"""Tests for chat router endpoints.

Testy obejmują:
- /api/chat/send z różnymi trybami (pc, proxy, auto)
- /api/chat/pc/send (wymuszony tryb lokalny)
- /api/providers/text (status providera)
- /api/chat/pc/generate-pr-content (generowanie treści PR)
"""

import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from pc_client.api.routers import chat_router
from pc_client.providers import TextProvider
from pc_client.providers.base import TaskResult, TaskStatus


@pytest.fixture
def app():
    """Create test FastAPI app with chat router."""
    test_app = FastAPI()
    test_app.include_router(chat_router.router)

    # Initialize state
    test_app.state.text_provider = None
    test_app.state.rest_adapter = None

    return test_app


@pytest.fixture
def mock_text_provider():
    """Create mock TextProvider."""
    provider = MagicMock(spec=TextProvider)
    provider.get_telemetry.return_value = {
        "initialized": True,
        "model": "llama3.2:1b",
        "ollama_available": False,
        "mode": "mock",
        "cache_size": 0,
        "max_tokens": 512,
        "temperature": 0.7,
        "use_cache": True,
    }

    # Mock process_task to return success
    async def mock_process_task(task):
        return TaskResult(
            task_id=task.task_id,
            status=TaskStatus.COMPLETED,
            result={"text": f"Mock response to: {task.payload.get('prompt', '')[:30]}..."},
            meta={"model": "mock", "engine": "mock"},
        )

    provider.process_task = mock_process_task
    return provider


@pytest.fixture
def mock_rest_adapter():
    """Create mock RestAdapter."""
    adapter = MagicMock()

    async def mock_post_chat_send(payload):
        return {
            "ok": True,
            "reply": f"Proxy response to: {payload.get('msg', '')}",
        }

    adapter.post_chat_send = mock_post_chat_send
    return adapter


class TestChatSendEndpoint:
    """Tests for /api/chat/send endpoint."""

    @pytest.mark.asyncio
    async def test_chat_send_missing_prompt(self, app):
        """Test chat send with missing prompt returns 400."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/chat/send", json={})
            assert response.status_code == 400
            data = response.json()
            assert data["ok"] is False
            assert "missing prompt" in data["error"]

    @pytest.mark.asyncio
    async def test_chat_send_no_provider_no_adapter(self, app):
        """Test chat send without provider or adapter returns 503."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/chat/send", json={"msg": "Hello"})
            assert response.status_code == 503
            data = response.json()
            assert data["ok"] is False
            assert "unavailable" in data["error"]

    @pytest.mark.asyncio
    async def test_chat_send_with_local_provider(self, app, mock_text_provider):
        """Test chat send uses local provider when available."""
        app.state.text_provider = mock_text_provider

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/chat/send", json={"msg": "Hello world"})
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert "reply" in data
            assert data["source"] == "pc"

    @pytest.mark.asyncio
    async def test_chat_send_mode_pc_without_provider(self, app):
        """Test chat send with mode=pc but no provider returns 503."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/chat/send", json={"msg": "Hello", "mode": "pc"})
            assert response.status_code == 503
            data = response.json()
            assert data["ok"] is False
            assert "not available" in data["error"]

    @pytest.mark.asyncio
    async def test_chat_send_mode_proxy(self, app, mock_rest_adapter):
        """Test chat send with mode=proxy uses adapter."""
        app.state.rest_adapter = mock_rest_adapter

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/chat/send", json={"msg": "Hello", "mode": "proxy"})
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert data["source"] == "proxy"

    @pytest.mark.asyncio
    async def test_chat_send_mode_proxy_without_adapter(self, app):
        """Test chat send with mode=proxy but no adapter returns 503."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/chat/send", json={"msg": "Hello", "mode": "proxy"})
            assert response.status_code == 503
            data = response.json()
            assert data["ok"] is False
            assert "adapter not available" in data["error"]

    @pytest.mark.asyncio
    async def test_chat_send_auto_prefers_local(self, app, mock_text_provider, mock_rest_adapter):
        """Test chat send with mode=auto prefers local provider."""
        app.state.text_provider = mock_text_provider
        app.state.rest_adapter = mock_rest_adapter

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/chat/send", json={"msg": "Hello", "mode": "auto"})
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert data["source"] == "pc"

    @pytest.mark.asyncio
    async def test_chat_send_fallback_to_proxy(self, app, mock_rest_adapter):
        """Test chat send falls back to proxy when no local provider."""
        app.state.rest_adapter = mock_rest_adapter

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/chat/send", json={"msg": "Hello"})
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert data["source"] == "proxy"


class TestChatPcSendEndpoint:
    """Tests for /api/chat/pc/send endpoint."""

    @pytest.mark.asyncio
    async def test_chat_pc_send_without_provider(self, app):
        """Test PC-only endpoint without provider returns 503."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/chat/pc/send", json={"msg": "Hello"})
            assert response.status_code == 503
            data = response.json()
            assert data["ok"] is False
            assert "not initialized" in data["error"]

    @pytest.mark.asyncio
    async def test_chat_pc_send_with_provider(self, app, mock_text_provider):
        """Test PC-only endpoint works with provider."""
        app.state.text_provider = mock_text_provider

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/chat/pc/send", json={"msg": "Test message"})
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert "reply" in data
            assert data["source"] == "pc"

    @pytest.mark.asyncio
    async def test_chat_pc_send_missing_prompt(self, app, mock_text_provider):
        """Test PC-only endpoint with missing prompt returns 400."""
        app.state.text_provider = mock_text_provider

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/chat/pc/send", json={})
            assert response.status_code == 400
            data = response.json()
            assert data["ok"] is False
            assert "missing prompt" in data["error"]


class TestProvidersTextEndpoint:
    """Tests for /api/providers/text endpoint."""

    @pytest.mark.asyncio
    async def test_providers_text_no_provider(self, app):
        """Test status endpoint without provider returns not_configured."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/providers/text")
            assert response.status_code == 200
            data = response.json()
            assert data["initialized"] is False
            assert data["status"] == "not_configured"

    @pytest.mark.asyncio
    async def test_providers_text_with_provider(self, app, mock_text_provider):
        """Test status endpoint returns provider info."""
        app.state.text_provider = mock_text_provider

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/providers/text")
            assert response.status_code == 200
            data = response.json()
            assert data["initialized"] is True
            assert data["status"] == "ready"
            assert data["model"] == "llama3.2:1b"
            assert data["engine"] == "mock"


class TestGeneratePrContentEndpoint:
    """Tests for /api/chat/pc/generate-pr-content endpoint."""

    @pytest.mark.asyncio
    async def test_generate_pr_content_without_provider(self, app):
        """Test PR content generation without provider returns 503."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/chat/pc/generate-pr-content", json={"draft": "Test changes"})
            assert response.status_code == 503
            data = response.json()
            assert data["ok"] is False

    @pytest.mark.asyncio
    async def test_generate_pr_content_missing_draft(self, app, mock_text_provider):
        """Test PR content generation with missing draft returns 400."""
        app.state.text_provider = mock_text_provider

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/chat/pc/generate-pr-content", json={})
            assert response.status_code == 400
            data = response.json()
            assert data["ok"] is False
            assert "draft" in data["error"]

    @pytest.mark.asyncio
    async def test_generate_pr_content_success(self, app, mock_text_provider):
        """Test PR content generation with valid draft."""

        # Mock provider to return structured PR content
        async def mock_pr_task(task):
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.COMPLETED,
                result={
                    "text": """TYTUŁ: Dodanie nowej funkcjonalności
OPIS: Ta zmiana dodaje nową funkcjonalność do systemu.
Szczegóły implementacji...
PODSUMOWANIE: Nowa funkcja zwiększająca wydajność."""
                },
                meta={},
            )

        mock_text_provider.process_task = mock_pr_task
        app.state.text_provider = mock_text_provider

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/chat/pc/generate-pr-content",
                json={
                    "draft": "Dodaję nową funkcję do systemu",
                    "context": {
                        "issues": ["#123 - Feature request"],
                        "files_changed": ["src/feature.py", "tests/test_feature.py"],
                    },
                    "style": "detailed",
                    "language": "pl",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert "title" in data
            assert "description" in data
            assert "summary" in data
            assert data["title"] == "Dodanie nowej funkcjonalności"


class TestParsePrContent:
    """Tests for PR content parsing helper function."""

    def test_parse_pr_content_with_all_sections(self):
        """Test parsing PR content with all sections present."""
        from pc_client.api.routers.chat_router import _parse_pr_content

        text = """TYTUŁ: Test PR
OPIS: This is the description.
It has multiple lines.
PODSUMOWANIE: Short summary."""

        result = _parse_pr_content(text, "fallback")
        assert result["title"] == "Test PR"
        assert "This is the description" in result["description"]
        assert result["summary"] == "Short summary."

    def test_parse_pr_content_fallback(self):
        """Test parsing PR content with missing sections uses fallback."""
        from pc_client.api.routers.chat_router import _parse_pr_content

        text = "Just some text without structure."
        result = _parse_pr_content(text, "Fallback title here")

        assert result["title"] == "Fallback title here"
        assert result["description"] == text

    def test_parse_pr_content_english_labels(self):
        """Test parsing PR content with English labels."""
        from pc_client.api.routers.chat_router import _parse_pr_content

        text = """TITLE: English PR Title
DESCRIPTION: English description here.
SUMMARY: English summary."""

        result = _parse_pr_content(text, "fallback")
        assert result["title"] == "English PR Title"
        assert "English description" in result["description"]
        assert result["summary"] == "English summary."


class TestChatMode:
    """Tests for ChatMode enum and parsing."""

    def test_parse_chat_mode_valid(self):
        """Test parsing valid chat modes."""
        from pc_client.api.routers.chat_router import _parse_chat_mode, ChatMode

        assert _parse_chat_mode({"mode": "pc"}) == ChatMode.PC
        assert _parse_chat_mode({"mode": "proxy"}) == ChatMode.PROXY
        assert _parse_chat_mode({"mode": "auto"}) == ChatMode.AUTO

    def test_parse_chat_mode_case_insensitive(self):
        """Test chat mode parsing is case insensitive."""
        from pc_client.api.routers.chat_router import _parse_chat_mode, ChatMode

        assert _parse_chat_mode({"mode": "PC"}) == ChatMode.PC
        assert _parse_chat_mode({"mode": "PROXY"}) == ChatMode.PROXY

    def test_parse_chat_mode_invalid_defaults_to_auto(self):
        """Test invalid mode defaults to auto."""
        from pc_client.api.routers.chat_router import _parse_chat_mode, ChatMode

        assert _parse_chat_mode({"mode": "invalid"}) == ChatMode.AUTO
        assert _parse_chat_mode({}) == ChatMode.AUTO


class TestBenchmarkModelsEndpoint:
    """Tests for /api/benchmark/models endpoint."""

    @pytest.mark.asyncio
    async def test_benchmark_without_provider(self, app):
        """Test benchmark without provider returns 503."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/benchmark/models", json={"prompt": "Test prompt"})
            assert response.status_code == 503
            data = response.json()
            assert data["ok"] is False

    @pytest.mark.asyncio
    async def test_benchmark_missing_prompts(self, app, mock_text_provider):
        """Test benchmark with missing prompts returns 400."""
        app.state.text_provider = mock_text_provider

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/benchmark/models", json={})
            assert response.status_code == 400
            data = response.json()
            assert data["ok"] is False
            assert "prompts" in data["error"] or "prompt" in data["error"]

    @pytest.mark.asyncio
    async def test_benchmark_success_single_prompt(self, app, mock_text_provider):
        """Test benchmark with single prompt succeeds."""
        app.state.text_provider = mock_text_provider

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/benchmark/models", json={"prompt": "Test benchmark prompt", "iterations": 1}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert "results" in data
            assert "summary" in data
            assert data["summary"]["total_prompts"] == 1
            assert data["summary"]["total_iterations"] == 1

    @pytest.mark.asyncio
    async def test_benchmark_success_multiple_prompts(self, app, mock_text_provider):
        """Test benchmark with multiple prompts succeeds."""
        app.state.text_provider = mock_text_provider

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/benchmark/models", json={"prompts": ["Prompt 1", "Prompt 2", "Prompt 3"], "iterations": 2}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert len(data["results"]) == 3
            assert data["summary"]["total_prompts"] == 3
            assert data["summary"]["total_iterations"] == 6


class TestKnowledgeDocumentsEndpoint:
    """Tests for /api/knowledge/documents endpoint."""

    @pytest.mark.asyncio
    async def test_knowledge_documents_returns_list(self, app):
        """Test knowledge documents endpoint returns list."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/knowledge/documents")
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert "documents" in data
            assert "total" in data
            assert isinstance(data["documents"], list)


class TestPreviewPrChangesEndpoint:
    """Tests for /api/chat/pc/preview-pr-changes endpoint."""

    @pytest.mark.asyncio
    async def test_preview_without_provider(self, app):
        """Test preview without provider returns 503."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/chat/pc/preview-pr-changes", json={"draft": "Test draft"})
            assert response.status_code == 503
            data = response.json()
            assert data["ok"] is False

    @pytest.mark.asyncio
    async def test_preview_missing_draft(self, app, mock_text_provider):
        """Test preview with missing draft returns 400."""
        app.state.text_provider = mock_text_provider

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/chat/pc/preview-pr-changes", json={})
            assert response.status_code == 400
            data = response.json()
            assert data["ok"] is False
            assert "draft" in data["error"]

    @pytest.mark.asyncio
    async def test_preview_success(self, app, mock_text_provider):
        """Test preview with valid draft succeeds."""

        # Mock provider to return structured content
        async def mock_preview_task(task):
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.COMPLETED,
                result={
                    "text": """TYTUŁ: Test Preview
OPIS: Preview description here.
PODSUMOWANIE: Short preview summary.
SUGESTIE:
- Add more details
- Include references"""
                },
                meta={},
            )

        mock_text_provider.process_task = mock_preview_task
        app.state.text_provider = mock_text_provider

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/chat/pc/preview-pr-changes",
                json={
                    "draft": "Test draft for preview",
                    "style": "detailed",
                    "language": "pl",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert "preview" in data
            assert "suggestions" in data
            assert data["preview"]["title"] == "Test Preview"


class TestParsePrSuggestions:
    """Tests for PR suggestions parsing helper function."""

    def test_parse_suggestions_with_items(self):
        """Test parsing PR suggestions with items."""
        from pc_client.api.routers.chat_router import _parse_pr_suggestions

        text = """TYTUŁ: Test
OPIS: Description
SUGESTIE:
- First suggestion
- Second suggestion
- Third suggestion"""

        result = _parse_pr_suggestions(text)
        assert len(result) == 3
        assert "First suggestion" in result[0]
        assert "Second suggestion" in result[1]

    def test_parse_suggestions_empty(self):
        """Test parsing PR suggestions when none present."""
        from pc_client.api.routers.chat_router import _parse_pr_suggestions

        text = "Just some text without suggestions."
        result = _parse_pr_suggestions(text)
        assert len(result) == 0

    def test_parse_suggestions_english_label(self):
        """Test parsing PR suggestions with English label."""
        from pc_client.api.routers.chat_router import _parse_pr_suggestions

        text = """TITLE: Test
SUGGESTIONS:
- Suggestion A
* Suggestion B"""

        result = _parse_pr_suggestions(text)
        assert len(result) == 2
