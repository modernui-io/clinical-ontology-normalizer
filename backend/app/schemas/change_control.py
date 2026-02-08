"""Pydantic schemas for Change Control and Configuration Management.

VP-Quality-4: Formal change request lifecycle, approval workflows,
configuration baselines, and drift detection.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Change Request Enumerations
# ---------------------------------------------------------------------------


class ChangeType(str, Enum):
    """Type of change request."""

    ENHANCEMENT = "ENHANCEMENT"
    BUG_FIX = "BUG_FIX"
    CONFIGURATION = "CONFIGURATION"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    REGULATORY = "REGULATORY"


class RiskLevel(str, Enum):
    """Risk level classification determining approval requirements."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ChangeStatus(str, Enum):
    """Change request lifecycle status."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    IMPACT_ASSESSED = "IMPACT_ASSESSED"
    APPROVED = "APPROVED"
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    TESTING = "TESTING"
    DEPLOYED = "DEPLOYED"
    VERIFIED = "VERIFIED"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"
    ROLLED_BACK = "ROLLED_BACK"


class ApproverRole(str, Enum):
    """Role of an approver in the approval chain."""

    TEAM_LEAD = "TEAM_LEAD"
    QA = "QA"
    COMPLIANCE = "COMPLIANCE"
    EXECUTIVE = "EXECUTIVE"


# ---------------------------------------------------------------------------
# Impact Assessment
# ---------------------------------------------------------------------------


class ImpactAssessment(BaseModel):
    """Impact assessment template for change requests."""

    affected_systems: list[str] = Field(
        default_factory=list,
        description="List of systems/services affected by the change",
    )
    patient_data_impact: bool = Field(
        default=False, description="Whether the change impacts PHI/patient data"
    )
    phi_details: str | None = Field(
        default=None,
        description="Details of PHI impact if applicable",
    )
    regulatory_impact: bool = Field(
        default=False, description="Whether the change requires re-validation"
    )
    regulatory_details: str | None = Field(
        default=None,
        description="Details of regulatory impact if applicable",
    )
    performance_impact: str | None = Field(
        default=None,
        description="Expected performance impact description",
    )
    rollback_complexity: str = Field(
        default="LOW",
        description="Complexity of rollback: LOW, MEDIUM, HIGH",
    )
    estimated_downtime_minutes: int = Field(
        default=0, description="Estimated downtime in minutes"
    )


# ---------------------------------------------------------------------------
# Approval Record
# ---------------------------------------------------------------------------


class ApprovalRecord(BaseModel):
    """Record of an approval or rejection in the approval chain."""

    approver: str = Field(description="Name/ID of the approver")
    role: ApproverRole = Field(description="Role of the approver")
    decision: str = Field(description="APPROVED or REJECTED")
    comment: str | None = Field(default=None, description="Optional comment")
    decided_at: datetime = Field(description="When the decision was made")


# ---------------------------------------------------------------------------
# Configuration Item
# ---------------------------------------------------------------------------


class ConfigurationItem(BaseModel):
    """A single configuration item in the inventory."""

    key: str = Field(description="Configuration key or identifier")
    value: str = Field(description="Current value")
    category: str = Field(
        default="general",
        description="Category: env_var, feature_flag, service_version, setting",
    )
    description: str | None = Field(
        default=None, description="Human-readable description"
    )
    sensitive: bool = Field(
        default=False, description="Whether value contains sensitive data"
    )


# ---------------------------------------------------------------------------
# Configuration Baseline
# ---------------------------------------------------------------------------


class ConfigurationBaseline(BaseModel):
    """Snapshot of all configuration at a point in time."""

    id: str = Field(description="Baseline unique identifier")
    name: str = Field(description="Human-readable baseline name")
    description: str | None = Field(default=None, description="Baseline description")
    captured_at: datetime = Field(description="When the baseline was captured")
    captured_by: str = Field(description="Who captured the baseline")
    items: list[ConfigurationItem] = Field(
        default_factory=list, description="Configuration items in this baseline"
    )
    environment: str = Field(
        default="production", description="Environment this baseline represents"
    )


# ---------------------------------------------------------------------------
# Configuration Drift
# ---------------------------------------------------------------------------


class DriftItem(BaseModel):
    """A single configuration drift detection result."""

    key: str = Field(description="Configuration key that drifted")
    baseline_value: str = Field(description="Value in the baseline")
    current_value: str = Field(description="Current value")
    category: str = Field(description="Configuration category")
    severity: str = Field(
        default="LOW", description="Drift severity: LOW, MEDIUM, HIGH"
    )


class DriftReport(BaseModel):
    """Configuration drift detection report."""

    baseline_id: str = Field(description="Baseline compared against")
    baseline_name: str = Field(description="Name of the baseline")
    checked_at: datetime = Field(description="When the drift check was performed")
    total_items: int = Field(description="Total configuration items checked")
    drifted_items: int = Field(description="Number of items that drifted")
    drift_percentage: float = Field(description="Percentage of items that drifted")
    drifts: list[DriftItem] = Field(
        default_factory=list, description="Individual drift details"
    )
    added_items: list[ConfigurationItem] = Field(
        default_factory=list,
        description="Items present in current config but not in baseline",
    )
    removed_keys: list[str] = Field(
        default_factory=list,
        description="Keys present in baseline but missing from current config",
    )


# ---------------------------------------------------------------------------
# Change Request Schemas
# ---------------------------------------------------------------------------


class ChangeRequestCreate(BaseModel):
    """Request schema for creating a new change request."""

    title: str = Field(..., min_length=1, max_length=500, description="Change title")
    description: str = Field(
        ..., min_length=1, description="Detailed change description"
    )
    change_type: ChangeType = Field(..., description="Type of change")
    risk_level: RiskLevel = Field(..., description="Risk level classification")
    requester: str = Field(..., min_length=1, description="Person requesting the change")
    assigned_to: str | None = Field(
        default=None, description="Person assigned to implement"
    )
    impact_assessment: ImpactAssessment | None = Field(
        default=None, description="Impact assessment"
    )
    rollback_plan: str | None = Field(
        default=None, description="Rollback plan description"
    )
    testing_requirements: str | None = Field(
        default=None, description="Testing requirements"
    )
    scheduled_date: datetime | None = Field(
        default=None, description="Scheduled deployment date"
    )


class ChangeRequestUpdate(BaseModel):
    """Request schema for updating a change request."""

    title: str | None = Field(default=None, max_length=500, description="Updated title")
    description: str | None = Field(
        default=None, description="Updated description"
    )
    status: ChangeStatus | None = Field(
        default=None, description="New status (state transition)"
    )
    risk_level: RiskLevel | None = Field(
        default=None, description="Updated risk level"
    )
    assigned_to: str | None = Field(
        default=None, description="Updated assignee"
    )
    impact_assessment: ImpactAssessment | None = Field(
        default=None, description="Updated impact assessment"
    )
    rollback_plan: str | None = Field(
        default=None, description="Updated rollback plan"
    )
    testing_requirements: str | None = Field(
        default=None, description="Updated testing requirements"
    )
    scheduled_date: datetime | None = Field(
        default=None, description="Updated scheduled date"
    )


class ChangeRequestResponse(BaseModel):
    """Full change request record response."""

    id: str
    title: str
    description: str
    change_type: ChangeType
    risk_level: RiskLevel
    requester: str
    assigned_to: str | None = None
    status: ChangeStatus
    impact_assessment: ImpactAssessment | None = None
    rollback_plan: str | None = None
    testing_requirements: str | None = None
    approval_chain: list[ApprovalRecord] = Field(default_factory=list)
    required_approvals: int = Field(
        default=1, description="Number of approvals required"
    )
    current_approvals: int = Field(
        default=0, description="Number of approvals received"
    )
    scheduled_date: datetime | None = None
    created_at: datetime
    updated_at: datetime
    deployed_at: datetime | None = None
    closed_at: datetime | None = None
    rolled_back_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChangeRequestListResponse(BaseModel):
    """Paginated list of change requests."""

    changes: list[ChangeRequestResponse]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Approval Schemas
# ---------------------------------------------------------------------------


class ApprovalRequest(BaseModel):
    """Request to approve a change."""

    approver: str = Field(..., min_length=1, description="Name/ID of the approver")
    role: ApproverRole = Field(..., description="Role of the approver")
    comment: str | None = Field(default=None, description="Optional approval comment")


class RejectionRequest(BaseModel):
    """Request to reject a change."""

    approver: str = Field(..., min_length=1, description="Name/ID of the rejector")
    role: ApproverRole = Field(..., description="Role of the rejector")
    reason: str = Field(
        ..., min_length=1, description="Reason for rejection"
    )


# ---------------------------------------------------------------------------
# Baseline Capture
# ---------------------------------------------------------------------------


class BaselineCaptureRequest(BaseModel):
    """Request to capture a configuration baseline."""

    name: str = Field(
        ..., min_length=1, max_length=200, description="Baseline name"
    )
    description: str | None = Field(
        default=None, description="Baseline description"
    )
    captured_by: str = Field(
        default="system", description="Who is capturing the baseline"
    )
    environment: str = Field(
        default="production", description="Environment to snapshot"
    )


class BaselineListResponse(BaseModel):
    """List of configuration baselines."""

    baselines: list[ConfigurationBaseline]
    total: int


# ---------------------------------------------------------------------------
# Change Metrics
# ---------------------------------------------------------------------------


class ChangeMetrics(BaseModel):
    """Change control dashboard metrics."""

    total_changes: int = Field(description="Total change request count")
    open_changes: int = Field(description="Non-closed/rejected change count")
    by_risk_level: dict[str, int] = Field(description="Count by risk level")
    by_status: dict[str, int] = Field(description="Count by status")
    by_type: dict[str, int] = Field(description="Count by change type")
    avg_time_to_deploy_hours: float = Field(
        description="Average hours from creation to deployment"
    )
    change_failure_rate: float = Field(
        description="Percentage of deployed changes that were rolled back"
    )
    rollback_rate: float = Field(
        description="Percentage of all changes that were rolled back"
    )
    pending_approvals: int = Field(
        description="Changes awaiting approval"
    )
    deployed_last_30_days: int = Field(
        description="Changes deployed in the last 30 days"
    )
