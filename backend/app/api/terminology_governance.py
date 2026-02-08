"""Terminology Governance API endpoints.

Dir-CI-3.1: Terminology Governance Workflow - endpoints for managing
the mapping review queue, submitting mappings for review, approving/rejecting
mappings, and viewing review statistics.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas.terminology_governance import (
    ReviewDecision,
    ReviewItemResponse,
    ReviewStats,
    ReviewStatus,
    ReviewSubmission,
)
from app.services.terminology_governance_service import get_terminology_governance_service

router = APIRouter(prefix="/terminology/review-queue", tags=["Terminology Governance"])


@router.get(
    "",
    response_model=list[ReviewItemResponse],
    summary="Get review queue",
    description=(
        "Returns mapping review items from the governance queue. "
        "Can be filtered by review status and OMOP domain."
    ),
)
async def get_review_queue(
    status: ReviewStatus | None = Query(None, description="Filter by review status"),
    domain: str | None = Query(None, description="Filter by OMOP domain"),
    limit: int = Query(50, ge=1, le=500, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> list[ReviewItemResponse]:
    """Get items from the terminology review queue."""
    service = get_terminology_governance_service()
    return service.get_review_queue(
        status=status,
        domain=domain,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=ReviewItemResponse,
    status_code=201,
    summary="Submit mapping for review",
    description=(
        "Submit an OMOP concept mapping for terminology expert review. "
        "Typically used for low-confidence mappings or manual review requests."
    ),
)
async def submit_for_review(
    submission: ReviewSubmission,
) -> ReviewItemResponse:
    """Submit a mapping for terminology review."""
    service = get_terminology_governance_service()
    return service.submit_for_review(
        mention_id=submission.mention_id,
        candidate_id=submission.candidate_id,
        concept_name="",  # Caller may not know; populated by pipeline
        concept_id=0,
        confidence=0.0,
        domain="",
        reason=submission.reason,
        submitted_by=submission.submitted_by,
    )


@router.put(
    "/{review_id}/approve",
    response_model=ReviewItemResponse,
    summary="Approve a mapping",
    description=(
        "Approve a mapping in the review queue, marking it as vetted "
        "by a terminology expert."
    ),
)
async def approve_mapping(
    review_id: str,
    decision: ReviewDecision,
) -> ReviewItemResponse:
    """Approve a mapping review item."""
    service = get_terminology_governance_service()
    result = service.approve_mapping(
        review_id=review_id,
        reviewer_id=decision.reviewer_id,
        notes=decision.notes,
    )
    if result is None:
        raise HTTPException(status_code=404, detail=f"Review item {review_id} not found")
    return result


@router.put(
    "/{review_id}/reject",
    response_model=ReviewItemResponse,
    summary="Reject a mapping",
    description=(
        "Reject a mapping in the review queue, optionally suggesting "
        "an alternative OMOP concept."
    ),
)
async def reject_mapping(
    review_id: str,
    decision: ReviewDecision,
) -> ReviewItemResponse:
    """Reject a mapping review item."""
    service = get_terminology_governance_service()
    result = service.reject_mapping(
        review_id=review_id,
        reviewer_id=decision.reviewer_id,
        reason=decision.notes,
        suggested_concept_id=decision.suggested_concept_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail=f"Review item {review_id} not found")
    return result


@router.put(
    "/{review_id}/escalate",
    response_model=ReviewItemResponse,
    summary="Escalate a mapping",
    description=(
        "Escalate a mapping for senior terminology expert review."
    ),
)
async def escalate_mapping(
    review_id: str,
    decision: ReviewDecision,
) -> ReviewItemResponse:
    """Escalate a mapping review item."""
    service = get_terminology_governance_service()
    result = service.escalate_mapping(
        review_id=review_id,
        reviewer_id=decision.reviewer_id,
        reason=decision.notes,
    )
    if result is None:
        raise HTTPException(status_code=404, detail=f"Review item {review_id} not found")
    return result


@router.get(
    "/stats",
    response_model=ReviewStats,
    summary="Get review statistics",
    description=(
        "Returns aggregate statistics for the review queue including "
        "counts by status and average review time."
    ),
)
async def get_review_stats() -> ReviewStats:
    """Get review queue statistics."""
    service = get_terminology_governance_service()
    return service.get_review_stats()
