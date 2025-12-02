"""OpenAI ChatGPT API provider for text generation."""

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
    logger.warning("httpx not available, ChatGPT provider will use mock mode")


class ChatGPTProvider(ExternalLLMProvider):
    """
    OpenAI ChatGPT API provider for text generation.

    Supports:
    - Text generation with gpt-4o-mini, gpt-4o, gpt-4-turbo, etc.
    - System messages for instructions
    - Function calling (tools) for MCP integration
    - Reasoning models (o1-preview, o1-mini) with extended timeout
    - Rate limiting with exponential backoff
    """

    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    DEFAULT_MODEL = "gpt-4o-mini"

    # Reasoning models that may need longer timeouts and have tool limitations
    REASONING_MODELS = {"o1-preview", "o1-mini", "o1"}

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: int = 60,
        max_retries: int = 3,
        use_mock: bool = False,
    ):
        """
        Initialize ChatGPT provider.

        Args:
            api_key: OpenAI API key
            model: Model name (e.g., gpt-4o-mini, gpt-4o)
            base_url: API base URL (for Azure OpenAI or compatible endpoints)
            timeout_seconds: Request timeout
            max_retries: Max retry attempts on rate limiting
            use_mock: Enable mock mode for testing
        """
        # Increase timeout for reasoning models
        if model in self.REASONING_MODELS:
            timeout_seconds = max(timeout_seconds, 120)

        super().__init__(
            provider_name="chatgpt",
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            use_mock=use_mock,
        )
        self._http_client: Optional["httpx.AsyncClient"] = None

    async def _get_client(self) -> "httpx.AsyncClient":
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            if not HTTPX_AVAILABLE:
                raise RuntimeError("httpx is required for ChatGPT API calls")
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
        Generate text using ChatGPT API.

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
            self.logger.debug("[chatgpt] Using mock response")
            return self.get_mock_response(prompt)

        if not self.api_key:
            self.logger.warning("[chatgpt] No API key configured")
            return LLMResponse(
                text="",
                model=self.model,
                provider="chatgpt",
                error="OpenAI API key not configured",
            )

        # Check cache
        cache_key = self._get_cache_key(prompt, system_prompt, max_tokens, temperature)
        cached = self._get_cached_response(cache_key)
        if cached:
            self.logger.debug("[chatgpt] Cache hit")
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
            self.logger.error("[chatgpt] Generation failed: %s", e)
            return LLMResponse(
                text="",
                model=self.model,
                provider="chatgpt",
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
        """Send request to ChatGPT API."""
        import time

        start_time = time.time()
        client = await self._get_client()

        # Build request payload
        payload = self._build_payload(prompt, system_prompt, max_tokens, temperature, tools)

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        self.logger.debug("[chatgpt] Sending request to %s", url)

        response = await client.post(url, headers=headers, json=payload)

        latency_ms = (time.time() - start_time) * 1000

        if response.status_code == 429:
            raise Exception("Rate limit exceeded (429)")

        if response.status_code != 200:
            error_text = response.text[:200]
            raise Exception(f"ChatGPT API error {response.status_code}: {error_text}")

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
        """Build ChatGPT API request payload."""
        messages = []

        # Add system message
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Add user message
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }

        # Reasoning models have temperature restrictions
        if self.model not in self.REASONING_MODELS:
            payload["temperature"] = temperature

        # Add tools for function calling (not supported by reasoning models)
        if tools and self.model not in self.REASONING_MODELS:
            payload["tools"] = self._convert_tools(tools)

        return payload

    def _convert_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert MCP tools to OpenAI function calling format."""
        openai_tools = []
        for tool in tools:
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                },
            }
            if "parameters" in tool:
                openai_tool["function"]["parameters"] = tool["parameters"]
            openai_tools.append(openai_tool)
        return openai_tools

    def _parse_response(self, data: Dict[str, Any], latency_ms: float) -> LLMResponse:
        """Parse ChatGPT API response."""
        choices = data.get("choices", [])
        if not choices:
            return LLMResponse(
                text="",
                model=self.model,
                provider="chatgpt",
                latency_ms=latency_ms,
                error="No choices in response",
            )

        message = choices[0].get("message", {})
        text = message.get("content", "") or ""

        # Extract tool calls
        tool_calls = []
        raw_tool_calls = message.get("tool_calls", [])
        for tc in raw_tool_calls:
            if tc.get("type") == "function":
                func = tc.get("function", {})
                # Parse arguments JSON if needed
                args = func.get("arguments", "{}")
                if isinstance(args, str):
                    try:
                        import json
                        args = json.loads(args)
                    except (json.JSONDecodeError, TypeError):
                        args = {}
                tool_calls.append({
                    "id": tc.get("id"),
                    "name": func.get("name", ""),
                    "arguments": args,
                })

        # Extract usage
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        return LLMResponse(
            text=text,
            model=data.get("model", self.model),
            provider="chatgpt",
            tokens_used=prompt_tokens + completion_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            from_cache=False,
            tool_calls=tool_calls if tool_calls else None,
            meta={
                "finish_reason": choices[0].get("finish_reason"),
                "id": data.get("id"),
            },
        )

    def get_status(self) -> Dict[str, Any]:
        """Get provider status."""
        status = super().get_status()
        status["base_url"] = self.base_url
        status["has_api_key"] = bool(self.api_key)
        status["is_reasoning_model"] = self.model in self.REASONING_MODELS
        return status
