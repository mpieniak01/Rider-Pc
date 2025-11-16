"""Tests for task queue and circuit breaker."""

import asyncio
from unittest.mock import MagicMock

import pytest

from pc_client.queue import TaskQueue, CircuitBreaker
from pc_client.queue.circuit_breaker import CircuitState, CircuitBreakerConfig
from pc_client.queue.task_queue import TaskQueueWorker
from pc_client.providers import VisionProvider, VoiceProvider
from pc_client.providers.base import TaskEnvelope, TaskResult, TaskType, TaskStatus


def test_circuit_breaker_closed_state():
    """Test circuit breaker in closed state."""
    cb = CircuitBreaker()

    assert cb.state == CircuitState.CLOSED

    # Successful calls
    result = cb.call(lambda x: x * 2, None, 5)
    assert result == 10
    assert cb.state == CircuitState.CLOSED


def test_circuit_breaker_open_on_failures():
    """Test circuit breaker opens after threshold failures."""
    config = CircuitBreakerConfig(failure_threshold=3)
    cb = CircuitBreaker(config)

    def failing_func():
        raise ValueError("Test error")

    def fallback_func():
        return "fallback"

    # Trigger failures
    for _ in range(3):
        result = cb.call(failing_func, fallback_func)
        assert result == "fallback"

    # Circuit should be open now
    assert cb.state == CircuitState.OPEN


def test_circuit_breaker_half_open_recovery():
    """Test circuit breaker recovery through half-open state."""
    config = CircuitBreakerConfig(
        failure_threshold=2,
        success_threshold=2,
        timeout_seconds=0,  # Immediate recovery attempt
    )
    cb = CircuitBreaker(config)

    def failing_func():
        raise ValueError("Test error")

    def success_func():
        return "success"

    def fallback_func():
        return "fallback"

    # Open the circuit
    for _ in range(2):
        cb.call(failing_func, fallback_func)

    assert cb.state == CircuitState.OPEN

    # Should transition to half-open
    result = cb.call(success_func, fallback_func)
    assert result == "success"
    assert cb.state == CircuitState.HALF_OPEN

    # Another success should close it
    result = cb.call(success_func, fallback_func)
    assert result == "success"
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_circuit_breaker_async():
    """Test circuit breaker with async functions."""
    cb = CircuitBreaker()

    async def async_func(x):
        return x * 2

    result = await cb.call_async(async_func, None, 5)
    assert result == 10


def test_circuit_breaker_get_state():
    """Test getting circuit breaker state."""
    cb = CircuitBreaker()

    state = cb.get_state()
    assert state["state"] == "closed"
    assert state["failure_count"] == 0
    assert state["success_count"] == 0


def test_circuit_breaker_reset():
    """Test manual circuit breaker reset."""
    config = CircuitBreakerConfig(failure_threshold=2)
    cb = CircuitBreaker(config)

    def failing_func():
        raise ValueError("Test error")

    def fallback_func():
        return "fallback"

    # Open the circuit
    for _ in range(2):
        cb.call(failing_func, fallback_func)

    assert cb.state == CircuitState.OPEN

    # Reset
    cb.reset()
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0


@pytest.mark.asyncio
async def test_task_queue_enqueue_dequeue():
    """Test task queue enqueue and dequeue."""
    queue = TaskQueue(max_size=10)

    task = TaskEnvelope(task_id="test-1", task_type=TaskType.VOICE_ASR, payload={"data": "test"}, priority=5)

    # Enqueue
    success = await queue.enqueue(task)
    assert success is True
    assert queue.size() == 1

    # Dequeue
    dequeued_task = await queue.dequeue(timeout=1.0)
    assert dequeued_task is not None
    assert dequeued_task.task_id == "test-1"
    assert queue.size() == 0


@pytest.mark.asyncio
async def test_task_queue_priority():
    """Test task queue priority ordering."""
    queue = TaskQueue(max_size=10)

    # Enqueue tasks with different priorities
    tasks = [
        TaskEnvelope(task_id=f"task-{i}", task_type=TaskType.VOICE_ASR, payload={}, priority=priority)
        for i, priority in enumerate([5, 1, 10, 3])
    ]

    for task in tasks:
        await queue.enqueue(task)

    # Dequeue should return in priority order (1, 3, 5, 10)
    dequeued = []
    for _ in range(4):
        task = await queue.dequeue(timeout=1.0)
        dequeued.append(task.priority)

    assert dequeued == [1, 3, 5, 10]


@pytest.mark.asyncio
async def test_task_queue_full():
    """Test task queue when full."""
    queue = TaskQueue(max_size=2)

    task1 = TaskEnvelope(task_id="task-1", task_type=TaskType.VOICE_ASR, payload={}, priority=5)

    task2 = TaskEnvelope(task_id="task-2", task_type=TaskType.VOICE_ASR, payload={}, priority=5)

    task3 = TaskEnvelope(task_id="task-3", task_type=TaskType.VOICE_ASR, payload={}, priority=5)

    # Fill queue
    await queue.enqueue(task1)
    await queue.enqueue(task2)

    assert queue.is_full()

    # Try to add one more (should fail)
    success = await queue.enqueue(task3)
    assert success is False
    assert queue.stats["queue_full_count"] == 1


@pytest.mark.asyncio
async def test_task_queue_timeout():
    """Test task queue dequeue timeout."""
    queue = TaskQueue(max_size=10)

    # Dequeue from empty queue with timeout
    task = await queue.dequeue(timeout=0.1)
    assert task is None


@pytest.mark.asyncio
async def test_task_queue_stats():
    """Test task queue statistics."""
    queue = TaskQueue(max_size=10)

    task = TaskEnvelope(task_id="test-1", task_type=TaskType.VOICE_ASR, payload={}, priority=5)

    await queue.enqueue(task)

    stats = queue.get_stats()
    assert stats["total_queued"] == 1
    assert stats["current_size"] == 1
    assert stats["max_size"] == 10
    assert stats["is_full"] is False


@pytest.mark.asyncio
async def test_task_queue_clear():
    """Test clearing task queue."""
    queue = TaskQueue(max_size=10)

    # Add some tasks
    for i in range(5):
        task = TaskEnvelope(task_id=f"task-{i}", task_type=TaskType.VOICE_ASR, payload={}, priority=5)
        await queue.enqueue(task)

    assert queue.size() == 5

    # Clear queue
    queue.clear()
    assert queue.size() == 0
    assert queue.is_empty()


@pytest.mark.asyncio
async def test_task_queue_with_circuit_breaker():
    """Test task queue integration with circuit breaker."""
    queue = TaskQueue(max_size=10, enable_circuit_breaker=True)

    assert queue.circuit_breaker is not None

    stats = queue.get_stats()
    assert "circuit_breaker" in stats
    assert stats["circuit_breaker"]["state"] == "closed"


@pytest.mark.asyncio
async def test_task_queue_worker_mock():
    """Test task queue worker basic functionality."""
    queue = TaskQueue(max_size=10)
    providers = {}  # Empty for this test

    worker = TaskQueueWorker(queue, providers)

    assert worker.task_queue == queue
    assert worker.providers == providers
    assert worker.running is False


@pytest.mark.asyncio
async def test_worker_publishes_vision_results():
    """Vision frame results should trigger telemetry publication."""
    queue = TaskQueue(max_size=5)
    provider = VisionProvider({"use_mock": True})
    await provider.initialize()

    telemetry = MagicMock()
    worker = TaskQueueWorker(queue, {"vision": provider}, telemetry_publisher=telemetry)

    task = TaskEnvelope(
        task_id="vision-test-1",
        task_type=TaskType.VISION_FRAME,
        payload={
            "frame_data": "ZGVtby1mcmFtZQ==",  # "demo-frame"
            "frame_id": "frame-123",
            "timestamp": 123.456,
        },
        priority=1,
    )

    result = await provider.process_task(task)
    await worker._publish_result(task, result)

    telemetry.publish_task_result.assert_called_once()
    telemetry.publish_vision_obstacle_enhanced.assert_called_once()
    _, kwargs = telemetry.publish_vision_obstacle_enhanced.call_args
    assert kwargs["frame_id"] == "frame-123"
    assert isinstance(kwargs["obstacles"], list)

    await provider.shutdown()


@pytest.mark.asyncio
async def test_worker_publishes_voice_asr_results():
    """Voice ASR results should be published to ZMQ."""
    queue = TaskQueue(max_size=5)
    provider = VoiceProvider({"use_mock": True})
    await provider.initialize()

    telemetry = MagicMock()
    worker = TaskQueueWorker(queue, {"voice": provider}, telemetry_publisher=telemetry)

    task = TaskEnvelope(
        task_id="voice-asr-1",
        task_type=TaskType.VOICE_ASR,
        payload={
            "audio_data": "ZGVtby1hdWRpbw==",
            "format": "wav",
            "sample_rate": 16000,
        },
        meta={"request_id": "req-1"},
    )

    result = await provider.process_task(task)
    await worker._publish_result(task, result)

    telemetry.publish_voice_asr_result.assert_called_once()
    payload = telemetry.publish_voice_asr_result.call_args[0][0]
    assert isinstance(payload["text"], str)

    await provider.shutdown()


@pytest.mark.asyncio
async def test_worker_publishes_voice_tts_chunks():
    """Voice TTS results publish audio chunks."""
    queue = TaskQueue(max_size=5)
    provider = VoiceProvider({"use_mock": True})
    await provider.initialize()

    telemetry = MagicMock()
    worker = TaskQueueWorker(queue, {"voice": provider}, telemetry_publisher=telemetry)

    task = TaskEnvelope(
        task_id="voice-tts-1",
        task_type=TaskType.VOICE_TTS,
        payload={"text": "Hello Rider"},
        meta={"request_id": "req-2"},
    )

    result = await provider.process_task(task)
    await worker._publish_result(task, result)

    telemetry.publish_voice_tts_chunk.assert_called_once()
    args, kwargs = telemetry.publish_voice_tts_chunk.call_args
    assert "audio_data" in args[0]
    assert args[1]["request_id"] == "req-2"

    await provider.shutdown()
