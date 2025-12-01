"""Tests for Google Home router endpoints."""

import pytest
from fastapi.testclient import TestClient

from pc_client.api.server import create_app
from pc_client.cache import CacheManager
from pc_client.config import Settings
from pc_client.services.google_home import reset_google_home_service

# Test configuration constants
TEST_CLIENT_ID = "test-client-id"
TEST_CLIENT_SECRET = "test-client-secret"
TEST_PROJECT_ID = "test-project-id"
TEST_REDIRECT_URI = "http://localhost:8000/api/home/auth/callback"


@pytest.fixture(autouse=True)
def reset_service():
    """Reset the Google Home service singleton before each test."""
    reset_google_home_service()
    yield
    reset_google_home_service()


def make_client(tmp_path, google_home_local=False) -> TestClient:
    settings = Settings()
    settings.test_mode = True
    settings.google_home_local_enabled = google_home_local
    if google_home_local:
        settings.google_home_test_mode = True
        settings.google_client_id = "test-client-id"
        settings.google_client_secret = "test-client-secret"
        settings.google_device_access_project_id = "test-project-id"
    cache = CacheManager(db_path=str(tmp_path / "cache.db"))
    app = create_app(settings, cache)
    return TestClient(app)


def make_client_with_google_home(tmp_path) -> TestClient:
    """Create client with Google Home local mode enabled."""
    settings = Settings()
    settings.test_mode = True
    settings.google_home_local_enabled = True
    settings.google_home_client_id = "test-client-id"
    settings.google_home_client_secret = "test-client-secret"
    settings.google_home_project_id = "test-project-id"
    settings.google_home_redirect_uri = "http://localhost:8000/api/home/auth/callback"
    settings.google_home_test_mode = True
    settings.google_home_tokens_path = str(tmp_path / "tokens.json")
    cache = CacheManager(db_path=str(tmp_path / "cache.db"))
    app = create_app(settings, cache)
    return TestClient(app)


def test_home_status_returns_authenticated(tmp_path):
    client = make_client(tmp_path)
    resp = client.get("/api/home/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["authenticated"] is True
    assert "profile" in body


def test_home_devices_and_command(tmp_path):
    client = make_client(tmp_path)
    devices = client.get("/api/home/devices").json()["devices"]
    assert devices
    target = devices[0]
    device_id = target["name"]
    cmd = {
        "deviceId": device_id,
        "command": "action.devices.commands.OnOff",
        "params": {"on": False},
    }
    resp = client.post("/api/home/command", json=cmd)
    assert resp.status_code == 200
    result = resp.json()
    assert result["ok"] is True

    devices_after = client.get("/api/home/devices").json()["devices"]
    updated = next(d for d in devices_after if d["name"] == device_id)
    trait = updated["traits"]["sdm.devices.traits.OnOff"]
    assert trait["on"] is False


def test_home_auth_endpoint(tmp_path):
    client = make_client(tmp_path)
    resp = client.post("/api/home/auth")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def make_client_with_google_home(tmp_path) -> TestClient:
    """Create client with Google Home local mode enabled."""
    settings = Settings()
    settings.test_mode = True
    settings.google_home_local_enabled = True
    settings.google_home_client_id = TEST_CLIENT_ID
    settings.google_home_client_secret = TEST_CLIENT_SECRET
    settings.google_home_project_id = TEST_PROJECT_ID
    settings.google_home_redirect_uri = TEST_REDIRECT_URI
    settings.google_home_test_mode = True
    settings.google_home_tokens_path = str(tmp_path / "tokens.json")
    cache = CacheManager(db_path=str(tmp_path / "cache.db"))
    app = create_app(settings, cache)
    return TestClient(app)


def test_home_auth_url_not_enabled(tmp_path):
    """Test auth/url returns error when Google Home local is not enabled."""
    client = make_client(tmp_path)
    resp = client.get("/api/home/auth/url")
    assert resp.status_code == 400
    body = resp.json()
    assert body["ok"] is False
    assert body["error"] == "not_enabled"


def test_home_auth_url_enabled(tmp_path):
    """Test auth/url returns auth URL when Google Home local is enabled."""
    client = make_client_with_google_home(tmp_path)
    resp = client.get("/api/home/auth/url")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "auth_url" in body
    assert "accounts.google.com" in body["auth_url"]
    assert "state" in body


def test_home_auth_callback_missing_params(tmp_path):
    """Auth callback redirects with error when params missing."""
    client = make_client(tmp_path, google_home_local=True)
    resp = client.get("/api/home/auth/callback", follow_redirects=False)
    assert resp.status_code == 307
    assert "auth=error" in resp.headers["location"]
    assert "missing_params" in resp.headers["location"]


def test_home_auth_callback_with_error(tmp_path):
    """Auth callback handles error from Google."""
    client = make_client(tmp_path, google_home_local=True)
    resp = client.get(
        "/api/home/auth/callback?error=access_denied&error_description=User+denied",
        follow_redirects=False,
    )
    assert resp.status_code == 307
    assert "auth=error" in resp.headers["location"]
    assert "access_denied" in resp.headers["location"]


def test_home_auth_callback_invalid_state(tmp_path):
    """Auth callback handles invalid state parameter."""
    client = make_client(tmp_path, google_home_local=True)
    resp = client.get(
        "/api/home/auth/callback?code=test-code&state=invalid-state",
        follow_redirects=False,
    )
    assert resp.status_code == 307
    assert "auth=error" in resp.headers["location"]
    assert "invalid_state" in resp.headers["location"]


def test_home_auth_clear_endpoint(tmp_path):
    """Auth clear endpoint clears authentication state."""
    client = make_client(tmp_path, google_home_local=True)
    resp = client.post("/api/home/auth/clear")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True


def test_home_profile_endpoint_not_authenticated(tmp_path):
    """Profile endpoint returns error when not authenticated."""
    # Create client without test mode to test unauthenticated state
    settings = Settings()
    settings.test_mode = True
    settings.google_home_local_enabled = True
    settings.google_home_test_mode = False  # Disable test mode
    settings.google_client_id = "test-client-id"
    settings.google_client_secret = "test-client-secret"
    settings.google_device_access_project_id = "test-project-id"
    cache = CacheManager(db_path=str(tmp_path / "cache.db"))
    app = create_app(settings, cache)
    client = TestClient(app)

    resp = client.get("/api/home/profile")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["error"] == "not_authenticated"


def test_home_status_local_service(tmp_path):
    """Status endpoint uses local service when enabled."""
    client = make_client(tmp_path, google_home_local=True)
    resp = client.get("/api/home/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["configured"] is True
    assert body["authenticated"] is True
    assert body["test_mode"] is True


def test_home_devices_local_service(tmp_path):
    """Devices endpoint uses local service when enabled."""
    client = make_client(tmp_path, google_home_local=True)
    resp = client.get("/api/home/devices")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert len(body["devices"]) == 3
    assert body.get("test_mode") is True


def test_home_command_local_service(tmp_path):
    """Command endpoint uses local service when enabled."""
    client = make_client(tmp_path, google_home_local=True)
    cmd = {
        "deviceId": "enterprises/test-project/devices/light-living-room",
        "command": "action.devices.commands.OnOff",
        "params": {"on": True},
    }
    resp = client.post("/api/home/command", json=cmd)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body.get("test_mode") is True
