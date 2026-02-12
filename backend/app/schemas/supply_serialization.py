"""Pydantic schemas for Supply Chain Serialization & Track-and-Trace (CLINICAL-11).

Manages product serialization, unit-level tracking, cold chain monitoring,
distribution verification, DSCSA/FMD compliance, and counterfeit detection
for clinical supply.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SerializationLevel(str, Enum):
    """Hierarchy level for a serialized packaging unit."""

    UNIT = "unit"
    BUNDLE = "bundle"
    CASE = "case"
    PALLET = "pallet"


class TrackingEventType(str, Enum):
    """Type of supply chain tracking event."""

    MANUFACTURED = "manufactured"
    PACKAGED = "packaged"
    SHIPPED = "shipped"
    RECEIVED = "received"
    DISPENSED = "dispensed"
    RETURNED = "returned"
    DESTROYED = "destroyed"
    RECALLED = "recalled"


class ComplianceStandard(str, Enum):
    """Regulatory compliance standard for serialization."""

    DSCSA = "dscsa"
    EU_FMD = "eu_fmd"
    CHINA_NMPA = "china_nmpa"
    BRAZIL_SNCM = "brazil_sncm"
    INDIA_DCTS = "india_dcts"


class ColdChainStatus(str, Enum):
    """Cold chain reading status classification."""

    WITHIN_RANGE = "within_range"
    EXCURSION_MINOR = "excursion_minor"
    EXCURSION_MAJOR = "excursion_major"
    BREACH = "breach"


class VerificationStatus(str, Enum):
    """Result of a product verification inquiry."""

    VERIFIED = "verified"
    SUSPECT = "suspect"
    CONFIRMED_COUNTERFEIT = "confirmed_counterfeit"
    QUARANTINED = "quarantined"


class UnitStatus(str, Enum):
    """Lifecycle status of a serialized unit."""

    ACTIVE = "active"
    IN_TRANSIT = "in_transit"
    DISPENSED = "dispensed"
    RETURNED = "returned"
    DESTROYED = "destroyed"
    RECALLED = "recalled"
    QUARANTINED = "quarantined"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class SerializedUnit(BaseModel):
    """A uniquely serialized packaging unit with GTIN and serial number."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique serialized unit identifier")
    product_name: str = Field(..., description="Product trade or generic name")
    gtin: str = Field(..., description="Global Trade Item Number (14-digit)")
    serial_number: str = Field(..., description="Unique serial number for this unit")
    lot_number: str = Field(..., description="Manufacturing lot/batch number")
    expiry_date: datetime = Field(..., description="Product expiration date")
    serialization_level: SerializationLevel = Field(
        ..., description="Packaging hierarchy level"
    )
    parent_id: str | None = Field(
        None, description="Parent unit ID for aggregation hierarchy"
    )
    manufacturing_site: str = Field(..., description="Site where the unit was manufactured")
    manufacturing_date: datetime = Field(..., description="Date of manufacture")
    status: UnitStatus = Field(
        default=UnitStatus.ACTIVE, description="Current lifecycle status"
    )
    current_location: str = Field(..., description="Current facility or location")
    last_scan_date: datetime | None = Field(
        None, description="Timestamp of the most recent scan event"
    )


class TrackingEvent(BaseModel):
    """A single tracking event for a serialized unit in the supply chain."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique tracking event identifier")
    unit_id: str = Field(..., description="Reference to the serialized unit")
    event_type: TrackingEventType = Field(..., description="Type of tracking event")
    timestamp: datetime = Field(..., description="When the event occurred")
    location: str = Field(..., description="Facility or location identifier")
    facility_name: str = Field(..., description="Human-readable facility name")
    scanned_by: str = Field(..., description="Operator or system that recorded the event")
    gps_latitude: float | None = Field(None, description="GPS latitude of event location")
    gps_longitude: float | None = Field(None, description="GPS longitude of event location")
    temperature: float | None = Field(None, description="Temperature at event time (Celsius)")
    humidity: float | None = Field(None, description="Relative humidity at event time (%)")
    notes: str | None = Field(None, description="Free-text notes about the event")
    transaction_id: str | None = Field(
        None, description="Transaction identifier for DSCSA/FMD linking"
    )


class ColdChainReading(BaseModel):
    """A single cold chain sensor reading during shipment or storage."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique reading identifier")
    shipment_id: str = Field(..., description="Reference to the distribution shipment")
    sensor_id: str = Field(..., description="IoT sensor device identifier")
    timestamp: datetime = Field(..., description="When the reading was captured")
    temperature: float = Field(..., description="Temperature in Celsius")
    humidity: float | None = Field(None, description="Relative humidity (%)")
    location: str = Field(..., description="Location at time of reading")
    status: ColdChainStatus = Field(..., description="Classification of the reading")
    alert_triggered: bool = Field(
        default=False, description="Whether this reading triggered an alert"
    )
    alert_acknowledged_by: str | None = Field(
        None, description="Person who acknowledged the alert"
    )
    alert_acknowledged_date: datetime | None = Field(
        None, description="When the alert was acknowledged"
    )


class ComplianceRecord(BaseModel):
    """A regulatory compliance verification record for a serialized unit."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique compliance record identifier")
    unit_id: str = Field(..., description="Reference to the serialized unit")
    standard: ComplianceStandard = Field(..., description="Regulatory standard applied")
    country: str = Field(..., description="Country code (ISO 3166-1 alpha-2)")
    compliant: bool = Field(..., description="Whether the unit is compliant")
    verification_date: datetime = Field(..., description="Date compliance was verified")
    verified_by: str = Field(..., description="Person or system that verified compliance")
    transaction_information: str | None = Field(
        None, description="DSCSA Transaction Information (TI)"
    )
    transaction_history: str | None = Field(
        None, description="DSCSA Transaction History (TH)"
    )
    transaction_statement: str | None = Field(
        None, description="DSCSA Transaction Statement (TS)"
    )
    certificate_reference: str | None = Field(
        None, description="Reference to compliance certificate or document"
    )


class VerificationRequest(BaseModel):
    """A product verification request and its resolution (DSCSA VRS / EU FMD)."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique verification request identifier")
    requestor: str = Field(..., description="Entity that initiated the verification")
    request_date: datetime = Field(..., description="When the request was submitted")
    gtin: str = Field(..., description="GTIN of the product being verified")
    serial_number: str = Field(..., description="Serial number being verified")
    lot_number: str = Field(..., description="Lot number being verified")
    verification_status: VerificationStatus = Field(
        ..., description="Outcome of the verification"
    )
    response_date: datetime | None = Field(
        None, description="When the verification response was returned"
    )
    responder: str | None = Field(
        None, description="Entity that responded to the verification request"
    )
    investigation_notes: str | None = Field(
        None, description="Notes from investigation if suspect or counterfeit"
    )
    resolution: str | None = Field(
        None, description="Final resolution description"
    )


class DistributionRecord(BaseModel):
    """A distribution/shipment record tracking unit movement between facilities."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique distribution record identifier")
    shipment_id: str = Field(..., description="Shipment tracking identifier")
    from_facility: str = Field(..., description="Origin facility identifier")
    to_facility: str = Field(..., description="Destination facility identifier")
    shipped_date: datetime = Field(..., description="Date units were shipped")
    received_date: datetime | None = Field(
        None, description="Date units were received at destination"
    )
    units_shipped: int = Field(ge=1, description="Number of units in the shipment")
    units_received: int | None = Field(
        None, ge=0, description="Number of units received (may differ from shipped)"
    )
    discrepancy: bool = Field(
        default=False,
        description="Whether there is a discrepancy between shipped and received counts",
    )
    carrier: str = Field(..., description="Logistics carrier name")
    tracking_number: str = Field(..., description="Carrier tracking number")
    chain_of_custody_verified: bool = Field(
        default=False, description="Whether chain of custody was fully verified"
    )


class SerializationMetrics(BaseModel):
    """Aggregated metrics for the serialization and track-and-trace dashboard."""

    model_config = ConfigDict(from_attributes=True)

    total_serialized_units: int = Field(ge=0, description="Total serialized units tracked")
    units_by_level: dict[str, int] = Field(
        default_factory=dict, description="Unit count by serialization level"
    )
    units_by_status: dict[str, int] = Field(
        default_factory=dict, description="Unit count by lifecycle status"
    )
    total_tracking_events: int = Field(ge=0, description="Total tracking events recorded")
    total_cold_chain_readings: int = Field(ge=0, description="Total cold chain readings")
    cold_chain_alerts: int = Field(
        ge=0, description="Number of cold chain readings that triggered alerts"
    )
    total_compliance_records: int = Field(ge=0, description="Total compliance records")
    compliance_rate: float = Field(
        ge=0.0, le=100.0, description="Overall compliance rate (%)"
    )
    total_verification_requests: int = Field(
        ge=0, description="Total verification requests"
    )
    suspect_or_counterfeit: int = Field(
        ge=0, description="Number of suspect or confirmed counterfeit findings"
    )
    total_distribution_records: int = Field(
        ge=0, description="Total distribution records"
    )
    distribution_discrepancies: int = Field(
        ge=0, description="Number of distributions with discrepancies"
    )
    units_dispensed: int = Field(ge=0, description="Total units dispensed to patients")
    units_recalled: int = Field(ge=0, description="Total units recalled")


# ---------------------------------------------------------------------------
# Create / Update models
# ---------------------------------------------------------------------------


class SerializedUnitCreate(BaseModel):
    """Request payload for registering a new serialized unit."""

    model_config = ConfigDict(from_attributes=True)

    product_name: str = Field(..., description="Product name")
    gtin: str = Field(..., description="GTIN (14-digit)")
    serial_number: str = Field(..., description="Unique serial number")
    lot_number: str = Field(..., description="Lot/batch number")
    expiry_date: datetime = Field(..., description="Expiration date")
    serialization_level: SerializationLevel = Field(
        ..., description="Packaging level"
    )
    parent_id: str | None = Field(None, description="Parent unit ID")
    manufacturing_site: str = Field(..., description="Manufacturing site")
    manufacturing_date: datetime = Field(..., description="Manufacturing date")
    current_location: str = Field(..., description="Initial location")


class SerializedUnitUpdate(BaseModel):
    """Request payload for updating a serialized unit."""

    model_config = ConfigDict(from_attributes=True)

    status: UnitStatus | None = Field(None, description="Updated lifecycle status")
    current_location: str | None = Field(None, description="Updated location")
    parent_id: str | None = Field(None, description="Updated parent unit ID")


class TrackingEventCreate(BaseModel):
    """Request payload for recording a tracking event."""

    model_config = ConfigDict(from_attributes=True)

    unit_id: str = Field(..., description="Serialized unit ID")
    event_type: TrackingEventType = Field(..., description="Event type")
    location: str = Field(..., description="Location identifier")
    facility_name: str = Field(..., description="Facility name")
    scanned_by: str = Field(..., description="Operator or system ID")
    gps_latitude: float | None = Field(None, description="GPS latitude")
    gps_longitude: float | None = Field(None, description="GPS longitude")
    temperature: float | None = Field(None, description="Temperature (Celsius)")
    humidity: float | None = Field(None, description="Humidity (%)")
    notes: str | None = Field(None, description="Event notes")
    transaction_id: str | None = Field(None, description="Transaction ID")


class ColdChainReadingCreate(BaseModel):
    """Request payload for logging a cold chain reading."""

    model_config = ConfigDict(from_attributes=True)

    shipment_id: str = Field(..., description="Distribution shipment ID")
    sensor_id: str = Field(..., description="Sensor device ID")
    temperature: float = Field(..., description="Temperature (Celsius)")
    humidity: float | None = Field(None, description="Humidity (%)")
    location: str = Field(..., description="Location at time of reading")


class ColdChainAcknowledge(BaseModel):
    """Request payload for acknowledging a cold chain alert."""

    model_config = ConfigDict(from_attributes=True)

    acknowledged_by: str = Field(..., description="Person acknowledging the alert")


class ComplianceRecordCreate(BaseModel):
    """Request payload for creating a compliance record."""

    model_config = ConfigDict(from_attributes=True)

    unit_id: str = Field(..., description="Serialized unit ID")
    standard: ComplianceStandard = Field(..., description="Regulatory standard")
    country: str = Field(..., description="Country code")
    verified_by: str = Field(..., description="Verifier")
    transaction_information: str | None = Field(None, description="TI data")
    transaction_history: str | None = Field(None, description="TH data")
    transaction_statement: str | None = Field(None, description="TS data")
    certificate_reference: str | None = Field(None, description="Certificate reference")


class VerificationRequestCreate(BaseModel):
    """Request payload for submitting a verification request."""

    model_config = ConfigDict(from_attributes=True)

    requestor: str = Field(..., description="Requesting entity")
    gtin: str = Field(..., description="GTIN to verify")
    serial_number: str = Field(..., description="Serial number to verify")
    lot_number: str = Field(..., description="Lot number to verify")


class VerificationRequestUpdate(BaseModel):
    """Request payload for updating a verification request resolution."""

    model_config = ConfigDict(from_attributes=True)

    verification_status: VerificationStatus | None = Field(
        None, description="Updated status"
    )
    responder: str | None = Field(None, description="Responding entity")
    investigation_notes: str | None = Field(None, description="Investigation notes")
    resolution: str | None = Field(None, description="Resolution description")


class DistributionRecordCreate(BaseModel):
    """Request payload for creating a distribution record."""

    model_config = ConfigDict(from_attributes=True)

    from_facility: str = Field(..., description="Origin facility")
    to_facility: str = Field(..., description="Destination facility")
    units_shipped: int = Field(ge=1, description="Number of units shipped")
    carrier: str = Field(..., description="Carrier name")
    tracking_number: str = Field(..., description="Tracking number")


class DistributionRecordUpdate(BaseModel):
    """Request payload for updating a distribution record (e.g., on receipt)."""

    model_config = ConfigDict(from_attributes=True)

    received_date: datetime | None = Field(None, description="Date received")
    units_received: int | None = Field(None, ge=0, description="Units received")
    chain_of_custody_verified: bool | None = Field(
        None, description="Chain of custody verified"
    )


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class SerializedUnitListResponse(BaseModel):
    """Paginated list of serialized units."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SerializedUnit] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class TrackingEventListResponse(BaseModel):
    """List of tracking events."""

    model_config = ConfigDict(from_attributes=True)

    items: list[TrackingEvent] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total events")


class ColdChainReadingListResponse(BaseModel):
    """List of cold chain readings."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ColdChainReading] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total readings")


class ComplianceRecordListResponse(BaseModel):
    """List of compliance records."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ComplianceRecord] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total compliance records")


class VerificationRequestListResponse(BaseModel):
    """List of verification requests."""

    model_config = ConfigDict(from_attributes=True)

    items: list[VerificationRequest] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total verification requests")


class DistributionRecordListResponse(BaseModel):
    """List of distribution records."""

    model_config = ConfigDict(from_attributes=True)

    items: list[DistributionRecord] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total distribution records")


class UnitTraceResponse(BaseModel):
    """Full history trace of a serialized unit across the supply chain."""

    model_config = ConfigDict(from_attributes=True)

    unit: SerializedUnit = Field(..., description="The serialized unit")
    events: list[TrackingEvent] = Field(
        default_factory=list, description="All tracking events for this unit"
    )
    cold_chain_readings: list[ColdChainReading] = Field(
        default_factory=list, description="Cold chain readings for related shipments"
    )
    compliance_records: list[ComplianceRecord] = Field(
        default_factory=list, description="Compliance records for this unit"
    )
    verification_requests: list[VerificationRequest] = Field(
        default_factory=list, description="Verification requests for this unit"
    )
    children: list[SerializedUnit] = Field(
        default_factory=list, description="Child units in aggregation hierarchy"
    )
