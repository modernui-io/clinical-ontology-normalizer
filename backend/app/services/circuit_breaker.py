"""Circuit breaker pattern implementation for external services.

This module provides circuit breaker functionality to prevent cascading failures:
- Automatic failure detection and circuit opening
- Configurable failure thresholds and recovery timeouts
- Half-open state for gradual recovery
- Per-service circuit breakers with metrics
"""

from __future__ import annotations

import asyncio
import functools
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(str, Enum):
    """State of a circuit breaker."""

    CLOSED = "closed"  # Normal operation, requests flow through
    OPEN = "open"  # Circuit tripped, requests fail immediately
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for a circuit breaker."""

    # Number of failures before opening the circuit
    failure_threshold: int = 5

    # Number of successes in half-open state to close the circuit
    success_threshold: int = 3

    # Seconds to wait before entering half-open state
    recovery_timeout: float = 30.0

    # Seconds to keep metrics history
    metrics_window: float = 60.0

    # Maximum concurrent requests in half-open state
    half_open_max_requests: int = 3

    # Exceptions that should trip the circuit
    trip_exceptions: tuple[type[Exception], ...] = (Exception,)

    # Exceptions that should NOT trip the circuit (e.g., validation errors)
    ignore_exceptions: tuple[type[Exception], ...] = ()


@dataclass
class CircuitBreakerMetrics:
    """Metrics for a circuit breaker."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0  # Calls rejected due to open circuit
    last_failure_time: datetime | None = None
    last_success_time: datetime | None = None
    state_changes: list[tuple[datetime, CircuitState]] = field(default_factory=list)
    recent_failures: list[tuple[datetime, str]] = field(default_factory=list)
    current_state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    consecutive_successes: int = 0

    def record_success(self) -> None:
        """Record a successful call."""
        now = datetime.now(timezone.utc)
        self.total_calls += 1
        self.successful_calls += 1
        self.last_success_time = now
        self.consecutive_failures = 0
        self.consecutive_successes += 1

    def record_failure(self, error: str) -> None:
        """Record a failed call."""
        now = datetime.now(timezone.utc)
        self.total_calls += 1
        self.failed_calls += 1
        self.last_failure_time = now
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.recent_failures.append((now, error))

        # Keep only recent failures
        cutoff = now.timestamp() - 60.0
        self.recent_failures = [
            (t, e) for t, e in self.recent_failures
            if t.timestamp() > cutoff
        ]

    def record_rejection(self) -> None:
        """Record a rejected call (circuit open)."""
        self.total_calls += 1
        self.rejected_calls += 1

    def record_state_change(self, new_state: CircuitState) -> None:
        """Record a state change."""
        now = datetime.now(timezone.utc)
        self.current_state = new_state
        self.state_changes.append((now, new_state))

        # Keep only last 100 state changes
        if len(self.state_changes) > 100:
            self.state_changes = self.state_changes[-100:]

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate."""
        if self.total_calls == 0:
            return 0.0
        return self.failed_calls / self.total_calls

    @property
    def rejection_rate(self) -> float:
        """Calculate rejection rate."""
        if self.total_calls == 0:
            return 0.0
        return self.rejected_calls / self.total_calls

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rejected_calls": self.rejected_calls,
            "failure_rate": round(self.failure_rate, 4),
            "rejection_rate": round(self.rejection_rate, 4),
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "current_state": self.current_state.value,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_success_time": self.last_success_time.isoformat() if self.last_success_time else None,
            "recent_failures_count": len(self.recent_failures),
        }


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit is open."""

    def __init__(self, service_name: str, remaining_seconds: float) -> None:
        self.service_name = service_name
        self.remaining_seconds = remaining_seconds
        super().__init__(
            f"Circuit breaker for '{service_name}' is open. "
            f"Retry in {remaining_seconds:.1f} seconds."
        )


class CircuitBreaker:
    """Circuit breaker for a single service.

    States:
    - CLOSED: Normal operation, all requests go through
    - OPEN: Service is failing, requests are rejected immediately
    - HALF_OPEN: Testing if service recovered, limited requests allowed

    Transitions:
    - CLOSED -> OPEN: When failure_threshold is exceeded
    - OPEN -> HALF_OPEN: After recovery_timeout expires
    - HALF_OPEN -> CLOSED: When success_threshold is reached
    - HALF_OPEN -> OPEN: On any failure
    """

    def __init__(
        self,
        service_name: str,
        config: CircuitBreakerConfig | None = None
    ) -> None:
        """Initialize the circuit breaker.

        Args:
            service_name: Name of the service this breaker protects
            config: Circuit breaker configuration
        """
        self._service_name = service_name
        self._config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._metrics = CircuitBreakerMetrics()
        self._lock = threading.RLock()
        self._opened_at: float | None = None
        self._half_open_requests = 0

    @property
    def service_name(self) -> str:
        """Get service name."""
        return self._service_name

    @property
    def state(self) -> CircuitState:
        """Get current state."""
        return self._state

    @property
    def metrics(self) -> CircuitBreakerMetrics:
        """Get metrics."""
        return self._metrics

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed."""
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open."""
        return self._state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open."""
        return self._state == CircuitState.HALF_OPEN

    def _check_recovery_timeout(self) -> bool:
        """Check if recovery timeout has elapsed."""
        if self._opened_at is None:
            return False
        elapsed = time.time() - self._opened_at
        return elapsed >= self._config.recovery_timeout

    def _remaining_timeout(self) -> float:
        """Get remaining timeout in seconds."""
        if self._opened_at is None:
            return 0.0
        elapsed = time.time() - self._opened_at
        remaining = self._config.recovery_timeout - elapsed
        return max(0.0, remaining)

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        if new_state == self._state:
            return

        old_state = self._state
        self._state = new_state
        self._metrics.record_state_change(new_state)

        logger.info(
            f"Circuit breaker '{self._service_name}' transitioned "
            f"from {old_state.value} to {new_state.value}"
        )

        if new_state == CircuitState.OPEN:
            self._opened_at = time.time()
            self._half_open_requests = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_requests = 0
            self._metrics.consecutive_successes = 0
        elif new_state == CircuitState.CLOSED:
            self._opened_at = None
            self._half_open_requests = 0
            self._metrics.consecutive_failures = 0

    def _should_trip(self) -> bool:
        """Check if circuit should trip based on failures."""
        return self._metrics.consecutive_failures >= self._config.failure_threshold

    def _should_close(self) -> bool:
        """Check if circuit should close based on successes."""
        return self._metrics.consecutive_successes >= self._config.success_threshold

    def _can_attempt(self) -> bool:
        """Check if a request attempt is allowed."""
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                if self._check_recovery_timeout():
                    self._transition_to(CircuitState.HALF_OPEN)
                    return True
                return False

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_requests < self._config.half_open_max_requests:
                    self._half_open_requests += 1
                    return True
                return False

            return False

    def _should_ignore(self, exception: Exception) -> bool:
        """Check if exception should be ignored (not trip circuit)."""
        return isinstance(exception, self._config.ignore_exceptions)

    def _should_trip_on(self, exception: Exception) -> bool:
        """Check if exception should trip the circuit."""
        return (
            isinstance(exception, self._config.trip_exceptions)
            and not self._should_ignore(exception)
        )

    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            self._metrics.record_success()

            if self._state == CircuitState.HALF_OPEN:
                if self._should_close():
                    self._transition_to(CircuitState.CLOSED)

    def record_failure(self, exception: Exception) -> None:
        """Record a failed call."""
        with self._lock:
            error_str = f"{type(exception).__name__}: {str(exception)}"
            self._metrics.record_failure(error_str)

            if self._state == CircuitState.CLOSED:
                if self._should_trip():
                    self._transition_to(CircuitState.OPEN)
            elif self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open state reopens the circuit
                self._transition_to(CircuitState.OPEN)

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute a function with circuit breaker protection.

        Args:
            func: The function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            The function result

        Raises:
            CircuitBreakerOpen: If the circuit is open
            Exception: Any exception from the function
        """
        if not self._can_attempt():
            self._metrics.record_rejection()
            raise CircuitBreakerOpen(self._service_name, self._remaining_timeout())

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            if self._should_trip_on(e):
                self.record_failure(e)
            raise

    async def call_async(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any
    ) -> T:
        """Execute an async function with circuit breaker protection.

        Args:
            func: The async function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            The function result

        Raises:
            CircuitBreakerOpen: If the circuit is open
            Exception: Any exception from the function
        """
        if not self._can_attempt():
            self._metrics.record_rejection()
            raise CircuitBreakerOpen(self._service_name, self._remaining_timeout())

        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            if self._should_trip_on(e):
                self.record_failure(e)
            raise

    def reset(self) -> None:
        """Reset the circuit breaker to closed state."""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)
            self._metrics = CircuitBreakerMetrics()

    def get_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "service_name": self._service_name,
            "state": self._state.value,
            "remaining_timeout": self._remaining_timeout() if self._state == CircuitState.OPEN else None,
            "config": {
                "failure_threshold": self._config.failure_threshold,
                "success_threshold": self._config.success_threshold,
                "recovery_timeout": self._config.recovery_timeout,
            },
            "metrics": self._metrics.to_dict(),
        }


def circuit_breaker(
    breaker: CircuitBreaker,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to protect a function with a circuit breaker.

    Args:
        breaker: The circuit breaker instance

    Returns:
        Decorated function

    Example:
        neo4j_breaker = CircuitBreaker("neo4j")

        @circuit_breaker(neo4j_breaker)
        def query_database(query: str) -> dict:
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return breaker.call(func, *args, **kwargs)

        return wrapper
    return decorator


def async_circuit_breaker(
    breaker: CircuitBreaker,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to protect an async function with a circuit breaker.

    Args:
        breaker: The circuit breaker instance

    Returns:
        Decorated async function

    Example:
        redis_breaker = CircuitBreaker("redis")

        @async_circuit_breaker(redis_breaker)
        async def get_cached_value(key: str) -> dict:
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await breaker.call_async(func, *args, **kwargs)

        return wrapper  # type: ignore
    return decorator


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""

    def __init__(self) -> None:
        """Initialize the registry."""
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def get_or_create(
        self,
        service_name: str,
        config: CircuitBreakerConfig | None = None
    ) -> CircuitBreaker:
        """Get or create a circuit breaker for a service.

        Args:
            service_name: Name of the service
            config: Optional configuration

        Returns:
            CircuitBreaker instance
        """
        with self._lock:
            if service_name not in self._breakers:
                self._breakers[service_name] = CircuitBreaker(
                    service_name,
                    config
                )
            return self._breakers[service_name]

    def get(self, service_name: str) -> CircuitBreaker | None:
        """Get a circuit breaker by name.

        Args:
            service_name: Name of the service

        Returns:
            CircuitBreaker if found, None otherwise
        """
        return self._breakers.get(service_name)

    def list_all(self) -> list[str]:
        """List all registered circuit breakers."""
        return list(self._breakers.keys())

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all circuit breakers."""
        return {
            name: breaker.get_stats()
            for name, breaker in self._breakers.items()
        }

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            breaker.reset()


# Global registry instance
_registry: CircuitBreakerRegistry | None = None
_registry_lock = threading.Lock()


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Get the global circuit breaker registry."""
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = CircuitBreakerRegistry()
    return _registry


def reset_circuit_breaker_registry() -> None:
    """Reset the global circuit breaker registry (for testing)."""
    global _registry
    with _registry_lock:
        if _registry is not None:
            _registry.reset_all()
        _registry = None


# Pre-configured circuit breakers for common services
def get_neo4j_circuit_breaker() -> CircuitBreaker:
    """Get circuit breaker for Neo4j database."""
    registry = get_circuit_breaker_registry()
    return registry.get_or_create(
        "neo4j",
        CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            recovery_timeout=30.0,
        )
    )


def get_redis_circuit_breaker() -> CircuitBreaker:
    """Get circuit breaker for Redis cache."""
    registry = get_circuit_breaker_registry()
    return registry.get_or_create(
        "redis",
        CircuitBreakerConfig(
            failure_threshold=5,
            success_threshold=2,
            recovery_timeout=15.0,
        )
    )


def get_embedding_circuit_breaker() -> CircuitBreaker:
    """Get circuit breaker for embedding service."""
    registry = get_circuit_breaker_registry()
    return registry.get_or_create(
        "embedding",
        CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            recovery_timeout=60.0,
        )
    )


def get_external_api_circuit_breaker(api_name: str) -> CircuitBreaker:
    """Get circuit breaker for an external API.

    Args:
        api_name: Name of the external API

    Returns:
        CircuitBreaker configured for external APIs
    """
    registry = get_circuit_breaker_registry()
    return registry.get_or_create(
        f"api:{api_name}",
        CircuitBreakerConfig(
            failure_threshold=5,
            success_threshold=3,
            recovery_timeout=45.0,
        )
    )
