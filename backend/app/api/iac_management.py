"""Infrastructure-as-Code Management API endpoints (DEVOPS-1).

Provides endpoints for discovering Terraform modules, validating
configurations, estimating costs, and checking HIPAA compliance
for the clinical trial platform infrastructure.

Endpoints:
    GET   /infrastructure/iac/modules           - List all Terraform modules
    GET   /infrastructure/iac/modules/{name}    - Get module detail
    GET   /infrastructure/iac/environments      - List environment configurations
    POST  /infrastructure/iac/validate          - Validate configuration
    GET   /infrastructure/iac/cost-estimate     - Estimate infrastructure costs
    GET   /infrastructure/iac/compliance        - Run HIPAA compliance checks
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas.iac_management import (
    ComplianceReport,
    CostEstimate,
    EnvironmentConfigList,
    IaCModule,
    IaCModuleList,
    ValidationRequest,
    ValidationResult,
)
from app.services.iac_service import get_iac_validation_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/infrastructure/iac",
    tags=["Infrastructure IaC"],
)


# ---------------------------------------------------------------------------
# Module Discovery
# ---------------------------------------------------------------------------


@router.get(
    "/modules",
    response_model=IaCModuleList,
    summary="List all Terraform modules",
    description="Discover all Terraform modules in the infrastructure directory.",
)
async def list_modules() -> IaCModuleList:
    """List all Terraform modules with their variables, outputs, and resources."""
    svc = get_iac_validation_service()
    return svc.list_modules()


@router.get(
    "/modules/{name}",
    response_model=IaCModule,
    summary="Get module detail",
    description="Get detailed information about a specific Terraform module.",
)
async def get_module(name: str) -> IaCModule:
    """Get a specific Terraform module by name."""
    svc = get_iac_validation_service()
    module = svc.get_module(name)
    if module is None:
        raise HTTPException(
            status_code=404,
            detail=f"Module '{name}' not found",
        )
    return module


# ---------------------------------------------------------------------------
# Environment Configurations
# ---------------------------------------------------------------------------


@router.get(
    "/environments",
    response_model=EnvironmentConfigList,
    summary="List environment configurations",
    description="Get configuration values for all environments (dev, staging, prod).",
)
async def list_environments() -> EnvironmentConfigList:
    """List all environment configurations parsed from tfvars files."""
    svc = get_iac_validation_service()
    return svc.get_environment_configs()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@router.post(
    "/validate",
    response_model=ValidationResult,
    summary="Validate IaC configuration",
    description=(
        "Validate the Terraform configuration against security, operational, "
        "and compliance rules."
    ),
)
async def validate_configuration(
    request: ValidationRequest,
) -> ValidationResult:
    """Validate IaC configuration and return findings."""
    svc = get_iac_validation_service()
    return svc.validate_configuration(
        environment=request.environment.value,
        config=request.config,
    )


# ---------------------------------------------------------------------------
# Cost Estimation
# ---------------------------------------------------------------------------


@router.get(
    "/cost-estimate",
    response_model=CostEstimate,
    summary="Estimate infrastructure costs",
    description="Get estimated monthly and annual costs for the specified environment.",
)
async def get_cost_estimate(
    environment: str = Query(
        default="dev",
        description="Environment to estimate costs for (dev, staging, prod)",
    ),
) -> CostEstimate:
    """Estimate infrastructure costs for the specified environment."""
    if environment not in ("dev", "staging", "prod"):
        raise HTTPException(
            status_code=400,
            detail="Environment must be one of: dev, staging, prod",
        )
    svc = get_iac_validation_service()
    return svc.estimate_costs(environment=environment)


# ---------------------------------------------------------------------------
# Compliance
# ---------------------------------------------------------------------------


@router.get(
    "/compliance",
    response_model=ComplianceReport,
    summary="HIPAA compliance check",
    description=(
        "Run HIPAA compliance checks against the IaC configuration "
        "and return a detailed report."
    ),
)
async def check_compliance(
    environment: str = Query(
        default="dev",
        description="Environment to check compliance for (dev, staging, prod)",
    ),
) -> ComplianceReport:
    """Run HIPAA compliance checks against the IaC configuration."""
    if environment not in ("dev", "staging", "prod"):
        raise HTTPException(
            status_code=400,
            detail="Environment must be one of: dev, staging, prod",
        )
    svc = get_iac_validation_service()
    return svc.check_compliance(environment=environment)
