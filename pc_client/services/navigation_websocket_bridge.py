"""Optional WebSocket bridge for navigation visualizer."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


def _pick_payload(cache, *keys: str) -> Optional[Dict[str, Any]]:
    for key in keys:
        payload = cache.get(key)
        if payload:
            return payload
    return None


async def _stream_navigation_state(websocket: WebSocket) -> None:
    await websocket.accept()

    cache = websocket.app.state.cache
    last_sent: Dict[str, Any] = {
        "map": None,
        "odometry": None,
        "path": None,
    }

    try:
        while True:
            nav_map = _pick_payload(
                cache,
                "zmq:navigator.map",
                "navigator.map",
            )
            odometry = _pick_payload(
                cache,
                "zmq:navigator.odometry",
                "zmq:motion.odometry",
                "navigator.odometry",
            )
            path = _pick_payload(
                cache,
                "zmq:navigator.path",
                "navigator.path",
            )

            if nav_map is not None and nav_map != last_sent["map"]:
                await websocket.send_json({"type": "map", "data": nav_map})
                last_sent["map"] = nav_map

            if odometry is not None and odometry != last_sent["odometry"]:
                await websocket.send_json({"type": "odometry", "data": odometry})
                last_sent["odometry"] = odometry

            if path is not None and path != last_sent["path"]:
                await websocket.send_json({"type": "path", "data": path})
                last_sent["path"] = path

            await asyncio.sleep(0.2)
    except WebSocketDisconnect:
        logger.info("Navigation WebSocket disconnected")
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Navigation WebSocket error: %s", exc)


def register_websocket_endpoint(app: FastAPI) -> None:
    """Register WebSocket endpoint for navigation visualizer."""

    @app.websocket("/ws/navigation")
    async def navigation_ws(websocket: WebSocket):
        await _stream_navigation_state(websocket)

    logger.info("Navigation WebSocket registered at /ws/navigation")
