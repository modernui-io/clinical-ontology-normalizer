"""Pipeline Scheduling API endpoints.

Provides endpoints for managing scheduled ETL pipeline runs
including schedule CRUD, triggering runs, and viewing history.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.pipeline_scheduling_service import (
    RunStatus,
    ScheduleFrequency,
    ScheduleStatus,
    get_pipeline_scheduling_service,
)

router = APIRouter(prefix="/pipeline-scheduling", tags=["Pipeline Scheduling"])


# ============================================================================
# Request/Response Models
# ============================================================================


class CreateScheduleRequest(BaseModel):
    """Request to create a schedule."""

    pipeline_id: str = Field(..., description="Pipeline ID to schedule")
    name: str = Field(..., min_length=1, max_length=255, description="Schedule name")
    description: str = Field(default="", description="Schedule description")
    frequency: str = Field(..., description="Frequency: hourly, daily, weekly, monthly, custom")
    cron_expression: str | None = Field(None, description="Cron expression for custom frequency")
    timezone: str = Field(default="UTC", description="Timezone for scheduling")
    retry_on_failure: bool = Field(default=True, description="Retry on failure")
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retries")
    timeout_minutes: int = Field(default=60, ge=1, le=480, description="Execution timeout")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    model_config = {
        "json_schema_extra": {
            "example": {
                "pipeline_id": "pl-patient-sync",
                "name": "Daily Patient Sync",
                "description": "Synchronize patient data daily",
                "frequency": "daily",
                "timezone": "America/New_York",
                "retry_on_failure": True,
                "max_retries": 3,
                "timeout_minutes": 120,
            }
        }
    }


class UpdateScheduleRequest(BaseModel):
    """Request to update a schedule."""

    name: str | None = Field(None, description="Schedule name")
    description: str | None = Field(None, description="Schedule description")
    frequency: str | None = Field(None, description="Frequency")
    cron_expression: str | None = Field(None, description="Cron expression")
    timezone: str | None = Field(None, description="Timezone")
    status: str | None = Field(None, description="Status: active, paused, disabled")
    retry_on_failure: bool | None = Field(None, description="Retry on failure")
    max_retries: int | None = Field(None, ge=0, le=10, description="Maximum retries")
    timeout_minutes: int | None = Field(None, ge=1, le=480, description="Timeout")


class ScheduleResponse(BaseModel):
    """Response for a schedule."""

    id: str = Field(..., description="Schedule ID")
    pipeline_id: str = Field(..., description="Pipeline ID")
    name: str = Field(..., description="Schedule name")
    description: str = Field(..., description="Description")
    frequency: str = Field(..., description="Frequency")
    cron_expression: str | None = Field(None, description="Cron expression")
    timezone: str = Field(..., description="Timezone")
    status: str = Field(..., description="Status")
    created_at: str = Field(..., description="Created timestamp")
    updated_at: str = Field(..., description="Updated timestamp")
    next_run_at: str | None = Field(None, description="Next scheduled run")
    last_run_at: str | None = Field(None, description="Last run timestamp")
    last_run_status: str | None = Field(None, description="Last run status")
    retry_on_failure: bool = Field(..., description="Retry on failure")
    max_retries: int = Field(..., description="Maximum retries")
    timeout_minutes: int = Field(..., description="Timeout in minutes")


class ScheduleListResponse(BaseModel):
    """Response for list of schedules."""

    total: int = Field(..., description="Total schedules")
    schedules: list[ScheduleResponse] = Field(..., description="Schedule list")


class RunResponse(BaseModel):
    """Response for a pipeline run."""

    id: str = Field(..., description="Run ID")
    schedule_id: str = Field(..., description="Schedule ID")
    pipeline_id: str = Field(..., description="Pipeline ID")
    status: str = Field(..., description="Run status")
    started_at: str = Field(..., description="Start timestamp")
    completed_at: str | None = Field(None, description="Completion timestamp")
    duration_seconds: float | None = Field(None, description="Duration in seconds")
    records_processed: int = Field(..., description="Records processed")
    records_failed: int = Field(..., description="Records failed")
    triggered_by: str = Field(..., description="How the run was triggered")
    error_message: str | None = Field(None, description="Error message if failed")


class RunListResponse(BaseModel):
    """Response for list of runs."""

    total: int = Field(..., description="Total runs")
    runs: list[RunResponse] = Field(..., description="Run list")


class StatsResponse(BaseModel):
    """Response for scheduling statistics."""

    total_schedules: int
    active_schedules: int
    schedules_by_status: dict[str, int]
    schedules_by_frequency: dict[str, int]
    total_runs: int
    runs_by_status: dict[str, int]


class FrequenciesResponse(BaseModel):
    """Response for available frequencies."""

    frequencies: list[dict[str, str]]


class StatusesResponse(BaseModel):
    """Response for available statuses."""

    statuses: list[dict[str, str]]


# ============================================================================
# Helper Functions
# ============================================================================


def _schedule_to_response(schedule) -> ScheduleResponse:
    """Convert PipelineSchedule to response model."""
    return ScheduleResponse(
        id=schedule.id,
        pipeline_id=schedule.pipeline_id,
        name=schedule.name,
        description=schedule.description,
        frequency=schedule.frequency.value,
        cron_expression=schedule.cron_expression,
        timezone=schedule.timezone,
        status=schedule.status.value,
        created_at=schedule.created_at.isoformat(),
        updated_at=schedule.updated_at.isoformat(),
        next_run_at=schedule.next_run_at.isoformat() if schedule.next_run_at else None,
        last_run_at=schedule.last_run_at.isoformat() if schedule.last_run_at else None,
        last_run_status=schedule.last_run_status.value if schedule.last_run_status else None,
        retry_on_failure=schedule.retry_on_failure,
        max_retries=schedule.max_retries,
        timeout_minutes=schedule.timeout_minutes,
    )


def _run_to_response(run) -> RunResponse:
    """Convert PipelineRun to response model."""
    return RunResponse(
        id=run.id,
        schedule_id=run.schedule_id,
        pipeline_id=run.pipeline_id,
        status=run.status.value,
        started_at=run.started_at.isoformat(),
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        duration_seconds=run.duration_seconds,
        records_processed=run.records_processed,
        records_failed=run.records_failed,
        triggered_by=run.triggered_by,
        error_message=run.error_message,
    )


# ============================================================================
# Endpoints - Static routes first
# ============================================================================


@router.get(
    "",
    response_model=ScheduleListResponse,
    summary="List schedules",
    description="Get a list of pipeline schedules.",
)
async def list_schedules(
    pipeline_id: str | None = Query(None, description="Filter by pipeline ID"),
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
) -> ScheduleListResponse:
    """List pipeline schedules."""
    service = get_pipeline_scheduling_service()

    status_enum = None
    if status:
        try:
            status_enum = ScheduleStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    schedules = service.list_schedules(
        pipeline_id=pipeline_id,
        status=status_enum,
        limit=limit,
    )

    return ScheduleListResponse(
        total=len(schedules),
        schedules=[_schedule_to_response(s) for s in schedules],
    )


@router.post(
    "",
    response_model=ScheduleResponse,
    summary="Create schedule",
    description="Create a new pipeline schedule.",
)
async def create_schedule(request: CreateScheduleRequest) -> ScheduleResponse:
    """Create a new schedule."""
    service = get_pipeline_scheduling_service()

    try:
        frequency = ScheduleFrequency(request.frequency)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid frequency: {request.frequency}")

    schedule = service.create_schedule(
        pipeline_id=request.pipeline_id,
        name=request.name,
        description=request.description,
        frequency=frequency,
        created_by="anonymous",
        cron_expression=request.cron_expression,
        timezone=request.timezone,
        retry_on_failure=request.retry_on_failure,
        max_retries=request.max_retries,
        timeout_minutes=request.timeout_minutes,
        metadata=request.metadata,
    )

    return _schedule_to_response(schedule)


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Get statistics",
    description="Get pipeline scheduling statistics.",
)
async def get_stats() -> StatsResponse:
    """Get scheduling statistics."""
    service = get_pipeline_scheduling_service()
    stats = service.get_stats()
    return StatsResponse(**stats)


@router.get(
    "/frequencies",
    response_model=FrequenciesResponse,
    summary="List frequencies",
    description="Get available schedule frequencies.",
)
async def list_frequencies() -> FrequenciesResponse:
    """List available frequencies."""
    frequencies = [
        {"value": f.value, "name": f.name.replace("_", " ").title()}
        for f in ScheduleFrequency
    ]
    return FrequenciesResponse(frequencies=frequencies)


@router.get(
    "/statuses",
    response_model=StatusesResponse,
    summary="List statuses",
    description="Get available schedule statuses.",
)
async def list_statuses() -> StatusesResponse:
    """List available statuses."""
    statuses = [
        {"value": s.value, "name": s.name.replace("_", " ").title()}
        for s in ScheduleStatus
    ]
    return StatusesResponse(statuses=statuses)


@router.get(
    "/runs",
    response_model=RunListResponse,
    summary="List runs",
    description="Get a list of pipeline runs.",
)
async def list_runs(
    pipeline_id: str | None = Query(None, description="Filter by pipeline ID"),
    schedule_id: str | None = Query(None, description="Filter by schedule ID"),
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
) -> RunListResponse:
    """List pipeline runs."""
    service = get_pipeline_scheduling_service()

    status_enum = None
    if status:
        try:
            status_enum = RunStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    runs = service.list_runs(
        pipeline_id=pipeline_id,
        schedule_id=schedule_id,
        status=status_enum,
        limit=limit,
    )

    return RunListResponse(
        total=len(runs),
        runs=[_run_to_response(r) for r in runs],
    )


# ============================================================================
# Endpoints - Parameterized routes
# ============================================================================


@router.get(
    "/{schedule_id}",
    response_model=ScheduleResponse,
    summary="Get schedule",
    description="Get a specific schedule by ID.",
)
async def get_schedule(schedule_id: str) -> ScheduleResponse:
    """Get a specific schedule."""
    service = get_pipeline_scheduling_service()
    schedule = service.get_schedule(schedule_id)

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    return _schedule_to_response(schedule)


@router.put(
    "/{schedule_id}",
    response_model=ScheduleResponse,
    summary="Update schedule",
    description="Update a schedule.",
)
async def update_schedule(schedule_id: str, request: UpdateScheduleRequest) -> ScheduleResponse:
    """Update a schedule."""
    service = get_pipeline_scheduling_service()

    updates = {}
    if request.name is not None:
        updates["name"] = request.name
    if request.description is not None:
        updates["description"] = request.description
    if request.frequency is not None:
        try:
            ScheduleFrequency(request.frequency)
            updates["frequency"] = request.frequency
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid frequency: {request.frequency}")
    if request.cron_expression is not None:
        updates["cron_expression"] = request.cron_expression
    if request.timezone is not None:
        updates["timezone"] = request.timezone
    if request.status is not None:
        try:
            ScheduleStatus(request.status)
            updates["status"] = request.status
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {request.status}")
    if request.retry_on_failure is not None:
        updates["retry_on_failure"] = request.retry_on_failure
    if request.max_retries is not None:
        updates["max_retries"] = request.max_retries
    if request.timeout_minutes is not None:
        updates["timeout_minutes"] = request.timeout_minutes

    schedule = service.update_schedule(schedule_id, **updates)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    return _schedule_to_response(schedule)


@router.delete(
    "/{schedule_id}",
    summary="Delete schedule",
    description="Delete a schedule.",
)
async def delete_schedule(schedule_id: str) -> dict[str, bool]:
    """Delete a schedule."""
    service = get_pipeline_scheduling_service()
    deleted = service.delete_schedule(schedule_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Schedule not found")

    return {"deleted": True}


@router.post(
    "/{schedule_id}/pause",
    response_model=ScheduleResponse,
    summary="Pause schedule",
    description="Pause a schedule.",
)
async def pause_schedule(schedule_id: str) -> ScheduleResponse:
    """Pause a schedule."""
    service = get_pipeline_scheduling_service()
    schedule = service.pause_schedule(schedule_id)

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    return _schedule_to_response(schedule)


@router.post(
    "/{schedule_id}/resume",
    response_model=ScheduleResponse,
    summary="Resume schedule",
    description="Resume a paused schedule.",
)
async def resume_schedule(schedule_id: str) -> ScheduleResponse:
    """Resume a paused schedule."""
    service = get_pipeline_scheduling_service()
    schedule = service.resume_schedule(schedule_id)

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    return _schedule_to_response(schedule)


@router.post(
    "/{schedule_id}/trigger",
    response_model=RunResponse,
    summary="Trigger run",
    description="Manually trigger a pipeline run.",
)
async def trigger_run(schedule_id: str) -> RunResponse:
    """Manually trigger a run."""
    service = get_pipeline_scheduling_service()
    schedule = service.get_schedule(schedule_id)

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    run = service.trigger_run(schedule.pipeline_id, triggered_by="manual")
    return _run_to_response(run)


@router.get(
    "/{schedule_id}/runs",
    response_model=RunListResponse,
    summary="Get schedule runs",
    description="Get runs for a specific schedule.",
)
async def get_schedule_runs(
    schedule_id: str,
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
) -> RunListResponse:
    """Get runs for a schedule."""
    service = get_pipeline_scheduling_service()

    schedule = service.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    runs = service.list_runs(schedule_id=schedule_id, limit=limit)

    return RunListResponse(
        total=len(runs),
        runs=[_run_to_response(r) for r in runs],
    )
