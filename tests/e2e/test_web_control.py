"""Operator UI against isolated mock server only; never physical robot."""

import json
import time

import pytest
from playwright.sync_api import expect
from pc_client.http_contract import unpack

pytestmark = pytest.mark.timeout(60)


def open_control(page, base):
    response = page.goto(base + "/control", wait_until="domcontentloaded")
    expect(page.locator("#safety-state")).to_have_text("DISARMED")
    assert response.status == 200
    return response


def explicit_arm(page):
    page.locator("#operator-plan").fill("Mock-only fixture: clear space, secured cable, 0.1 s pulse and STOP.")
    page.locator("#operator-consent").check()
    expect(page.locator("#arm")).to_be_enabled()
    with page.expect_response(
        lambda response: response.request.method == "POST" and response.url.endswith("/api/safety")
    ) as event:
        page.locator("#arm").click()
    response = event.value
    assert response.status == 200, response.text()
    body = response.json()
    assert body["meta"]["contract_id"] == "rider.safety" and body["meta"]["contract_version"] == 1
    assert body["operation"]["confirmed"] is True and body["operation"]["status"] == "executed"
    command, result = json.loads(response.request.post_data), unpack(body)
    assert result.get("ok") is True and result.get("confirmed") is True and result.get("pending") is False, result
    assert result.get("simulated") is True and result.get("physical_completion") == "unverified", result
    ack, safety = result["ack"], result["safety"]
    assert ack["status"] == "executed" and ack["physical_completion"] == "unverified", result
    for key in ("request_id", "source", "seq", "action"):
        assert ack[key] == command[key], result
    assert ack["command_generation"] == ack["generation"] == safety["generation"] == command["generation"], result
    assert safety["state"] == "ARMED" and safety["owner"] == command["owner"] == "manual", result
    assert safety["ready"] is True and safety["hardware_ready"] is True and safety["can_move"] is True, result
    assert safety["last_seq"] == command["seq"] and safety["last_ack"] == ack, result
    expect(page.locator("#safety-state")).to_have_text("ARMED")
    expect(page.locator('[data-direction="forward"]')).to_be_enabled()


def test_control_is_read_only_on_entry(browser_context):
    page, base = browser_context
    open_control(page, base)
    expect(page.locator("#task-list article").first).to_be_visible()
    expect(page.locator("#provider-runtime article").first).to_be_visible()
    assert not [r for r in page.requests if r.method in {"POST", "PATCH", "PUT"}]
    assert not page.errors
    expect(page.locator('[data-direction="forward"]')).to_be_disabled()


def test_explicit_arm_then_motion_preserves_original_envelope(browser_context):
    page, base = browser_context
    open_control(page, base)
    explicit_arm(page)
    with page.expect_request("**/api/control") as event:
        page.locator('[data-direction="forward"]').click()
    payload = json.loads(event.value.post_data)
    assert payload["action"] == "move"
    assert payload["vx"] == 0.1 and payload["duration"] == 0.1
    assert payload["source"] == "manual" and payload["seq"] >= 1
    assert payload["generation"] and payload["request_id"] and payload["ttl_ms"] == 500
    expect(page.locator("#request-history")).to_contain_text("SDK")
    page.locator("[data-stop]").first.click()
    expect(page.locator("#safety-state")).to_have_text("DISARMED")


def test_stop_remains_available_without_metadata(browser_context):
    page, base = browser_context
    open_control(page, base)
    with page.expect_request("**/api/control") as event:
        page.locator("[data-stop]").first.click()
    payload = json.loads(event.value.post_data)
    assert payload["action"] == "stop"
    assert "generation" not in payload and "seq" not in payload


def test_typing_and_parameter_edits_never_issue_motion(browser_context):
    page, base = browser_context
    open_control(page, base)
    page.locator("#operator-plan").fill("wsad movement text")
    page.locator("#operator-plan").press("Space")
    page.locator("#speed").fill("0.25")
    page.locator("#control-owner").select_option("navigation")
    assert not [r for r in page.requests if r.method == "POST"]


def test_unverified_posture_actions_remain_disabled(browser_context):
    page, base = browser_context
    open_control(page, base)
    explicit_arm(page)
    for name in ["height", "balance", "action"]:
        expect(page.locator(f"[data-actuator='{name}']")).to_be_disabled()
    page.locator("[data-stop]").first.click()


def test_pending_never_displays_executed(browser_context):
    page, base = browser_context
    open_control(page, base)
    explicit_arm(page)
    page.route(
        "**/api/control",
        lambda route: route.fulfill(status=202, json={"ok": True, "pending": True, "confirmed": False}),
    )
    page.locator('[data-direction="forward"]').click()
    expect(page.locator("#request-history li").first).to_contain_text("Oczekuje")
    assert "SDK" not in page.locator("#request-history li").first.inner_text()
    page.unroute("**/api/control")
    page.locator("[data-stop]").first.click()


def test_stop_immediately_blocks_motion_before_slow_response(browser_context):
    page, base = browser_context
    open_control(page, base)
    explicit_arm(page)
    page.route(
        "**/api/control",
        lambda route: route.fulfill(status=202, json={"ok": True, "pending": True, "confirmed": False}),
    )
    page.locator("[data-stop]").first.click()
    expect(page.locator('[data-direction="forward"]')).to_be_disabled()
    page.unroute("**/api/control")
    page.locator("[data-stop]").first.click()


def test_legacy_pi_is_read_only_with_visible_reason(browser_context):
    page, base = browser_context
    page.route(
        "**/api/control/state",
        lambda route: route.fulfill(
            json={"source": "pi", "safety": {"state": "UNKNOWN", "ready": False, "reason": "legacy_safety_contract"}}
        ),
    )
    page.goto(base + "/control", wait_until="domcontentloaded")
    expect(page.locator("#safety-state")).to_have_text("UNKNOWN")
    expect(page.locator("#arm")).to_be_disabled()
    expect(page.locator('[data-direction="forward"]')).to_be_disabled()
    expect(page.locator("[data-stop]").first).to_be_enabled()
    assert not [r for r in page.requests if r.method == "POST"]


def test_domain_selection_does_not_start_models(browser_context):
    page, base = browser_context
    open_control(page, base)
    before = len(page.requests)
    page.locator("#control-owner").select_option("follow_me")
    page.locator("#provider-runtime article").first.click()
    assert not [r for r in page.requests[before:] if r.method in {"POST", "PATCH", "PUT"}]


def test_catalog_domain_option_selection_is_get_only(browser_context):
    page, base = browser_context

    def catalog(route):
        observed = time.time()
        task = {
            "name": "provider-domain",
            "title": "Fixture domain",
            "option_kind": "provider",
            "installed": True,
            "can_move": False,
            "requested": False,
            "ready": False,
            "state": "stopped",
            "observed_at": observed,
            "source": "demo",
            "option_schema": {
                "field": "domain",
                "default": "text",
                "choices": [{"value": "text", "label": "Text"}, {"value": "vision", "label": "Vision"}],
            },
        }
        route.fulfill(
            json={
                "contract_version": 2,
                "catalog_version": 2,
                "source": "demo",
                "observed_at": observed,
                "units": [],
                "features": [task],
            }
        )

    page.route("**/api/logic/catalog", catalog)
    open_control(page, base)
    choice = page.locator("#task-option-provider-domain")
    expect(choice).to_be_visible()
    choice.select_option("vision")
    assert not [request for request in page.requests if request.method in {"POST", "PUT", "PATCH"}]
