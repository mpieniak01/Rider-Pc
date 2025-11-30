"""Google Home / Smart Device Management service for Rider-PC.

This module provides OAuth 2.0 authentication flow and communication
with Google Smart Device Management (SDM) API. It enables Rider-PC to
act as a standalone Google Home controller without proxying through Rider-Pi.
"""

from __future__ import annotations

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

# SDM API endpoints
SDM_API_BASE = "https://smartdevicemanagement.googleapis.com/v1"
GOOGLE_OAUTH_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_OAUTH_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO = "https://www.googleapis.com/oauth2/v3/userinfo"

# OAuth 2.0 scopes for SDM
SDM_SCOPES = [
    "https://www.googleapis.com/auth/sdm.service",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


@dataclass
class AuthSession:
    """Represents an active OAuth authorization session."""

    state: str
    code_verifier: str
    redirect_uri: str
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 600)  # 10 minutes

    def is_expired(self) -> bool:
        """Check if this session has expired."""
        return time.time() > self.expires_at


@dataclass
class TokenData:
    """Represents stored OAuth tokens."""

    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_at: Optional[float] = None
    scopes: List[str] = field(default_factory=list)

    def is_expired(self) -> bool:
        """Check if the access token has expired."""
        if not self.expires_at:
            return False
        return time.time() > self.expires_at - 60  # 60 second buffer

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_at": self.expires_at,
            "scopes": self.scopes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TokenData":
        """Create from dictionary loaded from JSON."""
        return cls(
            access_token=data.get("access_token", ""),
            refresh_token=data.get("refresh_token"),
            token_type=data.get("token_type", "Bearer"),
            expires_at=data.get("expires_at"),
            scopes=data.get("scopes", []),
        )


@dataclass
class UserProfile:
    """Represents the authenticated user's profile."""

    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "email": self.email,
            "name": self.name,
            "picture": self.picture,
            "updated_at": self.updated_at,
        }


class GoogleHomeService:
    """Service for Google Home / SDM integration.

    Handles OAuth 2.0 Authorization Code flow with PKCE,
    token management, and SDM API communication.
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        project_id: Optional[str] = None,
        redirect_uri: str = "http://localhost:8000/api/home/auth/callback",
        tokens_path: str = "config/local/google_tokens_pc.json",
        test_mode: bool = False,
    ):
        """Initialize the Google Home service.

        Args:
            client_id: Google OAuth Client ID
            client_secret: Google OAuth Client Secret
            project_id: Google Device Access Project ID
            redirect_uri: OAuth callback URI
            tokens_path: Path to store OAuth tokens
            test_mode: If True, use mock responses
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.project_id = project_id
        self.redirect_uri = redirect_uri
        self.tokens_path = Path(tokens_path)
        self.test_mode = test_mode

        self._auth_sessions: Dict[str, AuthSession] = {}
        self._tokens: Optional[TokenData] = None
        self._profile: Optional[UserProfile] = None
        self._devices_cache: List[Dict[str, Any]] = []
        self._devices_cache_time: float = 0
        self._http_client: Optional[httpx.AsyncClient] = None

        # Load stored tokens if available
        self._load_tokens()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    def is_configured(self) -> bool:
        """Check if the service is properly configured."""
        return bool(self.client_id and self.client_secret and self.project_id)

    def is_authenticated(self) -> bool:
        """Check if we have valid authentication tokens."""
        if self.test_mode:
            return True
        if not self._tokens:
            return False
        if not self._tokens.refresh_token:
            return False
        return True

    def get_status(self) -> Dict[str, Any]:
        """Get the current authentication status.

        Returns:
            Dictionary with configuration and auth status
        """
        configured = self.is_configured()
        authenticated = self.is_authenticated()

        status: Dict[str, Any] = {
            "configured": configured,
            "authenticated": authenticated,
            "auth_url_available": configured and not authenticated,
            "profile": self._profile.to_dict() if self._profile else None,
            "scopes": self._tokens.scopes if self._tokens else [],
            "test_mode": self.test_mode,
        }

        if not configured:
            status["configuration_missing"] = []
            if not self.client_id:
                status["configuration_missing"].append("GOOGLE_CLIENT_ID")
            if not self.client_secret:
                status["configuration_missing"].append("GOOGLE_CLIENT_SECRET")
            if not self.project_id:
                status["configuration_missing"].append("GOOGLE_DEVICE_ACCESS_PROJECT_ID")

        return status

    def _generate_code_verifier(self) -> str:
        """Generate a code verifier for PKCE."""
        return secrets.token_urlsafe(64)[:128]

    def _generate_code_challenge(self, verifier: str) -> str:
        """Generate a code challenge from verifier using S256."""
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        # Base64url encoding
        import base64

        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    def start_auth_session(self, redirect_uri: Optional[str] = None) -> Dict[str, Any]:
        """Start a new OAuth authorization session.

        Args:
            redirect_uri: Optional override for redirect URI

        Returns:
            Dictionary with auth_url and session info
        """
        if not self.is_configured():
            return {
                "ok": False,
                "error": "auth_env_missing",
                "message": "Google Home not configured. Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_DEVICE_ACCESS_PROJECT_ID.",
            }

        # Generate PKCE parameters
        state = secrets.token_urlsafe(32)
        code_verifier = self._generate_code_verifier()
        code_challenge = self._generate_code_challenge(code_verifier)
        actual_redirect = redirect_uri or self.redirect_uri

        # Store session
        session = AuthSession(
            state=state,
            code_verifier=code_verifier,
            redirect_uri=actual_redirect,
        )
        self._auth_sessions[state] = session

        # Clean up expired sessions
        self._cleanup_expired_sessions()

        # Build authorization URL
        params = {
            "client_id": self.client_id,
            "redirect_uri": actual_redirect,
            "response_type": "code",
            "scope": " ".join(SDM_SCOPES),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "access_type": "offline",
            "prompt": "consent",
        }

        auth_url = f"{GOOGLE_OAUTH_AUTH}?{urlencode(params)}"

        return {
            "ok": True,
            "auth_url": auth_url,
            "state": state,
            "expires_at": session.expires_at,
        }

    def _cleanup_expired_sessions(self) -> None:
        """Remove expired auth sessions."""
        expired = [state for state, session in self._auth_sessions.items() if session.is_expired()]
        for state in expired:
            del self._auth_sessions[state]

    async def complete_auth(self, code: str, state: str) -> Dict[str, Any]:
        """Complete the OAuth flow by exchanging code for tokens.

        Args:
            code: Authorization code from Google
            state: State parameter for verification

        Returns:
            Dictionary with result or error
        """
        # Verify state and get session
        session = self._auth_sessions.get(state)
        if not session:
            return {"ok": False, "error": "invalid_state", "message": "Invalid or expired state parameter"}

        if session.is_expired():
            del self._auth_sessions[state]
            return {"ok": False, "error": "session_expired", "message": "Auth session has expired"}

        # Exchange code for tokens
        client = await self._get_client()
        try:
            response = await client.post(
                GOOGLE_OAUTH_TOKEN,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "code_verifier": session.code_verifier,
                    "grant_type": "authorization_code",
                    "redirect_uri": session.redirect_uri,
                },
            )

            if response.status_code != 200:
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                return {
                    "ok": False,
                    "error": "token_exchange_failed",
                    "message": error_data.get("error_description", f"HTTP {response.status_code}"),
                }

            token_data = response.json()

            # Calculate expiration time
            expires_in = token_data.get("expires_in", 3600)
            expires_at = time.time() + expires_in

            self._tokens = TokenData(
                access_token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token"),
                token_type=token_data.get("token_type", "Bearer"),
                expires_at=expires_at,
                scopes=token_data.get("scope", "").split(),
            )

            # Save tokens
            self._save_tokens()

            # Fetch user profile
            await self._fetch_profile()

            # Clean up session
            del self._auth_sessions[state]

            return {
                "ok": True,
                "profile": self._profile.to_dict() if self._profile else None,
                "authenticated": True,
            }

        except Exception as exc:
            logger.exception("Error completing OAuth flow")
            return {"ok": False, "error": "auth_error", "message": str(exc)}

    async def _fetch_profile(self) -> None:
        """Fetch the user's profile from Google."""
        if not self._tokens:
            return

        client = await self._get_client()
        try:
            response = await client.get(
                GOOGLE_USERINFO,
                headers={"Authorization": f"Bearer {self._tokens.access_token}"},
            )
            if response.status_code == 200:
                data = response.json()
                self._profile = UserProfile(
                    email=data.get("email", "unknown"),
                    name=data.get("name"),
                    picture=data.get("picture"),
                )
        except Exception as exc:
            logger.warning("Failed to fetch user profile: %s", exc)

    async def _ensure_valid_token(self) -> bool:
        """Ensure we have a valid access token, refreshing if needed.

        Returns:
            True if we have a valid token, False otherwise
        """
        if not self._tokens:
            return False

        if not self._tokens.is_expired():
            return True

        # Try to refresh
        if not self._tokens.refresh_token:
            return False

        client = await self._get_client()
        try:
            response = await client.post(
                GOOGLE_OAUTH_TOKEN,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self._tokens.refresh_token,
                    "grant_type": "refresh_token",
                },
            )

            if response.status_code != 200:
                logger.error("Token refresh failed: %s", response.text)
                return False

            token_data = response.json()
            expires_in = token_data.get("expires_in", 3600)

            self._tokens.access_token = token_data["access_token"]
            self._tokens.expires_at = time.time() + expires_in
            if "scope" in token_data:
                self._tokens.scopes = token_data["scope"].split()

            self._save_tokens()
            return True

        except Exception as exc:
            logger.exception("Error refreshing token: %s", exc)
            return False

    def _load_tokens(self) -> None:
        """Load tokens from storage."""
        if not self.tokens_path.exists():
            return

        try:
            with open(self.tokens_path, "r") as f:
                data = json.load(f)
                self._tokens = TokenData.from_dict(data.get("tokens", {}))
                if "profile" in data:
                    self._profile = UserProfile(
                        email=data["profile"].get("email", "unknown"),
                        name=data["profile"].get("name"),
                        picture=data["profile"].get("picture"),
                        updated_at=data["profile"].get("updated_at", time.time()),
                    )
                logger.info("Loaded Google Home tokens from %s", self.tokens_path)
        except Exception as exc:
            logger.warning("Failed to load tokens from %s: %s", self.tokens_path, exc)

    def _save_tokens(self) -> None:
        """Save tokens to storage."""
        if not self._tokens:
            return

        try:
            self.tokens_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "tokens": self._tokens.to_dict(),
                "saved_at": time.time(),
            }
            if self._profile:
                data["profile"] = self._profile.to_dict()

            with open(self.tokens_path, "w") as f:
                json.dump(data, f, indent=2)
            logger.info("Saved Google Home tokens to %s", self.tokens_path)
        except Exception as exc:
            logger.error("Failed to save tokens to %s: %s", self.tokens_path, exc)

    async def list_devices(self, use_cache: bool = True) -> Dict[str, Any]:
        """List devices from Google SDM.

        Args:
            use_cache: If True, return cached devices if available

        Returns:
            Dictionary with devices list or error
        """
        if self.test_mode:
            return self._get_mock_devices()

        if not self.is_authenticated():
            return {"ok": False, "error": "not_authenticated", "devices": []}

        # Return cached devices if fresh (< 30 seconds)
        if use_cache and self._devices_cache and (time.time() - self._devices_cache_time) < 30:
            return {"ok": True, "devices": self._devices_cache, "cached": True}

        if not await self._ensure_valid_token():
            return {"ok": False, "error": "token_refresh_failed", "devices": []}

        client = await self._get_client()
        try:
            url = f"{SDM_API_BASE}/enterprises/{self.project_id}/devices"
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {self._tokens.access_token}"},
            )

            if response.status_code == 401:
                # Token might be invalid, try refresh once
                if await self._ensure_valid_token():
                    response = await client.get(
                        url,
                        headers={"Authorization": f"Bearer {self._tokens.access_token}"},
                    )

            if response.status_code != 200:
                error_msg = response.text[:200]
                logger.error("SDM devices request failed: %s - %s", response.status_code, error_msg)
                return {
                    "ok": False,
                    "error": f"sdm_error_{response.status_code}",
                    "message": error_msg,
                    "devices": [],
                }

            data = response.json()
            devices = data.get("devices", [])

            # Transform to expected format
            formatted_devices = []
            for device in devices:
                formatted_device = {
                    "name": device.get("name", ""),
                    "type": device.get("type", "UNKNOWN"),
                    "traits": device.get("traits", {}),
                    "parentRelations": device.get("parentRelations", []),
                }
                formatted_devices.append(formatted_device)

            self._devices_cache = formatted_devices
            self._devices_cache_time = time.time()

            return {"ok": True, "devices": formatted_devices}

        except Exception as exc:
            logger.exception("Error fetching SDM devices")
            return {"ok": False, "error": "sdm_request_failed", "message": str(exc), "devices": []}

    async def send_command(self, device_id: str, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a command to a device.

        Args:
            device_id: Full device resource name
            command: Command name (e.g., action.devices.commands.OnOff)
            params: Command parameters

        Returns:
            Dictionary with result or error
        """
        if self.test_mode:
            return self._apply_mock_command(device_id, command, params)

        if not self.is_authenticated():
            return {"ok": False, "error": "not_authenticated"}

        if not await self._ensure_valid_token():
            return {"ok": False, "error": "token_refresh_failed"}

        client = await self._get_client()
        try:
            # Extract command name for SDM API
            sdm_command = command.replace("action.devices.commands.", "sdm.devices.commands.")

            url = f"{SDM_API_BASE}/{device_id}:executeCommand"
            payload = {
                "command": sdm_command,
                "params": params,
            }

            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {self._tokens.access_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

            if response.status_code == 401:
                if await self._ensure_valid_token():
                    response = await client.post(
                        url,
                        headers={
                            "Authorization": f"Bearer {self._tokens.access_token}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )

            if response.status_code not in (200, 204):
                error_msg = response.text[:200]
                logger.error("SDM command failed: %s - %s", response.status_code, error_msg)
                return {
                    "ok": False,
                    "error": f"sdm_error_{response.status_code}",
                    "message": error_msg,
                }

            # Invalidate device cache after command
            self._devices_cache_time = 0

            return {"ok": True, "device": device_id, "command": command}

        except Exception as exc:
            logger.exception("Error sending SDM command")
            return {"ok": False, "error": "sdm_request_failed", "message": str(exc)}

    def get_profile(self) -> Optional[Dict[str, Any]]:
        """Get the current user profile."""
        if self._profile:
            return self._profile.to_dict()
        return None

    def clear_auth(self) -> Dict[str, Any]:
        """Clear stored authentication and tokens."""
        self._tokens = None
        self._profile = None
        self._devices_cache = []
        self._devices_cache_time = 0

        if self.tokens_path.exists():
            try:
                os.remove(self.tokens_path)
            except Exception as exc:
                logger.warning("Failed to remove tokens file: %s", exc)

        return {"ok": True, "message": "Authentication cleared"}

    # Mock methods for test mode
    def _get_mock_devices(self) -> Dict[str, Any]:
        """Return mock devices for test mode."""
        return {
            "ok": True,
            "devices": [
                {
                    "name": "enterprises/test-project/devices/light-living-room",
                    "type": "sdm.devices.types.LIGHT",
                    "traits": {
                        "sdm.devices.traits.OnOff": {"on": True},
                        "sdm.devices.traits.Brightness": {"brightness": 70},
                        "sdm.devices.traits.ColorSetting": {"color": {"temperatureK": 3200}},
                    },
                },
                {
                    "name": "enterprises/test-project/devices/thermostat-hall",
                    "type": "sdm.devices.types.THERMOSTAT",
                    "traits": {
                        "sdm.devices.traits.ThermostatMode": {
                            "mode": "HEATCOOL",
                            "availableModes": ["OFF", "HEAT", "COOL", "HEATCOOL"],
                        },
                        "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                            "heatCelsius": 20.0,
                            "coolCelsius": 24.0,
                        },
                        "sdm.devices.traits.Temperature": {
                            "ambientTemperatureCelsius": 21.5,
                        },
                    },
                },
                {
                    "name": "enterprises/test-project/devices/vacuum-dusty",
                    "type": "sdm.devices.types.VACUUM",
                    "traits": {
                        "sdm.devices.traits.StartStop": {"isRunning": False, "isPaused": False},
                        "sdm.devices.traits.Dock": {"available": True},
                    },
                },
            ],
            "test_mode": True,
        }

    def _apply_mock_command(
        self, device_id: str, command: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply command in mock mode (update local cache)."""
        return {
            "ok": True,
            "device": device_id,
            "command": command,
            "test_mode": True,
            "note": "Command simulated in test mode",
        }


# Singleton instance for the service
_google_home_service: Optional[GoogleHomeService] = None


def get_google_home_service(
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    project_id: Optional[str] = None,
    redirect_uri: str = "http://localhost:8000/api/home/auth/callback",
    tokens_path: str = "config/local/google_tokens_pc.json",
    test_mode: bool = False,
    reset: bool = False,
) -> GoogleHomeService:
    """Get or create the Google Home service singleton.

    Args:
        client_id: Google OAuth Client ID
        client_secret: Google OAuth Client Secret
        project_id: Google Device Access Project ID
        redirect_uri: OAuth callback URI
        tokens_path: Path to store OAuth tokens
        test_mode: If True, use mock responses
        reset: If True, create a new instance

    Returns:
        GoogleHomeService instance
    """
    global _google_home_service

    if reset or _google_home_service is None:
        _google_home_service = GoogleHomeService(
            client_id=client_id,
            client_secret=client_secret,
            project_id=project_id,
            redirect_uri=redirect_uri,
            tokens_path=tokens_path,
            test_mode=test_mode,
        )

    return _google_home_service


def reset_google_home_service() -> None:
    """Reset the Google Home service singleton (useful for testing)."""
    global _google_home_service
    _google_home_service = None
