"""Google Home Service for Rider-PC.

This module provides native Google Smart Device Management (SDM) integration,
enabling OAuth 2.0 authentication flow and device control directly from Rider-PC.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

# Google OAuth endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
SDM_API_BASE = "https://smartdevicemanagement.googleapis.com/v1"

# Required scopes for Google Home / SDM
SDM_SCOPES = [
    "https://www.googleapis.com/auth/sdm.service",
]

# PKCE configuration constants
AUTH_SESSION_TTL_SECONDS = 600  # 10 minutes for auth session validity
PKCE_STATE_LENGTH = 32  # Length of state token for CSRF protection
PKCE_VERIFIER_RAW_LENGTH = 64  # Raw length for code verifier generation
PKCE_VERIFIER_MAX_LENGTH = 128  # Max length for code verifier (PKCE spec)

# Cache configuration
DEVICE_CACHE_TTL_SECONDS = 300  # 5 minutes cache for device list
TOKEN_EXPIRY_BUFFER_SECONDS = 300  # Refresh token 5 minutes before expiry


@dataclass
class GoogleHomeConfig:
    """Configuration for Google Home integration."""

    # OAuth credentials (from Google Cloud Console)
    client_id: str = ""
    client_secret: str = ""

    # Device Access Project ID (from device-access.cloud.google.com)
    project_id: str = ""

    # Redirect URL for OAuth callback (must match Google Cloud Console config)
    redirect_uri: str = ""

    # Path to store tokens locally
    tokens_path: str = "config/local/google_tokens_pc.json"

    # Enable test mode (uses mock data instead of real API)
    test_mode: bool = False

    @classmethod
    def from_env(cls) -> "GoogleHomeConfig":
        """Create config from environment variables."""
        return cls(
            client_id=os.getenv("GOOGLE_HOME_CLIENT_ID", ""),
            client_secret=os.getenv("GOOGLE_HOME_CLIENT_SECRET", ""),
            project_id=os.getenv("GOOGLE_HOME_PROJECT_ID", ""),
            redirect_uri=os.getenv("GOOGLE_HOME_REDIRECT_URI", ""),
            tokens_path=os.getenv("GOOGLE_HOME_TOKENS_PATH", "config/local/google_tokens_pc.json"),
            test_mode=os.getenv("GOOGLE_HOME_TEST_MODE", "false").lower() == "true",
        )

    def is_configured(self) -> bool:
        """Check if all required OAuth fields are set."""
        return bool(self.client_id and self.client_secret and self.project_id and self.redirect_uri)


@dataclass
class AuthSession:
    """OAuth authentication session data."""

    state: str = ""
    code_verifier: str = ""
    code_challenge: str = ""
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0

    @classmethod
    def create(cls, ttl_seconds: int = AUTH_SESSION_TTL_SECONDS) -> "AuthSession":
        """Create a new auth session with PKCE parameters."""
        state = secrets.token_urlsafe(PKCE_STATE_LENGTH)
        code_verifier = secrets.token_urlsafe(PKCE_VERIFIER_RAW_LENGTH)[:PKCE_VERIFIER_MAX_LENGTH]

        # Create code_challenge using S256 method (base64url encoding without padding)
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

        now = time.time()
        return cls(
            state=state,
            code_verifier=code_verifier,
            code_challenge=code_challenge,
            created_at=now,
            expires_at=now + ttl_seconds,
        )

    def is_valid(self) -> bool:
        """Check if session is still valid."""
        return time.time() < self.expires_at


@dataclass
class TokenData:
    """OAuth token storage."""

    access_token: str = ""
    refresh_token: str = ""
    token_type: str = "Bearer"
    expires_at: float = 0.0
    scopes: List[str] = field(default_factory=list)
    profile_email: str = ""

    def is_expired(self) -> bool:
        """Check if access token is expired (with buffer before expiry)."""
        return time.time() > (self.expires_at - TOKEN_EXPIRY_BUFFER_SECONDS)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_at": self.expires_at,
            "scopes": self.scopes,
            "profile_email": self.profile_email,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TokenData":
        """Create from dictionary."""
        return cls(
            access_token=data.get("access_token", ""),
            refresh_token=data.get("refresh_token", ""),
            token_type=data.get("token_type", "Bearer"),
            expires_at=data.get("expires_at", 0.0),
            scopes=data.get("scopes", []),
            profile_email=data.get("profile_email", ""),
        )


class GoogleHomeService:
    """Service for Google Home / SDM integration.

    Provides:
    - OAuth 2.0 Authorization Code flow with PKCE
    - Token storage and automatic refresh
    - Device listing and command execution via SDM API

    Usage:
        service = GoogleHomeService(config)
        if service.is_configured() and not service.is_authenticated():
            auth_url = service.get_auth_url()
            # Redirect user to auth_url
        # After callback:
        await service.complete_auth(code, state)
        devices = await service.list_devices()
    """

    def __init__(self, config: Optional[GoogleHomeConfig] = None):
        """Initialize the Google Home service.

        Args:
            config: Configuration object. If None, loads from environment.
        """
        self.config = config or GoogleHomeConfig.from_env()
        self._tokens: Optional[TokenData] = None
        self._auth_session: Optional[AuthSession] = None
        self._devices_cache: List[Dict[str, Any]] = []
        self._cache_timestamp: float = 0.0
        self._http_client: Optional[httpx.AsyncClient] = None

        # Load tokens from disk if available
        self._load_tokens()

    def is_configured(self) -> bool:
        """Check if Google Home integration is configured."""
        return self.config.is_configured()

    def is_authenticated(self) -> bool:
        """Check if we have valid authentication."""
        if not self._tokens:
            return False
        if not self._tokens.refresh_token:
            return False
        return True

    def get_status(self) -> Dict[str, Any]:
        """Get current authentication status."""
        if self.config.test_mode:
            return {
                "configured": True,
                "authenticated": True,
                "test_mode": True,
                "profile": {"email": "test@example.com"},
                "auth_url_available": False,
            }

        if not self.is_configured():
            return {
                "configured": False,
                "authenticated": False,
                "test_mode": False,
                "profile": None,
                "auth_url_available": False,
                "config_missing": self._get_missing_config(),
            }

        return {
            "configured": True,
            "authenticated": self.is_authenticated(),
            "test_mode": False,
            "profile": {"email": self._tokens.profile_email} if self._tokens else None,
            "auth_url_available": True,
            "token_expires_at": self._tokens.expires_at if self._tokens else None,
        }

    def _get_missing_config(self) -> List[str]:
        """Get list of missing configuration fields."""
        missing = []
        if not self.config.client_id:
            missing.append("GOOGLE_HOME_CLIENT_ID")
        if not self.config.client_secret:
            missing.append("GOOGLE_HOME_CLIENT_SECRET")
        if not self.config.project_id:
            missing.append("GOOGLE_HOME_PROJECT_ID")
        if not self.config.redirect_uri:
            missing.append("GOOGLE_HOME_REDIRECT_URI")
        return missing

    def start_auth_session(self) -> Dict[str, Any]:
        """Start a new OAuth authentication session.

        Returns:
            Dict with auth_url and session metadata.
        """
        if not self.is_configured():
            return {"ok": False, "error": "not_configured", "missing": self._get_missing_config()}

        self._auth_session = AuthSession.create()

        params = {
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "response_type": "code",
            "scope": " ".join(SDM_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": self._auth_session.state,
            "code_challenge": self._auth_session.code_challenge,
            "code_challenge_method": "S256",
        }

        auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

        return {
            "ok": True,
            "auth_url": auth_url,
            "state": self._auth_session.state,
            "expires_at": self._auth_session.expires_at,
        }

    async def complete_auth(self, code: str, state: str) -> Dict[str, Any]:
        """Complete OAuth flow by exchanging authorization code for tokens.

        Args:
            code: Authorization code from Google callback.
            state: State parameter for CSRF validation.

        Returns:
            Dict with success status and profile info.
        """
        # Validate state
        if not self._auth_session or self._auth_session.state != state:
            return {"ok": False, "error": "invalid_state"}

        if not self._auth_session.is_valid():
            return {"ok": False, "error": "session_expired"}

        # Exchange code for tokens
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    GOOGLE_TOKEN_URL,
                    data={
                        "client_id": self.config.client_id,
                        "client_secret": self.config.client_secret,
                        "code": code,
                        "code_verifier": self._auth_session.code_verifier,
                        "grant_type": "authorization_code",
                        "redirect_uri": self.config.redirect_uri,
                    },
                )

                if response.status_code != 200:
                    error_data = response.json() if response.content else {}
                    logger.error("Token exchange failed: %s", error_data)
                    return {
                        "ok": False,
                        "error": "token_exchange_failed",
                        "details": error_data.get("error_description", str(response.status_code)),
                    }

                token_data = response.json()

        except Exception as e:
            logger.exception("Error during token exchange")
            return {"ok": False, "error": "network_error", "details": str(e)}

        # Store tokens
        expires_in = token_data.get("expires_in", 3600)
        self._tokens = TokenData(
            access_token=token_data.get("access_token", ""),
            refresh_token=token_data.get("refresh_token", ""),
            token_type=token_data.get("token_type", "Bearer"),
            expires_at=time.time() + expires_in,
            scopes=token_data.get("scope", "").split(),
        )

        # Clear auth session
        self._auth_session = None

        # Save tokens to disk
        self._save_tokens()

        return {
            "ok": True,
            "profile": {"email": self._tokens.profile_email},
            "expires_at": self._tokens.expires_at,
        }

    async def refresh_access_token(self) -> bool:
        """Refresh the access token using refresh token.

        Returns:
            True if refresh was successful.
        """
        if not self._tokens or not self._tokens.refresh_token:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    GOOGLE_TOKEN_URL,
                    data={
                        "client_id": self.config.client_id,
                        "client_secret": self.config.client_secret,
                        "refresh_token": self._tokens.refresh_token,
                        "grant_type": "refresh_token",
                    },
                )

                if response.status_code != 200:
                    logger.error("Token refresh failed: %s", response.text)
                    return False

                token_data = response.json()

        except Exception:
            logger.exception("Error during token refresh")
            return False

        # Update tokens
        expires_in = token_data.get("expires_in", 3600)
        self._tokens.access_token = token_data.get("access_token", self._tokens.access_token)
        self._tokens.expires_at = time.time() + expires_in

        # Save updated tokens
        self._save_tokens()

        return True

    async def _ensure_valid_token(self) -> bool:
        """Ensure we have a valid access token, refreshing if needed."""
        if not self._tokens:
            return False

        if self._tokens.is_expired():
            return await self.refresh_access_token()

        return True

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get HTTP client with authentication headers."""
        if not await self._ensure_valid_token():
            raise RuntimeError("No valid authentication")

        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {self._tokens.access_token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        else:
            # Update auth header in case token was refreshed
            self._http_client.headers["Authorization"] = f"Bearer {self._tokens.access_token}"

        return self._http_client

    async def __aenter__(self):
        """Pozwala używać serwisu jako asynchronicznego context managera."""
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Zamyka klienta HTTPX przy wyjściu z context managera."""
        await self.close()

    async def close(self):
        """Zamyka klienta HTTPX, aby uniknąć wycieków zasobów."""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
        else:
            logger.debug("close() wywołane, ale klient HTTPX już zamknięty lub nieutworzony.")
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for HTTP requests."""
        if not self._tokens:
            raise RuntimeError("No valid authentication")
        return {
            "Authorization": f"Bearer {self._tokens.access_token}",
            "Content-Type": "application/json",
        }

    async def list_devices(self, use_cache: bool = True) -> Dict[str, Any]:
        """List devices from Google Home / SDM.

        Args:
            use_cache: If True, return cached devices if available and fresh.

        Returns:
            Dict with devices list or error.
        """
        if self.config.test_mode:
            return self._get_mock_devices()

        if not self.is_authenticated():
            return {"ok": False, "error": "not_authenticated"}

        # Check cache using defined TTL
        if use_cache and self._devices_cache and (time.time() - self._cache_timestamp) < DEVICE_CACHE_TTL_SECONDS:
            return {"ok": True, "devices": self._devices_cache, "from_cache": True}

        try:
            if not await self._ensure_valid_token():
                return {"ok": False, "error": "auth_expired"}

            url = f"{SDM_API_BASE}/enterprises/{self.config.project_id}/devices"

            async with httpx.AsyncClient(headers=self._get_auth_headers(), timeout=30.0) as client:
                response = await client.get(url)

                if response.status_code == 401:
                    # Token might be expired, try refresh
                    if await self.refresh_access_token():
                        async with httpx.AsyncClient(headers=self._get_auth_headers(), timeout=30.0) as retry_client:
                            response = await retry_client.get(url)
                    else:
                        return {"ok": False, "error": "auth_expired"}

                if response.status_code != 200:
                    error_data = response.json() if response.content else {}
                    return {
                        "ok": False,
                        "error": "sdm_error",
                        "status_code": response.status_code,
                        "details": error_data.get("error", {}).get("message", "Unknown error"),
                    }

                data = response.json()
                devices = data.get("devices", [])

            # Transform SDM devices to our format
            transformed = [self._transform_device(d) for d in devices]

            # Update cache
            self._devices_cache = transformed
            self._cache_timestamp = time.time()

            return {"ok": True, "devices": transformed, "from_cache": False}

        except Exception as e:
            logger.exception("Error fetching devices")
            return {"ok": False, "error": "network_error", "details": str(e)}

    async def send_command(self, device_id: str, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send command to a device.

        Args:
            device_id: Full device name/path.
            command: Command name (e.g., 'action.devices.commands.OnOff').
            params: Command parameters.

        Returns:
            Dict with command result.
        """
        if self.config.test_mode:
            return self._mock_command(device_id, command, params)

        if not self.is_authenticated():
            return {"ok": False, "error": "not_authenticated"}

        try:
            client = await self._get_http_client()
            if not await self._ensure_valid_token():
                return {"ok": False, "error": "auth_expired"}

            url = f"{SDM_API_BASE}/{device_id}:executeCommand"

            # Map our command format to SDM format
            sdm_command = self._map_command_to_sdm(command, params)

            response = await client.post(url, json=sdm_command)

            if response.status_code == 401:
                if await self.refresh_access_token():
                    client = await self._get_http_client()
                    response = await client.post(url, json=sdm_command)
                else:
                    return {"ok": False, "error": "auth_expired"}

            if response.status_code != 200:
                error_data = response.json() if response.content else {}
                return {
                    "ok": False,
                    "error": "command_failed",
                    "status_code": response.status_code,
                    "details": error_data.get("error", {}).get("message", "Unknown error"),
                }
            async with httpx.AsyncClient(headers=self._get_auth_headers(), timeout=30.0) as client:
                response = await client.post(url, json=sdm_command)

                if response.status_code == 401:
                    if await self.refresh_access_token():
                        async with httpx.AsyncClient(headers=self._get_auth_headers(), timeout=30.0) as retry_client:
                            response = await retry_client.post(url, json=sdm_command)
                    else:
                        return {"ok": False, "error": "auth_expired"}

                if response.status_code != 200:
                    error_data = response.json() if response.content else {}
                    return {
                        "ok": False,
                        "error": "command_failed",
                        "status_code": response.status_code,
                        "details": error_data.get("error", {}).get("message", "Unknown error"),
                    }

            # Invalidate device cache after command
            self._cache_timestamp = 0.0

            return {"ok": True, "device": device_id, "command": command}

        except Exception as e:
            logger.exception("Error sending command")
            return {"ok": False, "error": "network_error", "details": str(e)}

    def _transform_device(self, sdm_device: Dict[str, Any]) -> Dict[str, Any]:
        """Transform SDM device format to our internal format."""
        name = sdm_device.get("name", "")
        device_type = sdm_device.get("type", "")
        traits = sdm_device.get("traits", {})
        parent_relations = sdm_device.get("parentRelations", [])

        # Extract room name from parent relations
        room = ""
        structure = ""
        for rel in parent_relations:
            display = rel.get("displayName", "")
            parent = rel.get("parent", "")
            if "structures" in parent:
                structure = display
            elif "rooms" in parent:
                room = display

        return {
            "name": name,
            "type": device_type,
            "traits": traits,
            "room": room,
            "structure": structure,
            "custom_name": sdm_device.get("customName", ""),
        }

    def _map_command_to_sdm(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Map our command format to SDM executeCommand format."""
        # SDM uses different command structure
        sdm_command_map = {
            "action.devices.commands.OnOff": ("sdm.devices.commands.OnOff", params),
            "action.devices.commands.BrightnessAbsolute": (
                "sdm.devices.commands.Brightness",
                {"brightness": params.get("brightness", 0) / 100.0},
            ),
            "action.devices.commands.ThermostatTemperatureSetpoint": (
                "sdm.devices.commands.ThermostatTemperatureSetpoint.SetHeat",
                {"heatCelsius": params.get("thermostatTemperatureSetpoint", 20)},
            ),
        }

        sdm_cmd, sdm_params = sdm_command_map.get(command, (command, params))

        return {"command": sdm_cmd, "params": sdm_params}

    def _load_tokens(self) -> None:
        """Load tokens from disk."""
        tokens_path = Path(self.config.tokens_path)
        if tokens_path.exists():
            try:
                with open(tokens_path) as f:
                    data = json.load(f)
                self._tokens = TokenData.from_dict(data)
                logger.info("Loaded Google Home tokens from %s", tokens_path)
            except Exception as e:
                logger.warning("Failed to load tokens: %s", e)

    def _save_tokens(self) -> None:
        """Save tokens to disk."""
        if not self._tokens:
            return

        tokens_path = Path(self.config.tokens_path)
        try:
            tokens_path.parent.mkdir(parents=True, exist_ok=True)
            with open(tokens_path, "w") as f:
                json.dump(self._tokens.to_dict(), f, indent=2)
            logger.info("Saved Google Home tokens to %s", tokens_path)
        except Exception as e:
            logger.warning("Failed to save tokens: %s", e)

    def clear_tokens(self) -> None:
        """Clear stored tokens (logout)."""
        self._tokens = None
        self._devices_cache = []
        self._cache_timestamp = 0.0

        tokens_path = Path(self.config.tokens_path)
        if tokens_path.exists():
            try:
                tokens_path.unlink()
                logger.info("Deleted tokens file: %s", tokens_path)
            except Exception as e:
                logger.warning("Failed to delete tokens: %s", e)

    # Mock methods for test mode
    def _get_mock_devices(self) -> Dict[str, Any]:
        """Return mock devices for test mode."""
        return {
            "ok": True,
            "devices": [
                {
                    "name": "enterprises/test/devices/light-living-room",
                    "type": "sdm.devices.types.LIGHT",
                    "traits": {
                        "sdm.devices.traits.OnOff": {"on": True},
                        "sdm.devices.traits.Brightness": {"brightness": 0.7},
                    },
                    "room": "Living Room",
                    "structure": "Home",
                    "custom_name": "Main Light",
                },
                {
                    "name": "enterprises/test/devices/thermostat-hall",
                    "type": "sdm.devices.types.THERMOSTAT",
                    "traits": {
                        "sdm.devices.traits.Temperature": {"ambientTemperatureCelsius": 21.5},
                        "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                            "heatCelsius": 20.0,
                            "coolCelsius": 24.0,
                        },
                        "sdm.devices.traits.ThermostatMode": {"mode": "HEAT"},
                    },
                    "room": "Hallway",
                    "structure": "Home",
                    "custom_name": "Smart Thermostat",
                },
            ],
            "test_mode": True,
        }

    def _mock_command(self, device_id: str, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle command in test mode."""
        return {
            "ok": True,
            "device": device_id,
            "command": command,
            "test_mode": True,
            "note": "Command simulated in test mode",
        }


# Singleton instance
_google_home_service: Optional[GoogleHomeService] = None


def get_google_home_service() -> GoogleHomeService:
    """Get or create the singleton GoogleHomeService instance."""
    global _google_home_service
    if _google_home_service is None:
        _google_home_service = GoogleHomeService()
    return _google_home_service


def reset_google_home_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _google_home_service
    _google_home_service = None
