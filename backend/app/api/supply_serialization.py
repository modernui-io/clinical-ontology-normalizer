"""Supply Chain Serialization & Track-and-Trace API endpoints (CLINICAL-11).

Provides comprehensive serialization operations: unit registration &
management, tracking event recording, cold chain monitoring, DSCSA/FMD
compliance verification, counterfeit detection via verification requests,
distribution tracking, full unit history tracing, and operational metrics.

Endpoints:
    GET    /supply-serialization/units                              - List serialized units
    GET    /supply-serialization/units/{unit_id}                    - Get single unit
    POST   /supply-serialization/units                              - Register new serial
    PUT    /supply-serialization/units/{unit_id}                    - Update unit
    DELETE /supply-serialization/units/{unit_id}                    - Delete unit
    GET    /supply-serialization/units/{unit_id}/children           - Get child units
    GET    /supply-serialization/units/{unit_id}/trace              - Full unit history trace
    GET    /supply-serialization/tracking-events                    - List tracking events
    GET    /supply-serialization/tracking-events/{event_id}         - Get single event
    POST   /supply-serialization/tracking-events                    - Record tracking event
    DELETE /supply-serialization/tracking-events/{event_id}         - Delete tracking event
    GET    /supply-serialization/cold-chain                         - List cold chain readings
    GET    /supply-serialization/cold-chain/{reading_id}            - Get single reading
    POST   /supply-serialization/cold-chain                         - Log cold chain reading
    POST   /supply-serialization/cold-chain/{reading_id}/acknowledge - Acknowledge alert
    DELETE /supply-serialization/cold-chain/{reading_id}            - Delete reading
    GET    /supply-serialization/compliance                         - List compliance records
    GET    /supply-serialization/compliance/{record_id}             - Get single record
    POST   /supply-serialization/compliance                         - Check compliance
    DELETE /supply-serialization/compliance/{record_id}             - Delete compliance record
    GET    /supply-serialization/verifications                      - List verification requests
    GET    /supply-serialization/verifications/{request_id}         - Get single request
    POST   /supply-serialization/verifications                      - Verify unit
    PUT    /supply-serialization/verifications/{request_id}         - Update verification
    DELETE /supply-serialization/verifications/{request_id}         - Delete verification
    GET    /supply-serialization/distributions                      - List distribution records
    GET    /supply-serialization/distributions/{record_id}          - Get single record
    POST   /supply-serialization/distributions                      - Create distribution
    PUT    /supply-serialization/distributions/{record_id}          - Update distribution
    DELETE /supply-serialization/distributions/{record_id}          - Delete distribution
    GET    /supply-serialization/metrics                            - Serialization metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.supply_serialization import (
    ColdChainAcknowledge,
    ColdChainReading,
    ColdChainReadingCreate,
    ColdChainReadingListResponse,
    ColdChainStatus,
    ComplianceRecord,
    ComplianceRecordCreate,
    ComplianceRecordListResponse,
    ComplianceStandard,
    DistributionRecord,
    DistributionRecordCreate,
    DistributionRecordListResponse,
    DistributionRecordUpdate,
    SerializationLevel,
    SerializationMetrics,
    SerializedUnit,
    SerializedUnitCreate,
    SerializedUnitListResponse,
    SerializedUnitUpdate,
    TrackingEvent,
    TrackingEventCreate,
    TrackingEventListResponse,
    TrackingEventType,
    UnitStatus,
    UnitTraceResponse,
    VerificationRequest,
    VerificationRequestCreate,
    VerificationRequestListResponse,
    VerificationRequestUpdate,
    VerificationStatus,
)
from app.services.supply_serialization_service import get_supply_serialization_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/supply-serialization",
    tags=["Supply Serialization"],
)


# ---------------------------------------------------------------------------
# Serialized Units
# ---------------------------------------------------------------------------


@router.get(
    "/units",
    response_model=SerializedUnitListResponse,
    summary="List Serialized Units",
    description="Retrieve serialized units with optional filtering by level, status, lot, or GTIN.",
)
async def list_units(
    serialization_level: Optional[SerializationLevel] = Query(
        None, description="Filter by serialization level"
    ),
    status: Optional[UnitStatus] = Query(None, description="Filter by lifecycle status"),
    lot_number: Optional[str] = Query(None, description="Filter by lot number"),
    gtin: Optional[str] = Query(None, description="Filter by GTIN"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> SerializedUnitListResponse:
    svc = get_supply_serialization_service()
    items, total = svc.list_units(
        serialization_level=serialization_level,
        status=status,
        lot_number=lot_number,
        gtin=gtin,
        limit=limit,
        offset=offset,
    )
    return SerializedUnitListResponse(items=items, total=total)


@router.get(
    "/units/{unit_id}",
    response_model=SerializedUnit,
    summary="Get Serialized Unit",
    description="Retrieve a single serialized unit by ID.",
)
async def get_unit(unit_id: str) -> SerializedUnit:
    svc = get_supply_serialization_service()
    try:
        return svc.get_unit(unit_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/units",
    response_model=SerializedUnit,
    status_code=201,
    summary="Register Serialized Unit",
    description="Register a new serialized unit with GTIN, serial number, and hierarchy.",
)
async def register_serial(data: SerializedUnitCreate) -> SerializedUnit:
    svc = get_supply_serialization_service()
    try:
        return svc.register_serial(data)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put(
    "/units/{unit_id}",
    response_model=SerializedUnit,
    summary="Update Serialized Unit",
    description="Update status, location, or parent of a serialized unit.",
)
async def update_unit(unit_id: str, data: SerializedUnitUpdate) -> SerializedUnit:
    svc = get_supply_serialization_service()
    try:
        return svc.update_unit(unit_id, data)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete(
    "/units/{unit_id}",
    status_code=204,
    summary="Delete Serialized Unit",
    description="Remove a serialized unit from tracking.",
)
async def delete_unit(unit_id: str) -> None:
    svc = get_supply_serialization_service()
    try:
        svc.delete_unit(unit_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/units/{unit_id}/children",
    response_model=SerializedUnitListResponse,
    summary="Get Child Units",
    description="Retrieve child units in the aggregation hierarchy.",
)
async def get_children(unit_id: str) -> SerializedUnitListResponse:
    svc = get_supply_serialization_service()
    try:
        children = svc.get_children(unit_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SerializedUnitListResponse(items=children, total=len(children))


@router.get(
    "/units/{unit_id}/trace",
    response_model=UnitTraceResponse,
    summary="Trace Unit History",
    description="Build a full supply chain history trace for a serialized unit.",
)
async def trace_unit_history(unit_id: str) -> UnitTraceResponse:
    svc = get_supply_serialization_service()
    try:
        return svc.trace_unit_history(unit_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Tracking Events
# ---------------------------------------------------------------------------


@router.get(
    "/tracking-events",
    response_model=TrackingEventListResponse,
    summary="List Tracking Events",
    description="Retrieve tracking events with optional filtering by unit or event type.",
)
async def list_tracking_events(
    unit_id: Optional[str] = Query(None, description="Filter by unit ID"),
    event_type: Optional[TrackingEventType] = Query(None, description="Filter by event type"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> TrackingEventListResponse:
    svc = get_supply_serialization_service()
    items, total = svc.list_tracking_events(
        unit_id=unit_id, event_type=event_type, limit=limit, offset=offset,
    )
    return TrackingEventListResponse(items=items, total=total)


@router.get(
    "/tracking-events/{event_id}",
    response_model=TrackingEvent,
    summary="Get Tracking Event",
    description="Retrieve a single tracking event by ID.",
)
async def get_tracking_event(event_id: str) -> TrackingEvent:
    svc = get_supply_serialization_service()
    try:
        return svc.get_tracking_event(event_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/tracking-events",
    response_model=TrackingEvent,
    status_code=201,
    summary="Record Tracking Event",
    description="Record a new tracking event for a serialized unit.",
)
async def record_tracking_event(data: TrackingEventCreate) -> TrackingEvent:
    svc = get_supply_serialization_service()
    try:
        return svc.record_tracking_event(data)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete(
    "/tracking-events/{event_id}",
    status_code=204,
    summary="Delete Tracking Event",
    description="Remove a tracking event.",
)
async def delete_tracking_event(event_id: str) -> None:
    svc = get_supply_serialization_service()
    try:
        svc.delete_tracking_event(event_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Cold Chain Monitoring
# ---------------------------------------------------------------------------


@router.get(
    "/cold-chain",
    response_model=ColdChainReadingListResponse,
    summary="List Cold Chain Readings",
    description="Retrieve cold chain readings with optional filtering.",
)
async def list_cold_chain_readings(
    shipment_id: Optional[str] = Query(None, description="Filter by shipment ID"),
    status: Optional[ColdChainStatus] = Query(None, description="Filter by status"),
    alert_triggered: Optional[bool] = Query(None, description="Filter by alert triggered"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> ColdChainReadingListResponse:
    svc = get_supply_serialization_service()
    items, total = svc.list_cold_chain_readings(
        shipment_id=shipment_id, status=status, alert_triggered=alert_triggered,
        limit=limit, offset=offset,
    )
    return ColdChainReadingListResponse(items=items, total=total)


@router.get(
    "/cold-chain/{reading_id}",
    response_model=ColdChainReading,
    summary="Get Cold Chain Reading",
    description="Retrieve a single cold chain reading by ID.",
)
async def get_cold_chain_reading(reading_id: str) -> ColdChainReading:
    svc = get_supply_serialization_service()
    try:
        return svc.get_cold_chain_reading(reading_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/cold-chain",
    response_model=ColdChainReading,
    status_code=201,
    summary="Log Cold Chain Reading",
    description="Log a new cold chain reading with automatic status classification.",
)
async def log_cold_chain(data: ColdChainReadingCreate) -> ColdChainReading:
    svc = get_supply_serialization_service()
    return svc.log_cold_chain(data)


@router.post(
    "/cold-chain/{reading_id}/acknowledge",
    response_model=ColdChainReading,
    summary="Acknowledge Cold Chain Alert",
    description="Acknowledge a cold chain alert for a reading that triggered one.",
)
async def acknowledge_cold_chain_alert(
    reading_id: str, data: ColdChainAcknowledge,
) -> ColdChainReading:
    svc = get_supply_serialization_service()
    try:
        return svc.acknowledge_cold_chain_alert(reading_id, data)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/cold-chain/{reading_id}",
    status_code=204,
    summary="Delete Cold Chain Reading",
    description="Remove a cold chain reading.",
)
async def delete_cold_chain_reading(reading_id: str) -> None:
    svc = get_supply_serialization_service()
    try:
        svc.delete_cold_chain_reading(reading_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Compliance
# ---------------------------------------------------------------------------


@router.get(
    "/compliance",
    response_model=ComplianceRecordListResponse,
    summary="List Compliance Records",
    description="Retrieve compliance records with optional filtering.",
)
async def list_compliance_records(
    unit_id: Optional[str] = Query(None, description="Filter by unit ID"),
    standard: Optional[ComplianceStandard] = Query(None, description="Filter by standard"),
    compliant: Optional[bool] = Query(None, description="Filter by compliance status"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> ComplianceRecordListResponse:
    svc = get_supply_serialization_service()
    items, total = svc.list_compliance_records(
        unit_id=unit_id, standard=standard, compliant=compliant,
        limit=limit, offset=offset,
    )
    return ComplianceRecordListResponse(items=items, total=total)


@router.get(
    "/compliance/{record_id}",
    response_model=ComplianceRecord,
    summary="Get Compliance Record",
    description="Retrieve a single compliance record by ID.",
)
async def get_compliance_record(record_id: str) -> ComplianceRecord:
    svc = get_supply_serialization_service()
    try:
        return svc.get_compliance_record(record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/compliance",
    response_model=ComplianceRecord,
    status_code=201,
    summary="Check Compliance",
    description="Create a compliance verification record for a serialized unit.",
)
async def check_compliance(data: ComplianceRecordCreate) -> ComplianceRecord:
    svc = get_supply_serialization_service()
    try:
        return svc.check_compliance(data)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete(
    "/compliance/{record_id}",
    status_code=204,
    summary="Delete Compliance Record",
    description="Remove a compliance record.",
)
async def delete_compliance_record(record_id: str) -> None:
    svc = get_supply_serialization_service()
    try:
        svc.delete_compliance_record(record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Verification Requests
# ---------------------------------------------------------------------------


@router.get(
    "/verifications",
    response_model=VerificationRequestListResponse,
    summary="List Verification Requests",
    description="Retrieve verification requests with optional status filtering.",
)
async def list_verification_requests(
    verification_status: Optional[VerificationStatus] = Query(
        None, description="Filter by verification status"
    ),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> VerificationRequestListResponse:
    svc = get_supply_serialization_service()
    items, total = svc.list_verification_requests(
        verification_status=verification_status, limit=limit, offset=offset,
    )
    return VerificationRequestListResponse(items=items, total=total)


@router.get(
    "/verifications/{request_id}",
    response_model=VerificationRequest,
    summary="Get Verification Request",
    description="Retrieve a single verification request by ID.",
)
async def get_verification_request(request_id: str) -> VerificationRequest:
    svc = get_supply_serialization_service()
    try:
        return svc.get_verification_request(request_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/verifications",
    response_model=VerificationRequest,
    status_code=201,
    summary="Verify Unit",
    description="Submit a verification request to check product authenticity.",
)
async def verify_unit(data: VerificationRequestCreate) -> VerificationRequest:
    svc = get_supply_serialization_service()
    return svc.verify_unit(data)


@router.put(
    "/verifications/{request_id}",
    response_model=VerificationRequest,
    summary="Update Verification Request",
    description="Update a verification request with investigation results.",
)
async def update_verification_request(
    request_id: str, data: VerificationRequestUpdate,
) -> VerificationRequest:
    svc = get_supply_serialization_service()
    try:
        return svc.update_verification_request(request_id, data)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete(
    "/verifications/{request_id}",
    status_code=204,
    summary="Delete Verification Request",
    description="Remove a verification request.",
)
async def delete_verification_request(request_id: str) -> None:
    svc = get_supply_serialization_service()
    try:
        svc.delete_verification_request(request_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Distribution Records
# ---------------------------------------------------------------------------


@router.get(
    "/distributions",
    response_model=DistributionRecordListResponse,
    summary="List Distribution Records",
    description="Retrieve distribution records with optional filtering.",
)
async def list_distribution_records(
    from_facility: Optional[str] = Query(None, description="Filter by origin facility"),
    to_facility: Optional[str] = Query(None, description="Filter by destination facility"),
    discrepancy: Optional[bool] = Query(None, description="Filter by discrepancy flag"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> DistributionRecordListResponse:
    svc = get_supply_serialization_service()
    items, total = svc.list_distribution_records(
        from_facility=from_facility, to_facility=to_facility,
        discrepancy=discrepancy, limit=limit, offset=offset,
    )
    return DistributionRecordListResponse(items=items, total=total)


@router.get(
    "/distributions/{record_id}",
    response_model=DistributionRecord,
    summary="Get Distribution Record",
    description="Retrieve a single distribution record by ID.",
)
async def get_distribution_record(record_id: str) -> DistributionRecord:
    svc = get_supply_serialization_service()
    try:
        return svc.get_distribution_record(record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/distributions",
    response_model=DistributionRecord,
    status_code=201,
    summary="Create Distribution Record",
    description="Create a new distribution record for unit shipment.",
)
async def create_distribution_record(data: DistributionRecordCreate) -> DistributionRecord:
    svc = get_supply_serialization_service()
    return svc.create_distribution_record(data)


@router.put(
    "/distributions/{record_id}",
    response_model=DistributionRecord,
    summary="Update Distribution Record",
    description="Update a distribution record (e.g., record receipt and verify custody).",
)
async def update_distribution_record(
    record_id: str, data: DistributionRecordUpdate,
) -> DistributionRecord:
    svc = get_supply_serialization_service()
    try:
        return svc.update_distribution_record(record_id, data)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete(
    "/distributions/{record_id}",
    status_code=204,
    summary="Delete Distribution Record",
    description="Remove a distribution record.",
)
async def delete_distribution_record(record_id: str) -> None:
    svc = get_supply_serialization_service()
    try:
        svc.delete_distribution_record(record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=SerializationMetrics,
    summary="Serialization Metrics",
    description="Get aggregated serialization and track-and-trace metrics.",
)
async def get_metrics() -> SerializationMetrics:
    svc = get_supply_serialization_service()
    return svc.get_metrics()
