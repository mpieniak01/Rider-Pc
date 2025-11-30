"""E2E tests for informational web screens.

Tests cover smoke testing for passive/informational screens:
- system.html - System diagnostics and metrics
- navigation.html - Navigation map and visualization
- chat.html - Chat interface for LLM interaction

These are basic smoke tests verifying:
- HTTP 200 response
- Absence of JavaScript errors
- Presence of key UI elements

Mock Backend:
The tests automatically enable TEST_MODE which uses MockRestAdapter.
"""


def _filter_test_env_console_errors(console_messages):
    """Filter out expected console errors in test environment.

    Filters:
    - External resource loading failures (CDN)
    - WebSocket connection failures (not available in test mode)

    Returns only actual JavaScript execution errors.
    """
    return [
        msg
        for msg in console_messages
        if msg.type == "error" and "Failed to load resource" not in msg.text and "WebSocket connection" not in msg.text
    ]


def test_system_page_loads(browser_context):
    """Test that system.html loads without errors."""
    page, base_url = browser_context

    response = page.goto(f"{base_url}/web/system.html")
    assert response.status == 200, "System page should load successfully"

    # Wait for page to be fully loaded
    page.wait_for_load_state("load")

    # Check no JavaScript errors occurred
    js_errors = [msg for msg in page.console_messages if msg.type == "error"]
    assert len(js_errors) == 0, f"JavaScript errors found: {[msg.text for msg in js_errors]}"

    # Check no page errors
    assert len(page.errors) == 0, f"Page errors found: {page.errors}"


def test_system_graph_element_visible(browser_context):
    """Test that PC services block element is present and visible."""
    page, base_url = browser_context

    page.goto(f"{base_url}/web/system.html")
    page.wait_for_load_state("load")

    # Wait for PC services block to be visible (replaces old #system-graph)
    page.wait_for_selector("#pc-services-block", state="visible", timeout=5000)

    # Check that PC services block exists and is visible
    pc_services_block = page.locator("#pc-services-block")
    assert pc_services_block.count() > 0, "PC services block element should exist"
    assert pc_services_block.is_visible(), "PC services block should be visible"

    # Check that PC services grid exists within the block
    pc_services_graph = page.locator("#pc-services-graph")
    assert pc_services_graph.count() > 0, "PC services graph element should exist"


def test_navigation_page_loads(browser_context):
    """Test that navigation.html loads without errors."""
    page, base_url = browser_context

    response = page.goto(f"{base_url}/web/navigation.html")
    assert response.status == 200, "Navigation page should load successfully"

    # Wait for page to be fully loaded
    page.wait_for_load_state("load")

    # Filter out expected errors in test environment
    js_errors = _filter_test_env_console_errors(page.console_messages)
    assert len(js_errors) == 0, f"JavaScript errors found: {[msg.text for msg in js_errors]}"

    # Check no page errors (actual JavaScript exceptions)
    assert len(page.errors) == 0, f"Page errors found: {page.errors}"


def test_navigation_canvas_element_present(browser_context):
    """Test that navigation canvas element is present."""
    page, base_url = browser_context

    page.goto(f"{base_url}/web/navigation.html")
    page.wait_for_load_state("load")

    # Check that mapCanvas element exists
    map_canvas = page.locator("#mapCanvas")
    assert map_canvas.count() > 0, "Map canvas element should exist"

    # Verify it's a canvas element
    tag_name = map_canvas.evaluate("el => el.tagName")
    assert tag_name.lower() == "canvas", "Element should be a canvas"


def test_chat_page_loads(browser_context):
    """Test that chat.html loads without errors."""
    page, base_url = browser_context

    response = page.goto(f"{base_url}/web/chat.html")
    assert response.status == 200, "Chat page should load successfully"

    # Wait for page to be fully loaded
    page.wait_for_load_state("load")

    # Check no JavaScript errors occurred
    js_errors = [msg for msg in page.console_messages if msg.type == "error"]
    assert len(js_errors) == 0, f"JavaScript errors found: {[msg.text for msg in js_errors]}"

    # Check no page errors
    assert len(page.errors) == 0, f"Page errors found: {page.errors}"


def test_chat_critical_elements_present(browser_context):
    """Test that critical chat interface elements are present."""
    page, base_url = browser_context

    page.goto(f"{base_url}/web/chat.html")
    page.wait_for_load_state("load")

    # Wait for critical elements to be present
    page.wait_for_selector("#board", state="attached", timeout=5000)
    page.wait_for_selector("#input", state="attached", timeout=5000)
    page.wait_for_selector("#sendBtn", state="visible", timeout=5000)

    # Check board (chat messages container)
    board = page.locator("#board")
    assert board.count() > 0, "Chat board element should exist"

    # Check input textarea
    input_field = page.locator("#input")
    assert input_field.count() > 0, "Chat input field should exist"

    # Check send button
    send_btn = page.locator("#sendBtn")
    assert send_btn.count() > 0, "Send button should exist"
    assert send_btn.is_visible(), "Send button should be visible"

    # Check TTS checkbox
    tts_checkbox = page.locator("#tts")
    assert tts_checkbox.count() > 0, "TTS checkbox should exist"


def test_view_system_card_displays_host(browser_context):
    """Ensure the main dashboard view loads and shows mock host data."""
    page, base_url = browser_context

    response = page.goto(f"{base_url}/web/view.html")
    assert response.status == 200, "View page should load successfully"

    page.wait_for_load_state("load")
    page.wait_for_function(
        """
        () => {
            const el = document.getElementById('ci_host');
            return el && el.textContent.trim() !== '—';
        }
        """,
        timeout=5000,
    )

    host_text = page.locator("#ci_host").inner_text().strip()
    assert host_text not in {"", "—"}, "System card should display detected host name"


def test_view_system_card_structure(browser_context):
    """Verify that key rows of the system card stay in the DOM."""
    page, base_url = browser_context

    page.goto(f"{base_url}/web/view.html")
    page.wait_for_load_state("load")

    labels = [
        "dash.system.host",
        "dash.system.cpu_est",
        "dash.system.load",
        "dash.system.mem",
        "dash.system.disk",
        "dash.system.os",
        "dash.system.fw",
    ]
    value_ids = ["ci_host", "ci_cpu", "ci_load", "ci_mem", "ci_disk", "ci_os", "ci_fw"]

    for data_i18n in labels:
        locator = page.locator(f"div[data-i18n='{data_i18n}']")
        assert locator.count() > 0, f"Etykieta {data_i18n} powinna istnieć"

    for element_id in value_ids:
        locator = page.locator(f"#{element_id}")
        assert locator.count() > 0, f"Wartość dla {element_id} powinna istnieć"


def test_system_network_cards_update(browser_context):
    """Verify system dashboard populates network cards with data."""
    page, base_url = browser_context

    response = page.goto(f"{base_url}/web/system.html")
    assert response.status == 200, "System page should load successfully"

    page.wait_for_load_state("load")
    page.wait_for_function(
        """
        () => {
            const host = document.getElementById('rider-pi-host');
            const localIp = document.getElementById('local-ip-value');
            if (!host || !localIp) return false;
            const hasHost = host.textContent.trim().length > 0;
            const hasIp = localIp.textContent.trim() !== '---.---.---.---';
            return hasHost && hasIp;
        }
        """,
        timeout=7000,
    )

    local_ip = page.locator("#local-ip-value").inner_text().strip()
    rider_pi_host = page.locator("#rider-pi-host").inner_text().strip()

    assert local_ip != '---.---.---.---', "Local IP card should display the detected host IP"
    assert rider_pi_host != '', "Rider-Pi card should display configured host address"


def test_system_page_sections_present(browser_context):
    """Ensure that the main sections of system.html are rendered."""
    page, base_url = browser_context

    page.goto(f"{base_url}/web/system.html")
    page.wait_for_load_state("load")

    selectors = [
        "#status-line",
        "#network-status-block",
        "#pc-services-block",
        "#pc-services-graph",
        "#pi-services-block",
        "#pi-services-graph",
        ".log-panel",
        "#log-terminal",
        "#log-clear-btn",
    ]

    for selector in selectors:
        locator = page.locator(selector)
        assert locator.count() > 0, f"Element {selector} powinien istnieć"
        assert locator.first.is_visible(), f"Element {selector} powinien być widoczny"


def test_control_page_core_widgets_present(browser_context):
    """Validate that control.html renders camera, motion and feature panels."""
    page, base_url = browser_context

    page.goto(f"{base_url}/web/control.html")
    page.wait_for_load_state("load")

    basic_selectors = [
        "#camPrev",
        ".motion-grid",
        "#featureList",
        ".feature-card",
        "#scenarioList",
        "#resTable",
        "#svcTable",
        "#motionQueueTable",
        "#log",
    ]
    for selector in basic_selectors:
        locator = page.locator(selector)
        assert locator.count() > 0, f"Element {selector} powinien istnieć"

    # Wait for data-driven sections to populate
    page.wait_for_selector("#motionQueueBody tr", timeout=7000)
    assert page.locator("#motionQueueBody tr").count() > 0, "Tabela kolejki ruchu powinna mieć wiersze"
    page.wait_for_selector("#scenarioList .scenario-row", timeout=7000)


def test_models_page_sections_render(browser_context):
    """Smoke test for models.html ensuring main grids show seeded data."""
    page, base_url = browser_context

    page.goto(f"{base_url}/web/models.html")
    page.wait_for_load_state("load")

    page.wait_for_selector(".active-model-card", timeout=7000)
    assert page.locator(".active-model-card").count() > 0, "Powinna istnieć co najmniej jedna karta aktywnego modelu"

    page.wait_for_selector(".provider-card", timeout=7000)
    assert page.locator(".provider-card").count() > 0, "Powinna istnieć karta stanu providera Rider-Pi"

    page.wait_for_selector("#installed-models-tbody tr", timeout=7000)
    assert page.locator("#installed-models-tbody tr").count() > 0, "Tabela lokalnych modeli powinna zawierać wiersze"


def test_project_page_lists_mock_issues(browser_context):
    """Ensure that project.html renders issues from the mock GitHub adapter."""
    page, base_url = browser_context

    page.goto(f"{base_url}/web/project.html")
    page.wait_for_load_state("load")

    page.wait_for_selector("article.issue-card", timeout=7000)
    issue_cards = page.locator("article.issue-card")
    assert issue_cards.count() > 0, "Powinna zostać wyrenderowana co najmniej jedna karta zgłoszenia"
