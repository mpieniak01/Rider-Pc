"""Odczyty tylko z fake adaptera: pojedynczy cache i zachowana tożsamość źródła."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pc_client.api.telemetry_snapshot import refresh_snapshot
from pc_client.api.routers.status_router import router
from pc_client.cache import CacheManager
from pc_client.core.service_manager import ServiceManager


@pytest.mark.asyncio
async def test_parallel_reads_share_source_fetch_and_reuse_only_half_second(monkeypatch, tmp_path):
    now = [1002.0]
    monkeypatch.setattr("pc_client.api.telemetry_snapshot.time.time", lambda: now[0])
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def fetch():
        calls.append(True)
        entered.set()
        await release.wait()
        return {
            "devices": {"xgo": {"observed_at": 1001.8}},
            "observed_at": None,
            "generated_at": 1001.9,
            "server_time": 1001.9,
        }

    app = SimpleNamespace(state=SimpleNamespace(cache=CacheManager(str(tmp_path / "cache.db")), rest_adapter=object()))
    first = asyncio.create_task(refresh_snapshot(app, "state", fetch, reuse_s=0.5))
    await entered.wait()
    second = asyncio.create_task(refresh_snapshot(app, "state", fetch, reuse_s=0.5))
    await asyncio.sleep(0)
    release.set()
    rows = await asyncio.gather(first, second)
    assert len(calls) == 1 and rows[0] == rows[1]
    assert rows[0]["devices"]["xgo"]["observed_at"] == 1001.8
    assert rows[0]["observed_at"] is None and rows[0]["generated_at"] == rows[0]["server_time"] == 1001.9
    now[0] += 0.49
    assert (await refresh_snapshot(app, "state", fetch, reuse_s=0.5))["received_at"] == 1002.0
    assert len(calls) == 1
    now[0] += 0.02
    await refresh_snapshot(app, "state", fetch, reuse_s=0.5)
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_failed_refresh_keeps_source_times_and_invalidates_outer_transport(monkeypatch, tmp_path):
    monkeypatch.setattr("pc_client.api.telemetry_snapshot.time.time", lambda: 1002.0)
    cache = CacheManager(str(tmp_path / "cache.db"))
    cache.set("state", {"received_at": 1000, "devices": {"xgo": {"observed_at": 999.8}}})
    app = SimpleNamespace(state=SimpleNamespace(cache=cache, rest_adapter=object()))
    fetch = AsyncMock(side_effect=RuntimeError("fixture_offline"))
    row = await refresh_snapshot(app, "state", fetch, reuse_s=0.5)
    assert row["offline"] and row["stale"] and row["error"] == "fixture_offline"
    assert row["devices"]["xgo"]["observed_at"] == 999.8 and row["received_at"] == 1000
    assert row["attempted_at"] == 1002
    await refresh_snapshot(app, "state", fetch, reuse_s=0.5)
    assert fetch.await_count == 1


@pytest.mark.parametrize("path,method", [("/state", "get_state"), ("/vision/snap-info", "get_vision_snap_info")])
def test_state_get_acquires_current_source_without_mutation_or_background_cache(path, method, tmp_path):
    app = FastAPI()
    app.include_router(router)
    app.state.cache = CacheManager(str(tmp_path / "cache.db"))
    app.state.control_state = {}
    adapter = SimpleNamespace(
        get_state=AsyncMock(
            return_value={
                "observed_at": 100,
                "devices": {"xgo": {"sensor_quality": {"sensors": {"battery": {"value": 1, "unit": "ratio"}}}}},
            }
        )
    )
    setattr(adapter, method, adapter.get_state)
    app.state.rest_adapter = adapter
    with TestClient(app) as client:
        row = client.get(path).json()
        assert client.get(path).json() == row
    assert adapter.get_state.await_count == 1
    assert row["observed_at"] == 100 and row["devices"]["xgo"]["sensor_quality"]["sensors"]["battery"]["value"] == 1


@pytest.mark.asyncio
async def test_service_hosts_preserve_pi_source_age_and_failure_not_receipt(monkeypatch):
    monkeypatch.setattr("pc_client.core.service_manager.time.time", lambda: 1002.0)
    meta = {"envelope_version": 1, "contract_id": "rider.services", "observed_at": 999.8}
    adapter = SimpleNamespace(
        get_services=AsyncMock(
            return_value={
                "observed_at": 999.8,
                "contract_version": 2,
                "contract_meta": meta,
                "services": [{"unit": "real.service", "observed_at": 999.7}],
            }
        )
    )
    manager = ServiceManager(rest_adapter=adapter)
    row = await manager.get_all_services()
    assert row["observed_at"] is None
    assert row["hosts"]["pi"]["observed_at"] == 999.8
    assert row["hosts"]["pi"]["received_at"] == 1002.0
    assert row["hosts"]["pi"]["contract_meta"] == meta
    adapter.get_services.side_effect = RuntimeError("fixture_offline")
    row = await manager.get_all_services()
    assert row["hosts"]["pi"]["observed_at"] == 999.8 and row["hosts"]["pi"]["offline"]


@pytest.mark.asyncio
@pytest.mark.parametrize("explicit_unknown", [True, False])
async def test_unknown_host_batch_time_does_not_erase_independent_member_age(explicit_unknown):
    payload = {"contract_version": 2, "services": [{"unit": "real.service", "observed_at": 999.7}]}
    if explicit_unknown:
        payload["observed_at"] = None
    manager = ServiceManager(rest_adapter=SimpleNamespace(get_services=AsyncMock(return_value=payload)))
    row = (await manager.get_all_services())["hosts"]["pi"]
    assert row["observed_at"] == (None if explicit_unknown else 999.7)
    assert row["oldest_member_observed_at"] == 999.7
    assert row["observed_at_basis"] == ("source" if explicit_unknown else "min_member")


@pytest.mark.parametrize(
    "failure",
    [
        {"offline": True},
        {"stale": True},
        {"error": "REST timeout"},
        {"data_ready": False},
        {"quality": "unknown"},
        {"observed_at": None},
    ],
)
def test_healthy_bus_observation_survives_newer_failed_rest_attempt(failure):
    from pc_client.api.telemetry_snapshot import latest_observation

    bus = {"observed_at": 1000, "received_at": 1040, "present": False, "confidence": 0, "source": "camera/roi"}
    rest = {"observed_at": 999, "received_at": 1039, "attempted_at": 1041, **failure}
    for candidates in [(bus, rest), (rest, bus)]:
        result = latest_observation(*candidates)
        assert result["observed_at"] == 1000
        assert result["present"] is False
        assert result["confidence"] == 0
        assert result["received_at"] == 1040
        assert result["upstream_source"] == "camera/roi"
        assert not result.get("offline")
    assert bus["source"] == "camera/roi"
    assert "stale" not in bus


def test_latest_observation_chooses_newest_healthy_source_or_failure_if_none_valid():
    from pc_client.api.telemetry_snapshot import latest_observation

    healthy = latest_observation({"observed_at": 1001, "received_at": 1039}, {"observed_at": 1000, "received_at": 1040})
    assert healthy["observed_at"] == 1001
    failure = latest_observation(
        {"observed_at": 1000, "received_at": 1039, "stale": True},
        {"observed_at": None, "attempted_at": 1041, "offline": True},
    )
    assert failure["offline"] is True and failure["observed_at"] is None


def test_python39_function_annotations_are_postponed():
    from pc_client.api.telemetry_snapshot import _time

    assert isinstance(_time.__annotations__["return"], str)
