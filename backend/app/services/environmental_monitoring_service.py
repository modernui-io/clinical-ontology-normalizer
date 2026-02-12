"""Environmental Monitoring (ENV-MON) Service.

Manages environmental conditions for investigational products: storage facility
management, monitoring sensors, temperature excursion tracking, calibration
records, cold chain shipment compliance, and environmental monitoring metrics.

Usage:
    from app.services.environmental_monitoring_service import (
        get_environmental_monitoring_service,
    )

    svc = get_environmental_monitoring_service()
    facilities = svc.list_facilities()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.environmental_monitoring import (
    CalibrationRecord,
    CalibrationRecordCreate,
    CalibrationStatus,
    ColdChainShipment,
    ColdChainShipmentCreate,
    ColdChainShipmentUpdate,
    EnvironmentalMonitoringMetrics,
    ExcursionSeverity,
    ExcursionStatus,
    MonitoringSensor,
    MonitoringSensorCreate,
    MonitoringSensorUpdate,
    SensorType,
    StorageCondition,
    StorageFacility,
    StorageFacilityCreate,
    StorageFacilityUpdate,
    TemperatureExcursion,
    TemperatureExcursionCreate,
    TemperatureExcursionUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class EnvironmentalMonitoringService:
    """In-memory Environmental Monitoring engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._facilities: dict[str, StorageFacility] = {}
        self._sensors: dict[str, MonitoringSensor] = {}
        self._excursions: dict[str, TemperatureExcursion] = {}
        self._calibrations: dict[str, CalibrationRecord] = {}
        self._shipments: dict[str, ColdChainShipment] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic environmental monitoring data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Storage Facilities ---
        facilities_data = [
            {"id": "FAC-001", "trial_id": EYLEA_TRIAL, "facility_name": "Tarrytown Central Pharmacy", "facility_type": "central_pharmacy", "location": "Tarrytown, NY", "storage_condition": StorageCondition.REFRIGERATED, "temperature_min": 2.0, "temperature_max": 8.0, "humidity_min_pct": 30.0, "humidity_max_pct": 65.0, "capacity_units": 5000, "current_occupancy": 3200, "qualified": True, "qualification_date": now - timedelta(days=180), "next_qualification_date": now + timedelta(days=185), "responsible_person": "Dr. Sarah Chen", "site_id": "SITE-101", "created_at": now - timedelta(days=365)},
            {"id": "FAC-002", "trial_id": EYLEA_TRIAL, "facility_name": "Boston Depot A", "facility_type": "regional_depot", "location": "Boston, MA", "storage_condition": StorageCondition.REFRIGERATED, "temperature_min": 2.0, "temperature_max": 8.0, "capacity_units": 2000, "current_occupancy": 1100, "qualified": True, "qualification_date": now - timedelta(days=120), "next_qualification_date": now + timedelta(days=245), "responsible_person": "James Rodriguez", "site_id": "SITE-102", "created_at": now - timedelta(days=300)},
            {"id": "FAC-003", "trial_id": EYLEA_TRIAL, "facility_name": "EU Distribution Center", "facility_type": "distribution_center", "location": "Dublin, Ireland", "storage_condition": StorageCondition.REFRIGERATED, "temperature_min": 2.0, "temperature_max": 8.0, "capacity_units": 8000, "current_occupancy": 4500, "qualified": True, "qualification_date": now - timedelta(days=90), "next_qualification_date": now + timedelta(days=275), "responsible_person": "Marie O'Brien", "site_id": "SITE-103", "created_at": now - timedelta(days=400)},
            {"id": "FAC-004", "trial_id": DUPIXENT_TRIAL, "facility_name": "Sanofi Warehouse NJ", "facility_type": "warehouse", "location": "Bridgewater, NJ", "storage_condition": StorageCondition.REFRIGERATED, "temperature_min": 2.0, "temperature_max": 8.0, "humidity_min_pct": 25.0, "humidity_max_pct": 60.0, "capacity_units": 10000, "current_occupancy": 6800, "qualified": True, "qualification_date": now - timedelta(days=60), "next_qualification_date": now + timedelta(days=305), "responsible_person": "Dr. Angela Martinez", "site_id": "SITE-104", "created_at": now - timedelta(days=500)},
            {"id": "FAC-005", "trial_id": DUPIXENT_TRIAL, "facility_name": "Munich Site Pharmacy", "facility_type": "site_pharmacy", "location": "Munich, Germany", "storage_condition": StorageCondition.CONTROLLED_ROOM, "temperature_min": 15.0, "temperature_max": 25.0, "capacity_units": 500, "current_occupancy": 280, "qualified": True, "qualification_date": now - timedelta(days=45), "next_qualification_date": now + timedelta(days=320), "responsible_person": "Hans Muller", "site_id": "SITE-105", "created_at": now - timedelta(days=250)},
            {"id": "FAC-006", "trial_id": DUPIXENT_TRIAL, "facility_name": "Tokyo Clinical Site", "facility_type": "site_pharmacy", "location": "Tokyo, Japan", "storage_condition": StorageCondition.REFRIGERATED, "temperature_min": 2.0, "temperature_max": 8.0, "capacity_units": 800, "current_occupancy": 450, "qualified": True, "qualification_date": now - timedelta(days=30), "next_qualification_date": now + timedelta(days=335), "responsible_person": "Dr. Yuki Tanaka", "site_id": "SITE-106", "created_at": now - timedelta(days=200)},
            {"id": "FAC-007", "trial_id": LIBTAYO_TRIAL, "facility_name": "MD Anderson Pharmacy", "facility_type": "site_pharmacy", "location": "Houston, TX", "storage_condition": StorageCondition.FROZEN, "temperature_min": -25.0, "temperature_max": -15.0, "capacity_units": 1500, "current_occupancy": 900, "qualified": True, "qualification_date": now - timedelta(days=75), "next_qualification_date": now + timedelta(days=290), "responsible_person": "Dr. Robert Kim", "site_id": "SITE-107", "created_at": now - timedelta(days=350)},
            {"id": "FAC-008", "trial_id": LIBTAYO_TRIAL, "facility_name": "MSKCC Infusion Center", "facility_type": "infusion_center", "location": "New York, NY", "storage_condition": StorageCondition.REFRIGERATED, "temperature_min": 2.0, "temperature_max": 8.0, "capacity_units": 300, "current_occupancy": 180, "qualified": True, "qualification_date": now - timedelta(days=100), "next_qualification_date": now + timedelta(days=265), "responsible_person": "Dr. Catherine Liu", "site_id": "SITE-108", "created_at": now - timedelta(days=280)},
            {"id": "FAC-009", "trial_id": LIBTAYO_TRIAL, "facility_name": "London Oncology Hub", "facility_type": "regional_depot", "location": "London, UK", "storage_condition": StorageCondition.ULTRA_FROZEN, "temperature_min": -85.0, "temperature_max": -75.0, "capacity_units": 600, "current_occupancy": 320, "qualified": False, "qualification_date": now - timedelta(days=400), "next_qualification_date": now - timedelta(days=35), "responsible_person": "Dr. William Ashton", "site_id": "SITE-109", "created_at": now - timedelta(days=450)},
            {"id": "FAC-010", "trial_id": EYLEA_TRIAL, "facility_name": "Chicago Investigator Site", "facility_type": "site_pharmacy", "location": "Chicago, IL", "storage_condition": StorageCondition.REFRIGERATED, "temperature_min": 2.0, "temperature_max": 8.0, "capacity_units": 400, "current_occupancy": 210, "qualified": True, "qualification_date": now - timedelta(days=55), "next_qualification_date": now + timedelta(days=310), "responsible_person": "Dr. Patricia Sullivan", "site_id": "SITE-110", "created_at": now - timedelta(days=220)},
            {"id": "FAC-011", "trial_id": DUPIXENT_TRIAL, "facility_name": "Paris Biologics Center", "facility_type": "central_pharmacy", "location": "Paris, France", "storage_condition": StorageCondition.REFRIGERATED, "temperature_min": 2.0, "temperature_max": 8.0, "humidity_min_pct": 30.0, "humidity_max_pct": 60.0, "capacity_units": 6000, "current_occupancy": 4100, "qualified": True, "qualification_date": now - timedelta(days=40), "next_qualification_date": now + timedelta(days=325), "responsible_person": "Dr. Pierre Dupont", "site_id": "SITE-111", "created_at": now - timedelta(days=380)},
            {"id": "FAC-012", "trial_id": LIBTAYO_TRIAL, "facility_name": "Sydney Oncology Depot", "facility_type": "regional_depot", "location": "Sydney, Australia", "storage_condition": StorageCondition.REFRIGERATED, "temperature_min": 2.0, "temperature_max": 8.0, "capacity_units": 1200, "current_occupancy": 650, "qualified": True, "qualification_date": now - timedelta(days=85), "next_qualification_date": now + timedelta(days=280), "responsible_person": "Dr. Emma Walsh", "site_id": "SITE-112", "created_at": now - timedelta(days=310)},
        ]

        for f in facilities_data:
            self._facilities[f["id"]] = StorageFacility(**f)

        # --- 15 Monitoring Sensors ---
        sensors_data = [
            {"id": "SEN-001", "facility_id": "FAC-001", "sensor_type": SensorType.TEMPERATURE, "sensor_serial": "TH-2024-0451", "location_in_facility": "Main refrigerator unit A", "active": True, "reading_interval_minutes": 5, "alert_threshold_low": 1.5, "alert_threshold_high": 8.5, "last_reading_value": 4.2, "last_reading_time": now - timedelta(minutes=3), "calibration_status": CalibrationStatus.CURRENT, "calibration_due_date": now + timedelta(days=90), "installed_date": now - timedelta(days=300), "installed_by": "TechCal Services"},
            {"id": "SEN-002", "facility_id": "FAC-001", "sensor_type": SensorType.HUMIDITY, "sensor_serial": "HM-2024-0122", "location_in_facility": "Main refrigerator unit A", "active": True, "reading_interval_minutes": 15, "alert_threshold_low": 25.0, "alert_threshold_high": 70.0, "last_reading_value": 45.3, "last_reading_time": now - timedelta(minutes=12), "calibration_status": CalibrationStatus.CURRENT, "calibration_due_date": now + timedelta(days=120), "installed_date": now - timedelta(days=300), "installed_by": "TechCal Services"},
            {"id": "SEN-003", "facility_id": "FAC-002", "sensor_type": SensorType.TEMPERATURE, "sensor_serial": "TH-2024-0452", "location_in_facility": "Walk-in cooler north wall", "active": True, "reading_interval_minutes": 5, "alert_threshold_low": 1.5, "alert_threshold_high": 8.5, "last_reading_value": 5.1, "last_reading_time": now - timedelta(minutes=2), "calibration_status": CalibrationStatus.CURRENT, "calibration_due_date": now + timedelta(days=60), "installed_date": now - timedelta(days=250), "installed_by": "PharmaTemp Inc"},
            {"id": "SEN-004", "facility_id": "FAC-003", "sensor_type": SensorType.TEMPERATURE, "sensor_serial": "TH-2024-0453", "location_in_facility": "Cold storage room center", "active": True, "reading_interval_minutes": 10, "alert_threshold_low": 1.0, "alert_threshold_high": 9.0, "last_reading_value": 3.8, "last_reading_time": now - timedelta(minutes=8), "calibration_status": CalibrationStatus.DUE_SOON, "calibration_due_date": now + timedelta(days=14), "installed_date": now - timedelta(days=350), "installed_by": "EuroTemp GmbH"},
            {"id": "SEN-005", "facility_id": "FAC-004", "sensor_type": SensorType.TEMPERATURE, "sensor_serial": "TH-2024-0454", "location_in_facility": "Warehouse refrigeration zone 1", "active": True, "reading_interval_minutes": 5, "alert_threshold_low": 1.5, "alert_threshold_high": 8.5, "last_reading_value": 6.7, "last_reading_time": now - timedelta(minutes=4), "calibration_status": CalibrationStatus.CURRENT, "calibration_due_date": now + timedelta(days=150), "installed_date": now - timedelta(days=400), "installed_by": "ColdGuard Systems"},
            {"id": "SEN-006", "facility_id": "FAC-004", "sensor_type": SensorType.HUMIDITY, "sensor_serial": "HM-2024-0123", "location_in_facility": "Warehouse refrigeration zone 1", "active": True, "reading_interval_minutes": 15, "alert_threshold_low": 20.0, "alert_threshold_high": 65.0, "last_reading_value": 42.1, "last_reading_time": now - timedelta(minutes=10), "calibration_status": CalibrationStatus.CURRENT, "calibration_due_date": now + timedelta(days=180), "installed_date": now - timedelta(days=400), "installed_by": "ColdGuard Systems"},
            {"id": "SEN-007", "facility_id": "FAC-005", "sensor_type": SensorType.TEMPERATURE, "sensor_serial": "TH-2024-0455", "location_in_facility": "Controlled room storage cabinet", "active": True, "reading_interval_minutes": 15, "alert_threshold_low": 14.0, "alert_threshold_high": 26.0, "last_reading_value": 21.3, "last_reading_time": now - timedelta(minutes=7), "calibration_status": CalibrationStatus.CURRENT, "calibration_due_date": now + timedelta(days=200), "installed_date": now - timedelta(days=200), "installed_by": "TempWatch EU"},
            {"id": "SEN-008", "facility_id": "FAC-007", "sensor_type": SensorType.TEMPERATURE, "sensor_serial": "TH-2024-0456", "location_in_facility": "Freezer unit F-1 top shelf", "active": True, "reading_interval_minutes": 5, "alert_threshold_low": -26.0, "alert_threshold_high": -14.0, "last_reading_value": -20.5, "last_reading_time": now - timedelta(minutes=1), "calibration_status": CalibrationStatus.CURRENT, "calibration_due_date": now + timedelta(days=75), "installed_date": now - timedelta(days=280), "installed_by": "CryoTech USA"},
            {"id": "SEN-009", "facility_id": "FAC-008", "sensor_type": SensorType.TEMPERATURE, "sensor_serial": "TH-2024-0457", "location_in_facility": "Infusion prep refrigerator", "active": True, "reading_interval_minutes": 5, "alert_threshold_low": 1.5, "alert_threshold_high": 8.5, "last_reading_value": 5.9, "last_reading_time": now - timedelta(minutes=5), "calibration_status": CalibrationStatus.CURRENT, "calibration_due_date": now + timedelta(days=110), "installed_date": now - timedelta(days=220), "installed_by": "MedTemp Solutions"},
            {"id": "SEN-010", "facility_id": "FAC-009", "sensor_type": SensorType.TEMPERATURE, "sensor_serial": "TH-2024-0458", "location_in_facility": "Ultra-low freezer ULF-3", "active": False, "reading_interval_minutes": 5, "alert_threshold_low": -86.0, "alert_threshold_high": -74.0, "last_reading_value": -79.2, "last_reading_time": now - timedelta(days=2), "calibration_status": CalibrationStatus.OVERDUE, "calibration_due_date": now - timedelta(days=30), "installed_date": now - timedelta(days=400), "installed_by": "CryoTech UK"},
            {"id": "SEN-011", "facility_id": "FAC-010", "sensor_type": SensorType.TEMPERATURE, "sensor_serial": "TH-2024-0459", "location_in_facility": "Site pharmacy fridge", "active": True, "reading_interval_minutes": 10, "alert_threshold_low": 1.5, "alert_threshold_high": 8.5, "last_reading_value": 4.8, "last_reading_time": now - timedelta(minutes=6), "calibration_status": CalibrationStatus.CURRENT, "calibration_due_date": now + timedelta(days=95), "installed_date": now - timedelta(days=180), "installed_by": "PharmaTemp Inc"},
            {"id": "SEN-012", "facility_id": "FAC-011", "sensor_type": SensorType.TEMPERATURE, "sensor_serial": "TH-2024-0460", "location_in_facility": "Biologics cold room A", "active": True, "reading_interval_minutes": 5, "alert_threshold_low": 1.0, "alert_threshold_high": 9.0, "last_reading_value": 3.5, "last_reading_time": now - timedelta(minutes=4), "calibration_status": CalibrationStatus.CURRENT, "calibration_due_date": now + timedelta(days=130), "installed_date": now - timedelta(days=320), "installed_by": "TempWatch EU"},
            {"id": "SEN-013", "facility_id": "FAC-011", "sensor_type": SensorType.LIGHT, "sensor_serial": "LX-2024-0031", "location_in_facility": "Biologics cold room A entrance", "active": True, "reading_interval_minutes": 30, "alert_threshold_low": None, "alert_threshold_high": 500.0, "last_reading_value": 120.0, "last_reading_time": now - timedelta(minutes=20), "calibration_status": CalibrationStatus.CURRENT, "calibration_due_date": now + timedelta(days=200), "installed_date": now - timedelta(days=320), "installed_by": "TempWatch EU"},
            {"id": "SEN-014", "facility_id": "FAC-012", "sensor_type": SensorType.TEMPERATURE, "sensor_serial": "TH-2024-0461", "location_in_facility": "Depot refrigerator R-2", "active": True, "reading_interval_minutes": 10, "alert_threshold_low": 1.5, "alert_threshold_high": 8.5, "last_reading_value": 5.4, "last_reading_time": now - timedelta(minutes=9), "calibration_status": CalibrationStatus.DUE_SOON, "calibration_due_date": now + timedelta(days=10), "installed_date": now - timedelta(days=260), "installed_by": "AusCold Pty"},
            {"id": "SEN-015", "facility_id": "FAC-006", "sensor_type": SensorType.VIBRATION, "sensor_serial": "VB-2024-0008", "location_in_facility": "Compressor room adjacent", "active": True, "reading_interval_minutes": 60, "alert_threshold_low": None, "alert_threshold_high": 5.0, "last_reading_value": 1.2, "last_reading_time": now - timedelta(minutes=45), "calibration_status": CalibrationStatus.CURRENT, "calibration_due_date": now + timedelta(days=250), "installed_date": now - timedelta(days=150), "installed_by": "VibSense Japan"},
        ]

        for s in sensors_data:
            self._sensors[s["id"]] = MonitoringSensor(**s)

        # --- 12 Temperature Excursions ---
        excursions_data = [
            {"id": "EXC-001", "facility_id": "FAC-001", "sensor_id": "SEN-001", "trial_id": EYLEA_TRIAL, "severity": ExcursionSeverity.MINOR, "status": ExcursionStatus.RESOLVED, "excursion_start": now - timedelta(days=60, hours=3), "excursion_end": now - timedelta(days=60, hours=1), "duration_minutes": 120, "min_temperature": 1.2, "max_temperature": 8.0, "allowed_min": 2.0, "allowed_max": 8.0, "products_affected": 50, "root_cause": "Brief door seal failure during restocking", "corrective_action": "Door seal replaced and restocking SOP updated", "product_disposition": "Products assessed and released - no impact", "reported_by": "Sarah Chen", "investigated_by": "QA Team Lead", "created_at": now - timedelta(days=60)},
            {"id": "EXC-002", "facility_id": "FAC-002", "sensor_id": "SEN-003", "trial_id": EYLEA_TRIAL, "severity": ExcursionSeverity.MODERATE, "status": ExcursionStatus.RESOLVED, "excursion_start": now - timedelta(days=45, hours=6), "excursion_end": now - timedelta(days=45, hours=2), "duration_minutes": 240, "min_temperature": 2.0, "max_temperature": 12.3, "allowed_min": 2.0, "allowed_max": 8.0, "products_affected": 200, "root_cause": "Compressor malfunction during heatwave", "corrective_action": "Emergency compressor repair and backup unit installed", "product_disposition": "Stability data review - 120 units quarantined", "reported_by": "James Rodriguez", "investigated_by": "QA Director", "created_at": now - timedelta(days=45)},
            {"id": "EXC-003", "facility_id": "FAC-004", "sensor_id": "SEN-005", "trial_id": DUPIXENT_TRIAL, "severity": ExcursionSeverity.MINOR, "status": ExcursionStatus.RESOLVED, "excursion_start": now - timedelta(days=30, hours=2), "excursion_end": now - timedelta(days=30, hours=1), "duration_minutes": 60, "min_temperature": 2.0, "max_temperature": 9.1, "allowed_min": 2.0, "allowed_max": 8.0, "products_affected": 30, "root_cause": "Sensor drift before recalibration", "corrective_action": "Sensor recalibrated and alert thresholds tightened", "product_disposition": "Products released after stability review", "reported_by": "Angela Martinez", "investigated_by": "QA Specialist", "created_at": now - timedelta(days=30)},
            {"id": "EXC-004", "facility_id": "FAC-007", "sensor_id": "SEN-008", "trial_id": LIBTAYO_TRIAL, "severity": ExcursionSeverity.CRITICAL, "status": ExcursionStatus.PRODUCT_IMPACTED, "excursion_start": now - timedelta(days=20, hours=8), "excursion_end": now - timedelta(days=19, hours=4), "duration_minutes": 1680, "min_temperature": -25.0, "max_temperature": -5.0, "allowed_min": -25.0, "allowed_max": -15.0, "products_affected": 450, "root_cause": "Power outage during tropical storm, backup generator failed", "corrective_action": "Generator replaced, UPS system upgraded, emergency protocol revised", "product_disposition": "450 units destroyed per deviation protocol", "reported_by": "Robert Kim", "investigated_by": "VP Quality", "created_at": now - timedelta(days=20)},
            {"id": "EXC-005", "facility_id": "FAC-003", "sensor_id": "SEN-004", "trial_id": EYLEA_TRIAL, "severity": ExcursionSeverity.MINOR, "status": ExcursionStatus.RESOLVED, "excursion_start": now - timedelta(days=15, hours=1), "excursion_end": now - timedelta(days=15), "duration_minutes": 60, "min_temperature": 1.5, "max_temperature": 8.0, "allowed_min": 2.0, "allowed_max": 8.0, "products_affected": 0, "root_cause": "Defrost cycle lasted longer than expected", "corrective_action": "Defrost timer recalibrated", "product_disposition": "No product impact - excursion within tolerable range", "reported_by": "Marie O'Brien", "investigated_by": "Site QA", "created_at": now - timedelta(days=15)},
            {"id": "EXC-006", "facility_id": "FAC-009", "sensor_id": "SEN-010", "trial_id": LIBTAYO_TRIAL, "severity": ExcursionSeverity.MAJOR, "status": ExcursionStatus.UNDER_INVESTIGATION, "excursion_start": now - timedelta(days=5, hours=12), "excursion_end": now - timedelta(days=4, hours=6), "duration_minutes": 1800, "min_temperature": -85.0, "max_temperature": -60.0, "allowed_min": -85.0, "allowed_max": -75.0, "products_affected": 150, "root_cause": None, "corrective_action": None, "product_disposition": None, "reported_by": "William Ashton", "investigated_by": "UK QA Team", "created_at": now - timedelta(days=5)},
            {"id": "EXC-007", "facility_id": "FAC-006", "sensor_id": "SEN-015", "trial_id": DUPIXENT_TRIAL, "severity": ExcursionSeverity.MINOR, "status": ExcursionStatus.ASSESSED, "excursion_start": now - timedelta(days=10, hours=4), "excursion_end": now - timedelta(days=10, hours=3), "duration_minutes": 60, "min_temperature": 2.0, "max_temperature": 9.5, "allowed_min": 2.0, "allowed_max": 8.0, "products_affected": 25, "root_cause": "Earthquake tremor caused brief compressor trip", "corrective_action": "Seismic bracing added to compressor mounts", "product_disposition": None, "reported_by": "Yuki Tanaka", "investigated_by": "Dr. Yuki Tanaka", "created_at": now - timedelta(days=10)},
            {"id": "EXC-008", "facility_id": "FAC-008", "sensor_id": "SEN-009", "trial_id": LIBTAYO_TRIAL, "severity": ExcursionSeverity.MODERATE, "status": ExcursionStatus.RESOLVED, "excursion_start": now - timedelta(days=35, hours=5), "excursion_end": now - timedelta(days=35, hours=1), "duration_minutes": 240, "min_temperature": 2.0, "max_temperature": 11.0, "allowed_min": 2.0, "allowed_max": 8.0, "products_affected": 80, "root_cause": "HVAC maintenance without cold chain notification", "corrective_action": "Maintenance communication SOP updated", "product_disposition": "Products assessed, 60 units released, 20 quarantined", "reported_by": "Catherine Liu", "investigated_by": "MSKCC QA", "created_at": now - timedelta(days=35)},
            {"id": "EXC-009", "facility_id": "FAC-011", "sensor_id": "SEN-012", "trial_id": DUPIXENT_TRIAL, "severity": ExcursionSeverity.MINOR, "status": ExcursionStatus.RESOLVED, "excursion_start": now - timedelta(days=25, hours=2), "excursion_end": now - timedelta(days=25, hours=1), "duration_minutes": 60, "min_temperature": 0.5, "max_temperature": 8.0, "allowed_min": 2.0, "allowed_max": 8.0, "products_affected": 15, "root_cause": "Refrigerant low level", "corrective_action": "Refrigerant topped up and leak repaired", "product_disposition": "Products released after review", "reported_by": "Pierre Dupont", "investigated_by": "EU QA", "created_at": now - timedelta(days=25)},
            {"id": "EXC-010", "facility_id": "FAC-010", "sensor_id": "SEN-011", "trial_id": EYLEA_TRIAL, "severity": ExcursionSeverity.MINOR, "status": ExcursionStatus.DETECTED, "excursion_start": now - timedelta(hours=6), "excursion_end": None, "duration_minutes": 0, "min_temperature": 2.0, "max_temperature": 8.8, "allowed_min": 2.0, "allowed_max": 8.0, "products_affected": 0, "root_cause": None, "corrective_action": None, "product_disposition": None, "reported_by": "Patricia Sullivan", "investigated_by": None, "created_at": now},
            {"id": "EXC-011", "facility_id": "FAC-005", "sensor_id": "SEN-007", "trial_id": DUPIXENT_TRIAL, "severity": ExcursionSeverity.MINOR, "status": ExcursionStatus.RESOLVED, "excursion_start": now - timedelta(days=50, hours=3), "excursion_end": now - timedelta(days=50, hours=2), "duration_minutes": 60, "min_temperature": 15.0, "max_temperature": 26.2, "allowed_min": 15.0, "allowed_max": 25.0, "products_affected": 10, "root_cause": "Direct sunlight through window during summer", "corrective_action": "UV film applied to windows", "product_disposition": "Products released", "reported_by": "Hans Muller", "investigated_by": "Munich QA", "created_at": now - timedelta(days=50)},
            {"id": "EXC-012", "facility_id": "FAC-012", "sensor_id": "SEN-014", "trial_id": LIBTAYO_TRIAL, "severity": ExcursionSeverity.MODERATE, "status": ExcursionStatus.ASSESSED, "excursion_start": now - timedelta(days=8, hours=10), "excursion_end": now - timedelta(days=8, hours=4), "duration_minutes": 360, "min_temperature": 2.0, "max_temperature": 10.5, "allowed_min": 2.0, "allowed_max": 8.0, "products_affected": 90, "root_cause": "Facility power grid brownout", "corrective_action": "Backup power system tested and certified", "product_disposition": None, "reported_by": "Emma Walsh", "investigated_by": "AU QA Director", "created_at": now - timedelta(days=8)},
        ]

        for e in excursions_data:
            self._excursions[e["id"]] = TemperatureExcursion(**e)

        # --- 12 Calibration Records ---
        calibrations_data = [
            {"id": "CAL-001", "sensor_id": "SEN-001", "calibration_date": now - timedelta(days=90), "next_due_date": now + timedelta(days=90), "performed_by": "TechCal Services", "reference_standard": "NIST-traceable Pt100 RTD", "pre_calibration_offset": 0.15, "post_calibration_offset": 0.02, "passed": True, "certificate_number": "TC-2025-04512", "notes": "Routine annual calibration"},
            {"id": "CAL-002", "sensor_id": "SEN-002", "calibration_date": now - timedelta(days=60), "next_due_date": now + timedelta(days=120), "performed_by": "TechCal Services", "reference_standard": "Rotronic HC2A-S humidity standard", "pre_calibration_offset": 1.2, "post_calibration_offset": 0.3, "passed": True, "certificate_number": "TC-2025-04513", "notes": "Humidity probe cleaned and recalibrated"},
            {"id": "CAL-003", "sensor_id": "SEN-003", "calibration_date": now - timedelta(days=120), "next_due_date": now + timedelta(days=60), "performed_by": "PharmaTemp Inc", "reference_standard": "NIST-traceable Pt100 RTD", "pre_calibration_offset": 0.08, "post_calibration_offset": 0.01, "passed": True, "certificate_number": "PT-2025-08821", "notes": "Semi-annual calibration"},
            {"id": "CAL-004", "sensor_id": "SEN-004", "calibration_date": now - timedelta(days=170), "next_due_date": now + timedelta(days=14), "performed_by": "EuroTemp GmbH", "reference_standard": "DKD/DAkkS-calibrated reference thermometer", "pre_calibration_offset": 0.22, "post_calibration_offset": 0.05, "passed": True, "certificate_number": "ET-2025-DE-3301", "notes": "Due for recalibration soon"},
            {"id": "CAL-005", "sensor_id": "SEN-005", "calibration_date": now - timedelta(days=30), "next_due_date": now + timedelta(days=150), "performed_by": "ColdGuard Systems", "reference_standard": "NIST-traceable Pt100 RTD", "pre_calibration_offset": 0.05, "post_calibration_offset": 0.01, "passed": True, "certificate_number": "CG-2025-12240", "notes": "Recent calibration, excellent condition"},
            {"id": "CAL-006", "sensor_id": "SEN-008", "calibration_date": now - timedelta(days=105), "next_due_date": now + timedelta(days=75), "performed_by": "CryoTech USA", "reference_standard": "NIST-traceable cryogenic Pt100", "pre_calibration_offset": 0.35, "post_calibration_offset": 0.08, "passed": True, "certificate_number": "CT-2025-US-5501", "notes": "Freezer sensor calibration"},
            {"id": "CAL-007", "sensor_id": "SEN-009", "calibration_date": now - timedelta(days=70), "next_due_date": now + timedelta(days=110), "performed_by": "MedTemp Solutions", "reference_standard": "NIST-traceable Pt100 RTD", "pre_calibration_offset": 0.12, "post_calibration_offset": 0.03, "passed": True, "certificate_number": "MT-2025-NY-7701", "notes": "Standard calibration"},
            {"id": "CAL-008", "sensor_id": "SEN-010", "calibration_date": now - timedelta(days=210), "next_due_date": now - timedelta(days=30), "performed_by": "CryoTech UK", "reference_standard": "UKAS-accredited cryogenic reference", "pre_calibration_offset": 0.50, "post_calibration_offset": 0.40, "passed": False, "certificate_number": "CT-2024-UK-9902", "notes": "Sensor drift excessive - recommended replacement"},
            {"id": "CAL-009", "sensor_id": "SEN-011", "calibration_date": now - timedelta(days=85), "next_due_date": now + timedelta(days=95), "performed_by": "PharmaTemp Inc", "reference_standard": "NIST-traceable Pt100 RTD", "pre_calibration_offset": 0.10, "post_calibration_offset": 0.02, "passed": True, "certificate_number": "PT-2025-08830", "notes": "Annual calibration"},
            {"id": "CAL-010", "sensor_id": "SEN-012", "calibration_date": now - timedelta(days=50), "next_due_date": now + timedelta(days=130), "performed_by": "TempWatch EU", "reference_standard": "DKD/DAkkS-calibrated reference thermometer", "pre_calibration_offset": 0.07, "post_calibration_offset": 0.02, "passed": True, "certificate_number": "TW-2025-FR-4401", "notes": "Routine calibration"},
            {"id": "CAL-011", "sensor_id": "SEN-014", "calibration_date": now - timedelta(days=170), "next_due_date": now + timedelta(days=10), "performed_by": "AusCold Pty", "reference_standard": "NATA-accredited Pt100 reference", "pre_calibration_offset": 0.18, "post_calibration_offset": 0.04, "passed": True, "certificate_number": "AC-2025-AU-2201", "notes": "Calibration due soon"},
            {"id": "CAL-012", "sensor_id": "SEN-007", "calibration_date": now - timedelta(days=20), "next_due_date": now + timedelta(days=200), "performed_by": "TempWatch EU", "reference_standard": "DKD/DAkkS-calibrated reference thermometer", "pre_calibration_offset": 0.09, "post_calibration_offset": 0.02, "passed": True, "certificate_number": "TW-2025-DE-4410", "notes": "Controlled room temperature sensor"},
        ]

        for c in calibrations_data:
            self._calibrations[c["id"]] = CalibrationRecord(**c)

        # --- 12 Cold Chain Shipments ---
        shipments_data = [
            {"id": "SHP-001", "trial_id": EYLEA_TRIAL, "shipment_id": "REGEN-EYL-2025-001", "origin_facility_id": "FAC-001", "destination_facility_id": "FAC-002", "storage_condition": StorageCondition.REFRIGERATED, "shipper_type": "Qualified passive shipper 48h", "monitoring_device": "TempTale Ultra", "departure_date": now - timedelta(days=40), "arrival_date": now - timedelta(days=39), "transit_duration_hours": 18.5, "min_temp_recorded": 3.1, "max_temp_recorded": 6.8, "excursion_detected": False, "units_shipped": 500, "status": "delivered", "carrier": "World Courier", "created_at": now - timedelta(days=40)},
            {"id": "SHP-002", "trial_id": EYLEA_TRIAL, "shipment_id": "REGEN-EYL-2025-002", "origin_facility_id": "FAC-001", "destination_facility_id": "FAC-003", "storage_condition": StorageCondition.REFRIGERATED, "shipper_type": "Qualified passive shipper 96h", "monitoring_device": "TempTale Ultra", "departure_date": now - timedelta(days=35), "arrival_date": now - timedelta(days=33), "transit_duration_hours": 52.0, "min_temp_recorded": 2.5, "max_temp_recorded": 7.2, "excursion_detected": False, "units_shipped": 1200, "status": "delivered", "carrier": "Marken", "created_at": now - timedelta(days=35)},
            {"id": "SHP-003", "trial_id": EYLEA_TRIAL, "shipment_id": "REGEN-EYL-2025-003", "origin_facility_id": "FAC-003", "destination_facility_id": "FAC-010", "storage_condition": StorageCondition.REFRIGERATED, "shipper_type": "Active temperature-controlled container", "monitoring_device": "Sensitech ColdStream", "departure_date": now - timedelta(days=20), "arrival_date": now - timedelta(days=18), "transit_duration_hours": 42.0, "min_temp_recorded": 3.8, "max_temp_recorded": 5.5, "excursion_detected": False, "units_shipped": 300, "status": "delivered", "carrier": "World Courier", "created_at": now - timedelta(days=20)},
            {"id": "SHP-004", "trial_id": DUPIXENT_TRIAL, "shipment_id": "REGEN-DUP-2025-001", "origin_facility_id": "FAC-004", "destination_facility_id": "FAC-005", "storage_condition": StorageCondition.CONTROLLED_ROOM, "shipper_type": "Insulated shipper 72h", "monitoring_device": "TempTale GEO", "departure_date": now - timedelta(days=28), "arrival_date": now - timedelta(days=26), "transit_duration_hours": 36.0, "min_temp_recorded": 16.2, "max_temp_recorded": 23.1, "excursion_detected": False, "units_shipped": 200, "status": "delivered", "carrier": "FedEx Custom Critical", "created_at": now - timedelta(days=28)},
            {"id": "SHP-005", "trial_id": DUPIXENT_TRIAL, "shipment_id": "REGEN-DUP-2025-002", "origin_facility_id": "FAC-004", "destination_facility_id": "FAC-006", "storage_condition": StorageCondition.REFRIGERATED, "shipper_type": "Qualified passive shipper 120h", "monitoring_device": "TempTale Ultra", "departure_date": now - timedelta(days=22), "arrival_date": now - timedelta(days=19), "transit_duration_hours": 68.0, "min_temp_recorded": 2.8, "max_temp_recorded": 7.9, "excursion_detected": False, "units_shipped": 400, "status": "delivered", "carrier": "Marken", "created_at": now - timedelta(days=22)},
            {"id": "SHP-006", "trial_id": DUPIXENT_TRIAL, "shipment_id": "REGEN-DUP-2025-003", "origin_facility_id": "FAC-011", "destination_facility_id": "FAC-005", "storage_condition": StorageCondition.REFRIGERATED, "shipper_type": "Qualified passive shipper 48h", "monitoring_device": "Sensitech ColdStream", "departure_date": now - timedelta(days=12), "arrival_date": now - timedelta(days=11), "transit_duration_hours": 14.0, "min_temp_recorded": 3.2, "max_temp_recorded": 6.5, "excursion_detected": False, "units_shipped": 150, "status": "delivered", "carrier": "DHL Temperature Management", "created_at": now - timedelta(days=12)},
            {"id": "SHP-007", "trial_id": LIBTAYO_TRIAL, "shipment_id": "REGEN-LIB-2025-001", "origin_facility_id": "FAC-007", "destination_facility_id": "FAC-008", "storage_condition": StorageCondition.REFRIGERATED, "shipper_type": "Qualified passive shipper 48h", "monitoring_device": "TempTale Ultra", "departure_date": now - timedelta(days=18), "arrival_date": now - timedelta(days=17), "transit_duration_hours": 22.0, "min_temp_recorded": 3.5, "max_temp_recorded": 7.0, "excursion_detected": False, "units_shipped": 100, "status": "delivered", "carrier": "World Courier", "created_at": now - timedelta(days=18)},
            {"id": "SHP-008", "trial_id": LIBTAYO_TRIAL, "shipment_id": "REGEN-LIB-2025-002", "origin_facility_id": "FAC-007", "destination_facility_id": "FAC-009", "storage_condition": StorageCondition.ULTRA_FROZEN, "shipper_type": "Dry ice shipper 96h", "monitoring_device": "Sensitech TempTale Dry Ice", "departure_date": now - timedelta(days=14), "arrival_date": now - timedelta(days=12), "transit_duration_hours": 58.0, "min_temp_recorded": -82.0, "max_temp_recorded": -70.0, "excursion_detected": True, "units_shipped": 80, "status": "delivered_with_excursion", "carrier": "Marken", "created_at": now - timedelta(days=14)},
            {"id": "SHP-009", "trial_id": LIBTAYO_TRIAL, "shipment_id": "REGEN-LIB-2025-003", "origin_facility_id": "FAC-007", "destination_facility_id": "FAC-012", "storage_condition": StorageCondition.REFRIGERATED, "shipper_type": "Active temperature-controlled container", "monitoring_device": "Sensitech ColdStream", "departure_date": now - timedelta(days=7), "arrival_date": now - timedelta(days=4), "transit_duration_hours": 72.0, "min_temp_recorded": 3.0, "max_temp_recorded": 6.2, "excursion_detected": False, "units_shipped": 250, "status": "delivered", "carrier": "World Courier", "created_at": now - timedelta(days=7)},
            {"id": "SHP-010", "trial_id": EYLEA_TRIAL, "shipment_id": "REGEN-EYL-2025-004", "origin_facility_id": "FAC-001", "destination_facility_id": "FAC-010", "storage_condition": StorageCondition.REFRIGERATED, "shipper_type": "Qualified passive shipper 48h", "monitoring_device": "TempTale Ultra", "departure_date": now - timedelta(days=3), "arrival_date": None, "transit_duration_hours": None, "min_temp_recorded": 3.5, "max_temp_recorded": 5.0, "excursion_detected": False, "units_shipped": 350, "status": "in_transit", "carrier": "FedEx Custom Critical", "created_at": now - timedelta(days=3)},
            {"id": "SHP-011", "trial_id": DUPIXENT_TRIAL, "shipment_id": "REGEN-DUP-2025-004", "origin_facility_id": "FAC-011", "destination_facility_id": "FAC-006", "storage_condition": StorageCondition.REFRIGERATED, "shipper_type": "Qualified passive shipper 120h", "monitoring_device": "TempTale GEO", "departure_date": now - timedelta(days=2), "arrival_date": None, "transit_duration_hours": None, "min_temp_recorded": None, "max_temp_recorded": None, "excursion_detected": False, "units_shipped": 180, "status": "in_transit", "carrier": "Marken", "created_at": now - timedelta(days=2)},
            {"id": "SHP-012", "trial_id": LIBTAYO_TRIAL, "shipment_id": "REGEN-LIB-2025-004", "origin_facility_id": "FAC-008", "destination_facility_id": "FAC-012", "storage_condition": StorageCondition.REFRIGERATED, "shipper_type": "Active temperature-controlled container", "monitoring_device": "Sensitech ColdStream", "departure_date": now - timedelta(days=1), "arrival_date": None, "transit_duration_hours": None, "min_temp_recorded": None, "max_temp_recorded": None, "excursion_detected": False, "units_shipped": 120, "status": "in_transit", "carrier": "World Courier", "created_at": now - timedelta(days=1)},
        ]

        for s in shipments_data:
            self._shipments[s["id"]] = ColdChainShipment(**s)

    # ------------------------------------------------------------------
    # Storage Facility Management
    # ------------------------------------------------------------------

    def list_facilities(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[StorageFacility]:
        """List storage facilities with optional trial filter."""
        with self._lock:
            result = list(self._facilities.values())

        if trial_id is not None:
            result = [f for f in result if f.trial_id == trial_id]

        return sorted(result, key=lambda f: f.id)

    def get_facility(self, facility_id: str) -> StorageFacility | None:
        """Get a single facility by ID."""
        with self._lock:
            return self._facilities.get(facility_id)

    def create_facility(self, payload: StorageFacilityCreate) -> StorageFacility:
        """Create a new storage facility."""
        now = datetime.now(timezone.utc)
        facility_id = f"FAC-{uuid4().hex[:8].upper()}"
        facility = StorageFacility(
            id=facility_id,
            trial_id=payload.trial_id,
            facility_name=payload.facility_name,
            facility_type=payload.facility_type,
            location=payload.location,
            storage_condition=payload.storage_condition,
            temperature_min=payload.temperature_min,
            temperature_max=payload.temperature_max,
            responsible_person=payload.responsible_person,
            site_id=payload.site_id,
            created_at=now,
        )
        with self._lock:
            self._facilities[facility_id] = facility
        logger.info("Created storage facility %s: %s", facility_id, payload.facility_name)
        return facility

    def update_facility(
        self, facility_id: str, payload: StorageFacilityUpdate
    ) -> StorageFacility | None:
        """Update an existing storage facility."""
        with self._lock:
            existing = self._facilities.get(facility_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = StorageFacility(**data)
            self._facilities[facility_id] = updated
        return updated

    def delete_facility(self, facility_id: str) -> bool:
        """Delete a facility. Returns True if deleted."""
        with self._lock:
            if facility_id in self._facilities:
                del self._facilities[facility_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Monitoring Sensor Management
    # ------------------------------------------------------------------

    def list_sensors(
        self,
        *,
        facility_id: str | None = None,
    ) -> list[MonitoringSensor]:
        """List monitoring sensors with optional facility filter."""
        with self._lock:
            result = list(self._sensors.values())

        if facility_id is not None:
            result = [s for s in result if s.facility_id == facility_id]

        return sorted(result, key=lambda s: s.id)

    def get_sensor(self, sensor_id: str) -> MonitoringSensor | None:
        """Get a single sensor by ID."""
        with self._lock:
            return self._sensors.get(sensor_id)

    def create_sensor(self, payload: MonitoringSensorCreate) -> MonitoringSensor:
        """Create a new monitoring sensor."""
        now = datetime.now(timezone.utc)
        sensor_id = f"SEN-{uuid4().hex[:8].upper()}"
        sensor = MonitoringSensor(
            id=sensor_id,
            facility_id=payload.facility_id,
            sensor_type=payload.sensor_type,
            sensor_serial=payload.sensor_serial,
            location_in_facility=payload.location_in_facility,
            reading_interval_minutes=payload.reading_interval_minutes,
            installed_by=payload.installed_by,
            alert_threshold_low=payload.alert_threshold_low,
            alert_threshold_high=payload.alert_threshold_high,
            installed_date=now,
        )
        with self._lock:
            self._sensors[sensor_id] = sensor
        logger.info("Created sensor %s: %s", sensor_id, payload.sensor_serial)
        return sensor

    def update_sensor(
        self, sensor_id: str, payload: MonitoringSensorUpdate
    ) -> MonitoringSensor | None:
        """Update an existing monitoring sensor."""
        with self._lock:
            existing = self._sensors.get(sensor_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = MonitoringSensor(**data)
            self._sensors[sensor_id] = updated
        return updated

    def delete_sensor(self, sensor_id: str) -> bool:
        """Delete a sensor. Returns True if deleted."""
        with self._lock:
            if sensor_id in self._sensors:
                del self._sensors[sensor_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Temperature Excursion Management
    # ------------------------------------------------------------------

    def list_excursions(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[TemperatureExcursion]:
        """List temperature excursions with optional trial filter."""
        with self._lock:
            result = list(self._excursions.values())

        if trial_id is not None:
            result = [e for e in result if e.trial_id == trial_id]

        return sorted(result, key=lambda e: e.created_at, reverse=True)

    def get_excursion(self, excursion_id: str) -> TemperatureExcursion | None:
        """Get a single excursion by ID."""
        with self._lock:
            return self._excursions.get(excursion_id)

    def create_excursion(self, payload: TemperatureExcursionCreate) -> TemperatureExcursion:
        """Create a new temperature excursion."""
        now = datetime.now(timezone.utc)
        excursion_id = f"EXC-{uuid4().hex[:8].upper()}"
        excursion = TemperatureExcursion(
            id=excursion_id,
            facility_id=payload.facility_id,
            sensor_id=payload.sensor_id,
            trial_id=payload.trial_id,
            severity=payload.severity,
            excursion_start=payload.excursion_start,
            allowed_min=payload.allowed_min,
            allowed_max=payload.allowed_max,
            reported_by=payload.reported_by,
            created_at=now,
        )
        with self._lock:
            self._excursions[excursion_id] = excursion
        logger.info(
            "Created excursion %s: trial=%s severity=%s",
            excursion_id, payload.trial_id, payload.severity.value,
        )
        return excursion

    def update_excursion(
        self, excursion_id: str, payload: TemperatureExcursionUpdate
    ) -> TemperatureExcursion | None:
        """Update an existing temperature excursion."""
        with self._lock:
            existing = self._excursions.get(excursion_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = TemperatureExcursion(**data)
            self._excursions[excursion_id] = updated
        return updated

    def delete_excursion(self, excursion_id: str) -> bool:
        """Delete an excursion. Returns True if deleted."""
        with self._lock:
            if excursion_id in self._excursions:
                del self._excursions[excursion_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Calibration Record Management
    # ------------------------------------------------------------------

    def list_calibrations(
        self,
        *,
        sensor_id: str | None = None,
    ) -> list[CalibrationRecord]:
        """List calibration records with optional sensor filter."""
        with self._lock:
            result = list(self._calibrations.values())

        if sensor_id is not None:
            result = [c for c in result if c.sensor_id == sensor_id]

        return sorted(result, key=lambda c: c.calibration_date, reverse=True)

    def get_calibration(self, calibration_id: str) -> CalibrationRecord | None:
        """Get a single calibration record by ID."""
        with self._lock:
            return self._calibrations.get(calibration_id)

    def create_calibration(self, payload: CalibrationRecordCreate) -> CalibrationRecord:
        """Create a new calibration record."""
        now = datetime.now(timezone.utc)
        calibration_id = f"CAL-{uuid4().hex[:8].upper()}"
        calibration = CalibrationRecord(
            id=calibration_id,
            sensor_id=payload.sensor_id,
            calibration_date=now,
            next_due_date=payload.next_due_date,
            performed_by=payload.performed_by,
            reference_standard=payload.reference_standard,
            passed=payload.passed,
            certificate_number=payload.certificate_number,
        )
        with self._lock:
            self._calibrations[calibration_id] = calibration
        logger.info("Created calibration %s for sensor %s", calibration_id, payload.sensor_id)
        return calibration

    def delete_calibration(self, calibration_id: str) -> bool:
        """Delete a calibration record. Returns True if deleted."""
        with self._lock:
            if calibration_id in self._calibrations:
                del self._calibrations[calibration_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Cold Chain Shipment Management
    # ------------------------------------------------------------------

    def list_shipments(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[ColdChainShipment]:
        """List cold chain shipments with optional trial filter."""
        with self._lock:
            result = list(self._shipments.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]

        return sorted(result, key=lambda s: s.departure_date, reverse=True)

    def get_shipment(self, shipment_id: str) -> ColdChainShipment | None:
        """Get a single shipment by ID."""
        with self._lock:
            return self._shipments.get(shipment_id)

    def create_shipment(self, payload: ColdChainShipmentCreate) -> ColdChainShipment:
        """Create a new cold chain shipment."""
        now = datetime.now(timezone.utc)
        record_id = f"SHP-{uuid4().hex[:8].upper()}"
        shipment = ColdChainShipment(
            id=record_id,
            trial_id=payload.trial_id,
            shipment_id=payload.shipment_id,
            origin_facility_id=payload.origin_facility_id,
            destination_facility_id=payload.destination_facility_id,
            storage_condition=payload.storage_condition,
            shipper_type=payload.shipper_type,
            units_shipped=payload.units_shipped,
            carrier=payload.carrier,
            departure_date=now,
            created_at=now,
        )
        with self._lock:
            self._shipments[record_id] = shipment
        logger.info("Created shipment %s: %s", record_id, payload.shipment_id)
        return shipment

    def update_shipment(
        self, shipment_id: str, payload: ColdChainShipmentUpdate
    ) -> ColdChainShipment | None:
        """Update an existing cold chain shipment."""
        with self._lock:
            existing = self._shipments.get(shipment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ColdChainShipment(**data)
            self._shipments[shipment_id] = updated
        return updated

    def delete_shipment(self, shipment_id: str) -> bool:
        """Delete a shipment. Returns True if deleted."""
        with self._lock:
            if shipment_id in self._shipments:
                del self._shipments[shipment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> EnvironmentalMonitoringMetrics:
        """Compute aggregated environmental monitoring metrics."""
        with self._lock:
            facilities = list(self._facilities.values())
            sensors = list(self._sensors.values())
            excursions = list(self._excursions.values())
            calibrations = list(self._calibrations.values())
            shipments = list(self._shipments.values())

        if trial_id is not None:
            facility_ids = {f.id for f in facilities if f.trial_id == trial_id}
            facilities = [f for f in facilities if f.trial_id == trial_id]
            sensors = [s for s in sensors if s.facility_id in facility_ids]
            sensor_ids = {s.id for s in sensors}
            excursions = [e for e in excursions if e.trial_id == trial_id]
            calibrations = [c for c in calibrations if c.sensor_id in sensor_ids]
            shipments = [s for s in shipments if s.trial_id == trial_id]

        # Facilities by storage condition
        facilities_by_condition: dict[str, int] = {}
        for f in facilities:
            key = f.storage_condition.value
            facilities_by_condition[key] = facilities_by_condition.get(key, 0) + 1

        # Sensors by calibration status
        sensors_by_calibration: dict[str, int] = {}
        for s in sensors:
            key = s.calibration_status.value
            sensors_by_calibration[key] = sensors_by_calibration.get(key, 0) + 1

        # Excursions by severity
        excursions_by_severity: dict[str, int] = {}
        for e in excursions:
            key = e.severity.value
            excursions_by_severity[key] = excursions_by_severity.get(key, 0) + 1

        # Excursions by status
        excursions_by_status: dict[str, int] = {}
        for e in excursions:
            key = e.status.value
            excursions_by_status[key] = excursions_by_status.get(key, 0) + 1

        # Open excursions (not resolved and not product_impacted)
        open_excursions = sum(
            1 for e in excursions
            if e.status not in (ExcursionStatus.RESOLVED, ExcursionStatus.PRODUCT_IMPACTED)
        )

        # Calibrations passed percentage
        if calibrations:
            calibrations_passed_pct = round(
                sum(1 for c in calibrations if c.passed) / len(calibrations) * 100.0, 1
            )
        else:
            calibrations_passed_pct = 0.0

        # Shipments with excursions
        shipments_with_excursions = sum(1 for s in shipments if s.excursion_detected)

        return EnvironmentalMonitoringMetrics(
            total_facilities=len(facilities),
            qualified_facilities=sum(1 for f in facilities if f.qualified),
            facilities_by_condition=facilities_by_condition,
            total_sensors=len(sensors),
            active_sensors=sum(1 for s in sensors if s.active),
            sensors_by_calibration=sensors_by_calibration,
            total_excursions=len(excursions),
            excursions_by_severity=excursions_by_severity,
            excursions_by_status=excursions_by_status,
            open_excursions=open_excursions,
            total_calibrations=len(calibrations),
            calibrations_passed_pct=calibrations_passed_pct,
            total_shipments=len(shipments),
            shipments_with_excursions=shipments_with_excursions,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: EnvironmentalMonitoringService | None = None
_instance_lock = threading.Lock()


def get_environmental_monitoring_service() -> EnvironmentalMonitoringService:
    """Return the singleton EnvironmentalMonitoringService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = EnvironmentalMonitoringService()
    return _instance


def reset_environmental_monitoring_service() -> EnvironmentalMonitoringService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = EnvironmentalMonitoringService()
    return _instance
