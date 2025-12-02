"""Tests for pipeline_config module."""

import pytest
from pc_client.providers.pipeline_config import (
    PipelineConfig,
    PipelineProfile,
    get_pipeline_config,
    reset_pipeline_config,
    VALID_BACKENDS,
    VALID_LLM_BACKENDS,
    DEFAULT_PROFILES,
    BACKEND_DISPLAY_NAMES,
)


class TestPipelineProfile:
    """Tests for PipelineProfile dataclass."""

    def test_profile_defaults(self):
        """Test default profile values."""
        profile = PipelineProfile(name="test")
        assert profile.name == "test"
        assert profile.asr_backend == "local"
        assert profile.llm_backend == "local"
        assert profile.tts_backend == "local"
        assert profile.description == ""

    def test_profile_custom_values(self):
        """Test profile with custom values."""
        profile = PipelineProfile(
            name="hybrid",
            description="Test hybrid",
            asr_backend="local",
            llm_backend="gemini",
            tts_backend="chatgpt",
        )
        assert profile.llm_backend == "gemini"
        assert profile.tts_backend == "chatgpt"

    def test_profile_to_dict(self):
        """Test profile serialization."""
        profile = PipelineProfile(name="test", description="desc")
        d = profile.to_dict()
        assert d["name"] == "test"
        assert d["description"] == "desc"
        assert "asr_backend" in d
        assert "llm_backend" in d
        assert "tts_backend" in d


class TestPipelineConfig:
    """Tests for PipelineConfig class."""

    def test_config_defaults(self):
        """Test default config values."""
        config = PipelineConfig()
        assert config.asr_backend == "local"
        assert config.llm_backend == "local"
        assert config.tts_backend == "local"
        assert config.active_profile is None
        assert len(config.profiles) == len(DEFAULT_PROFILES)

    def test_get_backend_asr(self):
        """Test getting ASR backend."""
        config = PipelineConfig(asr_backend="gemini")
        assert config.get_backend("asr") == "gemini"

    def test_get_backend_llm(self):
        """Test getting LLM backend."""
        config = PipelineConfig(llm_backend="chatgpt")
        assert config.get_backend("llm") == "chatgpt"

    def test_get_backend_tts(self):
        """Test getting TTS backend."""
        config = PipelineConfig(tts_backend="gemini")
        assert config.get_backend("tts") == "gemini"

    def test_get_backend_unknown(self):
        """Test getting unknown backend returns local."""
        config = PipelineConfig()
        assert config.get_backend("unknown") == "local"

    def test_set_backend_valid(self):
        """Test setting valid backend."""
        config = PipelineConfig()
        result = config.set_backend("asr", "gemini")
        assert result is True
        assert config.asr_backend == "gemini"

    def test_set_backend_llm_auto(self):
        """Test setting LLM backend to auto."""
        config = PipelineConfig()
        result = config.set_backend("llm", "auto")
        assert result is True
        assert config.llm_backend == "auto"

    def test_set_backend_invalid(self):
        """Test setting invalid backend fails."""
        config = PipelineConfig()
        result = config.set_backend("asr", "invalid")
        assert result is False
        assert config.asr_backend == "local"

    def test_set_backend_clears_profile(self):
        """Test that setting backend clears active profile."""
        config = PipelineConfig()
        config.active_profile = "local"
        config.set_backend("llm", "gemini")
        assert config.active_profile is None

    def test_apply_profile_valid(self):
        """Test applying valid profile."""
        config = PipelineConfig()
        result = config.apply_profile("hybrid-gemini")
        assert result is True
        assert config.active_profile == "hybrid-gemini"
        assert config.llm_backend == "gemini"
        assert config.asr_backend == "local"
        assert config.tts_backend == "local"

    def test_apply_profile_invalid(self):
        """Test applying invalid profile fails."""
        config = PipelineConfig()
        result = config.apply_profile("nonexistent")
        assert result is False
        assert config.active_profile is None

    def test_get_profile(self):
        """Test getting profile by name."""
        config = PipelineConfig()
        profile = config.get_profile("local")
        assert profile is not None
        assert profile.name == "local"

    def test_get_profile_nonexistent(self):
        """Test getting nonexistent profile."""
        config = PipelineConfig()
        profile = config.get_profile("nonexistent")
        assert profile is None

    def test_get_status(self):
        """Test getting config status."""
        config = PipelineConfig()
        config.llm_backend = "gemini"
        status = config.get_status()
        assert status["llm_backend"] == "gemini"
        assert "profiles" in status
        assert len(status["profiles"]) > 0


class TestGlobalPipelineConfig:
    """Tests for global pipeline config singleton."""

    def test_get_pipeline_config(self):
        """Test getting global config."""
        reset_pipeline_config()
        config = get_pipeline_config()
        assert config is not None
        assert isinstance(config, PipelineConfig)

    def test_get_pipeline_config_singleton(self):
        """Test that get returns same instance."""
        reset_pipeline_config()
        config1 = get_pipeline_config()
        config2 = get_pipeline_config()
        assert config1 is config2

    def test_reset_pipeline_config(self):
        """Test resetting global config."""
        config1 = get_pipeline_config()
        config1.llm_backend = "gemini"
        reset_pipeline_config()
        config2 = get_pipeline_config()
        assert config2.llm_backend == "local"
        assert config1 is not config2


class TestConstants:
    """Tests for module constants."""

    def test_valid_backends(self):
        """Test VALID_BACKENDS contains expected values."""
        assert "local" in VALID_BACKENDS
        assert "gemini" in VALID_BACKENDS
        assert "chatgpt" in VALID_BACKENDS

    def test_valid_llm_backends(self):
        """Test VALID_LLM_BACKENDS includes auto."""
        assert "auto" in VALID_LLM_BACKENDS
        assert VALID_BACKENDS.issubset(VALID_LLM_BACKENDS)

    def test_backend_display_names(self):
        """Test display names mapping."""
        assert BACKEND_DISPLAY_NAMES["local"] == "Local"
        assert BACKEND_DISPLAY_NAMES["gemini"] == "Gemini"
        assert BACKEND_DISPLAY_NAMES["chatgpt"] == "ChatGPT"

    def test_default_profiles(self):
        """Test default profiles exist."""
        names = [p.name for p in DEFAULT_PROFILES]
        assert "local" in names
        assert "hybrid-gemini" in names
        assert "hybrid-chatgpt" in names
        assert "auto" in names
