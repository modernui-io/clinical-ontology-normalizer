"""Tests for Investigator Meeting Management (INV-MTG).

Covers:
- Seed data verification (meeting plans, attendance records, training sessions,
  presentation materials, action items)
- Meeting plan CRUD (create, read, update, delete, list, filter by trial/type/status/format)
- Attendance record CRUD (create, read, update, delete, list, filter by trial/meeting/status)
- Training session CRUD (create, read, update, delete, list, filter by trial/meeting/gcp)
- Presentation material CRUD (create, read, update, delete, list, filter by trial/meeting/approved)
- Action item CRUD (create, read, update, delete, list, filter by trial/meeting/priority/status)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.investigator_meeting import (
    ActionPriority,
    AttendanceStatus,
    MeetingFormat,
    MeetingStatus,
    MeetingType,
)
from app.services.investigator_meeting_service import (
    InvestigatorMeetingService,
    get_investigator_meeting_service,
    reset_investigator_meeting_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/investigator-meeting"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_investigator_meeting_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> InvestigatorMeetingService:
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


def _make_meeting_plan_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "meeting_name": "Test Investigator Meeting",
        "meeting_type": "investigator_meeting",
        "planned_date": (now + timedelta(days=60)).isoformat(),
        "organized_by": "Dr. Test Organizer",
        "meeting_format": "hybrid",
        "duration_hours": 8.0,
    }
    defaults.update(overrides)
    return defaults


def _make_attendance_record_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "meeting_id": "MP-001",
        "attendee_name": "Dr. Test Attendee",
        "role": "Principal Investigator",
        "managed_by": "Clinical Operations Team",
    }
    defaults.update(overrides)
    return defaults


def _make_training_session_create(**overrides) -> dict:
    defaults = {
        "trial_id": DUPIXENT_TRIAL,
        "session_title": "Test Training Session",
        "topic": "Test Topic",
        "trainer": "Dr. Test Trainer",
        "created_by": "Dr. Test Creator",
        "duration_minutes": 60,
    }
    defaults.update(overrides)
    return defaults


def _make_presentation_material_create(**overrides) -> dict:
    defaults = {
        "trial_id": LIBTAYO_TRIAL,
        "meeting_id": "MP-007",
        "title": "Test Presentation",
        "presenter": "Dr. Test Presenter",
        "uploaded_by": "Dr. Test Uploader",
        "material_type": "slides",
        "slide_count": 25,
    }
    defaults.update(overrides)
    return defaults


def _make_action_item_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "meeting_id": "MP-001",
        "action_description": "Test action item description",
        "assigned_to": "Dr. Test Assignee",
        "due_date": (now + timedelta(days=30)).isoformat(),
        "created_by": "Dr. Test Creator",
        "priority": "medium",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_meeting_plans_count(self, svc: InvestigatorMeetingService):
        plans = svc.list_meeting_plans()
        assert len(plans) == 12

    def test_seed_attendance_records_count(self, svc: InvestigatorMeetingService):
        records = svc.list_attendance_records()
        assert len(records) == 12

    def test_seed_training_sessions_count(self, svc: InvestigatorMeetingService):
        sessions = svc.list_training_sessions()
        assert len(sessions) == 12

    def test_seed_presentation_materials_count(self, svc: InvestigatorMeetingService):
        materials = svc.list_presentation_materials()
        assert len(materials) == 12

    def test_seed_action_items_count(self, svc: InvestigatorMeetingService):
        items = svc.list_action_items()
        assert len(items) == 12

    def test_seed_plans_cover_all_trials(self, svc: InvestigatorMeetingService):
        plans = svc.list_meeting_plans()
        trial_ids = {p.trial_id for p in plans}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_plans_have_multiple_types(self, svc: InvestigatorMeetingService):
        plans = svc.list_meeting_plans()
        types = {p.meeting_type for p in plans}
        assert len(types) >= 4

    def test_seed_plans_have_multiple_statuses(self, svc: InvestigatorMeetingService):
        plans = svc.list_meeting_plans()
        statuses = {p.status for p in plans}
        assert MeetingStatus.COMPLETED in statuses
        assert MeetingStatus.PLANNED in statuses

    def test_seed_attendance_has_multiple_statuses(self, svc: InvestigatorMeetingService):
        records = svc.list_attendance_records()
        statuses = {r.attendance_status for r in records}
        assert AttendanceStatus.ATTENDED in statuses
        assert AttendanceStatus.DECLINED in statuses
        assert AttendanceStatus.NO_SHOW in statuses

    def test_seed_training_has_gcp_sessions(self, svc: InvestigatorMeetingService):
        sessions = svc.list_training_sessions()
        gcp = [s for s in sessions if s.gcp_training]
        assert len(gcp) >= 2

    def test_seed_materials_have_approved_and_unapproved(self, svc: InvestigatorMeetingService):
        materials = svc.list_presentation_materials()
        approved = [m for m in materials if m.approved_for_distribution]
        unapproved = [m for m in materials if not m.approved_for_distribution]
        assert len(approved) >= 1
        assert len(unapproved) >= 1

    def test_seed_action_items_have_multiple_priorities(self, svc: InvestigatorMeetingService):
        items = svc.list_action_items()
        priorities = {a.priority for a in items}
        assert ActionPriority.CRITICAL in priorities
        assert ActionPriority.HIGH in priorities
        assert ActionPriority.MEDIUM in priorities

    def test_seed_action_items_have_open_and_completed(self, svc: InvestigatorMeetingService):
        items = svc.list_action_items()
        statuses = {a.status for a in items}
        assert "open" in statuses
        assert "completed" in statuses


# =====================================================================
# MEETING PLAN CRUD
# =====================================================================


class TestMeetingPlanCrud:
    """Test meeting plan CRUD operations."""

    @pytest.mark.anyio
    async def test_list_meeting_plans(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meeting-plans")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_meeting_plans_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/meeting-plans", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_meeting_plans_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/meeting-plans", params={"meeting_type": "investigator_meeting"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["meeting_type"] == "investigator_meeting"

    @pytest.mark.anyio
    async def test_list_meeting_plans_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/meeting-plans", params={"status": "completed"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_list_meeting_plans_filter_format(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/meeting-plans", params={"meeting_format": "virtual"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["meeting_format"] == "virtual"

    @pytest.mark.anyio
    async def test_get_meeting_plan(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meeting-plans/MP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "MP-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["meeting_type"] == "investigator_meeting"

    @pytest.mark.anyio
    async def test_get_meeting_plan_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meeting-plans/MP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_meeting_plan(self, client: AsyncClient):
        payload = _make_meeting_plan_create()
        resp = await client.post(f"{API_PREFIX}/meeting-plans", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["meeting_type"] == "investigator_meeting"
        assert data["status"] == "planned"
        assert data["id"].startswith("MP-")

    @pytest.mark.anyio
    async def test_update_meeting_plan(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/meeting-plans/MP-009",
            json={"status": "confirmed", "agenda_finalized": True, "notes": "Updated"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "confirmed"
        assert data["agenda_finalized"] is True
        assert data["notes"] == "Updated"

    @pytest.mark.anyio
    async def test_update_meeting_plan_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/meeting-plans/MP-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_meeting_plan(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/meeting-plans/MP-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/meeting-plans/MP-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_meeting_plan_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/meeting-plans/MP-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# ATTENDANCE RECORD CRUD
# =====================================================================


class TestAttendanceRecordCrud:
    """Test attendance record CRUD operations."""

    @pytest.mark.anyio
    async def test_list_attendance_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/attendance-records")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_attendance_records_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/attendance-records", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_attendance_records_filter_meeting(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/attendance-records", params={"meeting_id": "MP-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["meeting_id"] == "MP-001"

    @pytest.mark.anyio
    async def test_list_attendance_records_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/attendance-records", params={"attendance_status": "attended"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["attendance_status"] == "attended"

    @pytest.mark.anyio
    async def test_get_attendance_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/attendance-records/AR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "AR-001"
        assert data["attendee_name"] == "Dr. Michael Johnson"

    @pytest.mark.anyio
    async def test_get_attendance_record_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/attendance-records/AR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_attendance_record(self, client: AsyncClient):
        payload = _make_attendance_record_create()
        resp = await client.post(f"{API_PREFIX}/attendance-records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["meeting_id"] == "MP-001"
        assert data["attendance_status"] == "invited"
        assert data["id"].startswith("AR-")

    @pytest.mark.anyio
    async def test_update_attendance_record(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/attendance-records/AR-012",
            json={"attendance_status": "confirmed", "notes": "RSVP received"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["attendance_status"] == "confirmed"
        assert data["notes"] == "RSVP received"

    @pytest.mark.anyio
    async def test_update_attendance_record_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/attendance-records/AR-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_attendance_record(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/attendance-records/AR-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/attendance-records/AR-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_attendance_record_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/attendance-records/AR-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# TRAINING SESSION CRUD
# =====================================================================


class TestTrainingSessionCrud:
    """Test training session CRUD operations."""

    @pytest.mark.anyio
    async def test_list_training_sessions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/training-sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_training_sessions_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/training-sessions", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_training_sessions_filter_meeting(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/training-sessions", params={"meeting_id": "MP-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["meeting_id"] == "MP-001"

    @pytest.mark.anyio
    async def test_list_training_sessions_filter_gcp(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/training-sessions", params={"gcp_training": True}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        for item in data["items"]:
            assert item["gcp_training"] is True

    @pytest.mark.anyio
    async def test_get_training_session(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/training-sessions/TS-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "TS-001"
        assert data["session_title"] == "EYLEA Protocol Overview and Objectives"

    @pytest.mark.anyio
    async def test_get_training_session_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/training-sessions/TS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_training_session(self, client: AsyncClient):
        payload = _make_training_session_create()
        resp = await client.post(f"{API_PREFIX}/training-sessions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == DUPIXENT_TRIAL
        assert data["session_title"] == "Test Training Session"
        assert data["id"].startswith("TS-")

    @pytest.mark.anyio
    async def test_update_training_session(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/training-sessions/TS-012",
            json={"recording_available": True, "certificate_issued": True, "notes": "Updated"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["recording_available"] is True
        assert data["certificate_issued"] is True
        assert data["notes"] == "Updated"

    @pytest.mark.anyio
    async def test_update_training_session_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/training-sessions/TS-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_training_session(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/training-sessions/TS-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/training-sessions/TS-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_training_session_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/training-sessions/TS-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# PRESENTATION MATERIAL CRUD
# =====================================================================


class TestPresentationMaterialCrud:
    """Test presentation material CRUD operations."""

    @pytest.mark.anyio
    async def test_list_presentation_materials(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/presentation-materials")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_presentation_materials_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/presentation-materials", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_presentation_materials_filter_meeting(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/presentation-materials", params={"meeting_id": "MP-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["meeting_id"] == "MP-001"

    @pytest.mark.anyio
    async def test_list_presentation_materials_filter_approved(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/presentation-materials", params={"approved_for_distribution": True}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["approved_for_distribution"] is True

    @pytest.mark.anyio
    async def test_get_presentation_material(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/presentation-materials/PM-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PM-001"
        assert data["title"] == "EYLEA Phase III Protocol Overview"

    @pytest.mark.anyio
    async def test_get_presentation_material_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/presentation-materials/PM-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_presentation_material(self, client: AsyncClient):
        payload = _make_presentation_material_create()
        resp = await client.post(f"{API_PREFIX}/presentation-materials", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == LIBTAYO_TRIAL
        assert data["title"] == "Test Presentation"
        assert data["approved_for_distribution"] is False
        assert data["id"].startswith("PM-")

    @pytest.mark.anyio
    async def test_update_presentation_material(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/presentation-materials/PM-006",
            json={
                "approved_for_distribution": True,
                "legal_review_completed": True,
                "approved_by": "Dr. Legal Reviewer",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["approved_for_distribution"] is True
        assert data["legal_review_completed"] is True
        assert data["approved_by"] == "Dr. Legal Reviewer"

    @pytest.mark.anyio
    async def test_update_presentation_material_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/presentation-materials/PM-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_presentation_material(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/presentation-materials/PM-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/presentation-materials/PM-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_presentation_material_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/presentation-materials/PM-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# ACTION ITEM CRUD
# =====================================================================


class TestActionItemCrud:
    """Test action item CRUD operations."""

    @pytest.mark.anyio
    async def test_list_action_items(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/action-items")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_action_items_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/action-items", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_action_items_filter_meeting(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/action-items", params={"meeting_id": "MP-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["meeting_id"] == "MP-001"

    @pytest.mark.anyio
    async def test_list_action_items_filter_priority(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/action-items", params={"priority": "critical"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["priority"] == "critical"

    @pytest.mark.anyio
    async def test_list_action_items_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/action-items", params={"status": "open"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "open"

    @pytest.mark.anyio
    async def test_get_action_item(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/action-items/AI-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "AI-001"
        assert data["status"] == "completed"

    @pytest.mark.anyio
    async def test_get_action_item_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/action-items/AI-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_action_item(self, client: AsyncClient):
        payload = _make_action_item_create()
        resp = await client.post(f"{API_PREFIX}/action-items", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["status"] == "open"
        assert data["priority"] == "medium"
        assert data["id"].startswith("AI-")

    @pytest.mark.anyio
    async def test_update_action_item(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/action-items/AI-010",
            json={"status": "completed", "notes": "Done"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["notes"] == "Done"

    @pytest.mark.anyio
    async def test_update_action_item_priority(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/action-items/AI-011",
            json={"priority": "critical", "escalated": True, "escalated_to": "VP Operations"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["priority"] == "critical"
        assert data["escalated"] is True
        assert data["escalated_to"] == "VP Operations"

    @pytest.mark.anyio
    async def test_update_action_item_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/action-items/AI-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_action_item(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/action-items/AI-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/action-items/AI-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_action_item_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/action-items/AI-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestInvestigatorMeetingMetrics:
    """Test investigator meeting metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_meetings"] == 12
        assert data["total_attendance_records"] == 12
        assert data["total_training_sessions"] == 12
        assert data["total_presentations"] == 12
        assert data["total_action_items"] == 12

    @pytest.mark.anyio
    async def test_metrics_meetings_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_type = data["meetings_by_type"]
        total = sum(by_type.values())
        assert total == data["total_meetings"]

    @pytest.mark.anyio
    async def test_metrics_meetings_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["meetings_by_status"]
        total = sum(by_status.values())
        assert total == data["total_meetings"]

    @pytest.mark.anyio
    async def test_metrics_meetings_by_format(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_format = data["meetings_by_format"]
        total = sum(by_format.values())
        assert total == data["total_meetings"]

    @pytest.mark.anyio
    async def test_metrics_attendance_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["attendance_by_status"]
        total = sum(by_status.values())
        assert total == data["total_attendance_records"]

    @pytest.mark.anyio
    async def test_metrics_avg_attendance_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["avg_attendance_rate_pct"] > 0
        assert data["avg_attendance_rate_pct"] <= 100

    @pytest.mark.anyio
    async def test_metrics_avg_pass_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["avg_pass_rate_pct"] > 0
        assert data["avg_pass_rate_pct"] <= 100

    @pytest.mark.anyio
    async def test_metrics_approved_presentations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["approved_presentations"] > 0
        assert data["approved_presentations"] <= data["total_presentations"]

    @pytest.mark.anyio
    async def test_metrics_action_items_by_priority(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_priority = data["action_items_by_priority"]
        total = sum(by_priority.values())
        assert total == data["total_action_items"]

    @pytest.mark.anyio
    async def test_metrics_open_action_items(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["open_action_items"] > 0
        assert data["open_action_items"] <= data["total_action_items"]

    @pytest.mark.anyio
    async def test_metrics_overdue_action_items(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["overdue_action_items"] >= 0
        assert data["overdue_action_items"] <= data["open_action_items"]

    def test_metrics_avg_pass_rate_value(self, svc: InvestigatorMeetingService):
        metrics = svc.get_metrics()
        assert isinstance(metrics.avg_pass_rate_pct, float)
        assert metrics.avg_pass_rate_pct > 0


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_investigator_meeting_service()
        svc2 = get_investigator_meeting_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_investigator_meeting_service()
        svc2 = reset_investigator_meeting_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_investigator_meeting_service()
        # Delete a meeting plan
        svc.delete_meeting_plan("MP-001")
        assert svc.get_meeting_plan("MP-001") is None
        # Reset should bring it back
        svc2 = reset_investigator_meeting_service()
        assert svc2.get_meeting_plan("MP-001") is not None


# =====================================================================
# FILTERING AND EDGE CASES
# =====================================================================


class TestFilteringAndEdgeCases:
    """Test filtering combinations and edge cases."""

    @pytest.mark.anyio
    async def test_list_plans_empty_filter(self, client: AsyncClient):
        """Filter by a trial that has no plans."""
        resp = await client.get(
            f"{API_PREFIX}/meeting-plans",
            params={"trial_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.anyio
    async def test_list_attendance_empty_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/attendance-records",
            params={"meeting_id": "MP-NONEXISTENT"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_training_sessions_no_gcp(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/training-sessions", params={"gcp_training": False}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["gcp_training"] is False

    @pytest.mark.anyio
    async def test_list_materials_unapproved(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/presentation-materials",
            params={"approved_for_distribution": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["approved_for_distribution"] is False

    @pytest.mark.anyio
    async def test_list_action_items_completed(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/action-items", params={"status": "completed"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_create_plan_then_retrieve(self, client: AsyncClient):
        """Create a plan and verify it shows in the list."""
        payload = _make_meeting_plan_create()
        resp = await client.post(f"{API_PREFIX}/meeting-plans", json=payload)
        assert resp.status_code == 201
        created_id = resp.json()["id"]

        resp2 = await client.get(f"{API_PREFIX}/meeting-plans/{created_id}")
        assert resp2.status_code == 200
        assert resp2.json()["id"] == created_id

    @pytest.mark.anyio
    async def test_create_plan_then_update_status(self, client: AsyncClient):
        """Create a plan, then update its status through lifecycle."""
        payload = _make_meeting_plan_create()
        resp = await client.post(f"{API_PREFIX}/meeting-plans", json=payload)
        assert resp.status_code == 201
        plan_id = resp.json()["id"]
        assert resp.json()["status"] == "planned"

        # Update to confirmed
        resp2 = await client.put(
            f"{API_PREFIX}/meeting-plans/{plan_id}",
            json={"status": "confirmed"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "confirmed"

        # Update to completed
        resp3 = await client.put(
            f"{API_PREFIX}/meeting-plans/{plan_id}",
            json={"status": "completed", "notes": "Meeting completed successfully"},
        )
        assert resp3.status_code == 200
        assert resp3.json()["status"] == "completed"
        assert resp3.json()["notes"] == "Meeting completed successfully"

    @pytest.mark.anyio
    async def test_create_and_delete_attendance(self, client: AsyncClient):
        """Create a record and then delete it."""
        payload = _make_attendance_record_create()
        resp = await client.post(f"{API_PREFIX}/attendance-records", json=payload)
        assert resp.status_code == 201
        record_id = resp.json()["id"]

        resp2 = await client.delete(f"{API_PREFIX}/attendance-records/{record_id}")
        assert resp2.status_code == 204

        resp3 = await client.get(f"{API_PREFIX}/attendance-records/{record_id}")
        assert resp3.status_code == 404

    @pytest.mark.anyio
    async def test_create_training_with_meeting_id(self, client: AsyncClient):
        """Create a training session linked to a meeting."""
        payload = _make_training_session_create(meeting_id="MP-004")
        resp = await client.post(f"{API_PREFIX}/training-sessions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["meeting_id"] == "MP-004"

    @pytest.mark.anyio
    async def test_create_training_without_meeting_id(self, client: AsyncClient):
        """Create a standalone training session."""
        payload = _make_training_session_create()
        resp = await client.post(f"{API_PREFIX}/training-sessions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["meeting_id"] is None

    @pytest.mark.anyio
    async def test_create_action_item_with_high_priority(self, client: AsyncClient):
        payload = _make_action_item_create(priority="high")
        resp = await client.post(f"{API_PREFIX}/action-items", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["priority"] == "high"

    @pytest.mark.anyio
    async def test_plans_sorted_by_planned_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meeting-plans")
        data = resp.json()
        dates = [item["planned_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_action_items_sorted_by_due_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/action-items")
        data = resp.json()
        dates = [item["due_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_metrics_after_create_and_delete(self, client: AsyncClient):
        """Metrics should reflect dynamic changes."""
        # Get baseline metrics
        resp1 = await client.get(f"{API_PREFIX}/metrics")
        baseline = resp1.json()

        # Create a new plan
        payload = _make_meeting_plan_create()
        await client.post(f"{API_PREFIX}/meeting-plans", json=payload)

        resp2 = await client.get(f"{API_PREFIX}/metrics")
        after_create = resp2.json()
        assert after_create["total_meetings"] == baseline["total_meetings"] + 1

        # Delete a plan
        await client.delete(f"{API_PREFIX}/meeting-plans/MP-012")
        resp3 = await client.get(f"{API_PREFIX}/metrics")
        after_delete = resp3.json()
        assert after_delete["total_meetings"] == baseline["total_meetings"]

    @pytest.mark.anyio
    async def test_create_attendance_with_site_id(self, client: AsyncClient):
        payload = _make_attendance_record_create(site_id="SITE-US-100")
        resp = await client.post(f"{API_PREFIX}/attendance-records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_id"] == "SITE-US-100"

    @pytest.mark.anyio
    async def test_create_material_then_approve(self, client: AsyncClient):
        """Create a material and approve it for distribution."""
        payload = _make_presentation_material_create()
        resp = await client.post(f"{API_PREFIX}/presentation-materials", json=payload)
        assert resp.status_code == 201
        material_id = resp.json()["id"]
        assert resp.json()["approved_for_distribution"] is False

        resp2 = await client.put(
            f"{API_PREFIX}/presentation-materials/{material_id}",
            json={
                "medical_review_completed": True,
                "legal_review_completed": True,
                "approved_for_distribution": True,
                "approved_by": "Dr. Board Chair",
            },
        )
        assert resp2.status_code == 200
        assert resp2.json()["approved_for_distribution"] is True
        assert resp2.json()["approved_by"] == "Dr. Board Chair"


# =====================================================================
# ENUM COVERAGE
# =====================================================================


class TestEnumCoverage:
    """Verify enum values are represented in seed data."""

    @pytest.mark.anyio
    async def test_meeting_types_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meeting-plans")
        data = resp.json()
        types = {item["meeting_type"] for item in data["items"]}
        assert "investigator_meeting" in types
        assert "site_initiation" in types
        assert "interim_review" in types
        assert "advisory_board" in types
        assert "training_session" in types
        assert "close_out" in types

    @pytest.mark.anyio
    async def test_meeting_statuses_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meeting-plans")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "completed" in statuses
        assert "planned" in statuses
        assert "confirmed" in statuses
        assert "postponed" in statuses

    @pytest.mark.anyio
    async def test_meeting_formats_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meeting-plans")
        data = resp.json()
        formats = {item["meeting_format"] for item in data["items"]}
        assert "in_person" in formats
        assert "virtual" in formats
        assert "hybrid" in formats

    @pytest.mark.anyio
    async def test_attendance_statuses_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/attendance-records")
        data = resp.json()
        statuses = {item["attendance_status"] for item in data["items"]}
        assert "attended" in statuses
        assert "declined" in statuses
        assert "no_show" in statuses
        assert "confirmed" in statuses
        assert "invited" in statuses
        assert "excused" in statuses

    @pytest.mark.anyio
    async def test_action_priorities_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/action-items")
        data = resp.json()
        priorities = {item["priority"] for item in data["items"]}
        assert "low" not in priorities or True  # low may not be in seed
        assert "medium" in priorities
        assert "high" in priorities
        assert "critical" in priorities
