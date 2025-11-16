"""FastAPI server for replicating Rider-PI UI."""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.datastructures import MutableHeaders

from pc_client.config import Settings
from pc_client.cache import CacheManager
from pc_client.adapters import RestAdapter, ZmqSubscriber

logger = logging.getLogger(__name__)


def create_app(settings: Settings, cache: CacheManager) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        settings: Application settings
        cache: Cache manager instance

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(title="Rider-PC Client", description="PC-side client replicating Rider-PI UI", version="0.1.0")

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store settings and cache in app state
    app.state.settings = settings
    app.state.cache = cache
    app.state.rest_adapter = None
    app.state.zmq_subscriber = None
    app.state.control_state = {
        "tracking": {"mode": "none", "enabled": False},
        "navigator": {"active": False, "strategy": "standard", "state": "idle"},
        "camera": {"vision_enabled": True, "on": True, "res": [1280, 720]},
    }
    app.state.resources: Dict[str, Dict[str, Any]] = {
        "mic": {"name": "mic", "free": True, "holders": [], "checked_at": time.time()},
        "speaker": {"name": "speaker", "free": True, "holders": [], "checked_at": time.time()},
        "camera": {
            "name": "camera",
            "free": False,
            "holders": [{"pid": 4242, "cmd": "rider-cam", "service": "rider-cam-preview.service"}],
            "checked_at": time.time(),
        },
        "lcd": {"name": "lcd", "free": True, "holders": [], "checked_at": time.time()},
    }
    app.state.services: List[Dict[str, Any]] = [
        {
            "unit": "rider-cam-preview.service",
            "desc": "Camera preview pipeline",
            "active": "active",
            "sub": "running",
            "enabled": "enabled",
        },
        {
            "unit": "rider-edge-preview.service",
            "desc": "Edge detection preview",
            "active": "inactive",
            "sub": "dead",
            "enabled": "enabled",
        },
        {
            "unit": "rider-vision.service",
            "desc": "Vision main stack",
            "active": "active",
            "sub": "running",
            "enabled": "enabled",
        },
        {
            "unit": "rider-tracker.service",
            "desc": "Vision tracker",
            "active": "inactive",
            "sub": "dead",
            "enabled": "enabled",
        },
        {
            "unit": "rider-tracking-controller.service",
            "desc": "Tracking controller",
            "active": "inactive",
            "sub": "dead",
            "enabled": "enabled",
        },
    ]
    app.state.motion_queue: List[Dict[str, Any]] = []
    app.state.last_camera_frame = {
        "content": (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02"
            b"\x08\x06\x00\x00\x00\xf4x\xd4\xfa\x00\x00\x00\x19IDATx\x9cc```\xf8"
            b"\x0f\x04\x0c\x0c\x0c\x0c\x00\x01\x04\x01\x00tC^\x8f\x00\x00\x00\x00IEND"
            b"\xaeB`\x82"
        ),
        "timestamp": time.time(),
    }
    app.state.event_subscribers: List[asyncio.Queue] = []

    def publish_event(topic: str, data: Dict[str, Any]):
        """Publish server-sent events to all subscribers."""
        payload = {"topic": topic, "data": data, "ts": time.time()}
        stale_subscribers: List[asyncio.Queue] = []
        for queue in app.state.event_subscribers:
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                stale_subscribers.append(queue)
        for queue in stale_subscribers:
            if queue in app.state.event_subscribers:
                app.state.event_subscribers.remove(queue)

    # Background task for data synchronization
    app.state.sync_task = None

    @app.on_event("startup")
    async def startup_event():
        """Initialize connections on startup."""
        logger.info("Starting Rider-PC Client API server...")

        # Initialize REST adapter
        app.state.rest_adapter = RestAdapter(
            base_url=settings.rider_pi_base_url,
            secure_mode=settings.secure_mode,
            mtls_cert_path=settings.mtls_cert_path,
            mtls_key_path=settings.mtls_key_path,
            mtls_ca_path=settings.mtls_ca_path,
        )
        logger.info(f"REST adapter initialized for {settings.rider_pi_base_url}")

        # Initialize ZMQ subscriber
        app.state.zmq_subscriber = ZmqSubscriber(
            settings.zmq_pub_endpoint, topics=["vision.*", "motion.*", "robot.*", "navigator.*"]
        )

        # Register ZMQ handlers to update cache
        def cache_handler(topic: str, data: Dict[str, Any]):
            """Handler to cache ZMQ messages."""
            cache.set(f"zmq:{topic}", data)
            logger.debug(f"Cached ZMQ message for topic: {topic}")

        for topic in ["vision.*", "motion.*", "robot.*", "navigator.*"]:
            app.state.zmq_subscriber.subscribe_topic(topic, cache_handler)

        # Start ZMQ subscriber in background
        asyncio.create_task(app.state.zmq_subscriber.start())
        logger.info("ZMQ subscriber started")

        # Start background sync task
        app.state.sync_task = asyncio.create_task(sync_data_periodically(app))
        logger.info("Background sync task started")

    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup on shutdown."""
        logger.info("Shutting down Rider-PC Client API server...")

        # Stop sync task
        if app.state.sync_task:
            app.state.sync_task.cancel()
            try:
                await app.state.sync_task
            except asyncio.CancelledError:
                pass

        # Stop ZMQ subscriber
        if app.state.zmq_subscriber:
            await app.state.zmq_subscriber.stop()

        # Close REST adapter
        if app.state.rest_adapter:
            await app.state.rest_adapter.close()

        logger.info("Shutdown complete")

    # API Endpoints

    @app.get("/healthz")
    async def healthz() -> JSONResponse:
        """Health check endpoint (deprecated, use /health/live)."""
        data = cache.get("healthz", {"ok": True, "status": "ok"})
        return JSONResponse(content=data)

    @app.get("/health/live")
    async def health_live() -> JSONResponse:
        """
        Liveness probe endpoint.
        Returns 200 if the application is running and responsive.
        Used by container orchestrators to determine if the app should be restarted.
        """
        return JSONResponse(content={"status": "alive", "timestamp": time.time()})

    @app.get("/health/ready")
    async def health_ready() -> JSONResponse:
        """
        Readiness probe endpoint.
        Returns 200 if the application is ready to serve requests.
        Checks critical components: cache, providers, and queue.
        Used by container orchestrators to determine if traffic should be routed to this instance.
        """
        # Check cache health
        cache_healthy = True
        cache_error = None
        try:
            cache.get("_health_check", None)
        except Exception as e:
            logger.error(f"Cache health check failed: {e}")
            cache_healthy = False
            cache_error = str(e)

        # Check if adapters are initialized
        adapters_ready = (
            hasattr(app.state, 'rest_adapter')
            and app.state.rest_adapter is not None
            and hasattr(app.state, 'zmq_subscriber')
            and app.state.zmq_subscriber is not None
        )

        # Overall readiness
        ready = cache_healthy and adapters_ready
        status_code = 200 if ready else 503

        return JSONResponse(
            status_code=status_code,
            content={
                "status": "ready" if ready else "not_ready",
                "timestamp": time.time(),
                "checks": {
                    "cache": {"status": "healthy" if cache_healthy else "unhealthy", "error": cache_error},
                    "adapters": "ready" if adapters_ready else "not_ready",
                },
            },
        )

    @app.get("/state")
    async def state() -> JSONResponse:
        """State endpoint."""
        data = cache.get("state", {"present": False, "mode": "idle"})
        return JSONResponse(content=data)

    @app.get("/sysinfo")
    async def sysinfo() -> JSONResponse:
        """System info endpoint."""
        data = cache.get("sysinfo", {})
        return JSONResponse(content=data)

    @app.get("/vision/snap-info")
    async def vision_snap_info() -> JSONResponse:
        """Vision snapshot info endpoint."""
        data = cache.get("vision_snap_info", {})
        return JSONResponse(content=data)

    @app.get("/vision/obstacle")
    async def vision_obstacle() -> JSONResponse:
        """Vision obstacle endpoint."""
        # Try ZMQ cache first, then REST cache
        data = cache.get("zmq:vision.obstacle", cache.get("vision_obstacle", {}))
        return JSONResponse(content=data)

    @app.get("/api/app-metrics")
    async def app_metrics() -> JSONResponse:
        """App metrics endpoint."""
        data = cache.get("app_metrics", {"ok": True, "metrics": {}, "total_errors": 0})
        return JSONResponse(content=data)

    @app.get("/api/resource/camera")
    async def camera_resource() -> JSONResponse:
        """Camera resource endpoint."""
        data = cache.get("camera_resource", {})
        return JSONResponse(content=data)

    @app.get("/api/bus/health")
    async def bus_health() -> JSONResponse:
        """Bus health endpoint."""
        data = cache.get("bus_health", {})
        return JSONResponse(content=data)

    @app.get("/camera/placeholder")
    async def camera_placeholder() -> Response:
        """Placeholder image for camera."""
        # Return a simple 1x1 transparent PNG
        png_data = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
            b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
            b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01'
            b'\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        return Response(content=png_data, media_type="image/png")

    @app.get("/metrics")
    async def metrics() -> Response:
        """Prometheus metrics endpoint."""
        metrics_data = generate_latest()
        return Response(content=metrics_data, media_type=CONTENT_TYPE_LATEST)

    async def proxy_remote_media(remote_path: str, request: Request) -> Response:
        """Proxy binary media endpoints to Rider-PI."""
        adapter: RestAdapter = app.state.rest_adapter
        if adapter is None:
            raise HTTPException(status_code=503, detail="REST adapter not initialized")

        params = dict(request.query_params)
        try:
            content, media_type = await adapter.fetch_binary(remote_path, params=params)
            return Response(content=content, media_type=media_type)
        except Exception as e:
            logger.error(f"Failed to proxy {remote_path}: {e}")
            raise HTTPException(status_code=502, detail="Unable to fetch remote media")

    @app.get("/vision/cam")
    async def vision_cam_proxy(request: Request):
        """Proxy raw camera feed."""
        return await proxy_remote_media("/vision/cam", request)

    @app.get("/vision/edge")
    async def vision_edge_proxy(request: Request):
        """Proxy processed edge feed."""
        return await proxy_remote_media("/vision/edge", request)

    @app.get("/vision/tracker")
    async def vision_tracker_proxy(request: Request):
        """Proxy tracker overlay feed."""
        return await proxy_remote_media("/vision/tracker", request)

    @app.get("/snapshots/{snapshot_path:path}")
    async def snapshots_proxy(snapshot_path: str, request: Request):
        """Proxy snapshot images (e.g., obstacle annotations)."""
        return await proxy_remote_media(f"/snapshots/{snapshot_path}", request)

    # Provider Control Endpoints

    @app.get("/api/providers/state")
    async def providers_state() -> JSONResponse:
        """
        Get current state of all AI providers.
        Mock implementation for Phase 3.
        """
        providers_data = cache.get(
            "providers_state",
            {
                "voice": {"current": "local", "status": "online", "last_health_check": "2025-11-12T14:00:00Z"},
                "text": {"current": "local", "status": "online", "last_health_check": "2025-11-12T14:00:00Z"},
                "vision": {"current": "local", "status": "online", "last_health_check": "2025-11-12T14:00:00Z"},
            },
        )
        return JSONResponse(content=providers_data)

    @app.patch("/api/providers/{domain}")
    async def update_provider(domain: str) -> JSONResponse:
        """
        Update provider configuration for a specific domain.
        Mock implementation for Phase 3.

        Args:
            domain: Provider domain (voice, text, vision)
        """
        # Validate domain
        valid_domains = ["voice", "text", "vision"]
        if domain not in valid_domains:
            return JSONResponse(status_code=400, content={"error": f"Invalid domain. Must be one of {valid_domains}"})

        # Get current state
        providers_state = cache.get(
            "providers_state",
            {
                "voice": {"current": "local", "status": "online"},
                "text": {"current": "local", "status": "online"},
                "vision": {"current": "local", "status": "online"},
            },
        )

        # Update the provider
        # In real implementation, this would send command to Rider-PI
        if domain in providers_state:
            providers_state[domain]["current"] = "pc"  # Mock switching to PC
            providers_state[domain]["status"] = "online"
            cache.set("providers_state", providers_state)

            logger.info(f"Provider {domain} switched to PC (mock)")

            return JSONResponse(content={"success": True, "domain": domain, "new_state": providers_state[domain]})

        return JSONResponse(status_code=404, content={"error": f"Provider {domain} not found"})

    @app.get("/api/providers/health")
    async def providers_health() -> JSONResponse:
        """
        Get health status of all providers.
        Mock implementation for Phase 3.
        """
        health_data = cache.get(
            "providers_health",
            {
                "voice": {
                    "status": "healthy",
                    "latency_ms": 45.2,
                    "success_rate": 0.98,
                    "last_check": "2025-11-12T14:00:00Z",
                },
                "text": {
                    "status": "healthy",
                    "latency_ms": 120.5,
                    "success_rate": 0.95,
                    "last_check": "2025-11-12T14:00:00Z",
                },
                "vision": {
                    "status": "healthy",
                    "latency_ms": 85.3,
                    "success_rate": 0.99,
                    "last_check": "2025-11-12T14:00:00Z",
                },
            },
        )
        return JSONResponse(content=health_data)

    @app.get("/api/services/graph")
    async def services_graph() -> JSONResponse:
        """
        Get system services graph for system dashboard.
        Mock implementation for Phase 3.
        """
        import time

        graph_data = cache.get(
            "services_graph",
            {
                "generated_at": time.time(),
                "nodes": [
                    {
                        "label": "FastAPI Server",
                        "unit": "pc_client.service",
                        "status": "active",
                        "group": "api",
                        "since": "2025-11-12 14:00:00",
                        "description": "Main REST API server",
                        "edges_out": ["cache", "zmq"],
                    },
                    {
                        "label": "Cache Manager",
                        "unit": "cache.service",
                        "status": "active",
                        "group": "data",
                        "since": "2025-11-12 14:00:00",
                        "description": "SQLite cache for data buffering",
                        "edges_out": [],
                    },
                    {
                        "label": "ZMQ Subscriber",
                        "unit": "zmq.service",
                        "status": "active",
                        "group": "messaging",
                        "since": "2025-11-12 14:00:00",
                        "description": "Real-time data stream subscriber",
                        "edges_out": ["cache"],
                    },
                    {
                        "label": "Voice Provider",
                        "unit": "voice.provider",
                        "status": "active",
                        "group": "providers",
                        "since": "2025-11-12 14:00:00",
                        "description": "ASR/TTS processing",
                        "edges_out": ["task_queue"],
                    },
                    {
                        "label": "Vision Provider",
                        "unit": "vision.provider",
                        "status": "active",
                        "group": "providers",
                        "since": "2025-11-12 14:00:00",
                        "description": "Object detection and frame processing",
                        "edges_out": ["task_queue"],
                    },
                    {
                        "label": "Text Provider",
                        "unit": "text.provider",
                        "status": "active",
                        "group": "providers",
                        "since": "2025-11-12 14:00:00",
                        "description": "LLM text generation and NLU",
                        "edges_out": ["task_queue", "cache"],
                    },
                    {
                        "label": "Task Queue",
                        "unit": "task_queue.service",
                        "status": "active",
                        "group": "queue",
                        "since": "2025-11-12 14:00:00",
                        "description": "Redis-based task queue",
                        "edges_out": [],
                    },
                    {
                        "label": "Telemetry Publisher",
                        "unit": "telemetry.service",
                        "status": "active",
                        "group": "monitoring",
                        "since": "2025-11-12 14:00:00",
                        "description": "ZMQ telemetry and Prometheus metrics",
                        "edges_out": [],
                    },
                ],
                "edges": [],
            },
        )
        return JSONResponse(content=graph_data)

    @app.post("/api/control")
    async def api_control_endpoint(command: Dict[str, Any]) -> JSONResponse:
        """Forward control commands from the UI to Rider-PI."""
        cmd = command.get("cmd", "noop")
        entry = {"ts": time.time(), "command": command}
        app.state.motion_queue.append(entry)
        app.state.motion_queue[:] = app.state.motion_queue[-50:]
        if cmd == "move":
            publish_event("cmd.move", command)
        elif cmd == "stop":
            publish_event("cmd.stop", command)

        forward_result: Dict[str, Any]
        status_code = 200
        adapter: RestAdapter = app.state.rest_adapter
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

        response_payload = {"ok": forward_ok, "queued": len(app.state.motion_queue), "device_response": forward_result}
        if not forward_ok and "error" in forward_result:
            response_payload["error"] = forward_result["error"]
        return JSONResponse(response_payload, status_code=status_code if not forward_ok else 200)

    @app.get("/api/control/state")
    async def api_control_state() -> JSONResponse:
        """Return current mock control state."""
        state = dict(app.state.control_state)
        state["updated_at"] = time.time()
        return JSONResponse(content=state)

    @app.post("/api/vision/tracking/mode")
    async def update_tracking_mode(payload: Dict[str, Any]) -> JSONResponse:
        """Update tracking mode state."""
        mode = payload.get("mode", "none")
        enabled = bool(payload.get("enabled", False)) and mode != "none"
        app.state.control_state["tracking"] = {"mode": mode, "enabled": enabled}
        publish_event("motion.bridge.event", {"event": "tracking_mode", "detail": {"mode": mode, "enabled": enabled}})
        return JSONResponse({"ok": True, "mode": mode, "enabled": enabled})

    @app.post("/api/navigator/start")
    async def navigator_start(payload: Dict[str, Any]) -> JSONResponse:
        """Start navigator with selected strategy."""
        strategy = payload.get("strategy", "standard")
        app.state.control_state["navigator"] = {"active": True, "strategy": strategy, "state": "navigating"}
        publish_event("navigator.start", {"strategy": strategy})
        return JSONResponse({"ok": True, "strategy": strategy})

    @app.post("/api/navigator/stop")
    async def navigator_stop() -> JSONResponse:
        """Stop navigator."""
        strategy = app.state.control_state.get("navigator", {}).get("strategy", "standard")
        app.state.control_state["navigator"] = {"active": False, "strategy": strategy, "state": "idle"}
        publish_event("navigator.stop", {})
        return JSONResponse({"ok": True})

    @app.post("/api/navigator/return_home")
    async def navigator_return_home() -> JSONResponse:
        """Simulate navigator return home action."""
        navigator = app.state.control_state.get("navigator", {})
        navigator_state = {
            "active": navigator.get("active", True),
            "strategy": navigator.get("strategy", "standard"),
            "state": "returning",
        }
        app.state.control_state["navigator"] = navigator_state
        publish_event("navigator.return_home", {})
        return JSONResponse({"ok": True, "state": "returning"})

    @app.get("/api/resource/{resource_name}")
    async def get_resource_status(resource_name: str) -> JSONResponse:
        """Return resource status, preferring Rider-PI data when available."""
        local_resource = app.state.resources.get(resource_name)
        if not local_resource:
            return JSONResponse({"error": f"Resource {resource_name} not found"}, status_code=404)

        adapter: RestAdapter = app.state.rest_adapter
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

    @app.post("/api/resource/{resource_name}")
    async def update_resource(resource_name: str, payload: Dict[str, Any]) -> JSONResponse:
        """Forward resource actions (release/stop) to Rider-PI."""
        local_resource = app.state.resources.get(resource_name)
        if not local_resource:
            return JSONResponse({"error": f"Resource {resource_name} not found"}, status_code=404)
        adapter: RestAdapter = app.state.rest_adapter
        if not adapter:
            action = (payload or {}).get("action")
            if action in {"release", "stop"}:
                local_resource["free"] = True
                local_resource["holders"] = []
                local_resource["checked_at"] = time.time()
                publish_event("resource.update", {"resource": resource_name, "action": action})
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

    @app.get("/svc")
    async def list_services() -> JSONResponse:
        """Return mock systemd service states."""
        services = [{**svc, "ts": time.time()} for svc in app.state.services]
        return JSONResponse({"services": services, "timestamp": time.time()})

    @app.post("/svc/{unit}")
    async def control_service(unit: str, payload: Dict[str, Any]) -> JSONResponse:
        """Handle service control actions."""
        service = next((s for s in app.state.services if s["unit"] == unit), None)
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
        publish_event("service.action", {"unit": unit, "action": action})
        return JSONResponse({"ok": True, "unit": unit, "action": action})

    def _camera_last_headers() -> Dict[str, str]:
        ts = app.state.last_camera_frame["timestamp"]
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return {"Last-Modified": dt.strftime("%a, %d %b %Y %H:%M:%S GMT")}

    @app.get("/camera/last")
    async def camera_last() -> Response:
        """Return last camera frame placeholder."""
        headers = _camera_last_headers()
        return Response(content=app.state.last_camera_frame["content"], media_type="image/png", headers=headers)

    @app.head("/camera/last")
    async def camera_last_head() -> Response:
        """HEAD variant for last camera frame."""
        headers = _camera_last_headers()
        return Response(content=b"", media_type="image/png", headers=headers)

    @app.get("/events")
    async def events(request: Request):
        """Server-sent events endpoint for UI panels."""
        queue: asyncio.Queue = asyncio.Queue()
        app.state.event_subscribers.append(queue)

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
                if queue in app.state.event_subscribers:
                    app.state.event_subscribers.remove(queue)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    class NoCacheStaticFiles(StaticFiles):
        """StaticFiles variant that disables conditional caching."""

        async def __call__(self, scope, receive, send):
            if scope["type"] == "http":
                stripped_headers = [
                    (key, value)
                    for key, value in scope["headers"]
                    if key not in (b"if-none-match", b"if-modified-since")
                ]
                scope = dict(scope)
                scope["headers"] = stripped_headers

            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    headers = MutableHeaders(scope=message)
                    headers["cache-control"] = "no-store"
                await send(message)

            await super().__call__(scope, receive, send_wrapper)

    # Serve static files from web directory
    web_path = Path(__file__).parent.parent.parent / "web"
    if web_path.exists():
        app.mount("/web", NoCacheStaticFiles(directory=str(web_path)), name="web")
        logger.info(f"Serving static files from: {web_path}")

        page_map = {
            "": "view.html",
            "view": "view.html",
            "control": "control.html",
            "navigation": "navigation.html",
            "system": "system.html",
            "home": "home.html",
            "google_home": "google_home.html",
            "chat": "chat.html",
            "providers": "providers.html",
        }

        def make_page_handler(file_path: Path):
            async def handler():
                if file_path.exists():
                    return FileResponse(file_path)
                return JSONResponse({"error": f"{file_path.name} not found"}, status_code=404)

            return handler

        for route_suffix, filename in page_map.items():
            route_path = "/" if route_suffix == "" else f"/{route_suffix}"
            app.get(route_path)(make_page_handler(web_path / filename))

    return app


async def sync_data_periodically(app: FastAPI):
    """
    Background task to periodically sync data from Rider-PI.

    Args:
        app: FastAPI application instance
    """
    adapter: RestAdapter = app.state.rest_adapter
    cache: CacheManager = app.state.cache

    logger.info("Starting periodic data sync...")

    while True:
        try:
            # Fetch data from Rider-PI REST API
            healthz_data = await adapter.get_healthz()
            cache.set("healthz", healthz_data)

            state_data = await adapter.get_state()
            cache.set("state", state_data)

            sysinfo_data = await adapter.get_sysinfo()
            cache.set("sysinfo", sysinfo_data)

            snap_info_data = await adapter.get_vision_snap_info()
            cache.set("vision_snap_info", snap_info_data)

            obstacle_data = await adapter.get_vision_obstacle()
            cache.set("vision_obstacle", obstacle_data)

            metrics_data = await adapter.get_app_metrics()
            cache.set("app_metrics", metrics_data)

            camera_resource_data = await adapter.get_camera_resource()
            cache.set("camera_resource", camera_resource_data)

            bus_health_data = await adapter.get_bus_health()
            cache.set("bus_health", bus_health_data)

            logger.debug("Data sync completed")

            # Cleanup expired cache entries
            cache.cleanup_expired()

        except Exception as e:
            logger.error(f"Error in data sync: {e}")

        # Wait before next sync (2 seconds to match frontend refresh)
        await asyncio.sleep(2)
