"""Data Review & Lock Service (CLINICAL-DL).

Manages database lock lifecycle for clinical trials: data freeze planning,
soft/hard lock execution, clean data workflows, unblinding procedures,
interim analysis locks, data cut management, lock checklists, and pre-lock
validation summaries.

Usage:
    from app.services.data_lock_service import get_data_lock_service

    svc = get_data_lock_service()
    locks = svc.list_locks()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.data_lock import (
    ChecklistItemStatus,
    CleanDataRecord,
    CleanDataRecordCreate,
    CleanDataRecordUpdate,
    CleanDataStatus,
    DataCut,
    DataCutCreate,
    DataCutType,
    DataLock,
    DataLockCreate,
    DataLockMetrics,
    DataLockUpdate,
    LockChecklist,
    LockChecklistCreate,
    LockChecklistItem,
    LockChecklistItemCreate,
    LockChecklistItemUpdate,
    LockExecute,
    LockStatus,
    LockType,
    LockUnlock,
    PreLockSummary,
    UnblindingApproval,
    UnblindingExecute,
    UnblindingRequest,
    UnblindingRequestCreate,
    UnblindingType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class DataLockService:
    """In-memory Data Review & Lock engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._locks: dict[str, DataLock] = {}
        self._data_cuts: dict[str, DataCut] = {}
        self._clean_data_records: dict[str, CleanDataRecord] = {}
        self._unblinding_requests: dict[str, UnblindingRequest] = {}
        self._checklists: dict[str, LockChecklist] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic data lock records across clinical trials."""
        now = datetime.now(timezone.utc)

        # --- 8 Data Locks ---
        locks_data = [
            {
                "id": "LOCK-001",
                "trial_id": EYLEA_TRIAL,
                "lock_type": LockType.SOFT_LOCK,
                "status": LockStatus.LOCKED,
                "description": "Interim soft lock for DSMB review of EYLEA HD Phase 3",
                "planned_date": now - timedelta(days=90),
                "executed_date": now - timedelta(days=88),
                "locked_by": "Maria Chen, Data Manager",
                "subjects_locked": 245,
                "forms_locked": 4890,
                "sites_included": ["SITE-101", "SITE-102", "SITE-103"],
                "audit_trail": [
                    f"{(now - timedelta(days=95)).isoformat()} - Lock planned by Sarah Kim",
                    f"{(now - timedelta(days=90)).isoformat()} - Pre-lock checks initiated",
                    f"{(now - timedelta(days=88)).isoformat()} - Soft lock executed by Maria Chen",
                ],
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "LOCK-002",
                "trial_id": EYLEA_TRIAL,
                "lock_type": LockType.HARD_LOCK,
                "status": LockStatus.LOCKED,
                "description": "Hard lock for EYLEA HD interim analysis submission to FDA",
                "planned_date": now - timedelta(days=60),
                "executed_date": now - timedelta(days=58),
                "locked_by": "Maria Chen, Data Manager",
                "subjects_locked": 245,
                "forms_locked": 4890,
                "sites_included": ["SITE-101", "SITE-102", "SITE-103"],
                "audit_trail": [
                    f"{(now - timedelta(days=65)).isoformat()} - Hard lock planned following soft lock review",
                    f"{(now - timedelta(days=60)).isoformat()} - All clean data flags verified",
                    f"{(now - timedelta(days=58)).isoformat()} - Hard lock executed by Maria Chen",
                ],
                "created_at": now - timedelta(days=65),
            },
            {
                "id": "LOCK-003",
                "trial_id": DUPIXENT_TRIAL,
                "lock_type": LockType.INTERIM_LOCK,
                "status": LockStatus.IN_PROGRESS,
                "description": "Interim lock for DUPIXENT COPD Phase 3 DSMB scheduled review",
                "planned_date": now - timedelta(days=10),
                "executed_date": None,
                "locked_by": None,
                "subjects_locked": 0,
                "forms_locked": 0,
                "sites_included": ["SITE-104", "SITE-105", "SITE-106"],
                "audit_trail": [
                    f"{(now - timedelta(days=15)).isoformat()} - Lock planned by James Wright",
                    f"{(now - timedelta(days=10)).isoformat()} - Lock process initiated, clean data review started",
                ],
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "LOCK-004",
                "trial_id": LIBTAYO_TRIAL,
                "lock_type": LockType.FINAL_LOCK,
                "status": LockStatus.PLANNED,
                "description": "Final database lock for LIBTAYO adjuvant melanoma primary analysis",
                "planned_date": now + timedelta(days=30),
                "executed_date": None,
                "locked_by": None,
                "subjects_locked": 0,
                "forms_locked": 0,
                "sites_included": ["SITE-107", "SITE-108"],
                "audit_trail": [
                    f"{(now - timedelta(days=5)).isoformat()} - Final lock planned by Lisa Park",
                ],
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "LOCK-005",
                "trial_id": DUPIXENT_TRIAL,
                "lock_type": LockType.SOFT_LOCK,
                "status": LockStatus.UNLOCKED,
                "description": "Soft lock for DUPIXENT atopic dermatitis extension study",
                "planned_date": now - timedelta(days=120),
                "executed_date": now - timedelta(days=118),
                "unlocked_date": now - timedelta(days=100),
                "locked_by": "James Wright, Sr. Data Manager",
                "unlocked_by": "Dr. Robert Kim, Medical Monitor",
                "unlock_reason": "Protocol amendment requiring re-analysis of safety endpoint data",
                "subjects_locked": 180,
                "forms_locked": 3240,
                "sites_included": ["SITE-104", "SITE-105"],
                "audit_trail": [
                    f"{(now - timedelta(days=125)).isoformat()} - Lock planned by James Wright",
                    f"{(now - timedelta(days=118)).isoformat()} - Soft lock executed by James Wright",
                    f"{(now - timedelta(days=100)).isoformat()} - Lock removed by Dr. Robert Kim: protocol amendment",
                ],
                "created_at": now - timedelta(days=125),
            },
            {
                "id": "LOCK-006",
                "trial_id": LIBTAYO_TRIAL,
                "lock_type": LockType.INTERIM_LOCK,
                "status": LockStatus.LOCKED,
                "description": "Interim lock for LIBTAYO NSCLC combination therapy DSMB review",
                "planned_date": now - timedelta(days=45),
                "executed_date": now - timedelta(days=43),
                "locked_by": "Lisa Park, Data Manager",
                "subjects_locked": 312,
                "forms_locked": 6864,
                "sites_included": ["SITE-107", "SITE-108", "SITE-101"],
                "audit_trail": [
                    f"{(now - timedelta(days=50)).isoformat()} - Interim lock planned by Lisa Park",
                    f"{(now - timedelta(days=43)).isoformat()} - Lock executed after pre-lock checks passed",
                ],
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "LOCK-007",
                "trial_id": EYLEA_TRIAL,
                "lock_type": LockType.SOFT_LOCK,
                "status": LockStatus.PLANNED,
                "description": "Soft lock for EYLEA DME extension study mid-study analysis",
                "planned_date": now + timedelta(days=14),
                "executed_date": None,
                "locked_by": None,
                "subjects_locked": 0,
                "forms_locked": 0,
                "sites_included": ["SITE-101", "SITE-102"],
                "audit_trail": [
                    f"{(now - timedelta(days=3)).isoformat()} - Lock planned by Maria Chen",
                ],
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "LOCK-008",
                "trial_id": DUPIXENT_TRIAL,
                "lock_type": LockType.HARD_LOCK,
                "status": LockStatus.CANCELLED,
                "description": "Hard lock for DUPIXENT EoE study cancelled due to protocol revision",
                "planned_date": now - timedelta(days=30),
                "executed_date": None,
                "locked_by": None,
                "subjects_locked": 0,
                "forms_locked": 0,
                "sites_included": ["SITE-104", "SITE-106"],
                "audit_trail": [
                    f"{(now - timedelta(days=40)).isoformat()} - Lock planned by James Wright",
                    f"{(now - timedelta(days=28)).isoformat()} - Lock cancelled: protocol revision pending",
                ],
                "created_at": now - timedelta(days=40),
            },
        ]

        for lk in locks_data:
            self._locks[lk["id"]] = DataLock(**lk)

        # --- Data Cuts ---
        cuts_data = [
            {
                "id": "CUT-001",
                "lock_id": "LOCK-001",
                "cut_type": DataCutType.DSMB_REVIEW,
                "cutoff_date": now - timedelta(days=92),
                "subjects_included": 245,
                "forms_included": 4890,
                "description": "Data cut for planned DSMB safety review at 50% enrollment",
                "created_at": now - timedelta(days=92),
            },
            {
                "id": "CUT-002",
                "lock_id": "LOCK-002",
                "cut_type": DataCutType.INTERIM_ANALYSIS,
                "cutoff_date": now - timedelta(days=62),
                "subjects_included": 245,
                "forms_included": 4890,
                "description": "Interim analysis data cut for FDA pre-specified efficacy review",
                "created_at": now - timedelta(days=62),
            },
            {
                "id": "CUT-003",
                "lock_id": "LOCK-003",
                "cut_type": DataCutType.DSMB_REVIEW,
                "cutoff_date": now - timedelta(days=12),
                "subjects_included": 198,
                "forms_included": 3564,
                "description": "Scheduled DSMB safety review for DUPIXENT COPD study",
                "created_at": now - timedelta(days=12),
            },
            {
                "id": "CUT-004",
                "lock_id": "LOCK-006",
                "cut_type": DataCutType.INTERIM_ANALYSIS,
                "cutoff_date": now - timedelta(days=47),
                "subjects_included": 312,
                "forms_included": 6864,
                "description": "Interim efficacy analysis for LIBTAYO NSCLC combination study",
                "created_at": now - timedelta(days=47),
            },
            {
                "id": "CUT-005",
                "lock_id": "LOCK-004",
                "cut_type": DataCutType.REGULATORY_SUBMISSION,
                "cutoff_date": now + timedelta(days=28),
                "subjects_included": 0,
                "forms_included": 0,
                "description": "Planned regulatory submission cut for LIBTAYO adjuvant melanoma BLA",
                "created_at": now - timedelta(days=5),
            },
        ]

        for c in cuts_data:
            self._data_cuts[c["id"]] = DataCut(**c)

        # --- Clean Data Records ---
        subjects = [
            ("SUBJ-1001", "Adverse Events", "Week 24"),
            ("SUBJ-1001", "Vital Signs", "Week 24"),
            ("SUBJ-1002", "Adverse Events", "Week 24"),
            ("SUBJ-1002", "Lab Results", "Week 12"),
            ("SUBJ-1003", "Adverse Events", "Week 24"),
            ("SUBJ-1003", "Concomitant Meds", "Week 24"),
            ("SUBJ-1004", "Adverse Events", "Week 12"),
            ("SUBJ-1004", "Vital Signs", "Week 12"),
            ("SUBJ-1005", "Efficacy Assessment", "Week 24"),
            ("SUBJ-1005", "Lab Results", "Week 24"),
            ("SUBJ-1006", "Adverse Events", "Week 12"),
            ("SUBJ-1006", "Efficacy Assessment", "Week 12"),
        ]

        clean_statuses = [
            CleanDataStatus.CLEAN, CleanDataStatus.CLEAN,
            CleanDataStatus.CLEAN, CleanDataStatus.FLAGGED,
            CleanDataStatus.CLEAN, CleanDataStatus.IN_PROGRESS,
            CleanDataStatus.FLAGGED, CleanDataStatus.CLEAN,
            CleanDataStatus.NOT_STARTED, CleanDataStatus.NOT_STARTED,
            CleanDataStatus.CLEAN, CleanDataStatus.CLEAN,
        ]

        for i, (subj, form, visit) in enumerate(subjects):
            cdr_id = f"CDR-{i + 1:04d}"
            status = clean_statuses[i]
            reviewer = "Anna Brooks, Data Reviewer" if status != CleanDataStatus.NOT_STARTED else None
            review_date = now - timedelta(days=10 - i) if status in (CleanDataStatus.CLEAN, CleanDataStatus.FLAGGED) else None
            flagged = ["ae_onset_date", "ae_severity"] if status == CleanDataStatus.FLAGGED else []
            notes = "Onset date inconsistency with visit date" if status == CleanDataStatus.FLAGGED and form == "Lab Results" else None

            self._clean_data_records[cdr_id] = CleanDataRecord(
                id=cdr_id,
                lock_id="LOCK-003",
                subject_id=subj,
                form=form,
                visit=visit,
                status=status,
                reviewer=reviewer,
                flagged_fields=flagged,
                review_date=review_date,
                notes=notes,
            )

        # --- Unblinding Requests ---
        unblinding_data = [
            {
                "id": "UBR-001",
                "lock_id": "LOCK-002",
                "unblinding_type": UnblindingType.PARTIAL,
                "justification": "DSMB requested partial unblinding for interim efficacy analysis per protocol-specified stopping rules",
                "requestor": "Dr. Elena Rodriguez, DSMB Chair",
                "approver": "Dr. Michael Davis, Sponsor Medical Director",
                "approved_date": now - timedelta(days=55),
                "executed": True,
                "executed_date": now - timedelta(days=53),
                "subjects_unblinded": ["SUBJ-1001", "SUBJ-1002", "SUBJ-1003"],
                "created_at": now - timedelta(days=57),
            },
            {
                "id": "UBR-002",
                "lock_id": "LOCK-006",
                "unblinding_type": UnblindingType.EMERGENCY,
                "justification": "Emergency unblinding for subject SUBJ-2045 with suspected serious adverse drug reaction requiring treatment decision",
                "requestor": "Dr. Sarah Johnson, Site PI at SITE-107",
                "approver": "Dr. Michael Davis, Sponsor Medical Director",
                "approved_date": now - timedelta(days=40),
                "executed": True,
                "executed_date": now - timedelta(days=40),
                "subjects_unblinded": ["SUBJ-2045"],
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "UBR-003",
                "lock_id": "LOCK-003",
                "unblinding_type": UnblindingType.PARTIAL,
                "justification": "DSMB scheduled review requires partial unblinding per charter",
                "requestor": "Dr. Elena Rodriguez, DSMB Chair",
                "approver": None,
                "approved_date": None,
                "executed": False,
                "executed_date": None,
                "subjects_unblinded": [],
                "created_at": now - timedelta(days=8),
            },
        ]

        for u in unblinding_data:
            self._unblinding_requests[u["id"]] = UnblindingRequest(**u)

        # --- Lock Checklists ---
        checklists_data = [
            {
                "id": "CKL-001",
                "lock_id": "LOCK-003",
                "name": "DUPIXENT COPD Interim Lock Checklist",
                "items": [
                    LockChecklistItem(
                        id="CKI-001", item_description="All open queries resolved or documented",
                        responsible="Anna Brooks, Data Reviewer",
                        status=ChecklistItemStatus.IN_PROGRESS, completion_date=None,
                    ),
                    LockChecklistItem(
                        id="CKI-002", item_description="SDV completion rate >= 100% for critical variables",
                        responsible="Jennifer Lee, CRA",
                        status=ChecklistItemStatus.COMPLETED,
                        completion_date=now - timedelta(days=7),
                    ),
                    LockChecklistItem(
                        id="CKI-003", item_description="All SAEs reconciled with safety database",
                        responsible="Dr. Robert Kim, Medical Monitor",
                        status=ChecklistItemStatus.COMPLETED,
                        completion_date=now - timedelta(days=5),
                    ),
                    LockChecklistItem(
                        id="CKI-004", item_description="Protocol deviation log finalized",
                        responsible="James Wright, Sr. Data Manager",
                        status=ChecklistItemStatus.PENDING, completion_date=None,
                    ),
                    LockChecklistItem(
                        id="CKI-005", item_description="Medical coding review completed (MedDRA/WHODrug)",
                        responsible="Anna Brooks, Data Reviewer",
                        status=ChecklistItemStatus.COMPLETED,
                        completion_date=now - timedelta(days=6),
                    ),
                    LockChecklistItem(
                        id="CKI-006", item_description="External data transfers received and reconciled",
                        responsible="Maria Chen, Data Manager",
                        status=ChecklistItemStatus.PENDING, completion_date=None,
                    ),
                    LockChecklistItem(
                        id="CKI-007", item_description="Investigator signature pages collected",
                        responsible="Jennifer Lee, CRA",
                        status=ChecklistItemStatus.IN_PROGRESS, completion_date=None,
                    ),
                ],
                "created_at": now - timedelta(days=14),
            },
            {
                "id": "CKL-002",
                "lock_id": "LOCK-004",
                "name": "LIBTAYO Adjuvant Melanoma Final Lock Checklist",
                "items": [
                    LockChecklistItem(
                        id="CKI-008", item_description="All patient data entered and verified",
                        responsible="Lisa Park, Data Manager",
                        status=ChecklistItemStatus.PENDING, completion_date=None,
                    ),
                    LockChecklistItem(
                        id="CKI-009", item_description="100% SDV for primary endpoint variables",
                        responsible="David Park, Sr. CRA",
                        status=ChecklistItemStatus.PENDING, completion_date=None,
                    ),
                    LockChecklistItem(
                        id="CKI-010", item_description="Biostatistician sign-off on analysis-ready dataset",
                        responsible="Dr. Amy Liu, Biostatistician",
                        status=ChecklistItemStatus.PENDING, completion_date=None,
                    ),
                    LockChecklistItem(
                        id="CKI-011", item_description="All AEs and SAEs coded and reconciled",
                        responsible="Lisa Park, Data Manager",
                        status=ChecklistItemStatus.PENDING, completion_date=None,
                    ),
                    LockChecklistItem(
                        id="CKI-012", item_description="Central lab data transfer complete",
                        responsible="Maria Chen, Data Manager",
                        status=ChecklistItemStatus.PENDING, completion_date=None,
                    ),
                ],
                "created_at": now - timedelta(days=5),
            },
        ]

        for ck in checklists_data:
            self._checklists[ck["id"]] = LockChecklist(**ck)

    # ------------------------------------------------------------------
    # Lock CRUD
    # ------------------------------------------------------------------

    def list_locks(
        self,
        *,
        trial_id: str | None = None,
        status: LockStatus | None = None,
        lock_type: LockType | None = None,
    ) -> list[DataLock]:
        """List data locks with optional filters."""
        with self._lock:
            result = list(self._locks.values())

        if trial_id is not None:
            result = [lk for lk in result if lk.trial_id == trial_id]
        if status is not None:
            result = [lk for lk in result if lk.status == status]
        if lock_type is not None:
            result = [lk for lk in result if lk.lock_type == lock_type]

        return sorted(result, key=lambda lk: lk.created_at, reverse=True)

    def get_lock(self, lock_id: str) -> DataLock | None:
        """Get a single lock by ID."""
        with self._lock:
            return self._locks.get(lock_id)

    def create_lock(self, payload: DataLockCreate) -> DataLock:
        """Create a new database lock."""
        now = datetime.now(timezone.utc)
        lock_id = f"LOCK-{uuid4().hex[:8].upper()}"
        new_lock = DataLock(
            id=lock_id,
            trial_id=payload.trial_id,
            lock_type=payload.lock_type,
            status=LockStatus.PLANNED,
            description=payload.description,
            planned_date=payload.planned_date,
            sites_included=payload.sites_included,
            audit_trail=[f"{now.isoformat()} - Lock planned"],
            created_at=now,
        )
        with self._lock:
            self._locks[lock_id] = new_lock
        logger.info("Created lock %s for trial %s", lock_id, payload.trial_id)
        return new_lock

    def update_lock(self, lock_id: str, payload: DataLockUpdate) -> DataLock | None:
        """Update a lock's metadata."""
        with self._lock:
            existing = self._locks.get(lock_id)
            if existing is None:
                return None
            if existing.status in (LockStatus.LOCKED, LockStatus.CANCELLED):
                raise ValueError(
                    f"Cannot update lock '{lock_id}' in status '{existing.status.value}'"
                )
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DataLock(**data)
            self._locks[lock_id] = updated
        return updated

    def delete_lock(self, lock_id: str) -> bool:
        """Delete a lock. Only planned or cancelled locks can be deleted."""
        with self._lock:
            existing = self._locks.get(lock_id)
            if existing is None:
                return False
            if existing.status not in (LockStatus.PLANNED, LockStatus.CANCELLED):
                raise ValueError(
                    f"Cannot delete lock '{lock_id}' in status '{existing.status.value}'"
                )
            del self._locks[lock_id]
            return True

    # ------------------------------------------------------------------
    # Lock Lifecycle
    # ------------------------------------------------------------------

    def start_lock_process(self, lock_id: str) -> DataLock | None:
        """Transition a planned lock to in_progress."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._locks.get(lock_id)
            if existing is None:
                return None
            if existing.status != LockStatus.PLANNED:
                raise ValueError(
                    f"Can only start lock process from 'planned' status, got '{existing.status.value}'"
                )
            data = existing.model_dump()
            data["status"] = LockStatus.IN_PROGRESS
            data["audit_trail"] = existing.audit_trail + [
                f"{now.isoformat()} - Lock process started"
            ]
            updated = DataLock(**data)
            self._locks[lock_id] = updated
        logger.info("Lock %s transitioned to in_progress", lock_id)
        return updated

    def execute_soft_lock(self, lock_id: str, payload: LockExecute) -> DataLock | None:
        """Execute a soft lock on a database."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._locks.get(lock_id)
            if existing is None:
                return None
            if existing.status != LockStatus.IN_PROGRESS:
                raise ValueError(
                    f"Can only execute soft lock from 'in_progress' status, got '{existing.status.value}'"
                )
            if existing.lock_type not in (LockType.SOFT_LOCK, LockType.INTERIM_LOCK):
                raise ValueError(
                    f"execute_soft_lock requires lock_type soft_lock or interim_lock, got '{existing.lock_type.value}'"
                )
            data = existing.model_dump()
            data["status"] = LockStatus.LOCKED
            data["executed_date"] = now
            data["locked_by"] = payload.locked_by
            data["subjects_locked"] = payload.subjects_locked
            data["forms_locked"] = payload.forms_locked
            data["audit_trail"] = existing.audit_trail + [
                f"{now.isoformat()} - Soft lock executed by {payload.locked_by}"
            ]
            updated = DataLock(**data)
            self._locks[lock_id] = updated
        logger.info("Soft lock executed on %s by %s", lock_id, payload.locked_by)
        return updated

    def execute_hard_lock(self, lock_id: str, payload: LockExecute) -> DataLock | None:
        """Execute a hard lock on a database."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._locks.get(lock_id)
            if existing is None:
                return None
            if existing.status != LockStatus.IN_PROGRESS:
                raise ValueError(
                    f"Can only execute hard lock from 'in_progress' status, got '{existing.status.value}'"
                )
            if existing.lock_type not in (LockType.HARD_LOCK, LockType.FINAL_LOCK):
                raise ValueError(
                    f"execute_hard_lock requires lock_type hard_lock or final_lock, got '{existing.lock_type.value}'"
                )
            data = existing.model_dump()
            data["status"] = LockStatus.LOCKED
            data["executed_date"] = now
            data["locked_by"] = payload.locked_by
            data["subjects_locked"] = payload.subjects_locked
            data["forms_locked"] = payload.forms_locked
            data["audit_trail"] = existing.audit_trail + [
                f"{now.isoformat()} - Hard lock executed by {payload.locked_by}"
            ]
            updated = DataLock(**data)
            self._locks[lock_id] = updated
        logger.info("Hard lock executed on %s by %s", lock_id, payload.locked_by)
        return updated

    def unlock(self, lock_id: str, payload: LockUnlock) -> DataLock | None:
        """Unlock a previously locked database."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._locks.get(lock_id)
            if existing is None:
                return None
            if existing.status != LockStatus.LOCKED:
                raise ValueError(
                    f"Can only unlock from 'locked' status, got '{existing.status.value}'"
                )
            data = existing.model_dump()
            data["status"] = LockStatus.UNLOCKED
            data["unlocked_date"] = now
            data["unlocked_by"] = payload.unlocked_by
            data["unlock_reason"] = payload.unlock_reason
            data["audit_trail"] = existing.audit_trail + [
                f"{now.isoformat()} - Unlocked by {payload.unlocked_by}: {payload.unlock_reason}"
            ]
            updated = DataLock(**data)
            self._locks[lock_id] = updated
        logger.info("Lock %s unlocked by %s", lock_id, payload.unlocked_by)
        return updated

    def cancel_lock(self, lock_id: str) -> DataLock | None:
        """Cancel a planned or in-progress lock."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._locks.get(lock_id)
            if existing is None:
                return None
            if existing.status not in (LockStatus.PLANNED, LockStatus.IN_PROGRESS):
                raise ValueError(
                    f"Can only cancel from 'planned' or 'in_progress' status, got '{existing.status.value}'"
                )
            data = existing.model_dump()
            data["status"] = LockStatus.CANCELLED
            data["audit_trail"] = existing.audit_trail + [
                f"{now.isoformat()} - Lock cancelled"
            ]
            updated = DataLock(**data)
            self._locks[lock_id] = updated
        logger.info("Lock %s cancelled", lock_id)
        return updated

    # ------------------------------------------------------------------
    # Pre-Lock Validation
    # ------------------------------------------------------------------

    def run_pre_lock_checks(self, lock_id: str) -> PreLockSummary | None:
        """Run pre-lock validation checks for a lock."""
        with self._lock:
            existing = self._locks.get(lock_id)
            if existing is None:
                return None

            # Gather clean data records for this lock
            cdrs = [
                cdr for cdr in self._clean_data_records.values()
                if cdr.lock_id == lock_id
            ]

        total_records = len(cdrs)
        clean_count = sum(1 for c in cdrs if c.status == CleanDataStatus.CLEAN)
        flagged_count = sum(1 for c in cdrs if c.status == CleanDataStatus.FLAGGED)

        clean_pct = round(clean_count / max(1, total_records) * 100, 1)

        # Simulate realistic pre-lock metrics based on lock state
        if existing.status == LockStatus.LOCKED:
            open_queries = 0
            deviations = 0
            sdv_rate = 100.0
            outstanding_aes = 0
            pending_sigs = 0
            clean_pct = 100.0  # Already locked => data was validated
        elif existing.status == LockStatus.IN_PROGRESS:
            open_queries = flagged_count * 2 + 3
            deviations = 2
            sdv_rate = 92.5
            outstanding_aes = 1
            pending_sigs = 3
        else:
            open_queries = flagged_count * 3 + 8
            deviations = 5
            sdv_rate = 78.0
            outstanding_aes = 4
            pending_sigs = 7

        ready = (
            open_queries == 0
            and deviations == 0
            and sdv_rate >= 100.0
            and clean_pct >= 95.0
            and outstanding_aes == 0
            and pending_sigs == 0
        )

        return PreLockSummary(
            lock_id=lock_id,
            total_queries_open=open_queries,
            total_deviations=deviations,
            sdv_completion_rate=sdv_rate,
            clean_data_pct=clean_pct,
            outstanding_aes=outstanding_aes,
            pending_signatures=pending_sigs,
            ready_to_lock=ready,
        )

    # ------------------------------------------------------------------
    # Data Cuts
    # ------------------------------------------------------------------

    def list_data_cuts(self, *, lock_id: str | None = None) -> list[DataCut]:
        """List data cuts with optional lock filter."""
        with self._lock:
            result = list(self._data_cuts.values())

        if lock_id is not None:
            result = [c for c in result if c.lock_id == lock_id]

        return sorted(result, key=lambda c: c.cutoff_date, reverse=True)

    def get_data_cut(self, cut_id: str) -> DataCut | None:
        """Get a single data cut by ID."""
        with self._lock:
            return self._data_cuts.get(cut_id)

    def create_data_cut(self, lock_id: str, payload: DataCutCreate) -> DataCut:
        """Create a data cut for a lock."""
        now = datetime.now(timezone.utc)
        with self._lock:
            if lock_id not in self._locks:
                raise ValueError(f"Lock '{lock_id}' not found")

        cut_id = f"CUT-{uuid4().hex[:8].upper()}"
        cut = DataCut(
            id=cut_id,
            lock_id=lock_id,
            cut_type=payload.cut_type,
            cutoff_date=payload.cutoff_date,
            subjects_included=payload.subjects_included,
            forms_included=payload.forms_included,
            description=payload.description,
            created_at=now,
        )
        with self._lock:
            self._data_cuts[cut_id] = cut
        logger.info("Created data cut %s for lock %s", cut_id, lock_id)
        return cut

    def delete_data_cut(self, cut_id: str) -> bool:
        """Delete a data cut."""
        with self._lock:
            if cut_id in self._data_cuts:
                del self._data_cuts[cut_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Clean Data Records
    # ------------------------------------------------------------------

    def list_clean_data_records(
        self,
        *,
        lock_id: str | None = None,
        status: CleanDataStatus | None = None,
        subject_id: str | None = None,
    ) -> list[CleanDataRecord]:
        """List clean data records with optional filters."""
        with self._lock:
            result = list(self._clean_data_records.values())

        if lock_id is not None:
            result = [c for c in result if c.lock_id == lock_id]
        if status is not None:
            result = [c for c in result if c.status == status]
        if subject_id is not None:
            result = [c for c in result if c.subject_id == subject_id]

        return sorted(result, key=lambda c: c.id)

    def get_clean_data_record(self, record_id: str) -> CleanDataRecord | None:
        """Get a single clean data record."""
        with self._lock:
            return self._clean_data_records.get(record_id)

    def create_clean_data_record(self, lock_id: str, payload: CleanDataRecordCreate) -> CleanDataRecord:
        """Create a clean data record for a lock."""
        with self._lock:
            if lock_id not in self._locks:
                raise ValueError(f"Lock '{lock_id}' not found")

        record_id = f"CDR-{uuid4().hex[:8].upper()}"
        record = CleanDataRecord(
            id=record_id,
            lock_id=lock_id,
            subject_id=payload.subject_id,
            form=payload.form,
            visit=payload.visit,
            status=CleanDataStatus.NOT_STARTED,
            reviewer=payload.reviewer,
        )
        with self._lock:
            self._clean_data_records[record_id] = record
        logger.info("Created clean data record %s for lock %s", record_id, lock_id)
        return record

    def update_clean_data_record(
        self, record_id: str, payload: CleanDataRecordUpdate
    ) -> CleanDataRecord | None:
        """Update a clean data record."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._clean_data_records.get(record_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set review_date when marking clean or flagged
            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = CleanDataStatus(new_status)
                if new_status in (CleanDataStatus.CLEAN, CleanDataStatus.FLAGGED):
                    updates["review_date"] = now

            data.update(updates)
            updated = CleanDataRecord(**data)
            self._clean_data_records[record_id] = updated
        return updated

    def flag_data(self, record_id: str, flagged_fields: list[str], notes: str | None = None) -> CleanDataRecord | None:
        """Flag a clean data record with specific fields."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._clean_data_records.get(record_id)
            if existing is None:
                return None
            data = existing.model_dump()
            data["status"] = CleanDataStatus.FLAGGED
            data["flagged_fields"] = flagged_fields
            data["review_date"] = now
            if notes:
                data["notes"] = notes
            updated = CleanDataRecord(**data)
            self._clean_data_records[record_id] = updated
        return updated

    def mark_clean(self, record_id: str, reviewer: str) -> CleanDataRecord | None:
        """Mark a data record as clean."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._clean_data_records.get(record_id)
            if existing is None:
                return None
            data = existing.model_dump()
            data["status"] = CleanDataStatus.CLEAN
            data["reviewer"] = reviewer
            data["review_date"] = now
            data["flagged_fields"] = []
            updated = CleanDataRecord(**data)
            self._clean_data_records[record_id] = updated
        return updated

    def get_clean_data_summary(self, lock_id: str) -> dict[str, int]:
        """Get summary counts of clean data statuses for a lock."""
        with self._lock:
            records = [
                c for c in self._clean_data_records.values()
                if c.lock_id == lock_id
            ]

        summary: dict[str, int] = {s.value: 0 for s in CleanDataStatus}
        for r in records:
            summary[r.status.value] = summary.get(r.status.value, 0) + 1
        summary["total"] = len(records)
        return summary

    # ------------------------------------------------------------------
    # Unblinding
    # ------------------------------------------------------------------

    def list_unblinding_requests(
        self,
        *,
        lock_id: str | None = None,
        executed: bool | None = None,
    ) -> list[UnblindingRequest]:
        """List unblinding requests with optional filters."""
        with self._lock:
            result = list(self._unblinding_requests.values())

        if lock_id is not None:
            result = [u for u in result if u.lock_id == lock_id]
        if executed is not None:
            result = [u for u in result if u.executed == executed]

        return sorted(result, key=lambda u: u.created_at, reverse=True)

    def get_unblinding_request(self, request_id: str) -> UnblindingRequest | None:
        """Get a single unblinding request."""
        with self._lock:
            return self._unblinding_requests.get(request_id)

    def request_unblinding(self, lock_id: str, payload: UnblindingRequestCreate) -> UnblindingRequest:
        """Create a new unblinding request."""
        now = datetime.now(timezone.utc)
        with self._lock:
            if lock_id not in self._locks:
                raise ValueError(f"Lock '{lock_id}' not found")

        req_id = f"UBR-{uuid4().hex[:8].upper()}"
        req = UnblindingRequest(
            id=req_id,
            lock_id=lock_id,
            unblinding_type=payload.unblinding_type,
            justification=payload.justification,
            requestor=payload.requestor,
            created_at=now,
        )
        with self._lock:
            self._unblinding_requests[req_id] = req
        logger.info("Unblinding request %s created for lock %s", req_id, lock_id)
        return req

    def approve_unblinding(self, request_id: str, payload: UnblindingApproval) -> UnblindingRequest | None:
        """Approve an unblinding request."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._unblinding_requests.get(request_id)
            if existing is None:
                return None
            if existing.approved_date is not None:
                raise ValueError(f"Unblinding request '{request_id}' is already approved")
            data = existing.model_dump()
            data["approver"] = payload.approver
            data["approved_date"] = now
            updated = UnblindingRequest(**data)
            self._unblinding_requests[request_id] = updated
        logger.info("Unblinding request %s approved by %s", request_id, payload.approver)
        return updated

    def execute_unblinding(self, request_id: str, payload: UnblindingExecute) -> UnblindingRequest | None:
        """Execute an approved unblinding request."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._unblinding_requests.get(request_id)
            if existing is None:
                return None
            if existing.approved_date is None:
                raise ValueError(f"Unblinding request '{request_id}' has not been approved")
            if existing.executed:
                raise ValueError(f"Unblinding request '{request_id}' has already been executed")
            data = existing.model_dump()
            data["executed"] = True
            data["executed_date"] = now
            data["subjects_unblinded"] = payload.subjects_unblinded
            updated = UnblindingRequest(**data)
            self._unblinding_requests[request_id] = updated
        logger.info(
            "Unblinding executed for %s: %d subjects",
            request_id, len(payload.subjects_unblinded),
        )
        return updated

    def get_unblinding_audit(self, lock_id: str) -> list[UnblindingRequest]:
        """Get unblinding audit trail for a lock (all requests, executed or not)."""
        with self._lock:
            result = [
                u for u in self._unblinding_requests.values()
                if u.lock_id == lock_id
            ]
        return sorted(result, key=lambda u: u.created_at)

    # ------------------------------------------------------------------
    # Lock Checklists
    # ------------------------------------------------------------------

    def list_checklists(self, *, lock_id: str | None = None) -> list[LockChecklist]:
        """List lock checklists with optional lock filter."""
        with self._lock:
            result = list(self._checklists.values())

        if lock_id is not None:
            result = [ck for ck in result if ck.lock_id == lock_id]

        return sorted(result, key=lambda ck: ck.created_at, reverse=True)

    def get_checklist(self, checklist_id: str) -> LockChecklist | None:
        """Get a single checklist by ID."""
        with self._lock:
            return self._checklists.get(checklist_id)

    def create_checklist(self, lock_id: str, payload: LockChecklistCreate) -> LockChecklist:
        """Create a new lock checklist."""
        now = datetime.now(timezone.utc)
        with self._lock:
            if lock_id not in self._locks:
                raise ValueError(f"Lock '{lock_id}' not found")

        checklist_id = f"CKL-{uuid4().hex[:8].upper()}"
        items: list[LockChecklistItem] = []
        if payload.items:
            for item_payload in payload.items:
                item_id = f"CKI-{uuid4().hex[:8].upper()}"
                items.append(LockChecklistItem(
                    id=item_id,
                    item_description=item_payload.item_description,
                    responsible=item_payload.responsible,
                    status=ChecklistItemStatus.PENDING,
                ))

        checklist = LockChecklist(
            id=checklist_id,
            lock_id=lock_id,
            name=payload.name,
            items=items,
            created_at=now,
        )
        with self._lock:
            self._checklists[checklist_id] = checklist
        logger.info("Created checklist %s for lock %s", checklist_id, lock_id)
        return checklist

    def update_checklist_item(
        self,
        checklist_id: str,
        item_id: str,
        payload: LockChecklistItemUpdate,
    ) -> LockChecklist | None:
        """Update a checklist item within a checklist."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._checklists.get(checklist_id)
            if existing is None:
                return None

            found = False
            updated_items: list[LockChecklistItem] = []
            for item in existing.items:
                if item.id == item_id:
                    found = True
                    item_data = item.model_dump()
                    updates = payload.model_dump(exclude_unset=True)
                    # Auto-set completion_date when marking completed
                    if "status" in updates:
                        new_status = updates["status"]
                        if isinstance(new_status, str):
                            new_status = ChecklistItemStatus(new_status)
                        if new_status == ChecklistItemStatus.COMPLETED and item.status != ChecklistItemStatus.COMPLETED:
                            updates["completion_date"] = now
                    item_data.update(updates)
                    updated_items.append(LockChecklistItem(**item_data))
                else:
                    updated_items.append(item)

            if not found:
                raise ValueError(f"Checklist item '{item_id}' not found in checklist '{checklist_id}'")

            data = existing.model_dump()
            data["items"] = [it.model_dump() for it in updated_items]
            updated_ck = LockChecklist(**data)
            self._checklists[checklist_id] = updated_ck
        return updated_ck

    def get_checklist_completion(self, checklist_id: str) -> dict[str, int | float] | None:
        """Get completion stats for a checklist."""
        with self._lock:
            existing = self._checklists.get(checklist_id)
            if existing is None:
                return None

        total = len(existing.items)
        completed = sum(
            1 for i in existing.items if i.status == ChecklistItemStatus.COMPLETED
        )
        na = sum(
            1 for i in existing.items if i.status == ChecklistItemStatus.NOT_APPLICABLE
        )
        applicable = total - na
        completion_pct = round(completed / max(1, applicable) * 100, 1)

        return {
            "total_items": total,
            "completed": completed,
            "in_progress": sum(1 for i in existing.items if i.status == ChecklistItemStatus.IN_PROGRESS),
            "pending": sum(1 for i in existing.items if i.status == ChecklistItemStatus.PENDING),
            "not_applicable": na,
            "completion_pct": completion_pct,
        }

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> DataLockMetrics:
        """Compute aggregated data lock metrics."""
        with self._lock:
            locks = list(self._locks.values())
            cuts = list(self._data_cuts.values())
            cdrs = list(self._clean_data_records.values())
            ubrs = list(self._unblinding_requests.values())

        # Locks by status
        locks_by_status: dict[str, int] = {}
        for lk in locks:
            key = lk.status.value
            locks_by_status[key] = locks_by_status.get(key, 0) + 1

        # Locks by type
        locks_by_type: dict[str, int] = {}
        for lk in locks:
            key = lk.lock_type.value
            locks_by_type[key] = locks_by_type.get(key, 0) + 1

        # Average lock duration
        durations: list[float] = []
        for lk in locks:
            if lk.executed_date and lk.planned_date:
                delta = (lk.executed_date - lk.planned_date).total_seconds() / 86400
                durations.append(abs(delta))
        avg_duration = round(sum(durations) / max(1, len(durations)), 1)

        # Clean data stats
        total_clean = sum(1 for c in cdrs if c.status == CleanDataStatus.CLEAN)
        clean_pct = round(total_clean / max(1, len(cdrs)) * 100, 1)

        # Unblinding stats
        pending_ubr = sum(1 for u in ubrs if not u.executed and u.approved_date is None)

        return DataLockMetrics(
            total_locks=len(locks),
            locks_by_status=locks_by_status,
            locks_by_type=locks_by_type,
            avg_lock_duration_days=avg_duration,
            total_data_cuts=len(cuts),
            total_clean_records=len(cdrs),
            clean_data_pct=clean_pct,
            total_unblinding_requests=len(ubrs),
            pending_unblinding_requests=pending_ubr,
        )

    def get_pre_lock_summary(self, lock_id: str) -> PreLockSummary | None:
        """Alias for run_pre_lock_checks."""
        return self.run_pre_lock_checks(lock_id)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: DataLockService | None = None
_instance_lock = threading.Lock()


def get_data_lock_service() -> DataLockService:
    """Return the singleton DataLockService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = DataLockService()
    return _instance


def reset_data_lock_service() -> DataLockService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = DataLockService()
    return _instance
