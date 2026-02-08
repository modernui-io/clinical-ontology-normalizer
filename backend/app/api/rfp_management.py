"""RFP Management API endpoints.

Partnership-1: Provides endpoints for generating RFP responses,
retrieving competitive positioning matrices, capability catalogs,
case studies, and matching requirements to platform capabilities.

Endpoints:
    GET  /partnerships/rfp/templates              - List available RFP templates
    GET  /partnerships/rfp/templates/{section}     - Get specific section
    POST /partnerships/rfp/generate                - Generate customized RFP response
    GET  /partnerships/rfp/capabilities            - Full capability catalog
    GET  /partnerships/rfp/competitive-matrix      - Competitive positioning
    GET  /partnerships/rfp/case-studies             - Case study templates
    POST /partnerships/rfp/match-requirements       - Match requirements to capabilities
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.schemas.rfp_management import (
    CapabilityCatalogResponse,
    CaseStudyListResponse,
    CompetitiveMatrixResponse,
    RFPGeneratedResponse,
    RFPGenerateRequest,
    RFPTemplateListResponse,
    RFPTemplateSection,
    RequirementMatchRequest,
    RequirementMatchResponse,
)
from app.services.rfp_service import get_rfp_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/partnerships/rfp", tags=["Partnerships"])


@router.get(
    "/templates",
    response_model=RFPTemplateListResponse,
    summary="List RFP template sections",
    description="Returns all available RFP response template sections with pre-populated content.",
)
async def list_templates() -> RFPTemplateListResponse:
    """List all available RFP template sections."""
    service = get_rfp_service()
    return service.list_templates()


@router.get(
    "/templates/{section}",
    response_model=RFPTemplateSection,
    summary="Get RFP template section",
    description="Returns a specific RFP template section by its identifier.",
)
async def get_template_section(section: str) -> RFPTemplateSection:
    """Get a specific RFP template section."""
    service = get_rfp_service()
    result = service.get_template_section(section)
    if result is None:
        valid_sections = service.get_section_ids()
        raise HTTPException(
            status_code=404,
            detail=f"Section '{section}' not found. Valid sections: {valid_sections}",
        )
    return result


@router.post(
    "/generate",
    response_model=RFPGeneratedResponse,
    summary="Generate customized RFP response",
    description=(
        "Generates a customized RFP response based on sponsor details, "
        "therapeutic area, and specific requirements. Automatically matches "
        "requirements to platform capabilities and selects relevant case studies."
    ),
)
async def generate_rfp(request: RFPGenerateRequest) -> RFPGeneratedResponse:
    """Generate a customized RFP response."""
    service = get_rfp_service()
    return service.generate_rfp_response(request)


@router.get(
    "/capabilities",
    response_model=CapabilityCatalogResponse,
    summary="Platform capability catalog",
    description="Returns the full platform capability catalog with maturity levels.",
)
async def get_capabilities() -> CapabilityCatalogResponse:
    """Return the full capability catalog."""
    service = get_rfp_service()
    return service.get_capability_catalog()


@router.get(
    "/competitive-matrix",
    response_model=CompetitiveMatrixResponse,
    summary="Competitive positioning matrix",
    description=(
        "Returns the competitive positioning matrix comparing the platform "
        "against key competitors across multiple evaluation categories."
    ),
)
async def get_competitive_matrix() -> CompetitiveMatrixResponse:
    """Return the competitive positioning matrix."""
    service = get_rfp_service()
    return service.get_competitive_matrix()


@router.get(
    "/case-studies",
    response_model=CaseStudyListResponse,
    summary="Case study templates",
    description="Returns case study templates based on demo trial data.",
)
async def get_case_studies() -> CaseStudyListResponse:
    """Return all case study templates."""
    service = get_rfp_service()
    return service.get_case_studies()


@router.post(
    "/match-requirements",
    response_model=RequirementMatchResponse,
    summary="Match requirements to capabilities",
    description=(
        "Given a list of RFP requirements, matches each to platform "
        "capabilities with confidence scores and gap analysis."
    ),
)
async def match_requirements(
    request: RequirementMatchRequest,
) -> RequirementMatchResponse:
    """Match requirements to platform capabilities."""
    service = get_rfp_service()
    return service.match_requirements(request.requirements)
