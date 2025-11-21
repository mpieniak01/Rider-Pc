"""Shared fixtures for E2E tests.

Provides session-scoped test server and function-scoped browser contexts.
"""

import os
import socket
import sys
import threading
import time
import urllib.request

import pytest
import uvicorn
from playwright.sync_api import sync_playwright


def run_server_thread():
    """Run FastAPI server in a background thread."""
    # Get port from environment
    port = int(os.environ.get('TEST_SERVER_PORT', 18765))

    # Enable TEST_MODE for mock backend
    os.environ['TEST_MODE'] = 'true'

    # Add project root to path (go up 3 levels from tests/e2e/conftest.py)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from pc_client.api.server import create_app
    from pc_client.cache import CacheManager
    from pc_client.config import Settings

    settings = Settings()
    cache = CacheManager()
    app = create_app(settings, cache)

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    server.run()


@pytest.fixture(scope="session")
def test_server():
    """Start test server in a background thread.

    The server is started once per test session and shared across all tests.
    Uses dynamic port allocation to prevent conflicts.
    Includes robust health check loop to wait for server readiness.
    """
    # Find a free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]

    # Store port for server function
    os.environ['TEST_SERVER_PORT'] = str(port)

    thread = threading.Thread(target=run_server_thread, daemon=True)
    thread.start()

    # Wait for server to be ready with robust health check loop
    base_url = f"http://127.0.0.1:{port}"
    max_retries = 30
    retry_delay = 0.5

    for attempt in range(max_retries):
        try:
            response = urllib.request.urlopen(f"{base_url}/healthz", timeout=2)
            if response.status == 200:
                # Server is ready
                break
        except Exception as e:
            if attempt == max_retries - 1:
                raise Exception(f"Server failed to start after {max_retries} attempts: {e}")
            time.sleep(retry_delay)

    yield base_url
    # Thread will be cleaned up automatically as it's daemonic


@pytest.fixture
def browser_context(test_server):
    """Create a Playwright browser context for testing.

    Provides a fresh browser page for each test with automatic tracking of:
    - Network requests
    - Console messages
    - Page errors

    Args:
        test_server: The base URL of the test server

    Yields:
        tuple: (page, base_url) where page is a Playwright Page object
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-site-isolation-trials",
            ],
        )
        context = browser.new_context()
        context.set_default_navigation_timeout(10000)
        context.set_default_timeout(10000)
        page = context.new_page()

        # Track network requests
        page.requests = []
        page.on("request", lambda request: page.requests.append(request))

        # Track console messages
        page.console_messages = []
        page.on("console", lambda msg: page.console_messages.append(msg))

        # Track page errors
        page.errors = []
        page.on("pageerror", lambda error: page.errors.append(error))

        yield page, test_server
        # Context manager handles cleanup automatically
