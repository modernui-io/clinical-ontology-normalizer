"""Budget Tracking & Approval Workflows API (CFO-3).

Provides endpoints for budget period management, allocation tracking,
spend request workflows, approval routing, variance analysis, forecasting,
and department budget summaries.

Endpoints:
    GET  /budget-management/periods              - List budget periods
    POST /budget-management/periods              - Create budget period
    GET  /budget-management/periods/{period_id}   - Get budget period
    GET  /budget-management/allocations           - List allocations
    POST /budget-management/allocations           - Create allocation
    GET  /budget-management/allocations/{id}      - Get allocation
    POST /budget-management/allocations/{id}/record-spend - Record spend
    GET  /budget-management/spend-requests        - List spend requests
    POST /budget-management/spend-requests        - Submit spend request
    GET  /budget-management/spend-requests/{id}   - Get spend request
    PUT  /budget-management/spend-requests/{id}   - Update spend request
    POST /budget-management/spend-requests/{id}/approve - Approve request
    POST /budget-management/spend-requests/{id}/reject  - Reject request
    GET  /budget-management/alerts                - List budget alerts
    POST /budget-management/alerts/{id}/acknowledge - Acknowledge alert
    GET  /budget-management/metrics               - Dashboard metrics
    GET  /budget-management/forecast              - Spend forecast
    GET  /budget-management/approval-route        - Approval route lookup
    GET  /budget-management/department-summary    - Department summaries
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from app.schemas.budget_management import (
    AlertListResponse,
    AllocationListResponse,
    ApprovalInput,
    ApprovalStatus,
    BudgetAlert,
    BudgetAllocation,
    BudgetCategory,
    BudgetMetrics,
    BudgetPeriod,
    BudgetPeriodListResponse,
    RecordSpendInput,
    RejectionInput,
    SpendForecast,
    SpendRequest,
    SpendRequestCreate,
    SpendRequestListResponse,
    SpendRequestUpdate,
)
from app.services.budget_management_service import get_budget_management_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/budget-management", tags=["Budget Management"])


# ---------------------------------------------------------------------------
# Budget Periods
# ---------------------------------------------------------------------------


@router.get(
    "/periods",
    response_model=BudgetPeriodListResponse,
    summary="List budget periods",
    description="List all budget periods with optional fiscal year filter.",
)
async def list_periods(
    fiscal_year: int | None = Query(None, description="Filter by fiscal year"),
) -> BudgetPeriodListResponse:
    """Return budget periods."""
    svc = get_budget_management_service()
    periods = svc.list_periods(fiscal_year=fiscal_year)
    return BudgetPeriodListResponse(items=periods, total=len(periods))


@router.post(
    "/periods",
    response_model=BudgetPeriod,
    status_code=201,
    summary="Create budget period",
    description="Create a new quarterly budget period.",
)
async def create_period(
    fiscal_year: int = Query(..., description="Fiscal year (e.g. 2026)"),
    quarter: str = Query(..., description="Quarter (Q1, Q2, Q3, Q4)"),
    total_budget: float = Query(..., description="Total budget for the period"),
) -> BudgetPeriod:
    """Create a budget period."""
    svc = get_budget_management_service()
    try:
        return svc.create_period(
            fiscal_year=fiscal_year,
            quarter=quarter,
            total_budget=total_budget,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/periods/{period_id}",
    response_model=BudgetPeriod,
    summary="Get budget period",
    description="Get a single budget period by ID.",
)
async def get_period(period_id: str) -> BudgetPeriod:
    """Return a budget period."""
    svc = get_budget_management_service()
    period = svc.get_period(period_id)
    if period is None:
        raise HTTPException(status_code=404, detail=f"Period {period_id} not found")
    return period


# ---------------------------------------------------------------------------
# Budget Allocations
# ---------------------------------------------------------------------------


@router.get(
    "/allocations",
    response_model=AllocationListResponse,
    summary="List budget allocations",
    description="List allocations with optional period and category filters.",
)
async def list_allocations(
    period_id: str | None = Query(None, description="Filter by period ID"),
    category: BudgetCategory | None = Query(None, description="Filter by category"),
) -> AllocationListResponse:
    """Return budget allocations."""
    svc = get_budget_management_service()
    allocs = svc.list_allocations(period_id=period_id, category=category)
    return AllocationListResponse(items=allocs, total=len(allocs))


@router.post(
    "/allocations",
    response_model=BudgetAllocation,
    status_code=201,
    summary="Create budget allocation",
    description="Create a new allocation for a budget period and category.",
)
async def create_allocation(
    period_id: str = Query(..., description="Budget period ID"),
    category: BudgetCategory = Query(..., description="Budget category"),
    allocated_amount: float = Query(..., description="Amount to allocate"),
    owner: str = Query("", description="Budget owner"),
) -> BudgetAllocation:
    """Create a budget allocation."""
    svc = get_budget_management_service()
    try:
        return svc.create_allocation(
            period_id=period_id,
            category=category,
            allocated_amount=allocated_amount,
            owner=owner,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/allocations/{allocation_id}",
    response_model=BudgetAllocation,
    summary="Get budget allocation",
    description="Get a single allocation by ID.",
)
async def get_allocation(allocation_id: str) -> BudgetAllocation:
    """Return a budget allocation."""
    svc = get_budget_management_service()
    alloc = svc.get_allocation(allocation_id)
    if alloc is None:
        raise HTTPException(
            status_code=404, detail=f"Allocation {allocation_id} not found"
        )
    return alloc


@router.post(
    "/allocations/{allocation_id}/record-spend",
    response_model=BudgetAllocation,
    summary="Record spend against allocation",
    description="Record a direct spend against a budget allocation.",
)
async def record_spend(
    allocation_id: str,
    spend_input: RecordSpendInput,
) -> BudgetAllocation:
    """Record spend against an allocation."""
    svc = get_budget_management_service()
    try:
        result = svc.record_spend(allocation_id, spend_input)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Allocation {allocation_id} not found"
        )
    return result


# ---------------------------------------------------------------------------
# Spend Requests
# ---------------------------------------------------------------------------


@router.get(
    "/spend-requests",
    response_model=SpendRequestListResponse,
    summary="List spend requests",
    description="List spend requests with optional allocation and status filters.",
)
async def list_spend_requests(
    allocation_id: str | None = Query(None, description="Filter by allocation ID"),
    status: ApprovalStatus | None = Query(None, description="Filter by status"),
) -> SpendRequestListResponse:
    """Return spend requests."""
    svc = get_budget_management_service()
    requests = svc.list_spend_requests(allocation_id=allocation_id, status=status)
    return SpendRequestListResponse(items=requests, total=len(requests))


@router.post(
    "/spend-requests",
    response_model=SpendRequest,
    status_code=201,
    summary="Submit spend request",
    description=(
        "Submit a new spend request. Automatically routes to the appropriate "
        "approver based on amount (>$10K VP, >$50K CFO)."
    ),
)
async def submit_spend_request(
    request: SpendRequestCreate,
) -> SpendRequest:
    """Submit a spend request."""
    svc = get_budget_management_service()
    try:
        return svc.submit_spend_request(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/spend-requests/{request_id}",
    response_model=SpendRequest,
    summary="Get spend request",
    description="Get a single spend request by ID.",
)
async def get_spend_request(request_id: str) -> SpendRequest:
    """Return a spend request."""
    svc = get_budget_management_service()
    sr = svc.get_spend_request(request_id)
    if sr is None:
        raise HTTPException(
            status_code=404, detail=f"Spend request {request_id} not found"
        )
    return sr


@router.put(
    "/spend-requests/{request_id}",
    response_model=SpendRequest,
    summary="Update spend request",
    description="Update a spend request (only DRAFT or REVISION_REQUESTED).",
)
async def update_spend_request(
    request_id: str,
    update: SpendRequestUpdate,
) -> SpendRequest:
    """Update a spend request."""
    svc = get_budget_management_service()
    try:
        result = svc.update_spend_request(request_id, update)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Spend request {request_id} not found"
        )
    return result


@router.post(
    "/spend-requests/{request_id}/approve",
    response_model=SpendRequest,
    summary="Approve spend request",
    description="Approve a pending spend request.",
)
async def approve_spend_request(
    request_id: str,
    approval: ApprovalInput,
) -> SpendRequest:
    """Approve a spend request."""
    svc = get_budget_management_service()
    try:
        result = svc.approve_request(request_id, approval.approver)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Spend request {request_id} not found"
        )
    return result


@router.post(
    "/spend-requests/{request_id}/reject",
    response_model=SpendRequest,
    summary="Reject spend request",
    description="Reject a pending spend request with a reason.",
)
async def reject_spend_request(
    request_id: str,
    rejection: RejectionInput,
) -> SpendRequest:
    """Reject a spend request."""
    svc = get_budget_management_service()
    try:
        result = svc.reject_request(
            request_id, rejection.approver, rejection.reason
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Spend request {request_id} not found"
        )
    return result


# ---------------------------------------------------------------------------
# Budget Alerts
# ---------------------------------------------------------------------------


@router.get(
    "/alerts",
    response_model=AlertListResponse,
    summary="List budget alerts",
    description="List budget alerts with optional acknowledgment filter.",
)
async def list_alerts(
    acknowledged: bool | None = Query(
        None, description="Filter by acknowledgment status"
    ),
) -> AlertListResponse:
    """Return budget alerts."""
    svc = get_budget_management_service()
    alerts = svc.get_budget_alerts(acknowledged=acknowledged)
    return AlertListResponse(items=alerts, total=len(alerts))


@router.post(
    "/alerts/{alert_id}/acknowledge",
    response_model=BudgetAlert,
    summary="Acknowledge budget alert",
    description="Mark a budget alert as acknowledged.",
)
async def acknowledge_alert(alert_id: str) -> BudgetAlert:
    """Acknowledge a budget alert."""
    svc = get_budget_management_service()
    alert = svc.acknowledge_alert(alert_id)
    if alert is None:
        raise HTTPException(
            status_code=404, detail=f"Alert {alert_id} not found"
        )
    return alert


# ---------------------------------------------------------------------------
# Metrics & Forecasting
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=BudgetMetrics,
    summary="Budget dashboard metrics",
    description="Get aggregated budget metrics for the dashboard.",
)
async def get_metrics() -> BudgetMetrics:
    """Return budget dashboard metrics."""
    svc = get_budget_management_service()
    return svc.get_metrics()


@router.get(
    "/forecast",
    response_model=SpendForecast,
    summary="Spend forecast",
    description="Project spend based on current burn rate.",
)
async def get_forecast(
    months_ahead: int = Query(
        6, ge=1, le=36, description="Number of months to project"
    ),
) -> SpendForecast:
    """Return spend forecast."""
    svc = get_budget_management_service()
    return svc.forecast_spend(months_ahead=months_ahead)


@router.get(
    "/approval-route",
    summary="Approval route lookup",
    description="Determine the required approval level for a given amount.",
)
async def get_approval_route(
    amount: float = Query(..., description="Spend amount in USD"),
) -> dict[str, str]:
    """Return the approval route for a given amount."""
    svc = get_budget_management_service()
    route = svc.get_approval_route(amount)
    return {"amount": str(amount), "approval_route": route}


@router.get(
    "/department-summary",
    summary="Department budget summaries",
    description=(
        "Get budget summary by department/owner for a given period. "
        "Groups allocations by owner with totals."
    ),
)
async def get_department_summary(
    period_id: str | None = Query(None, description="Filter by period ID"),
) -> list[dict]:
    """Return department budget summaries."""
    svc = get_budget_management_service()
    allocs = svc.list_allocations(period_id=period_id)

    # Group by owner
    owner_map: dict[str, dict] = {}
    for alloc in allocs:
        owner = alloc.owner or "Unassigned"
        if owner not in owner_map:
            owner_map[owner] = {
                "owner": owner,
                "total_allocated": 0.0,
                "total_spent": 0.0,
                "total_remaining": 0.0,
                "total_committed": 0.0,
                "categories": [],
            }
        entry = owner_map[owner]
        entry["total_allocated"] += alloc.allocated_amount
        entry["total_spent"] += alloc.spent_amount
        entry["total_remaining"] += alloc.remaining
        entry["total_committed"] += alloc.committed
        entry["categories"].append(alloc.category.value)

    return list(owner_map.values())
