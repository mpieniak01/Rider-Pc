"""FastAPI server for replicating Rider-PI UI."""

import logging
import asyncio
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

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
    app = FastAPI(
        title="Rider-PC Client",
        description="PC-side client replicating Rider-PI UI",
        version="0.1.0"
    )
    
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
    
    # Background task for data synchronization
    app.state.sync_task = None
    
    @app.on_event("startup")
    async def startup_event():
        """Initialize connections on startup."""
        logger.info("Starting Rider-PC Client API server...")
        
        # Initialize REST adapter
        app.state.rest_adapter = RestAdapter(settings.rider_pi_base_url)
        logger.info(f"REST adapter initialized for {settings.rider_pi_base_url}")
        
        # Initialize ZMQ subscriber
        app.state.zmq_subscriber = ZmqSubscriber(
            settings.zmq_pub_endpoint,
            topics=["vision.*", "motion.*", "robot.*", "navigator.*"]
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
        """Health check endpoint."""
        data = cache.get("healthz", {"ok": True, "status": "ok"})
        return JSONResponse(content=data)
    
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
        data = cache.get("app_metrics", {
            "ok": True,
            "metrics": {},
            "total_errors": 0
        })
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
    
    # Serve static files from web directory
    web_path = Path(__file__).parent.parent.parent / "web"
    if web_path.exists():
        app.mount("/web", StaticFiles(directory=str(web_path)), name="web")
        logger.info(f"Serving static files from: {web_path}")
        
        # Serve view.html at root
        @app.get("/")
        async def root():
            """Serve view.html at root."""
            view_file = web_path / "view.html"
            if view_file.exists():
                return FileResponse(view_file)
            return JSONResponse({"error": "view.html not found"}, status_code=404)
    
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
