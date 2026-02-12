"""Bioequivalence Study Management Service (BE-STUDY).

Manages bioequivalence study operations: BE study tracking,
PK parameter analysis, formulation comparison, statistical
assessments, and regulatory filing with compliance metrics.

Usage:
    from app.services.bioequivalence_service import (
        get_bioequivalence_service,
    )

    svc = get_bioequivalence_service()
    studies = svc.list_be_studies()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.bioequivalence import (
    BECriterion,
    BEResult,
    BEStudy,
    BEStudyCreate,
    BEStudyUpdate,
    BioequivalenceMetrics,
    FormulationComparison,
    FormulationComparisonCreate,
    FormulationComparisonUpdate,
    PKParameter,
    PKParameterCreate,
    PKParameterName,
    PKParameterUpdate,
    RegulatoryFiling,
    RegulatoryFilingCreate,
    RegulatoryFilingUpdate,
    StatisticalAssessment,
    StatisticalAssessmentCreate,
    StatisticalAssessmentUpdate,
    StudyDesign,
    StudyStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class BioequivalenceService:
    """In-memory Bioequivalence Study engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._be_studies: dict[str, BEStudy] = {}
        self._pk_parameters: dict[str, PKParameter] = {}
        self._formulation_comparisons: dict[str, FormulationComparison] = {}
        self._statistical_assessments: dict[str, StatisticalAssessment] = {}
        self._regulatory_filings: dict[str, RegulatoryFiling] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic bioequivalence study data."""
        now = datetime.now(timezone.utc)

        # --- 12 BE Studies ---
        studies_data = [
            {
                "id": "BE-001",
                "trial_id": EYLEA_TRIAL,
                "study_name": "EYLEA Biosimilar PFS vs Vial 2mg Crossover",
                "study_design": StudyDesign.CROSSOVER_2X2,
                "status": StudyStatus.COMPLETED,
                "reference_product": "Aflibercept 2mg/0.05mL Vial (Regeneron)",
                "test_product": "Aflibercept 2mg/0.05mL Pre-filled Syringe",
                "route_of_administration": "intravitreal",
                "dosage_strength": "2mg/0.05mL",
                "subjects_planned": 60,
                "subjects_enrolled": 62,
                "subjects_completed": 58,
                "washout_period_days": 28,
                "fasting_fed": "fasting",
                "be_criterion": BECriterion.STANDARD_80_125,
                "overall_result": BEResult.BIOEQUIVALENT,
                "start_date": now - timedelta(days=360),
                "completion_date": now - timedelta(days=90),
                "principal_investigator": "Dr. Sarah Chen",
                "sponsor": "Regeneron Pharmaceuticals",
                "notes": "Successful BE demonstration for PFS formulation.",
                "created_at": now - timedelta(days=400),
            },
            {
                "id": "BE-002",
                "trial_id": EYLEA_TRIAL,
                "study_name": "EYLEA 8mg High-Dose BE Study",
                "study_design": StudyDesign.PARALLEL,
                "status": StudyStatus.IN_PROGRESS,
                "reference_product": "Aflibercept 2mg/0.05mL Vial",
                "test_product": "Aflibercept 8mg/0.07mL Vial (EYLEA HD)",
                "route_of_administration": "intravitreal",
                "dosage_strength": "8mg/0.07mL",
                "subjects_planned": 80,
                "subjects_enrolled": 75,
                "subjects_completed": 40,
                "washout_period_days": 56,
                "fasting_fed": "fasting",
                "be_criterion": BECriterion.WIDE_75_133,
                "overall_result": BEResult.PENDING,
                "start_date": now - timedelta(days=180),
                "completion_date": None,
                "principal_investigator": "Dr. Sarah Chen",
                "sponsor": "Regeneron Pharmaceuticals",
                "notes": "High-dose formulation comparison. Extended washout due to long half-life.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "BE-003",
                "trial_id": EYLEA_TRIAL,
                "study_name": "EYLEA Multi-Dose Vial Preservative-Free BE",
                "study_design": StudyDesign.CROSSOVER_3X3,
                "status": StudyStatus.ANALYSIS,
                "reference_product": "Aflibercept 2mg/0.05mL Single-Use Vial",
                "test_product": "Aflibercept 2mg/0.05mL Multi-Dose Vial (PF)",
                "route_of_administration": "intravitreal",
                "dosage_strength": "2mg/0.05mL",
                "subjects_planned": 48,
                "subjects_enrolled": 48,
                "subjects_completed": 45,
                "washout_period_days": 28,
                "fasting_fed": "fasting",
                "be_criterion": BECriterion.STANDARD_80_125,
                "overall_result": BEResult.PENDING,
                "start_date": now - timedelta(days=240),
                "completion_date": now - timedelta(days=30),
                "principal_investigator": "Dr. James Wright",
                "sponsor": "Regeneron Pharmaceuticals",
                "notes": "3-period crossover to assess multi-dose vial stability.",
                "created_at": now - timedelta(days=260),
            },
            {
                "id": "BE-004",
                "trial_id": DUPIXENT_TRIAL,
                "study_name": "DUPIXENT Autoinjector vs PFS Subcutaneous BE",
                "study_design": StudyDesign.CROSSOVER_2X2,
                "status": StudyStatus.COMPLETED,
                "reference_product": "Dupilumab 300mg/2mL Pre-filled Syringe",
                "test_product": "Dupilumab 300mg/2mL Autoinjector",
                "route_of_administration": "subcutaneous",
                "dosage_strength": "300mg/2mL",
                "subjects_planned": 120,
                "subjects_enrolled": 124,
                "subjects_completed": 118,
                "washout_period_days": 42,
                "fasting_fed": "fasting",
                "be_criterion": BECriterion.STANDARD_80_125,
                "overall_result": BEResult.BIOEQUIVALENT,
                "start_date": now - timedelta(days=300),
                "completion_date": now - timedelta(days=60),
                "principal_investigator": "Dr. Maria Lopez",
                "sponsor": "Sanofi / Regeneron",
                "notes": "Pivotal BE study for autoinjector device switch.",
                "created_at": now - timedelta(days=320),
            },
            {
                "id": "BE-005",
                "trial_id": DUPIXENT_TRIAL,
                "study_name": "DUPIXENT High-Concentration 200mg/mL BE",
                "study_design": StudyDesign.REPLICATE,
                "status": StudyStatus.IN_PROGRESS,
                "reference_product": "Dupilumab 300mg/2mL (150mg/mL)",
                "test_product": "Dupilumab 300mg/1.5mL (200mg/mL)",
                "route_of_administration": "subcutaneous",
                "dosage_strength": "300mg/1.5mL",
                "subjects_planned": 90,
                "subjects_enrolled": 85,
                "subjects_completed": 50,
                "washout_period_days": 42,
                "fasting_fed": "fasting",
                "be_criterion": BECriterion.SCALED_ABE,
                "overall_result": BEResult.PENDING,
                "start_date": now - timedelta(days=150),
                "completion_date": None,
                "principal_investigator": "Dr. Maria Lopez",
                "sponsor": "Sanofi / Regeneron",
                "notes": "Replicate design to allow scaled ABE assessment for highly variable drug.",
                "created_at": now - timedelta(days=170),
            },
            {
                "id": "BE-006",
                "trial_id": DUPIXENT_TRIAL,
                "study_name": "DUPIXENT Pediatric Formulation BE",
                "study_design": StudyDesign.PARALLEL,
                "status": StudyStatus.ENROLLED,
                "reference_product": "Dupilumab 200mg/1.14mL PFS",
                "test_product": "Dupilumab 200mg/1.14mL Pediatric Autoinjector",
                "route_of_administration": "subcutaneous",
                "dosage_strength": "200mg/1.14mL",
                "subjects_planned": 72,
                "subjects_enrolled": 72,
                "subjects_completed": 0,
                "washout_period_days": 35,
                "fasting_fed": "fasting",
                "be_criterion": BECriterion.STANDARD_80_125,
                "overall_result": BEResult.PENDING,
                "start_date": now - timedelta(days=45),
                "completion_date": None,
                "principal_investigator": "Dr. Robert Kim",
                "sponsor": "Sanofi / Regeneron",
                "notes": "Pediatric autoinjector device bridging study.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "BE-007",
                "trial_id": DUPIXENT_TRIAL,
                "study_name": "DUPIXENT Fed vs Fasting Interaction BE",
                "study_design": StudyDesign.CROSSOVER_2X2,
                "status": StudyStatus.COMPLETED,
                "reference_product": "Dupilumab 300mg/2mL PFS (fasting)",
                "test_product": "Dupilumab 300mg/2mL PFS (fed)",
                "route_of_administration": "subcutaneous",
                "dosage_strength": "300mg/2mL",
                "subjects_planned": 36,
                "subjects_enrolled": 36,
                "subjects_completed": 34,
                "washout_period_days": 42,
                "fasting_fed": "fed",
                "be_criterion": BECriterion.STANDARD_80_125,
                "overall_result": BEResult.BIOEQUIVALENT,
                "start_date": now - timedelta(days=280),
                "completion_date": now - timedelta(days=120),
                "principal_investigator": "Dr. Robert Kim",
                "sponsor": "Sanofi / Regeneron",
                "notes": "Food effect study. SC administration not expected to be affected.",
                "created_at": now - timedelta(days=300),
            },
            {
                "id": "BE-008",
                "trial_id": LIBTAYO_TRIAL,
                "study_name": "LIBTAYO IV Infusion Rate BE Study",
                "study_design": StudyDesign.CROSSOVER_2X2,
                "status": StudyStatus.COMPLETED,
                "reference_product": "Cemiplimab 350mg/7mL IV (30-min infusion)",
                "test_product": "Cemiplimab 350mg/7mL IV (60-min infusion)",
                "route_of_administration": "intravenous",
                "dosage_strength": "350mg/7mL",
                "subjects_planned": 50,
                "subjects_enrolled": 52,
                "subjects_completed": 49,
                "washout_period_days": 21,
                "fasting_fed": "fasting",
                "be_criterion": BECriterion.STANDARD_80_125,
                "overall_result": BEResult.BIOEQUIVALENT,
                "start_date": now - timedelta(days=250),
                "completion_date": now - timedelta(days=80),
                "principal_investigator": "Dr. Angela Park",
                "sponsor": "Regeneron Pharmaceuticals",
                "notes": "Infusion rate comparison. Both rates demonstrated equivalent PK.",
                "created_at": now - timedelta(days=270),
            },
            {
                "id": "BE-009",
                "trial_id": LIBTAYO_TRIAL,
                "study_name": "LIBTAYO SC vs IV Formulation Bridge",
                "study_design": StudyDesign.SEQUENTIAL,
                "status": StudyStatus.IN_PROGRESS,
                "reference_product": "Cemiplimab 350mg/7mL IV Infusion",
                "test_product": "Cemiplimab 350mg/2.5mL SC Injection",
                "route_of_administration": "subcutaneous",
                "dosage_strength": "350mg/2.5mL",
                "subjects_planned": 100,
                "subjects_enrolled": 90,
                "subjects_completed": 55,
                "washout_period_days": 21,
                "fasting_fed": "fasting",
                "be_criterion": BECriterion.WIDE_75_133,
                "overall_result": BEResult.PENDING,
                "start_date": now - timedelta(days=120),
                "completion_date": None,
                "principal_investigator": "Dr. Angela Park",
                "sponsor": "Regeneron Pharmaceuticals",
                "notes": "Sequential design for IV-to-SC bridging. Wider limits justified by route change.",
                "created_at": now - timedelta(days=140),
            },
            {
                "id": "BE-010",
                "trial_id": LIBTAYO_TRIAL,
                "study_name": "LIBTAYO Biosimilar Comparability",
                "study_design": StudyDesign.ADAPTIVE,
                "status": StudyStatus.PLANNED,
                "reference_product": "Cemiplimab 350mg/7mL IV (Regeneron)",
                "test_product": "Cemiplimab Biosimilar Candidate CMP-001",
                "route_of_administration": "intravenous",
                "dosage_strength": "350mg/7mL",
                "subjects_planned": 150,
                "subjects_enrolled": 0,
                "subjects_completed": 0,
                "washout_period_days": 21,
                "fasting_fed": "fasting",
                "be_criterion": BECriterion.STANDARD_80_125,
                "overall_result": BEResult.PENDING,
                "start_date": None,
                "completion_date": None,
                "principal_investigator": "Dr. Angela Park",
                "sponsor": "Regeneron Pharmaceuticals",
                "notes": "Adaptive design allowing sample size re-estimation at interim.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "BE-011",
                "trial_id": EYLEA_TRIAL,
                "study_name": "EYLEA Tmax Non-parametric Assessment",
                "study_design": StudyDesign.CROSSOVER_2X2,
                "status": StudyStatus.COMPLETED,
                "reference_product": "Aflibercept 2mg/0.05mL Vial",
                "test_product": "Aflibercept 2mg/0.05mL PFS",
                "route_of_administration": "intravitreal",
                "dosage_strength": "2mg/0.05mL",
                "subjects_planned": 40,
                "subjects_enrolled": 40,
                "subjects_completed": 38,
                "washout_period_days": 28,
                "fasting_fed": "fasting",
                "be_criterion": BECriterion.TMAX_NONPARAMETRIC,
                "overall_result": BEResult.BIOEQUIVALENT,
                "start_date": now - timedelta(days=400),
                "completion_date": now - timedelta(days=200),
                "principal_investigator": "Dr. James Wright",
                "sponsor": "Regeneron Pharmaceuticals",
                "notes": "Tmax assessment using non-parametric Wilcoxon signed-rank test.",
                "created_at": now - timedelta(days=420),
            },
            {
                "id": "BE-012",
                "trial_id": LIBTAYO_TRIAL,
                "study_name": "LIBTAYO Manufacturing Site Change BE",
                "study_design": StudyDesign.CROSSOVER_2X2,
                "status": StudyStatus.FAILED,
                "reference_product": "Cemiplimab 350mg/7mL (Site A)",
                "test_product": "Cemiplimab 350mg/7mL (Site B)",
                "route_of_administration": "intravenous",
                "dosage_strength": "350mg/7mL",
                "subjects_planned": 60,
                "subjects_enrolled": 60,
                "subjects_completed": 56,
                "washout_period_days": 21,
                "fasting_fed": "fasting",
                "be_criterion": BECriterion.NARROW_90_111,
                "overall_result": BEResult.NOT_BIOEQUIVALENT,
                "start_date": now - timedelta(days=350),
                "completion_date": now - timedelta(days=150),
                "principal_investigator": "Dr. Angela Park",
                "sponsor": "Regeneron Pharmaceuticals",
                "notes": "Failed narrow BE criteria. Manufacturing process at Site B requires optimization.",
                "created_at": now - timedelta(days=370),
            },
        ]

        for s in studies_data:
            self._be_studies[s["id"]] = BEStudy(**s)

        # --- 12 PK Parameters ---
        pk_data = [
            {
                "id": "PK-001",
                "trial_id": EYLEA_TRIAL,
                "study_id": "BE-001",
                "parameter_name": PKParameterName.AUC_0_INF,
                "formulation": "reference",
                "subject_count": 58,
                "geometric_mean": 4520.5,
                "arithmetic_mean": 4780.2,
                "cv_pct": 28.3,
                "median": 4450.0,
                "min_value": 2180.0,
                "max_value": 8920.0,
                "unit": "ng*h/mL",
                "ln_transformed": True,
                "analyzed_by": "Dr. Sarah Chen",
                "analysis_date": now - timedelta(days=95),
                "notes": "Reference arm AUC analysis.",
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "PK-002",
                "trial_id": EYLEA_TRIAL,
                "study_id": "BE-001",
                "parameter_name": PKParameterName.AUC_0_INF,
                "formulation": "test",
                "subject_count": 58,
                "geometric_mean": 4610.8,
                "arithmetic_mean": 4850.6,
                "cv_pct": 27.1,
                "median": 4510.0,
                "min_value": 2250.0,
                "max_value": 8750.0,
                "unit": "ng*h/mL",
                "ln_transformed": True,
                "analyzed_by": "Dr. Sarah Chen",
                "analysis_date": now - timedelta(days=95),
                "notes": "Test arm AUC analysis.",
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "PK-003",
                "trial_id": EYLEA_TRIAL,
                "study_id": "BE-001",
                "parameter_name": PKParameterName.CMAX,
                "formulation": "reference",
                "subject_count": 58,
                "geometric_mean": 185.4,
                "arithmetic_mean": 198.7,
                "cv_pct": 32.5,
                "median": 180.0,
                "min_value": 78.0,
                "max_value": 410.0,
                "unit": "ng/mL",
                "ln_transformed": True,
                "analyzed_by": "Dr. Sarah Chen",
                "analysis_date": now - timedelta(days=95),
                "notes": None,
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "PK-004",
                "trial_id": EYLEA_TRIAL,
                "study_id": "BE-001",
                "parameter_name": PKParameterName.CMAX,
                "formulation": "test",
                "subject_count": 58,
                "geometric_mean": 190.2,
                "arithmetic_mean": 203.1,
                "cv_pct": 31.8,
                "median": 185.0,
                "min_value": 82.0,
                "max_value": 395.0,
                "unit": "ng/mL",
                "ln_transformed": True,
                "analyzed_by": "Dr. Sarah Chen",
                "analysis_date": now - timedelta(days=95),
                "notes": None,
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "PK-005",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "BE-004",
                "parameter_name": PKParameterName.AUC_0_T,
                "formulation": "reference",
                "subject_count": 118,
                "geometric_mean": 1850.3,
                "arithmetic_mean": 1980.5,
                "cv_pct": 35.2,
                "median": 1800.0,
                "min_value": 680.0,
                "max_value": 4200.0,
                "unit": "mg*h/L",
                "ln_transformed": True,
                "analyzed_by": "Dr. Maria Lopez",
                "analysis_date": now - timedelta(days=65),
                "notes": "PFS reference arm pharmacokinetics.",
                "created_at": now - timedelta(days=65),
            },
            {
                "id": "PK-006",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "BE-004",
                "parameter_name": PKParameterName.AUC_0_T,
                "formulation": "test",
                "subject_count": 118,
                "geometric_mean": 1890.1,
                "arithmetic_mean": 2020.8,
                "cv_pct": 34.8,
                "median": 1840.0,
                "min_value": 700.0,
                "max_value": 4350.0,
                "unit": "mg*h/L",
                "ln_transformed": True,
                "analyzed_by": "Dr. Maria Lopez",
                "analysis_date": now - timedelta(days=65),
                "notes": "Autoinjector test arm pharmacokinetics.",
                "created_at": now - timedelta(days=65),
            },
            {
                "id": "PK-007",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "BE-004",
                "parameter_name": PKParameterName.TMAX,
                "formulation": "reference",
                "subject_count": 118,
                "geometric_mean": 168.0,
                "arithmetic_mean": 172.5,
                "cv_pct": 42.1,
                "median": 168.0,
                "min_value": 48.0,
                "max_value": 336.0,
                "unit": "h",
                "ln_transformed": False,
                "analyzed_by": "Dr. Maria Lopez",
                "analysis_date": now - timedelta(days=65),
                "notes": "Tmax for SC administration. Wide variability expected.",
                "created_at": now - timedelta(days=65),
            },
            {
                "id": "PK-008",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "BE-008",
                "parameter_name": PKParameterName.AUC_0_INF,
                "formulation": "reference",
                "subject_count": 49,
                "geometric_mean": 28500.0,
                "arithmetic_mean": 30200.0,
                "cv_pct": 22.5,
                "median": 27800.0,
                "min_value": 15200.0,
                "max_value": 52000.0,
                "unit": "ug*h/mL",
                "ln_transformed": True,
                "analyzed_by": "Dr. Angela Park",
                "analysis_date": now - timedelta(days=85),
                "notes": "30-min infusion reference PK.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "PK-009",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "BE-008",
                "parameter_name": PKParameterName.AUC_0_INF,
                "formulation": "test",
                "subject_count": 49,
                "geometric_mean": 28200.0,
                "arithmetic_mean": 29800.0,
                "cv_pct": 23.1,
                "median": 27500.0,
                "min_value": 14800.0,
                "max_value": 51500.0,
                "unit": "ug*h/mL",
                "ln_transformed": True,
                "analyzed_by": "Dr. Angela Park",
                "analysis_date": now - timedelta(days=85),
                "notes": "60-min infusion test PK.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "PK-010",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "BE-008",
                "parameter_name": PKParameterName.CMAX,
                "formulation": "reference",
                "subject_count": 49,
                "geometric_mean": 152.0,
                "arithmetic_mean": 160.8,
                "cv_pct": 25.4,
                "median": 148.0,
                "min_value": 82.0,
                "max_value": 290.0,
                "unit": "ug/mL",
                "ln_transformed": True,
                "analyzed_by": "Dr. Angela Park",
                "analysis_date": now - timedelta(days=85),
                "notes": None,
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "PK-011",
                "trial_id": EYLEA_TRIAL,
                "study_id": "BE-001",
                "parameter_name": PKParameterName.T_HALF,
                "formulation": "reference",
                "subject_count": 58,
                "geometric_mean": 5.6,
                "arithmetic_mean": 5.9,
                "cv_pct": 18.2,
                "median": 5.5,
                "min_value": 3.2,
                "max_value": 9.1,
                "unit": "days",
                "ln_transformed": True,
                "analyzed_by": "Dr. Sarah Chen",
                "analysis_date": now - timedelta(days=95),
                "notes": "Terminal half-life estimation.",
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "PK-012",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "BE-004",
                "parameter_name": PKParameterName.CL_F,
                "formulation": "test",
                "subject_count": 118,
                "geometric_mean": 0.042,
                "arithmetic_mean": 0.045,
                "cv_pct": 38.5,
                "median": 0.041,
                "min_value": 0.018,
                "max_value": 0.095,
                "unit": "L/h",
                "ln_transformed": True,
                "analyzed_by": "Dr. Maria Lopez",
                "analysis_date": now - timedelta(days=65),
                "notes": "Apparent clearance for autoinjector formulation.",
                "created_at": now - timedelta(days=65),
            },
        ]

        for p in pk_data:
            self._pk_parameters[p["id"]] = PKParameter(**p)

        # --- 12 Formulation Comparisons ---
        comparisons_data = [
            {
                "id": "FC-001",
                "trial_id": EYLEA_TRIAL,
                "study_id": "BE-001",
                "parameter_name": PKParameterName.AUC_0_INF,
                "test_gmean": 4610.8,
                "reference_gmean": 4520.5,
                "ratio_pct": 102.0,
                "ci_lower_pct": 95.4,
                "ci_upper_pct": 109.0,
                "be_criterion": BECriterion.STANDARD_80_125,
                "within_limits": True,
                "result": BEResult.BIOEQUIVALENT,
                "intra_subject_cv_pct": 18.5,
                "power_pct": 92.0,
                "method": "ANOVA",
                "analyzed_by": "Dr. Sarah Chen",
                "analysis_date": now - timedelta(days=93),
                "notes": "AUC ratio within 80-125% limits.",
                "created_at": now - timedelta(days=93),
            },
            {
                "id": "FC-002",
                "trial_id": EYLEA_TRIAL,
                "study_id": "BE-001",
                "parameter_name": PKParameterName.CMAX,
                "test_gmean": 190.2,
                "reference_gmean": 185.4,
                "ratio_pct": 102.6,
                "ci_lower_pct": 93.8,
                "ci_upper_pct": 112.1,
                "be_criterion": BECriterion.STANDARD_80_125,
                "within_limits": True,
                "result": BEResult.BIOEQUIVALENT,
                "intra_subject_cv_pct": 22.3,
                "power_pct": 88.5,
                "method": "ANOVA",
                "analyzed_by": "Dr. Sarah Chen",
                "analysis_date": now - timedelta(days=93),
                "notes": "Cmax ratio within 80-125% limits.",
                "created_at": now - timedelta(days=93),
            },
            {
                "id": "FC-003",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "BE-004",
                "parameter_name": PKParameterName.AUC_0_T,
                "test_gmean": 1890.1,
                "reference_gmean": 1850.3,
                "ratio_pct": 102.2,
                "ci_lower_pct": 97.1,
                "ci_upper_pct": 107.5,
                "be_criterion": BECriterion.STANDARD_80_125,
                "within_limits": True,
                "result": BEResult.BIOEQUIVALENT,
                "intra_subject_cv_pct": 15.2,
                "power_pct": 95.0,
                "method": "ANOVA",
                "analyzed_by": "Dr. Maria Lopez",
                "analysis_date": now - timedelta(days=63),
                "notes": "Autoinjector demonstrates equivalent AUC.",
                "created_at": now - timedelta(days=63),
            },
            {
                "id": "FC-004",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "BE-008",
                "parameter_name": PKParameterName.AUC_0_INF,
                "test_gmean": 28200.0,
                "reference_gmean": 28500.0,
                "ratio_pct": 98.9,
                "ci_lower_pct": 93.2,
                "ci_upper_pct": 105.0,
                "be_criterion": BECriterion.STANDARD_80_125,
                "within_limits": True,
                "result": BEResult.BIOEQUIVALENT,
                "intra_subject_cv_pct": 14.8,
                "power_pct": 96.5,
                "method": "ANOVA",
                "analyzed_by": "Dr. Angela Park",
                "analysis_date": now - timedelta(days=83),
                "notes": "Infusion rate comparison AUC within limits.",
                "created_at": now - timedelta(days=83),
            },
            {
                "id": "FC-005",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "BE-012",
                "parameter_name": PKParameterName.AUC_0_INF,
                "test_gmean": 26800.0,
                "reference_gmean": 28500.0,
                "ratio_pct": 94.0,
                "ci_lower_pct": 88.5,
                "ci_upper_pct": 99.9,
                "be_criterion": BECriterion.NARROW_90_111,
                "within_limits": False,
                "result": BEResult.NOT_BIOEQUIVALENT,
                "intra_subject_cv_pct": 16.2,
                "power_pct": 78.0,
                "method": "ANOVA",
                "analyzed_by": "Dr. Angela Park",
                "analysis_date": now - timedelta(days=155),
                "notes": "CI lower bound 88.5% below narrow criterion 90%. Failed.",
                "created_at": now - timedelta(days=155),
            },
            {
                "id": "FC-006",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "BE-012",
                "parameter_name": PKParameterName.CMAX,
                "test_gmean": 140.0,
                "reference_gmean": 152.0,
                "ratio_pct": 92.1,
                "ci_lower_pct": 86.4,
                "ci_upper_pct": 98.2,
                "be_criterion": BECriterion.NARROW_90_111,
                "within_limits": False,
                "result": BEResult.NOT_BIOEQUIVALENT,
                "intra_subject_cv_pct": 17.8,
                "power_pct": 72.0,
                "method": "ANOVA",
                "analyzed_by": "Dr. Angela Park",
                "analysis_date": now - timedelta(days=155),
                "notes": "Cmax also failed narrow criterion.",
                "created_at": now - timedelta(days=155),
            },
            {
                "id": "FC-007",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "BE-005",
                "parameter_name": PKParameterName.AUC_0_INF,
                "test_gmean": None,
                "reference_gmean": None,
                "ratio_pct": None,
                "ci_lower_pct": None,
                "ci_upper_pct": None,
                "be_criterion": BECriterion.SCALED_ABE,
                "within_limits": False,
                "result": BEResult.PENDING,
                "intra_subject_cv_pct": None,
                "power_pct": None,
                "method": "scaled_ABE_RSABE",
                "analyzed_by": "Dr. Maria Lopez",
                "analysis_date": now - timedelta(days=10),
                "notes": "Interim comparison placeholder. Awaiting complete data.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "FC-008",
                "trial_id": EYLEA_TRIAL,
                "study_id": "BE-003",
                "parameter_name": PKParameterName.AUC_0_T,
                "test_gmean": 4380.0,
                "reference_gmean": 4520.5,
                "ratio_pct": 96.9,
                "ci_lower_pct": 90.1,
                "ci_upper_pct": 104.2,
                "be_criterion": BECriterion.STANDARD_80_125,
                "within_limits": True,
                "result": BEResult.BIOEQUIVALENT,
                "intra_subject_cv_pct": 20.1,
                "power_pct": 90.0,
                "method": "ANOVA",
                "analyzed_by": "Dr. James Wright",
                "analysis_date": now - timedelta(days=35),
                "notes": "Multi-dose vial AUC0-t comparison.",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "FC-009",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "BE-008",
                "parameter_name": PKParameterName.CMAX,
                "test_gmean": 125.0,
                "reference_gmean": 152.0,
                "ratio_pct": 82.2,
                "ci_lower_pct": 76.5,
                "ci_upper_pct": 88.3,
                "be_criterion": BECriterion.STANDARD_80_125,
                "within_limits": False,
                "result": BEResult.INCONCLUSIVE,
                "intra_subject_cv_pct": 19.8,
                "power_pct": 65.0,
                "method": "ANOVA",
                "analyzed_by": "Dr. Angela Park",
                "analysis_date": now - timedelta(days=83),
                "notes": "Cmax lower with 60-min infusion as expected. Clinically acceptable.",
                "created_at": now - timedelta(days=83),
            },
            {
                "id": "FC-010",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "BE-007",
                "parameter_name": PKParameterName.AUC_0_INF,
                "test_gmean": 1870.0,
                "reference_gmean": 1850.3,
                "ratio_pct": 101.1,
                "ci_lower_pct": 96.2,
                "ci_upper_pct": 106.2,
                "be_criterion": BECriterion.STANDARD_80_125,
                "within_limits": True,
                "result": BEResult.BIOEQUIVALENT,
                "intra_subject_cv_pct": 14.0,
                "power_pct": 97.0,
                "method": "ANOVA",
                "analyzed_by": "Dr. Robert Kim",
                "analysis_date": now - timedelta(days=125),
                "notes": "No food effect on SC dupilumab exposure.",
                "created_at": now - timedelta(days=125),
            },
            {
                "id": "FC-011",
                "trial_id": EYLEA_TRIAL,
                "study_id": "BE-011",
                "parameter_name": PKParameterName.TMAX,
                "test_gmean": None,
                "reference_gmean": None,
                "ratio_pct": None,
                "ci_lower_pct": None,
                "ci_upper_pct": None,
                "be_criterion": BECriterion.TMAX_NONPARAMETRIC,
                "within_limits": True,
                "result": BEResult.BIOEQUIVALENT,
                "intra_subject_cv_pct": None,
                "power_pct": None,
                "method": "Wilcoxon_signed_rank",
                "analyzed_by": "Dr. James Wright",
                "analysis_date": now - timedelta(days=205),
                "notes": "Non-parametric Tmax comparison p=0.82.",
                "created_at": now - timedelta(days=205),
            },
            {
                "id": "FC-012",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "BE-009",
                "parameter_name": PKParameterName.AUC_0_INF,
                "test_gmean": None,
                "reference_gmean": None,
                "ratio_pct": None,
                "ci_lower_pct": None,
                "ci_upper_pct": None,
                "be_criterion": BECriterion.WIDE_75_133,
                "within_limits": False,
                "result": BEResult.PENDING,
                "intra_subject_cv_pct": None,
                "power_pct": None,
                "method": "ANOVA",
                "analyzed_by": "Dr. Angela Park",
                "analysis_date": now - timedelta(days=5),
                "notes": "SC vs IV bridging comparison pending full enrollment.",
                "created_at": now - timedelta(days=5),
            },
        ]

        for c in comparisons_data:
            self._formulation_comparisons[c["id"]] = FormulationComparison(**c)

        # --- 10 Statistical Assessments ---
        assessments_data = [
            {
                "id": "SA-001",
                "trial_id": EYLEA_TRIAL,
                "study_id": "BE-001",
                "assessment_name": "BE-001 Primary ANOVA AUC",
                "model_used": "mixed_effects_ANOVA",
                "factors": ["sequence", "period", "treatment", "subject_within_sequence"],
                "sequence_effect_p": 0.72,
                "period_effect_p": 0.45,
                "treatment_effect_p": 0.68,
                "subject_within_sequence_p": 0.001,
                "residual_variance": 0.0342,
                "outliers_detected": 2,
                "outliers_excluded": 0,
                "sensitivity_analysis_done": True,
                "consistent_with_primary": True,
                "assessed_by": "Dr. Sarah Chen",
                "assessment_date": now - timedelta(days=92),
                "notes": "No significant sequence or period effects.",
                "created_at": now - timedelta(days=92),
            },
            {
                "id": "SA-002",
                "trial_id": EYLEA_TRIAL,
                "study_id": "BE-001",
                "assessment_name": "BE-001 Primary ANOVA Cmax",
                "model_used": "mixed_effects_ANOVA",
                "factors": ["sequence", "period", "treatment", "subject_within_sequence"],
                "sequence_effect_p": 0.58,
                "period_effect_p": 0.31,
                "treatment_effect_p": 0.55,
                "subject_within_sequence_p": 0.002,
                "residual_variance": 0.0498,
                "outliers_detected": 1,
                "outliers_excluded": 0,
                "sensitivity_analysis_done": True,
                "consistent_with_primary": True,
                "assessed_by": "Dr. Sarah Chen",
                "assessment_date": now - timedelta(days=92),
                "notes": "Cmax ANOVA consistent with AUC results.",
                "created_at": now - timedelta(days=92),
            },
            {
                "id": "SA-003",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "BE-004",
                "assessment_name": "BE-004 Autoinjector ANOVA AUC0-t",
                "model_used": "mixed_effects_ANOVA",
                "factors": ["sequence", "period", "treatment", "subject_within_sequence"],
                "sequence_effect_p": 0.83,
                "period_effect_p": 0.62,
                "treatment_effect_p": 0.71,
                "subject_within_sequence_p": 0.0001,
                "residual_variance": 0.0231,
                "outliers_detected": 3,
                "outliers_excluded": 1,
                "sensitivity_analysis_done": True,
                "consistent_with_primary": True,
                "assessed_by": "Dr. Maria Lopez",
                "assessment_date": now - timedelta(days=62),
                "notes": "One outlier excluded in sensitivity; results consistent.",
                "created_at": now - timedelta(days=62),
            },
            {
                "id": "SA-004",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "BE-008",
                "assessment_name": "BE-008 Infusion Rate ANOVA",
                "model_used": "mixed_effects_ANOVA",
                "factors": ["sequence", "period", "treatment", "subject_within_sequence"],
                "sequence_effect_p": 0.91,
                "period_effect_p": 0.78,
                "treatment_effect_p": 0.82,
                "subject_within_sequence_p": 0.003,
                "residual_variance": 0.0218,
                "outliers_detected": 0,
                "outliers_excluded": 0,
                "sensitivity_analysis_done": False,
                "consistent_with_primary": True,
                "assessed_by": "Dr. Angela Park",
                "assessment_date": now - timedelta(days=82),
                "notes": "Clean dataset. No outliers detected.",
                "created_at": now - timedelta(days=82),
            },
            {
                "id": "SA-005",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "BE-012",
                "assessment_name": "BE-012 Site Change ANOVA (Failed)",
                "model_used": "mixed_effects_ANOVA",
                "factors": ["sequence", "period", "treatment", "subject_within_sequence"],
                "sequence_effect_p": 0.44,
                "period_effect_p": 0.52,
                "treatment_effect_p": 0.003,
                "subject_within_sequence_p": 0.0005,
                "residual_variance": 0.0265,
                "outliers_detected": 4,
                "outliers_excluded": 2,
                "sensitivity_analysis_done": True,
                "consistent_with_primary": True,
                "assessed_by": "Dr. Angela Park",
                "assessment_date": now - timedelta(days=153),
                "notes": "Significant treatment effect (p=0.003) confirms manufacturing difference.",
                "created_at": now - timedelta(days=153),
            },
            {
                "id": "SA-006",
                "trial_id": EYLEA_TRIAL,
                "study_id": "BE-003",
                "assessment_name": "BE-003 Multi-Dose ANOVA",
                "model_used": "mixed_effects_ANOVA",
                "factors": ["sequence", "period", "treatment", "subject_within_sequence"],
                "sequence_effect_p": 0.65,
                "period_effect_p": 0.38,
                "treatment_effect_p": 0.72,
                "subject_within_sequence_p": 0.001,
                "residual_variance": 0.0405,
                "outliers_detected": 1,
                "outliers_excluded": 0,
                "sensitivity_analysis_done": True,
                "consistent_with_primary": True,
                "assessed_by": "Dr. James Wright",
                "assessment_date": now - timedelta(days=33),
                "notes": "3-period crossover ANOVA. Period 3 shows slight numeric drift.",
                "created_at": now - timedelta(days=33),
            },
            {
                "id": "SA-007",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "BE-007",
                "assessment_name": "BE-007 Food Effect ANOVA",
                "model_used": "mixed_effects_ANOVA",
                "factors": ["sequence", "period", "treatment"],
                "sequence_effect_p": 0.88,
                "period_effect_p": 0.75,
                "treatment_effect_p": 0.91,
                "subject_within_sequence_p": 0.002,
                "residual_variance": 0.0196,
                "outliers_detected": 0,
                "outliers_excluded": 0,
                "sensitivity_analysis_done": False,
                "consistent_with_primary": True,
                "assessed_by": "Dr. Robert Kim",
                "assessment_date": now - timedelta(days=123),
                "notes": "No food effect detected as expected for SC monoclonal antibody.",
                "created_at": now - timedelta(days=123),
            },
            {
                "id": "SA-008",
                "trial_id": EYLEA_TRIAL,
                "study_id": "BE-001",
                "assessment_name": "BE-001 Sensitivity Without Outliers",
                "model_used": "mixed_effects_ANOVA",
                "factors": ["sequence", "period", "treatment", "subject_within_sequence"],
                "sequence_effect_p": 0.74,
                "period_effect_p": 0.48,
                "treatment_effect_p": 0.70,
                "subject_within_sequence_p": 0.001,
                "residual_variance": 0.0318,
                "outliers_detected": 2,
                "outliers_excluded": 2,
                "sensitivity_analysis_done": True,
                "consistent_with_primary": True,
                "assessed_by": "Dr. Sarah Chen",
                "assessment_date": now - timedelta(days=91),
                "notes": "Sensitivity analysis excluding 2 outliers. Results consistent.",
                "created_at": now - timedelta(days=91),
            },
            {
                "id": "SA-009",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "BE-005",
                "assessment_name": "BE-005 Scaled ABE Preliminary",
                "model_used": "reference_scaled_ABE",
                "factors": ["sequence", "period", "treatment", "subject_within_sequence"],
                "sequence_effect_p": None,
                "period_effect_p": None,
                "treatment_effect_p": None,
                "subject_within_sequence_p": None,
                "residual_variance": None,
                "outliers_detected": 0,
                "outliers_excluded": 0,
                "sensitivity_analysis_done": False,
                "consistent_with_primary": True,
                "assessed_by": "Dr. Maria Lopez",
                "assessment_date": now - timedelta(days=8),
                "notes": "Preliminary assessment framework. Full analysis pending data lock.",
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "SA-010",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "BE-009",
                "assessment_name": "BE-009 SC vs IV Interim Assessment",
                "model_used": "parallel_group_ANOVA",
                "factors": ["treatment", "site", "weight_category"],
                "sequence_effect_p": None,
                "period_effect_p": None,
                "treatment_effect_p": None,
                "subject_within_sequence_p": None,
                "residual_variance": None,
                "outliers_detected": 0,
                "outliers_excluded": 0,
                "sensitivity_analysis_done": False,
                "consistent_with_primary": True,
                "assessed_by": "Dr. Angela Park",
                "assessment_date": now - timedelta(days=3),
                "notes": "Interim assessment setup. Awaiting sufficient enrollment.",
                "created_at": now - timedelta(days=3),
            },
        ]

        for a in assessments_data:
            self._statistical_assessments[a["id"]] = StatisticalAssessment(**a)

        # --- 10 Regulatory Filings ---
        filings_data = [
            {
                "id": "RF-001",
                "trial_id": EYLEA_TRIAL,
                "study_id": "BE-001",
                "filing_type": "ANDA",
                "regulatory_authority": "FDA",
                "submission_date": now - timedelta(days=80),
                "target_date": now - timedelta(days=90),
                "reference_number": "ANDA-2025-0847",
                "status": "submitted",
                "study_report_attached": True,
                "dissolution_data_included": False,
                "bioanalytical_report_included": True,
                "statistical_report_included": True,
                "response_date": None,
                "outcome": None,
                "prepared_by": "Dr. Sarah Chen",
                "reviewer": "Dr. William Torres",
                "notes": "Complete BE package for PFS formulation.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "RF-002",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "BE-004",
                "filing_type": "sBLA",
                "regulatory_authority": "FDA",
                "submission_date": now - timedelta(days=50),
                "target_date": now - timedelta(days=60),
                "reference_number": "sBLA-2025-1234",
                "status": "under_review",
                "study_report_attached": True,
                "dissolution_data_included": False,
                "bioanalytical_report_included": True,
                "statistical_report_included": True,
                "response_date": None,
                "outcome": None,
                "prepared_by": "Dr. Maria Lopez",
                "reviewer": "Dr. David Patel",
                "notes": "Supplemental BLA for autoinjector device switch.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "RF-003",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "BE-008",
                "filing_type": "variation_type_II",
                "regulatory_authority": "EMA",
                "submission_date": now - timedelta(days=70),
                "target_date": now - timedelta(days=75),
                "reference_number": "EMEA/H/C/004844/II/0012",
                "status": "approved",
                "study_report_attached": True,
                "dissolution_data_included": False,
                "bioanalytical_report_included": True,
                "statistical_report_included": True,
                "response_date": now - timedelta(days=20),
                "outcome": "approved",
                "prepared_by": "Dr. Angela Park",
                "reviewer": "Dr. William Torres",
                "notes": "EMA approved infusion rate flexibility.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "RF-004",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "BE-012",
                "filing_type": "CBE-30",
                "regulatory_authority": "FDA",
                "submission_date": now - timedelta(days=140),
                "target_date": now - timedelta(days=145),
                "reference_number": "CBE30-2025-0562",
                "status": "rejected",
                "study_report_attached": True,
                "dissolution_data_included": True,
                "bioanalytical_report_included": True,
                "statistical_report_included": True,
                "response_date": now - timedelta(days=100),
                "outcome": "rejected",
                "prepared_by": "Dr. Angela Park",
                "reviewer": "Dr. William Torres",
                "notes": "Rejected due to failed BE. Manufacturing process revision required.",
                "created_at": now - timedelta(days=145),
            },
            {
                "id": "RF-005",
                "trial_id": EYLEA_TRIAL,
                "study_id": "BE-003",
                "filing_type": "ANDA",
                "regulatory_authority": "FDA",
                "submission_date": None,
                "target_date": now + timedelta(days=30),
                "reference_number": None,
                "status": "draft",
                "study_report_attached": False,
                "dissolution_data_included": False,
                "bioanalytical_report_included": False,
                "statistical_report_included": False,
                "response_date": None,
                "outcome": None,
                "prepared_by": "Dr. James Wright",
                "reviewer": None,
                "notes": "Draft filing for multi-dose vial. Pending final statistical report.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "RF-006",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "BE-005",
                "filing_type": "sBLA",
                "regulatory_authority": "FDA",
                "submission_date": None,
                "target_date": now + timedelta(days=120),
                "reference_number": None,
                "status": "draft",
                "study_report_attached": False,
                "dissolution_data_included": False,
                "bioanalytical_report_included": False,
                "statistical_report_included": False,
                "response_date": None,
                "outcome": None,
                "prepared_by": "Dr. Maria Lopez",
                "reviewer": None,
                "notes": "Preliminary filing shell for high-concentration formulation.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "RF-007",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "BE-004",
                "filing_type": "variation_type_II",
                "regulatory_authority": "EMA",
                "submission_date": now - timedelta(days=40),
                "target_date": now - timedelta(days=45),
                "reference_number": "EMEA/H/C/004310/II/0045",
                "status": "submitted",
                "study_report_attached": True,
                "dissolution_data_included": False,
                "bioanalytical_report_included": True,
                "statistical_report_included": True,
                "response_date": None,
                "outcome": None,
                "prepared_by": "Dr. Maria Lopez",
                "reviewer": "Dr. David Patel",
                "notes": "EMA Type II variation for autoinjector device addition.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "RF-008",
                "trial_id": EYLEA_TRIAL,
                "study_id": "BE-001",
                "filing_type": "CTD_Module_5",
                "regulatory_authority": "PMDA",
                "submission_date": now - timedelta(days=60),
                "target_date": now - timedelta(days=65),
                "reference_number": "PMDA-2025-BE-0192",
                "status": "under_review",
                "study_report_attached": True,
                "dissolution_data_included": True,
                "bioanalytical_report_included": True,
                "statistical_report_included": True,
                "response_date": None,
                "outcome": None,
                "prepared_by": "Dr. Sarah Chen",
                "reviewer": "Dr. James Wright",
                "notes": "Japanese PMDA submission for PFS device approval.",
                "created_at": now - timedelta(days=65),
            },
            {
                "id": "RF-009",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "BE-009",
                "filing_type": "IND_amendment",
                "regulatory_authority": "FDA",
                "submission_date": None,
                "target_date": now + timedelta(days=90),
                "reference_number": None,
                "status": "draft",
                "study_report_attached": False,
                "dissolution_data_included": False,
                "bioanalytical_report_included": False,
                "statistical_report_included": False,
                "response_date": None,
                "outcome": None,
                "prepared_by": "Dr. Angela Park",
                "reviewer": None,
                "notes": "IND amendment for SC formulation pending study completion.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "RF-010",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "BE-007",
                "filing_type": "annual_report",
                "regulatory_authority": "FDA",
                "submission_date": now - timedelta(days=110),
                "target_date": now - timedelta(days=115),
                "reference_number": "AR-2025-DUP-003",
                "status": "approved",
                "study_report_attached": True,
                "dissolution_data_included": False,
                "bioanalytical_report_included": True,
                "statistical_report_included": True,
                "response_date": now - timedelta(days=90),
                "outcome": "approved",
                "prepared_by": "Dr. Robert Kim",
                "reviewer": "Dr. David Patel",
                "notes": "Annual report including food effect BE data. Acknowledged by FDA.",
                "created_at": now - timedelta(days=115),
            },
        ]

        for f in filings_data:
            self._regulatory_filings[f["id"]] = RegulatoryFiling(**f)

    # ------------------------------------------------------------------
    # BE Studies
    # ------------------------------------------------------------------

    def list_be_studies(
        self,
        *,
        trial_id: str | None = None,
        status: StudyStatus | None = None,
        study_design: StudyDesign | None = None,
        overall_result: BEResult | None = None,
    ) -> list[BEStudy]:
        """List BE studies with optional filters."""
        with self._lock:
            result = list(self._be_studies.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if status is not None:
            result = [s for s in result if s.status == status]
        if study_design is not None:
            result = [s for s in result if s.study_design == study_design]
        if overall_result is not None:
            result = [s for s in result if s.overall_result == overall_result]

        return sorted(result, key=lambda s: s.created_at, reverse=True)

    def get_be_study(self, study_id: str) -> BEStudy | None:
        """Get a single BE study by ID."""
        with self._lock:
            return self._be_studies.get(study_id)

    def create_be_study(self, payload: BEStudyCreate) -> BEStudy:
        """Create a new BE study."""
        now = datetime.now(timezone.utc)
        study_id = f"BE-{uuid4().hex[:8].upper()}"
        study = BEStudy(
            id=study_id,
            trial_id=payload.trial_id,
            study_name=payload.study_name,
            study_design=payload.study_design,
            status=StudyStatus.PLANNED,
            reference_product=payload.reference_product,
            test_product=payload.test_product,
            route_of_administration="oral",
            dosage_strength=payload.dosage_strength,
            subjects_planned=payload.subjects_planned,
            subjects_enrolled=0,
            subjects_completed=0,
            washout_period_days=7,
            fasting_fed="fasting",
            be_criterion=BECriterion.STANDARD_80_125,
            overall_result=BEResult.PENDING,
            start_date=None,
            completion_date=None,
            principal_investigator=payload.principal_investigator,
            sponsor=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._be_studies[study_id] = study
        logger.info("Created BE study %s for trial %s", study_id, payload.trial_id)
        return study

    def update_be_study(self, study_id: str, payload: BEStudyUpdate) -> BEStudy | None:
        """Update an existing BE study."""
        with self._lock:
            existing = self._be_studies.get(study_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = BEStudy(**data)
            self._be_studies[study_id] = updated
        return updated

    def delete_be_study(self, study_id: str) -> bool:
        """Delete a BE study. Returns True if deleted."""
        with self._lock:
            if study_id in self._be_studies:
                del self._be_studies[study_id]
                return True
            return False

    # ------------------------------------------------------------------
    # PK Parameters
    # ------------------------------------------------------------------

    def list_pk_parameters(
        self,
        *,
        trial_id: str | None = None,
        study_id: str | None = None,
        parameter_name: PKParameterName | None = None,
    ) -> list[PKParameter]:
        """List PK parameters with optional filters."""
        with self._lock:
            result = list(self._pk_parameters.values())

        if trial_id is not None:
            result = [p for p in result if p.trial_id == trial_id]
        if study_id is not None:
            result = [p for p in result if p.study_id == study_id]
        if parameter_name is not None:
            result = [p for p in result if p.parameter_name == parameter_name]

        return sorted(result, key=lambda p: p.analysis_date, reverse=True)

    def get_pk_parameter(self, pk_id: str) -> PKParameter | None:
        """Get a single PK parameter by ID."""
        with self._lock:
            return self._pk_parameters.get(pk_id)

    def create_pk_parameter(self, payload: PKParameterCreate) -> PKParameter:
        """Create a new PK parameter."""
        now = datetime.now(timezone.utc)
        pk_id = f"PK-{uuid4().hex[:8].upper()}"
        pk = PKParameter(
            id=pk_id,
            trial_id=payload.trial_id,
            study_id=payload.study_id,
            parameter_name=payload.parameter_name,
            formulation=payload.formulation,
            subject_count=payload.subject_count,
            geometric_mean=None,
            arithmetic_mean=None,
            cv_pct=0.0,
            median=None,
            min_value=None,
            max_value=None,
            unit="ng*h/mL",
            ln_transformed=True,
            analyzed_by=payload.analyzed_by,
            analysis_date=now,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._pk_parameters[pk_id] = pk
        logger.info("Created PK parameter %s for trial %s", pk_id, payload.trial_id)
        return pk

    def update_pk_parameter(self, pk_id: str, payload: PKParameterUpdate) -> PKParameter | None:
        """Update an existing PK parameter."""
        with self._lock:
            existing = self._pk_parameters.get(pk_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = PKParameter(**data)
            self._pk_parameters[pk_id] = updated
        return updated

    def delete_pk_parameter(self, pk_id: str) -> bool:
        """Delete a PK parameter. Returns True if deleted."""
        with self._lock:
            if pk_id in self._pk_parameters:
                del self._pk_parameters[pk_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Formulation Comparisons
    # ------------------------------------------------------------------

    def list_formulation_comparisons(
        self,
        *,
        trial_id: str | None = None,
        study_id: str | None = None,
        result: BEResult | None = None,
    ) -> list[FormulationComparison]:
        """List formulation comparisons with optional filters."""
        with self._lock:
            items = list(self._formulation_comparisons.values())

        if trial_id is not None:
            items = [c for c in items if c.trial_id == trial_id]
        if study_id is not None:
            items = [c for c in items if c.study_id == study_id]
        if result is not None:
            items = [c for c in items if c.result == result]

        return sorted(items, key=lambda c: c.analysis_date, reverse=True)

    def get_formulation_comparison(self, comparison_id: str) -> FormulationComparison | None:
        """Get a single formulation comparison by ID."""
        with self._lock:
            return self._formulation_comparisons.get(comparison_id)

    def create_formulation_comparison(
        self, payload: FormulationComparisonCreate
    ) -> FormulationComparison:
        """Create a new formulation comparison."""
        now = datetime.now(timezone.utc)
        fc_id = f"FC-{uuid4().hex[:8].upper()}"
        fc = FormulationComparison(
            id=fc_id,
            trial_id=payload.trial_id,
            study_id=payload.study_id,
            parameter_name=payload.parameter_name,
            test_gmean=None,
            reference_gmean=None,
            ratio_pct=None,
            ci_lower_pct=None,
            ci_upper_pct=None,
            be_criterion=payload.be_criterion,
            within_limits=False,
            result=BEResult.PENDING,
            intra_subject_cv_pct=None,
            power_pct=None,
            method=payload.method,
            analyzed_by=payload.analyzed_by,
            analysis_date=now,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._formulation_comparisons[fc_id] = fc
        logger.info("Created formulation comparison %s for trial %s", fc_id, payload.trial_id)
        return fc

    def update_formulation_comparison(
        self, comparison_id: str, payload: FormulationComparisonUpdate
    ) -> FormulationComparison | None:
        """Update an existing formulation comparison."""
        with self._lock:
            existing = self._formulation_comparisons.get(comparison_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = FormulationComparison(**data)
            self._formulation_comparisons[comparison_id] = updated
        return updated

    def delete_formulation_comparison(self, comparison_id: str) -> bool:
        """Delete a formulation comparison. Returns True if deleted."""
        with self._lock:
            if comparison_id in self._formulation_comparisons:
                del self._formulation_comparisons[comparison_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Statistical Assessments
    # ------------------------------------------------------------------

    def list_statistical_assessments(
        self,
        *,
        trial_id: str | None = None,
        study_id: str | None = None,
    ) -> list[StatisticalAssessment]:
        """List statistical assessments with optional filters."""
        with self._lock:
            result = list(self._statistical_assessments.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if study_id is not None:
            result = [a for a in result if a.study_id == study_id]

        return sorted(result, key=lambda a: a.assessment_date, reverse=True)

    def get_statistical_assessment(self, assessment_id: str) -> StatisticalAssessment | None:
        """Get a single statistical assessment by ID."""
        with self._lock:
            return self._statistical_assessments.get(assessment_id)

    def create_statistical_assessment(
        self, payload: StatisticalAssessmentCreate
    ) -> StatisticalAssessment:
        """Create a new statistical assessment."""
        now = datetime.now(timezone.utc)
        sa_id = f"SA-{uuid4().hex[:8].upper()}"
        sa = StatisticalAssessment(
            id=sa_id,
            trial_id=payload.trial_id,
            study_id=payload.study_id,
            assessment_name=payload.assessment_name,
            model_used=payload.model_used,
            factors=payload.factors,
            sequence_effect_p=None,
            period_effect_p=None,
            treatment_effect_p=None,
            subject_within_sequence_p=None,
            residual_variance=None,
            outliers_detected=0,
            outliers_excluded=0,
            sensitivity_analysis_done=False,
            consistent_with_primary=True,
            assessed_by=payload.assessed_by,
            assessment_date=now,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._statistical_assessments[sa_id] = sa
        logger.info("Created statistical assessment %s for trial %s", sa_id, payload.trial_id)
        return sa

    def update_statistical_assessment(
        self, assessment_id: str, payload: StatisticalAssessmentUpdate
    ) -> StatisticalAssessment | None:
        """Update an existing statistical assessment."""
        with self._lock:
            existing = self._statistical_assessments.get(assessment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = StatisticalAssessment(**data)
            self._statistical_assessments[assessment_id] = updated
        return updated

    def delete_statistical_assessment(self, assessment_id: str) -> bool:
        """Delete a statistical assessment. Returns True if deleted."""
        with self._lock:
            if assessment_id in self._statistical_assessments:
                del self._statistical_assessments[assessment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Regulatory Filings
    # ------------------------------------------------------------------

    def list_regulatory_filings(
        self,
        *,
        trial_id: str | None = None,
        study_id: str | None = None,
        status: str | None = None,
    ) -> list[RegulatoryFiling]:
        """List regulatory filings with optional filters."""
        with self._lock:
            result = list(self._regulatory_filings.values())

        if trial_id is not None:
            result = [f for f in result if f.trial_id == trial_id]
        if study_id is not None:
            result = [f for f in result if f.study_id == study_id]
        if status is not None:
            result = [f for f in result if f.status == status]

        return sorted(result, key=lambda f: f.created_at, reverse=True)

    def get_regulatory_filing(self, filing_id: str) -> RegulatoryFiling | None:
        """Get a single regulatory filing by ID."""
        with self._lock:
            return self._regulatory_filings.get(filing_id)

    def create_regulatory_filing(self, payload: RegulatoryFilingCreate) -> RegulatoryFiling:
        """Create a new regulatory filing."""
        now = datetime.now(timezone.utc)
        rf_id = f"RF-{uuid4().hex[:8].upper()}"
        rf = RegulatoryFiling(
            id=rf_id,
            trial_id=payload.trial_id,
            study_id=payload.study_id,
            filing_type=payload.filing_type,
            regulatory_authority=payload.regulatory_authority,
            submission_date=None,
            target_date=payload.target_date,
            reference_number=None,
            status="draft",
            study_report_attached=False,
            dissolution_data_included=False,
            bioanalytical_report_included=False,
            statistical_report_included=False,
            response_date=None,
            outcome=None,
            prepared_by=payload.prepared_by,
            reviewer=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._regulatory_filings[rf_id] = rf
        logger.info("Created regulatory filing %s for trial %s", rf_id, payload.trial_id)
        return rf

    def update_regulatory_filing(
        self, filing_id: str, payload: RegulatoryFilingUpdate
    ) -> RegulatoryFiling | None:
        """Update an existing regulatory filing."""
        with self._lock:
            existing = self._regulatory_filings.get(filing_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = RegulatoryFiling(**data)
            self._regulatory_filings[filing_id] = updated
        return updated

    def delete_regulatory_filing(self, filing_id: str) -> bool:
        """Delete a regulatory filing. Returns True if deleted."""
        with self._lock:
            if filing_id in self._regulatory_filings:
                del self._regulatory_filings[filing_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> BioequivalenceMetrics:
        """Compute aggregated bioequivalence metrics."""
        with self._lock:
            studies = list(self._be_studies.values())
            pk_params = list(self._pk_parameters.values())
            comparisons = list(self._formulation_comparisons.values())
            assessments = list(self._statistical_assessments.values())
            filings = list(self._regulatory_filings.values())

        # Studies by design
        studies_by_design: dict[str, int] = {}
        for s in studies:
            key = s.study_design.value
            studies_by_design[key] = studies_by_design.get(key, 0) + 1

        # Studies by status
        studies_by_status: dict[str, int] = {}
        for s in studies:
            key = s.status.value
            studies_by_status[key] = studies_by_status.get(key, 0) + 1

        # Studies by result
        studies_by_result: dict[str, int] = {}
        for s in studies:
            key = s.overall_result.value
            studies_by_result[key] = studies_by_result.get(key, 0) + 1

        # Parameters by name
        parameters_by_name: dict[str, int] = {}
        for p in pk_params:
            key = p.parameter_name.value
            parameters_by_name[key] = parameters_by_name.get(key, 0) + 1

        # Comparisons within limits
        comparisons_within_limits = sum(1 for c in comparisons if c.within_limits)

        # Filings by status
        filings_by_status: dict[str, int] = {}
        for f in filings:
            key = f.status
            filings_by_status[key] = filings_by_status.get(key, 0) + 1

        return BioequivalenceMetrics(
            total_studies=len(studies),
            studies_by_design=studies_by_design,
            studies_by_status=studies_by_status,
            studies_by_result=studies_by_result,
            total_pk_parameters=len(pk_params),
            parameters_by_name=parameters_by_name,
            total_comparisons=len(comparisons),
            comparisons_within_limits=comparisons_within_limits,
            total_assessments=len(assessments),
            total_filings=len(filings),
            filings_by_status=filings_by_status,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: BioequivalenceService | None = None
_instance_lock = threading.Lock()


def get_bioequivalence_service() -> BioequivalenceService:
    """Return the singleton BioequivalenceService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = BioequivalenceService()
    return _instance


def reset_bioequivalence_service() -> BioequivalenceService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = BioequivalenceService()
    return _instance
