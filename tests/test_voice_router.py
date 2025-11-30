"""Tests for voice router endpoints.

Testy obejmują:
- /api/voice/asr (speech-to-text)
- /api/providers/voice (status providera)
"""

import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from pc_client.api.routers import voice_router
from pc_client.providers import VoiceProvider
from pc_client.providers.base import TaskResult, TaskStatus


@pytest.fixture
def app():
    """Create test FastAPI app with voice router."""
    test_app = FastAPI()
    test_app.include_router(voice_router.router)

    # Initialize state
    test_app.state.providers = {}
    test_app.state.rest_adapter = None
    test_app.state.services = []
    test_app.state.settings = MagicMock()
    test_app.state.settings.voice_model = "en_US-lessac-medium"
    test_app.state.voice_asr_priority = 5
    test_app.state.voice_tts_priority = 6

    return test_app


@pytest.fixture
def mock_voice_provider():
    """Create mock VoiceProvider."""
    provider = MagicMock(spec=VoiceProvider)
    provider.get_telemetry.return_value = {
        "initialized": True,
        "asr_model": "base",
        "tts_model": "en_US-lessac-medium",
        "sample_rate": 16000,
        "asr_available": True,
        "tts_available": True,
        "mode": "mock",
    }

    # Mock process_task for ASR
    async def mock_process_task(task):
        if task.task_type.value == "voice.asr":
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.COMPLETED,
                result={
                    "text": "Mock transcription result",
                    "confidence": 0.95,
                    "language": "en",
                },
                meta={"model": "mock", "engine": "mock"},
            )
        elif task.task_type.value == "voice.tts":
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.COMPLETED,
                result={
                    "audio_data": "bW9jayBhdWRpbyBkYXRh",  # base64 "mock audio data"
                    "format": "wav",
                    "sample_rate": 16000,
                    "duration_ms": 1000,
                },
                meta={"model": "mock", "engine": "mock"},
            )
        return TaskResult(
            task_id=task.task_id,
            status=TaskStatus.FAILED,
            error="Unknown task type",
        )

    provider.process_task = mock_process_task
    return provider


class TestVoiceAsrEndpoint:
    """Tests for /api/voice/asr endpoint."""

    @pytest.mark.asyncio
    async def test_voice_asr_without_provider(self, app):
        """Test ASR without provider returns 503."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/voice/asr", json={"audio_data": "dGVzdCBhdWRpbyBkYXRh"})
            assert response.status_code == 503
            data = response.json()
            assert data["ok"] is False
            assert "unavailable" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_voice_asr_missing_audio_data(self, app, mock_voice_provider):
        """Test ASR with missing audio data returns 400."""
        app.state.providers["voice"] = mock_voice_provider

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/voice/asr", json={})
            assert response.status_code == 400
            data = response.json()
            assert data["ok"] is False
            assert "audio" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_voice_asr_with_provider(self, app, mock_voice_provider):
        """Test ASR works with provider."""
        app.state.providers["voice"] = mock_voice_provider

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/voice/asr",
                json={
                    "audio_data": "dGVzdCBhdWRpbyBkYXRh",  # base64 "test audio data"
                    "format": "wav",
                    "sample_rate": 16000,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert "text" in data
            assert data["source"] == "pc"
            assert "latency_ms" in data


class TestProvidersVoiceEndpoint:
    """Tests for /api/providers/voice endpoint."""

    @pytest.mark.asyncio
    async def test_providers_voice_no_provider(self, app):
        """Test status endpoint without provider returns not_configured."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/providers/voice")
            assert response.status_code == 200
            data = response.json()
            assert data["initialized"] is False
            assert data["status"] == "not_configured"

    @pytest.mark.asyncio
    async def test_providers_voice_with_provider(self, app, mock_voice_provider):
        """Test status endpoint returns provider info."""
        app.state.providers["voice"] = mock_voice_provider

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/providers/voice")
            assert response.status_code == 200
            data = response.json()
            assert data["initialized"] is True
            assert data["status"] == "ready"
            assert data["asr_model"] == "base"
            assert data["tts_model"] == "en_US-lessac-medium"
            assert data["asr_available"] is True
            assert data["tts_available"] is True
