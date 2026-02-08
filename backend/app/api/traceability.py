"""Requirements Traceability API endpoints (VP-Quality-3).

Provides endpoints for managing requirements traceability across the full
lifecycle: requirements -> design -> code -> tests -> validation.

Endpoints:
    GET    /api/v1/quality/traceability/requirements          - List all requirements
    GET    /api/v1/quality/traceability/requirements/{id}     - Get requirement with trace links
    POST   /api/v1/quality/traceability/requirements          - Create requirement
    PUT    /api/v1/quality/traceability/requirements/{id}     - Update requirement/links
    GET    /api/v1/quality/traceability/coverage              - Coverage analysis report
    GET    /api/v1/quality/traceability/gaps                  - Requirements with gaps
    POST   /api/v1/quality/traceability/impact-analysis       - Impact analysis for code changes
    GET    /api/v1/quality/traceability/matrix                - Full traceability matrix
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.traceability import (
    CoverageLevel,
    CoverageReport,
    GapReport,
    ImpactAnalysisRequest,
    ImpactAnalysisResponse,
    RequirementCategory,
    RequirementCreate,
    RequirementListResponse,
    RequirementPriority,
    RequirementResponse,
    RequirementStatus,
    RequirementUpdate,
    TraceabilityMatrix,
)
from app.services.traceability_service import get_traceability_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/quality/traceability",
    tags=["Requirements Traceability"],
)


# ============================================================================
# Requirements CRUD
# ============================================================================


@router.get(
    "/requirements",
    response_model=RequirementListResponse,
    summary="List all requirements",
    description="List requirements with optional filtering by category, priority, status, and coverage level.",
)
async def list_requirements(
    category: RequirementCategory | None = Query(default=None, description="Filter by category"),
    priority: RequirementPriority | None = Query(default=None, description="Filter by priority"),
    req_status: RequirementStatus | None = Query(default=None, alias="status", description="Filter by status"),
    coverage: CoverageLevel | None = Query(default=None, description="Filter by coverage level"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=200, description="Page size"),
) -> RequirementListResponse:
    """List all requirements with optional filters."""
    svc = get_traceability_service()
    requirements, total = svc.list_requirements(
        category=category,
        priority=priority,
        status=req_status,
        coverage=coverage,
        page=page,
        page_size=page_size,
    )
    return RequirementListResponse(
        requirements=requirements,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/requirements/{requirement_id}",
    response_model=RequirementResponse,
    summary="Get requirement detail",
    description="Get a single requirement by ID with all trace links.",
)
async def get_requirement(requirement_id: str) -> RequirementResponse:
    """Get a single requirement by ID."""
    svc = get_traceability_service()
    result = svc.get_requirement(requirement_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requirement {requirement_id} not found",
        )
    return result


@router.post(
    "/requirements",
    response_model=RequirementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create requirement",
    description="Create a new requirement with optional trace links.",
)
async def create_requirement(data: RequirementCreate) -> RequirementResponse:
    """Create a new requirement."""
    svc = get_traceability_service()
    try:
        return svc.create_requirement(data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.put(
    "/requirements/{requirement_id}",
    response_model=RequirementResponse,
    summary="Update requirement",
    description="Update a requirement's fields and/or trace links.",
)
async def update_requirement(
    requirement_id: str,
    data: RequirementUpdate,
) -> RequirementResponse:
    """Update an existing requirement."""
    svc = get_traceability_service()
    result = svc.update_requirement(requirement_id, data)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requirement {requirement_id} not found",
        )
    return result


# ============================================================================
# Coverage Analysis
# ============================================================================


@router.get(
    "/coverage",
    response_model=CoverageReport,
    summary="Coverage analysis report",
    description="Generate a comprehensive coverage analysis showing which requirements have full traceability.",
)
async def get_coverage() -> CoverageReport:
    """Get coverage analysis report."""
    svc = get_traceability_service()
    return svc.get_coverage_report()


# ============================================================================
# Gap Analysis
# ============================================================================


@router.get(
    "/gaps",
    response_model=GapReport,
    summary="Gap analysis report",
    description="Identify requirements with incomplete traceability and provide recommendations.",
)
async def get_gaps() -> GapReport:
    """Get gap analysis report."""
    svc = get_traceability_service()
    return svc.get_gap_report()


# ============================================================================
# Impact Analysis
# ============================================================================


@router.post(
    "/impact-analysis",
    response_model=ImpactAnalysisResponse,
    summary="Impact analysis",
    description="Analyze which requirements are affected by changes to specific code files.",
)
async def analyze_impact(data: ImpactAnalysisRequest) -> ImpactAnalysisResponse:
    """Analyze impact of code changes on requirements."""
    svc = get_traceability_service()
    return svc.analyze_impact(data)


# ============================================================================
# Full Matrix
# ============================================================================


@router.get(
    "/matrix",
    response_model=TraceabilityMatrix,
    summary="Full traceability matrix",
    description="Generate the complete requirements traceability matrix with all trace links and coverage data.",
)
async def get_matrix() -> TraceabilityMatrix:
    """Get the full traceability matrix."""
    svc = get_traceability_service()
    return svc.get_matrix()
