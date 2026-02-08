"""SOC 2 Compliance API endpoints.

CISO-12: SOC 2 Gap Analysis for the clinical trial patient recruitment
platform. Exposes controls, gap reporting, readiness scoring, and
evidence management.

Endpoints:
    GET  /compliance/soc2/controls           - All controls with status
    GET  /compliance/soc2/controls/{id}       - Control detail
    PUT  /compliance/soc2/controls/{id}       - Update control status/evidence
    GET  /compliance/soc2/gap-report          - Full gap analysis report
    GET  /compliance/soc2/readiness           - Readiness scores per category
    GET  /compliance/soc2/remediation         - Prioritized remediation plan
    POST /compliance/soc2/evidence            - Attach evidence to a control
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.soc2_compliance import (
    ControlStatus,
    EvidenceAttachment,
    EvidenceCreate,
    GapReport,
    ReadinessScore,
    RemediationPlan,
    SOC2Control,
    SOC2ControlUpdate,
    TrustServiceCategory,
)
from app.services.soc2_service import get_soc2_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/compliance/soc2", tags=["SOC 2 Compliance"])


# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------


@router.get(
    "/controls",
    response_model=list[SOC2Control],
    summary="List all SOC 2 controls",
    description=(
        "Returns all SOC 2 controls mapped to platform features. "
        "Optionally filter by Trust Service Category or implementation status."
    ),
)
async def list_controls(
    category: Optional[TrustServiceCategory] = Query(
        default=None, description="Filter by Trust Service Category"
    ),
    control_status: Optional[ControlStatus] = Query(
        default=None,
        alias="status",
        description="Filter by implementation status",
    ),
) -> list[SOC2Control]:
    """List all SOC 2 controls with optional filtering."""
    service = get_soc2_service()
    return service.get_all_controls(category=category, status=control_status)


@router.get(
    "/controls/{control_id}",
    response_model=SOC2Control,
    summary="Get SOC 2 control detail",
    description="Returns detailed information about a specific SOC 2 control.",
)
async def get_control(control_id: str) -> SOC2Control:
    """Get a single SOC 2 control by ID."""
    service = get_soc2_service()
    control = service.get_control(control_id)
    if control is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Control {control_id} not found",
        )
    return control


@router.put(
    "/controls/{control_id}",
    response_model=SOC2Control,
    summary="Update SOC 2 control",
    description=(
        "Update a SOC 2 control's status, evidence, or remediation plan. "
        "Validates status transitions."
    ),
)
async def update_control(
    control_id: str, update: SOC2ControlUpdate
) -> SOC2Control:
    """Update a SOC 2 control."""
    service = get_soc2_service()
    try:
        updated = service.update_control(control_id, update)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Control {control_id} not found",
        )
    return updated


# ---------------------------------------------------------------------------
# Gap Report
# ---------------------------------------------------------------------------


@router.get(
    "/gap-report",
    response_model=GapReport,
    summary="Generate SOC 2 gap analysis report",
    description=(
        "Generates a comprehensive SOC 2 Type II gap analysis report "
        "with executive summary, per-category analysis, and prioritized "
        "remediation plan."
    ),
)
async def get_gap_report() -> GapReport:
    """Generate comprehensive gap analysis report."""
    service = get_soc2_service()
    return service.generate_gap_report()


# ---------------------------------------------------------------------------
# Readiness
# ---------------------------------------------------------------------------


@router.get(
    "/readiness",
    response_model=ReadinessScore,
    summary="Get SOC 2 readiness scores",
    description=(
        "Returns readiness percentage scores per Trust Service Category "
        "and overall readiness."
    ),
)
async def get_readiness() -> ReadinessScore:
    """Get readiness scores per category."""
    service = get_soc2_service()
    return service.get_readiness_scores()


# ---------------------------------------------------------------------------
# Remediation
# ---------------------------------------------------------------------------


@router.get(
    "/remediation",
    response_model=RemediationPlan,
    summary="Get prioritized remediation plan",
    description=(
        "Returns a prioritized list of remediation actions sorted by "
        "priority (P1 audit blockers first)."
    ),
)
async def get_remediation() -> RemediationPlan:
    """Get prioritized remediation plan."""
    service = get_soc2_service()
    return service.get_remediation_plan()


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


@router.post(
    "/evidence",
    response_model=EvidenceAttachment,
    status_code=status.HTTP_201_CREATED,
    summary="Attach evidence to a control",
    description=(
        "Attach evidence (document, test, configuration, screenshot, etc.) "
        "to a SOC 2 control."
    ),
)
async def attach_evidence(evidence: EvidenceCreate) -> EvidenceAttachment:
    """Attach evidence to a SOC 2 control."""
    service = get_soc2_service()
    try:
        return service.attach_evidence(evidence)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
