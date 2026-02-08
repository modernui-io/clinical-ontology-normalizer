"""Pydantic schemas for the Site Referral Network and Trial Enrollment Workflow.

VP-Product-5: Manages patient referrals between sites and trials,
site matching, enrollment workflow tracking, and network analytics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ReferralStatus(str, Enum):
    """Referral lifecycle status."""

    INITIATED = "initiated"
    PENDING_REVIEW = "pending_review"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DECLINED = "declined"
    CANCELLED = "cancelled"


class ReferralPriority(str, Enum):
    """Referral urgency level."""

    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class EnrollmentStage(str, Enum):
    """Patient enrollment workflow stages (distinct from trial EnrollmentStatus)."""

    CANDIDATE = "candidate"
    REFERRED = "referred"
    SCREENED = "screened"
    ELIGIBLE = "eligible"
    CONSENTED = "consented"
    ENROLLED = "enrolled"
    ACTIVE = "active"
    WITHDRAWN = "withdrawn"


# Valid transitions map: current_stage -> [allowed_next_stages]
ENROLLMENT_STAGE_TRANSITIONS: dict[EnrollmentStage, list[EnrollmentStage]] = {
    EnrollmentStage.CANDIDATE: [EnrollmentStage.REFERRED, EnrollmentStage.WITHDRAWN],
    EnrollmentStage.REFERRED: [EnrollmentStage.SCREENED, EnrollmentStage.WITHDRAWN],
    EnrollmentStage.SCREENED: [EnrollmentStage.ELIGIBLE, EnrollmentStage.WITHDRAWN],
    EnrollmentStage.ELIGIBLE: [EnrollmentStage.CONSENTED, EnrollmentStage.WITHDRAWN],
    EnrollmentStage.CONSENTED: [EnrollmentStage.ENROLLED, EnrollmentStage.WITHDRAWN],
    EnrollmentStage.ENROLLED: [EnrollmentStage.ACTIVE, EnrollmentStage.WITHDRAWN],
    EnrollmentStage.ACTIVE: [EnrollmentStage.WITHDRAWN],
    EnrollmentStage.WITHDRAWN: [],
}

# Valid referral status transitions
REFERRAL_STATUS_TRANSITIONS: dict[ReferralStatus, list[ReferralStatus]] = {
    ReferralStatus.INITIATED: [ReferralStatus.PENDING_REVIEW, ReferralStatus.CANCELLED],
    ReferralStatus.PENDING_REVIEW: [
        ReferralStatus.ACCEPTED,
        ReferralStatus.DECLINED,
        ReferralStatus.CANCELLED,
    ],
    ReferralStatus.ACCEPTED: [ReferralStatus.IN_PROGRESS, ReferralStatus.CANCELLED],
    ReferralStatus.IN_PROGRESS: [ReferralStatus.COMPLETED, ReferralStatus.CANCELLED],
    ReferralStatus.COMPLETED: [],
    ReferralStatus.DECLINED: [],
    ReferralStatus.CANCELLED: [],
}


# ---------------------------------------------------------------------------
# Referral schemas
# ---------------------------------------------------------------------------


class ReferralCreate(BaseModel):
    """Schema for creating a new referral."""

    patient_id: str = Field(..., description="Patient being referred")
    source_site_id: str = Field(..., description="Site initiating the referral")
    destination_site_id: str = Field(..., description="Site receiving the referral")
    trial_id: str = Field(..., description="Trial the referral is for")
    referring_provider: str | None = Field(None, description="Name of referring clinician")
    reason: str | None = Field(None, description="Reason for referral")
    priority: ReferralPriority = Field(
        default=ReferralPriority.NORMAL,
        description="Referral urgency level",
    )
    notes: str | None = Field(None, description="Additional notes")


class ReferralUpdate(BaseModel):
    """Schema for updating a referral."""

    status: ReferralStatus | None = Field(None, description="New status")
    priority: ReferralPriority | None = Field(None, description="Updated priority")
    notes: str | None = Field(None, description="Updated notes")
    referring_provider: str | None = Field(None, description="Updated referring provider")
    reason: str | None = Field(None, description="Updated reason")


class ReferralResponse(BaseModel):
    """Full referral record response."""

    id: str
    patient_id: str
    source_site_id: str
    destination_site_id: str
    trial_id: str
    referring_provider: str | None = None
    reason: str | None = None
    status: ReferralStatus
    priority: ReferralPriority
    created_at: str
    updated_at: str
    accepted_at: str | None = None
    completed_at: str | None = None
    notes: str | None = None


class ReferralListResponse(BaseModel):
    """Paginated list of referrals."""

    referrals: list[ReferralResponse]
    total: int
    offset: int
    limit: int


# ---------------------------------------------------------------------------
# Site suggestion schemas
# ---------------------------------------------------------------------------


class SiteSuggestionRequest(BaseModel):
    """Request for site matching suggestions."""

    patient_id: str = Field(..., description="Patient to find best sites for")
    trial_id: str = Field(..., description="Trial to find sites for")
    patient_lat: float | None = Field(None, description="Patient latitude for distance scoring")
    patient_lon: float | None = Field(None, description="Patient longitude for distance scoring")
    max_results: int = Field(default=5, ge=1, le=20, description="Maximum suggestions to return")


class SiteSuggestion(BaseModel):
    """A suggested site for a patient/trial combination."""

    site_id: str
    site_name: str
    city: str | None = None
    state: str | None = None
    overall_score: float = Field(ge=0.0, le=1.0, description="Weighted composite score")
    distance_score: float = Field(ge=0.0, le=1.0, description="Geographic proximity score (1.0 = closest)")
    capacity_score: float = Field(ge=0.0, le=1.0, description="Available capacity score (1.0 = most capacity)")
    performance_score: float = Field(ge=0.0, le=1.0, description="Historical screening success rate")
    specialty_score: float = Field(ge=0.0, le=1.0, description="Specialty match score")
    current_enrollment: int = Field(default=0, description="Current enrollment at this site")
    enrollment_target: int = Field(default=0, description="Enrollment target for this site")
    reasoning: str | None = Field(None, description="Explanation of why this site was suggested")


class SiteSuggestionResponse(BaseModel):
    """Response containing site suggestions."""

    patient_id: str
    trial_id: str
    suggestions: list[SiteSuggestion]
    total_sites_evaluated: int


# ---------------------------------------------------------------------------
# Enrollment tracking schemas
# ---------------------------------------------------------------------------


class EnrollmentMilestone(BaseModel):
    """A single enrollment milestone timestamp."""

    stage: EnrollmentStage
    timestamp: str
    notes: str | None = None


class EnrollmentTracking(BaseModel):
    """Full enrollment tracking for a patient/trial pair."""

    patient_id: str
    trial_id: str
    current_stage: EnrollmentStage
    milestones: list[EnrollmentMilestone] = Field(default_factory=list)
    time_to_enrollment_days: float | None = Field(
        None,
        description="Days from CANDIDATE to ENROLLED (None if not yet enrolled)",
    )
    created_at: str
    updated_at: str


class EnrollmentAdvanceRequest(BaseModel):
    """Request to advance a patient's enrollment stage."""

    notes: str | None = Field(None, description="Notes for this stage transition")


class EnrollmentAdvanceResponse(BaseModel):
    """Response after advancing enrollment stage."""

    patient_id: str
    trial_id: str
    previous_stage: EnrollmentStage
    current_stage: EnrollmentStage
    milestone: EnrollmentMilestone


# ---------------------------------------------------------------------------
# Network analytics schemas
# ---------------------------------------------------------------------------


class SiteReferralMetrics(BaseModel):
    """Referral metrics for a single site."""

    site_id: str
    site_name: str
    referrals_sent: int = 0
    referrals_received: int = 0
    acceptance_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Fraction of received referrals accepted")
    avg_time_to_accept_hours: float | None = Field(None, description="Average hours to accept a referral")
    avg_time_to_complete_hours: float | None = Field(None, description="Average hours to complete a referral")
    conversion_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fraction of referrals that led to enrollment",
    )


class NetworkAnalytics(BaseModel):
    """Aggregate referral network analytics."""

    total_referrals: int = 0
    total_active_referrals: int = 0
    total_completed_referrals: int = 0
    total_declined_referrals: int = 0
    overall_acceptance_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    overall_conversion_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    avg_time_to_accept_hours: float | None = None
    avg_time_to_complete_hours: float | None = None
    site_metrics: list[SiteReferralMetrics] = Field(default_factory=list)
    top_referring_sites: list[SiteReferralMetrics] = Field(
        default_factory=list,
        description="Sites with the most outgoing referrals",
    )
    referral_volume_by_trial: dict[str, int] = Field(
        default_factory=dict,
        description="Referral count per trial_id",
    )
