"""Shared periodic observations; inactive resources never trigger frame downloads."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import Dict, Optional

from fastapi import FastAPI
from pc_client.adapters import RestAdapter

from pc_client.api.telemetry_snapshot import refresh_snapshot, unavailable_snapshot
from pc_client.api.binary_snapshot import fetch_camera_binary
from pc_client.core.remote_safety import finite_number

logger = logging.getLogger(__name__)

from pc_client.api.observation_policy import INTERVALS


def camera_activity(app):
    cache = getattr(app.state, "cache", None)
    if cache is None or getattr(app.state, "rest_adapter", None) is None:
        return None
    # Prefer the live telemetry projection. A known OFF never falls back to old ON.
    for key in ("state", "healthz"):
        row = cache.get(key)
        if not isinstance(row, dict) or row.get("offline") or row.get("stale") or row.get("error"):
            continue
        received = row.get("received_at")
        if not finite_number(received) or not 0 <= time.time() - received <= 8:
            continue
        parent = row.get("camera") if key == "state" else row.get("devices")
        if not isinstance(parent, dict):
            continue
        activity = parent.get("activity" if key == "state" else "camera")
        if (
            isinstance(activity, dict)
            and isinstance(activity.get("on"), bool)
            and not activity.get("error")
            and not activity.get("stale")
            and not activity.get("offline")
        ):
            return activity["on"]
    return None


def camera_on(app) -> bool:
    return camera_activity(app) is True


async def sync_data_periodically(app: FastAPI):
    """A single read schedule per key, shared with foreground readers."""
    due = {}
    next_cleanup = 0.0
    was_on = None
    missing_adapter = False
    while True:
        adapter = app.state.rest_adapter
        if adapter is not None:
            now = time.monotonic()
            on = camera_on(app)
            if on != was_on:
                for key in ("vision_snap_info", "vision_obstacle"):
                    due[key] = 0.0
                was_on = on
            missing_adapter = False
            plan = {
                "state": adapter.get_state,
                "sysinfo": adapter.get_sysinfo,
                "healthz": adapter.get_healthz,
                "app_metrics": adapter.get_app_metrics,
                "bus_health": adapter.get_bus_health,
                "vision_snap_info": adapter.get_vision_snap_info,
                "vision_obstacle": adapter.get_vision_obstacle,
            }

            async def read(key, fetch):
                period = INTERVALS[key]
                try:
                    row = await refresh_snapshot(app, key, fetch, reuse_s=period)
                    if key == "state" and not row.get("offline") and isinstance(row.get("tracking"), dict):
                        app.state.control_state["tracking"] = row["tracking"]
                finally:
                    due[key] = time.monotonic() + period

            await asyncio.gather(
                *(
                    read(key, fetch)
                    for key, fetch in plan.items()
                    if now >= due.get(key, 0) and (on or not key.startswith("vision_"))
                ),
                return_exceptions=True,
            )
            if now >= next_cleanup:
                app.state.cache.cleanup_expired()
                next_cleanup = now + 30.0
        elif not missing_adapter:
            for key in INTERVALS:
                app.state.cache.set(key, unavailable_snapshot(app.state.cache.get(key), error="pi_offline"))
            missing_adapter = True
        await asyncio.sleep(0.5)


def _last_modified_timestamp(headers: Dict[str, str]) -> Optional[float]:
    """Return UNIX timestamp if Last-Modified header is present."""
    last_modified = next((value for key, value in headers.items() if key.lower() == "last-modified"), None)
    if not last_modified:
        return None
    try:
        parsed = parsedate_to_datetime(last_modified)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        observed = parsed.timestamp()
        return observed if finite_number(observed) and observed > 0 else None
    except Exception as exc:  # pragma: no cover - defensive parsing
        logger.debug("Failed to parse Last-Modified header '%s': %s", last_modified, exc)
        return None


async def _fetch_and_store_camera_frame(app: FastAPI) -> None:
    """Fetch the latest camera frame from Rider-PI and cache it locally."""
    adapter: Optional[RestAdapter] = app.state.rest_adapter
    if adapter is None:
        logger.debug("REST adapter unavailable, skipping camera frame fetch")
        return

    content, media_type, headers = await fetch_camera_binary(app)
    timestamp = _last_modified_timestamp(headers)
    app.state.last_camera_frame = {
        "content": content,
        "media_type": media_type,
        "timestamp": timestamp,
        "received_at": time.time(),
    }


async def sync_camera_frame_periodically(app: FastAPI, interval: float = 0.8):
    """Fetch frames only while camera is observed ON; retry failures more slowly."""
    logger.info("Starting demand-aware camera sync")
    while True:
        delay = interval if camera_on(app) else 2.0
        if camera_on(app):
            try:
                await _fetch_and_store_camera_frame(app)
            except Exception as exc:
                logger.debug("Camera frame sync failed: %s", exc)
                delay = 5.0
        await asyncio.sleep(delay)
