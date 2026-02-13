"""Investigator Oversight API endpoints (INV-OVS).

Provides comprehensive investigator oversight operations: investigator performance
reviews, site supervision records, GCP compliance checks, investigator
communications, and oversight metrics.

Endpoints:
    GET    /investigator-oversight/performances                        - List performances
    GET    /investigator-oversight/performances/{perf_id}              - Get single performance
    POST   /investigator-oversight/performances                        - Create performance
    PUT    /investigator-oversight/performances/{perf_id}              - Update performance
    DELETE /investigator-oversight/performances/{perf_id}              - Delete performance
    GET    /investigator-oversight/supervisions                        - List supervisions
    GET    /investigator-oversight/supervisions/{supervision_id}       - Get single supervision
    POST   /investigator-oversight/supervisions                        - Create supervision
    PUT    /investigator-oversight/supervisions/{supervision_id}       - Update supervision
    DELETE /investigator-oversight/supervisions/{supervision_id}       - Delete supervision
    GET    /investigator-oversight/compliance-checks                   - List compliance checks
    GET    /investigator-oversight/compliance-checks/{check_id}        - Get single check
    POST   /investigator-oversight/compliance-checks                   - Create check
    PUT    /investigator-oversight/compliance-checks/{check_id}        - Update check
    DELETE /investigator-oversight/compliance-checks/{check_id}        - Delete check
    GET    /investigator-oversight/communications                      - List communications
    GET    /investigator-oversight/communications/{comm_id}            - Get single communication
    POST   /investigator-oversight/communications                      - Create communication
    PUT    /investigator-oversight/communications/{comm_id}            - Update communication
    DELETE /investigator-oversight/communications/{comm_id}            - Delete communication
    GET    /investigator-oversight/metrics                             - Oversight metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.investigator_oversight import (
    CommunicationStatus,
    CommunicationType,
    ComplianceResult,
    GCPComplianceCheck,
    GCPComplianceCheckCreate,
    GCPComplianceCheckListResponse,
    GCPComplianceCheckUpdate,
    InvestigatorCommunication,
    InvestigatorCommunicationCreate,
    InvestigatorCommunicationListResponse,
    InvestigatorCommunicationUpdate,
    InvestigatorOversightMetrics,
    InvestigatorPerformance,
    InvestigatorPerformanceCreate,
    InvestigatorPerformanceListResponse,
    InvestigatorPerformanceUpdate,
    PerformanceRating,
    SiteSupervision,
    SiteSupervisionCreate,
    SiteSupervisionListResponse,
    SiteSupervisionUpdate,
    SupervisionType,
)
from app.services.investigator_oversight_service import get_investigator_oversight_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/investigator-oversight",
    tags=["Investigator Oversight"],
)


# ---------------------------------------------------------------------------
# Investigator Performances
# ---------------------------------------------------------------------------


@router.get(
    "/performances",
    response_model=InvestigatorPerformanceListResponse,
    summary="List investigator performances",
    description="Retrieve investigator performances with optional filtering by trial, rating, and site.",
)
async def list_investigator_performances(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    performance_rating: Optional[PerformanceRating] = Query(None, description="Filter by performance rating"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
) -> InvestigatorPerformanceListResponse:
    svc = get_investigator_oversight_service()
    items = svc.list_investigator_performances(
        trial_id=trial_id, performance_rating=performance_rating, site_id=site_id
    )
    return InvestigatorPerformanceListResponse(items=items, total=len(items))


@router.get(
    "/performances/{perf_id}",
    response_model=InvestigatorPerformance,
    summary="Get an investigator performance record",
)
async def get_investigator_performance(perf_id: str) -> InvestigatorPerformance:
    svc = get_investigator_oversight_service()
    record = svc.get_investigator_performance(perf_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Investigator performance '{perf_id}' not found")
    return record


@router.post(
    "/performances",
    response_model=InvestigatorPerformance,
    status_code=201,
    summary="Create an investigator performance record",
)
async def create_investigator_performance(
    payload: InvestigatorPerformanceCreate,
) -> InvestigatorPerformance:
    svc = get_investigator_oversight_service()
    return svc.create_investigator_performance(payload)


@router.put(
    "/performances/{perf_id}",
    response_model=InvestigatorPerformance,
    summary="Update an investigator performance record",
)
async def update_investigator_performance(
    perf_id: str, payload: InvestigatorPerformanceUpdate
) -> InvestigatorPerformance:
    svc = get_investigator_oversight_service()
    updated = svc.update_investigator_performance(perf_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Investigator performance '{perf_id}' not found")
    return updated


@router.delete(
    "/performances/{perf_id}",
    status_code=204,
    summary="Delete an investigator performance record",
)
async def delete_investigator_performance(perf_id: str) -> None:
    svc = get_investigator_oversight_service()
    deleted = svc.delete_investigator_performance(perf_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Investigator performance '{perf_id}' not found")


# ---------------------------------------------------------------------------
# Site Supervisions
# ---------------------------------------------------------------------------


@router.get(
    "/supervisions",
    response_model=SiteSupervisionListResponse,
    summary="List site supervisions",
    description="Retrieve site supervisions with optional filtering by trial, type, and site.",
)
async def list_site_supervisions(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    supervision_type: Optional[SupervisionType] = Query(None, description="Filter by supervision type"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
) -> SiteSupervisionListResponse:
    svc = get_investigator_oversight_service()
    items = svc.list_site_supervisions(
        trial_id=trial_id, supervision_type=supervision_type, site_id=site_id
    )
    return SiteSupervisionListResponse(items=items, total=len(items))


@router.get(
    "/supervisions/{supervision_id}",
    response_model=SiteSupervision,
    summary="Get a site supervision record",
)
async def get_site_supervision(supervision_id: str) -> SiteSupervision:
    svc = get_investigator_oversight_service()
    record = svc.get_site_supervision(supervision_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Site supervision '{supervision_id}' not found"
        )
    return record


@router.post(
    "/supervisions",
    response_model=SiteSupervision,
    status_code=201,
    summary="Create a site supervision record",
)
async def create_site_supervision(payload: SiteSupervisionCreate) -> SiteSupervision:
    svc = get_investigator_oversight_service()
    return svc.create_site_supervision(payload)


@router.put(
    "/supervisions/{supervision_id}",
    response_model=SiteSupervision,
    summary="Update a site supervision record",
)
async def update_site_supervision(
    supervision_id: str, payload: SiteSupervisionUpdate
) -> SiteSupervision:
    svc = get_investigator_oversight_service()
    updated = svc.update_site_supervision(supervision_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Site supervision '{supervision_id}' not found"
        )
    return updated


@router.delete(
    "/supervisions/{supervision_id}",
    status_code=204,
    summary="Delete a site supervision record",
)
async def delete_site_supervision(supervision_id: str) -> None:
    svc = get_investigator_oversight_service()
    deleted = svc.delete_site_supervision(supervision_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Site supervision '{supervision_id}' not found"
        )


# ---------------------------------------------------------------------------
# GCP Compliance Checks
# ---------------------------------------------------------------------------


@router.get(
    "/compliance-checks",
    response_model=GCPComplianceCheckListResponse,
    summary="List GCP compliance checks",
    description="Retrieve GCP compliance checks with optional filtering by trial, result, and site.",
)
async def list_gcp_compliance_checks(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    compliance_result: Optional[ComplianceResult] = Query(None, description="Filter by compliance result"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
) -> GCPComplianceCheckListResponse:
    svc = get_investigator_oversight_service()
    items = svc.list_gcp_compliance_checks(
        trial_id=trial_id, compliance_result=compliance_result, site_id=site_id
    )
    return GCPComplianceCheckListResponse(items=items, total=len(items))


@router.get(
    "/compliance-checks/{check_id}",
    response_model=GCPComplianceCheck,
    summary="Get a GCP compliance check",
)
async def get_gcp_compliance_check(check_id: str) -> GCPComplianceCheck:
    svc = get_investigator_oversight_service()
    record = svc.get_gcp_compliance_check(check_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"GCP compliance check '{check_id}' not found"
        )
    return record


@router.post(
    "/compliance-checks",
    response_model=GCPComplianceCheck,
    status_code=201,
    summary="Create a GCP compliance check",
)
async def create_gcp_compliance_check(
    payload: GCPComplianceCheckCreate,
) -> GCPComplianceCheck:
    svc = get_investigator_oversight_service()
    return svc.create_gcp_compliance_check(payload)


@router.put(
    "/compliance-checks/{check_id}",
    response_model=GCPComplianceCheck,
    summary="Update a GCP compliance check",
)
async def update_gcp_compliance_check(
    check_id: str, payload: GCPComplianceCheckUpdate
) -> GCPComplianceCheck:
    svc = get_investigator_oversight_service()
    updated = svc.update_gcp_compliance_check(check_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"GCP compliance check '{check_id}' not found"
        )
    return updated


@router.delete(
    "/compliance-checks/{check_id}",
    status_code=204,
    summary="Delete a GCP compliance check",
)
async def delete_gcp_compliance_check(check_id: str) -> None:
    svc = get_investigator_oversight_service()
    deleted = svc.delete_gcp_compliance_check(check_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"GCP compliance check '{check_id}' not found"
        )


# ---------------------------------------------------------------------------
# Investigator Communications
# ---------------------------------------------------------------------------


@router.get(
    "/communications",
    response_model=InvestigatorCommunicationListResponse,
    summary="List investigator communications",
    description="Retrieve investigator communications with optional filtering by trial, type, and status.",
)
async def list_investigator_communications(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    communication_type: Optional[CommunicationType] = Query(None, description="Filter by communication type"),
    communication_status: Optional[CommunicationStatus] = Query(None, description="Filter by communication status"),
) -> InvestigatorCommunicationListResponse:
    svc = get_investigator_oversight_service()
    items = svc.list_investigator_communications(
        trial_id=trial_id,
        communication_type=communication_type,
        communication_status=communication_status,
    )
    return InvestigatorCommunicationListResponse(items=items, total=len(items))


@router.get(
    "/communications/{comm_id}",
    response_model=InvestigatorCommunication,
    summary="Get an investigator communication",
)
async def get_investigator_communication(comm_id: str) -> InvestigatorCommunication:
    svc = get_investigator_oversight_service()
    record = svc.get_investigator_communication(comm_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Investigator communication '{comm_id}' not found"
        )
    return record


@router.post(
    "/communications",
    response_model=InvestigatorCommunication,
    status_code=201,
    summary="Create an investigator communication",
)
async def create_investigator_communication(
    payload: InvestigatorCommunicationCreate,
) -> InvestigatorCommunication:
    svc = get_investigator_oversight_service()
    return svc.create_investigator_communication(payload)


@router.put(
    "/communications/{comm_id}",
    response_model=InvestigatorCommunication,
    summary="Update an investigator communication",
)
async def update_investigator_communication(
    comm_id: str, payload: InvestigatorCommunicationUpdate
) -> InvestigatorCommunication:
    svc = get_investigator_oversight_service()
    updated = svc.update_investigator_communication(comm_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Investigator communication '{comm_id}' not found"
        )
    return updated


@router.delete(
    "/communications/{comm_id}",
    status_code=204,
    summary="Delete an investigator communication",
)
async def delete_investigator_communication(comm_id: str) -> None:
    svc = get_investigator_oversight_service()
    deleted = svc.delete_investigator_communication(comm_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Investigator communication '{comm_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=InvestigatorOversightMetrics,
    summary="Get investigator oversight metrics",
    description="Aggregated metrics across all investigator oversight operations.",
)
async def get_metrics() -> InvestigatorOversightMetrics:
    svc = get_investigator_oversight_service()
    return svc.get_metrics()
