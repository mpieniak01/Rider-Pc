"""Control commands, resource management, and camera feed endpoints."""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from pc_client.adapters import RestAdapter
from pc_client.providers import VisionProvider

logger = logging.getLogger(__name__)

router = APIRouter()


async def proxy_remote_media(request: Request, remote_path: str) -> Response:
    """Proxy binary media endpoints to Rider-PI."""
    adapter: RestAdapter = request.app.state.rest_adapter
    if adapter is None:
        raise HTTPException(status_code=503, detail="REST adapter not initialized")

    params = dict(request.query_params)
    try:
        content, media_type = await adapter.fetch_binary(remote_path, params=params)
        return Response(content=content, media_type=media_type)
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
    enabled = bool(payload.get("enabled", raw_mode in {"face", "hand"}))
    if not enabled:
        raw_mode = "none"
    return raw_mode, raw_mode != "none"


def _set_local_tracking_state(request: Request, mode: str, enabled: bool) -> Dict[str, Any]:
    """Update local tracking state cache + emit SSE."""
    state = {"mode": mode, "enabled": enabled}
    request.app.state.control_state["tracking"] = state
    _publish_event(request, "motion.bridge.event", {"event": "tracking_mode", "detail": state})
    return {"ok": True, **state}


def _publish_event(request: Request, topic: str, data: Dict[str, Any]):
    """Publish server-sent events to all subscribers."""
    payload = {"topic": topic, "data": data, "ts": time.time()}
    stale_subscribers: List[asyncio.Queue] = []
    for queue in request.app.state.event_subscribers:
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            stale_subscribers.append(queue)
    for queue in stale_subscribers:
        if queue in request.app.state.event_subscribers:
            request.app.state.event_subscribers.remove(queue)


@router.post("/api/control")
async def api_control_endpoint(request: Request, command: Dict[str, Any]) -> JSONResponse:
    """Forward control commands from the UI to Rider-PI."""
    cmd = command.get("cmd", "noop")
    entry = {"ts": time.time(), "command": command}
    request.app.state.motion_queue.append(entry)
    request.app.state.motion_queue[:] = request.app.state.motion_queue[-50:]
    if cmd == "move":
        _publish_event(request, "cmd.move", command)
    elif cmd == "stop":
        _publish_event(request, "cmd.stop", command)

    forward_result: Dict[str, Any]
    status_code = 200
    adapter: RestAdapter = request.app.state.rest_adapter
    if adapter is None:
        forward_result = {"ok": False, "error": "REST adapter not initialized"}
        status_code = 503
        logger.error("Cannot forward /api/control command: REST adapter unavailable")
    else:
        try:
            forward_result = await adapter.post_control(command)
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.error("Error forwarding control command to Rider-PI: %s", exc)
            forward_result = {"ok": False, "error": str(exc)}
            status_code = 502

    forward_ok = bool(forward_result.get("ok"))
    if not forward_ok:
        status = str(forward_result.get("status", "")).lower()
        forward_ok = status == "ok"

    response_payload = {"ok": forward_ok, "queued": len(request.app.state.motion_queue), "device_response": forward_result}
    if not forward_ok and "error" in forward_result:
        response_payload["error"] = forward_result["error"]
    return JSONResponse(response_payload, status_code=status_code if not forward_ok else 200)


@router.get("/api/motion/queue")
async def api_motion_queue(request: Request) -> JSONResponse:
    """Expose the latest motion queue entries collected during control calls."""
    now = time.time()
    items: List[Dict[str, Any]] = []
    for entry in reversed(request.app.state.motion_queue or []):
        cmd = entry.get("command", {}) if isinstance(entry, dict) else {}
        ts = entry.get("ts", 0) if isinstance(entry, dict) else 0
        items.append(
            {
                "source": cmd.get("source") or cmd.get("provider") or "pc-ui",
                "vx": cmd.get("vx"),
                "vy": cmd.get("vy"),
                "yaw": cmd.get("yaw"),
                "time_s": cmd.get("t"),
                "status": cmd.get("status") or cmd.get("cmd"),
                "age_s": round(max(0.0, now - ts), 2) if ts else None,
            }
        )
    return JSONResponse({"items": items})


@router.get("/api/control/state")
async def api_control_state(request: Request) -> JSONResponse:
    """Return current control state, preferring Rider-PI data."""
    adapter: Optional[RestAdapter] = request.app.state.rest_adapter
    state = dict(request.app.state.control_state)
    if adapter:
        try:
            remote_state = await adapter.get_control_state()
            if isinstance(remote_state, dict) and "error" not in remote_state:
                state = remote_state
                request.app.state.control_state.update(remote_state)
            else:
                logger.warning("Falling back to local control state: %s", remote_state.get("error"))
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to fetch control state from Rider-PI: %s", exc)
    state["updated_at"] = time.time()
    return JSONResponse(content=state)


@router.post("/api/vision/tracking/mode")
async def update_tracking_mode(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    """Update tracking mode state, forwarding to Rider-PI when possible."""
    adapter: Optional[RestAdapter] = request.app.state.rest_adapter
    body = payload or {}
    if adapter:
        try:
            result = await adapter.post_tracking_mode(body)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to forward tracking mode: %s", exc)
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=502)

        status_code = 200
        if not result.get("ok", True):
            status_code = 502
        else:
            mode = str(result.get("mode", "none")).strip().lower()
            enabled = bool(result.get("enabled", mode != "none"))
            _set_local_tracking_state(request, mode, enabled)
        return JSONResponse(result, status_code=status_code)

    mode, enabled = _normalize_tracking_request(body)
    result = _set_local_tracking_state(request, mode, enabled)
    return JSONResponse(result)


@router.post("/api/navigator/start")
async def navigator_start(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    """Start navigator with selected strategy."""
    strategy = payload.get("strategy", "standard")
    request.app.state.control_state["navigator"] = {"active": True, "strategy": strategy, "state": "navigating"}
    _publish_event(request, "navigator.start", {"strategy": strategy})
    return JSONResponse({"ok": True, "strategy": strategy})


@router.post("/api/navigator/stop")
async def navigator_stop(request: Request) -> JSONResponse:
    """Stop navigator."""
    strategy = request.app.state.control_state.get("navigator", {}).get("strategy", "standard")
    request.app.state.control_state["navigator"] = {"active": False, "strategy": strategy, "state": "idle"}
    _publish_event(request, "navigator.stop", {})
    return JSONResponse({"ok": True})


@router.post("/api/navigator/return_home")
async def navigator_return_home(request: Request) -> JSONResponse:
    """Simulate navigator return home action."""
    navigator = request.app.state.control_state.get("navigator", {})
    navigator_state = {
        "active": navigator.get("active", True),
        "strategy": navigator.get("strategy", "standard"),
        "state": "returning",
    }
    request.app.state.control_state["navigator"] = navigator_state
    _publish_event(request, "navigator.return_home", {})
    return JSONResponse({"ok": True, "state": "returning"})


@router.get("/api/resource/{resource_name}")
async def get_resource_status(request: Request, resource_name: str) -> JSONResponse:
    """Return resource status, preferring Rider-PI data when available."""
    local_resource = request.app.state.resources.get(resource_name)
    if not local_resource:
        return JSONResponse({"error": f"Resource {resource_name} not found"}, status_code=404)

    adapter: RestAdapter = request.app.state.rest_adapter
    result: Dict[str, Any]
    if adapter:
        try:
            remote_data = await adapter.get_resource(resource_name)
            if remote_data and not remote_data.get("error"):
                result = remote_data
            else:
                result = dict(local_resource)
                if remote_data and remote_data.get("error"):
                    result["error"] = remote_data["error"]
        except Exception as exc:  # pragma: no cover - defensive network error
            logger.error("Error fetching resource %s from Rider-PI: %s", resource_name, exc)
            result = dict(local_resource)
            result["error"] = str(exc)
    else:
        result = dict(local_resource)

    result.setdefault("checked_at", time.time())
    return JSONResponse(content=result)


@router.post("/api/resource/{resource_name}")
async def update_resource(request: Request, resource_name: str, payload: Dict[str, Any]) -> JSONResponse:
    """Forward resource actions (release/stop) to Rider-PI."""
    local_resource = request.app.state.resources.get(resource_name)
    if not local_resource:
        return JSONResponse({"error": f"Resource {resource_name} not found"}, status_code=404)
    adapter: RestAdapter = request.app.state.rest_adapter
    if not adapter:
        action = (payload or {}).get("action")
        if action in {"release", "stop"}:
            local_resource["free"] = True
            local_resource["holders"] = []
            local_resource["checked_at"] = time.time()
            _publish_event(request, "resource.update", {"resource": resource_name, "action": action})
            return JSONResponse({"ok": True, "resource": resource_name, "note": "local-only"})
        return JSONResponse({"error": f"Unsupported action {action}"}, status_code=400)

    action_payload = payload or {}
    try:
        response = await adapter.post_resource_action(resource_name, action_payload)
    except Exception as exc:  # pragma: no cover
        logger.error("Error posting resource action for %s: %s", resource_name, exc)
        response = {"ok": False, "error": str(exc)}

    status_code = 200
    if not response.get("ok", True) and "error" in response:
        status_code = 502
    return JSONResponse(content=response, status_code=status_code)


@router.get("/svc")
async def list_services(request: Request) -> JSONResponse:
    """Return systemd service states (proxy Rider-PI when possible)."""
    adapter: Optional[RestAdapter] = request.app.state.rest_adapter
    if adapter:
        remote = await adapter.get_services()
        if remote and not remote.get("error"):
            return JSONResponse(remote)
        logger.warning("Falling back to local /svc list: %s", remote.get("error") if remote else "unknown error")

    services = [{**svc, "ts": time.time()} for svc in request.app.state.services]
    return JSONResponse({"services": services, "timestamp": time.time()})


@router.post("/svc/{unit}")
async def control_service(request: Request, unit: str, payload: Dict[str, Any]) -> JSONResponse:
    """Handle service control actions (proxy Rider-PI when possible)."""
    adapter: Optional[RestAdapter] = request.app.state.rest_adapter
    if adapter:
        result = await adapter.service_action(unit, payload or {})
        status_code = 200
        if not result.get("ok", True) or result.get("error"):
            status_code = 502
        return JSONResponse(result, status_code=status_code)

    service = next((s for s in request.app.state.services if s["unit"] == unit), None)
    if not service:
        return JSONResponse({"error": f"Service {unit} not found"}, status_code=404)
    action = (payload or {}).get("action")
    if action == "start":
        service["active"] = "active"
        service["sub"] = "running"
    elif action == "stop":
        service["active"] = "inactive"
        service["sub"] = "dead"
    elif action == "restart":
        service["active"] = "active"
        service["sub"] = "running"
    elif action == "enable":
        service["enabled"] = "enabled"
    elif action == "disable":
        service["enabled"] = "disabled"
    else:
        return JSONResponse({"error": f"Unsupported action {action}"}, status_code=400)
    _publish_event(request, "service.action", {"unit": unit, "action": action})
    return JSONResponse({"ok": True, "unit": unit, "action": action})


def _camera_last_headers(request: Request) -> Dict[str, str]:
    ts = request.app.state.last_camera_frame["timestamp"]
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return {"Last-Modified": dt.strftime("%a, %d %b %Y %H:%M:%S GMT")}


@router.get("/camera/last")
async def camera_last(request: Request) -> Response:
    """Return last camera frame placeholder."""
    headers = _camera_last_headers(request)
    return Response(content=request.app.state.last_camera_frame["content"], media_type="image/png", headers=headers)


@router.head("/camera/last")
async def camera_last_head(request: Request) -> Response:
    """HEAD variant for last camera frame."""
    headers = _camera_last_headers(request)
    return Response(content=b"", media_type="image/png", headers=headers)


@router.get("/events")
async def events(request: Request):
    """Server-sent events endpoint for UI panels."""
    queue: asyncio.Queue = asyncio.Queue()
    request.app.state.event_subscribers.append(queue)

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
            if queue in request.app.state.event_subscribers:
                request.app.state.event_subscribers.remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
