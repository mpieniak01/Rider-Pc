"""Task building utilities for converting ZMQ/REST payloads into TaskEnvelope objects."""

import logging
import uuid
from typing import Any, Dict, Optional

from pc_client.providers.base import TaskEnvelope, TaskType

logger = logging.getLogger(__name__)


def build_vision_frame_task(
    payload: Dict[str, Any], priority: int, tracking_state: Optional[Dict[str, Any]] = None
) -> Optional[TaskEnvelope]:
    """Convert a vision.frame.offload payload into a TaskEnvelope."""
    frame_data = payload.get("frame_jpeg") or payload.get("frame_data")
    if not frame_data:
        logger.debug("Skipping vision frame without frame_jpeg/frame_data")
        return None

    frame_id = payload.get("frame_id") or payload.get("rid") or str(uuid.uuid4())
    timestamp = payload.get("timestamp") or payload.get("ts")

    task_payload: Dict[str, Any] = {
        "frame_data": frame_data,
        "frame_id": frame_id,
        "timestamp": timestamp,
        "format": payload.get("format", "jpeg"),
    }

    for key in ("rid", "roi", "meta"):
        if key in payload:
            task_payload[key] = payload[key]

    task_meta = {"source_topic": "vision.frame.offload", "frame_id": frame_id}
    if tracking_state:
        task_meta["tracking_state"] = tracking_state

    return TaskEnvelope(
        task_id=f"vision-frame-{frame_id}",
        task_type=TaskType.VISION_FRAME,
        payload=task_payload,
        meta=task_meta,
        priority=priority,
    )


def build_voice_asr_task(payload: Dict[str, Any], priority: int) -> Optional[TaskEnvelope]:
    """Convert voice.asr.request payload into TaskEnvelope."""
    audio_data = payload.get("chunk_pcm") or payload.get("audio_data")
    if not audio_data:
        logger.debug("Skipping voice request without audio data")
        return None

    request_id = payload.get("request_id") or payload.get("seq") or str(uuid.uuid4())
    sample_rate = payload.get("sample_rate")
    lang = payload.get("lang") or payload.get("language")
    format_hint = payload.get("format", "wav")

    task_payload = {
        "audio_data": audio_data,
        "format": format_hint,
        "sample_rate": sample_rate,
        "language": lang,
    }

    task_meta = {
        "source_topic": "voice.asr.request",
        "request_id": request_id,
        "rid": payload.get("rid"),
        "timestamp": payload.get("ts"),
    }

    return TaskEnvelope(
        task_id=f"voice-asr-{request_id}",
        task_type=TaskType.VOICE_ASR,
        payload=task_payload,
        meta=task_meta,
        priority=priority,
    )


def build_voice_tts_task(payload: Dict[str, Any], priority: int) -> Optional[TaskEnvelope]:
    """Convert voice.tts.request payload into TaskEnvelope."""
    text = payload.get("text")
    if not text:
        logger.debug("Skipping voice TTS request without text")
        return None

    request_id = payload.get("request_id") or payload.get("seq") or str(uuid.uuid4())

    task_payload = {
        "text": text,
        "voice": payload.get("voice"),
        "speed": payload.get("speed"),
    }
    task_meta = {
        "source_topic": "voice.tts.request",
        "request_id": request_id,
        "ts": payload.get("ts"),
    }

    return TaskEnvelope(
        task_id=f"voice-tts-{request_id}",
        task_type=TaskType.VOICE_TTS,
        payload=task_payload,
        meta=task_meta,
        priority=priority,
    )
