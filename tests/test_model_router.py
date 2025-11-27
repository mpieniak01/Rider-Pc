"""Tests for model_router.py API endpoints."""

import pytest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pc_client.api.routers.model_router import router
from pc_client.core.model_manager import ModelManager, ActiveModels


@pytest.fixture
def app():
    """Create test FastAPI app."""
    app = FastAPI()
    app.include_router(router)
    app.state.model_manager = None
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestGetInstalledModels:
    """Tests for GET /api/models/installed endpoint."""

    def test_returns_empty_when_no_models(self, client, tmp_path):
        """Test endpoint returns empty lists when no models found."""
        with patch.object(ModelManager, "scan_local_models", return_value=[]):
            with patch.object(ModelManager, "scan_ollama_models", return_value=[]):
                response = client.get("/api/models/installed")

        assert response.status_code == 200
        data = response.json()
        assert data["total_local"] == 0
        assert data["total_ollama"] == 0
        assert data["local"] == []
        assert data["total_remote"] == 0
        assert data["remote"] == []
        assert data["ollama"] == []

    def test_returns_local_models(self, client, tmp_path):
        """Test endpoint returns detected local models."""
        mock_models = [
            {
                "name": "yolov8n",
                "path": "yolov8n.pt",
                "type": "yolo",
                "category": "vision",
                "size_mb": 12.5,
                "format": "pt",
            }
        ]

        with patch.object(ModelManager, "scan_local_models", return_value=[]):
            with patch.object(ModelManager, "get_installed_models", return_value=mock_models):
                with patch.object(ModelManager, "scan_ollama_models", return_value=[]):
                    with patch.object(ModelManager, "get_ollama_models", return_value=[]):
                        response = client.get("/api/models/installed")

        assert response.status_code == 200
        data = response.json()
        assert data["total_local"] == 1
        assert data["local"][0]["name"] == "yolov8n"


class TestGetActiveModels:
    """Tests for GET /api/models/active endpoint."""

    def test_returns_active_models(self, client):
        """Test endpoint returns active model configuration."""
        mock_active = ActiveModels(
            vision={"model": "yolov8n", "enabled": True, "provider": "yolo"},
            text={"model": "llama3.2:1b", "enabled": True, "provider": "ollama"},
        )

        with patch.object(ModelManager, "get_active_models", return_value=mock_active):
            response = client.get("/api/models/active")

        assert response.status_code == 200
        data = response.json()
        assert data["vision"]["model"] == "yolov8n"
        assert data["text"]["model"] == "llama3.2:1b"


class TestBindModel:
    """Tests for POST /api/models/bind endpoint."""

    def test_bind_model_success(self, client):
        """Test successful model binding."""
        mock_active = ActiveModels()

        with patch.object(ModelManager, "get_active_models", return_value=mock_active):
            with patch.object(ModelManager, "persist_active_model", return_value=None):
                response = client.post(
                    "/api/models/bind",
                    json={"slot": "text", "provider": "ollama", "model": "llama3.2:1b"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["slot"] == "text"
        assert data["provider"] == "ollama"
        assert data["model"] == "llama3.2:1b"

    def test_bind_model_invalid_slot(self, client):
        """Test binding with invalid slot returns error."""
        response = client.post(
            "/api/models/bind",
            json={"slot": "invalid", "provider": "ollama", "model": "test"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    def test_bind_model_missing_provider(self, client):
        """Test binding without provider returns error."""
        response = client.post(
            "/api/models/bind",
            json={"slot": "text", "model": "test"},
        )

        # Pydantic validation returns 422 for missing required fields
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_bind_model_missing_model(self, client):
        """Test binding without model returns error."""
        response = client.post(
            "/api/models/bind",
            json={"slot": "text", "provider": "ollama"},
        )

        # Pydantic validation returns 422 for missing required fields
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data


class TestGetModelsSummary:
    """Tests for GET /api/models/summary endpoint."""

    def test_returns_full_summary(self, client):
        """Test endpoint returns complete model summary."""
        mock_active = ActiveModels(
            vision={"model": "yolov8n", "enabled": True},
        )
        mock_installed = [
            {
                "name": "test",
                "type": "unknown",
                "category": "unknown",
                "path": "test.pt",
                "size_mb": 1.0,
                "format": "pt",
            }
        ]
        mock_ollama = [{"name": "llama3.2:1b"}]

        with patch.object(ModelManager, "scan_local_models", return_value=[]):
            with patch.object(ModelManager, "scan_ollama_models", return_value=[]):
                with patch.object(ModelManager, "get_active_models", return_value=mock_active):
                    with patch.object(ModelManager, "get_installed_models", return_value=mock_installed):
                        with patch.object(ModelManager, "get_ollama_models", return_value=mock_ollama):
                            with patch.object(
                                ModelManager,
                                "get_all_models",
                                return_value={
                                    "installed": mock_installed,
                                    "ollama": mock_ollama,
                                    "active": mock_active.to_dict(),
                                },
                            ):
                                response = client.get("/api/models/summary")

        assert response.status_code == 200
        data = response.json()
        assert "installed" in data
        assert "ollama" in data
        assert "active" in data
        assert "remote" in data
