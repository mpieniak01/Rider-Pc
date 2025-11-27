"""Tests for the GitHub adapter."""

import pytest
from pc_client.adapters.github_adapter import parse_checklist_progress, GitHubAdapter, MockGitHubAdapter


class TestParseChecklistProgress:
    """Tests for the parse_checklist_progress function."""

    def test_empty_body(self):
        """Test with empty body."""
        done, total = parse_checklist_progress("")
        assert done == 0
        assert total == 0

    def test_none_body(self):
        """Test with None body."""
        done, total = parse_checklist_progress(None)
        assert done == 0
        assert total == 0

    def test_no_checkboxes(self):
        """Test with body containing no checkboxes."""
        body = "This is a description without any checkboxes."
        done, total = parse_checklist_progress(body)
        assert done == 0
        assert total == 0

    def test_single_unchecked(self):
        """Test with single unchecked checkbox."""
        body = "- [ ] Task one"
        done, total = parse_checklist_progress(body)
        assert done == 0
        assert total == 1

    def test_single_checked(self):
        """Test with single checked checkbox."""
        body = "- [x] Task one"
        done, total = parse_checklist_progress(body)
        assert done == 1
        assert total == 1

    def test_mixed_checkboxes(self):
        """Test with mixed checked and unchecked checkboxes."""
        body = """## Tasks
- [x] First task completed
- [ ] Second task pending
- [x] Third task done
- [ ] Fourth task to do
"""
        done, total = parse_checklist_progress(body)
        assert done == 2
        assert total == 4

    def test_uppercase_x(self):
        """Test with uppercase X in checkbox."""
        body = "- [X] Task with uppercase X"
        done, total = parse_checklist_progress(body)
        assert done == 1
        assert total == 1

    def test_indented_checkboxes(self):
        """Test with indented checkboxes."""
        body = """  - [ ] Indented unchecked
  - [x] Indented checked
"""
        done, total = parse_checklist_progress(body)
        assert done == 1
        assert total == 2

    def test_nested_lists(self):
        """Test with nested list checkboxes."""
        body = """- [ ] Parent task
  - [x] Child task 1
  - [ ] Child task 2
"""
        done, total = parse_checklist_progress(body)
        assert done == 1
        assert total == 3

    def test_all_completed(self):
        """Test with all checkboxes checked."""
        body = """- [x] Task 1
- [x] Task 2
- [x] Task 3
"""
        done, total = parse_checklist_progress(body)
        assert done == 3
        assert total == 3


class TestGitHubAdapterConfiguration:
    """Tests for GitHubAdapter configuration."""

    def test_not_configured_without_token(self):
        """Test adapter is not configured without token."""
        adapter = GitHubAdapter(token=None, owner="owner", repo="repo")
        assert not adapter.configured

    def test_not_configured_without_owner(self):
        """Test adapter is not configured without owner."""
        adapter = GitHubAdapter(token="token", owner="", repo="repo")
        assert not adapter.configured

    def test_not_configured_without_repo(self):
        """Test adapter is not configured without repo."""
        adapter = GitHubAdapter(token="token", owner="owner", repo="")
        assert not adapter.configured

    def test_configured_with_all_fields(self):
        """Test adapter is configured with all required fields."""
        adapter = GitHubAdapter(token="token", owner="owner", repo="repo")
        assert adapter.configured

    def test_repo_full_name(self):
        """Test repo_full_name property."""
        adapter = GitHubAdapter(token="token", owner="myorg", repo="myrepo")
        assert adapter.repo_full_name == "myorg/myrepo"


class TestGitHubAdapterNotConfigured:
    """Tests for GitHubAdapter when not configured."""

    @pytest.mark.asyncio
    async def test_get_open_issues_returns_error(self):
        """Test get_open_issues returns error when not configured."""
        adapter = GitHubAdapter(token=None, owner="", repo="")
        result = await adapter.get_open_issues()

        assert result["configured"] is False
        assert result["issues"] == []
        assert "error" in result
        assert "niekompletna" in result["error"].lower()


class TestMockGitHubAdapter:
    """Tests for MockGitHubAdapter."""

    @pytest.mark.asyncio
    async def test_mock_configured(self):
        """Test mock adapter returns configured status."""
        adapter = MockGitHubAdapter(configured=True)
        result = await adapter.get_open_issues()
        assert result["configured"] is True

    @pytest.mark.asyncio
    async def test_mock_not_configured(self):
        """Test mock adapter returns not configured status."""
        adapter = MockGitHubAdapter(configured=False)
        result = await adapter.get_open_issues()
        assert result["configured"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_mock_returns_issues(self):
        """Test mock adapter returns provided issues."""
        mock_issues = [
            {"number": 1, "title": "Issue 1"},
            {"number": 2, "title": "Issue 2"},
        ]
        adapter = MockGitHubAdapter(configured=True, issues=mock_issues)
        result = await adapter.get_open_issues()
        assert len(result["issues"]) == 2
        assert result["issues"][0]["number"] == 1

    @pytest.mark.asyncio
    async def test_mock_respects_limit(self):
        """Test mock adapter respects limit parameter."""
        mock_issues = [{"number": i, "title": f"Issue {i}"} for i in range(10)]
        adapter = MockGitHubAdapter(configured=True, issues=mock_issues)
        result = await adapter.get_open_issues(limit=3)
        assert len(result["issues"]) == 3

    @pytest.mark.asyncio
    async def test_mock_invalidate_cache_is_noop(self):
        """Test mock adapter invalidate_cache is a no-op."""
        adapter = MockGitHubAdapter(configured=True)
        # Should not raise
        adapter.invalidate_cache()

    @pytest.mark.asyncio
    async def test_mock_close_is_noop(self):
        """Test mock adapter close is a no-op."""
        adapter = MockGitHubAdapter(configured=True)
        # Should not raise
        await adapter.close()

    @pytest.mark.asyncio
    async def test_mock_get_collaborators(self):
        """Test mock adapter returns collaborators."""
        adapter = MockGitHubAdapter(configured=True, collaborators=["alice", "bob"])
        collaborators = await adapter.get_collaborators()
        assert collaborators == ["alice", "bob"]

    @pytest.mark.asyncio
    async def test_mock_get_collaborators_not_configured(self):
        """Test mock adapter returns empty collaborators when not configured."""
        adapter = MockGitHubAdapter(configured=False)
        collaborators = await adapter.get_collaborators()
        assert collaborators == []

    @pytest.mark.asyncio
    async def test_mock_get_labels(self):
        """Test mock adapter returns labels."""
        adapter = MockGitHubAdapter(configured=True, labels=["bug", "feature"])
        labels = await adapter.get_labels()
        assert labels == ["bug", "feature"]

    @pytest.mark.asyncio
    async def test_mock_get_labels_not_configured(self):
        """Test mock adapter returns empty labels when not configured."""
        adapter = MockGitHubAdapter(configured=False)
        labels = await adapter.get_labels()
        assert labels == []

    @pytest.mark.asyncio
    async def test_mock_create_issue_success(self):
        """Test mock adapter creates issue successfully."""
        adapter = MockGitHubAdapter(configured=True)
        result = await adapter.create_issue(title="Test Issue", body="Test body", assignees=["alice"], labels=["bug"])
        assert result["success"] is True
        assert result["number"] == 100
        assert "url" in result
        assert result["title"] == "Test Issue"

    @pytest.mark.asyncio
    async def test_mock_create_issue_not_configured(self):
        """Test mock adapter fails to create issue when not configured."""
        adapter = MockGitHubAdapter(configured=False)
        result = await adapter.create_issue(title="Test Issue")
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_mock_create_issue_empty_title(self):
        """Test mock adapter fails with empty title."""
        adapter = MockGitHubAdapter(configured=True)
        result = await adapter.create_issue(title="")
        assert result["success"] is False
        assert "error" in result
