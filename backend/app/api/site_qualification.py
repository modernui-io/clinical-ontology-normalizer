"""Site Qualification Management API endpoints (SITE-QUAL).

Provides comprehensive site qualification operations: capability assessments,
equipment verification, staff credentialing, infrastructure audits,
qualification records, and qualification metrics.

Endpoints:
    GET    /site-qualification/capability-assessments                        - List assessments
    GET    /site-qualification/capability-assessments/{assessment_id}        - Get single assessment
    POST   /site-qualification/capability-assessments                        - Create assessment
    PUT    /site-qualification/capability-assessments/{assessment_id}        - Update assessment
    DELETE /site-qualification/capability-assessments/{assessment_id}        - Delete assessment
    GET    /site-qualification/equipment-verifications                       - List verifications
    GET    /site-qualification/equipment-verifications/{verification_id}     - Get single verification
    POST   /site-qualification/equipment-verifications                       - Create verification
    PUT    /site-qualification/equipment-verifications/{verification_id}     - Update verification
    DELETE /site-qualification/equipment-verifications/{verification_id}     - Delete verification
    GET    /site-qualification/staff-credentials                             - List credentials
    GET    /site-qualification/staff-credentials/{credential_id}             - Get single credential
    POST   /site-qualification/staff-credentials                             - Create credential
    PUT    /site-qualification/staff-credentials/{credential_id}             - Update credential
    DELETE /site-qualification/staff-credentials/{credential_id}             - Delete credential
    GET    /site-qualification/infrastructure-audits                         - List audits
    GET    /site-qualification/infrastructure-audits/{audit_id}              - Get single audit
    POST   /site-qualification/infrastructure-audits                         - Create audit
    PUT    /site-qualification/infrastructure-audits/{audit_id}              - Update audit
    DELETE /site-qualification/infrastructure-audits/{audit_id}              - Delete audit
    GET    /site-qualification/qualification-records                         - List records
    GET    /site-qualification/qualification-records/{record_id}             - Get single record
    POST   /site-qualification/qualification-records                         - Create record
    PUT    /site-qualification/qualification-records/{record_id}             - Update record
    DELETE /site-qualification/qualification-records/{record_id}             - Delete record
    GET    /site-qualification/metrics                                       - Qualification metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.site_qualification import (
    AssessmentCategory,
    AuditRating,
    CapabilityAssessment,
    CapabilityAssessmentCreate,
    CapabilityAssessmentListResponse,
    CapabilityAssessmentUpdate,
    CredentialType,
    EquipmentStatus,
    EquipmentVerification,
    EquipmentVerificationCreate,
    EquipmentVerificationListResponse,
    EquipmentVerificationUpdate,
    InfrastructureAudit,
    InfrastructureAuditCreate,
    InfrastructureAuditListResponse,
    InfrastructureAuditUpdate,
    QualificationRecord,
    QualificationRecordCreate,
    QualificationRecordListResponse,
    QualificationRecordUpdate,
    QualificationStatus,
    SiteQualificationMetrics,
    StaffCredential,
    StaffCredentialCreate,
    StaffCredentialListResponse,
    StaffCredentialUpdate,
)
from app.services.site_qualification_service import get_site_qualification_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/site-qualification",
    tags=["Site Qualification"],
)


# ---------------------------------------------------------------------------
# Capability Assessments
# ---------------------------------------------------------------------------


@router.get(
    "/capability-assessments",
    response_model=CapabilityAssessmentListResponse,
    summary="List capability assessments",
    description="Retrieve capability assessments with optional filtering by trial, site, and category.",
)
async def list_capability_assessments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    category: Optional[AssessmentCategory] = Query(None, description="Filter by assessment category"),
) -> CapabilityAssessmentListResponse:
    svc = get_site_qualification_service()
    items = svc.list_capability_assessments(
        trial_id=trial_id, site_id=site_id, category=category
    )
    return CapabilityAssessmentListResponse(items=items, total=len(items))


@router.get(
    "/capability-assessments/{assessment_id}",
    response_model=CapabilityAssessment,
    summary="Get a capability assessment",
)
async def get_capability_assessment(assessment_id: str) -> CapabilityAssessment:
    svc = get_site_qualification_service()
    assessment = svc.get_capability_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(
            status_code=404, detail=f"Capability assessment '{assessment_id}' not found"
        )
    return assessment


@router.post(
    "/capability-assessments",
    response_model=CapabilityAssessment,
    status_code=201,
    summary="Create a capability assessment",
)
async def create_capability_assessment(payload: CapabilityAssessmentCreate) -> CapabilityAssessment:
    svc = get_site_qualification_service()
    return svc.create_capability_assessment(payload)


@router.put(
    "/capability-assessments/{assessment_id}",
    response_model=CapabilityAssessment,
    summary="Update a capability assessment",
)
async def update_capability_assessment(
    assessment_id: str, payload: CapabilityAssessmentUpdate
) -> CapabilityAssessment:
    svc = get_site_qualification_service()
    updated = svc.update_capability_assessment(assessment_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Capability assessment '{assessment_id}' not found"
        )
    return updated


@router.delete(
    "/capability-assessments/{assessment_id}",
    status_code=204,
    summary="Delete a capability assessment",
)
async def delete_capability_assessment(assessment_id: str) -> None:
    svc = get_site_qualification_service()
    deleted = svc.delete_capability_assessment(assessment_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Capability assessment '{assessment_id}' not found"
        )


# ---------------------------------------------------------------------------
# Equipment Verifications
# ---------------------------------------------------------------------------


@router.get(
    "/equipment-verifications",
    response_model=EquipmentVerificationListResponse,
    summary="List equipment verifications",
    description="Retrieve equipment verifications with optional filtering by trial, site, and status.",
)
async def list_equipment_verifications(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    status: Optional[EquipmentStatus] = Query(None, description="Filter by equipment status"),
) -> EquipmentVerificationListResponse:
    svc = get_site_qualification_service()
    items = svc.list_equipment_verifications(
        trial_id=trial_id, site_id=site_id, status=status
    )
    return EquipmentVerificationListResponse(items=items, total=len(items))


@router.get(
    "/equipment-verifications/{verification_id}",
    response_model=EquipmentVerification,
    summary="Get an equipment verification",
)
async def get_equipment_verification(verification_id: str) -> EquipmentVerification:
    svc = get_site_qualification_service()
    verification = svc.get_equipment_verification(verification_id)
    if verification is None:
        raise HTTPException(
            status_code=404, detail=f"Equipment verification '{verification_id}' not found"
        )
    return verification


@router.post(
    "/equipment-verifications",
    response_model=EquipmentVerification,
    status_code=201,
    summary="Create an equipment verification",
)
async def create_equipment_verification(payload: EquipmentVerificationCreate) -> EquipmentVerification:
    svc = get_site_qualification_service()
    return svc.create_equipment_verification(payload)


@router.put(
    "/equipment-verifications/{verification_id}",
    response_model=EquipmentVerification,
    summary="Update an equipment verification",
)
async def update_equipment_verification(
    verification_id: str, payload: EquipmentVerificationUpdate
) -> EquipmentVerification:
    svc = get_site_qualification_service()
    updated = svc.update_equipment_verification(verification_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Equipment verification '{verification_id}' not found"
        )
    return updated


@router.delete(
    "/equipment-verifications/{verification_id}",
    status_code=204,
    summary="Delete an equipment verification",
)
async def delete_equipment_verification(verification_id: str) -> None:
    svc = get_site_qualification_service()
    deleted = svc.delete_equipment_verification(verification_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Equipment verification '{verification_id}' not found"
        )


# ---------------------------------------------------------------------------
# Staff Credentials
# ---------------------------------------------------------------------------


@router.get(
    "/staff-credentials",
    response_model=StaffCredentialListResponse,
    summary="List staff credentials",
    description="Retrieve staff credentials with optional filtering by trial, site, and credential type.",
)
async def list_staff_credentials(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    credential_type: Optional[CredentialType] = Query(None, description="Filter by credential type"),
) -> StaffCredentialListResponse:
    svc = get_site_qualification_service()
    items = svc.list_staff_credentials(
        trial_id=trial_id, site_id=site_id, credential_type=credential_type
    )
    return StaffCredentialListResponse(items=items, total=len(items))


@router.get(
    "/staff-credentials/{credential_id}",
    response_model=StaffCredential,
    summary="Get a staff credential",
)
async def get_staff_credential(credential_id: str) -> StaffCredential:
    svc = get_site_qualification_service()
    credential = svc.get_staff_credential(credential_id)
    if credential is None:
        raise HTTPException(
            status_code=404, detail=f"Staff credential '{credential_id}' not found"
        )
    return credential


@router.post(
    "/staff-credentials",
    response_model=StaffCredential,
    status_code=201,
    summary="Create a staff credential",
)
async def create_staff_credential(payload: StaffCredentialCreate) -> StaffCredential:
    svc = get_site_qualification_service()
    return svc.create_staff_credential(payload)


@router.put(
    "/staff-credentials/{credential_id}",
    response_model=StaffCredential,
    summary="Update a staff credential",
)
async def update_staff_credential(
    credential_id: str, payload: StaffCredentialUpdate
) -> StaffCredential:
    svc = get_site_qualification_service()
    updated = svc.update_staff_credential(credential_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Staff credential '{credential_id}' not found"
        )
    return updated


@router.delete(
    "/staff-credentials/{credential_id}",
    status_code=204,
    summary="Delete a staff credential",
)
async def delete_staff_credential(credential_id: str) -> None:
    svc = get_site_qualification_service()
    deleted = svc.delete_staff_credential(credential_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Staff credential '{credential_id}' not found"
        )


# ---------------------------------------------------------------------------
# Infrastructure Audits
# ---------------------------------------------------------------------------


@router.get(
    "/infrastructure-audits",
    response_model=InfrastructureAuditListResponse,
    summary="List infrastructure audits",
    description="Retrieve infrastructure audits with optional filtering by trial, site, and rating.",
)
async def list_infrastructure_audits(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    rating: Optional[AuditRating] = Query(None, description="Filter by audit rating"),
) -> InfrastructureAuditListResponse:
    svc = get_site_qualification_service()
    items = svc.list_infrastructure_audits(
        trial_id=trial_id, site_id=site_id, rating=rating
    )
    return InfrastructureAuditListResponse(items=items, total=len(items))


@router.get(
    "/infrastructure-audits/{audit_id}",
    response_model=InfrastructureAudit,
    summary="Get an infrastructure audit",
)
async def get_infrastructure_audit(audit_id: str) -> InfrastructureAudit:
    svc = get_site_qualification_service()
    audit = svc.get_infrastructure_audit(audit_id)
    if audit is None:
        raise HTTPException(
            status_code=404, detail=f"Infrastructure audit '{audit_id}' not found"
        )
    return audit


@router.post(
    "/infrastructure-audits",
    response_model=InfrastructureAudit,
    status_code=201,
    summary="Create an infrastructure audit",
)
async def create_infrastructure_audit(payload: InfrastructureAuditCreate) -> InfrastructureAudit:
    svc = get_site_qualification_service()
    return svc.create_infrastructure_audit(payload)


@router.put(
    "/infrastructure-audits/{audit_id}",
    response_model=InfrastructureAudit,
    summary="Update an infrastructure audit",
)
async def update_infrastructure_audit(
    audit_id: str, payload: InfrastructureAuditUpdate
) -> InfrastructureAudit:
    svc = get_site_qualification_service()
    updated = svc.update_infrastructure_audit(audit_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Infrastructure audit '{audit_id}' not found"
        )
    return updated


@router.delete(
    "/infrastructure-audits/{audit_id}",
    status_code=204,
    summary="Delete an infrastructure audit",
)
async def delete_infrastructure_audit(audit_id: str) -> None:
    svc = get_site_qualification_service()
    deleted = svc.delete_infrastructure_audit(audit_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Infrastructure audit '{audit_id}' not found"
        )


# ---------------------------------------------------------------------------
# Qualification Records
# ---------------------------------------------------------------------------


@router.get(
    "/qualification-records",
    response_model=QualificationRecordListResponse,
    summary="List qualification records",
    description="Retrieve qualification records with optional filtering by trial, site, and status.",
)
async def list_qualification_records(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    qualification_status: Optional[QualificationStatus] = Query(
        None, description="Filter by qualification status"
    ),
) -> QualificationRecordListResponse:
    svc = get_site_qualification_service()
    items = svc.list_qualification_records(
        trial_id=trial_id, site_id=site_id, qualification_status=qualification_status
    )
    return QualificationRecordListResponse(items=items, total=len(items))


@router.get(
    "/qualification-records/{record_id}",
    response_model=QualificationRecord,
    summary="Get a qualification record",
)
async def get_qualification_record(record_id: str) -> QualificationRecord:
    svc = get_site_qualification_service()
    record = svc.get_qualification_record(record_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Qualification record '{record_id}' not found"
        )
    return record


@router.post(
    "/qualification-records",
    response_model=QualificationRecord,
    status_code=201,
    summary="Create a qualification record",
)
async def create_qualification_record(payload: QualificationRecordCreate) -> QualificationRecord:
    svc = get_site_qualification_service()
    return svc.create_qualification_record(payload)


@router.put(
    "/qualification-records/{record_id}",
    response_model=QualificationRecord,
    summary="Update a qualification record",
)
async def update_qualification_record(
    record_id: str, payload: QualificationRecordUpdate
) -> QualificationRecord:
    svc = get_site_qualification_service()
    updated = svc.update_qualification_record(record_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Qualification record '{record_id}' not found"
        )
    return updated


@router.delete(
    "/qualification-records/{record_id}",
    status_code=204,
    summary="Delete a qualification record",
)
async def delete_qualification_record(record_id: str) -> None:
    svc = get_site_qualification_service()
    deleted = svc.delete_qualification_record(record_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Qualification record '{record_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=SiteQualificationMetrics,
    summary="Get site qualification metrics",
    description="Aggregated metrics across all site qualification operations.",
)
async def get_metrics() -> SiteQualificationMetrics:
    svc = get_site_qualification_service()
    return svc.get_metrics()
