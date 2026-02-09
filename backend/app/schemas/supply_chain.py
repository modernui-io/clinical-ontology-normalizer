"""Pydantic schemas for Investigational Medicinal Product (IMP) Supply Chain Management (CLINICAL-6).

Tracks drug product inventory, shipments, temperature monitoring, kit
assignments, and supply forecasting across clinical trial sites.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SupplyStatus(str, Enum):
    """Status of an inventory item."""

    IN_STOCK = "in_stock"
    LOW_STOCK = "low_stock"
    OUT_OF_STOCK = "out_of_stock"
    EXPIRED = "expired"
    QUARANTINED = "quarantined"
    RECALLED = "recalled"


class ShipmentStatus(str, Enum):
    """Status of a shipment."""

    PENDING = "pending"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    RETURNED = "returned"
    LOST = "lost"


class StorageCondition(str, Enum):
    """Required storage condition for a drug product."""

    AMBIENT = "ambient"
    REFRIGERATED_2_8 = "refrigerated_2_8"
    FROZEN_MINUS20 = "frozen_minus20"
    FROZEN_MINUS80 = "frozen_minus80"
    CRYOGENIC = "cryogenic"


class KitType(str, Enum):
    """Type of clinical trial kit."""

    SCREENING = "screening"
    RANDOMIZATION = "randomization"
    TREATMENT = "treatment"
    RESCUE = "rescue"
    EXTENSION = "extension"


class TemperatureExcursionSeverity(str, Enum):
    """Severity classification of a temperature excursion."""

    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


class ExcursionDisposition(str, Enum):
    """Disposition decision for a temperature excursion."""

    USE = "use"
    QUARANTINE = "quarantine"
    DESTROY = "destroy"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class DrugProduct(BaseModel):
    """An investigational medicinal product (IMP) or comparator drug."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique drug product identifier")
    name: str = Field(..., description="Product trade name")
    ndc_code: str | None = Field(None, description="National Drug Code")
    manufacturer: str = Field(..., description="Manufacturer name")
    active_ingredient: str = Field(..., description="Active pharmaceutical ingredient")
    formulation: str = Field(..., description="Dosage form (e.g., injection, tablet)")
    strength: str = Field(..., description="Strength (e.g., 8mg/0.07mL)")
    storage_condition: StorageCondition = Field(
        ..., description="Required storage condition"
    )
    shelf_life_months: int = Field(ge=1, description="Shelf life in months")
    retest_date: datetime | None = Field(None, description="Next retest date for stability")


class InventoryItem(BaseModel):
    """A single inventory item at a clinical trial site."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique inventory item identifier")
    drug_product_id: str = Field(..., description="Reference to drug product")
    lot_number: str = Field(..., description="Manufacturing lot number")
    quantity: int = Field(ge=0, description="Current quantity on hand")
    site_id: str = Field(..., description="Site where the item is stored")
    storage_condition: StorageCondition = Field(
        ..., description="Actual storage condition"
    )
    expiry_date: datetime = Field(..., description="Expiration date")
    status: SupplyStatus = Field(
        default=SupplyStatus.IN_STOCK, description="Current inventory status"
    )
    received_date: datetime = Field(..., description="Date the item was received at site")


class TemperatureReading(BaseModel):
    """A single temperature sensor reading."""

    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime = Field(..., description="Time the reading was taken")
    temperature_celsius: float = Field(..., description="Temperature in Celsius")
    location: str = Field(..., description="Location description")
    sensor_id: str = Field(..., description="Sensor device identifier")


class Shipment(BaseModel):
    """A shipment of drug product between sites or from depot to site."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique shipment identifier")
    from_site: str = Field(..., description="Origin site or depot")
    to_site: str = Field(..., description="Destination site")
    drug_product_id: str = Field(..., description="Drug product being shipped")
    lot_number: str = Field(..., description="Lot number of shipped product")
    quantity: int = Field(ge=1, description="Quantity shipped")
    status: ShipmentStatus = Field(
        default=ShipmentStatus.PENDING, description="Shipment status"
    )
    shipped_date: datetime | None = Field(None, description="Date shipped")
    delivered_date: datetime | None = Field(None, description="Date delivered")
    tracking_number: str | None = Field(None, description="Carrier tracking number")
    temperature_log: list[TemperatureReading] = Field(
        default_factory=list, description="Temperature readings during transit"
    )


class TemperatureExcursion(BaseModel):
    """A temperature excursion event for a shipment or inventory item."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique excursion identifier")
    shipment_id: str | None = Field(None, description="Related shipment ID")
    inventory_id: str | None = Field(None, description="Related inventory item ID")
    start_time: datetime = Field(..., description="Start of excursion")
    end_time: datetime = Field(..., description="End of excursion")
    min_temp: float = Field(..., description="Minimum temperature during excursion (C)")
    max_temp: float = Field(..., description="Maximum temperature during excursion (C)")
    severity: TemperatureExcursionSeverity = Field(
        ..., description="Severity classification"
    )
    disposition: ExcursionDisposition = Field(
        ..., description="Disposition decision"
    )


class KitAssignment(BaseModel):
    """Assignment of a clinical trial kit to a patient."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique assignment identifier")
    kit_type: KitType = Field(..., description="Type of kit")
    patient_id: str = Field(..., description="Patient who received the kit")
    site_id: str = Field(..., description="Site where the kit was assigned")
    kit_number: str = Field(..., description="Kit identification number")
    assigned_date: datetime = Field(..., description="Date the kit was assigned")
    returned_date: datetime | None = Field(None, description="Date the kit was returned")


class SupplyForecast(BaseModel):
    """Supply forecast for a drug product at a site."""

    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., description="Clinical trial site")
    drug_product_id: str = Field(..., description="Drug product")
    current_stock: int = Field(ge=0, description="Current inventory quantity")
    monthly_consumption_rate: float = Field(
        ge=0.0, description="Average monthly consumption over last 6 months"
    )
    months_of_supply: float | None = Field(
        None, description="Estimated months of supply remaining"
    )
    reorder_point: int = Field(ge=0, description="Quantity triggering reorder alert")
    reorder_quantity: int = Field(ge=0, description="Recommended reorder quantity")


class SupplyMetrics(BaseModel):
    """Aggregated supply chain metrics for the dashboard."""

    model_config = ConfigDict(from_attributes=True)

    total_drug_products: int = Field(ge=0, description="Total drug products tracked")
    total_sites: int = Field(ge=0, description="Total sites with inventory")
    total_inventory_items: int = Field(ge=0, description="Total inventory line items")
    active_shipments: int = Field(ge=0, description="Shipments in transit")
    temperature_excursions_30d: int = Field(
        ge=0, description="Temperature excursions in last 30 days"
    )
    kits_assigned: int = Field(ge=0, description="Total kits currently assigned")
    avg_months_of_supply: float | None = Field(
        None, description="Average months of supply across all sites"
    )
    sites_below_reorder_point: int = Field(
        ge=0, description="Number of sites below reorder threshold"
    )


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class DrugProductCreate(BaseModel):
    """Request payload for creating a new drug product."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Product trade name")
    ndc_code: str | None = Field(None, description="National Drug Code")
    manufacturer: str = Field(..., description="Manufacturer name")
    active_ingredient: str = Field(..., description="Active pharmaceutical ingredient")
    formulation: str = Field(..., description="Dosage form")
    strength: str = Field(..., description="Strength")
    storage_condition: StorageCondition = Field(
        ..., description="Required storage condition"
    )
    shelf_life_months: int = Field(ge=1, description="Shelf life in months")


class DrugProductUpdate(BaseModel):
    """Request payload for updating a drug product."""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = Field(None, description="Updated product name")
    ndc_code: str | None = Field(None, description="Updated NDC code")
    storage_condition: StorageCondition | None = Field(
        None, description="Updated storage condition"
    )
    shelf_life_months: int | None = Field(None, ge=1, description="Updated shelf life")
    retest_date: datetime | None = Field(None, description="Updated retest date")


class InventoryItemCreate(BaseModel):
    """Request payload for adding inventory."""

    model_config = ConfigDict(from_attributes=True)

    drug_product_id: str = Field(..., description="Drug product ID")
    lot_number: str = Field(..., description="Lot number")
    quantity: int = Field(ge=1, description="Quantity received")
    site_id: str = Field(..., description="Receiving site")
    storage_condition: StorageCondition = Field(
        ..., description="Storage condition"
    )
    expiry_date: datetime = Field(..., description="Expiration date")


class InventoryItemUpdate(BaseModel):
    """Request payload for updating inventory."""

    model_config = ConfigDict(from_attributes=True)

    quantity: int | None = Field(None, ge=0, description="Updated quantity")
    status: SupplyStatus | None = Field(None, description="Updated status")
    storage_condition: StorageCondition | None = Field(
        None, description="Updated storage condition"
    )


class ShipmentCreate(BaseModel):
    """Request payload for creating a shipment."""

    model_config = ConfigDict(from_attributes=True)

    from_site: str = Field(..., description="Origin site or depot")
    to_site: str = Field(..., description="Destination site")
    drug_product_id: str = Field(..., description="Drug product being shipped")
    lot_number: str = Field(..., description="Lot number")
    quantity: int = Field(ge=1, description="Quantity shipped")
    tracking_number: str | None = Field(None, description="Carrier tracking number")


class ShipmentUpdate(BaseModel):
    """Request payload for updating a shipment."""

    model_config = ConfigDict(from_attributes=True)

    status: ShipmentStatus | None = Field(None, description="Updated status")
    tracking_number: str | None = Field(None, description="Updated tracking number")


class TemperatureExcursionReport(BaseModel):
    """Request payload for reporting a temperature excursion."""

    model_config = ConfigDict(from_attributes=True)

    start_time: datetime = Field(..., description="Start of excursion")
    end_time: datetime = Field(..., description="End of excursion")
    min_temp: float = Field(..., description="Minimum temperature (C)")
    max_temp: float = Field(..., description="Maximum temperature (C)")
    severity: TemperatureExcursionSeverity = Field(
        ..., description="Severity classification"
    )
    disposition: ExcursionDisposition = Field(
        ..., description="Disposition decision"
    )


class KitAssignRequest(BaseModel):
    """Request payload for assigning a kit to a patient."""

    model_config = ConfigDict(from_attributes=True)

    kit_type: KitType = Field(..., description="Type of kit")
    patient_id: str = Field(..., description="Patient receiving the kit")
    site_id: str = Field(..., description="Site assigning the kit")
    kit_number: str = Field(..., description="Kit identification number")


class DrugProductListResponse(BaseModel):
    """Paginated list of drug products."""

    model_config = ConfigDict(from_attributes=True)

    items: list[DrugProduct] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class InventoryListResponse(BaseModel):
    """Paginated list of inventory items."""

    model_config = ConfigDict(from_attributes=True)

    items: list[InventoryItem] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")
    limit: int = Field(ge=1, description="Page size")
    offset: int = Field(ge=0, description="Page offset")


class ShipmentListResponse(BaseModel):
    """Paginated list of shipments."""

    model_config = ConfigDict(from_attributes=True)

    items: list[Shipment] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")
    limit: int = Field(ge=1, description="Page size")
    offset: int = Field(ge=0, description="Page offset")


class TemperatureExcursionListResponse(BaseModel):
    """List of temperature excursions."""

    model_config = ConfigDict(from_attributes=True)

    items: list[TemperatureExcursion] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total excursions")


class KitAssignmentListResponse(BaseModel):
    """List of kit assignments."""

    model_config = ConfigDict(from_attributes=True)

    items: list[KitAssignment] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total assignments")


class KitReconciliation(BaseModel):
    """Kit reconciliation summary."""

    model_config = ConfigDict(from_attributes=True)

    total_assigned: int = Field(ge=0, description="Total kits assigned")
    total_returned: int = Field(ge=0, description="Total kits returned")
    outstanding: int = Field(ge=0, description="Kits not yet returned")
    by_kit_type: dict[str, dict[str, int]] = Field(
        default_factory=dict,
        description="Breakdown by kit type: {type: {assigned, returned, outstanding}}",
    )
    by_site: dict[str, dict[str, int]] = Field(
        default_factory=dict,
        description="Breakdown by site: {site: {assigned, returned, outstanding}}",
    )


class LotTrace(BaseModel):
    """Lot traceability record."""

    model_config = ConfigDict(from_attributes=True)

    lot_number: str = Field(..., description="Lot number traced")
    drug_product_id: str = Field(..., description="Drug product")
    drug_product_name: str = Field(..., description="Drug product name")
    inventory_items: list[InventoryItem] = Field(
        default_factory=list, description="Inventory items with this lot"
    )
    shipments: list[Shipment] = Field(
        default_factory=list, description="Shipments with this lot"
    )
    patients_exposed: list[str] = Field(
        default_factory=list, description="Patient IDs who received this lot"
    )
    excursions: list[TemperatureExcursion] = Field(
        default_factory=list, description="Temperature excursions for this lot"
    )


class SupplyForecastResponse(BaseModel):
    """Supply forecast response."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SupplyForecast] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total forecast records")
    sites_below_reorder: list[str] = Field(
        default_factory=list, description="Site IDs below reorder point"
    )


class ExpiringItemsResponse(BaseModel):
    """Response listing items expiring within a time window."""

    model_config = ConfigDict(from_attributes=True)

    items: list[InventoryItem] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total expiring items")
    days_window: int = Field(ge=1, description="Days until expiry threshold")
