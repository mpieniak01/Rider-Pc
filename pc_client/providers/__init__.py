"""Provider layer for AI task offloading from Rider-PI to PC."""

from pc_client.providers.base import BaseProvider, TaskEnvelope, TaskResult
from pc_client.providers.voice_provider import VoiceProvider
from pc_client.providers.vision_provider import VisionProvider
from pc_client.providers.text_provider import TextProvider
from pc_client.providers.external_llm_base import ExternalLLMProvider, LLMResponse
from pc_client.providers.gemini_provider import GeminiProvider
from pc_client.providers.chatgpt_provider import ChatGPTProvider

__all__ = [
    "BaseProvider",
    "TaskEnvelope",
    "TaskResult",
    "VoiceProvider",
    "VisionProvider",
    "TextProvider",
    "ExternalLLMProvider",
    "LLMResponse",
    "GeminiProvider",
    "ChatGPTProvider",
]
