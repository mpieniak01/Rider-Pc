"""Google Assistant API endpoints for smart home control.

Provides endpoints for listing devices, sending commands, and viewing history.
Devices are configured in config/google_assistant_devices.toml.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_service(request: Request):
    """Get Google Assistant service from app state."""
    return getattr(request.app.state, "google_assistant_service", None)


@router.get("/api/assistant/status")
async def assistant_status(request: Request) -> JSONResponse:
    """Return Google Assistant integration status."""
    service = _get_service(request)
    if not service:
        return JSONResponse(
            content={"ok": False, "enabled": False, "error": "Service not initialized"},
            status_code=200,
        )

    return JSONResponse(content={"ok": True, **service.get_status()})


@router.get("/api/assistant/devices")
async def assistant_devices(request: Request) -> JSONResponse:
    """Return list of configured devices."""
    service = _get_service(request)
    if not service:
        return JSONResponse(
            content={"ok": False, "devices": [], "error": "Service not initialized"},
            status_code=200,
        )

    devices = service.list_devices()
    return JSONResponse(content={"ok": True, "devices": devices})


@router.get("/api/assistant/device/{device_id}")
async def assistant_device(request: Request, device_id: str) -> JSONResponse:
    """Return details for a specific device."""
    service = _get_service(request)
    if not service:
        return JSONResponse(
            content={"ok": False, "error": "Service not initialized"},
            status_code=200,
        )

    device = service.get_device(device_id)
    if not device:
        return JSONResponse(
            content={"ok": False, "error": f"Device not found: {device_id}"},
            status_code=404,
        )

    return JSONResponse(content={"ok": True, "device": device})


@router.post("/api/assistant/command")
async def assistant_command(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    """Send a command to a device.

    Body:
        device_id: Target device ID
        action: Action to perform (on, off, brightness, dock)
        params: Optional action parameters (e.g., {"value": 75} for brightness)
    """
    service = _get_service(request)
    if not service:
        return JSONResponse(
            content={"ok": False, "error": "Service not initialized"},
            status_code=200,
        )

    device_id = payload.get("device_id")
    action = payload.get("action")
    params = payload.get("params") or {}

    if not device_id:
        return JSONResponse(
            content={"ok": False, "error": "Missing device_id"},
            status_code=400,
        )

    if not action:
        return JSONResponse(
            content={"ok": False, "error": "Missing action"},
            status_code=400,
        )

    result = await service.send_command(device_id, action, params)
    status_code = 200 if result.get("ok") else 400
    return JSONResponse(content=result, status_code=status_code)


@router.post("/api/assistant/custom")
async def assistant_custom(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    """Send a custom text command to Google Assistant.

    Body:
        text: Custom command text (e.g., "Wyłącz wszystkie światła")
    """
    service = _get_service(request)
    if not service:
        return JSONResponse(
            content={"ok": False, "error": "Service not initialized"},
            status_code=200,
        )

    text = payload.get("text", "").strip()
    if not text:
        return JSONResponse(
            content={"ok": False, "error": "Missing command text"},
            status_code=400,
        )

    result = await service.send_custom_text(text)
    status_code = 200 if result.get("ok") else 400
    return JSONResponse(content=result, status_code=status_code)


@router.get("/api/assistant/history")
async def assistant_history(request: Request, limit: int = 20) -> JSONResponse:
    """Return command history.

    Query params:
        limit: Maximum number of entries (default: 20)
    """
    service = _get_service(request)
    if not service:
        return JSONResponse(
            content={"ok": False, "history": [], "error": "Service not initialized"},
            status_code=200,
        )

    history = service.get_history(limit=limit)
    return JSONResponse(content={"ok": True, "history": history})


@router.post("/api/assistant/reload")
async def assistant_reload(request: Request) -> JSONResponse:
    """Reload device configuration from file."""
    service = _get_service(request)
    if not service:
        return JSONResponse(
            content={"ok": False, "error": "Service not initialized"},
            status_code=200,
        )

    result = service.reload_config()
    return JSONResponse(content=result)
