"""Specimen Management Service (SPEC-MGT).

Manages specimen management operations: collection tracking, storage
inventory, chain of custody records, shipping logistics, and specimen
quality control with specimen metrics.

Usage:
    from app.services.specimen_management_service import (
        get_specimen_management_service,
    )

    svc = get_specimen_management_service()
    collections = svc.list_collection_records()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.specimen_management import (
    ChainOfCustody,
    ChainOfCustodyCreate,
    ChainOfCustodyUpdate,
    CollectionRecord,
    CollectionRecordCreate,
    CollectionRecordUpdate,
    CollectionStatus,
    QCResult,
    ShippingLogistic,
    ShippingLogisticCreate,
    ShippingLogisticUpdate,
    ShippingStatus,
    SpecimenManagementMetrics,
    SpecimenQC,
    SpecimenQCCreate,
    SpecimenQCUpdate,
    SpecimenType,
    StorageCondition,
    StorageInventory,
    StorageInventoryCreate,
    StorageInventoryUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class SpecimenManagementService:
    """In-memory Specimen Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._collection_records: dict[str, CollectionRecord] = {}
        self._storage_inventory: dict[str, StorageInventory] = {}
        self._chain_of_custody: dict[str, ChainOfCustody] = {}
        self._shipping_logistics: dict[str, ShippingLogistic] = {}
        self._specimen_qc: dict[str, SpecimenQC] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic specimen management data."""
        now = datetime.now(timezone.utc)

        # --- 12 Collection Records ---
        collections_data = [
            {
                "id": "COL-001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E001",
                "site_id": "SITE-NY-001",
                "specimen_type": SpecimenType.BLOOD,
                "collection_status": CollectionStatus.COLLECTED,
                "visit_number": 1,
                "collection_date": now - timedelta(days=90),
                "scheduled_date": now - timedelta(days=91),
                "tube_count": 4,
                "volume_ml": 20.0,
                "fasting_required": True,
                "fasting_confirmed": True,
                "collection_time_critical": True,
                "protocol_timepoint": "Screening",
                "collected_by": "Nurse Patricia Wells",
                "notes": "Collected per protocol. All 4 tubes filled successfully.",
                "created_at": now - timedelta(days=91),
            },
            {
                "id": "COL-002",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E001",
                "site_id": "SITE-NY-001",
                "specimen_type": SpecimenType.SERUM,
                "collection_status": CollectionStatus.COLLECTED,
                "visit_number": 2,
                "collection_date": now - timedelta(days=60),
                "scheduled_date": now - timedelta(days=60),
                "tube_count": 2,
                "volume_ml": 10.0,
                "fasting_required": False,
                "fasting_confirmed": False,
                "collection_time_critical": False,
                "protocol_timepoint": "Week 4",
                "collected_by": "Nurse Patricia Wells",
                "notes": "Routine Week 4 serum draw.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "COL-003",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E002",
                "site_id": "SITE-NY-001",
                "specimen_type": SpecimenType.PLASMA,
                "collection_status": CollectionStatus.COLLECTED,
                "visit_number": 1,
                "collection_date": now - timedelta(days=85),
                "scheduled_date": now - timedelta(days=86),
                "tube_count": 3,
                "volume_ml": 15.0,
                "fasting_required": True,
                "fasting_confirmed": True,
                "collection_time_critical": True,
                "protocol_timepoint": "Screening",
                "collected_by": "Nurse James Rodriguez",
                "notes": "Plasma collected within protocol window.",
                "created_at": now - timedelta(days=86),
            },
            {
                "id": "COL-004",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E003",
                "site_id": "SITE-LA-001",
                "specimen_type": SpecimenType.URINE,
                "collection_status": CollectionStatus.MISSED,
                "visit_number": 3,
                "collection_date": None,
                "scheduled_date": now - timedelta(days=30),
                "tube_count": 1,
                "volume_ml": 0.0,
                "fasting_required": False,
                "fasting_confirmed": False,
                "collection_time_critical": False,
                "protocol_timepoint": "Week 8",
                "collected_by": None,
                "notes": "Subject did not attend visit. Rescheduling attempted.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "COL-005",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D001",
                "site_id": "SITE-CHI-001",
                "specimen_type": SpecimenType.BLOOD,
                "collection_status": CollectionStatus.COLLECTED,
                "visit_number": 1,
                "collection_date": now - timedelta(days=75),
                "scheduled_date": now - timedelta(days=75),
                "tube_count": 6,
                "volume_ml": 30.0,
                "fasting_required": True,
                "fasting_confirmed": True,
                "collection_time_critical": True,
                "protocol_timepoint": "Baseline",
                "collected_by": "Nurse Karen Liu",
                "notes": "Full baseline panel. All PK and biomarker tubes collected.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "COL-006",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D002",
                "site_id": "SITE-CHI-001",
                "specimen_type": SpecimenType.TISSUE,
                "collection_status": CollectionStatus.COLLECTED,
                "visit_number": 2,
                "collection_date": now - timedelta(days=50),
                "scheduled_date": now - timedelta(days=51),
                "tube_count": 2,
                "volume_ml": 0.5,
                "fasting_required": False,
                "fasting_confirmed": False,
                "collection_time_critical": False,
                "protocol_timepoint": "Week 4",
                "collected_by": "Dr. Michael Torres",
                "notes": "Skin biopsy collected per protocol. Two punch biopsies.",
                "created_at": now - timedelta(days=51),
            },
            {
                "id": "COL-007",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D001",
                "site_id": "SITE-CHI-001",
                "specimen_type": SpecimenType.SERUM,
                "collection_status": CollectionStatus.PARTIAL,
                "visit_number": 3,
                "collection_date": now - timedelta(days=40),
                "scheduled_date": now - timedelta(days=40),
                "tube_count": 1,
                "volume_ml": 3.0,
                "fasting_required": False,
                "fasting_confirmed": False,
                "collection_time_critical": False,
                "protocol_timepoint": "Week 8",
                "collected_by": "Nurse Karen Liu",
                "notes": "Difficult venipuncture. Only 1 of 3 tubes obtained. Recollection may be needed.",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "COL-008",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D003",
                "site_id": "SITE-BOS-001",
                "specimen_type": SpecimenType.BLOOD,
                "collection_status": CollectionStatus.SCHEDULED,
                "visit_number": 1,
                "collection_date": None,
                "scheduled_date": now + timedelta(days=5),
                "tube_count": 4,
                "volume_ml": 0.0,
                "fasting_required": True,
                "fasting_confirmed": False,
                "collection_time_critical": True,
                "protocol_timepoint": "Screening",
                "collected_by": None,
                "notes": "Upcoming screening visit blood draw.",
                "created_at": now - timedelta(days=2),
            },
            {
                "id": "COL-009",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L001",
                "site_id": "SITE-HOU-001",
                "specimen_type": SpecimenType.BLOOD,
                "collection_status": CollectionStatus.COLLECTED,
                "visit_number": 1,
                "collection_date": now - timedelta(days=70),
                "scheduled_date": now - timedelta(days=70),
                "tube_count": 8,
                "volume_ml": 40.0,
                "fasting_required": True,
                "fasting_confirmed": True,
                "collection_time_critical": True,
                "protocol_timepoint": "Baseline",
                "collected_by": "Nurse David Park",
                "notes": "Complete baseline panel including immune profiling tubes.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "COL-010",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L002",
                "site_id": "SITE-HOU-001",
                "specimen_type": SpecimenType.CSF,
                "collection_status": CollectionStatus.COLLECTED,
                "visit_number": 2,
                "collection_date": now - timedelta(days=45),
                "scheduled_date": now - timedelta(days=45),
                "tube_count": 3,
                "volume_ml": 5.0,
                "fasting_required": False,
                "fasting_confirmed": False,
                "collection_time_critical": True,
                "protocol_timepoint": "Week 6",
                "collected_by": "Dr. Angela Martinez",
                "notes": "CSF collected via lumbar puncture. No complications.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "COL-011",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L003",
                "site_id": "SITE-SEA-001",
                "specimen_type": SpecimenType.PLASMA,
                "collection_status": CollectionStatus.RECOLLECTION_NEEDED,
                "visit_number": 1,
                "collection_date": now - timedelta(days=55),
                "scheduled_date": now - timedelta(days=56),
                "tube_count": 3,
                "volume_ml": 8.0,
                "fasting_required": True,
                "fasting_confirmed": False,
                "collection_time_critical": True,
                "protocol_timepoint": "Screening",
                "collected_by": "Nurse Sarah Kim",
                "notes": "Fasting not confirmed. QC flagged hemolyzed sample. Recollection required.",
                "created_at": now - timedelta(days=56),
            },
            {
                "id": "COL-012",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L001",
                "site_id": "SITE-HOU-001",
                "specimen_type": SpecimenType.URINE,
                "collection_status": CollectionStatus.CANCELLED,
                "visit_number": 3,
                "collection_date": None,
                "scheduled_date": now - timedelta(days=20),
                "tube_count": 1,
                "volume_ml": 0.0,
                "fasting_required": False,
                "fasting_confirmed": False,
                "collection_time_critical": False,
                "protocol_timepoint": "Week 12",
                "collected_by": None,
                "notes": "Visit cancelled due to protocol amendment removing this timepoint.",
                "created_at": now - timedelta(days=20),
            },
        ]

        for c in collections_data:
            self._collection_records[c["id"]] = CollectionRecord(**c)

        # --- 12 Storage Inventory Records ---
        storage_data = [
            {
                "id": "STR-001",
                "trial_id": EYLEA_TRIAL,
                "specimen_id": "COL-001",
                "storage_condition": StorageCondition.FROZEN_MINUS_80,
                "freezer_id": "FRZ-NY-001",
                "rack_position": "R01",
                "box_number": "B001",
                "slot_number": "A1",
                "aliquot_number": 1,
                "volume_remaining_ml": 5.0,
                "date_stored": now - timedelta(days=90),
                "expiry_date": now + timedelta(days=365),
                "is_available": True,
                "thaw_count": 0,
                "max_thaw_cycles": 3,
                "managed_by": "Lab Tech Maria Santos",
                "notes": "Primary aliquot stored per SOP.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "STR-002",
                "trial_id": EYLEA_TRIAL,
                "specimen_id": "COL-001",
                "storage_condition": StorageCondition.FROZEN_MINUS_80,
                "freezer_id": "FRZ-NY-001",
                "rack_position": "R01",
                "box_number": "B001",
                "slot_number": "A2",
                "aliquot_number": 2,
                "volume_remaining_ml": 5.0,
                "date_stored": now - timedelta(days=90),
                "expiry_date": now + timedelta(days=365),
                "is_available": True,
                "thaw_count": 0,
                "max_thaw_cycles": 3,
                "managed_by": "Lab Tech Maria Santos",
                "notes": "Backup aliquot.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "STR-003",
                "trial_id": EYLEA_TRIAL,
                "specimen_id": "COL-002",
                "storage_condition": StorageCondition.FROZEN_MINUS_20,
                "freezer_id": "FRZ-NY-002",
                "rack_position": "R03",
                "box_number": "B010",
                "slot_number": "C5",
                "aliquot_number": 1,
                "volume_remaining_ml": 8.0,
                "date_stored": now - timedelta(days=59),
                "expiry_date": now + timedelta(days=180),
                "is_available": True,
                "thaw_count": 1,
                "max_thaw_cycles": 3,
                "managed_by": "Lab Tech Maria Santos",
                "notes": "One thaw for routine testing.",
                "created_at": now - timedelta(days=59),
            },
            {
                "id": "STR-004",
                "trial_id": EYLEA_TRIAL,
                "specimen_id": "COL-003",
                "storage_condition": StorageCondition.FROZEN_MINUS_80,
                "freezer_id": "FRZ-NY-001",
                "rack_position": "R02",
                "box_number": "B002",
                "slot_number": "B3",
                "aliquot_number": 1,
                "volume_remaining_ml": 12.0,
                "date_stored": now - timedelta(days=85),
                "expiry_date": now + timedelta(days=365),
                "is_available": False,
                "thaw_count": 3,
                "max_thaw_cycles": 3,
                "managed_by": "Lab Tech John Reeves",
                "notes": "Maximum thaw cycles reached. No longer suitable for PK analysis.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "STR-005",
                "trial_id": DUPIXENT_TRIAL,
                "specimen_id": "COL-005",
                "storage_condition": StorageCondition.LIQUID_NITROGEN,
                "freezer_id": "LN2-CHI-001",
                "rack_position": "R01",
                "box_number": "B100",
                "slot_number": "D1",
                "aliquot_number": 1,
                "volume_remaining_ml": 10.0,
                "date_stored": now - timedelta(days=74),
                "expiry_date": now + timedelta(days=730),
                "is_available": True,
                "thaw_count": 0,
                "max_thaw_cycles": 1,
                "managed_by": "Lab Tech Rachel Green",
                "notes": "PBMC sample for immune profiling. Single thaw only.",
                "created_at": now - timedelta(days=74),
            },
            {
                "id": "STR-006",
                "trial_id": DUPIXENT_TRIAL,
                "specimen_id": "COL-006",
                "storage_condition": StorageCondition.FROZEN_MINUS_80,
                "freezer_id": "FRZ-CHI-001",
                "rack_position": "R05",
                "box_number": "B050",
                "slot_number": "E2",
                "aliquot_number": 1,
                "volume_remaining_ml": 0.3,
                "date_stored": now - timedelta(days=50),
                "expiry_date": now + timedelta(days=365),
                "is_available": True,
                "thaw_count": 0,
                "max_thaw_cycles": 2,
                "managed_by": "Lab Tech Rachel Green",
                "notes": "Tissue biopsy preserved in OCT medium.",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "STR-007",
                "trial_id": DUPIXENT_TRIAL,
                "specimen_id": "COL-005",
                "storage_condition": StorageCondition.FROZEN_MINUS_80,
                "freezer_id": "FRZ-CHI-001",
                "rack_position": "R01",
                "box_number": "B101",
                "slot_number": "D2",
                "aliquot_number": 2,
                "volume_remaining_ml": 8.0,
                "date_stored": now - timedelta(days=74),
                "expiry_date": now + timedelta(days=365),
                "is_available": True,
                "thaw_count": 0,
                "max_thaw_cycles": 3,
                "managed_by": "Lab Tech Rachel Green",
                "notes": "Serum aliquot from baseline PK draw.",
                "created_at": now - timedelta(days=74),
            },
            {
                "id": "STR-008",
                "trial_id": DUPIXENT_TRIAL,
                "specimen_id": "COL-007",
                "storage_condition": StorageCondition.REFRIGERATED,
                "freezer_id": "REF-CHI-001",
                "rack_position": "R02",
                "box_number": "B200",
                "slot_number": "A1",
                "aliquot_number": 1,
                "volume_remaining_ml": 2.5,
                "date_stored": now - timedelta(days=39),
                "expiry_date": now + timedelta(days=7),
                "is_available": True,
                "thaw_count": 0,
                "max_thaw_cycles": 5,
                "managed_by": "Lab Tech Rachel Green",
                "notes": "Short-term refrigerated storage pending analysis. Expiring soon.",
                "created_at": now - timedelta(days=39),
            },
            {
                "id": "STR-009",
                "trial_id": LIBTAYO_TRIAL,
                "specimen_id": "COL-009",
                "storage_condition": StorageCondition.FROZEN_MINUS_80,
                "freezer_id": "FRZ-HOU-001",
                "rack_position": "R01",
                "box_number": "B300",
                "slot_number": "A1",
                "aliquot_number": 1,
                "volume_remaining_ml": 15.0,
                "date_stored": now - timedelta(days=69),
                "expiry_date": now + timedelta(days=365),
                "is_available": True,
                "thaw_count": 0,
                "max_thaw_cycles": 3,
                "managed_by": "Lab Tech Kevin Owens",
                "notes": "Baseline immune panel aliquot.",
                "created_at": now - timedelta(days=69),
            },
            {
                "id": "STR-010",
                "trial_id": LIBTAYO_TRIAL,
                "specimen_id": "COL-010",
                "storage_condition": StorageCondition.FROZEN_MINUS_80,
                "freezer_id": "FRZ-HOU-001",
                "rack_position": "R02",
                "box_number": "B301",
                "slot_number": "B1",
                "aliquot_number": 1,
                "volume_remaining_ml": 3.0,
                "date_stored": now - timedelta(days=44),
                "expiry_date": now + timedelta(days=365),
                "is_available": True,
                "thaw_count": 0,
                "max_thaw_cycles": 2,
                "managed_by": "Lab Tech Kevin Owens",
                "notes": "CSF specimen for CNS biomarker analysis.",
                "created_at": now - timedelta(days=44),
            },
            {
                "id": "STR-011",
                "trial_id": LIBTAYO_TRIAL,
                "specimen_id": "COL-009",
                "storage_condition": StorageCondition.LIQUID_NITROGEN,
                "freezer_id": "LN2-HOU-001",
                "rack_position": "R01",
                "box_number": "B400",
                "slot_number": "C1",
                "aliquot_number": 2,
                "volume_remaining_ml": 10.0,
                "date_stored": now - timedelta(days=69),
                "expiry_date": now + timedelta(days=730),
                "is_available": True,
                "thaw_count": 0,
                "max_thaw_cycles": 1,
                "managed_by": "Lab Tech Kevin Owens",
                "notes": "PBMC cryopreserved for flow cytometry sub-study.",
                "created_at": now - timedelta(days=69),
            },
            {
                "id": "STR-012",
                "trial_id": LIBTAYO_TRIAL,
                "specimen_id": "COL-011",
                "storage_condition": StorageCondition.ROOM_TEMP,
                "freezer_id": "BENCH-SEA-001",
                "rack_position": "R01",
                "box_number": "B500",
                "slot_number": "A1",
                "aliquot_number": 1,
                "volume_remaining_ml": 6.0,
                "date_stored": now - timedelta(days=54),
                "expiry_date": now - timedelta(days=50),
                "is_available": False,
                "thaw_count": 0,
                "max_thaw_cycles": 3,
                "managed_by": "Lab Tech Amy Chen",
                "notes": "Flagged specimen. Hemolyzed sample held pending recollection decision.",
                "created_at": now - timedelta(days=54),
            },
        ]

        for s in storage_data:
            self._storage_inventory[s["id"]] = StorageInventory(**s)

        # --- 12 Chain of Custody Records ---
        custody_data = [
            {
                "id": "COC-001",
                "trial_id": EYLEA_TRIAL,
                "specimen_id": "COL-001",
                "custody_event": "collection_to_processing",
                "event_date": now - timedelta(days=90),
                "from_location": "Phlebotomy Room A",
                "to_location": "Central Processing Lab",
                "from_person": "Nurse Patricia Wells",
                "to_person": "Lab Tech Maria Santos",
                "temperature_at_transfer": 22.5,
                "temperature_within_range": True,
                "condition_at_transfer": "acceptable",
                "witnessed": True,
                "witness_name": "Nurse James Rodriguez",
                "documentation_complete": True,
                "recorded_by": "Lab Tech Maria Santos",
                "notes": "Specimens transferred within 30 minutes of collection.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "COC-002",
                "trial_id": EYLEA_TRIAL,
                "specimen_id": "COL-001",
                "custody_event": "processing_to_storage",
                "event_date": now - timedelta(days=90),
                "from_location": "Central Processing Lab",
                "to_location": "Freezer Room FRZ-NY-001",
                "from_person": "Lab Tech Maria Santos",
                "to_person": "Lab Tech Maria Santos",
                "temperature_at_transfer": -78.5,
                "temperature_within_range": True,
                "condition_at_transfer": "acceptable",
                "witnessed": False,
                "witness_name": None,
                "documentation_complete": True,
                "recorded_by": "Lab Tech Maria Santos",
                "notes": "Aliquots placed in -80C freezer within 2 hours of processing.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "COC-003",
                "trial_id": EYLEA_TRIAL,
                "specimen_id": "COL-002",
                "custody_event": "collection_to_processing",
                "event_date": now - timedelta(days=60),
                "from_location": "Phlebotomy Room B",
                "to_location": "Central Processing Lab",
                "from_person": "Nurse Patricia Wells",
                "to_person": "Lab Tech John Reeves",
                "temperature_at_transfer": 23.0,
                "temperature_within_range": True,
                "condition_at_transfer": "acceptable",
                "witnessed": True,
                "witness_name": "Nurse Patricia Wells",
                "documentation_complete": True,
                "recorded_by": "Lab Tech John Reeves",
                "notes": "Standard transfer protocol followed.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "COC-004",
                "trial_id": EYLEA_TRIAL,
                "specimen_id": "COL-003",
                "custody_event": "collection_to_processing",
                "event_date": now - timedelta(days=85),
                "from_location": "Phlebotomy Room A",
                "to_location": "Central Processing Lab",
                "from_person": "Nurse James Rodriguez",
                "to_person": "Lab Tech Maria Santos",
                "temperature_at_transfer": 24.0,
                "temperature_within_range": False,
                "condition_at_transfer": "warm",
                "witnessed": True,
                "witness_name": "Lab Tech John Reeves",
                "documentation_complete": True,
                "recorded_by": "Lab Tech Maria Santos",
                "notes": "Slightly above acceptable range. Deviation documented. Processed immediately.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "COC-005",
                "trial_id": DUPIXENT_TRIAL,
                "specimen_id": "COL-005",
                "custody_event": "collection_to_processing",
                "event_date": now - timedelta(days=75),
                "from_location": "Phlebotomy Room C",
                "to_location": "Central Lab Chicago",
                "from_person": "Nurse Karen Liu",
                "to_person": "Lab Tech Rachel Green",
                "temperature_at_transfer": 21.0,
                "temperature_within_range": True,
                "condition_at_transfer": "acceptable",
                "witnessed": True,
                "witness_name": "Nurse Karen Liu",
                "documentation_complete": True,
                "recorded_by": "Lab Tech Rachel Green",
                "notes": "Baseline specimens processed within protocol time window.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "COC-006",
                "trial_id": DUPIXENT_TRIAL,
                "specimen_id": "COL-005",
                "custody_event": "processing_to_storage",
                "event_date": now - timedelta(days=74),
                "from_location": "Central Lab Chicago",
                "to_location": "LN2 Facility LN2-CHI-001",
                "from_person": "Lab Tech Rachel Green",
                "to_person": "Lab Tech Rachel Green",
                "temperature_at_transfer": -195.0,
                "temperature_within_range": True,
                "condition_at_transfer": "acceptable",
                "witnessed": False,
                "witness_name": None,
                "documentation_complete": True,
                "recorded_by": "Lab Tech Rachel Green",
                "notes": "PBMCs viably frozen in LN2 vapor phase storage.",
                "created_at": now - timedelta(days=74),
            },
            {
                "id": "COC-007",
                "trial_id": DUPIXENT_TRIAL,
                "specimen_id": "COL-006",
                "custody_event": "collection_to_processing",
                "event_date": now - timedelta(days=50),
                "from_location": "Procedure Room 2",
                "to_location": "Histology Lab Chicago",
                "from_person": "Dr. Michael Torres",
                "to_person": "Lab Tech Rachel Green",
                "temperature_at_transfer": 22.0,
                "temperature_within_range": True,
                "condition_at_transfer": "acceptable",
                "witnessed": True,
                "witness_name": "Nurse Karen Liu",
                "documentation_complete": True,
                "recorded_by": "Lab Tech Rachel Green",
                "notes": "Tissue biopsy transported in fixative. Chain maintained.",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "COC-008",
                "trial_id": DUPIXENT_TRIAL,
                "specimen_id": "COL-007",
                "custody_event": "collection_to_processing",
                "event_date": now - timedelta(days=40),
                "from_location": "Phlebotomy Room C",
                "to_location": "Central Lab Chicago",
                "from_person": "Nurse Karen Liu",
                "to_person": "Lab Tech Rachel Green",
                "temperature_at_transfer": 25.5,
                "temperature_within_range": False,
                "condition_at_transfer": "warm",
                "witnessed": False,
                "witness_name": None,
                "documentation_complete": False,
                "recorded_by": "Lab Tech Rachel Green",
                "notes": "Partial collection. Temperature slightly elevated. Documentation pending.",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "COC-009",
                "trial_id": LIBTAYO_TRIAL,
                "specimen_id": "COL-009",
                "custody_event": "collection_to_processing",
                "event_date": now - timedelta(days=70),
                "from_location": "Phlebotomy Suite Houston",
                "to_location": "Central Lab Houston",
                "from_person": "Nurse David Park",
                "to_person": "Lab Tech Kevin Owens",
                "temperature_at_transfer": 21.5,
                "temperature_within_range": True,
                "condition_at_transfer": "acceptable",
                "witnessed": True,
                "witness_name": "Nurse David Park",
                "documentation_complete": True,
                "recorded_by": "Lab Tech Kevin Owens",
                "notes": "Full baseline panel transferred. All 8 tubes accounted for.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "COC-010",
                "trial_id": LIBTAYO_TRIAL,
                "specimen_id": "COL-010",
                "custody_event": "collection_to_processing",
                "event_date": now - timedelta(days=45),
                "from_location": "Procedure Room LP-1",
                "to_location": "Central Lab Houston",
                "from_person": "Dr. Angela Martinez",
                "to_person": "Lab Tech Kevin Owens",
                "temperature_at_transfer": 4.0,
                "temperature_within_range": True,
                "condition_at_transfer": "acceptable",
                "witnessed": True,
                "witness_name": "Nurse David Park",
                "documentation_complete": True,
                "recorded_by": "Lab Tech Kevin Owens",
                "notes": "CSF transported on ice per protocol. Processed within 1 hour.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "COC-011",
                "trial_id": LIBTAYO_TRIAL,
                "specimen_id": "COL-009",
                "custody_event": "storage_to_shipping",
                "event_date": now - timedelta(days=30),
                "from_location": "Freezer Room FRZ-HOU-001",
                "to_location": "Shipping Dock Houston",
                "from_person": "Lab Tech Kevin Owens",
                "to_person": "Shipping Coord Tom Bradley",
                "temperature_at_transfer": -75.0,
                "temperature_within_range": True,
                "condition_at_transfer": "acceptable",
                "witnessed": True,
                "witness_name": "Lab Tech Amy Chen",
                "documentation_complete": True,
                "recorded_by": "Shipping Coord Tom Bradley",
                "notes": "Specimens packed on dry ice for central lab shipment.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "COC-012",
                "trial_id": LIBTAYO_TRIAL,
                "specimen_id": "COL-011",
                "custody_event": "collection_to_processing",
                "event_date": now - timedelta(days=55),
                "from_location": "Phlebotomy Room Seattle",
                "to_location": "Site Lab Seattle",
                "from_person": "Nurse Sarah Kim",
                "to_person": "Lab Tech Amy Chen",
                "temperature_at_transfer": 26.0,
                "temperature_within_range": False,
                "condition_at_transfer": "warm",
                "witnessed": False,
                "witness_name": None,
                "documentation_complete": True,
                "recorded_by": "Lab Tech Amy Chen",
                "notes": "Temperature excursion noted. Sample visibly hemolyzed. QC review initiated.",
                "created_at": now - timedelta(days=55),
            },
        ]

        for coc in custody_data:
            self._chain_of_custody[coc["id"]] = ChainOfCustody(**coc)

        # --- 12 Shipping Logistics Records ---
        shipping_data = [
            {
                "id": "SHP-001",
                "trial_id": EYLEA_TRIAL,
                "shipment_number": "EYLEA-SHP-2025-001",
                "shipping_status": ShippingStatus.DELIVERED,
                "origin_site": "SITE-NY-001",
                "destination_site": "Central Lab Reference",
                "specimen_count": 8,
                "shipping_condition": StorageCondition.DRY_ICE,
                "carrier_name": "World Courier",
                "tracking_number": "WC-2025-NY-00142",
                "ship_date": now - timedelta(days=85),
                "expected_delivery_date": now - timedelta(days=83),
                "actual_delivery_date": now - timedelta(days=83),
                "temperature_monitored": True,
                "temperature_excursion": False,
                "excursion_duration_minutes": 0,
                "prepared_by": "Lab Tech Maria Santos",
                "received_by": "Central Lab Receiving",
                "notes": "Routine shipment. All specimens received in acceptable condition.",
                "created_at": now - timedelta(days=86),
            },
            {
                "id": "SHP-002",
                "trial_id": EYLEA_TRIAL,
                "shipment_number": "EYLEA-SHP-2025-002",
                "shipping_status": ShippingStatus.DELIVERED,
                "origin_site": "SITE-LA-001",
                "destination_site": "Central Lab Reference",
                "specimen_count": 4,
                "shipping_condition": StorageCondition.DRY_ICE,
                "carrier_name": "World Courier",
                "tracking_number": "WC-2025-LA-00087",
                "ship_date": now - timedelta(days=55),
                "expected_delivery_date": now - timedelta(days=53),
                "actual_delivery_date": now - timedelta(days=52),
                "temperature_monitored": True,
                "temperature_excursion": True,
                "excursion_duration_minutes": 45,
                "prepared_by": "Lab Tech John Reeves",
                "received_by": "Central Lab Receiving",
                "notes": "Brief temperature excursion during transit. Dry ice depleted partially. QC review required.",
                "created_at": now - timedelta(days=56),
            },
            {
                "id": "SHP-003",
                "trial_id": EYLEA_TRIAL,
                "shipment_number": "EYLEA-SHP-2025-003",
                "shipping_status": ShippingStatus.IN_TRANSIT,
                "origin_site": "SITE-NY-001",
                "destination_site": "Bioanalytical Lab East",
                "specimen_count": 6,
                "shipping_condition": StorageCondition.FROZEN_MINUS_80,
                "carrier_name": "Marken",
                "tracking_number": "MK-2025-0298",
                "ship_date": now - timedelta(days=2),
                "expected_delivery_date": now + timedelta(days=1),
                "actual_delivery_date": None,
                "temperature_monitored": True,
                "temperature_excursion": False,
                "excursion_duration_minutes": 0,
                "prepared_by": "Lab Tech Maria Santos",
                "received_by": None,
                "notes": "PK samples for bioanalytical testing. Currently in transit.",
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "SHP-004",
                "trial_id": EYLEA_TRIAL,
                "shipment_number": "EYLEA-SHP-2025-004",
                "shipping_status": ShippingStatus.PENDING,
                "origin_site": "SITE-NY-001",
                "destination_site": "Central Lab Reference",
                "specimen_count": 3,
                "shipping_condition": StorageCondition.DRY_ICE,
                "carrier_name": "World Courier",
                "tracking_number": None,
                "ship_date": None,
                "expected_delivery_date": now + timedelta(days=5),
                "actual_delivery_date": None,
                "temperature_monitored": True,
                "temperature_excursion": False,
                "excursion_duration_minutes": 0,
                "prepared_by": "Lab Tech John Reeves",
                "received_by": None,
                "notes": "Awaiting pickup. Specimens packed and ready.",
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "SHP-005",
                "trial_id": DUPIXENT_TRIAL,
                "shipment_number": "DUP-SHP-2025-001",
                "shipping_status": ShippingStatus.DELIVERED,
                "origin_site": "SITE-CHI-001",
                "destination_site": "Central Lab Immunology",
                "specimen_count": 10,
                "shipping_condition": StorageCondition.LIQUID_NITROGEN,
                "carrier_name": "Cryoport",
                "tracking_number": "CP-2025-CHI-00312",
                "ship_date": now - timedelta(days=65),
                "expected_delivery_date": now - timedelta(days=63),
                "actual_delivery_date": now - timedelta(days=63),
                "temperature_monitored": True,
                "temperature_excursion": False,
                "excursion_duration_minutes": 0,
                "prepared_by": "Lab Tech Rachel Green",
                "received_by": "Central Immunology Lab",
                "notes": "LN2 dry shipper. All PBMC vials received viable.",
                "created_at": now - timedelta(days=66),
            },
            {
                "id": "SHP-006",
                "trial_id": DUPIXENT_TRIAL,
                "shipment_number": "DUP-SHP-2025-002",
                "shipping_status": ShippingStatus.DELIVERED,
                "origin_site": "SITE-CHI-001",
                "destination_site": "Histopathology Lab East",
                "specimen_count": 4,
                "shipping_condition": StorageCondition.ROOM_TEMP,
                "carrier_name": "FedEx Clinical",
                "tracking_number": "FX-2025-5567812",
                "ship_date": now - timedelta(days=48),
                "expected_delivery_date": now - timedelta(days=47),
                "actual_delivery_date": now - timedelta(days=47),
                "temperature_monitored": False,
                "temperature_excursion": False,
                "excursion_duration_minutes": 0,
                "prepared_by": "Lab Tech Rachel Green",
                "received_by": "Histopath Receiving",
                "notes": "FFPE tissue blocks. Ambient temperature shipping.",
                "created_at": now - timedelta(days=49),
            },
            {
                "id": "SHP-007",
                "trial_id": DUPIXENT_TRIAL,
                "shipment_number": "DUP-SHP-2025-003",
                "shipping_status": ShippingStatus.PACKED,
                "origin_site": "SITE-BOS-001",
                "destination_site": "Central Lab Immunology",
                "specimen_count": 5,
                "shipping_condition": StorageCondition.DRY_ICE,
                "carrier_name": "World Courier",
                "tracking_number": None,
                "ship_date": None,
                "expected_delivery_date": now + timedelta(days=3),
                "actual_delivery_date": None,
                "temperature_monitored": True,
                "temperature_excursion": False,
                "excursion_duration_minutes": 0,
                "prepared_by": "Lab Tech Alex Yun",
                "received_by": None,
                "notes": "Packed and awaiting courier pickup schedule confirmation.",
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "SHP-008",
                "trial_id": DUPIXENT_TRIAL,
                "shipment_number": "DUP-SHP-2025-004",
                "shipping_status": ShippingStatus.RETURNED,
                "origin_site": "SITE-CHI-001",
                "destination_site": "Central Lab Immunology",
                "specimen_count": 2,
                "shipping_condition": StorageCondition.DRY_ICE,
                "carrier_name": "World Courier",
                "tracking_number": "WC-2025-CHI-00198",
                "ship_date": now - timedelta(days=35),
                "expected_delivery_date": now - timedelta(days=33),
                "actual_delivery_date": None,
                "temperature_monitored": True,
                "temperature_excursion": True,
                "excursion_duration_minutes": 120,
                "prepared_by": "Lab Tech Rachel Green",
                "received_by": None,
                "notes": "Extended temperature excursion during transit. Shipment returned to origin. Specimens compromised.",
                "created_at": now - timedelta(days=36),
            },
            {
                "id": "SHP-009",
                "trial_id": LIBTAYO_TRIAL,
                "shipment_number": "LIB-SHP-2025-001",
                "shipping_status": ShippingStatus.DELIVERED,
                "origin_site": "SITE-HOU-001",
                "destination_site": "Central Oncology Lab",
                "specimen_count": 12,
                "shipping_condition": StorageCondition.DRY_ICE,
                "carrier_name": "Marken",
                "tracking_number": "MK-2025-HOU-00445",
                "ship_date": now - timedelta(days=60),
                "expected_delivery_date": now - timedelta(days=58),
                "actual_delivery_date": now - timedelta(days=58),
                "temperature_monitored": True,
                "temperature_excursion": False,
                "excursion_duration_minutes": 0,
                "prepared_by": "Lab Tech Kevin Owens",
                "received_by": "Central Onc Lab Receiving",
                "notes": "Full baseline shipment. Temperature log verified on receipt.",
                "created_at": now - timedelta(days=61),
            },
            {
                "id": "SHP-010",
                "trial_id": LIBTAYO_TRIAL,
                "shipment_number": "LIB-SHP-2025-002",
                "shipping_status": ShippingStatus.IN_TRANSIT,
                "origin_site": "SITE-HOU-001",
                "destination_site": "Biomarker Analysis Lab",
                "specimen_count": 6,
                "shipping_condition": StorageCondition.FROZEN_MINUS_80,
                "carrier_name": "Cryoport",
                "tracking_number": "CP-2025-HOU-00678",
                "ship_date": now - timedelta(days=1),
                "expected_delivery_date": now + timedelta(days=2),
                "actual_delivery_date": None,
                "temperature_monitored": True,
                "temperature_excursion": False,
                "excursion_duration_minutes": 0,
                "prepared_by": "Lab Tech Kevin Owens",
                "received_by": None,
                "notes": "Immune profiling specimens in transit to biomarker lab.",
                "created_at": now - timedelta(days=2),
            },
            {
                "id": "SHP-011",
                "trial_id": LIBTAYO_TRIAL,
                "shipment_number": "LIB-SHP-2025-003",
                "shipping_status": ShippingStatus.LOST,
                "origin_site": "SITE-SEA-001",
                "destination_site": "Central Oncology Lab",
                "specimen_count": 3,
                "shipping_condition": StorageCondition.DRY_ICE,
                "carrier_name": "FedEx Clinical",
                "tracking_number": "FX-2025-8891023",
                "ship_date": now - timedelta(days=25),
                "expected_delivery_date": now - timedelta(days=23),
                "actual_delivery_date": None,
                "temperature_monitored": True,
                "temperature_excursion": False,
                "excursion_duration_minutes": 0,
                "prepared_by": "Lab Tech Amy Chen",
                "received_by": None,
                "notes": "Shipment lost in transit. Investigation opened with carrier. Specimens unrecoverable.",
                "created_at": now - timedelta(days=26),
            },
            {
                "id": "SHP-012",
                "trial_id": LIBTAYO_TRIAL,
                "shipment_number": "LIB-SHP-2025-004",
                "shipping_status": ShippingStatus.PENDING,
                "origin_site": "SITE-HOU-001",
                "destination_site": "Genomics Lab Central",
                "specimen_count": 4,
                "shipping_condition": StorageCondition.FROZEN_MINUS_80,
                "carrier_name": "Marken",
                "tracking_number": None,
                "ship_date": None,
                "expected_delivery_date": now + timedelta(days=7),
                "actual_delivery_date": None,
                "temperature_monitored": True,
                "temperature_excursion": False,
                "excursion_duration_minutes": 0,
                "prepared_by": "Lab Tech Kevin Owens",
                "received_by": None,
                "notes": "Pending genomic analysis specimens. Awaiting shipping window.",
                "created_at": now - timedelta(days=1),
            },
        ]

        for sh in shipping_data:
            self._shipping_logistics[sh["id"]] = ShippingLogistic(**sh)

        # --- 12 Specimen QC Records ---
        qc_data = [
            {
                "id": "QC-001",
                "trial_id": EYLEA_TRIAL,
                "specimen_id": "COL-001",
                "qc_date": now - timedelta(days=90),
                "qc_result": QCResult.PASS,
                "test_performed": "Visual inspection and hemolysis index",
                "hemolysis_index": 15.0,
                "lipemia_index": 5.0,
                "icterus_index": 2.0,
                "volume_adequate": True,
                "labeling_correct": True,
                "container_integrity": True,
                "acceptance_criteria_met": True,
                "corrective_action": None,
                "performed_by": "Lab Tech Maria Santos",
                "reviewed_by": "Lab Supervisor Dr. Elena Voss",
                "notes": "All QC parameters within acceptable limits.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "QC-002",
                "trial_id": EYLEA_TRIAL,
                "specimen_id": "COL-002",
                "qc_date": now - timedelta(days=59),
                "qc_result": QCResult.PASS,
                "test_performed": "Visual inspection and volume verification",
                "hemolysis_index": 10.0,
                "lipemia_index": 3.0,
                "icterus_index": 1.0,
                "volume_adequate": True,
                "labeling_correct": True,
                "container_integrity": True,
                "acceptance_criteria_met": True,
                "corrective_action": None,
                "performed_by": "Lab Tech John Reeves",
                "reviewed_by": "Lab Supervisor Dr. Elena Voss",
                "notes": "Serum quality excellent. Clear and non-hemolyzed.",
                "created_at": now - timedelta(days=59),
            },
            {
                "id": "QC-003",
                "trial_id": EYLEA_TRIAL,
                "specimen_id": "COL-003",
                "qc_date": now - timedelta(days=84),
                "qc_result": QCResult.BORDERLINE,
                "test_performed": "Hemolysis and lipemia assessment",
                "hemolysis_index": 45.0,
                "lipemia_index": 8.0,
                "icterus_index": 3.0,
                "volume_adequate": True,
                "labeling_correct": True,
                "container_integrity": True,
                "acceptance_criteria_met": True,
                "corrective_action": None,
                "performed_by": "Lab Tech Maria Santos",
                "reviewed_by": "Lab Supervisor Dr. Elena Voss",
                "notes": "Slightly elevated hemolysis index. Acceptable for non-PK assays.",
                "created_at": now - timedelta(days=84),
            },
            {
                "id": "QC-004",
                "trial_id": EYLEA_TRIAL,
                "specimen_id": "COL-003",
                "qc_date": now - timedelta(days=82),
                "qc_result": QCResult.PASS,
                "test_performed": "Re-test after centrifuge optimization",
                "hemolysis_index": 22.0,
                "lipemia_index": 6.0,
                "icterus_index": 2.0,
                "volume_adequate": True,
                "labeling_correct": True,
                "container_integrity": True,
                "acceptance_criteria_met": True,
                "corrective_action": "Re-centrifuged aliquot at optimized speed",
                "performed_by": "Lab Tech Maria Santos",
                "reviewed_by": "Lab Supervisor Dr. Elena Voss",
                "notes": "Re-test passed. Hemolysis reduced to acceptable level after re-processing.",
                "created_at": now - timedelta(days=82),
            },
            {
                "id": "QC-005",
                "trial_id": DUPIXENT_TRIAL,
                "specimen_id": "COL-005",
                "qc_date": now - timedelta(days=74),
                "qc_result": QCResult.PASS,
                "test_performed": "PBMC viability count and volume check",
                "hemolysis_index": None,
                "lipemia_index": None,
                "icterus_index": None,
                "volume_adequate": True,
                "labeling_correct": True,
                "container_integrity": True,
                "acceptance_criteria_met": True,
                "corrective_action": None,
                "performed_by": "Lab Tech Rachel Green",
                "reviewed_by": "Lab Supervisor Dr. Mark Phillips",
                "notes": "PBMC viability >90%. Cell count meets minimum threshold.",
                "created_at": now - timedelta(days=74),
            },
            {
                "id": "QC-006",
                "trial_id": DUPIXENT_TRIAL,
                "specimen_id": "COL-006",
                "qc_date": now - timedelta(days=49),
                "qc_result": QCResult.PASS,
                "test_performed": "Tissue quality assessment",
                "hemolysis_index": None,
                "lipemia_index": None,
                "icterus_index": None,
                "volume_adequate": True,
                "labeling_correct": True,
                "container_integrity": True,
                "acceptance_criteria_met": True,
                "corrective_action": None,
                "performed_by": "Lab Tech Rachel Green",
                "reviewed_by": "Lab Supervisor Dr. Mark Phillips",
                "notes": "Tissue biopsy quality acceptable. Adequate depth and diameter.",
                "created_at": now - timedelta(days=49),
            },
            {
                "id": "QC-007",
                "trial_id": DUPIXENT_TRIAL,
                "specimen_id": "COL-007",
                "qc_date": now - timedelta(days=39),
                "qc_result": QCResult.FAIL,
                "test_performed": "Volume and labeling verification",
                "hemolysis_index": 30.0,
                "lipemia_index": 4.0,
                "icterus_index": 1.0,
                "volume_adequate": False,
                "labeling_correct": True,
                "container_integrity": True,
                "acceptance_criteria_met": False,
                "corrective_action": "Recollection scheduled for subject SUBJ-D001",
                "performed_by": "Lab Tech Rachel Green",
                "reviewed_by": "Lab Supervisor Dr. Mark Phillips",
                "notes": "Insufficient volume. Only 3ml obtained vs 10ml required. Recollection needed.",
                "created_at": now - timedelta(days=39),
            },
            {
                "id": "QC-008",
                "trial_id": DUPIXENT_TRIAL,
                "specimen_id": "COL-005",
                "qc_date": now - timedelta(days=30),
                "qc_result": QCResult.REPEAT_NEEDED,
                "test_performed": "Post-thaw viability assessment",
                "hemolysis_index": None,
                "lipemia_index": None,
                "icterus_index": None,
                "volume_adequate": True,
                "labeling_correct": True,
                "container_integrity": True,
                "acceptance_criteria_met": False,
                "corrective_action": "Repeat viability test with fresh aliquot",
                "performed_by": "Lab Tech Rachel Green",
                "reviewed_by": None,
                "notes": "Post-thaw PBMC viability borderline at 72%. Repeat with control sample needed.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "QC-009",
                "trial_id": LIBTAYO_TRIAL,
                "specimen_id": "COL-009",
                "qc_date": now - timedelta(days=69),
                "qc_result": QCResult.PASS,
                "test_performed": "Complete specimen panel QC",
                "hemolysis_index": 8.0,
                "lipemia_index": 2.0,
                "icterus_index": 1.0,
                "volume_adequate": True,
                "labeling_correct": True,
                "container_integrity": True,
                "acceptance_criteria_met": True,
                "corrective_action": None,
                "performed_by": "Lab Tech Kevin Owens",
                "reviewed_by": "Lab Supervisor Dr. Grace Lee",
                "notes": "Full panel QC complete. All parameters within limits. Excellent sample quality.",
                "created_at": now - timedelta(days=69),
            },
            {
                "id": "QC-010",
                "trial_id": LIBTAYO_TRIAL,
                "specimen_id": "COL-010",
                "qc_date": now - timedelta(days=44),
                "qc_result": QCResult.PASS,
                "test_performed": "CSF cell count and protein assessment",
                "hemolysis_index": None,
                "lipemia_index": None,
                "icterus_index": None,
                "volume_adequate": True,
                "labeling_correct": True,
                "container_integrity": True,
                "acceptance_criteria_met": True,
                "corrective_action": None,
                "performed_by": "Lab Tech Kevin Owens",
                "reviewed_by": "Lab Supervisor Dr. Grace Lee",
                "notes": "CSF clear, no blood contamination. Cell count and protein within normal limits.",
                "created_at": now - timedelta(days=44),
            },
            {
                "id": "QC-011",
                "trial_id": LIBTAYO_TRIAL,
                "specimen_id": "COL-011",
                "qc_date": now - timedelta(days=54),
                "qc_result": QCResult.FAIL,
                "test_performed": "Hemolysis and fasting verification",
                "hemolysis_index": 120.0,
                "lipemia_index": 15.0,
                "icterus_index": 5.0,
                "volume_adequate": True,
                "labeling_correct": True,
                "container_integrity": True,
                "acceptance_criteria_met": False,
                "corrective_action": "Recollection required with confirmed fasting status",
                "performed_by": "Lab Tech Amy Chen",
                "reviewed_by": "Lab Supervisor Dr. Grace Lee",
                "notes": "Grossly hemolyzed. Hemolysis index 120 (limit 50). Fasting not confirmed. Sample rejected.",
                "created_at": now - timedelta(days=54),
            },
            {
                "id": "QC-012",
                "trial_id": LIBTAYO_TRIAL,
                "specimen_id": "COL-009",
                "qc_date": now - timedelta(days=10),
                "qc_result": QCResult.NOT_TESTED,
                "test_performed": "Pre-shipment integrity check",
                "hemolysis_index": None,
                "lipemia_index": None,
                "icterus_index": None,
                "volume_adequate": True,
                "labeling_correct": True,
                "container_integrity": True,
                "acceptance_criteria_met": True,
                "corrective_action": None,
                "performed_by": "Lab Tech Kevin Owens",
                "reviewed_by": None,
                "notes": "Pre-shipment visual check only. Full QC to be performed at receiving lab.",
                "created_at": now - timedelta(days=10),
            },
        ]

        for q in qc_data:
            self._specimen_qc[q["id"]] = SpecimenQC(**q)

    # ------------------------------------------------------------------
    # Collection Records
    # ------------------------------------------------------------------

    def list_collection_records(
        self,
        *,
        trial_id: str | None = None,
        specimen_type: SpecimenType | None = None,
        collection_status: CollectionStatus | None = None,
    ) -> list[CollectionRecord]:
        """List collection records with optional filters."""
        with self._lock:
            result = list(self._collection_records.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if specimen_type is not None:
            result = [r for r in result if r.specimen_type == specimen_type]
        if collection_status is not None:
            result = [r for r in result if r.collection_status == collection_status]

        return sorted(result, key=lambda r: r.scheduled_date, reverse=True)

    def get_collection_record(self, record_id: str) -> CollectionRecord | None:
        """Get a single collection record by ID."""
        with self._lock:
            return self._collection_records.get(record_id)

    def create_collection_record(self, payload: CollectionRecordCreate) -> CollectionRecord:
        """Create a new collection record."""
        now = datetime.now(timezone.utc)
        record_id = f"COL-{uuid4().hex[:8].upper()}"
        record = CollectionRecord(
            id=record_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            site_id=payload.site_id,
            specimen_type=payload.specimen_type,
            collection_status=CollectionStatus.SCHEDULED,
            visit_number=1,
            collection_date=None,
            scheduled_date=payload.scheduled_date,
            tube_count=payload.tube_count,
            volume_ml=payload.volume_ml,
            fasting_required=False,
            fasting_confirmed=False,
            collection_time_critical=False,
            protocol_timepoint=payload.protocol_timepoint,
            collected_by=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._collection_records[record_id] = record
        logger.info("Created collection record %s for trial %s", record_id, payload.trial_id)
        return record

    def update_collection_record(
        self, record_id: str, payload: CollectionRecordUpdate
    ) -> CollectionRecord | None:
        """Update an existing collection record."""
        with self._lock:
            existing = self._collection_records.get(record_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CollectionRecord(**data)
            self._collection_records[record_id] = updated
        return updated

    def delete_collection_record(self, record_id: str) -> bool:
        """Delete a collection record. Returns True if deleted."""
        with self._lock:
            if record_id in self._collection_records:
                del self._collection_records[record_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Storage Inventory
    # ------------------------------------------------------------------

    def list_storage_inventory(
        self,
        *,
        trial_id: str | None = None,
        storage_condition: StorageCondition | None = None,
        is_available: bool | None = None,
    ) -> list[StorageInventory]:
        """List storage inventory with optional filters."""
        with self._lock:
            result = list(self._storage_inventory.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if storage_condition is not None:
            result = [s for s in result if s.storage_condition == storage_condition]
        if is_available is not None:
            result = [s for s in result if s.is_available == is_available]

        return sorted(result, key=lambda s: s.date_stored, reverse=True)

    def get_storage_inventory(self, inventory_id: str) -> StorageInventory | None:
        """Get a single storage inventory record by ID."""
        with self._lock:
            return self._storage_inventory.get(inventory_id)

    def create_storage_inventory(self, payload: StorageInventoryCreate) -> StorageInventory:
        """Create a new storage inventory record."""
        now = datetime.now(timezone.utc)
        inventory_id = f"STR-{uuid4().hex[:8].upper()}"
        record = StorageInventory(
            id=inventory_id,
            trial_id=payload.trial_id,
            specimen_id=payload.specimen_id,
            storage_condition=payload.storage_condition,
            freezer_id=payload.freezer_id,
            rack_position=payload.rack_position,
            box_number=payload.box_number,
            slot_number=payload.slot_number,
            aliquot_number=1,
            volume_remaining_ml=payload.volume_remaining_ml,
            date_stored=now,
            expiry_date=None,
            is_available=True,
            thaw_count=0,
            max_thaw_cycles=3,
            managed_by=payload.managed_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._storage_inventory[inventory_id] = record
        logger.info("Created storage inventory %s for trial %s", inventory_id, payload.trial_id)
        return record

    def update_storage_inventory(
        self, inventory_id: str, payload: StorageInventoryUpdate
    ) -> StorageInventory | None:
        """Update an existing storage inventory record."""
        with self._lock:
            existing = self._storage_inventory.get(inventory_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = StorageInventory(**data)
            self._storage_inventory[inventory_id] = updated
        return updated

    def delete_storage_inventory(self, inventory_id: str) -> bool:
        """Delete a storage inventory record. Returns True if deleted."""
        with self._lock:
            if inventory_id in self._storage_inventory:
                del self._storage_inventory[inventory_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Chain of Custody
    # ------------------------------------------------------------------

    def list_chain_of_custody(
        self,
        *,
        trial_id: str | None = None,
        specimen_id: str | None = None,
    ) -> list[ChainOfCustody]:
        """List chain of custody records with optional filters."""
        with self._lock:
            result = list(self._chain_of_custody.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]
        if specimen_id is not None:
            result = [c for c in result if c.specimen_id == specimen_id]

        return sorted(result, key=lambda c: c.event_date, reverse=True)

    def get_chain_of_custody(self, custody_id: str) -> ChainOfCustody | None:
        """Get a single chain of custody record by ID."""
        with self._lock:
            return self._chain_of_custody.get(custody_id)

    def create_chain_of_custody(self, payload: ChainOfCustodyCreate) -> ChainOfCustody:
        """Create a new chain of custody record."""
        now = datetime.now(timezone.utc)
        custody_id = f"COC-{uuid4().hex[:8].upper()}"
        record = ChainOfCustody(
            id=custody_id,
            trial_id=payload.trial_id,
            specimen_id=payload.specimen_id,
            custody_event=payload.custody_event,
            event_date=now,
            from_location=payload.from_location,
            to_location=payload.to_location,
            from_person=payload.from_person,
            to_person=payload.to_person,
            temperature_at_transfer=None,
            temperature_within_range=True,
            condition_at_transfer="acceptable",
            witnessed=False,
            witness_name=None,
            documentation_complete=True,
            recorded_by=payload.recorded_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._chain_of_custody[custody_id] = record
        logger.info("Created chain of custody %s for specimen %s", custody_id, payload.specimen_id)
        return record

    def update_chain_of_custody(
        self, custody_id: str, payload: ChainOfCustodyUpdate
    ) -> ChainOfCustody | None:
        """Update an existing chain of custody record."""
        with self._lock:
            existing = self._chain_of_custody.get(custody_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ChainOfCustody(**data)
            self._chain_of_custody[custody_id] = updated
        return updated

    def delete_chain_of_custody(self, custody_id: str) -> bool:
        """Delete a chain of custody record. Returns True if deleted."""
        with self._lock:
            if custody_id in self._chain_of_custody:
                del self._chain_of_custody[custody_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Shipping Logistics
    # ------------------------------------------------------------------

    def list_shipping_logistics(
        self,
        *,
        trial_id: str | None = None,
        shipping_status: ShippingStatus | None = None,
    ) -> list[ShippingLogistic]:
        """List shipping logistics with optional filters."""
        with self._lock:
            result = list(self._shipping_logistics.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if shipping_status is not None:
            result = [s for s in result if s.shipping_status == shipping_status]

        return sorted(result, key=lambda s: s.created_at, reverse=True)

    def get_shipping_logistic(self, shipping_id: str) -> ShippingLogistic | None:
        """Get a single shipping logistic record by ID."""
        with self._lock:
            return self._shipping_logistics.get(shipping_id)

    def create_shipping_logistic(self, payload: ShippingLogisticCreate) -> ShippingLogistic:
        """Create a new shipping logistic record."""
        now = datetime.now(timezone.utc)
        shipping_id = f"SHP-{uuid4().hex[:8].upper()}"
        record = ShippingLogistic(
            id=shipping_id,
            trial_id=payload.trial_id,
            shipment_number=payload.shipment_number,
            shipping_status=ShippingStatus.PENDING,
            origin_site=payload.origin_site,
            destination_site=payload.destination_site,
            specimen_count=payload.specimen_count,
            shipping_condition=payload.shipping_condition,
            carrier_name=payload.carrier_name,
            tracking_number=None,
            ship_date=None,
            expected_delivery_date=None,
            actual_delivery_date=None,
            temperature_monitored=True,
            temperature_excursion=False,
            excursion_duration_minutes=0,
            prepared_by=payload.prepared_by,
            received_by=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._shipping_logistics[shipping_id] = record
        logger.info("Created shipping logistic %s for trial %s", shipping_id, payload.trial_id)
        return record

    def update_shipping_logistic(
        self, shipping_id: str, payload: ShippingLogisticUpdate
    ) -> ShippingLogistic | None:
        """Update an existing shipping logistic record."""
        with self._lock:
            existing = self._shipping_logistics.get(shipping_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ShippingLogistic(**data)
            self._shipping_logistics[shipping_id] = updated
        return updated

    def delete_shipping_logistic(self, shipping_id: str) -> bool:
        """Delete a shipping logistic record. Returns True if deleted."""
        with self._lock:
            if shipping_id in self._shipping_logistics:
                del self._shipping_logistics[shipping_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Specimen QC
    # ------------------------------------------------------------------

    def list_specimen_qc(
        self,
        *,
        trial_id: str | None = None,
        specimen_id: str | None = None,
        qc_result: QCResult | None = None,
    ) -> list[SpecimenQC]:
        """List specimen QC records with optional filters."""
        with self._lock:
            result = list(self._specimen_qc.values())

        if trial_id is not None:
            result = [q for q in result if q.trial_id == trial_id]
        if specimen_id is not None:
            result = [q for q in result if q.specimen_id == specimen_id]
        if qc_result is not None:
            result = [q for q in result if q.qc_result == qc_result]

        return sorted(result, key=lambda q: q.qc_date, reverse=True)

    def get_specimen_qc(self, qc_id: str) -> SpecimenQC | None:
        """Get a single specimen QC record by ID."""
        with self._lock:
            return self._specimen_qc.get(qc_id)

    def create_specimen_qc(self, payload: SpecimenQCCreate) -> SpecimenQC:
        """Create a new specimen QC record."""
        now = datetime.now(timezone.utc)
        qc_id = f"QC-{uuid4().hex[:8].upper()}"
        record = SpecimenQC(
            id=qc_id,
            trial_id=payload.trial_id,
            specimen_id=payload.specimen_id,
            qc_date=now,
            qc_result=payload.qc_result,
            test_performed=payload.test_performed,
            hemolysis_index=None,
            lipemia_index=None,
            icterus_index=None,
            volume_adequate=payload.volume_adequate,
            labeling_correct=True,
            container_integrity=True,
            acceptance_criteria_met=True,
            corrective_action=None,
            performed_by=payload.performed_by,
            reviewed_by=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._specimen_qc[qc_id] = record
        logger.info("Created specimen QC %s for specimen %s", qc_id, payload.specimen_id)
        return record

    def update_specimen_qc(
        self, qc_id: str, payload: SpecimenQCUpdate
    ) -> SpecimenQC | None:
        """Update an existing specimen QC record."""
        with self._lock:
            existing = self._specimen_qc.get(qc_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SpecimenQC(**data)
            self._specimen_qc[qc_id] = updated
        return updated

    def delete_specimen_qc(self, qc_id: str) -> bool:
        """Delete a specimen QC record. Returns True if deleted."""
        with self._lock:
            if qc_id in self._specimen_qc:
                del self._specimen_qc[qc_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> SpecimenManagementMetrics:
        """Compute aggregated specimen management metrics."""
        with self._lock:
            collections = list(self._collection_records.values())
            storage = list(self._storage_inventory.values())
            custody = list(self._chain_of_custody.values())
            shipments = list(self._shipping_logistics.values())
            qc_records = list(self._specimen_qc.values())

        # Collections by type
        collections_by_type: dict[str, int] = {}
        for c in collections:
            key = c.specimen_type.value
            collections_by_type[key] = collections_by_type.get(key, 0) + 1

        # Collections by status
        collections_by_status: dict[str, int] = {}
        for c in collections:
            key = c.collection_status.value
            collections_by_status[key] = collections_by_status.get(key, 0) + 1

        # Collection completion rate
        collected_count = sum(
            1 for c in collections if c.collection_status == CollectionStatus.COLLECTED
        )
        completion_rate = round(
            (collected_count / max(1, len(collections))) * 100, 1
        )

        # Storage by condition
        specimens_by_condition: dict[str, int] = {}
        for s in storage:
            key = s.storage_condition.value
            specimens_by_condition[key] = specimens_by_condition.get(key, 0) + 1

        # Available specimens
        available_specimens = sum(1 for s in storage if s.is_available)

        # Custody temperature excursions
        temperature_excursions_custody = sum(
            1 for c in custody if not c.temperature_within_range
        )

        # Shipments by status
        shipments_by_status: dict[str, int] = {}
        for s in shipments:
            key = s.shipping_status.value
            shipments_by_status[key] = shipments_by_status.get(key, 0) + 1

        # Shipping temperature excursions
        temperature_excursions_shipping = sum(
            1 for s in shipments if s.temperature_excursion
        )

        # QC by result
        qc_by_result: dict[str, int] = {}
        for q in qc_records:
            key = q.qc_result.value
            qc_by_result[key] = qc_by_result.get(key, 0) + 1

        # QC pass rate
        qc_pass_count = sum(1 for q in qc_records if q.qc_result == QCResult.PASS)
        qc_tested = sum(1 for q in qc_records if q.qc_result != QCResult.NOT_TESTED)
        qc_pass_rate = round(
            (qc_pass_count / max(1, qc_tested)) * 100, 1
        )

        return SpecimenManagementMetrics(
            total_collections=len(collections),
            collections_by_type=collections_by_type,
            collections_by_status=collections_by_status,
            collection_completion_rate=completion_rate,
            total_stored_specimens=len(storage),
            specimens_by_condition=specimens_by_condition,
            available_specimens=available_specimens,
            total_custody_events=len(custody),
            temperature_excursions_custody=temperature_excursions_custody,
            total_shipments=len(shipments),
            shipments_by_status=shipments_by_status,
            temperature_excursions_shipping=temperature_excursions_shipping,
            total_qc_records=len(qc_records),
            qc_by_result=qc_by_result,
            qc_pass_rate=qc_pass_rate,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: SpecimenManagementService | None = None
_instance_lock = threading.Lock()


def get_specimen_management_service() -> SpecimenManagementService:
    """Return the singleton SpecimenManagementService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = SpecimenManagementService()
    return _instance


def reset_specimen_management_service() -> SpecimenManagementService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = SpecimenManagementService()
    return _instance
