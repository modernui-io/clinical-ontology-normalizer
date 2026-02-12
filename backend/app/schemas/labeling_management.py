"""Pydantic schemas for Labeling Management (LABEL-MGMT).

Manages drug labeling lifecycle: label content sections, labeling negotiations
with health authorities, label artwork management, labeling change control,
country-specific labeling requirements, and labeling operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class LabelSection(str, Enum):
    INDICATIONS = "indications_and_usage"
    DOSAGE = "dosage_and_administration"
    DOSAGE_FORMS = "dosage_forms_and_strengths"
    CONTRAINDICATIONS = "contraindications"
    WARNINGS = "warnings_and_precautions"
    ADVERSE_REACTIONS = "adverse_reactions"
    DRUG_INTERACTIONS = "drug_interactions"
    USE_IN_POPULATIONS = "use_in_specific_populations"
    CLINICAL_PHARMACOLOGY = "clinical_pharmacology"
    CLINICAL_STUDIES = "clinical_studies"
    PATIENT_INFORMATION = "patient_information"
    BOXED_WARNING = "boxed_warning"


class LabelStatus(str, Enum):
    DRAFT = "draft"
    INTERNAL_REVIEW = "internal_review"
    HA_NEGOTIATION = "ha_negotiation"
    APPROVED = "approved"
    EFFECTIVE = "effective"
    SUPERSEDED = "superseded"


class NegotiationStatus(str, Enum):
    PROPOSED = "proposed"
    UNDER_DISCUSSION = "under_discussion"
    AGREED = "agreed"
    DISPUTED = "disputed"
    WITHDRAWN = "withdrawn"


class ArtworkStatus(str, Enum):
    DESIGN = "design"
    REVIEW = "review"
    PROOF = "proof"
    APPROVED = "approved"
    PRINT_READY = "print_ready"
    IN_PRODUCTION = "in_production"


class ChangeCategory(str, Enum):
    SAFETY_UPDATE = "safety_update"
    EFFICACY_UPDATE = "efficacy_update"
    NEW_INDICATION = "new_indication"
    FORMULATION_CHANGE = "formulation_change"
    MANUFACTURING_CHANGE = "manufacturing_change"
    ADMINISTRATIVE = "administrative"
    POST_MARKETING = "post_marketing"


class LabelContent(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    product_name: str
    version: str
    section: LabelSection
    content_text: str
    status: LabelStatus = LabelStatus.DRAFT
    language: str = "en"
    country: str | None = None
    effective_date: datetime | None = None
    expiry_date: datetime | None = None
    author: str
    reviewer: str | None = None
    approved_by: str | None = None
    approved_date: datetime | None = None
    created_at: datetime


class LabelNegotiation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    label_id: str
    trial_id: str
    health_authority: str
    section: LabelSection
    proposed_text: str
    ha_position: str | None = None
    agreed_text: str | None = None
    status: NegotiationStatus = NegotiationStatus.PROPOSED
    meeting_date: datetime | None = None
    negotiation_rounds: int = Field(ge=0, default=0)
    regulatory_contact: str
    internal_lead: str
    notes: str | None = None
    created_at: datetime


class LabelArtwork(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    label_id: str
    artwork_type: str
    file_name: str
    version: str
    status: ArtworkStatus = ArtworkStatus.DESIGN
    dimensions: str | None = None
    color_model: str | None = None
    language: str = "en"
    country: str | None = None
    designer: str
    reviewer: str | None = None
    approved_date: datetime | None = None
    print_specification: str | None = None
    created_at: datetime


class LabelChange(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    label_id: str
    trial_id: str
    change_category: ChangeCategory
    description: str
    affected_sections: list[LabelSection] = Field(default_factory=list)
    rationale: str
    safety_impact: bool = False
    regulatory_notification_required: bool = False
    implementation_date: datetime | None = None
    status: str = "pending"
    requested_by: str
    approved_by: str | None = None
    created_at: datetime


class CountryLabel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    label_id: str
    country: str
    language: str
    local_product_name: str | None = None
    translation_status: str = "pending"
    local_requirements: list[str] = Field(default_factory=list)
    deviation_from_core: str | None = None
    regulatory_authority: str
    approval_date: datetime | None = None
    implementation_date: datetime | None = None
    responsible_person: str
    created_at: datetime


class LabelContentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    product_name: str
    version: str
    section: LabelSection
    content_text: str
    language: str = "en"
    country: str | None = None
    author: str


class LabelContentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    content_text: str | None = None
    status: LabelStatus | None = None
    reviewer: str | None = None
    approved_by: str | None = None


class LabelNegotiationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    label_id: str
    trial_id: str
    health_authority: str
    section: LabelSection
    proposed_text: str
    regulatory_contact: str
    internal_lead: str


class LabelNegotiationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ha_position: str | None = None
    agreed_text: str | None = None
    status: NegotiationStatus | None = None
    negotiation_rounds: int | None = None
    notes: str | None = None


class LabelArtworkCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    label_id: str
    artwork_type: str
    file_name: str
    version: str
    language: str = "en"
    country: str | None = None
    designer: str


class LabelArtworkUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: ArtworkStatus | None = None
    reviewer: str | None = None
    print_specification: str | None = None


class LabelChangeCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    label_id: str
    trial_id: str
    change_category: ChangeCategory
    description: str
    affected_sections: list[LabelSection] = Field(default_factory=list)
    rationale: str
    safety_impact: bool = False
    requested_by: str


class LabelChangeUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str | None = None
    approved_by: str | None = None
    implementation_date: datetime | None = None
    regulatory_notification_required: bool | None = None


class CountryLabelCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    label_id: str
    country: str
    language: str
    regulatory_authority: str
    responsible_person: str
    local_product_name: str | None = None
    local_requirements: list[str] = Field(default_factory=list)


class CountryLabelUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    translation_status: str | None = None
    deviation_from_core: str | None = None
    approval_date: datetime | None = None
    implementation_date: datetime | None = None


class LabelContentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[LabelContent] = Field(default_factory=list)
    total: int = Field(ge=0)


class LabelNegotiationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[LabelNegotiation] = Field(default_factory=list)
    total: int = Field(ge=0)


class LabelArtworkListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[LabelArtwork] = Field(default_factory=list)
    total: int = Field(ge=0)


class LabelChangeListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[LabelChange] = Field(default_factory=list)
    total: int = Field(ge=0)


class CountryLabelListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CountryLabel] = Field(default_factory=list)
    total: int = Field(ge=0)


class LabelingMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_labels: int = Field(ge=0)
    labels_by_status: dict[str, int] = Field(default_factory=dict)
    labels_by_section: dict[str, int] = Field(default_factory=dict)
    total_negotiations: int = Field(ge=0)
    negotiations_by_status: dict[str, int] = Field(default_factory=dict)
    avg_negotiation_rounds: float = Field(ge=0)
    total_artworks: int = Field(ge=0)
    artworks_by_status: dict[str, int] = Field(default_factory=dict)
    total_changes: int = Field(ge=0)
    changes_by_category: dict[str, int] = Field(default_factory=dict)
    safety_changes: int = Field(ge=0)
    total_country_labels: int = Field(ge=0)
    countries_covered: int = Field(ge=0)
