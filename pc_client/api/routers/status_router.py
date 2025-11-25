"""Status, health, metrics, and information endpoints."""

import logging
import time

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from pc_client.cache import CacheManager
from pc_client.utils.system_info import collect_system_metrics

logger = logging.getLogger(__name__)

router = APIRouter()
PC_SYSINFO_CACHE_KEY = "pc_sysinfo"
PC_SYSINFO_TTL = 5


@router.get("/healthz")
async def healthz(request: Request) -> JSONResponse:
    """Health check endpoint (deprecated, use /health/live)."""
    cache: CacheManager = request.app.state.cache
    data = cache.get("healthz", {"ok": True, "status": "ok"})
    return JSONResponse(content=data)


@router.get("/health/live")
async def health_live() -> JSONResponse:
    """
    Liveness probe endpoint.
    Returns 200 if the application is running and responsive.
    Used by container orchestrators to determine if the app should be restarted.
    """
    return JSONResponse(content={"status": "alive", "timestamp": time.time()})


@router.get("/health/ready")
async def health_ready(request: Request) -> JSONResponse:
    """
    Readiness probe endpoint.
    Returns 200 if the application is ready to serve requests.
    Checks critical components: cache, providers, and queue.
    Used by container orchestrators to determine if traffic should be routed to this instance.
    """
    cache: CacheManager = request.app.state.cache

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
        hasattr(request.app.state, 'rest_adapter')
        and request.app.state.rest_adapter is not None
        and hasattr(request.app.state, 'zmq_subscriber')
        and request.app.state.zmq_subscriber is not None
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


@router.get("/state")
async def state(request: Request) -> JSONResponse:
    """State endpoint."""
    cache: CacheManager = request.app.state.cache
    data = cache.get("state", {"present": False, "mode": "idle"})
    return JSONResponse(content=data)


@router.get("/sysinfo")
async def sysinfo(request: Request) -> JSONResponse:
    """System info endpoint."""
    cache: CacheManager = request.app.state.cache
    data = cache.get("sysinfo", {})
    return JSONResponse(content=data)


@router.get("/vision/snap-info")
async def vision_snap_info(request: Request) -> JSONResponse:
    """Vision snapshot info endpoint."""
    cache: CacheManager = request.app.state.cache
    data = cache.get("vision_snap_info", {})
    return JSONResponse(content=data)


@router.get("/vision/obstacle")
async def vision_obstacle(request: Request) -> JSONResponse:
    """Vision obstacle endpoint."""
    cache: CacheManager = request.app.state.cache
    # Try ZMQ cache first, then REST cache
    data = cache.get("zmq:vision.obstacle", cache.get("vision_obstacle", {}))
    return JSONResponse(content=data)


@router.get("/api/app-metrics")
async def app_metrics(request: Request) -> JSONResponse:
    """App metrics endpoint."""
    cache: CacheManager = request.app.state.cache
    data = cache.get("app_metrics", {"ok": True, "metrics": {}, "total_errors": 0})
    return JSONResponse(content=data)


@router.get("/status/system-pc")
async def system_pc_status(request: Request) -> JSONResponse:
    """Return metrics for the Rider-PC host."""
    cache: CacheManager = request.app.state.cache
    data = cache.get(PC_SYSINFO_CACHE_KEY)
    if not data:
        data = collect_system_metrics()
        cache.set(PC_SYSINFO_CACHE_KEY, data, ttl=PC_SYSINFO_TTL)
    return JSONResponse(content=data or {})


@router.get("/api/resource/camera")
async def camera_resource(request: Request) -> JSONResponse:
    """Camera resource endpoint."""
    cache: CacheManager = request.app.state.cache
    data = cache.get("camera_resource", {})
    return JSONResponse(content=data)


@router.get("/api/bus/health")
async def bus_health(request: Request) -> JSONResponse:
    """Bus health endpoint."""
    cache: CacheManager = request.app.state.cache
    data = cache.get("bus_health", {})
    return JSONResponse(content=data)


@router.get("/camera/placeholder")
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


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint."""
    metrics_data = generate_latest()
    return Response(content=metrics_data, media_type=CONTENT_TYPE_LATEST)
