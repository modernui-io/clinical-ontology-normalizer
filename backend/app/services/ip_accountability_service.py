"""IP Accountability (Investigational Product Accountability) Service.

Manages investigational product lifecycle at clinical trial sites: shipment receipt,
inventory tracking, dispensing to patients, returns, destruction, temperature
excursion logging, accountability log maintenance, and site-level reconciliation.

Usage:
    from app.services.ip_accountability_service import (
        get_ip_accountability_service,
    )

    svc = get_ip_accountability_service()
    shipments = svc.list_shipments()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.ip_accountability import (
    AccountabilityLog,
    AccountabilityLogCreate,
    DispensingRecord,
    DispensingRecordCreate,
    IPInventoryItem,
    IPInventoryItemCreate,
    IPInventoryItemUpdate,
    IPMetrics,
    IPReconciliation,
    IPReconciliationCreate,
    IPShipment,
    IPShipmentCreate,
    IPShipmentUpdate,
    IPStatus,
    ReconciliationStatus,
    ReturnCondition,
    ReturnRecord,
    ReturnRecordCreate,
    StorageCondition,
    TemperatureExcursion,
    TemperatureExcursionCreate,
    TemperatureExcursionResolve,
    TemperatureExcursionSeverity,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class IPAccountabilityService:
    """In-memory IP Accountability engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._shipments: dict[str, IPShipment] = {}
        self._inventory: dict[str, IPInventoryItem] = {}
        self._excursions: dict[str, TemperatureExcursion] = {}
        self._dispensing_records: dict[str, DispensingRecord] = {}
        self._return_records: dict[str, ReturnRecord] = {}
        self._accountability_logs: dict[str, AccountabilityLog] = {}
        self._reconciliations: dict[str, IPReconciliation] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic IP accountability data across clinical trial sites."""
        now = datetime.now(timezone.utc)

        # --- 4 Shipments ---
        shipments_data = [
            {
                "id": "SHIP-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "lot_number": "LOT-2025-A001",
                "batch_number": "BATCH-2025-001",
                "product_name": "Aflibercept 2mg/0.05mL",
                "quantity_shipped": 50,
                "quantity_received": 50,
                "storage_condition": StorageCondition.REFRIGERATED,
                "temperature_range_min": 2.0,
                "temperature_range_max": 8.0,
                "shipment_date": now - timedelta(days=90),
                "receipt_date": now - timedelta(days=88),
                "status": IPStatus.RECEIVED,
                "tracking_number": "FDX-98765432100",
                "carrier": "FedEx Priority",
                "created_at": now - timedelta(days=91),
            },
            {
                "id": "SHIP-002",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "lot_number": "LOT-2025-D002",
                "batch_number": "BATCH-2025-042",
                "product_name": "Dupilumab 300mg/2mL",
                "quantity_shipped": 80,
                "quantity_received": 80,
                "storage_condition": StorageCondition.REFRIGERATED,
                "temperature_range_min": 2.0,
                "temperature_range_max": 8.0,
                "shipment_date": now - timedelta(days=60),
                "receipt_date": now - timedelta(days=58),
                "status": IPStatus.RECEIVED,
                "tracking_number": "UPS-1Z999AA10123456784",
                "carrier": "UPS Healthcare",
                "created_at": now - timedelta(days=61),
            },
            {
                "id": "SHIP-003",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "lot_number": "LOT-2025-L003",
                "batch_number": "BATCH-2025-087",
                "product_name": "Cemiplimab 350mg/7mL",
                "quantity_shipped": 30,
                "quantity_received": 30,
                "storage_condition": StorageCondition.REFRIGERATED,
                "temperature_range_min": 2.0,
                "temperature_range_max": 8.0,
                "shipment_date": now - timedelta(days=45),
                "receipt_date": now - timedelta(days=43),
                "status": IPStatus.RECEIVED,
                "tracking_number": "WTC-CL789456123",
                "carrier": "World Courier",
                "created_at": now - timedelta(days=46),
            },
            {
                "id": "SHIP-004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-107",
                "lot_number": "LOT-2025-A004",
                "batch_number": "BATCH-2025-112",
                "product_name": "Aflibercept 2mg/0.05mL",
                "quantity_shipped": 40,
                "quantity_received": 38,
                "storage_condition": StorageCondition.REFRIGERATED,
                "temperature_range_min": 2.0,
                "temperature_range_max": 8.0,
                "shipment_date": now - timedelta(days=30),
                "receipt_date": now - timedelta(days=28),
                "status": IPStatus.RECEIVED,
                "tracking_number": "FDX-11223344556",
                "carrier": "FedEx Priority",
                "created_at": now - timedelta(days=31),
            },
        ]

        for s in shipments_data:
            self._shipments[s["id"]] = IPShipment(**s)

        # --- 12 Inventory Items ---
        inventory_data = [
            {
                "id": "INV-001",
                "shipment_id": "SHIP-001",
                "site_id": "SITE-101",
                "kit_number": "KIT-A001-001",
                "lot_number": "LOT-2025-A001",
                "product_name": "Aflibercept 2mg/0.05mL",
                "status": IPStatus.DISPENSED,
                "storage_condition": StorageCondition.REFRIGERATED,
                "expiry_date": now + timedelta(days=365),
                "current_quantity": 0,
                "dispensed_quantity": 6,
                "patient_id": "PAT-1001",
                "dispensed_date": now - timedelta(days=75),
                "dispensed_by": "Dr. Sarah Chen",
                "created_at": now - timedelta(days=88),
            },
            {
                "id": "INV-002",
                "shipment_id": "SHIP-001",
                "site_id": "SITE-101",
                "kit_number": "KIT-A001-002",
                "lot_number": "LOT-2025-A001",
                "product_name": "Aflibercept 2mg/0.05mL",
                "status": IPStatus.DISPENSED,
                "storage_condition": StorageCondition.REFRIGERATED,
                "expiry_date": now + timedelta(days=365),
                "current_quantity": 0,
                "dispensed_quantity": 6,
                "patient_id": "PAT-1002",
                "dispensed_date": now - timedelta(days=60),
                "dispensed_by": "Dr. Sarah Chen",
                "created_at": now - timedelta(days=88),
            },
            {
                "id": "INV-003",
                "shipment_id": "SHIP-001",
                "site_id": "SITE-101",
                "kit_number": "KIT-A001-003",
                "lot_number": "LOT-2025-A001",
                "product_name": "Aflibercept 2mg/0.05mL",
                "status": IPStatus.RELEASED,
                "storage_condition": StorageCondition.REFRIGERATED,
                "expiry_date": now + timedelta(days=365),
                "current_quantity": 6,
                "dispensed_quantity": 0,
                "patient_id": None,
                "dispensed_date": None,
                "dispensed_by": None,
                "created_at": now - timedelta(days=88),
            },
            {
                "id": "INV-004",
                "shipment_id": "SHIP-002",
                "site_id": "SITE-103",
                "kit_number": "KIT-D002-001",
                "lot_number": "LOT-2025-D002",
                "product_name": "Dupilumab 300mg/2mL",
                "status": IPStatus.DISPENSED,
                "storage_condition": StorageCondition.REFRIGERATED,
                "expiry_date": now + timedelta(days=300),
                "current_quantity": 0,
                "dispensed_quantity": 4,
                "patient_id": "PAT-2001",
                "dispensed_date": now - timedelta(days=45),
                "dispensed_by": "Dr. Michael Park",
                "created_at": now - timedelta(days=58),
            },
            {
                "id": "INV-005",
                "shipment_id": "SHIP-002",
                "site_id": "SITE-103",
                "kit_number": "KIT-D002-002",
                "lot_number": "LOT-2025-D002",
                "product_name": "Dupilumab 300mg/2mL",
                "status": IPStatus.RETURNED,
                "storage_condition": StorageCondition.REFRIGERATED,
                "expiry_date": now + timedelta(days=300),
                "current_quantity": 2,
                "dispensed_quantity": 2,
                "patient_id": "PAT-2002",
                "dispensed_date": now - timedelta(days=40),
                "dispensed_by": "Dr. Michael Park",
                "created_at": now - timedelta(days=58),
            },
            {
                "id": "INV-006",
                "shipment_id": "SHIP-002",
                "site_id": "SITE-103",
                "kit_number": "KIT-D002-003",
                "lot_number": "LOT-2025-D002",
                "product_name": "Dupilumab 300mg/2mL",
                "status": IPStatus.RELEASED,
                "storage_condition": StorageCondition.REFRIGERATED,
                "expiry_date": now + timedelta(days=300),
                "current_quantity": 4,
                "dispensed_quantity": 0,
                "patient_id": None,
                "dispensed_date": None,
                "dispensed_by": None,
                "created_at": now - timedelta(days=58),
            },
            {
                "id": "INV-007",
                "shipment_id": "SHIP-003",
                "site_id": "SITE-105",
                "kit_number": "KIT-L003-001",
                "lot_number": "LOT-2025-L003",
                "product_name": "Cemiplimab 350mg/7mL",
                "status": IPStatus.DISPENSED,
                "storage_condition": StorageCondition.REFRIGERATED,
                "expiry_date": now + timedelta(days=270),
                "current_quantity": 0,
                "dispensed_quantity": 3,
                "patient_id": "PAT-3001",
                "dispensed_date": now - timedelta(days=30),
                "dispensed_by": "Dr. Jennifer Lee",
                "created_at": now - timedelta(days=43),
            },
            {
                "id": "INV-008",
                "shipment_id": "SHIP-003",
                "site_id": "SITE-105",
                "kit_number": "KIT-L003-002",
                "lot_number": "LOT-2025-L003",
                "product_name": "Cemiplimab 350mg/7mL",
                "status": IPStatus.QUARANTINE,
                "storage_condition": StorageCondition.REFRIGERATED,
                "expiry_date": now + timedelta(days=270),
                "current_quantity": 3,
                "dispensed_quantity": 0,
                "patient_id": None,
                "dispensed_date": None,
                "dispensed_by": None,
                "created_at": now - timedelta(days=43),
            },
            {
                "id": "INV-009",
                "shipment_id": "SHIP-003",
                "site_id": "SITE-105",
                "kit_number": "KIT-L003-003",
                "lot_number": "LOT-2025-L003",
                "product_name": "Cemiplimab 350mg/7mL",
                "status": IPStatus.DESTROYED,
                "storage_condition": StorageCondition.REFRIGERATED,
                "expiry_date": now + timedelta(days=270),
                "current_quantity": 0,
                "dispensed_quantity": 0,
                "patient_id": None,
                "dispensed_date": None,
                "dispensed_by": None,
                "created_at": now - timedelta(days=43),
            },
            {
                "id": "INV-010",
                "shipment_id": "SHIP-004",
                "site_id": "SITE-107",
                "kit_number": "KIT-A004-001",
                "lot_number": "LOT-2025-A004",
                "product_name": "Aflibercept 2mg/0.05mL",
                "status": IPStatus.DISPENSED,
                "storage_condition": StorageCondition.REFRIGERATED,
                "expiry_date": now + timedelta(days=330),
                "current_quantity": 0,
                "dispensed_quantity": 6,
                "patient_id": "PAT-4001",
                "dispensed_date": now - timedelta(days=20),
                "dispensed_by": "Dr. Robert Kim",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "INV-011",
                "shipment_id": "SHIP-004",
                "site_id": "SITE-107",
                "kit_number": "KIT-A004-002",
                "lot_number": "LOT-2025-A004",
                "product_name": "Aflibercept 2mg/0.05mL",
                "status": IPStatus.RELEASED,
                "storage_condition": StorageCondition.REFRIGERATED,
                "expiry_date": now + timedelta(days=330),
                "current_quantity": 6,
                "dispensed_quantity": 0,
                "patient_id": None,
                "dispensed_date": None,
                "dispensed_by": None,
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "INV-012",
                "shipment_id": "SHIP-004",
                "site_id": "SITE-107",
                "kit_number": "KIT-A004-003",
                "lot_number": "LOT-2025-A004",
                "product_name": "Aflibercept 2mg/0.05mL",
                "status": IPStatus.EXPIRED,
                "storage_condition": StorageCondition.REFRIGERATED,
                "expiry_date": now - timedelta(days=5),
                "current_quantity": 6,
                "dispensed_quantity": 0,
                "patient_id": None,
                "dispensed_date": None,
                "dispensed_by": None,
                "created_at": now - timedelta(days=28),
            },
        ]

        for inv in inventory_data:
            self._inventory[inv["id"]] = IPInventoryItem(**inv)

        # --- 3 Temperature Excursions ---
        excursions_data = [
            {
                "id": "EXC-001",
                "site_id": "SITE-105",
                "shipment_id": "SHIP-003",
                "recorded_temperature": 12.5,
                "min_threshold": 2.0,
                "max_threshold": 8.0,
                "duration_minutes": 45,
                "severity": TemperatureExcursionSeverity.MODERATE,
                "detected_at": now - timedelta(days=35),
                "resolved_at": now - timedelta(days=35, hours=-2),
                "resolution_notes": "Refrigerator door left ajar. Product moved to backup unit. Manufacturer consulted.",
                "impact_assessment": "Product stability data reviewed. No impact on product integrity per manufacturer guidance.",
                "affected_kits": ["KIT-L003-002", "KIT-L003-003"],
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "EXC-002",
                "site_id": "SITE-107",
                "shipment_id": "SHIP-004",
                "recorded_temperature": 15.8,
                "min_threshold": 2.0,
                "max_threshold": 8.0,
                "duration_minutes": 180,
                "severity": TemperatureExcursionSeverity.CRITICAL,
                "detected_at": now - timedelta(days=10),
                "resolved_at": None,
                "resolution_notes": None,
                "impact_assessment": "Power outage caused prolonged excursion. Product quarantined pending manufacturer assessment.",
                "affected_kits": ["KIT-A004-002", "KIT-A004-003"],
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "EXC-003",
                "site_id": "SITE-101",
                "shipment_id": "SHIP-001",
                "recorded_temperature": 9.2,
                "min_threshold": 2.0,
                "max_threshold": 8.0,
                "duration_minutes": 15,
                "severity": TemperatureExcursionSeverity.MINOR,
                "detected_at": now - timedelta(days=50),
                "resolved_at": now - timedelta(days=50, hours=-1),
                "resolution_notes": "Brief excursion during inventory check. Temperature returned to range within 15 minutes.",
                "impact_assessment": "Within acceptable transient excursion limits per IB.",
                "affected_kits": ["KIT-A001-003"],
                "created_at": now - timedelta(days=50),
            },
        ]

        for exc in excursions_data:
            self._excursions[exc["id"]] = TemperatureExcursion(**exc)

        # --- 6 Dispensing Records ---
        dispensing_data = [
            {
                "id": "DISP-001",
                "inventory_item_id": "INV-001",
                "site_id": "SITE-101",
                "patient_id": "PAT-1001",
                "visit_number": "V1",
                "quantity_dispensed": 2,
                "dispensed_by": "Dr. Sarah Chen",
                "dispensed_date": now - timedelta(days=75),
                "witnessed_by": "RN Emily Watson",
                "notes": "Initial dispensing at enrollment visit",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "DISP-002",
                "inventory_item_id": "INV-001",
                "site_id": "SITE-101",
                "patient_id": "PAT-1001",
                "visit_number": "V2",
                "quantity_dispensed": 2,
                "dispensed_by": "Dr. Sarah Chen",
                "dispensed_date": now - timedelta(days=45),
                "witnessed_by": "RN Emily Watson",
                "notes": "Follow-up visit dispensing",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "DISP-003",
                "inventory_item_id": "INV-001",
                "site_id": "SITE-101",
                "patient_id": "PAT-1001",
                "visit_number": "V3",
                "quantity_dispensed": 2,
                "dispensed_by": "Dr. Sarah Chen",
                "dispensed_date": now - timedelta(days=15),
                "witnessed_by": None,
                "notes": None,
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "DISP-004",
                "inventory_item_id": "INV-004",
                "site_id": "SITE-103",
                "patient_id": "PAT-2001",
                "visit_number": "V1",
                "quantity_dispensed": 2,
                "dispensed_by": "Dr. Michael Park",
                "dispensed_date": now - timedelta(days=45),
                "witnessed_by": "RN Lisa Brown",
                "notes": "Dupilumab loading dose dispensing",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "DISP-005",
                "inventory_item_id": "INV-004",
                "site_id": "SITE-103",
                "patient_id": "PAT-2001",
                "visit_number": "V2",
                "quantity_dispensed": 2,
                "dispensed_by": "Dr. Michael Park",
                "dispensed_date": now - timedelta(days=31),
                "witnessed_by": "RN Lisa Brown",
                "notes": "Maintenance dose dispensing",
                "created_at": now - timedelta(days=31),
            },
            {
                "id": "DISP-006",
                "inventory_item_id": "INV-007",
                "site_id": "SITE-105",
                "patient_id": "PAT-3001",
                "visit_number": "V1",
                "quantity_dispensed": 3,
                "dispensed_by": "Dr. Jennifer Lee",
                "dispensed_date": now - timedelta(days=30),
                "witnessed_by": "PharmD David Wong",
                "notes": "Cemiplimab infusion preparation",
                "created_at": now - timedelta(days=30),
            },
        ]

        for d in dispensing_data:
            self._dispensing_records[d["id"]] = DispensingRecord(**d)

        # --- 2 Return Records ---
        return_data = [
            {
                "id": "RET-001",
                "inventory_item_id": "INV-005",
                "site_id": "SITE-103",
                "patient_id": "PAT-2002",
                "quantity_returned": 2,
                "returned_date": now - timedelta(days=20),
                "condition": ReturnCondition.PARTIALLY_USED,
                "destruction_required": True,
                "destruction_date": now - timedelta(days=15),
                "destroyed_by": "PharmD Maria Santos",
                "notes": "Patient withdrew from study. Returned unused syringes.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "RET-002",
                "inventory_item_id": "INV-010",
                "site_id": "SITE-107",
                "patient_id": "PAT-4001",
                "quantity_returned": 1,
                "returned_date": now - timedelta(days=5),
                "condition": ReturnCondition.INTACT,
                "destruction_required": False,
                "destruction_date": None,
                "destroyed_by": None,
                "notes": "Patient returned unused vials at scheduled visit.",
                "created_at": now - timedelta(days=5),
            },
        ]

        for r in return_data:
            self._return_records[r["id"]] = ReturnRecord(**r)

        # --- 3 Accountability Logs ---
        log_data = [
            {
                "id": "LOG-001",
                "site_id": "SITE-101",
                "trial_id": EYLEA_TRIAL,
                "log_date": now - timedelta(days=30),
                "opening_balance": 50,
                "received": 0,
                "dispensed": 12,
                "returned": 0,
                "destroyed": 0,
                "adjustments": 0,
                "closing_balance": 38,
                "reconciled_by": "PharmD James Wilson",
                "reconciliation_status": ReconciliationStatus.COMPLETED,
                "discrepancy_notes": None,
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "LOG-002",
                "site_id": "SITE-103",
                "trial_id": DUPIXENT_TRIAL,
                "log_date": now - timedelta(days=14),
                "opening_balance": 80,
                "received": 0,
                "dispensed": 6,
                "returned": 2,
                "destroyed": 2,
                "adjustments": 0,
                "closing_balance": 74,
                "reconciled_by": "PharmD Maria Santos",
                "reconciliation_status": ReconciliationStatus.COMPLETED,
                "discrepancy_notes": None,
                "created_at": now - timedelta(days=14),
            },
            {
                "id": "LOG-003",
                "site_id": "SITE-107",
                "trial_id": EYLEA_TRIAL,
                "log_date": now - timedelta(days=7),
                "opening_balance": 38,
                "received": 0,
                "dispensed": 6,
                "returned": 1,
                "destroyed": 0,
                "adjustments": -2,
                "closing_balance": 31,
                "reconciled_by": None,
                "reconciliation_status": ReconciliationStatus.DISCREPANCY_FOUND,
                "discrepancy_notes": "2 units unaccounted for. Shipment receipt discrepancy (40 shipped, 38 received).",
                "created_at": now - timedelta(days=7),
            },
        ]

        for lg in log_data:
            self._accountability_logs[lg["id"]] = AccountabilityLog(**lg)

        # --- 2 Reconciliations ---
        recon_data = [
            {
                "id": "REC-001",
                "site_id": "SITE-101",
                "trial_id": EYLEA_TRIAL,
                "reconciliation_date": now - timedelta(days=30),
                "status": ReconciliationStatus.COMPLETED,
                "expected_quantity": 38,
                "actual_quantity": 38,
                "discrepancy": 0,
                "investigator_signature": "Dr. Sarah Chen",
                "monitor_signature": "CRA Patricia Wells",
                "notes": "Full reconciliation completed. No discrepancies.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "REC-002",
                "site_id": "SITE-107",
                "trial_id": EYLEA_TRIAL,
                "reconciliation_date": now - timedelta(days=7),
                "status": ReconciliationStatus.DISCREPANCY_FOUND,
                "expected_quantity": 33,
                "actual_quantity": 31,
                "discrepancy": -2,
                "investigator_signature": "Dr. Robert Kim",
                "monitor_signature": None,
                "notes": "2-unit discrepancy identified. Investigation in progress. Possible shipment shortage.",
                "created_at": now - timedelta(days=7),
            },
        ]

        for rc in recon_data:
            self._reconciliations[rc["id"]] = IPReconciliation(**rc)

    # ------------------------------------------------------------------
    # Shipment Management
    # ------------------------------------------------------------------

    def list_shipments(
        self,
        *,
        site_id: str | None = None,
        trial_id: str | None = None,
        status: IPStatus | None = None,
    ) -> list[IPShipment]:
        """List shipments with optional filters."""
        with self._lock:
            result = list(self._shipments.values())

        if site_id is not None:
            result = [s for s in result if s.site_id == site_id]
        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if status is not None:
            result = [s for s in result if s.status == status]

        return sorted(result, key=lambda s: s.shipment_date, reverse=True)

    def get_shipment(self, shipment_id: str) -> IPShipment | None:
        """Get a single shipment by ID."""
        with self._lock:
            return self._shipments.get(shipment_id)

    def create_shipment(self, payload: IPShipmentCreate) -> IPShipment:
        """Create a new IP shipment."""
        now = datetime.now(timezone.utc)
        shipment_id = f"SHIP-{uuid4().hex[:8].upper()}"
        shipment = IPShipment(
            id=shipment_id,
            **payload.model_dump(),
            created_at=now,
        )
        with self._lock:
            self._shipments[shipment_id] = shipment
        logger.info("Created shipment %s for site %s", shipment_id, payload.site_id)
        return shipment

    def update_shipment(self, shipment_id: str, payload: IPShipmentUpdate) -> IPShipment | None:
        """Update an existing shipment."""
        with self._lock:
            existing = self._shipments.get(shipment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = IPShipment(**data)
            self._shipments[shipment_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Inventory Management
    # ------------------------------------------------------------------

    def list_inventory(
        self,
        *,
        site_id: str | None = None,
        status: IPStatus | None = None,
        shipment_id: str | None = None,
    ) -> list[IPInventoryItem]:
        """List inventory items with optional filters."""
        with self._lock:
            result = list(self._inventory.values())

        if site_id is not None:
            result = [i for i in result if i.site_id == site_id]
        if status is not None:
            result = [i for i in result if i.status == status]
        if shipment_id is not None:
            result = [i for i in result if i.shipment_id == shipment_id]

        return sorted(result, key=lambda i: i.created_at, reverse=True)

    def get_inventory_item(self, item_id: str) -> IPInventoryItem | None:
        """Get a single inventory item by ID."""
        with self._lock:
            return self._inventory.get(item_id)

    def create_inventory_item(self, payload: IPInventoryItemCreate) -> IPInventoryItem:
        """Create an inventory item."""
        now = datetime.now(timezone.utc)
        item_id = f"INV-{uuid4().hex[:8].upper()}"
        item = IPInventoryItem(
            id=item_id,
            status=IPStatus.RECEIVED,
            dispensed_quantity=0,
            patient_id=None,
            dispensed_date=None,
            dispensed_by=None,
            created_at=now,
            **payload.model_dump(),
        )
        with self._lock:
            self._inventory[item_id] = item
        logger.info("Created inventory item %s for site %s", item_id, payload.site_id)
        return item

    def update_inventory_item(self, item_id: str, payload: IPInventoryItemUpdate) -> IPInventoryItem | None:
        """Update an inventory item."""
        with self._lock:
            existing = self._inventory.get(item_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = IPInventoryItem(**data)
            self._inventory[item_id] = updated
        return updated

    def get_site_inventory(self, site_id: str) -> list[IPInventoryItem]:
        """Get all inventory items for a specific site."""
        with self._lock:
            result = [
                item for item in self._inventory.values()
                if item.site_id == site_id
            ]
        return sorted(result, key=lambda i: i.kit_number)

    # ------------------------------------------------------------------
    # Dispensing
    # ------------------------------------------------------------------

    def record_dispensing(self, payload: DispensingRecordCreate) -> DispensingRecord:
        """Record a dispensing event and update inventory."""
        now = datetime.now(timezone.utc)
        disp_id = f"DISP-{uuid4().hex[:8].upper()}"

        with self._lock:
            # Validate inventory item exists
            item = self._inventory.get(payload.inventory_item_id)
            if item is None:
                raise ValueError(f"Inventory item '{payload.inventory_item_id}' not found")

            # Validate item can be dispensed
            if item.status not in (IPStatus.RELEASED, IPStatus.RECEIVED):
                raise ValueError(
                    f"Inventory item '{payload.inventory_item_id}' cannot be dispensed "
                    f"(current status: {item.status.value})"
                )

            if item.current_quantity < payload.quantity_dispensed:
                raise ValueError(
                    f"Insufficient quantity: requested {payload.quantity_dispensed}, "
                    f"available {item.current_quantity}"
                )

            # Create dispensing record
            record = DispensingRecord(
                id=disp_id,
                created_at=now,
                **payload.model_dump(),
            )
            self._dispensing_records[disp_id] = record

            # Update inventory item
            data = item.model_dump()
            data["current_quantity"] -= payload.quantity_dispensed
            data["dispensed_quantity"] += payload.quantity_dispensed
            data["patient_id"] = payload.patient_id
            data["dispensed_date"] = payload.dispensed_date
            data["dispensed_by"] = payload.dispensed_by
            if data["current_quantity"] == 0:
                data["status"] = IPStatus.DISPENSED
            updated_item = IPInventoryItem(**data)
            self._inventory[payload.inventory_item_id] = updated_item

        logger.info(
            "Dispensed %d units from %s to patient %s",
            payload.quantity_dispensed, payload.inventory_item_id, payload.patient_id,
        )
        return record

    def list_dispensing_records(
        self,
        *,
        site_id: str | None = None,
        patient_id: str | None = None,
    ) -> list[DispensingRecord]:
        """List dispensing records with optional filters."""
        with self._lock:
            result = list(self._dispensing_records.values())

        if site_id is not None:
            result = [r for r in result if r.site_id == site_id]
        if patient_id is not None:
            result = [r for r in result if r.patient_id == patient_id]

        return sorted(result, key=lambda r: r.dispensed_date, reverse=True)

    # ------------------------------------------------------------------
    # Returns
    # ------------------------------------------------------------------

    def record_return(self, payload: ReturnRecordCreate) -> ReturnRecord:
        """Record a product return and update inventory."""
        now = datetime.now(timezone.utc)
        ret_id = f"RET-{uuid4().hex[:8].upper()}"

        with self._lock:
            # Validate inventory item exists
            item = self._inventory.get(payload.inventory_item_id)
            if item is None:
                raise ValueError(f"Inventory item '{payload.inventory_item_id}' not found")

            # Create return record
            record = ReturnRecord(
                id=ret_id,
                destruction_date=None,
                destroyed_by=None,
                created_at=now,
                **payload.model_dump(),
            )
            self._return_records[ret_id] = record

            # Update inventory item status
            data = item.model_dump()
            data["status"] = IPStatus.RETURNED
            updated_item = IPInventoryItem(**data)
            self._inventory[payload.inventory_item_id] = updated_item

        logger.info(
            "Returned %d units for %s from patient %s",
            payload.quantity_returned, payload.inventory_item_id, payload.patient_id,
        )
        return record

    def list_return_records(
        self,
        *,
        site_id: str | None = None,
        patient_id: str | None = None,
    ) -> list[ReturnRecord]:
        """List return records with optional filters."""
        with self._lock:
            result = list(self._return_records.values())

        if site_id is not None:
            result = [r for r in result if r.site_id == site_id]
        if patient_id is not None:
            result = [r for r in result if r.patient_id == patient_id]

        return sorted(result, key=lambda r: r.returned_date, reverse=True)

    # ------------------------------------------------------------------
    # Temperature Excursions
    # ------------------------------------------------------------------

    def log_temperature_excursion(self, payload: TemperatureExcursionCreate) -> TemperatureExcursion:
        """Log a temperature excursion event."""
        now = datetime.now(timezone.utc)
        exc_id = f"EXC-{uuid4().hex[:8].upper()}"

        excursion = TemperatureExcursion(
            id=exc_id,
            resolved_at=None,
            resolution_notes=None,
            created_at=now,
            **payload.model_dump(),
        )

        with self._lock:
            self._excursions[exc_id] = excursion

        logger.info(
            "Temperature excursion %s logged at site %s: %.1f C (range: %.1f-%.1f C)",
            exc_id, payload.site_id, payload.recorded_temperature,
            payload.min_threshold, payload.max_threshold,
        )
        return excursion

    def resolve_temperature_excursion(
        self,
        excursion_id: str,
        payload: TemperatureExcursionResolve,
    ) -> TemperatureExcursion | None:
        """Resolve a temperature excursion."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._excursions.get(excursion_id)
            if existing is None:
                return None

            if existing.resolved_at is not None:
                raise ValueError(f"Excursion '{excursion_id}' is already resolved")

            data = existing.model_dump()
            data["resolved_at"] = now
            data["resolution_notes"] = payload.resolution_notes
            if payload.impact_assessment is not None:
                data["impact_assessment"] = payload.impact_assessment
            updated = TemperatureExcursion(**data)
            self._excursions[excursion_id] = updated

        logger.info("Resolved temperature excursion %s", excursion_id)
        return updated

    def list_temperature_excursions(
        self,
        *,
        site_id: str | None = None,
        severity: TemperatureExcursionSeverity | None = None,
        resolved: bool | None = None,
    ) -> list[TemperatureExcursion]:
        """List temperature excursions with optional filters."""
        with self._lock:
            result = list(self._excursions.values())

        if site_id is not None:
            result = [e for e in result if e.site_id == site_id]
        if severity is not None:
            result = [e for e in result if e.severity == severity]
        if resolved is not None:
            if resolved:
                result = [e for e in result if e.resolved_at is not None]
            else:
                result = [e for e in result if e.resolved_at is None]

        return sorted(result, key=lambda e: e.detected_at, reverse=True)

    def get_temperature_excursion(self, excursion_id: str) -> TemperatureExcursion | None:
        """Get a single temperature excursion by ID."""
        with self._lock:
            return self._excursions.get(excursion_id)

    # ------------------------------------------------------------------
    # Accountability Logs
    # ------------------------------------------------------------------

    def create_accountability_log(self, payload: AccountabilityLogCreate) -> AccountabilityLog:
        """Create an accountability log entry."""
        now = datetime.now(timezone.utc)
        log_id = f"LOG-{uuid4().hex[:8].upper()}"

        log_entry = AccountabilityLog(
            id=log_id,
            reconciliation_status=ReconciliationStatus.PENDING,
            discrepancy_notes=None,
            created_at=now,
            **payload.model_dump(),
        )

        with self._lock:
            self._accountability_logs[log_id] = log_entry

        logger.info("Created accountability log %s for site %s", log_id, payload.site_id)
        return log_entry

    def list_accountability_logs(
        self,
        *,
        site_id: str | None = None,
        trial_id: str | None = None,
        reconciliation_status: ReconciliationStatus | None = None,
    ) -> list[AccountabilityLog]:
        """List accountability logs with optional filters."""
        with self._lock:
            result = list(self._accountability_logs.values())

        if site_id is not None:
            result = [lg for lg in result if lg.site_id == site_id]
        if trial_id is not None:
            result = [lg for lg in result if lg.trial_id == trial_id]
        if reconciliation_status is not None:
            result = [lg for lg in result if lg.reconciliation_status == reconciliation_status]

        return sorted(result, key=lambda lg: lg.log_date, reverse=True)

    def get_accountability_log(self, log_id: str) -> AccountabilityLog | None:
        """Get a single accountability log by ID."""
        with self._lock:
            return self._accountability_logs.get(log_id)

    # ------------------------------------------------------------------
    # Reconciliation
    # ------------------------------------------------------------------

    def perform_reconciliation(self, payload: IPReconciliationCreate) -> IPReconciliation:
        """Perform an IP reconciliation."""
        now = datetime.now(timezone.utc)
        recon_id = f"REC-{uuid4().hex[:8].upper()}"

        discrepancy = payload.actual_quantity - payload.expected_quantity

        if discrepancy == 0:
            status = ReconciliationStatus.COMPLETED
        else:
            status = ReconciliationStatus.DISCREPANCY_FOUND

        recon = IPReconciliation(
            id=recon_id,
            site_id=payload.site_id,
            trial_id=payload.trial_id,
            reconciliation_date=payload.reconciliation_date,
            status=status,
            expected_quantity=payload.expected_quantity,
            actual_quantity=payload.actual_quantity,
            discrepancy=discrepancy,
            investigator_signature=payload.investigator_signature,
            monitor_signature=payload.monitor_signature,
            notes=payload.notes,
            created_at=now,
        )

        with self._lock:
            self._reconciliations[recon_id] = recon

        logger.info(
            "Reconciliation %s for site %s: expected=%d actual=%d discrepancy=%d",
            recon_id, payload.site_id, payload.expected_quantity,
            payload.actual_quantity, discrepancy,
        )
        return recon

    def list_reconciliations(
        self,
        *,
        site_id: str | None = None,
        trial_id: str | None = None,
        status: ReconciliationStatus | None = None,
    ) -> list[IPReconciliation]:
        """List reconciliation records with optional filters."""
        with self._lock:
            result = list(self._reconciliations.values())

        if site_id is not None:
            result = [r for r in result if r.site_id == site_id]
        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if status is not None:
            result = [r for r in result if r.status == status]

        return sorted(result, key=lambda r: r.reconciliation_date, reverse=True)

    def get_reconciliation(self, recon_id: str) -> IPReconciliation | None:
        """Get a single reconciliation by ID."""
        with self._lock:
            return self._reconciliations.get(recon_id)

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self) -> IPMetrics:
        """Compute aggregated IP accountability operational metrics."""
        with self._lock:
            shipments = list(self._shipments.values())
            inventory = list(self._inventory.values())
            excursions = list(self._excursions.values())
            reconciliations = list(self._reconciliations.values())

        total_shipments = len(shipments)
        total_kits = len(inventory)
        kits_dispensed = sum(1 for i in inventory if i.status == IPStatus.DISPENSED)
        kits_returned = sum(1 for i in inventory if i.status == IPStatus.RETURNED)
        kits_destroyed = sum(1 for i in inventory if i.status == IPStatus.DESTROYED)
        temperature_excursions = len(excursions)

        # Sites with discrepancies (from reconciliations)
        sites_with_discrepancies = len({
            r.site_id for r in reconciliations
            if r.status == ReconciliationStatus.DISCREPANCY_FOUND
        })

        # Reconciliation completion %
        total_recons = len(reconciliations)
        completed_recons = sum(
            1 for r in reconciliations
            if r.status in (ReconciliationStatus.COMPLETED, ReconciliationStatus.RESOLVED)
        )
        recon_pct = round(
            (completed_recons / total_recons * 100.0) if total_recons > 0 else 0.0,
            1,
        )

        return IPMetrics(
            total_shipments=total_shipments,
            total_kits=total_kits,
            kits_dispensed=kits_dispensed,
            kits_returned=kits_returned,
            kits_destroyed=kits_destroyed,
            temperature_excursions=temperature_excursions,
            sites_with_discrepancies=sites_with_discrepancies,
            reconciliation_completion_pct=recon_pct,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: IPAccountabilityService | None = None
_instance_lock = threading.Lock()


def get_ip_accountability_service() -> IPAccountabilityService:
    """Return the singleton IPAccountabilityService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = IPAccountabilityService()
    return _instance


def reset_ip_accountability_service() -> IPAccountabilityService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = IPAccountabilityService()
    return _instance
