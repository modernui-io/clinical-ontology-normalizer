"""Tests for Data Review & Lock (CLINICAL-DL).

Covers:
- Seed data verification (locks, data cuts, clean data records, unblinding, checklists)
- Lock CRUD (create, read, update, delete, list, filter by trial/status/type)
- Lock lifecycle (plan -> start -> soft lock -> unlock, plan -> start -> hard lock)
- Lock lifecycle errors (invalid transitions, locked update, locked delete)
- Pre-lock validation checks
- Data cut CRUD (create, read, delete, list, filter by lock)
- Clean data workflow (create, update, flag, mark clean, summary)
- Unblinding procedures (request, approve, execute, audit trail)
- Unblinding error handling (double approve, execute without approval, double execute)
- Lock checklists (create, update item, completion stats)
- Checklist item auto-completion date
- Metrics computation
- Service singleton pattern
- Edge cases and error handling (404s, 400s, invalid operations)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.data_lock import router as data_lock_router
from app.schemas.data_lock import (
    ChecklistItemStatus,
    CleanDataRecordCreate,
    CleanDataRecordUpdate,
    CleanDataStatus,
    DataCutCreate,
    DataCutType,
    DataLockCreate,
    DataLockUpdate,
    LockChecklistCreate,
    LockChecklistItemCreate,
    LockChecklistItemUpdate,
    LockExecute,
    LockStatus,
    LockType,
    LockUnlock,
    PreLockSummary,
    UnblindingApproval,
    UnblindingExecute,
    UnblindingRequestCreate,
    UnblindingType,
)
from app.services.data_lock_service import (
    DataLockService,
    get_data_lock_service,
    reset_data_lock_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/data-locks"

# Standalone test app with the data-locks router
_test_app = FastAPI()
_test_app.include_router(data_lock_router)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_data_lock_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> DataLockService:
    """Shorthand for the fresh service."""
    return fresh_service


@pytest.fixture
async def client():
    """Async HTTP client for API tests."""
    transport = ASGITransport(app=_test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_lock_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "lock_type": "soft_lock",
        "description": "Test lock for unit testing",
        "planned_date": (now + timedelta(days=7)).isoformat(),
        "sites_included": ["SITE-101"],
    }
    defaults.update(overrides)
    return defaults


def _make_lock_execute(**overrides) -> dict:
    defaults = {
        "locked_by": "Test User, Data Manager",
        "subjects_locked": 100,
        "forms_locked": 2000,
    }
    defaults.update(overrides)
    return defaults


def _make_data_cut_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "cut_type": "interim_analysis",
        "cutoff_date": now.isoformat(),
        "subjects_included": 150,
        "forms_included": 3000,
        "description": "Test data cut",
    }
    defaults.update(overrides)
    return defaults


def _make_unblinding_create(**overrides) -> dict:
    defaults = {
        "unblinding_type": "partial",
        "justification": "DSMB requested partial unblinding for safety review",
        "requestor": "Dr. Test, DSMB Chair",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_locks_count(self, svc: DataLockService):
        locks = svc.list_locks()
        assert len(locks) == 8

    def test_seed_locks_statuses(self, svc: DataLockService):
        locks = svc.list_locks()
        statuses = {lk.status for lk in locks}
        assert LockStatus.PLANNED in statuses
        assert LockStatus.IN_PROGRESS in statuses
        assert LockStatus.LOCKED in statuses
        assert LockStatus.UNLOCKED in statuses
        assert LockStatus.CANCELLED in statuses

    def test_seed_locks_types(self, svc: DataLockService):
        locks = svc.list_locks()
        types = {lk.lock_type for lk in locks}
        assert LockType.SOFT_LOCK in types
        assert LockType.HARD_LOCK in types
        assert LockType.INTERIM_LOCK in types
        assert LockType.FINAL_LOCK in types

    def test_seed_data_cuts_count(self, svc: DataLockService):
        cuts = svc.list_data_cuts()
        assert len(cuts) == 5

    def test_seed_clean_data_records_count(self, svc: DataLockService):
        records = svc.list_clean_data_records()
        assert len(records) == 12

    def test_seed_clean_data_statuses(self, svc: DataLockService):
        records = svc.list_clean_data_records()
        statuses = {r.status for r in records}
        assert CleanDataStatus.CLEAN in statuses
        assert CleanDataStatus.FLAGGED in statuses
        assert CleanDataStatus.IN_PROGRESS in statuses
        assert CleanDataStatus.NOT_STARTED in statuses

    def test_seed_unblinding_requests_count(self, svc: DataLockService):
        reqs = svc.list_unblinding_requests()
        assert len(reqs) == 3

    def test_seed_unblinding_types(self, svc: DataLockService):
        reqs = svc.list_unblinding_requests()
        types = {r.unblinding_type for r in reqs}
        assert UnblindingType.PARTIAL in types
        assert UnblindingType.EMERGENCY in types

    def test_seed_checklists_count(self, svc: DataLockService):
        checklists = svc.list_checklists()
        assert len(checklists) == 2

    def test_seed_checklist_items(self, svc: DataLockService):
        ck = svc.get_checklist("CKL-001")
        assert ck is not None
        assert len(ck.items) == 7

    def test_seed_locked_lock_has_audit_trail(self, svc: DataLockService):
        lock = svc.get_lock("LOCK-001")
        assert lock is not None
        assert len(lock.audit_trail) >= 2

    def test_seed_unlocked_lock_has_reason(self, svc: DataLockService):
        lock = svc.get_lock("LOCK-005")
        assert lock is not None
        assert lock.status == LockStatus.UNLOCKED
        assert lock.unlocked_by is not None
        assert lock.unlock_reason is not None


# =====================================================================
# LOCK CRUD
# =====================================================================


class TestLockCrud:
    """Test lock create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_locks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/locks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8
        assert len(data["items"]) == 8

    @pytest.mark.anyio
    async def test_list_locks_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/locks", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_locks_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/locks", params={"status": "locked"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "locked"

    @pytest.mark.anyio
    async def test_list_locks_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/locks", params={"lock_type": "soft_lock"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["lock_type"] == "soft_lock"

    @pytest.mark.anyio
    async def test_get_lock(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/locks/LOCK-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "LOCK-001"
        assert data["status"] == "locked"
        assert data["lock_type"] == "soft_lock"

    @pytest.mark.anyio
    async def test_get_lock_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/locks/LOCK-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_lock(self, client: AsyncClient):
        payload = _make_lock_create()
        resp = await client.post(f"{API_PREFIX}/locks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["status"] == "planned"
        assert data["lock_type"] == "soft_lock"
        assert data["id"].startswith("LOCK-")
        assert len(data["audit_trail"]) == 1

    @pytest.mark.anyio
    async def test_update_lock_planned(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/locks/LOCK-004",
            json={"description": "Updated final lock description"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == "Updated final lock description"

    @pytest.mark.anyio
    async def test_update_lock_locked_fails(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/locks/LOCK-001",
            json={"description": "Should fail"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_lock_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/locks/LOCK-NONEXISTENT",
            json={"description": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_lock_planned(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/locks/LOCK-007")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/locks/LOCK-007")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_lock_cancelled(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/locks/LOCK-008")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_lock_locked_fails(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/locks/LOCK-001")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_delete_lock_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/locks/LOCK-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# LOCK LIFECYCLE
# =====================================================================


class TestLockLifecycle:
    """Test lock lifecycle transitions."""

    @pytest.mark.anyio
    async def test_start_lock_process(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/locks/LOCK-004/start")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert len(data["audit_trail"]) >= 2

    @pytest.mark.anyio
    async def test_start_lock_not_planned_fails(self, client: AsyncClient):
        # LOCK-003 is already in_progress
        resp = await client.post(f"{API_PREFIX}/locks/LOCK-003/start")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_start_lock_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/locks/LOCK-NONEXISTENT/start")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_execute_soft_lock(self, client: AsyncClient):
        # LOCK-003 is in_progress and interim_lock type
        payload = _make_lock_execute()
        resp = await client.post(f"{API_PREFIX}/locks/LOCK-003/soft-lock", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "locked"
        assert data["locked_by"] == "Test User, Data Manager"
        assert data["subjects_locked"] == 100
        assert data["forms_locked"] == 2000
        assert data["executed_date"] is not None

    @pytest.mark.anyio
    async def test_execute_soft_lock_wrong_status_fails(self, client: AsyncClient):
        payload = _make_lock_execute()
        resp = await client.post(f"{API_PREFIX}/locks/LOCK-004/soft-lock", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_execute_soft_lock_not_found(self, client: AsyncClient):
        payload = _make_lock_execute()
        resp = await client.post(f"{API_PREFIX}/locks/LOCK-NONEXISTENT/soft-lock", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_execute_hard_lock(self, client: AsyncClient):
        # First start LOCK-004 (final_lock, planned)
        resp1 = await client.post(f"{API_PREFIX}/locks/LOCK-004/start")
        assert resp1.status_code == 200
        # Then execute hard lock
        payload = _make_lock_execute()
        resp2 = await client.post(f"{API_PREFIX}/locks/LOCK-004/hard-lock", json=payload)
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["status"] == "locked"
        assert data["locked_by"] == "Test User, Data Manager"

    @pytest.mark.anyio
    async def test_execute_hard_lock_wrong_type_fails(self, client: AsyncClient):
        # LOCK-003 is interim_lock (should use soft-lock instead)
        payload = _make_lock_execute()
        resp = await client.post(f"{API_PREFIX}/locks/LOCK-003/hard-lock", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_unlock_database(self, client: AsyncClient):
        payload = {
            "unlocked_by": "Dr. Test, Medical Monitor",
            "unlock_reason": "Data correction required for subject SUBJ-1001",
        }
        resp = await client.post(f"{API_PREFIX}/locks/LOCK-001/unlock", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "unlocked"
        assert data["unlocked_by"] == "Dr. Test, Medical Monitor"
        assert data["unlock_reason"] is not None
        assert data["unlocked_date"] is not None

    @pytest.mark.anyio
    async def test_unlock_not_locked_fails(self, client: AsyncClient):
        payload = {
            "unlocked_by": "Test",
            "unlock_reason": "Test",
        }
        resp = await client.post(f"{API_PREFIX}/locks/LOCK-004/unlock", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_unlock_not_found(self, client: AsyncClient):
        payload = {
            "unlocked_by": "Test",
            "unlock_reason": "Test",
        }
        resp = await client.post(f"{API_PREFIX}/locks/LOCK-NONEXISTENT/unlock", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_cancel_planned_lock(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/locks/LOCK-004/cancel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"

    @pytest.mark.anyio
    async def test_cancel_in_progress_lock(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/locks/LOCK-003/cancel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"

    @pytest.mark.anyio
    async def test_cancel_locked_fails(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/locks/LOCK-001/cancel")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_cancel_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/locks/LOCK-NONEXISTENT/cancel")
        assert resp.status_code == 404

    def test_full_soft_lock_lifecycle(self, svc: DataLockService):
        """Test complete lifecycle: create -> start -> soft lock -> unlock."""
        now = datetime.now(timezone.utc)
        # Create
        lock = svc.create_lock(DataLockCreate(
            trial_id=EYLEA_TRIAL,
            lock_type=LockType.SOFT_LOCK,
            description="Full lifecycle test",
            planned_date=now + timedelta(days=7),
            sites_included=["SITE-101"],
        ))
        assert lock.status == LockStatus.PLANNED

        # Start
        started = svc.start_lock_process(lock.id)
        assert started is not None
        assert started.status == LockStatus.IN_PROGRESS

        # Soft lock
        locked = svc.execute_soft_lock(lock.id, LockExecute(
            locked_by="Test User",
            subjects_locked=50,
            forms_locked=1000,
        ))
        assert locked is not None
        assert locked.status == LockStatus.LOCKED
        assert locked.executed_date is not None

        # Unlock
        unlocked = svc.unlock(lock.id, LockUnlock(
            unlocked_by="Test Admin",
            unlock_reason="Data correction needed",
        ))
        assert unlocked is not None
        assert unlocked.status == LockStatus.UNLOCKED
        assert unlocked.unlocked_date is not None
        assert len(unlocked.audit_trail) == 4

    def test_full_hard_lock_lifecycle(self, svc: DataLockService):
        """Test: create -> start -> hard lock."""
        now = datetime.now(timezone.utc)
        lock = svc.create_lock(DataLockCreate(
            trial_id=DUPIXENT_TRIAL,
            lock_type=LockType.HARD_LOCK,
            description="Hard lock lifecycle test",
            planned_date=now + timedelta(days=14),
        ))
        assert lock.status == LockStatus.PLANNED

        started = svc.start_lock_process(lock.id)
        assert started is not None
        assert started.status == LockStatus.IN_PROGRESS

        locked = svc.execute_hard_lock(lock.id, LockExecute(
            locked_by="Senior DM",
            subjects_locked=200,
            forms_locked=4000,
        ))
        assert locked is not None
        assert locked.status == LockStatus.LOCKED

    def test_cancel_lifecycle(self, svc: DataLockService):
        """Test: create -> start -> cancel."""
        now = datetime.now(timezone.utc)
        lock = svc.create_lock(DataLockCreate(
            trial_id=LIBTAYO_TRIAL,
            lock_type=LockType.INTERIM_LOCK,
            description="Cancel test",
            planned_date=now + timedelta(days=5),
        ))
        started = svc.start_lock_process(lock.id)
        assert started is not None
        cancelled = svc.cancel_lock(lock.id)
        assert cancelled is not None
        assert cancelled.status == LockStatus.CANCELLED


# =====================================================================
# PRE-LOCK VALIDATION
# =====================================================================


class TestPreLockValidation:
    """Test pre-lock validation checks."""

    @pytest.mark.anyio
    async def test_pre_lock_checks_locked(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/locks/LOCK-001/pre-lock-checks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["lock_id"] == "LOCK-001"
        assert data["total_queries_open"] == 0
        assert data["sdv_completion_rate"] == 100.0
        assert data["ready_to_lock"] is True

    @pytest.mark.anyio
    async def test_pre_lock_checks_in_progress(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/locks/LOCK-003/pre-lock-checks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["lock_id"] == "LOCK-003"
        assert data["total_queries_open"] > 0
        assert data["ready_to_lock"] is False

    @pytest.mark.anyio
    async def test_pre_lock_checks_planned(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/locks/LOCK-004/pre-lock-checks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ready_to_lock"] is False
        assert data["total_queries_open"] > 0
        assert data["total_deviations"] > 0

    @pytest.mark.anyio
    async def test_pre_lock_checks_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/locks/LOCK-NONEXISTENT/pre-lock-checks")
        assert resp.status_code == 404

    def test_pre_lock_summary_alias(self, svc: DataLockService):
        summary = svc.get_pre_lock_summary("LOCK-001")
        assert summary is not None
        assert summary.lock_id == "LOCK-001"


# =====================================================================
# DATA CUTS
# =====================================================================


class TestDataCuts:
    """Test data cut CRUD operations."""

    @pytest.mark.anyio
    async def test_list_data_cuts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-cuts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_list_data_cuts_filter_lock(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-cuts", params={"lock_id": "LOCK-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["lock_id"] == "LOCK-001"

    @pytest.mark.anyio
    async def test_get_data_cut(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-cuts/CUT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CUT-001"
        assert data["cut_type"] == "dsmb_review"

    @pytest.mark.anyio
    async def test_get_data_cut_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-cuts/CUT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_data_cut(self, client: AsyncClient):
        payload = _make_data_cut_create()
        resp = await client.post(f"{API_PREFIX}/locks/LOCK-001/data-cuts", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["lock_id"] == "LOCK-001"
        assert data["cut_type"] == "interim_analysis"
        assert data["id"].startswith("CUT-")

    @pytest.mark.anyio
    async def test_create_data_cut_invalid_lock(self, client: AsyncClient):
        payload = _make_data_cut_create()
        resp = await client.post(f"{API_PREFIX}/locks/LOCK-NONEXISTENT/data-cuts", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_delete_data_cut(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/data-cuts/CUT-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/data-cuts/CUT-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_data_cut_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/data-cuts/CUT-NONEXISTENT")
        assert resp.status_code == 404

    def test_data_cut_types_in_seed(self, svc: DataLockService):
        cuts = svc.list_data_cuts()
        types = {c.cut_type for c in cuts}
        assert DataCutType.DSMB_REVIEW in types
        assert DataCutType.INTERIM_ANALYSIS in types
        assert DataCutType.REGULATORY_SUBMISSION in types


# =====================================================================
# CLEAN DATA RECORDS
# =====================================================================


class TestCleanDataRecords:
    """Test clean data record operations."""

    @pytest.mark.anyio
    async def test_list_clean_data_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/clean-data")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_clean_data_filter_lock(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/clean-data", params={"lock_id": "LOCK-003"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        for item in data["items"]:
            assert item["lock_id"] == "LOCK-003"

    @pytest.mark.anyio
    async def test_list_clean_data_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/clean-data", params={"status": "clean"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "clean"

    @pytest.mark.anyio
    async def test_list_clean_data_filter_subject(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/clean-data", params={"subject_id": "SUBJ-1001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["subject_id"] == "SUBJ-1001"

    @pytest.mark.anyio
    async def test_get_clean_data_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/clean-data/CDR-0001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CDR-0001"

    @pytest.mark.anyio
    async def test_get_clean_data_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/clean-data/CDR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_clean_data_record(self, client: AsyncClient):
        payload = {
            "subject_id": "SUBJ-9999",
            "form": "Lab Results",
            "visit": "Week 48",
            "reviewer": "Test Reviewer",
        }
        resp = await client.post(f"{API_PREFIX}/locks/LOCK-003/clean-data", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["subject_id"] == "SUBJ-9999"
        assert data["status"] == "not_started"
        assert data["lock_id"] == "LOCK-003"

    @pytest.mark.anyio
    async def test_create_clean_data_invalid_lock(self, client: AsyncClient):
        payload = {
            "subject_id": "SUBJ-9999",
            "form": "Lab Results",
            "visit": "Week 48",
        }
        resp = await client.post(f"{API_PREFIX}/locks/LOCK-NONEXISTENT/clean-data", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_clean_data_record(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/clean-data/CDR-0009",
            json={"status": "in_progress", "reviewer": "New Reviewer"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["reviewer"] == "New Reviewer"

    @pytest.mark.anyio
    async def test_update_clean_data_to_clean_sets_date(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/clean-data/CDR-0009",
            json={"status": "clean"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "clean"
        assert data["review_date"] is not None

    @pytest.mark.anyio
    async def test_update_clean_data_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/clean-data/CDR-NONEXISTENT",
            json={"status": "clean"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_flag_data_record(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/clean-data/CDR-0001/flag",
            json=["dosing_date", "ae_severity"],
            params={"notes": "Dosing date inconsistency"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "flagged"
        assert "dosing_date" in data["flagged_fields"]
        assert "ae_severity" in data["flagged_fields"]

    @pytest.mark.anyio
    async def test_flag_data_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/clean-data/CDR-NONEXISTENT/flag",
            json=["field1"],
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_mark_data_clean(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/clean-data/CDR-0004/mark-clean",
            params={"reviewer": "Senior Reviewer"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "clean"
        assert data["reviewer"] == "Senior Reviewer"
        assert data["flagged_fields"] == []
        assert data["review_date"] is not None

    @pytest.mark.anyio
    async def test_mark_clean_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/clean-data/CDR-NONEXISTENT/mark-clean",
            params={"reviewer": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_clean_data_summary(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/locks/LOCK-003/clean-data-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert data["total"] == 12
        assert "clean" in data
        assert "flagged" in data
        assert "in_progress" in data
        assert "not_started" in data

    @pytest.mark.anyio
    async def test_clean_data_summary_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/locks/LOCK-NONEXISTENT/clean-data-summary")
        assert resp.status_code == 404

    def test_flag_data_service_method(self, svc: DataLockService):
        result = svc.flag_data("CDR-0001", ["field_a", "field_b"], "Test notes")
        assert result is not None
        assert result.status == CleanDataStatus.FLAGGED
        assert result.flagged_fields == ["field_a", "field_b"]

    def test_mark_clean_service_method(self, svc: DataLockService):
        result = svc.mark_clean("CDR-0004", "Test Reviewer")
        assert result is not None
        assert result.status == CleanDataStatus.CLEAN
        assert result.reviewer == "Test Reviewer"
        assert result.flagged_fields == []


# =====================================================================
# CLEAN DATA WORKFLOW
# =====================================================================


class TestCleanDataWorkflow:
    """Test clean data lifecycle: not_started -> in_progress -> flagged -> clean."""

    def test_clean_data_lifecycle(self, svc: DataLockService):
        # Create record
        record = svc.create_clean_data_record("LOCK-003", CleanDataRecordCreate(
            subject_id="SUBJ-TEST",
            form="Vital Signs",
            visit="Screening",
        ))
        assert record.status == CleanDataStatus.NOT_STARTED

        # Update to in_progress
        updated = svc.update_clean_data_record(record.id, CleanDataRecordUpdate(
            status=CleanDataStatus.IN_PROGRESS,
            reviewer="Test Reviewer",
        ))
        assert updated is not None
        assert updated.status == CleanDataStatus.IN_PROGRESS

        # Flag
        flagged = svc.flag_data(record.id, ["bp_systolic", "bp_diastolic"], "Values out of range")
        assert flagged is not None
        assert flagged.status == CleanDataStatus.FLAGGED
        assert len(flagged.flagged_fields) == 2

        # Mark clean
        cleaned = svc.mark_clean(record.id, "Senior Reviewer")
        assert cleaned is not None
        assert cleaned.status == CleanDataStatus.CLEAN
        assert cleaned.flagged_fields == []
        assert cleaned.review_date is not None


# =====================================================================
# UNBLINDING REQUESTS
# =====================================================================


class TestUnblindingRequests:
    """Test unblinding request operations."""

    @pytest.mark.anyio
    async def test_list_unblinding_requests(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/unblinding-requests")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_unblinding_filter_lock(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/unblinding-requests", params={"lock_id": "LOCK-002"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["lock_id"] == "LOCK-002"

    @pytest.mark.anyio
    async def test_list_unblinding_filter_executed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/unblinding-requests", params={"executed": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["executed"] is True

    @pytest.mark.anyio
    async def test_get_unblinding_request(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/unblinding-requests/UBR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "UBR-001"
        assert data["executed"] is True

    @pytest.mark.anyio
    async def test_get_unblinding_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/unblinding-requests/UBR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_unblinding_request(self, client: AsyncClient):
        payload = _make_unblinding_create()
        resp = await client.post(f"{API_PREFIX}/locks/LOCK-001/unblinding-requests", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["lock_id"] == "LOCK-001"
        assert data["unblinding_type"] == "partial"
        assert data["executed"] is False
        assert data["approver"] is None

    @pytest.mark.anyio
    async def test_create_unblinding_invalid_lock(self, client: AsyncClient):
        payload = _make_unblinding_create()
        resp = await client.post(f"{API_PREFIX}/locks/LOCK-NONEXISTENT/unblinding-requests", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_approve_unblinding(self, client: AsyncClient):
        payload = {"approver": "Dr. Approver, Medical Director"}
        resp = await client.post(f"{API_PREFIX}/unblinding-requests/UBR-003/approve", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["approver"] == "Dr. Approver, Medical Director"
        assert data["approved_date"] is not None

    @pytest.mark.anyio
    async def test_approve_already_approved_fails(self, client: AsyncClient):
        payload = {"approver": "Test"}
        resp = await client.post(f"{API_PREFIX}/unblinding-requests/UBR-001/approve", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_approve_not_found(self, client: AsyncClient):
        payload = {"approver": "Test"}
        resp = await client.post(f"{API_PREFIX}/unblinding-requests/UBR-NONEXISTENT/approve", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_execute_unblinding(self, client: AsyncClient):
        # First approve UBR-003
        await client.post(
            f"{API_PREFIX}/unblinding-requests/UBR-003/approve",
            json={"approver": "Dr. Approver"},
        )
        # Then execute
        payload = {"subjects_unblinded": ["SUBJ-2001", "SUBJ-2002"]}
        resp = await client.post(f"{API_PREFIX}/unblinding-requests/UBR-003/execute", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["executed"] is True
        assert data["executed_date"] is not None
        assert len(data["subjects_unblinded"]) == 2

    @pytest.mark.anyio
    async def test_execute_without_approval_fails(self, client: AsyncClient):
        # Create a new unblinding request (unapproved)
        create_resp = await client.post(
            f"{API_PREFIX}/locks/LOCK-001/unblinding-requests",
            json=_make_unblinding_create(),
        )
        req_id = create_resp.json()["id"]
        payload = {"subjects_unblinded": ["SUBJ-001"]}
        resp = await client.post(f"{API_PREFIX}/unblinding-requests/{req_id}/execute", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_execute_already_executed_fails(self, client: AsyncClient):
        payload = {"subjects_unblinded": ["SUBJ-001"]}
        resp = await client.post(f"{API_PREFIX}/unblinding-requests/UBR-001/execute", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_execute_not_found(self, client: AsyncClient):
        payload = {"subjects_unblinded": ["SUBJ-001"]}
        resp = await client.post(f"{API_PREFIX}/unblinding-requests/UBR-NONEXISTENT/execute", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_unblinding_audit_trail(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/locks/LOCK-002/unblinding-audit")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    @pytest.mark.anyio
    async def test_unblinding_audit_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/locks/LOCK-NONEXISTENT/unblinding-audit")
        assert resp.status_code == 404


# =====================================================================
# UNBLINDING LIFECYCLE
# =====================================================================


class TestUnblindingLifecycle:
    """Test full unblinding lifecycle: request -> approve -> execute."""

    def test_full_unblinding_lifecycle(self, svc: DataLockService):
        # Request
        req = svc.request_unblinding("LOCK-006", UnblindingRequestCreate(
            unblinding_type=UnblindingType.FULL,
            justification="Final analysis requires full unblinding",
            requestor="Dr. Test Requestor",
        ))
        assert req.approver is None
        assert req.executed is False

        # Approve
        approved = svc.approve_unblinding(req.id, UnblindingApproval(
            approver="Dr. Test Approver",
        ))
        assert approved is not None
        assert approved.approved_date is not None

        # Execute
        executed = svc.execute_unblinding(req.id, UnblindingExecute(
            subjects_unblinded=["SUBJ-3001", "SUBJ-3002", "SUBJ-3003"],
        ))
        assert executed is not None
        assert executed.executed is True
        assert len(executed.subjects_unblinded) == 3

    def test_emergency_unblinding(self, svc: DataLockService):
        req = svc.request_unblinding("LOCK-001", UnblindingRequestCreate(
            unblinding_type=UnblindingType.EMERGENCY,
            justification="Suspected serious adverse reaction requiring treatment decision",
            requestor="Dr. Emergency PI",
        ))
        assert req.unblinding_type == UnblindingType.EMERGENCY

        approved = svc.approve_unblinding(req.id, UnblindingApproval(approver="Medical Monitor"))
        assert approved is not None

        executed = svc.execute_unblinding(req.id, UnblindingExecute(
            subjects_unblinded=["SUBJ-EMRG-001"],
        ))
        assert executed is not None
        assert executed.executed is True


# =====================================================================
# LOCK CHECKLISTS
# =====================================================================


class TestLockChecklists:
    """Test lock checklist operations."""

    @pytest.mark.anyio
    async def test_list_checklists(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/checklists")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    @pytest.mark.anyio
    async def test_list_checklists_filter_lock(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/checklists", params={"lock_id": "LOCK-003"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["lock_id"] == "LOCK-003"

    @pytest.mark.anyio
    async def test_get_checklist(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/checklists/CKL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CKL-001"
        assert len(data["items"]) == 7

    @pytest.mark.anyio
    async def test_get_checklist_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/checklists/CKL-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_checklist(self, client: AsyncClient):
        payload = {
            "name": "Test Checklist",
            "items": [
                {"item_description": "Item 1", "responsible": "Person A"},
                {"item_description": "Item 2", "responsible": "Person B"},
            ],
        }
        resp = await client.post(f"{API_PREFIX}/locks/LOCK-003/checklists", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Checklist"
        assert len(data["items"]) == 2
        assert data["items"][0]["status"] == "pending"

    @pytest.mark.anyio
    async def test_create_checklist_no_items(self, client: AsyncClient):
        payload = {"name": "Empty Checklist"}
        resp = await client.post(f"{API_PREFIX}/locks/LOCK-003/checklists", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["items"]) == 0

    @pytest.mark.anyio
    async def test_create_checklist_invalid_lock(self, client: AsyncClient):
        payload = {"name": "Test"}
        resp = await client.post(f"{API_PREFIX}/locks/LOCK-NONEXISTENT/checklists", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_checklist_item(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/checklists/CKL-001/items/CKI-001",
            json={"status": "completed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Find the updated item
        item = next(i for i in data["items"] if i["id"] == "CKI-001")
        assert item["status"] == "completed"
        assert item["completion_date"] is not None

    @pytest.mark.anyio
    async def test_update_checklist_item_responsible(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/checklists/CKL-001/items/CKI-004",
            json={"responsible": "New Person"},
        )
        assert resp.status_code == 200
        data = resp.json()
        item = next(i for i in data["items"] if i["id"] == "CKI-004")
        assert item["responsible"] == "New Person"

    @pytest.mark.anyio
    async def test_update_checklist_item_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/checklists/CKL-001/items/CKI-NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_checklist_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/checklists/CKL-NONEXISTENT/items/CKI-001",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_checklist_completion(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/checklists/CKL-001/completion")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_items"] == 7
        assert data["completed"] == 3
        assert data["in_progress"] == 2
        assert data["pending"] == 2
        assert "completion_pct" in data
        assert 0 <= data["completion_pct"] <= 100

    @pytest.mark.anyio
    async def test_checklist_completion_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/checklists/CKL-NONEXISTENT/completion")
        assert resp.status_code == 404


# =====================================================================
# CHECKLIST LIFECYCLE
# =====================================================================


class TestChecklistLifecycle:
    """Test checklist completion workflow."""

    def test_complete_all_checklist_items(self, svc: DataLockService):
        """Complete all items and verify 100% completion."""
        ck = svc.get_checklist("CKL-002")
        assert ck is not None

        for item in ck.items:
            svc.update_checklist_item("CKL-002", item.id, LockChecklistItemUpdate(
                status=ChecklistItemStatus.COMPLETED,
            ))

        completion = svc.get_checklist_completion("CKL-002")
        assert completion is not None
        assert completion["completed"] == 5
        assert completion["completion_pct"] == 100.0

    def test_checklist_item_auto_completion_date(self, svc: DataLockService):
        """Completing an item should auto-set completion_date."""
        result = svc.update_checklist_item("CKL-002", "CKI-008", LockChecklistItemUpdate(
            status=ChecklistItemStatus.COMPLETED,
        ))
        assert result is not None
        item = next(i for i in result.items if i.id == "CKI-008")
        assert item.completion_date is not None

    def test_checklist_not_applicable_excluded(self, svc: DataLockService):
        """N/A items should be excluded from completion percentage."""
        # Mark one item as N/A
        svc.update_checklist_item("CKL-002", "CKI-012", LockChecklistItemUpdate(
            status=ChecklistItemStatus.NOT_APPLICABLE,
        ))
        # Mark remaining 4 as completed
        for item_id in ["CKI-008", "CKI-009", "CKI-010", "CKI-011"]:
            svc.update_checklist_item("CKL-002", item_id, LockChecklistItemUpdate(
                status=ChecklistItemStatus.COMPLETED,
            ))

        completion = svc.get_checklist_completion("CKL-002")
        assert completion is not None
        assert completion["not_applicable"] == 1
        assert completion["completed"] == 4
        assert completion["completion_pct"] == 100.0


# =====================================================================
# METRICS
# =====================================================================


class TestDataLockMetrics:
    """Test data lock metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_locks"] == 8
        assert data["total_data_cuts"] == 5
        assert data["total_clean_records"] == 12
        assert data["total_unblinding_requests"] == 3
        assert data["avg_lock_duration_days"] >= 0
        assert 0 <= data["clean_data_pct"] <= 100

    def test_metrics_locks_by_status(self, svc: DataLockService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.locks_by_status.values())
        assert total_by_status == metrics.total_locks

    def test_metrics_locks_by_type(self, svc: DataLockService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.locks_by_type.values())
        assert total_by_type == metrics.total_locks

    def test_metrics_clean_data_pct(self, svc: DataLockService):
        metrics = svc.get_metrics()
        # 7 out of 12 records are clean
        assert metrics.clean_data_pct > 0

    def test_metrics_pending_unblinding(self, svc: DataLockService):
        metrics = svc.get_metrics()
        # UBR-003 is pending (not approved, not executed)
        assert metrics.pending_unblinding_requests == 1

    def test_metrics_avg_lock_duration(self, svc: DataLockService):
        metrics = svc.get_metrics()
        assert metrics.avg_lock_duration_days >= 0


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_data_lock_service()
        svc2 = get_data_lock_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_data_lock_service()
        svc2 = reset_data_lock_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_data_lock_service()
        svc.delete_lock("LOCK-007")
        assert svc.get_lock("LOCK-007") is None
        svc2 = reset_data_lock_service()
        assert svc2.get_lock("LOCK-007") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_locks_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/locks")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_data_cuts_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-cuts")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_clean_data_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/clean-data")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_unblinding_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/unblinding-requests")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_checklists_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/checklists")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_lock_all_types(self, client: AsyncClient):
        for lt in ["soft_lock", "hard_lock", "interim_lock", "final_lock"]:
            payload = _make_lock_create(lock_type=lt)
            resp = await client.post(f"{API_PREFIX}/locks", json=payload)
            assert resp.status_code == 201
            assert resp.json()["lock_type"] == lt

    @pytest.mark.anyio
    async def test_create_data_cut_all_types(self, client: AsyncClient):
        for ct in ["interim_analysis", "final_analysis", "dsmb_review", "regulatory_submission"]:
            payload = _make_data_cut_create(cut_type=ct)
            resp = await client.post(f"{API_PREFIX}/locks/LOCK-001/data-cuts", json=payload)
            assert resp.status_code == 201
            assert resp.json()["cut_type"] == ct

    @pytest.mark.anyio
    async def test_create_unblinding_all_types(self, client: AsyncClient):
        for ut in ["partial", "full", "emergency"]:
            payload = _make_unblinding_create(unblinding_type=ut)
            resp = await client.post(f"{API_PREFIX}/locks/LOCK-001/unblinding-requests", json=payload)
            assert resp.status_code == 201
            assert resp.json()["unblinding_type"] == ut

    @pytest.mark.anyio
    async def test_lock_audit_trail_grows(self, client: AsyncClient):
        # Create lock
        payload = _make_lock_create()
        resp1 = await client.post(f"{API_PREFIX}/locks", json=payload)
        lock_id = resp1.json()["id"]
        assert len(resp1.json()["audit_trail"]) == 1

        # Start
        resp2 = await client.post(f"{API_PREFIX}/locks/{lock_id}/start")
        assert len(resp2.json()["audit_trail"]) == 2

        # Soft lock
        resp3 = await client.post(
            f"{API_PREFIX}/locks/{lock_id}/soft-lock",
            json=_make_lock_execute(),
        )
        assert len(resp3.json()["audit_trail"]) == 3

        # Unlock
        resp4 = await client.post(
            f"{API_PREFIX}/locks/{lock_id}/unlock",
            json={"unlocked_by": "Test", "unlock_reason": "Testing"},
        )
        assert len(resp4.json()["audit_trail"]) == 4

    @pytest.mark.anyio
    async def test_locked_locks_have_subjects_and_forms(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/locks", params={"status": "locked"})
        data = resp.json()
        for item in data["items"]:
            assert item["subjects_locked"] > 0
            assert item["forms_locked"] > 0

    @pytest.mark.anyio
    async def test_planned_locks_have_zero_subjects(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/locks", params={"status": "planned"})
        data = resp.json()
        for item in data["items"]:
            assert item["subjects_locked"] == 0
            assert item["forms_locked"] == 0

    def test_clean_data_summary_empty_lock(self, svc: DataLockService):
        """Summary for a lock with no clean data records."""
        summary = svc.get_clean_data_summary("LOCK-001")
        assert summary["total"] == 0

    def test_clean_data_summary_all_statuses(self, svc: DataLockService):
        summary = svc.get_clean_data_summary("LOCK-003")
        assert "clean" in summary
        assert "flagged" in summary
        assert "in_progress" in summary
        assert "not_started" in summary

    def test_data_cut_sorted_by_cutoff_date(self, svc: DataLockService):
        cuts = svc.list_data_cuts()
        dates = [c.cutoff_date for c in cuts]
        assert dates == sorted(dates, reverse=True)

    def test_locks_sorted_by_created_at(self, svc: DataLockService):
        locks = svc.list_locks()
        dates = [lk.created_at for lk in locks]
        assert dates == sorted(dates, reverse=True)


# =====================================================================
# ENUMERATION VERIFICATION
# =====================================================================


class TestEnumerations:
    """Test enum values are correctly used throughout the system."""

    @pytest.mark.anyio
    async def test_all_lock_statuses_represented(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/locks")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "planned" in statuses
        assert "in_progress" in statuses
        assert "locked" in statuses
        assert "unlocked" in statuses
        assert "cancelled" in statuses

    @pytest.mark.anyio
    async def test_all_lock_types_represented(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/locks")
        data = resp.json()
        types = {item["lock_type"] for item in data["items"]}
        assert "soft_lock" in types
        assert "hard_lock" in types
        assert "interim_lock" in types
        assert "final_lock" in types

    @pytest.mark.anyio
    async def test_all_clean_data_statuses_represented(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/clean-data")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "clean" in statuses
        assert "flagged" in statuses
        assert "in_progress" in statuses
        assert "not_started" in statuses

    @pytest.mark.anyio
    async def test_checklist_item_statuses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/checklists/CKL-001")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "completed" in statuses
        assert "pending" in statuses
        assert "in_progress" in statuses

    @pytest.mark.anyio
    async def test_data_cut_types(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-cuts")
        data = resp.json()
        types = {item["cut_type"] for item in data["items"]}
        assert "dsmb_review" in types
        assert "interim_analysis" in types
        assert "regulatory_submission" in types


# =====================================================================
# LOCK DETAILS
# =====================================================================


class TestLockDetails:
    """Test detailed lock attributes and relationships."""

    @pytest.mark.anyio
    async def test_lock_has_sites_included(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/locks/LOCK-001")
        data = resp.json()
        assert len(data["sites_included"]) > 0
        assert "SITE-101" in data["sites_included"]

    @pytest.mark.anyio
    async def test_lock_has_audit_trail(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/locks/LOCK-002")
        data = resp.json()
        assert len(data["audit_trail"]) >= 2

    @pytest.mark.anyio
    async def test_unlocked_lock_details(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/locks/LOCK-005")
        data = resp.json()
        assert data["status"] == "unlocked"
        assert data["unlocked_by"] is not None
        assert data["unlock_reason"] is not None
        assert data["unlocked_date"] is not None
        assert data["locked_by"] is not None
        assert data["executed_date"] is not None

    @pytest.mark.anyio
    async def test_cancelled_lock_details(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/locks/LOCK-008")
        data = resp.json()
        assert data["status"] == "cancelled"
        assert data["executed_date"] is None
        assert data["locked_by"] is None

    @pytest.mark.anyio
    async def test_data_cut_has_required_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-cuts/CUT-002")
        data = resp.json()
        assert "cutoff_date" in data
        assert "subjects_included" in data
        assert "forms_included" in data
        assert data["subjects_included"] > 0

    @pytest.mark.anyio
    async def test_clean_data_flagged_has_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/clean-data", params={"status": "flagged"})
        data = resp.json()
        for item in data["items"]:
            assert len(item["flagged_fields"]) > 0

    @pytest.mark.anyio
    async def test_executed_unblinding_has_subjects(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/unblinding-requests/UBR-001")
        data = resp.json()
        assert data["executed"] is True
        assert len(data["subjects_unblinded"]) > 0
        assert data["executed_date"] is not None
        assert data["approver"] is not None

    @pytest.mark.anyio
    async def test_pending_unblinding_has_no_subjects(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/unblinding-requests/UBR-003")
        data = resp.json()
        assert data["executed"] is False
        assert len(data["subjects_unblinded"]) == 0
        assert data["approver"] is None
        assert data["executed_date"] is None


# =====================================================================
# CROSS-ENTITY RELATIONSHIPS
# =====================================================================


class TestCrossEntityRelationships:
    """Test relationships between locks, cuts, records, and checklists."""

    def test_data_cuts_reference_valid_locks(self, svc: DataLockService):
        cuts = svc.list_data_cuts()
        for cut in cuts:
            lock = svc.get_lock(cut.lock_id)
            assert lock is not None, f"Data cut {cut.id} references invalid lock {cut.lock_id}"

    def test_clean_data_records_reference_valid_locks(self, svc: DataLockService):
        records = svc.list_clean_data_records()
        for rec in records:
            lock = svc.get_lock(rec.lock_id)
            assert lock is not None, f"CDR {rec.id} references invalid lock {rec.lock_id}"

    def test_unblinding_requests_reference_valid_locks(self, svc: DataLockService):
        reqs = svc.list_unblinding_requests()
        for req in reqs:
            lock = svc.get_lock(req.lock_id)
            assert lock is not None, f"UBR {req.id} references invalid lock {req.lock_id}"

    def test_checklists_reference_valid_locks(self, svc: DataLockService):
        checklists = svc.list_checklists()
        for ck in checklists:
            lock = svc.get_lock(ck.lock_id)
            assert lock is not None, f"Checklist {ck.id} references invalid lock {ck.lock_id}"

    def test_lock_003_has_associated_entities(self, svc: DataLockService):
        """LOCK-003 should have clean data records, a checklist, and an unblinding request."""
        cdrs = svc.list_clean_data_records(lock_id="LOCK-003")
        assert len(cdrs) > 0

        checklists = svc.list_checklists(lock_id="LOCK-003")
        assert len(checklists) == 1

        ubrs = svc.list_unblinding_requests(lock_id="LOCK-003")
        assert len(ubrs) == 1
