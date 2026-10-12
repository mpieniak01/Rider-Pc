"""Only fake adapters and local caches; never connects to or actuates a robot."""

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pc_client.api import background_sync
from pc_client.api.binary_snapshot import fetch_camera_binary
from pc_client.api.telemetry_snapshot import invalidate_snapshots, refresh_snapshot
from pc_client.api.routers.control_router import router


class MemoryCache:
    def __init__(self):
        self.rows = {}

    def get(self, key, default=None):
        return self.rows.get(key, default)

    def set(self, key, value):
        self.rows[key] = value

    def delete(self, key):
        self.rows.pop(key, None)

    def cleanup_expired(self):
        return 0


def app_fixture(on=None):
    cache = MemoryCache()
    adapter = SimpleNamespace(fetch_binary=AsyncMock(return_value=(b"frame", "image/jpeg", {})))
    app = FastAPI()
    app.state.cache = cache
    app.state.rest_adapter = adapter
    app.state.remote_snapshots = {}
    app.state.control_state = {}
    if on is not None:
        cache.set("state", {"received_at": time.time(), "camera": {"activity": {"on": on}}})
    return app, adapter, cache


@pytest.mark.asyncio
@pytest.mark.parametrize("state", [False, None])
async def test_background_never_downloads_frames_when_off_or_unknown(monkeypatch, state):
    app, adapter, _ = app_fixture(state)
    monkeypatch.setattr(background_sync.asyncio, "sleep", AsyncMock(side_effect=asyncio.CancelledError))
    with pytest.raises(asyncio.CancelledError):
        await background_sync.sync_camera_frame_periodically(app)
    adapter.fetch_binary.assert_not_awaited()


@pytest.mark.asyncio
async def test_background_downloads_when_on_and_backs_off_on_error(monkeypatch):
    app, adapter, _ = app_fixture(True)
    adapter.fetch_binary.side_effect = RuntimeError("no_frame")
    sleep = AsyncMock(side_effect=asyncio.CancelledError)
    monkeypatch.setattr(background_sync.asyncio, "sleep", sleep)
    with pytest.raises(asyncio.CancelledError):
        await background_sync.sync_camera_frame_periodically(app)
    adapter.fetch_binary.assert_awaited_once()
    sleep.assert_awaited_once_with(5.0)


def test_known_off_never_falls_back_to_an_older_on():
    app, _, cache = app_fixture(False)
    cache.set("healthz", {"received_at": time.time(), "devices": {"camera": {"on": True}}})
    assert background_sync.camera_activity(app) is False
    cache.rows["state"]["received_at"] = time.time() - 100
    cache.rows["healthz"]["received_at"] = time.time() - 100
    assert background_sync.camera_activity(app) is None


@pytest.mark.asyncio
async def test_shared_binary_transfer_and_source_headers(monkeypatch):
    app, adapter, _ = app_fixture(True)
    entered, release = asyncio.Event(), asyncio.Event()

    async def fetch(path, params):
        entered.set()
        await release.wait()
        return b"frame", "image/jpeg", {"Last-Modified": "source-time"}

    adapter.fetch_binary.side_effect = fetch
    a = asyncio.create_task(fetch_camera_binary(app))
    await entered.wait()
    b = asyncio.create_task(fetch_camera_binary(app))
    release.set()
    rows = await asyncio.gather(a, b)
    assert rows[0] == rows[1]
    assert rows[0][2] == {"Last-Modified": "source-time"}
    assert await fetch_camera_binary(app) == rows[0]
    adapter.fetch_binary.assert_awaited_once()


@pytest.mark.asyncio
async def test_archive_bypasses_current_frame_cache():
    app, adapter, _ = app_fixture()
    await fetch_camera_binary(app)
    await fetch_camera_binary(app, params={"archive": "1"})
    assert adapter.fetch_binary.await_count == 2


@pytest.mark.asyncio
async def test_action_invalidates_earlier_json_flight():
    app, _, cache = app_fixture(False)
    entered, release = asyncio.Event(), asyncio.Event()

    async def fetch():
        entered.set()
        await release.wait()
        return {"observed_at": 100, "on": True}

    flight = asyncio.create_task(refresh_snapshot(app, "camera_resource", fetch, reuse_s=4))
    await entered.wait()
    invalidate_snapshots(app)
    release.set()
    result = await flight
    assert result["error"] == "observation_superseded"
    assert cache.get("camera_resource") is None


def test_foreground_image_off_is_local_404_but_archive_is_forwarded():
    app, adapter, _ = app_fixture(False)
    app.include_router(router)
    with TestClient(app) as client:
        assert client.get("/camera/last").status_code == 404
        adapter.fetch_binary.assert_not_awaited()
        client.get("/camera/last?archive=1")
        adapter.fetch_binary.assert_awaited_once()


@pytest.mark.asyncio
async def test_periodic_sync_does_not_request_resource_inventory(monkeypatch):
    app, adapter, _ = app_fixture(False)
    for method in (
        "get_state",
        "get_sysinfo",
        "get_healthz",
        "get_app_metrics",
        "get_bus_health",
        "get_vision_snap_info",
        "get_vision_obstacle",
    ):
        setattr(adapter, method, AsyncMock(return_value={"observed_at": 100}))
    adapter.get_camera_resource = AsyncMock()
    adapter.get_resource = AsyncMock()
    monkeypatch.setattr(background_sync.asyncio, "sleep", AsyncMock(side_effect=asyncio.CancelledError))
    with pytest.raises(asyncio.CancelledError):
        await background_sync.sync_data_periodically(app)
    adapter.get_camera_resource.assert_not_awaited()
    adapter.get_resource.assert_not_awaited()
    adapter.get_vision_snap_info.assert_not_awaited()
    adapter.get_vision_obstacle.assert_not_awaited()


def test_resource_get_reuses_one_read_preserving_receipt_time():
    app, adapter, _ = app_fixture()
    adapter.get_resource = AsyncMock(return_value={"observed_at": 100, "free": True})
    app.include_router(router)
    with TestClient(app) as client:
        first = client.get("/api/resource/camera").json()
        second = client.get("/api/resource/camera").json()
    adapter.get_resource.assert_awaited_once()
    assert first["observed_at"] == second["observed_at"] == 100
    assert first["received_at"] == second["received_at"]


@pytest.mark.asyncio
async def test_slow_read_plan_uses_existing_response_for_all_receivers():
    app, adapter, _ = app_fixture()
    adapter.get_healthz = AsyncMock(return_value={"observed_at": 100})
    first = await refresh_snapshot(app, "healthz", adapter.get_healthz, reuse_s=5)
    second = await refresh_snapshot(app, "healthz", adapter.get_healthz, reuse_s=5)
    assert first == second
    adapter.get_healthz.assert_awaited_once()


@pytest.mark.asyncio
async def test_background_intervals_and_resume_after_on(monkeypatch):
    app, adapter, _ = app_fixture(False)
    clock = [1000.0]
    calls = {}
    monkeypatch.setattr(background_sync.time, "time", lambda: clock[0])
    monkeypatch.setattr(background_sync.time, "monotonic", lambda: clock[0])

    for key, method in {
        "state": "get_state",
        "sysinfo": "get_sysinfo",
        "healthz": "get_healthz",
        "app_metrics": "get_app_metrics",
        "bus_health": "get_bus_health",
        "vision_snap_info": "get_vision_snap_info",
        "vision_obstacle": "get_vision_obstacle",
    }.items():
        calls[key] = []

        async def fetch(key=key):
            calls[key].append(clock[0])
            on = clock[0] >= 1005
            return {"observed_at": clock[0], "camera": {"activity": {"on": on}}, "devices": {"camera": {"on": on}}}

        setattr(adapter, method, fetch)

    async def sleep(delay):
        clock[0] += delay
        if clock[0] > 1010:
            raise asyncio.CancelledError

    monkeypatch.setattr(background_sync.asyncio, "sleep", sleep)
    with pytest.raises(asyncio.CancelledError):
        await background_sync.sync_data_periodically(app)
    assert len(calls["state"]) == len(calls["sysinfo"]) == 6
    assert len(calls["healthz"]) == 3
    assert len(calls["app_metrics"]) == len(calls["bus_health"]) == 2
    assert calls["vision_snap_info"] and min(calls["vision_snap_info"]) >= 1006
    assert min(calls["vision_obstacle"]) >= 1006


def test_malformed_camera_status_is_unknown():
    app, _, cache = app_fixture()
    cache.set("state", {"received_at": time.time(), "camera": None})
    cache.set("healthz", {"received_at": time.time(), "devices": None})
    assert background_sync.camera_activity(app) is None


def test_idle_metadata_reuses_history_without_rewriting_source_or_receipt():
    from pc_client.api.routers.status_router import router as status_router

    app, adapter, _ = app_fixture(False)
    adapter.get_vision_snap_info = AsyncMock(return_value={"observed_at": 100, "raw": {"exists": False}})
    app.include_router(status_router)
    with TestClient(app) as client:
        first = client.get("/vision/snap-info").json()
        second = client.get("/vision/snap-info").json()
    adapter.get_vision_snap_info.assert_awaited_once()
    assert first == second and first["observed_at"] == 100


@pytest.mark.asyncio
async def test_failed_postprocessing_preserves_scheduled_retry_period(monkeypatch):
    app, adapter, _ = app_fixture(False)
    clock = [1000.0]
    reads = []
    for method in (
        "get_state",
        "get_sysinfo",
        "get_healthz",
        "get_app_metrics",
        "get_bus_health",
        "get_vision_snap_info",
        "get_vision_obstacle",
    ):
        setattr(adapter, method, AsyncMock())

    async def refresh(app, key, fetch, **kwargs):
        if key == "healthz":
            reads.append(clock[0])
            raise RuntimeError("cache_write_failed")
        return {}

    async def sleep(delay):
        clock[0] += delay
        if clock[0] > 1006:
            raise asyncio.CancelledError

    monkeypatch.setattr(background_sync, "refresh_snapshot", refresh)
    monkeypatch.setattr(background_sync.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(background_sync.asyncio, "sleep", sleep)
    with pytest.raises(asyncio.CancelledError):
        await background_sync.sync_data_periodically(app)
    assert reads == [1000, 1005]
