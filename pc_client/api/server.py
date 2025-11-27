"""FastAPI server for replicating Rider-PI UI."""

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import MutableHeaders

from pc_client.config import Settings
from pc_client.cache import CacheManager
from pc_client.core import ServiceManager
from pc_client.api import lifecycle
from pc_client.api.routers import status_router, provider_router, control_router, voice_router, chat_router, project_router, model_router
from pc_client.api.sse_manager import SseManager

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
    app.state.task_queue = None
    app.state.providers: Dict[str, Any] = {}
    app.state.provider_worker = None
    app.state.provider_worker_task = None
    app.state.telemetry_publisher = None
    app.state.vision_offload_enabled = False
    app.state.vision_frame_priority = 1
    app.state.voice_offload_enabled = False
    app.state.voice_asr_priority = 5
    app.state.voice_tts_priority = 6
    app.state.text_provider = None
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
        "media_type": "image/png",
    }
    app.state.sse_manager = SseManager()
    app.state.service_manager = ServiceManager()  # Initialize ServiceManager
    app.state.sync_task = None
    app.state.provider_heartbeat_task = None
    app.state.camera_sync_task = None
    app.state.last_lcd_poweroff_ts = 0.0

    # Register lifecycle events
    @app.on_event("startup")
    async def startup():
        await lifecycle.startup_event(app)

    @app.on_event("shutdown")
    async def shutdown():
        await lifecycle.shutdown_event(app)

    # Include routers
    app.include_router(status_router)
    app.include_router(provider_router)
    app.include_router(control_router)
    app.include_router(voice_router)
    app.include_router(chat_router)
    app.include_router(project_router)
    app.include_router(model_router)

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
            "project": "project.html",
            "models": "models.html",
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
