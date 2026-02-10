"""Site Payment Reconciliation Service (FINANCE-PR).

Manages payment reconciliation between sponsor and clinical sites including
reconciliation batch lifecycle, site-level payment matching, discrepancy
identification and resolution, payment adjustments with approval workflows,
audit trail tracking, financial close processes, auto-matching, and metrics.

Usage:
    from app.services.payment_reconciliation_service import (
        get_payment_reconciliation_service,
    )

    svc = get_payment_reconciliation_service()
    batches = svc.list_batches()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.payment_reconciliation import (
    AdjustmentApproval,
    AdjustmentType,
    ApprovalStatus,
    AutoMatchRequest,
    DiscrepancyType,
    FinancialClose,
    FinancialCloseRequest,
    PaymentAdjustment,
    PaymentAdjustmentCreate,
    PaymentDiscrepancy,
    PaymentDiscrepancyCreate,
    PaymentDiscrepancyUpdate,
    ReconciliationAuditEntry,
    ReconciliationBatch,
    ReconciliationBatchCreate,
    ReconciliationBatchUpdate,
    ReconciliationMetrics,
    ReconciliationPeriod,
    ReconciliationStatus,
    SiteReconciliation,
    SiteReconciliationCreate,
    SiteReconciliationUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class PaymentReconciliationService:
    """In-memory Site Payment Reconciliation engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._batches: dict[str, ReconciliationBatch] = {}
        self._site_reconciliations: dict[str, SiteReconciliation] = {}
        self._discrepancies: dict[str, PaymentDiscrepancy] = {}
        self._adjustments: dict[str, PaymentAdjustment] = {}
        self._audit_entries: dict[str, ReconciliationAuditEntry] = {}
        self._financial_closes: dict[str, FinancialClose] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic payment reconciliation data."""
        now = datetime.now(timezone.utc)

        # --- 3 Reconciliation Batches ---
        batches_data = [
            {
                "id": "REC-BATCH-001",
                "trial_id": EYLEA_TRIAL,
                "period_type": ReconciliationPeriod.QUARTERLY,
                "period_start": now - timedelta(days=90),
                "period_end": now - timedelta(days=1),
                "status": ReconciliationStatus.RECONCILED,
                "initiated_date": now - timedelta(days=5),
                "initiated_by": "Maria Johnson",
                "completed_date": now - timedelta(days=1),
                "total_payments": 24,
                "total_amount": 1_845_000.00,
                "reconciled_count": 22,
                "discrepancy_count": 2,
                "auto_reconciled_pct": 83.3,
            },
            {
                "id": "REC-BATCH-002",
                "trial_id": DUPIXENT_TRIAL,
                "period_type": ReconciliationPeriod.MONTHLY,
                "period_start": now - timedelta(days=30),
                "period_end": now,
                "status": ReconciliationStatus.IN_PROGRESS,
                "initiated_date": now - timedelta(days=2),
                "initiated_by": "James Chen",
                "completed_date": None,
                "total_payments": 18,
                "total_amount": 972_500.00,
                "reconciled_count": 12,
                "discrepancy_count": 3,
                "auto_reconciled_pct": 66.7,
            },
            {
                "id": "REC-BATCH-003",
                "trial_id": LIBTAYO_TRIAL,
                "period_type": ReconciliationPeriod.QUARTERLY,
                "period_start": now - timedelta(days=180),
                "period_end": now - timedelta(days=91),
                "status": ReconciliationStatus.CLOSED,
                "initiated_date": now - timedelta(days=85),
                "initiated_by": "Sarah Williams",
                "completed_date": now - timedelta(days=80),
                "total_payments": 32,
                "total_amount": 2_156_000.00,
                "reconciled_count": 32,
                "discrepancy_count": 0,
                "auto_reconciled_pct": 96.9,
            },
        ]

        for b in batches_data:
            self._batches[b["id"]] = ReconciliationBatch(**b)

        # --- 8 Site Reconciliations ---
        site_recons_data = [
            {
                "id": "SREC-001",
                "batch_id": "REC-BATCH-001",
                "site_id": "SITE-101",
                "site_name": "Memorial Hermann Hospital",
                "expected_amount": 325_000.00,
                "actual_amount": 325_000.00,
                "variance": 0.0,
                "status": ReconciliationStatus.RECONCILED,
                "last_payment_date": now - timedelta(days=10),
                "payments_count": 4,
                "matched_payments": 4,
                "unmatched_payments": 0,
                "reconciled_by": "Maria Johnson",
                "reconciled_date": now - timedelta(days=3),
                "notes": "All payments matched. No discrepancies.",
            },
            {
                "id": "SREC-002",
                "batch_id": "REC-BATCH-001",
                "site_id": "SITE-102",
                "site_name": "Cleveland Clinic Foundation",
                "expected_amount": 280_000.00,
                "actual_amount": 280_000.00,
                "variance": 0.0,
                "status": ReconciliationStatus.RECONCILED,
                "last_payment_date": now - timedelta(days=15),
                "payments_count": 4,
                "matched_payments": 4,
                "unmatched_payments": 0,
                "reconciled_by": "Maria Johnson",
                "reconciled_date": now - timedelta(days=3),
                "notes": None,
            },
            {
                "id": "SREC-003",
                "batch_id": "REC-BATCH-001",
                "site_id": "SITE-103",
                "site_name": "Johns Hopkins Research Center",
                "expected_amount": 450_000.00,
                "actual_amount": 437_500.00,
                "variance": -12_500.00,
                "status": ReconciliationStatus.DISCREPANCY_IDENTIFIED,
                "last_payment_date": now - timedelta(days=8),
                "payments_count": 6,
                "matched_payments": 5,
                "unmatched_payments": 1,
                "reconciled_by": None,
                "reconciled_date": None,
                "notes": "One payment short by $12,500 - under investigation.",
            },
            {
                "id": "SREC-004",
                "batch_id": "REC-BATCH-001",
                "site_id": "SITE-104",
                "site_name": "Mayo Clinic Jacksonville",
                "expected_amount": 390_000.00,
                "actual_amount": 395_200.00,
                "variance": 5_200.00,
                "status": ReconciliationStatus.DISCREPANCY_IDENTIFIED,
                "last_payment_date": now - timedelta(days=12),
                "payments_count": 5,
                "matched_payments": 4,
                "unmatched_payments": 1,
                "reconciled_by": None,
                "reconciled_date": None,
                "notes": "Overpayment detected - possible duplicate or tax calculation error.",
            },
            {
                "id": "SREC-005",
                "batch_id": "REC-BATCH-002",
                "site_id": "SITE-105",
                "site_name": "Duke Clinical Research Institute",
                "expected_amount": 185_000.00,
                "actual_amount": 185_000.00,
                "variance": 0.0,
                "status": ReconciliationStatus.RECONCILED,
                "last_payment_date": now - timedelta(days=5),
                "payments_count": 3,
                "matched_payments": 3,
                "unmatched_payments": 0,
                "reconciled_by": "James Chen",
                "reconciled_date": now - timedelta(days=1),
                "notes": None,
            },
            {
                "id": "SREC-006",
                "batch_id": "REC-BATCH-002",
                "site_id": "SITE-106",
                "site_name": "Cedars-Sinai Medical Center",
                "expected_amount": 210_000.00,
                "actual_amount": 175_000.00,
                "variance": -35_000.00,
                "status": ReconciliationStatus.DISCREPANCY_IDENTIFIED,
                "last_payment_date": now - timedelta(days=20),
                "payments_count": 3,
                "matched_payments": 2,
                "unmatched_payments": 1,
                "reconciled_by": None,
                "reconciled_date": None,
                "notes": "Missing payment for December services.",
            },
            {
                "id": "SREC-007",
                "batch_id": "REC-BATCH-002",
                "site_id": "SITE-107",
                "site_name": "Mass General Brigham",
                "expected_amount": 275_000.00,
                "actual_amount": 275_000.00,
                "variance": 0.0,
                "status": ReconciliationStatus.PENDING,
                "last_payment_date": now - timedelta(days=3),
                "payments_count": 4,
                "matched_payments": 0,
                "unmatched_payments": 4,
                "reconciled_by": None,
                "reconciled_date": None,
                "notes": "Awaiting auto-match processing.",
            },
            {
                "id": "SREC-008",
                "batch_id": "REC-BATCH-002",
                "site_id": "SITE-108",
                "site_name": "Stanford Health Care",
                "expected_amount": 302_500.00,
                "actual_amount": 302_500.00,
                "variance": 0.0,
                "status": ReconciliationStatus.RECONCILED,
                "last_payment_date": now - timedelta(days=7),
                "payments_count": 4,
                "matched_payments": 4,
                "unmatched_payments": 0,
                "reconciled_by": "James Chen",
                "reconciled_date": now - timedelta(days=1),
                "notes": None,
            },
        ]

        for sr in site_recons_data:
            self._site_reconciliations[sr["id"]] = SiteReconciliation(**sr)

        # --- 5 Payment Discrepancies ---
        discrepancies_data = [
            {
                "id": "DISC-001",
                "reconciliation_id": "SREC-003",
                "site_id": "SITE-103",
                "discrepancy_type": DiscrepancyType.AMOUNT_MISMATCH,
                "expected_amount": 75_000.00,
                "actual_amount": 62_500.00,
                "difference": 12_500.00,
                "description": "Q4 patient visit milestone payment $12,500 short of contracted amount",
                "identified_date": now - timedelta(days=4),
                "assigned_to": "Robert Kim",
                "resolution": None,
                "resolved_date": None,
                "status": ReconciliationStatus.UNDER_REVIEW,
                "root_cause": None,
            },
            {
                "id": "DISC-002",
                "reconciliation_id": "SREC-004",
                "site_id": "SITE-104",
                "discrepancy_type": DiscrepancyType.DUPLICATE_PAYMENT,
                "expected_amount": 78_000.00,
                "actual_amount": 83_200.00,
                "difference": 5_200.00,
                "description": "Duplicate processing fee included in November payment",
                "identified_date": now - timedelta(days=3),
                "assigned_to": "Lisa Park",
                "resolution": None,
                "resolved_date": None,
                "status": ReconciliationStatus.DISCREPANCY_IDENTIFIED,
                "root_cause": "Duplicate invoice submission by site",
            },
            {
                "id": "DISC-003",
                "reconciliation_id": "SREC-006",
                "site_id": "SITE-106",
                "discrepancy_type": DiscrepancyType.MISSING_PAYMENT,
                "expected_amount": 35_000.00,
                "actual_amount": 0.0,
                "difference": 35_000.00,
                "description": "December monitoring visit payment not received by site",
                "identified_date": now - timedelta(days=2),
                "assigned_to": "James Chen",
                "resolution": None,
                "resolved_date": None,
                "status": ReconciliationStatus.UNDER_REVIEW,
                "root_cause": None,
            },
            {
                "id": "DISC-004",
                "reconciliation_id": "SREC-006",
                "site_id": "SITE-106",
                "discrepancy_type": DiscrepancyType.LATE_PAYMENT,
                "expected_amount": 70_000.00,
                "actual_amount": 70_000.00,
                "difference": 0.0,
                "description": "October payment received 18 days past contract terms (Net 30)",
                "identified_date": now - timedelta(days=2),
                "assigned_to": "James Chen",
                "resolution": "Payment confirmed received. Interest accrual under review.",
                "resolved_date": now - timedelta(days=1),
                "status": ReconciliationStatus.RESOLVED,
                "root_cause": "Wire transfer processing delay at sponsor bank",
            },
            {
                "id": "DISC-005",
                "reconciliation_id": "SREC-004",
                "site_id": "SITE-104",
                "discrepancy_type": DiscrepancyType.TAX_ERROR,
                "expected_amount": 12_000.00,
                "actual_amount": 12_480.00,
                "difference": 480.00,
                "description": "Withholding tax calculated at incorrect rate (4% vs contracted 0%)",
                "identified_date": now - timedelta(days=3),
                "assigned_to": "Lisa Park",
                "resolution": None,
                "resolved_date": None,
                "status": ReconciliationStatus.DISCREPANCY_IDENTIFIED,
                "root_cause": "ERP system tax code misconfiguration",
            },
        ]

        for d in discrepancies_data:
            self._discrepancies[d["id"]] = PaymentDiscrepancy(**d)

        # --- 4 Payment Adjustments ---
        adjustments_data = [
            {
                "id": "ADJ-001",
                "reconciliation_id": "SREC-004",
                "site_id": "SITE-104",
                "adjustment_type": AdjustmentType.DEBIT,
                "amount": 5_200.00,
                "currency": "USD",
                "reason": "Recovery of duplicate processing fee from November payment",
                "reference_payment_id": "PAY-NOV-104-003",
                "approved_by": "Sarah Williams",
                "approval_status": ApprovalStatus.APPROVED,
                "approval_date": now - timedelta(days=1),
                "effective_date": now + timedelta(days=5),
                "notes": "Debit to be applied in next payment cycle.",
            },
            {
                "id": "ADJ-002",
                "reconciliation_id": "SREC-003",
                "site_id": "SITE-103",
                "adjustment_type": AdjustmentType.CREDIT,
                "amount": 12_500.00,
                "currency": "USD",
                "reason": "Credit for underpayment on Q4 patient visit milestone",
                "reference_payment_id": "PAY-Q4-103-006",
                "approved_by": None,
                "approval_status": ApprovalStatus.PENDING,
                "approval_date": None,
                "effective_date": None,
                "notes": "Pending finance director approval.",
            },
            {
                "id": "ADJ-003",
                "reconciliation_id": "SREC-006",
                "site_id": "SITE-106",
                "adjustment_type": AdjustmentType.INTEREST,
                "amount": 287.50,
                "currency": "USD",
                "reason": "Interest accrual for late payment (18 days at 8.5% annual)",
                "reference_payment_id": "PAY-OCT-106-002",
                "approved_by": None,
                "approval_status": ApprovalStatus.PENDING,
                "approval_date": None,
                "effective_date": None,
                "notes": "Per contract clause 7.3 - late payment interest.",
            },
            {
                "id": "ADJ-004",
                "reconciliation_id": "SREC-004",
                "site_id": "SITE-104",
                "adjustment_type": AdjustmentType.CORRECTION,
                "amount": 480.00,
                "currency": "USD",
                "reason": "Correction for incorrect withholding tax calculation",
                "reference_payment_id": "PAY-NOV-104-002",
                "approved_by": "Sarah Williams",
                "approval_status": ApprovalStatus.APPROVED,
                "approval_date": now - timedelta(days=1),
                "effective_date": now + timedelta(days=5),
                "notes": "Tax code corrected in ERP. Credit applied.",
            },
        ]

        for a in adjustments_data:
            self._adjustments[a["id"]] = PaymentAdjustment(**a)

        # --- 7 Audit Trail Entries ---
        audit_data = [
            {
                "id": "AUD-001",
                "batch_id": "REC-BATCH-001",
                "action": "batch_initiated",
                "performed_by": "Maria Johnson",
                "performed_date": now - timedelta(days=5),
                "details": "Reconciliation batch REC-BATCH-001 initiated for EYLEA trial Q4 2025",
                "old_value": None,
                "new_value": "pending",
                "entity_type": "batch",
                "entity_id": "REC-BATCH-001",
            },
            {
                "id": "AUD-002",
                "batch_id": "REC-BATCH-001",
                "action": "auto_match_completed",
                "performed_by": "System",
                "performed_date": now - timedelta(days=4),
                "details": "Auto-matching completed: 20 of 24 payments matched (83.3%)",
                "old_value": "0",
                "new_value": "20",
                "entity_type": "batch",
                "entity_id": "REC-BATCH-001",
            },
            {
                "id": "AUD-003",
                "batch_id": "REC-BATCH-001",
                "action": "discrepancy_flagged",
                "performed_by": "Maria Johnson",
                "performed_date": now - timedelta(days=4),
                "details": "Discrepancy DISC-001 flagged: Amount mismatch at SITE-103 ($12,500)",
                "old_value": None,
                "new_value": "discrepancy_identified",
                "entity_type": "discrepancy",
                "entity_id": "DISC-001",
            },
            {
                "id": "AUD-004",
                "batch_id": "REC-BATCH-001",
                "action": "adjustment_created",
                "performed_by": "Maria Johnson",
                "performed_date": now - timedelta(days=3),
                "details": "Adjustment ADJ-001 created: Debit $5,200 for duplicate processing fee at SITE-104",
                "old_value": None,
                "new_value": "5200.00",
                "entity_type": "adjustment",
                "entity_id": "ADJ-001",
            },
            {
                "id": "AUD-005",
                "batch_id": "REC-BATCH-001",
                "action": "adjustment_approved",
                "performed_by": "Sarah Williams",
                "performed_date": now - timedelta(days=1),
                "details": "Adjustment ADJ-001 approved by finance director",
                "old_value": "pending",
                "new_value": "approved",
                "entity_type": "adjustment",
                "entity_id": "ADJ-001",
            },
            {
                "id": "AUD-006",
                "batch_id": "REC-BATCH-001",
                "action": "status_change",
                "performed_by": "Maria Johnson",
                "performed_date": now - timedelta(days=1),
                "details": "Batch status changed from in_progress to reconciled",
                "old_value": "in_progress",
                "new_value": "reconciled",
                "entity_type": "batch",
                "entity_id": "REC-BATCH-001",
            },
            {
                "id": "AUD-007",
                "batch_id": "REC-BATCH-002",
                "action": "batch_initiated",
                "performed_by": "James Chen",
                "performed_date": now - timedelta(days=2),
                "details": "Reconciliation batch REC-BATCH-002 initiated for DUPIXENT trial Jan 2026",
                "old_value": None,
                "new_value": "pending",
                "entity_type": "batch",
                "entity_id": "REC-BATCH-002",
            },
        ]

        for ae in audit_data:
            self._audit_entries[ae["id"]] = ReconciliationAuditEntry(**ae)

        # --- 2 Financial Close records ---
        close_data = [
            {
                "id": "FC-001",
                "trial_id": LIBTAYO_TRIAL,
                "close_period": "2025-Q3",
                "period_start": now - timedelta(days=180),
                "period_end": now - timedelta(days=91),
                "status": ApprovalStatus.APPROVED,
                "total_reconciled": 2_156_000.00,
                "total_adjustments": 3_450.00,
                "outstanding_discrepancies": 0,
                "closed_by": "Sarah Williams",
                "closed_date": now - timedelta(days=78),
                "sign_off_cfo": "David Reynolds",
                "sign_off_date": now - timedelta(days=75),
            },
            {
                "id": "FC-002",
                "trial_id": EYLEA_TRIAL,
                "close_period": "2025-Q4",
                "period_start": now - timedelta(days=90),
                "period_end": now - timedelta(days=1),
                "status": ApprovalStatus.PENDING,
                "total_reconciled": 1_845_000.00,
                "total_adjustments": 18_180.00,
                "outstanding_discrepancies": 2,
                "closed_by": "Maria Johnson",
                "closed_date": None,
                "sign_off_cfo": None,
                "sign_off_date": None,
            },
        ]

        for fc in close_data:
            self._financial_closes[fc["id"]] = FinancialClose(**fc)

    # ------------------------------------------------------------------
    # Reconciliation Batch CRUD
    # ------------------------------------------------------------------

    def list_batches(
        self,
        *,
        trial_id: str | None = None,
        status: ReconciliationStatus | None = None,
    ) -> list[ReconciliationBatch]:
        """List reconciliation batches with optional filters."""
        with self._lock:
            result = list(self._batches.values())

        if trial_id is not None:
            result = [b for b in result if b.trial_id == trial_id]
        if status is not None:
            result = [b for b in result if b.status == status]

        return sorted(result, key=lambda b: b.initiated_date, reverse=True)

    def get_batch(self, batch_id: str) -> ReconciliationBatch | None:
        """Get a single batch by ID."""
        with self._lock:
            return self._batches.get(batch_id)

    def create_batch(self, payload: ReconciliationBatchCreate) -> ReconciliationBatch:
        """Create a new reconciliation batch (initiate reconciliation)."""
        now = datetime.now(timezone.utc)
        batch_id = f"REC-BATCH-{uuid4().hex[:8].upper()}"
        batch = ReconciliationBatch(
            id=batch_id,
            trial_id=payload.trial_id,
            period_type=payload.period_type,
            period_start=payload.period_start,
            period_end=payload.period_end,
            status=ReconciliationStatus.PENDING,
            initiated_date=now,
            initiated_by=payload.initiated_by,
            completed_date=None,
            total_payments=0,
            total_amount=0.0,
            reconciled_count=0,
            discrepancy_count=0,
            auto_reconciled_pct=0.0,
        )
        with self._lock:
            self._batches[batch_id] = batch

        self._create_audit_entry(
            batch_id=batch_id,
            action="batch_initiated",
            performed_by=payload.initiated_by,
            details=f"Reconciliation batch {batch_id} initiated for trial {payload.trial_id}",
            old_value=None,
            new_value="pending",
            entity_type="batch",
            entity_id=batch_id,
        )
        logger.info("Created reconciliation batch %s for trial %s", batch_id, payload.trial_id)
        return batch

    def update_batch(self, batch_id: str, payload: ReconciliationBatchUpdate) -> ReconciliationBatch | None:
        """Update a reconciliation batch."""
        with self._lock:
            existing = self._batches.get(batch_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            old_status = data.get("status")
            data.update(updates)
            updated = ReconciliationBatch(**data)
            self._batches[batch_id] = updated

        if "status" in updates:
            self._create_audit_entry(
                batch_id=batch_id,
                action="status_change",
                performed_by="System",
                details=f"Batch status changed from {old_status} to {updates['status']}",
                old_value=str(old_status) if old_status else None,
                new_value=str(updates["status"]),
                entity_type="batch",
                entity_id=batch_id,
            )
        return updated

    def delete_batch(self, batch_id: str) -> bool:
        """Delete a reconciliation batch."""
        with self._lock:
            if batch_id in self._batches:
                del self._batches[batch_id]
                return True
            return False

    def initiate_reconciliation(self, payload: ReconciliationBatchCreate) -> ReconciliationBatch:
        """Initiate a new reconciliation process (alias for create_batch with status set)."""
        batch = self.create_batch(payload)
        # Move to in_progress
        with self._lock:
            data = batch.model_dump()
            data["status"] = ReconciliationStatus.IN_PROGRESS
            updated = ReconciliationBatch(**data)
            self._batches[batch.id] = updated
        self._create_audit_entry(
            batch_id=batch.id,
            action="reconciliation_started",
            performed_by=payload.initiated_by,
            details=f"Reconciliation process started for batch {batch.id}",
            old_value="pending",
            new_value="in_progress",
            entity_type="batch",
            entity_id=batch.id,
        )
        return updated

    # ------------------------------------------------------------------
    # Site Reconciliation CRUD
    # ------------------------------------------------------------------

    def list_site_reconciliations(
        self,
        *,
        batch_id: str | None = None,
        site_id: str | None = None,
        status: ReconciliationStatus | None = None,
    ) -> list[SiteReconciliation]:
        """List site reconciliation records with optional filters."""
        with self._lock:
            result = list(self._site_reconciliations.values())

        if batch_id is not None:
            result = [sr for sr in result if sr.batch_id == batch_id]
        if site_id is not None:
            result = [sr for sr in result if sr.site_id == site_id]
        if status is not None:
            result = [sr for sr in result if sr.status == status]

        return sorted(result, key=lambda sr: sr.id)

    def get_site_reconciliation(self, recon_id: str) -> SiteReconciliation | None:
        """Get a single site reconciliation by ID."""
        with self._lock:
            return self._site_reconciliations.get(recon_id)

    def create_site_reconciliation(self, payload: SiteReconciliationCreate) -> SiteReconciliation:
        """Create a site reconciliation record."""
        now = datetime.now(timezone.utc)
        recon_id = f"SREC-{uuid4().hex[:8].upper()}"
        variance = payload.actual_amount - payload.expected_amount
        sr = SiteReconciliation(
            id=recon_id,
            batch_id=payload.batch_id,
            site_id=payload.site_id,
            site_name=payload.site_name,
            expected_amount=payload.expected_amount,
            actual_amount=payload.actual_amount,
            variance=round(variance, 2),
            status=ReconciliationStatus.PENDING,
            last_payment_date=None,
            payments_count=0,
            matched_payments=0,
            unmatched_payments=0,
            reconciled_by=None,
            reconciled_date=None,
            notes=None,
        )
        with self._lock:
            self._site_reconciliations[recon_id] = sr

        # Update parent batch counts
        self._update_batch_counts(payload.batch_id)

        logger.info("Created site reconciliation %s for site %s", recon_id, payload.site_id)
        return sr

    def update_site_reconciliation(
        self, recon_id: str, payload: SiteReconciliationUpdate,
    ) -> SiteReconciliation | None:
        """Update a site reconciliation record."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._site_reconciliations.get(recon_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Recalculate variance if amounts change
            if "expected_amount" in updates or "actual_amount" in updates:
                exp = updates.get("expected_amount", data["expected_amount"])
                act = updates.get("actual_amount", data["actual_amount"])
                updates["variance"] = round(act - exp, 2)

            # Auto-set reconciled_date when status goes to reconciled
            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = ReconciliationStatus(new_status)
                if new_status == ReconciliationStatus.RECONCILED and existing.status != ReconciliationStatus.RECONCILED:
                    updates["reconciled_date"] = now

            data.update(updates)
            updated = SiteReconciliation(**data)
            self._site_reconciliations[recon_id] = updated
        return updated

    def delete_site_reconciliation(self, recon_id: str) -> bool:
        """Delete a site reconciliation record."""
        with self._lock:
            if recon_id in self._site_reconciliations:
                del self._site_reconciliations[recon_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Payment Discrepancy
    # ------------------------------------------------------------------

    def list_discrepancies(
        self,
        *,
        site_id: str | None = None,
        reconciliation_id: str | None = None,
        discrepancy_type: DiscrepancyType | None = None,
        status: ReconciliationStatus | None = None,
    ) -> list[PaymentDiscrepancy]:
        """List discrepancies with optional filters."""
        with self._lock:
            result = list(self._discrepancies.values())

        if site_id is not None:
            result = [d for d in result if d.site_id == site_id]
        if reconciliation_id is not None:
            result = [d for d in result if d.reconciliation_id == reconciliation_id]
        if discrepancy_type is not None:
            result = [d for d in result if d.discrepancy_type == discrepancy_type]
        if status is not None:
            result = [d for d in result if d.status == status]

        return sorted(result, key=lambda d: d.identified_date, reverse=True)

    def get_discrepancy(self, disc_id: str) -> PaymentDiscrepancy | None:
        """Get a single discrepancy by ID."""
        with self._lock:
            return self._discrepancies.get(disc_id)

    def flag_discrepancy(self, payload: PaymentDiscrepancyCreate) -> PaymentDiscrepancy:
        """Flag a new payment discrepancy."""
        now = datetime.now(timezone.utc)
        disc_id = f"DISC-{uuid4().hex[:8].upper()}"
        difference = abs(payload.expected_amount - payload.actual_amount)
        disc = PaymentDiscrepancy(
            id=disc_id,
            reconciliation_id=payload.reconciliation_id,
            site_id=payload.site_id,
            discrepancy_type=payload.discrepancy_type,
            expected_amount=payload.expected_amount,
            actual_amount=payload.actual_amount,
            difference=round(difference, 2),
            description=payload.description,
            identified_date=now,
            assigned_to=payload.assigned_to,
            resolution=None,
            resolved_date=None,
            status=ReconciliationStatus.DISCREPANCY_IDENTIFIED,
            root_cause=None,
        )
        with self._lock:
            self._discrepancies[disc_id] = disc

        # Determine batch_id from the reconciliation
        batch_id = self._get_batch_id_for_reconciliation(payload.reconciliation_id)
        if batch_id:
            self._create_audit_entry(
                batch_id=batch_id,
                action="discrepancy_flagged",
                performed_by=payload.assigned_to or "System",
                details=f"Discrepancy {disc_id} flagged: {payload.discrepancy_type.value} at {payload.site_id} (${difference:,.2f})",
                old_value=None,
                new_value="discrepancy_identified",
                entity_type="discrepancy",
                entity_id=disc_id,
            )

        logger.info("Flagged discrepancy %s: %s at %s", disc_id, payload.discrepancy_type.value, payload.site_id)
        return disc

    def update_discrepancy(
        self, disc_id: str, payload: PaymentDiscrepancyUpdate,
    ) -> PaymentDiscrepancy | None:
        """Update a discrepancy (e.g., resolve it)."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._discrepancies.get(disc_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set resolved_date when status goes to resolved
            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = ReconciliationStatus(new_status)
                if new_status == ReconciliationStatus.RESOLVED and existing.status != ReconciliationStatus.RESOLVED:
                    updates["resolved_date"] = now

            data.update(updates)
            updated = PaymentDiscrepancy(**data)
            self._discrepancies[disc_id] = updated
        return updated

    def delete_discrepancy(self, disc_id: str) -> bool:
        """Delete a discrepancy."""
        with self._lock:
            if disc_id in self._discrepancies:
                del self._discrepancies[disc_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Payment Adjustments
    # ------------------------------------------------------------------

    def list_adjustments(
        self,
        *,
        site_id: str | None = None,
        reconciliation_id: str | None = None,
        adjustment_type: AdjustmentType | None = None,
        approval_status: ApprovalStatus | None = None,
    ) -> list[PaymentAdjustment]:
        """List adjustments with optional filters."""
        with self._lock:
            result = list(self._adjustments.values())

        if site_id is not None:
            result = [a for a in result if a.site_id == site_id]
        if reconciliation_id is not None:
            result = [a for a in result if a.reconciliation_id == reconciliation_id]
        if adjustment_type is not None:
            result = [a for a in result if a.adjustment_type == adjustment_type]
        if approval_status is not None:
            result = [a for a in result if a.approval_status == approval_status]

        return sorted(result, key=lambda a: a.id)

    def get_adjustment(self, adj_id: str) -> PaymentAdjustment | None:
        """Get a single adjustment by ID."""
        with self._lock:
            return self._adjustments.get(adj_id)

    def create_adjustment(self, payload: PaymentAdjustmentCreate) -> PaymentAdjustment:
        """Create a payment adjustment."""
        adj_id = f"ADJ-{uuid4().hex[:8].upper()}"
        adj = PaymentAdjustment(
            id=adj_id,
            reconciliation_id=payload.reconciliation_id,
            site_id=payload.site_id,
            adjustment_type=payload.adjustment_type,
            amount=payload.amount,
            currency=payload.currency,
            reason=payload.reason,
            reference_payment_id=payload.reference_payment_id,
            approved_by=None,
            approval_status=ApprovalStatus.PENDING,
            approval_date=None,
            effective_date=payload.effective_date,
            notes=payload.notes,
        )
        with self._lock:
            self._adjustments[adj_id] = adj

        batch_id = self._get_batch_id_for_reconciliation(payload.reconciliation_id)
        if batch_id:
            self._create_audit_entry(
                batch_id=batch_id,
                action="adjustment_created",
                performed_by="System",
                details=f"Adjustment {adj_id} created: {payload.adjustment_type.value} ${payload.amount:,.2f} for {payload.site_id}",
                old_value=None,
                new_value=f"{payload.amount:.2f}",
                entity_type="adjustment",
                entity_id=adj_id,
            )
        logger.info("Created adjustment %s: %s $%.2f", adj_id, payload.adjustment_type.value, payload.amount)
        return adj

    def approve_adjustment(self, adj_id: str, payload: AdjustmentApproval) -> PaymentAdjustment | None:
        """Approve or reject a payment adjustment."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._adjustments.get(adj_id)
            if existing is None:
                return None

            if existing.approval_status != ApprovalStatus.PENDING:
                raise ValueError(
                    f"Adjustment '{adj_id}' has already been {existing.approval_status.value}"
                )

            data = existing.model_dump()
            data["approval_status"] = payload.approval_status
            data["approved_by"] = payload.approved_by
            data["approval_date"] = now
            if payload.notes:
                data["notes"] = payload.notes
            updated = PaymentAdjustment(**data)
            self._adjustments[adj_id] = updated

        batch_id = self._get_batch_id_for_reconciliation(existing.reconciliation_id)
        if batch_id:
            self._create_audit_entry(
                batch_id=batch_id,
                action=f"adjustment_{payload.approval_status.value}",
                performed_by=payload.approved_by,
                details=f"Adjustment {adj_id} {payload.approval_status.value} by {payload.approved_by}",
                old_value="pending",
                new_value=payload.approval_status.value,
                entity_type="adjustment",
                entity_id=adj_id,
            )
        logger.info("Adjustment %s %s by %s", adj_id, payload.approval_status.value, payload.approved_by)
        return updated

    def delete_adjustment(self, adj_id: str) -> bool:
        """Delete an adjustment."""
        with self._lock:
            if adj_id in self._adjustments:
                del self._adjustments[adj_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Audit Trail
    # ------------------------------------------------------------------

    def list_audit_entries(
        self,
        *,
        batch_id: str | None = None,
        entity_type: str | None = None,
        performed_by: str | None = None,
    ) -> list[ReconciliationAuditEntry]:
        """List audit trail entries with optional filters."""
        with self._lock:
            result = list(self._audit_entries.values())

        if batch_id is not None:
            result = [e for e in result if e.batch_id == batch_id]
        if entity_type is not None:
            result = [e for e in result if e.entity_type == entity_type]
        if performed_by is not None:
            result = [e for e in result if e.performed_by == performed_by]

        return sorted(result, key=lambda e: e.performed_date, reverse=True)

    def get_audit_entry(self, entry_id: str) -> ReconciliationAuditEntry | None:
        """Get a single audit entry by ID."""
        with self._lock:
            return self._audit_entries.get(entry_id)

    def _create_audit_entry(
        self,
        *,
        batch_id: str,
        action: str,
        performed_by: str,
        details: str,
        old_value: str | None,
        new_value: str | None,
        entity_type: str,
        entity_id: str,
    ) -> ReconciliationAuditEntry:
        """Internal: create an audit trail entry."""
        now = datetime.now(timezone.utc)
        entry_id = f"AUD-{uuid4().hex[:8].upper()}"
        entry = ReconciliationAuditEntry(
            id=entry_id,
            batch_id=batch_id,
            action=action,
            performed_by=performed_by,
            performed_date=now,
            details=details,
            old_value=old_value,
            new_value=new_value,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        with self._lock:
            self._audit_entries[entry_id] = entry
        return entry

    # ------------------------------------------------------------------
    # Financial Close
    # ------------------------------------------------------------------

    def list_financial_closes(
        self,
        *,
        trial_id: str | None = None,
        status: ApprovalStatus | None = None,
    ) -> list[FinancialClose]:
        """List financial close records with optional filters."""
        with self._lock:
            result = list(self._financial_closes.values())

        if trial_id is not None:
            result = [fc for fc in result if fc.trial_id == trial_id]
        if status is not None:
            result = [fc for fc in result if fc.status == status]

        return sorted(result, key=lambda fc: fc.period_start, reverse=True)

    def get_financial_close(self, close_id: str) -> FinancialClose | None:
        """Get a single financial close by ID."""
        with self._lock:
            return self._financial_closes.get(close_id)

    def close_period(self, payload: FinancialCloseRequest) -> FinancialClose:
        """Close a financial period."""
        now = datetime.now(timezone.utc)
        close_id = f"FC-{uuid4().hex[:8].upper()}"

        # Calculate totals from reconciliation data
        total_reconciled = 0.0
        total_adj = 0.0
        outstanding_disc = 0

        with self._lock:
            for sr in self._site_reconciliations.values():
                if sr.status == ReconciliationStatus.RECONCILED:
                    total_reconciled += sr.actual_amount

            for adj in self._adjustments.values():
                if adj.approval_status == ApprovalStatus.APPROVED:
                    total_adj += adj.amount

            for disc in self._discrepancies.values():
                if disc.status not in (
                    ReconciliationStatus.RESOLVED,
                    ReconciliationStatus.CLOSED,
                ):
                    outstanding_disc += 1

        fc = FinancialClose(
            id=close_id,
            trial_id=payload.trial_id,
            close_period=payload.close_period,
            period_start=payload.period_start,
            period_end=payload.period_end,
            status=ApprovalStatus.PENDING,
            total_reconciled=round(total_reconciled, 2),
            total_adjustments=round(total_adj, 2),
            outstanding_discrepancies=outstanding_disc,
            closed_by=payload.closed_by,
            closed_date=now,
            sign_off_cfo=payload.sign_off_cfo,
            sign_off_date=now if payload.sign_off_cfo else None,
        )
        with self._lock:
            self._financial_closes[close_id] = fc

        logger.info("Financial close %s created for period %s", close_id, payload.close_period)
        return fc

    def approve_financial_close(
        self, close_id: str, approved_by: str, sign_off_cfo: str | None = None,
    ) -> FinancialClose | None:
        """Approve a financial close."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._financial_closes.get(close_id)
            if existing is None:
                return None

            if existing.status != ApprovalStatus.PENDING:
                raise ValueError(
                    f"Financial close '{close_id}' has already been {existing.status.value}"
                )

            data = existing.model_dump()
            data["status"] = ApprovalStatus.APPROVED
            data["closed_date"] = now
            if sign_off_cfo:
                data["sign_off_cfo"] = sign_off_cfo
                data["sign_off_date"] = now
            updated = FinancialClose(**data)
            self._financial_closes[close_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Auto-matching
    # ------------------------------------------------------------------

    def auto_match_payments(
        self,
        batch_id: str,
        payload: AutoMatchRequest,
    ) -> ReconciliationBatch | None:
        """Auto-match payments within a batch using tolerance-based matching."""
        with self._lock:
            batch = self._batches.get(batch_id)
            if batch is None:
                return None

            # Get all site reconciliations for this batch
            site_recons = [
                sr for sr in self._site_reconciliations.values()
                if sr.batch_id == batch_id
            ]

        tolerance = payload.tolerance_pct / 100.0
        matched_count = 0
        total_count = 0

        for sr in site_recons:
            total_count += sr.payments_count
            if sr.status in (ReconciliationStatus.RECONCILED, ReconciliationStatus.CLOSED):
                matched_count += sr.matched_payments
                continue

            # Auto-match logic: if variance is within tolerance, mark as reconciled
            if sr.expected_amount > 0:
                variance_pct = abs(sr.variance) / sr.expected_amount
            else:
                variance_pct = 0.0 if sr.variance == 0 else 1.0

            if variance_pct <= tolerance:
                now = datetime.now(timezone.utc)
                with self._lock:
                    data = sr.model_dump()
                    data["status"] = ReconciliationStatus.RECONCILED
                    data["matched_payments"] = sr.payments_count
                    data["unmatched_payments"] = 0
                    data["reconciled_by"] = "Auto-Match System"
                    data["reconciled_date"] = now
                    updated_sr = SiteReconciliation(**data)
                    self._site_reconciliations[sr.id] = updated_sr
                matched_count += sr.payments_count
            else:
                matched_count += sr.matched_payments

        # Update batch statistics
        auto_pct = round((matched_count / max(1, total_count)) * 100, 1)
        with self._lock:
            data = batch.model_dump()
            data["reconciled_count"] = matched_count
            data["auto_reconciled_pct"] = auto_pct
            data["total_payments"] = total_count
            updated_batch = ReconciliationBatch(**data)
            self._batches[batch_id] = updated_batch

        self._create_audit_entry(
            batch_id=batch_id,
            action="auto_match_completed",
            performed_by="System",
            details=f"Auto-matching completed: {matched_count} of {total_count} payments matched ({auto_pct}%) with {payload.tolerance_pct}% tolerance",
            old_value=str(batch.reconciled_count),
            new_value=str(matched_count),
            entity_type="batch",
            entity_id=batch_id,
        )
        logger.info("Auto-match for batch %s: %d/%d matched (%.1f%%)", batch_id, matched_count, total_count, auto_pct)
        return updated_batch

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> ReconciliationMetrics:
        """Compute aggregated reconciliation metrics."""
        with self._lock:
            batches = list(self._batches.values())
            site_recons = list(self._site_reconciliations.values())
            discrepancies = list(self._discrepancies.values())
            adjustments = list(self._adjustments.values())
            audit_entries = list(self._audit_entries.values())
            financial_closes = list(self._financial_closes.values())

        pending_batches = sum(
            1 for b in batches
            if b.status in (ReconciliationStatus.PENDING, ReconciliationStatus.IN_PROGRESS)
        )
        completed_batches = sum(
            1 for b in batches
            if b.status in (ReconciliationStatus.RECONCILED, ReconciliationStatus.CLOSED)
        )

        open_disc = sum(
            1 for d in discrepancies
            if d.status not in (ReconciliationStatus.RESOLVED, ReconciliationStatus.CLOSED)
        )
        resolved_disc = sum(
            1 for d in discrepancies
            if d.status in (ReconciliationStatus.RESOLVED, ReconciliationStatus.CLOSED)
        )

        pending_adj = sum(1 for a in adjustments if a.approval_status == ApprovalStatus.PENDING)
        approved_adj = sum(1 for a in adjustments if a.approval_status == ApprovalStatus.APPROVED)
        total_adj_amount = sum(a.amount for a in adjustments if a.approval_status == ApprovalStatus.APPROVED)

        avg_auto = 0.0
        if batches:
            avg_auto = round(sum(b.auto_reconciled_pct for b in batches) / len(batches), 1)

        open_fc = sum(1 for fc in financial_closes if fc.status == ApprovalStatus.PENDING)

        return ReconciliationMetrics(
            total_batches=len(batches),
            pending_batches=pending_batches,
            completed_batches=completed_batches,
            total_site_reconciliations=len(site_recons),
            total_discrepancies=len(discrepancies),
            open_discrepancies=open_disc,
            resolved_discrepancies=resolved_disc,
            total_adjustments=len(adjustments),
            pending_adjustments=pending_adj,
            approved_adjustments=approved_adj,
            total_adjustment_amount=round(total_adj_amount, 2),
            avg_auto_reconciled_pct=avg_auto,
            total_financial_closes=len(financial_closes),
            open_financial_closes=open_fc,
            total_audit_entries=len(audit_entries),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_batch_id_for_reconciliation(self, reconciliation_id: str) -> str | None:
        """Get the batch ID for a given site reconciliation ID."""
        with self._lock:
            sr = self._site_reconciliations.get(reconciliation_id)
            return sr.batch_id if sr else None

    def _update_batch_counts(self, batch_id: str) -> None:
        """Recalculate batch counts from site reconciliations."""
        with self._lock:
            batch = self._batches.get(batch_id)
            if batch is None:
                return

            site_recons = [
                sr for sr in self._site_reconciliations.values()
                if sr.batch_id == batch_id
            ]

            total_payments = sum(sr.payments_count for sr in site_recons)
            total_amount = sum(sr.expected_amount for sr in site_recons)
            reconciled = sum(
                sr.matched_payments for sr in site_recons
                if sr.status == ReconciliationStatus.RECONCILED
            )
            disc_count = sum(
                1 for sr in site_recons
                if sr.status == ReconciliationStatus.DISCREPANCY_IDENTIFIED
            )

            data = batch.model_dump()
            data["total_payments"] = total_payments
            data["total_amount"] = round(total_amount, 2)
            data["reconciled_count"] = reconciled
            data["discrepancy_count"] = disc_count
            updated = ReconciliationBatch(**data)
            self._batches[batch_id] = updated


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: PaymentReconciliationService | None = None
_instance_lock = threading.Lock()


def get_payment_reconciliation_service() -> PaymentReconciliationService:
    """Return the singleton PaymentReconciliationService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = PaymentReconciliationService()
    return _instance


def reset_payment_reconciliation_service() -> PaymentReconciliationService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = PaymentReconciliationService()
    return _instance
