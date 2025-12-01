"""Tests for Google Home router endpoints."""

from fastapi.testclient import TestClient

from pc_client.api.server import create_app
from pc_client.cache import CacheManager
from pc_client.config import Settings
from pc_client.services.google_home import reset_google_home_service


def make_client(tmp_path, google_home_configured: bool = False) -> TestClient:
    """Create test client with optional Google Home configuration."""
    settings = Settings()
    settings.test_mode = True

    if google_home_configured:
        settings.google_client_id = "test-client-id"
        settings.google_client_secret = "test-secret"
        settings.google_device_access_project_id = "test-project"
        settings.google_home_redirect_uri = "http://localhost:8000/api/home/auth/callback"

    cache = CacheManager(db_path=str(tmp_path / "cache.db"))
    app = create_app(settings, cache)
    return TestClient(app)


def test_home_status_returns_authenticated(tmp_path):
    """Status should return authenticated in test mode."""
    client = make_client(tmp_path)
    resp = client.get("/api/home/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["authenticated"] is True  # Sprawdzamy, że w trybie testowym endpoint zwraca authenticated=True
    assert "profile" in body
    assert isinstance(body["profile"], dict)


def test_home_devices_and_command(tmp_path):
    """Should list devices and apply commands."""
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
    """Auth endpoint should work in test mode."""
    client = make_client(tmp_path)
    resp = client.post("/api/home/auth")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_home_auth_url_returns_url_when_configured(tmp_path):
    """Auth URL endpoint should return OAuth URL when configured."""
    reset_google_home_service()
    try:
        # Create client with test_mode=False but with Google credentials
        settings = Settings()
        settings.test_mode = False
        settings.google_home_local_enabled = True
        settings.google_client_id = "test-client-id"
        settings.google_client_secret = "test-secret"
        settings.google_device_access_project_id = "test-project"
        settings.google_home_redirect_uri = "http://localhost:8000/api/home/auth/callback"

        cache = CacheManager(db_path=str(tmp_path / "cache.db"))
        app = create_app(settings, cache)
        client = TestClient(app)

        resp = client.get("/api/home/auth/url")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert "auth_url" in body
        # Verify URL starts with expected Google OAuth endpoint
        assert body["auth_url"].startswith("https://accounts.google.com/o/oauth2/")
        assert "state" in body
    finally:
        reset_google_home_service()


def test_home_auth_url_fails_without_config(tmp_path):
    """Auth URL endpoint should fail when not configured."""
    reset_google_home_service()
    try:
        settings = Settings()
        settings.test_mode = False
        settings.google_home_local_enabled = True
        # No Google credentials set

        cache = CacheManager(db_path=str(tmp_path / "cache.db"))
        app = create_app(settings, cache)
        client = TestClient(app)

        resp = client.get("/api/home/auth/url")
        assert resp.status_code == 400
        body = resp.json()
        assert body["ok"] is False
        assert body["error"] == "auth_env_missing"
    finally:
        reset_google_home_service()


def test_home_auth_callback_invalid_state(tmp_path):
    """Auth callback should fail with invalid state."""
    reset_google_home_service()
    try:
        settings = Settings()
        settings.test_mode = False
        settings.google_home_local_enabled = True
        settings.google_client_id = "test-client-id"
        settings.google_client_secret = "test-secret"
        settings.google_device_access_project_id = "test-project"

        cache = CacheManager(db_path=str(tmp_path / "cache.db"))
        app = create_app(settings, cache)
        client = TestClient(app)

        resp = client.get("/api/home/auth/callback?code=test&state=invalid")
        assert resp.status_code == 400
        assert "invalid_state" in resp.text
    finally:
        reset_google_home_service()


def test_home_auth_callback_missing_params(tmp_path):
    """Auth callback should fail without required params."""
    reset_google_home_service()
    try:
        settings = Settings()
        settings.test_mode = False
        settings.google_home_local_enabled = True

        cache = CacheManager(db_path=str(tmp_path / "cache.db"))
        app = create_app(settings, cache)
        client = TestClient(app)

        resp = client.get("/api/home/auth/callback")
        assert resp.status_code == 400
        assert "missing_params" in resp.text
    finally:
        reset_google_home_service()


def test_home_logout(tmp_path):
    """Logout should clear authentication state."""
    reset_google_home_service()
    try:
        settings = Settings()
        settings.test_mode = False
        settings.google_home_local_enabled = True

        cache = CacheManager(db_path=str(tmp_path / "cache.db"))
        app = create_app(settings, cache)
        client = TestClient(app)

        resp = client.post("/api/home/logout")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
    finally:
        reset_google_home_service()


def test_home_command_device_not_found(tmp_path):
    """Command should fail for non-existent device."""
    client = make_client(tmp_path)
    cmd = {
        "deviceId": "non-existent-device",
        "command": "action.devices.commands.OnOff",
        "params": {"on": True},
    }
    resp = client.post("/api/home/command", json=cmd)
    assert resp.status_code == 400
    assert resp.json()["error"] == "device_not_found"


def test_home_devices_returns_list(tmp_path):
    """Devices endpoint should return list of devices."""
    client = make_client(tmp_path)
    resp = client.get("/api/home/devices")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "devices" in body
    assert isinstance(body["devices"], list)
    assert len(body["devices"]) >= 1
