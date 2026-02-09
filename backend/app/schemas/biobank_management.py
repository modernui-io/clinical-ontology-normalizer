"""Pydantic schemas for Biospecimen & Biobank Management (CLINICAL-17).

Manages biospecimen collection, aliquot tracking with chain of custody,
biorepository storage with capacity monitoring, consent scope validation,
quality scoring, specimen genealogy, and shipment manifests.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SpecimenType(str, Enum):
    """Type of biological specimen collected."""

    SERUM = "serum"
    PLASMA = "plasma"
    WHOLE_BLOOD = "whole_blood"
    PBMC = "pbmc"
    DNA = "dna"
    RNA = "rna"
    TISSUE_FFPE = "tissue_ffpe"
    TISSUE_FROZEN = "tissue_frozen"
    URINE = "urine"
    CSF = "csf"
    SALIVA = "saliva"
    STOOL = "stool"


class StorageType(str, Enum):
    """Storage condition for specimens and aliquots."""

    MINUS80_FREEZER = "minus80_freezer"
    MINUS20_FREEZER = "minus20_freezer"
    LIQUID_NITROGEN = "liquid_nitrogen"
    REFRIGERATOR_4C = "refrigerator_4c"
    AMBIENT = "ambient"


class ConsentScope(str, Enum):
    """Scope of consent granted for specimen use."""

    PRIMARY_STUDY = "primary_study"
    FUTURE_RESEARCH = "future_research"
    GENETIC_ANALYSIS = "genetic_analysis"
    COMMERCIAL_USE = "commercial_use"
    INDEFINITE_STORAGE = "indefinite_storage"


class AliquotStatus(str, Enum):
    """Lifecycle status of an aliquot."""

    AVAILABLE = "available"
    RESERVED = "reserved"
    SHIPPED = "shipped"
    USED = "used"
    DEPLETED = "depleted"
    DESTROYED = "destroyed"
    QC_FAILED = "qc_failed"


class BiorepositoryType(str, Enum):
    """Type of biorepository facility."""

    CENTRAL = "central"
    REGIONAL = "regional"
    SITE_LEVEL = "site_level"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class BiospecimenCollection(BaseModel):
    """A biospecimen collection event from a patient visit."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique specimen identifier")
    patient_id: str = Field(..., description="Patient identifier")
    trial_id: str = Field(..., description="Clinical trial identifier")
    site_id: str = Field(..., description="Collection site identifier")
    specimen_type: SpecimenType = Field(..., description="Type of specimen collected")
    collection_date: datetime = Field(..., description="Date of specimen collection")
    collection_time: str = Field(..., description="Time of collection (HH:MM)")
    collector: str = Field(..., description="Name of the person who collected the specimen")
    protocol_visit: str = Field(..., description="Protocol visit identifier (e.g., Visit 1, Week 4)")
    fasting_status: bool = Field(default=False, description="Whether the patient was fasting at collection")
    processing_time_minutes: int = Field(
        ge=0, description="Time from collection to processing in minutes"
    )
    parent_specimen_id: str | None = Field(
        None, description="Parent specimen ID for derived specimens"
    )


class Aliquot(BaseModel):
    """An aliquot derived from a biospecimen."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique aliquot identifier")
    specimen_id: str = Field(..., description="Parent specimen identifier")
    aliquot_number: int = Field(ge=1, description="Sequential aliquot number within specimen")
    barcode: str = Field(..., description="Physical barcode label")
    volume_ul: float = Field(ge=0.0, description="Volume in microliters")
    concentration: float | None = Field(None, description="Concentration (ng/uL for DNA/RNA)")
    storage_type: StorageType = Field(..., description="Storage condition")
    freezer_id: str = Field(..., description="Freezer/storage unit identifier")
    rack: str = Field(..., description="Rack position within freezer")
    box: str = Field(..., description="Box position within rack")
    position: str = Field(..., description="Well/slot position within box")
    status: AliquotStatus = Field(
        default=AliquotStatus.AVAILABLE, description="Current aliquot status"
    )
    freeze_thaw_cycles: int = Field(default=0, ge=0, description="Number of freeze-thaw cycles")
    quality_score: float = Field(
        default=100.0, ge=0.0, le=100.0, description="Quality score (0-100)"
    )


class Biorepository(BaseModel):
    """A biorepository facility for specimen storage."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique biorepository identifier")
    name: str = Field(..., description="Facility name")
    type: BiorepositoryType = Field(..., description="Biorepository type")
    location: str = Field(..., description="Physical location (city, state)")
    capacity_total: int = Field(ge=0, description="Total storage capacity (number of aliquots)")
    capacity_used: int = Field(ge=0, description="Currently used capacity")
    temperature_monitored: bool = Field(
        default=True, description="Whether temperature is continuously monitored"
    )
    backup_power: bool = Field(
        default=True, description="Whether backup power is available"
    )
    certifications: list[str] = Field(
        default_factory=list, description="Facility certifications (e.g., CAP, CLIA)"
    )


class ConsentRecord(BaseModel):
    """A consent record for specimen use."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique consent record identifier")
    patient_id: str = Field(..., description="Patient identifier")
    specimen_id: str = Field(..., description="Associated specimen identifier")
    scope: list[ConsentScope] = Field(
        ..., description="Granted consent scopes"
    )
    consent_date: datetime = Field(..., description="Date consent was obtained")
    withdrawal_date: datetime | None = Field(
        None, description="Date consent was withdrawn (None if active)"
    )
    consent_version: str = Field(..., description="Version of consent form used")


class ShipmentManifest(BaseModel):
    """A shipment manifest for transporting aliquots between repositories."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique shipment identifier")
    from_repository: str = Field(..., description="Source biorepository ID")
    to_repository: str = Field(..., description="Destination biorepository ID")
    aliquot_ids: list[str] = Field(..., description="List of aliquot IDs in shipment")
    shipped_date: datetime = Field(..., description="Date shipment was sent")
    received_date: datetime | None = Field(
        None, description="Date shipment was received"
    )
    temperature_log: list[float] = Field(
        default_factory=list,
        description="Temperature readings during transit (Celsius)",
    )
    condition_on_arrival: str | None = Field(
        None, description="Condition assessment upon arrival"
    )


# ---------------------------------------------------------------------------
# Metrics / dashboard
# ---------------------------------------------------------------------------


class BiobankMetrics(BaseModel):
    """Aggregated biobank operational metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_specimens: int = Field(ge=0, description="Total specimens collected")
    total_aliquots: int = Field(ge=0, description="Total aliquots created")
    aliquots_by_status: dict[str, int] = Field(
        default_factory=dict, description="Aliquot counts by status"
    )
    storage_utilization_pct: float = Field(
        ge=0.0, le=100.0, description="Overall storage utilization percentage"
    )
    avg_quality_score: float = Field(
        ge=0.0, le=100.0, description="Average aliquot quality score"
    )
    consent_withdrawal_rate: float = Field(
        ge=0.0, le=100.0, description="Percentage of consents withdrawn"
    )
    shipments_in_transit: int = Field(
        ge=0, description="Number of shipments currently in transit"
    )


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class SpecimenCreate(BaseModel):
    """Request to register a new biospecimen collection."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str = Field(..., description="Patient identifier")
    trial_id: str = Field(..., description="Clinical trial identifier")
    site_id: str = Field(..., description="Collection site identifier")
    specimen_type: SpecimenType = Field(..., description="Specimen type")
    collection_date: datetime = Field(..., description="Collection date")
    collection_time: str = Field(..., description="Collection time (HH:MM)")
    collector: str = Field(..., description="Collector name")
    protocol_visit: str = Field(..., description="Protocol visit")
    fasting_status: bool = Field(default=False, description="Fasting status")
    processing_time_minutes: int = Field(ge=0, description="Processing time in minutes")
    parent_specimen_id: str | None = Field(None, description="Parent specimen ID")


class SpecimenUpdate(BaseModel):
    """Request to update a specimen record."""

    model_config = ConfigDict(from_attributes=True)

    collector: str | None = Field(None, description="Collector name")
    protocol_visit: str | None = Field(None, description="Protocol visit")
    fasting_status: bool | None = Field(None, description="Fasting status")
    processing_time_minutes: int | None = Field(None, ge=0, description="Processing time")


class AliquotCreate(BaseModel):
    """Request to create an aliquot from a specimen."""

    model_config = ConfigDict(from_attributes=True)

    specimen_id: str = Field(..., description="Parent specimen ID")
    volume_ul: float = Field(ge=0.0, description="Volume in microliters")
    concentration: float | None = Field(None, description="Concentration")
    storage_type: StorageType = Field(..., description="Storage type")
    freezer_id: str = Field(..., description="Freezer ID")
    rack: str = Field(..., description="Rack position")
    box: str = Field(..., description="Box position")
    position: str = Field(..., description="Well position")


class AliquotUpdate(BaseModel):
    """Request to update an aliquot."""

    model_config = ConfigDict(from_attributes=True)

    status: AliquotStatus | None = Field(None, description="Aliquot status")
    volume_ul: float | None = Field(None, ge=0.0, description="Volume")
    storage_type: StorageType | None = Field(None, description="Storage type")
    freezer_id: str | None = Field(None, description="Freezer ID")
    rack: str | None = Field(None, description="Rack")
    box: str | None = Field(None, description="Box")
    position: str | None = Field(None, description="Position")
    freeze_thaw_cycles: int | None = Field(None, ge=0, description="Freeze-thaw cycles")


class AliquotReserve(BaseModel):
    """Request to reserve an aliquot for use."""

    model_config = ConfigDict(from_attributes=True)

    purpose: str = Field(..., description="Purpose for reservation")
    required_scopes: list[ConsentScope] = Field(
        ..., description="Required consent scopes for this use"
    )


class ConsentCreate(BaseModel):
    """Request to create a consent record."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str = Field(..., description="Patient ID")
    specimen_id: str = Field(..., description="Specimen ID")
    scope: list[ConsentScope] = Field(..., description="Consent scopes")
    consent_date: datetime = Field(..., description="Consent date")
    consent_version: str = Field(..., description="Consent form version")


class ConsentWithdraw(BaseModel):
    """Request to withdraw consent for a specimen."""

    model_config = ConfigDict(from_attributes=True)

    reason: str | None = Field(None, description="Reason for withdrawal")


class ShipmentCreate(BaseModel):
    """Request to create a shipment manifest."""

    model_config = ConfigDict(from_attributes=True)

    from_repository: str = Field(..., description="Source repository ID")
    to_repository: str = Field(..., description="Destination repository ID")
    aliquot_ids: list[str] = Field(..., description="Aliquot IDs to ship")


class ShipmentReceive(BaseModel):
    """Request to mark a shipment as received."""

    model_config = ConfigDict(from_attributes=True)

    condition_on_arrival: str = Field(..., description="Condition assessment")
    temperature_log: list[float] = Field(
        default_factory=list, description="Temperature readings during transit"
    )


class BiorepositoryCreate(BaseModel):
    """Request to register a new biorepository."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Facility name")
    type: BiorepositoryType = Field(..., description="Biorepository type")
    location: str = Field(..., description="Physical location")
    capacity_total: int = Field(ge=0, description="Total capacity")
    temperature_monitored: bool = Field(default=True, description="Temperature monitored")
    backup_power: bool = Field(default=True, description="Backup power available")
    certifications: list[str] = Field(default_factory=list, description="Certifications")


class BiorepositoryUpdate(BaseModel):
    """Request to update a biorepository."""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = Field(None, description="Facility name")
    location: str | None = Field(None, description="Location")
    capacity_total: int | None = Field(None, ge=0, description="Total capacity")
    temperature_monitored: bool | None = Field(None, description="Temperature monitored")
    backup_power: bool | None = Field(None, description="Backup power")
    certifications: list[str] | None = Field(None, description="Certifications")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class SpecimenListResponse(BaseModel):
    """List of biospecimen collections."""

    model_config = ConfigDict(from_attributes=True)

    items: list[BiospecimenCollection] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class AliquotListResponse(BaseModel):
    """List of aliquots."""

    model_config = ConfigDict(from_attributes=True)

    items: list[Aliquot] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class BiorepositoryListResponse(BaseModel):
    """List of biorepositories."""

    model_config = ConfigDict(from_attributes=True)

    items: list[Biorepository] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class ConsentListResponse(BaseModel):
    """List of consent records."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ConsentRecord] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class ShipmentListResponse(BaseModel):
    """List of shipment manifests."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ShipmentManifest] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Specimen genealogy
# ---------------------------------------------------------------------------


class SpecimenGenealogy(BaseModel):
    """Genealogy tree for a specimen showing parent-child relationships."""

    model_config = ConfigDict(from_attributes=True)

    specimen: BiospecimenCollection = Field(..., description="The specimen")
    aliquots: list[Aliquot] = Field(default_factory=list, description="Derived aliquots")
    child_specimens: list[BiospecimenCollection] = Field(
        default_factory=list, description="Child specimens derived from this specimen"
    )


# ---------------------------------------------------------------------------
# Storage capacity alert
# ---------------------------------------------------------------------------


class StorageCapacityAlert(BaseModel):
    """Alert for a biorepository nearing capacity."""

    model_config = ConfigDict(from_attributes=True)

    repository_id: str = Field(..., description="Biorepository ID")
    repository_name: str = Field(..., description="Biorepository name")
    utilization_pct: float = Field(
        ge=0.0, le=100.0, description="Current utilization percentage"
    )
    capacity_total: int = Field(ge=0, description="Total capacity")
    capacity_used: int = Field(ge=0, description="Used capacity")
    capacity_remaining: int = Field(ge=0, description="Remaining capacity")
    alert_level: str = Field(..., description="Alert level (warning, critical)")
