"""Google Assistant service for sending commands to smart home devices.

This module provides a service layer for interacting with Google Assistant API.
Devices are defined in a static TOML configuration file.
"""

import json
import logging
import os
import time
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

try:
    import tomllib as toml_module
except ImportError:
    try:
        import tomli as toml_module  # type: ignore
    except ImportError:  # pragma: no cover - optional dependency
        toml_module = None  # type: ignore[assignment]

GoogleCredentials: Any
GoogleAuthRequest: Any
GoogleSecureChannel: Any
try:
    from google.oauth2.credentials import Credentials as GoogleCredentials
    from google.auth.transport.requests import Request as GoogleAuthRequest
    from google.auth.transport.grpc import secure_authorized_channel as GoogleSecureChannel
    import google.assistant.embedded.v1alpha2.embedded_assistant_pb2 as embedded_assistant_pb2
    import google.assistant.embedded.v1alpha2.embedded_assistant_pb2_grpc as embedded_assistant_pb2_grpc
    import grpc

    GOOGLE_ASSISTANT_SDK_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    GoogleCredentials = None
    GoogleAuthRequest = None
    GoogleSecureChannel = None
    embedded_assistant_pb2 = None
    embedded_assistant_pb2_grpc = None
    grpc = None
    GOOGLE_ASSISTANT_SDK_AVAILABLE = False

logger = logging.getLogger(__name__)
ASSISTANT_SCOPE = "https://www.googleapis.com/auth/assistant-sdk-prototype"


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
        result: Dict[str, Any] = {
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
        tokens_path: Optional[str] = None,
        project_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        device_model_id: Optional[str] = None,
        device_id: Optional[str] = None,
        language_code: str = "pl-PL",
    ):
        """Initialize the Google Assistant service.

        Args:
            config_path: Path to device configuration file.
            test_mode: If True, use mock responses instead of real API.
            enabled: If False, all operations return disabled status.
            tokens_path: Path to OAuth tokens JSON.
            project_id: Google Cloud project identifier.
            client_id: OAuth client ID override.
            client_secret: OAuth client secret override.
            device_model_id: Assistant device model ID.
            device_id: Registered device ID.
            language_code: Preferred Assistant language (pl-PL/en-US/etc).
        """
        self.config_path = Path(config_path)
        self.test_mode = test_mode
        self.enabled = enabled
        self.tokens_path = Path(tokens_path) if tokens_path else None
        self.project_id = project_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.device_model_id = cast(
            str,
            device_model_id or (f"{project_id}-panel" if project_id else "rider-pc-panel-model"),
        )
        self.device_id = device_id or "rider-pc-panel-device"
        self.language_code = language_code or "pl-PL"

        self._devices: Dict[str, AssistantDevice] = {}
        self._device_status: Dict[str, str] = {}  # Optimistic status tracking
        self._command_history: List[CommandHistoryEntry] = []
        self._config_mtime: float = 0.0
        self._max_history_size = 100
        self._credentials: Optional[GoogleCredentials] = None
        self._http_request: Optional[GoogleAuthRequest] = None
        self._assistant_endpoint = "embeddedassistant.googleapis.com"
        self._grpc_deadline = 20  # seconds
        self._conversation_state: Optional[bytes] = None

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

            if toml_module is None:
                logger.warning("No TOML parser available; cannot load %s", self.config_path)
                return False
            with open(self.config_path, "rb") as f:
                data = toml_module.load(f)

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

    def _load_tokens_from_file(self) -> Optional[Dict[str, Any]]:
        """Read OAuth tokens JSON if available."""
        if not self.tokens_path or not self.tokens_path.exists():
            return None
        try:
            return json.loads(self.tokens_path.read_text())
        except Exception as exc:  # pragma: no cover - IO error
            logger.error("Failed to read tokens file %s: %s", self.tokens_path, exc)
            return None

    def _build_credentials(self) -> Optional[GoogleCredentials]:
        """Build google.oauth2.credentials.Credentials from stored tokens."""
        if not GOOGLE_ASSISTANT_SDK_AVAILABLE or not self.tokens_path:
            return None

        token_data = self._load_tokens_from_file()
        if not token_data:
            return None

        refresh_token = token_data.get("refresh_token")
        client_id = self.client_id or token_data.get("client_id")
        client_secret = self.client_secret or token_data.get("client_secret")

        if not all([refresh_token, client_id, client_secret]):
            logger.warning("Incomplete OAuth tokens; check %s", self.tokens_path)
            return None

        scopes = token_data.get("scopes") or [ASSISTANT_SCOPE]
        credentials = GoogleCredentials(
            token=token_data.get("access_token"),
            refresh_token=refresh_token,
            token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes,
        )
        expiry = token_data.get("expiry")
        if expiry:
            try:
                credentials.expiry = datetime.fromisoformat(expiry)
            except ValueError:
                pass
        return credentials

    def _save_credentials(self, credentials: GoogleCredentials) -> None:
        """Persist refreshed credentials back to tokens file."""
        if not self.tokens_path:
            return
        payload = {
            "refresh_token": credentials.refresh_token,
            "client_id": credentials.client_id or self.client_id,
            "client_secret": credentials.client_secret or self.client_secret,
            "token_uri": credentials.token_uri,
            "scopes": list(credentials.scopes or []),
        }
        if credentials.token:
            payload["access_token"] = credentials.token
        if credentials.expiry:
            payload["expiry"] = credentials.expiry.isoformat()

        try:
            self.tokens_path.parent.mkdir(parents=True, exist_ok=True)
            self.tokens_path.write_text(json.dumps(payload, indent=2))
        except Exception as exc:  # pragma: no cover - IO error
            logger.warning("Failed to persist refreshed token: %s", exc)

    def _get_credentials(self) -> Optional[GoogleCredentials]:
        """Return cached credentials (refreshed if needed)."""
        if not GOOGLE_ASSISTANT_SDK_AVAILABLE:
            return None

        if self._credentials is None:
            self._credentials = self._build_credentials()

        creds = self._credentials
        if creds is None:
            return None

        if not self._http_request and GoogleAuthRequest:
            self._http_request = GoogleAuthRequest()

        if self._http_request and (creds.expired or not creds.valid):
            try:
                creds.refresh(self._http_request)
                self._save_credentials(creds)
            except Exception as exc:
                logger.error("Failed to refresh Google Assistant token: %s", exc)
                return None

        return creds

    def _create_assistant_stub(self, credentials: GoogleCredentials):
        """Create an authorized gRPC stub."""
        if not GoogleSecureChannel or not GoogleAuthRequest:
            return None, None
        if not self._http_request:
            self._http_request = GoogleAuthRequest()
        channel = GoogleSecureChannel(credentials, self._http_request, self._assistant_endpoint)
        stub = embedded_assistant_pb2_grpc.EmbeddedAssistantStub(channel)
        return stub, channel

    def _live_ready(self) -> bool:
        """Return True if live (non-test) mode has required configuration."""
        if self.test_mode or not self.enabled:
            return False
        if not GOOGLE_ASSISTANT_SDK_AVAILABLE:
            return False
        tokens = self._load_tokens_from_file()
        return bool(tokens and (tokens.get("refresh_token") or tokens.get("access_token")))

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

    async def send_command(
        self, device_id: str, action: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
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

        if not GOOGLE_ASSISTANT_SDK_AVAILABLE:
            return {"ok": False, "error": "google_assistant_sdk_missing"}

        if not self._live_ready():
            return {"ok": False, "error": "assistant_live_config_missing"}

        credentials = self._get_credentials()
        if credentials is None:
            return {"ok": False, "error": "assistant_credentials_missing"}

        stub, channel = self._create_assistant_stub(credentials)
        if not stub or not channel:
            return {"ok": False, "error": "assistant_channel_unavailable"}

        responses: List[str] = []
        try:
            dialog_state = embedded_assistant_pb2.DialogStateIn(
                language_code=self.language_code,
                conversation_state=self._conversation_state or b"",
                is_new_conversation=self._conversation_state is None,
            )
            assist_config = embedded_assistant_pb2.AssistConfig(
                text_query=command_text,
                dialog_state_in=dialog_state,
                device_config=embedded_assistant_pb2.DeviceConfig(
                    device_id=self.device_id or "rider-pc-panel-device",
                    device_model_id=self.device_model_id or "rider-pc-panel-model",
                ),
                audio_out_config=embedded_assistant_pb2.AudioOutConfig(
                    encoding=embedded_assistant_pb2.AudioOutConfig.MP3,
                    sample_rate_hertz=16000,
                    volume_percentage=0,
                ),
            )
            request = embedded_assistant_pb2.AssistRequest(config=assist_config)

            for response in stub.Assist(iter([request]), timeout=self._grpc_deadline):
                if response.dialog_state_out.conversation_state:
                    self._conversation_state = response.dialog_state_out.conversation_state
                if response.dialog_state_out.supplemental_display_text:
                    responses.append(response.dialog_state_out.supplemental_display_text)
                if response.speech_results:
                    responses.extend([res.transcript for res in response.speech_results if res.transcript])

        except grpc.RpcError as exc:  # pragma: no cover - network
            logger.exception("Google Assistant RPC error: %s", exc)
            return {
                "ok": False,
                "error": "assistant_rpc_error",
                "details": exc.details() if hasattr(exc, "details") else str(exc),
            }
        finally:
            if channel:
                channel.close()

        response_text = " ".join(responses).strip() or "Command sent."
        return {
            "ok": True,
            "response": response_text,
            "command": command_text,
            "mode": "live",
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
            self._command_history = self._command_history[-self._max_history_size :]

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
            "libs_available": GOOGLE_ASSISTANT_SDK_AVAILABLE,
            "live_ready": self._live_ready(),
            "language": self.language_code,
        }
