"""Izolowane regresje: leniwe domeny i brak pozornych sukcesów AI."""

import asyncio
import base64
import importlib
import io
import json
import subprocess
import sys
import wave
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from pc_client.api import lifecycle
from pc_client.api.config_utils import get_provider_capabilities
from pc_client.api.routers import voice_router
from pc_client.config import Settings
from pc_client.providers.base import TaskEnvelope, TaskStatus, TaskType
from pc_client.providers.voice_provider import VoiceProvider


def test_disabled_application_imports_no_ai_domain():
    code = """
import json, sys
from pc_client.api.server import create_app
from pc_client.providers.base import TaskType
roots = {'numpy', 'torch', 'whisper', 'ultralytics', 'mediapipe', 'ollama', 'piper'}
print(json.dumps(sorted(name for name in sys.modules if name.split('.')[0] in roots)))
"""
    child = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert json.loads(child.stdout.strip().splitlines()[-1]) == []


@pytest.mark.asyncio
async def test_explicit_voice_demo_imports_no_backend(monkeypatch):
    monkeypatch.setattr(importlib, "import_module", lambda name: pytest.fail(f"unselected import {name}"))
    provider = VoiceProvider({"use_mock": True})
    await provider.initialize()
    assert provider.get_telemetry()["source"] == "demo"
    assert provider.get_telemetry()["ready"] is True
    result = await provider.process_task(TaskEnvelope("demo", TaskType.VOICE_TTS, {"text": "hello"}))
    assert result.status == TaskStatus.COMPLETED
    assert result.meta["simulated"] is True
    with wave.open(io.BytesIO(base64.b64decode(result.result["audio_data"])), "rb") as audio:
        assert audio.getnframes() > 0


@pytest.mark.asyncio
@pytest.mark.parametrize("domain", ["asr", "tts"])
async def test_real_missing_assets_do_not_download_or_enable_mock(domain, tmp_path, monkeypatch):
    monkeypatch.setattr(importlib, "import_module", lambda name: pytest.fail(f"download/import {name}"))
    provider = VoiceProvider({"domain": domain, f"{domain}_model_path": str(tmp_path / "missing")})
    with pytest.raises(RuntimeError, match="unavailable"):
        await provider.initialize()
    telemetry = provider.get_telemetry()
    assert telemetry["initialized"] is False
    assert telemetry["mode"] == "real"
    assert telemetry["ready"] is False
    assert telemetry["capabilities"][domain]["error"]


def local_assets(tmp_path):
    asr = tmp_path / "whisper.pt"
    asr.write_bytes(b"fake")
    tts = tmp_path / "piper.onnx"
    tts.write_bytes(b"fake")
    (tmp_path / "piper.onnx.json").write_text("{}")
    return {"asr_model_path": str(asr), "tts_model_path": str(tts)}


class FakePiper:
    def synthesize(self, text, audio, length_scale=1):
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(bytes(320))


@pytest.mark.asyncio
async def test_tts_only_loads_selected_model_without_whisper(tmp_path, monkeypatch):
    assets = local_assets(tmp_path)
    calls = []

    def load(model, config):
        calls.append((model, config))
        return FakePiper()

    def selected_import(name):
        assert name == "piper.voice"
        return SimpleNamespace(PiperVoice=SimpleNamespace(load=load))

    monkeypatch.setattr(importlib, "import_module", selected_import)
    provider = VoiceProvider({**assets, "domain": "tts"})
    await provider.initialize()
    assert provider.get_supported_tasks() == [TaskType.VOICE_TTS]
    assert calls == [(assets["tts_model_path"], assets["tts_model_path"] + ".json")]
    result = await provider.process_task(TaskEnvelope("tts", TaskType.VOICE_TTS, {"text": "hello"}))
    assert result.status == TaskStatus.COMPLETED and result.meta["engine"] == "piper"
    assert provider.get_telemetry()["asr_available"] is False
    denied = await provider.process_task(TaskEnvelope("asr", TaskType.VOICE_ASR, {"audio_data": "eA=="}))
    assert denied.status == TaskStatus.FAILED


@pytest.mark.asyncio
async def test_asr_only_loads_local_file_without_piper(tmp_path, monkeypatch):
    assets = local_assets(tmp_path)
    calls = []
    model = SimpleNamespace(transcribe=lambda path: {"text": "real answer", "language": "pl"})

    def selected_import(name):
        assert name == "whisper"
        return SimpleNamespace(load_model=lambda path: calls.append(path) or model)

    monkeypatch.setattr(importlib, "import_module", selected_import)
    provider = VoiceProvider({**assets, "domain": "asr"})
    await provider.initialize()
    assert calls == [assets["asr_model_path"]]
    result = await provider.process_task(TaskEnvelope("asr", TaskType.VOICE_ASR, {"audio_data": "eA=="}))
    assert result.status == TaskStatus.COMPLETED and result.meta["engine"] == "whisper"
    assert result.result["text"] == "real answer"
    assert provider.get_telemetry()["tts_available"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("domain", ["asr", "tts"])
async def test_corrupt_selected_model_is_not_ready(domain, tmp_path, monkeypatch):
    assets = local_assets(tmp_path)

    def broken(*args):
        raise ValueError("corrupt local model")

    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda name: SimpleNamespace(load_model=broken, PiperVoice=SimpleNamespace(load=broken)),
    )
    provider = VoiceProvider({**assets, "domain": domain})
    with pytest.raises(RuntimeError, match="corrupt local model"):
        await provider.initialize()
    assert provider.get_telemetry()[f"{domain}_available"] is False


@pytest.mark.asyncio
async def test_partial_voice_keeps_only_working_domain(tmp_path, monkeypatch):
    assets = local_assets(tmp_path)

    def broken(*args):
        raise ValueError("corrupt ASR")

    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda name: SimpleNamespace(load_model=broken)
        if name == "whisper"
        else SimpleNamespace(PiperVoice=SimpleNamespace(load=lambda *args: FakePiper())),
    )
    provider = VoiceProvider(assets)
    await provider.initialize()
    assert provider.get_telemetry()["initialized"] is True
    assert provider.get_telemetry()["ready"] is False
    assert provider.get_supported_tasks() == [TaskType.VOICE_TTS]


@pytest.mark.asyncio
@pytest.mark.parametrize("domain", ["asr", "tts"])
async def test_real_inference_failure_returns_failed_without_mock(domain, monkeypatch):
    provider = VoiceProvider({"domain": domain})
    provider._initialized = True
    provider.capabilities[domain]["ready"] = True

    def broken(*args, **kwargs):
        raise RuntimeError("inference failed")

    provider.asr_model = SimpleNamespace(transcribe=broken)
    provider.tts_model = SimpleNamespace(synthesize=broken)
    kind = TaskType.VOICE_ASR if domain == "asr" else TaskType.VOICE_TTS
    result = await provider.process_task(TaskEnvelope("fail", kind, {"audio_data": "eA==", "text": "hello"}))
    assert result.status == TaskStatus.FAILED
    assert result.result is None
    assert result.meta["simulated"] is False
    assert provider.get_telemetry()[f"{domain}_available"] is False


@pytest.mark.asyncio
async def test_lifecycle_real_voice_failure_does_not_create_worker_or_demo(tmp_path, monkeypatch):
    app = FastAPI()
    app.state.settings = Settings(
        enable_providers=True, enable_task_queue=True, enable_voice_offload=True, voice_model="real"
    )
    app.state.providers = {}
    app.state.voice_offload_enabled = False
    monkeypatch.setattr(
        lifecycle, "load_provider_config", lambda *args: {"domain": "asr", "asr_model_path": str(tmp_path / "missing")}
    )
    queue = AsyncMock()
    monkeypatch.setattr(lifecycle, "ensure_task_queue", queue)
    await lifecycle.initialize_voice_pipeline(app)
    queue.assert_not_called()
    assert app.state.providers == {}
    assert app.state.voice_offload_enabled is False
    assert app.state.voice_provider_status["initialized"] is False
    assert app.state.voice_provider_status["error"]


@pytest.mark.asyncio
async def test_real_text_backend_error_does_not_generate_mock(monkeypatch):
    from pc_client.providers.text_provider import TextProvider

    provider = TextProvider()

    def missing(name):
        assert name == "ollama"
        raise ImportError("missing selected backend")

    monkeypatch.setattr(importlib, "import_module", missing)
    with pytest.raises(RuntimeError, match="backend unavailable"):
        await provider.initialize()
    provider._initialized = True
    result = await provider.process_task(TaskEnvelope("text", TaskType.TEXT_GENERATE, {"prompt": "hello"}))
    assert result.status == TaskStatus.FAILED
    assert result.result is None
    assert provider.get_telemetry()["ready"] is False
    nlu = await provider.process_task(TaskEnvelope("nlu", TaskType.TEXT_NLU, {"text": "hello"}))
    assert nlu.status == TaskStatus.FAILED


@pytest.mark.asyncio
async def test_local_text_checks_model_without_other_backends(monkeypatch):
    from pc_client.providers.text_provider import TextProvider

    calls = []
    client = SimpleNamespace(
        list=lambda: calls.append("list"),
        show=lambda model: calls.append(model),
        chat=lambda **kwargs: {"message": {"content": "actual answer"}},
    )

    def selected_import(name):
        assert name == "ollama"
        return SimpleNamespace(Client=lambda **kwargs: client)

    monkeypatch.setattr(importlib, "import_module", selected_import)
    provider = TextProvider({"model": "existing", "enable_mcp_tools": False})
    await provider.initialize()
    assert calls == ["list", "existing"]
    assert provider._gemini_provider is provider._chatgpt_provider is None
    result = await provider.process_task(TaskEnvelope("text", TaskType.TEXT_GENERATE, {"prompt": "hello"}))
    assert result.result["text"] == "actual answer"
    assert result.meta["simulated"] is False


@pytest.mark.asyncio
async def test_vision_requires_existing_weights_before_import_or_download(tmp_path, monkeypatch):
    from pc_client.providers.vision_provider import VisionProvider

    monkeypatch.setattr(importlib, "import_module", lambda name: pytest.fail(f"unexpected import {name}"))
    provider = VisionProvider({"detection_model_path": str(tmp_path / "missing.pt")})
    with pytest.raises(RuntimeError, match="no download"):
        await provider.initialize()
    assert provider.get_telemetry()["initialized"] is False
    assert provider.get_telemetry()["mode"] == "real"


@pytest.mark.asyncio
async def test_vision_real_inference_failure_is_not_mock():
    from pc_client.providers.vision_provider import VisionProvider
    from PIL import Image

    encoded = io.BytesIO()
    Image.new("RGB", (10, 10)).save(encoded, format="PNG")
    provider = VisionProvider()

    def broken(*args, **kwargs):
        raise RuntimeError("detector failed")

    provider.detector = broken
    provider._initialized = True
    result = await provider.process_task(
        TaskEnvelope("vision", TaskType.VISION_DETECTION, {"image_data": base64.b64encode(encoded.getvalue()).decode()})
    )
    assert result.status == TaskStatus.FAILED and result.result is None
    assert provider.get_telemetry()["ready"] is False


@pytest.mark.asyncio
async def test_voice_http_real_failure_returns_error_not_silence():
    app = FastAPI()
    app.include_router(voice_router.router)
    provider = VoiceProvider({"domain": "tts"})
    provider._initialized = True
    app.state.providers = {"voice": provider}
    app.state.rest_adapter = None
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture") as client:
        result = await client.post("/api/voice/tts", json={"text": "hello"})
    assert result.status_code == 503
    assert result.headers["content-type"].startswith("application/json")
    assert result.json()["ok"] is False


@pytest.mark.asyncio
async def test_tts_proxy_does_not_accept_remote_fallback_audio():
    from pc_client.adapters.rest_adapter import RestAdapter

    adapter = RestAdapter("http://fixture")
    await adapter.client.aclose()
    adapter.client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, content=b"fake", headers={"X-Voice-Fallback": "mock", "content-type": "audio/wav"}
            )
        )
    )
    try:
        with pytest.raises(RuntimeError, match="fallback"):
            await adapter.post_voice_tts({"text": "hello"})
    finally:
        await adapter.client.aclose()


def test_capabilities_require_observed_initialized_backend():
    payload = get_provider_capabilities(Settings(enable_voice_offload=True))
    assert payload["voice"]["requested"] is True
    assert payload["voice"]["ready"] is False and payload["voice"]["features"] == []
    assert payload["vision"]["source"] == "unknown"


@pytest.mark.asyncio
async def test_passive_status_sync_never_changes_lcd():
    app = FastAPI()
    adapter = MagicMock()
    for name in (
        "get_healthz",
        "get_state",
        "get_sysinfo",
        "get_vision_snap_info",
        "get_vision_obstacle",
        "get_app_metrics",
        "get_camera_resource",
        "get_bus_health",
    ):
        setattr(adapter, name, AsyncMock(return_value={"lcd": {"on": True}}))
    adapter.get_resource = AsyncMock(return_value={"free": True})
    adapter.post_resource_action = AsyncMock(side_effect=AssertionError("passive mutation"))
    app.state.rest_adapter = adapter
    app.state.cache = MagicMock()
    app.state.control_state = {}
    from unittest.mock import patch

    with patch.object(lifecycle.asyncio, "sleep", AsyncMock(side_effect=asyncio.CancelledError)):
        with pytest.raises(asyncio.CancelledError):
            await lifecycle.sync_data_periodically(app)
    adapter.post_resource_action.assert_not_called()
    assert app.state.cache.set.call_count == 9


@pytest.mark.asyncio
@pytest.mark.parametrize("domain", ["asr", "tts"])
async def test_unknown_configured_voice_backend_is_not_silently_local(domain, tmp_path, monkeypatch):
    monkeypatch.setattr(importlib, "import_module", lambda name: pytest.fail(f"wrong backend import {name}"))
    provider = VoiceProvider({"domain": domain, f"{domain}_backend": "unknown", **local_assets(tmp_path)})
    with pytest.raises(RuntimeError, match="Configured"):
        await provider.initialize()
    assert provider.get_telemetry()[f"{domain}_available"] is False


@pytest.mark.asyncio
async def test_tts_does_not_claim_cloud_provider_for_local_audio():
    provider = VoiceProvider({"domain": "tts", "use_mock": True})
    await provider.initialize()
    result = await provider.process_task(
        TaskEnvelope("unsupported", TaskType.VOICE_TTS, {"text": "hello", "provider": "openai"})
    )
    assert result.status == TaskStatus.FAILED
    assert result.result is None


@pytest.mark.asyncio
async def test_nondefault_text_backend_failure_does_not_poison_default():
    from pc_client.providers.text_provider import TextProvider

    provider = TextProvider({"backend": "local", "enable_mcp_tools": False})
    provider._initialized = True
    provider.ollama_available = True
    provider._generate_single_backend = AsyncMock(side_effect=RuntimeError("cloud unavailable"))
    with pytest.raises(RuntimeError, match="gemini"):
        await provider._generate_with_backend("hello", "", 10, 0.1, "gemini")
    assert provider.get_telemetry()["ready"] is True
    assert provider.get_telemetry()["error"] is None
    with pytest.raises(RuntimeError, match="local"):
        await provider._generate_with_backend("hello", "", 10, 0.1, "local")
    error = provider.get_telemetry()["error"]
    assert error and provider.get_telemetry()["ready"] is False
    provider._generate_single_backend = AsyncMock(return_value=("cloud answer", None))
    await provider._generate_with_backend("hello", "", 10, 0.1, "gemini")
    assert provider.get_telemetry()["error"] == error
    assert provider.get_telemetry()["ready"] is False
    provider.set_default_backend("local")
    assert provider.get_telemetry()["ready"] is False  # Selecting the failed backend is not recovery.
    assert provider.get_telemetry()["error"] == error
    provider._gemini_provider = SimpleNamespace(is_available=True, is_configured=True)
    provider.set_default_backend("gemini")
    assert provider.get_telemetry()["ready"] is True
    assert provider.get_telemetry()["error"] is None


def test_actual_capability_cannot_be_ready_when_initialization_is_unknown():
    fake = SimpleNamespace(get_telemetry=lambda: {"ready": True, "initialized": False, "source": "pc"})
    result = get_provider_capabilities(Settings(test_mode=True), providers={"vision": fake}, text_provider=fake)
    assert result["text"]["initialized"] is result["text"]["ready"] is False
    assert result["vision"]["initialized"] is result["vision"]["ready"] is False
    assert result["text"]["features"] == result["vision"]["features"] == []
