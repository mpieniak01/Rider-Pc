"""Provider control and AI mode management endpoints."""

import logging
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from pc_client.adapters import RestAdapter
from pc_client.cache import CacheManager
from pc_client.config import Settings
from pc_client.providers import TextProvider
from pc_client.providers.base import TaskEnvelope, TaskType, TaskStatus
from pc_client.api.lifecycle import load_provider_config

logger = logging.getLogger(__name__)

router = APIRouter()


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


@router.get("/providers/capabilities")
async def providers_capabilities(request: Request) -> JSONResponse:
    """Expose provider capabilities for Rider-PI handshake."""
    settings: Settings = request.app.state.settings
    return JSONResponse(content=get_provider_capabilities(settings))


@router.get("/api/providers/capabilities")
async def providers_capabilities_api(request: Request) -> JSONResponse:
    """API-prefixed alias."""
    return await providers_capabilities(request)


@router.post("/providers/text/generate")
async def providers_text_generate(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    """Generate text via TextProvider (chat/NLU)."""
    provider: Optional[TextProvider] = request.app.state.text_provider
    if provider is None:
        raise HTTPException(status_code=503, detail="Text provider not initialized")

    prompt = (payload or {}).get("prompt")
    if not prompt:
        raise HTTPException(status_code=400, detail="Missing 'prompt' in payload")

    task = TaskEnvelope(
        task_id=f"text-generate-{uuid.uuid4()}",
        task_type=TaskType.TEXT_GENERATE,
        payload={
            "prompt": prompt,
            "max_tokens": payload.get("max_tokens"),
            "temperature": payload.get("temperature"),
            "system_prompt": payload.get("system_prompt"),
        },
        meta={"mode": payload.get("mode", "chat"), "context": payload.get("context")},
    )

    result = await provider.process_task(task)
    if result.status != TaskStatus.COMPLETED:
        raise HTTPException(status_code=502, detail=result.error or "Text generation failed")

    response_body = {
        "task_id": result.task_id,
        "text": (result.result or {}).get("text"),
        "meta": result.meta,
        "from_cache": (result.result or {}).get("from_cache", False),
        "tokens_used": (result.result or {}).get("tokens_used"),
    }
    return JSONResponse(content=response_body)


@router.post("/api/providers/text/generate")
async def providers_text_generate_api(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    return await providers_text_generate(request, payload)


def _default_provider_state() -> Dict[str, Any]:
    provider_domains = ("voice", "text", "vision")
    return {
        "domains": {
            domain: {"mode": "local", "status": "local_only", "changed_ts": None} for domain in provider_domains
        },
        "pc_health": {"reachable": False, "status": "unknown"},
    }


def _default_provider_health() -> Dict[str, Any]:
    provider_domains = ("voice", "text", "vision")
    return {
        domain: {
            "status": "unknown",
            "latency_ms": 0.0,
            "success_rate": 1.0,
            "last_check": None,
        }
        for domain in provider_domains
    }


def _default_ai_mode() -> Dict[str, Any]:
    return {"mode": "local", "changed_ts": None}


@router.get("/api/system/ai-mode")
async def get_ai_mode_route(request: Request) -> JSONResponse:
    """Fetch AI mode from Rider-PI or cache."""
    adapter: Optional[RestAdapter] = request.app.state.rest_adapter
    cache: CacheManager = request.app.state.cache
    cached = cache.get("ai_mode", _default_ai_mode())
    if adapter:
        try:
            data = await adapter.get_ai_mode()
            if isinstance(data, dict) and data:
                cache.set("ai_mode", data)
                return JSONResponse(content=data)
        except Exception as exc:
            logger.error("Failed to fetch AI mode from Rider-PI: %s", exc)
    if cached:
        return JSONResponse(content=cached)
    raise HTTPException(status_code=502, detail="Unable to fetch AI mode")


async def _set_ai_mode(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    mode = str(payload.get("mode") or "").lower()
    if mode not in {"local", "pc_offload"}:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid mode. Must be 'local' or 'pc_offload'"},
        )
    adapter: Optional[RestAdapter] = request.app.state.rest_adapter
    cache: CacheManager = request.app.state.cache
    if not adapter:
        return JSONResponse(
            status_code=503,
            content={"error": "REST adapter not initialized"},
        )
    result = await adapter.set_ai_mode(mode)
    if isinstance(result, dict) and "error" not in result:
        cache.set("ai_mode", result)
        return JSONResponse(content=result)
    logger.error("Failed to set AI mode via Rider-PI: %s", result)
    return JSONResponse(content=result or {"error": "Failed to set mode"}, status_code=502)


@router.put("/api/system/ai-mode")
async def put_ai_mode_route(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    return await _set_ai_mode(request, payload)


@router.post("/api/system/ai-mode")
async def post_ai_mode_route(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    return await _set_ai_mode(request, payload)


@router.get("/api/providers/state")
async def providers_state(request: Request) -> JSONResponse:
    """Fetch provider state information."""
    adapter: Optional[RestAdapter] = request.app.state.rest_adapter
    cache: CacheManager = request.app.state.cache
    cached = cache.get("providers_state", _default_provider_state())
    if adapter:
        try:
            data = await adapter.get_providers_state()
            if isinstance(data, dict) and data:
                cache.set("providers_state", data)
                return JSONResponse(content=data)
        except Exception as exc:
            logger.error("Failed to fetch provider state from Rider-PI: %s", exc)
    if cached:
        return JSONResponse(content=cached)
    raise HTTPException(status_code=502, detail="Unable to fetch provider state")


@router.patch("/api/providers/{domain}")
async def update_provider(request: Request, domain: str, payload: Dict[str, Any]) -> JSONResponse:
    """Update provider configuration for a specific domain."""
    adapter: Optional[RestAdapter] = request.app.state.rest_adapter
    cache: CacheManager = request.app.state.cache
    
    domain = (domain or "").lower()
    valid_domains = {"voice", "text", "vision"}
    if domain not in valid_domains:
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid domain. Must be one of {sorted(valid_domains)}"},
        )
    target = str(payload.get("target") or "").lower()
    if target not in {"local", "pc"}:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid target. Must be 'local' or 'pc'."},
        )
    if adapter:
        forwarded_payload = {"target": target}
        if "force" in payload:
            forwarded_payload["force"] = bool(payload.get("force"))
        result = await adapter.patch_provider(domain, forwarded_payload)
        if isinstance(result, dict) and "error" not in result:
            cached_state = cache.get("providers_state", _default_provider_state())
            domains = cached_state.get("domains") if isinstance(cached_state, dict) else None
            if isinstance(domains, dict) and domain in domains:
                domains[domain]["mode"] = target
                domains[domain]["status"] = "pc_active" if target == "pc" else "local_only"
                domains[domain]["changed_ts"] = time.time()
                cache.set("providers_state", cached_state)
            return JSONResponse(content=result)
        logger.error("Failed to patch provider via Rider-PI: %s", result)
        return JSONResponse(content=result or {"error": "Failed to update provider"}, status_code=502)

    cached_state = cache.get("providers_state", _default_provider_state())
    domains = cached_state.setdefault("domains", {})
    domain_entry = domains.get(domain, {"mode": "local", "status": "local_only", "changed_ts": None})
    domain_entry["mode"] = target
    domain_entry["status"] = "pc_active" if target == "pc" else "local_only"
    domain_entry["changed_ts"] = time.time()
    domains[domain] = domain_entry
    cache.set("providers_state", cached_state)
    return JSONResponse(
        content={"success": True, "domain": domain, "new_state": domain_entry},
        status_code=200,
    )


@router.get("/api/providers/health")
async def providers_health(request: Request) -> JSONResponse:
    """Fetch provider health metrics."""
    adapter: Optional[RestAdapter] = request.app.state.rest_adapter
    cache: CacheManager = request.app.state.cache
    cached = cache.get("providers_health", _default_provider_health())
    if adapter:
        try:
            data = await adapter.get_providers_health()
            if isinstance(data, dict) and data:
                cache.set("providers_health", data)
                return JSONResponse(content=data)
        except Exception as exc:
            logger.error("Failed to fetch provider health from Rider-PI: %s", exc)
    if cached:
        return JSONResponse(content=cached)
    raise HTTPException(status_code=502, detail="Unable to fetch provider health")


@router.get("/api/services/graph")
async def services_graph(request: Request) -> JSONResponse:
    """
    Get system services graph for system dashboard.
    Mock implementation for Phase 3.
    """
    cache: CacheManager = request.app.state.cache
    
    graph_data = cache.get(
        "services_graph",
        {
            "generated_at": time.time(),
            "nodes": [
                {
                    "label": "FastAPI Server",
                    "unit": "pc_client.service",
                    "status": "active",
                    "group": "api",
                    "since": "2025-11-12 14:00:00",
                    "description": "Main REST API server",
                    "edges_out": ["cache", "zmq"],
                },
                {
                    "label": "Cache Manager",
                    "unit": "cache.service",
                    "status": "active",
                    "group": "data",
                    "since": "2025-11-12 14:00:00",
                    "description": "SQLite cache for data buffering",
                    "edges_out": [],
                },
                {
                    "label": "ZMQ Subscriber",
                    "unit": "zmq.service",
                    "status": "active",
                    "group": "messaging",
                    "since": "2025-11-12 14:00:00",
                    "description": "Real-time data stream subscriber",
                    "edges_out": ["cache"],
                },
                {
                    "label": "Voice Provider",
                    "unit": "voice.provider",
                    "status": "active",
                    "group": "providers",
                    "since": "2025-11-12 14:00:00",
                    "description": "ASR/TTS processing",
                    "edges_out": ["task_queue"],
                },
                {
                    "label": "Vision Provider",
                    "unit": "vision.provider",
                    "status": "active",
                    "group": "providers",
                    "since": "2025-11-12 14:00:00",
                    "description": "Object detection and frame processing",
                    "edges_out": ["task_queue"],
                },
                {
                    "label": "Text Provider",
                    "unit": "text.provider",
                    "status": "active",
                    "group": "providers",
                    "since": "2025-11-12 14:00:00",
                    "description": "LLM text generation and NLU",
                    "edges_out": ["task_queue", "cache"],
                },
                {
                    "label": "Task Queue",
                    "unit": "task_queue.service",
                    "status": "active",
                    "group": "queue",
                    "since": "2025-11-12 14:00:00",
                    "description": "Redis-based task queue",
                    "edges_out": [],
                },
                {
                    "label": "Telemetry Publisher",
                    "unit": "telemetry.service",
                    "status": "active",
                    "group": "monitoring",
                    "since": "2025-11-12 14:00:00",
                    "description": "ZMQ telemetry and Prometheus metrics",
                    "edges_out": [],
                },
            ],
            "edges": [],
        },
    )
    return JSONResponse(content=graph_data)
