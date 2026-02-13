"""Medical Device Tracking Service (MDT-TRK).

Manages medical device tracking operations: device registrations, device
deployment records, maintenance logs, device incident reports, and device
tracking metrics.

Usage:
    from app.services.medical_device_tracking_service import (
        get_medical_device_tracking_service,
    )

    svc = get_medical_device_tracking_service()
    registrations = svc.list_device_registrations()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.medical_device_tracking import (
    DeploymentStatus,
    DeviceClassification,
    DeviceDeployment,
    DeviceDeploymentCreate,
    DeviceDeploymentUpdate,
    DeviceIncidentReport,
    DeviceIncidentReportCreate,
    DeviceIncidentReportUpdate,
    DeviceRegistration,
    DeviceRegistrationCreate,
    DeviceRegistrationUpdate,
    IncidentSeverity,
    MaintenanceLog,
    MaintenanceLogCreate,
    MaintenanceLogUpdate,
    MaintenanceResult,
    MaintenanceType,
    MedicalDeviceTrackingMetrics,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class MedicalDeviceTrackingService:
    """In-memory Medical Device Tracking engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._device_registrations: dict[str, DeviceRegistration] = {}
        self._device_deployments: dict[str, DeviceDeployment] = {}
        self._maintenance_logs: dict[str, MaintenanceLog] = {}
        self._device_incident_reports: dict[str, DeviceIncidentReport] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic medical device tracking data."""
        now = datetime.now(timezone.utc)

        # --- 12 Device Registrations ---
        registrations_data = [
            {
                "id": "DEV-001",
                "trial_id": EYLEA_TRIAL,
                "device_name": "Retinal OCT Scanner Pro",
                "manufacturer": "Heidelberg Engineering",
                "model_number": "SPECTRALIS-HRA2",
                "serial_number": "HE-2024-00142",
                "device_classification": DeviceClassification.CLASS_II,
                "udi_number": "(01)00884838000125(17)261231(10)HRA2-001",
                "firmware_version": "6.16.4",
                "calibration_due_date": now + timedelta(days=90),
                "regulatory_approval_id": "K212345",
                "purchase_date": now - timedelta(days=365),
                "warranty_expiry": now + timedelta(days=365),
                "registered_by": "Biomedical Engineer Sarah Chen",
                "notes": "Primary OCT scanner for EYLEA intravitreal injection monitoring.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "DEV-002",
                "trial_id": EYLEA_TRIAL,
                "device_name": "Visual Acuity Chart System",
                "manufacturer": "Precision Vision",
                "model_number": "ETDRS-2000",
                "serial_number": "PV-2024-00089",
                "device_classification": DeviceClassification.CLASS_I,
                "udi_number": "(01)00850003000211(17)271231(10)ETDRS-002",
                "firmware_version": "3.2.1",
                "calibration_due_date": now + timedelta(days=180),
                "regulatory_approval_id": "K201234",
                "purchase_date": now - timedelta(days=200),
                "warranty_expiry": now + timedelta(days=530),
                "registered_by": "Biomedical Engineer Sarah Chen",
                "notes": "ETDRS chart system for standardized visual acuity measurement.",
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "DEV-003",
                "trial_id": EYLEA_TRIAL,
                "device_name": "Fundus Camera",
                "manufacturer": "Topcon Medical",
                "model_number": "TRC-NW400",
                "serial_number": "TM-2024-00563",
                "device_classification": DeviceClassification.CLASS_II,
                "udi_number": "(01)00753456000312(17)271231(10)NW400-003",
                "firmware_version": "2.8.0",
                "calibration_due_date": now + timedelta(days=45),
                "regulatory_approval_id": "K213456",
                "purchase_date": now - timedelta(days=300),
                "warranty_expiry": now + timedelta(days=65),
                "registered_by": "Biomedical Engineer Mark Torres",
                "notes": "Non-mydriatic fundus camera for retinal imaging. Warranty expiring soon.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "DEV-004",
                "trial_id": EYLEA_TRIAL,
                "device_name": "Intraocular Pressure Tonometer",
                "manufacturer": "Reichert Technologies",
                "model_number": "TONO-PEN-AVIA",
                "serial_number": "RT-2024-00891",
                "device_classification": DeviceClassification.CLASS_II,
                "udi_number": "(01)00881234000445(17)261231(10)TPA-004",
                "firmware_version": "4.1.2",
                "calibration_due_date": now - timedelta(days=15),
                "regulatory_approval_id": "K214567",
                "purchase_date": now - timedelta(days=180),
                "warranty_expiry": now + timedelta(days=550),
                "registered_by": "Biomedical Engineer Mark Torres",
                "notes": "Calibration overdue. Temporary replacement unit deployed.",
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "DEV-005",
                "trial_id": DUPIXENT_TRIAL,
                "device_name": "Dermatology Imaging System",
                "manufacturer": "Canfield Scientific",
                "model_number": "VISIA-CR",
                "serial_number": "CS-2024-01234",
                "device_classification": DeviceClassification.CLASS_I,
                "udi_number": "(01)00867890000556(17)271231(10)VISIA-005",
                "firmware_version": "8.3.0",
                "calibration_due_date": now + timedelta(days=120),
                "regulatory_approval_id": "K215678",
                "purchase_date": now - timedelta(days=150),
                "warranty_expiry": now + timedelta(days=580),
                "registered_by": "Biomedical Engineer Lisa Park",
                "notes": "Standardized skin imaging for atopic dermatitis severity scoring.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "DEV-006",
                "trial_id": DUPIXENT_TRIAL,
                "device_name": "SCORAD Assessment Tablet",
                "manufacturer": "Samsung Medical",
                "model_number": "GALAXY-TAB-S9-MED",
                "serial_number": "SM-2024-02345",
                "device_classification": DeviceClassification.CLASS_I,
                "udi_number": None,
                "firmware_version": "Android 14.0 / ClinApp 2.1",
                "calibration_due_date": None,
                "regulatory_approval_id": None,
                "purchase_date": now - timedelta(days=90),
                "warranty_expiry": now + timedelta(days=640),
                "registered_by": "Biomedical Engineer Lisa Park",
                "notes": "Tablet preloaded with validated SCORAD assessment application.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "DEV-007",
                "trial_id": DUPIXENT_TRIAL,
                "device_name": "Spirometer",
                "manufacturer": "ndd Medical Technologies",
                "model_number": "EASYONE-AIR",
                "serial_number": "NDD-2024-03456",
                "device_classification": DeviceClassification.CLASS_II,
                "udi_number": "(01)00891234000778(17)271231(10)EOA-007",
                "firmware_version": "5.2.3",
                "calibration_due_date": now + timedelta(days=30),
                "regulatory_approval_id": "K216789",
                "purchase_date": now - timedelta(days=120),
                "warranty_expiry": now + timedelta(days=610),
                "registered_by": "Biomedical Engineer Lisa Park",
                "notes": "For pulmonary function monitoring in asthma comorbidity subjects.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "DEV-008",
                "trial_id": DUPIXENT_TRIAL,
                "device_name": "Digital Skin pH Meter",
                "manufacturer": "Courage+Khazaka",
                "model_number": "SKIN-PH-900",
                "serial_number": "CK-2024-04567",
                "device_classification": DeviceClassification.INVESTIGATIONAL,
                "udi_number": None,
                "firmware_version": "1.4.0",
                "calibration_due_date": now + timedelta(days=60),
                "regulatory_approval_id": "IDE-G240001",
                "purchase_date": now - timedelta(days=60),
                "warranty_expiry": now + timedelta(days=670),
                "registered_by": "Biomedical Engineer Lisa Park",
                "notes": "Investigational device for skin barrier function assessment sub-study.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "DEV-009",
                "trial_id": LIBTAYO_TRIAL,
                "device_name": "CT Scanner",
                "manufacturer": "Siemens Healthineers",
                "model_number": "SOMATOM-FORCE",
                "serial_number": "SH-2024-05678",
                "device_classification": DeviceClassification.CLASS_III,
                "udi_number": "(01)00901234000889(17)271231(10)SF-009",
                "firmware_version": "VA50A",
                "calibration_due_date": now + timedelta(days=150),
                "regulatory_approval_id": "P150039",
                "purchase_date": now - timedelta(days=500),
                "warranty_expiry": now + timedelta(days=230),
                "registered_by": "Biomedical Engineer David Kim",
                "notes": "Primary CT scanner for tumor response assessment per RECIST 1.1.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "DEV-010",
                "trial_id": LIBTAYO_TRIAL,
                "device_name": "Infusion Pump System",
                "manufacturer": "B. Braun Medical",
                "model_number": "INFUSOMAT-SPACE",
                "serial_number": "BB-2024-06789",
                "device_classification": DeviceClassification.CLASS_II,
                "udi_number": "(01)00912345000990(17)261231(10)IS-010",
                "firmware_version": "689G",
                "calibration_due_date": now + timedelta(days=75),
                "regulatory_approval_id": "K217890",
                "purchase_date": now - timedelta(days=200),
                "warranty_expiry": now + timedelta(days=530),
                "registered_by": "Biomedical Engineer David Kim",
                "notes": "Programmable infusion pump for cemiplimab IV administration.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "DEV-011",
                "trial_id": LIBTAYO_TRIAL,
                "device_name": "ECG Monitor",
                "manufacturer": "GE HealthCare",
                "model_number": "MAC-5500-HD",
                "serial_number": "GE-2024-07890",
                "device_classification": DeviceClassification.CLASS_II,
                "udi_number": "(01)00923456001101(17)271231(10)M55-011",
                "firmware_version": "11.0.2",
                "calibration_due_date": now + timedelta(days=200),
                "regulatory_approval_id": "K218901",
                "purchase_date": now - timedelta(days=250),
                "warranty_expiry": now + timedelta(days=480),
                "registered_by": "Biomedical Engineer David Kim",
                "notes": "12-lead ECG for cardiac safety monitoring during immunotherapy.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "DEV-012",
                "trial_id": LIBTAYO_TRIAL,
                "device_name": "Vital Signs Monitor",
                "manufacturer": "Philips Healthcare",
                "model_number": "INTELLIVUE-MX450",
                "serial_number": "PH-2024-08901",
                "device_classification": DeviceClassification.CLASS_II,
                "udi_number": "(01)00934567001212(17)271231(10)MX-012",
                "firmware_version": "M.02.03",
                "calibration_due_date": now + timedelta(days=100),
                "regulatory_approval_id": "K219012",
                "purchase_date": now - timedelta(days=180),
                "warranty_expiry": now + timedelta(days=550),
                "registered_by": "Biomedical Engineer David Kim",
                "notes": "Multi-parameter vital signs monitor for infusion suite.",
                "created_at": now - timedelta(days=70),
            },
        ]

        for r in registrations_data:
            self._device_registrations[r["id"]] = DeviceRegistration(**r)

        # --- 12 Device Deployments ---
        deployments_data = [
            {
                "id": "DDP-001",
                "trial_id": EYLEA_TRIAL,
                "device_id": "DEV-001",
                "site_id": "SITE-NY-001",
                "deployment_status": DeploymentStatus.DEPLOYED,
                "deployed_date": now - timedelta(days=110),
                "returned_date": None,
                "assigned_to": "Dr. Patricia Wells",
                "location_description": "Ophthalmology Clinic, Room 204",
                "subjects_using": 12,
                "condition_on_deploy": "New - factory sealed",
                "condition_on_return": None,
                "shipped_by": "Biomedical Engineer Sarah Chen",
                "tracking_number": "WC-DEV-2025-001",
                "notes": "Primary OCT scanner deployed to NY site. Operating within specifications.",
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "DDP-002",
                "trial_id": EYLEA_TRIAL,
                "device_id": "DEV-002",
                "site_id": "SITE-NY-001",
                "deployment_status": DeploymentStatus.DEPLOYED,
                "deployed_date": now - timedelta(days=105),
                "returned_date": None,
                "assigned_to": "Dr. Patricia Wells",
                "location_description": "Ophthalmology Clinic, Exam Room 1",
                "subjects_using": 12,
                "condition_on_deploy": "New - calibrated on site",
                "condition_on_return": None,
                "shipped_by": "Biomedical Engineer Sarah Chen",
                "tracking_number": "WC-DEV-2025-002",
                "notes": "ETDRS chart system installed and validated.",
                "created_at": now - timedelta(days=105),
            },
            {
                "id": "DDP-003",
                "trial_id": EYLEA_TRIAL,
                "device_id": "DEV-003",
                "site_id": "SITE-LA-001",
                "deployment_status": DeploymentStatus.DEPLOYED,
                "deployed_date": now - timedelta(days=95),
                "returned_date": None,
                "assigned_to": "Dr. James Rodriguez",
                "location_description": "Retina Center, Imaging Suite",
                "subjects_using": 8,
                "condition_on_deploy": "Refurbished - certified",
                "condition_on_return": None,
                "shipped_by": "Biomedical Engineer Mark Torres",
                "tracking_number": "MK-DEV-2025-003",
                "notes": "Fundus camera deployed to LA site. Warranty expiring soon - monitor closely.",
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "DDP-004",
                "trial_id": EYLEA_TRIAL,
                "device_id": "DEV-004",
                "site_id": "SITE-NY-001",
                "deployment_status": DeploymentStatus.QUARANTINED,
                "deployed_date": now - timedelta(days=90),
                "returned_date": None,
                "assigned_to": "Dr. Patricia Wells",
                "location_description": "Biomedical Engineering - Quarantine Storage",
                "subjects_using": 0,
                "condition_on_deploy": "New",
                "condition_on_return": None,
                "shipped_by": "Biomedical Engineer Mark Torres",
                "tracking_number": "WC-DEV-2025-004",
                "notes": "Quarantined due to overdue calibration. Replacement unit in use.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "DDP-005",
                "trial_id": DUPIXENT_TRIAL,
                "device_id": "DEV-005",
                "site_id": "SITE-CHI-001",
                "deployment_status": DeploymentStatus.DEPLOYED,
                "deployed_date": now - timedelta(days=80),
                "returned_date": None,
                "assigned_to": "Dr. Karen Liu",
                "location_description": "Dermatology Research Center, Studio A",
                "subjects_using": 15,
                "condition_on_deploy": "New - factory calibrated",
                "condition_on_return": None,
                "shipped_by": "Biomedical Engineer Lisa Park",
                "tracking_number": "FX-DEV-2025-005",
                "notes": "Imaging system operational. High subject throughput.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "DDP-006",
                "trial_id": DUPIXENT_TRIAL,
                "device_id": "DEV-006",
                "site_id": "SITE-CHI-001",
                "deployment_status": DeploymentStatus.DEPLOYED,
                "deployed_date": now - timedelta(days=75),
                "returned_date": None,
                "assigned_to": "CRC Michelle Torres",
                "location_description": "Dermatology Research Center, Assessment Room 2",
                "subjects_using": 15,
                "condition_on_deploy": "New",
                "condition_on_return": None,
                "shipped_by": "Biomedical Engineer Lisa Park",
                "tracking_number": "FX-DEV-2025-006",
                "notes": "SCORAD tablet in daily use. Battery health 98%.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "DDP-007",
                "trial_id": DUPIXENT_TRIAL,
                "device_id": "DEV-007",
                "site_id": "SITE-BOS-001",
                "deployment_status": DeploymentStatus.IN_TRANSIT,
                "deployed_date": None,
                "returned_date": None,
                "assigned_to": None,
                "location_description": None,
                "subjects_using": 0,
                "condition_on_deploy": None,
                "condition_on_return": None,
                "shipped_by": "Biomedical Engineer Lisa Park",
                "tracking_number": "MK-DEV-2025-007",
                "notes": "Spirometer in transit to Boston site. Expected delivery in 2 days.",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "DDP-008",
                "trial_id": DUPIXENT_TRIAL,
                "device_id": "DEV-008",
                "site_id": "SITE-CHI-001",
                "deployment_status": DeploymentStatus.RETURNED,
                "deployed_date": now - timedelta(days=50),
                "returned_date": now - timedelta(days=10),
                "assigned_to": "Dr. Michael Torres",
                "location_description": "Central Device Warehouse",
                "subjects_using": 0,
                "condition_on_deploy": "New - investigational",
                "condition_on_return": "Functional - software update required",
                "shipped_by": "Biomedical Engineer Lisa Park",
                "tracking_number": "FX-DEV-2025-008",
                "notes": "Returned for mandatory firmware update. Re-deployment after validation.",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "DDP-009",
                "trial_id": LIBTAYO_TRIAL,
                "device_id": "DEV-009",
                "site_id": "SITE-HOU-001",
                "deployment_status": DeploymentStatus.DEPLOYED,
                "deployed_date": now - timedelta(days=85),
                "returned_date": None,
                "assigned_to": "Dr. Angela Martinez",
                "location_description": "Oncology Center, Radiology Suite 3",
                "subjects_using": 20,
                "condition_on_deploy": "Existing - site-owned",
                "condition_on_return": None,
                "shipped_by": None,
                "tracking_number": None,
                "notes": "Site-owned CT scanner qualified for trial use per imaging charter.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "DDP-010",
                "trial_id": LIBTAYO_TRIAL,
                "device_id": "DEV-010",
                "site_id": "SITE-HOU-001",
                "deployment_status": DeploymentStatus.DEPLOYED,
                "deployed_date": now - timedelta(days=80),
                "returned_date": None,
                "assigned_to": "Nurse David Park",
                "location_description": "Infusion Suite, Bay 4",
                "subjects_using": 10,
                "condition_on_deploy": "New - verified",
                "condition_on_return": None,
                "shipped_by": "Biomedical Engineer David Kim",
                "tracking_number": "MK-DEV-2025-010",
                "notes": "Infusion pump dedicated to cemiplimab administration.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "DDP-011",
                "trial_id": LIBTAYO_TRIAL,
                "device_id": "DEV-011",
                "site_id": "SITE-SEA-001",
                "deployment_status": DeploymentStatus.IN_STORAGE,
                "deployed_date": None,
                "returned_date": None,
                "assigned_to": None,
                "location_description": "Seattle Site - Equipment Storage Room B",
                "subjects_using": 0,
                "condition_on_deploy": None,
                "condition_on_return": None,
                "shipped_by": "Biomedical Engineer David Kim",
                "tracking_number": "FX-DEV-2025-011",
                "notes": "Awaiting site initiation visit before deployment.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "DDP-012",
                "trial_id": LIBTAYO_TRIAL,
                "device_id": "DEV-012",
                "site_id": "SITE-HOU-001",
                "deployment_status": DeploymentStatus.DECOMMISSIONED,
                "deployed_date": now - timedelta(days=170),
                "returned_date": now - timedelta(days=20),
                "assigned_to": "Nurse David Park",
                "location_description": "Biomedical Engineering - Decommissioned Storage",
                "subjects_using": 0,
                "condition_on_deploy": "Refurbished",
                "condition_on_return": "End of service life - battery failure",
                "shipped_by": "Biomedical Engineer David Kim",
                "tracking_number": "MK-DEV-2025-012",
                "notes": "Decommissioned due to battery module failure. Replacement unit ordered.",
                "created_at": now - timedelta(days=170),
            },
        ]

        for d in deployments_data:
            self._device_deployments[d["id"]] = DeviceDeployment(**d)

        # --- 12 Maintenance Logs ---
        maintenance_data = [
            {
                "id": "MNT-001",
                "trial_id": EYLEA_TRIAL,
                "device_id": "DEV-001",
                "maintenance_type": MaintenanceType.CALIBRATION,
                "maintenance_result": MaintenanceResult.PASS,
                "scheduled_date": now - timedelta(days=90),
                "completed_date": now - timedelta(days=89),
                "performed_by": "Biomedical Engineer Sarah Chen",
                "service_provider": "Heidelberg Engineering Service",
                "parts_replaced": None,
                "downtime_hours": 4.0,
                "next_maintenance_date": now + timedelta(days=90),
                "cost_usd": 1200.00,
                "certificate_id": "CAL-HE-2025-001",
                "notes": "Annual calibration completed. All parameters within specification.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "MNT-002",
                "trial_id": EYLEA_TRIAL,
                "device_id": "DEV-002",
                "maintenance_type": MaintenanceType.PREVENTIVE,
                "maintenance_result": MaintenanceResult.PASS,
                "scheduled_date": now - timedelta(days=60),
                "completed_date": now - timedelta(days=60),
                "performed_by": "Biomedical Engineer Mark Torres",
                "service_provider": None,
                "parts_replaced": "LED panel backlight",
                "downtime_hours": 2.0,
                "next_maintenance_date": now + timedelta(days=120),
                "cost_usd": 350.00,
                "certificate_id": "PM-PV-2025-002",
                "notes": "Preventive maintenance. Replaced aging LED backlight per schedule.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "MNT-003",
                "trial_id": EYLEA_TRIAL,
                "device_id": "DEV-003",
                "maintenance_type": MaintenanceType.CORRECTIVE,
                "maintenance_result": MaintenanceResult.CONDITIONAL,
                "scheduled_date": now - timedelta(days=40),
                "completed_date": now - timedelta(days=38),
                "performed_by": "Biomedical Engineer Mark Torres",
                "service_provider": "Topcon Authorized Service",
                "parts_replaced": "Flash capacitor assembly",
                "downtime_hours": 16.0,
                "next_maintenance_date": now + timedelta(days=30),
                "cost_usd": 2800.00,
                "certificate_id": "CM-TM-2025-003",
                "notes": "Flash unit intermittent failure. Capacitor replaced. Conditional pass - recheck at 30 days.",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "MNT-004",
                "trial_id": EYLEA_TRIAL,
                "device_id": "DEV-004",
                "maintenance_type": MaintenanceType.CALIBRATION,
                "maintenance_result": MaintenanceResult.FAIL,
                "scheduled_date": now - timedelta(days=15),
                "completed_date": now - timedelta(days=14),
                "performed_by": "Biomedical Engineer Mark Torres",
                "service_provider": "Reichert Technologies Service",
                "parts_replaced": None,
                "downtime_hours": 3.0,
                "next_maintenance_date": now + timedelta(days=7),
                "cost_usd": 800.00,
                "certificate_id": None,
                "notes": "Calibration failed. Pressure readings 3mmHg above reference. Device quarantined pending repair.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "MNT-005",
                "trial_id": DUPIXENT_TRIAL,
                "device_id": "DEV-005",
                "maintenance_type": MaintenanceType.CALIBRATION,
                "maintenance_result": MaintenanceResult.PASS,
                "scheduled_date": now - timedelta(days=50),
                "completed_date": now - timedelta(days=50),
                "performed_by": "Biomedical Engineer Lisa Park",
                "service_provider": "Canfield Scientific Service",
                "parts_replaced": None,
                "downtime_hours": 3.0,
                "next_maintenance_date": now + timedelta(days=120),
                "cost_usd": 950.00,
                "certificate_id": "CAL-CS-2025-005",
                "notes": "Color calibration and light source verification. All within tolerance.",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "MNT-006",
                "trial_id": DUPIXENT_TRIAL,
                "device_id": "DEV-006",
                "maintenance_type": MaintenanceType.SOFTWARE_UPDATE,
                "maintenance_result": MaintenanceResult.PASS,
                "scheduled_date": now - timedelta(days=30),
                "completed_date": now - timedelta(days=30),
                "performed_by": "IT Support Alex Yun",
                "service_provider": None,
                "parts_replaced": None,
                "downtime_hours": 1.5,
                "next_maintenance_date": now + timedelta(days=90),
                "cost_usd": 0.00,
                "certificate_id": "SW-SM-2025-006",
                "notes": "ClinApp updated to v2.1.3. Security patches and scoring algorithm update.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "MNT-007",
                "trial_id": DUPIXENT_TRIAL,
                "device_id": "DEV-007",
                "maintenance_type": MaintenanceType.INSPECTION,
                "maintenance_result": MaintenanceResult.PASS,
                "scheduled_date": now - timedelta(days=20),
                "completed_date": now - timedelta(days=20),
                "performed_by": "Biomedical Engineer Lisa Park",
                "service_provider": None,
                "parts_replaced": None,
                "downtime_hours": 1.0,
                "next_maintenance_date": now + timedelta(days=160),
                "cost_usd": 0.00,
                "certificate_id": "INS-NDD-2025-007",
                "notes": "Pre-deployment inspection. Flow sensor and turbine verified.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "MNT-008",
                "trial_id": DUPIXENT_TRIAL,
                "device_id": "DEV-008",
                "maintenance_type": MaintenanceType.SOFTWARE_UPDATE,
                "maintenance_result": MaintenanceResult.PENDING,
                "scheduled_date": now + timedelta(days=5),
                "completed_date": None,
                "performed_by": "Biomedical Engineer Lisa Park",
                "service_provider": "Courage+Khazaka Service",
                "parts_replaced": None,
                "downtime_hours": 0.0,
                "next_maintenance_date": None,
                "cost_usd": 0.00,
                "certificate_id": None,
                "notes": "Firmware update v1.5.0 scheduled. Device returned from site for update.",
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "MNT-009",
                "trial_id": LIBTAYO_TRIAL,
                "device_id": "DEV-009",
                "maintenance_type": MaintenanceType.PREVENTIVE,
                "maintenance_result": MaintenanceResult.PASS,
                "scheduled_date": now - timedelta(days=45),
                "completed_date": now - timedelta(days=44),
                "performed_by": "Siemens Field Service Engineer",
                "service_provider": "Siemens Healthineers Service",
                "parts_replaced": "X-ray tube cooling fan",
                "downtime_hours": 8.0,
                "next_maintenance_date": now + timedelta(days=135),
                "cost_usd": 4500.00,
                "certificate_id": "PM-SH-2025-009",
                "notes": "Scheduled PM. Replaced cooling fan as preventive measure. All systems nominal.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "MNT-010",
                "trial_id": LIBTAYO_TRIAL,
                "device_id": "DEV-010",
                "maintenance_type": MaintenanceType.CALIBRATION,
                "maintenance_result": MaintenanceResult.PASS,
                "scheduled_date": now - timedelta(days=35),
                "completed_date": now - timedelta(days=35),
                "performed_by": "Biomedical Engineer David Kim",
                "service_provider": None,
                "parts_replaced": None,
                "downtime_hours": 2.0,
                "next_maintenance_date": now + timedelta(days=145),
                "cost_usd": 200.00,
                "certificate_id": "CAL-BB-2025-010",
                "notes": "Flow rate calibration verified across all channels. Within 2% tolerance.",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "MNT-011",
                "trial_id": LIBTAYO_TRIAL,
                "device_id": "DEV-011",
                "maintenance_type": MaintenanceType.INSPECTION,
                "maintenance_result": MaintenanceResult.PASS,
                "scheduled_date": now - timedelta(days=25),
                "completed_date": now - timedelta(days=25),
                "performed_by": "Biomedical Engineer David Kim",
                "service_provider": None,
                "parts_replaced": None,
                "downtime_hours": 1.0,
                "next_maintenance_date": now + timedelta(days=155),
                "cost_usd": 0.00,
                "certificate_id": "INS-GE-2025-011",
                "notes": "Pre-storage inspection. Device tested and packaged per manufacturer guidelines.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "MNT-012",
                "trial_id": LIBTAYO_TRIAL,
                "device_id": "DEV-012",
                "maintenance_type": MaintenanceType.EMERGENCY,
                "maintenance_result": MaintenanceResult.FAIL,
                "scheduled_date": now - timedelta(days=22),
                "completed_date": now - timedelta(days=21),
                "performed_by": "Biomedical Engineer David Kim",
                "service_provider": "Philips Healthcare Service",
                "parts_replaced": None,
                "downtime_hours": 12.0,
                "next_maintenance_date": None,
                "cost_usd": 1500.00,
                "certificate_id": None,
                "notes": "Emergency service call for battery failure. Battery module not repairable. Device decommissioned.",
                "created_at": now - timedelta(days=22),
            },
        ]

        for m in maintenance_data:
            self._maintenance_logs[m["id"]] = MaintenanceLog(**m)

        # --- 12 Device Incident Reports ---
        incidents_data = [
            {
                "id": "DIR-001",
                "trial_id": EYLEA_TRIAL,
                "device_id": "DEV-001",
                "site_id": "SITE-NY-001",
                "incident_severity": IncidentSeverity.MINOR,
                "incident_date": now - timedelta(days=60),
                "description": "OCT scanner displayed intermittent 'lens alignment' error during subject scan. Resolved after device restart.",
                "subject_affected": "SUBJ-E001",
                "patient_harm": False,
                "root_cause": "Transient software glitch in alignment module",
                "corrective_action": "Software restart protocol documented. Firmware update scheduled.",
                "regulatory_reported": False,
                "regulatory_report_date": None,
                "mdr_report_number": None,
                "reported_by": "CRC Jennifer Adams",
                "investigated_by": "Biomedical Engineer Sarah Chen",
                "resolution_date": now - timedelta(days=58),
                "notes": "No impact on image quality. Subject scan completed successfully after restart.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "DIR-002",
                "trial_id": EYLEA_TRIAL,
                "device_id": "DEV-003",
                "site_id": "SITE-LA-001",
                "incident_severity": IncidentSeverity.MODERATE,
                "incident_date": now - timedelta(days=42),
                "description": "Fundus camera flash unit failed during imaging session. Unable to complete required retinal photographs for visit.",
                "subject_affected": "SUBJ-E003",
                "patient_harm": False,
                "root_cause": "Flash capacitor degradation beyond operational threshold",
                "corrective_action": "Capacitor assembly replaced. Corrective maintenance MNT-003 performed.",
                "regulatory_reported": False,
                "regulatory_report_date": None,
                "mdr_report_number": None,
                "reported_by": "CRC Robert Kim",
                "investigated_by": "Biomedical Engineer Mark Torres",
                "resolution_date": now - timedelta(days=38),
                "notes": "Subject rescheduled within protocol window. No data loss.",
                "created_at": now - timedelta(days=42),
            },
            {
                "id": "DIR-003",
                "trial_id": EYLEA_TRIAL,
                "device_id": "DEV-004",
                "site_id": "SITE-NY-001",
                "incident_severity": IncidentSeverity.SERIOUS,
                "incident_date": now - timedelta(days=16),
                "description": "Tonometer provided intraocular pressure readings 3mmHg above reference standard during calibration verification.",
                "subject_affected": None,
                "patient_harm": False,
                "root_cause": "Sensor drift exceeding acceptable tolerance after extended use",
                "corrective_action": "Device quarantined immediately. All IOP readings from last 30 days flagged for re-evaluation. Replacement device deployed.",
                "regulatory_reported": True,
                "regulatory_report_date": now - timedelta(days=14),
                "mdr_report_number": "MDR-2025-NY-00342",
                "reported_by": "Biomedical Engineer Mark Torres",
                "investigated_by": "Quality Assurance Director Dr. Elena Voss",
                "resolution_date": None,
                "notes": "Investigation ongoing. Reviewing all affected subject IOP measurements. No treatment decisions were based solely on IOP readings.",
                "created_at": now - timedelta(days=16),
            },
            {
                "id": "DIR-004",
                "trial_id": EYLEA_TRIAL,
                "device_id": "DEV-002",
                "site_id": "SITE-NY-001",
                "incident_severity": IncidentSeverity.NEAR_MISS,
                "incident_date": now - timedelta(days=35),
                "description": "Visual acuity chart system found displaying incorrect letter size for 20/40 line during morning QC check.",
                "subject_affected": None,
                "patient_harm": False,
                "root_cause": "Display calibration file corrupted during power surge",
                "corrective_action": "Display recalibrated. UPS installed for power protection. QC checklist enhanced.",
                "regulatory_reported": False,
                "regulatory_report_date": None,
                "mdr_report_number": None,
                "reported_by": "Ophthalmic Technician Amy Wong",
                "investigated_by": "Biomedical Engineer Sarah Chen",
                "resolution_date": now - timedelta(days=33),
                "notes": "Caught during routine morning QC. No subjects tested with incorrect calibration.",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "DIR-005",
                "trial_id": DUPIXENT_TRIAL,
                "device_id": "DEV-005",
                "site_id": "SITE-CHI-001",
                "incident_severity": IncidentSeverity.MINOR,
                "incident_date": now - timedelta(days=28),
                "description": "Dermatology imaging system produced slightly overexposed images for 3 subjects due to ambient light sensor malfunction.",
                "subject_affected": "SUBJ-D002",
                "patient_harm": False,
                "root_cause": "Ambient light sensor contaminated with cleaning solution residue",
                "corrective_action": "Sensor cleaned per manufacturer protocol. Cleaning SOP updated to avoid sensor area.",
                "regulatory_reported": False,
                "regulatory_report_date": None,
                "mdr_report_number": None,
                "reported_by": "CRC Michelle Torres",
                "investigated_by": "Biomedical Engineer Lisa Park",
                "resolution_date": now - timedelta(days=26),
                "notes": "Affected images were retaken. No impact on SCORAD assessments.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "DIR-006",
                "trial_id": DUPIXENT_TRIAL,
                "device_id": "DEV-006",
                "site_id": "SITE-CHI-001",
                "incident_severity": IncidentSeverity.INFORMATIONAL,
                "incident_date": now - timedelta(days=20),
                "description": "SCORAD tablet application crashed during assessment entry. Data was auto-saved and recovered after app restart.",
                "subject_affected": "SUBJ-D001",
                "patient_harm": False,
                "root_cause": "Memory leak in ClinApp v2.1.2 when processing large image attachments",
                "corrective_action": "ClinApp updated to v2.1.3 which includes memory management fix.",
                "regulatory_reported": False,
                "regulatory_report_date": None,
                "mdr_report_number": None,
                "reported_by": "CRC Michelle Torres",
                "investigated_by": "IT Support Alex Yun",
                "resolution_date": now - timedelta(days=18),
                "notes": "No data loss. Assessment completed after app restart.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "DIR-007",
                "trial_id": DUPIXENT_TRIAL,
                "device_id": "DEV-008",
                "site_id": "SITE-CHI-001",
                "incident_severity": IncidentSeverity.MODERATE,
                "incident_date": now - timedelta(days=12),
                "description": "Investigational skin pH meter provided inconsistent readings across repeated measurements on same anatomical site.",
                "subject_affected": "SUBJ-D003",
                "patient_harm": False,
                "root_cause": "Firmware bug in averaging algorithm for rapid sequential readings",
                "corrective_action": "Device returned for firmware update. Sub-study measurements suspended until device revalidated.",
                "regulatory_reported": True,
                "regulatory_report_date": now - timedelta(days=10),
                "mdr_report_number": "IDE-EVT-2025-001",
                "reported_by": "Dr. Michael Torres",
                "investigated_by": "Biomedical Engineer Lisa Park",
                "resolution_date": None,
                "notes": "IDE event report filed. Sponsor notified. Awaiting firmware fix from manufacturer.",
                "created_at": now - timedelta(days=12),
            },
            {
                "id": "DIR-008",
                "trial_id": DUPIXENT_TRIAL,
                "device_id": "DEV-007",
                "site_id": "SITE-BOS-001",
                "incident_severity": IncidentSeverity.NEAR_MISS,
                "incident_date": now - timedelta(days=8),
                "description": "Spirometer shipped without turbine flow sensor attached. Discovered during receiving inspection at Boston site.",
                "subject_affected": None,
                "patient_harm": False,
                "root_cause": "Incomplete packing checklist at shipping facility",
                "corrective_action": "Turbine sensor shipped separately via overnight courier. Packing checklist updated with mandatory photo documentation.",
                "regulatory_reported": False,
                "regulatory_report_date": None,
                "mdr_report_number": None,
                "reported_by": "CRC Alex Yun",
                "investigated_by": "Biomedical Engineer Lisa Park",
                "resolution_date": now - timedelta(days=6),
                "notes": "No patient impact. Sensor received and installed before first use.",
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "DIR-009",
                "trial_id": LIBTAYO_TRIAL,
                "device_id": "DEV-010",
                "site_id": "SITE-HOU-001",
                "incident_severity": IncidentSeverity.SERIOUS,
                "incident_date": now - timedelta(days=30),
                "description": "Infusion pump alarmed with occlusion error mid-infusion. Infusion interrupted for 15 minutes during cemiplimab administration.",
                "subject_affected": "SUBJ-L001",
                "patient_harm": False,
                "root_cause": "Kinked IV tubing at pump clamp point",
                "corrective_action": "Tubing repositioned, infusion resumed. Nursing re-educated on tubing routing. New tubing sets with anti-kink design ordered.",
                "regulatory_reported": True,
                "regulatory_report_date": now - timedelta(days=28),
                "mdr_report_number": "MDR-2025-HOU-00156",
                "reported_by": "Nurse David Park",
                "investigated_by": "Biomedical Engineer David Kim",
                "resolution_date": now - timedelta(days=27),
                "notes": "Subject tolerated interruption well. Full dose administered. No adverse events reported.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "DIR-010",
                "trial_id": LIBTAYO_TRIAL,
                "device_id": "DEV-009",
                "site_id": "SITE-HOU-001",
                "incident_severity": IncidentSeverity.MINOR,
                "incident_date": now - timedelta(days=18),
                "description": "CT scanner produced motion artifact on initial scan. Repeat scan required, resulting in additional radiation exposure.",
                "subject_affected": "SUBJ-L002",
                "patient_harm": False,
                "root_cause": "Subject movement during breath-hold. No device malfunction.",
                "corrective_action": "Additional coaching for breath-hold technique. Not a device issue.",
                "regulatory_reported": False,
                "regulatory_report_date": None,
                "mdr_report_number": None,
                "reported_by": "Radiology Technician Maria Santos",
                "investigated_by": "Biomedical Engineer David Kim",
                "resolution_date": now - timedelta(days=18),
                "notes": "Additional radiation dose within protocol-defined limits. Documented per IRB requirements.",
                "created_at": now - timedelta(days=18),
            },
            {
                "id": "DIR-011",
                "trial_id": LIBTAYO_TRIAL,
                "device_id": "DEV-012",
                "site_id": "SITE-HOU-001",
                "incident_severity": IncidentSeverity.CRITICAL,
                "incident_date": now - timedelta(days=22),
                "description": "Vital signs monitor displayed erratic blood pressure readings during post-infusion monitoring. Values fluctuated 40mmHg within seconds.",
                "subject_affected": "SUBJ-L003",
                "patient_harm": False,
                "root_cause": "Internal battery module failure causing intermittent power fluctuations to sensor circuitry",
                "corrective_action": "Device immediately replaced. Subject vitals manually confirmed stable. Device sent for root cause analysis. All subjects previously monitored with this device reviewed.",
                "regulatory_reported": True,
                "regulatory_report_date": now - timedelta(days=20),
                "mdr_report_number": "MDR-2025-HOU-00163",
                "reported_by": "Nurse David Park",
                "investigated_by": "Quality Assurance Director Dr. Grace Lee",
                "resolution_date": now - timedelta(days=15),
                "notes": "No actual patient harm. Erratic readings immediately recognized by nursing staff. Manual vitals confirmed stable. Device decommissioned.",
                "created_at": now - timedelta(days=22),
            },
            {
                "id": "DIR-012",
                "trial_id": LIBTAYO_TRIAL,
                "device_id": "DEV-011",
                "site_id": "SITE-SEA-001",
                "incident_severity": IncidentSeverity.INFORMATIONAL,
                "incident_date": now - timedelta(days=5),
                "description": "ECG monitor firmware update notification received from manufacturer. Current version approaching end-of-support date.",
                "subject_affected": None,
                "patient_harm": False,
                "root_cause": None,
                "corrective_action": "Firmware update scheduled before deployment. Added to site initiation checklist.",
                "regulatory_reported": False,
                "regulatory_report_date": None,
                "mdr_report_number": None,
                "reported_by": "Biomedical Engineer David Kim",
                "investigated_by": None,
                "resolution_date": None,
                "notes": "Proactive tracking. No current impact as device is in storage pending site initiation.",
                "created_at": now - timedelta(days=5),
            },
        ]

        for inc in incidents_data:
            self._device_incident_reports[inc["id"]] = DeviceIncidentReport(**inc)

    # ------------------------------------------------------------------
    # Device Registrations
    # ------------------------------------------------------------------

    def list_device_registrations(
        self,
        *,
        trial_id: str | None = None,
        device_classification: DeviceClassification | None = None,
    ) -> list[DeviceRegistration]:
        """List device registrations with optional filters."""
        with self._lock:
            result = list(self._device_registrations.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if device_classification is not None:
            result = [r for r in result if r.device_classification == device_classification]

        return sorted(result, key=lambda r: r.created_at, reverse=True)

    def get_device_registration(self, registration_id: str) -> DeviceRegistration | None:
        """Get a single device registration by ID."""
        with self._lock:
            return self._device_registrations.get(registration_id)

    def create_device_registration(self, payload: DeviceRegistrationCreate) -> DeviceRegistration:
        """Create a new device registration."""
        now = datetime.now(timezone.utc)
        registration_id = f"DEV-{uuid4().hex[:8].upper()}"
        record = DeviceRegistration(
            id=registration_id,
            trial_id=payload.trial_id,
            device_name=payload.device_name,
            manufacturer=payload.manufacturer,
            model_number=payload.model_number,
            serial_number=payload.serial_number,
            device_classification=payload.device_classification,
            udi_number=None,
            firmware_version=None,
            calibration_due_date=None,
            regulatory_approval_id=None,
            purchase_date=None,
            warranty_expiry=None,
            registered_by=payload.registered_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._device_registrations[registration_id] = record
        logger.info("Created device registration %s for trial %s", registration_id, payload.trial_id)
        return record

    def update_device_registration(
        self, registration_id: str, payload: DeviceRegistrationUpdate
    ) -> DeviceRegistration | None:
        """Update an existing device registration."""
        with self._lock:
            existing = self._device_registrations.get(registration_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DeviceRegistration(**data)
            self._device_registrations[registration_id] = updated
        return updated

    def delete_device_registration(self, registration_id: str) -> bool:
        """Delete a device registration. Returns True if deleted."""
        with self._lock:
            if registration_id in self._device_registrations:
                del self._device_registrations[registration_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Device Deployments
    # ------------------------------------------------------------------

    def list_device_deployments(
        self,
        *,
        trial_id: str | None = None,
        deployment_status: DeploymentStatus | None = None,
        site_id: str | None = None,
    ) -> list[DeviceDeployment]:
        """List device deployments with optional filters."""
        with self._lock:
            result = list(self._device_deployments.values())

        if trial_id is not None:
            result = [d for d in result if d.trial_id == trial_id]
        if deployment_status is not None:
            result = [d for d in result if d.deployment_status == deployment_status]
        if site_id is not None:
            result = [d for d in result if d.site_id == site_id]

        return sorted(result, key=lambda d: d.created_at, reverse=True)

    def get_device_deployment(self, deployment_id: str) -> DeviceDeployment | None:
        """Get a single device deployment by ID."""
        with self._lock:
            return self._device_deployments.get(deployment_id)

    def create_device_deployment(self, payload: DeviceDeploymentCreate) -> DeviceDeployment:
        """Create a new device deployment."""
        now = datetime.now(timezone.utc)
        deployment_id = f"DDP-{uuid4().hex[:8].upper()}"
        record = DeviceDeployment(
            id=deployment_id,
            trial_id=payload.trial_id,
            device_id=payload.device_id,
            site_id=payload.site_id,
            deployment_status=payload.deployment_status,
            deployed_date=None,
            returned_date=None,
            assigned_to=None,
            location_description=None,
            subjects_using=0,
            condition_on_deploy=None,
            condition_on_return=None,
            shipped_by=None,
            tracking_number=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._device_deployments[deployment_id] = record
        logger.info("Created device deployment %s for trial %s", deployment_id, payload.trial_id)
        return record

    def update_device_deployment(
        self, deployment_id: str, payload: DeviceDeploymentUpdate
    ) -> DeviceDeployment | None:
        """Update an existing device deployment."""
        with self._lock:
            existing = self._device_deployments.get(deployment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DeviceDeployment(**data)
            self._device_deployments[deployment_id] = updated
        return updated

    def delete_device_deployment(self, deployment_id: str) -> bool:
        """Delete a device deployment. Returns True if deleted."""
        with self._lock:
            if deployment_id in self._device_deployments:
                del self._device_deployments[deployment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Maintenance Logs
    # ------------------------------------------------------------------

    def list_maintenance_logs(
        self,
        *,
        trial_id: str | None = None,
        maintenance_type: MaintenanceType | None = None,
        maintenance_result: MaintenanceResult | None = None,
    ) -> list[MaintenanceLog]:
        """List maintenance logs with optional filters."""
        with self._lock:
            result = list(self._maintenance_logs.values())

        if trial_id is not None:
            result = [m for m in result if m.trial_id == trial_id]
        if maintenance_type is not None:
            result = [m for m in result if m.maintenance_type == maintenance_type]
        if maintenance_result is not None:
            result = [m for m in result if m.maintenance_result == maintenance_result]

        return sorted(result, key=lambda m: m.scheduled_date, reverse=True)

    def get_maintenance_log(self, maintenance_id: str) -> MaintenanceLog | None:
        """Get a single maintenance log by ID."""
        with self._lock:
            return self._maintenance_logs.get(maintenance_id)

    def create_maintenance_log(self, payload: MaintenanceLogCreate) -> MaintenanceLog:
        """Create a new maintenance log."""
        now = datetime.now(timezone.utc)
        maintenance_id = f"MNT-{uuid4().hex[:8].upper()}"
        record = MaintenanceLog(
            id=maintenance_id,
            trial_id=payload.trial_id,
            device_id=payload.device_id,
            maintenance_type=payload.maintenance_type,
            maintenance_result=MaintenanceResult.PENDING,
            scheduled_date=payload.scheduled_date,
            completed_date=None,
            performed_by=payload.performed_by,
            service_provider=None,
            parts_replaced=None,
            downtime_hours=0.0,
            next_maintenance_date=None,
            cost_usd=0.0,
            certificate_id=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._maintenance_logs[maintenance_id] = record
        logger.info("Created maintenance log %s for device %s", maintenance_id, payload.device_id)
        return record

    def update_maintenance_log(
        self, maintenance_id: str, payload: MaintenanceLogUpdate
    ) -> MaintenanceLog | None:
        """Update an existing maintenance log."""
        with self._lock:
            existing = self._maintenance_logs.get(maintenance_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = MaintenanceLog(**data)
            self._maintenance_logs[maintenance_id] = updated
        return updated

    def delete_maintenance_log(self, maintenance_id: str) -> bool:
        """Delete a maintenance log. Returns True if deleted."""
        with self._lock:
            if maintenance_id in self._maintenance_logs:
                del self._maintenance_logs[maintenance_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Device Incident Reports
    # ------------------------------------------------------------------

    def list_device_incident_reports(
        self,
        *,
        trial_id: str | None = None,
        incident_severity: IncidentSeverity | None = None,
        site_id: str | None = None,
    ) -> list[DeviceIncidentReport]:
        """List device incident reports with optional filters."""
        with self._lock:
            result = list(self._device_incident_reports.values())

        if trial_id is not None:
            result = [i for i in result if i.trial_id == trial_id]
        if incident_severity is not None:
            result = [i for i in result if i.incident_severity == incident_severity]
        if site_id is not None:
            result = [i for i in result if i.site_id == site_id]

        return sorted(result, key=lambda i: i.incident_date, reverse=True)

    def get_device_incident_report(self, incident_id: str) -> DeviceIncidentReport | None:
        """Get a single device incident report by ID."""
        with self._lock:
            return self._device_incident_reports.get(incident_id)

    def create_device_incident_report(self, payload: DeviceIncidentReportCreate) -> DeviceIncidentReport:
        """Create a new device incident report."""
        now = datetime.now(timezone.utc)
        incident_id = f"DIR-{uuid4().hex[:8].upper()}"
        record = DeviceIncidentReport(
            id=incident_id,
            trial_id=payload.trial_id,
            device_id=payload.device_id,
            site_id=payload.site_id,
            incident_severity=payload.incident_severity,
            incident_date=payload.incident_date,
            description=payload.description,
            subject_affected=None,
            patient_harm=False,
            root_cause=None,
            corrective_action=None,
            regulatory_reported=False,
            regulatory_report_date=None,
            mdr_report_number=None,
            reported_by=payload.reported_by,
            investigated_by=None,
            resolution_date=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._device_incident_reports[incident_id] = record
        logger.info("Created device incident report %s for device %s", incident_id, payload.device_id)
        return record

    def update_device_incident_report(
        self, incident_id: str, payload: DeviceIncidentReportUpdate
    ) -> DeviceIncidentReport | None:
        """Update an existing device incident report."""
        with self._lock:
            existing = self._device_incident_reports.get(incident_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DeviceIncidentReport(**data)
            self._device_incident_reports[incident_id] = updated
        return updated

    def delete_device_incident_report(self, incident_id: str) -> bool:
        """Delete a device incident report. Returns True if deleted."""
        with self._lock:
            if incident_id in self._device_incident_reports:
                del self._device_incident_reports[incident_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> MedicalDeviceTrackingMetrics:
        """Compute aggregated medical device tracking metrics."""
        with self._lock:
            registrations = list(self._device_registrations.values())
            deployments = list(self._device_deployments.values())
            maintenance = list(self._maintenance_logs.values())
            incidents = list(self._device_incident_reports.values())

        # Devices by classification
        devices_by_classification: dict[str, int] = {}
        for r in registrations:
            key = r.device_classification.value
            devices_by_classification[key] = devices_by_classification.get(key, 0) + 1

        # Deployments by status
        deployments_by_status: dict[str, int] = {}
        for d in deployments:
            key = d.deployment_status.value
            deployments_by_status[key] = deployments_by_status.get(key, 0) + 1

        # Maintenance by type
        maintenance_by_type: dict[str, int] = {}
        for m in maintenance:
            key = m.maintenance_type.value
            maintenance_by_type[key] = maintenance_by_type.get(key, 0) + 1

        # Maintenance pass rate
        mnt_tested = [m for m in maintenance if m.maintenance_result != MaintenanceResult.PENDING]
        mnt_pass_count = sum(1 for m in mnt_tested if m.maintenance_result == MaintenanceResult.PASS)
        maintenance_pass_rate = round(
            (mnt_pass_count / max(1, len(mnt_tested))) * 100, 1
        )

        # Incidents by severity
        incidents_by_severity: dict[str, int] = {}
        for i in incidents:
            key = i.incident_severity.value
            incidents_by_severity[key] = incidents_by_severity.get(key, 0) + 1

        # Patient harm rate
        harm_count = sum(1 for i in incidents if i.patient_harm)
        patient_harm_rate = round(
            (harm_count / max(1, len(incidents))) * 100, 1
        )

        return MedicalDeviceTrackingMetrics(
            total_devices=len(registrations),
            devices_by_classification=devices_by_classification,
            total_deployments=len(deployments),
            deployments_by_status=deployments_by_status,
            total_maintenance_logs=len(maintenance),
            maintenance_by_type=maintenance_by_type,
            maintenance_pass_rate=maintenance_pass_rate,
            total_incidents=len(incidents),
            incidents_by_severity=incidents_by_severity,
            patient_harm_rate=patient_harm_rate,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: MedicalDeviceTrackingService | None = None
_instance_lock = threading.Lock()


def get_medical_device_tracking_service() -> MedicalDeviceTrackingService:
    """Return the singleton MedicalDeviceTrackingService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = MedicalDeviceTrackingService()
    return _instance


def reset_medical_device_tracking_service() -> MedicalDeviceTrackingService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = MedicalDeviceTrackingService()
    return _instance
