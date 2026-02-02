"""Tests for Redis task queue."""

import os
import pytest
from pc_client.queue.redis_queue import RedisTaskQueue, REDIS_AVAILABLE
from pc_client.providers.base import TaskEnvelope, TaskType

if os.getenv("RIDER_ENABLE_REDIS_TESTS", "").lower() not in {"1", "true", "yes", "on"}:
    pytest.skip("Redis queue tests disabled (set RIDER_ENABLE_REDIS_TESTS=1 to run)", allow_module_level=True)


@pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not installed")
class TestRedisTaskQueue:
    """Tests for Redis task queue (requires Redis to be running)."""

    @pytest.mark.asyncio
    async def test_redis_queue_unavailable(self):
        """Test Redis queue when Redis is not available."""
        queue = RedisTaskQueue(host="invalid-host", port=9999)

        # Should raise exception on connect
        with pytest.raises(Exception):
            await queue.connect()

    @pytest.mark.asyncio
    async def test_redis_queue_enqueue_without_connection(self):
        """Test enqueueing without connection."""
        queue = RedisTaskQueue()

        task = TaskEnvelope(task_id="test-1", task_type=TaskType.VOICE_ASR, payload={"test": "data"}, priority=5)

        # Should fail gracefully
        result = await queue.enqueue(task)
        assert result is False


def test_redis_not_available_error():
    """Test that proper error is raised when redis is not installed."""
    # This test should always pass if REDIS_AVAILABLE is True
    if REDIS_AVAILABLE:
        queue = RedisTaskQueue()
        assert queue is not None
    else:
        # If Redis is not available, creating queue should raise ImportError
        with pytest.raises(ImportError):
            RedisTaskQueue()


@pytest.mark.asyncio
async def test_redis_queue_size_without_connection():
    """Test getting queue size without connection."""
    if not REDIS_AVAILABLE:
        pytest.skip("Redis not installed")

    queue = RedisTaskQueue()
    size = await queue.size()
    assert size == 0


@pytest.mark.asyncio
async def test_redis_queue_stats_without_connection():
    """Test getting stats without connection."""
    if not REDIS_AVAILABLE:
        pytest.skip("Redis not installed")

    queue = RedisTaskQueue()
    stats = await queue.get_stats()
    assert isinstance(stats, dict)
