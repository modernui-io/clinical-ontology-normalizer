"""Infrastructure API endpoints (VPE-6).

Provides production infrastructure monitoring, Docker Compose analysis,
deployment readiness, and configuration validation endpoints.

Endpoints:
    GET  /infrastructure/health               - All service health status
    GET  /infrastructure/health/{service}      - Single service detail
    GET  /infrastructure/resources             - Resource utilization
    GET  /infrastructure/readiness             - Deployment readiness check
    POST /infrastructure/validate-compose      - Validate compose file structure
    GET  /infrastructure/compose-analysis      - Analyze current docker-compose
    GET  /infrastructure/dependencies          - Service dependency graph
    GET  /infrastructure/recommendations       - Infrastructure recommendations
"""

import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.schemas.infrastructure import (
    AllServicesHealth,
    ComposeAnalysis,
    DeploymentReadiness,
    DependencyGraph,
    InfrastructureRecommendation,
    ResourceUtilization,
    ServiceHealth,
)
from app.services.compose_analyzer_service import get_compose_analyzer
from app.services.infrastructure_service import get_infrastructure_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/infrastructure",
    tags=["Infrastructure"],
)


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/health",
    response_model=AllServicesHealth,
    summary="Get all service health status",
)
async def get_all_health() -> AllServicesHealth:
    """Return aggregated health status for all infrastructure services."""
    svc = get_infrastructure_service()
    return svc.get_all_health()


@router.get(
    "/health/{service}",
    response_model=ServiceHealth,
    summary="Get single service health",
)
async def get_service_health(service: str) -> ServiceHealth:
    """Return health status for a specific service.

    Args:
        service: Service name (e.g. postgres, redis, backend).
    """
    svc = get_infrastructure_service()
    try:
        return svc.get_service_health(service)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Service '{service}' not found",
        )


# ---------------------------------------------------------------------------
# Resource utilization
# ---------------------------------------------------------------------------


@router.get(
    "/resources",
    response_model=ResourceUtilization,
    summary="Get resource utilization",
)
async def get_resources() -> ResourceUtilization:
    """Return simulated resource utilization for all services."""
    svc = get_infrastructure_service()
    return svc.get_resource_utilization()


# ---------------------------------------------------------------------------
# Deployment readiness
# ---------------------------------------------------------------------------


@router.get(
    "/readiness",
    response_model=DeploymentReadiness,
    summary="Check deployment readiness",
)
async def check_readiness() -> DeploymentReadiness:
    """Assess deployment readiness across all services and dependencies."""
    svc = get_infrastructure_service()
    return svc.check_deployment_readiness()


# ---------------------------------------------------------------------------
# Compose analysis
# ---------------------------------------------------------------------------


@router.post(
    "/validate-compose",
    response_model=ComposeAnalysis,
    summary="Validate compose file structure",
)
async def validate_compose(compose_data: dict[str, Any]) -> ComposeAnalysis:
    """Validate a Docker Compose configuration passed as JSON.

    The request body should be the parsed YAML content of a docker-compose file.
    """
    analyzer = get_compose_analyzer()
    return analyzer.analyze_dict(compose_data)


@router.get(
    "/compose-analysis",
    response_model=ComposeAnalysis,
    summary="Analyze current docker-compose",
)
async def analyze_compose() -> ComposeAnalysis:
    """Analyze the project's docker-compose.prod.yml file."""
    analyzer = get_compose_analyzer()

    # Look for docker-compose.prod.yml relative to project root
    # Walk up from backend/app/api to find the project root
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(current_dir))
    )
    compose_path = os.path.join(project_root, "docker-compose.prod.yml")

    if not os.path.exists(compose_path):
        raise HTTPException(
            status_code=404,
            detail="docker-compose.prod.yml not found",
        )

    return analyzer.analyze_file(compose_path)


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


@router.get(
    "/dependencies",
    response_model=DependencyGraph,
    summary="Get service dependency graph",
)
async def get_dependencies() -> DependencyGraph:
    """Return the service dependency graph with startup order."""
    svc = get_infrastructure_service()
    return svc.get_dependency_graph()


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


@router.get(
    "/recommendations",
    response_model=list[InfrastructureRecommendation],
    summary="Get infrastructure recommendations",
)
async def get_recommendations() -> list[InfrastructureRecommendation]:
    """Return prioritized infrastructure improvement recommendations."""
    svc = get_infrastructure_service()
    return svc.get_recommendations()
