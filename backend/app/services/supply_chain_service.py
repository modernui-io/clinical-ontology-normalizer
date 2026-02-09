"""IMP Supply Chain Management Service (CLINICAL-6).

Manages drug product inventory, shipments, temperature monitoring, kit
assignments, and supply forecasting across clinical trial sites.

Usage:
    from app.services.supply_chain_service import (
        get_supply_chain_service,
    )

    svc = get_supply_chain_service()
    forecast = svc.get_supply_forecast()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.supply_chain import (
    DrugProduct,
    DrugProductCreate,
    DrugProductUpdate,
    ExcursionDisposition,
    ExpiringItemsResponse,
    InventoryItem,
    InventoryItemCreate,
    InventoryItemUpdate,
    KitAssignment,
    KitAssignRequest,
    KitReconciliation,
    KitType,
    LotTrace,
    Shipment,
    ShipmentCreate,
    ShipmentStatus,
    ShipmentUpdate,
    StorageCondition,
    SupplyForecast,
    SupplyForecastResponse,
    SupplyMetrics,
    SupplyStatus,
    TemperatureExcursion,
    TemperatureExcursionReport,
    TemperatureExcursionSeverity,
    TemperatureReading,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Storage condition temperature ranges (Celsius)
# ---------------------------------------------------------------------------

STORAGE_TEMP_RANGES: dict[StorageCondition, tuple[float, float]] = {
    StorageCondition.AMBIENT: (15.0, 25.0),
    StorageCondition.REFRIGERATED_2_8: (2.0, 8.0),
    StorageCondition.FROZEN_MINUS20: (-25.0, -15.0),
    StorageCondition.FROZEN_MINUS80: (-85.0, -75.0),
    StorageCondition.CRYOGENIC: (-200.0, -150.0),
}

# ---------------------------------------------------------------------------
# Trial and site IDs matching trial_eligibility_service
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

SITE_IDS = [
    "SITE-101", "SITE-102", "SITE-103", "SITE-104",
    "SITE-201", "SITE-202", "SITE-301", "SITE-302",
]


class SupplyChainService:
    """In-memory IMP supply chain management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._drug_products: dict[str, DrugProduct] = {}
        self._inventory: dict[str, InventoryItem] = {}
        self._shipments: dict[str, Shipment] = {}
        self._excursions: dict[str, TemperatureExcursion] = {}
        self._kit_assignments: dict[str, KitAssignment] = {}
        self._consumption_history: dict[str, dict[str, list[int]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic supply chain data for Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- Drug Products ---
        drug_products = [
            DrugProduct(
                id="DP-001",
                name="EYLEA HD (Aflibercept) 8mg",
                ndc_code="61755-0006-01",
                manufacturer="Regeneron Pharmaceuticals",
                active_ingredient="Aflibercept",
                formulation="Intravitreal injection",
                strength="8mg/0.07mL",
                storage_condition=StorageCondition.REFRIGERATED_2_8,
                shelf_life_months=24,
                retest_date=now + timedelta(days=180),
            ),
            DrugProduct(
                id="DP-002",
                name="Dupixent (Dupilumab) 300mg",
                ndc_code="00024-5918-01",
                manufacturer="Regeneron Pharmaceuticals",
                active_ingredient="Dupilumab",
                formulation="Subcutaneous injection, prefilled syringe",
                strength="300mg/2mL",
                storage_condition=StorageCondition.REFRIGERATED_2_8,
                shelf_life_months=18,
                retest_date=now + timedelta(days=120),
            ),
            DrugProduct(
                id="DP-003",
                name="Libtayo (Cemiplimab) 350mg",
                ndc_code="00024-5959-10",
                manufacturer="Regeneron Pharmaceuticals",
                active_ingredient="Cemiplimab-rwlc",
                formulation="Intravenous infusion",
                strength="350mg/7mL",
                storage_condition=StorageCondition.REFRIGERATED_2_8,
                shelf_life_months=24,
                retest_date=now + timedelta(days=200),
            ),
            DrugProduct(
                id="DP-004",
                name="Placebo (Saline)",
                ndc_code=None,
                manufacturer="Central Pharmacy",
                active_ingredient="Sodium chloride 0.9%",
                formulation="Injection",
                strength="0.9% NaCl",
                storage_condition=StorageCondition.AMBIENT,
                shelf_life_months=36,
                retest_date=None,
            ),
            DrugProduct(
                id="DP-005",
                name="Rescue Medication (Prednisone)",
                ndc_code="00054-4728-25",
                manufacturer="Roxane Laboratories",
                active_ingredient="Prednisone",
                formulation="Oral tablet",
                strength="10mg",
                storage_condition=StorageCondition.AMBIENT,
                shelf_life_months=36,
                retest_date=None,
            ),
        ]
        for dp in drug_products:
            self._drug_products[dp.id] = dp

        # --- Inventory Items ---
        inventory_data = [
            # EYLEA at ophthalmology sites
            ("INV-001", "DP-001", "LOT-2025-0001", 48, "SITE-101", StorageCondition.REFRIGERATED_2_8, 300),
            ("INV-002", "DP-001", "LOT-2025-0002", 32, "SITE-102", StorageCondition.REFRIGERATED_2_8, 270),
            ("INV-003", "DP-001", "LOT-2025-0003", 5, "SITE-103", StorageCondition.REFRIGERATED_2_8, 180),
            # Dupixent at dermatology/immunology sites
            ("INV-004", "DP-002", "LOT-2025-0004", 60, "SITE-201", StorageCondition.REFRIGERATED_2_8, 240),
            ("INV-005", "DP-002", "LOT-2025-0005", 24, "SITE-202", StorageCondition.REFRIGERATED_2_8, 210),
            ("INV-006", "DP-002", "LOT-2025-0006", 3, "SITE-104", StorageCondition.REFRIGERATED_2_8, 150),
            # Libtayo at oncology sites
            ("INV-007", "DP-003", "LOT-2025-0007", 20, "SITE-301", StorageCondition.REFRIGERATED_2_8, 360),
            ("INV-008", "DP-003", "LOT-2025-0008", 15, "SITE-302", StorageCondition.REFRIGERATED_2_8, 330),
            # Placebo at multiple sites
            ("INV-009", "DP-004", "LOT-2025-0009", 100, "SITE-101", StorageCondition.AMBIENT, 540),
            ("INV-010", "DP-004", "LOT-2025-0010", 80, "SITE-201", StorageCondition.AMBIENT, 540),
            ("INV-011", "DP-004", "LOT-2025-0011", 50, "SITE-301", StorageCondition.AMBIENT, 540),
            # Rescue medication
            ("INV-012", "DP-005", "LOT-2025-0012", 40, "SITE-101", StorageCondition.AMBIENT, 540),
            ("INV-013", "DP-005", "LOT-2025-0013", 30, "SITE-201", StorageCondition.AMBIENT, 540),
            ("INV-014", "DP-005", "LOT-2025-0014", 25, "SITE-301", StorageCondition.AMBIENT, 540),
            # Low / expiring items
            ("INV-015", "DP-001", "LOT-2025-0015", 2, "SITE-104", StorageCondition.REFRIGERATED_2_8, 30),
            ("INV-016", "DP-002", "LOT-2025-0016", 0, "SITE-103", StorageCondition.REFRIGERATED_2_8, 60),
        ]
        for inv_id, dp_id, lot, qty, site, storage, expiry_days in inventory_data:
            status = SupplyStatus.IN_STOCK
            if qty == 0:
                status = SupplyStatus.OUT_OF_STOCK
            elif qty <= 5:
                status = SupplyStatus.LOW_STOCK

            self._inventory[inv_id] = InventoryItem(
                id=inv_id,
                drug_product_id=dp_id,
                lot_number=lot,
                quantity=qty,
                site_id=site,
                storage_condition=storage,
                expiry_date=now + timedelta(days=expiry_days),
                status=status,
                received_date=now - timedelta(days=90),
            )

        # --- Shipments ---
        shipments_data = [
            ("SHP-001", "DEPOT-CENTRAL", "SITE-101", "DP-001", "LOT-2025-0001", 50, ShipmentStatus.DELIVERED, -30, -28),
            ("SHP-002", "DEPOT-CENTRAL", "SITE-102", "DP-001", "LOT-2025-0002", 35, ShipmentStatus.DELIVERED, -25, -23),
            ("SHP-003", "DEPOT-CENTRAL", "SITE-201", "DP-002", "LOT-2025-0004", 65, ShipmentStatus.DELIVERED, -20, -18),
            ("SHP-004", "DEPOT-CENTRAL", "SITE-301", "DP-003", "LOT-2025-0007", 25, ShipmentStatus.DELIVERED, -15, -13),
            ("SHP-005", "DEPOT-CENTRAL", "SITE-103", "DP-001", "LOT-2025-0017", 20, ShipmentStatus.IN_TRANSIT, -2, None),
            ("SHP-006", "DEPOT-CENTRAL", "SITE-104", "DP-002", "LOT-2025-0018", 30, ShipmentStatus.IN_TRANSIT, -1, None),
            ("SHP-007", "SITE-102", "DEPOT-CENTRAL", "DP-001", "LOT-2025-0019", 10, ShipmentStatus.RETURNED, -10, -8),
            ("SHP-008", "DEPOT-CENTRAL", "SITE-302", "DP-003", "LOT-2025-0020", 15, ShipmentStatus.PENDING, None, None),
        ]
        for shp_id, frm, to, dp_id, lot, qty, status, ship_days, deliv_days in shipments_data:
            temp_log = []
            if status in (ShipmentStatus.IN_TRANSIT, ShipmentStatus.DELIVERED):
                # Generate temperature readings
                base_time = now + timedelta(days=ship_days) if ship_days else now
                for i in range(5):
                    temp_log.append(
                        TemperatureReading(
                            timestamp=base_time + timedelta(hours=i * 4),
                            temperature_celsius=4.0 + (i % 3) * 0.5,
                            location=f"Transit checkpoint {i + 1}",
                            sensor_id=f"SENSOR-{shp_id}-{i + 1:02d}",
                        )
                    )

            self._shipments[shp_id] = Shipment(
                id=shp_id,
                from_site=frm,
                to_site=to,
                drug_product_id=dp_id,
                lot_number=lot,
                quantity=qty,
                status=status,
                shipped_date=now + timedelta(days=ship_days) if ship_days else None,
                delivered_date=now + timedelta(days=deliv_days) if deliv_days else None,
                tracking_number=f"TRK-{shp_id[-3:]}-{uuid4().hex[:6].upper()}" if ship_days else None,
                temperature_log=temp_log,
            )

        # --- Temperature Excursions ---
        self._excursions["EXC-001"] = TemperatureExcursion(
            id="EXC-001",
            shipment_id="SHP-005",
            inventory_id=None,
            start_time=now - timedelta(hours=18),
            end_time=now - timedelta(hours=16),
            min_temp=2.0,
            max_temp=10.5,
            severity=TemperatureExcursionSeverity.MINOR,
            disposition=ExcursionDisposition.USE,
        )
        self._excursions["EXC-002"] = TemperatureExcursion(
            id="EXC-002",
            shipment_id=None,
            inventory_id="INV-006",
            start_time=now - timedelta(days=5),
            end_time=now - timedelta(days=5) + timedelta(hours=4),
            min_temp=-2.0,
            max_temp=15.0,
            severity=TemperatureExcursionSeverity.MAJOR,
            disposition=ExcursionDisposition.QUARANTINE,
        )
        self._excursions["EXC-003"] = TemperatureExcursion(
            id="EXC-003",
            shipment_id="SHP-007",
            inventory_id=None,
            start_time=now - timedelta(days=10),
            end_time=now - timedelta(days=10) + timedelta(hours=8),
            min_temp=25.0,
            max_temp=35.0,
            severity=TemperatureExcursionSeverity.CRITICAL,
            disposition=ExcursionDisposition.DESTROY,
        )

        # --- Kit Assignments ---
        kit_data = [
            ("KIT-001", KitType.SCREENING, "PAT-DME-001", "SITE-101", "K-SCR-001", -60, None),
            ("KIT-002", KitType.SCREENING, "PAT-DME-003", "SITE-101", "K-SCR-002", -55, -50),
            ("KIT-003", KitType.RANDOMIZATION, "PAT-DME-003", "SITE-101", "K-RND-001", -50, None),
            ("KIT-004", KitType.TREATMENT, "PAT-DME-003", "SITE-101", "K-TRT-001", -48, None),
            ("KIT-005", KitType.SCREENING, "PAT-AD-001", "SITE-201", "K-SCR-003", -45, -40),
            ("KIT-006", KitType.RANDOMIZATION, "PAT-AD-001", "SITE-201", "K-RND-002", -40, None),
            ("KIT-007", KitType.TREATMENT, "PAT-AD-001", "SITE-201", "K-TRT-002", -38, None),
            ("KIT-008", KitType.SCREENING, "PAT-ONC-001", "SITE-301", "K-SCR-004", -35, -30),
            ("KIT-009", KitType.RANDOMIZATION, "PAT-ONC-001", "SITE-301", "K-RND-003", -30, None),
            ("KIT-010", KitType.TREATMENT, "PAT-ONC-001", "SITE-301", "K-TRT-003", -28, None),
            ("KIT-011", KitType.SCREENING, "PAT-DME-007", "SITE-102", "K-SCR-005", -25, -20),
            ("KIT-012", KitType.TREATMENT, "PAT-DME-007", "SITE-102", "K-TRT-004", -18, None),
            ("KIT-013", KitType.RESCUE, "PAT-AD-007", "SITE-202", "K-RSC-001", -15, -10),
            ("KIT-014", KitType.SCREENING, "PAT-AD-010", "SITE-202", "K-SCR-006", -12, -8),
            ("KIT-015", KitType.TREATMENT, "PAT-AD-010", "SITE-202", "K-TRT-005", -8, None),
            ("KIT-016", KitType.EXTENSION, "PAT-DME-003", "SITE-101", "K-EXT-001", -5, None),
            ("KIT-017", KitType.SCREENING, "PAT-ONC-005", "SITE-302", "K-SCR-007", -4, None),
            ("KIT-018", KitType.TREATMENT, "PAT-ONC-005", "SITE-302", "K-TRT-006", -2, None),
            ("KIT-019", KitType.RESCUE, "PAT-DME-012", "SITE-101", "K-RSC-002", -1, None),
            ("KIT-020", KitType.SCREENING, "PAT-AD-015", "SITE-104", "K-SCR-008", 0, None),
        ]
        for kit_id, kit_type, pat_id, site_id, kit_num, assign_days, return_days in kit_data:
            self._kit_assignments[kit_id] = KitAssignment(
                id=kit_id,
                kit_type=kit_type,
                patient_id=pat_id,
                site_id=site_id,
                kit_number=kit_num,
                assigned_date=now + timedelta(days=assign_days),
                returned_date=now + timedelta(days=return_days) if return_days is not None else None,
            )

        # --- Consumption history (simulated 6 months) ---
        consumption_data = {
            "SITE-101": {"DP-001": [8, 10, 9, 7, 11, 8], "DP-004": [12, 14, 11, 13, 10, 15]},
            "SITE-102": {"DP-001": [6, 7, 5, 8, 6, 7]},
            "SITE-103": {"DP-001": [3, 4, 2, 5, 3, 4]},
            "SITE-201": {"DP-002": [10, 12, 11, 9, 13, 10], "DP-004": [15, 14, 16, 13, 17, 14]},
            "SITE-202": {"DP-002": [5, 6, 4, 7, 5, 6]},
            "SITE-301": {"DP-003": [4, 5, 3, 6, 4, 5], "DP-004": [8, 9, 7, 10, 8, 9]},
            "SITE-302": {"DP-003": [3, 3, 2, 4, 3, 3]},
        }
        for site_id, products in consumption_data.items():
            for dp_id, monthly_values in products.items():
                self._consumption_history[site_id][dp_id] = monthly_values

        logger.info(
            "Supply chain service initialised with %d drug products, %d inventory items, "
            "%d shipments, %d excursions, %d kit assignments",
            len(self._drug_products),
            len(self._inventory),
            len(self._shipments),
            len(self._excursions),
            len(self._kit_assignments),
        )

    # ------------------------------------------------------------------
    # Drug Product CRUD
    # ------------------------------------------------------------------

    def list_drug_products(self) -> list[DrugProduct]:
        """Return all drug products."""
        with self._lock:
            return list(self._drug_products.values())

    def get_drug_product(self, product_id: str) -> DrugProduct:
        """Get a single drug product by ID."""
        with self._lock:
            if product_id not in self._drug_products:
                raise KeyError(f"Drug product '{product_id}' not found")
            return self._drug_products[product_id]

    def create_drug_product(self, data: DrugProductCreate) -> DrugProduct:
        """Create a new drug product."""
        now = datetime.now(timezone.utc)
        product_id = f"DP-{uuid4().hex[:6].upper()}"

        record = DrugProduct(
            id=product_id,
            name=data.name,
            ndc_code=data.ndc_code,
            manufacturer=data.manufacturer,
            active_ingredient=data.active_ingredient,
            formulation=data.formulation,
            strength=data.strength,
            storage_condition=data.storage_condition,
            shelf_life_months=data.shelf_life_months,
            retest_date=None,
        )
        with self._lock:
            self._drug_products[product_id] = record
        logger.info("Created drug product %s: %s", product_id, data.name)
        return record

    def update_drug_product(self, product_id: str, data: DrugProductUpdate) -> DrugProduct:
        """Update an existing drug product."""
        with self._lock:
            if product_id not in self._drug_products:
                raise KeyError(f"Drug product '{product_id}' not found")
            existing = self._drug_products[product_id]
            updates = data.model_dump(exclude_none=True)
            updated = existing.model_copy(update=updates)
            self._drug_products[product_id] = updated
        logger.info("Updated drug product %s", product_id)
        return updated

    def delete_drug_product(self, product_id: str) -> None:
        """Delete a drug product."""
        with self._lock:
            if product_id not in self._drug_products:
                raise KeyError(f"Drug product '{product_id}' not found")
            del self._drug_products[product_id]
        logger.info("Deleted drug product %s", product_id)

    # ------------------------------------------------------------------
    # Inventory CRUD
    # ------------------------------------------------------------------

    def list_inventory(
        self,
        site_id: str | None = None,
        drug_product_id: str | None = None,
        status: SupplyStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[InventoryItem], int]:
        """List inventory items with optional filters."""
        with self._lock:
            items = list(self._inventory.values())

        if site_id:
            items = [i for i in items if i.site_id == site_id]
        if drug_product_id:
            items = [i for i in items if i.drug_product_id == drug_product_id]
        if status:
            items = [i for i in items if i.status == status]

        total = len(items)
        items = items[offset : offset + limit]
        return items, total

    def get_inventory_item(self, item_id: str) -> InventoryItem:
        """Get a single inventory item."""
        with self._lock:
            if item_id not in self._inventory:
                raise KeyError(f"Inventory item '{item_id}' not found")
            return self._inventory[item_id]

    def create_inventory_item(self, data: InventoryItemCreate) -> InventoryItem:
        """Add a new inventory item."""
        item_id = f"INV-{uuid4().hex[:6].upper()}"
        now = datetime.now(timezone.utc)

        status = SupplyStatus.IN_STOCK
        if data.quantity == 0:
            status = SupplyStatus.OUT_OF_STOCK
        elif data.quantity <= 5:
            status = SupplyStatus.LOW_STOCK

        record = InventoryItem(
            id=item_id,
            drug_product_id=data.drug_product_id,
            lot_number=data.lot_number,
            quantity=data.quantity,
            site_id=data.site_id,
            storage_condition=data.storage_condition,
            expiry_date=data.expiry_date,
            status=status,
            received_date=now,
        )
        with self._lock:
            self._inventory[item_id] = record
        logger.info("Created inventory item %s at site %s", item_id, data.site_id)
        return record

    def update_inventory_item(self, item_id: str, data: InventoryItemUpdate) -> InventoryItem:
        """Update an existing inventory item."""
        with self._lock:
            if item_id not in self._inventory:
                raise KeyError(f"Inventory item '{item_id}' not found")
            existing = self._inventory[item_id]
            updates = data.model_dump(exclude_none=True)
            updated = existing.model_copy(update=updates)
            self._inventory[item_id] = updated
        logger.info("Updated inventory item %s", item_id)
        return updated

    def delete_inventory_item(self, item_id: str) -> None:
        """Delete an inventory item."""
        with self._lock:
            if item_id not in self._inventory:
                raise KeyError(f"Inventory item '{item_id}' not found")
            del self._inventory[item_id]
        logger.info("Deleted inventory item %s", item_id)

    # ------------------------------------------------------------------
    # Shipment CRUD
    # ------------------------------------------------------------------

    def list_shipments(
        self,
        status: ShipmentStatus | None = None,
        drug_product_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Shipment], int]:
        """List shipments with optional filters."""
        with self._lock:
            items = list(self._shipments.values())

        if status:
            items = [s for s in items if s.status == status]
        if drug_product_id:
            items = [s for s in items if s.drug_product_id == drug_product_id]

        total = len(items)
        items = items[offset : offset + limit]
        return items, total

    def get_shipment(self, shipment_id: str) -> Shipment:
        """Get a single shipment."""
        with self._lock:
            if shipment_id not in self._shipments:
                raise KeyError(f"Shipment '{shipment_id}' not found")
            return self._shipments[shipment_id]

    def create_shipment(self, data: ShipmentCreate) -> Shipment:
        """Create a new shipment."""
        now = datetime.now(timezone.utc)
        shipment_id = f"SHP-{uuid4().hex[:6].upper()}"

        record = Shipment(
            id=shipment_id,
            from_site=data.from_site,
            to_site=data.to_site,
            drug_product_id=data.drug_product_id,
            lot_number=data.lot_number,
            quantity=data.quantity,
            status=ShipmentStatus.PENDING,
            shipped_date=now,
            delivered_date=None,
            tracking_number=data.tracking_number,
            temperature_log=[],
        )
        with self._lock:
            self._shipments[shipment_id] = record
        logger.info("Created shipment %s: %s -> %s", shipment_id, data.from_site, data.to_site)
        return record

    def update_shipment(self, shipment_id: str, data: ShipmentUpdate) -> Shipment:
        """Update a shipment."""
        with self._lock:
            if shipment_id not in self._shipments:
                raise KeyError(f"Shipment '{shipment_id}' not found")
            existing = self._shipments[shipment_id]
            updates = data.model_dump(exclude_none=True)
            updated = existing.model_copy(update=updates)
            self._shipments[shipment_id] = updated
        logger.info("Updated shipment %s", shipment_id)
        return updated

    def deliver_shipment(self, shipment_id: str) -> Shipment:
        """Mark a shipment as delivered."""
        now = datetime.now(timezone.utc)
        with self._lock:
            if shipment_id not in self._shipments:
                raise KeyError(f"Shipment '{shipment_id}' not found")
            existing = self._shipments[shipment_id]
            if existing.status not in (ShipmentStatus.PENDING, ShipmentStatus.IN_TRANSIT):
                raise ValueError(
                    f"Cannot deliver shipment in status '{existing.status.value}'. "
                    f"Must be 'pending' or 'in_transit'."
                )
            updated = existing.model_copy(
                update={"status": ShipmentStatus.DELIVERED, "delivered_date": now}
            )
            self._shipments[shipment_id] = updated
        logger.info("Delivered shipment %s", shipment_id)
        return updated

    def delete_shipment(self, shipment_id: str) -> None:
        """Delete a shipment."""
        with self._lock:
            if shipment_id not in self._shipments:
                raise KeyError(f"Shipment '{shipment_id}' not found")
            del self._shipments[shipment_id]
        logger.info("Deleted shipment %s", shipment_id)

    # ------------------------------------------------------------------
    # Temperature Excursion Management
    # ------------------------------------------------------------------

    def report_temperature_excursion(
        self, shipment_id: str, data: TemperatureExcursionReport
    ) -> TemperatureExcursion:
        """Report a temperature excursion for a shipment."""
        with self._lock:
            if shipment_id not in self._shipments:
                raise KeyError(f"Shipment '{shipment_id}' not found")

        exc_id = f"EXC-{uuid4().hex[:6].upper()}"
        record = TemperatureExcursion(
            id=exc_id,
            shipment_id=shipment_id,
            inventory_id=None,
            start_time=data.start_time,
            end_time=data.end_time,
            min_temp=data.min_temp,
            max_temp=data.max_temp,
            severity=data.severity,
            disposition=data.disposition,
        )
        with self._lock:
            self._excursions[exc_id] = record
        logger.info("Reported temperature excursion %s for shipment %s", exc_id, shipment_id)
        return record

    def list_temperature_excursions(
        self,
        severity: TemperatureExcursionSeverity | None = None,
        days: int | None = None,
    ) -> list[TemperatureExcursion]:
        """List temperature excursions with optional filters."""
        now = datetime.now(timezone.utc)
        with self._lock:
            items = list(self._excursions.values())

        if severity:
            items = [e for e in items if e.severity == severity]
        if days:
            cutoff = now - timedelta(days=days)
            items = [e for e in items if e.start_time >= cutoff]

        return items

    def get_temperature_excursion(self, excursion_id: str) -> TemperatureExcursion:
        """Get a single temperature excursion."""
        with self._lock:
            if excursion_id not in self._excursions:
                raise KeyError(f"Temperature excursion '{excursion_id}' not found")
            return self._excursions[excursion_id]

    # ------------------------------------------------------------------
    # Kit Assignment Management
    # ------------------------------------------------------------------

    def assign_kit(self, data: KitAssignRequest) -> KitAssignment:
        """Assign a kit to a patient."""
        now = datetime.now(timezone.utc)
        kit_id = f"KIT-{uuid4().hex[:6].upper()}"

        record = KitAssignment(
            id=kit_id,
            kit_type=data.kit_type,
            patient_id=data.patient_id,
            site_id=data.site_id,
            kit_number=data.kit_number,
            assigned_date=now,
            returned_date=None,
        )
        with self._lock:
            self._kit_assignments[kit_id] = record
        logger.info("Assigned kit %s (%s) to patient %s", kit_id, data.kit_type.value, data.patient_id)
        return record

    def return_kit(self, kit_id: str) -> KitAssignment:
        """Record kit return."""
        now = datetime.now(timezone.utc)
        with self._lock:
            if kit_id not in self._kit_assignments:
                raise KeyError(f"Kit assignment '{kit_id}' not found")
            existing = self._kit_assignments[kit_id]
            if existing.returned_date is not None:
                raise ValueError(f"Kit '{kit_id}' has already been returned")
            updated = existing.model_copy(update={"returned_date": now})
            self._kit_assignments[kit_id] = updated
        logger.info("Returned kit %s", kit_id)
        return updated

    def list_kit_assignments(
        self,
        site_id: str | None = None,
        kit_type: KitType | None = None,
        patient_id: str | None = None,
    ) -> list[KitAssignment]:
        """List kit assignments with optional filters."""
        with self._lock:
            items = list(self._kit_assignments.values())

        if site_id:
            items = [k for k in items if k.site_id == site_id]
        if kit_type:
            items = [k for k in items if k.kit_type == kit_type]
        if patient_id:
            items = [k for k in items if k.patient_id == patient_id]

        return items

    def get_kit_assignment(self, kit_id: str) -> KitAssignment:
        """Get a single kit assignment."""
        with self._lock:
            if kit_id not in self._kit_assignments:
                raise KeyError(f"Kit assignment '{kit_id}' not found")
            return self._kit_assignments[kit_id]

    def get_kit_reconciliation(self, site_id: str | None = None) -> KitReconciliation:
        """Get kit reconciliation report."""
        with self._lock:
            items = list(self._kit_assignments.values())

        if site_id:
            items = [k for k in items if k.site_id == site_id]

        total_assigned = len(items)
        total_returned = sum(1 for k in items if k.returned_date is not None)
        outstanding = total_assigned - total_returned

        by_kit_type: dict[str, dict[str, int]] = {}
        for k in items:
            kt = k.kit_type.value
            if kt not in by_kit_type:
                by_kit_type[kt] = {"assigned": 0, "returned": 0, "outstanding": 0}
            by_kit_type[kt]["assigned"] += 1
            if k.returned_date is not None:
                by_kit_type[kt]["returned"] += 1
            else:
                by_kit_type[kt]["outstanding"] += 1

        by_site: dict[str, dict[str, int]] = {}
        for k in items:
            sid = k.site_id
            if sid not in by_site:
                by_site[sid] = {"assigned": 0, "returned": 0, "outstanding": 0}
            by_site[sid]["assigned"] += 1
            if k.returned_date is not None:
                by_site[sid]["returned"] += 1
            else:
                by_site[sid]["outstanding"] += 1

        return KitReconciliation(
            total_assigned=total_assigned,
            total_returned=total_returned,
            outstanding=outstanding,
            by_kit_type=by_kit_type,
            by_site=by_site,
        )

    # ------------------------------------------------------------------
    # Supply Forecasting
    # ------------------------------------------------------------------

    def get_supply_forecast(
        self, site_id: str | None = None, drug_product_id: str | None = None
    ) -> SupplyForecastResponse:
        """Generate supply forecasts based on consumption history."""
        forecasts: list[SupplyForecast] = []
        sites_below_reorder: list[str] = []

        with self._lock:
            inventory_items = list(self._inventory.values())
            consumption = dict(self._consumption_history)

        # Group inventory by (site, drug_product)
        site_product_stock: dict[tuple[str, str], int] = defaultdict(int)
        for item in inventory_items:
            if item.status not in (SupplyStatus.EXPIRED, SupplyStatus.RECALLED):
                site_product_stock[(item.site_id, item.drug_product_id)] += item.quantity

        # Build forecasts
        all_pairs = set(site_product_stock.keys())
        for s_id, dp_id in all_pairs:
            if site_id and s_id != site_id:
                continue
            if drug_product_id and dp_id != drug_product_id:
                continue

            current_stock = site_product_stock[(s_id, dp_id)]

            # Calculate monthly consumption rate from history
            history = consumption.get(s_id, {}).get(dp_id, [])
            if history:
                rate = sum(history) / len(history)
            else:
                rate = 0.0

            # Months of supply
            months = current_stock / rate if rate > 0 else None

            # Reorder point = 2 months of supply
            reorder_point = int(rate * 2) if rate > 0 else 10
            reorder_qty = int(rate * 3) if rate > 0 else 20

            forecast = SupplyForecast(
                site_id=s_id,
                drug_product_id=dp_id,
                current_stock=current_stock,
                monthly_consumption_rate=round(rate, 2),
                months_of_supply=round(months, 2) if months is not None else None,
                reorder_point=reorder_point,
                reorder_quantity=reorder_qty,
            )
            forecasts.append(forecast)

            if months is not None and months < 2.0:
                sites_below_reorder.append(s_id)

        return SupplyForecastResponse(
            items=forecasts,
            total=len(forecasts),
            sites_below_reorder=list(set(sites_below_reorder)),
        )

    # ------------------------------------------------------------------
    # Expiry Management
    # ------------------------------------------------------------------

    def get_expiring_items(self, days: int = 90) -> ExpiringItemsResponse:
        """Return inventory items expiring within N days."""
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=days)

        with self._lock:
            items = [
                item
                for item in self._inventory.values()
                if item.expiry_date <= cutoff
                and item.status not in (SupplyStatus.EXPIRED, SupplyStatus.RECALLED)
            ]

        return ExpiringItemsResponse(
            items=items,
            total=len(items),
            days_window=days,
        )

    # ------------------------------------------------------------------
    # Lot Traceability
    # ------------------------------------------------------------------

    def trace_lot(self, lot_number: str) -> LotTrace:
        """Trace all usage of a specific lot number."""
        with self._lock:
            inv_items = [
                item for item in self._inventory.values()
                if item.lot_number == lot_number
            ]
            shipments = [
                shp for shp in self._shipments.values()
                if shp.lot_number == lot_number
            ]
            excursions_for_lot: list[TemperatureExcursion] = []
            inv_ids = {i.id for i in inv_items}
            shp_ids = {s.id for s in shipments}
            for exc in self._excursions.values():
                if exc.inventory_id in inv_ids or exc.shipment_id in shp_ids:
                    excursions_for_lot.append(exc)

        if not inv_items and not shipments:
            raise KeyError(f"Lot number '{lot_number}' not found")

        # Determine drug product from inventory items or shipments
        dp_id = ""
        dp_name = ""
        if inv_items:
            dp_id = inv_items[0].drug_product_id
        elif shipments:
            dp_id = shipments[0].drug_product_id

        with self._lock:
            dp = self._drug_products.get(dp_id)
        dp_name = dp.name if dp else "Unknown"

        # Find patients exposed via kit assignments at sites that had this lot
        sites_with_lot = {i.site_id for i in inv_items}
        with self._lock:
            patients = list({
                k.patient_id
                for k in self._kit_assignments.values()
                if k.site_id in sites_with_lot
            })

        return LotTrace(
            lot_number=lot_number,
            drug_product_id=dp_id,
            drug_product_name=dp_name,
            inventory_items=inv_items,
            shipments=shipments,
            patients_exposed=patients,
            excursions=excursions_for_lot,
        )

    # ------------------------------------------------------------------
    # Temperature Monitoring
    # ------------------------------------------------------------------

    def check_temperature_compliance(
        self, shipment_id: str
    ) -> list[TemperatureReading]:
        """Check temperature readings for a shipment and return out-of-range readings."""
        with self._lock:
            if shipment_id not in self._shipments:
                raise KeyError(f"Shipment '{shipment_id}' not found")
            shipment = self._shipments[shipment_id]

        dp = self.get_drug_product(shipment.drug_product_id)
        temp_range = STORAGE_TEMP_RANGES.get(dp.storage_condition, (2.0, 8.0))

        violations = [
            reading
            for reading in shipment.temperature_log
            if reading.temperature_celsius < temp_range[0]
            or reading.temperature_celsius > temp_range[1]
        ]
        return violations

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> SupplyMetrics:
        """Calculate aggregated supply chain metrics."""
        now = datetime.now(timezone.utc)
        thirty_days_ago = now - timedelta(days=30)

        with self._lock:
            total_products = len(self._drug_products)
            total_items = len(self._inventory)
            sites = set(i.site_id for i in self._inventory.values())
            total_sites = len(sites)

            active_shipments = sum(
                1
                for s in self._shipments.values()
                if s.status == ShipmentStatus.IN_TRANSIT
            )

            excursions_30d = sum(
                1
                for e in self._excursions.values()
                if e.start_time >= thirty_days_ago
            )

            kits_assigned = sum(
                1
                for k in self._kit_assignments.values()
                if k.returned_date is None
            )

        # Calculate avg months of supply from forecast
        forecast = self.get_supply_forecast()
        months_values = [
            f.months_of_supply
            for f in forecast.items
            if f.months_of_supply is not None
        ]
        avg_months = (
            round(sum(months_values) / len(months_values), 2)
            if months_values
            else None
        )

        sites_below = len(forecast.sites_below_reorder)

        return SupplyMetrics(
            total_drug_products=total_products,
            total_sites=total_sites,
            total_inventory_items=total_items,
            active_shipments=active_shipments,
            temperature_excursions_30d=excursions_30d,
            kits_assigned=kits_assigned,
            avg_months_of_supply=avg_months,
            sites_below_reorder_point=sites_below,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: SupplyChainService | None = None
_instance_lock = threading.Lock()


def get_supply_chain_service() -> SupplyChainService:
    """Return the singleton SupplyChainService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = SupplyChainService()
    return _instance


def reset_supply_chain_service() -> SupplyChainService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = SupplyChainService()
    return _instance
