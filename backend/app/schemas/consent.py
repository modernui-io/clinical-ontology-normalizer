"""Pydantic schemas for HIPAA Consent Management.

Defines consent record structures, consent status tracking, and
data use authorization models for the clinical trial recruitment
platform.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ConsentType(str, Enum):
    """Types of consent tracked by the platform."""

    HIPAA_AUTHORIZATION = "HIPAA_AUTHORIZATION"
    RESEARCH_PARTICIPATION = "RESEARCH_PARTICIPATION"
    SCREENING_CONSENT = "SCREENING_CONSENT"
    DATA_SHARING = "DATA_SHARING"


class ConsentStatusValue(str, Enum):
    """Possible states of a consent record."""

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    NOT_FOUND = "not_found"


class DataUsePurpose(str, Enum):
    """Purposes for which PHI may be accessed."""

    TREATMENT = "TREATMENT"
    PAYMENT = "PAYMENT"
    OPERATIONS = "OPERATIONS"
    RESEARCH = "RESEARCH"
    SCREENING = "SCREENING"
    MARKETING = "MARKETING"


# ---------------------------------------------------------------------------
# Core schemas
# ---------------------------------------------------------------------------


class ConsentRecord(BaseModel):
    """A recorded consent event with full audit metadata."""

    id: str = Field(..., description="Unique consent record identifier")
    patient_id: str = Field(..., description="Patient identifier")
    consent_type: ConsentType = Field(..., description="Type of consent")
    scope: dict | None = Field(
        default=None,
        description=(
            "Scope of the consent: what PHI, for what purposes, "
            "with whom. Structure varies by consent type."
        ),
    )
    status: ConsentStatusValue = Field(
        default=ConsentStatusValue.ACTIVE,
        description="Current consent status",
    )
    granted_at: datetime = Field(..., description="When consent was granted")
    granted_by: str = Field(
        ...,
        description="User or entity who captured/recorded the consent",
    )
    expires_at: datetime | None = Field(
        default=None,
        description="When the consent expires (None = no expiration)",
    )
    revoked_at: datetime | None = Field(
        default=None,
        description="When consent was revoked (None = not revoked)",
    )
    revoked_by: str | None = Field(
        default=None,
        description="User who revoked the consent",
    )
    revocation_reason: str | None = Field(
        default=None,
        description="Reason for revocation",
    )

    model_config = {"from_attributes": True}


class ConsentStatus(BaseModel):
    """Result of checking a patient's consent status."""

    patient_id: str = Field(..., description="Patient identifier")
    consent_type: ConsentType = Field(..., description="Type of consent checked")
    status: ConsentStatusValue = Field(..., description="Current status")
    consent_record: ConsentRecord | None = Field(
        default=None,
        description="The consent record if found",
    )


class ConsentCheck(BaseModel):
    """Result of checking whether a specific data use is authorized."""

    patient_id: str = Field(..., description="Patient identifier")
    consent_type: ConsentType | None = Field(
        default=None,
        description="Consent type that authorizes this use (if any)",
    )
    purpose: DataUsePurpose = Field(
        ...,
        description="The purpose being checked",
    )
    is_authorized: bool = Field(
        ...,
        description="Whether the requested use is authorized",
    )
    reason: str = Field(
        default="",
        description="Human-readable explanation of the authorization decision",
    )


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class ConsentRecordRequest(BaseModel):
    """Request body for recording a new consent."""

    patient_id: str = Field(..., description="Patient identifier")
    consent_type: ConsentType = Field(..., description="Type of consent")
    scope: dict | None = Field(
        default=None,
        description="Scope of the consent (purposes, data elements, recipients)",
    )
    granted_by: str = Field(
        ...,
        description="User or entity capturing the consent",
    )
    expires_at: datetime | None = Field(
        default=None,
        description="Optional expiration date",
    )


class ConsentRevokeRequest(BaseModel):
    """Request body for revoking a consent."""

    patient_id: str = Field(..., description="Patient identifier")
    consent_type: ConsentType = Field(..., description="Type of consent to revoke")
    revoked_by: str = Field(..., description="User revoking the consent")
    reason: str = Field(
        default="",
        description="Reason for revocation",
    )


class DataUseCheckRequest(BaseModel):
    """Request body for checking data use authorization."""

    patient_id: str = Field(..., description="Patient identifier")
    purpose: DataUsePurpose = Field(..., description="Intended purpose of data use")


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------


class ConsentAuditEntry(BaseModel):
    """A single entry in the consent audit trail."""

    event_id: str = Field(..., description="Unique event identifier")
    timestamp: datetime = Field(..., description="When the event occurred")
    patient_id: str = Field(..., description="Patient identifier")
    consent_type: ConsentType = Field(..., description="Consent type involved")
    action: str = Field(
        ...,
        description="Action: GRANTED, REVOKED, CHECKED, EXPIRED",
    )
    actor: str = Field(..., description="User or system that performed the action")
    details: str = Field(
        default="",
        description="Additional context about the event",
    )


class ConsentAuditTrail(BaseModel):
    """Full audit trail for a patient's consent history."""

    patient_id: str = Field(..., description="Patient identifier")
    entries: list[ConsentAuditEntry] = Field(
        default_factory=list,
        description="Audit trail entries in chronological order",
    )
    total_entries: int = Field(
        default=0,
        description="Total number of audit entries",
    )


# ---------------------------------------------------------------------------
# P1-027: Ingestion-level consent metadata
# ---------------------------------------------------------------------------


class IngestionConsentMetadata(BaseModel):
    """Consent metadata captured at document ingestion time.

    P1-027: Tracks residency and consent status for regulatory compliance
    (e.g. Australian Privacy Act, GDPR, HIPAA).
    """

    residency_country: str | None = Field(
        None,
        min_length=2,
        max_length=2,
        description="ISO 3166-1 alpha-2 country code (e.g. AU, US, GB)",
    )
    consent_status: str | None = Field(
        None,
        description="obtained | pending | declined | not_required",
    )
    consent_date: datetime | None = Field(
        None,
        description="When consent was obtained or last updated",
    )
    consent_reference: str | None = Field(
        None,
        max_length=500,
        description="URI or ID linking to the external consent record",
    )

    model_config = {"from_attributes": True}
