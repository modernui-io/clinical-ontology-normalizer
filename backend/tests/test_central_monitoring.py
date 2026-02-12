"""Tests for Central Monitoring Management (CTR-MON).

Covers:
- Seed data verification (monitoring visits, KRI signals, site risk indicators,
  monitoring actions, central reviews)
- Full CRUD for all 5 entity types (create, read, update, delete, list)
- List filtering by trial_id
- 404 error handling for missing resources
- 422 validation errors for malformed payloads
- Metrics endpoint
- Demo data seeding verification
- Singleton service pattern (get, reset, reseed)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.central_monitoring_service import (
    CentralMonitoringService,
    get_central_monitoring_service,
    reset_central_monitoring_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/central-monitoring"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_central_monitoring_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> CentralMonitoringService:
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


def _make_visit_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "monitoring_type": "remote",
        "monitor": "Test Monitor",
        "subjects_reviewed": 10,
    }
    defaults.update(overrides)
    return defaults


def _make_signal_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "signal_category": "data_quality",
        "kri_name": "Test KRI Signal",
        "kri_value": 72.0,
        "threshold_value": 80.0,
        "breach_direction": "below",
    }
    defaults.update(overrides)
    return defaults


def _make_indicator_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "assessed_by": "Test Assessor",
        "enrollment_score": 40.0,
        "data_quality_score": 35.0,
        "safety_score": 45.0,
        "compliance_score": 50.0,
    }
    defaults.update(overrides)
    return defaults


def _make_action_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "action_description": "Test action item",
        "category": "data_quality",
        "assigned_to": "Test Assignee",
        "due_date": (now + timedelta(days=14)).isoformat(),
        "created_by": "Test Creator",
    }
    defaults.update(overrides)
    return defaults


def _make_review_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "review_period_start": (now - timedelta(days=30)).isoformat(),
        "review_period_end": now.isoformat(),
        "reviewer": "Test Reviewer",
        "sites_reviewed": 3,
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_monitoring_visits_count(self, svc: CentralMonitoringService):
        visits = svc.list_monitoring_visits()
        assert len(visits) == 12

    def test_seed_kri_signals_count(self, svc: CentralMonitoringService):
        signals = svc.list_kri_signals()
        assert len(signals) == 12

    def test_seed_site_risk_indicators_count(self, svc: CentralMonitoringService):
        indicators = svc.list_site_risk_indicators()
        assert len(indicators) == 10

    def test_seed_monitoring_actions_count(self, svc: CentralMonitoringService):
        actions = svc.list_monitoring_actions()
        assert len(actions) == 12

    def test_seed_central_reviews_count(self, svc: CentralMonitoringService):
        reviews = svc.list_central_reviews()
        assert len(reviews) == 10

    def test_seed_visits_have_multiple_types(self, svc: CentralMonitoringService):
        visits = svc.list_monitoring_visits()
        types = {v.monitoring_type.value for v in visits}
        assert len(types) >= 4

    def test_seed_signals_have_multiple_categories(self, svc: CentralMonitoringService):
        signals = svc.list_kri_signals()
        categories = {s.signal_category.value for s in signals}
        assert len(categories) >= 5

    def test_seed_signals_have_multiple_risk_levels(self, svc: CentralMonitoringService):
        signals = svc.list_kri_signals()
        levels = {s.risk_level.value for s in signals}
        assert "low" in levels
        assert "medium" in levels
        assert "high" in levels
        assert "critical" in levels

    def test_seed_indicators_have_multiple_risk_levels(self, svc: CentralMonitoringService):
        indicators = svc.list_site_risk_indicators()
        levels = {ri.risk_level.value for ri in indicators}
        assert "low" in levels
        assert "high" in levels
        assert "critical" in levels

    def test_seed_actions_have_multiple_statuses(self, svc: CentralMonitoringService):
        actions = svc.list_monitoring_actions()
        statuses = {a.status.value for a in actions}
        assert len(statuses) >= 4

    def test_seed_reviews_span_all_trials(self, svc: CentralMonitoringService):
        reviews = svc.list_central_reviews()
        trial_ids = {r.trial_id for r in reviews}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_visits_span_all_trials(self, svc: CentralMonitoringService):
        visits = svc.list_monitoring_visits()
        trial_ids = {v.trial_id for v in visits}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids


# =====================================================================
# MONITORING VISITS CRUD
# =====================================================================


class TestMonitoringVisitsCrud:
    """Test monitoring visit CRUD operations."""

    @pytest.mark.anyio
    async def test_list_visits(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/monitoring-visits")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_visits_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/monitoring-visits", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_visit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/monitoring-visits/CMV-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CMV-001"
        assert data["monitor"] == "Sarah Mitchell"

    @pytest.mark.anyio
    async def test_get_visit_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/monitoring-visits/CMV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_visit(self, client: AsyncClient):
        payload = _make_visit_create()
        resp = await client.post(f"{API_PREFIX}/monitoring-visits", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["monitor"] == "Test Monitor"
        assert data["id"].startswith("CMV-")

    @pytest.mark.anyio
    async def test_create_visit_validation_error(self, client: AsyncClient):
        # Missing required fields
        resp = await client.post(
            f"{API_PREFIX}/monitoring-visits", json={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_update_visit(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/monitoring-visits/CMV-001",
            json={"notes": "Updated notes", "follow_up_required": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated notes"
        assert data["follow_up_required"] is True

    @pytest.mark.anyio
    async def test_update_visit_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/monitoring-visits/CMV-NONEXISTENT",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_visit(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/monitoring-visits/CMV-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/monitoring-visits/CMV-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_visit_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/monitoring-visits/CMV-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# KRI SIGNALS CRUD
# =====================================================================


class TestKRISignalsCrud:
    """Test KRI signal CRUD operations."""

    @pytest.mark.anyio
    async def test_list_signals(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kri-signals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_signals_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/kri-signals", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_get_signal(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kri-signals/KRS-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "KRS-001"
        assert data["kri_name"] == "Query Resolution Rate"

    @pytest.mark.anyio
    async def test_get_signal_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kri-signals/KRS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_signal(self, client: AsyncClient):
        payload = _make_signal_create()
        resp = await client.post(f"{API_PREFIX}/kri-signals", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["kri_name"] == "Test KRI Signal"
        assert data["id"].startswith("KRS-")
        assert data["acknowledged"] is False

    @pytest.mark.anyio
    async def test_create_signal_validation_error(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/kri-signals", json={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_update_signal(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/kri-signals/KRS-005",
            json={"acknowledged": True, "acknowledged_by": "Test Monitor"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["acknowledged"] is True
        assert data["acknowledged_by"] == "Test Monitor"

    @pytest.mark.anyio
    async def test_update_signal_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/kri-signals/KRS-NONEXISTENT",
            json={"acknowledged": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_signal(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/kri-signals/KRS-011")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/kri-signals/KRS-011")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_signal_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/kri-signals/KRS-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# SITE RISK INDICATORS CRUD
# =====================================================================


class TestSiteRiskIndicatorsCrud:
    """Test site risk indicator CRUD operations."""

    @pytest.mark.anyio
    async def test_list_indicators(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-risk-indicators")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_indicators_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-risk-indicators", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_indicators_sorted_by_risk_score(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-risk-indicators")
        data = resp.json()
        scores = [item["overall_risk_score"] for item in data["items"]]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.anyio
    async def test_get_indicator(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-risk-indicators/SRI-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SRI-001"
        assert data["risk_level"] == "low"

    @pytest.mark.anyio
    async def test_get_indicator_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-risk-indicators/SRI-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_indicator(self, client: AsyncClient):
        payload = _make_indicator_create()
        resp = await client.post(f"{API_PREFIX}/site-risk-indicators", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["assessed_by"] == "Test Assessor"
        assert data["id"].startswith("SRI-")
        # Overall score should be computed as average of component scores
        expected_overall = (40.0 + 35.0 + 45.0 + 50.0) / 4
        assert data["overall_risk_score"] == expected_overall

    @pytest.mark.anyio
    async def test_create_indicator_risk_level_computed(self, client: AsyncClient):
        # Low risk: all low component scores
        payload = _make_indicator_create(
            enrollment_score=10.0,
            data_quality_score=15.0,
            safety_score=20.0,
            compliance_score=10.0,
        )
        resp = await client.post(f"{API_PREFIX}/site-risk-indicators", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["risk_level"] == "low"

    @pytest.mark.anyio
    async def test_create_indicator_high_risk_computed(self, client: AsyncClient):
        # High risk: high component scores
        payload = _make_indicator_create(
            enrollment_score=70.0,
            data_quality_score=65.0,
            safety_score=60.0,
            compliance_score=55.0,
        )
        resp = await client.post(f"{API_PREFIX}/site-risk-indicators", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["risk_level"] == "high"

    @pytest.mark.anyio
    async def test_create_indicator_validation_error(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/site-risk-indicators", json={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_indicator_score_out_of_range(self, client: AsyncClient):
        payload = _make_indicator_create(enrollment_score=150.0)
        resp = await client.post(f"{API_PREFIX}/site-risk-indicators", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_update_indicator(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/site-risk-indicators/SRI-002",
            json={"triggered_visit_recommended": True, "operational_score": 55.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["triggered_visit_recommended"] is True
        assert data["operational_score"] == 55.0

    @pytest.mark.anyio
    async def test_update_indicator_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/site-risk-indicators/SRI-NONEXISTENT",
            json={"operational_score": 50.0},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_indicator(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/site-risk-indicators/SRI-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/site-risk-indicators/SRI-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_indicator_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/site-risk-indicators/SRI-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# MONITORING ACTIONS CRUD
# =====================================================================


class TestMonitoringActionsCrud:
    """Test monitoring action CRUD operations."""

    @pytest.mark.anyio
    async def test_list_actions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/monitoring-actions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_actions_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/monitoring-actions", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_action(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/monitoring-actions/CMA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CMA-001"
        assert data["status"] == "in_progress"

    @pytest.mark.anyio
    async def test_get_action_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/monitoring-actions/CMA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_action(self, client: AsyncClient):
        payload = _make_action_create()
        resp = await client.post(f"{API_PREFIX}/monitoring-actions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["action_description"] == "Test action item"
        assert data["id"].startswith("CMA-")
        assert data["status"] == "open"

    @pytest.mark.anyio
    async def test_create_action_validation_error(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/monitoring-actions", json={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_update_action_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/monitoring-actions/CMA-004",
            json={"status": "in_progress", "response_text": "Working on it."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["response_text"] == "Working on it."

    @pytest.mark.anyio
    async def test_update_action_resolve_auto_date(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/monitoring-actions/CMA-004",
            json={"status": "resolved"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "resolved"
        assert data["completed_date"] is not None

    @pytest.mark.anyio
    async def test_update_action_escalate_auto_date(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/monitoring-actions/CMA-004",
            json={"status": "escalated", "escalated_to": "Dr. Robert Chen"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "escalated"
        assert data["escalation_date"] is not None

    @pytest.mark.anyio
    async def test_update_action_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/monitoring-actions/CMA-NONEXISTENT",
            json={"status": "resolved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_action(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/monitoring-actions/CMA-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/monitoring-actions/CMA-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_action_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/monitoring-actions/CMA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# CENTRAL REVIEWS CRUD
# =====================================================================


class TestCentralReviewsCrud:
    """Test central review CRUD operations."""

    @pytest.mark.anyio
    async def test_list_reviews(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/central-reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_reviews_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/central-reviews", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_review(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/central-reviews/CRV-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CRV-001"
        assert data["reviewer"] == "Sarah Mitchell"

    @pytest.mark.anyio
    async def test_get_review_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/central-reviews/CRV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_review(self, client: AsyncClient):
        payload = _make_review_create()
        resp = await client.post(f"{API_PREFIX}/central-reviews", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["reviewer"] == "Test Reviewer"
        assert data["id"].startswith("CRV-")
        assert data["sites_reviewed"] == 3

    @pytest.mark.anyio
    async def test_create_review_validation_error(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/central-reviews", json={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_update_review(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/central-reviews/CRV-010",
            json={
                "summary": "Updated review summary",
                "escalations": 3,
                "triggered_visits_recommended": 2,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"] == "Updated review summary"
        assert data["escalations"] == 3
        assert data["triggered_visits_recommended"] == 2

    @pytest.mark.anyio
    async def test_update_review_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/central-reviews/CRV-NONEXISTENT",
            json={"summary": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_review(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/central-reviews/CRV-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/central-reviews/CRV-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_review_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/central-reviews/CRV-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestCentralMonitoringMetrics:
    """Test central monitoring metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_visits"] == 12
        assert data["total_signals"] == 12
        assert data["total_actions"] == 12
        assert data["total_reviews"] == 10
        assert data["unresolved_signals"] >= 0
        assert data["overdue_actions"] >= 0
        assert data["avg_action_resolution_days"] >= 0
        assert data["sites_at_high_risk"] >= 0

    @pytest.mark.anyio
    async def test_metrics_visits_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_type = sum(data["visits_by_type"].values())
        assert total_by_type == data["total_visits"]

    @pytest.mark.anyio
    async def test_metrics_visits_by_outcome(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_outcome = sum(data["visits_by_outcome"].values())
        assert total_by_outcome == data["total_visits"]

    @pytest.mark.anyio
    async def test_metrics_signals_by_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_cat = sum(data["signals_by_category"].values())
        assert total_by_cat == data["total_signals"]

    @pytest.mark.anyio
    async def test_metrics_signals_by_risk(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_risk = sum(data["signals_by_risk"].values())
        assert total_by_risk == data["total_signals"]

    @pytest.mark.anyio
    async def test_metrics_actions_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_status = sum(data["actions_by_status"].values())
        assert total_by_status == data["total_actions"]

    def test_metrics_unresolved_signals_count(self, svc: CentralMonitoringService):
        metrics = svc.get_metrics()
        signals = svc.list_kri_signals()
        unresolved = sum(1 for s in signals if s.resolution_date is None)
        assert metrics.unresolved_signals == unresolved

    def test_metrics_sites_at_high_risk(self, svc: CentralMonitoringService):
        metrics = svc.get_metrics()
        indicators = svc.list_site_risk_indicators()
        high_risk = sum(
            1 for ri in indicators if ri.risk_level.value in ("high", "critical")
        )
        assert metrics.sites_at_high_risk == high_risk


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_central_monitoring_service()
        svc2 = get_central_monitoring_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_central_monitoring_service()
        svc2 = reset_central_monitoring_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_central_monitoring_service()
        # Delete a visit
        svc.delete_monitoring_visit("CMV-001")
        assert svc.get_monitoring_visit("CMV-001") is None
        # Reset should bring it back
        svc2 = reset_central_monitoring_service()
        assert svc2.get_monitoring_visit("CMV-001") is not None


# =====================================================================
# FILTERING & EDGE CASES
# =====================================================================


class TestFilteringAndEdgeCases:
    """Test filtering and edge case scenarios."""

    @pytest.mark.anyio
    async def test_filter_visits_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/monitoring-visits",
            params={"trial_id": "nonexistent-trial-id"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_filter_signals_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/kri-signals",
            params={"trial_id": "nonexistent-trial-id"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_filter_indicators_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-risk-indicators",
            params={"trial_id": "nonexistent-trial-id"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_filter_actions_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/monitoring-actions",
            params={"trial_id": "nonexistent-trial-id"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_filter_reviews_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/central-reviews",
            params={"trial_id": "nonexistent-trial-id"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_create_and_retrieve_visit(self, client: AsyncClient):
        """Create a visit and verify it shows up in list."""
        payload = _make_visit_create(site_id="SITE-NEW")
        resp = await client.post(f"{API_PREFIX}/monitoring-visits", json=payload)
        assert resp.status_code == 201
        visit_id = resp.json()["id"]

        resp2 = await client.get(f"{API_PREFIX}/monitoring-visits/{visit_id}")
        assert resp2.status_code == 200
        assert resp2.json()["site_id"] == "SITE-NEW"

    @pytest.mark.anyio
    async def test_create_and_delete_signal(self, client: AsyncClient):
        """Create a signal and then delete it."""
        payload = _make_signal_create()
        resp = await client.post(f"{API_PREFIX}/kri-signals", json=payload)
        assert resp.status_code == 201
        signal_id = resp.json()["id"]

        resp2 = await client.delete(f"{API_PREFIX}/kri-signals/{signal_id}")
        assert resp2.status_code == 204

        resp3 = await client.get(f"{API_PREFIX}/kri-signals/{signal_id}")
        assert resp3.status_code == 404

    @pytest.mark.anyio
    async def test_create_action_with_optional_fields(self, client: AsyncClient):
        payload = _make_action_create(
            signal_id="KRS-001",
            visit_id="CMV-001",
        )
        resp = await client.post(f"{API_PREFIX}/monitoring-actions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["signal_id"] == "KRS-001"
        assert data["visit_id"] == "CMV-001"

    @pytest.mark.anyio
    async def test_update_review_next_review_date(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        next_date = (now + timedelta(days=30)).isoformat()
        resp = await client.put(
            f"{API_PREFIX}/central-reviews/CRV-001",
            json={"next_review_date": next_date},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["next_review_date"] is not None

    @pytest.mark.anyio
    async def test_visits_sorted_by_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/monitoring-visits")
        data = resp.json()
        dates = [item["visit_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_reviews_sorted_by_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/central-reviews")
        data = resp.json()
        dates = [item["review_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_multiple_creates_increase_total(self, client: AsyncClient):
        """Creating multiple entities increases the list total."""
        resp = await client.get(f"{API_PREFIX}/kri-signals")
        initial = resp.json()["total"]

        for i in range(3):
            payload = _make_signal_create(kri_name=f"Test Signal {i}")
            await client.post(f"{API_PREFIX}/kri-signals", json=payload)

        resp2 = await client.get(f"{API_PREFIX}/kri-signals")
        assert resp2.json()["total"] == initial + 3


# =====================================================================
# VISIT REVIEW OUTCOMES
# =====================================================================


class TestVisitReviewOutcomes:
    """Test monitoring visit review outcomes."""

    @pytest.mark.anyio
    async def test_visit_outcomes_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/monitoring-visits")
        data = resp.json()
        outcomes = {item["review_outcome"] for item in data["items"]}
        assert "no_action" in outcomes
        assert "escalated" in outcomes

    @pytest.mark.anyio
    async def test_update_visit_outcome(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/monitoring-visits/CMV-009",
            json={"review_outcome": "action_required", "report_finalized": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["review_outcome"] == "action_required"
        assert data["report_finalized"] is True

    @pytest.mark.anyio
    async def test_critical_visits_have_findings(self, client: AsyncClient):
        """Visits with escalated outcomes should have findings."""
        resp = await client.get(f"{API_PREFIX}/monitoring-visits")
        data = resp.json()
        escalated = [v for v in data["items"] if v["review_outcome"] == "escalated"]
        for v in escalated:
            assert v["findings_count"] > 0


# =====================================================================
# SIGNAL RESOLUTION
# =====================================================================


class TestSignalResolution:
    """Test KRI signal resolution workflow."""

    @pytest.mark.anyio
    async def test_resolved_signal_has_date(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kri-signals/KRS-001")
        data = resp.json()
        assert data["resolution_date"] is not None
        assert data["resolution_notes"] is not None

    @pytest.mark.anyio
    async def test_unresolved_signal_no_date(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kri-signals/KRS-005")
        data = resp.json()
        assert data["resolution_date"] is None
        assert data["acknowledged"] is False

    @pytest.mark.anyio
    async def test_update_signal_resolve(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/kri-signals/KRS-005",
            json={
                "acknowledged": True,
                "acknowledged_by": "Test User",
                "resolution_notes": "Issue resolved after retraining.",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["acknowledged"] is True
        assert data["resolution_notes"] == "Issue resolved after retraining."
        assert data["resolution_date"] is not None
