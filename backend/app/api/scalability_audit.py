"""Architecture Scalability Audit API endpoints (CTO-1).

Provides comprehensive scalability analysis, growth projections, database
analysis, and load simulation for the clinical trial platform.

Endpoints:
    GET  /architecture/scalability                    - Full scalability audit report
    GET  /architecture/scalability/components          - Per-component analysis
    GET  /architecture/scalability/components/{name}   - Single component detail
    GET  /architecture/scalability/projections          - Growth projections
    GET  /architecture/scalability/recommendations     - Prioritized recommendations
    GET  /architecture/scalability/database             - Database-specific analysis
    POST /architecture/scalability/simulate             - Simulate load at given patient count
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.permissions import Permission, PermissionChecker
from app.schemas.scalability_audit import (
    ComponentAnalysis,
    ComponentListResponse,
    DatabaseAnalysis,
    LoadSimulationRequest,
    LoadSimulationResult,
    RecommendationsResponse,
    ScalabilityReport,
    ScalingProjection,
)
from app.services.scalability_audit_service import get_scalability_audit_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/architecture/scalability",
    tags=["Architecture"],
)

# ---------------------------------------------------------------------------
# Permission dependency
# ---------------------------------------------------------------------------

_analytics_perm_checker = PermissionChecker([Permission.READ_ANALYTICS])


async def _require_analytics_perm(request: Request) -> None:
    return await _analytics_perm_checker(request)


# ---------------------------------------------------------------------------
# Full Report
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=ScalabilityReport,
    summary="Full scalability audit report",
    description=(
        "Returns a comprehensive architecture scalability audit including "
        "component analysis, scaling projections, database analysis, horizontal "
        "scaling readiness, and prioritized recommendations."
    ),
    dependencies=[Depends(_require_analytics_perm)],
)
async def get_scalability_report() -> ScalabilityReport:
    """Generate a full scalability audit report."""
    service = get_scalability_audit_service()
    return service.generate_full_report()


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------


@router.get(
    "/components",
    response_model=ComponentListResponse,
    summary="Per-component scalability analysis",
    description=(
        "Returns scalability analysis for all architectural components including "
        "PostgreSQL, Redis, Neo4j, FastAPI, NLP pipeline, FHIR import, trial "
        "screening, and knowledge graph."
    ),
    dependencies=[Depends(_require_analytics_perm)],
)
async def get_components() -> ComponentListResponse:
    """Return analysis for all components."""
    service = get_scalability_audit_service()
    components = service.analyze_all_components()
    return ComponentListResponse(
        timestamp=datetime.now(timezone.utc),
        components=components,
        total=len(components),
    )


@router.get(
    "/components/{name}",
    response_model=ComponentAnalysis,
    summary="Single component detail",
    description="Returns detailed scalability analysis for a single named component.",
    dependencies=[Depends(_require_analytics_perm)],
)
async def get_component_detail(name: str) -> ComponentAnalysis:
    """Return analysis for a single component."""
    service = get_scalability_audit_service()
    analysis = service.analyze_component(name)
    if analysis is None:
        available = service.get_component_names()
        raise HTTPException(
            status_code=404,
            detail=f"Component '{name}' not found. Available: {', '.join(available)}",
        )
    return analysis


# ---------------------------------------------------------------------------
# Projections
# ---------------------------------------------------------------------------


@router.get(
    "/projections",
    response_model=ScalingProjection,
    summary="Growth projections",
    description=(
        "Returns resource projections across patient-count tiers "
        "(1K, 10K, 100K, 1M) including compute, storage, network, and cost estimates."
    ),
    dependencies=[Depends(_require_analytics_perm)],
)
async def get_projections() -> ScalingProjection:
    """Return growth projections at standard patient tiers."""
    service = get_scalability_audit_service()
    return service.generate_projections()


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


@router.get(
    "/recommendations",
    response_model=RecommendationsResponse,
    summary="Prioritized recommendations",
    description=(
        "Returns prioritized scalability recommendations sorted by impact, "
        "including effort estimates and affected components."
    ),
    dependencies=[Depends(_require_analytics_perm)],
)
async def get_recommendations() -> RecommendationsResponse:
    """Return prioritized scalability recommendations."""
    service = get_scalability_audit_service()
    recommendations = service.generate_recommendations()
    return RecommendationsResponse(
        timestamp=datetime.now(timezone.utc),
        recommendations=recommendations,
        total=len(recommendations),
    )


# ---------------------------------------------------------------------------
# Database Analysis
# ---------------------------------------------------------------------------


@router.get(
    "/database",
    response_model=DatabaseAnalysis,
    summary="Database scalability analysis",
    description=(
        "Returns database-specific scalability analysis including table size "
        "projections, query performance analysis, index recommendations, "
        "and partitioning strategies."
    ),
    dependencies=[Depends(_require_analytics_perm)],
)
async def get_database_analysis() -> DatabaseAnalysis:
    """Return database scalability analysis."""
    service = get_scalability_audit_service()
    return service.analyze_database()


# ---------------------------------------------------------------------------
# Load Simulation
# ---------------------------------------------------------------------------


@router.post(
    "/simulate",
    response_model=LoadSimulationResult,
    summary="Simulate load at given patient count",
    description=(
        "Simulates the platform under a specified load scenario and returns "
        "resource estimates, identified bottlenecks, and required scaling actions."
    ),
    dependencies=[Depends(_require_analytics_perm)],
)
async def simulate_load(request: LoadSimulationRequest) -> LoadSimulationResult:
    """Simulate load at a given patient count."""
    service = get_scalability_audit_service()
    return service.simulate_load(request)
