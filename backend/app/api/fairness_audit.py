"""Fairness Audit API endpoints (VP-DS-5).

Endpoints for detecting and monitoring bias in clinical trial screening
across protected demographic groups.

Endpoints:
    POST /api/v1/fairness/audits                    - Run a fairness audit
    GET  /api/v1/fairness/audits                    - List audit reports
    GET  /api/v1/fairness/audits/{id}               - Audit detail
    GET  /api/v1/fairness/audits/{id}/recommendations - Bias mitigation recommendations
    POST /api/v1/fairness/record                    - Record screening outcome
    GET  /api/v1/fairness/trends                    - Fairness metric trends
    GET  /api/v1/fairness/platform-summary          - Platform-wide fairness summary
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.permissions import Permission, PermissionChecker
from app.schemas.fairness_audit import (
    BiasRecommendation,
    FairnessAuditCreate,
    FairnessAuditResponse,
    FairnessTrend,
    PlatformFairnessSummary,
    RecordScreeningOutcomeRequest,
    ScreeningOutcomeRecord,
)
from app.services.fairness_audit_service import get_fairness_audit_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/fairness",
    tags=["Fairness Audits"],
)


@router.post(
    "/audits",
    response_model=FairnessAuditResponse,
    summary="Run a fairness audit for a trial",
    description=(
        "Runs a comprehensive fairness audit analyzing demographic parity, "
        "equal opportunity, predictive parity, individual fairness, and "
        "intersectional bias for a trial's screening outcomes."
    ),
)
async def run_fairness_audit(
    request: Request,
    body: FairnessAuditCreate,
    _perm: None = Depends(PermissionChecker([Permission.READ_ANALYTICS])),
) -> FairnessAuditResponse:
    """Run a fairness audit for a trial."""
    service = get_fairness_audit_service()
    return service.run_audit(body)


@router.get(
    "/audits",
    response_model=list[FairnessAuditResponse],
    summary="List fairness audit reports",
    description=(
        "Lists fairness audit reports, optionally filtered by trial ID."
    ),
)
async def list_audits(
    request: Request,
    trial_id: str | None = Query(
        None, description="Filter by trial ID"
    ),
    _perm: None = Depends(PermissionChecker([Permission.READ_ANALYTICS])),
) -> list[FairnessAuditResponse]:
    """List fairness audit reports."""
    service = get_fairness_audit_service()
    return service.list_audits(trial_id=trial_id)


@router.get(
    "/audits/{audit_id}",
    response_model=FairnessAuditResponse,
    summary="Get audit detail",
    description="Retrieves a specific fairness audit report by ID.",
)
async def get_audit(
    audit_id: str,
    request: Request,
    _perm: None = Depends(PermissionChecker([Permission.READ_ANALYTICS])),
) -> FairnessAuditResponse:
    """Get a specific audit report."""
    service = get_fairness_audit_service()
    audit = service.get_audit(audit_id)
    if audit is None:
        raise HTTPException(status_code=404, detail=f"Audit {audit_id} not found")
    return audit


@router.get(
    "/audits/{audit_id}/recommendations",
    response_model=list[BiasRecommendation],
    summary="Get bias mitigation recommendations",
    description=(
        "Returns bias mitigation recommendations for a specific audit, "
        "including criteria review, data collection, and threshold adjustment "
        "suggestions."
    ),
)
async def get_recommendations(
    audit_id: str,
    request: Request,
    _perm: None = Depends(PermissionChecker([Permission.READ_ANALYTICS])),
) -> list[BiasRecommendation]:
    """Get recommendations for a specific audit."""
    service = get_fairness_audit_service()
    audit = service.get_audit(audit_id)
    if audit is None:
        raise HTTPException(status_code=404, detail=f"Audit {audit_id} not found")
    return service.get_recommendations(audit_id)


@router.post(
    "/record",
    response_model=dict,
    summary="Record screening outcome with demographics",
    description=(
        "Records a patient screening outcome along with demographic data "
        "for subsequent fairness analysis."
    ),
)
async def record_screening_outcome(
    request: Request,
    body: RecordScreeningOutcomeRequest,
    _perm: None = Depends(PermissionChecker([Permission.READ_ANALYTICS])),
) -> dict:
    """Record a screening outcome with demographics."""
    service = get_fairness_audit_service()
    service.record_screening_outcome(body.outcome)
    return {"status": "recorded", "patient_id": body.outcome.patient_id}


@router.get(
    "/trends",
    response_model=FairnessTrend,
    summary="Get fairness metric trends over time",
    description=(
        "Returns historical fairness metric trends for a trial, showing "
        "how demographic parity, equal opportunity, and predictive parity "
        "scores have evolved over successive audits."
    ),
)
async def get_trends(
    request: Request,
    trial_id: str = Query(..., description="Trial ID to get trends for"),
    _perm: None = Depends(PermissionChecker([Permission.READ_ANALYTICS])),
) -> FairnessTrend:
    """Get fairness metric trends for a trial."""
    service = get_fairness_audit_service()
    return service.get_trends(trial_id)


@router.get(
    "/platform-summary",
    response_model=PlatformFairnessSummary,
    summary="Get platform-wide fairness summary",
    description=(
        "Returns a platform-wide summary of fairness metrics across all "
        "trials, including average scores, violation counts, and per-trial "
        "summaries."
    ),
)
async def get_platform_summary(
    request: Request,
    _perm: None = Depends(PermissionChecker([Permission.READ_ANALYTICS])),
) -> PlatformFairnessSummary:
    """Get platform-wide fairness summary."""
    service = get_fairness_audit_service()
    return service.get_platform_summary()
