"""Pydantic schemas for Infrastructure-as-Code Management (DEVOPS-1).

Defines schemas for Terraform module discovery, configuration validation,
cost estimation, and HIPAA compliance checking.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class IaCModuleStatus(str, Enum):
    """Status of an IaC module."""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    EXPERIMENTAL = "experimental"


class ValidationSeverity(str, Enum):
    """Severity of a validation finding."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ComplianceStatus(str, Enum):
    """HIPAA compliance status."""

    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    NOT_APPLICABLE = "not_applicable"


class EnvironmentTier(str, Enum):
    """Environment tier."""

    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


# ---------------------------------------------------------------------------
# Module Schemas
# ---------------------------------------------------------------------------


class IaCVariable(BaseModel):
    """A Terraform variable definition."""

    name: str = Field(..., description="Variable name")
    type: str = Field(default="string", description="Variable type (string, number, bool, list, map)")
    description: str = Field(default="", description="Variable description")
    default: Any = Field(default=None, description="Default value if any")
    required: bool = Field(default=True, description="Whether the variable is required")


class IaCOutput(BaseModel):
    """A Terraform output definition."""

    name: str = Field(..., description="Output name")
    description: str = Field(default="", description="Output description")
    sensitive: bool = Field(default=False, description="Whether the output is sensitive")


class IaCResource(BaseModel):
    """A Terraform resource definition."""

    type: str = Field(..., description="Resource type (e.g., aws_vpc, aws_rds_instance)")
    name: str = Field(..., description="Resource logical name")
    provider: str = Field(default="aws", description="Provider name")


class IaCModule(BaseModel):
    """A Terraform module definition."""

    name: str = Field(..., description="Module name")
    path: str = Field(..., description="Module path relative to terraform root")
    description: str = Field(default="", description="Module description")
    status: IaCModuleStatus = Field(default=IaCModuleStatus.ACTIVE)
    variables: list[IaCVariable] = Field(default_factory=list)
    outputs: list[IaCOutput] = Field(default_factory=list)
    resources: list[IaCResource] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list, description="Other modules this depends on")


class IaCModuleList(BaseModel):
    """List of IaC modules."""

    modules: list[IaCModule] = Field(default_factory=list)
    total_count: int = Field(default=0, ge=0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now())


# ---------------------------------------------------------------------------
# Validation Schemas
# ---------------------------------------------------------------------------


class ValidationFinding(BaseModel):
    """A single validation finding."""

    rule: str = Field(..., description="Validation rule identifier")
    severity: ValidationSeverity = Field(..., description="Finding severity")
    resource: str = Field(default="", description="Affected resource")
    message: str = Field(..., description="Human-readable description")
    remediation: str = Field(default="", description="Suggested remediation")


class ValidationResult(BaseModel):
    """Result of IaC configuration validation."""

    valid: bool = Field(..., description="Whether the configuration is valid")
    findings: list[ValidationFinding] = Field(default_factory=list)
    critical_count: int = Field(default=0, ge=0)
    high_count: int = Field(default=0, ge=0)
    medium_count: int = Field(default=0, ge=0)
    low_count: int = Field(default=0, ge=0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now())


class ValidationRequest(BaseModel):
    """Request to validate an IaC configuration."""

    environment: EnvironmentTier = Field(default=EnvironmentTier.DEV)
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration key-value pairs to validate",
    )


# ---------------------------------------------------------------------------
# Cost Estimation Schemas
# ---------------------------------------------------------------------------


class ResourceCost(BaseModel):
    """Estimated cost of a single resource."""

    resource_type: str = Field(..., description="AWS resource type")
    resource_name: str = Field(default="", description="Resource name")
    monthly_cost_usd: float = Field(..., ge=0, description="Estimated monthly cost in USD")
    hourly_cost_usd: float = Field(default=0.0, ge=0, description="Estimated hourly cost in USD")
    notes: str = Field(default="", description="Cost calculation notes")


class CostEstimate(BaseModel):
    """Cost estimation result."""

    environment: str = Field(..., description="Environment name")
    resources: list[ResourceCost] = Field(default_factory=list)
    total_monthly_usd: float = Field(default=0.0, ge=0)
    total_annual_usd: float = Field(default=0.0, ge=0)
    currency: str = Field(default="USD")
    disclaimer: str = Field(
        default="Estimates are approximate and may vary based on actual usage."
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now())


# ---------------------------------------------------------------------------
# Compliance Schemas
# ---------------------------------------------------------------------------


class ComplianceCheck(BaseModel):
    """A single HIPAA compliance check."""

    check_id: str = Field(..., description="Check identifier")
    category: str = Field(..., description="Check category")
    description: str = Field(..., description="What this check verifies")
    status: ComplianceStatus = Field(..., description="Compliance status")
    details: str = Field(default="", description="Additional details")
    hipaa_reference: str = Field(default="", description="HIPAA regulation reference")


class ComplianceReport(BaseModel):
    """HIPAA compliance report for IaC configuration."""

    environment: str = Field(..., description="Environment evaluated")
    overall_status: ComplianceStatus = Field(..., description="Overall compliance status")
    checks: list[ComplianceCheck] = Field(default_factory=list)
    compliant_count: int = Field(default=0, ge=0)
    non_compliant_count: int = Field(default=0, ge=0)
    partial_count: int = Field(default=0, ge=0)
    score_percent: float = Field(default=0.0, ge=0, le=100)
    timestamp: datetime = Field(default_factory=lambda: datetime.now())


# ---------------------------------------------------------------------------
# Environment Configuration Schemas
# ---------------------------------------------------------------------------


class EnvironmentConfig(BaseModel):
    """Configuration for a specific environment."""

    environment: EnvironmentTier = Field(..., description="Environment tier")
    region: str = Field(default="us-east-1")
    vpc_cidr: str = Field(default="10.0.0.0/16")
    db_instance_class: str = Field(default="db.t3.medium")
    db_allocated_storage: int = Field(default=20, ge=1)
    db_backup_retention: int = Field(default=1, ge=1, le=35)
    redis_node_type: str = Field(default="cache.t3.medium")
    redis_num_cache_nodes: int = Field(default=1, ge=1)
    ecs_cpu: int = Field(default=512, ge=256)
    ecs_memory: int = Field(default=1024, ge=512)
    ecs_desired_count: int = Field(default=1, ge=1)
    multi_az: bool = Field(default=False)
    encryption_enabled: bool = Field(default=True)


class EnvironmentConfigList(BaseModel):
    """List of environment configurations."""

    environments: list[EnvironmentConfig] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now())
