"""Configuration utilities for provider setup and capabilities."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.9 compatibility
    import tomli as tomllib  # type: ignore

from pc_client.config import Settings

logger = logging.getLogger(__name__)


def load_provider_config(config_path: str, section: Optional[str] = None) -> Dict[str, Any]:
    """Load optional TOML config for providers."""
    if not config_path:
        return {}

    file_path = Path(config_path)
    if not file_path.exists():
        logger.warning(f"Provider config not found at {config_path}, using defaults")
        return {}

    try:
        with file_path.open("rb") as fp:
            data = tomllib.load(fp)
            if isinstance(data, dict):
                if section:
                    return data.get(section, data) or {}
                return data
    except Exception as exc:  # pragma: no cover - defensive
        logger.error(f"Failed to parse provider config {config_path}: {exc}")
    return {}


def get_provider_capabilities(settings: Settings) -> Dict[str, Any]:
    """Build capability payload for Rider-PI handshake."""
    vision_cfg = load_provider_config(settings.vision_provider_config_path, "vision")
    voice_cfg = load_provider_config(settings.voice_provider_config_path, "voice")
    text_cfg = load_provider_config(settings.text_provider_config_path, "text")

    def mode(enabled: bool) -> str:
        return "pc" if enabled else "local"

    return {
        "vision": {
            "version": vision_cfg.get("schema_version", "1.0.0"),
            "features": ["frame_offload", "obstacle_enhanced"],
            "frame_schema": vision_cfg.get("frame_schema", "vision.frame.v1"),
            "model": vision_cfg.get("detection_model", settings.vision_model),
            "priority": {"frame": int(vision_cfg.get("frame_priority", 1))},
            "mode": mode(settings.enable_vision_offload),
        },
        "voice": {
            "version": voice_cfg.get("schema_version", "1.0.0"),
            "features": ["asr", "tts"],
            "asr_model": voice_cfg.get("asr_model", settings.voice_model),
            "tts_model": voice_cfg.get("tts_model", voice_cfg.get("voice", "piper")),
            "sample_rate": voice_cfg.get("sample_rate", 16000),
            "mode": mode(settings.enable_voice_offload),
        },
        "text": {
            "version": text_cfg.get("schema_version", "1.0.0"),
            "features": ["chat", "nlu"],
            "model": text_cfg.get("model", settings.text_model),
            "nlu_tasks": text_cfg.get("nlu_tasks", []),
            "mode": mode(settings.enable_text_offload),
        },
    }
