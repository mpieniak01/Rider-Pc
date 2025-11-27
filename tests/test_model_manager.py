"""Tests for model_manager.py"""

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from pc_client.core.model_manager import ModelManager, ModelInfo, ActiveModels


class TestModelInfo:
    """Tests for ModelInfo dataclass."""

    def test_to_dict(self):
        """Test ModelInfo serialization."""
        info = ModelInfo(
            name="yolov8n",
            path="vision/yolov8n.pt",
            type="yolo",
            category="vision",
            size_mb=12.5,
            format="pt",
        )
        result = info.to_dict()
        assert result["name"] == "yolov8n"
        assert result["path"] == "vision/yolov8n.pt"
        assert result["type"] == "yolo"
        assert result["category"] == "vision"
        assert result["size_mb"] == 12.5
        assert result["format"] == "pt"


class TestActiveModels:
    """Tests for ActiveModels dataclass."""

    def test_to_dict_empty(self):
        """Test ActiveModels with default values."""
        active = ActiveModels()
        result = active.to_dict()
        assert result == {
            "vision": {},
            "voice_asr": {},
            "voice_tts": {},
            "text": {},
        }

    def test_to_dict_with_data(self):
        """Test ActiveModels with populated data."""
        active = ActiveModels(
            vision={"model": "yolov8n", "enabled": True},
            text={"model": "llama3.2:1b", "provider": "ollama"},
        )
        result = active.to_dict()
        assert result["vision"]["model"] == "yolov8n"
        assert result["text"]["provider"] == "ollama"


class TestModelManager:
    """Tests for ModelManager class."""

    def test_init_default_paths(self):
        """Test ModelManager initialization with defaults."""
        manager = ModelManager()
        assert manager.models_dir == Path("data/models")
        assert manager.providers_config_path == Path("config/providers.toml")

    def test_init_custom_paths(self):
        """Test ModelManager initialization with custom paths."""
        manager = ModelManager(
            models_dir="/custom/models",
            providers_config_path="/custom/providers.toml",
        )
        assert manager.models_dir == Path("/custom/models")
        assert manager.providers_config_path == Path("/custom/providers.toml")

    def test_detect_category_yolo(self):
        """Test category detection for YOLO models."""
        manager = ModelManager()
        category, model_type = manager._detect_category_and_type("yolov8n")
        assert category == "vision"
        assert model_type == "yolo"

    def test_detect_category_whisper(self):
        """Test category detection for Whisper models."""
        manager = ModelManager()
        category, model_type = manager._detect_category_and_type("whisper-base")
        assert category == "voice_asr"
        assert model_type == "whisper"

    def test_detect_category_piper(self):
        """Test category detection for Piper models."""
        manager = ModelManager()
        category, model_type = manager._detect_category_and_type("piper-pl-medium")
        assert category == "voice_tts"
        assert model_type == "piper"

    def test_detect_category_llama(self):
        """Test category detection for LLaMA models."""
        manager = ModelManager()
        category, model_type = manager._detect_category_and_type("llama3.2-1b")
        assert category == "text"
        assert model_type == "llama"

    def test_detect_category_unknown(self):
        """Test category detection for unknown models."""
        manager = ModelManager()
        category, model_type = manager._detect_category_and_type("random-model")
        assert category == "unknown"
        assert model_type == "unknown"

    def test_scan_local_models_missing_dir(self, tmp_path):
        """Test scanning when models directory doesn't exist."""
        manager = ModelManager(models_dir=str(tmp_path / "nonexistent"))
        result = manager.scan_local_models()
        assert result == []

    def test_scan_local_models_empty_dir(self, tmp_path):
        """Test scanning empty directory."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        manager = ModelManager(models_dir=str(models_dir))
        result = manager.scan_local_models()
        assert result == []

    def test_scan_local_models_with_files(self, tmp_path):
        """Test scanning directory with model files."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()

        # Create test model files
        (models_dir / "yolov8n.pt").write_bytes(b"fake model data")
        (models_dir / "whisper-base.onnx").write_bytes(b"fake whisper data")
        (models_dir / "readme.txt").write_text("Not a model file")

        manager = ModelManager(models_dir=str(models_dir))
        result = manager.scan_local_models()

        assert len(result) == 2
        names = [m.name for m in result]
        assert "yolov8n" in names
        assert "whisper-base" in names

    def test_get_active_models_missing_config(self, tmp_path):
        """Test reading config when file doesn't exist."""
        manager = ModelManager(providers_config_path=str(tmp_path / "nonexistent.toml"))
        result = manager.get_active_models()
        assert isinstance(result, ActiveModels)

    def test_get_active_models_valid_config(self, tmp_path):
        """Test reading valid providers.toml config."""
        config_path = tmp_path / "providers.toml"
        config_path.write_text("""
[vision]
detection_model = "yolov8n"
enabled = true
use_mock = false

[voice]
asr_model = "base"
tts_model = "en_US-lessac-medium"
enabled = true
use_mock = false

[text]
model = "llama3.2:1b"
enabled = true
use_mock = false
ollama_host = "http://localhost:11434"
""")

        manager = ModelManager(providers_config_path=str(config_path))
        result = manager.get_active_models()

        assert result.vision["model"] == "yolov8n"
        assert result.vision["enabled"] is True
        assert result.voice_asr["model"] == "base"
        assert result.voice_tts["model"] == "en_US-lessac-medium"
        assert result.text["model"] == "llama3.2:1b"
        assert result.text["ollama_host"] == "http://localhost:11434"

    def test_get_installed_models_returns_dicts(self, tmp_path):
        """Test get_installed_models returns list of dicts."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "test.pt").write_bytes(b"data")

        manager = ModelManager(models_dir=str(models_dir))
        result = manager.get_installed_models()

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], dict)
        assert result[0]["name"] == "test"

    def test_get_all_models(self, tmp_path):
        """Test get_all_models returns complete inventory."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()

        config_path = tmp_path / "providers.toml"
        config_path.write_text("[vision]\ndetection_model = 'yolov8n'\n")

        manager = ModelManager(
            models_dir=str(models_dir),
            providers_config_path=str(config_path),
        )
        manager.get_active_models()

        result = manager.get_all_models()

        assert "installed" in result
        assert "ollama" in result
        assert "active" in result
        assert isinstance(result["installed"], list)
        assert isinstance(result["ollama"], list)
        assert isinstance(result["active"], dict)


class TestPersistActiveModel:
    """Tests for persist_active_model method."""

    def test_persist_vision_model(self, tmp_path):
        """Test persisting vision model to TOML file."""
        config_path = tmp_path / "providers.toml"
        config_path.write_text("[vision]\ndetection_model = 'yolov8n'\n")

        manager = ModelManager(providers_config_path=str(config_path))
        manager.get_active_models()
        manager.persist_active_model("vision", "yolov8s")

        # Read back and verify
        import tomllib

        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        assert data["vision"]["detection_model"] == "yolov8s"

    def test_persist_text_model(self, tmp_path):
        """Test persisting text model to TOML file."""
        config_path = tmp_path / "providers.toml"
        config_path.write_text("[text]\nmodel = 'llama2'\n")

        manager = ModelManager(providers_config_path=str(config_path))
        manager.get_active_models()
        manager.persist_active_model("text", "llama3.2:1b")

        import tomllib

        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        assert data["text"]["model"] == "llama3.2:1b"

    def test_persist_voice_asr_model(self, tmp_path):
        """Test persisting voice ASR model to TOML file."""
        config_path = tmp_path / "providers.toml"
        config_path.write_text("[voice]\nasr_model = 'base'\n")

        manager = ModelManager(providers_config_path=str(config_path))
        manager.get_active_models()
        manager.persist_active_model("voice_asr", "large-v3")

        import tomllib

        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        assert data["voice"]["asr_model"] == "large-v3"

    def test_persist_voice_tts_model(self, tmp_path):
        """Test persisting voice TTS model to TOML file."""
        config_path = tmp_path / "providers.toml"
        config_path.write_text("[voice]\ntts_model = 'en_US-lessac-medium'\n")

        manager = ModelManager(providers_config_path=str(config_path))
        manager.get_active_models()
        manager.persist_active_model("voice_tts", "pl_PL-darkman-medium")

        import tomllib

        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        assert data["voice"]["tts_model"] == "pl_PL-darkman-medium"

    def test_persist_unknown_slot_skipped(self, tmp_path):
        """Test that unknown slots are skipped without error."""
        config_path = tmp_path / "providers.toml"
        config_path.write_text("[vision]\ndetection_model = 'yolov8n'\n")

        manager = ModelManager(providers_config_path=str(config_path))
        manager.get_active_models()
        manager.persist_active_model("invalid_slot", "some-model")

        # File should remain unchanged
        import tomllib

        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        assert data["vision"]["detection_model"] == "yolov8n"
        assert "invalid_slot" not in data

    def test_persist_empty_slot_skipped(self, tmp_path):
        """Test that empty slot is skipped without error."""
        config_path = tmp_path / "providers.toml"
        config_path.write_text("[vision]\ndetection_model = 'yolov8n'\n")

        manager = ModelManager(providers_config_path=str(config_path))
        manager.get_active_models()
        manager.persist_active_model("", "some-model")

        # File should remain unchanged
        import tomllib

        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        assert data["vision"]["detection_model"] == "yolov8n"

    def test_persist_none_slot_skipped(self, tmp_path):
        """Test that None slot is handled gracefully."""
        config_path = tmp_path / "providers.toml"
        config_path.write_text("[vision]\ndetection_model = 'yolov8n'\n")

        manager = ModelManager(providers_config_path=str(config_path))
        manager.get_active_models()
        manager.persist_active_model(None, "some-model")

        # File should remain unchanged
        import tomllib

        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        assert data["vision"]["detection_model"] == "yolov8n"

    def test_persist_creates_parent_directories(self, tmp_path):
        """Test that persist creates parent directories if needed."""
        config_path = tmp_path / "subdir" / "nested" / "providers.toml"
        manager = ModelManager(providers_config_path=str(config_path))
        manager._providers_config = {"vision": {"detection_model": "yolov8n"}}

        manager.persist_active_model("vision", "yolov8s")

        assert config_path.exists()
        import tomllib

        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        assert data["vision"]["detection_model"] == "yolov8s"

    def test_persist_reloads_config_if_empty(self, tmp_path):
        """Test that persist reloads config if _providers_config is empty."""
        config_path = tmp_path / "providers.toml"
        config_path.write_text("[vision]\ndetection_model = 'yolov8n'\nenabled = true\n")

        manager = ModelManager(providers_config_path=str(config_path))
        # Don't call get_active_models() first - _providers_config is empty
        assert manager._providers_config == {}

        manager.persist_active_model("vision", "yolov8s")

        import tomllib

        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        # Check that both original and new values are present
        assert data["vision"]["detection_model"] == "yolov8s"
        assert data["vision"]["enabled"] is True

    def test_persist_preserves_existing_config(self, tmp_path):
        """Test that persist preserves other config sections."""
        config_path = tmp_path / "providers.toml"
        config_path.write_text("""
[vision]
detection_model = "yolov8n"
enabled = true

[text]
model = "llama2"
ollama_host = "http://localhost:11434"
""")

        manager = ModelManager(providers_config_path=str(config_path))
        manager.get_active_models()
        manager.persist_active_model("vision", "yolov8s")

        import tomllib

        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        # Vision model updated
        assert data["vision"]["detection_model"] == "yolov8s"
        assert data["vision"]["enabled"] is True
        # Text config preserved
        assert data["text"]["model"] == "llama2"
        assert data["text"]["ollama_host"] == "http://localhost:11434"

    def test_persist_without_tomli_w_logs_error(self, tmp_path, caplog):
        """Test behavior when tomli-w is not installed."""
        config_path = tmp_path / "providers.toml"
        config_path.write_text("[vision]\ndetection_model = 'yolov8n'\n")

        manager = ModelManager(providers_config_path=str(config_path))
        manager.get_active_models()

        # Mock import failure for tomli_w
        with patch.dict(sys.modules, {"tomli_w": None}):
            with patch("builtins.__import__", side_effect=ImportError("No module named 'tomli_w'")):
                manager.persist_active_model("vision", "yolov8s")

        # File should remain unchanged
        import tomllib

        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        assert data["vision"]["detection_model"] == "yolov8n"

    def test_persist_handles_write_failure(self, tmp_path, caplog):
        """Test that IOError during write is logged."""
        config_path = tmp_path / "providers.toml"
        config_path.write_text("[vision]\ndetection_model = 'yolov8n'\n")

        manager = ModelManager(providers_config_path=str(config_path))
        manager.get_active_models()

        # Make directory read-only to cause write failure
        tmp_path.chmod(0o444)

        try:
            import logging

            with caplog.at_level(logging.ERROR):
                manager.persist_active_model("vision", "yolov8s")
            # Should log an error about write failure
            assert any("Failed to write" in r.message or "Unexpected error" in r.message for r in caplog.records)
        finally:
            # Restore permissions for cleanup
            tmp_path.chmod(0o755)
