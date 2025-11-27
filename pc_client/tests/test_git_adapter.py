"""Tests for the GitAdapter and MockGitAdapter."""

import pytest
from unittest.mock import AsyncMock, patch

from pc_client.adapters.git_adapter import (
    GitAdapter,
    MockGitAdapter,
    is_git_available,
)


def _make_mock_process(returncode: int, stdout: bytes, stderr: bytes = b"") -> AsyncMock:
    """Helper to create a mock subprocess process."""
    mock_process = AsyncMock()
    mock_process.returncode = returncode
    mock_process.communicate = AsyncMock(return_value=(stdout, stderr))
    return mock_process


class TestIsGitAvailable:
    """Tests for is_git_available function."""

    @patch("pc_client.adapters.git_adapter.shutil.which")
    def test_returns_true_when_git_found(self, mock_which):
        """Should return True when git binary is found."""
        mock_which.return_value = "/usr/bin/git"
        assert is_git_available() is True

    @patch("pc_client.adapters.git_adapter.shutil.which")
    def test_returns_false_when_git_not_found(self, mock_which):
        """Should return False when git binary is not found."""
        mock_which.return_value = None
        assert is_git_available() is False


class TestMockGitAdapter:
    """Tests for MockGitAdapter."""

    @pytest.mark.asyncio
    async def test_get_current_branch_default(self):
        """Should return default branch 'main'."""
        adapter = MockGitAdapter()
        branch = await adapter.get_current_branch()
        assert branch == "main"

    @pytest.mark.asyncio
    async def test_get_current_branch_custom(self):
        """Should return custom branch name."""
        adapter = MockGitAdapter(branch="feature/test")
        branch = await adapter.get_current_branch()
        assert branch == "feature/test"

    @pytest.mark.asyncio
    async def test_get_current_commit_default(self):
        """Should return default commit hash."""
        adapter = MockGitAdapter()
        commit = await adapter.get_current_commit()
        assert commit == "abc1234"

    @pytest.mark.asyncio
    async def test_get_current_commit_custom(self):
        """Should return custom commit hash."""
        adapter = MockGitAdapter(commit="def5678")
        commit = await adapter.get_current_commit()
        assert commit == "def5678"

    @pytest.mark.asyncio
    async def test_is_dirty_default(self):
        """Should return False by default."""
        adapter = MockGitAdapter()
        dirty = await adapter.is_dirty()
        assert dirty is False

    @pytest.mark.asyncio
    async def test_is_dirty_true(self):
        """Should return True when set."""
        adapter = MockGitAdapter(dirty=True)
        dirty = await adapter.is_dirty()
        assert dirty is True

    @pytest.mark.asyncio
    async def test_get_last_commit_message_default(self):
        """Should return default commit message."""
        adapter = MockGitAdapter()
        message = await adapter.get_last_commit_message()
        assert message == "Test commit message"

    @pytest.mark.asyncio
    async def test_get_last_commit_message_custom(self):
        """Should return custom commit message."""
        adapter = MockGitAdapter(message="Custom message")
        message = await adapter.get_last_commit_message()
        assert message == "Custom message"

    @pytest.mark.asyncio
    async def test_get_version_info(self):
        """Should return complete version info."""
        adapter = MockGitAdapter(
            branch="develop",
            commit="xyz9876",
            dirty=True,
            message="Fix bug",
        )
        info = await adapter.get_version_info()
        assert info["branch"] == "develop"
        assert info["commit"] == "xyz9876"
        assert info["dirty"] is True
        assert info["message"] == "Fix bug"
        assert info["available"] is True
        assert "ts" in info

    @pytest.mark.asyncio
    async def test_get_version_info_unavailable(self):
        """Should return 'unknown' values when unavailable."""
        adapter = MockGitAdapter(available=False)
        info = await adapter.get_version_info()
        assert info["branch"] == "unknown"
        assert info["commit"] == "unknown"
        assert info["dirty"] is False
        assert info["message"] == ""
        assert info["available"] is False

    def test_available_property_true(self):
        """Should report as available by default."""
        adapter = MockGitAdapter()
        assert adapter.available is True

    def test_available_property_false(self):
        """Should report as unavailable when set."""
        adapter = MockGitAdapter(available=False)
        assert adapter.available is False

    def test_invalidate_cache_noop(self):
        """Should not raise error on cache invalidation."""
        adapter = MockGitAdapter()
        adapter.invalidate_cache()  # Should not raise


class TestGitAdapter:
    """Tests for GitAdapter with mocked subprocess."""

    @patch("pc_client.adapters.git_adapter.is_git_available")
    def test_adapter_unavailable_when_git_not_present(self, mock_available):
        """Adapter should be unavailable when git is not present."""
        mock_available.return_value = False
        adapter = GitAdapter()
        assert adapter.available is False

    @patch("pc_client.adapters.git_adapter.is_git_available")
    @pytest.mark.asyncio
    async def test_get_current_branch_when_unavailable(self, mock_available):
        """Should return 'unknown' when git unavailable."""
        mock_available.return_value = False
        adapter = GitAdapter()
        branch = await adapter.get_current_branch()
        assert branch == "unknown"

    @patch("pc_client.adapters.git_adapter.is_git_available")
    @pytest.mark.asyncio
    async def test_get_current_commit_when_unavailable(self, mock_available):
        """Should return 'unknown' when git unavailable."""
        mock_available.return_value = False
        adapter = GitAdapter()
        commit = await adapter.get_current_commit()
        assert commit == "unknown"

    @patch("pc_client.adapters.git_adapter.is_git_available")
    @pytest.mark.asyncio
    async def test_is_dirty_when_unavailable(self, mock_available):
        """Should return False when git unavailable."""
        mock_available.return_value = False
        adapter = GitAdapter()
        dirty = await adapter.is_dirty()
        assert dirty is False

    @patch("pc_client.adapters.git_adapter.is_git_available")
    @pytest.mark.asyncio
    async def test_get_last_commit_message_when_unavailable(self, mock_available):
        """Should return empty string when git unavailable."""
        mock_available.return_value = False
        adapter = GitAdapter()
        message = await adapter.get_last_commit_message()
        assert message == ""

    @patch("pc_client.adapters.git_adapter.is_git_available")
    @patch("pc_client.adapters.git_adapter.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_get_current_branch_parses_output(self, mock_subprocess, mock_available):
        """Should correctly parse branch name."""
        mock_available.return_value = True
        mock_subprocess.return_value = _make_mock_process(0, b"main")

        adapter = GitAdapter()
        branch = await adapter.get_current_branch()
        assert branch == "main"

    @patch("pc_client.adapters.git_adapter.is_git_available")
    @patch("pc_client.adapters.git_adapter.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_get_current_branch_handles_feature_branch(self, mock_subprocess, mock_available):
        """Should handle feature branch names with slashes."""
        mock_available.return_value = True
        mock_subprocess.return_value = _make_mock_process(0, b"feature/my-feature")

        adapter = GitAdapter()
        branch = await adapter.get_current_branch()
        assert branch == "feature/my-feature"

    @patch("pc_client.adapters.git_adapter.is_git_available")
    @patch("pc_client.adapters.git_adapter.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_get_current_commit_parses_output(self, mock_subprocess, mock_available):
        """Should correctly parse short commit hash."""
        mock_available.return_value = True
        mock_subprocess.return_value = _make_mock_process(0, b"a1b2c3d")

        adapter = GitAdapter()
        commit = await adapter.get_current_commit()
        assert commit == "a1b2c3d"

    @patch("pc_client.adapters.git_adapter.is_git_available")
    @patch("pc_client.adapters.git_adapter.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_is_dirty_returns_true_when_changes(self, mock_subprocess, mock_available):
        """Should return True when there are uncommitted changes."""
        mock_available.return_value = True
        mock_subprocess.return_value = _make_mock_process(0, b" M modified_file.py\n?? new_file.py")

        adapter = GitAdapter()
        dirty = await adapter.is_dirty()
        assert dirty is True

    @patch("pc_client.adapters.git_adapter.is_git_available")
    @patch("pc_client.adapters.git_adapter.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_is_dirty_returns_false_when_clean(self, mock_subprocess, mock_available):
        """Should return False when there are no uncommitted changes."""
        mock_available.return_value = True
        mock_subprocess.return_value = _make_mock_process(0, b"")

        adapter = GitAdapter()
        dirty = await adapter.is_dirty()
        assert dirty is False

    @patch("pc_client.adapters.git_adapter.is_git_available")
    @patch("pc_client.adapters.git_adapter.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_get_last_commit_message_parses_output(self, mock_subprocess, mock_available):
        """Should correctly parse commit message."""
        mock_available.return_value = True
        mock_subprocess.return_value = _make_mock_process(0, b"Fix systemd adapter bug\n\nMore details here")

        adapter = GitAdapter()
        message = await adapter.get_last_commit_message()
        assert message == "Fix systemd adapter bug"

    @patch("pc_client.adapters.git_adapter.is_git_available")
    @patch("pc_client.adapters.git_adapter.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_get_version_info_returns_complete_info(self, mock_subprocess, mock_available):
        """Should return complete version info."""
        mock_available.return_value = True

        # Mock will be called multiple times with different returns
        mock_subprocess.side_effect = [
            _make_mock_process(0, b".git"),  # _is_in_git_repo
            _make_mock_process(0, b"develop"),  # get_current_branch
            _make_mock_process(0, b"xyz9876"),  # get_current_commit
            _make_mock_process(0, b" M file.py"),  # is_dirty
            _make_mock_process(0, b"Test message"),  # get_last_commit_message
        ]

        adapter = GitAdapter()
        info = await adapter.get_version_info()
        assert info["branch"] == "develop"
        assert info["commit"] == "xyz9876"
        assert info["dirty"] is True
        assert info["message"] == "Test message"
        assert info["available"] is True
        assert "ts" in info

    @patch("pc_client.adapters.git_adapter.is_git_available")
    @patch("pc_client.adapters.git_adapter.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_get_version_info_not_in_git_repo(self, mock_subprocess, mock_available):
        """Should return unavailable info when not in git repo."""
        mock_available.return_value = True
        mock_subprocess.return_value = _make_mock_process(128, b"", b"fatal: not a git repository")

        adapter = GitAdapter()
        info = await adapter.get_version_info()
        assert info["branch"] == "unknown"
        assert info["commit"] == "unknown"
        assert info["dirty"] is False
        assert info["message"] == ""
        assert info["available"] is False

    @patch("pc_client.adapters.git_adapter.is_git_available")
    @patch("pc_client.adapters.git_adapter.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_caching_returns_cached_data(self, mock_subprocess, mock_available):
        """Should return cached data on subsequent calls."""
        mock_available.return_value = True
        mock_subprocess.side_effect = [
            _make_mock_process(0, b".git"),  # _is_in_git_repo
            _make_mock_process(0, b"main"),  # get_current_branch
            _make_mock_process(0, b"abc1234"),  # get_current_commit
            _make_mock_process(0, b""),  # is_dirty
            _make_mock_process(0, b"Message"),  # get_last_commit_message
        ]

        adapter = GitAdapter(cache_ttl=60)

        # First call
        info1 = await adapter.get_version_info()
        assert info1["branch"] == "main"

        # Second call should return cached data (subprocess not called again)
        info2 = await adapter.get_version_info()
        assert info2["branch"] == "main"
        assert info2["ts"] == info1["ts"]

        # Verify subprocess was only called for first request
        assert mock_subprocess.call_count == 5

    @patch("pc_client.adapters.git_adapter.is_git_available")
    def test_invalidate_cache(self, mock_available):
        """Should invalidate cache when called."""
        mock_available.return_value = True
        adapter = GitAdapter()
        adapter._cache = {"test": "data"}
        adapter._cache_ts = 999999

        adapter.invalidate_cache()

        assert adapter._cache == {}
        assert adapter._cache_ts == 0

    @patch("pc_client.adapters.git_adapter.is_git_available")
    @patch("pc_client.adapters.git_adapter.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_handles_command_failure(self, mock_subprocess, mock_available):
        """Should handle command failure gracefully."""
        mock_available.return_value = True
        mock_subprocess.return_value = _make_mock_process(1, b"", b"error")

        adapter = GitAdapter()
        branch = await adapter.get_current_branch()
        assert branch == "unknown"

    @patch("pc_client.adapters.git_adapter.is_git_available")
    @patch("pc_client.adapters.git_adapter.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_add_file_success(self, mock_subprocess, mock_available):
        """Should successfully add a file."""
        mock_available.return_value = True
        mock_subprocess.return_value = _make_mock_process(0, b"")

        adapter = GitAdapter()
        success, error = await adapter.add_file("test.md")
        assert success is True
        assert error == ""

    @patch("pc_client.adapters.git_adapter.is_git_available")
    @patch("pc_client.adapters.git_adapter.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_add_file_failure(self, mock_subprocess, mock_available):
        """Should return error when add fails."""
        mock_available.return_value = True
        mock_subprocess.return_value = _make_mock_process(1, b"", b"fatal: pathspec 'test.md' did not match any files")

        adapter = GitAdapter()
        success, error = await adapter.add_file("test.md")
        assert success is False
        assert "pathspec" in error

    @patch("pc_client.adapters.git_adapter.is_git_available")
    @pytest.mark.asyncio
    async def test_add_file_empty_path(self, mock_available):
        """Should return error for empty path."""
        mock_available.return_value = True
        adapter = GitAdapter()
        success, error = await adapter.add_file("")
        assert success is False
        assert "pusta" in error.lower()

    @patch("pc_client.adapters.git_adapter.is_git_available")
    @pytest.mark.asyncio
    async def test_add_file_unavailable(self, mock_available):
        """Should return error when git is unavailable."""
        mock_available.return_value = False
        adapter = GitAdapter()
        success, error = await adapter.add_file("test.md")
        assert success is False
        assert "dostępny" in error.lower()

    @patch("pc_client.adapters.git_adapter.is_git_available")
    @patch("pc_client.adapters.git_adapter.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_commit_success(self, mock_subprocess, mock_available):
        """Should successfully commit."""
        mock_available.return_value = True
        mock_subprocess.return_value = _make_mock_process(0, b"[main abc1234] Test commit")

        adapter = GitAdapter()
        success, error = await adapter.commit("Test commit")
        assert success is True
        assert error == ""

    @patch("pc_client.adapters.git_adapter.is_git_available")
    @patch("pc_client.adapters.git_adapter.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_commit_failure(self, mock_subprocess, mock_available):
        """Should return error when commit fails."""
        mock_available.return_value = True
        mock_subprocess.return_value = _make_mock_process(1, b"", b"nothing to commit")

        adapter = GitAdapter()
        success, error = await adapter.commit("Test commit")
        assert success is False
        assert "nothing to commit" in error

    @patch("pc_client.adapters.git_adapter.is_git_available")
    @pytest.mark.asyncio
    async def test_commit_empty_message(self, mock_available):
        """Should return error for empty message."""
        mock_available.return_value = True
        adapter = GitAdapter()
        success, error = await adapter.commit("")
        assert success is False
        assert "pusta" in error.lower()

    @patch("pc_client.adapters.git_adapter.is_git_available")
    @pytest.mark.asyncio
    async def test_commit_unavailable(self, mock_available):
        """Should return error when git is unavailable."""
        mock_available.return_value = False
        adapter = GitAdapter()
        success, error = await adapter.commit("Test commit")
        assert success is False
        assert "dostępny" in error.lower()

    @patch("pc_client.adapters.git_adapter.is_git_available")
    @patch("pc_client.adapters.git_adapter.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_create_branch_and_checkout_success(self, mock_subprocess, mock_available):
        """Should successfully create and checkout a branch."""
        mock_available.return_value = True
        mock_subprocess.return_value = _make_mock_process(0, b"Switched to a new branch 'feat/123-test'")

        adapter = GitAdapter()
        success, error = await adapter.create_branch_and_checkout("feat/123-test", "main")
        assert success is True
        assert error == ""


class TestMockGitAdapterNewMethods:
    """Tests for new MockGitAdapter methods."""

    @pytest.mark.asyncio
    async def test_add_file_success(self):
        """Should return success for add_file."""
        adapter = MockGitAdapter()
        success, error = await adapter.add_file("test.md")
        assert success is True
        assert error == ""

    @pytest.mark.asyncio
    async def test_add_file_empty_path(self):
        """Should return error for empty path."""
        adapter = MockGitAdapter()
        success, error = await adapter.add_file("")
        assert success is False
        assert "pusta" in error.lower()

    @pytest.mark.asyncio
    async def test_add_file_unavailable(self):
        """Should return error when unavailable."""
        adapter = MockGitAdapter(available=False)
        success, error = await adapter.add_file("test.md")
        assert success is False
        assert "dostępny" in error.lower()

    @pytest.mark.asyncio
    async def test_commit_success(self):
        """Should return success for commit."""
        adapter = MockGitAdapter()
        success, error = await adapter.commit("Test commit")
        assert success is True
        assert error == ""

    @pytest.mark.asyncio
    async def test_commit_empty_message(self):
        """Should return error for empty message."""
        adapter = MockGitAdapter()
        success, error = await adapter.commit("")
        assert success is False
        assert "pusta" in error.lower()

    @pytest.mark.asyncio
    async def test_commit_unavailable(self):
        """Should return error when unavailable."""
        adapter = MockGitAdapter(available=False)
        success, error = await adapter.commit("Test commit")
        assert success is False
        assert "dostępny" in error.lower()

    @pytest.mark.asyncio
    async def test_create_branch_and_checkout_success(self):
        """Should create and checkout a branch."""
        adapter = MockGitAdapter()
        success, error = await adapter.create_branch_and_checkout("feat/123-test", "main")
        assert success is True
        assert error == ""
        # Verify branch was added and is now current
        assert adapter._branch == "feat/123-test"
        assert "feat/123-test" in adapter._branches
