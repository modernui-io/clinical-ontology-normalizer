"""Tests for Clinical Endpoint Adjudication Committee (CEAC) Management (CLINICAL-20).

Covers:
- Seed data verification (committees, members, events, assessments, meetings)
- Committee CRUD (create, read, update, delete, list, filter by trial)
- Member management (add, update, remove, list, filter by role/committee)
- Event CRUD (create, read, update, list, filter by trial/status/type/classification)
- Reviewer assignment (dual-reviewer, validation)
- Event adjudication (consensus, disagreement, tiebreaker)
- Reviewer assessments (submit, list, filter by event/reviewer)
- Blinded review workflow (redacted patient ID, filtered documents)
- Consensus tracking (events requiring consensus)
- Inter-rater agreement (Cohen's kappa calculation)
- Turnaround time tracking
- Disagreement rate calculation
- Committee meetings (create, list, filter)
- Adjudication metrics computation
- Error handling (404s, 400s, invalid operations)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.endpoint_adjudication import (
    AdjudicationStatus,
    AdjudicatorRole,
    AssessmentCreate,
    BlindingStatus,
    CommitteeCreate,
    CommitteeUpdate,
    ConfidenceLevel,
    EndpointType,
    EventClassification,
    EventCreate,
    EventUpdate,
    MeetingCreate,
    MemberCreate,
    MemberUpdate,
)
from app.services.endpoint_adjudication_service import (
    AdjudicationService,
    get_adjudication_service,
    reset_adjudication_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/endpoint-adjudication"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_adjudication_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> AdjudicationService:
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


def _make_committee_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "name": "Test Adjudication Committee",
        "charter_version": "1.0",
        "blinding_status": "blinded",
        "meeting_frequency": "monthly",
    }
    defaults.update(overrides)
    return defaults


def _make_event_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "patient_id": "PT-9999",
        "event_type": "primary",
        "event_date": (now - timedelta(days=5)).isoformat(),
        "reported_by_site": "SITE-101",
        "source_documents": ["DOC-001", "DOC-002"],
    }
    defaults.update(overrides)
    return defaults


def _make_assessment_create(**overrides) -> dict:
    defaults = {
        "event_id": "AEV-007",
        "reviewer_id": "MBR-002",
        "classification": "confirmed",
        "confidence_level": "high",
        "rationale": "Clear evidence supporting endpoint confirmation.",
    }
    defaults.update(overrides)
    return defaults


def _make_member_create(**overrides) -> dict:
    defaults = {
        "name": "Dr. Test Member",
        "specialty": "Cardiology",
        "institution": "Test Hospital",
        "role": "primary_reviewer",
        "conflict_of_interest_disclosed": True,
        "training_completed": True,
    }
    defaults.update(overrides)
    return defaults


def _make_meeting_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "committee_id": "CEAC-001",
        "meeting_date": now.isoformat(),
        "events_reviewed": ["AEV-007", "AEV-008"],
        "events_adjudicated": 2,
        "disagreements_resolved": 0,
        "minutes_summary": "Routine meeting. All events reviewed.",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_committees_count(self, svc: AdjudicationService):
        committees = svc.list_committees()
        assert len(committees) == 3

    def test_seed_committees_one_per_trial(self, svc: AdjudicationService):
        trials = {c.trial_id for c in svc.list_committees()}
        assert EYLEA_TRIAL in trials
        assert DUPIXENT_TRIAL in trials
        assert LIBTAYO_TRIAL in trials

    def test_seed_members_count(self, svc: AdjudicationService):
        members = svc.list_members()
        assert len(members) == 15

    def test_seed_members_roles_present(self, svc: AdjudicationService):
        members = svc.list_members()
        roles = {m.role for m in members}
        assert AdjudicatorRole.CHAIR in roles
        assert AdjudicatorRole.PRIMARY_REVIEWER in roles
        assert AdjudicatorRole.SECONDARY_REVIEWER in roles
        assert AdjudicatorRole.TIEBREAKER in roles

    def test_seed_events_count(self, svc: AdjudicationService):
        events = svc.list_events()
        assert len(events) == 30

    def test_seed_events_all_statuses_present(self, svc: AdjudicationService):
        events = svc.list_events()
        statuses = {e.status for e in events}
        assert AdjudicationStatus.PENDING in statuses
        assert AdjudicationStatus.IN_REVIEW in statuses
        assert AdjudicationStatus.ADJUDICATED in statuses
        assert AdjudicationStatus.FINAL in statuses
        assert AdjudicationStatus.APPEALED in statuses

    def test_seed_assessments_count(self, svc: AdjudicationService):
        assessments = svc.list_assessments()
        assert len(assessments) == 40

    def test_seed_meetings_count(self, svc: AdjudicationService):
        meetings = svc.list_meetings()
        assert len(meetings) == 5

    def test_seed_committee_has_members(self, svc: AdjudicationService):
        committee = svc.get_committee("CEAC-001")
        assert committee is not None
        assert len(committee.members) == 5

    def test_seed_eylea_committee_blinded(self, svc: AdjudicationService):
        committee = svc.get_committee("CEAC-001")
        assert committee is not None
        assert committee.blinding_status == BlindingStatus.BLINDED

    def test_seed_libtayo_committee_partially_unblinded(self, svc: AdjudicationService):
        committee = svc.get_committee("CEAC-003")
        assert committee is not None
        assert committee.blinding_status == BlindingStatus.PARTIALLY_UNBLINDED


# =====================================================================
# COMMITTEE CRUD
# =====================================================================


class TestCommitteeCrud:
    """Test committee create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_committees(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/committees")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    @pytest.mark.anyio
    async def test_list_committees_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/committees", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_committee(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/committees/CEAC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CEAC-001"
        assert "EYLEA" in data["name"] or "BCVA" in data["name"]

    @pytest.mark.anyio
    async def test_get_committee_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/committees/CEAC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_committee(self, client: AsyncClient):
        payload = _make_committee_create()
        resp = await client.post(f"{API_PREFIX}/committees", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Adjudication Committee"
        assert data["id"].startswith("CEAC-")

    @pytest.mark.anyio
    async def test_update_committee(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/committees/CEAC-001",
            json={"charter_version": "3.0", "meeting_frequency": "weekly"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["charter_version"] == "3.0"
        assert data["meeting_frequency"] == "weekly"

    @pytest.mark.anyio
    async def test_update_committee_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/committees/CEAC-NONEXISTENT",
            json={"name": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_committee(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/committees/CEAC-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/committees/CEAC-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_committee_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/committees/CEAC-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# MEMBER MANAGEMENT
# =====================================================================


class TestMemberManagement:
    """Test committee member management operations."""

    @pytest.mark.anyio
    async def test_list_members(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/members")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15

    @pytest.mark.anyio
    async def test_list_members_filter_committee(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/members", params={"committee_id": "CEAC-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_list_members_filter_role(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/members", params={"role": "chair"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["role"] == "chair"

    @pytest.mark.anyio
    async def test_get_member(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/members/MBR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "MBR-001"
        assert data["name"] == "Dr. Elizabeth Chen"

    @pytest.mark.anyio
    async def test_get_member_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/members/MBR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_add_member_to_committee(self, client: AsyncClient):
        payload = _make_member_create()
        resp = await client.post(f"{API_PREFIX}/committees/CEAC-001/members", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Dr. Test Member"
        assert data["id"].startswith("MBR-")

    @pytest.mark.anyio
    async def test_add_member_to_nonexistent_committee(self, client: AsyncClient):
        payload = _make_member_create()
        resp = await client.post(f"{API_PREFIX}/committees/CEAC-NONEXISTENT/members", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_member(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/members/MBR-015",
            json={"training_completed": True, "conflict_of_interest_disclosed": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["training_completed"] is True
        assert data["conflict_of_interest_disclosed"] is True

    @pytest.mark.anyio
    async def test_update_member_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/members/MBR-NONEXISTENT",
            json={"training_completed": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_remove_member_from_committee(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/committees/CEAC-001/members/MBR-001")
        assert resp.status_code == 204
        # Verify committee has one fewer member
        resp2 = await client.get(f"{API_PREFIX}/committees/CEAC-001")
        data = resp2.json()
        member_ids = [m["id"] for m in data["members"]]
        assert "MBR-001" not in member_ids

    @pytest.mark.anyio
    async def test_remove_member_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/committees/CEAC-001/members/MBR-NONEXISTENT")
        assert resp.status_code == 404

    def test_members_have_required_fields(self, svc: AdjudicationService):
        members = svc.list_members()
        for m in members:
            assert m.id
            assert m.name
            assert m.specialty
            assert m.institution
            assert m.role is not None


# =====================================================================
# EVENT CRUD
# =====================================================================


class TestEventCrud:
    """Test adjudication event CRUD operations."""

    @pytest.mark.anyio
    async def test_list_events(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/events")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 30

    @pytest.mark.anyio
    async def test_list_events_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/events", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_events_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/events", params={"status": "pending"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "pending"

    @pytest.mark.anyio
    async def test_list_events_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/events", params={"event_type": "primary"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["event_type"] == "primary"

    @pytest.mark.anyio
    async def test_list_events_filter_classification(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/events", params={"classification": "confirmed"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["classification"] == "confirmed"

    @pytest.mark.anyio
    async def test_get_event(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/events/AEV-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "AEV-001"
        assert data["status"] == "final"

    @pytest.mark.anyio
    async def test_get_event_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/events/AEV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_event(self, client: AsyncClient):
        payload = _make_event_create()
        resp = await client.post(f"{API_PREFIX}/events", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_id"] == "PT-9999"
        assert data["status"] == "pending"
        assert data["id"].startswith("AEV-")

    @pytest.mark.anyio
    async def test_update_event(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/events/AEV-006",
            json={"status": "final"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "final"

    @pytest.mark.anyio
    async def test_update_event_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/events/AEV-NONEXISTENT",
            json={"status": "final"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_event_set_classification_auto_date(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/events/AEV-007",
            json={"classification": "confirmed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["classification"] == "confirmed"
        assert data["classification_date"] is not None

    @pytest.mark.anyio
    async def test_events_sorted_by_date_descending(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/events")
        data = resp.json()
        dates = [item["event_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)


# =====================================================================
# REVIEWER ASSIGNMENT
# =====================================================================


class TestReviewerAssignment:
    """Test dual-reviewer assignment."""

    @pytest.mark.anyio
    async def test_assign_reviewers(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/events/AEV-009/assign-reviewers",
            json=["MBR-002", "MBR-003"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_review"
        assert "MBR-002" in data["assigned_reviewers"]
        assert "MBR-003" in data["assigned_reviewers"]

    @pytest.mark.anyio
    async def test_assign_reviewers_not_found_event(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/events/AEV-NONEXISTENT/assign-reviewers",
            json=["MBR-002", "MBR-003"],
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_assign_reviewers_invalid_reviewer(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/events/AEV-009/assign-reviewers",
            json=["MBR-002", "MBR-INVALID"],
        )
        assert resp.status_code == 400

    def test_assign_reviewers_service(self, svc: AdjudicationService):
        result = svc.assign_reviewers("AEV-010", ["MBR-002", "MBR-005"])
        assert result is not None
        assert result.status == AdjudicationStatus.IN_REVIEW
        assert len(result.assigned_reviewers) == 2


# =====================================================================
# EVENT ADJUDICATION
# =====================================================================


class TestEventAdjudication:
    """Test event adjudication with dual-reviewer and tiebreaker logic."""

    @pytest.mark.anyio
    async def test_adjudicate_event_consensus(self, client: AsyncClient):
        """AEV-001 has two agreeing assessments -> should adjudicate."""
        # AEV-001 already has ASS-001 (confirmed) and ASS-002 (confirmed) and is FINAL
        # Use AEV-004 which has ASS-008 and ASS-009 both confirmed, currently FINAL
        # Need to test with an in_review event - use AEV-007
        # First submit two agreeing assessments
        svc = get_adjudication_service()
        svc.submit_assessment(AssessmentCreate(
            event_id="AEV-007",
            reviewer_id="MBR-002",
            classification=EventClassification.CONFIRMED,
            confidence_level=ConfidenceLevel.HIGH,
            rationale="Test assessment 1",
        ))
        svc.submit_assessment(AssessmentCreate(
            event_id="AEV-007",
            reviewer_id="MBR-003",
            classification=EventClassification.CONFIRMED,
            confidence_level=ConfidenceLevel.HIGH,
            rationale="Test assessment 2",
        ))
        resp = await client.post(f"{API_PREFIX}/events/AEV-007/adjudicate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "adjudicated"
        assert data["classification"] == "confirmed"
        assert data["consensus_required"] is False

    @pytest.mark.anyio
    async def test_adjudicate_event_disagreement_needs_tiebreaker(self, client: AsyncClient):
        """Event with two disagreeing assessments should flag consensus required."""
        svc = get_adjudication_service()
        svc.submit_assessment(AssessmentCreate(
            event_id="AEV-008",
            reviewer_id="MBR-005",
            classification=EventClassification.CONFIRMED,
            confidence_level=ConfidenceLevel.HIGH,
            rationale="Endpoint met",
        ))
        svc.submit_assessment(AssessmentCreate(
            event_id="AEV-008",
            reviewer_id="MBR-002",
            classification=EventClassification.NOT_CONFIRMED,
            confidence_level=ConfidenceLevel.MEDIUM,
            rationale="Insufficient evidence",
        ))
        resp = await client.post(f"{API_PREFIX}/events/AEV-008/adjudicate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["consensus_required"] is True

    @pytest.mark.anyio
    async def test_adjudicate_event_tiebreaker_resolves(self, client: AsyncClient):
        """Event with three assessments (2+1 tiebreaker) should adjudicate by majority."""
        svc = get_adjudication_service()
        svc.submit_assessment(AssessmentCreate(
            event_id="AEV-008",
            reviewer_id="MBR-005",
            classification=EventClassification.CONFIRMED,
            confidence_level=ConfidenceLevel.HIGH,
            rationale="Endpoint met",
        ))
        svc.submit_assessment(AssessmentCreate(
            event_id="AEV-008",
            reviewer_id="MBR-002",
            classification=EventClassification.NOT_CONFIRMED,
            confidence_level=ConfidenceLevel.MEDIUM,
            rationale="Insufficient evidence",
        ))
        svc.submit_assessment(AssessmentCreate(
            event_id="AEV-008",
            reviewer_id="MBR-004",
            classification=EventClassification.CONFIRMED,
            confidence_level=ConfidenceLevel.HIGH,
            rationale="Tiebreaker: agree with confirmed",
        ))
        resp = await client.post(f"{API_PREFIX}/events/AEV-008/adjudicate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "adjudicated"
        assert data["classification"] == "confirmed"
        assert data["consensus_required"] is True

    @pytest.mark.anyio
    async def test_adjudicate_event_insufficient_assessments(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/events/AEV-009/adjudicate")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_adjudicate_already_adjudicated(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/events/AEV-001/adjudicate")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_adjudicate_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/events/AEV-NONEXISTENT/adjudicate")
        assert resp.status_code == 404


# =====================================================================
# REVIEWER ASSESSMENTS
# =====================================================================


class TestReviewerAssessments:
    """Test reviewer assessment operations."""

    @pytest.mark.anyio
    async def test_list_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 40

    @pytest.mark.anyio
    async def test_list_assessments_filter_event(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments", params={"event_id": "AEV-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["event_id"] == "AEV-001"

    @pytest.mark.anyio
    async def test_list_assessments_filter_reviewer(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments", params={"reviewer_id": "MBR-002"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["reviewer_id"] == "MBR-002"

    @pytest.mark.anyio
    async def test_get_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/ASS-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ASS-001"
        assert data["classification"] == "confirmed"

    @pytest.mark.anyio
    async def test_get_assessment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/ASS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_submit_assessment(self, client: AsyncClient):
        payload = _make_assessment_create()
        resp = await client.post(f"{API_PREFIX}/assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["event_id"] == "AEV-007"
        assert data["classification"] == "confirmed"
        assert data["id"].startswith("ASS-")

    @pytest.mark.anyio
    async def test_submit_assessment_invalid_event(self, client: AsyncClient):
        payload = _make_assessment_create(event_id="AEV-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/assessments", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_submit_assessment_invalid_reviewer(self, client: AsyncClient):
        payload = _make_assessment_create(reviewer_id="MBR-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/assessments", json=payload)
        assert resp.status_code == 400

    def test_assessment_has_all_fields(self, svc: AdjudicationService):
        assessment = svc.get_assessment("ASS-001")
        assert assessment is not None
        assert assessment.event_id == "AEV-001"
        assert assessment.reviewer_id == "MBR-002"
        assert assessment.classification == EventClassification.CONFIRMED
        assert assessment.confidence_level == ConfidenceLevel.HIGH
        assert assessment.rationale
        assert assessment.reviewed_date is not None


# =====================================================================
# BLINDED REVIEW WORKFLOW
# =====================================================================


class TestBlindedReview:
    """Test blinded review workflow."""

    @pytest.mark.anyio
    async def test_get_blinded_event(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/events/AEV-001/blinded")
        assert resp.status_code == 200
        data = resp.json()
        assert data["patient_id"].startswith("BLINDED-")
        assert "1001" in data["patient_id"]

    @pytest.mark.anyio
    async def test_get_blinded_event_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/events/AEV-NONEXISTENT/blinded")
        assert resp.status_code == 404

    def test_blinded_event_redacts_patient_id(self, svc: AdjudicationService):
        blinded = svc.get_blinded_event("AEV-001")
        assert blinded is not None
        assert "PT-1001" not in blinded["patient_id"]
        assert blinded["patient_id"].startswith("BLINDED-")

    def test_blinded_event_filters_treatment_docs(self, svc: AdjudicationService):
        blinded = svc.get_blinded_event("AEV-001")
        assert blinded is not None
        for doc in blinded["source_documents"]:
            assert "treatment" not in doc.lower()
            assert "arm" not in doc.lower()


# =====================================================================
# CONSENSUS TRACKING
# =====================================================================


class TestConsensusTracking:
    """Test consensus requirement tracking."""

    @pytest.mark.anyio
    async def test_get_events_requiring_consensus(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/events/consensus-required")
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["consensus_required"] is True

    @pytest.mark.anyio
    async def test_consensus_events_filter_by_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/events/consensus-required",
            params={"trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["consensus_required"] is True

    def test_consensus_events_count(self, svc: AdjudicationService):
        events = svc.get_events_requiring_consensus()
        assert len(events) > 0
        for e in events:
            assert e.consensus_required is True


# =====================================================================
# INTER-RATER AGREEMENT (COHEN'S KAPPA)
# =====================================================================


class TestInterRaterAgreement:
    """Test Cohen's kappa calculation for inter-rater agreement."""

    def test_kappa_overall(self, svc: AdjudicationService):
        kappa = svc.calculate_inter_rater_agreement()
        # Kappa should be between -1 and 1
        assert -1.0 <= kappa <= 1.0

    def test_kappa_by_trial(self, svc: AdjudicationService):
        kappa_eylea = svc.calculate_inter_rater_agreement(trial_id=EYLEA_TRIAL)
        kappa_dupixent = svc.calculate_inter_rater_agreement(trial_id=DUPIXENT_TRIAL)
        kappa_libtayo = svc.calculate_inter_rater_agreement(trial_id=LIBTAYO_TRIAL)
        assert -1.0 <= kappa_eylea <= 1.0
        assert -1.0 <= kappa_dupixent <= 1.0
        assert -1.0 <= kappa_libtayo <= 1.0

    def test_kappa_perfect_agreement(self, svc: AdjudicationService):
        """Test kappa with perfect agreement."""
        kappa = svc._cohens_kappa(
            ["confirmed", "confirmed", "confirmed"],
            ["confirmed", "confirmed", "confirmed"],
        )
        assert kappa == 1.0

    def test_kappa_no_agreement(self, svc: AdjudicationService):
        """Test kappa with no agreement."""
        kappa = svc._cohens_kappa(
            ["confirmed", "not_confirmed", "confirmed", "not_confirmed"],
            ["not_confirmed", "confirmed", "not_confirmed", "confirmed"],
        )
        assert kappa < 0

    def test_kappa_moderate_agreement(self, svc: AdjudicationService):
        """Test kappa with partial agreement."""
        kappa = svc._cohens_kappa(
            ["confirmed", "confirmed", "not_confirmed", "confirmed"],
            ["confirmed", "not_confirmed", "not_confirmed", "confirmed"],
        )
        assert 0.0 < kappa < 1.0

    def test_kappa_empty_ratings(self, svc: AdjudicationService):
        kappa = svc._cohens_kappa([], [])
        assert kappa == 0.0

    def test_kappa_single_category(self, svc: AdjudicationService):
        kappa = svc._cohens_kappa(
            ["confirmed", "confirmed"],
            ["confirmed", "confirmed"],
        )
        assert kappa == 1.0


# =====================================================================
# TURNAROUND TIME
# =====================================================================


class TestTurnaroundTime:
    """Test turnaround time calculation."""

    def test_avg_turnaround_overall(self, svc: AdjudicationService):
        avg = svc.calculate_avg_turnaround_days()
        assert avg > 0
        assert avg < 60  # Should be reasonable

    def test_avg_turnaround_by_trial(self, svc: AdjudicationService):
        avg = svc.calculate_avg_turnaround_days(trial_id=EYLEA_TRIAL)
        assert avg > 0

    def test_avg_turnaround_no_events(self, svc: AdjudicationService):
        avg = svc.calculate_avg_turnaround_days(trial_id="NONEXISTENT")
        assert avg == 0.0


# =====================================================================
# DISAGREEMENT RATE
# =====================================================================


class TestDisagreementRate:
    """Test disagreement rate calculation."""

    def test_disagreement_rate_overall(self, svc: AdjudicationService):
        rate = svc.calculate_disagreement_rate()
        assert 0.0 <= rate <= 100.0

    def test_disagreement_rate_by_trial(self, svc: AdjudicationService):
        rate = svc.calculate_disagreement_rate(trial_id=LIBTAYO_TRIAL)
        assert 0.0 <= rate <= 100.0

    def test_disagreement_rate_no_events(self, svc: AdjudicationService):
        rate = svc.calculate_disagreement_rate(trial_id="NONEXISTENT")
        assert rate == 0.0

    def test_disagreement_rate_reflects_consensus_required(self, svc: AdjudicationService):
        """Events with consensus_required should count as disagreements."""
        events = svc.list_events()
        adjudicated = [
            e for e in events
            if e.status in (
                AdjudicationStatus.ADJUDICATED,
                AdjudicationStatus.FINAL,
                AdjudicationStatus.APPEALED,
            )
        ]
        if adjudicated:
            disagreements = sum(1 for e in adjudicated if e.consensus_required)
            expected_rate = round(disagreements / len(adjudicated) * 100.0, 1)
            actual_rate = svc.calculate_disagreement_rate()
            assert abs(actual_rate - expected_rate) < 0.2


# =====================================================================
# MEETINGS
# =====================================================================


class TestMeetings:
    """Test committee meeting operations."""

    @pytest.mark.anyio
    async def test_list_meetings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meetings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_list_meetings_filter_committee(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meetings", params={"committee_id": "CEAC-001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["committee_id"] == "CEAC-001"

    @pytest.mark.anyio
    async def test_get_meeting(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meetings/MTG-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "MTG-001"
        assert data["events_adjudicated"] == 5

    @pytest.mark.anyio
    async def test_get_meeting_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meetings/MTG-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_meeting(self, client: AsyncClient):
        payload = _make_meeting_create()
        resp = await client.post(f"{API_PREFIX}/meetings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["committee_id"] == "CEAC-001"
        assert data["id"].startswith("MTG-")

    def test_meeting_has_minutes(self, svc: AdjudicationService):
        meeting = svc.get_meeting("MTG-001")
        assert meeting is not None
        assert meeting.minutes_summary
        assert len(meeting.minutes_summary) > 10

    def test_meeting_events_reviewed_list(self, svc: AdjudicationService):
        meeting = svc.get_meeting("MTG-005")
        assert meeting is not None
        assert len(meeting.events_reviewed) == 6
        assert meeting.disagreements_resolved == 2


# =====================================================================
# METRICS
# =====================================================================


class TestAdjudicationMetrics:
    """Test adjudication metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_events"] == 30
        assert data["events_pending"] > 0
        assert -1.0 <= data["inter_rater_agreement_kappa"] <= 1.0
        assert data["avg_adjudication_days"] > 0
        assert 0.0 <= data["disagreement_rate"] <= 100.0

    @pytest.mark.anyio
    async def test_get_metrics_by_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_events"] == 10

    def test_metrics_events_by_status(self, svc: AdjudicationService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.events_by_status.values())
        assert total_by_status == metrics.total_events

    def test_metrics_events_by_classification(self, svc: AdjudicationService):
        metrics = svc.get_metrics()
        # Not all events have classifications (pending/in_review don't)
        classified_count = sum(metrics.events_by_classification.values())
        total_classified = sum(
            1 for e in svc.list_events() if e.classification is not None
        )
        assert classified_count == total_classified

    def test_metrics_pending_count(self, svc: AdjudicationService):
        metrics = svc.get_metrics()
        pending = [
            e for e in svc.list_events()
            if e.status in (AdjudicationStatus.PENDING, AdjudicationStatus.IN_REVIEW)
        ]
        assert metrics.events_pending == len(pending)

    def test_metrics_kappa_matches_direct_calculation(self, svc: AdjudicationService):
        metrics = svc.get_metrics()
        direct_kappa = svc.calculate_inter_rater_agreement()
        assert abs(metrics.inter_rater_agreement_kappa - direct_kappa) < 0.001


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_adjudication_service()
        svc2 = get_adjudication_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_adjudication_service()
        svc2 = reset_adjudication_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_adjudication_service()
        svc.delete_committee("CEAC-001")
        assert svc.get_committee("CEAC-001") is None
        svc2 = reset_adjudication_service()
        assert svc2.get_committee("CEAC-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_committees_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/committees")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_events_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/events")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_assessments_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_meetings_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meetings")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_members_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/members")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_committee_with_all_fields(self, client: AsyncClient):
        payload = _make_committee_create(
            blinding_status="unblinded",
            meeting_frequency="weekly",
        )
        resp = await client.post(f"{API_PREFIX}/committees", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["blinding_status"] == "unblinded"
        assert data["meeting_frequency"] == "weekly"

    @pytest.mark.anyio
    async def test_create_event_all_endpoint_types(self, client: AsyncClient):
        for et in ["primary", "secondary", "exploratory", "safety", "composite"]:
            payload = _make_event_create(event_type=et, patient_id=f"PT-{et}")
            resp = await client.post(f"{API_PREFIX}/events", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["event_type"] == et

    @pytest.mark.anyio
    async def test_submit_assessment_all_confidence_levels(self, client: AsyncClient):
        for level in ["high", "medium", "low"]:
            payload = _make_assessment_create(
                confidence_level=level,
                reviewer_id="MBR-003" if level != "high" else "MBR-002",
            )
            resp = await client.post(f"{API_PREFIX}/assessments", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["confidence_level"] == level

    @pytest.mark.anyio
    async def test_submit_assessment_all_classifications(self, client: AsyncClient):
        for cls in ["confirmed", "not_confirmed", "indeterminate", "missing_data"]:
            payload = _make_assessment_create(
                classification=cls,
                reviewer_id="MBR-005",
            )
            resp = await client.post(f"{API_PREFIX}/assessments", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["classification"] == cls

    @pytest.mark.anyio
    async def test_list_members_nonexistent_committee(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/members", params={"committee_id": "CEAC-NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_metrics_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_events"] == 0

    @pytest.mark.anyio
    async def test_event_create_with_source_documents(self, client: AsyncClient):
        payload = _make_event_create(
            source_documents=["CT-SCAN-001", "MRI-002", "LAB-003"],
        )
        resp = await client.post(f"{API_PREFIX}/events", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["source_documents"]) == 3

    @pytest.mark.anyio
    async def test_event_create_minimal(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = {
            "trial_id": EYLEA_TRIAL,
            "patient_id": "PT-MINIMAL",
            "event_type": "primary",
            "event_date": now.isoformat(),
            "reported_by_site": "SITE-101",
        }
        resp = await client.post(f"{API_PREFIX}/events", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["source_documents"] == []
        assert data["assigned_reviewers"] == []


# =====================================================================
# ENDPOINT TYPE ENUMERATION
# =====================================================================


class TestEnumerations:
    """Test enum values are correctly used throughout the system."""

    @pytest.mark.anyio
    async def test_all_endpoint_types_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/events")
        data = resp.json()
        types = {item["event_type"] for item in data["items"]}
        assert "primary" in types
        assert "secondary" in types
        assert "safety" in types

    @pytest.mark.anyio
    async def test_all_statuses_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/events")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "pending" in statuses
        assert "in_review" in statuses
        assert "adjudicated" in statuses
        assert "final" in statuses
        assert "appealed" in statuses

    @pytest.mark.anyio
    async def test_all_roles_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/members")
        data = resp.json()
        roles = {item["role"] for item in data["items"]}
        assert "chair" in roles
        assert "primary_reviewer" in roles
        assert "secondary_reviewer" in roles
        assert "tiebreaker" in roles

    @pytest.mark.anyio
    async def test_classifications_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/events", params={"status": "final"})
        data = resp.json()
        classifications = {item["classification"] for item in data["items"] if item["classification"]}
        assert "confirmed" in classifications
        assert "not_confirmed" in classifications

    @pytest.mark.anyio
    async def test_confidence_levels_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        data = resp.json()
        levels = {item["confidence_level"] for item in data["items"]}
        assert "high" in levels
        assert "medium" in levels
        assert "low" in levels

    @pytest.mark.anyio
    async def test_blinding_statuses_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/committees")
        data = resp.json()
        blinding = {item["blinding_status"] for item in data["items"]}
        assert "blinded" in blinding
        assert "partially_unblinded" in blinding


# =====================================================================
# DETAILED DATA VALIDATION
# =====================================================================


class TestDataValidation:
    """Test detailed data validation across the system."""

    @pytest.mark.anyio
    async def test_committee_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/committees/CEAC-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "name" in data
        assert "charter_version" in data
        assert "members" in data
        assert "blinding_status" in data
        assert "meeting_frequency" in data

    @pytest.mark.anyio
    async def test_event_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/events/AEV-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "patient_id" in data
        assert "event_type" in data
        assert "event_date" in data
        assert "reported_by_site" in data
        assert "source_documents" in data
        assert "status" in data
        assert "assigned_reviewers" in data

    @pytest.mark.anyio
    async def test_assessment_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/ASS-001")
        data = resp.json()
        assert "id" in data
        assert "event_id" in data
        assert "reviewer_id" in data
        assert "classification" in data
        assert "confidence_level" in data
        assert "rationale" in data
        assert "reviewed_date" in data

    @pytest.mark.anyio
    async def test_meeting_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meetings/MTG-001")
        data = resp.json()
        assert "id" in data
        assert "committee_id" in data
        assert "meeting_date" in data
        assert "events_reviewed" in data
        assert "events_adjudicated" in data
        assert "disagreements_resolved" in data
        assert "minutes_summary" in data

    @pytest.mark.anyio
    async def test_metrics_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "total_events" in data
        assert "events_by_status" in data
        assert "events_by_classification" in data
        assert "inter_rater_agreement_kappa" in data
        assert "avg_adjudication_days" in data
        assert "disagreement_rate" in data
        assert "events_pending" in data

    def test_final_events_have_classification(self, svc: AdjudicationService):
        events = svc.list_events(status=AdjudicationStatus.FINAL)
        for e in events:
            assert e.classification is not None
            assert e.classification_date is not None

    def test_pending_events_have_no_classification(self, svc: AdjudicationService):
        events = svc.list_events(status=AdjudicationStatus.PENDING)
        for e in events:
            assert e.classification is None
            assert len(e.assigned_reviewers) == 0

    def test_in_review_events_have_reviewers(self, svc: AdjudicationService):
        events = svc.list_events(status=AdjudicationStatus.IN_REVIEW)
        for e in events:
            assert len(e.assigned_reviewers) >= 2

    def test_each_committee_has_five_members(self, svc: AdjudicationService):
        for cid in ["CEAC-001", "CEAC-002", "CEAC-003"]:
            committee = svc.get_committee(cid)
            assert committee is not None
            assert len(committee.members) == 5

    def test_eylea_events_count(self, svc: AdjudicationService):
        events = svc.list_events(trial_id=EYLEA_TRIAL)
        assert len(events) == 10

    def test_dupixent_events_count(self, svc: AdjudicationService):
        events = svc.list_events(trial_id=DUPIXENT_TRIAL)
        assert len(events) == 10

    def test_libtayo_events_count(self, svc: AdjudicationService):
        events = svc.list_events(trial_id=LIBTAYO_TRIAL)
        assert len(events) == 10

    def test_appealed_event_has_classification(self, svc: AdjudicationService):
        events = svc.list_events(status=AdjudicationStatus.APPEALED)
        assert len(events) > 0
        for e in events:
            assert e.classification is not None
