"""Pydantic schemas for Release Management & Deployment Tracking.

VPE-8: Release lifecycle management, deployment tracking with blue-green/canary
support, release gates, rollback capabilities, and DORA metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Release Enumerations
# ---------------------------------------------------------------------------


class ReleaseStatus(str, Enum):
    """Release lifecycle status."""

    PLANNING = "PLANNING"
    DEVELOPMENT = "DEVELOPMENT"
    CODE_FREEZE = "CODE_FREEZE"
    TESTING = "TESTING"
    STAGING = "STAGING"
    APPROVED = "APPROVED"
    DEPLOYING = "DEPLOYING"
    DEPLOYED = "DEPLOYED"
    ROLLED_BACK = "ROLLED_BACK"
    CANCELLED = "CANCELLED"


class ReleaseType(str, Enum):
    """Semantic versioning release type."""

    MAJOR = "MAJOR"
    MINOR = "MINOR"
    PATCH = "PATCH"
    HOTFIX = "HOTFIX"


class Environment(str, Enum):
    """Deployment target environment."""

    DEVELOPMENT = "DEVELOPMENT"
    STAGING = "STAGING"
    PRODUCTION = "PRODUCTION"
    DR_SITE = "DR_SITE"


class DeploymentType(str, Enum):
    """Deployment strategy type."""

    BLUE_GREEN = "BLUE_GREEN"
    CANARY = "CANARY"
    ROLLING = "ROLLING"
    HOTFIX = "HOTFIX"
    ROLLBACK = "ROLLBACK"


class DeploymentStatus(str, Enum):
    """Deployment execution status."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class GateName(str, Enum):
    """Release gate checkpoint name."""

    CODE_REVIEW = "CODE_REVIEW"
    QA_SIGN_OFF = "QA_SIGN_OFF"
    SECURITY_SCAN = "SECURITY_SCAN"
    PERFORMANCE_TEST = "PERFORMANCE_TEST"
    COMPLIANCE_REVIEW = "COMPLIANCE_REVIEW"
    STAKEHOLDER_APPROVAL = "STAKEHOLDER_APPROVAL"


class GateStatus(str, Enum):
    """Release gate evaluation status."""

    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    WAIVED = "WAIVED"


# ---------------------------------------------------------------------------
# Release
# ---------------------------------------------------------------------------


class Release(BaseModel):
    """A software release with version, features, and lifecycle status."""

    id: str = Field(description="Unique release identifier")
    version: str = Field(description="Semantic version string (e.g. 2.3.0)")
    title: str = Field(description="Human-readable release title")
    description: str | None = Field(
        default=None, description="Detailed release description"
    )
    status: ReleaseStatus = Field(description="Current release lifecycle status")
    release_type: ReleaseType = Field(description="Type of release (MAJOR/MINOR/PATCH/HOTFIX)")
    features: list[str] = Field(
        default_factory=list, description="Features included in this release"
    )
    bug_fixes: list[str] = Field(
        default_factory=list, description="Bug fixes included in this release"
    )
    breaking_changes: list[str] = Field(
        default_factory=list, description="Breaking changes in this release"
    )
    release_manager: str = Field(description="Person responsible for the release")
    planned_date: datetime | None = Field(
        default=None, description="Planned release date"
    )
    actual_date: datetime | None = Field(
        default=None, description="Actual release date"
    )
    changelog: str | None = Field(
        default=None, description="Formatted changelog text"
    )
    created_at: datetime = Field(description="When the release was created")
    updated_at: datetime = Field(description="When the release was last updated")

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Deployment
# ---------------------------------------------------------------------------


class Deployment(BaseModel):
    """A single deployment of a release to an environment."""

    id: str = Field(description="Unique deployment identifier")
    release_id: str = Field(description="ID of the release being deployed")
    environment: Environment = Field(description="Target deployment environment")
    deployment_type: DeploymentType = Field(description="Deployment strategy used")
    status: DeploymentStatus = Field(description="Current deployment status")
    deployed_by: str = Field(description="Person or system that triggered the deployment")
    started_at: datetime = Field(description="When the deployment started")
    completed_at: datetime | None = Field(
        default=None, description="When the deployment completed"
    )
    duration_seconds: float | None = Field(
        default=None, description="Total deployment duration in seconds"
    )
    health_check_passed: bool | None = Field(
        default=None, description="Whether post-deployment health check passed"
    )
    rollback_available: bool = Field(
        default=True, description="Whether rollback is available for this deployment"
    )
    rollback_to_version: str | None = Field(
        default=None, description="Version to rollback to if needed"
    )
    notes: str | None = Field(
        default=None, description="Deployment notes or comments"
    )

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Release Gate
# ---------------------------------------------------------------------------


class ReleaseGate(BaseModel):
    """A quality gate checkpoint for a release."""

    id: str = Field(description="Unique gate identifier")
    release_id: str = Field(description="ID of the release this gate belongs to")
    gate_name: GateName = Field(description="Gate checkpoint name")
    status: GateStatus = Field(description="Gate evaluation status")
    reviewer: str | None = Field(
        default=None, description="Person who reviewed this gate"
    )
    reviewed_at: datetime | None = Field(
        default=None, description="When the gate was reviewed"
    )
    comments: str | None = Field(
        default=None, description="Review comments"
    )

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Release Metrics (DORA)
# ---------------------------------------------------------------------------


class ReleaseMetrics(BaseModel):
    """DORA metrics and release statistics."""

    total_releases: int = Field(description="Total number of releases")
    deployment_frequency_per_month: float = Field(
        description="Average deployments per month"
    )
    mean_lead_time_days: float = Field(
        description="Mean lead time from planning to deployment in days"
    )
    change_failure_rate_pct: float = Field(
        description="Percentage of deployments that failed or were rolled back"
    )
    mean_time_to_recovery_minutes: float = Field(
        description="Mean time to recovery from failures in minutes"
    )
    by_type: dict[str, int] = Field(
        default_factory=dict, description="Release count by type"
    )
    by_status: dict[str, int] = Field(
        default_factory=dict, description="Release count by status"
    )
    rollback_count: int = Field(
        default=0, description="Total number of rollbacks"
    )
    hotfix_count: int = Field(
        default=0, description="Total number of hotfixes"
    )


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------


class ReleaseCreate(BaseModel):
    """Request schema for creating a new release."""

    version: str = Field(
        ..., min_length=1, max_length=50, description="Semantic version (e.g. 2.3.0)"
    )
    title: str = Field(
        ..., min_length=1, max_length=500, description="Release title"
    )
    description: str | None = Field(
        default=None, description="Detailed release description"
    )
    release_type: ReleaseType = Field(..., description="Type of release")
    features: list[str] = Field(
        default_factory=list, description="Features in this release"
    )
    bug_fixes: list[str] = Field(
        default_factory=list, description="Bug fixes in this release"
    )
    breaking_changes: list[str] = Field(
        default_factory=list, description="Breaking changes"
    )
    release_manager: str = Field(
        ..., min_length=1, description="Person responsible for the release"
    )
    planned_date: datetime | None = Field(
        default=None, description="Planned release date"
    )


class ReleaseUpdate(BaseModel):
    """Request schema for updating a release."""

    title: str | None = Field(default=None, max_length=500, description="Updated title")
    description: str | None = Field(
        default=None, description="Updated description"
    )
    status: ReleaseStatus | None = Field(
        default=None, description="Updated status"
    )
    features: list[str] | None = Field(
        default=None, description="Updated features list"
    )
    bug_fixes: list[str] | None = Field(
        default=None, description="Updated bug fixes list"
    )
    breaking_changes: list[str] | None = Field(
        default=None, description="Updated breaking changes"
    )
    planned_date: datetime | None = Field(
        default=None, description="Updated planned date"
    )
    changelog: str | None = Field(
        default=None, description="Updated changelog text"
    )


class DeployRequest(BaseModel):
    """Request to deploy a release to an environment."""

    environment: Environment = Field(..., description="Target environment")
    deployment_type: DeploymentType = Field(
        default=DeploymentType.BLUE_GREEN, description="Deployment strategy"
    )
    deployed_by: str = Field(
        ..., min_length=1, description="Person or system deploying"
    )
    notes: str | None = Field(default=None, description="Deployment notes")


class GateUpdateRequest(BaseModel):
    """Request to update a release gate status."""

    status: GateStatus = Field(..., description="New gate status")
    reviewer: str = Field(..., min_length=1, description="Person reviewing")
    comments: str | None = Field(default=None, description="Review comments")


class RollbackRequest(BaseModel):
    """Request to rollback a deployment."""

    rolled_back_by: str = Field(
        ..., min_length=1, description="Person initiating rollback"
    )
    reason: str | None = Field(default=None, description="Reason for rollback")


# ---------------------------------------------------------------------------
# Response Wrappers
# ---------------------------------------------------------------------------


class ReleaseListResponse(BaseModel):
    """Paginated list of releases."""

    releases: list[Release]
    total: int
    limit: int
    offset: int


class DeploymentListResponse(BaseModel):
    """List of deployments."""

    deployments: list[Deployment]
    total: int


class ReleaseGateListResponse(BaseModel):
    """List of release gates."""

    gates: list[ReleaseGate]
    total: int


class ReleaseReadinessResponse(BaseModel):
    """Release readiness check result."""

    release_id: str
    version: str
    ready: bool
    gates: list[ReleaseGate]
    passed_count: int
    total_count: int
    blocking_gates: list[str] = Field(
        default_factory=list,
        description="Gate names that are blocking the release",
    )


class ReleaseHistoryEntry(BaseModel):
    """A release with its deployment summary."""

    release: Release
    deployments: list[Deployment] = Field(default_factory=list)
    gates_passed: int = Field(default=0)
    gates_total: int = Field(default=0)


class ReleaseHistoryResponse(BaseModel):
    """Recent release history with deployment details."""

    entries: list[ReleaseHistoryEntry]
    total: int
