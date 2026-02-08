"""Pydantic schemas for Data Governance (DUA + Right-to-Deletion).

Defines Data Use Agreement structures, deletion request workflows,
data access logging, and compliance checking models for the clinical
trial patient recruitment platform.

CLO-2: Data Use Agreements and Right-to-Deletion
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DUAType(str, Enum):
    """Types of Data Use Agreements."""

    SITE_DUA = "SITE_DUA"
    SPONSOR_DUA = "SPONSOR_DUA"
    RESEARCH_DUA = "RESEARCH_DUA"
    VENDOR_DUA = "VENDOR_DUA"


class DUAStatus(str, Enum):
    """Lifecycle states for a DUA."""

    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    TERMINATED = "TERMINATED"


class DataCategory(str, Enum):
    """Categories of data governed by a DUA."""

    PHI = "PHI"
    DE_IDENTIFIED = "DE_IDENTIFIED"
    LIMITED_DATASET = "LIMITED_DATASET"
    AGGREGATE = "AGGREGATE"


class ComplianceDecision(str, Enum):
    """Result of a DUA compliance check."""

    ALLOWED = "ALLOWED"
    DENIED = "DENIED"


class DeletionStatus(str, Enum):
    """Lifecycle states for a deletion request."""

    RECEIVED = "RECEIVED"
    VALIDATING = "VALIDATING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    DENIED = "DENIED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"


class DeletionScope(str, Enum):
    """Scope of a deletion request."""

    ALL = "ALL"
    PHI_ONLY = "PHI_ONLY"
    SPECIFIC_RECORDS = "SPECIFIC_RECORDS"


# ---------------------------------------------------------------------------
# DUA Amendment
# ---------------------------------------------------------------------------


class DUAAmendment(BaseModel):
    """Record of a change to an active DUA."""

    amendment_id: str = Field(..., description="Unique amendment identifier")
    timestamp: datetime = Field(..., description="When the amendment was made")
    field_changed: str = Field(..., description="Which field was amended")
    old_value: str = Field(..., description="Previous value")
    new_value: str = Field(..., description="New value")
    reason: str = Field(default="", description="Reason for the amendment")
    approved_by: str = Field(..., description="Who approved the amendment")


# ---------------------------------------------------------------------------
# DUA Core Schemas
# ---------------------------------------------------------------------------


class DUACreate(BaseModel):
    """Request body for creating a new DUA."""

    title: str = Field(..., description="Title of the agreement")
    dua_type: DUAType = Field(..., description="Type of DUA")
    parties: list[str] = Field(..., description="List of organization names that are parties to this DUA")
    data_categories: list[DataCategory] = Field(..., description="Categories of data covered")
    permitted_uses: list[str] = Field(default_factory=list, description="Specific approved uses")
    prohibited_uses: list[str] = Field(default_factory=list, description="Explicitly prohibited uses")
    retention_period_days: int = Field(default=2190, description="Data retention period in days (default ~6 years)")
    start_date: datetime | None = Field(default=None, description="Effective start date")
    end_date: datetime | None = Field(default=None, description="Agreement end date")


class DUAResponse(BaseModel):
    """Full DUA response with all fields."""

    id: str = Field(..., description="Unique DUA identifier")
    title: str = Field(..., description="Title of the agreement")
    dua_type: DUAType = Field(..., description="Type of DUA")
    parties: list[str] = Field(..., description="Parties to the agreement")
    data_categories: list[DataCategory] = Field(..., description="Categories of data covered")
    permitted_uses: list[str] = Field(default_factory=list, description="Approved uses")
    prohibited_uses: list[str] = Field(default_factory=list, description="Prohibited uses")
    retention_period_days: int = Field(..., description="Retention period in days")
    start_date: datetime | None = Field(default=None, description="Start date")
    end_date: datetime | None = Field(default=None, description="End date")
    status: DUAStatus = Field(..., description="Current lifecycle status")
    signed_by: str | None = Field(default=None, description="Who signed the DUA")
    signed_date: datetime | None = Field(default=None, description="When the DUA was signed")
    amendment_history: list[DUAAmendment] = Field(default_factory=list, description="History of amendments")
    created_at: datetime = Field(..., description="When the DUA was created")
    updated_at: datetime = Field(..., description="When the DUA was last updated")

    model_config = {"from_attributes": True}


class DUAUpdate(BaseModel):
    """Request body for updating a DUA."""

    title: str | None = Field(default=None, description="Updated title")
    status: DUAStatus | None = Field(default=None, description="New status (for state transitions)")
    parties: list[str] | None = Field(default=None, description="Updated parties")
    data_categories: list[DataCategory] | None = Field(default=None, description="Updated data categories")
    permitted_uses: list[str] | None = Field(default=None, description="Updated permitted uses")
    prohibited_uses: list[str] | None = Field(default=None, description="Updated prohibited uses")
    retention_period_days: int | None = Field(default=None, description="Updated retention period")
    start_date: datetime | None = Field(default=None, description="Updated start date")
    end_date: datetime | None = Field(default=None, description="Updated end date")
    signed_by: str | None = Field(default=None, description="Signer name (for activation)")
    signed_date: datetime | None = Field(default=None, description="Signature date")
    amendment_reason: str | None = Field(default=None, description="Reason for amendment (required for active DUAs)")
    amendment_approved_by: str | None = Field(default=None, description="Who approved the amendment")


# ---------------------------------------------------------------------------
# DUA Compliance Check
# ---------------------------------------------------------------------------


class DUAComplianceCheck(BaseModel):
    """Request body for checking data access against active DUAs."""

    user_id: str = Field(..., description="User requesting access")
    data_category: DataCategory = Field(..., description="Category of data being accessed")
    purpose: str = Field(..., description="Purpose of the data access")


class DUAComplianceResult(BaseModel):
    """Result of a DUA compliance check."""

    decision: ComplianceDecision = Field(..., description="ALLOWED or DENIED")
    dua_id: str | None = Field(default=None, description="DUA authorizing the access (if allowed)")
    dua_title: str | None = Field(default=None, description="Title of the authorizing DUA")
    reason: str = Field(default="", description="Explanation of the decision")


# ---------------------------------------------------------------------------
# Deletion Request Schemas
# ---------------------------------------------------------------------------


class DeletionRequestCreate(BaseModel):
    """Request body for submitting a deletion request."""

    patient_id: str = Field(..., description="Patient whose data should be deleted")
    requester: str = Field(..., description="Who is requesting deletion")
    reason: str = Field(default="", description="Reason for deletion request")
    scope: DeletionScope = Field(default=DeletionScope.ALL, description="Scope of deletion")
    specific_records: list[str] | None = Field(
        default=None,
        description="Specific record types to delete (when scope is SPECIFIC_RECORDS)",
    )


class DeletionRequestResponse(BaseModel):
    """Full deletion request response."""

    id: str = Field(..., description="Unique deletion request identifier")
    patient_id: str = Field(..., description="Patient identifier")
    requester: str = Field(..., description="Who requested deletion")
    reason: str = Field(default="", description="Reason for deletion")
    status: DeletionStatus = Field(..., description="Current request status")
    scope: DeletionScope = Field(..., description="Scope of deletion")
    specific_records: list[str] | None = Field(default=None, description="Specific records if applicable")
    created_at: datetime = Field(..., description="When the request was created")
    completed_at: datetime | None = Field(default=None, description="When deletion was completed")
    denial_reason: str | None = Field(default=None, description="Reason if denied")
    deleted_items: list[str] = Field(default_factory=list, description="List of deleted data categories")
    retained_items: list[str] = Field(default_factory=list, description="Items retained with reason")
    audit_entries: list[DeletionAuditEntry] = Field(default_factory=list, description="Audit trail for this request")

    model_config = {"from_attributes": True}


class DeletionAuditEntry(BaseModel):
    """A single audit entry for a deletion request."""

    timestamp: datetime = Field(..., description="When the action occurred")
    action: str = Field(..., description="Action performed")
    actor: str = Field(..., description="Who performed the action")
    details: str = Field(default="", description="Additional details")


# Fix forward reference
DeletionRequestResponse.model_rebuild()


class DeletionCertificate(BaseModel):
    """Certificate confirming what was deleted."""

    certificate_id: str = Field(..., description="Unique certificate identifier")
    deletion_request_id: str = Field(..., description="Associated deletion request")
    patient_id: str = Field(..., description="Patient identifier")
    issued_at: datetime = Field(..., description="When the certificate was issued")
    issued_by: str = Field(default="system", description="Who issued the certificate")
    scope: DeletionScope = Field(..., description="Scope of the deletion")
    deleted_items: list[str] = Field(default_factory=list, description="Data categories deleted")
    retained_items: list[str] = Field(default_factory=list, description="Items retained with reason")
    exceptions: list[str] = Field(
        default_factory=list,
        description="Any exceptions or items that could not be deleted",
    )
    backup_note: str = Field(
        default="Existing backups will be purged on next rotation cycle",
        description="Note about backup deletion",
    )
    compliance_statement: str = Field(
        default="Deletion performed in compliance with HIPAA and GDPR requirements",
        description="Compliance statement",
    )


# ---------------------------------------------------------------------------
# Access Log Schemas
# ---------------------------------------------------------------------------


class AccessLogEntry(BaseModel):
    """A record of a data access event."""

    id: str = Field(..., description="Unique log entry identifier")
    user_id: str = Field(..., description="User who accessed data")
    patient_id: str | None = Field(default=None, description="Patient whose data was accessed")
    data_category: DataCategory = Field(..., description="Category of data accessed")
    purpose: str = Field(..., description="Purpose of the access")
    timestamp: datetime = Field(..., description="When the access occurred")
    dua_id: str | None = Field(default=None, description="DUA authorizing this access")


class AccessLogCreate(BaseModel):
    """Request body for recording a data access."""

    user_id: str = Field(..., description="User accessing data")
    patient_id: str | None = Field(default=None, description="Patient whose data is accessed")
    data_category: DataCategory = Field(..., description="Category of data being accessed")
    purpose: str = Field(..., description="Purpose of the access")
    dua_id: str | None = Field(default=None, description="DUA authorizing this access")


class AccessLogQuery(BaseModel):
    """Query parameters for filtering access logs."""

    user_id: str | None = Field(default=None, description="Filter by user")
    patient_id: str | None = Field(default=None, description="Filter by patient")
    data_category: DataCategory | None = Field(default=None, description="Filter by data category")
    dua_id: str | None = Field(default=None, description="Filter by DUA")
    start_date: datetime | None = Field(default=None, description="Filter from date")
    end_date: datetime | None = Field(default=None, description="Filter to date")


class SuspiciousAccessReport(BaseModel):
    """Report of data accesses not covered by any active DUA."""

    total_uncovered: int = Field(..., description="Total number of uncovered accesses")
    entries: list[AccessLogEntry] = Field(default_factory=list, description="Uncovered access entries")
    generated_at: datetime = Field(..., description="When the report was generated")


# ---------------------------------------------------------------------------
# DUA Template
# ---------------------------------------------------------------------------


class DUATemplate(BaseModel):
    """Pre-populated DUA template for a specific type."""

    dua_type: DUAType = Field(..., description="Type of DUA this template is for")
    title: str = Field(..., description="Default title")
    parties: list[str] = Field(default_factory=list, description="Default parties (placeholders)")
    data_categories: list[DataCategory] = Field(default_factory=list, description="Default data categories")
    permitted_uses: list[str] = Field(default_factory=list, description="Default permitted uses")
    prohibited_uses: list[str] = Field(default_factory=list, description="Default prohibited uses")
    retention_period_days: int = Field(..., description="Default retention period")
