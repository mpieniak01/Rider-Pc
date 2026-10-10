"""New panel mappings against fake REST only; no hardware or external IO."""

import time
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from pc_client.api.server import create_app
from pc_client.cache import CacheManager
from pc_client.config import Settings


@pytest.fixture
def panel_client():
    app = create_app(Settings(test_mode=True), CacheManager())
    with TestClient(app) as client:
        yield client


def envelope(client):
    safety = client.get("/api/control/state").json()["safety"]
    return {
        "request_id": "panel-fixture",
        "source": "manual",
        "generation": safety["generation"],
        "seq": safety["last_seq"] + 1,
        "ts": time.time(),
        "ttl_ms": 500,
    }


def prepare(client):
    body = {
        **envelope(client),
        "action": "arm",
        "owner": "manual",
        "lease_s": 10,
        "operator_plan": "Isolated fake fixture only.",
        "operator_consent": True,
    }
    assert client.post("/api/safety", json=body).status_code == 200


def test_canonical_move_is_forwarded_without_restamping(panel_client):
    client = panel_client
    prepare(client)
    adapter = client.app.state.rest_adapter
    adapter.post_control = AsyncMock(return_value={"ok": True, "pending": True, "_http_status": 202})
    body = {**envelope(client), "action": "move", "vx": 0.1, "yaw": 0, "duration": 0.1}
    response = client.post("/api/control", json=body)
    assert response.status_code == 202
    assert adapter.post_control.await_args.args[0] == body


def test_canonical_stop_works_with_offline_gate(panel_client):
    client = panel_client
    adapter = client.app.state.rest_adapter
    adapter.get_control_state = AsyncMock(side_effect=AssertionError("STOP must not read gate"))
    adapter.post_control = AsyncMock(return_value={"ok": True, "pending": True, "_http_status": 202})
    response = client.post("/api/control", json={"action": "stop", "request_id": "stop"})
    assert response.status_code == 202
    adapter.get_control_state.assert_not_awaited()


def test_navigator_status_is_real_proxy_not_local_functional_fallback(panel_client):
    adapter = panel_client.app.state.rest_adapter
    adapter.get_navigator_status = AsyncMock(return_value={"navigator": {"state": "partial"}, "observed_at": 123})
    result = panel_client.get("/api/navigator/status").json()
    assert result["navigator"]["state"] == "partial"
    adapter.get_navigator_status = AsyncMock(return_value={"error": "offline"})
    result = panel_client.get("/api/navigator/status").json()
    assert result["offline"] and result["stale"]
    assert result["navigator"]["state"] == "partial"  # retained observation


def test_navigation_config_requires_known_disarmed_snapshot(panel_client):
    adapter = panel_client.app.state.rest_adapter
    adapter.post_navigator_config = AsyncMock(return_value={"ok": True})
    assert panel_client.post("/api/navigator/config", json={"strategy": "STOP"}).status_code == 200
    prepare(panel_client)
    assert panel_client.post("/api/navigator/config", json={"strategy": "STOP"}).status_code == 409
    assert adapter.post_navigator_config.await_count == 1


def test_merged_service_version_does_not_upgrade_legacy_pi_rows(panel_client):
    adapter = panel_client.app.state.rest_adapter
    adapter.get_services = AsyncMock(return_value={"services": [{"unit": "legacy.service", "active": "active"}]})
    result = panel_client.get("/svc").json()
    assert result["contract_version"] == 2 and result["source"] == "pc_aggregator"
    row = next(r for r in result["services"] if r["host"] == "pi")
    assert row["contract_version"] is None and "can_move" not in row


@pytest.mark.parametrize("path", ["/devices", "/api/navigator/status", "/web/assets/operator/app.js"])
def test_new_panel_routes_exist(panel_client, path):
    assert panel_client.get(path).status_code == 200


def test_service_logs_require_host_and_matching_inventory(panel_client):
    client = panel_client
    assert client.get("/api/services/not-in-inventory.service/logs?host=pi").status_code == 404
    assert client.get("/api/services/not-in-inventory.service/logs?host=pc").status_code == 404
    assert client.get("/api/services/pc_client.service/logs").status_code == 422
    response = client.get("/api/services/pc_client.service/logs?host=pc")
    assert response.status_code == 200
    assert response.json()["source"] == "demo" and response.json()["simulated"] is True
    assert response.headers["Cache-Control"] == "no-store"


def test_remote_logs_keep_pi_provenance_without_local_fallback(panel_client):
    client = panel_client
    adapter = client.app.state.rest_adapter
    adapter.get_services = AsyncMock(return_value={"services": [{"unit": "test.service", "active": "inactive"}]})
    adapter.get_service_logs = AsyncMock(
        return_value={"ok": True, "source": "pi/systemd/journal", "observed_at": 123, "lines": ["source event"]}
    )
    result = client.get("/api/services/test.service/logs?host=pi").json()
    assert result["source"] == "pi/systemd/journal" and result["host"] == "pi"
    assert result["observed_at"] == 123 and result["lines"] == ["source event"]
    adapter.get_service_logs = AsyncMock(side_effect=RuntimeError("pi_offline"))
    response = client.get("/api/services/test.service/logs?host=pi")
    assert response.status_code == 503 and response.json()["observed_at"] is None


def test_local_log_reader_is_bounded_and_configured_only():
    from pc_client.core.service_logs import MAX_BYTES, MAX_LINES, read_logs

    calls = []

    def runner(command):
        calls.append(command)
        return {"returncode": 0, "stdout": "event\n" * 100, "stderr": "", "timeout": False, "truncated": True}

    assert read_logs("--all", catalog=["safe.service"], runner=runner)["ok"] is False
    assert not calls
    result = read_logs("safe.service", catalog=["safe.service"], runner=runner)
    assert result["ok"] is True and result["truncated"] is True
    assert len(result["lines"]) == MAX_LINES and MAX_BYTES == 65536
    assert calls[0][-1] == "safe.service" and "sudo" not in calls[0]
    failed = read_logs("safe.service", catalog=["safe.service"], runner=lambda _: {"timeout": True})
    assert failed["ok"] is False and failed["error"] == "journal_timeout"


@pytest.mark.parametrize("server_time", [None, "bad", float("nan"), float("inf"), False])
def test_navigation_config_requires_remote_clock_without_local_fallback(panel_client, server_time):
    adapter = panel_client.app.state.rest_adapter
    snapshot = {"safety": {"contract_version": 1, "state": "DISARMED", "observed_at": time.time()}}
    # NaN/Infinity cannot be transported as JSON; use the private cache path
    # by stubbing the snapshot helper, never a real clock/network peer.
    from unittest.mock import patch

    with patch(
        "pc_client.api.routers.control_router._remote_snapshot",
        AsyncMock(return_value={**snapshot, "server_time": server_time}),
    ):
        adapter.post_navigator_config = AsyncMock()
        assert panel_client.post("/api/navigator/config", json={"strategy": "STOP"}).status_code == 409
        adapter.post_navigator_config.assert_not_awaited()


def test_navigation_config_accepts_only_fresh_remote_clock_despite_pc_skew(panel_client):
    adapter = panel_client.app.state.rest_adapter
    snapshot = {"safety": {"contract_version": 1, "state": "DISARMED", "observed_at": 123.0}, "server_time": 124.0}
    from unittest.mock import patch

    with patch("pc_client.api.routers.control_router._remote_snapshot", AsyncMock(return_value=snapshot)):
        adapter.post_navigator_config = AsyncMock(return_value={"ok": True})
        assert panel_client.post("/api/navigator/config", json={"strategy": "STOP"}).status_code == 200
        assert adapter.post_navigator_config.await_args.args[0] == {"strategy": "STOP"}


def test_actual_text_and_partial_voice_inventory_are_truthful(panel_client):
    from types import SimpleNamespace

    text = SimpleNamespace(
        shutdown=AsyncMock(), get_telemetry=lambda: {"initialized": True, "ready": True, "mode": "real", "source": "pc"}
    )
    voice = SimpleNamespace(
        shutdown=AsyncMock(),
        _initialized=True,
        get_telemetry=lambda: {
            "initialized": True,
            "ready": False,
            "mode": "real",
            "source": "pc",
            "error": "asr_unavailable",
            "capabilities": {"asr": {"ready": False}, "tts": {"ready": True}},
        },
    )
    panel_client.app.state.providers = {"voice": voice}
    panel_client.app.state.text_provider = text
    rows = {
        row["unit"]: row
        for row in panel_client.get("/svc").json()["services"]
        if row.get("kind") == "application_provider"
    }
    assert rows["text.provider"]["ready"] is True
    assert rows["text.provider"]["provider_source"] == "pc"
    assert rows["voice.provider"]["initialized"] is True
    assert rows["voice.provider"]["ready"] is False
    assert rows["voice.provider"]["capabilities"]["tts"]["ready"] is True
    graph = panel_client.get("/api/services/graph").json()
    assert any(row.get("unit") == "text.provider" for row in graph["nodes"])


@pytest.mark.asyncio
async def test_demo_catalog_navigation_identity_matches_canonical_api():
    from pc_client.adapters.mock_rest_adapter import MockRestAdapter

    adapter = MockRestAdapter()
    catalog = await adapter.get_logic_catalog()
    names = {row["name"] for row in catalog["features"]}
    assert "s9_navigation" in names and "s4_recon" not in names
    result = await adapter.post_feature_toggle("s9_navigation", {"enabled": True})
    assert result["ok"] is True
    state = await adapter.get_navigator_status()
    assert state["navigator"]["active"] is True
    assert (await adapter.post_feature_toggle("s4_recon", {"enabled": True}))["ok"] is False


def test_navigation_history_container_exists():
    from pathlib import Path

    document = (Path(__file__).resolve().parents[2] / "web/navigation.html").read_text()
    assert 'id="nav-request-history"' in document


def test_navigation_api_starts_canonical_demo_task_only_after_explicit_navigation_arm(panel_client):
    body = {
        **envelope(panel_client),
        "action": "arm",
        "owner": "navigation",
        "lease_s": 10,
        "operator_plan": "Isolated navigation fake only.",
        "operator_consent": True,
    }
    assert panel_client.post("/api/safety", json=body).status_code == 200
    assert panel_client.post("/api/navigator/start", json=envelope(panel_client)).status_code == 200
    catalog = panel_client.get("/api/logic/catalog").json()
    task = next(row for row in catalog["features"] if row["name"] == "s9_navigation")
    assert task["requested"] is True
    assert task["source"] == "demo"
