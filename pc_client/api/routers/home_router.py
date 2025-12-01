"""Google Home integration endpoints.

Provides OAuth 2.0 flow for Google Home authentication and Smart Device Management
(SDM) API integration. Supports both local (native) mode and legacy proxy mode
through Rider-Pi.
"""

from __future__ import annotations

import html
import logging
import time
from typing import Any, Dict, Optional
from urllib.parse import quote

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from pc_client.adapters import RestAdapter
from pc_client.services.google_home import GoogleHomeService, get_google_home_service, reset_google_home_service

logger = logging.getLogger(__name__)
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


def _get_service(request: Request) -> GoogleHomeService:
    """Get or create GoogleHomeService instance from app state."""
    settings = request.app.state.settings

    # Check if service exists in app state
    service = getattr(request.app.state, "google_home_service", None)
    if service is not None:
        return service

    # Create service based on settings
    test_mode = settings.test_mode or settings.google_home_test_mode

    service = get_google_home_service(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        project_id=settings.google_device_access_project_id,
        redirect_uri=settings.google_home_redirect_uri,
        tokens_path=settings.google_home_tokens_path,
        test_mode=test_mode,
    )

    # Store in app state for reuse
    request.app.state.google_home_service = service
    return service


def _home_state(app) -> Dict[str, Any]:
    """Get fallback home state (legacy mock mode)."""
    state = getattr(app.state, "home_state", None)
    if isinstance(state, dict):
        return state
    default = {"authenticated": False, "profile": {"email": "unknown@mock.local"}, "scopes": []}
    app.state.home_state = default
    return default


def _home_devices(app) -> Dict[str, Any]:
    """Get fallback home devices (legacy mock mode)."""
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
    """Apply command to local mock devices."""
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
    """Return Google Home auth and configuration status.

    Returns comprehensive status including:
    - configured: Whether OAuth credentials are set
    - authenticated: Whether valid tokens exist
    - auth_url_available: Whether auth flow can be initiated
    - profile: User profile if authenticated
    - error: Error code if not configured
    """
    settings = request.app.state.settings

    # In test mode, use simple mock state from app.state
    if settings.test_mode:
        return JSONResponse(content=_home_state(request.app))

    # Use local service if enabled
    if settings.google_home_local_enabled:
        service = _get_service(request)
        status = service.get_status()
        return JSONResponse(content=status)

    # Legacy: proxy to Rider-Pi
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


@router.get("/api/home/auth/url")
async def home_auth_url(request: Request) -> JSONResponse:
    """Generate OAuth authorization URL for Google sign-in.

    Returns:
        JSON with auth_url for redirecting user to Google login,
        state parameter for CSRF protection, and expiration time.
    """
    settings = request.app.state.settings

    if not settings.google_home_local_enabled:
        return JSONResponse(
            content={"ok": False, "error": "local_mode_disabled", "auth_url": None},
            status_code=400,
        )

    service = _get_service(request)
    result = service.build_auth_url()

    if not result.get("ok"):
        return JSONResponse(content=result, status_code=400)

    return JSONResponse(content=result)


@router.get("/api/home/auth/callback")
async def home_auth_callback(
    request: Request,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
) -> HTMLResponse:
    """Handle OAuth callback from Google.

    This endpoint receives the authorization code from Google after user
    grants permission. It exchanges the code for tokens and redirects
    back to the Google Home UI page.
    """
    # Handle OAuth errors from Google
    if error:
        logger.warning("OAuth callback error: %s", error)
        return HTMLResponse(
            content=_auth_result_html(success=False, error=error),
            status_code=400,
        )

    if not code or not state:
        return HTMLResponse(
            content=_auth_result_html(success=False, error="missing_params"),
            status_code=400,
        )

    service = _get_service(request)
    result = await service.complete_auth(code, state)

    if not result.get("ok"):
        error_code = result.get("error", "auth_failed")
        return HTMLResponse(
            content=_auth_result_html(success=False, error=error_code),
            status_code=400,
        )

    # Update app state for compatibility
    request.app.state.home_state = {
        "authenticated": True,
        "profile": result.get("profile"),
        "scopes": ["sdm.service"],
    }

    return HTMLResponse(
        content=_auth_result_html(success=True),
        status_code=200,
    )


def _auth_result_html(success: bool, error: Optional[str] = None) -> str:
    """Generate HTML page for OAuth result with auto-redirect."""
    if success:
        message = "Logowanie zakończone pomyślnie!"
        redirect_url = "/google_home?auth=success"
        status_class = "success"
    else:
        # Sanitize error message for display and URL encode for redirect
        safe_error = error if error else "unknown"
        message = f"Błąd logowania: {safe_error}"
        redirect_url = f"/google_home?auth=error&error={quote(safe_error, safe='')}"
        status_class = "error"

    return f"""<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Google Home - Autoryzacja</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: #1a1a2e;
            color: #eee;
        }}
        .container {{
            text-align: center;
            padding: 2rem;
            background: #16213e;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }}
        .{status_class} {{ color: {'#4caf50' if success else '#f44336'}; }}
        .spinner {{
            border: 3px solid #333;
            border-top: 3px solid #4caf50;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            margin: 1rem auto;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h2 class="{status_class}">{message}</h2>
        <div class="spinner"></div>
        <p>Przekierowywanie...</p>
    </div>
    <script>
        setTimeout(function() {{
            window.location.href = '{redirect_url}';
        }}, 2000);
    </script>
</body>
</html>"""


@router.get("/api/home/devices")
async def home_devices(request: Request) -> JSONResponse:
    """Return list of Google Home devices.

    Uses local SDM API integration when enabled, otherwise
    proxies to Rider-Pi or returns mock data.
    """
    settings = request.app.state.settings

    # In test mode, use simple mock state from app.state
    if settings.test_mode:
        return JSONResponse(content=_home_devices(request.app))

    # Use local service if enabled and authenticated
    if settings.google_home_local_enabled:
        service = _get_service(request)
        if service.is_authenticated():
            result = await service.list_devices()
            if result.get("ok"):
                request.app.state.home_devices = result.get("devices", [])
            return JSONResponse(content=result)

    # Legacy: proxy to Rider-Pi
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
    """Send command to Google Home device.

    Uses local SDM API integration when enabled, otherwise
    proxies to Rider-Pi or applies to mock devices.
    """
    settings = request.app.state.settings
    body = payload or {}

    # In test mode, apply command to local mock devices
    if settings.test_mode:
        result = _apply_local_command(request.app, body)
        return JSONResponse(content=result, status_code=200 if result.get("ok") else 400)

    # Use local service if enabled and authenticated
    if settings.google_home_local_enabled:
        service = _get_service(request)
        if service.is_authenticated():
            result = await service.send_command(
                device_id=body.get("deviceId", ""),
                command=body.get("command", ""),
                params=body.get("params"),
            )
            status = 200 if result.get("ok") else 400
            return JSONResponse(content=result, status_code=status)

    # Legacy: proxy to Rider-Pi
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
    """Initiate or restart Google auth flow.

    In local mode, returns auth URL for browser redirect.
    In legacy mode, proxies to Rider-Pi auth endpoint.
    In test mode, simulates successful auth.
    """
    settings = request.app.state.settings

    # In test mode, simulate successful auth
    if settings.test_mode:
        state = _home_state(request.app)
        state["authenticated"] = True
        state.setdefault("profile", {})["updated_at"] = time.time()
        return JSONResponse(content={"ok": True, "note": "local mock auth"})

    # Local mode: return auth URL
    if settings.google_home_local_enabled:
        service = _get_service(request)
        result = service.build_auth_url()

        if result.get("ok"):
            return JSONResponse(content={
                "ok": True,
                "auth_url": result.get("auth_url"),
                "note": "redirect_required",
            })
        else:
            return JSONResponse(content=result, status_code=400)

    # Legacy: proxy to Rider-Pi
    adapter: Optional[RestAdapter] = request.app.state.rest_adapter
    if adapter and hasattr(adapter, "post_home_auth"):
        try:
            result = await adapter.post_home_auth()
            status = 200 if not result.get("error") else 502
            return JSONResponse(content=result, status_code=status)
        except Exception as exc:  # pragma: no cover
            return JSONResponse(content={"ok": False, "error": str(exc)}, status_code=502)

    # Fallback: mock auth
    state = _home_state(request.app)
    state["authenticated"] = True
    state.setdefault("profile", {})["updated_at"] = time.time()
    return JSONResponse(content={"ok": True, "note": "local mock auth"})


@router.post("/api/home/logout")
async def home_logout(request: Request) -> JSONResponse:
    """Clear stored Google tokens and logout."""
    settings = request.app.state.settings

    if settings.google_home_local_enabled:
        service = _get_service(request)
        result = service.logout()

        # Update app state
        request.app.state.home_state = {
            "authenticated": False,
            "profile": None,
            "scopes": [],
        }

        # Reset service singleton to force re-creation
        reset_google_home_service()
        request.app.state.google_home_service = None

        return JSONResponse(content=result)

    # Legacy mode: reset local state only
    request.app.state.home_state = {
        "authenticated": False,
        "profile": None,
        "scopes": [],
    }
    return JSONResponse(content={"ok": True, "note": "local state cleared"})
