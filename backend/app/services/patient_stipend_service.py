"""Patient Stipend Management Service.

Manages patient compensation for clinical trial participation including stipend
schedules, payment processing, tax reporting, travel reimbursements, and
compliance with fair market value (FMV) guidelines.

Usage:
    from app.services.patient_stipend_service import (
        get_patient_stipend_service,
    )

    svc = get_patient_stipend_service()
    stipends = svc.list_stipends()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.patient_stipend import (
    PatientPaymentSummary,
    PatientStipend,
    PatientStipendCreate,
    PatientStipendUpdate,
    PaymentMethod,
    ProcessPaymentRequest,
    StipendMetrics,
    StipendSchedule,
    StipendScheduleCreate,
    StipendScheduleUpdate,
    StipendStatus,
    StipendType,
    TaxFormType,
    TaxRecord,
    TravelReimbursement,
    TravelReimbursementCreate,
    TravelReimbursementUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

# IRS reporting threshold (US)
IRS_REPORTING_THRESHOLD = 600.0

# Default mileage rate (IRS 2026 standard)
DEFAULT_MILEAGE_RATE = 0.67


class PatientStipendService:
    """In-memory Patient Stipend Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._schedules: dict[str, StipendSchedule] = {}
        self._stipends: dict[str, PatientStipend] = {}
        self._travel_reimbursements: dict[str, TravelReimbursement] = {}
        self._tax_records: dict[str, TaxRecord] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic patient stipend data across clinical trials."""
        now = datetime.now(timezone.utc)

        # --- Stipend Schedules (6) ---
        schedules_data = [
            {
                "id": "SCHED-001",
                "trial_id": EYLEA_TRIAL,
                "stipend_type": StipendType.VISIT_COMPENSATION,
                "visit_number": None,
                "amount": 75.00,
                "currency": "USD",
                "description": "Standard per-visit compensation for Eylea trial participants",
                "requires_receipt": False,
                "max_amount": None,
            },
            {
                "id": "SCHED-002",
                "trial_id": EYLEA_TRIAL,
                "stipend_type": StipendType.TRAVEL_REIMBURSEMENT,
                "visit_number": None,
                "amount": 0.67,
                "currency": "USD",
                "description": "Mileage reimbursement at IRS standard rate for Eylea trial",
                "requires_receipt": True,
                "max_amount": 150.00,
            },
            {
                "id": "SCHED-003",
                "trial_id": EYLEA_TRIAL,
                "stipend_type": StipendType.COMPLETION_BONUS,
                "visit_number": None,
                "amount": 200.00,
                "currency": "USD",
                "description": "Completion bonus for finishing all Eylea trial visits",
                "requires_receipt": False,
                "max_amount": None,
            },
            {
                "id": "SCHED-004",
                "trial_id": DUPIXENT_TRIAL,
                "stipend_type": StipendType.VISIT_COMPENSATION,
                "visit_number": None,
                "amount": 100.00,
                "currency": "USD",
                "description": "Per-visit compensation for Dupixent trial participants",
                "requires_receipt": False,
                "max_amount": None,
            },
            {
                "id": "SCHED-005",
                "trial_id": DUPIXENT_TRIAL,
                "stipend_type": StipendType.MEAL_ALLOWANCE,
                "visit_number": None,
                "amount": 25.00,
                "currency": "USD",
                "description": "Meal allowance per visit for Dupixent trial",
                "requires_receipt": True,
                "max_amount": 25.00,
            },
            {
                "id": "SCHED-006",
                "trial_id": LIBTAYO_TRIAL,
                "stipend_type": StipendType.VISIT_COMPENSATION,
                "visit_number": None,
                "amount": 125.00,
                "currency": "USD",
                "description": "Per-visit compensation for Libtayo oncology trial participants",
                "requires_receipt": False,
                "max_amount": None,
            },
        ]

        for s in schedules_data:
            self._schedules[s["id"]] = StipendSchedule(**s)

        # --- Patient Stipends (14) ---
        stipends_data = [
            {
                "id": "STIP-001",
                "patient_id": "PAT-1001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "schedule_id": "SCHED-001",
                "stipend_type": StipendType.VISIT_COMPENSATION,
                "visit_number": 1,
                "visit_date": now - timedelta(days=90),
                "amount": 75.00,
                "currency": "USD",
                "status": StipendStatus.PAID,
                "payment_method": PaymentMethod.DIRECT_DEPOSIT,
                "payment_date": now - timedelta(days=85),
                "payment_reference": "ACH-20260101-001",
                "receipt_submitted": False,
                "receipt_verified": False,
                "notes": None,
                "created_at": now - timedelta(days=91),
            },
            {
                "id": "STIP-002",
                "patient_id": "PAT-1001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "schedule_id": "SCHED-001",
                "stipend_type": StipendType.VISIT_COMPENSATION,
                "visit_number": 2,
                "visit_date": now - timedelta(days=60),
                "amount": 75.00,
                "currency": "USD",
                "status": StipendStatus.PAID,
                "payment_method": PaymentMethod.DIRECT_DEPOSIT,
                "payment_date": now - timedelta(days=55),
                "payment_reference": "ACH-20260201-002",
                "receipt_submitted": False,
                "receipt_verified": False,
                "notes": None,
                "created_at": now - timedelta(days=61),
            },
            {
                "id": "STIP-003",
                "patient_id": "PAT-1001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "schedule_id": "SCHED-001",
                "stipend_type": StipendType.VISIT_COMPENSATION,
                "visit_number": 3,
                "visit_date": now - timedelta(days=30),
                "amount": 75.00,
                "currency": "USD",
                "status": StipendStatus.PAID,
                "payment_method": PaymentMethod.DIRECT_DEPOSIT,
                "payment_date": now - timedelta(days=25),
                "payment_reference": "ACH-20260301-003",
                "receipt_submitted": False,
                "receipt_verified": False,
                "notes": None,
                "created_at": now - timedelta(days=31),
            },
            {
                "id": "STIP-004",
                "patient_id": "PAT-1001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "schedule_id": "SCHED-001",
                "stipend_type": StipendType.VISIT_COMPENSATION,
                "visit_number": 4,
                "visit_date": now - timedelta(days=5),
                "amount": 75.00,
                "currency": "USD",
                "status": StipendStatus.APPROVED,
                "payment_method": None,
                "payment_date": None,
                "payment_reference": None,
                "receipt_submitted": False,
                "receipt_verified": False,
                "notes": "Awaiting payment processing",
                "created_at": now - timedelta(days=6),
            },
            {
                "id": "STIP-005",
                "patient_id": "PAT-1001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "schedule_id": "SCHED-001",
                "stipend_type": StipendType.VISIT_COMPENSATION,
                "visit_number": 5,
                "visit_date": None,
                "amount": 75.00,
                "currency": "USD",
                "status": StipendStatus.SCHEDULED,
                "payment_method": None,
                "payment_date": None,
                "payment_reference": None,
                "receipt_submitted": False,
                "receipt_verified": False,
                "notes": "Future visit",
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "STIP-006",
                "patient_id": "PAT-1002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "schedule_id": "SCHED-001",
                "stipend_type": StipendType.VISIT_COMPENSATION,
                "visit_number": 1,
                "visit_date": now - timedelta(days=80),
                "amount": 75.00,
                "currency": "USD",
                "status": StipendStatus.PAID,
                "payment_method": PaymentMethod.PREPAID_CARD,
                "payment_date": now - timedelta(days=75),
                "payment_reference": "PPC-20260115-001",
                "receipt_submitted": False,
                "receipt_verified": False,
                "notes": None,
                "created_at": now - timedelta(days=81),
            },
            {
                "id": "STIP-007",
                "patient_id": "PAT-1002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "schedule_id": "SCHED-001",
                "stipend_type": StipendType.VISIT_COMPENSATION,
                "visit_number": 2,
                "visit_date": now - timedelta(days=50),
                "amount": 75.00,
                "currency": "USD",
                "status": StipendStatus.PAID,
                "payment_method": PaymentMethod.PREPAID_CARD,
                "payment_date": now - timedelta(days=45),
                "payment_reference": "PPC-20260215-002",
                "receipt_submitted": False,
                "receipt_verified": False,
                "notes": None,
                "created_at": now - timedelta(days=51),
            },
            {
                "id": "STIP-008",
                "patient_id": "PAT-1003",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "schedule_id": "SCHED-004",
                "stipend_type": StipendType.VISIT_COMPENSATION,
                "visit_number": 1,
                "visit_date": now - timedelta(days=45),
                "amount": 100.00,
                "currency": "USD",
                "status": StipendStatus.PAID,
                "payment_method": PaymentMethod.CHECK,
                "payment_date": now - timedelta(days=38),
                "payment_reference": "CHK-50001",
                "receipt_submitted": False,
                "receipt_verified": False,
                "notes": None,
                "created_at": now - timedelta(days=46),
            },
            {
                "id": "STIP-009",
                "patient_id": "PAT-1003",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "schedule_id": "SCHED-005",
                "stipend_type": StipendType.MEAL_ALLOWANCE,
                "visit_number": 1,
                "visit_date": now - timedelta(days=45),
                "amount": 22.50,
                "currency": "USD",
                "status": StipendStatus.PAID,
                "payment_method": PaymentMethod.CHECK,
                "payment_date": now - timedelta(days=38),
                "payment_reference": "CHK-50002",
                "receipt_submitted": True,
                "receipt_verified": True,
                "notes": "Lunch receipt verified",
                "created_at": now - timedelta(days=46),
            },
            {
                "id": "STIP-010",
                "patient_id": "PAT-1003",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "schedule_id": "SCHED-004",
                "stipend_type": StipendType.VISIT_COMPENSATION,
                "visit_number": 2,
                "visit_date": now - timedelta(days=15),
                "amount": 100.00,
                "currency": "USD",
                "status": StipendStatus.PROCESSING,
                "payment_method": PaymentMethod.CHECK,
                "payment_date": None,
                "payment_reference": None,
                "receipt_submitted": False,
                "receipt_verified": False,
                "notes": "Payment in processing",
                "created_at": now - timedelta(days=16),
            },
            {
                "id": "STIP-011",
                "patient_id": "PAT-1004",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "schedule_id": "SCHED-006",
                "stipend_type": StipendType.VISIT_COMPENSATION,
                "visit_number": 1,
                "visit_date": now - timedelta(days=70),
                "amount": 125.00,
                "currency": "USD",
                "status": StipendStatus.PAID,
                "payment_method": PaymentMethod.DIRECT_DEPOSIT,
                "payment_date": now - timedelta(days=65),
                "payment_reference": "ACH-20260110-004",
                "receipt_submitted": False,
                "receipt_verified": False,
                "notes": None,
                "created_at": now - timedelta(days=71),
            },
            {
                "id": "STIP-012",
                "patient_id": "PAT-1004",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "schedule_id": "SCHED-006",
                "stipend_type": StipendType.VISIT_COMPENSATION,
                "visit_number": 2,
                "visit_date": now - timedelta(days=40),
                "amount": 125.00,
                "currency": "USD",
                "status": StipendStatus.PAID,
                "payment_method": PaymentMethod.DIRECT_DEPOSIT,
                "payment_date": now - timedelta(days=35),
                "payment_reference": "ACH-20260210-005",
                "receipt_submitted": False,
                "receipt_verified": False,
                "notes": None,
                "created_at": now - timedelta(days=41),
            },
            {
                "id": "STIP-013",
                "patient_id": "PAT-1005",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "schedule_id": "SCHED-001",
                "stipend_type": StipendType.SCREEN_FAILURE_COMPENSATION,
                "visit_number": None,
                "visit_date": now - timedelta(days=60),
                "amount": 50.00,
                "currency": "USD",
                "status": StipendStatus.PAID,
                "payment_method": PaymentMethod.GIFT_CARD,
                "payment_date": now - timedelta(days=55),
                "payment_reference": "GC-20260201-001",
                "receipt_submitted": False,
                "receipt_verified": False,
                "notes": "Patient failed screening; screen failure compensation issued",
                "created_at": now - timedelta(days=61),
            },
            {
                "id": "STIP-014",
                "patient_id": "PAT-1004",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "schedule_id": "SCHED-006",
                "stipend_type": StipendType.VISIT_COMPENSATION,
                "visit_number": 3,
                "visit_date": now - timedelta(days=10),
                "amount": 125.00,
                "currency": "USD",
                "status": StipendStatus.ON_HOLD,
                "payment_method": None,
                "payment_date": None,
                "payment_reference": None,
                "receipt_submitted": False,
                "receipt_verified": False,
                "notes": "On hold pending tax form submission",
                "created_at": now - timedelta(days=11),
            },
        ]

        for st in stipends_data:
            self._stipends[st["id"]] = PatientStipend(**st)

        # --- Travel Reimbursements (5) ---
        travel_data = [
            {
                "id": "TRVL-001",
                "patient_id": "PAT-1001",
                "trial_id": EYLEA_TRIAL,
                "visit_number": 1,
                "travel_date": now - timedelta(days=90),
                "distance_miles": 45.0,
                "mileage_rate": 0.67,
                "parking_amount": 12.00,
                "tolls_amount": 5.50,
                "lodging_amount": 0.0,
                "meal_amount": 0.0,
                "total_amount": 47.65,
                "receipt_path": "/receipts/PAT-1001/visit1-mileage.pdf",
                "status": StipendStatus.PAID,
                "created_at": now - timedelta(days=89),
            },
            {
                "id": "TRVL-002",
                "patient_id": "PAT-1001",
                "trial_id": EYLEA_TRIAL,
                "visit_number": 2,
                "travel_date": now - timedelta(days=60),
                "distance_miles": 45.0,
                "mileage_rate": 0.67,
                "parking_amount": 12.00,
                "tolls_amount": 5.50,
                "lodging_amount": 0.0,
                "meal_amount": 0.0,
                "total_amount": 47.65,
                "receipt_path": "/receipts/PAT-1001/visit2-mileage.pdf",
                "status": StipendStatus.PAID,
                "created_at": now - timedelta(days=59),
            },
            {
                "id": "TRVL-003",
                "patient_id": "PAT-1003",
                "trial_id": DUPIXENT_TRIAL,
                "visit_number": 1,
                "travel_date": now - timedelta(days=45),
                "distance_miles": 120.0,
                "mileage_rate": 0.67,
                "parking_amount": 20.00,
                "tolls_amount": 8.00,
                "lodging_amount": 149.00,
                "meal_amount": 35.00,
                "total_amount": 292.40,
                "receipt_path": "/receipts/PAT-1003/visit1-travel.pdf",
                "status": StipendStatus.PAID,
                "created_at": now - timedelta(days=44),
            },
            {
                "id": "TRVL-004",
                "patient_id": "PAT-1004",
                "trial_id": LIBTAYO_TRIAL,
                "visit_number": 1,
                "travel_date": now - timedelta(days=70),
                "distance_miles": 30.0,
                "mileage_rate": 0.67,
                "parking_amount": 8.00,
                "tolls_amount": 0.0,
                "lodging_amount": 0.0,
                "meal_amount": 15.00,
                "total_amount": 43.10,
                "receipt_path": "/receipts/PAT-1004/visit1-travel.pdf",
                "status": StipendStatus.PAID,
                "created_at": now - timedelta(days=69),
            },
            {
                "id": "TRVL-005",
                "patient_id": "PAT-1001",
                "trial_id": EYLEA_TRIAL,
                "visit_number": 3,
                "travel_date": now - timedelta(days=30),
                "distance_miles": 45.0,
                "mileage_rate": 0.67,
                "parking_amount": 15.00,
                "tolls_amount": 5.50,
                "lodging_amount": 0.0,
                "meal_amount": 0.0,
                "total_amount": 50.65,
                "receipt_path": None,
                "status": StipendStatus.APPROVED,
                "created_at": now - timedelta(days=29),
            },
        ]

        for t in travel_data:
            self._travel_reimbursements[t["id"]] = TravelReimbursement(**t)

        # --- Tax Records (3) ---
        tax_data = [
            {
                "id": "TAX-001",
                "patient_id": "PAT-1001",
                "trial_id": EYLEA_TRIAL,
                "tax_year": 2026,
                "total_paid_ytd": 225.00,
                "form_type": TaxFormType.W9,
                "form_submitted": True,
                "form_date": now - timedelta(days=100),
                "threshold_amount": 600.0,
                "threshold_exceeded": False,
                "withholding_required": False,
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "TAX-002",
                "patient_id": "PAT-1003",
                "trial_id": DUPIXENT_TRIAL,
                "tax_year": 2026,
                "total_paid_ytd": 122.50,
                "form_type": TaxFormType.W9,
                "form_submitted": True,
                "form_date": now - timedelta(days=50),
                "threshold_amount": 600.0,
                "threshold_exceeded": False,
                "withholding_required": False,
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "TAX-003",
                "patient_id": "PAT-1004",
                "trial_id": LIBTAYO_TRIAL,
                "tax_year": 2026,
                "total_paid_ytd": 250.00,
                "form_type": TaxFormType.W8BEN,
                "form_submitted": False,
                "form_date": None,
                "threshold_amount": 600.0,
                "threshold_exceeded": False,
                "withholding_required": True,
                "created_at": now - timedelta(days=70),
            },
        ]

        for tr in tax_data:
            self._tax_records[tr["id"]] = TaxRecord(**tr)

    # ------------------------------------------------------------------
    # Stipend Schedule Management
    # ------------------------------------------------------------------

    def list_schedules(
        self,
        *,
        trial_id: str | None = None,
        stipend_type: StipendType | None = None,
    ) -> list[StipendSchedule]:
        """List stipend schedules with optional filters."""
        with self._lock:
            result = list(self._schedules.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if stipend_type is not None:
            result = [s for s in result if s.stipend_type == stipend_type]

        return sorted(result, key=lambda s: s.id)

    def get_schedule(self, schedule_id: str) -> StipendSchedule | None:
        """Get a single stipend schedule by ID."""
        with self._lock:
            return self._schedules.get(schedule_id)

    def create_schedule(self, payload: StipendScheduleCreate) -> StipendSchedule:
        """Create a new stipend schedule."""
        schedule_id = f"SCHED-{uuid4().hex[:8].upper()}"
        schedule = StipendSchedule(
            id=schedule_id,
            **payload.model_dump(),
        )
        with self._lock:
            self._schedules[schedule_id] = schedule
        logger.info("Created stipend schedule %s for trial %s", schedule_id, payload.trial_id)
        return schedule

    def update_schedule(self, schedule_id: str, payload: StipendScheduleUpdate) -> StipendSchedule | None:
        """Update an existing stipend schedule."""
        with self._lock:
            existing = self._schedules.get(schedule_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = StipendSchedule(**data)
            self._schedules[schedule_id] = updated
        return updated

    def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a stipend schedule. Returns True if deleted, False if not found."""
        with self._lock:
            if schedule_id in self._schedules:
                del self._schedules[schedule_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Patient Stipend Management
    # ------------------------------------------------------------------

    def list_stipends(
        self,
        *,
        patient_id: str | None = None,
        trial_id: str | None = None,
        site_id: str | None = None,
        status: StipendStatus | None = None,
        stipend_type: StipendType | None = None,
    ) -> list[PatientStipend]:
        """List patient stipends with optional filters."""
        with self._lock:
            result = list(self._stipends.values())

        if patient_id is not None:
            result = [s for s in result if s.patient_id == patient_id]
        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if site_id is not None:
            result = [s for s in result if s.site_id == site_id]
        if status is not None:
            result = [s for s in result if s.status == status]
        if stipend_type is not None:
            result = [s for s in result if s.stipend_type == stipend_type]

        return sorted(result, key=lambda s: s.created_at, reverse=True)

    def get_stipend(self, stipend_id: str) -> PatientStipend | None:
        """Get a single patient stipend by ID."""
        with self._lock:
            return self._stipends.get(stipend_id)

    def create_stipend(self, payload: PatientStipendCreate) -> PatientStipend:
        """Create a new patient stipend payment record."""
        now = datetime.now(timezone.utc)
        stipend_id = f"STIP-{uuid4().hex[:8].upper()}"
        stipend = PatientStipend(
            id=stipend_id,
            patient_id=payload.patient_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            schedule_id=payload.schedule_id,
            stipend_type=payload.stipend_type,
            visit_number=payload.visit_number,
            visit_date=payload.visit_date,
            amount=payload.amount,
            currency=payload.currency,
            status=StipendStatus.SCHEDULED,
            payment_method=payload.payment_method,
            payment_date=None,
            payment_reference=None,
            receipt_submitted=False,
            receipt_verified=False,
            notes=payload.notes,
            created_at=now,
        )
        with self._lock:
            self._stipends[stipend_id] = stipend
        logger.info("Created stipend %s for patient %s", stipend_id, payload.patient_id)
        return stipend

    def update_stipend(self, stipend_id: str, payload: PatientStipendUpdate) -> PatientStipend | None:
        """Update a patient stipend."""
        with self._lock:
            existing = self._stipends.get(stipend_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = PatientStipend(**data)
            self._stipends[stipend_id] = updated
        return updated

    def delete_stipend(self, stipend_id: str) -> bool:
        """Delete a patient stipend. Returns True if deleted."""
        with self._lock:
            if stipend_id in self._stipends:
                del self._stipends[stipend_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Payment Processing
    # ------------------------------------------------------------------

    def process_payment(
        self,
        stipend_id: str,
        payload: ProcessPaymentRequest,
    ) -> PatientStipend:
        """Process a stipend payment, transitioning it through the payment lifecycle.

        Valid transitions:
        - scheduled/approved -> processing -> paid
        - Only scheduled or approved stipends can be processed.
        """
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._stipends.get(stipend_id)
            if existing is None:
                raise ValueError(f"Stipend '{stipend_id}' not found")

            if existing.status not in (StipendStatus.SCHEDULED, StipendStatus.APPROVED):
                raise ValueError(
                    f"Stipend '{stipend_id}' cannot be processed: current status is '{existing.status.value}'"
                )

            data = existing.model_dump()
            data["status"] = StipendStatus.PAID
            data["payment_method"] = payload.payment_method
            data["payment_date"] = now
            data["payment_reference"] = payload.payment_reference or f"PAY-{uuid4().hex[:8].upper()}"
            if payload.notes:
                data["notes"] = payload.notes
            updated = PatientStipend(**data)
            self._stipends[stipend_id] = updated

        # Update tax record
        self._update_tax_ytd(updated.patient_id, updated.trial_id, updated.amount)

        logger.info(
            "Processed payment for stipend %s: patient=%s amount=%.2f method=%s",
            stipend_id, updated.patient_id, updated.amount, payload.payment_method.value,
        )
        return updated

    def _update_tax_ytd(self, patient_id: str, trial_id: str, amount: float) -> None:
        """Update YTD tax record when a payment is processed."""
        now = datetime.now(timezone.utc)
        current_year = now.year

        with self._lock:
            # Find existing tax record for this patient/trial/year
            matching_record = None
            for tr in self._tax_records.values():
                if (
                    tr.patient_id == patient_id
                    and tr.trial_id == trial_id
                    and tr.tax_year == current_year
                ):
                    matching_record = tr
                    break

            if matching_record is not None:
                data = matching_record.model_dump()
                data["total_paid_ytd"] = round(data["total_paid_ytd"] + amount, 2)
                data["threshold_exceeded"] = data["total_paid_ytd"] >= data["threshold_amount"]
                updated = TaxRecord(**data)
                self._tax_records[matching_record.id] = updated

    # ------------------------------------------------------------------
    # Receipt Management
    # ------------------------------------------------------------------

    def submit_receipt(self, stipend_id: str, receipt_path: str, notes: str | None = None) -> PatientStipend:
        """Submit a receipt for a stipend that requires one."""
        with self._lock:
            existing = self._stipends.get(stipend_id)
            if existing is None:
                raise ValueError(f"Stipend '{stipend_id}' not found")

            data = existing.model_dump()
            data["receipt_submitted"] = True
            if notes:
                data["notes"] = notes
            updated = PatientStipend(**data)
            self._stipends[stipend_id] = updated
        logger.info("Receipt submitted for stipend %s", stipend_id)
        return updated

    def verify_receipt(self, stipend_id: str, verified: bool = True) -> PatientStipend:
        """Verify (or reject) a submitted receipt for a stipend."""
        with self._lock:
            existing = self._stipends.get(stipend_id)
            if existing is None:
                raise ValueError(f"Stipend '{stipend_id}' not found")

            if not existing.receipt_submitted:
                raise ValueError(f"Stipend '{stipend_id}' has no receipt submitted to verify")

            data = existing.model_dump()
            data["receipt_verified"] = verified
            updated = PatientStipend(**data)
            self._stipends[stipend_id] = updated
        logger.info("Receipt %s for stipend %s", "verified" if verified else "rejected", stipend_id)
        return updated

    # ------------------------------------------------------------------
    # Travel Reimbursement Management
    # ------------------------------------------------------------------

    def list_travel_reimbursements(
        self,
        *,
        patient_id: str | None = None,
        trial_id: str | None = None,
        status: StipendStatus | None = None,
    ) -> list[TravelReimbursement]:
        """List travel reimbursements with optional filters."""
        with self._lock:
            result = list(self._travel_reimbursements.values())

        if patient_id is not None:
            result = [t for t in result if t.patient_id == patient_id]
        if trial_id is not None:
            result = [t for t in result if t.trial_id == trial_id]
        if status is not None:
            result = [t for t in result if t.status == status]

        return sorted(result, key=lambda t: t.travel_date, reverse=True)

    def get_travel_reimbursement(self, reimbursement_id: str) -> TravelReimbursement | None:
        """Get a single travel reimbursement by ID."""
        with self._lock:
            return self._travel_reimbursements.get(reimbursement_id)

    def create_travel_reimbursement(self, payload: TravelReimbursementCreate) -> TravelReimbursement:
        """Create a new travel reimbursement claim."""
        now = datetime.now(timezone.utc)
        reimb_id = f"TRVL-{uuid4().hex[:8].upper()}"

        # Calculate total
        mileage_total = round(payload.distance_miles * payload.mileage_rate, 2)
        total = round(
            mileage_total
            + payload.parking_amount
            + payload.tolls_amount
            + payload.lodging_amount
            + payload.meal_amount,
            2,
        )

        reimb = TravelReimbursement(
            id=reimb_id,
            patient_id=payload.patient_id,
            trial_id=payload.trial_id,
            visit_number=payload.visit_number,
            travel_date=payload.travel_date,
            distance_miles=payload.distance_miles,
            mileage_rate=payload.mileage_rate,
            parking_amount=payload.parking_amount,
            tolls_amount=payload.tolls_amount,
            lodging_amount=payload.lodging_amount,
            meal_amount=payload.meal_amount,
            total_amount=total,
            receipt_path=payload.receipt_path,
            status=StipendStatus.SCHEDULED,
            created_at=now,
        )
        with self._lock:
            self._travel_reimbursements[reimb_id] = reimb
        logger.info(
            "Created travel reimbursement %s for patient %s: $%.2f",
            reimb_id, payload.patient_id, total,
        )
        return reimb

    def update_travel_reimbursement(
        self, reimbursement_id: str, payload: TravelReimbursementUpdate
    ) -> TravelReimbursement | None:
        """Update a travel reimbursement claim and recalculate total."""
        with self._lock:
            existing = self._travel_reimbursements.get(reimbursement_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)

            # Recalculate total
            mileage_total = round(data["distance_miles"] * data["mileage_rate"], 2)
            data["total_amount"] = round(
                mileage_total
                + data["parking_amount"]
                + data["tolls_amount"]
                + data["lodging_amount"]
                + data["meal_amount"],
                2,
            )
            updated = TravelReimbursement(**data)
            self._travel_reimbursements[reimbursement_id] = updated
        return updated

    def delete_travel_reimbursement(self, reimbursement_id: str) -> bool:
        """Delete a travel reimbursement. Returns True if deleted."""
        with self._lock:
            if reimbursement_id in self._travel_reimbursements:
                del self._travel_reimbursements[reimbursement_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Tax Record Management
    # ------------------------------------------------------------------

    def list_tax_records(
        self,
        *,
        patient_id: str | None = None,
        trial_id: str | None = None,
        tax_year: int | None = None,
    ) -> list[TaxRecord]:
        """List tax records with optional filters."""
        with self._lock:
            result = list(self._tax_records.values())

        if patient_id is not None:
            result = [t for t in result if t.patient_id == patient_id]
        if trial_id is not None:
            result = [t for t in result if t.trial_id == trial_id]
        if tax_year is not None:
            result = [t for t in result if t.tax_year == tax_year]

        return sorted(result, key=lambda t: t.id)

    def get_tax_record(self, tax_record_id: str) -> TaxRecord | None:
        """Get a single tax record by ID."""
        with self._lock:
            return self._tax_records.get(tax_record_id)

    def check_tax_threshold(self, patient_id: str, trial_id: str) -> TaxRecord | None:
        """Check if a patient has exceeded the IRS reporting threshold.

        Returns the tax record if found, with threshold_exceeded flag updated.
        """
        now = datetime.now(timezone.utc)
        current_year = now.year

        with self._lock:
            for tr in self._tax_records.values():
                if (
                    tr.patient_id == patient_id
                    and tr.trial_id == trial_id
                    and tr.tax_year == current_year
                ):
                    return tr
        return None

    # ------------------------------------------------------------------
    # Patient Summary
    # ------------------------------------------------------------------

    def get_patient_summary(self, patient_id: str, trial_id: str) -> PatientPaymentSummary | None:
        """Generate a comprehensive payment summary for a patient in a trial."""
        with self._lock:
            stipends = [
                s for s in self._stipends.values()
                if s.patient_id == patient_id and s.trial_id == trial_id
            ]

        if not stipends:
            return None

        total_earned = 0.0
        total_paid = 0.0
        total_pending = 0.0
        payments_by_type: dict[str, float] = {}
        visits_completed = 0

        for s in stipends:
            total_earned += s.amount

            if s.status == StipendStatus.PAID:
                total_paid += s.amount
            elif s.status in (
                StipendStatus.SCHEDULED,
                StipendStatus.APPROVED,
                StipendStatus.PROCESSING,
            ):
                total_pending += s.amount

            type_key = s.stipend_type.value
            payments_by_type[type_key] = round(
                payments_by_type.get(type_key, 0.0) + s.amount, 2
            )

            if s.visit_number is not None and s.status == StipendStatus.PAID:
                visits_completed += 1

        return PatientPaymentSummary(
            patient_id=patient_id,
            trial_id=trial_id,
            total_earned=round(total_earned, 2),
            total_paid=round(total_paid, 2),
            total_pending=round(total_pending, 2),
            payments_by_type=payments_by_type,
            visits_completed=visits_completed,
        )

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self) -> StipendMetrics:
        """Compute aggregated patient stipend operational metrics."""
        with self._lock:
            schedules = list(self._schedules.values())
            stipends = list(self._stipends.values())
            travel_reimbursements = list(self._travel_reimbursements.values())
            tax_records = list(self._tax_records.values())

        # Stipend totals
        total_paid_amount = 0.0
        total_pending_amount = 0.0
        stipends_by_status: dict[str, int] = {}
        stipends_by_type: dict[str, int] = {}
        unique_patients: set[str] = set()
        visit_payment_count = 0
        visit_payment_total = 0.0

        for s in stipends:
            status_key = s.status.value
            stipends_by_status[status_key] = stipends_by_status.get(status_key, 0) + 1

            type_key = s.stipend_type.value
            stipends_by_type[type_key] = stipends_by_type.get(type_key, 0) + 1

            unique_patients.add(s.patient_id)

            if s.status == StipendStatus.PAID:
                total_paid_amount += s.amount
                if s.visit_number is not None:
                    visit_payment_count += 1
                    visit_payment_total += s.amount
            elif s.status in (
                StipendStatus.SCHEDULED,
                StipendStatus.APPROVED,
                StipendStatus.PROCESSING,
            ):
                total_pending_amount += s.amount

        # Travel reimbursements
        total_travel_amount = sum(t.total_amount for t in travel_reimbursements)

        # Tax records
        patients_exceeding = sum(1 for t in tax_records if t.threshold_exceeded)

        # Average payment per visit
        avg_per_visit = round(visit_payment_total / max(1, visit_payment_count), 2)

        return StipendMetrics(
            total_schedules=len(schedules),
            total_stipends=len(stipends),
            total_paid_amount=round(total_paid_amount, 2),
            total_pending_amount=round(total_pending_amount, 2),
            stipends_by_status=stipends_by_status,
            stipends_by_type=stipends_by_type,
            total_travel_reimbursements=len(travel_reimbursements),
            total_travel_amount=round(total_travel_amount, 2),
            total_tax_records=len(tax_records),
            patients_exceeding_threshold=patients_exceeding,
            avg_payment_per_visit=avg_per_visit,
            unique_patients=len(unique_patients),
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: PatientStipendService | None = None
_instance_lock = threading.Lock()


def get_patient_stipend_service() -> PatientStipendService:
    """Return the singleton PatientStipendService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = PatientStipendService()
    return _instance


def reset_patient_stipend_service() -> PatientStipendService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = PatientStipendService()
    return _instance
