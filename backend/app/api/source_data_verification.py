"""Source Data Verification API endpoints (SDV).

Provides comprehensive source data verification operations: SDV task tracking,
finding documentation, site-level SDV progress, review records, and SDV metrics.

Endpoints:
    GET    /source-data-verification/tasks                                - List SDV tasks
    GET    /source-data-verification/tasks/{task_id}                      - Get single task
    POST   /source-data-verification/tasks                                - Create task
    PUT    /source-data-verification/tasks/{task_id}                      - Update task
    DELETE /source-data-verification/tasks/{task_id}                      - Delete task
    GET    /source-data-verification/findings                             - List findings
    GET    /source-data-verification/findings/{finding_id}                - Get single finding
    POST   /source-data-verification/findings                             - Create finding
    PUT    /source-data-verification/findings/{finding_id}                - Update finding
    DELETE /source-data-verification/findings/{finding_id}                - Delete finding
    GET    /source-data-verification/site-progress                        - List site progress
    GET    /source-data-verification/site-progress/{progress_id}          - Get single progress
    POST   /source-data-verification/site-progress                        - Create progress
    PUT    /source-data-verification/site-progress/{progress_id}          - Update progress
    DELETE /source-data-verification/site-progress/{progress_id}          - Delete progress
    GET    /source-data-verification/review-records                       - List review records
    GET    /source-data-verification/review-records/{review_id}           - Get single review
    POST   /source-data-verification/review-records                       - Create review
    PUT    /source-data-verification/review-records/{review_id}           - Update review
    DELETE /source-data-verification/review-records/{review_id}           - Delete review
    GET    /source-data-verification/metrics                              - SDV metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.source_data_verification import (
    FindingSeverity,
    FindingStatus,
    ReviewOutcome,
    SDVFinding,
    SDVFindingCreate,
    SDVFindingListResponse,
    SDVFindingUpdate,
    SDVPriority,
    SDVReviewRecord,
    SDVReviewRecordCreate,
    SDVReviewRecordListResponse,
    SDVReviewRecordUpdate,
    SDVSiteProgress,
    SDVSiteProgressCreate,
    SDVSiteProgressListResponse,
    SDVSiteProgressUpdate,
    SDVTask,
    SDVTaskCreate,
    SDVTaskListResponse,
    SDVTaskStatus,
    SDVTaskUpdate,
    SourceDataVerificationMetrics,
)
from app.services.source_data_verification_service import get_source_data_verification_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/source-data-verification",
    tags=["Source Data Verification"],
)


# ---------------------------------------------------------------------------
# SDV Tasks
# ---------------------------------------------------------------------------


@router.get(
    "/tasks",
    response_model=SDVTaskListResponse,
    summary="List SDV tasks",
    description="Retrieve SDV tasks with optional filtering by trial, status, priority, and site.",
)
async def list_sdv_tasks(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    task_status: Optional[SDVTaskStatus] = Query(None, description="Filter by task status"),
    priority: Optional[SDVPriority] = Query(None, description="Filter by priority"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
) -> SDVTaskListResponse:
    svc = get_source_data_verification_service()
    items = svc.list_sdv_tasks(
        trial_id=trial_id, task_status=task_status, priority=priority, site_id=site_id
    )
    return SDVTaskListResponse(items=items, total=len(items))


@router.get(
    "/tasks/{task_id}",
    response_model=SDVTask,
    summary="Get an SDV task",
)
async def get_sdv_task(task_id: str) -> SDVTask:
    svc = get_source_data_verification_service()
    task = svc.get_sdv_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"SDV task '{task_id}' not found")
    return task


@router.post(
    "/tasks",
    response_model=SDVTask,
    status_code=201,
    summary="Create an SDV task",
)
async def create_sdv_task(payload: SDVTaskCreate) -> SDVTask:
    svc = get_source_data_verification_service()
    return svc.create_sdv_task(payload)


@router.put(
    "/tasks/{task_id}",
    response_model=SDVTask,
    summary="Update an SDV task",
)
async def update_sdv_task(task_id: str, payload: SDVTaskUpdate) -> SDVTask:
    svc = get_source_data_verification_service()
    updated = svc.update_sdv_task(task_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"SDV task '{task_id}' not found")
    return updated


@router.delete(
    "/tasks/{task_id}",
    status_code=204,
    summary="Delete an SDV task",
)
async def delete_sdv_task(task_id: str) -> None:
    svc = get_source_data_verification_service()
    deleted = svc.delete_sdv_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"SDV task '{task_id}' not found")


# ---------------------------------------------------------------------------
# SDV Findings
# ---------------------------------------------------------------------------


@router.get(
    "/findings",
    response_model=SDVFindingListResponse,
    summary="List SDV findings",
    description="Retrieve SDV findings with optional filtering by trial, severity, status, and task.",
)
async def list_sdv_findings(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    finding_severity: Optional[FindingSeverity] = Query(None, description="Filter by finding severity"),
    finding_status: Optional[FindingStatus] = Query(None, description="Filter by finding status"),
    task_id: Optional[str] = Query(None, description="Filter by task ID"),
) -> SDVFindingListResponse:
    svc = get_source_data_verification_service()
    items = svc.list_sdv_findings(
        trial_id=trial_id, finding_severity=finding_severity,
        finding_status=finding_status, task_id=task_id
    )
    return SDVFindingListResponse(items=items, total=len(items))


@router.get(
    "/findings/{finding_id}",
    response_model=SDVFinding,
    summary="Get an SDV finding",
)
async def get_sdv_finding(finding_id: str) -> SDVFinding:
    svc = get_source_data_verification_service()
    finding = svc.get_sdv_finding(finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail=f"SDV finding '{finding_id}' not found")
    return finding


@router.post(
    "/findings",
    response_model=SDVFinding,
    status_code=201,
    summary="Create an SDV finding",
)
async def create_sdv_finding(payload: SDVFindingCreate) -> SDVFinding:
    svc = get_source_data_verification_service()
    return svc.create_sdv_finding(payload)


@router.put(
    "/findings/{finding_id}",
    response_model=SDVFinding,
    summary="Update an SDV finding",
)
async def update_sdv_finding(finding_id: str, payload: SDVFindingUpdate) -> SDVFinding:
    svc = get_source_data_verification_service()
    updated = svc.update_sdv_finding(finding_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"SDV finding '{finding_id}' not found")
    return updated


@router.delete(
    "/findings/{finding_id}",
    status_code=204,
    summary="Delete an SDV finding",
)
async def delete_sdv_finding(finding_id: str) -> None:
    svc = get_source_data_verification_service()
    deleted = svc.delete_sdv_finding(finding_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"SDV finding '{finding_id}' not found")


# ---------------------------------------------------------------------------
# SDV Site Progress
# ---------------------------------------------------------------------------


@router.get(
    "/site-progress",
    response_model=SDVSiteProgressListResponse,
    summary="List SDV site progress",
    description="Retrieve SDV site progress records with optional filtering by trial and site.",
)
async def list_sdv_site_progress(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
) -> SDVSiteProgressListResponse:
    svc = get_source_data_verification_service()
    items = svc.list_sdv_site_progress(trial_id=trial_id, site_id=site_id)
    return SDVSiteProgressListResponse(items=items, total=len(items))


@router.get(
    "/site-progress/{progress_id}",
    response_model=SDVSiteProgress,
    summary="Get an SDV site progress record",
)
async def get_sdv_site_progress(progress_id: str) -> SDVSiteProgress:
    svc = get_source_data_verification_service()
    record = svc.get_sdv_site_progress(progress_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"SDV site progress '{progress_id}' not found"
        )
    return record


@router.post(
    "/site-progress",
    response_model=SDVSiteProgress,
    status_code=201,
    summary="Create an SDV site progress record",
)
async def create_sdv_site_progress(payload: SDVSiteProgressCreate) -> SDVSiteProgress:
    svc = get_source_data_verification_service()
    return svc.create_sdv_site_progress(payload)


@router.put(
    "/site-progress/{progress_id}",
    response_model=SDVSiteProgress,
    summary="Update an SDV site progress record",
)
async def update_sdv_site_progress(
    progress_id: str, payload: SDVSiteProgressUpdate
) -> SDVSiteProgress:
    svc = get_source_data_verification_service()
    updated = svc.update_sdv_site_progress(progress_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"SDV site progress '{progress_id}' not found"
        )
    return updated


@router.delete(
    "/site-progress/{progress_id}",
    status_code=204,
    summary="Delete an SDV site progress record",
)
async def delete_sdv_site_progress(progress_id: str) -> None:
    svc = get_source_data_verification_service()
    deleted = svc.delete_sdv_site_progress(progress_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"SDV site progress '{progress_id}' not found"
        )


# ---------------------------------------------------------------------------
# SDV Review Records
# ---------------------------------------------------------------------------


@router.get(
    "/review-records",
    response_model=SDVReviewRecordListResponse,
    summary="List SDV review records",
    description="Retrieve SDV review records with optional filtering by trial, outcome, and site.",
)
async def list_sdv_review_records(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    review_outcome: Optional[ReviewOutcome] = Query(None, description="Filter by review outcome"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
) -> SDVReviewRecordListResponse:
    svc = get_source_data_verification_service()
    items = svc.list_sdv_review_records(
        trial_id=trial_id, review_outcome=review_outcome, site_id=site_id
    )
    return SDVReviewRecordListResponse(items=items, total=len(items))


@router.get(
    "/review-records/{review_id}",
    response_model=SDVReviewRecord,
    summary="Get an SDV review record",
)
async def get_sdv_review_record(review_id: str) -> SDVReviewRecord:
    svc = get_source_data_verification_service()
    record = svc.get_sdv_review_record(review_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"SDV review record '{review_id}' not found"
        )
    return record


@router.post(
    "/review-records",
    response_model=SDVReviewRecord,
    status_code=201,
    summary="Create an SDV review record",
)
async def create_sdv_review_record(payload: SDVReviewRecordCreate) -> SDVReviewRecord:
    svc = get_source_data_verification_service()
    return svc.create_sdv_review_record(payload)


@router.put(
    "/review-records/{review_id}",
    response_model=SDVReviewRecord,
    summary="Update an SDV review record",
)
async def update_sdv_review_record(
    review_id: str, payload: SDVReviewRecordUpdate
) -> SDVReviewRecord:
    svc = get_source_data_verification_service()
    updated = svc.update_sdv_review_record(review_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"SDV review record '{review_id}' not found"
        )
    return updated


@router.delete(
    "/review-records/{review_id}",
    status_code=204,
    summary="Delete an SDV review record",
)
async def delete_sdv_review_record(review_id: str) -> None:
    svc = get_source_data_verification_service()
    deleted = svc.delete_sdv_review_record(review_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"SDV review record '{review_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=SourceDataVerificationMetrics,
    summary="Get source data verification metrics",
    description="Aggregated metrics across all SDV operations, optionally filtered by trial.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> SourceDataVerificationMetrics:
    svc = get_source_data_verification_service()
    return svc.get_metrics(trial_id=trial_id)
