"""Pydantic schemas for Clinical Site Payments & Grant Management (CLINICAL-21).

Manages site payment operations: grant definitions, payment line items (per-patient,
milestone, startup, annual, screen failure, protocol deviation credit, pass-through,
holdback release), invoice lifecycle, payment summaries per site, and aggregated
payment metrics across the trial portfolio.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PaymentType(str, Enum):
    """Type of payment line item."""

    PER_PATIENT = "per_patient"
    MILESTONE = "milestone"
    STARTUP_FEE = "startup_fee"
    ANNUAL_FEE = "annual_fee"
    SCREEN_FAILURE_FEE = "screen_failure_fee"
    PROTOCOL_DEVIATION_CREDIT = "protocol_deviation_credit"
    PASS_THROUGH = "pass_through"
    HOLDBACK_RELEASE = "holdback_release"


class PaymentStatus(str, Enum):
    """Lifecycle status of a payment line item or invoice."""

    ACCRUED = "accrued"
    INVOICE_RECEIVED = "invoice_received"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    PAID = "paid"
    DISPUTED = "disputed"
    WRITTEN_OFF = "written_off"


class CurrencyCode(str, Enum):
    """Supported currency codes."""

    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    AUD = "AUD"
    CAD = "CAD"


class PaymentScheduleType(str, Enum):
    """Frequency of payment schedule."""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    UPON_COMPLETION = "upon_completion"
    UPON_MILESTONE = "upon_milestone"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class SiteGrant(BaseModel):
    """A grant agreement defining payment terms for a clinical trial site."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique grant identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    site_id: str = Field(..., description="Site identifier")
    site_name: str = Field(..., description="Site display name")
    total_budget: float = Field(..., ge=0.0, description="Total grant budget amount")
    currency: CurrencyCode = Field(default=CurrencyCode.USD, description="Currency for all amounts")
    payment_schedule_type: PaymentScheduleType = Field(
        ..., description="Payment schedule frequency"
    )
    per_patient_amount: float = Field(default=0.0, ge=0.0, description="Per-patient payment amount")
    screen_failure_amount: float = Field(
        default=0.0, ge=0.0, description="Screen failure reimbursement amount"
    )
    startup_fee: float = Field(default=0.0, ge=0.0, description="One-time startup fee")
    annual_fee: float = Field(default=0.0, ge=0.0, description="Annual site maintenance fee")
    holdback_pct: float = Field(
        default=10.0, ge=0.0, le=100.0, description="Holdback percentage (released at study end)"
    )
    effective_date: datetime = Field(..., description="Grant effective date")
    end_date: datetime | None = Field(None, description="Grant end date")
    amendment_count: int = Field(default=0, ge=0, description="Number of grant amendments")


class PaymentLineItem(BaseModel):
    """A single payment line item within a grant."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique line item identifier")
    grant_id: str = Field(..., description="Associated grant identifier")
    site_id: str = Field(..., description="Site identifier")
    patient_id: str | None = Field(None, description="Patient identifier (for per-patient payments)")
    payment_type: PaymentType = Field(..., description="Type of payment")
    description: str = Field(..., description="Line item description")
    amount: float = Field(..., description="Payment amount")
    currency: CurrencyCode = Field(default=CurrencyCode.USD, description="Currency code")
    accrual_date: datetime = Field(..., description="Date the payment was accrued")
    invoice_date: datetime | None = Field(None, description="Date invoiced")
    payment_date: datetime | None = Field(None, description="Date paid")
    status: PaymentStatus = Field(default=PaymentStatus.ACCRUED, description="Payment status")
    visit_number: int | None = Field(None, ge=0, description="Visit number (for per-patient payments)")


class Invoice(BaseModel):
    """An invoice submitted by a site for a billing period."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique invoice identifier")
    site_id: str = Field(..., description="Site identifier")
    trial_id: str = Field(..., description="Trial identifier")
    invoice_number: str = Field(..., description="Site-provided invoice number")
    period_start: datetime = Field(..., description="Billing period start date")
    period_end: datetime = Field(..., description="Billing period end date")
    line_items: list[str] = Field(
        default_factory=list, description="List of payment line item IDs"
    )
    subtotal: float = Field(default=0.0, description="Subtotal before tax")
    tax: float = Field(default=0.0, ge=0.0, description="Tax amount")
    total: float = Field(default=0.0, description="Total invoice amount")
    status: PaymentStatus = Field(
        default=PaymentStatus.INVOICE_RECEIVED, description="Invoice status"
    )
    submitted_date: datetime = Field(..., description="Date invoice was submitted")
    approved_date: datetime | None = Field(None, description="Date invoice was approved")
    paid_date: datetime | None = Field(None, description="Date invoice was paid")


class SitePaymentSummary(BaseModel):
    """Aggregated payment summary for a single site."""

    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., description="Site identifier")
    site_name: str = Field(..., description="Site display name")
    total_accrued: float = Field(default=0.0, description="Total amount accrued")
    total_invoiced: float = Field(default=0.0, description="Total amount invoiced")
    total_paid: float = Field(default=0.0, description="Total amount paid")
    total_outstanding: float = Field(default=0.0, description="Total outstanding amount")
    holdback_amount: float = Field(default=0.0, description="Total holdback amount retained")
    patients_enrolled: int = Field(default=0, ge=0, description="Number of enrolled patients")
    payments_by_type: dict[str, float] = Field(
        default_factory=dict, description="Payment totals grouped by payment type"
    )


class PaymentMetrics(BaseModel):
    """Aggregated payment metrics across all grants and sites."""

    model_config = ConfigDict(from_attributes=True)

    total_grants: int = Field(default=0, ge=0, description="Total number of active grants")
    total_accrued_amount: float = Field(default=0.0, description="Total accrued across all sites")
    total_paid_amount: float = Field(default=0.0, description="Total paid across all sites")
    avg_payment_cycle_days: float = Field(
        default=0.0, ge=0.0, description="Average days from accrual to payment"
    )
    sites_with_outstanding: int = Field(
        default=0, ge=0, description="Number of sites with outstanding payments"
    )
    overdue_payments: int = Field(default=0, ge=0, description="Number of overdue payment line items")
    holdback_total: float = Field(default=0.0, description="Total holdback amount across all sites")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class SiteGrantCreate(BaseModel):
    """Request to create a new site grant."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    site_id: str = Field(..., description="Site identifier")
    site_name: str = Field(..., description="Site display name")
    total_budget: float = Field(..., ge=0.0, description="Total grant budget")
    currency: CurrencyCode = Field(default=CurrencyCode.USD, description="Currency")
    payment_schedule_type: PaymentScheduleType = Field(..., description="Payment schedule")
    per_patient_amount: float = Field(default=0.0, ge=0.0, description="Per-patient amount")
    screen_failure_amount: float = Field(default=0.0, ge=0.0, description="Screen failure amount")
    startup_fee: float = Field(default=0.0, ge=0.0, description="Startup fee")
    annual_fee: float = Field(default=0.0, ge=0.0, description="Annual fee")
    holdback_pct: float = Field(default=10.0, ge=0.0, le=100.0, description="Holdback percentage")
    effective_date: datetime = Field(..., description="Effective date")
    end_date: datetime | None = Field(None, description="End date")


class SiteGrantUpdate(BaseModel):
    """Request to update a site grant."""

    model_config = ConfigDict(from_attributes=True)

    total_budget: float | None = Field(None, ge=0.0, description="Total budget")
    per_patient_amount: float | None = Field(None, ge=0.0, description="Per-patient amount")
    screen_failure_amount: float | None = Field(None, ge=0.0, description="Screen failure amount")
    startup_fee: float | None = Field(None, ge=0.0, description="Startup fee")
    annual_fee: float | None = Field(None, ge=0.0, description="Annual fee")
    holdback_pct: float | None = Field(None, ge=0.0, le=100.0, description="Holdback pct")
    payment_schedule_type: PaymentScheduleType | None = Field(None, description="Schedule type")
    end_date: datetime | None = Field(None, description="End date")


class PaymentLineItemCreate(BaseModel):
    """Request to create a payment line item."""

    model_config = ConfigDict(from_attributes=True)

    grant_id: str = Field(..., description="Grant identifier")
    site_id: str = Field(..., description="Site identifier")
    patient_id: str | None = Field(None, description="Patient identifier")
    payment_type: PaymentType = Field(..., description="Payment type")
    description: str = Field(..., description="Description")
    amount: float = Field(..., description="Amount")
    currency: CurrencyCode = Field(default=CurrencyCode.USD, description="Currency")
    accrual_date: datetime = Field(..., description="Accrual date")
    visit_number: int | None = Field(None, ge=0, description="Visit number")


class PaymentLineItemUpdate(BaseModel):
    """Request to update a payment line item."""

    model_config = ConfigDict(from_attributes=True)

    status: PaymentStatus | None = Field(None, description="Payment status")
    invoice_date: datetime | None = Field(None, description="Invoice date")
    payment_date: datetime | None = Field(None, description="Payment date")
    description: str | None = Field(None, description="Description")
    amount: float | None = Field(None, description="Amount")


class InvoiceCreate(BaseModel):
    """Request to create an invoice."""

    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., description="Site identifier")
    trial_id: str = Field(..., description="Trial identifier")
    invoice_number: str = Field(..., description="Invoice number")
    period_start: datetime = Field(..., description="Period start")
    period_end: datetime = Field(..., description="Period end")
    line_item_ids: list[str] = Field(default_factory=list, description="Line item IDs to include")
    tax: float = Field(default=0.0, ge=0.0, description="Tax amount")


class InvoiceUpdate(BaseModel):
    """Request to update an invoice."""

    model_config = ConfigDict(from_attributes=True)

    status: PaymentStatus | None = Field(None, description="Invoice status")
    tax: float | None = Field(None, ge=0.0, description="Tax amount")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class SiteGrantListResponse(BaseModel):
    """List of site grants."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SiteGrant] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class PaymentLineItemListResponse(BaseModel):
    """List of payment line items."""

    model_config = ConfigDict(from_attributes=True)

    items: list[PaymentLineItem] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class InvoiceListResponse(BaseModel):
    """List of invoices."""

    model_config = ConfigDict(from_attributes=True)

    items: list[Invoice] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class SitePaymentSummaryListResponse(BaseModel):
    """List of site payment summaries."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SitePaymentSummary] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")
