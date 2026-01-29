"""ETL pipeline management API endpoints.

This module provides REST API endpoints for managing ETL pipelines,
schedules, and pipeline runs.

Endpoints:
    # Pipelines
    GET /etl/pipelines - List pipelines
    POST /etl/pipelines - Create pipeline
    GET /etl/pipelines/{id} - Get pipeline details
    PUT /etl/pipelines/{id} - Update pipeline
    DELETE /etl/pipelines/{id} - Delete pipeline
    PUT /etl/pipelines/{id}/schedule - Set schedule
    POST /etl/pipelines/{id}/run - Trigger manual run
    GET /etl/pipelines/{id}/runs - Get run history
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.services.source_config_service import (
    PipelineSchedule,
    PipelineStage,
    PipelineStatus,
    ScheduleFrequency,
    get_source_config_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/etl", tags=["ETL"])


# =============================================================================
# Pipeline Request/Response Models
# =============================================================================


class PipelineScheduleRequest(BaseModel):
    """Request body for pipeline schedule."""

    frequency: str = Field(
        default="manual",
        description="Schedule frequency",
        pattern="^(manual|hourly|daily|weekly|monthly|custom)$",
    )
    cron_expression: str | None = Field(default=None, description="Cron expression for custom")
    time_of_day: str = Field(default="00:00", pattern="^[0-2][0-9]:[0-5][0-9]$")
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    timezone: str = Field(default="UTC")
    enabled: bool = Field(default=False)


class PipelineStageRequest(BaseModel):
    """Request body for pipeline stage."""

    name: str = Field(..., min_length=1, max_length=100)
    stage_type: str = Field(..., description="Type of stage (extract, transform, load)")
    config: dict[str, Any] = Field(default_factory=dict)
    order: int = Field(default=0, ge=0)
    enabled: bool = Field(default=True)


class CreatePipelineRequest(BaseModel):
    """Request body for creating a new pipeline."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="", max_length=1000)
    source_id: str = Field(..., description="UUID of the data source")
    schedule: PipelineScheduleRequest | None = None
    stages: list[PipelineStageRequest] | None = None
    batch_size: int = Field(default=100, ge=1, le=10000)
    max_records: int | None = Field(default=None, ge=1)
    skip_on_error: bool = Field(default=True)


class UpdatePipelineRequest(BaseModel):
    """Request body for updating a pipeline."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    status: str | None = Field(default=None, pattern="^(active|paused|disabled)$")
    schedule: PipelineScheduleRequest | None = None
    stages: list[PipelineStageRequest] | None = None
    batch_size: int | None = Field(default=None, ge=1, le=10000)
    max_records: int | None = None
    skip_on_error: bool | None = None


class PipelineScheduleResponse(BaseModel):
    """Response containing pipeline schedule."""

    frequency: str
    cron_expression: str | None
    time_of_day: str
    day_of_week: int | None
    day_of_month: int | None
    timezone: str
    enabled: bool


class PipelineStageResponse(BaseModel):
    """Response containing pipeline stage."""

    name: str
    stage_type: str
    config: dict[str, Any]
    order: int
    enabled: bool


class PipelineRunResponse(BaseModel):
    """Response containing pipeline run details."""

    id: str
    pipeline_id: str
    status: str
    started_at: str
    completed_at: str | None
    records_processed: int
    records_failed: int
    error_message: str | None
    duration_seconds: float | None


class PipelineResponse(BaseModel):
    """Response containing pipeline details."""

    id: str
    name: str
    description: str
    source_id: str
    status: str
    schedule: PipelineScheduleResponse
    stages: list[PipelineStageResponse]
    batch_size: int
    max_records: int | None
    skip_on_error: bool
    created_at: str
    updated_at: str
    last_run_at: str | None
    last_run_status: str | None
    run_count: int


class PipelineListResponse(BaseModel):
    """Response containing list of pipelines."""

    pipelines: list[PipelineResponse]
    total: int


class PipelineRunListResponse(BaseModel):
    """Response containing list of pipeline runs."""

    runs: list[PipelineRunResponse]
    total: int


class TriggerPipelineResponse(BaseModel):
    """Response after triggering a pipeline run."""

    run_id: str
    pipeline_id: str
    status: str
    message: str


# =============================================================================
# Helper Functions
# =============================================================================


def _pipeline_to_response(pipeline: Any) -> PipelineResponse:
    """Convert a Pipeline to a PipelineResponse."""
    pipeline_dict = pipeline.to_dict()

    schedule = pipeline_dict["schedule"]
    stages = pipeline_dict["stages"]

    return PipelineResponse(
        id=pipeline_dict["id"],
        name=pipeline_dict["name"],
        description=pipeline_dict["description"],
        source_id=pipeline_dict["source_id"],
        status=pipeline_dict["status"],
        schedule=PipelineScheduleResponse(
            frequency=schedule["frequency"],
            cron_expression=schedule.get("cron_expression"),
            time_of_day=schedule["time_of_day"],
            day_of_week=schedule.get("day_of_week"),
            day_of_month=schedule.get("day_of_month"),
            timezone=schedule["timezone"],
            enabled=schedule["enabled"],
        ),
        stages=[
            PipelineStageResponse(
                name=s["name"],
                stage_type=s["stage_type"],
                config=s["config"],
                order=s["order"],
                enabled=s["enabled"],
            )
            for s in stages
        ],
        batch_size=pipeline_dict["batch_size"],
        max_records=pipeline_dict["max_records"],
        skip_on_error=pipeline_dict["skip_on_error"],
        created_at=pipeline_dict["created_at"],
        updated_at=pipeline_dict["updated_at"],
        last_run_at=pipeline_dict["last_run_at"],
        last_run_status=pipeline_dict["last_run_status"],
        run_count=pipeline_dict["run_count"],
    )


def _run_to_response(run: Any) -> PipelineRunResponse:
    """Convert a PipelineRun to a PipelineRunResponse."""
    run_dict = run.to_dict()

    return PipelineRunResponse(
        id=run_dict["id"],
        pipeline_id=run_dict["pipeline_id"],
        status=run_dict["status"],
        started_at=run_dict["started_at"],
        completed_at=run_dict["completed_at"],
        records_processed=run_dict["records_processed"],
        records_failed=run_dict["records_failed"],
        error_message=run_dict["error_message"],
        duration_seconds=run_dict["duration_seconds"],
    )


# =============================================================================
# Pipeline API Endpoints
# =============================================================================


@router.get(
    "/pipelines",
    response_model=PipelineListResponse,
    summary="List pipelines",
    description="Get a list of all ETL pipelines.",
)
async def list_pipelines(
    source_id: UUID | None = Query(default=None, description="Filter by source ID"),
    pipeline_status: str | None = Query(
        default=None,
        description="Filter by status (active, paused, disabled, error)",
    ),
    limit: int = Query(default=100, ge=1, le=1000),
) -> PipelineListResponse:
    """List all ETL pipelines.

    Args:
        source_id: Optional filter by source.
        pipeline_status: Optional filter by status.
        limit: Maximum pipelines to return.

    Returns:
        PipelineListResponse with list of pipelines.
    """
    try:
        service = get_source_config_service()

        status_filter = None
        if pipeline_status:
            try:
                status_filter = PipelineStatus(pipeline_status.lower())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid pipeline status: {pipeline_status}",
                )

        pipelines = await service.list_pipelines(
            source_id=source_id,
            status=status_filter,
            limit=limit,
        )

        return PipelineListResponse(
            pipelines=[_pipeline_to_response(p) for p in pipelines],
            total=len(pipelines),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list pipelines: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list pipelines",
        )


@router.post(
    "/pipelines",
    response_model=PipelineResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create pipeline",
    description="Create a new ETL pipeline.",
)
async def create_pipeline(
    request: CreatePipelineRequest,
) -> PipelineResponse:
    """Create a new ETL pipeline.

    Args:
        request: Pipeline configuration.

    Returns:
        Created PipelineResponse.
    """
    try:
        service = get_source_config_service()

        # Validate source exists
        try:
            source_uuid = UUID(request.source_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid source_id: {request.source_id}",
            )

        source = await service.get_source(source_uuid)
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source {request.source_id} not found",
            )

        # Convert schedule
        schedule = None
        if request.schedule:
            schedule = PipelineSchedule(
                frequency=ScheduleFrequency(request.schedule.frequency),
                cron_expression=request.schedule.cron_expression,
                time_of_day=request.schedule.time_of_day,
                day_of_week=request.schedule.day_of_week,
                day_of_month=request.schedule.day_of_month,
                timezone=request.schedule.timezone,
                enabled=request.schedule.enabled,
            )

        # Convert stages
        stages = None
        if request.stages:
            stages = [
                PipelineStage(
                    name=s.name,
                    stage_type=s.stage_type,
                    config=s.config,
                    order=s.order,
                    enabled=s.enabled,
                )
                for s in request.stages
            ]

        pipeline = await service.create_pipeline(
            name=request.name,
            source_id=source_uuid,
            description=request.description,
            schedule=schedule,
            stages=stages,
            batch_size=request.batch_size,
            max_records=request.max_records,
            skip_on_error=request.skip_on_error,
        )

        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create pipeline",
            )

        logger.info(f"Created pipeline {pipeline.id}: {request.name}")
        return _pipeline_to_response(pipeline)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create pipeline: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create pipeline",
        )


@router.get(
    "/pipelines/{pipeline_id}",
    response_model=PipelineResponse,
    summary="Get pipeline",
    description="Get details of a specific pipeline.",
)
async def get_pipeline(
    pipeline_id: UUID,
) -> PipelineResponse:
    """Get a specific pipeline by ID.

    Args:
        pipeline_id: Pipeline UUID.

    Returns:
        PipelineResponse with pipeline details.
    """
    try:
        service = get_source_config_service()
        pipeline = await service.get_pipeline(pipeline_id)

        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pipeline {pipeline_id} not found",
            )

        return _pipeline_to_response(pipeline)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get pipeline {pipeline_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get pipeline",
        )


@router.put(
    "/pipelines/{pipeline_id}",
    response_model=PipelineResponse,
    summary="Update pipeline",
    description="Update an existing pipeline configuration.",
)
async def update_pipeline(
    pipeline_id: UUID,
    request: UpdatePipelineRequest,
) -> PipelineResponse:
    """Update a pipeline configuration.

    Args:
        pipeline_id: Pipeline UUID.
        request: Updated configuration.

    Returns:
        Updated PipelineResponse.
    """
    try:
        service = get_source_config_service()

        # Check if pipeline exists
        existing = await service.get_pipeline(pipeline_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pipeline {pipeline_id} not found",
            )

        # Convert status
        pipeline_status = None
        if request.status:
            pipeline_status = PipelineStatus(request.status)

        # Convert schedule
        schedule = None
        if request.schedule:
            schedule = PipelineSchedule(
                frequency=ScheduleFrequency(request.schedule.frequency),
                cron_expression=request.schedule.cron_expression,
                time_of_day=request.schedule.time_of_day,
                day_of_week=request.schedule.day_of_week,
                day_of_month=request.schedule.day_of_month,
                timezone=request.schedule.timezone,
                enabled=request.schedule.enabled,
            )

        # Convert stages
        stages = None
        if request.stages:
            stages = [
                PipelineStage(
                    name=s.name,
                    stage_type=s.stage_type,
                    config=s.config,
                    order=s.order,
                    enabled=s.enabled,
                )
                for s in request.stages
            ]

        pipeline = await service.update_pipeline(
            pipeline_id=pipeline_id,
            name=request.name,
            description=request.description,
            status=pipeline_status,
            schedule=schedule,
            stages=stages,
            batch_size=request.batch_size,
            max_records=request.max_records,
            skip_on_error=request.skip_on_error,
        )

        logger.info(f"Updated pipeline {pipeline_id}")
        return _pipeline_to_response(pipeline)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update pipeline {pipeline_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update pipeline",
        )


@router.delete(
    "/pipelines/{pipeline_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete pipeline",
    description="Delete a pipeline.",
)
async def delete_pipeline(
    pipeline_id: UUID,
) -> None:
    """Delete a pipeline.

    Args:
        pipeline_id: Pipeline UUID.
    """
    try:
        service = get_source_config_service()
        deleted = await service.delete_pipeline(pipeline_id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pipeline {pipeline_id} not found",
            )

        logger.info(f"Deleted pipeline {pipeline_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete pipeline {pipeline_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete pipeline",
        )


@router.put(
    "/pipelines/{pipeline_id}/schedule",
    response_model=PipelineResponse,
    summary="Set pipeline schedule",
    description="Update the schedule for a pipeline.",
)
async def set_pipeline_schedule(
    pipeline_id: UUID,
    request: PipelineScheduleRequest,
) -> PipelineResponse:
    """Set or update pipeline schedule.

    Args:
        pipeline_id: Pipeline UUID.
        request: Schedule configuration.

    Returns:
        Updated PipelineResponse.
    """
    try:
        service = get_source_config_service()

        schedule = PipelineSchedule(
            frequency=ScheduleFrequency(request.frequency),
            cron_expression=request.cron_expression,
            time_of_day=request.time_of_day,
            day_of_week=request.day_of_week,
            day_of_month=request.day_of_month,
            timezone=request.timezone,
            enabled=request.enabled,
        )

        pipeline = await service.update_pipeline_schedule(pipeline_id, schedule)

        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pipeline {pipeline_id} not found",
            )

        logger.info(f"Updated schedule for pipeline {pipeline_id}")
        return _pipeline_to_response(pipeline)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set schedule for {pipeline_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set pipeline schedule",
        )


@router.post(
    "/pipelines/{pipeline_id}/run",
    response_model=TriggerPipelineResponse,
    summary="Trigger pipeline run",
    description="Manually trigger a pipeline execution.",
)
async def trigger_pipeline_run(
    pipeline_id: UUID,
    background_tasks: BackgroundTasks,
) -> TriggerPipelineResponse:
    """Manually trigger a pipeline execution.

    Args:
        pipeline_id: Pipeline UUID.
        background_tasks: FastAPI background tasks.

    Returns:
        TriggerPipelineResponse with run details.
    """
    try:
        service = get_source_config_service()

        # Check if pipeline exists
        pipeline = await service.get_pipeline(pipeline_id)
        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pipeline {pipeline_id} not found",
            )

        # Create a new run
        run = await service.create_pipeline_run(pipeline_id)

        if not run:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create pipeline run",
            )

        # In production, this would trigger the actual ETL job
        # For now, we just simulate scheduling it
        logger.info(f"Triggered run {run.id} for pipeline {pipeline_id}")

        return TriggerPipelineResponse(
            run_id=str(run.id),
            pipeline_id=str(pipeline_id),
            status=run.status,
            message="Pipeline run triggered successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger run for {pipeline_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger pipeline run",
        )


@router.get(
    "/pipelines/{pipeline_id}/runs",
    response_model=PipelineRunListResponse,
    summary="Get pipeline run history",
    description="Get the execution history for a pipeline.",
)
async def get_pipeline_runs(
    pipeline_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
) -> PipelineRunListResponse:
    """Get run history for a pipeline.

    Args:
        pipeline_id: Pipeline UUID.
        limit: Maximum runs to return.

    Returns:
        PipelineRunListResponse with run history.
    """
    try:
        service = get_source_config_service()

        # Check if pipeline exists
        pipeline = await service.get_pipeline(pipeline_id)
        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pipeline {pipeline_id} not found",
            )

        runs = await service.get_pipeline_runs(pipeline_id, limit)

        return PipelineRunListResponse(
            runs=[_run_to_response(r) for r in runs],
            total=len(runs),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get runs for {pipeline_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get pipeline runs",
        )
