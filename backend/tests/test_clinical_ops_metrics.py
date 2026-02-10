"""Tests for Clinical Operations Metrics Dashboard.

Covers:
- Seed data verification (KPIs, trends, scorecards, benchmarks, alerts, reports)
- KPI CRUD (create, read, update, delete, list, filter by trial/category/status)
- KPI calculation (variance, status, trend direction)
- Performance trend CRUD (create, read, delete, list, filter by KPI)
- Trial scorecard CRUD (create, read, delete, list, filter, regenerate)
- Portfolio summary computation
- Benchmark CRUD (create, read, update, delete, list, filter, compare)
- Alert management (create, acknowledge, resolve, delete, list, filter)
- Executive report lifecycle (create, generate, list, delete)
- Dashboard metrics aggregation
- Error handling (404s, 400s, invalid operations)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.clinical_ops_metrics import (
    AlertSeverity,
    BenchmarkSource,
    KPIStatus,
    MetricCategory,
    ReportPeriod,
    TrendDirection,
)
from app.services.clinical_ops_metrics_service import (
    ClinicalOpsMetricsService,
    get_clinical_ops_metrics_service,
    reset_clinical_ops_metrics_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"
ODLISIO_TRIAL = "00000000-de00-0004-0000-000000000004"
KEVZARA_TRIAL = "00000000-de00-0005-0000-000000000005"

API_PREFIX = "/api/v1/clinical-ops-metrics"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_clinical_ops_metrics_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ClinicalOpsMetricsService:
    """Shorthand for the fresh service."""
    return fresh_service


@pytest.fixture
async def client():
    """Async HTTP client for API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_kpi_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "category": "enrollment",
        "metric_name": "Test KPI Metric",
        "current_value": 75.0,
        "target_value": 80.0,
        "unit": "%",
        "period_start": (now - timedelta(days=30)).isoformat(),
        "period_end": now.isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_trend_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "kpi_id": "KPI-001",
        "period_start": (now - timedelta(days=30)).isoformat(),
        "period_end": now.isoformat(),
        "value": 72.0,
        "target": 80.0,
        "notes": "Test trend point",
    }
    defaults.update(overrides)
    return defaults


def _make_benchmark_create(**overrides) -> dict:
    defaults = {
        "category": "enrollment",
        "metric_name": "Test Benchmark",
        "internal_value": 75.0,
        "industry_value": 70.0,
        "sponsor_target": 80.0,
        "comparison_period": "Q1 2026",
        "source": "industry",
    }
    defaults.update(overrides)
    return defaults


def _make_alert_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "category": "enrollment",
        "severity": "warning",
        "message": "Test alert message",
        "metric_value": 65.0,
        "threshold_value": 80.0,
    }
    defaults.update(overrides)
    return defaults


def _make_report_generate(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "report_period": "monthly",
        "period_start": (now - timedelta(days=30)).isoformat(),
        "period_end": now.isoformat(),
        "generated_by": "test_user",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_kpis_count(self, svc: ClinicalOpsMetricsService):
        kpis = svc.list_kpis()
        assert len(kpis) == 12

    def test_seed_kpis_categories_present(self, svc: ClinicalOpsMetricsService):
        kpis = svc.list_kpis()
        categories = {k.category for k in kpis}
        assert MetricCategory.ENROLLMENT in categories
        assert MetricCategory.QUALITY in categories
        assert MetricCategory.TIMELINE in categories
        assert MetricCategory.BUDGET in categories
        assert MetricCategory.SAFETY in categories
        assert MetricCategory.COMPLIANCE in categories
        assert MetricCategory.SITE_PERFORMANCE in categories
        assert MetricCategory.DATA_MANAGEMENT in categories

    def test_seed_kpis_statuses_present(self, svc: ClinicalOpsMetricsService):
        kpis = svc.list_kpis()
        statuses = {k.status for k in kpis}
        assert KPIStatus.ON_TARGET in statuses
        assert KPIStatus.AT_RISK in statuses
        assert KPIStatus.OFF_TARGET in statuses

    def test_seed_trends_count(self, svc: ClinicalOpsMetricsService):
        trends = svc.list_trends()
        assert len(trends) == 24

    def test_seed_scorecards_count(self, svc: ClinicalOpsMetricsService):
        scorecards = svc.list_scorecards()
        assert len(scorecards) == 5

    def test_seed_benchmarks_count(self, svc: ClinicalOpsMetricsService):
        benchmarks = svc.list_benchmarks()
        assert len(benchmarks) == 7

    def test_seed_alerts_count(self, svc: ClinicalOpsMetricsService):
        alerts = svc.list_alerts()
        assert len(alerts) == 6

    def test_seed_reports_count(self, svc: ClinicalOpsMetricsService):
        reports = svc.list_reports()
        assert len(reports) == 2

    def test_seed_kpi_trend_directions(self, svc: ClinicalOpsMetricsService):
        kpis = svc.list_kpis()
        directions = {k.trend_direction for k in kpis}
        assert TrendDirection.IMPROVING in directions
        assert TrendDirection.STABLE in directions
        assert TrendDirection.DECLINING in directions
        assert TrendDirection.CRITICAL in directions

    def test_seed_alert_severities(self, svc: ClinicalOpsMetricsService):
        alerts = svc.list_alerts()
        severities = {a.severity for a in alerts}
        assert AlertSeverity.INFO in severities
        assert AlertSeverity.WARNING in severities
        assert AlertSeverity.CRITICAL in severities


# =====================================================================
# KPI CRUD
# =====================================================================


class TestKPICrud:
    """Test KPI create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_kpis(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kpis")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_kpis_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kpis", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_kpis_filter_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kpis", params={"category": "enrollment"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["category"] == "enrollment"

    @pytest.mark.anyio
    async def test_list_kpis_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kpis", params={"status": "on_target"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "on_target"

    @pytest.mark.anyio
    async def test_get_kpi(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kpis/KPI-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "KPI-001"
        assert data["metric_name"] == "Screen-to-Randomization Rate"

    @pytest.mark.anyio
    async def test_get_kpi_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kpis/KPI-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_kpi(self, client: AsyncClient):
        payload = _make_kpi_create()
        resp = await client.post(f"{API_PREFIX}/kpis", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["metric_name"] == "Test KPI Metric"
        assert data["category"] == "enrollment"
        assert data["id"].startswith("KPI-")
        assert "variance_pct" in data
        assert "status" in data

    @pytest.mark.anyio
    async def test_create_kpi_auto_status(self, client: AsyncClient):
        payload = _make_kpi_create(current_value=80.0, target_value=80.0)
        resp = await client.post(f"{API_PREFIX}/kpis", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "on_target"

    @pytest.mark.anyio
    async def test_create_kpi_off_target(self, client: AsyncClient):
        payload = _make_kpi_create(current_value=50.0, target_value=80.0)
        resp = await client.post(f"{API_PREFIX}/kpis", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "off_target"

    @pytest.mark.anyio
    async def test_update_kpi(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/kpis/KPI-001",
            json={"current_value": 82.0, "metric_name": "Updated Metric"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_value"] == 82.0
        assert data["metric_name"] == "Updated Metric"

    @pytest.mark.anyio
    async def test_update_kpi_recalculates_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/kpis/KPI-001",
            json={"current_value": 80.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "on_target"

    @pytest.mark.anyio
    async def test_update_kpi_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/kpis/KPI-NONEXISTENT",
            json={"current_value": 80.0},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_kpi(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/kpis/KPI-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/kpis/KPI-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_kpi_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/kpis/KPI-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# KPI CALCULATION
# =====================================================================


class TestKPICalculation:
    """Test KPI calculation and metrics computation."""

    @pytest.mark.anyio
    async def test_calculate_kpi(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/kpis/KPI-001/calculate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "KPI-001"
        assert "variance_pct" in data
        assert "status" in data
        assert "trend_direction" in data

    @pytest.mark.anyio
    async def test_calculate_kpi_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/kpis/KPI-NONEXISTENT/calculate")
        assert resp.status_code == 404

    def test_variance_calculation(self, svc: ClinicalOpsMetricsService):
        assert svc._calculate_variance(80.0, 100.0) == -20.0
        assert svc._calculate_variance(100.0, 100.0) == 0.0
        assert svc._calculate_variance(110.0, 100.0) == 10.0

    def test_variance_zero_target(self, svc: ClinicalOpsMetricsService):
        assert svc._calculate_variance(50.0, 0.0) == 0.0

    def test_variance_to_status_on_target(self, svc: ClinicalOpsMetricsService):
        assert svc._variance_to_status(0.0) == KPIStatus.ON_TARGET
        assert svc._variance_to_status(-5.0) == KPIStatus.ON_TARGET

    def test_variance_to_status_at_risk(self, svc: ClinicalOpsMetricsService):
        assert svc._variance_to_status(-10.0) == KPIStatus.AT_RISK
        assert svc._variance_to_status(-15.0) == KPIStatus.AT_RISK

    def test_variance_to_status_off_target(self, svc: ClinicalOpsMetricsService):
        assert svc._variance_to_status(-20.0) == KPIStatus.OFF_TARGET
        assert svc._variance_to_status(-50.0) == KPIStatus.OFF_TARGET

    def test_compute_trend_direction_insufficient_data(self, svc: ClinicalOpsMetricsService):
        assert svc._compute_trend_direction([]) == TrendDirection.STABLE

    def test_kpi_to_score_on_target(self, svc: ClinicalOpsMetricsService):
        kpi = svc.get_kpi("KPI-006")  # SAE Reporting Compliance - ON_TARGET
        assert kpi is not None
        score = svc._kpi_to_score(kpi)
        assert score >= 80.0

    def test_kpi_to_score_off_target(self, svc: ClinicalOpsMetricsService):
        kpi = svc.get_kpi("KPI-011")  # SDV Rate - OFF_TARGET
        assert kpi is not None
        score = svc._kpi_to_score(kpi)
        assert score < 50.0


# =====================================================================
# PERFORMANCE TRENDS
# =====================================================================


class TestPerformanceTrends:
    """Test performance trend CRUD operations."""

    @pytest.mark.anyio
    async def test_list_trends(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trends")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 24

    @pytest.mark.anyio
    async def test_list_trends_filter_kpi(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trends", params={"kpi_id": "KPI-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["kpi_id"] == "KPI-001"

    @pytest.mark.anyio
    async def test_get_trend(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trends/TRN-0001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "TRN-0001"
        assert data["kpi_id"] == "KPI-001"

    @pytest.mark.anyio
    async def test_get_trend_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trends/TRN-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_trend(self, client: AsyncClient):
        payload = _make_trend_create()
        resp = await client.post(f"{API_PREFIX}/trends", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["kpi_id"] == "KPI-001"
        assert data["value"] == 72.0
        assert "variance_pct" in data

    @pytest.mark.anyio
    async def test_delete_trend(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/trends/TRN-0001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/trends/TRN-0001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_trend_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/trends/TRN-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_trend_sorted_by_period(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trends", params={"kpi_id": "KPI-001"})
        data = resp.json()
        periods = [item["period_start"] for item in data["items"]]
        assert periods == sorted(periods)


# =====================================================================
# TRIAL SCORECARDS
# =====================================================================


class TestTrialScorecards:
    """Test trial scorecard CRUD and generation."""

    @pytest.mark.anyio
    async def test_list_scorecards(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/scorecards")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_list_scorecards_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/scorecards", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_scorecards_filter_phase(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/scorecards", params={"phase": "Phase III"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["phase"] == "Phase III"

    @pytest.mark.anyio
    async def test_list_scorecards_filter_therapeutic_area(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/scorecards", params={"therapeutic_area": "Oncology"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    @pytest.mark.anyio
    async def test_list_scorecards_sorted_by_score(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/scorecards")
        data = resp.json()
        scores = [item["overall_score"] for item in data["items"]]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.anyio
    async def test_get_scorecard(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/scorecards/SC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SC-001"
        assert data["trial_name"] == "EYLEA HD Phase III - Wet AMD"
        assert 0 <= data["overall_score"] <= 100

    @pytest.mark.anyio
    async def test_get_scorecard_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/scorecards/SC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_scorecard(self, client: AsyncClient):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "trial_name": "Test Trial Scorecard",
            "phase": "Phase II",
            "therapeutic_area": "Cardiology",
        }
        resp = await client.post(f"{API_PREFIX}/scorecards", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_name"] == "Test Trial Scorecard"
        assert data["id"].startswith("SC-")
        assert 0 <= data["overall_score"] <= 100

    @pytest.mark.anyio
    async def test_generate_scorecard(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/scorecards/SC-001/generate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SC-001"
        assert 0 <= data["overall_score"] <= 100

    @pytest.mark.anyio
    async def test_generate_scorecard_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/scorecards/SC-NONEXISTENT/generate")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_scorecard(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/scorecards/SC-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/scorecards/SC-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_scorecard_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/scorecards/SC-NONEXISTENT")
        assert resp.status_code == 404

    def test_scorecard_has_all_dimensions(self, svc: ClinicalOpsMetricsService):
        sc = svc.get_scorecard("SC-001")
        assert sc is not None
        assert 0 <= sc.enrollment_score <= 100
        assert 0 <= sc.quality_score <= 100
        assert 0 <= sc.timeline_score <= 100
        assert 0 <= sc.budget_score <= 100
        assert 0 <= sc.safety_score <= 100
        assert 0 <= sc.compliance_score <= 100

    def test_worst_scorecard_has_risk_flags(self, svc: ClinicalOpsMetricsService):
        sc = svc.get_scorecard("SC-005")  # KEVZARA - worst performing
        assert sc is not None
        assert len(sc.risk_flags) > 0


# =====================================================================
# PORTFOLIO SUMMARY
# =====================================================================


class TestPortfolioSummary:
    """Test portfolio summary computation."""

    @pytest.mark.anyio
    async def test_get_portfolio_summary(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/portfolio-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_trials"] == 5
        assert data["total_sites"] > 0
        assert data["total_patients"] > 0
        assert 0 <= data["trials_on_track_pct"] <= 100

    @pytest.mark.anyio
    async def test_portfolio_summary_trials_by_phase(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/portfolio-summary")
        data = resp.json()
        assert "Phase III" in data["trials_by_phase"]
        total_by_phase = sum(data["trials_by_phase"].values())
        assert total_by_phase == data["total_trials"]

    def test_portfolio_summary_critical_alerts(self, svc: ClinicalOpsMetricsService):
        summary = svc.get_portfolio_summary()
        # Verify critical alerts count matches actual critical unresolved alerts
        alerts = svc.list_alerts(severity=AlertSeverity.CRITICAL, resolved=False)
        assert summary.critical_alerts_count == len(alerts)

    def test_portfolio_summary_enrollment_rate(self, svc: ClinicalOpsMetricsService):
        summary = svc.get_portfolio_summary()
        assert summary.overall_enrollment_rate > 0

    def test_portfolio_summary_on_track_calculation(self, svc: ClinicalOpsMetricsService):
        summary = svc.get_portfolio_summary()
        scorecards = svc.list_scorecards()
        on_track = sum(1 for sc in scorecards if sc.overall_score >= 70.0)
        expected_pct = round((on_track / max(1, len(scorecards))) * 100, 1)
        assert summary.trials_on_track_pct == expected_pct


# =====================================================================
# BENCHMARKS
# =====================================================================


class TestBenchmarks:
    """Test benchmark CRUD and comparison operations."""

    @pytest.mark.anyio
    async def test_list_benchmarks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/benchmarks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 7

    @pytest.mark.anyio
    async def test_list_benchmarks_filter_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/benchmarks", params={"category": "enrollment"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["category"] == "enrollment"

    @pytest.mark.anyio
    async def test_list_benchmarks_filter_source(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/benchmarks", params={"source": "industry"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["source"] == "industry"

    @pytest.mark.anyio
    async def test_get_benchmark(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/benchmarks/BM-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "BM-001"
        assert data["metric_name"] == "Screen-to-Randomization Rate"

    @pytest.mark.anyio
    async def test_get_benchmark_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/benchmarks/BM-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_benchmark(self, client: AsyncClient):
        payload = _make_benchmark_create()
        resp = await client.post(f"{API_PREFIX}/benchmarks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["metric_name"] == "Test Benchmark"
        assert data["id"].startswith("BM-")
        assert 0 <= data["percentile_rank"] <= 100

    @pytest.mark.anyio
    async def test_update_benchmark(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/benchmarks/BM-001",
            json={"internal_value": 78.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["internal_value"] == 78.0

    @pytest.mark.anyio
    async def test_update_benchmark_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/benchmarks/BM-NONEXISTENT",
            json={"internal_value": 80.0},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_benchmark(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/benchmarks/BM-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/benchmarks/BM-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_benchmark_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/benchmarks/BM-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_compare_benchmarks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/benchmarks/compare")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 7
        # Verify sorted by percentile_rank ascending (worst first)
        ranks = [item["percentile_rank"] for item in data["items"]]
        assert ranks == sorted(ranks)

    @pytest.mark.anyio
    async def test_compare_benchmarks_filter_category(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/benchmarks/compare", params={"category": "safety"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["category"] == "safety"

    def test_calculate_percentile(self, svc: ClinicalOpsMetricsService):
        # Internal better than industry
        assert svc._calculate_percentile(80.0, 70.0) > 50.0
        # Internal equal to industry
        assert svc._calculate_percentile(70.0, 70.0) == 50.0
        # Internal worse than industry
        assert svc._calculate_percentile(60.0, 70.0) < 50.0

    def test_calculate_percentile_zero_industry(self, svc: ClinicalOpsMetricsService):
        assert svc._calculate_percentile(80.0, 0.0) == 50.0


# =====================================================================
# OPERATIONAL ALERTS
# =====================================================================


class TestOperationalAlerts:
    """Test operational alert management."""

    @pytest.mark.anyio
    async def test_list_alerts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6

    @pytest.mark.anyio
    async def test_list_alerts_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts", params={"trial_id": KEVZARA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == KEVZARA_TRIAL

    @pytest.mark.anyio
    async def test_list_alerts_filter_severity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts", params={"severity": "critical"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["severity"] == "critical"

    @pytest.mark.anyio
    async def test_list_alerts_filter_acknowledged(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts", params={"acknowledged": False})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["acknowledged"] is False

    @pytest.mark.anyio
    async def test_list_alerts_filter_resolved(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts", params={"resolved": True})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["resolved_date"] is not None

    @pytest.mark.anyio
    async def test_list_alerts_filter_unresolved(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts", params={"resolved": False})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["resolved_date"] is None

    @pytest.mark.anyio
    async def test_get_alert(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts/OA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "OA-001"

    @pytest.mark.anyio
    async def test_get_alert_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts/OA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_alert(self, client: AsyncClient):
        payload = _make_alert_create()
        resp = await client.post(f"{API_PREFIX}/alerts", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["message"] == "Test alert message"
        assert data["acknowledged"] is False
        assert data["resolved_date"] is None

    @pytest.mark.anyio
    async def test_acknowledge_alert(self, client: AsyncClient):
        # OA-002 is unacknowledged
        payload = {"acknowledged_by": "Dr. Test User"}
        resp = await client.post(f"{API_PREFIX}/alerts/OA-002/acknowledge", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["acknowledged"] is True
        assert data["acknowledged_by"] == "Dr. Test User"

    @pytest.mark.anyio
    async def test_acknowledge_alert_already_acknowledged(self, client: AsyncClient):
        # OA-001 is already acknowledged
        payload = {"acknowledged_by": "Another User"}
        resp = await client.post(f"{API_PREFIX}/alerts/OA-001/acknowledge", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_acknowledge_alert_not_found(self, client: AsyncClient):
        payload = {"acknowledged_by": "Test User"}
        resp = await client.post(f"{API_PREFIX}/alerts/OA-NONEXISTENT/acknowledge", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_resolve_alert(self, client: AsyncClient):
        # OA-002 is unresolved
        payload = {"resolved_by": "Dr. Test User", "notes": "Resolved via remediation"}
        resp = await client.post(f"{API_PREFIX}/alerts/OA-002/resolve", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["resolved_date"] is not None
        assert data["acknowledged"] is True

    @pytest.mark.anyio
    async def test_resolve_alert_already_resolved(self, client: AsyncClient):
        # OA-006 is already resolved
        payload = {"resolved_by": "Test User"}
        resp = await client.post(f"{API_PREFIX}/alerts/OA-006/resolve", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_resolve_alert_not_found(self, client: AsyncClient):
        payload = {"resolved_by": "Test User"}
        resp = await client.post(f"{API_PREFIX}/alerts/OA-NONEXISTENT/resolve", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_alert(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/alerts/OA-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/alerts/OA-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_alert_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/alerts/OA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_alerts_sorted_by_date_descending(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts")
        data = resp.json()
        dates = [item["created_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)


# =====================================================================
# EXECUTIVE REPORTS
# =====================================================================


class TestExecutiveReports:
    """Test executive report lifecycle."""

    @pytest.mark.anyio
    async def test_list_reports(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    @pytest.mark.anyio
    async def test_list_reports_filter_period(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports", params={"report_period": "monthly"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["report_period"] == "monthly"

    @pytest.mark.anyio
    async def test_get_report(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports/RPT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RPT-001"
        assert "portfolio_summary" in data
        assert "key_achievements" in data
        assert "key_risks" in data
        assert "recommendations" in data

    @pytest.mark.anyio
    async def test_get_report_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports/RPT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_generate_executive_report(self, client: AsyncClient):
        payload = _make_report_generate()
        resp = await client.post(f"{API_PREFIX}/reports/generate", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("RPT-")
        assert data["report_period"] == "monthly"
        assert data["generated_by"] == "test_user"
        assert len(data["portfolio_summary"]) > 0
        assert len(data["key_achievements"]) > 0
        assert len(data["key_risks"]) > 0
        assert len(data["recommendations"]) > 0

    @pytest.mark.anyio
    async def test_generate_quarterly_report(self, client: AsyncClient):
        payload = _make_report_generate(report_period="quarterly")
        resp = await client.post(f"{API_PREFIX}/reports/generate", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["report_period"] == "quarterly"

    @pytest.mark.anyio
    async def test_delete_report(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/reports/RPT-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/reports/RPT-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_report_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/reports/RPT-NONEXISTENT")
        assert resp.status_code == 404

    def test_report_portfolio_summary_populated(self, svc: ClinicalOpsMetricsService):
        report = svc.get_report("RPT-002")
        assert report is not None
        ps = report.portfolio_summary
        assert ps.total_trials > 0
        assert ps.total_sites > 0
        assert ps.total_patients > 0

    def test_report_has_achievements_and_risks(self, svc: ClinicalOpsMetricsService):
        report = svc.get_report("RPT-002")
        assert report is not None
        assert len(report.key_achievements) > 0
        assert len(report.key_risks) > 0
        assert len(report.recommendations) > 0


# =====================================================================
# DASHBOARD METRICS
# =====================================================================


class TestDashboardMetrics:
    """Test dashboard metrics aggregation."""

    @pytest.mark.anyio
    async def test_get_dashboard_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_kpis"] == 12
        assert data["kpis_on_target"] + data["kpis_at_risk"] + data["kpis_off_target"] == 12
        assert data["active_alerts"] >= 0
        assert data["total_scorecards"] == 5
        assert 0 <= data["avg_overall_score"] <= 100

    @pytest.mark.anyio
    async def test_dashboard_has_portfolio_summary(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dashboard")
        data = resp.json()
        ps = data["portfolio_summary"]
        assert ps["total_trials"] == 5
        assert ps["total_sites"] > 0
        assert ps["total_patients"] > 0

    @pytest.mark.anyio
    async def test_dashboard_has_top_risks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dashboard")
        data = resp.json()
        assert "top_risks" in data
        assert len(data["top_risks"]) > 0

    def test_dashboard_kpi_counts_match(self, svc: ClinicalOpsMetricsService):
        dashboard = svc.get_dashboard_metrics()
        kpis = svc.list_kpis()
        assert dashboard.total_kpis == len(kpis)
        on_target = sum(1 for k in kpis if k.status == KPIStatus.ON_TARGET)
        at_risk = sum(1 for k in kpis if k.status == KPIStatus.AT_RISK)
        off_target = sum(1 for k in kpis if k.status == KPIStatus.OFF_TARGET)
        assert dashboard.kpis_on_target == on_target
        assert dashboard.kpis_at_risk == at_risk
        assert dashboard.kpis_off_target == off_target

    def test_dashboard_alert_counts(self, svc: ClinicalOpsMetricsService):
        dashboard = svc.get_dashboard_metrics()
        all_alerts = svc.list_alerts()
        active = sum(1 for a in all_alerts if a.resolved_date is None)
        critical = sum(
            1 for a in all_alerts
            if a.severity == AlertSeverity.CRITICAL and a.resolved_date is None
        )
        assert dashboard.active_alerts == active
        assert dashboard.critical_alerts == critical

    def test_dashboard_avg_score(self, svc: ClinicalOpsMetricsService):
        dashboard = svc.get_dashboard_metrics()
        scorecards = svc.list_scorecards()
        expected_avg = round(sum(s.overall_score for s in scorecards) / len(scorecards), 1)
        assert dashboard.avg_overall_score == expected_avg

    def test_dashboard_benchmark_count(self, svc: ClinicalOpsMetricsService):
        dashboard = svc.get_dashboard_metrics()
        benchmarks = svc.list_benchmarks()
        assert dashboard.total_benchmarks == len(benchmarks)


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_clinical_ops_metrics_service()
        svc2 = get_clinical_ops_metrics_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_clinical_ops_metrics_service()
        svc2 = reset_clinical_ops_metrics_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_clinical_ops_metrics_service()
        svc.delete_kpi("KPI-001")
        assert svc.get_kpi("KPI-001") is None
        svc2 = reset_clinical_ops_metrics_service()
        assert svc2.get_kpi("KPI-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_kpis_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kpis")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_trends_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trends")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_scorecards_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/scorecards")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_benchmarks_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/benchmarks")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_alerts_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_reports_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_kpi_create_with_all_categories(self, client: AsyncClient):
        """Verify KPIs can be created for all categories."""
        for cat in ["enrollment", "quality", "timeline", "budget", "safety",
                     "compliance", "site_performance", "data_management"]:
            payload = _make_kpi_create(category=cat, metric_name=f"Test {cat}")
            resp = await client.post(f"{API_PREFIX}/kpis", json=payload)
            assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_benchmark_with_all_sources(self, client: AsyncClient):
        for source in ["internal", "industry", "sponsor_target"]:
            payload = _make_benchmark_create(source=source, metric_name=f"Test {source}")
            resp = await client.post(f"{API_PREFIX}/benchmarks", json=payload)
            assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_alert_with_all_severities(self, client: AsyncClient):
        for severity in ["info", "warning", "critical"]:
            payload = _make_alert_create(severity=severity, message=f"Test {severity}")
            resp = await client.post(f"{API_PREFIX}/alerts", json=payload)
            assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_report_with_all_periods(self, client: AsyncClient):
        for period in ["weekly", "monthly", "quarterly", "annual"]:
            payload = _make_report_generate(report_period=period)
            resp = await client.post(f"{API_PREFIX}/reports/generate", json=payload)
            assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_create_trend_with_notes(self, client: AsyncClient):
        payload = _make_trend_create(notes="Important observation about this period")
        resp = await client.post(f"{API_PREFIX}/trends", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["notes"] == "Important observation about this period"

    @pytest.mark.anyio
    async def test_create_trend_without_notes(self, client: AsyncClient):
        payload = _make_trend_create()
        del payload["notes"]
        resp = await client.post(f"{API_PREFIX}/trends", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_kpi_variance_positive(self, client: AsyncClient):
        """KPI where current exceeds target should have positive variance."""
        payload = _make_kpi_create(current_value=95.0, target_value=80.0)
        resp = await client.post(f"{API_PREFIX}/kpis", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["variance_pct"] > 0
        assert data["status"] == "on_target"

    @pytest.mark.anyio
    async def test_kpi_variance_negative(self, client: AsyncClient):
        """KPI where current is below target should have negative variance."""
        payload = _make_kpi_create(current_value=50.0, target_value=80.0)
        resp = await client.post(f"{API_PREFIX}/kpis", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["variance_pct"] < 0

    @pytest.mark.anyio
    async def test_scorecard_for_trial_without_kpis(self, client: AsyncClient):
        """Creating a scorecard for a trial with no KPIs should use default scores."""
        payload = {
            "trial_id": "TRIAL-NODATA",
            "trial_name": "Trial With No Data",
            "phase": "Phase I",
            "therapeutic_area": "Unknown",
        }
        resp = await client.post(f"{API_PREFIX}/scorecards", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        # Should default to 75.0 for each dimension
        assert data["enrollment_score"] == 75.0

    @pytest.mark.anyio
    async def test_update_kpi_preserves_unset_fields(self, client: AsyncClient):
        """Updating only one field should preserve all others."""
        # Get original
        resp1 = await client.get(f"{API_PREFIX}/kpis/KPI-001")
        original = resp1.json()
        # Update only current_value
        resp2 = await client.put(
            f"{API_PREFIX}/kpis/KPI-001",
            json={"current_value": 99.0},
        )
        updated = resp2.json()
        assert updated["current_value"] == 99.0
        assert updated["target_value"] == original["target_value"]
        assert updated["unit"] == original["unit"]

    @pytest.mark.anyio
    async def test_update_benchmark_recalculates_percentile(self, client: AsyncClient):
        """Updating benchmark values should recalculate percentile rank."""
        resp1 = await client.get(f"{API_PREFIX}/benchmarks/BM-001")
        original_percentile = resp1.json()["percentile_rank"]

        resp2 = await client.put(
            f"{API_PREFIX}/benchmarks/BM-001",
            json={"internal_value": 100.0},
        )
        assert resp2.status_code == 200
        new_percentile = resp2.json()["percentile_rank"]
        assert new_percentile != original_percentile

    @pytest.mark.anyio
    async def test_resolve_alert_sets_acknowledged(self, client: AsyncClient):
        """Resolving an unacknowledged alert should also acknowledge it."""
        payload = {"resolved_by": "Auto Resolver"}
        resp = await client.post(f"{API_PREFIX}/alerts/OA-004/resolve", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["resolved_date"] is not None
        assert data["acknowledged"] is True


# =====================================================================
# ENUMERATION VALUES
# =====================================================================


class TestEnumerations:
    """Test enum values are correctly used throughout the system."""

    @pytest.mark.anyio
    async def test_all_metric_categories_in_kpis(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kpis")
        data = resp.json()
        categories = {item["category"] for item in data["items"]}
        expected = {"enrollment", "quality", "timeline", "budget", "safety",
                    "compliance", "site_performance", "data_management"}
        assert categories == expected

    @pytest.mark.anyio
    async def test_all_trend_directions_in_kpis(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kpis")
        data = resp.json()
        directions = {item["trend_direction"] for item in data["items"]}
        assert "improving" in directions
        assert "stable" in directions
        assert "declining" in directions
        assert "critical" in directions

    @pytest.mark.anyio
    async def test_all_kpi_statuses_in_kpis(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kpis")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "on_target" in statuses
        assert "at_risk" in statuses
        assert "off_target" in statuses

    @pytest.mark.anyio
    async def test_all_alert_severities_in_alerts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts")
        data = resp.json()
        severities = {item["severity"] for item in data["items"]}
        assert "info" in severities
        assert "warning" in severities
        assert "critical" in severities

    @pytest.mark.anyio
    async def test_scorecard_score_ranges(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/scorecards")
        data = resp.json()
        for item in data["items"]:
            assert 0 <= item["overall_score"] <= 100
            assert 0 <= item["enrollment_score"] <= 100
            assert 0 <= item["quality_score"] <= 100
            assert 0 <= item["timeline_score"] <= 100
            assert 0 <= item["budget_score"] <= 100
            assert 0 <= item["safety_score"] <= 100
            assert 0 <= item["compliance_score"] <= 100


# =====================================================================
# GENERATED REPORT CONTENT
# =====================================================================


class TestGeneratedReportContent:
    """Test that generated executive reports contain meaningful content."""

    def test_generated_report_achievements(self, svc: ClinicalOpsMetricsService):
        now = datetime.now(timezone.utc)
        from app.schemas.clinical_ops_metrics import ExecutiveReportGenerate
        payload = ExecutiveReportGenerate(
            report_period=ReportPeriod.MONTHLY,
            period_start=now - timedelta(days=30),
            period_end=now,
            generated_by="test",
        )
        report = svc.generate_executive_report(payload)
        assert len(report.key_achievements) > 0

    def test_generated_report_risks(self, svc: ClinicalOpsMetricsService):
        now = datetime.now(timezone.utc)
        from app.schemas.clinical_ops_metrics import ExecutiveReportGenerate
        payload = ExecutiveReportGenerate(
            report_period=ReportPeriod.QUARTERLY,
            period_start=now - timedelta(days=90),
            period_end=now,
            generated_by="test",
        )
        report = svc.generate_executive_report(payload)
        assert len(report.key_risks) > 0

    def test_generated_report_recommendations(self, svc: ClinicalOpsMetricsService):
        now = datetime.now(timezone.utc)
        from app.schemas.clinical_ops_metrics import ExecutiveReportGenerate
        payload = ExecutiveReportGenerate(
            report_period=ReportPeriod.WEEKLY,
            period_start=now - timedelta(days=7),
            period_end=now,
            generated_by="ops_team",
        )
        report = svc.generate_executive_report(payload)
        assert len(report.recommendations) > 0

    def test_generated_report_portfolio_summary_accurate(self, svc: ClinicalOpsMetricsService):
        now = datetime.now(timezone.utc)
        from app.schemas.clinical_ops_metrics import ExecutiveReportGenerate
        payload = ExecutiveReportGenerate(
            report_period=ReportPeriod.MONTHLY,
            period_start=now - timedelta(days=30),
            period_end=now,
            generated_by="test",
        )
        report = svc.generate_executive_report(payload)
        live_summary = svc.get_portfolio_summary()
        assert report.portfolio_summary.total_trials == live_summary.total_trials
        assert report.portfolio_summary.total_sites == live_summary.total_sites
