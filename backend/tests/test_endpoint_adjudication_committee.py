"""Tests for Endpoint Adjudication Committee (EAC-MGMT).

Covers:
- Seed data verification (committee members, case reviews, adjudication results, charters, blinding)
- Committee member CRUD (create, read, update, delete, list, filter by trial/role/active)
- Case review CRUD (create, read, update, delete, list, filter by trial/status)
- Adjudication result CRUD (create, read, update, delete, list, filter by trial/outcome)
- Charter record CRUD (create, read, update, delete, list, filter by trial/status)
- Blinding compliance CRUD (create, read, update, delete, list, filter by trial/status)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
- Filtering and edge cases
- Enum coverage in seed data
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.endpoint_adjudication_committee import (
    AdjudicationOutcome,
    BlindingStatus,
    CaseStatus,
    CharterStatus,
    MemberRole,
)
from app.services.endpoint_adjudication_committee_service import (
    EndpointAdjudicationCommitteeService,
    get_endpoint_adjudication_committee_service,
    reset_endpoint_adjudication_committee_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/endpoint-adjudication-committee"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_endpoint_adjudication_committee_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> EndpointAdjudicationCommitteeService:
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


def _make_committee_member_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "member_name": "Dr. Test Member",
        "role": "voting_member",
        "specialty": "Ophthalmology",
        "institution": "Test University Hospital",
        "appointed_by": "Sponsor Medical Director",
    }
    defaults.update(overrides)
    return defaults


def _make_case_review_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": DUPIXENT_TRIAL,
        "case_number": "TEST-2025-001",
        "subject_id": "SUBJ-9999",
        "event_type": "Test Endpoint Event",
        "event_date": (now - timedelta(days=5)).isoformat(),
        "submitted_by": "Site Investigator - Site 999",
        "assigned_reviewers": ["CM-005", "CM-006"],
    }
    defaults.update(overrides)
    return defaults


def _make_adjudication_result_create(**overrides) -> dict:
    defaults = {
        "trial_id": LIBTAYO_TRIAL,
        "case_id": "CR-007",
        "outcome": "confirmed",
        "original_classification": "Test Original",
        "final_classification": "Test Final",
        "rationale": "Test rationale for adjudication decision",
        "adjudicated_by": "EAC Panel (Test)",
    }
    defaults.update(overrides)
    return defaults


def _make_charter_record_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "version": "3.0",
        "authored_by": "Dr. Test Author",
        "quorum_requirement": 3,
        "endpoint_definitions": ["Test endpoint definition 1", "Test endpoint definition 2"],
    }
    defaults.update(overrides)
    return defaults


def _make_blinding_compliance_create(**overrides) -> dict:
    defaults = {
        "trial_id": DUPIXENT_TRIAL,
        "assessed_by": "Test Coordinator",
        "blinding_status": "maintained",
        "case_id": None,
        "member_id": None,
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_committee_members_count(self, svc: EndpointAdjudicationCommitteeService):
        members = svc.list_committee_members()
        assert len(members) == 12

    def test_seed_case_reviews_count(self, svc: EndpointAdjudicationCommitteeService):
        cases = svc.list_case_reviews()
        assert len(cases) == 12

    def test_seed_adjudication_results_count(self, svc: EndpointAdjudicationCommitteeService):
        results = svc.list_adjudication_results()
        assert len(results) == 12

    def test_seed_charter_records_count(self, svc: EndpointAdjudicationCommitteeService):
        charters = svc.list_charter_records()
        assert len(charters) == 10

    def test_seed_blinding_compliance_count(self, svc: EndpointAdjudicationCommitteeService):
        blinding = svc.list_blinding_compliance()
        assert len(blinding) == 12

    def test_seed_members_cover_all_trials(self, svc: EndpointAdjudicationCommitteeService):
        members = svc.list_committee_members()
        trial_ids = {m.trial_id for m in members}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_cases_cover_all_trials(self, svc: EndpointAdjudicationCommitteeService):
        cases = svc.list_case_reviews()
        trial_ids = {c.trial_id for c in cases}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_members_have_multiple_roles(self, svc: EndpointAdjudicationCommitteeService):
        members = svc.list_committee_members()
        roles = {m.role for m in members}
        assert len(roles) >= 4

    def test_seed_cases_have_multiple_statuses(self, svc: EndpointAdjudicationCommitteeService):
        cases = svc.list_case_reviews()
        statuses = {c.status for c in cases}
        assert CaseStatus.ADJUDICATED in statuses
        assert CaseStatus.PENDING_REVIEW in statuses

    def test_seed_results_have_multiple_outcomes(self, svc: EndpointAdjudicationCommitteeService):
        results = svc.list_adjudication_results()
        outcomes = {r.outcome for r in results}
        assert AdjudicationOutcome.CONFIRMED in outcomes
        assert AdjudicationOutcome.NOT_CONFIRMED in outcomes

    def test_seed_has_inactive_member(self, svc: EndpointAdjudicationCommitteeService):
        members = svc.list_committee_members()
        inactive = [m for m in members if not m.is_active]
        assert len(inactive) >= 1

    def test_seed_has_confirmed_breach(self, svc: EndpointAdjudicationCommitteeService):
        blinding = svc.list_blinding_compliance()
        statuses = {b.blinding_status for b in blinding}
        assert BlindingStatus.CONFIRMED_BREACH in statuses


# =====================================================================
# COMMITTEE MEMBER CRUD
# =====================================================================


class TestCommitteeMemberCrud:
    """Test committee member CRUD operations."""

    @pytest.mark.anyio
    async def test_list_committee_members(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/committee-members")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_committee_members_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/committee-members", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_committee_members_filter_role(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/committee-members", params={"role": "chair"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["role"] == "chair"

    @pytest.mark.anyio
    async def test_list_committee_members_filter_active(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/committee-members", params={"is_active": True}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["is_active"] is True

    @pytest.mark.anyio
    async def test_list_committee_members_filter_inactive(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/committee-members", params={"is_active": False}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["is_active"] is False

    @pytest.mark.anyio
    async def test_get_committee_member(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/committee-members/CM-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CM-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["role"] == "chair"
        assert data["member_name"] == "Dr. Eleanor Hartfield"

    @pytest.mark.anyio
    async def test_get_committee_member_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/committee-members/CM-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_committee_member(self, client: AsyncClient):
        payload = _make_committee_member_create()
        resp = await client.post(f"{API_PREFIX}/committee-members", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["role"] == "voting_member"
        assert data["is_active"] is True
        assert data["training_completed"] is False
        assert data["cases_reviewed"] == 0
        assert data["id"].startswith("CM-")

    @pytest.mark.anyio
    async def test_update_committee_member(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/committee-members/CM-012",
            json={"is_active": True, "notes": "Reactivated for new term"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_active"] is True
        assert data["notes"] == "Reactivated for new term"

    @pytest.mark.anyio
    async def test_update_committee_member_training(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/committee-members/CM-012",
            json={"training_completed": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["training_completed"] is True

    @pytest.mark.anyio
    async def test_update_committee_member_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/committee-members/CM-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_committee_member(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/committee-members/CM-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/committee-members/CM-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_committee_member_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/committee-members/CM-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# CASE REVIEW CRUD
# =====================================================================


class TestCaseReviewCrud:
    """Test case review CRUD operations."""

    @pytest.mark.anyio
    async def test_list_case_reviews(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/case-reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_case_reviews_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/case-reviews", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_case_reviews_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/case-reviews", params={"status": "adjudicated"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "adjudicated"

    @pytest.mark.anyio
    async def test_list_case_reviews_filter_pending(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/case-reviews", params={"status": "pending_review"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "pending_review"

    @pytest.mark.anyio
    async def test_get_case_review(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/case-reviews/CR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CR-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["case_number"] == "EYL-2025-001"
        assert data["status"] == "adjudicated"

    @pytest.mark.anyio
    async def test_get_case_review_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/case-reviews/CR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_case_review(self, client: AsyncClient):
        payload = _make_case_review_create()
        resp = await client.post(f"{API_PREFIX}/case-reviews", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == DUPIXENT_TRIAL
        assert data["case_number"] == "TEST-2025-001"
        assert data["status"] == "pending_review"
        assert data["source_documents_received"] is False
        assert data["id"].startswith("CR-")

    @pytest.mark.anyio
    async def test_update_case_review(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/case-reviews/CR-010",
            json={"status": "under_review", "documents_adequate": True, "notes": "Documents received"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "under_review"
        assert data["documents_adequate"] is True
        assert data["notes"] == "Documents received"

    @pytest.mark.anyio
    async def test_update_case_review_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/case-reviews/CR-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_case_review(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/case-reviews/CR-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/case-reviews/CR-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_case_review_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/case-reviews/CR-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# ADJUDICATION RESULT CRUD
# =====================================================================


class TestAdjudicationResultCrud:
    """Test adjudication result CRUD operations."""

    @pytest.mark.anyio
    async def test_list_adjudication_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjudication-results")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_adjudication_results_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/adjudication-results", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_adjudication_results_filter_outcome(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/adjudication-results", params={"outcome": "confirmed"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["outcome"] == "confirmed"

    @pytest.mark.anyio
    async def test_list_adjudication_results_filter_not_confirmed(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/adjudication-results", params={"outcome": "not_confirmed"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["outcome"] == "not_confirmed"

    @pytest.mark.anyio
    async def test_get_adjudication_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjudication-results/AR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "AR-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["outcome"] == "confirmed"
        assert data["unanimous"] is True

    @pytest.mark.anyio
    async def test_get_adjudication_result_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjudication-results/AR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_adjudication_result(self, client: AsyncClient):
        payload = _make_adjudication_result_create()
        resp = await client.post(f"{API_PREFIX}/adjudication-results", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == LIBTAYO_TRIAL
        assert data["outcome"] == "confirmed"
        assert data["finalized"] is False
        assert data["reviewed_by_chair"] is False
        assert data["id"].startswith("AR-")

    @pytest.mark.anyio
    async def test_update_adjudication_result(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/adjudication-results/AR-007",
            json={"finalized": True, "reviewed_by_chair": True, "notes": "Finalized after re-photography"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["finalized"] is True
        assert data["reviewed_by_chair"] is True
        assert data["notes"] == "Finalized after re-photography"

    @pytest.mark.anyio
    async def test_update_adjudication_result_votes(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/adjudication-results/AR-008",
            json={"votes_for": 2, "votes_against": 1},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["votes_for"] == 2
        assert data["votes_against"] == 1

    @pytest.mark.anyio
    async def test_update_adjudication_result_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/adjudication-results/AR-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_adjudication_result(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/adjudication-results/AR-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/adjudication-results/AR-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_adjudication_result_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/adjudication-results/AR-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# CHARTER RECORD CRUD
# =====================================================================


class TestCharterRecordCrud:
    """Test charter record CRUD operations."""

    @pytest.mark.anyio
    async def test_list_charter_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/charter-records")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_charter_records_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/charter-records", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_charter_records_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/charter-records", params={"status": "approved"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "approved"

    @pytest.mark.anyio
    async def test_list_charter_records_filter_draft(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/charter-records", params={"status": "draft"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "draft"

    @pytest.mark.anyio
    async def test_get_charter_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/charter-records/CH-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CH-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["version"] == "1.0"
        assert data["status"] == "superseded"

    @pytest.mark.anyio
    async def test_get_charter_record_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/charter-records/CH-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_charter_record(self, client: AsyncClient):
        payload = _make_charter_record_create()
        resp = await client.post(f"{API_PREFIX}/charter-records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["version"] == "3.0"
        assert data["status"] == "draft"
        assert data["quorum_requirement"] == 3
        assert len(data["endpoint_definitions"]) == 2
        assert data["id"].startswith("CH-")

    @pytest.mark.anyio
    async def test_update_charter_record(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/charter-records/CH-006",
            json={"status": "approved", "approved_by": "Sponsor Medical Director"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["approved_by"] == "Sponsor Medical Director"

    @pytest.mark.anyio
    async def test_update_charter_record_blinding(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/charter-records/CH-008",
            json={"blinding_procedures": "Enhanced BICR blinding protocol", "notes": "Updated"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["blinding_procedures"] == "Enhanced BICR blinding protocol"
        assert data["notes"] == "Updated"

    @pytest.mark.anyio
    async def test_update_charter_record_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/charter-records/CH-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_charter_record(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/charter-records/CH-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/charter-records/CH-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_charter_record_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/charter-records/CH-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# BLINDING COMPLIANCE CRUD
# =====================================================================


class TestBlindingComplianceCrud:
    """Test blinding compliance CRUD operations."""

    @pytest.mark.anyio
    async def test_list_blinding_compliance(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/blinding-compliance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_blinding_compliance_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/blinding-compliance", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_blinding_compliance_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/blinding-compliance", params={"blinding_status": "maintained"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["blinding_status"] == "maintained"

    @pytest.mark.anyio
    async def test_list_blinding_compliance_filter_breach(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/blinding-compliance", params={"blinding_status": "confirmed_breach"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["blinding_status"] == "confirmed_breach"

    @pytest.mark.anyio
    async def test_get_blinding_compliance(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/blinding-compliance/BC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "BC-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["blinding_status"] == "maintained"

    @pytest.mark.anyio
    async def test_get_blinding_compliance_breach(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/blinding-compliance/BC-005")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "BC-005"
        assert data["blinding_status"] == "confirmed_breach"
        assert data["reported_to_sponsor"] is True
        assert data["reported_to_irb"] is True

    @pytest.mark.anyio
    async def test_get_blinding_compliance_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/blinding-compliance/BC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_blinding_compliance(self, client: AsyncClient):
        payload = _make_blinding_compliance_create()
        resp = await client.post(f"{API_PREFIX}/blinding-compliance", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == DUPIXENT_TRIAL
        assert data["blinding_status"] == "maintained"
        assert data["reported_to_sponsor"] is False
        assert data["id"].startswith("BC-")

    @pytest.mark.anyio
    async def test_create_blinding_compliance_with_case(self, client: AsyncClient):
        payload = _make_blinding_compliance_create(
            case_id="CR-012",
            member_id="CM-005",
            blinding_status="potential_breach",
        )
        resp = await client.post(f"{API_PREFIX}/blinding-compliance", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["case_id"] == "CR-012"
        assert data["member_id"] == "CM-005"
        assert data["blinding_status"] == "potential_breach"

    @pytest.mark.anyio
    async def test_update_blinding_compliance(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/blinding-compliance/BC-012",
            json={
                "blinding_status": "confirmed_breach",
                "corrective_action": "Member recused",
                "reported_to_sponsor": True,
                "notes": "Confirmed after investigation",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["blinding_status"] == "confirmed_breach"
        assert data["corrective_action"] == "Member recused"
        assert data["reported_to_sponsor"] is True
        assert data["notes"] == "Confirmed after investigation"

    @pytest.mark.anyio
    async def test_update_blinding_compliance_impact(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/blinding-compliance/BC-008",
            json={"impact_assessment": "No significant impact on trial integrity"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["impact_assessment"] == "No significant impact on trial integrity"

    @pytest.mark.anyio
    async def test_update_blinding_compliance_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/blinding-compliance/BC-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_blinding_compliance(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/blinding-compliance/BC-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/blinding-compliance/BC-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_blinding_compliance_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/blinding-compliance/BC-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestEndpointAdjudicationMetrics:
    """Test endpoint adjudication committee metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_members"] == 12
        assert data["total_cases"] == 12
        assert data["total_adjudications"] == 12
        assert data["total_charters"] == 10
        assert data["total_blinding_records"] == 12

    @pytest.mark.anyio
    async def test_metrics_active_members(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["active_members"] > 0
        assert data["active_members"] <= data["total_members"]

    @pytest.mark.anyio
    async def test_metrics_members_by_role(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_role = data["members_by_role"]
        total = sum(by_role.values())
        assert total == data["total_members"]

    @pytest.mark.anyio
    async def test_metrics_cases_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["cases_by_status"]
        total = sum(by_status.values())
        assert total == data["total_cases"]

    @pytest.mark.anyio
    async def test_metrics_adjudications_by_outcome(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_outcome = data["adjudications_by_outcome"]
        total = sum(by_outcome.values())
        assert total == data["total_adjudications"]

    @pytest.mark.anyio
    async def test_metrics_unanimous_decisions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["unanimous_decisions"] > 0
        assert data["unanimous_decisions"] <= data["total_adjudications"]

    @pytest.mark.anyio
    async def test_metrics_charters_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["charters_by_status"]
        total = sum(by_status.values())
        assert total == data["total_charters"]

    @pytest.mark.anyio
    async def test_metrics_blinding_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["blinding_by_status"]
        total = sum(by_status.values())
        assert total == data["total_blinding_records"]

    @pytest.mark.anyio
    async def test_metrics_confirmed_breaches(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["confirmed_breaches"] >= 1
        assert data["confirmed_breaches"] <= data["total_blinding_records"]

    def test_metrics_via_service(self, svc: EndpointAdjudicationCommitteeService):
        metrics = svc.get_metrics()
        assert metrics.total_members == 12
        assert metrics.active_members > 0
        assert isinstance(metrics.members_by_role, dict)
        assert isinstance(metrics.cases_by_status, dict)


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_endpoint_adjudication_committee_service()
        svc2 = get_endpoint_adjudication_committee_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_endpoint_adjudication_committee_service()
        svc2 = reset_endpoint_adjudication_committee_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_endpoint_adjudication_committee_service()
        # Delete a member
        svc.delete_committee_member("CM-001")
        assert svc.get_committee_member("CM-001") is None
        # Reset should bring it back
        svc2 = reset_endpoint_adjudication_committee_service()
        assert svc2.get_committee_member("CM-001") is not None


# =====================================================================
# FILTERING AND EDGE CASES
# =====================================================================


class TestFilteringAndEdgeCases:
    """Test filtering combinations and edge cases."""

    @pytest.mark.anyio
    async def test_list_members_empty_filter(self, client: AsyncClient):
        """Filter by a trial that has no members."""
        resp = await client.get(
            f"{API_PREFIX}/committee-members",
            params={"trial_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.anyio
    async def test_list_cases_combined_filter(self, client: AsyncClient):
        """Filter by trial and status combined."""
        resp = await client.get(
            f"{API_PREFIX}/case-reviews",
            params={"trial_id": EYLEA_TRIAL, "status": "adjudicated"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["status"] == "adjudicated"

    @pytest.mark.anyio
    async def test_list_cases_empty_combined_filter(self, client: AsyncClient):
        """Filter by trial and status that produces no results."""
        resp = await client.get(
            f"{API_PREFIX}/case-reviews",
            params={"trial_id": EYLEA_TRIAL, "status": "deferred"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_create_member_then_retrieve(self, client: AsyncClient):
        """Create a member and verify it shows in the list."""
        payload = _make_committee_member_create()
        resp = await client.post(f"{API_PREFIX}/committee-members", json=payload)
        assert resp.status_code == 201
        created_id = resp.json()["id"]

        resp2 = await client.get(f"{API_PREFIX}/committee-members/{created_id}")
        assert resp2.status_code == 200
        assert resp2.json()["id"] == created_id

    @pytest.mark.anyio
    async def test_create_case_then_update_status(self, client: AsyncClient):
        """Create a case, then update its status through lifecycle."""
        payload = _make_case_review_create()
        resp = await client.post(f"{API_PREFIX}/case-reviews", json=payload)
        assert resp.status_code == 201
        case_id = resp.json()["id"]
        assert resp.json()["status"] == "pending_review"

        # Update to under_review
        resp2 = await client.put(
            f"{API_PREFIX}/case-reviews/{case_id}",
            json={"status": "under_review"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "under_review"

        # Update to adjudicated
        resp3 = await client.put(
            f"{API_PREFIX}/case-reviews/{case_id}",
            json={"status": "adjudicated", "documents_adequate": True},
        )
        assert resp3.status_code == 200
        assert resp3.json()["status"] == "adjudicated"
        assert resp3.json()["documents_adequate"] is True

    @pytest.mark.anyio
    async def test_create_and_delete_result(self, client: AsyncClient):
        """Create an adjudication result and then delete it."""
        payload = _make_adjudication_result_create()
        resp = await client.post(f"{API_PREFIX}/adjudication-results", json=payload)
        assert resp.status_code == 201
        result_id = resp.json()["id"]

        resp2 = await client.delete(f"{API_PREFIX}/adjudication-results/{result_id}")
        assert resp2.status_code == 204

        resp3 = await client.get(f"{API_PREFIX}/adjudication-results/{result_id}")
        assert resp3.status_code == 404

    @pytest.mark.anyio
    async def test_create_charter_then_approve(self, client: AsyncClient):
        """Create a charter in draft and update to approved."""
        payload = _make_charter_record_create()
        resp = await client.post(f"{API_PREFIX}/charter-records", json=payload)
        assert resp.status_code == 201
        charter_id = resp.json()["id"]
        assert resp.json()["status"] == "draft"

        # Update to approved
        resp2 = await client.put(
            f"{API_PREFIX}/charter-records/{charter_id}",
            json={"status": "approved", "approved_by": "Sponsor Medical Director"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "approved"
        assert resp2.json()["approved_by"] == "Sponsor Medical Director"

    @pytest.mark.anyio
    async def test_create_blinding_then_update_to_breach(self, client: AsyncClient):
        """Create a blinding record and escalate to confirmed breach."""
        payload = _make_blinding_compliance_create(blinding_status="potential_breach")
        resp = await client.post(f"{API_PREFIX}/blinding-compliance", json=payload)
        assert resp.status_code == 201
        compliance_id = resp.json()["id"]
        assert resp.json()["blinding_status"] == "potential_breach"

        # Escalate to confirmed breach
        resp2 = await client.put(
            f"{API_PREFIX}/blinding-compliance/{compliance_id}",
            json={
                "blinding_status": "confirmed_breach",
                "corrective_action": "Member recused from all future cases",
                "reported_to_sponsor": True,
            },
        )
        assert resp2.status_code == 200
        assert resp2.json()["blinding_status"] == "confirmed_breach"
        assert resp2.json()["reported_to_sponsor"] is True

    @pytest.mark.anyio
    async def test_members_sorted_by_appointment_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/committee-members")
        data = resp.json()
        dates = [item["appointment_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_cases_sorted_by_event_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/case-reviews")
        data = resp.json()
        dates = [item["event_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_results_sorted_by_adjudication_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjudication-results")
        data = resp.json()
        dates = [item["adjudication_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_metrics_after_create_and_delete(self, client: AsyncClient):
        """Metrics should reflect dynamic changes."""
        # Get baseline metrics
        resp1 = await client.get(f"{API_PREFIX}/metrics")
        baseline = resp1.json()

        # Create a new member
        payload = _make_committee_member_create()
        await client.post(f"{API_PREFIX}/committee-members", json=payload)

        resp2 = await client.get(f"{API_PREFIX}/metrics")
        after_create = resp2.json()
        assert after_create["total_members"] == baseline["total_members"] + 1

        # Delete a member
        await client.delete(f"{API_PREFIX}/committee-members/CM-012")
        resp3 = await client.get(f"{API_PREFIX}/metrics")
        after_delete = resp3.json()
        assert after_delete["total_members"] == baseline["total_members"]

    @pytest.mark.anyio
    async def test_adjudication_results_filter_reclassified(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/adjudication-results", params={"outcome": "reclassified"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["outcome"] == "reclassified"

    @pytest.mark.anyio
    async def test_adjudication_results_filter_split_decision(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/adjudication-results", params={"outcome": "split_decision"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["outcome"] == "split_decision"

    @pytest.mark.anyio
    async def test_blinding_filter_under_investigation(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/blinding-compliance", params={"blinding_status": "under_investigation"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["blinding_status"] == "under_investigation"

    @pytest.mark.anyio
    async def test_blinding_filter_not_applicable(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/blinding-compliance", params={"blinding_status": "not_applicable"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["blinding_status"] == "not_applicable"


# =====================================================================
# ENUM COVERAGE
# =====================================================================


class TestEnumCoverage:
    """Verify enum values are represented in seed data."""

    @pytest.mark.anyio
    async def test_member_roles_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/committee-members")
        data = resp.json()
        roles = {item["role"] for item in data["items"]}
        assert "chair" in roles
        assert "voting_member" in roles
        assert "alternate" in roles
        assert "non_voting_advisor" in roles
        assert "statistician" in roles
        assert "coordinator" in roles

    @pytest.mark.anyio
    async def test_case_statuses_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/case-reviews")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "pending_review" in statuses
        assert "under_review" in statuses
        assert "adjudicated" in statuses
        assert "deferred" in statuses
        assert "returned_for_info" in statuses
        assert "closed" in statuses

    @pytest.mark.anyio
    async def test_adjudication_outcomes_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjudication-results")
        data = resp.json()
        outcomes = {item["outcome"] for item in data["items"]}
        assert "confirmed" in outcomes
        assert "not_confirmed" in outcomes
        assert "indeterminate" in outcomes
        assert "reclassified" in outcomes
        assert "split_decision" in outcomes

    @pytest.mark.anyio
    async def test_charter_statuses_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/charter-records")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "draft" in statuses
        assert "under_review" in statuses
        assert "approved" in statuses
        assert "amended" in statuses
        assert "superseded" in statuses

    @pytest.mark.anyio
    async def test_blinding_statuses_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/blinding-compliance")
        data = resp.json()
        statuses = {item["blinding_status"] for item in data["items"]}
        assert "maintained" in statuses
        assert "potential_breach" in statuses
        assert "confirmed_breach" in statuses
        assert "not_applicable" in statuses
        assert "under_investigation" in statuses

    @pytest.mark.anyio
    async def test_seed_has_unanimous_and_non_unanimous(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjudication-results")
        data = resp.json()
        unanimous_values = {item["unanimous"] for item in data["items"]}
        assert True in unanimous_values
        assert False in unanimous_values

    @pytest.mark.anyio
    async def test_seed_has_finalized_and_non_finalized(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjudication-results")
        data = resp.json()
        finalized_values = {item["finalized"] for item in data["items"]}
        assert True in finalized_values
        assert False in finalized_values

    @pytest.mark.anyio
    async def test_seed_has_dissenting_opinions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjudication-results")
        data = resp.json()
        has_dissent = any(
            len(item["dissenting_opinions"]) > 0 for item in data["items"]
        )
        assert has_dissent

    @pytest.mark.anyio
    async def test_seed_charters_have_endpoint_definitions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/charter-records")
        data = resp.json()
        for item in data["items"]:
            assert len(item["endpoint_definitions"]) >= 1

    @pytest.mark.anyio
    async def test_seed_blinding_has_reported_to_irb(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/blinding-compliance")
        data = resp.json()
        irb_reported = any(item["reported_to_irb"] for item in data["items"])
        assert irb_reported
