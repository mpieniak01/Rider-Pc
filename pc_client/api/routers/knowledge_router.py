"""Knowledge base API endpoints for RAG functionality."""

import asyncio
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse

from pc_client.config.settings import settings
from pc_client.core.knowledge.ingest import DocumentLoader, TextSplitter
from pc_client.core.knowledge.store import VectorStore

logger = logging.getLogger(__name__)

router = APIRouter()

# Maximum query length for search requests
MAX_QUERY_LENGTH = 1000

# Global vector store instance (lazy initialization)
_vector_store: Optional[VectorStore] = None
_reindex_in_progress = False
_reindex_lock = asyncio.Lock()


def _get_vector_store() -> VectorStore:
    """Get or create the global vector store instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore(
            persist_path=settings.rag_persist_path,
            embedding_model=settings.embedding_model,
        )
    return _vector_store


async def _perform_reindex() -> Dict[str, Any]:
    """Perform the reindexing operation.

    Returns:
        Dictionary with indexing results.
    """
    global _reindex_in_progress

    async with _reindex_lock:
        if _reindex_in_progress:
            return {"ok": False, "error": "Reindexing already in progress"}
        _reindex_in_progress = True

    try:
        # Parse document paths from settings
        docs_paths = [p.strip() for p in settings.rag_docs_paths.split(",") if p.strip()]

        # Load documents
        loader = DocumentLoader(paths=docs_paths)
        documents = await asyncio.to_thread(loader.load)

        if not documents:
            return {
                "ok": False,
                "error": "No documents found",
                "paths_checked": docs_paths,
            }

        # Split into chunks
        splitter = TextSplitter(
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
        )
        chunks = await asyncio.to_thread(splitter.split, documents)

        # Clear and add to vector store
        store = _get_vector_store()
        await asyncio.to_thread(store.clear)
        count = await asyncio.to_thread(store.add_documents, chunks)

        if count < 0:
            return {
                "ok": False,
                "error": "Failed to add documents to vector store",
            }

        return {
            "ok": True,
            "documents_loaded": len(documents),
            "chunks_created": len(chunks),
            "chunks_indexed": count,
            "paths": docs_paths,
        }

    except Exception as e:
        logger.exception("Reindexing failed")
        return {"ok": False, "error": str(e)}

    finally:
        _reindex_in_progress = False


async def _reindex_background_task():
    """Background task wrapper for reindexing."""
    result = await _perform_reindex()
    logger.info("Background reindex completed: %s", result)


@router.post("/api/knowledge/reindex")
async def reindex_knowledge_base(
    background_tasks: BackgroundTasks,
    blocking: bool = False,
) -> JSONResponse:
    """Reindex the knowledge base from documentation files.

    Args:
        background_tasks: FastAPI background tasks handler.
        blocking: If True, wait for indexing to complete. Default is False (async).

    Returns:
        JSON response with indexing status.
    """
    if not settings.rag_enabled:
        return JSONResponse(
            {"ok": False, "error": "RAG is not enabled. Set RAG_ENABLED=true."},
            status_code=400,
        )

    global _reindex_in_progress
    if _reindex_in_progress:
        return JSONResponse(
            {"ok": False, "error": "Reindexing already in progress"},
            status_code=409,
        )

    if blocking:
        # Synchronous reindexing
        result = await _perform_reindex()
        status_code = 200 if result.get("ok") else 500
        return JSONResponse(result, status_code=status_code)
    else:
        # Async reindexing in background
        background_tasks.add_task(_reindex_background_task)
        return JSONResponse(
            {
                "ok": True,
                "message": "Reindexing started in background",
            }
        )


@router.get("/api/knowledge/search")
async def search_knowledge_base(
    q: str,
    k: int = 3,
) -> JSONResponse:
    """Search the knowledge base.

    Args:
        q: Search query.
        k: Number of results to return (default: 3).

    Returns:
        JSON response with search results.
    """
    if not settings.rag_enabled:
        return JSONResponse(
            {"ok": False, "error": "RAG is not enabled. Set RAG_ENABLED=true."},
            status_code=400,
        )

    if not q.strip():
        return JSONResponse(
            {"ok": False, "error": "Query parameter 'q' is required"},
            status_code=400,
        )

    if len(q) > MAX_QUERY_LENGTH:
        return JSONResponse(
            {"ok": False, "error": f"Query too long (max {MAX_QUERY_LENGTH} characters)"},
            status_code=400,
        )

    # Limit k to reasonable bounds
    k = max(1, min(k, 10))

    try:
        store = _get_vector_store()
        results = await asyncio.to_thread(store.search, q, k)

        return JSONResponse(
            {
                "ok": True,
                "query": q,
                "count": len(results),
                "results": [
                    {
                        "content": doc.content,
                        "source": doc.metadata.get("source", ""),
                        "heading": doc.metadata.get("heading", ""),
                    }
                    for doc in results
                ],
            }
        )

    except Exception as e:
        logger.exception("Search failed")
        return JSONResponse(
            {"ok": False, "error": str(e)},
            status_code=500,
        )


@router.get("/api/knowledge/status")
async def knowledge_base_status() -> JSONResponse:
    """Get the status of the knowledge base.

    Returns:
        JSON response with knowledge base status.
    """
    if not settings.rag_enabled:
        return JSONResponse(
            {
                "ok": True,
                "enabled": False,
                "message": "RAG is not enabled",
            }
        )

    try:
        store = _get_vector_store()
        count = await asyncio.to_thread(store.count)

        return JSONResponse(
            {
                "ok": True,
                "enabled": True,
                "initialized": store.initialized,
                "document_count": count,
                "embedding_model": settings.embedding_model,
                "persist_path": settings.rag_persist_path,
                "reindex_in_progress": _reindex_in_progress,
            }
        )

    except Exception as e:
        logger.exception("Status check failed")
        return JSONResponse(
            {"ok": False, "error": str(e)},
            status_code=500,
        )
