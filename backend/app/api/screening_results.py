"""Screening Results API endpoints.

Exposes persisted screening outcomes produced by the automated
Metriport consent-to-screening pipeline, manual screening, or bulk
screening runs.

Endpoints:
    GET /api/v1/screening-results           - List/filter screening results
    GET /api/v1/screening-results/{id}      - Get a single screening result
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import Permission, PermissionChecker
from app.models.screening_result import (
    OverallScreeningStatus,
    ScreeningResult,
    ScreeningTrigger,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/screening-results", tags=["Screening Results"])


# ==============================================================================
# Response schemas
# ==============================================================================


class ScreeningResultResponse(BaseModel):
    """Single screening result."""

    id: str
    patient_id: str
    trial_id: str
    trial_name: str | None = None
    screening_date: datetime
    overall_status: str
    match_score: float | None = None
    inclusion_met: int | None = None
    inclusion_total: int | None = None
    exclusion_triggered: int | None = None
    exclusion_total: int | None = None
    criterion_results: dict | None = None
    safety_blocked: bool | None = None
    triggered_by: str
    notes: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ScreeningResultListResponse(BaseModel):
    """Paginated list of screening results."""

    results: list[ScreeningResultResponse]
    total: int
    offset: int
    limit: int


# ==============================================================================
# Endpoints
# ==============================================================================


@router.get(
    "",
    response_model=ScreeningResultListResponse,
    summary="List screening results",
    description=(
        "Retrieve persisted screening results with optional filtering by "
        "patient_id, trial_id, overall_status, and triggered_by."
    ),
)
async def list_screening_results(
    request: Request,
    patient_id: str | None = Query(None, description="Filter by patient ID"),
    trial_id: str | None = Query(None, description="Filter by trial ID"),
    overall_status: OverallScreeningStatus | None = Query(
        None, description="Filter by outcome status"
    ),
    triggered_by: ScreeningTrigger | None = Query(
        None, description="Filter by trigger type (webhook, manual, bulk)"
    ),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    _perm: None = Depends(PermissionChecker([Permission.SCREEN_PATIENTS])),
) -> ScreeningResultListResponse:
    """List screening results with optional filters."""
    filters = []
    if patient_id:
        filters.append(ScreeningResult.patient_id == patient_id)
    if trial_id:
        filters.append(ScreeningResult.trial_id == trial_id)
    if overall_status:
        filters.append(ScreeningResult.overall_status == overall_status)
    if triggered_by:
        filters.append(ScreeningResult.triggered_by == triggered_by)

    # Count query
    count_stmt = select(func.count(ScreeningResult.id)).where(*filters)
    total = (await session.execute(count_stmt)).scalar_one()

    # Data query
    stmt = (
        select(ScreeningResult)
        .where(*filters)
        .order_by(ScreeningResult.screening_date.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()

    results = [
        ScreeningResultResponse.model_validate(row) for row in rows
    ]
    return ScreeningResultListResponse(
        results=results, total=total, offset=offset, limit=limit
    )


@router.get(
    "/{result_id}",
    response_model=ScreeningResultResponse,
    summary="Get a screening result",
    description="Retrieve a single screening result by ID.",
)
async def get_screening_result(
    result_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
    _perm: None = Depends(PermissionChecker([Permission.SCREEN_PATIENTS])),
) -> ScreeningResultResponse:
    """Get a single screening result by ID."""
    stmt = select(ScreeningResult).where(ScreeningResult.id == result_id)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Screening result {result_id} not found",
        )
    return ScreeningResultResponse.model_validate(row)
