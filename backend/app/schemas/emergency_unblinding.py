"""Pydantic schemas for Emergency Unblinding (EMRG-UBL).

Manages emergency unblinding operations: unblinding requests, approval
workflows, unblinding notifications, audit log entries, and unblinding metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class UnblindingReason(str, Enum):
    MEDICAL_EMERGENCY = "medical_emergency"
    SERIOUS_ADVERSE_EVENT = "serious_adverse_event"
    OVERDOSE = "overdose"
    PREGNANCY = "pregnancy"
    REGULATORY_REQUEST = "regulatory_request"
    INVESTIGATOR_DECISION = "investigator_decision"


class RequestStatus(str, Enum):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    DENIED = "denied"
    EXECUTED = "executed"
    CANCELLED = "cancelled"


class ApprovalDecision(str, Enum):
    APPROVED = "approved"
    DENIED = "denied"
    DEFERRED = "deferred"
    CONDITIONAL = "conditional"
    ESCALATED = "escalated"


class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    PHONE = "phone"
    FAX = "fax"
    SYSTEM_ALERT = "system_alert"
    IN_PERSON = "in_person"


class AuditAction(str, Enum):
    REQUEST_CREATED = "request_created"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    TREATMENT_REVEALED = "treatment_revealed"
    NOTIFICATION_SENT = "notification_sent"
    DOCUMENTATION_FILED = "documentation_filed"


# --- Main entities ---

class UnblindingRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    subject_id: str
    requestor_name: str
    requestor_role: str
    unblinding_reason: UnblindingReason
    request_status: RequestStatus = RequestStatus.SUBMITTED
    clinical_justification: str
    is_emergency: bool = True
    request_date: datetime
    resolved_date: datetime | None = None
    treatment_arm_revealed: str | None = None
    impact_on_study: str | None = None
    notes: str | None = None
    created_at: datetime


class UnblindingApproval(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    request_id: str
    approver_name: str
    approver_role: str
    approval_decision: ApprovalDecision
    decision_date: datetime
    conditions: str | None = None
    rationale: str
    escalated_to: str | None = None
    response_time_minutes: int = Field(ge=0, default=0)
    notes: str | None = None
    created_at: datetime


class UnblindingNotification(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    request_id: str
    recipient_name: str
    recipient_role: str
    notification_channel: NotificationChannel
    sent_date: datetime
    acknowledged: bool = False
    acknowledged_date: datetime | None = None
    content_summary: str
    delivery_confirmed: bool = False
    retry_count: int = Field(ge=0, default=0)
    notes: str | None = None
    created_at: datetime


class UnblindingAuditLog(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    request_id: str
    audit_action: AuditAction
    action_date: datetime
    performed_by: str
    ip_address: str | None = None
    details: str
    document_reference: str | None = None
    regulatory_reported: bool = False
    report_date: datetime | None = None
    notes: str | None = None
    created_at: datetime


# --- Create / Update schemas ---

class UnblindingRequestCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    subject_id: str
    requestor_name: str
    requestor_role: str
    unblinding_reason: UnblindingReason
    clinical_justification: str
    is_emergency: bool = True


class UnblindingRequestUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    request_status: RequestStatus | None = None
    treatment_arm_revealed: str | None = None
    impact_on_study: str | None = None
    resolved_date: datetime | None = None
    notes: str | None = None


class UnblindingApprovalCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    request_id: str
    approver_name: str
    approver_role: str
    approval_decision: ApprovalDecision
    rationale: str
    response_time_minutes: int = Field(ge=0, default=0)


class UnblindingApprovalUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    conditions: str | None = None
    escalated_to: str | None = None
    notes: str | None = None


class UnblindingNotificationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    request_id: str
    recipient_name: str
    recipient_role: str
    notification_channel: NotificationChannel
    content_summary: str


class UnblindingNotificationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    acknowledged: bool | None = None
    acknowledged_date: datetime | None = None
    delivery_confirmed: bool | None = None
    retry_count: int | None = None
    notes: str | None = None


class UnblindingAuditLogCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    request_id: str
    audit_action: AuditAction
    performed_by: str
    details: str
    document_reference: str | None = None


class UnblindingAuditLogUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    regulatory_reported: bool | None = None
    report_date: datetime | None = None
    notes: str | None = None


# --- List responses ---

class UnblindingRequestListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[UnblindingRequest] = Field(default_factory=list)
    total: int = Field(ge=0)


class UnblindingApprovalListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[UnblindingApproval] = Field(default_factory=list)
    total: int = Field(ge=0)


class UnblindingNotificationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[UnblindingNotification] = Field(default_factory=list)
    total: int = Field(ge=0)


class UnblindingAuditLogListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[UnblindingAuditLog] = Field(default_factory=list)
    total: int = Field(ge=0)


# --- Metrics ---

class EmergencyUnblindingMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_requests: int = Field(ge=0)
    requests_by_reason: dict[str, int] = Field(default_factory=dict)
    requests_by_status: dict[str, int] = Field(default_factory=dict)
    emergency_request_rate: float = Field(ge=0)
    total_approvals: int = Field(ge=0)
    approvals_by_decision: dict[str, int] = Field(default_factory=dict)
    avg_response_time_minutes: float = Field(ge=0)
    total_notifications: int = Field(ge=0)
    notification_acknowledgment_rate: float = Field(ge=0)
    total_audit_entries: int = Field(ge=0)
    audit_actions_by_type: dict[str, int] = Field(default_factory=dict)
    regulatory_reporting_rate: float = Field(ge=0)
