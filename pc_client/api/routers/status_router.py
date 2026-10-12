"""Status, health, metrics, and information endpoints."""

import asyncio
import logging
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from pc_client.cache import CacheManager
from pc_client.utils.system_info import collect_system_metrics
from pc_client.utils.network import get_local_ip, check_connectivity
from pc_client.adapters.git_adapter import GitAdapter
from pc_client.config.settings import Settings
from urllib.parse import urlparse
from pc_client.api.background_sync import camera_on
from pc_client.api.telemetry_snapshot import adapter_source, cached_snapshot, latest_observation, refresh_snapshot

logger = logging.getLogger(__name__)

router = APIRouter()
PC_SYSINFO_CACHE_KEY = "pc_sysinfo"
PC_SYSINFO_TTL = 5
INTERNET_PROBE_HOST = "8.8.8.8"

# Git adapter singleton for version info (caching handled internally)
_git_adapter: Optional[GitAdapter] = None


def get_git_adapter() -> GitAdapter:
    """Get or create the git adapter singleton."""
    global _git_adapter
    if _git_adapter is None:
        _git_adapter = GitAdapter()
    return _git_adapter


def _get_settings(request: Request) -> Settings:
    """Safely obtain Settings instance from the app state."""
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        settings = Settings()
    return settings


def _extract_public_host(settings: Settings) -> Optional[str]:
    url = settings.pc_public_base_url
    if not url:
        return None
    try:
        parsed = urlparse(url if "://" in url else f"http://{url}")
        return parsed.hostname
    except ValueError:
        return None


@router.get("/healthz")
async def healthz(request: Request) -> JSONResponse:
    """Health check endpoint (deprecated, use /health/live)."""
    cache: CacheManager = request.app.state.cache
    data = cached_snapshot(cache, "healthz", source=adapter_source(getattr(request.app.state, "rest_adapter", None)))
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
    adapter = getattr(request.app.state, "rest_adapter", None)
    if adapter is None:
        data = cached_snapshot(cache, "state", source=adapter_source(adapter))
    else:
        data = await refresh_snapshot(request.app, "state", adapter.get_state, reuse_s=0.5)
        if not data.get("error") and not data.get("offline"):
            tracking = data.get("tracking")
            if isinstance(tracking, dict):
                getattr(request.app.state, "control_state", {})["tracking"] = tracking
    return JSONResponse(content=data)


@router.get("/sysinfo")
async def sysinfo(request: Request) -> JSONResponse:
    """System info endpoint."""
    cache: CacheManager = request.app.state.cache
    data = cached_snapshot(cache, "sysinfo", source=adapter_source(getattr(request.app.state, "rest_adapter", None)))
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
    adapter = getattr(request.app.state, "rest_adapter", None)
    data = (
        await refresh_snapshot(
            request.app,
            "vision_snap_info",
            adapter.get_vision_snap_info,
            reuse_s=1.0 if camera_on(request.app) else 5.0,
        )
        if adapter is not None
        else cached_snapshot(cache, "vision_snap_info", source=adapter_source(adapter))
    )
    return JSONResponse(content=data)


@router.get("/vision/obstacle")
async def vision_obstacle(request: Request) -> JSONResponse:
    """Vision obstacle endpoint."""
    cache: CacheManager = request.app.state.cache
    data = latest_observation(
        cache.get("zmq:vision.obstacle"),
        cache.get("vision_obstacle"),
        source=adapter_source(getattr(request.app.state, "rest_adapter", None)),
    )
    return JSONResponse(content=data)


@router.get("/api/app-metrics")
async def app_metrics(request: Request) -> JSONResponse:
    """App metrics endpoint."""
    cache: CacheManager = request.app.state.cache
    data = cached_snapshot(
        cache, "app_metrics", source=adapter_source(getattr(request.app.state, "rest_adapter", None))
    )
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
    """Jeden kontrakt zasobu kamery, także przy utracie Pi."""
    from pc_client.api.routers.control_router import get_resource_status

    return await get_resource_status(request, "camera")


@router.get("/api/bus/health")
async def bus_health(request: Request) -> JSONResponse:
    """Bus health endpoint."""
    cache: CacheManager = request.app.state.cache
    data = cached_snapshot(cache, "bus_health", source=adapter_source(getattr(request.app.state, "rest_adapter", None)))
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


@router.get("/api/config/network")
async def network_config(request: Request) -> JSONResponse:
    """Return static network configuration derived from application settings."""
    settings = _get_settings(request)
    public_host = _extract_public_host(settings)
    return JSONResponse(
        content={
            "rider_pi_host": settings.rider_pi_host,
            "rider_pi_port": settings.rider_pi_port,
            "internet_probe_host": INTERNET_PROBE_HOST,
            "pc_host": public_host,
        }
    )


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
    settings = _get_settings(request)
    rider_pi_host = settings.rider_pi_host

    # Run connectivity checks in parallel for faster response
    local_ip = get_local_ip()
    rider_pi_check: Dict[str, Any]
    internet_check: Dict[str, Any]
    rider_pi_check, internet_check = await asyncio.gather(
        check_connectivity(rider_pi_host),
        check_connectivity(INTERNET_PROBE_HOST),
    )

    # Build response structure matching the issue specification
    response: Dict[str, Any] = {
        "local_ip": local_ip,
        "rider_pi": {
            "host": rider_pi_host,
            "status": rider_pi_check.get("status", "offline"),
        },
        "internet": {
            "host": INTERNET_PROBE_HOST,
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


@router.get("/api/google/status")
async def google_feed_status(request: Request):
    from pc_client.api.routers.control_router import _remote_snapshot

    return JSONResponse(await _remote_snapshot(request, "google_feed", "get_json", {}, "/api/google/status"))


@router.get("/api/google/raw/last.json")
async def google_feed_last(request: Request):
    from pc_client.api.routers.control_router import _remote_snapshot

    return JSONResponse(
        await _remote_snapshot(request, "google_feed_last", "get_json", {}, "/api/google/raw/last.json")
    )


@router.get("/api/proxy/pi/status")
async def pi_model_status(request: Request):
    from pc_client.api.routers.control_router import _remote_snapshot

    system, registry, inventory = await asyncio.gather(
        _remote_snapshot(request, "model_system", "get_sysinfo", {}),
        _remote_snapshot(request, "model_registry", "get_providers_state", {}),
        _remote_snapshot(request, "model_inventory", "get_remote_models", {}),
    )
    unavailable = any(row.get("offline") or row.get("error") for row in (system, registry, inventory))
    return JSONResponse(
        {
            "source": "pi",
            "offline": unavailable,
            "stale": unavailable,
            "observed_at": system.get("observed_at", system.get("ts")),
            "received_at": system.get("received_at"),
            "cpu_usage": system.get("cpu_pct"),
            "temp_c": system.get("temp_c"),
            "latency_ms": None,
            "available_models": inventory.get("models", []),
            "domains": registry.get("domains", {}),
            "model_binding_available": False,
            "reason": "pi_model_binding_not_advertised",
            "active_model": None,
            "error": "source_unavailable" if unavailable else None,
        },
        status_code=503 if unavailable else 200,
    )


@router.post("/api/proxy/pi/set-model")
async def pi_model_binding_unavailable(request: Request):
    # Pi nie publikuje kontraktu zapisu model binding. Routing domeny to inna operacja.
    return JSONResponse({"ok": False, "error": "pi_model_binding_not_advertised"}, status_code=409)
