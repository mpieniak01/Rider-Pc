"""Tests for GitHub settings configuration in Settings class."""

from pc_client.config.settings import Settings


class TestGitHubSettings:
    """Tests for GitHub-related settings fields."""

    def test_github_token_from_env(self, monkeypatch):
        """Test github_token reads from GITHUB_TOKEN environment variable."""
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123token")
        settings = Settings()
        assert settings.github_token == "ghp_test123token"

    def test_github_token_default_none(self, monkeypatch):
        """Test github_token defaults to None when not set."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        settings = Settings()
        assert settings.github_token is None

    def test_github_repo_owner_from_env(self, monkeypatch):
        """Test github_repo_owner reads from GITHUB_REPO_OWNER environment variable."""
        monkeypatch.setenv("GITHUB_REPO_OWNER", "test-owner")
        settings = Settings()
        assert settings.github_repo_owner == "test-owner"

    def test_github_repo_owner_default_empty(self, monkeypatch):
        """Test github_repo_owner defaults to empty string when not set."""
        monkeypatch.delenv("GITHUB_REPO_OWNER", raising=False)
        settings = Settings()
        assert settings.github_repo_owner == ""

    def test_github_repo_name_from_env(self, monkeypatch):
        """Test github_repo_name reads from GITHUB_REPO_NAME environment variable."""
        monkeypatch.setenv("GITHUB_REPO_NAME", "test-repo")
        settings = Settings()
        assert settings.github_repo_name == "test-repo"

    def test_github_repo_name_default_empty(self, monkeypatch):
        """Test github_repo_name defaults to empty string when not set."""
        monkeypatch.delenv("GITHUB_REPO_NAME", raising=False)
        settings = Settings()
        assert settings.github_repo_name == ""


class TestIsGitHubConfigured:
    """Tests for is_github_configured property."""

    def test_configured_with_token(self, monkeypatch):
        """Test is_github_configured returns True when token is set."""
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123token")
        settings = Settings()
        assert settings.is_github_configured is True

    def test_not_configured_without_token(self, monkeypatch):
        """Test is_github_configured returns False when token is not set."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        settings = Settings()
        assert settings.is_github_configured is False

    def test_not_configured_with_empty_token(self, monkeypatch):
        """Test is_github_configured returns False when token is empty string."""
        monkeypatch.setenv("GITHUB_TOKEN", "")
        settings = Settings()
        assert settings.is_github_configured is False

    def test_configured_ignores_owner_and_repo(self, monkeypatch):
        """Test is_github_configured only checks token, not owner/repo.
        
        Note: The adapter separately validates owner/repo, but the Settings
        property only checks if the token is present per the specification.
        """
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123token")
        monkeypatch.delenv("GITHUB_REPO_OWNER", raising=False)
        monkeypatch.delenv("GITHUB_REPO_NAME", raising=False)
        settings = Settings()
        # Token is set, so is_github_configured should be True
        assert settings.is_github_configured is True
