"""Tests for Study Closeout module.

Covers:
- Seed data verification (closeouts, site closeouts, tasks, archives,
  regulatory notifications, financial reconciliations)
- Study closeout CRUD (create, read, update, list, filter)
- Study closeout initiation workflow
- Site closeout CRUD and workflow (schedule -> visit -> documents -> IP -> close)
- Closeout task management and dependencies
- Document archiving
- Regulatory notifications
- Financial reconciliation lifecycle
- Progress tracking
- Metrics aggregation
- Error cases (404s, invalid transitions)
- Edge cases and service singleton pattern
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.study_closeout import (
    CloseoutStatus,
    CloseoutTaskType,
    FinancialReconciliationStatus,
    SiteCloseoutStatus,
    TaskStatus,
)
from app.services.study_closeout_service import (
    StudyCloseoutService,
    get_study_closeout_service,
    reset_study_closeout_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"

API_PREFIX = "/api/v1/study-closeout"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_study_closeout_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> StudyCloseoutService:
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


def _make_closeout_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": "TRIAL-NEW-001",
        "trial_name": "New Phase III Trial",
        "closeout_lead": "Dr. Test Lead",
        "planned_start_date": (now + timedelta(days=14)).isoformat(),
        "target_completion_date": (now + timedelta(days=120)).isoformat(),
        "total_sites": 5,
    }
    defaults.update(overrides)
    return defaults


def _make_site_closeout_create(**overrides) -> dict:
    defaults = {
        "site_id": "SITE-NEW-001",
        "site_name": "Test Clinical Site",
        "monitor": "Test Monitor",
    }
    defaults.update(overrides)
    return defaults


def _make_task_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "task_type": "site_closure_visit",
        "description": "Test closeout task",
        "assigned_to": "Test Assignee",
        "due_date": (now + timedelta(days=14)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_closeouts_count(self, svc: StudyCloseoutService):
        closeouts = svc.list_closeouts()
        assert len(closeouts) == 2

    def test_seed_closeout_statuses(self, svc: StudyCloseoutService):
        closeouts = svc.list_closeouts()
        statuses = {c.status for c in closeouts}
        assert CloseoutStatus.IN_PROGRESS in statuses
        assert CloseoutStatus.PLANNING in statuses

    def test_seed_site_closeouts_count_sco001(self, svc: StudyCloseoutService):
        sites = svc.list_site_closeouts("SCO-001")
        assert len(sites) == 6

    def test_seed_site_closeouts_count_sco002(self, svc: StudyCloseoutService):
        sites = svc.list_site_closeouts("SCO-002")
        assert len(sites) == 4

    def test_seed_site_closeout_statuses(self, svc: StudyCloseoutService):
        sites = svc.list_site_closeouts("SCO-001")
        statuses = {s.status for s in sites}
        assert SiteCloseoutStatus.CLOSED in statuses
        assert SiteCloseoutStatus.PENDING in statuses
        assert SiteCloseoutStatus.SCHEDULED in statuses

    def test_seed_tasks_count(self, svc: StudyCloseoutService):
        tasks = svc.list_tasks("SCO-001")
        assert len(tasks) == 14

    def test_seed_task_types(self, svc: StudyCloseoutService):
        tasks = svc.list_tasks("SCO-001")
        types = {t.task_type for t in tasks}
        assert CloseoutTaskType.SITE_CLOSURE_VISIT in types
        assert CloseoutTaskType.IP_RECONCILIATION in types
        assert CloseoutTaskType.DATABASE_LOCK in types
        assert CloseoutTaskType.DATA_ARCHIVING in types

    def test_seed_archives_count(self, svc: StudyCloseoutService):
        archives = svc.list_archives("SCO-001")
        assert len(archives) == 3

    def test_seed_regulatory_notifications_count(self, svc: StudyCloseoutService):
        notifs = svc.list_regulatory_notifications("SCO-001")
        assert len(notifs) == 5

    def test_seed_financial_reconciliations_count(self, svc: StudyCloseoutService):
        recs = svc.list_financial_reconciliations("SCO-001")
        assert len(recs) == 4

    def test_seed_database_locked(self, svc: StudyCloseoutService):
        co = svc.get_closeout("SCO-001")
        assert co is not None
        assert co.database_locked is True
        assert co.database_lock_date is not None

    def test_seed_closed_sites_count(self, svc: StudyCloseoutService):
        co = svc.get_closeout("SCO-001")
        assert co is not None
        assert co.sites_closed == 2


# =====================================================================
# STUDY CLOSEOUT CRUD
# =====================================================================


class TestStudyCloseoutCrud:
    """Test study closeout CRUD operations."""

    @pytest.mark.anyio
    async def test_list_closeouts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/closeouts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    @pytest.mark.anyio
    async def test_list_closeouts_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/closeouts", params={"status": "in_progress"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "in_progress"

    @pytest.mark.anyio
    async def test_list_closeouts_filter_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/closeouts", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_closeout(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/closeouts/SCO-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SCO-001"
        assert data["trial_name"] == "EYLEA Phase III - Diabetic Macular Edema"

    @pytest.mark.anyio
    async def test_get_closeout_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/closeouts/SCO-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_closeout(self, client: AsyncClient):
        payload = _make_closeout_create()
        resp = await client.post(f"{API_PREFIX}/closeouts", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_name"] == "New Phase III Trial"
        assert data["status"] == "not_started"
        assert data["id"].startswith("SCO-")

    @pytest.mark.anyio
    async def test_update_closeout(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/closeouts/SCO-001",
            json={"closeout_lead": "Dr. Updated Lead"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["closeout_lead"] == "Dr. Updated Lead"

    @pytest.mark.anyio
    async def test_update_closeout_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/closeouts/SCO-NONEXISTENT",
            json={"closeout_lead": "Test"},
        )
        assert resp.status_code == 404


# =====================================================================
# STUDY CLOSEOUT INITIATION
# =====================================================================


class TestStudyCloseoutInitiation:
    """Test study closeout initiation workflow."""

    @pytest.mark.anyio
    async def test_initiate_planning_closeout(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/closeouts/SCO-002/initiate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["actual_start_date"] is not None

    @pytest.mark.anyio
    async def test_initiate_not_started_closeout(self, client: AsyncClient):
        # Create a not_started closeout first
        payload = _make_closeout_create()
        create_resp = await client.post(f"{API_PREFIX}/closeouts", json=payload)
        closeout_id = create_resp.json()["id"]

        resp = await client.post(f"{API_PREFIX}/closeouts/{closeout_id}/initiate")
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"

    @pytest.mark.anyio
    async def test_initiate_already_in_progress(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/closeouts/SCO-001/initiate")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_initiate_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/closeouts/SCO-NONEXISTENT/initiate")
        assert resp.status_code == 404


# =====================================================================
# SITE CLOSEOUT CRUD
# =====================================================================


class TestSiteCloseoutCrud:
    """Test site closeout CRUD operations."""

    @pytest.mark.anyio
    async def test_list_site_closeouts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/closeouts/SCO-001/site-closeouts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6

    @pytest.mark.anyio
    async def test_list_site_closeouts_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/closeouts/SCO-001/site-closeouts",
            params={"status": "closed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["status"] == "closed"

    @pytest.mark.anyio
    async def test_list_site_closeouts_nonexistent_closeout(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/closeouts/SCO-NONEXISTENT/site-closeouts"
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_site_closeout(self, client: AsyncClient):
        payload = _make_site_closeout_create()
        resp = await client.post(
            f"{API_PREFIX}/closeouts/SCO-001/site-closeouts", json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_name"] == "Test Clinical Site"
        assert data["status"] == "pending"

    @pytest.mark.anyio
    async def test_create_site_closeout_updates_total(self, client: AsyncClient):
        # Get initial total
        resp1 = await client.get(f"{API_PREFIX}/closeouts/SCO-001")
        initial_total = resp1.json()["total_sites"]

        payload = _make_site_closeout_create()
        await client.post(
            f"{API_PREFIX}/closeouts/SCO-001/site-closeouts", json=payload
        )

        resp2 = await client.get(f"{API_PREFIX}/closeouts/SCO-001")
        assert resp2.json()["total_sites"] == initial_total + 1

    @pytest.mark.anyio
    async def test_get_site_closeout(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-closeouts/SCSITE-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SCSITE-001"
        assert data["status"] == "closed"

    @pytest.mark.anyio
    async def test_get_site_closeout_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-closeouts/SCSITE-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_site_closeout(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/site-closeouts/SCSITE-004",
            json={"notes": "Updated notes for Mayo Clinic"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated notes for Mayo Clinic"

    @pytest.mark.anyio
    async def test_update_site_closeout_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/site-closeouts/SCSITE-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404


# =====================================================================
# SITE CLOSEOUT WORKFLOW
# =====================================================================


class TestSiteCloseoutWorkflow:
    """Test site closeout workflow: schedule -> visit -> documents -> IP -> close."""

    @pytest.mark.anyio
    async def test_schedule_visit(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = {
            "scheduled_visit_date": (now + timedelta(days=10)).isoformat(),
            "monitor": "New Monitor",
        }
        resp = await client.post(
            f"{API_PREFIX}/site-closeouts/SCSITE-006/schedule-visit", json=payload
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "scheduled"
        assert data["monitor"] == "New Monitor"

    @pytest.mark.anyio
    async def test_schedule_visit_already_visited(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = {
            "scheduled_visit_date": (now + timedelta(days=10)).isoformat(),
            "monitor": "Test Monitor",
        }
        resp = await client.post(
            f"{API_PREFIX}/site-closeouts/SCSITE-004/schedule-visit", json=payload
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_schedule_visit_not_found(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = {
            "scheduled_visit_date": (now + timedelta(days=10)).isoformat(),
            "monitor": "Test",
        }
        resp = await client.post(
            f"{API_PREFIX}/site-closeouts/SCSITE-NONEXISTENT/schedule-visit",
            json=payload,
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_complete_site_closure(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = {
            "actual_visit_date": now.isoformat(),
            "notes": "Site closure completed successfully",
        }
        resp = await client.post(
            f"{API_PREFIX}/site-closeouts/SCSITE-004/complete", json=payload
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "closed"
        assert data["ip_reconciled"] is True
        assert data["documents_collected"] is True
        assert data["financial_reconciled"] is True
        assert data["outstanding_queries_count"] == 0

    @pytest.mark.anyio
    async def test_complete_already_closed_site(self, client: AsyncClient):
        payload = {"notes": "Trying to close again"}
        resp = await client.post(
            f"{API_PREFIX}/site-closeouts/SCSITE-001/complete", json=payload
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_complete_site_not_found(self, client: AsyncClient):
        payload = {"notes": "Test"}
        resp = await client.post(
            f"{API_PREFIX}/site-closeouts/SCSITE-NONEXISTENT/complete", json=payload
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_complete_site_updates_parent_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/closeouts/SCO-001")
        initial_closed = resp1.json()["sites_closed"]

        payload = {"notes": "Closing site"}
        await client.post(
            f"{API_PREFIX}/site-closeouts/SCSITE-004/complete", json=payload
        )

        resp2 = await client.get(f"{API_PREFIX}/closeouts/SCO-001")
        assert resp2.json()["sites_closed"] == initial_closed + 1

    @pytest.mark.anyio
    async def test_full_site_workflow(self, client: AsyncClient):
        """Test complete workflow: schedule -> complete."""
        now = datetime.now(timezone.utc)

        # Schedule visit for pending site
        schedule_payload = {
            "scheduled_visit_date": (now + timedelta(days=5)).isoformat(),
            "monitor": "Workflow Monitor",
        }
        resp1 = await client.post(
            f"{API_PREFIX}/site-closeouts/SCSITE-006/schedule-visit",
            json=schedule_payload,
        )
        assert resp1.status_code == 200
        assert resp1.json()["status"] == "scheduled"

        # Complete the site closure
        complete_payload = {
            "actual_visit_date": now.isoformat(),
            "notes": "Full workflow test complete",
        }
        resp2 = await client.post(
            f"{API_PREFIX}/site-closeouts/SCSITE-006/complete",
            json=complete_payload,
        )
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "closed"


# =====================================================================
# CLOSEOUT TASKS
# =====================================================================


class TestCloseoutTasks:
    """Test closeout task management."""

    @pytest.mark.anyio
    async def test_list_tasks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/closeouts/SCO-001/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 14

    @pytest.mark.anyio
    async def test_list_tasks_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/closeouts/SCO-001/tasks",
            params={"status": "completed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_list_tasks_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/closeouts/SCO-001/tasks",
            params={"task_type": "ip_reconciliation"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["task_type"] == "ip_reconciliation"

    @pytest.mark.anyio
    async def test_list_tasks_nonexistent_closeout(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/closeouts/SCO-NONEXISTENT/tasks")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_task(self, client: AsyncClient):
        payload = _make_task_create()
        resp = await client.post(
            f"{API_PREFIX}/closeouts/SCO-001/tasks", json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["description"] == "Test closeout task"
        assert data["status"] == "not_started"
        assert data["id"].startswith("SCT-")

    @pytest.mark.anyio
    async def test_create_task_with_dependencies(self, client: AsyncClient):
        payload = _make_task_create(dependencies=["SCT-001", "SCT-002"])
        resp = await client.post(
            f"{API_PREFIX}/closeouts/SCO-001/tasks", json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["dependencies"] == ["SCT-001", "SCT-002"]

    @pytest.mark.anyio
    async def test_get_task(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks/SCT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SCT-001"
        assert data["status"] == "completed"

    @pytest.mark.anyio
    async def test_get_task_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks/SCT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_task_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/tasks/SCT-009",
            json={"status": "in_progress"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"

    @pytest.mark.anyio
    async def test_update_task_complete_auto_date(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/tasks/SCT-009",
            json={"status": "completed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["completed_date"] is not None

    @pytest.mark.anyio
    async def test_update_task_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/tasks/SCT-NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_task_blockers(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/tasks/SCT-008",
            json={
                "status": "blocked",
                "blockers": ["Missing shipment records"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "blocked"
        assert "Missing shipment records" in data["blockers"]

    @pytest.mark.anyio
    async def test_task_sorted_by_due_date(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/closeouts/SCO-001/tasks")
        data = resp.json()
        dates = [item["due_date"] for item in data["items"]]
        assert dates == sorted(dates)


# =====================================================================
# DOCUMENT ARCHIVES
# =====================================================================


class TestDocumentArchives:
    """Test document archiving."""

    @pytest.mark.anyio
    async def test_list_archives(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/closeouts/SCO-001/archives")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_archives_nonexistent_closeout(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/closeouts/SCO-NONEXISTENT/archives")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_archive(self, client: AsyncClient):
        payload = {
            "archive_type": "electronic",
            "archive_location": "S3://test-bucket/archive/",
            "total_documents": 500,
            "retention_period_years": 20,
        }
        resp = await client.post(
            f"{API_PREFIX}/closeouts/SCO-001/archives", json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["archive_type"] == "electronic"
        assert data["total_documents"] == 500
        assert data["archived_documents"] == 0
        assert data["id"].startswith("ARCH-")

    @pytest.mark.anyio
    async def test_create_archive_nonexistent_closeout(self, client: AsyncClient):
        payload = {
            "archive_type": "paper",
            "archive_location": "Warehouse",
            "total_documents": 100,
        }
        resp = await client.post(
            f"{API_PREFIX}/closeouts/SCO-NONEXISTENT/archives", json=payload
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_archive(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/archives/ARCH-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ARCH-001"
        assert data["archive_type"] == "electronic"

    @pytest.mark.anyio
    async def test_get_archive_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/archives/ARCH-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_archive_paper_verified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/archives/ARCH-002")
        assert resp.status_code == 200
        data = resp.json()
        assert data["archive_type"] == "paper"
        assert data["verified_by"] is not None
        assert data["verification_date"] is not None
        assert data["archived_documents"] == data["total_documents"]


# =====================================================================
# REGULATORY NOTIFICATIONS
# =====================================================================


class TestRegulatoryNotifications:
    """Test regulatory notifications."""

    @pytest.mark.anyio
    async def test_list_notifications(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/closeouts/SCO-001/regulatory-notifications"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_list_notifications_nonexistent_closeout(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/closeouts/SCO-NONEXISTENT/regulatory-notifications"
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_send_notification(self, client: AsyncClient):
        payload = {
            "authority_name": "TGA",
            "country": "Australia",
            "notification_type": "end_of_study",
            "sent_by": "Maria Garcia",
        }
        resp = await client.post(
            f"{API_PREFIX}/closeouts/SCO-001/regulatory-notifications", json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["authority_name"] == "TGA"
        assert data["country"] == "Australia"
        assert data["sent_date"] is not None
        assert data["acknowledgment_received"] is False

    @pytest.mark.anyio
    async def test_send_notification_updates_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/closeouts/SCO-001")
        initial_count = resp1.json()["regulatory_notifications_sent"]

        payload = {
            "authority_name": "ANVISA",
            "country": "Brazil",
            "notification_type": "end_of_study",
        }
        await client.post(
            f"{API_PREFIX}/closeouts/SCO-001/regulatory-notifications", json=payload
        )

        resp2 = await client.get(f"{API_PREFIX}/closeouts/SCO-001")
        assert resp2.json()["regulatory_notifications_sent"] == initial_count + 1

    @pytest.mark.anyio
    async def test_send_notification_nonexistent_closeout(self, client: AsyncClient):
        payload = {
            "authority_name": "Test",
            "country": "Test",
            "notification_type": "end_of_study",
        }
        resp = await client.post(
            f"{API_PREFIX}/closeouts/SCO-NONEXISTENT/regulatory-notifications",
            json=payload,
        )
        assert resp.status_code == 404

    def test_seed_notification_acknowledgments(self, svc: StudyCloseoutService):
        notifs = svc.list_regulatory_notifications("SCO-001")
        ack_count = sum(1 for n in notifs if n.acknowledgment_received)
        assert ack_count == 2  # FDA and EMA acknowledged


# =====================================================================
# FINANCIAL RECONCILIATION
# =====================================================================


class TestFinancialReconciliation:
    """Test financial reconciliation operations."""

    @pytest.mark.anyio
    async def test_list_reconciliations(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/closeouts/SCO-001/financial-reconciliations"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4

    @pytest.mark.anyio
    async def test_list_reconciliations_nonexistent_closeout(
        self, client: AsyncClient
    ):
        resp = await client.get(
            f"{API_PREFIX}/closeouts/SCO-NONEXISTENT/financial-reconciliations"
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_reconciliation(self, client: AsyncClient):
        payload = {
            "site_id": "SITE-105",
            "total_paid": 150000.00,
            "total_owed": 180000.00,
            "holdback_amount": 12000.00,
        }
        resp = await client.post(
            f"{API_PREFIX}/closeouts/SCO-001/financial-reconciliations", json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_id"] == "SITE-105"
        assert data["outstanding_amount"] == 30000.00
        assert data["status"] == "pending"

    @pytest.mark.anyio
    async def test_get_reconciliation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/financial-reconciliations/FINREC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "FINREC-001"
        assert data["status"] == "reconciled"

    @pytest.mark.anyio
    async def test_get_reconciliation_not_found(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/financial-reconciliations/FINREC-NONEXISTENT"
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_reconciliation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/financial-reconciliations/FINREC-004",
            json={"total_paid": 210000.00, "status": "in_progress"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_paid"] == 210000.00
        assert data["outstanding_amount"] == 30000.00  # 240000 - 210000
        assert data["status"] == "in_progress"

    @pytest.mark.anyio
    async def test_update_reconciliation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/financial-reconciliations/FINREC-NONEXISTENT",
            json={"total_paid": 100.00},
        )
        assert resp.status_code == 404

    def test_reconcile_finances(self, svc: StudyCloseoutService):
        result = svc.reconcile_finances("FINREC-003", "Robert Kim")
        assert result is not None
        assert result.status == FinancialReconciliationStatus.RECONCILED
        assert result.reconciled_by == "Robert Kim"
        assert result.reconciliation_date is not None
        assert result.holdback_released is True

    def test_reconcile_already_reconciled(self, svc: StudyCloseoutService):
        with pytest.raises(ValueError, match="already reconciled"):
            svc.reconcile_finances("FINREC-001", "Someone")

    def test_reconcile_not_found(self, svc: StudyCloseoutService):
        result = svc.reconcile_finances("FINREC-NONEXISTENT", "Someone")
        assert result is None

    def test_seed_reconciled_sites(self, svc: StudyCloseoutService):
        recs = svc.list_financial_reconciliations("SCO-001")
        reconciled = [
            r for r in recs if r.status == FinancialReconciliationStatus.RECONCILED
        ]
        assert len(reconciled) == 2


# =====================================================================
# PROGRESS TRACKING
# =====================================================================


class TestProgressTracking:
    """Test progress tracking."""

    @pytest.mark.anyio
    async def test_get_progress(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/closeouts/SCO-001/progress")
        assert resp.status_code == 200
        data = resp.json()
        assert data["closeout_id"] == "SCO-001"
        assert data["overall_status"] == "in_progress"
        assert data["total_sites"] == 6
        assert data["sites_closed"] == 2
        assert data["database_locked"] is True

    @pytest.mark.anyio
    async def test_progress_task_counts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/closeouts/SCO-001/progress")
        data = resp.json()
        assert data["total_tasks"] == 14
        assert data["tasks_completed"] > 0
        assert data["tasks_in_progress"] > 0

    @pytest.mark.anyio
    async def test_progress_completion_percentage(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/closeouts/SCO-001/progress")
        data = resp.json()
        assert 0 <= data["completion_percentage"] <= 100

    @pytest.mark.anyio
    async def test_progress_regulatory_counts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/closeouts/SCO-001/progress")
        data = resp.json()
        assert data["regulatory_notifications_sent"] == 3
        assert data["regulatory_notifications_acknowledged"] == 2

    @pytest.mark.anyio
    async def test_progress_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/closeouts/SCO-NONEXISTENT/progress")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_progress_pending_sites_count(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/closeouts/SCO-001/progress")
        data = resp.json()
        # 6 total - 2 closed - pending
        assert data["sites_pending"] >= 1
        assert data["sites_in_progress"] >= 0
        total = data["sites_closed"] + data["sites_in_progress"] + data["sites_pending"]
        assert total == data["total_sites"]

    @pytest.mark.anyio
    async def test_progress_overdue_tasks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/closeouts/SCO-001/progress")
        data = resp.json()
        assert data["tasks_overdue"] >= 1  # SCT-014 is overdue


# =====================================================================
# METRICS
# =====================================================================


class TestCloseoutMetrics:
    """Test closeout metrics aggregation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active_closeouts"] == 2
        assert data["sites_pending_closure"] > 0
        assert data["documents_archived"] > 0
        assert data["financial_reconciliations_pending"] > 0

    def test_metrics_active_closeouts(self, svc: StudyCloseoutService):
        metrics = svc.get_metrics()
        assert metrics.active_closeouts == 2  # in_progress + planning

    def test_metrics_sites_pending(self, svc: StudyCloseoutService):
        metrics = svc.get_metrics()
        # All sites from SCO-002 (4 pending) + non-closed from SCO-001 (4)
        assert metrics.sites_pending_closure >= 8

    def test_metrics_overdue_tasks(self, svc: StudyCloseoutService):
        metrics = svc.get_metrics()
        assert metrics.overdue_tasks >= 1  # SCT-014 is overdue

    def test_metrics_documents_archived(self, svc: StudyCloseoutService):
        metrics = svc.get_metrics()
        # 1820 + 420 + 90 = 2330
        assert metrics.documents_archived == 2330

    def test_metrics_financial_pending(self, svc: StudyCloseoutService):
        metrics = svc.get_metrics()
        assert metrics.financial_reconciliations_pending == 2  # FINREC-003 and FINREC-004

    def test_metrics_avg_days(self, svc: StudyCloseoutService):
        metrics = svc.get_metrics()
        assert metrics.avg_days_to_close >= 0


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_study_closeout_service()
        svc2 = get_study_closeout_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_study_closeout_service()
        svc2 = reset_study_closeout_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_study_closeout_service()
        # Delete a closeout
        with svc._lock:
            del svc._closeouts["SCO-001"]
        assert svc.get_closeout("SCO-001") is None
        # Reset should bring it back
        svc2 = reset_study_closeout_service()
        assert svc2.get_closeout("SCO-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_closeouts_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/closeouts")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_site_closeouts_no_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/closeouts/SCO-001/site-closeouts")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_closeout_minimal(self, client: AsyncClient):
        payload = {
            "trial_id": "TRIAL-MIN",
            "trial_name": "Minimal Trial",
            "closeout_lead": "Dr. Minimal",
        }
        resp = await client.post(f"{API_PREFIX}/closeouts", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["total_sites"] == 0
        assert data["planned_start_date"] is None

    @pytest.mark.anyio
    async def test_create_task_site_specific(self, client: AsyncClient):
        payload = _make_task_create(
            site_id="SITE-105",
            task_type="sample_disposition",
            description="Dispose of samples at Duke",
        )
        resp = await client.post(
            f"{API_PREFIX}/closeouts/SCO-001/tasks", json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_id"] == "SITE-105"
        assert data["task_type"] == "sample_disposition"

    @pytest.mark.anyio
    async def test_update_closeout_database_lock(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/closeouts/SCO-002",
            json={
                "database_locked": True,
                "database_lock_date": now.isoformat(),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["database_locked"] is True
        assert data["database_lock_date"] is not None

    @pytest.mark.anyio
    async def test_update_closeout_final_csr(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/closeouts/SCO-001",
            json={
                "final_csr_submitted": True,
                "final_csr_date": now.isoformat(),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["final_csr_submitted"] is True
        assert data["final_csr_date"] is not None

    @pytest.mark.anyio
    async def test_create_archive_hybrid(self, client: AsyncClient):
        payload = {
            "archive_type": "hybrid",
            "archive_location": "Mixed storage - electronic + paper",
            "total_documents": 250,
            "retention_period_years": 30,
        }
        resp = await client.post(
            f"{API_PREFIX}/closeouts/SCO-001/archives", json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["archive_type"] == "hybrid"
        assert data["retention_period_years"] == 30

    @pytest.mark.anyio
    async def test_financial_reconciliation_outstanding_calculation(
        self, client: AsyncClient
    ):
        payload = {
            "site_id": "SITE-106",
            "total_paid": 100000.00,
            "total_owed": 175000.00,
            "holdback_amount": 10000.00,
        }
        resp = await client.post(
            f"{API_PREFIX}/closeouts/SCO-001/financial-reconciliations", json=payload
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["outstanding_amount"] == 75000.00

    @pytest.mark.anyio
    async def test_update_financial_recalculates_outstanding(
        self, client: AsyncClient
    ):
        resp = await client.put(
            f"{API_PREFIX}/financial-reconciliations/FINREC-004",
            json={"total_paid": 230000.00},
        )
        assert resp.status_code == 200
        data = resp.json()
        # total_owed = 240000, total_paid = 230000
        assert data["outstanding_amount"] == 10000.00

    @pytest.mark.anyio
    async def test_closeout_created_at_populated(self, client: AsyncClient):
        payload = _make_closeout_create()
        resp = await client.post(f"{API_PREFIX}/closeouts", json=payload)
        data = resp.json()
        assert data["created_at"] is not None
        assert data["updated_at"] is not None

    def test_task_waived_status(self, svc: StudyCloseoutService):
        from app.schemas.study_closeout import CloseoutTaskUpdate

        result = svc.update_task("SCT-009", CloseoutTaskUpdate(status=TaskStatus.WAIVED))
        assert result is not None
        assert result.status == TaskStatus.WAIVED

    def test_task_na_status(self, svc: StudyCloseoutService):
        from app.schemas.study_closeout import CloseoutTaskUpdate

        result = svc.update_task("SCT-009", CloseoutTaskUpdate(status=TaskStatus.NA))
        assert result is not None
        assert result.status == TaskStatus.NA

    def test_site_closeout_ip_reconciliation_date(self, svc: StudyCloseoutService):
        sc = svc.get_site_closeout("SCSITE-003")
        assert sc is not None
        assert sc.ip_reconciled is True
        assert sc.ip_reconciliation_date is not None

    @pytest.mark.anyio
    async def test_schedule_reschedule_visit(self, client: AsyncClient):
        """Test rescheduling a visit that is already scheduled."""
        now = datetime.now(timezone.utc)
        # SCSITE-005 is already scheduled
        new_date = (now + timedelta(days=14)).isoformat()
        payload = {
            "scheduled_visit_date": new_date,
            "monitor": "Rescheduled Monitor",
        }
        resp = await client.post(
            f"{API_PREFIX}/site-closeouts/SCSITE-005/schedule-visit", json=payload
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["monitor"] == "Rescheduled Monitor"
        assert data["status"] == "scheduled"
