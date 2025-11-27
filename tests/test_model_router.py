"""Tests for model_router.py API endpoints."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pc_client.api.routers.model_router import router, _fetch_remote_models, _switch_provider_mode
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


class TestFetchRemoteModels:
    """Tests for _fetch_remote_models helper function."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_adapter(self):
        """Test returns empty list when rest_adapter is not available."""
        mock_request = MagicMock()
        mock_request.app.state = MagicMock(spec=[])  # No rest_adapter attribute

        result = await _fetch_remote_models(mock_request)

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_adapter_is_none(self):
        """Test returns empty list when rest_adapter is None."""
        mock_request = MagicMock()
        mock_request.app.state.rest_adapter = None

        result = await _fetch_remote_models(mock_request)

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_models_from_models_key(self):
        """Test returns models from 'models' key in response."""
        mock_adapter = MagicMock()
        mock_adapter.get_remote_models = AsyncMock(
            return_value={"models": [{"name": "yolov8n", "category": "vision"}]}
        )
        mock_request = MagicMock()
        mock_request.app.state.rest_adapter = mock_adapter

        result = await _fetch_remote_models(mock_request)

        assert len(result) == 1
        assert result[0]["name"] == "yolov8n"

    @pytest.mark.asyncio
    async def test_returns_models_from_local_key_for_backward_compat(self):
        """Test returns models from 'local' key for backward compatibility."""
        mock_adapter = MagicMock()
        mock_adapter.get_remote_models = AsyncMock(
            return_value={"local": [{"name": "whisper-base", "category": "voice_asr"}]}
        )
        mock_request = MagicMock()
        mock_request.app.state.rest_adapter = mock_adapter

        result = await _fetch_remote_models(mock_request)

        assert len(result) == 1
        assert result[0]["name"] == "whisper-base"

    @pytest.mark.asyncio
    async def test_prefers_models_key_over_local(self):
        """Test prefers 'models' key over 'local' when both present."""
        mock_adapter = MagicMock()
        mock_adapter.get_remote_models = AsyncMock(
            return_value={
                "models": [{"name": "new-format"}],
                "local": [{"name": "old-format"}],
            }
        )
        mock_request = MagicMock()
        mock_request.app.state.rest_adapter = mock_adapter

        result = await _fetch_remote_models(mock_request)

        assert len(result) == 1
        assert result[0]["name"] == "new-format"

    @pytest.mark.asyncio
    async def test_returns_empty_on_network_error(self):
        """Test returns empty list when network error occurs."""
        mock_adapter = MagicMock()
        mock_adapter.get_remote_models = AsyncMock(
            side_effect=ConnectionError("Network unreachable")
        )
        mock_request = MagicMock()
        mock_request.app.state.rest_adapter = mock_adapter

        result = await _fetch_remote_models(mock_request)

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_invalid_payload(self):
        """Test returns empty list when payload is not a dict."""
        mock_adapter = MagicMock()
        mock_adapter.get_remote_models = AsyncMock(return_value="invalid")
        mock_request = MagicMock()
        mock_request.app.state.rest_adapter = mock_adapter

        result = await _fetch_remote_models(mock_request)

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_missing_keys(self):
        """Test returns empty list when neither models nor local keys present."""
        mock_adapter = MagicMock()
        mock_adapter.get_remote_models = AsyncMock(return_value={"other": []})
        mock_request = MagicMock()
        mock_request.app.state.rest_adapter = mock_adapter

        result = await _fetch_remote_models(mock_request)

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_models_not_list(self):
        """Test returns empty list when models value is not a list."""
        mock_adapter = MagicMock()
        mock_adapter.get_remote_models = AsyncMock(
            return_value={"models": "not-a-list"}
        )
        mock_request = MagicMock()
        mock_request.app.state.rest_adapter = mock_adapter

        result = await _fetch_remote_models(mock_request)

        assert result == []


class TestSwitchProviderMode:
    """Tests for _switch_provider_mode helper function."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_adapter(self):
        """Test returns None when rest_adapter is not available."""
        mock_request = MagicMock()
        mock_request.app.state = MagicMock(spec=[])  # No rest_adapter attribute

        result = await _switch_provider_mode(mock_request, "vision", "pc")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_adapter_is_none(self):
        """Test returns None when rest_adapter is None."""
        mock_request = MagicMock()
        mock_request.app.state.rest_adapter = None

        result = await _switch_provider_mode(mock_request, "vision", "pc")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_invalid_slot(self):
        """Test returns None for unknown slot."""
        mock_adapter = MagicMock()
        mock_request = MagicMock()
        mock_request.app.state.rest_adapter = mock_adapter

        result = await _switch_provider_mode(mock_request, "invalid_slot", "pc")

        assert result is None
        mock_adapter.patch_provider.assert_not_called()

    @pytest.mark.asyncio
    async def test_maps_vision_slot_to_vision_domain(self):
        """Test vision slot maps to vision domain."""
        mock_adapter = MagicMock()
        mock_adapter.patch_provider = AsyncMock(return_value={"success": True})
        mock_request = MagicMock()
        mock_request.app.state.rest_adapter = mock_adapter

        result = await _switch_provider_mode(mock_request, "vision", "pc")

        mock_adapter.patch_provider.assert_called_once_with(
            "vision", {"target": "pc", "reason": "models_ui"}
        )
        assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_maps_voice_asr_slot_to_voice_domain(self):
        """Test voice_asr slot maps to voice domain."""
        mock_adapter = MagicMock()
        mock_adapter.patch_provider = AsyncMock(return_value={"success": True})
        mock_request = MagicMock()
        mock_request.app.state.rest_adapter = mock_adapter

        result = await _switch_provider_mode(mock_request, "voice_asr", "local")

        mock_adapter.patch_provider.assert_called_once_with(
            "voice", {"target": "local", "reason": "models_ui"}
        )

    @pytest.mark.asyncio
    async def test_maps_voice_tts_slot_to_voice_domain(self):
        """Test voice_tts slot maps to voice domain."""
        mock_adapter = MagicMock()
        mock_adapter.patch_provider = AsyncMock(return_value={"success": True})
        mock_request = MagicMock()
        mock_request.app.state.rest_adapter = mock_adapter

        result = await _switch_provider_mode(mock_request, "voice_tts", "pc")

        mock_adapter.patch_provider.assert_called_once_with(
            "voice", {"target": "pc", "reason": "models_ui"}
        )

    @pytest.mark.asyncio
    async def test_maps_text_slot_to_text_domain(self):
        """Test text slot maps to text domain."""
        mock_adapter = MagicMock()
        mock_adapter.patch_provider = AsyncMock(return_value={"success": True})
        mock_request = MagicMock()
        mock_request.app.state.rest_adapter = mock_adapter

        result = await _switch_provider_mode(mock_request, "text", "pc")

        mock_adapter.patch_provider.assert_called_once_with(
            "text", {"target": "pc", "reason": "models_ui"}
        )

    @pytest.mark.asyncio
    async def test_returns_error_on_network_failure(self):
        """Test returns error dict when network failure occurs."""
        mock_adapter = MagicMock()
        mock_adapter.patch_provider = AsyncMock(
            side_effect=ConnectionError("Rider-PI offline")
        )
        mock_request = MagicMock()
        mock_request.app.state.rest_adapter = mock_adapter

        result = await _switch_provider_mode(mock_request, "vision", "pc")

        assert result is not None
        assert "error" in result
        assert "Rider-PI offline" in result["error"]
