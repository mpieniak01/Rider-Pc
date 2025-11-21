# End-to-End Tests for Web Interface

This directory contains End-to-End (E2E) tests for the Rider-PC web interface using Playwright.

## Overview

The E2E tests use Playwright to run a real browser (Chromium in headless mode) and interact with the web interface just like a real user would. These tests help catch regressions in:

- UI rendering
- JavaScript functionality
- API interactions
- User workflows

## Test Coverage

### test_web_control.py

Comprehensive tests for the control panel (`control.html`):

1. **test_control_page_loads** - Verifies the page loads without JavaScript errors
2. **test_critical_elements_render** - Checks that key UI elements (tables, camera preview) render correctly
3. **test_api_status_indicator** - Validates page structure and title rendering
4. **test_motion_button_forward_sends_api_request** - Tests that motion control buttons send correct API requests
5. **test_stop_button_sends_stop_command** - Verifies stop button functionality
6. **test_speed_slider_updates_label** - Tests that UI sliders update their display values
7. **test_service_table_loads** - Checks that the services table populates with data

### test_web_screens.py

Smoke tests for informational/passive web screens:

1. **test_system_page_loads** - Verifies system.html loads without errors
2. **test_system_graph_element_visible** - Checks #system-graph element is visible
3. **test_navigation_page_loads** - Verifies navigation.html loads without errors
4. **test_navigation_canvas_element_present** - Checks map canvas element exists
5. **test_chat_page_loads** - Verifies chat.html loads without errors
6. **test_chat_critical_elements_present** - Checks chat UI elements are present

## Running the Tests

### Prerequisites

```bash
# Install test dependencies
pip install -r requirements-ci.txt

# Install Playwright browser
python3 -m playwright install chromium
```

### Run All E2E Tests

```bash
pytest tests/e2e/ -v
```

### Run Specific Test File

```bash
pytest tests/e2e/test_web_control.py -v
pytest tests/e2e/test_web_screens.py -v
```

### Run Specific Test

```bash
pytest tests/e2e/test_web_control.py::test_control_page_loads -v
```

### Mock Backend (Default)

The tests automatically use a mock backend to avoid connection errors and timeouts. This happens automatically when running tests - no additional configuration is needed.

The mock backend (MockRestAdapter) provides deterministic responses for all Rider-PI endpoints without requiring a real device or network connection.

## How It Works

The tests follow this pattern:

1. **Server Setup** - Session-scoped fixture in `conftest.py` starts test server once per test session
2. **Health Check** - Robust health check loop verifies `/healthz` endpoint before tests begin
3. **Mock Backend** - TEST_MODE is automatically enabled, which replaces RestAdapter with MockRestAdapter
4. **Browser Launch** - Function-scoped fixture provides fresh browser context for each test
5. **Test Execution** - Tests navigate to pages, interact with elements, and verify behavior
6. **Cleanup** - Browser and server are automatically cleaned up after tests

### Test Infrastructure

The test infrastructure uses shared fixtures in `conftest.py`:

- `test_server` - Session-scoped fixture that starts FastAPI server once
- `browser_context` - Function-scoped fixture that provides fresh browser page for each test
- Automatic tracking of network requests, console messages, and page errors
- Dynamic port allocation to prevent conflicts
- Robust health check with retry logic for slow startup scenarios

## Mock Backend

The e2e tests use a mock REST adapter (`MockRestAdapter`) that provides deterministic responses for all Rider-PI endpoints. This eliminates:

- Connection timeouts to non-existent Rider-PI devices
- Network latency and reliability issues
- The need for complex test environment setup

The mock backend automatically returns realistic test data for endpoints like:
- `/sysinfo` - System information
- `/vision/snap-info` - Vision snapshot data
- `/api/providers/state` - Provider state
- `/camera/last` - Camera images
- `/svc` - Service status
- And all other Rider-PI REST endpoints

You can review the mock implementation in `pc_client/adapters/mock_rest_adapter.py`.

## CI/CD Integration

These tests are designed to run in CI environments (GitHub Actions):

- Run in headless mode (no display required)
- Use session-scoped server fixture to minimize startup overhead
- Track network requests to validate API calls
- Capture JavaScript errors and console messages
- Robust health check handles slow CI machines

## Debugging Tips

### View Console Messages

The test fixtures automatically capture console messages and page errors, which are available in test failures.

### Increase Timeouts

If tests fail due to slow startup, you can increase the wait times in the `test_server` fixture.

### Run Headed Mode

For local debugging, you can modify the `browser_context` fixture in `conftest.py` to use `headless=False`:

```python
browser = p.chromium.launch(headless=False)  # Change to False
```

## Adding New Tests

When adding new E2E tests:

1. Use the `browser_context` fixture from `conftest.py` which provides configured page and server URL
2. Always wait for page load state: `page.wait_for_load_state("load")`
3. Use appropriate waits for dynamic content: `time.sleep()` or Playwright's wait methods
4. Verify both UI state and API requests where applicable
5. Filter out expected test environment errors (resource loading, WebSocket connections)
6. Clean up any test-specific state

## Known Limitations

- Tests use a mock backend by default (MockRestAdapter) - no real Rider-PI device connection required
- The mock backend provides deterministic test data that may differ from real device responses
- Some advanced features (like actual robot control) are stubbed
- SSE (Server-Sent Events) connections may cause `networkidle` state to timeout, so tests use `load` state instead
- ZMQ subscriber is disabled in test mode to avoid connection attempts
