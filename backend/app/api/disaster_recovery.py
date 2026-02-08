"""Disaster Recovery Runbooks & RTO/RPO Management API endpoints (VPE-7).

Provides endpoints for managing DR runbooks, recording test results,
tracking RTO/RPO compliance, and accessing communication plans.

Endpoints:
    GET    /api/v1/disaster-recovery/runbooks                    - List runbooks
    POST   /api/v1/disaster-recovery/runbooks                    - Create runbook
    GET    /api/v1/disaster-recovery/runbooks/{id}               - Get runbook
    PUT    /api/v1/disaster-recovery/runbooks/{id}               - Update runbook
    DELETE /api/v1/disaster-recovery/runbooks/{id}               - Delete runbook
    POST   /api/v1/disaster-recovery/runbooks/{id}/tests         - Record test
    GET    /api/v1/disaster-recovery/runbooks/{id}/tests         - Test history
    GET    /api/v1/disaster-recovery/runbooks/{id}/validate      - Validate runbook
    GET    /api/v1/disaster-recovery/runbooks/{id}/communication - Communication plan
    GET    /api/v1/disaster-recovery/metrics                     - DR metrics
    GET    /api/v1/disaster-recovery/overdue                     - Overdue tests
    GET    /api/v1/disaster-recovery/categories                  - List categories
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.disaster_recovery import (
    CommunicationPlanResponse,
    DisasterCategory,
    DisasterRecoveryRunbook,
    DRMetrics,
    DRTestResult,
    RecordTestRequest,
    RecoveryTier,
    RunbookCreateRequest,
    RunbookListResponse,
    RunbookStatus,
    RunbookUpdateRequest,
    RunbookValidation,
    TestHistoryResponse,
)
from app.services.disaster_recovery_service import get_disaster_recovery_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/disaster-recovery",
    tags=["Disaster Recovery"],
)


# ============================================================================
# Runbook CRUD
# ============================================================================


@router.get(
    "/runbooks",
    response_model=RunbookListResponse,
    summary="List disaster recovery runbooks",
)
async def list_runbooks(
    category: DisasterCategory | None = Query(None, description="Filter by disaster category"),
    tier: RecoveryTier | None = Query(None, description="Filter by recovery tier"),
    runbook_status: RunbookStatus | None = Query(
        None, alias="status", description="Filter by runbook status"
    ),
) -> RunbookListResponse:
    """List all DR runbooks with optional filters."""
    svc = get_disaster_recovery_service()
    items = svc.list_runbooks(category=category, tier=tier, status=runbook_status)
    return RunbookListResponse(items=items, total=len(items))


@router.post(
    "/runbooks",
    response_model=DisasterRecoveryRunbook,
    status_code=status.HTTP_201_CREATED,
    summary="Create a disaster recovery runbook",
)
async def create_runbook(req: RunbookCreateRequest) -> DisasterRecoveryRunbook:
    """Create a new DR runbook."""
    svc = get_disaster_recovery_service()
    return svc.create_runbook(req)


@router.get(
    "/runbooks/{runbook_id}",
    response_model=DisasterRecoveryRunbook,
    summary="Get a disaster recovery runbook",
)
async def get_runbook(runbook_id: str) -> DisasterRecoveryRunbook:
    """Get a single DR runbook by ID."""
    svc = get_disaster_recovery_service()
    rb = svc.get_runbook(runbook_id)
    if rb is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runbook '{runbook_id}' not found",
        )
    return rb


@router.put(
    "/runbooks/{runbook_id}",
    response_model=DisasterRecoveryRunbook,
    summary="Update a disaster recovery runbook",
)
async def update_runbook(
    runbook_id: str, req: RunbookUpdateRequest
) -> DisasterRecoveryRunbook:
    """Update an existing DR runbook."""
    svc = get_disaster_recovery_service()
    updated = svc.update_runbook(runbook_id, req)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runbook '{runbook_id}' not found",
        )
    return updated


@router.delete(
    "/runbooks/{runbook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a disaster recovery runbook",
)
async def delete_runbook(runbook_id: str) -> None:
    """Delete a DR runbook."""
    svc = get_disaster_recovery_service()
    deleted = svc.delete_runbook(runbook_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runbook '{runbook_id}' not found",
        )


# ============================================================================
# Test management
# ============================================================================


@router.post(
    "/runbooks/{runbook_id}/tests",
    response_model=DRTestResult,
    status_code=status.HTTP_201_CREATED,
    summary="Record a DR test execution",
)
async def record_test(
    runbook_id: str, req: RecordTestRequest
) -> DRTestResult:
    """Record the result of a DR test for a runbook."""
    svc = get_disaster_recovery_service()
    result = svc.record_test(runbook_id, req)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runbook '{runbook_id}' not found",
        )
    return result


@router.get(
    "/runbooks/{runbook_id}/tests",
    response_model=TestHistoryResponse,
    summary="Get test history for a runbook",
)
async def get_test_history(runbook_id: str) -> TestHistoryResponse:
    """Get the test result history for a specific runbook."""
    svc = get_disaster_recovery_service()
    history = svc.get_test_history(runbook_id)
    if history is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runbook '{runbook_id}' not found",
        )
    return history


# ============================================================================
# Validation & communication
# ============================================================================


@router.get(
    "/runbooks/{runbook_id}/validate",
    response_model=RunbookValidation,
    summary="Validate runbook completeness",
)
async def validate_runbook(runbook_id: str) -> RunbookValidation:
    """Validate a runbook for completeness and readiness."""
    svc = get_disaster_recovery_service()
    validation = svc.validate_runbook(runbook_id)
    if validation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runbook '{runbook_id}' not found",
        )
    return validation


@router.get(
    "/runbooks/{runbook_id}/communication",
    response_model=CommunicationPlanResponse,
    summary="Get communication plan for a runbook",
)
async def get_communication_plan(
    runbook_id: str,
) -> CommunicationPlanResponse:
    """Get escalation contacts and communication plan for a runbook."""
    svc = get_disaster_recovery_service()
    plan = svc.get_communication_plan(runbook_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runbook '{runbook_id}' not found",
        )
    return plan


# ============================================================================
# Metrics & overdue
# ============================================================================


@router.get(
    "/metrics",
    response_model=DRMetrics,
    summary="Get DR program metrics",
)
async def get_metrics() -> DRMetrics:
    """Get aggregate disaster recovery program metrics."""
    svc = get_disaster_recovery_service()
    return svc.get_metrics()


@router.get(
    "/overdue",
    response_model=RunbookListResponse,
    summary="Get runbooks with overdue tests",
)
async def get_overdue_tests() -> RunbookListResponse:
    """Get runbooks whose DR tests are overdue based on tier thresholds."""
    svc = get_disaster_recovery_service()
    items = svc.get_overdue_tests()
    return RunbookListResponse(items=items, total=len(items))


@router.get(
    "/categories",
    response_model=list[dict[str, str]],
    summary="List disaster categories",
)
async def list_categories() -> list[dict[str, str]]:
    """List all available disaster categories."""
    return [
        {"value": c.value, "label": c.value.replace("_", " ").title()}
        for c in DisasterCategory
    ]
