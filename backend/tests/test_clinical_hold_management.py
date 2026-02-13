"""Tests for Clinical Hold Management (CHM-MGT).

Covers:
- Seed data verification (hold events, impact assessments, corrective action plans, restart authorizations)
- Full CRUD for each entity (list, get, create, update, delete, not-found)
- Trial ID filtering for list endpoints
- Clinical hold metrics computation
- Metrics filtered by trial ID
- Edge cases and error handling
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.clinical_hold_management_service import (
    ClinicalHoldManagementService,
    get_clinical_hold_management_service,
    reset_clinical_hold_management_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/clinical-hold-management"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_clinical_hold_management_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ClinicalHoldManagementService:
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


def _make_hold_event_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "hold_type": "full_clinical_hold",
        "hold_reason": "Test hold reason for safety signal",
        "issuing_authority": "FDA CDER",
        "hold_date": now.isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_impact_assessment_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "hold_event_id": "HLD-00000001",
        "assessment_area": "Patient Safety",
        "impact_description": "Test impact description",
        "assessed_by": "Dr. Test Assessor",
        "assessment_date": now.isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_corrective_action_plan_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "hold_event_id": "HLD-00000001",
        "plan_title": "Test Corrective Action Plan",
        "plan_description": "Test plan description",
        "corrective_actions": "1. Action one; 2. Action two",
        "responsible_party": "Dr. Test Responsible",
    }
    defaults.update(overrides)
    return defaults


def _make_restart_authorization_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "hold_event_id": "HLD-00000001",
        "authorization_authority": "FDA CDER",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_hold_events_count(self, svc: ClinicalHoldManagementService):
        events = svc.list_hold_events()
        assert len(events) == 12

    def test_seed_hold_events_per_trial(self, svc: ClinicalHoldManagementService):
        eylea = svc.list_hold_events(trial_id=EYLEA_TRIAL)
        dupixent = svc.list_hold_events(trial_id=DUPIXENT_TRIAL)
        libtayo = svc.list_hold_events(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) == 4
        assert len(dupixent) == 4
        assert len(libtayo) == 4

    def test_seed_impact_assessments_count(self, svc: ClinicalHoldManagementService):
        assessments = svc.list_impact_assessments()
        assert len(assessments) == 12

    def test_seed_corrective_action_plans_count(self, svc: ClinicalHoldManagementService):
        plans = svc.list_corrective_action_plans()
        assert len(plans) == 12

    def test_seed_restart_authorizations_count(self, svc: ClinicalHoldManagementService):
        auths = svc.list_restart_authorizations()
        assert len(auths) == 12

    def test_seed_hold_types_diverse(self, svc: ClinicalHoldManagementService):
        events = svc.list_hold_events()
        types = {e.hold_type.value for e in events}
        assert len(types) >= 4

    def test_seed_hold_statuses_diverse(self, svc: ClinicalHoldManagementService):
        events = svc.list_hold_events()
        statuses = {e.hold_status.value for e in events}
        assert len(statuses) >= 4

    def test_seed_impact_severities_diverse(self, svc: ClinicalHoldManagementService):
        assessments = svc.list_impact_assessments()
        severities = {a.impact_severity.value for a in assessments}
        assert len(severities) >= 4


# =====================================================================
# HOLD EVENT CRUD
# =====================================================================


class TestHoldEventCrud:
    """Test hold event CRUD operations."""

    @pytest.mark.anyio
    async def test_list_hold_events(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/hold-events")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_hold_events_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/hold-events", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_hold_event(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/hold-events/HLD-00000001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "HLD-00000001"
        assert data["hold_type"] == "full_clinical_hold"
        assert data["hold_status"] == "lifted"

    @pytest.mark.anyio
    async def test_get_hold_event_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/hold-events/HLD-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_hold_event(self, client: AsyncClient):
        payload = _make_hold_event_create()
        resp = await client.post(f"{API_PREFIX}/hold-events", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("HLD-")
        assert data["hold_type"] == "full_clinical_hold"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_update_hold_event(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/hold-events/HLD-00000002",
            json={"hold_status": "lifted", "notes": "Hold resolved after review"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["hold_status"] == "lifted"
        assert data["notes"] == "Hold resolved after review"

    @pytest.mark.anyio
    async def test_update_hold_event_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/hold-events/HLD-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_hold_event(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/hold-events/HLD-00000001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/hold-events/HLD-00000001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_hold_event_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/hold-events/HLD-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# IMPACT ASSESSMENT CRUD
# =====================================================================


class TestImpactAssessmentCrud:
    """Test impact assessment CRUD operations."""

    @pytest.mark.anyio
    async def test_list_impact_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/impact-assessments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_impact_assessments_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/impact-assessments", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_get_impact_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/impact-assessments/IMA-00000001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "IMA-00000001"
        assert data["impact_severity"] == "critical"

    @pytest.mark.anyio
    async def test_get_impact_assessment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/impact-assessments/IMA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_impact_assessment(self, client: AsyncClient):
        payload = _make_impact_assessment_create()
        resp = await client.post(f"{API_PREFIX}/impact-assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("IMA-")
        assert data["assessment_area"] == "Patient Safety"

    @pytest.mark.anyio
    async def test_update_impact_assessment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/impact-assessments/IMA-00000004",
            json={"impact_severity": "moderate", "notes": "Severity upgraded after further analysis"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["impact_severity"] == "moderate"
        assert data["notes"] == "Severity upgraded after further analysis"

    @pytest.mark.anyio
    async def test_update_impact_assessment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/impact-assessments/IMA-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_impact_assessment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/impact-assessments/IMA-00000001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/impact-assessments/IMA-00000001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_impact_assessment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/impact-assessments/IMA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# CORRECTIVE ACTION PLAN CRUD
# =====================================================================


class TestCorrectiveActionPlanCrud:
    """Test corrective action plan CRUD operations."""

    @pytest.mark.anyio
    async def test_list_corrective_action_plans(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/corrective-action-plans")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_corrective_action_plans_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/corrective-action-plans", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_corrective_action_plan(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/corrective-action-plans/CAP-00000001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CAP-00000001"
        assert data["action_plan_status"] == "completed"

    @pytest.mark.anyio
    async def test_get_corrective_action_plan_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/corrective-action-plans/CAP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_corrective_action_plan(self, client: AsyncClient):
        payload = _make_corrective_action_plan_create()
        resp = await client.post(f"{API_PREFIX}/corrective-action-plans", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("CAP-")
        assert data["plan_title"] == "Test Corrective Action Plan"

    @pytest.mark.anyio
    async def test_update_corrective_action_plan(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/corrective-action-plans/CAP-00000004",
            json={"action_plan_status": "submitted", "notes": "Plan submitted for review"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["action_plan_status"] == "submitted"
        assert data["notes"] == "Plan submitted for review"

    @pytest.mark.anyio
    async def test_update_corrective_action_plan_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/corrective-action-plans/CAP-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_corrective_action_plan(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/corrective-action-plans/CAP-00000001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/corrective-action-plans/CAP-00000001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_corrective_action_plan_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/corrective-action-plans/CAP-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# RESTART AUTHORIZATION CRUD
# =====================================================================


class TestRestartAuthorizationCrud:
    """Test restart authorization CRUD operations."""

    @pytest.mark.anyio
    async def test_list_restart_authorizations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/restart-authorizations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_restart_authorizations_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/restart-authorizations", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_restart_authorization(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/restart-authorizations/RSA-00000001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RSA-00000001"
        assert data["restart_decision"] == "approved"

    @pytest.mark.anyio
    async def test_get_restart_authorization_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/restart-authorizations/RSA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_restart_authorization(self, client: AsyncClient):
        payload = _make_restart_authorization_create()
        resp = await client.post(f"{API_PREFIX}/restart-authorizations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("RSA-")
        assert data["authorization_authority"] == "FDA CDER"
        assert data["restart_decision"] == "pending"

    @pytest.mark.anyio
    async def test_update_restart_authorization(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/restart-authorizations/RSA-00000002",
            json={
                "restart_decision": "conditional_approval",
                "conditions": "Enhanced monitoring required",
                "notes": "Approved with conditions",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["restart_decision"] == "conditional_approval"
        assert data["conditions"] == "Enhanced monitoring required"

    @pytest.mark.anyio
    async def test_update_restart_authorization_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/restart-authorizations/RSA-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_restart_authorization(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/restart-authorizations/RSA-00000001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/restart-authorizations/RSA-00000001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_restart_authorization_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/restart-authorizations/RSA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestClinicalHoldMetrics:
    """Test clinical hold metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_hold_events"] == 12
        assert data["total_impact_assessments"] == 12
        assert data["total_action_plans"] == 12
        assert data["total_restart_authorizations"] == 12
        assert data["avg_hold_duration_days"] > 0

    @pytest.mark.anyio
    async def test_get_metrics_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_hold_events"] == 4
        assert data["total_impact_assessments"] == 4
        assert data["total_action_plans"] == 4
        assert data["total_restart_authorizations"] == 4

    def test_metrics_holds_by_type(self, svc: ClinicalHoldManagementService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.holds_by_type.values())
        assert total_by_type == metrics.total_hold_events

    def test_metrics_holds_by_status(self, svc: ClinicalHoldManagementService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.holds_by_status.values())
        assert total_by_status == metrics.total_hold_events

    def test_metrics_assessments_by_severity(self, svc: ClinicalHoldManagementService):
        metrics = svc.get_metrics()
        total_by_severity = sum(metrics.assessments_by_severity.values())
        assert total_by_severity == metrics.total_impact_assessments

    def test_metrics_plans_by_status(self, svc: ClinicalHoldManagementService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.plans_by_status.values())
        assert total_by_status == metrics.total_action_plans

    def test_metrics_restarts_by_decision(self, svc: ClinicalHoldManagementService):
        metrics = svc.get_metrics()
        total_by_decision = sum(metrics.restarts_by_decision.values())
        assert total_by_decision == metrics.total_restart_authorizations

    def test_metrics_avg_hold_duration(self, svc: ClinicalHoldManagementService):
        metrics = svc.get_metrics()
        # Only lifted holds have duration, so avg should be > 0
        assert metrics.avg_hold_duration_days > 0


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_clinical_hold_management_service()
        svc2 = get_clinical_hold_management_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_clinical_hold_management_service()
        svc2 = reset_clinical_hold_management_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_clinical_hold_management_service()
        svc.delete_hold_event("HLD-00000001")
        assert svc.get_hold_event("HLD-00000001") is None
        svc2 = reset_clinical_hold_management_service()
        assert svc2.get_hold_event("HLD-00000001") is not None


# =====================================================================
# EDGE CASES
# =====================================================================


class TestEdgeCases:
    """Test edge cases and additional scenarios."""

    @pytest.mark.anyio
    async def test_list_hold_events_no_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/hold-events")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_impact_assessments_no_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/impact-assessments")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_corrective_action_plans_no_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/corrective-action-plans")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_restart_authorizations_no_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/restart-authorizations")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_hold_event_with_partial_hold(self, client: AsyncClient):
        payload = _make_hold_event_create(
            hold_type="partial_clinical_hold",
            hold_reason="Partial hold for specific arm",
        )
        resp = await client.post(f"{API_PREFIX}/hold-events", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["hold_type"] == "partial_clinical_hold"

    @pytest.mark.anyio
    async def test_create_impact_assessment_with_severity(self, client: AsyncClient):
        payload = _make_impact_assessment_create(impact_severity="critical")
        resp = await client.post(f"{API_PREFIX}/impact-assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["impact_severity"] == "critical"

    @pytest.mark.anyio
    async def test_create_corrective_action_plan_with_status(self, client: AsyncClient):
        payload = _make_corrective_action_plan_create(action_plan_status="submitted")
        resp = await client.post(f"{API_PREFIX}/corrective-action-plans", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["action_plan_status"] == "submitted"

    @pytest.mark.anyio
    async def test_create_restart_authorization_with_decision(self, client: AsyncClient):
        payload = _make_restart_authorization_create(restart_decision="conditional_approval")
        resp = await client.post(f"{API_PREFIX}/restart-authorizations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["restart_decision"] == "conditional_approval"

    @pytest.mark.anyio
    async def test_metrics_empty_trial_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": "nonexistent-trial"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_hold_events"] == 0
        assert data["total_impact_assessments"] == 0
        assert data["total_action_plans"] == 0
        assert data["total_restart_authorizations"] == 0
        assert data["avg_hold_duration_days"] == 0

    @pytest.mark.anyio
    async def test_hold_event_id_prefix(self, client: AsyncClient):
        payload = _make_hold_event_create()
        resp = await client.post(f"{API_PREFIX}/hold-events", json=payload)
        assert resp.status_code == 201
        assert resp.json()["id"].startswith("HLD-")

    @pytest.mark.anyio
    async def test_impact_assessment_id_prefix(self, client: AsyncClient):
        payload = _make_impact_assessment_create()
        resp = await client.post(f"{API_PREFIX}/impact-assessments", json=payload)
        assert resp.status_code == 201
        assert resp.json()["id"].startswith("IMA-")

    @pytest.mark.anyio
    async def test_corrective_action_plan_id_prefix(self, client: AsyncClient):
        payload = _make_corrective_action_plan_create()
        resp = await client.post(f"{API_PREFIX}/corrective-action-plans", json=payload)
        assert resp.status_code == 201
        assert resp.json()["id"].startswith("CAP-")

    @pytest.mark.anyio
    async def test_restart_authorization_id_prefix(self, client: AsyncClient):
        payload = _make_restart_authorization_create()
        resp = await client.post(f"{API_PREFIX}/restart-authorizations", json=payload)
        assert resp.status_code == 201
        assert resp.json()["id"].startswith("RSA-")
