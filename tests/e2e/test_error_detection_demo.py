"""Demonstration test showing E2E tests catch JavaScript errors."""

import time
import pytest
from playwright.sync_api import sync_playwright


def test_javascript_error_detection_demo():
    """
    This test demonstrates that E2E tests can detect JavaScript errors
    that would not be caught by unit tests.
    
    If you introduce a typo in control.html JavaScript (e.g., calling a
    non-existent function), this type of test would catch it.
    """
    # This is a demonstration/documentation test that shows the capability
    # It's marked as skip to avoid running in CI by default
    pytest.skip("Demo test - shows E2E error detection capability")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Track errors
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        
        # Load a page that intentionally has a JavaScript error
        # (In real scenario, this would be control.html with a bug)
        page.set_content("""
        <html>
            <body>
                <h1>Test Page</h1>
                <script>
                    // This will cause an error
                    nonExistentFunction();
                </script>
            </body>
        </html>
        """)
        
        time.sleep(0.5)
        
        # Verify error was caught
        assert len(errors) > 0, "JavaScript error should have been detected"
        assert "nonExistentFunction" in errors[0], "Error should mention the missing function"
        
        browser.close()


def test_api_failure_detection_demo():
    """
    This test demonstrates that E2E tests can detect API failures
    that might occur due to backend changes or network issues.
    """
    pytest.skip("Demo test - shows E2E API failure detection")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Intercept and fail API requests
        page.route("**/api/control", lambda route: route.abort("failed"))
        
        # Track console errors
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg) if msg.type == "error" else None)
        
        # Load page with API interaction
        page.set_content("""
        <html>
            <body>
                <button id="testBtn">Test</button>
                <div id="log"></div>
                <script>
                    document.getElementById('testBtn').addEventListener('click', async () => {
                        try {
                            const response = await fetch('/api/control', {
                                method: 'POST',
                                body: JSON.stringify({cmd: 'test'})
                            });
                            if (!response.ok) {
                                console.error('API failed');
                                document.getElementById('log').textContent = 'Error';
                            }
                        } catch (e) {
                            console.error('Network error');
                            document.getElementById('log').textContent = 'Error';
                        }
                    });
                </script>
            </body>
        </html>
        """)
        
        # Click button to trigger API call
        page.click("#testBtn")
        time.sleep(0.5)
        
        # Verify error handling
        log_text = page.locator("#log").text_content()
        assert "Error" in log_text, "UI should show error state"
        
        browser.close()


if __name__ == "__main__":
    print("These are demonstration tests showing E2E capabilities.")
    print("Run them with: pytest tests/e2e/test_error_detection_demo.py -v")
