"""Risk Prediction Service.

Provides clinical risk prediction models:
- 30-day readmission risk (LACE+ score features)
- Clinical deterioration (NEWS2/MEWS early warning scores)
- Mortality risk stratification (Charlson/Elixhauser comorbidity index)
- Risk tier classification (Low/Medium/High/Critical)
"""

import hashlib
import logging
import math
import threading
import time
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4

import numpy as np
from pydantic import BaseModel, Field

from app.services.ml_model_service import (
    FeatureSet,
    PredictionResult,
    get_ml_model_service,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Types
# ============================================================================


class RiskTier(str, Enum):
    """Risk tier classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskType(str, Enum):
    """Type of clinical risk."""

    READMISSION = "readmission"
    DETERIORATION = "deterioration"
    MORTALITY = "mortality"
    SEPSIS = "sepsis"
    FALL = "fall"
    PRESSURE_INJURY = "pressure_injury"


class ConsciousnessLevel(str, Enum):
    """AVPU consciousness scale."""

    ALERT = "alert"
    VOICE_RESPONSIVE = "voice"
    PAIN_RESPONSIVE = "pain"
    UNRESPONSIVE = "unresponsive"


class AdmissionType(str, Enum):
    """Type of hospital admission."""

    ELECTIVE = "elective"
    EMERGENCY = "emergency"
    URGENT = "urgent"
    TRANSFER = "transfer"


class DischargeDisposition(str, Enum):
    """Discharge disposition."""

    HOME = "home"
    HOME_HEALTH = "home_health"
    SNF = "snf"  # Skilled Nursing Facility
    REHAB = "rehab"
    LTAC = "ltac"  # Long-term Acute Care
    HOSPICE = "hospice"
    AMA = "ama"  # Against Medical Advice
    EXPIRED = "expired"


# ============================================================================
# Risk Score Models
# ============================================================================


class LACEPlusFeatures(BaseModel):
    """Features for LACE+ readmission risk score.

    LACE = Length of stay, Acuity, Comorbidities, ED visits
    Plus includes additional predictive features.
    """

    # Core LACE components
    length_of_stay: int = Field(..., ge=0, description="Length of stay in days")
    acuity_score: int = Field(
        default=0, ge=0, le=3, description="Admission acuity (0=elective, 1-3=emergency)"
    )
    comorbidity_count: int = Field(default=0, ge=0, description="Charlson comorbidity count")
    ed_visits_6mo: int = Field(
        default=0, ge=0, description="ED visits in prior 6 months"
    )

    # Additional predictive features
    age: int = Field(..., ge=0, le=120, description="Patient age in years")
    prior_admissions_12mo: int = Field(
        default=0, ge=0, description="Admissions in prior 12 months"
    )
    medication_count: int = Field(default=0, ge=0, description="Number of discharge medications")
    discharge_disposition: DischargeDisposition = Field(
        default=DischargeDisposition.HOME
    )
    hemoglobin: float | None = Field(None, description="Hemoglobin level (g/dL)")
    sodium: float | None = Field(None, description="Sodium level (mEq/L)")
    bun: float | None = Field(None, description="Blood urea nitrogen (mg/dL)")
    primary_diagnosis_code: str | None = Field(None, description="Primary ICD-10 diagnosis")


class NEWS2Features(BaseModel):
    """Features for NEWS2 (National Early Warning Score 2).

    Used for detecting clinical deterioration.
    """

    respiratory_rate: int = Field(..., ge=0, le=60, description="Breaths per minute")
    oxygen_saturation: float = Field(..., ge=0, le=100, description="SpO2 percentage")
    supplemental_oxygen: bool = Field(default=False, description="On supplemental O2")
    systolic_bp: int = Field(..., ge=0, le=300, description="Systolic blood pressure mmHg")
    heart_rate: int = Field(..., ge=0, le=300, description="Heart rate BPM")
    consciousness_level: ConsciousnessLevel = Field(default=ConsciousnessLevel.ALERT)
    temperature: float = Field(..., ge=30, le=45, description="Temperature in Celsius")

    # Optional additional features
    age: int | None = Field(None, ge=0, le=120)
    creatinine: float | None = Field(None, description="Creatinine (mg/dL)")
    wbc: float | None = Field(None, description="White blood cell count (K/uL)")
    lactate: float | None = Field(None, description="Lactate level (mmol/L)")


class MortalityFeatures(BaseModel):
    """Features for mortality risk stratification.

    Uses Charlson and Elixhauser comorbidity indices.
    """

    # Demographics
    age: int = Field(..., ge=0, le=120, description="Patient age in years")
    admission_type: AdmissionType = Field(default=AdmissionType.EMERGENCY)

    # Comorbidity scores
    charlson_score: int = Field(default=0, ge=0, description="Charlson Comorbidity Index")
    elixhauser_score: int = Field(default=0, description="Elixhauser Comorbidity Index")

    # Clinical status
    icu_admission: bool = Field(default=False, description="Admitted to ICU")
    mechanical_ventilation: bool = Field(default=False)
    vasopressor_use: bool = Field(default=False)

    # Lab values
    creatinine: float | None = Field(None, description="Creatinine (mg/dL)")
    bilirubin: float | None = Field(None, description="Total bilirubin (mg/dL)")
    albumin: float | None = Field(None, description="Albumin (g/dL)")
    platelets: float | None = Field(None, description="Platelet count (K/uL)")
    inr: float | None = Field(None, description="INR")
    pao2_fio2: float | None = Field(None, description="PaO2/FiO2 ratio")
    glasgow_coma_scale: int | None = Field(None, ge=3, le=15, description="GCS score")


# ============================================================================
# Risk Assessment Results
# ============================================================================


class RiskScore(BaseModel):
    """Individual risk score result."""

    risk_type: RiskType = Field(..., description="Type of risk assessed")
    score: float = Field(..., ge=0, le=1, description="Risk probability (0-1)")
    score_raw: float | None = Field(None, description="Raw score before normalization")
    tier: RiskTier = Field(..., description="Risk tier classification")
    percentile: float | None = Field(None, ge=0, le=100, description="Population percentile")
    confidence: float = Field(..., ge=0, le=1, description="Prediction confidence")
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RiskFactor(BaseModel):
    """Contributing factor to risk score."""

    name: str = Field(..., description="Factor name")
    value: Any = Field(..., description="Factor value")
    contribution: float = Field(..., description="Contribution to risk score")
    direction: str = Field(..., description="increases/decreases risk")
    explanation: str | None = Field(None, description="Human-readable explanation")


class PatientRiskAssessment(BaseModel):
    """Complete risk assessment for a patient."""

    patient_id: str = Field(..., description="Patient identifier")
    assessment_id: str = Field(default_factory=lambda: str(uuid4()))
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Risk scores
    readmission_risk: RiskScore | None = Field(None)
    deterioration_risk: RiskScore | None = Field(None)
    mortality_risk: RiskScore | None = Field(None)

    # Overall risk tier (highest of all risks)
    overall_tier: RiskTier = Field(default=RiskTier.LOW)
    overall_score: float = Field(default=0.0)

    # Contributing factors
    risk_factors: list[RiskFactor] = Field(default_factory=list)

    # Recommendations
    recommendations: list[str] = Field(default_factory=list)

    # Model information
    model_versions: dict[str, str] = Field(default_factory=dict)
    processing_time_ms: float = Field(default=0.0)


class RiskHistory(BaseModel):
    """Historical risk scores for trending."""

    patient_id: str
    risk_type: RiskType
    scores: list[dict[str, Any]] = Field(default_factory=list)
    trend: str | None = Field(None, description="improving/worsening/stable")
    trend_slope: float | None = Field(None)


class PopulationRiskSummary(BaseModel):
    """Summary of risk scores across patient population."""

    risk_type: RiskType
    total_patients: int
    tier_distribution: dict[str, int] = Field(default_factory=dict)
    average_score: float
    median_score: float
    high_risk_count: int
    critical_count: int
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# Risk Calculation Functions
# ============================================================================


def calculate_lace_score(features: LACEPlusFeatures) -> tuple[int, dict[str, int]]:
    """Calculate LACE score components.

    Returns:
        Tuple of (total_score, component_scores)
    """
    components = {}

    # Length of stay component (0-7 points)
    los = features.length_of_stay
    if los < 1:
        components["length_of_stay"] = 0
    elif los == 1:
        components["length_of_stay"] = 1
    elif los == 2:
        components["length_of_stay"] = 2
    elif los == 3:
        components["length_of_stay"] = 3
    elif los <= 6:
        components["length_of_stay"] = 4
    elif los <= 13:
        components["length_of_stay"] = 5
    else:
        components["length_of_stay"] = 7

    # Acuity component (0-3 points)
    components["acuity"] = min(features.acuity_score, 3)

    # Comorbidity component (0-5 points based on Charlson)
    charlson = features.comorbidity_count
    if charlson == 0:
        components["comorbidity"] = 0
    elif charlson == 1:
        components["comorbidity"] = 1
    elif charlson == 2:
        components["comorbidity"] = 2
    elif charlson == 3:
        components["comorbidity"] = 3
    else:
        components["comorbidity"] = 5

    # ED visits component (0-4 points)
    ed_visits = features.ed_visits_6mo
    if ed_visits == 0:
        components["ed_visits"] = 0
    elif ed_visits == 1:
        components["ed_visits"] = 1
    elif ed_visits == 2:
        components["ed_visits"] = 2
    elif ed_visits == 3:
        components["ed_visits"] = 3
    else:
        components["ed_visits"] = 4

    total = sum(components.values())
    return total, components


def calculate_news2_score(features: NEWS2Features) -> tuple[int, dict[str, int]]:
    """Calculate NEWS2 score components.

    Returns:
        Tuple of (total_score, component_scores)
    """
    components = {}

    # Respiratory rate (0-3 points)
    rr = features.respiratory_rate
    if rr <= 8:
        components["respiratory_rate"] = 3
    elif rr <= 11:
        components["respiratory_rate"] = 1
    elif rr <= 20:
        components["respiratory_rate"] = 0
    elif rr <= 24:
        components["respiratory_rate"] = 2
    else:
        components["respiratory_rate"] = 3

    # Oxygen saturation (0-3 points)
    spo2 = features.oxygen_saturation
    if features.supplemental_oxygen:
        # Scale 2 for hypercapnic respiratory failure
        if spo2 <= 83:
            components["oxygen_saturation"] = 3
        elif spo2 <= 85:
            components["oxygen_saturation"] = 2
        elif spo2 <= 87:
            components["oxygen_saturation"] = 1
        elif spo2 <= 92:
            components["oxygen_saturation"] = 0
        elif spo2 <= 94:
            components["oxygen_saturation"] = 1
        elif spo2 <= 96:
            components["oxygen_saturation"] = 2
        else:
            components["oxygen_saturation"] = 3
    else:
        # Scale 1
        if spo2 <= 91:
            components["oxygen_saturation"] = 3
        elif spo2 <= 93:
            components["oxygen_saturation"] = 2
        elif spo2 <= 95:
            components["oxygen_saturation"] = 1
        else:
            components["oxygen_saturation"] = 0

    # Supplemental oxygen (0-2 points)
    components["supplemental_oxygen"] = 2 if features.supplemental_oxygen else 0

    # Systolic BP (0-3 points)
    sbp = features.systolic_bp
    if sbp <= 90:
        components["systolic_bp"] = 3
    elif sbp <= 100:
        components["systolic_bp"] = 2
    elif sbp <= 110:
        components["systolic_bp"] = 1
    elif sbp <= 219:
        components["systolic_bp"] = 0
    else:
        components["systolic_bp"] = 3

    # Heart rate (0-3 points)
    hr = features.heart_rate
    if hr <= 40:
        components["heart_rate"] = 3
    elif hr <= 50:
        components["heart_rate"] = 1
    elif hr <= 90:
        components["heart_rate"] = 0
    elif hr <= 110:
        components["heart_rate"] = 1
    elif hr <= 130:
        components["heart_rate"] = 2
    else:
        components["heart_rate"] = 3

    # Consciousness (0-3 points)
    if features.consciousness_level == ConsciousnessLevel.ALERT:
        components["consciousness"] = 0
    else:
        components["consciousness"] = 3

    # Temperature (0-3 points)
    temp = features.temperature
    if temp <= 35.0:
        components["temperature"] = 3
    elif temp <= 36.0:
        components["temperature"] = 1
    elif temp <= 38.0:
        components["temperature"] = 0
    elif temp <= 39.0:
        components["temperature"] = 1
    else:
        components["temperature"] = 2

    total = sum(components.values())
    return total, components


def calculate_charlson_index(conditions: list[str]) -> int:
    """Calculate Charlson Comorbidity Index from ICD-10 codes.

    Simplified version - in production would use full ICD-10 mapping.
    """
    # Condition weights (simplified)
    weights = {
        "myocardial_infarction": 1,
        "congestive_heart_failure": 1,
        "peripheral_vascular": 1,
        "cerebrovascular": 1,
        "dementia": 1,
        "chronic_pulmonary": 1,
        "rheumatic": 1,
        "peptic_ulcer": 1,
        "mild_liver": 1,
        "diabetes_uncomplicated": 1,
        "diabetes_complicated": 2,
        "hemiplegia": 2,
        "renal": 2,
        "malignancy": 2,
        "moderate_severe_liver": 3,
        "metastatic_tumor": 6,
        "aids_hiv": 6,
    }

    total = 0
    conditions_lower = [c.lower() for c in conditions]
    for condition, weight in weights.items():
        if any(condition in c for c in conditions_lower):
            total += weight

    return total


def score_to_tier(score: float) -> RiskTier:
    """Convert probability score to risk tier."""
    if score >= 0.7:
        return RiskTier.CRITICAL
    elif score >= 0.5:
        return RiskTier.HIGH
    elif score >= 0.3:
        return RiskTier.MEDIUM
    else:
        return RiskTier.LOW


def tier_to_score_threshold(tier: RiskTier) -> float:
    """Get minimum score threshold for a tier."""
    thresholds = {
        RiskTier.CRITICAL: 0.7,
        RiskTier.HIGH: 0.5,
        RiskTier.MEDIUM: 0.3,
        RiskTier.LOW: 0.0,
    }
    return thresholds[tier]


# ============================================================================
# Risk Prediction Service
# ============================================================================


class RiskPredictionService:
    """Service for clinical risk predictions."""

    def __init__(self):
        """Initialize the risk prediction service."""
        self._ml_service = get_ml_model_service()
        self._risk_history: dict[str, list[dict[str, Any]]] = {}  # patient_id -> history
        self._initialized = False

    def assess_readmission_risk(
        self, patient_id: str, features: LACEPlusFeatures
    ) -> RiskScore:
        """Assess 30-day readmission risk using LACE+ features.

        Args:
            patient_id: Patient identifier.
            features: LACE+ input features.

        Returns:
            RiskScore with readmission probability.
        """
        # Calculate raw LACE score
        lace_score, components = calculate_lace_score(features)

        # Create feature set for ML model
        feature_dict = {
            "length_of_stay": features.length_of_stay,
            "acuity_score": features.acuity_score,
            "comorbidity_count": features.comorbidity_count,
            "ed_visits_6mo": features.ed_visits_6mo,
            "age": features.age,
            "prior_admissions": features.prior_admissions_12mo,
            "medication_count": features.medication_count,
            "discharge_disposition": features.discharge_disposition.value,
        }

        feature_set = FeatureSet(patient_id=patient_id, features=feature_dict)

        # Get ML prediction
        try:
            prediction = self._ml_service.predict("readmission-risk-v1", feature_set)
            score = prediction.prediction
            confidence = prediction.confidence
        except Exception as e:
            logger.warning(f"ML prediction failed, using LACE score: {e}")
            # Fallback to LACE score conversion
            # LACE score 0-19, convert to probability
            score = min(0.99, max(0.01, lace_score / 19 * 0.8 + 0.1))
            confidence = 0.6

        tier = score_to_tier(score)

        # Store in history
        self._store_risk_history(patient_id, RiskType.READMISSION, score, tier)

        return RiskScore(
            risk_type=RiskType.READMISSION,
            score=round(score, 4),
            score_raw=float(lace_score),
            tier=tier,
            percentile=self._calculate_percentile(score, RiskType.READMISSION),
            confidence=round(confidence, 4),
        )

    def assess_deterioration_risk(
        self, patient_id: str, features: NEWS2Features
    ) -> RiskScore:
        """Assess clinical deterioration risk using NEWS2.

        Args:
            patient_id: Patient identifier.
            features: NEWS2 input features.

        Returns:
            RiskScore with deterioration probability.
        """
        # Calculate raw NEWS2 score
        news2_score, components = calculate_news2_score(features)

        # Create feature set for ML model
        feature_dict = {
            "respiratory_rate": features.respiratory_rate,
            "oxygen_saturation": features.oxygen_saturation,
            "supplemental_oxygen": 1 if features.supplemental_oxygen else 0,
            "systolic_bp": features.systolic_bp,
            "heart_rate": features.heart_rate,
            "consciousness_level": features.consciousness_level.value,
            "temperature": features.temperature,
            "age": features.age or 60,
        }

        feature_set = FeatureSet(patient_id=patient_id, features=feature_dict)

        # Get ML prediction
        try:
            prediction = self._ml_service.predict("deterioration-risk-v1", feature_set)
            score = prediction.prediction
            confidence = prediction.confidence
        except Exception as e:
            logger.warning(f"ML prediction failed, using NEWS2 score: {e}")
            # NEWS2 score 0-20, convert to probability
            # Score 0-4: Low, 5-6: Medium, 7+: High
            if news2_score >= 7:
                score = 0.7 + (news2_score - 7) / 13 * 0.29
            elif news2_score >= 5:
                score = 0.4 + (news2_score - 5) / 2 * 0.3
            else:
                score = news2_score / 5 * 0.4
            score = min(0.99, max(0.01, score))
            confidence = 0.7

        tier = score_to_tier(score)

        # Store in history
        self._store_risk_history(patient_id, RiskType.DETERIORATION, score, tier)

        return RiskScore(
            risk_type=RiskType.DETERIORATION,
            score=round(score, 4),
            score_raw=float(news2_score),
            tier=tier,
            percentile=self._calculate_percentile(score, RiskType.DETERIORATION),
            confidence=round(confidence, 4),
        )

    def assess_mortality_risk(
        self, patient_id: str, features: MortalityFeatures
    ) -> RiskScore:
        """Assess mortality risk using comorbidity indices.

        Args:
            patient_id: Patient identifier.
            features: Mortality risk features.

        Returns:
            RiskScore with mortality probability.
        """
        # Create feature set for ML model
        feature_dict = {
            "charlson_score": features.charlson_score,
            "elixhauser_score": features.elixhauser_score,
            "age": features.age,
            "admission_type": features.admission_type.value,
            "icu_admission": 1 if features.icu_admission else 0,
            "mechanical_ventilation": 1 if features.mechanical_ventilation else 0,
            "vasopressor_use": 1 if features.vasopressor_use else 0,
            "creatinine": features.creatinine or 1.0,
            "bilirubin": features.bilirubin or 1.0,
        }

        feature_set = FeatureSet(patient_id=patient_id, features=feature_dict)

        # Get ML prediction
        try:
            prediction = self._ml_service.predict("mortality-risk-v1", feature_set)
            score = prediction.prediction
            confidence = prediction.confidence
        except Exception as e:
            logger.warning(f"ML prediction failed, using Charlson score: {e}")
            # Charlson-based estimate
            charlson = features.charlson_score
            age_factor = max(0, (features.age - 50) / 50) * 0.2
            icu_factor = 0.2 if features.icu_admission else 0
            vent_factor = 0.25 if features.mechanical_ventilation else 0

            base_risk = charlson / 37  # Max Charlson ~37
            score = min(0.95, base_risk + age_factor + icu_factor + vent_factor)
            score = max(0.01, score)
            confidence = 0.55

        tier = score_to_tier(score)

        # Calculate combined comorbidity score for raw
        raw_score = features.charlson_score + abs(features.elixhauser_score) / 2

        # Store in history
        self._store_risk_history(patient_id, RiskType.MORTALITY, score, tier)

        return RiskScore(
            risk_type=RiskType.MORTALITY,
            score=round(score, 4),
            score_raw=round(raw_score, 2),
            tier=tier,
            percentile=self._calculate_percentile(score, RiskType.MORTALITY),
            confidence=round(confidence, 4),
        )

    def get_comprehensive_assessment(
        self,
        patient_id: str,
        lace_features: LACEPlusFeatures | None = None,
        news2_features: NEWS2Features | None = None,
        mortality_features: MortalityFeatures | None = None,
    ) -> PatientRiskAssessment:
        """Get comprehensive risk assessment for a patient.

        Args:
            patient_id: Patient identifier.
            lace_features: Optional LACE+ features for readmission.
            news2_features: Optional NEWS2 features for deterioration.
            mortality_features: Optional features for mortality risk.

        Returns:
            PatientRiskAssessment with all available risk scores.
        """
        start_time = time.perf_counter()

        assessment = PatientRiskAssessment(patient_id=patient_id)
        risk_factors = []
        recommendations = []
        scores = []

        # Readmission risk
        if lace_features:
            assessment.readmission_risk = self.assess_readmission_risk(
                patient_id, lace_features
            )
            scores.append(assessment.readmission_risk.score)
            assessment.model_versions["readmission"] = "1.2.0"

            # Add risk factors
            if lace_features.length_of_stay > 7:
                risk_factors.append(
                    RiskFactor(
                        name="Length of Stay",
                        value=lace_features.length_of_stay,
                        contribution=0.15,
                        direction="increases",
                        explanation=f"Extended stay of {lace_features.length_of_stay} days increases readmission risk",
                    )
                )

            if lace_features.ed_visits_6mo >= 2:
                risk_factors.append(
                    RiskFactor(
                        name="ED Visits",
                        value=lace_features.ed_visits_6mo,
                        contribution=0.12,
                        direction="increases",
                        explanation=f"{lace_features.ed_visits_6mo} ED visits in 6 months indicates instability",
                    )
                )
                recommendations.append(
                    "Consider care management enrollment for frequent ED utilization"
                )

            if assessment.readmission_risk.tier in [RiskTier.HIGH, RiskTier.CRITICAL]:
                recommendations.append(
                    "Schedule follow-up appointment within 7 days of discharge"
                )
                recommendations.append("Consider transitional care management services")

        # Deterioration risk
        if news2_features:
            assessment.deterioration_risk = self.assess_deterioration_risk(
                patient_id, news2_features
            )
            scores.append(assessment.deterioration_risk.score)
            assessment.model_versions["deterioration"] = "2.0.0"

            # Add risk factors
            if news2_features.oxygen_saturation < 94:
                risk_factors.append(
                    RiskFactor(
                        name="Oxygen Saturation",
                        value=news2_features.oxygen_saturation,
                        contribution=0.18,
                        direction="increases",
                        explanation=f"SpO2 of {news2_features.oxygen_saturation}% below normal",
                    )
                )
                recommendations.append("Monitor oxygen saturation continuously")

            if news2_features.heart_rate > 100 or news2_features.heart_rate < 50:
                risk_factors.append(
                    RiskFactor(
                        name="Heart Rate",
                        value=news2_features.heart_rate,
                        contribution=0.12,
                        direction="increases",
                        explanation=f"Abnormal heart rate of {news2_features.heart_rate} BPM",
                    )
                )

            if assessment.deterioration_risk.tier == RiskTier.CRITICAL:
                recommendations.append("Urgent clinical review required")
                recommendations.append("Consider ICU consult")

        # Mortality risk
        if mortality_features:
            assessment.mortality_risk = self.assess_mortality_risk(
                patient_id, mortality_features
            )
            scores.append(assessment.mortality_risk.score)
            assessment.model_versions["mortality"] = "1.0.5"

            # Add risk factors
            if mortality_features.icu_admission:
                risk_factors.append(
                    RiskFactor(
                        name="ICU Admission",
                        value=True,
                        contribution=0.20,
                        direction="increases",
                        explanation="ICU admission significantly increases mortality risk",
                    )
                )

            if mortality_features.charlson_score >= 5:
                risk_factors.append(
                    RiskFactor(
                        name="Charlson Score",
                        value=mortality_features.charlson_score,
                        contribution=0.15,
                        direction="increases",
                        explanation=f"High comorbidity burden (Charlson {mortality_features.charlson_score})",
                    )
                )
                recommendations.append("Ensure goals of care discussion documented")

        # Calculate overall risk
        if scores:
            assessment.overall_score = round(max(scores), 4)
            assessment.overall_tier = score_to_tier(assessment.overall_score)
        else:
            assessment.overall_tier = RiskTier.LOW
            assessment.overall_score = 0.0

        assessment.risk_factors = risk_factors
        assessment.recommendations = recommendations
        assessment.processing_time_ms = round(
            (time.perf_counter() - start_time) * 1000, 2
        )

        return assessment

    def get_risk_history(
        self, patient_id: str, risk_type: RiskType | None = None, days: int = 30
    ) -> list[RiskHistory]:
        """Get historical risk scores for a patient.

        Args:
            patient_id: Patient identifier.
            risk_type: Optional filter by risk type.
            days: Number of days of history.

        Returns:
            List of RiskHistory objects.
        """
        history = []
        patient_history = self._risk_history.get(patient_id, [])

        # Filter by date
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        filtered = [
            h for h in patient_history if h.get("timestamp", datetime.now(timezone.utc)) >= cutoff
        ]

        # Group by risk type
        by_type: dict[RiskType, list[dict[str, Any]]] = {}
        for entry in filtered:
            rt = entry.get("risk_type")
            if risk_type and rt != risk_type:
                continue
            if rt not in by_type:
                by_type[rt] = []
            by_type[rt].append(entry)

        # Build history objects
        for rt, entries in by_type.items():
            entries_sorted = sorted(entries, key=lambda x: x.get("timestamp", datetime.now(timezone.utc)))

            # Calculate trend
            if len(entries_sorted) >= 2:
                scores = [e.get("score", 0) for e in entries_sorted]
                slope = (scores[-1] - scores[0]) / len(scores) if len(scores) > 1 else 0
                if slope > 0.02:
                    trend = "worsening"
                elif slope < -0.02:
                    trend = "improving"
                else:
                    trend = "stable"
            else:
                trend = None
                slope = None

            history.append(
                RiskHistory(
                    patient_id=patient_id,
                    risk_type=rt,
                    scores=entries_sorted,
                    trend=trend,
                    trend_slope=round(slope, 4) if slope else None,
                )
            )

        return history

    def get_population_summary(
        self, risk_type: RiskType, patient_ids: list[str] | None = None
    ) -> PopulationRiskSummary:
        """Get summary statistics for patient population.

        Args:
            risk_type: Type of risk to summarize.
            patient_ids: Optional list of patient IDs to include.

        Returns:
            PopulationRiskSummary with aggregate statistics.
        """
        # Collect latest scores for each patient
        scores = []
        tier_counts: dict[str, int] = {tier.value: 0 for tier in RiskTier}

        for pid, history in self._risk_history.items():
            if patient_ids and pid not in patient_ids:
                continue

            # Find latest entry for this risk type
            relevant = [h for h in history if h.get("risk_type") == risk_type]
            if relevant:
                latest = max(relevant, key=lambda x: x.get("timestamp", datetime.min))
                score = latest.get("score", 0)
                tier = latest.get("tier", RiskTier.LOW)
                scores.append(score)
                tier_counts[tier.value if isinstance(tier, RiskTier) else tier] += 1

        if not scores:
            # Return empty summary
            return PopulationRiskSummary(
                risk_type=risk_type,
                total_patients=0,
                tier_distribution=tier_counts,
                average_score=0.0,
                median_score=0.0,
                high_risk_count=0,
                critical_count=0,
            )

        return PopulationRiskSummary(
            risk_type=risk_type,
            total_patients=len(scores),
            tier_distribution=tier_counts,
            average_score=round(np.mean(scores), 4),
            median_score=round(np.median(scores), 4),
            high_risk_count=tier_counts.get(RiskTier.HIGH.value, 0),
            critical_count=tier_counts.get(RiskTier.CRITICAL.value, 0),
        )

    def explain_prediction(
        self, patient_id: str, risk_type: RiskType
    ) -> dict[str, Any]:
        """Get SHAP-based explanation for a prediction.

        Args:
            patient_id: Patient identifier.
            risk_type: Type of risk to explain.

        Returns:
            Dictionary with feature contributions and explanation.
        """
        # In production, this would use actual SHAP values
        # For demo, return mock explanation

        # Find latest prediction for this patient/risk
        history = self._risk_history.get(patient_id, [])
        relevant = [h for h in history if h.get("risk_type") == risk_type]

        if not relevant:
            return {
                "patient_id": patient_id,
                "risk_type": risk_type.value,
                "error": "No prediction found for this patient and risk type",
            }

        latest = max(relevant, key=lambda x: x.get("timestamp", datetime.min))

        # Generate mock SHAP values
        np.random.seed(hash(patient_id) % 2**32)
        features = ["age", "comorbidity_count", "length_of_stay", "ed_visits", "medications"]
        shap_values = np.random.uniform(-0.15, 0.15, len(features))

        # Normalize to sum to prediction - 0.5
        pred = latest.get("score", 0.5)
        shap_values = shap_values / shap_values.sum() * (pred - 0.5) if shap_values.sum() != 0 else shap_values

        return {
            "patient_id": patient_id,
            "risk_type": risk_type.value,
            "prediction": round(pred, 4),
            "base_value": 0.5,
            "feature_contributions": {
                f: round(v, 4) for f, v in zip(features, shap_values)
            },
            "explanation": f"The predicted {risk_type.value} risk of {pred:.1%} is primarily influenced by "
            + ", ".join(
                f"{f} ({'+' if v > 0 else ''}{v:.2f})"
                for f, v in sorted(
                    zip(features, shap_values), key=lambda x: abs(x[1]), reverse=True
                )[:3]
            ),
        }

    def _store_risk_history(
        self, patient_id: str, risk_type: RiskType, score: float, tier: RiskTier
    ) -> None:
        """Store risk score in history."""
        if patient_id not in self._risk_history:
            self._risk_history[patient_id] = []

        self._risk_history[patient_id].append(
            {
                "risk_type": risk_type,
                "score": score,
                "tier": tier,
                "timestamp": datetime.now(timezone.utc),
            }
        )

        # Limit history size
        if len(self._risk_history[patient_id]) > 100:
            self._risk_history[patient_id] = self._risk_history[patient_id][-100:]

    def _calculate_percentile(self, score: float, risk_type: RiskType) -> float:
        """Calculate approximate percentile for a score.

        In production, this would compare against actual population data.
        """
        # Mock percentile calculation using assumed distribution
        # Most patients are low risk, fewer are high risk
        # Using a beta distribution approximation
        alpha, beta = 2, 5  # Skewed toward lower scores
        percentile = 100 * (1 - (1 - score) ** (alpha / (alpha + beta)))
        return round(min(99, max(1, percentile)), 1)

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            "total_patients_tracked": len(self._risk_history),
            "total_predictions": sum(
                len(h) for h in self._risk_history.values()
            ),
            "risk_types_supported": [rt.value for rt in RiskType],
            "ml_service_stats": self._ml_service.get_stats(),
        }


# ============================================================================
# Singleton Instance
# ============================================================================

_risk_prediction_service: RiskPredictionService | None = None
_risk_lock = threading.Lock()


def get_risk_prediction_service() -> RiskPredictionService:
    """Get the singleton risk prediction service instance."""
    global _risk_prediction_service
    # VP-ThreadSafety: Double-checked locking for thread safety
    if _risk_prediction_service is None:
        with _risk_lock:
            if _risk_prediction_service is None:
                _risk_prediction_service = RiskPredictionService()
    return _risk_prediction_service
