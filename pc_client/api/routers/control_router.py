"""Control commands, resource management, and camera feed endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

import httpx

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from pc_client.adapters import RestAdapter
from pc_client.api.sse_manager import SseManager
from pc_client.api.binary_snapshot import fetch_camera_binary
from pc_client.api.observation_policy import reuse_period
from pc_client.api.telemetry_snapshot import refresh_snapshot, invalidate_snapshots
from pc_client.core.remote_safety import finite_number
from pc_client.api.telemetry_snapshot import received_snapshot, unavailable_snapshot, transport_failure

if TYPE_CHECKING:
    from pc_client.providers import VisionProvider
    from pc_client.core import ServiceManager

logger = logging.getLogger(__name__)

router = APIRouter()


async def proxy_remote_media(request: Request, remote_path: str) -> Response:
    """Proxy binary media endpoints to Rider-PI."""
    adapter: RestAdapter = request.app.state.rest_adapter
    if adapter is None:
        raise HTTPException(status_code=503, detail="REST adapter not initialized")

    params = dict(request.query_params)
    if params.get("archive") != "1" and remote_path in {
        "/camera/last",
        "/vision/cam",
        "/vision/edge",
        "/vision/obst",
        "/vision/ssd",
        "/vision/tracker",
    }:
        from pc_client.api.background_sync import camera_activity

        if camera_activity(request.app) is False:
            raise HTTPException(
                status_code=404,
                detail="Camera is OFF",
                headers={"X-Rider-Stale": "true", "X-Rider-Source": "pi/camera", "Cache-Control": "no-store"},
            )
    try:
        if remote_path == "/camera/last":
            content, media_type, remote_headers = await fetch_camera_binary(request.app, params=params)
        else:
            content, media_type, remote_headers = await adapter.fetch_binary(remote_path, params=params)
        headers = {key: value for key, value in remote_headers.items() if key.lower() != "content-type"}
        return Response(content=content, media_type=media_type, headers=headers)
    except httpx.HTTPStatusError as exc:
        headers = {
            key: value
            for key, value in exc.response.headers.items()
            if key.lower().startswith("x-rider-") or key.lower() in {"cache-control", "pragma"}
        }
        raise HTTPException(
            status_code=exc.response.status_code, detail="Remote frame unavailable", headers=headers
        ) from exc
    except Exception as e:
        logger.error(f"Failed to proxy {remote_path}: {e}")
        raise HTTPException(status_code=502, detail="Unable to fetch remote media")


@router.get("/vision/cam")
async def vision_cam_proxy(request: Request):
    """Proxy raw camera feed."""
    return await proxy_remote_media(request, "/vision/cam")


@router.get("/vision/obst")
async def vision_obst_proxy(request: Request):
    return await proxy_remote_media(request, "/vision/obst")


@router.get("/vision/ssd")
async def vision_ssd_proxy(request: Request):
    return await proxy_remote_media(request, "/vision/ssd")


@router.get("/vision/edge")
async def vision_edge_proxy(request: Request):
    """Proxy processed edge feed."""
    return await proxy_remote_media(request, "/vision/edge")


@router.get("/vision/tracker")
async def vision_tracker_proxy(request: Request):
    """Serve tracker overlay feed."""
    provider = request.app.state.providers.get("vision")
    if provider is not None:
        from pc_client.providers import VisionProvider
    if provider is not None and isinstance(provider, VisionProvider):
        overlay, ts, fps = provider.get_tracker_snapshot()
        if overlay and finite_number(ts) and 0 <= time.time() - ts <= 3:
            headers = {
                "X-Tracker-FPS": f"{fps:.1f}",
                "X-Tracker-TS": f"{ts:.3f}",
            }
            return Response(content=overlay, media_type="image/png", headers=headers)
    return await proxy_remote_media(request, "/vision/tracker")


@router.get("/snapshots/{snapshot_path:path}")
async def snapshots_proxy(request: Request, snapshot_path: str):
    """Proxy snapshot images (e.g., obstacle annotations)."""
    return await proxy_remote_media(request, f"/snapshots/{snapshot_path}")


def _normalize_tracking_request(payload: Dict[str, Any]) -> tuple[str, bool]:
    """Validate and normalize tracking payload similar to Rider-PI."""
    raw_mode = str(payload.get("mode", "none")).strip().lower()
    if raw_mode not in {"face", "hand", "none"}:
        raise HTTPException(status_code=400, detail=f"Invalid tracking mode '{raw_mode}'")
    if "enabled" in payload and not isinstance(payload["enabled"], bool):
        raise HTTPException(status_code=400, detail="enabled_must_be_boolean")
    enabled = payload.get("enabled", raw_mode in {"face", "hand"})
    if not enabled:
        raw_mode = "none"
    return raw_mode, raw_mode != "none"


def _get_sse_manager(request: Request) -> SseManager:
    manager: Optional[SseManager] = getattr(request.app.state, "sse_manager", None)
    if manager is None:
        manager = SseManager()
        request.app.state.sse_manager = manager
    return manager


def _publish_event(request: Request, topic: str, data: Dict[str, Any]):
    """Publish server-sent events to all subscribers."""
    payload = {"topic": topic, "data": data, "ts": time.time()}
    manager = _get_sse_manager(request)
    manager.publish(payload)


def _emit_system_log(request: Request, level: str, action: str, unit: str, error: Optional[str] = None):
    """Emit a system.log SSE event for service control operations."""
    if error:
        message = f"Błąd: {action} dla {unit} - {error}"
    else:
        message = f"Sukces: {action} dla {unit}"
    _publish_event(request, "system.log", {"level": level, "message": message})


def _demo_adapter(request):
    from pc_client.adapters.mock_rest_adapter import MockRestAdapter

    adapter = request.app.state.rest_adapter
    return isinstance(adapter, MockRestAdapter)


async def _remote_snapshot(request, key, method, empty, *args, force=False):
    adapter = request.app.state.rest_adapter
    snapshots = request.app.state.remote_snapshots
    try:
        if adapter is None:
            raise RuntimeError("pi_offline")
        shared = (key.startswith("resource:") or key == "catalog") and getattr(
            request.app.state, "cache", None
        ) is not None
        if shared:
            cache_key = {"resource:camera": "camera_resource", "resource:lcd": "lcd_resource"}.get(key, key)
            result = await refresh_snapshot(
                request.app,
                cache_key,
                lambda: getattr(adapter, method)(*args),
                reuse_s=0.0 if force else reuse_period(key),
            )
        else:
            result = await getattr(adapter, method)(*args)
        if not isinstance(result, dict) or transport_failure(result):
            raise RuntimeError((result or {}).get("error", "invalid_response"))
        quality = {key: result.get(key) for key in ("stale", "offline")}
        result = (
            dict(result)
            if shared
            else received_snapshot(result, source="demo" if _demo_adapter(request) else "pi", received_at=time.time())
        )
        # Błąd konfiguracji/domeny nie oznacza awarii transportu ani starego odczytu.
        for flag, value in quality.items():
            result[flag] = value is True
        if key == "control":
            safety = result.get("safety", {})
            if safety.get("contract_version") != 1:
                result["safety"] = {
                    "state": "UNKNOWN",
                    "ready": False,
                    "can_move": False,
                    "read_only": True,
                    "reason": "legacy_safety_contract",
                }
        if not shared:
            snapshots[key] = result
        return result
    except Exception as exc:
        result = unavailable_snapshot(
            snapshots.get(key, empty),
            source="demo" if _demo_adapter(request) else "pi",
            error=str(exc),
            attempted_at=time.time(),
        )
        if key == "control":
            # Preserve the last executor permission; mark only its observation
            # unavailable. No client-side transition to DISARMED/UNKNOWN.
            previous = dict(snapshots.get(key, {}).get("safety") or {})
            result["safety"] = {
                **previous,
                "state": previous.get("state", "UNKNOWN"),
                "ready": False,
                "can_move": False,
                "read_only": True,
                "stale": True,
                "observation_error": "pi_offline",
            }
            if previous.get("authorization"):
                result["safety"]["authorization"] = {**previous["authorization"], "confirmed": False}
        return result


async def _proxy_action(request, method, *args):
    adapter = request.app.state.rest_adapter
    if adapter is None:
        return JSONResponse({"ok": False, "error": "pi_offline"}, status_code=503)
    try:
        if method in {"post_feature_toggle", "post_resource_action", "post_service_action"}:
            invalidate_snapshots(request.app)
        result = await getattr(adapter, method)(*args)
        if method in {"post_feature_toggle", "post_resource_action", "post_service_action"}:
            invalidate_snapshots(request.app)
        if not isinstance(result, dict):
            raise ValueError("invalid_response")
        result = dict(result)
        status = result.pop("_http_status", None)
        operation = result.get("operation") or {}
        legacy_provider = (
            method == "patch_provider"
            and isinstance(result.get("state"), dict)
            and isinstance(result.get("changed"), bool)
            and not result.get("error")
        )
        pending = status == 202 or result.get("pending") is True or operation.get("status") == "pending"
        if result.get("error") or (
            result.get("ok") is not True and result.get("status") != "ok" and not legacy_provider and not pending
        ):
            return JSONResponse(result, status_code=status or 502)
        return JSONResponse(result, status_code=status or (202 if pending else 200))
    except Exception as exc:
        if method in {"post_feature_toggle", "post_resource_action", "post_service_action"}:
            invalidate_snapshots(request.app)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=502)


async def _motion_context(request, owner="manual", supplied=None):
    try:
        return await request.app.state.remote_safety.command_context(
            request.app.state.rest_adapter, owner, supplied=supplied
        )
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/api/safety")
async def safety_action(request: Request, payload: Dict[str, Any]):
    action = payload.get("action")
    if action not in {"arm", "disarm", "estop", "clear_estop"}:
        raise HTTPException(status_code=400, detail="invalid_safety_action")
    if action in {"arm", "clear_estop"}:
        if payload.get("operator_consent") is not True or (
            not isinstance(payload.get("operator_plan"), str) or not payload["operator_plan"].strip()
        ):
            raise HTTPException(status_code=400, detail="explicit_operator_plan_required")
        try:
            context = await request.app.state.remote_safety.command_context(
                request.app.state.rest_adapter, require_armed=False, supplied=payload
            )
        except Exception as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        payload = {**payload, **context}
    return await _proxy_action(request, "post_safety", payload)


@router.post("/api/control")
async def api_control_endpoint(request: Request, command: Dict[str, Any]) -> JSONResponse:
    cmd = str(command.get("action", command.get("cmd", ""))).lower()
    if cmd not in {"move", "turn", "spin", "height", "balance", "stabilization", "action", "stop"}:
        raise HTTPException(status_code=400, detail="unsupported_actuator_command")
    body = dict(command)
    body.setdefault("action", "turn" if cmd == "spin" else cmd)
    if cmd != "stop":
        body.update(await _motion_context(request, supplied=body))
    response = await _proxy_action(request, "post_control", body)
    entry = {"ts": time.time(), "command": body, "response": json.loads(response.body)}
    request.app.state.motion_queue.append(entry)
    request.app.state.motion_queue[:] = request.app.state.motion_queue[-50:]
    return response


@router.get("/api/motion/queue")
async def api_motion_queue(request: Request) -> JSONResponse:
    result = await _remote_snapshot(request, "queue", "get_motion_queue", {"items": []})
    result["local_request_history"] = list(request.app.state.motion_queue)
    return JSONResponse(result)


@router.get("/api/control/state")
async def api_control_state(request: Request) -> JSONResponse:
    result = await _remote_snapshot(request, "control", "get_control_state", {})
    return JSONResponse(result)


@router.post("/api/vision/tracking/mode")
async def update_tracking_mode(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    mode, enabled = _normalize_tracking_request(payload)
    body = {**payload, "mode": mode, "enabled": enabled}
    # Ten alias oznacza pasywne S6; nie uruchamia producenta ruchu S3.
    return await _proxy_action(request, "post_tracking_mode", body)


@router.post("/api/logic/feature/{name}")
async def feature_toggle(request: Request, name: str, payload: Dict[str, Any]) -> JSONResponse:
    if not isinstance(payload.get("enabled"), bool):
        raise HTTPException(status_code=400, detail="enabled_must_be_boolean")
    body = dict(payload)
    if body["enabled"]:
        catalog = await _remote_snapshot(request, "features", "get_logic_features", {"features": []})
        row = next(
            (r for r in catalog.get("features", []) if r.get("name") == name or name in r.get("aliases", [])), None
        )
        if (
            catalog.get("offline")
            or catalog.get("stale")
            or type(catalog.get("contract_version")) is not int
            or catalog["contract_version"] != 2
            or not finite_number(catalog.get("observed_at"))
            or not 0
            <= (catalog.get("server_time") if finite_number(catalog.get("server_time")) else time.time())
            - catalog["observed_at"]
            <= 3
            or not row
            or not isinstance(row.get("can_move"), bool)
        ):
            raise HTTPException(status_code=409, detail="unconfirmed_task_capability")
        if row.get("start_available") is False:
            raise HTTPException(status_code=409, detail=row.get("start_unavailable_reason") or "capability_unavailable")
        if row.get("installed") is False or row.get("stale") is True:
            raise HTTPException(status_code=409, detail="task_unavailable")
        if row["can_move"]:
            owner = row.get("motion_owner")
            if owner not in {"manual", "follow_me", "navigation"}:
                raise HTTPException(status_code=409, detail="unknown_motion_owner")
            body.update(await _motion_context(request, owner, supplied=body))
    return await _proxy_action(request, "post_feature_toggle", name, body)


@router.get("/api/logic/features")
async def logic_features(request: Request) -> JSONResponse:
    return JSONResponse(await _remote_snapshot(request, "features", "get_logic_features", {"features": []}))


@router.get("/api/logic/summary")
async def logic_summary(request: Request) -> JSONResponse:
    return JSONResponse(await _remote_snapshot(request, "summary", "get_logic_summary", {"features": []}))


@router.get("/api/logic/catalog")
async def logic_catalog(request: Request) -> JSONResponse:
    return JSONResponse(
        await _remote_snapshot(
            request, "catalog", "get_logic_catalog", {"features": [], "services": [], "resources": []}
        )
    )


@router.get("/api/navigator/status")
async def navigator_status(request: Request) -> JSONResponse:
    return JSONResponse(await _remote_snapshot(request, "navigator", "get_navigator_status", {}))


@router.post("/api/navigator/config")
async def navigator_config(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    snapshot = await _remote_snapshot(request, "control", "get_control_state", {})
    safety = snapshot.get("safety", {})
    if snapshot.get("offline") or snapshot.get("stale") or safety.get("state") != "DISARMED":
        raise HTTPException(status_code=409, detail="disarmed_contract_required")
    if safety.get("contract_version") != 1 or not finite_number(safety.get("observed_at")):
        raise HTTPException(status_code=409, detail="disarmed_contract_required")
    peer_now = snapshot.get("server_time")
    if not finite_number(peer_now) or not -0.1 <= peer_now - safety["observed_at"] <= 3:
        raise HTTPException(status_code=409, detail="disarmed_contract_required")
    return await _proxy_action(request, "post_navigator_config", payload)


@router.post("/api/navigator/start")
async def navigator_start(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    return await feature_toggle(request, "s9_navigation", {**payload, "enabled": True})


@router.post("/api/navigator/stop")
async def navigator_stop(request: Request) -> JSONResponse:
    return await feature_toggle(request, "s9_navigation", {"enabled": False})


@router.post("/api/navigator/return_home")
async def navigator_return_home(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    raise HTTPException(status_code=409, detail="navigation_traversal_unverified")


@router.get("/api/resource/{resource_name}")
async def get_resource_status(request: Request, resource_name: str) -> JSONResponse:
    return JSONResponse(
        await _remote_snapshot(
            request, "resource:" + resource_name, "get_resource", {"name": resource_name, "free": None}, resource_name
        )
    )


@router.post("/api/resource/{resource_name}")
async def update_resource(request: Request, resource_name: str, payload: Dict[str, Any]) -> JSONResponse:
    if payload.get("action") not in {"release", "stop"}:
        raise HTTPException(status_code=400, detail="unsupported_resource_action")
    return await _proxy_action(request, "post_resource_action", resource_name, payload)


@router.get("/svc")
async def list_services(request: Request) -> JSONResponse:
    manager = request.app.state.service_manager
    manager.set_adapter(request.app.state.rest_adapter)
    manager.set_providers(
        {
            **request.app.state.providers,
            **({"text": request.app.state.text_provider} if request.app.state.text_provider is not None else {}),
        }
    )
    return JSONResponse(await manager.get_all_services())


@router.get("/api/systemd/services")
@router.get("/api/services/systemd")
@router.get("/api/services")
async def list_services_alias(request: Request) -> JSONResponse:
    return await list_services(request)


@router.get("/api/services/{unit}/logs")
async def service_logs(request: Request, unit: str, host: str):
    manager = request.app.state.service_manager
    manager.set_adapter(request.app.state.rest_adapter)
    result = await manager.get_service_logs(unit, host)
    code = result.pop("status_code", 200 if result.get("ok") is True else 503)
    return JSONResponse(result, status_code=code, headers={"Cache-Control": "no-store"})


def _extract_service_unit(payload):
    return next((str(payload[k]) for k in ("unit", "service", "name", "id") if payload.get(k)), None)


@router.post("/svc/{unit}")
async def control_service(request: Request, unit: str, payload: Dict[str, Any]) -> JSONResponse:
    manager = request.app.state.service_manager
    manager.set_adapter(request.app.state.rest_adapter)
    result = await manager.control_service(unit, payload.get("action"), host=payload.get("host"), payload=payload)
    if result.get("ok") is True and not result.get("pending"):
        _publish_event(
            request, "service.action", {"unit": unit, "host": payload.get("host"), "action": payload.get("action")}
        )
        _emit_system_log(request, "INFO", payload.get("action"), unit)
    elif not result.get("pending"):
        _emit_system_log(request, "ERROR", payload.get("action"), unit, result.get("error"))
    status_code = result.pop("status_code", result.pop("_http_status", None))
    status_code = status_code or (202 if result.get("pending") else 200 if result.get("ok") is True else 502)
    return JSONResponse(result, status_code=status_code)


async def _control_service_alias(request: Request, payload: Optional[Dict[str, Any]]) -> JSONResponse:
    data = payload or {}
    unit = _extract_service_unit(data)
    if not unit:
        raise HTTPException(status_code=400, detail="missing_service_unit")
    return await control_service(request, unit, data)


@router.post("/api/systemd/action")
@router.post("/api/services/systemd/action")
@router.post("/api/services/action")
async def api_service_action_alias(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    return await _control_service_alias(request, payload)


async def _camera_last_response(request: Request) -> Response:
    """Bieżący obraz pochodzi z resolvera Pi; lokalny placeholder nigdy nie jest klatką."""
    response = await proxy_remote_media(request, "/camera/last")
    headers = response.headers
    archive = request.query_params.get("archive") == "1"
    file_time = headers.get("x-rider-file-observed-at")
    observed = headers.get("x-rider-observed-at")
    try:
        known_time = any(finite_number(float(value)) and float(value) > 0 for value in (file_time, observed) if value)
    except (ValueError, OverflowError):
        known_time = False
    if headers.get("x-rider-placeholder") != "false" or (
        not archive
        and (
            headers.get("x-rider-stale") != "false"
            or headers.get("x-rider-contract") != "rider.frames;version=1"
            or not known_time
        )
    ):
        failure_headers = {key: value for key, value in headers.items() if key.startswith("x-rider-")}
        failure_headers["Cache-Control"] = "no-store"
        raise HTTPException(status_code=404, detail="Current frame unavailable", headers=failure_headers)
    return response


@router.get("/camera/last")
async def camera_last(request: Request) -> Response:
    return await _camera_last_response(request)


@router.head("/camera/last")
async def camera_last_head(request: Request) -> Response:
    response = await _camera_last_response(request)
    return Response(
        content=b"", status_code=response.status_code, media_type=response.media_type, headers=dict(response.headers)
    )


@router.get("/events")
async def events(request: Request):
    """Server-sent events endpoint for UI panels."""
    manager = _get_sse_manager(request)
    cursor = request.headers.get("last-event-id") or request.query_params.get("after")
    after_id = int(cursor) if cursor and cursor.isdigit() else None
    queue = manager.subscribe(after_id)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=5.0)
                except asyncio.TimeoutError:
                    payload = {"topic": "heartbeat", "data": {"status": "ok"}, "ts": time.time()}
                event_id = payload.get("event_id")
                prefix = f"id: {event_id}\n" if event_id is not None else ""
                yield f"{prefix}data: {json.dumps(payload)}\n\n"
        finally:
            manager.unsubscribe(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/api/odometry/state")
@router.get("/api/calibration/controls")
@router.get("/api/calibration/state")
@router.get("/api/calibration/profiles")
@router.get("/api/calibration/profiles/{digest}")
async def configuration_snapshot(request: Request, digest: str = ""):
    path = request.url.path
    return JSONResponse(await _remote_snapshot(request, path, "get_json", {}, path))


@router.post("/api/odometry/reference")
@router.post("/api/calibration/controls")
@router.post("/api/calibration/profiles")
@router.post("/api/calibration/activate")
async def configuration_request(request: Request, payload: Dict[str, Any]):
    # API źródła waliduje oryginalną DISARMED kopertę/zgodę. Proxy nic nie dodaje.
    return await _proxy_action(request, "_post_operator_action", request.url.path, payload)
