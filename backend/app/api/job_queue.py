"""Job Queue API endpoints.

Provides endpoints for queue visualization, worker status,
job retry/cancel operations, and wait time estimation.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.services.job_queue_service import (
    Job,
    JobPriority,
    JobQueueService,
    JobStatus,
    ProcessingRate,
    QueueDepthPoint,
    QueueStats,
    RetryAttempt,
    WorkerStatus,
    get_job_queue_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])


# ============================================================================
# Dependencies
# ============================================================================


def get_service() -> JobQueueService:
    """Get the job queue service instance."""
    return get_job_queue_service()


ServiceDep = Annotated[JobQueueService, Depends(get_service)]


# ============================================================================
# Response Models
# ============================================================================


class QueueStatsResponse(BaseModel):
    """Response model for queue statistics."""

    pending_count: int
    queued_count: int
    running_count: int
    completed_count: int
    failed_count: int
    cancelled_count: int
    total_count: int
    avg_wait_time_seconds: float
    avg_processing_time_seconds: float
    throughput_per_minute: float
    oldest_pending_job_age_seconds: float
    by_priority: dict[str, int]
    by_type: dict[str, int]


class QueueDepthResponse(BaseModel):
    """Response model for queue depth history."""

    history: list[dict[str, Any]]
    hours: int


class ProcessingRateResponse(BaseModel):
    """Response model for processing rate."""

    jobs_per_minute: float
    jobs_per_hour: float
    avg_duration_seconds: float
    success_rate: float
    error_rate: float
    trend: str


class WorkerStatusResponse(BaseModel):
    """Response model for worker status."""

    worker_id: str
    name: str
    state: str
    current_job_id: str | None
    current_job_type: str | None
    jobs_completed: int
    jobs_failed: int
    started_at: str
    last_heartbeat: str
    avg_processing_time_seconds: float
    memory_usage_mb: float
    cpu_usage_percent: float


class WorkerListResponse(BaseModel):
    """Response model for list of workers."""

    workers: list[WorkerStatusResponse]
    total: int


class JobResponse(BaseModel):
    """Response model for a job."""

    id: str
    job_type: str
    status: str
    priority: str
    created_at: str
    started_at: str | None
    completed_at: str | None
    worker_id: str | None
    error: str | None
    retry_count: int
    max_retries: int
    position_in_queue: int | None
    estimated_duration_seconds: float | None


class JobListResponse(BaseModel):
    """Response model for list of jobs."""

    jobs: list[JobResponse]
    total: int
    page: int
    page_size: int


class JobEstimateResponse(BaseModel):
    """Response model for job time estimate."""

    job_id: str
    status: str
    position_in_queue: int | None = None
    started_at: str | None = None
    elapsed_seconds: float | None = None
    estimated_wait_seconds: float | None = None
    estimated_remaining_seconds: float | None = None
    estimated_completion: str | None = None


class RetryAttemptResponse(BaseModel):
    """Response model for a retry attempt."""

    attempt_number: int
    timestamp: str
    error: str
    worker_id: str | None
    duration_seconds: float | None


class RetryHistoryResponse(BaseModel):
    """Response model for retry history."""

    job_id: str
    retry_count: int
    max_retries: int
    attempts: list[RetryAttemptResponse]


class BulkActionRequest(BaseModel):
    """Request model for bulk job actions."""

    job_ids: list[str] = Field(..., min_length=1, max_length=100)


class BulkActionResponse(BaseModel):
    """Response model for bulk actions."""

    succeeded: int
    failed: int
    jobs: list[JobResponse]


class WaitTimeEstimateResponse(BaseModel):
    """Response model for wait time estimate."""

    job_type: str
    estimated_wait_seconds: float
    estimated_wait_formatted: str


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "/queue/stats",
    response_model=QueueStatsResponse,
    summary="Get queue statistics",
    description="Get current statistics for the job queue including counts by status, priority, and type.",
)
async def get_queue_stats(service: ServiceDep) -> QueueStatsResponse:
    """Get queue statistics."""
    stats = service.get_queue_stats()
    return QueueStatsResponse(
        pending_count=stats.pending_count,
        queued_count=stats.queued_count,
        running_count=stats.running_count,
        completed_count=stats.completed_count,
        failed_count=stats.failed_count,
        cancelled_count=stats.cancelled_count,
        total_count=stats.total_count,
        avg_wait_time_seconds=stats.avg_wait_time_seconds,
        avg_processing_time_seconds=stats.avg_processing_time_seconds,
        throughput_per_minute=stats.throughput_per_minute,
        oldest_pending_job_age_seconds=stats.oldest_pending_job_age_seconds,
        by_priority=stats.by_priority,
        by_type=stats.by_type,
    )


@router.get(
    "/queue/depth",
    response_model=QueueDepthResponse,
    summary="Get queue depth history",
    description="Get queue depth over time for visualization.",
)
async def get_queue_depth(
    service: ServiceDep,
    hours: int = Query(24, ge=1, le=168, description="Number of hours of history"),
) -> QueueDepthResponse:
    """Get queue depth history."""
    history = service.get_queue_depth_history(hours)
    return QueueDepthResponse(
        history=[
            {
                "timestamp": point.timestamp,
                "pending": point.pending,
                "running": point.running,
                "completed": point.completed,
                "failed": point.failed,
            }
            for point in history
        ],
        hours=hours,
    )


@router.get(
    "/queue/rate",
    response_model=ProcessingRateResponse,
    summary="Get processing rate",
    description="Get current processing rate metrics.",
)
async def get_processing_rate(service: ServiceDep) -> ProcessingRateResponse:
    """Get processing rate."""
    rate = service.get_processing_rate()
    return ProcessingRateResponse(
        jobs_per_minute=rate.jobs_per_minute,
        jobs_per_hour=rate.jobs_per_hour,
        avg_duration_seconds=rate.avg_duration_seconds,
        success_rate=rate.success_rate,
        error_rate=rate.error_rate,
        trend=rate.trend,
    )


@router.get(
    "/queue/workers",
    response_model=WorkerListResponse,
    summary="Get worker status",
    description="Get status of all queue workers.",
)
async def get_workers(service: ServiceDep) -> WorkerListResponse:
    """Get worker status."""
    workers = service.get_worker_status()
    return WorkerListResponse(
        workers=[
            WorkerStatusResponse(
                worker_id=w.worker_id,
                name=w.name,
                state=w.state.value,
                current_job_id=w.current_job_id,
                current_job_type=w.current_job_type,
                jobs_completed=w.jobs_completed,
                jobs_failed=w.jobs_failed,
                started_at=w.started_at,
                last_heartbeat=w.last_heartbeat,
                avg_processing_time_seconds=w.avg_processing_time_seconds,
                memory_usage_mb=w.memory_usage_mb,
                cpu_usage_percent=w.cpu_usage_percent,
            )
            for w in workers
        ],
        total=len(workers),
    )


@router.get(
    "/queue/estimate/{job_type}",
    response_model=WaitTimeEstimateResponse,
    summary="Estimate wait time",
    description="Estimate wait time for a new job of the given type.",
)
async def estimate_wait_time(
    job_type: str,
    service: ServiceDep,
) -> WaitTimeEstimateResponse:
    """Estimate wait time for a new job."""
    wait_time = service.estimate_wait_time(job_type)

    # Format the wait time
    total_seconds = wait_time.total_seconds()
    if total_seconds < 60:
        formatted = f"{int(total_seconds)} seconds"
    elif total_seconds < 3600:
        formatted = f"{int(total_seconds / 60)} minutes"
    else:
        formatted = f"{total_seconds / 3600:.1f} hours"

    return WaitTimeEstimateResponse(
        job_type=job_type,
        estimated_wait_seconds=round(total_seconds, 2),
        estimated_wait_formatted=formatted,
    )


@router.get(
    "/list",
    response_model=JobListResponse,
    summary="List jobs",
    description="List jobs with optional filtering by status, type, and priority.",
)
async def list_jobs(
    service: ServiceDep,
    status: JobStatus | None = Query(None, description="Filter by job status"),
    job_type: str | None = Query(None, description="Filter by job type"),
    priority: JobPriority | None = Query(None, description="Filter by priority"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> JobListResponse:
    """List jobs with pagination and filtering."""
    offset = (page - 1) * page_size
    jobs, total = service.get_jobs(
        status=status,
        job_type=job_type,
        priority=priority,
        limit=page_size,
        offset=offset,
    )

    return JobListResponse(
        jobs=[
            JobResponse(
                id=j.id,
                job_type=j.job_type,
                status=j.status.value,
                priority=j.priority.value,
                created_at=j.created_at,
                started_at=j.started_at,
                completed_at=j.completed_at,
                worker_id=j.worker_id,
                error=j.error,
                retry_count=j.retry_count,
                max_retries=j.max_retries,
                position_in_queue=j.position_in_queue,
                estimated_duration_seconds=j.estimated_duration_seconds,
            )
            for j in jobs
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{job_id}/estimate",
    response_model=JobEstimateResponse,
    summary="Get job estimate",
    description="Get estimated completion time for a specific job.",
)
async def get_job_estimate(
    job_id: str,
    service: ServiceDep,
) -> JobEstimateResponse:
    """Get estimated completion time for a job."""
    try:
        estimate = service.get_job_estimate(job_id)
        return JobEstimateResponse(**estimate)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/{job_id}/retry",
    response_model=JobResponse,
    summary="Retry failed job",
    description="Retry a failed or cancelled job.",
)
async def retry_job(
    job_id: str,
    service: ServiceDep,
) -> JobResponse:
    """Retry a failed job."""
    try:
        job = service.retry_job(job_id)
        return JobResponse(
            id=job.id,
            job_type=job.job_type,
            status=job.status.value,
            priority=job.priority.value,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            worker_id=job.worker_id,
            error=job.error,
            retry_count=job.retry_count,
            max_retries=job.max_retries,
            position_in_queue=job.position_in_queue,
            estimated_duration_seconds=job.estimated_duration_seconds,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{job_id}/cancel",
    response_model=JobResponse,
    summary="Cancel job",
    description="Cancel a pending or running job.",
)
async def cancel_job(
    job_id: str,
    service: ServiceDep,
) -> JobResponse:
    """Cancel a job."""
    try:
        job = service.cancel_job(job_id)
        return JobResponse(
            id=job.id,
            job_type=job.job_type,
            status=job.status.value,
            priority=job.priority.value,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            worker_id=job.worker_id,
            error=job.error,
            retry_count=job.retry_count,
            max_retries=job.max_retries,
            position_in_queue=job.position_in_queue,
            estimated_duration_seconds=job.estimated_duration_seconds,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/{job_id}/retries",
    response_model=RetryHistoryResponse,
    summary="Get retry history",
    description="Get retry history for a job.",
)
async def get_retry_history(
    job_id: str,
    service: ServiceDep,
) -> RetryHistoryResponse:
    """Get retry history for a job."""
    try:
        job = service.get_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        attempts = service.get_retry_history(job_id)
        return RetryHistoryResponse(
            job_id=job_id,
            retry_count=job.retry_count,
            max_retries=job.max_retries,
            attempts=[
                RetryAttemptResponse(
                    attempt_number=a.attempt_number,
                    timestamp=a.timestamp,
                    error=a.error,
                    worker_id=a.worker_id,
                    duration_seconds=a.duration_seconds,
                )
                for a in attempts
            ],
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/bulk/retry",
    response_model=BulkActionResponse,
    summary="Retry all failed jobs",
    description="Retry all failed jobs that haven't exceeded max retries.",
)
async def retry_all_failed(service: ServiceDep) -> BulkActionResponse:
    """Retry all failed jobs."""
    jobs = service.retry_all_failed()
    return BulkActionResponse(
        succeeded=len(jobs),
        failed=0,
        jobs=[
            JobResponse(
                id=j.id,
                job_type=j.job_type,
                status=j.status.value,
                priority=j.priority.value,
                created_at=j.created_at,
                started_at=j.started_at,
                completed_at=j.completed_at,
                worker_id=j.worker_id,
                error=j.error,
                retry_count=j.retry_count,
                max_retries=j.max_retries,
                position_in_queue=j.position_in_queue,
                estimated_duration_seconds=j.estimated_duration_seconds,
            )
            for j in jobs
        ],
    )


@router.post(
    "/bulk/cancel",
    response_model=BulkActionResponse,
    summary="Cancel selected jobs",
    description="Cancel multiple jobs by ID.",
)
async def cancel_selected_jobs(
    request: BulkActionRequest,
    service: ServiceDep,
) -> BulkActionResponse:
    """Cancel selected jobs."""
    jobs = service.cancel_selected(request.job_ids)
    failed = len(request.job_ids) - len(jobs)
    return BulkActionResponse(
        succeeded=len(jobs),
        failed=failed,
        jobs=[
            JobResponse(
                id=j.id,
                job_type=j.job_type,
                status=j.status.value,
                priority=j.priority.value,
                created_at=j.created_at,
                started_at=j.started_at,
                completed_at=j.completed_at,
                worker_id=j.worker_id,
                error=j.error,
                retry_count=j.retry_count,
                max_retries=j.max_retries,
                position_in_queue=j.position_in_queue,
                estimated_duration_seconds=j.estimated_duration_seconds,
            )
            for j in jobs
        ],
    )
