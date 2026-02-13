"""Inventory Reconciliation Service (INV-REC).

Manages investigational product inventory operations: site inventory snapshots,
reconciliation audits, discrepancy records, lot accountability logs, and
inventory reconciliation metrics.

Usage:
    from app.services.inventory_reconciliation_service import (
        get_inventory_reconciliation_service,
    )

    svc = get_inventory_reconciliation_service()
    snapshots = svc.list_site_inventory_snapshots()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.inventory_reconciliation import (
    AccountabilityAction,
    AuditOutcome,
    DiscrepancyRecord,
    DiscrepancyRecordCreate,
    DiscrepancyRecordUpdate,
    DiscrepancySeverity,
    DiscrepancyType,
    InventoryReconciliationMetrics,
    InventoryStatus,
    LotAccountabilityLog,
    LotAccountabilityLogCreate,
    LotAccountabilityLogUpdate,
    ReconciliationAudit,
    ReconciliationAuditCreate,
    ReconciliationAuditUpdate,
    SiteInventorySnapshot,
    SiteInventorySnapshotCreate,
    SiteInventorySnapshotUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class InventoryReconciliationService:
    """In-memory Inventory Reconciliation engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._site_inventory_snapshots: dict[str, SiteInventorySnapshot] = {}
        self._reconciliation_audits: dict[str, ReconciliationAudit] = {}
        self._discrepancy_records: dict[str, DiscrepancyRecord] = {}
        self._lot_accountability_logs: dict[str, LotAccountabilityLog] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic inventory reconciliation data."""
        now = datetime.now(timezone.utc)

        # --- 12 Site Inventory Snapshots ---
        snapshots_data = [
            {
                "id": "SIS-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "site_name": "New York Clinical Center",
                "snapshot_date": now - timedelta(days=90),
                "inventory_status": InventoryStatus.RECONCILED,
                "product_name": "Aflibercept 2mg/0.05mL",
                "lot_number": "LOT-EYL-2025-A001",
                "total_received": 100,
                "total_dispensed": 45,
                "total_returned": 5,
                "total_destroyed": 2,
                "current_on_hand": 48,
                "expected_on_hand": 48,
                "expiry_date": now + timedelta(days=180),
                "storage_condition": "2-8C refrigerated",
                "recorded_by": "Pharmacist Sarah Chen",
                "notes": "Monthly reconciliation complete. All counts match.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "SIS-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "site_name": "New York Clinical Center",
                "snapshot_date": now - timedelta(days=60),
                "inventory_status": InventoryStatus.RECONCILED,
                "product_name": "Aflibercept 2mg/0.05mL",
                "lot_number": "LOT-EYL-2025-A002",
                "total_received": 50,
                "total_dispensed": 20,
                "total_returned": 3,
                "total_destroyed": 0,
                "current_on_hand": 27,
                "expected_on_hand": 27,
                "expiry_date": now + timedelta(days=270),
                "storage_condition": "2-8C refrigerated",
                "recorded_by": "Pharmacist Sarah Chen",
                "notes": "Second lot reconciliation. No issues.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "SIS-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "site_name": "Los Angeles Research Clinic",
                "snapshot_date": now - timedelta(days=45),
                "inventory_status": InventoryStatus.DISCREPANCY_FOUND,
                "product_name": "Aflibercept 2mg/0.05mL",
                "lot_number": "LOT-EYL-2025-A001",
                "total_received": 80,
                "total_dispensed": 35,
                "total_returned": 2,
                "total_destroyed": 1,
                "current_on_hand": 40,
                "expected_on_hand": 42,
                "expiry_date": now + timedelta(days=150),
                "storage_condition": "2-8C refrigerated",
                "recorded_by": "Pharmacist Tom Bradley",
                "notes": "Discrepancy of 2 units found during count. Investigation initiated.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "SIS-004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "site_name": "Los Angeles Research Clinic",
                "snapshot_date": now - timedelta(days=15),
                "inventory_status": InventoryStatus.PENDING_RECONCILIATION,
                "product_name": "Aflibercept 2mg/0.05mL",
                "lot_number": "LOT-EYL-2025-A003",
                "total_received": 60,
                "total_dispensed": 10,
                "total_returned": 0,
                "total_destroyed": 0,
                "current_on_hand": 50,
                "expected_on_hand": 50,
                "expiry_date": now + timedelta(days=365),
                "storage_condition": "2-8C refrigerated",
                "recorded_by": "Pharmacist Tom Bradley",
                "notes": "New shipment received. Reconciliation pending.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "SIS-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "site_name": "Chicago Dermatology Institute",
                "snapshot_date": now - timedelta(days=75),
                "inventory_status": InventoryStatus.RECONCILED,
                "product_name": "Dupilumab 300mg/2mL",
                "lot_number": "LOT-DUP-2025-B001",
                "total_received": 200,
                "total_dispensed": 120,
                "total_returned": 15,
                "total_destroyed": 5,
                "current_on_hand": 60,
                "expected_on_hand": 60,
                "expiry_date": now + timedelta(days=240),
                "storage_condition": "2-8C refrigerated",
                "recorded_by": "Pharmacist Lisa Wang",
                "notes": "Quarterly reconciliation. All IP accounted for.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "SIS-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "site_name": "Chicago Dermatology Institute",
                "snapshot_date": now - timedelta(days=30),
                "inventory_status": InventoryStatus.UNDER_INVESTIGATION,
                "product_name": "Dupilumab 300mg/2mL",
                "lot_number": "LOT-DUP-2025-B002",
                "total_received": 150,
                "total_dispensed": 80,
                "total_returned": 8,
                "total_destroyed": 3,
                "current_on_hand": 56,
                "expected_on_hand": 59,
                "expiry_date": now + timedelta(days=300),
                "storage_condition": "2-8C refrigerated",
                "recorded_by": "Pharmacist Lisa Wang",
                "notes": "3-unit variance detected. Temperature excursion may be factor.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "SIS-007",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "site_name": "Boston Allergy Center",
                "snapshot_date": now - timedelta(days=50),
                "inventory_status": InventoryStatus.RECONCILED,
                "product_name": "Dupilumab 300mg/2mL",
                "lot_number": "LOT-DUP-2025-B001",
                "total_received": 100,
                "total_dispensed": 55,
                "total_returned": 10,
                "total_destroyed": 2,
                "current_on_hand": 33,
                "expected_on_hand": 33,
                "expiry_date": now + timedelta(days=200),
                "storage_condition": "2-8C refrigerated",
                "recorded_by": "Pharmacist James Morton",
                "notes": "Reconciliation complete. All documentation verified.",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "SIS-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "site_name": "Boston Allergy Center",
                "snapshot_date": now - timedelta(days=10),
                "inventory_status": InventoryStatus.QUARANTINED,
                "product_name": "Dupilumab 300mg/2mL",
                "lot_number": "LOT-DUP-2025-B003",
                "total_received": 75,
                "total_dispensed": 0,
                "total_returned": 0,
                "total_destroyed": 0,
                "current_on_hand": 75,
                "expected_on_hand": 75,
                "expiry_date": now + timedelta(days=90),
                "storage_condition": "2-8C refrigerated",
                "recorded_by": "Pharmacist James Morton",
                "notes": "Lot quarantined pending temperature excursion investigation.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "SIS-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "site_name": "Houston Oncology Network",
                "snapshot_date": now - timedelta(days=70),
                "inventory_status": InventoryStatus.RECONCILED,
                "product_name": "Cemiplimab 350mg/7mL",
                "lot_number": "LOT-LIB-2025-C001",
                "total_received": 50,
                "total_dispensed": 25,
                "total_returned": 3,
                "total_destroyed": 1,
                "current_on_hand": 21,
                "expected_on_hand": 21,
                "expiry_date": now + timedelta(days=210),
                "storage_condition": "2-8C refrigerated, protect from light",
                "recorded_by": "Pharmacist Robert Kim",
                "notes": "All IV infusion bags accounted for. Chain of custody complete.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "SIS-010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "site_name": "Houston Oncology Network",
                "snapshot_date": now - timedelta(days=20),
                "inventory_status": InventoryStatus.PENDING_RECONCILIATION,
                "product_name": "Cemiplimab 350mg/7mL",
                "lot_number": "LOT-LIB-2025-C002",
                "total_received": 40,
                "total_dispensed": 12,
                "total_returned": 1,
                "total_destroyed": 0,
                "current_on_hand": 27,
                "expected_on_hand": 27,
                "expiry_date": now + timedelta(days=330),
                "storage_condition": "2-8C refrigerated, protect from light",
                "recorded_by": "Pharmacist Robert Kim",
                "notes": "Awaiting pharmacy sign-off for reconciliation.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "SIS-011",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "site_name": "Seattle Cancer Institute",
                "snapshot_date": now - timedelta(days=55),
                "inventory_status": InventoryStatus.CLOSED,
                "product_name": "Cemiplimab 350mg/7mL",
                "lot_number": "LOT-LIB-2025-C001",
                "total_received": 30,
                "total_dispensed": 18,
                "total_returned": 5,
                "total_destroyed": 7,
                "current_on_hand": 0,
                "expected_on_hand": 0,
                "expiry_date": now - timedelta(days=10),
                "storage_condition": "2-8C refrigerated, protect from light",
                "recorded_by": "Pharmacist Amy Chen",
                "notes": "Lot fully consumed and destroyed. Final reconciliation complete.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "SIS-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "site_name": "Seattle Cancer Institute",
                "snapshot_date": now - timedelta(days=5),
                "inventory_status": InventoryStatus.DISCREPANCY_FOUND,
                "product_name": "Cemiplimab 350mg/7mL",
                "lot_number": "LOT-LIB-2025-C003",
                "total_received": 25,
                "total_dispensed": 8,
                "total_returned": 0,
                "total_destroyed": 0,
                "current_on_hand": 16,
                "expected_on_hand": 17,
                "expiry_date": now + timedelta(days=365),
                "storage_condition": "2-8C refrigerated, protect from light",
                "recorded_by": "Pharmacist Amy Chen",
                "notes": "1-unit shortage detected. Documentation gap under review.",
                "created_at": now - timedelta(days=5),
            },
        ]

        for s in snapshots_data:
            self._site_inventory_snapshots[s["id"]] = SiteInventorySnapshot(**s)

        # --- 12 Reconciliation Audits ---
        audits_data = [
            {
                "id": "RAD-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "snapshot_id": "SIS-001",
                "audit_date": now - timedelta(days=89),
                "audit_outcome": AuditOutcome.PASS,
                "auditor_name": "Dr. Elena Voss",
                "auditor_role": "Clinical Monitor",
                "units_counted": 48,
                "units_expected": 48,
                "variance": 0,
                "documentation_complete": True,
                "temperature_logs_verified": True,
                "follow_up_required": False,
                "follow_up_date": None,
                "notes": "Routine monitoring visit. All counts verified. No findings.",
                "created_at": now - timedelta(days=89),
            },
            {
                "id": "RAD-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "snapshot_id": "SIS-002",
                "audit_date": now - timedelta(days=59),
                "audit_outcome": AuditOutcome.PASS,
                "auditor_name": "Dr. Elena Voss",
                "auditor_role": "Clinical Monitor",
                "units_counted": 27,
                "units_expected": 27,
                "variance": 0,
                "documentation_complete": True,
                "temperature_logs_verified": True,
                "follow_up_required": False,
                "follow_up_date": None,
                "notes": "Second lot audit passed. Dispensing logs match accountability.",
                "created_at": now - timedelta(days=59),
            },
            {
                "id": "RAD-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "snapshot_id": "SIS-003",
                "audit_date": now - timedelta(days=44),
                "audit_outcome": AuditOutcome.FAIL,
                "auditor_name": "Dr. Mark Phillips",
                "auditor_role": "Clinical Monitor",
                "units_counted": 40,
                "units_expected": 42,
                "variance": -2,
                "documentation_complete": False,
                "temperature_logs_verified": True,
                "follow_up_required": True,
                "follow_up_date": now - timedelta(days=30),
                "notes": "2-unit shortage. Missing dispensing documentation for 2 subjects.",
                "created_at": now - timedelta(days=44),
            },
            {
                "id": "RAD-004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "snapshot_id": "SIS-003",
                "audit_date": now - timedelta(days=28),
                "audit_outcome": AuditOutcome.CONDITIONAL_PASS,
                "auditor_name": "Dr. Mark Phillips",
                "auditor_role": "Clinical Monitor",
                "units_counted": 38,
                "units_expected": 40,
                "variance": -2,
                "documentation_complete": True,
                "temperature_logs_verified": True,
                "follow_up_required": True,
                "follow_up_date": now + timedelta(days=14),
                "notes": "Documentation corrected. Variance accounted for via breakage report. Conditional pass pending CAPA.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "RAD-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "snapshot_id": "SIS-005",
                "audit_date": now - timedelta(days=74),
                "audit_outcome": AuditOutcome.PASS,
                "auditor_name": "Dr. Grace Lee",
                "auditor_role": "Senior Clinical Monitor",
                "units_counted": 60,
                "units_expected": 60,
                "variance": 0,
                "documentation_complete": True,
                "temperature_logs_verified": True,
                "follow_up_required": False,
                "follow_up_date": None,
                "notes": "Quarterly audit. Exemplary documentation and storage practices.",
                "created_at": now - timedelta(days=74),
            },
            {
                "id": "RAD-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "snapshot_id": "SIS-006",
                "audit_date": now - timedelta(days=29),
                "audit_outcome": AuditOutcome.REQUIRES_FOLLOW_UP,
                "auditor_name": "Dr. Grace Lee",
                "auditor_role": "Senior Clinical Monitor",
                "units_counted": 56,
                "units_expected": 59,
                "variance": -3,
                "documentation_complete": True,
                "temperature_logs_verified": False,
                "follow_up_required": True,
                "follow_up_date": now + timedelta(days=7),
                "notes": "Temperature logger malfunction suspected. 3-unit variance under investigation.",
                "created_at": now - timedelta(days=29),
            },
            {
                "id": "RAD-007",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "snapshot_id": "SIS-007",
                "audit_date": now - timedelta(days=49),
                "audit_outcome": AuditOutcome.PASS,
                "auditor_name": "Dr. Angela Martinez",
                "auditor_role": "Clinical Monitor",
                "units_counted": 33,
                "units_expected": 33,
                "variance": 0,
                "documentation_complete": True,
                "temperature_logs_verified": True,
                "follow_up_required": False,
                "follow_up_date": None,
                "notes": "Clean audit. All dispensing records match subject diaries.",
                "created_at": now - timedelta(days=49),
            },
            {
                "id": "RAD-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "snapshot_id": "SIS-008",
                "audit_date": now - timedelta(days=9),
                "audit_outcome": AuditOutcome.INCOMPLETE,
                "auditor_name": "Dr. Angela Martinez",
                "auditor_role": "Clinical Monitor",
                "units_counted": 75,
                "units_expected": 75,
                "variance": 0,
                "documentation_complete": False,
                "temperature_logs_verified": False,
                "follow_up_required": True,
                "follow_up_date": now + timedelta(days=14),
                "notes": "Lot quarantined. Audit paused pending temperature excursion investigation.",
                "created_at": now - timedelta(days=9),
            },
            {
                "id": "RAD-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "snapshot_id": "SIS-009",
                "audit_date": now - timedelta(days=69),
                "audit_outcome": AuditOutcome.PASS,
                "auditor_name": "Dr. David Park",
                "auditor_role": "Lead Clinical Monitor",
                "units_counted": 21,
                "units_expected": 21,
                "variance": 0,
                "documentation_complete": True,
                "temperature_logs_verified": True,
                "follow_up_required": False,
                "follow_up_date": None,
                "notes": "IV infusion accountability verified against treatment records.",
                "created_at": now - timedelta(days=69),
            },
            {
                "id": "RAD-010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "snapshot_id": "SIS-010",
                "audit_date": now - timedelta(days=19),
                "audit_outcome": AuditOutcome.NOT_APPLICABLE,
                "auditor_name": "Dr. David Park",
                "auditor_role": "Lead Clinical Monitor",
                "units_counted": 0,
                "units_expected": 0,
                "variance": 0,
                "documentation_complete": False,
                "temperature_logs_verified": False,
                "follow_up_required": False,
                "follow_up_date": None,
                "notes": "Reconciliation not yet due. Preliminary count only.",
                "created_at": now - timedelta(days=19),
            },
            {
                "id": "RAD-011",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "snapshot_id": "SIS-011",
                "audit_date": now - timedelta(days=54),
                "audit_outcome": AuditOutcome.PASS,
                "auditor_name": "Dr. Kevin Owens",
                "auditor_role": "Clinical Monitor",
                "units_counted": 0,
                "units_expected": 0,
                "variance": 0,
                "documentation_complete": True,
                "temperature_logs_verified": True,
                "follow_up_required": False,
                "follow_up_date": None,
                "notes": "Final closeout audit. All IP fully accounted for and destroyed per protocol.",
                "created_at": now - timedelta(days=54),
            },
            {
                "id": "RAD-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "snapshot_id": "SIS-012",
                "audit_date": now - timedelta(days=4),
                "audit_outcome": AuditOutcome.FAIL,
                "auditor_name": "Dr. Kevin Owens",
                "auditor_role": "Clinical Monitor",
                "units_counted": 16,
                "units_expected": 17,
                "variance": -1,
                "documentation_complete": False,
                "temperature_logs_verified": True,
                "follow_up_required": True,
                "follow_up_date": now + timedelta(days=10),
                "notes": "1-unit shortage. Missing dispensing record for subject SUBJ-L005.",
                "created_at": now - timedelta(days=4),
            },
        ]

        for a in audits_data:
            self._reconciliation_audits[a["id"]] = ReconciliationAudit(**a)

        # --- 12 Discrepancy Records ---
        discrepancies_data = [
            {
                "id": "DIS-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "snapshot_id": "SIS-003",
                "audit_id": "RAD-003",
                "discrepancy_type": DiscrepancyType.QUANTITY_MISMATCH,
                "discrepancy_severity": DiscrepancySeverity.MAJOR,
                "description": "2-unit shortage in Aflibercept inventory at LA site.",
                "quantity_affected": 2,
                "lot_number": "LOT-EYL-2025-A001",
                "root_cause": "Missing dispensing documentation for 2 subjects.",
                "corrective_action": "Dispensing records retroactively completed and verified.",
                "resolved": True,
                "resolved_date": now - timedelta(days=30),
                "reported_by": "Dr. Mark Phillips",
                "assigned_to": "Pharmacist Tom Bradley",
                "notes": "Root cause: documentation gap. No actual product loss.",
                "created_at": now - timedelta(days=44),
            },
            {
                "id": "DIS-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "snapshot_id": "SIS-003",
                "audit_id": "RAD-004",
                "discrepancy_type": DiscrepancyType.DOCUMENTATION_GAP,
                "discrepancy_severity": DiscrepancySeverity.MINOR,
                "description": "Breakage report filed late for 2 vials accidentally dropped.",
                "quantity_affected": 2,
                "lot_number": "LOT-EYL-2025-A001",
                "root_cause": "Staff did not immediately file breakage documentation.",
                "corrective_action": "SOP retraining on immediate incident reporting.",
                "resolved": True,
                "resolved_date": now - timedelta(days=25),
                "reported_by": "Pharmacist Tom Bradley",
                "assigned_to": "Site Manager Dr. Johnson",
                "notes": "CAPA implemented. Staff retraining completed.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "DIS-003",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "snapshot_id": "SIS-006",
                "audit_id": "RAD-006",
                "discrepancy_type": DiscrepancyType.TEMPERATURE_EXCURSION,
                "discrepancy_severity": DiscrepancySeverity.CRITICAL,
                "description": "Temperature excursion detected in pharmacy refrigerator. 3 units potentially affected.",
                "quantity_affected": 3,
                "lot_number": "LOT-DUP-2025-B002",
                "root_cause": None,
                "corrective_action": None,
                "resolved": False,
                "resolved_date": None,
                "reported_by": "Dr. Grace Lee",
                "assigned_to": "Pharmacist Lisa Wang",
                "notes": "Temperature reached 12C for 4 hours. Stability assessment ongoing.",
                "created_at": now - timedelta(days=29),
            },
            {
                "id": "DIS-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "snapshot_id": "SIS-006",
                "audit_id": None,
                "discrepancy_type": DiscrepancyType.QUANTITY_MISMATCH,
                "discrepancy_severity": DiscrepancySeverity.MAJOR,
                "description": "3-unit variance between physical count and system records.",
                "quantity_affected": 3,
                "lot_number": "LOT-DUP-2025-B002",
                "root_cause": "Units destroyed due to temperature excursion but not yet recorded.",
                "corrective_action": "Destruction records updated in IRT system.",
                "resolved": True,
                "resolved_date": now - timedelta(days=15),
                "reported_by": "Pharmacist Lisa Wang",
                "assigned_to": "Pharmacist Lisa Wang",
                "notes": "Variance resolved after temperature-damaged units recorded as destroyed.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "DIS-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "snapshot_id": "SIS-008",
                "audit_id": "RAD-008",
                "discrepancy_type": DiscrepancyType.EXPIRY_ISSUE,
                "discrepancy_severity": DiscrepancySeverity.MINOR,
                "description": "Lot approaching expiry within 90 days. Usage planning needed.",
                "quantity_affected": 75,
                "lot_number": "LOT-DUP-2025-B003",
                "root_cause": None,
                "corrective_action": None,
                "resolved": False,
                "resolved_date": None,
                "reported_by": "Pharmacist James Morton",
                "assigned_to": "Supply Chain Manager",
                "notes": "Lot re-allocation under consideration to higher-enrolling site.",
                "created_at": now - timedelta(days=9),
            },
            {
                "id": "DIS-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "snapshot_id": None,
                "audit_id": None,
                "discrepancy_type": DiscrepancyType.LOT_NUMBER_ERROR,
                "discrepancy_severity": DiscrepancySeverity.INFORMATIONAL,
                "description": "Lot number transposition error on dispensing log: B003 recorded as B030.",
                "quantity_affected": 1,
                "lot_number": "LOT-DUP-2025-B003",
                "root_cause": "Manual transcription error.",
                "corrective_action": "Dispensing log corrected. Barcode scanning enforced.",
                "resolved": True,
                "resolved_date": now - timedelta(days=7),
                "reported_by": "Pharmacist James Morton",
                "assigned_to": "Pharmacist James Morton",
                "notes": "Minor clerical error. No impact on product integrity.",
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "DIS-007",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "snapshot_id": "SIS-012",
                "audit_id": "RAD-012",
                "discrepancy_type": DiscrepancyType.MISSING_UNITS,
                "discrepancy_severity": DiscrepancySeverity.MAJOR,
                "description": "1 unit of Cemiplimab unaccounted for at Seattle site.",
                "quantity_affected": 1,
                "lot_number": "LOT-LIB-2025-C003",
                "root_cause": None,
                "corrective_action": None,
                "resolved": False,
                "resolved_date": None,
                "reported_by": "Dr. Kevin Owens",
                "assigned_to": "Pharmacist Amy Chen",
                "notes": "Investigation in progress. CCTV review of pharmacy access underway.",
                "created_at": now - timedelta(days=4),
            },
            {
                "id": "DIS-008",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "snapshot_id": "SIS-009",
                "audit_id": "RAD-009",
                "discrepancy_type": DiscrepancyType.DOCUMENTATION_GAP,
                "discrepancy_severity": DiscrepancySeverity.OBSERVATION,
                "description": "Minor documentation gap in return shipment log for 3 returned units.",
                "quantity_affected": 3,
                "lot_number": "LOT-LIB-2025-C001",
                "root_cause": "Return authorization form missing co-signature.",
                "corrective_action": "Co-signature obtained retroactively.",
                "resolved": True,
                "resolved_date": now - timedelta(days=60),
                "reported_by": "Dr. David Park",
                "assigned_to": "Pharmacist Robert Kim",
                "notes": "Administrative finding only. No impact on drug accountability.",
                "created_at": now - timedelta(days=68),
            },
            {
                "id": "DIS-009",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "snapshot_id": "SIS-001",
                "audit_id": "RAD-001",
                "discrepancy_type": DiscrepancyType.EXPIRY_ISSUE,
                "discrepancy_severity": DiscrepancySeverity.INFORMATIONAL,
                "description": "5 units within 6-month expiry window. Flagged for prioritized dispensing.",
                "quantity_affected": 5,
                "lot_number": "LOT-EYL-2025-A001",
                "root_cause": None,
                "corrective_action": "Units prioritized for next enrolled subjects.",
                "resolved": True,
                "resolved_date": now - timedelta(days=80),
                "reported_by": "Pharmacist Sarah Chen",
                "assigned_to": "Pharmacist Sarah Chen",
                "notes": "Proactive flagging. Units dispensed before expiry.",
                "created_at": now - timedelta(days=88),
            },
            {
                "id": "DIS-010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "snapshot_id": "SIS-011",
                "audit_id": "RAD-011",
                "discrepancy_type": DiscrepancyType.QUANTITY_MISMATCH,
                "discrepancy_severity": DiscrepancySeverity.MINOR,
                "description": "Destruction count initially recorded as 6 instead of 7.",
                "quantity_affected": 1,
                "lot_number": "LOT-LIB-2025-C001",
                "root_cause": "Counting error during witnessed destruction event.",
                "corrective_action": "Destruction log corrected and witnessed again.",
                "resolved": True,
                "resolved_date": now - timedelta(days=50),
                "reported_by": "Pharmacist Amy Chen",
                "assigned_to": "Pharmacist Amy Chen",
                "notes": "Minor error caught during QA review of destruction records.",
                "created_at": now - timedelta(days=53),
            },
            {
                "id": "DIS-011",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "snapshot_id": "SIS-005",
                "audit_id": "RAD-005",
                "discrepancy_type": DiscrepancyType.DOCUMENTATION_GAP,
                "discrepancy_severity": DiscrepancySeverity.OBSERVATION,
                "description": "Return receipt acknowledgment not filed for 2 weeks after receipt.",
                "quantity_affected": 15,
                "lot_number": "LOT-DUP-2025-B001",
                "root_cause": "Administrative backlog during site audit preparation.",
                "corrective_action": "Acknowledgment filed and process reminder issued.",
                "resolved": True,
                "resolved_date": now - timedelta(days=65),
                "reported_by": "Dr. Grace Lee",
                "assigned_to": "Pharmacist Lisa Wang",
                "notes": "No impact on accountability. Filing delay only.",
                "created_at": now - timedelta(days=72),
            },
            {
                "id": "DIS-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "snapshot_id": "SIS-010",
                "audit_id": None,
                "discrepancy_type": DiscrepancyType.TEMPERATURE_EXCURSION,
                "discrepancy_severity": DiscrepancySeverity.CRITICAL,
                "description": "Brief temperature excursion (15 min at 11C) during pharmacy power outage.",
                "quantity_affected": 27,
                "lot_number": "LOT-LIB-2025-C002",
                "root_cause": "Brief power outage; backup generator activated with 15-min delay.",
                "corrective_action": "Stability assessment initiated. Generator response time under review.",
                "resolved": False,
                "resolved_date": None,
                "reported_by": "Pharmacist Robert Kim",
                "assigned_to": "Facilities Manager",
                "notes": "Manufacturer stability data requested for out-of-range assessment.",
                "created_at": now - timedelta(days=18),
            },
        ]

        for d in discrepancies_data:
            self._discrepancy_records[d["id"]] = DiscrepancyRecord(**d)

        # --- 12 Lot Accountability Logs ---
        logs_data = [
            {
                "id": "LAL-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "lot_number": "LOT-EYL-2025-A001",
                "product_name": "Aflibercept 2mg/0.05mL",
                "accountability_action": AccountabilityAction.RECEIVED,
                "action_date": now - timedelta(days=100),
                "quantity": 100,
                "subject_id": None,
                "dispensing_record_id": None,
                "performed_by": "Pharmacist Sarah Chen",
                "witnessed_by": "Pharmacy Tech Mark Davis",
                "documentation_reference": "RECV-EYL-NY-001",
                "notes": "Initial lot receipt. All 100 units verified against shipping manifest.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "LAL-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "lot_number": "LOT-EYL-2025-A001",
                "product_name": "Aflibercept 2mg/0.05mL",
                "accountability_action": AccountabilityAction.DISPENSED,
                "action_date": now - timedelta(days=85),
                "quantity": 1,
                "subject_id": "SUBJ-E001",
                "dispensing_record_id": "DISP-001",
                "performed_by": "Pharmacist Sarah Chen",
                "witnessed_by": None,
                "documentation_reference": "DISP-EYL-NY-001",
                "notes": "Dispensed for Visit 1 intravitreal injection.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "LAL-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "lot_number": "LOT-EYL-2025-A001",
                "product_name": "Aflibercept 2mg/0.05mL",
                "accountability_action": AccountabilityAction.RETURNED,
                "action_date": now - timedelta(days=70),
                "quantity": 5,
                "subject_id": None,
                "dispensing_record_id": None,
                "performed_by": "Pharmacist Sarah Chen",
                "witnessed_by": "Pharmacy Tech Mark Davis",
                "documentation_reference": "RET-EYL-NY-001",
                "notes": "5 units returned to depot. Near-expiry return per protocol.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "LAL-004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "lot_number": "LOT-EYL-2025-A001",
                "product_name": "Aflibercept 2mg/0.05mL",
                "accountability_action": AccountabilityAction.DESTROYED,
                "action_date": now - timedelta(days=40),
                "quantity": 2,
                "subject_id": None,
                "dispensing_record_id": None,
                "performed_by": "Pharmacist Tom Bradley",
                "witnessed_by": "Nurse James Rodriguez",
                "documentation_reference": "DEST-EYL-LA-001",
                "notes": "2 vials destroyed due to accidental breakage. Witnessed destruction.",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "LAL-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "lot_number": "LOT-DUP-2025-B001",
                "product_name": "Dupilumab 300mg/2mL",
                "accountability_action": AccountabilityAction.RECEIVED,
                "action_date": now - timedelta(days=90),
                "quantity": 200,
                "subject_id": None,
                "dispensing_record_id": None,
                "performed_by": "Pharmacist Lisa Wang",
                "witnessed_by": "Pharmacy Tech Jun Park",
                "documentation_reference": "RECV-DUP-CHI-001",
                "notes": "200 pre-filled syringes received. Temperature verified on receipt.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "LAL-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "lot_number": "LOT-DUP-2025-B001",
                "product_name": "Dupilumab 300mg/2mL",
                "accountability_action": AccountabilityAction.DISPENSED,
                "action_date": now - timedelta(days=80),
                "quantity": 2,
                "subject_id": "SUBJ-D001",
                "dispensing_record_id": "DISP-D001",
                "performed_by": "Pharmacist Lisa Wang",
                "witnessed_by": None,
                "documentation_reference": "DISP-DUP-CHI-001",
                "notes": "2 syringes dispensed for loading dose. Subject self-administered in clinic.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "LAL-007",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "lot_number": "LOT-DUP-2025-B002",
                "product_name": "Dupilumab 300mg/2mL",
                "accountability_action": AccountabilityAction.QUARANTINED,
                "action_date": now - timedelta(days=29),
                "quantity": 3,
                "subject_id": None,
                "dispensing_record_id": None,
                "performed_by": "Pharmacist Lisa Wang",
                "witnessed_by": "Pharmacy Tech Jun Park",
                "documentation_reference": "QUAR-DUP-CHI-001",
                "notes": "3 units quarantined due to temperature excursion. Pending stability assessment.",
                "created_at": now - timedelta(days=29),
            },
            {
                "id": "LAL-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "lot_number": "LOT-DUP-2025-B001",
                "product_name": "Dupilumab 300mg/2mL",
                "accountability_action": AccountabilityAction.TRANSFERRED,
                "action_date": now - timedelta(days=60),
                "quantity": 20,
                "subject_id": None,
                "dispensing_record_id": None,
                "performed_by": "Pharmacist James Morton",
                "witnessed_by": "Pharmacy Tech Anna Wells",
                "documentation_reference": "XFER-DUP-BOS-001",
                "notes": "20 units transferred from Chicago overflow. Inter-site transfer approved.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "LAL-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "lot_number": "LOT-LIB-2025-C001",
                "product_name": "Cemiplimab 350mg/7mL",
                "accountability_action": AccountabilityAction.RECEIVED,
                "action_date": now - timedelta(days=80),
                "quantity": 50,
                "subject_id": None,
                "dispensing_record_id": None,
                "performed_by": "Pharmacist Robert Kim",
                "witnessed_by": "Pharmacy Tech David Song",
                "documentation_reference": "RECV-LIB-HOU-001",
                "notes": "50 vials received. Stored in dedicated oncology refrigerator.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "LAL-010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "lot_number": "LOT-LIB-2025-C001",
                "product_name": "Cemiplimab 350mg/7mL",
                "accountability_action": AccountabilityAction.DISPENSED,
                "action_date": now - timedelta(days=65),
                "quantity": 1,
                "subject_id": "SUBJ-L001",
                "dispensing_record_id": "DISP-L001",
                "performed_by": "Pharmacist Robert Kim",
                "witnessed_by": "Infusion Nurse Maria Torres",
                "documentation_reference": "DISP-LIB-HOU-001",
                "notes": "1 vial prepared for IV infusion. Dose verification complete.",
                "created_at": now - timedelta(days=65),
            },
            {
                "id": "LAL-011",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "lot_number": "LOT-LIB-2025-C001",
                "product_name": "Cemiplimab 350mg/7mL",
                "accountability_action": AccountabilityAction.DESTROYED,
                "action_date": now - timedelta(days=55),
                "quantity": 7,
                "subject_id": None,
                "dispensing_record_id": None,
                "performed_by": "Pharmacist Amy Chen",
                "witnessed_by": "Dr. Kevin Owens",
                "documentation_reference": "DEST-LIB-SEA-001",
                "notes": "7 expired vials destroyed per protocol. Witnessed destruction documented.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "LAL-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "lot_number": "LOT-LIB-2025-C003",
                "product_name": "Cemiplimab 350mg/7mL",
                "accountability_action": AccountabilityAction.RECEIVED,
                "action_date": now - timedelta(days=10),
                "quantity": 25,
                "subject_id": None,
                "dispensing_record_id": None,
                "performed_by": "Pharmacist Amy Chen",
                "witnessed_by": "Pharmacy Tech Lisa Tran",
                "documentation_reference": "RECV-LIB-SEA-002",
                "notes": "New lot received. Replacement for expired lot C001.",
                "created_at": now - timedelta(days=10),
            },
        ]

        for log in logs_data:
            self._lot_accountability_logs[log["id"]] = LotAccountabilityLog(**log)

    # ------------------------------------------------------------------
    # Site Inventory Snapshots
    # ------------------------------------------------------------------

    def list_site_inventory_snapshots(
        self,
        *,
        trial_id: str | None = None,
        inventory_status: InventoryStatus | None = None,
        site_id: str | None = None,
    ) -> list[SiteInventorySnapshot]:
        """List site inventory snapshots with optional filters."""
        with self._lock:
            result = list(self._site_inventory_snapshots.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if inventory_status is not None:
            result = [r for r in result if r.inventory_status == inventory_status]
        if site_id is not None:
            result = [r for r in result if r.site_id == site_id]

        return sorted(result, key=lambda r: r.snapshot_date, reverse=True)

    def get_site_inventory_snapshot(self, snapshot_id: str) -> SiteInventorySnapshot | None:
        """Get a single site inventory snapshot by ID."""
        with self._lock:
            return self._site_inventory_snapshots.get(snapshot_id)

    def create_site_inventory_snapshot(
        self, payload: SiteInventorySnapshotCreate
    ) -> SiteInventorySnapshot:
        """Create a new site inventory snapshot."""
        now = datetime.now(timezone.utc)
        snapshot_id = f"SIS-{uuid4().hex[:8].upper()}"
        record = SiteInventorySnapshot(
            id=snapshot_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            site_name=payload.site_name,
            snapshot_date=payload.snapshot_date,
            inventory_status=InventoryStatus.PENDING_RECONCILIATION,
            product_name=payload.product_name,
            lot_number=payload.lot_number,
            total_received=payload.total_received,
            total_dispensed=0,
            total_returned=0,
            total_destroyed=0,
            current_on_hand=payload.total_received,
            expected_on_hand=payload.total_received,
            expiry_date=None,
            storage_condition=None,
            recorded_by=payload.recorded_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._site_inventory_snapshots[snapshot_id] = record
        logger.info("Created site inventory snapshot %s for trial %s", snapshot_id, payload.trial_id)
        return record

    def update_site_inventory_snapshot(
        self, snapshot_id: str, payload: SiteInventorySnapshotUpdate
    ) -> SiteInventorySnapshot | None:
        """Update an existing site inventory snapshot."""
        with self._lock:
            existing = self._site_inventory_snapshots.get(snapshot_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SiteInventorySnapshot(**data)
            self._site_inventory_snapshots[snapshot_id] = updated
        return updated

    def delete_site_inventory_snapshot(self, snapshot_id: str) -> bool:
        """Delete a site inventory snapshot. Returns True if deleted."""
        with self._lock:
            if snapshot_id in self._site_inventory_snapshots:
                del self._site_inventory_snapshots[snapshot_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Reconciliation Audits
    # ------------------------------------------------------------------

    def list_reconciliation_audits(
        self,
        *,
        trial_id: str | None = None,
        audit_outcome: AuditOutcome | None = None,
        site_id: str | None = None,
    ) -> list[ReconciliationAudit]:
        """List reconciliation audits with optional filters."""
        with self._lock:
            result = list(self._reconciliation_audits.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if audit_outcome is not None:
            result = [r for r in result if r.audit_outcome == audit_outcome]
        if site_id is not None:
            result = [r for r in result if r.site_id == site_id]

        return sorted(result, key=lambda r: r.audit_date, reverse=True)

    def get_reconciliation_audit(self, audit_id: str) -> ReconciliationAudit | None:
        """Get a single reconciliation audit by ID."""
        with self._lock:
            return self._reconciliation_audits.get(audit_id)

    def create_reconciliation_audit(
        self, payload: ReconciliationAuditCreate
    ) -> ReconciliationAudit:
        """Create a new reconciliation audit."""
        now = datetime.now(timezone.utc)
        audit_id = f"RAD-{uuid4().hex[:8].upper()}"
        record = ReconciliationAudit(
            id=audit_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            snapshot_id=payload.snapshot_id,
            audit_date=payload.audit_date,
            audit_outcome=AuditOutcome.INCOMPLETE,
            auditor_name=payload.auditor_name,
            auditor_role=payload.auditor_role,
            units_counted=payload.units_counted,
            units_expected=payload.units_expected,
            variance=payload.units_counted - payload.units_expected,
            documentation_complete=False,
            temperature_logs_verified=False,
            follow_up_required=False,
            follow_up_date=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._reconciliation_audits[audit_id] = record
        logger.info("Created reconciliation audit %s for trial %s", audit_id, payload.trial_id)
        return record

    def update_reconciliation_audit(
        self, audit_id: str, payload: ReconciliationAuditUpdate
    ) -> ReconciliationAudit | None:
        """Update an existing reconciliation audit."""
        with self._lock:
            existing = self._reconciliation_audits.get(audit_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ReconciliationAudit(**data)
            self._reconciliation_audits[audit_id] = updated
        return updated

    def delete_reconciliation_audit(self, audit_id: str) -> bool:
        """Delete a reconciliation audit. Returns True if deleted."""
        with self._lock:
            if audit_id in self._reconciliation_audits:
                del self._reconciliation_audits[audit_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Discrepancy Records
    # ------------------------------------------------------------------

    def list_discrepancy_records(
        self,
        *,
        trial_id: str | None = None,
        discrepancy_type: DiscrepancyType | None = None,
        discrepancy_severity: DiscrepancySeverity | None = None,
        resolved: bool | None = None,
    ) -> list[DiscrepancyRecord]:
        """List discrepancy records with optional filters."""
        with self._lock:
            result = list(self._discrepancy_records.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if discrepancy_type is not None:
            result = [r for r in result if r.discrepancy_type == discrepancy_type]
        if discrepancy_severity is not None:
            result = [r for r in result if r.discrepancy_severity == discrepancy_severity]
        if resolved is not None:
            result = [r for r in result if r.resolved == resolved]

        return sorted(result, key=lambda r: r.created_at, reverse=True)

    def get_discrepancy_record(self, discrepancy_id: str) -> DiscrepancyRecord | None:
        """Get a single discrepancy record by ID."""
        with self._lock:
            return self._discrepancy_records.get(discrepancy_id)

    def create_discrepancy_record(
        self, payload: DiscrepancyRecordCreate
    ) -> DiscrepancyRecord:
        """Create a new discrepancy record."""
        now = datetime.now(timezone.utc)
        discrepancy_id = f"DIS-{uuid4().hex[:8].upper()}"
        record = DiscrepancyRecord(
            id=discrepancy_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            snapshot_id=payload.snapshot_id,
            audit_id=payload.audit_id,
            discrepancy_type=payload.discrepancy_type,
            discrepancy_severity=payload.discrepancy_severity,
            description=payload.description,
            quantity_affected=payload.quantity_affected,
            lot_number=None,
            root_cause=None,
            corrective_action=None,
            resolved=False,
            resolved_date=None,
            reported_by=payload.reported_by,
            assigned_to=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._discrepancy_records[discrepancy_id] = record
        logger.info("Created discrepancy record %s for trial %s", discrepancy_id, payload.trial_id)
        return record

    def update_discrepancy_record(
        self, discrepancy_id: str, payload: DiscrepancyRecordUpdate
    ) -> DiscrepancyRecord | None:
        """Update an existing discrepancy record."""
        with self._lock:
            existing = self._discrepancy_records.get(discrepancy_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DiscrepancyRecord(**data)
            self._discrepancy_records[discrepancy_id] = updated
        return updated

    def delete_discrepancy_record(self, discrepancy_id: str) -> bool:
        """Delete a discrepancy record. Returns True if deleted."""
        with self._lock:
            if discrepancy_id in self._discrepancy_records:
                del self._discrepancy_records[discrepancy_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Lot Accountability Logs
    # ------------------------------------------------------------------

    def list_lot_accountability_logs(
        self,
        *,
        trial_id: str | None = None,
        accountability_action: AccountabilityAction | None = None,
        site_id: str | None = None,
    ) -> list[LotAccountabilityLog]:
        """List lot accountability logs with optional filters."""
        with self._lock:
            result = list(self._lot_accountability_logs.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if accountability_action is not None:
            result = [r for r in result if r.accountability_action == accountability_action]
        if site_id is not None:
            result = [r for r in result if r.site_id == site_id]

        return sorted(result, key=lambda r: r.action_date, reverse=True)

    def get_lot_accountability_log(self, log_id: str) -> LotAccountabilityLog | None:
        """Get a single lot accountability log by ID."""
        with self._lock:
            return self._lot_accountability_logs.get(log_id)

    def create_lot_accountability_log(
        self, payload: LotAccountabilityLogCreate
    ) -> LotAccountabilityLog:
        """Create a new lot accountability log."""
        now = datetime.now(timezone.utc)
        log_id = f"LAL-{uuid4().hex[:8].upper()}"
        record = LotAccountabilityLog(
            id=log_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            lot_number=payload.lot_number,
            product_name=payload.product_name,
            accountability_action=payload.accountability_action,
            action_date=payload.action_date,
            quantity=payload.quantity,
            subject_id=None,
            dispensing_record_id=None,
            performed_by=payload.performed_by,
            witnessed_by=None,
            documentation_reference=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._lot_accountability_logs[log_id] = record
        logger.info("Created lot accountability log %s for trial %s", log_id, payload.trial_id)
        return record

    def update_lot_accountability_log(
        self, log_id: str, payload: LotAccountabilityLogUpdate
    ) -> LotAccountabilityLog | None:
        """Update an existing lot accountability log."""
        with self._lock:
            existing = self._lot_accountability_logs.get(log_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = LotAccountabilityLog(**data)
            self._lot_accountability_logs[log_id] = updated
        return updated

    def delete_lot_accountability_log(self, log_id: str) -> bool:
        """Delete a lot accountability log. Returns True if deleted."""
        with self._lock:
            if log_id in self._lot_accountability_logs:
                del self._lot_accountability_logs[log_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> InventoryReconciliationMetrics:
        """Compute aggregated inventory reconciliation metrics."""
        with self._lock:
            snapshots = list(self._site_inventory_snapshots.values())
            audits = list(self._reconciliation_audits.values())
            discrepancies = list(self._discrepancy_records.values())
            logs = list(self._lot_accountability_logs.values())

        # Apply trial filter if provided
        if trial_id is not None:
            snapshots = [s for s in snapshots if s.trial_id == trial_id]
            audits = [a for a in audits if a.trial_id == trial_id]
            discrepancies = [d for d in discrepancies if d.trial_id == trial_id]
            logs = [lg for lg in logs if lg.trial_id == trial_id]

        # Snapshots by status
        snapshots_by_status: dict[str, int] = {}
        for s in snapshots:
            key = s.inventory_status.value
            snapshots_by_status[key] = snapshots_by_status.get(key, 0) + 1

        # Reconciliation rate
        reconciled_count = sum(
            1 for s in snapshots if s.inventory_status == InventoryStatus.RECONCILED
        )
        reconciliation_rate = round(
            (reconciled_count / max(1, len(snapshots))) * 100, 1
        )

        # Audits by outcome
        audits_by_outcome: dict[str, int] = {}
        for a in audits:
            key = a.audit_outcome.value
            audits_by_outcome[key] = audits_by_outcome.get(key, 0) + 1

        # Audit pass rate
        pass_count = sum(
            1 for a in audits if a.audit_outcome == AuditOutcome.PASS
        )
        auditable = sum(
            1 for a in audits if a.audit_outcome not in (
                AuditOutcome.INCOMPLETE, AuditOutcome.NOT_APPLICABLE
            )
        )
        audit_pass_rate = round(
            (pass_count / max(1, auditable)) * 100, 1
        )

        # Discrepancies by type
        discrepancies_by_type: dict[str, int] = {}
        for d in discrepancies:
            key = d.discrepancy_type.value
            discrepancies_by_type[key] = discrepancies_by_type.get(key, 0) + 1

        # Discrepancies by severity
        discrepancies_by_severity: dict[str, int] = {}
        for d in discrepancies:
            key = d.discrepancy_severity.value
            discrepancies_by_severity[key] = discrepancies_by_severity.get(key, 0) + 1

        # Discrepancy resolution rate
        resolved_count = sum(1 for d in discrepancies if d.resolved)
        discrepancy_resolution_rate = round(
            (resolved_count / max(1, len(discrepancies))) * 100, 1
        )

        # Logs by action
        logs_by_action: dict[str, int] = {}
        for lg in logs:
            key = lg.accountability_action.value
            logs_by_action[key] = logs_by_action.get(key, 0) + 1

        return InventoryReconciliationMetrics(
            total_snapshots=len(snapshots),
            snapshots_by_status=snapshots_by_status,
            reconciliation_rate=reconciliation_rate,
            total_audits=len(audits),
            audits_by_outcome=audits_by_outcome,
            audit_pass_rate=audit_pass_rate,
            total_discrepancies=len(discrepancies),
            discrepancies_by_type=discrepancies_by_type,
            discrepancies_by_severity=discrepancies_by_severity,
            discrepancy_resolution_rate=discrepancy_resolution_rate,
            total_accountability_logs=len(logs),
            logs_by_action=logs_by_action,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: InventoryReconciliationService | None = None
_instance_lock = threading.Lock()


def get_inventory_reconciliation_service() -> InventoryReconciliationService:
    """Return the singleton InventoryReconciliationService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = InventoryReconciliationService()
    return _instance


def reset_inventory_reconciliation_service() -> InventoryReconciliationService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = InventoryReconciliationService()
    return _instance
