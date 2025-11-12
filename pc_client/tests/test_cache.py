"""Tests for the cache manager."""

import pytest
import time
import tempfile
from pathlib import Path

from pc_client.cache import CacheManager


@pytest.fixture
def temp_cache():
    """Create a temporary cache for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_cache.db"
        cache = CacheManager(db_path=str(db_path), ttl_seconds=2)
        yield cache
        cache.clear_all()


def test_cache_set_and_get(temp_cache):
    """Test setting and getting values from cache."""
    temp_cache.set("test_key", {"data": "test_value"})
    result = temp_cache.get("test_key")
    assert result == {"data": "test_value"}


def test_cache_get_default(temp_cache):
    """Test getting non-existent key returns default."""
    result = temp_cache.get("nonexistent", default={"default": "value"})
    assert result == {"default": "value"}


def test_cache_expiration(temp_cache):
    """Test that cache entries expire after TTL."""
    temp_cache.set("expire_key", {"data": "expires"}, ttl=1)
    
    # Should exist immediately
    result = temp_cache.get("expire_key")
    assert result == {"data": "expires"}
    
    # Wait for expiration
    time.sleep(1.5)
    
    # Should be expired
    result = temp_cache.get("expire_key", default=None)
    assert result is None


def test_cache_delete(temp_cache):
    """Test deleting cache entries."""
    temp_cache.set("delete_key", {"data": "delete_me"})
    assert temp_cache.get("delete_key") is not None
    
    temp_cache.delete("delete_key")
    assert temp_cache.get("delete_key") is None


def test_cache_cleanup_expired(temp_cache):
    """Test cleanup of expired entries."""
    # Add some entries with different TTLs
    temp_cache.set("short_ttl", {"data": "expires"}, ttl=1)
    temp_cache.set("long_ttl", {"data": "persists"}, ttl=10)
    
    # Wait for short TTL to expire
    time.sleep(1.5)
    
    # Cleanup expired entries
    deleted_count = temp_cache.cleanup_expired()
    assert deleted_count == 1
    
    # Check that long_ttl still exists
    assert temp_cache.get("long_ttl") is not None
    assert temp_cache.get("short_ttl") is None


def test_cache_stats(temp_cache):
    """Test cache statistics."""
    temp_cache.set("key1", {"data": "value1"}, ttl=10)
    temp_cache.set("key2", {"data": "value2"}, ttl=1)
    
    stats = temp_cache.get_stats()
    assert stats["total_entries"] == 2
    assert stats["active_entries"] == 2
    
    # Wait for one to expire
    time.sleep(1.5)
    
    stats = temp_cache.get_stats()
    assert stats["total_entries"] == 2
    assert stats["expired_entries"] == 1


def test_cache_clear_all(temp_cache):
    """Test clearing all cache entries."""
    temp_cache.set("key1", {"data": "value1"})
    temp_cache.set("key2", {"data": "value2"})
    
    stats = temp_cache.get_stats()
    assert stats["total_entries"] == 2
    
    temp_cache.clear_all()
    
    stats = temp_cache.get_stats()
    assert stats["total_entries"] == 0


def test_cache_complex_data(temp_cache):
    """Test storing complex data structures."""
    complex_data = {
        "nested": {
            "array": [1, 2, 3],
            "string": "test",
            "boolean": True,
            "null": None
        },
        "numbers": [1.5, 2.7, 3.9]
    }
    
    temp_cache.set("complex", complex_data)
    result = temp_cache.get("complex")
    assert result == complex_data
