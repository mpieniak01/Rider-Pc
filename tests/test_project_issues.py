"""Tests for the /api/project/issues endpoint."""

import sys
from fastapi.testclient import TestClient

from pc_client.api.server import create_app
from pc_client.cache import CacheManager
from pc_client.config import Settings

# Import the module correctly (avoiding __init__.py shadowing)
import pc_client.api.routers.project_router

project_router_module = sys.modules['pc_client.api.routers.project_router']

# Import slugify after module is properly loaded
from pc_client.api.routers.project_router import slugify


class TestSlugify:
    """Tests for the slugify function."""

    def test_basic_text(self):
        """Test basic text slugification."""
        assert slugify("Hello World") == "hello-world"

    def test_polish_characters(self):
        """Test Polish characters are transliterated or removed."""
        assert slugify("Nowa Funkcja X") == "nowa-funkcja-x"
        # NFKD normalization handles some Polish diacritics:
        # ż (U+017C) -> z with combining dot above -> 'z' after stripping
        # ó (U+00F3) -> o with combining acute -> 'o' after stripping
        # ł (U+0142) has no NFKD decomposition -> removed entirely
        # ć (U+0107) -> c with combining acute -> 'c' after stripping
        # Result: "żółć" -> "zoc" (without ł which has no decomposition)
        result = slugify("żółć")
        assert result == "zoc"  # ł is removed as it has no NFKD decomposition

    def test_special_characters(self):
        """Test special characters are removed."""
        assert slugify("Test@#$%^&*()!") == "test"

    def test_multiple_spaces(self):
        """Test multiple spaces become single hyphen."""
        assert slugify("hello   world") == "hello-world"

    def test_underscores(self):
        """Test underscores become hyphens."""
        assert slugify("hello_world_test") == "hello-world-test"

    def test_max_length(self):
        """Test max length truncation."""
        result = slugify("a" * 100, max_length=50)
        assert len(result) <= 50

    def test_trailing_hyphens_removed(self):
        """Test trailing hyphens are removed after truncation."""
        result = slugify("hello world-", max_length=11)
        assert not result.endswith("-")

    def test_empty_string(self):
        """Test empty string returns empty."""
        assert slugify("") == ""


def make_client(db_path, github_token=None, github_owner="", github_repo=""):
    """Create a test client with GitHub configuration."""
    settings = Settings()
    # Override GitHub settings for testing
    settings.github_token = github_token
    settings.github_repo_owner = github_owner
    settings.github_repo_name = github_repo
    settings.github_cache_ttl_seconds = 300

    cache = CacheManager(db_path=str(db_path))
    app = create_app(settings, cache)
    return TestClient(app)


def test_project_issues_not_configured(tmp_path, monkeypatch):
    """Test endpoint returns error when GitHub is not configured."""
    # Reset the singleton
    project_router_module._github_adapter = None

    client = make_client(tmp_path / "cache.db")

    resp = client.get("/api/project/issues")
    assert resp.status_code == 200
    data = resp.json()

    assert data["configured"] is False
    assert data["issues"] == []
    assert "error" in data
    assert "niekompletna" in data["error"].lower()


def test_project_issues_with_mock_adapter(tmp_path, monkeypatch):
    """Test endpoint with mocked GitHub adapter."""
    # Reset the singleton
    project_router_module._github_adapter = None

    mock_response = {
        "repo": "rider-pc",
        "issues": [
            {
                "number": 15,
                "title": "Implementacja Systemd Adapter",
                "state": "open",
                "tasks_total": 5,
                "tasks_done": 5,
                "progress_pct": 100,
                "assignee": "mpieniak01",
                "url": "https://github.com/mpieniak01/rider-pc/issues/15",
            },
            {
                "number": 16,
                "title": "Dashboard Projektowy",
                "state": "open",
                "tasks_total": 4,
                "tasks_done": 1,
                "progress_pct": 25,
                "assignee": None,
                "url": "https://github.com/mpieniak01/rider-pc/issues/16",
            },
        ],
        "configured": True,
        "cached": False,
        "timestamp": 1716200000,
    }

    async def mock_get_open_issues(self, limit=10, force_refresh=False):
        return mock_response

    monkeypatch.setattr(
        "pc_client.adapters.github_adapter.GitHubAdapter.get_open_issues",
        mock_get_open_issues,
    )

    client = make_client(
        tmp_path / "cache.db",
        github_token="fake_token",
        github_owner="mpieniak01",
        github_repo="rider-pc",
    )

    resp = client.get("/api/project/issues")
    assert resp.status_code == 200
    data = resp.json()

    assert data["configured"] is True
    assert len(data["issues"]) == 2
    assert data["issues"][0]["number"] == 15
    assert data["issues"][0]["progress_pct"] == 100
    assert data["issues"][1]["number"] == 16
    assert data["issues"][1]["progress_pct"] == 25


def test_project_issues_with_limit(tmp_path, monkeypatch):
    """Test endpoint respects limit parameter."""
    # Reset the singleton
    project_router_module._github_adapter = None

    captured_limit = {}

    async def mock_get_open_issues(self, limit=10, force_refresh=False):
        captured_limit["value"] = limit
        return {
            "repo": "rider-pc",
            "issues": [],
            "configured": True,
            "cached": False,
            "timestamp": 1716200000,
        }

    monkeypatch.setattr(
        "pc_client.adapters.github_adapter.GitHubAdapter.get_open_issues",
        mock_get_open_issues,
    )

    client = make_client(
        tmp_path / "cache.db",
        github_token="fake_token",
        github_owner="mpieniak01",
        github_repo="rider-pc",
    )

    resp = client.get("/api/project/issues?limit=5")
    assert resp.status_code == 200
    assert captured_limit["value"] == 5


def test_project_issues_with_refresh(tmp_path, monkeypatch):
    """Test endpoint respects refresh parameter."""
    # Reset the singleton
    project_router_module._github_adapter = None

    captured_params = {}

    async def mock_get_open_issues(self, limit=10, force_refresh=False):
        captured_params["force_refresh"] = force_refresh
        return {
            "repo": "rider-pc",
            "issues": [],
            "configured": True,
            "cached": False,
            "timestamp": 1716200000,
        }

    monkeypatch.setattr(
        "pc_client.adapters.github_adapter.GitHubAdapter.get_open_issues",
        mock_get_open_issues,
    )

    client = make_client(
        tmp_path / "cache.db",
        github_token="fake_token",
        github_owner="mpieniak01",
        github_repo="rider-pc",
    )

    resp = client.get("/api/project/issues?refresh=true")
    assert resp.status_code == 200
    assert captured_params["force_refresh"] is True


def test_project_refresh_endpoint(tmp_path, monkeypatch):
    """Test the refresh endpoint invalidates cache and fetches fresh data."""
    # Reset the singleton
    project_router_module._github_adapter = None

    invalidate_called = {"value": False}

    def mock_invalidate_cache(self):
        invalidate_called["value"] = True

    async def mock_get_open_issues(self, limit=10, force_refresh=False):
        return {
            "repo": "rider-pc",
            "issues": [],
            "configured": True,
            "cached": False,
            "timestamp": 1716200000,
        }

    monkeypatch.setattr(
        "pc_client.adapters.github_adapter.GitHubAdapter.invalidate_cache",
        mock_invalidate_cache,
    )
    monkeypatch.setattr(
        "pc_client.adapters.github_adapter.GitHubAdapter.get_open_issues",
        mock_get_open_issues,
    )

    client = make_client(
        tmp_path / "cache.db",
        github_token="fake_token",
        github_owner="mpieniak01",
        github_repo="rider-pc",
    )

    resp = client.post("/api/project/refresh")
    assert resp.status_code == 200
    assert invalidate_called["value"] is True


def test_project_meta_endpoint(tmp_path, monkeypatch):
    """Test the meta endpoint returns collaborators, labels, and branches."""
    # Reset the singletons
    project_router_module._github_adapter = None
    project_router_module._git_adapter = None

    async def mock_get_collaborators(self):
        return ["alice", "bob"]

    async def mock_get_labels(self):
        return ["bug", "feature", "enhancement"]

    async def mock_get_local_branches(self):
        return ["main", "develop", "feature/test"]

    async def mock_get_current_branch(self):
        return "main"

    monkeypatch.setattr(
        "pc_client.adapters.github_adapter.GitHubAdapter.get_collaborators",
        mock_get_collaborators,
    )
    monkeypatch.setattr(
        "pc_client.adapters.github_adapter.GitHubAdapter.get_labels",
        mock_get_labels,
    )
    monkeypatch.setattr(
        "pc_client.adapters.git_adapter.GitAdapter.get_local_branches",
        mock_get_local_branches,
    )
    monkeypatch.setattr(
        "pc_client.adapters.git_adapter.GitAdapter.get_current_branch",
        mock_get_current_branch,
    )

    client = make_client(
        tmp_path / "cache.db",
        github_token="fake_token",
        github_owner="mpieniak01",
        github_repo="rider-pc",
    )

    resp = client.get("/api/project/meta")
    assert resp.status_code == 200
    data = resp.json()

    assert data["collaborators"] == ["alice", "bob"]
    assert data["labels"] == ["bug", "feature", "enhancement"]
    assert data["branches"] == ["main", "develop", "feature/test"]
    assert data["current_branch"] == "main"
    assert data["configured"] is True


def test_create_task_endpoint_success(tmp_path, monkeypatch):
    """Test creating a task successfully."""
    # Reset the singletons
    project_router_module._github_adapter = None
    project_router_module._git_adapter = None

    async def mock_create_issue(self, title, body="", assignees=None, labels=None):
        return {
            "success": True,
            "number": 150,
            "url": "https://github.com/mpieniak01/rider-pc/issues/150",
            "title": title,
        }

    async def mock_get_current_branch(self):
        return "main"

    monkeypatch.setattr(
        "pc_client.adapters.github_adapter.GitHubAdapter.create_issue",
        mock_create_issue,
    )
    monkeypatch.setattr(
        "pc_client.adapters.git_adapter.GitAdapter.get_current_branch",
        mock_get_current_branch,
    )

    client = make_client(
        tmp_path / "cache.db",
        github_token="fake_token",
        github_owner="mpieniak01",
        github_repo="rider-pc",
    )

    resp = client.post(
        "/api/project/create-task",
        json={
            "title": "Test Issue",
            "body": "Test description",
            "git_strategy": "current",
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["success"] is True
    assert data["issue"]["number"] == 150
    assert data["branch"] == "main"


def test_create_task_with_new_branch(tmp_path, monkeypatch):
    """Test creating a task with new branch strategy."""
    # Reset the singletons
    project_router_module._github_adapter = None
    project_router_module._git_adapter = None

    created_branch = {"name": None}

    async def mock_create_issue(self, title, body="", assignees=None, labels=None):
        return {
            "success": True,
            "number": 151,
            "url": "https://github.com/mpieniak01/rider-pc/issues/151",
            "title": title,
        }

    async def mock_create_branch(self, name, base="main"):
        created_branch["name"] = name
        return True, ""

    async def mock_is_dirty(self):
        return False

    monkeypatch.setattr(
        "pc_client.adapters.github_adapter.GitHubAdapter.create_issue",
        mock_create_issue,
    )
    monkeypatch.setattr(
        "pc_client.adapters.git_adapter.GitAdapter.create_branch",
        mock_create_branch,
    )
    monkeypatch.setattr(
        "pc_client.adapters.git_adapter.GitAdapter.is_dirty",
        mock_is_dirty,
    )

    client = make_client(
        tmp_path / "cache.db",
        github_token="fake_token",
        github_owner="mpieniak01",
        github_repo="rider-pc",
    )

    resp = client.post(
        "/api/project/create-task",
        json={
            "title": "Nowa Funkcja X",
            "git_strategy": "new_branch",
            "base_branch": "main",
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["success"] is True
    assert "feat/151-" in created_branch["name"]
    assert "nowa-funkcja-x" in created_branch["name"]


def test_create_task_issue_creation_fails(tmp_path, monkeypatch):
    """Test that endpoint returns error when issue creation fails."""
    # Reset the singletons
    project_router_module._github_adapter = None
    project_router_module._git_adapter = None

    async def mock_create_issue(self, title, body="", assignees=None, labels=None):
        return {
            "success": False,
            "error": "Błąd API GitHub",
        }

    monkeypatch.setattr(
        "pc_client.adapters.github_adapter.GitHubAdapter.create_issue",
        mock_create_issue,
    )

    client = make_client(
        tmp_path / "cache.db",
        github_token="fake_token",
        github_owner="mpieniak01",
        github_repo="rider-pc",
    )

    resp = client.post(
        "/api/project/create-task",
        json={
            "title": "Test Issue",
        },
    )
    assert resp.status_code == 400
    data = resp.json()

    assert data["success"] is False
    assert "error" in data


def test_create_task_branch_fails_with_warning(tmp_path, monkeypatch):
    """Test that warning is returned when branch operation fails."""
    # Reset the singletons
    project_router_module._github_adapter = None
    project_router_module._git_adapter = None

    async def mock_create_issue(self, title, body="", assignees=None, labels=None):
        return {
            "success": True,
            "number": 152,
            "url": "https://github.com/mpieniak01/rider-pc/issues/152",
            "title": title,
        }

    async def mock_create_branch(self, name, base="main"):
        return False, "Dirty repository state"

    async def mock_is_dirty(self):
        return False

    monkeypatch.setattr(
        "pc_client.adapters.github_adapter.GitHubAdapter.create_issue",
        mock_create_issue,
    )
    monkeypatch.setattr(
        "pc_client.adapters.git_adapter.GitAdapter.create_branch",
        mock_create_branch,
    )
    monkeypatch.setattr(
        "pc_client.adapters.git_adapter.GitAdapter.is_dirty",
        mock_is_dirty,
    )

    client = make_client(
        tmp_path / "cache.db",
        github_token="fake_token",
        github_owner="mpieniak01",
        github_repo="rider-pc",
    )

    resp = client.post(
        "/api/project/create-task",
        json={
            "title": "Test Issue",
            "git_strategy": "new_branch",
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["success"] is True
    assert "warning" in data
    assert "#152" in data["warning"]


def test_create_task_with_main_strategy(tmp_path, monkeypatch):
    """Test creating a task with main git strategy."""
    # Reset the singletons
    project_router_module._github_adapter = None
    project_router_module._git_adapter = None

    async def mock_create_issue(self, title, body="", assignees=None, labels=None):
        return {
            "success": True,
            "number": 153,
            "url": "https://github.com/mpieniak01/rider-pc/issues/153",
            "title": title,
        }

    async def mock_checkout_branch(self, name):
        return True, ""

    async def mock_is_dirty(self):
        return False

    monkeypatch.setattr(
        "pc_client.adapters.github_adapter.GitHubAdapter.create_issue",
        mock_create_issue,
    )
    monkeypatch.setattr(
        "pc_client.adapters.git_adapter.GitAdapter.checkout_branch",
        mock_checkout_branch,
    )
    monkeypatch.setattr(
        "pc_client.adapters.git_adapter.GitAdapter.is_dirty",
        mock_is_dirty,
    )

    client = make_client(
        tmp_path / "cache.db",
        github_token="fake_token",
        github_owner="mpieniak01",
        github_repo="rider-pc",
    )

    resp = client.post(
        "/api/project/create-task",
        json={
            "title": "Test Issue",
            "git_strategy": "main",
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["success"] is True
    assert data["branch"] == "main"


def test_create_task_with_existing_strategy(tmp_path, monkeypatch):
    """Test creating a task with existing branch strategy."""
    # Reset the singletons
    project_router_module._github_adapter = None
    project_router_module._git_adapter = None

    async def mock_create_issue(self, title, body="", assignees=None, labels=None):
        return {
            "success": True,
            "number": 154,
            "url": "https://github.com/mpieniak01/rider-pc/issues/154",
            "title": title,
        }

    async def mock_checkout_branch(self, name):
        return True, ""

    async def mock_is_dirty(self):
        return False

    monkeypatch.setattr(
        "pc_client.adapters.github_adapter.GitHubAdapter.create_issue",
        mock_create_issue,
    )
    monkeypatch.setattr(
        "pc_client.adapters.git_adapter.GitAdapter.checkout_branch",
        mock_checkout_branch,
    )
    monkeypatch.setattr(
        "pc_client.adapters.git_adapter.GitAdapter.is_dirty",
        mock_is_dirty,
    )

    client = make_client(
        tmp_path / "cache.db",
        github_token="fake_token",
        github_owner="mpieniak01",
        github_repo="rider-pc",
    )

    resp = client.post(
        "/api/project/create-task",
        json={
            "title": "Test Issue",
            "git_strategy": "existing",
            "existing_branch": "develop",
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["success"] is True
    assert data["branch"] == "develop"


def test_create_task_existing_strategy_no_branch(tmp_path, monkeypatch):
    """Test that existing strategy without branch returns error."""
    # Reset the singletons
    project_router_module._github_adapter = None
    project_router_module._git_adapter = None

    async def mock_create_issue(self, title, body="", assignees=None, labels=None):
        return {
            "success": True,
            "number": 155,
            "url": "https://github.com/mpieniak01/rider-pc/issues/155",
            "title": title,
        }

    async def mock_is_dirty(self):
        return False

    monkeypatch.setattr(
        "pc_client.adapters.github_adapter.GitHubAdapter.create_issue",
        mock_create_issue,
    )
    monkeypatch.setattr(
        "pc_client.adapters.git_adapter.GitAdapter.is_dirty",
        mock_is_dirty,
    )

    client = make_client(
        tmp_path / "cache.db",
        github_token="fake_token",
        github_owner="mpieniak01",
        github_repo="rider-pc",
    )

    resp = client.post(
        "/api/project/create-task",
        json={
            "title": "Test Issue",
            "git_strategy": "existing",
        },
    )
    assert resp.status_code == 400
    data = resp.json()

    assert "error" in data


def test_create_task_dirty_repo_returns_409(tmp_path, monkeypatch):
    """Test that dirty repository blocks branch operations with 409 Conflict."""
    # Reset the singletons
    project_router_module._github_adapter = None
    project_router_module._git_adapter = None

    async def mock_create_issue(self, title, body="", assignees=None, labels=None):
        return {
            "success": True,
            "number": 156,
            "url": "https://github.com/mpieniak01/rider-pc/issues/156",
            "title": title,
        }

    async def mock_is_dirty(self):
        return True

    monkeypatch.setattr(
        "pc_client.adapters.github_adapter.GitHubAdapter.create_issue",
        mock_create_issue,
    )
    monkeypatch.setattr(
        "pc_client.adapters.git_adapter.GitAdapter.is_dirty",
        mock_is_dirty,
    )

    client = make_client(
        tmp_path / "cache.db",
        github_token="fake_token",
        github_owner="mpieniak01",
        github_repo="rider-pc",
    )

    resp = client.post(
        "/api/project/create-task",
        json={
            "title": "Test Issue",
            "git_strategy": "new_branch",
        },
    )
    assert resp.status_code == 409
    data = resp.json()

    # Issue should still be created
    assert data["success"] is True
    assert data["issue"]["number"] == 156
    # Warning should indicate dirty repo
    assert "warning" in data
    assert "niezatwierdzone" in data["warning"].lower()


def test_create_task_dirty_repo_allows_current_strategy(tmp_path, monkeypatch):
    """Test that dirty repository does not block 'current' git strategy."""
    # Reset the singletons
    project_router_module._github_adapter = None
    project_router_module._git_adapter = None

    async def mock_create_issue(self, title, body="", assignees=None, labels=None):
        return {
            "success": True,
            "number": 157,
            "url": "https://github.com/mpieniak01/rider-pc/issues/157",
            "title": title,
        }

    async def mock_is_dirty(self):
        return True

    async def mock_get_current_branch(self):
        return "feature-xyz"

    monkeypatch.setattr(
        "pc_client.adapters.github_adapter.GitHubAdapter.create_issue",
        mock_create_issue,
    )
    monkeypatch.setattr(
        "pc_client.adapters.git_adapter.GitAdapter.is_dirty",
        mock_is_dirty,
    )
    monkeypatch.setattr(
        "pc_client.adapters.git_adapter.GitAdapter.get_current_branch",
        mock_get_current_branch,
    )

    client = make_client(
        tmp_path / "cache.db",
        github_token="fake_token",
        github_owner="mpieniak01",
        github_repo="rider-pc",
    )

    resp = client.post(
        "/api/project/create-task",
        json={
            "title": "Test Issue",
            "git_strategy": "current",
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["success"] is True
    assert data["issue"]["number"] == 157
    assert data["branch"] == "feature-xyz"
    # No warning should be present for 'current' strategy
    assert "warning" not in data


def test_create_task_with_auto_init(tmp_path, monkeypatch):
    """Test creating a task with auto_init enabled creates docs file."""
    # Reset the singletons
    project_router_module._github_adapter = None
    project_router_module._git_adapter = None

    created_branch = {"name": None}
    added_files = []
    committed_messages = []

    async def mock_create_issue(self, title, body="", assignees=None, labels=None):
        return {
            "success": True,
            "number": 160,
            "url": "https://github.com/mpieniak01/rider-pc/issues/160",
            "title": title,
        }

    async def mock_create_branch_and_checkout(self, name, base="main"):
        created_branch["name"] = name
        return True, ""

    async def mock_is_dirty(self):
        return False

    async def mock_add_file(self, path):
        added_files.append(path)
        return True, ""

    async def mock_commit(self, message):
        committed_messages.append(message)
        return True, ""

    monkeypatch.setattr(
        "pc_client.adapters.github_adapter.GitHubAdapter.create_issue",
        mock_create_issue,
    )
    monkeypatch.setattr(
        "pc_client.adapters.git_adapter.GitAdapter.create_branch_and_checkout",
        mock_create_branch_and_checkout,
    )
    monkeypatch.setattr(
        "pc_client.adapters.git_adapter.GitAdapter.is_dirty",
        mock_is_dirty,
    )
    monkeypatch.setattr(
        "pc_client.adapters.git_adapter.GitAdapter.add_file",
        mock_add_file,
    )
    monkeypatch.setattr(
        "pc_client.adapters.git_adapter.GitAdapter.commit",
        mock_commit,
    )

    client = make_client(
        tmp_path / "cache.db",
        github_token="fake_token",
        github_owner="mpieniak01",
        github_repo="rider-pc",
    )

    resp = client.post(
        "/api/project/create-task",
        json={
            "title": "Nowa Funkcja Y",
            "body": "Opis zadania testowego",
            "git_strategy": "new_branch",
            "base_branch": "main",
            "auto_init": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["success"] is True
    assert data["issue"]["number"] == 160
    assert "feat/160-" in created_branch["name"]
    # Verify docs file was created
    assert "docs_file" in data
    assert "160_" in data["docs_file"]
    assert len(added_files) == 1
    assert "160_" in added_files[0]
    assert len(committed_messages) == 1
    assert "#160" in committed_messages[0]


def test_create_task_auto_init_disabled(tmp_path, monkeypatch):
    """Test creating a task with auto_init disabled doesn't create docs file."""
    # Reset the singletons
    project_router_module._github_adapter = None
    project_router_module._git_adapter = None

    created_branch = {"name": None}
    added_files = []

    async def mock_create_issue(self, title, body="", assignees=None, labels=None):
        return {
            "success": True,
            "number": 161,
            "url": "https://github.com/mpieniak01/rider-pc/issues/161",
            "title": title,
        }

    async def mock_create_branch_and_checkout(self, name, base="main"):
        created_branch["name"] = name
        return True, ""

    async def mock_is_dirty(self):
        return False

    async def mock_add_file(self, path):
        added_files.append(path)
        return True, ""

    monkeypatch.setattr(
        "pc_client.adapters.github_adapter.GitHubAdapter.create_issue",
        mock_create_issue,
    )
    monkeypatch.setattr(
        "pc_client.adapters.git_adapter.GitAdapter.create_branch_and_checkout",
        mock_create_branch_and_checkout,
    )
    monkeypatch.setattr(
        "pc_client.adapters.git_adapter.GitAdapter.is_dirty",
        mock_is_dirty,
    )
    monkeypatch.setattr(
        "pc_client.adapters.git_adapter.GitAdapter.add_file",
        mock_add_file,
    )

    client = make_client(
        tmp_path / "cache.db",
        github_token="fake_token",
        github_owner="mpieniak01",
        github_repo="rider-pc",
    )

    resp = client.post(
        "/api/project/create-task",
        json={
            "title": "Nowa Funkcja Z",
            "git_strategy": "new_branch",
            "base_branch": "main",
            "auto_init": False,
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["success"] is True
    assert data["issue"]["number"] == 161
    # Docs file should NOT be created
    assert "docs_file" not in data
    assert len(added_files) == 0
