"""Pydantic schemas for Budget Tracking & Approval Workflows (CFO-3).

Defines budget periods, allocations, spend requests, alerts, and metrics
for budget management in the clinical trial patient recruitment platform.

CFO-3: Budget Tracking & Approval Workflows
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class BudgetCategory(str, Enum):
    """Budget allocation category."""

    INFRASTRUCTURE = "INFRASTRUCTURE"
    PERSONNEL = "PERSONNEL"
    DATA_LICENSING = "DATA_LICENSING"
    COMPLIANCE = "COMPLIANCE"
    MARKETING = "MARKETING"
    RESEARCH = "RESEARCH"
    OPERATIONS = "OPERATIONS"
    PROFESSIONAL_SERVICES = "PROFESSIONAL_SERVICES"


class ApprovalStatus(str, Enum):
    """Status of a spend request in the approval workflow."""

    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVISION_REQUESTED = "REVISION_REQUESTED"


class SpendStatus(str, Enum):
    """Budget spend status indicating fiscal health."""

    WITHIN_BUDGET = "WITHIN_BUDGET"
    WARNING = "WARNING"  # >80% spent
    OVER_BUDGET = "OVER_BUDGET"
    FROZEN = "FROZEN"


class BudgetAlertType(str, Enum):
    """Types of budget alerts."""

    THRESHOLD_80 = "THRESHOLD_80"
    THRESHOLD_90 = "THRESHOLD_90"
    OVER_BUDGET = "OVER_BUDGET"
    LARGE_SPEND = "LARGE_SPEND"


# ---------------------------------------------------------------------------
# Budget Period
# ---------------------------------------------------------------------------


class BudgetPeriod(BaseModel):
    """A fiscal budget period (quarter)."""

    id: str = Field(..., description="Unique period identifier")
    fiscal_year: int = Field(..., description="Fiscal year (e.g. 2025)")
    quarter: str = Field(..., description="Quarter (Q1, Q2, Q3, Q4)")
    total_budget: float = Field(..., description="Total budget for the period")
    total_allocated: float = Field(
        default=0.0, description="Total allocated across categories"
    )
    total_spent: float = Field(default=0.0, description="Total spent to date")
    remaining: float = Field(default=0.0, description="Remaining budget")
    status: SpendStatus = Field(
        default=SpendStatus.WITHIN_BUDGET, description="Current spend status"
    )


# ---------------------------------------------------------------------------
# Budget Allocation
# ---------------------------------------------------------------------------


class BudgetAllocation(BaseModel):
    """Budget allocation for a specific category within a period."""

    id: str = Field(..., description="Unique allocation identifier")
    period_id: str = Field(..., description="Associated budget period ID")
    category: BudgetCategory = Field(..., description="Budget category")
    allocated_amount: float = Field(
        ..., description="Amount allocated for this category"
    )
    spent_amount: float = Field(default=0.0, description="Amount spent to date")
    remaining: float = Field(default=0.0, description="Remaining allocation")
    committed: float = Field(
        default=0.0,
        description="Amount committed via POs issued but not yet paid",
    )
    variance_pct: float = Field(
        default=0.0,
        description="Variance percentage ((spent - allocated) / allocated * 100)",
    )
    owner: str = Field(default="", description="Budget owner / department head")


# ---------------------------------------------------------------------------
# Spend Request
# ---------------------------------------------------------------------------


class SpendRequest(BaseModel):
    """A request to spend against a budget allocation."""

    id: str = Field(..., description="Unique spend request identifier")
    allocation_id: str = Field(..., description="Associated allocation ID")
    title: str = Field(..., description="Short title for the spend request")
    description: str = Field(default="", description="Detailed description")
    amount: float = Field(..., description="Requested spend amount in USD")
    requested_by: str = Field(..., description="Person who submitted the request")
    requested_date: datetime = Field(
        ..., description="Date/time the request was submitted"
    )
    status: ApprovalStatus = Field(
        default=ApprovalStatus.DRAFT, description="Current approval status"
    )
    approver: str | None = Field(
        default=None, description="Person who approved/rejected"
    )
    approved_date: datetime | None = Field(
        default=None, description="Date/time of approval or rejection"
    )
    rejection_reason: str | None = Field(
        default=None, description="Reason for rejection"
    )
    vendor: str = Field(default="", description="Vendor name for the spend")
    invoice_ref: str = Field(default="", description="Invoice or PO reference number")


# ---------------------------------------------------------------------------
# Spend Request Create / Update
# ---------------------------------------------------------------------------


class SpendRequestCreate(BaseModel):
    """Request to create a new spend request."""

    allocation_id: str = Field(..., description="Target allocation ID")
    title: str = Field(..., description="Short title")
    description: str = Field(default="", description="Detailed description")
    amount: float = Field(..., description="Requested amount in USD")
    requested_by: str = Field(..., description="Requester name")
    vendor: str = Field(default="", description="Vendor name")
    invoice_ref: str = Field(default="", description="Invoice or PO reference")


class SpendRequestUpdate(BaseModel):
    """Request to update an existing spend request."""

    title: str | None = Field(default=None, description="Updated title")
    description: str | None = Field(default=None, description="Updated description")
    amount: float | None = Field(default=None, description="Updated amount")
    vendor: str | None = Field(default=None, description="Updated vendor")
    invoice_ref: str | None = Field(default=None, description="Updated invoice ref")


# ---------------------------------------------------------------------------
# Budget Alert
# ---------------------------------------------------------------------------


class BudgetAlert(BaseModel):
    """An alert triggered by a budget threshold breach."""

    id: str = Field(..., description="Unique alert identifier")
    allocation_id: str = Field(..., description="Associated allocation ID")
    alert_type: BudgetAlertType = Field(..., description="Type of alert")
    message: str = Field(..., description="Human-readable alert message")
    triggered_at: datetime = Field(
        ..., description="When the alert was triggered"
    )
    acknowledged: bool = Field(
        default=False, description="Whether the alert has been acknowledged"
    )


# ---------------------------------------------------------------------------
# Budget Metrics
# ---------------------------------------------------------------------------


class BudgetMetrics(BaseModel):
    """Aggregated budget dashboard metrics."""

    total_annual_budget: float = Field(
        ..., description="Total annual budget across all periods"
    )
    total_spent_ytd: float = Field(
        ..., description="Total spent year-to-date"
    )
    burn_rate_monthly: float = Field(
        ..., description="Average monthly burn rate"
    )
    projected_annual_spend: float = Field(
        ..., description="Projected annual spend based on burn rate"
    )
    budget_utilization_pct: float = Field(
        ..., description="Budget utilization percentage"
    )
    by_category: dict[str, float] = Field(
        ..., description="Spend by category"
    )
    pending_approvals_count: int = Field(
        ..., description="Number of pending approval requests"
    )
    pending_approvals_amount: float = Field(
        ..., description="Total amount of pending approvals"
    )
    over_budget_categories: list[str] = Field(
        ..., description="Categories that are over budget"
    )


# ---------------------------------------------------------------------------
# Spend Forecast
# ---------------------------------------------------------------------------


class SpendForecast(BaseModel):
    """Spend projection over future months."""

    months_ahead: int = Field(..., description="Number of months projected")
    current_monthly_burn: float = Field(
        ..., description="Current monthly burn rate"
    )
    projected_total: float = Field(
        ..., description="Projected total spend over the forecast period"
    )
    projected_remaining: float = Field(
        ..., description="Projected remaining budget after forecast period"
    )
    will_exceed_budget: bool = Field(
        ..., description="Whether spend will exceed budget"
    )
    months_until_exhausted: float | None = Field(
        default=None,
        description="Estimated months until budget is exhausted (None if not projected)",
    )


# ---------------------------------------------------------------------------
# Record Spend Request
# ---------------------------------------------------------------------------


class RecordSpendInput(BaseModel):
    """Input for directly recording a spend against an allocation."""

    amount: float = Field(..., description="Amount spent")
    vendor: str = Field(default="", description="Vendor name")
    invoice_ref: str = Field(default="", description="Invoice reference")
    description: str = Field(default="", description="Spend description")


# ---------------------------------------------------------------------------
# Approval / Rejection Inputs
# ---------------------------------------------------------------------------


class ApprovalInput(BaseModel):
    """Input for approving a spend request."""

    approver: str = Field(..., description="Name of the approver")


class RejectionInput(BaseModel):
    """Input for rejecting a spend request."""

    approver: str = Field(..., description="Name of the person rejecting")
    reason: str = Field(..., description="Reason for rejection")


# ---------------------------------------------------------------------------
# Response Wrappers
# ---------------------------------------------------------------------------


class BudgetPeriodListResponse(BaseModel):
    """List response for budget periods."""

    items: list[BudgetPeriod] = Field(..., description="Budget periods")
    total: int = Field(..., description="Total count")


class AllocationListResponse(BaseModel):
    """List response for budget allocations."""

    items: list[BudgetAllocation] = Field(..., description="Allocations")
    total: int = Field(..., description="Total count")


class SpendRequestListResponse(BaseModel):
    """List response for spend requests."""

    items: list[SpendRequest] = Field(..., description="Spend requests")
    total: int = Field(..., description="Total count")


class AlertListResponse(BaseModel):
    """List response for budget alerts."""

    items: list[BudgetAlert] = Field(..., description="Budget alerts")
    total: int = Field(..., description="Total count")
