"""Tests for the /api/project/issues endpoint."""

from fastapi.testclient import TestClient

from pc_client.api.server import create_app
from pc_client.cache import CacheManager
from pc_client.config import Settings
import pc_client.api.routers.project_router as project_router_module


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
