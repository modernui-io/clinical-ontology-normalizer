"""Access Review & Certification Management API endpoints (CISO-11).

Provides endpoints for managing periodic access review cycles, tracking
entitlements, submitting review decisions, detecting excessive access,
and computing compliance metrics.

Endpoints:
    GET    /api/v1/access-review/cycles                          - List review cycles
    POST   /api/v1/access-review/cycles                          - Create cycle
    GET    /api/v1/access-review/cycles/{id}                     - Get cycle
    PUT    /api/v1/access-review/cycles/{id}                     - Update cycle
    DELETE /api/v1/access-review/cycles/{id}                     - Delete cycle
    POST   /api/v1/access-review/cycles/{id}/start               - Start cycle
    POST   /api/v1/access-review/cycles/{id}/complete            - Complete cycle
    GET    /api/v1/access-review/cycles/{id}/pending              - Pending reviews
    POST   /api/v1/access-review/cycles/{id}/decisions            - Submit decision
    GET    /api/v1/access-review/entitlements                     - List entitlements
    POST   /api/v1/access-review/entitlements                     - Create entitlement
    GET    /api/v1/access-review/entitlements/{id}                - Get entitlement
    DELETE /api/v1/access-review/entitlements/{id}                - Delete entitlement
    GET    /api/v1/access-review/decisions                        - List decisions
    GET    /api/v1/access-review/excessive-access                 - Detect excessive access
    GET    /api/v1/access-review/metrics                          - Review metrics
    GET    /api/v1/access-review/overdue                          - Overdue cycles
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.access_review import (
    AccessEntitlement,
    AccessLevel,
    AccessReviewMetrics,
    CycleStatus,
    CycleType,
    DecisionListResponse,
    DecisionSubmitRequest,
    EntitlementCreateRequest,
    EntitlementListResponse,
    ExcessiveAccessResponse,
    ReviewCycle,
    ReviewCycleCreateRequest,
    ReviewCycleListResponse,
    ReviewCycleUpdateRequest,
    ReviewDecision,
    ReviewDecisionType,
)
from app.services.access_review_service import get_access_review_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/access-review",
    tags=["Access Review"],
)


# ============================================================================
# Review Cycle CRUD
# ============================================================================


@router.get(
    "/cycles",
    response_model=ReviewCycleListResponse,
    summary="List access review cycles",
)
async def list_cycles(
    cycle_type: CycleType | None = Query(None, description="Filter by cycle type"),
    cycle_status: CycleStatus | None = Query(
        None, alias="status", description="Filter by cycle status"
    ),
) -> ReviewCycleListResponse:
    """List all access review cycles with optional filters."""
    svc = get_access_review_service()
    items = svc.list_cycles(cycle_type=cycle_type, status=cycle_status)
    return ReviewCycleListResponse(items=items, total=len(items))


@router.post(
    "/cycles",
    response_model=ReviewCycle,
    status_code=status.HTTP_201_CREATED,
    summary="Create a review cycle",
)
async def create_cycle(req: ReviewCycleCreateRequest) -> ReviewCycle:
    """Create a new periodic access review cycle."""
    svc = get_access_review_service()
    return svc.create_cycle(req)


@router.get(
    "/cycles/{cycle_id}",
    response_model=ReviewCycle,
    summary="Get a review cycle",
)
async def get_cycle(cycle_id: str) -> ReviewCycle:
    """Get a single review cycle by ID."""
    svc = get_access_review_service()
    cycle = svc.get_cycle(cycle_id)
    if cycle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review cycle '{cycle_id}' not found",
        )
    return cycle


@router.put(
    "/cycles/{cycle_id}",
    response_model=ReviewCycle,
    summary="Update a review cycle",
)
async def update_cycle(cycle_id: str, req: ReviewCycleUpdateRequest) -> ReviewCycle:
    """Update an existing review cycle."""
    svc = get_access_review_service()
    updated = svc.update_cycle(cycle_id, req)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review cycle '{cycle_id}' not found",
        )
    return updated


@router.delete(
    "/cycles/{cycle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a review cycle",
)
async def delete_cycle(cycle_id: str) -> None:
    """Delete a review cycle and its decisions."""
    svc = get_access_review_service()
    deleted = svc.delete_cycle(cycle_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review cycle '{cycle_id}' not found",
        )


# ============================================================================
# Cycle lifecycle transitions
# ============================================================================


@router.post(
    "/cycles/{cycle_id}/start",
    response_model=ReviewCycle,
    summary="Start a review cycle",
)
async def start_cycle(cycle_id: str) -> ReviewCycle:
    """Transition a PLANNED cycle to IN_PROGRESS."""
    svc = get_access_review_service()
    result = svc.start_cycle(cycle_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot start cycle '{cycle_id}' (not found or not PLANNED)",
        )
    return result


@router.post(
    "/cycles/{cycle_id}/complete",
    response_model=ReviewCycle,
    summary="Complete a review cycle",
)
async def complete_cycle(cycle_id: str) -> ReviewCycle:
    """Transition an IN_PROGRESS cycle to COMPLETED."""
    svc = get_access_review_service()
    result = svc.complete_cycle(cycle_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot complete cycle '{cycle_id}' (not found or not IN_PROGRESS)",
        )
    return result


# ============================================================================
# Pending reviews & decision submission
# ============================================================================


@router.get(
    "/cycles/{cycle_id}/pending",
    response_model=EntitlementListResponse,
    summary="Get pending reviews for a cycle",
)
async def get_pending_reviews(cycle_id: str) -> EntitlementListResponse:
    """Get entitlements not yet reviewed in a given cycle."""
    svc = get_access_review_service()
    pending = svc.get_pending_reviews(cycle_id)
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review cycle '{cycle_id}' not found",
        )
    return EntitlementListResponse(items=pending, total=len(pending))


@router.post(
    "/cycles/{cycle_id}/decisions",
    response_model=ReviewDecision,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a review decision",
)
async def submit_decision(
    cycle_id: str, req: DecisionSubmitRequest
) -> ReviewDecision:
    """Submit a review decision for an entitlement within a cycle."""
    svc = get_access_review_service()
    decision = svc.submit_decision(cycle_id, req)
    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cycle '{cycle_id}' or entitlement '{req.entitlement_id}' not found",
        )
    return decision


# ============================================================================
# Entitlement CRUD
# ============================================================================


@router.get(
    "/entitlements",
    response_model=EntitlementListResponse,
    summary="List access entitlements",
)
async def list_entitlements(
    user_id: str | None = Query(None, description="Filter by user ID"),
    resource: str | None = Query(None, description="Filter by resource"),
    access_level: AccessLevel | None = Query(None, description="Filter by access level"),
) -> EntitlementListResponse:
    """List all access entitlements with optional filters."""
    svc = get_access_review_service()
    items = svc.list_entitlements(user_id=user_id, resource=resource, access_level=access_level)
    return EntitlementListResponse(items=items, total=len(items))


@router.post(
    "/entitlements",
    response_model=AccessEntitlement,
    status_code=status.HTTP_201_CREATED,
    summary="Create an access entitlement",
)
async def create_entitlement(req: EntitlementCreateRequest) -> AccessEntitlement:
    """Create a new access entitlement."""
    svc = get_access_review_service()
    return svc.create_entitlement(req)


@router.get(
    "/entitlements/{entitlement_id}",
    response_model=AccessEntitlement,
    summary="Get an access entitlement",
)
async def get_entitlement(entitlement_id: str) -> AccessEntitlement:
    """Get a single access entitlement by ID."""
    svc = get_access_review_service()
    ent = svc.get_entitlement(entitlement_id)
    if ent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entitlement '{entitlement_id}' not found",
        )
    return ent


@router.delete(
    "/entitlements/{entitlement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an access entitlement",
)
async def delete_entitlement(entitlement_id: str) -> None:
    """Delete an access entitlement."""
    svc = get_access_review_service()
    deleted = svc.delete_entitlement(entitlement_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entitlement '{entitlement_id}' not found",
        )


# ============================================================================
# Decisions
# ============================================================================


@router.get(
    "/decisions",
    response_model=DecisionListResponse,
    summary="List review decisions",
)
async def list_decisions(
    cycle_id: str | None = Query(None, description="Filter by cycle ID"),
    decision_type: ReviewDecisionType | None = Query(
        None, alias="decision", description="Filter by decision type"
    ),
) -> DecisionListResponse:
    """List all review decisions with optional filters."""
    svc = get_access_review_service()
    items = svc.list_decisions(cycle_id=cycle_id, decision_type=decision_type)
    return DecisionListResponse(items=items, total=len(items))


# ============================================================================
# Excessive access & metrics
# ============================================================================


@router.get(
    "/excessive-access",
    response_model=ExcessiveAccessResponse,
    summary="Detect excessive access",
)
async def detect_excessive_access() -> ExcessiveAccessResponse:
    """Flag users with ADMIN on 3+ resources or unused access > 90 days."""
    svc = get_access_review_service()
    return svc.detect_excessive_access()


@router.get(
    "/metrics",
    response_model=AccessReviewMetrics,
    summary="Get access review metrics",
)
async def get_metrics() -> AccessReviewMetrics:
    """Get aggregate access review compliance metrics."""
    svc = get_access_review_service()
    return svc.get_metrics()


@router.get(
    "/overdue",
    response_model=ReviewCycleListResponse,
    summary="Get overdue review cycles",
)
async def get_overdue_cycles() -> ReviewCycleListResponse:
    """Get review cycles that are past their end date."""
    svc = get_access_review_service()
    items = svc.get_overdue_cycles()
    return ReviewCycleListResponse(items=items, total=len(items))
