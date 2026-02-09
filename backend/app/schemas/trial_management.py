"""Pydantic schemas for Trial Management Office (TMO) & Multi-Site Coordination (CLINICAL-10).

Manages TMO operations: site activation tracking, country regulatory status,
trial milestones with critical path analysis, site communications with
acknowledgment tracking, blocker management, cross-trial resource allocation,
enrollment forecasting, and TMO dashboard aggregation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SiteActivationStatus(str, Enum):
    """Status of a clinical trial site activation."""

    PLANNED = "planned"
    REGULATORY_SUBMITTED = "regulatory_submitted"
    IRB_APPROVED = "irb_approved"
    CONTRACTS_EXECUTED = "contracts_executed"
    SITE_INITIATED = "site_initiated"
    ENROLLING = "enrolling"
    ENROLLMENT_COMPLETE = "enrollment_complete"
    CLOSED = "closed"


class CountryStatus(str, Enum):
    """Regulatory status for a country in a trial."""

    PLANNED = "planned"
    REGULATORY_SUBMITTED = "regulatory_submitted"
    APPROVED = "approved"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class MilestoneCategory(str, Enum):
    """Category of a trial milestone."""

    REGULATORY = "regulatory"
    SITE_ACTIVATION = "site_activation"
    ENROLLMENT = "enrollment"
    DATA = "data"
    SAFETY = "safety"
    REPORTING = "reporting"


class MilestoneStatus(str, Enum):
    """Status of a trial milestone."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DELAYED = "delayed"
    AT_RISK = "at_risk"
    CANCELLED = "cancelled"


class CommunicationType(str, Enum):
    """Type of communication sent to sites."""

    NEWSLETTER = "newsletter"
    MEMO = "memo"
    ALERT = "alert"
    PROTOCOL_AMENDMENT = "protocol_amendment"
    SAFETY_LETTER = "safety_letter"
    TRAINING_BULLETIN = "training_bulletin"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class SiteActivation(BaseModel):
    """A clinical trial site activation record."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique site activation identifier")
    site_id: str = Field(..., description="Site identifier")
    site_name: str = Field(..., description="Name of the clinical trial site")
    trial_id: str = Field(..., description="Associated trial identifier")
    country: str = Field(..., description="Country where the site is located")
    status: SiteActivationStatus = Field(..., description="Current activation status")
    planned_activation_date: datetime | None = Field(
        None, description="Planned date for site activation"
    )
    actual_activation_date: datetime | None = Field(
        None, description="Actual date of site activation"
    )
    irb_approval_date: datetime | None = Field(
        None, description="Date of IRB/ethics committee approval"
    )
    contract_execution_date: datetime | None = Field(
        None, description="Date the site contract was executed"
    )
    first_patient_date: datetime | None = Field(
        None, description="Date of first patient enrolled at site"
    )
    milestones: list[str] = Field(
        default_factory=list, description="List of site-level milestones achieved"
    )
    blockers: list[str] = Field(
        default_factory=list, description="List of blocker IDs affecting this site"
    )


class CountryRegulatory(BaseModel):
    """Regulatory status for a country in a clinical trial."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique country regulatory record identifier")
    country_code: str = Field(..., description="ISO country code (e.g., US, DE, JP)")
    country_name: str = Field(..., description="Full country name")
    trial_id: str = Field(..., description="Associated trial identifier")
    status: CountryStatus = Field(..., description="Current regulatory status")
    regulatory_body: str = Field(..., description="Name of the regulatory authority")
    submission_date: datetime | None = Field(
        None, description="Date regulatory submission was filed"
    )
    approval_date: datetime | None = Field(
        None, description="Date regulatory approval was received"
    )
    import_license_date: datetime | None = Field(
        None, description="Date import license was obtained"
    )
    data_privacy_approval: bool = Field(
        default=False, description="Whether data privacy approval has been obtained"
    )
    local_requirements: list[str] = Field(
        default_factory=list, description="List of country-specific local requirements"
    )


class TrialMilestone(BaseModel):
    """A milestone within a clinical trial."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique milestone identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    name: str = Field(..., description="Name of the milestone")
    category: MilestoneCategory = Field(..., description="Category of the milestone")
    status: MilestoneStatus = Field(..., description="Current status of the milestone")
    planned_date: datetime = Field(..., description="Planned completion date")
    actual_date: datetime | None = Field(None, description="Actual completion date")
    responsible_party: str = Field(..., description="Person or team responsible")
    dependencies: list[str] = Field(
        default_factory=list, description="List of milestone IDs this depends on"
    )
    percent_complete: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Percent complete (0-100)"
    )


class SiteCommunication(BaseModel):
    """A communication sent to clinical trial sites."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique communication identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    type: CommunicationType = Field(..., description="Type of communication")
    subject: str = Field(..., description="Subject line of the communication")
    body: str = Field(..., description="Body text of the communication")
    sent_date: datetime = Field(..., description="Date the communication was sent")
    recipients: list[str] = Field(
        default_factory=list, description="List of site IDs that received this"
    )
    acknowledgments: list[str] = Field(
        default_factory=list, description="List of site IDs that acknowledged"
    )
    requires_acknowledgment: bool = Field(
        default=False, description="Whether sites must acknowledge this communication"
    )


class SiteBlocker(BaseModel):
    """A blocker impeding site activation or operation."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique blocker identifier")
    site_id: str = Field(..., description="Affected site identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    description: str = Field(..., description="Description of the blocker")
    category: str = Field(..., description="Category (regulatory, contract, supply, staffing, other)")
    raised_date: datetime = Field(..., description="Date the blocker was raised")
    resolved_date: datetime | None = Field(
        None, description="Date the blocker was resolved"
    )
    impact_description: str = Field(
        default="", description="Description of the impact on the trial"
    )
    escalated: bool = Field(
        default=False, description="Whether the blocker has been escalated"
    )


class CrossTrialResource(BaseModel):
    """A resource (person) shared across multiple trials."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique resource identifier")
    resource_name: str = Field(..., description="Name of the person or resource")
    role: str = Field(..., description="Role or title")
    assigned_trials: list[str] = Field(
        default_factory=list, description="List of trial IDs this resource is assigned to"
    )
    utilization_pct: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Current utilization percentage"
    )
    availability_start: datetime | None = Field(
        None, description="When the resource becomes available"
    )
    skills: list[str] = Field(
        default_factory=list, description="List of skills or competencies"
    )


class TMODashboard(BaseModel):
    """Aggregated TMO dashboard for a trial."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    total_sites: int = Field(ge=0, description="Total number of sites")
    sites_by_status: dict[str, int] = Field(
        default_factory=dict, description="Site counts by activation status"
    )
    countries_active: int = Field(ge=0, description="Number of active countries")
    enrollment_target: int = Field(ge=0, description="Target enrollment count")
    current_enrollment: int = Field(ge=0, description="Current enrollment count")
    enrollment_rate_per_month: float = Field(
        ge=0.0, description="Current enrollment rate per month"
    )
    milestones_on_track: int = Field(ge=0, description="Number of milestones on track")
    milestones_delayed: int = Field(ge=0, description="Number of delayed milestones")
    open_blockers: int = Field(ge=0, description="Number of open blockers")
    upcoming_milestones_30d: list[TrialMilestone] = Field(
        default_factory=list, description="Milestones due in the next 30 days"
    )


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class SiteActivationUpdate(BaseModel):
    """Request to update a site activation status."""

    model_config = ConfigDict(from_attributes=True)

    status: SiteActivationStatus = Field(..., description="New activation status")


class SiteBlockerCreate(BaseModel):
    """Request to raise a new blocker for a site."""

    model_config = ConfigDict(from_attributes=True)

    description: str = Field(..., description="Description of the blocker")
    category: str = Field(
        default="other", description="Category (regulatory, contract, supply, staffing, other)"
    )
    impact_description: str = Field(
        default="", description="Description of the impact"
    )


class CountryStatusUpdate(BaseModel):
    """Request to update a country regulatory status."""

    model_config = ConfigDict(from_attributes=True)

    status: CountryStatus = Field(..., description="New country status")


class TrialMilestoneCreate(BaseModel):
    """Request to create a new trial milestone."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial ID")
    name: str = Field(..., description="Name of the milestone")
    category: MilestoneCategory = Field(..., description="Category")
    planned_date: datetime = Field(..., description="Planned date")
    responsible_party: str = Field(..., description="Responsible person or team")
    dependencies: list[str] = Field(
        default_factory=list, description="Dependent milestone IDs"
    )


class TrialMilestoneUpdate(BaseModel):
    """Request to update a trial milestone."""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = Field(None, description="Updated name")
    category: MilestoneCategory | None = Field(None, description="Updated category")
    status: MilestoneStatus | None = Field(None, description="Updated status")
    planned_date: datetime | None = Field(None, description="Updated planned date")
    actual_date: datetime | None = Field(None, description="Actual completion date")
    responsible_party: str | None = Field(None, description="Updated responsible party")
    dependencies: list[str] | None = Field(None, description="Updated dependencies")
    percent_complete: float | None = Field(None, description="Updated percent complete")


class SiteCommunicationCreate(BaseModel):
    """Request to send a communication to sites."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial ID")
    type: CommunicationType = Field(..., description="Type of communication")
    subject: str = Field(..., description="Subject line")
    body: str = Field(..., description="Body text")
    recipients: list[str] = Field(..., description="List of site IDs to receive")
    requires_acknowledgment: bool = Field(
        default=False, description="Whether acknowledgment is required"
    )


class CrossTrialResourceCreate(BaseModel):
    """Request to add a cross-trial resource."""

    model_config = ConfigDict(from_attributes=True)

    resource_name: str = Field(..., description="Name of the resource")
    role: str = Field(..., description="Role or title")
    assigned_trials: list[str] = Field(
        default_factory=list, description="Assigned trial IDs"
    )
    utilization_pct: float = Field(default=0.0, description="Utilization percentage")
    availability_start: datetime | None = Field(None, description="Availability start")
    skills: list[str] = Field(default_factory=list, description="Skills")


class EnrollmentProjection(BaseModel):
    """Enrollment projection for a trial."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    enrollment_target: int = Field(ge=0, description="Target enrollment")
    current_enrollment: int = Field(ge=0, description="Current enrollment")
    enrollment_rate_per_month: float = Field(ge=0.0, description="Monthly enrollment rate")
    projected_completion_date: datetime | None = Field(
        None, description="Projected date to reach target"
    )
    months_remaining: float | None = Field(
        None, description="Estimated months to reach target"
    )
    on_track: bool = Field(default=True, description="Whether enrollment is on track")
    sites_enrolling: int = Field(ge=0, description="Number of sites actively enrolling")


class ResourceUtilization(BaseModel):
    """Resource utilization report."""

    model_config = ConfigDict(from_attributes=True)

    total_resources: int = Field(ge=0, description="Total cross-trial resources")
    avg_utilization_pct: float = Field(ge=0.0, description="Average utilization percentage")
    over_utilized: list[CrossTrialResource] = Field(
        default_factory=list, description="Resources with utilization > 90%"
    )
    under_utilized: list[CrossTrialResource] = Field(
        default_factory=list, description="Resources with utilization < 30%"
    )
    by_role: dict[str, float] = Field(
        default_factory=dict, description="Average utilization by role"
    )


class CriticalPathResult(BaseModel):
    """Result of critical path analysis."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    critical_path: list[TrialMilestone] = Field(
        default_factory=list, description="Milestones on the critical path"
    )
    total_duration_days: int = Field(
        ge=0, description="Total duration of the critical path in days"
    )
    earliest_completion: datetime | None = Field(
        None, description="Earliest possible trial completion date"
    )


class GanttItem(BaseModel):
    """A single item in Gantt chart data."""

    model_config = ConfigDict(from_attributes=True)

    milestone_id: str = Field(..., description="Milestone identifier")
    name: str = Field(..., description="Milestone name")
    category: MilestoneCategory = Field(..., description="Category")
    status: MilestoneStatus = Field(..., description="Status")
    planned_start: datetime = Field(..., description="Planned start date")
    planned_end: datetime = Field(..., description="Planned end date")
    actual_end: datetime | None = Field(None, description="Actual end date")
    percent_complete: float = Field(default=0.0, description="Percent complete")
    dependencies: list[str] = Field(default_factory=list, description="Dependencies")
    is_critical_path: bool = Field(default=False, description="Whether on critical path")


class GanttChartData(BaseModel):
    """Gantt chart data for a trial."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    items: list[GanttItem] = Field(default_factory=list, description="Gantt chart items")
    critical_path_ids: list[str] = Field(
        default_factory=list, description="IDs of milestones on the critical path"
    )


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class SiteActivationListResponse(BaseModel):
    """Paginated list of site activations."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SiteActivation] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class CountryRegulatoryListResponse(BaseModel):
    """List of country regulatory records."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CountryRegulatory] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class TrialMilestoneListResponse(BaseModel):
    """List of trial milestones."""

    model_config = ConfigDict(from_attributes=True)

    items: list[TrialMilestone] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class SiteCommunicationListResponse(BaseModel):
    """List of site communications."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SiteCommunication] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class SiteBlockerListResponse(BaseModel):
    """List of site blockers."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SiteBlocker] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class CrossTrialResourceListResponse(BaseModel):
    """List of cross-trial resources."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CrossTrialResource] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class EnrollmentProjectionListResponse(BaseModel):
    """List of enrollment projections."""

    model_config = ConfigDict(from_attributes=True)

    items: list[EnrollmentProjection] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")
