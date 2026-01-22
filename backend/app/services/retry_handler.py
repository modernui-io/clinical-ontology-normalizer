"""Retry handler with exponential backoff for KG operations.

This module provides retry functionality for transient failures:
- Exponential backoff with jitter
- Configurable retry conditions
- Integration with circuit breakers
- Async support
"""

from __future__ import annotations

import asyncio
import functools
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerOpen

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    # Maximum number of retry attempts (not including initial attempt)
    max_retries: int = 3

    # Initial delay between retries in seconds
    initial_delay: float = 1.0

    # Maximum delay between retries in seconds
    max_delay: float = 60.0

    # Exponential backoff multiplier
    backoff_multiplier: float = 2.0

    # Random jitter factor (0.0 to 1.0) to prevent thundering herd
    jitter: float = 0.1

    # Exceptions that should be retried
    retry_exceptions: tuple[type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
        OSError,
    )

    # Exceptions that should NOT be retried (even if in retry_exceptions)
    no_retry_exceptions: tuple[type[Exception], ...] = ()

    # Whether to retry on circuit breaker open
    retry_on_circuit_open: bool = False


@dataclass
class RetryAttempt:
    """Information about a single retry attempt."""

    attempt_number: int  # 0 = initial attempt
    start_time: datetime
    end_time: datetime | None = None
    success: bool = False
    error: str | None = None
    delay_before: float = 0.0  # Delay before this attempt

    @property
    def duration_ms(self) -> float | None:
        """Get attempt duration in milliseconds."""
        if self.end_time is None:
            return None
        delta = self.end_time - self.start_time
        return delta.total_seconds() * 1000


@dataclass
class RetryResult:
    """Result of a retry operation."""

    success: bool
    value: Any = None
    final_error: Exception | None = None
    attempts: list[RetryAttempt] = field(default_factory=list)
    total_delay: float = 0.0  # Total delay across all retries

    @property
    def attempt_count(self) -> int:
        """Get total number of attempts."""
        return len(self.attempts)

    @property
    def total_duration_ms(self) -> float:
        """Get total duration across all attempts."""
        return sum(
            a.duration_ms or 0.0
            for a in self.attempts
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "attempt_count": self.attempt_count,
            "total_delay_seconds": round(self.total_delay, 3),
            "total_duration_ms": round(self.total_duration_ms, 2),
            "final_error": str(self.final_error) if self.final_error else None,
            "attempts": [
                {
                    "attempt": a.attempt_number,
                    "success": a.success,
                    "error": a.error,
                    "delay_before": round(a.delay_before, 3),
                    "duration_ms": round(a.duration_ms, 2) if a.duration_ms else None,
                }
                for a in self.attempts
            ],
        }


def calculate_delay(
    attempt: int,
    config: RetryConfig,
) -> float:
    """Calculate delay before next retry with exponential backoff and jitter.

    Args:
        attempt: Current attempt number (0-indexed)
        config: Retry configuration

    Returns:
        Delay in seconds
    """
    if attempt == 0:
        return 0.0

    # Exponential backoff
    delay = config.initial_delay * (config.backoff_multiplier ** (attempt - 1))

    # Cap at max delay
    delay = min(delay, config.max_delay)

    # Add jitter
    if config.jitter > 0:
        jitter_range = delay * config.jitter
        delay = delay + random.uniform(-jitter_range, jitter_range)

    return max(0.0, delay)


def should_retry(
    exception: Exception,
    config: RetryConfig,
) -> bool:
    """Check if an exception should trigger a retry.

    Args:
        exception: The exception that occurred
        config: Retry configuration

    Returns:
        True if the operation should be retried
    """
    # Check no-retry exceptions first
    if isinstance(exception, config.no_retry_exceptions):
        return False

    # Check if circuit breaker open
    if isinstance(exception, CircuitBreakerOpen):
        return config.retry_on_circuit_open

    # Check retry exceptions
    return isinstance(exception, config.retry_exceptions)


class RetryHandler:
    """Handler for retry operations with exponential backoff."""

    def __init__(
        self,
        config: RetryConfig | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        """Initialize the retry handler.

        Args:
            config: Retry configuration
            circuit_breaker: Optional circuit breaker to use
        """
        self._config = config or RetryConfig()
        self._circuit_breaker = circuit_breaker

    @property
    def config(self) -> RetryConfig:
        """Get the retry configuration."""
        return self._config

    def execute(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute a function with retry logic.

        Args:
            func: The function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            The function result

        Raises:
            Exception: The last exception if all retries fail
        """
        result = self.execute_with_result(func, *args, **kwargs)

        if result.success:
            return result.value

        if result.final_error:
            raise result.final_error

        raise RuntimeError("Retry operation failed without error")

    def execute_with_result(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> RetryResult:
        """Execute a function with retry logic, returning full result.

        Args:
            func: The function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            RetryResult with attempt details
        """
        result = RetryResult(success=False)
        last_exception: Exception | None = None

        for attempt in range(self._config.max_retries + 1):
            # Calculate and apply delay
            delay = calculate_delay(attempt, self._config)
            if delay > 0:
                result.total_delay += delay
                time.sleep(delay)

            # Create attempt record
            attempt_record = RetryAttempt(
                attempt_number=attempt,
                start_time=datetime.now(timezone.utc),
                delay_before=delay,
            )

            try:
                # Execute with circuit breaker if available
                if self._circuit_breaker:
                    value = self._circuit_breaker.call(func, *args, **kwargs)
                else:
                    value = func(*args, **kwargs)

                # Success
                attempt_record.end_time = datetime.now(timezone.utc)
                attempt_record.success = True
                result.attempts.append(attempt_record)
                result.success = True
                result.value = value

                if attempt > 0:
                    logger.info(
                        f"Retry succeeded on attempt {attempt + 1} "
                        f"after {result.total_delay:.2f}s total delay"
                    )

                return result

            except Exception as e:
                attempt_record.end_time = datetime.now(timezone.utc)
                attempt_record.error = str(e)
                result.attempts.append(attempt_record)
                last_exception = e

                # Check if we should retry
                if attempt < self._config.max_retries and should_retry(e, self._config):
                    logger.warning(
                        f"Attempt {attempt + 1} failed with {type(e).__name__}: {e}. "
                        f"Retrying ({self._config.max_retries - attempt} attempts remaining)..."
                    )
                else:
                    break

        result.final_error = last_exception
        logger.error(
            f"All {result.attempt_count} attempts failed. "
            f"Final error: {last_exception}"
        )

        return result

    async def execute_async(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute an async function with retry logic.

        Args:
            func: The async function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            The function result

        Raises:
            Exception: The last exception if all retries fail
        """
        result = await self.execute_async_with_result(func, *args, **kwargs)

        if result.success:
            return result.value

        if result.final_error:
            raise result.final_error

        raise RuntimeError("Retry operation failed without error")

    async def execute_async_with_result(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> RetryResult:
        """Execute an async function with retry logic, returning full result.

        Args:
            func: The async function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            RetryResult with attempt details
        """
        result = RetryResult(success=False)
        last_exception: Exception | None = None

        for attempt in range(self._config.max_retries + 1):
            # Calculate and apply delay
            delay = calculate_delay(attempt, self._config)
            if delay > 0:
                result.total_delay += delay
                await asyncio.sleep(delay)

            # Create attempt record
            attempt_record = RetryAttempt(
                attempt_number=attempt,
                start_time=datetime.now(timezone.utc),
                delay_before=delay,
            )

            try:
                # Execute with circuit breaker if available
                if self._circuit_breaker:
                    value = await self._circuit_breaker.call_async(func, *args, **kwargs)
                else:
                    value = await func(*args, **kwargs)

                # Success
                attempt_record.end_time = datetime.now(timezone.utc)
                attempt_record.success = True
                result.attempts.append(attempt_record)
                result.success = True
                result.value = value

                if attempt > 0:
                    logger.info(
                        f"Async retry succeeded on attempt {attempt + 1} "
                        f"after {result.total_delay:.2f}s total delay"
                    )

                return result

            except Exception as e:
                attempt_record.end_time = datetime.now(timezone.utc)
                attempt_record.error = str(e)
                result.attempts.append(attempt_record)
                last_exception = e

                # Check if we should retry
                if attempt < self._config.max_retries and should_retry(e, self._config):
                    logger.warning(
                        f"Async attempt {attempt + 1} failed with {type(e).__name__}: {e}. "
                        f"Retrying ({self._config.max_retries - attempt} attempts remaining)..."
                    )
                else:
                    break

        result.final_error = last_exception
        logger.error(
            f"All {result.attempt_count} async attempts failed. "
            f"Final error: {last_exception}"
        )

        return result


def retry(
    config: RetryConfig | None = None,
    circuit_breaker: CircuitBreaker | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to add retry logic to a function.

    Args:
        config: Retry configuration
        circuit_breaker: Optional circuit breaker

    Returns:
        Decorated function

    Example:
        @retry(RetryConfig(max_retries=3))
        def fetch_data() -> dict:
            ...
    """
    handler = RetryHandler(config, circuit_breaker)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return handler.execute(func, *args, **kwargs)

        return wrapper
    return decorator


def retry_async(
    config: RetryConfig | None = None,
    circuit_breaker: CircuitBreaker | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to add retry logic to an async function.

    Args:
        config: Retry configuration
        circuit_breaker: Optional circuit breaker

    Returns:
        Decorated async function

    Example:
        @retry_async(RetryConfig(max_retries=3))
        async def fetch_data_async() -> dict:
            ...
    """
    handler = RetryHandler(config, circuit_breaker)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await handler.execute_async(func, *args, **kwargs)

        return wrapper  # type: ignore
    return decorator


# Pre-configured retry handlers
def get_database_retry_handler(
    circuit_breaker: CircuitBreaker | None = None,
) -> RetryHandler:
    """Get a retry handler configured for database operations."""
    return RetryHandler(
        config=RetryConfig(
            max_retries=3,
            initial_delay=0.5,
            max_delay=10.0,
            backoff_multiplier=2.0,
            retry_exceptions=(ConnectionError, TimeoutError, OSError),
        ),
        circuit_breaker=circuit_breaker,
    )


def get_api_retry_handler(
    circuit_breaker: CircuitBreaker | None = None,
) -> RetryHandler:
    """Get a retry handler configured for external API calls."""
    return RetryHandler(
        config=RetryConfig(
            max_retries=3,
            initial_delay=1.0,
            max_delay=30.0,
            backoff_multiplier=2.0,
            retry_exceptions=(ConnectionError, TimeoutError),
        ),
        circuit_breaker=circuit_breaker,
    )


def get_cache_retry_handler(
    circuit_breaker: CircuitBreaker | None = None,
) -> RetryHandler:
    """Get a retry handler configured for cache operations."""
    return RetryHandler(
        config=RetryConfig(
            max_retries=2,
            initial_delay=0.1,
            max_delay=1.0,
            backoff_multiplier=2.0,
            retry_exceptions=(ConnectionError, TimeoutError),
        ),
        circuit_breaker=circuit_breaker,
    )
