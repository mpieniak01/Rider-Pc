"""FastAPI server for replicating Rider-PI UI."""

import logging
import asyncio
import time
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

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
        return JSONResponse(content={
            "status": "alive",
            "timestamp": time.time()
        })
    
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
            hasattr(app.state, 'rest_adapter') and app.state.rest_adapter is not None and
            hasattr(app.state, 'zmq_subscriber') and app.state.zmq_subscriber is not None
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
                    "cache": {
                        "status": "healthy" if cache_healthy else "unhealthy",
                        "error": cache_error
                    },
                    "adapters": "ready" if adapters_ready else "not_ready"
                }
            }
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
    
    @app.get("/metrics")
    async def metrics() -> Response:
        """Prometheus metrics endpoint."""
        metrics_data = generate_latest()
        return Response(content=metrics_data, media_type=CONTENT_TYPE_LATEST)
    
    # Provider Control Endpoints
    
    @app.get("/api/providers/state")
    async def providers_state() -> JSONResponse:
        """
        Get current state of all AI providers.
        Mock implementation for Phase 3.
        """
        providers_data = cache.get("providers_state", {
            "voice": {
                "current": "local",
                "status": "online",
                "last_health_check": "2025-11-12T14:00:00Z"
            },
            "text": {
                "current": "local",
                "status": "online",
                "last_health_check": "2025-11-12T14:00:00Z"
            },
            "vision": {
                "current": "local",
                "status": "online",
                "last_health_check": "2025-11-12T14:00:00Z"
            }
        })
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
            return JSONResponse(
                status_code=400,
                content={"error": f"Invalid domain. Must be one of {valid_domains}"}
            )
        
        # Get current state
        providers_state = cache.get("providers_state", {
            "voice": {"current": "local", "status": "online"},
            "text": {"current": "local", "status": "online"},
            "vision": {"current": "local", "status": "online"}
        })
        
        # Update the provider
        # In real implementation, this would send command to Rider-PI
        if domain in providers_state:
            providers_state[domain]["current"] = "pc"  # Mock switching to PC
            providers_state[domain]["status"] = "online"
            cache.set("providers_state", providers_state)
            
            logger.info(f"Provider {domain} switched to PC (mock)")
            
            return JSONResponse(content={
                "success": True,
                "domain": domain,
                "new_state": providers_state[domain]
            })
        
        return JSONResponse(
            status_code=404,
            content={"error": f"Provider {domain} not found"}
        )
    
    @app.get("/api/providers/health")
    async def providers_health() -> JSONResponse:
        """
        Get health status of all providers.
        Mock implementation for Phase 3.
        """
        health_data = cache.get("providers_health", {
            "voice": {
                "status": "healthy",
                "latency_ms": 45.2,
                "success_rate": 0.98,
                "last_check": "2025-11-12T14:00:00Z"
            },
            "text": {
                "status": "healthy",
                "latency_ms": 120.5,
                "success_rate": 0.95,
                "last_check": "2025-11-12T14:00:00Z"
            },
            "vision": {
                "status": "healthy",
                "latency_ms": 85.3,
                "success_rate": 0.99,
                "last_check": "2025-11-12T14:00:00Z"
            }
        })
        return JSONResponse(content=health_data)
    
    @app.get("/api/services/graph")
    async def services_graph() -> JSONResponse:
        """
        Get system services graph for system dashboard.
        Mock implementation for Phase 3.
        """
        import time
        
        graph_data = cache.get("services_graph", {
            "generated_at": time.time(),
            "nodes": [
                {
                    "label": "FastAPI Server",
                    "unit": "pc_client.service",
                    "status": "active",
                    "group": "api",
                    "since": "2025-11-12 14:00:00",
                    "description": "Main REST API server",
                    "edges_out": ["cache", "zmq"]
                },
                {
                    "label": "Cache Manager",
                    "unit": "cache.service",
                    "status": "active",
                    "group": "data",
                    "since": "2025-11-12 14:00:00",
                    "description": "SQLite cache for data buffering",
                    "edges_out": []
                },
                {
                    "label": "ZMQ Subscriber",
                    "unit": "zmq.service",
                    "status": "active",
                    "group": "messaging",
                    "since": "2025-11-12 14:00:00",
                    "description": "Real-time data stream subscriber",
                    "edges_out": ["cache"]
                },
                {
                    "label": "Voice Provider",
                    "unit": "voice.provider",
                    "status": "active",
                    "group": "providers",
                    "since": "2025-11-12 14:00:00",
                    "description": "ASR/TTS processing",
                    "edges_out": ["task_queue"]
                },
                {
                    "label": "Vision Provider",
                    "unit": "vision.provider",
                    "status": "active",
                    "group": "providers",
                    "since": "2025-11-12 14:00:00",
                    "description": "Object detection and frame processing",
                    "edges_out": ["task_queue"]
                },
                {
                    "label": "Text Provider",
                    "unit": "text.provider",
                    "status": "active",
                    "group": "providers",
                    "since": "2025-11-12 14:00:00",
                    "description": "LLM text generation and NLU",
                    "edges_out": ["task_queue", "cache"]
                },
                {
                    "label": "Task Queue",
                    "unit": "task_queue.service",
                    "status": "active",
                    "group": "queue",
                    "since": "2025-11-12 14:00:00",
                    "description": "Redis-based task queue",
                    "edges_out": []
                },
                {
                    "label": "Telemetry Publisher",
                    "unit": "telemetry.service",
                    "status": "active",
                    "group": "monitoring",
                    "since": "2025-11-12 14:00:00",
                    "description": "ZMQ telemetry and Prometheus metrics",
                    "edges_out": []
                }
            ],
            "edges": []
        })
        return JSONResponse(content=graph_data)
    
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
