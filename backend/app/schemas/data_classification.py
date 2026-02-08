"""Pydantic schemas for Data Classification Policy and Handling Procedures.

Defines classification levels, data asset inventory, handling rules,
reclassification workflows, and summary statistics for the clinical
trial patient recruitment platform.

CLO-3: Data Classification Policy and Handling Procedures

Classification levels align with HIPAA/NIST SP 800-60:
  - PUBLIC: Marketing materials, general trial info
  - INTERNAL: Internal analytics, aggregated reports
  - CONFIDENTIAL: De-identified patient data, trial protocols
  - RESTRICTED: PHI, PII, credentials, encryption keys
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ClassificationLevel(str, Enum):
    """Data classification levels (HIPAA/NIST aligned)."""

    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


class ReclassificationStatus(str, Enum):
    """Lifecycle states for a reclassification request."""

    PENDING = "PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ReviewFrequency(str, Enum):
    """Standard review frequency labels."""

    QUARTERLY = "QUARTERLY"
    SEMI_ANNUAL = "SEMI_ANNUAL"
    ANNUAL = "ANNUAL"
    BIENNIAL = "BIENNIAL"


# ---------------------------------------------------------------------------
# Classification Level Definition
# ---------------------------------------------------------------------------


class ClassificationLevelDefinition(BaseModel):
    """Full definition of a classification level with handling guidance."""

    level: ClassificationLevel
    name: str = Field(description="Human-readable label")
    description: str = Field(description="Detailed description")
    examples: list[str] = Field(default_factory=list, description="Example data types")
    color: str = Field(description="UI indicator color")
    severity_order: int = Field(description="Numeric ordering, 0=lowest")


# ---------------------------------------------------------------------------
# Handling Rules
# ---------------------------------------------------------------------------


class StorageRequirements(BaseModel):
    """Storage requirements for a classification level."""

    encryption_at_rest: bool = False
    encryption_algorithm: Optional[str] = None
    isolated_storage: bool = False
    backup_encrypted: bool = False
    geographic_restrictions: Optional[str] = None


class AccessControlRequirements(BaseModel):
    """Access control requirements for a classification level."""

    authentication_required: bool = False
    mfa_required: bool = False
    rbac_required: bool = False
    minimum_role: Optional[str] = None
    dua_required: bool = False
    need_to_know: bool = False
    access_logging: str = Field(default="none", description="none|standard|full")


class TransmissionRequirements(BaseModel):
    """Transmission security for a classification level."""

    encryption_in_transit: bool = False
    minimum_tls_version: Optional[str] = None
    vpn_required: bool = False
    secure_channel_only: bool = False


class RetentionRequirements(BaseModel):
    """Retention and disposal requirements."""

    default_retention_days: Optional[int] = None
    disposal_method: str = Field(default="standard_delete", description="standard_delete|secure_erase|crypto_shred")
    disposal_verification: bool = False
    legal_hold_eligible: bool = False


class IncidentResponse(BaseModel):
    """Incident response procedures per level."""

    notification_required: bool = False
    notification_timeline_hours: Optional[int] = None
    breach_report_required: bool = False
    hhs_notification: bool = False
    patient_notification: bool = False
    severity: str = Field(default="low", description="low|medium|high|critical")


class SharingRestrictions(BaseModel):
    """Data sharing restrictions per level."""

    internal_sharing: str = Field(default="unrestricted", description="unrestricted|authenticated|role_based|prohibited")
    external_sharing: str = Field(default="unrestricted", description="unrestricted|with_approval|dua_required|prohibited")
    third_party_sharing: str = Field(default="unrestricted", description="unrestricted|with_approval|dua_required|prohibited")
    de_identification_required: bool = False


class HandlingRules(BaseModel):
    """Complete handling rules for a classification level."""

    classification_level: ClassificationLevel
    storage: StorageRequirements
    access_control: AccessControlRequirements
    transmission: TransmissionRequirements
    retention: RetentionRequirements
    incident_response: IncidentResponse
    sharing: SharingRestrictions


# ---------------------------------------------------------------------------
# Data Asset
# ---------------------------------------------------------------------------


class DataAssetCreate(BaseModel):
    """Schema for registering a new data asset."""

    name: str = Field(min_length=1, max_length=200, description="Human-readable asset name")
    description: str = Field(min_length=1, max_length=2000, description="Description of the data asset")
    classification_level: ClassificationLevel
    data_owner: str = Field(min_length=1, max_length=200, description="Owner responsible for the asset")
    data_steward: Optional[str] = Field(default=None, max_length=200, description="Steward managing day-to-day")
    storage_location: str = Field(min_length=1, max_length=500, description="Where data is stored")
    retention_period_days: Optional[int] = Field(default=None, ge=1, description="Retention period in days")
    encryption_required: bool = Field(default=False, description="Whether encryption is required")
    access_restrictions: Optional[list[str]] = Field(default=None, description="Access restriction notes")
    review_frequency_days: int = Field(default=365, ge=1, description="How often to review classification")
    tags: Optional[list[str]] = Field(default=None, description="Searchable tags")


class DataAssetResponse(BaseModel):
    """Schema for a data asset response."""

    asset_id: str = Field(description="Unique asset identifier")
    name: str
    description: str
    classification_level: ClassificationLevel
    data_owner: str
    data_steward: Optional[str] = None
    storage_location: str
    retention_period_days: Optional[int] = None
    encryption_required: bool = False
    access_restrictions: list[str] = Field(default_factory=list)
    review_frequency_days: int = 365
    last_reviewed: Optional[datetime] = None
    next_review_due: Optional[datetime] = None
    is_overdue: bool = False
    created_at: datetime
    updated_at: datetime
    tags: list[str] = Field(default_factory=list)
    handling_rules: Optional[HandlingRules] = None


class DataAssetUpdate(BaseModel):
    """Schema for updating a data asset (partial update)."""

    name: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    classification_level: Optional[ClassificationLevel] = None
    data_owner: Optional[str] = Field(default=None, max_length=200)
    data_steward: Optional[str] = Field(default=None, max_length=200)
    storage_location: Optional[str] = Field(default=None, max_length=500)
    retention_period_days: Optional[int] = Field(default=None, ge=1)
    encryption_required: Optional[bool] = None
    access_restrictions: Optional[list[str]] = None
    review_frequency_days: Optional[int] = Field(default=None, ge=1)
    tags: Optional[list[str]] = None


# ---------------------------------------------------------------------------
# Reclassification
# ---------------------------------------------------------------------------


class ReclassificationRequest(BaseModel):
    """Request to reclassify a data asset."""

    asset_id: str = Field(description="Asset to reclassify")
    current_level: ClassificationLevel = Field(description="Current classification")
    requested_level: ClassificationLevel = Field(description="Proposed new classification")
    justification: str = Field(min_length=10, max_length=2000, description="Why the change is needed")
    requested_by: str = Field(min_length=1, max_length=200, description="Who is requesting")


class ReclassificationResponse(BaseModel):
    """Response for a reclassification request."""

    request_id: str
    asset_id: str
    asset_name: str
    current_level: ClassificationLevel
    requested_level: ClassificationLevel
    justification: str
    requested_by: str
    status: ReclassificationStatus
    reviewer: Optional[str] = None
    review_notes: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Summary / Stats
# ---------------------------------------------------------------------------


class ClassificationSummary(BaseModel):
    """Summary statistics for the data classification inventory."""

    total_assets: int = 0
    by_level: dict[str, int] = Field(default_factory=dict)
    overdue_reviews: int = 0
    pending_reclassifications: int = 0
    encryption_coverage: float = Field(default=0.0, description="Percentage of assets with encryption")
    assets_with_dua_requirement: int = 0
    last_updated: datetime


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------


class DataRole(BaseModel):
    """Definition of a data governance role."""

    role_name: str
    description: str
    responsibilities: list[str]
    required_for_levels: list[ClassificationLevel]
