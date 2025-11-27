"""Tests for the /api/status/version endpoint."""

from fastapi.testclient import TestClient

from pc_client.api.server import create_app
from pc_client.cache import CacheManager
from pc_client.config import Settings
import pc_client.api.routers.status_router as status_router_module


def make_client(db_path):
    """Create a test client."""
    settings = Settings()
    cache = CacheManager(db_path=str(db_path))
    app = create_app(settings, cache)
    return TestClient(app)


def test_version_endpoint_returns_version_info(monkeypatch, tmp_path):
    """Test that the version endpoint returns git version info."""
    # Mock the GitAdapter to return controlled data
    mock_version_info = {
        "branch": "main",
        "commit": "abc1234",
        "dirty": False,
        "message": "Test commit",
        "ts": 1716200000,
        "available": True,
    }

    async def mock_get_version_info(self):
        return mock_version_info

    monkeypatch.setattr(
        "pc_client.adapters.git_adapter.GitAdapter.get_version_info",
        mock_get_version_info,
    )

    # Reset the singleton by setting the module-level variable
    status_router_module._git_adapter = None

    client = make_client(tmp_path / "cache.db")

    resp = client.get("/api/status/version")
    assert resp.status_code == 200
    data = resp.json()
    assert data["branch"] == "main"
    assert data["commit"] == "abc1234"
    assert data["dirty"] is False
    assert data["message"] == "Test commit"
    assert data["available"] is True


def test_version_endpoint_dirty_repo(monkeypatch, tmp_path):
    """Test that the version endpoint returns dirty status correctly."""
    mock_version_info = {
        "branch": "feature/test",
        "commit": "def5678",
        "dirty": True,
        "message": "Work in progress",
        "ts": 1716200000,
        "available": True,
    }

    async def mock_get_version_info(self):
        return mock_version_info

    monkeypatch.setattr(
        "pc_client.adapters.git_adapter.GitAdapter.get_version_info",
        mock_get_version_info,
    )

    # Reset the singleton
    status_router_module._git_adapter = None

    client = make_client(tmp_path / "cache.db")

    resp = client.get("/api/status/version")
    assert resp.status_code == 200
    data = resp.json()
    assert data["branch"] == "feature/test"
    assert data["dirty"] is True


def test_version_endpoint_git_unavailable(monkeypatch, tmp_path):
    """Test that the version endpoint handles git unavailability."""
    mock_version_info = {
        "branch": "unknown",
        "commit": "unknown",
        "dirty": False,
        "message": "",
        "ts": 1716200000,
        "available": False,
    }

    async def mock_get_version_info(self):
        return mock_version_info

    monkeypatch.setattr(
        "pc_client.adapters.git_adapter.GitAdapter.get_version_info",
        mock_get_version_info,
    )

    # Reset the singleton
    status_router_module._git_adapter = None

    client = make_client(tmp_path / "cache.db")

    resp = client.get("/api/status/version")
    assert resp.status_code == 200
    data = resp.json()
    assert data["branch"] == "unknown"
    assert data["commit"] == "unknown"
    assert data["available"] is False
