"""Tests for Regulatory Correspondence Tracking (CLO-7).

Covers:
- Correspondence CRUD (create, read, update, delete, list with all filter combinations)
- Status transition validation
- Submit workflow
- Correspondence linking
- Action item CRUD (create, read, update, delete, list)
- Action item completion auto-date
- Action item filtering (completed, overdue)
- Regulatory timeline CRUD (create, read, update, delete, list)
- Milestone CRUD within timelines (add, update, delete)
- Agency contact CRUD (create, read, update, delete, list)
- Deadline report (upcoming, overdue)
- Metrics computation
- Agency relationship summary
- Seed data verification
- API endpoint integration tests
- Edge cases (non-existent records, invalid transitions, pagination, self-link)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.regulatory_correspondence import (
    ActionItemCreate,
    ActionItemUpdate,
    AgencyContactCreate,
    AgencyContactUpdate,
    CorrespondenceCreate,
    CorrespondenceStatus,
    CorrespondenceType,
    CorrespondenceUpdate,
    LinkCorrespondenceRequest,
    MilestoneCreate,
    MilestoneUpdate,
    Priority,
    RegulatoryAgency,
    ResponseDeadline,
    TimelineCreate,
    TimelineMilestone,
    TimelineUpdate,
)
from app.services.regulatory_correspondence_service import (
    RegulatoryCorrespondenceService,
    get_regulatory_correspondence_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/regulatory-correspondence"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_service():
    """Ensure a fresh service for every test."""
    svc = get_regulatory_correspondence_service()
    svc.clear()
    yield svc
    svc.clear()


@pytest.fixture
def svc(clean_service) -> RegulatoryCorrespondenceService:
    """Shorthand for the clean service."""
    return clean_service


def _make_corr_create(
    trial_id: str = EYLEA_TRIAL,
    correspondence_type: CorrespondenceType = CorrespondenceType.PRE_IND_MEETING,
    agency: RegulatoryAgency = RegulatoryAgency.FDA,
    priority: Priority = Priority.NORMAL,
    **kwargs,
) -> CorrespondenceCreate:
    """Helper to build a CorrespondenceCreate with defaults."""
    defaults = dict(
        title="Test Pre-IND Meeting",
        correspondence_type=correspondence_type,
        agency=agency,
        priority=priority,
        trial_id=trial_id,
        trial_name="Test Trial",
        description="Test correspondence description",
        response_deadline=ResponseDeadline.DAYS_30,
        assigned_to="Dr. Test",
        reviewer="Dr. Review",
        tags=["test"],
        key_points=["Key point 1"],
    )
    defaults.update(kwargs)
    return CorrespondenceCreate(**defaults)


def _seed_varied(svc: RegulatoryCorrespondenceService) -> list[str]:
    """Seed a variety of correspondence and return their IDs."""
    ids = []
    configs = [
        (CorrespondenceType.PRE_IND_MEETING, RegulatoryAgency.FDA, Priority.HIGH, EYLEA_TRIAL),
        (CorrespondenceType.TYPE_B_MEETING, RegulatoryAgency.EMA, Priority.NORMAL, DUPIXENT_TRIAL),
        (CorrespondenceType.FORM_483, RegulatoryAgency.FDA, Priority.URGENT, DUPIXENT_TRIAL),
        (CorrespondenceType.INFORMATION_REQUEST, RegulatoryAgency.MHRA, Priority.LOW, LIBTAYO_TRIAL),
        (CorrespondenceType.ANNUAL_REPORT, RegulatoryAgency.FDA, Priority.NORMAL, EYLEA_TRIAL),
    ]
    for ct, ag, pri, tid in configs:
        c = svc.create_correspondence(_make_corr_create(
            correspondence_type=ct, agency=ag, priority=pri, trial_id=tid,
            title=f"Test {ct.value} - {ag.value}",
        ))
        ids.append(c.id)
    return ids


# ===========================================================================
# Service-level tests: Correspondence CRUD
# ===========================================================================


class TestCorrespondenceCRUD:
    """Tests for correspondence create, read, update, delete."""

    def test_create_correspondence(self, svc):
        payload = _make_corr_create()
        corr = svc.create_correspondence(payload)
        assert corr.id.startswith("CORR-")
        assert corr.title == payload.title
        assert corr.status == CorrespondenceStatus.DRAFT
        assert corr.agency == RegulatoryAgency.FDA
        assert corr.correspondence_type == CorrespondenceType.PRE_IND_MEETING
        assert corr.priority == Priority.NORMAL
        assert corr.trial_id == EYLEA_TRIAL

    def test_create_with_all_fields(self, svc):
        payload = _make_corr_create(
            tags=["tag1", "tag2"],
            key_points=["Point A", "Point B"],
        )
        corr = svc.create_correspondence(payload)
        assert corr.tags == ["tag1", "tag2"]
        assert corr.key_points == ["Point A", "Point B"]

    def test_get_correspondence(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        fetched = svc.get_correspondence(corr.id)
        assert fetched.id == corr.id
        assert fetched.title == corr.title

    def test_get_not_found(self, svc):
        with pytest.raises(KeyError, match="not found"):
            svc.get_correspondence("CORR-NONEXISTENT")

    def test_update_correspondence(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        updated = svc.update_correspondence(
            corr.id,
            CorrespondenceUpdate(title="Updated Title", priority=Priority.HIGH),
        )
        assert updated.title == "Updated Title"
        assert updated.priority == Priority.HIGH

    def test_update_not_found(self, svc):
        with pytest.raises(KeyError, match="not found"):
            svc.update_correspondence(
                "CORR-NONEXISTENT",
                CorrespondenceUpdate(title="X"),
            )

    def test_update_description(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        updated = svc.update_correspondence(
            corr.id,
            CorrespondenceUpdate(description="New description"),
        )
        assert updated.description == "New description"

    def test_update_tags(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        updated = svc.update_correspondence(
            corr.id,
            CorrespondenceUpdate(tags=["new-tag"]),
        )
        assert updated.tags == ["new-tag"]

    def test_update_key_points(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        updated = svc.update_correspondence(
            corr.id,
            CorrespondenceUpdate(key_points=["New point"]),
        )
        assert updated.key_points == ["New point"]

    def test_update_assigned_to(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        updated = svc.update_correspondence(
            corr.id,
            CorrespondenceUpdate(assigned_to="Dr. New"),
        )
        assert updated.assigned_to == "Dr. New"

    def test_update_reviewer(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        updated = svc.update_correspondence(
            corr.id,
            CorrespondenceUpdate(reviewer="Dr. New Reviewer"),
        )
        assert updated.reviewer == "Dr. New Reviewer"

    def test_delete_correspondence(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        svc.delete_correspondence(corr.id)
        with pytest.raises(KeyError):
            svc.get_correspondence(corr.id)

    def test_delete_removes_action_items(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        now = datetime.now(timezone.utc)
        ai = svc.create_action_item(
            corr.id,
            ActionItemCreate(description="Test AI", due_date=now + timedelta(days=7)),
        )
        svc.delete_correspondence(corr.id)
        with pytest.raises(KeyError):
            svc.get_action_item(ai.id)

    def test_delete_not_found(self, svc):
        with pytest.raises(KeyError, match="not found"):
            svc.delete_correspondence("CORR-NONEXISTENT")

    def test_delete_cleans_related_links(self, svc):
        c1 = svc.create_correspondence(_make_corr_create(title="Corr 1"))
        c2 = svc.create_correspondence(_make_corr_create(title="Corr 2"))
        svc.link_correspondence(c1.id, c2.id)
        svc.delete_correspondence(c1.id)
        c2_after = svc.get_correspondence(c2.id)
        assert c1.id not in c2_after.related_correspondence_ids


class TestCorrespondenceList:
    """Tests for listing and filtering correspondence."""

    def test_list_all(self, svc):
        ids = _seed_varied(svc)
        items, total = svc.list_correspondence()
        assert total == len(ids)

    def test_filter_by_agency(self, svc):
        _seed_varied(svc)
        items, total = svc.list_correspondence(agency=RegulatoryAgency.FDA)
        assert all(c.agency == RegulatoryAgency.FDA for c in items)
        assert total == 3  # PRE_IND, FORM_483, ANNUAL_REPORT

    def test_filter_by_type(self, svc):
        _seed_varied(svc)
        items, total = svc.list_correspondence(
            correspondence_type=CorrespondenceType.FORM_483
        )
        assert total == 1
        assert items[0].correspondence_type == CorrespondenceType.FORM_483

    def test_filter_by_status(self, svc):
        _seed_varied(svc)
        items, total = svc.list_correspondence(status=CorrespondenceStatus.DRAFT)
        assert total == 5  # All seeded are DRAFT

    def test_filter_by_priority(self, svc):
        _seed_varied(svc)
        items, total = svc.list_correspondence(priority=Priority.HIGH)
        assert total == 1

    def test_filter_by_trial_id(self, svc):
        _seed_varied(svc)
        items, total = svc.list_correspondence(trial_id=DUPIXENT_TRIAL)
        assert total == 2

    def test_filter_by_search(self, svc):
        _seed_varied(svc)
        items, total = svc.list_correspondence(search="FORM_483")
        assert total == 1

    def test_search_in_description(self, svc):
        svc.create_correspondence(_make_corr_create(
            title="Some Title",
            description="Contains special keyword XYZ",
        ))
        items, total = svc.list_correspondence(search="xyz")
        assert total == 1

    def test_pagination(self, svc):
        _seed_varied(svc)
        items, total = svc.list_correspondence(limit=2, offset=0)
        assert len(items) == 2
        assert total == 5

    def test_pagination_offset(self, svc):
        _seed_varied(svc)
        items, total = svc.list_correspondence(limit=2, offset=3)
        assert len(items) == 2
        assert total == 5

    def test_combined_filters(self, svc):
        _seed_varied(svc)
        items, total = svc.list_correspondence(
            agency=RegulatoryAgency.FDA, priority=Priority.URGENT
        )
        assert total == 1

    def test_empty_result(self, svc):
        items, total = svc.list_correspondence()
        assert total == 0
        assert items == []


class TestCorrespondenceStatus:
    """Tests for status transitions and submit workflow."""

    def test_valid_transition_draft_to_under_review(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        updated = svc.update_correspondence(
            corr.id,
            CorrespondenceUpdate(status=CorrespondenceStatus.UNDER_REVIEW),
        )
        assert updated.status == CorrespondenceStatus.UNDER_REVIEW

    def test_valid_transition_draft_to_submitted(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        updated = svc.update_correspondence(
            corr.id,
            CorrespondenceUpdate(status=CorrespondenceStatus.SUBMITTED),
        )
        assert updated.status == CorrespondenceStatus.SUBMITTED
        assert updated.submission_date is not None

    def test_submit_sets_deadline_date(self, svc):
        corr = svc.create_correspondence(_make_corr_create(
            response_deadline=ResponseDeadline.DAYS_30,
        ))
        updated = svc.update_correspondence(
            corr.id,
            CorrespondenceUpdate(status=CorrespondenceStatus.SUBMITTED),
        )
        assert updated.response_deadline_date is not None

    def test_submit_workflow(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        submitted = svc.submit_correspondence(corr.id)
        assert submitted.status == CorrespondenceStatus.SUBMITTED
        assert submitted.submission_date is not None

    def test_submit_from_under_review(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        svc.update_correspondence(
            corr.id,
            CorrespondenceUpdate(status=CorrespondenceStatus.UNDER_REVIEW),
        )
        submitted = svc.submit_correspondence(corr.id)
        assert submitted.status == CorrespondenceStatus.SUBMITTED

    def test_submit_from_invalid_status(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        svc.submit_correspondence(corr.id)
        # Now try to submit again from SUBMITTED
        with pytest.raises(ValueError, match="Cannot submit"):
            svc.submit_correspondence(corr.id)

    def test_submit_not_found(self, svc):
        with pytest.raises(KeyError, match="not found"):
            svc.submit_correspondence("CORR-NONEXISTENT")

    def test_invalid_transition(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        with pytest.raises(ValueError, match="Invalid status transition"):
            svc.update_correspondence(
                corr.id,
                CorrespondenceUpdate(status=CorrespondenceStatus.CLOSED),
            )

    def test_closed_is_terminal(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        svc.submit_correspondence(corr.id)
        svc.update_correspondence(
            corr.id,
            CorrespondenceUpdate(status=CorrespondenceStatus.ACKNOWLEDGED),
        )
        svc.update_correspondence(
            corr.id,
            CorrespondenceUpdate(status=CorrespondenceStatus.CLOSED),
        )
        with pytest.raises(ValueError, match="Invalid status transition"):
            svc.update_correspondence(
                corr.id,
                CorrespondenceUpdate(status=CorrespondenceStatus.DRAFT),
            )

    def test_withdrawn_is_terminal(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        svc.update_correspondence(
            corr.id,
            CorrespondenceUpdate(status=CorrespondenceStatus.WITHDRAWN),
        )
        with pytest.raises(ValueError, match="Invalid status transition"):
            svc.update_correspondence(
                corr.id,
                CorrespondenceUpdate(status=CorrespondenceStatus.DRAFT),
            )

    def test_response_received_auto_date(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        svc.submit_correspondence(corr.id)
        svc.update_correspondence(
            corr.id,
            CorrespondenceUpdate(status=CorrespondenceStatus.ACKNOWLEDGED),
        )
        updated = svc.update_correspondence(
            corr.id,
            CorrespondenceUpdate(status=CorrespondenceStatus.RESPONSE_RECEIVED),
        )
        assert updated.response_received_date is not None

    def test_follow_up_to_submitted(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        svc.submit_correspondence(corr.id)
        svc.update_correspondence(
            corr.id,
            CorrespondenceUpdate(status=CorrespondenceStatus.ACKNOWLEDGED),
        )
        svc.update_correspondence(
            corr.id,
            CorrespondenceUpdate(status=CorrespondenceStatus.FOLLOW_UP_REQUIRED),
        )
        resubmitted = svc.update_correspondence(
            corr.id,
            CorrespondenceUpdate(status=CorrespondenceStatus.SUBMITTED),
        )
        assert resubmitted.status == CorrespondenceStatus.SUBMITTED


class TestCorrespondenceLinking:
    """Tests for linking correspondence records."""

    def test_link_two_records(self, svc):
        c1 = svc.create_correspondence(_make_corr_create(title="Corr A"))
        c2 = svc.create_correspondence(_make_corr_create(title="Corr B"))
        result = svc.link_correspondence(c1.id, c2.id)
        assert c2.id in result.related_correspondence_ids
        c2_updated = svc.get_correspondence(c2.id)
        assert c1.id in c2_updated.related_correspondence_ids

    def test_link_idempotent(self, svc):
        c1 = svc.create_correspondence(_make_corr_create(title="Corr A"))
        c2 = svc.create_correspondence(_make_corr_create(title="Corr B"))
        svc.link_correspondence(c1.id, c2.id)
        svc.link_correspondence(c1.id, c2.id)
        c1_updated = svc.get_correspondence(c1.id)
        assert c1_updated.related_correspondence_ids.count(c2.id) == 1

    def test_link_not_found(self, svc):
        c1 = svc.create_correspondence(_make_corr_create())
        with pytest.raises(KeyError, match="not found"):
            svc.link_correspondence(c1.id, "CORR-NONEXISTENT")

    def test_link_self_raises(self, svc):
        c1 = svc.create_correspondence(_make_corr_create())
        with pytest.raises(ValueError, match="Cannot link correspondence to itself"):
            svc.link_correspondence(c1.id, c1.id)

    def test_link_source_not_found(self, svc):
        c2 = svc.create_correspondence(_make_corr_create())
        with pytest.raises(KeyError, match="not found"):
            svc.link_correspondence("CORR-NONEXISTENT", c2.id)


# ===========================================================================
# Service-level tests: Action Items
# ===========================================================================


class TestActionItemCRUD:
    """Tests for action item management."""

    def test_create_action_item(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        now = datetime.now(timezone.utc)
        ai = svc.create_action_item(
            corr.id,
            ActionItemCreate(
                description="Test action",
                assigned_to="Dr. Test",
                due_date=now + timedelta(days=7),
                priority=Priority.HIGH,
            ),
        )
        assert ai.id.startswith("AI-")
        assert ai.description == "Test action"
        assert ai.completed is False
        assert ai.priority == Priority.HIGH

    def test_create_action_item_corr_not_found(self, svc):
        now = datetime.now(timezone.utc)
        with pytest.raises(KeyError, match="not found"):
            svc.create_action_item(
                "CORR-NONEXISTENT",
                ActionItemCreate(description="X", due_date=now + timedelta(days=1)),
            )

    def test_get_action_item(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        now = datetime.now(timezone.utc)
        ai = svc.create_action_item(
            corr.id,
            ActionItemCreate(description="Get test", due_date=now + timedelta(days=5)),
        )
        fetched = svc.get_action_item(ai.id)
        assert fetched.id == ai.id

    def test_get_action_item_not_found(self, svc):
        with pytest.raises(KeyError, match="not found"):
            svc.get_action_item("AI-NONEXISTENT")

    def test_update_action_item_description(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        now = datetime.now(timezone.utc)
        ai = svc.create_action_item(
            corr.id,
            ActionItemCreate(description="Original", due_date=now + timedelta(days=5)),
        )
        updated = svc.update_action_item(
            ai.id, ActionItemUpdate(description="Updated")
        )
        assert updated.description == "Updated"

    def test_update_action_item_priority(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        now = datetime.now(timezone.utc)
        ai = svc.create_action_item(
            corr.id,
            ActionItemCreate(description="Priority test", due_date=now + timedelta(days=5)),
        )
        updated = svc.update_action_item(
            ai.id, ActionItemUpdate(priority=Priority.URGENT)
        )
        assert updated.priority == Priority.URGENT

    def test_complete_action_item_auto_date(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        now = datetime.now(timezone.utc)
        ai = svc.create_action_item(
            corr.id,
            ActionItemCreate(description="Complete me", due_date=now + timedelta(days=5)),
        )
        updated = svc.update_action_item(ai.id, ActionItemUpdate(completed=True))
        assert updated.completed is True
        assert updated.completed_date is not None

    def test_uncomplete_action_item_clears_date(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        now = datetime.now(timezone.utc)
        ai = svc.create_action_item(
            corr.id,
            ActionItemCreate(description="Toggle", due_date=now + timedelta(days=5)),
        )
        svc.update_action_item(ai.id, ActionItemUpdate(completed=True))
        updated = svc.update_action_item(ai.id, ActionItemUpdate(completed=False))
        assert updated.completed is False
        assert updated.completed_date is None

    def test_update_action_item_not_found(self, svc):
        with pytest.raises(KeyError, match="not found"):
            svc.update_action_item("AI-NONEXISTENT", ActionItemUpdate(description="X"))

    def test_delete_action_item(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        now = datetime.now(timezone.utc)
        ai = svc.create_action_item(
            corr.id,
            ActionItemCreate(description="Delete me", due_date=now + timedelta(days=5)),
        )
        svc.delete_action_item(ai.id)
        with pytest.raises(KeyError):
            svc.get_action_item(ai.id)

    def test_delete_action_item_not_found(self, svc):
        with pytest.raises(KeyError, match="not found"):
            svc.delete_action_item("AI-NONEXISTENT")

    def test_list_action_items_for_correspondence(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        now = datetime.now(timezone.utc)
        for i in range(3):
            svc.create_action_item(
                corr.id,
                ActionItemCreate(description=f"AI {i}", due_date=now + timedelta(days=i + 1)),
            )
        items = svc.list_action_items(correspondence_id=corr.id)
        assert len(items) == 3

    def test_list_action_items_filter_completed(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        now = datetime.now(timezone.utc)
        ai1 = svc.create_action_item(
            corr.id,
            ActionItemCreate(description="Done", due_date=now + timedelta(days=1)),
        )
        svc.create_action_item(
            corr.id,
            ActionItemCreate(description="Not done", due_date=now + timedelta(days=2)),
        )
        svc.update_action_item(ai1.id, ActionItemUpdate(completed=True))
        completed = svc.list_action_items(completed=True)
        assert len(completed) == 1
        open_items = svc.list_action_items(completed=False)
        assert len(open_items) == 1

    def test_list_action_items_overdue(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        now = datetime.now(timezone.utc)
        svc.create_action_item(
            corr.id,
            ActionItemCreate(description="Overdue", due_date=now - timedelta(days=5)),
        )
        svc.create_action_item(
            corr.id,
            ActionItemCreate(description="Future", due_date=now + timedelta(days=5)),
        )
        overdue = svc.list_action_items(overdue_only=True)
        assert len(overdue) == 1
        assert overdue[0].description == "Overdue"

    def test_list_action_items_sorted_by_due_date(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        now = datetime.now(timezone.utc)
        svc.create_action_item(
            corr.id,
            ActionItemCreate(description="Later", due_date=now + timedelta(days=10)),
        )
        svc.create_action_item(
            corr.id,
            ActionItemCreate(description="Sooner", due_date=now + timedelta(days=2)),
        )
        items = svc.list_action_items()
        assert items[0].description == "Sooner"

    def test_update_due_date(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        now = datetime.now(timezone.utc)
        ai = svc.create_action_item(
            corr.id,
            ActionItemCreate(description="Reschedule", due_date=now + timedelta(days=5)),
        )
        new_date = now + timedelta(days=15)
        updated = svc.update_action_item(ai.id, ActionItemUpdate(due_date=new_date))
        assert updated.due_date == new_date


# ===========================================================================
# Service-level tests: Timelines
# ===========================================================================


class TestTimelineCRUD:
    """Tests for regulatory timeline management."""

    def test_create_timeline(self, svc):
        tl = svc.create_timeline(TimelineCreate(
            trial_id=EYLEA_TRIAL,
            trial_name="Test Timeline",
        ))
        assert tl.id.startswith("TL-")
        assert tl.trial_id == EYLEA_TRIAL
        assert tl.milestones == []

    def test_create_timeline_with_milestones(self, svc):
        now = datetime.now(timezone.utc)
        tl = svc.create_timeline(TimelineCreate(
            trial_id=EYLEA_TRIAL,
            trial_name="Test Timeline",
            milestones=[
                TimelineMilestone(name="MS1", planned_date=now + timedelta(days=30)),
                TimelineMilestone(name="MS2", planned_date=now + timedelta(days=60)),
            ],
        ))
        assert len(tl.milestones) == 2

    def test_get_timeline(self, svc):
        tl = svc.create_timeline(TimelineCreate(
            trial_id=EYLEA_TRIAL, trial_name="Get Test",
        ))
        fetched = svc.get_timeline(tl.id)
        assert fetched.id == tl.id

    def test_get_timeline_not_found(self, svc):
        with pytest.raises(KeyError, match="not found"):
            svc.get_timeline("TL-NONEXISTENT")

    def test_get_timeline_by_trial(self, svc):
        svc.create_timeline(TimelineCreate(
            trial_id=EYLEA_TRIAL, trial_name="By Trial Test",
        ))
        result = svc.get_timeline_by_trial(EYLEA_TRIAL)
        assert result is not None
        assert result.trial_id == EYLEA_TRIAL

    def test_get_timeline_by_trial_not_found(self, svc):
        result = svc.get_timeline_by_trial("nonexistent-trial")
        assert result is None

    def test_update_timeline(self, svc):
        tl = svc.create_timeline(TimelineCreate(
            trial_id=EYLEA_TRIAL, trial_name="Original",
        ))
        updated = svc.update_timeline(tl.id, TimelineUpdate(trial_name="Updated"))
        assert updated.trial_name == "Updated"

    def test_update_timeline_not_found(self, svc):
        with pytest.raises(KeyError, match="not found"):
            svc.update_timeline("TL-NONEXISTENT", TimelineUpdate(trial_name="X"))

    def test_delete_timeline(self, svc):
        tl = svc.create_timeline(TimelineCreate(
            trial_id=EYLEA_TRIAL, trial_name="Delete Me",
        ))
        svc.delete_timeline(tl.id)
        with pytest.raises(KeyError):
            svc.get_timeline(tl.id)

    def test_delete_timeline_not_found(self, svc):
        with pytest.raises(KeyError, match="not found"):
            svc.delete_timeline("TL-NONEXISTENT")

    def test_list_timelines(self, svc):
        svc.create_timeline(TimelineCreate(trial_id=EYLEA_TRIAL, trial_name="TL A"))
        svc.create_timeline(TimelineCreate(trial_id=DUPIXENT_TRIAL, trial_name="TL B"))
        items = svc.list_timelines()
        assert len(items) == 2


class TestMilestoneCRUD:
    """Tests for milestone management within timelines."""

    def test_add_milestone(self, svc):
        tl = svc.create_timeline(TimelineCreate(
            trial_id=EYLEA_TRIAL, trial_name="Milestone Test",
        ))
        now = datetime.now(timezone.utc)
        updated = svc.add_milestone(tl.id, MilestoneCreate(
            name="New Milestone", planned_date=now + timedelta(days=30),
        ))
        assert len(updated.milestones) == 1
        assert updated.milestones[0].name == "New Milestone"

    def test_add_milestone_with_correspondence(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        tl = svc.create_timeline(TimelineCreate(
            trial_id=EYLEA_TRIAL, trial_name="MS with Corr",
        ))
        now = datetime.now(timezone.utc)
        updated = svc.add_milestone(tl.id, MilestoneCreate(
            name="Linked MS", planned_date=now + timedelta(days=30),
            correspondence_id=corr.id,
        ))
        assert updated.milestones[0].correspondence_id == corr.id

    def test_add_milestone_timeline_not_found(self, svc):
        now = datetime.now(timezone.utc)
        with pytest.raises(KeyError, match="not found"):
            svc.add_milestone("TL-NONEXISTENT", MilestoneCreate(
                name="X", planned_date=now + timedelta(days=1),
            ))

    def test_update_milestone(self, svc):
        tl = svc.create_timeline(TimelineCreate(
            trial_id=EYLEA_TRIAL, trial_name="Update MS",
        ))
        now = datetime.now(timezone.utc)
        svc.add_milestone(tl.id, MilestoneCreate(
            name="Original", planned_date=now + timedelta(days=30),
        ))
        updated = svc.update_milestone(
            tl.id, 0,
            MilestoneUpdate(name="Renamed", status="COMPLETED", actual_date=now),
        )
        assert updated.milestones[0].name == "Renamed"
        assert updated.milestones[0].status == "COMPLETED"
        assert updated.milestones[0].actual_date is not None

    def test_update_milestone_out_of_range(self, svc):
        tl = svc.create_timeline(TimelineCreate(
            trial_id=EYLEA_TRIAL, trial_name="Range Test",
        ))
        with pytest.raises(IndexError, match="out of range"):
            svc.update_milestone(tl.id, 0, MilestoneUpdate(name="X"))

    def test_update_milestone_timeline_not_found(self, svc):
        with pytest.raises(KeyError, match="not found"):
            svc.update_milestone("TL-NONEXISTENT", 0, MilestoneUpdate(name="X"))

    def test_delete_milestone(self, svc):
        tl = svc.create_timeline(TimelineCreate(
            trial_id=EYLEA_TRIAL, trial_name="Delete MS",
        ))
        now = datetime.now(timezone.utc)
        svc.add_milestone(tl.id, MilestoneCreate(
            name="To Delete", planned_date=now + timedelta(days=30),
        ))
        svc.add_milestone(tl.id, MilestoneCreate(
            name="Keep", planned_date=now + timedelta(days=60),
        ))
        updated = svc.delete_milestone(tl.id, 0)
        assert len(updated.milestones) == 1
        assert updated.milestones[0].name == "Keep"

    def test_delete_milestone_out_of_range(self, svc):
        tl = svc.create_timeline(TimelineCreate(
            trial_id=EYLEA_TRIAL, trial_name="Range Del",
        ))
        with pytest.raises(IndexError, match="out of range"):
            svc.delete_milestone(tl.id, 0)

    def test_update_milestone_notes(self, svc):
        tl = svc.create_timeline(TimelineCreate(
            trial_id=EYLEA_TRIAL, trial_name="Notes Test",
        ))
        now = datetime.now(timezone.utc)
        svc.add_milestone(tl.id, MilestoneCreate(
            name="With Notes", planned_date=now + timedelta(days=30),
        ))
        updated = svc.update_milestone(
            tl.id, 0, MilestoneUpdate(notes="Important note"),
        )
        assert updated.milestones[0].notes == "Important note"


# ===========================================================================
# Service-level tests: Agency Contacts
# ===========================================================================


class TestAgencyContactCRUD:
    """Tests for agency contact management."""

    def test_create_contact(self, svc):
        contact = svc.create_contact(AgencyContactCreate(
            name="Test Contact",
            agency=RegulatoryAgency.FDA,
            title="Director",
            division="CDER",
            email="test@fda.gov",
            phone="+1-555-0000",
        ))
        assert contact.id.startswith("AC-")
        assert contact.name == "Test Contact"
        assert contact.agency == RegulatoryAgency.FDA

    def test_get_contact(self, svc):
        contact = svc.create_contact(AgencyContactCreate(
            name="Get Test", agency=RegulatoryAgency.EMA,
        ))
        fetched = svc.get_contact(contact.id)
        assert fetched.id == contact.id

    def test_get_contact_not_found(self, svc):
        with pytest.raises(KeyError, match="not found"):
            svc.get_contact("AC-NONEXISTENT")

    def test_update_contact(self, svc):
        contact = svc.create_contact(AgencyContactCreate(
            name="Original", agency=RegulatoryAgency.FDA,
        ))
        updated = svc.update_contact(contact.id, AgencyContactUpdate(
            name="Updated Name", title="Senior Director",
        ))
        assert updated.name == "Updated Name"
        assert updated.title == "Senior Director"

    def test_update_contact_agency(self, svc):
        contact = svc.create_contact(AgencyContactCreate(
            name="Switch", agency=RegulatoryAgency.FDA,
        ))
        updated = svc.update_contact(contact.id, AgencyContactUpdate(
            agency=RegulatoryAgency.EMA,
        ))
        assert updated.agency == RegulatoryAgency.EMA

    def test_update_contact_not_found(self, svc):
        with pytest.raises(KeyError, match="not found"):
            svc.update_contact("AC-NONEXISTENT", AgencyContactUpdate(name="X"))

    def test_delete_contact(self, svc):
        contact = svc.create_contact(AgencyContactCreate(
            name="Delete Me", agency=RegulatoryAgency.MHRA,
        ))
        svc.delete_contact(contact.id)
        with pytest.raises(KeyError):
            svc.get_contact(contact.id)

    def test_delete_contact_not_found(self, svc):
        with pytest.raises(KeyError, match="not found"):
            svc.delete_contact("AC-NONEXISTENT")

    def test_list_contacts(self, svc):
        svc.create_contact(AgencyContactCreate(name="C1", agency=RegulatoryAgency.FDA))
        svc.create_contact(AgencyContactCreate(name="C2", agency=RegulatoryAgency.EMA))
        svc.create_contact(AgencyContactCreate(name="C3", agency=RegulatoryAgency.FDA))
        all_contacts = svc.list_contacts()
        assert len(all_contacts) == 3

    def test_list_contacts_by_agency(self, svc):
        svc.create_contact(AgencyContactCreate(name="F1", agency=RegulatoryAgency.FDA))
        svc.create_contact(AgencyContactCreate(name="E1", agency=RegulatoryAgency.EMA))
        svc.create_contact(AgencyContactCreate(name="F2", agency=RegulatoryAgency.FDA))
        fda = svc.list_contacts(agency=RegulatoryAgency.FDA)
        assert len(fda) == 2

    def test_list_contacts_sorted_by_name(self, svc):
        svc.create_contact(AgencyContactCreate(name="Zara", agency=RegulatoryAgency.FDA))
        svc.create_contact(AgencyContactCreate(name="Alice", agency=RegulatoryAgency.FDA))
        contacts = svc.list_contacts()
        assert contacts[0].name == "Alice"
        assert contacts[1].name == "Zara"


# ===========================================================================
# Service-level tests: Deadline Report
# ===========================================================================


class TestDeadlineReport:
    """Tests for deadline report generation."""

    def test_empty_report(self, svc):
        report = svc.get_deadline_report()
        assert report.total_upcoming == 0
        assert report.total_overdue == 0

    def test_upcoming_correspondence_deadline(self, svc):
        corr = svc.create_correspondence(_make_corr_create(
            response_deadline=ResponseDeadline.DAYS_15,
        ))
        svc.submit_correspondence(corr.id)
        report = svc.get_deadline_report(days_ahead=30)
        assert report.total_upcoming >= 1

    def test_overdue_action_item(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        now = datetime.now(timezone.utc)
        svc.create_action_item(
            corr.id,
            ActionItemCreate(description="Overdue AI", due_date=now - timedelta(days=5)),
        )
        report = svc.get_deadline_report()
        assert report.total_overdue >= 1

    def test_completed_action_items_excluded(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        now = datetime.now(timezone.utc)
        ai = svc.create_action_item(
            corr.id,
            ActionItemCreate(description="Done AI", due_date=now - timedelta(days=5)),
        )
        svc.update_action_item(ai.id, ActionItemUpdate(completed=True))
        report = svc.get_deadline_report()
        # Completed items should not appear in overdue
        overdue_ids = [e.id for e in report.overdue]
        assert ai.id not in overdue_ids

    def test_closed_correspondence_excluded(self, svc):
        corr = svc.create_correspondence(_make_corr_create(
            response_deadline=ResponseDeadline.DAYS_15,
        ))
        svc.submit_correspondence(corr.id)
        svc.update_correspondence(
            corr.id,
            CorrespondenceUpdate(status=CorrespondenceStatus.ACKNOWLEDGED),
        )
        svc.update_correspondence(
            corr.id,
            CorrespondenceUpdate(status=CorrespondenceStatus.CLOSED),
        )
        report = svc.get_deadline_report(days_ahead=365)
        corr_ids = [e.id for e in report.upcoming + report.overdue]
        assert corr.id not in corr_ids

    def test_deadline_sorting(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        now = datetime.now(timezone.utc)
        svc.create_action_item(
            corr.id,
            ActionItemCreate(description="Later", due_date=now + timedelta(days=20)),
        )
        svc.create_action_item(
            corr.id,
            ActionItemCreate(description="Sooner", due_date=now + timedelta(days=5)),
        )
        report = svc.get_deadline_report(days_ahead=30)
        if len(report.upcoming) >= 2:
            assert report.upcoming[0].deadline_date <= report.upcoming[1].deadline_date


# ===========================================================================
# Service-level tests: Metrics
# ===========================================================================


class TestMetrics:
    """Tests for aggregated metrics."""

    def test_empty_metrics(self, svc):
        m = svc.get_metrics()
        assert m.total_correspondence == 0
        assert m.by_agency == {}
        assert m.avg_response_time_days is None

    def test_metrics_counts(self, svc):
        _seed_varied(svc)
        m = svc.get_metrics()
        assert m.total_correspondence == 5
        assert m.by_agency["FDA"] == 3
        assert m.by_agency["EMA"] == 1
        assert m.by_agency["MHRA"] == 1

    def test_metrics_by_type(self, svc):
        _seed_varied(svc)
        m = svc.get_metrics()
        assert "PRE_IND_MEETING" in m.by_type
        assert "FORM_483" in m.by_type

    def test_metrics_by_status(self, svc):
        _seed_varied(svc)
        m = svc.get_metrics()
        assert m.by_status["DRAFT"] == 5

    def test_metrics_action_item_counts(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        now = datetime.now(timezone.utc)
        ai1 = svc.create_action_item(
            corr.id,
            ActionItemCreate(description="Open", due_date=now + timedelta(days=5)),
        )
        ai2 = svc.create_action_item(
            corr.id,
            ActionItemCreate(description="Done", due_date=now + timedelta(days=5)),
        )
        svc.update_action_item(ai2.id, ActionItemUpdate(completed=True))
        m = svc.get_metrics()
        assert m.open_action_items == 1
        assert m.completed_action_items == 1

    def test_metrics_overdue_action_items(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        now = datetime.now(timezone.utc)
        svc.create_action_item(
            corr.id,
            ActionItemCreate(description="Overdue", due_date=now - timedelta(days=5)),
        )
        m = svc.get_metrics()
        assert m.overdue_action_items == 1

    def test_metrics_avg_response_time(self, svc):
        corr = svc.create_correspondence(_make_corr_create())
        svc.submit_correspondence(corr.id)
        svc.update_correspondence(
            corr.id,
            CorrespondenceUpdate(status=CorrespondenceStatus.ACKNOWLEDGED),
        )
        svc.update_correspondence(
            corr.id,
            CorrespondenceUpdate(status=CorrespondenceStatus.RESPONSE_RECEIVED),
        )
        m = svc.get_metrics()
        # Response time should be very small (nearly 0 since all happens instantly)
        assert m.avg_response_time_days is not None
        assert m.avg_response_time_days >= 0


# ===========================================================================
# Service-level tests: Agency Relationship Summary
# ===========================================================================


class TestAgencyRelationshipSummary:
    """Tests for agency relationship summary."""

    def test_summary_empty(self, svc):
        summary = svc.get_agency_relationship_summary(RegulatoryAgency.FDA)
        assert summary.agency == RegulatoryAgency.FDA
        assert summary.total_correspondence == 0

    def test_summary_with_data(self, svc):
        _seed_varied(svc)
        svc.create_contact(AgencyContactCreate(name="FDA Contact", agency=RegulatoryAgency.FDA))
        summary = svc.get_agency_relationship_summary(RegulatoryAgency.FDA)
        assert summary.total_correspondence == 3
        assert len(summary.contacts) == 1
        assert summary.open_items == 3  # All DRAFT = open

    def test_summary_closed_items(self, svc):
        c = svc.create_correspondence(_make_corr_create())
        svc.submit_correspondence(c.id)
        svc.update_correspondence(
            c.id, CorrespondenceUpdate(status=CorrespondenceStatus.ACKNOWLEDGED)
        )
        svc.update_correspondence(
            c.id, CorrespondenceUpdate(status=CorrespondenceStatus.CLOSED)
        )
        summary = svc.get_agency_relationship_summary(RegulatoryAgency.FDA)
        assert summary.closed_items == 1

    def test_summary_recent_limited_to_5(self, svc):
        for i in range(7):
            svc.create_correspondence(_make_corr_create(title=f"Corr {i}"))
        summary = svc.get_agency_relationship_summary(RegulatoryAgency.FDA)
        assert len(summary.recent_correspondence) == 5


# ===========================================================================
# Service-level tests: Seed Data and Utility
# ===========================================================================


class TestSeedDataAndUtility:
    """Tests for seed data and utility methods."""

    def test_seed_data_loads(self, svc):
        svc._seed_demo_data()
        stats = svc.get_stats()
        assert stats["correspondence"] == 10
        assert stats["action_items"] == 15
        assert stats["timelines"] == 3
        assert stats["contacts"] == 8

    def test_seed_correspondence_ids(self, svc):
        svc._seed_demo_data()
        for i in range(1, 11):
            corr = svc.get_correspondence(f"CORR-{i:03d}")
            assert corr is not None

    def test_seed_action_items(self, svc):
        svc._seed_demo_data()
        for i in range(1, 16):
            ai = svc.get_action_item(f"AI-{i:03d}")
            assert ai is not None

    def test_seed_timelines(self, svc):
        svc._seed_demo_data()
        for tid in ["TL-001", "TL-002", "TL-003"]:
            tl = svc.get_timeline(tid)
            assert tl is not None
            assert len(tl.milestones) > 0

    def test_seed_contacts(self, svc):
        svc._seed_demo_data()
        for i in range(1, 9):
            c = svc.get_contact(f"AC-{i:03d}")
            assert c is not None

    def test_seed_related_links(self, svc):
        svc._seed_demo_data()
        c1 = svc.get_correspondence("CORR-001")
        assert "CORR-002" in c1.related_correspondence_ids

    def test_clear(self, svc):
        svc._seed_demo_data()
        svc.clear()
        stats = svc.get_stats()
        assert stats["correspondence"] == 0
        assert stats["action_items"] == 0
        assert stats["timelines"] == 0
        assert stats["contacts"] == 0

    def test_get_stats(self, svc):
        stats = svc.get_stats()
        assert "correspondence" in stats
        assert "action_items" in stats
        assert "timelines" in stats
        assert "contacts" in stats


# ===========================================================================
# API integration tests
# ===========================================================================


@pytest.fixture
def client():
    """Async HTTP client for API tests."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


class TestAPICorrespondence:
    """API tests for correspondence endpoints."""

    @pytest.mark.anyio
    async def test_list_correspondence(self, client, svc):
        svc._seed_demo_data()
        resp = await client.get(f"{API_PREFIX}/correspondence")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_filter_agency(self, client, svc):
        svc._seed_demo_data()
        resp = await client.get(f"{API_PREFIX}/correspondence", params={"agency": "EMA"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(c["agency"] == "EMA" for c in data["items"])

    @pytest.mark.anyio
    async def test_list_filter_type(self, client, svc):
        svc._seed_demo_data()
        resp = await client.get(
            f"{API_PREFIX}/correspondence",
            params={"correspondence_type": "FORM_483"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.anyio
    async def test_list_filter_status(self, client, svc):
        svc._seed_demo_data()
        resp = await client.get(
            f"{API_PREFIX}/correspondence", params={"status": "DRAFT"}
        )
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_filter_priority(self, client, svc):
        svc._seed_demo_data()
        resp = await client.get(
            f"{API_PREFIX}/correspondence", params={"priority": "URGENT"}
        )
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_pagination(self, client, svc):
        svc._seed_demo_data()
        resp = await client.get(
            f"{API_PREFIX}/correspondence", params={"limit": 3, "offset": 0}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 3
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_search(self, client, svc):
        svc._seed_demo_data()
        resp = await client.get(
            f"{API_PREFIX}/correspondence", params={"search": "EYLEA"}
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.anyio
    async def test_get_correspondence(self, client, svc):
        svc._seed_demo_data()
        resp = await client.get(f"{API_PREFIX}/correspondence/CORR-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "CORR-001"

    @pytest.mark.anyio
    async def test_get_correspondence_not_found(self, client, svc):
        resp = await client.get(f"{API_PREFIX}/correspondence/CORR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_correspondence(self, client, svc):
        payload = {
            "title": "API Created Corr",
            "correspondence_type": "PRE_IND_MEETING",
            "agency": "FDA",
            "trial_id": EYLEA_TRIAL,
            "trial_name": "API Trial",
        }
        resp = await client.post(f"{API_PREFIX}/correspondence", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "API Created Corr"
        assert data["status"] == "DRAFT"

    @pytest.mark.anyio
    async def test_update_correspondence(self, client, svc):
        corr = svc.create_correspondence(_make_corr_create())
        payload = {"title": "API Updated"}
        resp = await client.put(
            f"{API_PREFIX}/correspondence/{corr.id}", json=payload
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "API Updated"

    @pytest.mark.anyio
    async def test_update_correspondence_not_found(self, client, svc):
        resp = await client.put(
            f"{API_PREFIX}/correspondence/CORR-NONEXISTENT",
            json={"title": "X"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_invalid_transition(self, client, svc):
        corr = svc.create_correspondence(_make_corr_create())
        resp = await client.put(
            f"{API_PREFIX}/correspondence/{corr.id}",
            json={"status": "CLOSED"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_delete_correspondence(self, client, svc):
        corr = svc.create_correspondence(_make_corr_create())
        resp = await client.delete(f"{API_PREFIX}/correspondence/{corr.id}")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_correspondence_not_found(self, client, svc):
        resp = await client.delete(f"{API_PREFIX}/correspondence/CORR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_submit_correspondence(self, client, svc):
        corr = svc.create_correspondence(_make_corr_create())
        resp = await client.post(
            f"{API_PREFIX}/correspondence/{corr.id}/submit"
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "SUBMITTED"

    @pytest.mark.anyio
    async def test_submit_invalid_status(self, client, svc):
        corr = svc.create_correspondence(_make_corr_create())
        svc.submit_correspondence(corr.id)
        resp = await client.post(
            f"{API_PREFIX}/correspondence/{corr.id}/submit"
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_link_correspondence(self, client, svc):
        c1 = svc.create_correspondence(_make_corr_create(title="Link A"))
        c2 = svc.create_correspondence(_make_corr_create(title="Link B"))
        resp = await client.post(
            f"{API_PREFIX}/correspondence/{c1.id}/link",
            json={"related_id": c2.id},
        )
        assert resp.status_code == 200
        assert c2.id in resp.json()["related_correspondence_ids"]

    @pytest.mark.anyio
    async def test_link_not_found(self, client, svc):
        c1 = svc.create_correspondence(_make_corr_create())
        resp = await client.post(
            f"{API_PREFIX}/correspondence/{c1.id}/link",
            json={"related_id": "CORR-NONEXISTENT"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_link_self(self, client, svc):
        c1 = svc.create_correspondence(_make_corr_create())
        resp = await client.post(
            f"{API_PREFIX}/correspondence/{c1.id}/link",
            json={"related_id": c1.id},
        )
        assert resp.status_code == 400


class TestAPIMetrics:
    """API tests for metrics and deadlines."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client, svc):
        svc._seed_demo_data()
        resp = await client.get(f"{API_PREFIX}/correspondence/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_correspondence"] == 10

    @pytest.mark.anyio
    async def test_get_deadlines(self, client, svc):
        svc._seed_demo_data()
        resp = await client.get(f"{API_PREFIX}/correspondence/deadlines")
        assert resp.status_code == 200
        data = resp.json()
        assert "upcoming" in data
        assert "overdue" in data

    @pytest.mark.anyio
    async def test_get_deadlines_custom_days(self, client, svc):
        svc._seed_demo_data()
        resp = await client.get(
            f"{API_PREFIX}/correspondence/deadlines", params={"days_ahead": 90}
        )
        assert resp.status_code == 200


class TestAPIActionItems:
    """API tests for action item endpoints."""

    @pytest.mark.anyio
    async def test_list_all_action_items(self, client, svc):
        svc._seed_demo_data()
        resp = await client.get(f"{API_PREFIX}/action-items")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15

    @pytest.mark.anyio
    async def test_list_action_items_completed(self, client, svc):
        svc._seed_demo_data()
        resp = await client.get(
            f"{API_PREFIX}/action-items", params={"completed": True}
        )
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_action_items_overdue(self, client, svc):
        svc._seed_demo_data()
        resp = await client.get(
            f"{API_PREFIX}/action-items", params={"overdue_only": True}
        )
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_correspondence_action_items(self, client, svc):
        svc._seed_demo_data()
        resp = await client.get(
            f"{API_PREFIX}/correspondence/CORR-002/action-items"
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    @pytest.mark.anyio
    async def test_list_correspondence_action_items_not_found(self, client, svc):
        resp = await client.get(
            f"{API_PREFIX}/correspondence/CORR-NONEXISTENT/action-items"
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_action_item(self, client, svc):
        corr = svc.create_correspondence(_make_corr_create())
        now = datetime.now(timezone.utc)
        payload = {
            "description": "API Action Item",
            "due_date": (now + timedelta(days=7)).isoformat(),
            "priority": "HIGH",
        }
        resp = await client.post(
            f"{API_PREFIX}/correspondence/{corr.id}/action-items", json=payload
        )
        assert resp.status_code == 201
        assert resp.json()["description"] == "API Action Item"

    @pytest.mark.anyio
    async def test_get_action_item(self, client, svc):
        svc._seed_demo_data()
        resp = await client.get(f"{API_PREFIX}/action-items/AI-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "AI-001"

    @pytest.mark.anyio
    async def test_get_action_item_not_found(self, client, svc):
        resp = await client.get(f"{API_PREFIX}/action-items/AI-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_action_item(self, client, svc):
        svc._seed_demo_data()
        resp = await client.put(
            f"{API_PREFIX}/action-items/AI-003",
            json={"completed": True},
        )
        assert resp.status_code == 200
        assert resp.json()["completed"] is True

    @pytest.mark.anyio
    async def test_delete_action_item(self, client, svc):
        svc._seed_demo_data()
        resp = await client.delete(f"{API_PREFIX}/action-items/AI-001")
        assert resp.status_code == 204


class TestAPITimelines:
    """API tests for timeline endpoints."""

    @pytest.mark.anyio
    async def test_list_timelines(self, client, svc):
        svc._seed_demo_data()
        resp = await client.get(f"{API_PREFIX}/timelines")
        assert resp.status_code == 200
        assert resp.json()["total"] == 3

    @pytest.mark.anyio
    async def test_get_timeline(self, client, svc):
        svc._seed_demo_data()
        resp = await client.get(f"{API_PREFIX}/timelines/TL-001")
        assert resp.status_code == 200
        assert len(resp.json()["milestones"]) > 0

    @pytest.mark.anyio
    async def test_get_timeline_not_found(self, client, svc):
        resp = await client.get(f"{API_PREFIX}/timelines/TL-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_timeline(self, client, svc):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "trial_name": "API Timeline",
        }
        resp = await client.post(f"{API_PREFIX}/timelines", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_update_timeline(self, client, svc):
        svc._seed_demo_data()
        resp = await client.put(
            f"{API_PREFIX}/timelines/TL-001",
            json={"trial_name": "Updated Name"},
        )
        assert resp.status_code == 200
        assert resp.json()["trial_name"] == "Updated Name"

    @pytest.mark.anyio
    async def test_delete_timeline(self, client, svc):
        svc._seed_demo_data()
        resp = await client.delete(f"{API_PREFIX}/timelines/TL-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_add_milestone(self, client, svc):
        svc._seed_demo_data()
        now = datetime.now(timezone.utc)
        payload = {
            "name": "API Milestone",
            "planned_date": (now + timedelta(days=45)).isoformat(),
        }
        resp = await client.post(
            f"{API_PREFIX}/timelines/TL-001/milestones", json=payload
        )
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_update_milestone(self, client, svc):
        svc._seed_demo_data()
        resp = await client.put(
            f"{API_PREFIX}/timelines/TL-001/milestones/0",
            json={"status": "DELAYED"},
        )
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_update_milestone_out_of_range(self, client, svc):
        svc._seed_demo_data()
        resp = await client.put(
            f"{API_PREFIX}/timelines/TL-001/milestones/999",
            json={"status": "DELAYED"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_delete_milestone(self, client, svc):
        svc._seed_demo_data()
        tl_before = svc.get_timeline("TL-001")
        count_before = len(tl_before.milestones)
        resp = await client.delete(
            f"{API_PREFIX}/timelines/TL-001/milestones/0"
        )
        assert resp.status_code == 200
        assert len(resp.json()["milestones"]) == count_before - 1


class TestAPIContacts:
    """API tests for agency contact endpoints."""

    @pytest.mark.anyio
    async def test_list_contacts(self, client, svc):
        svc._seed_demo_data()
        resp = await client.get(f"{API_PREFIX}/contacts")
        assert resp.status_code == 200
        assert resp.json()["total"] == 8

    @pytest.mark.anyio
    async def test_list_contacts_filter_agency(self, client, svc):
        svc._seed_demo_data()
        resp = await client.get(
            f"{API_PREFIX}/contacts", params={"agency": "FDA"}
        )
        assert resp.status_code == 200
        assert all(c["agency"] == "FDA" for c in resp.json()["items"])

    @pytest.mark.anyio
    async def test_get_contact(self, client, svc):
        svc._seed_demo_data()
        resp = await client.get(f"{API_PREFIX}/contacts/AC-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "AC-001"

    @pytest.mark.anyio
    async def test_get_contact_not_found(self, client, svc):
        resp = await client.get(f"{API_PREFIX}/contacts/AC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_contact(self, client, svc):
        payload = {
            "name": "API Contact",
            "agency": "FDA",
            "title": "Reviewer",
        }
        resp = await client.post(f"{API_PREFIX}/contacts", json=payload)
        assert resp.status_code == 201
        assert resp.json()["name"] == "API Contact"

    @pytest.mark.anyio
    async def test_update_contact(self, client, svc):
        svc._seed_demo_data()
        resp = await client.put(
            f"{API_PREFIX}/contacts/AC-001",
            json={"title": "Updated Title"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"

    @pytest.mark.anyio
    async def test_delete_contact(self, client, svc):
        svc._seed_demo_data()
        resp = await client.delete(f"{API_PREFIX}/contacts/AC-001")
        assert resp.status_code == 204


class TestAPIAgencySummary:
    """API tests for agency relationship summary."""

    @pytest.mark.anyio
    async def test_agency_summary(self, client, svc):
        svc._seed_demo_data()
        resp = await client.get(f"{API_PREFIX}/agency/FDA/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agency"] == "FDA"
        assert data["total_correspondence"] > 0

    @pytest.mark.anyio
    async def test_agency_summary_ema(self, client, svc):
        svc._seed_demo_data()
        resp = await client.get(f"{API_PREFIX}/agency/EMA/summary")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_agency_summary_empty(self, client, svc):
        resp = await client.get(f"{API_PREFIX}/agency/TGA/summary")
        assert resp.status_code == 200
        assert resp.json()["total_correspondence"] == 0
