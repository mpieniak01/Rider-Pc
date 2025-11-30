"""Cache manager using SQLite for data storage."""

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Optional
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
        self._use_memory_cache = False
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

    def _switch_to_memory_cache(self, exc: Exception) -> None:
        """Switch to in-memory cache when disk operations fail."""
        if self._use_memory_cache:
            return
        logger.warning(
            "Cache database error (%s); switching to in-memory cache (DB path: %s)",
            exc,
            self.db_path,
        )
        self._use_memory_cache = True
        self._memory_cache.clear()

    def _create_memory_entry(self, value: Any, ttl: int) -> Dict[str, Any]:
        return {"value": json.dumps(value), "timestamp": time.time(), "ttl": ttl}

    def _memory_set(self, key: str, value: Any, ttl: int) -> None:
        self._memory_cache[key] = self._create_memory_entry(value, ttl)

    def _memory_get(self, key: str, default: Any = None) -> Any:
        entry = self._memory_cache.get(key)
        if not entry:
            logger.debug(f"Cache miss for key: {key} (memory cache)")
            return default
        if time.time() - entry["timestamp"] >= entry["ttl"]:
            logger.debug(f"Cache expired for key: {key} (memory cache)")
            self._memory_cache.pop(key, None)
            return default
        logger.debug(f"Cache hit for key: {key} (memory cache)")
        return json.loads(entry["value"])

    def _memory_delete(self, key: str) -> None:
        self._memory_cache.pop(key, None)

    def _memory_cleanup_expired(self) -> int:
        now = time.time()
        expired = [key for key, entry in self._memory_cache.items() if now - entry["timestamp"] >= entry["ttl"]]
        for key in expired:
            self._memory_cache.pop(key, None)
        return len(expired)

    def _memory_clear_all(self) -> None:
        self._memory_cache.clear()

    def _memory_get_stats(self) -> Dict[str, Any]:
        now = time.time()
        total = len(self._memory_cache)
        expired = len([1 for entry in self._memory_cache.values() if now - entry["timestamp"] >= entry["ttl"]])
        return {
            "total_entries": total,
            "active_entries": total - expired,
            "expired_entries": expired,
        }

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

        if self._use_memory_cache:
            self._memory_set(key, value, ttl)
            return

        timestamp = time.time()
        value_json = json.dumps(value)

        try:
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
        except sqlite3.DatabaseError as exc:
            self._switch_to_memory_cache(exc)
            self._memory_set(key, value, ttl)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a value from the cache.

        Args:
            key: Cache key
            default: Default value if key not found or expired

        Returns:
            Cached value or default
        """
        if self._use_memory_cache:
            return self._memory_get(key, default)

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                SELECT value, timestamp, ttl FROM cache WHERE key = ?
            """,
                    (key,),
                )
                row = cursor.fetchone()
        except sqlite3.DatabaseError as exc:
            self._switch_to_memory_cache(exc)
            return self._memory_get(key, default)

        if row is None:
            logger.debug(f"Cache miss for key: {key}")
            return default

        value_json, timestamp, ttl = row
        current_time = time.time()

        # Check if expired
        if current_time - timestamp >= ttl:
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
        if self._use_memory_cache:
            self._memory_delete(key)
            return

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM cache WHERE key = ?", (key,))
                conn.commit()
        except sqlite3.DatabaseError as exc:
            self._switch_to_memory_cache(exc)
            self._memory_delete(key)

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from the cache.

        Returns:
            Number of entries removed
        """
        current_time = time.time()

        if self._use_memory_cache:
            deleted_count = self._memory_cleanup_expired()
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired cache entries")
            return deleted_count

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                changes_before = conn.total_changes
                # Find and delete expired entries
                cursor.execute(
                    """
                DELETE FROM cache 
                WHERE (? - timestamp) >= ttl
            """,
                    (current_time,),
                )
                # rowcount is unreliable on SQLite; total_changes reflects committed deletions
                deleted_count = conn.total_changes - changes_before
                conn.commit()
        except sqlite3.DatabaseError as exc:
            self._switch_to_memory_cache(exc)
            deleted_count = self._memory_cleanup_expired()

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} expired cache entries")

        return deleted_count

    def clear_all(self) -> None:
        """Clear all entries from the cache."""
        if self._use_memory_cache:
            self._memory_clear_all()
            logger.info("Cleared all cache entries")
            return

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM cache")
                conn.commit()
            logger.info("Cleared all cache entries")
        except sqlite3.DatabaseError as exc:
            self._switch_to_memory_cache(exc)
            self._memory_clear_all()
            logger.info("Cleared all cache entries (memory)")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        if self._use_memory_cache:
            return self._memory_get_stats()

        current_time = time.time()
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM cache")
                total_entries = cursor.fetchone()[0]
                cursor.execute(
                    """
                SELECT COUNT(*) FROM cache 
                WHERE (? - timestamp) >= ttl
            """,
                    (current_time,),
                )
                expired_entries = cursor.fetchone()[0]
        except sqlite3.DatabaseError as exc:
            self._switch_to_memory_cache(exc)
            return self._memory_get_stats()

        return {
            "total_entries": total_entries,
            "active_entries": total_entries - expired_entries,
            "expired_entries": expired_entries,
        }
