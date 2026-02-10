"""Pydantic schemas for Site Payment Reconciliation (FINANCE-PR).

Manages payment reconciliation between sponsor and clinical sites: reconciliation
batch lifecycle, site-level payment matching, discrepancy identification and
resolution, payment adjustments with approval workflows, audit trail tracking,
financial close processes, and reconciliation operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ReconciliationStatus(str, Enum):
    """Lifecycle status of a reconciliation batch or site reconciliation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RECONCILED = "reconciled"
    DISCREPANCY_IDENTIFIED = "discrepancy_identified"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    CLOSED = "closed"


class DiscrepancyType(str, Enum):
    """Classification of a payment discrepancy."""

    AMOUNT_MISMATCH = "amount_mismatch"
    MISSING_PAYMENT = "missing_payment"
    DUPLICATE_PAYMENT = "duplicate_payment"
    WRONG_SITE = "wrong_site"
    WRONG_PERIOD = "wrong_period"
    CURRENCY_ERROR = "currency_error"
    TAX_ERROR = "tax_error"
    LATE_PAYMENT = "late_payment"


class AdjustmentType(str, Enum):
    """Type of financial adjustment applied."""

    CREDIT = "credit"
    DEBIT = "debit"
    WRITEOFF = "writeoff"
    REFUND = "refund"
    CORRECTION = "correction"
    INTEREST = "interest"


class ReconciliationPeriod(str, Enum):
    """Period granularity for reconciliation batches."""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"


class ApprovalStatus(str, Enum):
    """Approval workflow status for adjustments and close processes."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class ReconciliationBatch(BaseModel):
    """A reconciliation batch covering a specific trial and period."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique batch identifier")
    trial_id: str = Field(..., description="Associated clinical trial identifier")
    period_type: ReconciliationPeriod = Field(..., description="Reconciliation period type")
    period_start: datetime = Field(..., description="Start date of the reconciliation period")
    period_end: datetime = Field(..., description="End date of the reconciliation period")
    status: ReconciliationStatus = Field(
        default=ReconciliationStatus.PENDING, description="Current batch status"
    )
    initiated_date: datetime = Field(..., description="Date reconciliation was initiated")
    initiated_by: str = Field(..., description="User who initiated the reconciliation")
    completed_date: datetime | None = Field(None, description="Date reconciliation was completed")
    total_payments: int = Field(default=0, ge=0, description="Total number of payments in the batch")
    total_amount: float = Field(default=0.0, description="Total monetary amount across all payments")
    reconciled_count: int = Field(default=0, ge=0, description="Number of successfully reconciled payments")
    discrepancy_count: int = Field(default=0, ge=0, description="Number of identified discrepancies")
    auto_reconciled_pct: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Percentage of payments auto-reconciled"
    )


class SiteReconciliation(BaseModel):
    """Payment reconciliation record for a specific site within a batch."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique site reconciliation identifier")
    batch_id: str = Field(..., description="Parent reconciliation batch identifier")
    site_id: str = Field(..., description="Clinical site identifier")
    site_name: str = Field(..., description="Clinical site name")
    expected_amount: float = Field(..., description="Expected payment amount based on contract terms")
    actual_amount: float = Field(..., description="Actual payment amount received or sent")
    variance: float = Field(..., description="Difference between expected and actual amounts")
    status: ReconciliationStatus = Field(
        default=ReconciliationStatus.PENDING, description="Site reconciliation status"
    )
    last_payment_date: datetime | None = Field(
        None, description="Date of the most recent payment for this site"
    )
    payments_count: int = Field(default=0, ge=0, description="Total number of payments for this site")
    matched_payments: int = Field(default=0, ge=0, description="Number of matched payments")
    unmatched_payments: int = Field(default=0, ge=0, description="Number of unmatched payments")
    reconciled_by: str | None = Field(None, description="User who performed the reconciliation")
    reconciled_date: datetime | None = Field(None, description="Date the reconciliation was completed")
    notes: str | None = Field(None, description="Reconciliation notes and comments")


class PaymentDiscrepancy(BaseModel):
    """A discrepancy identified during payment reconciliation."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique discrepancy identifier")
    reconciliation_id: str = Field(..., description="Parent site reconciliation identifier")
    site_id: str = Field(..., description="Clinical site identifier")
    discrepancy_type: DiscrepancyType = Field(..., description="Classification of the discrepancy")
    expected_amount: float = Field(..., description="Expected payment amount")
    actual_amount: float = Field(..., description="Actual payment amount")
    difference: float = Field(..., description="Absolute difference between expected and actual")
    description: str = Field(..., description="Detailed description of the discrepancy")
    identified_date: datetime = Field(..., description="Date the discrepancy was identified")
    assigned_to: str | None = Field(None, description="User assigned to resolve the discrepancy")
    resolution: str | None = Field(None, description="Resolution description once resolved")
    resolved_date: datetime | None = Field(None, description="Date the discrepancy was resolved")
    status: ReconciliationStatus = Field(
        default=ReconciliationStatus.DISCREPANCY_IDENTIFIED,
        description="Discrepancy resolution status",
    )
    root_cause: str | None = Field(None, description="Root cause analysis of the discrepancy")


class PaymentAdjustment(BaseModel):
    """A financial adjustment applied during reconciliation."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique adjustment identifier")
    reconciliation_id: str = Field(..., description="Parent site reconciliation identifier")
    site_id: str = Field(..., description="Clinical site identifier")
    adjustment_type: AdjustmentType = Field(..., description="Type of financial adjustment")
    amount: float = Field(..., description="Adjustment amount (positive value)")
    currency: str = Field(default="USD", description="Currency code (ISO 4217)")
    reason: str = Field(..., description="Reason for the adjustment")
    reference_payment_id: str | None = Field(
        None, description="Reference to the original payment being adjusted"
    )
    approved_by: str | None = Field(None, description="User who approved the adjustment")
    approval_status: ApprovalStatus = Field(
        default=ApprovalStatus.PENDING, description="Approval workflow status"
    )
    approval_date: datetime | None = Field(None, description="Date the adjustment was approved or rejected")
    effective_date: datetime | None = Field(None, description="Effective date for the adjustment")
    notes: str | None = Field(None, description="Additional notes about the adjustment")


class ReconciliationAuditEntry(BaseModel):
    """An audit trail entry for reconciliation activities."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique audit entry identifier")
    batch_id: str = Field(..., description="Associated reconciliation batch identifier")
    action: str = Field(..., description="Action performed (e.g., status_change, adjustment_created)")
    performed_by: str = Field(..., description="User who performed the action")
    performed_date: datetime = Field(..., description="Timestamp of the action")
    details: str = Field(..., description="Detailed description of the action")
    old_value: str | None = Field(None, description="Previous value before the change")
    new_value: str | None = Field(None, description="New value after the change")
    entity_type: str = Field(..., description="Type of entity affected (batch, site_recon, discrepancy, adjustment)")
    entity_id: str = Field(..., description="Identifier of the affected entity")


class FinancialClose(BaseModel):
    """A financial close record for a reconciliation period."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique financial close identifier")
    trial_id: str = Field(..., description="Associated clinical trial identifier")
    close_period: str = Field(..., description="Period label (e.g., '2026-Q1', '2025-12')")
    period_start: datetime = Field(..., description="Start date of the close period")
    period_end: datetime = Field(..., description="End date of the close period")
    status: ApprovalStatus = Field(
        default=ApprovalStatus.PENDING, description="Financial close approval status"
    )
    total_reconciled: float = Field(
        default=0.0, description="Total amount reconciled during the period"
    )
    total_adjustments: float = Field(
        default=0.0, description="Total adjustment amount applied during the period"
    )
    outstanding_discrepancies: int = Field(
        default=0, ge=0, description="Number of outstanding unresolved discrepancies"
    )
    closed_by: str | None = Field(None, description="User who closed the period")
    closed_date: datetime | None = Field(None, description="Date the period was closed")
    sign_off_cfo: str | None = Field(None, description="CFO sign-off name")
    sign_off_date: datetime | None = Field(None, description="Date of CFO sign-off")


# ---------------------------------------------------------------------------
# Metrics / dashboard
# ---------------------------------------------------------------------------


class ReconciliationMetrics(BaseModel):
    """Aggregated reconciliation operational metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_batches: int = Field(ge=0, description="Total reconciliation batches")
    pending_batches: int = Field(ge=0, description="Batches pending reconciliation")
    completed_batches: int = Field(ge=0, description="Batches fully reconciled or closed")
    total_site_reconciliations: int = Field(ge=0, description="Total site-level reconciliations")
    total_discrepancies: int = Field(ge=0, description="Total discrepancies identified")
    open_discrepancies: int = Field(ge=0, description="Unresolved discrepancies")
    resolved_discrepancies: int = Field(ge=0, description="Resolved discrepancies")
    total_adjustments: int = Field(ge=0, description="Total payment adjustments")
    pending_adjustments: int = Field(ge=0, description="Adjustments awaiting approval")
    approved_adjustments: int = Field(ge=0, description="Approved adjustments")
    total_adjustment_amount: float = Field(
        default=0.0, description="Sum of all approved adjustment amounts"
    )
    avg_auto_reconciled_pct: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Average auto-reconciliation percentage"
    )
    total_financial_closes: int = Field(ge=0, description="Total financial close records")
    open_financial_closes: int = Field(ge=0, description="Financial closes pending approval")
    total_audit_entries: int = Field(ge=0, description="Total audit trail entries")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class ReconciliationBatchCreate(BaseModel):
    """Request to create a new reconciliation batch."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    period_type: ReconciliationPeriod = Field(..., description="Reconciliation period type")
    period_start: datetime = Field(..., description="Period start date")
    period_end: datetime = Field(..., description="Period end date")
    initiated_by: str = Field(..., description="User initiating the reconciliation")


class ReconciliationBatchUpdate(BaseModel):
    """Request to update a reconciliation batch."""

    model_config = ConfigDict(from_attributes=True)

    status: ReconciliationStatus | None = Field(None, description="Batch status")
    notes: str | None = Field(None, description="Additional notes")


class SiteReconciliationCreate(BaseModel):
    """Request to create a site reconciliation record."""

    model_config = ConfigDict(from_attributes=True)

    batch_id: str = Field(..., description="Parent batch identifier")
    site_id: str = Field(..., description="Site identifier")
    site_name: str = Field(..., description="Site name")
    expected_amount: float = Field(..., description="Expected payment amount")
    actual_amount: float = Field(..., description="Actual payment amount")


class SiteReconciliationUpdate(BaseModel):
    """Request to update a site reconciliation record."""

    model_config = ConfigDict(from_attributes=True)

    expected_amount: float | None = Field(None, description="Expected amount")
    actual_amount: float | None = Field(None, description="Actual amount")
    status: ReconciliationStatus | None = Field(None, description="Status")
    reconciled_by: str | None = Field(None, description="Reconciled by")
    notes: str | None = Field(None, description="Notes")


class PaymentDiscrepancyCreate(BaseModel):
    """Request to flag a payment discrepancy."""

    model_config = ConfigDict(from_attributes=True)

    reconciliation_id: str = Field(..., description="Parent site reconciliation ID")
    site_id: str = Field(..., description="Site identifier")
    discrepancy_type: DiscrepancyType = Field(..., description="Discrepancy type")
    expected_amount: float = Field(..., description="Expected amount")
    actual_amount: float = Field(..., description="Actual amount")
    description: str = Field(..., description="Discrepancy description")
    assigned_to: str | None = Field(None, description="Assigned resolver")


class PaymentDiscrepancyUpdate(BaseModel):
    """Request to update a payment discrepancy."""

    model_config = ConfigDict(from_attributes=True)

    assigned_to: str | None = Field(None, description="Assigned resolver")
    resolution: str | None = Field(None, description="Resolution description")
    status: ReconciliationStatus | None = Field(None, description="Status")
    root_cause: str | None = Field(None, description="Root cause")


class PaymentAdjustmentCreate(BaseModel):
    """Request to create a payment adjustment."""

    model_config = ConfigDict(from_attributes=True)

    reconciliation_id: str = Field(..., description="Parent site reconciliation ID")
    site_id: str = Field(..., description="Site identifier")
    adjustment_type: AdjustmentType = Field(..., description="Adjustment type")
    amount: float = Field(..., gt=0, description="Adjustment amount (positive)")
    currency: str = Field(default="USD", description="Currency code")
    reason: str = Field(..., description="Reason for adjustment")
    reference_payment_id: str | None = Field(None, description="Reference payment ID")
    effective_date: datetime | None = Field(None, description="Effective date")
    notes: str | None = Field(None, description="Additional notes")


class AdjustmentApproval(BaseModel):
    """Request to approve or reject a payment adjustment."""

    model_config = ConfigDict(from_attributes=True)

    approval_status: ApprovalStatus = Field(..., description="Approval decision")
    approved_by: str = Field(..., description="Approver name")
    notes: str | None = Field(None, description="Approval notes")


class FinancialCloseRequest(BaseModel):
    """Request to close a financial period."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    close_period: str = Field(..., description="Period label (e.g., '2026-Q1')")
    period_start: datetime = Field(..., description="Period start date")
    period_end: datetime = Field(..., description="Period end date")
    closed_by: str = Field(..., description="User initiating the close")
    sign_off_cfo: str | None = Field(None, description="CFO sign-off name")


class AutoMatchRequest(BaseModel):
    """Request to auto-match payments within a batch."""

    model_config = ConfigDict(from_attributes=True)

    tolerance_pct: float = Field(
        default=1.0, ge=0.0, le=10.0,
        description="Percentage tolerance for auto-matching (0-10%)",
    )


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class ReconciliationBatchListResponse(BaseModel):
    """List of reconciliation batches."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ReconciliationBatch] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class SiteReconciliationListResponse(BaseModel):
    """List of site reconciliation records."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SiteReconciliation] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class PaymentDiscrepancyListResponse(BaseModel):
    """List of payment discrepancies."""

    model_config = ConfigDict(from_attributes=True)

    items: list[PaymentDiscrepancy] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class PaymentAdjustmentListResponse(BaseModel):
    """List of payment adjustments."""

    model_config = ConfigDict(from_attributes=True)

    items: list[PaymentAdjustment] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class ReconciliationAuditListResponse(BaseModel):
    """List of reconciliation audit entries."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ReconciliationAuditEntry] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class FinancialCloseListResponse(BaseModel):
    """List of financial close records."""

    model_config = ConfigDict(from_attributes=True)

    items: list[FinancialClose] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")
