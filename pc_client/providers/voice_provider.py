"""ASR/TTS: wybrane domeny, lokalne modele i jawny tryb demo."""

import base64
import importlib
import io
import math
import os
import tempfile
import wave
from pathlib import Path
from typing import Any, Dict, Optional

from pc_client.providers.base import BaseProvider, TaskEnvelope, TaskResult, TaskType, TaskStatus
from pc_client.telemetry.metrics import tasks_processed_total


class VoiceProvider(BaseProvider):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("VoiceProvider", config)
        self.asr_model_name = self.config.get("asr_model", "base")
        self.tts_model_name = self.config.get("tts_model", "en_US-lessac-medium")
        self.sample_rate = self.config.get("sample_rate", 16000)
        self.use_mock = self.config.get("use_mock") is True
        selected = self.config.get("domains", self.config.get("domain", "voice"))
        if isinstance(selected, str):
            selected = ["asr", "tts"] if selected == "voice" else [selected]
        if not isinstance(selected, list) or not selected or any(item not in {"asr", "tts"} for item in selected):
            raise ValueError("voice domain/domains must select asr, tts or voice")
        self.domains = set(selected)
        self.asr_model = None
        self.tts_model = None
        self.tts_available = False
        self.capabilities = {
            domain: {
                "selected": domain in self.domains,
                "ready": False,
                "error": None,
                "mode": "demo" if self.use_mock else "real",
            }
            for domain in ("asr", "tts")
        }

    def _asr_path(self) -> Path:
        configured = self.config.get("asr_model_path")
        if configured:
            return Path(configured).expanduser()
        name = Path(str(self.asr_model_name)).expanduser()
        if name.is_file():
            return name
        cache = Path(self.config.get("asr_cache_dir") or os.getenv("XDG_CACHE_HOME", str(Path.home() / ".cache")))
        return cache / "whisper" / f"{self.asr_model_name}.pt"

    def _load_domain(self, domain: str) -> None:
        backend = self.config.get(f"{domain}_backend", "local")
        allowed = {"local", "whisper"} if domain == "asr" else {"local", "piper"}
        if backend not in allowed:
            raise RuntimeError(f"Configured {domain} backend unavailable: {backend}")
        if domain == "asr":
            model_path = self._asr_path()
            if not model_path.is_file():
                raise RuntimeError("Whisper cached model unavailable; configure asr_model_path (no download)")
            backend = importlib.import_module("whisper")
            self.asr_model = backend.load_model(str(model_path))
            if self.asr_model is None or not callable(getattr(self.asr_model, "transcribe", None)):
                raise RuntimeError("Whisper model not usable")
        else:
            configured = self.config.get("tts_model_path", self.tts_model_name)
            model_path = Path(str(configured)).expanduser()
            config_path = Path(str(model_path) + ".json")
            if not model_path.is_file() or not config_path.is_file():
                raise RuntimeError("Piper local model/JSON unavailable; configure tts_model_path")
            backend = importlib.import_module("piper.voice")
            self.tts_model = backend.PiperVoice.load(str(model_path), str(config_path))
            if not any(callable(getattr(self.tts_model, method, None)) for method in ("synthesize", "synthesize_wav")):
                raise RuntimeError("Piper model not usable")
            self.tts_available = True

    async def _initialize_impl(self) -> None:
        for domain in sorted(self.domains):
            try:
                if not self.use_mock:
                    self._load_domain(domain)
                self.capabilities[domain].update(ready=True, error=None)
            except Exception as exc:
                self.capabilities[domain].update(ready=False, error=str(exc))
        if not any(self.capabilities[domain]["ready"] for domain in self.domains):
            raise RuntimeError(
                "; ".join(f"{domain}: {self.capabilities[domain]['error']}" for domain in sorted(self.domains))
            )

    async def _shutdown_impl(self) -> None:
        self.asr_model = self.tts_model = None
        self.tts_available = False
        for value in self.capabilities.values():
            value["ready"] = False

    def _failed(self, task: TaskEnvelope, domain: str, error: str) -> TaskResult:
        return TaskResult(
            task_id=task.task_id,
            status=TaskStatus.FAILED,
            error=error,
            meta={"domain": domain, "engine": "mock" if self.use_mock else domain, "simulated": self.use_mock},
        )

    async def _process_task_impl(self, task: TaskEnvelope) -> TaskResult:
        domain = {TaskType.VOICE_ASR: "asr", TaskType.VOICE_TTS: "tts"}.get(task.task_type)
        if domain is None:
            return self._failed(task, "unknown", f"Unsupported task type: {task.task_type}")
        if not self.capabilities[domain]["ready"]:
            return self._failed(task, domain, self.capabilities[domain]["error"] or "Voice domain inactive")
        try:
            result = await (self._process_asr(task) if domain == "asr" else self._process_tts(task))
            if result.status == TaskStatus.COMPLETED:
                tasks_processed_total.labels(
                    provider="VoiceProvider", task_type=task.task_type.value, status="completed"
                ).inc()
            return result
        except Exception as exc:
            # Błąd wykonania nie może zostać zastąpiony udanym wynikiem demo.
            self.capabilities[domain].update(ready=False, error=str(exc))
            return self._failed(task, domain, str(exc))

    async def _process_asr(self, task: TaskEnvelope) -> TaskResult:
        audio_data = task.payload.get("audio_data")
        if not audio_data:
            return self._failed(task, "asr", "Missing audio_data in payload")
        audio_format = task.payload.get("format", "wav")
        if audio_format not in {"wav", "raw", "mp3", "flac", "ogg"}:
            return self._failed(task, "asr", "Unsupported audio format")
        if self.use_mock:
            result = {"text": "Mock transcription: Hello from voice provider", "confidence": 0.95, "language": "en"}
        else:
            audio_bytes = base64.b64decode(audio_data, validate=True)
            if not audio_bytes:
                raise ValueError("Audio data is empty")
            if self.asr_model is None:
                raise RuntimeError("Whisper backend unavailable")
            with tempfile.NamedTemporaryFile(suffix=f".{audio_format}", delete=False) as temp:
                temp.write(audio_bytes)
                temp_path = Path(temp.name)
            try:
                observed = self.asr_model.transcribe(str(temp_path))
                result = {"text": observed["text"].strip(), "language": observed.get("language", "en")}
            finally:
                temp_path.unlink(missing_ok=True)
        return TaskResult(
            task_id=task.task_id,
            status=TaskStatus.COMPLETED,
            result=result,
            meta={
                "model": "mock" if self.use_mock else self.asr_model_name,
                "sample_rate": task.payload.get("sample_rate", self.sample_rate),
                "format": audio_format,
                "engine": "mock" if self.use_mock else "whisper",
                "simulated": self.use_mock,
            },
        )

    async def _process_tts(self, task: TaskEnvelope) -> TaskResult:
        text = task.payload.get("text")
        if not isinstance(text, str) or not text.strip():
            return self._failed(task, "tts", "Missing text in payload")
        if len(text) > 5000:
            return self._failed(task, "tts", "Text too long (max 5000 chars)")
        requested = task.payload.get("provider", task.payload.get("backend", "local"))
        if requested not in {"local", "piper"}:
            return self._failed(task, "tts", f"Requested TTS backend unavailable: {requested}")
        speed = task.payload.get("speed")
        if speed is None:
            speed = 1.0
        if (
            isinstance(speed, bool)
            or not isinstance(speed, (int, float))
            or not math.isfinite(speed)
            or not 0.1 <= speed <= 4
        ):
            return self._failed(task, "tts", "Invalid speech speed")
        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            if self.use_mock:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(self.sample_rate)
                wav.writeframes(bytes(self.sample_rate * 2))
            else:
                if self.tts_model is None:
                    raise RuntimeError("Piper backend unavailable")
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(
                    getattr(getattr(self.tts_model, "config", None), "sample_rate", None) or self.sample_rate
                )
                if callable(getattr(self.tts_model, "synthesize_wav", None)):
                    if speed != 1:
                        return self._failed(task, "tts", "This Piper backend does not expose speech speed")
                    self.tts_model.synthesize_wav(text, wav)
                else:
                    self.tts_model.synthesize(text, wav, length_scale=1.0 / speed)
        audio = output.getvalue()
        with wave.open(io.BytesIO(audio), "rb") as wav:
            rate = wav.getframerate()
            frames = wav.getnframes()
            if rate <= 0 or frames <= 0:
                raise RuntimeError("Piper returned empty audio")
        return TaskResult(
            task_id=task.task_id,
            status=TaskStatus.COMPLETED,
            result={
                "audio_data": base64.b64encode(audio).decode("ascii"),
                "format": "wav",
                "sample_rate": rate,
                "duration_ms": int(frames / rate * 1000),
            },
            meta={
                "model": "mock" if self.use_mock else self.tts_model_name,
                "voice": "mock" if self.use_mock else self.tts_model_name,
                "requested_voice": task.payload.get("voice", "default"),
                "speed": speed,
                "engine": "mock" if self.use_mock else "piper",
                "simulated": self.use_mock,
            },
        )

    def get_supported_tasks(self) -> list[TaskType]:
        return [
            kind
            for kind, domain in ((TaskType.VOICE_ASR, "asr"), (TaskType.VOICE_TTS, "tts"))
            if self.capabilities[domain]["ready"]
        ]

    def get_telemetry(self) -> Dict[str, Any]:
        return {
            **super().get_telemetry(),
            "asr_model": self.asr_model_name,
            "tts_model": self.tts_model_name,
            "sample_rate": self.sample_rate,
            "asr_available": self.capabilities["asr"]["ready"],
            "tts_available": self.capabilities["tts"]["ready"],
            "domains": sorted(self.domains),
            "capabilities": {key: dict(value) for key, value in self.capabilities.items()},
            "ready": all(self.capabilities[domain]["ready"] for domain in self.domains),
            "error": "; ".join(value["error"] for value in self.capabilities.values() if value["error"]) or None,
            "mode": "mock" if self.use_mock else "real",
            "source": "demo" if self.use_mock else "pc",
        }
