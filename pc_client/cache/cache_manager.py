"""Cache manager using SQLite for data storage."""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages caching of data from Rider-PI in SQLite."""

    def __init__(self, db_path: str = "data/cache.db", ttl_seconds: int = 30):
        """
        Initialize the cache manager.

        Args:
            db_path: Path to the SQLite database file
            ttl_seconds: Time-to-live for cached data in seconds
        """
        self.db_path = db_path
        self.ttl_seconds = ttl_seconds

        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    ttl INTEGER NOT NULL
                )
            """)
            # Create index on timestamp for cleanup
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON cache(timestamp)
            """)
            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Store a value in the cache.

        Args:
            key: Cache key
            value: Value to store (will be JSON serialized)
            ttl: Time-to-live in seconds (uses default if not specified)
        """
        if ttl is None:
            ttl = self.ttl_seconds

        timestamp = time.time()
        value_json = json.dumps(value)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO cache (key, value, timestamp, ttl)
                VALUES (?, ?, ?, ?)
            """,
                (key, value_json, timestamp, ttl),
            )
            conn.commit()

        logger.debug(f"Cached data for key: {key}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a value from the cache.

        Args:
            key: Cache key
            default: Default value if key not found or expired

        Returns:
            Cached value or default
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT value, timestamp, ttl FROM cache WHERE key = ?
            """,
                (key,),
            )
            row = cursor.fetchone()

        if row is None:
            logger.debug(f"Cache miss for key: {key}")
            return default

        value_json, timestamp, ttl = row
        current_time = time.time()

        # Check if expired
        if current_time - timestamp > ttl:
            logger.debug(f"Cache expired for key: {key}")
            self.delete(key)
            return default

        logger.debug(f"Cache hit for key: {key}")
        return json.loads(value_json)

    def delete(self, key: str) -> None:
        """
        Delete a value from the cache.

        Args:
            key: Cache key to delete
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM cache WHERE key = ?", (key,))
            conn.commit()

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from the cache.

        Returns:
            Number of entries removed
        """
        current_time = time.time()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Find and delete expired entries
            cursor.execute(
                """
                DELETE FROM cache 
                WHERE (? - timestamp) > ttl
            """,
                (current_time,),
            )
            deleted_count = cursor.rowcount
            conn.commit()

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} expired cache entries")

        return deleted_count

    def clear_all(self) -> None:
        """Clear all entries from the cache."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM cache")
            conn.commit()
        logger.info("Cleared all cache entries")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM cache")
            total_entries = cursor.fetchone()[0]

            current_time = time.time()
            cursor.execute(
                """
                SELECT COUNT(*) FROM cache 
                WHERE (? - timestamp) > ttl
            """,
                (current_time,),
            )
            expired_entries = cursor.fetchone()[0]

        return {
            "total_entries": total_entries,
            "active_entries": total_entries - expired_entries,
            "expired_entries": expired_entries,
        }
