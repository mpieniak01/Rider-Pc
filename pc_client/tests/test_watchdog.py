"""Tests for ServiceWatchdog module."""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock

from pc_client.core.watchdog import ServiceWatchdog
from pc_client.core.service_manager import ServiceManager


class MockServiceManager:
    """Mock ServiceManager for testing."""

    def __init__(self, services=None):
        self._services = services or []
        self.control_calls = []

    def set_services(self, services):
        """Update the mock services list."""
        self._services = services

    async def get_local_services_async(self):
        """Return mock services."""
        return self._services

    async def control_service(self, unit, action):
        """Mock control service - record the call."""
        self.control_calls.append({"unit": unit, "action": action})
        return {"ok": True, "unit": unit, "action": action}


@pytest.mark.asyncio
async def test_watchdog_initialization():
    """Test watchdog initializes correctly."""
    service_manager = MockServiceManager()
    watchdog = ServiceWatchdog(
        service_manager=service_manager,
        monitored_services=["test.service"],
        max_retry_count=1,
        retry_window_seconds=300,
    )

    assert watchdog._max_retry_count == 1
    assert watchdog._retry_window_seconds == 300
    assert watchdog._monitored_services == ["test.service"]
    assert not watchdog._running


@pytest.mark.asyncio
async def test_watchdog_start_stop():
    """Test watchdog start and stop lifecycle."""
    service_manager = MockServiceManager()
    watchdog = ServiceWatchdog(
        service_manager=service_manager,
        check_interval_seconds=0.1,  # Fast interval for testing
    )

    await watchdog.start()
    assert watchdog._running
    assert watchdog._task is not None

    await asyncio.sleep(0.05)  # Let it run briefly

    await watchdog.stop()
    assert not watchdog._running
    assert watchdog._task is None


@pytest.mark.asyncio
async def test_watchdog_detects_failed_service():
    """Test watchdog detects and restarts a failed service."""
    services = [
        {"unit": "healthy.service", "active": "active", "is_local": True},
        {"unit": "failed.service", "active": "failed", "is_local": True},
    ]
    service_manager = MockServiceManager(services=services)

    watchdog = ServiceWatchdog(
        service_manager=service_manager,
        monitored_services=["healthy.service", "failed.service"],
        max_retry_count=1,
        check_interval_seconds=0.1,
    )

    await watchdog.start()
    await asyncio.sleep(0.15)  # Wait for at least one check
    await watchdog.stop()

    # Should have attempted to restart the failed service
    assert len(service_manager.control_calls) == 1
    assert service_manager.control_calls[0]["unit"] == "failed.service"
    assert service_manager.control_calls[0]["action"] == "restart"


@pytest.mark.asyncio
async def test_watchdog_respects_max_retry_count():
    """Test watchdog respects MAX_RETRY_COUNT limit."""
    services = [
        {"unit": "failed.service", "active": "failed", "is_local": True},
    ]
    service_manager = MockServiceManager(services=services)

    watchdog = ServiceWatchdog(
        service_manager=service_manager,
        monitored_services=["failed.service"],
        max_retry_count=1,
        check_interval_seconds=0.05,
    )

    await watchdog.start()
    await asyncio.sleep(0.2)  # Wait for multiple check cycles
    await watchdog.stop()

    # Should have attempted restart only once despite multiple checks
    assert len(service_manager.control_calls) == 1


@pytest.mark.asyncio
async def test_watchdog_does_not_restart_active_services():
    """Test watchdog ignores active services."""
    services = [
        {"unit": "active.service", "active": "active", "is_local": True},
        {"unit": "running.service", "active": "active", "sub": "running", "is_local": True},
    ]
    service_manager = MockServiceManager(services=services)

    watchdog = ServiceWatchdog(
        service_manager=service_manager,
        monitored_services=["active.service", "running.service"],
        check_interval_seconds=0.05,
    )

    await watchdog.start()
    await asyncio.sleep(0.15)
    await watchdog.stop()

    # Should not have attempted any restarts
    assert len(service_manager.control_calls) == 0


@pytest.mark.asyncio
async def test_watchdog_resets_retry_counter_after_window():
    """Test retry counter resets after retry window expires."""
    services = [
        {"unit": "test.service", "active": "failed", "is_local": True},
    ]
    service_manager = MockServiceManager(services=services)

    watchdog = ServiceWatchdog(
        service_manager=service_manager,
        monitored_services=["test.service"],
        max_retry_count=1,
        retry_window_seconds=0.1,  # Short window for testing
        check_interval_seconds=0.05,
    )

    await watchdog.start()
    await asyncio.sleep(0.08)  # First check - should restart
    await watchdog.stop()

    assert len(service_manager.control_calls) == 1
    retry_state = watchdog.get_retry_state()
    assert "test.service" in retry_state
    assert retry_state["test.service"]["count"] == 1

    # Simulate service becoming active for the window period
    service_manager.set_services([
        {"unit": "test.service", "active": "active", "is_local": True},
    ])

    await watchdog.start()
    await asyncio.sleep(0.15)  # Wait for window to expire
    await watchdog.stop()

    # Counter should be reset
    retry_state = watchdog.get_retry_state()
    assert retry_state["test.service"]["count"] == 0


@pytest.mark.asyncio
async def test_watchdog_sse_notifications():
    """Test watchdog sends SSE notifications."""
    services = [
        {"unit": "failed.service", "active": "failed", "is_local": True},
    ]
    service_manager = MockServiceManager(services=services)

    sse_events = []

    def mock_sse_publish(event):
        sse_events.append(event)

    watchdog = ServiceWatchdog(
        service_manager=service_manager,
        monitored_services=["failed.service"],
        max_retry_count=1,
        check_interval_seconds=0.05,
        sse_publish_fn=mock_sse_publish,
    )

    await watchdog.start()
    await asyncio.sleep(0.08)
    await watchdog.stop()

    # Should have sent healing notification
    assert len(sse_events) >= 1
    healing_event = next((e for e in sse_events if e["type"] == "watchdog.healing"), None)
    assert healing_event is not None
    assert healing_event["unit"] == "failed.service"
    assert "Attempt 1/1" in healing_event["message"]


@pytest.mark.asyncio
async def test_watchdog_exhausted_notification():
    """Test watchdog sends exhausted notification when retries are used up."""
    services = [
        {"unit": "failed.service", "active": "failed", "is_local": True},
    ]
    service_manager = MockServiceManager(services=services)

    sse_events = []

    def mock_sse_publish(event):
        sse_events.append(event)

    watchdog = ServiceWatchdog(
        service_manager=service_manager,
        monitored_services=["failed.service"],
        max_retry_count=1,
        check_interval_seconds=0.05,
        sse_publish_fn=mock_sse_publish,
    )

    await watchdog.start()
    await asyncio.sleep(0.2)  # Wait for multiple checks
    await watchdog.stop()

    # Should have sent exhausted notification
    exhausted_events = [e for e in sse_events if e["type"] == "watchdog.exhausted"]
    assert len(exhausted_events) >= 1
    assert exhausted_events[0]["unit"] == "failed.service"
    assert "Manual intervention required" in exhausted_events[0]["message"]


@pytest.mark.asyncio
async def test_watchdog_monitors_all_local_services_when_no_list():
    """Test watchdog monitors all local services when no specific list is given."""
    services = [
        {"unit": "local1.service", "active": "failed", "is_local": True},
        {"unit": "local2.service", "active": "active", "is_local": True},
        {"unit": "remote.service", "active": "failed", "is_local": False},
    ]
    service_manager = MockServiceManager(services=services)

    watchdog = ServiceWatchdog(
        service_manager=service_manager,
        monitored_services=[],  # Empty list means monitor all local
        max_retry_count=1,
        check_interval_seconds=0.05,
    )

    await watchdog.start()
    await asyncio.sleep(0.08)
    await watchdog.stop()

    # Should have restarted local1.service but not remote.service
    assert len(service_manager.control_calls) == 1
    assert service_manager.control_calls[0]["unit"] == "local1.service"


@pytest.mark.asyncio
async def test_watchdog_ignores_inactive_services():
    """Test watchdog ignores inactive (not failed) services."""
    services = [
        {"unit": "inactive.service", "active": "inactive", "is_local": True},
        {"unit": "dead.service", "active": "inactive", "sub": "dead", "is_local": True},
    ]
    service_manager = MockServiceManager(services=services)

    watchdog = ServiceWatchdog(
        service_manager=service_manager,
        monitored_services=["inactive.service", "dead.service"],
        check_interval_seconds=0.05,
    )

    await watchdog.start()
    await asyncio.sleep(0.1)
    await watchdog.stop()

    # Should not have attempted any restarts (inactive != failed)
    assert len(service_manager.control_calls) == 0


@pytest.mark.asyncio
async def test_watchdog_handles_service_manager_exception():
    """Test watchdog handles exceptions from service manager gracefully."""
    service_manager = MockServiceManager()
    # Make get_local_services_async raise an exception
    service_manager.get_local_services_async = AsyncMock(side_effect=Exception("Test error"))

    watchdog = ServiceWatchdog(
        service_manager=service_manager,
        check_interval_seconds=0.05,
    )

    await watchdog.start()
    await asyncio.sleep(0.1)
    await watchdog.stop()

    # Should not crash, just continue running
    assert not watchdog._running  # Stopped gracefully


@pytest.mark.asyncio
async def test_watchdog_get_retry_state():
    """Test get_retry_state returns current retry state."""
    services = [
        {"unit": "failed.service", "active": "failed", "is_local": True},
    ]
    service_manager = MockServiceManager(services=services)

    watchdog = ServiceWatchdog(
        service_manager=service_manager,
        monitored_services=["failed.service"],
        max_retry_count=1,
        check_interval_seconds=0.05,
    )

    # Initially empty
    assert watchdog.get_retry_state() == {}

    await watchdog.start()
    await asyncio.sleep(0.08)
    await watchdog.stop()

    # Should have recorded the failure
    retry_state = watchdog.get_retry_state()
    assert "failed.service" in retry_state
    assert retry_state["failed.service"]["count"] == 1
    assert retry_state["failed.service"]["last_failure_ts"] > 0


@pytest.mark.asyncio
async def test_watchdog_double_start():
    """Test calling start twice does not create duplicate tasks."""
    service_manager = MockServiceManager()
    watchdog = ServiceWatchdog(
        service_manager=service_manager,
        check_interval_seconds=0.1,
    )

    await watchdog.start()
    task1 = watchdog._task
    await watchdog.start()  # Second start should be ignored
    task2 = watchdog._task

    assert task1 is task2  # Same task

    await watchdog.stop()


@pytest.mark.asyncio
async def test_watchdog_with_real_service_manager():
    """Test watchdog works with real ServiceManager (mock mode)."""
    from pc_client.core.service_manager import ServiceManager

    manager = ServiceManager()

    # Simulate a failed service in mock mode
    manager._local_services["test.service"] = {
        "unit": "test.service",
        "active": "failed",
        "sub": "failed",
        "enabled": "enabled",
        "desc": "Test service",
        "group": "test",
        "is_local": True,
        "location": "pc",
    }

    watchdog = ServiceWatchdog(
        service_manager=manager,
        monitored_services=["test.service"],
        max_retry_count=1,
        check_interval_seconds=0.05,
    )

    await watchdog.start()
    await asyncio.sleep(0.08)
    await watchdog.stop()

    # Check service was restarted (state changed from failed to active)
    services = manager.get_local_services()
    test_service = next((s for s in services if s["unit"] == "test.service"), None)
    assert test_service is not None
    assert test_service["active"] == "active"  # Restart sets to active in mock mode
