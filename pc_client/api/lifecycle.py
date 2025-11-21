"""Lifecycle management for application startup, shutdown, and background tasks."""

import asyncio
import contextlib
import logging
import time
from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Optional

from fastapi import FastAPI
from pc_client.adapters import RestAdapter
from pc_client.cache import CacheManager
from pc_client.config import Settings
from pc_client.providers import VisionProvider, VoiceProvider, TextProvider
from pc_client.queue import TaskQueue
from pc_client.queue.task_queue import TaskQueueWorker
from pc_client.telemetry import ZMQTelemetryPublisher
from pc_client.api.task_utils import build_vision_frame_task, build_voice_asr_task, build_voice_tts_task
from pc_client.api.config_utils import load_provider_config, get_provider_capabilities

logger = logging.getLogger(__name__)


def vision_offload_requested(settings: Settings) -> bool:
    """Return True if all toggles required for vision offload are enabled."""
    return settings.enable_providers and settings.enable_task_queue and settings.enable_vision_offload


def voice_offload_requested(settings: Settings) -> bool:
    """Return True if toggles required for voice offload are enabled."""
    return settings.enable_providers and settings.enable_task_queue and settings.enable_voice_offload


def text_offload_requested(settings: Settings) -> bool:
    """Return True if toggles required for text offload are enabled."""
    return settings.enable_providers and settings.enable_text_offload


async def ensure_task_queue(app: FastAPI) -> None:
    """Ensure task queue + worker exist when at least one provider is enabled."""
    settings: Settings = app.state.settings

    if app.state.task_queue:
        return

    queue = TaskQueue(max_size=settings.task_queue_max_size)

    telemetry_endpoint = None
    if settings.enable_telemetry or settings.enable_vision_offload or settings.enable_voice_offload:
        telemetry_endpoint = settings.telemetry_zmq_endpoint

    telemetry_publisher = (
        ZMQTelemetryPublisher(telemetry_endpoint) if telemetry_endpoint else ZMQTelemetryPublisher(None)
    )
    worker = TaskQueueWorker(queue, app.state.providers, telemetry_publisher=telemetry_publisher)
    worker_task = asyncio.create_task(worker.start())

    app.state.task_queue = queue
    app.state.provider_worker = worker
    app.state.provider_worker_task = worker_task
    app.state.telemetry_publisher = telemetry_publisher

    logger.info("Task queue initialized (max_size=%s)", settings.task_queue_max_size)


async def initialize_vision_pipeline(app: FastAPI) -> None:
    """Create TaskQueue/Provider worker for vision frame offload if enabled."""
    settings: Settings = app.state.settings

    if not vision_offload_requested(settings):
        logger.info(
            "Vision offload disabled (ENABLE_PROVIDERS=%s, ENABLE_TASK_QUEUE=%s, ENABLE_VISION_OFFLOAD=%s)",
            settings.enable_providers,
            settings.enable_task_queue,
            settings.enable_vision_offload,
        )
        return

    await ensure_task_queue(app)

    vision_config = load_provider_config(settings.vision_provider_config_path, "vision")
    if settings.vision_model == "mock":
        vision_config.setdefault("use_mock", True)

    provider = VisionProvider(vision_config)

    try:
        await provider.initialize()
    except Exception as exc:  # pragma: no cover - defensive log
        logger.error(f"Failed to initialize VisionProvider: {exc}")
        await provider.shutdown()
        return

    app.state.providers["vision"] = provider
    app.state.vision_offload_enabled = True
    app.state.vision_frame_priority = int(vision_config.get("frame_priority") or 1)

    logger.info(
        "Vision offload enabled (queue size=%s, frame priority=%s)",
        settings.task_queue_max_size,
        app.state.vision_frame_priority,
    )


async def initialize_voice_pipeline(app: FastAPI) -> None:
    """Enable TaskQueue + VoiceProvider for ASR/TTS offload."""
    settings: Settings = app.state.settings

    if not voice_offload_requested(settings):
        logger.info(
            "Voice offload disabled (ENABLE_PROVIDERS=%s, ENABLE_TASK_QUEUE=%s, ENABLE_VOICE_OFFLOAD=%s)",
            settings.enable_providers,
            settings.enable_task_queue,
            settings.enable_voice_offload,
        )
        return

    await ensure_task_queue(app)

    voice_config = load_provider_config(settings.voice_provider_config_path, "voice")
    if settings.voice_model == "mock":
        voice_config.setdefault("use_mock", True)

    provider = VoiceProvider(voice_config)

    try:
        await provider.initialize()
    except Exception as exc:  # pragma: no cover
        logger.error(f"Failed to initialize VoiceProvider: {exc}")
        await provider.shutdown()
        return

    app.state.providers["voice"] = provider
    app.state.voice_offload_enabled = True
    app.state.voice_asr_priority = int(voice_config.get("asr_priority") or voice_config.get("priority") or 5)
    app.state.voice_tts_priority = int(voice_config.get("tts_priority") or (app.state.voice_asr_priority + 1))

    logger.info(
        "Voice offload enabled (ASR priority=%s, TTS priority=%s)",
        app.state.voice_asr_priority,
        app.state.voice_tts_priority,
    )


async def initialize_text_provider(app: FastAPI) -> None:
    """Initialize TextProvider for chat/NLU offload."""
    settings: Settings = app.state.settings

    if not text_offload_requested(settings):
        logger.info(
            "Text offload disabled (ENABLE_PROVIDERS=%s, ENABLE_TEXT_OFFLOAD=%s)",
            settings.enable_providers,
            settings.enable_text_offload,
        )
        return

    text_config = load_provider_config(settings.text_provider_config_path, "text")
    if settings.text_model == "mock":
        text_config.setdefault("use_mock", True)

    provider = TextProvider(text_config)

    try:
        await provider.initialize()
    except Exception as exc:  # pragma: no cover
        logger.error(f"Failed to initialize TextProvider: {exc}")
        await provider.shutdown()
        return

    app.state.text_provider = provider
    logger.info("Text offload enabled (model=%s)", text_config.get("model", settings.text_model))


async def sync_data_periodically(app: FastAPI):
    """
    Background task to periodically sync data from Rider-PI.

    Args:
        app: FastAPI application instance
    """
    adapter: RestAdapter = app.state.rest_adapter
    cache: CacheManager = app.state.cache

    logger.info("Starting periodic data sync...")

    while True:
        try:
            # Fetch data from Rider-PI REST API
            healthz_data = await adapter.get_healthz()
            cache.set("healthz", healthz_data)

            state_data = await adapter.get_state()
            cache.set("state", state_data)
            tracking_remote = state_data.get("tracking")
            if isinstance(tracking_remote, dict):
                app.state.control_state["tracking"] = tracking_remote

            sysinfo_data = await adapter.get_sysinfo()
            cache.set("sysinfo", sysinfo_data)

            snap_info_data = await adapter.get_vision_snap_info()
            cache.set("vision_snap_info", snap_info_data)

            obstacle_data = await adapter.get_vision_obstacle()
            cache.set("vision_obstacle", obstacle_data)

            metrics_data = await adapter.get_app_metrics()
            cache.set("app_metrics", metrics_data)

            camera_resource_data = await adapter.get_camera_resource()
            cache.set("camera_resource", camera_resource_data)

            bus_health_data = await adapter.get_bus_health()
            cache.set("bus_health", bus_health_data)

            logger.debug("Data sync completed")

            # Cleanup expired cache entries
            cache.cleanup_expired()

        except Exception as e:
            logger.error(f"Error in data sync: {e}")

        # Wait before next sync (2 seconds to match frontend refresh)
        await asyncio.sleep(2)


def _last_modified_timestamp(headers: Dict[str, str]) -> Optional[float]:
    """Return UNIX timestamp if Last-Modified header is present."""
    last_modified = next((value for key, value in headers.items() if key.lower() == "last-modified"), None)
    if not last_modified:
        return None
    try:
        parsed = parsedate_to_datetime(last_modified)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except Exception as exc:  # pragma: no cover - defensive parsing
        logger.debug("Failed to parse Last-Modified header '%s': %s", last_modified, exc)
        return None


async def _fetch_and_store_camera_frame(app: FastAPI) -> None:
    """Fetch the latest camera frame from Rider-PI and cache it locally."""
    adapter: Optional[RestAdapter] = app.state.rest_adapter
    if adapter is None:
        logger.debug("REST adapter unavailable, skipping camera frame fetch")
        return

    content, media_type, headers = await adapter.fetch_binary("/camera/last")
    timestamp = _last_modified_timestamp(headers) or time.time()
    app.state.last_camera_frame = {
        "content": content,
        "media_type": media_type,
        "timestamp": timestamp,
    }


async def sync_camera_frame_periodically(app: FastAPI, interval: float = 0.8):
    """
    Background task to continuously refresh the cached camera frame.
    """
    logger.info("Starting camera frame sync task (interval=%.2fs)", interval)
    try:
        while True:
            try:
                await _fetch_and_store_camera_frame(app)
            except Exception as exc:
                logger.debug("Camera frame sync failed: %s", exc)
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info("Camera frame sync task cancelled")
        raise


async def start_provider_heartbeat(app: FastAPI):
    """Start provider heartbeat loop to register with Rider-PI."""
    settings: Settings = app.state.settings

    base_url = (settings.pc_public_base_url or "").strip()
    if not base_url:
        logger.info("PC_PUBLIC_BASE_URL not set; skipping provider heartbeat loop")
        return

    capabilities = get_provider_capabilities(settings)
    normalized = base_url.rstrip("/")

    async def _heartbeat_loop():
        while True:
            adapter: Optional[RestAdapter] = app.state.rest_adapter
            if not adapter:
                await asyncio.sleep(5)
                continue
            payload = {
                "base_url": normalized,
                "capabilities": capabilities,
                "timestamp": time.time(),
            }
            try:
                result = await adapter.post_pc_heartbeat(payload)
                if isinstance(result, dict) and result.get("error"):
                    logger.warning("Provider heartbeat rejected: %s", result["error"])
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Provider heartbeat failed: %s", exc)
            await asyncio.sleep(5)

    if app.state.provider_heartbeat_task:
        app.state.provider_heartbeat_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await app.state.provider_heartbeat_task
    app.state.provider_heartbeat_task = asyncio.create_task(_heartbeat_loop())


def create_zmq_handlers(app: FastAPI, cache: CacheManager):
    """Create and return ZMQ message handlers."""

    def cache_handler(topic: str, data: Dict[str, Any]):
        """Handler to cache ZMQ messages."""
        cache.set(f"zmq:{topic}", data)
        logger.debug(f"Cached ZMQ message for topic: {topic}")

    async def vision_frame_handler(topic: str, data: Dict[str, Any]):
        """Convert Rider-PI vision frames into queue tasks."""
        if not app.state.vision_offload_enabled or not app.state.task_queue:
            return

        tracking_state = app.state.control_state.get("tracking") or {}
        tracking_snapshot: Optional[Dict[str, Any]] = None
        if tracking_state:
            tracking_snapshot = dict(tracking_state)

        task = build_vision_frame_task(data, app.state.vision_frame_priority, tracking_snapshot)
        if task is None:
            return

        enqueued = await app.state.task_queue.enqueue(task)
        if not enqueued:
            logger.warning("Vision task queue is full – dropped frame %s", task.task_id)

    async def voice_asr_handler(topic: str, data: Dict[str, Any]):
        """Enqueue ASR requests coming from Rider-PI."""
        if not app.state.voice_offload_enabled or not app.state.task_queue:
            return

        task = build_voice_asr_task(data, app.state.voice_asr_priority)
        if task is None:
            return

        enqueued = await app.state.task_queue.enqueue(task)
        if not enqueued:
            logger.warning("Voice ASR queue full – dropped request %s", task.task_id)

    async def voice_tts_handler(topic: str, data: Dict[str, Any]):
        """Enqueue TTS requests coming from Rider-PI."""
        if not app.state.voice_offload_enabled or not app.state.task_queue:
            return

        task = build_voice_tts_task(data, app.state.voice_tts_priority)
        if task is None:
            return

        enqueued = await app.state.task_queue.enqueue(task)
        if not enqueued:
            logger.warning("Voice TTS queue full – dropped request %s", task.task_id)

    return cache_handler, vision_frame_handler, voice_asr_handler, voice_tts_handler


async def startup_event(app: FastAPI):
    """Initialize connections on startup."""
    logger.info("Starting Rider-PC Client API server...")

    settings: Settings = app.state.settings

    # Initialize REST adapter
    app.state.rest_adapter = RestAdapter(
        base_url=settings.rider_pi_base_url,
        secure_mode=settings.secure_mode,
        mtls_cert_path=settings.mtls_cert_path,
        mtls_key_path=settings.mtls_key_path,
        mtls_ca_path=settings.mtls_ca_path,
    )
    logger.info(f"REST adapter initialized for {settings.rider_pi_base_url}")

    # Initialize provider pipelines
    await initialize_vision_pipeline(app)
    await initialize_voice_pipeline(app)
    await initialize_text_provider(app)

    # Initialize ZMQ subscriber
    from pc_client.adapters import ZmqSubscriber

    app.state.zmq_subscriber = ZmqSubscriber(
        settings.zmq_pub_endpoint, topics=["vision.*", "voice.*", "motion.*", "robot.*", "navigator.*"]
    )

    # Register ZMQ handlers to update cache
    cache_handler, vision_frame_handler, voice_asr_handler, voice_tts_handler = create_zmq_handlers(
        app, app.state.cache
    )

    for topic in ["vision.*", "voice.*", "motion.*", "robot.*", "navigator.*"]:
        app.state.zmq_subscriber.subscribe_topic(topic, cache_handler)

    if app.state.vision_offload_enabled:
        app.state.zmq_subscriber.subscribe_topic("vision.frame.offload", vision_frame_handler)

    if app.state.voice_offload_enabled:
        app.state.zmq_subscriber.subscribe_topic("voice.asr.request", voice_asr_handler)
        app.state.zmq_subscriber.subscribe_topic("voice.tts.request", voice_tts_handler)

    # Start ZMQ subscriber in background
    asyncio.create_task(app.state.zmq_subscriber.start())
    logger.info("ZMQ subscriber started")

    await start_provider_heartbeat(app)

    if app.state.camera_sync_task:
        app.state.camera_sync_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await app.state.camera_sync_task
    app.state.camera_sync_task = asyncio.create_task(sync_camera_frame_periodically(app))
    logger.info("Camera frame sync task started")

    # Start background sync task
    app.state.sync_task = asyncio.create_task(sync_data_periodically(app))
    logger.info("Background sync task started")


async def shutdown_event(app: FastAPI):
    """Cleanup on shutdown."""
    logger.info("Shutting down Rider-PC Client API server...")

    # Stop sync task
    if app.state.sync_task:
        app.state.sync_task.cancel()
        try:
            await app.state.sync_task
        except asyncio.CancelledError:
            # Task cancellation is expected during shutdown; ignore.
            pass
    if app.state.provider_heartbeat_task:
        app.state.provider_heartbeat_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await app.state.provider_heartbeat_task

    if app.state.camera_sync_task:
        app.state.camera_sync_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await app.state.camera_sync_task

    # Stop task queue worker / providers
    if app.state.provider_worker:
        await app.state.provider_worker.stop()

    if app.state.provider_worker_task:
        try:
            await app.state.provider_worker_task
        except asyncio.CancelledError:
            # Cancellation is expected during shutdown; ignore.
            pass

    if app.state.telemetry_publisher:
        app.state.telemetry_publisher.close()

    for provider in app.state.providers.values():
        try:
            await provider.shutdown()
        except Exception as exc:
            logger.warning(f"Failed to shutdown provider {provider}: {exc}")

    if app.state.text_provider:
        try:
            await app.state.text_provider.shutdown()
        except Exception as exc:
            logger.warning(f"Failed to shutdown TextProvider: {exc}")

    # Stop ZMQ subscriber
    if app.state.zmq_subscriber:
        await app.state.zmq_subscriber.stop()

    # Close REST adapter
    if app.state.rest_adapter:
        await app.state.rest_adapter.close()

    logger.info("Shutdown complete")
