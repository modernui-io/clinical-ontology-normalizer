"""Safety Signal Detection Service (SAFETY-SIGNAL).

Manages pharmacovigilance signal detection: disproportionality analysis,
signal evaluation, safety signal lifecycle, cumulative review tracking,
aggregate safety reports, and signal detection operational metrics.

Usage:
    from app.services.safety_signal_detection_service import (
        get_safety_signal_detection_service,
    )

    svc = get_safety_signal_detection_service()
    signals = svc.list_signals()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.safety_signal_detection import (
    AggregateSafetyReport,
    AggregateSafetyReportCreate,
    AggregateSafetyReportUpdate,
    CausalityAssessment,
    CumulativeReview,
    CumulativeReviewCreate,
    DisproportionalityAnalysis,
    DisproportionalityAnalysisCreate,
    DisproportionalityAnalysisUpdate,
    ReportPeriod,
    SafetySignal,
    SafetySignalCreate,
    SafetySignalMetrics,
    SafetySignalUpdate,
    SignalEvaluation,
    SignalEvaluationCreate,
    SignalMethod,
    SignalPriority,
    SignalStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class SafetySignalDetectionService:
    """In-memory Safety Signal Detection engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._signals: dict[str, SafetySignal] = {}
        self._evaluations: dict[str, SignalEvaluation] = {}
        self._cumulative_reviews: dict[str, CumulativeReview] = {}
        self._analyses: dict[str, DisproportionalityAnalysis] = {}
        self._aggregate_reports: dict[str, AggregateSafetyReport] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic safety signal detection data."""
        now = datetime.now(timezone.utc)

        # --- Safety Signals (12) ---
        signal_defs = [
            {
                "trial_id": EYLEA_TRIAL,
                "signal_name": "Endophthalmitis post-injection",
                "preferred_term": "Endophthalmitis",
                "meddra_code": "10014801",
                "soc": "Eye disorders",
                "detection_method": SignalMethod.PRR,
                "status": SignalStatus.CONFIRMED,
                "priority": SignalPriority.HIGH,
                "drug_name": "Aflibercept",
                "comparator": "Ranibizumab",
                "observed_cases": 18,
                "expected_cases": 8.5,
                "prr_value": 2.12,
                "ror_value": 2.35,
                "ci_lower": 1.45,
                "ci_upper": 3.81,
                "p_value": 0.003,
                "causality": CausalityAssessment.PROBABLE,
                "detected_by": "Dr. Sarah Chen",
                "assigned_to": "Dr. James Miller",
            },
            {
                "trial_id": EYLEA_TRIAL,
                "signal_name": "Retinal detachment",
                "preferred_term": "Retinal detachment",
                "meddra_code": "10038848",
                "soc": "Eye disorders",
                "detection_method": SignalMethod.BCPNN,
                "status": SignalStatus.UNDER_EVALUATION,
                "priority": SignalPriority.CRITICAL,
                "drug_name": "Aflibercept",
                "observed_cases": 7,
                "expected_cases": 2.1,
                "ebgm_value": 3.33,
                "ci_lower": 1.85,
                "ci_upper": 5.99,
                "detected_by": "Signal Detection Algorithm",
                "assigned_to": "Dr. Emily Park",
            },
            {
                "trial_id": EYLEA_TRIAL,
                "signal_name": "Intraocular pressure increased",
                "preferred_term": "Intraocular pressure increased",
                "meddra_code": "10022806",
                "soc": "Eye disorders",
                "detection_method": SignalMethod.ROR,
                "status": SignalStatus.ONGOING_MONITORING,
                "priority": SignalPriority.MEDIUM,
                "drug_name": "Aflibercept",
                "observed_cases": 32,
                "expected_cases": 24.0,
                "ror_value": 1.42,
                "ci_lower": 0.98,
                "ci_upper": 2.06,
                "causality": CausalityAssessment.POSSIBLE,
                "detected_by": "Dr. Michael Huang",
            },
            {
                "trial_id": DUPIXENT_TRIAL,
                "signal_name": "Conjunctivitis allergic",
                "preferred_term": "Conjunctivitis allergic",
                "meddra_code": "10010744",
                "soc": "Eye disorders",
                "detection_method": SignalMethod.PRR,
                "status": SignalStatus.CONFIRMED,
                "priority": SignalPriority.HIGH,
                "drug_name": "Dupilumab",
                "comparator": "Placebo",
                "observed_cases": 45,
                "expected_cases": 12.0,
                "prr_value": 3.75,
                "ror_value": 4.12,
                "ci_lower": 2.85,
                "ci_upper": 5.95,
                "p_value": 0.0001,
                "causality": CausalityAssessment.CERTAIN,
                "detected_by": "PRAC Signal Detection",
                "assigned_to": "Dr. Lisa Thompson",
            },
            {
                "trial_id": DUPIXENT_TRIAL,
                "signal_name": "Injection site reaction severe",
                "preferred_term": "Injection site reaction",
                "meddra_code": "10022095",
                "soc": "General disorders",
                "detection_method": SignalMethod.MGPS,
                "status": SignalStatus.REFUTED,
                "priority": SignalPriority.LOW,
                "drug_name": "Dupilumab",
                "observed_cases": 15,
                "expected_cases": 13.5,
                "prr_value": 1.11,
                "ci_lower": 0.65,
                "ci_upper": 1.90,
                "p_value": 0.72,
                "causality": CausalityAssessment.UNLIKELY,
                "detected_by": "Routine Screening",
            },
            {
                "trial_id": DUPIXENT_TRIAL,
                "signal_name": "Eosinophilia",
                "preferred_term": "Eosinophilia",
                "meddra_code": "10014950",
                "soc": "Blood and lymphatic system disorders",
                "detection_method": SignalMethod.EBGM,
                "status": SignalStatus.UNDER_EVALUATION,
                "priority": SignalPriority.MEDIUM,
                "drug_name": "Dupilumab",
                "observed_cases": 22,
                "expected_cases": 9.8,
                "ebgm_value": 2.24,
                "ci_lower": 1.42,
                "ci_upper": 3.55,
                "detected_by": "Bayesian Signal Detection",
                "assigned_to": "Dr. Robert Kim",
            },
            {
                "trial_id": DUPIXENT_TRIAL,
                "signal_name": "Arthralgia",
                "preferred_term": "Arthralgia",
                "meddra_code": "10003239",
                "soc": "Musculoskeletal disorders",
                "detection_method": SignalMethod.FREQUENTIST,
                "status": SignalStatus.DETECTED,
                "priority": SignalPriority.LOW,
                "drug_name": "Dupilumab",
                "observed_cases": 28,
                "expected_cases": 22.0,
                "prr_value": 1.27,
                "ci_lower": 0.88,
                "ci_upper": 1.84,
                "p_value": 0.21,
                "detected_by": "Dr. Anna Kowalski",
            },
            {
                "trial_id": LIBTAYO_TRIAL,
                "signal_name": "Pneumonitis immune-related",
                "preferred_term": "Pneumonitis",
                "meddra_code": "10035742",
                "soc": "Respiratory disorders",
                "detection_method": SignalMethod.PRR,
                "status": SignalStatus.CONFIRMED,
                "priority": SignalPriority.CRITICAL,
                "drug_name": "Cemiplimab",
                "observed_cases": 12,
                "expected_cases": 3.2,
                "prr_value": 3.75,
                "ror_value": 4.05,
                "ci_lower": 2.10,
                "ci_upper": 7.81,
                "p_value": 0.0005,
                "causality": CausalityAssessment.PROBABLE,
                "detected_by": "Safety Surveillance Team",
                "assigned_to": "Dr. David Wilson",
            },
            {
                "trial_id": LIBTAYO_TRIAL,
                "signal_name": "Hepatitis autoimmune",
                "preferred_term": "Autoimmune hepatitis",
                "meddra_code": "10003827",
                "soc": "Hepatobiliary disorders",
                "detection_method": SignalMethod.BAYESIAN,
                "status": SignalStatus.UNDER_EVALUATION,
                "priority": SignalPriority.HIGH,
                "drug_name": "Cemiplimab",
                "observed_cases": 8,
                "expected_cases": 2.5,
                "ebgm_value": 3.20,
                "ci_lower": 1.55,
                "ci_upper": 6.60,
                "detected_by": "PBRER Review",
                "assigned_to": "Dr. Maria Garcia",
            },
            {
                "trial_id": LIBTAYO_TRIAL,
                "signal_name": "Thyroiditis",
                "preferred_term": "Thyroiditis",
                "meddra_code": "10043738",
                "soc": "Endocrine disorders",
                "detection_method": SignalMethod.ROR,
                "status": SignalStatus.ONGOING_MONITORING,
                "priority": SignalPriority.MEDIUM,
                "drug_name": "Cemiplimab",
                "observed_cases": 19,
                "expected_cases": 11.0,
                "ror_value": 1.78,
                "ci_lower": 1.10,
                "ci_upper": 2.88,
                "causality": CausalityAssessment.POSSIBLE,
                "detected_by": "Dr. Thomas Lee",
            },
            {
                "trial_id": LIBTAYO_TRIAL,
                "signal_name": "Colitis immune-related",
                "preferred_term": "Colitis",
                "meddra_code": "10009887",
                "soc": "Gastrointestinal disorders",
                "detection_method": SignalMethod.MGPS,
                "status": SignalStatus.DETECTED,
                "priority": SignalPriority.HIGH,
                "drug_name": "Cemiplimab",
                "observed_cases": 10,
                "expected_cases": 4.0,
                "prr_value": 2.50,
                "ci_lower": 1.30,
                "ci_upper": 4.80,
                "detected_by": "Signal Detection Algorithm",
            },
            {
                "trial_id": EYLEA_TRIAL,
                "signal_name": "Vitreous floaters",
                "preferred_term": "Vitreous floaters",
                "meddra_code": "10047654",
                "soc": "Eye disorders",
                "detection_method": SignalMethod.FREQUENTIST,
                "status": SignalStatus.CLOSED,
                "priority": SignalPriority.LOW,
                "drug_name": "Aflibercept",
                "observed_cases": 40,
                "expected_cases": 38.0,
                "prr_value": 1.05,
                "ci_lower": 0.75,
                "ci_upper": 1.48,
                "p_value": 0.78,
                "causality": CausalityAssessment.UNLIKELY,
                "detected_by": "Routine Screening",
            },
        ]

        for i, sd in enumerate(signal_defs):
            sig_id = str(uuid4())
            detected_offset = timedelta(days=90 - i * 7)
            self._signals[sig_id] = SafetySignal(
                id=sig_id,
                trial_id=sd["trial_id"],
                signal_name=sd["signal_name"],
                preferred_term=sd["preferred_term"],
                meddra_code=sd.get("meddra_code"),
                soc=sd.get("soc"),
                detection_method=sd["detection_method"],
                status=sd["status"],
                priority=sd["priority"],
                detected_date=now - detected_offset,
                drug_name=sd["drug_name"],
                comparator=sd.get("comparator"),
                observed_cases=sd.get("observed_cases", 0),
                expected_cases=sd.get("expected_cases", 0),
                prr_value=sd.get("prr_value"),
                ror_value=sd.get("ror_value"),
                ebgm_value=sd.get("ebgm_value"),
                ci_lower=sd.get("ci_lower"),
                ci_upper=sd.get("ci_upper"),
                p_value=sd.get("p_value"),
                causality=sd.get("causality"),
                detected_by=sd["detected_by"],
                assigned_to=sd.get("assigned_to"),
                created_at=now - detected_offset,
            )

        # --- Signal Evaluations (10) ---
        signal_ids = list(self._signals.keys())
        eval_defs = [
            {
                "signal_idx": 0,
                "evaluator": "Dr. James Miller",
                "clinical_significance": "Clinically significant - known class effect for anti-VEGF agents",
                "biological_plausibility": "Strong - intravitreal injection introduces infection risk",
                "temporal_relationship": True,
                "dose_response": False,
                "dechallenge_positive": True,
                "overall_assessment": CausalityAssessment.PROBABLE,
                "recommendation": "Update labeling with enhanced post-injection monitoring guidance",
                "action_items": ["Update PI section 5.1", "Revise injection protocol", "Issue DHPC"],
            },
            {
                "signal_idx": 1,
                "evaluator": "Dr. Emily Park",
                "clinical_significance": "Serious - potential sight-threatening complication",
                "biological_plausibility": "Moderate - mechanical effect of vitreous manipulation",
                "temporal_relationship": True,
                "dose_response": None,
                "overall_assessment": CausalityAssessment.POSSIBLE,
                "recommendation": "Conduct focused case review and request additional data from sites",
                "action_items": ["Request 90-day follow-up data", "Engage ophthalmology consultants"],
            },
            {
                "signal_idx": 3,
                "evaluator": "Dr. Lisa Thompson",
                "clinical_significance": "Well-established signal - dose-dependent ocular inflammation",
                "biological_plausibility": "Strong - IL-4/IL-13 blockade affects conjunctival immune homeostasis",
                "temporal_relationship": True,
                "dose_response": True,
                "dechallenge_positive": True,
                "rechallenge_positive": True,
                "overall_assessment": CausalityAssessment.CERTAIN,
                "recommendation": "Confirmed as ADR. Include in PBRER and update SmPC section 4.8",
                "action_items": ["Update SmPC", "Submit variation to EMA", "Update patient leaflet"],
            },
            {
                "signal_idx": 4,
                "evaluator": "Dr. Anna Kowalski",
                "clinical_significance": "Not significant - rates consistent with background",
                "biological_plausibility": "Low - no known mechanism",
                "temporal_relationship": False,
                "overall_assessment": CausalityAssessment.UNLIKELY,
                "recommendation": "Close signal - no further action needed",
                "action_items": ["Document in signal tracking log"],
            },
            {
                "signal_idx": 7,
                "evaluator": "Dr. David Wilson",
                "clinical_significance": "Serious - known immune checkpoint inhibitor class effect",
                "biological_plausibility": "Strong - T-cell activation can cause pneumonitis",
                "temporal_relationship": True,
                "dose_response": True,
                "dechallenge_positive": True,
                "overall_assessment": CausalityAssessment.PROBABLE,
                "recommendation": "Enhanced monitoring and dosing guidelines for immune-related pneumonitis",
                "action_items": ["Update REMS", "Revise dosing algorithm", "Train sites on management"],
            },
            {
                "signal_idx": 8,
                "evaluator": "Dr. Maria Garcia",
                "clinical_significance": "Serious - hepatotoxicity requiring monitoring",
                "biological_plausibility": "Strong - immune checkpoint inhibitors known to cause autoimmune hepatitis",
                "temporal_relationship": True,
                "overall_assessment": CausalityAssessment.POSSIBLE,
                "recommendation": "Request hepatic monitoring data and conduct expert review",
                "action_items": ["Convene hepatology advisory board", "Collect LFT data from all sites"],
            },
            {
                "signal_idx": 9,
                "evaluator": "Dr. Thomas Lee",
                "clinical_significance": "Moderate - thyroid dysfunction is manageable",
                "biological_plausibility": "Strong - PD-1 inhibition affects thyroid immune tolerance",
                "temporal_relationship": True,
                "dose_response": False,
                "overall_assessment": CausalityAssessment.PROBABLE,
                "recommendation": "Continue monitoring with thyroid function tests at baseline and q3 months",
                "action_items": ["Add thyroid monitoring to protocol", "Update informed consent"],
            },
            {
                "signal_idx": 2,
                "evaluator": "Dr. Michael Huang",
                "clinical_significance": "Moderate - transient IOP elevation commonly observed",
                "biological_plausibility": "Moderate - injection volume can raise IOP",
                "temporal_relationship": True,
                "overall_assessment": CausalityAssessment.POSSIBLE,
                "recommendation": "Monitor IOP 30 minutes post-injection per existing guidance",
                "action_items": ["Review IOP monitoring compliance across sites"],
            },
            {
                "signal_idx": 5,
                "evaluator": "Dr. Robert Kim",
                "clinical_significance": "Moderate - eosinophilia may indicate hypersensitivity",
                "biological_plausibility": "Strong - IL-4/IL-13 pathway involved in eosinophil regulation",
                "temporal_relationship": True,
                "dose_response": True,
                "overall_assessment": CausalityAssessment.PROBABLE,
                "recommendation": "Complete eosinophilia signal evaluation with lab data review",
                "action_items": ["Collect eosinophil counts from all subjects", "Correlate with clinical outcomes"],
            },
            {
                "signal_idx": 10,
                "evaluator": "Dr. David Wilson",
                "clinical_significance": "Serious - immune-related colitis can be life-threatening",
                "biological_plausibility": "Strong - PD-1 inhibition disrupts gut immune tolerance",
                "temporal_relationship": True,
                "dose_response": False,
                "dechallenge_positive": True,
                "overall_assessment": CausalityAssessment.PROBABLE,
                "recommendation": "Initiate formal signal evaluation and notify DSMB",
                "action_items": ["Notify DSMB", "Review all GI events", "Prepare signal assessment report"],
            },
        ]

        for i, ed in enumerate(eval_defs):
            eval_id = str(uuid4())
            self._evaluations[eval_id] = SignalEvaluation(
                id=eval_id,
                signal_id=signal_ids[ed["signal_idx"]],
                evaluation_date=now - timedelta(days=60 - i * 5),
                evaluator=ed["evaluator"],
                clinical_significance=ed["clinical_significance"],
                biological_plausibility=ed.get("biological_plausibility"),
                temporal_relationship=ed.get("temporal_relationship"),
                dose_response=ed.get("dose_response"),
                dechallenge_positive=ed.get("dechallenge_positive"),
                rechallenge_positive=ed.get("rechallenge_positive"),
                alternative_explanations=ed.get("alternative_explanations"),
                literature_support=ed.get("literature_support"),
                overall_assessment=ed["overall_assessment"],
                recommendation=ed["recommendation"],
                action_items=ed.get("action_items", []),
            )

        # --- Cumulative Reviews (10) ---
        review_defs = [
            {"signal_idx": 0, "period": ReportPeriod.QUARTERLY, "cumulative": 18, "new": 5, "exposure": 1250.0, "trend": "stable", "reviewer": "Dr. James Miller", "conclusion": "Signal confirmed; rate stable over Q4"},
            {"signal_idx": 1, "period": ReportPeriod.MONTHLY, "cumulative": 7, "new": 2, "exposure": 850.0, "trend": "worsening", "reviewer": "Dr. Emily Park", "conclusion": "Increasing trend observed; expedited review recommended"},
            {"signal_idx": 3, "period": ReportPeriod.SEMI_ANNUAL, "cumulative": 45, "new": 12, "exposure": 3200.0, "trend": "stable", "reviewer": "Dr. Lisa Thompson", "conclusion": "Well-characterized ADR; incidence within expected range"},
            {"signal_idx": 5, "period": ReportPeriod.QUARTERLY, "cumulative": 22, "new": 8, "exposure": 1800.0, "trend": "worsening", "reviewer": "Dr. Robert Kim", "conclusion": "Upward trend in eosinophilia cases; dose correlation under review"},
            {"signal_idx": 7, "period": ReportPeriod.QUARTERLY, "cumulative": 12, "new": 3, "exposure": 950.0, "trend": "stable", "reviewer": "Dr. David Wilson", "conclusion": "Rate consistent with published checkpoint inhibitor data"},
            {"signal_idx": 8, "period": ReportPeriod.MONTHLY, "cumulative": 8, "new": 3, "exposure": 620.0, "trend": "worsening", "reviewer": "Dr. Maria Garcia", "conclusion": "New cases in latest month; hepatology review initiated"},
            {"signal_idx": 9, "period": ReportPeriod.QUARTERLY, "cumulative": 19, "new": 4, "exposure": 1100.0, "trend": "improving", "reviewer": "Dr. Thomas Lee", "conclusion": "Thyroid events decreasing with updated monitoring protocol"},
            {"signal_idx": 2, "period": ReportPeriod.SEMI_ANNUAL, "cumulative": 32, "new": 6, "exposure": 2800.0, "trend": "stable", "reviewer": "Dr. Michael Huang", "conclusion": "IOP elevation rates stable; existing mitigation adequate"},
            {"signal_idx": 10, "period": ReportPeriod.MONTHLY, "cumulative": 10, "new": 4, "exposure": 780.0, "trend": "worsening", "reviewer": "Dr. David Wilson", "conclusion": "Colitis cases increasing; DSMB notified"},
            {"signal_idx": 6, "period": ReportPeriod.QUARTERLY, "cumulative": 28, "new": 6, "exposure": 2100.0, "trend": "stable", "reviewer": "Dr. Anna Kowalski", "conclusion": "Arthralgia rates within expected background range"},
        ]

        for i, rd in enumerate(review_defs):
            rev_id = str(uuid4())
            review_date = now - timedelta(days=30 - i * 3)
            self._cumulative_reviews[rev_id] = CumulativeReview(
                id=rev_id,
                signal_id=signal_ids[rd["signal_idx"]],
                review_date=review_date,
                review_period=rd["period"],
                cumulative_cases=rd["cumulative"],
                new_cases_in_period=rd["new"],
                total_exposure_patient_years=rd["exposure"],
                incidence_rate=rd["cumulative"] / rd["exposure"] * 1000 if rd["exposure"] > 0 else None,
                trend=rd["trend"],
                reviewer=rd["reviewer"],
                conclusion=rd["conclusion"],
                next_review_date=review_date + timedelta(days=90),
            )

        # --- Disproportionality Analyses (10) ---
        analysis_defs = [
            {"trial_id": EYLEA_TRIAL, "name": "Eylea Q4 2025 PRR Analysis", "method": SignalMethod.PRR, "events": 2450, "signals": 3, "prr_thr": 2.0, "min_count": 3, "run_by": "Dr. Sarah Chen"},
            {"trial_id": EYLEA_TRIAL, "name": "Eylea Q4 2025 ROR Analysis", "method": SignalMethod.ROR, "events": 2450, "signals": 2, "ror_thr": 2.0, "min_count": 3, "run_by": "Pharmacovigilance Team"},
            {"trial_id": DUPIXENT_TRIAL, "name": "Dupixent H2 2025 BCPNN Screening", "method": SignalMethod.BCPNN, "events": 5800, "signals": 4, "min_count": 5, "run_by": "PRAC Signal Detection"},
            {"trial_id": DUPIXENT_TRIAL, "name": "Dupixent Q4 2025 MGPS Analysis", "method": SignalMethod.MGPS, "events": 5800, "signals": 2, "min_count": 3, "run_by": "Dr. Lisa Thompson"},
            {"trial_id": DUPIXENT_TRIAL, "name": "Dupixent Q4 2025 EBGM Screening", "method": SignalMethod.EBGM, "events": 5800, "signals": 3, "ebgm_thr": 2.0, "min_count": 3, "run_by": "Bayesian Analytics Group"},
            {"trial_id": LIBTAYO_TRIAL, "name": "Libtayo Q4 2025 PRR irAE Screening", "method": SignalMethod.PRR, "events": 1850, "signals": 4, "prr_thr": 2.0, "min_count": 3, "run_by": "Dr. David Wilson"},
            {"trial_id": LIBTAYO_TRIAL, "name": "Libtayo Q4 2025 Bayesian Analysis", "method": SignalMethod.BAYESIAN, "events": 1850, "signals": 3, "min_count": 3, "run_by": "Safety Surveillance Team"},
            {"trial_id": EYLEA_TRIAL, "name": "Eylea Q3 2025 PRR Analysis", "method": SignalMethod.PRR, "events": 2100, "signals": 2, "prr_thr": 2.0, "min_count": 3, "run_by": "Dr. Sarah Chen"},
            {"trial_id": LIBTAYO_TRIAL, "name": "Libtayo Q3 2025 Frequentist Analysis", "method": SignalMethod.FREQUENTIST, "events": 1600, "signals": 2, "min_count": 5, "run_by": "Biostatistics Team"},
            {"trial_id": DUPIXENT_TRIAL, "name": "Dupixent Q3 2025 PRR Analysis", "method": SignalMethod.PRR, "events": 5200, "signals": 3, "prr_thr": 2.0, "min_count": 3, "run_by": "Dr. Robert Kim"},
        ]

        for i, ad in enumerate(analysis_defs):
            analysis_id = str(uuid4())
            run_date = now - timedelta(days=15 + i * 10)
            self._analyses[analysis_id] = DisproportionalityAnalysis(
                id=analysis_id,
                trial_id=ad["trial_id"],
                analysis_name=ad["name"],
                method=ad["method"],
                run_date=run_date,
                data_cutoff_date=run_date - timedelta(days=7),
                total_events_analyzed=ad["events"],
                signals_detected=ad["signals"],
                threshold_prr=ad.get("prr_thr"),
                threshold_ror=ad.get("ror_thr"),
                threshold_ebgm=ad.get("ebgm_thr"),
                min_case_count=ad["min_count"],
                run_by=ad["run_by"],
                status="completed",
                report_reference=f"RPT-SSD-{2025}-{1000 + i:04d}",
            )

        # --- Aggregate Safety Reports (10) ---
        report_defs = [
            {"trial_id": EYLEA_TRIAL, "type": "DSUR", "period": ReportPeriod.ANNUAL, "subjects": 2800, "aes": 890, "saes": 45, "deaths": 2, "new_signals": 1, "ongoing": 2, "author": "Dr. Sarah Chen", "reviewer": "Dr. James Miller"},
            {"trial_id": EYLEA_TRIAL, "type": "PBRER", "period": ReportPeriod.SEMI_ANNUAL, "subjects": 2800, "aes": 450, "saes": 22, "deaths": 1, "new_signals": 0, "ongoing": 3, "author": "Pharmacovigilance Team", "reviewer": "Dr. Michael Huang"},
            {"trial_id": DUPIXENT_TRIAL, "type": "DSUR", "period": ReportPeriod.ANNUAL, "subjects": 6500, "aes": 2100, "saes": 78, "deaths": 3, "new_signals": 2, "ongoing": 3, "author": "Dr. Lisa Thompson", "reviewer": "Dr. Robert Kim"},
            {"trial_id": DUPIXENT_TRIAL, "type": "PSUR", "period": ReportPeriod.SEMI_ANNUAL, "subjects": 6500, "aes": 1050, "saes": 38, "deaths": 1, "new_signals": 1, "ongoing": 4, "author": "Global Safety Team", "reviewer": "Dr. Anna Kowalski"},
            {"trial_id": DUPIXENT_TRIAL, "type": "PBRER", "period": ReportPeriod.QUARTERLY, "subjects": 6500, "aes": 520, "saes": 19, "deaths": 0, "new_signals": 1, "ongoing": 3, "author": "Dr. Robert Kim"},
            {"trial_id": LIBTAYO_TRIAL, "type": "DSUR", "period": ReportPeriod.ANNUAL, "subjects": 1200, "aes": 680, "saes": 95, "deaths": 8, "new_signals": 3, "ongoing": 4, "author": "Dr. David Wilson", "reviewer": "Dr. Maria Garcia"},
            {"trial_id": LIBTAYO_TRIAL, "type": "PBRER", "period": ReportPeriod.SEMI_ANNUAL, "subjects": 1200, "aes": 340, "saes": 48, "deaths": 4, "new_signals": 1, "ongoing": 3, "author": "Safety Surveillance Team", "reviewer": "Dr. Thomas Lee"},
            {"trial_id": LIBTAYO_TRIAL, "type": "IND Safety Report", "period": ReportPeriod.AD_HOC, "subjects": 1200, "aes": 15, "saes": 15, "deaths": 2, "new_signals": 1, "ongoing": 0, "author": "Dr. David Wilson"},
            {"trial_id": EYLEA_TRIAL, "type": "PSUR", "period": ReportPeriod.QUARTERLY, "subjects": 2800, "aes": 225, "saes": 11, "deaths": 0, "new_signals": 0, "ongoing": 2, "author": "Dr. Michael Huang", "reviewer": "Dr. Sarah Chen"},
            {"trial_id": DUPIXENT_TRIAL, "type": "Ad Hoc Safety Review", "period": ReportPeriod.AD_HOC, "subjects": 6500, "aes": 85, "saes": 12, "deaths": 0, "new_signals": 1, "ongoing": 2, "author": "Dr. Lisa Thompson", "reviewer": "Dr. Robert Kim"},
        ]

        for i, rd in enumerate(report_defs):
            report_id = str(uuid4())
            period_end = now - timedelta(days=i * 15)
            period_days = {"annual": 365, "semi_annual": 182, "quarterly": 91, "monthly": 30, "ad_hoc": 30}
            period_start = period_end - timedelta(days=period_days.get(rd["period"].value, 90))
            self._aggregate_reports[report_id] = AggregateSafetyReport(
                id=report_id,
                trial_id=rd["trial_id"],
                report_type=rd["type"],
                period=rd["period"],
                period_start=period_start,
                period_end=period_end,
                total_subjects_exposed=rd["subjects"],
                total_aes=rd["aes"],
                total_saes=rd["saes"],
                deaths=rd["deaths"],
                new_signals=rd["new_signals"],
                ongoing_signals=rd["ongoing"],
                benefit_risk_conclusion=f"Benefit-risk balance remains favorable for {rd['type']}",
                author=rd["author"],
                reviewer=rd.get("reviewer"),
                approval_date=period_end + timedelta(days=14) if rd.get("reviewer") else None,
                submitted_date=period_end + timedelta(days=21) if rd.get("reviewer") else None,
                created_at=period_end - timedelta(days=7),
            )

    # ------------------------------------------------------------------
    # Safety Signals CRUD
    # ------------------------------------------------------------------

    def create_signal(self, payload: SafetySignalCreate) -> SafetySignal:
        now = datetime.now(timezone.utc)
        sig_id = str(uuid4())
        signal = SafetySignal(
            id=sig_id,
            trial_id=payload.trial_id,
            signal_name=payload.signal_name,
            preferred_term=payload.preferred_term,
            meddra_code=payload.meddra_code,
            soc=payload.soc,
            detection_method=payload.detection_method,
            status=SignalStatus.DETECTED,
            priority=payload.priority,
            detected_date=now,
            drug_name=payload.drug_name,
            comparator=payload.comparator,
            observed_cases=payload.observed_cases,
            expected_cases=payload.expected_cases,
            detected_by=payload.detected_by,
            created_at=now,
        )
        with self._lock:
            self._signals[sig_id] = signal
        return signal

    def get_signal(self, signal_id: str) -> SafetySignal | None:
        return self._signals.get(signal_id)

    def list_signals(self, trial_id: str | None = None) -> list[SafetySignal]:
        items = list(self._signals.values())
        if trial_id:
            items = [s for s in items if s.trial_id == trial_id]
        return items

    def update_signal(self, signal_id: str, payload: SafetySignalUpdate) -> SafetySignal | None:
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
        with self._lock:
            return self._signals.pop(signal_id, None) is not None

    # ------------------------------------------------------------------
    # Signal Evaluations CRUD
    # ------------------------------------------------------------------

    def create_evaluation(self, payload: SignalEvaluationCreate) -> SignalEvaluation:
        now = datetime.now(timezone.utc)
        eval_id = str(uuid4())
        evaluation = SignalEvaluation(
            id=eval_id,
            signal_id=payload.signal_id,
            evaluation_date=now,
            evaluator=payload.evaluator,
            clinical_significance=payload.clinical_significance,
            biological_plausibility=payload.biological_plausibility,
            temporal_relationship=payload.temporal_relationship,
            dose_response=payload.dose_response,
            overall_assessment=payload.overall_assessment,
            recommendation=payload.recommendation,
            action_items=payload.action_items,
        )
        with self._lock:
            self._evaluations[eval_id] = evaluation
        return evaluation

    def get_evaluation(self, evaluation_id: str) -> SignalEvaluation | None:
        return self._evaluations.get(evaluation_id)

    def list_evaluations(self, signal_id: str | None = None) -> list[SignalEvaluation]:
        items = list(self._evaluations.values())
        if signal_id:
            items = [e for e in items if e.signal_id == signal_id]
        return items

    def delete_evaluation(self, evaluation_id: str) -> bool:
        with self._lock:
            return self._evaluations.pop(evaluation_id, None) is not None

    # ------------------------------------------------------------------
    # Cumulative Reviews CRUD
    # ------------------------------------------------------------------

    def create_cumulative_review(self, payload: CumulativeReviewCreate) -> CumulativeReview:
        now = datetime.now(timezone.utc)
        rev_id = str(uuid4())
        review = CumulativeReview(
            id=rev_id,
            signal_id=payload.signal_id,
            review_date=now,
            review_period=payload.review_period,
            cumulative_cases=payload.cumulative_cases,
            new_cases_in_period=payload.new_cases_in_period,
            total_exposure_patient_years=payload.total_exposure_patient_years,
            incidence_rate=payload.cumulative_cases / payload.total_exposure_patient_years * 1000
            if payload.total_exposure_patient_years > 0
            else None,
            reviewer=payload.reviewer,
            conclusion=payload.conclusion,
            next_review_date=payload.next_review_date,
        )
        with self._lock:
            self._cumulative_reviews[rev_id] = review
        return review

    def get_cumulative_review(self, review_id: str) -> CumulativeReview | None:
        return self._cumulative_reviews.get(review_id)

    def list_cumulative_reviews(self, signal_id: str | None = None) -> list[CumulativeReview]:
        items = list(self._cumulative_reviews.values())
        if signal_id:
            items = [r for r in items if r.signal_id == signal_id]
        return items

    def delete_cumulative_review(self, review_id: str) -> bool:
        with self._lock:
            return self._cumulative_reviews.pop(review_id, None) is not None

    # ------------------------------------------------------------------
    # Disproportionality Analyses CRUD
    # ------------------------------------------------------------------

    def create_analysis(self, payload: DisproportionalityAnalysisCreate) -> DisproportionalityAnalysis:
        now = datetime.now(timezone.utc)
        analysis_id = str(uuid4())
        analysis = DisproportionalityAnalysis(
            id=analysis_id,
            trial_id=payload.trial_id,
            analysis_name=payload.analysis_name,
            method=payload.method,
            run_date=now,
            data_cutoff_date=payload.data_cutoff_date,
            total_events_analyzed=0,
            signals_detected=0,
            threshold_prr=payload.threshold_prr,
            threshold_ror=payload.threshold_ror,
            min_case_count=payload.min_case_count,
            run_by=payload.run_by,
            status="running",
        )
        with self._lock:
            self._analyses[analysis_id] = analysis
        return analysis

    def get_analysis(self, analysis_id: str) -> DisproportionalityAnalysis | None:
        return self._analyses.get(analysis_id)

    def list_analyses(self, trial_id: str | None = None) -> list[DisproportionalityAnalysis]:
        items = list(self._analyses.values())
        if trial_id:
            items = [a for a in items if a.trial_id == trial_id]
        return items

    def update_analysis(self, analysis_id: str, payload: DisproportionalityAnalysisUpdate) -> DisproportionalityAnalysis | None:
        with self._lock:
            existing = self._analyses.get(analysis_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DisproportionalityAnalysis(**data)
            self._analyses[analysis_id] = updated
            return updated

    def delete_analysis(self, analysis_id: str) -> bool:
        with self._lock:
            return self._analyses.pop(analysis_id, None) is not None

    # ------------------------------------------------------------------
    # Aggregate Safety Reports CRUD
    # ------------------------------------------------------------------

    def create_aggregate_report(self, payload: AggregateSafetyReportCreate) -> AggregateSafetyReport:
        now = datetime.now(timezone.utc)
        report_id = str(uuid4())
        report = AggregateSafetyReport(
            id=report_id,
            trial_id=payload.trial_id,
            report_type=payload.report_type,
            period=payload.period,
            period_start=payload.period_start,
            period_end=payload.period_end,
            total_subjects_exposed=payload.total_subjects_exposed,
            total_aes=0,
            total_saes=0,
            deaths=0,
            new_signals=0,
            ongoing_signals=0,
            author=payload.author,
            created_at=now,
        )
        with self._lock:
            self._aggregate_reports[report_id] = report
        return report

    def get_aggregate_report(self, report_id: str) -> AggregateSafetyReport | None:
        return self._aggregate_reports.get(report_id)

    def list_aggregate_reports(self, trial_id: str | None = None) -> list[AggregateSafetyReport]:
        items = list(self._aggregate_reports.values())
        if trial_id:
            items = [r for r in items if r.trial_id == trial_id]
        return items

    def update_aggregate_report(self, report_id: str, payload: AggregateSafetyReportUpdate) -> AggregateSafetyReport | None:
        with self._lock:
            existing = self._aggregate_reports.get(report_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = AggregateSafetyReport(**data)
            self._aggregate_reports[report_id] = updated
            return updated

    def delete_aggregate_report(self, report_id: str) -> bool:
        with self._lock:
            return self._aggregate_reports.pop(report_id, None) is not None

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> SafetySignalMetrics:
        signals = list(self._signals.values())
        evaluations = list(self._evaluations.values())
        reviews = list(self._cumulative_reviews.values())
        analyses = list(self._analyses.values())
        reports = list(self._aggregate_reports.values())

        signals_by_status: dict[str, int] = {}
        signals_by_priority: dict[str, int] = {}
        signals_by_method: dict[str, int] = {}
        confirmed = 0
        for s in signals:
            signals_by_status[s.status.value] = signals_by_status.get(s.status.value, 0) + 1
            signals_by_priority[s.priority.value] = signals_by_priority.get(s.priority.value, 0) + 1
            signals_by_method[s.detection_method.value] = signals_by_method.get(s.detection_method.value, 0) + 1
            if s.status == SignalStatus.CONFIRMED:
                confirmed += 1

        evaluations_by_causality: dict[str, int] = {}
        for e in evaluations:
            evaluations_by_causality[e.overall_assessment.value] = evaluations_by_causality.get(e.overall_assessment.value, 0) + 1

        reports_by_period: dict[str, int] = {}
        for r in reports:
            reports_by_period[r.period.value] = reports_by_period.get(r.period.value, 0) + 1

        # Calculate average signal-to-evaluation days
        avg_days = 0.0
        matched = 0
        for e in evaluations:
            sig = self._signals.get(e.signal_id)
            if sig is None:
                # signal_id might not be a key; check all signals
                for s in signals:
                    if s.id == e.signal_id:
                        sig = s
                        break
            if sig:
                delta = (e.evaluation_date - sig.detected_date).total_seconds() / 86400
                avg_days += delta
                matched += 1
        if matched > 0:
            avg_days = avg_days / matched

        return SafetySignalMetrics(
            total_signals=len(signals),
            signals_by_status=signals_by_status,
            signals_by_priority=signals_by_priority,
            signals_by_method=signals_by_method,
            confirmed_signals=confirmed,
            total_evaluations=len(evaluations),
            evaluations_by_causality=evaluations_by_causality,
            total_cumulative_reviews=len(reviews),
            total_analyses=len(analyses),
            total_aggregate_reports=len(reports),
            reports_by_period=reports_by_period,
            avg_signal_to_evaluation_days=round(max(avg_days, 0), 2),
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: SafetySignalDetectionService | None = None
_instance_lock = threading.Lock()


def get_safety_signal_detection_service() -> SafetySignalDetectionService:
    """Return the singleton SafetySignalDetectionService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = SafetySignalDetectionService()
    return _instance


def reset_safety_signal_detection_service() -> SafetySignalDetectionService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = SafetySignalDetectionService()
    return _instance
