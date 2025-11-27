"""Model Manager for AI model inventory and configuration."""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    """Information about a detected model file."""

    name: str
    path: str
    type: str  # 'yolo', 'whisper', 'piper', 'llm', 'unknown'
    category: str  # 'vision', 'voice_asr', 'voice_tts', 'text'
    size_mb: float = 0.0
    format: str = ""  # 'pt', 'onnx', 'tflite', 'gguf'

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "path": self.path,
            "type": self.type,
            "category": self.category,
            "size_mb": round(self.size_mb, 2),
            "format": self.format,
        }


@dataclass
class ActiveModels:
    """Currently active model configuration."""

    vision: Dict[str, Any] = field(default_factory=dict)
    voice_asr: Dict[str, Any] = field(default_factory=dict)
    voice_tts: Dict[str, Any] = field(default_factory=dict)
    text: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "vision": self.vision,
            "voice_asr": self.voice_asr,
            "voice_tts": self.voice_tts,
            "text": self.text,
        }


class ModelManager:
    """
    Manager for AI model inventory and configuration.

    Responsible for:
    - Scanning local directories for model files
    - Reading active model configuration from providers.toml
    - Optionally querying Ollama for available LLM models
    """

    # Supported model file extensions
    MODEL_EXTENSIONS = {".pt", ".onnx", ".tflite", ".gguf", ".bin"}

    # Category detection patterns
    CATEGORY_PATTERNS = {
        "vision": ["yolo", "detection", "vision", "mediapipe"],
        "voice_asr": ["whisper", "asr", "stt", "speech-to-text"],
        "voice_tts": ["piper", "tts", "text-to-speech", "voice"],
        "text": ["llama", "gpt", "mistral", "phi", "gemma", "qwen"],
    }

    def __init__(
        self,
        models_dir: Optional[str] = None,
        providers_config_path: Optional[str] = None,
    ):
        """
        Initialize the Model Manager.

        Args:
            models_dir: Path to the models directory (default: data/models)
            providers_config_path: Path to providers.toml (default: config/providers.toml)
        """
        self.models_dir = Path(models_dir) if models_dir else Path("data/models")
        self.providers_config_path = (
            Path(providers_config_path) if providers_config_path else Path("config/providers.toml")
        )
        self._installed_models: List[ModelInfo] = []
        self._active_models: Optional[ActiveModels] = None
        self._ollama_models: List[Dict[str, Any]] = []
        self._providers_config: Dict[str, Any] = {}
        self._slot_field_map: Dict[str, tuple[str, str]] = {
            "vision": ("vision", "detection_model"),
            "voice_asr": ("voice", "asr_model"),
            "voice_tts": ("voice", "tts_model"),
            "text": ("text", "model"),
        }

    def scan_local_models(self) -> List[ModelInfo]:
        """
        Scan the models directory for installed model files.

        Returns:
            List of detected ModelInfo objects
        """
        self._installed_models = []

        if not self.models_dir.exists():
            logger.warning("Models directory does not exist: %s", self.models_dir)
            return self._installed_models

        for root, _, files in os.walk(self.models_dir):
            for file in files:
                ext = Path(file).suffix.lower()
                if ext in self.MODEL_EXTENSIONS:
                    file_path = Path(root) / file
                    model_info = self._create_model_info(file_path)
                    self._installed_models.append(model_info)
                    logger.debug("Found model: %s (%s)", model_info.name, model_info.category)

        logger.info("Scanned %d local models", len(self._installed_models))
        return self._installed_models

    def _create_model_info(self, file_path: Path) -> ModelInfo:
        """Create ModelInfo from a file path."""
        name = file_path.stem
        ext = file_path.suffix.lower().lstrip(".")

        # Detect category and type based on filename
        category, model_type = self._detect_category_and_type(name.lower())

        # Get file size in MB
        try:
            size_mb = file_path.stat().st_size / (1024 * 1024)
        except OSError:
            size_mb = 0.0

        return ModelInfo(
            name=name,
            path=str(
                file_path.relative_to(self.models_dir) if file_path.is_relative_to(self.models_dir) else file_path
            ),
            type=model_type,
            category=category,
            size_mb=size_mb,
            format=ext,
        )

    def _detect_category_and_type(self, name: str) -> tuple[str, str]:
        """Detect model category and type from filename."""
        for category, patterns in self.CATEGORY_PATTERNS.items():
            for pattern in patterns:
                if pattern in name:
                    return category, pattern
        return "unknown", "unknown"

    def get_active_models(self) -> ActiveModels:
        """
        Read active model configuration from providers.toml.

        Returns:
            ActiveModels configuration object
        """
        self._active_models = ActiveModels()

        if not self.providers_config_path.exists():
            logger.warning("Providers config not found: %s", self.providers_config_path)
            return self._active_models

        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[import-untyped]

        try:
            with open(self.providers_config_path, "rb") as f:
                config = tomllib.load(f)

            if not isinstance(config, dict):
                config = {}
            self._providers_config = config

            # Vision configuration
            vision_config = self._providers_config.setdefault("vision", {})
            self._active_models.vision = {
                "model": vision_config.get("detection_model", "yolov8n"),
                "enabled": vision_config.get("enabled", False),
                "provider": "yolo",
                "use_mock": vision_config.get("use_mock", False),
            }

            # Voice configuration
            voice_config = self._providers_config.setdefault("voice", {})
            self._active_models.voice_asr = {
                "model": voice_config.get("asr_model", "base"),
                "enabled": voice_config.get("enabled", False),
                "provider": "whisper",
                "use_mock": voice_config.get("use_mock", False),
            }
            self._active_models.voice_tts = {
                "model": voice_config.get("tts_model", "en_US-lessac-medium"),
                "enabled": voice_config.get("enabled", False),
                "provider": "piper",
                "use_mock": voice_config.get("use_mock", False),
            }

            # Text configuration
            text_config = self._providers_config.setdefault("text", {})
            self._active_models.text = {
                "model": text_config.get("model", "llama3.2:1b"),
                "enabled": text_config.get("enabled", False),
                "provider": "ollama",
                "ollama_host": text_config.get("ollama_host", "http://localhost:11434"),
                "use_mock": text_config.get("use_mock", False),
            }

            logger.info("Loaded active model configuration")

        except Exception as e:
            logger.error("Failed to read providers config: %s", e)
            self._providers_config = {}

        return self._active_models

    async def scan_ollama_models(self, ollama_host: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query Ollama API for available LLM models.

        Args:
            ollama_host: Ollama API host URL (default from config)

        Returns:
            List of available Ollama models
        """
        import httpx

        host = ollama_host or "http://localhost:11434"
        self._ollama_models = []

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{host}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    self._ollama_models = data.get("models", [])
                    logger.info("Found %d Ollama models", len(self._ollama_models))
                else:
                    logger.warning("Ollama API returned status %d", response.status_code)
        except Exception as e:
            logger.debug("Could not connect to Ollama: %s", e)

        return self._ollama_models

    def get_installed_models(self) -> List[Dict[str, Any]]:
        """Get list of installed models as dictionaries."""
        if not self._installed_models:
            self.scan_local_models()
        return [m.to_dict() for m in self._installed_models]

    def get_ollama_models(self) -> List[Dict[str, Any]]:
        """Get cached list of Ollama models."""
        return self._ollama_models

    def get_all_models(self) -> Dict[str, Any]:
        """
        Get complete model inventory.

        Returns:
            Dictionary with installed, ollama, and active models
        """
        return {
            "installed": self.get_installed_models(),
            "ollama": self.get_ollama_models(),
            "active": self._active_models.to_dict() if self._active_models else {},
        }

    def persist_active_model(self, slot: str, model: str) -> None:
        """
        Update providers.toml with the newly selected model.

        Args:
            slot: Target slot identifier
            model: Model name to store in configuration
        """
        slot = (slot or "").lower()
        if slot not in self._slot_field_map:
            logger.warning("Unknown slot %s – skipping persistence", slot)
            return

        section_name, field_name = self._slot_field_map[slot]
        if not self._providers_config:
            # Reload to avoid overwriting the file with empty data
            self.get_active_models()

        section = self._providers_config.setdefault(section_name, {})
        section[field_name] = model

        try:
            import tomli_w
        except ImportError:  # pragma: no cover - dependency missing only in misconfiguration
            logger.error("tomli-w not installed; cannot persist providers config")
            return

        try:
            self.providers_config_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.providers_config_path.with_suffix(".tmp")
            with open(tmp_path, "wb") as tmp_file:
                tomli_w.dump(self._providers_config, tmp_file)
            tmp_path.replace(self.providers_config_path)
            logger.info("Updated %s for slot %s", self.providers_config_path, slot)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to persist providers config: %s", exc)
