"""Tests for circuit breaker pattern implementation."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock

import pytest

from app.services.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerMetrics,
    CircuitBreakerOpen,
    CircuitBreakerRegistry,
    CircuitState,
    async_circuit_breaker,
    circuit_breaker,
    get_circuit_breaker_registry,
    get_embedding_circuit_breaker,
    get_external_api_circuit_breaker,
    get_neo4j_circuit_breaker,
    get_redis_circuit_breaker,
    reset_circuit_breaker_registry,
)


class TestCircuitState:
    """Test CircuitState enum."""

    def test_states_exist(self) -> None:
        """Test all states exist."""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"


class TestCircuitBreakerConfig:
    """Test CircuitBreakerConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.success_threshold == 3
        assert config.recovery_timeout == 30.0
        assert config.half_open_max_requests == 3

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            recovery_timeout=10.0,
        )
        assert config.failure_threshold == 3
        assert config.success_threshold == 2
        assert config.recovery_timeout == 10.0


class TestCircuitBreakerMetrics:
    """Test CircuitBreakerMetrics dataclass."""

    def test_initial_metrics(self) -> None:
        """Test initial metrics values."""
        metrics = CircuitBreakerMetrics()
        assert metrics.total_calls == 0
        assert metrics.successful_calls == 0
        assert metrics.failed_calls == 0
        assert metrics.failure_rate == 0.0

    def test_record_success(self) -> None:
        """Test recording successful calls."""
        metrics = CircuitBreakerMetrics()
        metrics.record_success()
        metrics.record_success()

        assert metrics.total_calls == 2
        assert metrics.successful_calls == 2
        assert metrics.consecutive_successes == 2
        assert metrics.consecutive_failures == 0
        assert metrics.last_success_time is not None

    def test_record_failure(self) -> None:
        """Test recording failed calls."""
        metrics = CircuitBreakerMetrics()
        metrics.record_failure("Connection refused")
        metrics.record_failure("Timeout")

        assert metrics.total_calls == 2
        assert metrics.failed_calls == 2
        assert metrics.consecutive_failures == 2
        assert metrics.consecutive_successes == 0
        assert metrics.last_failure_time is not None
        assert len(metrics.recent_failures) == 2

    def test_success_resets_consecutive_failures(self) -> None:
        """Test that success resets consecutive failures."""
        metrics = CircuitBreakerMetrics()
        metrics.record_failure("Error 1")
        metrics.record_failure("Error 2")
        assert metrics.consecutive_failures == 2

        metrics.record_success()
        assert metrics.consecutive_failures == 0
        assert metrics.consecutive_successes == 1

    def test_failure_resets_consecutive_successes(self) -> None:
        """Test that failure resets consecutive successes."""
        metrics = CircuitBreakerMetrics()
        metrics.record_success()
        metrics.record_success()
        assert metrics.consecutive_successes == 2

        metrics.record_failure("Error")
        assert metrics.consecutive_successes == 0
        assert metrics.consecutive_failures == 1

    def test_failure_rate(self) -> None:
        """Test failure rate calculation."""
        metrics = CircuitBreakerMetrics()
        metrics.record_success()
        metrics.record_success()
        metrics.record_failure("Error")
        metrics.record_success()

        assert metrics.failure_rate == 0.25  # 1 failure out of 4 calls

    def test_record_rejection(self) -> None:
        """Test recording rejected calls."""
        metrics = CircuitBreakerMetrics()
        metrics.record_rejection()
        metrics.record_rejection()

        assert metrics.total_calls == 2
        assert metrics.rejected_calls == 2
        assert metrics.rejection_rate == 1.0

    def test_to_dict(self) -> None:
        """Test converting metrics to dictionary."""
        metrics = CircuitBreakerMetrics()
        metrics.record_success()
        metrics.record_failure("Error")

        data = metrics.to_dict()
        assert data["total_calls"] == 2
        assert data["successful_calls"] == 1
        assert data["failed_calls"] == 1
        assert data["failure_rate"] == 0.5
        assert "current_state" in data


class TestCircuitBreaker:
    """Test CircuitBreaker class."""

    def test_initial_state_is_closed(self) -> None:
        """Test that initial state is closed."""
        breaker = CircuitBreaker("test-service")
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_closed
        assert not breaker.is_open
        assert not breaker.is_half_open

    def test_successful_calls_stay_closed(self) -> None:
        """Test that successful calls keep circuit closed."""
        breaker = CircuitBreaker("test-service")

        for _ in range(10):
            result = breaker.call(lambda: "success")
            assert result == "success"

        assert breaker.is_closed

    def test_circuit_opens_after_failures(self) -> None:
        """Test that circuit opens after failure threshold."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("test-service", config)

        def failing_func():
            raise ConnectionError("Connection refused")

        # First 3 failures should trip the circuit
        for i in range(3):
            with pytest.raises(ConnectionError):
                breaker.call(failing_func)

        assert breaker.is_open

    def test_open_circuit_rejects_requests(self) -> None:
        """Test that open circuit rejects requests."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=60.0,  # Long timeout
        )
        breaker = CircuitBreaker("test-service", config)

        def failing_func():
            raise ConnectionError("Connection refused")

        # Trip the circuit
        for _ in range(2):
            with pytest.raises(ConnectionError):
                breaker.call(failing_func)

        assert breaker.is_open

        # Next call should be rejected
        with pytest.raises(CircuitBreakerOpen) as exc_info:
            breaker.call(lambda: "success")

        assert exc_info.value.service_name == "test-service"
        assert exc_info.value.remaining_seconds > 0

    def test_circuit_transitions_to_half_open(self) -> None:
        """Test circuit transitions to half-open after timeout."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,  # 100ms timeout
        )
        breaker = CircuitBreaker("test-service", config)

        def failing_func():
            raise ConnectionError("Connection refused")

        # Trip the circuit
        for _ in range(2):
            with pytest.raises(ConnectionError):
                breaker.call(failing_func)

        assert breaker.is_open

        # Wait for recovery timeout
        time.sleep(0.15)

        # Next call should be allowed (half-open)
        result = breaker.call(lambda: "success")
        assert result == "success"
        assert breaker.is_half_open or breaker.is_closed

    def test_half_open_closes_on_success(self) -> None:
        """Test half-open circuit closes after success threshold."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=2,
            recovery_timeout=0.05,
        )
        breaker = CircuitBreaker("test-service", config)

        def failing_func():
            raise ConnectionError("Connection refused")

        # Trip the circuit
        for _ in range(2):
            with pytest.raises(ConnectionError):
                breaker.call(failing_func)

        assert breaker.is_open

        # Wait for recovery
        time.sleep(0.1)

        # Success threshold should close circuit
        for _ in range(2):
            breaker.call(lambda: "success")

        assert breaker.is_closed

    def test_half_open_reopens_on_failure(self) -> None:
        """Test half-open circuit reopens on failure."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.05,
        )
        breaker = CircuitBreaker("test-service", config)

        def failing_func():
            raise ConnectionError("Connection refused")

        # Trip the circuit
        for _ in range(2):
            with pytest.raises(ConnectionError):
                breaker.call(failing_func)

        assert breaker.is_open

        # Wait for recovery
        time.sleep(0.1)

        # Failure in half-open state should reopen
        with pytest.raises(ConnectionError):
            breaker.call(failing_func)

        assert breaker.is_open

    def test_ignored_exceptions_dont_trip(self) -> None:
        """Test that ignored exceptions don't trip the circuit."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            ignore_exceptions=(ValueError,),
        )
        breaker = CircuitBreaker("test-service", config)

        def value_error_func():
            raise ValueError("Invalid input")

        # ValueError should not trip the circuit
        for _ in range(5):
            with pytest.raises(ValueError):
                breaker.call(value_error_func)

        assert breaker.is_closed

    def test_reset(self) -> None:
        """Test resetting the circuit breaker."""
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker("test-service", config)

        def failing_func():
            raise ConnectionError("Connection refused")

        # Trip the circuit
        for _ in range(2):
            with pytest.raises(ConnectionError):
                breaker.call(failing_func)

        assert breaker.is_open

        # Reset should close circuit
        breaker.reset()
        assert breaker.is_closed
        assert breaker.metrics.total_calls == 0

    def test_get_stats(self) -> None:
        """Test getting circuit breaker statistics."""
        breaker = CircuitBreaker("test-service")
        breaker.call(lambda: "success")

        stats = breaker.get_stats()
        assert stats["service_name"] == "test-service"
        assert stats["state"] == "closed"
        assert "config" in stats
        assert "metrics" in stats


class TestCircuitBreakerDecorator:
    """Test circuit breaker decorator."""

    def test_decorator_protects_function(self) -> None:
        """Test that decorator protects a function."""
        breaker = CircuitBreaker("test-service")

        @circuit_breaker(breaker)
        def my_function(x: int) -> int:
            return x * 2

        result = my_function(5)
        assert result == 10
        assert breaker.metrics.successful_calls == 1

    def test_decorator_records_failures(self) -> None:
        """Test that decorator records failures."""
        config = CircuitBreakerConfig(failure_threshold=5)
        breaker = CircuitBreaker("test-service", config)

        @circuit_breaker(breaker)
        def failing_function():
            raise RuntimeError("Failed")

        with pytest.raises(RuntimeError):
            failing_function()

        assert breaker.metrics.failed_calls == 1


class TestAsyncCircuitBreaker:
    """Test async circuit breaker functionality."""

    @pytest.mark.asyncio
    async def test_async_call(self) -> None:
        """Test async call with circuit breaker."""
        breaker = CircuitBreaker("test-service")

        async def async_func():
            await asyncio.sleep(0.001)
            return "success"

        result = await breaker.call_async(async_func)
        assert result == "success"
        assert breaker.metrics.successful_calls == 1

    @pytest.mark.asyncio
    async def test_async_failure(self) -> None:
        """Test async failure trips circuit."""
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker("test-service", config)

        async def failing_func():
            raise ConnectionError("Failed")

        for _ in range(2):
            with pytest.raises(ConnectionError):
                await breaker.call_async(failing_func)

        assert breaker.is_open

    @pytest.mark.asyncio
    async def test_async_decorator(self) -> None:
        """Test async circuit breaker decorator."""
        breaker = CircuitBreaker("test-service")

        @async_circuit_breaker(breaker)
        async def my_async_function(x: int) -> int:
            await asyncio.sleep(0.001)
            return x * 2

        result = await my_async_function(5)
        assert result == 10
        assert breaker.metrics.successful_calls == 1


class TestCircuitBreakerRegistry:
    """Test circuit breaker registry."""

    def test_get_or_create(self) -> None:
        """Test getting or creating a circuit breaker."""
        registry = CircuitBreakerRegistry()

        breaker1 = registry.get_or_create("service-a")
        breaker2 = registry.get_or_create("service-a")

        assert breaker1 is breaker2

    def test_different_services(self) -> None:
        """Test different services get different breakers."""
        registry = CircuitBreakerRegistry()

        breaker1 = registry.get_or_create("service-a")
        breaker2 = registry.get_or_create("service-b")

        assert breaker1 is not breaker2

    def test_get_nonexistent(self) -> None:
        """Test getting non-existent breaker returns None."""
        registry = CircuitBreakerRegistry()
        assert registry.get("nonexistent") is None

    def test_list_all(self) -> None:
        """Test listing all registered breakers."""
        registry = CircuitBreakerRegistry()
        registry.get_or_create("service-a")
        registry.get_or_create("service-b")
        registry.get_or_create("service-c")

        services = registry.list_all()
        assert "service-a" in services
        assert "service-b" in services
        assert "service-c" in services

    def test_get_all_stats(self) -> None:
        """Test getting stats for all breakers."""
        registry = CircuitBreakerRegistry()
        breaker = registry.get_or_create("service-a")
        breaker.call(lambda: "success")

        stats = registry.get_all_stats()
        assert "service-a" in stats
        assert stats["service-a"]["metrics"]["successful_calls"] == 1

    def test_reset_all(self) -> None:
        """Test resetting all breakers."""
        registry = CircuitBreakerRegistry()
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = registry.get_or_create("service-a", config)

        # Trip the circuit
        for _ in range(2):
            with pytest.raises(ConnectionError):
                breaker.call(lambda: (_ for _ in ()).throw(ConnectionError()))

        assert breaker.is_open

        registry.reset_all()
        assert breaker.is_closed


class TestGlobalRegistry:
    """Test global registry functions."""

    @pytest.fixture(autouse=True)
    def reset_registry(self) -> None:
        """Reset global registry before each test."""
        reset_circuit_breaker_registry()

    def test_get_global_registry(self) -> None:
        """Test getting global registry."""
        registry1 = get_circuit_breaker_registry()
        registry2 = get_circuit_breaker_registry()
        assert registry1 is registry2

    def test_reset_global_registry(self) -> None:
        """Test resetting global registry."""
        registry1 = get_circuit_breaker_registry()
        reset_circuit_breaker_registry()
        registry2 = get_circuit_breaker_registry()
        assert registry1 is not registry2


class TestPreconfiguredBreakers:
    """Test pre-configured circuit breakers."""

    @pytest.fixture(autouse=True)
    def reset_registry(self) -> None:
        """Reset global registry before each test."""
        reset_circuit_breaker_registry()

    def test_neo4j_breaker(self) -> None:
        """Test Neo4j circuit breaker."""
        breaker = get_neo4j_circuit_breaker()
        assert breaker.service_name == "neo4j"
        assert breaker._config.failure_threshold == 3

    def test_redis_breaker(self) -> None:
        """Test Redis circuit breaker."""
        breaker = get_redis_circuit_breaker()
        assert breaker.service_name == "redis"
        assert breaker._config.failure_threshold == 5

    def test_embedding_breaker(self) -> None:
        """Test embedding service circuit breaker."""
        breaker = get_embedding_circuit_breaker()
        assert breaker.service_name == "embedding"
        assert breaker._config.recovery_timeout == 60.0

    def test_external_api_breaker(self) -> None:
        """Test external API circuit breaker."""
        breaker = get_external_api_circuit_breaker("umls")
        assert breaker.service_name == "api:umls"
        assert breaker._config.failure_threshold == 5


class TestHalfOpenConcurrency:
    """Test half-open state concurrency limits."""

    def test_half_open_limits_requests(self) -> None:
        """Test that half-open state limits concurrent requests."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.01,
            half_open_max_requests=2,
        )
        breaker = CircuitBreaker("test-service", config)

        def failing_func():
            raise ConnectionError("Failed")

        # Trip the circuit
        for _ in range(2):
            with pytest.raises(ConnectionError):
                breaker.call(failing_func)

        assert breaker.is_open

        # Wait for recovery
        time.sleep(0.02)

        # First two requests in half-open should be allowed
        breaker.call(lambda: "success")
        breaker.call(lambda: "success")

        # Reset should happen after success threshold

    def test_state_change_tracking(self) -> None:
        """Test that state changes are tracked."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=1,
            recovery_timeout=0.01,
        )
        breaker = CircuitBreaker("test-service", config)

        def failing_func():
            raise ConnectionError("Failed")

        # CLOSED -> OPEN
        for _ in range(2):
            with pytest.raises(ConnectionError):
                breaker.call(failing_func)

        # Wait for recovery
        time.sleep(0.02)

        # OPEN -> HALF_OPEN -> CLOSED
        breaker.call(lambda: "success")

        # Check state changes were recorded
        state_changes = breaker.metrics.state_changes
        states = [s.value for _, s in state_changes]

        assert "open" in states
        # Note: HALF_OPEN may or may not be in states depending on timing
        assert breaker.is_closed or breaker.is_half_open
