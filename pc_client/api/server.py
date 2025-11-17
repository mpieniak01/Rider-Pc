"""FastAPI server for replicating Rider-PI UI."""

import asyncio
import contextlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.9 compatibility
    import tomli as tomllib  # type: ignore

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.datastructures import MutableHeaders

from pc_client.config import Settings
from pc_client.cache import CacheManager
from pc_client.adapters import RestAdapter, ZmqSubscriber
from pc_client.queue import TaskQueue
from pc_client.queue.task_queue import TaskQueueWorker
from pc_client.providers import VisionProvider, VoiceProvider, TextProvider
from pc_client.providers.base import TaskEnvelope, TaskType, TaskStatus
from pc_client.telemetry import ZMQTelemetryPublisher

logger = logging.getLogger(__name__)


def _load_provider_config(config_path: str, section: Optional[str] = None) -> Dict[str, Any]:
    """Load optional TOML config for providers."""
    if not config_path:
        return {}

    file_path = Path(config_path)
    if not file_path.exists():
        logger.warning(f"Provider config not found at {config_path}, using defaults")
        return {}

    try:
        with file_path.open("rb") as fp:
            data = tomllib.load(fp)
            if isinstance(data, dict):
                if section:
                    return data.get(section, data) or {}
                return data
    except Exception as exc:  # pragma: no cover - defensive
        logger.error(f"Failed to parse provider config {config_path}: {exc}")
    return {}


def _build_vision_frame_task(payload: Dict[str, Any], priority: int) -> Optional[TaskEnvelope]:
    """Convert a vision.frame.offload payload into a TaskEnvelope."""
    frame_data = payload.get("frame_jpeg") or payload.get("frame_data")
    if not frame_data:
        logger.debug("Skipping vision frame without frame_jpeg/frame_data")
        return None

    frame_id = payload.get("frame_id") or payload.get("rid") or str(uuid.uuid4())
    timestamp = payload.get("timestamp") or payload.get("ts")

    task_payload: Dict[str, Any] = {
        "frame_data": frame_data,
        "frame_id": frame_id,
        "timestamp": timestamp,
        "format": payload.get("format", "jpeg"),
    }

    for key in ("rid", "roi", "meta"):
        if key in payload:
            task_payload[key] = payload[key]

    task_meta = {"source_topic": "vision.frame.offload", "frame_id": frame_id}

    return TaskEnvelope(
        task_id=f"vision-frame-{frame_id}",
        task_type=TaskType.VISION_FRAME,
        payload=task_payload,
        meta=task_meta,
        priority=priority,
    )


def _build_voice_asr_task(payload: Dict[str, Any], priority: int) -> Optional[TaskEnvelope]:
    """Convert voice.asr.request payload into TaskEnvelope."""
    audio_data = payload.get("chunk_pcm") or payload.get("audio_data")
    if not audio_data:
        logger.debug("Skipping voice request without audio data")
        return None

    request_id = payload.get("request_id") or payload.get("seq") or str(uuid.uuid4())
    sample_rate = payload.get("sample_rate")
    lang = payload.get("lang") or payload.get("language")
    format_hint = payload.get("format", "wav")

    task_payload = {
        "audio_data": audio_data,
        "format": format_hint,
        "sample_rate": sample_rate,
        "language": lang,
    }

    task_meta = {
        "source_topic": "voice.asr.request",
        "request_id": request_id,
        "rid": payload.get("rid"),
        "timestamp": payload.get("ts"),
    }

    return TaskEnvelope(
        task_id=f"voice-asr-{request_id}",
        task_type=TaskType.VOICE_ASR,
        payload=task_payload,
        meta=task_meta,
        priority=priority,
    )


def _build_voice_tts_task(payload: Dict[str, Any], priority: int) -> Optional[TaskEnvelope]:
    """Convert voice.tts.request payload into TaskEnvelope."""
    text = payload.get("text")
    if not text:
        logger.debug("Skipping voice TTS request without text")
        return None

    request_id = payload.get("request_id") or payload.get("seq") or str(uuid.uuid4())

    task_payload = {
        "text": text,
        "voice": payload.get("voice"),
        "speed": payload.get("speed"),
    }
    task_meta = {
        "source_topic": "voice.tts.request",
        "request_id": request_id,
        "ts": payload.get("ts"),
    }

    return TaskEnvelope(
        task_id=f"voice-tts-{request_id}",
        task_type=TaskType.VOICE_TTS,
        payload=task_payload,
        meta=task_meta,
        priority=priority,
    )


def _vision_offload_requested(settings: Settings) -> bool:
    """Return True if all toggles required for vision offload are enabled."""
    return settings.enable_providers and settings.enable_task_queue and settings.enable_vision_offload


def _voice_offload_requested(settings: Settings) -> bool:
    """Return True if toggles required for voice offload are enabled."""
    return settings.enable_providers and settings.enable_task_queue and settings.enable_voice_offload


def _text_offload_requested(settings: Settings) -> bool:
    """Return True if toggles required for text offload are enabled."""
    return settings.enable_providers and settings.enable_text_offload


def _get_provider_capabilities(settings: Settings) -> Dict[str, Any]:
    """Build capability payload for Rider-PI handshake."""
    vision_cfg = _load_provider_config(settings.vision_provider_config_path, "vision")
    voice_cfg = _load_provider_config(settings.voice_provider_config_path, "voice")
    text_cfg = _load_provider_config(settings.text_provider_config_path, "text")

    def mode(enabled: bool) -> str:
        return "pc" if enabled else "local"

    return {
        "vision": {
            "version": vision_cfg.get("schema_version", "1.0.0"),
            "features": ["frame_offload", "obstacle_enhanced"],
            "frame_schema": vision_cfg.get("frame_schema", "vision.frame.v1"),
            "model": vision_cfg.get("detection_model", settings.vision_model),
            "priority": {"frame": int(vision_cfg.get("frame_priority", 1))},
            "mode": mode(settings.enable_vision_offload),
        },
        "voice": {
            "version": voice_cfg.get("schema_version", "1.0.0"),
            "features": ["asr", "tts"],
            "asr_model": voice_cfg.get("asr_model", settings.voice_model),
            "tts_model": voice_cfg.get("tts_model", voice_cfg.get("voice", "piper")),
            "sample_rate": voice_cfg.get("sample_rate", 16000),
            "mode": mode(settings.enable_voice_offload),
        },
        "text": {
            "version": text_cfg.get("schema_version", "1.0.0"),
            "features": ["chat", "nlu"],
            "model": text_cfg.get("model", settings.text_model),
            "nlu_tasks": text_cfg.get("nlu_tasks", []),
            "mode": mode(settings.enable_text_offload),
        },
    }


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
    app.state.task_queue: Optional[TaskQueue] = None
    app.state.providers: Dict[str, Any] = {}
    app.state.provider_worker: Optional[TaskQueueWorker] = None
    app.state.provider_worker_task: Optional[asyncio.Task] = None
    app.state.telemetry_publisher: Optional[ZMQTelemetryPublisher] = None
    app.state.vision_offload_enabled = False
    app.state.vision_frame_priority = 1
    app.state.voice_offload_enabled = False
    app.state.voice_asr_priority = 5
    app.state.voice_tts_priority = 6
    app.state.text_provider: Optional[TextProvider] = None
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

    provider_domains = ("voice", "text", "vision")

    def default_provider_state() -> Dict[str, Any]:
        return {
            "domains": {
                domain: {"mode": "local", "status": "local_only", "changed_ts": None} for domain in provider_domains
            },
            "pc_health": {"reachable": False, "status": "unknown"},
        }

    def default_provider_health() -> Dict[str, Any]:
        return {
            domain: {
                "status": "unknown",
                "latency_ms": 0.0,
                "success_rate": 1.0,
                "last_check": None,
            }
            for domain in provider_domains
        }

    def default_ai_mode() -> Dict[str, Any]:
        return {"mode": "local", "changed_ts": None}

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

    def _normalize_tracking_request(payload: Dict[str, Any]) -> Tuple[str, bool]:
        """Validate and normalize tracking payload similar to Rider-PI."""
        raw_mode = str(payload.get("mode", "none")).strip().lower()
        if raw_mode not in {"face", "hand", "none"}:
            raise HTTPException(status_code=400, detail=f"Invalid tracking mode '{raw_mode}'")
        enabled = bool(payload.get("enabled", raw_mode in {"face", "hand"}))
        if not enabled:
            raw_mode = "none"
        return raw_mode, raw_mode != "none"

    def _set_local_tracking_state(mode: str, enabled: bool) -> Dict[str, Any]:
        """Update local tracking state cache + emit SSE."""
        state = {"mode": mode, "enabled": enabled}
        app.state.control_state["tracking"] = state
        publish_event("motion.bridge.event", {"event": "tracking_mode", "detail": state})
        return {"ok": True, **state}

    async def start_provider_heartbeat():
        base_url = (settings.pc_public_base_url or "").strip()
        if not base_url:
            logger.info("PC_PUBLIC_BASE_URL not set; skipping provider heartbeat loop")
            return
        capabilities = _get_provider_capabilities(settings)
        normalized = base_url.rstrip("/")

        async def _heartbeat_loop():
            while True:
                adapter: Optional[RestAdapter] = app.state.rest_adapter
                if not adapter:
                    await asyncio.sleep(5)
                    continue
                payload = {
                    "base_url": normalized,
                    "capabilities": capabilities,
                    "timestamp": time.time(),
                }
                try:
                    result = await adapter.post_pc_heartbeat(payload)
                    if isinstance(result, dict) and result.get("error"):
                        logger.warning("Provider heartbeat rejected: %s", result["error"])
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("Provider heartbeat failed: %s", exc)
                await asyncio.sleep(5)

        if app.state.provider_heartbeat_task:
            app.state.provider_heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await app.state.provider_heartbeat_task
        app.state.provider_heartbeat_task = asyncio.create_task(_heartbeat_loop())

    # Background tasks for data sync + provider heartbeat
    app.state.sync_task = None
    app.state.provider_heartbeat_task = None

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

        # Initialize provider pipelines
        await _initialize_vision_pipeline(app)
        await _initialize_voice_pipeline(app)
        await _initialize_text_provider(app)

        # Initialize ZMQ subscriber
        app.state.zmq_subscriber = ZmqSubscriber(
            settings.zmq_pub_endpoint, topics=["vision.*", "voice.*", "motion.*", "robot.*", "navigator.*"]
        )

        # Register ZMQ handlers to update cache
        def cache_handler(topic: str, data: Dict[str, Any]):
            """Handler to cache ZMQ messages."""
            cache.set(f"zmq:{topic}", data)
            logger.debug(f"Cached ZMQ message for topic: {topic}")

        async def vision_frame_handler(topic: str, data: Dict[str, Any]):
            """Convert Rider-PI vision frames into queue tasks."""
            if not app.state.vision_offload_enabled or not app.state.task_queue:
                return

            task = _build_vision_frame_task(data, app.state.vision_frame_priority)
            if task is None:
                return

            enqueued = await app.state.task_queue.enqueue(task)
            if not enqueued:
                logger.warning("Vision task queue is full – dropped frame %s", task.task_id)

        async def voice_asr_handler(topic: str, data: Dict[str, Any]):
            """Enqueue ASR requests coming from Rider-PI."""
            if not app.state.voice_offload_enabled or not app.state.task_queue:
                return

            task = _build_voice_asr_task(data, app.state.voice_asr_priority)
            if task is None:
                return

            enqueued = await app.state.task_queue.enqueue(task)
            if not enqueued:
                logger.warning("Voice ASR queue full – dropped request %s", task.task_id)

        async def voice_tts_handler(topic: str, data: Dict[str, Any]):
            """Enqueue TTS requests coming from Rider-PI."""
            if not app.state.voice_offload_enabled or not app.state.task_queue:
                return

            task = _build_voice_tts_task(data, app.state.voice_tts_priority)
            if task is None:
                return

            enqueued = await app.state.task_queue.enqueue(task)
            if not enqueued:
                logger.warning("Voice TTS queue full – dropped request %s", task.task_id)

        for topic in ["vision.*", "voice.*", "motion.*", "robot.*", "navigator.*"]:
            app.state.zmq_subscriber.subscribe_topic(topic, cache_handler)

        if app.state.vision_offload_enabled:
            app.state.zmq_subscriber.subscribe_topic("vision.frame.offload", vision_frame_handler)

        if app.state.voice_offload_enabled:
            app.state.zmq_subscriber.subscribe_topic("voice.asr.request", voice_asr_handler)
            app.state.zmq_subscriber.subscribe_topic("voice.tts.request", voice_tts_handler)

        # Start ZMQ subscriber in background
        asyncio.create_task(app.state.zmq_subscriber.start())
        logger.info("ZMQ subscriber started")

        await start_provider_heartbeat()

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
        if app.state.provider_heartbeat_task:
            app.state.provider_heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await app.state.provider_heartbeat_task

        # Stop task queue worker / providers
        if app.state.provider_worker:
            await app.state.provider_worker.stop()

        if app.state.provider_worker_task:
            try:
                await app.state.provider_worker_task
            except asyncio.CancelledError:
                pass

        if app.state.telemetry_publisher:
            app.state.telemetry_publisher.close()

        for provider in app.state.providers.values():
            try:
                await provider.shutdown()
            except Exception as exc:
                logger.warning(f"Failed to shutdown provider {provider}: {exc}")

        if app.state.text_provider:
            try:
                await app.state.text_provider.shutdown()
            except Exception as exc:
                logger.warning(f"Failed to shutdown TextProvider: {exc}")

        # Stop ZMQ subscriber
        if app.state.zmq_subscriber:
            await app.state.zmq_subscriber.stop()

        # Close REST adapter
        if app.state.rest_adapter:
            await app.state.rest_adapter.close()

        logger.info("Shutdown complete")

    # API Endpoints
    @app.get("/providers/capabilities")
    async def providers_capabilities() -> JSONResponse:
        """Expose provider capabilities for Rider-PI handshake."""
        return JSONResponse(content=_get_provider_capabilities(settings))

    @app.get("/api/providers/capabilities")
    async def providers_capabilities_api() -> JSONResponse:
        """API-prefixed alias."""
        return await providers_capabilities()

    @app.post("/providers/text/generate")
    async def providers_text_generate(payload: Dict[str, Any]) -> JSONResponse:
        """Generate text via TextProvider (chat/NLU)."""
        provider: Optional[TextProvider] = app.state.text_provider
        if provider is None:
            raise HTTPException(status_code=503, detail="Text provider not initialized")

        prompt = (payload or {}).get("prompt")
        if not prompt:
            raise HTTPException(status_code=400, detail="Missing 'prompt' in payload")

        task = TaskEnvelope(
            task_id=f"text-generate-{uuid.uuid4()}",
            task_type=TaskType.TEXT_GENERATE,
            payload={
                "prompt": prompt,
                "max_tokens": payload.get("max_tokens"),
                "temperature": payload.get("temperature"),
                "system_prompt": payload.get("system_prompt"),
            },
            meta={"mode": payload.get("mode", "chat"), "context": payload.get("context")},
        )

        result = await provider.process_task(task)
        if result.status != TaskStatus.COMPLETED:
            raise HTTPException(status_code=502, detail=result.error or "Text generation failed")

        response_body = {
            "task_id": result.task_id,
            "text": (result.result or {}).get("text"),
            "meta": result.meta,
            "from_cache": (result.result or {}).get("from_cache", False),
            "tokens_used": (result.result or {}).get("tokens_used"),
        }
        return JSONResponse(content=response_body)

    @app.post("/api/providers/text/generate")
    async def providers_text_generate_api(payload: Dict[str, Any]) -> JSONResponse:
        return await providers_text_generate(payload)

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

    # AI mode & Provider Control Endpoints

    @app.get("/api/system/ai-mode")
    async def get_ai_mode_route() -> JSONResponse:
        """Fetch AI mode from Rider-PI or cache."""
        adapter: Optional[RestAdapter] = app.state.rest_adapter
        cached = cache.get("ai_mode", default_ai_mode())
        if adapter:
            try:
                data = await adapter.get_ai_mode()
                if isinstance(data, dict) and data:
                    cache.set("ai_mode", data)
                    return JSONResponse(content=data)
            except Exception as exc:
                logger.error("Failed to fetch AI mode from Rider-PI: %s", exc)
        if cached:
            return JSONResponse(content=cached)
        raise HTTPException(status_code=502, detail="Unable to fetch AI mode")

    async def _set_ai_mode(payload: Dict[str, Any]) -> JSONResponse:
        mode = str(payload.get("mode") or "").lower()
        if mode not in {"local", "pc_offload"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid mode. Must be 'local' or 'pc_offload'"},
            )
        adapter: Optional[RestAdapter] = app.state.rest_adapter
        if not adapter:
            return JSONResponse(
                status_code=503,
                content={"error": "REST adapter not initialized"},
            )
        result = await adapter.set_ai_mode(mode)
        if isinstance(result, dict) and "error" not in result:
            cache.set("ai_mode", result)
            return JSONResponse(content=result)
        logger.error("Failed to set AI mode via Rider-PI: %s", result)
        return JSONResponse(content=result or {"error": "Failed to set mode"}, status_code=502)

    @app.put("/api/system/ai-mode")
    async def put_ai_mode_route(payload: Dict[str, Any]) -> JSONResponse:
        return await _set_ai_mode(payload)

    @app.post("/api/system/ai-mode")
    async def post_ai_mode_route(payload: Dict[str, Any]) -> JSONResponse:
        return await _set_ai_mode(payload)

    @app.get("/api/providers/state")
    async def providers_state() -> JSONResponse:
        """Fetch provider state information."""
        adapter: Optional[RestAdapter] = app.state.rest_adapter
        cached = cache.get("providers_state", default_provider_state())
        if adapter:
            try:
                data = await adapter.get_providers_state()
                if isinstance(data, dict) and data:
                    cache.set("providers_state", data)
                    return JSONResponse(content=data)
            except Exception as exc:
                logger.error("Failed to fetch provider state from Rider-PI: %s", exc)
        if cached:
            return JSONResponse(content=cached)
        raise HTTPException(status_code=502, detail="Unable to fetch provider state")

    @app.patch("/api/providers/{domain}")
    async def update_provider(domain: str, payload: Dict[str, Any]) -> JSONResponse:
        """Update provider configuration for a specific domain."""
        domain = (domain or "").lower()
        valid_domains = {"voice", "text", "vision"}
        if domain not in valid_domains:
            return JSONResponse(
                status_code=400,
                content={"error": f"Invalid domain. Must be one of {sorted(valid_domains)}"},
            )
        target = str(payload.get("target") or "").lower()
        if target not in {"local", "pc"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid target. Must be 'local' or 'pc'."},
            )
        adapter: Optional[RestAdapter] = app.state.rest_adapter
        if adapter:
            forwarded_payload = {"target": target}
            if "force" in payload:
                forwarded_payload["force"] = bool(payload.get("force"))
            result = await adapter.patch_provider(domain, forwarded_payload)
            if isinstance(result, dict) and "error" not in result:
                cached_state = cache.get("providers_state", default_provider_state())
                domains = cached_state.get("domains") if isinstance(cached_state, dict) else None
                if isinstance(domains, dict) and domain in domains:
                    domains[domain]["mode"] = target
                    domains[domain]["status"] = "pc_active" if target == "pc" else "local_only"
                    domains[domain]["changed_ts"] = time.time()
                    cache.set("providers_state", cached_state)
                return JSONResponse(content=result)
            logger.error("Failed to patch provider via Rider-PI: %s", result)
            return JSONResponse(content=result or {"error": "Failed to update provider"}, status_code=502)

        cached_state = cache.get("providers_state", default_provider_state())
        domains = cached_state.setdefault("domains", {})
        domain_entry = domains.get(domain, {"mode": "local", "status": "local_only", "changed_ts": None})
        domain_entry["mode"] = target
        domain_entry["status"] = "pc_active" if target == "pc" else "local_only"
        domain_entry["changed_ts"] = time.time()
        domains[domain] = domain_entry
        cache.set("providers_state", cached_state)
        return JSONResponse(
            content={"success": True, "domain": domain, "new_state": domain_entry},
            status_code=200,
        )

    @app.get("/api/providers/health")
    async def providers_health() -> JSONResponse:
        """Fetch provider health metrics."""
        adapter: Optional[RestAdapter] = app.state.rest_adapter
        cached = cache.get("providers_health", default_provider_health())
        if adapter:
            try:
                data = await adapter.get_providers_health()
                if isinstance(data, dict) and data:
                    cache.set("providers_health", data)
                    return JSONResponse(content=data)
            except Exception as exc:
                logger.error("Failed to fetch provider health from Rider-PI: %s", exc)
        if cached:
            return JSONResponse(content=cached)
        raise HTTPException(status_code=502, detail="Unable to fetch provider health")

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

    @app.get("/api/motion/queue")
    async def api_motion_queue() -> JSONResponse:
        """Expose the latest motion queue entries collected during control calls."""
        now = time.time()
        items: List[Dict[str, Any]] = []
        for entry in reversed(app.state.motion_queue or []):
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

    @app.get("/api/control/state")
    async def api_control_state() -> JSONResponse:
        """Return current control state, preferring Rider-PI data."""
        adapter: Optional[RestAdapter] = app.state.rest_adapter
        state = dict(app.state.control_state)
        if adapter:
            try:
                remote_state = await adapter.get_control_state()
                if isinstance(remote_state, dict) and "error" not in remote_state:
                    state = remote_state
                    app.state.control_state.update(remote_state)
                else:
                    logger.warning("Falling back to local control state: %s", remote_state.get("error"))
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("Failed to fetch control state from Rider-PI: %s", exc)
        state["updated_at"] = time.time()
        return JSONResponse(content=state)

    @app.post("/api/vision/tracking/mode")
    async def update_tracking_mode(payload: Dict[str, Any]) -> JSONResponse:
        """Update tracking mode state, forwarding to Rider-PI when possible."""
        adapter: Optional[RestAdapter] = app.state.rest_adapter
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
                _set_local_tracking_state(mode, enabled)
            return JSONResponse(result, status_code=status_code)

        mode, enabled = _normalize_tracking_request(body)
        result = _set_local_tracking_state(mode, enabled)
        return JSONResponse(result)

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
        """Return systemd service states (proxy Rider-PI when possible)."""
        adapter: Optional[RestAdapter] = app.state.rest_adapter
        if adapter:
            remote = await adapter.get_services()
            if remote and not remote.get("error"):
                return JSONResponse(remote)
            logger.warning("Falling back to local /svc list: %s", remote.get("error") if remote else "unknown error")

        services = [{**svc, "ts": time.time()} for svc in app.state.services]
        return JSONResponse({"services": services, "timestamp": time.time()})

    @app.post("/svc/{unit}")
    async def control_service(unit: str, payload: Dict[str, Any]) -> JSONResponse:
        """Handle service control actions (proxy Rider-PI when possible)."""
        adapter: Optional[RestAdapter] = app.state.rest_adapter
        if adapter:
            result = await adapter.service_action(unit, payload or {})
            status_code = 200
            if not result.get("ok", True) or result.get("error"):
                status_code = 502
            return JSONResponse(result, status_code=status_code)

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
            "mode": "mode.html",
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


async def _ensure_task_queue(app: FastAPI) -> None:
    """Ensure task queue + worker exist when at least one provider is enabled."""
    settings: Settings = app.state.settings

    if app.state.task_queue:
        return

    queue = TaskQueue(max_size=settings.task_queue_max_size)

    telemetry_endpoint = None
    if settings.enable_telemetry or settings.enable_vision_offload or settings.enable_voice_offload:
        telemetry_endpoint = settings.telemetry_zmq_endpoint

    telemetry_publisher = (
        ZMQTelemetryPublisher(telemetry_endpoint) if telemetry_endpoint else ZMQTelemetryPublisher(None)
    )
    worker = TaskQueueWorker(queue, app.state.providers, telemetry_publisher=telemetry_publisher)
    worker_task = asyncio.create_task(worker.start())

    app.state.task_queue = queue
    app.state.provider_worker = worker
    app.state.provider_worker_task = worker_task
    app.state.telemetry_publisher = telemetry_publisher

    logger.info("Task queue initialized (max_size=%s)", settings.task_queue_max_size)


async def _initialize_vision_pipeline(app: FastAPI) -> None:
    """Create TaskQueue/Provider worker for vision frame offload if enabled."""
    settings: Settings = app.state.settings

    if not _vision_offload_requested(settings):
        logger.info(
            "Vision offload disabled (ENABLE_PROVIDERS=%s, ENABLE_TASK_QUEUE=%s, ENABLE_VISION_OFFLOAD=%s)",
            settings.enable_providers,
            settings.enable_task_queue,
            settings.enable_vision_offload,
        )
        return

    await _ensure_task_queue(app)

    vision_config = _load_provider_config(settings.vision_provider_config_path, "vision")
    if settings.vision_model == "mock":
        vision_config.setdefault("use_mock", True)

    provider = VisionProvider(vision_config)

    try:
        await provider.initialize()
    except Exception as exc:  # pragma: no cover - defensive log
        logger.error(f"Failed to initialize VisionProvider: {exc}")
        await provider.shutdown()
        return

    app.state.providers["vision"] = provider
    app.state.vision_offload_enabled = True
    app.state.vision_frame_priority = int(vision_config.get("frame_priority") or 1)

    logger.info(
        "Vision offload enabled (queue size=%s, frame priority=%s)",
        settings.task_queue_max_size,
        app.state.vision_frame_priority,
    )


async def _initialize_voice_pipeline(app: FastAPI) -> None:
    """Enable TaskQueue + VoiceProvider for ASR/TTS offload."""
    settings: Settings = app.state.settings

    if not _voice_offload_requested(settings):
        logger.info(
            "Voice offload disabled (ENABLE_PROVIDERS=%s, ENABLE_TASK_QUEUE=%s, ENABLE_VOICE_OFFLOAD=%s)",
            settings.enable_providers,
            settings.enable_task_queue,
            settings.enable_voice_offload,
        )
        return

    await _ensure_task_queue(app)

    voice_config = _load_provider_config(settings.voice_provider_config_path, "voice")
    if settings.voice_model == "mock":
        voice_config.setdefault("use_mock", True)

    provider = VoiceProvider(voice_config)

    try:
        await provider.initialize()
    except Exception as exc:  # pragma: no cover
        logger.error(f"Failed to initialize VoiceProvider: {exc}")
        await provider.shutdown()
        return

    app.state.providers["voice"] = provider
    app.state.voice_offload_enabled = True
    app.state.voice_asr_priority = int(voice_config.get("asr_priority") or voice_config.get("priority") or 5)
    app.state.voice_tts_priority = int(voice_config.get("tts_priority") or (app.state.voice_asr_priority + 1))

    logger.info(
        "Voice offload enabled (ASR priority=%s, TTS priority=%s)",
        app.state.voice_asr_priority,
        app.state.voice_tts_priority,
    )


async def _initialize_text_provider(app: FastAPI) -> None:
    """Initialize TextProvider for chat/NLU offload."""
    settings: Settings = app.state.settings

    if not _text_offload_requested(settings):
        logger.info(
            "Text offload disabled (ENABLE_PROVIDERS=%s, ENABLE_TEXT_OFFLOAD=%s)",
            settings.enable_providers,
            settings.enable_text_offload,
        )
        return

    text_config = _load_provider_config(settings.text_provider_config_path, "text")
    if settings.text_model == "mock":
        text_config.setdefault("use_mock", True)

    provider = TextProvider(text_config)

    try:
        await provider.initialize()
    except Exception as exc:  # pragma: no cover
        logger.error(f"Failed to initialize TextProvider: {exc}")
        await provider.shutdown()
        return

    app.state.text_provider = provider
    logger.info("Text offload enabled (model=%s)", text_config.get("model", settings.text_model))


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
