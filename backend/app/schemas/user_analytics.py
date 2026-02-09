"""Pydantic schemas for User Analytics & Feature Flag Management (VP-Product-9).

Tracks user behavior events, manages feature flags with multiple rollout
strategies, runs funnel analysis, computes retention cohorts, and provides
product health metrics for the clinical trial patient recruitment platform.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EventCategory(str, Enum):
    """Category of a user analytics event."""

    PAGE_VIEW = "PAGE_VIEW"
    BUTTON_CLICK = "BUTTON_CLICK"
    FORM_SUBMIT = "FORM_SUBMIT"
    SEARCH = "SEARCH"
    FILTER = "FILTER"
    EXPORT = "EXPORT"
    API_CALL = "API_CALL"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    ERROR = "ERROR"


class FlagStatus(str, Enum):
    """Lifecycle status of a feature flag."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"


class RolloutStrategy(str, Enum):
    """Strategy for rolling out a feature flag."""

    ALL_USERS = "ALL_USERS"
    PERCENTAGE = "PERCENTAGE"
    USER_LIST = "USER_LIST"
    ROLE_BASED = "ROLE_BASED"
    GRADUAL = "GRADUAL"


class FunnelStage(str, Enum):
    """Stages of the clinical trial screening funnel."""

    VISIT = "VISIT"
    SEARCH_TRIAL = "SEARCH_TRIAL"
    VIEW_CRITERIA = "VIEW_CRITERIA"
    RUN_SCREENING = "RUN_SCREENING"
    REVIEW_RESULTS = "REVIEW_RESULTS"
    EXPORT_REPORT = "EXPORT_REPORT"
    ENROLL_CANDIDATE = "ENROLL_CANDIDATE"


class RetentionPeriod(str, Enum):
    """Period for retention cohort analysis."""

    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class MetricType(str, Enum):
    """Type of product metric."""

    COUNTER = "COUNTER"
    GAUGE = "GAUGE"
    HISTOGRAM = "HISTOGRAM"
    RATE = "RATE"


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------


class AnalyticsEvent(BaseModel):
    """A single user analytics event."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique event identifier")
    user_id: str = Field(..., description="ID of the user who triggered the event")
    session_id: str = Field(..., description="Session in which the event occurred")
    event_category: EventCategory = Field(..., description="Category of the event")
    event_name: str = Field(..., description="Human-readable event name")
    properties: dict[str, Any] = Field(
        default_factory=dict, description="Additional event properties"
    )
    page_url: str | None = Field(None, description="Page URL where the event occurred")
    timestamp: datetime = Field(..., description="When the event occurred")
    duration_ms: int | None = Field(
        None, description="Duration of the event in milliseconds"
    )


class UserSession(BaseModel):
    """A user browsing session."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique session identifier")
    user_id: str = Field(..., description="User who owns this session")
    started_at: datetime = Field(..., description="Session start time")
    ended_at: datetime | None = Field(None, description="Session end time")
    page_views: int = Field(0, description="Number of page views in the session")
    events_count: int = Field(0, description="Number of events in the session")
    device_type: str | None = Field(None, description="Device type (desktop, mobile, tablet)")
    browser: str | None = Field(None, description="Browser name and version")


class FlagVariant(BaseModel):
    """A variant within a feature flag experiment."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Variant name (e.g., 'control', 'treatment')")
    weight: float = Field(
        ..., ge=0.0, le=1.0, description="Weight for traffic allocation"
    )
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Variant-specific configuration"
    )


class FeatureFlag(BaseModel):
    """A feature flag with rollout configuration."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique flag identifier")
    name: str = Field(..., description="Flag name (kebab-case)")
    description: str = Field("", description="Human-readable description")
    status: FlagStatus = Field(FlagStatus.INACTIVE, description="Flag lifecycle status")
    rollout_strategy: RolloutStrategy = Field(
        RolloutStrategy.ALL_USERS, description="How the flag is rolled out"
    )
    rollout_percentage: float = Field(
        100.0, ge=0.0, le=100.0, description="Percentage of users for PERCENTAGE strategy"
    )
    allowed_users: list[str] = Field(
        default_factory=list, description="Allowed user IDs for USER_LIST strategy"
    )
    allowed_roles: list[str] = Field(
        default_factory=list, description="Allowed roles for ROLE_BASED strategy"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: str = Field(..., description="User who created the flag")
    variants: list[FlagVariant] = Field(
        default_factory=list, description="Variants for A/B testing"
    )
    default_variant: str = Field(
        "control", description="Default variant name when flag is off"
    )


class FlagEvaluation(BaseModel):
    """Result of evaluating a feature flag for a specific user."""

    model_config = ConfigDict(from_attributes=True)

    flag_id: str = Field(..., description="Feature flag ID")
    user_id: str = Field(..., description="User the flag was evaluated for")
    variant: str = Field(..., description="Assigned variant name")
    evaluated_at: datetime = Field(..., description="When the evaluation occurred")
    context: dict[str, Any] = Field(
        default_factory=dict, description="Evaluation context (role, percentage bucket, etc.)"
    )


# ---------------------------------------------------------------------------
# Analytics models
# ---------------------------------------------------------------------------


class FunnelStageResult(BaseModel):
    """Result for a single stage within a funnel analysis."""

    model_config = ConfigDict(from_attributes=True)

    stage: FunnelStage = Field(..., description="Funnel stage")
    count: int = Field(..., description="Number of users who reached this stage")
    conversion_from_previous: float = Field(
        ..., description="Conversion rate from the previous stage (0.0 - 1.0)"
    )
    drop_off_rate: float = Field(
        ..., description="Drop-off rate at this stage (0.0 - 1.0)"
    )
    median_time_seconds: float | None = Field(
        None, description="Median time spent at this stage in seconds"
    )


class FunnelAnalysis(BaseModel):
    """Complete funnel analysis result."""

    model_config = ConfigDict(from_attributes=True)

    funnel_name: str = Field(..., description="Name of the funnel")
    stages: list[FunnelStageResult] = Field(..., description="Per-stage results")
    total_entered: int = Field(..., description="Total users who entered the funnel")
    conversion_rate: float = Field(
        ..., description="End-to-end conversion rate (0.0 - 1.0)"
    )
    drop_off_stages: list[FunnelStage] = Field(
        default_factory=list, description="Stages with highest drop-off"
    )
    median_time_to_complete: float | None = Field(
        None, description="Median time to complete the funnel in seconds"
    )


class RetentionCohort(BaseModel):
    """Retention cohort data for a specific start date."""

    model_config = ConfigDict(from_attributes=True)

    cohort_date: str = Field(..., description="Cohort start date (YYYY-MM-DD)")
    cohort_size: int = Field(..., description="Number of users in the cohort")
    periods: list[int] = Field(
        ..., description="Period indices (0, 1, 2, ...)"
    )
    retention_rates: list[float] = Field(
        ..., description="Retention rate per period (0.0 - 1.0)"
    )


class ProductMetric(BaseModel):
    """A single product health metric."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Metric name")
    metric_type: MetricType = Field(..., description="Type of metric")
    value: float = Field(..., description="Current metric value")
    period: str = Field(..., description="Time period (e.g., 'daily', 'weekly')")
    comparison_value: float | None = Field(
        None, description="Previous period value for comparison"
    )
    change_percent: float | None = Field(
        None, description="Percentage change from comparison period"
    )


class UserAnalyticsMetrics(BaseModel):
    """Aggregated user analytics metrics for the dashboard."""

    model_config = ConfigDict(from_attributes=True)

    total_events: int = Field(0, description="Total tracked events")
    unique_users: int = Field(0, description="Unique users")
    avg_session_duration_minutes: float = Field(
        0.0, description="Average session duration in minutes"
    )
    total_sessions: int = Field(0, description="Total sessions")
    events_per_session: float = Field(0.0, description="Average events per session")
    top_events: list[dict[str, Any]] = Field(
        default_factory=list, description="Top events by count"
    )
    top_pages: list[dict[str, Any]] = Field(
        default_factory=list, description="Top pages by views"
    )
    active_flags: int = Field(0, description="Number of active feature flags")
    feature_adoption_rates: dict[str, float] = Field(
        default_factory=dict, description="Adoption rate per feature flag"
    )


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class EventCreateRequest(BaseModel):
    """Request to create a new analytics event."""

    user_id: str = Field(..., description="ID of the user")
    session_id: str = Field(..., description="Session ID")
    event_category: EventCategory = Field(..., description="Event category")
    event_name: str = Field(..., description="Event name")
    properties: dict[str, Any] = Field(
        default_factory=dict, description="Event properties"
    )
    page_url: str | None = Field(None, description="Page URL")
    duration_ms: int | None = Field(None, description="Duration in milliseconds")


class EventListResponse(BaseModel):
    """Paginated list of analytics events."""

    items: list[AnalyticsEvent] = Field(..., description="List of events")
    total: int = Field(..., description="Total matching events")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Page offset")


class FeatureFlagCreateRequest(BaseModel):
    """Request to create a new feature flag."""

    name: str = Field(..., description="Flag name (kebab-case)")
    description: str = Field("", description="Description of the flag")
    status: FlagStatus = Field(FlagStatus.INACTIVE, description="Initial status")
    rollout_strategy: RolloutStrategy = Field(
        RolloutStrategy.ALL_USERS, description="Rollout strategy"
    )
    rollout_percentage: float = Field(
        100.0, ge=0.0, le=100.0, description="Rollout percentage"
    )
    allowed_users: list[str] = Field(default_factory=list, description="Allowed users")
    allowed_roles: list[str] = Field(default_factory=list, description="Allowed roles")
    created_by: str = Field(..., description="Creator user ID")
    variants: list[FlagVariant] = Field(
        default_factory=list, description="Flag variants"
    )
    default_variant: str = Field("control", description="Default variant")


class FeatureFlagUpdateRequest(BaseModel):
    """Request to update an existing feature flag."""

    name: str | None = Field(None, description="Updated name")
    description: str | None = Field(None, description="Updated description")
    status: FlagStatus | None = Field(None, description="Updated status")
    rollout_strategy: RolloutStrategy | None = Field(
        None, description="Updated rollout strategy"
    )
    rollout_percentage: float | None = Field(
        None, ge=0.0, le=100.0, description="Updated rollout percentage"
    )
    allowed_users: list[str] | None = Field(None, description="Updated allowed users")
    allowed_roles: list[str] | None = Field(None, description="Updated allowed roles")
    variants: list[FlagVariant] | None = Field(None, description="Updated variants")
    default_variant: str | None = Field(None, description="Updated default variant")


class FlagListResponse(BaseModel):
    """List of feature flags."""

    items: list[FeatureFlag] = Field(..., description="List of flags")
    total: int = Field(..., description="Total flags")


class FlagEvaluateRequest(BaseModel):
    """Request to evaluate a feature flag for a user."""

    user_id: str = Field(..., description="User to evaluate for")
    role: str | None = Field(None, description="User role for role-based rollout")


class FunnelRequest(BaseModel):
    """Request for funnel analysis."""

    funnel_name: str = Field(
        "trial_screening", description="Name of the funnel to analyze"
    )
    stages: list[FunnelStage] | None = Field(
        None, description="Custom funnel stages (defaults to all stages)"
    )
    start_date: str | None = Field(None, description="Start date (YYYY-MM-DD)")
    end_date: str | None = Field(None, description="End date (YYYY-MM-DD)")


class RetentionRequest(BaseModel):
    """Request for retention cohort analysis."""

    period: RetentionPeriod = Field(
        RetentionPeriod.WEEKLY, description="Retention period"
    )
    num_cohorts: int = Field(4, ge=1, le=12, description="Number of cohorts")
    num_periods: int = Field(6, ge=1, le=24, description="Periods per cohort")


class SessionCreateRequest(BaseModel):
    """Request to create a new session."""

    user_id: str = Field(..., description="User who owns this session")
    device_type: str | None = Field(None, description="Device type")
    browser: str | None = Field(None, description="Browser name and version")


class ProductHealthReport(BaseModel):
    """Comprehensive product health report."""

    model_config = ConfigDict(from_attributes=True)

    generated_at: datetime = Field(..., description="Report generation time")
    metrics: list[ProductMetric] = Field(..., description="Product health metrics")
    user_analytics: UserAnalyticsMetrics = Field(
        ..., description="Aggregated analytics"
    )
    active_experiments: int = Field(0, description="Number of active A/B experiments")
    total_feature_flags: int = Field(0, description="Total feature flags")
