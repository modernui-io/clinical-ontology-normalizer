"""Clinical Trial Risk Management API endpoints (RISK-MGMT).

Provides comprehensive risk management operations: risk identification, assessment,
mitigation planning, risk monitoring, risk reviews, issue escalation, and risk metrics.

Endpoints:
    GET    /risk-management/risks                       - List risks
    GET    /risk-management/risks/{risk_id}              - Get single risk
    POST   /risk-management/risks                       - Create risk
    PUT    /risk-management/risks/{risk_id}              - Update risk
    DELETE /risk-management/risks/{risk_id}              - Delete risk
    GET    /risk-management/mitigations                  - List mitigations
    GET    /risk-management/mitigations/{mitigation_id}  - Get single mitigation
    POST   /risk-management/mitigations                  - Create mitigation
    PUT    /risk-management/mitigations/{mitigation_id}  - Update mitigation
    DELETE /risk-management/mitigations/{mitigation_id}  - Delete mitigation
    GET    /risk-management/reviews                      - List reviews
    GET    /risk-management/reviews/{review_id}           - Get single review
    POST   /risk-management/reviews                      - Create review
    GET    /risk-management/issues                       - List issues
    GET    /risk-management/issues/{issue_id}             - Get single issue
    POST   /risk-management/issues                       - Create issue
    PUT    /risk-management/issues/{issue_id}             - Update issue
    DELETE /risk-management/issues/{issue_id}             - Delete issue
    GET    /risk-management/metrics                      - Risk management metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.risk_management import (
    IssueStatus,
    MitigationStatus,
    RiskCategory,
    RiskIssue,
    RiskIssueCreate,
    RiskIssueListResponse,
    RiskIssueUpdate,
    RiskLevel,
    RiskManagementMetrics,
    RiskMitigation,
    RiskMitigationCreate,
    RiskMitigationListResponse,
    RiskMitigationUpdate,
    RiskReview,
    RiskReviewCreate,
    RiskReviewListResponse,
    RiskStatus,
    TrialRisk,
    TrialRiskCreate,
    TrialRiskListResponse,
    TrialRiskUpdate,
)
from app.services.risk_management_service import get_risk_management_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/risk-management",
    tags=["Risk Management"],
)


# ---------------------------------------------------------------------------
# Risk Management
# ---------------------------------------------------------------------------


@router.get(
    "/risks",
    response_model=TrialRiskListResponse,
    summary="List trial risks",
    description="Retrieve trial risks with optional filtering by trial, category, level, and status.",
)
async def list_risks(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    category: Optional[RiskCategory] = Query(None, description="Filter by risk category"),
    risk_level: Optional[RiskLevel] = Query(None, description="Filter by risk level"),
    status: Optional[RiskStatus] = Query(None, description="Filter by status"),
) -> TrialRiskListResponse:
    svc = get_risk_management_service()
    items = svc.list_risks(
        trial_id=trial_id, category=category, risk_level=risk_level, status=status,
    )
    return TrialRiskListResponse(items=items, total=len(items))


@router.get(
    "/risks/{risk_id}",
    response_model=TrialRisk,
    summary="Get a trial risk",
)
async def get_risk(risk_id: str) -> TrialRisk:
    svc = get_risk_management_service()
    risk = svc.get_risk(risk_id)
    if risk is None:
        raise HTTPException(status_code=404, detail=f"Risk '{risk_id}' not found")
    return risk


@router.post(
    "/risks",
    response_model=TrialRisk,
    status_code=201,
    summary="Create a trial risk",
)
async def create_risk(payload: TrialRiskCreate) -> TrialRisk:
    svc = get_risk_management_service()
    return svc.create_risk(payload)


@router.put(
    "/risks/{risk_id}",
    response_model=TrialRisk,
    summary="Update a trial risk",
)
async def update_risk(risk_id: str, payload: TrialRiskUpdate) -> TrialRisk:
    svc = get_risk_management_service()
    updated = svc.update_risk(risk_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Risk '{risk_id}' not found")
    return updated


@router.delete(
    "/risks/{risk_id}",
    status_code=204,
    summary="Delete a trial risk",
)
async def delete_risk(risk_id: str) -> None:
    svc = get_risk_management_service()
    deleted = svc.delete_risk(risk_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Risk '{risk_id}' not found")


# ---------------------------------------------------------------------------
# Mitigation Management
# ---------------------------------------------------------------------------


@router.get(
    "/mitigations",
    response_model=RiskMitigationListResponse,
    summary="List risk mitigations",
    description="Retrieve risk mitigations with optional filtering by risk and status.",
)
async def list_mitigations(
    risk_id: Optional[str] = Query(None, description="Filter by risk ID"),
    status: Optional[MitigationStatus] = Query(None, description="Filter by status"),
) -> RiskMitigationListResponse:
    svc = get_risk_management_service()
    items = svc.list_mitigations(risk_id=risk_id, status=status)
    return RiskMitigationListResponse(items=items, total=len(items))


@router.get(
    "/mitigations/{mitigation_id}",
    response_model=RiskMitigation,
    summary="Get a risk mitigation",
)
async def get_mitigation(mitigation_id: str) -> RiskMitigation:
    svc = get_risk_management_service()
    mitigation = svc.get_mitigation(mitigation_id)
    if mitigation is None:
        raise HTTPException(status_code=404, detail=f"Mitigation '{mitigation_id}' not found")
    return mitigation


@router.post(
    "/mitigations",
    response_model=RiskMitigation,
    status_code=201,
    summary="Create a risk mitigation",
)
async def create_mitigation(payload: RiskMitigationCreate) -> RiskMitigation:
    svc = get_risk_management_service()
    result = svc.create_mitigation(payload)
    if result is None:
        raise HTTPException(status_code=400, detail=f"Risk '{payload.risk_id}' not found")
    return result


@router.put(
    "/mitigations/{mitigation_id}",
    response_model=RiskMitigation,
    summary="Update a risk mitigation",
)
async def update_mitigation(
    mitigation_id: str, payload: RiskMitigationUpdate
) -> RiskMitigation:
    svc = get_risk_management_service()
    updated = svc.update_mitigation(mitigation_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Mitigation '{mitigation_id}' not found")
    return updated


@router.delete(
    "/mitigations/{mitigation_id}",
    status_code=204,
    summary="Delete a risk mitigation",
)
async def delete_mitigation(mitigation_id: str) -> None:
    svc = get_risk_management_service()
    deleted = svc.delete_mitigation(mitigation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Mitigation '{mitigation_id}' not found")


# ---------------------------------------------------------------------------
# Review Management
# ---------------------------------------------------------------------------


@router.get(
    "/reviews",
    response_model=RiskReviewListResponse,
    summary="List risk reviews",
    description="Retrieve risk reviews with optional filtering by risk.",
)
async def list_reviews(
    risk_id: Optional[str] = Query(None, description="Filter by risk ID"),
) -> RiskReviewListResponse:
    svc = get_risk_management_service()
    items = svc.list_reviews(risk_id=risk_id)
    return RiskReviewListResponse(items=items, total=len(items))


@router.get(
    "/reviews/{review_id}",
    response_model=RiskReview,
    summary="Get a risk review",
)
async def get_review(review_id: str) -> RiskReview:
    svc = get_risk_management_service()
    review = svc.get_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found")
    return review


@router.post(
    "/reviews",
    response_model=RiskReview,
    status_code=201,
    summary="Create a risk review",
    description="Submit a risk review. Updates the associated risk's last_reviewed date.",
)
async def create_review(payload: RiskReviewCreate) -> RiskReview:
    svc = get_risk_management_service()
    result = svc.create_review(payload)
    if result is None:
        raise HTTPException(status_code=400, detail=f"Risk '{payload.risk_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Issue Management
# ---------------------------------------------------------------------------


@router.get(
    "/issues",
    response_model=RiskIssueListResponse,
    summary="List risk issues",
    description="Retrieve risk issues with optional filtering by trial, risk, status, severity, and category.",
)
async def list_issues(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    risk_id: Optional[str] = Query(None, description="Filter by risk ID"),
    status: Optional[IssueStatus] = Query(None, description="Filter by status"),
    severity: Optional[RiskLevel] = Query(None, description="Filter by severity"),
    category: Optional[RiskCategory] = Query(None, description="Filter by category"),
) -> RiskIssueListResponse:
    svc = get_risk_management_service()
    items = svc.list_issues(
        trial_id=trial_id, risk_id=risk_id, status=status,
        severity=severity, category=category,
    )
    return RiskIssueListResponse(items=items, total=len(items))


@router.get(
    "/issues/{issue_id}",
    response_model=RiskIssue,
    summary="Get a risk issue",
)
async def get_issue(issue_id: str) -> RiskIssue:
    svc = get_risk_management_service()
    issue = svc.get_issue(issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail=f"Issue '{issue_id}' not found")
    return issue


@router.post(
    "/issues",
    response_model=RiskIssue,
    status_code=201,
    summary="Create a risk issue",
)
async def create_issue(payload: RiskIssueCreate) -> RiskIssue:
    svc = get_risk_management_service()
    return svc.create_issue(payload)


@router.put(
    "/issues/{issue_id}",
    response_model=RiskIssue,
    summary="Update a risk issue",
)
async def update_issue(issue_id: str, payload: RiskIssueUpdate) -> RiskIssue:
    svc = get_risk_management_service()
    updated = svc.update_issue(issue_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Issue '{issue_id}' not found")
    return updated


@router.delete(
    "/issues/{issue_id}",
    status_code=204,
    summary="Delete a risk issue",
)
async def delete_issue(issue_id: str) -> None:
    svc = get_risk_management_service()
    deleted = svc.delete_issue(issue_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Issue '{issue_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=RiskManagementMetrics,
    summary="Get risk management metrics",
    description="Aggregated risk management metrics including risk counts by category/level/status, "
                "overdue mitigations, critical risks, open issues, and issue severity breakdown.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> RiskManagementMetrics:
    svc = get_risk_management_service()
    return svc.get_metrics(trial_id=trial_id)
