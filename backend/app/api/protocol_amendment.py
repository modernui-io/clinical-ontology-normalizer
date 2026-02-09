"""Protocol Amendment Management API endpoints (CLINICAL-16).

Provides comprehensive protocol amendment operations: amendment CRUD, lifecycle
management (draft -> sponsor_review -> irb_submitted -> irb_approved ->
implemented), IRB submission tracking across sites, impact assessment,
site implementation tracking, re-consent progress, and amendment metrics.

Endpoints:
    GET    /protocol-amendments/                                                - List amendments
    GET    /protocol-amendments/{amendment_id}                                  - Get single amendment
    POST   /protocol-amendments/                                                - Create amendment
    PUT    /protocol-amendments/{amendment_id}                                  - Update amendment
    DELETE /protocol-amendments/{amendment_id}                                  - Delete amendment
    POST   /protocol-amendments/{amendment_id}/submit                           - Submit for review
    POST   /protocol-amendments/{amendment_id}/approve                          - Approve amendment
    POST   /protocol-amendments/{amendment_id}/implement                        - Implement amendment
    POST   /protocol-amendments/{amendment_id}/withdraw                         - Withdraw amendment
    GET    /protocol-amendments/{amendment_id}/irb-submissions                  - List IRB submissions
    GET    /protocol-amendments/irb-submissions/{submission_id}                 - Get IRB submission
    POST   /protocol-amendments/{amendment_id}/irb-submissions                  - Create IRB submission
    PUT    /protocol-amendments/irb-submissions/{submission_id}                 - Update IRB submission
    GET    /protocol-amendments/{amendment_id}/impact-assessment                - Get impact assessment
    POST   /protocol-amendments/{amendment_id}/impact-assessment                - Create impact assessment
    GET    /protocol-amendments/{amendment_id}/site-implementations             - Get site implementations
    GET    /protocol-amendments/{amendment_id}/sites/{site_id}/implementation   - Get site implementation
    PUT    /protocol-amendments/{amendment_id}/sites/{site_id}/implementation   - Update site implementation
    PUT    /protocol-amendments/{amendment_id}/sites/{site_id}/re-consent       - Update re-consent progress
    GET    /protocol-amendments/tracker/{trial_id}                              - Get amendment tracker
    GET    /protocol-amendments/metrics                                         - Get amendment metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.protocol_amendment import (
    AmendmentCreate,
    AmendmentImpactAssessment,
    AmendmentImplement,
    AmendmentListResponse,
    AmendmentMetrics,
    AmendmentStatus,
    AmendmentSubmit,
    AmendmentTracker,
    AmendmentType,
    AmendmentUpdate,
    IRBStatus,
    IRBSubmission,
    IRBSubmissionCreate,
    IRBSubmissionListResponse,
    IRBSubmissionUpdate,
    ProtocolAmendment,
    ReConsentUpdate,
    SiteImplementationListResponse,
    SiteImplementationStatus,
)
from app.services.protocol_amendment_service import get_protocol_amendment_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/protocol-amendments",
    tags=["Protocol Amendments"],
)


# ---------------------------------------------------------------------------
# Amendment CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=AmendmentListResponse,
    summary="List protocol amendments",
    description="Retrieve amendments with optional filtering by trial, status, and type.",
)
async def list_amendments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[AmendmentStatus] = Query(None, description="Filter by status"),
    amendment_type: Optional[AmendmentType] = Query(None, description="Filter by type"),
) -> AmendmentListResponse:
    svc = get_protocol_amendment_service()
    items = svc.list_amendments(trial_id=trial_id, status=status, amendment_type=amendment_type)
    return AmendmentListResponse(items=items, total=len(items))


@router.get(
    "/metrics",
    response_model=AmendmentMetrics,
    summary="Get amendment metrics",
    description="Aggregated protocol amendment metrics across all trials.",
)
async def get_metrics() -> AmendmentMetrics:
    svc = get_protocol_amendment_service()
    return svc.get_metrics()


@router.get(
    "/tracker/{trial_id}",
    response_model=AmendmentTracker,
    summary="Get amendment tracker for a trial",
    description="Aggregated amendment tracking data for a specific trial.",
)
async def get_amendment_tracker(trial_id: str) -> AmendmentTracker:
    svc = get_protocol_amendment_service()
    return svc.get_amendment_tracker(trial_id)


@router.get(
    "/irb-submissions/{submission_id}",
    response_model=IRBSubmission,
    summary="Get an IRB submission",
)
async def get_irb_submission(submission_id: str) -> IRBSubmission:
    svc = get_protocol_amendment_service()
    sub = svc.get_irb_submission(submission_id)
    if sub is None:
        raise HTTPException(status_code=404, detail=f"IRB submission '{submission_id}' not found")
    return sub


@router.put(
    "/irb-submissions/{submission_id}",
    response_model=IRBSubmission,
    summary="Update an IRB submission",
    description="Update IRB submission status, approval date, conditions, or review date.",
)
async def update_irb_submission(
    submission_id: str, payload: IRBSubmissionUpdate
) -> IRBSubmission:
    svc = get_protocol_amendment_service()
    updated = svc.update_irb_submission(submission_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"IRB submission '{submission_id}' not found")
    return updated


@router.get(
    "/{amendment_id}",
    response_model=ProtocolAmendment,
    summary="Get a protocol amendment",
)
async def get_amendment(amendment_id: str) -> ProtocolAmendment:
    svc = get_protocol_amendment_service()
    amd = svc.get_amendment(amendment_id)
    if amd is None:
        raise HTTPException(status_code=404, detail=f"Amendment '{amendment_id}' not found")
    return amd


@router.post(
    "/",
    response_model=ProtocolAmendment,
    status_code=201,
    summary="Create a protocol amendment",
)
async def create_amendment(payload: AmendmentCreate) -> ProtocolAmendment:
    svc = get_protocol_amendment_service()
    return svc.create_amendment(payload)


@router.put(
    "/{amendment_id}",
    response_model=ProtocolAmendment,
    summary="Update a protocol amendment",
)
async def update_amendment(
    amendment_id: str, payload: AmendmentUpdate
) -> ProtocolAmendment:
    svc = get_protocol_amendment_service()
    updated = svc.update_amendment(amendment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Amendment '{amendment_id}' not found")
    return updated


@router.delete(
    "/{amendment_id}",
    status_code=204,
    summary="Delete a protocol amendment",
)
async def delete_amendment(amendment_id: str) -> None:
    svc = get_protocol_amendment_service()
    deleted = svc.delete_amendment(amendment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Amendment '{amendment_id}' not found")


# ---------------------------------------------------------------------------
# Amendment Lifecycle
# ---------------------------------------------------------------------------


@router.post(
    "/{amendment_id}/submit",
    response_model=ProtocolAmendment,
    summary="Submit amendment for review",
    description="Transition amendment from draft to sponsor_review status.",
)
async def submit_amendment(
    amendment_id: str, payload: AmendmentSubmit
) -> ProtocolAmendment:
    svc = get_protocol_amendment_service()
    try:
        result = svc.submit_amendment(amendment_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Amendment '{amendment_id}' not found")
    return result


@router.post(
    "/{amendment_id}/approve",
    response_model=ProtocolAmendment,
    summary="Approve amendment",
    description="Mark amendment as IRB approved. Requires current status of irb_submitted.",
)
async def approve_amendment(amendment_id: str) -> ProtocolAmendment:
    svc = get_protocol_amendment_service()
    try:
        result = svc.approve_amendment(amendment_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Amendment '{amendment_id}' not found")
    return result


@router.post(
    "/{amendment_id}/implement",
    response_model=ProtocolAmendment,
    summary="Implement amendment",
    description="Mark amendment as implemented. Requires current status of irb_approved.",
)
async def implement_amendment(
    amendment_id: str, payload: AmendmentImplement
) -> ProtocolAmendment:
    svc = get_protocol_amendment_service()
    try:
        result = svc.implement_amendment(amendment_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Amendment '{amendment_id}' not found")
    return result


@router.post(
    "/{amendment_id}/withdraw",
    response_model=ProtocolAmendment,
    summary="Withdraw amendment",
    description="Withdraw a protocol amendment. Cannot withdraw after implementation.",
)
async def withdraw_amendment(amendment_id: str) -> ProtocolAmendment:
    svc = get_protocol_amendment_service()
    try:
        result = svc.withdraw_amendment(amendment_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Amendment '{amendment_id}' not found")
    return result


# ---------------------------------------------------------------------------
# IRB Submissions
# ---------------------------------------------------------------------------


@router.get(
    "/{amendment_id}/irb-submissions",
    response_model=IRBSubmissionListResponse,
    summary="List IRB submissions for an amendment",
    description="Retrieve IRB submissions with optional filtering by site and status.",
)
async def list_irb_submissions(
    amendment_id: str,
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    status: Optional[IRBStatus] = Query(None, description="Filter by IRB status"),
) -> IRBSubmissionListResponse:
    svc = get_protocol_amendment_service()
    items = svc.list_irb_submissions(
        amendment_id=amendment_id, site_id=site_id, status=status
    )
    return IRBSubmissionListResponse(items=items, total=len(items))


@router.post(
    "/{amendment_id}/irb-submissions",
    response_model=IRBSubmission,
    status_code=201,
    summary="Create an IRB submission",
)
async def create_irb_submission(
    amendment_id: str, payload: IRBSubmissionCreate
) -> IRBSubmission:
    svc = get_protocol_amendment_service()
    try:
        return svc.create_irb_submission(amendment_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Impact Assessment
# ---------------------------------------------------------------------------


@router.get(
    "/{amendment_id}/impact-assessment",
    response_model=AmendmentImpactAssessment,
    summary="Get impact assessment",
    description="Retrieve the impact assessment for a protocol amendment.",
)
async def get_impact_assessment(amendment_id: str) -> AmendmentImpactAssessment:
    svc = get_protocol_amendment_service()
    assessment = svc.get_impact_assessment(amendment_id)
    if assessment is None:
        raise HTTPException(
            status_code=404,
            detail=f"Impact assessment for amendment '{amendment_id}' not found",
        )
    return assessment


@router.post(
    "/{amendment_id}/impact-assessment",
    response_model=AmendmentImpactAssessment,
    status_code=201,
    summary="Create or update impact assessment",
    description="Create or replace the impact assessment for a protocol amendment.",
)
async def create_impact_assessment(
    amendment_id: str, payload: AmendmentImpactAssessment
) -> AmendmentImpactAssessment:
    svc = get_protocol_amendment_service()
    try:
        return svc.create_impact_assessment(amendment_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Site Implementation
# ---------------------------------------------------------------------------


@router.get(
    "/{amendment_id}/site-implementations",
    response_model=SiteImplementationListResponse,
    summary="Get site implementation statuses",
    description="Retrieve implementation status for all sites for an amendment.",
)
async def get_site_implementations(amendment_id: str) -> SiteImplementationListResponse:
    svc = get_protocol_amendment_service()
    items = svc.get_site_implementations(amendment_id)
    return SiteImplementationListResponse(items=items, total=len(items))


@router.get(
    "/{amendment_id}/sites/{site_id}/implementation",
    response_model=SiteImplementationStatus,
    summary="Get site implementation status",
)
async def get_site_implementation(
    amendment_id: str, site_id: str
) -> SiteImplementationStatus:
    svc = get_protocol_amendment_service()
    impl = svc.get_site_implementation(amendment_id, site_id)
    if impl is None:
        raise HTTPException(
            status_code=404,
            detail=f"Implementation status for amendment '{amendment_id}' site '{site_id}' not found",
        )
    return impl


@router.put(
    "/{amendment_id}/sites/{site_id}/implementation",
    response_model=SiteImplementationStatus,
    summary="Update site implementation status",
    description="Mark a site as implemented for an amendment.",
)
async def update_site_implementation(
    amendment_id: str,
    site_id: str,
    implemented: bool = Query(..., description="Whether the amendment is implemented"),
    implementation_date: Optional[str] = Query(None, description="Implementation date (ISO format)"),
) -> SiteImplementationStatus:
    from datetime import datetime as dt

    svc = get_protocol_amendment_service()
    impl_date = None
    if implementation_date:
        impl_date = dt.fromisoformat(implementation_date)
    result = svc.update_site_implementation(
        amendment_id, site_id,
        implemented=implemented,
        implementation_date=impl_date,
    )
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Implementation status for amendment '{amendment_id}' site '{site_id}' not found",
        )
    return result


@router.put(
    "/{amendment_id}/sites/{site_id}/re-consent",
    response_model=SiteImplementationStatus,
    summary="Update re-consent progress",
    description="Update the re-consent progress for a specific site.",
)
async def update_re_consent_progress(
    amendment_id: str, site_id: str, payload: ReConsentUpdate
) -> SiteImplementationStatus:
    svc = get_protocol_amendment_service()
    result = svc.update_re_consent_progress(amendment_id, site_id, payload)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Implementation status for amendment '{amendment_id}' site '{site_id}' not found",
        )
    return result
