"""Patient Stratification Service (STRAT-MGT).

Manages patient stratification operations including stratification factor
definitions, balance assessments, covariate analysis, arm assignments,
randomization balance monitoring, and stratification metrics.

Usage:
    from app.services.patient_stratification_service import (
        get_patient_stratification_service,
    )

    svc = get_patient_stratification_service()
    factors = svc.list_stratification_factors()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.patient_stratification import (
    ArmAssignment,
    ArmAssignmentCreate,
    ArmAssignmentUpdate,
    AssignmentMethod,
    BalanceAssessment,
    BalanceAssessmentCreate,
    BalanceAssessmentUpdate,
    BalanceStatus,
    CovariateAnalysis,
    CovariateAnalysisCreate,
    CovariateAnalysisUpdate,
    CovariateStatus,
    PatientStratificationMetrics,
    RandomizationBalance,
    RandomizationBalanceCreate,
    RandomizationBalanceUpdate,
    StratFactorType,
    StratificationFactor,
    StratificationFactorCreate,
    StratificationFactorUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class PatientStratificationService:
    """In-memory Patient Stratification engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._factors: dict[str, StratificationFactor] = {}
        self._assessments: dict[str, BalanceAssessment] = {}
        self._covariates: dict[str, CovariateAnalysis] = {}
        self._assignments: dict[str, ArmAssignment] = {}
        self._balances: dict[str, RandomizationBalance] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic patient stratification data."""
        now = datetime.now(timezone.utc)

        # --- 12 Stratification Factors ---
        factors_data = [
            {
                "id": "SF-001",
                "trial_id": EYLEA_TRIAL,
                "factor_name": "Age Group",
                "factor_type": StratFactorType.DEMOGRAPHIC,
                "levels": ["<50", "50-64", "65-74", ">=75"],
                "is_dynamic": False,
                "weight": 1.0,
                "is_active": True,
                "description": "Age-based stratification for nAMD population",
                "created_by": "Dr. Sarah Chen",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "SF-002",
                "trial_id": EYLEA_TRIAL,
                "factor_name": "Baseline Visual Acuity",
                "factor_type": StratFactorType.DISEASE_SEVERITY,
                "levels": ["<35 letters", "35-55 letters", ">55 letters"],
                "is_dynamic": False,
                "weight": 0.9,
                "is_active": True,
                "description": "ETDRS letter score at baseline",
                "created_by": "Dr. Sarah Chen",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "SF-003",
                "trial_id": EYLEA_TRIAL,
                "factor_name": "Geographic Region",
                "factor_type": StratFactorType.GEOGRAPHIC,
                "levels": ["North America", "Europe", "Asia-Pacific", "Rest of World"],
                "is_dynamic": False,
                "weight": 0.7,
                "is_active": True,
                "description": "Geographic region of enrollment site",
                "created_by": "Dr. Sarah Chen",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "SF-004",
                "trial_id": DUPIXENT_TRIAL,
                "factor_name": "Disease Severity (EASI)",
                "factor_type": StratFactorType.DISEASE_SEVERITY,
                "levels": ["Moderate (16-23)", "Severe (24-50)", "Very Severe (>50)"],
                "is_dynamic": False,
                "weight": 1.0,
                "is_active": True,
                "description": "EASI score at screening for atopic dermatitis",
                "created_by": "Dr. Michael Park",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "SF-005",
                "trial_id": DUPIXENT_TRIAL,
                "factor_name": "Prior Biologic Use",
                "factor_type": StratFactorType.PRIOR_THERAPY,
                "levels": ["Naive", "1 Prior Biologic", "2+ Prior Biologics"],
                "is_dynamic": False,
                "weight": 0.8,
                "is_active": True,
                "description": "Prior biologic therapy exposure",
                "created_by": "Dr. Michael Park",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "SF-006",
                "trial_id": DUPIXENT_TRIAL,
                "factor_name": "IgE Level",
                "factor_type": StratFactorType.BIOMARKER,
                "levels": ["Normal (<100 IU/mL)", "Elevated (100-500)", "High (>500)"],
                "is_dynamic": True,
                "weight": 0.6,
                "is_active": True,
                "description": "Baseline serum IgE level",
                "created_by": "Dr. Michael Park",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "SF-007",
                "trial_id": LIBTAYO_TRIAL,
                "factor_name": "PD-L1 Expression",
                "factor_type": StratFactorType.BIOMARKER,
                "levels": ["<1%", "1-49%", ">=50%"],
                "is_dynamic": False,
                "weight": 1.0,
                "is_active": True,
                "description": "PD-L1 tumor proportion score (TPS)",
                "created_by": "Dr. Lisa Wong",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "SF-008",
                "trial_id": LIBTAYO_TRIAL,
                "factor_name": "ECOG Performance Status",
                "factor_type": StratFactorType.DISEASE_SEVERITY,
                "levels": ["0", "1"],
                "is_dynamic": False,
                "weight": 0.9,
                "is_active": True,
                "description": "ECOG performance status at screening",
                "created_by": "Dr. Lisa Wong",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "SF-009",
                "trial_id": LIBTAYO_TRIAL,
                "factor_name": "Histology",
                "factor_type": StratFactorType.DISEASE_SEVERITY,
                "levels": ["Squamous", "Non-squamous"],
                "is_dynamic": False,
                "weight": 0.8,
                "is_active": True,
                "description": "Tumor histology subtype",
                "created_by": "Dr. Lisa Wong",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "SF-010",
                "trial_id": LIBTAYO_TRIAL,
                "factor_name": "Prior Chemotherapy Lines",
                "factor_type": StratFactorType.PRIOR_THERAPY,
                "levels": ["0 (First-line)", "1", "2+"],
                "is_dynamic": False,
                "weight": 0.7,
                "is_active": True,
                "description": "Number of prior chemotherapy lines",
                "created_by": "Dr. Lisa Wong",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "SF-011",
                "trial_id": EYLEA_TRIAL,
                "factor_name": "Diabetes Status",
                "factor_type": StratFactorType.COMORBIDITY,
                "levels": ["No Diabetes", "Type 2 Diabetes"],
                "is_dynamic": False,
                "weight": 0.5,
                "is_active": False,
                "description": "Presence of diabetes mellitus (retired factor)",
                "created_by": "Dr. Sarah Chen",
                "created_at": now - timedelta(days=160),
            },
            {
                "id": "SF-012",
                "trial_id": DUPIXENT_TRIAL,
                "factor_name": "Body Weight Category",
                "factor_type": StratFactorType.DEMOGRAPHIC,
                "levels": ["<60 kg", "60-100 kg", ">100 kg"],
                "is_dynamic": False,
                "weight": 0.4,
                "is_active": True,
                "description": "Body weight category for dose stratification",
                "created_by": "Dr. Michael Park",
                "created_at": now - timedelta(days=140),
            },
        ]

        for f in factors_data:
            self._factors[f["id"]] = StratificationFactor(**f)

        # --- 10 Balance Assessments ---
        assessments_data = [
            {
                "id": "BA-001",
                "trial_id": EYLEA_TRIAL,
                "assessment_date": now - timedelta(days=60),
                "factor_id": "SF-001",
                "factor_name": "Age Group",
                "arm_counts": {"Eylea HD": 32, "Eylea 2mg": 30, "Sham": 31},
                "total_randomized": 93,
                "imbalance_ratio": 0.03,
                "balance_status": BalanceStatus.BALANCED,
                "chi_square_statistic": 0.12,
                "p_value": 0.94,
                "assessed_by": "IWRS System",
                "notes": "Excellent balance across age groups",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "BA-002",
                "trial_id": EYLEA_TRIAL,
                "assessment_date": now - timedelta(days=30),
                "factor_id": "SF-002",
                "factor_name": "Baseline Visual Acuity",
                "arm_counts": {"Eylea HD": 33, "Eylea 2mg": 31, "Sham": 29},
                "total_randomized": 93,
                "imbalance_ratio": 0.06,
                "balance_status": BalanceStatus.BALANCED,
                "chi_square_statistic": 0.38,
                "p_value": 0.83,
                "assessed_by": "IWRS System",
                "notes": None,
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "BA-003",
                "trial_id": EYLEA_TRIAL,
                "assessment_date": now - timedelta(days=15),
                "factor_id": "SF-003",
                "factor_name": "Geographic Region",
                "arm_counts": {"Eylea HD": 35, "Eylea 2mg": 28, "Sham": 30},
                "total_randomized": 93,
                "imbalance_ratio": 0.11,
                "balance_status": BalanceStatus.SLIGHTLY_IMBALANCED,
                "chi_square_statistic": 1.05,
                "p_value": 0.59,
                "assessed_by": "IWRS System",
                "notes": "Slight regional imbalance; monitoring",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "BA-004",
                "trial_id": DUPIXENT_TRIAL,
                "assessment_date": now - timedelta(days=45),
                "factor_id": "SF-004",
                "factor_name": "Disease Severity (EASI)",
                "arm_counts": {"Dupixent 300mg Q2W": 48, "Dupixent 300mg QW": 45, "Placebo": 47},
                "total_randomized": 140,
                "imbalance_ratio": 0.04,
                "balance_status": BalanceStatus.BALANCED,
                "chi_square_statistic": 0.19,
                "p_value": 0.91,
                "assessed_by": "IRT System",
                "notes": None,
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "BA-005",
                "trial_id": DUPIXENT_TRIAL,
                "assessment_date": now - timedelta(days=20),
                "factor_id": "SF-005",
                "factor_name": "Prior Biologic Use",
                "arm_counts": {"Dupixent 300mg Q2W": 50, "Dupixent 300mg QW": 42, "Placebo": 48},
                "total_randomized": 140,
                "imbalance_ratio": 0.09,
                "balance_status": BalanceStatus.SLIGHTLY_IMBALANCED,
                "chi_square_statistic": 1.26,
                "p_value": 0.53,
                "assessed_by": "IRT System",
                "notes": "Minor imbalance in prior biologic subgroup",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "BA-006",
                "trial_id": DUPIXENT_TRIAL,
                "assessment_date": now - timedelta(days=10),
                "factor_id": "SF-006",
                "factor_name": "IgE Level",
                "arm_counts": {"Dupixent 300mg Q2W": 52, "Dupixent 300mg QW": 40, "Placebo": 48},
                "total_randomized": 140,
                "imbalance_ratio": 0.14,
                "balance_status": BalanceStatus.IMBALANCED,
                "chi_square_statistic": 2.74,
                "p_value": 0.25,
                "assessed_by": "IRT System",
                "notes": "IgE-high subgroup skewed to active arm; adaptive adjustment recommended",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "BA-007",
                "trial_id": LIBTAYO_TRIAL,
                "assessment_date": now - timedelta(days=40),
                "factor_id": "SF-007",
                "factor_name": "PD-L1 Expression",
                "arm_counts": {"Libtayo": 55, "Chemotherapy": 53},
                "total_randomized": 108,
                "imbalance_ratio": 0.02,
                "balance_status": BalanceStatus.BALANCED,
                "chi_square_statistic": 0.07,
                "p_value": 0.79,
                "assessed_by": "IWRS System",
                "notes": None,
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "BA-008",
                "trial_id": LIBTAYO_TRIAL,
                "assessment_date": now - timedelta(days=25),
                "factor_id": "SF-008",
                "factor_name": "ECOG Performance Status",
                "arm_counts": {"Libtayo": 56, "Chemotherapy": 52},
                "total_randomized": 108,
                "imbalance_ratio": 0.05,
                "balance_status": BalanceStatus.BALANCED,
                "chi_square_statistic": 0.30,
                "p_value": 0.58,
                "assessed_by": "IWRS System",
                "notes": None,
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "BA-009",
                "trial_id": LIBTAYO_TRIAL,
                "assessment_date": now - timedelta(days=5),
                "factor_id": "SF-009",
                "factor_name": "Histology",
                "arm_counts": {"Libtayo": 60, "Chemotherapy": 50},
                "total_randomized": 110,
                "imbalance_ratio": 0.18,
                "balance_status": BalanceStatus.IMBALANCED,
                "chi_square_statistic": 3.64,
                "p_value": 0.06,
                "assessed_by": "IWRS System",
                "notes": "Non-squamous patients over-represented in Libtayo arm",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "BA-010",
                "trial_id": LIBTAYO_TRIAL,
                "assessment_date": now - timedelta(days=2),
                "factor_id": "SF-010",
                "factor_name": "Prior Chemotherapy Lines",
                "arm_counts": {"Libtayo": 62, "Chemotherapy": 48},
                "total_randomized": 110,
                "imbalance_ratio": 0.25,
                "balance_status": BalanceStatus.CRITICAL,
                "chi_square_statistic": 5.82,
                "p_value": 0.02,
                "assessed_by": "IWRS System",
                "notes": "Critical imbalance in first-line patients; escalation to DSMB",
                "created_at": now - timedelta(days=2),
            },
        ]

        for a in assessments_data:
            self._assessments[a["id"]] = BalanceAssessment(**a)

        # --- 10 Covariate Analyses ---
        covariates_data = [
            {
                "id": "COV-001",
                "trial_id": EYLEA_TRIAL,
                "covariate_name": "Central Retinal Thickness",
                "covariate_type": "continuous",
                "status": CovariateStatus.VALIDATED,
                "sample_size": 93,
                "mean_value": 412.5,
                "std_deviation": 98.3,
                "missing_count": 2,
                "missing_pct": 2.2,
                "distribution_type": "normal",
                "correlation_with_outcome": 0.68,
                "analyst": "Dr. Emily Foster",
                "analysis_date": now - timedelta(days=30),
                "notes": "Strong correlation with VA outcome; recommend as stratification factor",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "COV-002",
                "trial_id": EYLEA_TRIAL,
                "covariate_name": "Choroidal Neovascularization Type",
                "covariate_type": "categorical",
                "status": CovariateStatus.COMPLETE,
                "sample_size": 93,
                "mean_value": None,
                "std_deviation": None,
                "missing_count": 0,
                "missing_pct": 0.0,
                "distribution_type": "categorical",
                "correlation_with_outcome": 0.42,
                "analyst": "Dr. Emily Foster",
                "analysis_date": now - timedelta(days=28),
                "notes": "Moderate correlation with outcome; consider for subgroup analysis",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "COV-003",
                "trial_id": DUPIXENT_TRIAL,
                "covariate_name": "Baseline IGA Score",
                "covariate_type": "ordinal",
                "status": CovariateStatus.VALIDATED,
                "sample_size": 140,
                "mean_value": 3.6,
                "std_deviation": 0.7,
                "missing_count": 1,
                "missing_pct": 0.7,
                "distribution_type": "ordinal",
                "correlation_with_outcome": 0.55,
                "analyst": "Dr. James Lee",
                "analysis_date": now - timedelta(days=25),
                "notes": "Good correlation; already captured via EASI factor",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "COV-004",
                "trial_id": DUPIXENT_TRIAL,
                "covariate_name": "Serum Thymus and Activation-Regulated Chemokine",
                "covariate_type": "continuous",
                "status": CovariateStatus.COLLECTING,
                "sample_size": 85,
                "mean_value": 1250.0,
                "std_deviation": 620.0,
                "missing_count": 12,
                "missing_pct": 14.1,
                "distribution_type": "log-normal",
                "correlation_with_outcome": 0.38,
                "analyst": "Dr. James Lee",
                "analysis_date": now - timedelta(days=18),
                "notes": "Data collection ongoing; high missing rate needs resolution",
                "created_at": now - timedelta(days=18),
            },
            {
                "id": "COV-005",
                "trial_id": DUPIXENT_TRIAL,
                "covariate_name": "Body Surface Area Affected",
                "covariate_type": "continuous",
                "status": CovariateStatus.VALIDATED,
                "sample_size": 140,
                "mean_value": 45.2,
                "std_deviation": 22.1,
                "missing_count": 3,
                "missing_pct": 2.1,
                "distribution_type": "normal",
                "correlation_with_outcome": 0.61,
                "analyst": "Dr. James Lee",
                "analysis_date": now - timedelta(days=22),
                "notes": "Strong predictor of treatment response",
                "created_at": now - timedelta(days=22),
            },
            {
                "id": "COV-006",
                "trial_id": LIBTAYO_TRIAL,
                "covariate_name": "Tumor Mutational Burden",
                "covariate_type": "continuous",
                "status": CovariateStatus.COMPLETE,
                "sample_size": 108,
                "mean_value": 12.4,
                "std_deviation": 8.7,
                "missing_count": 5,
                "missing_pct": 4.6,
                "distribution_type": "right-skewed",
                "correlation_with_outcome": 0.52,
                "analyst": "Dr. Ana Rodriguez",
                "analysis_date": now - timedelta(days=20),
                "notes": "Moderate correlation; potential predictive biomarker",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "COV-007",
                "trial_id": LIBTAYO_TRIAL,
                "covariate_name": "Liver Metastasis Status",
                "covariate_type": "binary",
                "status": CovariateStatus.VALIDATED,
                "sample_size": 110,
                "mean_value": 0.28,
                "std_deviation": None,
                "missing_count": 0,
                "missing_pct": 0.0,
                "distribution_type": "bernoulli",
                "correlation_with_outcome": -0.35,
                "analyst": "Dr. Ana Rodriguez",
                "analysis_date": now - timedelta(days=15),
                "notes": "Negative correlation; liver mets predict worse outcome",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "COV-008",
                "trial_id": LIBTAYO_TRIAL,
                "covariate_name": "Neutrophil-to-Lymphocyte Ratio",
                "covariate_type": "continuous",
                "status": CovariateStatus.PLANNED,
                "sample_size": 0,
                "mean_value": None,
                "std_deviation": None,
                "missing_count": 0,
                "missing_pct": 0.0,
                "distribution_type": None,
                "correlation_with_outcome": None,
                "analyst": "Dr. Ana Rodriguez",
                "analysis_date": now - timedelta(days=10),
                "notes": "Analysis planned for next interim review",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "COV-009",
                "trial_id": EYLEA_TRIAL,
                "covariate_name": "Intraocular Pressure",
                "covariate_type": "continuous",
                "status": CovariateStatus.LOCKED,
                "sample_size": 93,
                "mean_value": 15.8,
                "std_deviation": 3.2,
                "missing_count": 1,
                "missing_pct": 1.1,
                "distribution_type": "normal",
                "correlation_with_outcome": 0.12,
                "analyst": "Dr. Emily Foster",
                "analysis_date": now - timedelta(days=35),
                "notes": "Weak correlation; not recommended for stratification",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "COV-010",
                "trial_id": DUPIXENT_TRIAL,
                "covariate_name": "Age at Onset",
                "covariate_type": "continuous",
                "status": CovariateStatus.COMPLETE,
                "sample_size": 140,
                "mean_value": 18.5,
                "std_deviation": 12.8,
                "missing_count": 4,
                "missing_pct": 2.9,
                "distribution_type": "right-skewed",
                "correlation_with_outcome": 0.22,
                "analyst": "Dr. James Lee",
                "analysis_date": now - timedelta(days=12),
                "notes": "Weak-moderate correlation; early onset may predict different response",
                "created_at": now - timedelta(days=12),
            },
        ]

        for c in covariates_data:
            self._covariates[c["id"]] = CovariateAnalysis(**c)

        # --- 15 Arm Assignments ---
        assignments_data = [
            {
                "id": "AA-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "subject_id": "SUBJ-E001",
                "arm_name": "Eylea HD",
                "assignment_method": AssignmentMethod.PERMUTED_BLOCK,
                "assignment_date": now - timedelta(days=150),
                "stratification_values": {"Age Group": "65-74", "Baseline Visual Acuity": "35-55 letters", "Geographic Region": "North America"},
                "stratum_id": "STR-E-001",
                "block_id": "BLK-001",
                "sequence_number": 1,
                "is_confirmed": True,
                "confirmed_by": "IWRS Auto",
                "confirmed_date": now - timedelta(days=150),
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "AA-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "subject_id": "SUBJ-E002",
                "arm_name": "Eylea 2mg",
                "assignment_method": AssignmentMethod.PERMUTED_BLOCK,
                "assignment_date": now - timedelta(days=145),
                "stratification_values": {"Age Group": ">=75", "Baseline Visual Acuity": "<35 letters", "Geographic Region": "North America"},
                "stratum_id": "STR-E-002",
                "block_id": "BLK-001",
                "sequence_number": 2,
                "is_confirmed": True,
                "confirmed_by": "IWRS Auto",
                "confirmed_date": now - timedelta(days=145),
                "created_at": now - timedelta(days=145),
            },
            {
                "id": "AA-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "subject_id": "SUBJ-E003",
                "arm_name": "Sham",
                "assignment_method": AssignmentMethod.PERMUTED_BLOCK,
                "assignment_date": now - timedelta(days=140),
                "stratification_values": {"Age Group": "50-64", "Baseline Visual Acuity": ">55 letters", "Geographic Region": "Europe"},
                "stratum_id": "STR-E-003",
                "block_id": "BLK-002",
                "sequence_number": 3,
                "is_confirmed": True,
                "confirmed_by": "IWRS Auto",
                "confirmed_date": now - timedelta(days=140),
                "created_at": now - timedelta(days=140),
            },
            {
                "id": "AA-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "subject_id": "SUBJ-D001",
                "arm_name": "Dupixent 300mg Q2W",
                "assignment_method": AssignmentMethod.MINIMIZATION,
                "assignment_date": now - timedelta(days=120),
                "stratification_values": {"Disease Severity (EASI)": "Severe (24-50)", "Prior Biologic Use": "Naive"},
                "stratum_id": None,
                "block_id": None,
                "sequence_number": 1,
                "is_confirmed": True,
                "confirmed_by": "IRT Auto",
                "confirmed_date": now - timedelta(days=120),
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "AA-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "subject_id": "SUBJ-D002",
                "arm_name": "Placebo",
                "assignment_method": AssignmentMethod.MINIMIZATION,
                "assignment_date": now - timedelta(days=115),
                "stratification_values": {"Disease Severity (EASI)": "Moderate (16-23)", "Prior Biologic Use": "1 Prior Biologic"},
                "stratum_id": None,
                "block_id": None,
                "sequence_number": 2,
                "is_confirmed": True,
                "confirmed_by": "IRT Auto",
                "confirmed_date": now - timedelta(days=115),
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "AA-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "subject_id": "SUBJ-D003",
                "arm_name": "Dupixent 300mg QW",
                "assignment_method": AssignmentMethod.MINIMIZATION,
                "assignment_date": now - timedelta(days=110),
                "stratification_values": {"Disease Severity (EASI)": "Very Severe (>50)", "Prior Biologic Use": "2+ Prior Biologics"},
                "stratum_id": None,
                "block_id": None,
                "sequence_number": 3,
                "is_confirmed": True,
                "confirmed_by": "IRT Auto",
                "confirmed_date": now - timedelta(days=110),
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "AA-007",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "subject_id": "SUBJ-L001",
                "arm_name": "Libtayo",
                "assignment_method": AssignmentMethod.PERMUTED_BLOCK,
                "assignment_date": now - timedelta(days=100),
                "stratification_values": {"PD-L1 Expression": ">=50%", "ECOG Performance Status": "0", "Histology": "Non-squamous"},
                "stratum_id": "STR-L-001",
                "block_id": "BLK-L-001",
                "sequence_number": 1,
                "is_confirmed": True,
                "confirmed_by": "IWRS Auto",
                "confirmed_date": now - timedelta(days=100),
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "AA-008",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "subject_id": "SUBJ-L002",
                "arm_name": "Chemotherapy",
                "assignment_method": AssignmentMethod.PERMUTED_BLOCK,
                "assignment_date": now - timedelta(days=95),
                "stratification_values": {"PD-L1 Expression": "1-49%", "ECOG Performance Status": "1", "Histology": "Squamous"},
                "stratum_id": "STR-L-002",
                "block_id": "BLK-L-001",
                "sequence_number": 2,
                "is_confirmed": True,
                "confirmed_by": "IWRS Auto",
                "confirmed_date": now - timedelta(days=95),
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "AA-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "subject_id": "SUBJ-L003",
                "arm_name": "Libtayo",
                "assignment_method": AssignmentMethod.BIASED_COIN,
                "assignment_date": now - timedelta(days=90),
                "stratification_values": {"PD-L1 Expression": "<1%", "ECOG Performance Status": "0", "Histology": "Squamous"},
                "stratum_id": "STR-L-003",
                "block_id": None,
                "sequence_number": 3,
                "is_confirmed": True,
                "confirmed_by": "IWRS Auto",
                "confirmed_date": now - timedelta(days=90),
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "AA-010",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "subject_id": "SUBJ-E004",
                "arm_name": "Eylea HD",
                "assignment_method": AssignmentMethod.PERMUTED_BLOCK,
                "assignment_date": now - timedelta(days=80),
                "stratification_values": {"Age Group": "<50", "Baseline Visual Acuity": "35-55 letters", "Geographic Region": "Asia-Pacific"},
                "stratum_id": "STR-E-004",
                "block_id": "BLK-003",
                "sequence_number": 4,
                "is_confirmed": True,
                "confirmed_by": "IWRS Auto",
                "confirmed_date": now - timedelta(days=80),
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "AA-011",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "subject_id": "SUBJ-D004",
                "arm_name": "Dupixent 300mg Q2W",
                "assignment_method": AssignmentMethod.MINIMIZATION,
                "assignment_date": now - timedelta(days=70),
                "stratification_values": {"Disease Severity (EASI)": "Severe (24-50)", "Prior Biologic Use": "Naive", "IgE Level": "High (>500)"},
                "stratum_id": None,
                "block_id": None,
                "sequence_number": 4,
                "is_confirmed": True,
                "confirmed_by": "IRT Auto",
                "confirmed_date": now - timedelta(days=70),
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "AA-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "subject_id": "SUBJ-L004",
                "arm_name": "Chemotherapy",
                "assignment_method": AssignmentMethod.PERMUTED_BLOCK,
                "assignment_date": now - timedelta(days=60),
                "stratification_values": {"PD-L1 Expression": ">=50%", "ECOG Performance Status": "1"},
                "stratum_id": "STR-L-004",
                "block_id": "BLK-L-002",
                "sequence_number": 4,
                "is_confirmed": True,
                "confirmed_by": "IWRS Auto",
                "confirmed_date": now - timedelta(days=60),
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "AA-013",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-108",
                "subject_id": "SUBJ-E005",
                "arm_name": "Eylea 2mg",
                "assignment_method": AssignmentMethod.URN,
                "assignment_date": now - timedelta(days=45),
                "stratification_values": {"Age Group": "65-74", "Baseline Visual Acuity": ">55 letters"},
                "stratum_id": "STR-E-005",
                "block_id": None,
                "sequence_number": 5,
                "is_confirmed": True,
                "confirmed_by": "IWRS Auto",
                "confirmed_date": now - timedelta(days=45),
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "AA-014",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "subject_id": "SUBJ-D005",
                "arm_name": "Dupixent 300mg QW",
                "assignment_method": AssignmentMethod.SIMPLE,
                "assignment_date": now - timedelta(days=30),
                "stratification_values": {"Disease Severity (EASI)": "Moderate (16-23)"},
                "stratum_id": None,
                "block_id": None,
                "sequence_number": 5,
                "is_confirmed": False,
                "confirmed_by": None,
                "confirmed_date": None,
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "AA-015",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "subject_id": "SUBJ-L005",
                "arm_name": "Libtayo",
                "assignment_method": AssignmentMethod.PERMUTED_BLOCK,
                "assignment_date": now - timedelta(days=15),
                "stratification_values": {"PD-L1 Expression": "1-49%", "Histology": "Non-squamous"},
                "stratum_id": "STR-L-005",
                "block_id": "BLK-L-003",
                "sequence_number": 5,
                "is_confirmed": False,
                "confirmed_by": None,
                "confirmed_date": None,
                "created_at": now - timedelta(days=15),
            },
        ]

        for aa in assignments_data:
            self._assignments[aa["id"]] = ArmAssignment(**aa)

        # --- 10 Randomization Balance Reports ---
        balances_data = [
            {
                "id": "RB-001",
                "trial_id": EYLEA_TRIAL,
                "snapshot_date": now - timedelta(days=120),
                "total_randomized": 45,
                "arm_distribution": {"Eylea HD": 16, "Eylea 2mg": 14, "Sham": 15},
                "target_ratio": "1:1:1",
                "actual_ratio": "1.07:0.93:1.00",
                "overall_balance_status": BalanceStatus.BALANCED,
                "strata_balance": [{"stratum": "Age >=75 / NA", "status": "balanced"}],
                "sites_with_imbalance": 0,
                "recommendation": "No action needed; balance within acceptable range",
                "generated_by": "IWRS System",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "RB-002",
                "trial_id": EYLEA_TRIAL,
                "snapshot_date": now - timedelta(days=60),
                "total_randomized": 75,
                "arm_distribution": {"Eylea HD": 27, "Eylea 2mg": 24, "Sham": 24},
                "target_ratio": "1:1:1",
                "actual_ratio": "1.08:0.96:0.96",
                "overall_balance_status": BalanceStatus.BALANCED,
                "strata_balance": [
                    {"stratum": "Age >=75 / NA", "status": "balanced"},
                    {"stratum": "Age <50 / APAC", "status": "slightly_imbalanced"},
                ],
                "sites_with_imbalance": 1,
                "recommendation": "Monitor Asia-Pacific enrollment; consider adjusted allocation",
                "generated_by": "IWRS System",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "RB-003",
                "trial_id": EYLEA_TRIAL,
                "snapshot_date": now - timedelta(days=7),
                "total_randomized": 93,
                "arm_distribution": {"Eylea HD": 33, "Eylea 2mg": 30, "Sham": 30},
                "target_ratio": "1:1:1",
                "actual_ratio": "1.06:0.97:0.97",
                "overall_balance_status": BalanceStatus.BALANCED,
                "strata_balance": [],
                "sites_with_imbalance": 1,
                "recommendation": None,
                "generated_by": "IWRS System",
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "RB-004",
                "trial_id": DUPIXENT_TRIAL,
                "snapshot_date": now - timedelta(days=90),
                "total_randomized": 80,
                "arm_distribution": {"Dupixent 300mg Q2W": 28, "Dupixent 300mg QW": 26, "Placebo": 26},
                "target_ratio": "1:1:1",
                "actual_ratio": "1.05:0.97:0.97",
                "overall_balance_status": BalanceStatus.BALANCED,
                "strata_balance": [],
                "sites_with_imbalance": 0,
                "recommendation": None,
                "generated_by": "IRT System",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "RB-005",
                "trial_id": DUPIXENT_TRIAL,
                "snapshot_date": now - timedelta(days=30),
                "total_randomized": 120,
                "arm_distribution": {"Dupixent 300mg Q2W": 44, "Dupixent 300mg QW": 38, "Placebo": 38},
                "target_ratio": "1:1:1",
                "actual_ratio": "1.10:0.95:0.95",
                "overall_balance_status": BalanceStatus.SLIGHTLY_IMBALANCED,
                "strata_balance": [{"stratum": "Severe / IgE High", "status": "imbalanced"}],
                "sites_with_imbalance": 2,
                "recommendation": "Adjust IgE-high minimization probability to rebalance",
                "generated_by": "IRT System",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "RB-006",
                "trial_id": DUPIXENT_TRIAL,
                "snapshot_date": now - timedelta(days=5),
                "total_randomized": 140,
                "arm_distribution": {"Dupixent 300mg Q2W": 52, "Dupixent 300mg QW": 42, "Placebo": 46},
                "target_ratio": "1:1:1",
                "actual_ratio": "1.11:0.90:0.98",
                "overall_balance_status": BalanceStatus.IMBALANCED,
                "strata_balance": [
                    {"stratum": "Severe / IgE High", "status": "imbalanced"},
                    {"stratum": "Moderate / Naive", "status": "slightly_imbalanced"},
                ],
                "sites_with_imbalance": 3,
                "recommendation": "Implement adaptive allocation for QW arm; trigger DSMB review",
                "generated_by": "IRT System",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "RB-007",
                "trial_id": LIBTAYO_TRIAL,
                "snapshot_date": now - timedelta(days=80),
                "total_randomized": 60,
                "arm_distribution": {"Libtayo": 31, "Chemotherapy": 29},
                "target_ratio": "1:1",
                "actual_ratio": "1.03:0.97",
                "overall_balance_status": BalanceStatus.BALANCED,
                "strata_balance": [],
                "sites_with_imbalance": 0,
                "recommendation": None,
                "generated_by": "IWRS System",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "RB-008",
                "trial_id": LIBTAYO_TRIAL,
                "snapshot_date": now - timedelta(days=40),
                "total_randomized": 85,
                "arm_distribution": {"Libtayo": 44, "Chemotherapy": 41},
                "target_ratio": "1:1",
                "actual_ratio": "1.04:0.96",
                "overall_balance_status": BalanceStatus.BALANCED,
                "strata_balance": [],
                "sites_with_imbalance": 0,
                "recommendation": None,
                "generated_by": "IWRS System",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "RB-009",
                "trial_id": LIBTAYO_TRIAL,
                "snapshot_date": now - timedelta(days=10),
                "total_randomized": 108,
                "arm_distribution": {"Libtayo": 58, "Chemotherapy": 50},
                "target_ratio": "1:1",
                "actual_ratio": "1.07:0.93",
                "overall_balance_status": BalanceStatus.SLIGHTLY_IMBALANCED,
                "strata_balance": [{"stratum": "PD-L1 <1% / Non-squamous", "status": "imbalanced"}],
                "sites_with_imbalance": 2,
                "recommendation": "Monitor histology imbalance; may need block size reduction",
                "generated_by": "IWRS System",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "RB-010",
                "trial_id": LIBTAYO_TRIAL,
                "snapshot_date": now - timedelta(days=2),
                "total_randomized": 110,
                "arm_distribution": {"Libtayo": 62, "Chemotherapy": 48},
                "target_ratio": "1:1",
                "actual_ratio": "1.13:0.87",
                "overall_balance_status": BalanceStatus.CRITICAL,
                "strata_balance": [
                    {"stratum": "PD-L1 <1% / Non-squamous", "status": "critical"},
                    {"stratum": "First-line / ECOG 1", "status": "imbalanced"},
                ],
                "sites_with_imbalance": 4,
                "recommendation": "Urgent: Halt randomization for first-line stratum; DSMB emergency review",
                "generated_by": "IWRS System",
                "created_at": now - timedelta(days=2),
            },
        ]

        for b in balances_data:
            self._balances[b["id"]] = RandomizationBalance(**b)

    # ------------------------------------------------------------------
    # Stratification Factors
    # ------------------------------------------------------------------

    def list_stratification_factors(
        self,
        *,
        trial_id: str | None = None,
        factor_type: StratFactorType | None = None,
        is_active: bool | None = None,
    ) -> list[StratificationFactor]:
        """List stratification factors with optional filters."""
        with self._lock:
            result = list(self._factors.values())

        if trial_id is not None:
            result = [f for f in result if f.trial_id == trial_id]
        if factor_type is not None:
            result = [f for f in result if f.factor_type == factor_type]
        if is_active is not None:
            result = [f for f in result if f.is_active == is_active]

        return sorted(result, key=lambda f: f.id)

    def get_stratification_factor(self, factor_id: str) -> StratificationFactor | None:
        """Get a single stratification factor by ID."""
        with self._lock:
            return self._factors.get(factor_id)

    def create_stratification_factor(self, payload: StratificationFactorCreate) -> StratificationFactor:
        """Create a new stratification factor."""
        now = datetime.now(timezone.utc)
        factor_id = f"SF-{uuid4().hex[:8].upper()}"
        factor = StratificationFactor(
            id=factor_id,
            created_at=now,
            is_active=True,
            **payload.model_dump(),
        )
        with self._lock:
            self._factors[factor_id] = factor
        logger.info("Created stratification factor %s: %s", factor_id, payload.factor_name)
        return factor

    def update_stratification_factor(
        self, factor_id: str, payload: StratificationFactorUpdate
    ) -> StratificationFactor | None:
        """Update an existing stratification factor."""
        with self._lock:
            existing = self._factors.get(factor_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = StratificationFactor(**data)
            self._factors[factor_id] = updated
        return updated

    def delete_stratification_factor(self, factor_id: str) -> bool:
        """Delete a stratification factor. Returns True if deleted, False if not found."""
        with self._lock:
            if factor_id in self._factors:
                del self._factors[factor_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Balance Assessments
    # ------------------------------------------------------------------

    def list_balance_assessments(
        self,
        *,
        trial_id: str | None = None,
        factor_id: str | None = None,
        balance_status: BalanceStatus | None = None,
    ) -> list[BalanceAssessment]:
        """List balance assessments with optional filters."""
        with self._lock:
            result = list(self._assessments.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if factor_id is not None:
            result = [a for a in result if a.factor_id == factor_id]
        if balance_status is not None:
            result = [a for a in result if a.balance_status == balance_status]

        return sorted(result, key=lambda a: a.assessment_date, reverse=True)

    def get_balance_assessment(self, assessment_id: str) -> BalanceAssessment | None:
        """Get a single balance assessment by ID."""
        with self._lock:
            return self._assessments.get(assessment_id)

    def create_balance_assessment(self, payload: BalanceAssessmentCreate) -> BalanceAssessment:
        """Create a new balance assessment."""
        now = datetime.now(timezone.utc)
        assessment_id = f"BA-{uuid4().hex[:8].upper()}"

        # Calculate imbalance ratio and status
        arm_counts = payload.arm_counts
        total = sum(arm_counts.values()) if arm_counts else 0
        imbalance_ratio = 0.0
        balance_status = BalanceStatus.BALANCED

        if total > 0 and len(arm_counts) > 1:
            expected = total / len(arm_counts)
            max_dev = max(abs(v - expected) for v in arm_counts.values())
            imbalance_ratio = round(max_dev / expected, 4) if expected > 0 else 0.0

            if imbalance_ratio >= 0.20:
                balance_status = BalanceStatus.CRITICAL
            elif imbalance_ratio >= 0.12:
                balance_status = BalanceStatus.IMBALANCED
            elif imbalance_ratio >= 0.08:
                balance_status = BalanceStatus.SLIGHTLY_IMBALANCED

        assessment = BalanceAssessment(
            id=assessment_id,
            trial_id=payload.trial_id,
            assessment_date=now,
            factor_id=payload.factor_id,
            factor_name=payload.factor_name,
            arm_counts=payload.arm_counts,
            total_randomized=total,
            imbalance_ratio=imbalance_ratio,
            balance_status=balance_status,
            chi_square_statistic=None,
            p_value=None,
            assessed_by=payload.assessed_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._assessments[assessment_id] = assessment
        logger.info("Created balance assessment %s for factor %s", assessment_id, payload.factor_id)
        return assessment

    def update_balance_assessment(
        self, assessment_id: str, payload: BalanceAssessmentUpdate
    ) -> BalanceAssessment | None:
        """Update an existing balance assessment."""
        with self._lock:
            existing = self._assessments.get(assessment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = BalanceAssessment(**data)
            self._assessments[assessment_id] = updated
        return updated

    def delete_balance_assessment(self, assessment_id: str) -> bool:
        """Delete a balance assessment. Returns True if deleted."""
        with self._lock:
            if assessment_id in self._assessments:
                del self._assessments[assessment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Covariate Analyses
    # ------------------------------------------------------------------

    def list_covariate_analyses(
        self,
        *,
        trial_id: str | None = None,
        status: CovariateStatus | None = None,
    ) -> list[CovariateAnalysis]:
        """List covariate analyses with optional filters."""
        with self._lock:
            result = list(self._covariates.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]
        if status is not None:
            result = [c for c in result if c.status == status]

        return sorted(result, key=lambda c: c.id)

    def get_covariate_analysis(self, covariate_id: str) -> CovariateAnalysis | None:
        """Get a single covariate analysis by ID."""
        with self._lock:
            return self._covariates.get(covariate_id)

    def create_covariate_analysis(self, payload: CovariateAnalysisCreate) -> CovariateAnalysis:
        """Create a new covariate analysis."""
        now = datetime.now(timezone.utc)
        covariate_id = f"COV-{uuid4().hex[:8].upper()}"
        covariate = CovariateAnalysis(
            id=covariate_id,
            status=CovariateStatus.PLANNED,
            analysis_date=now,
            created_at=now,
            mean_value=None,
            std_deviation=None,
            missing_count=0,
            missing_pct=0.0,
            distribution_type=None,
            correlation_with_outcome=None,
            notes=None,
            **payload.model_dump(),
        )
        with self._lock:
            self._covariates[covariate_id] = covariate
        logger.info("Created covariate analysis %s: %s", covariate_id, payload.covariate_name)
        return covariate

    def update_covariate_analysis(
        self, covariate_id: str, payload: CovariateAnalysisUpdate
    ) -> CovariateAnalysis | None:
        """Update an existing covariate analysis."""
        with self._lock:
            existing = self._covariates.get(covariate_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CovariateAnalysis(**data)
            self._covariates[covariate_id] = updated
        return updated

    def delete_covariate_analysis(self, covariate_id: str) -> bool:
        """Delete a covariate analysis. Returns True if deleted."""
        with self._lock:
            if covariate_id in self._covariates:
                del self._covariates[covariate_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Arm Assignments
    # ------------------------------------------------------------------

    def list_arm_assignments(
        self,
        *,
        trial_id: str | None = None,
        site_id: str | None = None,
        arm_name: str | None = None,
        assignment_method: AssignmentMethod | None = None,
        is_confirmed: bool | None = None,
    ) -> list[ArmAssignment]:
        """List arm assignments with optional filters."""
        with self._lock:
            result = list(self._assignments.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if site_id is not None:
            result = [a for a in result if a.site_id == site_id]
        if arm_name is not None:
            result = [a for a in result if a.arm_name == arm_name]
        if assignment_method is not None:
            result = [a for a in result if a.assignment_method == assignment_method]
        if is_confirmed is not None:
            result = [a for a in result if a.is_confirmed == is_confirmed]

        return sorted(result, key=lambda a: a.assignment_date, reverse=True)

    def get_arm_assignment(self, assignment_id: str) -> ArmAssignment | None:
        """Get a single arm assignment by ID."""
        with self._lock:
            return self._assignments.get(assignment_id)

    def create_arm_assignment(self, payload: ArmAssignmentCreate) -> ArmAssignment:
        """Create a new arm assignment."""
        now = datetime.now(timezone.utc)
        assignment_id = f"AA-{uuid4().hex[:8].upper()}"

        # Determine next sequence number for this trial
        with self._lock:
            trial_assignments = [
                a for a in self._assignments.values()
                if a.trial_id == payload.trial_id
            ]
        seq = max((a.sequence_number for a in trial_assignments), default=0) + 1

        assignment = ArmAssignment(
            id=assignment_id,
            assignment_date=now,
            stratum_id=None,
            block_id=None,
            sequence_number=seq,
            is_confirmed=False,
            confirmed_by=None,
            confirmed_date=None,
            created_at=now,
            **payload.model_dump(),
        )
        with self._lock:
            self._assignments[assignment_id] = assignment
        logger.info(
            "Created arm assignment %s: patient=%s arm=%s",
            assignment_id, payload.subject_id, payload.arm_name,
        )
        return assignment

    def update_arm_assignment(
        self, assignment_id: str, payload: ArmAssignmentUpdate
    ) -> ArmAssignment | None:
        """Update an arm assignment."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._assignments.get(assignment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set confirmed_date when confirming
            if updates.get("is_confirmed") is True and not existing.is_confirmed:
                updates["confirmed_date"] = now

            data.update(updates)
            updated = ArmAssignment(**data)
            self._assignments[assignment_id] = updated
        return updated

    def delete_arm_assignment(self, assignment_id: str) -> bool:
        """Delete an arm assignment. Returns True if deleted."""
        with self._lock:
            if assignment_id in self._assignments:
                del self._assignments[assignment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Randomization Balance
    # ------------------------------------------------------------------

    def list_randomization_balances(
        self,
        *,
        trial_id: str | None = None,
        overall_balance_status: BalanceStatus | None = None,
    ) -> list[RandomizationBalance]:
        """List randomization balance reports with optional filters."""
        with self._lock:
            result = list(self._balances.values())

        if trial_id is not None:
            result = [b for b in result if b.trial_id == trial_id]
        if overall_balance_status is not None:
            result = [b for b in result if b.overall_balance_status == overall_balance_status]

        return sorted(result, key=lambda b: b.snapshot_date, reverse=True)

    def get_randomization_balance(self, balance_id: str) -> RandomizationBalance | None:
        """Get a single randomization balance report by ID."""
        with self._lock:
            return self._balances.get(balance_id)

    def create_randomization_balance(self, payload: RandomizationBalanceCreate) -> RandomizationBalance:
        """Create a new randomization balance report."""
        now = datetime.now(timezone.utc)
        balance_id = f"RB-{uuid4().hex[:8].upper()}"

        total = sum(payload.arm_distribution.values()) if payload.arm_distribution else 0

        # Calculate actual ratio
        actual_ratio: str | None = None
        balance_status = BalanceStatus.BALANCED
        if total > 0 and len(payload.arm_distribution) > 1:
            min_count = min(payload.arm_distribution.values())
            if min_count > 0:
                ratios = [round(v / min_count, 2) for v in payload.arm_distribution.values()]
                actual_ratio = ":".join(f"{r:.2f}" for r in ratios)

            expected = total / len(payload.arm_distribution)
            max_dev = max(abs(v - expected) for v in payload.arm_distribution.values())
            imbalance_pct = max_dev / expected if expected > 0 else 0.0

            if imbalance_pct >= 0.20:
                balance_status = BalanceStatus.CRITICAL
            elif imbalance_pct >= 0.12:
                balance_status = BalanceStatus.IMBALANCED
            elif imbalance_pct >= 0.08:
                balance_status = BalanceStatus.SLIGHTLY_IMBALANCED

        balance = RandomizationBalance(
            id=balance_id,
            trial_id=payload.trial_id,
            snapshot_date=now,
            total_randomized=total,
            arm_distribution=payload.arm_distribution,
            target_ratio=payload.target_ratio,
            actual_ratio=actual_ratio,
            overall_balance_status=balance_status,
            strata_balance=[],
            sites_with_imbalance=0,
            recommendation=None,
            generated_by=payload.generated_by,
            created_at=now,
        )
        with self._lock:
            self._balances[balance_id] = balance
        logger.info("Created randomization balance report %s for trial %s", balance_id, payload.trial_id)
        return balance

    def update_randomization_balance(
        self, balance_id: str, payload: RandomizationBalanceUpdate
    ) -> RandomizationBalance | None:
        """Update a randomization balance report."""
        with self._lock:
            existing = self._balances.get(balance_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = RandomizationBalance(**data)
            self._balances[balance_id] = updated
        return updated

    def delete_randomization_balance(self, balance_id: str) -> bool:
        """Delete a randomization balance report. Returns True if deleted."""
        with self._lock:
            if balance_id in self._balances:
                del self._balances[balance_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self) -> PatientStratificationMetrics:
        """Compute aggregated patient stratification metrics."""
        with self._lock:
            factors = list(self._factors.values())
            assessments = list(self._assessments.values())
            covariates = list(self._covariates.values())
            assignments = list(self._assignments.values())
            balances = list(self._balances.values())

        # Factors
        active_factors = sum(1 for f in factors if f.is_active)
        factors_by_type: dict[str, int] = {}
        for f in factors:
            key = f.factor_type.value
            factors_by_type[key] = factors_by_type.get(key, 0) + 1

        # Assessments by status
        assessments_by_status: dict[str, int] = {}
        for a in assessments:
            key = a.balance_status.value
            assessments_by_status[key] = assessments_by_status.get(key, 0) + 1

        # Covariates by status
        covariates_by_status: dict[str, int] = {}
        for c in covariates:
            key = c.status.value
            covariates_by_status[key] = covariates_by_status.get(key, 0) + 1

        # Assignments by method
        assignments_by_method: dict[str, int] = {}
        for a in assignments:
            key = a.assignment_method.value
            assignments_by_method[key] = assignments_by_method.get(key, 0) + 1

        confirmed_assignments = sum(1 for a in assignments if a.is_confirmed)

        # Current balance status (latest report)
        current_balance_status: str | None = None
        if balances:
            latest = max(balances, key=lambda b: b.snapshot_date)
            current_balance_status = latest.overall_balance_status.value

        return PatientStratificationMetrics(
            total_factors=len(factors),
            active_factors=active_factors,
            factors_by_type=factors_by_type,
            total_assessments=len(assessments),
            assessments_by_status=assessments_by_status,
            total_covariates=len(covariates),
            covariates_by_status=covariates_by_status,
            total_assignments=len(assignments),
            assignments_by_method=assignments_by_method,
            confirmed_assignments=confirmed_assignments,
            total_balance_snapshots=len(balances),
            current_balance_status=current_balance_status,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: PatientStratificationService | None = None
_instance_lock = threading.Lock()


def get_patient_stratification_service() -> PatientStratificationService:
    """Return the singleton PatientStratificationService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = PatientStratificationService()
    return _instance


def reset_patient_stratification_service() -> PatientStratificationService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = PatientStratificationService()
    return _instance
