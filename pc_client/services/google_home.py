"""Google Home integration service for Rider-PC.

This module provides native OAuth 2.0 flow and Smart Device Management (SDM) API
integration, allowing Rider-PC to directly communicate with Google Home devices
without proxying through Rider-Pi.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

# SDM API base URL
SDM_API_BASE = "https://smartdevicemanagement.googleapis.com/v1"

# OAuth endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

# Required OAuth scopes for SDM
SDM_SCOPES = [
    "https://www.googleapis.com/auth/sdm.service",
]


def _generate_code_verifier() -> str:
    """Generate a cryptographically random code verifier for PKCE."""
    return secrets.token_urlsafe(64)[:128]


def _generate_code_challenge(verifier: str) -> str:
    """Generate code challenge from verifier using S256 method."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class GoogleHomeService:
    """Service for Google Home integration via Smart Device Management API.

    Handles OAuth 2.0 flow with PKCE, token storage/refresh, and SDM API calls.
    Designed for web application flow where callback is handled by FastAPI endpoint.
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        project_id: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        tokens_path: Optional[str] = None,
        test_mode: bool = False,
    ):
        """Initialize Google Home service.

        Args:
            client_id: OAuth 2.0 client ID from Google Cloud Console
            client_secret: OAuth 2.0 client secret
            project_id: Device Access project ID (starts with enterprise prefix)
            redirect_uri: OAuth callback URI (e.g., http://localhost:8000/api/home/auth/callback)
            tokens_path: Path to JSON file for storing tokens
            test_mode: If True, skip real API calls and use mock data
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.project_id = project_id
        self.redirect_uri = redirect_uri
        self.tokens_path = Path(tokens_path) if tokens_path else Path("config/local/google_tokens_pc.json")
        self.test_mode = test_mode

        # In-memory token cache
        self._tokens: Optional[Dict[str, Any]] = None
        self._pending_auth: Dict[str, Dict[str, Any]] = {}  # state -> {verifier, created_at}
        self._pending_auth_lock = threading.Lock()  # Lock for thread-safe access to pending auth

        # Load existing tokens if available
        self._load_tokens()

        if test_mode:
            logger.info("GoogleHomeService initialized in TEST MODE")
        else:
            logger.info(
                "GoogleHomeService initialized (configured=%s, authenticated=%s)",
                self.is_configured(),
                self.is_authenticated(),
            )

    def is_configured(self) -> bool:
        """Check if all required OAuth credentials are configured."""
        return all([self.client_id, self.client_secret, self.project_id])

    def is_authenticated(self) -> bool:
        """Check if we have valid tokens (or unexpired tokens)."""
        if self.test_mode:
            return True
        if not self._tokens:
            return False
        # Check if refresh token exists (access tokens can be refreshed)
        if not self._tokens.get("refresh_token"):
            return False
        return True

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive authentication status.

        Returns:
            Dict with keys: configured, authenticated, auth_url_available, profile, error
        """
        if self.test_mode:
            return {
                "configured": True,
                "authenticated": True,
                "auth_url_available": True,
                "profile": {"email": "mock@rider.test", "name": "Test User"},
                "error": None,
            }

        configured = self.is_configured()
        authenticated = self.is_authenticated()

        profile = None
        if authenticated and self._tokens:
            profile = self._tokens.get("profile")

        return {
            "configured": configured,
            "authenticated": authenticated,
            "auth_url_available": configured and not authenticated,
            "profile": profile,
            "error": None if configured else "auth_env_missing",
        }

    def build_auth_url(self, state: Optional[str] = None) -> Dict[str, Any]:
        """Build OAuth authorization URL with PKCE.

        Args:
            state: Optional state parameter for CSRF protection

        Returns:
            Dict with keys: ok, auth_url, state, expires_at
        """
        if not self.is_configured():
            return {"ok": False, "error": "auth_env_missing", "auth_url": None}

        if not state:
            state = secrets.token_urlsafe(32)

        # Generate PKCE parameters
        code_verifier = _generate_code_verifier()
        code_challenge = _generate_code_challenge(code_verifier)

        # Store pending auth session
        self._pending_auth[state] = {
            "verifier": code_verifier,
            "created_at": time.time(),
        }

        # Clean up old pending sessions (older than 10 minutes)
        self._cleanup_pending_auth()

        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(SDM_SCOPES),
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

        auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
        expires_at = time.time() + 600  # 10 minutes validity

        logger.info("Generated OAuth URL for state=%s", state[:8])
        return {
            "ok": True,
            "auth_url": auth_url,
            "state": state,
            "expires_at": expires_at,
        }

    async def complete_auth(self, code: str, state: str) -> Dict[str, Any]:
        """Exchange authorization code for tokens.

        Args:
            code: Authorization code from OAuth callback
            state: State parameter for verification

        Returns:
            Dict with keys: ok, profile, error
        """
        if self.test_mode:
            self._tokens = {
                "access_token": "mock_access_token",
                "refresh_token": "mock_refresh_token",
                "expires_at": time.time() + 3600,
                "profile": {"email": "mock@rider.test", "name": "Test User"},
            }
            return {"ok": True, "profile": self._tokens["profile"]}

        # Verify state and get verifier (thread-safe)
        with self._pending_auth_lock:
            pending = self._pending_auth.pop(state, None)
        if not pending:
            logger.warning("Invalid or expired OAuth state: %s", state[:8] if state else "None")
            return {"ok": False, "error": "invalid_state"}

        code_verifier = pending["verifier"]

        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    GOOGLE_TOKEN_URL,
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "code": code,
                        "code_verifier": code_verifier,
                        "grant_type": "authorization_code",
                        "redirect_uri": self.redirect_uri,
                    },
                    timeout=30.0,
                )

                if response.status_code != 200:
                    try:
                        error_data = response.json() if response.content else {}
                    except json.JSONDecodeError:
                        error_data = {}
                    error = error_data.get("error", f"http_{response.status_code}")
                    logger.error("Token exchange failed: %s - %s", response.status_code, error)
                    return {"ok": False, "error": error}

                try:
                    token_data = response.json()
                except json.JSONDecodeError as e:
                    logger.error("Invalid JSON in token response: %s", e)
                    return {"ok": False, "error": "invalid_response"}

            except httpx.RequestError as e:
                logger.error("Network error during token exchange: %s", e)
                return {"ok": False, "error": "network_error"}

        # Store tokens
        self._tokens = {
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "expires_at": time.time() + token_data.get("expires_in", 3600),
            "scope": token_data.get("scope"),
            "profile": None,  # Will be fetched if needed
        }

        self._save_tokens()
        logger.info("OAuth tokens obtained and saved successfully")

        return {"ok": True, "profile": self._tokens.get("profile")}

    async def _refresh_token_if_needed(self) -> bool:
        """Refresh access token if expired or about to expire.

        Returns:
            True if token is valid or refreshed successfully
        """
        if self.test_mode:
            return True

        if not self._tokens or not self._tokens.get("refresh_token"):
            return False

        # Check if token expires in less than 5 minutes
        expires_at = self._tokens.get("expires_at", 0)
        if time.time() < expires_at - 300:
            return True  # Token still valid

        logger.info("Refreshing access token...")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    GOOGLE_TOKEN_URL,
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "refresh_token": self._tokens["refresh_token"],
                        "grant_type": "refresh_token",
                    },
                    timeout=30.0,
                )

                if response.status_code != 200:
                    logger.error("Token refresh failed: %s", response.status_code)
                    return False

                token_data = response.json()

            except httpx.RequestError as e:
                logger.error("Network error during token refresh: %s", e)
                return False

        # Update tokens (refresh_token might not be included in refresh response)
        self._tokens["access_token"] = token_data.get("access_token")
        self._tokens["expires_at"] = time.time() + token_data.get("expires_in", 3600)
        if token_data.get("refresh_token"):
            self._tokens["refresh_token"] = token_data["refresh_token"]

        self._save_tokens()
        logger.info("Access token refreshed successfully")
        return True

    async def list_devices(self) -> Dict[str, Any]:
        """Fetch devices from Smart Device Management API.

        Returns:
            Dict with keys: ok, devices, error
        """
        if self.test_mode:
            return {
                "ok": True,
                "devices": [
                    {
                        "name": f"enterprises/{self.project_id}/devices/mock-light-1",
                        "type": "action.devices.types.LIGHT",
                        "traits": {
                            "sdm.devices.traits.OnOff": {"on": True},
                            "sdm.devices.traits.Brightness": {"brightness": 75},
                        },
                        "customName": "Mock Light",
                        "room": "Living Room",
                    },
                    {
                        "name": f"enterprises/{self.project_id}/devices/mock-thermostat-1",
                        "type": "action.devices.types.THERMOSTAT",
                        "traits": {
                            "sdm.devices.traits.TemperatureSetting": {
                                "thermostatTemperatureSetpoint": 21.0,
                                "thermostatTemperatureAmbient": 20.5,
                                "availableThermostatModes": ["heat", "cool", "off"],
                            },
                        },
                        "customName": "Mock Thermostat",
                        "room": "Hallway",
                    },
                ],
            }

        if not self.is_authenticated():
            return {"ok": False, "error": "not_authenticated", "devices": []}

        if not await self._refresh_token_if_needed():
            return {"ok": False, "error": "token_refresh_failed", "devices": []}

        url = f"{SDM_API_BASE}/enterprises/{self.project_id}/devices"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {self._tokens['access_token']}"},
                    timeout=30.0,
                )

                if response.status_code == 401:
                    logger.warning("SDM API returned 401 - tokens may be revoked")
                    return {"ok": False, "error": "access_denied", "devices": []}

                if response.status_code == 403:
                    logger.warning("SDM API returned 403 - insufficient permissions")
                    return {"ok": False, "error": "access_denied", "devices": []}

                if response.status_code != 200:
                    logger.error("SDM API error: %s", response.status_code)
                    return {"ok": False, "error": f"sdm_error_{response.status_code}", "devices": []}

                try:
                    data = response.json()
                except json.JSONDecodeError:
                    logger.error("Invalid JSON response from SDM API")
                    return {"ok": False, "error": "invalid_response", "devices": []}
                devices = data.get("devices", [])

                # Transform device data for UI
                transformed = []
                for device in devices:
                    transformed.append(
                        {
                            "name": device.get("name", ""),
                            "type": device.get("type", ""),
                            "traits": device.get("traits", {}),
                            "customName": device.get("parentRelations", [{}])[0].get("displayName", ""),
                            "room": device.get("parentRelations", [{}])[0].get("displayName", ""),
                        }
                    )

                logger.info("Fetched %d devices from SDM API", len(transformed))
                return {"ok": True, "devices": transformed}

            except httpx.RequestError as e:
                logger.error("Network error fetching devices: %s", e)
                return {"ok": False, "error": "network_error", "devices": []}

    async def send_command(
        self, device_id: str, command: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute command on a device via SDM API.

        Args:
            device_id: Full device name (e.g., enterprises/project-id/devices/device-id)
            command: Command name (e.g., action.devices.commands.OnOff)
            params: Command parameters

        Returns:
            Dict with keys: ok, device, command, error
        """
        if self.test_mode:
            logger.info("TEST MODE: Would send command %s to %s with params %s", command, device_id, params)
            return {"ok": True, "device": device_id, "command": command}

        if not self.is_authenticated():
            return {"ok": False, "error": "not_authenticated"}

        if not await self._refresh_token_if_needed():
            return {"ok": False, "error": "token_refresh_failed"}

        # Map UI command format to SDM format
        sdm_command = self._map_command_to_sdm(command)
        if not sdm_command:
            return {"ok": False, "error": "unsupported_command"}

        url = f"{SDM_API_BASE}/{device_id}:executeCommand"

        payload = {
            "command": sdm_command,
            "params": params or {},
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self._tokens['access_token']}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=30.0,
                )

                if response.status_code == 401:
                    return {"ok": False, "error": "access_denied"}

                if response.status_code == 429:
                    return {"ok": False, "error": "quota_exceeded"}

                if response.status_code not in (200, 204):
                    logger.error("SDM command error: %s - %s", response.status_code, response.text)
                    return {"ok": False, "error": f"sdm_error_{response.status_code}"}

                logger.info("Command %s sent to %s successfully", command, device_id)
                return {"ok": True, "device": device_id, "command": command}

            except httpx.RequestError as e:
                logger.error("Network error sending command: %s", e)
                return {"ok": False, "error": "network_error"}

    def _map_command_to_sdm(self, command: str) -> Optional[str]:
        """Map UI command format to SDM API command format."""
        # SDM uses different command prefixes
        command_mapping = {
            "action.devices.commands.OnOff": "sdm.devices.commands.OnOff.SetOnOff",
            "action.devices.commands.BrightnessAbsolute": "sdm.devices.commands.Brightness.SetBrightness",
            "action.devices.commands.ColorAbsolute": "sdm.devices.commands.ColorSetting.SetColor",
            "action.devices.commands.ThermostatTemperatureSetpoint": "sdm.devices.commands.ThermostatTemperatureSetting.SetTemperature",
            "action.devices.commands.ThermostatSetMode": "sdm.devices.commands.ThermostatMode.SetMode",
            "action.devices.commands.StartStop": "sdm.devices.commands.StartStop.SetRunning",
            "action.devices.commands.PauseUnpause": "sdm.devices.commands.StartStop.SetPaused",
            "action.devices.commands.Dock": "sdm.devices.commands.Dock.Dock",
        }
        return command_mapping.get(command, command)

    def logout(self) -> Dict[str, Any]:
        """Clear stored tokens and logout.

        Returns:
            Dict with keys: ok
        """
        self._tokens = None
        if self.tokens_path.exists():
            try:
                self.tokens_path.unlink()
                logger.info("Tokens file deleted: %s", self.tokens_path)
            except OSError as e:
                logger.warning("Failed to delete tokens file: %s", e)

        return {"ok": True}

    def _load_tokens(self) -> None:
        """Load tokens from file if available."""
        if self.test_mode:
            return

        if not self.tokens_path.exists():
            return

        try:
            with open(self.tokens_path, "r") as f:
                self._tokens = json.load(f)
                logger.debug("Loaded tokens from %s", self.tokens_path)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load tokens: %s", e)
            self._tokens = None

    def _save_tokens(self) -> None:
        """Save tokens to file."""
        if self.test_mode or not self._tokens:
            return

        try:
            # Ensure directory exists
            self.tokens_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.tokens_path, "w") as f:
                json.dump(self._tokens, f, indent=2)
                logger.debug("Saved tokens to %s", self.tokens_path)
            # Set restrictive file permissions for OAuth tokens (owner-only read/write)
            os.chmod(self.tokens_path, 0o600)
        except OSError as e:
            logger.error("Failed to save tokens: %s", e)

    def _cleanup_pending_auth(self, max_age: float = 600.0) -> None:
        """Remove expired pending auth sessions."""
        now = time.time()
        expired = [
            state for state, data in self._pending_auth.items() if now - data.get("created_at", 0) > max_age
        ]
        for state in expired:
            del self._pending_auth[state]
            logger.debug("Cleaned up expired auth state: %s", state[:8])


# Singleton instance for global access
_service_instance: Optional[GoogleHomeService] = None
_service_lock = threading.Lock()


def get_google_home_service(
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    project_id: Optional[str] = None,
    redirect_uri: Optional[str] = None,
    tokens_path: Optional[str] = None,
    test_mode: bool = False,
    reset: bool = False,
) -> GoogleHomeService:
    """Get or create GoogleHomeService singleton instance.

    Args:
        client_id: OAuth client ID (uses env var if not provided)
        client_secret: OAuth client secret (uses env var if not provided)
        project_id: Device Access project ID (uses env var if not provided)
        redirect_uri: OAuth callback URI (uses env var if not provided)
        tokens_path: Path for token storage
        test_mode: Enable test mode with mock responses
        reset: Force creation of new instance

    Returns:
        GoogleHomeService instance
    """
    global _service_instance

    if _service_instance is None or reset:
        with _service_lock:
            # Double-check after acquiring lock
            if _service_instance is None or reset:
                # Read from environment if not provided
                client_id = client_id or os.getenv("GOOGLE_CLIENT_ID")
                client_secret = client_secret or os.getenv("GOOGLE_CLIENT_SECRET")
                project_id = project_id or os.getenv("GOOGLE_DEVICE_ACCESS_PROJECT_ID")
                redirect_uri = redirect_uri or os.getenv(
                    "GOOGLE_HOME_REDIRECT_URI", "http://localhost:8000/api/home/auth/callback"
                )
                tokens_path = tokens_path or os.getenv("GOOGLE_HOME_TOKENS_PATH", "config/local/google_tokens_pc.json")

                _service_instance = GoogleHomeService(
                    client_id=client_id,
                    client_secret=client_secret,
                    project_id=project_id,
                    redirect_uri=redirect_uri,
                    tokens_path=tokens_path,
                    test_mode=test_mode,
                )

    return _service_instance


def reset_google_home_service() -> None:
    """Reset the singleton instance (useful for testing)."""
    global _service_instance
    with _service_lock:
        _service_instance = None
