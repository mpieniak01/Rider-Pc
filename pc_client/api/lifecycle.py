"""Lifecycle management for application startup, shutdown, and background tasks."""

import asyncio
import contextlib
import logging
import time
from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Optional, Callable, Awaitable, Tuple

from fastapi import FastAPI
from pc_client.adapters import RestAdapter
from pc_client.cache import CacheManager
from pc_client.config import Settings
from pc_client.core.watchdog import ServiceWatchdog
from pc_client.queue import TaskQueue
from pc_client.queue.task_queue import TaskQueueWorker
from pc_client.telemetry import ZMQTelemetryPublisher
from pc_client.api.task_utils import build_vision_frame_task, build_voice_asr_task, build_voice_tts_task
from pc_client.api.config_utils import load_provider_config, get_provider_capabilities
from pc_client.core.remote_safety import finite_number
from pc_client.api.telemetry_snapshot import (
    adapter_source,
    received_snapshot,
    transport_failure,
    unavailable_snapshot,
)

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
    if not settings.test_mode and (
        settings.enable_telemetry or settings.enable_vision_offload or settings.enable_voice_offload
    ):
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

    vision_config = load_provider_config(settings.vision_provider_config_path, "vision")
    if settings.vision_model == "mock":
        vision_config["use_mock"] = True

    provider = None
    try:
        from pc_client.providers import VisionProvider

        provider = VisionProvider(vision_config)
        await provider.initialize()
    except Exception as exc:  # pragma: no cover - defensive log
        logger.error(f"Failed to initialize VisionProvider: {exc}")
        if provider is not None:
            await provider.shutdown()
        return

    await ensure_task_queue(app)
    app.state.providers["vision"] = provider
    app.state.vision_offload_enabled = True
    app.state.vision_frame_priority = int(vision_config.get("frame_priority") or 1)

    logger.info(
        "Vision offload enabled (queue size=%s, frame priority=%s)",
        settings.task_queue_max_size,
        app.state.vision_frame_priority,
    )


async def initialize_voice_pipeline(app: FastAPI) -> None:
    """Enable TaskQueue + VoiceProvider for ASR/TTS offload.

    Rozszerzona diagnostyka:
    - Loguje przyczyny braku inicjalizacji
    - Proponuje akcje naprawcze
    - Ustawia flagi diagnostyczne w app.state
    """
    settings: Settings = app.state.settings

    # Diagnostyka: zapisz status dla UI
    app.state.voice_provider_status = {
        "requested": voice_offload_requested(settings),
        "initialized": False,
        "error": None,
        "hint": None,
    }

    if not voice_offload_requested(settings):
        logger.info(
            "Voice offload disabled (ENABLE_PROVIDERS=%s, ENABLE_TASK_QUEUE=%s, ENABLE_VOICE_OFFLOAD=%s)",
            settings.enable_providers,
            settings.enable_task_queue,
            settings.enable_voice_offload,
        )
        app.state.voice_provider_status["hint"] = (
            "Włącz ENABLE_PROVIDERS=true, ENABLE_TASK_QUEUE=true i ENABLE_VOICE_OFFLOAD=true w .env"
        )
        return

    voice_config = load_provider_config(settings.voice_provider_config_path, "voice")
    if settings.voice_model == "mock":
        voice_config["use_mock"] = True

    provider = None
    try:
        from pc_client.providers import VoiceProvider

        provider = VoiceProvider(voice_config)
        await provider.initialize()
    except Exception as exc:  # pragma: no cover
        error_msg = str(exc)
        logger.error(f"Failed to initialize VoiceProvider: {error_msg}")
        app.state.voice_provider_status["error"] = error_msg

        # Diagnostyka: proponowane akcje
        if "whisper" in error_msg.lower():
            hint = "Sprawdź lokalny runtime ASR i istniejący plik asr_model_path; instalacja jest osobnym krokiem."
            logger.warning(f"VoiceProvider diagnostic hint: {hint}")
            app.state.voice_provider_status["hint"] = hint
        elif "piper" in error_msg.lower():
            hint = "Sprawdź lokalny runtime Piper i istniejące tts_model_path oraz plik JSON."
            logger.warning(f"VoiceProvider diagnostic hint: {hint}")
            app.state.voice_provider_status["hint"] = hint
        else:
            hint = "Sprawdź konfigurację w config/providers.toml"
            app.state.voice_provider_status["hint"] = hint

        if provider is not None:
            await provider.shutdown()
            app.state.voice_provider_status["capabilities"] = provider.get_telemetry().get("capabilities", {})
        return

    await ensure_task_queue(app)
    app.state.providers["voice"] = provider
    app.state.voice_offload_enabled = True
    app.state.voice_provider_status["initialized"] = True
    telemetry = provider.get_telemetry()
    app.state.voice_provider_status.update(
        {
            "capabilities": telemetry.get("capabilities", {}),
            "mode": telemetry.get("mode"),
            "ready": telemetry.get("ready", False),
            "error": telemetry.get("error"),
        }
    )
    app.state.voice_asr_priority = int(voice_config.get("asr_priority") or voice_config.get("priority") or 5)
    app.state.voice_tts_priority = int(voice_config.get("tts_priority") or (app.state.voice_asr_priority + 1))

    logger.info(
        "Voice offload enabled (ASR priority=%s, TTS priority=%s)",
        app.state.voice_asr_priority,
        app.state.voice_tts_priority,
    )


async def initialize_text_provider(app: FastAPI) -> None:
    """Initialize TextProvider for chat/NLU offload.

    Rozszerzona diagnostyka:
    - Loguje przyczyny braku inicjalizacji
    - Proponuje akcje naprawcze
    - Ustawia flagi diagnostyczne w app.state
    """
    settings: Settings = app.state.settings

    # Diagnostyka: zapisz status dla UI
    app.state.text_provider_status = {
        "requested": text_offload_requested(settings),
        "initialized": False,
        "error": None,
        "hint": None,
    }

    if not text_offload_requested(settings):
        logger.info(
            "Text offload disabled (ENABLE_PROVIDERS=%s, ENABLE_TEXT_OFFLOAD=%s)",
            settings.enable_providers,
            settings.enable_text_offload,
        )
        app.state.text_provider_status["hint"] = "Włącz ENABLE_PROVIDERS=true i ENABLE_TEXT_OFFLOAD=true w .env"
        return

    text_config = load_provider_config(settings.text_provider_config_path, "text")
    if settings.text_model == "mock":
        text_config["use_mock"] = True

    # Pass through backend/env configuration for external providers
    if settings.text_provider_backend:
        text_config.setdefault("backend", settings.text_provider_backend)

    if settings.gemini_api_key:
        text_config.setdefault("gemini_api_key", settings.gemini_api_key)
    if settings.gemini_model:
        text_config.setdefault("gemini_model", settings.gemini_model)
    if settings.gemini_endpoint:
        text_config.setdefault("gemini_endpoint", settings.gemini_endpoint)

    if settings.openai_api_key:
        text_config.setdefault("openai_api_key", settings.openai_api_key)
    if settings.openai_model:
        text_config.setdefault("openai_model", settings.openai_model)
    if settings.openai_base_url:
        text_config.setdefault("openai_base_url", settings.openai_base_url)

    provider = None
    try:
        from pc_client.providers import TextProvider

        provider = TextProvider(text_config)
        await provider.initialize()
    except Exception as exc:  # pragma: no cover
        error_msg = str(exc)
        logger.error(f"Failed to initialize TextProvider: {error_msg}")
        app.state.text_provider_status["error"] = error_msg

        # Diagnostyka: proponowane akcje
        if "ollama" in error_msg.lower() or "connection" in error_msg.lower():
            hint = "Ollama może być niedostępna. Uruchom: ollama serve"
            logger.warning(f"TextProvider diagnostic hint: {hint}")
            app.state.text_provider_status["hint"] = hint
        else:
            hint = "Sprawdź konfigurację w config/providers_text_local.toml"
            app.state.text_provider_status["hint"] = hint

        if provider is not None:
            await provider.shutdown()
        return

    app.state.text_provider = provider
    app.state.text_provider_status["initialized"] = True
    logger.info("Text offload enabled (model=%s)", text_config.get("model", settings.text_model))


async def sync_data_periodically(app: FastAPI):
    """
    Background task to periodically sync data from Rider-PI.

    Args:
        app: FastAPI application instance
    """
    cache: CacheManager = app.state.cache

    logger.info("Starting periodic data sync...")

    def _update_tracking(data: Dict[str, Any]) -> None:
        """Persist latest tracking snapshot without clobbering on bad payloads."""
        tracking_remote = data.get("tracking")
        if isinstance(tracking_remote, dict):
            app.state.control_state["tracking"] = tracking_remote

    async def _fetch_and_cache(
        cache_key: str,
        coroutine_factory: Callable[[], Awaitable[Any]],
        on_success: Optional[Callable[[Any], None]] = None,
    ) -> Tuple[str, Optional[Any], Optional[str]]:
        """
        Zachowaj dane przy awarii, ale oznacz transport jako offline/stale.

        Returns a tuple of (cache_key, payload or None, error_message or None).
        """
        source = adapter_source(app.state.rest_adapter)
        try:
            payload = await coroutine_factory()
            if not isinstance(payload, dict) or not payload:
                raise ValueError("invalid_snapshot_response")
            if transport_failure(payload):
                raise RuntimeError(str(payload["error"]))
        except Exception as exc:  # pragma: no cover - network/adapter failures
            failed = unavailable_snapshot(
                cache.get(cache_key), source=source, error=str(exc) or type(exc).__name__, attempted_at=time.time()
            )
            cache.set(cache_key, failed)
            return cache_key, failed, failed["error"]

        observed = received_snapshot(payload, source=source, received_at=time.time())
        cache.set(cache_key, observed)
        if on_success and not observed.get("error") and observed.get("offline") is not True:
            try:
                on_success(observed)
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("Post-cache hook failed for %s: %s", cache_key, exc)
        return cache_key, observed, observed.get("error")

    while True:
        try:
            adapter: Optional[RestAdapter] = app.state.rest_adapter
            if adapter is None:
                logger.warning("REST adapter unavailable; skipping sync iteration")
                for cache_key in (
                    "healthz",
                    "state",
                    "sysinfo",
                    "vision_snap_info",
                    "vision_obstacle",
                    "app_metrics",
                    "camera_resource",
                    "lcd_resource",
                    "bus_health",
                ):
                    cache.set(
                        cache_key,
                        unavailable_snapshot(
                            cache.get(cache_key), source="pi", error="pi_offline", attempted_at=time.time()
                        ),
                    )
                await asyncio.sleep(2)
                continue

            fetch_plan = [
                ("healthz", adapter.get_healthz, None),
                ("state", adapter.get_state, _update_tracking),
                ("sysinfo", adapter.get_sysinfo, None),
                ("vision_snap_info", adapter.get_vision_snap_info, None),
                ("vision_obstacle", adapter.get_vision_obstacle, None),
                ("app_metrics", adapter.get_app_metrics, None),
                ("camera_resource", adapter.get_camera_resource, None),
                ("lcd_resource", lambda: adapter.get_resource("lcd"), None),
                ("bus_health", adapter.get_bus_health, None),
            ]

            results = await asyncio.gather(
                *[
                    _fetch_and_cache(cache_key, coro_factory, on_success)
                    for cache_key, coro_factory, on_success in fetch_plan
                ],
                return_exceptions=True,
            )

            cache_data: Dict[str, Any] = {}
            for result in results:
                if isinstance(result, BaseException):  # pragma: no cover - defensive
                    logger.debug("Background sync task raised: %s", result)
                    continue
                cache_key, payload, err = result
                if err:
                    logger.warning("Snapshot unavailable for %s: %s", cache_key, err)
                if payload is not None:
                    cache_data[cache_key] = payload

            # Cleanup expired cache entries
            cache.cleanup_expired()

        except Exception as e:  # pragma: no cover - defensive
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
        observed = parsed.timestamp()
        return observed if finite_number(observed) and observed > 0 else None
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
    timestamp = _last_modified_timestamp(headers)
    app.state.last_camera_frame = {
        "content": content,
        "media_type": media_type,
        "timestamp": timestamp,
        "received_at": time.time(),
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

    normalized = base_url.rstrip("/")

    async def _heartbeat_loop() -> None:
        while True:
            adapter: Optional[RestAdapter] = app.state.rest_adapter
            if not adapter:
                await asyncio.sleep(5)
                continue
            payload = {
                "base_url": normalized,
                "capabilities": get_provider_capabilities(settings, app.state.providers, app.state.text_provider),
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
        original = data
        if topic == "vision.obstacle" and isinstance(data, dict):
            data = received_snapshot(
                data, source=adapter_source(getattr(app.state, "rest_adapter", None)), received_at=time.time()
            )
        cache.set(f"zmq:{topic}", data)
        # Surowe klatki/audio zostają wyłącznie wejściem kolejki, nie SSE/backlogiem.
        if topic not in {"vision.frame.offload", "voice.asr.request", "voice.tts.request"}:
            manager = getattr(app.state, "sse_manager", None)
            if manager is not None:
                manager.publish({"topic": topic, "data": original, "source": "pi/bus", "received_at": time.time()})
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
        provider = app.state.providers.get("voice")
        if not app.state.voice_offload_enabled or not app.state.task_queue or provider is None:
            return

        from pc_client.providers.base import TaskType

        if TaskType.VOICE_ASR not in provider.get_supported_tasks():
            return
        task = build_voice_asr_task(data, app.state.voice_asr_priority)
        if task is None:
            return

        enqueued = await app.state.task_queue.enqueue(task)
        if not enqueued:
            logger.warning("Voice ASR queue full – dropped request %s", task.task_id)

    async def voice_tts_handler(topic: str, data: Dict[str, Any]):
        """Enqueue TTS requests coming from Rider-PI."""
        provider = app.state.providers.get("voice")
        if not app.state.voice_offload_enabled or not app.state.task_queue or provider is None:
            return

        from pc_client.providers.base import TaskType

        if TaskType.VOICE_TTS not in provider.get_supported_tasks():
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

    # Initialize REST adapter (mock, real or disabled based on settings)
    pi_rest_disabled = settings.disable_rider_pi_adapter
    if pi_rest_disabled:
        app.state.rest_adapter = None
        logger.info("REST adapter disabled via DISABLE_RIDER_PI_ADAPTER")
    elif settings.test_mode:
        from pc_client.adapters import MockRestAdapter

        app.state.rest_adapter = MockRestAdapter()
        logger.info("REST adapter initialized in TEST MODE (using MockRestAdapter)")
    else:
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

    # Initialize ZMQ subscriber (skip in test mode or when Rider-PI adapter disabled)
    if not settings.test_mode and not pi_rest_disabled:
        from pc_client.adapters import ZmqSubscriber

        app.state.zmq_subscriber = ZmqSubscriber(
            settings.zmq_pub_endpoint,
            topics=[
                "vision.*",
                "voice.*",
                "motion.*",
                "robot.*",
                "navigator.*",
                "tracking.*",
                "camera.*",
                "mapper.map.data",
                "imu.data",
            ],
        )

        # Register ZMQ handlers to update cache
        cache_handler, vision_frame_handler, voice_asr_handler, voice_tts_handler = create_zmq_handlers(
            app, app.state.cache
        )

        for topic in [
            "vision.*",
            "voice.*",
            "motion.*",
            "robot.*",
            "navigator.*",
            "tracking.*",
            "camera.*",
            "mapper.map.data",
            "imu.data",
        ]:
            app.state.zmq_subscriber.subscribe_topic(topic, cache_handler)

        if app.state.vision_offload_enabled:
            app.state.zmq_subscriber.subscribe_topic("vision.frame.offload", vision_frame_handler)

        if app.state.voice_offload_enabled:
            app.state.zmq_subscriber.subscribe_topic("voice.asr.request", voice_asr_handler)
            app.state.zmq_subscriber.subscribe_topic("voice.tts.request", voice_tts_handler)

        # Start ZMQ subscriber in background
        asyncio.create_task(app.state.zmq_subscriber.start())
        logger.info("ZMQ subscriber started")
    elif settings.test_mode:
        logger.info("ZMQ subscriber skipped in TEST MODE")
    else:
        logger.info("ZMQ subscriber skipped (DISABLE_RIDER_PI_ADAPTER=true)")

    # Skip provider heartbeat in test mode or when adapter disabled
    if not settings.test_mode and not pi_rest_disabled:
        await start_provider_heartbeat(app)
    elif pi_rest_disabled:
        logger.info("Provider heartbeat disabled (DISABLE_RIDER_PI_ADAPTER=true)")

    if not pi_rest_disabled:
        if app.state.camera_sync_task:
            app.state.camera_sync_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await app.state.camera_sync_task
        app.state.camera_sync_task = asyncio.create_task(sync_camera_frame_periodically(app))
        logger.info("Camera frame sync task started")

        # Start background sync task
        app.state.sync_task = asyncio.create_task(sync_data_periodically(app))
        logger.info("Background sync task started")
    else:
        app.state.camera_sync_task = None
        app.state.sync_task = None
        logger.info("Rider-PI sync tasks skipped (adapter disabled)")

    # Initialize and start ServiceWatchdog if enabled
    app.state.service_watchdog = None
    if settings.auto_heal_enabled and not settings.test_mode:
        watchdog = ServiceWatchdog(
            service_manager=app.state.service_manager,
            monitored_services=app.state.service_manager.monitored_services,
            max_retry_count=settings.max_retry_count,
            retry_window_seconds=settings.retry_window_seconds,
            sse_publish_fn=app.state.sse_manager.publish,
        )
        await watchdog.start()
        app.state.service_watchdog = watchdog
        monitored_count = len(settings.monitored_services) if settings.monitored_services else "none"
        logger.info(
            "ServiceWatchdog started (monitored=%s services, max_retry=%d, window=%ds)",
            monitored_count,
            settings.max_retry_count,
            settings.retry_window_seconds,
        )
    else:
        logger.info("ServiceWatchdog disabled (AUTO_HEAL_ENABLED=false)")


async def shutdown_event(app: FastAPI):
    """Cleanup on shutdown."""
    logger.info("Shutting down Rider-PC Client API server...")

    # Stop ServiceWatchdog
    if getattr(app.state, "service_watchdog", None):
        await app.state.service_watchdog.stop()
        logger.info("ServiceWatchdog stopped")

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

    # Close GitHub adapter
    from pc_client.api.routers.project_router import cleanup_github_adapter

    await cleanup_github_adapter()

    logger.info("Shutdown complete")
