"""Pydantic schemas for Clinical Supply Returns Management (SUPPLY-RET).

Manages investigational product returns, drug accountability reconciliation,
destruction tracking, temperature excursion documentation, quarantine management,
and returns metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ReturnStatus(str, Enum):
    """Lifecycle status of a supply return."""

    INITIATED = "initiated"
    PACKAGED = "packaged"
    SHIPPED = "shipped"
    RECEIVED = "received"
    INSPECTED = "inspected"
    QUARANTINED = "quarantined"
    APPROVED_FOR_DESTRUCTION = "approved_for_destruction"
    DESTROYED = "destroyed"
    DISCREPANCY = "discrepancy"


class ReturnReason(str, Enum):
    """Reason for returning clinical supplies."""

    STUDY_COMPLETION = "study_completion"
    PATIENT_WITHDRAWAL = "patient_withdrawal"
    EXPIRED = "expired"
    DAMAGED = "damaged"
    TEMPERATURE_EXCURSION = "temperature_excursion"
    PROTOCOL_AMENDMENT = "protocol_amendment"
    SITE_CLOSURE = "site_closure"
    RECALL = "recall"
    EXCESS_INVENTORY = "excess_inventory"


class DestructionMethod(str, Enum):
    """Method of clinical supply destruction."""

    INCINERATION = "incineration"
    CHEMICAL = "chemical"
    AUTOCLAVING = "autoclaving"
    LANDFILL = "landfill"
    RETURN_TO_MANUFACTURER = "return_to_manufacturer"


class QuarantineReason(str, Enum):
    """Reason for quarantining supplies."""

    TEMPERATURE_EXCURSION = "temperature_excursion"
    DAMAGED_PACKAGING = "damaged_packaging"
    ACCOUNTABILITY_DISCREPANCY = "accountability_discrepancy"
    PENDING_INSPECTION = "pending_inspection"
    RECALL_HOLD = "recall_hold"
    SUSPECTED_COUNTERFEIT = "suspected_counterfeit"


class ExcursionSeverity(str, Enum):
    """Severity of temperature excursion."""

    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CRITICAL = "critical"


class ReconciliationResult(str, Enum):
    """Result of drug accountability reconciliation."""

    RECONCILED = "reconciled"
    MINOR_DISCREPANCY = "minor_discrepancy"
    MAJOR_DISCREPANCY = "major_discrepancy"
    PENDING = "pending"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class SupplyReturn(BaseModel):
    """A clinical supply return record."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique return identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    site_id: str = Field(..., description="Originating site identifier")
    product_name: str = Field(..., description="Name of the investigational product")
    lot_number: str = Field(..., description="Lot/batch number")
    quantity_returned: int = Field(ge=0, description="Quantity returned")
    unit: str = Field(..., description="Unit of measure (vials, tablets, kits, etc.)")
    return_reason: ReturnReason = Field(..., description="Reason for return")
    status: ReturnStatus = Field(default=ReturnStatus.INITIATED, description="Return status")
    initiated_date: datetime = Field(..., description="Date return was initiated")
    initiated_by: str = Field(..., description="Person who initiated the return")
    shipped_date: datetime | None = Field(None, description="Date shipped from site")
    received_date: datetime | None = Field(None, description="Date received at depot/sponsor")
    received_by: str | None = Field(None, description="Person who received the return")
    tracking_number: str | None = Field(None, description="Shipment tracking number")
    condition_on_receipt: str | None = Field(None, description="Condition when received")
    created_at: datetime = Field(..., description="Record creation timestamp")


class DestructionRecord(BaseModel):
    """A record of clinical supply destruction."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique destruction record identifier")
    return_id: str = Field(..., description="Associated return identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    product_name: str = Field(..., description="Product name")
    lot_number: str = Field(..., description="Lot number")
    quantity_destroyed: int = Field(ge=0, description="Quantity destroyed")
    destruction_method: DestructionMethod = Field(..., description="Method of destruction")
    destruction_date: datetime = Field(..., description="Date of destruction")
    destruction_facility: str = Field(..., description="Facility where destruction occurred")
    witnessed_by: str = Field(..., description="Witness name")
    certificate_number: str | None = Field(None, description="Destruction certificate number")
    certificate_date: datetime | None = Field(None, description="Certificate issue date")
    approved_by: str = Field(..., description="Person who approved destruction")


class TemperatureExcursion(BaseModel):
    """A temperature excursion event during storage or transit."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique excursion identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    site_id: str | None = Field(None, description="Site where excursion occurred")
    return_id: str | None = Field(None, description="Associated return if in transit")
    product_name: str = Field(..., description="Affected product name")
    lot_number: str = Field(..., description="Affected lot number")
    excursion_start: datetime = Field(..., description="Start of excursion")
    excursion_end: datetime | None = Field(None, description="End of excursion")
    min_temp: float = Field(..., description="Minimum temperature recorded (Celsius)")
    max_temp: float = Field(..., description="Maximum temperature recorded (Celsius)")
    required_range_min: float = Field(..., description="Required minimum temperature")
    required_range_max: float = Field(..., description="Required maximum temperature")
    duration_minutes: int = Field(ge=0, description="Duration of excursion in minutes")
    severity: ExcursionSeverity = Field(..., description="Severity classification")
    product_disposition: str | None = Field(None, description="Disposition decision for affected product")
    reported_by: str = Field(..., description="Person who reported the excursion")
    assessed_by: str | None = Field(None, description="Person who assessed the impact")


class QuarantineRecord(BaseModel):
    """A quarantine record for clinical supplies."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique quarantine identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    site_id: str | None = Field(None, description="Site identifier")
    product_name: str = Field(..., description="Product name")
    lot_number: str = Field(..., description="Lot number")
    quantity: int = Field(ge=0, description="Quantity quarantined")
    reason: QuarantineReason = Field(..., description="Quarantine reason")
    quarantine_date: datetime = Field(..., description="Date placed in quarantine")
    location: str = Field(..., description="Quarantine storage location")
    released: bool = Field(default=False, description="Whether released from quarantine")
    release_date: datetime | None = Field(None, description="Release date")
    released_by: str | None = Field(None, description="Person who released")
    disposition: str | None = Field(None, description="Final disposition decision")


class DrugAccountability(BaseModel):
    """Drug accountability reconciliation record."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique reconciliation identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    site_id: str = Field(..., description="Site identifier")
    product_name: str = Field(..., description="Product name")
    lot_number: str = Field(..., description="Lot number")
    quantity_received: int = Field(ge=0, description="Quantity received at site")
    quantity_dispensed: int = Field(ge=0, description="Quantity dispensed to patients")
    quantity_returned: int = Field(ge=0, description="Quantity returned by patients")
    quantity_destroyed_at_site: int = Field(ge=0, description="Quantity destroyed at site")
    quantity_returned_to_sponsor: int = Field(ge=0, description="Quantity returned to sponsor")
    quantity_remaining: int = Field(ge=0, description="Quantity remaining on site")
    discrepancy_quantity: int = Field(default=0, description="Unexplained quantity difference")
    result: ReconciliationResult = Field(
        default=ReconciliationResult.PENDING, description="Reconciliation result"
    )
    reconciled_by: str | None = Field(None, description="Person who performed reconciliation")
    reconciled_date: datetime | None = Field(None, description="Date of reconciliation")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class SupplyReturnCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    product_name: str
    lot_number: str
    quantity_returned: int = Field(ge=0)
    unit: str
    return_reason: ReturnReason
    initiated_by: str


class SupplyReturnUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: ReturnStatus | None = None
    tracking_number: str | None = None
    received_by: str | None = None
    condition_on_receipt: str | None = None


class DestructionRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    return_id: str
    trial_id: str
    product_name: str
    lot_number: str
    quantity_destroyed: int = Field(ge=0)
    destruction_method: DestructionMethod
    destruction_facility: str
    witnessed_by: str
    approved_by: str
    certificate_number: str | None = None


class TemperatureExcursionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str | None = None
    return_id: str | None = None
    product_name: str
    lot_number: str
    excursion_start: datetime
    excursion_end: datetime | None = None
    min_temp: float
    max_temp: float
    required_range_min: float
    required_range_max: float
    duration_minutes: int = Field(ge=0)
    severity: ExcursionSeverity
    reported_by: str


class TemperatureExcursionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    excursion_end: datetime | None = None
    severity: ExcursionSeverity | None = None
    product_disposition: str | None = None
    assessed_by: str | None = None


class QuarantineRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str | None = None
    product_name: str
    lot_number: str
    quantity: int = Field(ge=0)
    reason: QuarantineReason
    location: str


class QuarantineRecordUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    released: bool | None = None
    released_by: str | None = None
    disposition: str | None = None


class DrugAccountabilityCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    product_name: str
    lot_number: str
    quantity_received: int = Field(ge=0)
    quantity_dispensed: int = Field(ge=0, default=0)
    quantity_returned: int = Field(ge=0, default=0)
    quantity_destroyed_at_site: int = Field(ge=0, default=0)
    quantity_returned_to_sponsor: int = Field(ge=0, default=0)
    quantity_remaining: int = Field(ge=0, default=0)


class DrugAccountabilityUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    quantity_dispensed: int | None = None
    quantity_returned: int | None = None
    quantity_destroyed_at_site: int | None = None
    quantity_returned_to_sponsor: int | None = None
    quantity_remaining: int | None = None
    result: ReconciliationResult | None = None
    reconciled_by: str | None = None


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class SupplyReturnListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SupplyReturn] = Field(default_factory=list)
    total: int = Field(ge=0)


class DestructionRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DestructionRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


class TemperatureExcursionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[TemperatureExcursion] = Field(default_factory=list)
    total: int = Field(ge=0)


class QuarantineRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[QuarantineRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


class DrugAccountabilityListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DrugAccountability] = Field(default_factory=list)
    total: int = Field(ge=0)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class SupplyReturnsMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_returns: int = Field(ge=0)
    returns_by_status: dict[str, int] = Field(default_factory=dict)
    returns_by_reason: dict[str, int] = Field(default_factory=dict)
    total_units_returned: int = Field(ge=0)
    total_destructions: int = Field(ge=0)
    total_units_destroyed: int = Field(ge=0)
    destructions_by_method: dict[str, int] = Field(default_factory=dict)
    total_excursions: int = Field(ge=0)
    excursions_by_severity: dict[str, int] = Field(default_factory=dict)
    total_quarantined: int = Field(ge=0)
    currently_quarantined: int = Field(ge=0)
    total_accountability_records: int = Field(ge=0)
    reconciled_records: int = Field(ge=0)
    discrepancy_records: int = Field(ge=0)
