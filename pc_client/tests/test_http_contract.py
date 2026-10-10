"""Odcięte kontrakty HTTP/BUS; żadnego urządzenia ani transportu sieciowego."""

import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from pc_client.adapters.rest_adapter import RestAdapter
from pc_client.api.lifecycle import create_zmq_handlers
from pc_client.api.routers.control_router import _proxy_action
from pc_client.api.sse_manager import SseManager
from pc_client.cache import CacheManager
from pc_client.http_contract import ACCEPT, ContractMiddleware, envelope, unpack

FIXTURE = json.loads((Path(__file__).parents[2] / "tests/fixtures/contracts/rider-v1.json").read_text())


@pytest.mark.parametrize("name", FIXTURE["cases"])
def test_golden_envelope_preserves_every_domain_field_and_source_time(name):
    body = FIXTURE["cases"][name]["body"]
    result = unpack(body)
    for key, value in body["data"].items():
        if key not in {"error", "offline", "stale"}:
            assert result[key] == value
    assert result["contract_meta"] == body["meta"]
    assert result["offline"] == (body["meta"]["offline"] or body["data"].get("offline") is True)


@pytest.mark.asyncio
async def test_adapter_negotiates_and_preserves_pending_original_command():
    requests = []
    command = {
        "action": "move",
        "request_id": "original",
        "source": "manual",
        "generation": "old",
        "seq": 4,
        "ts": 999,
        "ttl_ms": 100,
    }

    def handler(request):
        requests.append(request)
        assert request.headers["Accept"] == ACCEPT
        case = FIXTURE["cases"]["catalog" if request.method == "GET" else "pending"]
        return httpx.Response(case["status"], json=case["body"])

    adapter = RestAdapter("http://fixture.invalid")
    await adapter.client.aclose()
    adapter.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await adapter.post_control(command)
    assert [r.method for r in requests] == ["GET", "POST"]
    assert json.loads(requests[-1].content) == command
    assert result["_http_status"] == 202
    assert result["pending"] is True
    assert result["confirmed"] is False
    await adapter.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [{"features": []}, {"meta": {"envelope_version": 99}, "data": {}}])
async def test_unknown_upstream_contract_cannot_mutate(body):
    requests = []

    def handler(request):
        requests.append(request.method)
        return httpx.Response(200, json=body)

    adapter = RestAdapter("http://fixture.invalid")
    await adapter.client.aclose()
    adapter.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await adapter.patch_provider("text", {"target": "pc"})
    assert result["error"] == "unsupported_contract"
    assert requests == ["GET"]
    await adapter.close()


@pytest.mark.asyncio
async def test_provider_legacy_success_and_pending_do_not_turn_into_false_502():
    async def patch_provider(*args):
        return {"domain": "text", "state": {"mode": "local"}, "changed": True}

    async def post_control(*args):
        return {
            "ok": False,
            "pending": True,
            "_http_status": 202,
            "operation": {"status": "pending", "confirmed": False},
        }

    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                rest_adapter=SimpleNamespace(patch_provider=patch_provider, post_control=post_control)
            )
        )
    )
    assert (await _proxy_action(request, "patch_provider", "text", {})).status_code == 200
    response = await _proxy_action(request, "post_control", {})
    assert response.status_code == 202
    assert json.loads(response.body)["operation"]["confirmed"] is False


@pytest.mark.asyncio
async def test_local_negotiation_includes_errors_and_rejects_before_mutation():
    app = FastAPI()
    app.add_middleware(ContractMiddleware)
    calls = []

    @app.post("/api/providers/text")
    def action():
        calls.append(True)
        return {"ok": True, "changed": True}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture.invalid") as client:
        old = await client.post("/api/providers/text")
        assert old.json() == {"ok": True, "changed": True}
        response = await client.post("/api/providers/text", headers={"Accept": ACCEPT.replace("=1", "=99")})
        assert response.status_code == 406 and len(calls) == 1
        missing = await client.get("/api/mcp/missing", headers={"Accept": ACCEPT})
        assert missing.status_code == 404
        assert missing.json()["meta"]["contract_id"] == "rider.mcp"
        assert missing.json()["error"] is not None


def test_bus_cache_to_sse_preserves_observation_and_skips_large_offload():
    manager = SseManager(queue_size=2)
    app = SimpleNamespace(state=SimpleNamespace(sse_manager=manager, rest_adapter=None))
    cache = CacheManager()
    handler, *_ = create_zmq_handlers(app, cache)
    row = {"observed_at": 900, "ts": 901, "value": 0, "ready": False}
    handler("robot.pose", row)
    assert cache.get("zmq:robot.pose") == row
    assert tuple(manager.backlog())[0]["data"] == row
    handler("vision.frame.offload", {"payload": "raw-image"})
    assert len(tuple(manager.backlog())) == 1
    queue = manager.subscribe()
    for i in range(5):
        manager.publish({"topic": "motion.state", "data": {"observed_at": i}})
    assert queue.qsize() <= 2
    assert queue.get_nowait()["topic"] == "transport.gap"


@pytest.mark.parametrize(
    "patch", [{"contract_id": "rider.future"}, {"contract_version": True}, {"envelope_version": True}]
)
def test_unknown_named_family_and_boolean_versions_fail_closed(patch):
    body = FIXTURE["cases"]["telemetry"]["body"]
    with pytest.raises(ValueError, match="unsupported_contract"):
        unpack({**body, "meta": {**body["meta"], **patch}})


def test_pc_proxy_preserves_pi_clock_and_puts_receipt_under_transport():
    row = unpack(FIXTURE["cases"]["telemetry"]["body"])
    row["received_at"] = 2000
    result = envelope(row, "/state", "GET", 200)
    assert result["meta"]["generated_at"] == row["contract_meta"]["generated_at"]
    assert result["meta"]["server_time"] == row["contract_meta"]["server_time"]
    assert result["meta"]["observed_at"] == row["contract_meta"]["observed_at"]
    assert result["meta"]["transport"]["received_at"] == 2000


def test_unconfirmed_success_does_not_invent_executed_ack():
    result = envelope({"ok": True, "changed": True}, "/api/providers/text", "PATCH", 200)
    assert result["operation"]["status"] == "unknown"
    assert result["operation"]["confirmed"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change", ["wrong_family", "stale", "no_advertisement", "boolean_advertisement", "partial_shape", "bad_http"]
)
async def test_catalog_preflight_requires_matching_fresh_successful_domain(change):
    import copy

    body = copy.deepcopy(FIXTURE["cases"]["catalog"]["body"])
    status = 200
    if change == "wrong_family":
        body["meta"]["contract_id"] = "rider.services"
    elif change == "stale":
        body["meta"]["observed_at"] -= 11
    elif change == "no_advertisement":
        body["data"]["api_envelope_versions"] = []
    elif change == "boolean_advertisement":
        body["data"]["api_envelope_versions"] = [True]
    elif change == "partial_shape":
        body["data"]["units"] = None
    else:
        status = 503
    methods = []

    def handler(request):
        methods.append(request.method)
        return httpx.Response(status, json=body)

    adapter = RestAdapter("http://fixture.invalid")
    await adapter.client.aclose()
    adapter.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    assert (await adapter.post_control({"action": "move"}))["error"] == "unsupported_contract"
    assert methods == ["GET"]
    await adapter.close()


@pytest.mark.asyncio
async def test_stop_remains_available_without_catalog_or_automatic_metadata():
    commands = []

    def handler(request):
        commands.append((request.method, json.loads(request.content)))
        return httpx.Response(200, json={"ok": True, "confirmed": True})

    adapter = RestAdapter("http://fixture.invalid")
    await adapter.client.aclose()
    adapter.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await adapter.post_control({"action": "stop", "request_id": "original-stop"})
    assert commands == [("POST", {"action": "stop", "request_id": "original-stop"})]
    await adapter.close()


def test_sse_reconnect_replays_only_after_cursor_and_marks_bounded_gaps():
    manager = SseManager(backlog_limit=3, queue_size=2)
    for at in range(1, 6):
        manager.publish({"topic": "robot.pose", "data": {"observed_at": at, "value": 0}})
    queue = manager.subscribe(4)
    assert queue.qsize() == 1
    assert queue.get_nowait()["data"]["observed_at"] == 5
    gap = manager.subscribe(0)
    assert gap.get_nowait()["topic"] == "transport.gap"
    assert gap.get_nowait()["data"]["observed_at"] == 5
    restart = manager.subscribe(100)
    assert restart.get_nowait()["topic"] == "transport.gap"


def test_bus_obstacle_sse_keeps_original_source_not_proxy_receipt_source():
    manager = SseManager()
    app = SimpleNamespace(state=SimpleNamespace(sse_manager=manager, rest_adapter=None))
    handler, *_ = create_zmq_handlers(app, CacheManager())
    original = {"source": "camera/roi", "observed_at": None, "ts": 1000, "present": False, "error": "not_found"}
    handler("vision.obstacle", original)
    assert tuple(manager.backlog())[0]["data"] == original
    assert "received_at" not in original


@pytest.mark.asyncio
async def test_zmq_socket_receives_literal_prefixes_without_wildcard(monkeypatch):
    from pc_client.adapters.zmq_subscriber import ZmqSubscriber
    from pc_client.adapters import zmq_subscriber as module

    prefixes = []

    class Socket:
        def connect(self, endpoint):
            assert endpoint == "inproc://fixture"

        def setsockopt_string(self, option, value):
            prefixes.append(value)

        def close(self, **kwargs):
            pass

    class Context:
        def socket(self, kind):
            return Socket()

        def term(self):
            pass

    monkeypatch.setattr(module, "Context", Context)
    subscriber = ZmqSubscriber("inproc://fixture", ["vision.*", "tracking.*", "mapper.map.data", "motion.*"])

    async def loop():
        await subscriber.stop()

    monkeypatch.setattr(subscriber, "_message_loop", loop)
    await subscriber.start()
    assert prefixes == ["vision.", "tracking.", "mapper.map.data", "motion."]


@pytest.mark.asyncio
async def test_expired_supported_catalog_cannot_survive_failed_refresh():
    import time

    methods = []

    def handler(request):
        methods.append(request.method)
        raise httpx.ReadTimeout("isolated failure")

    adapter = RestAdapter("http://fixture.invalid")
    await adapter.client.aclose()
    adapter.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter._contract_supported = True
    adapter._contract_verified_at = time.monotonic() - 11
    result = await adapter.patch_provider("text", {"target": "pc"})
    assert result["error"] == "unsupported_contract"
    assert methods == ["GET"] and adapter._contract_supported is False
    await adapter.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "accept,status,canonical",
    [
        (ACCEPT + ";q=0", 200, False),
        ("application/json, " + ACCEPT + ";q=0.5", 502, True),
        (ACCEPT.replace("=1", "=2") + ";q=1, " + ACCEPT + ";q=0.2", 502, True),
        (ACCEPT.replace("=1", "=2"), 406, True),
    ],
)
async def test_accept_alternatives_and_q_zero_match_pi_semantics(accept, status, canonical):
    app = FastAPI()
    app.add_middleware(ContractMiddleware)
    effects = []

    @app.post("/api/providers/text")
    def action():
        effects.append(True)
        return {"ok": True, "changed": True}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture.invalid") as client:
        response = await client.post("/api/providers/text", headers={"Accept": accept})
    assert response.status_code == status
    assert ("meta" in response.json()) is canonical
    assert len(effects) == (0 if status == 406 else 1)
    if status == 502:
        assert response.json()["ok"] is False and response.json()["operation"]["status"] == "unknown"


@pytest.mark.asyncio
async def test_invalid_json_domain_get_is_structured_502_and_existing_vary_survives():
    from starlette.responses import Response

    app = FastAPI()
    app.add_middleware(ContractMiddleware)

    @app.get("/state")
    def invalid():
        return Response(content='{"value":NaN}', media_type="application/json", headers={"Vary": "Origin, X-Mode"})

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture.invalid") as client:
        response = await client.get("/state", headers={"Accept": ACCEPT})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "invalid_domain_payload"
    assert response.json()["data"] is None and response.json()["ok"] is False
    assert set(part.strip() for part in response.headers["Vary"].split(",")) == {"Origin", "X-Mode", "Accept"}
    assert unpack(response.json())["error"] == "invalid_domain_payload"


@pytest.mark.parametrize(
    "body", [{"meta": {"envelope_version": 99}}, {"data": {"ok": True}}, {"meta": {"contract_id": "rider.telemetry"}}]
)
def test_partial_declared_envelope_is_not_silently_legacy(body):
    with pytest.raises(ValueError, match="invalid_contract_payload"):
        unpack(body)


@pytest.mark.asyncio
async def test_adapter_refuses_valid_but_wrong_domain_for_endpoint():
    body = FIXTURE["cases"]["telemetry"]["body"]
    adapter = RestAdapter("http://fixture.invalid")
    await adapter.client.aclose()
    adapter.client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)))
    response = await adapter.get_control_state()
    assert response["error"] == "contract_family_mismatch" and response["_http_status"] == 502
    await adapter.close()


@pytest.mark.asyncio
async def test_generic_unknown_route_error_stays_404_but_http_success_cannot_masquerade():
    adapter = RestAdapter("http://fixture.invalid")
    await adapter.client.aclose()
    body = {
        "meta": {"envelope_version": 1, "contract_id": "rider.http", "contract_version": 1},
        "ok": False,
        "data": None,
        "error": {"code": "http_404", "message": "Missing"},
        "operation": None,
    }
    adapter.client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(404, json=body)))
    result = await adapter.get_state()
    assert result["_http_status"] == 404 and result["error"] == "http_404"
    await adapter.client.aclose()
    adapter.client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)))
    result = await adapter.get_state()
    assert result["_http_status"] == 502 and result["error"] == "contract_family_mismatch"
    await adapter.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("conditional", ["If-None-Match", "If-Modified-Since"])
async def test_transitive_operator_modules_are_not_served_from_conditional_browser_cache(conditional):
    from pc_client.api.server import create_app
    from pc_client.config import Settings

    app = create_app(Settings(test_mode=True, enable_providers=False, enable_task_queue=False), CacheManager())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture.invalid") as client:
        original = await client.get("/web/assets/operator/model.js")
        assert original.status_code == 200 and original.headers["Cache-Control"] == "no-store"
        key = "etag" if conditional == "If-None-Match" else "last-modified"
        refreshed = await client.get("/web/assets/operator/model.js", headers={conditional: original.headers[key]})
        assert refreshed.status_code == 200
        assert refreshed.headers["Cache-Control"] == "no-store" and refreshed.content == original.content
