"""Protocol Compliance Management API endpoints (PROT-COMP).

Provides protocol compliance operations: GCP compliance assessments,
compliance finding management, training compliance tracking, protocol
adherence records, corrective action management, and compliance metrics.

Endpoints:
    GET    /protocol-compliance/assessments                          - List assessments
    GET    /protocol-compliance/assessments/{assessment_id}          - Get single assessment
    POST   /protocol-compliance/assessments                          - Create assessment
    PUT    /protocol-compliance/assessments/{assessment_id}          - Update assessment
    DELETE /protocol-compliance/assessments/{assessment_id}          - Delete assessment
    GET    /protocol-compliance/findings                             - List findings
    GET    /protocol-compliance/findings/{finding_id}                - Get single finding
    POST   /protocol-compliance/findings                             - Create finding
    PUT    /protocol-compliance/findings/{finding_id}                - Update finding
    DELETE /protocol-compliance/findings/{finding_id}                - Delete finding
    GET    /protocol-compliance/training                             - List training records
    GET    /protocol-compliance/training/{training_id}               - Get single training record
    POST   /protocol-compliance/training                             - Create training record
    PUT    /protocol-compliance/training/{training_id}               - Update training record
    DELETE /protocol-compliance/training/{training_id}               - Delete training record
    GET    /protocol-compliance/adherence                            - List adherence records
    GET    /protocol-compliance/adherence/{adherence_id}             - Get single adherence record
    POST   /protocol-compliance/adherence                            - Create adherence record
    PUT    /protocol-compliance/adherence/{adherence_id}             - Update adherence record
    DELETE /protocol-compliance/adherence/{adherence_id}             - Delete adherence record
    GET    /protocol-compliance/corrective-actions                   - List corrective actions
    GET    /protocol-compliance/corrective-actions/{action_id}       - Get single corrective action
    POST   /protocol-compliance/corrective-actions                   - Create corrective action
    PUT    /protocol-compliance/corrective-actions/{action_id}       - Update corrective action
    DELETE /protocol-compliance/corrective-actions/{action_id}       - Delete corrective action
    GET    /protocol-compliance/metrics                              - Compliance metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.protocol_compliance import (
    ComplianceArea,
    ComplianceAssessment,
    ComplianceAssessmentCreate,
    ComplianceAssessmentListResponse,
    ComplianceAssessmentUpdate,
    ComplianceFinding,
    ComplianceFindingCreate,
    ComplianceFindingListResponse,
    ComplianceFindingUpdate,
    ComplianceRating,
    CorrectiveAction,
    CorrectiveActionCreate,
    CorrectiveActionListResponse,
    CorrectiveActionUpdate,
    FindingSeverity,
    FindingStatus,
    ProtocolAdherence,
    ProtocolAdherenceCreate,
    ProtocolAdherenceListResponse,
    ProtocolAdherenceUpdate,
    ProtocolComplianceMetrics,
    TrainingCompliance,
    TrainingComplianceCreate,
    TrainingComplianceListResponse,
    TrainingComplianceUpdate,
    TrainingStatus,
)
from app.services.protocol_compliance_service import get_protocol_compliance_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/protocol-compliance",
    tags=["Protocol Compliance"],
)


# ---------------------------------------------------------------------------
# Compliance Assessments
# ---------------------------------------------------------------------------


@router.get(
    "/assessments",
    response_model=ComplianceAssessmentListResponse,
    summary="List compliance assessments",
    description="Retrieve compliance assessments with optional filtering by trial, site, area, and rating.",
)
async def list_assessments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    compliance_area: Optional[ComplianceArea] = Query(None, description="Filter by compliance area"),
    rating: Optional[ComplianceRating] = Query(None, description="Filter by compliance rating"),
) -> ComplianceAssessmentListResponse:
    svc = get_protocol_compliance_service()
    items = svc.list_assessments(
        trial_id=trial_id, site_id=site_id, compliance_area=compliance_area, rating=rating
    )
    return ComplianceAssessmentListResponse(items=items, total=len(items))


@router.get(
    "/assessments/{assessment_id}",
    response_model=ComplianceAssessment,
    summary="Get a compliance assessment",
)
async def get_assessment(assessment_id: str) -> ComplianceAssessment:
    svc = get_protocol_compliance_service()
    assessment = svc.get_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found")
    return assessment


@router.post(
    "/assessments",
    response_model=ComplianceAssessment,
    status_code=201,
    summary="Create a compliance assessment",
)
async def create_assessment(payload: ComplianceAssessmentCreate) -> ComplianceAssessment:
    svc = get_protocol_compliance_service()
    return svc.create_assessment(payload)


@router.put(
    "/assessments/{assessment_id}",
    response_model=ComplianceAssessment,
    summary="Update a compliance assessment",
)
async def update_assessment(
    assessment_id: str, payload: ComplianceAssessmentUpdate
) -> ComplianceAssessment:
    svc = get_protocol_compliance_service()
    updated = svc.update_assessment(assessment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found")
    return updated


@router.delete(
    "/assessments/{assessment_id}",
    status_code=204,
    summary="Delete a compliance assessment",
)
async def delete_assessment(assessment_id: str) -> None:
    svc = get_protocol_compliance_service()
    deleted = svc.delete_assessment(assessment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found")


# ---------------------------------------------------------------------------
# Compliance Findings
# ---------------------------------------------------------------------------


@router.get(
    "/findings",
    response_model=ComplianceFindingListResponse,
    summary="List compliance findings",
    description="Retrieve compliance findings with optional filtering by trial, site, area, severity, and status.",
)
async def list_findings(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    compliance_area: Optional[ComplianceArea] = Query(None, description="Filter by compliance area"),
    severity: Optional[FindingSeverity] = Query(None, description="Filter by severity"),
    status: Optional[FindingStatus] = Query(None, description="Filter by status"),
) -> ComplianceFindingListResponse:
    svc = get_protocol_compliance_service()
    items = svc.list_findings(
        trial_id=trial_id,
        site_id=site_id,
        compliance_area=compliance_area,
        severity=severity,
        status=status,
    )
    return ComplianceFindingListResponse(items=items, total=len(items))


@router.get(
    "/findings/{finding_id}",
    response_model=ComplianceFinding,
    summary="Get a compliance finding",
)
async def get_finding(finding_id: str) -> ComplianceFinding:
    svc = get_protocol_compliance_service()
    finding = svc.get_finding(finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail=f"Finding '{finding_id}' not found")
    return finding


@router.post(
    "/findings",
    response_model=ComplianceFinding,
    status_code=201,
    summary="Create a compliance finding",
)
async def create_finding(payload: ComplianceFindingCreate) -> ComplianceFinding:
    svc = get_protocol_compliance_service()
    return svc.create_finding(payload)


@router.put(
    "/findings/{finding_id}",
    response_model=ComplianceFinding,
    summary="Update a compliance finding",
)
async def update_finding(finding_id: str, payload: ComplianceFindingUpdate) -> ComplianceFinding:
    svc = get_protocol_compliance_service()
    updated = svc.update_finding(finding_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Finding '{finding_id}' not found")
    return updated


@router.delete(
    "/findings/{finding_id}",
    status_code=204,
    summary="Delete a compliance finding",
)
async def delete_finding(finding_id: str) -> None:
    svc = get_protocol_compliance_service()
    deleted = svc.delete_finding(finding_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Finding '{finding_id}' not found")


# ---------------------------------------------------------------------------
# Training Compliance
# ---------------------------------------------------------------------------


@router.get(
    "/training",
    response_model=TrainingComplianceListResponse,
    summary="List training compliance records",
    description="Retrieve training compliance records with optional filtering by trial, site, and status.",
)
async def list_training(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    status: Optional[TrainingStatus] = Query(None, description="Filter by training status"),
) -> TrainingComplianceListResponse:
    svc = get_protocol_compliance_service()
    items = svc.list_training(trial_id=trial_id, site_id=site_id, status=status)
    return TrainingComplianceListResponse(items=items, total=len(items))


@router.get(
    "/training/{training_id}",
    response_model=TrainingCompliance,
    summary="Get a training compliance record",
)
async def get_training(training_id: str) -> TrainingCompliance:
    svc = get_protocol_compliance_service()
    training = svc.get_training(training_id)
    if training is None:
        raise HTTPException(status_code=404, detail=f"Training record '{training_id}' not found")
    return training


@router.post(
    "/training",
    response_model=TrainingCompliance,
    status_code=201,
    summary="Create a training compliance record",
)
async def create_training(payload: TrainingComplianceCreate) -> TrainingCompliance:
    svc = get_protocol_compliance_service()
    return svc.create_training(payload)


@router.put(
    "/training/{training_id}",
    response_model=TrainingCompliance,
    summary="Update a training compliance record",
)
async def update_training(
    training_id: str, payload: TrainingComplianceUpdate
) -> TrainingCompliance:
    svc = get_protocol_compliance_service()
    updated = svc.update_training(training_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Training record '{training_id}' not found")
    return updated


@router.delete(
    "/training/{training_id}",
    status_code=204,
    summary="Delete a training compliance record",
)
async def delete_training(training_id: str) -> None:
    svc = get_protocol_compliance_service()
    deleted = svc.delete_training(training_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Training record '{training_id}' not found")


# ---------------------------------------------------------------------------
# Protocol Adherence
# ---------------------------------------------------------------------------


@router.get(
    "/adherence",
    response_model=ProtocolAdherenceListResponse,
    summary="List protocol adherence records",
    description="Retrieve protocol adherence records with optional filtering by trial, site, and compliance status.",
)
async def list_adherence(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    is_compliant: Optional[bool] = Query(None, description="Filter by compliance status"),
) -> ProtocolAdherenceListResponse:
    svc = get_protocol_compliance_service()
    items = svc.list_adherence(trial_id=trial_id, site_id=site_id, is_compliant=is_compliant)
    return ProtocolAdherenceListResponse(items=items, total=len(items))


@router.get(
    "/adherence/{adherence_id}",
    response_model=ProtocolAdherence,
    summary="Get a protocol adherence record",
)
async def get_adherence(adherence_id: str) -> ProtocolAdherence:
    svc = get_protocol_compliance_service()
    adherence = svc.get_adherence(adherence_id)
    if adherence is None:
        raise HTTPException(status_code=404, detail=f"Adherence record '{adherence_id}' not found")
    return adherence


@router.post(
    "/adherence",
    response_model=ProtocolAdherence,
    status_code=201,
    summary="Create a protocol adherence record",
)
async def create_adherence(payload: ProtocolAdherenceCreate) -> ProtocolAdherence:
    svc = get_protocol_compliance_service()
    return svc.create_adherence(payload)


@router.put(
    "/adherence/{adherence_id}",
    response_model=ProtocolAdherence,
    summary="Update a protocol adherence record",
)
async def update_adherence(
    adherence_id: str, payload: ProtocolAdherenceUpdate
) -> ProtocolAdherence:
    svc = get_protocol_compliance_service()
    updated = svc.update_adherence(adherence_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Adherence record '{adherence_id}' not found")
    return updated


@router.delete(
    "/adherence/{adherence_id}",
    status_code=204,
    summary="Delete a protocol adherence record",
)
async def delete_adherence(adherence_id: str) -> None:
    svc = get_protocol_compliance_service()
    deleted = svc.delete_adherence(adherence_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Adherence record '{adherence_id}' not found")


# ---------------------------------------------------------------------------
# Corrective Actions
# ---------------------------------------------------------------------------


@router.get(
    "/corrective-actions",
    response_model=CorrectiveActionListResponse,
    summary="List corrective actions",
    description="Retrieve corrective actions with optional filtering by trial, site, status, and priority.",
)
async def list_corrective_actions(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    status: Optional[FindingStatus] = Query(None, description="Filter by status"),
    priority: Optional[FindingSeverity] = Query(None, description="Filter by priority"),
) -> CorrectiveActionListResponse:
    svc = get_protocol_compliance_service()
    items = svc.list_corrective_actions(
        trial_id=trial_id, site_id=site_id, status=status, priority=priority
    )
    return CorrectiveActionListResponse(items=items, total=len(items))


@router.get(
    "/corrective-actions/{action_id}",
    response_model=CorrectiveAction,
    summary="Get a corrective action",
)
async def get_corrective_action(action_id: str) -> CorrectiveAction:
    svc = get_protocol_compliance_service()
    action = svc.get_corrective_action(action_id)
    if action is None:
        raise HTTPException(status_code=404, detail=f"Corrective action '{action_id}' not found")
    return action


@router.post(
    "/corrective-actions",
    response_model=CorrectiveAction,
    status_code=201,
    summary="Create a corrective action",
)
async def create_corrective_action(payload: CorrectiveActionCreate) -> CorrectiveAction:
    svc = get_protocol_compliance_service()
    return svc.create_corrective_action(payload)


@router.put(
    "/corrective-actions/{action_id}",
    response_model=CorrectiveAction,
    summary="Update a corrective action",
)
async def update_corrective_action(
    action_id: str, payload: CorrectiveActionUpdate
) -> CorrectiveAction:
    svc = get_protocol_compliance_service()
    updated = svc.update_corrective_action(action_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Corrective action '{action_id}' not found")
    return updated


@router.delete(
    "/corrective-actions/{action_id}",
    status_code=204,
    summary="Delete a corrective action",
)
async def delete_corrective_action(action_id: str) -> None:
    svc = get_protocol_compliance_service()
    deleted = svc.delete_corrective_action(action_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Corrective action '{action_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=ProtocolComplianceMetrics,
    summary="Get protocol compliance metrics",
    description="Aggregated protocol compliance metrics across all entities.",
)
async def get_metrics() -> ProtocolComplianceMetrics:
    svc = get_protocol_compliance_service()
    return svc.get_metrics()
