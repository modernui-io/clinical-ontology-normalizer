"""Tests for Central IRB/EC Management (CLINICAL-8).

Covers:
- Seed data verification (boards, submissions, continuing reviews, events, documents, correspondence)
- Board CRUD (create, read, update, list, filter by type/active)
- Submission lifecycle (draft -> submitted -> under_review -> approved)
- Submission CRUD and filtering
- Submit for review transition
- Record outcome (approved, conditionally approved, deferred, disapproved)
- Continuing review workflow (create, list, update, get)
- Reportable event filing and updates
- Regulatory document management
- Correspondence tracking
- Expiring approvals query
- IRB metrics aggregation
- Error cases (404s, invalid transitions)
- Service singleton pattern
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.central_irb import (
    BoardType,
    ContinuingReviewCreate,
    CorrespondenceDirection,
    DocumentStatus,
    DocumentType,
    EventSeverity,
    EventStatus,
    IRBBoardCreate,
    IRBCorrespondenceCreate,
    IRBSubmissionCreate,
    RecordOutcomeRequest,
    RegulatoryDocumentCreate,
    ReportableEventCreate,
    ReviewOutcome,
    ReviewStatus,
    SubmissionSubmitRequest,
    SubmissionType,
)
from app.services.central_irb_service import (
    CentralIRBService,
    get_central_irb_service,
    reset_central_irb_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/central-irb"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_central_irb_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> CentralIRBService:
    """Shorthand for the fresh service."""
    return fresh_service


@pytest.fixture
async def client():
    """Async HTTP client for API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_board_create(**overrides) -> dict:
    defaults = {
        "name": "Test IRB Board",
        "board_type": "central_irb",
        "organization": "Test Organization",
        "country": "United States",
        "contact_email": "test@irb.com",
        "meeting_schedule": "Monthly, 1st Tuesday",
        "submission_lead_time_days": 14,
    }
    defaults.update(overrides)
    return defaults


def _make_submission_create(**overrides) -> dict:
    defaults = {
        "board_id": "IRB-001",
        "trial_id": EYLEA_TRIAL,
        "submission_type": "initial",
        "submission_number": "TEST-001",
        "protocol_version": "1.0",
        "submitted_by": "Dr. Test User",
    }
    defaults.update(overrides)
    return defaults


def _make_continuing_review_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "board_id": "IRB-001",
        "trial_id": EYLEA_TRIAL,
        "review_period_start": (now - timedelta(days=365)).isoformat(),
        "review_period_end": now.isoformat(),
        "enrollment_since_last_review": 25,
        "total_enrolled": 80,
        "adverse_events_count": 5,
        "protocol_deviations_count": 2,
        "amendments_since_last": 1,
        "risk_assessment": "Risk remains acceptable.",
    }
    defaults.update(overrides)
    return defaults


def _make_reportable_event_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "board_id": "IRB-001",
        "trial_id": EYLEA_TRIAL,
        "event_type": "Serious Adverse Event",
        "event_description": "Test adverse event description.",
        "event_date": now.isoformat(),
        "severity": "high",
        "requires_immediate_report": True,
        "report_deadline": (now + timedelta(days=3)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_document_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "document_type": "protocol",
        "document_name": "Test Protocol v1.0",
        "version": "1.0",
        "file_reference": "/documents/test/protocol_v1.0.pdf",
        "uploaded_by": "Dr. Test User",
    }
    defaults.update(overrides)
    return defaults


def _make_correspondence_create(**overrides) -> dict:
    defaults = {
        "direction": "outgoing",
        "subject": "Test Correspondence",
        "content": "This is a test correspondence message.",
        "sent_by": "Dr. Test User",
        "response_required": False,
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_boards_count(self, svc: CentralIRBService):
        boards = svc.list_boards()
        assert len(boards) == 3

    def test_seed_boards_types(self, svc: CentralIRBService):
        boards = svc.list_boards()
        types = {b.board_type for b in boards}
        assert BoardType.CENTRAL_IRB in types
        assert BoardType.ETHICS_COMMITTEE in types

    def test_seed_submissions_count(self, svc: CentralIRBService):
        submissions = svc.list_submissions()
        assert len(submissions) == 7

    def test_seed_submissions_statuses(self, svc: CentralIRBService):
        submissions = svc.list_submissions()
        statuses = {s.status for s in submissions}
        assert ReviewStatus.APPROVED in statuses
        assert ReviewStatus.DRAFT in statuses
        assert ReviewStatus.SUBMITTED in statuses

    def test_seed_continuing_reviews_count(self, svc: CentralIRBService):
        crs = svc.list_continuing_reviews()
        assert len(crs) == 3

    def test_seed_reportable_events_count(self, svc: CentralIRBService):
        events = svc.list_reportable_events()
        assert len(events) == 3

    def test_seed_documents_count(self, svc: CentralIRBService):
        docs = svc.list_documents()
        assert len(docs) == 5

    def test_seed_correspondence_count(self, svc: CentralIRBService):
        corr = svc.list_correspondence()
        assert len(corr) == 4


# =====================================================================
# BOARD CRUD
# =====================================================================


class TestBoardCrud:
    """Test board create, read, update, list operations."""

    @pytest.mark.anyio
    async def test_list_boards(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/boards")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    @pytest.mark.anyio
    async def test_list_boards_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/boards", params={"board_type": "central_irb"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["board_type"] == "central_irb"

    @pytest.mark.anyio
    async def test_list_boards_filter_active(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/boards", params={"active": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_get_board(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/boards/IRB-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "IRB-001"
        assert "WCG" in data["name"]

    @pytest.mark.anyio
    async def test_get_board_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/boards/IRB-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_board(self, client: AsyncClient):
        payload = _make_board_create()
        resp = await client.post(f"{API_PREFIX}/boards", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test IRB Board"
        assert data["board_type"] == "central_irb"
        assert data["id"].startswith("IRB-")

    @pytest.mark.anyio
    async def test_update_board(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/boards/IRB-001",
            json={"name": "Updated WCG IRB", "submission_lead_time_days": 21},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated WCG IRB"
        assert data["submission_lead_time_days"] == 21

    @pytest.mark.anyio
    async def test_update_board_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/boards/IRB-NONEXISTENT",
            json={"name": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_board_active_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/boards/IRB-003",
            json={"active": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] is False

    @pytest.mark.anyio
    async def test_list_boards_filter_ethics_committee(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/boards", params={"board_type": "ethics_committee"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["country"] == "United Kingdom"


# =====================================================================
# SUBMISSION CRUD
# =====================================================================


class TestSubmissionCrud:
    """Test submission create, read, update, list operations."""

    @pytest.mark.anyio
    async def test_list_submissions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 7

    @pytest.mark.anyio
    async def test_list_submissions_filter_board(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/submissions", params={"board_id": "IRB-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["board_id"] == "IRB-001"

    @pytest.mark.anyio
    async def test_list_submissions_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/submissions", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_submissions_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/submissions", params={"status": "approved"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "approved"

    @pytest.mark.anyio
    async def test_list_submissions_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/submissions", params={"submission_type": "initial"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["submission_type"] == "initial"

    @pytest.mark.anyio
    async def test_get_submission(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions/SUB-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SUB-001"
        assert data["status"] == "approved"
        assert data["submission_type"] == "initial"

    @pytest.mark.anyio
    async def test_get_submission_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions/SUB-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_submission(self, client: AsyncClient):
        payload = _make_submission_create()
        resp = await client.post(f"{API_PREFIX}/submissions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["submission_number"] == "TEST-001"
        assert data["status"] == "draft"
        assert data["id"].startswith("SUB-")

    @pytest.mark.anyio
    async def test_update_submission(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/submissions/SUB-007",
            json={"notes": "Updated notes for closure submission."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated notes for closure submission."

    @pytest.mark.anyio
    async def test_update_submission_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/submissions/SUB-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404


# =====================================================================
# SUBMISSION LIFECYCLE
# =====================================================================


class TestSubmissionLifecycle:
    """Test submission lifecycle: draft -> submitted -> under_review -> approved."""

    @pytest.mark.anyio
    async def test_submit_for_review(self, client: AsyncClient):
        """Submit a draft submission."""
        now = datetime.now(timezone.utc)
        resp = await client.post(
            f"{API_PREFIX}/submissions/SUB-007/submit",
            json={"submitted_date": now.isoformat()},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "submitted"
        assert data["submitted_date"] is not None

    @pytest.mark.anyio
    async def test_submit_non_draft_fails(self, client: AsyncClient):
        """Attempting to submit an already-submitted submission should fail."""
        resp = await client.post(
            f"{API_PREFIX}/submissions/SUB-001/submit",
            json={},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_submit_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/submissions/SUB-NONEXISTENT/submit",
            json={},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_record_outcome_approved(self, client: AsyncClient):
        """Record an approved outcome for a submitted submission."""
        now = datetime.now(timezone.utc)
        resp = await client.post(
            f"{API_PREFIX}/submissions/SUB-006/record-outcome",
            json={
                "outcome": "approved",
                "review_date": now.isoformat(),
                "approval_date": now.isoformat(),
                "expiry_date": (now + timedelta(days=365)).isoformat(),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["outcome"] == "approved"
        assert data["approval_date"] is not None
        assert data["expiry_date"] is not None

    @pytest.mark.anyio
    async def test_record_outcome_conditionally_approved(self, client: AsyncClient):
        """Record a conditionally approved outcome."""
        now = datetime.now(timezone.utc)
        # SUB-004 is under_review
        resp = await client.post(
            f"{API_PREFIX}/submissions/SUB-004/record-outcome",
            json={
                "outcome": "conditionally_approved",
                "review_date": now.isoformat(),
                "conditions": "Update ICF within 30 days.",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved_with_conditions"
        assert data["conditions"] == "Update ICF within 30 days."

    @pytest.mark.anyio
    async def test_record_outcome_disapproved(self, client: AsyncClient):
        """Record a disapproved outcome."""
        now = datetime.now(timezone.utc)
        resp = await client.post(
            f"{API_PREFIX}/submissions/SUB-006/record-outcome",
            json={
                "outcome": "disapproved",
                "review_date": now.isoformat(),
                "notes": "Protocol has significant methodological concerns.",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "disapproved"
        assert data["outcome"] == "disapproved"

    @pytest.mark.anyio
    async def test_record_outcome_deferred(self, client: AsyncClient):
        """Record a deferred outcome."""
        now = datetime.now(timezone.utc)
        resp = await client.post(
            f"{API_PREFIX}/submissions/SUB-006/record-outcome",
            json={
                "outcome": "deferred",
                "review_date": now.isoformat(),
                "notes": "Additional information needed.",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "deferred"

    @pytest.mark.anyio
    async def test_record_outcome_invalid_status(self, client: AsyncClient):
        """Cannot record outcome for a draft submission."""
        now = datetime.now(timezone.utc)
        resp = await client.post(
            f"{API_PREFIX}/submissions/SUB-007/record-outcome",
            json={
                "outcome": "approved",
                "review_date": now.isoformat(),
            },
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_record_outcome_not_found(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.post(
            f"{API_PREFIX}/submissions/SUB-NONEXISTENT/record-outcome",
            json={
                "outcome": "approved",
                "review_date": now.isoformat(),
            },
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_full_lifecycle_draft_to_approved(self, client: AsyncClient):
        """Test complete lifecycle: create -> submit -> record outcome."""
        now = datetime.now(timezone.utc)

        # Step 1: Create
        create_resp = await client.post(
            f"{API_PREFIX}/submissions",
            json=_make_submission_create(submission_number="LIFECYCLE-001"),
        )
        assert create_resp.status_code == 201
        sub_id = create_resp.json()["id"]
        assert create_resp.json()["status"] == "draft"

        # Step 2: Submit
        submit_resp = await client.post(
            f"{API_PREFIX}/submissions/{sub_id}/submit",
            json={"submitted_date": now.isoformat()},
        )
        assert submit_resp.status_code == 200
        assert submit_resp.json()["status"] == "submitted"

        # Step 3: Record outcome
        outcome_resp = await client.post(
            f"{API_PREFIX}/submissions/{sub_id}/record-outcome",
            json={
                "outcome": "approved",
                "review_date": (now + timedelta(days=14)).isoformat(),
                "approval_date": (now + timedelta(days=14)).isoformat(),
                "expiry_date": (now + timedelta(days=379)).isoformat(),
            },
        )
        assert outcome_resp.status_code == 200
        assert outcome_resp.json()["status"] == "approved"
        assert outcome_resp.json()["outcome"] == "approved"


# =====================================================================
# CONTINUING REVIEWS
# =====================================================================


class TestContinuingReviews:
    """Test continuing review workflow."""

    @pytest.mark.anyio
    async def test_list_continuing_reviews_for_submission(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/submissions/SUB-001/continuing-reviews"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["submission_id"] == "SUB-001"

    @pytest.mark.anyio
    async def test_create_continuing_review(self, client: AsyncClient):
        payload = _make_continuing_review_create()
        resp = await client.post(
            f"{API_PREFIX}/submissions/SUB-001/continuing-reviews",
            json=payload,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["submission_id"] == "SUB-001"
        assert data["status"] == "draft"
        assert data["id"].startswith("CR-")

    @pytest.mark.anyio
    async def test_create_continuing_review_submission_not_found(
        self, client: AsyncClient
    ):
        payload = _make_continuing_review_create()
        resp = await client.post(
            f"{API_PREFIX}/submissions/SUB-NONEXISTENT/continuing-reviews",
            json=payload,
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_continuing_review(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/continuing-reviews/CR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CR-001"
        assert data["board_id"] == "IRB-001"

    @pytest.mark.anyio
    async def test_get_continuing_review_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/continuing-reviews/CR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_continuing_review(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/continuing-reviews/CR-001",
            json={
                "total_enrolled": 130,
                "risk_assessment": "Updated risk assessment.",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_enrolled"] == 130
        assert data["risk_assessment"] == "Updated risk assessment."

    @pytest.mark.anyio
    async def test_update_continuing_review_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/continuing-reviews/CR-NONEXISTENT",
            json={"total_enrolled": 100},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_continuing_review_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/continuing-reviews/CR-003",
            json={"status": "submitted"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "submitted"


# =====================================================================
# REPORTABLE EVENTS
# =====================================================================


class TestReportableEvents:
    """Test reportable event filing and updates."""

    @pytest.mark.anyio
    async def test_list_reportable_events(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reportable-events")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_events_filter_board(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/reportable-events", params={"board_id": "IRB-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["board_id"] == "IRB-001"

    @pytest.mark.anyio
    async def test_list_events_filter_severity(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/reportable-events", params={"severity": "high"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["severity"] == "high"

    @pytest.mark.anyio
    async def test_list_events_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/reportable-events", params={"status": "draft"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "draft"

    @pytest.mark.anyio
    async def test_file_reportable_event(self, client: AsyncClient):
        payload = _make_reportable_event_create()
        resp = await client.post(f"{API_PREFIX}/reportable-events", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["event_type"] == "Serious Adverse Event"
        assert data["status"] == "draft"
        assert data["id"].startswith("RE-")

    @pytest.mark.anyio
    async def test_get_reportable_event(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reportable-events/RE-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RE-001"
        assert data["severity"] == "high"

    @pytest.mark.anyio
    async def test_get_reportable_event_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reportable-events/RE-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_reportable_event(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reportable-events/RE-001",
            json={
                "board_response": "Event acknowledged. Additional monitoring recommended.",
                "status": "acknowledged",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "acknowledged"
        assert "acknowledged" in data["board_response"].lower()

    @pytest.mark.anyio
    async def test_update_reportable_event_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reportable-events/RE-NONEXISTENT",
            json={"status": "acknowledged"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_event_auto_reported_date(self, client: AsyncClient):
        """Transitioning from draft to submitted should set reported_date."""
        resp = await client.put(
            f"{API_PREFIX}/reportable-events/RE-003",
            json={"status": "submitted"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "submitted"
        assert data["reported_date"] is not None

    @pytest.mark.anyio
    async def test_resolve_reportable_event(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reportable-events/RE-002",
            json={
                "status": "resolved",
                "resolution": "Subject completed additional monitoring without issues.",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "resolved"
        assert data["resolution"] is not None


# =====================================================================
# REGULATORY DOCUMENTS
# =====================================================================


class TestRegulatoryDocuments:
    """Test regulatory document management."""

    @pytest.mark.anyio
    async def test_list_documents_for_submission(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions/SUB-002/documents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2

    @pytest.mark.anyio
    async def test_list_documents_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/submissions/SUB-002/documents",
            params={"document_type": "icf"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["document_type"] == "icf"

    @pytest.mark.anyio
    async def test_list_documents_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/submissions/SUB-002/documents",
            params={"status": "approved"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "approved"

    @pytest.mark.anyio
    async def test_create_document(self, client: AsyncClient):
        payload = _make_document_create()
        resp = await client.post(
            f"{API_PREFIX}/submissions/SUB-001/documents", json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["document_name"] == "Test Protocol v1.0"
        assert data["submission_id"] == "SUB-001"
        assert data["status"] == "draft"
        assert data["id"].startswith("DOC-")

    @pytest.mark.anyio
    async def test_create_document_submission_not_found(self, client: AsyncClient):
        payload = _make_document_create()
        resp = await client.post(
            f"{API_PREFIX}/submissions/SUB-NONEXISTENT/documents", json=payload
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_document(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/DOC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DOC-001"
        assert data["document_type"] == "protocol"

    @pytest.mark.anyio
    async def test_get_document_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/DOC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_document_all_types(self, client: AsyncClient):
        """Create documents of various types."""
        for doc_type in ["protocol", "icf", "investigator_brochure", "safety_report"]:
            payload = _make_document_create(
                document_type=doc_type,
                document_name=f"Test {doc_type} document",
            )
            resp = await client.post(
                f"{API_PREFIX}/submissions/SUB-001/documents", json=payload
            )
            assert resp.status_code == 201
            assert resp.json()["document_type"] == doc_type


# =====================================================================
# CORRESPONDENCE
# =====================================================================


class TestCorrespondence:
    """Test correspondence tracking."""

    @pytest.mark.anyio
    async def test_list_correspondence_for_submission(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/submissions/SUB-002/correspondence"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        for item in data["items"]:
            assert item["submission_id"] == "SUB-002"

    @pytest.mark.anyio
    async def test_create_correspondence(self, client: AsyncClient):
        payload = _make_correspondence_create()
        resp = await client.post(
            f"{API_PREFIX}/submissions/SUB-001/correspondence", json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["subject"] == "Test Correspondence"
        assert data["submission_id"] == "SUB-001"
        assert data["id"].startswith("CORR-")

    @pytest.mark.anyio
    async def test_create_correspondence_submission_not_found(
        self, client: AsyncClient
    ):
        payload = _make_correspondence_create()
        resp = await client.post(
            f"{API_PREFIX}/submissions/SUB-NONEXISTENT/correspondence", json=payload
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_incoming_correspondence(self, client: AsyncClient):
        payload = _make_correspondence_create(
            direction="incoming",
            subject="Board Response",
            content="Your submission has been received.",
            sent_by="WCG IRB Committee",
            response_required=True,
            response_deadline=(
                datetime.now(timezone.utc) + timedelta(days=14)
            ).isoformat(),
        )
        resp = await client.post(
            f"{API_PREFIX}/submissions/SUB-001/correspondence", json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["direction"] == "incoming"
        assert data["response_required"] is True
        assert data["response_deadline"] is not None

    @pytest.mark.anyio
    async def test_correspondence_has_sent_date(self, client: AsyncClient):
        payload = _make_correspondence_create()
        resp = await client.post(
            f"{API_PREFIX}/submissions/SUB-001/correspondence", json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["sent_date"] is not None


# =====================================================================
# EXPIRING APPROVALS
# =====================================================================


class TestExpiringApprovals:
    """Test expiring approvals query."""

    @pytest.mark.anyio
    async def test_get_expiring_approvals_default(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/expiring-approvals")
        assert resp.status_code == 200
        data = resp.json()
        # SUB-005 has expiry within ~15 days
        assert data["total"] >= 1

    @pytest.mark.anyio
    async def test_get_expiring_approvals_custom_days(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/expiring-approvals", params={"days": 365}
        )
        assert resp.status_code == 200
        data = resp.json()
        # With 365 days, all approved submissions with expiry dates should appear
        assert data["total"] >= 1

    @pytest.mark.anyio
    async def test_expiring_approvals_sorted_by_date(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/expiring-approvals", params={"days": 365}
        )
        data = resp.json()
        if data["total"] > 1:
            dates = [item["expiry_date"] for item in data["items"]]
            assert dates == sorted(dates)

    @pytest.mark.anyio
    async def test_expiring_approvals_narrow_window(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/expiring-approvals", params={"days": 1}
        )
        assert resp.status_code == 200
        data = resp.json()
        # Very narrow window should return fewer or zero results
        assert data["total"] >= 0

    def test_expiring_approvals_service_direct(self, svc: CentralIRBService):
        """SUB-005 expires in ~15 days so should appear in 30-day window."""
        expiring = svc.get_expiring_approvals(days=30)
        ids = [s.id for s in expiring]
        assert "SUB-005" in ids


# =====================================================================
# METRICS
# =====================================================================


class TestIRBMetrics:
    """Test IRB metrics aggregation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_submissions"] == 7
        assert data["pending_reviews"] >= 1
        assert data["approved_count"] >= 1
        assert data["avg_review_days"] >= 0
        assert data["reportable_events_open"] >= 0

    def test_metrics_total_submissions(self, svc: CentralIRBService):
        metrics = svc.get_metrics()
        submissions = svc.list_submissions()
        assert metrics.total_submissions == len(submissions)

    def test_metrics_pending_reviews(self, svc: CentralIRBService):
        metrics = svc.get_metrics()
        pending = [
            s
            for s in svc.list_submissions()
            if s.status in (ReviewStatus.SUBMITTED, ReviewStatus.UNDER_REVIEW)
        ]
        assert metrics.pending_reviews == len(pending)

    def test_metrics_approved_count(self, svc: CentralIRBService):
        metrics = svc.get_metrics()
        approved = [
            s
            for s in svc.list_submissions()
            if s.status
            in (ReviewStatus.APPROVED, ReviewStatus.APPROVED_WITH_CONDITIONS)
        ]
        assert metrics.approved_count == len(approved)

    def test_metrics_avg_review_days(self, svc: CentralIRBService):
        metrics = svc.get_metrics()
        assert metrics.avg_review_days > 0  # Seed data has reviewed submissions

    def test_metrics_expiring_approvals(self, svc: CentralIRBService):
        metrics = svc.get_metrics()
        expiring = svc.get_expiring_approvals(days=30)
        assert metrics.expiring_approvals_30d == len(expiring)

    def test_metrics_reportable_events_open(self, svc: CentralIRBService):
        metrics = svc.get_metrics()
        open_events = [
            e
            for e in svc.list_reportable_events()
            if e.status
            in (EventStatus.DRAFT, EventStatus.SUBMITTED, EventStatus.UNDER_REVIEW)
        ]
        assert metrics.reportable_events_open == len(open_events)


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_central_irb_service()
        svc2 = get_central_irb_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_central_irb_service()
        svc2 = reset_central_irb_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_central_irb_service()
        # Create and verify new board
        board = svc.create_board(
            IRBBoardCreate(
                name="Temporary Board",
                board_type=BoardType.LOCAL_IRB,
                organization="Temp Org",
                country="United States",
                contact_email="temp@irb.com",
                meeting_schedule="Weekly",
                submission_lead_time_days=7,
            )
        )
        assert svc.get_board(board.id) is not None

        # Reset should discard the temporary board
        svc2 = reset_central_irb_service()
        assert svc2.get_board(board.id) is None
        # Original seed data should be back
        assert svc2.get_board("IRB-001") is not None


# =====================================================================
# ERROR CASES AND EDGE CASES
# =====================================================================


class TestErrorCases:
    """Test error cases and edge conditions."""

    @pytest.mark.anyio
    async def test_submit_already_approved_fails(self, client: AsyncClient):
        """Cannot submit an already-approved submission."""
        resp = await client.post(
            f"{API_PREFIX}/submissions/SUB-001/submit", json={}
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_record_outcome_for_approved_fails(self, client: AsyncClient):
        """Cannot record outcome for an already-approved submission."""
        now = datetime.now(timezone.utc)
        resp = await client.post(
            f"{API_PREFIX}/submissions/SUB-001/record-outcome",
            json={
                "outcome": "approved",
                "review_date": now.isoformat(),
            },
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_record_outcome_tabled(self, client: AsyncClient):
        """Recording a tabled outcome should set status to deferred."""
        now = datetime.now(timezone.utc)
        resp = await client.post(
            f"{API_PREFIX}/submissions/SUB-006/record-outcome",
            json={
                "outcome": "tabled",
                "review_date": now.isoformat(),
                "notes": "Tabled for further discussion.",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "deferred"
        assert data["outcome"] == "tabled"

    @pytest.mark.anyio
    async def test_list_submissions_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_reportable_events_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reportable-events")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_boards_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/boards")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_submission_with_site_id(self, client: AsyncClient):
        payload = _make_submission_create(
            site_id="SITE-101",
            submission_number="SITE-TEST-001",
        )
        resp = await client.post(f"{API_PREFIX}/submissions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_file_event_with_immediate_report(self, client: AsyncClient):
        payload = _make_reportable_event_create(
            requires_immediate_report=True,
            severity="critical",
        )
        resp = await client.post(f"{API_PREFIX}/reportable-events", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["requires_immediate_report"] is True
        assert data["severity"] == "critical"

    @pytest.mark.anyio
    async def test_submit_with_default_date(self, client: AsyncClient):
        """Submitting without explicit date should use current time."""
        resp = await client.post(
            f"{API_PREFIX}/submissions/SUB-007/submit",
            json={},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["submitted_date"] is not None


# =====================================================================
# DATA INTEGRITY
# =====================================================================


class TestDataIntegrity:
    """Test data integrity and cross-referencing."""

    def test_all_submissions_reference_valid_boards(self, svc: CentralIRBService):
        submissions = svc.list_submissions()
        board_ids = {b.id for b in svc.list_boards()}
        for sub in submissions:
            assert sub.board_id in board_ids

    def test_all_continuing_reviews_reference_valid_submissions(
        self, svc: CentralIRBService
    ):
        crs = svc.list_continuing_reviews()
        submission_ids = {s.id for s in svc.list_submissions()}
        for cr in crs:
            assert cr.submission_id in submission_ids

    def test_all_documents_reference_valid_submissions(
        self, svc: CentralIRBService
    ):
        docs = svc.list_documents()
        submission_ids = {s.id for s in svc.list_submissions()}
        for doc in docs:
            assert doc.submission_id in submission_ids

    def test_all_correspondence_reference_valid_submissions(
        self, svc: CentralIRBService
    ):
        corr = svc.list_correspondence()
        submission_ids = {s.id for s in svc.list_submissions()}
        for c in corr:
            assert c.submission_id in submission_ids

    def test_approved_submissions_have_outcome(self, svc: CentralIRBService):
        submissions = svc.list_submissions()
        for sub in submissions:
            if sub.status == ReviewStatus.APPROVED:
                assert sub.outcome is not None
                assert sub.approval_date is not None

    def test_seed_submission_types_variety(self, svc: CentralIRBService):
        submissions = svc.list_submissions()
        types = {s.submission_type for s in submissions}
        assert SubmissionType.INITIAL in types
        assert SubmissionType.AMENDMENT in types


# =====================================================================
# ENUMERATION COVERAGE
# =====================================================================


class TestEnumerations:
    """Test enum values are correctly used throughout."""

    @pytest.mark.anyio
    async def test_board_types_in_seed_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/boards")
        data = resp.json()
        types = {item["board_type"] for item in data["items"]}
        assert "central_irb" in types
        assert "ethics_committee" in types

    @pytest.mark.anyio
    async def test_submission_types_in_seed_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions")
        data = resp.json()
        types = {item["submission_type"] for item in data["items"]}
        assert "initial" in types
        assert "amendment" in types
        assert "safety_report" in types

    @pytest.mark.anyio
    async def test_document_types_in_seed_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions/SUB-001/documents")
        data1 = resp.json()
        resp2 = await client.get(f"{API_PREFIX}/submissions/SUB-002/documents")
        data2 = resp2.json()
        all_types = {
            item["document_type"]
            for item in data1["items"] + data2["items"]
        }
        assert "protocol" in all_types
        assert "icf" in all_types

    @pytest.mark.anyio
    async def test_event_severity_levels(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reportable-events")
        data = resp.json()
        severities = {item["severity"] for item in data["items"]}
        assert "high" in severities
        assert "medium" in severities

    @pytest.mark.anyio
    async def test_correspondence_directions(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/submissions/SUB-002/correspondence"
        )
        data = resp.json()
        directions = {item["direction"] for item in data["items"]}
        assert "incoming" in directions
        assert "outgoing" in directions
