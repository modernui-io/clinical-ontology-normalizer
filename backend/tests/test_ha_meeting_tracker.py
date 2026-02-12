"""Tests for Health Authority Meeting Tracker (HA-MEET).

Covers:
- Seed data verification (meetings, briefing docs, minutes, action items, commitments)
- Meeting CRUD (create, read, update, delete, list, filter by trial)
- Briefing document CRUD (create, read, update, delete, list, filter by meeting)
- Meeting minutes CRUD (create, read, update, delete, list, filter by meeting)
- Action item CRUD (create, read, update, delete, list, filter by meeting)
- Commitment CRUD (create, read, update, delete, list, filter by trial)
- Metrics computation
- Error handling (404s)
- Edge cases (empty filters, nonexistent IDs)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.ha_meeting_tracker_service import (
    HAMeetingTrackerService,
    get_ha_meeting_tracker_service,
    reset_ha_meeting_tracker_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/ha-meeting-tracker"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_ha_meeting_tracker_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> HAMeetingTrackerService:
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


def _make_meeting_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "meeting_type": "type_b",
        "health_authority": "fda",
        "title": "Test HA Meeting",
        "objective": "Discuss test objectives",
        "regulatory_lead": "Dr. Test Lead",
    }
    defaults.update(overrides)
    return defaults


def _make_briefing_doc_create(**overrides) -> dict:
    defaults = {
        "meeting_id": "HAM-001",
        "title": "Test Briefing Document",
        "version": "1.0",
        "author": "Dr. Test Author",
        "sections": ["Executive Summary", "Clinical Data"],
    }
    defaults.update(overrides)
    return defaults


def _make_minutes_create(**overrides) -> dict:
    defaults = {
        "meeting_id": "HAM-001",
        "summary": "Test meeting summary with key discussion points.",
        "recorded_by": "Dr. Test Recorder",
        "key_outcomes": ["Outcome 1", "Outcome 2"],
        "agreements": ["Agreement 1"],
    }
    defaults.update(overrides)
    return defaults


def _make_action_item_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "meeting_id": "HAM-001",
        "action_description": "Test action item description",
        "assigned_to": "Dr. Test Assignee",
        "priority": "high",
        "due_date": (now + timedelta(days=30)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_commitment_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "meeting_id": "HAM-001",
        "trial_id": EYLEA_TRIAL,
        "commitment_text": "Test commitment for regulatory milestone",
        "health_authority": "fda",
        "source": "Test Meeting Minutes",
        "responsible_person": "Dr. Test Person",
        "due_date": (now + timedelta(days=90)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_meetings_count(self, svc: HAMeetingTrackerService):
        meetings = svc.list_meetings()
        assert len(meetings) == 12

    def test_seed_meetings_across_trials(self, svc: HAMeetingTrackerService):
        eylea = svc.list_meetings(trial_id=EYLEA_TRIAL)
        dupixent = svc.list_meetings(trial_id=DUPIXENT_TRIAL)
        libtayo = svc.list_meetings(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) == 4
        assert len(dupixent) == 4
        assert len(libtayo) == 4

    def test_seed_briefing_docs_count(self, svc: HAMeetingTrackerService):
        docs = svc.list_briefing_docs()
        assert len(docs) == 12

    def test_seed_minutes_count(self, svc: HAMeetingTrackerService):
        minutes = svc.list_minutes()
        assert len(minutes) == 10

    def test_seed_action_items_count(self, svc: HAMeetingTrackerService):
        items = svc.list_action_items()
        assert len(items) == 15

    def test_seed_commitments_count(self, svc: HAMeetingTrackerService):
        commitments = svc.list_commitments()
        assert len(commitments) == 12

    def test_seed_meeting_has_key_questions(self, svc: HAMeetingTrackerService):
        meeting = svc.get_meeting("HAM-001")
        assert meeting is not None
        assert len(meeting.key_questions) >= 2

    def test_seed_meeting_statuses_varied(self, svc: HAMeetingTrackerService):
        meetings = svc.list_meetings()
        statuses = {m.status.value for m in meetings}
        assert "completed" in statuses
        assert "scheduled" in statuses
        assert "planning" in statuses

    def test_seed_meeting_authorities_varied(self, svc: HAMeetingTrackerService):
        meetings = svc.list_meetings()
        authorities = {m.health_authority.value for m in meetings}
        assert "fda" in authorities
        assert "ema" in authorities

    def test_seed_meeting_types_varied(self, svc: HAMeetingTrackerService):
        meetings = svc.list_meetings()
        types = {m.meeting_type.value for m in meetings}
        assert len(types) >= 5


# =====================================================================
# MEETING CRUD
# =====================================================================


class TestMeetingCrud:
    """Test meeting create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_meetings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meetings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_meetings_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meetings", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_meeting(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meetings/HAM-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "HAM-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_meeting_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meetings/HAM-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_meeting(self, client: AsyncClient):
        payload = _make_meeting_create()
        resp = await client.post(f"{API_PREFIX}/meetings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test HA Meeting"
        assert data["id"].startswith("HAM-")
        assert data["status"] == "planning"

    @pytest.mark.anyio
    async def test_update_meeting(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/meetings/HAM-003",
            json={"status": "completed", "duration_minutes": 150},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["duration_minutes"] == 150

    @pytest.mark.anyio
    async def test_update_meeting_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/meetings/HAM-NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_meeting(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/meetings/HAM-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/meetings/HAM-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_meeting_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/meetings/HAM-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# BRIEFING DOCUMENT CRUD
# =====================================================================


class TestBriefingDocCrud:
    """Test briefing document create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_briefing_docs(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/briefing-docs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_briefing_docs_filter_meeting(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/briefing-docs", params={"meeting_id": "HAM-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["meeting_id"] == "HAM-001"

    @pytest.mark.anyio
    async def test_get_briefing_doc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/briefing-docs/BD-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "BD-001"
        assert data["meeting_id"] == "HAM-001"

    @pytest.mark.anyio
    async def test_get_briefing_doc_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/briefing-docs/BD-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_briefing_doc(self, client: AsyncClient):
        payload = _make_briefing_doc_create()
        resp = await client.post(f"{API_PREFIX}/briefing-docs", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Briefing Document"
        assert data["id"].startswith("BD-")

    @pytest.mark.anyio
    async def test_update_briefing_doc(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/briefing-docs/BD-003",
            json={"status": "approved", "page_count": 125},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["page_count"] == 125

    @pytest.mark.anyio
    async def test_update_briefing_doc_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/briefing-docs/BD-NONEXISTENT",
            json={"status": "approved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_briefing_doc(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/briefing-docs/BD-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/briefing-docs/BD-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_briefing_doc_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/briefing-docs/BD-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# MEETING MINUTES CRUD
# =====================================================================


class TestMinutesCrud:
    """Test meeting minutes create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_minutes(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/minutes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_minutes_filter_meeting(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/minutes", params={"meeting_id": "HAM-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["meeting_id"] == "HAM-001"

    @pytest.mark.anyio
    async def test_get_minutes(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/minutes/MIN-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "MIN-001"
        assert data["meeting_id"] == "HAM-001"

    @pytest.mark.anyio
    async def test_get_minutes_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/minutes/MIN-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_minutes(self, client: AsyncClient):
        payload = _make_minutes_create()
        resp = await client.post(f"{API_PREFIX}/minutes", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["summary"] == "Test meeting summary with key discussion points."
        assert data["id"].startswith("MIN-")

    @pytest.mark.anyio
    async def test_update_minutes(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/minutes/MIN-001",
            json={"ha_feedback": "Updated feedback from HA", "approved_by": "VP Regulatory"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ha_feedback"] == "Updated feedback from HA"
        assert data["approved_by"] == "VP Regulatory"

    @pytest.mark.anyio
    async def test_update_minutes_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/minutes/MIN-NONEXISTENT",
            json={"ha_feedback": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_minutes(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/minutes/MIN-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/minutes/MIN-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_minutes_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/minutes/MIN-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# ACTION ITEM CRUD
# =====================================================================


class TestActionItemCrud:
    """Test action item create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_action_items(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/action-items")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15

    @pytest.mark.anyio
    async def test_list_action_items_filter_meeting(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/action-items", params={"meeting_id": "HAM-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["meeting_id"] == "HAM-001"

    @pytest.mark.anyio
    async def test_get_action_item(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/action-items/AI-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "AI-001"
        assert data["meeting_id"] == "HAM-001"

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
        assert data["action_description"] == "Test action item description"
        assert data["id"].startswith("AI-")
        assert data["status"] == "open"

    @pytest.mark.anyio
    async def test_update_action_item(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/action-items/AI-013",
            json={"status": "in_progress", "notes": "Work started"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["notes"] == "Work started"

    @pytest.mark.anyio
    async def test_update_action_item_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/action-items/AI-NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_action_item(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/action-items/AI-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/action-items/AI-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_action_item_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/action-items/AI-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# COMMITMENT CRUD
# =====================================================================


class TestCommitmentCrud:
    """Test commitment create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_commitments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/commitments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_commitments_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/commitments", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_commitment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/commitments/HC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "HC-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_commitment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/commitments/HC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_commitment(self, client: AsyncClient):
        payload = _make_commitment_create()
        resp = await client.post(f"{API_PREFIX}/commitments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["commitment_text"] == "Test commitment for regulatory milestone"
        assert data["id"].startswith("HC-")
        assert data["status"] == "open"

    @pytest.mark.anyio
    async def test_update_commitment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/commitments/HC-007",
            json={"status": "in_progress", "evidence_reference": "Safety Report v1.0"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["evidence_reference"] == "Safety Report v1.0"

    @pytest.mark.anyio
    async def test_update_commitment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/commitments/HC-NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_commitment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/commitments/HC-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/commitments/HC-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_commitment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/commitments/HC-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test HA meeting metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_meetings"] == 12
        assert data["total_briefing_docs"] == 12
        assert data["total_minutes"] == 10
        assert data["total_action_items"] == 15
        assert data["total_commitments"] == 12
        assert data["approved_briefing_docs"] > 0
        assert len(data["meetings_by_type"]) > 0
        assert len(data["meetings_by_status"]) > 0
        assert len(data["meetings_by_authority"]) > 0

    @pytest.mark.anyio
    async def test_get_metrics_by_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_meetings"] == 4

    @pytest.mark.anyio
    async def test_metrics_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_meetings"] == 0
        assert data["total_briefing_docs"] == 0

    def test_metrics_action_items_by_status(self, svc: HAMeetingTrackerService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.action_items_by_status.values())
        assert total_by_status == metrics.total_action_items

    def test_metrics_commitments_by_status(self, svc: HAMeetingTrackerService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.commitments_by_status.values())
        assert total_by_status == metrics.total_commitments

    def test_metrics_meetings_by_type_sum(self, svc: HAMeetingTrackerService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.meetings_by_type.values())
        assert total_by_type == metrics.total_meetings

    def test_metrics_meetings_by_status_sum(self, svc: HAMeetingTrackerService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.meetings_by_status.values())
        assert total_by_status == metrics.total_meetings

    def test_metrics_meetings_by_authority_sum(self, svc: HAMeetingTrackerService):
        metrics = svc.get_metrics()
        total_by_authority = sum(metrics.meetings_by_authority.values())
        assert total_by_authority == metrics.total_meetings


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_ha_meeting_tracker_service()
        svc2 = get_ha_meeting_tracker_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_ha_meeting_tracker_service()
        svc2 = reset_ha_meeting_tracker_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_ha_meeting_tracker_service()
        svc.delete_meeting("HAM-001")
        assert svc.get_meeting("HAM-001") is None
        svc2 = reset_ha_meeting_tracker_service()
        assert svc2.get_meeting("HAM-001") is not None


# =====================================================================
# EDGE CASES
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_meetings_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meetings")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_briefing_docs_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/briefing-docs")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_minutes_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/minutes")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_action_items_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/action-items")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_commitments_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/commitments")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_briefing_docs_nonexistent_meeting(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/briefing-docs", params={"meeting_id": "HAM-NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_minutes_nonexistent_meeting(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/minutes", params={"meeting_id": "HAM-NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_action_items_nonexistent_meeting(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/action-items", params={"meeting_id": "HAM-NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_commitments_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/commitments", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_create_meeting_with_medical_lead(self, client: AsyncClient):
        payload = _make_meeting_create(medical_lead="Dr. Test Medical Lead")
        resp = await client.post(f"{API_PREFIX}/meetings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["medical_lead"] == "Dr. Test Medical Lead"

    @pytest.mark.anyio
    async def test_create_meeting_with_key_questions(self, client: AsyncClient):
        payload = _make_meeting_create(key_questions=["Q1?", "Q2?", "Q3?"])
        resp = await client.post(f"{API_PREFIX}/meetings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["key_questions"]) == 3


# =====================================================================
# DATA VALIDATION
# =====================================================================


class TestDataValidation:
    """Test detailed data validation across the system."""

    @pytest.mark.anyio
    async def test_meeting_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meetings/HAM-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "meeting_type" in data
        assert "health_authority" in data
        assert "status" in data
        assert "title" in data
        assert "objective" in data
        assert "regulatory_lead" in data
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_briefing_doc_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/briefing-docs/BD-001")
        data = resp.json()
        assert "id" in data
        assert "meeting_id" in data
        assert "title" in data
        assert "version" in data
        assert "author" in data
        assert "status" in data
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_minutes_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/minutes/MIN-001")
        data = resp.json()
        assert "id" in data
        assert "meeting_id" in data
        assert "summary" in data
        assert "key_outcomes" in data
        assert "recorded_by" in data
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_action_item_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/action-items/AI-001")
        data = resp.json()
        assert "id" in data
        assert "meeting_id" in data
        assert "action_description" in data
        assert "assigned_to" in data
        assert "priority" in data
        assert "due_date" in data
        assert "status" in data
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_commitment_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/commitments/HC-001")
        data = resp.json()
        assert "id" in data
        assert "meeting_id" in data
        assert "trial_id" in data
        assert "commitment_text" in data
        assert "health_authority" in data
        assert "source" in data
        assert "status" in data
        assert "responsible_person" in data
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_metrics_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "total_meetings" in data
        assert "meetings_by_type" in data
        assert "meetings_by_status" in data
        assert "meetings_by_authority" in data
        assert "total_briefing_docs" in data
        assert "approved_briefing_docs" in data
        assert "total_minutes" in data
        assert "total_action_items" in data
        assert "action_items_by_status" in data
        assert "overdue_actions" in data
        assert "total_commitments" in data
        assert "commitments_by_status" in data
        assert "overdue_commitments" in data

    def test_completed_meetings_have_actual_date(self, svc: HAMeetingTrackerService):
        meetings = svc.list_meetings()
        completed = [m for m in meetings if m.status.value == "completed"]
        for m in completed:
            assert m.actual_date is not None

    def test_approved_briefing_docs_have_approved_date(self, svc: HAMeetingTrackerService):
        docs = svc.list_briefing_docs()
        approved = [bd for bd in docs if bd.status == "approved"]
        for bd in approved:
            assert bd.approved_date is not None

    def test_completed_action_items_have_completed_date(self, svc: HAMeetingTrackerService):
        items = svc.list_action_items()
        completed = [ai for ai in items if ai.status.value == "completed"]
        for ai in completed:
            assert ai.completed_date is not None

    def test_completed_commitments_have_completed_date(self, svc: HAMeetingTrackerService):
        commitments = svc.list_commitments()
        completed = [c for c in commitments if c.status.value == "completed"]
        for c in completed:
            assert c.completed_date is not None
