"""
Pipelines API

REST endpoints for managing data ingestion pipelines.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.data_source import PipelineRunStatus, PipelineStatus
from app.services.pipeline_service import (
    PipelineCreate,
    PipelineResponse,
    PipelineRunResponse,
    PipelineService,
    PipelineUpdate,
)

router = APIRouter(prefix="/pipelines", tags=["Pipelines"])


def get_service(db: AsyncSession = Depends(get_db)) -> PipelineService:
    """Get pipeline service instance."""
    return PipelineService(db)


@router.post("", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline(
    data: PipelineCreate,
    service: PipelineService = Depends(get_service),
) -> PipelineResponse:
    """
    Create a new data ingestion pipeline.

    Configure:
    - Data source to pull from
    - Schedule (manual, cron, interval)
    - Transformation settings (patient matching, code mapping, NLP enrichment)
    - Quality thresholds
    - Filters (resource types, date ranges)
    """
    try:
        pipeline = await service.create(data)
        return service.to_response(pipeline)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("", response_model=list[PipelineResponse])
async def list_pipelines(
    source_id: Optional[UUID] = None,
    status: Optional[PipelineStatus] = None,
    is_active: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
    service: PipelineService = Depends(get_service),
) -> list[PipelineResponse]:
    """
    List all pipelines.

    Optionally filter by:
    - source_id: Only pipelines using specific data source
    - status: active, paused, disabled
    - is_active: true/false
    """
    pipelines = await service.list(
        source_id=source_id,
        status=status,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return [service.to_response(p) for p in pipelines]


@router.get("/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(
    pipeline_id: UUID,
    service: PipelineService = Depends(get_service),
) -> PipelineResponse:
    """Get details of a specific pipeline."""
    pipeline = await service.get(pipeline_id)
    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline not found: {pipeline_id}",
        )
    return service.to_response(pipeline)


@router.put("/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(
    pipeline_id: UUID,
    data: PipelineUpdate,
    service: PipelineService = Depends(get_service),
) -> PipelineResponse:
    """
    Update a pipeline configuration.

    Only provided fields will be updated.
    """
    try:
        pipeline = await service.update(pipeline_id, data)
        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pipeline not found: {pipeline_id}",
            )
        return service.to_response(pipeline)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete("/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pipeline(
    pipeline_id: UUID,
    service: PipelineService = Depends(get_service),
) -> None:
    """
    Delete a pipeline.

    This will also delete all associated run history.
    """
    deleted = await service.delete(pipeline_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline not found: {pipeline_id}",
        )


# Pipeline control endpoints
@router.post("/{pipeline_id}/run", response_model=PipelineRunResponse)
async def trigger_run(
    pipeline_id: UUID,
    service: PipelineService = Depends(get_service),
) -> PipelineRunResponse:
    """
    Trigger a manual pipeline run.

    Creates a new run in PENDING status and queues it for execution.
    """
    try:
        run = await service.create_run(
            pipeline_id,
            triggered_by="manual",
        )

        # TODO: Enqueue to RQ for execution
        # from app.core.queue import enqueue_job
        # enqueue_job("execute_pipeline", run.id)

        # For now, just mark as running (executor will be implemented separately)
        await service.update_run_status(run.id, PipelineRunStatus.PENDING)

        return service.run_to_response(run)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/{pipeline_id}/pause", response_model=PipelineResponse)
async def pause_pipeline(
    pipeline_id: UUID,
    service: PipelineService = Depends(get_service),
) -> PipelineResponse:
    """
    Pause a pipeline.

    Stops scheduled runs. Does not affect currently running executions.
    """
    pipeline = await service.pause(pipeline_id)
    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline not found: {pipeline_id}",
        )
    return service.to_response(pipeline)


@router.post("/{pipeline_id}/resume", response_model=PipelineResponse)
async def resume_pipeline(
    pipeline_id: UUID,
    service: PipelineService = Depends(get_service),
) -> PipelineResponse:
    """
    Resume a paused pipeline.

    Restarts scheduled runs and calculates next run time.
    """
    pipeline = await service.resume(pipeline_id)
    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline not found: {pipeline_id}",
        )
    return service.to_response(pipeline)


# Run management endpoints
@router.get("/{pipeline_id}/runs", response_model=list[PipelineRunResponse])
async def list_runs(
    pipeline_id: UUID,
    status: Optional[PipelineRunStatus] = None,
    limit: int = 50,
    offset: int = 0,
    service: PipelineService = Depends(get_service),
) -> list[PipelineRunResponse]:
    """
    List run history for a pipeline.

    Returns most recent runs first.
    """
    # Verify pipeline exists
    pipeline = await service.get(pipeline_id)
    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline not found: {pipeline_id}",
        )

    runs = await service.list_runs(
        pipeline_id=pipeline_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return [service.run_to_response(r) for r in runs]


@router.get("/{pipeline_id}/runs/{run_id}", response_model=PipelineRunResponse)
async def get_run(
    pipeline_id: UUID,
    run_id: UUID,
    service: PipelineService = Depends(get_service),
) -> PipelineRunResponse:
    """Get details of a specific pipeline run."""
    run = await service.get_run(run_id)
    if not run or run.pipeline_id != pipeline_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run not found: {run_id}",
        )
    return service.run_to_response(run)


@router.post("/{pipeline_id}/runs/{run_id}/cancel", response_model=PipelineRunResponse)
async def cancel_run(
    pipeline_id: UUID,
    run_id: UUID,
    service: PipelineService = Depends(get_service),
) -> PipelineRunResponse:
    """
    Cancel a running or pending pipeline execution.
    """
    try:
        run = await service.cancel_run(run_id)
        if not run or run.pipeline_id != pipeline_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run not found: {run_id}",
            )
        return service.run_to_response(run)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# Summary endpoint for dashboard
@router.get("/summary/stats")
async def get_pipeline_stats(
    service: PipelineService = Depends(get_service),
) -> dict:
    """
    Get summary statistics about pipelines.

    Returns counts by status, recent run statistics.
    """
    all_pipelines = await service.list(limit=1000)

    by_status = {}
    total_runs = 0
    successful_runs = 0
    failed_runs = 0

    for pipeline in all_pipelines:
        # Count by status
        status_key = pipeline.status.value
        by_status[status_key] = by_status.get(status_key, 0) + 1

        # Sum run stats
        total_runs += pipeline.total_runs
        successful_runs += pipeline.successful_runs
        failed_runs += pipeline.failed_runs

    success_rate = (
        (successful_runs / total_runs * 100) if total_runs > 0 else 0
    )

    return {
        "total_pipelines": len(all_pipelines),
        "active_pipelines": len([p for p in all_pipelines if p.is_active]),
        "by_status": by_status,
        "total_runs": total_runs,
        "successful_runs": successful_runs,
        "failed_runs": failed_runs,
        "success_rate": round(success_rate, 1),
    }
