"""Tests for Google Home service."""

import pytest
from unittest.mock import patch, AsyncMock

from pc_client.services.google_home import (
    GoogleHomeService,
    get_google_home_service,
    reset_google_home_service,
    _generate_code_verifier,
    _generate_code_challenge,
)


class TestGoogleHomeService:
    """Test GoogleHomeService functionality."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_google_home_service()

    def teardown_method(self):
        """Reset singleton after each test."""
        reset_google_home_service()

    def test_is_configured_returns_false_without_credentials(self):
        """Service should not be configured without OAuth credentials."""
        service = GoogleHomeService()
        assert service.is_configured() is False

    def test_is_configured_returns_true_with_all_credentials(self):
        """Service should be configured when all credentials are provided."""
        service = GoogleHomeService(
            client_id="test-client-id",
            client_secret="test-secret",
            project_id="test-project-id",
        )
        assert service.is_configured() is True

    def test_is_authenticated_in_test_mode(self):
        """Service should report authenticated in test mode."""
        service = GoogleHomeService(test_mode=True)
        assert service.is_authenticated() is True

    def test_is_authenticated_without_tokens(self):
        """Service should not be authenticated without tokens."""
        service = GoogleHomeService()
        assert service.is_authenticated() is False

    def test_get_status_in_test_mode(self):
        """Status should show configured and authenticated in test mode."""
        service = GoogleHomeService(test_mode=True)
        status = service.get_status()

        assert status["configured"] is True
        assert status["authenticated"] is True
        assert status["auth_url_available"] is True
        assert status["profile"]["email"] == "mock@rider.test"
        assert status["error"] is None

    def test_get_status_without_config(self):
        """Status should indicate missing configuration."""
        service = GoogleHomeService()
        status = service.get_status()

        assert status["configured"] is False
        assert status["authenticated"] is False
        assert status["error"] == "auth_env_missing"

    def test_build_auth_url_without_config(self):
        """Building auth URL should fail without config."""
        service = GoogleHomeService()
        result = service.build_auth_url()

        assert result["ok"] is False
        assert result["error"] == "auth_env_missing"

    def test_build_auth_url_with_config(self):
        """Building auth URL should succeed with config."""
        service = GoogleHomeService(
            client_id="test-client-id",
            client_secret="test-secret",
            project_id="test-project-id",
            redirect_uri="http://localhost:8000/api/home/auth/callback",
        )
        result = service.build_auth_url()

        assert result["ok"] is True
        assert "auth_url" in result
        assert "state" in result
        assert "expires_at" in result
        assert "accounts.google.com" in result["auth_url"]
        assert "test-client-id" in result["auth_url"]

    def test_build_auth_url_with_custom_state(self):
        """Building auth URL should use provided state."""
        service = GoogleHomeService(
            client_id="test-client-id",
            client_secret="test-secret",
            project_id="test-project-id",
            redirect_uri="http://localhost:8000/api/home/auth/callback",
        )
        custom_state = "custom-test-state-12345"
        result = service.build_auth_url(state=custom_state)

        assert result["ok"] is True
        assert result["state"] == custom_state
        assert custom_state in result["auth_url"]

    @pytest.mark.asyncio
    async def test_complete_auth_in_test_mode(self):
        """Auth completion should work in test mode."""
        service = GoogleHomeService(test_mode=True)
        result = await service.complete_auth(code="test-code", state="test-state")

        assert result["ok"] is True
        assert "profile" in result

    @pytest.mark.asyncio
    async def test_complete_auth_invalid_state(self):
        """Auth completion should fail with invalid state."""
        service = GoogleHomeService(
            client_id="test-client-id",
            client_secret="test-secret",
            project_id="test-project-id",
        )
        result = await service.complete_auth(code="test-code", state="invalid-state")

        assert result["ok"] is False
        assert result["error"] == "invalid_state"

    @pytest.mark.asyncio
    async def test_list_devices_in_test_mode(self):
        """Listing devices should return mock data in test mode."""
        service = GoogleHomeService(test_mode=True, project_id="test-project")
        result = await service.list_devices()

        assert result["ok"] is True
        assert "devices" in result
        assert len(result["devices"]) > 0
        assert "mock-light-1" in result["devices"][0]["name"]

    @pytest.mark.asyncio
    async def test_list_devices_not_authenticated(self):
        """Listing devices should fail when not authenticated."""
        service = GoogleHomeService(
            client_id="test-client-id",
            client_secret="test-secret",
            project_id="test-project-id",
        )
        result = await service.list_devices()

        assert result["ok"] is False
        assert result["error"] == "not_authenticated"

    @pytest.mark.asyncio
    async def test_send_command_in_test_mode(self):
        """Sending command should work in test mode."""
        service = GoogleHomeService(test_mode=True)
        result = await service.send_command(
            device_id="test-device",
            command="action.devices.commands.OnOff",
            params={"on": True},
        )

        assert result["ok"] is True
        assert result["device"] == "test-device"
        assert result["command"] == "action.devices.commands.OnOff"

    @pytest.mark.asyncio
    async def test_send_command_not_authenticated(self):
        """Sending command should fail when not authenticated."""
        service = GoogleHomeService(
            client_id="test-client-id",
            client_secret="test-secret",
            project_id="test-project-id",
        )
        result = await service.send_command(
            device_id="test-device",
            command="action.devices.commands.OnOff",
            params={"on": True},
        )

        assert result["ok"] is False
        assert result["error"] == "not_authenticated"

    def test_logout(self, tmp_path):
        """Logout should clear tokens."""
        tokens_file = tmp_path / "tokens.json"
        tokens_file.write_text('{"access_token": "test"}')

        service = GoogleHomeService(tokens_path=str(tokens_file))
        service._tokens = {"access_token": "test", "refresh_token": "test"}

        result = service.logout()

        assert result["ok"] is True
        assert service._tokens is None
        assert not tokens_file.exists()


class TestPKCE:
    """Test PKCE functions."""

    def test_code_verifier_length(self):
        """Code verifier should be valid length."""
        verifier = _generate_code_verifier()
        assert len(verifier) >= 43
        assert len(verifier) <= 128

    def test_code_verifier_uniqueness(self):
        """Code verifiers should be unique."""
        verifiers = [_generate_code_verifier() for _ in range(10)]
        assert len(set(verifiers)) == 10

    def test_code_challenge_deterministic(self):
        """Code challenge should be deterministic for same verifier."""
        verifier = "test-verifier-string-12345678901234567890"
        challenge1 = _generate_code_challenge(verifier)
        challenge2 = _generate_code_challenge(verifier)
        assert challenge1 == challenge2

    def test_code_challenge_different_for_different_verifier(self):
        """Code challenge should differ for different verifiers."""
        challenge1 = _generate_code_challenge("verifier-1-test-string-12345")
        challenge2 = _generate_code_challenge("verifier-2-test-string-12345")
        assert challenge1 != challenge2


class TestSingleton:
    """Test singleton behavior."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_google_home_service()

    def teardown_method(self):
        """Reset singleton after each test."""
        reset_google_home_service()

    def test_get_service_creates_singleton(self):
        """get_google_home_service should return same instance."""
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
