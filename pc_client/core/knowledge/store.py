"""Vector store for the knowledge base.

This module provides a simple vector store implementation using ChromaDB
for storing and searching document embeddings.
"""

import logging
from pathlib import Path
from typing import List, Optional, Any

from pc_client.core.knowledge.ingest import Document

logger = logging.getLogger(__name__)


class VectorStore:
    """Vector store backed by ChromaDB for document storage and retrieval."""

    def __init__(
        self,
        persist_path: str = "data/chroma_db",
        embedding_model: str = "all-MiniLM-L6-v2",
        collection_name: str = "knowledge_base",
    ):
        """Initialize the vector store.

        Args:
            persist_path: Path for persistent storage.
            embedding_model: Name of the sentence-transformers model to use.
            collection_name: Name of the ChromaDB collection.
        """
        self.persist_path = Path(persist_path)
        self.embedding_model = embedding_model
        self.collection_name = collection_name

        self._client: Optional[Any] = None
        self._collection: Optional[Any] = None
        self._embedding_fn: Optional[Any] = None
        self._initialized = False

    @property
    def initialized(self) -> bool:
        """Check if the store is initialized."""
        return self._initialized

    def _ensure_initialized(self) -> bool:
        """Ensure ChromaDB and embedding model are initialized.

        Returns:
            True if initialized successfully, False otherwise.
        """
        if self._initialized:
            return True

        try:
            import chromadb
            from chromadb.utils import embedding_functions

            # Ensure persist directory exists
            self.persist_path.mkdir(parents=True, exist_ok=True)

            # Initialize ChromaDB with persistent storage
            self._client = chromadb.PersistentClient(path=str(self.persist_path))

            # Create embedding function using sentence-transformers
            self._embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=self.embedding_model
            )

            # Get or create collection
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self._embedding_fn,
                metadata={"hnsw:space": "cosine"},
            )

            self._initialized = True
            logger.info(
                "VectorStore initialized with model '%s' at '%s'",
                self.embedding_model,
                self.persist_path,
            )
            return True

        except ImportError as e:
            logger.error("Missing dependency for VectorStore: %s", e)
            return False
        except Exception as e:
            logger.error("Failed to initialize VectorStore: %s", e)
            return False

    def add_documents(self, documents: List[Document]) -> int:
        """Add documents to the vector store.

        Args:
            documents: List of Document objects to add.

        Returns:
            Number of documents added, or -1 on error.
        """
        if not self._ensure_initialized():
            return -1

        if not documents:
            logger.warning("No documents to add")
            return 0

        try:
            # Prepare data for ChromaDB
            ids = [f"doc_{i}" for i in range(len(documents))]
            texts = [doc.content for doc in documents]
            metadatas = [doc.metadata for doc in documents]

            # Clear existing documents before adding new ones
            # ChromaDB requires a where filter; we match all documents with a source field
            self._collection.delete(where={"source": {"$exists": True}})

            self._collection.add(
                ids=ids,
                documents=texts,
                metadatas=metadatas,
            )

            logger.info("Added %d documents to vector store", len(documents))
            return len(documents)

        except Exception as e:
            logger.error("Failed to add documents: %s", e)
            return -1

    def search(self, query: str, k: int = 3) -> List[Document]:
        """Search for documents similar to the query.

        Args:
            query: Search query string.
            k: Number of results to return.

        Returns:
            List of matching Document objects.
        """
        if not self._ensure_initialized():
            return []

        if not query.strip():
            logger.warning("Empty search query")
            return []

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=k,
            )

            documents = []
            if results and results.get("documents"):
                for i, doc_text in enumerate(results["documents"][0]):
                    metadata = {}
                    if results.get("metadatas") and results["metadatas"][0]:
                        metadata = results["metadatas"][0][i] or {}

                    documents.append(Document(content=doc_text, metadata=metadata))

            logger.debug("Search for '%s' returned %d results", query[:50], len(documents))
            return documents

        except Exception as e:
            logger.error("Search failed: %s", e)
            return []

    def count(self) -> int:
        """Get the number of documents in the store.

        Returns:
            Number of documents, or -1 on error.
        """
        if not self._ensure_initialized():
            return -1

        try:
            return self._collection.count()
        except Exception as e:
            logger.error("Failed to count documents: %s", e)
            return -1

    def clear(self) -> bool:
        """Clear all documents from the store.

        Returns:
            True if successful, False otherwise.
        """
        if not self._ensure_initialized():
            return False

        try:
            # Delete the collection and recreate it
            self._client.delete_collection(self.collection_name)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self._embedding_fn,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("Cleared vector store")
            return True
        except Exception as e:
            logger.error("Failed to clear store: %s", e)
            return False
