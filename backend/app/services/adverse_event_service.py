"""Adverse Event Monitoring & Safety Reporting Service (CMO-9).

Manages adverse events across clinical trials, performs statistical safety
signal detection, tracks expedited regulatory reporting obligations, and
provides safety dashboard metrics.

Usage:
    from app.services.adverse_event_service import (
        get_adverse_event_service,
    )

    svc = get_adverse_event_service()
    ae = svc.report_event(...)
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import math
import threading
from collections import Counter
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.adverse_events import (
    AdverseEvent,
    AEActionTaken,
    AECategory,
    AECreate,
    AEMetrics,
    AEOutcome,
    AERelatedness,
    AESeverity,
    AEStatus,
    AEUpdate,
    CausalityAssessment,
    CausalityFactor,
    ExpeditedReport,
    ExpeditedReportStatus,
    ExpeditedReportType,
    MostCommonEvent,
    NarrativeReport,
    SafetySignal,
    SafetySignalStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regulatory timeline constants
# ---------------------------------------------------------------------------

# FDA IND Safety Report: 15 calendar days for serious + unexpected
EXPEDITED_REPORT_DAYS = 15
# Fatal / life-threatening: 7 calendar days
EXPEDITED_REPORT_DAYS_FATAL = 7

# ---------------------------------------------------------------------------
# Valid status transitions
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: dict[AEStatus, set[AEStatus]] = {
    AEStatus.REPORTED: {AEStatus.UNDER_INVESTIGATION, AEStatus.CONFIRMED, AEStatus.CLOSED},
    AEStatus.UNDER_INVESTIGATION: {AEStatus.CONFIRMED, AEStatus.RESOLVED, AEStatus.CLOSED},
    AEStatus.CONFIRMED: {AEStatus.RESOLVED, AEStatus.CLOSED},
    AEStatus.RESOLVED: {AEStatus.CLOSED},
    AEStatus.CLOSED: set(),  # terminal
}

# ---------------------------------------------------------------------------
# Expected background rates (per 100 patients) for signal detection
# ---------------------------------------------------------------------------

EXPECTED_RATES: dict[str, float] = {
    "Headache": 8.0,
    "Nausea": 5.0,
    "Injection site reaction": 10.0,
    "Fatigue": 6.0,
    "Elevated ALT": 2.0,
    "Rash": 3.0,
    "Arthralgia": 4.0,
    "Diarrhea": 4.5,
    "Hypertension": 3.0,
    "Neutropenia": 1.5,
    "Conjunctivitis": 2.0,
    "Nasopharyngitis": 7.0,
    "Peripheral neuropathy": 1.0,
    "Pneumonitis": 0.5,
    "Anaphylaxis": 0.1,
}


class AdverseEventService:
    """In-memory adverse event management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._events: dict[str, AdverseEvent] = {}
        self._signals: dict[str, SafetySignal] = {}
        self._expedited_reports: dict[str, ExpeditedReport] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic adverse events across the 3 Regeneron trials."""
        now = datetime.now(timezone.utc)

        # Stable trial IDs matching trial_eligibility_service
        eylea_id = "00000000-de00-0001-0000-000000000001"
        dupixent_id = "00000000-de00-0002-0000-000000000002"
        libtayo_id = "00000000-de00-0003-0000-000000000003"

        seed_events: list[dict] = [
            # --- EYLEA (Aflibercept) - Ophthalmology ---
            {
                "trial_id": eylea_id,
                "patient_id": "PAT-DME-003",
                "site_id": "SITE-101",
                "event_term": "Conjunctival hemorrhage",
                "preferred_term": "Conjunctivitis",
                "category": AECategory.OPHTHALMIC,
                "severity": AESeverity.MILD,
                "relatedness": AERelatedness.PROBABLE,
                "serious": False,
                "expected": True,
                "status": AEStatus.RESOLVED,
                "onset_date": now - timedelta(days=60),
                "resolution_date": now - timedelta(days=53),
                "reporter": "Dr. Sarah Chen",
                "description": "Mild conjunctival hemorrhage at injection site following intravitreal aflibercept injection. Self-limited, resolved within 7 days.",
                "action_taken": AEActionTaken.NONE,
                "outcome": AEOutcome.RECOVERED,
            },
            {
                "trial_id": eylea_id,
                "patient_id": "PAT-DME-007",
                "site_id": "SITE-102",
                "event_term": "Increased intraocular pressure",
                "preferred_term": "Intraocular pressure increased",
                "category": AECategory.OPHTHALMIC,
                "severity": AESeverity.MODERATE,
                "relatedness": AERelatedness.PROBABLE,
                "serious": False,
                "expected": True,
                "status": AEStatus.RESOLVED,
                "onset_date": now - timedelta(days=40),
                "resolution_date": now - timedelta(days=39),
                "reporter": "Dr. Michael Torres",
                "description": "Transient elevation of IOP to 28 mmHg post-injection. Returned to baseline within 30 minutes with topical timolol.",
                "action_taken": AEActionTaken.NONE,
                "outcome": AEOutcome.RECOVERED,
            },
            {
                "trial_id": eylea_id,
                "patient_id": "PAT-DME-012",
                "site_id": "SITE-101",
                "event_term": "Endophthalmitis",
                "preferred_term": "Endophthalmitis",
                "category": AECategory.OPHTHALMIC,
                "severity": AESeverity.SEVERE,
                "relatedness": AERelatedness.POSSIBLE,
                "serious": True,
                "expected": False,
                "status": AEStatus.CONFIRMED,
                "onset_date": now - timedelta(days=12),
                "reporter": "Dr. Sarah Chen",
                "description": "Suspected endophthalmitis 3 days post-injection. Vitreous tap and intravitreal antibiotics administered. Culture results pending.",
                "action_taken": AEActionTaken.DOSE_INTERRUPTED,
                "outcome": AEOutcome.RECOVERING,
            },
            {
                "trial_id": eylea_id,
                "patient_id": "PAT-DME-019",
                "site_id": "SITE-103",
                "event_term": "Headache",
                "preferred_term": "Headache",
                "category": AECategory.NEUROLOGICAL,
                "severity": AESeverity.MILD,
                "relatedness": AERelatedness.UNLIKELY,
                "serious": False,
                "expected": True,
                "status": AEStatus.RESOLVED,
                "onset_date": now - timedelta(days=25),
                "resolution_date": now - timedelta(days=24),
                "reporter": "Study Coordinator Maria Santos",
                "description": "Mild headache following clinic visit. Resolved with over-the-counter analgesic.",
                "action_taken": AEActionTaken.NONE,
                "outcome": AEOutcome.RECOVERED,
            },
            # --- DUPIXENT (Dupilumab) - Dermatology/Immunology ---
            {
                "trial_id": dupixent_id,
                "patient_id": "PAT-AD-007",
                "site_id": "SITE-205",
                "event_term": "Injection site reaction",
                "preferred_term": "Injection site reaction",
                "category": AECategory.DERMATOLOGICAL,
                "severity": AESeverity.MILD,
                "relatedness": AERelatedness.DEFINITE,
                "serious": False,
                "expected": True,
                "status": AEStatus.RESOLVED,
                "onset_date": now - timedelta(days=50),
                "resolution_date": now - timedelta(days=47),
                "reporter": "Nurse Coordinator Lisa Park",
                "description": "Erythema and mild swelling at injection site. Resolved spontaneously within 3 days.",
                "action_taken": AEActionTaken.NONE,
                "outcome": AEOutcome.RECOVERED,
            },
            {
                "trial_id": dupixent_id,
                "patient_id": "PAT-AD-015",
                "site_id": "SITE-206",
                "event_term": "Conjunctivitis",
                "preferred_term": "Conjunctivitis",
                "category": AECategory.OPHTHALMIC,
                "severity": AESeverity.MODERATE,
                "relatedness": AERelatedness.PROBABLE,
                "serious": False,
                "expected": True,
                "status": AEStatus.UNDER_INVESTIGATION,
                "onset_date": now - timedelta(days=18),
                "reporter": "Dr. James Liu",
                "description": "Bilateral conjunctivitis developing 6 weeks after starting dupilumab. Known class effect. Ophthalmology referral initiated.",
                "action_taken": AEActionTaken.NONE,
                "outcome": AEOutcome.NOT_RECOVERED,
            },
            {
                "trial_id": dupixent_id,
                "patient_id": "PAT-AD-021",
                "site_id": "SITE-207",
                "event_term": "Anaphylaxis",
                "preferred_term": "Anaphylaxis",
                "category": AECategory.IMMUNOLOGICAL,
                "severity": AESeverity.LIFE_THREATENING,
                "relatedness": AERelatedness.PROBABLE,
                "serious": True,
                "expected": False,
                "status": AEStatus.CONFIRMED,
                "onset_date": now - timedelta(days=8),
                "reporter": "Dr. Angela Martinez",
                "description": "Anaphylactic reaction within 15 minutes of dupilumab injection. Epinephrine administered, patient stabilized. Admitted for 24-hour observation.",
                "action_taken": AEActionTaken.DISCONTINUED,
                "outcome": AEOutcome.RECOVERED,
            },
            {
                "trial_id": dupixent_id,
                "patient_id": "PAT-AD-028",
                "site_id": "SITE-205",
                "event_term": "Nasopharyngitis",
                "preferred_term": "Nasopharyngitis",
                "category": AECategory.RESPIRATORY,
                "severity": AESeverity.MILD,
                "relatedness": AERelatedness.UNLIKELY,
                "serious": False,
                "expected": True,
                "status": AEStatus.RESOLVED,
                "onset_date": now - timedelta(days=30),
                "resolution_date": now - timedelta(days=22),
                "reporter": "Nurse Coordinator Lisa Park",
                "description": "Upper respiratory symptoms consistent with common cold. Resolved spontaneously.",
                "action_taken": AEActionTaken.NONE,
                "outcome": AEOutcome.RECOVERED,
            },
            # --- LIBTAYO (Cemiplimab) - Oncology ---
            {
                "trial_id": libtayo_id,
                "patient_id": "PAT-CSCC-005",
                "site_id": "SITE-310",
                "event_term": "Fatigue",
                "preferred_term": "Fatigue",
                "category": AECategory.GENERAL,
                "severity": AESeverity.MODERATE,
                "relatedness": AERelatedness.POSSIBLE,
                "serious": False,
                "expected": True,
                "status": AEStatus.REPORTED,
                "onset_date": now - timedelta(days=15),
                "reporter": "Dr. Robert Kim",
                "description": "Moderate fatigue developing after cycle 3 of cemiplimab. Impacting daily activities but not requiring hospitalization.",
                "action_taken": AEActionTaken.DOSE_REDUCED,
                "outcome": AEOutcome.NOT_RECOVERED,
            },
            {
                "trial_id": libtayo_id,
                "patient_id": "PAT-CSCC-012",
                "site_id": "SITE-312",
                "event_term": "Elevated ALT",
                "preferred_term": "Elevated ALT",
                "category": AECategory.HEPATIC,
                "severity": AESeverity.MODERATE,
                "relatedness": AERelatedness.POSSIBLE,
                "serious": False,
                "expected": True,
                "status": AEStatus.UNDER_INVESTIGATION,
                "onset_date": now - timedelta(days=10),
                "reporter": "Dr. Jennifer Walsh",
                "description": "ALT elevation to 3x ULN detected on routine labs. AST mildly elevated. Hepatology consult ordered. Possible immune-mediated hepatitis.",
                "action_taken": AEActionTaken.DOSE_INTERRUPTED,
                "outcome": AEOutcome.NOT_RECOVERED,
            },
            {
                "trial_id": libtayo_id,
                "patient_id": "PAT-CSCC-018",
                "site_id": "SITE-310",
                "event_term": "Pneumonitis",
                "preferred_term": "Pneumonitis",
                "category": AECategory.RESPIRATORY,
                "severity": AESeverity.SEVERE,
                "relatedness": AERelatedness.PROBABLE,
                "serious": True,
                "expected": True,
                "status": AEStatus.CONFIRMED,
                "onset_date": now - timedelta(days=5),
                "reporter": "Dr. Robert Kim",
                "description": "Grade 3 immune-mediated pneumonitis. CT showing bilateral ground-glass opacities. High-dose corticosteroids initiated. Treatment discontinued.",
                "action_taken": AEActionTaken.DISCONTINUED,
                "outcome": AEOutcome.RECOVERING,
            },
            {
                "trial_id": libtayo_id,
                "patient_id": "PAT-CSCC-022",
                "site_id": "SITE-312",
                "event_term": "Rash",
                "preferred_term": "Rash",
                "category": AECategory.DERMATOLOGICAL,
                "severity": AESeverity.MILD,
                "relatedness": AERelatedness.PROBABLE,
                "serious": False,
                "expected": True,
                "status": AEStatus.RESOLVED,
                "onset_date": now - timedelta(days=35),
                "resolution_date": now - timedelta(days=21),
                "reporter": "Dr. Jennifer Walsh",
                "description": "Maculopapular rash on trunk, Grade 1. Managed with topical corticosteroids. Resolved after 2 weeks.",
                "action_taken": AEActionTaken.NONE,
                "outcome": AEOutcome.RECOVERED,
            },
            {
                "trial_id": libtayo_id,
                "patient_id": "PAT-CSCC-025",
                "site_id": "SITE-310",
                "event_term": "Neutropenia",
                "preferred_term": "Neutropenia",
                "category": AECategory.HEMATOLOGICAL,
                "severity": AESeverity.SEVERE,
                "relatedness": AERelatedness.POSSIBLE,
                "serious": True,
                "expected": True,
                "status": AEStatus.UNDER_INVESTIGATION,
                "onset_date": now - timedelta(days=3),
                "reporter": "Dr. Robert Kim",
                "description": "Grade 3 neutropenia (ANC 0.8 x 10^9/L) detected on pre-cycle labs. Treatment held. G-CSF support initiated.",
                "action_taken": AEActionTaken.DOSE_INTERRUPTED,
                "outcome": AEOutcome.RECOVERING,
            },
            {
                "trial_id": dupixent_id,
                "patient_id": "PAT-AD-033",
                "site_id": "SITE-207",
                "event_term": "Arthralgia",
                "preferred_term": "Arthralgia",
                "category": AECategory.MUSCULOSKELETAL,
                "severity": AESeverity.MILD,
                "relatedness": AERelatedness.UNLIKELY,
                "serious": False,
                "expected": True,
                "status": AEStatus.RESOLVED,
                "onset_date": now - timedelta(days=45),
                "resolution_date": now - timedelta(days=38),
                "reporter": "Dr. James Liu",
                "description": "Mild bilateral knee pain. Managed with acetaminophen. Not considered related to study drug.",
                "action_taken": AEActionTaken.NONE,
                "outcome": AEOutcome.RECOVERED,
            },
        ]

        for i, data in enumerate(seed_events):
            ae_id = f"AE-{i + 1:04d}"
            reported_date = data["onset_date"] + timedelta(hours=8)

            # Determine expedited reporting requirement
            requires_expedited = data["serious"] and not data["expected"]

            record = AdverseEvent(
                id=ae_id,
                trial_id=data["trial_id"],
                patient_id=data["patient_id"],
                site_id=data["site_id"],
                event_term=data["event_term"],
                preferred_term=data["preferred_term"],
                category=data["category"],
                severity=data["severity"],
                relatedness=data["relatedness"],
                serious=data["serious"],
                expected=data["expected"],
                status=data["status"],
                onset_date=data["onset_date"],
                resolution_date=data.get("resolution_date"),
                reported_date=reported_date,
                reporter=data["reporter"],
                description=data["description"],
                action_taken=data.get("action_taken", AEActionTaken.NONE),
                outcome=data.get("outcome", AEOutcome.UNKNOWN),
                requires_expedited_reporting=requires_expedited,
                expedited_report_date=None,
                created_at=reported_date,
                updated_at=reported_date,
            )
            self._events[ae_id] = record

        # --- Seed safety signals ---
        self._signals["SIG-0001"] = SafetySignal(
            id="SIG-0001",
            signal_term="Anaphylaxis",
            trials_affected=[dupixent_id],
            events_count=1,
            expected_rate=0.1,
            observed_rate=0.8,
            relative_risk=8.0,
            p_value=0.003,
            detected_at=now - timedelta(days=7),
            status=SafetySignalStatus.INVESTIGATING,
            assessed_by="Dr. Safety Officer",
        )
        self._signals["SIG-0002"] = SafetySignal(
            id="SIG-0002",
            signal_term="Pneumonitis",
            trials_affected=[libtayo_id],
            events_count=1,
            expected_rate=0.5,
            observed_rate=1.8,
            relative_risk=3.6,
            p_value=0.012,
            detected_at=now - timedelta(days=4),
            status=SafetySignalStatus.NEW,
            assessed_by=None,
        )
        self._signals["SIG-0003"] = SafetySignal(
            id="SIG-0003",
            signal_term="Conjunctivitis",
            trials_affected=[dupixent_id],
            events_count=1,
            expected_rate=2.0,
            observed_rate=5.5,
            relative_risk=2.75,
            p_value=0.025,
            detected_at=now - timedelta(days=20),
            status=SafetySignalStatus.CONFIRMED,
            assessed_by="Dr. Safety Officer",
        )

        # --- Seed expedited reports ---
        # Endophthalmitis in EYLEA (serious + unexpected)
        self._expedited_reports["EXP-0001"] = ExpeditedReport(
            id="EXP-0001",
            ae_id="AE-0003",
            report_type=ExpeditedReportType.IND_SAFETY,
            regulatory_body="FDA",
            due_date=now - timedelta(days=12) + timedelta(days=EXPEDITED_REPORT_DAYS),
            submitted_date=now - timedelta(days=8),
            status=ExpeditedReportStatus.SUBMITTED,
        )
        # Anaphylaxis in DUPIXENT (serious + unexpected + life-threatening)
        self._expedited_reports["EXP-0002"] = ExpeditedReport(
            id="EXP-0002",
            ae_id="AE-0007",
            report_type=ExpeditedReportType.SUSAR,
            regulatory_body="FDA",
            due_date=now - timedelta(days=8) + timedelta(days=EXPEDITED_REPORT_DAYS_FATAL),
            submitted_date=None,
            status=ExpeditedReportStatus.PENDING,
        )
        self._expedited_reports["EXP-0003"] = ExpeditedReport(
            id="EXP-0003",
            ae_id="AE-0007",
            report_type=ExpeditedReportType.CIOMS,
            regulatory_body="EMA",
            due_date=now - timedelta(days=8) + timedelta(days=EXPEDITED_REPORT_DAYS),
            submitted_date=None,
            status=ExpeditedReportStatus.PENDING,
        )

        logger.info(
            "Adverse event service initialised with %d events, %d signals, %d expedited reports",
            len(self._events),
            len(self._signals),
            len(self._expedited_reports),
        )

    # ------------------------------------------------------------------
    # Report (Create) with auto-expedited detection
    # ------------------------------------------------------------------

    def report_event(self, data: AECreate) -> AdverseEvent:
        """Report a new adverse event.

        Auto-detects expedited reporting requirement:
        - Serious + Unexpected = expedited within 15 days (FDA IND Safety)
        - Fatal / life-threatening = expedited within 7 days
        """
        now = datetime.now(timezone.utc)
        ae_id = f"AE-{uuid4().hex[:8].upper()}"

        # Determine expedited reporting
        requires_expedited = data.serious and not data.expected

        record = AdverseEvent(
            id=ae_id,
            trial_id=data.trial_id,
            patient_id=data.patient_id,
            site_id=data.site_id,
            event_term=data.event_term,
            preferred_term=data.preferred_term,
            category=data.category,
            severity=data.severity,
            relatedness=data.relatedness,
            serious=data.serious,
            expected=data.expected,
            status=AEStatus.REPORTED,
            onset_date=data.onset_date,
            resolution_date=None,
            reported_date=now,
            reporter=data.reporter,
            description=data.description,
            action_taken=data.action_taken,
            outcome=data.outcome,
            requires_expedited_reporting=requires_expedited,
            expedited_report_date=None,
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            self._events[ae_id] = record

        # Auto-create expedited report if required
        if requires_expedited:
            deadline_days = EXPEDITED_REPORT_DAYS
            if data.severity in (AESeverity.FATAL, AESeverity.LIFE_THREATENING):
                deadline_days = EXPEDITED_REPORT_DAYS_FATAL

            exp_id = f"EXP-{uuid4().hex[:8].upper()}"
            exp_report = ExpeditedReport(
                id=exp_id,
                ae_id=ae_id,
                report_type=ExpeditedReportType.IND_SAFETY,
                regulatory_body="FDA",
                due_date=now + timedelta(days=deadline_days),
                submitted_date=None,
                status=ExpeditedReportStatus.PENDING,
            )
            with self._lock:
                self._expedited_reports[exp_id] = exp_report

            logger.info(
                "Created expedited report %s for AE %s (due in %d days)",
                exp_id,
                ae_id,
                deadline_days,
            )

        logger.info(
            "Reported AE %s [%s/%s] for trial %s, patient %s",
            ae_id,
            data.severity.value,
            data.category.value,
            data.trial_id,
            data.patient_id,
        )
        return record

    # ------------------------------------------------------------------
    # Update with status transition validation
    # ------------------------------------------------------------------

    def update_event(self, ae_id: str, data: AEUpdate) -> AdverseEvent:
        """Update an adverse event with status transition validation.

        Raises ``KeyError`` if not found.
        Raises ``ValueError`` for invalid status transitions.
        """
        with self._lock:
            record = self._events.get(ae_id)
            if record is None:
                raise KeyError(f"Adverse event {ae_id} not found")

            # Validate status transition
            if data.status is not None and data.status != record.status:
                allowed = VALID_TRANSITIONS.get(record.status, set())
                if data.status not in allowed:
                    raise ValueError(
                        f"Invalid status transition from {record.status.value} "
                        f"to {data.status.value}. Allowed: "
                        f"{[s.value for s in allowed]}"
                    )

            now = datetime.now(timezone.utc)
            updates: dict = {"updated_at": now}

            if data.status is not None:
                updates["status"] = data.status
            if data.severity is not None:
                updates["severity"] = data.severity
            if data.relatedness is not None:
                updates["relatedness"] = data.relatedness
            if data.serious is not None:
                updates["serious"] = data.serious
                # Recalculate expedited if serious/expected changed
                expected = data.expected if data.expected is not None else record.expected
                updates["requires_expedited_reporting"] = data.serious and not expected
            if data.expected is not None:
                updates["expected"] = data.expected
                serious = data.serious if data.serious is not None else record.serious
                updates["requires_expedited_reporting"] = serious and not data.expected
            if data.resolution_date is not None:
                updates["resolution_date"] = data.resolution_date
            if data.action_taken is not None:
                updates["action_taken"] = data.action_taken
            if data.outcome is not None:
                updates["outcome"] = data.outcome
            if data.description is not None:
                updates["description"] = data.description

            updated = record.model_copy(update=updates)
            self._events[ae_id] = updated

        return updated

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_event(self, ae_id: str) -> AdverseEvent:
        """Retrieve a single adverse event by ID.

        Raises ``KeyError`` if not found.
        """
        record = self._events.get(ae_id)
        if record is None:
            raise KeyError(f"Adverse event {ae_id} not found")
        return record

    def list_events(
        self,
        *,
        trial_id: str | None = None,
        severity: AESeverity | None = None,
        status: AEStatus | None = None,
        category: AECategory | None = None,
        serious: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AdverseEvent], int]:
        """List adverse events with optional filtering and pagination."""
        records = list(self._events.values())

        if trial_id is not None:
            records = [r for r in records if r.trial_id == trial_id]
        if severity is not None:
            records = [r for r in records if r.severity == severity]
        if status is not None:
            records = [r for r in records if r.status == status]
        if category is not None:
            records = [r for r in records if r.category == category]
        if serious is not None:
            records = [r for r in records if r.serious == serious]

        # Sort by reported_date descending
        records.sort(key=lambda r: r.reported_date, reverse=True)

        total = len(records)
        page = records[offset : offset + limit]
        return page, total

    # ------------------------------------------------------------------
    # Safety signal detection
    # ------------------------------------------------------------------

    def detect_safety_signals(self, trial_id: str | None = None) -> list[SafetySignal]:
        """Statistical safety signal detection.

        Compares observed event rates to expected background rates.
        Flags a signal when relative risk > 2.0.

        Returns newly detected or updated signals.
        """
        records = list(self._events.values())
        if trial_id is not None:
            records = [r for r in records if r.trial_id == trial_id]

        if not records:
            return []

        # Count events by preferred term
        term_counts = Counter(r.preferred_term for r in records)

        # Estimate population size (unique patients)
        unique_patients = len({r.patient_id for r in records})
        if unique_patients == 0:
            return []

        # Calculate per 100 patients rate
        population_factor = 100 / max(unique_patients, 1)

        now = datetime.now(timezone.utc)
        detected: list[SafetySignal] = []
        trial_ids_affected = list({r.trial_id for r in records})

        for term, count in term_counts.items():
            expected_rate = EXPECTED_RATES.get(term, 2.0)  # default 2% background
            observed_rate = count * population_factor

            if expected_rate <= 0:
                continue

            relative_risk = observed_rate / expected_rate

            if relative_risk > 2.0:
                # Simple approximate p-value using normal approximation
                # For demo purposes, smaller RR gets higher p-value
                p_value = min(1.0, max(0.001, 0.05 / relative_risk))

                # Check if signal already exists
                existing = None
                for sig in self._signals.values():
                    if sig.signal_term == term:
                        existing = sig
                        break

                if existing is None:
                    sig_id = f"SIG-{uuid4().hex[:6].upper()}"
                    signal = SafetySignal(
                        id=sig_id,
                        signal_term=term,
                        trials_affected=trial_ids_affected,
                        events_count=count,
                        expected_rate=round(expected_rate, 2),
                        observed_rate=round(observed_rate, 2),
                        relative_risk=round(relative_risk, 2),
                        p_value=round(p_value, 4),
                        detected_at=now,
                        status=SafetySignalStatus.NEW,
                        assessed_by=None,
                    )
                    with self._lock:
                        self._signals[sig_id] = signal
                    detected.append(signal)
                else:
                    # Update existing signal counts
                    updated = existing.model_copy(
                        update={
                            "events_count": count,
                            "observed_rate": round(observed_rate, 2),
                            "relative_risk": round(relative_risk, 2),
                            "p_value": round(p_value, 4),
                            "trials_affected": trial_ids_affected,
                        }
                    )
                    with self._lock:
                        self._signals[existing.id] = updated
                    detected.append(updated)

        logger.info(
            "Safety signal detection complete: %d signals detected/updated",
            len(detected),
        )
        return detected

    def list_signals(
        self,
        status: SafetySignalStatus | None = None,
    ) -> list[SafetySignal]:
        """List all safety signals, optionally filtered by status."""
        signals = list(self._signals.values())
        if status is not None:
            signals = [s for s in signals if s.status == status]
        signals.sort(key=lambda s: s.detected_at, reverse=True)
        return signals

    def get_signal(self, signal_id: str) -> SafetySignal:
        """Get a specific safety signal.

        Raises ``KeyError`` if not found.
        """
        signal = self._signals.get(signal_id)
        if signal is None:
            raise KeyError(f"Safety signal {signal_id} not found")
        return signal

    def update_signal_status(
        self, signal_id: str, status: SafetySignalStatus, assessed_by: str | None = None
    ) -> SafetySignal:
        """Update the status of a safety signal.

        Raises ``KeyError`` if not found.
        """
        with self._lock:
            signal = self._signals.get(signal_id)
            if signal is None:
                raise KeyError(f"Safety signal {signal_id} not found")

            updates: dict = {"status": status}
            if assessed_by is not None:
                updates["assessed_by"] = assessed_by

            updated = signal.model_copy(update=updates)
            self._signals[signal_id] = updated

        return updated

    # ------------------------------------------------------------------
    # Expedited reporting
    # ------------------------------------------------------------------

    def get_expedited_reports(
        self,
        status: ExpeditedReportStatus | None = None,
    ) -> list[ExpeditedReport]:
        """List expedited reports, optionally filtered by status."""
        reports = list(self._expedited_reports.values())
        if status is not None:
            reports = [r for r in reports if r.status == status]
        reports.sort(key=lambda r: r.due_date)
        return reports

    def submit_expedited_report(
        self, ae_id: str, report_type: ExpeditedReportType, regulatory_body: str
    ) -> ExpeditedReport:
        """Record submission of an expedited report.

        If a matching pending report exists, marks it as submitted.
        Otherwise creates a new submitted report.

        Raises ``KeyError`` if the AE does not exist.
        """
        # Verify AE exists
        if ae_id not in self._events:
            raise KeyError(f"Adverse event {ae_id} not found")

        now = datetime.now(timezone.utc)

        with self._lock:
            # Look for existing pending report
            for report in self._expedited_reports.values():
                if (
                    report.ae_id == ae_id
                    and report.report_type == report_type
                    and report.regulatory_body == regulatory_body
                    and report.status == ExpeditedReportStatus.PENDING
                ):
                    updated = report.model_copy(
                        update={
                            "submitted_date": now,
                            "status": ExpeditedReportStatus.SUBMITTED,
                        }
                    )
                    self._expedited_reports[report.id] = updated
                    # Also update the AE expedited_report_date
                    ae = self._events.get(ae_id)
                    if ae is not None:
                        self._events[ae_id] = ae.model_copy(
                            update={"expedited_report_date": now, "updated_at": now}
                        )
                    logger.info(
                        "Submitted expedited report %s for AE %s to %s",
                        report.id,
                        ae_id,
                        regulatory_body,
                    )
                    return updated

            # Create new submitted report
            exp_id = f"EXP-{uuid4().hex[:8].upper()}"
            report = ExpeditedReport(
                id=exp_id,
                ae_id=ae_id,
                report_type=report_type,
                regulatory_body=regulatory_body,
                due_date=now,  # already submitted
                submitted_date=now,
                status=ExpeditedReportStatus.SUBMITTED,
            )
            self._expedited_reports[exp_id] = report

            # Update AE
            ae = self._events.get(ae_id)
            if ae is not None:
                self._events[ae_id] = ae.model_copy(
                    update={"expedited_report_date": now, "updated_at": now}
                )

        logger.info(
            "Created and submitted expedited report %s for AE %s to %s",
            exp_id,
            ae_id,
            regulatory_body,
        )
        return report

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> AEMetrics:
        """Compute aggregated safety metrics, optionally filtered by trial."""
        records = list(self._events.values())
        if trial_id is not None:
            records = [r for r in records if r.trial_id == trial_id]

        if not records:
            return AEMetrics(
                total_events=0,
                serious_count=0,
                by_severity={},
                by_category={},
                by_trial={},
                mean_time_to_resolution_days=None,
                expedited_reporting_compliance_rate=1.0,
                active_safety_signals=0,
                most_common_events=[],
            )

        serious_count = sum(1 for r in records if r.serious)
        by_severity = dict(Counter(r.severity.value for r in records))
        by_category = dict(Counter(r.category.value for r in records))
        by_trial = dict(Counter(r.trial_id for r in records))

        # Mean time to resolution
        resolved = [r for r in records if r.resolution_date is not None]
        if resolved:
            days = [
                (r.resolution_date - r.onset_date).total_seconds() / 86400
                for r in resolved
            ]
            mtr = round(sum(days) / len(days), 2)
        else:
            mtr = None

        # Expedited reporting compliance
        requiring_expedited = [r for r in records if r.requires_expedited_reporting]
        if requiring_expedited:
            submitted = sum(
                1 for r in requiring_expedited if r.expedited_report_date is not None
            )
            compliance = round(submitted / len(requiring_expedited), 4)
        else:
            compliance = 1.0

        # Active safety signals
        active_signals = sum(
            1
            for s in self._signals.values()
            if s.status not in (SafetySignalStatus.DISMISSED,)
        )

        # Most common events
        term_counts = Counter(r.preferred_term for r in records)
        most_common = [
            MostCommonEvent(event_term=term, count=count)
            for term, count in term_counts.most_common(10)
        ]

        return AEMetrics(
            total_events=len(records),
            serious_count=serious_count,
            by_severity=by_severity,
            by_category=by_category,
            by_trial=by_trial,
            mean_time_to_resolution_days=mtr,
            expedited_reporting_compliance_rate=compliance,
            active_safety_signals=active_signals,
            most_common_events=most_common,
        )

    # ------------------------------------------------------------------
    # Category analysis
    # ------------------------------------------------------------------

    def get_events_by_category(self, category: AECategory) -> list[AdverseEvent]:
        """Return all adverse events in a specific SOC category."""
        return [
            r for r in self._events.values() if r.category == category
        ]

    # ------------------------------------------------------------------
    # Causality assessment (Naranjo algorithm)
    # ------------------------------------------------------------------

    def assess_causality(self, ae_id: str) -> CausalityAssessment:
        """Run a simplified Naranjo causality assessment for an AE.

        Raises ``KeyError`` if the AE is not found.
        """
        record = self._events.get(ae_id)
        if record is None:
            raise KeyError(f"Adverse event {ae_id} not found")

        factors: list[CausalityFactor] = []

        # Q1: Previous conclusive reports?
        answer = "yes"
        score = 1
        factors.append(CausalityFactor(question="Previous conclusive reports on this reaction?", answer=answer, score=score))

        # Q2: AE appeared after drug was given?
        answer = "yes"
        score = 2
        factors.append(CausalityFactor(question="Event appeared after the suspected drug was given?", answer=answer, score=score))

        # Q3: Did the AE improve when drug was discontinued?
        if record.action_taken in (AEActionTaken.DISCONTINUED, AEActionTaken.DOSE_INTERRUPTED):
            if record.outcome in (AEOutcome.RECOVERED, AEOutcome.RECOVERING):
                answer, score = "yes", 1
            else:
                answer, score = "unknown", 0
        else:
            answer, score = "unknown", 0
        factors.append(CausalityFactor(question="Adverse reaction improved when drug was discontinued?", answer=answer, score=score))

        # Q4: Did the AE reappear on re-administration?
        answer, score = "unknown", 0
        factors.append(CausalityFactor(question="Reaction reappeared on re-administration?", answer=answer, score=score))

        # Q5: Alternative causes?
        if record.relatedness in (AERelatedness.DEFINITE, AERelatedness.PROBABLE):
            answer, score = "no", 2
        elif record.relatedness == AERelatedness.POSSIBLE:
            answer, score = "unknown", 0
        else:
            answer, score = "yes", -1
        factors.append(CausalityFactor(question="Are there alternative causes that could have caused the reaction?", answer=answer, score=score))

        # Q6: Was the drug detected in the blood?
        answer, score = "unknown", 0
        factors.append(CausalityFactor(question="Drug detected in blood in toxic concentrations?", answer=answer, score=score))

        # Q7: Severity related to dose?
        if record.severity in (AESeverity.SEVERE, AESeverity.LIFE_THREATENING, AESeverity.FATAL):
            answer, score = "yes", 1
        else:
            answer, score = "unknown", 0
        factors.append(CausalityFactor(question="Was the reaction more severe when dose was increased?", answer=answer, score=score))

        # Q8: Similar reaction to same or similar drug?
        if record.expected:
            answer, score = "yes", 1
        else:
            answer, score = "unknown", 0
        factors.append(CausalityFactor(question="Patient had similar reaction to same or similar drug before?", answer=answer, score=score))

        # Q9: Objective evidence?
        if record.serious:
            answer, score = "yes", 1
        else:
            answer, score = "unknown", 0
        factors.append(CausalityFactor(question="Was the adverse event confirmed by any objective evidence?", answer=answer, score=score))

        total_score = sum(f.score for f in factors)

        # Naranjo classification
        if total_score >= 9:
            classification = AERelatedness.DEFINITE
        elif total_score >= 5:
            classification = AERelatedness.PROBABLE
        elif total_score >= 1:
            classification = AERelatedness.POSSIBLE
        else:
            classification = AERelatedness.UNLIKELY

        return CausalityAssessment(
            ae_id=ae_id,
            total_score=total_score,
            classification=classification,
            factors=factors,
        )

    # ------------------------------------------------------------------
    # Narrative generation
    # ------------------------------------------------------------------

    def generate_narrative(self, ae_id: str) -> NarrativeReport:
        """Generate a MedWatch-style narrative for an adverse event.

        Raises ``KeyError`` if the AE is not found.
        """
        record = self._events.get(ae_id)
        if record is None:
            raise KeyError(f"Adverse event {ae_id} not found")

        now = datetime.now(timezone.utc)

        serious_text = "serious" if record.serious else "non-serious"
        expected_text = "expected" if record.expected else "unexpected"

        resolution_text = ""
        if record.resolution_date is not None:
            days = (record.resolution_date - record.onset_date).days
            resolution_text = (
                f" The event resolved on {record.resolution_date.strftime('%Y-%m-%d')} "
                f"({days} days after onset)."
            )
        else:
            resolution_text = " The event has not yet resolved."

        action_text = ""
        if record.action_taken != AEActionTaken.NONE:
            action_map = {
                AEActionTaken.DOSE_REDUCED: "dose was reduced",
                AEActionTaken.DOSE_INTERRUPTED: "dosing was interrupted",
                AEActionTaken.DISCONTINUED: "study treatment was permanently discontinued",
                AEActionTaken.OTHER: "other action was taken",
            }
            action_text = f" In response, {action_map.get(record.action_taken, 'action was taken')}."

        expedited_text = ""
        if record.requires_expedited_reporting:
            if record.expedited_report_date is not None:
                expedited_text = (
                    f" Expedited regulatory reporting was completed on "
                    f"{record.expedited_report_date.strftime('%Y-%m-%d')}."
                )
            else:
                expedited_text = " Expedited regulatory reporting is required but has not yet been submitted."

        narrative = (
            f"ADVERSE EVENT NARRATIVE REPORT\n\n"
            f"Patient {record.patient_id} enrolled in trial {record.trial_id} at "
            f"site {record.site_id} experienced a {record.severity.value.lower()} "
            f"{serious_text} adverse event: {record.event_term} "
            f"(MedDRA PT: {record.preferred_term}, SOC: {record.category.value}). "
            f"The event was {expected_text} and assessed as {record.relatedness.value.lower()} "
            f"related to study treatment.\n\n"
            f"Onset date: {record.onset_date.strftime('%Y-%m-%d')}. "
            f"Reported by {record.reporter} on {record.reported_date.strftime('%Y-%m-%d')}. "
            f"{record.description}{resolution_text}{action_text}\n\n"
            f"Current outcome: {record.outcome.value}. "
            f"Current status: {record.status.value}.{expedited_text}"
        )

        return NarrativeReport(
            ae_id=ae_id,
            narrative=narrative,
            generated_at=now,
        )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all data (for testing)."""
        with self._lock:
            self._events.clear()
            self._signals.clear()
            self._expedited_reports.clear()

    def get_stats(self) -> dict:
        """Return service stats for health/prewarm."""
        return {
            "total_events": len(self._events),
            "total_signals": len(self._signals),
            "total_expedited_reports": len(self._expedited_reports),
            "service": "adverse_event",
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: AdverseEventService | None = None
_instance_lock = threading.Lock()


def get_adverse_event_service() -> AdverseEventService:
    """Return the singleton AdverseEventService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = AdverseEventService()
    return _instance


def reset_adverse_event_service() -> AdverseEventService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = AdverseEventService()
    return _instance
