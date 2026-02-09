"""Pydantic schemas for Risk-Based Monitoring (RBM) & Central Monitoring (CLINICAL-7).

Manages risk-based monitoring operations: Key Risk Indicator (KRI) definitions,
site risk scoring with weighted aggregation, KRI data point tracking, monitoring
plan lifecycle (site initiation through close-out), monitoring finding management
with CAPA linkage, central monitoring alerts, and RBM operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class KRICategory(str, Enum):
    """Category of a Key Risk Indicator."""

    SAFETY = "safety"
    DATA_QUALITY = "data_quality"
    ENROLLMENT = "enrollment"
    PROTOCOL_COMPLIANCE = "protocol_compliance"
    SITE_MANAGEMENT = "site_management"


class RiskLevel(str, Enum):
    """Risk level classification for a site."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MonitoringAction(str, Enum):
    """Type of monitoring action triggered."""

    ROUTINE = "routine"
    TARGETED = "targeted"
    FOR_CAUSE = "for_cause"
    TRIGGERED = "triggered"


class FindingCategory(str, Enum):
    """Severity category for a monitoring finding."""

    MAJOR = "major"
    MINOR = "minor"
    CRITICAL = "critical"
    OBSERVATION = "observation"


class MonitoringVisitType(str, Enum):
    """Type of monitoring visit."""

    SITE_INITIATION = "site_initiation"
    INTERIM = "interim"
    CLOSE_OUT = "close_out"
    FOR_CAUSE = "for_cause"
    REMOTE = "remote"


class KRIStatus(str, Enum):
    """Traffic-light status for a KRI data point."""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class Trend(str, Enum):
    """Trend direction for site risk."""

    IMPROVING = "improving"
    STABLE = "stable"
    WORSENING = "worsening"


class MonitoringPlanStatus(str, Enum):
    """Status of a monitoring plan/visit."""

    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class FindingStatus(str, Enum):
    """Lifecycle status of a monitoring finding."""

    OPEN = "open"
    RESPONSE_REQUIRED = "response_required"
    RESOLVED = "resolved"
    VERIFIED = "verified"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class KeyRiskIndicator(BaseModel):
    """Definition of a Key Risk Indicator (KRI)."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique KRI identifier")
    name: str = Field(..., description="KRI name")
    category: KRICategory = Field(..., description="KRI category")
    description: str = Field(..., description="Detailed description of the KRI")
    threshold_yellow: float = Field(..., description="Threshold value for yellow/warning status")
    threshold_red: float = Field(..., description="Threshold value for red/critical status")
    unit: str = Field(..., description="Unit of measurement (e.g., %, days, count)")
    weight: float = Field(
        default=1.0, ge=0.0, le=10.0, description="Weight for risk score aggregation"
    )
    active: bool = Field(default=True, description="Whether this KRI is actively monitored")


class KRIScore(BaseModel):
    """Per-KRI score within a site risk profile."""

    model_config = ConfigDict(from_attributes=True)

    kri_id: str = Field(..., description="KRI identifier")
    kri_name: str = Field(..., description="KRI name")
    value: float = Field(..., description="Current KRI value")
    status: KRIStatus = Field(..., description="Traffic-light status")
    score: float = Field(ge=0.0, le=100.0, description="Normalized score (0-100)")


class SiteRiskScore(BaseModel):
    """Risk assessment for a clinical trial site."""

    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., description="Site identifier")
    site_name: str = Field(..., description="Site name")
    overall_risk_score: float = Field(
        ge=0.0, le=100.0, description="Aggregate risk score (0-100)"
    )
    risk_level: RiskLevel = Field(..., description="Classified risk level")
    kri_scores: list[KRIScore] = Field(
        default_factory=list, description="Per-KRI score breakdown"
    )
    last_assessed: datetime = Field(..., description="Date of last risk assessment")
    trend: Trend = Field(default=Trend.STABLE, description="Risk trend direction")


class KRIDataPoint(BaseModel):
    """A single KRI measurement for a site in a given period."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique data point identifier")
    kri_id: str = Field(..., description="Associated KRI identifier")
    site_id: str = Field(..., description="Site identifier")
    value: float = Field(..., description="Measured value")
    period: str = Field(..., description="Reporting period (YYYY-MM)")
    status: KRIStatus = Field(..., description="Traffic-light status based on thresholds")
    recorded_at: datetime = Field(..., description="When the data point was recorded")


class MonitoringPlan(BaseModel):
    """A monitoring plan/visit for a site."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique plan identifier")
    trial_id: str = Field(..., description="Trial identifier")
    site_id: str = Field(..., description="Site identifier")
    visit_type: MonitoringVisitType = Field(..., description="Type of monitoring visit")
    planned_date: datetime = Field(..., description="Planned visit date")
    actual_date: datetime | None = Field(None, description="Actual visit date")
    monitor_name: str = Field(..., description="Assigned monitor name")
    status: MonitoringPlanStatus = Field(
        default=MonitoringPlanStatus.PLANNED, description="Visit status"
    )
    findings_count: int = Field(default=0, ge=0, description="Number of findings from this visit")
    notes: str | None = Field(None, description="Visit notes")
    created_at: datetime = Field(..., description="Record creation timestamp")


class MonitoringFinding(BaseModel):
    """A finding from a monitoring visit."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique finding identifier")
    plan_id: str = Field(..., description="Associated monitoring plan ID")
    site_id: str = Field(..., description="Site identifier")
    category: FindingCategory = Field(..., description="Finding severity category")
    description: str = Field(..., description="Finding description")
    response_due_date: datetime = Field(..., description="Due date for site response")
    resolved_date: datetime | None = Field(None, description="Date the finding was resolved")
    capa_id: str | None = Field(None, description="Linked CAPA identifier")
    status: FindingStatus = Field(
        default=FindingStatus.OPEN, description="Finding lifecycle status"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")


class CentralMonitoringAlert(BaseModel):
    """An alert triggered by central monitoring of KRI thresholds."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique alert identifier")
    site_id: str = Field(..., description="Site that triggered the alert")
    kri_id: str = Field(..., description="KRI that was breached")
    triggered_date: datetime = Field(..., description="Date the alert was triggered")
    value: float = Field(..., description="KRI value at time of trigger")
    threshold_breached: str = Field(..., description="Which threshold was breached (yellow/red)")
    action_taken: MonitoringAction | None = Field(
        None, description="Monitoring action taken in response"
    )
    resolved: bool = Field(default=False, description="Whether the alert has been resolved")
    resolved_date: datetime | None = Field(None, description="Date the alert was resolved")
    notes: str | None = Field(None, description="Resolution notes")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class KRICreate(BaseModel):
    """Request to create a new Key Risk Indicator."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="KRI name")
    category: KRICategory = Field(..., description="KRI category")
    description: str = Field(..., description="Detailed description")
    threshold_yellow: float = Field(..., description="Yellow threshold")
    threshold_red: float = Field(..., description="Red threshold")
    unit: str = Field(..., description="Unit of measurement")
    weight: float = Field(default=1.0, ge=0.0, le=10.0, description="Aggregation weight")


class KRIUpdate(BaseModel):
    """Request to update a Key Risk Indicator."""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = Field(None, description="KRI name")
    description: str | None = Field(None, description="Description")
    threshold_yellow: float | None = Field(None, description="Yellow threshold")
    threshold_red: float | None = Field(None, description="Red threshold")
    unit: str | None = Field(None, description="Unit")
    weight: float | None = Field(None, ge=0.0, le=10.0, description="Weight")
    active: bool | None = Field(None, description="Active status")


class KRIDataPointCreate(BaseModel):
    """Request to submit a KRI data point."""

    model_config = ConfigDict(from_attributes=True)

    kri_id: str = Field(..., description="KRI identifier")
    site_id: str = Field(..., description="Site identifier")
    value: float = Field(..., description="Measured value")
    period: str = Field(..., description="Reporting period (YYYY-MM)")


class MonitoringPlanCreate(BaseModel):
    """Request to create a monitoring plan/visit."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial ID")
    site_id: str = Field(..., description="Site ID")
    visit_type: MonitoringVisitType = Field(..., description="Visit type")
    planned_date: datetime = Field(..., description="Planned date")
    monitor_name: str = Field(..., description="Monitor name")


class MonitoringPlanUpdate(BaseModel):
    """Request to update a monitoring plan."""

    model_config = ConfigDict(from_attributes=True)

    visit_type: MonitoringVisitType | None = Field(None, description="Visit type")
    planned_date: datetime | None = Field(None, description="Planned date")
    monitor_name: str | None = Field(None, description="Monitor name")
    status: MonitoringPlanStatus | None = Field(None, description="Visit status")
    notes: str | None = Field(None, description="Notes")


class MonitoringVisitComplete(BaseModel):
    """Request to complete a monitoring visit with findings."""

    model_config = ConfigDict(from_attributes=True)

    actual_date: datetime = Field(..., description="Actual visit date")
    notes: str | None = Field(None, description="Visit notes")
    findings: list[FindingCreate] | None = Field(
        None, description="Findings from the visit"
    )


class FindingCreate(BaseModel):
    """Request to create a monitoring finding."""

    model_config = ConfigDict(from_attributes=True)

    category: FindingCategory = Field(..., description="Finding category")
    description: str = Field(..., description="Finding description")
    response_due_date: datetime = Field(..., description="Response due date")
    capa_id: str | None = Field(None, description="Linked CAPA ID")


class FindingUpdate(BaseModel):
    """Request to update a monitoring finding."""

    model_config = ConfigDict(from_attributes=True)

    category: FindingCategory | None = Field(None, description="Category")
    description: str | None = Field(None, description="Description")
    response_due_date: datetime | None = Field(None, description="Response due date")
    resolved_date: datetime | None = Field(None, description="Resolved date")
    capa_id: str | None = Field(None, description="CAPA ID")
    status: FindingStatus | None = Field(None, description="Status")


class AlertResolve(BaseModel):
    """Request to resolve a central monitoring alert."""

    model_config = ConfigDict(from_attributes=True)

    action_taken: MonitoringAction = Field(..., description="Action taken")
    notes: str | None = Field(None, description="Resolution notes")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class KRIListResponse(BaseModel):
    """List of Key Risk Indicators."""

    model_config = ConfigDict(from_attributes=True)

    items: list[KeyRiskIndicator] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class SiteRiskScoreListResponse(BaseModel):
    """List of site risk scores."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SiteRiskScore] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class KRIDataPointListResponse(BaseModel):
    """List of KRI data points."""

    model_config = ConfigDict(from_attributes=True)

    items: list[KRIDataPoint] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class MonitoringPlanListResponse(BaseModel):
    """List of monitoring plans."""

    model_config = ConfigDict(from_attributes=True)

    items: list[MonitoringPlan] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class MonitoringFindingListResponse(BaseModel):
    """List of monitoring findings."""

    model_config = ConfigDict(from_attributes=True)

    items: list[MonitoringFinding] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class CentralMonitoringAlertListResponse(BaseModel):
    """List of central monitoring alerts."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CentralMonitoringAlert] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Metrics / dashboard
# ---------------------------------------------------------------------------


class RBMMetrics(BaseModel):
    """Aggregated Risk-Based Monitoring operational metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_sites: int = Field(ge=0, description="Total sites under monitoring")
    sites_by_risk_level: dict[str, int] = Field(
        default_factory=dict, description="Site counts by risk level"
    )
    total_kris: int = Field(ge=0, description="Total KRIs defined")
    active_alerts: int = Field(ge=0, description="Number of unresolved central monitoring alerts")
    avg_risk_score: float = Field(ge=0.0, description="Average risk score across all sites")
    monitoring_visits_completed: int = Field(
        ge=0, description="Total monitoring visits completed"
    )
    open_findings: int = Field(ge=0, description="Number of open findings")
    overdue_findings: int = Field(ge=0, description="Number of overdue findings")
    total_findings: int = Field(ge=0, description="Total findings across all visits")
    total_monitoring_plans: int = Field(ge=0, description="Total monitoring plans")
    kri_data_points: int = Field(ge=0, description="Total KRI data points recorded")


# ---------------------------------------------------------------------------
# Monitoring schedule recommendation
# ---------------------------------------------------------------------------


class MonitoringScheduleRecommendation(BaseModel):
    """Recommended monitoring schedule for a site."""

    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., description="Site identifier")
    site_name: str = Field(..., description="Site name")
    risk_level: RiskLevel = Field(..., description="Current risk level")
    recommended_frequency: str = Field(
        ..., description="Recommended visit frequency (e.g., monthly, quarterly)"
    )
    recommended_visit_type: MonitoringVisitType = Field(
        ..., description="Recommended visit type"
    )
    next_recommended_date: datetime = Field(
        ..., description="Next recommended visit date"
    )
    rationale: str = Field(..., description="Rationale for the recommendation")
