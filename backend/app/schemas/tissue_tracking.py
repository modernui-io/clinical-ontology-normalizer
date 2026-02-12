"""Pydantic schemas for Tissue Tracking Management (TISSUE-TRK).

Manages tissue specimen operations: tissue collection tracking, FFPE block
management, slide preparation, pathology review workflow, tissue inventory,
and tissue tracking operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TissueType(str, Enum):
    BIOPSY = "biopsy"
    RESECTION = "resection"
    FINE_NEEDLE_ASPIRATE = "fine_needle_aspirate"
    CORE_NEEDLE = "core_needle"
    PUNCH = "punch"
    EXCISIONAL = "excisional"
    BONE_MARROW = "bone_marrow"
    LIQUID_BIOPSY = "liquid_biopsy"


class PreservationMethod(str, Enum):
    FFPE = "formalin_fixed_paraffin_embedded"
    FRESH_FROZEN = "fresh_frozen"
    OCT = "optimal_cutting_temperature"
    RNA_LATER = "rna_later"
    SNAP_FROZEN = "snap_frozen"
    FRESH = "fresh"


class SpecimenStatus(str, Enum):
    COLLECTED = "collected"
    IN_TRANSIT = "in_transit"
    RECEIVED = "received"
    PROCESSING = "processing"
    STORED = "stored"
    DEPLETED = "depleted"
    DISCARDED = "discarded"
    QUALITY_FAILED = "quality_failed"


class SlideStatus(str, Enum):
    PREPARED = "prepared"
    STAINED = "stained"
    UNDER_REVIEW = "under_review"
    REVIEWED = "reviewed"
    RESCANNED = "rescanned"
    ARCHIVED = "archived"


class PathologyResult(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    EQUIVOCAL = "equivocal"
    INSUFFICIENT = "insufficient_tissue"
    PENDING = "pending"


class TissueSpecimen(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    site_id: str
    tissue_type: TissueType
    preservation_method: PreservationMethod
    status: SpecimenStatus = SpecimenStatus.COLLECTED
    collection_date: datetime
    body_site: str
    laterality: str | None = None
    tumor_type: str | None = None
    specimen_weight_mg: float | None = None
    block_count: int = Field(ge=0, default=0)
    sections_available: int = Field(ge=0, default=0)
    quality_score: float | None = None
    ischemia_time_minutes: int | None = None
    collected_by: str
    pathologist: str | None = None
    storage_location: str | None = None
    created_at: datetime


class FFPEBlock(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    specimen_id: str
    block_identifier: str
    fixation_time_hours: float | None = None
    embedding_date: datetime | None = None
    sections_cut: int = Field(ge=0, default=0)
    sections_remaining: int = Field(ge=0, default=0)
    thickness_microns: float = 4.0
    tumor_content_pct: float | None = None
    necrosis_pct: float | None = None
    storage_location: str | None = None
    temperature_c: float | None = None
    quality_adequate: bool = True
    created_at: datetime


class TissueSlide(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    block_id: str
    specimen_id: str
    slide_identifier: str
    stain_type: str
    status: SlideStatus = SlideStatus.PREPARED
    section_number: int = Field(ge=1)
    preparation_date: datetime
    staining_date: datetime | None = None
    scanner_used: str | None = None
    scan_resolution: str | None = None
    image_file_path: str | None = None
    prepared_by: str
    reviewed_by: str | None = None
    review_date: datetime | None = None
    created_at: datetime


class PathologyReview(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    specimen_id: str
    slide_id: str | None = None
    trial_id: str
    subject_id: str
    reviewer: str
    review_date: datetime
    result: PathologyResult = PathologyResult.PENDING
    diagnosis: str | None = None
    biomarker_name: str | None = None
    biomarker_result: str | None = None
    scoring_method: str | None = None
    score_value: str | None = None
    tumor_cellularity_pct: float | None = None
    comments: str | None = None
    adjudication_required: bool = False
    adjudicated_by: str | None = None
    created_at: datetime


class TissueShipment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    origin_site_id: str
    destination_lab: str
    shipment_date: datetime
    arrival_date: datetime | None = None
    specimen_count: int = Field(ge=0, default=0)
    tracking_number: str | None = None
    courier: str
    temperature_condition: str
    temperature_monitored: bool = True
    excursion_detected: bool = False
    status: str = "in_transit"
    received_by: str | None = None
    created_at: datetime


class TissueSpecimenCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    site_id: str
    tissue_type: TissueType
    preservation_method: PreservationMethod
    body_site: str
    collected_by: str
    laterality: str | None = None
    tumor_type: str | None = None


class TissueSpecimenUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: SpecimenStatus | None = None
    quality_score: float | None = None
    pathologist: str | None = None
    storage_location: str | None = None
    block_count: int | None = None
    sections_available: int | None = None


class FFPEBlockCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    specimen_id: str
    block_identifier: str
    fixation_time_hours: float | None = None
    thickness_microns: float = 4.0


class FFPEBlockUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    sections_cut: int | None = None
    sections_remaining: int | None = None
    tumor_content_pct: float | None = None
    necrosis_pct: float | None = None
    quality_adequate: bool | None = None


class TissueSlideCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    block_id: str
    specimen_id: str
    slide_identifier: str
    stain_type: str
    section_number: int = Field(ge=1)
    prepared_by: str


class TissueSlideUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: SlideStatus | None = None
    reviewed_by: str | None = None
    scanner_used: str | None = None
    image_file_path: str | None = None


class PathologyReviewCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    specimen_id: str
    trial_id: str
    subject_id: str
    reviewer: str
    slide_id: str | None = None
    biomarker_name: str | None = None


class PathologyReviewUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    result: PathologyResult | None = None
    diagnosis: str | None = None
    biomarker_result: str | None = None
    score_value: str | None = None
    adjudication_required: bool | None = None
    adjudicated_by: str | None = None


class TissueShipmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    origin_site_id: str
    destination_lab: str
    courier: str
    temperature_condition: str
    specimen_count: int = Field(ge=0, default=0)
    tracking_number: str | None = None


class TissueShipmentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str | None = None
    received_by: str | None = None
    excursion_detected: bool | None = None


class TissueSpecimenListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[TissueSpecimen] = Field(default_factory=list)
    total: int = Field(ge=0)


class FFPEBlockListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[FFPEBlock] = Field(default_factory=list)
    total: int = Field(ge=0)


class TissueSlideListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[TissueSlide] = Field(default_factory=list)
    total: int = Field(ge=0)


class PathologyReviewListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[PathologyReview] = Field(default_factory=list)
    total: int = Field(ge=0)


class TissueShipmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[TissueShipment] = Field(default_factory=list)
    total: int = Field(ge=0)


class TissueTrackingMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_specimens: int = Field(ge=0)
    specimens_by_type: dict[str, int] = Field(default_factory=dict)
    specimens_by_status: dict[str, int] = Field(default_factory=dict)
    specimens_by_preservation: dict[str, int] = Field(default_factory=dict)
    total_blocks: int = Field(ge=0)
    total_slides: int = Field(ge=0)
    slides_by_status: dict[str, int] = Field(default_factory=dict)
    total_reviews: int = Field(ge=0)
    reviews_by_result: dict[str, int] = Field(default_factory=dict)
    pending_reviews: int = Field(ge=0)
    total_shipments: int = Field(ge=0)
    shipments_with_excursions: int = Field(ge=0)
