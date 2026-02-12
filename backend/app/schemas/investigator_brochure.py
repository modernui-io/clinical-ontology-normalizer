"""Pydantic schemas for Investigator Brochure Management (IB-MGMT).

Manages investigator brochure operations: IB version tracking,
safety update records, distribution management, revision history,
and acknowledgment records with compliance metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class IBStatus(str, Enum):
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    DISTRIBUTED = "distributed"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


class UpdateType(str, Enum):
    SCHEDULED = "scheduled"
    SAFETY_DRIVEN = "safety_driven"
    REGULATORY_REQUEST = "regulatory_request"
    NEW_DATA = "new_data"
    CORRECTION = "correction"


class DistributionMethod(str, Enum):
    ELECTRONIC = "electronic"
    PAPER = "paper"
    PORTAL = "portal"
    REGISTERED_MAIL = "registered_mail"
    HYBRID = "hybrid"


class AcknowledgmentStatus(str, Enum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    OVERDUE = "overdue"
    WAIVED = "waived"
    ESCALATED = "escalated"


class RevisionScope(str, Enum):
    MINOR = "minor"
    MAJOR = "major"
    SAFETY_ADDENDUM = "safety_addendum"
    FULL_REWRITE = "full_rewrite"
    ADMINISTRATIVE = "administrative"


class IBVersion(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    version_number: str
    edition_number: int = Field(ge=1, default=1)
    status: IBStatus = IBStatus.DRAFT
    effective_date: datetime | None = None
    superseded_date: datetime | None = None
    page_count: int = Field(ge=0, default=0)
    sections_updated: list[str] = Field(default_factory=list)
    preclinical_data_current: bool = True
    clinical_data_current: bool = True
    safety_data_cutoff: datetime | None = None
    approved_by: str | None = None
    approval_date: datetime | None = None
    authored_by: str
    regulatory_references: list[str] = Field(default_factory=list)
    notes: str | None = None
    created_at: datetime


class SafetyUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    ib_version_id: str | None = None
    update_type: UpdateType
    update_date: datetime
    safety_signal: str
    affected_sections: list[str] = Field(default_factory=list)
    new_risk_identified: bool = False
    risk_category: str = "low"
    regulatory_notification_required: bool = False
    regulatory_notified: bool = False
    notification_date: datetime | None = None
    dsmb_informed: bool = False
    investigator_notification_required: bool = True
    days_to_distribute: int = Field(ge=0, default=0)
    prepared_by: str
    reviewed_by: str | None = None
    notes: str | None = None
    created_at: datetime


class DistributionRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    ib_version_id: str
    site_id: str
    investigator_name: str
    distribution_method: DistributionMethod
    distribution_date: datetime
    received_date: datetime | None = None
    receipt_confirmed: bool = False
    prior_version_recalled: bool = False
    recall_date: datetime | None = None
    tracking_number: str | None = None
    distributed_by: str
    notes: str | None = None
    created_at: datetime


class RevisionHistory(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    ib_version_id: str
    revision_date: datetime
    revision_scope: RevisionScope
    section_number: str
    section_title: str
    change_description: str
    rationale: str
    data_source: str | None = None
    regulatory_driven: bool = False
    safety_driven: bool = False
    pages_affected: int = Field(ge=0, default=0)
    revised_by: str
    approved_by: str | None = None
    created_at: datetime


class AcknowledgmentRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    ib_version_id: str
    distribution_id: str | None = None
    investigator_name: str
    site_id: str
    status: AcknowledgmentStatus = AcknowledgmentStatus.PENDING
    sent_date: datetime
    due_date: datetime | None = None
    acknowledged_date: datetime | None = None
    reminder_count: int = Field(ge=0, default=0)
    last_reminder_date: datetime | None = None
    escalation_date: datetime | None = None
    signature_on_file: bool = False
    managed_by: str
    notes: str | None = None
    created_at: datetime


class IBVersionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    version_number: str
    authored_by: str
    edition_number: int = Field(ge=1, default=1)
    page_count: int = Field(ge=0, default=0)


class IBVersionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: IBStatus | None = None
    approved_by: str | None = None
    safety_data_cutoff: datetime | None = None
    sections_updated: list[str] | None = None
    notes: str | None = None


class SafetyUpdateCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    update_type: UpdateType
    safety_signal: str
    prepared_by: str
    ib_version_id: str | None = None
    new_risk_identified: bool = False


class SafetyUpdateUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    reviewed_by: str | None = None
    regulatory_notified: bool | None = None
    dsmb_informed: bool | None = None
    risk_category: str | None = None
    notes: str | None = None


class DistributionRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    ib_version_id: str
    site_id: str
    investigator_name: str
    distribution_method: DistributionMethod
    distributed_by: str


class DistributionRecordUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    receipt_confirmed: bool | None = None
    prior_version_recalled: bool | None = None
    tracking_number: str | None = None
    notes: str | None = None


class RevisionHistoryCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    ib_version_id: str
    section_number: str
    section_title: str
    change_description: str
    rationale: str
    revision_scope: RevisionScope
    revised_by: str
    pages_affected: int = Field(ge=0, default=0)


class RevisionHistoryUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    approved_by: str | None = None
    regulatory_driven: bool | None = None
    safety_driven: bool | None = None
    notes: str | None = None


class AcknowledgmentRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    ib_version_id: str
    investigator_name: str
    site_id: str
    managed_by: str
    distribution_id: str | None = None


class AcknowledgmentRecordUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: AcknowledgmentStatus | None = None
    signature_on_file: bool | None = None
    reminder_count: int | None = None
    notes: str | None = None


class IBVersionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[IBVersion] = Field(default_factory=list)
    total: int = Field(ge=0)


class SafetyUpdateListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SafetyUpdate] = Field(default_factory=list)
    total: int = Field(ge=0)


class DistributionRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DistributionRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


class RevisionHistoryListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[RevisionHistory] = Field(default_factory=list)
    total: int = Field(ge=0)


class AcknowledgmentRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[AcknowledgmentRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


class InvestigatorBrochureMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_versions: int = Field(ge=0)
    versions_by_status: dict[str, int] = Field(default_factory=dict)
    current_versions: int = Field(ge=0)
    total_safety_updates: int = Field(ge=0)
    updates_by_type: dict[str, int] = Field(default_factory=dict)
    new_risks_identified: int = Field(ge=0)
    total_distributions: int = Field(ge=0)
    distributions_confirmed: int = Field(ge=0)
    total_revisions: int = Field(ge=0)
    revisions_by_scope: dict[str, int] = Field(default_factory=dict)
    total_acknowledgments: int = Field(ge=0)
    acknowledgments_by_status: dict[str, int] = Field(default_factory=dict)
    overdue_acknowledgments: int = Field(ge=0)
