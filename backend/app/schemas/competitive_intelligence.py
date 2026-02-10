"""Pydantic schemas for Competitive Intelligence (CI-INTEL).

Tracks competing clinical trials, competitor pipeline analysis, market landscape
intelligence, patent landscape monitoring, conference intelligence, and
competitive positioning metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CompetitorStatus(str, Enum):
    """Status of a competitor's program."""

    PRECLINICAL = "preclinical"
    PHASE_I = "phase_i"
    PHASE_II = "phase_ii"
    PHASE_III = "phase_iii"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    WITHDRAWN = "withdrawn"
    DISCONTINUED = "discontinued"


class IntelligenceSource(str, Enum):
    """Source of competitive intelligence."""

    CLINICAL_TRIALS_GOV = "clinical_trials_gov"
    SEC_FILING = "sec_filing"
    PRESS_RELEASE = "press_release"
    CONFERENCE = "conference"
    PATENT_FILING = "patent_filing"
    PUBLICATION = "publication"
    ANALYST_REPORT = "analyst_report"
    FDA_DATABASE = "fda_database"


class ThreatLevel(str, Enum):
    """Competitive threat level."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class PatentStatus(str, Enum):
    """Status of a patent."""

    FILED = "filed"
    PUBLISHED = "published"
    GRANTED = "granted"
    EXPIRED = "expired"
    CHALLENGED = "challenged"


class ConferenceType(str, Enum):
    """Type of scientific conference."""

    MEDICAL = "medical"
    SCIENTIFIC = "scientific"
    REGULATORY = "regulatory"
    INVESTOR = "investor"


class AlertPriority(str, Enum):
    """Priority of a competitive alert."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class CompetitorProgram(BaseModel):
    """A competitor's drug/therapy development program."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique program identifier")
    competitor_name: str = Field(..., description="Competitor company name")
    drug_name: str = Field(..., description="Drug or therapy name")
    mechanism_of_action: str = Field(..., description="Mechanism of action")
    therapeutic_area: str = Field(..., description="Therapeutic area")
    indication: str = Field(..., description="Target indication")
    status: CompetitorStatus = Field(..., description="Development status")
    phase_start_date: datetime | None = Field(None, description="Current phase start date")
    estimated_approval_date: datetime | None = Field(None, description="Estimated approval date")
    trial_count: int = Field(default=0, ge=0, description="Number of active trials")
    patient_enrollment: int = Field(default=0, ge=0, description="Total patient enrollment")
    threat_level: ThreatLevel = Field(..., description="Competitive threat assessment")
    our_competing_program: str | None = Field(
        None, description="Our competing program/drug name"
    )
    key_differentiators: list[str] = Field(
        default_factory=list, description="Key differentiators vs our program"
    )
    notes: str | None = Field(None, description="Analysis notes")
    last_updated: datetime = Field(..., description="Last intelligence update date")
    created_at: datetime = Field(..., description="Record creation timestamp")


class MarketIntelligence(BaseModel):
    """A market intelligence data point."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique intelligence identifier")
    source: IntelligenceSource = Field(..., description="Intelligence source")
    title: str = Field(..., description="Intelligence title/headline")
    summary: str = Field(..., description="Intelligence summary")
    competitor_name: str | None = Field(None, description="Related competitor")
    therapeutic_area: str = Field(..., description="Related therapeutic area")
    event_date: datetime = Field(..., description="Date of the event/publication")
    impact_assessment: str | None = Field(None, description="Impact assessment narrative")
    threat_level: ThreatLevel = Field(default=ThreatLevel.LOW, description="Threat level")
    action_required: bool = Field(default=False, description="Whether action is required")
    action_items: list[str] = Field(default_factory=list, description="Required actions")
    source_url: str | None = Field(None, description="Source URL")
    analyzed_by: str | None = Field(None, description="Analyst who reviewed")
    created_at: datetime = Field(..., description="Record creation timestamp")


class PatentLandscape(BaseModel):
    """A patent in the competitive landscape."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique patent record identifier")
    patent_number: str = Field(..., description="Patent number")
    title: str = Field(..., description="Patent title")
    assignee: str = Field(..., description="Patent assignee/owner")
    filing_date: datetime = Field(..., description="Patent filing date")
    grant_date: datetime | None = Field(None, description="Patent grant date")
    expiry_date: datetime | None = Field(None, description="Patent expiry date")
    status: PatentStatus = Field(..., description="Patent status")
    therapeutic_area: str = Field(..., description="Related therapeutic area")
    claims_summary: str = Field(..., description="Summary of key claims")
    relevance_to_portfolio: str = Field(
        ..., description="Relevance to our portfolio"
    )
    freedom_to_operate: bool | None = Field(
        None, description="Whether we have freedom to operate"
    )
    reviewed_by: str | None = Field(None, description="IP attorney who reviewed")


class ConferenceIntelligence(BaseModel):
    """Intelligence gathered from a scientific conference."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique conference intelligence identifier")
    conference_name: str = Field(..., description="Conference name")
    conference_type: ConferenceType = Field(..., description="Type of conference")
    conference_date: datetime = Field(..., description="Conference date")
    location: str = Field(..., description="Conference location")
    presentation_title: str = Field(..., description="Presentation or poster title")
    presenter: str = Field(..., description="Presenter name")
    company: str | None = Field(None, description="Presenting company")
    therapeutic_area: str = Field(..., description="Therapeutic area")
    key_findings: list[str] = Field(default_factory=list, description="Key findings")
    competitive_implications: str | None = Field(
        None, description="Implications for our programs"
    )
    threat_level: ThreatLevel = Field(default=ThreatLevel.LOW, description="Threat assessment")
    attended_by: str = Field(..., description="Our attendee")


class CompetitiveAlert(BaseModel):
    """A competitive intelligence alert."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique alert identifier")
    title: str = Field(..., description="Alert title")
    description: str = Field(..., description="Alert description")
    competitor_name: str | None = Field(None, description="Related competitor")
    therapeutic_area: str = Field(..., description="Related therapeutic area")
    priority: AlertPriority = Field(..., description="Alert priority")
    source: IntelligenceSource = Field(..., description="Information source")
    created_date: datetime = Field(..., description="Date alert was created")
    acknowledged: bool = Field(default=False, description="Whether acknowledged")
    acknowledged_by: str | None = Field(None, description="Person who acknowledged")
    action_taken: str | None = Field(None, description="Action taken in response")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class CompetitorProgramCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    competitor_name: str
    drug_name: str
    mechanism_of_action: str
    therapeutic_area: str
    indication: str
    status: CompetitorStatus
    threat_level: ThreatLevel
    our_competing_program: str | None = None
    key_differentiators: list[str] = Field(default_factory=list)
    notes: str | None = None


class CompetitorProgramUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: CompetitorStatus | None = None
    threat_level: ThreatLevel | None = None
    trial_count: int | None = None
    patient_enrollment: int | None = None
    estimated_approval_date: datetime | None = None
    key_differentiators: list[str] | None = None
    notes: str | None = None


class MarketIntelligenceCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    source: IntelligenceSource
    title: str
    summary: str
    competitor_name: str | None = None
    therapeutic_area: str
    event_date: datetime
    impact_assessment: str | None = None
    threat_level: ThreatLevel = ThreatLevel.LOW
    source_url: str | None = None
    analyzed_by: str | None = None


class MarketIntelligenceUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    title: str | None = None
    summary: str | None = None
    threat_level: ThreatLevel | None = None
    action_required: bool | None = None
    action_items: list[str] | None = None
    impact_assessment: str | None = None


class PatentLandscapeCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    patent_number: str
    title: str
    assignee: str
    filing_date: datetime
    grant_date: datetime | None = None
    expiry_date: datetime | None = None
    status: PatentStatus
    therapeutic_area: str
    claims_summary: str
    relevance_to_portfolio: str
    freedom_to_operate: bool | None = None
    reviewed_by: str | None = None


class PatentLandscapeUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: PatentStatus | None = None
    grant_date: datetime | None = None
    expiry_date: datetime | None = None
    freedom_to_operate: bool | None = None
    reviewed_by: str | None = None


class ConferenceIntelligenceCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    conference_name: str
    conference_type: ConferenceType
    conference_date: datetime
    location: str
    presentation_title: str
    presenter: str
    company: str | None = None
    therapeutic_area: str
    key_findings: list[str] = Field(default_factory=list)
    competitive_implications: str | None = None
    threat_level: ThreatLevel = ThreatLevel.LOW
    attended_by: str


class ConferenceIntelligenceUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    key_findings: list[str] | None = None
    competitive_implications: str | None = None
    threat_level: ThreatLevel | None = None


class CompetitiveAlertCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    title: str
    description: str
    competitor_name: str | None = None
    therapeutic_area: str
    priority: AlertPriority
    source: IntelligenceSource


class CompetitiveAlertUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    priority: AlertPriority | None = None
    acknowledged: bool | None = None
    acknowledged_by: str | None = None
    action_taken: str | None = None


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class CompetitorProgramListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CompetitorProgram] = Field(default_factory=list)
    total: int = Field(ge=0)


class MarketIntelligenceListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[MarketIntelligence] = Field(default_factory=list)
    total: int = Field(ge=0)


class PatentLandscapeListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[PatentLandscape] = Field(default_factory=list)
    total: int = Field(ge=0)


class ConferenceIntelligenceListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ConferenceIntelligence] = Field(default_factory=list)
    total: int = Field(ge=0)


class CompetitiveAlertListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CompetitiveAlert] = Field(default_factory=list)
    total: int = Field(ge=0)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class CompetitiveIntelligenceMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_competitor_programs: int = Field(ge=0)
    programs_by_status: dict[str, int] = Field(default_factory=dict)
    programs_by_threat_level: dict[str, int] = Field(default_factory=dict)
    programs_by_therapeutic_area: dict[str, int] = Field(default_factory=dict)
    total_market_intel: int = Field(ge=0)
    intel_by_source: dict[str, int] = Field(default_factory=dict)
    total_patents: int = Field(ge=0)
    patents_by_status: dict[str, int] = Field(default_factory=dict)
    total_conference_intel: int = Field(ge=0)
    total_alerts: int = Field(ge=0)
    unacknowledged_alerts: int = Field(ge=0)
    high_priority_alerts: int = Field(ge=0)
    critical_threats: int = Field(ge=0)
