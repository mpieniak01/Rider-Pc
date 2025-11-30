"""Chat endpoints for Rider-PC UI.

Ten moduł obsługuje endpointy czatu zarówno w trybie lokalnym (PC standalone),
jak i proxy do Rider-PI. Kluczowe endpointy:
- /api/chat/send - standardowy endpoint czatu (automatycznie wybiera tryb)
- /api/chat/pc/send - wymuszony tryb lokalny (bez proxy)
- /api/chat/pc/generate-pr-content - generowanie treści PR z pomocą AI
- /api/providers/text - status providera tekstowego
"""

import time
import uuid
import logging
from enum import Enum
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from pc_client.adapters import RestAdapter
from pc_client.providers import TextProvider
from pc_client.providers.base import TaskEnvelope, TaskStatus, TaskType

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatMode(str, Enum):
    """Tryby pracy czatu."""

    PC = "pc"  # Wymuszony tryb lokalny
    PROXY = "proxy"  # Wymuszony tryb proxy do Rider-PI
    AUTO = "auto"  # Automatyczny wybór (domyślny)


def _get_text_provider(request: Request) -> Optional[TextProvider]:
    provider = getattr(request.app.state, "text_provider", None)
    return provider if isinstance(provider, TextProvider) else None


def _extract_prompt(payload: Dict[str, Any]) -> Optional[str]:
    for key in ("msg", "message", "prompt", "text", "content"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _parse_chat_mode(payload: Dict[str, Any]) -> ChatMode:
    """Parsuj tryb czatu z payloadu."""
    mode_str = str(payload.get("mode", "auto")).lower()
    try:
        return ChatMode(mode_str)
    except ValueError:
        return ChatMode.AUTO


def _is_provider_ready(provider: Optional[TextProvider]) -> bool:
    """Sprawdź czy provider tekstowy jest gotowy do użycia."""
    if not provider:
        return False
    telemetry = provider.get_telemetry()
    return bool(telemetry.get("initialized"))


async def _process_local_chat(
    provider: TextProvider, prompt: str, payload: Dict[str, Any]
) -> JSONResponse:
    """Przetwórz żądanie czatu lokalnie przez TextProvider."""
    # Walidacja max_tokens
    max_tokens = payload.get("max_tokens")
    if max_tokens is not None:
        try:
            max_tokens = int(max_tokens)
            if max_tokens < 1 or max_tokens > 4096:
                max_tokens = None
        except (ValueError, TypeError):
            max_tokens = None
    # Walidacja temperature
    temperature = payload.get("temperature")
    if temperature is not None:
        try:
            temperature = float(temperature)
            if temperature < 0.0 or temperature > 2.0:
                temperature = None
        except (ValueError, TypeError):
            temperature = None
    task = TaskEnvelope(
        task_id=f"text-chat-{uuid.uuid4()}",
        task_type=TaskType.TEXT_GENERATE,
        payload={
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system_prompt": payload.get("system_prompt"),
        },
        meta={
            "mode": "pc",
            "context": payload.get("context"),
            "user": payload.get("user"),
        },
    )
    start_time = time.time()
    result = await provider.process_task(task)
    latency_ms = int((time.time() - start_time) * 1000)

    if result.status != TaskStatus.COMPLETED or not result.result:
        return JSONResponse(
            {"ok": False, "error": result.error or "chat generation failed", "source": "pc"},
            status_code=502,
        )

    reply = (result.result or {}).get("text") or ""
    telemetry = provider.get_telemetry()

    return JSONResponse(
        {
            "ok": True,
            "reply": reply,
            "source": "pc",
            "meta": result.meta,
            "task_id": result.task_id,
            "latency_ms": latency_ms,
            "provider_info": {
                "model": telemetry.get("model"),
                "engine": telemetry.get("mode"),
                "ollama_available": telemetry.get("ollama_available", False),
            },
        }
    )


async def _process_proxy_chat(
    adapter: RestAdapter, payload: Dict[str, Any]
) -> JSONResponse:
    """Prześlij żądanie czatu do Rider-PI przez proxy."""
    start_time = time.time()
    remote = await adapter.post_chat_send(payload or {})
    latency_ms = int((time.time() - start_time) * 1000)

    if isinstance(remote, dict) and "error" not in remote:
        remote["source"] = "proxy"
        remote["latency_ms"] = latency_ms
        return JSONResponse(remote)

    error_msg = remote.get("error", "chat proxy failed") if isinstance(remote, dict) else "chat proxy failed"
    logger.error("Chat proxy failed: %s", error_msg)
    return JSONResponse(
        {"ok": False, "error": error_msg, "source": "proxy"},
        status_code=502,
    )


@router.post("/api/chat/send")
async def chat_send(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    """Handle chat requests locally or proxy to Rider-PI.

    Parametry w payload:
    - msg/message/prompt/text/content: tekst wiadomości (wymagane)
    - mode: "pc" | "proxy" | "auto" (opcjonalne, domyślnie "auto")
    - max_tokens: maksymalna liczba tokenów (opcjonalne)
    - temperature: temperatura generowania (opcjonalne)
    - system_prompt: prompt systemowy (opcjonalne)
    - context: kontekst rozmowy (opcjonalne)
    - user: identyfikator użytkownika (opcjonalne)

    Odpowiedź zawiera pole "source" wskazujące źródło ("pc" lub "proxy").
    """
    provider = _get_text_provider(request)
    adapter: Optional[RestAdapter] = request.app.state.rest_adapter
    mode = _parse_chat_mode(payload)

    prompt = _extract_prompt(payload)
    if not prompt:
        return JSONResponse({"ok": False, "error": "missing prompt"}, status_code=400)

    provider_ready = _is_provider_ready(provider)

    # Tryb wymuszony PC
    if mode == ChatMode.PC:
        if not provider_ready:
            return JSONResponse(
                {
                    "ok": False,
                    "error": "local text provider not available",
                    "hint": "Sprawdź czy ENABLE_PROVIDERS=true i ENABLE_TEXT_OFFLOAD=true",
                },
                status_code=503,
            )
        return await _process_local_chat(provider, prompt, payload)  # type: ignore

    # Tryb wymuszony proxy
    if mode == ChatMode.PROXY:
        if not adapter:
            return JSONResponse(
                {"ok": False, "error": "Rider-PI adapter not available"},
                status_code=503,
            )
        return await _process_proxy_chat(adapter, payload)

    # Tryb automatyczny - preferuj lokalny provider
    if provider_ready:
        return await _process_local_chat(provider, prompt, payload)  # type: ignore

    if adapter:
        return await _process_proxy_chat(adapter, payload)

    return JSONResponse(
        {
            "ok": False,
            "error": "chat provider unavailable",
            "hint": "Brak lokalnego providera i połączenia z Rider-PI",
        },
        status_code=503,
    )


@router.post("/api/chat/pc/send")
async def chat_pc_send(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    """Endpoint czatu działający wyłącznie lokalnie (bez proxy do Rider-PI).

    Ten endpoint wymusza tryb PC i zwraca błąd 503 jeśli lokalny provider
    nie jest dostępny. Używaj tego endpointu gdy chcesz mieć pewność,
    że odpowiedź pochodzi z lokalnego modelu.

    Parametry w payload:
    - msg/message/prompt/text/content: tekst wiadomości (wymagane)
    - max_tokens: maksymalna liczba tokenów (opcjonalne)
    - temperature: temperatura generowania (opcjonalne)
    - system_prompt: prompt systemowy (opcjonalne)
    - context: kontekst rozmowy (opcjonalne)
    - user: identyfikator użytkownika (opcjonalne)
    """
    provider = _get_text_provider(request)

    if not _is_provider_ready(provider):
        return JSONResponse(
            {
                "ok": False,
                "error": "local text provider not initialized",
                "hint": "Sprawdź czy ENABLE_PROVIDERS=true i ENABLE_TEXT_OFFLOAD=true",
                "status": "offline",
            },
            status_code=503,
        )

    prompt = _extract_prompt(payload)
    if not prompt:
        return JSONResponse({"ok": False, "error": "missing prompt"}, status_code=400)

    return await _process_local_chat(provider, prompt, payload)  # type: ignore


@router.get("/api/providers/text")
async def providers_text_status(request: Request) -> JSONResponse:
    """Zwróć status providera tekstowego.

    Odpowiedź zawiera:
    - initialized: czy provider jest zainicjalizowany
    - model: nazwa modelu
    - engine: silnik (ollama/mock)
    - ollama_available: czy Ollama jest dostępna
    - cache_size: rozmiar cache
    - mode: tryb pracy (real/mock)
    """
    provider = _get_text_provider(request)

    if not provider:
        return JSONResponse(
            {
                "initialized": False,
                "status": "not_configured",
                "hint": "TextProvider nie jest skonfigurowany. Ustaw ENABLE_PROVIDERS=true i ENABLE_TEXT_OFFLOAD=true",
            }
        )

    telemetry = provider.get_telemetry()
    return JSONResponse(
        {
            "initialized": telemetry.get("initialized", False),
            "status": "ready" if telemetry.get("initialized") else "initializing",
            "model": telemetry.get("model"),
            "engine": "ollama" if telemetry.get("ollama_available") else "mock",
            "ollama_available": telemetry.get("ollama_available", False),
            "cache_size": telemetry.get("cache_size", 0),
            "mode": telemetry.get("mode", "unknown"),
            "max_tokens": telemetry.get("max_tokens"),
            "temperature": telemetry.get("temperature"),
            "use_cache": telemetry.get("use_cache", False),
        }
    )


@router.post("/api/chat/pc/generate-pr-content")
async def generate_pr_content(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    """Generuj treść PR z pomocą AI.

    Ten endpoint integruje Chat PC z modułem Project/PR editor, umożliwiając
    automatyczne generowanie i ulepszanie treści PR na podstawie szkiców,
    bazy wiedzy i kontekstu projektu.

    Parametry w payload:
    - draft: szkic PR lub opis zmian (wymagane)
    - context: dodatkowy kontekst (opcjonalne)
      - issues: lista powiązanych issues
      - files_changed: lista zmienionych plików
      - knowledge_base: fragmenty bazy wiedzy
    - style: styl generowania ("concise", "detailed", "technical")
    - language: język wyjściowy ("pl", "en")

    Odpowiedź:
    - title: sugerowany tytuł PR
    - description: wygenerowany opis PR
    - summary: krótkie podsumowanie zmian
    """
    provider = _get_text_provider(request)

    if not _is_provider_ready(provider):
        return JSONResponse(
            {
                "ok": False,
                "error": "local text provider not initialized",
                "hint": "Endpoint wymaga aktywnego TextProvider",
            },
            status_code=503,
        )

    draft = payload.get("draft", "").strip()
    if not draft:
        return JSONResponse(
            {"ok": False, "error": "missing 'draft' field"},
            status_code=400,
        )

    context = payload.get("context", {})
    VALID_STYLES = {"concise", "detailed", "technical"}
    VALID_LANGUAGES = {"pl", "en"}
    style = payload.get("style", "detailed")
    if style not in VALID_STYLES:
        style = "detailed"
    language = payload.get("language", "pl")
    if language not in VALID_LANGUAGES:
        language = "pl"

    # Buduj prompt systemowy dla generowania treści PR
    system_prompt = _build_pr_system_prompt(style, language)
    user_prompt = _build_pr_user_prompt(draft, context)

    task = TaskEnvelope(
        task_id=f"pr-content-{uuid.uuid4()}",
        task_type=TaskType.TEXT_GENERATE,
        payload={
            "prompt": user_prompt,
            "system_prompt": system_prompt,
            "max_tokens": payload.get("max_tokens", 1024),
            "temperature": payload.get("temperature", 0.7),
        },
        meta={
            "mode": "pr_generation",
            "style": style,
            "language": language,
        },
    )

    start_time = time.time()
    result = await provider.process_task(task)  # type: ignore
    latency_ms = int((time.time() - start_time) * 1000)

    if result.status != TaskStatus.COMPLETED or not result.result:
        return JSONResponse(
            {"ok": False, "error": result.error or "PR content generation failed"},
            status_code=502,
        )

    generated_text = (result.result or {}).get("text", "")

    # Parsuj wygenerowany tekst na strukturę PR
    pr_content = _parse_pr_content(generated_text, draft)

    return JSONResponse(
        {
            "ok": True,
            "title": pr_content.get("title", ""),
            "description": pr_content.get("description", ""),
            "summary": pr_content.get("summary", ""),
            "raw_output": generated_text,
            "latency_ms": latency_ms,
            "task_id": result.task_id,
        }
    )


def _build_pr_system_prompt(style: str, language: str) -> str:
    """Buduj prompt systemowy dla generowania treści PR."""
    lang_instruction = "Odpowiadaj po polsku." if language == "pl" else "Respond in English."

    style_instructions = {
        "concise": "Bądź zwięzły i rzeczowy. Skup się na najważniejszych zmianach.",
        "detailed": "Podaj szczegółowy opis zmian, ich uzasadnienie i wpływ na projekt.",
        "technical": "Skup się na aspektach technicznych: architektura, API, zależności.",
    }

    style_text = style_instructions.get(style, style_instructions["detailed"])

    return f"""Jesteś asystentem AI pomagającym w tworzeniu opisów Pull Requestów.
{lang_instruction}
{style_text}

Generuj treść w formacie:
TYTUŁ: [krótki, opisowy tytuł PR]
OPIS: [szczegółowy opis zmian]
PODSUMOWANIE: [1-2 zdania podsumowania]

Używaj markdown dla formatowania."""


def _build_pr_user_prompt(draft: str, context: Dict[str, Any]) -> str:
    """Buduj prompt użytkownika dla generowania treści PR."""
    parts = [f"Szkic PR:\n{draft}"]

    if context.get("issues"):
        issues_text = "\n".join(f"- {issue}" for issue in context["issues"])
        parts.append(f"\nPowiązane issues:\n{issues_text}")

    if context.get("files_changed"):
        files_text = "\n".join(f"- {f}" for f in context["files_changed"])
        parts.append(f"\nZmienione pliki:\n{files_text}")

    if context.get("knowledge_base"):
        kb_text = "\n".join(context["knowledge_base"])
        parts.append(f"\nKontekst z bazy wiedzy:\n{kb_text}")

    parts.append("\nWygeneruj profesjonalny opis PR na podstawie powyższych informacji.")

    return "\n".join(parts)


def _parse_pr_content(generated_text: str, fallback_draft: str) -> Dict[str, str]:
    """Parsuj wygenerowany tekst na strukturę PR."""
    result = {
        "title": "",
        "description": "",
        "summary": "",
    }

    lines = generated_text.strip().split("\n")
    current_section = None
    section_content: list[str] = []

    for line in lines:
        line_upper = line.upper().strip()
        if line_upper.startswith("TYTUŁ:") or line_upper.startswith("TITLE:"):
            if current_section and section_content:
                result[current_section] = "\n".join(section_content).strip()
            current_section = "title"
            # Wyciągnij treść po dwukropku
            content = line.split(":", 1)[1].strip() if ":" in line else ""
            section_content = [content] if content else []
        elif line_upper.startswith("OPIS:") or line_upper.startswith("DESCRIPTION:"):
            if current_section and section_content:
                result[current_section] = "\n".join(section_content).strip()
            current_section = "description"
            content = line.split(":", 1)[1].strip() if ":" in line else ""
            section_content = [content] if content else []
        elif line_upper.startswith("PODSUMOWANIE:") or line_upper.startswith("SUMMARY:"):
            if current_section and section_content:
                result[current_section] = "\n".join(section_content).strip()
            current_section = "summary"
            content = line.split(":", 1)[1].strip() if ":" in line else ""
            section_content = [content] if content else []
        elif current_section:
            section_content.append(line)

    # Zapisz ostatnią sekcję
    if current_section and section_content:
        result[current_section] = "\n".join(section_content).strip()

    # Fallbacki jeśli parsowanie nie zadziałało
    if not result["title"]:
        # Użyj pierwszej linii draftu lub wygenerowanego tekstu
        first_line = fallback_draft.strip().split("\n")[0][:80]
        result["title"] = first_line if first_line else "Aktualizacja projektu"

    if not result["description"]:
        result["description"] = generated_text if generated_text else fallback_draft

    if not result["summary"]:
        # Użyj pierwszych 150 znaków opisu
        result["summary"] = result["description"][:150] + "..." if len(result["description"]) > 150 else result["description"]

    return result
