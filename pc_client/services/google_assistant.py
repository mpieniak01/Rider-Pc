"""Google Assistant service for sending commands to smart home devices.

This module provides a service layer for interacting with Google Assistant API.
Devices are defined in a static TOML configuration file.
"""

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import tomli
except ImportError:
    import tomllib as tomli  # Python 3.11+ standard library

logger = logging.getLogger(__name__)


@dataclass
class AssistantDevice:
    """Represents a device controllable via Google Assistant."""

    id: str
    label: str
    assistant_name: str
    room: str = ""
    category: str = "generic"
    on_command: str = ""
    off_command: str = ""
    supports_brightness: bool = False
    brightness_template: str = ""
    dock_command: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AssistantDevice":
        """Create an AssistantDevice from a dictionary."""
        return cls(
            id=data.get("id", ""),
            label=data.get("label", ""),
            assistant_name=data.get("assistant_name", ""),
            room=data.get("room", ""),
            category=data.get("category", "generic"),
            on_command=data.get("on_command", ""),
            off_command=data.get("off_command", ""),
            supports_brightness=data.get("supports_brightness", False),
            brightness_template=data.get("brightness_template", ""),
            dock_command=data.get("dock_command", ""),
            notes=data.get("notes", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        result = {
            "id": self.id,
            "label": self.label,
            "assistant_name": self.assistant_name,
            "room": self.room,
            "category": self.category,
            "on_command": self.on_command,
            "off_command": self.off_command,
        }
        if self.supports_brightness and self.brightness_template:
            result["supports_brightness"] = True
            result["brightness_template"] = self.brightness_template
        if self.dock_command:
            result["dock_command"] = self.dock_command
        return result


@dataclass
class CommandHistoryEntry:
    """Single entry in command history."""

    timestamp: float
    device_id: str
    action: str
    command_text: str
    success: bool
    response: str = ""


class GoogleAssistantService:
    """Service for managing Google Assistant integration.

    Loads device configuration from TOML file and provides methods for
    sending commands to devices. Supports test mode with mock responses.
    """

    def __init__(
        self,
        config_path: str = "config/google_assistant_devices.toml",
        test_mode: bool = False,
        enabled: bool = True,
    ):
        """Initialize the Google Assistant service.

        Args:
            config_path: Path to device configuration file.
            test_mode: If True, use mock responses instead of real API.
            enabled: If False, all operations return disabled status.
        """
        self.config_path = Path(config_path)
        self.test_mode = test_mode
        self.enabled = enabled

        self._devices: Dict[str, AssistantDevice] = {}
        self._device_status: Dict[str, str] = {}  # Optimistic status tracking
        self._command_history: List[CommandHistoryEntry] = []
        self._config_mtime: float = 0.0
        self._max_history_size = 100

        if self.enabled:
            self._load_config()

    def _load_config(self) -> bool:
        """Load or reload device configuration from TOML file.

        Returns:
            True if configuration was loaded successfully.
        """
        if not self.config_path.exists():
            logger.warning("Config file not found: %s", self.config_path)
            return False

        try:
            current_mtime = self.config_path.stat().st_mtime
            if current_mtime <= self._config_mtime and self._devices:
                return True  # No changes

            with open(self.config_path, "rb") as f:
                data = tomli.load(f)

            devices = data.get("devices", [])
            self._devices = {}

            for device_data in devices:
                try:
                    device = AssistantDevice.from_dict(device_data)
                    if device.id:
                        self._devices[device.id] = device
                        # Initialize status to unknown
                        if device.id not in self._device_status:
                            self._device_status[device.id] = "unknown"
                except Exception as e:
                    logger.warning("Failed to parse device: %s", e)

            self._config_mtime = current_mtime
            logger.info("Loaded %d devices from %s", len(self._devices), self.config_path)
            return True

        except Exception as e:
            logger.error("Failed to load config: %s", e)
            return False

    def reload_config(self) -> Dict[str, Any]:
        """Force reload configuration file.

        Returns:
            Status dict with ok flag and device count.
        """
        if not self.enabled:
            return {"ok": False, "error": "Service disabled"}

        success = self._load_config()
        return {
            "ok": success,
            "devices_count": len(self._devices),
            "config_path": str(self.config_path),
        }

    def list_devices(self) -> List[Dict[str, Any]]:
        """Get list of all configured devices.

        Returns:
            List of device dictionaries with current status.
        """
        if not self.enabled:
            return []

        # Check for config updates (hot-reload)
        self._load_config()

        result = []
        for device_id, device in self._devices.items():
            device_dict = device.to_dict()
            device_dict["status"] = self._device_status.get(device_id, "unknown")
            result.append(device_dict)

        return result

    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific device by ID.

        Args:
            device_id: Device identifier.

        Returns:
            Device dictionary or None if not found.
        """
        if not self.enabled:
            return None

        device = self._devices.get(device_id)
        if not device:
            return None

        device_dict = device.to_dict()
        device_dict["status"] = self._device_status.get(device_id, "unknown")
        return device_dict

    async def send_command(self, device_id: str, action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a command to a device.

        Args:
            device_id: Target device identifier.
            action: Action to perform (on, off, brightness, dock).
            params: Optional parameters (e.g., brightness value).

        Returns:
            Result dictionary with ok flag and response.
        """
        if not self.enabled:
            return {"ok": False, "error": "Service disabled"}

        device = self._devices.get(device_id)
        if not device:
            return {"ok": False, "error": f"Device not found: {device_id}"}

        params = params or {}
        command_text = self._build_command_text(device, action, params)

        if not command_text:
            return {"ok": False, "error": f"Invalid action: {action}"}

        # Send command (real or mock)
        result = await self._execute_command(command_text)

        # Update optimistic status
        if result.get("ok"):
            if action == "on":
                self._device_status[device_id] = "on"
            elif action == "off":
                self._device_status[device_id] = "off"
            elif action == "dock":
                self._device_status[device_id] = "docking"

        # Record in history
        self._add_to_history(
            device_id=device_id,
            action=action,
            command_text=command_text,
            success=result.get("ok", False),
            response=result.get("response", ""),
        )

        return result

    async def send_custom_text(self, text: str) -> Dict[str, Any]:
        """Send a custom text command to Google Assistant.

        Args:
            text: Custom command text.

        Returns:
            Result dictionary with ok flag and response.
        """
        if not self.enabled:
            return {"ok": False, "error": "Service disabled"}

        if not text or not text.strip():
            return {"ok": False, "error": "Empty command text"}

        result = await self._execute_command(text.strip())

        # Record in history
        self._add_to_history(
            device_id="custom",
            action="custom_text",
            command_text=text.strip(),
            success=result.get("ok", False),
            response=result.get("response", ""),
        )

        return result

    def _build_command_text(self, device: AssistantDevice, action: str, params: Dict[str, Any]) -> str:
        """Build command text for a device action.

        Args:
            device: Target device.
            action: Action to perform.
            params: Optional parameters.

        Returns:
            Command text string or empty if invalid.
        """
        action = action.lower()

        if action == "on":
            return device.on_command
        elif action == "off":
            return device.off_command
        elif action == "dock":
            return device.dock_command
        elif action == "brightness":
            if device.supports_brightness and device.brightness_template:
                value = params.get("value", 50)
                return device.brightness_template.format(value=value)
        return ""

    async def _execute_command(self, command_text: str) -> Dict[str, Any]:
        """Execute a command via Google Assistant API.

        Args:
            command_text: Text command to send.

        Returns:
            Result dictionary with ok flag and response.
        """
        if self.test_mode:
            # Mock response for testing
            return {
                "ok": True,
                "response": f"[TEST MODE] Command sent: {command_text}",
                "command": command_text,
                "mode": "test",
            }

        # TODO: Implement real Google Assistant API integration
        # For now, return a placeholder response indicating production mode
        # would require proper OAuth setup and gRPC client
        return {
            "ok": True,
            "response": f"Command queued: {command_text}",
            "command": command_text,
            "mode": "production",
            "note": "Real API integration requires OAuth setup",
        }

    def _add_to_history(
        self,
        device_id: str,
        action: str,
        command_text: str,
        success: bool,
        response: str = "",
    ):
        """Add a command to history.

        Args:
            device_id: Device identifier.
            action: Action performed.
            command_text: Command text sent.
            success: Whether command succeeded.
            response: Response from Assistant.
        """
        entry = CommandHistoryEntry(
            timestamp=time.time(),
            device_id=device_id,
            action=action,
            command_text=command_text,
            success=success,
            response=response,
        )
        self._command_history.append(entry)

        # Trim history to max size
        if len(self._command_history) > self._max_history_size:
            self._command_history = self._command_history[-self._max_history_size:]

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get command history.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of history entry dictionaries.
        """
        entries = self._command_history[-limit:] if limit > 0 else self._command_history
        return [
            {
                "timestamp": e.timestamp,
                "device_id": e.device_id,
                "action": e.action,
                "command_text": e.command_text,
                "success": e.success,
                "response": e.response,
            }
            for e in reversed(entries)  # Most recent first
        ]

    def get_status(self) -> Dict[str, Any]:
        """Get overall service status.

        Returns:
            Status dictionary with enabled flag, device count, etc.
        """
        return {
            "enabled": self.enabled,
            "test_mode": self.test_mode,
            "config_path": str(self.config_path),
            "config_exists": self.config_path.exists(),
            "devices_count": len(self._devices),
            "history_count": len(self._command_history),
        }
