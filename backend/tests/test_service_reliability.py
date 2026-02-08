"""Tests for VPE-4: Service Reliability SLAs.

Tests cover:
- Health check endpoints (detailed health with mocked dependencies)
- SLI collection middleware (simulated requests)
- Error budget calculations and alert thresholds
- End-to-end SLI + error budget integration

~20 tests organized into four test classes.
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.middleware.sli_collector import (
    EndpointMetrics,
    SLICollector,
    get_sli_collector,
    reset_sli_collector,
)
from app.services.error_budget_service import (
    AlertLevel,
    ErrorBudgetService,
    ServiceBudget,
    get_error_budget_service,
    reset_error_budget_service,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset singletons before and after each test."""
    reset_sli_collector()
    reset_error_budget_service()
    yield
    reset_sli_collector()
    reset_error_budget_service()


# =============================================================================
# Test EndpointMetrics (unit)
# =============================================================================


class TestEndpointMetrics:
    """Unit tests for EndpointMetrics data structure."""

    def test_record_success_increments_counts(self) -> None:
        """Recording a successful request increments total and success counts."""
        m = EndpointMetrics()
        m.record(200, 0.05, time.time())

        assert m.total_requests == 1
        assert m.success_count == 1
        assert m.error_count == 0

    def test_record_error_increments_error_count(self) -> None:
        """Recording a 500 response increments the error counter."""
        m = EndpointMetrics()
        m.record(500, 0.1, time.time())

        assert m.total_requests == 1
        assert m.success_count == 0
        assert m.error_count == 1
        assert m.error_by_status[500] == 1

    def test_error_rate_calculation(self) -> None:
        """Error rate is errors / total requests."""
        m = EndpointMetrics()
        now = time.time()
        # 8 successes, 2 errors = 20% error rate
        for _ in range(8):
            m.record(200, 0.01, now)
        for _ in range(2):
            m.record(500, 0.01, now)

        assert m.get_error_rate() == pytest.approx(0.2, abs=1e-6)

    def test_error_rate_zero_when_no_requests(self) -> None:
        """Error rate is 0 when no requests recorded."""
        m = EndpointMetrics()
        assert m.get_error_rate() == 0.0

    def test_percentile_calculation(self) -> None:
        """Percentile calculation returns correct values from sorted samples."""
        m = EndpointMetrics()
        now = time.time()
        # Record latencies: 10ms, 20ms, ..., 100ms (10 samples)
        for i in range(1, 11):
            m.record(200, i * 0.01, now)

        p50 = m.get_percentile(50)
        p95 = m.get_percentile(95)
        p99 = m.get_percentile(99)

        assert p50 is not None
        assert p95 is not None
        assert p99 is not None
        # p50 should be around 50-60ms, p95 around 90-100ms
        assert 40 <= p50 <= 70
        assert 80 <= p95 <= 110
        assert 90 <= p99 <= 110

    def test_percentile_returns_none_when_empty(self) -> None:
        """Percentile returns None when there are no latency samples."""
        m = EndpointMetrics()
        assert m.get_percentile(50) is None

    def test_to_dict_contains_all_fields(self) -> None:
        """to_dict() returns all expected metric fields."""
        m = EndpointMetrics()
        m.record(200, 0.05, time.time())
        d = m.to_dict()

        expected_keys = {
            "total_requests",
            "success_count",
            "error_count",
            "error_rate",
            "error_by_status",
            "latency_p50_ms",
            "latency_p95_ms",
            "latency_p99_ms",
            "sample_count",
        }
        assert expected_keys.issubset(d.keys())


# =============================================================================
# Test SLICollector
# =============================================================================


class TestSLICollector:
    """Tests for the SLICollector singleton and metric aggregation."""

    def test_record_and_retrieve_metrics(self) -> None:
        """Recording requests populates per-endpoint metrics."""
        collector = SLICollector(window_seconds=300)
        collector.record("GET", "/api/v1/trials", 200, 0.05)
        collector.record("GET", "/api/v1/trials", 200, 0.08)
        collector.record("GET", "/api/v1/trials", 500, 0.15)

        metrics = collector.get_all_metrics()
        key = "GET /api/v1/trials"
        assert key in metrics
        assert metrics[key]["total_requests"] == 3
        assert metrics[key]["error_count"] == 1
        assert metrics[key]["success_count"] == 2

    def test_summary_aggregates_across_endpoints(self) -> None:
        """get_summary() aggregates metrics across all endpoints."""
        collector = SLICollector(window_seconds=300)
        collector.record("GET", "/api/v1/trials", 200, 0.05)
        collector.record("POST", "/api/v1/fhir/import", 200, 0.10)
        collector.record("POST", "/api/v1/fhir/import", 500, 0.20)

        summary = collector.get_summary()
        assert summary["total_requests"] == 3
        assert summary["total_errors"] == 1
        assert summary["total_success"] == 2
        assert summary["endpoints_tracked"] == 2
        assert summary["error_rate"] == pytest.approx(1 / 3, abs=0.01)

    def test_summary_latency_percentiles(self) -> None:
        """Summary includes aggregate latency percentiles."""
        collector = SLICollector(window_seconds=300)
        for i in range(100):
            collector.record("GET", "/api/v1/health", 200, (i + 1) * 0.001)

        summary = collector.get_summary()
        assert summary["latency_p50_ms"] is not None
        assert summary["latency_p95_ms"] is not None
        assert summary["latency_p99_ms"] is not None
        # p50 ~ 50ms, p95 ~ 95ms
        assert 40 <= summary["latency_p50_ms"] <= 60
        assert 85 <= summary["latency_p95_ms"] <= 100

    def test_reset_clears_all_data(self) -> None:
        """reset() clears all collected metrics."""
        collector = SLICollector(window_seconds=300)
        collector.record("GET", "/test", 200, 0.01)
        collector.reset()

        metrics = collector.get_all_metrics()
        assert len(metrics) == 0

    def test_singleton_get_sli_collector(self) -> None:
        """get_sli_collector() returns the same instance on repeated calls."""
        c1 = get_sli_collector(window_seconds=60)
        c2 = get_sli_collector(window_seconds=120)  # window_seconds ignored
        assert c1 is c2


# =============================================================================
# Test Error Budget Service
# =============================================================================


class TestErrorBudgetService:
    """Tests for error budget tracking and alerting."""

    def test_service_budget_initial_state(self) -> None:
        """A fresh ServiceBudget has zero consumption."""
        budget = ServiceBudget(service_name="test", sla_target=0.999)

        assert budget.total_requests == 0
        assert budget.total_errors == 0
        assert budget.budget_consumed_pct == 0.0
        assert budget.budget_remaining_pct == 100.0
        assert budget.burn_rate == 0.0
        assert budget.alert_level == AlertLevel.OK

    def test_allowed_error_rate(self) -> None:
        """allowed_error_rate is 1 - sla_target."""
        budget = ServiceBudget(service_name="test", sla_target=0.999)
        assert budget.allowed_error_rate == pytest.approx(0.001)

        budget2 = ServiceBudget(service_name="test2", sla_target=0.9999)
        assert budget2.allowed_error_rate == pytest.approx(0.0001)

    def test_budget_consumption_at_50_percent(self) -> None:
        """Budget consumption crosses 50% and triggers warning."""
        # SLA = 99.0%, allowed error rate = 1.0%
        budget = ServiceBudget(service_name="nlp", sla_target=0.99)

        # Record 1000 requests with 5 errors = 0.5% error rate
        # Budget consumed = 0.5% / 1.0% = 50%
        for _ in range(995):
            budget.record(success=True)
        for _ in range(5):
            budget.record(success=False)

        assert budget.budget_consumed_pct == pytest.approx(50.0, abs=1.0)
        assert budget.alert_level == AlertLevel.WARNING

    def test_budget_consumption_at_80_percent(self) -> None:
        """Budget consumption at 80% triggers critical alert."""
        budget = ServiceBudget(service_name="api", sla_target=0.99)

        # 1000 requests, 8 errors = 0.8% error rate
        # Budget consumed = 0.8% / 1.0% = 80%
        for _ in range(992):
            budget.record(success=True)
        for _ in range(8):
            budget.record(success=False)

        assert budget.budget_consumed_pct == pytest.approx(80.0, abs=1.0)
        assert budget.alert_level == AlertLevel.CRITICAL

    def test_budget_exhausted(self) -> None:
        """Budget is exhausted when error rate exceeds allowed rate."""
        budget = ServiceBudget(service_name="db", sla_target=0.99)

        # 1000 requests, 10 errors = 1.0% error rate = 100% consumed
        for _ in range(990):
            budget.record(success=True)
        for _ in range(10):
            budget.record(success=False)

        assert budget.budget_consumed_pct >= 100.0
        assert budget.alert_level == AlertLevel.EXHAUSTED

    def test_alert_level_change_returns_new_level(self) -> None:
        """record() returns the new AlertLevel only when it changes."""
        budget = ServiceBudget(service_name="test", sla_target=0.99)

        # First request -- stays OK, no change from initial OK
        result = budget.record(success=True)
        assert result is None  # No change

        # Push to warning (need enough errors to cross 50% budget)
        # With sla=0.99, allowed rate = 1%. Need error rate > 0.5%
        for _ in range(97):
            budget.record(success=True)
        # Now at 99 requests, 0 errors. Add 1 error.
        # 1/100 = 1% = 100% budget consumed, goes straight to EXHAUSTED
        result = budget.record(success=False)
        assert result == AlertLevel.EXHAUSTED

    def test_reset_clears_budget(self) -> None:
        """reset() clears all counters and resets alert level."""
        budget = ServiceBudget(service_name="test", sla_target=0.99)
        for _ in range(10):
            budget.record(success=False)
        budget.reset()

        assert budget.total_requests == 0
        assert budget.total_errors == 0
        assert budget.alert_level == AlertLevel.OK

    def test_error_budget_service_record_and_status(self) -> None:
        """ErrorBudgetService records requests and reports correct status."""
        service = ErrorBudgetService(
            sla_targets={"api_gateway": 0.999},
            reset_interval_seconds=86400,
        )

        # Record 1000 requests, all successful
        for _ in range(1000):
            service.record_request("api_gateway", success=True)

        status = service.get_budget_status("api_gateway")
        assert status is not None
        assert status["total_requests"] == 1000
        assert status["total_errors"] == 0
        assert status["alert_level"] == "ok"
        assert status["budget_remaining_pct"] == 100.0

    def test_get_all_budgets_status(self) -> None:
        """get_all_budgets_status returns status for all configured services."""
        service = ErrorBudgetService(
            sla_targets={
                "api_gateway": 0.999,
                "trial_screening": 0.995,
                "database": 0.9999,
            },
        )
        all_status = service.get_all_budgets_status()

        assert "api_gateway" in all_status
        assert "trial_screening" in all_status
        assert "database" in all_status
        assert all_status["api_gateway"]["sla_target"] == 0.999

    def test_get_services_at_risk_filters_correctly(self) -> None:
        """get_services_at_risk returns only services above warning threshold."""
        service = ErrorBudgetService(
            sla_targets={"healthy_svc": 0.99, "risky_svc": 0.99},
        )

        # healthy_svc: all success
        for _ in range(100):
            service.record_request("healthy_svc", success=True)

        # risky_svc: high error rate (exhaust budget)
        for _ in range(90):
            service.record_request("risky_svc", success=True)
        for _ in range(10):
            service.record_request("risky_svc", success=False)

        at_risk = service.get_services_at_risk()
        assert len(at_risk) == 1
        assert at_risk[0]["service_name"] == "risky_svc"

    def test_unknown_service_returns_none(self) -> None:
        """Requesting status for an unknown service returns None."""
        service = ErrorBudgetService(sla_targets={"known": 0.999})
        assert service.get_budget_status("unknown") is None

    def test_unknown_service_record_is_ignored(self) -> None:
        """Recording to an unknown service is silently ignored."""
        service = ErrorBudgetService(sla_targets={"known": 0.999})
        result = service.record_request("unknown", success=False)
        assert result is None

    def test_singleton_get_error_budget_service(self) -> None:
        """get_error_budget_service returns the same instance on repeated calls."""
        s1 = get_error_budget_service()
        s2 = get_error_budget_service()
        assert s1 is s2

    def test_service_budget_to_dict(self) -> None:
        """to_dict() returns all expected fields."""
        budget = ServiceBudget(service_name="test", sla_target=0.999)
        budget.record(success=True)
        d = budget.to_dict()

        expected_keys = {
            "service_name",
            "sla_target",
            "sla_target_pct",
            "allowed_error_rate",
            "current_error_rate",
            "total_requests",
            "total_errors",
            "budget_consumed_pct",
            "budget_remaining_pct",
            "burn_rate",
            "alert_level",
            "last_reset",
        }
        assert expected_keys.issubset(d.keys())
        assert d["service_name"] == "test"
        assert d["sla_target_pct"] == "99.90%"

    def test_burn_rate_calculation(self) -> None:
        """Burn rate is current_error_rate / allowed_error_rate."""
        budget = ServiceBudget(service_name="test", sla_target=0.99)
        # allowed_error_rate = 0.01

        # 100 requests, 1 error = 1% error rate, burn_rate = 1% / 1% = 1.0
        for _ in range(99):
            budget.record(success=True)
        budget.record(success=False)

        assert budget.burn_rate == pytest.approx(1.0, abs=0.01)


# =============================================================================
# Test Health Check (Detailed endpoint)
# =============================================================================


class TestDetailedHealthEndpoint:
    """Tests for the /health/detailed endpoint logic."""

    @pytest.mark.asyncio
    async def test_detailed_health_structure(self) -> None:
        """The detailed health check returns correct JSON structure."""
        from unittest.mock import AsyncMock, MagicMock, patch
        from starlette.testclient import TestClient
        from app.main import app

        client = TestClient(app, raise_server_exceptions=False)

        # Mock dependencies at their source modules so the lazy imports
        # inside the endpoint function pick up the mocks.
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock()
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_session_maker = MagicMock(return_value=mock_session_ctx)

        mock_redis_client = MagicMock()
        mock_redis_client.ping.return_value = True

        with (
            patch("app.core.database.async_session_maker", mock_session_maker),
            patch("app.core.redis.get_redis", return_value=mock_redis_client),
        ):
            response = client.get("/api/v1/health/detailed")

            # Should return valid JSON with expected structure
            assert response.status_code in (200, 503)
            data = response.json()
            assert "status" in data
            assert "components" in data
            assert "latency_ms" in data
            assert "timestamp" in data
            assert data["status"] in ("healthy", "degraded", "unhealthy")
