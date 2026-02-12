"""Decentralized Trial Operations (DCT-OPS) Service.

Manages decentralized/hybrid trial components: remote visit scheduling,
wearable device management, telemedicine sessions, eSource data capture,
and DCT operational metrics.

Usage:
    from app.services.decentralized_trials_service import (
        get_decentralized_trials_service,
    )

    svc = get_decentralized_trials_service()
    visits = svc.list_visits()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.decentralized_trials import (
    DataQuality,
    DeviceStatus,
    DeviceType,
    ESourceCapture,
    ESourceCaptureCreate,
    ESourceCaptureUpdate,
    DecentralizedTrialMetrics,
    RemoteVisit,
    RemoteVisitCreate,
    RemoteVisitUpdate,
    SessionPlatform,
    TelemedicineSession,
    TelemedicineSessionCreate,
    TelemedicineSessionUpdate,
    VisitStatus,
    VisitType,
    WearableDevice,
    WearableDeviceCreate,
    WearableDeviceUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class DecentralizedTrialsService:
    """In-memory Decentralized Trial Operations engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._visits: dict[str, RemoteVisit] = {}
        self._devices: dict[str, WearableDevice] = {}
        self._sessions: dict[str, TelemedicineSession] = {}
        self._esource: dict[str, ESourceCapture] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic DCT data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Remote Visits ---
        visits_data = [
            {
                "id": "RV-001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1001",
                "site_id": "SITE-101",
                "visit_type": VisitType.HOME_NURSING,
                "scheduled_date": now - timedelta(days=30),
                "actual_date": now - timedelta(days=30),
                "status": VisitStatus.COMPLETED,
                "provider_name": "Maria Rodriguez, RN",
                "provider_organization": "NovaCare Home Health",
                "procedures": ["vitals", "blood_draw", "injection_administration"],
                "location_address": "123 Main St, Houston, TX 77001",
                "duration_minutes": 45,
                "notes": "Patient tolerated injection well. All samples collected.",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "RV-002",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1001",
                "site_id": "SITE-101",
                "visit_type": VisitType.TELEMEDICINE,
                "scheduled_date": now - timedelta(days=14),
                "actual_date": now - timedelta(days=14),
                "status": VisitStatus.COMPLETED,
                "provider_name": "Dr. James Chen",
                "provider_organization": "Memorial Hermann Hospital",
                "procedures": ["symptom_assessment", "medication_review"],
                "location_address": None,
                "duration_minutes": 25,
                "notes": "Follow-up telemedicine visit. No adverse events reported.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "RV-003",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2001",
                "site_id": "SITE-103",
                "visit_type": VisitType.LOCAL_LAB,
                "scheduled_date": now - timedelta(days=21),
                "actual_date": now - timedelta(days=20),
                "status": VisitStatus.COMPLETED,
                "provider_name": "Quest Diagnostics",
                "provider_organization": "Quest Diagnostics",
                "procedures": ["CBC", "CMP", "IgE_levels"],
                "location_address": "456 Oak Ave, Cleveland, OH 44101",
                "duration_minutes": 30,
                "notes": "All labs drawn successfully. Results pending.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "RV-004",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2002",
                "site_id": "SITE-103",
                "visit_type": VisitType.HOME_NURSING,
                "scheduled_date": now - timedelta(days=10),
                "actual_date": now - timedelta(days=10),
                "status": VisitStatus.COMPLETED,
                "provider_name": "Sarah Johnson, RN",
                "provider_organization": "Bayada Home Health",
                "procedures": ["vitals", "skin_assessment", "injection_training"],
                "location_address": "789 Elm St, Cleveland, OH 44102",
                "duration_minutes": 60,
                "notes": "Patient trained on self-injection technique.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "RV-005",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3001",
                "site_id": "SITE-105",
                "visit_type": VisitType.LOCAL_IMAGING,
                "scheduled_date": now - timedelta(days=7),
                "actual_date": now - timedelta(days=7),
                "status": VisitStatus.COMPLETED,
                "provider_name": "RadNet Imaging",
                "provider_organization": "RadNet Inc.",
                "procedures": ["CT_scan_chest", "CT_scan_abdomen"],
                "location_address": "321 Pine Rd, Durham, NC 27701",
                "duration_minutes": 90,
                "notes": "CT scans completed. Images uploaded to central imaging core.",
                "created_at": now - timedelta(days=14),
            },
            {
                "id": "RV-006",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1002",
                "site_id": "SITE-102",
                "visit_type": VisitType.MOBILE_UNIT,
                "scheduled_date": now - timedelta(days=5),
                "actual_date": now - timedelta(days=5),
                "status": VisitStatus.COMPLETED,
                "provider_name": "Regeneron Mobile Research Unit",
                "provider_organization": "Regeneron Pharmaceuticals",
                "procedures": ["OCT_scan", "visual_acuity", "IOP_measurement"],
                "location_address": "555 River Rd, Jacksonville, FL 32099",
                "duration_minutes": 75,
                "notes": "Full ophthalmic assessment completed via mobile unit.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "RV-007",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3002",
                "site_id": "SITE-106",
                "visit_type": VisitType.SELF_ADMINISTERED,
                "scheduled_date": now - timedelta(days=3),
                "actual_date": now - timedelta(days=3),
                "status": VisitStatus.COMPLETED,
                "provider_name": None,
                "provider_organization": None,
                "procedures": ["ePRO_completion", "photo_capture"],
                "location_address": None,
                "duration_minutes": 15,
                "notes": "Patient completed ePRO questionnaires and photo diary.",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "RV-008",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2003",
                "site_id": "SITE-104",
                "visit_type": VisitType.HOME_NURSING,
                "scheduled_date": now + timedelta(days=3),
                "actual_date": None,
                "status": VisitStatus.SCHEDULED,
                "provider_name": "Emily Davis, RN",
                "provider_organization": "Amedisys Home Health",
                "procedures": ["vitals", "blood_draw", "skin_assessment"],
                "location_address": "222 Maple Dr, Rochester, MN 55901",
                "duration_minutes": None,
                "notes": None,
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "RV-009",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1003",
                "site_id": "SITE-101",
                "visit_type": VisitType.TELEMEDICINE,
                "scheduled_date": now + timedelta(days=7),
                "actual_date": None,
                "status": VisitStatus.CONFIRMED,
                "provider_name": "Dr. James Chen",
                "provider_organization": "Memorial Hermann Hospital",
                "procedures": ["symptom_assessment", "AE_review"],
                "location_address": None,
                "duration_minutes": None,
                "notes": None,
                "created_at": now - timedelta(days=2),
            },
            {
                "id": "RV-010",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3003",
                "site_id": "SITE-107",
                "visit_type": VisitType.LOCAL_LAB,
                "scheduled_date": now + timedelta(days=14),
                "actual_date": None,
                "status": VisitStatus.SCHEDULED,
                "provider_name": "LabCorp",
                "provider_organization": "Laboratory Corporation of America",
                "procedures": ["CBC", "LFT", "tumor_markers"],
                "location_address": "888 Health Blvd, Boston, MA 02101",
                "duration_minutes": None,
                "notes": None,
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "RV-011",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2001",
                "site_id": "SITE-103",
                "visit_type": VisitType.TELEMEDICINE,
                "scheduled_date": now - timedelta(days=2),
                "actual_date": None,
                "status": VisitStatus.CANCELLED,
                "provider_name": "Dr. Lisa Park",
                "provider_organization": "Cleveland Clinic",
                "procedures": ["follow_up"],
                "location_address": None,
                "duration_minutes": None,
                "notes": "Patient requested reschedule due to conflict.",
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "RV-012",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1004",
                "site_id": "SITE-108",
                "visit_type": VisitType.HOME_NURSING,
                "scheduled_date": now - timedelta(days=1),
                "actual_date": None,
                "status": VisitStatus.NO_SHOW,
                "provider_name": "Tom Wilson, RN",
                "provider_organization": "Kindred at Home",
                "procedures": ["vitals", "injection_administration"],
                "location_address": "999 Stanford Ave, Palo Alto, CA 94301",
                "duration_minutes": None,
                "notes": "Patient not home at scheduled time. Rescheduling required.",
                "created_at": now - timedelta(days=5),
            },
        ]

        for v in visits_data:
            self._visits[v["id"]] = RemoteVisit(**v)

        # --- 12 Wearable Devices ---
        devices_data = [
            {
                "id": "DEV-001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1001",
                "device_type": DeviceType.BLOOD_PRESSURE,
                "manufacturer": "Omron",
                "model": "Evolv BP7000",
                "serial_number": "OMR-BP-2025-001",
                "firmware_version": "3.2.1",
                "status": DeviceStatus.COLLECTING_DATA,
                "activation_date": now - timedelta(days=60),
                "last_sync_date": now - timedelta(hours=6),
                "data_points_collected": 1842,
                "battery_level_pct": 78.5,
                "data_quality": DataQuality.EXCELLENT,
                "compliance_rate_pct": 95.2,
                "assigned_date": now - timedelta(days=65),
            },
            {
                "id": "DEV-002",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1001",
                "device_type": DeviceType.ACTIVITY_TRACKER,
                "manufacturer": "Fitbit",
                "model": "Charge 6",
                "serial_number": "FB-CH6-2025-001",
                "firmware_version": "2.1.0",
                "status": DeviceStatus.COLLECTING_DATA,
                "activation_date": now - timedelta(days=60),
                "last_sync_date": now - timedelta(hours=2),
                "data_points_collected": 43200,
                "battery_level_pct": 62.0,
                "data_quality": DataQuality.GOOD,
                "compliance_rate_pct": 88.7,
                "assigned_date": now - timedelta(days=65),
            },
            {
                "id": "DEV-003",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2001",
                "device_type": DeviceType.SMARTWATCH,
                "manufacturer": "Apple",
                "model": "Watch Series 10",
                "serial_number": "APL-AW10-2025-001",
                "firmware_version": "11.2.0",
                "status": DeviceStatus.COLLECTING_DATA,
                "activation_date": now - timedelta(days=45),
                "last_sync_date": now - timedelta(hours=1),
                "data_points_collected": 28800,
                "battery_level_pct": 85.0,
                "data_quality": DataQuality.EXCELLENT,
                "compliance_rate_pct": 97.1,
                "assigned_date": now - timedelta(days=50),
            },
            {
                "id": "DEV-004",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2002",
                "device_type": DeviceType.PULSE_OXIMETER,
                "manufacturer": "Masimo",
                "model": "MightySat Rx",
                "serial_number": "MAS-MS-2025-001",
                "firmware_version": "4.0.2",
                "status": DeviceStatus.COLLECTING_DATA,
                "activation_date": now - timedelta(days=30),
                "last_sync_date": now - timedelta(hours=12),
                "data_points_collected": 7200,
                "battery_level_pct": 45.0,
                "data_quality": DataQuality.GOOD,
                "compliance_rate_pct": 82.3,
                "assigned_date": now - timedelta(days=35),
            },
            {
                "id": "DEV-005",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3001",
                "device_type": DeviceType.ECG_PATCH,
                "manufacturer": "iRhythm",
                "model": "Zio XT",
                "serial_number": "IRH-ZIO-2025-001",
                "firmware_version": "5.1.0",
                "status": DeviceStatus.COLLECTING_DATA,
                "activation_date": now - timedelta(days=12),
                "last_sync_date": now - timedelta(hours=4),
                "data_points_collected": 172800,
                "battery_level_pct": 55.0,
                "data_quality": DataQuality.EXCELLENT,
                "compliance_rate_pct": 99.5,
                "assigned_date": now - timedelta(days=14),
            },
            {
                "id": "DEV-006",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3002",
                "device_type": DeviceType.SCALE,
                "manufacturer": "Withings",
                "model": "Body+ Smart Scale",
                "serial_number": "WTH-BP-2025-001",
                "firmware_version": "2.3.4",
                "status": DeviceStatus.COLLECTING_DATA,
                "activation_date": now - timedelta(days=20),
                "last_sync_date": now - timedelta(days=1),
                "data_points_collected": 40,
                "battery_level_pct": 92.0,
                "data_quality": DataQuality.GOOD,
                "compliance_rate_pct": 71.4,
                "assigned_date": now - timedelta(days=25),
            },
            {
                "id": "DEV-007",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1002",
                "device_type": DeviceType.CONTINUOUS_GLUCOSE,
                "manufacturer": "Dexcom",
                "model": "G7",
                "serial_number": "DXC-G7-2025-001",
                "firmware_version": "1.8.2",
                "status": DeviceStatus.ACTIVATED,
                "activation_date": now - timedelta(days=2),
                "last_sync_date": now - timedelta(hours=8),
                "data_points_collected": 576,
                "battery_level_pct": 95.0,
                "data_quality": DataQuality.ACCEPTABLE,
                "compliance_rate_pct": 100.0,
                "assigned_date": now - timedelta(days=5),
            },
            {
                "id": "DEV-008",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2003",
                "device_type": DeviceType.SPIROMETER,
                "manufacturer": "NuvoAir",
                "model": "Air Next",
                "serial_number": "NVA-AN-2025-001",
                "firmware_version": "3.0.1",
                "status": DeviceStatus.SHIPPED,
                "activation_date": None,
                "last_sync_date": None,
                "data_points_collected": 0,
                "battery_level_pct": None,
                "data_quality": None,
                "compliance_rate_pct": None,
                "assigned_date": now - timedelta(days=3),
            },
            {
                "id": "DEV-009",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3003",
                "device_type": DeviceType.THERMOMETER,
                "manufacturer": "Kinsa",
                "model": "QuickCare",
                "serial_number": "KNS-QC-2025-001",
                "firmware_version": "2.0.0",
                "status": DeviceStatus.PROVISIONED,
                "activation_date": None,
                "last_sync_date": None,
                "data_points_collected": 0,
                "battery_level_pct": None,
                "data_quality": None,
                "compliance_rate_pct": None,
                "assigned_date": now - timedelta(days=1),
            },
            {
                "id": "DEV-010",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1004",
                "device_type": DeviceType.BLOOD_PRESSURE,
                "manufacturer": "Omron",
                "model": "Evolv BP7000",
                "serial_number": "OMR-BP-2025-002",
                "firmware_version": "3.2.1",
                "status": DeviceStatus.DEACTIVATED,
                "activation_date": now - timedelta(days=90),
                "last_sync_date": now - timedelta(days=30),
                "data_points_collected": 5400,
                "battery_level_pct": 12.0,
                "data_quality": DataQuality.POOR,
                "compliance_rate_pct": 45.2,
                "assigned_date": now - timedelta(days=95),
            },
            {
                "id": "DEV-011",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2004",
                "device_type": DeviceType.ACTIVITY_TRACKER,
                "manufacturer": "Garmin",
                "model": "Vivosmart 5",
                "serial_number": "GAR-VS5-2025-001",
                "firmware_version": "7.10",
                "status": DeviceStatus.RETURNED,
                "activation_date": now - timedelta(days=120),
                "last_sync_date": now - timedelta(days=15),
                "data_points_collected": 75600,
                "battery_level_pct": None,
                "data_quality": DataQuality.GOOD,
                "compliance_rate_pct": 79.8,
                "assigned_date": now - timedelta(days=125),
            },
            {
                "id": "DEV-012",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3004",
                "device_type": DeviceType.ECG_PATCH,
                "manufacturer": "BioTelemetry",
                "model": "MCOT Patch",
                "serial_number": "BIO-MC-2025-001",
                "firmware_version": "6.0.3",
                "status": DeviceStatus.MALFUNCTIONING,
                "activation_date": now - timedelta(days=8),
                "last_sync_date": now - timedelta(days=3),
                "data_points_collected": 43200,
                "battery_level_pct": 5.0,
                "data_quality": DataQuality.UNUSABLE,
                "compliance_rate_pct": 60.0,
                "assigned_date": now - timedelta(days=10),
            },
        ]

        for d in devices_data:
            self._devices[d["id"]] = WearableDevice(**d)

        # --- 12 Telemedicine Sessions ---
        sessions_data = [
            {
                "id": "TMS-001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1001",
                "visit_id": "RV-002",
                "platform": SessionPlatform.ZOOM_HEALTHCARE,
                "scheduled_date": now - timedelta(days=14),
                "actual_start": now - timedelta(days=14, hours=-9),
                "actual_end": now - timedelta(days=14, hours=-9) + timedelta(minutes=25),
                "duration_minutes": 25,
                "provider_name": "Dr. James Chen",
                "provider_role": "Principal Investigator",
                "status": VisitStatus.COMPLETED,
                "recording_available": True,
                "consent_documented": True,
                "connection_quality": DataQuality.EXCELLENT,
                "clinical_notes": "Patient reports stable vision. No new floaters or flashes.",
            },
            {
                "id": "TMS-002",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2001",
                "visit_id": None,
                "platform": SessionPlatform.DOXY_ME,
                "scheduled_date": now - timedelta(days=10),
                "actual_start": now - timedelta(days=10, hours=-10),
                "actual_end": now - timedelta(days=10, hours=-10) + timedelta(minutes=35),
                "duration_minutes": 35,
                "provider_name": "Dr. Lisa Park",
                "provider_role": "Sub-Investigator",
                "status": VisitStatus.COMPLETED,
                "recording_available": False,
                "consent_documented": True,
                "connection_quality": DataQuality.GOOD,
                "clinical_notes": "Eczema improvement noted. EASI score decreased from 22 to 14.",
            },
            {
                "id": "TMS-003",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3001",
                "visit_id": None,
                "platform": SessionPlatform.TEAMS,
                "scheduled_date": now - timedelta(days=7),
                "actual_start": now - timedelta(days=7, hours=-14),
                "actual_end": now - timedelta(days=7, hours=-14) + timedelta(minutes=40),
                "duration_minutes": 40,
                "provider_name": "Dr. Robert Williams",
                "provider_role": "Oncologist",
                "status": VisitStatus.COMPLETED,
                "recording_available": True,
                "consent_documented": True,
                "connection_quality": DataQuality.GOOD,
                "clinical_notes": "Tumor response assessment discussed. Patient tolerating treatment.",
            },
            {
                "id": "TMS-004",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1002",
                "visit_id": None,
                "platform": SessionPlatform.ZOOM_HEALTHCARE,
                "scheduled_date": now - timedelta(days=5),
                "actual_start": now - timedelta(days=5, hours=-11),
                "actual_end": now - timedelta(days=5, hours=-11) + timedelta(minutes=20),
                "duration_minutes": 20,
                "provider_name": "Dr. James Chen",
                "provider_role": "Principal Investigator",
                "status": VisitStatus.COMPLETED,
                "recording_available": True,
                "consent_documented": True,
                "connection_quality": DataQuality.ACCEPTABLE,
                "clinical_notes": "Brief check-in. Patient reports mild injection site discomfort.",
            },
            {
                "id": "TMS-005",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2002",
                "visit_id": None,
                "platform": SessionPlatform.PHONE_CALL,
                "scheduled_date": now - timedelta(days=3),
                "actual_start": now - timedelta(days=3, hours=-15),
                "actual_end": now - timedelta(days=3, hours=-15) + timedelta(minutes=15),
                "duration_minutes": 15,
                "provider_name": "Sarah Johnson, RN",
                "provider_role": "Study Coordinator",
                "status": VisitStatus.COMPLETED,
                "recording_available": False,
                "consent_documented": True,
                "connection_quality": DataQuality.GOOD,
                "clinical_notes": "Phone follow-up on self-injection technique. Patient confident.",
            },
            {
                "id": "TMS-006",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3002",
                "visit_id": None,
                "platform": SessionPlatform.CUSTOM_PLATFORM,
                "scheduled_date": now - timedelta(days=2),
                "actual_start": now - timedelta(days=2, hours=-13),
                "actual_end": now - timedelta(days=2, hours=-13) + timedelta(minutes=30),
                "duration_minutes": 30,
                "provider_name": "Dr. Amanda Foster",
                "provider_role": "Dermatologist",
                "status": VisitStatus.COMPLETED,
                "recording_available": True,
                "consent_documented": True,
                "connection_quality": DataQuality.EXCELLENT,
                "clinical_notes": "Skin lesion photo review via custom platform. Stable disease.",
            },
            {
                "id": "TMS-007",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1003",
                "visit_id": "RV-009",
                "platform": SessionPlatform.ZOOM_HEALTHCARE,
                "scheduled_date": now + timedelta(days=7),
                "actual_start": None,
                "actual_end": None,
                "duration_minutes": None,
                "provider_name": "Dr. James Chen",
                "provider_role": "Principal Investigator",
                "status": VisitStatus.CONFIRMED,
                "recording_available": False,
                "consent_documented": False,
                "connection_quality": None,
                "clinical_notes": None,
            },
            {
                "id": "TMS-008",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2003",
                "visit_id": None,
                "platform": SessionPlatform.DOXY_ME,
                "scheduled_date": now + timedelta(days=10),
                "actual_start": None,
                "actual_end": None,
                "duration_minutes": None,
                "provider_name": "Dr. Lisa Park",
                "provider_role": "Sub-Investigator",
                "status": VisitStatus.SCHEDULED,
                "recording_available": False,
                "consent_documented": False,
                "connection_quality": None,
                "clinical_notes": None,
            },
            {
                "id": "TMS-009",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3003",
                "visit_id": None,
                "platform": SessionPlatform.TEAMS,
                "scheduled_date": now + timedelta(days=14),
                "actual_start": None,
                "actual_end": None,
                "duration_minutes": None,
                "provider_name": "Dr. Robert Williams",
                "provider_role": "Oncologist",
                "status": VisitStatus.SCHEDULED,
                "recording_available": False,
                "consent_documented": False,
                "connection_quality": None,
                "clinical_notes": None,
            },
            {
                "id": "TMS-010",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1004",
                "visit_id": None,
                "platform": SessionPlatform.ZOOM_HEALTHCARE,
                "scheduled_date": now - timedelta(days=1),
                "actual_start": None,
                "actual_end": None,
                "duration_minutes": None,
                "provider_name": "Dr. James Chen",
                "provider_role": "Principal Investigator",
                "status": VisitStatus.NO_SHOW,
                "recording_available": False,
                "consent_documented": False,
                "connection_quality": None,
                "clinical_notes": "Patient did not join session. Will attempt reschedule.",
            },
            {
                "id": "TMS-011",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2004",
                "visit_id": None,
                "platform": SessionPlatform.DOXY_ME,
                "scheduled_date": now - timedelta(days=4),
                "actual_start": now - timedelta(days=4, hours=-10),
                "actual_end": None,
                "duration_minutes": None,
                "provider_name": "Dr. Lisa Park",
                "provider_role": "Sub-Investigator",
                "status": VisitStatus.CANCELLED,
                "recording_available": False,
                "consent_documented": False,
                "connection_quality": DataQuality.POOR,
                "clinical_notes": "Session cancelled due to poor connection quality.",
            },
            {
                "id": "TMS-012",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3004",
                "visit_id": None,
                "platform": SessionPlatform.PHONE_CALL,
                "scheduled_date": now - timedelta(days=6),
                "actual_start": now - timedelta(days=6, hours=-9),
                "actual_end": now - timedelta(days=6, hours=-9) + timedelta(minutes=10),
                "duration_minutes": 10,
                "provider_name": "Emily Watson, RN",
                "provider_role": "Study Coordinator",
                "status": VisitStatus.COMPLETED,
                "recording_available": False,
                "consent_documented": True,
                "connection_quality": DataQuality.GOOD,
                "clinical_notes": "Brief safety check. No new AEs. Device issue reported.",
            },
        ]

        for s in sessions_data:
            self._sessions[s["id"]] = TelemedicineSession(**s)

        # --- 12 eSource Captures ---
        esource_data = [
            {
                "id": "ESC-001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1001",
                "visit_id": "RV-001",
                "device_id": "DEV-001",
                "data_type": "blood_pressure",
                "capture_date": now - timedelta(days=30),
                "value": "128/82",
                "unit": "mmHg",
                "data_quality": DataQuality.EXCELLENT,
                "source_system": "Omron Connect",
                "verified": True,
                "verified_by": "Dr. James Chen",
                "verified_date": now - timedelta(days=28),
            },
            {
                "id": "ESC-002",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1001",
                "visit_id": "RV-001",
                "device_id": None,
                "data_type": "heart_rate",
                "capture_date": now - timedelta(days=30),
                "value": "72",
                "unit": "bpm",
                "data_quality": DataQuality.GOOD,
                "source_system": "NovaCare EMR",
                "verified": True,
                "verified_by": "Maria Rodriguez, RN",
                "verified_date": now - timedelta(days=30),
            },
            {
                "id": "ESC-003",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2001",
                "visit_id": "RV-003",
                "device_id": None,
                "data_type": "IgE_level",
                "capture_date": now - timedelta(days=20),
                "value": "342",
                "unit": "IU/mL",
                "data_quality": DataQuality.EXCELLENT,
                "source_system": "Quest Diagnostics LIMS",
                "verified": True,
                "verified_by": "Lab Director",
                "verified_date": now - timedelta(days=18),
            },
            {
                "id": "ESC-004",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2001",
                "visit_id": None,
                "device_id": "DEV-003",
                "data_type": "step_count",
                "capture_date": now - timedelta(days=1),
                "value": "8432",
                "unit": "steps",
                "data_quality": DataQuality.GOOD,
                "source_system": "Apple HealthKit",
                "verified": False,
                "verified_by": None,
                "verified_date": None,
            },
            {
                "id": "ESC-005",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3001",
                "visit_id": None,
                "device_id": "DEV-005",
                "data_type": "ECG_rhythm",
                "capture_date": now - timedelta(days=5),
                "value": "normal_sinus_rhythm",
                "unit": None,
                "data_quality": DataQuality.EXCELLENT,
                "source_system": "iRhythm Zio Cloud",
                "verified": True,
                "verified_by": "Dr. Cardiologist",
                "verified_date": now - timedelta(days=3),
            },
            {
                "id": "ESC-006",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3002",
                "visit_id": None,
                "device_id": "DEV-006",
                "data_type": "body_weight",
                "capture_date": now - timedelta(days=1),
                "value": "74.5",
                "unit": "kg",
                "data_quality": DataQuality.GOOD,
                "source_system": "Withings Health Mate",
                "verified": False,
                "verified_by": None,
                "verified_date": None,
            },
            {
                "id": "ESC-007",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1002",
                "visit_id": "RV-006",
                "device_id": None,
                "data_type": "visual_acuity",
                "capture_date": now - timedelta(days=5),
                "value": "20/30",
                "unit": "Snellen",
                "data_quality": DataQuality.EXCELLENT,
                "source_system": "Mobile Unit EMR",
                "verified": True,
                "verified_by": "Dr. James Chen",
                "verified_date": now - timedelta(days=4),
            },
            {
                "id": "ESC-008",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2002",
                "visit_id": None,
                "device_id": "DEV-004",
                "data_type": "SpO2",
                "capture_date": now - timedelta(days=2),
                "value": "97",
                "unit": "%",
                "data_quality": DataQuality.GOOD,
                "source_system": "Masimo Personal Health",
                "verified": False,
                "verified_by": None,
                "verified_date": None,
            },
            {
                "id": "ESC-009",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3001",
                "visit_id": "RV-005",
                "device_id": None,
                "data_type": "tumor_size",
                "capture_date": now - timedelta(days=7),
                "value": "2.3",
                "unit": "cm",
                "data_quality": DataQuality.EXCELLENT,
                "source_system": "RadNet PACS",
                "verified": True,
                "verified_by": "Dr. Radiologist",
                "verified_date": now - timedelta(days=6),
            },
            {
                "id": "ESC-010",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1003",
                "visit_id": None,
                "device_id": None,
                "data_type": "patient_reported_outcome",
                "capture_date": now - timedelta(days=3),
                "value": "VFQ-25 composite: 82",
                "unit": "score",
                "data_quality": DataQuality.GOOD,
                "source_system": "ePRO Platform",
                "verified": False,
                "verified_by": None,
                "verified_date": None,
            },
            {
                "id": "ESC-011",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2003",
                "visit_id": None,
                "device_id": None,
                "data_type": "EASI_score",
                "capture_date": now - timedelta(days=10),
                "value": "18.4",
                "unit": "score",
                "data_quality": DataQuality.ACCEPTABLE,
                "source_system": "ePRO Platform",
                "verified": False,
                "verified_by": None,
                "verified_date": None,
            },
            {
                "id": "ESC-012",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3004",
                "visit_id": None,
                "device_id": "DEV-012",
                "data_type": "ECG_rhythm",
                "capture_date": now - timedelta(days=3),
                "value": "artifact_detected",
                "unit": None,
                "data_quality": DataQuality.UNUSABLE,
                "source_system": "BioTelemetry Cloud",
                "verified": False,
                "verified_by": None,
                "verified_date": None,
            },
        ]

        for e in esource_data:
            self._esource[e["id"]] = ESourceCapture(**e)

    # ------------------------------------------------------------------
    # Remote Visits
    # ------------------------------------------------------------------

    def list_visits(
        self,
        *,
        trial_id: str | None = None,
        visit_type: VisitType | None = None,
        status: VisitStatus | None = None,
        subject_id: str | None = None,
    ) -> list[RemoteVisit]:
        """List remote visits with optional filters."""
        with self._lock:
            result = list(self._visits.values())

        if trial_id is not None:
            result = [v for v in result if v.trial_id == trial_id]
        if visit_type is not None:
            result = [v for v in result if v.visit_type == visit_type]
        if status is not None:
            result = [v for v in result if v.status == status]
        if subject_id is not None:
            result = [v for v in result if v.subject_id == subject_id]

        return sorted(result, key=lambda v: v.scheduled_date, reverse=True)

    def get_visit(self, visit_id: str) -> RemoteVisit | None:
        """Get a single remote visit by ID."""
        with self._lock:
            return self._visits.get(visit_id)

    def create_visit(self, payload: RemoteVisitCreate) -> RemoteVisit:
        """Create a new remote visit."""
        now = datetime.now(timezone.utc)
        visit_id = f"RV-{uuid4().hex[:8].upper()}"
        visit = RemoteVisit(
            id=visit_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            site_id=payload.site_id,
            visit_type=payload.visit_type,
            scheduled_date=payload.scheduled_date,
            actual_date=None,
            status=VisitStatus.SCHEDULED,
            provider_name=payload.provider_name,
            provider_organization=payload.provider_organization,
            procedures=payload.procedures,
            location_address=payload.location_address,
            duration_minutes=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._visits[visit_id] = visit
        logger.info("Created remote visit %s for subject %s", visit_id, payload.subject_id)
        return visit

    def update_visit(self, visit_id: str, payload: RemoteVisitUpdate) -> RemoteVisit | None:
        """Update an existing remote visit."""
        with self._lock:
            existing = self._visits.get(visit_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = RemoteVisit(**data)
            self._visits[visit_id] = updated
        return updated

    def delete_visit(self, visit_id: str) -> bool:
        """Delete a remote visit. Returns True if deleted."""
        with self._lock:
            if visit_id in self._visits:
                del self._visits[visit_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Wearable Devices
    # ------------------------------------------------------------------

    def list_devices(
        self,
        *,
        trial_id: str | None = None,
        device_type: DeviceType | None = None,
        device_status: DeviceStatus | None = None,
        subject_id: str | None = None,
    ) -> list[WearableDevice]:
        """List wearable devices with optional filters."""
        with self._lock:
            result = list(self._devices.values())

        if trial_id is not None:
            result = [d for d in result if d.trial_id == trial_id]
        if device_type is not None:
            result = [d for d in result if d.device_type == device_type]
        if device_status is not None:
            result = [d for d in result if d.status == device_status]
        if subject_id is not None:
            result = [d for d in result if d.subject_id == subject_id]

        return sorted(result, key=lambda d: d.assigned_date, reverse=True)

    def get_device(self, device_id: str) -> WearableDevice | None:
        """Get a single wearable device by ID."""
        with self._lock:
            return self._devices.get(device_id)

    def create_device(self, payload: WearableDeviceCreate) -> WearableDevice:
        """Create a new wearable device."""
        now = datetime.now(timezone.utc)
        device_id = f"DEV-{uuid4().hex[:8].upper()}"
        device = WearableDevice(
            id=device_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            device_type=payload.device_type,
            manufacturer=payload.manufacturer,
            model=payload.model,
            serial_number=payload.serial_number,
            firmware_version=payload.firmware_version,
            status=DeviceStatus.PROVISIONED,
            activation_date=None,
            last_sync_date=None,
            data_points_collected=0,
            battery_level_pct=None,
            data_quality=None,
            compliance_rate_pct=None,
            assigned_date=now,
        )
        with self._lock:
            self._devices[device_id] = device
        logger.info("Created wearable device %s for subject %s", device_id, payload.subject_id)
        return device

    def update_device(self, device_id: str, payload: WearableDeviceUpdate) -> WearableDevice | None:
        """Update an existing wearable device."""
        with self._lock:
            existing = self._devices.get(device_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = WearableDevice(**data)
            self._devices[device_id] = updated
        return updated

    def delete_device(self, device_id: str) -> bool:
        """Delete a wearable device. Returns True if deleted."""
        with self._lock:
            if device_id in self._devices:
                del self._devices[device_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Telemedicine Sessions
    # ------------------------------------------------------------------

    def list_sessions(
        self,
        *,
        trial_id: str | None = None,
        platform: SessionPlatform | None = None,
        status: VisitStatus | None = None,
        subject_id: str | None = None,
    ) -> list[TelemedicineSession]:
        """List telemedicine sessions with optional filters."""
        with self._lock:
            result = list(self._sessions.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if platform is not None:
            result = [s for s in result if s.platform == platform]
        if status is not None:
            result = [s for s in result if s.status == status]
        if subject_id is not None:
            result = [s for s in result if s.subject_id == subject_id]

        return sorted(result, key=lambda s: s.scheduled_date, reverse=True)

    def get_session(self, session_id: str) -> TelemedicineSession | None:
        """Get a single telemedicine session by ID."""
        with self._lock:
            return self._sessions.get(session_id)

    def create_session(self, payload: TelemedicineSessionCreate) -> TelemedicineSession:
        """Create a new telemedicine session."""
        session_id = f"TMS-{uuid4().hex[:8].upper()}"
        session = TelemedicineSession(
            id=session_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            visit_id=payload.visit_id,
            platform=payload.platform,
            scheduled_date=payload.scheduled_date,
            actual_start=None,
            actual_end=None,
            duration_minutes=None,
            provider_name=payload.provider_name,
            provider_role=payload.provider_role,
            status=VisitStatus.SCHEDULED,
            recording_available=False,
            consent_documented=False,
            connection_quality=None,
            clinical_notes=None,
        )
        with self._lock:
            self._sessions[session_id] = session
        logger.info("Created telemedicine session %s for subject %s", session_id, payload.subject_id)
        return session

    def update_session(self, session_id: str, payload: TelemedicineSessionUpdate) -> TelemedicineSession | None:
        """Update an existing telemedicine session."""
        with self._lock:
            existing = self._sessions.get(session_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = TelemedicineSession(**data)
            self._sessions[session_id] = updated
        return updated

    def delete_session(self, session_id: str) -> bool:
        """Delete a telemedicine session. Returns True if deleted."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    # ------------------------------------------------------------------
    # eSource Captures
    # ------------------------------------------------------------------

    def list_esource(
        self,
        *,
        trial_id: str | None = None,
        subject_id: str | None = None,
        data_type: str | None = None,
        data_quality: DataQuality | None = None,
    ) -> list[ESourceCapture]:
        """List eSource captures with optional filters."""
        with self._lock:
            result = list(self._esource.values())

        if trial_id is not None:
            result = [e for e in result if e.trial_id == trial_id]
        if subject_id is not None:
            result = [e for e in result if e.subject_id == subject_id]
        if data_type is not None:
            result = [e for e in result if e.data_type == data_type]
        if data_quality is not None:
            result = [e for e in result if e.data_quality == data_quality]

        return sorted(result, key=lambda e: e.capture_date, reverse=True)

    def get_esource(self, esource_id: str) -> ESourceCapture | None:
        """Get a single eSource capture by ID."""
        with self._lock:
            return self._esource.get(esource_id)

    def create_esource(self, payload: ESourceCaptureCreate) -> ESourceCapture:
        """Create a new eSource capture."""
        now = datetime.now(timezone.utc)
        esource_id = f"ESC-{uuid4().hex[:8].upper()}"
        capture = ESourceCapture(
            id=esource_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            visit_id=payload.visit_id,
            device_id=payload.device_id,
            data_type=payload.data_type,
            capture_date=now,
            value=payload.value,
            unit=payload.unit,
            data_quality=DataQuality.GOOD,
            source_system=payload.source_system,
            verified=False,
            verified_by=None,
            verified_date=None,
        )
        with self._lock:
            self._esource[esource_id] = capture
        logger.info("Created eSource capture %s: %s", esource_id, payload.data_type)
        return capture

    def update_esource(self, esource_id: str, payload: ESourceCaptureUpdate) -> ESourceCapture | None:
        """Update an existing eSource capture."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._esource.get(esource_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set verified_date when verified becomes True
            if "verified" in updates and updates["verified"] and not existing.verified:
                updates["verified_date"] = now

            data.update(updates)
            updated = ESourceCapture(**data)
            self._esource[esource_id] = updated
        return updated

    def delete_esource(self, esource_id: str) -> bool:
        """Delete an eSource capture. Returns True if deleted."""
        with self._lock:
            if esource_id in self._esource:
                del self._esource[esource_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> DecentralizedTrialMetrics:
        """Compute aggregated DCT operational metrics."""
        with self._lock:
            visits = list(self._visits.values())
            devices = list(self._devices.values())
            sessions = list(self._sessions.values())
            esource = list(self._esource.values())

        # Visits
        visits_by_type: dict[str, int] = {}
        visits_by_status: dict[str, int] = {}
        completed_visits = 0
        for v in visits:
            vtype = v.visit_type.value
            visits_by_type[vtype] = visits_by_type.get(vtype, 0) + 1
            vstatus = v.status.value
            visits_by_status[vstatus] = visits_by_status.get(vstatus, 0) + 1
            if v.status == VisitStatus.COMPLETED:
                completed_visits += 1

        total_visits = len(visits)
        visit_completion_rate = (
            round((completed_visits / total_visits) * 100, 1)
            if total_visits > 0
            else 0.0
        )

        # Devices
        devices_by_type: dict[str, int] = {}
        devices_by_status: dict[str, int] = {}
        compliance_values: list[float] = []
        for d in devices:
            dtype = d.device_type.value
            devices_by_type[dtype] = devices_by_type.get(dtype, 0) + 1
            dstatus = d.status.value
            devices_by_status[dstatus] = devices_by_status.get(dstatus, 0) + 1
            if d.compliance_rate_pct is not None:
                compliance_values.append(d.compliance_rate_pct)

        avg_device_compliance = (
            round(sum(compliance_values) / len(compliance_values), 1)
            if compliance_values
            else 0.0
        )

        # Sessions
        sessions_by_status: dict[str, int] = {}
        session_durations: list[int] = []
        for s in sessions:
            sstatus = s.status.value
            sessions_by_status[sstatus] = sessions_by_status.get(sstatus, 0) + 1
            if s.status == VisitStatus.COMPLETED and s.duration_minutes is not None:
                session_durations.append(s.duration_minutes)

        avg_session_duration = (
            round(sum(session_durations) / len(session_durations), 1)
            if session_durations
            else 0.0
        )

        # eSource
        verified_captures = sum(1 for e in esource if e.verified)
        data_quality_distribution: dict[str, int] = {}
        for e in esource:
            qkey = e.data_quality.value
            data_quality_distribution[qkey] = data_quality_distribution.get(qkey, 0) + 1

        return DecentralizedTrialMetrics(
            total_remote_visits=total_visits,
            visits_by_type=visits_by_type,
            visits_by_status=visits_by_status,
            visit_completion_rate=visit_completion_rate,
            total_devices=len(devices),
            devices_by_type=devices_by_type,
            devices_by_status=devices_by_status,
            avg_device_compliance_pct=avg_device_compliance,
            total_telemedicine_sessions=len(sessions),
            sessions_by_status=sessions_by_status,
            avg_session_duration_minutes=avg_session_duration,
            total_esource_captures=len(esource),
            verified_captures=verified_captures,
            data_quality_distribution=data_quality_distribution,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: DecentralizedTrialsService | None = None
_instance_lock = threading.Lock()


def get_decentralized_trials_service() -> DecentralizedTrialsService:
    """Return the singleton DecentralizedTrialsService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = DecentralizedTrialsService()
    return _instance


def reset_decentralized_trials_service() -> DecentralizedTrialsService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = DecentralizedTrialsService()
    return _instance
