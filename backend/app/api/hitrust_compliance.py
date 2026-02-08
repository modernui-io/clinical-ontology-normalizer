"""HITRUST CSF v11 Compliance API endpoints.

CISO-13: HITRUST CSF Roadmap for the clinical trial patient recruitment
platform. Exposes controls, readiness scoring, certification roadmap,
and evidence management.

Endpoints:
    GET  /compliance/hitrust/controls           - All controls with maturity levels
    GET  /compliance/hitrust/controls/{id}       - Control detail
    PUT  /compliance/hitrust/controls/{id}       - Update control maturity/evidence
    GET  /compliance/hitrust/readiness           - Certification readiness scores
    GET  /compliance/hitrust/roadmap             - Phased certification roadmap
    GET  /compliance/hitrust/categories           - Category-level summary
    POST /compliance/hitrust/evidence             - Attach evidence to control
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.hitrust_compliance import (
    CategorySummary,
    CertificationRoadmap,
    EvidenceAttachment,
    EvidenceCreate,
    HITRUSTCategory,
    HITRUSTControl,
    HITRUSTControlUpdate,
    MaturityLevel,
    ReadinessScore,
)
from app.services.hitrust_service import get_hitrust_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/compliance/hitrust", tags=["HITRUST Compliance"])


# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------


@router.get(
    "/controls",
    response_model=list[HITRUSTControl],
    summary="List all HITRUST CSF controls",
    description=(
        "Returns all HITRUST CSF v11 controls mapped to platform features. "
        "Optionally filter by category (0-13) or maturity level."
    ),
)
async def list_controls(
    category: Optional[HITRUSTCategory] = Query(
        default=None, description="Filter by HITRUST category (0-13)"
    ),
    maturity: Optional[MaturityLevel] = Query(
        default=None,
        alias="maturity_level",
        description="Filter by maturity level",
    ),
) -> list[HITRUSTControl]:
    """List all HITRUST controls with optional filtering."""
    service = get_hitrust_service()
    return service.get_all_controls(category=category, maturity_level=maturity)


@router.get(
    "/controls/{control_id}",
    response_model=HITRUSTControl,
    summary="Get HITRUST control detail",
    description="Returns detailed information about a specific HITRUST control.",
)
async def get_control(control_id: str) -> HITRUSTControl:
    """Get a single HITRUST control by ID."""
    service = get_hitrust_service()
    control = service.get_control(control_id)
    if control is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Control {control_id} not found",
        )
    return control


@router.put(
    "/controls/{control_id}",
    response_model=HITRUSTControl,
    summary="Update HITRUST control",
    description=(
        "Update a HITRUST control's maturity level, evidence, or remediation plan. "
        "Validates maturity level transitions."
    ),
)
async def update_control(
    control_id: str, update: HITRUSTControlUpdate
) -> HITRUSTControl:
    """Update a HITRUST control."""
    service = get_hitrust_service()
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
# Readiness
# ---------------------------------------------------------------------------


@router.get(
    "/readiness",
    response_model=ReadinessScore,
    summary="Get HITRUST certification readiness scores",
    description=(
        "Returns readiness percentage scores per HITRUST category "
        "and overall readiness for certification."
    ),
)
async def get_readiness() -> ReadinessScore:
    """Get readiness scores per category."""
    service = get_hitrust_service()
    return service.get_readiness_scores()


# ---------------------------------------------------------------------------
# Roadmap
# ---------------------------------------------------------------------------


@router.get(
    "/roadmap",
    response_model=CertificationRoadmap,
    summary="Get HITRUST certification roadmap",
    description=(
        "Returns a phased HITRUST CSF v11 certification roadmap with "
        "4 phases: quick wins, foundational, advanced, and certification."
    ),
)
async def get_roadmap() -> CertificationRoadmap:
    """Generate phased certification roadmap."""
    service = get_hitrust_service()
    return service.generate_roadmap()


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


@router.get(
    "/categories",
    response_model=list[CategorySummary],
    summary="Get HITRUST category summaries",
    description=(
        "Returns a summary for each of the 14 HITRUST CSF v11 control "
        "categories including maturity scores and top gaps."
    ),
)
async def get_categories() -> list[CategorySummary]:
    """Get category-level summaries."""
    service = get_hitrust_service()
    return service.get_category_summaries()


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
        "to a HITRUST control."
    ),
)
async def attach_evidence(evidence: EvidenceCreate) -> EvidenceAttachment:
    """Attach evidence to a HITRUST control."""
    service = get_hitrust_service()
    try:
        return service.attach_evidence(evidence)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
