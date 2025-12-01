"""Tests for Google Home router endpoints."""

from fastapi.testclient import TestClient

from pc_client.api.server import create_app
from pc_client.cache import CacheManager
from pc_client.config import Settings

# Test configuration constants
TEST_CLIENT_ID = "test-client-id"
TEST_CLIENT_SECRET = "test-client-secret"
TEST_PROJECT_ID = "test-project-id"
TEST_REDIRECT_URI = "http://localhost:8000/api/home/auth/callback"


def make_client(tmp_path) -> TestClient:
    settings = Settings()
    settings.test_mode = True
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
    # Verify the auth URL starts with Google's OAuth endpoint
    assert body["auth_url"].startswith("https://accounts.google.com/o/oauth2/")
    assert "state" in body
    assert "expires_at" in body


def test_home_auth_callback_missing_params(tmp_path):
    """Test auth/callback returns error when code/state is missing."""
    client = make_client_with_google_home(tmp_path)
    resp = client.get("/api/home/auth/callback")
    assert resp.status_code == 400
    assert "missing_params" in resp.text


def test_home_auth_callback_error_from_google(tmp_path):
    """Test auth/callback handles error from Google."""
    client = make_client_with_google_home(tmp_path)
    resp = client.get("/api/home/auth/callback?error=access_denied")
    assert resp.status_code == 400
    assert "access_denied" in resp.text


def test_home_auth_callback_invalid_state(tmp_path):
    """Test auth/callback returns error for invalid state."""
    client = make_client_with_google_home(tmp_path)
    # First, start an auth session to have a valid service state
    client.get("/api/home/auth/url")
    # Then try callback with wrong state
    resp = client.get("/api/home/auth/callback?code=test-code&state=wrong-state")
    assert resp.status_code == 400
    assert "invalid_state" in resp.text


def test_home_status_with_local_service(tmp_path):
    """Test status endpoint with local Google Home service."""
    client = make_client_with_google_home(tmp_path)
    resp = client.get("/api/home/status")
    assert resp.status_code == 200
    body = resp.json()
    # In test mode, service reports as authenticated
    assert body["configured"] is True
    assert body["test_mode"] is True


def test_home_logout(tmp_path):
    """Test logout endpoint clears tokens."""
    client = make_client_with_google_home(tmp_path)
    resp = client.post("/api/home/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
