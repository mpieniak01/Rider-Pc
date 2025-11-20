"""Chat endpoints for Rider-PC UI."""

import uuid
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from pc_client.adapters import RestAdapter
from pc_client.providers import TextProvider
from pc_client.providers.base import TaskEnvelope, TaskStatus, TaskType

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_text_provider(request: Request) -> Optional[TextProvider]:
    provider = getattr(request.app.state, "text_provider", None)
    return provider if isinstance(provider, TextProvider) else None


def _extract_prompt(payload: Dict[str, Any]) -> Optional[str]:
    for key in ("msg", "message", "prompt", "text", "content"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


@router.post("/api/chat/send")
async def chat_send(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    """Handle chat requests locally or proxy to Rider-PI."""
    provider = _get_text_provider(request)
    adapter: Optional[RestAdapter] = request.app.state.rest_adapter

    if provider and provider.get_telemetry().get("initialized"):
        prompt = _extract_prompt(payload)
        if not prompt:
            return JSONResponse({"ok": False, "error": "missing prompt"}, status_code=400)
        task = TaskEnvelope(
            task_id=f"text-chat-{uuid.uuid4()}",
            task_type=TaskType.TEXT_GENERATE,
            payload={
                "prompt": prompt,
                "max_tokens": payload.get("max_tokens"),
                "temperature": payload.get("temperature"),
            },
            meta={
                "mode": payload.get("mode", "chat"),
                "context": payload.get("context"),
                "user": payload.get("user"),
            },
        )
        result = await provider.process_task(task)
        if result.status != TaskStatus.COMPLETED or not result.result:
            return JSONResponse(
                {"ok": False, "error": result.error or "chat generation failed"},
                status_code=502,
            )
        reply = (result.result or {}).get("text") or ""
        return JSONResponse(
            {
                "ok": True,
                "reply": reply,
                "meta": result.meta,
                "task_id": result.task_id,
            }
        )

    if adapter:
        remote = await adapter.post_chat_send(payload or {})
        if isinstance(remote, dict) and "error" not in remote:
            return JSONResponse(remote)
        logger.error("Chat proxy failed: %s", remote.get("error") if isinstance(remote, dict) else remote)
        return JSONResponse({"ok": False, "error": remote.get("error", "chat proxy failed")}, status_code=502)

    return JSONResponse({"ok": False, "error": "chat provider unavailable"}, status_code=503)
