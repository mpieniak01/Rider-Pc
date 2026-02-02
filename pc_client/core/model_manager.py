"""Model Manager for AI model inventory and configuration."""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

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


def _is_test_mode() -> bool:
    return os.getenv("TEST_MODE", "false").lower() == "true"


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

    DEMO_LOCAL_MODELS: tuple[Dict[str, object], ...] = (
        {
            "name": "vision-demo.onnx",
            "path": "vision-demo.onnx",
            "type": "yolo",
            "category": "vision",
            "size_mb": 18.4,
            "format": "onnx",
        },
        {
            "name": "whisper-small.en",
            "path": "whisper-small.en",
            "type": "whisper",
            "category": "voice_asr",
            "size_mb": 75.2,
            "format": "en",
        },
        {
            "name": "piper-pl",
            "path": "piper-pl.onnx",
            "type": "piper",
            "category": "voice_tts",
            "size_mb": 48.7,
            "format": "onnx",
        },
        {
            "name": "llama3.2-text",
            "path": "llama3.2.gguf",
            "type": "llm",
            "category": "text",
            "size_mb": 220.1,
            "format": "gguf",
        },
    )
    DEMO_OLLAMA_MODELS = (
        {"name": "llama3.2:1b", "size": 4_000_000_000, "details": {"format": "gguf"}},
        {"name": "mistral:7b", "size": 13_000_000_000, "details": {"format": "gguf"}},
    )

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
        self._using_default_models_dir = models_dir is None
        self.models_dir = Path(models_dir) if models_dir else Path("data/models")
        self.providers_config_path = (
            Path(providers_config_path) if providers_config_path else Path("config/providers.toml")
        )
        self._installed_models: List[ModelInfo] = []
        self._seen_model_paths: set[Path] = set()
        self._active_models: Optional[ActiveModels] = None
        self._ollama_models: List[Dict[str, Any]] = []
        self._providers_config: Dict[str, Any] = {}
        self._project_root = Path(__file__).resolve().parents[2]
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
        self._seen_model_paths = set()

        if not self.models_dir.exists():
            logger.warning("Models directory does not exist: %s", self.models_dir)
            if self._should_seed_demo_models():
                self._seed_demo_models()
            return self._installed_models

        for root, _, files in os.walk(self.models_dir):
            for file in files:
                ext = Path(file).suffix.lower()
                if ext in self.MODEL_EXTENSIONS:
                    file_path = Path(root) / file
                    self._register_model_file(file_path)

        if not self._installed_models and self._should_seed_demo_models():
            self._seed_demo_models()

        self._include_active_config_models()

        logger.info("Scanned %d local models", len(self._installed_models))
        return self._installed_models

    def _should_seed_demo_models(self) -> bool:
        """Return True when demo models should be injected."""
        return self._using_default_models_dir and _is_test_mode()

    def _seed_demo_models(self) -> None:
        """Populate deterministic demo models used in TEST_MODE."""
        self._installed_models = [
            ModelInfo(
                name=str(entry["name"]),
                path=str(entry["path"]),
                type=str(entry["type"]),
                category=str(entry["category"]),
                size_mb=cast(float, entry["size_mb"]),
                format=str(entry["format"]),
            )
            for entry in self.DEMO_LOCAL_MODELS
        ]
        logger.info("Seeded %d demo models for TEST_MODE", len(self._installed_models))

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

    def _register_model_file(self, file_path: Path) -> None:
        """Register a model file if it hasn't been seen yet."""
        try:
            resolved = file_path.resolve()
        except OSError:
            resolved = file_path
        if resolved in self._seen_model_paths:
            return

        model_info = self._create_model_info(file_path)
        self._installed_models.append(model_info)
        self._seen_model_paths.add(resolved)
        logger.debug("Found model: %s (%s)", model_info.name, model_info.category)

    def _include_active_config_models(self) -> None:
        """Ensure models referenced by providers.toml appear in the inventory even if stored outside data/models."""
        # Only extend inventory with configured models when using default models directory.
        # Custom/test directories should reflect their own contents without pulling files
        # from the project root (e.g., yolov8n.pt).
        if not self._using_default_models_dir:
            return

        if not self._providers_config:
            self.get_active_models()

        vision_config = self._providers_config.get("vision", {})
        detection_model = vision_config.get("detection_model")
        if detection_model:
            for candidate in self._candidate_paths(detection_model):
                if candidate.exists():
                    self._register_model_file(candidate)
                    break

    def _candidate_paths(self, model_name: str) -> List[Path]:
        """Generate possible filesystem paths for a configured model name."""
        candidates: List[Path] = []
        raw_path = Path(model_name)

        possible_names: List[Path]
        if raw_path.suffix:
            possible_names = [raw_path]
        else:
            possible_names = [raw_path]
            for ext in sorted(self.MODEL_EXTENSIONS):
                possible_names.append(raw_path.with_suffix(ext))

        search_bases = [self.models_dir, self._project_root]

        for variant in possible_names:
            if variant.is_absolute():
                candidates.append(variant)
                continue
            for base in search_bases:
                candidates.append(base / variant)

        seen: set[Path] = set()
        unique_candidates: List[Path] = []
        for path in candidates:
            try:
                resolved = path.resolve()
            except OSError:
                resolved = path
            if resolved in seen:
                continue
            seen.add(resolved)
            unique_candidates.append(path)

        return unique_candidates

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

        import importlib
        import importlib.util

        toml_name = "tomllib" if importlib.util.find_spec("tomllib") else "tomli"
        toml_reader = importlib.import_module(toml_name)

        try:
            with open(self.providers_config_path, "rb") as f:
                config = toml_reader.load(f)

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

        host = ollama_host
        if not host:
            if not self._active_models:
                self.get_active_models()
            host = (
                (self._active_models.text or {}).get("ollama_host")
                if self._active_models and isinstance(self._active_models.text, dict)
                else None
            )
        host = host or "http://localhost:11434"
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

        if not self._ollama_models and _is_test_mode():
            self._ollama_models = [dict(entry) for entry in self.DEMO_OLLAMA_MODELS]
            logger.info("Seeded %d demo Ollama models for TEST_MODE", len(self._ollama_models))

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
        except (IOError, OSError) as exc:
            logger.error("Failed to write providers config file: %s", exc)
        except Exception as exc:  # noqa: BLE001
            logger.error("Unexpected error while persisting providers config: %s", exc)
