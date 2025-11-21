# End-to-End Tests for Web Interface

This directory contains End-to-End (E2E) tests for the Rider-PC web interface, specifically focused on the control panel (`control.html`).

## Overview

The E2E tests use Playwright to run a real browser (Chromium in headless mode) and interact with the web interface just like a real user would. These tests help catch regressions in:

- UI rendering
- JavaScript functionality
- API interactions
- User workflows

## Test Coverage

### test_web_control.py

This file contains comprehensive tests for the control panel:

1. **test_control_page_loads** - Verifies the page loads without JavaScript errors
2. **test_critical_elements_render** - Checks that key UI elements (tables, camera preview) render correctly
3. **test_api_status_indicator** - Validates page structure and title rendering
4. **test_motion_button_forward_sends_api_request** - Tests that motion control buttons send correct API requests
5. **test_stop_button_sends_stop_command** - Verifies stop button functionality
6. **test_speed_slider_updates_label** - Tests that UI sliders update their display values
7. **test_service_table_loads** - Checks that the services table populates with data

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

### Run Specific Test

```bash
pytest tests/e2e/test_web_control.py::test_control_page_loads -v
```

### Run with Mock Backend (Default)

The tests automatically use a mock backend to avoid connection errors and timeouts. This happens automatically when running tests - no additional configuration is needed.

The mock backend (MockRestAdapter) provides deterministic responses for all Rider-PI endpoints without requiring a real device or network connection.

### Run with Real Backend (Advanced)

If you have a real Rider-PI device and want to test against it, you can disable test mode:

```bash
# Set environment variables before running tests
export TEST_MODE=false
export RIDER_PI_HOST=<your-rider-pi-ip>
pytest tests/e2e/ -v
```

**Note:** Running tests against a real backend requires a properly configured Rider-PI device and may take longer due to network latency.

### Run with Timeout Disabled (for debugging)

```bash
pytest tests/e2e/ -v --timeout=0
```

## How It Works

The tests follow this pattern:

1. **Server Setup** - A test server is started in a background thread using a dynamically allocated port
2. **Mock Backend** - TEST_MODE is automatically enabled, which replaces RestAdapter with MockRestAdapter
3. **Browser Launch** - Playwright launches Chromium in headless mode
4. **Test Execution** - Tests navigate to pages, interact with elements, and verify behavior
5. **Cleanup** - Browser and server are automatically cleaned up after tests

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
- Use module-scoped fixtures to minimize server startup overhead
- Track network requests to validate API calls
- Capture JavaScript errors and console messages

## Debugging Tips

### View Console Messages

The test fixtures automatically capture console messages and page errors, which are available in test failures.

### Increase Timeouts

If tests fail due to slow startup, you can increase the wait times in the `test_server` fixture.

### Run Headed Mode

For local debugging, you can modify the `browser_context` fixture to use `headless=False`:

```python
browser = p.chromium.launch(headless=False)  # Change to False
```

## Adding New Tests

When adding new E2E tests:

1. Use the `browser_context` fixture which provides a configured page and server URL
2. Always wait for page load state: `page.wait_for_load_state("load")`
3. Use appropriate waits for dynamic content: `time.sleep()` or Playwright's wait methods
4. Verify both UI state and API requests where applicable
5. Clean up any test-specific state

## Known Limitations

- Tests use a mock backend by default (MockRestAdapter) - no real Rider-PI device connection required
- The mock backend provides deterministic test data that may differ from real device responses
- Some advanced features (like actual robot control) are stubbed
- SSE (Server-Sent Events) connections may cause `networkidle` state to timeout, so tests use `load` state instead
- ZMQ subscriber is disabled in test mode to avoid connection attempts
