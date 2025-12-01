"""Tests for Google Home service and OAuth flow."""

import pytest
import time

from pc_client.services.google_home import (
    GoogleHomeService,
    AuthSession,
    TokenData,
    UserProfile,
    get_google_home_service,
    reset_google_home_service,
)


@pytest.fixture(autouse=True)
def reset_service():
    """Reset the service singleton before each test."""
    reset_google_home_service()
    yield
    reset_google_home_service()


class TestGoogleHomeService:
    """Test GoogleHomeService class."""

    def test_is_configured_without_credentials(self):
        """Service is not configured without credentials."""
        service = GoogleHomeService()
        assert service.is_configured() is False

    def test_is_configured_with_credentials(self):
        """Service is configured with all credentials."""
        service = GoogleHomeService(
            client_id="test-client-id",
            client_secret="test-client-secret",
            project_id="test-project-id",
        )
        assert service.is_configured() is True

    def test_is_configured_missing_client_secret(self):
        """Service is not configured with missing client_secret."""
        service = GoogleHomeService(
            client_id="test-client-id",
            project_id="test-project-id",
        )
        assert service.is_configured() is False

    def test_is_authenticated_test_mode(self):
        """In test mode, service is always authenticated."""
        service = GoogleHomeService(test_mode=True)
        assert service.is_authenticated() is True

    def test_is_authenticated_no_tokens(self):
        """Without tokens, service is not authenticated."""
        service = GoogleHomeService(
            client_id="test-client-id",
            client_secret="test-client-secret",
            project_id="test-project-id",
        )
        assert service.is_authenticated() is False

    def test_get_status_not_configured(self):
        """Status shows configuration missing when not configured."""
        service = GoogleHomeService()
        status = service.get_status()
        assert status["configured"] is False
        assert status["authenticated"] is False
        assert "GOOGLE_CLIENT_ID" in status["configuration_missing"]
        assert "GOOGLE_CLIENT_SECRET" in status["configuration_missing"]
        assert "GOOGLE_DEVICE_ACCESS_PROJECT_ID" in status["configuration_missing"]

    def test_get_status_configured(self):
        """Status shows configured when credentials are set."""
        service = GoogleHomeService(
            client_id="test-client-id",
            client_secret="test-client-secret",
            project_id="test-project-id",
        )
        status = service.get_status()
        assert status["configured"] is True
        assert status["auth_url_available"] is True

    def test_get_status_test_mode(self):
        """Status shows test mode when enabled."""
        service = GoogleHomeService(test_mode=True)
        status = service.get_status()
        assert status["test_mode"] is True
        assert status["authenticated"] is True

    def test_start_auth_session_not_configured(self):
        """Auth session fails when not configured."""
        service = GoogleHomeService()
        result = service.start_auth_session()
        assert result["ok"] is False
        assert result["error"] == "auth_env_missing"

    def test_start_auth_session_success(self):
        """Auth session starts successfully with configuration."""
        service = GoogleHomeService(
            client_id="test-client-id",
            client_secret="test-client-secret",
            project_id="test-project-id",
        )
        result = service.start_auth_session()
        assert result["ok"] is True
        assert "auth_url" in result
        assert "state" in result
        assert result["auth_url"].startswith("https://accounts.google.com/")
        assert "code_challenge" in result["auth_url"]

    def test_start_auth_session_pkce_params(self):
        """Auth URL contains PKCE parameters."""
        service = GoogleHomeService(
            client_id="test-client-id",
            client_secret="test-client-secret",
            project_id="test-project-id",
            redirect_uri="http://localhost:8000/api/home/auth/callback",
        )
        result = service.start_auth_session()
        auth_url = result["auth_url"]
        assert "code_challenge=" in auth_url
        assert "code_challenge_method=S256" in auth_url
        assert "state=" in auth_url
        assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fhome%2Fauth%2Fcallback" in auth_url

    def test_cleanup_expired_sessions(self):
        """Expired sessions are cleaned up."""
        service = GoogleHomeService(
            client_id="test-client-id",
            client_secret="test-client-secret",
            project_id="test-project-id",
        )
        # Create a session
        result = service.start_auth_session()
        state = result["state"]
        assert state in service._auth_sessions

        # Manually expire the session
        service._auth_sessions[state].expires_at = time.time() - 100

        # Trigger cleanup by starting new session
        service.start_auth_session()

        # Old session should be gone
        assert state not in service._auth_sessions

    def test_code_verifier_generation(self):
        """Code verifier is generated with correct length."""
        service = GoogleHomeService()
        verifier = service._generate_code_verifier()
        assert len(verifier) <= 128
        assert len(verifier) >= 43  # Minimum per RFC 7636

    def test_code_challenge_generation(self):
        """Code challenge is generated correctly."""
        service = GoogleHomeService()
        verifier = "test_verifier_string_for_pkce_testing"
        challenge = service._generate_code_challenge(verifier)
        # Challenge should be base64url encoded
        assert "=" not in challenge  # No padding
        assert "+" not in challenge  # URL safe
        assert "/" not in challenge  # URL safe


class TestGoogleHomeServiceAsync:
    """Async tests for GoogleHomeService."""

    @pytest.mark.asyncio
    async def test_list_devices_test_mode(self):
        """List devices returns mock devices in test mode."""
        service = GoogleHomeService(test_mode=True)
        result = await service.list_devices()
        assert result["ok"] is True
        assert len(result["devices"]) == 3
        assert result.get("test_mode") is True

    @pytest.mark.asyncio
    async def test_list_devices_not_authenticated(self):
        """List devices fails when not authenticated."""
        service = GoogleHomeService(
            client_id="test-client-id",
            client_secret="test-client-secret",
            project_id="test-project-id",
        )
        result = await service.list_devices()
        assert result["ok"] is False
        assert result["error"] == "not_authenticated"

    @pytest.mark.asyncio
    async def test_send_command_test_mode(self):
        """Send command returns success in test mode."""
        service = GoogleHomeService(test_mode=True)
        result = await service.send_command(
            "devices/light/living-room",
            "action.devices.commands.OnOff",
            {"on": True},
        )
        assert result["ok"] is True
        assert result.get("test_mode") is True

    @pytest.mark.asyncio
    async def test_send_command_not_authenticated(self):
        """Send command fails when not authenticated."""
        service = GoogleHomeService(
            client_id="test-client-id",
            client_secret="test-client-secret",
            project_id="test-project-id",
        )
        result = await service.send_command(
            "devices/light/living-room",
            "action.devices.commands.OnOff",
            {"on": True},
        )
        assert result["ok"] is False
        assert result["error"] == "not_authenticated"

    @pytest.mark.asyncio
    async def test_complete_auth_invalid_state(self):
        """Complete auth fails with invalid state."""
        service = GoogleHomeService(
            client_id="test-client-id",
            client_secret="test-client-secret",
            project_id="test-project-id",
        )
        result = await service.complete_auth("test-code", "invalid-state")
        assert result["ok"] is False
        assert result["error"] == "invalid_state"

    @pytest.mark.asyncio
    async def test_complete_auth_expired_session(self):
        """Complete auth fails with expired session."""
        service = GoogleHomeService(
            client_id="test-client-id",
            client_secret="test-client-secret",
            project_id="test-project-id",
        )
        # Start a session
        start_result = service.start_auth_session()
        state = start_result["state"]

        # Manually expire the session
        service._auth_sessions[state].expires_at = time.time() - 100

        result = await service.complete_auth("test-code", state)
        assert result["ok"] is False
        assert result["error"] == "session_expired"

    @pytest.mark.asyncio
    async def test_close_client(self):
        """HTTP client can be closed."""
        service = GoogleHomeService(test_mode=True)
        # Create client
        await service._get_client()
        assert service._http_client is not None

        # Close client
        await service.close()
        assert service._http_client is None


class TestAuthSession:
    """Tests for AuthSession dataclass."""

    def test_is_expired_false(self):
        """Session is not expired when created."""
        session = AuthSession(
            state="test-state",
            code_verifier="test-verifier",
            redirect_uri="http://localhost/callback",
        )
        assert session.is_expired() is False

    def test_is_expired_true(self):
        """Session is expired after expiration time."""
        session = AuthSession(
            state="test-state",
            code_verifier="test-verifier",
            redirect_uri="http://localhost/callback",
            expires_at=time.time() - 100,
        )
        assert session.is_expired() is True


class TestTokenData:
    """Tests for TokenData dataclass."""

    def test_is_expired_no_expiry(self):
        """Token without expiry is not considered expired."""
        token = TokenData(access_token="test-token")
        assert token.is_expired() is False

    def test_is_expired_future(self):
        """Token with future expiry is not expired."""
        token = TokenData(
            access_token="test-token",
            expires_at=time.time() + 3600,
        )
        assert token.is_expired() is False

    def test_is_expired_past(self):
        """Token with past expiry is expired."""
        token = TokenData(
            access_token="test-token",
            expires_at=time.time() - 100,
        )
        assert token.is_expired() is True

    def test_to_dict(self):
        """Token can be converted to dictionary."""
        token = TokenData(
            access_token="test-token",
            refresh_token="refresh-token",
            expires_at=1234567890,
            scopes=["scope1", "scope2"],
        )
        data = token.to_dict()
        assert data["access_token"] == "test-token"
        assert data["refresh_token"] == "refresh-token"
        assert data["expires_at"] == 1234567890
        assert data["scopes"] == ["scope1", "scope2"]

    def test_from_dict(self):
        """Token can be created from dictionary."""
        data = {
            "access_token": "test-token",
            "refresh_token": "refresh-token",
            "expires_at": 1234567890,
            "scopes": ["scope1", "scope2"],
        }
        token = TokenData.from_dict(data)
        assert token.access_token == "test-token"
        assert token.refresh_token == "refresh-token"
        assert token.expires_at == 1234567890
        assert token.scopes == ["scope1", "scope2"]


class TestUserProfile:
    """Tests for UserProfile dataclass."""

    def test_to_dict(self):
        """Profile can be converted to dictionary."""
        profile = UserProfile(
            email="test@example.com",
            name="Test User",
            picture="https://example.com/avatar.jpg",
        )
        data = profile.to_dict()
        assert data["email"] == "test@example.com"
        assert data["name"] == "Test User"
        assert data["picture"] == "https://example.com/avatar.jpg"
        assert "updated_at" in data


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_service_singleton(self):
        """Singleton returns same instance."""
        service1 = get_google_home_service(test_mode=True)
        service2 = get_google_home_service(test_mode=True)
        assert service1 is service2

    def test_reset_clears_singleton(self):
        """reset_google_home_service should clear the singleton."""
        service1 = get_google_home_service(test_mode=True)
        reset_google_home_service()
        service2 = get_google_home_service(test_mode=True)
        assert service1 is not service2

    def test_get_service_with_reset(self):
        """get_google_home_service with reset should create new instance."""
        service1 = get_google_home_service(test_mode=True)
        service2 = get_google_home_service(test_mode=True, reset=True)
        assert service1 is not service2
