"""Pydantic v2 schemas for CFO-4: Invoice Management & Contract Billing.

Defines schemas for invoices, line items, payment records, billing contracts,
milestones, AR aging, revenue recognition, and financial metrics for the
clinical trial patient recruitment platform.

CFO-4: Invoice Management & Contract Billing
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class InvoiceStatus(str, Enum):
    """Lifecycle status of an invoice."""

    DRAFT = "DRAFT"
    SENT = "SENT"
    VIEWED = "VIEWED"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    OVERDUE = "OVERDUE"
    DISPUTED = "DISPUTED"
    CANCELLED = "CANCELLED"
    WRITTEN_OFF = "WRITTEN_OFF"


class BillingModel(str, Enum):
    """Contract billing model type."""

    SUBSCRIPTION = "SUBSCRIPTION"
    PER_PATIENT = "PER_PATIENT"
    DATA_LICENSING = "DATA_LICENSING"
    MILESTONE = "MILESTONE"
    USAGE_BASED = "USAGE_BASED"
    HYBRID = "HYBRID"


class PaymentMethod(str, Enum):
    """Accepted payment methods."""

    WIRE_TRANSFER = "WIRE_TRANSFER"
    ACH = "ACH"
    CREDIT_CARD = "CREDIT_CARD"
    CHECK = "CHECK"


class PaymentTerms(str, Enum):
    """Payment term options (net days)."""

    NET_15 = "NET_15"
    NET_30 = "NET_30"
    NET_45 = "NET_45"
    NET_60 = "NET_60"
    NET_90 = "NET_90"


class LineItemType(str, Enum):
    """Types of invoice line items."""

    PLATFORM_FEE = "PLATFORM_FEE"
    PER_PATIENT_SCREENING = "PER_PATIENT_SCREENING"
    DATA_ACCESS = "DATA_ACCESS"
    ANALYTICS = "ANALYTICS"
    PROFESSIONAL_SERVICES = "PROFESSIONAL_SERVICES"
    SETUP_FEE = "SETUP_FEE"
    CUSTOM = "CUSTOM"


class Currency(str, Enum):
    """Supported currencies."""

    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    CHF = "CHF"


# ---------------------------------------------------------------------------
# Invoice Line Item
# ---------------------------------------------------------------------------


class InvoiceLineItem(BaseModel):
    """A single line item on an invoice."""

    id: str = Field(..., description="Unique line item identifier")
    invoice_id: str = Field(..., description="Parent invoice ID")
    line_item_type: LineItemType = Field(..., description="Type of line item")
    description: str = Field(..., description="Line item description")
    quantity: float = Field(..., description="Quantity of units")
    unit_price: float = Field(..., description="Price per unit")
    amount: float = Field(..., description="Subtotal (quantity * unit_price)")
    tax_rate: float = Field(default=0.0, description="Tax rate as decimal (e.g. 0.08)")
    tax_amount: float = Field(default=0.0, description="Tax amount")
    total: float = Field(..., description="Total including tax")


# ---------------------------------------------------------------------------
# Invoice
# ---------------------------------------------------------------------------


class Invoice(BaseModel):
    """An invoice issued to a client."""

    id: str = Field(..., description="Unique invoice identifier")
    invoice_number: str = Field(..., description="Human-readable invoice number (e.g. INV-2026-0001)")
    client_id: str = Field(..., description="Client / sponsor identifier")
    client_name: str = Field(..., description="Client / sponsor name")
    contract_id: str | None = Field(default=None, description="Associated billing contract ID")
    status: InvoiceStatus = Field(default=InvoiceStatus.DRAFT, description="Invoice status")
    billing_model: BillingModel = Field(..., description="Billing model for this invoice")
    line_items: list[InvoiceLineItem] = Field(default_factory=list, description="Line items")
    subtotal: float = Field(default=0.0, description="Subtotal before tax")
    tax_total: float = Field(default=0.0, description="Total tax amount")
    total: float = Field(default=0.0, description="Grand total")
    currency: Currency = Field(default=Currency.USD, description="Invoice currency")
    issued_date: date | None = Field(default=None, description="Date invoice was issued")
    due_date: date | None = Field(default=None, description="Payment due date")
    paid_date: date | None = Field(default=None, description="Date fully paid")
    payment_terms: PaymentTerms = Field(default=PaymentTerms.NET_30, description="Payment terms")
    payment_method: PaymentMethod | None = Field(default=None, description="Payment method used")
    notes: str = Field(default="", description="Additional notes")
    po_number: str | None = Field(default=None, description="Client purchase order number")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record last-updated timestamp")


# ---------------------------------------------------------------------------
# Payment Record
# ---------------------------------------------------------------------------


class PaymentRecord(BaseModel):
    """Record of a payment received against an invoice."""

    id: str = Field(..., description="Unique payment record identifier")
    invoice_id: str = Field(..., description="Associated invoice ID")
    amount: float = Field(..., description="Payment amount")
    payment_method: PaymentMethod = Field(..., description="Payment method used")
    reference_number: str = Field(default="", description="External payment reference / check number")
    received_date: date = Field(..., description="Date payment was received")
    processed_by: str = Field(default="", description="Person who processed the payment")


# ---------------------------------------------------------------------------
# Billing Milestone
# ---------------------------------------------------------------------------


class BillingMilestone(BaseModel):
    """A milestone within a billing contract (milestone-based billing)."""

    name: str = Field(..., description="Milestone name")
    amount: float = Field(..., description="Milestone payment amount")
    target_date: date = Field(..., description="Target completion date")
    completed: bool = Field(default=False, description="Whether milestone is completed")
    invoice_id: str | None = Field(default=None, description="Invoice ID if billed")


# ---------------------------------------------------------------------------
# Billing Contract
# ---------------------------------------------------------------------------


class BillingContract(BaseModel):
    """A billing contract / master service agreement with a client."""

    id: str = Field(..., description="Unique contract identifier")
    client_id: str = Field(..., description="Client / sponsor identifier")
    client_name: str = Field(..., description="Client / sponsor name")
    billing_model: BillingModel = Field(..., description="Billing model")
    start_date: date = Field(..., description="Contract start date")
    end_date: date = Field(..., description="Contract end date")
    monthly_fee: float = Field(default=0.0, description="Monthly subscription fee")
    per_patient_rate: float = Field(default=0.0, description="Per-patient screening rate")
    data_licensing_fee: float = Field(default=0.0, description="Monthly data licensing fee")
    payment_terms: PaymentTerms = Field(default=PaymentTerms.NET_30, description="Payment terms")
    auto_invoice: bool = Field(default=False, description="Auto-generate invoices")
    milestones: list[BillingMilestone] = Field(default_factory=list, description="Milestones (milestone-based)")
    total_value: float = Field(default=0.0, description="Total contract value")
    invoiced_to_date: float = Field(default=0.0, description="Total amount invoiced so far")


# ---------------------------------------------------------------------------
# AR Aging
# ---------------------------------------------------------------------------


class ARAgingBucket(BaseModel):
    """Accounts receivable aging bucket."""

    bucket: str = Field(..., description="Aging bucket label (e.g. '0-30 days')")
    count: int = Field(..., description="Number of invoices in this bucket")
    total_amount: float = Field(..., description="Total outstanding amount")


# ---------------------------------------------------------------------------
# Revenue Recognition
# ---------------------------------------------------------------------------


class RevenueRecognition(BaseModel):
    """Revenue recognition entry (ASC 606 compliant)."""

    period: str = Field(..., description="Reporting period (e.g. '2026-01')")
    recognized_revenue: float = Field(..., description="Revenue recognized in this period")
    deferred_revenue: float = Field(..., description="Revenue deferred to future periods")
    total_billed: float = Field(..., description="Total billed in this period")
    asc606_compliant: bool = Field(default=True, description="Whether ASC 606 compliant")


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------


class InvoiceLineItemCreate(BaseModel):
    """Request body for creating an invoice line item."""

    line_item_type: LineItemType = Field(..., description="Type of line item")
    description: str = Field(..., description="Line item description")
    quantity: float = Field(..., description="Quantity")
    unit_price: float = Field(..., description="Unit price")
    tax_rate: float = Field(default=0.0, description="Tax rate as decimal")


class InvoiceCreateRequest(BaseModel):
    """Request body for creating a new invoice."""

    client_id: str = Field(..., description="Client identifier")
    client_name: str = Field(..., description="Client name")
    contract_id: str | None = Field(default=None, description="Associated contract ID")
    billing_model: BillingModel = Field(..., description="Billing model")
    line_items: list[InvoiceLineItemCreate] = Field(default_factory=list, description="Line items")
    currency: Currency = Field(default=Currency.USD, description="Currency")
    payment_terms: PaymentTerms = Field(default=PaymentTerms.NET_30, description="Payment terms")
    notes: str = Field(default="", description="Notes")
    po_number: str | None = Field(default=None, description="PO number")
    issued_date: date | None = Field(default=None, description="Issue date")
    due_date: date | None = Field(default=None, description="Due date")


class InvoiceUpdateRequest(BaseModel):
    """Request body for updating an existing invoice."""

    status: InvoiceStatus | None = Field(default=None, description="New status")
    notes: str | None = Field(default=None, description="Updated notes")
    po_number: str | None = Field(default=None, description="Updated PO number")
    payment_method: PaymentMethod | None = Field(default=None, description="Payment method")
    due_date: date | None = Field(default=None, description="Updated due date")


class InvoiceListResponse(BaseModel):
    """Paginated list of invoices."""

    items: list[Invoice] = Field(..., description="Invoice records")
    total: int = Field(..., description="Total count")


class PaymentRecordRequest(BaseModel):
    """Request body for recording a payment."""

    amount: float = Field(..., description="Payment amount")
    payment_method: PaymentMethod = Field(..., description="Payment method")
    reference_number: str = Field(default="", description="External reference")
    received_date: date | None = Field(default=None, description="Date received")
    processed_by: str = Field(default="", description="Processor name")


class BillingContractCreateRequest(BaseModel):
    """Request body for creating a billing contract."""

    client_id: str = Field(..., description="Client identifier")
    client_name: str = Field(..., description="Client name")
    billing_model: BillingModel = Field(..., description="Billing model")
    start_date: date = Field(..., description="Start date")
    end_date: date = Field(..., description="End date")
    monthly_fee: float = Field(default=0.0, description="Monthly fee")
    per_patient_rate: float = Field(default=0.0, description="Per-patient rate")
    data_licensing_fee: float = Field(default=0.0, description="Data licensing fee")
    payment_terms: PaymentTerms = Field(default=PaymentTerms.NET_30, description="Payment terms")
    auto_invoice: bool = Field(default=False, description="Auto-invoice flag")
    milestones: list[BillingMilestone] = Field(default_factory=list, description="Milestones")
    total_value: float = Field(default=0.0, description="Total contract value")


class BillingContractListResponse(BaseModel):
    """Paginated list of billing contracts."""

    items: list[BillingContract] = Field(..., description="Contracts")
    total: int = Field(..., description="Total count")


class InvoiceMetrics(BaseModel):
    """Aggregated invoice / billing metrics."""

    total_billed: float = Field(..., description="Total amount billed across all invoices")
    total_collected: float = Field(..., description="Total amount collected (payments received)")
    total_outstanding: float = Field(..., description="Total outstanding (billed - collected)")
    days_sales_outstanding: float = Field(..., description="Days sales outstanding (DSO)")
    invoices_by_status: dict[str, int] = Field(
        ..., description="Count of invoices by status"
    )
    collection_rate: float = Field(..., description="Collection rate percentage")
    overdue_count: int = Field(..., description="Number of overdue invoices")
    overdue_amount: float = Field(..., description="Total overdue amount")
    average_invoice_amount: float = Field(..., description="Average invoice amount")
    average_days_to_pay: float = Field(..., description="Average days to payment")


class ARAgingReport(BaseModel):
    """Full accounts receivable aging report."""

    buckets: list[ARAgingBucket] = Field(..., description="Aging buckets")
    total_outstanding: float = Field(..., description="Total AR outstanding")
    total_overdue: float = Field(..., description="Total overdue amount")
    generated_at: datetime = Field(..., description="Report generation timestamp")


class RevenueReport(BaseModel):
    """Revenue recognition report."""

    periods: list[RevenueRecognition] = Field(..., description="Revenue by period")
    total_recognized: float = Field(..., description="Total recognized revenue")
    total_deferred: float = Field(..., description="Total deferred revenue")
    total_billed: float = Field(..., description="Total billed")
    asc606_compliant: bool = Field(default=True, description="Overall ASC 606 compliance")
    generated_at: datetime = Field(..., description="Report generation timestamp")


class ThreeWayMatchResult(BaseModel):
    """Result of a 3-way match (PO + Contract + Invoice)."""

    invoice_id: str = Field(..., description="Invoice ID")
    po_number: str | None = Field(default=None, description="PO number")
    contract_id: str | None = Field(default=None, description="Contract ID")
    po_match: bool = Field(..., description="Whether PO number is present")
    contract_match: bool = Field(..., description="Whether contract is linked and valid")
    amount_match: bool = Field(..., description="Whether amounts are consistent")
    fully_matched: bool = Field(..., description="Whether all 3 checks pass")
    discrepancies: list[str] = Field(default_factory=list, description="List of discrepancies found")


class LateFeeCalculation(BaseModel):
    """Late fee calculation for an overdue invoice."""

    invoice_id: str = Field(..., description="Invoice ID")
    invoice_number: str = Field(..., description="Invoice number")
    original_amount: float = Field(..., description="Original invoice amount")
    days_overdue: int = Field(..., description="Number of days overdue")
    monthly_rate: float = Field(..., description="Monthly late fee rate")
    late_fee: float = Field(..., description="Calculated late fee amount")
    total_with_late_fee: float = Field(..., description="Total including late fee")
