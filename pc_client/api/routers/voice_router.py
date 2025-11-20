"""Voice provider endpoints for chat/TTS UI."""

import base64
import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from pc_client.adapters import RestAdapter
from pc_client.api.task_utils import build_voice_tts_task
from pc_client.providers import VoiceProvider
from pc_client.providers.base import TaskStatus

logger = logging.getLogger(__name__)

router = APIRouter()

_MOCK_WAV_BASE64 = (
    "UklGRqQ+AABXQVZFZm10IBAAAAABAAEAgD4AAAB9AAACABAAZGF0YYA+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
)


def _decode_audio_payload(audio_data: Optional[str]) -> bytes:
    """Decode base64 audio data, falling back to a short silent WAV."""
    if not audio_data:
        logger.warning("Missing audio data from voice provider, using fallback sample")
        return base64.b64decode(_MOCK_WAV_BASE64)
    try:
        return base64.b64decode(audio_data)
    except Exception:
        logger.warning("Invalid audio payload, using fallback sample")
        return base64.b64decode(_MOCK_WAV_BASE64)


def _fallback_tts_response(reason: str) -> Response:
    """Return silent audio when real TTS is unavailable."""
    logger.warning("Returning fallback TTS audio: %s", reason)
    headers = {
        "X-Voice-Fallback": "pc-mock",
        "X-Voice-Error": reason,
    }
    return Response(content=_decode_audio_payload(None), media_type="audio/wav", headers=headers)


def _lookup_service_state(request: Request, alias: str) -> Optional[Dict[str, Any]]:
    """Find service state in app.state.services."""
    services: List[Dict[str, Any]] = getattr(request.app.state, "services", [])
    for svc in services:
        if svc.get("unit") == alias or svc.get("alias") == alias:
            return svc
    return None


def _get_voice_provider(request: Request) -> Optional[VoiceProvider]:
    """Return VoiceProvider instance if available."""
    providers: Dict[str, Any] = getattr(request.app.state, "providers", {})
    provider = providers.get("voice")
    return provider if isinstance(provider, VoiceProvider) else None


def _local_voice_provider_entry(request: Request) -> Dict[str, Any]:
    """Build description of the local VoiceProvider fallback."""
    provider = _get_voice_provider(request)
    telemetry = provider.get_telemetry() if provider else {}
    initialized = bool(telemetry.get("initialized"))
    detail = "Provider gotowy" if initialized else "Provider nieaktywny"
    entry = {
        "id": "local",
        "label": "Rider-PC Piper (lokalny)",
        "backend": "piper",
        "voice": telemetry.get("tts_model") or request.app.state.settings.voice_model,
        "model": telemetry.get("tts_model"),
        "description": "Lokalny provider TTS uruchamiany na Rider-PC.",
        "service": "voice.provider",
        "status": {
            "state": "ok" if initialized else "warn",
            "detail": detail,
            "updated": time.time(),
        },
    }
    service_state = _lookup_service_state(request, "voice.provider")
    if service_state:
        entry["service_state"] = service_state
    return entry


def _local_provider_catalog(request: Request) -> Dict[str, Any]:
    """Return fallback provider catalog for Rider-PC."""
    providers = [_local_voice_provider_entry(request)]
    # Mirror cloud placeholders so UI still lists selectable entries.
    providers.append(
        {
            "id": "openai",
            "label": "OpenAI gpt-4o-mini-tts",
            "backend": "openai",
            "voice": "alloy",
            "model": "gpt-4o-mini-tts",
            "description": "Chmurowy TTS OpenAI (wymaga Rider-PI).",
            "service": None,
            "status": {"state": "warn", "detail": "Proxy niedostępne w Rider-PC"},
        }
    )
    providers.append(
        {
            "id": "google",
            "label": "Google Gemini Kore",
            "backend": "google",
            "voice": "Kore",
            "model": "gemini-2.5-flash-preview-tts",
            "description": "Chmurowy TTS Gemini (obsługiwany na Rider-PI).",
            "service": None,
            "status": {"state": "warn", "detail": "Proxy niedostępne w Rider-PC"},
        }
    )
    return {"providers": providers, "source": "pc-local"}


@router.get("/api/voice/providers")
async def voice_providers(request: Request) -> JSONResponse:
    """Expose voice provider catalog, preferring Rider-PI data."""
    adapter: Optional[RestAdapter] = request.app.state.rest_adapter
    if adapter:
        remote = await adapter.get_voice_providers()
        if isinstance(remote, dict) and not remote.get("error"):
            return JSONResponse(remote)
        logger.warning("Falling back to local voice providers: %s", remote.get("error") if remote else "unknown error")
    return JSONResponse(_local_provider_catalog(request))


@router.post("/api/voice/providers/test")
async def voice_providers_test(request: Request, payload: Optional[Dict[str, Any]] = None) -> JSONResponse:
    """Run provider self-tests."""
    adapter: Optional[RestAdapter] = request.app.state.rest_adapter
    if adapter:
        remote = await adapter.test_voice_providers(payload or {})
        if isinstance(remote, dict) and not remote.get("error"):
            return JSONResponse(remote)
        logger.warning(
            "Falling back to local voice provider test: %s", remote.get("error") if remote else "unknown error"
        )

    provider = _get_voice_provider(request)
    if not provider or not provider.get_telemetry().get("initialized"):
        return JSONResponse({"ok": False, "error": "Voice provider not initialized"}, status_code=503)

    ids = (payload or {}).get("providers") or ["local"]
    results = []
    for provider_id in ids:
        if provider_id != "local":
            results.append({"id": provider_id, "state": "warn", "detail": "Provider obsługiwany tylko na Rider-PI"})
            continue
        try:
            priority = getattr(request.app.state, "voice_tts_priority", 6)
            envelope = build_voice_tts_task({"text": "Test TTS Rider-PC", "voice": "local"}, priority)
            if not envelope:
                raise ValueError("Nie udało się zbudować zadania TTS")
            result = await provider.process_task(envelope)
            if result.status == TaskStatus.COMPLETED:
                results.append(
                    {
                        "id": provider_id,
                        "state": "ok",
                        "detail": "Działa poprawnie",
                        "latency_ms": round(result.processing_time_ms or 0.0),
                    }
                )
            else:
                results.append(
                    {"id": provider_id, "state": "error", "detail": result.error or "Błąd wykonania zadania"}
                )
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Voice provider test failed: %s", exc)
            results.append({"id": provider_id, "state": "error", "detail": str(exc)})

    return JSONResponse({"ok": True, "results": results})


@router.post("/api/voice/tts")
async def voice_tts(request: Request, payload: Optional[Dict[str, Any]] = None) -> Response:
    """Synthesize speech locally or proxy to Rider-PI."""
    provider = _get_voice_provider(request)
    if provider and provider.get_telemetry().get("initialized"):
        task_payload = payload or {}
        priority = getattr(request.app.state, "voice_tts_priority", 6)
        envelope = build_voice_tts_task(task_payload, priority)
        if not envelope:
            return JSONResponse({"ok": False, "error": "Brak tekstu do odczytu"}, status_code=400)
        result = await provider.process_task(envelope)
        if result.status != TaskStatus.COMPLETED or not result.result:
            return _fallback_tts_response(result.error or "voice provider failed")
        audio_bytes = _decode_audio_payload(result.result.get("audio_data"))
        headers = {
            "X-Voice-Provider": task_payload.get("provider") or "local",
            "X-Voice-Engine": (result.meta or {}).get("engine", "piper"),
        }
        return Response(content=audio_bytes, media_type="audio/wav", headers=headers)

    adapter: Optional[RestAdapter] = request.app.state.rest_adapter
    if adapter:
        try:
            content, media_type = await adapter.post_voice_tts(payload or {})
            return Response(content=content, media_type=media_type)
        except Exception as exc:  # pragma: no cover - network failure
            logger.error("Voice TTS proxy failed: %s", exc)
            return _fallback_tts_response(str(exc) or "voice tts proxy failed")

    return _fallback_tts_response("voice provider unavailable")
