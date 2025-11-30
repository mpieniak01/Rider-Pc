"""Tests for Google Home router endpoints."""

from fastapi.testclient import TestClient

from pc_client.api.server import create_app
from pc_client.cache import CacheManager
from pc_client.config import Settings


def make_client(tmp_path) -> TestClient:
    settings = Settings()
    settings.test_mode = True
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
