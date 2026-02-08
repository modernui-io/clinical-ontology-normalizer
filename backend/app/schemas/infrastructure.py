"""Pydantic schemas for Production Infrastructure (VPE-6).

Defines schemas for service health tracking, resource utilization,
deployment readiness, Docker Compose analysis, and infrastructure
compliance scoring.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ServiceStatus(str, Enum):
    """Health status of an individual service."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ComplianceSeverity(str, Enum):
    """Severity of a compose compliance finding."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class ReadinessStatus(str, Enum):
    """Overall deployment readiness verdict."""

    READY = "ready"
    NOT_READY = "not_ready"
    DEGRADED = "degraded"


# ---------------------------------------------------------------------------
# Service Health
# ---------------------------------------------------------------------------


class HealthCheckResult(BaseModel):
    """Result of a single health check probe."""

    last_check: datetime = Field(..., description="When the last check was performed")
    response_time_ms: float = Field(..., ge=0, description="Response time in milliseconds")
    consecutive_failures: int = Field(default=0, ge=0, description="Number of consecutive failures")
    message: str = Field(default="", description="Optional diagnostic message")


class ServiceHealth(BaseModel):
    """Health status of a single infrastructure service."""

    name: str = Field(..., description="Service name (e.g. postgres, redis)")
    status: ServiceStatus = Field(..., description="Current health status")
    health_check: HealthCheckResult | None = Field(None, description="Latest health check result")
    version: str | None = Field(None, description="Service version if known")
    uptime_seconds: float | None = Field(None, ge=0, description="Service uptime in seconds")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class AllServicesHealth(BaseModel):
    """Aggregated health of all services."""

    timestamp: datetime = Field(..., description="When this snapshot was taken")
    overall_status: ServiceStatus = Field(..., description="Worst-case status across all services")
    services: list[ServiceHealth] = Field(default_factory=list, description="Per-service health")
    healthy_count: int = Field(default=0, ge=0)
    degraded_count: int = Field(default=0, ge=0)
    unhealthy_count: int = Field(default=0, ge=0)


# ---------------------------------------------------------------------------
# Resource Utilization
# ---------------------------------------------------------------------------


class ServiceResourceUsage(BaseModel):
    """Simulated resource utilization for one service."""

    service: str = Field(..., description="Service name")
    cpu_percent: float = Field(default=0.0, ge=0, le=100, description="CPU usage percentage")
    memory_mb: float = Field(default=0.0, ge=0, description="Memory usage in MB")
    memory_limit_mb: float = Field(default=0.0, ge=0, description="Memory limit in MB")
    memory_percent: float = Field(default=0.0, ge=0, le=100, description="Memory usage percentage")
    disk_usage_mb: float = Field(default=0.0, ge=0, description="Disk usage in MB")
    network_rx_bytes: int = Field(default=0, ge=0, description="Network bytes received")
    network_tx_bytes: int = Field(default=0, ge=0, description="Network bytes transmitted")


class ConnectionPoolStats(BaseModel):
    """Connection pool utilization."""

    service: str = Field(..., description="Service name (e.g. postgres, redis)")
    active_connections: int = Field(default=0, ge=0)
    idle_connections: int = Field(default=0, ge=0)
    max_connections: int = Field(default=0, ge=0)
    utilization_percent: float = Field(default=0.0, ge=0, le=100)


class ResourceUtilization(BaseModel):
    """Aggregated resource utilization across all services."""

    timestamp: datetime = Field(..., description="When this snapshot was taken")
    services: list[ServiceResourceUsage] = Field(default_factory=list)
    connection_pools: list[ConnectionPoolStats] = Field(default_factory=list)
    total_cpu_percent: float = Field(default=0.0, ge=0)
    total_memory_mb: float = Field(default=0.0, ge=0)


# ---------------------------------------------------------------------------
# Service Dependencies
# ---------------------------------------------------------------------------


class ServiceDependency(BaseModel):
    """A dependency relationship between two services."""

    source: str = Field(..., description="Service that depends on another")
    target: str = Field(..., description="Service that is depended upon")
    dependency_type: str = Field(default="required", description="required | optional")
    port: int | None = Field(None, description="Network port used")
    protocol: str | None = Field(None, description="Protocol (e.g. tcp, http)")


class DependencyGraph(BaseModel):
    """Full service dependency graph."""

    services: list[str] = Field(default_factory=list, description="All service names")
    dependencies: list[ServiceDependency] = Field(default_factory=list)
    startup_order: list[str] = Field(default_factory=list, description="Correct startup order")
    has_circular_dependencies: bool = Field(default=False)
    circular_chains: list[list[str]] = Field(default_factory=list, description="Circular dependency chains if any")


# ---------------------------------------------------------------------------
# Configuration Validation
# ---------------------------------------------------------------------------


class ConfigValidationIssue(BaseModel):
    """A single configuration validation issue."""

    service: str = Field(..., description="Service with the issue")
    category: str = Field(..., description="Category: env_vars | ports | volumes | secrets")
    severity: ComplianceSeverity = Field(..., description="Issue severity")
    message: str = Field(..., description="Human-readable issue description")


class ConfigValidationResult(BaseModel):
    """Result of configuration validation."""

    valid: bool = Field(..., description="Whether configuration is valid")
    issues: list[ConfigValidationIssue] = Field(default_factory=list)
    checked_services: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(..., description="When validation was performed")


# ---------------------------------------------------------------------------
# Deployment Readiness
# ---------------------------------------------------------------------------


class ReadinessCheck(BaseModel):
    """Individual readiness check."""

    name: str = Field(..., description="Check name")
    passed: bool = Field(..., description="Whether the check passed")
    message: str = Field(default="", description="Diagnostic message")
    required: bool = Field(default=True, description="Whether this check is required")


class DeploymentReadiness(BaseModel):
    """Overall deployment readiness assessment."""

    status: ReadinessStatus = Field(..., description="Readiness verdict")
    timestamp: datetime = Field(..., description="When readiness was assessed")
    checks: list[ReadinessCheck] = Field(default_factory=list)
    passed_count: int = Field(default=0, ge=0)
    failed_count: int = Field(default=0, ge=0)
    total_count: int = Field(default=0, ge=0)
    blocking_issues: list[str] = Field(default_factory=list, description="Issues preventing deployment")


# ---------------------------------------------------------------------------
# Docker Compose Analysis
# ---------------------------------------------------------------------------


class ComposeRecommendation(BaseModel):
    """A single recommendation from compose analysis."""

    service: str = Field(..., description="Affected service")
    category: str = Field(..., description="Category of recommendation")
    severity: ComplianceSeverity = Field(..., description="Severity level")
    current_value: str | None = Field(None, description="Current configuration value")
    recommended_value: str | None = Field(None, description="Recommended value")
    message: str = Field(..., description="Human-readable recommendation")


class ComposeServiceAnalysis(BaseModel):
    """Analysis result for a single compose service."""

    service: str = Field(..., description="Service name")
    has_resource_limits: bool = Field(default=False)
    has_restart_policy: bool = Field(default=False)
    has_health_check: bool = Field(default=False)
    has_logging_config: bool = Field(default=False)
    has_security_directives: bool = Field(default=False)
    has_network_isolation: bool = Field(default=True)
    has_host_volume_mounts: bool = Field(default=False)
    uses_env_secrets: bool = Field(default=True)
    image_pinned: bool = Field(default=True)
    issues: list[str] = Field(default_factory=list)


class ComplianceScore(BaseModel):
    """Overall compliance score for a compose configuration."""

    score: float = Field(..., ge=0, le=100, description="Overall compliance percentage")
    max_score: float = Field(default=100.0, description="Maximum possible score")
    category_scores: dict[str, float] = Field(
        default_factory=dict, description="Score per category"
    )
    grade: str = Field(..., description="Letter grade: A, B, C, D, F")


class ComposeAnalysis(BaseModel):
    """Complete Docker Compose analysis result."""

    timestamp: datetime = Field(..., description="When analysis was performed")
    file_path: str | None = Field(None, description="Path to analyzed compose file")
    services_analyzed: int = Field(default=0, ge=0)
    service_analyses: list[ComposeServiceAnalysis] = Field(default_factory=list)
    recommendations: list[ComposeRecommendation] = Field(default_factory=list)
    compliance: ComplianceScore = Field(..., description="Overall compliance score")


# ---------------------------------------------------------------------------
# Infrastructure Report
# ---------------------------------------------------------------------------


class InfrastructureRecommendation(BaseModel):
    """An infrastructure improvement recommendation."""

    category: str = Field(..., description="Recommendation category")
    priority: str = Field(..., description="Priority: high, medium, low")
    title: str = Field(..., description="Short title")
    description: str = Field(..., description="Detailed description")
    impact: str = Field(default="", description="Expected impact of implementing")


class InfrastructureReport(BaseModel):
    """Comprehensive infrastructure report."""

    timestamp: datetime = Field(..., description="Report generation time")
    health: AllServicesHealth
    resources: ResourceUtilization
    readiness: DeploymentReadiness
    compose_analysis: ComposeAnalysis | None = Field(None)
    recommendations: list[InfrastructureRecommendation] = Field(default_factory=list)
