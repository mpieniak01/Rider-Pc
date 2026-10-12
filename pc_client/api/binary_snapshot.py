"""One bounded camera transfer shared by background and HTTP GET/HEAD readers."""

from __future__ import annotations

import asyncio
import time


def invalidate(app):
    app.state.camera_binary_generation = getattr(app.state, "camera_binary_generation", 0) + 1
    app.state.camera_binary_cached = None
    app.state.camera_binary_flight = None


async def fetch_camera_binary(app, *, params=None):
    adapter = app.state.rest_adapter
    params = params or {}
    # Archives and custom queries are explicit requests, never background frames.
    if params:
        return await adapter.fetch_binary("/camera/last", params=params)
    now = time.monotonic()
    cached = getattr(app.state, "camera_binary_cached", None)
    if cached and cached[0] is adapter and 0 <= now - cached[1] < 0.8:
        if isinstance(cached[2], Exception):
            raise cached[2]
        return cached[2]
    flight = getattr(app.state, "camera_binary_flight", None)
    generation = getattr(app.state, "camera_binary_generation", 0)
    if flight is None or flight.done():

        async def read():
            try:
                result = await adapter.fetch_binary("/camera/last", params={})
            except Exception as exc:
                if generation == getattr(app.state, "camera_binary_generation", 0):
                    app.state.camera_binary_cached = (adapter, time.monotonic(), exc)
                raise
            if generation != getattr(app.state, "camera_binary_generation", 0):
                raise RuntimeError("camera_observation_superseded")
            app.state.camera_binary_cached = (adapter, time.monotonic(), result)
            return result

        flight = app.state.camera_binary_flight = asyncio.create_task(read())
    try:
        return await asyncio.shield(flight)
    finally:
        if flight.done() and getattr(app.state, "camera_binary_flight", None) is flight:
            app.state.camera_binary_flight = None
