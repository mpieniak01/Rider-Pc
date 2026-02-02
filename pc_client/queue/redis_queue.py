"""Redis backend for task queue."""

import asyncio
import json
import logging
from typing import Any, Awaitable, Dict, Optional, Tuple, TYPE_CHECKING, cast

if TYPE_CHECKING:
    from redis.asyncio import Redis as RedisType
else:
    RedisType = Any

try:
    import redis.asyncio as aioredis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    aioredis = None  # type: ignore[assignment]

from pc_client.providers.base import TaskEnvelope, TaskResult

logger = logging.getLogger(__name__)


class RedisTaskQueue:
    """
    Redis-backed task queue implementation.

    This provides persistent task queue storage using Redis lists
    with priority queue support via multiple Redis lists.
    """

    def __init__(self, host: str = "localhost", port: int = 6379, password: Optional[str] = None, db: int = 0):
        """
        Initialize Redis task queue.

        Args:
            host: Redis host
            port: Redis port
            password: Redis password (optional)
            db: Redis database number
        """
        if not REDIS_AVAILABLE:
            raise ImportError("redis package not installed. Install with: pip install redis")

        self.host = host
        self.port = port
        self.password = password
        self.db = db
        self.redis: Optional[RedisType] = None
        self.logger = logging.getLogger("[bridge] RedisTaskQueue")

        # Queue names by priority (1=highest, 10=lowest)
        self.queue_names: Dict[int, str] = {
            1: "task_queue:priority_critical",
            2: "task_queue:priority_high",
            3: "task_queue:priority_medium",
            4: "task_queue:priority_medium",
            5: "task_queue:priority_medium",
            6: "task_queue:priority_medium",
            7: "task_queue:priority_low",
            8: "task_queue:priority_low",
            9: "task_queue:priority_low",
            10: "task_queue:priority_low",
        }

    async def connect(self):
        """Connect to Redis."""
        try:
            redis_client = await aioredis.from_url(
                f"redis://{self.host}:{self.port}/{self.db}",
                password=self.password,
                encoding="utf-8",
                decode_responses=True,
            )
            self.redis = redis_client
            await redis_client.ping()
            self.logger.info(f"Connected to Redis at {self.host}:{self.port}")
        except Exception as e:
            self.logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()
            self.logger.info("Disconnected from Redis")

    async def enqueue(self, task: TaskEnvelope) -> bool:
        """
        Add task to queue.

        Args:
            task: Task envelope to enqueue

        Returns:
            True if enqueued successfully
        """
        if not self.redis:
            self.logger.error("Not connected to Redis")
            return False

        try:
            # Get queue name based on priority
            queue_name = self.queue_names.get(task.priority, "task_queue:priority_medium")

            # Serialize task
            task_json = json.dumps(task.to_dict())

            # Push to Redis list (LPUSH for FIFO with BRPOP)
            redis_client = cast(RedisType, self.redis)
            await cast(Awaitable[int], redis_client.lpush(queue_name, task_json))

            self.logger.debug(f"Enqueued task {task.task_id} to {queue_name} (priority: {task.priority})")

            return True
        except Exception as e:
            self.logger.error(f"Failed to enqueue task: {e}")
            return False

    async def dequeue(self, timeout: float = 1.0) -> Optional[TaskEnvelope]:
        """
        Get next task from queue (priority order).

        Args:
            timeout: Maximum time to wait for a task

        Returns:
            Task envelope or None if timeout
        """
        if not self.redis:
            self.logger.error("Not connected to Redis")
            return None

        try:
            # Try to pop from queues in priority order
            queue_list: list[str] = [
                "task_queue:priority_critical",
                "task_queue:priority_high",
                "task_queue:priority_medium",
                "task_queue:priority_low",
            ]

            # BRPOP blocks until a task is available or timeout
            redis_client = cast(RedisType, self.redis)
            timeout_value = int(timeout)
            result: Optional[Tuple[str, str]] = await cast(
                Awaitable[Optional[Tuple[str, str]]],
                redis_client.brpop(queue_list, timeout=timeout_value),
            )

            if result:
                queue_name, task_json = result
                task_dict = json.loads(task_json)
                task = TaskEnvelope.from_dict(task_dict)

                self.logger.debug(f"Dequeued task {task.task_id} from {queue_name}")

                return task

            return None
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            self.logger.error(f"Failed to dequeue task: {e}")
            return None

    async def size(self) -> int:
        """Get total queue size across all priorities."""
        if not self.redis:
            return 0

        try:
            total = 0
            redis_client = cast(RedisType, self.redis)
            for queue_name in set(self.queue_names.values()):
                length = await cast(Awaitable[int], redis_client.llen(queue_name))
                total += length
            return total
        except Exception as e:
            self.logger.error(f"Failed to get queue size: {e}")
            return 0

    async def clear(self):
        """Clear all queues."""
        if not self.redis:
            return

        try:
            redis_client = cast(RedisType, self.redis)
            for queue_name in set(self.queue_names.values()):
                await cast(Awaitable[int], redis_client.delete(queue_name))
            self.logger.info("All queues cleared")
        except Exception as e:
            self.logger.error(f"Failed to clear queues: {e}")

    async def get_stats(self) -> dict:
        """Get queue statistics."""
        if not self.redis:
            return {}

        try:
            redis_client = cast(RedisType, self.redis)
            queue_lengths: Dict[str, int] = {}
            for queue_name in set(self.queue_names.values()):
                length = await cast(Awaitable[int], redis_client.llen(queue_name))
                queue_lengths[queue_name] = length

            stats: Dict[str, object] = dict(queue_lengths)
            stats["total_size"] = sum(queue_lengths.values())
            stats["connected"] = True

            return stats
        except Exception as e:
            self.logger.error(f"Failed to get stats: {e}")
            return {"connected": False, "error": str(e)}
