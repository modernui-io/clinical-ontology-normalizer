"""Business Continuity Testing API endpoints (COO-2).

Provides endpoints for managing tabletop exercise scenarios, scheduling
and tracking exercises, validating recovery procedures, and monitoring
BC program metrics.

Endpoints:
    GET    /api/v1/operations/bc/scenarios              - List tabletop scenarios
    GET    /api/v1/operations/bc/scenarios/{id}          - Scenario detail
    POST   /api/v1/operations/bc/exercises               - Schedule exercise
    GET    /api/v1/operations/bc/exercises                - List exercises
    GET    /api/v1/operations/bc/exercises/{id}           - Exercise detail
    PUT    /api/v1/operations/bc/exercises/{id}           - Update exercise
    GET    /api/v1/operations/bc/metrics                  - BC program metrics
    POST   /api/v1/operations/bc/validate-procedures      - Validate recovery procedures
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.business_continuity import (
    BCMetrics,
    ExerciseCreate,
    ExerciseListResponse,
    ExerciseResponse,
    ExerciseStatus,
    ExerciseUpdate,
    ProcedureValidationReport,
    Severity,
    TabletopScenario,
)
from app.services.business_continuity_service import get_business_continuity_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/operations/bc",
    tags=["Business Continuity"],
)


# ============================================================================
# Helper
# ============================================================================


def _exercise_to_response(record) -> ExerciseResponse:
    """Convert an ExerciseRecord to an ExerciseResponse."""
    return ExerciseResponse(
        id=record.id,
        scenario_id=record.scenario_id,
        scenario_title=record.scenario_title,
        scheduled_date=record.scheduled_date,
        conducted_date=record.conducted_date,
        participants=record.participants,
        status=record.status,
        actual_rto=record.actual_rto,
        actual_rpo=record.actual_rpo,
        findings=record.findings,
        action_items=record.action_items,
        success_criteria_results=record.success_criteria_results,
        notes=record.notes,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


# ============================================================================
# Scenario Endpoints
# ============================================================================


@router.get(
    "/scenarios",
    response_model=list[TabletopScenario],
    summary="List tabletop scenarios",
    description="List all pre-defined tabletop exercise scenarios with optional severity filter.",
)
async def list_scenarios(
    severity: Severity | None = Query(
        default=None, description="Filter by severity level"
    ),
) -> list[TabletopScenario]:
    """List all tabletop scenarios."""
    service = get_business_continuity_service()
    return service.list_scenarios(severity=severity)


@router.get(
    "/scenarios/{scenario_id}",
    response_model=TabletopScenario,
    summary="Get scenario detail",
    description="Get full details of a specific tabletop scenario including recovery steps and success criteria.",
)
async def get_scenario(scenario_id: str) -> TabletopScenario:
    """Get a specific tabletop scenario."""
    service = get_business_continuity_service()
    scenario = service.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario not found: {scenario_id}",
        )
    return scenario


# ============================================================================
# Exercise Endpoints
# ============================================================================


@router.post(
    "/exercises",
    response_model=ExerciseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule an exercise",
    description="Schedule a new tabletop exercise for a specific scenario.",
)
async def schedule_exercise(request: ExerciseCreate) -> ExerciseResponse:
    """Schedule a new exercise."""
    service = get_business_continuity_service()
    try:
        record = service.schedule_exercise(
            scenario_id=request.scenario_id,
            scheduled_date=request.scheduled_date,
            participants=request.participants,
            notes=request.notes,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    logger.info("Exercise scheduled via API: %s", record.id)
    return _exercise_to_response(record)


@router.get(
    "/exercises",
    response_model=ExerciseListResponse,
    summary="List exercises",
    description="List all exercises with optional filtering by scenario and status.",
)
async def list_exercises(
    scenario_id: str | None = Query(
        default=None, description="Filter by scenario ID"
    ),
    exercise_status: ExerciseStatus | None = Query(
        default=None, alias="status", description="Filter by exercise status"
    ),
    limit: int = Query(default=100, ge=1, le=1000, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
) -> ExerciseListResponse:
    """List exercises with optional filters."""
    service = get_business_continuity_service()
    exercises, total = service.list_exercises(
        scenario_id=scenario_id,
        status=exercise_status,
        limit=limit,
        offset=offset,
    )
    return ExerciseListResponse(
        exercises=[_exercise_to_response(e) for e in exercises],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/exercises/{exercise_id}",
    response_model=ExerciseResponse,
    summary="Get exercise detail",
    description="Get full details of a specific exercise including findings and action items.",
)
async def get_exercise(exercise_id: str) -> ExerciseResponse:
    """Get a specific exercise by ID."""
    service = get_business_continuity_service()
    record = service.get_exercise(exercise_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exercise not found: {exercise_id}",
        )
    return _exercise_to_response(record)


@router.put(
    "/exercises/{exercise_id}",
    response_model=ExerciseResponse,
    summary="Update an exercise",
    description="Update exercise status, record results, add findings and action items.",
)
async def update_exercise(
    exercise_id: str, request: ExerciseUpdate
) -> ExerciseResponse:
    """Update an exercise record."""
    service = get_business_continuity_service()
    try:
        record = service.update_exercise(
            exercise_id=exercise_id,
            status=request.status,
            conducted_date=request.conducted_date,
            participants=request.participants,
            actual_rto=request.actual_rto,
            actual_rpo=request.actual_rpo,
            findings=request.findings,
            action_items=request.action_items,
            success_criteria_results=request.success_criteria_results,
            notes=request.notes,
        )
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    return _exercise_to_response(record)


# ============================================================================
# Metrics Endpoint
# ============================================================================


@router.get(
    "/metrics",
    response_model=BCMetrics,
    summary="Get BC program metrics",
    description="Get comprehensive business continuity program metrics including exercise frequency, RTO/RPO compliance, and readiness score.",
)
async def get_bc_metrics() -> BCMetrics:
    """Get BC program metrics."""
    service = get_business_continuity_service()
    return service.get_metrics()


# ============================================================================
# Procedure Validation Endpoint
# ============================================================================


@router.post(
    "/validate-procedures",
    response_model=ProcedureValidationReport,
    summary="Validate recovery procedures",
    description="Validate that recovery procedures are current, complete, and properly documented.",
)
async def validate_procedures(
    scenario_ids: list[str] | None = None,
) -> ProcedureValidationReport:
    """Validate recovery procedures for scenarios."""
    service = get_business_continuity_service()
    return service.validate_procedures(scenario_ids=scenario_ids)
