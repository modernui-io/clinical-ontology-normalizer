"""Tests for retry handler with exponential backoff."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock, AsyncMock

import pytest

from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from app.services.retry_handler import (
    RetryAttempt,
    RetryConfig,
    RetryHandler,
    RetryResult,
    calculate_delay,
    get_api_retry_handler,
    get_cache_retry_handler,
    get_database_retry_handler,
    retry,
    retry_async,
    should_retry,
)


class TestRetryConfig:
    """Test RetryConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.backoff_multiplier == 2.0
        assert config.jitter == 0.1

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = RetryConfig(
            max_retries=5,
            initial_delay=0.5,
            max_delay=30.0,
        )
        assert config.max_retries == 5
        assert config.initial_delay == 0.5
        assert config.max_delay == 30.0


class TestRetryAttempt:
    """Test RetryAttempt dataclass."""

    def test_attempt_creation(self) -> None:
        """Test creating a retry attempt."""
        from datetime import datetime, timezone

        start = datetime.now(timezone.utc)
        attempt = RetryAttempt(
            attempt_number=0,
            start_time=start,
        )
        assert attempt.attempt_number == 0
        assert attempt.success is False
        assert attempt.duration_ms is None

    def test_attempt_duration(self) -> None:
        """Test attempt duration calculation."""
        from datetime import datetime, timezone, timedelta

        start = datetime.now(timezone.utc)
        end = start + timedelta(milliseconds=100)

        attempt = RetryAttempt(
            attempt_number=0,
            start_time=start,
            end_time=end,
        )
        assert attempt.duration_ms is not None
        assert abs(attempt.duration_ms - 100.0) < 1.0


class TestRetryResult:
    """Test RetryResult dataclass."""

    def test_initial_result(self) -> None:
        """Test initial result values."""
        result = RetryResult(success=False)
        assert result.success is False
        assert result.attempt_count == 0
        assert result.total_duration_ms == 0.0

    def test_result_to_dict(self) -> None:
        """Test converting result to dictionary."""
        result = RetryResult(
            success=True,
            value="test",
            total_delay=1.5,
        )

        data = result.to_dict()
        assert data["success"] is True
        assert data["total_delay_seconds"] == 1.5
        assert "attempts" in data


class TestCalculateDelay:
    """Test delay calculation."""

    def test_first_attempt_no_delay(self) -> None:
        """Test that first attempt has no delay."""
        config = RetryConfig()
        delay = calculate_delay(0, config)
        assert delay == 0.0

    def test_exponential_backoff(self) -> None:
        """Test exponential backoff progression."""
        config = RetryConfig(
            initial_delay=1.0,
            backoff_multiplier=2.0,
            jitter=0.0,  # Disable jitter for predictable results
        )

        # Attempt 1: 1.0s
        delay1 = calculate_delay(1, config)
        assert abs(delay1 - 1.0) < 0.01

        # Attempt 2: 2.0s
        delay2 = calculate_delay(2, config)
        assert abs(delay2 - 2.0) < 0.01

        # Attempt 3: 4.0s
        delay3 = calculate_delay(3, config)
        assert abs(delay3 - 4.0) < 0.01

    def test_max_delay_cap(self) -> None:
        """Test that delay is capped at max_delay."""
        config = RetryConfig(
            initial_delay=10.0,
            max_delay=15.0,
            backoff_multiplier=2.0,
            jitter=0.0,
        )

        # Large attempt should be capped
        delay = calculate_delay(10, config)
        assert delay <= config.max_delay

    def test_jitter_adds_randomness(self) -> None:
        """Test that jitter adds randomness to delay."""
        config = RetryConfig(
            initial_delay=1.0,
            jitter=0.5,  # 50% jitter
        )

        delays = [calculate_delay(1, config) for _ in range(10)]

        # Delays should vary due to jitter
        unique_delays = len(set(round(d, 4) for d in delays))
        assert unique_delays > 1


class TestShouldRetry:
    """Test retry condition checking."""

    def test_retry_on_connection_error(self) -> None:
        """Test that ConnectionError triggers retry."""
        config = RetryConfig()
        assert should_retry(ConnectionError("Connection refused"), config)

    def test_retry_on_timeout_error(self) -> None:
        """Test that TimeoutError triggers retry."""
        config = RetryConfig()
        assert should_retry(TimeoutError("Timeout"), config)

    def test_no_retry_on_value_error(self) -> None:
        """Test that ValueError doesn't trigger retry by default."""
        config = RetryConfig()
        assert not should_retry(ValueError("Invalid input"), config)

    def test_no_retry_exceptions(self) -> None:
        """Test no_retry_exceptions override."""
        config = RetryConfig(
            no_retry_exceptions=(ConnectionError,),
        )
        # ConnectionError is in retry_exceptions but also in no_retry
        assert not should_retry(ConnectionError("Connection refused"), config)

    def test_custom_retry_exceptions(self) -> None:
        """Test custom retry exceptions."""
        config = RetryConfig(
            retry_exceptions=(ValueError, KeyError),
        )
        assert should_retry(ValueError("Test"), config)
        assert should_retry(KeyError("Test"), config)
        assert not should_retry(ConnectionError("Test"), config)


class TestRetryHandler:
    """Test RetryHandler class."""

    def test_successful_on_first_attempt(self) -> None:
        """Test successful execution on first attempt."""
        handler = RetryHandler()

        result = handler.execute(lambda: "success")
        assert result == "success"

    def test_execute_with_result(self) -> None:
        """Test execute_with_result returns full details."""
        handler = RetryHandler()

        result = handler.execute_with_result(lambda: "success")
        assert result.success is True
        assert result.value == "success"
        assert result.attempt_count == 1

    def test_retry_on_transient_failure(self) -> None:
        """Test retry on transient failure."""
        config = RetryConfig(
            max_retries=3,
            initial_delay=0.01,  # Fast for testing
        )
        handler = RetryHandler(config)

        call_count = 0

        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Connection refused")
            return "success"

        result = handler.execute(flaky_func)
        assert result == "success"
        assert call_count == 2

    def test_fail_after_max_retries(self) -> None:
        """Test failure after max retries exceeded."""
        config = RetryConfig(
            max_retries=2,
            initial_delay=0.01,
        )
        handler = RetryHandler(config)

        call_count = 0

        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Connection refused")

        with pytest.raises(ConnectionError):
            handler.execute(always_fails)

        assert call_count == 3  # Initial + 2 retries

    def test_no_retry_on_non_transient_error(self) -> None:
        """Test no retry on non-transient error."""
        config = RetryConfig(max_retries=3)
        handler = RetryHandler(config)

        call_count = 0

        def fails_with_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid input")

        with pytest.raises(ValueError):
            handler.execute(fails_with_value_error)

        assert call_count == 1  # No retries

    def test_with_circuit_breaker(self) -> None:
        """Test retry with circuit breaker integration."""
        cb_config = CircuitBreakerConfig(failure_threshold=5)
        circuit_breaker = CircuitBreaker("test", cb_config)

        retry_config = RetryConfig(
            max_retries=2,
            initial_delay=0.01,
        )
        handler = RetryHandler(retry_config, circuit_breaker)

        call_count = 0

        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Connection refused")
            return "success"

        result = handler.execute(flaky_func)
        assert result == "success"

        # Circuit breaker should have recorded the attempts
        assert circuit_breaker.metrics.successful_calls == 1
        assert circuit_breaker.metrics.failed_calls == 1


class TestRetryHandlerAsync:
    """Test async retry handler functionality."""

    @pytest.mark.asyncio
    async def test_async_success_first_attempt(self) -> None:
        """Test async successful execution on first attempt."""
        handler = RetryHandler()

        async def async_func():
            return "success"

        result = await handler.execute_async(async_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_async_retry_on_failure(self) -> None:
        """Test async retry on transient failure."""
        config = RetryConfig(
            max_retries=3,
            initial_delay=0.01,
        )
        handler = RetryHandler(config)

        call_count = 0

        async def flaky_async():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.001)
            if call_count < 2:
                raise ConnectionError("Connection refused")
            return "success"

        result = await handler.execute_async(flaky_async)
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_async_execute_with_result(self) -> None:
        """Test async execute_with_result."""
        handler = RetryHandler()

        async def async_func():
            return "data"

        result = await handler.execute_async_with_result(async_func)
        assert result.success is True
        assert result.value == "data"
        assert result.attempt_count == 1

    @pytest.mark.asyncio
    async def test_async_fail_after_retries(self) -> None:
        """Test async failure after max retries."""
        config = RetryConfig(
            max_retries=2,
            initial_delay=0.01,
        )
        handler = RetryHandler(config)

        async def always_fails():
            raise TimeoutError("Timeout")

        with pytest.raises(TimeoutError):
            await handler.execute_async(always_fails)


class TestRetryDecorator:
    """Test retry decorator."""

    def test_decorator_success(self) -> None:
        """Test decorator with successful function."""
        @retry(RetryConfig())
        def my_func(x: int) -> int:
            return x * 2

        result = my_func(5)
        assert result == 10

    def test_decorator_retry(self) -> None:
        """Test decorator retries on failure."""
        call_count = 0

        @retry(RetryConfig(max_retries=3, initial_delay=0.01))
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Failed")
            return "success"

        result = flaky_func()
        assert result == "success"
        assert call_count == 2

    def test_decorator_preserves_function_metadata(self) -> None:
        """Test that decorator preserves function metadata."""
        @retry()
        def documented_func():
            """This is my function."""
            return "result"

        assert documented_func.__name__ == "documented_func"
        assert "my function" in documented_func.__doc__


class TestRetryAsyncDecorator:
    """Test async retry decorator."""

    @pytest.mark.asyncio
    async def test_async_decorator_success(self) -> None:
        """Test async decorator with successful function."""
        @retry_async(RetryConfig())
        async def my_async_func(x: int) -> int:
            return x * 2

        result = await my_async_func(5)
        assert result == 10

    @pytest.mark.asyncio
    async def test_async_decorator_retry(self) -> None:
        """Test async decorator retries on failure."""
        call_count = 0

        @retry_async(RetryConfig(max_retries=3, initial_delay=0.01))
        async def flaky_async():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("Timeout")
            return "success"

        result = await flaky_async()
        assert result == "success"
        assert call_count == 2


class TestPreconfiguredHandlers:
    """Test pre-configured retry handlers."""

    def test_database_handler(self) -> None:
        """Test database retry handler configuration."""
        handler = get_database_retry_handler()
        assert handler.config.max_retries == 3
        assert handler.config.initial_delay == 0.5

    def test_api_handler(self) -> None:
        """Test API retry handler configuration."""
        handler = get_api_retry_handler()
        assert handler.config.max_retries == 3
        assert handler.config.initial_delay == 1.0

    def test_cache_handler(self) -> None:
        """Test cache retry handler configuration."""
        handler = get_cache_retry_handler()
        assert handler.config.max_retries == 2
        assert handler.config.initial_delay == 0.1

    def test_handler_with_circuit_breaker(self) -> None:
        """Test handler with circuit breaker."""
        circuit_breaker = CircuitBreaker("test")
        handler = get_database_retry_handler(circuit_breaker)

        result = handler.execute(lambda: "success")
        assert result == "success"
        assert circuit_breaker.metrics.successful_calls == 1


class TestRetryTiming:
    """Test retry timing behavior."""

    def test_total_delay_accumulated(self) -> None:
        """Test that total delay is accumulated correctly."""
        config = RetryConfig(
            max_retries=3,
            initial_delay=0.1,
            jitter=0.0,
        )
        handler = RetryHandler(config)

        call_count = 0

        def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Failed")
            return "success"

        result = handler.execute_with_result(fails_twice)
        assert result.success is True

        # Should have delays for attempts 1 and 2
        # Attempt 1: 0.1s, Attempt 2: 0.2s
        # Total delay should be approximately 0.3s
        assert result.total_delay >= 0.25

    def test_actual_delay_applied(self) -> None:
        """Test that delays are actually applied."""
        config = RetryConfig(
            max_retries=2,
            initial_delay=0.1,
            jitter=0.0,
        )
        handler = RetryHandler(config)

        call_count = 0
        timestamps = []

        def timestamped_func():
            nonlocal call_count
            timestamps.append(time.time())
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Failed")
            return "success"

        handler.execute(timestamped_func)

        # Check time between attempts
        assert len(timestamps) == 2
        time_diff = timestamps[1] - timestamps[0]
        assert time_diff >= 0.08  # Allow some tolerance


class TestEdgeCases:
    """Test edge cases."""

    def test_zero_max_retries(self) -> None:
        """Test with zero max retries."""
        config = RetryConfig(max_retries=0)
        handler = RetryHandler(config)

        call_count = 0

        def fails():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Failed")

        with pytest.raises(ConnectionError):
            handler.execute(fails)

        assert call_count == 1  # Only initial attempt

    def test_function_with_args(self) -> None:
        """Test retrying function with arguments."""
        handler = RetryHandler()

        def add(a: int, b: int) -> int:
            return a + b

        result = handler.execute(add, 3, 4)
        assert result == 7

    def test_function_with_kwargs(self) -> None:
        """Test retrying function with keyword arguments."""
        handler = RetryHandler()

        def greet(name: str, greeting: str = "Hello") -> str:
            return f"{greeting}, {name}!"

        result = handler.execute(greet, "World", greeting="Hi")
        assert result == "Hi, World!"

    def test_result_tracks_all_errors(self) -> None:
        """Test that result tracks all attempt errors."""
        config = RetryConfig(
            max_retries=2,
            initial_delay=0.01,
        )
        handler = RetryHandler(config)

        def always_fails():
            raise ConnectionError("Connection refused")

        result = handler.execute_with_result(always_fails)
        assert result.success is False
        assert result.attempt_count == 3
        assert all(a.error is not None for a in result.attempts)
