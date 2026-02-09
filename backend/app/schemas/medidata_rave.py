"""Pydantic v2 schemas for Medidata Rave EDC integration.

Defines request/response models for:
    - Rave connection configuration and testing
    - Study listing and import
    - Screening result push to Rave
    - Enrollment status sync
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, SecretStr


# ==============================================================================
# Enums
# ==============================================================================


class RaveEnvironment(str, Enum):
    """Rave study environments."""

    PROD = "Prod"
    UAT = "UAT"
    DEV = "Dev"
    AUX = "Aux"


class EnrollmentStatus(str, Enum):
    """Subject enrollment statuses in Rave."""

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


class RaveConnectionConfig(BaseModel):
    """Configuration for connecting to a Rave instance."""

    base_url: str = Field(..., description="Rave Web Services base URL")
    username: str = Field(..., description="Rave API username")
    password: SecretStr = Field(..., description="Rave API password")
    default_environment: RaveEnvironment = Field(
        default=RaveEnvironment.PROD,
        description="Default study environment",
    )


class RaveConnectionTestResponse(BaseModel):
    """Response from Rave connectivity test."""

    connected: bool = Field(..., description="Whether connection succeeded")
    version: str | None = Field(None, description="Rave Web Services version")
    studies_count: int = Field(0, description="Number of accessible studies")
    latency_ms: float = Field(0, description="Round-trip latency in milliseconds")
    error: str | None = Field(None, description="Error message if connection failed")
    demo_mode: bool = Field(False, description="True if running in demo mode")


# ==============================================================================
# Study Listing
# ==============================================================================


class RaveStudySummary(BaseModel):
    """Summary of a study in Rave."""

    oid: str = Field(..., description="Study OID in Rave")
    name: str = Field(..., description="Study name")
    environment: str = Field(..., description="Study environment (Prod, UAT, etc.)")
    protocol_number: str | None = Field(None, description="Protocol number")
    phase: str | None = Field(None, description="Trial phase")
    sponsor: str | None = Field(None, description="Sponsor name")
    subject_count: int = Field(0, description="Number of subjects")


class RaveStudyListResponse(BaseModel):
    """Response listing studies from Rave."""

    studies: list[RaveStudySummary] = Field(default_factory=list)
    total_count: int = Field(0, description="Total number of studies")
    demo_mode: bool = Field(False, description="True if returning demo data")


# ==============================================================================
# Study Import
# ==============================================================================


class RaveCriterionMapping(BaseModel):
    """A single eligibility criterion extracted from Rave ODM."""

    oid: str = Field(..., description="Item OID from ODM")
    criterion_type: str = Field(
        ..., description="'inclusion' or 'exclusion'"
    )
    description: str = Field(..., description="Human-readable criterion text")
    code_system: str | None = Field(None, description="Code system (SNOMED, ICD-10, etc.)")
    code: str | None = Field(None, description="Coded value")
    data_type: str | None = Field(None, description="Expected data type")


class RaveStudyImportRequest(BaseModel):
    """Request to import a study from Rave."""

    study_oid: str | None = Field(None, description="Study OID in Rave (optional, taken from URL path)")
    environment: RaveEnvironment = Field(
        default=RaveEnvironment.PROD,
        description="Study environment",
    )
    auto_create_trial: bool = Field(
        True, description="Automatically create a trial record"
    )


class RaveStudyImportResponse(BaseModel):
    """Response from importing a study from Rave."""

    trial_id: str | None = Field(None, description="Created trial ID")
    study_oid: str = Field(..., description="Imported study OID")
    study_name: str = Field(..., description="Study name from Rave")
    criteria_count: int = Field(0, description="Number of eligibility criteria extracted")
    criteria: list[RaveCriterionMapping] = Field(default_factory=list)
    forms_count: int = Field(0, description="Number of CRF forms in study")
    mapping_summary: dict = Field(
        default_factory=dict,
        description="Summary of criterion-to-code mappings",
    )
    demo_mode: bool = Field(False, description="True if using demo data")


# ==============================================================================
# Screening Push
# ==============================================================================


class RaveScreeningPushRequest(BaseModel):
    """Request to push screening results to Rave."""

    trial_id: str = Field(..., description="Internal trial ID")
    patient_ids: list[str] = Field(..., description="Patient IDs to push results for")
    include_details: bool = Field(
        True, description="Include detailed criterion results"
    )


class ScreeningPushResult(BaseModel):
    """Result of pushing a single patient's screening to Rave."""

    patient_id: str
    success: bool
    rave_subject_key: str | None = None
    error: str | None = None


class RaveScreeningPushResponse(BaseModel):
    """Response from pushing screening results to Rave."""

    pushed_count: int = Field(0, description="Successfully pushed count")
    failed_count: int = Field(0, description="Failed push count")
    results: list[ScreeningPushResult] = Field(default_factory=list)
    demo_mode: bool = Field(False, description="True if demo mode")


# ==============================================================================
# Enrollment Sync
# ==============================================================================


class EnrollmentStatusUpdate(BaseModel):
    """Status update for a single subject."""

    subject_key: str = Field(..., description="Rave subject key")
    patient_id: str | None = Field(None, description="Mapped internal patient ID")
    status: EnrollmentStatus = Field(..., description="Current enrollment status")
    status_date: datetime | None = Field(None, description="Date of status change")
    site_name: str | None = Field(None, description="Site name")


class RaveEnrollmentSyncResponse(BaseModel):
    """Response from enrollment status sync."""

    synced_count: int = Field(0, description="Number of statuses synced")
    status_updates: list[EnrollmentStatusUpdate] = Field(default_factory=list)
    demo_mode: bool = Field(False, description="True if demo mode")


# ==============================================================================
# Study Subjects
# ==============================================================================


class RaveSubject(BaseModel):
    """A subject in a Rave study."""

    subject_key: str = Field(..., description="Subject key in Rave")
    subject_name: str | None = Field(None, description="Subject name/label")
    site_oid: str | None = Field(None, description="Site OID")
    site_name: str | None = Field(None, description="Site name")
    status: str | None = Field(None, description="Subject status")
    created_date: datetime | None = Field(None, description="Creation date")


class RaveSubjectListResponse(BaseModel):
    """Response listing subjects in a study."""

    subjects: list[RaveSubject] = Field(default_factory=list)
    total_count: int = Field(0)
    demo_mode: bool = Field(False)


# ==============================================================================
# Integration Status
# ==============================================================================


class RaveIntegrationStatus(BaseModel):
    """Overall Medidata Rave integration status."""

    configured: bool = Field(
        False, description="Whether Rave credentials are configured"
    )
    demo_mode: bool = Field(
        False, description="Whether running in demo mode"
    )
    base_url: str | None = Field(None, description="Configured Rave base URL")
    last_sync: datetime | None = Field(None, description="Last sync timestamp")
    studies_imported: int = Field(0, description="Number of studies imported")
    screenings_pushed: int = Field(0, description="Number of screenings pushed to Rave")
    active_syncs: int = Field(0, description="Number of active enrollment syncs")
