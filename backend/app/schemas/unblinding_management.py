"""Pydantic schemas for Unblinding Management (CLINICAL-UBM).

Manages unblinding operations for clinical trials: unblinding request lifecycle
(request, approve, execute, deny, cancel), unblinding policies per trial,
blinding level configuration, approval authority tracking, emergency unblinding
procedures, and unblinding metrics/dashboard.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class UnblindingType(str, Enum):
    """Type of unblinding request."""

    EMERGENCY = "emergency"
    INTERIM_ANALYSIS = "interim_analysis"
    FINAL = "final"
    REGULATORY_REQUEST = "regulatory_request"
    DSMB_REQUEST = "dsmb_request"
    INDIVIDUAL_PATIENT = "individual_patient"


class UnblindingStatus(str, Enum):
    """Lifecycle status of an unblinding request."""

    REQUESTED = "requested"
    APPROVED = "approved"
    EXECUTED = "executed"
    DENIED = "denied"
    CANCELLED = "cancelled"


class BlindingLevel(str, Enum):
    """Blinding level of a clinical trial."""

    DOUBLE_BLIND = "double_blind"
    SINGLE_BLIND = "single_blind"
    OPEN_LABEL = "open_label"
    OBSERVER_BLIND = "observer_blind"


class ApprovalAuthority(str, Enum):
    """Authority that may approve an unblinding request."""

    INVESTIGATOR = "investigator"
    SPONSOR_MEDICAL_OFFICER = "sponsor_medical_officer"
    DSMB = "dsmb"
    IRB = "irb"
    REGULATORY_AUTHORITY = "regulatory_authority"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class UnblindingRequest(BaseModel):
    """An unblinding request for a clinical trial patient or cohort."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique unblinding request identifier")
    trial_id: str = Field(..., description="Trial identifier")
    site_id: str = Field(..., description="Site identifier where the request originated")
    patient_id: str | None = Field(None, description="Patient identifier (if individual unblinding)")
    request_number: str = Field(..., description="Human-readable request number (e.g., UBR-001)")
    unblinding_type: UnblindingType = Field(..., description="Type of unblinding request")
    status: UnblindingStatus = Field(
        default=UnblindingStatus.REQUESTED, description="Current status of the request"
    )
    blinding_level: BlindingLevel = Field(..., description="Blinding level of the trial")
    reason: str = Field(..., description="Reason for unblinding request")
    clinical_justification: str | None = Field(
        None, description="Clinical justification supporting the request"
    )
    requested_by: str = Field(..., description="Name of the person who requested unblinding")
    requested_date: datetime = Field(..., description="Date and time the request was made")
    approved_by: str | None = Field(None, description="Name of the person who approved the request")
    approval_authority: ApprovalAuthority | None = Field(
        None, description="Authority level of the approver"
    )
    approved_date: datetime | None = Field(None, description="Date the request was approved")
    executed_by: str | None = Field(None, description="Name of the person who executed the unblinding")
    executed_date: datetime | None = Field(None, description="Date the unblinding was executed")
    treatment_assignment: str | None = Field(
        None, description="Revealed treatment assignment (populated after execution)"
    )
    was_emergency: bool = Field(default=False, description="Whether this was an emergency unblinding")
    notification_list: list[str] = Field(
        default_factory=list, description="List of stakeholders notified about this unblinding"
    )
    impact_on_study: str | None = Field(
        None, description="Assessment of the impact on study integrity"
    )


class UnblindingPolicy(BaseModel):
    """Unblinding policy configuration for a clinical trial."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique policy identifier")
    trial_id: str = Field(..., description="Trial identifier this policy applies to")
    blinding_level: BlindingLevel = Field(..., description="Blinding level of the trial")
    emergency_procedure: str = Field(
        ..., description="Procedure for emergency unblinding"
    )
    interim_unblinding_plan: str | None = Field(
        None, description="Plan for interim analysis unblinding"
    )
    final_unblinding_plan: str | None = Field(
        None, description="Plan for final study unblinding"
    )
    authorized_unblinders: list[str] = Field(
        default_factory=list, description="Personnel authorized to execute unblinding"
    )
    code_break_instructions: str = Field(
        ..., description="Instructions for breaking the randomization code"
    )
    notification_requirements: list[str] = Field(
        default_factory=list,
        description="Required notifications when unblinding occurs",
    )


class UnblindingMetrics(BaseModel):
    """Aggregated unblinding management metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_requests: int = Field(ge=0, description="Total unblinding requests")
    requests_by_status: dict[str, int] = Field(
        default_factory=dict, description="Request counts by status"
    )
    requests_by_type: dict[str, int] = Field(
        default_factory=dict, description="Request counts by unblinding type"
    )
    emergency_unblinding_count: int = Field(
        ge=0, description="Number of emergency unblindings"
    )
    average_approval_time_hours: float | None = Field(
        None, description="Average time from request to approval in hours"
    )
    total_policies: int = Field(ge=0, description="Total unblinding policies defined")
    executed_count: int = Field(ge=0, description="Number of executed unblindings")
    denied_count: int = Field(ge=0, description="Number of denied requests")
    cancelled_count: int = Field(ge=0, description="Number of cancelled requests")
    pending_requests: int = Field(ge=0, description="Number of requests awaiting action")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class UnblindingRequestCreate(BaseModel):
    """Request to create a new unblinding request."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    site_id: str = Field(..., description="Site identifier")
    patient_id: str | None = Field(None, description="Patient identifier")
    unblinding_type: UnblindingType = Field(..., description="Type of unblinding")
    blinding_level: BlindingLevel = Field(..., description="Blinding level of the trial")
    reason: str = Field(..., description="Reason for unblinding")
    clinical_justification: str | None = Field(
        None, description="Clinical justification"
    )
    requested_by: str = Field(..., description="Name of requester")
    was_emergency: bool = Field(default=False, description="Whether this is an emergency")


class UnblindingRequestUpdate(BaseModel):
    """Request to update an existing unblinding request."""

    model_config = ConfigDict(from_attributes=True)

    reason: str | None = Field(None, description="Updated reason")
    clinical_justification: str | None = Field(
        None, description="Updated clinical justification"
    )
    impact_on_study: str | None = Field(
        None, description="Assessment of impact on study"
    )
    notification_list: list[str] | None = Field(
        None, description="Updated notification list"
    )


class UnblindingPolicyCreate(BaseModel):
    """Request to create a new unblinding policy."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    blinding_level: BlindingLevel = Field(..., description="Blinding level")
    emergency_procedure: str = Field(..., description="Emergency unblinding procedure")
    interim_unblinding_plan: str | None = Field(
        None, description="Interim analysis unblinding plan"
    )
    final_unblinding_plan: str | None = Field(
        None, description="Final study unblinding plan"
    )
    authorized_unblinders: list[str] = Field(
        default_factory=list, description="Authorized personnel"
    )
    code_break_instructions: str = Field(
        ..., description="Code break instructions"
    )
    notification_requirements: list[str] = Field(
        default_factory=list, description="Notification requirements"
    )


class UnblindingPolicyUpdate(BaseModel):
    """Request to update an existing unblinding policy."""

    model_config = ConfigDict(from_attributes=True)

    blinding_level: BlindingLevel | None = Field(None, description="Blinding level")
    emergency_procedure: str | None = Field(
        None, description="Emergency unblinding procedure"
    )
    interim_unblinding_plan: str | None = Field(
        None, description="Interim analysis unblinding plan"
    )
    final_unblinding_plan: str | None = Field(
        None, description="Final study unblinding plan"
    )
    authorized_unblinders: list[str] | None = Field(
        None, description="Authorized personnel"
    )
    code_break_instructions: str | None = Field(
        None, description="Code break instructions"
    )
    notification_requirements: list[str] | None = Field(
        None, description="Notification requirements"
    )


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class UnblindingRequestListResponse(BaseModel):
    """List of unblinding requests."""

    model_config = ConfigDict(from_attributes=True)

    items: list[UnblindingRequest] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class UnblindingPolicyListResponse(BaseModel):
    """List of unblinding policies."""

    model_config = ConfigDict(from_attributes=True)

    items: list[UnblindingPolicy] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")
