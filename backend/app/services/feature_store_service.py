"""Feature Store Service.

Manages ML features for clinical trial patient screening pipelines.
Implements:
- 25+ pre-defined screening features across clinical domains
- Feature computation engine (per-patient and batch)
- Feature versioning and change tracking
- Descriptive statistics per feature
- Feature importance ranking for screening decisions

All computations use only the Python standard library (no numpy/scipy).
Patient data is simulated in-memory for the feature computation engine;
in production this would query the OMOP CDM / clinical data warehouse.
"""

from __future__ import annotations

import logging
import math
import random
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.schemas.feature_store import (
    BatchComputeResponse,
    ComputedFeatureValue,
    FeatureDataType,
    FeatureDefinitionResponse,
    FeatureDomain,
    FeatureImportance,
    FeatureImportanceListResponse,
    FeatureStatistics,
    FeatureStatisticsListResponse,
    FeatureVectorResponse,
    FeatureVersion,
    FeatureVersionHistory,
    MissingReason,
    TrendDirection,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------


class _FeatureRecord:
    """Internal mutable record for a feature definition."""

    __slots__ = (
        "id",
        "name",
        "description",
        "data_type",
        "domain",
        "computation_logic",
        "freshness_requirements",
        "source_tables",
        "tags",
        "is_builtin",
        "version",
        "created_at",
        "updated_at",
        "versions",
    )

    def __init__(
        self,
        *,
        name: str,
        description: str,
        data_type: FeatureDataType,
        domain: FeatureDomain,
        computation_logic: str = "",
        freshness_requirements: str = "on_demand",
        source_tables: list[str] | None = None,
        tags: list[str] | None = None,
        is_builtin: bool = False,
    ) -> None:
        now = datetime.now(timezone.utc)
        self.id = str(uuid4())
        self.name = name
        self.description = description
        self.data_type = data_type
        self.domain = domain
        self.computation_logic = computation_logic
        self.freshness_requirements = freshness_requirements
        self.source_tables: list[str] = source_tables or []
        self.tags: list[str] = tags or []
        self.is_builtin = is_builtin
        self.version = 1
        self.created_at = now
        self.updated_at = now
        self.versions: list[dict[str, Any]] = [
            {
                "version": 1,
                "changed_at": now.isoformat(),
                "changes": {"initial": True},
                "changed_by": "system",
            }
        ]

    def to_response(self) -> FeatureDefinitionResponse:
        return FeatureDefinitionResponse(
            id=self.id,
            name=self.name,
            description=self.description,
            data_type=self.data_type,
            domain=self.domain,
            computation_logic=self.computation_logic,
            freshness_requirements=self.freshness_requirements,
            source_tables=self.source_tables,
            tags=self.tags,
            is_builtin=self.is_builtin,
            version=self.version,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


# ---------------------------------------------------------------------------
# Simulated patient data helpers
# ---------------------------------------------------------------------------

# Deterministic random seed per patient to ensure consistent results
def _patient_seed(patient_id: str) -> int:
    """Derive a deterministic seed from a patient ID."""
    return hash(patient_id) & 0x7FFFFFFF


def _patient_rng(patient_id: str) -> random.Random:
    """Return a seeded Random instance for consistent per-patient data."""
    rng = random.Random()
    rng.seed(_patient_seed(patient_id))
    return rng


# ---------------------------------------------------------------------------
# Feature computation functions
# ---------------------------------------------------------------------------

def _compute_patient_age(patient_id: str) -> tuple[Any, MissingReason | None]:
    rng = _patient_rng(patient_id)
    age = rng.randint(18, 90)
    return age, None


def _compute_has_diabetes_type2(patient_id: str) -> tuple[Any, MissingReason | None]:
    rng = _patient_rng(patient_id)
    return rng.random() < 0.25, None


def _compute_latest_hba1c(patient_id: str) -> tuple[Any, MissingReason | None]:
    rng = _patient_rng(patient_id)
    if rng.random() < 0.15:
        return None, MissingReason.NO_DATA
    return round(rng.uniform(4.0, 14.0), 1), None


def _compute_bmi(patient_id: str) -> tuple[Any, MissingReason | None]:
    rng = _patient_rng(patient_id)
    if rng.random() < 0.1:
        return None, MissingReason.NO_DATA
    return round(rng.uniform(16.0, 45.0), 1), None


def _compute_active_medication_count(patient_id: str) -> tuple[Any, MissingReason | None]:
    rng = _patient_rng(patient_id)
    return rng.randint(0, 15), None


def _compute_condition_count(patient_id: str) -> tuple[Any, MissingReason | None]:
    rng = _patient_rng(patient_id)
    return rng.randint(0, 12), None


def _compute_latest_egfr(patient_id: str) -> tuple[Any, MissingReason | None]:
    rng = _patient_rng(patient_id)
    if rng.random() < 0.2:
        return None, MissingReason.NO_DATA
    return round(rng.uniform(15.0, 120.0), 1), None


def _compute_has_prior_treatment_chemo(patient_id: str) -> tuple[Any, MissingReason | None]:
    rng = _patient_rng(patient_id)
    return rng.random() < 0.15, None


def _compute_has_prior_treatment_radiation(patient_id: str) -> tuple[Any, MissingReason | None]:
    rng = _patient_rng(patient_id)
    return rng.random() < 0.10, None


def _compute_has_prior_treatment_surgery(patient_id: str) -> tuple[Any, MissingReason | None]:
    rng = _patient_rng(patient_id)
    return rng.random() < 0.30, None


def _compute_has_prior_treatment_immunotherapy(patient_id: str) -> tuple[Any, MissingReason | None]:
    rng = _patient_rng(patient_id)
    return rng.random() < 0.08, None


def _compute_days_since_diagnosis_diabetes(patient_id: str) -> tuple[Any, MissingReason | None]:
    rng = _patient_rng(patient_id)
    has_diabetes = rng.random() < 0.25
    if not has_diabetes:
        return None, MissingReason.NOT_APPLICABLE
    return rng.randint(30, 10950), None  # 1 month to 30 years


def _compute_days_since_diagnosis_hypertension(patient_id: str) -> tuple[Any, MissingReason | None]:
    rng = _patient_rng(patient_id)
    has_htn = rng.random() < 0.35
    if not has_htn:
        return None, MissingReason.NOT_APPLICABLE
    return rng.randint(30, 14600), None


def _compute_days_since_diagnosis_cancer(patient_id: str) -> tuple[Any, MissingReason | None]:
    rng = _patient_rng(patient_id)
    has_cancer = rng.random() < 0.10
    if not has_cancer:
        return None, MissingReason.NOT_APPLICABLE
    return rng.randint(1, 3650), None


def _compute_screening_history_count(patient_id: str) -> tuple[Any, MissingReason | None]:
    rng = _patient_rng(patient_id)
    return rng.randint(0, 8), None


def _compute_lab_value_trend_hba1c(patient_id: str) -> tuple[Any, MissingReason | None]:
    rng = _patient_rng(patient_id)
    if rng.random() < 0.2:
        return TrendDirection.INSUFFICIENT_DATA.value, None
    choice = rng.choice([TrendDirection.INCREASING, TrendDirection.DECREASING, TrendDirection.STABLE])
    return choice.value, None


def _compute_lab_value_trend_egfr(patient_id: str) -> tuple[Any, MissingReason | None]:
    rng = _patient_rng(patient_id)
    if rng.random() < 0.25:
        return TrendDirection.INSUFFICIENT_DATA.value, None
    choice = rng.choice([TrendDirection.INCREASING, TrendDirection.DECREASING, TrendDirection.STABLE])
    return choice.value, None


def _compute_lab_value_trend_creatinine(patient_id: str) -> tuple[Any, MissingReason | None]:
    rng = _patient_rng(patient_id)
    if rng.random() < 0.2:
        return TrendDirection.INSUFFICIENT_DATA.value, None
    choice = rng.choice([TrendDirection.INCREASING, TrendDirection.DECREASING, TrendDirection.STABLE])
    return choice.value, None


def _compute_comorbidity_score(patient_id: str) -> tuple[Any, MissingReason | None]:
    """Approximate Charlson Comorbidity Index (0-37 range, simplified)."""
    rng = _patient_rng(patient_id)
    return rng.randint(0, 15), None


def _compute_insurance_type(patient_id: str) -> tuple[Any, MissingReason | None]:
    rng = _patient_rng(patient_id)
    types = ["commercial", "medicare", "medicaid", "self_pay", "tricare", "other"]
    return rng.choice(types), None


def _compute_distance_to_nearest_site(patient_id: str) -> tuple[Any, MissingReason | None]:
    rng = _patient_rng(patient_id)
    if rng.random() < 0.05:
        return None, MissingReason.NO_DATA
    return round(rng.uniform(0.5, 200.0), 1), None


def _compute_engagement_score(patient_id: str) -> tuple[Any, MissingReason | None]:
    rng = _patient_rng(patient_id)
    return round(rng.uniform(0.0, 100.0), 1), None


def _compute_latest_systolic_bp(patient_id: str) -> tuple[Any, MissingReason | None]:
    rng = _patient_rng(patient_id)
    if rng.random() < 0.1:
        return None, MissingReason.NO_DATA
    return rng.randint(90, 200), None


def _compute_latest_diastolic_bp(patient_id: str) -> tuple[Any, MissingReason | None]:
    rng = _patient_rng(patient_id)
    if rng.random() < 0.1:
        return None, MissingReason.NO_DATA
    return rng.randint(50, 120), None


def _compute_smoking_status(patient_id: str) -> tuple[Any, MissingReason | None]:
    rng = _patient_rng(patient_id)
    statuses = ["never", "former", "current", "unknown"]
    return rng.choice(statuses), None


def _compute_gender(patient_id: str) -> tuple[Any, MissingReason | None]:
    rng = _patient_rng(patient_id)
    return rng.choice(["male", "female", "other"]), None


def _compute_ethnicity(patient_id: str) -> tuple[Any, MissingReason | None]:
    rng = _patient_rng(patient_id)
    return rng.choice(["hispanic", "non_hispanic", "unknown"]), None


# Map feature name -> computation function
_COMPUTE_FNS: dict[str, Any] = {
    "patient_age": _compute_patient_age,
    "has_diabetes_type2": _compute_has_diabetes_type2,
    "latest_hba1c": _compute_latest_hba1c,
    "bmi": _compute_bmi,
    "active_medication_count": _compute_active_medication_count,
    "condition_count": _compute_condition_count,
    "latest_egfr": _compute_latest_egfr,
    "has_prior_treatment_chemo": _compute_has_prior_treatment_chemo,
    "has_prior_treatment_radiation": _compute_has_prior_treatment_radiation,
    "has_prior_treatment_surgery": _compute_has_prior_treatment_surgery,
    "has_prior_treatment_immunotherapy": _compute_has_prior_treatment_immunotherapy,
    "days_since_diagnosis_diabetes": _compute_days_since_diagnosis_diabetes,
    "days_since_diagnosis_hypertension": _compute_days_since_diagnosis_hypertension,
    "days_since_diagnosis_cancer": _compute_days_since_diagnosis_cancer,
    "screening_history_count": _compute_screening_history_count,
    "lab_value_trend_hba1c": _compute_lab_value_trend_hba1c,
    "lab_value_trend_egfr": _compute_lab_value_trend_egfr,
    "lab_value_trend_creatinine": _compute_lab_value_trend_creatinine,
    "comorbidity_score": _compute_comorbidity_score,
    "insurance_type": _compute_insurance_type,
    "distance_to_nearest_site": _compute_distance_to_nearest_site,
    "engagement_score": _compute_engagement_score,
    "latest_systolic_bp": _compute_latest_systolic_bp,
    "latest_diastolic_bp": _compute_latest_diastolic_bp,
    "smoking_status": _compute_smoking_status,
    "gender": _compute_gender,
    "ethnicity": _compute_ethnicity,
}


# ---------------------------------------------------------------------------
# Pre-defined feature definitions (25+)
# ---------------------------------------------------------------------------

_BUILTIN_FEATURES: list[dict[str, Any]] = [
    {
        "name": "patient_age",
        "description": "Current age of the patient computed from date of birth",
        "data_type": FeatureDataType.NUMERIC,
        "domain": FeatureDomain.DEMOGRAPHIC,
        "computation_logic": "DATEDIFF(year, person.birth_datetime, CURRENT_DATE)",
        "freshness_requirements": "daily",
        "source_tables": ["person"],
        "tags": ["demographic", "screening"],
    },
    {
        "name": "has_diabetes_type2",
        "description": "Whether the patient has a Type 2 Diabetes diagnosis",
        "data_type": FeatureDataType.BOOLEAN,
        "domain": FeatureDomain.CONDITION,
        "computation_logic": "EXISTS condition_occurrence WHERE concept_id IN (201826, 443238)",
        "freshness_requirements": "daily",
        "source_tables": ["condition_occurrence"],
        "tags": ["condition", "screening", "metabolic"],
    },
    {
        "name": "latest_hba1c",
        "description": "Most recent HbA1c lab result value",
        "data_type": FeatureDataType.NUMERIC,
        "domain": FeatureDomain.LAB,
        "computation_logic": "MAX(measurement.value_as_number) WHERE concept_id = 3004410 ORDER BY measurement_date DESC LIMIT 1",
        "freshness_requirements": "daily",
        "source_tables": ["measurement"],
        "tags": ["lab", "screening", "metabolic"],
    },
    {
        "name": "bmi",
        "description": "Body Mass Index computed from latest height and weight observations",
        "data_type": FeatureDataType.NUMERIC,
        "domain": FeatureDomain.OBSERVATION,
        "computation_logic": "weight_kg / (height_m ^ 2) from latest observation records",
        "freshness_requirements": "weekly",
        "source_tables": ["measurement", "observation"],
        "tags": ["observation", "screening", "anthropometric"],
    },
    {
        "name": "active_medication_count",
        "description": "Number of currently active medications for the patient",
        "data_type": FeatureDataType.NUMERIC,
        "domain": FeatureDomain.MEDICATION,
        "computation_logic": "COUNT DISTINCT drug_concept_id WHERE drug_exposure_end_date >= CURRENT_DATE",
        "freshness_requirements": "daily",
        "source_tables": ["drug_exposure"],
        "tags": ["medication", "screening", "polypharmacy"],
    },
    {
        "name": "condition_count",
        "description": "Total number of distinct diagnosed conditions",
        "data_type": FeatureDataType.NUMERIC,
        "domain": FeatureDomain.CONDITION,
        "computation_logic": "COUNT DISTINCT condition_concept_id FROM condition_occurrence",
        "freshness_requirements": "daily",
        "source_tables": ["condition_occurrence"],
        "tags": ["condition", "screening"],
    },
    {
        "name": "latest_egfr",
        "description": "Most recent estimated Glomerular Filtration Rate value",
        "data_type": FeatureDataType.NUMERIC,
        "domain": FeatureDomain.LAB,
        "computation_logic": "measurement.value_as_number WHERE concept_id = 3049187 ORDER BY measurement_date DESC LIMIT 1",
        "freshness_requirements": "daily",
        "source_tables": ["measurement"],
        "tags": ["lab", "screening", "renal"],
    },
    {
        "name": "has_prior_treatment_chemo",
        "description": "Whether the patient has received prior chemotherapy",
        "data_type": FeatureDataType.BOOLEAN,
        "domain": FeatureDomain.PROCEDURE,
        "computation_logic": "EXISTS procedure_occurrence WHERE concept_id IN chemotherapy concept set",
        "freshness_requirements": "daily",
        "source_tables": ["procedure_occurrence", "drug_exposure"],
        "tags": ["treatment", "screening", "oncology"],
    },
    {
        "name": "has_prior_treatment_radiation",
        "description": "Whether the patient has received prior radiation therapy",
        "data_type": FeatureDataType.BOOLEAN,
        "domain": FeatureDomain.PROCEDURE,
        "computation_logic": "EXISTS procedure_occurrence WHERE concept_id IN radiation concept set",
        "freshness_requirements": "daily",
        "source_tables": ["procedure_occurrence"],
        "tags": ["treatment", "screening", "oncology"],
    },
    {
        "name": "has_prior_treatment_surgery",
        "description": "Whether the patient has received prior surgical treatment",
        "data_type": FeatureDataType.BOOLEAN,
        "domain": FeatureDomain.PROCEDURE,
        "computation_logic": "EXISTS procedure_occurrence WHERE concept_id IN surgical concept set",
        "freshness_requirements": "daily",
        "source_tables": ["procedure_occurrence"],
        "tags": ["treatment", "screening"],
    },
    {
        "name": "has_prior_treatment_immunotherapy",
        "description": "Whether the patient has received prior immunotherapy",
        "data_type": FeatureDataType.BOOLEAN,
        "domain": FeatureDomain.PROCEDURE,
        "computation_logic": "EXISTS drug_exposure WHERE concept_id IN immunotherapy concept set",
        "freshness_requirements": "daily",
        "source_tables": ["drug_exposure"],
        "tags": ["treatment", "screening", "oncology"],
    },
    {
        "name": "days_since_diagnosis_diabetes",
        "description": "Days since first diabetes diagnosis",
        "data_type": FeatureDataType.NUMERIC,
        "domain": FeatureDomain.CONDITION,
        "computation_logic": "DATEDIFF(day, MIN(condition_start_date), CURRENT_DATE) WHERE concept_id IN diabetes set",
        "freshness_requirements": "daily",
        "source_tables": ["condition_occurrence"],
        "tags": ["condition", "screening", "metabolic"],
    },
    {
        "name": "days_since_diagnosis_hypertension",
        "description": "Days since first hypertension diagnosis",
        "data_type": FeatureDataType.NUMERIC,
        "domain": FeatureDomain.CONDITION,
        "computation_logic": "DATEDIFF(day, MIN(condition_start_date), CURRENT_DATE) WHERE concept_id IN hypertension set",
        "freshness_requirements": "daily",
        "source_tables": ["condition_occurrence"],
        "tags": ["condition", "screening", "cardiovascular"],
    },
    {
        "name": "days_since_diagnosis_cancer",
        "description": "Days since first cancer diagnosis",
        "data_type": FeatureDataType.NUMERIC,
        "domain": FeatureDomain.CONDITION,
        "computation_logic": "DATEDIFF(day, MIN(condition_start_date), CURRENT_DATE) WHERE concept_id IN cancer concept set",
        "freshness_requirements": "daily",
        "source_tables": ["condition_occurrence"],
        "tags": ["condition", "screening", "oncology"],
    },
    {
        "name": "screening_history_count",
        "description": "Number of prior clinical trial screenings for this patient",
        "data_type": FeatureDataType.NUMERIC,
        "domain": FeatureDomain.SCREENING,
        "computation_logic": "COUNT(*) FROM screening_results WHERE patient_id = :pid",
        "freshness_requirements": "on_demand",
        "source_tables": ["screening_results"],
        "tags": ["screening", "history"],
    },
    {
        "name": "lab_value_trend_hba1c",
        "description": "Trending direction for HbA1c values over the last 6 months",
        "data_type": FeatureDataType.CATEGORICAL,
        "domain": FeatureDomain.LAB,
        "computation_logic": "Linear regression slope on HbA1c measurements in last 180 days",
        "freshness_requirements": "weekly",
        "source_tables": ["measurement"],
        "tags": ["lab", "trend", "metabolic"],
    },
    {
        "name": "lab_value_trend_egfr",
        "description": "Trending direction for eGFR values over the last 6 months",
        "data_type": FeatureDataType.CATEGORICAL,
        "domain": FeatureDomain.LAB,
        "computation_logic": "Linear regression slope on eGFR measurements in last 180 days",
        "freshness_requirements": "weekly",
        "source_tables": ["measurement"],
        "tags": ["lab", "trend", "renal"],
    },
    {
        "name": "lab_value_trend_creatinine",
        "description": "Trending direction for serum creatinine values over the last 6 months",
        "data_type": FeatureDataType.CATEGORICAL,
        "domain": FeatureDomain.LAB,
        "computation_logic": "Linear regression slope on creatinine measurements in last 180 days",
        "freshness_requirements": "weekly",
        "source_tables": ["measurement"],
        "tags": ["lab", "trend", "renal"],
    },
    {
        "name": "comorbidity_score",
        "description": "Approximate Charlson Comorbidity Index score",
        "data_type": FeatureDataType.NUMERIC,
        "domain": FeatureDomain.COMORBIDITY,
        "computation_logic": "Sum of weighted conditions from Charlson index (age-adjusted)",
        "freshness_requirements": "daily",
        "source_tables": ["condition_occurrence", "person"],
        "tags": ["comorbidity", "screening", "risk"],
    },
    {
        "name": "insurance_type",
        "description": "Patient's primary insurance category",
        "data_type": FeatureDataType.CATEGORICAL,
        "domain": FeatureDomain.INSURANCE,
        "computation_logic": "payer_plan_period.payer_source_value mapped to category",
        "freshness_requirements": "monthly",
        "source_tables": ["payer_plan_period"],
        "tags": ["insurance", "demographic", "screening"],
    },
    {
        "name": "distance_to_nearest_site",
        "description": "Distance in miles to the nearest trial site from patient location",
        "data_type": FeatureDataType.NUMERIC,
        "domain": FeatureDomain.GEOGRAPHIC,
        "computation_logic": "Haversine distance from patient zip centroid to nearest site coordinates",
        "freshness_requirements": "weekly",
        "source_tables": ["location", "care_site"],
        "tags": ["geographic", "screening", "accessibility"],
    },
    {
        "name": "engagement_score",
        "description": "Patient engagement level (0-100) based on appointment adherence and portal usage",
        "data_type": FeatureDataType.NUMERIC,
        "domain": FeatureDomain.ENGAGEMENT,
        "computation_logic": "Composite of visit frequency, portal logins, and medication adherence",
        "freshness_requirements": "weekly",
        "source_tables": ["visit_occurrence", "observation"],
        "tags": ["engagement", "screening", "behavioral"],
    },
    {
        "name": "latest_systolic_bp",
        "description": "Most recent systolic blood pressure reading",
        "data_type": FeatureDataType.NUMERIC,
        "domain": FeatureDomain.LAB,
        "computation_logic": "measurement.value_as_number WHERE concept_id = 3004249 ORDER BY measurement_date DESC LIMIT 1",
        "freshness_requirements": "daily",
        "source_tables": ["measurement"],
        "tags": ["lab", "screening", "cardiovascular"],
    },
    {
        "name": "latest_diastolic_bp",
        "description": "Most recent diastolic blood pressure reading",
        "data_type": FeatureDataType.NUMERIC,
        "domain": FeatureDomain.LAB,
        "computation_logic": "measurement.value_as_number WHERE concept_id = 3012888 ORDER BY measurement_date DESC LIMIT 1",
        "freshness_requirements": "daily",
        "source_tables": ["measurement"],
        "tags": ["lab", "screening", "cardiovascular"],
    },
    {
        "name": "smoking_status",
        "description": "Patient's current smoking status (never/former/current/unknown)",
        "data_type": FeatureDataType.CATEGORICAL,
        "domain": FeatureDomain.OBSERVATION,
        "computation_logic": "observation.value_as_concept_id WHERE concept_id = 4005823 mapped to category",
        "freshness_requirements": "monthly",
        "source_tables": ["observation"],
        "tags": ["observation", "screening", "lifestyle"],
    },
    {
        "name": "gender",
        "description": "Patient's recorded gender",
        "data_type": FeatureDataType.CATEGORICAL,
        "domain": FeatureDomain.DEMOGRAPHIC,
        "computation_logic": "person.gender_concept_id mapped to category",
        "freshness_requirements": "monthly",
        "source_tables": ["person"],
        "tags": ["demographic", "screening"],
    },
    {
        "name": "ethnicity",
        "description": "Patient's recorded ethnicity",
        "data_type": FeatureDataType.CATEGORICAL,
        "domain": FeatureDomain.DEMOGRAPHIC,
        "computation_logic": "person.ethnicity_concept_id mapped to category",
        "freshness_requirements": "monthly",
        "source_tables": ["person"],
        "tags": ["demographic", "screening", "diversity"],
    },
]

# Pre-defined importance scores (simulated from historical screening analysis)
_DEFAULT_IMPORTANCE: dict[str, float] = {
    "patient_age": 0.92,
    "has_diabetes_type2": 0.88,
    "latest_hba1c": 0.86,
    "bmi": 0.72,
    "active_medication_count": 0.68,
    "condition_count": 0.65,
    "latest_egfr": 0.84,
    "has_prior_treatment_chemo": 0.78,
    "has_prior_treatment_radiation": 0.62,
    "has_prior_treatment_surgery": 0.55,
    "has_prior_treatment_immunotherapy": 0.74,
    "days_since_diagnosis_diabetes": 0.70,
    "days_since_diagnosis_hypertension": 0.58,
    "days_since_diagnosis_cancer": 0.80,
    "screening_history_count": 0.45,
    "lab_value_trend_hba1c": 0.67,
    "lab_value_trend_egfr": 0.63,
    "lab_value_trend_creatinine": 0.60,
    "comorbidity_score": 0.82,
    "insurance_type": 0.38,
    "distance_to_nearest_site": 0.50,
    "engagement_score": 0.42,
    "latest_systolic_bp": 0.56,
    "latest_diastolic_bp": 0.54,
    "smoking_status": 0.48,
    "gender": 0.35,
    "ethnicity": 0.30,
}


# ---------------------------------------------------------------------------
# FeatureStoreService
# ---------------------------------------------------------------------------


class FeatureStoreService:
    """Manages ML features for clinical trial patient screening.

    Thread-safe, in-memory implementation.  In production the computation
    engine would query a clinical data warehouse; here we use deterministic
    simulated data keyed by patient_id.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # feature_name -> _FeatureRecord
        self._features: dict[str, _FeatureRecord] = {}
        # feature_name -> importance score (0-1)
        self._importance: dict[str, float] = dict(_DEFAULT_IMPORTANCE)
        # feature_name -> usage count
        self._usage_counts: dict[str, int] = defaultdict(int)
        # Cached statistics (populated on demand)
        self._statistics: dict[str, FeatureStatistics] = {}
        self._stats_computed_at: datetime | None = None
        # Register built-in features
        self._register_builtins()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _register_builtins(self) -> None:
        for defn in _BUILTIN_FEATURES:
            record = _FeatureRecord(is_builtin=True, **defn)
            self._features[record.name] = record

    # ------------------------------------------------------------------
    # Feature CRUD
    # ------------------------------------------------------------------

    def list_features(
        self,
        domain: FeatureDomain | None = None,
        data_type: FeatureDataType | None = None,
        tag: str | None = None,
    ) -> list[FeatureDefinitionResponse]:
        with self._lock:
            results = list(self._features.values())
        if domain is not None:
            results = [f for f in results if f.domain == domain]
        if data_type is not None:
            results = [f for f in results if f.data_type == data_type]
        if tag is not None:
            results = [f for f in results if tag in f.tags]
        return [r.to_response() for r in results]

    def get_feature(self, name: str) -> FeatureDefinitionResponse | None:
        with self._lock:
            record = self._features.get(name)
        if record is None:
            return None
        return record.to_response()

    def register_feature(
        self,
        *,
        name: str,
        description: str,
        data_type: FeatureDataType,
        domain: FeatureDomain,
        computation_logic: str = "",
        freshness_requirements: str = "on_demand",
        source_tables: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> FeatureDefinitionResponse:
        with self._lock:
            if name in self._features:
                raise ValueError(f"Feature '{name}' already exists")
            record = _FeatureRecord(
                name=name,
                description=description,
                data_type=data_type,
                domain=domain,
                computation_logic=computation_logic,
                freshness_requirements=freshness_requirements,
                source_tables=source_tables,
                tags=tags,
                is_builtin=False,
            )
            self._features[name] = record
        return record.to_response()

    def update_feature(
        self,
        name: str,
        *,
        description: str | None = None,
        data_type: FeatureDataType | None = None,
        domain: FeatureDomain | None = None,
        computation_logic: str | None = None,
        freshness_requirements: str | None = None,
        source_tables: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> FeatureDefinitionResponse | None:
        with self._lock:
            record = self._features.get(name)
            if record is None:
                return None
            changes: dict[str, Any] = {}
            if description is not None and description != record.description:
                changes["description"] = {"old": record.description, "new": description}
                record.description = description
            if data_type is not None and data_type != record.data_type:
                changes["data_type"] = {"old": record.data_type.value, "new": data_type.value}
                record.data_type = data_type
            if domain is not None and domain != record.domain:
                changes["domain"] = {"old": record.domain.value, "new": domain.value}
                record.domain = domain
            if computation_logic is not None and computation_logic != record.computation_logic:
                changes["computation_logic"] = {"old": record.computation_logic, "new": computation_logic}
                record.computation_logic = computation_logic
            if freshness_requirements is not None and freshness_requirements != record.freshness_requirements:
                changes["freshness_requirements"] = {"old": record.freshness_requirements, "new": freshness_requirements}
                record.freshness_requirements = freshness_requirements
            if source_tables is not None and source_tables != record.source_tables:
                changes["source_tables"] = {"old": record.source_tables, "new": source_tables}
                record.source_tables = source_tables
            if tags is not None and tags != record.tags:
                changes["tags"] = {"old": record.tags, "new": tags}
                record.tags = tags

            if changes:
                record.version += 1
                record.updated_at = datetime.now(timezone.utc)
                record.versions.append(
                    {
                        "version": record.version,
                        "changed_at": record.updated_at.isoformat(),
                        "changes": changes,
                        "changed_by": "user",
                    }
                )
        return record.to_response()

    def get_feature_versions(self, name: str) -> FeatureVersionHistory | None:
        with self._lock:
            record = self._features.get(name)
            if record is None:
                return None
            versions = [
                FeatureVersion(
                    version=v["version"],
                    changed_at=datetime.fromisoformat(v["changed_at"]) if isinstance(v["changed_at"], str) else v["changed_at"],
                    changes=v["changes"],
                    changed_by=v.get("changed_by", "system"),
                )
                for v in reversed(record.versions)
            ]
            return FeatureVersionHistory(
                feature_name=name,
                current_version=record.version,
                versions=versions,
            )

    # ------------------------------------------------------------------
    # Feature Computation
    # ------------------------------------------------------------------

    def compute_features(
        self,
        patient_id: str,
        feature_names: list[str] | None = None,
    ) -> FeatureVectorResponse:
        """Compute features for a single patient.

        Args:
            patient_id: Patient identifier.
            feature_names: Specific features to compute; None = all.

        Returns:
            FeatureVectorResponse with computed values.
        """
        start = time.perf_counter()
        with self._lock:
            if feature_names is None:
                target_features = list(self._features.keys())
            else:
                target_features = [n for n in feature_names if n in self._features]

        features_dict: dict[str, Any] = {}
        details: list[ComputedFeatureValue] = []
        missing = 0
        computed = 0

        for fname in target_features:
            feat_start = time.perf_counter()
            compute_fn = _COMPUTE_FNS.get(fname)
            with self._lock:
                record = self._features.get(fname)
            if record is None:
                continue

            if compute_fn is not None:
                try:
                    value, miss_reason = compute_fn(patient_id)
                except Exception as exc:
                    logger.warning("Error computing feature %s for %s: %s", fname, patient_id, exc)
                    value = None
                    miss_reason = MissingReason.COMPUTATION_ERROR
            else:
                # Custom feature without a registered computation function
                value = None
                miss_reason = MissingReason.NO_DATA

            feat_time = (time.perf_counter() - feat_start) * 1000
            is_missing = value is None
            if is_missing:
                missing += 1
            else:
                computed += 1

            features_dict[fname] = value
            details.append(
                ComputedFeatureValue(
                    feature_name=fname,
                    value=value,
                    data_type=record.data_type,
                    is_missing=is_missing,
                    missing_reason=miss_reason if is_missing else None,
                    computation_time_ms=round(feat_time, 3),
                )
            )

            # Track usage
            with self._lock:
                self._usage_counts[fname] += 1

        total_time = (time.perf_counter() - start) * 1000
        return FeatureVectorResponse(
            patient_id=patient_id,
            features=features_dict,
            feature_details=details,
            total_computation_time_ms=round(total_time, 3),
            missing_count=missing,
            computed_count=computed,
        )

    def batch_compute(
        self,
        patient_ids: list[str],
        feature_names: list[str] | None = None,
    ) -> BatchComputeResponse:
        """Compute features for multiple patients."""
        start = time.perf_counter()
        results: list[FeatureVectorResponse] = []
        errors: dict[str, str] = {}
        for pid in patient_ids:
            try:
                result = self.compute_features(pid, feature_names)
                results.append(result)
            except Exception as exc:
                errors[pid] = str(exc)
        total_time = (time.perf_counter() - start) * 1000
        return BatchComputeResponse(
            results=results,
            total_patients=len(patient_ids),
            total_computation_time_ms=round(total_time, 3),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Feature Statistics
    # ------------------------------------------------------------------

    def compute_statistics(
        self, sample_patient_ids: list[str] | None = None
    ) -> FeatureStatisticsListResponse:
        """Compute descriptive statistics for all features.

        Uses a sample of simulated patients if no IDs provided.
        """
        if sample_patient_ids is None:
            sample_patient_ids = [f"sample_patient_{i}" for i in range(200)]

        # Compute feature vectors for all sample patients
        vectors = [self.compute_features(pid) for pid in sample_patient_ids]

        stats_list: list[FeatureStatistics] = []
        with self._lock:
            feature_names = list(self._features.keys())
            feature_types = {n: self._features[n].data_type for n in feature_names}

        for fname in feature_names:
            dt = feature_types[fname]
            values = [v.features.get(fname) for v in vectors]
            non_null = [v for v in values if v is not None]
            null_count = len(values) - len(non_null)
            null_rate = null_count / len(values) if values else 0.0

            stat = FeatureStatistics(
                feature_name=fname,
                data_type=dt,
                sample_count=len(values),
                null_count=null_count,
                null_rate=round(null_rate, 4),
            )

            if dt == FeatureDataType.NUMERIC and non_null:
                numeric_vals = [float(v) for v in non_null]
                stat.min_value = min(numeric_vals)
                stat.max_value = max(numeric_vals)
                stat.mean_value = round(sum(numeric_vals) / len(numeric_vals), 4)
                sorted_vals = sorted(numeric_vals)
                n = len(sorted_vals)
                if n % 2 == 1:
                    stat.median_value = sorted_vals[n // 2]
                else:
                    stat.median_value = (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
                if n > 1:
                    mean = stat.mean_value
                    variance = sum((v - mean) ** 2 for v in numeric_vals) / (n - 1)
                    stat.std_value = round(math.sqrt(variance), 4)
                else:
                    stat.std_value = 0.0
                stat.unique_count = len(set(numeric_vals))

            elif dt in (FeatureDataType.CATEGORICAL, FeatureDataType.BOOLEAN, FeatureDataType.TEXT):
                dist: dict[str, int] = defaultdict(int)
                for v in non_null:
                    dist[str(v)] += 1
                stat.distribution = dict(dist)
                stat.unique_count = len(dist)

            stats_list.append(stat)

        now = datetime.now(timezone.utc)
        with self._lock:
            self._statistics = {s.feature_name: s for s in stats_list}
            self._stats_computed_at = now

        return FeatureStatisticsListResponse(
            total=len(stats_list),
            statistics=stats_list,
            computed_at=now,
        )

    def get_cached_statistics(self) -> FeatureStatisticsListResponse | None:
        """Return previously computed statistics, if any."""
        with self._lock:
            if not self._statistics:
                return None
            return FeatureStatisticsListResponse(
                total=len(self._statistics),
                statistics=list(self._statistics.values()),
                computed_at=self._stats_computed_at or datetime.now(timezone.utc),
            )

    # ------------------------------------------------------------------
    # Feature Importance
    # ------------------------------------------------------------------

    def get_importance(self) -> FeatureImportanceListResponse:
        """Return feature importance ranking."""
        with self._lock:
            entries: list[tuple[str, float]] = []
            for fname, record in self._features.items():
                score = self._importance.get(fname, 0.0)
                entries.append((fname, score))

        # Sort by importance descending
        entries.sort(key=lambda x: x[1], reverse=True)

        importance_list: list[FeatureImportance] = []
        for rank, (fname, score) in enumerate(entries, start=1):
            with self._lock:
                record = self._features.get(fname)
            if record is None:
                continue
            importance_list.append(
                FeatureImportance(
                    feature_name=fname,
                    importance_score=score,
                    rank=rank,
                    domain=record.domain,
                    description=record.description,
                    usage_count=self._usage_counts.get(fname, 0),
                )
            )

        return FeatureImportanceListResponse(
            total=len(importance_list),
            importance=importance_list,
        )

    def set_importance(self, feature_name: str, score: float) -> bool:
        """Set the importance score for a feature."""
        with self._lock:
            if feature_name not in self._features:
                return False
            self._importance[feature_name] = max(0.0, min(1.0, score))
        return True

    # ------------------------------------------------------------------
    # Utility / stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return service-level statistics."""
        with self._lock:
            total = len(self._features)
            builtin = sum(1 for f in self._features.values() if f.is_builtin)
            custom = total - builtin
            domains = defaultdict(int)
            for f in self._features.values():
                domains[f.domain.value] += 1
        return {
            "total_features": total,
            "builtin_features": builtin,
            "custom_features": custom,
            "domains": dict(domains),
            "has_statistics": self._stats_computed_at is not None,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_service: FeatureStoreService | None = None
_service_lock = threading.Lock()


def get_feature_store_service() -> FeatureStoreService:
    """Return the singleton FeatureStoreService instance."""
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = FeatureStoreService()
    return _service


def reset_feature_store_service() -> None:
    """Reset the singleton (for testing)."""
    global _service
    with _service_lock:
        _service = None
