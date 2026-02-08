"""Schemas for Model Governance & Lifecycle Management (VP-DS-8).

Provides structured types for ML model governance including:
- Risk tiering (patient-facing, clinical support, internal analytics)
- Governance status lifecycle (development -> validation -> approval -> deployment -> monitoring)
- Validation records (technical, clinical, regulatory)
- Approval workflows with role-based requirements
- Monitoring alerts (drift, performance degradation, fairness violations)
- Governance metrics and dashboards
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ModelRiskTier(str, Enum):
    """Risk tier classification for governed models."""

    TIER_1_HIGH = "tier_1_high"  # Patient-facing decisions
    TIER_2_MEDIUM = "tier_2_medium"  # Clinical support
    TIER_3_LOW = "tier_3_low"  # Internal analytics


class GovernanceStatus(str, Enum):
    """Lifecycle status of a governed model."""

    DEVELOPMENT = "development"
    VALIDATION = "validation"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    DEPLOYED = "deployed"
    MONITORING = "monitoring"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class GovernedModelType(str, Enum):
    """Type of ML model under governance."""

    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    NLP = "nlp"
    ENSEMBLE = "ensemble"


class ValidationType(str, Enum):
    """Type of validation performed on a model."""

    TECHNICAL = "technical"
    CLINICAL = "clinical"
    REGULATORY = "regulatory"


class ApprovalStatus(str, Enum):
    """Status of an approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class AlertType(str, Enum):
    """Type of monitoring alert."""

    DRIFT = "drift"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    FAIRNESS_VIOLATION = "fairness_violation"
    DATA_QUALITY = "data_quality"


class AlertSeverity(str, Enum):
    """Severity level of a monitoring alert."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Core model schemas
# ---------------------------------------------------------------------------


class GovernedModel(BaseModel):
    """A model under governance oversight."""

    id: str = Field(..., description="Unique model identifier")
    name: str = Field(..., description="Human-readable model name")
    version: str = Field(..., description="Model version string")
    description: str = Field(default="", description="Model description")
    model_type: GovernedModelType = Field(..., description="Type of ML model")
    risk_tier: ModelRiskTier = Field(..., description="Risk tier classification")
    status: GovernanceStatus = Field(
        default=GovernanceStatus.DEVELOPMENT, description="Current governance status"
    )
    owner: str = Field(..., description="Model owner (person or team)")
    team: str = Field(default="", description="Owning team")
    training_data_hash: str = Field(
        default="", description="Hash of training data for reproducibility"
    )
    performance_metrics: dict[str, Any] = Field(
        default_factory=dict, description="Model performance metrics (accuracy, AUC, etc.)"
    )
    fairness_metrics: dict[str, Any] = Field(
        default_factory=dict, description="Fairness metrics (demographic parity, etc.)"
    )
    validation_date: datetime | None = Field(
        None, description="Date of last validation"
    )
    approved_by: str | None = Field(None, description="Final approver")
    approval_date: datetime | None = Field(None, description="Date of approval")
    deployment_date: datetime | None = Field(None, description="Date of deployment")
    monitoring_config: dict[str, Any] = Field(
        default_factory=dict, description="Monitoring configuration"
    )
    review_frequency_days: int = Field(
        default=90, ge=1, description="Days between mandatory reviews"
    )
    next_review_date: datetime | None = Field(
        None, description="Next scheduled review date"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update timestamp",
    )


# ---------------------------------------------------------------------------
# Validation records
# ---------------------------------------------------------------------------


class ModelValidationRecord(BaseModel):
    """Record of a model validation event."""

    id: str = Field(..., description="Unique validation record identifier")
    model_id: str = Field(..., description="ID of the validated model")
    validation_type: ValidationType = Field(..., description="Type of validation")
    validator: str = Field(..., description="Person or system performing validation")
    date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Validation date",
    )
    passed: bool = Field(..., description="Whether validation passed")
    metrics: dict[str, Any] = Field(
        default_factory=dict, description="Validation metrics"
    )
    findings: list[str] = Field(
        default_factory=list, description="Validation findings"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Recommendations from validation"
    )


# ---------------------------------------------------------------------------
# Approval workflow
# ---------------------------------------------------------------------------


class ModelApprovalRequest(BaseModel):
    """Approval request for a model to progress through governance."""

    id: str = Field(..., description="Unique approval request identifier")
    model_id: str = Field(..., description="ID of the model requesting approval")
    requested_by: str = Field(..., description="Person requesting approval")
    request_date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Date of approval request",
    )
    approvers_required: list[str] = Field(
        default_factory=list, description="Roles required to approve"
    )
    approvals_received: list[str] = Field(
        default_factory=list, description="Approvals received so far"
    )
    status: ApprovalStatus = Field(
        default=ApprovalStatus.PENDING, description="Current approval status"
    )
    comments: str = Field(default="", description="Comments on the approval request")


# ---------------------------------------------------------------------------
# Monitoring alerts
# ---------------------------------------------------------------------------


class ModelMonitoringAlert(BaseModel):
    """Alert from model monitoring."""

    id: str = Field(..., description="Unique alert identifier")
    model_id: str = Field(..., description="ID of the model that triggered the alert")
    alert_type: AlertType = Field(..., description="Type of alert")
    severity: AlertSeverity = Field(..., description="Alert severity level")
    message: str = Field(..., description="Alert message")
    detected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the alert was detected",
    )
    acknowledged: bool = Field(default=False, description="Whether alert is acknowledged")
    resolved_at: datetime | None = Field(None, description="When the alert was resolved")


# ---------------------------------------------------------------------------
# Governance metrics
# ---------------------------------------------------------------------------


class ModelGovernanceMetrics(BaseModel):
    """Aggregated governance metrics for the model portfolio."""

    total_models: int = Field(default=0, description="Total governed models")
    by_tier: dict[str, int] = Field(
        default_factory=dict, description="Models by risk tier"
    )
    by_status: dict[str, int] = Field(
        default_factory=dict, description="Models by governance status"
    )
    pending_approvals: int = Field(default=0, description="Number of pending approvals")
    overdue_reviews: int = Field(default=0, description="Number of overdue reviews")
    active_alerts: int = Field(default=0, description="Number of active (unresolved) alerts")
    avg_time_to_approval_days: float = Field(
        default=0.0, description="Average days from request to approval"
    )
    models_in_production: int = Field(
        default=0, description="Models currently deployed or monitoring"
    )
    deprecated_count: int = Field(default=0, description="Number of deprecated models")


# ---------------------------------------------------------------------------
# Request / Response wrappers
# ---------------------------------------------------------------------------


class GovernedModelCreate(BaseModel):
    """Request to register a new governed model."""

    name: str = Field(..., min_length=1, max_length=255, description="Model name")
    version: str = Field(..., min_length=1, max_length=50, description="Model version")
    description: str = Field(default="", description="Model description")
    model_type: GovernedModelType = Field(..., description="Type of ML model")
    risk_tier: ModelRiskTier = Field(..., description="Risk tier classification")
    owner: str = Field(..., min_length=1, description="Model owner")
    team: str = Field(default="", description="Owning team")
    training_data_hash: str = Field(default="", description="Training data hash")
    performance_metrics: dict[str, Any] = Field(
        default_factory=dict, description="Performance metrics"
    )
    fairness_metrics: dict[str, Any] = Field(
        default_factory=dict, description="Fairness metrics"
    )
    review_frequency_days: int = Field(default=90, ge=1, description="Review frequency")


class GovernedModelUpdate(BaseModel):
    """Request to update a governed model."""

    description: str | None = Field(None, description="Updated description")
    performance_metrics: dict[str, Any] | None = Field(None, description="Updated metrics")
    fairness_metrics: dict[str, Any] | None = Field(None, description="Updated fairness metrics")
    monitoring_config: dict[str, Any] | None = Field(None, description="Updated monitoring config")
    review_frequency_days: int | None = Field(None, ge=1, description="Updated review frequency")


class GovernedModelListResponse(BaseModel):
    """Response for listing governed models."""

    total: int = Field(..., description="Total number of models")
    models: list[GovernedModel] = Field(..., description="List of governed models")


class ValidationRecordListResponse(BaseModel):
    """Response for listing validation records."""

    total: int = Field(..., description="Total number of records")
    records: list[ModelValidationRecord] = Field(..., description="Validation records")


class ApprovalRequestListResponse(BaseModel):
    """Response for listing approval requests."""

    total: int = Field(..., description="Total number of requests")
    requests: list[ModelApprovalRequest] = Field(..., description="Approval requests")


class AlertListResponse(BaseModel):
    """Response for listing monitoring alerts."""

    total: int = Field(..., description="Total number of alerts")
    alerts: list[ModelMonitoringAlert] = Field(..., description="Monitoring alerts")


class SubmitValidationRequest(BaseModel):
    """Request to submit a model for validation."""

    validation_type: ValidationType = Field(..., description="Type of validation")
    validator: str = Field(..., min_length=1, description="Validator name or system")


class ApproveModelRequest(BaseModel):
    """Request to approve a model."""

    approver: str = Field(..., min_length=1, description="Approver name")
    role: str = Field(default="reviewer", description="Approver role")
    comments: str = Field(default="", description="Approval comments")


class RecordAlertRequest(BaseModel):
    """Request to record a monitoring alert."""

    alert_type: AlertType = Field(..., description="Type of alert")
    severity: AlertSeverity = Field(..., description="Alert severity")
    message: str = Field(..., min_length=1, description="Alert message")


class ModelHistoryResponse(BaseModel):
    """Aggregated history for a model including validations and alerts."""

    model_id: str = Field(..., description="Model ID")
    model_name: str = Field(..., description="Model name")
    validations: list[ModelValidationRecord] = Field(
        default_factory=list, description="Validation history"
    )
    alerts: list[ModelMonitoringAlert] = Field(
        default_factory=list, description="Alert history"
    )
    approval_requests: list[ModelApprovalRequest] = Field(
        default_factory=list, description="Approval request history"
    )
