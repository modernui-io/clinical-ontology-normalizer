"""Site Initiation & Activation API endpoints (CLINICAL-17).

Provides comprehensive site initiation operations: site CRUD, lifecycle
management (identified -> selected -> qualification_visit -> regulatory_submitted
-> activated -> enrolling -> closed), qualification visit tracking, regulatory
document management, readiness assessments, milestone tracking, and activation
metrics.

Endpoints:
    GET    /site-initiation/                                          - List sites
    GET    /site-initiation/metrics                                   - Get activation metrics
    GET    /site-initiation/documents/{doc_id}                        - Get regulatory document
    PUT    /site-initiation/documents/{doc_id}                        - Update regulatory document
    GET    /site-initiation/{site_id}                                 - Get single site
    POST   /site-initiation/                                          - Create site
    PUT    /site-initiation/{site_id}                                 - Update site
    DELETE /site-initiation/{site_id}                                 - Delete site
    POST   /site-initiation/{site_id}/select                          - Select site
    POST   /site-initiation/{site_id}/complete-qualification          - Complete qualification
    POST   /site-initiation/{site_id}/submit-regulatory               - Submit regulatory
    POST   /site-initiation/{site_id}/activate                        - Activate site
    POST   /site-initiation/{site_id}/begin-enrollment                - Begin enrollment
    POST   /site-initiation/{site_id}/close                           - Close site
    GET    /site-initiation/{site_id}/qualification-visits             - List qualification visits
    POST   /site-initiation/{site_id}/qualification-visits             - Add qualification visit
    GET    /site-initiation/{site_id}/regulatory-documents             - List regulatory documents
    POST   /site-initiation/{site_id}/regulatory-documents             - Add regulatory document
    GET    /site-initiation/{site_id}/readiness                        - Get readiness assessment
    PUT    /site-initiation/{site_id}/readiness                        - Update readiness assessment
    GET    /site-initiation/{site_id}/milestones                       - Get milestones
    PUT    /site-initiation/milestones/{milestone_id}                  - Update milestone
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.site_initiation import (
    DocumentStatus,
    DocumentType,
    MilestoneListResponse,
    MilestoneUpdate,
    QualificationVisit,
    QualificationVisitCreate,
    QualificationVisitListResponse,
    ReadinessAssessment,
    ReadinessUpdate,
    RegulatoryDocument,
    RegulatoryDocumentCreate,
    RegulatoryDocumentListResponse,
    RegulatoryDocumentUpdate,
    SiteActivationMetrics,
    SiteInitiation,
    SiteInitiationCreate,
    SiteInitiationListResponse,
    SiteInitiationUpdate,
    SiteMilestone,
    SiteStatus,
)
from app.services.site_initiation_service import get_site_initiation_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/site-initiation",
    tags=["Site Initiation & Activation"],
)


# ---------------------------------------------------------------------------
# Site CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=SiteInitiationListResponse,
    summary="List site initiation records",
    description="Retrieve sites with optional filtering by trial, status, and country.",
)
async def list_sites(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[SiteStatus] = Query(None, description="Filter by site status"),
    country: Optional[str] = Query(None, description="Filter by country code"),
) -> SiteInitiationListResponse:
    svc = get_site_initiation_service()
    items = svc.list_sites(trial_id=trial_id, status=status, country=country)
    return SiteInitiationListResponse(items=items, total=len(items))


@router.get(
    "/metrics",
    response_model=SiteActivationMetrics,
    summary="Get site activation metrics",
    description="Aggregated site activation metrics across all trials.",
)
async def get_activation_metrics() -> SiteActivationMetrics:
    svc = get_site_initiation_service()
    return svc.get_activation_metrics()


@router.get(
    "/documents/{doc_id}",
    response_model=RegulatoryDocument,
    summary="Get a regulatory document",
)
async def get_regulatory_document(doc_id: str) -> RegulatoryDocument:
    svc = get_site_initiation_service()
    doc = svc.get_regulatory_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Regulatory document '{doc_id}' not found")
    return doc


@router.put(
    "/documents/{doc_id}",
    response_model=RegulatoryDocument,
    summary="Update a regulatory document",
    description="Update regulatory document status, dates, notes, or version.",
)
async def update_regulatory_document(
    doc_id: str, payload: RegulatoryDocumentUpdate
) -> RegulatoryDocument:
    svc = get_site_initiation_service()
    updated = svc.update_regulatory_document(doc_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Regulatory document '{doc_id}' not found")
    return updated


@router.get(
    "/{site_id}",
    response_model=SiteInitiation,
    summary="Get a site initiation record",
)
async def get_site(site_id: str) -> SiteInitiation:
    svc = get_site_initiation_service()
    site = svc.get_site(site_id)
    if site is None:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")
    return site


@router.post(
    "/",
    response_model=SiteInitiation,
    status_code=201,
    summary="Create a site initiation record",
)
async def create_site(payload: SiteInitiationCreate) -> SiteInitiation:
    svc = get_site_initiation_service()
    return svc.create_site(payload)


@router.put(
    "/{site_id}",
    response_model=SiteInitiation,
    summary="Update a site initiation record",
)
async def update_site(
    site_id: str, payload: SiteInitiationUpdate
) -> SiteInitiation:
    svc = get_site_initiation_service()
    updated = svc.update_site(site_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")
    return updated


@router.delete(
    "/{site_id}",
    status_code=204,
    summary="Delete a site initiation record",
)
async def delete_site(site_id: str) -> None:
    svc = get_site_initiation_service()
    deleted = svc.delete_site(site_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")


# ---------------------------------------------------------------------------
# Lifecycle Transitions
# ---------------------------------------------------------------------------


@router.post(
    "/{site_id}/select",
    response_model=SiteInitiation,
    summary="Select site for trial",
    description="Transition site from identified to selected status.",
)
async def select_site(site_id: str) -> SiteInitiation:
    svc = get_site_initiation_service()
    try:
        result = svc.submit_for_qualification(site_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")
    return result


@router.post(
    "/{site_id}/complete-qualification",
    response_model=SiteInitiation,
    summary="Complete qualification visit",
    description="Transition site from selected to qualification_visit status.",
)
async def complete_qualification(site_id: str) -> SiteInitiation:
    svc = get_site_initiation_service()
    try:
        result = svc.complete_qualification(site_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")
    return result


@router.post(
    "/{site_id}/submit-regulatory",
    response_model=SiteInitiation,
    summary="Submit regulatory package",
    description="Transition site from qualification_visit to regulatory_submitted status.",
)
async def submit_regulatory(site_id: str) -> SiteInitiation:
    svc = get_site_initiation_service()
    try:
        result = svc.submit_regulatory(site_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")
    return result


@router.post(
    "/{site_id}/activate",
    response_model=SiteInitiation,
    summary="Activate site",
    description="Transition site from regulatory_submitted to activated status.",
)
async def activate_site(site_id: str) -> SiteInitiation:
    svc = get_site_initiation_service()
    try:
        result = svc.activate_site(site_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")
    return result


@router.post(
    "/{site_id}/begin-enrollment",
    response_model=SiteInitiation,
    summary="Begin enrollment",
    description="Transition site from activated to enrolling status.",
)
async def begin_enrollment(site_id: str) -> SiteInitiation:
    svc = get_site_initiation_service()
    try:
        result = svc.begin_enrollment(site_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")
    return result


@router.post(
    "/{site_id}/close",
    response_model=SiteInitiation,
    summary="Close site",
    description="Transition site to closed status (from activated or enrolling).",
)
async def close_site(site_id: str) -> SiteInitiation:
    svc = get_site_initiation_service()
    try:
        result = svc.close_site(site_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Qualification Visits
# ---------------------------------------------------------------------------


@router.get(
    "/{site_id}/qualification-visits",
    response_model=QualificationVisitListResponse,
    summary="List qualification visits for a site",
)
async def list_qualification_visits(site_id: str) -> QualificationVisitListResponse:
    svc = get_site_initiation_service()
    items = svc.list_qualification_visits(site_id)
    return QualificationVisitListResponse(items=items, total=len(items))


@router.post(
    "/{site_id}/qualification-visits",
    response_model=QualificationVisit,
    status_code=201,
    summary="Add a qualification visit",
)
async def add_qualification_visit(
    site_id: str, payload: QualificationVisitCreate
) -> QualificationVisit:
    svc = get_site_initiation_service()
    try:
        return svc.add_qualification_visit(site_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Regulatory Documents
# ---------------------------------------------------------------------------


@router.get(
    "/{site_id}/regulatory-documents",
    response_model=RegulatoryDocumentListResponse,
    summary="List regulatory documents for a site",
    description="Retrieve regulatory documents with optional filtering by type and status.",
)
async def list_regulatory_documents(
    site_id: str,
    doc_type: Optional[DocumentType] = Query(None, description="Filter by document type"),
    status: Optional[DocumentStatus] = Query(None, description="Filter by document status"),
) -> RegulatoryDocumentListResponse:
    svc = get_site_initiation_service()
    items = svc.list_regulatory_documents(site_id, doc_type=doc_type, status=status)
    return RegulatoryDocumentListResponse(items=items, total=len(items))


@router.post(
    "/{site_id}/regulatory-documents",
    response_model=RegulatoryDocument,
    status_code=201,
    summary="Add a regulatory document",
)
async def add_regulatory_document(
    site_id: str, payload: RegulatoryDocumentCreate
) -> RegulatoryDocument:
    svc = get_site_initiation_service()
    try:
        return svc.add_regulatory_document(site_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Readiness Assessment
# ---------------------------------------------------------------------------


@router.get(
    "/{site_id}/readiness",
    response_model=ReadinessAssessment,
    summary="Get readiness assessment",
    description="Retrieve the readiness assessment for a site.",
)
async def get_readiness_assessment(site_id: str) -> ReadinessAssessment:
    svc = get_site_initiation_service()
    assessment = svc.get_readiness_assessment(site_id)
    if assessment is None:
        raise HTTPException(
            status_code=404,
            detail=f"Readiness assessment for site '{site_id}' not found",
        )
    return assessment


@router.put(
    "/{site_id}/readiness",
    response_model=ReadinessAssessment,
    summary="Update readiness assessment",
    description="Create or update the readiness assessment for a site.",
)
async def update_readiness_assessment(
    site_id: str, payload: ReadinessUpdate
) -> ReadinessAssessment:
    svc = get_site_initiation_service()
    try:
        return svc.update_readiness(site_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Milestones
# ---------------------------------------------------------------------------


@router.get(
    "/{site_id}/milestones",
    response_model=MilestoneListResponse,
    summary="Get milestones for a site",
    description="Retrieve all activation milestones for a site, sorted by target date.",
)
async def get_milestones(site_id: str) -> MilestoneListResponse:
    svc = get_site_initiation_service()
    items = svc.get_milestones(site_id)
    return MilestoneListResponse(items=items, total=len(items))


@router.put(
    "/milestones/{milestone_id}",
    response_model=SiteMilestone,
    summary="Update a milestone",
    description="Update milestone target date, actual date, status, or notes.",
)
async def update_milestone(
    milestone_id: str, payload: MilestoneUpdate
) -> SiteMilestone:
    svc = get_site_initiation_service()
    updated = svc.update_milestone(milestone_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Milestone '{milestone_id}' not found",
        )
    return updated
