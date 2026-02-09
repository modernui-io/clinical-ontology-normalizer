"""Pydantic v2 schemas for Veeva Vault CDMS integration.

Defines request/response models for:
    - Vault connection configuration and testing
    - Study listing and import
    - Screening result push to Vault
    - Enrollment status sync
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, SecretStr


# ==============================================================================
# Enums
# ==============================================================================


class VaultStudyStatus(str, Enum):
    """Veeva Vault CDMS study statuses."""

    ACTIVE = "active"
    LOCKED = "locked"
    CLOSED = "closed"
    DRAFT = "draft"
    ARCHIVED = "archived"


class VaultEnrollmentStatus(str, Enum):
    """Subject enrollment statuses in Vault CDMS."""

    SCREENING = "Screening"
    ENROLLED = "Enrolled"
    SCREEN_FAILED = "Screen Failed"
    RANDOMIZED = "Randomized"
    COMPLETED = "Completed"
    WITHDRAWN = "Withdrawn"
    DISCONTINUED = "Discontinued"


# ==============================================================================
# Connection / Config
# ==============================================================================


class VeevaConnectionConfig(BaseModel):
    """Configuration for connecting to a Veeva Vault CDMS instance."""

    vault_url: str = Field(..., description="Veeva Vault CDMS base URL")
    username: str = Field(..., description="Vault API username")
    password: SecretStr = Field(..., description="Vault API password")


class VeevaConnectionTestResponse(BaseModel):
    """Response from Vault connectivity test."""

    connected: bool = Field(..., description="Whether connection succeeded")
    version: str | None = Field(None, description="Vault CDMS API version")
    studies_count: int = Field(0, description="Number of accessible studies")
    latency_ms: float = Field(0, description="Round-trip latency in milliseconds")
    session_valid: bool = Field(False, description="Whether session authentication succeeded")
    error: str | None = Field(None, description="Error message if connection failed")
    demo_mode: bool = Field(False, description="True if running in demo mode")


# ==============================================================================
# Study Listing
# ==============================================================================


class VeevaStudySummary(BaseModel):
    """Summary of a study in Vault CDMS."""

    name: str = Field(..., description="Study name in Vault")
    title: str = Field(..., description="Study title/description")
    phase: str | None = Field(None, description="Trial phase")
    status: VaultStudyStatus = Field(VaultStudyStatus.ACTIVE, description="Study status")
    sponsor: str | None = Field(None, description="Sponsor name")
    therapeutic_area: str | None = Field(None, description="Therapeutic area")
    subject_count: int = Field(0, description="Number of subjects")


class VeevaStudyListResponse(BaseModel):
    """Response listing studies from Vault CDMS."""

    studies: list[VeevaStudySummary] = Field(default_factory=list)
    total_count: int = Field(0, description="Total number of studies")
    demo_mode: bool = Field(False, description="True if returning demo data")


# ==============================================================================
# Study Import
# ==============================================================================


class VeevaCriterionMapping(BaseModel):
    """A single eligibility criterion extracted from Vault CDMS."""

    oid: str = Field(..., description="Criterion identifier")
    criterion_type: str = Field(
        ..., description="'inclusion' or 'exclusion'"
    )
    description: str = Field(..., description="Human-readable criterion text")
    code_system: str | None = Field(None, description="Code system (SNOMED, ICD-10, etc.)")
    code: str | None = Field(None, description="Coded value")
    data_type: str | None = Field(None, description="Expected data type")


class VeevaStudyImportRequest(BaseModel):
    """Request to import a study from Vault CDMS."""

    study_name: str | None = Field(None, description="Study name in Vault (optional, taken from URL path)")
    auto_create_trial: bool = Field(
        True, description="Automatically create a trial record"
    )


class VeevaStudyImportResponse(BaseModel):
    """Response from importing a study from Vault CDMS."""

    trial_id: str | None = Field(None, description="Created trial ID")
    study_name: str = Field(..., description="Imported study name")
    study_title: str = Field("", description="Study title from Vault")
    criteria_count: int = Field(0, description="Number of eligibility criteria extracted")
    criteria: list[VeevaCriterionMapping] = Field(default_factory=list)
    forms_count: int = Field(0, description="Number of CRF forms in study")
    mapping_summary: dict = Field(
        default_factory=dict,
        description="Summary of criterion-to-code mappings",
    )
    demo_mode: bool = Field(False, description="True if using demo data")


# ==============================================================================
# Screening Push
# ==============================================================================


class VeevaScreeningPushRequest(BaseModel):
    """Request to push screening results to Vault CDMS."""

    trial_id: str = Field(..., description="Internal trial ID")
    patient_ids: list[str] = Field(..., description="Patient IDs to push results for")
    include_details: bool = Field(
        True, description="Include detailed criterion results"
    )


class VeevaScreeningPushResult(BaseModel):
    """Result of pushing a single patient's screening to Vault."""

    patient_id: str
    success: bool
    vault_subject_id: str | None = None
    error: str | None = None


class VeevaScreeningPushResponse(BaseModel):
    """Response from pushing screening results to Vault CDMS."""

    pushed_count: int = Field(0, description="Successfully pushed count")
    failed_count: int = Field(0, description="Failed push count")
    results: list[VeevaScreeningPushResult] = Field(default_factory=list)
    demo_mode: bool = Field(False, description="True if demo mode")


# ==============================================================================
# Enrollment Sync
# ==============================================================================


class VeevaEnrollmentStatusUpdate(BaseModel):
    """Status update for a single subject."""

    subject_id: str = Field(..., description="Vault subject identifier")
    patient_id: str | None = Field(None, description="Mapped internal patient ID")
    status: VaultEnrollmentStatus = Field(..., description="Current enrollment status")
    status_date: datetime | None = Field(None, description="Date of status change")
    site_name: str | None = Field(None, description="Site name")


class VeevaEnrollmentSyncResponse(BaseModel):
    """Response from enrollment status sync."""

    synced_count: int = Field(0, description="Number of statuses synced")
    status_updates: list[VeevaEnrollmentStatusUpdate] = Field(default_factory=list)
    demo_mode: bool = Field(False, description="True if demo mode")


# ==============================================================================
# Study Subjects
# ==============================================================================


class VeevaSubject(BaseModel):
    """A subject in a Vault CDMS study."""

    subject_id: str = Field(..., description="Subject identifier in Vault")
    subject_name: str | None = Field(None, description="Subject name/label")
    site_id: str | None = Field(None, description="Site identifier")
    site_name: str | None = Field(None, description="Site name")
    status: str | None = Field(None, description="Subject status")
    created_date: datetime | None = Field(None, description="Creation date")


class VeevaSubjectListResponse(BaseModel):
    """Response listing subjects in a study."""

    subjects: list[VeevaSubject] = Field(default_factory=list)
    total_count: int = Field(0)
    demo_mode: bool = Field(False)


# ==============================================================================
# Integration Status
# ==============================================================================


class VeevaIntegrationStatus(BaseModel):
    """Overall Veeva Vault CDMS integration status."""

    configured: bool = Field(
        False, description="Whether Vault credentials are configured"
    )
    demo_mode: bool = Field(
        False, description="Whether running in demo mode"
    )
    vault_url: str | None = Field(None, description="Configured Vault URL")
    last_sync: datetime | None = Field(None, description="Last sync timestamp")
    studies_imported: int = Field(0, description="Number of studies imported")
    screenings_pushed: int = Field(0, description="Number of screenings pushed to Vault")
    active_syncs: int = Field(0, description="Number of active enrollment syncs")
