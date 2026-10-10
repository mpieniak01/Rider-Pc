"""Browser fixture lifecycle regressions: fake resources, no browser/network."""

from types import SimpleNamespace

import pytest

from tests.e2e.conftest import managed_browser_context


def fake_playwright(*, context_error=None, close_error=None):
    calls = []

    class Context:
        def close(self):
            calls.append("context.close")
            if close_error:
                raise close_error

    class Browser:
        def new_context(self):
            calls.append("browser.new_context")
            if context_error:
                raise context_error
            return Context()

        def close(self):
            calls.append("browser.close")

    def launch(**options):
        calls.append(("launch", options))
        return Browser()

    return SimpleNamespace(chromium=SimpleNamespace(launch=launch)), calls


@pytest.mark.parametrize("test_fails", [False, True])
def test_context_closes_before_browser_even_when_test_fails(test_fails):
    playwright, calls = fake_playwright()
    expected = RuntimeError("test failed") if test_fails else None
    try:
        with managed_browser_context(playwright):
            calls.append("test")
            if expected:
                raise expected
    except RuntimeError as error:
        assert error is expected
    assert calls[1:] == ["browser.new_context", "test", "context.close", "browser.close"]
    assert calls[0][1]["headless"] is True
    args = calls[0][1]["args"]
    assert "--single-process" not in args
    assert not any("site-isolation" in flag or "IsolateOrigins" in flag for flag in args)


def test_browser_closes_when_context_setup_fails():
    failure = RuntimeError("context failed")
    playwright, calls = fake_playwright(context_error=failure)
    with pytest.raises(RuntimeError, match="context failed"):
        with managed_browser_context(playwright):
            pytest.fail("setup must not yield")
    assert calls[1:] == ["browser.new_context", "browser.close"]


def test_browser_closes_when_context_cleanup_fails():
    failure = RuntimeError("close failed")
    playwright, calls = fake_playwright(close_error=failure)
    with pytest.raises(RuntimeError, match="close failed"):
        with managed_browser_context(playwright):
            calls.append("test")
    assert calls[1:] == ["browser.new_context", "test", "context.close", "browser.close"]
