"""Adaptive Trial Design Management Service (ADAPT-TRIAL).

Manages adaptive trial design operations: interim analysis tracking,
adaptation decision records, sample size re-estimation, futility
assessments, treatment arm modifications, and adaptive trial metrics.

Usage:
    from app.services.adaptive_trial_service import (
        get_adaptive_trial_service,
    )

    svc = get_adaptive_trial_service()
    analyses = svc.list_interim_analyses()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.adaptive_trial import (
    AdaptationDecision,
    AdaptationDecisionCreate,
    AdaptationDecisionUpdate,
    AdaptationType,
    AdaptiveTrialMetrics,
    AnalysisOutcome,
    AnalysisType,
    DecisionStatus,
    FutilityAssessment,
    FutilityAssessmentCreate,
    FutilityAssessmentUpdate,
    FutilityResult,
    InterimAnalysis,
    InterimAnalysisCreate,
    InterimAnalysisUpdate,
    SampleSizeReestimation,
    SampleSizeReestimationCreate,
    SampleSizeReestimationUpdate,
    TreatmentArmModification,
    TreatmentArmModificationCreate,
    TreatmentArmModificationUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class AdaptiveTrialService:
    """In-memory Adaptive Trial Design engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._interim_analyses: dict[str, InterimAnalysis] = {}
        self._adaptation_decisions: dict[str, AdaptationDecision] = {}
        self._sample_size_reestimations: dict[str, SampleSizeReestimation] = {}
        self._futility_assessments: dict[str, FutilityAssessment] = {}
        self._treatment_arm_modifications: dict[str, TreatmentArmModification] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic adaptive trial design data."""
        now = datetime.now(timezone.utc)

        # --- 12 Interim Analyses ---
        analyses_data = [
            {
                "id": "IA-001",
                "trial_id": EYLEA_TRIAL,
                "analysis_number": 1,
                "analysis_type": AnalysisType.INTERIM,
                "planned_date": now - timedelta(days=180),
                "actual_date": now - timedelta(days=178),
                "information_fraction": 0.25,
                "subjects_analyzed": 75,
                "events_observed": 18,
                "outcome": AnalysisOutcome.CONTINUE,
                "alpha_spent": 0.001,
                "cumulative_alpha": 0.001,
                "spending_function": "OBrien-Fleming",
                "test_statistic": 1.45,
                "p_value": 0.074,
                "boundary_value": 4.33,
                "conditional_power": 0.72,
                "performed_by": "Dr. Sarah Chen",
                "dsmb_reviewed": True,
                "notes": "First interim analysis. Efficacy trend favorable but below boundary.",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "IA-002",
                "trial_id": EYLEA_TRIAL,
                "analysis_number": 2,
                "analysis_type": AnalysisType.INTERIM,
                "planned_date": now - timedelta(days=120),
                "actual_date": now - timedelta(days=118),
                "information_fraction": 0.50,
                "subjects_analyzed": 150,
                "events_observed": 42,
                "outcome": AnalysisOutcome.CONTINUE,
                "alpha_spent": 0.005,
                "cumulative_alpha": 0.006,
                "spending_function": "OBrien-Fleming",
                "test_statistic": 2.18,
                "p_value": 0.015,
                "boundary_value": 2.96,
                "conditional_power": 0.85,
                "performed_by": "Dr. Sarah Chen",
                "dsmb_reviewed": True,
                "notes": "Second interim. Strong efficacy signal. Conditional power exceeds threshold.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "IA-003",
                "trial_id": EYLEA_TRIAL,
                "analysis_number": 3,
                "analysis_type": AnalysisType.SAFETY,
                "planned_date": now - timedelta(days=90),
                "actual_date": now - timedelta(days=89),
                "information_fraction": 0.60,
                "subjects_analyzed": 180,
                "events_observed": 8,
                "outcome": AnalysisOutcome.CONTINUE,
                "alpha_spent": 0.0,
                "cumulative_alpha": 0.006,
                "spending_function": "OBrien-Fleming",
                "test_statistic": None,
                "p_value": None,
                "boundary_value": None,
                "conditional_power": None,
                "performed_by": "Dr. James Wright",
                "dsmb_reviewed": True,
                "notes": "Safety analysis. No concerning safety signals identified.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "IA-004",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_number": 1,
                "analysis_type": AnalysisType.FUTILITY,
                "planned_date": now - timedelta(days=150),
                "actual_date": now - timedelta(days=148),
                "information_fraction": 0.30,
                "subjects_analyzed": 90,
                "events_observed": 22,
                "outcome": AnalysisOutcome.CONTINUE,
                "alpha_spent": 0.0,
                "cumulative_alpha": 0.0,
                "spending_function": "Lan-DeMets",
                "test_statistic": 0.95,
                "p_value": 0.171,
                "boundary_value": 0.50,
                "conditional_power": 0.55,
                "performed_by": "Dr. Maria Lopez",
                "dsmb_reviewed": True,
                "notes": "Futility analysis at 30%. Conditional power marginal but above futility boundary.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "IA-005",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_number": 2,
                "analysis_type": AnalysisType.INTERIM,
                "planned_date": now - timedelta(days=90),
                "actual_date": now - timedelta(days=88),
                "information_fraction": 0.50,
                "subjects_analyzed": 150,
                "events_observed": 38,
                "outcome": AnalysisOutcome.MODIFY,
                "alpha_spent": 0.004,
                "cumulative_alpha": 0.004,
                "spending_function": "Lan-DeMets",
                "test_statistic": 1.82,
                "p_value": 0.034,
                "boundary_value": 2.80,
                "conditional_power": 0.68,
                "performed_by": "Dr. Maria Lopez",
                "dsmb_reviewed": True,
                "notes": "Interim 2. Sample size re-estimation recommended due to variance higher than assumed.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "IA-006",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_number": 3,
                "analysis_type": AnalysisType.SAMPLE_SIZE_REESTIMATION,
                "planned_date": now - timedelta(days=60),
                "actual_date": now - timedelta(days=58),
                "information_fraction": 0.55,
                "subjects_analyzed": 165,
                "events_observed": 44,
                "outcome": AnalysisOutcome.MODIFY,
                "alpha_spent": 0.0,
                "cumulative_alpha": 0.004,
                "spending_function": "Lan-DeMets",
                "test_statistic": None,
                "p_value": None,
                "boundary_value": None,
                "conditional_power": 0.62,
                "performed_by": "Dr. Robert Kim",
                "dsmb_reviewed": True,
                "notes": "Sample size re-estimation performed. Recommended increase from 300 to 360.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "IA-007",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_number": 1,
                "analysis_type": AnalysisType.INTERIM,
                "planned_date": now - timedelta(days=200),
                "actual_date": now - timedelta(days=198),
                "information_fraction": 0.25,
                "subjects_analyzed": 100,
                "events_observed": 30,
                "outcome": AnalysisOutcome.CONTINUE,
                "alpha_spent": 0.001,
                "cumulative_alpha": 0.001,
                "spending_function": "OBrien-Fleming",
                "test_statistic": 1.20,
                "p_value": 0.115,
                "boundary_value": 4.33,
                "conditional_power": 0.60,
                "performed_by": "Dr. Angela Park",
                "dsmb_reviewed": True,
                "notes": "First interim for LIBTAYO. Treatment effect modest at early stage.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "IA-008",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_number": 2,
                "analysis_type": AnalysisType.DOSE_SELECTION,
                "planned_date": now - timedelta(days=140),
                "actual_date": now - timedelta(days=138),
                "information_fraction": 0.40,
                "subjects_analyzed": 160,
                "events_observed": 48,
                "outcome": AnalysisOutcome.MODIFY,
                "alpha_spent": 0.0,
                "cumulative_alpha": 0.001,
                "spending_function": "OBrien-Fleming",
                "test_statistic": None,
                "p_value": None,
                "boundary_value": None,
                "conditional_power": None,
                "performed_by": "Dr. Angela Park",
                "dsmb_reviewed": True,
                "notes": "Dose selection analysis. Low dose arm underperforming; drop recommended.",
                "created_at": now - timedelta(days=140),
            },
            {
                "id": "IA-009",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_number": 3,
                "analysis_type": AnalysisType.EFFICACY,
                "planned_date": now - timedelta(days=70),
                "actual_date": now - timedelta(days=68),
                "information_fraction": 0.65,
                "subjects_analyzed": 260,
                "events_observed": 82,
                "outcome": AnalysisOutcome.CONTINUE,
                "alpha_spent": 0.010,
                "cumulative_alpha": 0.011,
                "spending_function": "OBrien-Fleming",
                "test_statistic": 2.55,
                "p_value": 0.005,
                "boundary_value": 2.58,
                "conditional_power": 0.91,
                "performed_by": "Dr. Angela Park",
                "dsmb_reviewed": True,
                "notes": "Efficacy analysis post arm drop. Strong signal in remaining arms.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "IA-010",
                "trial_id": EYLEA_TRIAL,
                "analysis_number": 4,
                "analysis_type": AnalysisType.INTERIM,
                "planned_date": now - timedelta(days=30),
                "actual_date": now - timedelta(days=28),
                "information_fraction": 0.75,
                "subjects_analyzed": 225,
                "events_observed": 68,
                "outcome": AnalysisOutcome.STOP_EFFICACY,
                "alpha_spent": 0.018,
                "cumulative_alpha": 0.024,
                "spending_function": "OBrien-Fleming",
                "test_statistic": 3.12,
                "p_value": 0.0009,
                "boundary_value": 2.36,
                "conditional_power": 0.98,
                "performed_by": "Dr. Sarah Chen",
                "dsmb_reviewed": True,
                "notes": "Crossed efficacy boundary. DSMB recommended early stopping for efficacy.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "IA-011",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_number": 4,
                "analysis_type": AnalysisType.INTERIM,
                "planned_date": now - timedelta(days=15),
                "actual_date": None,
                "information_fraction": 0.0,
                "subjects_analyzed": 0,
                "events_observed": 0,
                "outcome": AnalysisOutcome.PENDING,
                "alpha_spent": 0.0,
                "cumulative_alpha": 0.004,
                "spending_function": "Lan-DeMets",
                "test_statistic": None,
                "p_value": None,
                "boundary_value": None,
                "conditional_power": None,
                "performed_by": "Dr. Maria Lopez",
                "dsmb_reviewed": False,
                "notes": None,
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "IA-012",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_number": 4,
                "analysis_type": AnalysisType.SAFETY,
                "planned_date": now + timedelta(days=10),
                "actual_date": None,
                "information_fraction": 0.0,
                "subjects_analyzed": 0,
                "events_observed": 0,
                "outcome": AnalysisOutcome.PENDING,
                "alpha_spent": 0.0,
                "cumulative_alpha": 0.011,
                "spending_function": "OBrien-Fleming",
                "test_statistic": None,
                "p_value": None,
                "boundary_value": None,
                "conditional_power": None,
                "performed_by": "Dr. James Wright",
                "dsmb_reviewed": False,
                "notes": None,
                "created_at": now - timedelta(days=5),
            },
        ]

        for a in analyses_data:
            self._interim_analyses[a["id"]] = InterimAnalysis(**a)

        # --- 10 Adaptation Decisions ---
        decisions_data = [
            {
                "id": "AD-001",
                "trial_id": EYLEA_TRIAL,
                "analysis_id": "IA-002",
                "adaptation_type": AdaptationType.POPULATION_ENRICHMENT,
                "status": DecisionStatus.IMPLEMENTED,
                "decision_date": now - timedelta(days=115),
                "rationale": "Subgroup analysis at interim 2 showed enhanced treatment effect in patients with baseline BCVA < 50 letters. Enrichment to improve power.",
                "proposed_change": "Amend eligibility to enrich for patients with baseline BCVA 20-50 ETDRS letters",
                "impact_assessment": "Expected 15% increase in effect size with minimal impact on generalizability",
                "regulatory_notification_required": True,
                "regulatory_notified": True,
                "protocol_amendment_required": True,
                "amendment_id": "AMD-EYLEA-003",
                "proposed_by": "Dr. Sarah Chen",
                "approved_by": "Dr. William Torres",
                "approval_date": now - timedelta(days=110),
                "implementation_date": now - timedelta(days=100),
                "notes": "FDA notified via Type B amendment. No objection received.",
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "AD-002",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_id": "IA-005",
                "adaptation_type": AdaptationType.SAMPLE_SIZE,
                "status": DecisionStatus.IMPLEMENTED,
                "decision_date": now - timedelta(days=85),
                "rationale": "Observed variance at interim 2 is 20% higher than assumed. Sample size increase needed to maintain 80% power.",
                "proposed_change": "Increase total sample size from 300 to 360 (20% increase)",
                "impact_assessment": "Extends enrollment by approximately 3 months. Budget increase of $2.1M.",
                "regulatory_notification_required": True,
                "regulatory_notified": True,
                "protocol_amendment_required": True,
                "amendment_id": "AMD-DUP-002",
                "proposed_by": "Dr. Maria Lopez",
                "approved_by": "Dr. David Patel",
                "approval_date": now - timedelta(days=80),
                "implementation_date": now - timedelta(days=70),
                "notes": "Blinded sample size re-estimation using CHW method.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "AD-003",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_id": "IA-008",
                "adaptation_type": AdaptationType.TREATMENT_ARM_DROP,
                "status": DecisionStatus.IMPLEMENTED,
                "decision_date": now - timedelta(days=135),
                "rationale": "Low dose arm (200mg Q3W) shows futility with conditional power < 20%. High dose arm (350mg Q3W) shows promising efficacy.",
                "proposed_change": "Drop the 200mg Q3W arm. Continue enrollment in 350mg Q3W and placebo arms.",
                "impact_assessment": "39 subjects in low dose arm to be offered crossover to high dose. Net enrollment reduction of ~60 subjects.",
                "regulatory_notification_required": True,
                "regulatory_notified": True,
                "protocol_amendment_required": True,
                "amendment_id": "AMD-LIB-004",
                "proposed_by": "Dr. Angela Park",
                "approved_by": "Dr. William Torres",
                "approval_date": now - timedelta(days=130),
                "implementation_date": now - timedelta(days=120),
                "notes": "Subjects in dropped arm offered transition to high dose per DSMB recommendation.",
                "created_at": now - timedelta(days=135),
            },
            {
                "id": "AD-004",
                "trial_id": EYLEA_TRIAL,
                "analysis_id": "IA-010",
                "adaptation_type": AdaptationType.ENDPOINT_CHANGE,
                "status": DecisionStatus.APPROVED,
                "decision_date": now - timedelta(days=25),
                "rationale": "Early stopping for efficacy triggered. Need to formalize primary endpoint analysis window.",
                "proposed_change": "Confirm primary endpoint at Week 48 with final analysis at current data cut.",
                "impact_assessment": "No change to primary endpoint definition; timing advanced by 3 months.",
                "regulatory_notification_required": True,
                "regulatory_notified": False,
                "protocol_amendment_required": False,
                "amendment_id": None,
                "proposed_by": "Dr. Sarah Chen",
                "approved_by": "Dr. William Torres",
                "approval_date": now - timedelta(days=20),
                "implementation_date": None,
                "notes": "Pending regulatory notification before implementation.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "AD-005",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_id": "IA-006",
                "adaptation_type": AdaptationType.RANDOMIZATION_RATIO,
                "status": DecisionStatus.IMPLEMENTED,
                "decision_date": now - timedelta(days=55),
                "rationale": "Response-adaptive randomization based on interim results. Active arm showing 2:1 benefit.",
                "proposed_change": "Change randomization ratio from 1:1 to 2:1 (active:placebo) for remaining enrollment",
                "impact_assessment": "Ethically favorable; increases exposure to active treatment. Minimal impact on power.",
                "regulatory_notification_required": True,
                "regulatory_notified": True,
                "protocol_amendment_required": True,
                "amendment_id": "AMD-DUP-003",
                "proposed_by": "Dr. Robert Kim",
                "approved_by": "Dr. David Patel",
                "approval_date": now - timedelta(days=50),
                "implementation_date": now - timedelta(days=45),
                "notes": "IRB approved. Implemented via IVRS update.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "AD-006",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_id": "IA-009",
                "adaptation_type": AdaptationType.TREATMENT_ARM_ADD,
                "status": DecisionStatus.UNDER_REVIEW,
                "decision_date": now - timedelta(days=10),
                "rationale": "Strong efficacy in 350mg arm suggests combination therapy arm may provide additional benefit.",
                "proposed_change": "Add combination arm: LIBTAYO 350mg Q3W + ipilimumab 1mg/kg Q6W",
                "impact_assessment": "Additional 80 subjects needed. Extends trial by ~6 months.",
                "regulatory_notification_required": True,
                "regulatory_notified": False,
                "protocol_amendment_required": True,
                "amendment_id": None,
                "proposed_by": "Dr. Angela Park",
                "approved_by": None,
                "approval_date": None,
                "implementation_date": None,
                "notes": "Under DSMB and steering committee review.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "AD-007",
                "trial_id": EYLEA_TRIAL,
                "analysis_id": "IA-001",
                "adaptation_type": AdaptationType.DOSE_MODIFICATION,
                "status": DecisionStatus.REJECTED,
                "decision_date": now - timedelta(days=175),
                "rationale": "Proposed dose escalation to improve response in non-responders at interim 1.",
                "proposed_change": "Allow dose escalation from 2mg to 4mg for non-responders after Week 12",
                "impact_assessment": "Would add complexity to protocol and confound primary analysis.",
                "regulatory_notification_required": False,
                "regulatory_notified": False,
                "protocol_amendment_required": True,
                "amendment_id": None,
                "proposed_by": "Dr. James Wright",
                "approved_by": None,
                "approval_date": None,
                "implementation_date": None,
                "notes": "Rejected by steering committee. Insufficient evidence to support dose modification.",
                "created_at": now - timedelta(days=175),
            },
            {
                "id": "AD-008",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_id": None,
                "adaptation_type": AdaptationType.ENDPOINT_CHANGE,
                "status": DecisionStatus.DEFERRED,
                "decision_date": now - timedelta(days=40),
                "rationale": "Consideration to add PRO-based secondary endpoint given strong patient-reported outcomes data.",
                "proposed_change": "Add DLQI as co-primary endpoint",
                "impact_assessment": "Would require statistical plan amendment and potentially larger sample size.",
                "regulatory_notification_required": True,
                "regulatory_notified": False,
                "protocol_amendment_required": True,
                "amendment_id": None,
                "proposed_by": "Dr. Robert Kim",
                "approved_by": None,
                "approval_date": None,
                "implementation_date": None,
                "notes": "Deferred pending next interim analysis results. Revisit at IA-011.",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "AD-009",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_id": "IA-007",
                "adaptation_type": AdaptationType.SAMPLE_SIZE,
                "status": DecisionStatus.PROPOSED,
                "decision_date": now - timedelta(days=5),
                "rationale": "Post arm-drop power analysis suggests modest sample size increase needed for remaining comparison.",
                "proposed_change": "Increase per-arm sample size from 160 to 180 for remaining arms",
                "impact_assessment": "Adds approximately 40 subjects total. 2-month enrollment extension.",
                "regulatory_notification_required": False,
                "regulatory_notified": False,
                "protocol_amendment_required": False,
                "amendment_id": None,
                "proposed_by": "Dr. Angela Park",
                "approved_by": None,
                "approval_date": None,
                "implementation_date": None,
                "notes": "Within pre-specified adaptive design bounds. No amendment needed.",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "AD-010",
                "trial_id": EYLEA_TRIAL,
                "analysis_id": "IA-003",
                "adaptation_type": AdaptationType.DOSE_MODIFICATION,
                "status": DecisionStatus.IMPLEMENTED,
                "decision_date": now - timedelta(days=85),
                "rationale": "Safety analysis identified higher rate of injection-site reactions in Q4W arm. Dose interval modification recommended.",
                "proposed_change": "Modify Q4W arm to Q6W dosing after loading phase to reduce injection burden",
                "impact_assessment": "May reduce dropout rate by 10%. Minimal efficacy impact based on PK modeling.",
                "regulatory_notification_required": True,
                "regulatory_notified": True,
                "protocol_amendment_required": True,
                "amendment_id": "AMD-EYLEA-004",
                "proposed_by": "Dr. James Wright",
                "approved_by": "Dr. William Torres",
                "approval_date": now - timedelta(days=80),
                "implementation_date": now - timedelta(days=75),
                "notes": "Implemented after FDA agreement. PK bridging data submitted.",
                "created_at": now - timedelta(days=85),
            },
        ]

        for d in decisions_data:
            self._adaptation_decisions[d["id"]] = AdaptationDecision(**d)

        # --- 10 Sample Size Re-estimations ---
        ssr_data = [
            {
                "id": "SSR-001",
                "trial_id": EYLEA_TRIAL,
                "analysis_id": "IA-001",
                "reestimation_date": now - timedelta(days=175),
                "original_sample_size": 300,
                "observed_effect_size": 0.32,
                "assumed_effect_size": 0.35,
                "observed_variance": 1.05,
                "new_sample_size": 300,
                "change_pct": 0.0,
                "target_power": 0.80,
                "method": "CHW",
                "blinded": True,
                "statistician": "Dr. Sarah Chen",
                "approved_by": "Dr. William Torres",
                "notes": "No change needed. Observed parameters consistent with assumptions.",
                "created_at": now - timedelta(days=175),
            },
            {
                "id": "SSR-002",
                "trial_id": EYLEA_TRIAL,
                "analysis_id": "IA-002",
                "reestimation_date": now - timedelta(days=115),
                "original_sample_size": 300,
                "observed_effect_size": 0.38,
                "assumed_effect_size": 0.35,
                "observed_variance": 1.02,
                "new_sample_size": 280,
                "change_pct": -6.7,
                "target_power": 0.80,
                "method": "CHW",
                "blinded": True,
                "statistician": "Dr. Sarah Chen",
                "approved_by": "Dr. William Torres",
                "notes": "Effect size larger than assumed. Could reduce sample size but maintaining original for robustness.",
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "SSR-003",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_id": "IA-004",
                "reestimation_date": now - timedelta(days=145),
                "original_sample_size": 300,
                "observed_effect_size": 0.28,
                "assumed_effect_size": 0.35,
                "observed_variance": 1.15,
                "new_sample_size": 340,
                "change_pct": 13.3,
                "target_power": 0.80,
                "method": "CHW",
                "blinded": True,
                "statistician": "Dr. Maria Lopez",
                "approved_by": None,
                "notes": "First signal of underpowering. Monitoring closely before formal increase.",
                "created_at": now - timedelta(days=145),
            },
            {
                "id": "SSR-004",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_id": "IA-005",
                "reestimation_date": now - timedelta(days=85),
                "original_sample_size": 300,
                "observed_effect_size": 0.30,
                "assumed_effect_size": 0.35,
                "observed_variance": 1.22,
                "new_sample_size": 360,
                "change_pct": 20.0,
                "target_power": 0.80,
                "method": "CHW",
                "blinded": True,
                "statistician": "Dr. Maria Lopez",
                "approved_by": "Dr. David Patel",
                "notes": "Formal re-estimation confirms 20% increase needed. Approved by steering committee.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "SSR-005",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_id": "IA-006",
                "reestimation_date": now - timedelta(days=55),
                "original_sample_size": 360,
                "observed_effect_size": 0.31,
                "assumed_effect_size": 0.35,
                "observed_variance": 1.18,
                "new_sample_size": 360,
                "change_pct": 0.0,
                "target_power": 0.80,
                "method": "CHW",
                "blinded": True,
                "statistician": "Dr. Robert Kim",
                "approved_by": "Dr. David Patel",
                "notes": "Re-estimation with updated N=360 baseline. No further increase needed.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "SSR-006",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_id": "IA-007",
                "reestimation_date": now - timedelta(days=195),
                "original_sample_size": 400,
                "observed_effect_size": 0.25,
                "assumed_effect_size": 0.30,
                "observed_variance": 1.10,
                "new_sample_size": 420,
                "change_pct": 5.0,
                "target_power": 0.80,
                "method": "Promising Zone",
                "blinded": True,
                "statistician": "Dr. Angela Park",
                "approved_by": None,
                "notes": "Early re-estimation. Slight increase in promising zone but not yet acted upon.",
                "created_at": now - timedelta(days=195),
            },
            {
                "id": "SSR-007",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_id": "IA-008",
                "reestimation_date": now - timedelta(days=135),
                "original_sample_size": 400,
                "observed_effect_size": None,
                "assumed_effect_size": 0.30,
                "observed_variance": None,
                "new_sample_size": 340,
                "change_pct": -15.0,
                "target_power": 0.80,
                "method": "Promising Zone",
                "blinded": False,
                "statistician": "Dr. Angela Park",
                "approved_by": "Dr. William Torres",
                "notes": "Post arm-drop re-estimation. Two-arm comparison requires fewer subjects.",
                "created_at": now - timedelta(days=135),
            },
            {
                "id": "SSR-008",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_id": "IA-009",
                "reestimation_date": now - timedelta(days=65),
                "original_sample_size": 340,
                "observed_effect_size": 0.38,
                "assumed_effect_size": 0.30,
                "observed_variance": 0.98,
                "new_sample_size": 320,
                "change_pct": -5.9,
                "target_power": 0.90,
                "method": "Promising Zone",
                "blinded": True,
                "statistician": "Dr. Angela Park",
                "approved_by": "Dr. William Torres",
                "notes": "Strong effect allows slight reduction even with increased power target (90%).",
                "created_at": now - timedelta(days=65),
            },
            {
                "id": "SSR-009",
                "trial_id": EYLEA_TRIAL,
                "analysis_id": "IA-010",
                "reestimation_date": now - timedelta(days=25),
                "original_sample_size": 300,
                "observed_effect_size": 0.45,
                "assumed_effect_size": 0.35,
                "observed_variance": 0.95,
                "new_sample_size": 225,
                "change_pct": -25.0,
                "target_power": 0.80,
                "method": "CHW",
                "blinded": False,
                "statistician": "Dr. Sarah Chen",
                "approved_by": "Dr. William Torres",
                "notes": "Early stopping triggered. Final analysis at N=225.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "SSR-010",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_id": None,
                "reestimation_date": now - timedelta(days=10),
                "original_sample_size": 360,
                "observed_effect_size": 0.33,
                "assumed_effect_size": 0.35,
                "observed_variance": 1.12,
                "new_sample_size": 370,
                "change_pct": 2.8,
                "target_power": 0.80,
                "method": "CHW",
                "blinded": True,
                "statistician": "Dr. Robert Kim",
                "approved_by": None,
                "notes": "Latest re-estimation. Minor increase; within pre-specified cap.",
                "created_at": now - timedelta(days=10),
            },
        ]

        for s in ssr_data:
            self._sample_size_reestimations[s["id"]] = SampleSizeReestimation(**s)

        # --- 10 Futility Assessments ---
        futility_data = [
            {
                "id": "FA-001",
                "trial_id": EYLEA_TRIAL,
                "analysis_id": "IA-001",
                "assessment_date": now - timedelta(days=178),
                "futility_boundary": 0.20,
                "observed_statistic": 1.45,
                "conditional_power": 0.72,
                "predictive_probability": 0.78,
                "result": FutilityResult.NOT_FUTILE,
                "recommendation": "Continue enrollment. Conditional power well above futility threshold.",
                "information_fraction": 0.25,
                "subjects_at_assessment": 75,
                "assessed_by": "Dr. Sarah Chen",
                "dsmb_concurrence": True,
                "notes": "Clear signal to continue.",
                "created_at": now - timedelta(days=178),
            },
            {
                "id": "FA-002",
                "trial_id": EYLEA_TRIAL,
                "analysis_id": "IA-002",
                "assessment_date": now - timedelta(days=118),
                "futility_boundary": 0.20,
                "observed_statistic": 2.18,
                "conditional_power": 0.85,
                "predictive_probability": 0.88,
                "result": FutilityResult.NOT_FUTILE,
                "recommendation": "Strong efficacy trajectory. No futility concern.",
                "information_fraction": 0.50,
                "subjects_at_assessment": 150,
                "assessed_by": "Dr. Sarah Chen",
                "dsmb_concurrence": True,
                "notes": None,
                "created_at": now - timedelta(days=118),
            },
            {
                "id": "FA-003",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_id": "IA-004",
                "assessment_date": now - timedelta(days=148),
                "futility_boundary": 0.20,
                "observed_statistic": 0.95,
                "conditional_power": 0.55,
                "predictive_probability": 0.60,
                "result": FutilityResult.NOT_FUTILE,
                "recommendation": "Continue with enhanced monitoring. Conditional power above threshold but warrants close surveillance.",
                "information_fraction": 0.30,
                "subjects_at_assessment": 90,
                "assessed_by": "Dr. Maria Lopez",
                "dsmb_concurrence": True,
                "notes": "Marginal but above futility boundary. Sample size re-estimation triggered.",
                "created_at": now - timedelta(days=148),
            },
            {
                "id": "FA-004",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_id": "IA-005",
                "assessment_date": now - timedelta(days=88),
                "futility_boundary": 0.20,
                "observed_statistic": 1.82,
                "conditional_power": 0.68,
                "predictive_probability": 0.72,
                "result": FutilityResult.NOT_FUTILE,
                "recommendation": "Continue. Sample size re-estimation addresses power concerns.",
                "information_fraction": 0.50,
                "subjects_at_assessment": 150,
                "assessed_by": "Dr. Maria Lopez",
                "dsmb_concurrence": True,
                "notes": "Improved since last assessment. SSR expected to restore adequate power.",
                "created_at": now - timedelta(days=88),
            },
            {
                "id": "FA-005",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_id": "IA-007",
                "assessment_date": now - timedelta(days=198),
                "futility_boundary": 0.15,
                "observed_statistic": 1.20,
                "conditional_power": 0.60,
                "predictive_probability": 0.65,
                "result": FutilityResult.NOT_FUTILE,
                "recommendation": "Continue enrollment across all arms. Early stage; expect improvement with larger N.",
                "information_fraction": 0.25,
                "subjects_at_assessment": 100,
                "assessed_by": "Dr. Angela Park",
                "dsmb_concurrence": True,
                "notes": None,
                "created_at": now - timedelta(days=198),
            },
            {
                "id": "FA-006",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_id": "IA-008",
                "assessment_date": now - timedelta(days=138),
                "futility_boundary": 0.15,
                "observed_statistic": 0.42,
                "conditional_power": 0.12,
                "predictive_probability": 0.15,
                "result": FutilityResult.FUTILE,
                "recommendation": "Low dose arm (200mg Q3W) meets futility criteria. Recommend arm discontinuation.",
                "information_fraction": 0.40,
                "subjects_at_assessment": 160,
                "assessed_by": "Dr. Angela Park",
                "dsmb_concurrence": True,
                "notes": "Arm-specific futility. High dose arm remains viable.",
                "created_at": now - timedelta(days=138),
            },
            {
                "id": "FA-007",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_id": "IA-009",
                "assessment_date": now - timedelta(days=68),
                "futility_boundary": 0.15,
                "observed_statistic": 2.55,
                "conditional_power": 0.91,
                "predictive_probability": 0.93,
                "result": FutilityResult.NOT_FUTILE,
                "recommendation": "Post arm-drop assessment. Remaining arms show strong efficacy. No futility concern.",
                "information_fraction": 0.65,
                "subjects_at_assessment": 260,
                "assessed_by": "Dr. Angela Park",
                "dsmb_concurrence": True,
                "notes": "Robust treatment effect in high dose vs placebo.",
                "created_at": now - timedelta(days=68),
            },
            {
                "id": "FA-008",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_id": "IA-006",
                "assessment_date": now - timedelta(days=58),
                "futility_boundary": 0.20,
                "observed_statistic": 1.65,
                "conditional_power": 0.62,
                "predictive_probability": 0.68,
                "result": FutilityResult.POSSIBLY_FUTILE,
                "recommendation": "Borderline. Continue with increased sample size. Re-assess at next interim.",
                "information_fraction": 0.55,
                "subjects_at_assessment": 165,
                "assessed_by": "Dr. Robert Kim",
                "dsmb_concurrence": True,
                "notes": "Conditional power recovering with SSR. Close monitoring advised.",
                "created_at": now - timedelta(days=58),
            },
            {
                "id": "FA-009",
                "trial_id": EYLEA_TRIAL,
                "analysis_id": "IA-010",
                "assessment_date": now - timedelta(days=28),
                "futility_boundary": 0.20,
                "observed_statistic": 3.12,
                "conditional_power": 0.98,
                "predictive_probability": 0.99,
                "result": FutilityResult.NOT_FUTILE,
                "recommendation": "Overwhelmingly positive. Efficacy boundary crossed; futility not a concern.",
                "information_fraction": 0.75,
                "subjects_at_assessment": 225,
                "assessed_by": "Dr. Sarah Chen",
                "dsmb_concurrence": True,
                "notes": "Final futility assessment. Trial stopping for efficacy.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "FA-010",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_id": None,
                "assessment_date": now - timedelta(days=3),
                "futility_boundary": 0.15,
                "observed_statistic": None,
                "conditional_power": 0.0,
                "predictive_probability": 0.0,
                "result": FutilityResult.NOT_FUTILE,
                "recommendation": "Planned assessment. Awaiting data lock.",
                "information_fraction": 0.0,
                "subjects_at_assessment": 0,
                "assessed_by": "Dr. Angela Park",
                "dsmb_concurrence": None,
                "notes": "Pending next scheduled interim analysis.",
                "created_at": now - timedelta(days=3),
            },
        ]

        for f in futility_data:
            self._futility_assessments[f["id"]] = FutilityAssessment(**f)

        # --- 10 Treatment Arm Modifications ---
        tam_data = [
            {
                "id": "TAM-001",
                "trial_id": LIBTAYO_TRIAL,
                "decision_id": "AD-003",
                "arm_name": "LIBTAYO 200mg Q3W",
                "modification_type": "drop",
                "modification_date": now - timedelta(days=120),
                "reason": "Futility at interim analysis 2. Conditional power < 20% for low dose arm.",
                "subjects_affected": 39,
                "subjects_reassigned": 28,
                "new_allocation_ratio": "1:1",
                "previous_allocation_ratio": "1:1:1",
                "effective_date": now - timedelta(days=118),
                "regulatory_approved": True,
                "irb_approved": True,
                "modified_by": "Dr. Angela Park",
                "notes": "28 of 39 subjects opted for crossover to high dose arm.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "TAM-002",
                "trial_id": LIBTAYO_TRIAL,
                "decision_id": "AD-003",
                "arm_name": "LIBTAYO 350mg Q3W",
                "modification_type": "enrich",
                "modification_date": now - timedelta(days=120),
                "reason": "Receiving crossover subjects from dropped 200mg arm.",
                "subjects_affected": 0,
                "subjects_reassigned": 28,
                "new_allocation_ratio": "1:1",
                "previous_allocation_ratio": "1:1:1",
                "effective_date": now - timedelta(days=118),
                "regulatory_approved": True,
                "irb_approved": True,
                "modified_by": "Dr. Angela Park",
                "notes": "Crossover subjects analyzed separately per ITT.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "TAM-003",
                "trial_id": DUPIXENT_TRIAL,
                "decision_id": "AD-005",
                "arm_name": "DUPIXENT Active",
                "modification_type": "ratio_change",
                "modification_date": now - timedelta(days=45),
                "reason": "Response-adaptive randomization showing 2:1 benefit for active arm.",
                "subjects_affected": 0,
                "subjects_reassigned": 0,
                "new_allocation_ratio": "2:1",
                "previous_allocation_ratio": "1:1",
                "effective_date": now - timedelta(days=43),
                "regulatory_approved": True,
                "irb_approved": True,
                "modified_by": "Dr. Robert Kim",
                "notes": "Applies to new enrollments only. Existing subjects unaffected.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "TAM-004",
                "trial_id": DUPIXENT_TRIAL,
                "decision_id": "AD-005",
                "arm_name": "Placebo",
                "modification_type": "ratio_change",
                "modification_date": now - timedelta(days=45),
                "reason": "Corresponding reduction in placebo allocation with 2:1 randomization.",
                "subjects_affected": 0,
                "subjects_reassigned": 0,
                "new_allocation_ratio": "2:1",
                "previous_allocation_ratio": "1:1",
                "effective_date": now - timedelta(days=43),
                "regulatory_approved": True,
                "irb_approved": True,
                "modified_by": "Dr. Robert Kim",
                "notes": "Ethical advantage: fewer subjects exposed to placebo.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "TAM-005",
                "trial_id": EYLEA_TRIAL,
                "decision_id": "AD-010",
                "arm_name": "EYLEA Q4W",
                "modification_type": "dose_interval",
                "modification_date": now - timedelta(days=75),
                "reason": "Higher rate of injection-site reactions. Extending dose interval to Q6W post loading.",
                "subjects_affected": 95,
                "subjects_reassigned": 0,
                "new_allocation_ratio": None,
                "previous_allocation_ratio": None,
                "effective_date": now - timedelta(days=73),
                "regulatory_approved": True,
                "irb_approved": True,
                "modified_by": "Dr. James Wright",
                "notes": "PK bridging data supports Q6W dosing after loading phase.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "TAM-006",
                "trial_id": EYLEA_TRIAL,
                "decision_id": "AD-001",
                "arm_name": "EYLEA Q8W",
                "modification_type": "population_enrichment",
                "modification_date": now - timedelta(days=100),
                "reason": "Enrichment for patients with baseline BCVA 20-50 ETDRS letters.",
                "subjects_affected": 0,
                "subjects_reassigned": 0,
                "new_allocation_ratio": None,
                "previous_allocation_ratio": None,
                "effective_date": now - timedelta(days=98),
                "regulatory_approved": True,
                "irb_approved": True,
                "modified_by": "Dr. Sarah Chen",
                "notes": "New enrollment criteria applied. Existing subjects continue per original protocol.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "TAM-007",
                "trial_id": LIBTAYO_TRIAL,
                "decision_id": "AD-006",
                "arm_name": "LIBTAYO 350mg + Ipilimumab",
                "modification_type": "add",
                "modification_date": now - timedelta(days=8),
                "reason": "Combination arm addition based on strong monotherapy efficacy.",
                "subjects_affected": 0,
                "subjects_reassigned": 0,
                "new_allocation_ratio": "1:1:1",
                "previous_allocation_ratio": "1:1",
                "effective_date": None,
                "regulatory_approved": False,
                "irb_approved": False,
                "modified_by": "Dr. Angela Park",
                "notes": "Pending regulatory and IRB approval.",
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "TAM-008",
                "trial_id": EYLEA_TRIAL,
                "decision_id": None,
                "arm_name": "EYLEA Q4W (original)",
                "modification_type": "close",
                "modification_date": now - timedelta(days=28),
                "reason": "Trial stopping for efficacy. Enrollment closure.",
                "subjects_affected": 225,
                "subjects_reassigned": 0,
                "new_allocation_ratio": None,
                "previous_allocation_ratio": None,
                "effective_date": now - timedelta(days=26),
                "regulatory_approved": True,
                "irb_approved": True,
                "modified_by": "Dr. Sarah Chen",
                "notes": "All arms closed to new enrollment. Subjects continue follow-up.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "TAM-009",
                "trial_id": EYLEA_TRIAL,
                "decision_id": None,
                "arm_name": "Placebo",
                "modification_type": "close",
                "modification_date": now - timedelta(days=28),
                "reason": "Trial stopping for efficacy. Placebo subjects offered open-label active treatment.",
                "subjects_affected": 75,
                "subjects_reassigned": 68,
                "new_allocation_ratio": None,
                "previous_allocation_ratio": None,
                "effective_date": now - timedelta(days=26),
                "regulatory_approved": True,
                "irb_approved": True,
                "modified_by": "Dr. Sarah Chen",
                "notes": "68 of 75 placebo subjects opted for open-label EYLEA.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "TAM-010",
                "trial_id": DUPIXENT_TRIAL,
                "decision_id": None,
                "arm_name": "DUPIXENT Active (high responders)",
                "modification_type": "substratification",
                "modification_date": now - timedelta(days=35),
                "reason": "Stratify high-responders for sub-study within active arm.",
                "subjects_affected": 45,
                "subjects_reassigned": 0,
                "new_allocation_ratio": None,
                "previous_allocation_ratio": None,
                "effective_date": now - timedelta(days=33),
                "regulatory_approved": True,
                "irb_approved": True,
                "modified_by": "Dr. Maria Lopez",
                "notes": "Sub-study to characterize biomarker profile of high responders.",
                "created_at": now - timedelta(days=35),
            },
        ]

        for t in tam_data:
            self._treatment_arm_modifications[t["id"]] = TreatmentArmModification(**t)

    # ------------------------------------------------------------------
    # Interim Analyses
    # ------------------------------------------------------------------

    def list_interim_analyses(
        self,
        *,
        trial_id: str | None = None,
        analysis_type: AnalysisType | None = None,
        outcome: AnalysisOutcome | None = None,
    ) -> list[InterimAnalysis]:
        """List interim analyses with optional filters."""
        with self._lock:
            result = list(self._interim_analyses.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if analysis_type is not None:
            result = [a for a in result if a.analysis_type == analysis_type]
        if outcome is not None:
            result = [a for a in result if a.outcome == outcome]

        return sorted(result, key=lambda a: a.planned_date, reverse=True)

    def get_interim_analysis(self, analysis_id: str) -> InterimAnalysis | None:
        """Get a single interim analysis by ID."""
        with self._lock:
            return self._interim_analyses.get(analysis_id)

    def create_interim_analysis(self, payload: InterimAnalysisCreate) -> InterimAnalysis:
        """Create a new interim analysis."""
        now = datetime.now(timezone.utc)
        analysis_id = f"IA-{uuid4().hex[:8].upper()}"
        analysis = InterimAnalysis(
            id=analysis_id,
            trial_id=payload.trial_id,
            analysis_number=payload.analysis_number,
            analysis_type=payload.analysis_type,
            planned_date=payload.planned_date,
            actual_date=None,
            information_fraction=0.0,
            subjects_analyzed=0,
            events_observed=0,
            outcome=AnalysisOutcome.PENDING,
            alpha_spent=0.0,
            cumulative_alpha=0.0,
            spending_function=payload.spending_function,
            test_statistic=None,
            p_value=None,
            boundary_value=None,
            conditional_power=None,
            performed_by=payload.performed_by,
            dsmb_reviewed=False,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._interim_analyses[analysis_id] = analysis
        logger.info("Created interim analysis %s for trial %s", analysis_id, payload.trial_id)
        return analysis

    def update_interim_analysis(
        self, analysis_id: str, payload: InterimAnalysisUpdate
    ) -> InterimAnalysis | None:
        """Update an existing interim analysis."""
        with self._lock:
            existing = self._interim_analyses.get(analysis_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = InterimAnalysis(**data)
            self._interim_analyses[analysis_id] = updated
        return updated

    def delete_interim_analysis(self, analysis_id: str) -> bool:
        """Delete an interim analysis. Returns True if deleted."""
        with self._lock:
            if analysis_id in self._interim_analyses:
                del self._interim_analyses[analysis_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Adaptation Decisions
    # ------------------------------------------------------------------

    def list_adaptation_decisions(
        self,
        *,
        trial_id: str | None = None,
        adaptation_type: AdaptationType | None = None,
        status: DecisionStatus | None = None,
    ) -> list[AdaptationDecision]:
        """List adaptation decisions with optional filters."""
        with self._lock:
            result = list(self._adaptation_decisions.values())

        if trial_id is not None:
            result = [d for d in result if d.trial_id == trial_id]
        if adaptation_type is not None:
            result = [d for d in result if d.adaptation_type == adaptation_type]
        if status is not None:
            result = [d for d in result if d.status == status]

        return sorted(result, key=lambda d: d.decision_date, reverse=True)

    def get_adaptation_decision(self, decision_id: str) -> AdaptationDecision | None:
        """Get a single adaptation decision by ID."""
        with self._lock:
            return self._adaptation_decisions.get(decision_id)

    def create_adaptation_decision(self, payload: AdaptationDecisionCreate) -> AdaptationDecision:
        """Create a new adaptation decision."""
        now = datetime.now(timezone.utc)
        decision_id = f"AD-{uuid4().hex[:8].upper()}"
        decision = AdaptationDecision(
            id=decision_id,
            trial_id=payload.trial_id,
            analysis_id=payload.analysis_id,
            adaptation_type=payload.adaptation_type,
            status=DecisionStatus.PROPOSED,
            decision_date=now,
            rationale=payload.rationale,
            proposed_change=payload.proposed_change,
            impact_assessment=None,
            regulatory_notification_required=False,
            regulatory_notified=False,
            protocol_amendment_required=False,
            amendment_id=None,
            proposed_by=payload.proposed_by,
            approved_by=None,
            approval_date=None,
            implementation_date=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._adaptation_decisions[decision_id] = decision
        logger.info("Created adaptation decision %s for trial %s", decision_id, payload.trial_id)
        return decision

    def update_adaptation_decision(
        self, decision_id: str, payload: AdaptationDecisionUpdate
    ) -> AdaptationDecision | None:
        """Update an existing adaptation decision."""
        with self._lock:
            existing = self._adaptation_decisions.get(decision_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = AdaptationDecision(**data)
            self._adaptation_decisions[decision_id] = updated
        return updated

    def delete_adaptation_decision(self, decision_id: str) -> bool:
        """Delete an adaptation decision. Returns True if deleted."""
        with self._lock:
            if decision_id in self._adaptation_decisions:
                del self._adaptation_decisions[decision_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Sample Size Re-estimations
    # ------------------------------------------------------------------

    def list_sample_size_reestimations(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[SampleSizeReestimation]:
        """List sample size re-estimations with optional filters."""
        with self._lock:
            result = list(self._sample_size_reestimations.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]

        return sorted(result, key=lambda s: s.reestimation_date, reverse=True)

    def get_sample_size_reestimation(self, reestimation_id: str) -> SampleSizeReestimation | None:
        """Get a single sample size re-estimation by ID."""
        with self._lock:
            return self._sample_size_reestimations.get(reestimation_id)

    def create_sample_size_reestimation(
        self, payload: SampleSizeReestimationCreate
    ) -> SampleSizeReestimation:
        """Create a new sample size re-estimation."""
        now = datetime.now(timezone.utc)
        ssr_id = f"SSR-{uuid4().hex[:8].upper()}"
        ssr = SampleSizeReestimation(
            id=ssr_id,
            trial_id=payload.trial_id,
            analysis_id=payload.analysis_id,
            reestimation_date=now,
            original_sample_size=payload.original_sample_size,
            observed_effect_size=None,
            assumed_effect_size=None,
            observed_variance=None,
            new_sample_size=0,
            change_pct=0.0,
            target_power=payload.target_power,
            method="CHW",
            blinded=True,
            statistician=payload.statistician,
            approved_by=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._sample_size_reestimations[ssr_id] = ssr
        logger.info("Created sample size re-estimation %s for trial %s", ssr_id, payload.trial_id)
        return ssr

    def update_sample_size_reestimation(
        self, reestimation_id: str, payload: SampleSizeReestimationUpdate
    ) -> SampleSizeReestimation | None:
        """Update an existing sample size re-estimation."""
        with self._lock:
            existing = self._sample_size_reestimations.get(reestimation_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SampleSizeReestimation(**data)
            self._sample_size_reestimations[reestimation_id] = updated
        return updated

    def delete_sample_size_reestimation(self, reestimation_id: str) -> bool:
        """Delete a sample size re-estimation. Returns True if deleted."""
        with self._lock:
            if reestimation_id in self._sample_size_reestimations:
                del self._sample_size_reestimations[reestimation_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Futility Assessments
    # ------------------------------------------------------------------

    def list_futility_assessments(
        self,
        *,
        trial_id: str | None = None,
        result: FutilityResult | None = None,
    ) -> list[FutilityAssessment]:
        """List futility assessments with optional filters."""
        with self._lock:
            items = list(self._futility_assessments.values())

        if trial_id is not None:
            items = [f for f in items if f.trial_id == trial_id]
        if result is not None:
            items = [f for f in items if f.result == result]

        return sorted(items, key=lambda f: f.assessment_date, reverse=True)

    def get_futility_assessment(self, assessment_id: str) -> FutilityAssessment | None:
        """Get a single futility assessment by ID."""
        with self._lock:
            return self._futility_assessments.get(assessment_id)

    def create_futility_assessment(self, payload: FutilityAssessmentCreate) -> FutilityAssessment:
        """Create a new futility assessment."""
        now = datetime.now(timezone.utc)
        fa_id = f"FA-{uuid4().hex[:8].upper()}"
        fa = FutilityAssessment(
            id=fa_id,
            trial_id=payload.trial_id,
            analysis_id=payload.analysis_id,
            assessment_date=now,
            futility_boundary=None,
            observed_statistic=None,
            conditional_power=payload.conditional_power,
            predictive_probability=0.0,
            result=FutilityResult.NOT_FUTILE,
            recommendation=payload.recommendation,
            information_fraction=0.0,
            subjects_at_assessment=0,
            assessed_by=payload.assessed_by,
            dsmb_concurrence=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._futility_assessments[fa_id] = fa
        logger.info("Created futility assessment %s for trial %s", fa_id, payload.trial_id)
        return fa

    def update_futility_assessment(
        self, assessment_id: str, payload: FutilityAssessmentUpdate
    ) -> FutilityAssessment | None:
        """Update an existing futility assessment."""
        with self._lock:
            existing = self._futility_assessments.get(assessment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = FutilityAssessment(**data)
            self._futility_assessments[assessment_id] = updated
        return updated

    def delete_futility_assessment(self, assessment_id: str) -> bool:
        """Delete a futility assessment. Returns True if deleted."""
        with self._lock:
            if assessment_id in self._futility_assessments:
                del self._futility_assessments[assessment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Treatment Arm Modifications
    # ------------------------------------------------------------------

    def list_treatment_arm_modifications(
        self,
        *,
        trial_id: str | None = None,
        modification_type: str | None = None,
    ) -> list[TreatmentArmModification]:
        """List treatment arm modifications with optional filters."""
        with self._lock:
            result = list(self._treatment_arm_modifications.values())

        if trial_id is not None:
            result = [t for t in result if t.trial_id == trial_id]
        if modification_type is not None:
            result = [t for t in result if t.modification_type == modification_type]

        return sorted(result, key=lambda t: t.modification_date, reverse=True)

    def get_treatment_arm_modification(
        self, modification_id: str
    ) -> TreatmentArmModification | None:
        """Get a single treatment arm modification by ID."""
        with self._lock:
            return self._treatment_arm_modifications.get(modification_id)

    def create_treatment_arm_modification(
        self, payload: TreatmentArmModificationCreate
    ) -> TreatmentArmModification:
        """Create a new treatment arm modification."""
        now = datetime.now(timezone.utc)
        tam_id = f"TAM-{uuid4().hex[:8].upper()}"
        tam = TreatmentArmModification(
            id=tam_id,
            trial_id=payload.trial_id,
            decision_id=payload.decision_id,
            arm_name=payload.arm_name,
            modification_type=payload.modification_type,
            modification_date=now,
            reason=payload.reason,
            subjects_affected=payload.subjects_affected,
            subjects_reassigned=0,
            new_allocation_ratio=None,
            previous_allocation_ratio=None,
            effective_date=None,
            regulatory_approved=False,
            irb_approved=False,
            modified_by=payload.modified_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._treatment_arm_modifications[tam_id] = tam
        logger.info("Created treatment arm modification %s for trial %s", tam_id, payload.trial_id)
        return tam

    def update_treatment_arm_modification(
        self, modification_id: str, payload: TreatmentArmModificationUpdate
    ) -> TreatmentArmModification | None:
        """Update an existing treatment arm modification."""
        with self._lock:
            existing = self._treatment_arm_modifications.get(modification_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = TreatmentArmModification(**data)
            self._treatment_arm_modifications[modification_id] = updated
        return updated

    def delete_treatment_arm_modification(self, modification_id: str) -> bool:
        """Delete a treatment arm modification. Returns True if deleted."""
        with self._lock:
            if modification_id in self._treatment_arm_modifications:
                del self._treatment_arm_modifications[modification_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> AdaptiveTrialMetrics:
        """Compute aggregated adaptive trial design metrics."""
        with self._lock:
            analyses = list(self._interim_analyses.values())
            decisions = list(self._adaptation_decisions.values())
            reestimations = list(self._sample_size_reestimations.values())
            futility_items = list(self._futility_assessments.values())
            arm_mods = list(self._treatment_arm_modifications.values())

        # Analyses by type
        analyses_by_type: dict[str, int] = {}
        for a in analyses:
            key = a.analysis_type.value
            analyses_by_type[key] = analyses_by_type.get(key, 0) + 1

        # Analyses by outcome
        analyses_by_outcome: dict[str, int] = {}
        for a in analyses:
            key = a.outcome.value
            analyses_by_outcome[key] = analyses_by_outcome.get(key, 0) + 1

        # Adaptations by type
        adaptations_by_type: dict[str, int] = {}
        for d in decisions:
            key = d.adaptation_type.value
            adaptations_by_type[key] = adaptations_by_type.get(key, 0) + 1

        # Adaptations by status
        adaptations_by_status: dict[str, int] = {}
        for d in decisions:
            key = d.status.value
            adaptations_by_status[key] = adaptations_by_status.get(key, 0) + 1

        # Implemented adaptations
        implemented = sum(1 for d in decisions if d.status == DecisionStatus.IMPLEMENTED)

        # Average sample size change
        change_pcts = [r.change_pct for r in reestimations if r.change_pct != 0.0]
        avg_change = round(sum(change_pcts) / max(1, len(change_pcts)), 1) if change_pcts else 0.0

        # Futility by result
        futility_by_result: dict[str, int] = {}
        for f in futility_items:
            key = f.result.value
            futility_by_result[key] = futility_by_result.get(key, 0) + 1

        # Arms dropped / added
        arms_dropped = sum(1 for t in arm_mods if t.modification_type == "drop")
        arms_added = sum(1 for t in arm_mods if t.modification_type == "add")

        return AdaptiveTrialMetrics(
            total_interim_analyses=len(analyses),
            analyses_by_type=analyses_by_type,
            analyses_by_outcome=analyses_by_outcome,
            total_adaptations=len(decisions),
            adaptations_by_type=adaptations_by_type,
            adaptations_by_status=adaptations_by_status,
            implemented_adaptations=implemented,
            total_reestimations=len(reestimations),
            avg_sample_size_change_pct=avg_change,
            total_futility_assessments=len(futility_items),
            futility_by_result=futility_by_result,
            total_arm_modifications=len(arm_mods),
            arms_dropped=arms_dropped,
            arms_added=arms_added,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: AdaptiveTrialService | None = None
_instance_lock = threading.Lock()


def get_adaptive_trial_service() -> AdaptiveTrialService:
    """Return the singleton AdaptiveTrialService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = AdaptiveTrialService()
    return _instance


def reset_adaptive_trial_service() -> AdaptiveTrialService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = AdaptiveTrialService()
    return _instance
