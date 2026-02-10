"""Pydantic schemas for IP Accountability (Investigational Product Accountability).

Manages investigational product lifecycle at clinical trial sites: shipment receipt,
inventory management, dispensing to patients, returns, destruction, temperature
excursion tracking, accountability log maintenance, and site-level reconciliation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class IPStatus(str, Enum):
    """Status of an investigational product item through its lifecycle."""

    RECEIVED = "received"
    QUARANTINE = "quarantine"
    RELEASED = "released"
    DISPENSED = "dispensed"
    RETURNED = "returned"
    DESTROYED = "destroyed"
    EXPIRED = "expired"


class StorageCondition(str, Enum):
    """Required storage condition for investigational product."""

    AMBIENT = "ambient"
    REFRIGERATED = "refrigerated"
    FROZEN = "frozen"
    ULTRA_FROZEN = "ultra_frozen"


class TemperatureExcursionSeverity(str, Enum):
    """Severity classification for a temperature excursion event."""

    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CRITICAL = "critical"


class ReconciliationStatus(str, Enum):
    """Status of an IP reconciliation process."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DISCREPANCY_FOUND = "discrepancy_found"
    RESOLVED = "resolved"


class ReturnCondition(str, Enum):
    """Condition of returned investigational product."""

    INTACT = "intact"
    PARTIALLY_USED = "partially_used"
    DAMAGED = "damaged"
    TAMPERED = "tampered"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class IPShipment(BaseModel):
    """A shipment of investigational product to a clinical trial site."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique shipment identifier")
    trial_id: str = Field(..., description="Clinical trial identifier")
    site_id: str = Field(..., description="Destination site identifier")
    lot_number: str = Field(..., description="Manufacturing lot number")
    batch_number: str = Field(..., description="Manufacturing batch number")
    product_name: str = Field(..., description="Investigational product name")
    quantity_shipped: int = Field(..., ge=0, description="Number of units shipped")
    quantity_received: int = Field(default=0, ge=0, description="Number of units received at site")
    storage_condition: StorageCondition = Field(..., description="Required storage condition")
    temperature_range_min: float = Field(..., description="Minimum acceptable storage temperature (Celsius)")
    temperature_range_max: float = Field(..., description="Maximum acceptable storage temperature (Celsius)")
    shipment_date: datetime = Field(..., description="Date the shipment was sent")
    receipt_date: datetime | None = Field(None, description="Date the shipment was received at site")
    status: IPStatus = Field(default=IPStatus.RECEIVED, description="Current shipment status")
    tracking_number: str = Field(..., description="Carrier tracking number")
    carrier: str = Field(..., description="Shipping carrier name")
    created_at: datetime = Field(..., description="Record creation timestamp")


class IPInventoryItem(BaseModel):
    """An individual investigational product unit in site inventory."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique inventory item identifier")
    shipment_id: str = Field(..., description="Associated shipment identifier")
    site_id: str = Field(..., description="Site holding this inventory")
    kit_number: str = Field(..., description="Unique kit/unit number")
    lot_number: str = Field(..., description="Manufacturing lot number")
    product_name: str = Field(..., description="Investigational product name")
    status: IPStatus = Field(default=IPStatus.RECEIVED, description="Current item status")
    storage_condition: StorageCondition = Field(..., description="Required storage condition")
    expiry_date: datetime = Field(..., description="Product expiry date")
    current_quantity: int = Field(..., ge=0, description="Current remaining quantity (e.g., tablets, vials)")
    dispensed_quantity: int = Field(default=0, ge=0, description="Total quantity dispensed from this item")
    patient_id: str | None = Field(None, description="Patient to whom this item was dispensed")
    dispensed_date: datetime | None = Field(None, description="Date this item was dispensed")
    dispensed_by: str | None = Field(None, description="Person who dispensed the item")
    created_at: datetime = Field(..., description="Record creation timestamp")


class TemperatureExcursion(BaseModel):
    """A temperature excursion event for stored investigational product."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique excursion identifier")
    site_id: str = Field(..., description="Site where excursion occurred")
    shipment_id: str | None = Field(None, description="Associated shipment identifier")
    recorded_temperature: float = Field(..., description="Temperature recorded during excursion (Celsius)")
    min_threshold: float = Field(..., description="Minimum acceptable temperature (Celsius)")
    max_threshold: float = Field(..., description="Maximum acceptable temperature (Celsius)")
    duration_minutes: int = Field(..., ge=0, description="Duration of excursion in minutes")
    severity: TemperatureExcursionSeverity = Field(..., description="Severity classification")
    detected_at: datetime = Field(..., description="When the excursion was detected")
    resolved_at: datetime | None = Field(None, description="When the excursion was resolved")
    resolution_notes: str | None = Field(None, description="Notes on how the excursion was resolved")
    impact_assessment: str | None = Field(None, description="Assessment of impact on product integrity")
    affected_kits: list[str] = Field(default_factory=list, description="List of kit numbers affected")
    created_at: datetime = Field(..., description="Record creation timestamp")


class DispensingRecord(BaseModel):
    """Record of dispensing investigational product to a patient."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique dispensing record identifier")
    inventory_item_id: str = Field(..., description="Inventory item dispensed")
    site_id: str = Field(..., description="Site where dispensing occurred")
    patient_id: str = Field(..., description="Patient receiving the product")
    visit_number: str = Field(..., description="Visit number or identifier")
    quantity_dispensed: int = Field(..., ge=1, description="Quantity dispensed")
    dispensed_by: str = Field(..., description="Person who dispensed")
    dispensed_date: datetime = Field(..., description="Date of dispensing")
    witnessed_by: str | None = Field(None, description="Witness to dispensing")
    notes: str | None = Field(None, description="Dispensing notes")
    created_at: datetime = Field(..., description="Record creation timestamp")


class ReturnRecord(BaseModel):
    """Record of investigational product returned by a patient."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique return record identifier")
    inventory_item_id: str = Field(..., description="Inventory item returned")
    site_id: str = Field(..., description="Site where return was processed")
    patient_id: str = Field(..., description="Patient returning the product")
    quantity_returned: int = Field(..., ge=1, description="Quantity returned")
    returned_date: datetime = Field(..., description="Date of return")
    condition: ReturnCondition = Field(..., description="Condition of returned product")
    destruction_required: bool = Field(default=False, description="Whether destruction is required")
    destruction_date: datetime | None = Field(None, description="Date product was destroyed")
    destroyed_by: str | None = Field(None, description="Person who destroyed the product")
    notes: str | None = Field(None, description="Return notes")
    created_at: datetime = Field(..., description="Record creation timestamp")


class AccountabilityLog(BaseModel):
    """Periodic accountability log tracking IP balance at a site."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique log identifier")
    site_id: str = Field(..., description="Site identifier")
    trial_id: str = Field(..., description="Trial identifier")
    log_date: datetime = Field(..., description="Date of this log entry")
    opening_balance: int = Field(..., ge=0, description="Opening inventory balance")
    received: int = Field(default=0, ge=0, description="Units received during period")
    dispensed: int = Field(default=0, ge=0, description="Units dispensed during period")
    returned: int = Field(default=0, ge=0, description="Units returned during period")
    destroyed: int = Field(default=0, ge=0, description="Units destroyed during period")
    adjustments: int = Field(default=0, description="Inventory adjustments (positive or negative)")
    closing_balance: int = Field(..., ge=0, description="Closing inventory balance")
    reconciled_by: str | None = Field(None, description="Person who reconciled the log")
    reconciliation_status: ReconciliationStatus = Field(
        default=ReconciliationStatus.PENDING, description="Reconciliation status"
    )
    discrepancy_notes: str | None = Field(None, description="Notes on any discrepancies found")
    created_at: datetime = Field(..., description="Record creation timestamp")


class IPReconciliation(BaseModel):
    """A formal IP reconciliation event for a site."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique reconciliation identifier")
    site_id: str = Field(..., description="Site identifier")
    trial_id: str = Field(..., description="Trial identifier")
    reconciliation_date: datetime = Field(..., description="Date of reconciliation")
    status: ReconciliationStatus = Field(
        default=ReconciliationStatus.PENDING, description="Reconciliation status"
    )
    expected_quantity: int = Field(..., ge=0, description="Expected quantity based on records")
    actual_quantity: int = Field(..., ge=0, description="Actual quantity counted on site")
    discrepancy: int = Field(default=0, description="Difference between expected and actual")
    investigator_signature: str | None = Field(None, description="Investigator signature/name")
    monitor_signature: str | None = Field(None, description="Monitor signature/name")
    notes: str | None = Field(None, description="Reconciliation notes")
    created_at: datetime = Field(..., description="Record creation timestamp")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class IPShipmentCreate(BaseModel):
    """Request to create a new IP shipment."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    site_id: str = Field(..., description="Destination site identifier")
    lot_number: str = Field(..., description="Manufacturing lot number")
    batch_number: str = Field(..., description="Manufacturing batch number")
    product_name: str = Field(..., description="Product name")
    quantity_shipped: int = Field(..., ge=1, description="Quantity shipped")
    storage_condition: StorageCondition = Field(..., description="Storage condition")
    temperature_range_min: float = Field(..., description="Min storage temperature (Celsius)")
    temperature_range_max: float = Field(..., description="Max storage temperature (Celsius)")
    shipment_date: datetime = Field(..., description="Shipment date")
    tracking_number: str = Field(..., description="Tracking number")
    carrier: str = Field(..., description="Carrier name")


class IPShipmentUpdate(BaseModel):
    """Request to update an IP shipment."""

    model_config = ConfigDict(from_attributes=True)

    quantity_received: int | None = Field(None, ge=0, description="Quantity received")
    receipt_date: datetime | None = Field(None, description="Receipt date")
    status: IPStatus | None = Field(None, description="Shipment status")
    tracking_number: str | None = Field(None, description="Tracking number")


class IPInventoryItemCreate(BaseModel):
    """Request to create an inventory item."""

    model_config = ConfigDict(from_attributes=True)

    shipment_id: str = Field(..., description="Shipment identifier")
    site_id: str = Field(..., description="Site identifier")
    kit_number: str = Field(..., description="Kit number")
    lot_number: str = Field(..., description="Lot number")
    product_name: str = Field(..., description="Product name")
    storage_condition: StorageCondition = Field(..., description="Storage condition")
    expiry_date: datetime = Field(..., description="Expiry date")
    current_quantity: int = Field(..., ge=1, description="Initial quantity")


class IPInventoryItemUpdate(BaseModel):
    """Request to update an inventory item."""

    model_config = ConfigDict(from_attributes=True)

    status: IPStatus | None = Field(None, description="Item status")
    current_quantity: int | None = Field(None, ge=0, description="Current quantity")
    patient_id: str | None = Field(None, description="Patient ID")
    dispensed_date: datetime | None = Field(None, description="Dispensed date")
    dispensed_by: str | None = Field(None, description="Dispensed by")


class DispensingRecordCreate(BaseModel):
    """Request to record a dispensing event."""

    model_config = ConfigDict(from_attributes=True)

    inventory_item_id: str = Field(..., description="Inventory item to dispense")
    site_id: str = Field(..., description="Site identifier")
    patient_id: str = Field(..., description="Patient identifier")
    visit_number: str = Field(..., description="Visit number")
    quantity_dispensed: int = Field(..., ge=1, description="Quantity to dispense")
    dispensed_by: str = Field(..., description="Person dispensing")
    dispensed_date: datetime = Field(..., description="Date of dispensing")
    witnessed_by: str | None = Field(None, description="Witness")
    notes: str | None = Field(None, description="Notes")


class ReturnRecordCreate(BaseModel):
    """Request to record a product return."""

    model_config = ConfigDict(from_attributes=True)

    inventory_item_id: str = Field(..., description="Inventory item returned")
    site_id: str = Field(..., description="Site identifier")
    patient_id: str = Field(..., description="Patient identifier")
    quantity_returned: int = Field(..., ge=1, description="Quantity returned")
    returned_date: datetime = Field(..., description="Date of return")
    condition: ReturnCondition = Field(..., description="Condition of returned product")
    destruction_required: bool = Field(default=False, description="Whether destruction is required")
    notes: str | None = Field(None, description="Notes")


class TemperatureExcursionCreate(BaseModel):
    """Request to log a temperature excursion event."""

    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., description="Site identifier")
    shipment_id: str | None = Field(None, description="Shipment identifier")
    recorded_temperature: float = Field(..., description="Recorded temperature (Celsius)")
    min_threshold: float = Field(..., description="Min threshold (Celsius)")
    max_threshold: float = Field(..., description="Max threshold (Celsius)")
    duration_minutes: int = Field(..., ge=1, description="Duration in minutes")
    severity: TemperatureExcursionSeverity = Field(..., description="Severity")
    detected_at: datetime = Field(..., description="Detection time")
    impact_assessment: str | None = Field(None, description="Impact assessment")
    affected_kits: list[str] = Field(default_factory=list, description="Affected kit numbers")


class TemperatureExcursionResolve(BaseModel):
    """Request to resolve a temperature excursion."""

    model_config = ConfigDict(from_attributes=True)

    resolution_notes: str = Field(..., description="Resolution notes")
    impact_assessment: str | None = Field(None, description="Updated impact assessment")


class AccountabilityLogCreate(BaseModel):
    """Request to create an accountability log entry."""

    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., description="Site identifier")
    trial_id: str = Field(..., description="Trial identifier")
    log_date: datetime = Field(..., description="Log date")
    opening_balance: int = Field(..., ge=0, description="Opening balance")
    received: int = Field(default=0, ge=0, description="Received")
    dispensed: int = Field(default=0, ge=0, description="Dispensed")
    returned: int = Field(default=0, ge=0, description="Returned")
    destroyed: int = Field(default=0, ge=0, description="Destroyed")
    adjustments: int = Field(default=0, description="Adjustments")
    closing_balance: int = Field(..., ge=0, description="Closing balance")
    reconciled_by: str | None = Field(None, description="Reconciled by")


class IPReconciliationCreate(BaseModel):
    """Request to perform an IP reconciliation."""

    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., description="Site identifier")
    trial_id: str = Field(..., description="Trial identifier")
    reconciliation_date: datetime = Field(..., description="Reconciliation date")
    expected_quantity: int = Field(..., ge=0, description="Expected quantity")
    actual_quantity: int = Field(..., ge=0, description="Actual quantity")
    investigator_signature: str | None = Field(None, description="Investigator signature")
    monitor_signature: str | None = Field(None, description="Monitor signature")
    notes: str | None = Field(None, description="Notes")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class IPShipmentListResponse(BaseModel):
    """List of IP shipments."""

    model_config = ConfigDict(from_attributes=True)

    items: list[IPShipment] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class IPInventoryItemListResponse(BaseModel):
    """List of IP inventory items."""

    model_config = ConfigDict(from_attributes=True)

    items: list[IPInventoryItem] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class TemperatureExcursionListResponse(BaseModel):
    """List of temperature excursion events."""

    model_config = ConfigDict(from_attributes=True)

    items: list[TemperatureExcursion] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class DispensingRecordListResponse(BaseModel):
    """List of dispensing records."""

    model_config = ConfigDict(from_attributes=True)

    items: list[DispensingRecord] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class ReturnRecordListResponse(BaseModel):
    """List of return records."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ReturnRecord] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class AccountabilityLogListResponse(BaseModel):
    """List of accountability log entries."""

    model_config = ConfigDict(from_attributes=True)

    items: list[AccountabilityLog] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class IPReconciliationListResponse(BaseModel):
    """List of IP reconciliation records."""

    model_config = ConfigDict(from_attributes=True)

    items: list[IPReconciliation] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Metrics / dashboard
# ---------------------------------------------------------------------------


class IPMetrics(BaseModel):
    """Aggregated IP accountability operational metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_shipments: int = Field(ge=0, description="Total shipments received")
    total_kits: int = Field(ge=0, description="Total inventory kits tracked")
    kits_dispensed: int = Field(ge=0, description="Kits dispensed to patients")
    kits_returned: int = Field(ge=0, description="Kits returned by patients")
    kits_destroyed: int = Field(ge=0, description="Kits destroyed")
    temperature_excursions: int = Field(ge=0, description="Total temperature excursion events")
    sites_with_discrepancies: int = Field(
        ge=0, description="Number of sites with unresolved inventory discrepancies"
    )
    reconciliation_completion_pct: float = Field(
        ge=0.0, le=100.0, description="Percentage of reconciliations completed"
    )
