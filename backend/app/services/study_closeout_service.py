"""Study Closeout Service.

Manages end-of-study activities including site closure visits, document
archiving, IP reconciliation, database lock confirmation, final reports,
regulatory notifications, and financial reconciliation for clinical trials.

Usage:
    from app.services.study_closeout_service import (
        get_study_closeout_service,
    )

    svc = get_study_closeout_service()
    closeouts = svc.list_closeouts()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.study_closeout import (
    ArchiveType,
    CloseoutMetrics,
    CloseoutProgress,
    CloseoutStatus,
    CloseoutTask,
    CloseoutTaskCreate,
    CloseoutTaskType,
    CloseoutTaskUpdate,
    CompleteSiteClosureRequest,
    DocumentArchive,
    DocumentArchiveCreate,
    FinancialReconciliation,
    FinancialReconciliationCreate,
    FinancialReconciliationStatus,
    FinancialReconciliationUpdate,
    RegulatoryNotification,
    RegulatoryNotificationCreate,
    ScheduleVisitRequest,
    SiteCloseout,
    SiteCloseoutCreate,
    SiteCloseoutStatus,
    SiteCloseoutUpdate,
    StudyCloseout,
    StudyCloseoutCreate,
    StudyCloseoutUpdate,
    TaskStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"


class StudyCloseoutService:
    """In-memory Study Closeout engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._closeouts: dict[str, StudyCloseout] = {}
        self._site_closeouts: dict[str, SiteCloseout] = {}
        self._tasks: dict[str, CloseoutTask] = {}
        self._archives: dict[str, DocumentArchive] = {}
        self._regulatory_notifications: dict[str, RegulatoryNotification] = {}
        self._financial_reconciliations: dict[str, FinancialReconciliation] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic study closeout data."""
        now = datetime.now(timezone.utc)

        # --- Study Closeout for EYLEA trial (in progress) ---
        co1 = StudyCloseout(
            id="SCO-001",
            trial_id=EYLEA_TRIAL,
            trial_name="EYLEA Phase III - Diabetic Macular Edema",
            status=CloseoutStatus.IN_PROGRESS,
            planned_start_date=now - timedelta(days=60),
            actual_start_date=now - timedelta(days=55),
            target_completion_date=now + timedelta(days=90),
            actual_completion_date=None,
            closeout_lead="Dr. Sarah Chen",
            total_sites=6,
            sites_closed=2,
            database_locked=True,
            database_lock_date=now - timedelta(days=30),
            final_csr_submitted=False,
            final_csr_date=None,
            regulatory_notifications_sent=3,
            created_at=now - timedelta(days=60),
            updated_at=now - timedelta(days=1),
        )
        self._closeouts[co1.id] = co1

        # --- Study Closeout for DUPIXENT trial (planning) ---
        co2 = StudyCloseout(
            id="SCO-002",
            trial_id=DUPIXENT_TRIAL,
            trial_name="DUPIXENT Phase III - Atopic Dermatitis",
            status=CloseoutStatus.PLANNING,
            planned_start_date=now + timedelta(days=30),
            actual_start_date=None,
            target_completion_date=now + timedelta(days=180),
            actual_completion_date=None,
            closeout_lead="Dr. Michael Torres",
            total_sites=4,
            sites_closed=0,
            database_locked=False,
            database_lock_date=None,
            final_csr_submitted=False,
            final_csr_date=None,
            regulatory_notifications_sent=0,
            created_at=now - timedelta(days=14),
            updated_at=now - timedelta(days=7),
        )
        self._closeouts[co2.id] = co2

        # --- 6 Site Closeouts for SCO-001 ---
        sites_data = [
            {
                "id": "SCSITE-001",
                "closeout_id": "SCO-001",
                "site_id": "SITE-101",
                "site_name": "Memorial Hermann Hospital",
                "status": SiteCloseoutStatus.CLOSED,
                "scheduled_visit_date": now - timedelta(days=45),
                "actual_visit_date": now - timedelta(days=43),
                "monitor": "Jennifer Lee",
                "ip_reconciled": True,
                "ip_reconciliation_date": now - timedelta(days=40),
                "documents_collected": True,
                "documents_collection_date": now - timedelta(days=38),
                "outstanding_queries_count": 0,
                "outstanding_queries_resolved_date": now - timedelta(days=42),
                "financial_reconciled": True,
                "notes": "Site closed successfully. All activities completed.",
            },
            {
                "id": "SCSITE-002",
                "closeout_id": "SCO-001",
                "site_id": "SITE-102",
                "site_name": "Cleveland Clinic Foundation",
                "status": SiteCloseoutStatus.CLOSED,
                "scheduled_visit_date": now - timedelta(days=35),
                "actual_visit_date": now - timedelta(days=34),
                "monitor": "David Park",
                "ip_reconciled": True,
                "ip_reconciliation_date": now - timedelta(days=30),
                "documents_collected": True,
                "documents_collection_date": now - timedelta(days=28),
                "outstanding_queries_count": 0,
                "outstanding_queries_resolved_date": now - timedelta(days=32),
                "financial_reconciled": True,
                "notes": "Smooth closure. All documents archived.",
            },
            {
                "id": "SCSITE-003",
                "closeout_id": "SCO-001",
                "site_id": "SITE-103",
                "site_name": "Johns Hopkins Research Center",
                "status": SiteCloseoutStatus.IP_RECONCILED,
                "scheduled_visit_date": now - timedelta(days=20),
                "actual_visit_date": now - timedelta(days=18),
                "monitor": "Jennifer Lee",
                "ip_reconciled": True,
                "ip_reconciliation_date": now - timedelta(days=10),
                "documents_collected": False,
                "documents_collection_date": None,
                "outstanding_queries_count": 3,
                "outstanding_queries_resolved_date": None,
                "financial_reconciled": False,
                "notes": "IP reconciled. Awaiting document collection and query resolution.",
            },
            {
                "id": "SCSITE-004",
                "closeout_id": "SCO-001",
                "site_id": "SITE-104",
                "site_name": "Mayo Clinic Jacksonville",
                "status": SiteCloseoutStatus.VISIT_COMPLETED,
                "scheduled_visit_date": now - timedelta(days=14),
                "actual_visit_date": now - timedelta(days=12),
                "monitor": "David Park",
                "ip_reconciled": False,
                "ip_reconciliation_date": None,
                "documents_collected": False,
                "documents_collection_date": None,
                "outstanding_queries_count": 7,
                "outstanding_queries_resolved_date": None,
                "financial_reconciled": False,
                "notes": "Closure visit completed. IP reconciliation in progress.",
            },
            {
                "id": "SCSITE-005",
                "closeout_id": "SCO-001",
                "site_id": "SITE-105",
                "site_name": "Duke Clinical Research Institute",
                "status": SiteCloseoutStatus.SCHEDULED,
                "scheduled_visit_date": now + timedelta(days=7),
                "actual_visit_date": None,
                "monitor": "Jennifer Lee",
                "ip_reconciled": False,
                "ip_reconciliation_date": None,
                "documents_collected": False,
                "documents_collection_date": None,
                "outstanding_queries_count": 12,
                "outstanding_queries_resolved_date": None,
                "financial_reconciled": False,
                "notes": "Closure visit scheduled. 12 outstanding queries need resolution.",
            },
            {
                "id": "SCSITE-006",
                "closeout_id": "SCO-001",
                "site_id": "SITE-106",
                "site_name": "Cedars-Sinai Medical Center",
                "status": SiteCloseoutStatus.PENDING,
                "scheduled_visit_date": None,
                "actual_visit_date": None,
                "monitor": None,
                "ip_reconciled": False,
                "ip_reconciliation_date": None,
                "documents_collected": False,
                "documents_collection_date": None,
                "outstanding_queries_count": 15,
                "outstanding_queries_resolved_date": None,
                "financial_reconciled": False,
                "notes": "Pending site closure planning.",
            },
        ]

        for s in sites_data:
            self._site_closeouts[s["id"]] = SiteCloseout(**s)

        # --- 4 Site Closeouts for SCO-002 (all pending, for the DUPIXENT trial) ---
        dupixent_sites = [
            {
                "id": "SCSITE-007",
                "closeout_id": "SCO-002",
                "site_id": "SITE-201",
                "site_name": "Stanford Health Care",
                "status": SiteCloseoutStatus.PENDING,
                "scheduled_visit_date": None,
                "actual_visit_date": None,
                "monitor": None,
                "ip_reconciled": False,
                "ip_reconciliation_date": None,
                "documents_collected": False,
                "documents_collection_date": None,
                "outstanding_queries_count": 0,
                "outstanding_queries_resolved_date": None,
                "financial_reconciled": False,
                "notes": None,
            },
            {
                "id": "SCSITE-008",
                "closeout_id": "SCO-002",
                "site_id": "SITE-202",
                "site_name": "Mass General Brigham",
                "status": SiteCloseoutStatus.PENDING,
                "scheduled_visit_date": None,
                "actual_visit_date": None,
                "monitor": None,
                "ip_reconciled": False,
                "ip_reconciliation_date": None,
                "documents_collected": False,
                "documents_collection_date": None,
                "outstanding_queries_count": 0,
                "outstanding_queries_resolved_date": None,
                "financial_reconciled": False,
                "notes": None,
            },
            {
                "id": "SCSITE-009",
                "closeout_id": "SCO-002",
                "site_id": "SITE-203",
                "site_name": "UCSF Medical Center",
                "status": SiteCloseoutStatus.PENDING,
                "scheduled_visit_date": None,
                "actual_visit_date": None,
                "monitor": None,
                "ip_reconciled": False,
                "ip_reconciliation_date": None,
                "documents_collected": False,
                "documents_collection_date": None,
                "outstanding_queries_count": 0,
                "outstanding_queries_resolved_date": None,
                "financial_reconciled": False,
                "notes": None,
            },
            {
                "id": "SCSITE-010",
                "closeout_id": "SCO-002",
                "site_id": "SITE-204",
                "site_name": "NYU Langone Health",
                "status": SiteCloseoutStatus.PENDING,
                "scheduled_visit_date": None,
                "actual_visit_date": None,
                "monitor": None,
                "ip_reconciled": False,
                "ip_reconciliation_date": None,
                "documents_collected": False,
                "documents_collection_date": None,
                "outstanding_queries_count": 0,
                "outstanding_queries_resolved_date": None,
                "financial_reconciled": False,
                "notes": None,
            },
        ]

        for s in dupixent_sites:
            self._site_closeouts[s["id"]] = SiteCloseout(**s)

        # --- 14 Closeout Tasks for SCO-001 ---
        tasks_data = [
            {
                "id": "SCT-001",
                "closeout_id": "SCO-001",
                "site_id": "SITE-101",
                "task_type": CloseoutTaskType.SITE_CLOSURE_VISIT,
                "description": "Conduct site closure visit at Memorial Hermann Hospital",
                "status": TaskStatus.COMPLETED,
                "assigned_to": "Jennifer Lee",
                "due_date": now - timedelta(days=44),
                "completed_date": now - timedelta(days=43),
                "dependencies": [],
                "blockers": [],
                "notes": "Visit completed on schedule.",
            },
            {
                "id": "SCT-002",
                "closeout_id": "SCO-001",
                "site_id": "SITE-101",
                "task_type": CloseoutTaskType.IP_RECONCILIATION,
                "description": "Reconcile IP at Memorial Hermann Hospital",
                "status": TaskStatus.COMPLETED,
                "assigned_to": "Jennifer Lee",
                "due_date": now - timedelta(days=39),
                "completed_date": now - timedelta(days=40),
                "dependencies": ["SCT-001"],
                "blockers": [],
                "notes": "All IP accounted for.",
            },
            {
                "id": "SCT-003",
                "closeout_id": "SCO-001",
                "site_id": "SITE-101",
                "task_type": CloseoutTaskType.DOCUMENT_COLLECTION,
                "description": "Collect documents from Memorial Hermann Hospital",
                "status": TaskStatus.COMPLETED,
                "assigned_to": "Jennifer Lee",
                "due_date": now - timedelta(days=36),
                "completed_date": now - timedelta(days=38),
                "dependencies": ["SCT-001"],
                "blockers": [],
                "notes": "All site documents collected and inventoried.",
            },
            {
                "id": "SCT-004",
                "closeout_id": "SCO-001",
                "site_id": None,
                "task_type": CloseoutTaskType.DATABASE_LOCK,
                "description": "Lock clinical database for EYLEA trial",
                "status": TaskStatus.COMPLETED,
                "assigned_to": "Dr. Sarah Chen",
                "due_date": now - timedelta(days=28),
                "completed_date": now - timedelta(days=30),
                "dependencies": [],
                "blockers": [],
                "notes": "Database locked after all queries resolved.",
            },
            {
                "id": "SCT-005",
                "closeout_id": "SCO-001",
                "site_id": "SITE-103",
                "task_type": CloseoutTaskType.SITE_CLOSURE_VISIT,
                "description": "Conduct site closure visit at Johns Hopkins",
                "status": TaskStatus.COMPLETED,
                "assigned_to": "Jennifer Lee",
                "due_date": now - timedelta(days=19),
                "completed_date": now - timedelta(days=18),
                "dependencies": [],
                "blockers": [],
                "notes": "Visit completed.",
            },
            {
                "id": "SCT-006",
                "closeout_id": "SCO-001",
                "site_id": "SITE-103",
                "task_type": CloseoutTaskType.IP_RECONCILIATION,
                "description": "Reconcile IP at Johns Hopkins",
                "status": TaskStatus.COMPLETED,
                "assigned_to": "Jennifer Lee",
                "due_date": now - timedelta(days=9),
                "completed_date": now - timedelta(days=10),
                "dependencies": ["SCT-005"],
                "blockers": [],
                "notes": "IP reconciled. Minor discrepancy documented.",
            },
            {
                "id": "SCT-007",
                "closeout_id": "SCO-001",
                "site_id": "SITE-103",
                "task_type": CloseoutTaskType.DOCUMENT_COLLECTION,
                "description": "Collect documents from Johns Hopkins",
                "status": TaskStatus.IN_PROGRESS,
                "assigned_to": "Jennifer Lee",
                "due_date": now + timedelta(days=5),
                "completed_date": None,
                "dependencies": ["SCT-005"],
                "blockers": ["Awaiting signed delegation log"],
                "notes": "Partially collected. Awaiting final documents.",
            },
            {
                "id": "SCT-008",
                "closeout_id": "SCO-001",
                "site_id": "SITE-104",
                "task_type": CloseoutTaskType.IP_RECONCILIATION,
                "description": "Reconcile IP at Mayo Clinic Jacksonville",
                "status": TaskStatus.IN_PROGRESS,
                "assigned_to": "David Park",
                "due_date": now + timedelta(days=7),
                "completed_date": None,
                "dependencies": [],
                "blockers": [],
                "notes": "IP count in progress.",
            },
            {
                "id": "SCT-009",
                "closeout_id": "SCO-001",
                "site_id": "SITE-105",
                "task_type": CloseoutTaskType.SITE_CLOSURE_VISIT,
                "description": "Conduct site closure visit at Duke",
                "status": TaskStatus.NOT_STARTED,
                "assigned_to": "Jennifer Lee",
                "due_date": now + timedelta(days=7),
                "completed_date": None,
                "dependencies": [],
                "blockers": [],
                "notes": None,
            },
            {
                "id": "SCT-010",
                "closeout_id": "SCO-001",
                "site_id": None,
                "task_type": CloseoutTaskType.DATA_ARCHIVING,
                "description": "Archive all electronic trial data",
                "status": TaskStatus.IN_PROGRESS,
                "assigned_to": "Lisa Wang",
                "due_date": now + timedelta(days=30),
                "completed_date": None,
                "dependencies": ["SCT-004"],
                "blockers": [],
                "notes": "Archiving in progress. 60% complete.",
            },
            {
                "id": "SCT-011",
                "closeout_id": "SCO-001",
                "site_id": None,
                "task_type": CloseoutTaskType.FINAL_REPORT,
                "description": "Prepare final clinical study report (CSR)",
                "status": TaskStatus.NOT_STARTED,
                "assigned_to": "Dr. Sarah Chen",
                "due_date": now + timedelta(days=60),
                "completed_date": None,
                "dependencies": ["SCT-004", "SCT-010"],
                "blockers": [],
                "notes": "Awaiting archive completion.",
            },
            {
                "id": "SCT-012",
                "closeout_id": "SCO-001",
                "site_id": None,
                "task_type": CloseoutTaskType.REGULATORY_NOTIFICATION,
                "description": "Send end-of-study notifications to all regulatory authorities",
                "status": TaskStatus.IN_PROGRESS,
                "assigned_to": "Maria Garcia",
                "due_date": now + timedelta(days=14),
                "completed_date": None,
                "dependencies": [],
                "blockers": [],
                "notes": "3 of 5 notifications sent.",
            },
            {
                "id": "SCT-013",
                "closeout_id": "SCO-001",
                "site_id": None,
                "task_type": CloseoutTaskType.FINANCIAL_RECONCILIATION,
                "description": "Complete financial reconciliation for all sites",
                "status": TaskStatus.IN_PROGRESS,
                "assigned_to": "Robert Kim",
                "due_date": now + timedelta(days=45),
                "completed_date": None,
                "dependencies": [],
                "blockers": [],
                "notes": "2 of 6 sites reconciled.",
            },
            {
                "id": "SCT-014",
                "closeout_id": "SCO-001",
                "site_id": "SITE-106",
                "task_type": CloseoutTaskType.SAMPLE_DISPOSITION,
                "description": "Dispose of biological samples at Cedars-Sinai",
                "status": TaskStatus.BLOCKED,
                "assigned_to": "David Park",
                "due_date": now - timedelta(days=3),
                "completed_date": None,
                "dependencies": [],
                "blockers": ["Awaiting IRB approval for sample destruction"],
                "notes": "IRB approval pending since last week.",
            },
        ]

        for t in tasks_data:
            self._tasks[t["id"]] = CloseoutTask(**t)

        # --- 3 Document Archives ---
        archives_data = [
            {
                "id": "ARCH-001",
                "closeout_id": "SCO-001",
                "trial_id": EYLEA_TRIAL,
                "archive_type": ArchiveType.ELECTRONIC,
                "archive_location": "AWS S3 - s3://clinical-archives/eylea-phase3/",
                "total_documents": 2450,
                "archived_documents": 1820,
                "archive_date": None,
                "archived_by": "Lisa Wang",
                "retention_period_years": 25,
                "destruction_date": None,
                "verified_by": None,
                "verification_date": None,
            },
            {
                "id": "ARCH-002",
                "closeout_id": "SCO-001",
                "trial_id": EYLEA_TRIAL,
                "archive_type": ArchiveType.PAPER,
                "archive_location": "Iron Mountain Facility - Box 2024-EYLEA-001 through 042",
                "total_documents": 420,
                "archived_documents": 420,
                "archive_date": now - timedelta(days=15),
                "archived_by": "Robert Kim",
                "retention_period_years": 25,
                "destruction_date": now + timedelta(days=25 * 365),
                "verified_by": "Dr. Sarah Chen",
                "verification_date": now - timedelta(days=12),
            },
            {
                "id": "ARCH-003",
                "closeout_id": "SCO-001",
                "trial_id": EYLEA_TRIAL,
                "archive_type": ArchiveType.HYBRID,
                "archive_location": "Sponsor TMF system + Iron Mountain supplement",
                "total_documents": 180,
                "archived_documents": 90,
                "archive_date": None,
                "archived_by": None,
                "retention_period_years": 15,
                "destruction_date": None,
                "verified_by": None,
                "verification_date": None,
            },
        ]

        for a in archives_data:
            self._archives[a["id"]] = DocumentArchive(**a)

        # --- 5 Regulatory Notifications ---
        reg_data = [
            {
                "id": "REGNOT-001",
                "closeout_id": "SCO-001",
                "authority_name": "FDA",
                "country": "United States",
                "notification_type": "end_of_study",
                "sent_date": now - timedelta(days=25),
                "sent_by": "Maria Garcia",
                "acknowledgment_received": True,
                "acknowledgment_date": now - timedelta(days=18),
                "reference_number": "FDA-EOS-2026-00142",
            },
            {
                "id": "REGNOT-002",
                "closeout_id": "SCO-001",
                "authority_name": "EMA",
                "country": "European Union",
                "notification_type": "end_of_study",
                "sent_date": now - timedelta(days=22),
                "sent_by": "Maria Garcia",
                "acknowledgment_received": True,
                "acknowledgment_date": now - timedelta(days=15),
                "reference_number": "EMA-CT-2026-EOS-0087",
            },
            {
                "id": "REGNOT-003",
                "closeout_id": "SCO-001",
                "authority_name": "MHRA",
                "country": "United Kingdom",
                "notification_type": "end_of_study",
                "sent_date": now - timedelta(days=20),
                "sent_by": "Maria Garcia",
                "acknowledgment_received": False,
                "acknowledgment_date": None,
                "reference_number": None,
            },
            {
                "id": "REGNOT-004",
                "closeout_id": "SCO-001",
                "authority_name": "PMDA",
                "country": "Japan",
                "notification_type": "end_of_study",
                "sent_date": None,
                "sent_by": None,
                "acknowledgment_received": False,
                "acknowledgment_date": None,
                "reference_number": None,
            },
            {
                "id": "REGNOT-005",
                "closeout_id": "SCO-001",
                "authority_name": "Health Canada",
                "country": "Canada",
                "notification_type": "end_of_study",
                "sent_date": None,
                "sent_by": None,
                "acknowledgment_received": False,
                "acknowledgment_date": None,
                "reference_number": None,
            },
        ]

        for r in reg_data:
            self._regulatory_notifications[r["id"]] = RegulatoryNotification(**r)

        # --- 4 Financial Reconciliations ---
        fin_data = [
            {
                "id": "FINREC-001",
                "closeout_id": "SCO-001",
                "site_id": "SITE-101",
                "total_paid": 285000.00,
                "total_owed": 295000.00,
                "outstanding_amount": 10000.00,
                "holdback_amount": 15000.00,
                "holdback_released": True,
                "final_payment_date": now - timedelta(days=20),
                "reconciled_by": "Robert Kim",
                "reconciliation_date": now - timedelta(days=22),
                "status": FinancialReconciliationStatus.RECONCILED,
            },
            {
                "id": "FINREC-002",
                "closeout_id": "SCO-001",
                "site_id": "SITE-102",
                "total_paid": 310000.00,
                "total_owed": 325000.00,
                "outstanding_amount": 15000.00,
                "holdback_amount": 20000.00,
                "holdback_released": True,
                "final_payment_date": now - timedelta(days=10),
                "reconciled_by": "Robert Kim",
                "reconciliation_date": now - timedelta(days=12),
                "status": FinancialReconciliationStatus.RECONCILED,
            },
            {
                "id": "FINREC-003",
                "closeout_id": "SCO-001",
                "site_id": "SITE-103",
                "total_paid": 270000.00,
                "total_owed": 290000.00,
                "outstanding_amount": 20000.00,
                "holdback_amount": 18000.00,
                "holdback_released": False,
                "final_payment_date": None,
                "reconciled_by": None,
                "reconciliation_date": None,
                "status": FinancialReconciliationStatus.IN_PROGRESS,
            },
            {
                "id": "FINREC-004",
                "closeout_id": "SCO-001",
                "site_id": "SITE-104",
                "total_paid": 195000.00,
                "total_owed": 240000.00,
                "outstanding_amount": 45000.00,
                "holdback_amount": 25000.00,
                "holdback_released": False,
                "final_payment_date": None,
                "reconciled_by": None,
                "reconciliation_date": None,
                "status": FinancialReconciliationStatus.PENDING,
            },
        ]

        for f in fin_data:
            self._financial_reconciliations[f["id"]] = FinancialReconciliation(**f)

    # ------------------------------------------------------------------
    # Study Closeout CRUD
    # ------------------------------------------------------------------

    def list_closeouts(
        self,
        *,
        status: CloseoutStatus | None = None,
        trial_id: str | None = None,
    ) -> list[StudyCloseout]:
        """List study closeouts with optional filters."""
        with self._lock:
            result = list(self._closeouts.values())

        if status is not None:
            result = [c for c in result if c.status == status]
        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]

        return sorted(result, key=lambda c: c.created_at, reverse=True)

    def get_closeout(self, closeout_id: str) -> StudyCloseout | None:
        """Get a single study closeout by ID."""
        with self._lock:
            return self._closeouts.get(closeout_id)

    def create_closeout(self, payload: StudyCloseoutCreate) -> StudyCloseout:
        """Create a new study closeout."""
        now = datetime.now(timezone.utc)
        closeout_id = f"SCO-{uuid4().hex[:8].upper()}"
        closeout = StudyCloseout(
            id=closeout_id,
            trial_id=payload.trial_id,
            trial_name=payload.trial_name,
            status=CloseoutStatus.NOT_STARTED,
            planned_start_date=payload.planned_start_date,
            actual_start_date=None,
            target_completion_date=payload.target_completion_date,
            actual_completion_date=None,
            closeout_lead=payload.closeout_lead,
            total_sites=payload.total_sites,
            sites_closed=0,
            database_locked=False,
            database_lock_date=None,
            final_csr_submitted=False,
            final_csr_date=None,
            regulatory_notifications_sent=0,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._closeouts[closeout_id] = closeout
        logger.info("Created study closeout %s for trial %s", closeout_id, payload.trial_id)
        return closeout

    def update_closeout(
        self, closeout_id: str, payload: StudyCloseoutUpdate
    ) -> StudyCloseout | None:
        """Update a study closeout."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._closeouts.get(closeout_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            data["updated_at"] = now
            updated = StudyCloseout(**data)
            self._closeouts[closeout_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Initiate Closeout
    # ------------------------------------------------------------------

    def initiate_closeout(self, closeout_id: str) -> StudyCloseout | None:
        """Initiate a study closeout, moving it from not_started/planning to in_progress."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._closeouts.get(closeout_id)
            if existing is None:
                return None

            if existing.status not in (
                CloseoutStatus.NOT_STARTED,
                CloseoutStatus.PLANNING,
            ):
                raise ValueError(
                    f"Cannot initiate closeout in status '{existing.status.value}'. "
                    "Must be 'not_started' or 'planning'."
                )

            data = existing.model_dump()
            data["status"] = CloseoutStatus.IN_PROGRESS
            data["actual_start_date"] = now
            data["updated_at"] = now
            updated = StudyCloseout(**data)
            self._closeouts[closeout_id] = updated
        logger.info("Initiated study closeout %s", closeout_id)
        return updated

    # ------------------------------------------------------------------
    # Site Closeout CRUD
    # ------------------------------------------------------------------

    def list_site_closeouts(
        self,
        closeout_id: str,
        *,
        status: SiteCloseoutStatus | None = None,
    ) -> list[SiteCloseout]:
        """List site closeouts for a study closeout."""
        with self._lock:
            result = [
                sc
                for sc in self._site_closeouts.values()
                if sc.closeout_id == closeout_id
            ]

        if status is not None:
            result = [sc for sc in result if sc.status == status]

        return sorted(result, key=lambda sc: sc.id)

    def get_site_closeout(self, site_closeout_id: str) -> SiteCloseout | None:
        """Get a single site closeout by ID."""
        with self._lock:
            return self._site_closeouts.get(site_closeout_id)

    def create_site_closeout(
        self, closeout_id: str, payload: SiteCloseoutCreate
    ) -> SiteCloseout:
        """Create a new site closeout within a study closeout."""
        sc_id = f"SCSITE-{uuid4().hex[:8].upper()}"
        sc = SiteCloseout(
            id=sc_id,
            closeout_id=closeout_id,
            site_id=payload.site_id,
            site_name=payload.site_name,
            status=SiteCloseoutStatus.PENDING,
            scheduled_visit_date=payload.scheduled_visit_date,
            actual_visit_date=None,
            monitor=payload.monitor,
            ip_reconciled=False,
            ip_reconciliation_date=None,
            documents_collected=False,
            documents_collection_date=None,
            outstanding_queries_count=0,
            outstanding_queries_resolved_date=None,
            financial_reconciled=False,
            notes=None,
        )
        with self._lock:
            self._site_closeouts[sc_id] = sc
            # Update total sites count
            co = self._closeouts.get(closeout_id)
            if co is not None:
                data = co.model_dump()
                data["total_sites"] = data["total_sites"] + 1
                data["updated_at"] = datetime.now(timezone.utc)
                self._closeouts[closeout_id] = StudyCloseout(**data)
        logger.info(
            "Created site closeout %s for closeout %s site %s",
            sc_id, closeout_id, payload.site_id,
        )
        return sc

    def update_site_closeout(
        self, site_closeout_id: str, payload: SiteCloseoutUpdate
    ) -> SiteCloseout | None:
        """Update a site closeout."""
        with self._lock:
            existing = self._site_closeouts.get(site_closeout_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SiteCloseout(**data)
            self._site_closeouts[site_closeout_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Schedule Visit & Complete Site Closure
    # ------------------------------------------------------------------

    def schedule_site_visit(
        self, site_closeout_id: str, payload: ScheduleVisitRequest
    ) -> SiteCloseout | None:
        """Schedule a site closure visit."""
        with self._lock:
            existing = self._site_closeouts.get(site_closeout_id)
            if existing is None:
                return None

            if existing.status not in (
                SiteCloseoutStatus.PENDING,
                SiteCloseoutStatus.SCHEDULED,
            ):
                raise ValueError(
                    f"Cannot schedule visit for site in status '{existing.status.value}'. "
                    "Must be 'pending' or 'scheduled'."
                )

            data = existing.model_dump()
            data["scheduled_visit_date"] = payload.scheduled_visit_date
            data["monitor"] = payload.monitor
            data["status"] = SiteCloseoutStatus.SCHEDULED
            updated = SiteCloseout(**data)
            self._site_closeouts[site_closeout_id] = updated
        logger.info("Scheduled visit for site closeout %s", site_closeout_id)
        return updated

    def complete_site_closure(
        self, site_closeout_id: str, payload: CompleteSiteClosureRequest
    ) -> SiteCloseout | None:
        """Complete a site closure, marking it as closed."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._site_closeouts.get(site_closeout_id)
            if existing is None:
                return None

            if existing.status == SiteCloseoutStatus.CLOSED:
                raise ValueError(
                    f"Site closeout '{site_closeout_id}' is already closed."
                )

            data = existing.model_dump()
            data["status"] = SiteCloseoutStatus.CLOSED
            if payload.actual_visit_date is not None:
                data["actual_visit_date"] = payload.actual_visit_date
            elif data["actual_visit_date"] is None:
                data["actual_visit_date"] = now
            data["ip_reconciled"] = True
            if data["ip_reconciliation_date"] is None:
                data["ip_reconciliation_date"] = now
            data["documents_collected"] = True
            if data["documents_collection_date"] is None:
                data["documents_collection_date"] = now
            data["outstanding_queries_count"] = 0
            data["outstanding_queries_resolved_date"] = now
            data["financial_reconciled"] = True
            if payload.notes is not None:
                data["notes"] = payload.notes

            updated = SiteCloseout(**data)
            self._site_closeouts[site_closeout_id] = updated

            # Update parent closeout sites_closed count
            co = self._closeouts.get(existing.closeout_id)
            if co is not None:
                co_data = co.model_dump()
                co_data["sites_closed"] = co_data["sites_closed"] + 1
                co_data["updated_at"] = now
                self._closeouts[existing.closeout_id] = StudyCloseout(**co_data)

        logger.info("Completed site closure %s", site_closeout_id)
        return updated

    # ------------------------------------------------------------------
    # Closeout Tasks
    # ------------------------------------------------------------------

    def list_tasks(
        self,
        closeout_id: str,
        *,
        status: TaskStatus | None = None,
        task_type: CloseoutTaskType | None = None,
    ) -> list[CloseoutTask]:
        """List tasks for a study closeout."""
        with self._lock:
            result = [
                t for t in self._tasks.values() if t.closeout_id == closeout_id
            ]

        if status is not None:
            result = [t for t in result if t.status == status]
        if task_type is not None:
            result = [t for t in result if t.task_type == task_type]

        return sorted(result, key=lambda t: t.due_date)

    def get_task(self, task_id: str) -> CloseoutTask | None:
        """Get a single task by ID."""
        with self._lock:
            return self._tasks.get(task_id)

    def create_task(
        self, closeout_id: str, payload: CloseoutTaskCreate
    ) -> CloseoutTask:
        """Create a new closeout task."""
        task_id = f"SCT-{uuid4().hex[:8].upper()}"
        task = CloseoutTask(
            id=task_id,
            closeout_id=closeout_id,
            site_id=payload.site_id,
            task_type=payload.task_type,
            description=payload.description,
            status=TaskStatus.NOT_STARTED,
            assigned_to=payload.assigned_to,
            due_date=payload.due_date,
            completed_date=None,
            dependencies=payload.dependencies,
            blockers=[],
            notes=None,
        )
        with self._lock:
            self._tasks[task_id] = task
        logger.info("Created closeout task %s for closeout %s", task_id, closeout_id)
        return task

    def update_task(
        self, task_id: str, payload: CloseoutTaskUpdate
    ) -> CloseoutTask | None:
        """Update a closeout task."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._tasks.get(task_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set completed_date when status goes to completed
            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = TaskStatus(new_status)
                if (
                    new_status == TaskStatus.COMPLETED
                    and existing.status != TaskStatus.COMPLETED
                ):
                    updates.setdefault("completed_date", now)

            data.update(updates)
            updated = CloseoutTask(**data)
            self._tasks[task_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Document Archives
    # ------------------------------------------------------------------

    def list_archives(self, closeout_id: str) -> list[DocumentArchive]:
        """List archives for a study closeout."""
        with self._lock:
            result = [
                a for a in self._archives.values() if a.closeout_id == closeout_id
            ]
        return sorted(result, key=lambda a: a.id)

    def get_archive(self, archive_id: str) -> DocumentArchive | None:
        """Get a single archive by ID."""
        with self._lock:
            return self._archives.get(archive_id)

    def create_archive(
        self, closeout_id: str, payload: DocumentArchiveCreate
    ) -> DocumentArchive:
        """Create a new document archive."""
        co = self.get_closeout(closeout_id)
        if co is None:
            raise ValueError(f"Closeout '{closeout_id}' not found")

        archive_id = f"ARCH-{uuid4().hex[:8].upper()}"
        archive = DocumentArchive(
            id=archive_id,
            closeout_id=closeout_id,
            trial_id=co.trial_id,
            archive_type=payload.archive_type,
            archive_location=payload.archive_location,
            total_documents=payload.total_documents,
            archived_documents=0,
            archive_date=None,
            archived_by=None,
            retention_period_years=payload.retention_period_years,
            destruction_date=None,
            verified_by=None,
            verification_date=None,
        )
        with self._lock:
            self._archives[archive_id] = archive
        logger.info("Created archive %s for closeout %s", archive_id, closeout_id)
        return archive

    # ------------------------------------------------------------------
    # Regulatory Notifications
    # ------------------------------------------------------------------

    def list_regulatory_notifications(
        self, closeout_id: str
    ) -> list[RegulatoryNotification]:
        """List regulatory notifications for a study closeout."""
        with self._lock:
            result = [
                rn
                for rn in self._regulatory_notifications.values()
                if rn.closeout_id == closeout_id
            ]
        return sorted(result, key=lambda rn: rn.id)

    def send_regulatory_notification(
        self, closeout_id: str, payload: RegulatoryNotificationCreate
    ) -> RegulatoryNotification:
        """Send a regulatory notification."""
        now = datetime.now(timezone.utc)
        notif_id = f"REGNOT-{uuid4().hex[:8].upper()}"
        notif = RegulatoryNotification(
            id=notif_id,
            closeout_id=closeout_id,
            authority_name=payload.authority_name,
            country=payload.country,
            notification_type=payload.notification_type,
            sent_date=now,
            sent_by=payload.sent_by,
            acknowledgment_received=False,
            acknowledgment_date=None,
            reference_number=None,
        )
        with self._lock:
            self._regulatory_notifications[notif_id] = notif
            # Update parent closeout notification count
            co = self._closeouts.get(closeout_id)
            if co is not None:
                co_data = co.model_dump()
                co_data["regulatory_notifications_sent"] = (
                    co_data["regulatory_notifications_sent"] + 1
                )
                co_data["updated_at"] = now
                self._closeouts[closeout_id] = StudyCloseout(**co_data)
        logger.info(
            "Sent regulatory notification %s to %s for closeout %s",
            notif_id, payload.authority_name, closeout_id,
        )
        return notif

    # ------------------------------------------------------------------
    # Financial Reconciliation
    # ------------------------------------------------------------------

    def list_financial_reconciliations(
        self, closeout_id: str
    ) -> list[FinancialReconciliation]:
        """List financial reconciliations for a study closeout."""
        with self._lock:
            result = [
                fr
                for fr in self._financial_reconciliations.values()
                if fr.closeout_id == closeout_id
            ]
        return sorted(result, key=lambda fr: fr.id)

    def get_financial_reconciliation(
        self, reconciliation_id: str
    ) -> FinancialReconciliation | None:
        """Get a single financial reconciliation by ID."""
        with self._lock:
            return self._financial_reconciliations.get(reconciliation_id)

    def create_financial_reconciliation(
        self, closeout_id: str, payload: FinancialReconciliationCreate
    ) -> FinancialReconciliation:
        """Create a new financial reconciliation."""
        rec_id = f"FINREC-{uuid4().hex[:8].upper()}"
        outstanding = payload.total_owed - payload.total_paid
        rec = FinancialReconciliation(
            id=rec_id,
            closeout_id=closeout_id,
            site_id=payload.site_id,
            total_paid=payload.total_paid,
            total_owed=payload.total_owed,
            outstanding_amount=outstanding,
            holdback_amount=payload.holdback_amount,
            holdback_released=False,
            final_payment_date=None,
            reconciled_by=None,
            reconciliation_date=None,
            status=FinancialReconciliationStatus.PENDING,
        )
        with self._lock:
            self._financial_reconciliations[rec_id] = rec
        logger.info(
            "Created financial reconciliation %s for closeout %s site %s",
            rec_id, closeout_id, payload.site_id,
        )
        return rec

    def update_financial_reconciliation(
        self, reconciliation_id: str, payload: FinancialReconciliationUpdate
    ) -> FinancialReconciliation | None:
        """Update a financial reconciliation."""
        with self._lock:
            existing = self._financial_reconciliations.get(reconciliation_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)

            # Recalculate outstanding amount if paid or owed changed
            if "total_paid" in updates or "total_owed" in updates:
                data["outstanding_amount"] = data["total_owed"] - data["total_paid"]

            updated = FinancialReconciliation(**data)
            self._financial_reconciliations[reconciliation_id] = updated
        return updated

    def reconcile_finances(
        self, reconciliation_id: str, reconciled_by: str
    ) -> FinancialReconciliation | None:
        """Mark a financial reconciliation as reconciled."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._financial_reconciliations.get(reconciliation_id)
            if existing is None:
                return None

            if existing.status == FinancialReconciliationStatus.RECONCILED:
                raise ValueError(
                    f"Financial reconciliation '{reconciliation_id}' is already reconciled."
                )

            data = existing.model_dump()
            data["status"] = FinancialReconciliationStatus.RECONCILED
            data["reconciled_by"] = reconciled_by
            data["reconciliation_date"] = now
            data["holdback_released"] = True
            updated = FinancialReconciliation(**data)
            self._financial_reconciliations[reconciliation_id] = updated
        logger.info("Reconciled financial record %s", reconciliation_id)
        return updated

    # ------------------------------------------------------------------
    # Progress Tracking
    # ------------------------------------------------------------------

    def get_closeout_progress(self, closeout_id: str) -> CloseoutProgress | None:
        """Get progress summary for a study closeout."""
        now = datetime.now(timezone.utc)

        with self._lock:
            co = self._closeouts.get(closeout_id)
            if co is None:
                return None

            site_closeouts = [
                sc
                for sc in self._site_closeouts.values()
                if sc.closeout_id == closeout_id
            ]
            tasks = [
                t for t in self._tasks.values() if t.closeout_id == closeout_id
            ]
            archives = [
                a for a in self._archives.values() if a.closeout_id == closeout_id
            ]
            fin_recs = [
                fr
                for fr in self._financial_reconciliations.values()
                if fr.closeout_id == closeout_id
            ]
            reg_notifs = [
                rn
                for rn in self._regulatory_notifications.values()
                if rn.closeout_id == closeout_id
            ]

        # Site counts
        sites_closed = sum(
            1 for sc in site_closeouts if sc.status == SiteCloseoutStatus.CLOSED
        )
        sites_pending = sum(
            1 for sc in site_closeouts if sc.status == SiteCloseoutStatus.PENDING
        )
        sites_in_progress = len(site_closeouts) - sites_closed - sites_pending

        # Task counts
        total_tasks = len(tasks)
        tasks_completed = sum(
            1
            for t in tasks
            if t.status in (TaskStatus.COMPLETED, TaskStatus.WAIVED, TaskStatus.NA)
        )
        tasks_in_progress = sum(
            1 for t in tasks if t.status == TaskStatus.IN_PROGRESS
        )
        tasks_blocked = sum(
            1 for t in tasks if t.status == TaskStatus.BLOCKED
        )
        tasks_overdue = sum(
            1
            for t in tasks
            if t.status in (TaskStatus.NOT_STARTED, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED)
            and t.due_date < now
        )

        # Archives
        archives_complete = all(
            a.archived_documents >= a.total_documents for a in archives
        ) if archives else False

        # Financial reconciliation
        fin_complete = all(
            fr.status == FinancialReconciliationStatus.RECONCILED for fr in fin_recs
        ) if fin_recs else False

        # Regulatory notifications
        notifs_sent = sum(
            1 for rn in reg_notifs if rn.sent_date is not None
        )
        notifs_acknowledged = sum(
            1 for rn in reg_notifs if rn.acknowledgment_received
        )

        # Completion percentage
        weight_sites = 40.0
        weight_tasks = 30.0
        weight_archives = 15.0
        weight_finance = 15.0

        site_pct = (sites_closed / len(site_closeouts) * 100) if site_closeouts else 0
        task_pct = (tasks_completed / total_tasks * 100) if total_tasks else 0
        archive_pct = 100.0 if archives_complete else (
            sum(a.archived_documents for a in archives)
            / max(1, sum(a.total_documents for a in archives))
            * 100
        )
        fin_pct = 100.0 if fin_complete else (
            sum(
                1
                for fr in fin_recs
                if fr.status == FinancialReconciliationStatus.RECONCILED
            )
            / max(1, len(fin_recs))
            * 100
        )

        completion = round(
            (
                site_pct * weight_sites
                + task_pct * weight_tasks
                + archive_pct * weight_archives
                + fin_pct * weight_finance
            )
            / 100.0,
            1,
        )

        return CloseoutProgress(
            closeout_id=closeout_id,
            overall_status=co.status,
            total_sites=len(site_closeouts),
            sites_closed=sites_closed,
            sites_in_progress=sites_in_progress,
            sites_pending=sites_pending,
            total_tasks=total_tasks,
            tasks_completed=tasks_completed,
            tasks_in_progress=tasks_in_progress,
            tasks_blocked=tasks_blocked,
            tasks_overdue=tasks_overdue,
            database_locked=co.database_locked,
            archives_complete=archives_complete,
            financial_reconciliation_complete=fin_complete,
            regulatory_notifications_sent=notifs_sent,
            regulatory_notifications_acknowledged=notifs_acknowledged,
            completion_percentage=completion,
        )

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> CloseoutMetrics:
        """Compute aggregated closeout operational metrics."""
        now = datetime.now(timezone.utc)

        with self._lock:
            closeouts = list(self._closeouts.values())
            site_closeouts = list(self._site_closeouts.values())
            tasks = list(self._tasks.values())
            archives = list(self._archives.values())
            fin_recs = list(self._financial_reconciliations.values())

        # Active closeouts
        active = sum(
            1
            for c in closeouts
            if c.status in (CloseoutStatus.PLANNING, CloseoutStatus.IN_PROGRESS)
        )

        # Sites pending closure
        sites_pending = sum(
            1
            for sc in site_closeouts
            if sc.status != SiteCloseoutStatus.CLOSED
        )

        # Average days to close (for closed sites with visit dates)
        close_days: list[float] = []
        for sc in site_closeouts:
            if (
                sc.status == SiteCloseoutStatus.CLOSED
                and sc.scheduled_visit_date is not None
                and sc.actual_visit_date is not None
            ):
                # Days from scheduled visit to closure
                # Use actual_visit_date as a proxy for closure completion
                delta = sc.actual_visit_date - sc.scheduled_visit_date
                close_days.append(abs(delta.total_seconds() / 86400))
        avg_days = round(sum(close_days) / len(close_days), 1) if close_days else 0.0

        # Overdue tasks
        overdue = sum(
            1
            for t in tasks
            if t.status
            in (TaskStatus.NOT_STARTED, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED)
            and t.due_date < now
        )

        # Documents archived
        docs_archived = sum(a.archived_documents for a in archives)

        # Financial reconciliations pending
        fin_pending = sum(
            1
            for fr in fin_recs
            if fr.status
            in (
                FinancialReconciliationStatus.PENDING,
                FinancialReconciliationStatus.IN_PROGRESS,
            )
        )

        return CloseoutMetrics(
            active_closeouts=active,
            sites_pending_closure=sites_pending,
            avg_days_to_close=avg_days,
            overdue_tasks=overdue,
            documents_archived=docs_archived,
            financial_reconciliations_pending=fin_pending,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: StudyCloseoutService | None = None
_lock = threading.Lock()


def get_study_closeout_service() -> StudyCloseoutService:
    """Return the singleton StudyCloseoutService instance."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = StudyCloseoutService()
    return _instance


def reset_study_closeout_service() -> StudyCloseoutService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _lock:
        _instance = StudyCloseoutService()
    return _instance
