"""Batch Processing API for Knowledge Graph Operations.

Provides endpoints for bulk operations on the knowledge graph:
- Batch concept lookups
- Batch relationship queries
- Batch path finding
- Job management (submit, status, cancel)
- Progress tracking with SSE streaming
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/batch", tags=["Batch Processing"])


# =============================================================================
# Enums
# =============================================================================


class BatchOperationType(str, Enum):
    """Types of batch operations."""

    CONCEPT_LOOKUP = "concept_lookup"
    RELATIONSHIP_QUERY = "relationship_query"
    PATH_FINDING = "path_finding"
    CONCEPT_SEARCH = "concept_search"
    PATIENT_SIMILARITY = "patient_similarity"
    GRAPH_TRAVERSAL = "graph_traversal"
    CONCEPT_VALIDATION = "concept_validation"


class BatchJobStatus(str, Enum):
    """Status of a batch job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


class BatchFailureMode(str, Enum):
    """How to handle failures in batch operations."""

    FAIL_FAST = "fail_fast"
    CONTINUE_ON_ERROR = "continue_on_error"
    RETRY_FAILURES = "retry_failures"


# =============================================================================
# Request/Response Models
# =============================================================================


class BatchConceptLookupRequest(BaseModel):
    """Request for batch concept lookups."""

    concept_ids: list[int] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="List of OMOP concept IDs to look up",
    )
    include_relationships: bool = Field(
        False, description="Include relationships for each concept"
    )
    include_ancestors: bool = Field(
        False, description="Include ancestor concepts"
    )
    max_ancestor_depth: int = Field(
        3, ge=1, le=10, description="Maximum ancestor depth"
    )
    failure_mode: BatchFailureMode = Field(
        BatchFailureMode.CONTINUE_ON_ERROR,
        description="How to handle lookup failures",
    )

    @field_validator("concept_ids")
    @classmethod
    def validate_concept_ids(cls, v: list[int]) -> list[int]:
        """Validate concept IDs are positive."""
        if any(cid <= 0 for cid in v):
            raise ValueError("All concept IDs must be positive integers")
        return v


class BatchRelationshipRequest(BaseModel):
    """Request for batch relationship queries."""

    source_concept_ids: list[int] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Source concept IDs",
    )
    relationship_types: list[str] | None = Field(
        None, description="Filter by relationship types"
    )
    target_vocabulary_ids: list[str] | None = Field(
        None, description="Filter by target vocabulary"
    )
    include_reverse: bool = Field(
        False, description="Include reverse relationships"
    )
    max_relationships_per_concept: int = Field(
        100, ge=1, le=500, description="Max relationships per concept"
    )
    failure_mode: BatchFailureMode = Field(
        BatchFailureMode.CONTINUE_ON_ERROR,
        description="How to handle query failures",
    )


class BatchPathRequest(BaseModel):
    """Request for batch path finding."""

    pairs: list[tuple[int, int]] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of (start_concept_id, end_concept_id) pairs",
    )
    max_path_length: int = Field(
        5, ge=1, le=10, description="Maximum path length"
    )
    include_all_paths: bool = Field(
        False, description="Include all paths (not just shortest)"
    )
    max_paths_per_pair: int = Field(
        5, ge=1, le=20, description="Max paths per pair if include_all_paths"
    )
    failure_mode: BatchFailureMode = Field(
        BatchFailureMode.CONTINUE_ON_ERROR,
        description="How to handle path finding failures",
    )


class BatchConceptSearchRequest(BaseModel):
    """Request for batch concept searches."""

    queries: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of search queries",
    )
    vocabulary_ids: list[str] | None = Field(
        None, description="Filter by vocabularies"
    )
    domain_ids: list[str] | None = Field(
        None, description="Filter by domains"
    )
    max_results_per_query: int = Field(
        20, ge=1, le=100, description="Max results per query"
    )
    include_synonyms: bool = Field(
        True, description="Search in synonyms"
    )
    failure_mode: BatchFailureMode = Field(
        BatchFailureMode.CONTINUE_ON_ERROR,
        description="How to handle search failures",
    )


class BatchPatientSimilarityRequest(BaseModel):
    """Request for batch patient similarity."""

    patient_ids: list[str] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of patient IDs to find similar patients for",
    )
    similarity_metric: str = Field(
        "jaccard", description="Similarity metric to use"
    )
    top_k: int = Field(
        10, ge=1, le=50, description="Number of similar patients per query"
    )
    min_similarity: float = Field(
        0.1, ge=0.0, le=1.0, description="Minimum similarity threshold"
    )
    failure_mode: BatchFailureMode = Field(
        BatchFailureMode.CONTINUE_ON_ERROR,
        description="How to handle similarity failures",
    )


class BatchJobSubmitResponse(BaseModel):
    """Response when submitting a batch job."""

    job_id: str = Field(..., description="Unique job identifier")
    operation_type: BatchOperationType = Field(..., description="Type of operation")
    total_items: int = Field(..., description="Total items to process")
    estimated_duration_seconds: float | None = Field(
        None, description="Estimated completion time"
    )
    status: BatchJobStatus = Field(..., description="Initial job status")
    created_at: str = Field(..., description="Job creation timestamp")
    progress_url: str = Field(..., description="URL for progress tracking")
    cancel_url: str = Field(..., description="URL to cancel job")


class BatchItemResult(BaseModel):
    """Result for a single item in a batch."""

    item_index: int = Field(..., description="Index in original batch")
    item_id: str | int = Field(..., description="Item identifier")
    success: bool = Field(..., description="Whether lookup succeeded")
    data: Any | None = Field(None, description="Result data if successful")
    error: str | None = Field(None, description="Error message if failed")
    processing_time_ms: float = Field(..., description="Processing time for item")


class BatchProgress(BaseModel):
    """Progress information for a batch job."""

    job_id: str = Field(..., description="Job identifier")
    status: BatchJobStatus = Field(..., description="Current job status")
    total_items: int = Field(..., description="Total items to process")
    processed_items: int = Field(..., description="Items processed so far")
    successful_items: int = Field(..., description="Successfully processed items")
    failed_items: int = Field(..., description="Failed items")
    percentage: float = Field(..., description="Completion percentage")
    elapsed_seconds: float = Field(..., description="Elapsed time")
    estimated_remaining_seconds: float | None = Field(
        None, description="Estimated remaining time"
    )
    current_item: str | None = Field(None, description="Currently processing item")
    errors: list[str] = Field(
        default_factory=list, description="Recent error messages"
    )


class BatchJobStatusResponse(BaseModel):
    """Response for batch job status."""

    job_id: str = Field(..., description="Job identifier")
    operation_type: BatchOperationType = Field(..., description="Type of operation")
    status: BatchJobStatus = Field(..., description="Current status")
    progress: BatchProgress = Field(..., description="Progress information")
    created_at: str = Field(..., description="Job creation timestamp")
    started_at: str | None = Field(None, description="Job start timestamp")
    completed_at: str | None = Field(None, description="Job completion timestamp")
    can_cancel: bool = Field(..., description="Whether job can be cancelled")


class BatchJobResultResponse(BaseModel):
    """Response for completed batch job results."""

    job_id: str = Field(..., description="Job identifier")
    operation_type: BatchOperationType = Field(..., description="Type of operation")
    status: BatchJobStatus = Field(..., description="Final status")
    total_items: int = Field(..., description="Total items processed")
    successful_items: int = Field(..., description="Successfully processed items")
    failed_items: int = Field(..., description="Failed items")
    results: list[BatchItemResult] = Field(..., description="Individual results")
    processing_time_ms: float = Field(..., description="Total processing time")
    created_at: str = Field(..., description="Job creation timestamp")
    completed_at: str = Field(..., description="Job completion timestamp")


class BatchJobListResponse(BaseModel):
    """Response for listing batch jobs."""

    total_jobs: int = Field(..., description="Total jobs matching filter")
    jobs: list[BatchJobStatusResponse] = Field(..., description="List of jobs")


# =============================================================================
# In-Memory Job Store (for demo; use Redis/DB in production)
# =============================================================================


_batch_jobs: dict[str, dict[str, Any]] = {}
_batch_results: dict[str, list[BatchItemResult]] = {}


# =============================================================================
# API Endpoints
# =============================================================================


@router.post(
    "/concepts/lookup",
    response_model=BatchJobSubmitResponse,
    summary="Submit batch concept lookup job",
    description="Submit a batch job to look up multiple concepts by ID.",
)
async def batch_concept_lookup(
    request: BatchConceptLookupRequest,
    background_tasks: BackgroundTasks,
) -> BatchJobSubmitResponse:
    """Submit a batch concept lookup job."""
    job_id = str(uuid.uuid4())
    total_items = len(request.concept_ids)

    # Create job record
    job = {
        "job_id": job_id,
        "operation_type": BatchOperationType.CONCEPT_LOOKUP,
        "request": request.model_dump(),
        "status": BatchJobStatus.PENDING,
        "total_items": total_items,
        "processed_items": 0,
        "successful_items": 0,
        "failed_items": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "started_at": None,
        "completed_at": None,
        "errors": [],
        "cancel_event": asyncio.Event(),
    }
    _batch_jobs[job_id] = job
    _batch_results[job_id] = []

    # Estimate duration (rough: 50ms per concept)
    base_time = 0.05
    if request.include_relationships:
        base_time += 0.02
    if request.include_ancestors:
        base_time += 0.03 * request.max_ancestor_depth
    estimated_duration = total_items * base_time

    # Schedule background processing
    background_tasks.add_task(_process_concept_lookup_batch, job_id)

    return BatchJobSubmitResponse(
        job_id=job_id,
        operation_type=BatchOperationType.CONCEPT_LOOKUP,
        total_items=total_items,
        estimated_duration_seconds=estimated_duration,
        status=BatchJobStatus.PENDING,
        created_at=job["created_at"],
        progress_url=f"/api/batch/jobs/{job_id}/progress",
        cancel_url=f"/api/batch/jobs/{job_id}/cancel",
    )


@router.post(
    "/concepts/relationships",
    response_model=BatchJobSubmitResponse,
    summary="Submit batch relationship query job",
    description="Submit a batch job to query relationships for multiple concepts.",
)
async def batch_relationship_query(
    request: BatchRelationshipRequest,
    background_tasks: BackgroundTasks,
) -> BatchJobSubmitResponse:
    """Submit a batch relationship query job."""
    job_id = str(uuid.uuid4())
    total_items = len(request.source_concept_ids)

    job = {
        "job_id": job_id,
        "operation_type": BatchOperationType.RELATIONSHIP_QUERY,
        "request": request.model_dump(),
        "status": BatchJobStatus.PENDING,
        "total_items": total_items,
        "processed_items": 0,
        "successful_items": 0,
        "failed_items": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "started_at": None,
        "completed_at": None,
        "errors": [],
        "cancel_event": asyncio.Event(),
    }
    _batch_jobs[job_id] = job
    _batch_results[job_id] = []

    estimated_duration = total_items * 0.1

    background_tasks.add_task(_process_relationship_batch, job_id)

    return BatchJobSubmitResponse(
        job_id=job_id,
        operation_type=BatchOperationType.RELATIONSHIP_QUERY,
        total_items=total_items,
        estimated_duration_seconds=estimated_duration,
        status=BatchJobStatus.PENDING,
        created_at=job["created_at"],
        progress_url=f"/api/batch/jobs/{job_id}/progress",
        cancel_url=f"/api/batch/jobs/{job_id}/cancel",
    )


@router.post(
    "/concepts/paths",
    response_model=BatchJobSubmitResponse,
    summary="Submit batch path finding job",
    description="Submit a batch job to find paths between concept pairs.",
)
async def batch_path_finding(
    request: BatchPathRequest,
    background_tasks: BackgroundTasks,
) -> BatchJobSubmitResponse:
    """Submit a batch path finding job."""
    job_id = str(uuid.uuid4())
    total_items = len(request.pairs)

    job = {
        "job_id": job_id,
        "operation_type": BatchOperationType.PATH_FINDING,
        "request": request.model_dump(),
        "status": BatchJobStatus.PENDING,
        "total_items": total_items,
        "processed_items": 0,
        "successful_items": 0,
        "failed_items": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "started_at": None,
        "completed_at": None,
        "errors": [],
        "cancel_event": asyncio.Event(),
    }
    _batch_jobs[job_id] = job
    _batch_results[job_id] = []

    # Path finding is more expensive
    estimated_duration = total_items * 0.5 * (request.max_path_length / 5)

    background_tasks.add_task(_process_path_batch, job_id)

    return BatchJobSubmitResponse(
        job_id=job_id,
        operation_type=BatchOperationType.PATH_FINDING,
        total_items=total_items,
        estimated_duration_seconds=estimated_duration,
        status=BatchJobStatus.PENDING,
        created_at=job["created_at"],
        progress_url=f"/api/batch/jobs/{job_id}/progress",
        cancel_url=f"/api/batch/jobs/{job_id}/cancel",
    )


@router.post(
    "/concepts/search",
    response_model=BatchJobSubmitResponse,
    summary="Submit batch concept search job",
    description="Submit a batch job to search for concepts using multiple queries.",
)
async def batch_concept_search(
    request: BatchConceptSearchRequest,
    background_tasks: BackgroundTasks,
) -> BatchJobSubmitResponse:
    """Submit a batch concept search job."""
    job_id = str(uuid.uuid4())
    total_items = len(request.queries)

    job = {
        "job_id": job_id,
        "operation_type": BatchOperationType.CONCEPT_SEARCH,
        "request": request.model_dump(),
        "status": BatchJobStatus.PENDING,
        "total_items": total_items,
        "processed_items": 0,
        "successful_items": 0,
        "failed_items": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "started_at": None,
        "completed_at": None,
        "errors": [],
        "cancel_event": asyncio.Event(),
    }
    _batch_jobs[job_id] = job
    _batch_results[job_id] = []

    estimated_duration = total_items * 0.15

    background_tasks.add_task(_process_search_batch, job_id)

    return BatchJobSubmitResponse(
        job_id=job_id,
        operation_type=BatchOperationType.CONCEPT_SEARCH,
        total_items=total_items,
        estimated_duration_seconds=estimated_duration,
        status=BatchJobStatus.PENDING,
        created_at=job["created_at"],
        progress_url=f"/api/batch/jobs/{job_id}/progress",
        cancel_url=f"/api/batch/jobs/{job_id}/cancel",
    )


@router.post(
    "/patients/similarity",
    response_model=BatchJobSubmitResponse,
    summary="Submit batch patient similarity job",
    description="Submit a batch job to find similar patients for multiple patients.",
)
async def batch_patient_similarity(
    request: BatchPatientSimilarityRequest,
    background_tasks: BackgroundTasks,
) -> BatchJobSubmitResponse:
    """Submit a batch patient similarity job."""
    job_id = str(uuid.uuid4())
    total_items = len(request.patient_ids)

    job = {
        "job_id": job_id,
        "operation_type": BatchOperationType.PATIENT_SIMILARITY,
        "request": request.model_dump(),
        "status": BatchJobStatus.PENDING,
        "total_items": total_items,
        "processed_items": 0,
        "successful_items": 0,
        "failed_items": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "started_at": None,
        "completed_at": None,
        "errors": [],
        "cancel_event": asyncio.Event(),
    }
    _batch_jobs[job_id] = job
    _batch_results[job_id] = []

    # Similarity is expensive
    estimated_duration = total_items * 1.0

    background_tasks.add_task(_process_similarity_batch, job_id)

    return BatchJobSubmitResponse(
        job_id=job_id,
        operation_type=BatchOperationType.PATIENT_SIMILARITY,
        total_items=total_items,
        estimated_duration_seconds=estimated_duration,
        status=BatchJobStatus.PENDING,
        created_at=job["created_at"],
        progress_url=f"/api/batch/jobs/{job_id}/progress",
        cancel_url=f"/api/batch/jobs/{job_id}/cancel",
    )


@router.get(
    "/jobs/{job_id}",
    response_model=BatchJobStatusResponse,
    summary="Get batch job status",
    description="Get the current status and progress of a batch job.",
)
async def get_batch_job_status(job_id: str) -> BatchJobStatusResponse:
    """Get batch job status."""
    job = _batch_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    elapsed = 0.0
    estimated_remaining = None

    if job["started_at"]:
        start = datetime.fromisoformat(job["started_at"])
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()

        if job["processed_items"] > 0:
            rate = job["processed_items"] / elapsed
            remaining = job["total_items"] - job["processed_items"]
            estimated_remaining = remaining / rate if rate > 0 else None

    progress = BatchProgress(
        job_id=job_id,
        status=job["status"],
        total_items=job["total_items"],
        processed_items=job["processed_items"],
        successful_items=job["successful_items"],
        failed_items=job["failed_items"],
        percentage=round(
            (job["processed_items"] / job["total_items"]) * 100, 2
        ) if job["total_items"] > 0 else 0.0,
        elapsed_seconds=round(elapsed, 2),
        estimated_remaining_seconds=(
            round(estimated_remaining, 2) if estimated_remaining else None
        ),
        current_item=job.get("current_item"),
        errors=job["errors"][-10:],  # Last 10 errors
    )

    return BatchJobStatusResponse(
        job_id=job_id,
        operation_type=job["operation_type"],
        status=job["status"],
        progress=progress,
        created_at=job["created_at"],
        started_at=job["started_at"],
        completed_at=job["completed_at"],
        can_cancel=job["status"] in (BatchJobStatus.PENDING, BatchJobStatus.RUNNING),
    )


@router.get(
    "/jobs/{job_id}/results",
    response_model=BatchJobResultResponse,
    summary="Get batch job results",
    description="Get the results of a completed batch job.",
)
async def get_batch_job_results(
    job_id: str,
    offset: int = Query(0, ge=0, description="Result offset"),
    limit: int = Query(100, ge=1, le=1000, description="Result limit"),
) -> BatchJobResultResponse:
    """Get batch job results."""
    job = _batch_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job["status"] not in (
        BatchJobStatus.COMPLETED,
        BatchJobStatus.PARTIAL,
        BatchJobStatus.FAILED,
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} is still {job['status'].value}, results not available",
        )

    results = _batch_results.get(job_id, [])
    paginated_results = results[offset : offset + limit]

    elapsed = 0.0
    if job["started_at"] and job["completed_at"]:
        start = datetime.fromisoformat(job["started_at"])
        end = datetime.fromisoformat(job["completed_at"])
        elapsed = (end - start).total_seconds() * 1000

    return BatchJobResultResponse(
        job_id=job_id,
        operation_type=job["operation_type"],
        status=job["status"],
        total_items=job["total_items"],
        successful_items=job["successful_items"],
        failed_items=job["failed_items"],
        results=paginated_results,
        processing_time_ms=round(elapsed, 2),
        created_at=job["created_at"],
        completed_at=job["completed_at"],
    )


@router.post(
    "/jobs/{job_id}/cancel",
    summary="Cancel a batch job",
    description="Cancel a running or pending batch job.",
)
async def cancel_batch_job(job_id: str) -> dict[str, Any]:
    """Cancel a batch job."""
    job = _batch_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job["status"] not in (BatchJobStatus.PENDING, BatchJobStatus.RUNNING):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job with status {job['status'].value}",
        )

    # Signal cancellation
    cancel_event = job.get("cancel_event")
    if cancel_event:
        cancel_event.set()

    job["status"] = BatchJobStatus.CANCELLED
    job["completed_at"] = datetime.now(timezone.utc).isoformat()

    logger.info(f"Batch job {job_id} cancelled")

    return {
        "job_id": job_id,
        "status": "cancelled",
        "message": f"Job {job_id} has been cancelled",
    }


@router.get(
    "/jobs/{job_id}/progress/stream",
    summary="Stream batch job progress",
    description="Stream progress updates as Server-Sent Events.",
)
async def stream_batch_job_progress(job_id: str) -> StreamingResponse:
    """Stream batch job progress as SSE."""
    job = _batch_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    async def event_generator():
        """Generate SSE events for progress updates."""
        last_processed = -1

        while True:
            current_job = _batch_jobs.get(job_id)
            if not current_job:
                yield f"event: error\ndata: Job not found\n\n"
                break

            if current_job["processed_items"] != last_processed:
                last_processed = current_job["processed_items"]

                progress_data = {
                    "job_id": job_id,
                    "status": current_job["status"].value,
                    "processed": current_job["processed_items"],
                    "total": current_job["total_items"],
                    "successful": current_job["successful_items"],
                    "failed": current_job["failed_items"],
                    "percentage": round(
                        (current_job["processed_items"] / current_job["total_items"]) * 100, 2
                    ) if current_job["total_items"] > 0 else 0.0,
                }

                import json
                yield f"event: progress\ndata: {json.dumps(progress_data)}\n\n"

            if current_job["status"] in (
                BatchJobStatus.COMPLETED,
                BatchJobStatus.FAILED,
                BatchJobStatus.CANCELLED,
                BatchJobStatus.PARTIAL,
            ):
                yield f"event: complete\ndata: {json.dumps({'status': current_job['status'].value})}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/jobs",
    response_model=BatchJobListResponse,
    summary="List batch jobs",
    description="List batch jobs with optional filtering.",
)
async def list_batch_jobs(
    status: BatchJobStatus | None = Query(None, description="Filter by status"),
    operation_type: BatchOperationType | None = Query(
        None, description="Filter by operation type"
    ),
    limit: int = Query(50, ge=1, le=200, description="Maximum jobs to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> BatchJobListResponse:
    """List batch jobs."""
    jobs = list(_batch_jobs.values())

    # Filter
    if status:
        jobs = [j for j in jobs if j["status"] == status]
    if operation_type:
        jobs = [j for j in jobs if j["operation_type"] == operation_type]

    # Sort by created_at descending
    jobs.sort(key=lambda j: j["created_at"], reverse=True)

    # Paginate
    total = len(jobs)
    jobs = jobs[offset : offset + limit]

    # Build response
    job_responses = []
    for job in jobs:
        elapsed = 0.0
        if job["started_at"]:
            start = datetime.fromisoformat(job["started_at"])
            elapsed = (datetime.now(timezone.utc) - start).total_seconds()

        progress = BatchProgress(
            job_id=job["job_id"],
            status=job["status"],
            total_items=job["total_items"],
            processed_items=job["processed_items"],
            successful_items=job["successful_items"],
            failed_items=job["failed_items"],
            percentage=round(
                (job["processed_items"] / job["total_items"]) * 100, 2
            ) if job["total_items"] > 0 else 0.0,
            elapsed_seconds=round(elapsed, 2),
            estimated_remaining_seconds=None,
            errors=job["errors"][-5:],
        )

        job_responses.append(
            BatchJobStatusResponse(
                job_id=job["job_id"],
                operation_type=job["operation_type"],
                status=job["status"],
                progress=progress,
                created_at=job["created_at"],
                started_at=job["started_at"],
                completed_at=job["completed_at"],
                can_cancel=job["status"] in (
                    BatchJobStatus.PENDING,
                    BatchJobStatus.RUNNING,
                ),
            )
        )

    return BatchJobListResponse(total_jobs=total, jobs=job_responses)


@router.delete(
    "/jobs/{job_id}",
    summary="Delete a batch job",
    description="Delete a completed batch job and its results.",
)
async def delete_batch_job(job_id: str) -> dict[str, Any]:
    """Delete a batch job."""
    job = _batch_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job["status"] in (BatchJobStatus.PENDING, BatchJobStatus.RUNNING):
        raise HTTPException(
            status_code=400,
            detail="Cannot delete running job. Cancel it first.",
        )

    del _batch_jobs[job_id]
    _batch_results.pop(job_id, None)

    return {"job_id": job_id, "deleted": True}


# =============================================================================
# Background Processing Functions
# =============================================================================


async def _process_concept_lookup_batch(job_id: str) -> None:
    """Process a batch concept lookup job."""
    job = _batch_jobs.get(job_id)
    if not job:
        return

    job["status"] = BatchJobStatus.RUNNING
    job["started_at"] = datetime.now(timezone.utc).isoformat()

    request_data = job["request"]
    concept_ids = request_data["concept_ids"]
    failure_mode = BatchFailureMode(request_data["failure_mode"])
    cancel_event = job["cancel_event"]

    try:
        for idx, concept_id in enumerate(concept_ids):
            if cancel_event.is_set():
                break

            job["current_item"] = f"Concept {concept_id}"
            start_time = asyncio.get_event_loop().time()

            try:
                # Simulate concept lookup (replace with actual service call)
                await asyncio.sleep(0.02)  # Simulated lookup time

                result_data = {
                    "concept_id": concept_id,
                    "concept_name": f"Concept_{concept_id}",
                    "vocabulary_id": "SNOMED",
                    "domain_id": "Condition",
                }

                if request_data.get("include_relationships"):
                    result_data["relationships"] = []

                if request_data.get("include_ancestors"):
                    result_data["ancestors"] = []

                elapsed = (asyncio.get_event_loop().time() - start_time) * 1000

                _batch_results[job_id].append(
                    BatchItemResult(
                        item_index=idx,
                        item_id=concept_id,
                        success=True,
                        data=result_data,
                        error=None,
                        processing_time_ms=round(elapsed, 2),
                    )
                )
                job["successful_items"] += 1

            except Exception as e:
                elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
                error_msg = str(e)

                _batch_results[job_id].append(
                    BatchItemResult(
                        item_index=idx,
                        item_id=concept_id,
                        success=False,
                        data=None,
                        error=error_msg,
                        processing_time_ms=round(elapsed, 2),
                    )
                )
                job["failed_items"] += 1
                job["errors"].append(f"Concept {concept_id}: {error_msg}")

                if failure_mode == BatchFailureMode.FAIL_FAST:
                    break

            job["processed_items"] = idx + 1

        # Set final status
        if cancel_event.is_set():
            job["status"] = BatchJobStatus.CANCELLED
        elif job["failed_items"] > 0 and job["successful_items"] > 0:
            job["status"] = BatchJobStatus.PARTIAL
        elif job["failed_items"] == job["total_items"]:
            job["status"] = BatchJobStatus.FAILED
        else:
            job["status"] = BatchJobStatus.COMPLETED

    except Exception as e:
        logger.error(f"Batch job {job_id} failed: {e}")
        job["status"] = BatchJobStatus.FAILED
        job["errors"].append(f"Job failed: {str(e)}")

    finally:
        job["completed_at"] = datetime.now(timezone.utc).isoformat()
        job["current_item"] = None


async def _process_relationship_batch(job_id: str) -> None:
    """Process a batch relationship query job."""
    job = _batch_jobs.get(job_id)
    if not job:
        return

    job["status"] = BatchJobStatus.RUNNING
    job["started_at"] = datetime.now(timezone.utc).isoformat()

    request_data = job["request"]
    concept_ids = request_data["source_concept_ids"]
    failure_mode = BatchFailureMode(request_data["failure_mode"])
    cancel_event = job["cancel_event"]

    try:
        for idx, concept_id in enumerate(concept_ids):
            if cancel_event.is_set():
                break

            job["current_item"] = f"Relationships for {concept_id}"
            start_time = asyncio.get_event_loop().time()

            try:
                await asyncio.sleep(0.03)  # Simulated query time

                result_data = {
                    "concept_id": concept_id,
                    "relationships": [
                        {
                            "type": "IS_A",
                            "target_id": concept_id + 1000,
                            "target_name": f"Parent_{concept_id}",
                        }
                    ],
                }

                elapsed = (asyncio.get_event_loop().time() - start_time) * 1000

                _batch_results[job_id].append(
                    BatchItemResult(
                        item_index=idx,
                        item_id=concept_id,
                        success=True,
                        data=result_data,
                        error=None,
                        processing_time_ms=round(elapsed, 2),
                    )
                )
                job["successful_items"] += 1

            except Exception as e:
                elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
                error_msg = str(e)

                _batch_results[job_id].append(
                    BatchItemResult(
                        item_index=idx,
                        item_id=concept_id,
                        success=False,
                        data=None,
                        error=error_msg,
                        processing_time_ms=round(elapsed, 2),
                    )
                )
                job["failed_items"] += 1
                job["errors"].append(f"Concept {concept_id}: {error_msg}")

                if failure_mode == BatchFailureMode.FAIL_FAST:
                    break

            job["processed_items"] = idx + 1

        _finalize_job_status(job, cancel_event)

    except Exception as e:
        logger.error(f"Batch job {job_id} failed: {e}")
        job["status"] = BatchJobStatus.FAILED
        job["errors"].append(f"Job failed: {str(e)}")

    finally:
        job["completed_at"] = datetime.now(timezone.utc).isoformat()
        job["current_item"] = None


async def _process_path_batch(job_id: str) -> None:
    """Process a batch path finding job."""
    job = _batch_jobs.get(job_id)
    if not job:
        return

    job["status"] = BatchJobStatus.RUNNING
    job["started_at"] = datetime.now(timezone.utc).isoformat()

    request_data = job["request"]
    pairs = request_data["pairs"]
    failure_mode = BatchFailureMode(request_data["failure_mode"])
    cancel_event = job["cancel_event"]

    try:
        for idx, pair in enumerate(pairs):
            if cancel_event.is_set():
                break

            start_id, end_id = pair
            job["current_item"] = f"Path {start_id} -> {end_id}"
            start_time = asyncio.get_event_loop().time()

            try:
                await asyncio.sleep(0.1)  # Path finding takes longer

                result_data = {
                    "start_concept_id": start_id,
                    "end_concept_id": end_id,
                    "path_found": True,
                    "path_length": 3,
                    "path": [start_id, start_id + 100, end_id],
                }

                elapsed = (asyncio.get_event_loop().time() - start_time) * 1000

                _batch_results[job_id].append(
                    BatchItemResult(
                        item_index=idx,
                        item_id=f"{start_id}->{end_id}",
                        success=True,
                        data=result_data,
                        error=None,
                        processing_time_ms=round(elapsed, 2),
                    )
                )
                job["successful_items"] += 1

            except Exception as e:
                elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
                error_msg = str(e)

                _batch_results[job_id].append(
                    BatchItemResult(
                        item_index=idx,
                        item_id=f"{start_id}->{end_id}",
                        success=False,
                        data=None,
                        error=error_msg,
                        processing_time_ms=round(elapsed, 2),
                    )
                )
                job["failed_items"] += 1
                job["errors"].append(f"Path {start_id}->{end_id}: {error_msg}")

                if failure_mode == BatchFailureMode.FAIL_FAST:
                    break

            job["processed_items"] = idx + 1

        _finalize_job_status(job, cancel_event)

    except Exception as e:
        logger.error(f"Batch job {job_id} failed: {e}")
        job["status"] = BatchJobStatus.FAILED
        job["errors"].append(f"Job failed: {str(e)}")

    finally:
        job["completed_at"] = datetime.now(timezone.utc).isoformat()
        job["current_item"] = None


async def _process_search_batch(job_id: str) -> None:
    """Process a batch concept search job."""
    job = _batch_jobs.get(job_id)
    if not job:
        return

    job["status"] = BatchJobStatus.RUNNING
    job["started_at"] = datetime.now(timezone.utc).isoformat()

    request_data = job["request"]
    queries = request_data["queries"]
    failure_mode = BatchFailureMode(request_data["failure_mode"])
    cancel_event = job["cancel_event"]

    try:
        for idx, query in enumerate(queries):
            if cancel_event.is_set():
                break

            job["current_item"] = f"Search: {query[:30]}"
            start_time = asyncio.get_event_loop().time()

            try:
                await asyncio.sleep(0.05)

                result_data = {
                    "query": query,
                    "results": [
                        {
                            "concept_id": 1000 + idx,
                            "concept_name": f"Match for {query}",
                            "score": 0.95,
                        }
                    ],
                    "total_results": 1,
                }

                elapsed = (asyncio.get_event_loop().time() - start_time) * 1000

                _batch_results[job_id].append(
                    BatchItemResult(
                        item_index=idx,
                        item_id=query,
                        success=True,
                        data=result_data,
                        error=None,
                        processing_time_ms=round(elapsed, 2),
                    )
                )
                job["successful_items"] += 1

            except Exception as e:
                elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
                error_msg = str(e)

                _batch_results[job_id].append(
                    BatchItemResult(
                        item_index=idx,
                        item_id=query,
                        success=False,
                        data=None,
                        error=error_msg,
                        processing_time_ms=round(elapsed, 2),
                    )
                )
                job["failed_items"] += 1
                job["errors"].append(f"Search '{query}': {error_msg}")

                if failure_mode == BatchFailureMode.FAIL_FAST:
                    break

            job["processed_items"] = idx + 1

        _finalize_job_status(job, cancel_event)

    except Exception as e:
        logger.error(f"Batch job {job_id} failed: {e}")
        job["status"] = BatchJobStatus.FAILED
        job["errors"].append(f"Job failed: {str(e)}")

    finally:
        job["completed_at"] = datetime.now(timezone.utc).isoformat()
        job["current_item"] = None


async def _process_similarity_batch(job_id: str) -> None:
    """Process a batch patient similarity job."""
    job = _batch_jobs.get(job_id)
    if not job:
        return

    job["status"] = BatchJobStatus.RUNNING
    job["started_at"] = datetime.now(timezone.utc).isoformat()

    request_data = job["request"]
    patient_ids = request_data["patient_ids"]
    failure_mode = BatchFailureMode(request_data["failure_mode"])
    cancel_event = job["cancel_event"]

    try:
        for idx, patient_id in enumerate(patient_ids):
            if cancel_event.is_set():
                break

            job["current_item"] = f"Similarity for {patient_id}"
            start_time = asyncio.get_event_loop().time()

            try:
                await asyncio.sleep(0.2)  # Similarity is expensive

                result_data = {
                    "patient_id": patient_id,
                    "similar_patients": [
                        {
                            "patient_id": f"P{1000 + idx}",
                            "similarity_score": 0.85,
                            "shared_conditions": ["Diabetes", "Hypertension"],
                        }
                    ],
                }

                elapsed = (asyncio.get_event_loop().time() - start_time) * 1000

                _batch_results[job_id].append(
                    BatchItemResult(
                        item_index=idx,
                        item_id=patient_id,
                        success=True,
                        data=result_data,
                        error=None,
                        processing_time_ms=round(elapsed, 2),
                    )
                )
                job["successful_items"] += 1

            except Exception as e:
                elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
                error_msg = str(e)

                _batch_results[job_id].append(
                    BatchItemResult(
                        item_index=idx,
                        item_id=patient_id,
                        success=False,
                        data=None,
                        error=error_msg,
                        processing_time_ms=round(elapsed, 2),
                    )
                )
                job["failed_items"] += 1
                job["errors"].append(f"Patient {patient_id}: {error_msg}")

                if failure_mode == BatchFailureMode.FAIL_FAST:
                    break

            job["processed_items"] = idx + 1

        _finalize_job_status(job, cancel_event)

    except Exception as e:
        logger.error(f"Batch job {job_id} failed: {e}")
        job["status"] = BatchJobStatus.FAILED
        job["errors"].append(f"Job failed: {str(e)}")

    finally:
        job["completed_at"] = datetime.now(timezone.utc).isoformat()
        job["current_item"] = None


def _finalize_job_status(job: dict[str, Any], cancel_event: asyncio.Event) -> None:
    """Set final job status based on results."""
    if cancel_event.is_set():
        job["status"] = BatchJobStatus.CANCELLED
    elif job["failed_items"] > 0 and job["successful_items"] > 0:
        job["status"] = BatchJobStatus.PARTIAL
    elif job["failed_items"] == job["total_items"]:
        job["status"] = BatchJobStatus.FAILED
    else:
        job["status"] = BatchJobStatus.COMPLETED
