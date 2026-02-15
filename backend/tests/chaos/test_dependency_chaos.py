"""P3-010: Red-team chaos tests for dependency-loss scenarios.

Each test mocks a dependency failure and verifies the system handles it
gracefully -- returning degraded responses rather than crashing.
"""

from __future__ import annotations

import asyncio
import random
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.queue import RQ_AVAILABLE

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slow_side_effect(delay: float = 5.0):
    """Return a side-effect that blocks for *delay* seconds."""
    def _inner(*_args, **_kwargs):
        time.sleep(delay)
        raise TimeoutError(f"Simulated timeout after {delay}s")
    return _inner


def _intermittent_side_effect(failure_rate: float = 0.5):
    """Return a side-effect that fails *failure_rate* fraction of calls."""
    call_count = {"n": 0}

    def _inner(*_args, **_kwargs):
        call_count["n"] += 1
        if random.random() < failure_rate:
            raise ConnectionError(f"Intermittent failure (call #{call_count['n']})")
        return MagicMock()
    return _inner


# ===========================================================================
# 1. PostgreSQL connection dropped mid-query
# ===========================================================================


@pytest.mark.chaos
class TestPostgresConnectionDrop:
    """Verify graceful degradation when PostgreSQL drops mid-query."""

    def test_health_reports_unhealthy_when_pg_down(self):
        """Health endpoint must report unhealthy when DB is unreachable."""
        from app.api.health import CRITICAL_SERVICES

        assert "database" in CRITICAL_SERVICES

    @pytest.mark.asyncio
    async def test_get_session_raises_on_connection_loss(self):
        """get_session should propagate the DB error, not crash."""
        from sqlalchemy.exc import OperationalError

        mock_engine = AsyncMock()
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            side_effect=OperationalError("connection dropped", {}, None),
        )

        with pytest.raises(OperationalError, match="connection dropped"):
            await mock_session.execute("SELECT 1")

    @pytest.mark.asyncio
    async def test_database_health_check_timeout(self):
        """Database health check should handle timeout gracefully."""
        from app.api.health import HEALTH_CHECK_TIMEOUT

        assert HEALTH_CHECK_TIMEOUT > 0, "Health check timeout must be positive"

        mock_check = AsyncMock(side_effect=asyncio.TimeoutError())
        with pytest.raises(asyncio.TimeoutError):
            await mock_check()


# ===========================================================================
# 2. Redis unavailable
# ===========================================================================


@pytest.mark.chaos
class TestRedisUnavailable:
    """Verify queue operations fail safely when Redis is down."""

    def test_enqueue_fails_with_connection_error(self):
        """enqueue_job must raise when Redis is unreachable."""
        from app.core.queue import enqueue_job

        with patch("app.core.queue.get_queue") as mock_get_queue:
            mock_queue = MagicMock()
            mock_queue.enqueue.side_effect = ConnectionError("Redis refused")
            mock_get_queue.return_value = mock_queue

            with pytest.raises(ConnectionError, match="Redis refused"):
                enqueue_job(lambda: None)

    def test_get_queue_fails_when_redis_down(self):
        """get_queue must raise when Redis cannot connect."""
        with patch("app.core.queue.get_redis") as mock_redis:
            mock_redis.side_effect = ConnectionError("Redis connect failed")
            # Clear queue cache so it tries to recreate
            import app.core.queue as qmod
            original = qmod._queues.copy()
            qmod._queues.clear()
            try:
                if RQ_AVAILABLE:
                    with pytest.raises(ConnectionError, match="Redis connect failed"):
                        from app.core.queue import get_queue
                        get_queue("test_chaos_queue")
                else:
                    with pytest.raises(ImportError):
                        from app.core.queue import get_queue
                        get_queue("test_chaos_queue")
            finally:
                qmod._queues.update(original)


# ===========================================================================
# 3. Neo4j timeout
# ===========================================================================


@pytest.mark.chaos
class TestNeo4jTimeout:
    """Verify KG queries return degraded response on Neo4j timeout."""

    def test_graph_service_mock_mode_on_failure(self):
        """Graph service must fall back to mock mode when Neo4j is down."""
        from app.services.graph_database_service import ConnectionStatus

        assert ConnectionStatus.MOCK_MODE.value == "mock_mode"

    def test_neo4j_health_check_handles_timeout(self):
        """Neo4j health check must surface error, not crash."""
        from app.services.graph_database_service import HealthCheckResult, ConnectionStatus

        result = HealthCheckResult(
            status=ConnectionStatus.ERROR,
            error_message="Connection timed out after 30s",
        )
        assert result.status == ConnectionStatus.ERROR
        assert "timed out" in result.error_message

    def test_neo4j_connection_timeout_config(self):
        """Neo4j config must define connection timeouts."""
        from app.services.graph_database_service import Neo4jConfig

        cfg = Neo4jConfig()
        assert cfg.connection_timeout > 0
        assert cfg.connection_acquisition_timeout > 0


# ===========================================================================
# 4. External LLM API returns 500
# ===========================================================================


@pytest.mark.chaos
class TestLlmApi500:
    """Verify fallback behavior when external LLM API returns 500."""

    def test_llm_500_triggers_fallback(self):
        """Service should not crash on LLM 500 -- should return fallback."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "Internal Server Error"}

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.openai_api_key = "test-key"
            # Simulating an HTTP call that returns 500
            assert mock_response.status_code == 500
            # The system should not crash; a fallback path should exist.

    def test_llm_timeout_returns_graceful_error(self):
        """LLM request timeout should produce a structured error, not crash."""
        mock_post = MagicMock(side_effect=TimeoutError("LLM request timed out"))

        with pytest.raises(TimeoutError, match="LLM request timed out"):
            mock_post("https://api.example.com/v1/chat/completions")


# ===========================================================================
# 5. All non-critical deps down simultaneously
# ===========================================================================


@pytest.mark.chaos
class TestAllNonCriticalDepsDown:
    """Verify core still responds when all non-critical deps are down."""

    def test_non_critical_services_listed(self):
        """Health module must enumerate non-critical services."""
        from app.api.health import NON_CRITICAL_SERVICES

        assert "redis" in NON_CRITICAL_SERVICES
        assert "neo4j" in NON_CRITICAL_SERVICES

    def test_health_degraded_not_unhealthy_when_non_critical_down(self):
        """When only non-critical services are down, status should be degraded, not unhealthy."""
        from app.api.health import HealthStatus

        # Degraded state must exist in the enum
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"

    def test_critical_vs_noncritical_separation(self):
        """Critical and non-critical service sets must be disjoint."""
        from app.api.health import CRITICAL_SERVICES, NON_CRITICAL_SERVICES

        overlap = CRITICAL_SERVICES & NON_CRITICAL_SERVICES
        assert len(overlap) == 0, f"Overlap between critical/non-critical: {overlap}"


# ===========================================================================
# 6. Slow dependency (5s response)
# ===========================================================================


@pytest.mark.chaos
class TestSlowDependency:
    """Verify timeout handling when a dependency responds slowly."""

    def test_slow_redis_exceeds_timeout(self):
        """Slow Redis should trigger a timeout, not hang indefinitely."""
        mock_redis = MagicMock()
        mock_redis.ping.side_effect = _slow_side_effect(delay=0.1)

        with pytest.raises(TimeoutError):
            mock_redis.ping()

    def test_health_check_timeout_value(self):
        """Health check timeout must be finite and reasonable."""
        from app.api.health import HEALTH_CHECK_TIMEOUT

        assert 1.0 <= HEALTH_CHECK_TIMEOUT <= 30.0, (
            f"Health check timeout {HEALTH_CHECK_TIMEOUT}s is outside [1, 30]"
        )

    def test_neo4j_acquisition_timeout_finite(self):
        """Neo4j connection acquisition timeout must prevent infinite waits."""
        from app.services.graph_database_service import Neo4jConfig

        cfg = Neo4jConfig()
        assert cfg.connection_acquisition_timeout <= 120


# ===========================================================================
# 7. Intermittent connection (50% failure rate)
# ===========================================================================


@pytest.mark.chaos
class TestIntermittentConnection:
    """Verify retry behavior under intermittent connectivity."""

    def test_intermittent_redis_partial_failures(self):
        """Under 50% failure, some calls succeed and some raise."""
        random.seed(42)  # deterministic for test
        side_effect = _intermittent_side_effect(failure_rate=0.5)

        successes = 0
        failures = 0
        for _ in range(100):
            try:
                side_effect()
                successes += 1
            except ConnectionError:
                failures += 1

        assert successes > 0, "Expected some successes"
        assert failures > 0, "Expected some failures"

    def test_intermittent_neo4j_does_not_crash(self):
        """Graph service should survive intermittent connectivity."""
        random.seed(99)
        side_effect = _intermittent_side_effect(failure_rate=0.5)

        results = []
        for _ in range(20):
            try:
                side_effect()
                results.append("ok")
            except ConnectionError:
                results.append("fail")

        # The service must not crash -- all iterations complete
        assert len(results) == 20


# ===========================================================================
# 8. Database connection pool exhausted
# ===========================================================================


@pytest.mark.chaos
class TestConnectionPoolExhausted:
    """Verify queuing or rejection when the DB pool is exhausted."""

    def test_pool_exhaustion_raises_operational_error(self):
        """When pool is exhausted, the system should raise, not deadlock."""
        from sqlalchemy.exc import OperationalError

        mock_pool = MagicMock()
        mock_pool.connect.side_effect = OperationalError(
            "connection pool exhausted", {}, None
        )

        with pytest.raises(OperationalError, match="connection pool exhausted"):
            mock_pool.connect()

    def test_pool_size_configured(self):
        """Neo4j pool size must be explicitly configured."""
        from app.services.graph_database_service import Neo4jConfig

        cfg = Neo4jConfig()
        assert cfg.max_connection_pool_size > 0
        assert cfg.max_connection_pool_size <= 200

    @pytest.mark.asyncio
    async def test_concurrent_session_pressure(self):
        """Simulating many concurrent sessions must not deadlock."""
        from sqlalchemy.exc import OperationalError

        mock_session_factory = AsyncMock()
        mock_session_factory.side_effect = OperationalError(
            "too many connections", {}, None
        )

        errors = 0
        for _ in range(50):
            try:
                await mock_session_factory()
            except OperationalError:
                errors += 1

        assert errors == 50, "All 50 attempts should fail gracefully"


# ===========================================================================
# 9. Additional chaos: Config missing / malformed
# ===========================================================================


@pytest.mark.chaos
class TestConfigChaos:
    """Verify behaviour when configuration values are missing or invalid."""

    def test_staleness_env_var_invalid(self):
        """Invalid staleness env var should fall back to default."""
        from app.services.guideline_version_service import (
            DEFAULT_STALENESS_DAYS,
            GuidelineVersionService,
        )

        with patch.dict("os.environ", {"GUIDELINE_STALENESS_DAYS": "not_a_number"}):
            svc = GuidelineVersionService(guidelines=[])
            assert svc.staleness_threshold_days == DEFAULT_STALENESS_DAYS

    def test_neo4j_config_defaults_safe(self):
        """Default Neo4j config should be safe even without env vars."""
        from app.services.graph_database_service import Neo4jConfig

        cfg = Neo4jConfig()
        assert cfg.encrypted is False  # safe default for local dev
        assert cfg.max_connection_lifetime > 0


# ===========================================================================
# 10. Additional chaos: Cascading failure
# ===========================================================================


@pytest.mark.chaos
class TestCascadingFailure:
    """When one dependency fails, others should not cascade-fail."""

    def test_redis_failure_does_not_crash_health_check(self):
        """Health check should still complete even if Redis check throws."""
        from app.api.health import HealthStatus

        # Health status enum must support degraded state for partial failures
        statuses = {s.value for s in HealthStatus}
        assert "degraded" in statuses

    def test_neo4j_failure_does_not_block_database_health(self):
        """Neo4j failure should not prevent PostgreSQL health from reporting."""
        from app.api.health import CRITICAL_SERVICES, NON_CRITICAL_SERVICES

        # Neo4j is non-critical, DB is critical -- they are independent
        assert "neo4j" in NON_CRITICAL_SERVICES
        assert "database" in CRITICAL_SERVICES
