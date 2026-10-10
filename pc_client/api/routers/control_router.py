"""Control commands, resource management, and camera feed endpoints."""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from pc_client.adapters import RestAdapter
from pc_client.providers import VisionProvider
from pc_client.api.sse_manager import SseManager
from pc_client.core.remote_safety import finite_number

if TYPE_CHECKING:
    from pc_client.core import ServiceManager

logger = logging.getLogger(__name__)

router = APIRouter()


async def proxy_remote_media(request: Request, remote_path: str) -> Response:
    """Proxy binary media endpoints to Rider-PI."""
    adapter: RestAdapter = request.app.state.rest_adapter
    if adapter is None:
        raise HTTPException(status_code=503, detail="REST adapter not initialized")

    params = dict(request.query_params)
    try:
        content, media_type, remote_headers = await adapter.fetch_binary(remote_path, params=params)
        headers = {key: value for key, value in remote_headers.items() if key.lower() != "content-type"}
        return Response(content=content, media_type=media_type, headers=headers)
    except Exception as e:
        logger.error(f"Failed to proxy {remote_path}: {e}")
        raise HTTPException(status_code=502, detail="Unable to fetch remote media")


@router.get("/vision/cam")
async def vision_cam_proxy(request: Request):
    """Proxy raw camera feed."""
    return await proxy_remote_media(request, "/vision/cam")


@router.get("/vision/edge")
async def vision_edge_proxy(request: Request):
    """Proxy processed edge feed."""
    return await proxy_remote_media(request, "/vision/edge")


@router.get("/vision/tracker")
async def vision_tracker_proxy(request: Request):
    """Serve tracker overlay feed."""
    provider = request.app.state.providers.get("vision")
    if isinstance(provider, VisionProvider):
        overlay, ts, fps = provider.get_tracker_snapshot()
        if overlay:
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


async def _remote_snapshot(request, key, method, empty):
    adapter = request.app.state.rest_adapter
    snapshots = request.app.state.remote_snapshots
    try:
        if adapter is None:
            raise RuntimeError("pi_offline")
        result = await getattr(adapter, method)()
        if not isinstance(result, dict) or result.get("error"):
            raise RuntimeError((result or {}).get("error", "invalid_response"))
        result = dict(result)
        result["source"] = "demo" if _demo_adapter(request) else "pi"
        result.setdefault("stale", False)
        result.setdefault("offline", False)
        result.setdefault("observed_at", time.time())
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
        snapshots[key] = result
        return result
    except Exception as exc:
        result = dict(snapshots.get(key, empty))
        result.update(ok=False, source=result.get("source", "pi"), stale=True, offline=True, error=str(exc))
        result.setdefault("observed_at", None)
        if key == "control":
            result["safety"] = {
                "state": "UNKNOWN",
                "ready": False,
                "can_move": False,
                "read_only": True,
                "reason": "pi_offline",
            }
        return result


async def _proxy_action(request, method, *args):
    adapter = request.app.state.rest_adapter
    if adapter is None:
        return JSONResponse({"ok": False, "error": "pi_offline"}, status_code=503)
    try:
        result = await getattr(adapter, method)(*args)
        if not isinstance(result, dict):
            raise ValueError("invalid_response")
        status = result.pop("_http_status", None)
        if result.get("ok") is not True and result.get("status") != "ok":
            return JSONResponse(result, status_code=status or 502)
        return JSONResponse(result, status_code=status or (202 if result.get("pending") else 200))
    except Exception as exc:
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
    cmd = str(command.get("cmd", "")).lower()
    if cmd not in {"move", "spin", "height", "balance", "action", "stop"}:
        raise HTTPException(status_code=400, detail="unsupported_actuator_command")
    body = dict(command)
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
    if enabled:
        body.update(await _motion_context(request, "follow_me", supplied=body))
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
            or not 0 <= time.time() - catalog["observed_at"] <= 3
            or not row
            or not isinstance(row.get("can_move"), bool)
        ):
            raise HTTPException(status_code=409, detail="unconfirmed_task_capability")
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


@router.post("/api/navigator/start")
async def navigator_start(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    return await feature_toggle(request, "s9_navigation", {**payload, "enabled": True})


@router.post("/api/navigator/stop")
async def navigator_stop(request: Request) -> JSONResponse:
    return await feature_toggle(request, "s9_navigation", {"enabled": False})


@router.post("/api/navigator/return_home")
async def navigator_return_home(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    context = await _motion_context(request, "navigation", supplied=payload)
    return await _proxy_action(request, "post_navigator_return_home", {**payload, **context})


@router.get("/api/resource/{resource_name}")
async def get_resource_status(request: Request, resource_name: str) -> JSONResponse:
    adapter = request.app.state.rest_adapter
    snapshots = request.app.state.remote_snapshots
    key = "resource:" + resource_name
    try:
        if adapter is None:
            raise RuntimeError("pi_offline")
        result = await adapter.get_resource(resource_name)
        if not isinstance(result, dict) or result.get("error"):
            raise RuntimeError((result or {}).get("error", "invalid_response"))
        result = {**result, "source": "demo" if _demo_adapter(request) else "pi"}
        result.setdefault("stale", False)
        result.setdefault("offline", False)
        result.setdefault("observed_at", time.time())
        snapshots[key] = result
    except Exception as exc:
        result = {
            **snapshots.get(key, {}),
            "name": resource_name,
            "free": None,
            "source": snapshots.get(key, {}).get("source", "pi"),
            "stale": True,
            "offline": True,
            "error": str(exc),
        }
    return JSONResponse(result)


@router.post("/api/resource/{resource_name}")
async def update_resource(request: Request, resource_name: str, payload: Dict[str, Any]) -> JSONResponse:
    if payload.get("action") not in {"release", "stop"}:
        raise HTTPException(status_code=400, detail="unsupported_resource_action")
    return await _proxy_action(request, "post_resource_action", resource_name, payload)


@router.get("/svc")
async def list_services(request: Request) -> JSONResponse:
    manager = request.app.state.service_manager
    manager.set_adapter(request.app.state.rest_adapter)
    manager.set_providers(request.app.state.providers)
    return JSONResponse(await manager.get_all_services())


@router.get("/api/systemd/services")
@router.get("/api/services/systemd")
@router.get("/api/services")
async def list_services_alias(request: Request) -> JSONResponse:
    return await list_services(request)


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


def _camera_last_headers(request: Request) -> Dict[str, str]:
    ts = request.app.state.last_camera_frame.get("timestamp", time.time())
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return {"Last-Modified": dt.strftime("%a, %d %b %Y %H:%M:%S GMT")}


@router.get("/camera/last")
async def camera_last(request: Request) -> Response:
    """Return last camera frame placeholder."""
    headers = _camera_last_headers(request)
    media_type = request.app.state.last_camera_frame.get("media_type", "image/png")
    return Response(
        content=request.app.state.last_camera_frame["content"],
        media_type=media_type,
        headers=headers,
    )


@router.head("/camera/last")
async def camera_last_head(request: Request) -> Response:
    """HEAD variant for last camera frame."""
    headers = _camera_last_headers(request)
    media_type = request.app.state.last_camera_frame.get("media_type", "image/png")
    return Response(content=b"", media_type=media_type, headers=headers)


@router.get("/events")
async def events(request: Request):
    """Server-sent events endpoint for UI panels."""
    manager = _get_sse_manager(request)
    queue = manager.subscribe()

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=5.0)
                except asyncio.TimeoutError:
                    payload = {"topic": "heartbeat", "data": {"status": "ok"}, "ts": time.time()}
                yield f"data: {json.dumps(payload)}\n\n"
        finally:
            manager.unsubscribe(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
