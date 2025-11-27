"""Tests for the knowledge base module."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import tempfile
import os

from pc_client.core.knowledge.ingest import Document, DocumentLoader, TextSplitter


class TestDocument:
    """Tests for Document dataclass."""

    def test_document_creation(self):
        """Should create a document with content and metadata."""
        doc = Document(content="Test content", metadata={"source": "test.md"})
        assert doc.content == "Test content"
        assert doc.metadata["source"] == "test.md"

    def test_document_source_property(self):
        """Should return source from metadata."""
        doc = Document(content="Test", metadata={"source": "docs/test.md"})
        assert doc.source == "docs/test.md"

    def test_document_source_empty_when_not_set(self):
        """Should return empty string when source not in metadata."""
        doc = Document(content="Test")
        assert doc.source == ""

    def test_document_default_metadata(self):
        """Should have empty dict as default metadata."""
        doc = Document(content="Test")
        assert doc.metadata == {}


class TestDocumentLoader:
    """Tests for DocumentLoader class."""

    def test_load_from_directory_with_md_files(self):
        """Should load all markdown files from directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test markdown files
            (Path(tmpdir) / "test1.md").write_text("# Test 1\nContent 1")
            (Path(tmpdir) / "test2.md").write_text("# Test 2\nContent 2")
            (Path(tmpdir) / "subdir").mkdir()
            (Path(tmpdir) / "subdir" / "test3.md").write_text("# Test 3\nContent 3")
            (Path(tmpdir) / "ignore.txt").write_text("This should be ignored")

            loader = DocumentLoader(paths=["test_dir"], base_dir=tmpdir)
            # Create the test_dir
            (Path(tmpdir) / "test_dir").mkdir()
            (Path(tmpdir) / "test_dir" / "doc.md").write_text("# Doc")

            docs = loader.load()
            assert len(docs) == 1
            assert "doc.md" in docs[0].metadata["filename"]

    def test_load_non_existent_path(self):
        """Should handle non-existent path gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = DocumentLoader(paths=["nonexistent"], base_dir=tmpdir)
            docs = loader.load()
            assert len(docs) == 0

    def test_load_empty_directory(self):
        """Should handle empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "empty").mkdir()
            loader = DocumentLoader(paths=["empty"], base_dir=tmpdir)
            docs = loader.load()
            assert len(docs) == 0

    def test_load_multiple_paths(self):
        """Should load from multiple paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "dir1").mkdir()
            (Path(tmpdir) / "dir2").mkdir()
            (Path(tmpdir) / "dir1" / "a.md").write_text("Content A")
            (Path(tmpdir) / "dir2" / "b.md").write_text("Content B")

            loader = DocumentLoader(paths=["dir1", "dir2"], base_dir=tmpdir)
            docs = loader.load()
            assert len(docs) == 2

    def test_load_sets_metadata(self):
        """Should set source and filename in metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "docs").mkdir()
            (Path(tmpdir) / "docs" / "test.md").write_text("# Test")

            loader = DocumentLoader(paths=["docs"], base_dir=tmpdir)
            docs = loader.load()
            assert len(docs) == 1
            assert docs[0].metadata["source"] == "docs/test.md"
            assert docs[0].metadata["filename"] == "test.md"


class TestTextSplitter:
    """Tests for TextSplitter class."""

    def test_split_short_text(self):
        """Should not split text shorter than chunk size."""
        splitter = TextSplitter(chunk_size=1000, chunk_overlap=100)
        doc = Document(content="Short text", metadata={"source": "test.md"})
        chunks = splitter.split([doc])
        assert len(chunks) == 1
        assert chunks[0].content == "Short text"

    def test_split_long_text(self):
        """Should split long text into chunks."""
        splitter = TextSplitter(chunk_size=50, chunk_overlap=10)
        long_text = "This is a sentence. " * 10  # ~200 chars
        doc = Document(content=long_text, metadata={"source": "test.md"})
        chunks = splitter.split([doc])
        assert len(chunks) > 1

    def test_split_preserves_metadata(self):
        """Should preserve source metadata in chunks."""
        splitter = TextSplitter(chunk_size=50, chunk_overlap=10)
        long_text = "Word " * 50
        doc = Document(content=long_text, metadata={"source": "docs/test.md"})
        chunks = splitter.split([doc])
        for chunk in chunks:
            assert chunk.metadata["source"] == "docs/test.md"

    def test_split_extracts_heading_context(self):
        """Should extract heading context for chunks."""
        splitter = TextSplitter(chunk_size=50, chunk_overlap=10)
        text = "# Main Heading\n\nSome content here. " * 5
        doc = Document(content=text, metadata={"source": "test.md"})
        chunks = splitter.split([doc])
        # At least some chunks should have heading metadata
        headings = [c.metadata.get("heading") for c in chunks if c.metadata.get("heading")]
        assert len(headings) > 0

    def test_split_empty_document(self):
        """Should handle empty document."""
        splitter = TextSplitter(chunk_size=100, chunk_overlap=10)
        doc = Document(content="", metadata={"source": "test.md"})
        chunks = splitter.split([doc])
        # Empty document results in one chunk with empty content
        assert len(chunks) == 1
        assert chunks[0].content == ""

    def test_split_multiple_documents(self):
        """Should split multiple documents."""
        splitter = TextSplitter(chunk_size=100, chunk_overlap=10)
        docs = [
            Document(content="Short doc 1", metadata={"source": "a.md"}),
            Document(content="Short doc 2", metadata={"source": "b.md"}),
        ]
        chunks = splitter.split(docs)
        assert len(chunks) == 2

    def test_split_respects_paragraph_boundaries(self):
        """Should prefer splitting at paragraph boundaries."""
        splitter = TextSplitter(chunk_size=100, chunk_overlap=10)
        text = "First paragraph.\n\nSecond paragraph that is a bit longer to force splitting."
        doc = Document(content=text, metadata={"source": "test.md"})
        chunks = splitter.split([doc])
        # Should prefer paragraph break if within reasonable range
        assert len(chunks) >= 1

    def test_extract_heading_context_with_multiple_levels(self):
        """Should extract most recent heading."""
        splitter = TextSplitter(chunk_size=100, chunk_overlap=10)
        text = "# H1\n## H2\n### H3\nContent here"
        heading = splitter._extract_heading_context(text, len(text) - 5)
        assert heading == "H3"

    def test_extract_heading_context_empty(self):
        """Should return empty string when no headings."""
        splitter = TextSplitter(chunk_size=100, chunk_overlap=10)
        text = "No headings here"
        heading = splitter._extract_heading_context(text, len(text) - 5)
        assert heading == ""


class TestVectorStoreMock:
    """Tests for VectorStore with mocked dependencies."""

    def test_vector_store_init(self):
        """Should initialize with default parameters."""
        from pc_client.core.knowledge.store import VectorStore

        store = VectorStore()
        assert store.persist_path == Path("data/chroma_db")
        assert store.embedding_model == "all-MiniLM-L6-v2"
        assert store.collection_name == "knowledge_base"
        assert not store.initialized

    def test_vector_store_custom_params(self):
        """Should accept custom parameters."""
        from pc_client.core.knowledge.store import VectorStore

        store = VectorStore(
            persist_path="/tmp/test_db",
            embedding_model="custom-model",
            collection_name="test_collection",
        )
        assert store.persist_path == Path("/tmp/test_db")
        assert store.embedding_model == "custom-model"
        assert store.collection_name == "test_collection"

    def test_search_without_init_returns_empty(self):
        """Should return empty list when not initialized."""
        from pc_client.core.knowledge.store import VectorStore

        store = VectorStore()
        # Without calling _ensure_initialized, it should return empty
        # Store is not initialized, so search should return empty list
        with patch.object(store, '_ensure_initialized', return_value=False):
            results = store.search("test query")
            assert results == []

    def test_add_documents_without_init_returns_error(self):
        """Should return -1 when not initialized."""
        from pc_client.core.knowledge.store import VectorStore

        store = VectorStore()
        with patch.object(store, '_ensure_initialized', return_value=False):
            result = store.add_documents([Document(content="test")])
            assert result == -1

    def test_count_without_init_returns_error(self):
        """Should return -1 when not initialized."""
        from pc_client.core.knowledge.store import VectorStore

        store = VectorStore()
        with patch.object(store, '_ensure_initialized', return_value=False):
            count = store.count()
            assert count == -1


class TestKnowledgeRouterMock:
    """Tests for knowledge router endpoints with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_status_when_rag_disabled(self):
        """Should return disabled status when RAG is not enabled."""
        import json
        with patch("pc_client.api.routers.knowledge_router.settings") as mock_settings:
            mock_settings.rag_enabled = False

            from pc_client.api.routers.knowledge_router import knowledge_base_status

            response = await knowledge_base_status()
            data = json.loads(response.body.decode())
            assert data["enabled"] is False

    @pytest.mark.asyncio
    async def test_search_when_rag_disabled(self):
        """Should return error when RAG is not enabled."""
        with patch("pc_client.api.routers.knowledge_router.settings") as mock_settings:
            mock_settings.rag_enabled = False

            from pc_client.api.routers.knowledge_router import search_knowledge_base

            response = await search_knowledge_base(q="test")
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_search_empty_query(self):
        """Should return error for empty query."""
        with patch("pc_client.api.routers.knowledge_router.settings") as mock_settings:
            mock_settings.rag_enabled = True

            from pc_client.api.routers.knowledge_router import search_knowledge_base

            response = await search_knowledge_base(q="")
            assert response.status_code == 400
            data = response.body.decode()
            assert "required" in data.lower()

    @pytest.mark.asyncio
    async def test_reindex_when_rag_disabled(self):
        """Should return error when RAG is not enabled."""
        with patch("pc_client.api.routers.knowledge_router.settings") as mock_settings:
            mock_settings.rag_enabled = False

            from pc_client.api.routers.knowledge_router import reindex_knowledge_base
            from fastapi import BackgroundTasks

            bg = BackgroundTasks()
            response = await reindex_knowledge_base(bg, blocking=True)
            assert response.status_code == 400
