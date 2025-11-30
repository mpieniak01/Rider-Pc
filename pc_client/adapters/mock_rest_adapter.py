"""Mock REST adapter for testing purposes.

This adapter provides deterministic mock responses for all Rider-PI endpoints,
allowing local testing without requiring a real Rider-PI device.
"""

import copy
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
        now = time.time()
        self._control_state = {
            "present": True,
            "mode": "auto",
            "tracking": {"mode": "none", "enabled": False, "target": None},
            "navigator": {"active": False, "strategy": "standard", "state": "idle"},
            "camera": {"vision_enabled": True, "on": True, "res": [1280, 720]},
        }
        self._ai_mode = {"mode": "pc_offload", "available_modes": ["pc_offload", "local"], "changed_ts": now - 120}
        self._provider_state = {
            "domains": {
                "vision": {"mode": "pc", "status": "ready", "changed_ts": now - 300, "reason": "mock"},
                "voice": {"mode": "local", "status": "ready", "changed_ts": now - 600, "reason": "mock"},
                "text": {"mode": "pc", "status": "ready", "changed_ts": now - 30, "reason": "sync"},
            },
            "pc_health": {"reachable": True, "status": "ok", "latency_ms": 12.4},
        }
        self._provider_health = {
            "vision": {"status": "ok", "latency_ms": 11.2, "success_rate": 0.99, "last_check": now - 5},
            "voice": {"status": "warn", "latency_ms": 32.5, "success_rate": 0.93, "last_check": now - 15},
            "text": {"status": "ok", "latency_ms": 8.7, "success_rate": 0.98, "last_check": now - 9},
        }
        self._motion_queue: list[Dict[str, Any]] = [
            {
                "ts": now - 1.5,
                "source": "pc-ui",
                "status": "move",
                "vx": 0.12,
                "vy": 0.0,
                "yaw": 0.05,
            },
            {
                "ts": now - 3.0,
                "source": "pc-ui",
                "status": "rotate",
                "vx": 0.0,
                "vy": 0.0,
                "yaw": 0.2,
            },
        ]
        self._remote_models = [
            {"name": "pi-vision-prod", "category": "vision", "type": "onnx", "format": "onnx", "size_mb": 32.1},
            {"name": "pi-asr-lo", "category": "voice_asr", "type": "whisper", "format": "en", "size_mb": 42.4},
            {"name": "pi-tts-hi", "category": "voice_tts", "type": "piper", "format": "onnx", "size_mb": 48.9},
            {"name": "pi-utils", "category": "unknown", "type": "custom", "format": "bin", "size_mb": 12.3},
        ]
        self._services = [
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
        self._logic_blueprints = [
            {
                "name": "s0_manual",
                "scenario": "S0",
                "title": "Stan 0 – Sterowanie ręczne",
                "description": "Podstawowy zestaw usług do sterowania manualnego.",
                "units": ["rider-cam-preview.service", "rider-edge-preview.service"],
                "default_active": True,
            },
            {
                "name": "s3_follow_me_face",
                "scenario": "S3",
                "title": "Śledzenie (twarz)",
                "description": "Tracker i kontroler ruchu pod Follow Me.",
                "units": ["rider-tracker.service", "rider-tracking-controller.service"],
                "default_active": False,
            },
            {
                "name": "s4_recon",
                "scenario": "S4",
                "title": "Rekonesans autonomiczny",
                "description": "Navigator oraz procesy mapowania.",
                "units": ["rider-vision.service"],
                "default_active": False,
            },
        ]
        self._feature_state = {bp["name"]: bool(bp.get("default_active")) for bp in self._logic_blueprints}
        self._home_state = {
            "authenticated": True,
            "profile": {"email": "mock-user@rider.ai", "name": "Mock User"},
            "scopes": ["homegraph", "cloud-control"],
        }
        self._home_devices = [
            {
                "name": "devices/light/living-room",
                "type": "action.devices.types.LIGHT",
                "traits": {
                    "sdm.devices.traits.OnOff": {"on": True},
                    "sdm.devices.traits.Brightness": {"brightness": 70},
                    "sdm.devices.traits.ColorSetting": {"color": {"temperatureK": 3200, "spectrumRgb": 0x33DDFF}},
                },
            },
            {
                "name": "devices/thermostat/studio",
                "type": "action.devices.types.THERMOSTAT",
                "traits": {
                    "sdm.devices.traits.ThermostatMode": {
                        "mode": "heatcool",
                        "availableModes": ["off", "heat", "cool", "heatcool"],
                    },
                    "sdm.devices.traits.ThermostatTemperatureSetpoint": {"heatCelsius": 20.0, "coolCelsius": 24.0},
                    "sdm.devices.traits.Temperature": {"ambientTemperatureCelsius": 21.2},
                },
            },
            {
                "name": "devices/vacuum/dusty",
                "type": "action.devices.types.VACUUM",
                "traits": {
                    "sdm.devices.traits.StartStop": {"isRunning": False, "isPaused": False},
                    "sdm.devices.traits.Dock": {"available": True},
                },
            },
        ]

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
        return copy.deepcopy(self._control_state)

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
            "timestamp": time.time(),
            "groups": {
                "control": {"ok": 48, "error": 2},
                "navigator": {"ok": 32, "error": 0},
                "google_home": {"ok": 5, "error": 1},
                "chat": {"ok": 11, "error": 0},
                "face": {"ok": 8, "error": 0},
            },
            "total_errors": 3,
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
        items = []
        now = time.time()
        for entry in reversed(self._motion_queue[-10:]):
            age = round(max(0.0, now - entry.get("ts", now)), 2)
            items.append(
                {
                    "source": entry.get("source", "pc-ui"),
                    "status": entry.get("status", "queued"),
                    "vx": entry.get("vx"),
                    "vy": entry.get("vy"),
                    "yaw": entry.get("yaw"),
                    "age_s": age,
                }
            )
        return {"items": items, "size": len(items), "max_size": 100, "generated_at": now}

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
        return copy.deepcopy(self._ai_mode)

    async def set_ai_mode(self, mode: str) -> Dict[str, Any]:
        """Return success for AI mode change."""
        self._ai_mode["mode"] = mode
        self._ai_mode["changed_ts"] = time.time()
        return {"ok": True, **self._ai_mode}

    async def get_providers_state(self) -> Dict[str, Any]:
        """Return mock provider state with flattened domain keys for convenience."""
        state = copy.deepcopy(self._provider_state)
        domains = state.get("domains", {})
        flattened = {name: info for name, info in domains.items()}
        flattened["domains"] = domains
        flattened["pc_health"] = state.get("pc_health", {})
        return flattened

    async def patch_provider(self, domain: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return success for provider update."""
        target = str(payload.get("target", "local")).lower()
        state = self._provider_state.setdefault("domains", {}).setdefault(
            domain, {"mode": "local", "status": "local_only", "changed_ts": None}
        )
        state["mode"] = target
        state["status"] = "pc_active" if target == "pc" else "local_only"
        state["changed_ts"] = time.time()
        return {"ok": True, "domain": domain, "mode": target}

    async def get_providers_health(self) -> Dict[str, Any]:
        """Return mock provider health."""
        return copy.deepcopy(self._provider_health)

    async def get_remote_models(self) -> Dict[str, Any]:
        """Return mock Rider-Pi model list."""
        return {"models": copy.deepcopy(self._remote_models), "total": len(self._remote_models)}

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
        entry = {
            "ts": time.time(),
            "source": command.get("source", "pc-ui"),
            "status": command.get("cmd", "idle"),
            "vx": command.get("vx"),
            "vy": command.get("vy"),
            "yaw": command.get("yaw"),
        }
        self._motion_queue.append(entry)
        self._motion_queue[:] = self._motion_queue[-20:]
        return {
            "ok": True,
            "command": command.get("cmd"),
            "queued": len(self._motion_queue),
            "timestamp": entry["ts"],
        }

    async def get_control_state(self) -> Dict[str, Any]:
        """Return mock control state."""
        state = copy.deepcopy(self._control_state)
        state["updated_at"] = time.time()
        return state

    async def post_pc_heartbeat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return success for provider heartbeat."""
        return {"ok": True, "registered": True, "timestamp": time.time()}

    async def post_tracking_mode(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return success for tracking mode change."""
        mode = str(payload.get("mode", "none"))
        enabled = bool(payload.get("enabled", mode != "none"))
        self._control_state["tracking"] = {"mode": mode, "enabled": enabled, "target": payload.get("target")}
        return {"ok": True, "mode": mode, "enabled": enabled}

    async def get_services(self) -> Dict[str, Any]:
        """Return mock systemd service list."""
        return {"services": copy.deepcopy(self._services), "timestamp": time.time()}

    async def service_action(self, unit: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return success for service action."""
        action = (payload or {}).get("action")
        svc = next((s for s in self._services if s["unit"] == unit), None)
        if not svc:
            return {"ok": False, "error": "service_not_found"}
        if action == "start":
            svc["active"] = "active"
            svc["sub"] = "running"
        elif action == "stop":
            svc["active"] = "inactive"
            svc["sub"] = "dead"
        elif action == "restart":
            svc["active"] = "active"
            svc["sub"] = "running"
        elif action == "enable":
            svc["enabled"] = "enabled"
        elif action == "disable":
            svc["enabled"] = "disabled"
        else:
            return {"ok": False, "error": "unsupported_action"}
        return {"ok": True, "unit": unit, "action": action}

    def _service_snapshot(self, unit: str) -> Dict[str, Any]:
        svc = next((s for s in self._services if s["unit"] == unit), None)
        if not svc:
            return {
                "unit": unit,
                "desc": "",
                "active": "inactive",
                "sub": "dead",
                "enabled": "enabled",
                "is_active": False,
            }
        active_flag = str(svc.get("active", "")).startswith("active")
        snapshot = dict(svc)
        snapshot["is_active"] = active_flag
        return snapshot

    def _logic_feature_rows(self) -> list[Dict[str, Any]]:
        rows: list[Dict[str, Any]] = []
        for bp in self._logic_blueprints:
            services = [self._service_snapshot(unit) for unit in bp.get("units", [])]
            total = len(services)
            active_count = sum(1 for svc in services if svc.get("is_active"))
            name = bp["name"]
            rows.append(
                {
                    "name": name,
                    "scenario": bp.get("scenario"),
                    "title": bp.get("title"),
                    "description": bp.get("description"),
                    "services": services,
                    "services_total": total,
                    "services_active": active_count,
                    "active": self._feature_state.get(name, False),
                }
            )
        return rows

    def _logic_summary_payload(self) -> Dict[str, Any]:
        rows = self._logic_feature_rows()
        active = [row["name"] for row in rows if row.get("active")]
        partial = [row["name"] for row in rows if row.get("services_active")]
        return {
            "features": rows,
            "active": active,
            "partial": partial,
            "counts": {"total": len(rows), "active": len(active), "partial": len(partial)},
        }

    async def get_logic_features(self) -> Dict[str, Any]:
        """Return mock feature registry."""
        return {"ok": True, "features": self._logic_feature_rows()}

    async def get_logic_summary(self) -> Dict[str, Any]:
        """Return mock logic summary payload."""
        return {"ok": True, "summary": self._logic_summary_payload()}

    async def post_feature_toggle(self, name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Toggle feature state in mock registry."""
        normalized = str(name or "").strip()
        if normalized not in self._feature_state:
            return {"ok": False, "error": "unknown_feature"}
        enabled = bool(payload.get("enabled"))
        self._feature_state[normalized] = enabled
        if normalized == "s3_follow_me_face":
            self._control_state["tracking"] = {"mode": "face", "enabled": enabled, "target": "auto"}
        elif normalized == "s4_recon":
            self._control_state["navigator"]["active"] = enabled
            self._control_state["navigator"]["state"] = "navigating" if enabled else "idle"
        elif normalized == "s0_manual" and enabled:
            for other in self._feature_state:
                if other != "s0_manual":
                    self._feature_state[other] = False
        return {"ok": True, "feature": normalized, "enabled": enabled}

    async def get_home_status(self) -> Dict[str, Any]:
        """Return mock Google Home auth state."""
        return copy.deepcopy(self._home_state)

    async def get_home_devices(self) -> Dict[str, Any]:
        """Return mock Google Home devices."""
        return {"ok": True, "devices": copy.deepcopy(self._home_devices)}

    async def post_home_command(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Apply mock Google Home command."""
        device_id = payload.get("deviceId")
        command = payload.get("command")
        params = payload.get("params") or {}
        device = next((d for d in self._home_devices if d.get("name") == device_id), None)
        if not device:
            return {"ok": False, "error": "device_not_found"}
        traits = device.setdefault("traits", {})
        if command == "action.devices.commands.OnOff":
            traits.setdefault("sdm.devices.traits.OnOff", {})["on"] = bool(params.get("on"))
        elif command == "action.devices.commands.BrightnessAbsolute":
            traits.setdefault("sdm.devices.traits.Brightness", {})["brightness"] = int(params.get("brightness", 0))
        elif command == "action.devices.commands.ColorAbsolute":
            traits.setdefault("sdm.devices.traits.ColorSetting", {})["color"] = params.get("color", {})
        elif command == "action.devices.commands.ThermostatTemperatureSetpoint":
            traits.setdefault("sdm.devices.traits.ThermostatTemperatureSetpoint", {}).update(params)
        elif command == "action.devices.commands.StartStop":
            traits.setdefault("sdm.devices.traits.StartStop", {}).update(
                {"isRunning": bool(params.get("start")), "isPaused": False}
            )
        elif command == "action.devices.commands.PauseUnpause":
            traits.setdefault("sdm.devices.traits.StartStop", {}).update({"isPaused": bool(params.get("pause"))})
        elif command == "action.devices.commands.Dock":
            traits.setdefault("sdm.devices.traits.Dock", {})["lastDockTs"] = time.time()
        return {"ok": True, "device": device_id, "command": command}

    async def post_home_auth(self) -> Dict[str, Any]:
        """Simulate successful Google auth."""
        self._home_state["authenticated"] = True
        self._home_state.setdefault("profile", {})["updated_at"] = time.time()
        return {"ok": True, "profile": self._home_state.get("profile")}
