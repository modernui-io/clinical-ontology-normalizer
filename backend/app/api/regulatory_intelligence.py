"""Regulatory Intelligence API endpoints (REG-INTEL).

Provides comprehensive regulatory intelligence operations: intelligence item tracking,
submission lifecycle management, compliance gap analysis, authority communication
tracking, and regulatory metrics dashboard.

Endpoints:
    GET    /regulatory-intelligence/items                              - List intelligence items
    GET    /regulatory-intelligence/items/{item_id}                    - Get single intelligence item
    POST   /regulatory-intelligence/items                              - Create intelligence item
    PUT    /regulatory-intelligence/items/{item_id}                    - Update intelligence item
    DELETE /regulatory-intelligence/items/{item_id}                    - Delete intelligence item
    GET    /regulatory-intelligence/submissions                        - List submissions
    GET    /regulatory-intelligence/submissions/{submission_id}        - Get single submission
    POST   /regulatory-intelligence/submissions                        - Create submission
    PUT    /regulatory-intelligence/submissions/{submission_id}        - Update submission
    DELETE /regulatory-intelligence/submissions/{submission_id}        - Delete submission
    GET    /regulatory-intelligence/gaps                               - List compliance gaps
    GET    /regulatory-intelligence/gaps/{gap_id}                      - Get single compliance gap
    POST   /regulatory-intelligence/gaps                               - Create compliance gap
    PUT    /regulatory-intelligence/gaps/{gap_id}                      - Update compliance gap
    DELETE /regulatory-intelligence/gaps/{gap_id}                      - Delete compliance gap
    GET    /regulatory-intelligence/communications                     - List communications
    GET    /regulatory-intelligence/communications/{comm_id}           - Get single communication
    POST   /regulatory-intelligence/communications                     - Create communication
    PUT    /regulatory-intelligence/communications/{comm_id}           - Update communication
    DELETE /regulatory-intelligence/communications/{comm_id}           - Delete communication
    GET    /regulatory-intelligence/metrics                            - Regulatory intelligence metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.regulatory_intelligence import (
    AuthorityCommunication,
    AuthorityCommunicationCreate,
    AuthorityCommunicationListResponse,
    AuthorityCommunicationUpdate,
    ComplianceGap,
    ComplianceGapCreate,
    ComplianceGapListResponse,
    ComplianceGapUpdate,
    GapSeverity,
    GapStatus,
    ImpactLevel,
    IntelligenceItemCreate,
    IntelligenceItemListResponse,
    IntelligenceItemUpdate,
    IntelligenceStatus,
    IntelligenceType,
    RegulatoryAuthority,
    RegulatoryIntelligenceItem,
    RegulatoryIntelligenceMetrics,
    RegulatorySubmissionTracker,
    SubmissionStatus,
    SubmissionTrackerCreate,
    SubmissionTrackerListResponse,
    SubmissionTrackerUpdate,
)
from app.services.regulatory_intelligence_service import get_regulatory_intelligence_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/regulatory-intelligence",
    tags=["Regulatory Intelligence"],
)


# ---------------------------------------------------------------------------
# Intelligence Item Management
# ---------------------------------------------------------------------------


@router.get(
    "/items",
    response_model=IntelligenceItemListResponse,
    summary="List regulatory intelligence items",
    description="Retrieve intelligence items with optional filtering by authority, type, status, and impact.",
)
async def list_intelligence_items(
    authority: Optional[RegulatoryAuthority] = Query(None, description="Filter by authority"),
    intelligence_type: Optional[IntelligenceType] = Query(None, description="Filter by type"),
    status: Optional[IntelligenceStatus] = Query(None, description="Filter by status"),
    impact_level: Optional[ImpactLevel] = Query(None, description="Filter by impact level"),
) -> IntelligenceItemListResponse:
    svc = get_regulatory_intelligence_service()
    items = svc.list_intelligence_items(
        authority=authority,
        intelligence_type=intelligence_type,
        status=status,
        impact_level=impact_level,
    )
    return IntelligenceItemListResponse(items=items, total=len(items))


@router.get(
    "/items/{item_id}",
    response_model=RegulatoryIntelligenceItem,
    summary="Get a regulatory intelligence item",
)
async def get_intelligence_item(item_id: str) -> RegulatoryIntelligenceItem:
    svc = get_regulatory_intelligence_service()
    item = svc.get_intelligence_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Intelligence item '{item_id}' not found")
    return item


@router.post(
    "/items",
    response_model=RegulatoryIntelligenceItem,
    status_code=201,
    summary="Create a regulatory intelligence item",
)
async def create_intelligence_item(payload: IntelligenceItemCreate) -> RegulatoryIntelligenceItem:
    svc = get_regulatory_intelligence_service()
    return svc.create_intelligence_item(payload)


@router.put(
    "/items/{item_id}",
    response_model=RegulatoryIntelligenceItem,
    summary="Update a regulatory intelligence item",
)
async def update_intelligence_item(
    item_id: str, payload: IntelligenceItemUpdate
) -> RegulatoryIntelligenceItem:
    svc = get_regulatory_intelligence_service()
    updated = svc.update_intelligence_item(item_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Intelligence item '{item_id}' not found")
    return updated


@router.delete(
    "/items/{item_id}",
    status_code=204,
    summary="Delete a regulatory intelligence item",
)
async def delete_intelligence_item(item_id: str) -> None:
    svc = get_regulatory_intelligence_service()
    deleted = svc.delete_intelligence_item(item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Intelligence item '{item_id}' not found")


# ---------------------------------------------------------------------------
# Submission Tracker Management
# ---------------------------------------------------------------------------


@router.get(
    "/submissions",
    response_model=SubmissionTrackerListResponse,
    summary="List regulatory submissions",
    description="Retrieve submission trackers with optional filtering by trial, authority, and status.",
)
async def list_submissions(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    authority: Optional[RegulatoryAuthority] = Query(None, description="Filter by authority"),
    status: Optional[SubmissionStatus] = Query(None, description="Filter by status"),
) -> SubmissionTrackerListResponse:
    svc = get_regulatory_intelligence_service()
    items = svc.list_submissions(trial_id=trial_id, authority=authority, status=status)
    return SubmissionTrackerListResponse(items=items, total=len(items))


@router.get(
    "/submissions/{submission_id}",
    response_model=RegulatorySubmissionTracker,
    summary="Get a regulatory submission",
)
async def get_submission(submission_id: str) -> RegulatorySubmissionTracker:
    svc = get_regulatory_intelligence_service()
    submission = svc.get_submission(submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail=f"Submission '{submission_id}' not found")
    return submission


@router.post(
    "/submissions",
    response_model=RegulatorySubmissionTracker,
    status_code=201,
    summary="Create a regulatory submission tracker",
)
async def create_submission(payload: SubmissionTrackerCreate) -> RegulatorySubmissionTracker:
    svc = get_regulatory_intelligence_service()
    return svc.create_submission(payload)


@router.put(
    "/submissions/{submission_id}",
    response_model=RegulatorySubmissionTracker,
    summary="Update a regulatory submission",
)
async def update_submission(
    submission_id: str, payload: SubmissionTrackerUpdate
) -> RegulatorySubmissionTracker:
    svc = get_regulatory_intelligence_service()
    updated = svc.update_submission(submission_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Submission '{submission_id}' not found")
    return updated


@router.delete(
    "/submissions/{submission_id}",
    status_code=204,
    summary="Delete a regulatory submission",
)
async def delete_submission(submission_id: str) -> None:
    svc = get_regulatory_intelligence_service()
    deleted = svc.delete_submission(submission_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Submission '{submission_id}' not found")


# ---------------------------------------------------------------------------
# Compliance Gap Management
# ---------------------------------------------------------------------------


@router.get(
    "/gaps",
    response_model=ComplianceGapListResponse,
    summary="List compliance gaps",
    description="Retrieve compliance gaps with optional filtering by trial, authority, severity, and status.",
)
async def list_compliance_gaps(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    authority: Optional[RegulatoryAuthority] = Query(None, description="Filter by authority"),
    severity: Optional[GapSeverity] = Query(None, description="Filter by severity"),
    status: Optional[GapStatus] = Query(None, description="Filter by status"),
) -> ComplianceGapListResponse:
    svc = get_regulatory_intelligence_service()
    items = svc.list_compliance_gaps(
        trial_id=trial_id, authority=authority, severity=severity, status=status,
    )
    return ComplianceGapListResponse(items=items, total=len(items))


@router.get(
    "/gaps/{gap_id}",
    response_model=ComplianceGap,
    summary="Get a compliance gap",
)
async def get_compliance_gap(gap_id: str) -> ComplianceGap:
    svc = get_regulatory_intelligence_service()
    gap = svc.get_compliance_gap(gap_id)
    if gap is None:
        raise HTTPException(status_code=404, detail=f"Compliance gap '{gap_id}' not found")
    return gap


@router.post(
    "/gaps",
    response_model=ComplianceGap,
    status_code=201,
    summary="Create a compliance gap",
)
async def create_compliance_gap(payload: ComplianceGapCreate) -> ComplianceGap:
    svc = get_regulatory_intelligence_service()
    return svc.create_compliance_gap(payload)


@router.put(
    "/gaps/{gap_id}",
    response_model=ComplianceGap,
    summary="Update a compliance gap",
)
async def update_compliance_gap(
    gap_id: str, payload: ComplianceGapUpdate
) -> ComplianceGap:
    svc = get_regulatory_intelligence_service()
    updated = svc.update_compliance_gap(gap_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Compliance gap '{gap_id}' not found")
    return updated


@router.delete(
    "/gaps/{gap_id}",
    status_code=204,
    summary="Delete a compliance gap",
)
async def delete_compliance_gap(gap_id: str) -> None:
    svc = get_regulatory_intelligence_service()
    deleted = svc.delete_compliance_gap(gap_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Compliance gap '{gap_id}' not found")


# ---------------------------------------------------------------------------
# Authority Communication Management
# ---------------------------------------------------------------------------


@router.get(
    "/communications",
    response_model=AuthorityCommunicationListResponse,
    summary="List authority communications",
    description="Retrieve authority communications with optional filtering by trial, authority, and submission.",
)
async def list_communications(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    authority: Optional[RegulatoryAuthority] = Query(None, description="Filter by authority"),
    submission_id: Optional[str] = Query(None, description="Filter by submission ID"),
) -> AuthorityCommunicationListResponse:
    svc = get_regulatory_intelligence_service()
    items = svc.list_communications(
        trial_id=trial_id, authority=authority, submission_id=submission_id,
    )
    return AuthorityCommunicationListResponse(items=items, total=len(items))


@router.get(
    "/communications/{comm_id}",
    response_model=AuthorityCommunication,
    summary="Get an authority communication",
)
async def get_communication(comm_id: str) -> AuthorityCommunication:
    svc = get_regulatory_intelligence_service()
    comm = svc.get_communication(comm_id)
    if comm is None:
        raise HTTPException(status_code=404, detail=f"Communication '{comm_id}' not found")
    return comm


@router.post(
    "/communications",
    response_model=AuthorityCommunication,
    status_code=201,
    summary="Create an authority communication",
)
async def create_communication(payload: AuthorityCommunicationCreate) -> AuthorityCommunication:
    svc = get_regulatory_intelligence_service()
    return svc.create_communication(payload)


@router.put(
    "/communications/{comm_id}",
    response_model=AuthorityCommunication,
    summary="Update an authority communication",
)
async def update_communication(
    comm_id: str, payload: AuthorityCommunicationUpdate
) -> AuthorityCommunication:
    svc = get_regulatory_intelligence_service()
    updated = svc.update_communication(comm_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Communication '{comm_id}' not found")
    return updated


@router.delete(
    "/communications/{comm_id}",
    status_code=204,
    summary="Delete an authority communication",
)
async def delete_communication(comm_id: str) -> None:
    svc = get_regulatory_intelligence_service()
    deleted = svc.delete_communication(comm_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Communication '{comm_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=RegulatoryIntelligenceMetrics,
    summary="Get regulatory intelligence metrics",
    description="Aggregated regulatory intelligence metrics including items by authority/type/status, "
                "submission tracking, compliance gap analysis, and communication status.",
)
async def get_metrics() -> RegulatoryIntelligenceMetrics:
    svc = get_regulatory_intelligence_service()
    return svc.get_metrics()
