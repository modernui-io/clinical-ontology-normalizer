"""Drug Accountability Management Service (DRUG-ACCT).

Manages drug accountability operations: dispensation records, drug return
tracking, destruction records, accountability reconciliation, deviation
tracking, and drug accountability operational metrics.

Usage:
    from app.services.drug_accountability_service import (
        get_drug_accountability_service,
    )

    svc = get_drug_accountability_service()
    records = svc.list_dispensation_records()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.drug_accountability import (
    AccountabilityDeviation,
    AccountabilityDeviationCreate,
    AccountabilityDeviationListResponse,
    AccountabilityDeviationUpdate,
    AccountabilityReconciliation,
    AccountabilityReconciliationCreate,
    AccountabilityReconciliationListResponse,
    AccountabilityReconciliationUpdate,
    DestructionMethod,
    DestructionRecord,
    DestructionRecordCreate,
    DestructionRecordListResponse,
    DestructionRecordUpdate,
    DeviationSeverity,
    DispensationRecord,
    DispensationRecordCreate,
    DispensationRecordListResponse,
    DispensationRecordUpdate,
    DispensationType,
    DrugAccountabilityMetrics,
    DrugReturn,
    DrugReturnCreate,
    DrugReturnListResponse,
    DrugReturnUpdate,
    DrugStatus,
    ReconciliationStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class DrugAccountabilityService:
    """In-memory Drug Accountability engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._dispensation_records: dict[str, DispensationRecord] = {}
        self._drug_returns: dict[str, DrugReturn] = {}
        self._destruction_records: dict[str, DestructionRecord] = {}
        self._accountability_reconciliations: dict[str, AccountabilityReconciliation] = {}
        self._accountability_deviations: dict[str, AccountabilityDeviation] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic drug accountability data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Dispensation Records ---
        dispensations_data = [
            {
                "id": "DISP-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "subject_id": "SUBJ-1001",
                "visit_id": "VISIT-W0",
                "dispensation_type": DispensationType.INITIAL,
                "drug_name": "Aflibercept (EYLEA) 2mg",
                "batch_number": "EYL-2025-A001",
                "kit_number": "KIT-E-0001",
                "quantity_dispensed": 4,
                "quantity_units": "vials",
                "dispensation_date": now - timedelta(days=120),
                "dispensed_by": "PharmD Sarah Chen",
                "verified_by": "Dr. James Wilson",
                "next_dispensation_date": now - timedelta(days=90),
                "storage_instructions": "Store at 2-8C. Protect from light.",
                "status": DrugStatus.ADMINISTERED,
                "randomization_number": "R-1001",
                "treatment_arm": "Treatment",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "DISP-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "subject_id": "SUBJ-1001",
                "visit_id": "VISIT-W4",
                "dispensation_type": DispensationType.REFILL,
                "drug_name": "Aflibercept (EYLEA) 2mg",
                "batch_number": "EYL-2025-A001",
                "kit_number": "KIT-E-0002",
                "quantity_dispensed": 4,
                "quantity_units": "vials",
                "dispensation_date": now - timedelta(days=90),
                "dispensed_by": "PharmD Sarah Chen",
                "verified_by": "Dr. James Wilson",
                "next_dispensation_date": now - timedelta(days=60),
                "storage_instructions": "Store at 2-8C. Protect from light.",
                "status": DrugStatus.ADMINISTERED,
                "randomization_number": "R-1001",
                "treatment_arm": "Treatment",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "DISP-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "subject_id": "SUBJ-1002",
                "visit_id": "VISIT-W0",
                "dispensation_type": DispensationType.INITIAL,
                "drug_name": "Aflibercept (EYLEA) 2mg",
                "batch_number": "EYL-2025-A002",
                "kit_number": "KIT-E-0003",
                "quantity_dispensed": 4,
                "quantity_units": "vials",
                "dispensation_date": now - timedelta(days=100),
                "dispensed_by": "PharmD Mark Torres",
                "verified_by": None,
                "next_dispensation_date": now - timedelta(days=70),
                "storage_instructions": "Store at 2-8C. Protect from light.",
                "status": DrugStatus.DISPENSED,
                "randomization_number": "R-1002",
                "treatment_arm": "Treatment",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "DISP-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "subject_id": "SUBJ-2001",
                "visit_id": "VISIT-D1",
                "dispensation_type": DispensationType.INITIAL,
                "drug_name": "Dupilumab (DUPIXENT) 300mg",
                "batch_number": "DUP-2025-B001",
                "kit_number": "KIT-D-0001",
                "quantity_dispensed": 2,
                "quantity_units": "pre-filled syringes",
                "dispensation_date": now - timedelta(days=80),
                "dispensed_by": "PharmD Lisa Park",
                "verified_by": "Dr. Angela Rivera",
                "next_dispensation_date": now - timedelta(days=66),
                "storage_instructions": "Store at 2-8C. Do not freeze. Do not shake.",
                "status": DrugStatus.ADMINISTERED,
                "randomization_number": "R-2001",
                "treatment_arm": "Dupilumab 300mg Q2W",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "DISP-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "subject_id": "SUBJ-2001",
                "visit_id": "VISIT-W2",
                "dispensation_type": DispensationType.REFILL,
                "drug_name": "Dupilumab (DUPIXENT) 300mg",
                "batch_number": "DUP-2025-B001",
                "kit_number": "KIT-D-0002",
                "quantity_dispensed": 2,
                "quantity_units": "pre-filled syringes",
                "dispensation_date": now - timedelta(days=66),
                "dispensed_by": "PharmD Lisa Park",
                "verified_by": "Dr. Angela Rivera",
                "next_dispensation_date": now - timedelta(days=52),
                "storage_instructions": "Store at 2-8C. Do not freeze. Do not shake.",
                "status": DrugStatus.ADMINISTERED,
                "randomization_number": "R-2001",
                "treatment_arm": "Dupilumab 300mg Q2W",
                "created_at": now - timedelta(days=66),
            },
            {
                "id": "DISP-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "subject_id": "SUBJ-2002",
                "visit_id": "VISIT-D1",
                "dispensation_type": DispensationType.INITIAL,
                "drug_name": "Dupilumab (DUPIXENT) 300mg",
                "batch_number": "DUP-2025-B002",
                "kit_number": "KIT-D-0003",
                "quantity_dispensed": 2,
                "quantity_units": "pre-filled syringes",
                "dispensation_date": now - timedelta(days=45),
                "dispensed_by": "PharmD Robert Kim",
                "verified_by": "Dr. Michael Santos",
                "next_dispensation_date": now - timedelta(days=31),
                "storage_instructions": "Store at 2-8C. Do not freeze.",
                "status": DrugStatus.DISPENSED,
                "randomization_number": "R-2002",
                "treatment_arm": "Placebo",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "DISP-007",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "subject_id": "SUBJ-3001",
                "visit_id": "VISIT-C1D1",
                "dispensation_type": DispensationType.INITIAL,
                "drug_name": "Cemiplimab (LIBTAYO) 350mg",
                "batch_number": "LIB-2025-C001",
                "kit_number": "KIT-L-0001",
                "quantity_dispensed": 1,
                "quantity_units": "IV infusion bags",
                "dispensation_date": now - timedelta(days=60),
                "dispensed_by": "PharmD Jennifer Adams",
                "verified_by": "Dr. David Park",
                "next_dispensation_date": now - timedelta(days=39),
                "storage_instructions": "Store at 2-8C. Do not freeze. Administer within 8 hours of preparation.",
                "status": DrugStatus.ADMINISTERED,
                "randomization_number": "R-3001",
                "treatment_arm": "Cemiplimab monotherapy",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "DISP-008",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "subject_id": "SUBJ-3001",
                "visit_id": "VISIT-C2D1",
                "dispensation_type": DispensationType.REFILL,
                "drug_name": "Cemiplimab (LIBTAYO) 350mg",
                "batch_number": "LIB-2025-C001",
                "kit_number": "KIT-L-0002",
                "quantity_dispensed": 1,
                "quantity_units": "IV infusion bags",
                "dispensation_date": now - timedelta(days=39),
                "dispensed_by": "PharmD Jennifer Adams",
                "verified_by": "Dr. David Park",
                "next_dispensation_date": now - timedelta(days=18),
                "storage_instructions": "Store at 2-8C. Do not freeze. Administer within 8 hours of preparation.",
                "status": DrugStatus.ADMINISTERED,
                "randomization_number": "R-3001",
                "treatment_arm": "Cemiplimab monotherapy",
                "created_at": now - timedelta(days=39),
            },
            {
                "id": "DISP-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "subject_id": "SUBJ-3002",
                "visit_id": "VISIT-C1D1",
                "dispensation_type": DispensationType.INITIAL,
                "drug_name": "Cemiplimab (LIBTAYO) 350mg",
                "batch_number": "LIB-2025-C002",
                "kit_number": "KIT-L-0003",
                "quantity_dispensed": 1,
                "quantity_units": "IV infusion bags",
                "dispensation_date": now - timedelta(days=30),
                "dispensed_by": "PharmD Amy Wright",
                "verified_by": None,
                "next_dispensation_date": now - timedelta(days=9),
                "storage_instructions": "Store at 2-8C. Do not freeze.",
                "status": DrugStatus.DISPENSED,
                "randomization_number": "R-3002",
                "treatment_arm": "Cemiplimab + chemotherapy",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "DISP-010",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-107",
                "subject_id": "SUBJ-1003",
                "visit_id": "VISIT-W0",
                "dispensation_type": DispensationType.INITIAL,
                "drug_name": "Aflibercept (EYLEA) 2mg",
                "batch_number": "EYL-2025-A003",
                "kit_number": "KIT-E-0004",
                "quantity_dispensed": 4,
                "quantity_units": "vials",
                "dispensation_date": now - timedelta(days=20),
                "dispensed_by": "PharmD Sarah Chen",
                "verified_by": "Dr. Patricia Gomez",
                "next_dispensation_date": now + timedelta(days=8),
                "storage_instructions": "Store at 2-8C. Protect from light.",
                "status": DrugStatus.DISPENSED,
                "randomization_number": "R-1003",
                "treatment_arm": "Treatment",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "DISP-011",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-108",
                "subject_id": "SUBJ-2003",
                "visit_id": "VISIT-D1",
                "dispensation_type": DispensationType.EMERGENCY,
                "drug_name": "Dupilumab (DUPIXENT) 300mg",
                "batch_number": "DUP-2025-B003",
                "kit_number": "KIT-D-0004",
                "quantity_dispensed": 1,
                "quantity_units": "pre-filled syringes",
                "dispensation_date": now - timedelta(days=10),
                "dispensed_by": "PharmD Robert Kim",
                "verified_by": "Dr. Angela Rivera",
                "next_dispensation_date": now + timedelta(days=4),
                "storage_instructions": "Store at 2-8C. Emergency replacement supply.",
                "status": DrugStatus.DISPENSED,
                "randomization_number": "R-2003",
                "treatment_arm": "Dupilumab 300mg Q2W",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "DISP-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "subject_id": "SUBJ-3003",
                "visit_id": "VISIT-C1D1",
                "dispensation_type": DispensationType.OPEN_LABEL,
                "drug_name": "Cemiplimab (LIBTAYO) 350mg",
                "batch_number": "LIB-2025-C003",
                "kit_number": "KIT-L-0004",
                "quantity_dispensed": 1,
                "quantity_units": "IV infusion bags",
                "dispensation_date": now - timedelta(days=5),
                "dispensed_by": "PharmD Jennifer Adams",
                "verified_by": "Dr. David Park",
                "next_dispensation_date": now + timedelta(days=16),
                "storage_instructions": "Store at 2-8C. Open-label extension.",
                "status": DrugStatus.DISPENSED,
                "randomization_number": "R-3003",
                "treatment_arm": "Open-label cemiplimab",
                "created_at": now - timedelta(days=5),
            },
        ]

        for d in dispensations_data:
            self._dispensation_records[d["id"]] = DispensationRecord(**d)

        # --- 10 Drug Returns ---
        returns_data = [
            {
                "id": "RET-001",
                "dispensation_id": "DISP-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "subject_id": "SUBJ-1001",
                "return_date": now - timedelta(days=88),
                "quantity_returned": 1,
                "quantity_used": 3,
                "quantity_lost": 0,
                "condition": "acceptable",
                "returned_to": "PharmD Sarah Chen",
                "verified_by": "PharmD Sarah Chen",
                "packaging_intact": True,
                "temperature_excursion": False,
                "notes": "1 unused vial returned. 3 administered per protocol.",
                "created_at": now - timedelta(days=88),
            },
            {
                "id": "RET-002",
                "dispensation_id": "DISP-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "subject_id": "SUBJ-1001",
                "return_date": now - timedelta(days=58),
                "quantity_returned": 0,
                "quantity_used": 4,
                "quantity_lost": 0,
                "condition": "acceptable",
                "returned_to": "PharmD Sarah Chen",
                "verified_by": "PharmD Sarah Chen",
                "packaging_intact": True,
                "temperature_excursion": False,
                "notes": "All 4 vials administered per protocol.",
                "created_at": now - timedelta(days=58),
            },
            {
                "id": "RET-003",
                "dispensation_id": "DISP-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "subject_id": "SUBJ-2001",
                "return_date": now - timedelta(days=64),
                "quantity_returned": 0,
                "quantity_used": 2,
                "quantity_lost": 0,
                "condition": "acceptable",
                "returned_to": "PharmD Lisa Park",
                "verified_by": "PharmD Lisa Park",
                "packaging_intact": True,
                "temperature_excursion": False,
                "notes": "Both syringes used as directed.",
                "created_at": now - timedelta(days=64),
            },
            {
                "id": "RET-004",
                "dispensation_id": "DISP-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "subject_id": "SUBJ-2001",
                "return_date": now - timedelta(days=50),
                "quantity_returned": 1,
                "quantity_used": 1,
                "quantity_lost": 0,
                "condition": "damaged",
                "returned_to": "PharmD Lisa Park",
                "verified_by": "PharmD Lisa Park",
                "packaging_intact": False,
                "temperature_excursion": False,
                "notes": "1 syringe returned with cracked barrel. Deviation filed.",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "RET-005",
                "dispensation_id": "DISP-007",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "subject_id": "SUBJ-3001",
                "return_date": now - timedelta(days=58),
                "quantity_returned": 0,
                "quantity_used": 1,
                "quantity_lost": 0,
                "condition": "acceptable",
                "returned_to": "PharmD Jennifer Adams",
                "verified_by": "PharmD Jennifer Adams",
                "packaging_intact": True,
                "temperature_excursion": False,
                "notes": "IV bag fully administered.",
                "created_at": now - timedelta(days=58),
            },
            {
                "id": "RET-006",
                "dispensation_id": "DISP-008",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "subject_id": "SUBJ-3001",
                "return_date": now - timedelta(days=37),
                "quantity_returned": 0,
                "quantity_used": 1,
                "quantity_lost": 0,
                "condition": "acceptable",
                "returned_to": "PharmD Jennifer Adams",
                "verified_by": "PharmD Jennifer Adams",
                "packaging_intact": True,
                "temperature_excursion": False,
                "notes": "Infusion completed without issues.",
                "created_at": now - timedelta(days=37),
            },
            {
                "id": "RET-007",
                "dispensation_id": "DISP-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "subject_id": "SUBJ-1002",
                "return_date": now - timedelta(days=68),
                "quantity_returned": 2,
                "quantity_used": 2,
                "quantity_lost": 0,
                "condition": "acceptable",
                "returned_to": "PharmD Mark Torres",
                "verified_by": None,
                "packaging_intact": True,
                "temperature_excursion": True,
                "notes": "Temperature excursion logged during transport. 2 unused vials quarantined.",
                "created_at": now - timedelta(days=68),
            },
            {
                "id": "RET-008",
                "dispensation_id": "DISP-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "subject_id": "SUBJ-2002",
                "return_date": now - timedelta(days=29),
                "quantity_returned": 1,
                "quantity_used": 1,
                "quantity_lost": 0,
                "condition": "acceptable",
                "returned_to": "PharmD Robert Kim",
                "verified_by": "PharmD Robert Kim",
                "packaging_intact": True,
                "temperature_excursion": False,
                "notes": "1 syringe administered, 1 returned unused.",
                "created_at": now - timedelta(days=29),
            },
            {
                "id": "RET-009",
                "dispensation_id": "DISP-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "subject_id": "SUBJ-3002",
                "return_date": now - timedelta(days=7),
                "quantity_returned": 0,
                "quantity_used": 0,
                "quantity_lost": 1,
                "condition": "lost",
                "returned_to": "PharmD Amy Wright",
                "verified_by": None,
                "packaging_intact": False,
                "temperature_excursion": False,
                "notes": "Drug lost during site transfer. Deviation reported.",
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "RET-010",
                "dispensation_id": "DISP-010",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-107",
                "subject_id": "SUBJ-1003",
                "return_date": now - timedelta(days=3),
                "quantity_returned": 2,
                "quantity_used": 2,
                "quantity_lost": 0,
                "condition": "acceptable",
                "returned_to": "PharmD Sarah Chen",
                "verified_by": "PharmD Sarah Chen",
                "packaging_intact": True,
                "temperature_excursion": False,
                "notes": "2 vials administered, 2 returned in good condition.",
                "created_at": now - timedelta(days=3),
            },
        ]

        for r in returns_data:
            self._drug_returns[r["id"]] = DrugReturn(**r)

        # --- 10 Destruction Records ---
        destruction_data = [
            {
                "id": "DEST-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "drug_name": "Aflibercept (EYLEA) 2mg",
                "batch_numbers": ["EYL-2025-A001"],
                "destruction_method": DestructionMethod.PHARMACY_DISPOSAL,
                "destruction_date": now - timedelta(days=85),
                "quantity_destroyed": 1,
                "quantity_units": "vials",
                "witness_1": "PharmD Sarah Chen",
                "witness_2": "RN Jennifer Moore",
                "certificate_number": "DEST-CERT-001",
                "destruction_facility": "Memorial Hermann Pharmacy",
                "approved_by": "Dr. James Wilson",
                "documentation_complete": True,
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "DEST-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "drug_name": "Aflibercept (EYLEA) 2mg",
                "batch_numbers": ["EYL-2025-A002"],
                "destruction_method": DestructionMethod.RETURN_TO_SPONSOR,
                "destruction_date": now - timedelta(days=65),
                "quantity_destroyed": 2,
                "quantity_units": "vials",
                "witness_1": "PharmD Mark Torres",
                "witness_2": "CRA David Johnson",
                "certificate_number": "DEST-CERT-002",
                "destruction_facility": None,
                "approved_by": "Dr. Patricia Gomez",
                "documentation_complete": True,
                "created_at": now - timedelta(days=65),
            },
            {
                "id": "DEST-003",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "drug_name": "Dupilumab (DUPIXENT) 300mg",
                "batch_numbers": ["DUP-2025-B001"],
                "destruction_method": DestructionMethod.WITNESSED_DESTRUCTION,
                "destruction_date": now - timedelta(days=48),
                "quantity_destroyed": 1,
                "quantity_units": "pre-filled syringes",
                "witness_1": "PharmD Lisa Park",
                "witness_2": "QA Specialist Maria Garcia",
                "certificate_number": "DEST-CERT-003",
                "destruction_facility": "Johns Hopkins Pharmacy Waste Facility",
                "approved_by": "Dr. Angela Rivera",
                "documentation_complete": True,
                "created_at": now - timedelta(days=48),
            },
            {
                "id": "DEST-004",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "drug_name": "Cemiplimab (LIBTAYO) 350mg",
                "batch_numbers": ["LIB-2025-C001"],
                "destruction_method": DestructionMethod.INCINERATION,
                "destruction_date": now - timedelta(days=35),
                "quantity_destroyed": 2,
                "quantity_units": "IV infusion bags",
                "witness_1": "PharmD Jennifer Adams",
                "witness_2": "CRA Emily Thompson",
                "certificate_number": "DEST-CERT-004",
                "destruction_facility": "Stericycle Incineration Facility",
                "approved_by": "Dr. David Park",
                "documentation_complete": True,
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "DEST-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "drug_name": "Dupilumab (DUPIXENT) 300mg",
                "batch_numbers": ["DUP-2025-B002"],
                "destruction_method": DestructionMethod.PHARMACY_DISPOSAL,
                "destruction_date": now - timedelta(days=25),
                "quantity_destroyed": 1,
                "quantity_units": "pre-filled syringes",
                "witness_1": "PharmD Robert Kim",
                "witness_2": None,
                "certificate_number": None,
                "destruction_facility": "Mayo Clinic Pharmacy",
                "approved_by": "Dr. Michael Santos",
                "documentation_complete": False,
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "DEST-006",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "drug_name": "Aflibercept (EYLEA) 2mg",
                "batch_numbers": ["EYL-2025-A001", "EYL-2025-A003"],
                "destruction_method": DestructionMethod.CHEMICAL,
                "destruction_date": now - timedelta(days=15),
                "quantity_destroyed": 3,
                "quantity_units": "vials",
                "witness_1": "PharmD Sarah Chen",
                "witness_2": "PharmD Mark Torres",
                "certificate_number": "DEST-CERT-006",
                "destruction_facility": "Memorial Hermann Hazardous Waste Unit",
                "approved_by": "Dr. James Wilson",
                "documentation_complete": True,
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "DEST-007",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "drug_name": "Cemiplimab (LIBTAYO) 350mg",
                "batch_numbers": ["LIB-2025-C002"],
                "destruction_method": DestructionMethod.RETURN_TO_SPONSOR,
                "destruction_date": now - timedelta(days=5),
                "quantity_destroyed": 1,
                "quantity_units": "IV infusion bags",
                "witness_1": "PharmD Amy Wright",
                "witness_2": None,
                "certificate_number": None,
                "destruction_facility": None,
                "approved_by": "Dr. David Park",
                "documentation_complete": False,
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "DEST-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-108",
                "drug_name": "Dupilumab (DUPIXENT) 300mg",
                "batch_numbers": ["DUP-2025-B003"],
                "destruction_method": DestructionMethod.WITNESSED_DESTRUCTION,
                "destruction_date": now - timedelta(days=3),
                "quantity_destroyed": 2,
                "quantity_units": "pre-filled syringes",
                "witness_1": "PharmD Robert Kim",
                "witness_2": "CRA Susan Brown",
                "certificate_number": "DEST-CERT-008",
                "destruction_facility": "Stanford Pharmacy",
                "approved_by": "Dr. Angela Rivera",
                "documentation_complete": True,
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "DEST-009",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-107",
                "drug_name": "Aflibercept (EYLEA) 2mg",
                "batch_numbers": ["EYL-2025-A003"],
                "destruction_method": DestructionMethod.INCINERATION,
                "destruction_date": now - timedelta(days=2),
                "quantity_destroyed": 2,
                "quantity_units": "vials",
                "witness_1": "PharmD Sarah Chen",
                "witness_2": "RN Patricia Wells",
                "certificate_number": "DEST-CERT-009",
                "destruction_facility": "Stericycle Northeast",
                "approved_by": "Dr. Patricia Gomez",
                "documentation_complete": True,
                "created_at": now - timedelta(days=2),
            },
            {
                "id": "DEST-010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "drug_name": "Cemiplimab (LIBTAYO) 350mg",
                "batch_numbers": ["LIB-2025-C001", "LIB-2025-C003"],
                "destruction_method": DestructionMethod.PHARMACY_DISPOSAL,
                "destruction_date": now - timedelta(days=1),
                "quantity_destroyed": 3,
                "quantity_units": "IV infusion bags",
                "witness_1": "PharmD Jennifer Adams",
                "witness_2": "CRA Emily Thompson",
                "certificate_number": "DEST-CERT-010",
                "destruction_facility": "Duke Pharmacy Waste",
                "approved_by": "Dr. David Park",
                "documentation_complete": True,
                "created_at": now - timedelta(days=1),
            },
        ]

        for d in destruction_data:
            self._destruction_records[d["id"]] = DestructionRecord(**d)

        # --- 10 Accountability Reconciliations ---
        reconciliation_data = [
            {
                "id": "RECON-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "reconciliation_date": now - timedelta(days=90),
                "period_start": now - timedelta(days=180),
                "period_end": now - timedelta(days=90),
                "total_received": 20,
                "total_dispensed": 8,
                "total_returned": 1,
                "total_destroyed": 1,
                "total_on_hand": 10,
                "total_lost": 0,
                "balance_expected": 10,
                "balance_actual": 10,
                "discrepancy": 0,
                "status": ReconciliationStatus.RECONCILED,
                "performed_by": "PharmD Sarah Chen",
                "verified_by": "CRA David Johnson",
                "notes": "Full reconciliation complete. No discrepancies.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "RECON-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "reconciliation_date": now - timedelta(days=60),
                "period_start": now - timedelta(days=120),
                "period_end": now - timedelta(days=60),
                "total_received": 12,
                "total_dispensed": 4,
                "total_returned": 2,
                "total_destroyed": 2,
                "total_on_hand": 4,
                "total_lost": 0,
                "balance_expected": 4,
                "balance_actual": 4,
                "discrepancy": 0,
                "status": ReconciliationStatus.RECONCILED,
                "performed_by": "PharmD Mark Torres",
                "verified_by": "CRA David Johnson",
                "notes": "All units accounted for.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "RECON-003",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "reconciliation_date": now - timedelta(days=45),
                "period_start": now - timedelta(days=90),
                "period_end": now - timedelta(days=45),
                "total_received": 16,
                "total_dispensed": 4,
                "total_returned": 1,
                "total_destroyed": 1,
                "total_on_hand": 10,
                "total_lost": 0,
                "balance_expected": 10,
                "balance_actual": 10,
                "discrepancy": 0,
                "status": ReconciliationStatus.RECONCILED,
                "performed_by": "PharmD Lisa Park",
                "verified_by": "CRA Emily Thompson",
                "notes": "Reconciliation complete.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "RECON-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "reconciliation_date": now - timedelta(days=20),
                "period_start": now - timedelta(days=60),
                "period_end": now - timedelta(days=20),
                "total_received": 10,
                "total_dispensed": 2,
                "total_returned": 1,
                "total_destroyed": 1,
                "total_on_hand": 6,
                "total_lost": 0,
                "balance_expected": 6,
                "balance_actual": 6,
                "discrepancy": 0,
                "status": ReconciliationStatus.RECONCILED,
                "performed_by": "PharmD Robert Kim",
                "verified_by": "CRA Susan Brown",
                "notes": None,
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "RECON-005",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "reconciliation_date": now - timedelta(days=30),
                "period_start": now - timedelta(days=90),
                "period_end": now - timedelta(days=30),
                "total_received": 8,
                "total_dispensed": 3,
                "total_returned": 0,
                "total_destroyed": 2,
                "total_on_hand": 3,
                "total_lost": 0,
                "balance_expected": 3,
                "balance_actual": 3,
                "discrepancy": 0,
                "status": ReconciliationStatus.RECONCILED,
                "performed_by": "PharmD Jennifer Adams",
                "verified_by": "CRA Emily Thompson",
                "notes": "IV infusion bags accounted for.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "RECON-006",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "reconciliation_date": now - timedelta(days=7),
                "period_start": now - timedelta(days=45),
                "period_end": now - timedelta(days=7),
                "total_received": 6,
                "total_dispensed": 1,
                "total_returned": 0,
                "total_destroyed": 1,
                "total_on_hand": 3,
                "total_lost": 1,
                "balance_expected": 4,
                "balance_actual": 3,
                "discrepancy": -1,
                "status": ReconciliationStatus.DISCREPANCY,
                "performed_by": "PharmD Amy Wright",
                "verified_by": None,
                "notes": "1 unit unaccounted for. Lost drug reported. Investigation ongoing.",
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "RECON-007",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-107",
                "reconciliation_date": now - timedelta(days=5),
                "period_start": now - timedelta(days=30),
                "period_end": now - timedelta(days=5),
                "total_received": 8,
                "total_dispensed": 4,
                "total_returned": 2,
                "total_destroyed": 2,
                "total_on_hand": 0,
                "total_lost": 0,
                "balance_expected": 0,
                "balance_actual": 0,
                "discrepancy": 0,
                "status": ReconciliationStatus.RECONCILED,
                "performed_by": "PharmD Sarah Chen",
                "verified_by": "CRA David Johnson",
                "notes": "All units accounted for at SITE-107.",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "RECON-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-108",
                "reconciliation_date": now - timedelta(days=2),
                "period_start": now - timedelta(days=30),
                "period_end": now - timedelta(days=2),
                "total_received": 6,
                "total_dispensed": 1,
                "total_returned": 0,
                "total_destroyed": 2,
                "total_on_hand": 3,
                "total_lost": 0,
                "balance_expected": 3,
                "balance_actual": 3,
                "discrepancy": 0,
                "status": ReconciliationStatus.RECONCILED,
                "performed_by": "PharmD Robert Kim",
                "verified_by": "CRA Susan Brown",
                "notes": None,
                "created_at": now - timedelta(days=2),
            },
            {
                "id": "RECON-009",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "reconciliation_date": now - timedelta(days=1),
                "period_start": now - timedelta(days=90),
                "period_end": now - timedelta(days=1),
                "total_received": 30,
                "total_dispensed": 12,
                "total_returned": 3,
                "total_destroyed": 4,
                "total_on_hand": 11,
                "total_lost": 0,
                "balance_expected": 11,
                "balance_actual": 11,
                "discrepancy": 0,
                "status": ReconciliationStatus.RECONCILED,
                "performed_by": "PharmD Sarah Chen",
                "verified_by": "CRA David Johnson",
                "notes": "Quarterly reconciliation complete.",
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "RECON-010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "reconciliation_date": now,
                "period_start": now - timedelta(days=30),
                "period_end": now,
                "total_received": 4,
                "total_dispensed": 2,
                "total_returned": 0,
                "total_destroyed": 3,
                "total_on_hand": 0,
                "total_lost": 0,
                "balance_expected": 0,
                "balance_actual": 0,
                "discrepancy": 0,
                "status": ReconciliationStatus.PENDING,
                "performed_by": "PharmD Jennifer Adams",
                "verified_by": None,
                "notes": None,
                "created_at": now,
            },
        ]

        for r in reconciliation_data:
            self._accountability_reconciliations[r["id"]] = AccountabilityReconciliation(**r)

        # --- 10 Accountability Deviations ---
        deviation_data = [
            {
                "id": "DEV-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "subject_id": "SUBJ-1002",
                "deviation_date": now - timedelta(days=68),
                "description": "Temperature excursion during drug transport from storage to pharmacy. Drug exposed to 12C for 45 minutes.",
                "severity": DeviationSeverity.MODERATE,
                "root_cause": "Inadequate cold chain maintenance during internal transport",
                "quantity_affected": 2,
                "batch_number": "EYL-2025-A002",
                "corrective_action": "Quarantined affected vials. Stability assessment requested from sponsor.",
                "preventive_action": "Updated SOPs for internal drug transport. Added temperature monitoring tags.",
                "reported_by": "PharmD Mark Torres",
                "resolved_by": "QA Manager Rebecca Hall",
                "resolution_date": now - timedelta(days=55),
                "sponsor_notified": True,
                "irb_notified": False,
                "created_at": now - timedelta(days=68),
            },
            {
                "id": "DEV-002",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "subject_id": "SUBJ-2001",
                "deviation_date": now - timedelta(days=50),
                "description": "Damaged pre-filled syringe returned by subject. Syringe barrel cracked, contents leaked.",
                "severity": DeviationSeverity.MINOR,
                "root_cause": "Patient dropped syringe during self-administration attempt",
                "quantity_affected": 1,
                "batch_number": "DUP-2025-B001",
                "corrective_action": "Replacement syringe dispensed. Subject re-trained on injection technique.",
                "preventive_action": "Enhanced patient training materials for self-injection.",
                "reported_by": "PharmD Lisa Park",
                "resolved_by": "CRA Emily Thompson",
                "resolution_date": now - timedelta(days=45),
                "sponsor_notified": True,
                "irb_notified": False,
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "DEV-003",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "subject_id": "SUBJ-3002",
                "deviation_date": now - timedelta(days=7),
                "description": "Drug unit lost during site transfer. 1 IV infusion bag unaccounted for during internal inventory.",
                "severity": DeviationSeverity.MAJOR,
                "root_cause": "Unclear chain of custody during pharmacy staff change",
                "quantity_affected": 1,
                "batch_number": "LIB-2025-C002",
                "corrective_action": "Comprehensive inventory audit completed. Staff interviewed.",
                "preventive_action": None,
                "reported_by": "PharmD Amy Wright",
                "resolved_by": None,
                "resolution_date": None,
                "sponsor_notified": True,
                "irb_notified": True,
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "DEV-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "subject_id": None,
                "deviation_date": now - timedelta(days=25),
                "description": "Destruction record incomplete. Second witness signature missing for DEST-005.",
                "severity": DeviationSeverity.MINOR,
                "root_cause": "Administrative oversight during destruction procedure",
                "quantity_affected": 1,
                "batch_number": "DUP-2025-B002",
                "corrective_action": "Retrospective witness signature obtained.",
                "preventive_action": "Updated destruction SOP checklist to enforce dual-signature before proceeding.",
                "reported_by": "CRA Susan Brown",
                "resolved_by": "PharmD Robert Kim",
                "resolution_date": now - timedelta(days=20),
                "sponsor_notified": False,
                "irb_notified": False,
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "DEV-005",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "subject_id": "SUBJ-1001",
                "deviation_date": now - timedelta(days=115),
                "description": "Drug dispensed before verification by second pharmacist. Protocol requires dual verification.",
                "severity": DeviationSeverity.MODERATE,
                "root_cause": "High workload during clinic hours. Verification step skipped inadvertently.",
                "quantity_affected": 4,
                "batch_number": "EYL-2025-A001",
                "corrective_action": "Retrospective verification completed same day. No safety impact.",
                "preventive_action": "Implemented electronic dispensing system with mandatory dual-signature lockout.",
                "reported_by": "PharmD Sarah Chen",
                "resolved_by": "QA Manager Rebecca Hall",
                "resolution_date": now - timedelta(days=110),
                "sponsor_notified": True,
                "irb_notified": False,
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "DEV-006",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "subject_id": "SUBJ-3001",
                "deviation_date": now - timedelta(days=38),
                "description": "IV infusion prepared > 8 hours before administration. Drug stability limit exceeded.",
                "severity": DeviationSeverity.MAJOR,
                "root_cause": "Infusion delayed due to patient adverse reaction to pre-medication",
                "quantity_affected": 1,
                "batch_number": "LIB-2025-C001",
                "corrective_action": "New infusion bag prepared. Original bag destroyed. Patient safety assessed - no impact.",
                "preventive_action": "Added prep-time tracking alerts in pharmacy system.",
                "reported_by": "PharmD Jennifer Adams",
                "resolved_by": "Dr. David Park",
                "resolution_date": now - timedelta(days=35),
                "sponsor_notified": True,
                "irb_notified": False,
                "created_at": now - timedelta(days=38),
            },
            {
                "id": "DEV-007",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-107",
                "subject_id": None,
                "deviation_date": now - timedelta(days=18),
                "description": "Drug storage refrigerator temperature out of range (10.5C) for 2 hours due to power interruption.",
                "severity": DeviationSeverity.CRITICAL,
                "root_cause": "Power outage affecting pharmacy wing. Backup generator failed to activate for refrigerator circuit.",
                "quantity_affected": 8,
                "batch_number": "EYL-2025-A003",
                "corrective_action": "All affected units quarantined. Sponsor notified for stability assessment. Units subsequently destroyed.",
                "preventive_action": "Emergency generator circuit review. Dedicated UPS installed for drug storage units.",
                "reported_by": "PharmD Sarah Chen",
                "resolved_by": "Facilities Director Tom Harris",
                "resolution_date": now - timedelta(days=10),
                "sponsor_notified": True,
                "irb_notified": True,
                "created_at": now - timedelta(days=18),
            },
            {
                "id": "DEV-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "subject_id": "SUBJ-2001",
                "deviation_date": now - timedelta(days=12),
                "description": "Wrong kit number recorded on dispensation log. Kit KIT-D-0002 dispensed but KIT-D-0001 documented.",
                "severity": DeviationSeverity.MINOR,
                "root_cause": "Transcription error by pharmacy staff",
                "quantity_affected": 2,
                "batch_number": "DUP-2025-B001",
                "corrective_action": "Dispensation log corrected with audit trail notation.",
                "preventive_action": "Barcode scanning implemented for kit number verification.",
                "reported_by": "PharmD Lisa Park",
                "resolved_by": "PharmD Lisa Park",
                "resolution_date": now - timedelta(days=10),
                "sponsor_notified": False,
                "irb_notified": False,
                "created_at": now - timedelta(days=12),
            },
            {
                "id": "DEV-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "subject_id": None,
                "deviation_date": now - timedelta(days=3),
                "description": "Return-to-sponsor shipment documentation incomplete. DEST-007 missing chain of custody form.",
                "severity": DeviationSeverity.MODERATE,
                "root_cause": "New staff member unfamiliar with return-to-sponsor procedures",
                "quantity_affected": 1,
                "batch_number": "LIB-2025-C002",
                "corrective_action": None,
                "preventive_action": None,
                "reported_by": "CRA Emily Thompson",
                "resolved_by": None,
                "resolution_date": None,
                "sponsor_notified": True,
                "irb_notified": False,
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "DEV-010",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-108",
                "subject_id": "SUBJ-2003",
                "deviation_date": now - timedelta(days=10),
                "description": "Emergency dispensation without prior authorization from sponsor. Drug provided to subject after-hours.",
                "severity": DeviationSeverity.MODERATE,
                "root_cause": "Subject ran out of medication over weekend. Emergency dispensation per site PI decision.",
                "quantity_affected": 1,
                "batch_number": "DUP-2025-B003",
                "corrective_action": "Retrospective sponsor notification within 24 hours. Documentation completed.",
                "preventive_action": "After-hours sponsor contact procedure distributed to all sites.",
                "reported_by": "PharmD Robert Kim",
                "resolved_by": "Dr. Angela Rivera",
                "resolution_date": now - timedelta(days=8),
                "sponsor_notified": True,
                "irb_notified": False,
                "created_at": now - timedelta(days=10),
            },
        ]

        for d in deviation_data:
            self._accountability_deviations[d["id"]] = AccountabilityDeviation(**d)

    # ------------------------------------------------------------------
    # Dispensation Records
    # ------------------------------------------------------------------

    def list_dispensation_records(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[DispensationRecord]:
        """List dispensation records with optional trial_id filter."""
        with self._lock:
            result = list(self._dispensation_records.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]

        return sorted(result, key=lambda r: r.dispensation_date, reverse=True)

    def get_dispensation_record(self, record_id: str) -> DispensationRecord | None:
        """Get a single dispensation record by ID."""
        with self._lock:
            return self._dispensation_records.get(record_id)

    def create_dispensation_record(self, payload: DispensationRecordCreate) -> DispensationRecord:
        """Create a new dispensation record."""
        now = datetime.now(timezone.utc)
        record_id = f"DISP-{uuid4().hex[:8].upper()}"
        record = DispensationRecord(
            id=record_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            subject_id=payload.subject_id,
            visit_id=payload.visit_id,
            dispensation_type=payload.dispensation_type,
            drug_name=payload.drug_name,
            batch_number=payload.batch_number,
            kit_number=payload.kit_number,
            quantity_dispensed=payload.quantity_dispensed,
            dispensation_date=now,
            dispensed_by=payload.dispensed_by,
            status=DrugStatus.DISPENSED,
            created_at=now,
        )
        with self._lock:
            self._dispensation_records[record_id] = record
        logger.info("Created dispensation record %s for subject %s", record_id, payload.subject_id)
        return record

    def update_dispensation_record(
        self, record_id: str, payload: DispensationRecordUpdate
    ) -> DispensationRecord | None:
        """Update an existing dispensation record."""
        with self._lock:
            existing = self._dispensation_records.get(record_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DispensationRecord(**data)
            self._dispensation_records[record_id] = updated
        return updated

    def delete_dispensation_record(self, record_id: str) -> bool:
        """Delete a dispensation record. Returns True if deleted."""
        with self._lock:
            if record_id in self._dispensation_records:
                del self._dispensation_records[record_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Drug Returns
    # ------------------------------------------------------------------

    def list_drug_returns(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[DrugReturn]:
        """List drug returns with optional trial_id filter."""
        with self._lock:
            result = list(self._drug_returns.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]

        return sorted(result, key=lambda r: r.return_date, reverse=True)

    def get_drug_return(self, return_id: str) -> DrugReturn | None:
        """Get a single drug return by ID."""
        with self._lock:
            return self._drug_returns.get(return_id)

    def create_drug_return(self, payload: DrugReturnCreate) -> DrugReturn:
        """Create a new drug return."""
        now = datetime.now(timezone.utc)
        return_id = f"RET-{uuid4().hex[:8].upper()}"
        record = DrugReturn(
            id=return_id,
            dispensation_id=payload.dispensation_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            subject_id=payload.subject_id,
            return_date=now,
            quantity_returned=payload.quantity_returned,
            quantity_used=payload.quantity_used,
            returned_to=payload.returned_to,
            created_at=now,
        )
        with self._lock:
            self._drug_returns[return_id] = record
        logger.info("Created drug return %s for dispensation %s", return_id, payload.dispensation_id)
        return record

    def update_drug_return(
        self, return_id: str, payload: DrugReturnUpdate
    ) -> DrugReturn | None:
        """Update an existing drug return."""
        with self._lock:
            existing = self._drug_returns.get(return_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DrugReturn(**data)
            self._drug_returns[return_id] = updated
        return updated

    def delete_drug_return(self, return_id: str) -> bool:
        """Delete a drug return. Returns True if deleted."""
        with self._lock:
            if return_id in self._drug_returns:
                del self._drug_returns[return_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Destruction Records
    # ------------------------------------------------------------------

    def list_destruction_records(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[DestructionRecord]:
        """List destruction records with optional trial_id filter."""
        with self._lock:
            result = list(self._destruction_records.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]

        return sorted(result, key=lambda r: r.destruction_date, reverse=True)

    def get_destruction_record(self, record_id: str) -> DestructionRecord | None:
        """Get a single destruction record by ID."""
        with self._lock:
            return self._destruction_records.get(record_id)

    def create_destruction_record(self, payload: DestructionRecordCreate) -> DestructionRecord:
        """Create a new destruction record."""
        now = datetime.now(timezone.utc)
        record_id = f"DEST-{uuid4().hex[:8].upper()}"
        record = DestructionRecord(
            id=record_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            drug_name=payload.drug_name,
            batch_numbers=payload.batch_numbers,
            destruction_method=payload.destruction_method,
            destruction_date=now,
            quantity_destroyed=payload.quantity_destroyed,
            witness_1=payload.witness_1,
            approved_by=payload.approved_by,
            created_at=now,
        )
        with self._lock:
            self._destruction_records[record_id] = record
        logger.info("Created destruction record %s for %s", record_id, payload.drug_name)
        return record

    def update_destruction_record(
        self, record_id: str, payload: DestructionRecordUpdate
    ) -> DestructionRecord | None:
        """Update an existing destruction record."""
        with self._lock:
            existing = self._destruction_records.get(record_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DestructionRecord(**data)
            self._destruction_records[record_id] = updated
        return updated

    def delete_destruction_record(self, record_id: str) -> bool:
        """Delete a destruction record. Returns True if deleted."""
        with self._lock:
            if record_id in self._destruction_records:
                del self._destruction_records[record_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Accountability Reconciliations
    # ------------------------------------------------------------------

    def list_accountability_reconciliations(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[AccountabilityReconciliation]:
        """List accountability reconciliations with optional trial_id filter."""
        with self._lock:
            result = list(self._accountability_reconciliations.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]

        return sorted(result, key=lambda r: r.reconciliation_date, reverse=True)

    def get_accountability_reconciliation(self, recon_id: str) -> AccountabilityReconciliation | None:
        """Get a single accountability reconciliation by ID."""
        with self._lock:
            return self._accountability_reconciliations.get(recon_id)

    def create_accountability_reconciliation(
        self, payload: AccountabilityReconciliationCreate
    ) -> AccountabilityReconciliation:
        """Create a new accountability reconciliation."""
        now = datetime.now(timezone.utc)
        recon_id = f"RECON-{uuid4().hex[:8].upper()}"
        record = AccountabilityReconciliation(
            id=recon_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            reconciliation_date=now,
            period_start=payload.period_start,
            period_end=payload.period_end,
            total_received=payload.total_received,
            performed_by=payload.performed_by,
            status=ReconciliationStatus.PENDING,
            created_at=now,
        )
        with self._lock:
            self._accountability_reconciliations[recon_id] = record
        logger.info("Created reconciliation %s for site %s", recon_id, payload.site_id)
        return record

    def update_accountability_reconciliation(
        self, recon_id: str, payload: AccountabilityReconciliationUpdate
    ) -> AccountabilityReconciliation | None:
        """Update an existing accountability reconciliation."""
        with self._lock:
            existing = self._accountability_reconciliations.get(recon_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = AccountabilityReconciliation(**data)
            self._accountability_reconciliations[recon_id] = updated
        return updated

    def delete_accountability_reconciliation(self, recon_id: str) -> bool:
        """Delete an accountability reconciliation. Returns True if deleted."""
        with self._lock:
            if recon_id in self._accountability_reconciliations:
                del self._accountability_reconciliations[recon_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Accountability Deviations
    # ------------------------------------------------------------------

    def list_accountability_deviations(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[AccountabilityDeviation]:
        """List accountability deviations with optional trial_id filter."""
        with self._lock:
            result = list(self._accountability_deviations.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]

        return sorted(result, key=lambda r: r.deviation_date, reverse=True)

    def get_accountability_deviation(self, deviation_id: str) -> AccountabilityDeviation | None:
        """Get a single accountability deviation by ID."""
        with self._lock:
            return self._accountability_deviations.get(deviation_id)

    def create_accountability_deviation(
        self, payload: AccountabilityDeviationCreate
    ) -> AccountabilityDeviation:
        """Create a new accountability deviation."""
        now = datetime.now(timezone.utc)
        deviation_id = f"DEV-{uuid4().hex[:8].upper()}"
        record = AccountabilityDeviation(
            id=deviation_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            subject_id=payload.subject_id,
            deviation_date=now,
            description=payload.description,
            severity=payload.severity,
            batch_number=payload.batch_number,
            reported_by=payload.reported_by,
            created_at=now,
        )
        with self._lock:
            self._accountability_deviations[deviation_id] = record
        logger.info("Created deviation %s: %s", deviation_id, payload.severity.value)
        return record

    def update_accountability_deviation(
        self, deviation_id: str, payload: AccountabilityDeviationUpdate
    ) -> AccountabilityDeviation | None:
        """Update an existing accountability deviation."""
        with self._lock:
            existing = self._accountability_deviations.get(deviation_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = AccountabilityDeviation(**data)
            self._accountability_deviations[deviation_id] = updated
        return updated

    def delete_accountability_deviation(self, deviation_id: str) -> bool:
        """Delete an accountability deviation. Returns True if deleted."""
        with self._lock:
            if deviation_id in self._accountability_deviations:
                del self._accountability_deviations[deviation_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> DrugAccountabilityMetrics:
        """Compute aggregated drug accountability operational metrics."""
        with self._lock:
            dispensations = list(self._dispensation_records.values())
            returns = list(self._drug_returns.values())
            destructions = list(self._destruction_records.values())
            reconciliations = list(self._accountability_reconciliations.values())
            deviations = list(self._accountability_deviations.values())

        # Dispensations by type
        dispensations_by_type: dict[str, int] = {}
        for d in dispensations:
            key = d.dispensation_type.value
            dispensations_by_type[key] = dispensations_by_type.get(key, 0) + 1

        # Dispensations by status
        dispensations_by_status: dict[str, int] = {}
        for d in dispensations:
            key = d.status.value
            dispensations_by_status[key] = dispensations_by_status.get(key, 0) + 1

        # Totals
        total_quantity_dispensed = sum(d.quantity_dispensed for d in dispensations)
        total_quantity_returned = sum(r.quantity_returned for r in returns)
        total_quantity_destroyed = sum(d.quantity_destroyed for d in destructions)

        # Reconciliations with discrepancy
        reconciliations_with_discrepancy = sum(
            1 for r in reconciliations if r.discrepancy != 0
        )

        # Deviations by severity
        deviations_by_severity: dict[str, int] = {}
        for d in deviations:
            key = d.severity.value
            deviations_by_severity[key] = deviations_by_severity.get(key, 0) + 1

        # Open deviations (no resolution_date)
        open_deviations = sum(
            1 for d in deviations if d.resolution_date is None
        )

        return DrugAccountabilityMetrics(
            total_dispensations=len(dispensations),
            dispensations_by_type=dispensations_by_type,
            dispensations_by_status=dispensations_by_status,
            total_returns=len(returns),
            total_quantity_dispensed=total_quantity_dispensed,
            total_quantity_returned=total_quantity_returned,
            total_quantity_destroyed=total_quantity_destroyed,
            total_reconciliations=len(reconciliations),
            reconciliations_with_discrepancy=reconciliations_with_discrepancy,
            total_deviations=len(deviations),
            deviations_by_severity=deviations_by_severity,
            open_deviations=open_deviations,
            destruction_records=len(destructions),
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: DrugAccountabilityService | None = None
_instance_lock = threading.Lock()


def get_drug_accountability_service() -> DrugAccountabilityService:
    """Return the singleton DrugAccountabilityService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = DrugAccountabilityService()
    return _instance


def reset_drug_accountability_service() -> DrugAccountabilityService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = DrugAccountabilityService()
    return _instance
