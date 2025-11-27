"""Model management API endpoints."""

import logging
from typing import Any, Dict

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

        return JSONResponse(
            content={
                "local": installed,
                "ollama": ollama,
                "total_local": len(installed),
                "total_ollama": len(ollama),
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

    logger.info("Model binding updated: slot=%s, provider=%s, model=%s", slot, provider, model)

    return JSONResponse(
        content={
            "success": True,
            "slot": slot,
            "provider": provider,
            "model": model,
            "note": "Configuration updated in memory. Restart may be required for full effect.",
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

        return JSONResponse(content=manager.get_all_models())
    except Exception as e:
        logger.error("Failed to get models summary: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
