"""Tests for model_manager.py"""

import pytest
from pathlib import Path
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
