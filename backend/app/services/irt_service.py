"""Interactive Response Technology (IRT/IWRS) Service (CLINICAL-19).

Manages IRT operations including transaction processing, drug supply tracking
and accountability, visit scheduling with window calculations, stratification
management, automated drug assignment based on randomization, drug resupply
triggers, dose modification workflows, and patient compliance tracking.

Usage:
    from app.services.irt_service import (
        get_irt_service,
    )

    svc = get_irt_service()
    transactions = svc.list_transactions()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import random
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.irt_system import (
    DoseModificationRequest,
    DrugAccountabilitySummary,
    DrugAssignment,
    DrugAssignmentCreate,
    DrugAssignmentUpdate,
    DrugKit,
    DrugResupplyRequest,
    DrugSupplyStatus,
    IRTConfiguration,
    IRTConfigurationUpdate,
    IRTMetrics,
    IRTTransaction,
    IRTTransactionCreate,
    IRTTransactionType,
    StratificationEntry,
    StratificationEntryCreate,
    StratificationFactor,
    UnblindingRequest,
    VisitConfirmation,
    VisitSchedule,
    VisitScheduleCreate,
    VisitWindow,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

# Site IDs matching RBM service
SITE_IDS = ["SITE-101", "SITE-102", "SITE-103", "SITE-104", "SITE-105", "SITE-106", "SITE-107", "SITE-108"]

# Drug supply buffer threshold
DEFAULT_BUFFER_WEEKS = 4


class IRTService:
    """In-memory Interactive Response Technology engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._transactions: dict[str, IRTTransaction] = {}
        self._drug_assignments: dict[str, DrugAssignment] = {}
        self._visit_schedules: dict[str, VisitSchedule] = {}
        self._stratification_entries: dict[str, StratificationEntry] = {}
        self._configurations: dict[str, IRTConfiguration] = {}
        self._drug_kits: dict[str, DrugKit] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic IRT data across clinical trial sites."""
        now = datetime.now(timezone.utc)
        random.seed(42)  # Reproducible seed data

        # --- 3 IRT Configurations ---
        configs = [
            IRTConfiguration(
                trial_id=EYLEA_TRIAL,
                randomization_ratio="2:1",
                stratification_factors=[
                    StratificationFactor.AGE_GROUP.value,
                    StratificationFactor.DISEASE_SEVERITY.value,
                    StratificationFactor.GEOGRAPHIC_REGION.value,
                ],
                drug_supply_buffer_weeks=4,
                visit_windows=[
                    "Screening: Day -28 to Day -1",
                    "Baseline: Day 1",
                    "Week 4: Day 22 to Day 34",
                    "Week 8: Day 50 to Day 62",
                    "Week 12: Day 78 to Day 90",
                    "Week 16: Day 106 to Day 118",
                    "Week 24: Day 162 to Day 174",
                ],
                dose_levels=["2mg", "4mg", "8mg"],
            ),
            IRTConfiguration(
                trial_id=DUPIXENT_TRIAL,
                randomization_ratio="1:1",
                stratification_factors=[
                    StratificationFactor.AGE_GROUP.value,
                    StratificationFactor.SEX.value,
                    StratificationFactor.PRIOR_THERAPY.value,
                ],
                drug_supply_buffer_weeks=6,
                visit_windows=[
                    "Screening: Day -14 to Day -1",
                    "Baseline: Day 1",
                    "Week 2: Day 10 to Day 18",
                    "Week 4: Day 24 to Day 32",
                    "Week 8: Day 52 to Day 60",
                    "Week 12: Day 80 to Day 88",
                    "Week 16: Day 108 to Day 116",
                ],
                dose_levels=["200mg", "300mg"],
            ),
            IRTConfiguration(
                trial_id=LIBTAYO_TRIAL,
                randomization_ratio="1:1:1",
                stratification_factors=[
                    StratificationFactor.DISEASE_SEVERITY.value,
                    StratificationFactor.PRIOR_THERAPY.value,
                    StratificationFactor.GEOGRAPHIC_REGION.value,
                ],
                drug_supply_buffer_weeks=4,
                visit_windows=[
                    "Screening: Day -21 to Day -1",
                    "Cycle 1 Day 1: Day 1",
                    "Cycle 1 Day 15: Day 12 to Day 18",
                    "Cycle 2 Day 1: Day 18 to Day 24",
                    "Cycle 3 Day 1: Day 39 to Day 45",
                    "Cycle 4 Day 1: Day 60 to Day 66",
                ],
                dose_levels=["350mg q3w", "350mg q3w + chemo"],
            ),
        ]
        for cfg in configs:
            self._configurations[cfg.trial_id] = cfg

        # --- Patient IDs ---
        patient_ids = [f"PAT-{i:04d}" for i in range(1, 41)]

        # Treatment arms per trial
        trial_arms = {
            EYLEA_TRIAL: ["Eylea 2mg", "Eylea 8mg", "Sham"],
            DUPIXENT_TRIAL: ["Dupixent 300mg", "Placebo"],
            LIBTAYO_TRIAL: ["Libtayo monotherapy", "Libtayo + chemo", "Chemo alone"],
        }

        # --- 50 Transactions ---
        transaction_types = list(IRTTransactionType)
        monitors = ["Dr. Sarah Chen", "Dr. James Wilson", "RN Maria Lopez", "CRC Tom Brown", "PI Dr. Patel"]
        tx_counter = 0
        for i in range(50):
            tx_counter += 1
            trial_id = random.choice([EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL])
            site_id = random.choice(SITE_IDS)
            patient_id = random.choice(patient_ids[:30])
            tx_type = transaction_types[i % len(transaction_types)]
            performer = random.choice(monitors)
            days_ago = random.randint(1, 180)

            details_map = {
                IRTTransactionType.SCREENING: f"Patient {patient_id} screened for eligibility",
                IRTTransactionType.RANDOMIZATION: f"Patient {patient_id} randomized to treatment arm",
                IRTTransactionType.DRUG_ASSIGNMENT: f"Drug kit assigned to patient {patient_id}",
                IRTTransactionType.DRUG_RESUPPLY: f"Drug resupply requested for site {site_id}",
                IRTTransactionType.VISIT_CONFIRMATION: f"Visit confirmed for patient {patient_id}",
                IRTTransactionType.UNBLINDING: f"Emergency unblinding for patient {patient_id}",
                IRTTransactionType.DOSE_MODIFICATION: f"Dose modified for patient {patient_id}",
                IRTTransactionType.DISCONTINUATION: f"Patient {patient_id} discontinued from study",
            }

            response_map = {
                IRTTransactionType.SCREENING: "Screening number assigned. Proceed with eligibility assessment.",
                IRTTransactionType.RANDOMIZATION: f"Randomized to {random.choice(trial_arms[trial_id])}. Stratification confirmed.",
                IRTTransactionType.DRUG_ASSIGNMENT: "Kit dispensed. Drug accountability updated.",
                IRTTransactionType.DRUG_RESUPPLY: "Resupply order placed. Expected delivery in 5 business days.",
                IRTTransactionType.VISIT_CONFIRMATION: "Visit confirmed within window. Next visit scheduled.",
                IRTTransactionType.UNBLINDING: "Treatment assignment revealed. Event logged for safety review.",
                IRTTransactionType.DOSE_MODIFICATION: "Dose modification approved. New kit assignment required.",
                IRTTransactionType.DISCONTINUATION: "Patient discontinued. Final visit and drug return required.",
            }

            tx = IRTTransaction(
                id=f"IRT-{tx_counter:04d}",
                trial_id=trial_id,
                site_id=site_id,
                patient_id=patient_id,
                transaction_type=tx_type,
                timestamp=now - timedelta(days=days_ago, hours=random.randint(0, 23)),
                details=details_map[tx_type],
                performed_by=performer,
                system_response=response_map[tx_type],
                confirmation_number=f"CNF-{uuid4().hex[:8].upper()}",
            )
            self._transactions[tx.id] = tx

        # --- 30 Drug Assignments ---
        lot_numbers = ["LOT-2025-A001", "LOT-2025-A002", "LOT-2025-B001", "LOT-2026-A001", "LOT-2026-A002"]
        for i in range(30):
            patient_id = patient_ids[i % len(patient_ids)]
            trial_id = [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL][i % 3]
            arm = random.choice(trial_arms[trial_id])
            days_ago = random.randint(5, 150)
            has_return = random.random() < 0.2
            compliance = round(random.uniform(70.0, 100.0), 1)

            da = DrugAssignment(
                id=f"DA-{i + 1:04d}",
                transaction_id=f"IRT-{(i % 50) + 1:04d}",
                patient_id=patient_id,
                treatment_arm=arm,
                kit_number=f"KIT-{random.randint(10000, 99999)}",
                lot_number=random.choice(lot_numbers),
                dispensed_date=now - timedelta(days=days_ago),
                return_date=(now - timedelta(days=days_ago - 30)) if has_return else None,
                compliance_pct=compliance,
            )
            self._drug_assignments[da.id] = da

        # --- Drug Kits (inventory) ---
        kit_counter = 0
        statuses_pool = [
            DrugSupplyStatus.AVAILABLE,
            DrugSupplyStatus.AVAILABLE,
            DrugSupplyStatus.AVAILABLE,
            DrugSupplyStatus.ASSIGNED,
            DrugSupplyStatus.DISPENSED,
            DrugSupplyStatus.DISPENSED,
            DrugSupplyStatus.RETURNED,
            DrugSupplyStatus.DESTROYED,
            DrugSupplyStatus.EXPIRED,
        ]
        for site_id in SITE_IDS:
            for trial_id in [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL]:
                num_kits = random.randint(5, 15)
                for _ in range(num_kits):
                    kit_counter += 1
                    status = random.choice(statuses_pool)
                    assigned_patient = None
                    if status in (DrugSupplyStatus.ASSIGNED, DrugSupplyStatus.DISPENSED):
                        assigned_patient = random.choice(patient_ids[:30])

                    kit = DrugKit(
                        kit_number=f"KIT-{kit_counter:05d}",
                        lot_number=random.choice(lot_numbers),
                        site_id=site_id,
                        trial_id=trial_id,
                        status=status,
                        assigned_patient=assigned_patient,
                        expiry_date=now + timedelta(days=random.randint(90, 730)),
                        created_at=now - timedelta(days=random.randint(30, 365)),
                    )
                    self._drug_kits[kit.kit_number] = kit

        # --- 40 Visit Schedules ---
        visit_names = [
            "Screening", "Baseline", "Week 2", "Week 4", "Week 8",
            "Week 12", "Week 16", "Week 24",
        ]
        vs_counter = 0
        for i in range(40):
            vs_counter += 1
            patient_id = patient_ids[i % len(patient_ids)]
            trial_id = [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL][i % 3]
            visit_num = (i % len(visit_names)) + 1
            visit_name = visit_names[i % len(visit_names)]

            # Calculate visit windows
            base_day = visit_num * 28  # ~4 weeks per visit
            scheduled = now - timedelta(days=180) + timedelta(days=base_day)
            window_open = scheduled - timedelta(days=4)
            window_close = scheduled + timedelta(days=4)

            # Determine if visit happened and window status
            has_actual = random.random() < 0.75  # 75% of visits completed
            if has_actual:
                offset_days = random.randint(-6, 6)
                actual = scheduled + timedelta(days=offset_days)
                if actual < window_open:
                    window_status = VisitWindow.EARLY
                elif actual > window_close:
                    window_status = VisitWindow.LATE
                else:
                    window_status = VisitWindow.ON_TIME
            else:
                actual = None
                if now > window_close:
                    window_status = VisitWindow.MISSED
                else:
                    window_status = VisitWindow.ON_TIME  # Still within future window

            vs = VisitSchedule(
                id=f"VS-{vs_counter:04d}",
                patient_id=patient_id,
                trial_id=trial_id,
                visit_number=visit_num,
                visit_name=visit_name,
                window_open=window_open,
                window_close=window_close,
                scheduled_date=scheduled,
                actual_date=actual,
                window_status=window_status,
            )
            self._visit_schedules[vs.id] = vs

        # --- Stratification Entries ---
        age_groups = ["18-40", "41-60", "61-75", ">75"]
        severities = ["mild", "moderate", "severe"]
        prior_therapies = ["naive", "one_prior", "two_or_more_prior"]
        regions = ["north_america", "europe", "asia_pacific", "latin_america"]

        for i, patient_id in enumerate(patient_ids[:30]):
            factors = {
                StratificationFactor.AGE_GROUP.value: random.choice(age_groups),
                StratificationFactor.SEX.value: random.choice(["male", "female"]),
                StratificationFactor.DISEASE_SEVERITY.value: random.choice(severities),
                StratificationFactor.PRIOR_THERAPY.value: random.choice(prior_therapies),
                StratificationFactor.GEOGRAPHIC_REGION.value: random.choice(regions),
            }
            stratum_id = f"STR-{hash(frozenset(factors.items())) % 10000:04d}"
            entry = StratificationEntry(
                patient_id=patient_id,
                factors=factors,
                stratum_id=stratum_id,
            )
            self._stratification_entries[patient_id] = entry

    # ------------------------------------------------------------------
    # IRT Transactions
    # ------------------------------------------------------------------

    def list_transactions(
        self,
        *,
        trial_id: str | None = None,
        site_id: str | None = None,
        patient_id: str | None = None,
        transaction_type: IRTTransactionType | None = None,
    ) -> list[IRTTransaction]:
        """List IRT transactions with optional filters."""
        with self._lock:
            result = list(self._transactions.values())

        if trial_id is not None:
            result = [t for t in result if t.trial_id == trial_id]
        if site_id is not None:
            result = [t for t in result if t.site_id == site_id]
        if patient_id is not None:
            result = [t for t in result if t.patient_id == patient_id]
        if transaction_type is not None:
            result = [t for t in result if t.transaction_type == transaction_type]

        return sorted(result, key=lambda t: t.timestamp, reverse=True)

    def get_transaction(self, transaction_id: str) -> IRTTransaction | None:
        """Get a single transaction by ID."""
        with self._lock:
            return self._transactions.get(transaction_id)

    def create_transaction(self, payload: IRTTransactionCreate) -> IRTTransaction:
        """Create a new IRT transaction."""
        now = datetime.now(timezone.utc)
        tx_id = f"IRT-{uuid4().hex[:8].upper()}"
        confirmation = f"CNF-{uuid4().hex[:8].upper()}"

        response_map = {
            IRTTransactionType.SCREENING: "Screening number assigned. Proceed with eligibility assessment.",
            IRTTransactionType.RANDOMIZATION: "Patient randomized successfully. Treatment arm assigned.",
            IRTTransactionType.DRUG_ASSIGNMENT: "Drug kit assigned. Accountability updated.",
            IRTTransactionType.DRUG_RESUPPLY: "Resupply order placed. Estimated delivery in 5 business days.",
            IRTTransactionType.VISIT_CONFIRMATION: "Visit confirmed within protocol window.",
            IRTTransactionType.UNBLINDING: "Treatment assignment revealed. Safety review initiated.",
            IRTTransactionType.DOSE_MODIFICATION: "Dose modification recorded. New dispensing instructions issued.",
            IRTTransactionType.DISCONTINUATION: "Patient discontinued. Final assessments and drug return required.",
        }

        tx = IRTTransaction(
            id=tx_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            patient_id=payload.patient_id,
            transaction_type=payload.transaction_type,
            timestamp=now,
            details=payload.details,
            performed_by=payload.performed_by,
            system_response=response_map.get(
                payload.transaction_type, "Transaction processed successfully."
            ),
            confirmation_number=confirmation,
        )

        with self._lock:
            self._transactions[tx_id] = tx

        logger.info(
            "Created IRT transaction %s: type=%s patient=%s",
            tx_id, payload.transaction_type.value, payload.patient_id,
        )
        return tx

    # ------------------------------------------------------------------
    # Drug Assignments
    # ------------------------------------------------------------------

    def list_drug_assignments(
        self,
        *,
        patient_id: str | None = None,
        treatment_arm: str | None = None,
    ) -> list[DrugAssignment]:
        """List drug assignments with optional filters."""
        with self._lock:
            result = list(self._drug_assignments.values())

        if patient_id is not None:
            result = [d for d in result if d.patient_id == patient_id]
        if treatment_arm is not None:
            result = [d for d in result if d.treatment_arm == treatment_arm]

        return sorted(result, key=lambda d: d.dispensed_date, reverse=True)

    def get_drug_assignment(self, assignment_id: str) -> DrugAssignment | None:
        """Get a single drug assignment by ID."""
        with self._lock:
            return self._drug_assignments.get(assignment_id)

    def create_drug_assignment(self, payload: DrugAssignmentCreate) -> DrugAssignment:
        """Create a new drug assignment with an associated transaction."""
        now = datetime.now(timezone.utc)
        da_id = f"DA-{uuid4().hex[:8].upper()}"
        tx_id = f"IRT-{uuid4().hex[:8].upper()}"

        # Create associated transaction
        tx = IRTTransaction(
            id=tx_id,
            trial_id=EYLEA_TRIAL,  # Default, can be improved
            site_id="SITE-101",
            patient_id=payload.patient_id,
            transaction_type=IRTTransactionType.DRUG_ASSIGNMENT,
            timestamp=now,
            details=f"Drug kit {payload.kit_number} assigned to {payload.patient_id}",
            performed_by="system",
            system_response="Drug kit assigned. Accountability updated.",
            confirmation_number=f"CNF-{uuid4().hex[:8].upper()}",
        )

        da = DrugAssignment(
            id=da_id,
            transaction_id=tx_id,
            patient_id=payload.patient_id,
            treatment_arm=payload.treatment_arm,
            kit_number=payload.kit_number,
            lot_number=payload.lot_number,
            dispensed_date=now,
            return_date=None,
            compliance_pct=100.0,
        )

        with self._lock:
            self._transactions[tx_id] = tx
            self._drug_assignments[da_id] = da

        logger.info(
            "Created drug assignment %s: patient=%s kit=%s",
            da_id, payload.patient_id, payload.kit_number,
        )
        return da

    def update_drug_assignment(
        self, assignment_id: str, payload: DrugAssignmentUpdate
    ) -> DrugAssignment | None:
        """Update a drug assignment (e.g., return date, compliance)."""
        with self._lock:
            existing = self._drug_assignments.get(assignment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DrugAssignment(**data)
            self._drug_assignments[assignment_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Drug Kits & Accountability
    # ------------------------------------------------------------------

    def list_drug_kits(
        self,
        *,
        site_id: str | None = None,
        trial_id: str | None = None,
        status: DrugSupplyStatus | None = None,
    ) -> list[DrugKit]:
        """List drug kits with optional filters."""
        with self._lock:
            result = list(self._drug_kits.values())

        if site_id is not None:
            result = [k for k in result if k.site_id == site_id]
        if trial_id is not None:
            result = [k for k in result if k.trial_id == trial_id]
        if status is not None:
            result = [k for k in result if k.status == status]

        return sorted(result, key=lambda k: k.kit_number)

    def get_drug_kit(self, kit_number: str) -> DrugKit | None:
        """Get a single drug kit by number."""
        with self._lock:
            return self._drug_kits.get(kit_number)

    def get_drug_accountability(self, site_id: str) -> DrugAccountabilitySummary | None:
        """Get drug accountability summary for a site."""
        with self._lock:
            site_kits = [k for k in self._drug_kits.values() if k.site_id == site_id]

        if not site_kits:
            return None

        status_counts = {s: 0 for s in DrugSupplyStatus}
        for kit in site_kits:
            status_counts[kit.status] += 1

        available = status_counts[DrugSupplyStatus.AVAILABLE]
        # Estimate buffer weeks: assume ~2 kits consumed per week
        consumption_rate = 2.0
        buffer_weeks = round(available / max(0.1, consumption_rate), 1)

        # Check configurations for buffer threshold
        buffer_threshold = DEFAULT_BUFFER_WEEKS
        for cfg in self._configurations.values():
            buffer_threshold = cfg.drug_supply_buffer_weeks
            break

        return DrugAccountabilitySummary(
            site_id=site_id,
            total_kits=len(site_kits),
            available=available,
            assigned=status_counts[DrugSupplyStatus.ASSIGNED],
            dispensed=status_counts[DrugSupplyStatus.DISPENSED],
            returned=status_counts[DrugSupplyStatus.RETURNED],
            destroyed=status_counts[DrugSupplyStatus.DESTROYED],
            expired=status_counts[DrugSupplyStatus.EXPIRED],
            buffer_weeks_remaining=buffer_weeks,
            resupply_needed=buffer_weeks < buffer_threshold,
        )

    def request_drug_resupply(self, payload: DrugResupplyRequest) -> IRTTransaction:
        """Process a drug resupply request, creating new kits and a transaction."""
        now = datetime.now(timezone.utc)
        tx_id = f"IRT-{uuid4().hex[:8].upper()}"
        confirmation = f"CNF-{uuid4().hex[:8].upper()}"

        # Create new kits
        with self._lock:
            for i in range(payload.kit_count):
                kit_number = f"KIT-{uuid4().hex[:5].upper()}"
                kit = DrugKit(
                    kit_number=kit_number,
                    lot_number=f"LOT-2026-R{uuid4().hex[:3].upper()}",
                    site_id=payload.site_id,
                    trial_id=payload.trial_id,
                    status=DrugSupplyStatus.AVAILABLE,
                    assigned_patient=None,
                    expiry_date=now + timedelta(days=365),
                    created_at=now,
                )
                self._drug_kits[kit_number] = kit

        tx = IRTTransaction(
            id=tx_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            patient_id="N/A",
            transaction_type=IRTTransactionType.DRUG_RESUPPLY,
            timestamp=now,
            details=f"Resupply of {payload.kit_count} kits to site {payload.site_id}",
            performed_by=payload.performed_by,
            system_response=f"Resupply order of {payload.kit_count} kits placed. Expected delivery in 5 business days.",
            confirmation_number=confirmation,
        )

        with self._lock:
            self._transactions[tx_id] = tx

        logger.info(
            "Drug resupply %s: %d kits to site %s",
            tx_id, payload.kit_count, payload.site_id,
        )
        return tx

    # ------------------------------------------------------------------
    # Visit Schedules
    # ------------------------------------------------------------------

    def list_visit_schedules(
        self,
        *,
        patient_id: str | None = None,
        trial_id: str | None = None,
        window_status: VisitWindow | None = None,
    ) -> list[VisitSchedule]:
        """List visit schedules with optional filters."""
        with self._lock:
            result = list(self._visit_schedules.values())

        if patient_id is not None:
            result = [v for v in result if v.patient_id == patient_id]
        if trial_id is not None:
            result = [v for v in result if v.trial_id == trial_id]
        if window_status is not None:
            result = [v for v in result if v.window_status == window_status]

        return sorted(result, key=lambda v: (v.patient_id, v.visit_number))

    def get_visit_schedule(self, schedule_id: str) -> VisitSchedule | None:
        """Get a single visit schedule by ID."""
        with self._lock:
            return self._visit_schedules.get(schedule_id)

    def create_visit_schedule(self, payload: VisitScheduleCreate) -> VisitSchedule:
        """Create a new visit schedule entry."""
        vs_id = f"VS-{uuid4().hex[:8].upper()}"

        vs = VisitSchedule(
            id=vs_id,
            patient_id=payload.patient_id,
            trial_id=payload.trial_id,
            visit_number=payload.visit_number,
            visit_name=payload.visit_name,
            window_open=payload.window_open,
            window_close=payload.window_close,
            scheduled_date=payload.scheduled_date,
            actual_date=None,
            window_status=VisitWindow.ON_TIME,
        )

        with self._lock:
            self._visit_schedules[vs_id] = vs

        logger.info(
            "Created visit schedule %s: patient=%s visit=%s",
            vs_id, payload.patient_id, payload.visit_name,
        )
        return vs

    def confirm_visit(self, schedule_id: str, payload: VisitConfirmation) -> VisitSchedule | None:
        """Confirm a visit occurred and calculate window compliance."""
        with self._lock:
            existing = self._visit_schedules.get(schedule_id)
            if existing is None:
                return None

            if existing.actual_date is not None:
                raise ValueError(f"Visit '{schedule_id}' already confirmed")

            # Calculate window status
            actual = payload.actual_date
            if actual < existing.window_open:
                window_status = VisitWindow.EARLY
            elif actual > existing.window_close:
                window_status = VisitWindow.LATE
            else:
                window_status = VisitWindow.ON_TIME

            data = existing.model_dump()
            data["actual_date"] = actual
            data["window_status"] = window_status
            updated = VisitSchedule(**data)
            self._visit_schedules[schedule_id] = updated

        # Create an associated transaction
        tx_id = f"IRT-{uuid4().hex[:8].upper()}"
        tx = IRTTransaction(
            id=tx_id,
            trial_id=existing.trial_id,
            site_id="SITE-101",  # Default
            patient_id=existing.patient_id,
            transaction_type=IRTTransactionType.VISIT_CONFIRMATION,
            timestamp=datetime.now(timezone.utc),
            details=f"Visit {existing.visit_name} confirmed for {existing.patient_id}. Window status: {window_status.value}",
            performed_by=payload.performed_by,
            system_response=f"Visit confirmed. Window status: {window_status.value}.",
            confirmation_number=f"CNF-{uuid4().hex[:8].upper()}",
        )

        with self._lock:
            self._transactions[tx_id] = tx

        logger.info(
            "Confirmed visit %s: patient=%s status=%s",
            schedule_id, existing.patient_id, window_status.value,
        )
        return updated

    # ------------------------------------------------------------------
    # Dose Modification
    # ------------------------------------------------------------------

    def request_dose_modification(self, payload: DoseModificationRequest) -> IRTTransaction:
        """Process a dose modification request."""
        now = datetime.now(timezone.utc)
        tx_id = f"IRT-{uuid4().hex[:8].upper()}"

        tx = IRTTransaction(
            id=tx_id,
            trial_id=payload.trial_id,
            site_id="SITE-101",
            patient_id=payload.patient_id,
            transaction_type=IRTTransactionType.DOSE_MODIFICATION,
            timestamp=now,
            details=f"Dose modification: {payload.current_dose} -> {payload.new_dose}. Reason: {payload.reason}",
            performed_by=payload.performed_by,
            system_response=f"Dose modified from {payload.current_dose} to {payload.new_dose}. New dispensing instructions issued.",
            confirmation_number=f"CNF-{uuid4().hex[:8].upper()}",
        )

        with self._lock:
            self._transactions[tx_id] = tx

        logger.info(
            "Dose modification %s: patient=%s from=%s to=%s",
            tx_id, payload.patient_id, payload.current_dose, payload.new_dose,
        )
        return tx

    # ------------------------------------------------------------------
    # Unblinding
    # ------------------------------------------------------------------

    def request_unblinding(self, payload: UnblindingRequest) -> IRTTransaction:
        """Process an emergency unblinding request."""
        now = datetime.now(timezone.utc)
        tx_id = f"IRT-{uuid4().hex[:8].upper()}"

        # Look up the patient's treatment arm
        patient_assignments = [
            da for da in self._drug_assignments.values()
            if da.patient_id == payload.patient_id
        ]

        treatment_info = "Treatment arm information unavailable"
        if patient_assignments:
            latest = sorted(patient_assignments, key=lambda d: d.dispensed_date, reverse=True)[0]
            treatment_info = f"Patient assigned to: {latest.treatment_arm}"

        tx = IRTTransaction(
            id=tx_id,
            trial_id=payload.trial_id,
            site_id="SITE-101",
            patient_id=payload.patient_id,
            transaction_type=IRTTransactionType.UNBLINDING,
            timestamp=now,
            details=f"Emergency unblinding for {payload.patient_id}. Reason: {payload.reason}",
            performed_by=payload.performed_by,
            system_response=f"Unblinding complete. {treatment_info}. Safety review initiated.",
            confirmation_number=f"CNF-{uuid4().hex[:8].upper()}",
        )

        with self._lock:
            self._transactions[tx_id] = tx

        logger.info(
            "Unblinding %s: patient=%s reason=%s",
            tx_id, payload.patient_id, payload.reason,
        )
        return tx

    # ------------------------------------------------------------------
    # Stratification
    # ------------------------------------------------------------------

    def list_stratification_entries(
        self,
        *,
        stratum_id: str | None = None,
    ) -> list[StratificationEntry]:
        """List stratification entries with optional stratum filter."""
        with self._lock:
            result = list(self._stratification_entries.values())

        if stratum_id is not None:
            result = [e for e in result if e.stratum_id == stratum_id]

        return sorted(result, key=lambda e: e.patient_id)

    def get_stratification_entry(self, patient_id: str) -> StratificationEntry | None:
        """Get stratification entry for a patient."""
        with self._lock:
            return self._stratification_entries.get(patient_id)

    def create_stratification_entry(
        self, payload: StratificationEntryCreate
    ) -> StratificationEntry:
        """Create a stratification entry for a patient."""
        stratum_id = f"STR-{hash(frozenset(payload.factors.items())) % 10000:04d}"

        entry = StratificationEntry(
            patient_id=payload.patient_id,
            factors=payload.factors,
            stratum_id=stratum_id,
        )

        with self._lock:
            self._stratification_entries[payload.patient_id] = entry

        logger.info(
            "Created stratification entry for %s: stratum=%s",
            payload.patient_id, stratum_id,
        )
        return entry

    # ------------------------------------------------------------------
    # IRT Configurations
    # ------------------------------------------------------------------

    def list_configurations(self) -> list[IRTConfiguration]:
        """List all IRT configurations."""
        with self._lock:
            return sorted(
                self._configurations.values(),
                key=lambda c: c.trial_id,
            )

    def get_configuration(self, trial_id: str) -> IRTConfiguration | None:
        """Get IRT configuration for a trial."""
        with self._lock:
            return self._configurations.get(trial_id)

    def update_configuration(
        self, trial_id: str, payload: IRTConfigurationUpdate
    ) -> IRTConfiguration | None:
        """Update IRT configuration for a trial."""
        with self._lock:
            existing = self._configurations.get(trial_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = IRTConfiguration(**data)
            self._configurations[trial_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Patient Compliance
    # ------------------------------------------------------------------

    def get_patient_compliance(self, patient_id: str) -> dict:
        """Get compliance summary for a patient."""
        with self._lock:
            assignments = [
                da for da in self._drug_assignments.values()
                if da.patient_id == patient_id
            ]
            visits = [
                vs for vs in self._visit_schedules.values()
                if vs.patient_id == patient_id
            ]

        if not assignments and not visits:
            return {
                "patient_id": patient_id,
                "drug_assignments": 0,
                "avg_drug_compliance_pct": 0.0,
                "total_visits": 0,
                "completed_visits": 0,
                "visit_compliance_rate": 0.0,
                "on_time_visits": 0,
                "late_visits": 0,
                "early_visits": 0,
                "missed_visits": 0,
            }

        # Drug compliance
        avg_compliance = 0.0
        if assignments:
            avg_compliance = round(
                sum(da.compliance_pct for da in assignments) / len(assignments), 1
            )

        # Visit compliance
        completed = [v for v in visits if v.actual_date is not None]
        on_time = sum(1 for v in visits if v.window_status == VisitWindow.ON_TIME and v.actual_date is not None)
        late = sum(1 for v in visits if v.window_status == VisitWindow.LATE)
        early = sum(1 for v in visits if v.window_status == VisitWindow.EARLY)
        missed = sum(1 for v in visits if v.window_status == VisitWindow.MISSED)
        visit_compliance = 0.0
        if visits:
            visit_compliance = round(on_time / max(1, len(completed)) * 100, 1)

        return {
            "patient_id": patient_id,
            "drug_assignments": len(assignments),
            "avg_drug_compliance_pct": avg_compliance,
            "total_visits": len(visits),
            "completed_visits": len(completed),
            "visit_compliance_rate": visit_compliance,
            "on_time_visits": on_time,
            "late_visits": late,
            "early_visits": early,
            "missed_visits": missed,
        }

    # ------------------------------------------------------------------
    # Sites needing resupply
    # ------------------------------------------------------------------

    def get_sites_needing_resupply(self) -> list[DrugAccountabilitySummary]:
        """Get list of sites where drug supply is below buffer threshold."""
        summaries = []
        for site_id in SITE_IDS:
            summary = self.get_drug_accountability(site_id)
            if summary is not None and summary.resupply_needed:
                summaries.append(summary)
        return sorted(summaries, key=lambda s: s.buffer_weeks_remaining)

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self) -> IRTMetrics:
        """Compute aggregated IRT operational metrics."""
        now = datetime.now(timezone.utc)

        with self._lock:
            transactions = list(self._transactions.values())
            assignments = list(self._drug_assignments.values())
            visits = list(self._visit_schedules.values())
            kits = list(self._drug_kits.values())

        # Transactions by type
        by_type: dict[str, int] = {}
        for tx in transactions:
            key = tx.transaction_type.value
            by_type[key] = by_type.get(key, 0) + 1

        # Active patients (have transactions but no discontinuation as their latest)
        patient_latest: dict[str, IRTTransaction] = {}
        for tx in sorted(transactions, key=lambda t: t.timestamp):
            patient_latest[tx.patient_id] = tx
        active_patients = sum(
            1 for tx in patient_latest.values()
            if tx.transaction_type != IRTTransactionType.DISCONTINUATION
            and tx.patient_id != "N/A"
        )

        # Drug kits
        available_kits = sum(1 for k in kits if k.status == DrugSupplyStatus.AVAILABLE)
        dispensed_kits = sum(1 for k in kits if k.status == DrugSupplyStatus.DISPENSED)

        # Visit compliance
        completed_visits = [v for v in visits if v.actual_date is not None]
        on_time = sum(1 for v in completed_visits if v.window_status == VisitWindow.ON_TIME)
        visit_compliance = round(on_time / max(1, len(completed_visits)) * 100, 1)

        # Drug compliance
        avg_drug_compliance = 0.0
        if assignments:
            avg_drug_compliance = round(
                sum(da.compliance_pct for da in assignments) / len(assignments), 1
            )

        # Missed visits in last 30 days
        cutoff = now - timedelta(days=30)
        missed_30d = sum(
            1 for v in visits
            if v.window_status == VisitWindow.MISSED
            and v.window_close >= cutoff
        )

        return IRTMetrics(
            total_transactions=len(transactions),
            transactions_by_type=by_type,
            active_patients=active_patients,
            drug_kits_available=available_kits,
            drug_kits_dispensed=dispensed_kits,
            visit_compliance_rate=visit_compliance,
            avg_drug_compliance_pct=avg_drug_compliance,
            missed_visits_30d=missed_30d,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: IRTService | None = None
_instance_lock = threading.Lock()


def get_irt_service() -> IRTService:
    """Return the singleton IRTService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = IRTService()
    return _instance


def reset_irt_service() -> IRTService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = IRTService()
    return _instance
