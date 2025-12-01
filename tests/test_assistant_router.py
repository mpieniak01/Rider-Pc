"""Tests for Google Assistant service and router."""

import pytest
from pathlib import Path

from fastapi.testclient import TestClient

from pc_client.api.server import create_app
from pc_client.cache import CacheManager
from pc_client.config import Settings
from pc_client.services.google_assistant import GoogleAssistantService, AssistantDevice


def make_client(tmp_path, enabled=True, test_mode=True) -> TestClient:
    """Create a test client with Google Assistant enabled."""
    settings = Settings()
    settings.test_mode = True
    settings.google_assistant_enabled = enabled
    settings.google_assistant_test_mode = test_mode
    settings.google_assistant_devices_config = str(tmp_path / "devices.toml")

    # Create a test config file
    config_content = """
[[devices]]
id = "test_light"
label = "Test Light"
assistant_name = "Test Light"
room = "Living Room"
category = "lights"
supports_brightness = true
on_command = "Turn on Test Light"
off_command = "Turn off Test Light"
brightness_template = "Set Test Light brightness to {value}%"

[[devices]]
id = "test_vacuum"
label = "Test Vacuum"
assistant_name = "Test Vacuum"
room = "Kitchen"
category = "vacuum"
on_command = "Start Test Vacuum"
off_command = "Stop Test Vacuum"
dock_command = "Dock Test Vacuum"
"""
    (tmp_path / "devices.toml").write_text(config_content)

    cache = CacheManager(db_path=str(tmp_path / "cache.db"))
    app = create_app(settings, cache)
    return TestClient(app)


class TestGoogleAssistantService:
    """Tests for GoogleAssistantService class."""

    def test_service_init_disabled(self, tmp_path):
        """Test service initialization when disabled."""
        service = GoogleAssistantService(
            config_path=str(tmp_path / "nonexistent.toml"),
            enabled=False,
        )
        assert service.enabled is False
        assert len(service.list_devices()) == 0

    def test_service_init_with_config(self, tmp_path):
        """Test service initialization with valid config."""
        config = tmp_path / "devices.toml"
        config.write_text("""
[[devices]]
id = "lamp1"
label = "Lamp 1"
assistant_name = "Lamp One"
room = "Bedroom"
category = "lights"
on_command = "Turn on Lamp One"
off_command = "Turn off Lamp One"
""")
        service = GoogleAssistantService(
            config_path=str(config),
            enabled=True,
            test_mode=True,
        )
        devices = service.list_devices()
        assert len(devices) == 1
        assert devices[0]["id"] == "lamp1"
        assert devices[0]["label"] == "Lamp 1"

    def test_service_get_device(self, tmp_path):
        """Test getting a specific device."""
        config = tmp_path / "devices.toml"
        config.write_text("""
[[devices]]
id = "purifier"
label = "Air Purifier"
assistant_name = "Air Purifier"
category = "air_purifier"
on_command = "Turn on Air Purifier"
off_command = "Turn off Air Purifier"
""")
        service = GoogleAssistantService(config_path=str(config), enabled=True)

        device = service.get_device("purifier")
        assert device is not None
        assert device["label"] == "Air Purifier"

        missing = service.get_device("nonexistent")
        assert missing is None

    @pytest.mark.asyncio
    async def test_service_send_command(self, tmp_path):
        """Test sending a command to a device."""
        config = tmp_path / "devices.toml"
        config.write_text("""
[[devices]]
id = "light1"
label = "Light 1"
assistant_name = "Light One"
category = "lights"
on_command = "Turn on Light One"
off_command = "Turn off Light One"
""")
        service = GoogleAssistantService(
            config_path=str(config),
            enabled=True,
            test_mode=True,
        )

        result = await service.send_command("light1", "on")
        assert result["ok"] is True
        assert "TEST MODE" in result["response"]

        # Check history
        history = service.get_history(limit=1)
        assert len(history) == 1
        assert history[0]["device_id"] == "light1"
        assert history[0]["action"] == "on"

    @pytest.mark.asyncio
    async def test_service_send_custom_text(self, tmp_path):
        """Test sending a custom text command."""
        config = tmp_path / "devices.toml"
        config.write_text("# Empty config\n")

        service = GoogleAssistantService(
            config_path=str(config),
            enabled=True,
            test_mode=True,
        )

        result = await service.send_custom_text("Turn off all lights")
        assert result["ok"] is True

        # Empty text should fail
        result = await service.send_custom_text("")
        assert result["ok"] is False

    def test_service_status(self, tmp_path):
        """Test service status report."""
        config = tmp_path / "devices.toml"
        config.write_text("# Empty\n")

        service = GoogleAssistantService(
            config_path=str(config),
            enabled=True,
            test_mode=True,
        )

        status = service.get_status()
        assert status["enabled"] is True
        assert status["test_mode"] is True
        assert "devices_count" in status


class TestAssistantDevice:
    """Tests for AssistantDevice dataclass."""

    def test_from_dict(self):
        """Test creating device from dictionary."""
        data = {
            "id": "dev1",
            "label": "Device 1",
            "assistant_name": "Device One",
            "room": "Room A",
            "category": "lights",
            "on_command": "On",
            "off_command": "Off",
            "supports_brightness": True,
            "brightness_template": "Set to {value}%",
        }
        device = AssistantDevice.from_dict(data)
        assert device.id == "dev1"
        assert device.supports_brightness is True

    def test_to_dict(self):
        """Test converting device to dictionary."""
        device = AssistantDevice(
            id="dev2",
            label="Device 2",
            assistant_name="Device Two",
            category="vacuum",
            on_command="Start",
            off_command="Stop",
            dock_command="Dock",
        )
        result = device.to_dict()
        assert result["id"] == "dev2"
        assert result["dock_command"] == "Dock"
        assert "supports_brightness" not in result


class TestAssistantRouter:
    """Tests for assistant router endpoints."""

    def test_status_endpoint(self, tmp_path):
        """Test /api/assistant/status endpoint."""
        client = make_client(tmp_path)
        resp = client.get("/api/assistant/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["enabled"] is True

    def test_devices_endpoint(self, tmp_path):
        """Test /api/assistant/devices endpoint."""
        client = make_client(tmp_path)
        resp = client.get("/api/assistant/devices")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert len(body["devices"]) == 2

    def test_device_endpoint(self, tmp_path):
        """Test /api/assistant/device/{id} endpoint."""
        client = make_client(tmp_path)
        resp = client.get("/api/assistant/device/test_light")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["device"]["id"] == "test_light"

        # Not found
        resp = client.get("/api/assistant/device/nonexistent")
        assert resp.status_code == 404

    def test_command_endpoint(self, tmp_path):
        """Test /api/assistant/command endpoint."""
        client = make_client(tmp_path)

        # Valid command
        resp = client.post("/api/assistant/command", json={
            "device_id": "test_light",
            "action": "on",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True

        # Missing device_id
        resp = client.post("/api/assistant/command", json={"action": "on"})
        assert resp.status_code == 400

        # Missing action
        resp = client.post("/api/assistant/command", json={"device_id": "test_light"})
        assert resp.status_code == 400

    def test_custom_endpoint(self, tmp_path):
        """Test /api/assistant/custom endpoint."""
        client = make_client(tmp_path)

        resp = client.post("/api/assistant/custom", json={
            "text": "Turn off all lights",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True

        # Empty text
        resp = client.post("/api/assistant/custom", json={"text": ""})
        assert resp.status_code == 400

    def test_history_endpoint(self, tmp_path):
        """Test /api/assistant/history endpoint."""
        client = make_client(tmp_path)

        # Send a command first
        client.post("/api/assistant/command", json={
            "device_id": "test_light",
            "action": "on",
        })

        resp = client.get("/api/assistant/history")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert len(body["history"]) >= 1

    def test_reload_endpoint(self, tmp_path):
        """Test /api/assistant/reload endpoint."""
        client = make_client(tmp_path)

        resp = client.post("/api/assistant/reload", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["devices_count"] == 2

    def test_disabled_service(self, tmp_path):
        """Test endpoints when service is disabled."""
        client = make_client(tmp_path, enabled=False)

        resp = client.get("/api/assistant/status")
        body = resp.json()
        assert body["enabled"] is False

        resp = client.get("/api/assistant/devices")
        body = resp.json()
        assert body["devices"] == []
