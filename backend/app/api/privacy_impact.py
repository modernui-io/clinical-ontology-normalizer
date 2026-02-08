"""Privacy Impact Assessment API endpoints (CLO-4).

Provides endpoints for GDPR Article 35 compliant Privacy Impact
Assessments including PIA lifecycle management, risk tracking,
mitigation workflows, and DPO approval.

Endpoints:
    GET    /privacy-impact/assessments              - List PIAs
    GET    /privacy-impact/assessments/metrics       - PIA program metrics
    GET    /privacy-impact/assessments/overdue       - Overdue PIA reviews
    GET    /privacy-impact/assessments/{id}          - PIA detail
    POST   /privacy-impact/assessments               - Create PIA
    PUT    /privacy-impact/assessments/{id}          - Update PIA
    POST   /privacy-impact/assessments/{id}/processing-activities - Add processing activity
    POST   /privacy-impact/assessments/{id}/risks    - Add risk
    PUT    /privacy-impact/assessments/{id}/risks/{risk_id}/mitigation - Update mitigation
    POST   /privacy-impact/assessments/{id}/submit   - Submit for review
    POST   /privacy-impact/assessments/{id}/approve  - Approve PIA
    POST   /privacy-impact/assessments/{id}/dpo-approval - Request DPO approval
    GET    /privacy-impact/assessments/{id}/consultation-check - Check consultation
    GET    /privacy-impact/templates                 - List templates
    GET    /privacy-impact/templates/{id}            - Template detail
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.privacy_impact import (
    ConsultationCheckResponse,
    PIAApproveRequest,
    PIACreateRequest,
    PIAListResponse,
    PIAMetrics,
    PIARecord,
    PIAStatus,
    PIATemplate,
    PIATemplateListResponse,
    PIAUpdateRequest,
    ProcessingActivityCreateRequest,
    RiskCreateRequest,
    RiskMitigationUpdateRequest,
)
from app.services.privacy_impact_service import get_privacy_impact_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/privacy-impact", tags=["Privacy Impact Assessment"])


# ============================================================================
# PIA Endpoints
# ============================================================================


@router.get(
    "/assessments/metrics",
    response_model=PIAMetrics,
    summary="Get PIA program metrics",
    description="Get aggregated PIA program metrics including counts by status, risk levels, and processing activities.",
)
async def get_pia_metrics() -> PIAMetrics:
    """Get PIA program metrics."""
    service = get_privacy_impact_service()
    return service.get_metrics()


@router.get(
    "/assessments/overdue",
    response_model=list[PIARecord],
    summary="Get overdue PIA reviews",
    description="List PIAs that are past their scheduled review date.",
)
async def get_overdue_reviews() -> list[PIARecord]:
    """Get PIAs past their next review date."""
    service = get_privacy_impact_service()
    return service.get_overdue_reviews()


@router.get(
    "/assessments",
    response_model=PIAListResponse,
    summary="List PIAs",
    description="List Privacy Impact Assessments with optional filtering by status.",
)
async def list_pias(
    pia_status: PIAStatus | None = Query(
        default=None, alias="status", description="Filter by PIA status"
    ),
    limit: int = Query(default=100, ge=1, le=1000, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
) -> PIAListResponse:
    """List PIAs with optional filters."""
    service = get_privacy_impact_service()
    pias, total = service.list_pias(status=pia_status, limit=limit, offset=offset)
    return PIAListResponse(
        assessments=pias,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/assessments/{pia_id}",
    response_model=PIARecord,
    summary="Get PIA detail",
    description="Get full details of a specific Privacy Impact Assessment.",
)
async def get_pia(pia_id: str) -> PIARecord:
    """Get a specific PIA by ID."""
    service = get_privacy_impact_service()
    pia = service.get_pia(pia_id)
    if pia is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PIA not found: {pia_id}",
        )
    return pia


@router.post(
    "/assessments",
    response_model=PIARecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a PIA",
    description="Create a new Privacy Impact Assessment in DRAFT status.",
)
async def create_pia(request: PIACreateRequest) -> PIARecord:
    """Create a new PIA."""
    service = get_privacy_impact_service()
    pia = service.create_pia(
        title=request.title,
        description=request.description,
        assessor=request.assessor,
    )
    logger.info("PIA created via API: %s", pia.id)
    return pia


@router.put(
    "/assessments/{pia_id}",
    response_model=PIARecord,
    summary="Update a PIA",
    description="Update PIA fields.",
)
async def update_pia(pia_id: str, request: PIAUpdateRequest) -> PIARecord:
    """Update an existing PIA."""
    service = get_privacy_impact_service()
    try:
        pia = service.update_pia(
            pia_id=pia_id,
            title=request.title,
            description=request.description,
            assessor=request.assessor,
            reviewer=request.reviewer,
            necessity_assessment=request.necessity_assessment,
            proportionality_assessment=request.proportionality_assessment,
            next_review_date=request.next_review_date,
        )
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    return pia


@router.post(
    "/assessments/{pia_id}/processing-activities",
    response_model=PIARecord,
    status_code=status.HTTP_201_CREATED,
    summary="Add processing activity",
    description="Add a data processing activity to a PIA.",
)
async def add_processing_activity(
    pia_id: str, request: ProcessingActivityCreateRequest
) -> PIARecord:
    """Add a processing activity to a PIA."""
    service = get_privacy_impact_service()
    try:
        pia = service.add_processing_activity(
            pia_id=pia_id,
            name=request.name,
            description=request.description,
            data_categories=request.data_categories,
            processing_purpose=request.processing_purpose,
            legal_basis=request.legal_basis,
            data_subjects=request.data_subjects,
            retention_period_months=request.retention_period_months,
            cross_border_transfer=request.cross_border_transfer,
            automated_decision_making=request.automated_decision_making,
            third_party_sharing=request.third_party_sharing,
            third_parties=request.third_parties,
        )
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    return pia


@router.post(
    "/assessments/{pia_id}/risks",
    response_model=PIARecord,
    status_code=status.HTTP_201_CREATED,
    summary="Add privacy risk",
    description="Add an identified privacy risk to a PIA with auto-calculated risk score.",
)
async def add_risk(pia_id: str, request: RiskCreateRequest) -> PIARecord:
    """Add a risk to a PIA."""
    service = get_privacy_impact_service()
    try:
        pia = service.add_risk(
            pia_id=pia_id,
            title=request.title,
            description=request.description,
            likelihood=request.likelihood,
            impact=request.impact,
            affected_rights=request.affected_rights,
        )
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    return pia


@router.put(
    "/assessments/{pia_id}/risks/{risk_id}/mitigation",
    response_model=PIARecord,
    summary="Update risk mitigation",
    description="Update mitigation measures and residual risk for an identified risk.",
)
async def update_risk_mitigation(
    pia_id: str, risk_id: str, request: RiskMitigationUpdateRequest
) -> PIARecord:
    """Update mitigation measures for a risk."""
    service = get_privacy_impact_service()
    try:
        pia = service.update_risk_mitigation(
            pia_id=pia_id,
            risk_id=risk_id,
            mitigation_measures=request.mitigation_measures,
            residual_risk_score=request.residual_risk_score,
        )
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    return pia


@router.post(
    "/assessments/{pia_id}/submit",
    response_model=PIARecord,
    summary="Submit PIA for review",
    description="Submit a DRAFT PIA for review (DRAFT -> IN_REVIEW).",
)
async def submit_for_review(pia_id: str) -> PIARecord:
    """Submit a PIA for review."""
    service = get_privacy_impact_service()
    try:
        pia = service.submit_for_review(pia_id)
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    return pia


@router.post(
    "/assessments/{pia_id}/approve",
    response_model=PIARecord,
    summary="Approve PIA",
    description="Approve a PIA (IN_REVIEW -> APPROVED). Requires all HIGH/CRITICAL risks to have mitigations.",
)
async def approve_pia(pia_id: str, request: PIAApproveRequest) -> PIARecord:
    """Approve a PIA."""
    service = get_privacy_impact_service()
    try:
        pia = service.approve_pia(pia_id, reviewer=request.reviewer)
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    return pia


@router.post(
    "/assessments/{pia_id}/dpo-approval",
    response_model=PIARecord,
    summary="Request DPO approval",
    description="Flag a PIA for Data Protection Officer review and approval.",
)
async def request_dpo_approval(pia_id: str) -> PIARecord:
    """Request DPO approval for a PIA."""
    service = get_privacy_impact_service()
    try:
        pia = service.request_dpo_approval(pia_id)
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    return pia


@router.get(
    "/assessments/{pia_id}/consultation-check",
    response_model=ConsultationCheckResponse,
    summary="Check consultation requirement",
    description="Check if supervisory authority consultation is required for this PIA.",
)
async def check_consultation(pia_id: str) -> ConsultationCheckResponse:
    """Check if supervisory authority consultation is required."""
    service = get_privacy_impact_service()
    try:
        result = service.check_consultation_required(pia_id)
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    return result


# ============================================================================
# Template Endpoints
# ============================================================================


@router.get(
    "/templates",
    response_model=PIATemplateListResponse,
    summary="List PIA templates",
    description="List all available PIA assessment templates.",
)
async def list_templates() -> PIATemplateListResponse:
    """List all PIA templates."""
    service = get_privacy_impact_service()
    templates = service.get_templates()
    return PIATemplateListResponse(
        templates=templates,
        total=len(templates),
    )


@router.get(
    "/templates/{template_id}",
    response_model=PIATemplate,
    summary="Get PIA template",
    description="Get full details of a specific PIA template.",
)
async def get_template(template_id: str) -> PIATemplate:
    """Get a specific PIA template by ID."""
    service = get_privacy_impact_service()
    template = service.get_template(template_id)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {template_id}",
        )
    return template
