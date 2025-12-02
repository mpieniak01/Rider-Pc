"""Gemini API provider for text generation."""

import logging
from typing import Any, Dict, List, Optional

from pc_client.providers.external_llm_base import ExternalLLMProvider, LLMResponse

logger = logging.getLogger(__name__)

# Import httpx with fallback
try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logger.warning("httpx not available, Gemini provider will use mock mode")


class GeminiProvider(ExternalLLMProvider):
    """
    Google Gemini API provider for text generation.

    Supports:
    - Text generation with gemini-2.0-flash, gemini-2.5-flash-lite, etc.
    - System instructions via systemInstruction field
    - Function calling (tools) for MCP integration
    - Rate limiting with exponential backoff
    """

    DEFAULT_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta"
    DEFAULT_MODEL = "gemini-2.0-flash"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout_seconds: int = 60,
        max_retries: int = 3,
        use_mock: bool = False,
    ):
        """
        Initialize Gemini provider.

        Args:
            api_key: Google AI API key (from aistudio.google.com)
            model: Model name (e.g., gemini-2.0-flash)
            endpoint: API endpoint URL
            timeout_seconds: Request timeout
            max_retries: Max retry attempts on rate limiting
            use_mock: Enable mock mode for testing
        """
        super().__init__(
            provider_name="gemini",
            api_key=api_key,
            model=model,
            base_url=endpoint,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            use_mock=use_mock,
        )
        self._http_client: Optional["httpx.AsyncClient"] = None

    async def _get_client(self) -> "httpx.AsyncClient":
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            if not HTTPX_AVAILABLE:
                raise RuntimeError("httpx is required for Gemini API calls")
            self._http_client = httpx.AsyncClient(timeout=self.timeout_seconds)
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        """
        Generate text using Gemini API.

        Args:
            prompt: User prompt
            system_prompt: System instructions
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-2.0)
            tools: MCP tools for function calling

        Returns:
            LLMResponse with generated text
        """
        # Check for mock mode
        if self.use_mock or not HTTPX_AVAILABLE:
            self.logger.debug("[gemini] Using mock response")
            return self.get_mock_response(prompt)

        if not self.api_key:
            self.logger.warning("[gemini] No API key configured")
            return LLMResponse(
                text="",
                model=self.model,
                provider="gemini",
                error="Gemini API key not configured",
            )

        # Check cache
        cache_key = self._get_cache_key(prompt, system_prompt, max_tokens, temperature)
        cached = self._get_cached_response(cache_key)
        if cached:
            self.logger.debug("[gemini] Cache hit")
            return cached

        try:
            response = await self._retry_with_backoff(
                self._send_request,
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                tools=tools,
            )
            self._cache_response(cache_key, response)
            return response

        except Exception as e:
            self.logger.error("[gemini] Generation failed: %s", e)
            return LLMResponse(
                text="",
                model=self.model,
                provider="gemini",
                error=str(e),
            )

    async def _send_request(
        self,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
        tools: Optional[List[Dict[str, Any]]],
    ) -> LLMResponse:
        """Send request to Gemini API."""
        import time

        start_time = time.time()
        client = await self._get_client()

        # Build request payload
        payload = self._build_payload(prompt, system_prompt, max_tokens, temperature, tools)

        # Gemini uses query param for API key
        url = f"{self.base_url}/models/{self.model}:generateContent"
        params = {"key": self.api_key}

        self.logger.debug("[gemini] Sending request to %s", url)

        response = await client.post(url, params=params, json=payload)

        latency_ms = (time.time() - start_time) * 1000

        if response.status_code == 429:
            raise Exception("Rate limit exceeded (429)")

        if response.status_code != 200:
            error_text = response.text[:200]
            raise Exception(f"Gemini API error {response.status_code}: {error_text}")

        data = response.json()
        return self._parse_response(data, latency_ms)

    def _build_payload(
        self,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
        tools: Optional[List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """Build Gemini API request payload."""
        payload: Dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "topP": 0.95,
            },
        }

        # Add system instruction (Gemini doesn't use "system" role in contents)
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        # Add tools for function calling
        if tools:
            payload["tools"] = [{"functionDeclarations": self._convert_tools(tools)}]

        return payload

    def _convert_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert MCP tools to Gemini function declarations format."""
        declarations = []
        for tool in tools:
            declaration = {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
            }
            if "parameters" in tool:
                declaration["parameters"] = tool["parameters"]
            declarations.append(declaration)
        return declarations

    def _parse_response(self, data: Dict[str, Any], latency_ms: float) -> LLMResponse:
        """Parse Gemini API response."""
        candidates = data.get("candidates", [])
        if not candidates:
            return LLMResponse(
                text="",
                model=self.model,
                provider="gemini",
                latency_ms=latency_ms,
                error="No candidates in response",
            )

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])

        # Extract text and tool calls
        text_parts = []
        tool_calls = []

        for part in parts:
            if "text" in part:
                text_parts.append(part["text"])
            elif "functionCall" in part:
                fc = part["functionCall"]
                tool_calls.append(
                    {
                        "name": fc.get("name", ""),
                        "arguments": fc.get("args", {}),
                    }
                )

        text = "\n".join(text_parts)

        # Extract usage metadata
        usage = data.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount", 0)
        completion_tokens = usage.get("candidatesTokenCount", 0)

        return LLMResponse(
            text=text,
            model=self.model,
            provider="gemini",
            tokens_used=prompt_tokens + completion_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            from_cache=False,
            tool_calls=tool_calls if tool_calls else None,
            meta={
                "finish_reason": candidates[0].get("finishReason"),
            },
        )

    def get_status(self) -> Dict[str, Any]:
        """Get provider status."""
        status = super().get_status()
        status["endpoint"] = self.base_url
        status["has_api_key"] = bool(self.api_key)
        return status
