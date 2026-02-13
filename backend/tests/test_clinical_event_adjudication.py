"""Tests for Clinical Event Adjudication (CEA-ADJ).

Covers:
- Seed data verification (event submissions, adjudicator assignments,
  adjudication decisions, consensus reviews)
- Event submission CRUD (create, read, update, delete, list, filter by trial/category/status)
- Adjudicator assignment CRUD (create, read, update, delete, list, filter by trial/role/event)
- Adjudication decision CRUD (create, read, update, delete, list, filter by trial/decision/event)
- Consensus review CRUD (create, read, update, delete, list, filter by trial/outcome/event)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.clinical_event_adjudication import (
    AdjudicationDecision,
    AdjudicatorRole,
    ConsensusOutcome,
    EventCategory,
    EventStatus,
)
from app.services.clinical_event_adjudication_service import (
    ClinicalEventAdjudicationService,
    get_clinical_event_adjudication_service,
    reset_clinical_event_adjudication_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/clinical-event-adjudication"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_clinical_event_adjudication_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ClinicalEventAdjudicationService:
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


def _make_submission_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-TEST-001",
        "site_id": "SITE-TEST-001",
        "event_category": "cardiovascular",
        "event_date": "2026-01-15T09:00:00Z",
        "event_description": "Test cardiovascular event for adjudication.",
        "submitted_by": "Dr. Test Physician",
        "submission_date": "2026-01-16T09:00:00Z",
    }
    defaults.update(overrides)
    return defaults


def _make_assignment_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "event_submission_id": "EVT-001",
        "adjudicator_name": "Dr. Test Reviewer",
        "adjudicator_role": "primary_reviewer",
        "specialty": "Cardiology",
        "assigned_date": "2026-01-17T09:00:00Z",
        "due_date": "2026-01-24T09:00:00Z",
    }
    defaults.update(overrides)
    return defaults


def _make_decision_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "event_submission_id": "EVT-001",
        "assignment_id": "AAG-001",
        "original_classification": "Acute MI",
        "rationale": "Biomarker and ECG evidence supports classification.",
        "decision_date": "2026-01-20T09:00:00Z",
        "adjudication_decision": "confirmed",
    }
    defaults.update(overrides)
    return defaults


def _make_consensus_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "event_submission_id": "EVT-001",
        "reviewers_count": 2,
        "chair_name": "Dr. Test Chair",
    }
    defaults.update(overrides)
    return defaults


# ===================================================================
# SEED DATA VERIFICATION
# ===================================================================


class TestSeedData:
    """Verify all 4 entity types are seeded with 12 records each."""

    @pytest.mark.anyio
    async def test_seed_event_submissions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/event-submissions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_seed_adjudicator_assignments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjudicator-assignments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_adjudication_decisions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjudication-decisions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_consensus_reviews(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consensus-reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12


# ===================================================================
# EVENT SUBMISSIONS CRUD
# ===================================================================


class TestEventSubmissionCRUD:
    @pytest.mark.anyio
    async def test_list_event_submissions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/event-submissions")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_event_submission(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/event-submissions/EVT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "EVT-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_event_submission_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/event-submissions/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_event_submission(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/event-submissions", json=_make_submission_create()
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("EVT-")
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["event_category"] == "cardiovascular"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/event-submissions")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/event-submissions", json=_make_submission_create())
        resp2 = await client.get(f"{API_PREFIX}/event-submissions")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_event_submission(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/event-submissions/EVT-001",
            json={"event_status": "under_review", "notes": "Updated note"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["event_status"] == "under_review"
        assert data["notes"] == "Updated note"

    @pytest.mark.anyio
    async def test_update_event_submission_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/event-submissions/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_event_submission(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/event-submissions/EVT-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/event-submissions/EVT-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_event_submission_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/event-submissions/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/event-submissions", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_filter_by_event_category(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/event-submissions", params={"event_category": "cardiovascular"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["event_category"] == "cardiovascular"

    @pytest.mark.anyio
    async def test_filter_by_event_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/event-submissions", params={"event_status": "adjudicated"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["event_status"] == "adjudicated"


# ===================================================================
# ADJUDICATOR ASSIGNMENTS CRUD
# ===================================================================


class TestAdjudicatorAssignmentCRUD:
    @pytest.mark.anyio
    async def test_list_adjudicator_assignments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjudicator-assignments")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_adjudicator_assignment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjudicator-assignments/AAG-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "AAG-001"

    @pytest.mark.anyio
    async def test_get_adjudicator_assignment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjudicator-assignments/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_adjudicator_assignment(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/adjudicator-assignments", json=_make_assignment_create()
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("AAG-")
        assert data["adjudicator_role"] == "primary_reviewer"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/adjudicator-assignments")
        before = resp1.json()["total"]
        await client.post(
            f"{API_PREFIX}/adjudicator-assignments", json=_make_assignment_create()
        )
        resp2 = await client.get(f"{API_PREFIX}/adjudicator-assignments")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_adjudicator_assignment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/adjudicator-assignments/AAG-001",
            json={"review_time_hours": 8.0, "notes": "Extended review"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["review_time_hours"] == 8.0
        assert data["notes"] == "Extended review"

    @pytest.mark.anyio
    async def test_update_adjudicator_assignment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/adjudicator-assignments/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_adjudicator_assignment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/adjudicator-assignments/AAG-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_adjudicator_assignment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/adjudicator-assignments/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_adjudicator_role(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/adjudicator-assignments",
            params={"adjudicator_role": "primary_reviewer"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["adjudicator_role"] == "primary_reviewer"

    @pytest.mark.anyio
    async def test_filter_by_event_submission_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/adjudicator-assignments",
            params={"event_submission_id": "EVT-001"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["event_submission_id"] == "EVT-001"

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/adjudicator-assignments",
            params={"trial_id": DUPIXENT_TRIAL},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL


# ===================================================================
# ADJUDICATION DECISIONS CRUD
# ===================================================================


class TestAdjudicationDecisionCRUD:
    @pytest.mark.anyio
    async def test_list_adjudication_decisions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjudication-decisions")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_adjudication_decision(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjudication-decisions/ADR-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "ADR-001"

    @pytest.mark.anyio
    async def test_get_adjudication_decision_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjudication-decisions/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_adjudication_decision(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/adjudication-decisions", json=_make_decision_create()
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("ADR-")
        assert data["adjudication_decision"] == "confirmed"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/adjudication-decisions")
        before = resp1.json()["total"]
        await client.post(
            f"{API_PREFIX}/adjudication-decisions", json=_make_decision_create()
        )
        resp2 = await client.get(f"{API_PREFIX}/adjudication-decisions")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_adjudication_decision(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/adjudication-decisions/ADR-001",
            json={"confidence_level": 99.0, "notes": "High confidence"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["confidence_level"] == 99.0
        assert data["notes"] == "High confidence"

    @pytest.mark.anyio
    async def test_update_adjudication_decision_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/adjudication-decisions/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_adjudication_decision(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/adjudication-decisions/ADR-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/adjudication-decisions/ADR-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_adjudication_decision_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/adjudication-decisions/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_adjudication_decision(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/adjudication-decisions",
            params={"adjudication_decision": "confirmed"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["adjudication_decision"] == "confirmed"

    @pytest.mark.anyio
    async def test_filter_by_event_submission_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/adjudication-decisions",
            params={"event_submission_id": "EVT-001"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["event_submission_id"] == "EVT-001"

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/adjudication-decisions",
            params={"trial_id": LIBTAYO_TRIAL},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL


# ===================================================================
# CONSENSUS REVIEWS CRUD
# ===================================================================


class TestConsensusReviewCRUD:
    @pytest.mark.anyio
    async def test_list_consensus_reviews(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consensus-reviews")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_consensus_review(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consensus-reviews/CNS-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "CNS-001"

    @pytest.mark.anyio
    async def test_get_consensus_review_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consensus-reviews/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_consensus_review(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/consensus-reviews", json=_make_consensus_create()
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("CNS-")
        assert data["consensus_outcome"] == "pending"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/consensus-reviews")
        before = resp1.json()["total"]
        await client.post(
            f"{API_PREFIX}/consensus-reviews", json=_make_consensus_create()
        )
        resp2 = await client.get(f"{API_PREFIX}/consensus-reviews")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_consensus_review(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/consensus-reviews/CNS-001",
            json={"consensus_outcome": "unanimous", "notes": "Confirmed consensus"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["consensus_outcome"] == "unanimous"
        assert data["notes"] == "Confirmed consensus"

    @pytest.mark.anyio
    async def test_update_consensus_review_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/consensus-reviews/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_consensus_review(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/consensus-reviews/CNS-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/consensus-reviews/CNS-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_consensus_review_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/consensus-reviews/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_consensus_outcome(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/consensus-reviews",
            params={"consensus_outcome": "unanimous"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["consensus_outcome"] == "unanimous"

    @pytest.mark.anyio
    async def test_filter_by_event_submission_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/consensus-reviews",
            params={"event_submission_id": "EVT-001"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["event_submission_id"] == "EVT-001"

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/consensus-reviews",
            params={"trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL


# ===================================================================
# METRICS
# ===================================================================


class TestMetrics:
    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_submissions" in data
        assert "total_assignments" in data
        assert "total_decisions" in data
        assert "total_consensus_reviews" in data
        assert "avg_confidence_level" in data
        assert "consensus_rate" in data

    @pytest.mark.anyio
    async def test_metrics_total_submissions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_submissions"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_assignments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_assignments"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_decisions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_decisions"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_consensus_reviews(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_consensus_reviews"] == 12

    @pytest.mark.anyio
    async def test_metrics_has_breakdowns(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert isinstance(data["submissions_by_category"], dict)
        assert isinstance(data["submissions_by_status"], dict)
        assert isinstance(data["assignments_by_role"], dict)
        assert isinstance(data["decisions_by_outcome"], dict)
        assert isinstance(data["consensus_by_outcome"], dict)

    @pytest.mark.anyio
    async def test_metrics_avg_confidence(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["avg_confidence_level"] > 0

    @pytest.mark.anyio
    async def test_metrics_consensus_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["consensus_rate"] > 0

    def test_metrics_service_level(self, svc: ClinicalEventAdjudicationService):
        metrics = svc.get_metrics()
        assert metrics.total_submissions == 12
        assert metrics.total_assignments == 12
        assert metrics.total_decisions == 12
        assert metrics.total_consensus_reviews == 12


# ===================================================================
# EDGE CASES & UPDATE PRESERVATION
# ===================================================================


class TestEdgeCases:
    @pytest.mark.anyio
    async def test_update_submission_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/event-submissions/EVT-001")
        original = resp.json()
        original_category = original["event_category"]

        resp2 = await client.put(
            f"{API_PREFIX}/event-submissions/EVT-001",
            json={"notes": "Partial update"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["event_category"] == original_category
        assert updated["notes"] == "Partial update"

    @pytest.mark.anyio
    async def test_update_assignment_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjudicator-assignments/AAG-001")
        original = resp.json()
        original_specialty = original["specialty"]

        resp2 = await client.put(
            f"{API_PREFIX}/adjudicator-assignments/AAG-001",
            json={"notes": "Updated assignment note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["specialty"] == original_specialty

    @pytest.mark.anyio
    async def test_update_decision_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjudication-decisions/ADR-001")
        original = resp.json()
        original_rationale = original["rationale"]

        resp2 = await client.put(
            f"{API_PREFIX}/adjudication-decisions/ADR-001",
            json={"notes": "Updated decision note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["rationale"] == original_rationale

    @pytest.mark.anyio
    async def test_update_consensus_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consensus-reviews/CNS-001")
        original = resp.json()
        original_reviewers = original["reviewers_count"]

        resp2 = await client.put(
            f"{API_PREFIX}/consensus-reviews/CNS-001",
            json={"notes": "Updated consensus note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["reviewers_count"] == original_reviewers


# ===================================================================
# SINGLETON PATTERN
# ===================================================================


class TestSingleton:
    def test_get_returns_same_instance(self):
        svc1 = get_clinical_event_adjudication_service()
        svc2 = get_clinical_event_adjudication_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        svc1 = get_clinical_event_adjudication_service()
        svc2 = reset_clinical_event_adjudication_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_clinical_event_adjudication_service()
        svc.delete_event_submission("EVT-001")
        assert svc.get_event_submission("EVT-001") is None
        svc2 = reset_clinical_event_adjudication_service()
        assert svc2.get_event_submission("EVT-001") is not None


# ===================================================================
# SERVICE-LEVEL CRUD
# ===================================================================


class TestServiceLevelCRUD:
    def test_list_event_submissions_service(self, svc: ClinicalEventAdjudicationService):
        items = svc.list_event_submissions()
        assert len(items) == 12

    def test_get_event_submission_service(self, svc: ClinicalEventAdjudicationService):
        record = svc.get_event_submission("EVT-001")
        assert record is not None
        assert record.id == "EVT-001"

    def test_list_adjudicator_assignments_service(self, svc: ClinicalEventAdjudicationService):
        items = svc.list_adjudicator_assignments()
        assert len(items) == 12

    def test_get_adjudicator_assignment_service(self, svc: ClinicalEventAdjudicationService):
        record = svc.get_adjudicator_assignment("AAG-001")
        assert record is not None
        assert record.id == "AAG-001"

    def test_list_adjudication_decisions_service(self, svc: ClinicalEventAdjudicationService):
        items = svc.list_adjudication_decision_records()
        assert len(items) == 12

    def test_get_adjudication_decision_service(self, svc: ClinicalEventAdjudicationService):
        record = svc.get_adjudication_decision_record("ADR-001")
        assert record is not None
        assert record.id == "ADR-001"

    def test_list_consensus_reviews_service(self, svc: ClinicalEventAdjudicationService):
        items = svc.list_consensus_reviews()
        assert len(items) == 12

    def test_get_consensus_review_service(self, svc: ClinicalEventAdjudicationService):
        record = svc.get_consensus_review("CNS-001")
        assert record is not None
        assert record.id == "CNS-001"

    def test_delete_event_submission_service(self, svc: ClinicalEventAdjudicationService):
        assert svc.delete_event_submission("EVT-001") is True
        assert svc.get_event_submission("EVT-001") is None

    def test_delete_nonexistent_returns_false(self, svc: ClinicalEventAdjudicationService):
        assert svc.delete_event_submission("NONEXISTENT") is False

    def test_filter_submissions_by_trial(self, svc: ClinicalEventAdjudicationService):
        items = svc.list_event_submissions(trial_id=EYLEA_TRIAL)
        for item in items:
            assert item.trial_id == EYLEA_TRIAL

    def test_filter_assignments_by_role(self, svc: ClinicalEventAdjudicationService):
        items = svc.list_adjudicator_assignments(
            adjudicator_role=AdjudicatorRole.PRIMARY_REVIEWER
        )
        for item in items:
            assert item.adjudicator_role == AdjudicatorRole.PRIMARY_REVIEWER

    def test_filter_decisions_by_outcome(self, svc: ClinicalEventAdjudicationService):
        items = svc.list_adjudication_decision_records(
            adjudication_decision=AdjudicationDecision.CONFIRMED
        )
        for item in items:
            assert item.adjudication_decision == AdjudicationDecision.CONFIRMED

    def test_filter_consensus_by_outcome(self, svc: ClinicalEventAdjudicationService):
        items = svc.list_consensus_reviews(consensus_outcome=ConsensusOutcome.UNANIMOUS)
        for item in items:
            assert item.consensus_outcome == ConsensusOutcome.UNANIMOUS


# ===================================================================
# BULK / MULTI-ENTITY
# ===================================================================


class TestBulkOperations:
    @pytest.mark.anyio
    async def test_create_multiple_event_submissions(self, client: AsyncClient):
        for i in range(3):
            resp = await client.post(
                f"{API_PREFIX}/event-submissions",
                json=_make_submission_create(subject_id=f"BULK-{i}"),
            )
            assert resp.status_code == 201
        resp = await client.get(f"{API_PREFIX}/event-submissions")
        assert resp.json()["total"] == 15  # 12 seed + 3 new

    @pytest.mark.anyio
    async def test_delete_multiple_decisions(self, client: AsyncClient):
        for decision_id in ["ADR-001", "ADR-002", "ADR-003"]:
            resp = await client.delete(f"{API_PREFIX}/adjudication-decisions/{decision_id}")
            assert resp.status_code == 204
        resp = await client.get(f"{API_PREFIX}/adjudication-decisions")
        assert resp.json()["total"] == 9  # 12 seed - 3 deleted


# ===================================================================
# RESPONSE STRUCTURE
# ===================================================================


class TestAPIResponseStructure:
    @pytest.mark.anyio
    async def test_event_submission_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/event-submissions/EVT-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "subject_id", "site_id", "event_category",
            "event_status", "event_date", "event_description", "submitted_by",
            "submission_date", "blinded", "priority_review", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_adjudicator_assignment_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjudicator-assignments/AAG-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "event_submission_id", "adjudicator_name",
            "adjudicator_role", "specialty", "assigned_date", "due_date",
            "is_active", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_adjudication_decision_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjudication-decisions/ADR-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "event_submission_id", "assignment_id",
            "adjudication_decision", "original_classification", "confidence_level",
            "rationale", "decision_date", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_consensus_review_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consensus-reviews/CNS-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "event_submission_id", "consensus_outcome",
            "reviewers_count", "agreeing_count", "disagreeing_count", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_list_response_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/event-submissions")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
