"""Pipeline configuration for AI providers.

This module manages the configuration of AI provider backends for the
speech-to-text-to-speech pipeline:
- ASR (Automatic Speech Recognition): voice -> text
- LLM (Large Language Model): text -> text
- TTS (Text-to-Speech): text -> voice

Each component can use a different backend (local, gemini, chatgpt)
to allow hybrid configurations like local ASR + cloud LLM + local TTS.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

logger = logging.getLogger(__name__)

# Valid backend identifiers (lowercase for config, CamelCase for UI)
VALID_BACKENDS = {"local", "gemini", "chatgpt"}
VALID_LLM_BACKENDS = {"local", "gemini", "chatgpt", "auto"}

# Backend display names for UI
BACKEND_DISPLAY_NAMES = {
    "local": "Local",
    "gemini": "Gemini",
    "chatgpt": "ChatGPT",
    "auto": "Auto",
}

BackendType = Literal["local", "gemini", "chatgpt"]
LLMBackendType = Literal["local", "gemini", "chatgpt", "auto"]


@dataclass
class PipelineProfile:
    """A named configuration profile for the AI pipeline.

    Profiles allow users to quickly switch between different configurations,
    e.g., "local" (all local), "hybrid-gemini" (local ASR + Gemini LLM + local TTS).
    """

    name: str
    description: str = ""
    asr_backend: BackendType = "local"
    llm_backend: LLMBackendType = "local"
    tts_backend: BackendType = "local"

    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "asr_backend": self.asr_backend,
            "llm_backend": self.llm_backend,
            "tts_backend": self.tts_backend,
        }


# Predefined profiles
DEFAULT_PROFILES = [
    PipelineProfile(
        name="local",
        description="Tryb w pełni lokalny (Whisper + Ollama + Piper)",
        asr_backend="local",
        llm_backend="local",
        tts_backend="local",
    ),
    PipelineProfile(
        name="hybrid-gemini",
        description="Hybrydowy: lokalny ASR/TTS + Gemini LLM",
        asr_backend="local",
        llm_backend="gemini",
        tts_backend="local",
    ),
    PipelineProfile(
        name="hybrid-chatgpt",
        description="Hybrydowy: lokalny ASR/TTS + ChatGPT LLM",
        asr_backend="local",
        llm_backend="chatgpt",
        tts_backend="local",
    ),
    PipelineProfile(
        name="auto",
        description="Automatyczny wybór dostępnego backendu",
        asr_backend="local",
        llm_backend="auto",
        tts_backend="local",
    ),
]


@dataclass
class PipelineConfig:
    """Configuration manager for AI provider pipeline.

    This class manages the current pipeline configuration and provides
    methods to get/set backend preferences for each component.
    """

    # Current backend selections
    asr_backend: BackendType = "local"
    llm_backend: LLMBackendType = "local"
    tts_backend: BackendType = "local"

    # Active profile name
    active_profile: Optional[str] = None

    # Available profiles
    profiles: List[PipelineProfile] = field(default_factory=lambda: list(DEFAULT_PROFILES))

    def get_backend(self, component: str) -> str:
        """Get backend for a pipeline component.

        Args:
            component: Component name ("asr", "llm", "tts")

        Returns:
            Backend identifier ("local", "gemini", "chatgpt", or "auto" for LLM)
        """
        if component == "asr":
            return self.asr_backend
        elif component == "llm":
            return self.llm_backend
        elif component == "tts":
            return self.tts_backend
        else:
            logger.warning("Unknown pipeline component: %s", component)
            return "local"

    def set_backend(self, component: str, backend: str) -> bool:
        """Set backend for a pipeline component.

        Args:
            component: Component name ("asr", "llm", "tts")
            backend: Backend identifier

        Returns:
            True if successful, False if invalid backend
        """
        valid_set = VALID_LLM_BACKENDS if component == "llm" else VALID_BACKENDS

        if backend not in valid_set:
            logger.warning("Invalid backend '%s' for component '%s'", backend, component)
            return False

        if component == "asr":
            self.asr_backend = backend  # type: ignore
        elif component == "llm":
            self.llm_backend = backend  # type: ignore
        elif component == "tts":
            self.tts_backend = backend  # type: ignore
        else:
            logger.warning("Unknown pipeline component: %s", component)
            return False

        # Clear active profile when manually changing backends
        self.active_profile = None
        return True

    def apply_profile(self, profile_name: str) -> bool:
        """Apply a named profile configuration.

        Args:
            profile_name: Name of the profile to apply

        Returns:
            True if profile found and applied, False otherwise
        """
        for profile in self.profiles:
            if profile.name == profile_name:
                self.asr_backend = profile.asr_backend
                self.llm_backend = profile.llm_backend
                self.tts_backend = profile.tts_backend
                self.active_profile = profile_name
                logger.info("Applied pipeline profile: %s", profile_name)
                return True

        logger.warning("Pipeline profile not found: %s", profile_name)
        return False

    def get_profile(self, profile_name: str) -> Optional[PipelineProfile]:
        """Get a profile by name."""
        for profile in self.profiles:
            if profile.name == profile_name:
                return profile
        return None

    def get_status(self) -> Dict[str, Any]:
        """Get current pipeline configuration status."""
        return {
            "asr_backend": self.asr_backend,
            "llm_backend": self.llm_backend,
            "tts_backend": self.tts_backend,
            "active_profile": self.active_profile,
            "profiles": [p.to_dict() for p in self.profiles],
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return self.get_status()


# Global pipeline configuration instance
_pipeline_config: Optional[PipelineConfig] = None


def get_pipeline_config() -> PipelineConfig:
    """Get or create the global pipeline configuration instance."""
    global _pipeline_config
    if _pipeline_config is None:
        _pipeline_config = PipelineConfig()
    return _pipeline_config


def reset_pipeline_config() -> None:
    """Reset the global pipeline configuration (for testing)."""
    global _pipeline_config
    _pipeline_config = None
