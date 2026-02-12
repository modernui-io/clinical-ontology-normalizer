"""Publication Planning & Management (PUB-PLAN) API endpoints.

Provides comprehensive publication planning operations: publication plan management,
manuscript tracking, author management, congress abstract submissions, journal
submissions, and publication operational metrics.

Endpoints:
    GET    /publication-planning/plans                                - List publication plans
    GET    /publication-planning/plans/{plan_id}                      - Get single plan
    POST   /publication-planning/plans                                - Create plan
    PUT    /publication-planning/plans/{plan_id}                      - Update plan
    DELETE /publication-planning/plans/{plan_id}                      - Delete plan
    GET    /publication-planning/manuscripts                          - List manuscripts
    GET    /publication-planning/manuscripts/{manuscript_id}          - Get single manuscript
    POST   /publication-planning/manuscripts                          - Create manuscript
    PUT    /publication-planning/manuscripts/{manuscript_id}          - Update manuscript
    DELETE /publication-planning/manuscripts/{manuscript_id}          - Delete manuscript
    GET    /publication-planning/authors                              - List authors
    GET    /publication-planning/authors/{author_id}                  - Get single author
    POST   /publication-planning/authors                              - Create author
    PUT    /publication-planning/authors/{author_id}                  - Update author
    DELETE /publication-planning/authors/{author_id}                  - Delete author
    GET    /publication-planning/congress-submissions                 - List congress submissions
    GET    /publication-planning/congress-submissions/{submission_id} - Get single submission
    POST   /publication-planning/congress-submissions                 - Create submission
    PUT    /publication-planning/congress-submissions/{submission_id} - Update submission
    DELETE /publication-planning/congress-submissions/{submission_id} - Delete submission
    GET    /publication-planning/journal-submissions                  - List journal submissions
    GET    /publication-planning/journal-submissions/{submission_id}  - Get single submission
    POST   /publication-planning/journal-submissions                  - Create submission
    PUT    /publication-planning/journal-submissions/{submission_id}  - Update submission
    DELETE /publication-planning/journal-submissions/{submission_id}  - Delete submission
    GET    /publication-planning/metrics                              - Publication metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.publication_planning import (
    Author,
    AuthorCreate,
    AuthorListResponse,
    AuthorRole,
    AuthorUpdate,
    CongressSubmission,
    CongressSubmissionCreate,
    CongressSubmissionListResponse,
    CongressSubmissionUpdate,
    CongressTier,
    JournalSubmission,
    JournalSubmissionCreate,
    JournalSubmissionListResponse,
    JournalSubmissionUpdate,
    Manuscript,
    ManuscriptCreate,
    ManuscriptListResponse,
    ManuscriptUpdate,
    PublicationMetrics,
    PublicationPlan,
    PublicationPlanCreate,
    PublicationPlanListResponse,
    PublicationPlanUpdate,
    PublicationStatus,
    PublicationType,
)
from app.services.publication_planning_service import get_publication_planning_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/publication-planning",
    tags=["Publication Planning"],
)


# ---------------------------------------------------------------------------
# Publication Plan Management
# ---------------------------------------------------------------------------


@router.get(
    "/plans",
    response_model=PublicationPlanListResponse,
    summary="List publication plans",
    description="Retrieve publication plans with optional filtering by trial ID and status.",
)
async def list_plans(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[str] = Query(None, description="Filter by plan status"),
) -> PublicationPlanListResponse:
    svc = get_publication_planning_service()
    items = svc.list_plans(trial_id=trial_id, status=status)
    return PublicationPlanListResponse(items=items, total=len(items))


@router.get(
    "/plans/{plan_id}",
    response_model=PublicationPlan,
    summary="Get a publication plan",
)
async def get_plan(plan_id: str) -> PublicationPlan:
    svc = get_publication_planning_service()
    plan = svc.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Publication plan '{plan_id}' not found")
    return plan


@router.post(
    "/plans",
    response_model=PublicationPlan,
    status_code=201,
    summary="Create a publication plan",
)
async def create_plan(payload: PublicationPlanCreate) -> PublicationPlan:
    svc = get_publication_planning_service()
    return svc.create_plan(payload)


@router.put(
    "/plans/{plan_id}",
    response_model=PublicationPlan,
    summary="Update a publication plan",
)
async def update_plan(plan_id: str, payload: PublicationPlanUpdate) -> PublicationPlan:
    svc = get_publication_planning_service()
    updated = svc.update_plan(plan_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Publication plan '{plan_id}' not found")
    return updated


@router.delete(
    "/plans/{plan_id}",
    status_code=204,
    summary="Delete a publication plan",
)
async def delete_plan(plan_id: str) -> None:
    svc = get_publication_planning_service()
    deleted = svc.delete_plan(plan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Publication plan '{plan_id}' not found")


# ---------------------------------------------------------------------------
# Manuscript Management
# ---------------------------------------------------------------------------


@router.get(
    "/manuscripts",
    response_model=ManuscriptListResponse,
    summary="List manuscripts",
    description="Retrieve manuscripts with optional filtering by plan, trial, status, and type.",
)
async def list_manuscripts(
    plan_id: Optional[str] = Query(None, description="Filter by plan ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[PublicationStatus] = Query(None, description="Filter by publication status"),
    publication_type: Optional[PublicationType] = Query(None, description="Filter by publication type"),
) -> ManuscriptListResponse:
    svc = get_publication_planning_service()
    items = svc.list_manuscripts(
        plan_id=plan_id, trial_id=trial_id, status=status, publication_type=publication_type,
    )
    return ManuscriptListResponse(items=items, total=len(items))


@router.get(
    "/manuscripts/{manuscript_id}",
    response_model=Manuscript,
    summary="Get a manuscript",
)
async def get_manuscript(manuscript_id: str) -> Manuscript:
    svc = get_publication_planning_service()
    manuscript = svc.get_manuscript(manuscript_id)
    if manuscript is None:
        raise HTTPException(status_code=404, detail=f"Manuscript '{manuscript_id}' not found")
    return manuscript


@router.post(
    "/manuscripts",
    response_model=Manuscript,
    status_code=201,
    summary="Create a manuscript",
)
async def create_manuscript(payload: ManuscriptCreate) -> Manuscript:
    svc = get_publication_planning_service()
    return svc.create_manuscript(payload)


@router.put(
    "/manuscripts/{manuscript_id}",
    response_model=Manuscript,
    summary="Update a manuscript",
)
async def update_manuscript(
    manuscript_id: str, payload: ManuscriptUpdate
) -> Manuscript:
    svc = get_publication_planning_service()
    updated = svc.update_manuscript(manuscript_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Manuscript '{manuscript_id}' not found")
    return updated


@router.delete(
    "/manuscripts/{manuscript_id}",
    status_code=204,
    summary="Delete a manuscript",
)
async def delete_manuscript(manuscript_id: str) -> None:
    svc = get_publication_planning_service()
    deleted = svc.delete_manuscript(manuscript_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Manuscript '{manuscript_id}' not found")


# ---------------------------------------------------------------------------
# Author Management
# ---------------------------------------------------------------------------


@router.get(
    "/authors",
    response_model=AuthorListResponse,
    summary="List authors",
    description="Retrieve authors with optional filtering by manuscript ID and role.",
)
async def list_authors(
    manuscript_id: Optional[str] = Query(None, description="Filter by manuscript ID"),
    role: Optional[AuthorRole] = Query(None, description="Filter by author role"),
) -> AuthorListResponse:
    svc = get_publication_planning_service()
    items = svc.list_authors(manuscript_id=manuscript_id, role=role)
    return AuthorListResponse(items=items, total=len(items))


@router.get(
    "/authors/{author_id}",
    response_model=Author,
    summary="Get an author",
)
async def get_author(author_id: str) -> Author:
    svc = get_publication_planning_service()
    author = svc.get_author(author_id)
    if author is None:
        raise HTTPException(status_code=404, detail=f"Author '{author_id}' not found")
    return author


@router.post(
    "/authors",
    response_model=Author,
    status_code=201,
    summary="Create an author",
)
async def create_author(payload: AuthorCreate) -> Author:
    svc = get_publication_planning_service()
    return svc.create_author(payload)


@router.put(
    "/authors/{author_id}",
    response_model=Author,
    summary="Update an author",
)
async def update_author(author_id: str, payload: AuthorUpdate) -> Author:
    svc = get_publication_planning_service()
    updated = svc.update_author(author_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Author '{author_id}' not found")
    return updated


@router.delete(
    "/authors/{author_id}",
    status_code=204,
    summary="Delete an author",
)
async def delete_author(author_id: str) -> None:
    svc = get_publication_planning_service()
    deleted = svc.delete_author(author_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Author '{author_id}' not found")


# ---------------------------------------------------------------------------
# Congress Submission Management
# ---------------------------------------------------------------------------


@router.get(
    "/congress-submissions",
    response_model=CongressSubmissionListResponse,
    summary="List congress submissions",
    description="Retrieve congress submissions with optional filtering by plan, trial, tier, and status.",
)
async def list_congress_submissions(
    plan_id: Optional[str] = Query(None, description="Filter by plan ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    congress_tier: Optional[CongressTier] = Query(None, description="Filter by congress tier"),
    status: Optional[PublicationStatus] = Query(None, description="Filter by status"),
) -> CongressSubmissionListResponse:
    svc = get_publication_planning_service()
    items = svc.list_congress_submissions(
        plan_id=plan_id, trial_id=trial_id, congress_tier=congress_tier, status=status,
    )
    return CongressSubmissionListResponse(items=items, total=len(items))


@router.get(
    "/congress-submissions/{submission_id}",
    response_model=CongressSubmission,
    summary="Get a congress submission",
)
async def get_congress_submission(submission_id: str) -> CongressSubmission:
    svc = get_publication_planning_service()
    submission = svc.get_congress_submission(submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail=f"Congress submission '{submission_id}' not found")
    return submission


@router.post(
    "/congress-submissions",
    response_model=CongressSubmission,
    status_code=201,
    summary="Create a congress submission",
)
async def create_congress_submission(payload: CongressSubmissionCreate) -> CongressSubmission:
    svc = get_publication_planning_service()
    return svc.create_congress_submission(payload)


@router.put(
    "/congress-submissions/{submission_id}",
    response_model=CongressSubmission,
    summary="Update a congress submission",
)
async def update_congress_submission(
    submission_id: str, payload: CongressSubmissionUpdate
) -> CongressSubmission:
    svc = get_publication_planning_service()
    updated = svc.update_congress_submission(submission_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Congress submission '{submission_id}' not found")
    return updated


@router.delete(
    "/congress-submissions/{submission_id}",
    status_code=204,
    summary="Delete a congress submission",
)
async def delete_congress_submission(submission_id: str) -> None:
    svc = get_publication_planning_service()
    deleted = svc.delete_congress_submission(submission_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Congress submission '{submission_id}' not found")


# ---------------------------------------------------------------------------
# Journal Submission Management
# ---------------------------------------------------------------------------


@router.get(
    "/journal-submissions",
    response_model=JournalSubmissionListResponse,
    summary="List journal submissions",
    description="Retrieve journal submissions with optional filtering by manuscript ID and decision.",
)
async def list_journal_submissions(
    manuscript_id: Optional[str] = Query(None, description="Filter by manuscript ID"),
    decision: Optional[str] = Query(None, description="Filter by decision"),
) -> JournalSubmissionListResponse:
    svc = get_publication_planning_service()
    items = svc.list_journal_submissions(manuscript_id=manuscript_id, decision=decision)
    return JournalSubmissionListResponse(items=items, total=len(items))


@router.get(
    "/journal-submissions/{submission_id}",
    response_model=JournalSubmission,
    summary="Get a journal submission",
)
async def get_journal_submission(submission_id: str) -> JournalSubmission:
    svc = get_publication_planning_service()
    submission = svc.get_journal_submission(submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail=f"Journal submission '{submission_id}' not found")
    return submission


@router.post(
    "/journal-submissions",
    response_model=JournalSubmission,
    status_code=201,
    summary="Create a journal submission",
)
async def create_journal_submission(payload: JournalSubmissionCreate) -> JournalSubmission:
    svc = get_publication_planning_service()
    return svc.create_journal_submission(payload)


@router.put(
    "/journal-submissions/{submission_id}",
    response_model=JournalSubmission,
    summary="Update a journal submission",
)
async def update_journal_submission(
    submission_id: str, payload: JournalSubmissionUpdate
) -> JournalSubmission:
    svc = get_publication_planning_service()
    updated = svc.update_journal_submission(submission_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Journal submission '{submission_id}' not found")
    return updated


@router.delete(
    "/journal-submissions/{submission_id}",
    status_code=204,
    summary="Delete a journal submission",
)
async def delete_journal_submission(submission_id: str) -> None:
    svc = get_publication_planning_service()
    deleted = svc.delete_journal_submission(submission_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Journal submission '{submission_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=PublicationMetrics,
    summary="Get publication metrics",
    description="Compute aggregated publication planning metrics across all plans, manuscripts, and submissions.",
)
async def get_metrics() -> PublicationMetrics:
    svc = get_publication_planning_service()
    return svc.get_metrics()
