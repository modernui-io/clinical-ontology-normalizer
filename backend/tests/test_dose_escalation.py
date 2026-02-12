"""Tests for Dose Escalation Management (DOSE-ESC).

Covers:
- Seed data verification (dose levels, DLT events, cohort decisions, PK results, RP2D)
- Dose level CRUD (create, read, update, delete, list, filter by trial)
- DLT event CRUD (create, read, update, delete, list, filter by trial)
- Cohort decision CRUD (create, read, update, delete, list, filter by trial)
- PK result CRUD (create, read, update, delete, list, filter by trial)
- RP2D recommendation CRUD (create, read, update, delete, list, filter by trial)
- Metrics computation
- Error handling (404s)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.dose_escalation_service import (
    DoseEscalationService,
    get_dose_escalation_service,
    reset_dose_escalation_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/dose-escalation"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_dose_escalation_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> DoseEscalationService:
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


def _make_dose_level_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "cohort_number": 5,
        "dose_amount": 16.0,
        "dose_unit": "mg",
        "route": "intravitreal",
        "schedule": "Q12W",
        "design": "3+3",
        "target_enrollment": 3,
        "evaluation_period_days": 28,
    }
    defaults.update(overrides)
    return defaults


def _make_dlt_event_create(**overrides) -> dict:
    defaults = {
        "dose_level_id": "DL-003",
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-9999",
        "dlt_grade": "grade_3",
        "toxicity_term": "Test toxicity",
        "organ_system": "Eye",
        "onset_day": 10,
        "attribution": "probable",
        "reported_by": "Dr. Test",
    }
    defaults.update(overrides)
    return defaults


def _make_cohort_decision_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "dose_level_id": "DL-004",
        "trial_id": EYLEA_TRIAL,
        "decision": "escalate",
        "rationale": "No DLTs observed. Safe to escalate.",
        "safety_review_date": now.isoformat(),
        "approved_by": "Dr. Test",
        "dlt_rate_observed": 0.0,
        "committee_members": ["Dr. A", "Dr. B"],
    }
    defaults.update(overrides)
    return defaults


def _make_pk_result_create(**overrides) -> dict:
    defaults = {
        "dose_level_id": "DL-001",
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-9999",
        "parameter": "cmax",
        "value": 1.25,
        "unit": "ug/mL",
        "time_point_hours": 24.0,
        "sample_matrix": "plasma",
    }
    defaults.update(overrides)
    return defaults


def _make_rp2d_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "recommended_dose": 10.0,
        "dose_unit": "mg",
        "recommended_schedule": "Q8W",
        "selected_dose_level_id": "DL-003",
        "safety_summary": "Well tolerated with acceptable DLT rate.",
        "proposed_by": "Dr. Test",
        "total_subjects_evaluated": 15,
        "overall_dlt_rate_pct": 10.0,
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_dose_levels_count(self, svc: DoseEscalationService):
        levels = svc.list_dose_levels()
        assert len(levels) == 12

    def test_seed_dose_levels_per_trial(self, svc: DoseEscalationService):
        eylea = svc.list_dose_levels(trial_id=EYLEA_TRIAL)
        dupixent = svc.list_dose_levels(trial_id=DUPIXENT_TRIAL)
        libtayo = svc.list_dose_levels(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) == 4
        assert len(dupixent) == 4
        assert len(libtayo) == 4

    def test_seed_dlt_events_count(self, svc: DoseEscalationService):
        events = svc.list_dlt_events()
        assert len(events) == 10

    def test_seed_cohort_decisions_count(self, svc: DoseEscalationService):
        decisions = svc.list_cohort_decisions()
        assert len(decisions) == 10

    def test_seed_pk_results_count(self, svc: DoseEscalationService):
        results = svc.list_pk_results()
        assert len(results) == 12

    def test_seed_rp2d_count(self, svc: DoseEscalationService):
        rp2ds = svc.list_rp2d_recommendations()
        assert len(rp2ds) == 3

    def test_seed_rp2d_approved_count(self, svc: DoseEscalationService):
        rp2ds = svc.list_rp2d_recommendations()
        approved = [r for r in rp2ds if r.status == "approved"]
        assert len(approved) == 2

    def test_seed_dose_levels_statuses(self, svc: DoseEscalationService):
        levels = svc.list_dose_levels()
        statuses = {dl.status.value for dl in levels}
        assert "completed" in statuses
        assert "enrolling" in statuses
        assert "planned" in statuses

    def test_seed_dlt_grades_present(self, svc: DoseEscalationService):
        events = svc.list_dlt_events()
        grades = {e.dlt_grade.value for e in events}
        assert "grade_3" in grades
        assert "grade_4" in grades

    def test_seed_escalation_decisions_present(self, svc: DoseEscalationService):
        decisions = svc.list_cohort_decisions()
        types = {d.decision.value for d in decisions}
        assert "escalate" in types
        assert "de_escalate" in types
        assert "stay" in types
        assert "expand" in types


# =====================================================================
# DOSE LEVEL CRUD
# =====================================================================


class TestDoseLevelCrud:
    """Test dose level CRUD operations."""

    @pytest.mark.anyio
    async def test_list_dose_levels(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dose-levels")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_dose_levels_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dose-levels", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_dose_level(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dose-levels/DL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DL-001"
        assert data["dose_amount"] == 2.0

    @pytest.mark.anyio
    async def test_get_dose_level_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dose-levels/DL-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_dose_level(self, client: AsyncClient):
        payload = _make_dose_level_create()
        resp = await client.post(f"{API_PREFIX}/dose-levels", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["dose_amount"] == 16.0
        assert data["status"] == "planned"
        assert data["id"].startswith("DL-")

    @pytest.mark.anyio
    async def test_update_dose_level(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/dose-levels/DL-004",
            json={"status": "completed", "actual_enrollment": 3},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["actual_enrollment"] == 3

    @pytest.mark.anyio
    async def test_update_dose_level_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/dose-levels/DL-NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_dose_level(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/dose-levels/DL-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/dose-levels/DL-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_dose_level_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/dose-levels/DL-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# DLT EVENT CRUD
# =====================================================================


class TestDLTEventCrud:
    """Test DLT event CRUD operations."""

    @pytest.mark.anyio
    async def test_list_dlt_events(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dlt-events")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_dlt_events_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dlt-events", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_get_dlt_event(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dlt-events/DLT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DLT-001"
        assert data["toxicity_term"] == "Intraocular inflammation"

    @pytest.mark.anyio
    async def test_get_dlt_event_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dlt-events/DLT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_dlt_event(self, client: AsyncClient):
        payload = _make_dlt_event_create()
        resp = await client.post(f"{API_PREFIX}/dlt-events", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["subject_id"] == "SUBJ-9999"
        assert data["id"].startswith("DLT-")

    @pytest.mark.anyio
    async def test_update_dlt_event(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/dlt-events/DLT-007",
            json={"resolved": True, "resolution_day": 42, "reviewed_by": "Dr. Reviewer"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["resolved"] is True
        assert data["resolution_day"] == 42
        assert data["reviewed_by"] == "Dr. Reviewer"

    @pytest.mark.anyio
    async def test_update_dlt_event_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/dlt-events/DLT-NONEXISTENT",
            json={"resolved": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_dlt_event(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/dlt-events/DLT-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/dlt-events/DLT-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_dlt_event_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/dlt-events/DLT-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# COHORT DECISION CRUD
# =====================================================================


class TestCohortDecisionCrud:
    """Test cohort decision CRUD operations."""

    @pytest.mark.anyio
    async def test_list_cohort_decisions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cohort-decisions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_cohort_decisions_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cohort-decisions", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_cohort_decision(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cohort-decisions/CD-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CD-001"
        assert data["decision"] == "escalate"

    @pytest.mark.anyio
    async def test_get_cohort_decision_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cohort-decisions/CD-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_cohort_decision(self, client: AsyncClient):
        payload = _make_cohort_decision_create()
        resp = await client.post(f"{API_PREFIX}/cohort-decisions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["decision"] == "escalate"
        assert data["id"].startswith("CD-")

    @pytest.mark.anyio
    async def test_update_cohort_decision(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/cohort-decisions/CD-001",
            json={"model_recommendation": "CRM supports escalation"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["model_recommendation"] == "CRM supports escalation"

    @pytest.mark.anyio
    async def test_update_cohort_decision_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/cohort-decisions/CD-NONEXISTENT",
            json={"model_recommendation": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_cohort_decision(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/cohort-decisions/CD-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/cohort-decisions/CD-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_cohort_decision_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/cohort-decisions/CD-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# PK RESULT CRUD
# =====================================================================


class TestPKResultCrud:
    """Test PK result CRUD operations."""

    @pytest.mark.anyio
    async def test_list_pk_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pk-results")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_pk_results_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pk-results", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_pk_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pk-results/PK-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PK-001"
        assert data["parameter"] == "cmax"

    @pytest.mark.anyio
    async def test_get_pk_result_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pk-results/PK-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_pk_result(self, client: AsyncClient):
        payload = _make_pk_result_create()
        resp = await client.post(f"{API_PREFIX}/pk-results", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["value"] == 1.25
        assert data["id"].startswith("PK-")

    @pytest.mark.anyio
    async def test_update_pk_result(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/pk-results/PK-001",
            json={"dose_proportional": False, "bioanalytical_method": "LC-MS/MS v2"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dose_proportional"] is False
        assert data["bioanalytical_method"] == "LC-MS/MS v2"

    @pytest.mark.anyio
    async def test_update_pk_result_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/pk-results/PK-NONEXISTENT",
            json={"dose_proportional": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_pk_result(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/pk-results/PK-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/pk-results/PK-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_pk_result_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/pk-results/PK-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# RP2D RECOMMENDATION CRUD
# =====================================================================


class TestRP2DRecommendationCrud:
    """Test RP2D recommendation CRUD operations."""

    @pytest.mark.anyio
    async def test_list_rp2d_recommendations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/rp2d-recommendations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_rp2d_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/rp2d-recommendations", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_get_rp2d_recommendation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/rp2d-recommendations/RP2D-002")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RP2D-002"
        assert data["recommended_dose"] == 300.0
        assert data["status"] == "approved"

    @pytest.mark.anyio
    async def test_get_rp2d_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/rp2d-recommendations/RP2D-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_rp2d_recommendation(self, client: AsyncClient):
        payload = _make_rp2d_create()
        resp = await client.post(f"{API_PREFIX}/rp2d-recommendations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["recommended_dose"] == 10.0
        assert data["status"] == "proposed"
        assert data["id"].startswith("RP2D-")

    @pytest.mark.anyio
    async def test_update_rp2d_recommendation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/rp2d-recommendations/RP2D-001",
            json={"status": "approved", "approved_by": "Dr. Approver"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["approved_by"] == "Dr. Approver"

    @pytest.mark.anyio
    async def test_update_rp2d_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/rp2d-recommendations/RP2D-NONEXISTENT",
            json={"status": "approved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_rp2d_recommendation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/rp2d-recommendations/RP2D-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/rp2d-recommendations/RP2D-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_rp2d_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/rp2d-recommendations/RP2D-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestDoseEscalationMetrics:
    """Test dose escalation metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_dose_levels"] == 12
        assert data["total_dlts"] == 10
        assert data["total_decisions"] == 10
        assert data["total_pk_results"] == 12
        assert data["total_rp2d_recommendations"] == 3
        assert data["rp2d_approved"] == 2
        assert data["total_subjects_enrolled"] > 0
        assert 0.0 <= data["overall_dlt_rate_pct"] <= 100.0

    @pytest.mark.anyio
    async def test_get_metrics_by_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_dose_levels"] == 4

    def test_metrics_levels_by_status(self, svc: DoseEscalationService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.levels_by_status.values())
        assert total_by_status == metrics.total_dose_levels

    def test_metrics_levels_by_design(self, svc: DoseEscalationService):
        metrics = svc.get_metrics()
        total_by_design = sum(metrics.levels_by_design.values())
        assert total_by_design == metrics.total_dose_levels

    def test_metrics_dlts_by_grade(self, svc: DoseEscalationService):
        metrics = svc.get_metrics()
        total_by_grade = sum(metrics.dlts_by_grade.values())
        assert total_by_grade == metrics.total_dlts

    def test_metrics_decisions_by_type(self, svc: DoseEscalationService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.decisions_by_type.values())
        assert total_by_type == metrics.total_decisions

    @pytest.mark.anyio
    async def test_metrics_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_dose_levels"] == 0
        assert data["total_dlts"] == 0
        assert data["overall_dlt_rate_pct"] == 0.0


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_dose_escalation_service()
        svc2 = get_dose_escalation_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_dose_escalation_service()
        svc2 = reset_dose_escalation_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_dose_escalation_service()
        svc.delete_dose_level("DL-001")
        assert svc.get_dose_level("DL-001") is None
        svc2 = reset_dose_escalation_service()
        assert svc2.get_dose_level("DL-001") is not None


# =====================================================================
# EDGE CASES AND DATA VALIDATION
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_dose_levels_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dose-levels")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_dlt_events_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dlt-events")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_cohort_decisions_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cohort-decisions")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_pk_results_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pk-results")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_rp2d_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/rp2d-recommendations")
        assert resp.status_code == 200

    def test_dose_level_has_required_fields(self, svc: DoseEscalationService):
        dl = svc.get_dose_level("DL-001")
        assert dl is not None
        assert dl.id
        assert dl.trial_id
        assert dl.dose_amount > 0
        assert dl.dose_unit
        assert dl.route
        assert dl.schedule
        assert dl.design is not None
        assert dl.status is not None

    def test_dlt_event_has_required_fields(self, svc: DoseEscalationService):
        dlt = svc.get_dlt_event("DLT-001")
        assert dlt is not None
        assert dlt.id
        assert dlt.dose_level_id
        assert dlt.trial_id
        assert dlt.subject_id
        assert dlt.dlt_grade is not None
        assert dlt.toxicity_term
        assert dlt.organ_system

    def test_cohort_decision_has_required_fields(self, svc: DoseEscalationService):
        cd = svc.get_cohort_decision("CD-001")
        assert cd is not None
        assert cd.id
        assert cd.dose_level_id
        assert cd.trial_id
        assert cd.decision is not None
        assert cd.rationale
        assert cd.approved_by

    def test_pk_result_has_required_fields(self, svc: DoseEscalationService):
        pk = svc.get_pk_result("PK-001")
        assert pk is not None
        assert pk.id
        assert pk.dose_level_id
        assert pk.trial_id
        assert pk.parameter is not None
        assert pk.value > 0
        assert pk.unit

    def test_rp2d_has_required_fields(self, svc: DoseEscalationService):
        rp2d = svc.get_rp2d_recommendation("RP2D-001")
        assert rp2d is not None
        assert rp2d.id
        assert rp2d.trial_id
        assert rp2d.recommended_dose > 0
        assert rp2d.dose_unit
        assert rp2d.recommended_schedule
        assert rp2d.safety_summary
        assert rp2d.proposed_by

    def test_completed_levels_have_enrollment(self, svc: DoseEscalationService):
        levels = svc.list_dose_levels()
        for dl in levels:
            if dl.status.value == "completed":
                assert dl.actual_enrollment > 0
                assert dl.completion_date is not None

    def test_planned_levels_have_no_enrollment(self, svc: DoseEscalationService):
        levels = svc.list_dose_levels()
        for dl in levels:
            if dl.status.value == "planned":
                assert dl.actual_enrollment == 0
                assert dl.start_date is None
