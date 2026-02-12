"""Regulatory Inspection Management API endpoints (REG-INSP).

Provides comprehensive inspection operations: inspection scheduling, finding tracking,
CAPA response preparation, mock inspection management, inspection readiness assessment,
commitment tracking, and regulatory inspection operational metrics.

Endpoints:
    GET    /regulatory-inspection/inspections                          - List inspections
    GET    /regulatory-inspection/inspections/{inspection_id}          - Get single inspection
    POST   /regulatory-inspection/inspections                          - Create inspection
    PUT    /regulatory-inspection/inspections/{inspection_id}          - Update inspection
    DELETE /regulatory-inspection/inspections/{inspection_id}          - Delete inspection
    GET    /regulatory-inspection/findings                             - List findings
    GET    /regulatory-inspection/findings/{finding_id}                - Get single finding
    POST   /regulatory-inspection/findings                             - Create finding
    PUT    /regulatory-inspection/findings/{finding_id}                - Update finding
    DELETE /regulatory-inspection/findings/{finding_id}                - Delete finding
    GET    /regulatory-inspection/mock-inspections                     - List mock inspections
    GET    /regulatory-inspection/mock-inspections/{mock_id}           - Get single mock inspection
    POST   /regulatory-inspection/mock-inspections                     - Create mock inspection
    PUT    /regulatory-inspection/mock-inspections/{mock_id}           - Update mock inspection
    DELETE /regulatory-inspection/mock-inspections/{mock_id}           - Delete mock inspection
    GET    /regulatory-inspection/readiness-assessments                - List readiness assessments
    GET    /regulatory-inspection/readiness-assessments/{assessment_id} - Get single readiness assessment
    POST   /regulatory-inspection/readiness-assessments                - Create readiness assessment
    PUT    /regulatory-inspection/readiness-assessments/{assessment_id} - Update readiness assessment
    DELETE /regulatory-inspection/readiness-assessments/{assessment_id} - Delete readiness assessment
    GET    /regulatory-inspection/commitments                          - List commitments
    GET    /regulatory-inspection/commitments/{commitment_id}          - Get single commitment
    POST   /regulatory-inspection/commitments                          - Create commitment
    PUT    /regulatory-inspection/commitments/{commitment_id}          - Update commitment
    DELETE /regulatory-inspection/commitments/{commitment_id}          - Delete commitment
    GET    /regulatory-inspection/metrics                              - Inspection metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.regulatory_inspection import (
    FindingClassification,
    FindingSeverity,
    Inspection,
    InspectionAuthority,
    InspectionCommitment,
    InspectionCommitmentCreate,
    InspectionCommitmentListResponse,
    InspectionCommitmentUpdate,
    InspectionCreate,
    InspectionFinding,
    InspectionFindingCreate,
    InspectionFindingListResponse,
    InspectionFindingUpdate,
    InspectionListResponse,
    InspectionStatus,
    InspectionType,
    InspectionUpdate,
    MockInspection,
    MockInspectionCreate,
    MockInspectionListResponse,
    MockInspectionUpdate,
    ReadinessAssessment,
    ReadinessAssessmentCreate,
    ReadinessAssessmentListResponse,
    ReadinessAssessmentUpdate,
    RegulatoryInspectionMetrics,
)
from app.services.regulatory_inspection_service import get_regulatory_inspection_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/regulatory-inspection",
    tags=["Regulatory Inspection Management"],
)


# ---------------------------------------------------------------------------
# Inspection CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/inspections",
    response_model=InspectionListResponse,
    summary="List inspections",
    description="Retrieve inspections with optional filtering by trial, status, authority, and type.",
)
async def list_inspections(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[InspectionStatus] = Query(None, description="Filter by status"),
    authority: Optional[InspectionAuthority] = Query(None, description="Filter by authority"),
    inspection_type: Optional[InspectionType] = Query(None, description="Filter by inspection type"),
) -> InspectionListResponse:
    svc = get_regulatory_inspection_service()
    items = svc.list_inspections(
        trial_id=trial_id,
        status=status,
        authority=authority,
        inspection_type=inspection_type,
    )
    return InspectionListResponse(items=items, total=len(items))


@router.get(
    "/inspections/{inspection_id}",
    response_model=Inspection,
    summary="Get an inspection",
)
async def get_inspection(inspection_id: str) -> Inspection:
    svc = get_regulatory_inspection_service()
    inspection = svc.get_inspection(inspection_id)
    if inspection is None:
        raise HTTPException(status_code=404, detail=f"Inspection '{inspection_id}' not found")
    return inspection


@router.post(
    "/inspections",
    response_model=Inspection,
    status_code=201,
    summary="Create an inspection",
)
async def create_inspection(payload: InspectionCreate) -> Inspection:
    svc = get_regulatory_inspection_service()
    return svc.create_inspection(payload)


@router.put(
    "/inspections/{inspection_id}",
    response_model=Inspection,
    summary="Update an inspection",
)
async def update_inspection(
    inspection_id: str, payload: InspectionUpdate
) -> Inspection:
    svc = get_regulatory_inspection_service()
    updated = svc.update_inspection(inspection_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Inspection '{inspection_id}' not found")
    return updated


@router.delete(
    "/inspections/{inspection_id}",
    status_code=204,
    summary="Delete an inspection",
)
async def delete_inspection(inspection_id: str) -> None:
    svc = get_regulatory_inspection_service()
    deleted = svc.delete_inspection(inspection_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Inspection '{inspection_id}' not found")


# ---------------------------------------------------------------------------
# Finding CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/findings",
    response_model=InspectionFindingListResponse,
    summary="List inspection findings",
    description="Retrieve findings with optional filtering by inspection, severity, and classification.",
)
async def list_findings(
    inspection_id: Optional[str] = Query(None, description="Filter by inspection ID"),
    severity: Optional[FindingSeverity] = Query(None, description="Filter by severity"),
    classification: Optional[FindingClassification] = Query(None, description="Filter by classification"),
) -> InspectionFindingListResponse:
    svc = get_regulatory_inspection_service()
    items = svc.list_findings(
        inspection_id=inspection_id,
        severity=severity,
        classification=classification,
    )
    return InspectionFindingListResponse(items=items, total=len(items))


@router.get(
    "/findings/{finding_id}",
    response_model=InspectionFinding,
    summary="Get an inspection finding",
)
async def get_finding(finding_id: str) -> InspectionFinding:
    svc = get_regulatory_inspection_service()
    finding = svc.get_finding(finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail=f"Finding '{finding_id}' not found")
    return finding


@router.post(
    "/findings",
    response_model=InspectionFinding,
    status_code=201,
    summary="Create an inspection finding",
)
async def create_finding(payload: InspectionFindingCreate) -> InspectionFinding:
    svc = get_regulatory_inspection_service()
    return svc.create_finding(payload)


@router.put(
    "/findings/{finding_id}",
    response_model=InspectionFinding,
    summary="Update an inspection finding",
)
async def update_finding(
    finding_id: str, payload: InspectionFindingUpdate
) -> InspectionFinding:
    svc = get_regulatory_inspection_service()
    updated = svc.update_finding(finding_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Finding '{finding_id}' not found")
    return updated


@router.delete(
    "/findings/{finding_id}",
    status_code=204,
    summary="Delete an inspection finding",
)
async def delete_finding(finding_id: str) -> None:
    svc = get_regulatory_inspection_service()
    deleted = svc.delete_finding(finding_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Finding '{finding_id}' not found")


# ---------------------------------------------------------------------------
# Mock Inspection CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/mock-inspections",
    response_model=MockInspectionListResponse,
    summary="List mock inspections",
    description="Retrieve mock inspections with optional filtering by trial and status.",
)
async def list_mock_inspections(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
) -> MockInspectionListResponse:
    svc = get_regulatory_inspection_service()
    items = svc.list_mock_inspections(trial_id=trial_id, status=status)
    return MockInspectionListResponse(items=items, total=len(items))


@router.get(
    "/mock-inspections/{mock_id}",
    response_model=MockInspection,
    summary="Get a mock inspection",
)
async def get_mock_inspection(mock_id: str) -> MockInspection:
    svc = get_regulatory_inspection_service()
    mock = svc.get_mock_inspection(mock_id)
    if mock is None:
        raise HTTPException(status_code=404, detail=f"Mock inspection '{mock_id}' not found")
    return mock


@router.post(
    "/mock-inspections",
    response_model=MockInspection,
    status_code=201,
    summary="Create a mock inspection",
)
async def create_mock_inspection(payload: MockInspectionCreate) -> MockInspection:
    svc = get_regulatory_inspection_service()
    return svc.create_mock_inspection(payload)


@router.put(
    "/mock-inspections/{mock_id}",
    response_model=MockInspection,
    summary="Update a mock inspection",
)
async def update_mock_inspection(
    mock_id: str, payload: MockInspectionUpdate
) -> MockInspection:
    svc = get_regulatory_inspection_service()
    updated = svc.update_mock_inspection(mock_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Mock inspection '{mock_id}' not found")
    return updated


@router.delete(
    "/mock-inspections/{mock_id}",
    status_code=204,
    summary="Delete a mock inspection",
)
async def delete_mock_inspection(mock_id: str) -> None:
    svc = get_regulatory_inspection_service()
    deleted = svc.delete_mock_inspection(mock_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Mock inspection '{mock_id}' not found")


# ---------------------------------------------------------------------------
# Readiness Assessment CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/readiness-assessments",
    response_model=ReadinessAssessmentListResponse,
    summary="List readiness assessments",
    description="Retrieve readiness assessments with optional filtering by trial and authority.",
)
async def list_readiness_assessments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    target_authority: Optional[InspectionAuthority] = Query(None, description="Filter by target authority"),
) -> ReadinessAssessmentListResponse:
    svc = get_regulatory_inspection_service()
    items = svc.list_readiness_assessments(
        trial_id=trial_id,
        target_authority=target_authority,
    )
    return ReadinessAssessmentListResponse(items=items, total=len(items))


@router.get(
    "/readiness-assessments/{assessment_id}",
    response_model=ReadinessAssessment,
    summary="Get a readiness assessment",
)
async def get_readiness_assessment(assessment_id: str) -> ReadinessAssessment:
    svc = get_regulatory_inspection_service()
    assessment = svc.get_readiness_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail=f"Readiness assessment '{assessment_id}' not found")
    return assessment


@router.post(
    "/readiness-assessments",
    response_model=ReadinessAssessment,
    status_code=201,
    summary="Create a readiness assessment",
)
async def create_readiness_assessment(payload: ReadinessAssessmentCreate) -> ReadinessAssessment:
    svc = get_regulatory_inspection_service()
    return svc.create_readiness_assessment(payload)


@router.put(
    "/readiness-assessments/{assessment_id}",
    response_model=ReadinessAssessment,
    summary="Update a readiness assessment",
)
async def update_readiness_assessment(
    assessment_id: str, payload: ReadinessAssessmentUpdate
) -> ReadinessAssessment:
    svc = get_regulatory_inspection_service()
    updated = svc.update_readiness_assessment(assessment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Readiness assessment '{assessment_id}' not found")
    return updated


@router.delete(
    "/readiness-assessments/{assessment_id}",
    status_code=204,
    summary="Delete a readiness assessment",
)
async def delete_readiness_assessment(assessment_id: str) -> None:
    svc = get_regulatory_inspection_service()
    deleted = svc.delete_readiness_assessment(assessment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Readiness assessment '{assessment_id}' not found")


# ---------------------------------------------------------------------------
# Commitment CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/commitments",
    response_model=InspectionCommitmentListResponse,
    summary="List inspection commitments",
    description="Retrieve commitments with optional filtering by inspection and status.",
)
async def list_commitments(
    inspection_id: Optional[str] = Query(None, description="Filter by inspection ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
) -> InspectionCommitmentListResponse:
    svc = get_regulatory_inspection_service()
    items = svc.list_commitments(inspection_id=inspection_id, status=status)
    return InspectionCommitmentListResponse(items=items, total=len(items))


@router.get(
    "/commitments/{commitment_id}",
    response_model=InspectionCommitment,
    summary="Get an inspection commitment",
)
async def get_commitment(commitment_id: str) -> InspectionCommitment:
    svc = get_regulatory_inspection_service()
    commitment = svc.get_commitment(commitment_id)
    if commitment is None:
        raise HTTPException(status_code=404, detail=f"Commitment '{commitment_id}' not found")
    return commitment


@router.post(
    "/commitments",
    response_model=InspectionCommitment,
    status_code=201,
    summary="Create an inspection commitment",
)
async def create_commitment(payload: InspectionCommitmentCreate) -> InspectionCommitment:
    svc = get_regulatory_inspection_service()
    return svc.create_commitment(payload)


@router.put(
    "/commitments/{commitment_id}",
    response_model=InspectionCommitment,
    summary="Update an inspection commitment",
)
async def update_commitment(
    commitment_id: str, payload: InspectionCommitmentUpdate
) -> InspectionCommitment:
    svc = get_regulatory_inspection_service()
    updated = svc.update_commitment(commitment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Commitment '{commitment_id}' not found")
    return updated


@router.delete(
    "/commitments/{commitment_id}",
    status_code=204,
    summary="Delete an inspection commitment",
)
async def delete_commitment(commitment_id: str) -> None:
    svc = get_regulatory_inspection_service()
    deleted = svc.delete_commitment(commitment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Commitment '{commitment_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=RegulatoryInspectionMetrics,
    summary="Get regulatory inspection metrics",
    description="Aggregated regulatory inspection metrics including inspection counts by type/authority/status, "
                "finding severity breakdown, readiness scores, and commitment tracking.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> RegulatoryInspectionMetrics:
    svc = get_regulatory_inspection_service()
    return svc.get_metrics(trial_id=trial_id)
