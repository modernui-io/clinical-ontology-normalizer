"""Tests for Regulatory Submission Tracking (CLO-5).

Covers:
- Submission CRUD (create, read, update, delete, list with all filter combinations)
- Status transition validation
- Submit workflow (transition to SUBMITTED with timestamp)
- Record response workflow
- Milestone CRUD (create, read, update, delete, list)
- Milestone auto-completion date
- Regulatory calendar (upcoming, overdue, awaiting response)
- Submission metrics computation
- Information request retrieval
- Deadline checking
- Seed data verification
- API endpoint integration tests
- Edge cases (non-existent records, invalid transitions, pagination)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.regulatory_submissions import (
    MilestoneCreate,
    MilestoneStatus,
    MilestoneUpdate,
    RecordResponseRequest,
    RegulatoryBody,
    SubmissionCreate,
    SubmissionPriority,
    SubmissionStatus,
    SubmissionType,
    SubmissionUpdate,
)
from app.services.regulatory_submission_service import (
    RegulatorySubmissionService,
    get_regulatory_submission_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/regulatory-submissions"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_service():
    """Ensure a fresh service for every test."""
    svc = get_regulatory_submission_service()
    svc.clear()
    yield svc
    svc.clear()


@pytest.fixture
def svc(clean_service) -> RegulatorySubmissionService:
    """Shorthand for the clean service."""
    return clean_service


def _make_create(
    trial_id: str = EYLEA_TRIAL,
    submission_type: SubmissionType = SubmissionType.IND,
    regulatory_body: RegulatoryBody = RegulatoryBody.FDA,
    priority: SubmissionPriority = SubmissionPriority.STANDARD,
    **kwargs,
) -> SubmissionCreate:
    """Helper to build a SubmissionCreate with defaults."""
    defaults = dict(
        title="Test IND Submission",
        submission_type=submission_type,
        regulatory_body=regulatory_body,
        trial_id=trial_id,
        priority=priority,
        assigned_to="Dr. Test",
        reviewer="Dr. Review",
        notes="Test notes",
    )
    defaults.update(kwargs)
    return SubmissionCreate(**defaults)


def _seed_varied(svc: RegulatorySubmissionService) -> list[str]:
    """Seed a variety of submissions and return their IDs."""
    ids = []
    configs = [
        (EYLEA_TRIAL, SubmissionType.IND, RegulatoryBody.FDA, SubmissionPriority.HIGH),
        (EYLEA_TRIAL, SubmissionType.ANNUAL_REPORT, RegulatoryBody.FDA, SubmissionPriority.STANDARD),
        (DUPIXENT_TRIAL, SubmissionType.PROTOCOL_AMENDMENT, RegulatoryBody.EMA, SubmissionPriority.HIGH),
        (DUPIXENT_TRIAL, SubmissionType.IND, RegulatoryBody.MHRA, SubmissionPriority.URGENT),
        (LIBTAYO_TRIAL, SubmissionType.IRB_APPROVAL, RegulatoryBody.FDA, SubmissionPriority.STANDARD),
        (LIBTAYO_TRIAL, SubmissionType.DSMB_REPORT, RegulatoryBody.FDA, SubmissionPriority.URGENT),
    ]
    for trial_id, stype, body, pri in configs:
        rec = svc.create_submission(_make_create(
            trial_id=trial_id,
            submission_type=stype,
            regulatory_body=body,
            priority=pri,
            title=f"{stype.value} - {body.value}",
        ))
        ids.append(rec.id)
    return ids


# ===========================================================================
# 1. Submission CRUD - Create
# ===========================================================================


class TestSubmissionCreate:
    """Tests for create_submission."""

    def test_create_basic(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        assert rec.id.startswith("SUB-")
        assert rec.trial_id == EYLEA_TRIAL
        assert rec.status == SubmissionStatus.DRAFTING
        assert rec.submission_type == SubmissionType.IND
        assert rec.regulatory_body == RegulatoryBody.FDA
        assert rec.created_at is not None
        assert rec.updated_at is not None

    def test_create_sets_timestamps(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        delta = (datetime.now(timezone.utc) - rec.created_at).total_seconds()
        assert delta < 5

    def test_create_initial_status_is_drafting(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        assert rec.status == SubmissionStatus.DRAFTING

    def test_create_preserves_assigned_to(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create(assigned_to="Dr. Specific"))
        assert rec.assigned_to == "Dr. Specific"

    def test_create_preserves_reviewer(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create(reviewer="Dr. Reviewer"))
        assert rec.reviewer == "Dr. Reviewer"

    def test_create_preserves_notes(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create(notes="Important note"))
        assert rec.notes == "Important note"

    def test_create_preserves_priority(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create(priority=SubmissionPriority.URGENT))
        assert rec.priority == SubmissionPriority.URGENT

    def test_create_no_submitted_date(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        assert rec.submitted_date is None

    def test_create_empty_documents(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        assert rec.documents == []

    def test_create_no_reference_number(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        assert rec.reference_number is None


# ===========================================================================
# 2. Submission CRUD - Read
# ===========================================================================


class TestSubmissionRead:
    """Tests for get_submission."""

    def test_get_existing(self, svc: RegulatorySubmissionService):
        created = svc.create_submission(_make_create())
        fetched = svc.get_submission(created.id)
        assert fetched.id == created.id
        assert fetched.title == created.title

    def test_get_nonexistent(self, svc: RegulatorySubmissionService):
        with pytest.raises(KeyError, match="not found"):
            svc.get_submission("SUB-DOES-NOT-EXIST")


# ===========================================================================
# 3. Submission CRUD - Update
# ===========================================================================


class TestSubmissionUpdate:
    """Tests for update_submission."""

    def test_update_title(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        updated = svc.update_submission(rec.id, SubmissionUpdate(title="New Title"))
        assert updated.title == "New Title"

    def test_update_priority(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        updated = svc.update_submission(rec.id, SubmissionUpdate(priority=SubmissionPriority.URGENT))
        assert updated.priority == SubmissionPriority.URGENT

    def test_update_assigned_to(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        updated = svc.update_submission(rec.id, SubmissionUpdate(assigned_to="Dr. New"))
        assert updated.assigned_to == "Dr. New"

    def test_update_reviewer(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        updated = svc.update_submission(rec.id, SubmissionUpdate(reviewer="Dr. NewReviewer"))
        assert updated.reviewer == "Dr. NewReviewer"

    def test_update_reference_number(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        updated = svc.update_submission(rec.id, SubmissionUpdate(reference_number="IND-999"))
        assert updated.reference_number == "IND-999"

    def test_update_notes(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        updated = svc.update_submission(rec.id, SubmissionUpdate(notes="Updated notes"))
        assert updated.notes == "Updated notes"

    def test_update_sets_updated_at(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        old = rec.updated_at
        updated = svc.update_submission(rec.id, SubmissionUpdate(title="Changed"))
        assert updated.updated_at >= old

    def test_update_nonexistent(self, svc: RegulatorySubmissionService):
        with pytest.raises(KeyError, match="not found"):
            svc.update_submission("SUB-NOPE", SubmissionUpdate(title="X"))

    def test_update_valid_status_transition(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        updated = svc.update_submission(
            rec.id, SubmissionUpdate(status=SubmissionStatus.INTERNAL_REVIEW)
        )
        assert updated.status == SubmissionStatus.INTERNAL_REVIEW

    def test_update_invalid_status_transition(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        with pytest.raises(ValueError, match="Invalid status transition"):
            svc.update_submission(
                rec.id, SubmissionUpdate(status=SubmissionStatus.APPROVED)
            )


# ===========================================================================
# 4. Submission CRUD - Delete
# ===========================================================================


class TestSubmissionDelete:
    """Tests for delete_submission."""

    def test_delete_existing(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        svc.delete_submission(rec.id)
        with pytest.raises(KeyError, match="not found"):
            svc.get_submission(rec.id)

    def test_delete_removes_milestones(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        ms = svc.create_milestone(
            rec.id,
            MilestoneCreate(
                milestone_name="Test",
                due_date=datetime.now(timezone.utc) + timedelta(days=10),
            ),
        )
        svc.delete_submission(rec.id)
        with pytest.raises(KeyError, match="not found"):
            svc.get_milestone(ms.id)

    def test_delete_nonexistent(self, svc: RegulatorySubmissionService):
        with pytest.raises(KeyError, match="not found"):
            svc.delete_submission("SUB-NOPE")


# ===========================================================================
# 5. Submission CRUD - List
# ===========================================================================


class TestSubmissionList:
    """Tests for list_submissions with filters."""

    def test_list_empty(self, svc: RegulatorySubmissionService):
        items, total = svc.list_submissions()
        assert total == 0
        assert items == []

    def test_list_all(self, svc: RegulatorySubmissionService):
        ids = _seed_varied(svc)
        items, total = svc.list_submissions()
        assert total == len(ids)
        assert len(items) == len(ids)

    def test_list_filter_trial_id(self, svc: RegulatorySubmissionService):
        _seed_varied(svc)
        items, total = svc.list_submissions(trial_id=EYLEA_TRIAL)
        assert total == 2
        assert all(s.trial_id == EYLEA_TRIAL for s in items)

    def test_list_filter_submission_type(self, svc: RegulatorySubmissionService):
        _seed_varied(svc)
        items, total = svc.list_submissions(submission_type=SubmissionType.IND)
        assert total == 2
        assert all(s.submission_type == SubmissionType.IND for s in items)

    def test_list_filter_regulatory_body(self, svc: RegulatorySubmissionService):
        _seed_varied(svc)
        items, total = svc.list_submissions(regulatory_body=RegulatoryBody.EMA)
        assert total == 1
        assert items[0].regulatory_body == RegulatoryBody.EMA

    def test_list_filter_priority(self, svc: RegulatorySubmissionService):
        _seed_varied(svc)
        items, total = svc.list_submissions(priority=SubmissionPriority.URGENT)
        assert total == 2
        assert all(s.priority == SubmissionPriority.URGENT for s in items)

    def test_list_pagination_limit(self, svc: RegulatorySubmissionService):
        _seed_varied(svc)
        items, total = svc.list_submissions(limit=2)
        assert len(items) == 2
        assert total == 6

    def test_list_pagination_offset(self, svc: RegulatorySubmissionService):
        _seed_varied(svc)
        items, total = svc.list_submissions(limit=2, offset=4)
        assert len(items) == 2
        assert total == 6

    def test_list_pagination_past_end(self, svc: RegulatorySubmissionService):
        _seed_varied(svc)
        items, total = svc.list_submissions(limit=10, offset=100)
        assert len(items) == 0
        assert total == 6


# ===========================================================================
# 6. Status Transition Validation
# ===========================================================================


class TestStatusTransitions:
    """Tests for valid and invalid status transitions."""

    def test_drafting_to_internal_review(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        updated = svc.update_submission(
            rec.id, SubmissionUpdate(status=SubmissionStatus.INTERNAL_REVIEW)
        )
        assert updated.status == SubmissionStatus.INTERNAL_REVIEW

    def test_drafting_to_withdrawn(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        updated = svc.update_submission(
            rec.id, SubmissionUpdate(status=SubmissionStatus.WITHDRAWN)
        )
        assert updated.status == SubmissionStatus.WITHDRAWN

    def test_drafting_to_submitted_invalid(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        with pytest.raises(ValueError, match="Invalid status transition"):
            svc.update_submission(
                rec.id, SubmissionUpdate(status=SubmissionStatus.SUBMITTED)
            )

    def test_internal_review_to_submitted(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.INTERNAL_REVIEW))
        updated = svc.update_submission(
            rec.id, SubmissionUpdate(status=SubmissionStatus.SUBMITTED)
        )
        assert updated.status == SubmissionStatus.SUBMITTED

    def test_internal_review_back_to_drafting(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.INTERNAL_REVIEW))
        updated = svc.update_submission(
            rec.id, SubmissionUpdate(status=SubmissionStatus.DRAFTING)
        )
        assert updated.status == SubmissionStatus.DRAFTING

    def test_submitted_to_under_review(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.INTERNAL_REVIEW))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.SUBMITTED))
        updated = svc.update_submission(
            rec.id, SubmissionUpdate(status=SubmissionStatus.UNDER_REVIEW)
        )
        assert updated.status == SubmissionStatus.UNDER_REVIEW

    def test_under_review_to_approved(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.INTERNAL_REVIEW))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.SUBMITTED))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.UNDER_REVIEW))
        updated = svc.update_submission(
            rec.id, SubmissionUpdate(status=SubmissionStatus.APPROVED)
        )
        assert updated.status == SubmissionStatus.APPROVED

    def test_under_review_to_rejected(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.INTERNAL_REVIEW))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.SUBMITTED))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.UNDER_REVIEW))
        updated = svc.update_submission(
            rec.id, SubmissionUpdate(status=SubmissionStatus.REJECTED)
        )
        assert updated.status == SubmissionStatus.REJECTED

    def test_under_review_to_information_request(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.INTERNAL_REVIEW))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.SUBMITTED))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.UNDER_REVIEW))
        updated = svc.update_submission(
            rec.id, SubmissionUpdate(status=SubmissionStatus.INFORMATION_REQUEST)
        )
        assert updated.status == SubmissionStatus.INFORMATION_REQUEST

    def test_approved_is_terminal(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.INTERNAL_REVIEW))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.SUBMITTED))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.UNDER_REVIEW))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.APPROVED))
        with pytest.raises(ValueError, match="Invalid status transition"):
            svc.update_submission(
                rec.id, SubmissionUpdate(status=SubmissionStatus.WITHDRAWN)
            )

    def test_withdrawn_is_terminal(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.WITHDRAWN))
        with pytest.raises(ValueError, match="Invalid status transition"):
            svc.update_submission(
                rec.id, SubmissionUpdate(status=SubmissionStatus.DRAFTING)
            )

    def test_rejected_can_go_to_drafting(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.INTERNAL_REVIEW))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.SUBMITTED))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.UNDER_REVIEW))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.REJECTED))
        updated = svc.update_submission(
            rec.id, SubmissionUpdate(status=SubmissionStatus.DRAFTING)
        )
        assert updated.status == SubmissionStatus.DRAFTING

    def test_information_request_to_under_review(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.INTERNAL_REVIEW))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.SUBMITTED))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.UNDER_REVIEW))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.INFORMATION_REQUEST))
        updated = svc.update_submission(
            rec.id, SubmissionUpdate(status=SubmissionStatus.UNDER_REVIEW)
        )
        assert updated.status == SubmissionStatus.UNDER_REVIEW


# ===========================================================================
# 7. Submit Workflow
# ===========================================================================


class TestSubmitWorkflow:
    """Tests for the submit() method."""

    def test_submit_from_internal_review(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.INTERNAL_REVIEW))
        submitted = svc.submit(rec.id)
        assert submitted.status == SubmissionStatus.SUBMITTED
        assert submitted.submitted_date is not None

    def test_submit_sets_date_stamp(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.INTERNAL_REVIEW))
        submitted = svc.submit(rec.id)
        delta = (datetime.now(timezone.utc) - submitted.submitted_date).total_seconds()
        assert delta < 5

    def test_submit_from_drafting_fails(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        with pytest.raises(ValueError, match="Cannot submit"):
            svc.submit(rec.id)

    def test_submit_from_approved_fails(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.INTERNAL_REVIEW))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.SUBMITTED))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.UNDER_REVIEW))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.APPROVED))
        with pytest.raises(ValueError, match="Cannot submit"):
            svc.submit(rec.id)

    def test_submit_nonexistent(self, svc: RegulatorySubmissionService):
        with pytest.raises(KeyError, match="not found"):
            svc.submit("SUB-NOPE")

    def test_submit_from_information_request(self, svc: RegulatorySubmissionService):
        """After an info request, re-submission is allowed."""
        rec = svc.create_submission(_make_create())
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.INTERNAL_REVIEW))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.SUBMITTED))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.UNDER_REVIEW))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.INFORMATION_REQUEST))
        submitted = svc.submit(rec.id)
        assert submitted.status == SubmissionStatus.SUBMITTED


# ===========================================================================
# 8. Record Response Workflow
# ===========================================================================


class TestRecordResponse:
    """Tests for record_response."""

    def _get_under_review(self, svc):
        rec = svc.create_submission(_make_create())
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.INTERNAL_REVIEW))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.SUBMITTED))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.UNDER_REVIEW))
        return rec.id

    def test_record_approval(self, svc: RegulatorySubmissionService):
        sub_id = self._get_under_review(svc)
        result = svc.record_response(
            sub_id, RecordResponseRequest(status=SubmissionStatus.APPROVED, notes="Approved")
        )
        assert result.status == SubmissionStatus.APPROVED
        assert result.actual_response_date is not None

    def test_record_rejection(self, svc: RegulatorySubmissionService):
        sub_id = self._get_under_review(svc)
        result = svc.record_response(
            sub_id, RecordResponseRequest(status=SubmissionStatus.REJECTED, notes="Rejected")
        )
        assert result.status == SubmissionStatus.REJECTED

    def test_record_info_request(self, svc: RegulatorySubmissionService):
        sub_id = self._get_under_review(svc)
        result = svc.record_response(
            sub_id, RecordResponseRequest(status=SubmissionStatus.INFORMATION_REQUEST, notes="Need more data")
        )
        assert result.status == SubmissionStatus.INFORMATION_REQUEST

    def test_record_response_appends_notes(self, svc: RegulatorySubmissionService):
        sub_id = self._get_under_review(svc)
        result = svc.record_response(
            sub_id, RecordResponseRequest(status=SubmissionStatus.APPROVED, notes="Good submission")
        )
        assert "[Response] Good submission" in result.notes

    def test_record_response_invalid_transition(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        with pytest.raises(ValueError, match="Invalid response status transition"):
            svc.record_response(
                rec.id, RecordResponseRequest(status=SubmissionStatus.APPROVED)
            )

    def test_record_response_nonexistent(self, svc: RegulatorySubmissionService):
        with pytest.raises(KeyError, match="not found"):
            svc.record_response(
                "SUB-NOPE", RecordResponseRequest(status=SubmissionStatus.APPROVED)
            )


# ===========================================================================
# 9. Milestone CRUD - Create
# ===========================================================================


class TestMilestoneCreate:
    """Tests for create_milestone."""

    def test_create_basic(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        ms = svc.create_milestone(
            sub.id,
            MilestoneCreate(
                milestone_name="Draft review",
                due_date=datetime.now(timezone.utc) + timedelta(days=7),
                responsible="Dr. Test",
            ),
        )
        assert ms.id.startswith("MS-")
        assert ms.submission_id == sub.id
        assert ms.milestone_name == "Draft review"
        assert ms.status == MilestoneStatus.PENDING
        assert ms.responsible == "Dr. Test"

    def test_create_for_nonexistent_submission(self, svc: RegulatorySubmissionService):
        with pytest.raises(KeyError, match="not found"):
            svc.create_milestone(
                "SUB-NOPE",
                MilestoneCreate(
                    milestone_name="Test",
                    due_date=datetime.now(timezone.utc) + timedelta(days=1),
                ),
            )


# ===========================================================================
# 10. Milestone CRUD - Read
# ===========================================================================


class TestMilestoneRead:
    """Tests for get_milestone."""

    def test_get_existing(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        ms = svc.create_milestone(
            sub.id,
            MilestoneCreate(
                milestone_name="Test",
                due_date=datetime.now(timezone.utc) + timedelta(days=5),
            ),
        )
        fetched = svc.get_milestone(ms.id)
        assert fetched.id == ms.id

    def test_get_nonexistent(self, svc: RegulatorySubmissionService):
        with pytest.raises(KeyError, match="not found"):
            svc.get_milestone("MS-NOPE")


# ===========================================================================
# 11. Milestone CRUD - Update
# ===========================================================================


class TestMilestoneUpdate:
    """Tests for update_milestone."""

    def test_update_name(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        ms = svc.create_milestone(
            sub.id,
            MilestoneCreate(
                milestone_name="Original",
                due_date=datetime.now(timezone.utc) + timedelta(days=10),
            ),
        )
        updated = svc.update_milestone(ms.id, MilestoneUpdate(milestone_name="Renamed"))
        assert updated.milestone_name == "Renamed"

    def test_update_status_to_completed(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        ms = svc.create_milestone(
            sub.id,
            MilestoneCreate(
                milestone_name="Task",
                due_date=datetime.now(timezone.utc) + timedelta(days=5),
            ),
        )
        updated = svc.update_milestone(ms.id, MilestoneUpdate(status=MilestoneStatus.COMPLETED))
        assert updated.status == MilestoneStatus.COMPLETED

    def test_update_auto_sets_completed_date(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        ms = svc.create_milestone(
            sub.id,
            MilestoneCreate(
                milestone_name="Task",
                due_date=datetime.now(timezone.utc) + timedelta(days=5),
            ),
        )
        updated = svc.update_milestone(ms.id, MilestoneUpdate(status=MilestoneStatus.COMPLETED))
        assert updated.completed_date is not None
        delta = (datetime.now(timezone.utc) - updated.completed_date).total_seconds()
        assert delta < 5

    def test_update_waived(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        ms = svc.create_milestone(
            sub.id,
            MilestoneCreate(
                milestone_name="Optional",
                due_date=datetime.now(timezone.utc) + timedelta(days=5),
            ),
        )
        updated = svc.update_milestone(ms.id, MilestoneUpdate(status=MilestoneStatus.WAIVED))
        assert updated.status == MilestoneStatus.WAIVED

    def test_update_responsible(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        ms = svc.create_milestone(
            sub.id,
            MilestoneCreate(
                milestone_name="Task",
                due_date=datetime.now(timezone.utc) + timedelta(days=5),
            ),
        )
        updated = svc.update_milestone(ms.id, MilestoneUpdate(responsible="New Person"))
        assert updated.responsible == "New Person"

    def test_update_due_date(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        new_date = datetime.now(timezone.utc) + timedelta(days=20)
        ms = svc.create_milestone(
            sub.id,
            MilestoneCreate(
                milestone_name="Task",
                due_date=datetime.now(timezone.utc) + timedelta(days=5),
            ),
        )
        updated = svc.update_milestone(ms.id, MilestoneUpdate(due_date=new_date))
        assert updated.due_date == new_date

    def test_update_nonexistent(self, svc: RegulatorySubmissionService):
        with pytest.raises(KeyError, match="not found"):
            svc.update_milestone("MS-NOPE", MilestoneUpdate(milestone_name="X"))


# ===========================================================================
# 12. Milestone CRUD - Delete
# ===========================================================================


class TestMilestoneDelete:
    """Tests for delete_milestone."""

    def test_delete_existing(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        ms = svc.create_milestone(
            sub.id,
            MilestoneCreate(
                milestone_name="Delete me",
                due_date=datetime.now(timezone.utc) + timedelta(days=5),
            ),
        )
        svc.delete_milestone(ms.id)
        with pytest.raises(KeyError, match="not found"):
            svc.get_milestone(ms.id)

    def test_delete_nonexistent(self, svc: RegulatorySubmissionService):
        with pytest.raises(KeyError, match="not found"):
            svc.delete_milestone("MS-NOPE")


# ===========================================================================
# 13. Milestone List
# ===========================================================================


class TestMilestoneList:
    """Tests for list_milestones."""

    def test_list_empty(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        items = svc.list_milestones(sub.id)
        assert items == []

    def test_list_multiple(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        for i in range(3):
            svc.create_milestone(
                sub.id,
                MilestoneCreate(
                    milestone_name=f"MS {i}",
                    due_date=datetime.now(timezone.utc) + timedelta(days=i + 1),
                ),
            )
        items = svc.list_milestones(sub.id)
        assert len(items) == 3

    def test_list_sorted_by_due_date(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        now = datetime.now(timezone.utc)
        svc.create_milestone(
            sub.id,
            MilestoneCreate(milestone_name="Later", due_date=now + timedelta(days=10)),
        )
        svc.create_milestone(
            sub.id,
            MilestoneCreate(milestone_name="Sooner", due_date=now + timedelta(days=1)),
        )
        items = svc.list_milestones(sub.id)
        assert items[0].milestone_name == "Sooner"
        assert items[1].milestone_name == "Later"

    def test_list_for_nonexistent_submission(self, svc: RegulatorySubmissionService):
        with pytest.raises(KeyError, match="not found"):
            svc.list_milestones("SUB-NOPE")


# ===========================================================================
# 14. Regulatory Calendar
# ===========================================================================


class TestRegulatoryCalendar:
    """Tests for get_calendar."""

    def test_calendar_empty(self, svc: RegulatorySubmissionService):
        cal = svc.get_calendar()
        assert cal.upcoming_deadlines == []
        assert cal.overdue == []
        assert cal.submitted_awaiting_response == []

    def test_calendar_upcoming_milestone(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        svc.create_milestone(
            sub.id,
            MilestoneCreate(
                milestone_name="Due soon",
                due_date=datetime.now(timezone.utc) + timedelta(days=5),
            ),
        )
        cal = svc.get_calendar()
        assert len(cal.upcoming_deadlines) >= 1
        assert any(d.milestone_name == "Due soon" for d in cal.upcoming_deadlines)

    def test_calendar_overdue_milestone(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        svc.create_milestone(
            sub.id,
            MilestoneCreate(
                milestone_name="Overdue task",
                due_date=datetime.now(timezone.utc) - timedelta(days=5),
            ),
        )
        cal = svc.get_calendar()
        assert len(cal.overdue) >= 1
        assert any(d.milestone_name == "Overdue task" for d in cal.overdue)
        assert any(d.is_overdue for d in cal.overdue)

    def test_calendar_completed_milestones_excluded(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        ms = svc.create_milestone(
            sub.id,
            MilestoneCreate(
                milestone_name="Done",
                due_date=datetime.now(timezone.utc) + timedelta(days=2),
            ),
        )
        svc.update_milestone(ms.id, MilestoneUpdate(status=MilestoneStatus.COMPLETED))
        cal = svc.get_calendar()
        assert not any(d.milestone_name == "Done" for d in cal.upcoming_deadlines)

    def test_calendar_awaiting_response(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.INTERNAL_REVIEW))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.SUBMITTED))
        cal = svc.get_calendar()
        assert len(cal.submitted_awaiting_response) >= 1
        assert any(s.id == rec.id for s in cal.submitted_awaiting_response)


# ===========================================================================
# 15. Metrics
# ===========================================================================


class TestSubmissionMetrics:
    """Tests for get_metrics."""

    def test_metrics_empty(self, svc: RegulatorySubmissionService):
        metrics = svc.get_metrics()
        assert metrics.total_submissions == 0
        assert metrics.by_type == {}
        assert metrics.by_body == {}
        assert metrics.by_status == {}
        assert metrics.avg_review_time_days is None
        assert metrics.approval_rate == 0.0

    def test_metrics_count(self, svc: RegulatorySubmissionService):
        _seed_varied(svc)
        metrics = svc.get_metrics()
        assert metrics.total_submissions == 6

    def test_metrics_by_type(self, svc: RegulatorySubmissionService):
        _seed_varied(svc)
        metrics = svc.get_metrics()
        assert "IND" in metrics.by_type
        assert metrics.by_type["IND"] == 2

    def test_metrics_by_body(self, svc: RegulatorySubmissionService):
        _seed_varied(svc)
        metrics = svc.get_metrics()
        assert "FDA" in metrics.by_body
        assert metrics.by_body["FDA"] == 4

    def test_metrics_by_status(self, svc: RegulatorySubmissionService):
        _seed_varied(svc)
        metrics = svc.get_metrics()
        assert "DRAFTING" in metrics.by_status

    def test_metrics_approval_rate(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.INTERNAL_REVIEW))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.SUBMITTED))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.UNDER_REVIEW))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.APPROVED))
        metrics = svc.get_metrics()
        assert metrics.approval_rate == 1.0

    def test_metrics_overdue_milestones(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        svc.create_milestone(
            sub.id,
            MilestoneCreate(
                milestone_name="Overdue",
                due_date=datetime.now(timezone.utc) - timedelta(days=5),
            ),
        )
        metrics = svc.get_metrics()
        assert metrics.overdue_milestones >= 1

    def test_metrics_pending_info_requests(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.INTERNAL_REVIEW))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.SUBMITTED))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.UNDER_REVIEW))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.INFORMATION_REQUEST))
        metrics = svc.get_metrics()
        assert metrics.pending_information_requests >= 1


# ===========================================================================
# 16. Information Requests
# ===========================================================================


class TestInformationRequests:
    """Tests for get_information_requests."""

    def test_empty(self, svc: RegulatorySubmissionService):
        result = svc.get_information_requests()
        assert result == []

    def test_returns_info_request_submissions(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.INTERNAL_REVIEW))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.SUBMITTED))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.UNDER_REVIEW))
        svc.update_submission(rec.id, SubmissionUpdate(status=SubmissionStatus.INFORMATION_REQUEST))
        result = svc.get_information_requests()
        assert len(result) == 1
        assert result[0].id == rec.id

    def test_excludes_non_info_request(self, svc: RegulatorySubmissionService):
        rec = svc.create_submission(_make_create())
        result = svc.get_information_requests()
        assert len(result) == 0


# ===========================================================================
# 17. Deadline Checking
# ===========================================================================


class TestDeadlineChecking:
    """Tests for check_deadlines."""

    def test_empty(self, svc: RegulatorySubmissionService):
        alerts = svc.check_deadlines()
        assert alerts == []

    def test_approaching_deadline(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        svc.create_milestone(
            sub.id,
            MilestoneCreate(
                milestone_name="Approaching",
                due_date=datetime.now(timezone.utc) + timedelta(days=7),
            ),
        )
        alerts = svc.check_deadlines(days_ahead=14)
        assert len(alerts) >= 1
        assert any(a.milestone_name == "Approaching" for a in alerts)

    def test_overdue_deadline(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        svc.create_milestone(
            sub.id,
            MilestoneCreate(
                milestone_name="Overdue",
                due_date=datetime.now(timezone.utc) - timedelta(days=3),
            ),
        )
        alerts = svc.check_deadlines()
        assert len(alerts) >= 1
        assert any(a.is_overdue for a in alerts)

    def test_far_future_excluded(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        svc.create_milestone(
            sub.id,
            MilestoneCreate(
                milestone_name="Far away",
                due_date=datetime.now(timezone.utc) + timedelta(days=100),
            ),
        )
        alerts = svc.check_deadlines(days_ahead=14)
        assert not any(a.milestone_name == "Far away" for a in alerts)

    def test_completed_excluded(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        ms = svc.create_milestone(
            sub.id,
            MilestoneCreate(
                milestone_name="Completed",
                due_date=datetime.now(timezone.utc) + timedelta(days=5),
            ),
        )
        svc.update_milestone(ms.id, MilestoneUpdate(status=MilestoneStatus.COMPLETED))
        alerts = svc.check_deadlines()
        assert not any(a.milestone_name == "Completed" for a in alerts)

    def test_sorted_by_due_date(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        svc.create_milestone(
            sub.id,
            MilestoneCreate(
                milestone_name="Later",
                due_date=datetime.now(timezone.utc) + timedelta(days=10),
            ),
        )
        svc.create_milestone(
            sub.id,
            MilestoneCreate(
                milestone_name="Sooner",
                due_date=datetime.now(timezone.utc) + timedelta(days=2),
            ),
        )
        alerts = svc.check_deadlines(days_ahead=30)
        names = [a.milestone_name for a in alerts]
        assert names.index("Sooner") < names.index("Later")


# ===========================================================================
# 18. Seed Data
# ===========================================================================


class TestSeedData:
    """Tests for seed data verification."""

    def test_seed_data_loads(self, svc: RegulatorySubmissionService):
        svc._seed_demo_data()
        items, total = svc.list_submissions()
        assert total == 10

    def test_seed_submissions_have_expected_types(self, svc: RegulatorySubmissionService):
        svc._seed_demo_data()
        items, _ = svc.list_submissions()
        types = {s.submission_type for s in items}
        assert SubmissionType.IND in types
        assert SubmissionType.PROTOCOL_AMENDMENT in types
        assert SubmissionType.IRB_APPROVAL in types

    def test_seed_has_multiple_bodies(self, svc: RegulatorySubmissionService):
        svc._seed_demo_data()
        items, _ = svc.list_submissions()
        bodies = {s.regulatory_body for s in items}
        assert RegulatoryBody.FDA in bodies
        assert RegulatoryBody.EMA in bodies
        assert RegulatoryBody.MHRA in bodies
        assert RegulatoryBody.HEALTH_CANADA in bodies

    def test_seed_has_milestones(self, svc: RegulatorySubmissionService):
        svc._seed_demo_data()
        items, _ = svc.list_submissions()
        total_ms = 0
        for sub in items:
            ms = svc.list_milestones(sub.id)
            total_ms += len(ms)
        assert total_ms >= 30  # At least 3 per submission average

    def test_seed_has_approved_submission(self, svc: RegulatorySubmissionService):
        svc._seed_demo_data()
        items, _ = svc.list_submissions(status=SubmissionStatus.APPROVED)
        assert len(items) >= 1

    def test_seed_has_info_request(self, svc: RegulatorySubmissionService):
        svc._seed_demo_data()
        items, _ = svc.list_submissions(status=SubmissionStatus.INFORMATION_REQUEST)
        assert len(items) >= 1


# ===========================================================================
# 19. Utility
# ===========================================================================


class TestUtility:
    """Tests for clear and get_stats."""

    def test_clear(self, svc: RegulatorySubmissionService):
        svc.create_submission(_make_create())
        svc.clear()
        items, total = svc.list_submissions()
        assert total == 0

    def test_get_stats(self, svc: RegulatorySubmissionService):
        svc.create_submission(_make_create())
        stats = svc.get_stats()
        assert stats["submissions"] == 1
        assert "milestones" in stats


# ===========================================================================
# 20. API Integration Tests
# ===========================================================================


@pytest.mark.anyio
class TestAPISubmissions:
    """Integration tests for submission API endpoints."""

    async def test_list_submissions(self, svc: RegulatorySubmissionService):
        svc.create_submission(_make_create())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/submissions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    async def test_create_submission_api(self, svc: RegulatorySubmissionService):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/submissions",
                json={
                    "title": "API Test IND",
                    "submission_type": "IND",
                    "regulatory_body": "FDA",
                    "trial_id": EYLEA_TRIAL,
                    "priority": "HIGH",
                },
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "API Test IND"
        assert data["status"] == "DRAFTING"

    async def test_get_submission_api(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/submissions/{sub.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == sub.id

    async def test_get_submission_not_found(self, svc: RegulatorySubmissionService):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/submissions/SUB-NOPE")
        assert resp.status_code == 404

    async def test_update_submission_api(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                f"{API_PREFIX}/submissions/{sub.id}",
                json={"title": "Updated via API"},
            )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated via API"

    async def test_update_submission_invalid_transition(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                f"{API_PREFIX}/submissions/{sub.id}",
                json={"status": "APPROVED"},
            )
        assert resp.status_code == 422

    async def test_delete_submission_api(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(f"{API_PREFIX}/submissions/{sub.id}")
        assert resp.status_code == 204

    async def test_delete_submission_not_found(self, svc: RegulatorySubmissionService):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(f"{API_PREFIX}/submissions/SUB-NOPE")
        assert resp.status_code == 404

    async def test_submit_api(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        svc.update_submission(sub.id, SubmissionUpdate(status=SubmissionStatus.INTERNAL_REVIEW))
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(f"{API_PREFIX}/submissions/{sub.id}/submit")
        assert resp.status_code == 200
        assert resp.json()["status"] == "SUBMITTED"

    async def test_submit_api_invalid(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(f"{API_PREFIX}/submissions/{sub.id}/submit")
        assert resp.status_code == 422

    async def test_record_response_api(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        svc.update_submission(sub.id, SubmissionUpdate(status=SubmissionStatus.INTERNAL_REVIEW))
        svc.update_submission(sub.id, SubmissionUpdate(status=SubmissionStatus.SUBMITTED))
        svc.update_submission(sub.id, SubmissionUpdate(status=SubmissionStatus.UNDER_REVIEW))
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/submissions/{sub.id}/record-response",
                json={"status": "APPROVED", "notes": "Looks good"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "APPROVED"

    async def test_metrics_api(self, svc: RegulatorySubmissionService):
        svc.create_submission(_make_create())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/submissions/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_submissions" in data

    async def test_calendar_api(self, svc: RegulatorySubmissionService):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/submissions/calendar")
        assert resp.status_code == 200
        data = resp.json()
        assert "upcoming_deadlines" in data
        assert "overdue" in data
        assert "submitted_awaiting_response" in data

    async def test_information_requests_api(self, svc: RegulatorySubmissionService):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/submissions/information-requests")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_deadlines_api(self, svc: RegulatorySubmissionService):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/submissions/deadlines")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_list_filter_by_type_api(self, svc: RegulatorySubmissionService):
        svc.create_submission(_make_create(submission_type=SubmissionType.IND))
        svc.create_submission(_make_create(submission_type=SubmissionType.NDA))
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/submissions", params={"submission_type": "IND"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    async def test_list_filter_by_body_api(self, svc: RegulatorySubmissionService):
        svc.create_submission(_make_create(regulatory_body=RegulatoryBody.FDA))
        svc.create_submission(_make_create(regulatory_body=RegulatoryBody.EMA))
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/submissions", params={"regulatory_body": "EMA"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1


@pytest.mark.anyio
class TestAPIMilestones:
    """Integration tests for milestone API endpoints."""

    async def test_create_milestone_api(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/submissions/{sub.id}/milestones",
                json={
                    "milestone_name": "API Milestone",
                    "due_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
                    "responsible": "Dr. Test",
                },
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["milestone_name"] == "API Milestone"

    async def test_list_milestones_api(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        svc.create_milestone(
            sub.id,
            MilestoneCreate(
                milestone_name="Test MS",
                due_date=datetime.now(timezone.utc) + timedelta(days=5),
            ),
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/submissions/{sub.id}/milestones")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    async def test_update_milestone_api(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        ms = svc.create_milestone(
            sub.id,
            MilestoneCreate(
                milestone_name="Original",
                due_date=datetime.now(timezone.utc) + timedelta(days=5),
            ),
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                f"{API_PREFIX}/milestones/{ms.id}",
                json={"milestone_name": "Renamed via API"},
            )
        assert resp.status_code == 200
        assert resp.json()["milestone_name"] == "Renamed via API"

    async def test_delete_milestone_api(self, svc: RegulatorySubmissionService):
        sub = svc.create_submission(_make_create())
        ms = svc.create_milestone(
            sub.id,
            MilestoneCreate(
                milestone_name="Delete me",
                due_date=datetime.now(timezone.utc) + timedelta(days=5),
            ),
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(f"{API_PREFIX}/milestones/{ms.id}")
        assert resp.status_code == 204

    async def test_delete_milestone_not_found(self, svc: RegulatorySubmissionService):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(f"{API_PREFIX}/milestones/MS-NOPE")
        assert resp.status_code == 404

    async def test_create_milestone_submission_not_found(self, svc: RegulatorySubmissionService):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/submissions/SUB-NOPE/milestones",
                json={
                    "milestone_name": "Test",
                    "due_date": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
                },
            )
        assert resp.status_code == 404

    async def test_list_milestones_submission_not_found(self, svc: RegulatorySubmissionService):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/submissions/SUB-NOPE/milestones")
        assert resp.status_code == 404
