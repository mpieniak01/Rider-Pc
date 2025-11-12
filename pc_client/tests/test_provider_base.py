"""Tests for provider base classes."""

import pytest
from pc_client.providers.base import (
    TaskEnvelope,
    TaskResult,
    TaskType,
    TaskStatus,
    BaseProvider
)


def test_task_envelope_creation():
    """Test TaskEnvelope creation."""
    task = TaskEnvelope(
        task_id="test-1",
        task_type=TaskType.VOICE_ASR,
        payload={"audio_data": "test_data"},
        meta={"source": "test"},
        priority=5
    )
    
    assert task.task_id == "test-1"
    assert task.task_type == TaskType.VOICE_ASR
    assert task.payload == {"audio_data": "test_data"}
    assert task.meta == {"source": "test"}
    assert task.priority == 5


def test_task_envelope_to_dict():
    """Test TaskEnvelope conversion to dict."""
    task = TaskEnvelope(
        task_id="test-1",
        task_type=TaskType.VOICE_ASR,
        payload={"data": "test"}
    )
    
    task_dict = task.to_dict()
    assert task_dict["task_id"] == "test-1"
    assert task_dict["task_type"] == TaskType.VOICE_ASR
    assert task_dict["payload"] == {"data": "test"}


def test_task_envelope_from_dict():
    """Test TaskEnvelope creation from dict."""
    data = {
        "task_id": "test-1",
        "task_type": "voice.asr",
        "payload": {"data": "test"},
        "meta": {},
        "priority": 5
    }
    
    task = TaskEnvelope.from_dict(data)
    assert task.task_id == "test-1"
    assert task.task_type == TaskType.VOICE_ASR
    assert task.payload == {"data": "test"}


def test_task_result_creation():
    """Test TaskResult creation."""
    result = TaskResult(
        task_id="test-1",
        status=TaskStatus.COMPLETED,
        result={"text": "transcription"},
        processing_time_ms=150.5
    )
    
    assert result.task_id == "test-1"
    assert result.status == TaskStatus.COMPLETED
    assert result.result == {"text": "transcription"}
    assert result.processing_time_ms == 150.5
    assert result.error is None


def test_task_result_with_error():
    """Test TaskResult with error."""
    result = TaskResult(
        task_id="test-1",
        status=TaskStatus.FAILED,
        error="Processing failed"
    )
    
    assert result.task_id == "test-1"
    assert result.status == TaskStatus.FAILED
    assert result.error == "Processing failed"
    assert result.result is None


def test_task_result_to_dict():
    """Test TaskResult conversion to dict."""
    result = TaskResult(
        task_id="test-1",
        status=TaskStatus.COMPLETED,
        result={"data": "result"}
    )
    
    result_dict = result.to_dict()
    assert result_dict["task_id"] == "test-1"
    assert result_dict["status"] == TaskStatus.COMPLETED


def test_task_result_from_dict():
    """Test TaskResult creation from dict."""
    data = {
        "task_id": "test-1",
        "status": "completed",
        "result": {"data": "result"},
        "error": None,
        "processing_time_ms": 100.0,
        "meta": {}
    }
    
    result = TaskResult.from_dict(data)
    assert result.task_id == "test-1"
    assert result.status == TaskStatus.COMPLETED
    assert result.result == {"data": "result"}


class MockProvider(BaseProvider):
    """Mock provider for testing."""
    
    async def _initialize_impl(self):
        pass
    
    async def _shutdown_impl(self):
        pass
    
    async def _process_task_impl(self, task: TaskEnvelope) -> TaskResult:
        return TaskResult(
            task_id=task.task_id,
            status=TaskStatus.COMPLETED,
            result={"mock": "result"}
        )
    
    def get_supported_tasks(self):
        return [TaskType.VOICE_ASR]


@pytest.mark.asyncio
async def test_provider_initialization():
    """Test provider initialization."""
    provider = MockProvider("TestProvider", {"test": "config"})
    
    assert provider.name == "TestProvider"
    assert provider.config == {"test": "config"}
    assert not provider._initialized
    
    await provider.initialize()
    assert provider._initialized
    
    await provider.shutdown()
    assert not provider._initialized


@pytest.mark.asyncio
async def test_provider_process_task():
    """Test provider task processing."""
    provider = MockProvider("TestProvider")
    await provider.initialize()
    
    task = TaskEnvelope(
        task_id="test-1",
        task_type=TaskType.VOICE_ASR,
        payload={"data": "test"}
    )
    
    result = await provider.process_task(task)
    
    assert result.task_id == "test-1"
    assert result.status == TaskStatus.COMPLETED
    assert result.result == {"mock": "result"}
    assert result.processing_time_ms is not None
    
    await provider.shutdown()


@pytest.mark.asyncio
async def test_provider_process_task_not_initialized():
    """Test processing task when provider not initialized."""
    provider = MockProvider("TestProvider")
    
    task = TaskEnvelope(
        task_id="test-1",
        task_type=TaskType.VOICE_ASR,
        payload={"data": "test"}
    )
    
    result = await provider.process_task(task)
    
    assert result.status == TaskStatus.FAILED
    assert "not initialized" in result.error


@pytest.mark.asyncio
async def test_provider_process_task_error():
    """Test provider handling of task processing errors."""
    
    class ErrorProvider(BaseProvider):
        async def _initialize_impl(self):
            pass
        
        async def _shutdown_impl(self):
            pass
        
        async def _process_task_impl(self, task: TaskEnvelope) -> TaskResult:
            raise ValueError("Test error")
    
    provider = ErrorProvider("ErrorProvider")
    await provider.initialize()
    
    task = TaskEnvelope(
        task_id="test-1",
        task_type=TaskType.VOICE_ASR,
        payload={"data": "test"}
    )
    
    result = await provider.process_task(task)
    
    assert result.status == TaskStatus.FAILED
    assert "Test error" in result.error
    assert result.processing_time_ms is not None
    
    await provider.shutdown()


def test_provider_get_telemetry():
    """Test provider telemetry."""
    provider = MockProvider("TestProvider", {"key": "value"})
    
    telemetry = provider.get_telemetry()
    
    assert telemetry["provider"] == "TestProvider"
    assert telemetry["initialized"] is False
    assert telemetry["supported_tasks"] == ["voice.asr"]


def test_provider_get_supported_tasks():
    """Test getting supported tasks."""
    provider = MockProvider("TestProvider")
    
    tasks = provider.get_supported_tasks()
    
    assert tasks == [TaskType.VOICE_ASR]
