"""Document ingestion for the knowledge base.

This module provides utilities for loading and processing Markdown documents
for use in the RAG (Retrieval-Augmented Generation) system.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """A chunk of text with metadata."""

    content: str
    metadata: dict = field(default_factory=dict)

    @property
    def source(self) -> str:
        """Get the source file path."""
        return self.metadata.get("source", "")


class DocumentLoader:
    """Recursively loads Markdown files from a directory."""

    def __init__(self, paths: List[str], base_dir: Optional[str] = None):
        """Initialize the document loader.

        Args:
            paths: List of directory paths to load documents from.
            base_dir: Base directory for relative paths. Defaults to current directory.
        """
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()
        self.paths = [self.base_dir / p for p in paths]

    def load(self) -> List[Document]:
        """Load all Markdown files from the configured paths.

        Returns:
            List of Document objects with full file content.
        """
        documents: List[Document] = []

        for path in self.paths:
            if not path.exists():
                logger.warning("Path does not exist: %s", path)
                continue

            if not path.is_dir():
                logger.warning("Path is not a directory: %s", path)
                continue

            for md_file in path.rglob("*.md"):
                try:
                    content = md_file.read_text(encoding="utf-8")
                    relative_path = md_file.relative_to(self.base_dir)
                    documents.append(
                        Document(
                            content=content,
                            metadata={
                                "source": relative_path.as_posix(),
                                "filename": md_file.name,
                            },
                        )
                    )
                    logger.debug("Loaded document: %s", relative_path)
                except Exception as e:
                    logger.error("Failed to load %s: %s", md_file, e)

        logger.info("Loaded %d documents from %d paths", len(documents), len(self.paths))
        return documents


class TextSplitter:
    """Splits text into chunks while preserving Markdown structure."""

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 100):
        """Initialize the text splitter.

        Args:
            chunk_size: Target size for each chunk in characters.
            chunk_overlap: Number of characters to overlap between chunks.

        Raises:
            ValueError: If chunk_overlap >= chunk_size or values are invalid.
        """
        if chunk_size <= 0 or chunk_overlap < 0:
            raise ValueError("chunk_size must be positive and chunk_overlap must be non-negative")
        if chunk_overlap >= chunk_size:
            raise ValueError(f"chunk_overlap ({chunk_overlap}) must be less than chunk_size ({chunk_size})")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def _extract_heading_context(self, text: str, position: int) -> str:
        """Extract the most recent heading before the given position.

        Args:
            text: Full document text.
            position: Position in the text.

        Returns:
            Most recent heading text, or empty string if none found.
        """
        heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
        headings = []

        for match in heading_pattern.finditer(text):
            if match.start() <= position:
                level = len(match.group(1))
                heading_text = match.group(2).strip()
                headings.append((level, heading_text, match.start()))
            else:
                break

        if not headings:
            return ""

        # Return the most recent heading
        return headings[-1][1]

    def split(self, documents: List[Document]) -> List[Document]:
        """Split documents into smaller chunks.

        Args:
            documents: List of documents to split.

        Returns:
            List of chunked documents with preserved metadata.
        """
        chunks: List[Document] = []

        for doc in documents:
            doc_chunks = self._split_text(doc.content, doc.metadata)
            chunks.extend(doc_chunks)

        logger.info("Split %d documents into %d chunks", len(documents), len(chunks))
        return chunks

    def _split_text(self, text: str, metadata: dict) -> List[Document]:
        """Split a single text into chunks.

        Args:
            text: Text to split.
            metadata: Metadata to attach to each chunk.

        Returns:
            List of Document chunks.
        """
        if len(text) <= self.chunk_size:
            return [Document(content=text, metadata=metadata.copy())]

        chunks: List[Document] = []
        current_pos = 0

        while current_pos < len(text):
            # Calculate chunk end position
            chunk_end = min(current_pos + self.chunk_size, len(text))

            # Try to find a good break point (paragraph, sentence, or word boundary)
            if chunk_end < len(text):
                chunk_end = self._find_break_point(text, current_pos, chunk_end)

            chunk_text = text[current_pos:chunk_end].strip()

            if chunk_text:
                # Get heading context for this chunk
                heading = self._extract_heading_context(text, current_pos)
                chunk_metadata = metadata.copy()
                if heading:
                    chunk_metadata["heading"] = heading

                chunks.append(Document(content=chunk_text, metadata=chunk_metadata))

            # Move position forward, accounting for overlap
            current_pos = max(chunk_end - self.chunk_overlap, current_pos + 1)

            # Ensure we don't get stuck in infinite loop
            if current_pos >= len(text):
                break

        return chunks

    def _find_break_point(self, text: str, start: int, end: int) -> int:
        """Find a suitable break point in the text.

        Prefers breaks at paragraph boundaries, then sentence endings,
        then word boundaries.

        Args:
            text: Full text.
            start: Start position of chunk.
            end: Proposed end position.

        Returns:
            Adjusted end position at a suitable break point.
        """
        # Look for paragraph break (double newline)
        para_break = text.rfind("\n\n", start, end)
        if para_break > start + (end - start) // 2:
            return para_break + 2

        # Look for sentence break
        for punct in [". ", "! ", "? ", ".\n", "!\n", "?\n"]:
            sentence_break = text.rfind(punct, start, end)
            if sentence_break > start + (end - start) // 2:
                return sentence_break + len(punct)

        # Look for word break (space or newline)
        space_break = text.rfind(" ", start, end)
        if space_break > start:
            return space_break + 1

        newline_break = text.rfind("\n", start, end)
        if newline_break > start:
            return newline_break + 1

        return end
