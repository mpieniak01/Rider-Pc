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
    """Test that #system-graph element is present and visible."""
    page, base_url = browser_context

    page.goto(f"{base_url}/web/system.html")
    page.wait_for_load_state("load")

    # Wait for system-graph element to be visible
    page.wait_for_selector("#system-graph", state="visible", timeout=5000)

    # Check that system-graph element exists and is visible
    system_graph = page.locator("#system-graph")
    assert system_graph.count() > 0, "System graph element should exist"
    assert system_graph.is_visible(), "System graph should be visible"


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
