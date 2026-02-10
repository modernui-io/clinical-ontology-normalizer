"""Vendor Qualification & Oversight API endpoints (QA-VENDOR).

Provides vendor qualification management: vendor CRUD, quality agreements,
vendor performance assessments, risk assessments, and vendor metrics.

Endpoints:
    GET    /vendor-qualification/vendors                              - List vendors
    GET    /vendor-qualification/vendors/{vendor_id}                  - Get single vendor
    POST   /vendor-qualification/vendors                              - Create vendor
    PUT    /vendor-qualification/vendors/{vendor_id}                  - Update vendor
    DELETE /vendor-qualification/vendors/{vendor_id}                  - Delete vendor
    GET    /vendor-qualification/agreements                           - List quality agreements
    GET    /vendor-qualification/agreements/{agreement_id}            - Get single agreement
    POST   /vendor-qualification/agreements                           - Create agreement
    PUT    /vendor-qualification/agreements/{agreement_id}            - Update agreement
    DELETE /vendor-qualification/agreements/{agreement_id}            - Delete agreement
    GET    /vendor-qualification/assessments                          - List vendor assessments
    GET    /vendor-qualification/assessments/{assessment_id}          - Get single assessment
    POST   /vendor-qualification/assessments                          - Create assessment
    DELETE /vendor-qualification/assessments/{assessment_id}          - Delete assessment
    GET    /vendor-qualification/risk-assessments                     - List risk assessments
    GET    /vendor-qualification/risk-assessments/{risk_assessment_id} - Get single risk assessment
    POST   /vendor-qualification/risk-assessments                     - Create risk assessment
    DELETE /vendor-qualification/risk-assessments/{risk_assessment_id} - Delete risk assessment
    GET    /vendor-qualification/metrics                              - Vendor qualification metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.vendor_qualification import (
    AgreementStatus,
    PerformanceRating,
    QualificationStatus,
    QualityAgreement,
    QualityAgreementCreate,
    QualityAgreementListResponse,
    QualityAgreementUpdate,
    RiskLevel,
    Vendor,
    VendorAssessment,
    VendorAssessmentCreate,
    VendorAssessmentListResponse,
    VendorCategory,
    VendorCreate,
    VendorListResponse,
    VendorQualificationMetrics,
    VendorRiskAssessment,
    VendorRiskAssessmentCreate,
    VendorRiskAssessmentListResponse,
    VendorUpdate,
)
from app.services.vendor_qualification_service import get_vendor_qualification_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/vendor-qualification",
    tags=["Vendor Qualification"],
)


# ---------------------------------------------------------------------------
# Vendor Management
# ---------------------------------------------------------------------------


@router.get(
    "/vendors",
    response_model=VendorListResponse,
    summary="List vendors",
    description="Retrieve vendors with optional filtering by category, qualification status, risk level, or trial.",
)
async def list_vendors(
    category: Optional[VendorCategory] = Query(None, description="Filter by vendor category"),
    qualification_status: Optional[QualificationStatus] = Query(None, description="Filter by qualification status"),
    risk_level: Optional[RiskLevel] = Query(None, description="Filter by risk level"),
    trial_id: Optional[str] = Query(None, description="Filter by active trial ID"),
) -> VendorListResponse:
    svc = get_vendor_qualification_service()
    items = svc.list_vendors(
        category=category,
        qualification_status=qualification_status,
        risk_level=risk_level,
        trial_id=trial_id,
    )
    return VendorListResponse(items=items, total=len(items))


@router.get(
    "/vendors/{vendor_id}",
    response_model=Vendor,
    summary="Get a vendor",
)
async def get_vendor(vendor_id: str) -> Vendor:
    svc = get_vendor_qualification_service()
    vendor = svc.get_vendor(vendor_id)
    if vendor is None:
        raise HTTPException(status_code=404, detail=f"Vendor '{vendor_id}' not found")
    return vendor


@router.post(
    "/vendors",
    response_model=Vendor,
    status_code=201,
    summary="Create a vendor",
)
async def create_vendor(payload: VendorCreate) -> Vendor:
    svc = get_vendor_qualification_service()
    return svc.create_vendor(payload)


@router.put(
    "/vendors/{vendor_id}",
    response_model=Vendor,
    summary="Update a vendor",
)
async def update_vendor(vendor_id: str, payload: VendorUpdate) -> Vendor:
    svc = get_vendor_qualification_service()
    updated = svc.update_vendor(vendor_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Vendor '{vendor_id}' not found")
    return updated


@router.delete(
    "/vendors/{vendor_id}",
    status_code=204,
    summary="Delete a vendor",
)
async def delete_vendor(vendor_id: str) -> None:
    svc = get_vendor_qualification_service()
    deleted = svc.delete_vendor(vendor_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Vendor '{vendor_id}' not found")


# ---------------------------------------------------------------------------
# Quality Agreements
# ---------------------------------------------------------------------------


@router.get(
    "/agreements",
    response_model=QualityAgreementListResponse,
    summary="List quality agreements",
    description="Retrieve quality agreements with optional filtering by vendor, trial, or status.",
)
async def list_agreements(
    vendor_id: Optional[str] = Query(None, description="Filter by vendor ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[AgreementStatus] = Query(None, description="Filter by agreement status"),
) -> QualityAgreementListResponse:
    svc = get_vendor_qualification_service()
    items = svc.list_agreements(vendor_id=vendor_id, trial_id=trial_id, status=status)
    return QualityAgreementListResponse(items=items, total=len(items))


@router.get(
    "/agreements/{agreement_id}",
    response_model=QualityAgreement,
    summary="Get a quality agreement",
)
async def get_agreement(agreement_id: str) -> QualityAgreement:
    svc = get_vendor_qualification_service()
    agreement = svc.get_agreement(agreement_id)
    if agreement is None:
        raise HTTPException(status_code=404, detail=f"Agreement '{agreement_id}' not found")
    return agreement


@router.post(
    "/agreements",
    response_model=QualityAgreement,
    status_code=201,
    summary="Create a quality agreement",
)
async def create_agreement(payload: QualityAgreementCreate) -> QualityAgreement:
    svc = get_vendor_qualification_service()
    try:
        return svc.create_agreement(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/agreements/{agreement_id}",
    response_model=QualityAgreement,
    summary="Update a quality agreement",
)
async def update_agreement(
    agreement_id: str, payload: QualityAgreementUpdate
) -> QualityAgreement:
    svc = get_vendor_qualification_service()
    updated = svc.update_agreement(agreement_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Agreement '{agreement_id}' not found")
    return updated


@router.delete(
    "/agreements/{agreement_id}",
    status_code=204,
    summary="Delete a quality agreement",
)
async def delete_agreement(agreement_id: str) -> None:
    svc = get_vendor_qualification_service()
    deleted = svc.delete_agreement(agreement_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Agreement '{agreement_id}' not found")


# ---------------------------------------------------------------------------
# Vendor Assessments
# ---------------------------------------------------------------------------


@router.get(
    "/assessments",
    response_model=VendorAssessmentListResponse,
    summary="List vendor assessments",
    description="Retrieve vendor assessments with optional filtering by vendor, trial, or rating.",
)
async def list_assessments(
    vendor_id: Optional[str] = Query(None, description="Filter by vendor ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    rating: Optional[PerformanceRating] = Query(None, description="Filter by performance rating"),
) -> VendorAssessmentListResponse:
    svc = get_vendor_qualification_service()
    items = svc.list_assessments(vendor_id=vendor_id, trial_id=trial_id, rating=rating)
    return VendorAssessmentListResponse(items=items, total=len(items))


@router.get(
    "/assessments/{assessment_id}",
    response_model=VendorAssessment,
    summary="Get a vendor assessment",
)
async def get_assessment(assessment_id: str) -> VendorAssessment:
    svc = get_vendor_qualification_service()
    assessment = svc.get_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found")
    return assessment


@router.post(
    "/assessments",
    response_model=VendorAssessment,
    status_code=201,
    summary="Create a vendor assessment",
    description="Create a vendor performance assessment. The overall_score is automatically computed as the average of the four component scores.",
)
async def create_assessment(payload: VendorAssessmentCreate) -> VendorAssessment:
    svc = get_vendor_qualification_service()
    try:
        return svc.create_assessment(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete(
    "/assessments/{assessment_id}",
    status_code=204,
    summary="Delete a vendor assessment",
)
async def delete_assessment(assessment_id: str) -> None:
    svc = get_vendor_qualification_service()
    deleted = svc.delete_assessment(assessment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found")


# ---------------------------------------------------------------------------
# Risk Assessments
# ---------------------------------------------------------------------------


@router.get(
    "/risk-assessments",
    response_model=VendorRiskAssessmentListResponse,
    summary="List vendor risk assessments",
    description="Retrieve vendor risk assessments with optional filtering by vendor or risk level.",
)
async def list_risk_assessments(
    vendor_id: Optional[str] = Query(None, description="Filter by vendor ID"),
    risk_level: Optional[RiskLevel] = Query(None, description="Filter by risk level"),
) -> VendorRiskAssessmentListResponse:
    svc = get_vendor_qualification_service()
    items = svc.list_risk_assessments(vendor_id=vendor_id, risk_level=risk_level)
    return VendorRiskAssessmentListResponse(items=items, total=len(items))


@router.get(
    "/risk-assessments/{risk_assessment_id}",
    response_model=VendorRiskAssessment,
    summary="Get a vendor risk assessment",
)
async def get_risk_assessment(risk_assessment_id: str) -> VendorRiskAssessment:
    svc = get_vendor_qualification_service()
    risk_assessment = svc.get_risk_assessment(risk_assessment_id)
    if risk_assessment is None:
        raise HTTPException(
            status_code=404,
            detail=f"Risk assessment '{risk_assessment_id}' not found",
        )
    return risk_assessment


@router.post(
    "/risk-assessments",
    response_model=VendorRiskAssessment,
    status_code=201,
    summary="Create a vendor risk assessment",
)
async def create_risk_assessment(
    payload: VendorRiskAssessmentCreate,
) -> VendorRiskAssessment:
    svc = get_vendor_qualification_service()
    try:
        return svc.create_risk_assessment(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete(
    "/risk-assessments/{risk_assessment_id}",
    status_code=204,
    summary="Delete a vendor risk assessment",
)
async def delete_risk_assessment(risk_assessment_id: str) -> None:
    svc = get_vendor_qualification_service()
    deleted = svc.delete_risk_assessment(risk_assessment_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Risk assessment '{risk_assessment_id}' not found",
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=VendorQualificationMetrics,
    summary="Get vendor qualification metrics",
    description="Aggregated vendor qualification metrics including vendor counts by category/status/risk, "
                "agreement status breakdown, assessment score averages, and risk overview.",
)
async def get_metrics() -> VendorQualificationMetrics:
    svc = get_vendor_qualification_service()
    return svc.get_metrics()
