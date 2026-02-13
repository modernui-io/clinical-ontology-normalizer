"""Pydantic schemas for Site Communication Management (SCM-MGT).

Manages site communication operations: communication logs, newsletter
distributions, site query threads, site broadcast alerts, and communication
metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class CommunicationChannel(str, Enum):
    EMAIL = "email"
    PORTAL = "portal"
    PHONE = "phone"
    VIDEO_CONFERENCE = "video_conference"
    LETTER = "letter"
    IN_PERSON = "in_person"


class CommunicationPriority(str, Enum):
    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    INFORMATIONAL = "informational"


class QueryStatus(str, Enum):
    OPEN = "open"
    PENDING_RESPONSE = "pending_response"
    RESPONDED = "responded"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"


class AlertLevel(str, Enum):
    EMERGENCY = "emergency"
    CRITICAL = "critical"
    WARNING = "warning"
    ADVISORY = "advisory"
    INFORMATIONAL = "informational"
    ALL_CLEAR = "all_clear"


class DistributionStatus(str, Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    SENT = "sent"
    DELIVERED = "delivered"
    PARTIALLY_DELIVERED = "partially_delivered"
    FAILED = "failed"


# --- Main entities ---

class CommunicationLog(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    communication_channel: CommunicationChannel
    communication_priority: CommunicationPriority = CommunicationPriority.NORMAL
    subject: str
    summary: str
    direction: str = "outbound"
    initiated_by: str
    recipient_name: str
    communication_date: datetime
    duration_minutes: int = Field(ge=0, default=0)
    follow_up_required: bool = False
    follow_up_date: datetime | None = None
    attachments_count: int = Field(ge=0, default=0)
    notes: str | None = None
    created_at: datetime


class NewsletterDistribution(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    newsletter_title: str
    edition_number: str
    distribution_status: DistributionStatus = DistributionStatus.DRAFT
    target_audience: str
    recipients_count: int = Field(ge=0, default=0)
    delivered_count: int = Field(ge=0, default=0)
    opened_count: int = Field(ge=0, default=0)
    scheduled_date: datetime | None = None
    sent_date: datetime | None = None
    authored_by: str
    approved_by: str | None = None
    content_topics: str | None = None
    notes: str | None = None
    created_at: datetime


class SiteQueryThread(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    query_status: QueryStatus = QueryStatus.OPEN
    subject: str
    query_text: str
    queried_by: str
    assigned_to: str | None = None
    query_date: datetime
    response_text: str | None = None
    response_date: datetime | None = None
    response_time_hours: float = Field(ge=0, default=0.0)
    escalated_to: str | None = None
    resolution_date: datetime | None = None
    satisfaction_rating: int | None = None
    notes: str | None = None
    created_at: datetime


class SiteBroadcastAlert(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    alert_level: AlertLevel = AlertLevel.INFORMATIONAL
    alert_title: str
    alert_message: str
    issued_by: str
    issued_date: datetime
    expiry_date: datetime | None = None
    sites_targeted: int = Field(ge=0, default=0)
    sites_acknowledged: int = Field(ge=0, default=0)
    requires_acknowledgment: bool = True
    action_required: str | None = None
    action_deadline: datetime | None = None
    supersedes_alert_id: str | None = None
    notes: str | None = None
    created_at: datetime


# --- Create / Update schemas ---

class CommunicationLogCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    communication_channel: CommunicationChannel
    subject: str
    summary: str
    initiated_by: str
    recipient_name: str
    communication_date: datetime
    communication_priority: CommunicationPriority = CommunicationPriority.NORMAL


class CommunicationLogUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    duration_minutes: int | None = None
    follow_up_required: bool | None = None
    follow_up_date: datetime | None = None
    attachments_count: int | None = None
    notes: str | None = None


class NewsletterDistributionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    newsletter_title: str
    edition_number: str
    target_audience: str
    authored_by: str
    recipients_count: int = Field(ge=0, default=0)


class NewsletterDistributionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    distribution_status: DistributionStatus | None = None
    approved_by: str | None = None
    sent_date: datetime | None = None
    delivered_count: int | None = None
    opened_count: int | None = None
    content_topics: str | None = None
    notes: str | None = None


class SiteQueryThreadCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    subject: str
    query_text: str
    queried_by: str
    query_date: datetime


class SiteQueryThreadUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    query_status: QueryStatus | None = None
    assigned_to: str | None = None
    response_text: str | None = None
    response_date: datetime | None = None
    escalated_to: str | None = None
    satisfaction_rating: int | None = None
    notes: str | None = None


class SiteBroadcastAlertCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    alert_level: AlertLevel = AlertLevel.INFORMATIONAL
    alert_title: str
    alert_message: str
    issued_by: str
    issued_date: datetime
    sites_targeted: int = Field(ge=0, default=0)


class SiteBroadcastAlertUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    expiry_date: datetime | None = None
    sites_acknowledged: int | None = None
    action_required: str | None = None
    action_deadline: datetime | None = None
    notes: str | None = None


# --- List responses ---

class CommunicationLogListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CommunicationLog] = Field(default_factory=list)
    total: int = Field(ge=0)


class NewsletterDistributionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[NewsletterDistribution] = Field(default_factory=list)
    total: int = Field(ge=0)


class SiteQueryThreadListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SiteQueryThread] = Field(default_factory=list)
    total: int = Field(ge=0)


class SiteBroadcastAlertListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SiteBroadcastAlert] = Field(default_factory=list)
    total: int = Field(ge=0)


# --- Metrics ---

class SiteCommunicationMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_communications: int = Field(ge=0)
    communications_by_channel: dict[str, int] = Field(default_factory=dict)
    communications_by_priority: dict[str, int] = Field(default_factory=dict)
    total_newsletters: int = Field(ge=0)
    newsletters_by_status: dict[str, int] = Field(default_factory=dict)
    avg_newsletter_open_rate: float = Field(ge=0)
    total_queries: int = Field(ge=0)
    queries_by_status: dict[str, int] = Field(default_factory=dict)
    avg_query_response_hours: float = Field(ge=0)
    total_alerts: int = Field(ge=0)
    alerts_by_level: dict[str, int] = Field(default_factory=dict)
    alert_acknowledgment_rate: float = Field(ge=0)
