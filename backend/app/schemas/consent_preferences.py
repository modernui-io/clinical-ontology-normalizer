"""Pydantic schemas for Patient Consent Preference Center (VP-Product-7).

Provides comprehensive consent preference management beyond the basic
HIPAA consent tracking in consent.py. Supports granular per-category
consent, channel preferences, consent templates, audit trails, and
program-wide consent metrics for pharma-regulated clinical trial
recruitment.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ConsentCategory(str, Enum):
    """Categories of patient consent tracked by the preference center."""

    TRIAL_SCREENING = "TRIAL_SCREENING"
    DATA_SHARING = "DATA_SHARING"
    COMMUNICATION = "COMMUNICATION"
    ANALYTICS = "ANALYTICS"
    RESEARCH_REUSE = "RESEARCH_REUSE"
    BIOBANK = "BIOBANK"
    GENETIC_ANALYSIS = "GENETIC_ANALYSIS"
    THIRD_PARTY_TRANSFER = "THIRD_PARTY_TRANSFER"


class CommunicationChannel(str, Enum):
    """Communication channels for consent preferences."""

    EMAIL = "EMAIL"
    SMS = "SMS"
    PHONE = "PHONE"
    PORTAL = "PORTAL"
    MAIL = "MAIL"


class PreferenceStatus(str, Enum):
    """Status of an individual consent preference."""

    OPTED_IN = "OPTED_IN"
    OPTED_OUT = "OPTED_OUT"
    NOT_SET = "NOT_SET"
    EXPIRED = "EXPIRED"


class OverallConsentStatus(str, Enum):
    """Aggregate consent status for a patient profile."""

    FULL = "FULL"
    PARTIAL = "PARTIAL"
    WITHDRAWN = "WITHDRAWN"
    PENDING = "PENDING"


class ConsentAction(str, Enum):
    """Actions recorded in the consent audit trail."""

    GRANTED = "GRANTED"
    WITHDRAWN = "WITHDRAWN"
    UPDATED = "UPDATED"
    EXPIRED = "EXPIRED"


class ConsentSource(str, Enum):
    """Source through which consent was captured."""

    WEB_PORTAL = "WEB_PORTAL"
    API = "API"
    PAPER_FORM = "PAPER_FORM"
    VERBAL = "VERBAL"


# ---------------------------------------------------------------------------
# Core schemas
# ---------------------------------------------------------------------------


class ConsentPreference(BaseModel):
    """A single consent preference for one category."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique preference identifier")
    patient_id: str = Field(..., description="Patient identifier")
    category: ConsentCategory = Field(..., description="Consent category")
    status: PreferenceStatus = Field(
        default=PreferenceStatus.NOT_SET,
        description="Current preference status",
    )
    channel_preferences: dict[str, bool] = Field(
        default_factory=dict,
        description="Per-channel opt-in/out (channel name -> enabled)",
    )
    grantor: str = Field(
        ...,
        description="Person or entity who granted/captured this consent",
    )
    granted_at: datetime = Field(..., description="When consent was granted")
    expires_at: datetime | None = Field(
        default=None,
        description="When this consent expires (None = no expiration)",
    )
    version: int = Field(default=1, description="Version of this preference record")
    withdrawal_reason: str | None = Field(
        default=None,
        description="Reason for withdrawal (required on opt-out)",
    )
    ip_address: str | None = Field(
        default=None,
        description="IP address captured for audit purposes",
    )
    source: ConsentSource = Field(
        default=ConsentSource.WEB_PORTAL,
        description="Source through which consent was captured",
    )


class PreferenceProfile(BaseModel):
    """Complete consent preference profile for a patient."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str = Field(..., description="Patient identifier")
    preferences: list[ConsentPreference] = Field(
        default_factory=list,
        description="List of consent preferences",
    )
    overall_consent_status: OverallConsentStatus = Field(
        default=OverallConsentStatus.PENDING,
        description="Aggregate consent status",
    )
    last_updated: datetime = Field(..., description="Last modification timestamp")
    consent_version: int = Field(
        default=1,
        description="Version of the consent profile",
    )
    profile_completeness_pct: float = Field(
        default=0.0,
        description="Percentage of consent categories addressed (0-100)",
    )


class ConsentPreferenceAuditEntry(BaseModel):
    """A single entry in the consent preferences audit trail."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique audit entry identifier")
    patient_id: str = Field(..., description="Patient identifier")
    category: ConsentCategory = Field(..., description="Consent category affected")
    action: ConsentAction = Field(..., description="Action that occurred")
    old_status: PreferenceStatus | None = Field(
        default=None,
        description="Previous preference status",
    )
    new_status: PreferenceStatus = Field(..., description="New preference status")
    performed_by: str = Field(
        ...,
        description="User or system that performed the action",
    )
    timestamp: datetime = Field(..., description="When the action occurred")
    ip_address: str | None = Field(
        default=None,
        description="IP address of the actor",
    )
    notes: str | None = Field(
        default=None,
        description="Additional context about the change",
    )


class CategoryMetrics(BaseModel):
    """Consent counts for a single category."""

    model_config = ConfigDict(from_attributes=True)

    opted_in: int = Field(default=0, description="Number of patients opted in")
    opted_out: int = Field(default=0, description="Number of patients opted out")
    not_set: int = Field(default=0, description="Number of patients not set")


class MonthlyRate(BaseModel):
    """Monthly consent rate data point."""

    model_config = ConfigDict(from_attributes=True)

    month: str = Field(..., description="Month in YYYY-MM format")
    rate: float = Field(..., description="Consent rate for the month (0-100)")


class ConsentMetrics(BaseModel):
    """Program-wide consent metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_patients: int = Field(default=0, description="Total patients tracked")
    fully_consented_pct: float = Field(
        default=0.0,
        description="Percentage of patients fully consented",
    )
    partially_consented_pct: float = Field(
        default=0.0,
        description="Percentage of patients partially consented",
    )
    withdrawn_pct: float = Field(
        default=0.0,
        description="Percentage of patients with all consents withdrawn",
    )
    pending_pct: float = Field(
        default=0.0,
        description="Percentage of patients with pending consent",
    )
    by_category: dict[str, CategoryMetrics] = Field(
        default_factory=dict,
        description="Metrics broken down by consent category",
    )
    avg_categories_consented: float = Field(
        default=0.0,
        description="Average number of categories consented per patient",
    )
    consent_rate_trend: list[MonthlyRate] = Field(
        default_factory=list,
        description="Monthly consent rate trend data",
    )
    withdrawal_rate_30d: float = Field(
        default=0.0,
        description="Consent withdrawal rate over the last 30 days (percentage)",
    )


class ConsentTemplate(BaseModel):
    """Template defining a standard set of consent categories."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique template identifier")
    name: str = Field(..., description="Template name")
    description: str = Field(..., description="Template description")
    version: int = Field(default=1, description="Template version")
    categories: list[ConsentCategory] = Field(
        default_factory=list,
        description="Categories included in this template",
    )
    required_categories: list[ConsentCategory] = Field(
        default_factory=list,
        description="Categories that must be consented",
    )
    language: str = Field(default="en", description="Template language")
    effective_date: datetime = Field(
        ...,
        description="Date from which this template is effective",
    )


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class PreferenceUpdateRequest(BaseModel):
    """Request to update a single consent preference."""

    category: ConsentCategory = Field(..., description="Consent category to update")
    status: PreferenceStatus = Field(..., description="New preference status")
    channel_preferences: dict[str, bool] = Field(
        default_factory=dict,
        description="Channel preferences (channel -> enabled)",
    )
    source: ConsentSource = Field(
        default=ConsentSource.WEB_PORTAL,
        description="Source of the update",
    )
    grantor: str = Field(..., description="Who is granting/updating consent")
    ip_address: str | None = Field(
        default=None,
        description="IP address for audit",
    )


class BulkPreferenceUpdateRequest(BaseModel):
    """Request to update multiple consent preferences at once."""

    preferences: list[PreferenceUpdateRequest] = Field(
        ...,
        description="List of preference updates",
    )


class WithdrawConsentRequest(BaseModel):
    """Request to withdraw consent for a specific category."""

    reason: str = Field(..., description="Reason for withdrawal (required)")


class WithdrawAllConsentRequest(BaseModel):
    """Request to withdraw all consent."""

    reason: str = Field(..., description="Reason for complete withdrawal (required)")


class ApplyTemplateRequest(BaseModel):
    """Request to apply a consent template to a patient."""

    template_id: str = Field(..., description="ID of the template to apply")
    source: ConsentSource = Field(
        default=ConsentSource.WEB_PORTAL,
        description="Source of the consent",
    )
    grantor: str = Field(..., description="Who is granting the consent")
    ip_address: str | None = Field(
        default=None,
        description="IP address for audit",
    )


class ConsentCheckResponse(BaseModel):
    """Response for a consent check query."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str = Field(..., description="Patient identifier")
    category: ConsentCategory = Field(..., description="Category checked")
    channel: str | None = Field(
        default=None,
        description="Channel checked (if applicable)",
    )
    is_consented: bool = Field(
        ...,
        description="Whether the patient has active consent",
    )
    status: PreferenceStatus = Field(
        ...,
        description="Current preference status",
    )


class ConsentExportRecord(BaseModel):
    """Full consent record export for data portability."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str = Field(..., description="Patient identifier")
    profile: PreferenceProfile = Field(
        ...,
        description="Complete preference profile",
    )
    audit_trail: list[ConsentPreferenceAuditEntry] = Field(
        default_factory=list,
        description="Complete audit history",
    )
    exported_at: datetime = Field(..., description="Timestamp of export")
    export_format: str = Field(
        default="JSON",
        description="Format of the export",
    )


class ProfileListResponse(BaseModel):
    """Paginated list of preference profiles."""

    model_config = ConfigDict(from_attributes=True)

    profiles: list[PreferenceProfile] = Field(
        default_factory=list,
        description="List of profiles",
    )
    total: int = Field(default=0, description="Total number of profiles")
    limit: int = Field(default=20, description="Page size")
    offset: int = Field(default=0, description="Page offset")


class ExpiringConsentItem(BaseModel):
    """A consent preference that is nearing expiration."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str = Field(..., description="Patient identifier")
    category: ConsentCategory = Field(..., description="Consent category")
    expires_at: datetime = Field(..., description="Expiration date")
    days_until_expiry: int = Field(
        ...,
        description="Number of days until expiry",
    )


class ExpiringConsentsResponse(BaseModel):
    """Response listing consents nearing expiration."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ExpiringConsentItem] = Field(
        default_factory=list,
        description="Expiring consent items",
    )
    total: int = Field(default=0, description="Total count")
    days_ahead: int = Field(..., description="Look-ahead window in days")
