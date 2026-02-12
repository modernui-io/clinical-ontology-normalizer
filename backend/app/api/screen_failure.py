"""Screen Failure Analytics API endpoints.

Full REST interface for screening records plus analytics, recruitment
funnel, criteria difficulty, and near-miss patient endpoints.

Endpoints:
    GET    /screen-failure/records                          - List screening records
    GET    /screen-failure/records/{record_id}              - Get single record
    POST   /screen-failure/records                          - Create screening record
    PUT    /screen-failure/records/{record_id}              - Update screening record
    DELETE /screen-failure/records/{record_id}              - Delete screening record
    GET    /screen-failure/{trial_id}/analytics             - Failure analytics report
    GET    /screen-failure/{trial_id}/funnel                - Recruitment funnel
    GET    /screen-failure/{trial_id}/criteria-difficulty   - Per-criterion pass rates
    GET    /screen-failure/{trial_id}/near-miss             - Near-miss patients
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.schemas.screen_failure import (
    CriteriaDifficultyReport,
    CriterionType,
    FailingCriterion,
    FailureAnalyticsReport,
    NearMissReport,
    RecruitmentFunnel,
    ScreeningOutcome,
    ScreeningRecord,
)
from app.services.screen_failure_service import get_screen_failure_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/screen-failure",
    tags=["Screen Failure Analytics"],
)


# ---------------------------------------------------------------------------
# Request / response helpers
# ---------------------------------------------------------------------------


class ScreeningRecordCreate(BaseModel):
    """Payload for creating a screening record."""

    trial_id: str = Field(..., description="Trial ID")
    patient_id: str = Field(..., description="Patient ID")
    outcome: ScreeningOutcome = Field(..., description="Screening outcome")
    failing_criteria: list[FailingCriterion] = Field(
        default_factory=list,
        description="Criteria the patient failed",
    )
    match_score: float | None = Field(None, ge=0.0, le=1.0, description="Overall match score")
    metadata: dict | None = Field(None, description="Arbitrary extra metadata")


class ScreeningRecordUpdate(BaseModel):
    """Payload for updating a screening record."""

    outcome: ScreeningOutcome | None = None
    failing_criteria: list[FailingCriterion] | None = None
    match_score: float | None = Field(None, ge=0.0, le=1.0)
    metadata: dict | None = None


class ScreeningRecordListResponse(BaseModel):
    """Paginated list of screening records."""

    items: list[ScreeningRecord]
    total: int = Field(ge=0)


# ---------------------------------------------------------------------------
# CRUD: Screening Records
# ---------------------------------------------------------------------------


@router.get(
    "/records",
    response_model=ScreeningRecordListResponse,
    summary="List screening records",
    description="Retrieve screening records with optional filtering by trial and outcome.",
)
async def list_screening_records(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    outcome: Optional[ScreeningOutcome] = Query(None, description="Filter by outcome"),
) -> ScreeningRecordListResponse:
    svc = get_screen_failure_service()
    items = svc.list_screening_records(trial_id=trial_id, outcome=outcome)
    return ScreeningRecordListResponse(items=items, total=len(items))


@router.get(
    "/records/{record_id}",
    response_model=ScreeningRecord,
    summary="Get a screening record",
)
async def get_screening_record(record_id: str) -> ScreeningRecord:
    svc = get_screen_failure_service()
    record = svc.get_screening_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Screening record '{record_id}' not found")
    return record


@router.post(
    "/records",
    response_model=ScreeningRecord,
    status_code=201,
    summary="Create a screening record",
)
async def create_screening_record(payload: ScreeningRecordCreate) -> ScreeningRecord:
    svc = get_screen_failure_service()
    return svc.create_screening_record(
        trial_id=payload.trial_id,
        patient_id=payload.patient_id,
        outcome=payload.outcome,
        failing_criteria=payload.failing_criteria or None,
        match_score=payload.match_score,
        metadata=payload.metadata,
    )


@router.put(
    "/records/{record_id}",
    response_model=ScreeningRecord,
    summary="Update a screening record",
)
async def update_screening_record(
    record_id: str,
    payload: ScreeningRecordUpdate,
) -> ScreeningRecord:
    svc = get_screen_failure_service()
    updates = payload.model_dump(exclude_unset=True)
    updated = svc.update_screening_record(record_id, **updates)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Screening record '{record_id}' not found")
    return updated


@router.delete(
    "/records/{record_id}",
    status_code=204,
    summary="Delete a screening record",
)
async def delete_screening_record(record_id: str) -> None:
    svc = get_screen_failure_service()
    deleted = svc.delete_screening_record(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Screening record '{record_id}' not found")


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


@router.get(
    "/{trial_id}/analytics",
    response_model=FailureAnalyticsReport,
    summary="Failure analytics report",
    description=(
        "Aggregated screen-failure analytics for a trial: top failing "
        "criteria, failure rate over time, failure distribution by "
        "criterion type, and near-miss count."
    ),
)
async def get_failure_analytics(
    trial_id: str,
    date_from: Optional[datetime] = Query(None, description="Start of date range"),
    date_to: Optional[datetime] = Query(None, description="End of date range"),
    top_n: int = Query(10, ge=1, le=100, description="Number of top failing criteria"),
) -> FailureAnalyticsReport:
    svc = get_screen_failure_service()
    return svc.get_failure_analytics(trial_id, date_from=date_from, date_to=date_to, top_n=top_n)


@router.get(
    "/{trial_id}/funnel",
    response_model=RecruitmentFunnel,
    summary="Recruitment funnel",
    description="End-to-end recruitment funnel for a trial.",
)
async def get_recruitment_funnel(
    trial_id: str,
    enrolled_count: Optional[int] = Query(None, ge=0, description="Externally-provided enrolled count"),
) -> RecruitmentFunnel:
    svc = get_screen_failure_service()
    return svc.get_recruitment_funnel(trial_id, enrolled_count=enrolled_count)


@router.get(
    "/{trial_id}/criteria-difficulty",
    response_model=CriteriaDifficultyReport,
    summary="Per-criterion pass rates",
    description="Per-criterion pass rate sorted by difficulty (hardest first).",
)
async def get_criteria_difficulty(trial_id: str) -> CriteriaDifficultyReport:
    svc = get_screen_failure_service()
    return svc.get_criteria_difficulty(trial_id)


@router.get(
    "/{trial_id}/near-miss",
    response_model=NearMissReport,
    summary="Near-miss patients",
    description="Patients who failed by 1-2 criteria -- high-value leads.",
)
async def get_near_miss_patients(
    trial_id: str,
    max_failures: int = Query(2, ge=1, le=10, description="Max failing criteria for near miss"),
) -> NearMissReport:
    svc = get_screen_failure_service()
    return svc.get_near_miss_patients(trial_id, max_failures=max_failures)
