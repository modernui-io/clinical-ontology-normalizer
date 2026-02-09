"""Statistical Analysis & Interim Analysis Management Service (CLINICAL-25).

Manages statistical analysis operations including SAP definitions, analysis results
with multiplicity adjustments, interim analysis with O'Brien-Fleming alpha spending,
sample size calculations, subgroup analyses with interaction testing, and statistical
metrics dashboards.

Usage:
    from app.services.statistical_analysis_service import (
        get_stats_service,
    )

    svc = get_stats_service()
    results = svc.list_analysis_results()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.statistical_analysis import (
    AnalysisResult,
    AnalysisResultCreate,
    AnalysisType,
    InterimAnalysis,
    InterimAnalysisCreate,
    InterimRecommendation,
    MultiplicityCorrectionMethod,
    PopulationType,
    SAPCreate,
    SAPUpdate,
    SampleSizeCalc,
    StatisticalAnalysisPlan,
    StatisticalMethod,
    StatisticalMetrics,
    SubgroupAnalysis,
    SubgroupAnalysisCreate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class StatisticalAnalysisService:
    """In-memory Statistical Analysis engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._saps: dict[str, StatisticalAnalysisPlan] = {}
        self._results: dict[str, AnalysisResult] = {}
        self._interim_analyses: dict[str, InterimAnalysis] = {}
        self._sample_size_calcs: dict[str, SampleSizeCalc] = {}
        self._subgroup_analyses: dict[str, SubgroupAnalysis] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic statistical analysis data for Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 3 Statistical Analysis Plans ---
        saps_data = [
            {
                "id": "SAP-001",
                "trial_id": EYLEA_TRIAL,
                "version": "2.0",
                "title": "EYLEA HD Phase 3 - BCVA Change from Baseline at Week 48",
                "primary_endpoint": "Change from baseline in BCVA (ETDRS letters) at Week 48",
                "secondary_endpoints": [
                    "Proportion of patients gaining >= 15 ETDRS letters at Week 48",
                    "Change from baseline in central subfield thickness (CST) at Week 48",
                    "Proportion of patients with BCVA >= 20/40 at Week 48",
                    "Time to first BCVA improvement of >= 10 ETDRS letters",
                ],
                "sample_size_calculation": "Non-inferiority design: 330 per arm, NI margin of -4 letters, "
                    "90% power, one-sided alpha=0.025, assumed SD=12.5 letters",
                "randomization_ratio": "1:1",
                "alpha_level": 0.025,
                "power": 0.90,
                "populations": [
                    PopulationType.ITT,
                    PopulationType.PER_PROTOCOL,
                    PopulationType.SAFETY,
                ],
                "analysis_methods": [
                    StatisticalMethod.MMRM,
                    StatisticalMethod.ANCOVA,
                    StatisticalMethod.KAPLAN_MEIER,
                    StatisticalMethod.LOG_RANK,
                ],
                "multiplicity_strategy": MultiplicityCorrectionMethod.GRAPHICAL,
                "status": "final",
                "created_at": now - timedelta(days=365),
                "updated_at": now - timedelta(days=90),
            },
            {
                "id": "SAP-002",
                "trial_id": DUPIXENT_TRIAL,
                "version": "1.0",
                "title": "DUPIXENT Phase 3 Atopic Dermatitis - EASI-75 Response Rate at Week 16",
                "primary_endpoint": "Proportion of patients achieving EASI-75 response at Week 16",
                "secondary_endpoints": [
                    "IGA 0/1 response at Week 16",
                    "Change from baseline in pruritus NRS at Week 4",
                    "Proportion achieving EASI-90 at Week 16",
                    "Change from baseline in DLQI at Week 16",
                    "Proportion with >= 4 point improvement in pruritus NRS at Week 16",
                ],
                "sample_size_calculation": "Superiority design: 240 per arm, expected response rates "
                    "37% (treatment) vs 12% (placebo), 95% power, two-sided alpha=0.05",
                "randomization_ratio": "2:1",
                "alpha_level": 0.05,
                "power": 0.95,
                "populations": [
                    PopulationType.ITT,
                    PopulationType.MODIFIED_ITT,
                    PopulationType.SAFETY,
                    PopulationType.FULL_ANALYSIS_SET,
                ],
                "analysis_methods": [
                    StatisticalMethod.CHI_SQUARE,
                    StatisticalMethod.LOGISTIC_REGRESSION,
                    StatisticalMethod.FISHER_EXACT,
                    StatisticalMethod.WILCOXON,
                    StatisticalMethod.MMRM,
                ],
                "multiplicity_strategy": MultiplicityCorrectionMethod.HOCHBERG,
                "status": "final",
                "created_at": now - timedelta(days=300),
                "updated_at": now - timedelta(days=60),
            },
            {
                "id": "SAP-003",
                "trial_id": LIBTAYO_TRIAL,
                "version": "1.1",
                "title": "LIBTAYO Phase 3 NSCLC - Objective Response Rate by RECIST 1.1",
                "primary_endpoint": "Objective response rate (ORR) per RECIST 1.1 by blinded IRC",
                "secondary_endpoints": [
                    "Overall survival (OS)",
                    "Progression-free survival (PFS) per RECIST 1.1",
                    "Duration of response (DOR)",
                    "Disease control rate (DCR)",
                    "Time to response (TTR)",
                ],
                "sample_size_calculation": "Simon's two-stage design: null ORR=10%, alternative ORR=25%, "
                    "alpha=0.05, power=0.90, Stage 1: 19 patients, Stage 2: 54 total",
                "randomization_ratio": "1:1",
                "alpha_level": 0.05,
                "power": 0.90,
                "populations": [
                    PopulationType.ITT,
                    PopulationType.PER_PROTOCOL,
                    PopulationType.SAFETY,
                ],
                "analysis_methods": [
                    StatisticalMethod.KAPLAN_MEIER,
                    StatisticalMethod.COX_REGRESSION,
                    StatisticalMethod.LOG_RANK,
                    StatisticalMethod.FISHER_EXACT,
                ],
                "multiplicity_strategy": MultiplicityCorrectionMethod.GATEKEEPING,
                "status": "final",
                "created_at": now - timedelta(days=400),
                "updated_at": now - timedelta(days=45),
            },
        ]

        for s in saps_data:
            self._saps[s["id"]] = StatisticalAnalysisPlan(**s)

        # --- 20 Analysis Results ---
        results_data = [
            # EYLEA: BCVA primary analysis
            {
                "id": "AR-001",
                "plan_id": "SAP-001",
                "trial_id": EYLEA_TRIAL,
                "analysis_type": AnalysisType.PRIMARY,
                "endpoint": "Change from baseline in BCVA (ETDRS letters) at Week 48",
                "population": PopulationType.ITT,
                "method": StatisticalMethod.MMRM,
                "estimate": 8.7,
                "confidence_interval_lower": 7.1,
                "confidence_interval_upper": 10.3,
                "p_value": 0.0001,
                "adjusted_p_value": 0.0003,
                "clinically_significant": True,
                "n_treatment": 331,
                "n_control": 329,
                "effect_size": 0.72,
                "test_statistic": 10.84,
                "created_at": now - timedelta(days=30),
            },
            # EYLEA: BCVA per-protocol sensitivity
            {
                "id": "AR-002",
                "plan_id": "SAP-001",
                "trial_id": EYLEA_TRIAL,
                "analysis_type": AnalysisType.SENSITIVITY,
                "endpoint": "Change from baseline in BCVA (ETDRS letters) at Week 48",
                "population": PopulationType.PER_PROTOCOL,
                "method": StatisticalMethod.MMRM,
                "estimate": 9.1,
                "confidence_interval_lower": 7.4,
                "confidence_interval_upper": 10.8,
                "p_value": 0.00005,
                "adjusted_p_value": None,
                "clinically_significant": True,
                "n_treatment": 305,
                "n_control": 301,
                "effect_size": 0.76,
                "test_statistic": 11.22,
                "created_at": now - timedelta(days=30),
            },
            # EYLEA: secondary - 15 letter gain
            {
                "id": "AR-003",
                "plan_id": "SAP-001",
                "trial_id": EYLEA_TRIAL,
                "analysis_type": AnalysisType.SECONDARY,
                "endpoint": "Proportion gaining >= 15 ETDRS letters at Week 48",
                "population": PopulationType.ITT,
                "method": StatisticalMethod.CHI_SQUARE,
                "estimate": 0.247,
                "confidence_interval_lower": 0.198,
                "confidence_interval_upper": 0.296,
                "p_value": 0.003,
                "adjusted_p_value": 0.009,
                "clinically_significant": True,
                "n_treatment": 331,
                "n_control": 329,
                "effect_size": 0.35,
                "test_statistic": 8.91,
                "created_at": now - timedelta(days=28),
            },
            # EYLEA: secondary - CST change
            {
                "id": "AR-004",
                "plan_id": "SAP-001",
                "trial_id": EYLEA_TRIAL,
                "analysis_type": AnalysisType.SECONDARY,
                "endpoint": "Change from baseline in CST at Week 48",
                "population": PopulationType.ITT,
                "method": StatisticalMethod.ANCOVA,
                "estimate": -128.3,
                "confidence_interval_lower": -145.2,
                "confidence_interval_upper": -111.4,
                "p_value": 0.0001,
                "adjusted_p_value": 0.0003,
                "clinically_significant": True,
                "n_treatment": 331,
                "n_control": 329,
                "effect_size": 0.68,
                "test_statistic": -9.45,
                "created_at": now - timedelta(days=28),
            },
            # EYLEA: safety analysis
            {
                "id": "AR-005",
                "plan_id": "SAP-001",
                "trial_id": EYLEA_TRIAL,
                "analysis_type": AnalysisType.SAFETY,
                "endpoint": "Incidence of treatment-emergent adverse events",
                "population": PopulationType.SAFETY,
                "method": StatisticalMethod.FISHER_EXACT,
                "estimate": 0.62,
                "confidence_interval_lower": 0.56,
                "confidence_interval_upper": 0.68,
                "p_value": 0.42,
                "adjusted_p_value": None,
                "clinically_significant": False,
                "n_treatment": 335,
                "n_control": 332,
                "effect_size": 0.04,
                "test_statistic": 0.81,
                "created_at": now - timedelta(days=25),
            },
            # EYLEA: exploratory
            {
                "id": "AR-006",
                "plan_id": "SAP-001",
                "trial_id": EYLEA_TRIAL,
                "analysis_type": AnalysisType.EXPLORATORY,
                "endpoint": "Time to first BCVA improvement >= 10 ETDRS letters",
                "population": PopulationType.ITT,
                "method": StatisticalMethod.KAPLAN_MEIER,
                "estimate": 0.71,
                "confidence_interval_lower": 0.58,
                "confidence_interval_upper": 0.87,
                "p_value": 0.012,
                "adjusted_p_value": None,
                "clinically_significant": True,
                "n_treatment": 331,
                "n_control": 329,
                "effect_size": 0.42,
                "test_statistic": -2.52,
                "created_at": now - timedelta(days=25),
            },
            # DUPIXENT: primary - EASI-75
            {
                "id": "AR-007",
                "plan_id": "SAP-002",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_type": AnalysisType.PRIMARY,
                "endpoint": "EASI-75 response rate at Week 16",
                "population": PopulationType.ITT,
                "method": StatisticalMethod.CHI_SQUARE,
                "estimate": 0.387,
                "confidence_interval_lower": 0.325,
                "confidence_interval_upper": 0.449,
                "p_value": 0.00001,
                "adjusted_p_value": 0.00005,
                "clinically_significant": True,
                "n_treatment": 242,
                "n_control": 118,
                "effect_size": 0.58,
                "test_statistic": 24.31,
                "created_at": now - timedelta(days=45),
            },
            # DUPIXENT: secondary - IGA 0/1
            {
                "id": "AR-008",
                "plan_id": "SAP-002",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_type": AnalysisType.SECONDARY,
                "endpoint": "IGA 0/1 response at Week 16",
                "population": PopulationType.ITT,
                "method": StatisticalMethod.CHI_SQUARE,
                "estimate": 0.362,
                "confidence_interval_lower": 0.301,
                "confidence_interval_upper": 0.423,
                "p_value": 0.00008,
                "adjusted_p_value": 0.00024,
                "clinically_significant": True,
                "n_treatment": 242,
                "n_control": 118,
                "effect_size": 0.52,
                "test_statistic": 18.45,
                "created_at": now - timedelta(days=43),
            },
            # DUPIXENT: secondary - pruritus NRS
            {
                "id": "AR-009",
                "plan_id": "SAP-002",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_type": AnalysisType.SECONDARY,
                "endpoint": "Change from baseline in pruritus NRS at Week 4",
                "population": PopulationType.ITT,
                "method": StatisticalMethod.MMRM,
                "estimate": -3.2,
                "confidence_interval_lower": -3.8,
                "confidence_interval_upper": -2.6,
                "p_value": 0.0001,
                "adjusted_p_value": 0.0003,
                "clinically_significant": True,
                "n_treatment": 242,
                "n_control": 118,
                "effect_size": 0.85,
                "test_statistic": -8.92,
                "created_at": now - timedelta(days=43),
            },
            # DUPIXENT: secondary - EASI-90
            {
                "id": "AR-010",
                "plan_id": "SAP-002",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_type": AnalysisType.SECONDARY,
                "endpoint": "EASI-90 response rate at Week 16",
                "population": PopulationType.ITT,
                "method": StatisticalMethod.LOGISTIC_REGRESSION,
                "estimate": 0.212,
                "confidence_interval_lower": 0.158,
                "confidence_interval_upper": 0.266,
                "p_value": 0.001,
                "adjusted_p_value": 0.004,
                "clinically_significant": True,
                "n_treatment": 242,
                "n_control": 118,
                "effect_size": 0.45,
                "test_statistic": 12.65,
                "created_at": now - timedelta(days=40),
            },
            # DUPIXENT: safety
            {
                "id": "AR-011",
                "plan_id": "SAP-002",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_type": AnalysisType.SAFETY,
                "endpoint": "Incidence of injection site reactions",
                "population": PopulationType.SAFETY,
                "method": StatisticalMethod.FISHER_EXACT,
                "estimate": 0.152,
                "confidence_interval_lower": 0.108,
                "confidence_interval_upper": 0.196,
                "p_value": 0.08,
                "adjusted_p_value": None,
                "clinically_significant": False,
                "n_treatment": 245,
                "n_control": 120,
                "effect_size": 0.12,
                "test_statistic": 3.07,
                "created_at": now - timedelta(days=38),
            },
            # DUPIXENT: post-hoc
            {
                "id": "AR-012",
                "plan_id": "SAP-002",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_type": AnalysisType.POST_HOC,
                "endpoint": "EASI-75 response stratified by baseline severity",
                "population": PopulationType.FULL_ANALYSIS_SET,
                "method": StatisticalMethod.LOGISTIC_REGRESSION,
                "estimate": 0.41,
                "confidence_interval_lower": 0.33,
                "confidence_interval_upper": 0.49,
                "p_value": 0.0005,
                "adjusted_p_value": None,
                "clinically_significant": True,
                "n_treatment": 240,
                "n_control": 116,
                "effect_size": 0.55,
                "test_statistic": 15.2,
                "created_at": now - timedelta(days=20),
            },
            # LIBTAYO: primary - ORR
            {
                "id": "AR-013",
                "plan_id": "SAP-003",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_type": AnalysisType.PRIMARY,
                "endpoint": "Objective response rate (ORR) per RECIST 1.1 by IRC",
                "population": PopulationType.ITT,
                "method": StatisticalMethod.FISHER_EXACT,
                "estimate": 0.268,
                "confidence_interval_lower": 0.183,
                "confidence_interval_upper": 0.353,
                "p_value": 0.002,
                "adjusted_p_value": 0.006,
                "clinically_significant": True,
                "n_treatment": 108,
                "n_control": 109,
                "effect_size": 0.38,
                "test_statistic": 9.65,
                "created_at": now - timedelta(days=60),
            },
            # LIBTAYO: secondary - OS
            {
                "id": "AR-014",
                "plan_id": "SAP-003",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_type": AnalysisType.SECONDARY,
                "endpoint": "Overall survival (OS)",
                "population": PopulationType.ITT,
                "method": StatisticalMethod.COX_REGRESSION,
                "estimate": 0.68,
                "confidence_interval_lower": 0.49,
                "confidence_interval_upper": 0.93,
                "p_value": 0.018,
                "adjusted_p_value": 0.036,
                "clinically_significant": True,
                "n_treatment": 108,
                "n_control": 109,
                "effect_size": 0.39,
                "test_statistic": -2.37,
                "created_at": now - timedelta(days=55),
            },
            # LIBTAYO: secondary - PFS
            {
                "id": "AR-015",
                "plan_id": "SAP-003",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_type": AnalysisType.SECONDARY,
                "endpoint": "Progression-free survival (PFS) per RECIST 1.1",
                "population": PopulationType.ITT,
                "method": StatisticalMethod.KAPLAN_MEIER,
                "estimate": 0.55,
                "confidence_interval_lower": 0.40,
                "confidence_interval_upper": 0.76,
                "p_value": 0.0003,
                "adjusted_p_value": 0.0009,
                "clinically_significant": True,
                "n_treatment": 108,
                "n_control": 109,
                "effect_size": 0.60,
                "test_statistic": -3.61,
                "created_at": now - timedelta(days=55),
            },
            # LIBTAYO: secondary - DOR
            {
                "id": "AR-016",
                "plan_id": "SAP-003",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_type": AnalysisType.SECONDARY,
                "endpoint": "Duration of response (DOR)",
                "population": PopulationType.ITT,
                "method": StatisticalMethod.KAPLAN_MEIER,
                "estimate": 16.3,
                "confidence_interval_lower": 11.8,
                "confidence_interval_upper": 22.1,
                "p_value": 0.04,
                "adjusted_p_value": 0.08,
                "clinically_significant": True,
                "n_treatment": 29,
                "n_control": 12,
                "effect_size": 0.48,
                "test_statistic": -2.05,
                "created_at": now - timedelta(days=50),
            },
            # LIBTAYO: safety
            {
                "id": "AR-017",
                "plan_id": "SAP-003",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_type": AnalysisType.SAFETY,
                "endpoint": "Incidence of immune-related adverse events (irAEs)",
                "population": PopulationType.SAFETY,
                "method": StatisticalMethod.FISHER_EXACT,
                "estimate": 0.185,
                "confidence_interval_lower": 0.118,
                "confidence_interval_upper": 0.252,
                "p_value": 0.31,
                "adjusted_p_value": None,
                "clinically_significant": False,
                "n_treatment": 110,
                "n_control": 110,
                "effect_size": 0.09,
                "test_statistic": 1.02,
                "created_at": now - timedelta(days=48),
            },
            # LIBTAYO: exploratory - PD-L1 subgroup
            {
                "id": "AR-018",
                "plan_id": "SAP-003",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_type": AnalysisType.EXPLORATORY,
                "endpoint": "ORR in PD-L1 >= 50% subgroup",
                "population": PopulationType.ITT,
                "method": StatisticalMethod.FISHER_EXACT,
                "estimate": 0.392,
                "confidence_interval_lower": 0.268,
                "confidence_interval_upper": 0.516,
                "p_value": 0.0004,
                "adjusted_p_value": None,
                "clinically_significant": True,
                "n_treatment": 51,
                "n_control": 52,
                "effect_size": 0.56,
                "test_statistic": 12.42,
                "created_at": now - timedelta(days=45),
            },
            # EYLEA: subgroup analysis result
            {
                "id": "AR-019",
                "plan_id": "SAP-001",
                "trial_id": EYLEA_TRIAL,
                "analysis_type": AnalysisType.SUBGROUP,
                "endpoint": "BCVA change by baseline vision category",
                "population": PopulationType.ITT,
                "method": StatisticalMethod.ANCOVA,
                "estimate": 9.5,
                "confidence_interval_lower": 7.2,
                "confidence_interval_upper": 11.8,
                "p_value": 0.0001,
                "adjusted_p_value": None,
                "clinically_significant": True,
                "n_treatment": 165,
                "n_control": 168,
                "effect_size": 0.78,
                "test_statistic": 8.23,
                "created_at": now - timedelta(days=22),
            },
            # DUPIXENT: sensitivity - modified ITT
            {
                "id": "AR-020",
                "plan_id": "SAP-002",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_type": AnalysisType.SENSITIVITY,
                "endpoint": "EASI-75 response rate at Week 16 (mITT)",
                "population": PopulationType.MODIFIED_ITT,
                "method": StatisticalMethod.CHI_SQUARE,
                "estimate": 0.395,
                "confidence_interval_lower": 0.331,
                "confidence_interval_upper": 0.459,
                "p_value": 0.000008,
                "adjusted_p_value": None,
                "clinically_significant": True,
                "n_treatment": 238,
                "n_control": 115,
                "effect_size": 0.60,
                "test_statistic": 25.88,
                "created_at": now - timedelta(days=42),
            },
        ]

        for r in results_data:
            self._results[r["id"]] = AnalysisResult(**r)

        # --- 3 Interim Analyses ---
        interim_data = [
            {
                "id": "IA-001",
                "trial_id": EYLEA_TRIAL,
                "analysis_number": 1,
                "planned_info_fraction": 0.50,
                "actual_info_fraction": 0.48,
                "analysis_date": now - timedelta(days=180),
                "alpha_spent": 0.003,
                "cumulative_alpha_spent": 0.003,
                "boundary_crossed": False,
                "recommendation": InterimRecommendation.CONTINUE,
                "dsmb_review_date": now - timedelta(days=175),
                "z_statistic": 2.12,
                "efficacy_boundary": 2.96,
                "futility_boundary": 0.50,
                "notes": "Positive trend observed. Study continues per protocol. "
                    "No safety concerns identified.",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "IA-002",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_number": 1,
                "planned_info_fraction": 0.50,
                "actual_info_fraction": 0.52,
                "analysis_date": now - timedelta(days=150),
                "alpha_spent": 0.005,
                "cumulative_alpha_spent": 0.005,
                "boundary_crossed": False,
                "recommendation": InterimRecommendation.CONTINUE,
                "dsmb_review_date": now - timedelta(days=145),
                "z_statistic": 3.15,
                "efficacy_boundary": 3.47,
                "futility_boundary": 0.00,
                "notes": "Strong efficacy signal. O'Brien-Fleming boundary not crossed at first "
                    "look. Recommend continuing to final analysis.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "IA-003",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_number": 1,
                "planned_info_fraction": 0.60,
                "actual_info_fraction": 0.58,
                "analysis_date": now - timedelta(days=120),
                "alpha_spent": 0.008,
                "cumulative_alpha_spent": 0.008,
                "boundary_crossed": True,
                "recommendation": InterimRecommendation.STOP_EFFICACY,
                "dsmb_review_date": now - timedelta(days=115),
                "z_statistic": 3.82,
                "efficacy_boundary": 2.58,
                "futility_boundary": 0.50,
                "notes": "Efficacy boundary crossed. Overwhelming evidence of benefit. "
                    "DSMB recommends early stopping for efficacy.",
                "created_at": now - timedelta(days=120),
            },
        ]

        for ia in interim_data:
            self._interim_analyses[ia["id"]] = InterimAnalysis(**ia)

        # --- 3 Sample Size Calculations ---
        ss_data = [
            {
                "id": "SS-001",
                "trial_id": EYLEA_TRIAL,
                "endpoint": "Change from baseline in BCVA (ETDRS letters) at Week 48",
                "assumed_effect_size": 4.0,
                "alpha": 0.025,
                "power": 0.90,
                "dropout_rate": 0.15,
                "calculated_n_per_arm": 286,
                "total_n_with_dropout": 674,
                "method": "Two-sample t-test for non-inferiority",
                "assumptions": "SD=12.5 letters, NI margin=-4 letters, one-sided alpha=0.025, "
                    "90% power, 15% dropout rate",
                "created_at": now - timedelta(days=500),
            },
            {
                "id": "SS-002",
                "trial_id": DUPIXENT_TRIAL,
                "endpoint": "EASI-75 response rate at Week 16",
                "assumed_effect_size": 0.25,
                "alpha": 0.05,
                "power": 0.95,
                "dropout_rate": 0.10,
                "calculated_n_per_arm": 210,
                "total_n_with_dropout": 468,
                "method": "Chi-squared test for two proportions",
                "assumptions": "Treatment rate=37%, placebo rate=12%, two-sided alpha=0.05, "
                    "95% power, 2:1 randomization, 10% dropout",
                "created_at": now - timedelta(days=450),
            },
            {
                "id": "SS-003",
                "trial_id": LIBTAYO_TRIAL,
                "endpoint": "Objective response rate (ORR) per RECIST 1.1",
                "assumed_effect_size": 0.15,
                "alpha": 0.05,
                "power": 0.90,
                "dropout_rate": 0.05,
                "calculated_n_per_arm": 103,
                "total_n_with_dropout": 218,
                "method": "Simon's two-stage optimal design",
                "assumptions": "Null ORR=10%, alternative ORR=25%, alpha=0.05, power=0.90, "
                    "5% dropout, two-stage with futility stopping",
                "created_at": now - timedelta(days=550),
            },
        ]

        for ss in ss_data:
            self._sample_size_calcs[ss["id"]] = SampleSizeCalc(**ss)

        # --- 10 Subgroup Analyses ---
        subgroup_data = [
            # EYLEA subgroups on AR-001 (primary BCVA)
            {
                "id": "SG-001",
                "result_id": "AR-001",
                "subgroup_variable": "age",
                "subgroup_value": "< 65 years",
                "estimate": 9.2,
                "ci_lower": 7.0,
                "ci_upper": 11.4,
                "p_value": 0.0001,
                "n": 285,
                "interaction_p_value": 0.42,
                "created_at": now - timedelta(days=22),
            },
            {
                "id": "SG-002",
                "result_id": "AR-001",
                "subgroup_variable": "age",
                "subgroup_value": ">= 65 years",
                "estimate": 8.1,
                "ci_lower": 6.0,
                "ci_upper": 10.2,
                "p_value": 0.0003,
                "n": 375,
                "interaction_p_value": 0.42,
                "created_at": now - timedelta(days=22),
            },
            {
                "id": "SG-003",
                "result_id": "AR-001",
                "subgroup_variable": "baseline_bcva",
                "subgroup_value": "< 60 letters",
                "estimate": 10.5,
                "ci_lower": 8.1,
                "ci_upper": 12.9,
                "p_value": 0.00005,
                "n": 310,
                "interaction_p_value": 0.08,
                "created_at": now - timedelta(days=22),
            },
            {
                "id": "SG-004",
                "result_id": "AR-001",
                "subgroup_variable": "baseline_bcva",
                "subgroup_value": ">= 60 letters",
                "estimate": 6.8,
                "ci_lower": 4.8,
                "ci_upper": 8.8,
                "p_value": 0.002,
                "n": 350,
                "interaction_p_value": 0.08,
                "created_at": now - timedelta(days=22),
            },
            # DUPIXENT subgroups on AR-007 (primary EASI-75)
            {
                "id": "SG-005",
                "result_id": "AR-007",
                "subgroup_variable": "baseline_easi",
                "subgroup_value": "Moderate (EASI 16-23)",
                "estimate": 0.42,
                "ci_lower": 0.33,
                "ci_upper": 0.51,
                "p_value": 0.00005,
                "n": 168,
                "interaction_p_value": 0.15,
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "SG-006",
                "result_id": "AR-007",
                "subgroup_variable": "baseline_easi",
                "subgroup_value": "Severe (EASI >= 24)",
                "estimate": 0.35,
                "ci_lower": 0.26,
                "ci_upper": 0.44,
                "p_value": 0.0002,
                "n": 192,
                "interaction_p_value": 0.15,
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "SG-007",
                "result_id": "AR-007",
                "subgroup_variable": "prior_systemic_therapy",
                "subgroup_value": "Yes",
                "estimate": 0.38,
                "ci_lower": 0.28,
                "ci_upper": 0.48,
                "p_value": 0.0001,
                "n": 205,
                "interaction_p_value": 0.72,
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "SG-008",
                "result_id": "AR-007",
                "subgroup_variable": "prior_systemic_therapy",
                "subgroup_value": "No",
                "estimate": 0.40,
                "ci_lower": 0.29,
                "ci_upper": 0.51,
                "p_value": 0.0003,
                "n": 155,
                "interaction_p_value": 0.72,
                "created_at": now - timedelta(days=35),
            },
            # LIBTAYO subgroups on AR-013 (primary ORR)
            {
                "id": "SG-009",
                "result_id": "AR-013",
                "subgroup_variable": "pd_l1_expression",
                "subgroup_value": "PD-L1 >= 50%",
                "estimate": 0.392,
                "ci_lower": 0.268,
                "ci_upper": 0.516,
                "p_value": 0.0004,
                "n": 103,
                "interaction_p_value": 0.02,
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "SG-010",
                "result_id": "AR-013",
                "subgroup_variable": "pd_l1_expression",
                "subgroup_value": "PD-L1 1-49%",
                "estimate": 0.158,
                "ci_lower": 0.072,
                "ci_upper": 0.244,
                "p_value": 0.12,
                "n": 114,
                "interaction_p_value": 0.02,
                "created_at": now - timedelta(days=45),
            },
        ]

        for sg in subgroup_data:
            self._subgroup_analyses[sg["id"]] = SubgroupAnalysis(**sg)

    # ------------------------------------------------------------------
    # SAP Management
    # ------------------------------------------------------------------

    def list_saps(
        self,
        *,
        trial_id: str | None = None,
        status: str | None = None,
    ) -> list[StatisticalAnalysisPlan]:
        """List SAPs with optional filters."""
        with self._lock:
            result = list(self._saps.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if status is not None:
            result = [s for s in result if s.status == status]

        return sorted(result, key=lambda s: s.id)

    def get_sap(self, sap_id: str) -> StatisticalAnalysisPlan | None:
        """Get a single SAP by ID."""
        with self._lock:
            return self._saps.get(sap_id)

    def create_sap(self, payload: SAPCreate) -> StatisticalAnalysisPlan:
        """Create a new SAP."""
        now = datetime.now(timezone.utc)
        sap_id = f"SAP-{uuid4().hex[:8].upper()}"
        sap = StatisticalAnalysisPlan(
            id=sap_id,
            **payload.model_dump(),
            status="draft",
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._saps[sap_id] = sap
        logger.info("Created SAP %s: %s", sap_id, payload.title)
        return sap

    def update_sap(self, sap_id: str, payload: SAPUpdate) -> StatisticalAnalysisPlan | None:
        """Update an existing SAP."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._saps.get(sap_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            data["updated_at"] = now
            updated = StatisticalAnalysisPlan(**data)
            self._saps[sap_id] = updated
        return updated

    def delete_sap(self, sap_id: str) -> bool:
        """Delete a SAP. Returns True if deleted, False if not found."""
        with self._lock:
            if sap_id in self._saps:
                del self._saps[sap_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Analysis Results
    # ------------------------------------------------------------------

    def list_analysis_results(
        self,
        *,
        trial_id: str | None = None,
        plan_id: str | None = None,
        analysis_type: AnalysisType | None = None,
        population: PopulationType | None = None,
        significant_only: bool | None = None,
    ) -> list[AnalysisResult]:
        """List analysis results with optional filters."""
        with self._lock:
            result = list(self._results.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if plan_id is not None:
            result = [r for r in result if r.plan_id == plan_id]
        if analysis_type is not None:
            result = [r for r in result if r.analysis_type == analysis_type]
        if population is not None:
            result = [r for r in result if r.population == population]
        if significant_only is True:
            result = [r for r in result if r.p_value < 0.05]

        return sorted(result, key=lambda r: r.id)

    def get_analysis_result(self, result_id: str) -> AnalysisResult | None:
        """Get a single analysis result by ID."""
        with self._lock:
            return self._results.get(result_id)

    def create_analysis_result(self, payload: AnalysisResultCreate) -> AnalysisResult:
        """Record a new analysis result."""
        now = datetime.now(timezone.utc)
        result_id = f"AR-{uuid4().hex[:8].upper()}"

        # Validate plan exists
        with self._lock:
            if payload.plan_id not in self._saps:
                raise ValueError(f"SAP '{payload.plan_id}' not found")

        result = AnalysisResult(
            id=result_id,
            **payload.model_dump(),
            created_at=now,
        )
        with self._lock:
            self._results[result_id] = result
        logger.info(
            "Recorded analysis result %s: %s (%s)",
            result_id, payload.endpoint, payload.analysis_type.value,
        )
        return result

    def delete_analysis_result(self, result_id: str) -> bool:
        """Delete an analysis result. Returns True if deleted."""
        with self._lock:
            if result_id in self._results:
                del self._results[result_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Interim Analyses
    # ------------------------------------------------------------------

    def list_interim_analyses(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[InterimAnalysis]:
        """List interim analyses with optional trial filter."""
        with self._lock:
            result = list(self._interim_analyses.values())

        if trial_id is not None:
            result = [ia for ia in result if ia.trial_id == trial_id]

        return sorted(result, key=lambda ia: (ia.trial_id, ia.analysis_number))

    def get_interim_analysis(self, ia_id: str) -> InterimAnalysis | None:
        """Get a single interim analysis by ID."""
        with self._lock:
            return self._interim_analyses.get(ia_id)

    def create_interim_analysis(self, payload: InterimAnalysisCreate) -> InterimAnalysis:
        """Record a new interim analysis."""
        now = datetime.now(timezone.utc)
        ia_id = f"IA-{uuid4().hex[:8].upper()}"

        ia = InterimAnalysis(
            id=ia_id,
            **payload.model_dump(),
            created_at=now,
        )
        with self._lock:
            self._interim_analyses[ia_id] = ia
        logger.info(
            "Recorded interim analysis %s: trial=%s number=%d recommendation=%s",
            ia_id, payload.trial_id, payload.analysis_number,
            payload.recommendation.value,
        )
        return ia

    def get_alpha_spending_summary(self, trial_id: str) -> dict:
        """Get alpha spending summary for a trial.

        Returns cumulative alpha spent across interim looks and remaining budget.
        """
        with self._lock:
            ias = [
                ia for ia in self._interim_analyses.values()
                if ia.trial_id == trial_id
            ]

        if not ias:
            # Look up alpha from SAP
            sap = next(
                (s for s in self._saps.values() if s.trial_id == trial_id),
                None,
            )
            total_alpha = sap.alpha_level if sap else 0.05
            return {
                "trial_id": trial_id,
                "total_alpha": total_alpha,
                "cumulative_alpha_spent": 0.0,
                "alpha_remaining": total_alpha,
                "interim_looks": 0,
                "boundary_crossed": False,
            }

        sorted_ias = sorted(ias, key=lambda x: x.analysis_number)
        last_ia = sorted_ias[-1]

        sap = next(
            (s for s in self._saps.values() if s.trial_id == trial_id),
            None,
        )
        total_alpha = sap.alpha_level if sap else 0.05

        return {
            "trial_id": trial_id,
            "total_alpha": total_alpha,
            "cumulative_alpha_spent": last_ia.cumulative_alpha_spent,
            "alpha_remaining": round(total_alpha - last_ia.cumulative_alpha_spent, 6),
            "interim_looks": len(sorted_ias),
            "boundary_crossed": any(ia.boundary_crossed for ia in sorted_ias),
        }

    # ------------------------------------------------------------------
    # Sample Size Calculations
    # ------------------------------------------------------------------

    def list_sample_size_calcs(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[SampleSizeCalc]:
        """List sample size calculations with optional trial filter."""
        with self._lock:
            result = list(self._sample_size_calcs.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]

        return sorted(result, key=lambda s: s.id)

    def get_sample_size_calc(self, calc_id: str) -> SampleSizeCalc | None:
        """Get a single sample size calculation by ID."""
        with self._lock:
            return self._sample_size_calcs.get(calc_id)

    # ------------------------------------------------------------------
    # Subgroup Analyses
    # ------------------------------------------------------------------

    def list_subgroup_analyses(
        self,
        *,
        result_id: str | None = None,
        subgroup_variable: str | None = None,
    ) -> list[SubgroupAnalysis]:
        """List subgroup analyses with optional filters."""
        with self._lock:
            result = list(self._subgroup_analyses.values())

        if result_id is not None:
            result = [sg for sg in result if sg.result_id == result_id]
        if subgroup_variable is not None:
            result = [sg for sg in result if sg.subgroup_variable == subgroup_variable]

        return sorted(result, key=lambda sg: sg.id)

    def get_subgroup_analysis(self, sg_id: str) -> SubgroupAnalysis | None:
        """Get a single subgroup analysis by ID."""
        with self._lock:
            return self._subgroup_analyses.get(sg_id)

    def create_subgroup_analysis(self, payload: SubgroupAnalysisCreate) -> SubgroupAnalysis:
        """Record a new subgroup analysis result."""
        now = datetime.now(timezone.utc)
        sg_id = f"SG-{uuid4().hex[:8].upper()}"

        # Validate result exists
        with self._lock:
            if payload.result_id not in self._results:
                raise ValueError(f"Analysis result '{payload.result_id}' not found")

        sg = SubgroupAnalysis(
            id=sg_id,
            **payload.model_dump(),
            created_at=now,
        )
        with self._lock:
            self._subgroup_analyses[sg_id] = sg
        logger.info(
            "Recorded subgroup analysis %s: %s=%s for result %s",
            sg_id, payload.subgroup_variable, payload.subgroup_value,
            payload.result_id,
        )
        return sg

    # ------------------------------------------------------------------
    # Multiplicity Adjustment
    # ------------------------------------------------------------------

    def get_multiplicity_summary(self, plan_id: str) -> dict:
        """Get multiplicity adjustment summary for a SAP.

        Returns count of tests, adjusted significance threshold, and
        list of results with their adjusted p-values.
        """
        with self._lock:
            sap = self._saps.get(plan_id)
            if sap is None:
                return {}

            results = [
                r for r in self._results.values()
                if r.plan_id == plan_id
            ]

        primary_results = [r for r in results if r.analysis_type == AnalysisType.PRIMARY]
        secondary_results = [r for r in results if r.analysis_type == AnalysisType.SECONDARY]

        return {
            "plan_id": plan_id,
            "multiplicity_method": sap.multiplicity_strategy.value,
            "alpha_level": sap.alpha_level,
            "total_tests": len(results),
            "primary_tests": len(primary_results),
            "secondary_tests": len(secondary_results),
            "primary_significant": sum(
                1 for r in primary_results
                if r.adjusted_p_value is not None and r.adjusted_p_value < sap.alpha_level
            ),
            "secondary_significant": sum(
                1 for r in secondary_results
                if r.adjusted_p_value is not None and r.adjusted_p_value < sap.alpha_level
            ),
        }

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self) -> StatisticalMetrics:
        """Compute aggregated statistical analysis metrics."""
        with self._lock:
            results = list(self._results.values())
            saps = list(self._saps.values())
            ias = list(self._interim_analyses.values())
            ss_calcs = list(self._sample_size_calcs.values())
            subgroups = list(self._subgroup_analyses.values())

        # Analyses by type
        by_type: dict[str, int] = {}
        for r in results:
            key = r.analysis_type.value
            by_type[key] = by_type.get(key, 0) + 1

        # Significant results (p < 0.05)
        significant = sum(1 for r in results if r.p_value < 0.05)

        # Average absolute effect size
        if results:
            avg_effect = round(
                sum(abs(r.effect_size) for r in results) / len(results), 3
            )
        else:
            avg_effect = 0.0

        # Alpha remaining: average across trials
        trial_ids = {s.trial_id for s in saps}
        total_alpha_remaining = 0.0
        for tid in trial_ids:
            summary = self.get_alpha_spending_summary(tid)
            total_alpha_remaining += summary["alpha_remaining"]
        avg_alpha_remaining = round(
            total_alpha_remaining / max(1, len(trial_ids)), 6
        )

        # Boundary crossed
        boundary_crossed_trials = len({
            ia.trial_id for ia in ias if ia.boundary_crossed
        })

        return StatisticalMetrics(
            total_analyses=len(results),
            analyses_by_type=by_type,
            significant_results_count=significant,
            avg_effect_size=avg_effect,
            interim_analyses_completed=len(ias),
            alpha_remaining=avg_alpha_remaining,
            total_saps=len(saps),
            total_sample_size_calcs=len(ss_calcs),
            total_subgroup_analyses=len(subgroups),
            trials_with_boundary_crossed=boundary_crossed_trials,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: StatisticalAnalysisService | None = None
_instance_lock = threading.Lock()


def get_stats_service() -> StatisticalAnalysisService:
    """Return the singleton StatisticalAnalysisService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = StatisticalAnalysisService()
    return _instance


def reset_stats_service() -> StatisticalAnalysisService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = StatisticalAnalysisService()
    return _instance
