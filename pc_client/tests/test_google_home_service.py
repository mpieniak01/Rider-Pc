"""Unit tests for GoogleHomeService."""

import time

import pytest

from pc_client.services.google_home import (
    AuthSession,
    GoogleHomeConfig,
    GoogleHomeService,
    TokenData,
    reset_google_home_service,
)

# Test configuration constants
TEST_CLIENT_ID = "test-client-id"
TEST_CLIENT_SECRET = "test-client-secret"
TEST_PROJECT_ID = "test-project-id"
TEST_REDIRECT_URI = "http://localhost:8000/api/home/auth/callback"
TEST_TOKENS_PATH = "/tmp/test_tokens.json"


@pytest.fixture
def config():
    """Create test configuration."""
    return GoogleHomeConfig(
        client_id=TEST_CLIENT_ID,
        client_secret=TEST_CLIENT_SECRET,
        project_id=TEST_PROJECT_ID,
        redirect_uri=TEST_REDIRECT_URI,
        tokens_path=TEST_TOKENS_PATH,
        test_mode=False,
    )


@pytest.fixture
def test_mode_config():
    """Create test mode configuration."""
    return GoogleHomeConfig(
        client_id=TEST_CLIENT_ID,
        client_secret=TEST_CLIENT_SECRET,
        project_id=TEST_PROJECT_ID,
        redirect_uri=TEST_REDIRECT_URI,
        tokens_path=TEST_TOKENS_PATH,
        test_mode=True,
    )


@pytest.fixture
def unconfigured_config():
    """Create unconfigured configuration."""
    return GoogleHomeConfig()


@pytest.fixture(autouse=True)
def cleanup():
    """Reset singleton after each test."""
    yield
    reset_google_home_service()


class TestGoogleHomeConfig:
    """Tests for GoogleHomeConfig."""

    def test_is_configured_true(self, config):
        """Test is_configured returns True when all fields set."""
        assert config.is_configured() is True

    def test_is_configured_false(self, unconfigured_config):
        """Test is_configured returns False when fields missing."""
        assert unconfigured_config.is_configured() is False

    def test_from_env(self, monkeypatch):
        """Test configuration from environment variables."""
        monkeypatch.setenv("GOOGLE_HOME_CLIENT_ID", "env-client-id")
        monkeypatch.setenv("GOOGLE_HOME_CLIENT_SECRET", "env-secret")
        monkeypatch.setenv("GOOGLE_HOME_PROJECT_ID", "env-project")
        monkeypatch.setenv("GOOGLE_HOME_REDIRECT_URI", "http://test/callback")
        monkeypatch.setenv("GOOGLE_HOME_TEST_MODE", "true")

        config = GoogleHomeConfig.from_env()

        assert config.client_id == "env-client-id"
        assert config.client_secret == "env-secret"
        assert config.project_id == "env-project"
        assert config.redirect_uri == "http://test/callback"
        assert config.test_mode is True


class TestAuthSession:
    """Tests for AuthSession."""

    def test_create_session(self):
        """Test creating new auth session."""
        session = AuthSession.create(ttl_seconds=300)

        assert session.state
        assert len(session.state) > 20
        assert session.code_verifier
        assert session.code_challenge
        assert session.expires_at > time.time()

    def test_session_validity(self):
        """Test session validity check."""
        session = AuthSession.create(ttl_seconds=300)
        assert session.is_valid() is True

        # Expired session
        expired = AuthSession(
            state="test",
            code_verifier="test",
            code_challenge="test",
            expires_at=time.time() - 100,
        )
        assert expired.is_valid() is False


class TestTokenData:
    """Tests for TokenData."""

    def test_is_expired(self):
        """Test token expiration check."""
        # Not expired
        token = TokenData(
            access_token="test",
            refresh_token="refresh",
            expires_at=time.time() + 3600,
        )
        assert token.is_expired() is False

        # Expired
        expired = TokenData(
            access_token="test",
            refresh_token="refresh",
            expires_at=time.time() - 100,
        )
        assert expired.is_expired() is True

    def test_to_dict_from_dict(self):
        """Test serialization and deserialization."""
        token = TokenData(
            access_token="access",
            refresh_token="refresh",
            token_type="Bearer",
            expires_at=1234567890.0,
            scopes=["scope1", "scope2"],
            profile_email="test@example.com",
        )

        data = token.to_dict()
        restored = TokenData.from_dict(data)

        assert restored.access_token == token.access_token
        assert restored.refresh_token == token.refresh_token
        assert restored.expires_at == token.expires_at
        assert restored.scopes == token.scopes
        assert restored.profile_email == token.profile_email


class TestGoogleHomeService:
    """Tests for GoogleHomeService."""

    def test_is_configured(self, config, unconfigured_config):
        """Test is_configured method."""
        service = GoogleHomeService(config)
        assert service.is_configured() is True

        service2 = GoogleHomeService(unconfigured_config)
        assert service2.is_configured() is False

    def test_is_authenticated_no_tokens(self, config):
        """Test is_authenticated when no tokens."""
        service = GoogleHomeService(config)
        assert service.is_authenticated() is False

    def test_is_authenticated_with_tokens(self, config):
        """Test is_authenticated with valid tokens."""
        service = GoogleHomeService(config)
        service._tokens = TokenData(
            access_token="test",
            refresh_token="refresh",
            expires_at=time.time() + 3600,
        )
        assert service.is_authenticated() is True

    def test_get_status_not_configured(self, unconfigured_config):
        """Test get_status when not configured."""
        service = GoogleHomeService(unconfigured_config)
        status = service.get_status()

        assert status["configured"] is False
        assert status["authenticated"] is False
        assert "config_missing" in status

    def test_get_status_configured_not_authenticated(self, config):
        """Test get_status when configured but not authenticated."""
        service = GoogleHomeService(config)
        status = service.get_status()

        assert status["configured"] is True
        assert status["authenticated"] is False
        assert status["auth_url_available"] is True

    def test_get_status_test_mode(self, test_mode_config):
        """Test get_status in test mode."""
        service = GoogleHomeService(test_mode_config)
        status = service.get_status()

        assert status["configured"] is True
        assert status["authenticated"] is True
        assert status["test_mode"] is True

    def test_start_auth_session(self, config):
        """Test starting OAuth session."""
        service = GoogleHomeService(config)
        result = service.start_auth_session()

        assert result["ok"] is True
        assert "auth_url" in result
        # Verify the auth URL starts with Google's OAuth endpoint
        assert result["auth_url"].startswith("https://accounts.google.com/o/oauth2/")
        assert "state" in result
        assert "expires_at" in result

    def test_start_auth_session_not_configured(self, unconfigured_config):
        """Test starting OAuth session when not configured."""
        service = GoogleHomeService(unconfigured_config)
        result = service.start_auth_session()

        assert result["ok"] is False
        assert result["error"] == "not_configured"

    @pytest.mark.asyncio
    async def test_complete_auth_invalid_state(self, config):
        """Test complete_auth with invalid state."""
        service = GoogleHomeService(config)
        service.start_auth_session()  # Start session

        result = await service.complete_auth("code", "wrong-state")

        assert result["ok"] is False
        assert result["error"] == "invalid_state"

    @pytest.mark.asyncio
    async def test_list_devices_test_mode(self, test_mode_config):
        """Test list_devices in test mode."""
        service = GoogleHomeService(test_mode_config)
        result = await service.list_devices()

        assert result["ok"] is True
        assert "devices" in result
        assert result["test_mode"] is True
        assert len(result["devices"]) > 0

    @pytest.mark.asyncio
    async def test_list_devices_not_authenticated(self, config):
        """Test list_devices when not authenticated."""
        service = GoogleHomeService(config)
        result = await service.list_devices()

        assert result["ok"] is False
        assert result["error"] == "not_authenticated"

    @pytest.mark.asyncio
    async def test_send_command_test_mode(self, test_mode_config):
        """Test send_command in test mode."""
        service = GoogleHomeService(test_mode_config)
        result = await service.send_command(
            device_id="test-device",
            command="action.devices.commands.OnOff",
            params={"on": True},
        )

        assert result["ok"] is True
        assert result["test_mode"] is True

    @pytest.mark.asyncio
    async def test_send_command_not_authenticated(self, config):
        """Test send_command when not authenticated."""
        service = GoogleHomeService(config)
        result = await service.send_command(
            device_id="test-device",
            command="action.devices.commands.OnOff",
            params={"on": True},
        )

        assert result["ok"] is False
        assert result["error"] == "not_authenticated"

    def test_clear_auth(self, config, tmp_path):
        """Test clearing authentication and tokens."""
        config.tokens_path = str(tmp_path / "tokens.json")
        service = GoogleHomeService(config)
        service._tokens = TokenData(
            access_token="test",
            refresh_token="refresh",
            expires_at=time.time() + 3600,
        )

        service.clear_auth()

        assert service._tokens is None
        assert service.is_authenticated() is False
