"""Model management API endpoints."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from pc_client.core.model_manager import ModelManager


class BindModelRequest(BaseModel):
    """Request body for model binding."""

    slot: str = Field(..., description="Target slot (vision, voice_asr, voice_tts, text)")
    provider: str = Field(..., description="Provider name (yolo, whisper, piper, ollama, openai)")
    model: str = Field(..., description="Model name or identifier")

    @field_validator("slot", "provider", "model")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Validate that fields are not empty or whitespace-only."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or whitespace-only")
        return v.strip()


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/models", tags=["models"])


def get_model_manager(request: Request) -> ModelManager:
    """Get or create ModelManager instance from app state."""
    if not hasattr(request.app.state, "model_manager") or request.app.state.model_manager is None:
        request.app.state.model_manager = ModelManager()
    return request.app.state.model_manager


async def _fetch_remote_models(request: Request) -> List[Dict[str, Any]]:
    """Fetch Rider-PI model inventory via RestAdapter."""
    adapter = getattr(request.app.state, "rest_adapter", None)
    if adapter is None:
        return []

    try:
        remote_payload = await adapter.get_remote_models()
    except Exception as exc:  # pragma: no cover - network errors
        logger.debug("Failed to fetch Rider-PI models: %s", exc)
        return []

    if not isinstance(remote_payload, dict):
        return []

    # Try "models" key first, fall back to "local" for backward compatibility
    models = remote_payload.get("models", remote_payload.get("local"))
    return models if isinstance(models, list) else []


async def _switch_provider_mode(request: Request, slot: str, target: str) -> Optional[Dict[str, Any]]:
    """Switch Rider-PI provider mode for a domain."""
    adapter = getattr(request.app.state, "rest_adapter", None)
    if adapter is None:
        return None

    domain_map = {
        "vision": "vision",
        "voice_asr": "voice",
        "voice_tts": "voice",
        "text": "text",
    }
    domain = domain_map.get(slot)
    if domain is None:
        return None

    try:
        return await adapter.patch_provider(domain, {"target": target, "reason": "models_ui"})
    except Exception as exc:  # pragma: no cover - Rider-PI offline
        logger.error("Failed to switch provider %s to %s: %s", domain, target, exc)
        return {"error": str(exc)}


@router.get("/installed")
async def get_installed_models(request: Request) -> JSONResponse:
    """
    List installed model files from the local models directory.

    Returns list of detected model files with metadata:
    - name: Model filename without extension
    - path: Relative path within models directory
    - type: Detected model type (yolo, whisper, piper, etc.)
    - category: Model category (vision, voice_asr, voice_tts, text)
    - size_mb: File size in megabytes
    - format: File format (pt, onnx, tflite, gguf)
    """
    manager = get_model_manager(request)

    try:
        # Scan for local models
        manager.scan_local_models()

        # Try to get Ollama models
        try:
            await manager.scan_ollama_models()
        except Exception as e:
            logger.debug("Could not scan Ollama models: %s", e)

        installed = manager.get_installed_models()
        ollama = manager.get_ollama_models()
        remote = await _fetch_remote_models(request)

        return JSONResponse(
            content={
                "local": installed,
                "ollama": ollama,
                "remote": remote,
                "total_local": len(installed),
                "total_ollama": len(ollama),
                "total_remote": len(remote),
            }
        )
    except Exception as e:
        logger.error("Failed to get installed models: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/active")
async def get_active_models(request: Request) -> JSONResponse:
    """
    Get currently active model configuration.

    Returns the active model bindings from providers.toml:
    - vision: Active vision/detection model
    - voice_asr: Active speech recognition model
    - voice_tts: Active text-to-speech model
    - text: Active LLM model
    """
    manager = get_model_manager(request)

    try:
        active = manager.get_active_models()
        return JSONResponse(content=active.to_dict())
    except Exception as e:
        logger.error("Failed to get active models: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/bind")
async def bind_model(request: Request, payload: BindModelRequest) -> JSONResponse:
    """
    Bind a model to a specific slot.

    Request body:
    - slot: Target slot (vision, voice_asr, voice_tts, text)
    - provider: Provider name (yolo, whisper, piper, ollama, openai)
    - model: Model name or identifier

    Note: This updates the in-memory configuration. For persistence,
    changes should be written to providers.toml.
    """
    slot = payload.slot
    provider = payload.provider
    model = payload.model

    valid_slots = {"vision", "voice_asr", "voice_tts", "text"}
    if slot not in valid_slots:
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid slot. Must be one of: {sorted(valid_slots)}"},
        )

    manager = get_model_manager(request)

    # Update in-memory configuration
    active = manager.get_active_models()
    slot_config = getattr(active, slot, {})
    if not isinstance(slot_config, dict):
        slot_config = {}
    slot_config = {**slot_config, "provider": provider, "model": model}
    setattr(active, slot, slot_config)
    manager.persist_active_model(slot, model)
    provider_switch = await _switch_provider_mode(request, slot, "pc")

    logger.info("Model binding updated: slot=%s, provider=%s, model=%s", slot, provider, model)

    return JSONResponse(
        content={
            "success": True,
            "slot": slot,
            "provider": provider,
            "model": model,
            "provider_switch": provider_switch,
        }
    )


@router.get("/summary")
async def get_models_summary(request: Request) -> JSONResponse:
    """
    Get a summary of the model configuration and inventory.

    Returns combined view of:
    - installed: List of local model files
    - ollama: List of Ollama models
    - active: Current active model configuration
    """
    manager = get_model_manager(request)

    try:
        # Refresh data
        manager.scan_local_models()
        try:
            await manager.scan_ollama_models()
        except Exception:
            pass  # Ollama may not be available

        manager.get_active_models()
        remote = await _fetch_remote_models(request)
        payload = manager.get_all_models()
        payload["remote"] = remote

        return JSONResponse(content=payload)
    except Exception as e:
        logger.error("Failed to get models summary: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
