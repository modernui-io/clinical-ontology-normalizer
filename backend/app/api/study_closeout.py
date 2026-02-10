"""Study Closeout API endpoints.

Manages end-of-study activities including site closure visits, document
archiving, IP reconciliation, database lock confirmation, final reports,
regulatory notifications, and financial reconciliation for clinical trials.

Endpoints:
    GET    /study-closeout/closeouts                                    - List closeouts
    POST   /study-closeout/closeouts                                    - Create closeout
    GET    /study-closeout/closeouts/{id}                               - Get closeout
    PUT    /study-closeout/closeouts/{id}                               - Update closeout
    POST   /study-closeout/closeouts/{id}/initiate                      - Initiate closeout
    GET    /study-closeout/closeouts/{id}/site-closeouts                - List site closeouts
    POST   /study-closeout/closeouts/{id}/site-closeouts                - Create site closeout
    GET    /study-closeout/site-closeouts/{id}                          - Get site closeout
    PUT    /study-closeout/site-closeouts/{id}                          - Update site closeout
    POST   /study-closeout/site-closeouts/{id}/schedule-visit           - Schedule visit
    POST   /study-closeout/site-closeouts/{id}/complete                 - Complete site closure
    GET    /study-closeout/closeouts/{id}/tasks                         - List tasks
    POST   /study-closeout/closeouts/{id}/tasks                         - Create task
    GET    /study-closeout/tasks/{id}                                   - Get task
    PUT    /study-closeout/tasks/{id}                                   - Update task
    GET    /study-closeout/closeouts/{id}/archives                      - List archives
    POST   /study-closeout/closeouts/{id}/archives                      - Create archive
    GET    /study-closeout/archives/{id}                                - Get archive
    GET    /study-closeout/closeouts/{id}/regulatory-notifications      - List notifications
    POST   /study-closeout/closeouts/{id}/regulatory-notifications      - Send notification
    GET    /study-closeout/closeouts/{id}/financial-reconciliations     - List reconciliations
    POST   /study-closeout/closeouts/{id}/financial-reconciliations     - Create reconciliation
    GET    /study-closeout/financial-reconciliations/{id}               - Get reconciliation
    PUT    /study-closeout/financial-reconciliations/{id}               - Update reconciliation
    GET    /study-closeout/closeouts/{id}/progress                      - Get progress
    GET    /study-closeout/metrics                                      - Get metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.study_closeout import (
    CloseoutMetrics,
    CloseoutProgress,
    CloseoutStatus,
    CloseoutTaskCreate,
    CloseoutTaskListResponse,
    CloseoutTaskType,
    CloseoutTaskUpdate,
    CloseoutTask,
    CompleteSiteClosureRequest,
    DocumentArchive,
    DocumentArchiveCreate,
    DocumentArchiveListResponse,
    FinancialReconciliation,
    FinancialReconciliationCreate,
    FinancialReconciliationListResponse,
    FinancialReconciliationUpdate,
    RegulatoryNotification,
    RegulatoryNotificationCreate,
    RegulatoryNotificationListResponse,
    ScheduleVisitRequest,
    SiteCloseout,
    SiteCloseoutCreate,
    SiteCloseoutListResponse,
    SiteCloseoutStatus,
    SiteCloseoutUpdate,
    StudyCloseout,
    StudyCloseoutCreate,
    StudyCloseoutListResponse,
    StudyCloseoutUpdate,
    TaskStatus,
)
from app.services.study_closeout_service import get_study_closeout_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/study-closeout",
    tags=["Study Closeout"],
)


# ---------------------------------------------------------------------------
# Study Closeout CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/closeouts",
    response_model=StudyCloseoutListResponse,
    summary="List study closeouts",
    description="Retrieve study closeouts with optional filtering by status and trial.",
)
async def list_closeouts(
    status: Optional[CloseoutStatus] = Query(None, description="Filter by status"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> StudyCloseoutListResponse:
    svc = get_study_closeout_service()
    items = svc.list_closeouts(status=status, trial_id=trial_id)
    return StudyCloseoutListResponse(items=items, total=len(items))


@router.post(
    "/closeouts",
    response_model=StudyCloseout,
    status_code=201,
    summary="Create a study closeout",
)
async def create_closeout(payload: StudyCloseoutCreate) -> StudyCloseout:
    svc = get_study_closeout_service()
    return svc.create_closeout(payload)


@router.get(
    "/closeouts/{closeout_id}",
    response_model=StudyCloseout,
    summary="Get a study closeout",
)
async def get_closeout(closeout_id: str) -> StudyCloseout:
    svc = get_study_closeout_service()
    closeout = svc.get_closeout(closeout_id)
    if closeout is None:
        raise HTTPException(
            status_code=404, detail=f"Study closeout '{closeout_id}' not found"
        )
    return closeout


@router.put(
    "/closeouts/{closeout_id}",
    response_model=StudyCloseout,
    summary="Update a study closeout",
)
async def update_closeout(
    closeout_id: str, payload: StudyCloseoutUpdate
) -> StudyCloseout:
    svc = get_study_closeout_service()
    updated = svc.update_closeout(closeout_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Study closeout '{closeout_id}' not found"
        )
    return updated


@router.post(
    "/closeouts/{closeout_id}/initiate",
    response_model=StudyCloseout,
    summary="Initiate a study closeout",
    description="Move a study closeout from not_started/planning to in_progress.",
)
async def initiate_closeout(closeout_id: str) -> StudyCloseout:
    svc = get_study_closeout_service()
    try:
        result = svc.initiate_closeout(closeout_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Study closeout '{closeout_id}' not found"
        )
    return result


# ---------------------------------------------------------------------------
# Site Closeouts
# ---------------------------------------------------------------------------


@router.get(
    "/closeouts/{closeout_id}/site-closeouts",
    response_model=SiteCloseoutListResponse,
    summary="List site closeouts",
    description="List site closeouts for a study closeout.",
)
async def list_site_closeouts(
    closeout_id: str,
    status: Optional[SiteCloseoutStatus] = Query(
        None, description="Filter by site closeout status"
    ),
) -> SiteCloseoutListResponse:
    svc = get_study_closeout_service()
    co = svc.get_closeout(closeout_id)
    if co is None:
        raise HTTPException(
            status_code=404, detail=f"Study closeout '{closeout_id}' not found"
        )
    items = svc.list_site_closeouts(closeout_id, status=status)
    return SiteCloseoutListResponse(items=items, total=len(items))


@router.post(
    "/closeouts/{closeout_id}/site-closeouts",
    response_model=SiteCloseout,
    status_code=201,
    summary="Create a site closeout",
)
async def create_site_closeout(
    closeout_id: str, payload: SiteCloseoutCreate
) -> SiteCloseout:
    svc = get_study_closeout_service()
    co = svc.get_closeout(closeout_id)
    if co is None:
        raise HTTPException(
            status_code=404, detail=f"Study closeout '{closeout_id}' not found"
        )
    return svc.create_site_closeout(closeout_id, payload)


@router.get(
    "/site-closeouts/{site_closeout_id}",
    response_model=SiteCloseout,
    summary="Get a site closeout",
)
async def get_site_closeout(site_closeout_id: str) -> SiteCloseout:
    svc = get_study_closeout_service()
    sc = svc.get_site_closeout(site_closeout_id)
    if sc is None:
        raise HTTPException(
            status_code=404,
            detail=f"Site closeout '{site_closeout_id}' not found",
        )
    return sc


@router.put(
    "/site-closeouts/{site_closeout_id}",
    response_model=SiteCloseout,
    summary="Update a site closeout",
)
async def update_site_closeout(
    site_closeout_id: str, payload: SiteCloseoutUpdate
) -> SiteCloseout:
    svc = get_study_closeout_service()
    updated = svc.update_site_closeout(site_closeout_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Site closeout '{site_closeout_id}' not found",
        )
    return updated


@router.post(
    "/site-closeouts/{site_closeout_id}/schedule-visit",
    response_model=SiteCloseout,
    summary="Schedule a site closure visit",
    description="Schedule a closure visit for a site.",
)
async def schedule_site_visit(
    site_closeout_id: str, payload: ScheduleVisitRequest
) -> SiteCloseout:
    svc = get_study_closeout_service()
    try:
        result = svc.schedule_site_visit(site_closeout_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Site closeout '{site_closeout_id}' not found",
        )
    return result


@router.post(
    "/site-closeouts/{site_closeout_id}/complete",
    response_model=SiteCloseout,
    summary="Complete a site closure",
    description="Mark a site closure as complete, finalizing all closeout activities.",
)
async def complete_site_closure(
    site_closeout_id: str, payload: CompleteSiteClosureRequest
) -> SiteCloseout:
    svc = get_study_closeout_service()
    try:
        result = svc.complete_site_closure(site_closeout_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Site closeout '{site_closeout_id}' not found",
        )
    return result


# ---------------------------------------------------------------------------
# Closeout Tasks
# ---------------------------------------------------------------------------


@router.get(
    "/closeouts/{closeout_id}/tasks",
    response_model=CloseoutTaskListResponse,
    summary="List closeout tasks",
    description="List tasks for a study closeout with optional filtering.",
)
async def list_tasks(
    closeout_id: str,
    status: Optional[TaskStatus] = Query(None, description="Filter by status"),
    task_type: Optional[CloseoutTaskType] = Query(
        None, description="Filter by task type"
    ),
) -> CloseoutTaskListResponse:
    svc = get_study_closeout_service()
    co = svc.get_closeout(closeout_id)
    if co is None:
        raise HTTPException(
            status_code=404, detail=f"Study closeout '{closeout_id}' not found"
        )
    items = svc.list_tasks(closeout_id, status=status, task_type=task_type)
    return CloseoutTaskListResponse(items=items, total=len(items))


@router.post(
    "/closeouts/{closeout_id}/tasks",
    response_model=CloseoutTask,
    status_code=201,
    summary="Create a closeout task",
)
async def create_task(
    closeout_id: str, payload: CloseoutTaskCreate
) -> CloseoutTask:
    svc = get_study_closeout_service()
    co = svc.get_closeout(closeout_id)
    if co is None:
        raise HTTPException(
            status_code=404, detail=f"Study closeout '{closeout_id}' not found"
        )
    return svc.create_task(closeout_id, payload)


@router.get(
    "/tasks/{task_id}",
    response_model=CloseoutTask,
    summary="Get a closeout task",
)
async def get_task(task_id: str) -> CloseoutTask:
    svc = get_study_closeout_service()
    task = svc.get_task(task_id)
    if task is None:
        raise HTTPException(
            status_code=404, detail=f"Closeout task '{task_id}' not found"
        )
    return task


@router.put(
    "/tasks/{task_id}",
    response_model=CloseoutTask,
    summary="Update a closeout task",
)
async def update_task(task_id: str, payload: CloseoutTaskUpdate) -> CloseoutTask:
    svc = get_study_closeout_service()
    updated = svc.update_task(task_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Closeout task '{task_id}' not found"
        )
    return updated


# ---------------------------------------------------------------------------
# Document Archives
# ---------------------------------------------------------------------------


@router.get(
    "/closeouts/{closeout_id}/archives",
    response_model=DocumentArchiveListResponse,
    summary="List document archives",
    description="List document archives for a study closeout.",
)
async def list_archives(closeout_id: str) -> DocumentArchiveListResponse:
    svc = get_study_closeout_service()
    co = svc.get_closeout(closeout_id)
    if co is None:
        raise HTTPException(
            status_code=404, detail=f"Study closeout '{closeout_id}' not found"
        )
    items = svc.list_archives(closeout_id)
    return DocumentArchiveListResponse(items=items, total=len(items))


@router.post(
    "/closeouts/{closeout_id}/archives",
    response_model=DocumentArchive,
    status_code=201,
    summary="Create a document archive",
)
async def create_archive(
    closeout_id: str, payload: DocumentArchiveCreate
) -> DocumentArchive:
    svc = get_study_closeout_service()
    try:
        return svc.create_archive(closeout_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/archives/{archive_id}",
    response_model=DocumentArchive,
    summary="Get a document archive",
)
async def get_archive(archive_id: str) -> DocumentArchive:
    svc = get_study_closeout_service()
    archive = svc.get_archive(archive_id)
    if archive is None:
        raise HTTPException(
            status_code=404, detail=f"Archive '{archive_id}' not found"
        )
    return archive


# ---------------------------------------------------------------------------
# Regulatory Notifications
# ---------------------------------------------------------------------------


@router.get(
    "/closeouts/{closeout_id}/regulatory-notifications",
    response_model=RegulatoryNotificationListResponse,
    summary="List regulatory notifications",
    description="List regulatory notifications for a study closeout.",
)
async def list_regulatory_notifications(
    closeout_id: str,
) -> RegulatoryNotificationListResponse:
    svc = get_study_closeout_service()
    co = svc.get_closeout(closeout_id)
    if co is None:
        raise HTTPException(
            status_code=404, detail=f"Study closeout '{closeout_id}' not found"
        )
    items = svc.list_regulatory_notifications(closeout_id)
    return RegulatoryNotificationListResponse(items=items, total=len(items))


@router.post(
    "/closeouts/{closeout_id}/regulatory-notifications",
    response_model=RegulatoryNotification,
    status_code=201,
    summary="Send a regulatory notification",
    description="Create and send a regulatory notification for a study closeout.",
)
async def send_regulatory_notification(
    closeout_id: str, payload: RegulatoryNotificationCreate
) -> RegulatoryNotification:
    from app.schemas.study_closeout import RegulatoryNotification

    svc = get_study_closeout_service()
    co = svc.get_closeout(closeout_id)
    if co is None:
        raise HTTPException(
            status_code=404, detail=f"Study closeout '{closeout_id}' not found"
        )
    return svc.send_regulatory_notification(closeout_id, payload)


# ---------------------------------------------------------------------------
# Financial Reconciliations
# ---------------------------------------------------------------------------


@router.get(
    "/closeouts/{closeout_id}/financial-reconciliations",
    response_model=FinancialReconciliationListResponse,
    summary="List financial reconciliations",
    description="List financial reconciliations for a study closeout.",
)
async def list_financial_reconciliations(
    closeout_id: str,
) -> FinancialReconciliationListResponse:
    svc = get_study_closeout_service()
    co = svc.get_closeout(closeout_id)
    if co is None:
        raise HTTPException(
            status_code=404, detail=f"Study closeout '{closeout_id}' not found"
        )
    items = svc.list_financial_reconciliations(closeout_id)
    return FinancialReconciliationListResponse(items=items, total=len(items))


@router.post(
    "/closeouts/{closeout_id}/financial-reconciliations",
    response_model=FinancialReconciliation,
    status_code=201,
    summary="Create a financial reconciliation",
)
async def create_financial_reconciliation(
    closeout_id: str, payload: FinancialReconciliationCreate
) -> FinancialReconciliation:
    svc = get_study_closeout_service()
    co = svc.get_closeout(closeout_id)
    if co is None:
        raise HTTPException(
            status_code=404, detail=f"Study closeout '{closeout_id}' not found"
        )
    return svc.create_financial_reconciliation(closeout_id, payload)


@router.get(
    "/financial-reconciliations/{reconciliation_id}",
    response_model=FinancialReconciliation,
    summary="Get a financial reconciliation",
)
async def get_financial_reconciliation(
    reconciliation_id: str,
) -> FinancialReconciliation:
    svc = get_study_closeout_service()
    rec = svc.get_financial_reconciliation(reconciliation_id)
    if rec is None:
        raise HTTPException(
            status_code=404,
            detail=f"Financial reconciliation '{reconciliation_id}' not found",
        )
    return rec


@router.put(
    "/financial-reconciliations/{reconciliation_id}",
    response_model=FinancialReconciliation,
    summary="Update a financial reconciliation",
)
async def update_financial_reconciliation(
    reconciliation_id: str, payload: FinancialReconciliationUpdate
) -> FinancialReconciliation:
    svc = get_study_closeout_service()
    updated = svc.update_financial_reconciliation(reconciliation_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Financial reconciliation '{reconciliation_id}' not found",
        )
    return updated


# ---------------------------------------------------------------------------
# Progress & Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/closeouts/{closeout_id}/progress",
    response_model=CloseoutProgress,
    summary="Get closeout progress",
    description="Get a progress summary for a study closeout.",
)
async def get_closeout_progress(closeout_id: str) -> CloseoutProgress:
    svc = get_study_closeout_service()
    progress = svc.get_closeout_progress(closeout_id)
    if progress is None:
        raise HTTPException(
            status_code=404, detail=f"Study closeout '{closeout_id}' not found"
        )
    return progress


@router.get(
    "/metrics",
    response_model=CloseoutMetrics,
    summary="Get closeout metrics",
    description="Aggregated study closeout operational metrics.",
)
async def get_metrics() -> CloseoutMetrics:
    svc = get_study_closeout_service()
    return svc.get_metrics()
