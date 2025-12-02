"""Text provider for NLU/NLG and LLM tasks with MCP tool-call support."""

import logging
import os
from collections import deque
from typing import Dict, Any, List, Optional, Deque, TYPE_CHECKING
from pc_client.providers.base import BaseProvider, TaskEnvelope, TaskResult, TaskType, TaskStatus
from pc_client.telemetry.metrics import (
    tasks_processed_total,
    cache_hits_total,
    cache_misses_total,
)
from pc_client.mcp.tool_call_handler import (
    get_tools_prompt,
    parse_tool_call,
    execute_tool_call,
    format_tool_result,
)

if TYPE_CHECKING:
    from pc_client.providers.gemini_provider import GeminiProvider
    from pc_client.providers.chatgpt_provider import ChatGPTProvider

logger = logging.getLogger(__name__)

# Maksymalna liczba wpisów w historii wywołań MCP
_MCP_HISTORY_MAX_SIZE = 100

# Available text provider backends
BACKEND_LOCAL = "local"
BACKEND_GEMINI = "gemini"
BACKEND_CHATGPT = "chatgpt"
BACKEND_AUTO = "auto"
BACKEND_MOCK = "mock"
VALID_BACKENDS = {BACKEND_LOCAL, BACKEND_GEMINI, BACKEND_CHATGPT, BACKEND_AUTO}

# Import AI libraries with fallback to mock mode
try:
    import ollama

    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    logger.warning("Ollama not available, using mock LLM")


class TextProvider(BaseProvider):
    """
    Provider for text processing tasks (NLU/NLG/LLM).

    This provider handles text generation and understanding tasks offloaded
    from Rider-PI. It can delegate to local LLMs (Ollama) or cloud APIs
    (Gemini, ChatGPT), with caching and fallback support.

    Supported backends:
    - "local": Local Ollama LLM
    - "gemini": Google Gemini API
    - "chatgpt": OpenAI ChatGPT API
    - "auto": Try backends in order (local -> gemini -> chatgpt)
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the text provider.

        Args:
            config: Text provider configuration
                - model: Model to use (default: "llama3.2:1b")
                - max_tokens: Maximum generation tokens (default: 512)
                - temperature: Sampling temperature (default: 0.7)
                - use_cache: Enable response caching (default: True)
                - use_mock: Force mock mode (default: False)
                - ollama_host: Ollama server host (default: "http://localhost:11434")
                - enable_mcp_tools: Enable MCP tool-call support (default: True)
                - max_tool_iterations: Max tool iterations per request (default: 3)
                - backend: LLM backend ("local", "gemini", "chatgpt", "auto")
                - gemini_api_key: Gemini API key
                - gemini_model: Gemini model name
                - gemini_endpoint: Gemini API endpoint
                - openai_api_key: OpenAI API key
                - openai_model: OpenAI model name
                - openai_base_url: OpenAI API base URL
        """
        super().__init__("TextProvider", config)
        self.model = self.config.get("model", "llama3.2:1b")
        self.max_tokens = self.config.get("max_tokens", 512)
        self.temperature = self.config.get("temperature", 0.7)
        self.use_cache = self.config.get("use_cache", True)
        self.use_mock = self.config.get("use_mock", False)
        self.ollama_host = self.config.get("ollama_host", "http://localhost:11434")
        self.enable_mcp_tools = self.config.get("enable_mcp_tools", True)
        self.max_tool_iterations = self.config.get("max_tool_iterations", 3)
        self._cache: Dict[str, str] = {}
        self.ollama_available = False
        self.ollama_client = None
        # Użycie deque z maxlen dla automatycznego zarządzania rozmiarem historii
        self._mcp_call_history: Deque[Dict[str, Any]] = deque(maxlen=_MCP_HISTORY_MAX_SIZE)

        # External provider configuration
        self.backend = self.config.get("backend", BACKEND_LOCAL)
        if self.backend not in VALID_BACKENDS:
            self.logger.warning(f"Invalid backend '{self.backend}', falling back to 'local'")
            self.backend = BACKEND_LOCAL

        # External providers (initialized lazily)
        self._gemini_provider: Optional["GeminiProvider"] = None
        self._chatgpt_provider: Optional["ChatGPTProvider"] = None

        # External provider config from Settings or config dict
        self._gemini_api_key = self.config.get("gemini_api_key")
        self._gemini_model = self.config.get("gemini_model", "gemini-2.0-flash")
        self._gemini_endpoint = self.config.get(
            "gemini_endpoint", "https://generativelanguage.googleapis.com/v1beta"
        )
        self._openai_api_key = self.config.get("openai_api_key")
        self._openai_model = self.config.get("openai_model", "gpt-4o-mini")
        self._openai_base_url = self.config.get("openai_base_url", "https://api.openai.com/v1")

    async def _initialize_impl(self) -> None:
        """Initialize text processing models."""
        self.logger.info(f"Loading text model: {self.model}")
        self.logger.info(f"Max tokens: {self.max_tokens}")
        self.logger.info(f"Temperature: {self.temperature}")
        self.logger.info(f"Caching enabled: {self.use_cache}")
        self.logger.info(f"Ollama host: {self.ollama_host}")

        # Check if Ollama is available and running
        if OLLAMA_AVAILABLE and not self.use_mock:
            try:
                client_cls = getattr(ollama, "Client", None)
                if client_cls is not None:
                    self.logger.info(
                        "[provider] Checking Ollama connection at %s ...",
                        self.ollama_host,
                    )
                    self.ollama_client = client_cls(host=self.ollama_host)
                    self.ollama_client.list()
                else:
                    # Fallback to module-level API (set env for custom host)
                    if self.ollama_host:
                        os.environ["OLLAMA_HOST"] = self.ollama_host
                    self.logger.info("[provider] Checking Ollama connection...")
                    ollama.list()

                self.ollama_available = True
                self.logger.info(
                    "[provider] Ollama connected at %s, using model: %s",
                    self.ollama_host,
                    self.model,
                )
            except Exception as e:
                self.logger.warning(f"[provider] Ollama not available: {e}")
                self.logger.warning("[provider] Falling back to mock LLM")
                self.ollama_available = False
        else:
            self.logger.info("[provider] Using mock text implementation")
            self.ollama_available = False

        # Initialize external providers if configured
        await self._initialize_external_providers()

        self.logger.info(
            "[provider] Text provider initialized (backend=%s, ollama=%s, gemini=%s, chatgpt=%s)",
            self.backend,
            self.ollama_available,
            self._gemini_provider.is_available if self._gemini_provider else False,
            self._chatgpt_provider.is_available if self._chatgpt_provider else False,
        )

    async def _initialize_external_providers(self) -> None:
        """Initialize external LLM providers (Gemini, ChatGPT)."""
        # Initialize Gemini provider if API key is available
        if self._gemini_api_key or self.use_mock:
            try:
                from pc_client.providers.gemini_provider import GeminiProvider
                self._gemini_provider = GeminiProvider(
                    api_key=self._gemini_api_key,
                    model=self._gemini_model,
                    endpoint=self._gemini_endpoint,
                    use_mock=self.use_mock,
                )
                self.logger.info(
                    "[provider] Gemini provider initialized (model=%s, mock=%s)",
                    self._gemini_model,
                    self.use_mock,
                )
            except Exception as e:
                self.logger.warning(f"[provider] Failed to initialize Gemini provider: {e}")

        # Initialize ChatGPT provider if API key is available
        if self._openai_api_key or self.use_mock:
            try:
                from pc_client.providers.chatgpt_provider import ChatGPTProvider
                self._chatgpt_provider = ChatGPTProvider(
                    api_key=self._openai_api_key,
                    model=self._openai_model,
                    base_url=self._openai_base_url,
                    use_mock=self.use_mock,
                )
                self.logger.info(
                    "[provider] ChatGPT provider initialized (model=%s, mock=%s)",
                    self._openai_model,
                    self.use_mock,
                )
            except Exception as e:
                self.logger.warning(f"[provider] Failed to initialize ChatGPT provider: {e}")

    async def _shutdown_impl(self) -> None:
        """Cleanup text processing resources."""
        self.logger.info("[provider] Cleaning up text resources")
        self._cache.clear()

        # Close external provider connections
        if self._gemini_provider:
            try:
                await self._gemini_provider.close()
            except Exception as e:
                self.logger.warning(f"[provider] Error closing Gemini provider: {e}")

        if self._chatgpt_provider:
            try:
                await self._chatgpt_provider.close()
            except Exception as e:
                self.logger.warning(f"[provider] Error closing ChatGPT provider: {e}")

    async def _process_task_impl(self, task: TaskEnvelope) -> TaskResult:
        """
        Process text task.

        Args:
            task: Task envelope with text data

        Returns:
            Task result with generated or analyzed text
        """
        if task.task_type == TaskType.TEXT_GENERATE:
            return await self._process_generate(task)
        elif task.task_type == TaskType.TEXT_NLU:
            return await self._process_nlu(task)
        else:
            return TaskResult(
                task_id=task.task_id, status=TaskStatus.FAILED, error=f"Unsupported task type: {task.task_type}"
            )

    async def _process_generate(self, task: TaskEnvelope) -> TaskResult:
        """
        Process text generation task (LLM) with MCP tool-call support.

        Expected payload:
            - prompt: Text prompt for generation
            - max_tokens: Maximum tokens to generate (optional)
            - temperature: Sampling temperature (optional)
            - system_prompt: System prompt (optional)
            - enable_tools: Enable MCP tools for this request (optional, default: True)
            - backend: Override backend for this request (optional)

        Returns:
            TaskResult with generated text
        """
        self.logger.info(f"[provider] Processing text generation task {task.task_id}")

        prompt = task.payload.get("prompt")
        max_tokens = task.payload.get("max_tokens", self.max_tokens)
        temperature = task.payload.get("temperature", self.temperature)
        system_prompt = task.payload.get("system_prompt", "")
        enable_tools = task.payload.get("enable_tools", self.enable_mcp_tools)
        # Allow per-request backend override
        request_backend = task.payload.get("backend") or task.meta.get("backend") or self.backend

        if not prompt:
            return TaskResult(task_id=task.task_id, status=TaskStatus.FAILED, error="Missing prompt in payload")

        # Wzbogać system prompt o dostępne narzędzia MCP jeśli włączone
        if enable_tools and self.enable_mcp_tools:
            tools_prompt = get_tools_prompt()
            if tools_prompt:
                system_prompt = f"{system_prompt}\n\n{tools_prompt}" if system_prompt else tools_prompt

        # Check cache
        cache_key = f"{request_backend}:{prompt}:{max_tokens}:{temperature}"
        messages: Optional[List[Dict[str, str]]] = None

        if self.use_cache and cache_key in self._cache:
            self.logger.info("[provider] Cache hit for text generation")
            generated_text = self._cache[cache_key]
            from_cache = True
            used_backend = request_backend
            cache_hits_total.labels(cache_type='text_llm').inc()
        else:
            # Generate with selected backend
            generated_text, used_backend, messages = await self._generate_with_backend(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                backend=request_backend,
            )

            # Update cache
            if self.use_cache and generated_text:
                self._cache[cache_key] = generated_text

            from_cache = False
            cache_misses_total.labels(cache_type='text_llm').inc()

        # Obsługa tool-call: sprawdź czy odpowiedź zawiera wywołanie narzędzia
        tool_calls = []
        if enable_tools and self.enable_mcp_tools:
            generated_text, tool_calls = await self._handle_tool_calls(
                generated_text, messages if used_backend == BACKEND_LOCAL else None, max_tokens, temperature
            )

        self.logger.info(f"[provider] Generated {len(generated_text)} characters via {used_backend}")

        # Update metrics with provider info
        tasks_processed_total.labels(
            provider=f'TextProvider-{used_backend}',
            task_type='text.generate',
            status='completed'
        ).inc()

        # Determine model used based on backend
        model_used = self._get_model_for_backend(used_backend)

        result_data = {
            "text": generated_text,
            "tokens_used": len(generated_text.split()),
            "from_cache": from_cache,
            "backend": used_backend,
        }
        if tool_calls:
            result_data["tool_calls"] = tool_calls

        return TaskResult(
            task_id=task.task_id,
            status=TaskStatus.COMPLETED,
            result=result_data,
            meta={
                "model": model_used,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "prompt_length": len(prompt),
                "backend": used_backend,
                "engine": self._get_engine_name(used_backend),
                "mcp_tools_used": len(tool_calls) if tool_calls else 0,
            },
        )

    async def _generate_with_backend(
        self,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
        backend: str,
    ) -> tuple:
        """
        Generate text with specified backend.

        Returns:
            Tuple of (generated_text, used_backend, messages)
        """
        # List of backends to try (for auto mode)
        if backend == BACKEND_AUTO:
            backends_to_try = [BACKEND_LOCAL, BACKEND_GEMINI, BACKEND_CHATGPT]
        else:
            backends_to_try = [backend]

        for current_backend in backends_to_try:
            try:
                text, messages = await self._generate_single_backend(
                    current_backend, prompt, system_prompt, max_tokens, temperature
                )
                # Accept empty strings as valid responses (content may be filtered)
                return text, current_backend, messages
            except Exception as e:
                self.logger.warning(f"[provider] Backend {current_backend} failed: {e}")
                if backend != BACKEND_AUTO:
                    break  # Don't try other backends if specific one was requested

        # All backends failed, return mock response
        self.logger.warning("[provider] All backends failed, using mock response")
        mock_text = f"Mock LLM response to: {prompt[:50]}..."
        return mock_text, BACKEND_MOCK, None

    async def _generate_single_backend(
        self,
        backend: str,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> tuple:
        """Generate with a single backend. Returns (text, messages)."""
        if backend == BACKEND_LOCAL:
            return await self._generate_local(prompt, system_prompt, max_tokens, temperature)
        elif backend == BACKEND_GEMINI:
            return await self._generate_gemini(prompt, system_prompt, max_tokens, temperature)
        elif backend == BACKEND_CHATGPT:
            return await self._generate_chatgpt(prompt, system_prompt, max_tokens, temperature)
        else:
            raise ValueError(f"Unknown backend: {backend}")

    async def _generate_local(
        self,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> tuple:
        """Generate with local Ollama backend."""
        if not self.ollama_available:
            raise RuntimeError("Ollama not available")

        self.logger.info(f"[provider] Generating with Ollama model: {self.model}")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        client = self.ollama_client or ollama
        response = client.chat(
            model=self.model,
            messages=messages,
            options={"temperature": temperature, "num_predict": max_tokens},
        )

        generated_text = response['message']['content']
        self.logger.info(f"[provider] Generated {len(generated_text)} characters with Ollama")
        return generated_text, messages

    async def _generate_gemini(
        self,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> tuple:
        """Generate with Gemini backend."""
        if not self._gemini_provider:
            raise RuntimeError("Gemini provider not initialized")
        if not self._gemini_provider.is_available:
            raise RuntimeError("Gemini API key not configured")

        self.logger.info(f"[provider] Generating with Gemini model: {self._gemini_model}")

        response = await self._gemini_provider.generate(
            prompt=prompt,
            system_prompt=system_prompt if system_prompt else None,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        if response.error:
            raise RuntimeError(f"Gemini error: {response.error}")

        self.logger.info(f"[provider] Generated {len(response.text)} characters with Gemini")
        return response.text, None

    async def _generate_chatgpt(
        self,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> tuple:
        """Generate with ChatGPT backend."""
        if not self._chatgpt_provider:
            raise RuntimeError("ChatGPT provider not initialized")
        if not self._chatgpt_provider.is_available:
            raise RuntimeError("OpenAI API key not configured")

        self.logger.info(f"[provider] Generating with ChatGPT model: {self._openai_model}")

        response = await self._chatgpt_provider.generate(
            prompt=prompt,
            system_prompt=system_prompt if system_prompt else None,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        if response.error:
            raise RuntimeError(f"ChatGPT error: {response.error}")

        self.logger.info(f"[provider] Generated {len(response.text)} characters with ChatGPT")
        return response.text, None

    def _get_model_for_backend(self, backend: str) -> str:
        """Get model name for the given backend."""
        if backend == BACKEND_LOCAL:
            return self.model
        elif backend == BACKEND_GEMINI:
            return self._gemini_model
        elif backend == BACKEND_CHATGPT:
            return self._openai_model
        else:
            return "mock"

    def _get_engine_name(self, backend: str) -> str:
        """Get engine name for telemetry."""
        if backend == BACKEND_LOCAL:
            return "ollama" if self.ollama_available else "mock"
        elif backend == BACKEND_GEMINI:
            return "gemini"
        elif backend == BACKEND_CHATGPT:
            return "chatgpt"
        else:
            return "mock"

    async def _handle_tool_calls(
        self,
        response_text: str,
        messages: Optional[List[Dict[str, str]]],
        max_tokens: int,
        temperature: float,
    ) -> tuple:
        """
        Obsługuje wywołania narzędzi MCP z odpowiedzi LLM.

        Args:
            response_text: Tekst odpowiedzi LLM.
            messages: Lista wiadomości (do kontynuacji konwersacji).
            max_tokens: Limit tokenów.
            temperature: Temperatura.

        Returns:
            Tuple (finalny tekst, lista wywołanych narzędzi).
        """
        tool_calls = []
        current_response = response_text
        iteration = 0

        while iteration < self.max_tool_iterations:
            tool_call = parse_tool_call(current_response)
            if not tool_call:
                break

            self.logger.info(f"[provider] Detected tool call: {tool_call['name']}")

            # Wykonaj narzędzie MCP
            result = await execute_tool_call(
                tool_call["name"],
                tool_call.get("arguments"),
                confirm=False,  # Domyślnie bez potwierdzenia (UI musi obsłużyć confirm)
            )

            # Zapisz w historii wywołań (deque automatycznie usuwa stare wpisy)
            call_record = {
                "tool": tool_call["name"],
                "arguments": tool_call.get("arguments"),
                "ok": result.ok,
                "result": result.result if result.ok else None,
                "error": result.error if not result.ok else None,
            }
            tool_calls.append(call_record)
            self._mcp_call_history.append(call_record)

            # Formatuj wynik narzędzia
            tool_result_text = format_tool_result(result)

            # Jeśli narzędzie wymaga potwierdzenia, zwróć informację
            if not result.ok and result.meta.get("requires_confirm"):
                current_response = (
                    f"Narzędzie {tool_call['name']} wymaga potwierdzenia użytkownika. "
                    f"Użyj endpointu /api/mcp/tools/invoke z confirm=true."
                )
                break

            # Kontynuuj konwersację z wynikiem narzędzia (jeśli Ollama dostępna)
            if self.ollama_available and messages:
                messages.append({"role": "assistant", "content": current_response})
                messages.append({"role": "user", "content": tool_result_text})

                try:
                    response = ollama.chat(
                        model=self.model,
                        messages=messages,
                        options={"temperature": temperature, "num_predict": max_tokens},
                    )
                    current_response = response['message']['content']
                except Exception as e:
                    self.logger.error(f"[provider] Follow-up generation failed: {e}")
                    current_response = f"Wynik narzędzia: {tool_result_text}"
                    break
            else:
                # W trybie mock lub bez kontynuacji, dołącz wynik
                current_response = f"{current_response}\n\n{tool_result_text}"
                break

            iteration += 1

        return current_response, tool_calls

    def get_mcp_call_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Zwróć ostatnie wywołania narzędzi MCP."""
        # Konwersja deque do listy, aby umożliwić slicing
        history_list = list(self._mcp_call_history)
        return history_list[-limit:]

    async def _process_nlu(self, task: TaskEnvelope) -> TaskResult:
        """
        Process natural language understanding task.

        Expected payload:
            - text: Text to analyze
            - tasks: List of NLU tasks (e.g., ["intent", "entities", "sentiment"])

        Returns:
            TaskResult with NLU analysis
        """
        self.logger.info(f"[provider] Processing NLU task {task.task_id}")

        text = task.payload.get("text")
        nlu_tasks = task.payload.get("tasks", ["intent", "entities"])

        if not text:
            return TaskResult(task_id=task.task_id, status=TaskStatus.FAILED, error="Missing text in payload")

        # TODO: Implement actual NLU processing
        # Example:
        # intent = self.llm.detect_intent(text)
        # entities = self.llm.extract_entities(text)
        # sentiment = self.llm.analyze_sentiment(text)

        # Mock implementation
        result_data = {}

        if "intent" in nlu_tasks:
            result_data["intent"] = {"name": "navigate", "confidence": 0.89}

        if "entities" in nlu_tasks:
            result_data["entities"] = [
                {"type": "location", "value": "kitchen", "confidence": 0.92},
                {"type": "action", "value": "go", "confidence": 0.95},
            ]

        if "sentiment" in nlu_tasks:
            result_data["sentiment"] = {"label": "neutral", "score": 0.75}

        self.logger.info(f"[provider] NLU completed for text: {text[:50]}...")

        # Update metrics
        tasks_processed_total.labels(provider='TextProvider', task_type='text.nlu', status='completed').inc()

        return TaskResult(
            task_id=task.task_id,
            status=TaskStatus.COMPLETED,
            result=result_data,
            meta={"model": self.model, "tasks": nlu_tasks, "text_length": len(text)},
        )

    def get_supported_tasks(self) -> list[TaskType]:
        """Get list of supported task types."""
        return [TaskType.TEXT_GENERATE, TaskType.TEXT_NLU]

    def get_telemetry(self) -> Dict[str, Any]:
        """Get text provider telemetry."""
        base_telemetry = super().get_telemetry()

        # Build available backends list
        available_backends = []
        if self.ollama_available:
            available_backends.append(BACKEND_LOCAL)
        if self._gemini_provider and self._gemini_provider.is_available:
            available_backends.append(BACKEND_GEMINI)
        if self._chatgpt_provider and self._chatgpt_provider.is_available:
            available_backends.append(BACKEND_CHATGPT)

        base_telemetry.update(
            {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "cache_size": len(self._cache),
                "use_cache": self.use_cache,
                "ollama_available": self.ollama_available,
                "mode": "mock" if not self.ollama_available else "real",
                "mcp_tools_enabled": self.enable_mcp_tools,
                "mcp_call_history_size": len(self._mcp_call_history),
                # External providers info
                "backend": self.backend,
                "available_backends": available_backends,
                "gemini_configured": self._gemini_provider.is_configured if self._gemini_provider else False,
                "gemini_model": self._gemini_model,
                "chatgpt_configured": self._chatgpt_provider.is_configured if self._chatgpt_provider else False,
                "chatgpt_model": self._openai_model,
            }
        )
        return base_telemetry

    def get_external_providers_status(self) -> Dict[str, Any]:
        """Get detailed status of external providers."""
        return {
            "gemini": self._gemini_provider.get_status() if self._gemini_provider else {"available": False},
            "chatgpt": self._chatgpt_provider.get_status() if self._chatgpt_provider else {"available": False},
            "active_backend": self.backend,
            "available_backends": [
                b for b in [BACKEND_LOCAL, BACKEND_GEMINI, BACKEND_CHATGPT]
                if (b == BACKEND_LOCAL and self.ollama_available) or
                   (b == BACKEND_GEMINI and self._gemini_provider and self._gemini_provider.is_available) or
                   (b == BACKEND_CHATGPT and self._chatgpt_provider and self._chatgpt_provider.is_available)
            ],
        }
