"""Pydantic schemas for Specimen Management (SPEC-MGT).

Manages specimen management operations: collection tracking, storage
inventory, chain of custody records, shipping logistics, and specimen
quality control with specimen metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SpecimenType(str, Enum):
    BLOOD = "blood"
    SERUM = "serum"
    PLASMA = "plasma"
    URINE = "urine"
    TISSUE = "tissue"
    CSF = "csf"


class CollectionStatus(str, Enum):
    SCHEDULED = "scheduled"
    COLLECTED = "collected"
    MISSED = "missed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    RECOLLECTION_NEEDED = "recollection_needed"


class StorageCondition(str, Enum):
    ROOM_TEMP = "room_temp"
    REFRIGERATED = "refrigerated"
    FROZEN_MINUS_20 = "frozen_minus_20"
    FROZEN_MINUS_80 = "frozen_minus_80"
    LIQUID_NITROGEN = "liquid_nitrogen"
    DRY_ICE = "dry_ice"


class ShippingStatus(str, Enum):
    PENDING = "pending"
    PACKED = "packed"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    RETURNED = "returned"
    LOST = "lost"


class QCResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    BORDERLINE = "borderline"
    REPEAT_NEEDED = "repeat_needed"
    NOT_TESTED = "not_tested"


class CollectionRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    site_id: str
    specimen_type: SpecimenType
    collection_status: CollectionStatus = CollectionStatus.SCHEDULED
    visit_number: int = Field(ge=1, default=1)
    collection_date: datetime | None = None
    scheduled_date: datetime
    tube_count: int = Field(ge=0, default=1)
    volume_ml: float = Field(ge=0, default=0.0)
    fasting_required: bool = False
    fasting_confirmed: bool = False
    collection_time_critical: bool = False
    protocol_timepoint: str
    collected_by: str | None = None
    notes: str | None = None
    created_at: datetime


class StorageInventory(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    specimen_id: str
    storage_condition: StorageCondition
    freezer_id: str
    rack_position: str
    box_number: str
    slot_number: str
    aliquot_number: int = Field(ge=1, default=1)
    volume_remaining_ml: float = Field(ge=0, default=0.0)
    date_stored: datetime
    expiry_date: datetime | None = None
    is_available: bool = True
    thaw_count: int = Field(ge=0, default=0)
    max_thaw_cycles: int = Field(ge=0, default=3)
    managed_by: str
    notes: str | None = None
    created_at: datetime


class ChainOfCustody(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    specimen_id: str
    custody_event: str
    event_date: datetime
    from_location: str
    to_location: str
    from_person: str
    to_person: str
    temperature_at_transfer: float | None = None
    temperature_within_range: bool = True
    condition_at_transfer: str = "acceptable"
    witnessed: bool = False
    witness_name: str | None = None
    documentation_complete: bool = True
    recorded_by: str
    notes: str | None = None
    created_at: datetime


class ShippingLogistic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    shipment_number: str
    shipping_status: ShippingStatus = ShippingStatus.PENDING
    origin_site: str
    destination_site: str
    specimen_count: int = Field(ge=0, default=0)
    shipping_condition: StorageCondition
    carrier_name: str
    tracking_number: str | None = None
    ship_date: datetime | None = None
    expected_delivery_date: datetime | None = None
    actual_delivery_date: datetime | None = None
    temperature_monitored: bool = True
    temperature_excursion: bool = False
    excursion_duration_minutes: int = Field(ge=0, default=0)
    prepared_by: str
    received_by: str | None = None
    notes: str | None = None
    created_at: datetime


class SpecimenQC(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    specimen_id: str
    qc_date: datetime
    qc_result: QCResult = QCResult.NOT_TESTED
    test_performed: str
    hemolysis_index: float | None = None
    lipemia_index: float | None = None
    icterus_index: float | None = None
    volume_adequate: bool = True
    labeling_correct: bool = True
    container_integrity: bool = True
    acceptance_criteria_met: bool = True
    corrective_action: str | None = None
    performed_by: str
    reviewed_by: str | None = None
    notes: str | None = None
    created_at: datetime


class CollectionRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    site_id: str
    specimen_type: SpecimenType
    protocol_timepoint: str
    scheduled_date: datetime
    tube_count: int = Field(ge=0, default=1)
    volume_ml: float = Field(ge=0, default=0.0)


class CollectionRecordUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    collection_status: CollectionStatus | None = None
    collection_date: datetime | None = None
    collected_by: str | None = None
    fasting_confirmed: bool | None = None
    notes: str | None = None


class StorageInventoryCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    specimen_id: str
    storage_condition: StorageCondition
    freezer_id: str
    rack_position: str
    box_number: str
    slot_number: str
    managed_by: str
    volume_remaining_ml: float = Field(ge=0, default=0.0)


class StorageInventoryUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    is_available: bool | None = None
    volume_remaining_ml: float | None = None
    thaw_count: int | None = None
    expiry_date: datetime | None = None
    notes: str | None = None


class ChainOfCustodyCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    specimen_id: str
    custody_event: str
    from_location: str
    to_location: str
    from_person: str
    to_person: str
    recorded_by: str


class ChainOfCustodyUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    temperature_within_range: bool | None = None
    condition_at_transfer: str | None = None
    witnessed: bool | None = None
    witness_name: str | None = None
    notes: str | None = None


class ShippingLogisticCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    shipment_number: str
    origin_site: str
    destination_site: str
    shipping_condition: StorageCondition
    carrier_name: str
    prepared_by: str
    specimen_count: int = Field(ge=0, default=0)


class ShippingLogisticUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    shipping_status: ShippingStatus | None = None
    tracking_number: str | None = None
    actual_delivery_date: datetime | None = None
    temperature_excursion: bool | None = None
    received_by: str | None = None
    notes: str | None = None


class SpecimenQCCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    specimen_id: str
    test_performed: str
    performed_by: str
    qc_result: QCResult = QCResult.NOT_TESTED
    volume_adequate: bool = True


class SpecimenQCUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    qc_result: QCResult | None = None
    acceptance_criteria_met: bool | None = None
    corrective_action: str | None = None
    reviewed_by: str | None = None
    notes: str | None = None


class CollectionRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CollectionRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


class StorageInventoryListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[StorageInventory] = Field(default_factory=list)
    total: int = Field(ge=0)


class ChainOfCustodyListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ChainOfCustody] = Field(default_factory=list)
    total: int = Field(ge=0)


class ShippingLogisticListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ShippingLogistic] = Field(default_factory=list)
    total: int = Field(ge=0)


class SpecimenQCListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SpecimenQC] = Field(default_factory=list)
    total: int = Field(ge=0)


class SpecimenManagementMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_collections: int = Field(ge=0)
    collections_by_type: dict[str, int] = Field(default_factory=dict)
    collections_by_status: dict[str, int] = Field(default_factory=dict)
    collection_completion_rate: float = Field(ge=0)
    total_stored_specimens: int = Field(ge=0)
    specimens_by_condition: dict[str, int] = Field(default_factory=dict)
    available_specimens: int = Field(ge=0)
    total_custody_events: int = Field(ge=0)
    temperature_excursions_custody: int = Field(ge=0)
    total_shipments: int = Field(ge=0)
    shipments_by_status: dict[str, int] = Field(default_factory=dict)
    temperature_excursions_shipping: int = Field(ge=0)
    total_qc_records: int = Field(ge=0)
    qc_by_result: dict[str, int] = Field(default_factory=dict)
    qc_pass_rate: float = Field(ge=0)
