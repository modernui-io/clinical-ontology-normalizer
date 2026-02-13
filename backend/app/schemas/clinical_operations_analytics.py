"""Pydantic schemas for Clinical Operations Analytics (CLIN-OPS-ANLY).

Manages clinical operations analytics: enrollment velocity tracking,
site performance scorecards, protocol deviation trending, resource
utilization analysis, and milestone achievement with analytics metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class VelocityTrend(str, Enum):
    ACCELERATING = "accelerating"
    STEADY = "steady"
    DECELERATING = "decelerating"
    STALLED = "stalled"
    RECOVERING = "recovering"
    NOT_STARTED = "not_started"


class PerformanceTier(str, Enum):
    TOP_PERFORMER = "top_performer"
    ABOVE_AVERAGE = "above_average"
    AVERAGE = "average"
    BELOW_AVERAGE = "below_average"
    UNDERPERFORMING = "underperforming"
    NEW_SITE = "new_site"


class DeviationCategory(str, Enum):
    INFORMED_CONSENT = "informed_consent"
    INCLUSION_EXCLUSION = "inclusion_exclusion"
    STUDY_PROCEDURES = "study_procedures"
    DOSING = "dosing"
    VISIT_WINDOW = "visit_window"
    SAFETY_REPORTING = "safety_reporting"


class ResourceType(str, Enum):
    CRA = "cra"
    DATA_MANAGER = "data_manager"
    PROJECT_MANAGER = "project_manager"
    MEDICAL_MONITOR = "medical_monitor"
    BIOSTATISTICIAN = "biostatistician"
    REGULATORY_SPECIALIST = "regulatory_specialist"


class MilestoneCategory(str, Enum):
    REGULATORY = "regulatory"
    SITE_ACTIVATION = "site_activation"
    ENROLLMENT = "enrollment"
    DATABASE_LOCK = "database_lock"
    ANALYSIS = "analysis"
    SUBMISSION = "submission"


class EnrollmentVelocity(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    measurement_date: datetime
    site_id: str | None = None
    period_days: int = Field(ge=1, default=30)
    patients_enrolled: int = Field(ge=0, default=0)
    patients_screened: int = Field(ge=0, default=0)
    screen_fail_rate_pct: float = Field(ge=0, le=100, default=0.0)
    enrollment_rate_per_site_month: float = Field(ge=0, default=0.0)
    velocity_trend: VelocityTrend = VelocityTrend.STEADY
    days_to_target: int | None = None
    target_enrollment: int = Field(ge=0, default=0)
    pct_target_achieved: float = Field(ge=0, le=100, default=0.0)
    forecast_completion_date: datetime | None = None
    analyzed_by: str
    notes: str | None = None
    created_at: datetime


class SitePerformanceScorecard(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    site_name: str
    scorecard_date: datetime
    performance_tier: PerformanceTier = PerformanceTier.AVERAGE
    enrollment_score: float = Field(ge=0, le=100, default=50.0)
    data_quality_score: float = Field(ge=0, le=100, default=50.0)
    compliance_score: float = Field(ge=0, le=100, default=50.0)
    safety_reporting_score: float = Field(ge=0, le=100, default=50.0)
    overall_score: float = Field(ge=0, le=100, default=50.0)
    query_rate_per_page: float = Field(ge=0, default=0.0)
    open_queries: int = Field(ge=0, default=0)
    overdue_queries: int = Field(ge=0, default=0)
    ranking: int = Field(ge=1, default=1)
    total_sites: int = Field(ge=1, default=1)
    evaluated_by: str
    notes: str | None = None
    created_at: datetime


class ProtocolDeviationTrend(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    reporting_period: str
    deviation_category: DeviationCategory
    total_deviations: int = Field(ge=0, default=0)
    major_deviations: int = Field(ge=0, default=0)
    minor_deviations: int = Field(ge=0, default=0)
    repeat_deviations: int = Field(ge=0, default=0)
    sites_affected: int = Field(ge=0, default=0)
    subjects_affected: int = Field(ge=0, default=0)
    root_causes: list[str] = Field(default_factory=list)
    corrective_actions_initiated: int = Field(ge=0, default=0)
    trend_direction: str = "stable"
    deviation_rate_per_subject: float = Field(ge=0, default=0.0)
    analyzed_by: str
    notes: str | None = None
    created_at: datetime


class ResourceUtilization(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    resource_type: ResourceType
    reporting_period: str
    total_fte_allocated: float = Field(ge=0, default=0.0)
    total_fte_utilized: float = Field(ge=0, default=0.0)
    utilization_pct: float = Field(ge=0, le=100, default=0.0)
    overtime_hours: float = Field(ge=0, default=0.0)
    vacancy_count: int = Field(ge=0, default=0)
    contractor_count: int = Field(ge=0, default=0)
    training_hours: float = Field(ge=0, default=0.0)
    cost_per_fte: float = Field(ge=0, default=0.0)
    budget_variance_pct: float = 0.0
    managed_by: str
    notes: str | None = None
    created_at: datetime


class MilestoneAchievement(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    milestone_name: str
    milestone_category: MilestoneCategory
    planned_date: datetime
    actual_date: datetime | None = None
    achieved: bool = False
    days_variance: int = 0
    on_track: bool = True
    critical_path: bool = False
    dependencies: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    owner: str
    escalated: bool = False
    notes: str | None = None
    created_at: datetime


class EnrollmentVelocityCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    analyzed_by: str
    patients_enrolled: int = Field(ge=0, default=0)
    patients_screened: int = Field(ge=0, default=0)
    target_enrollment: int = Field(ge=0, default=0)
    period_days: int = Field(ge=1, default=30)


class EnrollmentVelocityUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    velocity_trend: VelocityTrend | None = None
    pct_target_achieved: float | None = None
    forecast_completion_date: datetime | None = None
    days_to_target: int | None = None
    notes: str | None = None


class SitePerformanceScorecardCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    site_name: str
    evaluated_by: str
    enrollment_score: float = Field(ge=0, le=100, default=50.0)
    data_quality_score: float = Field(ge=0, le=100, default=50.0)


class SitePerformanceScorecardUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    performance_tier: PerformanceTier | None = None
    overall_score: float | None = None
    compliance_score: float | None = None
    ranking: int | None = None
    notes: str | None = None


class ProtocolDeviationTrendCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    reporting_period: str
    deviation_category: DeviationCategory
    analyzed_by: str
    total_deviations: int = Field(ge=0, default=0)
    major_deviations: int = Field(ge=0, default=0)


class ProtocolDeviationTrendUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trend_direction: str | None = None
    corrective_actions_initiated: int | None = None
    repeat_deviations: int | None = None
    deviation_rate_per_subject: float | None = None
    notes: str | None = None


class ResourceUtilizationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    resource_type: ResourceType
    reporting_period: str
    managed_by: str
    total_fte_allocated: float = Field(ge=0, default=0.0)
    total_fte_utilized: float = Field(ge=0, default=0.0)


class ResourceUtilizationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    utilization_pct: float | None = None
    vacancy_count: int | None = None
    budget_variance_pct: float | None = None
    overtime_hours: float | None = None
    notes: str | None = None


class MilestoneAchievementCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    milestone_name: str
    milestone_category: MilestoneCategory
    planned_date: datetime
    owner: str
    critical_path: bool = False


class MilestoneAchievementUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    achieved: bool | None = None
    actual_date: datetime | None = None
    on_track: bool | None = None
    escalated: bool | None = None
    notes: str | None = None


class EnrollmentVelocityListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[EnrollmentVelocity] = Field(default_factory=list)
    total: int = Field(ge=0)


class SitePerformanceScorecardListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SitePerformanceScorecard] = Field(default_factory=list)
    total: int = Field(ge=0)


class ProtocolDeviationTrendListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ProtocolDeviationTrend] = Field(default_factory=list)
    total: int = Field(ge=0)


class ResourceUtilizationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ResourceUtilization] = Field(default_factory=list)
    total: int = Field(ge=0)


class MilestoneAchievementListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[MilestoneAchievement] = Field(default_factory=list)
    total: int = Field(ge=0)


class ClinicalOperationsAnalyticsMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_velocity_records: int = Field(ge=0)
    velocity_by_trend: dict[str, int] = Field(default_factory=dict)
    avg_enrollment_rate: float = Field(ge=0)
    total_scorecards: int = Field(ge=0)
    scorecards_by_tier: dict[str, int] = Field(default_factory=dict)
    avg_overall_score: float = Field(ge=0)
    total_deviation_trends: int = Field(ge=0)
    deviations_by_category: dict[str, int] = Field(default_factory=dict)
    total_major_deviations: int = Field(ge=0)
    total_resource_records: int = Field(ge=0)
    resources_by_type: dict[str, int] = Field(default_factory=dict)
    avg_utilization_pct: float = Field(ge=0)
    total_milestones: int = Field(ge=0)
    milestones_by_category: dict[str, int] = Field(default_factory=dict)
    milestones_achieved: int = Field(ge=0)
    milestones_overdue: int = Field(ge=0)
