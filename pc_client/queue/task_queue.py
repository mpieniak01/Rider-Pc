"""Task queue implementation with priority support."""

import asyncio
import logging
import time
from typing import Optional, Dict, Any
from queue import PriorityQueue, Empty
from dataclasses import dataclass, field
from datetime import datetime

from pc_client.providers.base import TaskEnvelope, TaskResult, TaskStatus, TaskType
from pc_client.queue.circuit_breaker import CircuitBreaker
from pc_client.telemetry.metrics import task_queue_size, task_queue_full_count

logger = logging.getLogger(__name__)


@dataclass(order=True)
class PrioritizedTask:
    """Task wrapper with priority for queue ordering."""

    priority: int
    timestamp: float = field(compare=False)
    task: TaskEnvelope = field(compare=False)


class TaskQueue:
    """
    Asynchronous task queue with priority support.

    This queue manages offload tasks from Rider-PI, ensuring critical tasks
    (e.g., obstacle avoidance) are processed with higher priority.
    """

    def __init__(self, max_size: int = 100, enable_circuit_breaker: bool = True):
        """
        Initialize task queue.

        Args:
            max_size: Maximum queue size
            enable_circuit_breaker: Enable circuit breaker for fallback
        """
        self.max_size = max_size
        self.queue: PriorityQueue[PrioritizedTask] = PriorityQueue(maxsize=max_size)
        self.circuit_breaker = CircuitBreaker() if enable_circuit_breaker else None
        self.logger = logging.getLogger("[bridge] TaskQueue")

        # Statistics
        self.stats = {"total_queued": 0, "total_processed": 0, "total_failed": 0, "queue_full_count": 0}

    async def enqueue(self, task: TaskEnvelope) -> bool:
        """
        Add task to queue.

        Args:
            task: Task envelope to enqueue

        Returns:
            True if enqueued successfully, False if queue is full
        """
        if self.queue.full():
            self.logger.warning(f"Queue is full, cannot enqueue task {task.task_id}")
            self.stats["queue_full_count"] += 1
            task_queue_full_count.inc()
            return False

        prioritized_task = PrioritizedTask(priority=task.priority, timestamp=datetime.now().timestamp(), task=task)

        # Use asyncio.to_thread for sync queue operations
        await asyncio.to_thread(self.queue.put, prioritized_task)

        self.stats["total_queued"] += 1
        self.logger.info(
            f"Enqueued task {task.task_id} (priority: {task.priority}, " f"queue size: {self.queue.qsize()})"
        )

        # Update metrics
        task_queue_size.labels(queue_name="main").set(self.queue.qsize())

        return True

    async def dequeue(self, timeout: Optional[float] = None) -> Optional[TaskEnvelope]:
        """
        Get next task from queue.

        Args:
            timeout: Maximum time to wait for a task (None = wait forever)

        Returns:
            Task envelope or None if timeout
        """
        try:
            prioritized_task = await asyncio.to_thread(self.queue.get, True, timeout)
        except Empty:
            return None

        self.logger.debug(f"Dequeued task {prioritized_task.task.task_id} " f"(queue size: {self.queue.qsize()})")

        task_queue_size.labels(queue_name="main").set(self.queue.qsize())
        return prioritized_task.task

    def size(self) -> int:
        """Get current queue size."""
        return self.queue.qsize()

    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return self.queue.empty()

    def is_full(self) -> bool:
        """Check if queue is full."""
        return self.queue.full()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics.

        Returns:
            Dictionary with queue statistics
        """
        stats = self.stats.copy()
        stats.update({"current_size": self.size(), "max_size": self.max_size, "is_full": self.is_full()})

        if self.circuit_breaker:
            stats["circuit_breaker"] = self.circuit_breaker.get_state()

        return stats

    def clear(self):
        """Clear all tasks from queue."""
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except:
                break

        self.logger.info("Queue cleared")


class TaskQueueWorker:
    """
    Worker for processing tasks from the queue.

    This worker continuously processes tasks from the queue and executes
    them using the appropriate provider.
    """

    def __init__(self, task_queue: TaskQueue, providers: Dict[str, Any], telemetry_publisher: Optional[Any] = None):
        """
        Initialize task queue worker.

        Args:
            task_queue: Task queue to process
            providers: Dictionary of provider instances by task type
            telemetry_publisher: Optional ZMQ telemetry publisher
        """
        self.task_queue = task_queue
        self.providers = providers
        self.telemetry_publisher = telemetry_publisher
        self.running = False
        self.logger = logging.getLogger("[bridge] TaskQueueWorker")

    async def start(self):
        """Start processing tasks from queue."""
        if self.running:
            self.logger.warning("Worker already running")
            return

        self.running = True
        self.logger.info("Task queue worker started")

        while self.running:
            try:
                # Get next task (with 1 second timeout to allow shutdown)
                task = await self.task_queue.dequeue(timeout=1.0)

                if task is None:
                    continue

                # Process task
                result = await self._process_task(task)

                # Update statistics
                if result.status == TaskStatus.COMPLETED:
                    self.task_queue.stats["total_processed"] += 1
                else:
                    self.task_queue.stats["total_failed"] += 1

                # Publish result to ZMQ bus (TODO: implement ZMQ publisher)
                await self._publish_result(task, result)

            except Exception as e:
                self.logger.error(f"Error in worker loop: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def stop(self):
        """Stop processing tasks."""
        if not self.running:
            return

        self.logger.info("Stopping task queue worker...")
        self.running = False

    async def _process_task(self, task: TaskEnvelope) -> TaskResult:
        """
        Process a task using the appropriate provider.

        Args:
            task: Task to process

        Returns:
            Task result
        """
        # Find provider for task type
        provider_key = task.task_type.value.split('.')[0]  # e.g., "voice" from "voice.asr"
        provider = self.providers.get(provider_key)

        if provider is None:
            self.logger.error(f"No provider found for task type: {task.task_type}")
            return TaskResult(
                task_id=task.task_id, status=TaskStatus.FAILED, error=f"No provider for task type: {task.task_type}"
            )

        # Process task with circuit breaker if available
        if self.task_queue.circuit_breaker:
            result = await self.task_queue.circuit_breaker.call_async(
                provider.process_task, self._fallback_handler, task
            )
        else:
            result = await provider.process_task(task)

        return result

    async def _fallback_handler(self, task: TaskEnvelope) -> TaskResult:
        """
        Fallback handler when circuit breaker is open.

        This indicates that offload processing should fail back to
        local processing on Rider-PI.

        Args:
            task: Task that failed

        Returns:
            Task result indicating fallback needed
        """
        self.logger.warning(f"Circuit breaker open for task {task.task_id}, " "signaling fallback to local processing")

        return TaskResult(
            task_id=task.task_id,
            status=TaskStatus.FAILED,
            error="Circuit breaker open, use local processing",
            meta={"fallback_required": True},
        )

    async def _publish_result(self, task: TaskEnvelope, result: TaskResult):
        """
        Publish task result to ZMQ bus.

        This publishes telemetry data about task completion back to Rider-PI.

        Args:
            task: Original task envelope
            result: Task result to publish
        """
        self.logger.debug(
            f"Task {result.task_id} completed with status {result.status} " f"in {result.processing_time_ms:.2f}ms"
        )

        # Publish to ZMQ telemetry bus if available
        if self.telemetry_publisher:
            try:
                self.telemetry_publisher.publish_task_result(result)

                # Publish enhanced vision data for frame tasks
                if task.task_type == TaskType.VISION_FRAME and result.status == TaskStatus.COMPLETED:
                    result_payload = result.result or {}
                    frame_id = result_payload.get("frame_id") or task.meta.get("frame_id") or task.task_id
                    timestamp = result_payload.get("timestamp") or result.meta.get("timestamp")
                    meta = dict(task.meta)
                    meta.update(result.meta)
                    if timestamp and "timestamp" not in meta:
                        meta["timestamp"] = timestamp
                    meta.setdefault("source_topic", task.meta.get("source_topic"))

                    self.telemetry_publisher.publish_vision_obstacle_enhanced(
                        frame_id=str(frame_id),
                        obstacles=result_payload.get("obstacles", []),
                        meta=meta,
                    )
                elif task.task_type == TaskType.VOICE_ASR and result.status == TaskStatus.COMPLETED:
                    result_payload = result.result or {}
                    message = {
                        "task_id": task.task_id,
                        "text": result_payload.get("text", ""),
                        "confidence": result_payload.get("confidence"),
                        "language": result_payload.get("language"),
                        "ts": time.time(),
                        "meta": {**task.meta, **result.meta},
                    }
                    self.telemetry_publisher.publish_voice_asr_result(message)
                elif task.task_type == TaskType.VOICE_TTS and result.status == TaskStatus.COMPLETED:
                    result_payload = result.result or {}
                    audio_data = result_payload.get("audio_data")
                    if audio_data:
                        chunk_meta = {**task.meta, **result.meta}
                        chunk_meta.setdefault("timestamp", time.time())
                        self.telemetry_publisher.publish_voice_tts_chunk(
                            {
                                "task_id": task.task_id,
                                "audio_data": audio_data,
                                "format": result_payload.get("format", "wav"),
                                "sample_rate": result_payload.get("sample_rate"),
                                "duration_ms": result_payload.get("duration_ms"),
                            },
                            chunk_meta,
                        )
            except Exception as e:
                self.logger.error(f"Failed to publish telemetry: {e}")
