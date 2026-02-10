"""Clinical Supply Returns Management Service (SUPPLY-RET).

Manages investigational product returns, drug accountability reconciliation,
destruction tracking, temperature excursion documentation, quarantine management,
and returns metrics.

Usage:
    from app.services.clinical_supply_returns_service import (
        get_clinical_supply_returns_service,
    )

    svc = get_clinical_supply_returns_service()
    returns = svc.list_returns()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.clinical_supply_returns import (
    DestructionMethod,
    DestructionRecord,
    DestructionRecordCreate,
    DrugAccountability,
    DrugAccountabilityCreate,
    DrugAccountabilityUpdate,
    ExcursionSeverity,
    QuarantineReason,
    QuarantineRecord,
    QuarantineRecordCreate,
    QuarantineRecordUpdate,
    ReconciliationResult,
    ReturnReason,
    ReturnStatus,
    SupplyReturn,
    SupplyReturnCreate,
    SupplyReturnUpdate,
    SupplyReturnsMetrics,
    TemperatureExcursion,
    TemperatureExcursionCreate,
    TemperatureExcursionUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class ClinicalSupplyReturnsService:
    """In-memory Clinical Supply Returns Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._returns: dict[str, SupplyReturn] = {}
        self._destructions: dict[str, DestructionRecord] = {}
        self._excursions: dict[str, TemperatureExcursion] = {}
        self._quarantines: dict[str, QuarantineRecord] = {}
        self._accountabilities: dict[str, DrugAccountability] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic supply returns data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Supply Returns ---
        returns_data = [
            # EYLEA trial returns
            {"id": "RET-001", "trial_id": EYLEA_TRIAL, "site_id": "SITE-101", "product_name": "EYLEA HD 8mg", "lot_number": "EYL-2024-001", "quantity_returned": 24, "unit": "vials", "return_reason": ReturnReason.STUDY_COMPLETION, "status": ReturnStatus.DESTROYED, "initiated_date": now - timedelta(days=90), "initiated_by": "Sarah Johnson", "shipped_date": now - timedelta(days=88), "received_date": now - timedelta(days=85), "received_by": "Michael Chen", "tracking_number": "1Z999AA10123456784", "condition_on_receipt": "Good condition, seals intact", "created_at": now - timedelta(days=90)},
            {"id": "RET-002", "trial_id": EYLEA_TRIAL, "site_id": "SITE-102", "product_name": "EYLEA HD 8mg", "lot_number": "EYL-2024-002", "quantity_returned": 12, "unit": "vials", "return_reason": ReturnReason.EXPIRED, "status": ReturnStatus.APPROVED_FOR_DESTRUCTION, "initiated_date": now - timedelta(days=60), "initiated_by": "James Wilson", "shipped_date": now - timedelta(days=58), "received_date": now - timedelta(days=55), "received_by": "Lisa Park", "tracking_number": "1Z999AA10123456785", "condition_on_receipt": "Expired per label dating", "created_at": now - timedelta(days=60)},
            {"id": "RET-003", "trial_id": EYLEA_TRIAL, "site_id": "SITE-103", "product_name": "EYLEA HD 8mg", "lot_number": "EYL-2024-003", "quantity_returned": 6, "unit": "vials", "return_reason": ReturnReason.TEMPERATURE_EXCURSION, "status": ReturnStatus.QUARANTINED, "initiated_date": now - timedelta(days=30), "initiated_by": "Emily Davis", "shipped_date": now - timedelta(days=28), "received_date": now - timedelta(days=25), "received_by": "Robert Kim", "tracking_number": "1Z999AA10123456786", "condition_on_receipt": "Temperature excursion noted during transit", "created_at": now - timedelta(days=30)},
            {"id": "RET-004", "trial_id": EYLEA_TRIAL, "site_id": "SITE-101", "product_name": "EYLEA HD 8mg", "lot_number": "EYL-2024-004", "quantity_returned": 18, "unit": "vials", "return_reason": ReturnReason.PATIENT_WITHDRAWAL, "status": ReturnStatus.RECEIVED, "initiated_date": now - timedelta(days=15), "initiated_by": "Sarah Johnson", "shipped_date": now - timedelta(days=13), "received_date": now - timedelta(days=10), "received_by": "Michael Chen", "tracking_number": "1Z999AA10123456787", "condition_on_receipt": "Good condition", "created_at": now - timedelta(days=15)},
            # Dupixent trial returns
            {"id": "RET-005", "trial_id": DUPIXENT_TRIAL, "site_id": "SITE-104", "product_name": "Dupixent 300mg", "lot_number": "DUP-2024-001", "quantity_returned": 48, "unit": "syringes", "return_reason": ReturnReason.STUDY_COMPLETION, "status": ReturnStatus.DESTROYED, "initiated_date": now - timedelta(days=100), "initiated_by": "Karen Martinez", "shipped_date": now - timedelta(days=98), "received_date": now - timedelta(days=95), "received_by": "David Lee", "tracking_number": "1Z999BB20123456784", "condition_on_receipt": "All units accounted for", "created_at": now - timedelta(days=100)},
            {"id": "RET-006", "trial_id": DUPIXENT_TRIAL, "site_id": "SITE-105", "product_name": "Dupixent 300mg", "lot_number": "DUP-2024-002", "quantity_returned": 20, "unit": "syringes", "return_reason": ReturnReason.SITE_CLOSURE, "status": ReturnStatus.INSPECTED, "initiated_date": now - timedelta(days=45), "initiated_by": "Thomas Brown", "shipped_date": now - timedelta(days=43), "received_date": now - timedelta(days=40), "received_by": "Nancy White", "tracking_number": "1Z999BB20123456785", "condition_on_receipt": "Minor packaging damage noted", "created_at": now - timedelta(days=45)},
            {"id": "RET-007", "trial_id": DUPIXENT_TRIAL, "site_id": "SITE-106", "product_name": "Dupixent 300mg", "lot_number": "DUP-2024-003", "quantity_returned": 8, "unit": "syringes", "return_reason": ReturnReason.DAMAGED, "status": ReturnStatus.DISCREPANCY, "initiated_date": now - timedelta(days=20), "initiated_by": "Patricia Green", "shipped_date": now - timedelta(days=18), "received_date": now - timedelta(days=15), "received_by": "David Lee", "tracking_number": "1Z999BB20123456786", "condition_on_receipt": "2 syringes missing from shipment", "created_at": now - timedelta(days=20)},
            {"id": "RET-008", "trial_id": DUPIXENT_TRIAL, "site_id": "SITE-104", "product_name": "Dupixent 300mg", "lot_number": "DUP-2024-004", "quantity_returned": 30, "unit": "syringes", "return_reason": ReturnReason.EXCESS_INVENTORY, "status": ReturnStatus.SHIPPED, "initiated_date": now - timedelta(days=5), "initiated_by": "Karen Martinez", "shipped_date": now - timedelta(days=3), "received_date": None, "received_by": None, "tracking_number": "1Z999BB20123456787", "condition_on_receipt": None, "created_at": now - timedelta(days=5)},
            # Libtayo trial returns
            {"id": "RET-009", "trial_id": LIBTAYO_TRIAL, "site_id": "SITE-107", "product_name": "Libtayo 350mg", "lot_number": "LIB-2024-001", "quantity_returned": 10, "unit": "vials", "return_reason": ReturnReason.STUDY_COMPLETION, "status": ReturnStatus.DESTROYED, "initiated_date": now - timedelta(days=110), "initiated_by": "William Taylor", "shipped_date": now - timedelta(days=108), "received_date": now - timedelta(days=105), "received_by": "Jennifer Adams", "tracking_number": "1Z999CC30123456784", "condition_on_receipt": "Good condition", "created_at": now - timedelta(days=110)},
            {"id": "RET-010", "trial_id": LIBTAYO_TRIAL, "site_id": "SITE-108", "product_name": "Libtayo 350mg", "lot_number": "LIB-2024-002", "quantity_returned": 15, "unit": "vials", "return_reason": ReturnReason.RECALL, "status": ReturnStatus.APPROVED_FOR_DESTRUCTION, "initiated_date": now - timedelta(days=50), "initiated_by": "Susan Clark", "shipped_date": now - timedelta(days=48), "received_date": now - timedelta(days=45), "received_by": "Jennifer Adams", "tracking_number": "1Z999CC30123456785", "condition_on_receipt": "Product recall lot confirmed", "created_at": now - timedelta(days=50)},
            {"id": "RET-011", "trial_id": LIBTAYO_TRIAL, "site_id": "SITE-107", "product_name": "Libtayo 350mg", "lot_number": "LIB-2024-003", "quantity_returned": 5, "unit": "vials", "return_reason": ReturnReason.PROTOCOL_AMENDMENT, "status": ReturnStatus.PACKAGED, "initiated_date": now - timedelta(days=8), "initiated_by": "William Taylor", "shipped_date": None, "received_date": None, "received_by": None, "tracking_number": None, "condition_on_receipt": None, "created_at": now - timedelta(days=8)},
            {"id": "RET-012", "trial_id": LIBTAYO_TRIAL, "site_id": "SITE-108", "product_name": "Libtayo 350mg", "lot_number": "LIB-2024-004", "quantity_returned": 3, "unit": "vials", "return_reason": ReturnReason.PATIENT_WITHDRAWAL, "status": ReturnStatus.INITIATED, "initiated_date": now - timedelta(days=2), "initiated_by": "Susan Clark", "shipped_date": None, "received_date": None, "received_by": None, "tracking_number": None, "condition_on_receipt": None, "created_at": now - timedelta(days=2)},
        ]

        for r in returns_data:
            self._returns[r["id"]] = SupplyReturn(**r)

        # --- 5 Destruction Records ---
        destructions_data = [
            {"id": "DES-001", "return_id": "RET-001", "trial_id": EYLEA_TRIAL, "product_name": "EYLEA HD 8mg", "lot_number": "EYL-2024-001", "quantity_destroyed": 24, "destruction_method": DestructionMethod.INCINERATION, "destruction_date": now - timedelta(days=70), "destruction_facility": "Stericycle Environmental Solutions", "witnessed_by": "Dr. Patricia Wang", "certificate_number": "CERT-2024-001", "certificate_date": now - timedelta(days=68), "approved_by": "Dr. Robert Kim"},
            {"id": "DES-002", "return_id": "RET-005", "trial_id": DUPIXENT_TRIAL, "product_name": "Dupixent 300mg", "lot_number": "DUP-2024-001", "quantity_destroyed": 48, "destruction_method": DestructionMethod.INCINERATION, "destruction_date": now - timedelta(days=80), "destruction_facility": "Stericycle Environmental Solutions", "witnessed_by": "Dr. Nancy White", "certificate_number": "CERT-2024-002", "certificate_date": now - timedelta(days=78), "approved_by": "Dr. David Lee"},
            {"id": "DES-003", "return_id": "RET-009", "trial_id": LIBTAYO_TRIAL, "product_name": "Libtayo 350mg", "lot_number": "LIB-2024-001", "quantity_destroyed": 10, "destruction_method": DestructionMethod.CHEMICAL, "destruction_date": now - timedelta(days=90), "destruction_facility": "Clean Harbors Inc.", "witnessed_by": "Dr. Jennifer Adams", "certificate_number": "CERT-2024-003", "certificate_date": now - timedelta(days=88), "approved_by": "Dr. William Taylor"},
            {"id": "DES-004", "return_id": "RET-001", "trial_id": EYLEA_TRIAL, "product_name": "EYLEA HD 8mg", "lot_number": "EYL-2024-005", "quantity_destroyed": 6, "destruction_method": DestructionMethod.RETURN_TO_MANUFACTURER, "destruction_date": now - timedelta(days=40), "destruction_facility": "Regeneron Pharmaceuticals", "witnessed_by": "Dr. Lisa Park", "certificate_number": None, "certificate_date": None, "approved_by": "Dr. Michael Chen"},
            {"id": "DES-005", "return_id": "RET-005", "trial_id": DUPIXENT_TRIAL, "product_name": "Dupixent 300mg", "lot_number": "DUP-2024-005", "quantity_destroyed": 12, "destruction_method": DestructionMethod.AUTOCLAVING, "destruction_date": now - timedelta(days=35), "destruction_facility": "Triumvirate Environmental", "witnessed_by": "Dr. Thomas Brown", "certificate_number": "CERT-2024-005", "certificate_date": now - timedelta(days=33), "approved_by": "Dr. Nancy White"},
        ]

        for d in destructions_data:
            self._destructions[d["id"]] = DestructionRecord(**d)

        # --- 5 Temperature Excursions ---
        excursions_data = [
            {"id": "EXC-001", "trial_id": EYLEA_TRIAL, "site_id": "SITE-103", "return_id": "RET-003", "product_name": "EYLEA HD 8mg", "lot_number": "EYL-2024-003", "excursion_start": now - timedelta(days=29, hours=6), "excursion_end": now - timedelta(days=29, hours=2), "min_temp": 2.0, "max_temp": 12.5, "required_range_min": 2.0, "required_range_max": 8.0, "duration_minutes": 240, "severity": ExcursionSeverity.MODERATE, "product_disposition": "Quarantined pending stability assessment", "reported_by": "Emily Davis", "assessed_by": "Dr. Robert Kim"},
            {"id": "EXC-002", "trial_id": EYLEA_TRIAL, "site_id": "SITE-101", "return_id": None, "product_name": "EYLEA HD 8mg", "lot_number": "EYL-2024-001", "excursion_start": now - timedelta(days=95, hours=3), "excursion_end": now - timedelta(days=95, hours=1), "min_temp": -2.0, "max_temp": 8.0, "required_range_min": 2.0, "required_range_max": 8.0, "duration_minutes": 120, "severity": ExcursionSeverity.MINOR, "product_disposition": "Released - within acceptable range per stability data", "reported_by": "Sarah Johnson", "assessed_by": "Dr. Michael Chen"},
            {"id": "EXC-003", "trial_id": DUPIXENT_TRIAL, "site_id": "SITE-106", "return_id": None, "product_name": "Dupixent 300mg", "lot_number": "DUP-2024-003", "excursion_start": now - timedelta(days=22, hours=8), "excursion_end": now - timedelta(days=22, hours=1), "min_temp": 2.0, "max_temp": 25.0, "required_range_min": 2.0, "required_range_max": 8.0, "duration_minutes": 420, "severity": ExcursionSeverity.CRITICAL, "product_disposition": "Destroyed - exceeded stability limits", "reported_by": "Patricia Green", "assessed_by": "Dr. David Lee"},
            {"id": "EXC-004", "trial_id": LIBTAYO_TRIAL, "site_id": "SITE-107", "return_id": None, "product_name": "Libtayo 350mg", "lot_number": "LIB-2024-002", "excursion_start": now - timedelta(days=55, hours=4), "excursion_end": now - timedelta(days=55, hours=2), "min_temp": 2.0, "max_temp": 10.0, "required_range_min": 2.0, "required_range_max": 8.0, "duration_minutes": 120, "severity": ExcursionSeverity.MINOR, "product_disposition": "Released after QA review", "reported_by": "William Taylor", "assessed_by": "Dr. Jennifer Adams"},
            {"id": "EXC-005", "trial_id": LIBTAYO_TRIAL, "site_id": "SITE-108", "return_id": None, "product_name": "Libtayo 350mg", "lot_number": "LIB-2024-003", "excursion_start": now - timedelta(days=10, hours=6), "excursion_end": None, "min_temp": -5.0, "max_temp": 8.0, "required_range_min": 2.0, "required_range_max": 8.0, "duration_minutes": 360, "severity": ExcursionSeverity.MAJOR, "product_disposition": None, "reported_by": "Susan Clark", "assessed_by": None},
        ]

        for e in excursions_data:
            self._excursions[e["id"]] = TemperatureExcursion(**e)

        # --- 5 Quarantine Records ---
        quarantines_data = [
            {"id": "QUA-001", "trial_id": EYLEA_TRIAL, "site_id": "SITE-103", "product_name": "EYLEA HD 8mg", "lot_number": "EYL-2024-003", "quantity": 6, "reason": QuarantineReason.TEMPERATURE_EXCURSION, "quarantine_date": now - timedelta(days=25), "location": "Building A - Quarantine Room 1", "released": False, "release_date": None, "released_by": None, "disposition": None},
            {"id": "QUA-002", "trial_id": DUPIXENT_TRIAL, "site_id": "SITE-105", "product_name": "Dupixent 300mg", "lot_number": "DUP-2024-002", "quantity": 5, "reason": QuarantineReason.DAMAGED_PACKAGING, "quarantine_date": now - timedelta(days=40), "location": "Building B - Quarantine Area", "released": True, "release_date": now - timedelta(days=35), "released_by": "Dr. Nancy White", "disposition": "Released for destruction"},
            {"id": "QUA-003", "trial_id": DUPIXENT_TRIAL, "site_id": "SITE-106", "product_name": "Dupixent 300mg", "lot_number": "DUP-2024-003", "quantity": 8, "reason": QuarantineReason.ACCOUNTABILITY_DISCREPANCY, "quarantine_date": now - timedelta(days=15), "location": "Building B - Secure Storage", "released": False, "release_date": None, "released_by": None, "disposition": None},
            {"id": "QUA-004", "trial_id": LIBTAYO_TRIAL, "site_id": "SITE-108", "product_name": "Libtayo 350mg", "lot_number": "LIB-2024-002", "quantity": 15, "reason": QuarantineReason.RECALL_HOLD, "quarantine_date": now - timedelta(days=48), "location": "Building C - Quarantine Zone", "released": True, "release_date": now - timedelta(days=44), "released_by": "Dr. Jennifer Adams", "disposition": "Approved for destruction"},
            {"id": "QUA-005", "trial_id": LIBTAYO_TRIAL, "site_id": "SITE-107", "product_name": "Libtayo 350mg", "lot_number": "LIB-2024-003", "quantity": 3, "reason": QuarantineReason.PENDING_INSPECTION, "quarantine_date": now - timedelta(days=8), "location": "Building C - Incoming Area", "released": False, "release_date": None, "released_by": None, "disposition": None},
        ]

        for q in quarantines_data:
            self._quarantines[q["id"]] = QuarantineRecord(**q)

        # --- 6 Drug Accountability Records ---
        accountabilities_data = [
            {"id": "ACC-001", "trial_id": EYLEA_TRIAL, "site_id": "SITE-101", "product_name": "EYLEA HD 8mg", "lot_number": "EYL-2024-001", "quantity_received": 100, "quantity_dispensed": 52, "quantity_returned": 24, "quantity_destroyed_at_site": 0, "quantity_returned_to_sponsor": 24, "quantity_remaining": 0, "discrepancy_quantity": 0, "result": ReconciliationResult.RECONCILED, "reconciled_by": "Dr. Michael Chen", "reconciled_date": now - timedelta(days=65)},
            {"id": "ACC-002", "trial_id": EYLEA_TRIAL, "site_id": "SITE-102", "product_name": "EYLEA HD 8mg", "lot_number": "EYL-2024-002", "quantity_received": 80, "quantity_dispensed": 45, "quantity_returned": 12, "quantity_destroyed_at_site": 0, "quantity_returned_to_sponsor": 12, "quantity_remaining": 11, "discrepancy_quantity": 0, "result": ReconciliationResult.RECONCILED, "reconciled_by": "Dr. Lisa Park", "reconciled_date": now - timedelta(days=50)},
            {"id": "ACC-003", "trial_id": DUPIXENT_TRIAL, "site_id": "SITE-104", "product_name": "Dupixent 300mg", "lot_number": "DUP-2024-001", "quantity_received": 200, "quantity_dispensed": 120, "quantity_returned": 30, "quantity_destroyed_at_site": 2, "quantity_returned_to_sponsor": 48, "quantity_remaining": 0, "discrepancy_quantity": 0, "result": ReconciliationResult.RECONCILED, "reconciled_by": "Dr. David Lee", "reconciled_date": now - timedelta(days=75)},
            {"id": "ACC-004", "trial_id": DUPIXENT_TRIAL, "site_id": "SITE-106", "product_name": "Dupixent 300mg", "lot_number": "DUP-2024-003", "quantity_received": 60, "quantity_dispensed": 35, "quantity_returned": 10, "quantity_destroyed_at_site": 0, "quantity_returned_to_sponsor": 8, "quantity_remaining": 5, "discrepancy_quantity": 2, "result": ReconciliationResult.MINOR_DISCREPANCY, "reconciled_by": "Dr. David Lee", "reconciled_date": now - timedelta(days=12)},
            {"id": "ACC-005", "trial_id": LIBTAYO_TRIAL, "site_id": "SITE-107", "product_name": "Libtayo 350mg", "lot_number": "LIB-2024-001", "quantity_received": 50, "quantity_dispensed": 30, "quantity_returned": 5, "quantity_destroyed_at_site": 0, "quantity_returned_to_sponsor": 10, "quantity_remaining": 0, "discrepancy_quantity": 5, "result": ReconciliationResult.MAJOR_DISCREPANCY, "reconciled_by": "Dr. Jennifer Adams", "reconciled_date": now - timedelta(days=85)},
            {"id": "ACC-006", "trial_id": LIBTAYO_TRIAL, "site_id": "SITE-108", "product_name": "Libtayo 350mg", "lot_number": "LIB-2024-002", "quantity_received": 40, "quantity_dispensed": 20, "quantity_returned": 0, "quantity_destroyed_at_site": 0, "quantity_returned_to_sponsor": 0, "quantity_remaining": 20, "discrepancy_quantity": 0, "result": ReconciliationResult.PENDING, "reconciled_by": None, "reconciled_date": None},
        ]

        for a in accountabilities_data:
            self._accountabilities[a["id"]] = DrugAccountability(**a)

    # ------------------------------------------------------------------
    # Supply Returns CRUD
    # ------------------------------------------------------------------

    def list_returns(
        self,
        *,
        trial_id: str | None = None,
        status: ReturnStatus | None = None,
        return_reason: ReturnReason | None = None,
    ) -> list[SupplyReturn]:
        """List supply returns with optional filters."""
        with self._lock:
            result = list(self._returns.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if status is not None:
            result = [r for r in result if r.status == status]
        if return_reason is not None:
            result = [r for r in result if r.return_reason == return_reason]

        return sorted(result, key=lambda r: r.initiated_date, reverse=True)

    def get_return(self, return_id: str) -> SupplyReturn | None:
        """Get a single return by ID."""
        with self._lock:
            return self._returns.get(return_id)

    def create_return(self, payload: SupplyReturnCreate) -> SupplyReturn:
        """Create a new supply return."""
        now = datetime.now(timezone.utc)
        return_id = f"RET-{uuid4().hex[:8].upper()}"
        supply_return = SupplyReturn(
            id=return_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            product_name=payload.product_name,
            lot_number=payload.lot_number,
            quantity_returned=payload.quantity_returned,
            unit=payload.unit,
            return_reason=payload.return_reason,
            status=ReturnStatus.INITIATED,
            initiated_date=now,
            initiated_by=payload.initiated_by,
            shipped_date=None,
            received_date=None,
            received_by=None,
            tracking_number=None,
            condition_on_receipt=None,
            created_at=now,
        )
        with self._lock:
            self._returns[return_id] = supply_return
        logger.info(
            "Created supply return %s: trial=%s site=%s product=%s",
            return_id, payload.trial_id, payload.site_id, payload.product_name,
        )
        return supply_return

    def update_return(
        self, return_id: str, payload: SupplyReturnUpdate
    ) -> SupplyReturn | None:
        """Update an existing supply return."""
        with self._lock:
            existing = self._returns.get(return_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SupplyReturn(**data)
            self._returns[return_id] = updated
        return updated

    def delete_return(self, return_id: str) -> bool:
        """Delete a supply return. Returns True if deleted."""
        with self._lock:
            if return_id in self._returns:
                del self._returns[return_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Destruction Records CRUD
    # ------------------------------------------------------------------

    def list_destructions(
        self,
        *,
        trial_id: str | None = None,
        destruction_method: DestructionMethod | None = None,
    ) -> list[DestructionRecord]:
        """List destruction records with optional filters."""
        with self._lock:
            result = list(self._destructions.values())

        if trial_id is not None:
            result = [d for d in result if d.trial_id == trial_id]
        if destruction_method is not None:
            result = [d for d in result if d.destruction_method == destruction_method]

        return sorted(result, key=lambda d: d.destruction_date, reverse=True)

    def get_destruction(self, destruction_id: str) -> DestructionRecord | None:
        """Get a single destruction record by ID."""
        with self._lock:
            return self._destructions.get(destruction_id)

    def create_destruction(self, payload: DestructionRecordCreate) -> DestructionRecord:
        """Create a new destruction record."""
        now = datetime.now(timezone.utc)
        destruction_id = f"DES-{uuid4().hex[:8].upper()}"
        record = DestructionRecord(
            id=destruction_id,
            return_id=payload.return_id,
            trial_id=payload.trial_id,
            product_name=payload.product_name,
            lot_number=payload.lot_number,
            quantity_destroyed=payload.quantity_destroyed,
            destruction_method=payload.destruction_method,
            destruction_date=now,
            destruction_facility=payload.destruction_facility,
            witnessed_by=payload.witnessed_by,
            certificate_number=payload.certificate_number,
            certificate_date=None,
            approved_by=payload.approved_by,
        )
        with self._lock:
            self._destructions[destruction_id] = record
        logger.info(
            "Created destruction record %s: return=%s method=%s",
            destruction_id, payload.return_id, payload.destruction_method.value,
        )
        return record

    def delete_destruction(self, destruction_id: str) -> bool:
        """Delete a destruction record. Returns True if deleted."""
        with self._lock:
            if destruction_id in self._destructions:
                del self._destructions[destruction_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Temperature Excursions CRUD
    # ------------------------------------------------------------------

    def list_excursions(
        self,
        *,
        trial_id: str | None = None,
        severity: ExcursionSeverity | None = None,
    ) -> list[TemperatureExcursion]:
        """List temperature excursions with optional filters."""
        with self._lock:
            result = list(self._excursions.values())

        if trial_id is not None:
            result = [e for e in result if e.trial_id == trial_id]
        if severity is not None:
            result = [e for e in result if e.severity == severity]

        return sorted(result, key=lambda e: e.excursion_start, reverse=True)

    def get_excursion(self, excursion_id: str) -> TemperatureExcursion | None:
        """Get a single temperature excursion by ID."""
        with self._lock:
            return self._excursions.get(excursion_id)

    def create_excursion(self, payload: TemperatureExcursionCreate) -> TemperatureExcursion:
        """Create a new temperature excursion."""
        excursion_id = f"EXC-{uuid4().hex[:8].upper()}"
        excursion = TemperatureExcursion(
            id=excursion_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            return_id=payload.return_id,
            product_name=payload.product_name,
            lot_number=payload.lot_number,
            excursion_start=payload.excursion_start,
            excursion_end=payload.excursion_end,
            min_temp=payload.min_temp,
            max_temp=payload.max_temp,
            required_range_min=payload.required_range_min,
            required_range_max=payload.required_range_max,
            duration_minutes=payload.duration_minutes,
            severity=payload.severity,
            product_disposition=None,
            reported_by=payload.reported_by,
            assessed_by=None,
        )
        with self._lock:
            self._excursions[excursion_id] = excursion
        logger.info(
            "Created temperature excursion %s: trial=%s severity=%s",
            excursion_id, payload.trial_id, payload.severity.value,
        )
        return excursion

    def update_excursion(
        self, excursion_id: str, payload: TemperatureExcursionUpdate
    ) -> TemperatureExcursion | None:
        """Update a temperature excursion."""
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
        """Delete a temperature excursion. Returns True if deleted."""
        with self._lock:
            if excursion_id in self._excursions:
                del self._excursions[excursion_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Quarantine Records CRUD
    # ------------------------------------------------------------------

    def list_quarantines(
        self,
        *,
        trial_id: str | None = None,
        released: bool | None = None,
    ) -> list[QuarantineRecord]:
        """List quarantine records with optional filters."""
        with self._lock:
            result = list(self._quarantines.values())

        if trial_id is not None:
            result = [q for q in result if q.trial_id == trial_id]
        if released is not None:
            result = [q for q in result if q.released == released]

        return sorted(result, key=lambda q: q.quarantine_date, reverse=True)

    def get_quarantine(self, quarantine_id: str) -> QuarantineRecord | None:
        """Get a single quarantine record by ID."""
        with self._lock:
            return self._quarantines.get(quarantine_id)

    def create_quarantine(self, payload: QuarantineRecordCreate) -> QuarantineRecord:
        """Create a new quarantine record."""
        now = datetime.now(timezone.utc)
        quarantine_id = f"QUA-{uuid4().hex[:8].upper()}"
        record = QuarantineRecord(
            id=quarantine_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            product_name=payload.product_name,
            lot_number=payload.lot_number,
            quantity=payload.quantity,
            reason=payload.reason,
            quarantine_date=now,
            location=payload.location,
            released=False,
            release_date=None,
            released_by=None,
            disposition=None,
        )
        with self._lock:
            self._quarantines[quarantine_id] = record
        logger.info(
            "Created quarantine record %s: trial=%s reason=%s",
            quarantine_id, payload.trial_id, payload.reason.value,
        )
        return record

    def update_quarantine(
        self, quarantine_id: str, payload: QuarantineRecordUpdate
    ) -> QuarantineRecord | None:
        """Update a quarantine record."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._quarantines.get(quarantine_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set release_date when released is set to True
            if updates.get("released") is True and not existing.released:
                updates["release_date"] = now

            data.update(updates)
            updated = QuarantineRecord(**data)
            self._quarantines[quarantine_id] = updated
        return updated

    def delete_quarantine(self, quarantine_id: str) -> bool:
        """Delete a quarantine record. Returns True if deleted."""
        with self._lock:
            if quarantine_id in self._quarantines:
                del self._quarantines[quarantine_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Drug Accountability CRUD
    # ------------------------------------------------------------------

    def list_accountabilities(
        self,
        *,
        trial_id: str | None = None,
        result: ReconciliationResult | None = None,
    ) -> list[DrugAccountability]:
        """List drug accountability records with optional filters."""
        with self._lock:
            items = list(self._accountabilities.values())

        if trial_id is not None:
            items = [a for a in items if a.trial_id == trial_id]
        if result is not None:
            items = [a for a in items if a.result == result]

        return sorted(items, key=lambda a: a.id)

    def get_accountability(self, accountability_id: str) -> DrugAccountability | None:
        """Get a single drug accountability record by ID."""
        with self._lock:
            return self._accountabilities.get(accountability_id)

    def create_accountability(self, payload: DrugAccountabilityCreate) -> DrugAccountability:
        """Create a new drug accountability record."""
        accountability_id = f"ACC-{uuid4().hex[:8].upper()}"
        record = DrugAccountability(
            id=accountability_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            product_name=payload.product_name,
            lot_number=payload.lot_number,
            quantity_received=payload.quantity_received,
            quantity_dispensed=payload.quantity_dispensed,
            quantity_returned=payload.quantity_returned,
            quantity_destroyed_at_site=payload.quantity_destroyed_at_site,
            quantity_returned_to_sponsor=payload.quantity_returned_to_sponsor,
            quantity_remaining=payload.quantity_remaining,
            discrepancy_quantity=0,
            result=ReconciliationResult.PENDING,
            reconciled_by=None,
            reconciled_date=None,
        )
        with self._lock:
            self._accountabilities[accountability_id] = record
        logger.info(
            "Created drug accountability record %s: trial=%s site=%s",
            accountability_id, payload.trial_id, payload.site_id,
        )
        return record

    def update_accountability(
        self, accountability_id: str, payload: DrugAccountabilityUpdate
    ) -> DrugAccountability | None:
        """Update a drug accountability record."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._accountabilities.get(accountability_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set reconciled_date when reconciled_by is set
            if "reconciled_by" in updates and updates["reconciled_by"] is not None:
                if existing.reconciled_date is None:
                    updates["reconciled_date"] = now

            data.update(updates)
            updated = DrugAccountability(**data)
            self._accountabilities[accountability_id] = updated
        return updated

    def delete_accountability(self, accountability_id: str) -> bool:
        """Delete a drug accountability record. Returns True if deleted."""
        with self._lock:
            if accountability_id in self._accountabilities:
                del self._accountabilities[accountability_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> SupplyReturnsMetrics:
        """Compute aggregated supply returns metrics."""
        with self._lock:
            returns = list(self._returns.values())
            destructions = list(self._destructions.values())
            excursions = list(self._excursions.values())
            quarantines = list(self._quarantines.values())
            accountabilities = list(self._accountabilities.values())

        if trial_id is not None:
            returns = [r for r in returns if r.trial_id == trial_id]
            destructions = [d for d in destructions if d.trial_id == trial_id]
            excursions = [e for e in excursions if e.trial_id == trial_id]
            quarantines = [q for q in quarantines if q.trial_id == trial_id]
            accountabilities = [a for a in accountabilities if a.trial_id == trial_id]

        # Returns by status
        returns_by_status: dict[str, int] = {}
        for r in returns:
            key = r.status.value
            returns_by_status[key] = returns_by_status.get(key, 0) + 1

        # Returns by reason
        returns_by_reason: dict[str, int] = {}
        for r in returns:
            key = r.return_reason.value
            returns_by_reason[key] = returns_by_reason.get(key, 0) + 1

        # Total units returned
        total_units_returned = sum(r.quantity_returned for r in returns)

        # Total units destroyed
        total_units_destroyed = sum(d.quantity_destroyed for d in destructions)

        # Destructions by method
        destructions_by_method: dict[str, int] = {}
        for d in destructions:
            key = d.destruction_method.value
            destructions_by_method[key] = destructions_by_method.get(key, 0) + 1

        # Excursions by severity
        excursions_by_severity: dict[str, int] = {}
        for e in excursions:
            key = e.severity.value
            excursions_by_severity[key] = excursions_by_severity.get(key, 0) + 1

        # Quarantine counts
        currently_quarantined = sum(1 for q in quarantines if not q.released)

        # Accountability
        reconciled_records = sum(
            1 for a in accountabilities if a.result == ReconciliationResult.RECONCILED
        )
        discrepancy_records = sum(
            1 for a in accountabilities
            if a.result in (ReconciliationResult.MINOR_DISCREPANCY, ReconciliationResult.MAJOR_DISCREPANCY)
        )

        return SupplyReturnsMetrics(
            total_returns=len(returns),
            returns_by_status=returns_by_status,
            returns_by_reason=returns_by_reason,
            total_units_returned=total_units_returned,
            total_destructions=len(destructions),
            total_units_destroyed=total_units_destroyed,
            destructions_by_method=destructions_by_method,
            total_excursions=len(excursions),
            excursions_by_severity=excursions_by_severity,
            total_quarantined=len(quarantines),
            currently_quarantined=currently_quarantined,
            total_accountability_records=len(accountabilities),
            reconciled_records=reconciled_records,
            discrepancy_records=discrepancy_records,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ClinicalSupplyReturnsService | None = None
_instance_lock = threading.Lock()


def get_clinical_supply_returns_service() -> ClinicalSupplyReturnsService:
    """Return the singleton ClinicalSupplyReturnsService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ClinicalSupplyReturnsService()
    return _instance


def reset_clinical_supply_returns_service() -> ClinicalSupplyReturnsService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = ClinicalSupplyReturnsService()
    return _instance
