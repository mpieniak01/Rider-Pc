"""Google Home integration endpoints."""

from __future__ import annotations

import html
import logging
import time
from typing import Any, Dict, Optional
from urllib.parse import quote

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from pc_client.adapters import RestAdapter
from pc_client.services.google_home import (
    GoogleHomeConfig,
    GoogleHomeService,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_google_home_service(request: Request) -> Optional[GoogleHomeService]:
    """Get GoogleHomeService from app state or create one."""
    service = getattr(request.app.state, "google_home_service", None)
    if service is None:
        settings = getattr(request.app.state, "settings", None)
        if settings and getattr(settings, "google_home_local_enabled", False):
            config = GoogleHomeConfig(
                client_id=getattr(settings, "google_home_client_id", ""),
                client_secret=getattr(settings, "google_home_client_secret", ""),
                project_id=getattr(settings, "google_home_project_id", ""),
                redirect_uri=getattr(settings, "google_home_redirect_uri", ""),
                tokens_path=getattr(settings, "google_home_tokens_path", "config/local/google_tokens_pc.json"),
                test_mode=getattr(settings, "google_home_test_mode", False),
            )
            service = GoogleHomeService(config)
            request.app.state.google_home_service = service
    return service


def _home_state(app) -> Dict[str, Any]:
    state = getattr(app.state, "home_state", None)
    if isinstance(state, dict):
        return state
    default = {"authenticated": False, "profile": {"email": "unknown@mock.local"}, "scopes": []}
    app.state.home_state = default
    return default


def _home_devices(app) -> Dict[str, Any]:
    devices = getattr(app.state, "home_devices", None)
    if isinstance(devices, list):
        return {"ok": True, "devices": devices}
    payload = {
        "ok": True,
        "devices": [
            {
                "name": "devices/light/living-room",
                "type": "action.devices.types.LIGHT",
                "traits": {
                    "sdm.devices.traits.OnOff": {"on": True},
                    "sdm.devices.traits.Brightness": {"brightness": 72},
                    "sdm.devices.traits.ColorSetting": {"color": {"temperatureK": 3200}},
                },
            },
            {
                "name": "devices/thermostat/hall",
                "type": "action.devices.types.THERMOSTAT",
                "traits": {
                    "sdm.devices.traits.ThermostatMode": {"mode": "heatcool"},
                    "sdm.devices.traits.ThermostatTemperatureSetpoint": {"heatCelsius": 20.0, "coolCelsius": 24.0},
                    "sdm.devices.traits.Temperature": {"ambientTemperatureCelsius": 21.5},
                },
            },
            {
                "name": "devices/vacuum/dusty",
                "type": "action.devices.types.VACUUM",
                "traits": {
                    "sdm.devices.traits.StartStop": {"isRunning": False, "isPaused": False},
                    "sdm.devices.traits.Dock": {"available": True},
                },
            },
        ],
    }
    app.state.home_devices = payload["devices"]
    return payload


def _apply_local_command(app, payload: Dict[str, Any]) -> Dict[str, Any]:
    devices = getattr(app.state, "home_devices", []) or []
    device_id = payload.get("deviceId")
    command = payload.get("command")
    params = payload.get("params") or {}
    target = next((d for d in devices if d.get("name") == device_id), None)
    if not target:
        return {"ok": False, "error": "device_not_found"}

    traits = target.setdefault("traits", {})
    if command == "action.devices.commands.OnOff":
        traits.setdefault("sdm.devices.traits.OnOff", {})["on"] = bool(params.get("on"))
    elif command == "action.devices.commands.BrightnessAbsolute":
        traits.setdefault("sdm.devices.traits.Brightness", {})["brightness"] = int(params.get("brightness", 0))
    elif command == "action.devices.commands.ColorAbsolute":
        traits.setdefault("sdm.devices.traits.ColorSetting", {})["color"] = params.get("color", {})
    elif command == "action.devices.commands.ThermostatTemperatureSetpoint":
        traits.setdefault("sdm.devices.traits.ThermostatTemperatureSetpoint", {}).update(params)
    elif command == "action.devices.commands.StartStop":
        traits.setdefault("sdm.devices.traits.StartStop", {}).update(
            {"isRunning": bool(params.get("start")), "isPaused": False}
        )
    elif command == "action.devices.commands.PauseUnpause":
        traits.setdefault("sdm.devices.traits.StartStop", {}).update({"isPaused": bool(params.get("pause"))})
    elif command == "action.devices.commands.Dock":
        traits.setdefault("sdm.devices.traits.Dock", {})["lastDockTs"] = time.time()
    return {"ok": True, "device": device_id, "command": command}


@router.get("/api/home/status")
async def home_status(request: Request) -> JSONResponse:
    """Return Google Home auth state.

    When GOOGLE_HOME_LOCAL_ENABLED=true, returns status from local GoogleHomeService.
    Otherwise falls back to RestAdapter (Rider-Pi proxy) or mock data.
    """
    # Try local service first
    service = _get_google_home_service(request)
    if service:
        status = service.get_status()
        return JSONResponse(content=status)

    # Fallback to RestAdapter (Rider-Pi proxy)
    adapter: Optional[RestAdapter] = request.app.state.rest_adapter
    if adapter and hasattr(adapter, "get_home_status"):
        try:
            data = await adapter.get_home_status()
            if isinstance(data, dict):
                request.app.state.home_state = data
                return JSONResponse(content=data)
        except Exception:  # pragma: no cover - network fallback
            pass
    return JSONResponse(content=_home_state(request.app))


@router.get("/api/home/devices")
async def home_devices(request: Request) -> JSONResponse:
    """Return list of Google Home devices.

    When GOOGLE_HOME_LOCAL_ENABLED=true, fetches devices from SDM API.
    Otherwise falls back to RestAdapter or mock data.
    """
    # Try local service first
    service = _get_google_home_service(request)
    if service and service.is_authenticated():
        result = await service.list_devices()
        return JSONResponse(content=result)

    # Fallback to RestAdapter (Rider-Pi proxy)
    adapter: Optional[RestAdapter] = request.app.state.rest_adapter
    if adapter and hasattr(adapter, "get_home_devices"):
        try:
            result = await adapter.get_home_devices()
            if isinstance(result, dict) and not result.get("error"):
                request.app.state.home_devices = result.get("devices", [])
                return JSONResponse(content=result)
        except Exception:  # pragma: no cover
            pass
    return JSONResponse(content=_home_devices(request.app))


@router.post("/api/home/command")
async def home_command(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    """Send command to a Google Home device.

    When GOOGLE_HOME_LOCAL_ENABLED=true, sends command via SDM API.
    Otherwise falls back to RestAdapter or local mock.
    """
    body = payload or {}

    # Try local service first
    service = _get_google_home_service(request)
    if service and service.is_authenticated():
        result = await service.send_command(
            device_id=body.get("deviceId", ""),
            command=body.get("command", ""),
            params=body.get("params", {}),
        )
        status_code = 200 if result.get("ok") else 400
        return JSONResponse(content=result, status_code=status_code)

    # Fallback to RestAdapter (Rider-Pi proxy)
    adapter: Optional[RestAdapter] = request.app.state.rest_adapter
    if adapter and hasattr(adapter, "post_home_command"):
        try:
            result = await adapter.post_home_command(body)
            status = 200 if not result.get("error") else 502
            return JSONResponse(content=result, status_code=status)
        except Exception as exc:  # pragma: no cover
            return JSONResponse(content={"ok": False, "error": str(exc)}, status_code=502)
    result = _apply_local_command(request.app, body)
    return JSONResponse(content=result, status_code=200 if result.get("ok") else 400)


@router.get("/api/home/auth/url")
async def home_auth_url(request: Request) -> JSONResponse:
    """Get OAuth authorization URL for Google Home.

    Returns JSON with auth_url that the client should redirect to.
    This endpoint starts the OAuth 2.0 Authorization Code flow with PKCE.

    Returns:
        - ok: True if URL was generated successfully
        - auth_url: URL to redirect user to for Google authentication
        - state: CSRF protection state token
        - expires_at: Timestamp when the auth session expires
    """
    service = _get_google_home_service(request)
    if not service:
        return JSONResponse(
            content={
                "ok": False,
                "error": "not_enabled",
                "message": "Google Home local mode not enabled. Set GOOGLE_HOME_LOCAL_ENABLED=true",
            },
            status_code=400,
        )

    result = service.start_auth_session()
    status_code = 200 if result.get("ok") else 400
    return JSONResponse(content=result, status_code=status_code)


@router.get("/api/home/auth/callback")
async def home_auth_callback(
    request: Request,
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
) -> HTMLResponse:
    """Handle OAuth callback from Google.

    This endpoint receives the authorization code from Google after user consent.
    It exchanges the code for tokens and stores them locally.

    Query Parameters:
        - code: Authorization code from Google
        - state: CSRF protection state token
        - error: Error code if authorization failed

    Returns:
        HTML page that redirects to google_home.html with auth result.
    """
    # Handle error from Google
    if error:
        logger.warning("Google OAuth error: %s", error)
        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html>
            <head><meta http-equiv="refresh" content="2;url=/web/google_home.html?auth=error&reason={error}"></head>
            <body>
                <p>Błąd autoryzacji: {error}. Przekierowanie...</p>
            </body>
            </html>
            """,
            status_code=400,
        )

    # Validate required parameters
    if not code or not state:
        redirect_url = "/web/google_home.html?auth=error&reason=missing_params"
        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html>
            <head><meta http-equiv="refresh" content="2;url={redirect_url}"></head>
            <body>
                <p>Brak wymaganych parametrów. Przekierowanie...</p>
            </body>
            </html>
            """,
            status_code=400,
        )

    service = _get_google_home_service(request)
    if not service:
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head><meta http-equiv="refresh" content="2;url=/web/google_home.html?auth=error&reason=not_enabled"></head>
            <body>
                <p>Google Home nie jest włączone lokalnie. Przekierowanie...</p>
            </body>
            </html>
            """,
            status_code=400,
        )

    # Complete the OAuth flow
    result = await service.complete_auth(code, state)

    if result.get("ok"):
        logger.info("Google Home OAuth completed successfully")
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head><meta http-equiv="refresh" content="1;url=/web/google_home.html?auth=success"></head>
            <body>
                <p>Autoryzacja zakończona pomyślnie! Przekierowanie...</p>
            </body>
            </html>
            """
        )
    else:
        error_msg = result.get("error", "unknown")
        logger.warning("Google Home OAuth failed: %s", error_msg)
        safe_error_msg = html.escape(error_msg)
        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html>
            <head><meta http-equiv="refresh" content="2;url=/web/google_home.html?auth=error&reason={error_msg}"></head>
            <body>
                <p>Błąd autoryzacji: {error_msg}. Przekierowanie...</p>
            </body>
            </html>
            """,
            status_code=400,
        )


@router.post("/api/home/auth")
async def home_auth(request: Request) -> JSONResponse:
    """Trigger Google auth handshake (legacy/mock endpoint).

    When GOOGLE_HOME_LOCAL_ENABLED=true, this returns info about the OAuth flow.
    Otherwise simulates authentication for testing.
    """
    # Check if local service is available
    service = _get_google_home_service(request)
    if service:
        if service.is_authenticated():
            return JSONResponse(content={"ok": True, "authenticated": True, "note": "already authenticated"})
        # Return info about starting OAuth flow
        return JSONResponse(
            content={
                "ok": False,
                "error": "oauth_required",
                "message": "Use GET /api/home/auth/url to start OAuth flow",
            },
            status_code=400,
        )

    # Fallback to RestAdapter (Rider-Pi proxy)
    adapter: Optional[RestAdapter] = request.app.state.rest_adapter
    if adapter and hasattr(adapter, "post_home_auth"):
        try:
            result = await adapter.post_home_auth()
            status = 200 if not result.get("error") else 502
            return JSONResponse(content=result, status_code=status)
        except Exception as exc:  # pragma: no cover
            return JSONResponse(content={"ok": False, "error": str(exc)}, status_code=502)

    # Mock authentication
    state = _home_state(request.app)
    state["authenticated"] = True
    state.setdefault("profile", {})["updated_at"] = time.time()
    return JSONResponse(content={"ok": True, "note": "local mock auth"})


@router.post("/api/home/auth/logout")
async def home_auth_logout(request: Request) -> JSONResponse:
    """Clear Google Home authentication tokens.

    Removes stored tokens and resets authentication state.
    """
    service = _get_google_home_service(request)
    if service:
        service.clear_tokens()
        return JSONResponse(content={"ok": True, "message": "Tokens cleared"})

    # Clear mock state
    state = _home_state(request.app)
    state["authenticated"] = False
    return JSONResponse(content={"ok": True, "note": "local mock logout"})
