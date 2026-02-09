"""Pydantic schemas for Incident Response Playbooks (CISO-12).

Structured playbooks for pharma-grade incident response management with
automated escalation, regulatory notification tracking, SLA enforcement,
and post-incident review workflows.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class IncidentSeverity(str, Enum):
    """Severity classification for security incidents."""

    SEV1_CRITICAL = "SEV1_CRITICAL"
    SEV2_HIGH = "SEV2_HIGH"
    SEV3_MEDIUM = "SEV3_MEDIUM"
    SEV4_LOW = "SEV4_LOW"


class IncidentCategory(str, Enum):
    """Category of security incident."""

    DATA_BREACH = "DATA_BREACH"
    RANSOMWARE = "RANSOMWARE"
    INSIDER_THREAT = "INSIDER_THREAT"
    PHISHING = "PHISHING"
    DDOS = "DDOS"
    SUPPLY_CHAIN = "SUPPLY_CHAIN"
    ZERO_DAY = "ZERO_DAY"
    UNAUTHORIZED_ACCESS = "UNAUTHORIZED_ACCESS"
    DATA_LOSS = "DATA_LOSS"
    SYSTEM_COMPROMISE = "SYSTEM_COMPROMISE"
    COMPLIANCE_VIOLATION = "COMPLIANCE_VIOLATION"


class IncidentPhase(str, Enum):
    """Current phase of incident lifecycle."""

    DETECTION = "DETECTION"
    TRIAGE = "TRIAGE"
    CONTAINMENT = "CONTAINMENT"
    ERADICATION = "ERADICATION"
    RECOVERY = "RECOVERY"
    POST_INCIDENT = "POST_INCIDENT"
    CLOSED = "CLOSED"


class PlaybookType(str, Enum):
    """Type of incident response playbook."""

    DATA_BREACH = "DATA_BREACH"
    RANSOMWARE = "RANSOMWARE"
    INSIDER_THREAT = "INSIDER_THREAT"
    PHISHING = "PHISHING"
    DDOS = "DDOS"
    SUPPLY_CHAIN = "SUPPLY_CHAIN"
    ZERO_DAY = "ZERO_DAY"
    UNAUTHORIZED_ACCESS = "UNAUTHORIZED_ACCESS"
    GENERIC = "GENERIC"


class NotificationType(str, Enum):
    """Regulatory or stakeholder notification type with compliance deadlines."""

    HIPAA_BREACH = "HIPAA_BREACH"              # 60 days
    GDPR_BREACH = "GDPR_BREACH"                # 72 hours
    STATE_BREACH = "STATE_BREACH"
    FDA_NOTIFICATION = "FDA_NOTIFICATION"
    INTERNAL_STAKEHOLDER = "INTERNAL_STAKEHOLDER"
    LAW_ENFORCEMENT = "LAW_ENFORCEMENT"
    CYBER_INSURANCE = "CYBER_INSURANCE"


class NotificationStatus(str, Enum):
    """Status of a regulatory notification."""

    PENDING = "PENDING"
    SENT = "SENT"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    OVERDUE = "OVERDUE"


class EscalationLevel(str, Enum):
    """Escalation tiers for incident management."""

    L1_SOC = "L1_SOC"
    L2_IR_TEAM = "L2_IR_TEAM"
    L3_CISO = "L3_CISO"
    L4_EXECUTIVE = "L4_EXECUTIVE"
    L5_BOARD = "L5_BOARD"


# ---------------------------------------------------------------------------
# SLA targets (minutes)
# ---------------------------------------------------------------------------

SLA_TARGETS: dict[str, dict[str, int]] = {
    "SEV1_CRITICAL": {
        "triage_minutes": 15,
        "containment_minutes": 60,
        "resolution_minutes": 240,
    },
    "SEV2_HIGH": {
        "triage_minutes": 30,
        "containment_minutes": 240,
        "resolution_minutes": 1440,
    },
    "SEV3_MEDIUM": {
        "triage_minutes": 120,
        "containment_minutes": 1440,
        "resolution_minutes": 4320,
    },
    "SEV4_LOW": {
        "triage_minutes": 480,
        "containment_minutes": 4320,
        "resolution_minutes": 10080,
    },
}

# Notification deadline hours by type
NOTIFICATION_DEADLINES: dict[str, int] = {
    "HIPAA_BREACH": 1440,           # 60 days = 1440 hours
    "GDPR_BREACH": 72,              # 72 hours
    "STATE_BREACH": 720,            # 30 days = 720 hours
    "FDA_NOTIFICATION": 360,        # 15 days = 360 hours
    "INTERNAL_STAKEHOLDER": 24,     # 24 hours
    "LAW_ENFORCEMENT": 168,         # 7 days = 168 hours
    "CYBER_INSURANCE": 48,          # 48 hours
}


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------


class PlaybookStep(BaseModel):
    """A single step in an incident response playbook."""

    model_config = ConfigDict(from_attributes=True)

    step_number: int = Field(..., description="Step sequence number")
    title: str = Field(..., description="Step title")
    description: str = Field(..., description="Detailed step instructions")
    responsible_role: str = Field(..., description="Role responsible for this step")
    time_limit_minutes: int = Field(..., description="Maximum time for this step in minutes")
    automated: bool = Field(False, description="Whether this step can be automated")
    checklist_items: list[str] = Field(default_factory=list, description="Checklist items for the step")


class Playbook(BaseModel):
    """Incident response playbook template."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique playbook ID")
    playbook_type: PlaybookType = Field(..., description="Type of playbook")
    title: str = Field(..., description="Playbook title")
    description: str = Field(..., description="Playbook description")
    severity_threshold: IncidentSeverity = Field(..., description="Minimum severity for this playbook")
    steps: list[PlaybookStep] = Field(default_factory=list, description="Ordered steps")
    last_tested: Optional[datetime] = Field(None, description="Last tabletop exercise date")
    test_frequency_days: int = Field(90, description="Required test frequency in days")
    version: str = Field("1.0", description="Playbook version")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class IncidentEvent(BaseModel):
    """Timeline event within an incident."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique event ID")
    incident_id: str = Field(..., description="Parent incident ID")
    timestamp: datetime = Field(..., description="When the event occurred")
    phase: IncidentPhase = Field(..., description="Incident phase when event occurred")
    description: str = Field(..., description="Event description")
    actor: str = Field(..., description="Person or system that performed the action")
    evidence_refs: list[str] = Field(default_factory=list, description="References to evidence artifacts")


class RegulatoryNotification(BaseModel):
    """Regulatory notification tracking record."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique notification ID")
    incident_id: str = Field(..., description="Parent incident ID")
    notification_type: NotificationType = Field(..., description="Type of notification")
    deadline: datetime = Field(..., description="Notification deadline")
    sent_at: Optional[datetime] = Field(None, description="When notification was sent")
    recipient: str = Field(..., description="Notification recipient")
    status: NotificationStatus = Field(NotificationStatus.PENDING, description="Current status")
    content_summary: str = Field("", description="Summary of notification content")


class IncidentRecord(BaseModel):
    """Full incident record with all related data."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique incident ID")
    title: str = Field(..., description="Incident title")
    description: str = Field(..., description="Incident description")
    severity: IncidentSeverity = Field(..., description="Severity classification")
    category: IncidentCategory = Field(..., description="Incident category")
    phase: IncidentPhase = Field(..., description="Current incident phase")
    detected_at: datetime = Field(..., description="When the incident was detected")
    reported_by: str = Field(..., description="Who reported the incident")
    assigned_to: Optional[str] = Field(None, description="Current assignee")
    playbook_id: Optional[str] = Field(None, description="Associated playbook")
    events: list[IncidentEvent] = Field(default_factory=list, description="Timeline events")
    notifications: list[RegulatoryNotification] = Field(default_factory=list, description="Regulatory notifications")
    containment_time_minutes: Optional[float] = Field(None, description="Time to containment in minutes")
    resolution_time_minutes: Optional[float] = Field(None, description="Time to resolution in minutes")
    root_cause: Optional[str] = Field(None, description="Root cause analysis")
    lessons_learned: Optional[str] = Field(None, description="Lessons learned")
    affected_systems: list[str] = Field(default_factory=list, description="Affected systems")
    affected_patients_count: int = Field(0, description="Number of affected patients")
    data_compromised: bool = Field(False, description="Whether data was compromised")
    escalation_level: EscalationLevel = Field(EscalationLevel.L1_SOC, description="Current escalation level")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    closed_at: Optional[datetime] = Field(None, description="When the incident was closed")


class PostIncidentReview(BaseModel):
    """Post-incident review record."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique review ID")
    incident_id: str = Field(..., description="Related incident ID")
    review_date: datetime = Field(..., description="Date of review meeting")
    participants: list[str] = Field(default_factory=list, description="Review participants")
    findings: list[str] = Field(default_factory=list, description="Key findings")
    action_items: list[str] = Field(default_factory=list, description="Action items from the review")
    effectiveness_rating: float = Field(..., ge=0.0, le=10.0, description="Response effectiveness (0-10)")
    recurrence_risk: str = Field(..., description="Risk of recurrence (LOW, MEDIUM, HIGH)")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class IncidentCreateRequest(BaseModel):
    """Request to create a new incident."""

    model_config = ConfigDict(from_attributes=True)

    title: str = Field(..., description="Incident title")
    description: str = Field(..., description="Incident description")
    severity: IncidentSeverity = Field(..., description="Severity classification")
    category: IncidentCategory = Field(..., description="Incident category")
    reported_by: str = Field(..., description="Reporter name")
    affected_systems: list[str] = Field(default_factory=list, description="Affected systems")
    affected_patients_count: int = Field(0, ge=0, description="Number of affected patients")
    data_compromised: bool = Field(False, description="Whether data was compromised")


class IncidentUpdateRequest(BaseModel):
    """Request to update an incident."""

    model_config = ConfigDict(from_attributes=True)

    title: Optional[str] = Field(None, description="Updated title")
    description: Optional[str] = Field(None, description="Updated description")
    severity: Optional[IncidentSeverity] = Field(None, description="Updated severity")
    phase: Optional[IncidentPhase] = Field(None, description="Target phase for transition")
    assigned_to: Optional[str] = Field(None, description="New assignee")
    playbook_id: Optional[str] = Field(None, description="Associated playbook")
    root_cause: Optional[str] = Field(None, description="Root cause analysis")
    lessons_learned: Optional[str] = Field(None, description="Lessons learned")
    affected_systems: Optional[list[str]] = Field(None, description="Updated affected systems")
    affected_patients_count: Optional[int] = Field(None, ge=0, description="Updated patient count")
    data_compromised: Optional[bool] = Field(None, description="Updated data compromised flag")
    escalation_level: Optional[EscalationLevel] = Field(None, description="Updated escalation level")


class IncidentListResponse(BaseModel):
    """Paginated incident list response."""

    model_config = ConfigDict(from_attributes=True)

    items: list[IncidentRecord] = Field(..., description="Incident records")
    total: int = Field(..., description="Total matching records")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Page offset")


class EventCreateRequest(BaseModel):
    """Request to log an incident event."""

    model_config = ConfigDict(from_attributes=True)

    description: str = Field(..., description="Event description")
    actor: str = Field(..., description="Person or system performing the action")
    evidence_refs: list[str] = Field(default_factory=list, description="Evidence references")


class NotificationCreateRequest(BaseModel):
    """Request to create a regulatory notification."""

    model_config = ConfigDict(from_attributes=True)

    notification_type: NotificationType = Field(..., description="Notification type")
    recipient: str = Field(..., description="Recipient")
    content_summary: str = Field("", description="Content summary")


class NotificationSendRequest(BaseModel):
    """Request to mark a notification as sent."""

    model_config = ConfigDict(from_attributes=True)

    sent_at: Optional[datetime] = Field(None, description="Override send timestamp (defaults to now)")


class PostIncidentReviewRequest(BaseModel):
    """Request to create a post-incident review."""

    model_config = ConfigDict(from_attributes=True)

    participants: list[str] = Field(..., description="Review participants")
    findings: list[str] = Field(..., description="Key findings")
    action_items: list[str] = Field(..., description="Action items")
    effectiveness_rating: float = Field(..., ge=0.0, le=10.0, description="Response effectiveness (0-10)")
    recurrence_risk: str = Field(..., description="Recurrence risk (LOW, MEDIUM, HIGH)")


class IncidentMetrics(BaseModel):
    """Aggregated incident response metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_incidents: int = Field(..., description="Total incidents")
    active_incidents: int = Field(..., description="Currently active incidents")
    closed_incidents: int = Field(..., description="Closed incidents")
    by_severity: dict[str, int] = Field(default_factory=dict, description="Count by severity")
    by_category: dict[str, int] = Field(default_factory=dict, description="Count by category")
    mttd_minutes: Optional[float] = Field(None, description="Mean time to detect (minutes)")
    mttc_minutes: Optional[float] = Field(None, description="Mean time to contain (minutes)")
    mttr_minutes: Optional[float] = Field(None, description="Mean time to resolve (minutes)")
    sla_compliance_rate: float = Field(1.0, description="Percentage of incidents meeting SLA")
    overdue_notifications: int = Field(0, description="Number of overdue notifications")
    playbook_coverage_rate: float = Field(0.0, description="Percentage of incidents with playbooks")
    reviews_completed: int = Field(0, description="Number of post-incident reviews completed")


class EscalationContact(BaseModel):
    """Contact information for an escalation level."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Contact name")
    role: str = Field(..., description="Contact role")
    email: str = Field(..., description="Contact email")
    phone: str = Field(..., description="Contact phone")
    notification_methods: list[str] = Field(default_factory=list, description="Notification methods")


class EscalationMatrix(BaseModel):
    """Escalation matrix mapping severity to contacts."""

    model_config = ConfigDict(from_attributes=True)

    severity: IncidentSeverity = Field(..., description="Severity level")
    escalation_level: EscalationLevel = Field(..., description="Escalation level")
    contacts: list[EscalationContact] = Field(default_factory=list, description="Contacts at this level")
    auto_escalate_after_minutes: int = Field(..., description="Auto-escalate after this many minutes")


class PlaybookTestResult(BaseModel):
    """Result of a playbook test / tabletop exercise."""

    model_config = ConfigDict(from_attributes=True)

    playbook_id: str = Field(..., description="Tested playbook ID")
    tested_at: datetime = Field(..., description="Test timestamp")
    participants: list[str] = Field(default_factory=list, description="Test participants")
    findings: list[str] = Field(default_factory=list, description="Findings from test")
    passed: bool = Field(..., description="Whether the test passed")
    next_test_due: datetime = Field(..., description="Next test due date")
