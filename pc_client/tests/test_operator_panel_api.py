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
