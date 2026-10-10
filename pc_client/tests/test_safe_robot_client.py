"""Regresje kontraktu Pi bez sieci, BUS ani sprzętu."""

import copy
import socket
import subprocess
import time
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from pc_client.adapters.mock_rest_adapter import MockRestAdapter
from pc_client.api.server import create_app
from pc_client.cache import CacheManager
from pc_client.config import Settings
from pc_client.core.remote_safety import RemoteSafety, SafetyRefusal
from pc_client.core.service_manager import ServiceManager
from pc_client.core.watchdog import ServiceWatchdog


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        test_mode=False,
        disable_rider_pi_adapter=True,
        enable_providers=False,
        enable_task_queue=False,
        auto_heal_enabled=False,
    )
    app = create_app(settings, CacheManager(db_path=str(tmp_path / "cache.db")))

    @asynccontextmanager
    async def no_connections(_app):
        yield

    app.router.lifespan_context = no_connections
    adapter = MockRestAdapter()
    adapter.post_control = AsyncMock(wraps=adapter.post_control)
    adapter.post_feature_toggle = AsyncMock(wraps=adapter.post_feature_toggle)
    adapter.post_tracking_mode = AsyncMock(wraps=adapter.post_tracking_mode)
    app.state.rest_adapter = adapter
    with TestClient(app) as result:
        result.adapter = adapter
        result.app_instance = app
        yield result


def operator_payload(client, body):
    snapshot = client.get("/api/control/state").json()["safety"]
    return {
        **body,
        "generation": snapshot.get("generation"),
        "seq": snapshot.get("last_seq", 0) + 1,
        "source": "manual",
        "ts": time.time(),
        "ttl_ms": 500,
    }


def arm(client, owner="manual"):
    response = client.post(
        "/api/safety",
        json=operator_payload(
            client,
            {
                "action": "arm",
                "owner": owner,
                "operator_consent": True,
                "operator_plan": "Izolowana atrapa; bez połączenia z robotem",
                "lease_s": 10,
            },
        ),
    )
    assert response.status_code == 200


@pytest.mark.parametrize("cmd", ["move", "spin", "height", "balance", "action"])
def test_disarmed_blocks_every_actuator(client, cmd):
    response = client.post("/api/control", json=operator_payload(client, {"cmd": cmd, "vx": 0.1}))
    assert response.status_code == 409
    client.adapter.post_control.assert_not_called()


@pytest.mark.parametrize(
    "field,value",
    [
        ("contract_version", 0),
        ("state", "UNKNOWN"),
        ("state", "ESTOP"),
        ("ready", False),
        ("ready", "true"),
        ("can_move", False),
        ("can_move", "true"),
        ("read_only", True),
        ("generation", None),
        ("observed_at", 0),
        ("observed_at", "now"),
        ("observed_at", float("inf")),
        ("observed_at", time.time() + 60),
    ],
)
@pytest.mark.asyncio
async def test_safety_fails_closed_on_unknown_or_stale(field, value):
    safety = {
        "contract_version": 1,
        "state": "ARMED",
        "ready": True,
        "can_move": True,
        "read_only": False,
        "owner": "manual",
        "generation": "operator-issued",
        "observed_at": time.time(),
        "last_seq": 0,
    }
    safety[field] = value
    adapter = type("Fake", (), {"get_control_state": AsyncMock(return_value={"safety": safety})})()
    with pytest.raises(SafetyRefusal):
        await RemoteSafety().command_context(
            adapter,
            "manual",
            supplied={"generation": "operator-issued", "seq": 1, "source": "manual", "ts": time.time(), "ttl_ms": 500},
        )


def test_control_uses_issued_generation_and_increasing_sequence(client):
    arm(client)
    first = client.post("/api/control", json=operator_payload(client, {"cmd": "move", "vx": 0.1}))
    second = client.post("/api/control", json=operator_payload(client, {"cmd": "height", "height": 4}))
    assert first.status_code == second.status_code == 200
    a, b = [c.args[0] for c in client.adapter.post_control.call_args_list]
    assert a["generation"] == b["generation"] == client.adapter._safety["generation"]
    assert a["seq"] < b["seq"]
    assert a["source"] == "manual"
    assert abs(a["ts"] - time.time()) < 3


def test_stop_is_forwarded_without_safety_read_and_disarms(client):
    client.adapter.get_control_state = AsyncMock(side_effect=RuntimeError("state unavailable"))
    response = client.post("/api/control", json={"cmd": "stop"})
    assert response.status_code == 200
    client.adapter.post_control.assert_called_once()
    client.adapter.get_control_state.assert_not_called()
    assert client.adapter._safety["state"] == "DISARMED"


def test_pending_ack_and_refusal_metadata_are_preserved(client):
    arm(client)
    client.adapter.post_control = AsyncMock(
        return_value={
            "ok": True,
            "confirmed": False,
            "pending": True,
            "request_id": "r1",
            "physical_completion": "unverified",
            "_http_status": 202,
        }
    )
    response = client.post("/api/control", json=operator_payload(client, {"cmd": "move", "vx": 0.1}))
    assert response.status_code == 202
    assert response.json()["physical_completion"] == "unverified"
    client.adapter.post_control.return_value = {"ok": False, "error": "lease_expired", "_http_status": 409}
    assert client.post("/api/control", json=operator_payload(client, {"cmd": "move", "vx": 0.1})).status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"action": "arm"},
        {"action": "arm", "operator_consent": "true", "operator_plan": "attempt"},
        {"action": "clear_estop", "operator_consent": True, "operator_plan": " "},
    ],
)
def test_arm_clear_require_explicit_operator_plan(client, payload):
    client.adapter.post_safety = AsyncMock()
    assert client.post("/api/safety", json=payload).status_code == 400
    client.adapter.post_safety.assert_not_called()


def test_owner_mismatch_blocks_follow_me(client):
    arm(client, "manual")
    response = client.post("/api/logic/feature/s3_follow_me_face", json=operator_payload(client, {"enabled": True}))
    assert response.status_code == 409
    client.adapter.post_feature_toggle.assert_not_called()
    arm(client, "follow_me")
    assert (
        client.post(
            "/api/logic/feature/s3_follow_me_face", json=operator_payload(client, {"enabled": True})
        ).status_code
        == 200
    )


def test_non_moving_task_can_start_disarmed_only_with_confirmed_catalog(client):
    assert (
        client.post("/api/logic/feature/s0_manual", json=operator_payload(client, {"enabled": True})).status_code == 200
    )
    client.adapter.get_logic_features = AsyncMock(return_value={"features": [{"name": "s0_manual", "can_move": False}]})
    assert client.post("/api/logic/feature/s0_manual", json={"enabled": True}).status_code == 409


def test_bool_payload_is_strict_and_stop_does_not_require_catalog(client):
    assert client.post("/api/logic/feature/recon", json={"enabled": "false"}).status_code == 400
    client.adapter.get_logic_features = AsyncMock(side_effect=RuntimeError("offline"))
    assert client.post("/api/logic/feature/s9_navigation", json={"enabled": False}).status_code == 200


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/api/control", {"cmd": "move", "vx": 0.1}),
        ("/api/navigator/start", {}),
        ("/api/navigator/return_home", {}),
        ("/api/logic/feature/recon", {"enabled": True}),
        ("/api/vision/tracking/mode", {"mode": "face", "enabled": True}),
        ("/api/resource/camera", {"action": "release"}),
    ],
)
def test_no_local_success_without_robot(client, path, payload):
    client.app_instance.state.rest_adapter = None
    response = client.post(path, json=payload)
    assert response.status_code in {409, 503}
    assert response.json().get("ok") is not True


def test_no_local_catalog_or_green_control_fallback(client):
    real = client.get("/api/logic/features").json()
    client.adapter.get_logic_features = AsyncMock(return_value={"error": "network down"})
    failed = client.get("/api/logic/features").json()
    assert failed["features"] == real["features"]
    assert failed["source"] == real["source"] and failed["stale"] and failed["offline"]
    assert failed["observed_at"] == real["observed_at"]
    client.adapter.get_control_state = AsyncMock(return_value={"tracking": {"enabled": True}})
    legacy = client.get("/api/control/state").json()
    assert legacy["safety"]["state"] == "UNKNOWN" and not legacy["safety"]["can_move"]
    client.app_instance.state.rest_adapter = None
    assert client.get("/api/control/state").json()["safety"]["state"] == "UNKNOWN"
    resource = client.get("/api/resource/camera").json()
    assert resource["free"] is None and resource["offline"]


class FakeSystemd:
    available = True

    def __init__(self, active="active"):
        self.active = active
        self.calls = []

    async def get_unit_details(self, unit):
        return {"active": self.active, "sub": "running", "load": "loaded", "installed": True, "enabled": "disabled"}

    async def manage_service(self, unit, action):
        self.calls.append((unit, action))
        if action == "stop":
            self.active = "failed"  # Nawet nieudany stop nie uruchamia auto-heal.
        return {"ok": True}


@pytest.mark.asyncio
async def test_production_empty_configuration_is_not_demo():
    manager = ServiceManager()
    assert await manager.get_local_services_async() == []
    data = await manager.get_all_services()
    assert data["services"] == [] and data["hosts"]["pi"]["offline"]
    demo = ServiceManager(mock_mode=True)
    assert all(s["source"] == "demo" for s in await demo.get_local_services_async())


@pytest.mark.asyncio
async def test_host_identity_and_ambiguous_route():
    systemd = FakeSystemd()
    adapter = type(
        "Rest",
        (),
        {
            "get_services": AsyncMock(
                return_value={
                    "contract_version": 2,
                    "services": [{"unit": "same.service", "active": "active", "can_move": False}],
                }
            ),
            "service_action": AsyncMock(return_value={"ok": True}),
        },
    )()
    manager = ServiceManager(adapter, systemd, ["same.service"], non_actuating_services=["same.service"])
    result = await manager.get_all_services()
    assert {s["identity"] for s in result["services"]} == {"pc:same.service", "pi:same.service"}
    assert not (await manager.control_service("same.service", "start"))["ok"]
    assert (await manager.control_service("same.service", "start", host="pc"))["ok"]
    assert (await manager.control_service("same.service", "start", host="pi"))["ok"]
    assert systemd.calls == [("same.service", "start")]
    adapter.service_action.assert_called_once()


@pytest.mark.asyncio
async def test_remote_inventory_stays_unknown_after_connection_loss():
    adapter = type(
        "Rest",
        (),
        {"get_services": AsyncMock(return_value={"services": [{"unit": "known.service", "active": "active"}]})},
    )()
    manager = ServiceManager(adapter)
    first = await manager.get_all_services()
    adapter.get_services.return_value = {"error": "offline"}
    offline = await manager.get_all_services()
    row = offline["services"][0]
    assert row["identity"] == first["services"][0]["identity"]
    assert row["observed_at"] == first["services"][0]["observed_at"]
    assert row["stale"] and row["offline"] and row["active"] == "unknown"
    assert (await manager.get_service_graph())["nodes"][0]["status"] == "unknown"


@pytest.mark.asyncio
async def test_provider_does_not_appear_as_systemd_or_accept_systemctl():
    manager = ServiceManager()
    manager.set_providers({"voice": object()})
    row = (await manager.get_all_services())["services"][0]
    assert row["kind"] == "application_provider" and row["source"] == "application"
    assert row["actions"] == [] and row["enabled"] == "not-applicable"
    assert not (await manager.control_service("voice.provider", "restart", host="pc"))["ok"]


@pytest.mark.asyncio
async def test_watchdog_same_config_never_revives_operator_stop():
    systemd = FakeSystemd()
    manager = ServiceManager(
        systemd_adapter=systemd, monitored_services=["safe.service"], non_actuating_services=["safe.service"]
    )
    await manager.get_local_services_async()
    watchdog = ServiceWatchdog(manager)
    assert watchdog._monitored_services == manager.monitored_services
    systemd.active = "failed"
    await watchdog._check_and_heal_services()
    assert systemd.calls == [("safe.service", "restart")]
    await manager.control_service("safe.service", "stop", host="pc")
    await watchdog._check_and_heal_services()
    assert systemd.calls == [("safe.service", "restart"), ("safe.service", "stop")]


@pytest.mark.asyncio
async def test_watchdog_never_auto_starts_initially_failed_or_unknown_capability():
    systemd = FakeSystemd("failed")
    manager = ServiceManager(
        systemd_adapter=systemd, monitored_services=["safe.service"], non_actuating_services=["safe.service"]
    )
    await ServiceWatchdog(manager)._check_and_heal_services()
    assert systemd.calls == []
    systemd.active = "active"
    unsafe = ServiceManager(systemd_adapter=systemd, monitored_services=["motion.service"])
    await unsafe.get_local_services_async()
    systemd.active = "failed"
    await ServiceWatchdog(unsafe)._check_and_heal_services()
    assert systemd.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["start", "restart", "enable"])
async def test_legacy_service_unknown_capability_never_starts(action):
    adapter = type(
        "Rest",
        (),
        {
            "get_services": AsyncMock(return_value={"services": [{"unit": "legacy.service", "active": "inactive"}]}),
            "service_action": AsyncMock(),
        },
    )()
    result = await ServiceManager(adapter).control_service("legacy.service", action, host="pi")
    assert not result["ok"]
    adapter.service_action.assert_not_called()


def test_system_cards_have_no_mutation_handlers():
    html = (Path(__file__).resolve().parents[2] / "web/system.html").read_text()
    assert "toggleService(" not in html
    assert "role', 'button'" not in html
    assert "method: 'POST'" not in html


def test_test_isolation_blocks_network_bus_device_and_ssh(tmp_path):
    with socket.socket() as sock, pytest.raises(PermissionError, match="isolation"):
        sock.connect(("192.168.1.14", 8080))
    with pytest.raises(PermissionError, match="isolation"):
        open("/dev/ttyAMA0")
    with pytest.raises(PermissionError, match="isolation"):
        subprocess.Popen(["ssh", "robot", "true"])
    import zmq

    context = zmq.Context()
    sock = context.socket(zmq.PUB)
    try:
        with pytest.raises(PermissionError, match="isolation"):
            sock.connect("tcp://127.0.0.1:5555")
    finally:
        sock.close()
        context.term()


@pytest.mark.parametrize(
    "mutation",
    [
        {"generation": "old-lease"},
        {"seq": True},
        {"seq": -1},
        {"ts": 0},
        {"ts": float("inf")},
        {"ts": float("nan")},
        {"ttl_ms": 501},
        {"ttl_ms": True},
        {"source": "follow_me"},
        {"ts": "now"},
        {"ttl_ms": 0},
    ],
)
@pytest.mark.asyncio
async def test_operator_envelope_is_never_restamped(mutation):
    adapter = MockRestAdapter()
    adapter._safety.update(state="ARMED", ready=True, can_move=True, owner="manual")
    snapshot = (await adapter.get_control_state())["safety"]
    body = {"generation": snapshot["generation"], "seq": 1, "source": "manual", "ts": time.time(), "ttl_ms": 500}
    body.update(mutation)
    before = copy.deepcopy(body)
    with pytest.raises(SafetyRefusal):
        await RemoteSafety().command_context(adapter, "manual", supplied=body)
    for key, value in before.items():
        if isinstance(value, float) and value != value:
            assert body[key] != body[key]
        else:
            assert body[key] == value


def test_missing_metadata_is_read_only_even_when_armed(client):
    arm(client)
    assert client.post("/api/control", json={"cmd": "move", "vx": 0.1}).status_code == 409
    client.adapter.post_control.assert_not_called()
    assert (
        client.post(
            "/api/safety",
            json={"action": "arm", "owner": "manual", "operator_consent": True, "operator_plan": "Explicit mock plan"},
        ).status_code
        == 409
    )


def test_move_and_arm_from_old_generation_never_survive_stop(client):
    arm(client)
    stale_move = operator_payload(client, {"cmd": "move", "vx": 0.1})
    stale_arm = operator_payload(
        client, {"action": "arm", "owner": "manual", "operator_consent": True, "operator_plan": "Old mock trial"}
    )
    assert client.post("/api/control", json={"cmd": "stop"}).status_code == 200
    arm(client)
    assert client.post("/api/control", json=stale_move).status_code == 409
    assert client.post("/api/safety", json=stale_arm).status_code == 409
    assert client.adapter.post_control.call_count == 1  # Wyłącznie STOP.


def test_unavailable_or_server_stale_task_never_starts(client):
    for meta in ({"installed": False}, {"stale": True}):
        client.adapter.get_logic_features = AsyncMock(
            return_value={"contract_version": 2, "features": [{"name": "camera", "can_move": False, **meta}]}
        )
        assert client.post("/api/logic/feature/camera", json={"enabled": True}).status_code == 409
    client.adapter.post_feature_toggle.assert_not_called()


def test_provider_failure_is_explicit_and_cannot_simulate_configuration(client):
    current = client.get("/api/providers/state").json()
    client.adapter.get_providers_state = AsyncMock(return_value={"error": "offline"})
    failed = client.get("/api/providers/state").json()
    assert failed["stale"] and failed["offline"]
    assert failed["observed_at"] == current["observed_at"]
    client.app_instance.state.rest_adapter = None
    assert client.patch("/api/providers/voice", json={"target": "pc"}).status_code == 503


def test_no_camera_route_shadowing(client):
    paths = [r.path for r in client.app_instance.routes if "GET" in (getattr(r, "methods", []) or [])]
    assert paths.count("/api/resource/camera") == 1
    client.app_instance.state.rest_adapter = None
    assert client.get("/api/resource/camera").json()["free"] is None


def test_pending_service_action_keeps_status_without_success_event(client):
    client.adapter.service_action = AsyncMock(
        return_value={
            "ok": True,
            "pending": True,
            "confirmed": False,
            "request_id": "test-pending",
            "_http_status": 202,
        }
    )
    response = client.post("/svc/rider-motion.service", json={"action": "stop", "host": "pi"})
    assert response.status_code == 202
    assert response.json()["pending"] and response.json()["confirmed"] is False
    assert "_http_status" not in response.json()


def test_ai_mode_refusal_cannot_be_optimistic_success(client):
    client.adapter.set_ai_mode = AsyncMock(return_value={"ok": False, "reason": "unavailable"})
    assert client.put("/api/system/ai-mode", json={"mode": "pc_offload"}).status_code == 502


@pytest.mark.asyncio
async def test_pi_graph_dependency_units_and_aliases_have_one_host_identity():
    adapter = MockRestAdapter()
    adapter.get_services = AsyncMock(
        return_value={
            "contract_version": 2,
            "services": [
                {
                    "id": "camera",
                    "unit": "camera.service",
                    "active_state": "active",
                    "dependencies": ["worker.service"],
                    "edges_out": ["worker"],
                },
                {"id": "worker", "unit": "worker.service", "active": "active"},
            ],
        }
    )
    graph = await ServiceManager(rest_adapter=adapter).get_service_graph()
    assert graph["nodes"][0]["active"] == "active"
    assert graph["edges"] == [{"from": "pi:camera.service", "to": "pi:worker.service"}]


def test_stale_observation_cannot_start_even_nonmoving_task(client):
    client.adapter.get_logic_features = AsyncMock(
        return_value={
            "contract_version": 2,
            "observed_at": time.time() - 4,
            "features": [{"name": "camera", "can_move": False}],
        }
    )
    assert client.post("/api/logic/feature/camera", json={"enabled": True}).status_code == 409
    client.adapter.post_feature_toggle.assert_not_called()


@pytest.mark.asyncio
async def test_remote_moving_service_requires_known_owner():
    adapter = MockRestAdapter()
    adapter.get_services = AsyncMock(
        return_value={"contract_version": 2, "services": [{"unit": "actuator.service", "can_move": True}]}
    )
    adapter.service_action = AsyncMock()
    result = await ServiceManager(rest_adapter=adapter).control_service("actuator.service", "start", host="pi")
    assert result["ok"] is False and result["error"] == "unknown_motion_owner"
    adapter.service_action.assert_not_called()


@pytest.mark.asyncio
async def test_boolean_safety_version_is_not_supported_contract():
    adapter = MockRestAdapter()
    adapter._safety.update(state="ARMED", ready=True, can_move=True, owner="manual", contract_version=True)
    body = {"generation": adapter._safety["generation"], "seq": 1, "source": "manual", "ts": time.time(), "ttl_ms": 500}
    with pytest.raises(SafetyRefusal, match="unconfirmed_safety"):
        await RemoteSafety().command_context(adapter, "manual", supplied=body)


def test_os_open_cannot_bypass_hardware_guard():
    import os

    with pytest.raises(PermissionError, match="isolation"):
        os.open("/dev/ttyAMA0", os.O_RDWR)


@pytest.mark.parametrize("state,action", [("DISARMED", "arm"), ("ESTOP", "clear_estop")])
def test_explicit_consent_accepts_known_disarmed_read_only_snapshot(client, state, action):
    client.adapter._safety.update(state=state, read_only=True, ready=False, can_move=False)
    response = client.post(
        "/api/safety",
        json=operator_payload(
            client,
            {
                "action": action,
                "operator_consent": True,
                "operator_plan": "Isolated operator consent",
                "owner": "manual",
                "lease_s": 10,
            },
        ),
    )
    assert response.status_code == 200


def test_child_python_inherits_transport_and_device_guards():
    import sys

    for code in (
        "import socket; socket.socket().connect(('192.168.1.14', 8080))",
        "import os; os.open('/dev/ttyAMA0', os.O_RDWR)",
    ):
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=5)
        assert result.returncode != 0 and "Test isolation" in result.stderr


@pytest.mark.parametrize(
    "args",
    [
        ["bash", "-lc", "echo should-not-run"],
        ["env", "python3", "-S"],
        ["python3", "-S", "-c", "print('unguarded')"],
    ],
)
def test_child_process_cannot_disable_test_guard(args):
    with pytest.raises(PermissionError, match="isolation"):
        subprocess.Popen(args)


def test_robot_sdk_import_and_shell_are_forbidden():
    import importlib
    import os

    with pytest.raises(PermissionError, match="isolation"):
        importlib.import_module("xgolib")
    with pytest.raises(PermissionError, match="isolation"):
        os.system("true")


def test_initial_pi_sequence_zero_is_valid_for_explicit_arm(client):
    client.adapter._safety.update(state="DISARMED", read_only=True, last_seq=-1)
    arm(client)
    assert client.get("/api/control/state").json()["safety"]["last_seq"] == 0


@pytest.mark.asyncio
async def test_pi_time_handshake_compares_without_restamping_request():
    adapter = MockRestAdapter()
    peer_now = time.time() + 12
    snapshot = {
        "contract_version": 1,
        "state": "DISARMED",
        "read_only": True,
        "ready": False,
        "can_move": False,
        "last_seq": -1,
        "generation": "peer-generation",
        "observed_at": peer_now,
    }
    adapter.get_control_state = AsyncMock(return_value={"safety": snapshot, "server_time": peer_now})
    body = {"generation": "peer-generation", "seq": 0, "source": "manual", "ts": peer_now - 0.02, "ttl_ms": 500}
    result = await RemoteSafety().command_context(adapter, require_armed=False, supplied=body)
    assert result == body
    body["ts"] = peer_now - 1
    with pytest.raises(SafetyRefusal, match="expired"):
        await RemoteSafety().command_context(adapter, require_armed=False, supplied=body)


@pytest.mark.asyncio
async def test_inventory_envelope_stale_and_offline_remain_authoritative():
    adapter = MockRestAdapter()
    adapter.get_services = AsyncMock(
        return_value={
            "contract_version": 2,
            "stale": True,
            "offline": True,
            "services": [{"unit": "camera.service", "active": "active", "can_move": False}],
        }
    )
    adapter.service_action = AsyncMock()
    manager = ServiceManager(rest_adapter=adapter)
    observed = await manager.get_all_services()
    assert observed["services"][0]["stale"] and observed["services"][0]["offline"]
    assert observed["hosts"]["pi"]["offline"] is True
    result = await manager.control_service("camera.service", "start", host="pi")
    assert result["ok"] is False
    adapter.service_action.assert_not_called()
