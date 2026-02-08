"""Pydantic schemas for Patient Engagement and Communication Tracking.

Defines communication records, templates, campaigns, patient preferences,
engagement scoring, and analytics models for the clinical trial recruitment
platform.

No PHI is stored in communication content -- only summaries and metadata.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CommunicationChannel(str, Enum):
    """Channels through which patient communication occurs."""

    EMAIL = "EMAIL"
    SMS = "SMS"
    PHONE = "PHONE"
    IN_APP = "IN_APP"
    PORTAL = "PORTAL"


class CommunicationDirection(str, Enum):
    """Direction of the communication."""

    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class CommunicationStatus(str, Enum):
    """Delivery and engagement status of a communication."""

    SENT = "SENT"
    DELIVERED = "DELIVERED"
    OPENED = "OPENED"
    RESPONDED = "RESPONDED"
    FAILED = "FAILED"
    BOUNCED = "BOUNCED"


class TemplateType(str, Enum):
    """Pre-defined communication template types."""

    SCREENING_INVITATION = "SCREENING_INVITATION"
    ELIGIBILITY_RESULT = "ELIGIBILITY_RESULT"
    APPOINTMENT_REMINDER = "APPOINTMENT_REMINDER"
    CONSENT_REQUEST = "CONSENT_REQUEST"
    ENROLLMENT_CONFIRMATION = "ENROLLMENT_CONFIRMATION"
    FOLLOW_UP_REMINDER = "FOLLOW_UP_REMINDER"
    WITHDRAWAL_ACKNOWLEDGMENT = "WITHDRAWAL_ACKNOWLEDGMENT"


class CampaignStatus(str, Enum):
    """Status of a communication campaign."""

    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class FrequencyUnit(str, Enum):
    """Units for communication frequency limits."""

    DAY = "DAY"
    WEEK = "WEEK"
    MONTH = "MONTH"


# ---------------------------------------------------------------------------
# Core schemas
# ---------------------------------------------------------------------------


class CommunicationRecord(BaseModel):
    """A recorded patient communication event (no PHI in content)."""

    id: str = Field(..., description="Unique communication record identifier")
    patient_id: str = Field(..., description="Patient identifier")
    trial_id: str | None = Field(
        default=None,
        description="Associated clinical trial identifier",
    )
    channel: CommunicationChannel = Field(
        ..., description="Communication channel used"
    )
    direction: CommunicationDirection = Field(
        ..., description="Direction of the communication"
    )
    subject: str = Field(
        default="",
        description="Subject line or topic of the communication",
    )
    content_summary: str = Field(
        default="",
        description="Non-PHI summary of communication content",
    )
    status: CommunicationStatus = Field(
        default=CommunicationStatus.SENT,
        description="Current delivery/engagement status",
    )
    template_id: str | None = Field(
        default=None,
        description="Template used for this communication",
    )
    campaign_id: str | None = Field(
        default=None,
        description="Campaign this communication belongs to",
    )
    sent_at: datetime | None = Field(
        default=None,
        description="When the communication was sent",
    )
    delivered_at: datetime | None = Field(
        default=None,
        description="When the communication was delivered",
    )
    opened_at: datetime | None = Field(
        default=None,
        description="When the communication was opened/read",
    )
    responded_at: datetime | None = Field(
        default=None,
        description="When the patient responded",
    )
    created_at: datetime = Field(
        ..., description="When this record was created"
    )

    model_config = {"from_attributes": True}


class CommunicationTemplate(BaseModel):
    """A pre-defined communication template."""

    id: str = Field(..., description="Unique template identifier")
    template_type: TemplateType = Field(
        ..., description="Type of template"
    )
    name: str = Field(..., description="Human-readable template name")
    description: str = Field(
        default="",
        description="Description of when to use this template",
    )
    channel: CommunicationChannel = Field(
        ..., description="Default channel for this template"
    )
    subject_template: str = Field(
        default="",
        description="Subject line template with placeholders",
    )
    content_template: str = Field(
        default="",
        description="Content template with placeholders (no PHI)",
    )
    is_active: bool = Field(
        default=True,
        description="Whether this template is currently active",
    )
    created_at: datetime = Field(
        ..., description="When this template was created"
    )

    model_config = {"from_attributes": True}


class PatientPreferences(BaseModel):
    """Patient communication preferences."""

    patient_id: str = Field(..., description="Patient identifier")
    preferred_channel: CommunicationChannel = Field(
        default=CommunicationChannel.EMAIL,
        description="Patient's preferred communication channel",
    )
    alternate_channel: CommunicationChannel | None = Field(
        default=None,
        description="Secondary communication channel",
    )
    frequency_limit: int = Field(
        default=5,
        description="Maximum number of communications per frequency unit",
    )
    frequency_unit: FrequencyUnit = Field(
        default=FrequencyUnit.WEEK,
        description="Time unit for frequency limit",
    )
    opted_out: bool = Field(
        default=False,
        description="Whether the patient has opted out of communications",
    )
    opt_out_date: datetime | None = Field(
        default=None,
        description="When the patient opted out",
    )
    opt_out_reason: str | None = Field(
        default=None,
        description="Reason for opting out",
    )
    quiet_hours_start: int | None = Field(
        default=None,
        description="Start of quiet hours (0-23, local time)",
    )
    quiet_hours_end: int | None = Field(
        default=None,
        description="End of quiet hours (0-23, local time)",
    )
    updated_at: datetime | None = Field(
        default=None,
        description="When preferences were last updated",
    )

    model_config = {"from_attributes": True}


class EngagementScore(BaseModel):
    """Per-patient engagement score and breakdown."""

    patient_id: str = Field(..., description="Patient identifier")
    overall_score: float = Field(
        ...,
        description="Overall engagement score (0-100)",
        ge=0.0,
        le=100.0,
    )
    response_rate: float = Field(
        ...,
        description="Fraction of communications responded to (0-1)",
        ge=0.0,
        le=1.0,
    )
    avg_response_time_hours: float | None = Field(
        default=None,
        description="Average response time in hours",
    )
    appointment_adherence: float = Field(
        default=1.0,
        description="Fraction of appointments attended (0-1)",
        ge=0.0,
        le=1.0,
    )
    channel_preference_satisfaction: float = Field(
        default=1.0,
        description=(
            "Fraction of communications sent via preferred channel (0-1)"
        ),
        ge=0.0,
        le=1.0,
    )
    total_communications: int = Field(
        default=0,
        description="Total communications sent to this patient",
    )
    total_responses: int = Field(
        default=0,
        description="Total responses received from this patient",
    )
    calculated_at: datetime = Field(
        ..., description="When this score was calculated"
    )

    model_config = {"from_attributes": True}


class Campaign(BaseModel):
    """A grouped communication campaign."""

    id: str = Field(..., description="Unique campaign identifier")
    name: str = Field(..., description="Campaign name")
    trial_id: str | None = Field(
        default=None,
        description="Associated trial identifier",
    )
    template_id: str | None = Field(
        default=None,
        description="Template used for campaign communications",
    )
    target_criteria: dict | None = Field(
        default=None,
        description=(
            "Criteria for selecting target patients "
            "(e.g., trial_id, status, location)"
        ),
    )
    schedule: dict | None = Field(
        default=None,
        description="Campaign schedule configuration",
    )
    status: CampaignStatus = Field(
        default=CampaignStatus.DRAFT,
        description="Current campaign status",
    )
    total_sent: int = Field(
        default=0,
        description="Total communications sent in this campaign",
    )
    total_delivered: int = Field(
        default=0,
        description="Total communications delivered",
    )
    total_opened: int = Field(
        default=0,
        description="Total communications opened",
    )
    total_responded: int = Field(
        default=0,
        description="Total responses received",
    )
    created_at: datetime = Field(
        ..., description="When the campaign was created"
    )
    started_at: datetime | None = Field(
        default=None,
        description="When the campaign started sending",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="When the campaign completed",
    )

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Analytics schemas
# ---------------------------------------------------------------------------


class ChannelEffectiveness(BaseModel):
    """Effectiveness metrics for a communication channel."""

    channel: CommunicationChannel = Field(
        ..., description="Communication channel"
    )
    total_sent: int = Field(default=0, description="Total sent")
    total_delivered: int = Field(default=0, description="Total delivered")
    total_opened: int = Field(default=0, description="Total opened")
    total_responded: int = Field(default=0, description="Total responded")
    delivery_rate: float = Field(
        default=0.0,
        description="Delivery rate (delivered / sent)",
    )
    open_rate: float = Field(
        default=0.0,
        description="Open rate (opened / delivered)",
    )
    response_rate: float = Field(
        default=0.0,
        description="Response rate (responded / sent)",
    )


class TemplatePerformance(BaseModel):
    """Performance metrics for a communication template."""

    template_id: str = Field(..., description="Template identifier")
    template_type: TemplateType = Field(
        ..., description="Template type"
    )
    template_name: str = Field(..., description="Template name")
    total_sent: int = Field(default=0, description="Total sent")
    total_responded: int = Field(default=0, description="Total responded")
    response_rate: float = Field(
        default=0.0,
        description="Response rate (responded / sent)",
    )
    avg_response_time_hours: float | None = Field(
        default=None,
        description="Average response time in hours",
    )


class TimePeriodEffectiveness(BaseModel):
    """Response effectiveness by time period (hour or day)."""

    period: str = Field(
        ...,
        description="Time period label (e.g., '09:00', 'Monday')",
    )
    total_sent: int = Field(default=0, description="Total sent in period")
    total_responded: int = Field(
        default=0, description="Total responded in period"
    )
    response_rate: float = Field(
        default=0.0,
        description="Response rate for this period",
    )


class EngagementFunnel(BaseModel):
    """Patient engagement funnel metrics."""

    total_patients: int = Field(
        default=0,
        description="Total patients with communications",
    )
    total_sent: int = Field(
        default=0,
        description="Total communications sent",
    )
    total_delivered: int = Field(
        default=0,
        description="Total delivered",
    )
    total_opened: int = Field(
        default=0,
        description="Total opened",
    )
    total_responded: int = Field(
        default=0,
        description="Total responded",
    )
    delivery_rate: float = Field(
        default=0.0, description="Delivery rate"
    )
    open_rate: float = Field(default=0.0, description="Open rate")
    response_rate: float = Field(
        default=0.0, description="Response rate"
    )


class EngagementAnalytics(BaseModel):
    """Comprehensive engagement analytics."""

    channel_effectiveness: list[ChannelEffectiveness] = Field(
        default_factory=list,
        description="Effectiveness metrics per channel",
    )
    template_performance: list[TemplatePerformance] = Field(
        default_factory=list,
        description="Performance metrics per template",
    )
    best_send_times: list[TimePeriodEffectiveness] = Field(
        default_factory=list,
        description="Response rates by send time",
    )
    engagement_funnel: EngagementFunnel = Field(
        default_factory=EngagementFunnel,
        description="Overall engagement funnel",
    )
    total_communications: int = Field(
        default=0,
        description="Total communications across all channels",
    )
    total_patients: int = Field(
        default=0,
        description="Total unique patients communicated with",
    )
    avg_engagement_score: float = Field(
        default=0.0,
        description="Average engagement score across all patients",
    )
    calculated_at: datetime | None = Field(
        default=None,
        description="When analytics were last calculated",
    )


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class CommunicationCreateRequest(BaseModel):
    """Request to record a new communication."""

    patient_id: str = Field(..., description="Patient identifier")
    trial_id: str | None = Field(
        default=None,
        description="Associated trial identifier",
    )
    channel: CommunicationChannel = Field(
        ..., description="Communication channel"
    )
    direction: CommunicationDirection = Field(
        ..., description="Direction of communication"
    )
    subject: str = Field(
        default="",
        description="Subject line or topic",
    )
    content_summary: str = Field(
        default="",
        description="Non-PHI content summary",
    )
    template_id: str | None = Field(
        default=None,
        description="Template used",
    )
    campaign_id: str | None = Field(
        default=None,
        description="Campaign this belongs to",
    )


class CommunicationUpdateRequest(BaseModel):
    """Request to update a communication status."""

    status: CommunicationStatus = Field(
        ..., description="New status"
    )


class CommunicationListResponse(BaseModel):
    """Paginated list of communications."""

    items: list[CommunicationRecord] = Field(
        default_factory=list,
        description="Communication records",
    )
    total: int = Field(default=0, description="Total matching records")


class PreferencesUpdateRequest(BaseModel):
    """Request to update patient communication preferences."""

    preferred_channel: CommunicationChannel | None = Field(
        default=None,
        description="Preferred channel",
    )
    alternate_channel: CommunicationChannel | None = Field(
        default=None,
        description="Alternate channel",
    )
    frequency_limit: int | None = Field(
        default=None,
        description="Max communications per frequency unit",
    )
    frequency_unit: FrequencyUnit | None = Field(
        default=None,
        description="Frequency unit",
    )
    opted_out: bool | None = Field(
        default=None,
        description="Opt-out flag",
    )
    opt_out_reason: str | None = Field(
        default=None,
        description="Reason for opting out",
    )
    quiet_hours_start: int | None = Field(
        default=None,
        description="Quiet hours start (0-23)",
    )
    quiet_hours_end: int | None = Field(
        default=None,
        description="Quiet hours end (0-23)",
    )


class CampaignCreateRequest(BaseModel):
    """Request to create a new campaign."""

    name: str = Field(..., description="Campaign name")
    trial_id: str | None = Field(
        default=None,
        description="Associated trial",
    )
    template_id: str | None = Field(
        default=None,
        description="Template to use",
    )
    target_criteria: dict | None = Field(
        default=None,
        description="Target patient criteria",
    )
    schedule: dict | None = Field(
        default=None,
        description="Campaign schedule",
    )


class CampaignListResponse(BaseModel):
    """Paginated list of campaigns."""

    items: list[Campaign] = Field(
        default_factory=list,
        description="Campaign records",
    )
    total: int = Field(default=0, description="Total campaigns")
