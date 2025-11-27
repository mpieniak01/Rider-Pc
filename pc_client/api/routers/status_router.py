"""Status, health, metrics, and information endpoints."""

import asyncio
import logging
import time
from typing import Optional

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from pc_client.cache import CacheManager
from pc_client.utils.system_info import collect_system_metrics
from pc_client.utils.network import get_local_ip, check_connectivity
from pc_client.adapters.git_adapter import GitAdapter

logger = logging.getLogger(__name__)

router = APIRouter()
PC_SYSINFO_CACHE_KEY = "pc_sysinfo"
PC_SYSINFO_TTL = 5

# Git adapter singleton for version info (caching handled internally)
_git_adapter: Optional[GitAdapter] = None


def get_git_adapter() -> GitAdapter:
    """Get or create the git adapter singleton."""
    global _git_adapter
    if _git_adapter is None:
        _git_adapter = GitAdapter()
    return _git_adapter


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
    settings = getattr(request.app.state, "settings", None)
    host_hint = getattr(settings, "rider_pi_host", None)
    if host_hint and isinstance(data, dict) and not data.get("host"):
        data = dict(data)
        data["host"] = host_hint
    port_hint = getattr(settings, "rider_pi_port", None)
    if port_hint and isinstance(data, dict) and not data.get("port"):
        data["port"] = port_hint
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

    def needs_refresh(payload):
        if not payload or not isinstance(payload, dict):
            return True
        essential_keys = ("platform", "cpu_pct", "distribution", "os_release")
        return any(key not in payload for key in essential_keys)

    if needs_refresh(data):
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


@router.get("/api/status/version")
async def version_info() -> JSONResponse:
    """
    Get git version information for the running Rider-PC application.

    Returns JSON containing:
    - branch: Current git branch name (e.g., 'main')
    - commit: Short commit hash (e.g., 'a1b2c3d')
    - dirty: Boolean indicating if there are uncommitted changes
    - message: Last commit message
    - ts: Unix timestamp when the info was retrieved
    - available: Boolean indicating if git info is available
    """
    git_adapter = get_git_adapter()
    data = await git_adapter.get_version_info()
    return JSONResponse(content=data)


@router.get("/api/status/network")
async def network_status(request: Request) -> JSONResponse:
    """
    Get network connectivity status for Rider-PC.

    Checks connectivity to:
    - Rider-Pi (robot controller)
    - Internet (via 8.8.8.8)

    Returns JSON containing:
    - local_ip: Local IP address of the PC
    - rider_pi: Connection status to Rider-Pi with latency
    - internet: Connection status to internet with latency
    - timestamp: Unix timestamp when the check was performed
    """
    settings = getattr(request.app.state, "settings", None)
    rider_pi_host = getattr(settings, "rider_pi_host", "localhost") if settings else "localhost"

    # Run connectivity checks in parallel for faster response
    local_ip = get_local_ip()
    rider_pi_check, internet_check = await asyncio.gather(
        check_connectivity(rider_pi_host),
        check_connectivity("8.8.8.8"),
    )

    # Build response structure matching the issue specification
    response = {
        "local_ip": local_ip,
        "rider_pi": {
            "host": rider_pi_host,
            "status": rider_pi_check.get("status", "offline"),
        },
        "internet": {
            "host": "8.8.8.8",
            "status": internet_check.get("status", "offline"),
        },
        "timestamp": int(time.time()),
    }

    # Add latency if available
    if "latency_ms" in rider_pi_check:
        response["rider_pi"]["latency"] = int(rider_pi_check["latency_ms"])
    if "latency_ms" in internet_check:
        response["internet"]["latency"] = int(internet_check["latency_ms"])

    return JSONResponse(content=response)
