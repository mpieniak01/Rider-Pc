"""Tests for system.log SSE event emission from control_router."""

import os
import pytest
import tempfile
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi.testclient import TestClient
from pc_client.api.server import create_app
from pc_client.api.sse_manager import SseManager
from pc_client.cache import CacheManager
from pc_client.config import Settings

# Enable API tests explicitly (e.g. CI with live endpoints) via RIDER_ENABLE_API_TESTS=1.
_RUN_API_TESTS = os.getenv("RIDER_ENABLE_API_TESTS", "").lower() in {"1", "true", "yes", "on"}


@pytest.fixture
def test_client():
    """Create a test client with temporary cache."""
    if not _RUN_API_TESTS:
        pytest.skip("Control router API tests require RIDER_ENABLE_API_TESTS=1")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_cache.db"
        settings = Settings()
        cache = CacheManager(db_path=str(db_path))
        app = create_app(settings, cache)
        app.router.on_startup.clear()
        app.router.on_shutdown.clear()

        @asynccontextmanager
        async def _lifespan(_app):
            yield

        app.router.lifespan_context = _lifespan

        with TestClient(app) as client:
            yield client, app


def test_service_start_emits_info_log(test_client):
    """Test that starting a service emits INFO level system.log event."""
    client, app = test_client

    # Get SSE manager to check events
    sse_manager: SseManager = app.state.sse_manager

    # Clear backlog for clean test
    sse_manager._backlog.clear()

    # Stop service first to ensure we can start it
    client.post("/svc/voice.provider", json={"action": "stop"})
    sse_manager._backlog.clear()

    # Start the service
    response = client.post("/svc/voice.provider", json={"action": "start"})

    assert response.status_code == 200
    assert response.json()["ok"] is True

    # Check that system.log event was emitted
    backlog = list(sse_manager.backlog())
    system_log_events = [e for e in backlog if e.get("topic") == "system.log"]

    assert len(system_log_events) >= 1
    info_event = system_log_events[-1]  # Get the most recent
    assert info_event["data"]["level"] == "INFO"
    assert "Sukces" in info_event["data"]["message"]
    assert "start" in info_event["data"]["message"]
    assert "voice.provider" in info_event["data"]["message"]


def test_service_stop_emits_info_log(test_client):
    """Test that stopping a service emits INFO level system.log event."""
    client, app = test_client

    sse_manager: SseManager = app.state.sse_manager
    sse_manager._backlog.clear()

    # Stop the service
    response = client.post("/svc/voice.provider", json={"action": "stop"})

    assert response.status_code == 200
    assert response.json()["ok"] is True

    # Check that system.log event was emitted
    backlog = list(sse_manager.backlog())
    system_log_events = [e for e in backlog if e.get("topic") == "system.log"]

    assert len(system_log_events) >= 1
    info_event = system_log_events[-1]
    assert info_event["data"]["level"] == "INFO"
    assert "Sukces" in info_event["data"]["message"]
    assert "stop" in info_event["data"]["message"]


def test_service_restart_emits_info_log(test_client):
    """Test that restarting a service emits INFO level system.log event."""
    client, app = test_client

    sse_manager: SseManager = app.state.sse_manager
    sse_manager._backlog.clear()

    # Restart the service
    response = client.post("/svc/cache.service", json={"action": "restart"})

    assert response.status_code == 200
    assert response.json()["ok"] is True

    # Check that system.log event was emitted
    backlog = list(sse_manager.backlog())
    system_log_events = [e for e in backlog if e.get("topic") == "system.log"]

    assert len(system_log_events) >= 1
    info_event = system_log_events[-1]
    assert info_event["data"]["level"] == "INFO"
    assert "Sukces" in info_event["data"]["message"]
    assert "restart" in info_event["data"]["message"]


def test_service_not_found_emits_error_log(test_client):
    """Test that attempting to control non-existent service emits ERROR log."""
    client, app = test_client

    sse_manager: SseManager = app.state.sse_manager
    sse_manager._backlog.clear()

    # Try to start a non-existent service
    response = client.post("/svc/nonexistent.service", json={"action": "start"})

    assert response.status_code == 404

    # Check that system.log ERROR event was emitted
    backlog = list(sse_manager.backlog())
    system_log_events = [e for e in backlog if e.get("topic") == "system.log"]

    assert len(system_log_events) >= 1
    error_event = system_log_events[-1]
    assert error_event["data"]["level"] == "ERROR"
    assert "Błąd" in error_event["data"]["message"]
    assert "nonexistent.service" in error_event["data"]["message"]


def test_unsupported_action_emits_error_log(test_client):
    """Test that unsupported action emits ERROR log."""
    client, app = test_client

    sse_manager: SseManager = app.state.sse_manager
    sse_manager._backlog.clear()

    # Try unsupported action
    response = client.post("/svc/voice.provider", json={"action": "invalid_action"})

    assert response.status_code == 400

    # Check that system.log ERROR event was emitted
    backlog = list(sse_manager.backlog())
    system_log_events = [e for e in backlog if e.get("topic") == "system.log"]

    assert len(system_log_events) >= 1
    error_event = system_log_events[-1]
    assert error_event["data"]["level"] == "ERROR"
    assert "Błąd" in error_event["data"]["message"]


def test_enable_service_emits_info_log(test_client):
    """Test that enabling a service emits INFO level system.log event."""
    client, app = test_client

    sse_manager: SseManager = app.state.sse_manager
    sse_manager._backlog.clear()

    # Enable the service
    response = client.post("/svc/text.provider", json={"action": "enable"})

    assert response.status_code == 200
    assert response.json()["ok"] is True

    # Check that system.log event was emitted
    backlog = list(sse_manager.backlog())
    system_log_events = [e for e in backlog if e.get("topic") == "system.log"]

    assert len(system_log_events) >= 1
    info_event = system_log_events[-1]
    assert info_event["data"]["level"] == "INFO"
    assert "Sukces" in info_event["data"]["message"]
    assert "enable" in info_event["data"]["message"]


def test_disable_service_emits_info_log(test_client):
    """Test that disabling a service emits INFO level system.log event."""
    client, app = test_client

    sse_manager: SseManager = app.state.sse_manager
    sse_manager._backlog.clear()

    # Disable the service
    response = client.post("/svc/text.provider", json={"action": "disable"})

    assert response.status_code == 200
    assert response.json()["ok"] is True

    # Check that system.log event was emitted
    backlog = list(sse_manager.backlog())
    system_log_events = [e for e in backlog if e.get("topic") == "system.log"]

    assert len(system_log_events) >= 1
    info_event = system_log_events[-1]
    assert info_event["data"]["level"] == "INFO"
    assert "Sukces" in info_event["data"]["message"]
    assert "disable" in info_event["data"]["message"]


def test_system_log_event_has_timestamp(test_client):
    """Test that system.log events include timestamp."""
    client, app = test_client

    sse_manager: SseManager = app.state.sse_manager
    sse_manager._backlog.clear()

    # Trigger a service action
    client.post("/svc/cache.service", json={"action": "restart"})

    # Check that event has timestamp
    backlog = list(sse_manager.backlog())
    system_log_events = [e for e in backlog if e.get("topic") == "system.log"]

    assert len(system_log_events) >= 1
    event = system_log_events[-1]
    assert "ts" in event
    assert isinstance(event["ts"], (int, float))
