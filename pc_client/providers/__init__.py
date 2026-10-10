"""Lekki interfejs providerów; domeny są importowane dopiero na żądanie."""

from importlib import import_module

from pc_client.providers.base import BaseProvider, TaskEnvelope, TaskResult

_LAZY = {
    "VoiceProvider": "voice_provider",
    "VisionProvider": "vision_provider",
    "TextProvider": "text_provider",
    "ExternalLLMProvider": "external_llm_base",
    "LLMResponse": "external_llm_base",
    "GeminiProvider": "gemini_provider",
    "ChatGPTProvider": "chatgpt_provider",
}
__all__ = ["BaseProvider", "TaskEnvelope", "TaskResult", *_LAZY]


def __getattr__(name):
    if name not in _LAZY:
        raise AttributeError(name)
    value = getattr(import_module(f"pc_client.providers.{_LAZY[name]}"), name)
    globals()[name] = value
    return value
