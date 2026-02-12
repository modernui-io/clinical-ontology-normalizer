"""Biostatistics Operations (BIOSTATS-OPS) Management Service.

Manages biostatistical operations: interim analysis planning, adaptive design
decisions, multiplicity adjustments, statistical report generation, futility
assessments, and biostatistics operational metrics.

Usage:
    from app.services.biostatistics_ops_service import (
        get_biostatistics_ops_service,
    )

    svc = get_biostatistics_ops_service()
    analyses = svc.list_analyses()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.biostatistics_ops import (
    AdaptiveDecision,
    AdaptiveDecisionCreate,
    AnalysisStatus,
    AnalysisType,
    BiostatisticsMetrics,
    BlindingLevel,
    DecisionOutcome,
    FutilityAssessment,
    FutilityAssessmentCreate,
    InterimAnalysis,
    InterimAnalysisCreate,
    InterimAnalysisUpdate,
    MultiplicityAdjustment,
    MultiplicityAdjustmentCreate,
    MultiplicityAdjustmentUpdate,
    MultiplicityMethod,
    ReportType,
    StatisticalReport,
    StatisticalReportCreate,
    StatisticalReportUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class BiostatisticsOpsService:
    """In-memory Biostatistics Operations engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._analyses: dict[str, InterimAnalysis] = {}
        self._decisions: dict[str, AdaptiveDecision] = {}
        self._adjustments: dict[str, MultiplicityAdjustment] = {}
        self._reports: dict[str, StatisticalReport] = {}
        self._futility_assessments: dict[str, FutilityAssessment] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic biostatistics data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- Interim Analyses (12 records) ---
        analyses_data = [
            # EYLEA trial analyses
            {
                "id": "IA-001",
                "trial_id": EYLEA_TRIAL,
                "analysis_number": 1,
                "analysis_type": AnalysisType.INTERIM,
                "information_fraction": 0.25,
                "planned_date": now - timedelta(days=180),
                "actual_date": now - timedelta(days=178),
                "data_cutoff_date": now - timedelta(days=185),
                "status": AnalysisStatus.COMPLETED,
                "subjects_enrolled": 450,
                "subjects_analyzed": 420,
                "events_observed": 105,
                "events_required": 420,
                "alpha_spent": 0.003,
                "alpha_remaining": 0.047,
                "spending_function": "OBrien-Fleming",
                "lead_statistician": "Dr. Karen Mitchell",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "IA-002",
                "trial_id": EYLEA_TRIAL,
                "analysis_number": 2,
                "analysis_type": AnalysisType.INTERIM,
                "information_fraction": 0.50,
                "planned_date": now - timedelta(days=90),
                "actual_date": now - timedelta(days=88),
                "data_cutoff_date": now - timedelta(days=95),
                "status": AnalysisStatus.COMPLETED,
                "subjects_enrolled": 450,
                "subjects_analyzed": 445,
                "events_observed": 210,
                "events_required": 420,
                "alpha_spent": 0.014,
                "alpha_remaining": 0.036,
                "spending_function": "OBrien-Fleming",
                "lead_statistician": "Dr. Karen Mitchell",
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "IA-003",
                "trial_id": EYLEA_TRIAL,
                "analysis_number": 3,
                "analysis_type": AnalysisType.INTERIM,
                "information_fraction": 0.75,
                "planned_date": now + timedelta(days=30),
                "status": AnalysisStatus.PLANNED,
                "subjects_enrolled": 450,
                "subjects_analyzed": 0,
                "events_observed": 0,
                "events_required": 420,
                "spending_function": "OBrien-Fleming",
                "lead_statistician": "Dr. Karen Mitchell",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "IA-004",
                "trial_id": EYLEA_TRIAL,
                "analysis_number": 4,
                "analysis_type": AnalysisType.FINAL,
                "information_fraction": 1.0,
                "planned_date": now + timedelta(days=120),
                "status": AnalysisStatus.PLANNED,
                "subjects_enrolled": 450,
                "subjects_analyzed": 0,
                "events_observed": 0,
                "events_required": 420,
                "spending_function": "OBrien-Fleming",
                "lead_statistician": "Dr. Karen Mitchell",
                "created_at": now - timedelta(days=50),
            },
            # DUPIXENT trial analyses
            {
                "id": "IA-005",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_number": 1,
                "analysis_type": AnalysisType.INTERIM,
                "information_fraction": 0.33,
                "planned_date": now - timedelta(days=150),
                "actual_date": now - timedelta(days=148),
                "data_cutoff_date": now - timedelta(days=155),
                "status": AnalysisStatus.COMPLETED,
                "subjects_enrolled": 600,
                "subjects_analyzed": 580,
                "events_observed": 195,
                "events_required": 585,
                "alpha_spent": 0.005,
                "alpha_remaining": 0.045,
                "spending_function": "Lan-DeMets",
                "lead_statistician": "Dr. Robert Zhang",
                "created_at": now - timedelta(days=170),
            },
            {
                "id": "IA-006",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_number": 2,
                "analysis_type": AnalysisType.INTERIM,
                "information_fraction": 0.67,
                "planned_date": now - timedelta(days=45),
                "actual_date": now - timedelta(days=43),
                "data_cutoff_date": now - timedelta(days=50),
                "status": AnalysisStatus.QC_REVIEW,
                "subjects_enrolled": 600,
                "subjects_analyzed": 598,
                "events_observed": 390,
                "events_required": 585,
                "alpha_spent": 0.018,
                "alpha_remaining": 0.032,
                "spending_function": "Lan-DeMets",
                "lead_statistician": "Dr. Robert Zhang",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "IA-007",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_number": 1,
                "analysis_type": AnalysisType.SAFETY,
                "information_fraction": 0.50,
                "planned_date": now - timedelta(days=100),
                "actual_date": now - timedelta(days=98),
                "data_cutoff_date": now - timedelta(days=105),
                "status": AnalysisStatus.REPORTED,
                "subjects_enrolled": 600,
                "subjects_analyzed": 590,
                "events_observed": 42,
                "events_required": 0,
                "lead_statistician": "Dr. Lisa Park",
                "created_at": now - timedelta(days=120),
            },
            # LIBTAYO trial analyses
            {
                "id": "IA-008",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_number": 1,
                "analysis_type": AnalysisType.INTERIM,
                "information_fraction": 0.40,
                "planned_date": now - timedelta(days=120),
                "actual_date": now - timedelta(days=118),
                "data_cutoff_date": now - timedelta(days=125),
                "status": AnalysisStatus.COMPLETED,
                "subjects_enrolled": 350,
                "subjects_analyzed": 340,
                "events_observed": 102,
                "events_required": 255,
                "alpha_spent": 0.008,
                "alpha_remaining": 0.042,
                "spending_function": "Pocock",
                "lead_statistician": "Dr. Amanda Torres",
                "created_at": now - timedelta(days=140),
            },
            {
                "id": "IA-009",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_number": 2,
                "analysis_type": AnalysisType.ADAPTIVE,
                "information_fraction": 0.60,
                "planned_date": now - timedelta(days=30),
                "actual_date": now - timedelta(days=28),
                "data_cutoff_date": now - timedelta(days=35),
                "status": AnalysisStatus.IN_ANALYSIS,
                "subjects_enrolled": 350,
                "subjects_analyzed": 348,
                "events_observed": 153,
                "events_required": 255,
                "alpha_spent": 0.020,
                "alpha_remaining": 0.030,
                "spending_function": "Pocock",
                "lead_statistician": "Dr. Amanda Torres",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "IA-010",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_number": 1,
                "analysis_type": AnalysisType.FUTILITY,
                "information_fraction": 0.40,
                "planned_date": now - timedelta(days=120),
                "actual_date": now - timedelta(days=118),
                "data_cutoff_date": now - timedelta(days=125),
                "status": AnalysisStatus.COMPLETED,
                "subjects_enrolled": 350,
                "subjects_analyzed": 340,
                "events_observed": 102,
                "events_required": 255,
                "lead_statistician": "Dr. Amanda Torres",
                "created_at": now - timedelta(days=140),
            },
            {
                "id": "IA-011",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_number": 1,
                "analysis_type": AnalysisType.SUBGROUP,
                "information_fraction": 0.60,
                "planned_date": now - timedelta(days=30),
                "actual_date": now - timedelta(days=28),
                "data_cutoff_date": now - timedelta(days=35),
                "status": AnalysisStatus.COMPLETED,
                "subjects_enrolled": 350,
                "subjects_analyzed": 200,
                "events_observed": 90,
                "events_required": 0,
                "lead_statistician": "Dr. Amanda Torres",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "IA-012",
                "trial_id": EYLEA_TRIAL,
                "analysis_number": 1,
                "analysis_type": AnalysisType.SENSITIVITY,
                "information_fraction": 0.50,
                "planned_date": now - timedelta(days=90),
                "actual_date": now - timedelta(days=88),
                "data_cutoff_date": now - timedelta(days=95),
                "status": AnalysisStatus.COMPLETED,
                "subjects_enrolled": 450,
                "subjects_analyzed": 445,
                "events_observed": 210,
                "events_required": 0,
                "lead_statistician": "Dr. Karen Mitchell",
                "created_at": now - timedelta(days=110),
            },
        ]

        for a in analyses_data:
            self._analyses[a["id"]] = InterimAnalysis(**a)

        # --- Adaptive Decisions (12 records) ---
        decisions_data = [
            {
                "id": "AD-001",
                "analysis_id": "IA-001",
                "decision_date": now - timedelta(days=175),
                "outcome": DecisionOutcome.CONTINUE,
                "rationale": "First interim shows promising trend. Continue enrollment per protocol. O'Brien-Fleming boundary not crossed.",
                "conditional_power": 0.82,
                "predictive_probability": 0.78,
                "p_value": 0.08,
                "test_statistic": 1.75,
                "boundary_value": 3.36,
                "crossed_boundary": False,
                "blinding_level": BlindingLevel.UNBLINDED,
                "decided_by": "Dr. Karen Mitchell",
                "dsmb_recommendation": "Continue study without modification",
            },
            {
                "id": "AD-002",
                "analysis_id": "IA-002",
                "decision_date": now - timedelta(days=85),
                "outcome": DecisionOutcome.CONTINUE,
                "rationale": "Second interim shows strong efficacy signal. Conditional power exceeds 90%. Continue to third interim.",
                "conditional_power": 0.94,
                "predictive_probability": 0.91,
                "p_value": 0.012,
                "test_statistic": 2.51,
                "boundary_value": 2.44,
                "crossed_boundary": True,
                "blinding_level": BlindingLevel.UNBLINDED,
                "decided_by": "Dr. Karen Mitchell",
                "dsmb_recommendation": "Efficacy boundary crossed. Consider early stopping for efficacy at next DSMB.",
            },
            {
                "id": "AD-003",
                "analysis_id": "IA-005",
                "decision_date": now - timedelta(days=145),
                "outcome": DecisionOutcome.CONTINUE,
                "rationale": "First interim for Dupixent atopic dermatitis trial. EASI-75 response rate encouraging. Continue enrollment.",
                "conditional_power": 0.76,
                "predictive_probability": 0.72,
                "p_value": 0.045,
                "test_statistic": 2.01,
                "boundary_value": 3.71,
                "crossed_boundary": False,
                "blinding_level": BlindingLevel.UNBLINDED,
                "decided_by": "Dr. Robert Zhang",
                "dsmb_recommendation": "Continue study per protocol",
            },
            {
                "id": "AD-004",
                "analysis_id": "IA-006",
                "decision_date": now - timedelta(days=40),
                "outcome": DecisionOutcome.EXPAND_ENROLLMENT,
                "rationale": "Second interim shows efficacy in subgroup. Recommend expanding enrollment in high-dose arm by 50 subjects.",
                "conditional_power": 0.85,
                "predictive_probability": 0.80,
                "p_value": 0.022,
                "test_statistic": 2.29,
                "boundary_value": 2.56,
                "crossed_boundary": False,
                "blinding_level": BlindingLevel.UNBLINDED,
                "decided_by": "Dr. Robert Zhang",
                "dsmb_recommendation": "Expand high-dose arm enrollment. No safety concerns.",
            },
            {
                "id": "AD-005",
                "analysis_id": "IA-008",
                "decision_date": now - timedelta(days=115),
                "outcome": DecisionOutcome.CONTINUE,
                "rationale": "Libtayo first interim. ORR encouraging. PFS trend positive. Continue per protocol.",
                "conditional_power": 0.70,
                "predictive_probability": 0.65,
                "p_value": 0.068,
                "test_statistic": 1.83,
                "boundary_value": 2.80,
                "crossed_boundary": False,
                "blinding_level": BlindingLevel.UNBLINDED,
                "decided_by": "Dr. Amanda Torres",
                "dsmb_recommendation": "Continue. Monitor safety closely.",
            },
            {
                "id": "AD-006",
                "analysis_id": "IA-009",
                "decision_date": now - timedelta(days=25),
                "outcome": DecisionOutcome.MODIFY_DOSE,
                "rationale": "Adaptive analysis suggests higher dose arm showing superior response. Modify dose allocation ratio to 2:1 favoring high dose.",
                "conditional_power": 0.88,
                "predictive_probability": 0.84,
                "p_value": 0.018,
                "test_statistic": 2.37,
                "boundary_value": 2.56,
                "crossed_boundary": False,
                "blinding_level": BlindingLevel.PARTIALLY_UNBLINDED,
                "decided_by": "Dr. Amanda Torres",
                "dsmb_recommendation": "Modify dose allocation. Close low-dose futile arm.",
            },
            {
                "id": "AD-007",
                "analysis_id": "IA-010",
                "decision_date": now - timedelta(days=115),
                "outcome": DecisionOutcome.CONTINUE,
                "rationale": "Futility analysis does not meet stopping boundary. Conditional power adequate to continue.",
                "conditional_power": 0.65,
                "predictive_probability": 0.60,
                "p_value": 0.10,
                "boundary_value": 0.20,
                "crossed_boundary": False,
                "blinding_level": BlindingLevel.BLINDED_AGGREGATE,
                "decided_by": "Dr. Amanda Torres",
                "dsmb_recommendation": "Continue study. Futility boundary not crossed.",
            },
            {
                "id": "AD-008",
                "analysis_id": "IA-001",
                "decision_date": now - timedelta(days=174),
                "outcome": DecisionOutcome.CONTINUE,
                "rationale": "Safety review at first interim. No unexpected safety signals. Continue without modification.",
                "blinding_level": BlindingLevel.BLINDED_AGGREGATE,
                "decided_by": "Dr. Sarah Hoffman",
                "dsmb_recommendation": "No safety concerns identified",
            },
            {
                "id": "AD-009",
                "analysis_id": "IA-007",
                "decision_date": now - timedelta(days=95),
                "outcome": DecisionOutcome.CONTINUE,
                "rationale": "Safety analysis complete. AE rates within expected range. No dose-limiting toxicities in Dupixent arms.",
                "blinding_level": BlindingLevel.UNBLINDED,
                "decided_by": "Dr. Lisa Park",
                "dsmb_recommendation": "Continue. Safety profile acceptable.",
            },
            {
                "id": "AD-010",
                "analysis_id": "IA-002",
                "decision_date": now - timedelta(days=84),
                "outcome": DecisionOutcome.STOP_EFFICACY,
                "rationale": "Efficacy boundary crossed at second interim. Overwhelming evidence of superiority. Recommend early stopping for efficacy.",
                "conditional_power": 0.99,
                "predictive_probability": 0.98,
                "p_value": 0.001,
                "test_statistic": 3.29,
                "boundary_value": 2.44,
                "crossed_boundary": True,
                "blinding_level": BlindingLevel.UNBLINDED,
                "decided_by": "Dr. Karen Mitchell",
                "dsmb_recommendation": "Recommend early termination for overwhelming efficacy.",
            },
            {
                "id": "AD-011",
                "analysis_id": "IA-009",
                "decision_date": now - timedelta(days=24),
                "outcome": DecisionOutcome.REDUCE_SAMPLE,
                "rationale": "Conditional power exceeds 95%. Can reduce planned sample size from 350 to 300 while maintaining adequate power.",
                "conditional_power": 0.96,
                "predictive_probability": 0.93,
                "blinding_level": BlindingLevel.UNBLINDED,
                "decided_by": "Dr. Amanda Torres",
            },
            {
                "id": "AD-012",
                "analysis_id": "IA-005",
                "decision_date": now - timedelta(days=144),
                "outcome": DecisionOutcome.STOP_SAFETY,
                "rationale": "Elevated hepatotoxicity signal in high-dose subgroup. Recommend pausing high-dose arm pending safety review.",
                "blinding_level": BlindingLevel.UNBLINDED,
                "decided_by": "Dr. Lisa Park",
                "dsmb_recommendation": "Pause high-dose arm. Convene emergency safety review.",
            },
        ]

        for d in decisions_data:
            self._decisions[d["id"]] = AdaptiveDecision(**d)

        # --- Multiplicity Adjustments (10 records) ---
        adjustments_data = [
            {
                "id": "MA-001",
                "trial_id": EYLEA_TRIAL,
                "method": MultiplicityMethod.ALPHA_SPENDING,
                "family_name": "Primary Efficacy Endpoints",
                "endpoints": ["BCVA change from baseline at W48", "BCVA change from baseline at W96"],
                "overall_alpha": 0.05,
                "allocated_alphas": {"BCVA W48": 0.025, "BCVA W96": 0.025},
                "adjusted_p_values": {"BCVA W48": 0.012, "BCVA W96": 0.031},
                "rejection_decisions": {"BCVA W48": True, "BCVA W96": True},
                "description": "Alpha-spending approach for co-primary endpoints using O'Brien-Fleming spending function.",
                "statistician": "Dr. Karen Mitchell",
                "created_at": now - timedelta(days=250),
            },
            {
                "id": "MA-002",
                "trial_id": EYLEA_TRIAL,
                "method": MultiplicityMethod.GATEKEEPING,
                "family_name": "Secondary Endpoint Testing",
                "endpoints": ["CRT change at W48", "Proportion gaining 15+ letters", "Proportion with fluid-free retina"],
                "overall_alpha": 0.05,
                "allocated_alphas": {"CRT": 0.025, "15+ letters": 0.0125, "Fluid-free": 0.0125},
                "adjusted_p_values": {"CRT": 0.008, "15+ letters": 0.015, "Fluid-free": 0.028},
                "rejection_decisions": {"CRT": True, "15+ letters": False, "Fluid-free": False},
                "description": "Gatekeeping procedure for hierarchically ordered secondary endpoints.",
                "statistician": "Dr. Karen Mitchell",
                "created_at": now - timedelta(days=248),
            },
            {
                "id": "MA-003",
                "trial_id": EYLEA_TRIAL,
                "method": MultiplicityMethod.GROUP_SEQUENTIAL,
                "family_name": "Interim Analysis Boundaries",
                "endpoints": ["BCVA primary endpoint"],
                "overall_alpha": 0.05,
                "allocated_alphas": {"IA1": 0.003, "IA2": 0.014, "IA3": 0.022, "Final": 0.011},
                "description": "O'Brien-Fleming group sequential boundaries for 3 interim + final analysis.",
                "statistician": "Dr. Karen Mitchell",
                "created_at": now - timedelta(days=260),
            },
            {
                "id": "MA-004",
                "trial_id": DUPIXENT_TRIAL,
                "method": MultiplicityMethod.GRAPHICAL,
                "family_name": "Hierarchical Endpoint Testing",
                "endpoints": ["EASI-75 at W16", "IGA 0/1 at W16", "EASI-90 at W16", "NRS itch at W16"],
                "overall_alpha": 0.05,
                "allocated_alphas": {"EASI-75": 0.025, "IGA 0/1": 0.025, "EASI-90": 0.0, "NRS itch": 0.0},
                "adjusted_p_values": {"EASI-75": 0.003, "IGA 0/1": 0.008, "EASI-90": 0.015, "NRS itch": 0.022},
                "rejection_decisions": {"EASI-75": True, "IGA 0/1": True, "EASI-90": True, "NRS itch": True},
                "description": "Graphical approach for testing multiple endpoints with alpha propagation.",
                "statistician": "Dr. Robert Zhang",
                "created_at": now - timedelta(days=220),
            },
            {
                "id": "MA-005",
                "trial_id": DUPIXENT_TRIAL,
                "method": MultiplicityMethod.HOLM,
                "family_name": "Dose Comparison Family",
                "endpoints": ["High dose vs placebo", "Medium dose vs placebo", "Low dose vs placebo"],
                "overall_alpha": 0.05,
                "allocated_alphas": {"High": 0.0167, "Medium": 0.0167, "Low": 0.0167},
                "adjusted_p_values": {"High": 0.002, "Medium": 0.015, "Low": 0.08},
                "rejection_decisions": {"High": True, "Medium": True, "Low": False},
                "description": "Holm step-down procedure for pairwise dose-placebo comparisons.",
                "statistician": "Dr. Robert Zhang",
                "created_at": now - timedelta(days=218),
            },
            {
                "id": "MA-006",
                "trial_id": DUPIXENT_TRIAL,
                "method": MultiplicityMethod.BONFERRONI,
                "family_name": "Subgroup Analysis Adjustment",
                "endpoints": ["Adult subgroup", "Adolescent subgroup", "Pediatric subgroup"],
                "overall_alpha": 0.05,
                "allocated_alphas": {"Adult": 0.0167, "Adolescent": 0.0167, "Pediatric": 0.0167},
                "description": "Bonferroni correction for pre-specified subgroup analyses.",
                "statistician": "Dr. Robert Zhang",
                "created_at": now - timedelta(days=215),
            },
            {
                "id": "MA-007",
                "trial_id": LIBTAYO_TRIAL,
                "method": MultiplicityMethod.HOCHBERG,
                "family_name": "Co-Primary Endpoints",
                "endpoints": ["ORR per IRC", "ORR per investigator"],
                "overall_alpha": 0.05,
                "allocated_alphas": {"ORR IRC": 0.025, "ORR Inv": 0.025},
                "adjusted_p_values": {"ORR IRC": 0.008, "ORR Inv": 0.012},
                "rejection_decisions": {"ORR IRC": True, "ORR Inv": True},
                "description": "Hochberg step-up procedure for co-primary ORR endpoints.",
                "statistician": "Dr. Amanda Torres",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "MA-008",
                "trial_id": LIBTAYO_TRIAL,
                "method": MultiplicityMethod.ALPHA_SPENDING,
                "family_name": "PFS Sequential Testing",
                "endpoints": ["PFS per IRC"],
                "overall_alpha": 0.05,
                "allocated_alphas": {"IA1": 0.008, "IA2": 0.020, "Final": 0.022},
                "description": "Pocock-type alpha-spending for PFS sequential interim analyses.",
                "statistician": "Dr. Amanda Torres",
                "created_at": now - timedelta(days=195),
            },
            {
                "id": "MA-009",
                "trial_id": LIBTAYO_TRIAL,
                "method": MultiplicityMethod.GRAPHICAL,
                "family_name": "OS and PFS Testing Strategy",
                "endpoints": ["OS", "PFS", "ORR"],
                "overall_alpha": 0.05,
                "allocated_alphas": {"OS": 0.02, "PFS": 0.02, "ORR": 0.01},
                "description": "Graphical testing strategy with alpha reallocation between OS, PFS, and ORR.",
                "statistician": "Dr. Amanda Torres",
                "created_at": now - timedelta(days=198),
            },
            {
                "id": "MA-010",
                "trial_id": EYLEA_TRIAL,
                "method": MultiplicityMethod.BONFERRONI,
                "family_name": "Safety Endpoint Multiplicity",
                "endpoints": ["Endophthalmitis rate", "Retinal detachment rate", "IOP elevation rate"],
                "overall_alpha": 0.05,
                "allocated_alphas": {"Endophthalmitis": 0.0167, "Retinal detachment": 0.0167, "IOP elevation": 0.0167},
                "description": "Bonferroni correction for key safety endpoint comparisons.",
                "statistician": "Dr. Karen Mitchell",
                "created_at": now - timedelta(days=245),
            },
        ]

        for adj in adjustments_data:
            self._adjustments[adj["id"]] = MultiplicityAdjustment(**adj)

        # --- Statistical Reports (12 records) ---
        reports_data = [
            {
                "id": "SR-001",
                "trial_id": EYLEA_TRIAL,
                "analysis_id": "IA-001",
                "report_type": ReportType.DSMB_REPORT,
                "title": "EYLEA HD Phase 3 - DSMB Report #1 (First Interim)",
                "version": "1.0",
                "blinding_level": BlindingLevel.UNBLINDED,
                "status": "approved",
                "author": "Dr. Karen Mitchell",
                "reviewer": "Dr. James Wilson",
                "approval_date": now - timedelta(days=170),
                "distribution_list": ["DSMB Chair", "DSMB Members", "Sponsor Medical Monitor"],
                "key_findings": ["No safety concerns identified", "Efficacy trend positive but boundary not crossed", "Recommend continuation"],
                "created_at": now - timedelta(days=175),
            },
            {
                "id": "SR-002",
                "trial_id": EYLEA_TRIAL,
                "analysis_id": "IA-002",
                "report_type": ReportType.INTERIM_REPORT,
                "title": "EYLEA HD Phase 3 - Second Interim Analysis Report",
                "version": "2.0",
                "blinding_level": BlindingLevel.UNBLINDED,
                "status": "approved",
                "author": "Dr. Karen Mitchell",
                "reviewer": "Dr. James Wilson",
                "approval_date": now - timedelta(days=80),
                "distribution_list": ["DSMB Chair", "DSMB Members", "Sponsor Biostatistics Head"],
                "key_findings": ["O'Brien-Fleming efficacy boundary crossed", "Conditional power >90%", "Strong evidence of superiority"],
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "SR-003",
                "trial_id": EYLEA_TRIAL,
                "analysis_id": "IA-001",
                "report_type": ReportType.SAFETY_REPORT,
                "title": "EYLEA HD Phase 3 - Safety Analysis at IA1",
                "version": "1.0",
                "blinding_level": BlindingLevel.BLINDED_AGGREGATE,
                "status": "approved",
                "author": "Dr. Sarah Hoffman",
                "reviewer": "Dr. Karen Mitchell",
                "approval_date": now - timedelta(days=172),
                "distribution_list": ["Safety Committee", "Medical Monitor"],
                "key_findings": ["AE rates comparable between arms", "No dose-limiting toxicity signals"],
                "created_at": now - timedelta(days=176),
            },
            {
                "id": "SR-004",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_id": "IA-005",
                "report_type": ReportType.DSMB_REPORT,
                "title": "Dupixent AD Phase 3 - DSMB Report #1",
                "version": "1.0",
                "blinding_level": BlindingLevel.UNBLINDED,
                "status": "approved",
                "author": "Dr. Robert Zhang",
                "reviewer": "Dr. Patricia Chen",
                "approval_date": now - timedelta(days=140),
                "distribution_list": ["DSMB Chair", "DSMB Members"],
                "key_findings": ["EASI-75 response rates encouraging", "Safety profile consistent with known label"],
                "created_at": now - timedelta(days=148),
            },
            {
                "id": "SR-005",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_id": "IA-006",
                "report_type": ReportType.INTERIM_REPORT,
                "title": "Dupixent AD Phase 3 - Second Interim Analysis Report",
                "version": "1.0",
                "blinding_level": BlindingLevel.UNBLINDED,
                "status": "draft",
                "author": "Dr. Robert Zhang",
                "distribution_list": ["DSMB Chair", "DSMB Members", "Sponsor Biostatistics"],
                "key_findings": [],
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "SR-006",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_id": "IA-007",
                "report_type": ReportType.SAFETY_REPORT,
                "title": "Dupixent AD Phase 3 - Safety Report at 50% Information",
                "version": "1.0",
                "blinding_level": BlindingLevel.UNBLINDED,
                "status": "approved",
                "author": "Dr. Lisa Park",
                "reviewer": "Dr. Robert Zhang",
                "approval_date": now - timedelta(days=92),
                "distribution_list": ["Safety Committee", "DSMB Chair"],
                "key_findings": ["No unexpected AEs", "Injection site reactions within expected range"],
                "created_at": now - timedelta(days=98),
            },
            {
                "id": "SR-007",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_id": "IA-008",
                "report_type": ReportType.DSMB_REPORT,
                "title": "Libtayo CSCC Phase 3 - DSMB Report #1 (IA1)",
                "version": "1.0",
                "blinding_level": BlindingLevel.UNBLINDED,
                "status": "approved",
                "author": "Dr. Amanda Torres",
                "reviewer": "Dr. Michael Ng",
                "approval_date": now - timedelta(days=110),
                "distribution_list": ["DSMB Chair", "DSMB Members", "Medical Monitor"],
                "key_findings": ["ORR encouraging", "PFS trend positive", "Immune-related AEs manageable"],
                "created_at": now - timedelta(days=118),
            },
            {
                "id": "SR-008",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_id": "IA-009",
                "report_type": ReportType.INTERIM_REPORT,
                "title": "Libtayo CSCC Phase 3 - Adaptive Interim Analysis Report",
                "version": "1.0",
                "blinding_level": BlindingLevel.PARTIALLY_UNBLINDED,
                "status": "in_review",
                "author": "Dr. Amanda Torres",
                "reviewer": "Dr. Michael Ng",
                "distribution_list": ["DSMB Chair", "Adaptive Design Committee"],
                "key_findings": ["Dose-response relationship confirmed", "High dose arm superior"],
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "SR-009",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_id": "IA-010",
                "report_type": ReportType.FUTILITY_REPORT,
                "title": "Libtayo CSCC Phase 3 - Futility Assessment Report",
                "version": "1.0",
                "blinding_level": BlindingLevel.BLINDED_AGGREGATE,
                "status": "approved",
                "author": "Dr. Amanda Torres",
                "reviewer": "Dr. Michael Ng",
                "approval_date": now - timedelta(days=108),
                "distribution_list": ["DSMB Chair", "Sponsor Biostatistics Head"],
                "key_findings": ["Futility boundary not crossed", "Conditional power adequate to continue"],
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "SR-010",
                "trial_id": EYLEA_TRIAL,
                "report_type": ReportType.AD_HOC_REPORT,
                "title": "EYLEA HD - Ad Hoc Analysis: Subgroup by Baseline BCVA",
                "version": "1.0",
                "blinding_level": BlindingLevel.UNBLINDED,
                "status": "approved",
                "author": "Dr. Karen Mitchell",
                "reviewer": "Dr. James Wilson",
                "approval_date": now - timedelta(days=75),
                "distribution_list": ["Sponsor Medical Team", "Regulatory Affairs"],
                "key_findings": ["Consistent treatment effect across BCVA subgroups", "No heterogeneity of treatment effect"],
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "SR-011",
                "trial_id": DUPIXENT_TRIAL,
                "report_type": ReportType.AD_HOC_REPORT,
                "title": "Dupixent AD - Ad Hoc Dose-Response Analysis",
                "version": "1.0",
                "blinding_level": BlindingLevel.UNBLINDED,
                "status": "draft",
                "author": "Dr. Robert Zhang",
                "distribution_list": ["Sponsor Biostatistics"],
                "key_findings": [],
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "SR-012",
                "trial_id": LIBTAYO_TRIAL,
                "report_type": ReportType.FINAL_REPORT,
                "title": "Libtayo CSCC Phase 3 - Final Statistical Analysis Report",
                "version": "0.1",
                "blinding_level": BlindingLevel.OPEN,
                "status": "draft",
                "author": "Dr. Amanda Torres",
                "distribution_list": ["Regulatory Affairs", "Medical Writing", "Sponsor Biostatistics"],
                "key_findings": [],
                "created_at": now - timedelta(days=10),
            },
        ]

        for r in reports_data:
            self._reports[r["id"]] = StatisticalReport(**r)

        # --- Futility Assessments (10 records) ---
        futility_data = [
            {
                "id": "FA-001",
                "analysis_id": "IA-001",
                "conditional_power": 0.82,
                "predictive_power": 0.78,
                "futility_boundary": 0.20,
                "observed_statistic": 1.75,
                "futility_met": False,
                "stochastic_curtailment_pct": 82.0,
                "recommendation": "Continue enrollment. Conditional power well above futility threshold.",
                "assessed_by": "Dr. Karen Mitchell",
                "assessment_date": now - timedelta(days=177),
            },
            {
                "id": "FA-002",
                "analysis_id": "IA-002",
                "conditional_power": 0.94,
                "predictive_power": 0.91,
                "futility_boundary": 0.20,
                "observed_statistic": 2.51,
                "futility_met": False,
                "stochastic_curtailment_pct": 94.0,
                "recommendation": "Continue. Overwhelming evidence against futility. Efficacy boundary crossed.",
                "assessed_by": "Dr. Karen Mitchell",
                "assessment_date": now - timedelta(days=87),
            },
            {
                "id": "FA-003",
                "analysis_id": "IA-005",
                "conditional_power": 0.76,
                "predictive_power": 0.72,
                "futility_boundary": 0.20,
                "observed_statistic": 2.01,
                "futility_met": False,
                "stochastic_curtailment_pct": 76.0,
                "recommendation": "Continue enrollment. Conditional power adequate.",
                "assessed_by": "Dr. Robert Zhang",
                "assessment_date": now - timedelta(days=147),
            },
            {
                "id": "FA-004",
                "analysis_id": "IA-006",
                "conditional_power": 0.85,
                "predictive_power": 0.80,
                "futility_boundary": 0.20,
                "observed_statistic": 2.29,
                "futility_met": False,
                "stochastic_curtailment_pct": 85.0,
                "recommendation": "Continue. Strong evidence of efficacy in primary endpoint.",
                "assessed_by": "Dr. Robert Zhang",
                "assessment_date": now - timedelta(days=42),
            },
            {
                "id": "FA-005",
                "analysis_id": "IA-008",
                "conditional_power": 0.70,
                "predictive_power": 0.65,
                "futility_boundary": 0.30,
                "observed_statistic": 1.83,
                "futility_met": False,
                "stochastic_curtailment_pct": 70.0,
                "recommendation": "Continue with close monitoring. Conditional power above threshold but not robust.",
                "assessed_by": "Dr. Amanda Torres",
                "assessment_date": now - timedelta(days=117),
            },
            {
                "id": "FA-006",
                "analysis_id": "IA-009",
                "conditional_power": 0.88,
                "predictive_power": 0.84,
                "futility_boundary": 0.30,
                "observed_statistic": 2.37,
                "futility_met": False,
                "stochastic_curtailment_pct": 88.0,
                "recommendation": "Continue. Adaptive design modifications supported by strong conditional power.",
                "assessed_by": "Dr. Amanda Torres",
                "assessment_date": now - timedelta(days=27),
            },
            {
                "id": "FA-007",
                "analysis_id": "IA-010",
                "conditional_power": 0.65,
                "predictive_power": 0.60,
                "futility_boundary": 0.20,
                "observed_statistic": 1.50,
                "futility_met": False,
                "stochastic_curtailment_pct": 65.0,
                "recommendation": "Continue. Futility boundary not met. Monitor closely at next interim.",
                "assessed_by": "Dr. Amanda Torres",
                "assessment_date": now - timedelta(days=117),
            },
            {
                "id": "FA-008",
                "analysis_id": "IA-001",
                "conditional_power": 0.15,
                "predictive_power": 0.12,
                "futility_boundary": 0.20,
                "observed_statistic": 0.45,
                "futility_met": True,
                "stochastic_curtailment_pct": 15.0,
                "recommendation": "Futility threshold met for secondary endpoint CRT. Consider dropping from confirmatory testing.",
                "assessed_by": "Dr. Karen Mitchell",
                "assessment_date": now - timedelta(days=176),
            },
            {
                "id": "FA-009",
                "analysis_id": "IA-005",
                "conditional_power": 0.18,
                "predictive_power": 0.14,
                "futility_boundary": 0.20,
                "observed_statistic": 0.52,
                "futility_met": True,
                "stochastic_curtailment_pct": 18.0,
                "recommendation": "Low-dose arm meets futility criteria for EASI-90. Recommend discontinuing low-dose arm.",
                "assessed_by": "Dr. Robert Zhang",
                "assessment_date": now - timedelta(days=146),
            },
            {
                "id": "FA-010",
                "analysis_id": "IA-008",
                "conditional_power": 0.10,
                "predictive_power": 0.08,
                "futility_boundary": 0.30,
                "observed_statistic": 0.30,
                "futility_met": True,
                "stochastic_curtailment_pct": 10.0,
                "recommendation": "OS endpoint meets futility criteria. PFS remains viable. Focus reporting on PFS/ORR.",
                "assessed_by": "Dr. Amanda Torres",
                "assessment_date": now - timedelta(days=116),
            },
        ]

        for f in futility_data:
            self._futility_assessments[f["id"]] = FutilityAssessment(**f)

    # ------------------------------------------------------------------
    # Interim Analysis CRUD
    # ------------------------------------------------------------------

    def list_analyses(
        self,
        *,
        trial_id: str | None = None,
        analysis_type: AnalysisType | None = None,
        status: AnalysisStatus | None = None,
    ) -> list[InterimAnalysis]:
        """List interim analyses with optional filters."""
        with self._lock:
            result = list(self._analyses.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if analysis_type is not None:
            result = [a for a in result if a.analysis_type == analysis_type]
        if status is not None:
            result = [a for a in result if a.status == status]

        return sorted(result, key=lambda a: a.id)

    def get_analysis(self, analysis_id: str) -> InterimAnalysis | None:
        """Get a single interim analysis by ID."""
        with self._lock:
            return self._analyses.get(analysis_id)

    def create_analysis(self, payload: InterimAnalysisCreate) -> InterimAnalysis:
        """Create a new interim analysis."""
        now = datetime.now(timezone.utc)
        analysis_id = f"IA-{uuid4().hex[:8].upper()}"
        analysis = InterimAnalysis(
            id=analysis_id,
            trial_id=payload.trial_id,
            analysis_number=payload.analysis_number,
            analysis_type=payload.analysis_type,
            information_fraction=payload.information_fraction,
            planned_date=payload.planned_date,
            events_required=payload.events_required,
            spending_function=payload.spending_function,
            lead_statistician=payload.lead_statistician,
            status=AnalysisStatus.PLANNED,
            subjects_enrolled=0,
            subjects_analyzed=0,
            events_observed=0,
            created_at=now,
        )
        with self._lock:
            self._analyses[analysis_id] = analysis
        logger.info("Created interim analysis %s for trial %s", analysis_id, payload.trial_id)
        return analysis

    def update_analysis(
        self, analysis_id: str, payload: InterimAnalysisUpdate
    ) -> InterimAnalysis | None:
        """Update an existing interim analysis."""
        with self._lock:
            existing = self._analyses.get(analysis_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = InterimAnalysis(**data)
            self._analyses[analysis_id] = updated
        return updated

    def delete_analysis(self, analysis_id: str) -> bool:
        """Delete an interim analysis. Returns True if deleted."""
        with self._lock:
            if analysis_id in self._analyses:
                del self._analyses[analysis_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Adaptive Decision CRUD
    # ------------------------------------------------------------------

    def list_decisions(
        self,
        *,
        analysis_id: str | None = None,
        outcome: DecisionOutcome | None = None,
    ) -> list[AdaptiveDecision]:
        """List adaptive decisions with optional filters."""
        with self._lock:
            result = list(self._decisions.values())

        if analysis_id is not None:
            result = [d for d in result if d.analysis_id == analysis_id]
        if outcome is not None:
            result = [d for d in result if d.outcome == outcome]

        return sorted(result, key=lambda d: d.id)

    def get_decision(self, decision_id: str) -> AdaptiveDecision | None:
        """Get a single adaptive decision by ID."""
        with self._lock:
            return self._decisions.get(decision_id)

    def create_decision(self, payload: AdaptiveDecisionCreate) -> AdaptiveDecision:
        """Create a new adaptive decision."""
        now = datetime.now(timezone.utc)
        decision_id = f"AD-{uuid4().hex[:8].upper()}"
        decision = AdaptiveDecision(
            id=decision_id,
            analysis_id=payload.analysis_id,
            decision_date=now,
            outcome=payload.outcome,
            rationale=payload.rationale,
            blinding_level=payload.blinding_level,
            decided_by=payload.decided_by,
            conditional_power=payload.conditional_power,
            predictive_probability=payload.predictive_probability,
            p_value=payload.p_value,
            dsmb_recommendation=payload.dsmb_recommendation,
        )
        with self._lock:
            self._decisions[decision_id] = decision
        logger.info("Created adaptive decision %s for analysis %s", decision_id, payload.analysis_id)
        return decision

    def delete_decision(self, decision_id: str) -> bool:
        """Delete an adaptive decision. Returns True if deleted."""
        with self._lock:
            if decision_id in self._decisions:
                del self._decisions[decision_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Multiplicity Adjustment CRUD
    # ------------------------------------------------------------------

    def list_adjustments(
        self,
        *,
        trial_id: str | None = None,
        method: MultiplicityMethod | None = None,
    ) -> list[MultiplicityAdjustment]:
        """List multiplicity adjustments with optional filters."""
        with self._lock:
            result = list(self._adjustments.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if method is not None:
            result = [a for a in result if a.method == method]

        return sorted(result, key=lambda a: a.id)

    def get_adjustment(self, adjustment_id: str) -> MultiplicityAdjustment | None:
        """Get a single multiplicity adjustment by ID."""
        with self._lock:
            return self._adjustments.get(adjustment_id)

    def create_adjustment(self, payload: MultiplicityAdjustmentCreate) -> MultiplicityAdjustment:
        """Create a new multiplicity adjustment."""
        now = datetime.now(timezone.utc)
        adjustment_id = f"MA-{uuid4().hex[:8].upper()}"
        adjustment = MultiplicityAdjustment(
            id=adjustment_id,
            trial_id=payload.trial_id,
            method=payload.method,
            family_name=payload.family_name,
            endpoints=payload.endpoints,
            overall_alpha=payload.overall_alpha,
            allocated_alphas={},
            adjusted_p_values={},
            rejection_decisions={},
            description=payload.description,
            statistician=payload.statistician,
            created_at=now,
        )
        with self._lock:
            self._adjustments[adjustment_id] = adjustment
        logger.info("Created multiplicity adjustment %s for trial %s", adjustment_id, payload.trial_id)
        return adjustment

    def update_adjustment(
        self, adjustment_id: str, payload: MultiplicityAdjustmentUpdate
    ) -> MultiplicityAdjustment | None:
        """Update an existing multiplicity adjustment."""
        with self._lock:
            existing = self._adjustments.get(adjustment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = MultiplicityAdjustment(**data)
            self._adjustments[adjustment_id] = updated
        return updated

    def delete_adjustment(self, adjustment_id: str) -> bool:
        """Delete a multiplicity adjustment. Returns True if deleted."""
        with self._lock:
            if adjustment_id in self._adjustments:
                del self._adjustments[adjustment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Statistical Report CRUD
    # ------------------------------------------------------------------

    def list_reports(
        self,
        *,
        trial_id: str | None = None,
        analysis_id: str | None = None,
        report_type: ReportType | None = None,
    ) -> list[StatisticalReport]:
        """List statistical reports with optional filters."""
        with self._lock:
            result = list(self._reports.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if analysis_id is not None:
            result = [r for r in result if r.analysis_id == analysis_id]
        if report_type is not None:
            result = [r for r in result if r.report_type == report_type]

        return sorted(result, key=lambda r: r.id)

    def get_report(self, report_id: str) -> StatisticalReport | None:
        """Get a single statistical report by ID."""
        with self._lock:
            return self._reports.get(report_id)

    def create_report(self, payload: StatisticalReportCreate) -> StatisticalReport:
        """Create a new statistical report."""
        now = datetime.now(timezone.utc)
        report_id = f"SR-{uuid4().hex[:8].upper()}"
        report = StatisticalReport(
            id=report_id,
            trial_id=payload.trial_id,
            analysis_id=payload.analysis_id,
            report_type=payload.report_type,
            title=payload.title,
            version=payload.version,
            blinding_level=payload.blinding_level,
            status="draft",
            author=payload.author,
            distribution_list=payload.distribution_list,
            key_findings=[],
            created_at=now,
        )
        with self._lock:
            self._reports[report_id] = report
        logger.info("Created statistical report %s for trial %s", report_id, payload.trial_id)
        return report

    def update_report(
        self, report_id: str, payload: StatisticalReportUpdate
    ) -> StatisticalReport | None:
        """Update an existing statistical report."""
        with self._lock:
            existing = self._reports.get(report_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = StatisticalReport(**data)
            self._reports[report_id] = updated
        return updated

    def delete_report(self, report_id: str) -> bool:
        """Delete a statistical report. Returns True if deleted."""
        with self._lock:
            if report_id in self._reports:
                del self._reports[report_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Futility Assessment CRUD
    # ------------------------------------------------------------------

    def list_futility_assessments(
        self,
        *,
        analysis_id: str | None = None,
        futility_met: bool | None = None,
    ) -> list[FutilityAssessment]:
        """List futility assessments with optional filters."""
        with self._lock:
            result = list(self._futility_assessments.values())

        if analysis_id is not None:
            result = [f for f in result if f.analysis_id == analysis_id]
        if futility_met is not None:
            result = [f for f in result if f.futility_met == futility_met]

        return sorted(result, key=lambda f: f.id)

    def get_futility_assessment(self, assessment_id: str) -> FutilityAssessment | None:
        """Get a single futility assessment by ID."""
        with self._lock:
            return self._futility_assessments.get(assessment_id)

    def create_futility_assessment(self, payload: FutilityAssessmentCreate) -> FutilityAssessment:
        """Create a new futility assessment."""
        now = datetime.now(timezone.utc)
        assessment_id = f"FA-{uuid4().hex[:8].upper()}"
        assessment = FutilityAssessment(
            id=assessment_id,
            analysis_id=payload.analysis_id,
            conditional_power=payload.conditional_power,
            predictive_power=payload.predictive_power,
            futility_boundary=payload.futility_boundary,
            observed_statistic=payload.observed_statistic,
            futility_met=False,
            stochastic_curtailment_pct=payload.stochastic_curtailment_pct,
            recommendation=payload.recommendation,
            assessed_by=payload.assessed_by,
            assessment_date=now,
        )
        with self._lock:
            self._futility_assessments[assessment_id] = assessment
        logger.info("Created futility assessment %s for analysis %s", assessment_id, payload.analysis_id)
        return assessment

    def delete_futility_assessment(self, assessment_id: str) -> bool:
        """Delete a futility assessment. Returns True if deleted."""
        with self._lock:
            if assessment_id in self._futility_assessments:
                del self._futility_assessments[assessment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> BiostatisticsMetrics:
        """Compute aggregated biostatistics metrics."""
        with self._lock:
            analyses = list(self._analyses.values())
            decisions = list(self._decisions.values())
            adjustments = list(self._adjustments.values())
            reports = list(self._reports.values())
            futility = list(self._futility_assessments.values())

        # Analyses by type
        analyses_by_type: dict[str, int] = {}
        for a in analyses:
            key = a.analysis_type.value
            analyses_by_type[key] = analyses_by_type.get(key, 0) + 1

        # Analyses by status
        analyses_by_status: dict[str, int] = {}
        for a in analyses:
            key = a.status.value
            analyses_by_status[key] = analyses_by_status.get(key, 0) + 1

        # Decisions by outcome
        decisions_by_outcome: dict[str, int] = {}
        for d in decisions:
            key = d.outcome.value
            decisions_by_outcome[key] = decisions_by_outcome.get(key, 0) + 1

        # Adjustments by method
        adjustments_by_method: dict[str, int] = {}
        for adj in adjustments:
            key = adj.method.value
            adjustments_by_method[key] = adjustments_by_method.get(key, 0) + 1

        # Reports by type
        reports_by_type: dict[str, int] = {}
        for r in reports:
            key = r.report_type.value
            reports_by_type[key] = reports_by_type.get(key, 0) + 1

        # Futility met count
        futility_met_count = sum(1 for f in futility if f.futility_met)

        # Average information fraction
        fractions = [a.information_fraction for a in analyses if a.information_fraction is not None]
        avg_info_fraction = sum(fractions) / len(fractions) if fractions else 0.0

        return BiostatisticsMetrics(
            total_analyses=len(analyses),
            analyses_by_type=analyses_by_type,
            analyses_by_status=analyses_by_status,
            total_decisions=len(decisions),
            decisions_by_outcome=decisions_by_outcome,
            total_multiplicity_adjustments=len(adjustments),
            adjustments_by_method=adjustments_by_method,
            total_reports=len(reports),
            reports_by_type=reports_by_type,
            total_futility_assessments=len(futility),
            futility_met_count=futility_met_count,
            avg_information_fraction=round(avg_info_fraction, 4),
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: BiostatisticsOpsService | None = None
_instance_lock = threading.Lock()


def get_biostatistics_ops_service() -> BiostatisticsOpsService:
    """Return the singleton BiostatisticsOpsService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = BiostatisticsOpsService()
    return _instance


def reset_biostatistics_ops_service() -> BiostatisticsOpsService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = BiostatisticsOpsService()
    return _instance
