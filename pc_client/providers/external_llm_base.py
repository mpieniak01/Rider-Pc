"""Base class for external LLM providers (Gemini, ChatGPT, etc.)."""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Unified response format for external LLM providers."""

    text: str
    model: str
    provider: str
    tokens_used: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    from_cache: bool = False
    tool_calls: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class ExternalLLMProvider(ABC):
    """
    Abstract base class for external LLM providers.

    Provides a unified interface for Gemini, ChatGPT, and other external APIs.
    """

    def __init__(
        self,
        provider_name: str,
        api_key: Optional[str] = None,
        model: str = "",
        base_url: str = "",
        timeout_seconds: int = 60,
        max_retries: int = 3,
        use_mock: bool = False,
    ):
        """
        Initialize the external LLM provider.

        Args:
            provider_name: Name of the provider (e.g., "gemini", "chatgpt")
            api_key: API key for authentication
            model: Default model to use
            base_url: API base URL
            timeout_seconds: Request timeout in seconds
            max_retries: Maximum retry attempts on rate limiting
            use_mock: Enable mock mode for testing
        """
        self.provider_name = provider_name
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.use_mock = use_mock
        self.logger = logging.getLogger(f"[provider] {provider_name}")
        self._cache: Dict[str, LLMResponse] = {}

    @property
    def is_configured(self) -> bool:
        """Check if the provider is properly configured with API key."""
        return bool(self.api_key) and not self.use_mock

    @property
    def is_available(self) -> bool:
        """Check if the provider is available for use (configured or mock mode)."""
        return self.is_configured or self.use_mock

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        """
        Generate text response from the LLM.

        Args:
            prompt: User prompt/message
            system_prompt: System instructions
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-2.0)
            tools: MCP tools available for function calling

        Returns:
            LLMResponse with generated text and metadata
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close connections and cleanup resources."""
        pass

    def _get_cache_key(
        self,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Generate cache key for request."""
        tools_key = str(tools) if tools else "no_tools"
        return f"{self.provider_name}:{prompt}:{system_prompt}:{max_tokens}:{temperature}:{tools_key}"

    def _get_cached_response(self, cache_key: str) -> Optional[LLMResponse]:
        """Get cached response if available."""
        if cache_key in self._cache:
            response = self._cache[cache_key]
            # Create a copy to avoid mutating the cached object
            return replace(response, from_cache=True)
        return None

    def _cache_response(self, cache_key: str, response: LLMResponse) -> None:
        """Cache response for future use."""
        self._cache[cache_key] = response

    async def _retry_with_backoff(
        self,
        func,
        *args,
        retry_after: float = 1.0,
        **kwargs,
    ) -> Any:
        """
        Execute function with exponential backoff on rate limiting.

        Args:
            func: Async function to execute
            retry_after: Initial retry delay in seconds
            *args, **kwargs: Arguments to pass to the function

        Returns:
            Result from the function

        Raises:
            Exception: If all retries fail
        """
        last_error = None
        delay = retry_after

        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check for rate limiting errors
                if "429" in error_str or "rate limit" in error_str:
                    self.logger.warning(
                        "[%s] Rate limited, retrying in %.1fs (attempt %d/%d)",
                        self.provider_name,
                        delay,
                        attempt + 1,
                        self.max_retries,
                    )
                    await self._async_sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    # Non-retryable error
                    raise

        # All retries failed
        raise last_error if last_error else Exception("All retries failed")

    async def _async_sleep(self, seconds: float) -> None:
        """Async sleep helper."""
        await asyncio.sleep(seconds)

    def get_mock_response(self, prompt: str) -> LLMResponse:
        """Generate mock response for testing."""
        return LLMResponse(
            text=f"[MOCK {self.provider_name.upper()}] Response to: {prompt[:50]}...",
            model=f"mock-{self.model}",
            provider=self.provider_name,
            tokens_used=len(prompt.split()) + 10,
            prompt_tokens=len(prompt.split()),
            completion_tokens=10,
            latency_ms=50.0,
            from_cache=False,
            meta={"mock": True},
        )

    def log_cost(
        self,
        response: LLMResponse,
        task_id: Optional[str] = None,
    ) -> None:
        """Log API cost for the response.

        Args:
            response: LLMResponse with token usage information
            task_id: Optional task identifier for tracking
        """
        try:
            from pc_client.telemetry.cost_logger import log_api_cost
            from pc_client.telemetry.metrics import (
                llm_requests_total,
                llm_tokens_used_total,
                llm_latency_seconds,
                llm_errors_total,
            )

            # Log to cost file
            log_api_cost(
                provider=self.provider_name,
                model=response.model,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                latency_ms=response.latency_ms,
                task_id=task_id,
                success=response.error is None,
                error=response.error,
            )

            # Update Prometheus metrics
            status = "success" if response.error is None else "error"
            llm_requests_total.labels(
                provider=self.provider_name,
                model=response.model,
                status=status,
            ).inc()

            if response.prompt_tokens > 0:
                llm_tokens_used_total.labels(
                    provider=self.provider_name,
                    model=response.model,
                    token_type="input",
                ).inc(response.prompt_tokens)

            if response.completion_tokens > 0:
                llm_tokens_used_total.labels(
                    provider=self.provider_name,
                    model=response.model,
                    token_type="output",
                ).inc(response.completion_tokens)

            if response.latency_ms > 0:
                llm_latency_seconds.labels(
                    provider=self.provider_name,
                    model=response.model,
                ).observe(response.latency_ms / 1000.0)

            if response.error:
                llm_errors_total.labels(
                    provider=self.provider_name,
                    model=response.model,
                    error_type="api_error",
                ).inc()

        except Exception as e:
            self.logger.debug("Failed to log cost: %s", e)

    def get_status(self) -> Dict[str, Any]:
        """Get provider status information."""
        return {
            "provider": self.provider_name,
            "model": self.model,
            "configured": self.is_configured,
            "available": self.is_available,
            "use_mock": self.use_mock,
            "cache_size": len(self._cache),
        }

    def clear_cache(self) -> int:
        """Clear response cache. Returns number of entries cleared."""
        count = len(self._cache)
        self._cache.clear()
        return count
