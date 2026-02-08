"""EDC/CTMS Integration Roadmap API endpoints (Partnership-2).

Provides endpoints for viewing integration specifications, readiness
assessments, phased roadmap, data mapping templates, and overall
integration status summary for clinical trial system integrations.

Endpoints:
    GET /partnerships/integrations              - List all target integrations
    GET /partnerships/integrations/roadmap       - Phased integration roadmap
    GET /partnerships/integrations/summary       - Overall integration status
    GET /partnerships/integrations/{system}      - Integration detail
    GET /partnerships/integrations/{system}/readiness   - Readiness assessment
    GET /partnerships/integrations/{system}/data-mapping - Data mapping template
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.schemas.integration_roadmap import (
    DataMappingTemplate,
    IntegrationListResponse,
    IntegrationRoadmap,
    IntegrationSpec,
    IntegrationSummary,
    ReadinessAssessment,
)
from app.services.integration_roadmap_service import get_integration_roadmap_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/partnerships/integrations", tags=["Partnerships"])


@router.get(
    "",
    response_model=IntegrationListResponse,
    summary="List all target integrations",
    description=(
        "Returns all target clinical trial system integrations with their "
        "specifications including API types, data formats, authentication "
        "methods, and data domains."
    ),
)
async def list_integrations() -> IntegrationListResponse:
    """List all target integration systems."""
    service = get_integration_roadmap_service()
    return service.list_integrations()


@router.get(
    "/roadmap",
    response_model=IntegrationRoadmap,
    summary="Phased integration roadmap",
    description=(
        "Returns the complete phased integration roadmap with milestones, "
        "effort estimates, and delivery timeline across all four phases."
    ),
)
async def get_roadmap() -> IntegrationRoadmap:
    """Return the phased integration roadmap."""
    service = get_integration_roadmap_service()
    return service.get_roadmap()


@router.get(
    "/summary",
    response_model=IntegrationSummary,
    summary="Overall integration status summary",
    description=(
        "Returns a high-level summary of integration status including "
        "readiness scores, effort totals, capability gaps, and system "
        "categorization."
    ),
)
async def get_summary() -> IntegrationSummary:
    """Return overall integration status summary."""
    service = get_integration_roadmap_service()
    return service.get_summary()


@router.get(
    "/{system}",
    response_model=IntegrationSpec,
    summary="Integration detail for a specific system",
    description=(
        "Returns detailed integration specification for a target system "
        "including vendor, category, API patterns, data domains, and "
        "typical customers."
    ),
)
async def get_integration(system: str) -> IntegrationSpec:
    """Get integration specification for a specific system."""
    service = get_integration_roadmap_service()
    result = service.get_integration(system)
    if result is None:
        valid_systems = service.get_system_ids()
        raise HTTPException(
            status_code=404,
            detail=f"System '{system}' not found. Valid systems: {valid_systems}",
        )
    return result


@router.get(
    "/{system}/readiness",
    response_model=ReadinessAssessment,
    summary="Readiness assessment for a specific system",
    description=(
        "Returns integration readiness assessment showing per-capability "
        "status, overall readiness percentage, blockers, prerequisites, "
        "and recommended implementation phase."
    ),
)
async def get_readiness(system: str) -> ReadinessAssessment:
    """Get integration readiness assessment for a specific system."""
    service = get_integration_roadmap_service()
    result = service.assess_readiness(system)
    if result is None:
        valid_systems = service.get_system_ids()
        raise HTTPException(
            status_code=404,
            detail=f"System '{system}' not found. Valid systems: {valid_systems}",
        )
    return result


@router.get(
    "/{system}/data-mapping",
    response_model=list[DataMappingTemplate],
    summary="Data mapping template for a specific system",
    description=(
        "Returns data mapping templates showing field-level mappings "
        "between the platform schema and the target system, including "
        "transformation logic and coverage metrics."
    ),
)
async def get_data_mapping(system: str) -> list[DataMappingTemplate]:
    """Get data mapping templates for a specific system."""
    service = get_integration_roadmap_service()
    result = service.get_data_mapping(system)
    if result is None:
        valid_systems = service.get_system_ids()
        raise HTTPException(
            status_code=404,
            detail=f"System '{system}' not found. Valid systems: {valid_systems}",
        )
    return result
