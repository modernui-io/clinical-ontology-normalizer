"""Comprehensive tests for health check endpoints.

Tests all health-related endpoints including:
- /api/v1/health - Comprehensive health check
- /api/v1/health/live - Liveness probe
- /api/v1/health/ready - Readiness probe
- /health - Legacy health check
- /ready - Legacy readiness check

These tests cover:
- Successful responses
- Degraded state handling
- Error handling
- Response time requirements
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.health import (
    HealthStatus,
    ComponentStatus,
    check_database,
    check_redis,
    check_neo4j,
    check_kafka,
    _determine_overall_status,
    set_app_start_time,
    get_uptime_seconds,
)


@pytest.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestHealthEndpoint:
    """Test the comprehensive /api/v1/health endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client: AsyncClient) -> None:
        """Test health endpoint returns 200 when healthy."""
        response = await client.get("/api/v1/health")
        assert response.status_code in (200, 503)  # May be 503 if services down

    @pytest.mark.asyncio
    async def test_health_returns_required_fields(self, client: AsyncClient) -> None:
        """Test health endpoint returns all required fields."""
        response = await client.get("/api/v1/health")
        data = response.json()

        # Required fields
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "checks" in data

    @pytest.mark.asyncio
    async def test_health_status_values(self, client: AsyncClient) -> None:
        """Test health status is a valid value."""
        response = await client.get("/api/v1/health")
        data = response.json()

        valid_statuses = ["healthy", "degraded", "unhealthy"]
        assert data["status"] in valid_statuses

    @pytest.mark.asyncio
    async def test_health_timestamp_format(self, client: AsyncClient) -> None:
        """Test health timestamp is valid ISO format."""
        response = await client.get("/api/v1/health")
        data = response.json()

        # Should be parseable as ISO datetime
        timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
        assert timestamp is not None

    @pytest.mark.asyncio
    async def test_health_includes_component_checks(self, client: AsyncClient) -> None:
        """Test health includes individual component checks."""
        response = await client.get("/api/v1/health")
        data = response.json()

        checks = data["checks"]
        # Should include database at minimum
        assert "database" in checks

    @pytest.mark.asyncio
    async def test_health_component_check_format(self, client: AsyncClient) -> None:
        """Test each component check has required fields."""
        response = await client.get("/api/v1/health")
        data = response.json()

        for component, check in data["checks"].items():
            assert "status" in check
            assert check["status"] in ["up", "down"]


class TestLivenessProbe:
    """Test the /api/v1/health/live liveness probe endpoint."""

    @pytest.mark.asyncio
    async def test_live_returns_200(self, client: AsyncClient) -> None:
        """Test liveness probe always returns 200 if process is running."""
        response = await client.get("/api/v1/health/live")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_live_returns_ok_status(self, client: AsyncClient) -> None:
        """Test liveness probe returns ok status."""
        response = await client.get("/api/v1/health/live")
        data = response.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_live_returns_timestamp(self, client: AsyncClient) -> None:
        """Test liveness probe returns timestamp."""
        response = await client.get("/api/v1/health/live")
        data = response.json()
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_live_is_fast(self, client: AsyncClient) -> None:
        """Test liveness probe responds quickly (< 100ms)."""
        import time
        start = time.perf_counter()
        response = await client.get("/api/v1/health/live")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert response.status_code == 200
        assert elapsed_ms < 100, f"Liveness probe took {elapsed_ms:.2f}ms"


class TestReadinessProbe:
    """Test the /api/v1/health/ready readiness probe endpoint."""

    @pytest.mark.asyncio
    async def test_ready_returns_expected_status_code(self, client: AsyncClient) -> None:
        """Test readiness probe returns 200 or 503."""
        response = await client.get("/api/v1/health/ready")
        # 200 if ready, 503 if not
        assert response.status_code in (200, 503)

    @pytest.mark.asyncio
    async def test_ready_returns_status(self, client: AsyncClient) -> None:
        """Test readiness probe returns status field."""
        response = await client.get("/api/v1/health/ready")
        data = response.json()
        assert "status" in data
        assert data["status"] in ["ready", "not_ready"]

    @pytest.mark.asyncio
    async def test_ready_returns_service_counts(self, client: AsyncClient) -> None:
        """Test readiness probe returns service counts."""
        response = await client.get("/api/v1/health/ready")
        data = response.json()
        assert "services_ready" in data
        assert "services_total" in data
        assert isinstance(data["services_ready"], int)
        assert isinstance(data["services_total"], int)


class TestLegacyHealthEndpoint:
    """Test legacy /health endpoint."""

    @pytest.mark.asyncio
    async def test_legacy_health_returns_200(self, client: AsyncClient) -> None:
        """Test legacy health endpoint returns 200."""
        response = await client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_legacy_health_returns_healthy(self, client: AsyncClient) -> None:
        """Test legacy health returns healthy status."""
        response = await client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_legacy_health_returns_service_name(self, client: AsyncClient) -> None:
        """Test legacy health returns correct service name."""
        response = await client.get("/health")
        data = response.json()
        assert data["service"] == "clinical-ontology-normalizer"


class TestLegacyReadinessEndpoint:
    """Test legacy /ready endpoint."""

    @pytest.mark.asyncio
    async def test_legacy_ready_returns_200(self, client: AsyncClient) -> None:
        """Test legacy ready endpoint returns 200."""
        response = await client.get("/ready")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_legacy_ready_returns_status(self, client: AsyncClient) -> None:
        """Test legacy ready returns status field."""
        response = await client.get("/ready")
        data = response.json()
        assert data["status"] == "ready"


class TestHealthCheckFunctions:
    """Test individual health check functions."""

    @pytest.mark.asyncio
    async def test_check_database_success(self) -> None:
        """Test database health check with mocked connection."""
        with patch("app.core.database.async_session_maker") as mock_session:
            mock_session_instance = MagicMock()
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)

            mock_result = MagicMock()
            mock_result.scalar.return_value = 1
            mock_session_instance.execute = AsyncMock(return_value=mock_result)

            mock_session.return_value = mock_session_instance

            result = await check_database()

            assert result.status == ComponentStatus.UP
            assert result.latency_ms is not None

    @pytest.mark.asyncio
    async def test_check_database_timeout(self) -> None:
        """Test database health check handles timeout."""
        import asyncio

        with patch("app.core.database.async_session_maker") as mock_session:
            mock_session_instance = MagicMock()
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)

            async def slow_execute(*args, **kwargs):
                await asyncio.sleep(10)  # Longer than timeout

            mock_session_instance.execute = slow_execute
            mock_session.return_value = mock_session_instance

            result = await check_database()

            assert result.status == ComponentStatus.DOWN
            assert "timed out" in result.error.lower()


class TestHealthStatusDetermination:
    """Test overall health status determination logic."""

    def test_all_services_up_is_healthy(self) -> None:
        """Test all services up results in healthy status."""
        from app.api.health import ComponentHealth

        checks = {
            "database": ComponentHealth(status=ComponentStatus.UP, latency_ms=10.0),
            "redis": ComponentHealth(status=ComponentStatus.UP, latency_ms=5.0),
            "neo4j": ComponentHealth(status=ComponentStatus.UP, latency_ms=15.0),
            "kafka": ComponentHealth(status=ComponentStatus.UP, latency_ms=8.0),
        }

        status = _determine_overall_status(checks)
        assert status == HealthStatus.HEALTHY

    def test_database_down_is_unhealthy(self) -> None:
        """Test database down results in unhealthy status."""
        from app.api.health import ComponentHealth

        checks = {
            "database": ComponentHealth(status=ComponentStatus.DOWN, error="Connection failed"),
            "redis": ComponentHealth(status=ComponentStatus.UP, latency_ms=5.0),
            "neo4j": ComponentHealth(status=ComponentStatus.UP, latency_ms=15.0),
            "kafka": ComponentHealth(status=ComponentStatus.UP, latency_ms=8.0),
        }

        status = _determine_overall_status(checks)
        assert status == HealthStatus.UNHEALTHY

    def test_non_critical_down_is_degraded(self) -> None:
        """Test non-critical service down results in degraded status."""
        from app.api.health import ComponentHealth

        checks = {
            "database": ComponentHealth(status=ComponentStatus.UP, latency_ms=10.0),
            "redis": ComponentHealth(status=ComponentStatus.DOWN, error="Connection refused"),
            "neo4j": ComponentHealth(status=ComponentStatus.UP, latency_ms=15.0),
            "kafka": ComponentHealth(status=ComponentStatus.UP, latency_ms=8.0),
        }

        status = _determine_overall_status(checks)
        assert status == HealthStatus.DEGRADED


class TestUptimeTracking:
    """Test application uptime tracking."""

    def test_uptime_before_start_is_none(self) -> None:
        """Test uptime is None before start time is set."""
        # Reset start time
        import app.api.health
        app.api.health._app_start_time = None

        uptime = get_uptime_seconds()
        assert uptime is None

    def test_uptime_after_start(self) -> None:
        """Test uptime is calculated after start time is set."""
        import time

        start = time.time()
        set_app_start_time(start)

        # Wait a bit
        time.sleep(0.1)

        uptime = get_uptime_seconds()
        assert uptime is not None
        assert uptime >= 0.1


class TestHealthEndpointHTTPStatus:
    """Test HTTP status codes for health endpoints."""

    @pytest.mark.asyncio
    async def test_healthy_returns_200(self, client: AsyncClient) -> None:
        """Test healthy status returns HTTP 200."""
        # Liveness should always return 200
        response = await client.get("/api/v1/health/live")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_endpoint_consistency(self, client: AsyncClient) -> None:
        """Test health endpoint status is consistent with HTTP code."""
        response = await client.get("/api/v1/health")
        data = response.json()

        if response.status_code == 200:
            assert data["status"] in ["healthy", "degraded"]
        elif response.status_code == 503:
            assert data["status"] == "unhealthy"


class TestHealthEndpointPerformance:
    """Test health endpoint performance requirements."""

    @pytest.mark.asyncio
    async def test_health_check_under_5_seconds(self, client: AsyncClient) -> None:
        """Test comprehensive health check completes in under 5 seconds."""
        import time

        start = time.perf_counter()
        response = await client.get("/api/v1/health")
        elapsed = time.perf_counter() - start

        assert response.status_code in (200, 503)
        assert elapsed < 5.0, f"Health check took {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_liveness_check_under_100ms(self, client: AsyncClient) -> None:
        """Test liveness check completes in under 100ms."""
        import time

        start = time.perf_counter()
        response = await client.get("/api/v1/health/live")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert response.status_code == 200
        assert elapsed_ms < 100, f"Liveness check took {elapsed_ms:.2f}ms"


# ---------------------------------------------------------------------------
# P0-020: Verify X-API-Stability headers on canonical vs deprecated routes
# ---------------------------------------------------------------------------

class TestAPIStabilityHeaders:
    """Test that X-API-Stability headers are set correctly (P0-020)."""

    @pytest.mark.asyncio
    async def test_nlp_routes_return_deprecated_header(self, client: AsyncClient) -> None:
        """NLP routes should include X-API-Stability: deprecated."""
        response = await client.get("/api/v1/nlp/models")
        assert response.headers.get("x-api-stability") == "deprecated"
        assert response.headers.get("deprecation") == "true"
        assert "sunset" in response.headers

    @pytest.mark.asyncio
    async def test_nlp_routes_return_link_to_successor(self, client: AsyncClient) -> None:
        """NLP routes should link to the canonical clinical-agent successor."""
        response = await client.get("/api/v1/nlp/samples")
        link = response.headers.get("link", "")
        assert "clinical-agent" in link
        assert 'rel="successor-version"' in link

    @pytest.mark.asyncio
    async def test_clinical_agent_routes_return_pilot_header(self, client: AsyncClient) -> None:
        """Clinical-agent routes should include X-API-Stability: pilot."""
        response = await client.get("/api/v1/clinical-agent/patients")
        assert response.headers.get("x-api-stability") == "pilot"
