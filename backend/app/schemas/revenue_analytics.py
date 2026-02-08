"""Pydantic v2 schemas for CFO-2: Revenue Analytics & Financial Reporting.

Defines schemas for revenue contracts, monthly revenue tracking, SaaS
metrics (MRR, ARR, NRR, LTV/CAC), sponsor cohort analysis, revenue
forecasting with confidence intervals, and P&L-style financial reports.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RevenueStream(str, Enum):
    """Revenue stream categories for the platform."""

    PLATFORM_LICENSE = "platform_license"
    PER_PATIENT_SCREENING = "per_patient_screening"
    PER_ENROLLMENT = "per_enrollment"
    DATA_ANALYTICS = "data_analytics"
    INTEGRATION_FEES = "integration_fees"
    PROFESSIONAL_SERVICES = "professional_services"


class ContractStatus(str, Enum):
    """Lifecycle status for a revenue contract."""

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    EXPIRED = "expired"
    TERMINATED = "terminated"


class ReportType(str, Enum):
    """Financial report cadence."""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


# ---------------------------------------------------------------------------
# Revenue Contract
# ---------------------------------------------------------------------------


class RevenueContract(BaseModel):
    """A revenue contract with a pharma sponsor."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique contract identifier")
    sponsor_name: str = Field(..., description="Pharma sponsor name")
    trial_id: str = Field(..., description="Associated trial identifier")
    stream: RevenueStream = Field(..., description="Primary revenue stream")
    status: ContractStatus = Field(default=ContractStatus.DRAFT)
    monthly_base_fee: float = Field(default=0.0, ge=0, description="Monthly platform license fee ($)")
    per_patient_fee: float = Field(default=0.0, ge=0, description="Fee per patient screened ($)")
    per_enrollment_fee: float = Field(default=0.0, ge=0, description="Fee per patient enrolled ($)")
    start_date: date = Field(..., description="Contract start date")
    end_date: date = Field(..., description="Contract end date")
    total_contract_value: float = Field(default=0.0, ge=0, description="Total contract value ($)")
    recognized_revenue: float = Field(default=0.0, ge=0, description="Revenue recognized to date ($)")
    remaining_value: float = Field(default=0.0, ge=0, description="Remaining contract value ($)")
    created_at: datetime = Field(..., description="Record creation timestamp")


class RevenueContractCreate(BaseModel):
    """Request body to create a new revenue contract."""

    model_config = ConfigDict(from_attributes=True)

    sponsor_name: str
    trial_id: str
    stream: RevenueStream
    status: ContractStatus = ContractStatus.DRAFT
    monthly_base_fee: float = Field(default=0.0, ge=0)
    per_patient_fee: float = Field(default=0.0, ge=0)
    per_enrollment_fee: float = Field(default=0.0, ge=0)
    start_date: date
    end_date: date
    total_contract_value: float = Field(default=0.0, ge=0)


class RevenueContractUpdate(BaseModel):
    """Request body to update a revenue contract."""

    model_config = ConfigDict(from_attributes=True)

    sponsor_name: str | None = None
    trial_id: str | None = None
    stream: RevenueStream | None = None
    status: ContractStatus | None = None
    monthly_base_fee: float | None = Field(default=None, ge=0)
    per_patient_fee: float | None = Field(default=None, ge=0)
    per_enrollment_fee: float | None = Field(default=None, ge=0)
    start_date: date | None = None
    end_date: date | None = None
    total_contract_value: float | None = Field(default=None, ge=0)


class RevenueContractListResponse(BaseModel):
    """Paginated contract list response."""

    total: int = 0
    contracts: list[RevenueContract] = []


# ---------------------------------------------------------------------------
# Monthly Revenue
# ---------------------------------------------------------------------------


class MonthlyRevenue(BaseModel):
    """Revenue breakdown for a single month."""

    model_config = ConfigDict(from_attributes=True)

    month: str = Field(..., description="Month in YYYY-MM format")
    total: float = Field(default=0.0, description="Total revenue for the month ($)")
    by_stream: dict[str, float] = Field(default_factory=dict, description="Revenue breakdown by stream")
    by_sponsor: dict[str, float] = Field(default_factory=dict, description="Revenue breakdown by sponsor")
    patient_volume: int = Field(default=0, description="Number of patients screened")
    enrollment_volume: int = Field(default=0, description="Number of patients enrolled")


class MonthlyRevenueListResponse(BaseModel):
    """List of monthly revenue records."""

    total: int = 0
    months: list[MonthlyRevenue] = []


# ---------------------------------------------------------------------------
# Cohort Analysis
# ---------------------------------------------------------------------------


class CohortAnalysis(BaseModel):
    """Sponsor cohort retention analysis for a given acquisition quarter."""

    model_config = ConfigDict(from_attributes=True)

    cohort_month: str = Field(..., description="Cohort month (YYYY-MM)")
    sponsors_acquired: int = Field(default=0, description="Number of sponsors acquired in this cohort")
    total_contract_value: float = Field(default=0.0, description="Total contract value for cohort ($)")
    month_1_retention: float = Field(default=1.0, ge=0, le=1, description="Retention rate at month 1")
    month_3_retention: float = Field(default=1.0, ge=0, le=1, description="Retention rate at month 3")
    month_6_retention: float = Field(default=1.0, ge=0, le=1, description="Retention rate at month 6")
    month_12_retention: float = Field(default=1.0, ge=0, le=1, description="Retention rate at month 12")
    avg_revenue_per_sponsor: float = Field(default=0.0, description="Average revenue per sponsor ($)")
    churn_rate: float = Field(default=0.0, ge=0, le=1, description="Churn rate for cohort")


class CohortAnalysisListResponse(BaseModel):
    """List of cohort analysis records."""

    total: int = 0
    cohorts: list[CohortAnalysis] = []


# ---------------------------------------------------------------------------
# Revenue Forecast
# ---------------------------------------------------------------------------


class RevenueForecast(BaseModel):
    """Revenue projection for a future month."""

    model_config = ConfigDict(from_attributes=True)

    month: str = Field(..., description="Projected month (YYYY-MM)")
    projected_revenue: float = Field(default=0.0, description="Projected revenue ($)")
    confidence_low: float = Field(default=0.0, description="Low-end confidence bound ($)")
    confidence_high: float = Field(default=0.0, description="High-end confidence bound ($)")
    assumptions: list[str] = Field(default_factory=list, description="Key forecast assumptions")


class RevenueForecastListResponse(BaseModel):
    """List of revenue forecast records."""

    total: int = 0
    forecasts: list[RevenueForecast] = []


# ---------------------------------------------------------------------------
# Financial Report
# ---------------------------------------------------------------------------


class FinancialReport(BaseModel):
    """P&L-style financial report for a given period."""

    model_config = ConfigDict(from_attributes=True)

    report_type: ReportType = Field(..., description="Report cadence")
    period: str = Field(..., description="Period label (e.g. 2025-Q3, 2025-01)")
    total_revenue: float = Field(default=0.0, description="Total revenue ($)")
    total_costs: float = Field(default=0.0, description="Total costs ($)")
    gross_profit: float = Field(default=0.0, description="Gross profit ($)")
    gross_margin_pct: float = Field(default=0.0, description="Gross margin (%)")
    operating_expenses: float = Field(default=0.0, description="Operating expenses ($)")
    ebitda: float = Field(default=0.0, description="EBITDA ($)")
    ebitda_margin_pct: float = Field(default=0.0, description="EBITDA margin (%)")
    mrr: float = Field(default=0.0, description="Monthly recurring revenue ($)")
    arr: float = Field(default=0.0, description="Annual recurring revenue ($)")
    mrr_growth_rate: float = Field(default=0.0, description="MRR growth rate (%)")
    net_revenue_retention: float = Field(default=0.0, description="Net revenue retention (%)")
    customer_count: int = Field(default=0, description="Active customers")
    arpu: float = Field(default=0.0, description="Average revenue per user ($)")


# ---------------------------------------------------------------------------
# Revenue Metrics (SaaS KPIs)
# ---------------------------------------------------------------------------


class RevenueMetrics(BaseModel):
    """SaaS revenue metrics snapshot."""

    model_config = ConfigDict(from_attributes=True)

    mrr: float = Field(default=0.0, description="Monthly recurring revenue ($)")
    arr: float = Field(default=0.0, description="Annual recurring revenue ($)")
    mrr_growth_rate_pct: float = Field(default=0.0, description="MRR month-over-month growth (%)")
    net_revenue_retention_pct: float = Field(default=0.0, description="Net revenue retention (%)")
    gross_margin_pct: float = Field(default=0.0, description="Gross margin (%)")
    arpu: float = Field(default=0.0, description="Average revenue per user ($)")
    ltv: float = Field(default=0.0, description="Customer lifetime value ($)")
    cac: float = Field(default=0.0, description="Customer acquisition cost ($)")
    ltv_cac_ratio: float = Field(default=0.0, description="LTV/CAC ratio")
    payback_period_months: float = Field(default=0.0, description="CAC payback period (months)")
    revenue_per_employee: float = Field(default=0.0, description="Revenue per employee ($)")


# ---------------------------------------------------------------------------
# Revenue Breakdowns
# ---------------------------------------------------------------------------


class RevenueByStreamItem(BaseModel):
    """Revenue for a single stream."""

    stream: RevenueStream
    total: float = 0.0
    percentage: float = 0.0


class RevenueByStreamResponse(BaseModel):
    """Revenue breakdown by stream type."""

    total_revenue: float = 0.0
    streams: list[RevenueByStreamItem] = []


class RevenueBySponsorItem(BaseModel):
    """Revenue for a single sponsor."""

    sponsor_name: str
    total: float = 0.0
    percentage: float = 0.0


class RevenueBySponsorResponse(BaseModel):
    """Revenue breakdown by sponsor."""

    total_revenue: float = 0.0
    sponsors: list[RevenueBySponsorItem] = []


# ---------------------------------------------------------------------------
# Revenue Recognition
# ---------------------------------------------------------------------------


class RevenueRecognitionRequest(BaseModel):
    """Request to recognize revenue for a contract."""

    contract_id: str
    amount: float = Field(..., gt=0, description="Amount to recognize ($)")
    month: str = Field(..., description="Month to recognize in (YYYY-MM)")


class RevenueRecognitionResponse(BaseModel):
    """Result of a revenue recognition event."""

    contract_id: str
    amount_recognized: float
    month: str
    total_recognized: float
    remaining_value: float
