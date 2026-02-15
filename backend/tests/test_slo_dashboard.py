"""P2-017: Tests for SLO dashboard service."""

from __future__ import annotations

import pytest

from app.services.slo_dashboard_service import (
    DEFAULT_ERROR_RATE_TARGET,
    DEFAULT_P95_TARGET_MS,
    DEFAULT_P99_TARGET_MS,
    EndpointMetrics,
    SLOComplianceResult,
    SLODashboardService,
    SLOTarget,
    SLOViolation,
    _percentile,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def svc() -> SLODashboardService:
    return SLODashboardService()


@pytest.fixture
def populated_svc() -> SLODashboardService:
    """Service with some pre-recorded data."""
    s = SLODashboardService()
    # Record 100 fast requests on /api/documents (200ms each, 200 OK)
    for _ in range(100):
        s.record_request("/api/documents", "GET", 200.0, 200)
    # Record 10 slow requests on /api/nlp (3000ms each, 200 OK)
    for _ in range(10):
        s.record_request("/api/nlp", "POST", 3000.0, 200)
    return s


# ---------------------------------------------------------------------------
# Percentile helper
# ---------------------------------------------------------------------------

class TestPercentile:
    def test_empty(self) -> None:
        assert _percentile([], 50) == 0.0

    def test_single_value(self) -> None:
        assert _percentile([42.0], 50) == 42.0
        assert _percentile([42.0], 99) == 42.0

    def test_median(self) -> None:
        data = sorted([1.0, 2.0, 3.0, 4.0, 5.0])
        assert _percentile(data, 50) == 3.0

    def test_p95_large(self) -> None:
        data = sorted(float(i) for i in range(100))
        p95 = _percentile(data, 95)
        assert 93.0 <= p95 <= 96.0


# ---------------------------------------------------------------------------
# SLO Target defaults
# ---------------------------------------------------------------------------

class TestSLOTarget:
    def test_defaults(self) -> None:
        t = SLOTarget()
        assert t.p95_ms == DEFAULT_P95_TARGET_MS
        assert t.p99_ms == DEFAULT_P99_TARGET_MS
        assert t.error_rate == DEFAULT_ERROR_RATE_TARGET

    def test_custom(self) -> None:
        t = SLOTarget(p95_ms=100, p99_ms=500, error_rate=0.05)
        assert t.p95_ms == 100
        assert t.error_rate == 0.05


# ---------------------------------------------------------------------------
# Recording and retrieval
# ---------------------------------------------------------------------------

class TestRecordAndRetrieve:
    def test_record_single(self, svc: SLODashboardService) -> None:
        svc.record_request("/health", "GET", 5.0, 200)
        m = svc.get_endpoint_metrics("/health", "GET")
        assert m is not None
        assert m.request_count == 1
        assert m.p50_ms == 5.0

    def test_no_data_returns_none(self, svc: SLODashboardService) -> None:
        assert svc.get_endpoint_metrics("/missing", "GET") is None

    def test_multiple_methods_separate(self, svc: SLODashboardService) -> None:
        svc.record_request("/api/docs", "GET", 100.0, 200)
        svc.record_request("/api/docs", "POST", 200.0, 200)
        assert svc.get_endpoint_metrics("/api/docs", "GET") is not None
        assert svc.get_endpoint_metrics("/api/docs", "POST") is not None
        assert svc.get_endpoint_metrics("/api/docs", "GET").p50_ms != svc.get_endpoint_metrics("/api/docs", "POST").p50_ms


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class TestDashboard:
    def test_dashboard_returns_all(self, populated_svc: SLODashboardService) -> None:
        dashboard = populated_svc.get_slo_dashboard()
        assert len(dashboard) == 2
        endpoints = {m.endpoint for m in dashboard}
        assert "/api/documents" in endpoints
        assert "/api/nlp" in endpoints

    def test_dashboard_sorted(self, populated_svc: SLODashboardService) -> None:
        dashboard = populated_svc.get_slo_dashboard()
        names = [m.endpoint for m in dashboard]
        assert names == sorted(names)

    def test_empty_dashboard(self, svc: SLODashboardService) -> None:
        assert svc.get_slo_dashboard() == []


# ---------------------------------------------------------------------------
# Metrics accuracy
# ---------------------------------------------------------------------------

class TestMetricsAccuracy:
    def test_uniform_latency(self, svc: SLODashboardService) -> None:
        for _ in range(50):
            svc.record_request("/x", "GET", 100.0, 200)
        m = svc.get_endpoint_metrics("/x", "GET")
        assert m is not None
        assert m.p50_ms == 100.0
        assert m.p95_ms == 100.0
        assert m.p99_ms == 100.0

    def test_error_rate(self, svc: SLODashboardService) -> None:
        for _ in range(90):
            svc.record_request("/y", "GET", 50.0, 200)
        for _ in range(10):
            svc.record_request("/y", "GET", 50.0, 500)
        m = svc.get_endpoint_metrics("/y", "GET")
        assert m is not None
        assert m.error_rate == 0.1  # 10%
        assert m.request_count == 100

    def test_only_5xx_counts_as_error(self, svc: SLODashboardService) -> None:
        svc.record_request("/z", "GET", 50.0, 404)
        svc.record_request("/z", "GET", 50.0, 200)
        m = svc.get_endpoint_metrics("/z", "GET")
        assert m is not None
        assert m.error_rate == 0.0  # 404 is not a server error


# ---------------------------------------------------------------------------
# SLO compliance
# ---------------------------------------------------------------------------

class TestSLOCompliance:
    def test_compliant_endpoint(self, svc: SLODashboardService) -> None:
        for _ in range(100):
            svc.record_request("/fast", "GET", 50.0, 200)
        results = svc.check_slo_compliance()
        assert len(results) == 1
        assert results[0].compliant is True
        assert results[0].violations == []

    def test_p95_violation(self, svc: SLODashboardService) -> None:
        # Make p95 > 500ms
        for _ in range(100):
            svc.record_request("/slow", "GET", 600.0, 200)
        results = svc.check_slo_compliance()
        assert len(results) == 1
        assert results[0].compliant is False
        violation_metrics = [v.metric for v in results[0].violations]
        assert "p95_ms" in violation_metrics

    def test_error_rate_violation(self, svc: SLODashboardService) -> None:
        for _ in range(90):
            svc.record_request("/err", "POST", 50.0, 200)
        for _ in range(10):
            svc.record_request("/err", "POST", 50.0, 500)
        results = svc.check_slo_compliance()
        r = results[0]
        assert r.compliant is False
        violation_metrics = [v.metric for v in r.violations]
        assert "error_rate" in violation_metrics

    def test_custom_slo_target(self) -> None:
        svc = SLODashboardService(slo_target=SLOTarget(p95_ms=100, p99_ms=200, error_rate=0.001))
        for _ in range(100):
            svc.record_request("/t", "GET", 150.0, 200)
        results = svc.check_slo_compliance()
        assert results[0].compliant is False


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

class TestReset:
    def test_reset_clears_data(self, populated_svc: SLODashboardService) -> None:
        assert len(populated_svc.get_slo_dashboard()) > 0
        populated_svc.reset()
        assert len(populated_svc.get_slo_dashboard()) == 0


# ---------------------------------------------------------------------------
# Data model checks
# ---------------------------------------------------------------------------

class TestDataModels:
    def test_endpoint_metrics_fields(self, populated_svc: SLODashboardService) -> None:
        dashboard = populated_svc.get_slo_dashboard()
        m = dashboard[0]
        assert isinstance(m, EndpointMetrics)
        assert isinstance(m.period_start, float)
        assert isinstance(m.period_end, float)
        assert m.period_end >= m.period_start

    def test_slo_violation_fields(self) -> None:
        v = SLOViolation(metric="p95_ms", actual=600.0, target=500.0)
        assert v.actual > v.target

    def test_compliance_result_fields(self) -> None:
        r = SLOComplianceResult(
            endpoint="/x",
            method="GET",
            compliant=True,
            violations=[],
        )
        assert r.compliant is True
