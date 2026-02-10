"""Lab Certification & Accreditation API endpoints (CLINICAL-LC).

Provides comprehensive laboratory certification and accreditation management:
laboratory CRUD, certification tracking, proficiency testing, lab-trial
qualification workflow, compliance finding management, expiring certification
alerts, and operational metrics.

Endpoints:
    GET    /lab-certification/labs                                  - List laboratories
    GET    /lab-certification/labs/{lab_id}                         - Get single laboratory
    POST   /lab-certification/labs                                  - Create laboratory
    PUT    /lab-certification/labs/{lab_id}                         - Update laboratory
    DELETE /lab-certification/labs/{lab_id}                         - Delete laboratory
    GET    /lab-certification/certifications                        - List certifications
    GET    /lab-certification/certifications/{cert_id}              - Get single certification
    POST   /lab-certification/certifications                        - Create certification
    PUT    /lab-certification/certifications/{cert_id}              - Update certification
    DELETE /lab-certification/certifications/{cert_id}              - Delete certification
    GET    /lab-certification/proficiency-tests                     - List proficiency tests
    GET    /lab-certification/proficiency-tests/{pt_id}             - Get single proficiency test
    POST   /lab-certification/proficiency-tests                     - Record proficiency test
    PUT    /lab-certification/proficiency-tests/{pt_id}             - Update proficiency test
    DELETE /lab-certification/proficiency-tests/{pt_id}             - Delete proficiency test
    GET    /lab-certification/qualifications                        - List qualifications
    GET    /lab-certification/qualifications/{qual_id}              - Get single qualification
    POST   /lab-certification/qualifications                        - Qualify lab for trial
    PUT    /lab-certification/qualifications/{qual_id}              - Update qualification
    DELETE /lab-certification/qualifications/{qual_id}              - Delete qualification
    GET    /lab-certification/compliance-findings                   - List compliance findings
    GET    /lab-certification/compliance-findings/{finding_id}      - Get single finding
    POST   /lab-certification/compliance-findings                   - Log compliance finding
    PUT    /lab-certification/compliance-findings/{finding_id}      - Update finding
    DELETE /lab-certification/compliance-findings/{finding_id}      - Delete finding
    GET    /lab-certification/expiring                              - Expiring certifications
    GET    /lab-certification/metrics                               - Dashboard metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.lab_certification import (
    CertificationStatus,
    CertificationType,
    ComplianceFinding,
    ComplianceFindingCreate,
    ComplianceFindingListResponse,
    ComplianceFindingStatus,
    ComplianceFindingUpdate,
    FindingSeverity,
    LabCertification,
    LabCertificationCreate,
    LabCertificationListResponse,
    LabCertificationUpdate,
    LabMetrics,
    LabQualification,
    LabQualificationCreate,
    LabQualificationListResponse,
    LabQualificationUpdate,
    LabType,
    Laboratory,
    LaboratoryCreate,
    LaboratoryListResponse,
    LaboratoryUpdate,
    ProficiencyResult,
    ProficiencyTest,
    ProficiencyTestCreate,
    ProficiencyTestListResponse,
    ProficiencyTestUpdate,
    QualificationStatus,
)
from app.services.lab_certification_service import get_lab_certification_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/lab-certification",
    tags=["Lab Certification"],
)


# ---------------------------------------------------------------------------
# Laboratory Management
# ---------------------------------------------------------------------------


@router.get(
    "/labs",
    response_model=LaboratoryListResponse,
    summary="List laboratories",
    description="Retrieve laboratories with optional filtering by type, active status, and country.",
)
async def list_laboratories(
    lab_type: Optional[LabType] = Query(None, description="Filter by lab type"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
    country: Optional[str] = Query(None, description="Filter by country code"),
) -> LaboratoryListResponse:
    svc = get_lab_certification_service()
    items = svc.list_laboratories(lab_type=lab_type, active=active, country=country)
    return LaboratoryListResponse(items=items, total=len(items))


@router.get(
    "/labs/{lab_id}",
    response_model=Laboratory,
    summary="Get a laboratory",
)
async def get_laboratory(lab_id: str) -> Laboratory:
    svc = get_lab_certification_service()
    lab = svc.get_laboratory(lab_id)
    if lab is None:
        raise HTTPException(status_code=404, detail=f"Laboratory '{lab_id}' not found")
    return lab


@router.post(
    "/labs",
    response_model=Laboratory,
    status_code=201,
    summary="Create a laboratory",
)
async def create_laboratory(payload: LaboratoryCreate) -> Laboratory:
    svc = get_lab_certification_service()
    return svc.create_laboratory(payload)


@router.put(
    "/labs/{lab_id}",
    response_model=Laboratory,
    summary="Update a laboratory",
)
async def update_laboratory(lab_id: str, payload: LaboratoryUpdate) -> Laboratory:
    svc = get_lab_certification_service()
    updated = svc.update_laboratory(lab_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Laboratory '{lab_id}' not found")
    return updated


@router.delete(
    "/labs/{lab_id}",
    status_code=204,
    summary="Delete a laboratory",
)
async def delete_laboratory(lab_id: str) -> None:
    svc = get_lab_certification_service()
    deleted = svc.delete_laboratory(lab_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Laboratory '{lab_id}' not found")


# ---------------------------------------------------------------------------
# Certification Management
# ---------------------------------------------------------------------------


@router.get(
    "/certifications",
    response_model=LabCertificationListResponse,
    summary="List certifications",
    description="Retrieve certifications with optional filtering by lab, type, and status.",
)
async def list_certifications(
    lab_id: Optional[str] = Query(None, description="Filter by laboratory ID"),
    certification_type: Optional[CertificationType] = Query(
        None, description="Filter by certification type"
    ),
    status: Optional[CertificationStatus] = Query(
        None, description="Filter by status"
    ),
) -> LabCertificationListResponse:
    svc = get_lab_certification_service()
    items = svc.list_certifications(
        lab_id=lab_id, certification_type=certification_type, status=status
    )
    return LabCertificationListResponse(items=items, total=len(items))


@router.get(
    "/certifications/{cert_id}",
    response_model=LabCertification,
    summary="Get a certification",
)
async def get_certification(cert_id: str) -> LabCertification:
    svc = get_lab_certification_service()
    cert = svc.get_certification(cert_id)
    if cert is None:
        raise HTTPException(
            status_code=404, detail=f"Certification '{cert_id}' not found"
        )
    return cert


@router.post(
    "/certifications",
    response_model=LabCertification,
    status_code=201,
    summary="Create a certification",
)
async def create_certification(payload: LabCertificationCreate) -> LabCertification:
    svc = get_lab_certification_service()
    try:
        return svc.create_certification(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/certifications/{cert_id}",
    response_model=LabCertification,
    summary="Update a certification",
)
async def update_certification(
    cert_id: str, payload: LabCertificationUpdate
) -> LabCertification:
    svc = get_lab_certification_service()
    updated = svc.update_certification(cert_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Certification '{cert_id}' not found"
        )
    return updated


@router.delete(
    "/certifications/{cert_id}",
    status_code=204,
    summary="Delete a certification",
)
async def delete_certification(cert_id: str) -> None:
    svc = get_lab_certification_service()
    deleted = svc.delete_certification(cert_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Certification '{cert_id}' not found"
        )


# ---------------------------------------------------------------------------
# Proficiency Testing
# ---------------------------------------------------------------------------


@router.get(
    "/proficiency-tests",
    response_model=ProficiencyTestListResponse,
    summary="List proficiency tests",
    description="Retrieve proficiency test records with optional filtering by lab, result, and cycle.",
)
async def list_proficiency_tests(
    lab_id: Optional[str] = Query(None, description="Filter by laboratory ID"),
    result: Optional[ProficiencyResult] = Query(
        None, description="Filter by test result"
    ),
    cycle: Optional[str] = Query(None, description="Filter by testing cycle"),
) -> ProficiencyTestListResponse:
    svc = get_lab_certification_service()
    items = svc.list_proficiency_tests(lab_id=lab_id, result=result, cycle=cycle)
    return ProficiencyTestListResponse(items=items, total=len(items))


@router.get(
    "/proficiency-tests/{pt_id}",
    response_model=ProficiencyTest,
    summary="Get a proficiency test",
)
async def get_proficiency_test(pt_id: str) -> ProficiencyTest:
    svc = get_lab_certification_service()
    pt = svc.get_proficiency_test(pt_id)
    if pt is None:
        raise HTTPException(
            status_code=404, detail=f"Proficiency test '{pt_id}' not found"
        )
    return pt


@router.post(
    "/proficiency-tests",
    response_model=ProficiencyTest,
    status_code=201,
    summary="Record a proficiency test",
    description="Record a new proficiency testing result for a laboratory analyte.",
)
async def record_proficiency_test(
    payload: ProficiencyTestCreate,
) -> ProficiencyTest:
    svc = get_lab_certification_service()
    try:
        return svc.record_proficiency_test(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/proficiency-tests/{pt_id}",
    response_model=ProficiencyTest,
    summary="Update a proficiency test",
)
async def update_proficiency_test(
    pt_id: str, payload: ProficiencyTestUpdate
) -> ProficiencyTest:
    svc = get_lab_certification_service()
    updated = svc.update_proficiency_test(pt_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Proficiency test '{pt_id}' not found"
        )
    return updated


@router.delete(
    "/proficiency-tests/{pt_id}",
    status_code=204,
    summary="Delete a proficiency test",
)
async def delete_proficiency_test(pt_id: str) -> None:
    svc = get_lab_certification_service()
    deleted = svc.delete_proficiency_test(pt_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Proficiency test '{pt_id}' not found"
        )


# ---------------------------------------------------------------------------
# Lab Qualifications
# ---------------------------------------------------------------------------


@router.get(
    "/qualifications",
    response_model=LabQualificationListResponse,
    summary="List lab qualifications",
    description="Retrieve lab-trial qualifications with optional filtering by lab, trial, and status.",
)
async def list_qualifications(
    lab_id: Optional[str] = Query(None, description="Filter by laboratory ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    qualification_status: Optional[QualificationStatus] = Query(
        None, description="Filter by qualification status"
    ),
) -> LabQualificationListResponse:
    svc = get_lab_certification_service()
    items = svc.list_qualifications(
        lab_id=lab_id, trial_id=trial_id, qualification_status=qualification_status
    )
    return LabQualificationListResponse(items=items, total=len(items))


@router.get(
    "/qualifications/{qual_id}",
    response_model=LabQualification,
    summary="Get a lab qualification",
)
async def get_qualification(qual_id: str) -> LabQualification:
    svc = get_lab_certification_service()
    qual = svc.get_qualification(qual_id)
    if qual is None:
        raise HTTPException(
            status_code=404, detail=f"Qualification '{qual_id}' not found"
        )
    return qual


@router.post(
    "/qualifications",
    response_model=LabQualification,
    status_code=201,
    summary="Qualify lab for trial",
    description="Create a lab-trial qualification. Auto-qualifies if all prerequisites are met.",
)
async def qualify_lab_for_trial(payload: LabQualificationCreate) -> LabQualification:
    svc = get_lab_certification_service()
    try:
        return svc.qualify_lab_for_trial(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/qualifications/{qual_id}",
    response_model=LabQualification,
    summary="Update a lab qualification",
    description="Update qualification details. Auto-promotes to qualified when all prerequisites are met.",
)
async def update_qualification(
    qual_id: str, payload: LabQualificationUpdate
) -> LabQualification:
    svc = get_lab_certification_service()
    updated = svc.update_qualification(qual_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Qualification '{qual_id}' not found"
        )
    return updated


@router.delete(
    "/qualifications/{qual_id}",
    status_code=204,
    summary="Delete a lab qualification",
)
async def delete_qualification(qual_id: str) -> None:
    svc = get_lab_certification_service()
    deleted = svc.delete_qualification(qual_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Qualification '{qual_id}' not found"
        )


# ---------------------------------------------------------------------------
# Compliance Findings
# ---------------------------------------------------------------------------


@router.get(
    "/compliance-findings",
    response_model=ComplianceFindingListResponse,
    summary="List compliance findings",
    description="Retrieve compliance findings with optional filtering by lab, certification, severity, and status.",
)
async def list_compliance_findings(
    lab_id: Optional[str] = Query(None, description="Filter by laboratory ID"),
    certification_id: Optional[str] = Query(
        None, description="Filter by certification ID"
    ),
    severity: Optional[FindingSeverity] = Query(
        None, description="Filter by severity"
    ),
    status: Optional[ComplianceFindingStatus] = Query(
        None, description="Filter by status"
    ),
) -> ComplianceFindingListResponse:
    svc = get_lab_certification_service()
    items = svc.list_compliance_findings(
        lab_id=lab_id,
        certification_id=certification_id,
        severity=severity,
        status=status,
    )
    return ComplianceFindingListResponse(items=items, total=len(items))


@router.get(
    "/compliance-findings/{finding_id}",
    response_model=ComplianceFinding,
    summary="Get a compliance finding",
)
async def get_compliance_finding(finding_id: str) -> ComplianceFinding:
    svc = get_lab_certification_service()
    finding = svc.get_compliance_finding(finding_id)
    if finding is None:
        raise HTTPException(
            status_code=404, detail=f"Compliance finding '{finding_id}' not found"
        )
    return finding


@router.post(
    "/compliance-findings",
    response_model=ComplianceFinding,
    status_code=201,
    summary="Log a compliance finding",
    description="Log a new compliance finding from an inspection or audit.",
)
async def log_compliance_finding(
    payload: ComplianceFindingCreate,
) -> ComplianceFinding:
    svc = get_lab_certification_service()
    try:
        return svc.log_compliance_finding(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/compliance-findings/{finding_id}",
    response_model=ComplianceFinding,
    summary="Update a compliance finding",
    description="Update finding details including status and corrective action.",
)
async def update_compliance_finding(
    finding_id: str, payload: ComplianceFindingUpdate
) -> ComplianceFinding:
    svc = get_lab_certification_service()
    updated = svc.update_compliance_finding(finding_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Compliance finding '{finding_id}' not found"
        )
    return updated


@router.delete(
    "/compliance-findings/{finding_id}",
    status_code=204,
    summary="Delete a compliance finding",
)
async def delete_compliance_finding(finding_id: str) -> None:
    svc = get_lab_certification_service()
    deleted = svc.delete_compliance_finding(finding_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Compliance finding '{finding_id}' not found"
        )


# ---------------------------------------------------------------------------
# Expiring Certifications & Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/expiring",
    response_model=LabCertificationListResponse,
    summary="Get expiring certifications",
    description="Retrieve active/pending certifications expiring within the specified number of days.",
)
async def get_expiring_certifications(
    days: int = Query(
        default=90, ge=1, le=365, description="Number of days to look ahead"
    ),
) -> LabCertificationListResponse:
    svc = get_lab_certification_service()
    items = svc.get_expiring_certifications(days=days)
    return LabCertificationListResponse(items=items, total=len(items))


@router.get(
    "/metrics",
    response_model=LabMetrics,
    summary="Get lab certification metrics",
    description="Aggregated lab certification and accreditation operational metrics.",
)
async def get_metrics() -> LabMetrics:
    svc = get_lab_certification_service()
    return svc.get_metrics()
