"""Google Home integration endpoints."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from pc_client.adapters import RestAdapter

router = APIRouter()


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
    """Return Google Home auth state."""
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
    """Return list of Google Home devices."""
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
    """Forward device command."""
    adapter: Optional[RestAdapter] = request.app.state.rest_adapter
    body = payload or {}
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
    """Simulate Google auth handshake."""
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
