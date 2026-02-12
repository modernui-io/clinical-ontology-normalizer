"""Environmental Monitoring (ENV-MON) API endpoints.

Manages environmental conditions for investigational products: storage facility
management, monitoring sensors, temperature excursion tracking, calibration
records, cold chain shipment compliance, and environmental monitoring metrics.

Endpoints:
    GET    /environmental-monitoring/facilities                        - List facilities
    GET    /environmental-monitoring/facilities/{facility_id}          - Get single facility
    POST   /environmental-monitoring/facilities                        - Create facility
    PUT    /environmental-monitoring/facilities/{facility_id}          - Update facility
    DELETE /environmental-monitoring/facilities/{facility_id}          - Delete facility
    GET    /environmental-monitoring/sensors                           - List sensors
    GET    /environmental-monitoring/sensors/{sensor_id}               - Get single sensor
    POST   /environmental-monitoring/sensors                           - Create sensor
    PUT    /environmental-monitoring/sensors/{sensor_id}               - Update sensor
    DELETE /environmental-monitoring/sensors/{sensor_id}               - Delete sensor
    GET    /environmental-monitoring/excursions                        - List excursions
    GET    /environmental-monitoring/excursions/{excursion_id}         - Get single excursion
    POST   /environmental-monitoring/excursions                        - Create excursion
    PUT    /environmental-monitoring/excursions/{excursion_id}         - Update excursion
    DELETE /environmental-monitoring/excursions/{excursion_id}         - Delete excursion
    GET    /environmental-monitoring/calibrations                      - List calibrations
    GET    /environmental-monitoring/calibrations/{calibration_id}     - Get single calibration
    POST   /environmental-monitoring/calibrations                      - Create calibration
    DELETE /environmental-monitoring/calibrations/{calibration_id}     - Delete calibration
    GET    /environmental-monitoring/shipments                         - List shipments
    GET    /environmental-monitoring/shipments/{shipment_id}           - Get single shipment
    POST   /environmental-monitoring/shipments                         - Create shipment
    PUT    /environmental-monitoring/shipments/{shipment_id}           - Update shipment
    DELETE /environmental-monitoring/shipments/{shipment_id}           - Delete shipment
    GET    /environmental-monitoring/metrics                           - Monitoring metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.environmental_monitoring import (
    CalibrationRecord,
    CalibrationRecordCreate,
    CalibrationRecordListResponse,
    ColdChainShipment,
    ColdChainShipmentCreate,
    ColdChainShipmentListResponse,
    ColdChainShipmentUpdate,
    EnvironmentalMonitoringMetrics,
    MonitoringSensor,
    MonitoringSensorCreate,
    MonitoringSensorListResponse,
    MonitoringSensorUpdate,
    StorageFacility,
    StorageFacilityCreate,
    StorageFacilityListResponse,
    StorageFacilityUpdate,
    TemperatureExcursion,
    TemperatureExcursionCreate,
    TemperatureExcursionListResponse,
    TemperatureExcursionUpdate,
)
from app.services.environmental_monitoring_service import (
    get_environmental_monitoring_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/environmental-monitoring",
    tags=["Environmental Monitoring"],
)


# ---------------------------------------------------------------------------
# Storage Facilities
# ---------------------------------------------------------------------------


@router.get(
    "/facilities",
    response_model=StorageFacilityListResponse,
    summary="List storage facilities",
    description="Retrieve storage facilities with optional filtering by trial.",
)
async def list_facilities(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> StorageFacilityListResponse:
    svc = get_environmental_monitoring_service()
    items = svc.list_facilities(trial_id=trial_id)
    return StorageFacilityListResponse(items=items, total=len(items))


@router.get(
    "/facilities/{facility_id}",
    response_model=StorageFacility,
    summary="Get a storage facility",
)
async def get_facility(facility_id: str) -> StorageFacility:
    svc = get_environmental_monitoring_service()
    facility = svc.get_facility(facility_id)
    if facility is None:
        raise HTTPException(status_code=404, detail=f"Facility '{facility_id}' not found")
    return facility


@router.post(
    "/facilities",
    response_model=StorageFacility,
    status_code=201,
    summary="Create a storage facility",
)
async def create_facility(payload: StorageFacilityCreate) -> StorageFacility:
    svc = get_environmental_monitoring_service()
    return svc.create_facility(payload)


@router.put(
    "/facilities/{facility_id}",
    response_model=StorageFacility,
    summary="Update a storage facility",
)
async def update_facility(
    facility_id: str, payload: StorageFacilityUpdate
) -> StorageFacility:
    svc = get_environmental_monitoring_service()
    updated = svc.update_facility(facility_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Facility '{facility_id}' not found")
    return updated


@router.delete(
    "/facilities/{facility_id}",
    status_code=204,
    summary="Delete a storage facility",
)
async def delete_facility(facility_id: str) -> None:
    svc = get_environmental_monitoring_service()
    deleted = svc.delete_facility(facility_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Facility '{facility_id}' not found")


# ---------------------------------------------------------------------------
# Monitoring Sensors
# ---------------------------------------------------------------------------


@router.get(
    "/sensors",
    response_model=MonitoringSensorListResponse,
    summary="List monitoring sensors",
    description="Retrieve monitoring sensors with optional filtering by facility.",
)
async def list_sensors(
    facility_id: Optional[str] = Query(None, description="Filter by facility ID"),
) -> MonitoringSensorListResponse:
    svc = get_environmental_monitoring_service()
    items = svc.list_sensors(facility_id=facility_id)
    return MonitoringSensorListResponse(items=items, total=len(items))


@router.get(
    "/sensors/{sensor_id}",
    response_model=MonitoringSensor,
    summary="Get a monitoring sensor",
)
async def get_sensor(sensor_id: str) -> MonitoringSensor:
    svc = get_environmental_monitoring_service()
    sensor = svc.get_sensor(sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail=f"Sensor '{sensor_id}' not found")
    return sensor


@router.post(
    "/sensors",
    response_model=MonitoringSensor,
    status_code=201,
    summary="Create a monitoring sensor",
)
async def create_sensor(payload: MonitoringSensorCreate) -> MonitoringSensor:
    svc = get_environmental_monitoring_service()
    return svc.create_sensor(payload)


@router.put(
    "/sensors/{sensor_id}",
    response_model=MonitoringSensor,
    summary="Update a monitoring sensor",
)
async def update_sensor(
    sensor_id: str, payload: MonitoringSensorUpdate
) -> MonitoringSensor:
    svc = get_environmental_monitoring_service()
    updated = svc.update_sensor(sensor_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Sensor '{sensor_id}' not found")
    return updated


@router.delete(
    "/sensors/{sensor_id}",
    status_code=204,
    summary="Delete a monitoring sensor",
)
async def delete_sensor(sensor_id: str) -> None:
    svc = get_environmental_monitoring_service()
    deleted = svc.delete_sensor(sensor_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Sensor '{sensor_id}' not found")


# ---------------------------------------------------------------------------
# Temperature Excursions
# ---------------------------------------------------------------------------


@router.get(
    "/excursions",
    response_model=TemperatureExcursionListResponse,
    summary="List temperature excursions",
    description="Retrieve temperature excursions with optional filtering by trial.",
)
async def list_excursions(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> TemperatureExcursionListResponse:
    svc = get_environmental_monitoring_service()
    items = svc.list_excursions(trial_id=trial_id)
    return TemperatureExcursionListResponse(items=items, total=len(items))


@router.get(
    "/excursions/{excursion_id}",
    response_model=TemperatureExcursion,
    summary="Get a temperature excursion",
)
async def get_excursion(excursion_id: str) -> TemperatureExcursion:
    svc = get_environmental_monitoring_service()
    excursion = svc.get_excursion(excursion_id)
    if excursion is None:
        raise HTTPException(status_code=404, detail=f"Excursion '{excursion_id}' not found")
    return excursion


@router.post(
    "/excursions",
    response_model=TemperatureExcursion,
    status_code=201,
    summary="Create a temperature excursion",
)
async def create_excursion(payload: TemperatureExcursionCreate) -> TemperatureExcursion:
    svc = get_environmental_monitoring_service()
    return svc.create_excursion(payload)


@router.put(
    "/excursions/{excursion_id}",
    response_model=TemperatureExcursion,
    summary="Update a temperature excursion",
)
async def update_excursion(
    excursion_id: str, payload: TemperatureExcursionUpdate
) -> TemperatureExcursion:
    svc = get_environmental_monitoring_service()
    updated = svc.update_excursion(excursion_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Excursion '{excursion_id}' not found")
    return updated


@router.delete(
    "/excursions/{excursion_id}",
    status_code=204,
    summary="Delete a temperature excursion",
)
async def delete_excursion(excursion_id: str) -> None:
    svc = get_environmental_monitoring_service()
    deleted = svc.delete_excursion(excursion_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Excursion '{excursion_id}' not found")


# ---------------------------------------------------------------------------
# Calibration Records
# ---------------------------------------------------------------------------


@router.get(
    "/calibrations",
    response_model=CalibrationRecordListResponse,
    summary="List calibration records",
    description="Retrieve calibration records with optional filtering by sensor.",
)
async def list_calibrations(
    sensor_id: Optional[str] = Query(None, description="Filter by sensor ID"),
) -> CalibrationRecordListResponse:
    svc = get_environmental_monitoring_service()
    items = svc.list_calibrations(sensor_id=sensor_id)
    return CalibrationRecordListResponse(items=items, total=len(items))


@router.get(
    "/calibrations/{calibration_id}",
    response_model=CalibrationRecord,
    summary="Get a calibration record",
)
async def get_calibration(calibration_id: str) -> CalibrationRecord:
    svc = get_environmental_monitoring_service()
    calibration = svc.get_calibration(calibration_id)
    if calibration is None:
        raise HTTPException(status_code=404, detail=f"Calibration '{calibration_id}' not found")
    return calibration


@router.post(
    "/calibrations",
    response_model=CalibrationRecord,
    status_code=201,
    summary="Create a calibration record",
)
async def create_calibration(payload: CalibrationRecordCreate) -> CalibrationRecord:
    svc = get_environmental_monitoring_service()
    return svc.create_calibration(payload)


@router.delete(
    "/calibrations/{calibration_id}",
    status_code=204,
    summary="Delete a calibration record",
)
async def delete_calibration(calibration_id: str) -> None:
    svc = get_environmental_monitoring_service()
    deleted = svc.delete_calibration(calibration_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Calibration '{calibration_id}' not found")


# ---------------------------------------------------------------------------
# Cold Chain Shipments
# ---------------------------------------------------------------------------


@router.get(
    "/shipments",
    response_model=ColdChainShipmentListResponse,
    summary="List cold chain shipments",
    description="Retrieve cold chain shipments with optional filtering by trial.",
)
async def list_shipments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> ColdChainShipmentListResponse:
    svc = get_environmental_monitoring_service()
    items = svc.list_shipments(trial_id=trial_id)
    return ColdChainShipmentListResponse(items=items, total=len(items))


@router.get(
    "/shipments/{shipment_id}",
    response_model=ColdChainShipment,
    summary="Get a cold chain shipment",
)
async def get_shipment(shipment_id: str) -> ColdChainShipment:
    svc = get_environmental_monitoring_service()
    shipment = svc.get_shipment(shipment_id)
    if shipment is None:
        raise HTTPException(status_code=404, detail=f"Shipment '{shipment_id}' not found")
    return shipment


@router.post(
    "/shipments",
    response_model=ColdChainShipment,
    status_code=201,
    summary="Create a cold chain shipment",
)
async def create_shipment(payload: ColdChainShipmentCreate) -> ColdChainShipment:
    svc = get_environmental_monitoring_service()
    return svc.create_shipment(payload)


@router.put(
    "/shipments/{shipment_id}",
    response_model=ColdChainShipment,
    summary="Update a cold chain shipment",
)
async def update_shipment(
    shipment_id: str, payload: ColdChainShipmentUpdate
) -> ColdChainShipment:
    svc = get_environmental_monitoring_service()
    updated = svc.update_shipment(shipment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Shipment '{shipment_id}' not found")
    return updated


@router.delete(
    "/shipments/{shipment_id}",
    status_code=204,
    summary="Delete a cold chain shipment",
)
async def delete_shipment(shipment_id: str) -> None:
    svc = get_environmental_monitoring_service()
    deleted = svc.delete_shipment(shipment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Shipment '{shipment_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=EnvironmentalMonitoringMetrics,
    summary="Get environmental monitoring metrics",
    description="Aggregated environmental monitoring metrics including facility counts, "
                "sensor status, excursion breakdown, calibration compliance, and shipment stats.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> EnvironmentalMonitoringMetrics:
    svc = get_environmental_monitoring_service()
    return svc.get_metrics(trial_id=trial_id)
