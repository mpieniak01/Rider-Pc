"""Self-healing watchdog for monitoring and auto-restarting failed services."""

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from pc_client.core.service_manager import ServiceManager

logger = logging.getLogger(__name__)


class ServiceWatchdog:
    """
    Watchdog that monitors local services and auto-restarts failed ones.

    Implements a "Single Retry" policy: each service gets one automatic restart
    attempt within a configurable time window before requiring manual intervention.
    """

    def __init__(
        self,
        service_manager: ServiceManager,
        monitored_services: Optional[List[str]] = None,
        max_retry_count: int = 1,
        retry_window_seconds: int = 300,
        check_interval_seconds: float = 10.0,
        sse_publish_fn: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        """
        Initialize the ServiceWatchdog.

        Args:
            service_manager: ServiceManager instance for checking status and restarting services.
            monitored_services: List of service unit names to monitor. If None or empty,
                                uses the service manager's default local services.
            max_retry_count: Maximum number of auto-heal attempts per service (default: 1).
            retry_window_seconds: Time window after which retry counter resets if service
                                  was running stably (default: 300s = 5 minutes).
            check_interval_seconds: Interval between service status checks (default: 10s).
            sse_publish_fn: Optional callback to publish SSE notifications.
        """
        self._service_manager = service_manager
        self._monitored_services = monitored_services or []
        self._max_retry_count = max_retry_count
        self._retry_window_seconds = retry_window_seconds
        self._check_interval_seconds = check_interval_seconds
        self._sse_publish_fn = sse_publish_fn

        # Track retry attempts and last failure timestamps per service
        # Format: {unit: {"count": int, "last_failure_ts": float}}
        self._retry_state: Dict[str, Dict[str, Any]] = {}

        self._running = False
        self._task: Optional[asyncio.Task] = None

    def _get_monitored_units(self, services: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter services to only those that should be monitored."""
        if not self._monitored_services:
            # If no specific services configured, monitor all local services
            return [s for s in services if s.get("is_local", True)]

        # Filter to only monitored services
        monitored_set = set(self._monitored_services)
        return [s for s in services if s.get("unit") in monitored_set]

    def _should_auto_heal(self, unit: str) -> bool:
        """Check if a service should be auto-healed based on retry count."""
        state = self._retry_state.get(unit, {"count": 0})
        return state.get("count", 0) < self._max_retry_count

    def _maybe_reset_retry_counter(self, unit: str, current_time: float) -> None:
        """Reset retry counter if service has been stable for retry_window_seconds."""
        state = self._retry_state.get(unit)
        if not state:
            return

        last_failure_ts = state.get("last_failure_ts", 0)
        if current_time - last_failure_ts >= self._retry_window_seconds:
            # Service has been stable long enough, reset counter
            if state.get("count", 0) > 0:
                logger.info(
                    "Service %s stable for %ds, resetting retry counter",
                    unit,
                    self._retry_window_seconds,
                )
                state["count"] = 0
                state["last_failure_ts"] = 0

    def _record_failure(self, unit: str, current_time: float) -> None:
        """Record a failure and increment retry counter."""
        if unit not in self._retry_state:
            self._retry_state[unit] = {"count": 0, "last_failure_ts": 0}

        self._retry_state[unit]["count"] += 1
        self._retry_state[unit]["last_failure_ts"] = current_time

    def _publish_sse(self, event_type: str, unit: str, message: str) -> None:
        """Publish an SSE notification if callback is configured."""
        if self._sse_publish_fn:
            self._sse_publish_fn({
                "type": event_type,
                "unit": unit,
                "message": message,
                "ts": time.time(),
            })

    async def _check_and_heal_services(self) -> None:
        """Check service statuses and attempt auto-healing for failed services."""
        current_time = time.time()

        try:
            services = await self._service_manager.get_local_services_async()
        except Exception as exc:
            logger.error("Failed to fetch local services for watchdog: %s", exc)
            return

        monitored = self._get_monitored_units(services)

        for service in monitored:
            unit = service.get("unit", "")
            active_state = str(service.get("active", "")).lower()

            # Reset counter if service is active (includes running sub-state)
            if active_state == "active":
                self._maybe_reset_retry_counter(unit, current_time)
                continue

            # Check if service is failed
            if active_state != "failed":
                continue

            # Service is failed - check if we should auto-heal
            retry_state = self._retry_state.get(unit, {"count": 0})
            current_count = retry_state.get("count", 0)

            if current_count >= self._max_retry_count:
                # Already exhausted retries, log but don't restart
                logger.error(
                    "Auto-healing failed for %s. Manual intervention required. "
                    "(Retry limit %d reached)",
                    unit,
                    self._max_retry_count,
                )
                self._publish_sse(
                    "watchdog.exhausted",
                    unit,
                    f"Auto-healing failed for {unit}. Manual intervention required.",
                )
                continue

            # Attempt auto-heal
            logger.warning(
                "Auto-healing service %s (Attempt %d/%d)",
                unit,
                current_count + 1,
                self._max_retry_count,
            )
            self._publish_sse(
                "watchdog.healing",
                unit,
                f"Auto-healing service {unit} (Attempt {current_count + 1}/{self._max_retry_count})",
            )

            try:
                result = await self._service_manager.control_service(unit, "restart")
                if result.get("ok"):
                    logger.info("Auto-heal restart initiated for %s", unit)
                else:
                    logger.error(
                        "Auto-heal restart failed for %s: %s",
                        unit,
                        result.get("error", "unknown error"),
                    )
            except Exception as exc:
                logger.error("Auto-heal restart exception for %s: %s", unit, exc)

            # Record the failure and increment counter regardless of restart result
            self._record_failure(unit, current_time)

    async def _watchdog_loop(self) -> None:
        """Main watchdog loop that periodically checks services."""
        logger.info(
            "ServiceWatchdog started (check_interval=%.1fs, max_retry=%d, retry_window=%ds)",
            self._check_interval_seconds,
            self._max_retry_count,
            self._retry_window_seconds,
        )

        while self._running:
            try:
                await self._check_and_heal_services()
            except Exception as exc:
                logger.error("Watchdog loop error: %s", exc)

            await asyncio.sleep(self._check_interval_seconds)

    async def start(self) -> None:
        """Start the watchdog background task."""
        if self._running:
            logger.warning("ServiceWatchdog is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._watchdog_loop())
        logger.info("ServiceWatchdog task created")

    async def stop(self) -> None:
        """Stop the watchdog background task."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("ServiceWatchdog stopped")

    def get_retry_state(self) -> Dict[str, Dict[str, Any]]:
        """Return current retry state for diagnostics."""
        return dict(self._retry_state)
