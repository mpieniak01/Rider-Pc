"""Mock REST adapter for testing purposes.

This adapter provides deterministic mock responses for all Rider-PI endpoints,
allowing local testing without requiring a real Rider-PI device.
"""

import logging
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class MockRestAdapter:
    """Mock adapter that returns deterministic test data instead of making real HTTP requests."""

    def __init__(
        self,
        base_url: str = "http://mock-rider-pi:8080",
        timeout: float = 5.0,
        secure_mode: bool = False,
        mtls_cert_path: Optional[str] = None,
        mtls_key_path: Optional[str] = None,
        mtls_ca_path: Optional[str] = None,
    ):
        """
        Initialize the mock REST adapter.

        Args are kept for API compatibility but not used in mock.
        """
        self.base_url = base_url
        self.timeout = timeout
        logger.info("MockRestAdapter initialized (TEST MODE)")

    async def fetch_binary(
        self, path: str, params: Optional[Dict[str, Any]] = None
    ) -> Tuple[bytes, str, Dict[str, str]]:
        """
        Return mock binary content (e.g., camera images).

        Returns:
            Tuple of (content bytes, media type, response headers)
        """
        # Small 2x2 PNG image (valid PNG format)
        # This is a minimal valid PNG file with a 2x2 pixel image
        # Format: PNG signature + IHDR chunk (2x2, RGBA) + IDAT chunk (compressed pixel data) + IEND chunk
        mock_image = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02"
            b"\x08\x06\x00\x00\x00\xf4x\xd4\xfa\x00\x00\x00\x19IDATx\x9cc```\xf8"
            b"\x0f\x04\x0c\x0c\x0c\x0c\x00\x01\x04\x01\x00tC^\x8f\x00\x00\x00\x00IEND"
            b"\xaeB`\x82"
        )
        headers = {
            "content-type": "image/png",
            "last-modified": "Thu, 01 Jan 2025 00:00:00 GMT",
        }
        return mock_image, "image/png", headers

    async def close(self):
        """Close the client (no-op for mock)."""
        logger.debug("MockRestAdapter closed")

    async def get_healthz(self) -> Dict[str, Any]:
        """Return mock health status."""
        return {"ok": True, "status": "healthy", "timestamp": time.time()}

    async def get_state(self) -> Dict[str, Any]:
        """Return mock state data."""
        return {
            "present": True,
            "mode": "auto",
            "tracking": {
                "mode": "none",
                "enabled": False,
                "target": None,
            },
            "navigator": {
                "active": False,
                "strategy": "standard",
                "state": "idle",
            },
        }

    async def get_sysinfo(self) -> Dict[str, Any]:
        """Return mock system info."""
        return {
            "hostname": "mock-rider-pi",
            "uptime": 123456,
            "cpu_percent": 25.5,
            "memory_percent": 45.2,
            "disk_percent": 60.0,
            "temperature": 45.0,
        }

    async def get_vision_snap_info(self) -> Dict[str, Any]:
        """Return mock vision snapshot info."""
        return {
            "last_snap": time.time() - 1.5,
            "fps": 30,
            "resolution": [1280, 720],
            "objects_detected": 0,
        }

    async def get_vision_obstacle(self) -> Dict[str, Any]:
        """Return mock obstacle data."""
        return {
            "detected": False,
            "distance": None,
            "confidence": 0.0,
            "timestamp": time.time(),
        }

    async def get_app_metrics(self) -> Dict[str, Any]:
        """Return mock app metrics."""
        return {
            "ok": True,
            "uptime": 123456,
            "requests_total": 1000,
            "errors_total": 5,
        }

    async def get_camera_resource(self) -> Dict[str, Any]:
        """Return mock camera resource info."""
        return {
            "name": "camera",
            "free": False,
            "holders": [
                {
                    "pid": 4242,
                    "cmd": "rider-cam",
                    "service": "rider-cam-preview.service",
                }
            ],
            "checked_at": time.time(),
        }

    async def get_motion_queue(self) -> Dict[str, Any]:
        """Return mock motion queue."""
        return {"items": [], "size": 0, "max_size": 100}

    async def get_voice_providers(self) -> Dict[str, Any]:
        """Return mock voice provider catalog."""
        return {
            "providers": [
                {"name": "mock-asr", "type": "asr", "available": True},
                {"name": "mock-tts", "type": "tts", "available": True},
            ]
        }

    async def test_voice_providers(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return mock provider test results."""
        return {"ok": True, "results": {"mock-asr": "success", "mock-tts": "success"}}

    async def post_voice_tts(self, payload: Dict[str, Any]) -> Tuple[bytes, str]:
        """Return mock TTS audio."""
        # Mock WAV file header (minimal valid WAV file with silence)
        # Format: RIFF header + WAV format chunk + data chunk
        # Parameters: 1 channel, 44100 Hz sample rate, 16-bit PCM, 0 bytes of audio data (silence)
        mock_wav = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        return mock_wav, "audio/wav"

    async def post_chat_send(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return mock chat response."""
        return {
            "response": "This is a mock chat response.",
            "timestamp": time.time(),
        }

    async def get_bus_health(self) -> Dict[str, Any]:
        """Return mock bus health."""
        return {
            "ok": True,
            "status": "healthy",
            "connections": 3,
        }

    async def get_ai_mode(self) -> Dict[str, Any]:
        """Return mock AI mode."""
        return {"mode": "auto", "available_modes": ["auto", "manual", "idle"]}

    async def set_ai_mode(self, mode: str) -> Dict[str, Any]:
        """Return success for AI mode change."""
        return {"ok": True, "mode": mode}

    async def get_providers_state(self) -> Dict[str, Any]:
        """Return mock provider state."""
        return {
            "vision": {
                "provider": "mock-vision",
                "status": "ready",
                "enabled": True,
            },
            "voice": {
                "provider": "mock-voice",
                "status": "ready",
                "enabled": True,
            },
            "text": {
                "provider": "mock-text",
                "status": "ready",
                "enabled": True,
            },
        }

    async def patch_provider(self, domain: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return success for provider update."""
        return {"ok": True, "domain": domain, "updated": True}

    async def get_providers_health(self) -> Dict[str, Any]:
        """Return mock provider health."""
        return {
            "vision": {"status": "healthy", "last_check": time.time()},
            "voice": {"status": "healthy", "last_check": time.time()},
            "text": {"status": "healthy", "last_check": time.time()},
        }

    async def get_remote_models(self) -> Dict[str, Any]:
        """Return mock Rider-Pi model list."""
        return {
            "models": [
                {
                    "name": "pi-vision-model",
                    "category": "vision",
                    "type": "yolo",
                    "path": "vision/pi-vision-model.pt",
                    "size_mb": 25.0,
                    "format": "pt",
                }
            ],
            "total": 1,
        }

    async def get_resource(self, resource_name: str) -> Dict[str, Any]:
        """Return mock resource status."""
        resources = {
            "mic": {"name": "mic", "free": True, "holders": []},
            "speaker": {"name": "speaker", "free": True, "holders": []},
            "camera": {
                "name": "camera",
                "free": False,
                "holders": [
                    {
                        "pid": 4242,
                        "cmd": "rider-cam",
                        "service": "rider-cam-preview.service",
                    }
                ],
            },
            "lcd": {"name": "lcd", "free": True, "holders": []},
        }
        return resources.get(
            resource_name,
            {"name": resource_name, "free": True, "holders": []},
        )

    async def post_resource_action(self, resource_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return success for resource action."""
        return {"ok": True, "resource": resource_name, "action": payload.get("action")}

    async def post_control(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Return success for control command."""
        return {"ok": True, "command": command.get("cmd"), "timestamp": time.time()}

    async def get_control_state(self) -> Dict[str, Any]:
        """Return mock control state."""
        return {
            "tracking": {
                "mode": "none",
                "enabled": False,
                "target": None,
            },
            "navigator": {
                "active": False,
                "strategy": "standard",
                "state": "idle",
            },
            "camera": {
                "vision_enabled": True,
                "on": True,
                "res": [1280, 720],
            },
        }

    async def post_pc_heartbeat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return success for provider heartbeat."""
        return {"ok": True, "registered": True, "timestamp": time.time()}

    async def post_tracking_mode(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return success for tracking mode change."""
        return {"ok": True, "mode": payload.get("mode"), "enabled": payload.get("enabled")}

    async def get_services(self) -> Dict[str, Any]:
        """Return mock systemd service list."""
        return {
            "services": [
                {
                    "unit": "rider-cam-preview.service",
                    "desc": "Camera preview pipeline",
                    "active": "active",
                    "sub": "running",
                    "enabled": "enabled",
                },
                {
                    "unit": "rider-edge-preview.service",
                    "desc": "Edge detection preview",
                    "active": "inactive",
                    "sub": "dead",
                    "enabled": "enabled",
                },
                {
                    "unit": "rider-vision.service",
                    "desc": "Vision main stack",
                    "active": "active",
                    "sub": "running",
                    "enabled": "enabled",
                },
                {
                    "unit": "rider-tracker.service",
                    "desc": "Vision tracker",
                    "active": "inactive",
                    "sub": "dead",
                    "enabled": "enabled",
                },
                {
                    "unit": "rider-tracking-controller.service",
                    "desc": "Tracking controller",
                    "active": "inactive",
                    "sub": "dead",
                    "enabled": "enabled",
                },
            ]
        }

    async def service_action(self, unit: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return success for service action."""
        return {"ok": True, "unit": unit, "action": payload.get("action")}
