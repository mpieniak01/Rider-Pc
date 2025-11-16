"""Circuit breaker pattern implementation for fallback handling."""

import logging
import time
from enum import Enum
from typing import Callable, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 2  # Successes before closing from half-open
    timeout_seconds: float = 60  # Time before attempting recovery


class CircuitBreaker:
    """
    Circuit breaker for handling task failures with fallback.

    This ensures critical tasks (e.g., obstacle avoidance) can fall back
    to local processing if the PC offload is failing or slow.
    """

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        """
        Initialize circuit breaker.

        Args:
            config: Circuit breaker configuration
        """
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.logger = logging.getLogger("[bridge] CircuitBreaker")

    def call(self, func: Callable[..., Any], fallback: Optional[Callable[..., Any]] = None, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Primary function to call
            fallback: Fallback function if circuit is open
            *args: Arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from func or fallback
        """
        # Check if circuit should transition to half-open
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.logger.info("Circuit transitioning to HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
            else:
                self.logger.warning("Circuit is OPEN, using fallback")
                if fallback:
                    return fallback(*args, **kwargs)
                raise Exception("Circuit breaker is open and no fallback provided")

        # Try to execute the function
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            self.logger.error(f"Function failed: {e}")

            # Use fallback if available
            if fallback:
                self.logger.info("Using fallback function")
                return fallback(*args, **kwargs)
            raise

    async def call_async(
        self, func: Callable[..., Any], fallback: Optional[Callable[..., Any]] = None, *args, **kwargs
    ) -> Any:
        """
        Execute async function with circuit breaker protection.

        Args:
            func: Primary async function to call
            fallback: Fallback async function if circuit is open
            *args: Arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from func or fallback
        """
        # Check if circuit should transition to half-open
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.logger.info("Circuit transitioning to HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
            else:
                self.logger.warning("Circuit is OPEN, using fallback")
                if fallback:
                    return await fallback(*args, **kwargs)
                raise Exception("Circuit breaker is open and no fallback provided")

        # Try to execute the function
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            self.logger.error(f"Async function failed: {e}")

            # Use fallback if available
            if fallback:
                self.logger.info("Using fallback function")
                return await fallback(*args, **kwargs)
            raise

    def _on_success(self):
        """Handle successful execution."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.logger.info("Circuit transitioning to CLOSED")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    def _on_failure(self):
        """Handle failed execution."""
        self.last_failure_time = time.time()
        self.failure_count += 1

        if self.state == CircuitState.HALF_OPEN:
            self.logger.warning("Circuit transitioning to OPEN (failure in HALF_OPEN)")
            self.state = CircuitState.OPEN
            self.success_count = 0
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.logger.warning(f"Circuit transitioning to OPEN (failures: {self.failure_count})")
                self.state = CircuitState.OPEN

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True

        elapsed = time.time() - self.last_failure_time
        return elapsed >= self.config.timeout_seconds

    def get_state(self) -> dict:
        """Get current circuit breaker state."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "success_threshold": self.config.success_threshold,
                "timeout_seconds": self.config.timeout_seconds,
            },
        }

    def reset(self):
        """Manually reset the circuit breaker."""
        self.logger.info("Circuit breaker manually reset")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
