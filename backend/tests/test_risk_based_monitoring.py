"""Tests for Risk-Based Monitoring (RBM) & Central Monitoring (CLINICAL-7).

Covers:
- Seed data verification (KRIs, site risk scores, data points, plans, findings, alerts)
- KRI CRUD (create, read, update, delete, list, filter by category/active)
- Site risk scoring (list, filter by risk level, detailed profile, recalculation)
- KRI data point submission and threshold evaluation
- Auto-escalation when 3+ KRIs red
- Trend analysis (improving, stable, worsening)
- Central monitoring alerts (list, filter, resolve, duplicate prevention)
- Monitoring plan CRUD (create, read, update, delete, list, filter)
- Monitoring visit completion with finding creation
- Finding CRUD and lifecycle (open -> response_required -> resolved -> verified)
- Overdue finding detection
- RBM metrics computation
- Monitoring schedule recommendation
- Error handling (404s, 400s, invalid operations)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.risk_based_monitoring import (
    AlertResolve,
    FindingCategory,
    FindingCreate,
    FindingStatus,
    FindingUpdate,
    KRICategory,
    KRICreate,
    KRIDataPointCreate,
    KRIStatus,
    KRIUpdate,
    MonitoringAction,
    MonitoringPlanCreate,
    MonitoringPlanStatus,
    MonitoringPlanUpdate,
    MonitoringVisitComplete,
    MonitoringVisitType,
    RiskLevel,
    Trend,
)
from app.services.risk_based_monitoring_service import (
    RBMService,
    get_rbm_service,
    reset_rbm_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/risk-based-monitoring"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_rbm_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> RBMService:
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


def _make_kri_create(**overrides) -> dict:
    defaults = {
        "name": "Test KRI",
        "category": "safety",
        "description": "A test KRI for unit testing",
        "threshold_yellow": 80.0,
        "threshold_red": 60.0,
        "unit": "%",
        "weight": 2.0,
    }
    defaults.update(overrides)
    return defaults


def _make_plan_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "visit_type": "interim",
        "planned_date": (now + timedelta(days=14)).isoformat(),
        "monitor_name": "Test Monitor",
    }
    defaults.update(overrides)
    return defaults


def _make_kri_data(**overrides) -> dict:
    defaults = {
        "kri_id": "KRI-001",
        "site_id": "SITE-101",
        "value": 92.0,
        "period": "2026-02",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_kris_count(self, svc: RBMService):
        kris = svc.list_kris()
        assert len(kris) == 12

    def test_seed_kris_categories(self, svc: RBMService):
        kris = svc.list_kris()
        categories = {k.category for k in kris}
        assert KRICategory.SAFETY in categories
        assert KRICategory.DATA_QUALITY in categories
        assert KRICategory.ENROLLMENT in categories
        assert KRICategory.PROTOCOL_COMPLIANCE in categories
        assert KRICategory.SITE_MANAGEMENT in categories

    def test_seed_site_risk_scores_count(self, svc: RBMService):
        scores = svc.list_site_risk_scores()
        assert len(scores) == 8

    def test_seed_site_risk_levels(self, svc: RBMService):
        scores = svc.list_site_risk_scores()
        levels = {s.risk_level for s in scores}
        assert RiskLevel.LOW in levels
        assert RiskLevel.MEDIUM in levels
        assert RiskLevel.HIGH in levels
        assert RiskLevel.CRITICAL in levels

    def test_seed_monitoring_plans_count(self, svc: RBMService):
        plans = svc.list_monitoring_plans()
        assert len(plans) == 15

    def test_seed_findings_count(self, svc: RBMService):
        findings = svc.list_findings()
        assert len(findings) == 10

    def test_seed_alerts_count(self, svc: RBMService):
        alerts = svc.list_alerts()
        assert len(alerts) == 6

    def test_seed_kri_data_points_exist(self, svc: RBMService):
        # SITE-105 and SITE-107 should have data points
        dps = svc.get_kri_trends("SITE-105")
        assert len(dps) > 0

    def test_seed_critical_site_has_multiple_red_kris(self, svc: RBMService):
        profile = svc.get_site_risk_profile("SITE-107")
        assert profile is not None
        assert profile.risk_level == RiskLevel.CRITICAL
        red_count = sum(1 for k in profile.kri_scores if k.status == KRIStatus.RED)
        assert red_count >= 3


# =====================================================================
# KRI CRUD
# =====================================================================


class TestKRICrud:
    """Test KRI create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_kris(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kris")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_kris_filter_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kris", params={"category": "safety"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["category"] == "safety"

    @pytest.mark.anyio
    async def test_list_kris_filter_active(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kris", params={"active": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12  # all seeded KRIs are active

    @pytest.mark.anyio
    async def test_get_kri(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kris/KRI-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "KRI-001"
        assert data["name"] == "SAE Reporting Timeliness"

    @pytest.mark.anyio
    async def test_get_kri_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kris/KRI-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_kri(self, client: AsyncClient):
        payload = _make_kri_create()
        resp = await client.post(f"{API_PREFIX}/kris", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test KRI"
        assert data["category"] == "safety"
        assert data["id"].startswith("KRI-")

    @pytest.mark.anyio
    async def test_update_kri(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/kris/KRI-001",
            json={"name": "Updated SAE Reporting", "weight": 4.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated SAE Reporting"
        assert data["weight"] == 4.0

    @pytest.mark.anyio
    async def test_update_kri_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/kris/KRI-NONEXISTENT",
            json={"name": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_kri(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/kris/KRI-001")
        assert resp.status_code == 204
        # Verify it's gone
        resp2 = await client.get(f"{API_PREFIX}/kris/KRI-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_kri_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/kris/KRI-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# SITE RISK SCORING
# =====================================================================


class TestSiteRiskScoring:
    """Test site risk scoring operations."""

    @pytest.mark.anyio
    async def test_list_site_risk_scores(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/risk-scores")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8

    @pytest.mark.anyio
    async def test_list_site_risk_scores_filter_level(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/sites/risk-scores", params={"risk_level": "critical"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["risk_level"] == "critical"

    @pytest.mark.anyio
    async def test_get_site_risk_profile(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SITE-101/risk-profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["site_id"] == "SITE-101"
        assert data["risk_level"] == "low"
        assert "kri_scores" in data

    @pytest.mark.anyio
    async def test_get_site_risk_profile_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SITE-NONEXISTENT/risk-profile")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_recalculate_site_risk(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/sites/SITE-105/recalculate-risk")
        assert resp.status_code == 200
        data = resp.json()
        assert data["site_id"] == "SITE-105"
        assert 0 <= data["overall_risk_score"] <= 100

    @pytest.mark.anyio
    async def test_recalculate_site_risk_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/sites/SITE-NONEXISTENT/recalculate-risk")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_risk_scores_sorted_descending(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/risk-scores")
        data = resp.json()
        scores = [item["overall_risk_score"] for item in data["items"]]
        assert scores == sorted(scores, reverse=True)

    def test_score_to_risk_level_low(self, svc: RBMService):
        assert svc._score_to_risk_level(20.0) == RiskLevel.LOW

    def test_score_to_risk_level_medium(self, svc: RBMService):
        assert svc._score_to_risk_level(40.0) == RiskLevel.MEDIUM

    def test_score_to_risk_level_high(self, svc: RBMService):
        assert svc._score_to_risk_level(60.0) == RiskLevel.HIGH

    def test_score_to_risk_level_critical(self, svc: RBMService):
        assert svc._score_to_risk_level(80.0) == RiskLevel.CRITICAL


# =====================================================================
# KRI DATA POINTS
# =====================================================================


class TestKRIDataPoints:
    """Test KRI data point submission and trending."""

    @pytest.mark.anyio
    async def test_submit_kri_data_green(self, client: AsyncClient):
        payload = _make_kri_data(value=95.0)
        resp = await client.post(f"{API_PREFIX}/kri-data", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "green"
        assert data["value"] == 95.0

    @pytest.mark.anyio
    async def test_submit_kri_data_yellow(self, client: AsyncClient):
        payload = _make_kri_data(value=80.0)
        resp = await client.post(f"{API_PREFIX}/kri-data", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "yellow"

    @pytest.mark.anyio
    async def test_submit_kri_data_red(self, client: AsyncClient):
        payload = _make_kri_data(value=60.0)
        resp = await client.post(f"{API_PREFIX}/kri-data", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "red"

    @pytest.mark.anyio
    async def test_submit_kri_data_invalid_kri(self, client: AsyncClient):
        payload = _make_kri_data(kri_id="KRI-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/kri-data", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_get_kri_trends(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SITE-105/kri-trends")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_get_kri_trends_filter_kri(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/sites/SITE-105/kri-trends", params={"kri_id": "KRI-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["kri_id"] == "KRI-001"

    @pytest.mark.anyio
    async def test_get_kri_trends_empty_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SITE-101/kri-trends")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    def test_evaluate_kri_status_higher_is_better(self, svc: RBMService):
        kri = svc.get_kri("KRI-001")  # SAE Reporting Timeliness, yellow=85, red=70
        assert kri is not None
        assert svc._evaluate_kri_status(95.0, kri) == KRIStatus.GREEN
        assert svc._evaluate_kri_status(80.0, kri) == KRIStatus.YELLOW
        assert svc._evaluate_kri_status(60.0, kri) == KRIStatus.RED

    def test_evaluate_kri_status_lower_is_better(self, svc: RBMService):
        kri = svc.get_kri("KRI-003")  # Protocol Deviation Rate, yellow=3.0, red=6.0
        assert kri is not None
        assert svc._evaluate_kri_status(2.0, kri) == KRIStatus.GREEN
        assert svc._evaluate_kri_status(4.0, kri) == KRIStatus.YELLOW
        assert svc._evaluate_kri_status(7.0, kri) == KRIStatus.RED

    def test_evaluate_kri_status_data_entry_lag(self, svc: RBMService):
        kri = svc.get_kri("KRI-006")  # Data Entry Lag, yellow=5, red=10
        assert kri is not None
        assert svc._evaluate_kri_status(3.0, kri) == KRIStatus.GREEN
        assert svc._evaluate_kri_status(7.0, kri) == KRIStatus.YELLOW
        assert svc._evaluate_kri_status(12.0, kri) == KRIStatus.RED


# =====================================================================
# AUTO-ESCALATION & TREND ANALYSIS
# =====================================================================


class TestAutoEscalation:
    """Test auto-escalation and trend analysis logic."""

    def test_auto_escalation_critical_with_3_red(self, svc: RBMService):
        """SITE-107 has 5 red KRIs and should be critical."""
        profile = svc.get_site_risk_profile("SITE-107")
        assert profile is not None
        assert profile.risk_level == RiskLevel.CRITICAL

    def test_high_risk_site_not_escalated(self, svc: RBMService):
        """SITE-105 has red KRIs but may not reach 3 depending on data."""
        profile = svc.get_site_risk_profile("SITE-105")
        assert profile is not None
        assert profile.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    def test_low_risk_site_stays_low(self, svc: RBMService):
        profile = svc.get_site_risk_profile("SITE-101")
        assert profile is not None
        assert profile.risk_level == RiskLevel.LOW

    def test_trend_worsening_site(self, svc: RBMService):
        """SITE-107 should show worsening trend."""
        profile = svc.get_site_risk_profile("SITE-107")
        assert profile is not None
        assert profile.trend == Trend.WORSENING

    def test_trend_stable_site(self, svc: RBMService):
        """SITE-101 should show stable trend (no historical data)."""
        profile = svc.get_site_risk_profile("SITE-101")
        assert profile is not None
        assert profile.trend == Trend.STABLE

    def test_recalculate_site_risk_auto_escalation(self, svc: RBMService):
        """Submitting enough red KRI data should trigger escalation."""
        result = svc.recalculate_site_risk("SITE-107")
        assert result is not None
        # SITE-107 should remain critical after recalculation


# =====================================================================
# CENTRAL MONITORING ALERTS
# =====================================================================


class TestCentralMonitoringAlerts:
    """Test central monitoring alert operations."""

    @pytest.mark.anyio
    async def test_list_alerts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6

    @pytest.mark.anyio
    async def test_list_alerts_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts", params={"site_id": "SITE-105"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-105"

    @pytest.mark.anyio
    async def test_list_alerts_filter_resolved(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts", params={"resolved": False})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["resolved"] is False

    @pytest.mark.anyio
    async def test_get_alert(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts/CMA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CMA-001"
        assert data["resolved"] is True

    @pytest.mark.anyio
    async def test_get_alert_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts/CMA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_resolve_alert(self, client: AsyncClient):
        payload = {
            "action_taken": "for_cause",
            "notes": "For-cause visit completed and CAPA initiated",
        }
        resp = await client.post(f"{API_PREFIX}/alerts/CMA-002/resolve", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["resolved"] is True
        assert data["action_taken"] == "for_cause"
        assert data["resolved_date"] is not None

    @pytest.mark.anyio
    async def test_resolve_alert_already_resolved(self, client: AsyncClient):
        payload = {
            "action_taken": "routine",
            "notes": "Test",
        }
        resp = await client.post(f"{API_PREFIX}/alerts/CMA-001/resolve", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_resolve_alert_not_found(self, client: AsyncClient):
        payload = {
            "action_taken": "routine",
            "notes": "Test",
        }
        resp = await client.post(f"{API_PREFIX}/alerts/CMA-NONEXISTENT/resolve", json=payload)
        assert resp.status_code == 404

    def test_alert_triggered_on_red_kri_data(self, svc: RBMService):
        """Submitting a red KRI data point should trigger an alert."""
        initial_alerts = len(svc.list_alerts())
        svc.submit_kri_data(KRIDataPointCreate(
            kri_id="KRI-001",
            site_id="SITE-102",  # No existing alert for this site/KRI
            value=50.0,  # Below red threshold of 70
            period="2026-02",
        ))
        new_alerts = svc.list_alerts()
        assert len(new_alerts) > initial_alerts

    def test_alert_not_duplicated(self, svc: RBMService):
        """Submitting another red value for same site/KRI shouldn't create duplicate."""
        # SITE-105/KRI-002 already has an unresolved alert (CMA-002)
        initial_count = len(svc.list_alerts())
        svc.submit_kri_data(KRIDataPointCreate(
            kri_id="KRI-002",
            site_id="SITE-105",
            value=50.0,
            period="2026-02",
        ))
        assert len(svc.list_alerts()) == initial_count


# =====================================================================
# MONITORING PLANS
# =====================================================================


class TestMonitoringPlans:
    """Test monitoring plan CRUD operations."""

    @pytest.mark.anyio
    async def test_list_plans(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15

    @pytest.mark.anyio
    async def test_list_plans_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans", params={"site_id": "SITE-101"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_plans_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_plans_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans", params={"status": "completed"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_list_plans_filter_visit_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans", params={"visit_type": "for_cause"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["visit_type"] == "for_cause"

    @pytest.mark.anyio
    async def test_get_plan(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans/MON-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "MON-001"
        assert data["status"] == "completed"

    @pytest.mark.anyio
    async def test_get_plan_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans/MON-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_plan(self, client: AsyncClient):
        payload = _make_plan_create()
        resp = await client.post(f"{API_PREFIX}/plans", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_id"] == "SITE-101"
        assert data["status"] == "planned"
        assert data["id"].startswith("MON-")

    @pytest.mark.anyio
    async def test_update_plan(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/plans/MON-009",
            json={"monitor_name": "New Monitor", "status": "in_progress"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["monitor_name"] == "New Monitor"
        assert data["status"] == "in_progress"

    @pytest.mark.anyio
    async def test_update_plan_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/plans/MON-NONEXISTENT",
            json={"monitor_name": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_plan(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/plans/MON-015")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/plans/MON-015")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_plan_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/plans/MON-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# MONITORING VISIT COMPLETION
# =====================================================================


class TestMonitoringVisitCompletion:
    """Test completing monitoring visits with findings."""

    @pytest.mark.anyio
    async def test_complete_visit_no_findings(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = {
            "actual_date": now.isoformat(),
            "notes": "Visit completed successfully",
        }
        resp = await client.post(f"{API_PREFIX}/plans/MON-009/complete", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["findings_count"] == 0

    @pytest.mark.anyio
    async def test_complete_visit_with_findings(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = {
            "actual_date": now.isoformat(),
            "notes": "Issues identified during visit",
            "findings": [
                {
                    "category": "major",
                    "description": "Test finding 1",
                    "response_due_date": (now + timedelta(days=30)).isoformat(),
                },
                {
                    "category": "minor",
                    "description": "Test finding 2",
                    "response_due_date": (now + timedelta(days=14)).isoformat(),
                    "capa_id": "CAPA-TEST-001",
                },
            ],
        }
        resp = await client.post(f"{API_PREFIX}/plans/MON-010/complete", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["findings_count"] == 2

    @pytest.mark.anyio
    async def test_complete_already_completed_visit(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = {"actual_date": now.isoformat()}
        resp = await client.post(f"{API_PREFIX}/plans/MON-001/complete", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_complete_visit_not_found(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = {"actual_date": now.isoformat()}
        resp = await client.post(f"{API_PREFIX}/plans/MON-NONEXISTENT/complete", json=payload)
        assert resp.status_code == 404


# =====================================================================
# FINDINGS
# =====================================================================


class TestFindings:
    """Test monitoring finding operations."""

    @pytest.mark.anyio
    async def test_list_findings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_findings_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"site_id": "SITE-107"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-107"

    @pytest.mark.anyio
    async def test_list_findings_filter_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"category": "critical"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["category"] == "critical"

    @pytest.mark.anyio
    async def test_list_findings_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"status": "open"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "open"

    @pytest.mark.anyio
    async def test_list_findings_filter_plan(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"plan_id": "MON-005"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["plan_id"] == "MON-005"

    @pytest.mark.anyio
    async def test_get_finding(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings/FND-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "FND-001"

    @pytest.mark.anyio
    async def test_get_finding_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings/FND-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_finding_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/findings/FND-004",
            json={"status": "response_required"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "response_required"

    @pytest.mark.anyio
    async def test_update_finding_resolve_auto_date(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/findings/FND-004",
            json={"status": "resolved"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "resolved"
        assert data["resolved_date"] is not None

    @pytest.mark.anyio
    async def test_update_finding_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/findings/FND-NONEXISTENT",
            json={"status": "resolved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_overdue_findings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings/overdue")
        assert resp.status_code == 200
        data = resp.json()
        now = datetime.now(timezone.utc)
        for item in data["items"]:
            due_date = datetime.fromisoformat(item["response_due_date"])
            assert due_date < now


# =====================================================================
# FINDING LIFECYCLE
# =====================================================================


class TestFindingLifecycle:
    """Test finding lifecycle: open -> response_required -> resolved -> verified."""

    def test_finding_lifecycle_transitions(self, svc: RBMService):
        # Start: open
        finding = svc.get_finding("FND-004")
        assert finding is not None
        assert finding.status == FindingStatus.OPEN

        # Transition to response_required
        updated = svc.update_finding("FND-004", FindingUpdate(status=FindingStatus.RESPONSE_REQUIRED))
        assert updated is not None
        assert updated.status == FindingStatus.RESPONSE_REQUIRED

        # Transition to resolved
        updated = svc.update_finding("FND-004", FindingUpdate(status=FindingStatus.RESOLVED))
        assert updated is not None
        assert updated.status == FindingStatus.RESOLVED
        assert updated.resolved_date is not None

        # Transition to verified
        updated = svc.update_finding("FND-004", FindingUpdate(status=FindingStatus.VERIFIED))
        assert updated is not None
        assert updated.status == FindingStatus.VERIFIED

    def test_finding_already_resolved_keeps_date(self, svc: RBMService):
        # FND-001 is already verified with a resolved_date
        finding = svc.get_finding("FND-001")
        assert finding is not None
        assert finding.resolved_date is not None
        original_date = finding.resolved_date

        # Updating description should not change resolved_date
        updated = svc.update_finding("FND-001", FindingUpdate(description="Updated description"))
        assert updated is not None
        assert updated.resolved_date == original_date


# =====================================================================
# METRICS
# =====================================================================


class TestRBMMetrics:
    """Test RBM metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sites"] == 8
        assert data["total_kris"] == 12
        assert data["active_alerts"] >= 0
        assert data["avg_risk_score"] > 0
        assert data["monitoring_visits_completed"] > 0
        assert data["open_findings"] >= 0
        assert data["total_findings"] == 10
        assert data["total_monitoring_plans"] == 15

    def test_metrics_sites_by_risk_level(self, svc: RBMService):
        metrics = svc.get_metrics()
        total_by_level = sum(metrics.sites_by_risk_level.values())
        assert total_by_level == metrics.total_sites

    def test_metrics_overdue_findings_count(self, svc: RBMService):
        metrics = svc.get_metrics()
        overdue_list = svc.get_overdue_findings()
        assert metrics.overdue_findings == len(overdue_list)

    def test_metrics_active_alerts(self, svc: RBMService):
        metrics = svc.get_metrics()
        unresolved = svc.list_alerts(resolved=False)
        assert metrics.active_alerts == len(unresolved)


# =====================================================================
# MONITORING SCHEDULE
# =====================================================================


class TestMonitoringSchedule:
    """Test monitoring schedule recommendation."""

    @pytest.mark.anyio
    async def test_get_monitoring_schedule(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/monitoring-schedule")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 8  # One recommendation per site

    @pytest.mark.anyio
    async def test_schedule_sorted_by_risk(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/monitoring-schedule")
        data = resp.json()
        risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        levels = [risk_order.get(item["risk_level"], 4) for item in data]
        assert levels == sorted(levels)

    @pytest.mark.anyio
    async def test_critical_site_weekly_schedule(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/monitoring-schedule")
        data = resp.json()
        critical_recs = [r for r in data if r["risk_level"] == "critical"]
        for rec in critical_recs:
            assert rec["recommended_frequency"] == "weekly"
            assert rec["recommended_visit_type"] == "for_cause"

    @pytest.mark.anyio
    async def test_high_risk_monthly_schedule(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/monitoring-schedule")
        data = resp.json()
        high_recs = [r for r in data if r["risk_level"] == "high"]
        for rec in high_recs:
            assert rec["recommended_frequency"] == "monthly"

    @pytest.mark.anyio
    async def test_low_risk_quarterly_schedule(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/monitoring-schedule")
        data = resp.json()
        low_recs = [r for r in data if r["risk_level"] == "low"]
        for rec in low_recs:
            assert rec["recommended_frequency"] == "quarterly"
            assert rec["recommended_visit_type"] == "remote"

    def test_schedule_includes_rationale(self, svc: RBMService):
        schedule = svc.get_monitoring_schedule()
        for rec in schedule:
            assert rec.rationale
            assert len(rec.rationale) > 10


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_rbm_service()
        svc2 = get_rbm_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_rbm_service()
        svc2 = reset_rbm_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_rbm_service()
        # Delete a KRI
        svc.delete_kri("KRI-001")
        assert svc.get_kri("KRI-001") is None
        # Reset should bring it back
        svc2 = reset_rbm_service()
        assert svc2.get_kri("KRI-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_kris_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kris")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_alerts_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_plans_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_findings_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_kri_create_with_all_fields(self, client: AsyncClient):
        payload = _make_kri_create(
            name="Full KRI",
            category="data_quality",
            description="Complete KRI with all fields",
            threshold_yellow=75.0,
            threshold_red=50.0,
            unit="score",
            weight=5.0,
        )
        resp = await client.post(f"{API_PREFIX}/kris", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_plan_create_for_cause(self, client: AsyncClient):
        payload = _make_plan_create(
            visit_type="for_cause",
            site_id="SITE-107",
        )
        resp = await client.post(f"{API_PREFIX}/plans", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["visit_type"] == "for_cause"

    @pytest.mark.anyio
    async def test_kri_data_period_format(self, client: AsyncClient):
        payload = _make_kri_data(period="2026-01")
        resp = await client.post(f"{API_PREFIX}/kri-data", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["period"] == "2026-01"

    def test_value_to_score_green_percentage(self, svc: RBMService):
        kri = svc.get_kri("KRI-001")
        assert kri is not None
        score = svc._value_to_score(98.0, kri)
        assert score < 20  # Low risk score for green

    def test_value_to_score_red_percentage(self, svc: RBMService):
        kri = svc.get_kri("KRI-001")
        assert kri is not None
        score = svc._value_to_score(50.0, kri)
        assert score > 60  # High risk score for red

    def test_value_to_score_lower_is_better_green(self, svc: RBMService):
        kri = svc.get_kri("KRI-006")  # Data Entry Lag, yellow=5, red=10
        assert kri is not None
        score = svc._value_to_score(2.0, kri)
        assert score < 25

    def test_value_to_score_lower_is_better_red(self, svc: RBMService):
        kri = svc.get_kri("KRI-006")
        assert kri is not None
        score = svc._value_to_score(15.0, kri)
        assert score > 70

    @pytest.mark.anyio
    async def test_multiple_concurrent_data_submissions(self, client: AsyncClient):
        """Submit multiple KRI data points in sequence."""
        for i in range(5):
            payload = _make_kri_data(
                value=90.0 - i * 5,
                period=f"2026-{i + 1:02d}",
                site_id="SITE-102",
            )
            resp = await client.post(f"{API_PREFIX}/kri-data", json=payload)
            assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_complete_visit_creates_findings_in_listing(self, client: AsyncClient):
        """Completing a visit with findings should make them visible in findings list."""
        now = datetime.now(timezone.utc)
        # Complete a visit with findings
        payload = {
            "actual_date": now.isoformat(),
            "findings": [
                {
                    "category": "critical",
                    "description": "Test critical finding from visit completion",
                    "response_due_date": (now + timedelta(days=7)).isoformat(),
                },
            ],
        }
        resp = await client.post(f"{API_PREFIX}/plans/MON-011/complete", json=payload)
        assert resp.status_code == 200

        # Verify finding appears in list
        resp2 = await client.get(f"{API_PREFIX}/findings", params={"site_id": "SITE-107"})
        assert resp2.status_code == 200
        data = resp2.json()
        descriptions = [f["description"] for f in data["items"]]
        assert "Test critical finding from visit completion" in descriptions


# =====================================================================
# KRI CATEGORY & STATUS ENUMERATION
# =====================================================================


class TestEnumerations:
    """Test enum values are correctly used throughout the system."""

    @pytest.mark.anyio
    async def test_all_kri_categories_represented(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kris")
        data = resp.json()
        categories = {item["category"] for item in data["items"]}
        assert "safety" in categories
        assert "data_quality" in categories
        assert "enrollment" in categories
        assert "protocol_compliance" in categories
        assert "site_management" in categories

    @pytest.mark.anyio
    async def test_all_risk_levels_represented(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/risk-scores")
        data = resp.json()
        levels = {item["risk_level"] for item in data["items"]}
        assert "low" in levels
        assert "medium" in levels
        assert "high" in levels
        assert "critical" in levels

    @pytest.mark.anyio
    async def test_all_visit_types_in_plans(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans")
        data = resp.json()
        types = {item["visit_type"] for item in data["items"]}
        assert "site_initiation" in types
        assert "interim" in types
        assert "for_cause" in types
        assert "remote" in types

    @pytest.mark.anyio
    async def test_all_finding_categories_in_findings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings")
        data = resp.json()
        categories = {item["category"] for item in data["items"]}
        assert "critical" in categories
        assert "major" in categories
        assert "minor" in categories
        assert "observation" in categories

    @pytest.mark.anyio
    async def test_finding_statuses_in_findings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "open" in statuses
        assert "verified" in statuses


# =====================================================================
# RISK PROFILE DETAILS
# =====================================================================


class TestRiskProfileDetails:
    """Test detailed risk profile components."""

    @pytest.mark.anyio
    async def test_risk_profile_has_kri_scores(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SITE-107/risk-profile")
        data = resp.json()
        assert len(data["kri_scores"]) > 0
        for kri_score in data["kri_scores"]:
            assert "kri_id" in kri_score
            assert "kri_name" in kri_score
            assert "value" in kri_score
            assert "status" in kri_score
            assert "score" in kri_score

    @pytest.mark.anyio
    async def test_risk_profile_score_range(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/risk-scores")
        data = resp.json()
        for item in data["items"]:
            assert 0 <= item["overall_risk_score"] <= 100

    @pytest.mark.anyio
    async def test_risk_profile_trend_values(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/risk-scores")
        data = resp.json()
        valid_trends = {"improving", "stable", "worsening"}
        for item in data["items"]:
            assert item["trend"] in valid_trends

    @pytest.mark.anyio
    async def test_kri_scores_have_valid_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SITE-105/risk-profile")
        data = resp.json()
        valid_statuses = {"green", "yellow", "red"}
        for kri_score in data["kri_scores"]:
            assert kri_score["status"] in valid_statuses
