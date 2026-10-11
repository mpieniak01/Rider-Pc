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


def _demo(app):
    return getattr(getattr(app.state, "settings", None), "test_mode", False) is True


async def _remote(request, method, *args):
    from pc_client.api.telemetry_snapshot import received_snapshot, unavailable_snapshot

    adapter = request.app.state.rest_adapter
    if adapter is None:
        return None
    try:
        result = await getattr(adapter, method)(*args)
        if not isinstance(result, dict):
            raise ValueError("invalid_response")
        code = result.get("_http_status", 200 if not result.get("error") else 503)
        if result.get("error"):
            result = unavailable_snapshot(result, error=result["error"], attempted_at=time.time())
        else:
            result = received_snapshot(result, source="demo" if _demo(request.app) else "pi", received_at=time.time())
        return JSONResponse(result, status_code=code)
    except Exception:
        return JSONResponse(unavailable_snapshot(error="source_unavailable"), status_code=503)


def _unavailable():
    return JSONResponse(
        {
            "ok": False,
            "error": "home_source_unavailable",
            "source": "pi",
            "configured": False,
            "authenticated": False,
            "offline": True,
            "stale": True,
            "observed_at": None,
            "devices": [],
        },
        status_code=503,
    )


@router.get("/api/home/status")
async def home_status(request: Request):
    remote = await _remote(request, "get_home_status")
    if remote is not None:
        return remote
    if not _demo(request.app):
        return _unavailable()
    return JSONResponse({**_home_state(request.app), "source": "demo", "simulated": True})


@router.get("/api/home/devices")
async def home_devices(request: Request):
    remote = await _remote(request, "get_home_devices")
    if remote is not None:
        return remote
    if not _demo(request.app):
        return _unavailable()
    return JSONResponse({**_home_devices(request.app), "source": "demo", "simulated": True})


@router.post("/api/home/command")
async def home_command(request: Request, payload: Dict[str, Any]):
    remote = await _remote(request, "post_home_command", payload or {})
    if remote is not None:
        return remote
    if not _demo(request.app):
        return _unavailable()
    result = _apply_local_command(request.app, payload)
    return JSONResponse({**result, "source": "demo", "simulated": True}, status_code=200 if result.get("ok") else 400)


@router.post("/api/home/auth")
async def home_auth(request: Request):
    remote = await _remote(request, "post_home_auth")
    if remote is not None:
        return remote
    if not _demo(request.app):
        return _unavailable()
    state = _home_state(request.app)
    state["authenticated"] = True
    return JSONResponse({"ok": True, "source": "demo", "simulated": True, "note": "explicit demo auth"})
