"""Supply Chain Serialization & Track-and-Trace Service (CLINICAL-11).

Manages product serialization, unit-level tracking, cold chain monitoring,
distribution verification, DSCSA/FMD compliance, and counterfeit detection
for clinical supply.

Usage:
    from app.services.supply_serialization_service import (
        get_supply_serialization_service,
    )

    svc = get_supply_serialization_service()
    unit = svc.register_serial(data)
    trace = svc.trace_unit_history("SU-001")
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.supply_serialization import (
    ColdChainAcknowledge,
    ColdChainReading,
    ColdChainReadingCreate,
    ColdChainStatus,
    ComplianceRecord,
    ComplianceRecordCreate,
    ComplianceStandard,
    DistributionRecord,
    DistributionRecordCreate,
    DistributionRecordUpdate,
    SerializationLevel,
    SerializationMetrics,
    SerializedUnit,
    SerializedUnitCreate,
    SerializedUnitUpdate,
    TrackingEvent,
    TrackingEventCreate,
    TrackingEventType,
    UnitStatus,
    UnitTraceResponse,
    VerificationRequest,
    VerificationRequestCreate,
    VerificationRequestUpdate,
    VerificationStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cold chain temperature thresholds (Celsius)
# ---------------------------------------------------------------------------

COLD_CHAIN_THRESHOLDS = {
    "minor_low": 1.0,
    "minor_high": 9.0,
    "major_low": -2.0,
    "major_high": 12.0,
    "target_low": 2.0,
    "target_high": 8.0,
}


def _classify_cold_chain(temperature: float) -> ColdChainStatus:
    """Classify a temperature reading into a cold chain status."""
    if COLD_CHAIN_THRESHOLDS["target_low"] <= temperature <= COLD_CHAIN_THRESHOLDS["target_high"]:
        return ColdChainStatus.WITHIN_RANGE
    if COLD_CHAIN_THRESHOLDS["minor_low"] <= temperature <= COLD_CHAIN_THRESHOLDS["minor_high"]:
        return ColdChainStatus.EXCURSION_MINOR
    if COLD_CHAIN_THRESHOLDS["major_low"] <= temperature <= COLD_CHAIN_THRESHOLDS["major_high"]:
        return ColdChainStatus.EXCURSION_MAJOR
    return ColdChainStatus.BREACH


class SupplySerializationService:
    """In-memory supply chain serialization and track-and-trace engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._units: dict[str, SerializedUnit] = {}
        self._tracking_events: dict[str, TrackingEvent] = {}
        self._cold_chain_readings: dict[str, ColdChainReading] = {}
        self._compliance_records: dict[str, ComplianceRecord] = {}
        self._verification_requests: dict[str, VerificationRequest] = {}
        self._distribution_records: dict[str, DistributionRecord] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901 – seed method is intentionally long
        """Pre-populate realistic serialization and track-and-trace data."""
        now = datetime.now(timezone.utc)

        # --- Serialized Units (12 units with parent-child hierarchy) ---
        units = [
            # Pallet
            SerializedUnit(
                id="SU-001",
                product_name="EYLEA HD (Aflibercept) 8mg",
                gtin="00361755000601",
                serial_number="SN-PAL-2025-0001",
                lot_number="LOT-2025-A001",
                expiry_date=now + timedelta(days=365),
                serialization_level=SerializationLevel.PALLET,
                parent_id=None,
                manufacturing_site="Regeneron-Rensselaer",
                manufacturing_date=now - timedelta(days=60),
                status=UnitStatus.ACTIVE,
                current_location="DEPOT-CENTRAL",
                last_scan_date=now - timedelta(hours=6),
            ),
            # Cases under pallet
            SerializedUnit(
                id="SU-002",
                product_name="EYLEA HD (Aflibercept) 8mg",
                gtin="00361755000601",
                serial_number="SN-CAS-2025-0001",
                lot_number="LOT-2025-A001",
                expiry_date=now + timedelta(days=365),
                serialization_level=SerializationLevel.CASE,
                parent_id="SU-001",
                manufacturing_site="Regeneron-Rensselaer",
                manufacturing_date=now - timedelta(days=60),
                status=UnitStatus.ACTIVE,
                current_location="DEPOT-CENTRAL",
                last_scan_date=now - timedelta(hours=6),
            ),
            SerializedUnit(
                id="SU-003",
                product_name="EYLEA HD (Aflibercept) 8mg",
                gtin="00361755000601",
                serial_number="SN-CAS-2025-0002",
                lot_number="LOT-2025-A001",
                expiry_date=now + timedelta(days=365),
                serialization_level=SerializationLevel.CASE,
                parent_id="SU-001",
                manufacturing_site="Regeneron-Rensselaer",
                manufacturing_date=now - timedelta(days=60),
                status=UnitStatus.IN_TRANSIT,
                current_location="IN-TRANSIT-FedEx",
                last_scan_date=now - timedelta(hours=2),
            ),
            # Bundles under case SU-002
            SerializedUnit(
                id="SU-004",
                product_name="EYLEA HD (Aflibercept) 8mg",
                gtin="00361755000601",
                serial_number="SN-BND-2025-0001",
                lot_number="LOT-2025-A001",
                expiry_date=now + timedelta(days=365),
                serialization_level=SerializationLevel.BUNDLE,
                parent_id="SU-002",
                manufacturing_site="Regeneron-Rensselaer",
                manufacturing_date=now - timedelta(days=60),
                status=UnitStatus.ACTIVE,
                current_location="DEPOT-CENTRAL",
                last_scan_date=now - timedelta(hours=6),
            ),
            # Individual units under bundle SU-004
            SerializedUnit(
                id="SU-005",
                product_name="EYLEA HD (Aflibercept) 8mg",
                gtin="00361755000601",
                serial_number="SN-UNIT-2025-0001",
                lot_number="LOT-2025-A001",
                expiry_date=now + timedelta(days=365),
                serialization_level=SerializationLevel.UNIT,
                parent_id="SU-004",
                manufacturing_site="Regeneron-Rensselaer",
                manufacturing_date=now - timedelta(days=60),
                status=UnitStatus.DISPENSED,
                current_location="SITE-101",
                last_scan_date=now - timedelta(days=3),
            ),
            SerializedUnit(
                id="SU-006",
                product_name="EYLEA HD (Aflibercept) 8mg",
                gtin="00361755000601",
                serial_number="SN-UNIT-2025-0002",
                lot_number="LOT-2025-A001",
                expiry_date=now + timedelta(days=365),
                serialization_level=SerializationLevel.UNIT,
                parent_id="SU-004",
                manufacturing_site="Regeneron-Rensselaer",
                manufacturing_date=now - timedelta(days=60),
                status=UnitStatus.ACTIVE,
                current_location="SITE-101",
                last_scan_date=now - timedelta(days=1),
            ),
            # Dupixent product line
            SerializedUnit(
                id="SU-007",
                product_name="Dupixent (Dupilumab) 300mg",
                gtin="00024591801",
                serial_number="SN-CAS-DPX-0001",
                lot_number="LOT-2025-B001",
                expiry_date=now + timedelta(days=270),
                serialization_level=SerializationLevel.CASE,
                parent_id=None,
                manufacturing_site="Sanofi-Le-Trait",
                manufacturing_date=now - timedelta(days=45),
                status=UnitStatus.ACTIVE,
                current_location="SITE-201",
                last_scan_date=now - timedelta(days=2),
            ),
            SerializedUnit(
                id="SU-008",
                product_name="Dupixent (Dupilumab) 300mg",
                gtin="00024591801",
                serial_number="SN-UNIT-DPX-0001",
                lot_number="LOT-2025-B001",
                expiry_date=now + timedelta(days=270),
                serialization_level=SerializationLevel.UNIT,
                parent_id="SU-007",
                manufacturing_site="Sanofi-Le-Trait",
                manufacturing_date=now - timedelta(days=45),
                status=UnitStatus.DISPENSED,
                current_location="SITE-201",
                last_scan_date=now - timedelta(days=5),
            ),
            SerializedUnit(
                id="SU-009",
                product_name="Dupixent (Dupilumab) 300mg",
                gtin="00024591801",
                serial_number="SN-UNIT-DPX-0002",
                lot_number="LOT-2025-B001",
                expiry_date=now + timedelta(days=270),
                serialization_level=SerializationLevel.UNIT,
                parent_id="SU-007",
                manufacturing_site="Sanofi-Le-Trait",
                manufacturing_date=now - timedelta(days=45),
                status=UnitStatus.RETURNED,
                current_location="SITE-201",
                last_scan_date=now - timedelta(days=1),
            ),
            # Libtayo
            SerializedUnit(
                id="SU-010",
                product_name="Libtayo (Cemiplimab) 350mg",
                gtin="00024595910",
                serial_number="SN-CAS-LBT-0001",
                lot_number="LOT-2025-C001",
                expiry_date=now + timedelta(days=400),
                serialization_level=SerializationLevel.CASE,
                parent_id=None,
                manufacturing_site="Regeneron-Limerick",
                manufacturing_date=now - timedelta(days=30),
                status=UnitStatus.ACTIVE,
                current_location="SITE-301",
                last_scan_date=now - timedelta(hours=12),
            ),
            # Recalled unit
            SerializedUnit(
                id="SU-011",
                product_name="EYLEA HD (Aflibercept) 8mg",
                gtin="00361755000601",
                serial_number="SN-UNIT-2025-0099",
                lot_number="LOT-2025-A002",
                expiry_date=now + timedelta(days=200),
                serialization_level=SerializationLevel.UNIT,
                parent_id=None,
                manufacturing_site="Regeneron-Rensselaer",
                manufacturing_date=now - timedelta(days=90),
                status=UnitStatus.RECALLED,
                current_location="QUARANTINE-DEPOT",
                last_scan_date=now - timedelta(days=10),
            ),
            # Quarantined (suspected counterfeit)
            SerializedUnit(
                id="SU-012",
                product_name="EYLEA HD (Aflibercept) 8mg",
                gtin="00361755000601",
                serial_number="SN-UNIT-2025-SUSPECT",
                lot_number="LOT-2025-X001",
                expiry_date=now + timedelta(days=180),
                serialization_level=SerializationLevel.UNIT,
                parent_id=None,
                manufacturing_site="Unknown",
                manufacturing_date=now - timedelta(days=120),
                status=UnitStatus.QUARANTINED,
                current_location="QUARANTINE-DEPOT",
                last_scan_date=now - timedelta(days=7),
            ),
        ]
        for u in units:
            self._units[u.id] = u

        # --- Tracking Events (18 events) ---
        events = [
            # SU-005 full lifecycle
            TrackingEvent(
                id="TE-001", unit_id="SU-005", event_type=TrackingEventType.MANUFACTURED,
                timestamp=now - timedelta(days=60), location="PLANT-REN",
                facility_name="Regeneron Rensselaer Plant", scanned_by="MFG-SYS-001",
                gps_latitude=42.6428, gps_longitude=-73.7419, temperature=20.0,
                humidity=45.0, notes="Initial manufacture", transaction_id="TXN-MFG-001",
            ),
            TrackingEvent(
                id="TE-002", unit_id="SU-005", event_type=TrackingEventType.PACKAGED,
                timestamp=now - timedelta(days=58), location="PACK-REN",
                facility_name="Regeneron Packaging Facility", scanned_by="PKG-SYS-001",
                gps_latitude=42.6428, gps_longitude=-73.7419, temperature=5.0,
                humidity=40.0, notes="Packaged into bundle SU-004", transaction_id="TXN-PKG-001",
            ),
            TrackingEvent(
                id="TE-003", unit_id="SU-005", event_type=TrackingEventType.SHIPPED,
                timestamp=now - timedelta(days=30), location="DEPOT-CENTRAL",
                facility_name="Central Distribution Depot", scanned_by="WH-OPS-001",
                gps_latitude=40.7128, gps_longitude=-74.0060, temperature=4.5,
                humidity=42.0, notes="Shipped to SITE-101", transaction_id="TXN-SHP-001",
            ),
            TrackingEvent(
                id="TE-004", unit_id="SU-005", event_type=TrackingEventType.RECEIVED,
                timestamp=now - timedelta(days=28), location="SITE-101",
                facility_name="Johns Hopkins Clinical Site", scanned_by="PHARM-101",
                gps_latitude=39.2984, gps_longitude=-76.5922, temperature=5.0,
                humidity=44.0, notes="Received at site pharmacy", transaction_id="TXN-RCV-001",
            ),
            TrackingEvent(
                id="TE-005", unit_id="SU-005", event_type=TrackingEventType.DISPENSED,
                timestamp=now - timedelta(days=3), location="SITE-101",
                facility_name="Johns Hopkins Clinical Site", scanned_by="PHARM-101",
                gps_latitude=39.2984, gps_longitude=-76.5922, temperature=5.5,
                humidity=43.0, notes="Dispensed to patient PAT-DME-001", transaction_id="TXN-DSP-001",
            ),
            # SU-006 partial lifecycle
            TrackingEvent(
                id="TE-006", unit_id="SU-006", event_type=TrackingEventType.MANUFACTURED,
                timestamp=now - timedelta(days=60), location="PLANT-REN",
                facility_name="Regeneron Rensselaer Plant", scanned_by="MFG-SYS-001",
                gps_latitude=42.6428, gps_longitude=-73.7419, temperature=20.0,
                humidity=45.0, notes=None, transaction_id="TXN-MFG-002",
            ),
            TrackingEvent(
                id="TE-007", unit_id="SU-006", event_type=TrackingEventType.SHIPPED,
                timestamp=now - timedelta(days=30), location="DEPOT-CENTRAL",
                facility_name="Central Distribution Depot", scanned_by="WH-OPS-001",
                gps_latitude=40.7128, gps_longitude=-74.0060, temperature=4.0,
                humidity=41.0, notes=None, transaction_id="TXN-SHP-002",
            ),
            TrackingEvent(
                id="TE-008", unit_id="SU-006", event_type=TrackingEventType.RECEIVED,
                timestamp=now - timedelta(days=28), location="SITE-101",
                facility_name="Johns Hopkins Clinical Site", scanned_by="PHARM-101",
                gps_latitude=39.2984, gps_longitude=-76.5922, temperature=5.2,
                humidity=43.0, notes=None, transaction_id="TXN-RCV-002",
            ),
            # SU-008 Dupixent dispensed
            TrackingEvent(
                id="TE-009", unit_id="SU-008", event_type=TrackingEventType.MANUFACTURED,
                timestamp=now - timedelta(days=45), location="PLANT-LTR",
                facility_name="Sanofi Le Trait Plant", scanned_by="MFG-SYS-LTR",
                gps_latitude=49.5100, gps_longitude=0.8200, temperature=21.0,
                humidity=50.0, notes=None, transaction_id="TXN-MFG-003",
            ),
            TrackingEvent(
                id="TE-010", unit_id="SU-008", event_type=TrackingEventType.SHIPPED,
                timestamp=now - timedelta(days=20), location="DEPOT-EU",
                facility_name="EU Distribution Hub", scanned_by="WH-OPS-EU",
                gps_latitude=50.8503, gps_longitude=4.3517, temperature=4.8,
                humidity=45.0, notes=None, transaction_id="TXN-SHP-003",
            ),
            TrackingEvent(
                id="TE-011", unit_id="SU-008", event_type=TrackingEventType.RECEIVED,
                timestamp=now - timedelta(days=17), location="SITE-201",
                facility_name="Mass General Dermatology", scanned_by="PHARM-201",
                gps_latitude=42.3601, gps_longitude=-71.0589, temperature=5.1,
                humidity=44.0, notes=None, transaction_id="TXN-RCV-003",
            ),
            TrackingEvent(
                id="TE-012", unit_id="SU-008", event_type=TrackingEventType.DISPENSED,
                timestamp=now - timedelta(days=5), location="SITE-201",
                facility_name="Mass General Dermatology", scanned_by="PHARM-201",
                gps_latitude=42.3601, gps_longitude=-71.0589, temperature=5.3,
                humidity=43.0, notes="Dispensed to patient PAT-AD-001", transaction_id="TXN-DSP-002",
            ),
            # SU-009 returned
            TrackingEvent(
                id="TE-013", unit_id="SU-009", event_type=TrackingEventType.DISPENSED,
                timestamp=now - timedelta(days=10), location="SITE-201",
                facility_name="Mass General Dermatology", scanned_by="PHARM-201",
                gps_latitude=42.3601, gps_longitude=-71.0589, temperature=5.0,
                humidity=42.0, notes="Dispensed to patient PAT-AD-003", transaction_id="TXN-DSP-003",
            ),
            TrackingEvent(
                id="TE-014", unit_id="SU-009", event_type=TrackingEventType.RETURNED,
                timestamp=now - timedelta(days=1), location="SITE-201",
                facility_name="Mass General Dermatology", scanned_by="PHARM-201",
                gps_latitude=42.3601, gps_longitude=-71.0589, temperature=5.0,
                humidity=43.0, notes="Patient discontinued - unused medication returned",
                transaction_id="TXN-RTN-001",
            ),
            # SU-011 recalled
            TrackingEvent(
                id="TE-015", unit_id="SU-011", event_type=TrackingEventType.RECALLED,
                timestamp=now - timedelta(days=10), location="QUARANTINE-DEPOT",
                facility_name="Quarantine Depot", scanned_by="QA-SYS-001",
                gps_latitude=40.7128, gps_longitude=-74.0060, temperature=4.0,
                humidity=40.0, notes="Recalled due to potential contamination",
                transaction_id="TXN-RCL-001",
            ),
            # SU-012 suspect scan
            TrackingEvent(
                id="TE-016", unit_id="SU-012", event_type=TrackingEventType.RECEIVED,
                timestamp=now - timedelta(days=7), location="QUARANTINE-DEPOT",
                facility_name="Quarantine Depot", scanned_by="SEC-SYS-001",
                gps_latitude=40.7128, gps_longitude=-74.0060, temperature=6.0,
                humidity=48.0, notes="Flagged as suspect during intake verification",
                transaction_id="TXN-QRN-001",
            ),
            # SU-003 in transit
            TrackingEvent(
                id="TE-017", unit_id="SU-003", event_type=TrackingEventType.SHIPPED,
                timestamp=now - timedelta(hours=12), location="DEPOT-CENTRAL",
                facility_name="Central Distribution Depot", scanned_by="WH-OPS-001",
                gps_latitude=40.7128, gps_longitude=-74.0060, temperature=4.2,
                humidity=41.0, notes="Shipped to SITE-102 via FedEx Priority",
                transaction_id="TXN-SHP-004",
            ),
            # SU-010 Libtayo received at site
            TrackingEvent(
                id="TE-018", unit_id="SU-010", event_type=TrackingEventType.RECEIVED,
                timestamp=now - timedelta(hours=12), location="SITE-301",
                facility_name="MD Anderson Oncology", scanned_by="PHARM-301",
                gps_latitude=29.7070, gps_longitude=-95.3987, temperature=4.8,
                humidity=44.0, notes="Received and verified at site pharmacy",
                transaction_id="TXN-RCV-004",
            ),
        ]
        for e in events:
            self._tracking_events[e.id] = e

        # --- Cold Chain Readings (10 readings) ---
        readings = [
            ColdChainReading(
                id="CC-001", shipment_id="DIST-001", sensor_id="SENS-TH-001",
                timestamp=now - timedelta(days=30, hours=0), temperature=4.5,
                humidity=42.0, location="DEPOT-CENTRAL", status=ColdChainStatus.WITHIN_RANGE,
                alert_triggered=False, alert_acknowledged_by=None, alert_acknowledged_date=None,
            ),
            ColdChainReading(
                id="CC-002", shipment_id="DIST-001", sensor_id="SENS-TH-001",
                timestamp=now - timedelta(days=29, hours=18), temperature=5.0,
                humidity=43.0, location="In Transit - NJ", status=ColdChainStatus.WITHIN_RANGE,
                alert_triggered=False, alert_acknowledged_by=None, alert_acknowledged_date=None,
            ),
            ColdChainReading(
                id="CC-003", shipment_id="DIST-001", sensor_id="SENS-TH-001",
                timestamp=now - timedelta(days=29, hours=12), temperature=8.5,
                humidity=50.0, location="In Transit - PA", status=ColdChainStatus.EXCURSION_MINOR,
                alert_triggered=True, alert_acknowledged_by="QA-MGR-001",
                alert_acknowledged_date=now - timedelta(days=29, hours=10),
            ),
            ColdChainReading(
                id="CC-004", shipment_id="DIST-001", sensor_id="SENS-TH-001",
                timestamp=now - timedelta(days=29, hours=6), temperature=6.0,
                humidity=44.0, location="In Transit - MD", status=ColdChainStatus.WITHIN_RANGE,
                alert_triggered=False, alert_acknowledged_by=None, alert_acknowledged_date=None,
            ),
            ColdChainReading(
                id="CC-005", shipment_id="DIST-002", sensor_id="SENS-TH-002",
                timestamp=now - timedelta(days=20), temperature=3.5,
                humidity=41.0, location="DEPOT-EU", status=ColdChainStatus.WITHIN_RANGE,
                alert_triggered=False, alert_acknowledged_by=None, alert_acknowledged_date=None,
            ),
            ColdChainReading(
                id="CC-006", shipment_id="DIST-002", sensor_id="SENS-TH-002",
                timestamp=now - timedelta(days=19), temperature=11.5,
                humidity=55.0, location="In Transit - Atlantic", status=ColdChainStatus.EXCURSION_MAJOR,
                alert_triggered=True, alert_acknowledged_by="QA-MGR-002",
                alert_acknowledged_date=now - timedelta(days=19) + timedelta(hours=1),
            ),
            ColdChainReading(
                id="CC-007", shipment_id="DIST-002", sensor_id="SENS-TH-002",
                timestamp=now - timedelta(days=18), temperature=5.5,
                humidity=43.0, location="In Transit - US East", status=ColdChainStatus.WITHIN_RANGE,
                alert_triggered=False, alert_acknowledged_by=None, alert_acknowledged_date=None,
            ),
            ColdChainReading(
                id="CC-008", shipment_id="DIST-003", sensor_id="SENS-TH-003",
                timestamp=now - timedelta(days=5), temperature=15.0,
                humidity=60.0, location="In Transit - TX", status=ColdChainStatus.BREACH,
                alert_triggered=True, alert_acknowledged_by=None, alert_acknowledged_date=None,
            ),
            ColdChainReading(
                id="CC-009", shipment_id="DIST-004", sensor_id="SENS-TH-004",
                timestamp=now - timedelta(hours=6), temperature=4.0,
                humidity=42.0, location="DEPOT-CENTRAL", status=ColdChainStatus.WITHIN_RANGE,
                alert_triggered=False, alert_acknowledged_by=None, alert_acknowledged_date=None,
            ),
            ColdChainReading(
                id="CC-010", shipment_id="DIST-004", sensor_id="SENS-TH-004",
                timestamp=now - timedelta(hours=3), temperature=4.2,
                humidity=41.0, location="In Transit - NJ", status=ColdChainStatus.WITHIN_RANGE,
                alert_triggered=False, alert_acknowledged_by=None, alert_acknowledged_date=None,
            ),
        ]
        for r in readings:
            self._cold_chain_readings[r.id] = r

        # --- Compliance Records (7 records) ---
        compliance = [
            ComplianceRecord(
                id="CR-001", unit_id="SU-005", standard=ComplianceStandard.DSCSA,
                country="US", compliant=True, verification_date=now - timedelta(days=28),
                verified_by="COMPLIANCE-SYS-US",
                transaction_information="TI-EYLEA-SU005-20250128",
                transaction_history="TH-EYLEA-SU005-FULL",
                transaction_statement="TS-EYLEA-SU005-VERIFIED",
                certificate_reference="CERT-DSCSA-2025-0001",
            ),
            ComplianceRecord(
                id="CR-002", unit_id="SU-006", standard=ComplianceStandard.DSCSA,
                country="US", compliant=True, verification_date=now - timedelta(days=28),
                verified_by="COMPLIANCE-SYS-US",
                transaction_information="TI-EYLEA-SU006-20250128",
                transaction_history="TH-EYLEA-SU006-FULL",
                transaction_statement="TS-EYLEA-SU006-VERIFIED",
                certificate_reference="CERT-DSCSA-2025-0002",
            ),
            ComplianceRecord(
                id="CR-003", unit_id="SU-008", standard=ComplianceStandard.EU_FMD,
                country="FR", compliant=True, verification_date=now - timedelta(days=17),
                verified_by="EMVS-SYS-FR",
                transaction_information=None, transaction_history=None,
                transaction_statement=None,
                certificate_reference="CERT-FMD-2025-0001",
            ),
            ComplianceRecord(
                id="CR-004", unit_id="SU-008", standard=ComplianceStandard.DSCSA,
                country="US", compliant=True, verification_date=now - timedelta(days=15),
                verified_by="COMPLIANCE-SYS-US",
                transaction_information="TI-DPX-SU008-20250215",
                transaction_history="TH-DPX-SU008-FULL",
                transaction_statement="TS-DPX-SU008-VERIFIED",
                certificate_reference="CERT-DSCSA-2025-0003",
            ),
            ComplianceRecord(
                id="CR-005", unit_id="SU-010", standard=ComplianceStandard.DSCSA,
                country="US", compliant=True, verification_date=now - timedelta(hours=12),
                verified_by="COMPLIANCE-SYS-US",
                transaction_information="TI-LBT-SU010-20250301",
                transaction_history="TH-LBT-SU010-FULL",
                transaction_statement="TS-LBT-SU010-VERIFIED",
                certificate_reference="CERT-DSCSA-2025-0004",
            ),
            ComplianceRecord(
                id="CR-006", unit_id="SU-012", standard=ComplianceStandard.DSCSA,
                country="US", compliant=False, verification_date=now - timedelta(days=7),
                verified_by="COMPLIANCE-SYS-US",
                transaction_information="TI-SUSPECT-SU012",
                transaction_history="TH-SUSPECT-SU012-INCOMPLETE",
                transaction_statement=None,
                certificate_reference=None,
            ),
            ComplianceRecord(
                id="CR-007", unit_id="SU-009", standard=ComplianceStandard.BRAZIL_SNCM,
                country="BR", compliant=True, verification_date=now - timedelta(days=10),
                verified_by="ANVISA-SYS-BR",
                transaction_information=None, transaction_history=None,
                transaction_statement=None,
                certificate_reference="CERT-SNCM-2025-0001",
            ),
        ]
        for c in compliance:
            self._compliance_records[c.id] = c

        # --- Verification Requests (3 requests) ---
        verifications = [
            VerificationRequest(
                id="VR-001", requestor="PharmaCo Distribution",
                request_date=now - timedelta(days=7),
                gtin="00361755000601", serial_number="SN-UNIT-2025-SUSPECT",
                lot_number="LOT-2025-X001",
                verification_status=VerificationStatus.SUSPECT,
                response_date=now - timedelta(days=6),
                responder="Regeneron QA",
                investigation_notes="Serial number not found in manufacturing database. "
                    "Packaging anomalies detected. Under investigation.",
                resolution=None,
            ),
            VerificationRequest(
                id="VR-002", requestor="Hospital Pharmacy A",
                request_date=now - timedelta(days=14),
                gtin="00361755000601", serial_number="SN-UNIT-2025-0001",
                lot_number="LOT-2025-A001",
                verification_status=VerificationStatus.VERIFIED,
                response_date=now - timedelta(days=14),
                responder="DSCSA VRS System",
                investigation_notes=None,
                resolution="Product verified as authentic",
            ),
            VerificationRequest(
                id="VR-003", requestor="Import Authority BR",
                request_date=now - timedelta(days=3),
                gtin="00024591801", serial_number="SN-UNIT-DPX-0002",
                lot_number="LOT-2025-B001",
                verification_status=VerificationStatus.QUARANTINED,
                response_date=now - timedelta(days=2),
                responder="Sanofi QA",
                investigation_notes="Returned unit flagged during re-import. "
                    "Awaiting physical inspection.",
                resolution=None,
            ),
        ]
        for v in verifications:
            self._verification_requests[v.id] = v

        # --- Distribution Records (5 records) ---
        distributions = [
            DistributionRecord(
                id="DIST-001", shipment_id="SHP-SER-001",
                from_facility="DEPOT-CENTRAL", to_facility="SITE-101",
                shipped_date=now - timedelta(days=30),
                received_date=now - timedelta(days=28),
                units_shipped=24, units_received=24, discrepancy=False,
                carrier="FedEx Priority", tracking_number="FX-7890123456",
                chain_of_custody_verified=True,
            ),
            DistributionRecord(
                id="DIST-002", shipment_id="SHP-SER-002",
                from_facility="DEPOT-EU", to_facility="SITE-201",
                shipped_date=now - timedelta(days=20),
                received_date=now - timedelta(days=17),
                units_shipped=36, units_received=35, discrepancy=True,
                carrier="DHL Express", tracking_number="DHL-5678901234",
                chain_of_custody_verified=False,
            ),
            DistributionRecord(
                id="DIST-003", shipment_id="SHP-SER-003",
                from_facility="DEPOT-CENTRAL", to_facility="SITE-301",
                shipped_date=now - timedelta(days=5),
                received_date=None,
                units_shipped=12, units_received=None, discrepancy=False,
                carrier="UPS Next Day", tracking_number="UPS-3456789012",
                chain_of_custody_verified=False,
            ),
            DistributionRecord(
                id="DIST-004", shipment_id="SHP-SER-004",
                from_facility="DEPOT-CENTRAL", to_facility="SITE-102",
                shipped_date=now - timedelta(hours=6),
                received_date=None,
                units_shipped=18, units_received=None, discrepancy=False,
                carrier="FedEx Priority", tracking_number="FX-2345678901",
                chain_of_custody_verified=False,
            ),
            DistributionRecord(
                id="DIST-005", shipment_id="SHP-SER-005",
                from_facility="SITE-201", to_facility="DEPOT-CENTRAL",
                shipped_date=now - timedelta(days=1),
                received_date=None,
                units_shipped=5, units_received=None, discrepancy=False,
                carrier="FedEx Standard", tracking_number="FX-1234567890",
                chain_of_custody_verified=False,
            ),
        ]
        for d in distributions:
            self._distribution_records[d.id] = d

        logger.info(
            "Supply serialization service initialised with %d units, %d events, "
            "%d cold chain readings, %d compliance records, %d verification requests, "
            "%d distribution records",
            len(self._units),
            len(self._tracking_events),
            len(self._cold_chain_readings),
            len(self._compliance_records),
            len(self._verification_requests),
            len(self._distribution_records),
        )

    # ------------------------------------------------------------------
    # Serialized Unit CRUD
    # ------------------------------------------------------------------

    def list_units(
        self,
        serialization_level: SerializationLevel | None = None,
        status: UnitStatus | None = None,
        lot_number: str | None = None,
        gtin: str | None = None,
        parent_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SerializedUnit], int]:
        """List serialized units with optional filters."""
        with self._lock:
            items = list(self._units.values())

        if serialization_level:
            items = [u for u in items if u.serialization_level == serialization_level]
        if status:
            items = [u for u in items if u.status == status]
        if lot_number:
            items = [u for u in items if u.lot_number == lot_number]
        if gtin:
            items = [u for u in items if u.gtin == gtin]
        if parent_id is not None:
            items = [u for u in items if u.parent_id == parent_id]

        total = len(items)
        items = items[offset: offset + limit]
        return items, total

    def get_unit(self, unit_id: str) -> SerializedUnit:
        """Get a single serialized unit by ID."""
        with self._lock:
            if unit_id not in self._units:
                raise KeyError(f"Serialized unit '{unit_id}' not found")
            return self._units[unit_id]

    def register_serial(self, data: SerializedUnitCreate) -> SerializedUnit:
        """Register a new serialized unit."""
        unit_id = f"SU-{uuid4().hex[:6].upper()}"
        now = datetime.now(timezone.utc)

        # Validate parent exists if specified
        if data.parent_id:
            with self._lock:
                if data.parent_id not in self._units:
                    raise KeyError(f"Parent unit '{data.parent_id}' not found")

        record = SerializedUnit(
            id=unit_id,
            product_name=data.product_name,
            gtin=data.gtin,
            serial_number=data.serial_number,
            lot_number=data.lot_number,
            expiry_date=data.expiry_date,
            serialization_level=data.serialization_level,
            parent_id=data.parent_id,
            manufacturing_site=data.manufacturing_site,
            manufacturing_date=data.manufacturing_date,
            status=UnitStatus.ACTIVE,
            current_location=data.current_location,
            last_scan_date=now,
        )
        with self._lock:
            # Check for duplicate serial number + GTIN
            for existing in self._units.values():
                if existing.serial_number == data.serial_number and existing.gtin == data.gtin:
                    raise ValueError(
                        f"Duplicate serial number '{data.serial_number}' for GTIN '{data.gtin}'"
                    )
            self._units[unit_id] = record
        logger.info("Registered serialized unit %s: %s", unit_id, data.serial_number)
        return record

    def update_unit(self, unit_id: str, data: SerializedUnitUpdate) -> SerializedUnit:
        """Update a serialized unit."""
        with self._lock:
            if unit_id not in self._units:
                raise KeyError(f"Serialized unit '{unit_id}' not found")
            existing = self._units[unit_id]
            updates = data.model_dump(exclude_none=True)
            updated = existing.model_copy(update=updates)
            self._units[unit_id] = updated
        logger.info("Updated serialized unit %s", unit_id)
        return updated

    def delete_unit(self, unit_id: str) -> None:
        """Delete a serialized unit."""
        with self._lock:
            if unit_id not in self._units:
                raise KeyError(f"Serialized unit '{unit_id}' not found")
            del self._units[unit_id]
        logger.info("Deleted serialized unit %s", unit_id)

    def get_children(self, unit_id: str) -> list[SerializedUnit]:
        """Get child units in aggregation hierarchy."""
        with self._lock:
            if unit_id not in self._units:
                raise KeyError(f"Serialized unit '{unit_id}' not found")
            return [u for u in self._units.values() if u.parent_id == unit_id]

    # ------------------------------------------------------------------
    # Tracking Events
    # ------------------------------------------------------------------

    def list_tracking_events(
        self,
        unit_id: str | None = None,
        event_type: TrackingEventType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[TrackingEvent], int]:
        """List tracking events with optional filters."""
        with self._lock:
            items = list(self._tracking_events.values())

        if unit_id:
            items = [e for e in items if e.unit_id == unit_id]
        if event_type:
            items = [e for e in items if e.event_type == event_type]

        # Sort by timestamp
        items.sort(key=lambda e: e.timestamp)
        total = len(items)
        items = items[offset: offset + limit]
        return items, total

    def get_tracking_event(self, event_id: str) -> TrackingEvent:
        """Get a single tracking event."""
        with self._lock:
            if event_id not in self._tracking_events:
                raise KeyError(f"Tracking event '{event_id}' not found")
            return self._tracking_events[event_id]

    def record_tracking_event(self, data: TrackingEventCreate) -> TrackingEvent:
        """Record a new tracking event for a serialized unit."""
        event_id = f"TE-{uuid4().hex[:6].upper()}"
        now = datetime.now(timezone.utc)

        with self._lock:
            if data.unit_id not in self._units:
                raise KeyError(f"Serialized unit '{data.unit_id}' not found")

        record = TrackingEvent(
            id=event_id,
            unit_id=data.unit_id,
            event_type=data.event_type,
            timestamp=now,
            location=data.location,
            facility_name=data.facility_name,
            scanned_by=data.scanned_by,
            gps_latitude=data.gps_latitude,
            gps_longitude=data.gps_longitude,
            temperature=data.temperature,
            humidity=data.humidity,
            notes=data.notes,
            transaction_id=data.transaction_id,
        )

        # Update unit status and location based on event type
        status_map = {
            TrackingEventType.SHIPPED: UnitStatus.IN_TRANSIT,
            TrackingEventType.RECEIVED: UnitStatus.ACTIVE,
            TrackingEventType.DISPENSED: UnitStatus.DISPENSED,
            TrackingEventType.RETURNED: UnitStatus.RETURNED,
            TrackingEventType.DESTROYED: UnitStatus.DESTROYED,
            TrackingEventType.RECALLED: UnitStatus.RECALLED,
        }

        with self._lock:
            self._tracking_events[event_id] = record
            unit = self._units[data.unit_id]
            new_status = status_map.get(data.event_type)
            updates: dict = {"last_scan_date": now, "current_location": data.location}
            if new_status:
                updates["status"] = new_status
            self._units[data.unit_id] = unit.model_copy(update=updates)

        logger.info(
            "Recorded tracking event %s (%s) for unit %s",
            event_id, data.event_type.value, data.unit_id,
        )
        return record

    def delete_tracking_event(self, event_id: str) -> None:
        """Delete a tracking event."""
        with self._lock:
            if event_id not in self._tracking_events:
                raise KeyError(f"Tracking event '{event_id}' not found")
            del self._tracking_events[event_id]
        logger.info("Deleted tracking event %s", event_id)

    # ------------------------------------------------------------------
    # Cold Chain Monitoring
    # ------------------------------------------------------------------

    def list_cold_chain_readings(
        self,
        shipment_id: str | None = None,
        status: ColdChainStatus | None = None,
        alert_triggered: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ColdChainReading], int]:
        """List cold chain readings with optional filters."""
        with self._lock:
            items = list(self._cold_chain_readings.values())

        if shipment_id:
            items = [r for r in items if r.shipment_id == shipment_id]
        if status:
            items = [r for r in items if r.status == status]
        if alert_triggered is not None:
            items = [r for r in items if r.alert_triggered == alert_triggered]

        items.sort(key=lambda r: r.timestamp)
        total = len(items)
        items = items[offset: offset + limit]
        return items, total

    def get_cold_chain_reading(self, reading_id: str) -> ColdChainReading:
        """Get a single cold chain reading."""
        with self._lock:
            if reading_id not in self._cold_chain_readings:
                raise KeyError(f"Cold chain reading '{reading_id}' not found")
            return self._cold_chain_readings[reading_id]

    def log_cold_chain(self, data: ColdChainReadingCreate) -> ColdChainReading:
        """Log a cold chain reading with automatic status classification."""
        reading_id = f"CC-{uuid4().hex[:6].upper()}"
        now = datetime.now(timezone.utc)

        status = _classify_cold_chain(data.temperature)
        alert = status != ColdChainStatus.WITHIN_RANGE

        record = ColdChainReading(
            id=reading_id,
            shipment_id=data.shipment_id,
            sensor_id=data.sensor_id,
            timestamp=now,
            temperature=data.temperature,
            humidity=data.humidity,
            location=data.location,
            status=status,
            alert_triggered=alert,
            alert_acknowledged_by=None,
            alert_acknowledged_date=None,
        )
        with self._lock:
            self._cold_chain_readings[reading_id] = record
        logger.info(
            "Logged cold chain reading %s for shipment %s: %.1f C (%s)",
            reading_id, data.shipment_id, data.temperature, status.value,
        )
        return record

    def acknowledge_cold_chain_alert(
        self, reading_id: str, data: ColdChainAcknowledge,
    ) -> ColdChainReading:
        """Acknowledge a cold chain alert."""
        now = datetime.now(timezone.utc)
        with self._lock:
            if reading_id not in self._cold_chain_readings:
                raise KeyError(f"Cold chain reading '{reading_id}' not found")
            existing = self._cold_chain_readings[reading_id]
            if not existing.alert_triggered:
                raise ValueError(f"Reading '{reading_id}' did not trigger an alert")
            if existing.alert_acknowledged_by:
                raise ValueError(f"Alert for reading '{reading_id}' already acknowledged")
            updated = existing.model_copy(update={
                "alert_acknowledged_by": data.acknowledged_by,
                "alert_acknowledged_date": now,
            })
            self._cold_chain_readings[reading_id] = updated
        logger.info("Acknowledged cold chain alert for reading %s", reading_id)
        return updated

    def delete_cold_chain_reading(self, reading_id: str) -> None:
        """Delete a cold chain reading."""
        with self._lock:
            if reading_id not in self._cold_chain_readings:
                raise KeyError(f"Cold chain reading '{reading_id}' not found")
            del self._cold_chain_readings[reading_id]
        logger.info("Deleted cold chain reading %s", reading_id)

    # ------------------------------------------------------------------
    # Compliance
    # ------------------------------------------------------------------

    def list_compliance_records(
        self,
        unit_id: str | None = None,
        standard: ComplianceStandard | None = None,
        compliant: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ComplianceRecord], int]:
        """List compliance records with optional filters."""
        with self._lock:
            items = list(self._compliance_records.values())

        if unit_id:
            items = [c for c in items if c.unit_id == unit_id]
        if standard:
            items = [c for c in items if c.standard == standard]
        if compliant is not None:
            items = [c for c in items if c.compliant == compliant]

        total = len(items)
        items = items[offset: offset + limit]
        return items, total

    def get_compliance_record(self, record_id: str) -> ComplianceRecord:
        """Get a single compliance record."""
        with self._lock:
            if record_id not in self._compliance_records:
                raise KeyError(f"Compliance record '{record_id}' not found")
            return self._compliance_records[record_id]

    def check_compliance(self, data: ComplianceRecordCreate) -> ComplianceRecord:
        """Create a compliance verification record."""
        record_id = f"CR-{uuid4().hex[:6].upper()}"
        now = datetime.now(timezone.utc)

        with self._lock:
            if data.unit_id not in self._units:
                raise KeyError(f"Serialized unit '{data.unit_id}' not found")
            unit = self._units[data.unit_id]

        # Determine compliance: non-quarantined, non-recalled units with valid
        # serial numbers are considered compliant.
        compliant = unit.status not in (UnitStatus.QUARANTINED, UnitStatus.RECALLED)

        record = ComplianceRecord(
            id=record_id,
            unit_id=data.unit_id,
            standard=data.standard,
            country=data.country,
            compliant=compliant,
            verification_date=now,
            verified_by=data.verified_by,
            transaction_information=data.transaction_information,
            transaction_history=data.transaction_history,
            transaction_statement=data.transaction_statement,
            certificate_reference=data.certificate_reference,
        )
        with self._lock:
            self._compliance_records[record_id] = record
        logger.info(
            "Created compliance record %s for unit %s: %s",
            record_id, data.unit_id, "compliant" if compliant else "non-compliant",
        )
        return record

    def delete_compliance_record(self, record_id: str) -> None:
        """Delete a compliance record."""
        with self._lock:
            if record_id not in self._compliance_records:
                raise KeyError(f"Compliance record '{record_id}' not found")
            del self._compliance_records[record_id]
        logger.info("Deleted compliance record %s", record_id)

    # ------------------------------------------------------------------
    # Verification Requests
    # ------------------------------------------------------------------

    def list_verification_requests(
        self,
        verification_status: VerificationStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[VerificationRequest], int]:
        """List verification requests with optional filters."""
        with self._lock:
            items = list(self._verification_requests.values())

        if verification_status:
            items = [v for v in items if v.verification_status == verification_status]

        total = len(items)
        items = items[offset: offset + limit]
        return items, total

    def get_verification_request(self, request_id: str) -> VerificationRequest:
        """Get a single verification request."""
        with self._lock:
            if request_id not in self._verification_requests:
                raise KeyError(f"Verification request '{request_id}' not found")
            return self._verification_requests[request_id]

    def verify_unit(self, data: VerificationRequestCreate) -> VerificationRequest:
        """Submit a verification request and auto-resolve against known serials."""
        request_id = f"VR-{uuid4().hex[:6].upper()}"
        now = datetime.now(timezone.utc)

        # Check if the serial number matches a known unit
        matched_unit: SerializedUnit | None = None
        with self._lock:
            for unit in self._units.values():
                if (
                    unit.gtin == data.gtin
                    and unit.serial_number == data.serial_number
                    and unit.lot_number == data.lot_number
                ):
                    matched_unit = unit
                    break

        if matched_unit is None:
            status = VerificationStatus.SUSPECT
            notes = "Serial number not found in manufacturing database"
            resolution = None
        elif matched_unit.status == UnitStatus.QUARANTINED:
            status = VerificationStatus.QUARANTINED
            notes = "Unit is currently quarantined"
            resolution = None
        elif matched_unit.status == UnitStatus.RECALLED:
            status = VerificationStatus.SUSPECT
            notes = "Unit has been recalled"
            resolution = None
        else:
            status = VerificationStatus.VERIFIED
            notes = None
            resolution = "Product verified as authentic"

        record = VerificationRequest(
            id=request_id,
            requestor=data.requestor,
            request_date=now,
            gtin=data.gtin,
            serial_number=data.serial_number,
            lot_number=data.lot_number,
            verification_status=status,
            response_date=now,
            responder="Serialization VRS System",
            investigation_notes=notes,
            resolution=resolution,
        )
        with self._lock:
            self._verification_requests[request_id] = record
        logger.info(
            "Verification request %s for SN %s: %s",
            request_id, data.serial_number, status.value,
        )
        return record

    def update_verification_request(
        self, request_id: str, data: VerificationRequestUpdate,
    ) -> VerificationRequest:
        """Update a verification request (e.g., resolve investigation)."""
        with self._lock:
            if request_id not in self._verification_requests:
                raise KeyError(f"Verification request '{request_id}' not found")
            existing = self._verification_requests[request_id]
            updates = data.model_dump(exclude_none=True)
            if "response_date" not in updates:
                updates["response_date"] = datetime.now(timezone.utc)
            updated = existing.model_copy(update=updates)
            self._verification_requests[request_id] = updated
        logger.info("Updated verification request %s", request_id)
        return updated

    def delete_verification_request(self, request_id: str) -> None:
        """Delete a verification request."""
        with self._lock:
            if request_id not in self._verification_requests:
                raise KeyError(f"Verification request '{request_id}' not found")
            del self._verification_requests[request_id]
        logger.info("Deleted verification request %s", request_id)

    # ------------------------------------------------------------------
    # Distribution Records
    # ------------------------------------------------------------------

    def list_distribution_records(
        self,
        from_facility: str | None = None,
        to_facility: str | None = None,
        discrepancy: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[DistributionRecord], int]:
        """List distribution records with optional filters."""
        with self._lock:
            items = list(self._distribution_records.values())

        if from_facility:
            items = [d for d in items if d.from_facility == from_facility]
        if to_facility:
            items = [d for d in items if d.to_facility == to_facility]
        if discrepancy is not None:
            items = [d for d in items if d.discrepancy == discrepancy]

        total = len(items)
        items = items[offset: offset + limit]
        return items, total

    def get_distribution_record(self, record_id: str) -> DistributionRecord:
        """Get a single distribution record."""
        with self._lock:
            if record_id not in self._distribution_records:
                raise KeyError(f"Distribution record '{record_id}' not found")
            return self._distribution_records[record_id]

    def create_distribution_record(self, data: DistributionRecordCreate) -> DistributionRecord:
        """Create a new distribution record."""
        record_id = f"DIST-{uuid4().hex[:6].upper()}"
        now = datetime.now(timezone.utc)
        shipment_id = f"SHP-SER-{uuid4().hex[:6].upper()}"

        record = DistributionRecord(
            id=record_id,
            shipment_id=shipment_id,
            from_facility=data.from_facility,
            to_facility=data.to_facility,
            shipped_date=now,
            received_date=None,
            units_shipped=data.units_shipped,
            units_received=None,
            discrepancy=False,
            carrier=data.carrier,
            tracking_number=data.tracking_number,
            chain_of_custody_verified=False,
        )
        with self._lock:
            self._distribution_records[record_id] = record
        logger.info(
            "Created distribution record %s: %s -> %s",
            record_id, data.from_facility, data.to_facility,
        )
        return record

    def update_distribution_record(
        self, record_id: str, data: DistributionRecordUpdate,
    ) -> DistributionRecord:
        """Update a distribution record (e.g., record receipt)."""
        with self._lock:
            if record_id not in self._distribution_records:
                raise KeyError(f"Distribution record '{record_id}' not found")
            existing = self._distribution_records[record_id]
            updates = data.model_dump(exclude_none=True)

            # Auto-detect discrepancy
            units_received = updates.get("units_received", existing.units_received)
            if units_received is not None and units_received != existing.units_shipped:
                updates["discrepancy"] = True
            elif units_received is not None:
                updates["discrepancy"] = False

            updated = existing.model_copy(update=updates)
            self._distribution_records[record_id] = updated
        logger.info("Updated distribution record %s", record_id)
        return updated

    def delete_distribution_record(self, record_id: str) -> None:
        """Delete a distribution record."""
        with self._lock:
            if record_id not in self._distribution_records:
                raise KeyError(f"Distribution record '{record_id}' not found")
            del self._distribution_records[record_id]
        logger.info("Deleted distribution record %s", record_id)

    # ------------------------------------------------------------------
    # Unit History Trace
    # ------------------------------------------------------------------

    def trace_unit_history(self, unit_id: str) -> UnitTraceResponse:
        """Build a full history trace for a serialized unit."""
        with self._lock:
            if unit_id not in self._units:
                raise KeyError(f"Serialized unit '{unit_id}' not found")
            unit = self._units[unit_id]

            events = sorted(
                [e for e in self._tracking_events.values() if e.unit_id == unit_id],
                key=lambda e: e.timestamp,
            )

            # Find related distribution record IDs and shipment IDs from
            # distribution records where unit's tracking events overlap with
            # distribution facility locations.
            related_ids: set[str] = set()
            event_locations = {e.location for e in events}
            for dist in self._distribution_records.values():
                if dist.from_facility in event_locations or dist.to_facility in event_locations:
                    related_ids.add(dist.id)
                    related_ids.add(dist.shipment_id)

            cold_chain = sorted(
                [
                    r for r in self._cold_chain_readings.values()
                    if r.shipment_id in related_ids
                ],
                key=lambda r: r.timestamp,
            )

            compliance = [
                c for c in self._compliance_records.values()
                if c.unit_id == unit_id
            ]

            verifications = [
                v for v in self._verification_requests.values()
                if v.serial_number == unit.serial_number and v.gtin == unit.gtin
            ]

            children = [u for u in self._units.values() if u.parent_id == unit_id]

        return UnitTraceResponse(
            unit=unit,
            events=events,
            cold_chain_readings=cold_chain,
            compliance_records=compliance,
            verification_requests=verifications,
            children=children,
        )

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> SerializationMetrics:
        """Calculate aggregated serialization and track-and-trace metrics."""
        with self._lock:
            units = list(self._units.values())
            events = list(self._tracking_events.values())
            readings = list(self._cold_chain_readings.values())
            compliance = list(self._compliance_records.values())
            verifications = list(self._verification_requests.values())
            distributions = list(self._distribution_records.values())

        # Units by level
        units_by_level: dict[str, int] = {}
        for u in units:
            level = u.serialization_level.value
            units_by_level[level] = units_by_level.get(level, 0) + 1

        # Units by status
        units_by_status: dict[str, int] = {}
        for u in units:
            s = u.status.value
            units_by_status[s] = units_by_status.get(s, 0) + 1

        # Cold chain alerts
        cold_chain_alerts = sum(1 for r in readings if r.alert_triggered)

        # Compliance rate
        if compliance:
            compliance_rate = round(
                (sum(1 for c in compliance if c.compliant) / len(compliance)) * 100, 2,
            )
        else:
            compliance_rate = 100.0

        # Suspect / counterfeit
        suspect_count = sum(
            1
            for v in verifications
            if v.verification_status in (
                VerificationStatus.SUSPECT,
                VerificationStatus.CONFIRMED_COUNTERFEIT,
            )
        )

        # Distribution discrepancies
        dist_discrepancies = sum(1 for d in distributions if d.discrepancy)

        # Dispensed and recalled
        units_dispensed = sum(1 for u in units if u.status == UnitStatus.DISPENSED)
        units_recalled = sum(1 for u in units if u.status == UnitStatus.RECALLED)

        return SerializationMetrics(
            total_serialized_units=len(units),
            units_by_level=units_by_level,
            units_by_status=units_by_status,
            total_tracking_events=len(events),
            total_cold_chain_readings=len(readings),
            cold_chain_alerts=cold_chain_alerts,
            total_compliance_records=len(compliance),
            compliance_rate=compliance_rate,
            total_verification_requests=len(verifications),
            suspect_or_counterfeit=suspect_count,
            total_distribution_records=len(distributions),
            distribution_discrepancies=dist_discrepancies,
            units_dispensed=units_dispensed,
            units_recalled=units_recalled,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: SupplySerializationService | None = None
_instance_lock = threading.Lock()


def get_supply_serialization_service() -> SupplySerializationService:
    """Return the singleton SupplySerializationService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = SupplySerializationService()
    return _instance


def reset_supply_serialization_service() -> SupplySerializationService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = SupplySerializationService()
    return _instance
