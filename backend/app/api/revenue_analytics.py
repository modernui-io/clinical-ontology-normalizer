"""Revenue Analytics & Financial Reporting API (CFO-2).

Endpoints for revenue analytics on a pharma-regulated clinical trial
patient recruitment platform:
- Revenue contract CRUD
- Monthly revenue history
- SaaS metrics (MRR, ARR, NRR, LTV/CAC)
- Sponsor cohort retention analysis
- Revenue forecasting with confidence intervals
- P&L financial reporting
- Revenue breakdowns by stream and sponsor
- Revenue recognition
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas.revenue_analytics import (
    CohortAnalysisListResponse,
    ContractStatus,
    FinancialReport,
    MonthlyRevenueListResponse,
    ReportType,
    RevenueBySponsorResponse,
    RevenueByStreamResponse,
    RevenueContract,
    RevenueContractCreate,
    RevenueContractListResponse,
    RevenueContractUpdate,
    RevenueForecastListResponse,
    RevenueMetrics,
    RevenueRecognitionRequest,
    RevenueRecognitionResponse,
)
from app.services.revenue_analytics_service import get_revenue_analytics_service

router = APIRouter(prefix="/revenue-analytics", tags=["Revenue Analytics"])


# ============================================================================
# Contracts
# ============================================================================


@router.get(
    "/contracts",
    response_model=RevenueContractListResponse,
    summary="List revenue contracts",
    description="List all revenue contracts with optional status and sponsor filters.",
)
async def list_contracts(
    status: ContractStatus | None = Query(default=None, description="Filter by status"),
    sponsor: str | None = Query(default=None, description="Filter by sponsor name"),
) -> RevenueContractListResponse:
    """List revenue contracts."""
    service = get_revenue_analytics_service()
    return service.list_contracts(status=status, sponsor=sponsor)


@router.get(
    "/contracts/{contract_id}",
    response_model=RevenueContract,
    summary="Get a contract",
    description="Retrieve a single revenue contract by ID.",
)
async def get_contract(contract_id: str) -> RevenueContract:
    """Get a single contract by ID."""
    service = get_revenue_analytics_service()
    contract = service.get_contract(contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")
    return contract


@router.post(
    "/contracts",
    response_model=RevenueContract,
    status_code=201,
    summary="Create a contract",
    description="Create a new revenue contract with a pharma sponsor.",
)
async def create_contract(body: RevenueContractCreate) -> RevenueContract:
    """Create a new revenue contract."""
    service = get_revenue_analytics_service()
    return service.create_contract(body)


@router.put(
    "/contracts/{contract_id}",
    response_model=RevenueContract,
    summary="Update a contract",
    description="Update fields on an existing revenue contract.",
)
async def update_contract(contract_id: str, body: RevenueContractUpdate) -> RevenueContract:
    """Update an existing contract."""
    service = get_revenue_analytics_service()
    updated = service.update_contract(contract_id, body)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")
    return updated


# ============================================================================
# Monthly Revenue
# ============================================================================


@router.get(
    "/monthly",
    response_model=MonthlyRevenueListResponse,
    summary="Monthly revenue history",
    description="Historical monthly revenue with stream/sponsor breakdown.",
)
async def get_monthly_revenue(
    start_month: str | None = Query(default=None, description="Start month (YYYY-MM)"),
    end_month: str | None = Query(default=None, description="End month (YYYY-MM)"),
) -> MonthlyRevenueListResponse:
    """Return monthly revenue history."""
    service = get_revenue_analytics_service()
    return service.get_monthly_revenue(start_month=start_month, end_month=end_month)


# ============================================================================
# Revenue Metrics
# ============================================================================


@router.get(
    "/metrics",
    response_model=RevenueMetrics,
    summary="SaaS revenue metrics",
    description="Key SaaS metrics: MRR, ARR, growth, NRR, LTV/CAC, margins.",
)
async def get_revenue_metrics() -> RevenueMetrics:
    """Return current SaaS revenue metrics."""
    service = get_revenue_analytics_service()
    return service.get_revenue_metrics()


# ============================================================================
# Cohort Analysis
# ============================================================================


@router.get(
    "/cohorts",
    response_model=CohortAnalysisListResponse,
    summary="Sponsor cohort analysis",
    description="Retention analysis by sponsor acquisition cohort (quarterly).",
)
async def get_cohort_analysis() -> CohortAnalysisListResponse:
    """Return sponsor cohort retention analysis."""
    service = get_revenue_analytics_service()
    return service.get_cohort_analysis()


# ============================================================================
# Forecasting
# ============================================================================


@router.get(
    "/forecast",
    response_model=RevenueForecastListResponse,
    summary="Revenue forecast",
    description="Linear regression revenue forecast with confidence intervals.",
)
async def get_forecast(
    months_ahead: int = Query(default=6, ge=1, le=24, description="Months to forecast"),
) -> RevenueForecastListResponse:
    """Return revenue forecast."""
    service = get_revenue_analytics_service()
    return service.forecast_revenue(months_ahead=months_ahead)


# ============================================================================
# Financial Reports
# ============================================================================


@router.get(
    "/report",
    response_model=FinancialReport,
    summary="Financial report",
    description="P&L-style financial report for a given period.",
)
async def get_financial_report(
    report_type: ReportType = Query(default=ReportType.MONTHLY, description="Report type"),
    period: str | None = Query(default=None, description="Period (YYYY-MM, YYYY-QN, or YYYY)"),
) -> FinancialReport:
    """Generate a financial report."""
    service = get_revenue_analytics_service()
    return service.generate_financial_report(report_type=report_type, period=period)


# ============================================================================
# Revenue Breakdowns
# ============================================================================


@router.get(
    "/by-stream",
    response_model=RevenueByStreamResponse,
    summary="Revenue by stream",
    description="Revenue breakdown by stream type (platform license, screening, etc.).",
)
async def get_revenue_by_stream() -> RevenueByStreamResponse:
    """Return revenue breakdown by stream."""
    service = get_revenue_analytics_service()
    return service.get_revenue_by_stream()


@router.get(
    "/by-sponsor",
    response_model=RevenueBySponsorResponse,
    summary="Revenue by sponsor",
    description="Revenue breakdown by pharma sponsor.",
)
async def get_revenue_by_sponsor() -> RevenueBySponsorResponse:
    """Return revenue breakdown by sponsor."""
    service = get_revenue_analytics_service()
    return service.get_revenue_by_sponsor()


# ============================================================================
# Revenue Recognition
# ============================================================================


@router.post(
    "/recognize",
    response_model=RevenueRecognitionResponse,
    summary="Recognize revenue",
    description="Record a revenue recognition event for a contract.",
)
async def recognize_revenue(body: RevenueRecognitionRequest) -> RevenueRecognitionResponse:
    """Recognize revenue for a contract."""
    service = get_revenue_analytics_service()
    result = service.recognize_revenue(
        contract_id=body.contract_id,
        amount=body.amount,
        month=body.month,
    )
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Contract {body.contract_id} not found",
        )
    return result
