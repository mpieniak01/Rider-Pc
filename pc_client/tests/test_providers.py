"""Tests for provider implementations."""

import pytest
from pc_client.providers import VoiceProvider, VisionProvider, TextProvider
from pc_client.providers.base import TaskEnvelope, TaskType, TaskStatus


@pytest.mark.asyncio
async def test_voice_provider_initialization():
    """Test VoiceProvider initialization."""
    config = {
        "asr_model": "test_asr",
        "tts_model": "test_tts",
        "sample_rate": 16000,
        "use_mock": True,  # Force mock mode for testing
    }

    provider = VoiceProvider(config)
    await provider.initialize()

    assert provider.asr_model_name == "test_asr"
    assert provider.tts_model_name == "test_tts"
    assert provider.sample_rate == 16000

    supported = provider.get_supported_tasks()
    assert TaskType.VOICE_ASR in supported
    assert TaskType.VOICE_TTS in supported

    await provider.shutdown()


@pytest.mark.asyncio
async def test_voice_provider_asr():
    """Test VoiceProvider ASR processing."""
    provider = VoiceProvider()
    await provider.initialize()

    task = TaskEnvelope(
        task_id="asr-1",
        task_type=TaskType.VOICE_ASR,
        payload={
            "audio_data": "dGVzdCBhdWRpbyBkYXRh",  # Valid base64: "test audio data"
            "format": "wav",
            "sample_rate": 16000,
        },
    )

    result = await provider.process_task(task)

    assert result.task_id == "asr-1"
    assert result.status == TaskStatus.COMPLETED
    assert "text" in result.result
    assert "confidence" in result.result
    assert result.processing_time_ms is not None

    await provider.shutdown()


@pytest.mark.asyncio
async def test_voice_provider_tts():
    """Test VoiceProvider TTS processing."""
    provider = VoiceProvider()
    await provider.initialize()

    task = TaskEnvelope(
        task_id="tts-1", task_type=TaskType.VOICE_TTS, payload={"text": "Hello world", "voice": "default", "speed": 1.0}
    )

    result = await provider.process_task(task)

    assert result.task_id == "tts-1"
    assert result.status == TaskStatus.COMPLETED
    assert "audio_data" in result.result
    assert "format" in result.result
    assert result.processing_time_ms is not None

    await provider.shutdown()


@pytest.mark.asyncio
async def test_voice_provider_missing_payload():
    """Test VoiceProvider with missing payload data."""
    provider = VoiceProvider()
    await provider.initialize()

    task = TaskEnvelope(
        task_id="asr-bad",
        task_type=TaskType.VOICE_ASR,
        payload={},  # Missing audio_data
    )

    result = await provider.process_task(task)

    assert result.task_id == "asr-bad"
    assert result.status == TaskStatus.FAILED
    assert "Missing audio_data" in result.error

    await provider.shutdown()


@pytest.mark.asyncio
async def test_vision_provider_initialization():
    """Test VisionProvider initialization."""
    config = {
        "detection_model": "test_model",
        "confidence_threshold": 0.7,
        "max_detections": 20,
        "use_mock": True,  # Force mock mode for testing
    }

    provider = VisionProvider(config)
    await provider.initialize()

    assert provider.detection_model_name == "test_model"
    assert provider.confidence_threshold == 0.7
    assert provider.max_detections == 20

    supported = provider.get_supported_tasks()
    assert TaskType.VISION_DETECTION in supported
    assert TaskType.VISION_FRAME in supported

    await provider.shutdown()


@pytest.mark.asyncio
async def test_vision_provider_detection():
    """Test VisionProvider object detection."""
    provider = VisionProvider()
    await provider.initialize()

    task = TaskEnvelope(
        task_id="detect-1",
        task_type=TaskType.VISION_DETECTION,
        payload={
            "image_data": "dGVzdCBpbWFnZSBkYXRh",  # Valid base64: "test image data"
            "format": "jpeg",
            "width": 640,
            "height": 480,
        },
    )

    result = await provider.process_task(task)

    assert result.task_id == "detect-1"
    assert result.status == TaskStatus.COMPLETED
    assert "detections" in result.result
    assert "num_detections" in result.result
    assert result.processing_time_ms is not None

    await provider.shutdown()


@pytest.mark.asyncio
async def test_vision_provider_frame():
    """Test VisionProvider frame processing."""
    provider = VisionProvider()
    await provider.initialize()

    task = TaskEnvelope(
        task_id="frame-1",
        task_type=TaskType.VISION_FRAME,
        payload={
            "frame_data": "dGVzdCBmcmFtZSBkYXRh",  # Valid base64: "test frame data"
            "frame_id": 123,
            "timestamp": 1234567890.0,
        },
    )

    result = await provider.process_task(task)

    assert result.task_id == "frame-1"
    assert result.status == TaskStatus.COMPLETED
    assert "obstacles" in result.result
    assert "frame_id" in result.result
    assert result.processing_time_ms is not None

    await provider.shutdown()


@pytest.mark.asyncio
async def test_vision_provider_missing_payload():
    """Test VisionProvider with missing payload data."""
    provider = VisionProvider()
    await provider.initialize()

    task = TaskEnvelope(
        task_id="detect-bad",
        task_type=TaskType.VISION_DETECTION,
        payload={},  # Missing image_data
    )

    result = await provider.process_task(task)

    assert result.task_id == "detect-bad"
    assert result.status == TaskStatus.FAILED
    assert "Missing image_data" in result.error

    await provider.shutdown()


@pytest.mark.asyncio
async def test_text_provider_initialization():
    """Test TextProvider initialization."""
    config = {"model": "test_llm", "max_tokens": 1024, "temperature": 0.8, "use_cache": True}

    provider = TextProvider(config)
    await provider.initialize()

    assert provider.model == "test_llm"
    assert provider.max_tokens == 1024
    assert provider.temperature == 0.8
    assert provider.use_cache is True

    supported = provider.get_supported_tasks()
    assert TaskType.TEXT_GENERATE in supported
    assert TaskType.TEXT_NLU in supported

    await provider.shutdown()


@pytest.mark.asyncio
async def test_text_provider_generate():
    """Test TextProvider text generation."""
    provider = TextProvider()
    await provider.initialize()

    task = TaskEnvelope(
        task_id="gen-1",
        task_type=TaskType.TEXT_GENERATE,
        payload={"prompt": "What is the weather?", "max_tokens": 100, "temperature": 0.7},
    )

    result = await provider.process_task(task)

    assert result.task_id == "gen-1"
    assert result.status == TaskStatus.COMPLETED
    assert "text" in result.result
    assert "tokens_used" in result.result
    assert result.processing_time_ms is not None

    await provider.shutdown()


@pytest.mark.asyncio
async def test_text_provider_nlu():
    """Test TextProvider NLU processing."""
    provider = TextProvider()
    await provider.initialize()

    task = TaskEnvelope(
        task_id="nlu-1",
        task_type=TaskType.TEXT_NLU,
        payload={"text": "Go to the kitchen", "tasks": ["intent", "entities"]},
    )

    result = await provider.process_task(task)

    assert result.task_id == "nlu-1"
    assert result.status == TaskStatus.COMPLETED
    assert "intent" in result.result
    assert "entities" in result.result
    assert result.processing_time_ms is not None

    await provider.shutdown()


@pytest.mark.asyncio
async def test_text_provider_caching():
    """Test TextProvider response caching."""
    provider = TextProvider({"use_cache": True})
    await provider.initialize()

    task = TaskEnvelope(
        task_id="gen-cache-1",
        task_type=TaskType.TEXT_GENERATE,
        payload={"prompt": "Test prompt", "max_tokens": 100, "temperature": 0.7},
    )

    # First call - not from cache
    result1 = await provider.process_task(task)
    assert result1.result["from_cache"] is False

    # Second call with same parameters - from cache
    task.task_id = "gen-cache-2"
    result2 = await provider.process_task(task)
    assert result2.result["from_cache"] is True
    assert result2.result["text"] == result1.result["text"]

    await provider.shutdown()


@pytest.mark.asyncio
async def test_text_provider_missing_payload():
    """Test TextProvider with missing payload data."""
    provider = TextProvider()
    await provider.initialize()

    task = TaskEnvelope(
        task_id="gen-bad",
        task_type=TaskType.TEXT_GENERATE,
        payload={},  # Missing prompt
    )

    result = await provider.process_task(task)

    assert result.task_id == "gen-bad"
    assert result.status == TaskStatus.FAILED
    assert "Missing prompt" in result.error

    await provider.shutdown()


@pytest.mark.asyncio
async def test_provider_telemetry():
    """Test provider telemetry."""
    voice_provider = VoiceProvider({"asr_model": "test"})
    await voice_provider.initialize()

    telemetry = voice_provider.get_telemetry()
    assert telemetry["provider"] == "VoiceProvider"
    assert telemetry["initialized"] is True
    assert "asr_model" in telemetry
    assert len(telemetry["supported_tasks"]) > 0

    await voice_provider.shutdown()


@pytest.mark.asyncio
async def test_gemini_provider_mock_mode():
    """Test GeminiProvider in mock mode."""
    from pc_client.providers.gemini_provider import GeminiProvider

    provider = GeminiProvider(
        api_key=None,
        model="gemini-2.0-flash",
        use_mock=True,
    )

    response = await provider.generate(
        prompt="What is the weather?",
        system_prompt="You are a helpful assistant.",
        max_tokens=100,
        temperature=0.7,
    )

    assert response.text is not None
    assert "[MOCK GEMINI]" in response.text
    assert response.provider == "gemini"
    assert response.model == "mock-gemini-2.0-flash"
    assert response.error is None

    await provider.close()


@pytest.mark.asyncio
async def test_chatgpt_provider_mock_mode():
    """Test ChatGPTProvider in mock mode."""
    from pc_client.providers.chatgpt_provider import ChatGPTProvider

    provider = ChatGPTProvider(
        api_key=None,
        model="gpt-4o-mini",
        use_mock=True,
    )

    response = await provider.generate(
        prompt="What is the weather?",
        system_prompt="You are a helpful assistant.",
        max_tokens=100,
        temperature=0.7,
    )

    assert response.text is not None
    assert "[MOCK CHATGPT]" in response.text
    assert response.provider == "chatgpt"
    assert response.model == "mock-gpt-4o-mini"
    assert response.error is None

    await provider.close()


@pytest.mark.asyncio
async def test_gemini_provider_status():
    """Test GeminiProvider status reporting."""
    from pc_client.providers.gemini_provider import GeminiProvider

    provider = GeminiProvider(
        api_key="test_key",
        model="gemini-2.0-flash",
        use_mock=True,
    )

    status = provider.get_status()

    assert status["provider"] == "gemini"
    assert status["model"] == "gemini-2.0-flash"
    assert status["use_mock"] is True
    assert status["has_api_key"] is True

    await provider.close()


@pytest.mark.asyncio
async def test_chatgpt_provider_status():
    """Test ChatGPTProvider status reporting."""
    from pc_client.providers.chatgpt_provider import ChatGPTProvider

    provider = ChatGPTProvider(
        api_key="test_key",
        model="gpt-4o-mini",
        use_mock=True,
    )

    status = provider.get_status()

    assert status["provider"] == "chatgpt"
    assert status["model"] == "gpt-4o-mini"
    assert status["use_mock"] is True
    assert status["has_api_key"] is True
    assert status["is_reasoning_model"] is False

    await provider.close()


@pytest.mark.asyncio
async def test_chatgpt_provider_reasoning_model():
    """Test ChatGPTProvider with reasoning model detection."""
    from pc_client.providers.chatgpt_provider import ChatGPTProvider

    provider = ChatGPTProvider(
        api_key="test_key",
        model="o1-preview",
        use_mock=True,
    )

    status = provider.get_status()
    assert status["is_reasoning_model"] is True

    await provider.close()


@pytest.mark.asyncio
async def test_text_provider_with_external_backends():
    """Test TextProvider with external backends in mock mode."""
    config = {
        "model": "test_llm",
        "use_mock": True,
        "backend": "auto",
        "gemini_api_key": "test_gemini_key",
        "gemini_model": "gemini-2.0-flash",
        "openai_api_key": "test_openai_key",
        "openai_model": "gpt-4o-mini",
    }

    provider = TextProvider(config)
    await provider.initialize()

    telemetry = provider.get_telemetry()
    assert telemetry["backend"] == "auto"
    assert "gemini_configured" in telemetry
    assert "chatgpt_configured" in telemetry

    # Test generation with default (auto) backend
    task = TaskEnvelope(
        task_id="gen-external-1",
        task_type=TaskType.TEXT_GENERATE,
        payload={"prompt": "What is the weather?"},
    )

    result = await provider.process_task(task)
    assert result.status == TaskStatus.COMPLETED
    assert "text" in result.result
    assert "backend" in result.result

    await provider.shutdown()


@pytest.mark.asyncio
async def test_text_provider_backend_override():
    """Test TextProvider with per-request backend override."""
    config = {
        "model": "test_llm",
        "use_mock": True,
        "backend": "local",
        "gemini_api_key": "test_key",
        "openai_api_key": "test_key",
    }

    provider = TextProvider(config)
    await provider.initialize()

    # Request with gemini backend override
    task = TaskEnvelope(
        task_id="gen-gemini-1",
        task_type=TaskType.TEXT_GENERATE,
        payload={
            "prompt": "Test with gemini",
            "backend": "gemini",
        },
    )

    result = await provider.process_task(task)
    assert result.status == TaskStatus.COMPLETED
    assert result.result.get("backend") == "gemini"

    await provider.shutdown()


@pytest.mark.asyncio
async def test_text_provider_external_status():
    """Test TextProvider external providers status."""
    config = {
        "use_mock": True,
        "gemini_api_key": "test_key",
        "openai_api_key": "test_key",
    }

    provider = TextProvider(config)
    await provider.initialize()

    external_status = provider.get_external_providers_status()

    assert "gemini" in external_status
    assert "chatgpt" in external_status
    assert "active_backend" in external_status
    assert "available_backends" in external_status

    await provider.shutdown()
