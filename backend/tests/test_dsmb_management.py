"""Tests for DSMB (Data Safety Monitoring Board) Management.

Covers:
- Seed data verification (charters, members, meetings, safety reviews, recommendations,
  unblinding requests)
- Charter CRUD (create, read, update, delete, list, filter by trial)
- Member CRUD (create, read, update, delete, list, filter by charter/role/active)
- Meeting CRUD and lifecycle (schedule, update, complete, cancel)
- Meeting quorum validation (role-based quorum checks)
- Safety review CRUD and workflow (create, update, filter by meeting)
- Recommendation CRUD and voting (record, update sponsor communication, filter)
- Unblinding request workflow (create, approve, deny, complete, filter)
- Metrics computation
- Error handling (404s, 400s, invalid operations)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.dsmb_management import (
    DSMBCharterCreate,
    DSMBCharterUpdate,
    DSMBMeetingCreate,
    DSMBMeetingUpdate,
    DSMBMemberCreate,
    DSMBMemberUpdate,
    DSMBRecommendationCreate,
    DSMBRecommendationUpdate,
    MeetingStatus,
    MeetingType,
    MemberRole,
    RecommendationType,
    SafetyReviewCreate,
    SafetyReviewUpdate,
    UnblindingRequestCreate,
    UnblindingRequestUpdate,
    UnblindingScope,
    UnblindingStatus,
    VoteOutcome,
)
from app.services.dsmb_management_service import (
    DSMBManagementService,
    get_dsmb_management_service,
    reset_dsmb_management_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/dsmb"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_dsmb_management_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> DSMBManagementService:
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


def _make_charter_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": LIBTAYO_TRIAL,
        "version": "1.0",
        "effective_date": now.isoformat(),
        "review_frequency": "quarterly",
        "stopping_rules": "Group sequential with O'Brien-Fleming boundaries",
        "unblinding_procedures": "Unblinding requires DSMB majority vote",
        "membership_criteria": "Minimum 4 members with relevant expertise",
        "conflict_of_interest_policy": "No financial interest in sponsor",
    }
    defaults.update(overrides)
    return defaults


def _make_member_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "charter_id": "DSMB-CHR-001",
        "name": "Dr. Test Member",
        "role": "clinician",
        "institution": "Test University",
        "specialty": "Oncology",
        "email": "test@university.edu",
        "term_start": now.isoformat(),
        "term_end": (now + timedelta(days=730)).isoformat(),
        "conflict_declarations": [],
    }
    defaults.update(overrides)
    return defaults


def _make_meeting_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "charter_id": "DSMB-CHR-001",
        "trial_id": EYLEA_TRIAL,
        "meeting_type": "scheduled_review",
        "meeting_number": 10,
        "scheduled_date": (now + timedelta(days=30)).isoformat(),
        "location": "Virtual (Zoom)",
        "agenda": "Test meeting agenda",
        "quorum_required": 3,
    }
    defaults.update(overrides)
    return defaults


def _make_safety_review_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "meeting_id": "DSMB-MTG-002",
        "data_cutoff_date": now.isoformat(),
        "enrollment_at_review": 150,
        "ae_summary": "Test AE summary",
        "sae_summary": "Test SAE summary",
        "mortality_summary": "No deaths",
    }
    defaults.update(overrides)
    return defaults


def _make_recommendation_create(**overrides) -> dict:
    defaults = {
        "meeting_id": "DSMB-MTG-002",
        "recommendation_type": "continue_unchanged",
        "rationale": "Safety profile acceptable, no concerns identified",
        "vote_outcome": "unanimous",
        "votes_for": 4,
        "votes_against": 0,
        "votes_abstain": 0,
    }
    defaults.update(overrides)
    return defaults


def _make_unblinding_request_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "requested_by": "Dr. Test Requester",
        "justification": "Planned interim analysis per charter",
        "scope": "interim_analysis",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_charters_count(self, svc: DSMBManagementService):
        charters = svc.list_charters()
        assert len(charters) == 3

    def test_seed_charters_trials(self, svc: DSMBManagementService):
        charters = svc.list_charters()
        trial_ids = {c.trial_id for c in charters}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_members_count(self, svc: DSMBManagementService):
        members = svc.list_members()
        assert len(members) == 7

    def test_seed_members_roles(self, svc: DSMBManagementService):
        members = svc.list_members()
        roles = {m.role for m in members}
        assert MemberRole.CHAIR in roles
        assert MemberRole.STATISTICIAN in roles
        assert MemberRole.CLINICIAN in roles
        assert MemberRole.ETHICIST in roles
        assert MemberRole.PATIENT_ADVOCATE in roles

    def test_seed_meetings_count(self, svc: DSMBManagementService):
        meetings = svc.list_meetings()
        assert len(meetings) == 6

    def test_seed_meetings_types(self, svc: DSMBManagementService):
        meetings = svc.list_meetings()
        types = {m.meeting_type for m in meetings}
        assert MeetingType.ORGANIZATIONAL in types
        assert MeetingType.SCHEDULED_REVIEW in types
        assert MeetingType.EMERGENCY in types

    def test_seed_safety_reviews_count(self, svc: DSMBManagementService):
        reviews = svc.list_safety_reviews()
        assert len(reviews) == 4

    def test_seed_recommendations_count(self, svc: DSMBManagementService):
        recs = svc.list_recommendations()
        assert len(recs) == 4

    def test_seed_unblinding_requests_count(self, svc: DSMBManagementService):
        reqs = svc.list_unblinding_requests()
        assert len(reqs) == 3

    def test_seed_completed_meetings_have_minutes(self, svc: DSMBManagementService):
        meetings = svc.list_meetings(status=MeetingStatus.COMPLETED)
        for mtg in meetings:
            assert mtg.open_session_minutes is not None
            assert mtg.closed_session_minutes is not None

    def test_seed_pending_unblinding_exists(self, svc: DSMBManagementService):
        pending = svc.list_unblinding_requests(status=UnblindingStatus.PENDING)
        assert len(pending) >= 1


# =====================================================================
# CHARTER CRUD
# =====================================================================


class TestCharterCrud:
    """Test charter CRUD operations."""

    @pytest.mark.anyio
    async def test_list_charters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/charters")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    @pytest.mark.anyio
    async def test_list_charters_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/charters", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_charter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/charters/DSMB-CHR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DSMB-CHR-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["version"] == "2.0"

    @pytest.mark.anyio
    async def test_get_charter_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/charters/DSMB-CHR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_charter(self, client: AsyncClient):
        payload = _make_charter_create()
        resp = await client.post(f"{API_PREFIX}/charters", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == LIBTAYO_TRIAL
        assert data["version"] == "1.0"
        assert data["id"].startswith("DSMB-CHR-")

    @pytest.mark.anyio
    async def test_update_charter(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/charters/DSMB-CHR-001",
            json={"version": "3.0", "review_frequency": "monthly"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "3.0"
        assert data["review_frequency"] == "monthly"

    @pytest.mark.anyio
    async def test_update_charter_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/charters/DSMB-CHR-NONEXISTENT",
            json={"version": "2.0"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_charter(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/charters/DSMB-CHR-003")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/charters/DSMB-CHR-003")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_charter_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/charters/DSMB-CHR-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# MEMBER CRUD
# =====================================================================


class TestMemberCrud:
    """Test DSMB member CRUD operations."""

    @pytest.mark.anyio
    async def test_list_members(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/members")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 7

    @pytest.mark.anyio
    async def test_list_members_filter_charter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/members", params={"charter_id": "DSMB-CHR-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        for item in data["items"]:
            assert item["charter_id"] == "DSMB-CHR-001"

    @pytest.mark.anyio
    async def test_list_members_filter_role(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/members", params={"role": "chair"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["role"] == "chair"

    @pytest.mark.anyio
    async def test_list_members_filter_active(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/members", params={"active": True})
        assert resp.status_code == 200
        data = resp.json()
        # DSMB-MEM-007 is inactive
        assert data["total"] == 6

    @pytest.mark.anyio
    async def test_get_member(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/members/DSMB-MEM-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DSMB-MEM-001"
        assert data["role"] == "chair"
        assert data["name"] == "Dr. Elizabeth Warren"

    @pytest.mark.anyio
    async def test_get_member_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/members/DSMB-MEM-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_member(self, client: AsyncClient):
        payload = _make_member_create()
        resp = await client.post(f"{API_PREFIX}/members", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Dr. Test Member"
        assert data["role"] == "clinician"
        assert data["id"].startswith("DSMB-MEM-")

    @pytest.mark.anyio
    async def test_create_member_invalid_charter(self, client: AsyncClient):
        payload = _make_member_create(charter_id="DSMB-CHR-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/members", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_member(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/members/DSMB-MEM-001",
            json={"institution": "Updated University", "active": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["institution"] == "Updated University"
        assert data["active"] is False

    @pytest.mark.anyio
    async def test_update_member_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/members/DSMB-MEM-NONEXISTENT",
            json={"name": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_member(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/members/DSMB-MEM-005")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/members/DSMB-MEM-005")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_member_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/members/DSMB-MEM-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# MEETING CRUD AND LIFECYCLE
# =====================================================================


class TestMeetingCrud:
    """Test DSMB meeting CRUD and lifecycle operations."""

    @pytest.mark.anyio
    async def test_list_meetings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meetings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6

    @pytest.mark.anyio
    async def test_list_meetings_filter_charter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meetings", params={"charter_id": "DSMB-CHR-001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["charter_id"] == "DSMB-CHR-001"

    @pytest.mark.anyio
    async def test_list_meetings_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meetings", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_meetings_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meetings", params={"status": "completed"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_list_meetings_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meetings", params={"meeting_type": "emergency"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["meeting_type"] == "emergency"

    @pytest.mark.anyio
    async def test_get_meeting(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meetings/DSMB-MTG-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DSMB-MTG-001"
        assert data["meeting_type"] == "organizational"
        assert data["status"] == "completed"

    @pytest.mark.anyio
    async def test_get_meeting_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meetings/DSMB-MTG-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_schedule_meeting(self, client: AsyncClient):
        payload = _make_meeting_create()
        resp = await client.post(f"{API_PREFIX}/meetings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["meeting_type"] == "scheduled_review"
        assert data["status"] == "scheduled"
        assert data["id"].startswith("DSMB-MTG-")

    @pytest.mark.anyio
    async def test_schedule_meeting_invalid_charter(self, client: AsyncClient):
        payload = _make_meeting_create(charter_id="DSMB-CHR-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/meetings", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_meeting_status(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/meetings/DSMB-MTG-006",
            json={
                "status": "in_progress",
                "actual_date": now.isoformat(),
                "attendees": ["DSMB-MEM-001", "DSMB-MEM-002", "DSMB-MEM-003"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert len(data["attendees"]) == 3

    @pytest.mark.anyio
    async def test_update_meeting_add_minutes(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/meetings/DSMB-MTG-006",
            json={
                "open_session_minutes": "Test open minutes",
                "closed_session_minutes": "Test closed minutes",
                "status": "completed",
                "quorum_met": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["open_session_minutes"] == "Test open minutes"
        assert data["closed_session_minutes"] == "Test closed minutes"
        assert data["status"] == "completed"
        assert data["quorum_met"] is True

    @pytest.mark.anyio
    async def test_update_meeting_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/meetings/DSMB-MTG-NONEXISTENT",
            json={"status": "cancelled"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_meeting(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/meetings/DSMB-MTG-006")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/meetings/DSMB-MTG-006")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_meeting_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/meetings/DSMB-MTG-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# QUORUM VALIDATION
# =====================================================================


class TestQuorumValidation:
    """Test DSMB quorum check functionality."""

    @pytest.mark.anyio
    async def test_quorum_met_completed_meeting(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meetings/DSMB-MTG-001/quorum")
        assert resp.status_code == 200
        data = resp.json()
        assert data["meeting_id"] == "DSMB-MTG-001"
        assert data["quorum_met"] is True
        assert data["attendees_count"] == 5
        assert data["quorum_required"] == 3
        assert data["missing_roles"] == []

    @pytest.mark.anyio
    async def test_quorum_not_met_no_attendees(self, client: AsyncClient):
        # DSMB-MTG-006 is scheduled with no attendees
        resp = await client.get(f"{API_PREFIX}/meetings/DSMB-MTG-006/quorum")
        assert resp.status_code == 200
        data = resp.json()
        assert data["quorum_met"] is False
        assert data["attendees_count"] == 0

    @pytest.mark.anyio
    async def test_quorum_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meetings/DSMB-MTG-NONEXISTENT/quorum")
        assert resp.status_code == 404

    def test_quorum_check_missing_roles(self, svc: DSMBManagementService):
        """Meeting with only patient advocate should report missing required roles."""
        # Update meeting to have only patient advocate as attendee
        svc.update_meeting(
            "DSMB-MTG-006",
            DSMBMeetingUpdate(attendees=["DSMB-MEM-005"]),
        )
        result = svc.check_quorum("DSMB-MTG-006")
        assert result is not None
        assert result.quorum_met is False
        assert "chair" in result.missing_roles
        assert "statistician" in result.missing_roles
        assert "clinician" in result.missing_roles

    def test_quorum_check_with_required_roles(self, svc: DSMBManagementService):
        """Meeting with chair, statistician, clinician should meet role requirements."""
        svc.update_meeting(
            "DSMB-MTG-006",
            DSMBMeetingUpdate(
                attendees=["DSMB-MEM-001", "DSMB-MEM-002", "DSMB-MEM-003"],
            ),
        )
        result = svc.check_quorum("DSMB-MTG-006")
        assert result is not None
        assert result.quorum_met is True
        assert result.missing_roles == []

    def test_quorum_inactive_member_not_counted_for_roles(self, svc: DSMBManagementService):
        """Inactive members should not satisfy role requirements."""
        # DSMB-MEM-007 is inactive statistician for charter 002
        # Create meeting under charter 002 with only inactive member
        meeting = svc.schedule_meeting(DSMBMeetingCreate(
            charter_id="DSMB-CHR-002",
            trial_id=DUPIXENT_TRIAL,
            meeting_type=MeetingType.AD_HOC,
            meeting_number=99,
            scheduled_date=datetime.now(timezone.utc) + timedelta(days=5),
            location="Virtual",
            quorum_required=2,
        ))
        svc.update_meeting(
            meeting.id,
            DSMBMeetingUpdate(attendees=["DSMB-MEM-006", "DSMB-MEM-007"]),
        )
        result = svc.check_quorum(meeting.id)
        assert result is not None
        # MEM-007 is inactive, so statistician role not met
        assert "statistician" in result.missing_roles


# =====================================================================
# SAFETY REVIEW CRUD
# =====================================================================


class TestSafetyReviewCrud:
    """Test safety review CRUD operations."""

    @pytest.mark.anyio
    async def test_list_safety_reviews(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/safety-reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4

    @pytest.mark.anyio
    async def test_list_safety_reviews_filter_meeting(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/safety-reviews", params={"meeting_id": "DSMB-MTG-003"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["meeting_id"] == "DSMB-MTG-003"

    @pytest.mark.anyio
    async def test_get_safety_review(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/safety-reviews/DSMB-SR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DSMB-SR-001"
        assert data["enrollment_at_review"] == 126

    @pytest.mark.anyio
    async def test_get_safety_review_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/safety-reviews/DSMB-SR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_conduct_safety_review(self, client: AsyncClient):
        payload = _make_safety_review_create()
        resp = await client.post(f"{API_PREFIX}/safety-reviews", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["enrollment_at_review"] == 150
        assert data["id"].startswith("DSMB-SR-")

    @pytest.mark.anyio
    async def test_conduct_safety_review_invalid_meeting(self, client: AsyncClient):
        payload = _make_safety_review_create(meeting_id="DSMB-MTG-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/safety-reviews", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_safety_review(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/safety-reviews/DSMB-SR-001",
            json={
                "enrollment_at_review": 130,
                "efficacy_summary": "Updated efficacy analysis available",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["enrollment_at_review"] == 130
        assert data["efficacy_summary"] == "Updated efficacy analysis available"

    @pytest.mark.anyio
    async def test_update_safety_review_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/safety-reviews/DSMB-SR-NONEXISTENT",
            json={"enrollment_at_review": 100},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_safety_review(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/safety-reviews/DSMB-SR-004")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/safety-reviews/DSMB-SR-004")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_safety_review_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/safety-reviews/DSMB-SR-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# RECOMMENDATION CRUD AND VOTING
# =====================================================================


class TestRecommendationCrud:
    """Test DSMB recommendation CRUD and voting."""

    @pytest.mark.anyio
    async def test_list_recommendations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/recommendations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4

    @pytest.mark.anyio
    async def test_list_recommendations_filter_meeting(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/recommendations", params={"meeting_id": "DSMB-MTG-004"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["meeting_id"] == "DSMB-MTG-004"

    @pytest.mark.anyio
    async def test_list_recommendations_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/recommendations",
            params={"recommendation_type": "pause_enrollment"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["recommendation_type"] == "pause_enrollment"

    @pytest.mark.anyio
    async def test_get_recommendation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/recommendations/DSMB-REC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DSMB-REC-001"
        assert data["recommendation_type"] == "continue_unchanged"
        assert data["vote_outcome"] == "unanimous"
        assert data["votes_for"] == 4
        assert data["votes_against"] == 0

    @pytest.mark.anyio
    async def test_get_recommendation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/recommendations/DSMB-REC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_record_recommendation(self, client: AsyncClient):
        payload = _make_recommendation_create()
        resp = await client.post(f"{API_PREFIX}/recommendations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["recommendation_type"] == "continue_unchanged"
        assert data["vote_outcome"] == "unanimous"
        assert data["communicated_to_sponsor"] is False
        assert data["id"].startswith("DSMB-REC-")

    @pytest.mark.anyio
    async def test_record_recommendation_invalid_meeting(self, client: AsyncClient):
        payload = _make_recommendation_create(meeting_id="DSMB-MTG-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/recommendations", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_record_recommendation_majority_vote(self, client: AsyncClient):
        payload = _make_recommendation_create(
            recommendation_type="continue_with_modifications",
            vote_outcome="majority",
            votes_for=3,
            votes_against=1,
            votes_abstain=1,
        )
        resp = await client.post(f"{API_PREFIX}/recommendations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["vote_outcome"] == "majority"
        assert data["votes_for"] == 3
        assert data["votes_against"] == 1
        assert data["votes_abstain"] == 1

    @pytest.mark.anyio
    async def test_update_recommendation_sponsor_communication(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        # Create a recommendation first, then communicate it
        payload = _make_recommendation_create()
        resp = await client.post(f"{API_PREFIX}/recommendations", json=payload)
        rec_id = resp.json()["id"]

        resp2 = await client.put(
            f"{API_PREFIX}/recommendations/{rec_id}",
            json={
                "communicated_to_sponsor": True,
                "communicated_date": now.isoformat(),
                "sponsor_response": "Acknowledged and accepted",
            },
        )
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["communicated_to_sponsor"] is True
        assert data["sponsor_response"] == "Acknowledged and accepted"

    @pytest.mark.anyio
    async def test_update_recommendation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/recommendations/DSMB-REC-NONEXISTENT",
            json={"rationale": "Updated"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_recommendation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/recommendations/DSMB-REC-004")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/recommendations/DSMB-REC-004")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_recommendation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/recommendations/DSMB-REC-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# RECOMMENDATION VOTING DETAILS
# =====================================================================


class TestRecommendationVoting:
    """Test voting record details on recommendations."""

    def test_unanimous_vote(self, svc: DSMBManagementService):
        rec = svc.get_recommendation("DSMB-REC-001")
        assert rec is not None
        assert rec.vote_outcome == VoteOutcome.UNANIMOUS
        assert rec.votes_against == 0
        assert rec.votes_abstain == 0

    def test_majority_vote(self, svc: DSMBManagementService):
        rec = svc.get_recommendation("DSMB-REC-002")
        assert rec is not None
        assert rec.vote_outcome == VoteOutcome.MAJORITY
        assert rec.votes_for > rec.votes_against

    def test_pause_enrollment_recommendation(self, svc: DSMBManagementService):
        rec = svc.get_recommendation("DSMB-REC-003")
        assert rec is not None
        assert rec.recommendation_type == RecommendationType.PAUSE_ENROLLMENT
        assert rec.conditions is not None
        assert len(rec.conditions) > 0

    def test_all_recommendations_communicated(self, svc: DSMBManagementService):
        """All seeded recommendations should be communicated to sponsor."""
        recs = svc.list_recommendations()
        for rec in recs:
            assert rec.communicated_to_sponsor is True
            assert rec.communicated_date is not None
            assert rec.sponsor_response is not None


# =====================================================================
# UNBLINDING REQUEST WORKFLOW
# =====================================================================


class TestUnblindingRequestWorkflow:
    """Test unblinding request lifecycle."""

    @pytest.mark.anyio
    async def test_list_unblinding_requests(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/unblinding-requests")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_unblinding_requests_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/unblinding-requests", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_unblinding_requests_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/unblinding-requests", params={"status": "pending"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["status"] == "pending"

    @pytest.mark.anyio
    async def test_get_unblinding_request(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/unblinding-requests/DSMB-UBR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DSMB-UBR-001"
        assert data["scope"] == "interim_analysis"
        assert data["status"] == "completed"
        assert data["approved"] is True

    @pytest.mark.anyio
    async def test_get_unblinding_request_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/unblinding-requests/DSMB-UBR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_unblinding_request(self, client: AsyncClient):
        payload = _make_unblinding_request_create()
        resp = await client.post(f"{API_PREFIX}/unblinding-requests", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["approved"] is None
        assert data["scope"] == "interim_analysis"
        assert data["id"].startswith("DSMB-UBR-")

    @pytest.mark.anyio
    async def test_create_unblinding_request_individual_patient(self, client: AsyncClient):
        payload = _make_unblinding_request_create(
            scope="individual_patient",
            justification="Patient safety emergency requiring treatment knowledge",
        )
        resp = await client.post(f"{API_PREFIX}/unblinding-requests", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["scope"] == "individual_patient"

    @pytest.mark.anyio
    async def test_approve_unblinding_request(self, client: AsyncClient):
        # DSMB-UBR-003 is pending
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/unblinding-requests/DSMB-UBR-003",
            json={
                "approved": True,
                "approved_by": "Dr. Angela Torres (DSMB Chair)",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["approved"] is True
        assert data["status"] == "approved"
        assert data["approval_date"] is not None

    @pytest.mark.anyio
    async def test_deny_unblinding_request(self, client: AsyncClient):
        # Create a new pending request first
        payload = _make_unblinding_request_create(
            scope="full_study",
            justification="Premature full unblinding request",
        )
        resp = await client.post(f"{API_PREFIX}/unblinding-requests", json=payload)
        req_id = resp.json()["id"]

        resp2 = await client.put(
            f"{API_PREFIX}/unblinding-requests/{req_id}",
            json={
                "approved": False,
                "approved_by": "DSMB Chair",
            },
        )
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["approved"] is False
        assert data["status"] == "denied"

    @pytest.mark.anyio
    async def test_complete_unblinding_request(self, client: AsyncClient):
        # Approve then complete DSMB-UBR-003
        now = datetime.now(timezone.utc)
        await client.put(
            f"{API_PREFIX}/unblinding-requests/DSMB-UBR-003",
            json={"approved": True, "approved_by": "Chair"},
        )
        resp = await client.put(
            f"{API_PREFIX}/unblinding-requests/DSMB-UBR-003",
            json={
                "unblinding_date": now.isoformat(),
                "results_summary": "Patient was on active treatment arm",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["results_summary"] is not None

    @pytest.mark.anyio
    async def test_update_unblinding_request_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/unblinding-requests/DSMB-UBR-NONEXISTENT",
            json={"approved": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_unblinding_request(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/unblinding-requests/DSMB-UBR-003")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/unblinding-requests/DSMB-UBR-003")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_unblinding_request_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/unblinding-requests/DSMB-UBR-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# UNBLINDING SCOPE VERIFICATION
# =====================================================================


class TestUnblindingScopes:
    """Test different unblinding scopes are properly handled."""

    def test_interim_analysis_scope(self, svc: DSMBManagementService):
        req = svc.get_unblinding_request("DSMB-UBR-001")
        assert req is not None
        assert req.scope == UnblindingScope.INTERIM_ANALYSIS

    def test_treatment_arm_scope(self, svc: DSMBManagementService):
        req = svc.get_unblinding_request("DSMB-UBR-002")
        assert req is not None
        assert req.scope == UnblindingScope.TREATMENT_ARM

    def test_individual_patient_scope(self, svc: DSMBManagementService):
        req = svc.get_unblinding_request("DSMB-UBR-003")
        assert req is not None
        assert req.scope == UnblindingScope.INDIVIDUAL_PATIENT

    def test_create_full_study_scope(self, svc: DSMBManagementService):
        req = svc.request_unblinding(UnblindingRequestCreate(
            trial_id=EYLEA_TRIAL,
            requested_by="Dr. Test",
            justification="Final analysis",
            scope=UnblindingScope.FULL_STUDY,
        ))
        assert req.scope == UnblindingScope.FULL_STUDY
        assert req.status == UnblindingStatus.PENDING


# =====================================================================
# METRICS
# =====================================================================


class TestDSMBMetrics:
    """Test DSMB metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_charters"] == 3
        assert data["total_members"] == 7
        assert data["active_members"] == 6
        assert data["total_meetings"] == 6
        assert data["completed_meetings"] == 5
        assert data["planned_meetings"] >= 1
        assert data["total_safety_reviews"] == 4
        assert data["total_recommendations"] == 4
        assert data["total_unblinding_requests"] == 3
        assert data["pending_unblinding_requests"] == 1

    def test_metrics_recommendations_by_type(self, svc: DSMBManagementService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.recommendations_by_type.values())
        assert total_by_type == metrics.total_recommendations

    def test_metrics_communicated_recommendations(self, svc: DSMBManagementService):
        metrics = svc.get_metrics()
        # All 4 seeded recommendations are communicated
        assert metrics.recommendations_communicated == 4

    def test_metrics_meetings_with_quorum(self, svc: DSMBManagementService):
        metrics = svc.get_metrics()
        # All completed meetings had quorum
        assert metrics.meetings_with_quorum == 5

    def test_metrics_after_adding_data(self, svc: DSMBManagementService):
        """Adding new records should update metrics."""
        initial = svc.get_metrics()

        svc.create_charter(DSMBCharterCreate(
            trial_id=LIBTAYO_TRIAL,
            version="2.0",
            effective_date=datetime.now(timezone.utc),
            review_frequency="quarterly",
            stopping_rules="Test rules",
            unblinding_procedures="Test procedures",
            membership_criteria="Test criteria",
            conflict_of_interest_policy="Test policy",
        ))

        updated = svc.get_metrics()
        assert updated.total_charters == initial.total_charters + 1


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_dsmb_management_service()
        svc2 = get_dsmb_management_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_dsmb_management_service()
        svc2 = reset_dsmb_management_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_dsmb_management_service()
        svc.delete_charter("DSMB-CHR-001")
        assert svc.get_charter("DSMB-CHR-001") is None
        svc2 = reset_dsmb_management_service()
        assert svc2.get_charter("DSMB-CHR-001") is not None


# =====================================================================
# MEETING LIFECYCLE INTEGRATION
# =====================================================================


class TestMeetingLifecycleIntegration:
    """Test full meeting lifecycle: schedule -> conduct -> review -> recommend."""

    @pytest.mark.anyio
    async def test_full_meeting_lifecycle(self, client: AsyncClient):
        now = datetime.now(timezone.utc)

        # 1. Schedule a meeting
        mtg_payload = _make_meeting_create(meeting_number=20)
        resp = await client.post(f"{API_PREFIX}/meetings", json=mtg_payload)
        assert resp.status_code == 201
        meeting_id = resp.json()["id"]

        # 2. Update to in-progress with attendees
        resp = await client.put(
            f"{API_PREFIX}/meetings/{meeting_id}",
            json={
                "status": "in_progress",
                "actual_date": now.isoformat(),
                "attendees": ["DSMB-MEM-001", "DSMB-MEM-002", "DSMB-MEM-003", "DSMB-MEM-004"],
            },
        )
        assert resp.status_code == 200

        # 3. Check quorum
        resp = await client.get(f"{API_PREFIX}/meetings/{meeting_id}/quorum")
        assert resp.status_code == 200
        assert resp.json()["quorum_met"] is True

        # 4. Conduct safety review
        sr_payload = _make_safety_review_create(meeting_id=meeting_id)
        resp = await client.post(f"{API_PREFIX}/safety-reviews", json=sr_payload)
        assert resp.status_code == 201

        # 5. Record recommendation
        rec_payload = _make_recommendation_create(meeting_id=meeting_id)
        resp = await client.post(f"{API_PREFIX}/recommendations", json=rec_payload)
        assert resp.status_code == 201
        rec_id = resp.json()["id"]

        # 6. Complete meeting
        resp = await client.put(
            f"{API_PREFIX}/meetings/{meeting_id}",
            json={
                "status": "completed",
                "quorum_met": True,
                "open_session_minutes": "Sponsor presented data",
                "closed_session_minutes": "DSMB reviewed and voted",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

        # 7. Communicate recommendation to sponsor
        resp = await client.put(
            f"{API_PREFIX}/recommendations/{rec_id}",
            json={
                "communicated_to_sponsor": True,
                "communicated_date": now.isoformat(),
                "sponsor_response": "Acknowledged",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["communicated_to_sponsor"] is True


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_charters_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/charters")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_members_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/members")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_meetings_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meetings")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_safety_reviews_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/safety-reviews")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_recommendations_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/recommendations")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_unblinding_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/unblinding-requests")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_charter_with_all_fields(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = _make_charter_create(
            version="3.0",
            review_frequency="monthly",
            stopping_rules="Custom stopping rules with detailed criteria",
        )
        resp = await client.post(f"{API_PREFIX}/charters", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_member_with_conflicts(self, client: AsyncClient):
        payload = _make_member_create(
            conflict_declarations=["Consulting for Pfizer", "Research grant from Novartis"],
        )
        resp = await client.post(f"{API_PREFIX}/members", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["conflict_declarations"]) == 2

    @pytest.mark.anyio
    async def test_meeting_cancel(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/meetings/DSMB-MTG-006",
            json={"status": "cancelled"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    @pytest.mark.anyio
    async def test_safety_review_with_all_reports(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = _make_safety_review_create(
            efficacy_summary="Positive efficacy trends observed",
            dmc_statistician_report="Blinded analysis shows no imbalance",
            independent_statistician_report="Unblinded data supports continuation",
        )
        resp = await client.post(f"{API_PREFIX}/safety-reviews", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["efficacy_summary"] is not None
        assert data["dmc_statistician_report"] is not None
        assert data["independent_statistician_report"] is not None

    @pytest.mark.anyio
    async def test_recommendation_with_conditions(self, client: AsyncClient):
        payload = _make_recommendation_create(
            recommendation_type="continue_with_modifications",
            conditions="Add additional safety monitoring visits",
            vote_outcome="majority",
            votes_for=3,
            votes_against=1,
        )
        resp = await client.post(f"{API_PREFIX}/recommendations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["conditions"] is not None

    @pytest.mark.anyio
    async def test_unblinding_request_with_meeting(self, client: AsyncClient):
        payload = _make_unblinding_request_create(
            meeting_id="DSMB-MTG-002",
        )
        resp = await client.post(f"{API_PREFIX}/unblinding-requests", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["meeting_id"] == "DSMB-MTG-002"

    @pytest.mark.anyio
    async def test_unblinding_request_without_meeting(self, client: AsyncClient):
        payload = _make_unblinding_request_create()
        resp = await client.post(f"{API_PREFIX}/unblinding-requests", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["meeting_id"] is None


# =====================================================================
# ENUMERATION VERIFICATION
# =====================================================================


class TestEnumerations:
    """Test enum values are correctly used throughout the system."""

    @pytest.mark.anyio
    async def test_meeting_types_in_meetings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meetings")
        data = resp.json()
        types = {item["meeting_type"] for item in data["items"]}
        assert "organizational" in types
        assert "scheduled_review" in types
        assert "emergency" in types

    @pytest.mark.anyio
    async def test_meeting_statuses_in_meetings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meetings")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "completed" in statuses
        assert "scheduled" in statuses

    @pytest.mark.anyio
    async def test_member_roles_in_members(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/members")
        data = resp.json()
        roles = {item["role"] for item in data["items"]}
        assert "chair" in roles
        assert "statistician" in roles
        assert "clinician" in roles
        assert "ethicist" in roles
        assert "patient_advocate" in roles

    @pytest.mark.anyio
    async def test_recommendation_types_in_recommendations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/recommendations")
        data = resp.json()
        types = {item["recommendation_type"] for item in data["items"]}
        assert "continue_unchanged" in types
        assert "continue_with_modifications" in types
        assert "pause_enrollment" in types

    @pytest.mark.anyio
    async def test_vote_outcomes_in_recommendations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/recommendations")
        data = resp.json()
        outcomes = {item["vote_outcome"] for item in data["items"]}
        assert "unanimous" in outcomes
        assert "majority" in outcomes

    @pytest.mark.anyio
    async def test_unblinding_scopes(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/unblinding-requests")
        data = resp.json()
        scopes = {item["scope"] for item in data["items"]}
        assert "interim_analysis" in scopes
        assert "treatment_arm" in scopes
        assert "individual_patient" in scopes

    @pytest.mark.anyio
    async def test_unblinding_statuses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/unblinding-requests")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "completed" in statuses
        assert "pending" in statuses


# =====================================================================
# DATA INTEGRITY
# =====================================================================


class TestDataIntegrity:
    """Test data integrity across related entities."""

    def test_safety_reviews_reference_valid_meetings(self, svc: DSMBManagementService):
        reviews = svc.list_safety_reviews()
        for review in reviews:
            meeting = svc.get_meeting(review.meeting_id)
            assert meeting is not None, f"Review {review.id} references invalid meeting {review.meeting_id}"

    def test_recommendations_reference_valid_meetings(self, svc: DSMBManagementService):
        recs = svc.list_recommendations()
        for rec in recs:
            meeting = svc.get_meeting(rec.meeting_id)
            assert meeting is not None, f"Recommendation {rec.id} references invalid meeting {rec.meeting_id}"

    def test_members_reference_valid_charters(self, svc: DSMBManagementService):
        members = svc.list_members()
        for member in members:
            charter = svc.get_charter(member.charter_id)
            assert charter is not None, f"Member {member.id} references invalid charter {member.charter_id}"

    def test_meetings_reference_valid_charters(self, svc: DSMBManagementService):
        meetings = svc.list_meetings()
        for meeting in meetings:
            charter = svc.get_charter(meeting.charter_id)
            assert charter is not None, f"Meeting {meeting.id} references invalid charter {meeting.charter_id}"

    def test_completed_unblinding_has_results(self, svc: DSMBManagementService):
        completed = svc.list_unblinding_requests(status=UnblindingStatus.COMPLETED)
        for req in completed:
            assert req.approved is True
            assert req.unblinding_date is not None
            assert req.results_summary is not None

    def test_meeting_attendees_are_valid_members(self, svc: DSMBManagementService):
        meetings = svc.list_meetings()
        for meeting in meetings:
            for attendee_id in meeting.attendees:
                member = svc.get_member(attendee_id)
                assert member is not None, f"Meeting {meeting.id} has invalid attendee {attendee_id}"
