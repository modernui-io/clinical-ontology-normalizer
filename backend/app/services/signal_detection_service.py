"""Safety Signal Detection Service (Pharmacovigilance).

Manages safety signal detection operations including signal identification,
disproportionality analysis, evaluation lifecycle, causality assessment,
and signal detection metrics.

Usage:
    from app.services.signal_detection_service import (
        get_signal_detection_service,
    )

    svc = get_signal_detection_service()
    signals = svc.list_signals()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.signal_detection import (
    DisproportionalityMethod,
    SafetySignal,
    SignalCreate,
    SignalEvaluation,
    SignalEvaluationCreate,
    SignalMetrics,
    SignalPriority,
    SignalSource,
    SignalStatus,
    SignalUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class SignalDetectionService:
    """In-memory Safety Signal Detection engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._signals: dict[str, SafetySignal] = {}
        self._evaluations: dict[str, SignalEvaluation] = {}
        self._signal_counter: int = 0
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic safety signal data across clinical trials."""
        now = datetime.now(timezone.utc)

        signals_data = [
            {
                "id": "SIG-001",
                "signal_number": "SIG-2026-001",
                "title": "Disproportionate hepatotoxicity reporting with Dupilumab",
                "description": (
                    "An unexpected increase in hepatotoxicity-related adverse events has "
                    "been observed in the Dupixent Phase III trial (LIBERTY AD). The PRR "
                    "of 3.8 exceeds the threshold of 2.0, with 47 observed cases versus "
                    "12.4 expected based on background rates. Elevated ALT/AST levels "
                    "reported in 8.2% of the treatment arm compared to 2.1% in placebo."
                ),
                "status": SignalStatus.UNDER_EVALUATION,
                "priority": SignalPriority.HIGH,
                "source": SignalSource.CLINICAL_TRIAL,
                "detected_date": now - timedelta(days=45),
                "evaluation_start_date": now - timedelta(days=40),
                "confirmed_date": None,
                "closed_date": None,
                "drug_name": "Dupilumab",
                "trial_ids": [DUPIXENT_TRIAL],
                "preferred_term": "Hepatotoxicity",
                "soc": "Hepatobiliary disorders",
                "observed_count": 47,
                "expected_count": 12.4,
                "disproportionality_score": 3.8,
                "method_used": DisproportionalityMethod.PRR,
                "reporter": "Central Safety Database",
                "assigned_evaluator": "Dr. Sarah Chen",
                "regulatory_impact": "Potential label update required; FDA may request supplemental data",
                "action_taken": "Enhanced hepatic monitoring protocol initiated",
            },
            {
                "id": "SIG-002",
                "signal_number": "SIG-2026-002",
                "title": "Cardiac arrhythmia signal in Libtayo Phase III oncology trial",
                "description": (
                    "Signal detected for QT prolongation and cardiac arrhythmia events "
                    "in the EMPOWER-Lung 1 trial. ROR of 2.9 with 31 observed cases "
                    "versus 10.7 expected. Three Grade 4 cardiac events reported, "
                    "including one fatal arrhythmia. ECG monitoring data shows QTcF "
                    "increase >60ms in 4.1% of patients."
                ),
                "status": SignalStatus.CONFIRMED,
                "priority": SignalPriority.URGENT,
                "source": SignalSource.CLINICAL_TRIAL,
                "detected_date": now - timedelta(days=90),
                "evaluation_start_date": now - timedelta(days=85),
                "confirmed_date": now - timedelta(days=30),
                "closed_date": None,
                "drug_name": "Cemiplimab",
                "trial_ids": [LIBTAYO_TRIAL],
                "preferred_term": "Cardiac arrhythmia",
                "soc": "Cardiac disorders",
                "observed_count": 31,
                "expected_count": 10.7,
                "disproportionality_score": 2.9,
                "method_used": DisproportionalityMethod.ROR,
                "reporter": "DSMB Safety Review",
                "assigned_evaluator": "Dr. Michael Torres",
                "regulatory_impact": "SUSAR filed; IND safety report submitted to FDA",
                "action_taken": "Mandatory ECG monitoring at each visit; dose modification guidance issued",
            },
            {
                "id": "SIG-003",
                "signal_number": "SIG-2026-003",
                "title": "Injection site vasculitis with Aflibercept high-dose formulation",
                "description": (
                    "Post-marketing spontaneous reports indicate a cluster of injection "
                    "site vasculitis events with the new 8mg Eylea HD formulation. EBGM "
                    "of 4.2 from FAERS data mining. 23 reports received in 6 months, "
                    "compared to 2 expected based on reporting rates for standard Eylea."
                ),
                "status": SignalStatus.NEW,
                "priority": SignalPriority.HIGH,
                "source": SignalSource.SPONTANEOUS_REPORTS,
                "detected_date": now - timedelta(days=14),
                "evaluation_start_date": None,
                "confirmed_date": None,
                "closed_date": None,
                "drug_name": "Aflibercept",
                "trial_ids": [EYLEA_TRIAL],
                "preferred_term": "Injection site vasculitis",
                "soc": "General disorders and administration site conditions",
                "observed_count": 23,
                "expected_count": 2.0,
                "disproportionality_score": 4.2,
                "method_used": DisproportionalityMethod.EBGM,
                "reporter": "FAERS Data Mining Algorithm",
                "assigned_evaluator": None,
                "regulatory_impact": None,
                "action_taken": None,
            },
            {
                "id": "SIG-004",
                "signal_number": "SIG-2026-004",
                "title": "Rhabdomyolysis reports in Dupilumab eczema population",
                "description": (
                    "Literature review identified 5 case reports of rhabdomyolysis in "
                    "patients receiving Dupilumab for moderate-to-severe atopic dermatitis. "
                    "BCPNN IC value of 1.8 suggests disproportionate reporting. All cases "
                    "involved patients with concurrent statin use, suggesting potential "
                    "drug interaction."
                ),
                "status": SignalStatus.REFUTED,
                "priority": SignalPriority.MEDIUM,
                "source": SignalSource.LITERATURE,
                "detected_date": now - timedelta(days=120),
                "evaluation_start_date": now - timedelta(days=115),
                "confirmed_date": None,
                "closed_date": now - timedelta(days=60),
                "drug_name": "Dupilumab",
                "trial_ids": [DUPIXENT_TRIAL],
                "preferred_term": "Rhabdomyolysis",
                "soc": "Musculoskeletal and connective tissue disorders",
                "observed_count": 5,
                "expected_count": 2.8,
                "disproportionality_score": 1.8,
                "method_used": DisproportionalityMethod.BCPNN,
                "reporter": "Literature Surveillance Team",
                "assigned_evaluator": "Dr. Emily Watson",
                "regulatory_impact": "No regulatory action required",
                "action_taken": "Confounding factor identified (statin co-administration); signal refuted",
            },
            {
                "id": "SIG-005",
                "signal_number": "SIG-2026-005",
                "title": "Immune-mediated colitis rate increase with Cemiplimab",
                "description": (
                    "Registry data from the SEER-Medicare linkage shows higher-than-expected "
                    "immune-mediated colitis rates in Cemiplimab-treated NSCLC patients. "
                    "MGPS EB05 of 2.1 across 18 months of real-world data. 89 cases "
                    "identified versus 42.4 expected. Grade 3+ colitis in 3.7% of patients."
                ),
                "status": SignalStatus.UNDER_EVALUATION,
                "priority": SignalPriority.HIGH,
                "source": SignalSource.REGISTRY,
                "detected_date": now - timedelta(days=60),
                "evaluation_start_date": now - timedelta(days=55),
                "confirmed_date": None,
                "closed_date": None,
                "drug_name": "Cemiplimab",
                "trial_ids": [LIBTAYO_TRIAL],
                "preferred_term": "Immune-mediated colitis",
                "soc": "Gastrointestinal disorders",
                "observed_count": 89,
                "expected_count": 42.4,
                "disproportionality_score": 2.1,
                "method_used": DisproportionalityMethod.MGPS,
                "reporter": "Real-World Evidence Platform",
                "assigned_evaluator": "Dr. James Park",
                "regulatory_impact": "May require REMS update and prescribing information revision",
                "action_taken": "Retrospective chart review initiated at top 10 prescribing sites",
            },
            {
                "id": "SIG-006",
                "signal_number": "SIG-2026-006",
                "title": "Thromboembolic events in Aflibercept-treated diabetic patients",
                "description": (
                    "Real-world data analysis from insurance claims databases shows "
                    "elevated thromboembolic event rates in diabetic patients receiving "
                    "intravitreal Aflibercept. PRR of 1.9 with 156 observed events "
                    "versus 82.1 expected over 24-month observation period."
                ),
                "status": SignalStatus.CLOSED,
                "priority": SignalPriority.MEDIUM,
                "source": SignalSource.REAL_WORLD_DATA,
                "detected_date": now - timedelta(days=200),
                "evaluation_start_date": now - timedelta(days=195),
                "confirmed_date": now - timedelta(days=140),
                "closed_date": now - timedelta(days=30),
                "drug_name": "Aflibercept",
                "trial_ids": [EYLEA_TRIAL],
                "preferred_term": "Thromboembolic event",
                "soc": "Vascular disorders",
                "observed_count": 156,
                "expected_count": 82.1,
                "disproportionality_score": 1.9,
                "method_used": DisproportionalityMethod.PRR,
                "reporter": "Pharmacoepidemiology Team",
                "assigned_evaluator": "Dr. Lisa Nguyen",
                "regulatory_impact": "Label updated with thromboembolic risk warning for diabetic patients",
                "action_taken": "Prescribing information updated; Dear Healthcare Provider letter issued",
            },
            {
                "id": "SIG-007",
                "signal_number": "SIG-2026-007",
                "title": "Peripheral neuropathy cluster with Cemiplimab combination therapy",
                "description": (
                    "Spontaneous reports of peripheral neuropathy in patients receiving "
                    "Cemiplimab in combination with platinum-based chemotherapy. ROR of "
                    "3.1 detected in FAERS quarterly analysis. 18 reports in Q4 2025, "
                    "predominantly Grade 2-3 sensorimotor neuropathy."
                ),
                "status": SignalStatus.NEW,
                "priority": SignalPriority.MEDIUM,
                "source": SignalSource.SPONTANEOUS_REPORTS,
                "detected_date": now - timedelta(days=7),
                "evaluation_start_date": None,
                "confirmed_date": None,
                "closed_date": None,
                "drug_name": "Cemiplimab",
                "trial_ids": [LIBTAYO_TRIAL],
                "preferred_term": "Peripheral neuropathy",
                "soc": "Nervous system disorders",
                "observed_count": 18,
                "expected_count": 5.8,
                "disproportionality_score": 3.1,
                "method_used": DisproportionalityMethod.ROR,
                "reporter": "FAERS Quarterly Review",
                "assigned_evaluator": None,
                "regulatory_impact": None,
                "action_taken": None,
            },
            {
                "id": "SIG-008",
                "signal_number": "SIG-2026-008",
                "title": "Anaphylaxis signal with Dupilumab prefilled syringe formulation",
                "description": (
                    "Clinical trial safety database review identified a potential signal "
                    "for anaphylaxis with the prefilled syringe formulation of Dupilumab. "
                    "EBGM of 2.5 with 8 confirmed anaphylaxis cases across Phase III "
                    "studies versus 3.2 expected. Onset typically within 30 minutes of "
                    "injection."
                ),
                "status": SignalStatus.UNDER_EVALUATION,
                "priority": SignalPriority.URGENT,
                "source": SignalSource.CLINICAL_TRIAL,
                "detected_date": now - timedelta(days=21),
                "evaluation_start_date": now - timedelta(days=18),
                "confirmed_date": None,
                "closed_date": None,
                "drug_name": "Dupilumab",
                "trial_ids": [DUPIXENT_TRIAL],
                "preferred_term": "Anaphylaxis",
                "soc": "Immune system disorders",
                "observed_count": 8,
                "expected_count": 3.2,
                "disproportionality_score": 2.5,
                "method_used": DisproportionalityMethod.EBGM,
                "reporter": "Clinical Safety Database Review",
                "assigned_evaluator": "Dr. Rachel Kim",
                "regulatory_impact": "Potential REMS requirement; BPCA consideration",
                "action_taken": "Post-injection observation period extended to 60 minutes",
            },
            {
                "id": "SIG-009",
                "signal_number": "SIG-2026-009",
                "title": "Hypothyroidism increase in Cemiplimab-treated patients over 65",
                "description": (
                    "Age-stratified analysis of FAERS data reveals disproportionate "
                    "hypothyroidism reporting in Cemiplimab-treated patients aged 65+. "
                    "PRR of 2.3 in elderly subgroup versus 1.4 overall. 67 cases in "
                    "patients over 65 versus 29.1 expected."
                ),
                "status": SignalStatus.NEW,
                "priority": SignalPriority.LOW,
                "source": SignalSource.REAL_WORLD_DATA,
                "detected_date": now - timedelta(days=5),
                "evaluation_start_date": None,
                "confirmed_date": None,
                "closed_date": None,
                "drug_name": "Cemiplimab",
                "trial_ids": [LIBTAYO_TRIAL],
                "preferred_term": "Hypothyroidism",
                "soc": "Endocrine disorders",
                "observed_count": 67,
                "expected_count": 29.1,
                "disproportionality_score": 2.3,
                "method_used": DisproportionalityMethod.PRR,
                "reporter": "Geriatric PV Surveillance",
                "assigned_evaluator": None,
                "regulatory_impact": None,
                "action_taken": None,
            },
            {
                "id": "SIG-010",
                "signal_number": "SIG-2026-010",
                "title": "Retinal detachment rate with Aflibercept treat-and-extend regimen",
                "description": (
                    "Published meta-analysis of 12 studies reports elevated retinal "
                    "detachment rates with Aflibercept treat-and-extend dosing compared "
                    "to fixed monthly dosing. BCPNN IC of 1.6 with 34 cases across "
                    "pooled studies versus 21.3 expected."
                ),
                "status": SignalStatus.REFUTED,
                "priority": SignalPriority.LOW,
                "source": SignalSource.LITERATURE,
                "detected_date": now - timedelta(days=150),
                "evaluation_start_date": now - timedelta(days=145),
                "confirmed_date": None,
                "closed_date": now - timedelta(days=90),
                "drug_name": "Aflibercept",
                "trial_ids": [EYLEA_TRIAL],
                "preferred_term": "Retinal detachment",
                "soc": "Eye disorders",
                "observed_count": 34,
                "expected_count": 21.3,
                "disproportionality_score": 1.6,
                "method_used": DisproportionalityMethod.BCPNN,
                "reporter": "Medical Literature Review",
                "assigned_evaluator": "Dr. Amanda Foster",
                "regulatory_impact": "No regulatory action required",
                "action_taken": "Independent review concluded confounding by disease severity; signal refuted",
            },
        ]

        self._signal_counter = len(signals_data)

        for s in signals_data:
            self._signals[s["id"]] = SafetySignal(**s)

        # --- Seed evaluations for signals under evaluation / confirmed ---
        evaluations_data = [
            {
                "id": "EVAL-001",
                "signal_id": "SIG-001",
                "evaluator": "Dr. Sarah Chen",
                "evaluation_date": now - timedelta(days=35),
                "conclusion": (
                    "Preliminary analysis supports a potential causal relationship. "
                    "Dose-response relationship observed. Hepatic enzyme elevations "
                    "correlated with treatment duration."
                ),
                "supporting_evidence": (
                    "47 hepatotoxicity cases in treatment arm (N=2,340) vs 5 in "
                    "placebo (N=1,170). Dechallenge positive in 12/15 cases assessed. "
                    "No alternative etiology identified in 38 of 47 cases."
                ),
                "recommendation": (
                    "Continue enhanced hepatic monitoring. Request hepatology consult "
                    "for all Grade 2+ cases. Consider dose modification algorithm."
                ),
                "causality_assessment": "probable",
            },
            {
                "id": "EVAL-002",
                "signal_id": "SIG-002",
                "evaluator": "Dr. Michael Torres",
                "evaluation_date": now - timedelta(days=50),
                "conclusion": (
                    "Signal confirmed. Clear temporal relationship between Cemiplimab "
                    "administration and cardiac events. QTcF prolongation mechanism "
                    "identified through in-vitro hERG assay."
                ),
                "supporting_evidence": (
                    "31 cardiac arrhythmia events including 1 fatal case. Median "
                    "onset 42 days after treatment initiation. QTcF >500ms in 2.1% "
                    "of treatment arm. hERG channel inhibition confirmed at therapeutic "
                    "concentrations."
                ),
                "recommendation": (
                    "Implement mandatory baseline and on-treatment ECG monitoring. "
                    "Exclude patients with baseline QTcF >450ms. File IND safety report."
                ),
                "causality_assessment": "certain",
            },
            {
                "id": "EVAL-003",
                "signal_id": "SIG-002",
                "evaluator": "Dr. Anna Kowalski",
                "evaluation_date": now - timedelta(days=35),
                "conclusion": (
                    "Confirmatory evaluation concurs with initial assessment. "
                    "Additional mechanistic data from cardiac safety study supports "
                    "direct drug effect on cardiac conduction."
                ),
                "supporting_evidence": (
                    "Thorough QT study shows concentration-dependent QTcF increase. "
                    "Phase I cardiac safety substudy confirms findings. Two additional "
                    "Grade 3 arrhythmia cases reported since initial evaluation."
                ),
                "recommendation": (
                    "Update prescribing information. Implement REMS-like monitoring "
                    "program. Consider cardiology referral pathway."
                ),
                "causality_assessment": "certain",
            },
            {
                "id": "EVAL-004",
                "signal_id": "SIG-005",
                "evaluator": "Dr. James Park",
                "evaluation_date": now - timedelta(days=30),
                "conclusion": (
                    "Signal remains under active evaluation. Registry data consistent "
                    "with known class effect of immune checkpoint inhibitors but rate "
                    "appears higher than comparator agents."
                ),
                "supporting_evidence": (
                    "89 immune-mediated colitis cases in SEER-Medicare cohort. Rate "
                    "of 3.7% vs 2.1% for nivolumab and 2.4% for pembrolizumab in "
                    "similar populations. Onset typically 6-12 weeks post-initiation."
                ),
                "recommendation": (
                    "Expand analysis to include additional real-world data sources. "
                    "Initiate head-to-head comparison with other PD-1/PD-L1 inhibitors."
                ),
                "causality_assessment": "possible",
            },
            {
                "id": "EVAL-005",
                "signal_id": "SIG-004",
                "evaluator": "Dr. Emily Watson",
                "evaluation_date": now - timedelta(days=70),
                "conclusion": (
                    "Signal refuted. Rhabdomyolysis cases attributable to concurrent "
                    "statin therapy and viral myositis rather than Dupilumab. No "
                    "pharmacological mechanism supports direct causation."
                ),
                "supporting_evidence": (
                    "All 5 cases had concurrent high-dose statin use. 3 of 5 had "
                    "concurrent viral illness. No rhabdomyolysis in 12,000+ Dupilumab "
                    "patients without statin co-administration in clinical program."
                ),
                "recommendation": (
                    "Close signal. No label change required. Continue routine "
                    "pharmacovigilance monitoring."
                ),
                "causality_assessment": "unlikely",
            },
            {
                "id": "EVAL-006",
                "signal_id": "SIG-008",
                "evaluator": "Dr. Rachel Kim",
                "evaluation_date": now - timedelta(days=10),
                "conclusion": (
                    "Preliminary evaluation suggests formulation-specific issue. "
                    "Anaphylaxis cases clustered with specific lot numbers of "
                    "prefilled syringe. Latex allergy may be contributing factor."
                ),
                "supporting_evidence": (
                    "6 of 8 anaphylaxis cases from 3 lot numbers. 5 of 8 patients "
                    "had history of latex sensitivity. Prefilled syringe tip cap "
                    "contains natural rubber latex derivative."
                ),
                "recommendation": (
                    "Investigate lot-specific manufacturing deviations. Add latex "
                    "allergy contraindication warning. Extend post-injection "
                    "observation to 60 minutes for at-risk patients."
                ),
                "causality_assessment": "probable",
            },
        ]

        for e in evaluations_data:
            self._evaluations[e["id"]] = SignalEvaluation(**e)

    # ------------------------------------------------------------------
    # Signal CRUD
    # ------------------------------------------------------------------

    def list_signals(
        self,
        *,
        status: SignalStatus | None = None,
        priority: SignalPriority | None = None,
        source: SignalSource | None = None,
        drug_name: str | None = None,
    ) -> list[SafetySignal]:
        """List signals with optional filters."""
        with self._lock:
            result = list(self._signals.values())

        if status is not None:
            result = [s for s in result if s.status == status]
        if priority is not None:
            result = [s for s in result if s.priority == priority]
        if source is not None:
            result = [s for s in result if s.source == source]
        if drug_name is not None:
            result = [
                s for s in result
                if s.drug_name.lower() == drug_name.lower()
            ]

        return sorted(result, key=lambda s: s.detected_date, reverse=True)

    def get_signal(self, signal_id: str) -> SafetySignal | None:
        """Get a single signal by ID."""
        with self._lock:
            return self._signals.get(signal_id)

    def create_signal(self, payload: SignalCreate) -> SafetySignal:
        """Create a new safety signal."""
        now = datetime.now(timezone.utc)
        with self._lock:
            self._signal_counter += 1
            signal_id = f"SIG-{uuid4().hex[:8].upper()}"
            signal_number = f"SIG-2026-{self._signal_counter:03d}"

        signal = SafetySignal(
            id=signal_id,
            signal_number=signal_number,
            title=payload.title,
            description=payload.description,
            status=SignalStatus.NEW,
            priority=payload.priority,
            source=payload.source,
            detected_date=now,
            evaluation_start_date=None,
            confirmed_date=None,
            closed_date=None,
            drug_name=payload.drug_name,
            trial_ids=payload.trial_ids,
            preferred_term=payload.preferred_term,
            soc=payload.soc,
            observed_count=payload.observed_count,
            expected_count=payload.expected_count,
            disproportionality_score=payload.disproportionality_score,
            method_used=payload.method_used,
            reporter=payload.reporter,
            assigned_evaluator=payload.assigned_evaluator,
            regulatory_impact=None,
            action_taken=None,
        )

        with self._lock:
            self._signals[signal_id] = signal
        logger.info("Created safety signal %s: %s", signal_id, payload.title)
        return signal

    def update_signal(self, signal_id: str, payload: SignalUpdate) -> SafetySignal | None:
        """Update an existing signal."""
        with self._lock:
            existing = self._signals.get(signal_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SafetySignal(**data)
            self._signals[signal_id] = updated
        return updated

    def delete_signal(self, signal_id: str) -> bool:
        """Delete a signal. Returns True if deleted, False if not found."""
        with self._lock:
            if signal_id in self._signals:
                del self._signals[signal_id]
                # Also remove associated evaluations
                eval_ids_to_remove = [
                    eid for eid, ev in self._evaluations.items()
                    if ev.signal_id == signal_id
                ]
                for eid in eval_ids_to_remove:
                    del self._evaluations[eid]
                return True
            return False

    # ------------------------------------------------------------------
    # Signal Lifecycle Transitions
    # ------------------------------------------------------------------

    def evaluate_signal(self, signal_id: str) -> SafetySignal | None:
        """Transition a signal to under_evaluation status."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._signals.get(signal_id)
            if existing is None:
                return None

            if existing.status != SignalStatus.NEW:
                raise ValueError(
                    f"Signal '{signal_id}' cannot be evaluated from status "
                    f"'{existing.status.value}'; must be 'new'"
                )

            data = existing.model_dump()
            data["status"] = SignalStatus.UNDER_EVALUATION
            data["evaluation_start_date"] = now
            updated = SafetySignal(**data)
            self._signals[signal_id] = updated
        logger.info("Signal %s moved to under_evaluation", signal_id)
        return updated

    def confirm_signal(self, signal_id: str) -> SafetySignal | None:
        """Confirm a safety signal."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._signals.get(signal_id)
            if existing is None:
                return None

            if existing.status != SignalStatus.UNDER_EVALUATION:
                raise ValueError(
                    f"Signal '{signal_id}' cannot be confirmed from status "
                    f"'{existing.status.value}'; must be 'under_evaluation'"
                )

            data = existing.model_dump()
            data["status"] = SignalStatus.CONFIRMED
            data["confirmed_date"] = now
            updated = SafetySignal(**data)
            self._signals[signal_id] = updated
        logger.info("Signal %s confirmed", signal_id)
        return updated

    def refute_signal(self, signal_id: str) -> SafetySignal | None:
        """Refute a safety signal."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._signals.get(signal_id)
            if existing is None:
                return None

            if existing.status != SignalStatus.UNDER_EVALUATION:
                raise ValueError(
                    f"Signal '{signal_id}' cannot be refuted from status "
                    f"'{existing.status.value}'; must be 'under_evaluation'"
                )

            data = existing.model_dump()
            data["status"] = SignalStatus.REFUTED
            data["closed_date"] = now
            updated = SafetySignal(**data)
            self._signals[signal_id] = updated
        logger.info("Signal %s refuted", signal_id)
        return updated

    def close_signal(self, signal_id: str) -> SafetySignal | None:
        """Close a safety signal (from confirmed or refuted)."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._signals.get(signal_id)
            if existing is None:
                return None

            if existing.status not in (SignalStatus.CONFIRMED, SignalStatus.REFUTED):
                raise ValueError(
                    f"Signal '{signal_id}' cannot be closed from status "
                    f"'{existing.status.value}'; must be 'confirmed' or 'refuted'"
                )

            data = existing.model_dump()
            data["status"] = SignalStatus.CLOSED
            data["closed_date"] = now
            updated = SafetySignal(**data)
            self._signals[signal_id] = updated
        logger.info("Signal %s closed", signal_id)
        return updated

    # ------------------------------------------------------------------
    # Evaluations
    # ------------------------------------------------------------------

    def list_evaluations(self, signal_id: str) -> list[SignalEvaluation]:
        """List evaluations for a specific signal."""
        with self._lock:
            result = [
                ev for ev in self._evaluations.values()
                if ev.signal_id == signal_id
            ]
        return sorted(result, key=lambda e: e.evaluation_date, reverse=True)

    def create_evaluation(
        self, signal_id: str, payload: SignalEvaluationCreate
    ) -> SignalEvaluation:
        """Create an evaluation for a signal."""
        now = datetime.now(timezone.utc)

        with self._lock:
            if signal_id not in self._signals:
                raise ValueError(f"Signal '{signal_id}' not found")

        eval_id = f"EVAL-{uuid4().hex[:8].upper()}"
        evaluation = SignalEvaluation(
            id=eval_id,
            signal_id=signal_id,
            evaluator=payload.evaluator,
            evaluation_date=now,
            conclusion=payload.conclusion,
            supporting_evidence=payload.supporting_evidence,
            recommendation=payload.recommendation,
            causality_assessment=payload.causality_assessment,
        )

        with self._lock:
            self._evaluations[eval_id] = evaluation
        logger.info(
            "Created evaluation %s for signal %s by %s",
            eval_id, signal_id, payload.evaluator,
        )
        return evaluation

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> SignalMetrics:
        """Compute aggregated signal detection metrics."""
        with self._lock:
            signals = list(self._signals.values())
            evaluations = list(self._evaluations.values())

        # Signals by status
        by_status: dict[str, int] = {}
        for sig in signals:
            key = sig.status.value
            by_status[key] = by_status.get(key, 0) + 1

        # Signals by priority
        by_priority: dict[str, int] = {}
        for sig in signals:
            key = sig.priority.value
            by_priority[key] = by_priority.get(key, 0) + 1

        # Signals by source
        by_source: dict[str, int] = {}
        for sig in signals:
            key = sig.source.value
            by_source[key] = by_source.get(key, 0) + 1

        # Average disproportionality score
        if signals:
            avg_score = round(
                sum(s.disproportionality_score for s in signals) / len(signals),
                2,
            )
        else:
            avg_score = 0.0

        confirmed = sum(1 for s in signals if s.status == SignalStatus.CONFIRMED)
        refuted = sum(1 for s in signals if s.status == SignalStatus.REFUTED)
        open_signals = sum(
            1 for s in signals
            if s.status in (SignalStatus.NEW, SignalStatus.UNDER_EVALUATION)
        )
        urgent = sum(1 for s in signals if s.priority == SignalPriority.URGENT)

        return SignalMetrics(
            total_signals=len(signals),
            signals_by_status=by_status,
            signals_by_priority=by_priority,
            signals_by_source=by_source,
            avg_disproportionality_score=avg_score,
            total_evaluations=len(evaluations),
            confirmed_signals=confirmed,
            refuted_signals=refuted,
            open_signals=open_signals,
            urgent_signals=urgent,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: SignalDetectionService | None = None
_lock = threading.Lock()


def get_signal_detection_service() -> SignalDetectionService:
    """Return the singleton SignalDetectionService instance."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = SignalDetectionService()
    return _instance


def reset_signal_detection_service() -> SignalDetectionService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _lock:
        _instance = SignalDetectionService()
    return _instance
