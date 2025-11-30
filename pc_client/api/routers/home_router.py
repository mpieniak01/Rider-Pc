"""Google Home integration endpoints.

Provides both legacy proxy mode (via RestAdapter to Rider-Pi) and native OAuth 2.0
authentication flow for direct communication with Google Smart Device Management API.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse, RedirectResponse

from pc_client.adapters import RestAdapter
from pc_client.services.google_home import (
    GoogleHomeService,
    get_google_home_service,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_google_home_service(app) -> GoogleHomeService:
    """Get or create the Google Home service from app settings."""
    settings = getattr(app.state, "settings", None)
    if settings and settings.google_home_local_enabled:
        return get_google_home_service(
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            project_id=settings.google_device_access_project_id,
            redirect_uri=settings.google_redirect_uri,
            tokens_path=settings.google_tokens_path,
            test_mode=settings.google_home_test_mode or settings.test_mode,
        )
    # Return test mode service for fallback
    return get_google_home_service(test_mode=True)


def _use_local_service(app) -> bool:
    """Check if we should use the local Google Home service."""
    settings = getattr(app.state, "settings", None)
    return settings and settings.google_home_local_enabled


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

    If GOOGLE_HOME_LOCAL_ENABLED=true, returns status from local GoogleHomeService.
    Otherwise, proxies to Rider-Pi or returns mock data.
    """
    # Try local service first
    if _use_local_service(request.app):
        service = _get_google_home_service(request.app)
        status = service.get_status()
        return JSONResponse(content=status)

    # Fallback to adapter/mock
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

    If GOOGLE_HOME_LOCAL_ENABLED=true, fetches devices from SDM API.
    Otherwise, proxies to Rider-Pi or returns mock data.
    """
    # Try local service first
    if _use_local_service(request.app):
        service = _get_google_home_service(request.app)
        result = await service.list_devices()
        return JSONResponse(content=result)

    # Fallback to adapter/mock
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
    """Forward device command.

    If GOOGLE_HOME_LOCAL_ENABLED=true, sends command via SDM API.
    Otherwise, proxies to Rider-Pi or applies locally.
    """
    body = payload or {}

    # Try local service first
    if _use_local_service(request.app):
        service = _get_google_home_service(request.app)
        device_id = body.get("deviceId", "")
        command = body.get("command", "")
        params = body.get("params", {})
        result = await service.send_command(device_id, command, params)
        status_code = 200 if result.get("ok") else 400
        return JSONResponse(content=result, status_code=status_code)

    # Fallback to adapter/mock
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


@router.post("/api/home/auth")
async def home_auth(request: Request) -> JSONResponse:
    """Trigger Google auth handshake or return auth URL.

    For local mode: returns auth_url for OAuth flow.
    For legacy mode: proxies to Rider-Pi or simulates auth.
    """
    # Try local service first
    if _use_local_service(request.app):
        service = _get_google_home_service(request.app)
        if service.is_authenticated():
            return JSONResponse(content={"ok": True, "already_authenticated": True})
        result = service.start_auth_session()
        return JSONResponse(content=result)

    # Fallback to adapter/mock
    adapter: Optional[RestAdapter] = request.app.state.rest_adapter
    if adapter and hasattr(adapter, "post_home_auth"):
        try:
            result = await adapter.post_home_auth()
            status = 200 if not result.get("error") else 502
            return JSONResponse(content=result, status_code=status)
        except Exception as exc:  # pragma: no cover
            return JSONResponse(content={"ok": False, "error": str(exc)}, status_code=502)
    state = _home_state(request.app)
    state["authenticated"] = True
    state.setdefault("profile", {})["updated_at"] = time.time()
    return JSONResponse(content={"ok": True, "note": "local mock auth"})


@router.get("/api/home/auth/url")
async def home_auth_url(request: Request) -> JSONResponse:
    """Get OAuth authorization URL for Google login.

    Returns:
        JSON with auth_url for redirecting user to Google login.
    """
    service = _get_google_home_service(request.app)
    result = service.start_auth_session()

    if not result.get("ok"):
        return JSONResponse(content=result, status_code=400)

    return JSONResponse(content=result)


@router.get("/api/home/auth/callback")
async def home_auth_callback(
    request: Request,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
) -> RedirectResponse:
    """Handle OAuth callback from Google.

    After user authorizes, Google redirects here with code and state.
    We exchange the code for tokens and redirect to google_home page.
    """
    # Handle error from Google
    if error:
        logger.warning("OAuth callback error: %s - %s", error, error_description)
        return RedirectResponse(url=f"/google_home?auth=error&error={error}")

    # Validate parameters
    if not code or not state:
        return RedirectResponse(url="/google_home?auth=error&error=missing_params")

    # Complete the OAuth flow
    service = _get_google_home_service(request.app)
    result = await service.complete_auth(code, state)

    if result.get("ok"):
        logger.info("OAuth flow completed successfully")
        return RedirectResponse(url="/google_home?auth=success")
    else:
        error_code = result.get("error", "unknown")
        logger.error("OAuth flow failed: %s", result)
        return RedirectResponse(url=f"/google_home?auth=error&error={error_code}")


@router.post("/api/home/auth/clear")
async def home_auth_clear(request: Request) -> JSONResponse:
    """Clear stored authentication tokens.

    Useful for logging out or resetting the OAuth state.
    """
    if _use_local_service(request.app):
        service = _get_google_home_service(request.app)
        result = service.clear_auth()
        return JSONResponse(content=result)

    # For non-local mode, just reset the state
    request.app.state.home_state = {
        "authenticated": False,
        "profile": None,
        "scopes": [],
    }
    return JSONResponse(content={"ok": True, "message": "Auth state cleared"})


@router.get("/api/home/profile")
async def home_profile(request: Request) -> JSONResponse:
    """Get the current user's Google profile.

    Returns profile information if authenticated.
    """
    if _use_local_service(request.app):
        service = _get_google_home_service(request.app)
        profile = service.get_profile()
        if profile:
            return JSONResponse(content={"ok": True, "profile": profile})
        return JSONResponse(content={"ok": False, "error": "not_authenticated"})

    # For non-local mode, return from state
    state = _home_state(request.app)
    if state.get("authenticated"):
        return JSONResponse(content={"ok": True, "profile": state.get("profile")})
    return JSONResponse(content={"ok": False, "error": "not_authenticated"})
