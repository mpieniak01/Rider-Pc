"""End-to-end integration test for task offload."""

import asyncio
import os

import pytest

from pc_client.providers import VoiceProvider, VisionProvider, TextProvider
from pc_client.providers.base import TaskEnvelope, TaskType, TaskStatus
from pc_client.queue import TaskQueue
from pc_client.queue.task_queue import TaskQueueWorker


def _e2e_enabled() -> bool:
    """Return True when hardware-dependent E2E provider tests should run."""
    flag = os.getenv("RIDER_ENABLE_PROVIDER_E2E", "")
    return flag.lower() in {"1", "true", "yes", "on"}


pytestmark = pytest.mark.skipif(
    not _e2e_enabled(),
    reason="Provider E2E tests require aktywne Rider-Pi/offload stack; set RIDER_ENABLE_PROVIDER_E2E=1 to run.",
)


@pytest.mark.asyncio
async def test_end_to_end_voice_offload():
    """Test end-to-end voice task offload from queue to provider."""
    # Initialize provider
    voice_provider = VoiceProvider(config={"use_mock": True})
    await voice_provider.initialize()

    # Create task queue
    task_queue = TaskQueue(max_size=10)

    # Create worker with providers
    providers = {"voice": voice_provider}
    worker = TaskQueueWorker(task_queue, providers)

    # Create ASR task
    task = TaskEnvelope(
        task_id="e2e-asr-1",
        task_type=TaskType.VOICE_ASR,
        payload={
            "audio_data": "dGVzdCBhdWRpbyBkYXRh",  # Valid base64: "test audio data"
            "format": "wav",
            "sample_rate": 16000,
        },
        priority=5,
    )

    # Enqueue task
    success = await task_queue.enqueue(task)
    assert success is True

    # Process task (simulating worker)
    dequeued_task = await task_queue.dequeue()
    assert dequeued_task.task_id == "e2e-asr-1"

    result = await worker._process_task(dequeued_task)

    # Verify result
    assert result.task_id == "e2e-asr-1"
    assert result.status == TaskStatus.COMPLETED
    assert "text" in result.result
    assert result.processing_time_ms is not None

    # Cleanup
    await voice_provider.shutdown()


@pytest.mark.asyncio
async def test_end_to_end_vision_offload():
    """Test end-to-end vision task offload from queue to provider."""
    # Initialize provider
    vision_provider = VisionProvider()
    await vision_provider.initialize()

    # Create task queue
    task_queue = TaskQueue(max_size=10)

    # Create worker with providers
    providers = {"vision": vision_provider}
    worker = TaskQueueWorker(task_queue, providers)

    # Create detection task
    task = TaskEnvelope(
        task_id="e2e-detect-1",
        task_type=TaskType.VISION_DETECTION,
        payload={
            "image_data": "dGVzdCBpbWFnZSBkYXRh",  # Valid base64: "test image data"
            "format": "jpeg",
            "width": 640,
            "height": 480,
        },
        priority=8,  # High priority for vision
    )

    # Enqueue task
    success = await task_queue.enqueue(task)
    assert success is True

    # Process task
    dequeued_task = await task_queue.dequeue()
    result = await worker._process_task(dequeued_task)

    # Verify result
    assert result.task_id == "e2e-detect-1"
    assert result.status == TaskStatus.COMPLETED
    assert "detections" in result.result
    assert result.processing_time_ms is not None

    # Cleanup
    await vision_provider.shutdown()


@pytest.mark.asyncio
async def test_end_to_end_text_offload():
    """Test end-to-end text task offload from queue to provider."""
    # Initialize provider
    text_provider = TextProvider()
    await text_provider.initialize()

    # Create task queue
    task_queue = TaskQueue(max_size=10)

    # Create worker with providers
    providers = {"text": text_provider}
    worker = TaskQueueWorker(task_queue, providers)

    # Create generation task
    task = TaskEnvelope(
        task_id="e2e-gen-1",
        task_type=TaskType.TEXT_GENERATE,
        payload={"prompt": "What is the weather?", "max_tokens": 100},
        priority=3,  # Lower priority for text
    )

    # Enqueue task
    success = await task_queue.enqueue(task)
    assert success is True

    # Process task
    dequeued_task = await task_queue.dequeue()
    result = await worker._process_task(dequeued_task)

    # Verify result
    assert result.task_id == "e2e-gen-1"
    assert result.status == TaskStatus.COMPLETED
    assert "text" in result.result
    assert result.processing_time_ms is not None

    # Cleanup
    await text_provider.shutdown()


@pytest.mark.asyncio
async def test_end_to_end_priority_queue():
    """Test end-to-end with priority queue handling."""
    # Initialize all providers
    voice_provider = VoiceProvider(config={"use_mock": True})
    vision_provider = VisionProvider()
    text_provider = TextProvider()

    await voice_provider.initialize()
    await vision_provider.initialize()
    await text_provider.initialize()

    # Create task queue
    task_queue = TaskQueue(max_size=20)

    # Create worker with all providers
    providers = {"voice": voice_provider, "vision": vision_provider, "text": text_provider}
    worker = TaskQueueWorker(task_queue, providers)

    # Enqueue tasks with different priorities
    tasks = [
        TaskEnvelope(
            task_id="low-priority",
            task_type=TaskType.TEXT_GENERATE,
            payload={"prompt": "test"},
            priority=10,  # Low priority
        ),
        TaskEnvelope(
            task_id="high-priority-obstacle",
            task_type=TaskType.VISION_FRAME,
            payload={"frame_data": "dGVzdCBmcmFtZSBkYXRh", "frame_id": 1, "timestamp": 123.0},  # Valid base64
            priority=1,  # Critical priority
        ),
        TaskEnvelope(
            task_id="medium-priority",
            task_type=TaskType.VOICE_ASR,
            payload={"audio_data": "dGVzdCBhdWRpbyBkYXRh"},  # Valid base64
            priority=5,  # Medium priority
        ),
    ]

    # Enqueue all tasks
    for task in tasks:
        await task_queue.enqueue(task)

    # Process tasks - should come out in priority order
    results = []
    for _ in range(3):
        task = await task_queue.dequeue()
        result = await worker._process_task(task)
        results.append((result.task_id, task.priority))

    # Verify priority order (1, 5, 10)
    assert results[0][0] == "high-priority-obstacle"
    assert results[0][1] == 1
    assert results[1][0] == "medium-priority"
    assert results[1][1] == 5
    assert results[2][0] == "low-priority"
    assert results[2][1] == 10

    # Cleanup
    await voice_provider.shutdown()
    await vision_provider.shutdown()
    await text_provider.shutdown()


@pytest.mark.asyncio
async def test_end_to_end_circuit_breaker_fallback():
    """Test end-to-end with circuit breaker fallback."""

    # Create a failing provider for testing
    class FailingProvider:
        async def process_task(self, task):
            raise Exception("Provider unavailable")

    failing_provider = FailingProvider()

    # Create task queue with circuit breaker
    task_queue = TaskQueue(max_size=10, enable_circuit_breaker=True)

    # Create worker
    providers = {"voice": failing_provider}
    worker = TaskQueueWorker(task_queue, providers)

    # Create task
    task = TaskEnvelope(
        task_id="e2e-fail-1",
        task_type=TaskType.VOICE_ASR,
        payload={"audio_data": "dGVzdCBhdWRpbyBkYXRh"},  # Valid base64
        priority=1,  # Critical task
    )

    # Enqueue and process
    await task_queue.enqueue(task)
    dequeued_task = await task_queue.dequeue()

    # Process should fail and trigger fallback
    result = await worker._process_task(dequeued_task)

    # Verify fallback was triggered
    assert result.status == TaskStatus.FAILED
    assert "Circuit breaker" in result.error or "Provider unavailable" in result.error


@pytest.mark.asyncio
async def test_end_to_end_telemetry():
    """Test end-to-end telemetry collection."""
    # Initialize provider with mock mode
    voice_provider = VoiceProvider({"asr_model": "test_model", "use_mock": True})
    await voice_provider.initialize()

    # Get telemetry before processing
    telemetry_before = voice_provider.get_telemetry()
    assert telemetry_before["provider"] == "VoiceProvider"
    assert telemetry_before["initialized"] is True
    assert telemetry_before["asr_model"] == "test_model"

    # Process task
    task = TaskEnvelope(
        task_id="e2e-telemetry-1",
        task_type=TaskType.VOICE_ASR,
        payload={"audio_data": "dGVzdCBhdWRpbyBkYXRh"},  # Valid base64
    )

    result = await voice_provider.process_task(task)

    # Verify telemetry data in result
    assert result.processing_time_ms is not None
    # In mock mode, the model name in meta should be "mock"
    assert result.meta["engine"] == "mock"

    # Cleanup
    await voice_provider.shutdown()


@pytest.mark.asyncio
async def test_end_to_end_queue_full_handling():
    """Test handling of full queue."""
    # Create small queue
    task_queue = TaskQueue(max_size=2)

    # Fill queue
    task1 = TaskEnvelope(task_id="fill-1", task_type=TaskType.VOICE_ASR, payload={}, priority=5)
    task2 = TaskEnvelope(task_id="fill-2", task_type=TaskType.VOICE_ASR, payload={}, priority=5)
    task3 = TaskEnvelope(task_id="fill-3", task_type=TaskType.VOICE_ASR, payload={}, priority=5)

    await task_queue.enqueue(task1)
    await task_queue.enqueue(task2)

    # Third enqueue should fail
    success = await task_queue.enqueue(task3)
    assert success is False

    # Queue stats should reflect this
    stats = task_queue.get_stats()
    assert stats["queue_full_count"] == 1
    assert stats["is_full"] is True
