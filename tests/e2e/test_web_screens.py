"""Shared Pi/PC operator surfaces and retained PC specialist views."""

import time
import json
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect


@pytest.mark.parametrize(
    "path,selector",
    [
        ("/view", "#overview-connection"),
        ("/system", "#service-list"),
        ("/navigation", "#map-canvas"),
        ("/calibration", "#manual-settings-status"),
        ("/chat", "#chat-input"),
        ("/devices", "#device-list"),
        ("/models", "main"),
        ("/project", "main"),
        ("/chat-pc", "main"),
    ],
)
def test_screens_load_without_javascript_errors(browser_context, path, selector):
    page, base = browser_context
    response = page.goto(base + path, wait_until="domcontentloaded")
    expect(page.locator(selector)).to_be_visible()
    page.wait_for_timeout(350)
    assert response.status == 200
    assert not page.errors, str(page.errors)
    assert not [r for r in page.requests if r.method in {"POST", "PATCH", "PUT"}]


def test_operator_menu_and_language_switch(browser_context):
    page, base = browser_context
    page.goto(base + "/view", wait_until="domcontentloaded")
    for path in ["view", "control", "devices", "system"]:
        expect(page.locator(f".dashboard-menu a[href='/{path}']")).to_be_visible()
    page.locator(".lang-switch [data-lang='en']").click()
    expect(page.locator("h1")).to_have_text("Rider-PC: Overview")


def test_system_hosts_sources_admin_and_autostart_are_distinct(browser_context):
    page, base = browser_context
    page.goto(base + "/system", wait_until="domcontentloaded")
    expect(page.locator(".service-node").first).to_be_visible()
    assert page.locator(".service-node[data-identity^='pc:']").count() > 0
    assert page.locator(".service-node[data-identity^='pi:']").count() > 0
    expect(page.locator("#service-list")).to_contain_text("demo")
    assert not page.locator(".service-node button:not([data-service-logs]):not(:disabled)").count()
    page.locator("#admin-mode").check()
    expect(page.locator(".service-node[data-identity^='pi:']").first.locator("button").first).to_be_enabled()
    assert not [r for r in page.requests if r.method == "POST"]


def test_devices_preview_is_lazy_and_orientation_is_preserved(browser_context):
    page, base = browser_context
    page.goto(base + "/devices", wait_until="domcontentloaded")
    expect(page.locator("#device-list")).to_contain_text("270")
    expect(page.locator("#camera-preview-state")).to_contain_text("wyłączony")
    assert not [r for r in page.requests if "/vision/cam" in r.url]
    assert not [r for r in page.requests if r.method == "POST"]
    page.locator("#preview-toggle").click()
    expect(page.locator("#camera-preview-state")).to_contain_text("włączony")


def test_footer_preserves_unknown_for_unobserved_vision_and_camera(browser_context):
    page, base = browser_context
    page.route("**/state", lambda route: route.fulfill(json={"present": True, "camera": {"fps": 30}, "source": "pi"}))
    page.route(
        "**/vision/snap-info",
        lambda route: route.fulfill(
            json={"raw": {"exists": True, "age_s": 0}, "proc": {"exists": True, "mtime": None}}
        ),
    )
    page.goto(base + "/view", wait_until="domcontentloaded")
    expect(page.locator("[data-footer-presence-state]")).to_have_text("UNKNOWN / STALE")
    assert "ok" not in page.locator("[data-footer-presence]").get_attribute("class").split()
    assert "ok" not in page.locator("[data-footer-camera]").get_attribute("class").split()
    assert "30.0 fps" not in page.locator("[data-footer-camera-meta]").inner_text()


def test_logs_are_on_demand_get_only_and_keep_host_identity(browser_context):
    page, base = browser_context
    page.goto(base + "/system", wait_until="domcontentloaded")
    row = page.locator(".service-node[data-identity='pc:pc_client.service']")
    expect(row).to_be_visible()
    assert not [request for request in page.requests if "/logs?" in request.url]
    with page.expect_request("**/api/services/pc_client.service/logs?host=pc") as event:
        row.locator("[data-service-logs]").click()
    assert event.value.method == "GET"
    expect(row.locator("details").filter(has_text="Logi tylko do odczytu")).to_be_visible()
    assert not [request for request in page.requests if request.method == "POST"]


def test_mobile_stop_is_visible_and_not_covered_by_menu(browser_context):
    page, base = browser_context
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(base + "/control", wait_until="domcontentloaded")
    stop = page.locator("#global-motion-toggle")
    expect(stop).to_be_visible()
    assert stop.evaluate("""
        node => {
            const rect = node.getBoundingClientRect();
            return rect.top >= 0 && rect.bottom <= innerHeight &&
                document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2)?.closest('#global-motion-toggle') === node;
        }
    """)
    assert not [request for request in page.requests if request.method == "POST"]


def test_navigation_separates_fresh_task_status_from_unusable_measurements(browser_context):
    page, base = browser_context
    observed = time.time()
    measurement = {
        "width_cells": 2,
        "height_cells": 1,
        "grid": [0, 255],
        "resolution_m": 0.1,
        "origin_x": 0,
        "origin_y": 0,
        "observed_at": observed,
        "quality": "measured",
    }
    payload = {
        "state": "IDLE",
        "active": False,
        "data_ready": False,
        "observed_at": observed,
        "navigation": {"map": measurement, "pose": None, "path": None},
    }
    page.route("**/api/navigator/status", lambda route: route.fulfill(json=payload))
    page.add_init_script("""window.fixtureStreams = [];
        window.EventSource = class {
            constructor() { window.fixtureStreams.push(this); }
            close() {}
        };""")
    page.goto(base + "/navigation", wait_until="domcontentloaded")
    expect(page.locator("#map-age")).to_contain_text("measured")
    expect(page.locator("#nav-status")).to_contain_text("IDLE")
    assert "unavailable" not in page.locator("#map-age").inner_text()

    # The shared app wrapper must forward malformed inner navigation data;
    # skipping it would leave the previous map looking healthy.
    label = page.evaluate("""() => {
        window.fixtureStreams.forEach(stream => stream.onmessage?.({
            data: JSON.stringify({topic: 'mapper.map.data', data: 'broken-json'})
        }));
        return document.getElementById('map-age').textContent;
    }""")
    assert "—" in label and "unavailable" in label
    expect(page.locator("#map-age")).to_contain_text("measured")

    # Quality changed even though the producer timestamp did not.
    payload["navigation"]["map"] = {**measurement, "data_ready": False, "quality": "unknown", "error": "uncalibrated"}
    payload["state"] = "FAILED"
    payload["observed_at"] = time.time()
    expect(page.locator("#map-age")).to_contain_text("unavailable")
    expect(page.locator("#nav-status")).to_contain_text("FAILED")

    # Explicit unknown data must expire the previously drawn map.
    payload["navigation"] = None
    expect(page.locator("#map-age")).to_contain_text("—")
    assert not page.errors, str(page.errors)
    assert not [request for request in page.requests if request.method in {"POST", "PATCH", "PUT"}]


@pytest.mark.parametrize("path", ["/view", "/devices"])
def test_recent_offline_xgo_is_not_shown_as_a_healthy_measurement(browser_context, path):
    page, base = browser_context

    def offline_state(route):
        observed = time.time()
        route.fulfill(
            json={
                "source": "pi",
                "devices": {
                    "xgo": {
                        "observed_at": observed,
                        "ts": observed,
                        "source": "motion-executor",
                        "battery_pct": 0,
                        "roll": 0,
                        "pitch": 0,
                        "yaw": 0,
                        "offline": True,
                        "error": "sensor offline",
                    }
                },
            }
        )

    page.route("**/state", offline_state)
    page.goto(base + path, wait_until="domcontentloaded")
    if path == "/view":
        expect(page.locator("#d_xgo_batt")).to_contain_text("nieznane / stare")
        expect(page.locator("#d_xgo_batt")).to_contain_text("0%")
    else:
        telemetry = page.locator("#device-telemetry > article").first
        expect(telemetry).to_contain_text("nieznane / stare")
        expect(telemetry).to_contain_text("0%")
        assert not telemetry.locator(".ok").count()
    assert not page.errors, str(page.errors)
    assert not [request for request in page.requests if request.method in {"POST", "PATCH", "PUT"}]


def test_canonical_partial_sensor_contract_keeps_real_overview_values(browser_context):
    page, base = browser_context
    fixture = json.loads((Path(__file__).parents[1] / "fixtures/contracts/rider-v1.json").read_text())

    def state(route):
        body = json.loads(json.dumps(fixture["cases"]["partial_telemetry"]["body"]))
        now = time.time()
        body["meta"].update(server_time=now, generated_at=now)
        body["data"]["devices"]["xgo"].update(generated_at=now, observed_at=now)
        sensors = body["data"]["devices"]["xgo"]["sensor_quality"]["sensors"]
        for name in ("roll", "battery"):
            sensors[name]["observed_at"] = now
        route.fulfill(json=body)

    page.route("**/state", state)
    page.goto(base + "/view", wait_until="domcontentloaded")
    expect(page.locator("#d_xgo_batt")).to_contain_text("50%")
    expect(page.locator("#d_xgo_batt")).to_contain_text("świeże")
    expect(page.locator("#d_xgo_pose")).to_contain_text("roll: 0.00 surowe SDK")
    expect(page.locator("#d_xgo_imu")).to_contain_text("częściowe")
    assert page.locator("main .view-row > .c-card").count() == 20
    assert page.locator("main canvas").count() == 4
    assert not page.errors, str(page.errors)
    assert not [r for r in page.requests if r.method in {"POST", "PATCH", "PUT"}]


def test_overview_four_previews_use_distinct_sources_with_file_age_not_capture_age(browser_context):
    page, base = browser_context

    def metadata(route):
        now = time.time()
        frames = {
            kind: {
                "exists": True,
                "observed_at": None,
                "capture_at": None,
                "file_observed_at": now,
                "provenance": "file_mtime",
                "source": kind,
                "stale": False,
            }
            for kind in ("raw", "proc", "ssd", "obst", "tracker")
        }
        route.fulfill(
            json={
                "meta": {
                    "envelope_version": 1,
                    "contract_id": "rider.frames",
                    "contract_version": 1,
                    "host": "pi",
                    "source": "pi",
                    "observed_at": None,
                    "server_time": now,
                    "generated_at": now,
                    "offline": False,
                    "stale": False,
                },
                "ok": True,
                "data": frames,
                "error": None,
                "operation": None,
            }
        )

    page.route("**/vision/snap-info", metadata)
    page.goto(base + "/view", wait_until="domcontentloaded")
    for identifier, endpoint in (
        ("img_cam", "/vision/cam"),
        ("img_proc", "/vision/edge"),
        ("img_obst", "/snapshots/obst_annot.jpg"),
        ("img_tracker", "/vision/tracker"),
    ):
        expect(page.locator("#" + identifier)).to_have_attribute(
            "src", re.compile(endpoint.replace(".", r"\.") + r"\?t=")
        )
    expect(page.locator("#age_raw")).to_contain_text("wiek pliku")
    expect(page.locator("#age_raw")).to_contain_text("przechwycenia nieznany")
    assert not [r for r in page.requests if r.url.split("?")[0].endswith("/vision/ssd")]
    assert not page.errors, str(page.errors)
    assert not [r for r in page.requests if r.method in {"POST", "PATCH", "PUT"}]
