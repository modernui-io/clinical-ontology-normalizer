"""Predictions API Endpoints.

Provides predictive analytics endpoints:
- POST /api/predictions/readmission - Predict readmission risk
- POST /api/predictions/deterioration - Calculate early warning score
- POST /api/predictions/mortality - Mortality risk stratification
- GET /api/predictions/patient/{patient_id}/risks - All risks for patient
- GET /api/predictions/models - List available models
- GET /api/predictions/models/{model_id}/performance - Model metrics
- POST /api/predictions/explain - SHAP-based explanation
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.errors import ErrorCode, InternalError, NotFoundError

router = APIRouter(prefix="/predictions", tags=["Predictive Analytics"])


# ============================================================================
# Request/Response Models
# ============================================================================


class ReadmissionPredictionRequest(BaseModel):
    """Request for readmission risk prediction."""

    patient_id: str = Field(..., description="Patient identifier")
    length_of_stay: int = Field(..., ge=0, description="Length of stay in days")
    acuity_score: int = Field(
        default=0, ge=0, le=3, description="Admission acuity (0=elective, 1-3=emergency)"
    )
    comorbidity_count: int = Field(default=0, ge=0, description="Charlson comorbidity count")
    ed_visits_6mo: int = Field(default=0, ge=0, description="ED visits in prior 6 months")
    age: int = Field(..., ge=0, le=120, description="Patient age in years")
    prior_admissions_12mo: int = Field(default=0, ge=0)
    medication_count: int = Field(default=0, ge=0)
    discharge_disposition: str = Field(default="home")
    hemoglobin: float | None = Field(None)
    sodium: float | None = Field(None)
    bun: float | None = Field(None)
    primary_diagnosis_code: str | None = Field(None)


class DeteriorationPredictionRequest(BaseModel):
    """Request for deterioration risk (NEWS2) prediction."""

    patient_id: str = Field(..., description="Patient identifier")
    respiratory_rate: int = Field(..., ge=0, le=60, description="Breaths per minute")
    oxygen_saturation: float = Field(..., ge=0, le=100, description="SpO2 percentage")
    supplemental_oxygen: bool = Field(default=False)
    systolic_bp: int = Field(..., ge=0, le=300, description="Systolic BP mmHg")
    heart_rate: int = Field(..., ge=0, le=300, description="Heart rate BPM")
    consciousness_level: str = Field(default="alert", description="alert/voice/pain/unresponsive")
    temperature: float = Field(..., ge=30, le=45, description="Temperature in Celsius")
    age: int | None = Field(None, ge=0, le=120)
    creatinine: float | None = Field(None)
    wbc: float | None = Field(None)
    lactate: float | None = Field(None)


class MortalityPredictionRequest(BaseModel):
    """Request for mortality risk prediction."""

    patient_id: str = Field(..., description="Patient identifier")
    age: int = Field(..., ge=0, le=120, description="Patient age in years")
    admission_type: str = Field(default="emergency")
    charlson_score: int = Field(default=0, ge=0)
    elixhauser_score: int = Field(default=0)
    icu_admission: bool = Field(default=False)
    mechanical_ventilation: bool = Field(default=False)
    vasopressor_use: bool = Field(default=False)
    creatinine: float | None = Field(None)
    bilirubin: float | None = Field(None)
    albumin: float | None = Field(None)
    platelets: float | None = Field(None)
    inr: float | None = Field(None)
    pao2_fio2: float | None = Field(None)
    glasgow_coma_scale: int | None = Field(None, ge=3, le=15)


class RiskScoreResponse(BaseModel):
    """Response with risk score details."""

    request_id: str = Field(..., description="Unique request identifier")
    patient_id: str = Field(..., description="Patient identifier")
    risk_type: str = Field(..., description="Type of risk assessed")
    score: float = Field(..., ge=0, le=1, description="Risk probability (0-1)")
    score_raw: float | None = Field(None, description="Raw score before normalization")
    tier: str = Field(..., description="Risk tier (low/medium/high/critical)")
    percentile: float | None = Field(None, description="Population percentile")
    confidence: float = Field(..., ge=0, le=1)
    calculated_at: datetime = Field(...)
    processing_time_ms: float = Field(...)

    # Additional context
    contributing_factors: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class PatientRisksResponse(BaseModel):
    """Response with all risks for a patient."""

    patient_id: str
    assessment_id: str
    assessed_at: datetime
    overall_tier: str
    overall_score: float
    readmission_risk: dict[str, Any] | None = None
    deterioration_risk: dict[str, Any] | None = None
    mortality_risk: dict[str, Any] | None = None
    risk_factors: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    model_versions: dict[str, str] = Field(default_factory=dict)
    processing_time_ms: float


class ModelListResponse(BaseModel):
    """Response with list of available models."""

    total_models: int
    models: list[dict[str, Any]]


class ModelPerformanceResponse(BaseModel):
    """Response with model performance metrics."""

    model_id: str
    version: str
    evaluated_at: datetime
    dataset_type: str
    sample_count: int
    auc_roc: float | None
    auc_pr: float | None
    accuracy: float | None
    precision: float | None
    recall: float | None
    f1: float | None
    brier_score: float | None
    calibration_slope: float | None
    roc_curve: dict[str, list[float]] | None = None
    pr_curve: dict[str, list[float]] | None = None
    calibration_curve: dict[str, list[float]] | None = None
    feature_importance: dict[str, float] = Field(default_factory=dict)


class ExplainRequest(BaseModel):
    """Request for SHAP-based explanation."""

    patient_id: str = Field(..., description="Patient identifier")
    risk_type: str = Field(..., description="Type of risk to explain")


class ExplainResponse(BaseModel):
    """Response with prediction explanation."""

    patient_id: str
    risk_type: str
    prediction: float
    base_value: float
    feature_contributions: dict[str, float]
    explanation: str
    waterfall_data: list[dict[str, Any]] = Field(default_factory=list)


# ============================================================================
# Readmission Risk Endpoint
# ============================================================================


@router.post(
    "/readmission",
    response_model=RiskScoreResponse,
    summary="Predict 30-day readmission risk",
    description="Calculate readmission risk using LACE+ features.",
)
async def predict_readmission(request: ReadmissionPredictionRequest) -> RiskScoreResponse:
    """Predict 30-day hospital readmission risk.

    Uses LACE+ score features:
    - Length of stay
    - Acuity of admission
    - Comorbidities (Charlson index)
    - ED visits in prior 6 months
    - Additional features: age, medications, prior admissions

    Args:
        request: Patient features for readmission prediction.

    Returns:
        RiskScoreResponse with readmission probability and risk tier.
    """
    start_time = time.perf_counter()
    request_id = str(uuid4())

    try:
        from app.services.risk_prediction_service import (
            DischargeDisposition,
            LACEPlusFeatures,
            get_risk_prediction_service,
        )

        service = get_risk_prediction_service()

        # Map discharge disposition
        disposition_map = {
            "home": DischargeDisposition.HOME,
            "home_health": DischargeDisposition.HOME_HEALTH,
            "snf": DischargeDisposition.SNF,
            "rehab": DischargeDisposition.REHAB,
            "ltac": DischargeDisposition.LTAC,
            "hospice": DischargeDisposition.HOSPICE,
            "ama": DischargeDisposition.AMA,
        }
        disposition = disposition_map.get(
            request.discharge_disposition.lower(), DischargeDisposition.HOME
        )

        features = LACEPlusFeatures(
            length_of_stay=request.length_of_stay,
            acuity_score=request.acuity_score,
            comorbidity_count=request.comorbidity_count,
            ed_visits_6mo=request.ed_visits_6mo,
            age=request.age,
            prior_admissions_12mo=request.prior_admissions_12mo,
            medication_count=request.medication_count,
            discharge_disposition=disposition,
            hemoglobin=request.hemoglobin,
            sodium=request.sodium,
            bun=request.bun,
            primary_diagnosis_code=request.primary_diagnosis_code,
        )

        risk_score = service.assess_readmission_risk(request.patient_id, features)

        # Build contributing factors
        factors = []
        if request.length_of_stay > 5:
            factors.append({
                "name": "Length of Stay",
                "value": request.length_of_stay,
                "contribution": "high",
                "direction": "increases",
            })
        if request.ed_visits_6mo >= 2:
            factors.append({
                "name": "ED Visits (6mo)",
                "value": request.ed_visits_6mo,
                "contribution": "medium",
                "direction": "increases",
            })
        if request.comorbidity_count >= 3:
            factors.append({
                "name": "Comorbidities",
                "value": request.comorbidity_count,
                "contribution": "high",
                "direction": "increases",
            })

        # Build recommendations
        recommendations = []
        if risk_score.tier.value in ["high", "critical"]:
            recommendations.append("Schedule follow-up within 7 days of discharge")
            recommendations.append("Consider transitional care management")
            recommendations.append("Medication reconciliation recommended")
        if request.medication_count > 10:
            recommendations.append("Polypharmacy review recommended")

        processing_time = (time.perf_counter() - start_time) * 1000

        return RiskScoreResponse(
            request_id=request_id,
            patient_id=request.patient_id,
            risk_type="readmission",
            score=risk_score.score,
            score_raw=risk_score.score_raw,
            tier=risk_score.tier.value,
            percentile=risk_score.percentile,
            confidence=risk_score.confidence,
            calculated_at=risk_score.calculated_at,
            processing_time_ms=round(processing_time, 2),
            contributing_factors=factors,
            recommendations=recommendations,
        )

    except Exception as e:
        raise InternalError(
            message=f"Readmission prediction failed: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )


# ============================================================================
# Deterioration Risk Endpoint
# ============================================================================


@router.post(
    "/deterioration",
    response_model=RiskScoreResponse,
    summary="Calculate deterioration risk (NEWS2)",
    description="Calculate clinical deterioration risk using NEWS2 features.",
)
async def predict_deterioration(
    request: DeteriorationPredictionRequest,
) -> RiskScoreResponse:
    """Calculate clinical deterioration risk.

    Uses NEWS2 (National Early Warning Score 2):
    - Respiratory rate
    - Oxygen saturation
    - Supplemental oxygen
    - Systolic blood pressure
    - Heart rate
    - Consciousness level (AVPU)
    - Temperature

    Args:
        request: Patient vital signs and features.

    Returns:
        RiskScoreResponse with deterioration probability and NEWS2 score.
    """
    start_time = time.perf_counter()
    request_id = str(uuid4())

    try:
        from app.services.risk_prediction_service import (
            ConsciousnessLevel,
            NEWS2Features,
            get_risk_prediction_service,
        )

        service = get_risk_prediction_service()

        # Map consciousness level
        consciousness_map = {
            "alert": ConsciousnessLevel.ALERT,
            "voice": ConsciousnessLevel.VOICE_RESPONSIVE,
            "pain": ConsciousnessLevel.PAIN_RESPONSIVE,
            "unresponsive": ConsciousnessLevel.UNRESPONSIVE,
        }
        consciousness = consciousness_map.get(
            request.consciousness_level.lower(), ConsciousnessLevel.ALERT
        )

        features = NEWS2Features(
            respiratory_rate=request.respiratory_rate,
            oxygen_saturation=request.oxygen_saturation,
            supplemental_oxygen=request.supplemental_oxygen,
            systolic_bp=request.systolic_bp,
            heart_rate=request.heart_rate,
            consciousness_level=consciousness,
            temperature=request.temperature,
            age=request.age,
            creatinine=request.creatinine,
            wbc=request.wbc,
            lactate=request.lactate,
        )

        risk_score = service.assess_deterioration_risk(request.patient_id, features)

        # Build contributing factors
        factors = []
        if request.oxygen_saturation < 94:
            factors.append({
                "name": "Oxygen Saturation",
                "value": request.oxygen_saturation,
                "contribution": "high",
                "direction": "increases",
            })
        if request.heart_rate > 110 or request.heart_rate < 50:
            factors.append({
                "name": "Heart Rate",
                "value": request.heart_rate,
                "contribution": "medium",
                "direction": "increases",
            })
        if request.respiratory_rate > 24 or request.respiratory_rate < 9:
            factors.append({
                "name": "Respiratory Rate",
                "value": request.respiratory_rate,
                "contribution": "medium",
                "direction": "increases",
            })
        if consciousness != ConsciousnessLevel.ALERT:
            factors.append({
                "name": "Consciousness Level",
                "value": request.consciousness_level,
                "contribution": "high",
                "direction": "increases",
            })

        # Build recommendations
        recommendations = []
        if risk_score.tier.value == "critical":
            recommendations.append("URGENT: Clinical review required immediately")
            recommendations.append("Consider ICU consult")
            recommendations.append("Continuous monitoring required")
        elif risk_score.tier.value == "high":
            recommendations.append("Urgent clinical review within 1 hour")
            recommendations.append("Increase monitoring frequency")
        elif risk_score.tier.value == "medium":
            recommendations.append("Clinical review within 4-6 hours")

        processing_time = (time.perf_counter() - start_time) * 1000

        return RiskScoreResponse(
            request_id=request_id,
            patient_id=request.patient_id,
            risk_type="deterioration",
            score=risk_score.score,
            score_raw=risk_score.score_raw,
            tier=risk_score.tier.value,
            percentile=risk_score.percentile,
            confidence=risk_score.confidence,
            calculated_at=risk_score.calculated_at,
            processing_time_ms=round(processing_time, 2),
            contributing_factors=factors,
            recommendations=recommendations,
        )

    except Exception as e:
        raise InternalError(
            message=f"Deterioration prediction failed: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )


# ============================================================================
# Mortality Risk Endpoint
# ============================================================================


@router.post(
    "/mortality",
    response_model=RiskScoreResponse,
    summary="Calculate mortality risk",
    description="Calculate mortality risk using comorbidity indices.",
)
async def predict_mortality(request: MortalityPredictionRequest) -> RiskScoreResponse:
    """Calculate in-hospital mortality risk.

    Uses Charlson and Elixhauser comorbidity indices along with:
    - ICU admission status
    - Mechanical ventilation
    - Vasopressor use
    - Key lab values

    Args:
        request: Patient features for mortality risk.

    Returns:
        RiskScoreResponse with mortality probability.
    """
    start_time = time.perf_counter()
    request_id = str(uuid4())

    try:
        from app.services.risk_prediction_service import (
            AdmissionType,
            MortalityFeatures,
            get_risk_prediction_service,
        )

        service = get_risk_prediction_service()

        # Map admission type
        admission_map = {
            "elective": AdmissionType.ELECTIVE,
            "emergency": AdmissionType.EMERGENCY,
            "urgent": AdmissionType.URGENT,
            "transfer": AdmissionType.TRANSFER,
        }
        admission = admission_map.get(
            request.admission_type.lower(), AdmissionType.EMERGENCY
        )

        features = MortalityFeatures(
            age=request.age,
            admission_type=admission,
            charlson_score=request.charlson_score,
            elixhauser_score=request.elixhauser_score,
            icu_admission=request.icu_admission,
            mechanical_ventilation=request.mechanical_ventilation,
            vasopressor_use=request.vasopressor_use,
            creatinine=request.creatinine,
            bilirubin=request.bilirubin,
            albumin=request.albumin,
            platelets=request.platelets,
            inr=request.inr,
            pao2_fio2=request.pao2_fio2,
            glasgow_coma_scale=request.glasgow_coma_scale,
        )

        risk_score = service.assess_mortality_risk(request.patient_id, features)

        # Build contributing factors
        factors = []
        if request.icu_admission:
            factors.append({
                "name": "ICU Admission",
                "value": True,
                "contribution": "high",
                "direction": "increases",
            })
        if request.mechanical_ventilation:
            factors.append({
                "name": "Mechanical Ventilation",
                "value": True,
                "contribution": "high",
                "direction": "increases",
            })
        if request.charlson_score >= 5:
            factors.append({
                "name": "Charlson Score",
                "value": request.charlson_score,
                "contribution": "high",
                "direction": "increases",
            })
        if request.age >= 75:
            factors.append({
                "name": "Age",
                "value": request.age,
                "contribution": "medium",
                "direction": "increases",
            })

        # Build recommendations
        recommendations = []
        if risk_score.tier.value in ["high", "critical"]:
            recommendations.append("Ensure goals of care discussion documented")
            recommendations.append("Consider palliative care consult")
            if not request.icu_admission:
                recommendations.append("Monitor for ICU escalation criteria")

        processing_time = (time.perf_counter() - start_time) * 1000

        return RiskScoreResponse(
            request_id=request_id,
            patient_id=request.patient_id,
            risk_type="mortality",
            score=risk_score.score,
            score_raw=risk_score.score_raw,
            tier=risk_score.tier.value,
            percentile=risk_score.percentile,
            confidence=risk_score.confidence,
            calculated_at=risk_score.calculated_at,
            processing_time_ms=round(processing_time, 2),
            contributing_factors=factors,
            recommendations=recommendations,
        )

    except Exception as e:
        raise InternalError(
            message=f"Mortality prediction failed: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )


# ============================================================================
# Patient Risks Endpoint
# ============================================================================


@router.get(
    "/patient/{patient_id}/risks",
    response_model=PatientRisksResponse,
    summary="Get all risks for a patient",
    description="Retrieve all calculated risk scores for a patient.",
)
async def get_patient_risks(
    patient_id: str,
    include_history: bool = Query(default=False, description="Include risk history"),
) -> PatientRisksResponse:
    """Get all risk scores for a patient.

    Returns the most recent risk assessment including:
    - Readmission risk
    - Deterioration risk
    - Mortality risk
    - Contributing factors
    - Recommendations

    Args:
        patient_id: Patient identifier.
        include_history: Whether to include historical scores.

    Returns:
        PatientRisksResponse with all available risks.
    """
    try:
        from app.services.risk_prediction_service import get_risk_prediction_service

        service = get_risk_prediction_service()

        # Get risk history for this patient
        history = service.get_risk_history(patient_id, days=1)

        # Build response from latest scores
        assessment_id = str(uuid4())
        assessed_at = datetime.now(timezone.utc)
        overall_tier = "low"
        overall_score = 0.0

        readmission_risk = None
        deterioration_risk = None
        mortality_risk = None

        for rh in history:
            if rh.scores:
                latest = rh.scores[-1]
                risk_data = {
                    "score": latest.get("score", 0),
                    "tier": latest.get("tier", "low").value if hasattr(latest.get("tier"), "value") else latest.get("tier", "low"),
                    "timestamp": latest.get("timestamp", assessed_at).isoformat() if hasattr(latest.get("timestamp"), "isoformat") else str(latest.get("timestamp")),
                }

                if rh.risk_type.value == "readmission":
                    readmission_risk = risk_data
                elif rh.risk_type.value == "deterioration":
                    deterioration_risk = risk_data
                elif rh.risk_type.value == "mortality":
                    mortality_risk = risk_data

                # Track overall highest risk
                score = latest.get("score", 0)
                if score > overall_score:
                    overall_score = score
                    tier = latest.get("tier", "low")
                    overall_tier = tier.value if hasattr(tier, "value") else tier

        return PatientRisksResponse(
            patient_id=patient_id,
            assessment_id=assessment_id,
            assessed_at=assessed_at,
            overall_tier=overall_tier,
            overall_score=round(overall_score, 4),
            readmission_risk=readmission_risk,
            deterioration_risk=deterioration_risk,
            mortality_risk=mortality_risk,
            risk_factors=[],
            recommendations=[],
            model_versions={
                "readmission": "1.2.0",
                "deterioration": "2.0.0",
                "mortality": "1.0.5",
            },
            processing_time_ms=0.0,
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to retrieve patient risks: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )


# ============================================================================
# Models Endpoints
# ============================================================================


@router.get(
    "/models",
    response_model=ModelListResponse,
    summary="List available prediction models",
    description="Get a list of all registered prediction models.",
)
async def list_models() -> ModelListResponse:
    """List all available prediction models.

    Returns:
        ModelListResponse with model metadata.
    """
    try:
        from app.services.ml_model_service import get_ml_model_service

        service = get_ml_model_service()
        models = service.list_models()

        model_list = []
        for m in models:
            model_list.append({
                "model_id": m.model_id,
                "name": m.name,
                "version": m.version,
                "model_type": m.model_type.value,
                "prediction_type": m.prediction_type.value,
                "status": m.status.value,
                "description": m.description,
                "tags": m.tags,
                "feature_count": len(m.feature_names),
                "training_samples": m.training_samples,
                "created_at": m.created_at.isoformat(),
            })

        return ModelListResponse(total_models=len(model_list), models=model_list)

    except Exception as e:
        raise InternalError(
            message=f"Failed to list models: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )


@router.get(
    "/models/{model_id}/performance",
    response_model=ModelPerformanceResponse,
    summary="Get model performance metrics",
    description="Retrieve performance metrics for a specific model.",
)
async def get_model_performance(
    model_id: str,
    version: str | None = Query(default=None, description="Specific version"),
) -> ModelPerformanceResponse:
    """Get performance metrics for a model.

    Returns classification metrics including:
    - AUC-ROC and AUC-PR
    - Accuracy, precision, recall, F1
    - Calibration metrics
    - ROC and PR curves
    - Feature importance

    Args:
        model_id: Model identifier.
        version: Optional specific version.

    Returns:
        ModelPerformanceResponse with all metrics.
    """
    try:
        from app.services.ml_model_service import get_ml_model_service

        service = get_ml_model_service()
        performances = service.get_model_performance(model_id, version)

        if not performances:
            raise NotFoundError(
                message=f"No performance data found for model {model_id}",
                error_code=ErrorCode.NOT_FOUND,
            )

        perf = performances[0]  # Latest performance

        return ModelPerformanceResponse(
            model_id=perf.model_id,
            version=perf.version,
            evaluated_at=perf.evaluated_at,
            dataset_type=perf.dataset_type,
            sample_count=perf.sample_count,
            auc_roc=perf.auc_roc,
            auc_pr=perf.auc_pr,
            accuracy=perf.accuracy,
            precision=perf.precision,
            recall=perf.recall,
            f1=perf.f1,
            brier_score=perf.brier_score,
            calibration_slope=perf.calibration_slope,
            roc_curve={
                "fpr": perf.roc_curve_fpr,
                "tpr": perf.roc_curve_tpr,
            }
            if perf.roc_curve_fpr
            else None,
            pr_curve={
                "precision": perf.pr_curve_precision,
                "recall": perf.pr_curve_recall,
            }
            if perf.pr_curve_precision
            else None,
            calibration_curve={
                "prob_true": perf.calibration_prob_true,
                "prob_pred": perf.calibration_prob_pred,
            }
            if perf.calibration_prob_true
            else None,
            feature_importance=perf.feature_importance,
        )

    except NotFoundError:
        raise
    except Exception as e:
        raise InternalError(
            message=f"Failed to get model performance: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )


# ============================================================================
# Explain Endpoint
# ============================================================================


@router.post(
    "/explain",
    response_model=ExplainResponse,
    summary="Explain a prediction",
    description="Get SHAP-based explanation for a prediction.",
)
async def explain_prediction(request: ExplainRequest) -> ExplainResponse:
    """Get SHAP-based explanation for a prediction.

    Returns:
    - Feature contributions (SHAP values)
    - Waterfall chart data
    - Human-readable explanation

    Args:
        request: Patient ID and risk type to explain.

    Returns:
        ExplainResponse with feature contributions and explanation.
    """
    try:
        from app.services.risk_prediction_service import (
            RiskType,
            get_risk_prediction_service,
        )

        service = get_risk_prediction_service()

        # Map risk type
        risk_type_map = {
            "readmission": RiskType.READMISSION,
            "deterioration": RiskType.DETERIORATION,
            "mortality": RiskType.MORTALITY,
        }
        risk_type = risk_type_map.get(request.risk_type.lower())

        if not risk_type:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid risk type: {request.risk_type}. Must be one of: readmission, deterioration, mortality",
            )

        explanation = service.explain_prediction(request.patient_id, risk_type)

        if "error" in explanation:
            raise NotFoundError(
                message=explanation["error"],
                error_code=ErrorCode.NOT_FOUND,
            )

        # Build waterfall data for visualization
        contributions = explanation.get("feature_contributions", {})
        sorted_contributions = sorted(
            contributions.items(), key=lambda x: abs(x[1]), reverse=True
        )

        waterfall_data = []
        cumulative = explanation.get("base_value", 0.5)
        for feature, value in sorted_contributions:
            waterfall_data.append({
                "feature": feature,
                "value": round(value, 4),
                "cumulative": round(cumulative + value, 4),
            })
            cumulative += value

        return ExplainResponse(
            patient_id=request.patient_id,
            risk_type=request.risk_type,
            prediction=explanation.get("prediction", 0.5),
            base_value=explanation.get("base_value", 0.5),
            feature_contributions=contributions,
            explanation=explanation.get("explanation", ""),
            waterfall_data=waterfall_data,
        )

    except NotFoundError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise InternalError(
            message=f"Failed to explain prediction: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )


# ============================================================================
# Batch Prediction Endpoint
# ============================================================================


class BatchPredictionRequest(BaseModel):
    """Request for batch predictions."""

    model_id: str = Field(..., description="Model to use")
    patients: list[dict[str, Any]] = Field(..., description="List of patient features")


class BatchPredictionResponse(BaseModel):
    """Response from batch predictions."""

    request_id: str
    model_id: str
    total_predictions: int
    successful: int
    failed: int
    predictions: list[dict[str, Any]]
    processing_time_ms: float


@router.post(
    "/batch",
    response_model=BatchPredictionResponse,
    summary="Batch predictions",
    description="Run predictions for multiple patients.",
)
async def batch_predict(request: BatchPredictionRequest) -> BatchPredictionResponse:
    """Run batch predictions for multiple patients.

    Args:
        request: Model ID and list of patient features.

    Returns:
        BatchPredictionResponse with results for all patients.
    """
    start_time = time.perf_counter()
    request_id = str(uuid4())

    try:
        from app.services.ml_model_service import FeatureSet, get_ml_model_service

        service = get_ml_model_service()

        # Convert to FeatureSets
        feature_sets = []
        for patient in request.patients:
            patient_id = patient.get("patient_id", str(uuid4()))
            features = {k: v for k, v in patient.items() if k != "patient_id"}
            feature_sets.append(FeatureSet(patient_id=patient_id, features=features))

        # Run batch prediction
        result = service.predict_batch(request.model_id, feature_sets)

        # Convert predictions to dicts
        predictions = []
        for pred in result.predictions:
            predictions.append({
                "patient_id": pred.patient_id,
                "prediction": pred.prediction,
                "risk_tier": pred.risk_tier,
                "confidence": pred.confidence,
                "explanation": pred.explanation,
            })

        processing_time = (time.perf_counter() - start_time) * 1000

        return BatchPredictionResponse(
            request_id=request_id,
            model_id=request.model_id,
            total_predictions=result.total_predictions,
            successful=result.successful,
            failed=result.failed,
            predictions=predictions,
            processing_time_ms=round(processing_time, 2),
        )

    except KeyError as e:
        raise NotFoundError(
            message=f"Model not found: {str(e)}",
            error_code=ErrorCode.NOT_FOUND,
        )
    except Exception as e:
        raise InternalError(
            message=f"Batch prediction failed: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )


# ============================================================================
# Risk Scores List Endpoint (for dashboard)
# ============================================================================


class PatientRiskRow(BaseModel):
    """A single patient's risk summary for the dashboard table."""

    patient_id: str
    patient_name: str
    age: int
    department: str
    readmission_risk: dict[str, Any] | None = None
    deterioration_risk: dict[str, Any] | None = None
    mortality_risk: dict[str, Any] | None = None
    overall_tier: str
    overall_score: float
    trend: str | None = None
    last_updated: datetime


class RiskScoresListResponse(BaseModel):
    """Response with paginated patient risk scores."""

    total: int
    patients: list[PatientRiskRow]


@router.get(
    "/risk-scores",
    response_model=RiskScoresListResponse,
    summary="List patient risk scores",
    description="Get risk score summaries for all monitored patients.",
)
async def list_risk_scores(
    tier: str | None = Query(default=None, description="Filter by risk tier"),
    department: str | None = Query(default=None, description="Filter by department"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> RiskScoresListResponse:
    """List risk score summaries for all patients in the system.

    Returns a flat list of patients with their latest risk scores
    across readmission, deterioration, and mortality, plus an
    overall tier and trend.

    Args:
        tier: Optional filter by overall tier (low/medium/high/critical).
        department: Optional filter by department.
        limit: Max results to return.
        offset: Pagination offset.

    Returns:
        RiskScoresListResponse with patient rows.
    """
    try:
        from app.services.risk_prediction_service import (
            RiskType,
            get_risk_prediction_service,
        )

        service = get_risk_prediction_service()
        history_map = service._risk_history

        patients: list[PatientRiskRow] = []

        for pid, entries in history_map.items():
            if not entries:
                continue

            # Group latest entry per risk type
            latest_by_type: dict[str, dict[str, Any]] = {}
            for entry in entries:
                rt = entry.get("risk_type")
                rt_val = rt.value if hasattr(rt, "value") else str(rt)
                existing = latest_by_type.get(rt_val)
                entry_ts = entry.get("timestamp", datetime.min.replace(tzinfo=timezone.utc))
                if existing is None or entry_ts > existing.get("timestamp", datetime.min.replace(tzinfo=timezone.utc)):
                    latest_by_type[rt_val] = entry

            # Compute overall score = max of latest scores
            overall_score = 0.0
            overall_tier = "low"
            last_updated = datetime.min.replace(tzinfo=timezone.utc)

            risk_data: dict[str, dict[str, Any] | None] = {
                "readmission": None,
                "deterioration": None,
                "mortality": None,
            }

            for rt_val, entry in latest_by_type.items():
                score = entry.get("score", 0)
                entry_tier = entry.get("tier", "low")
                tier_str = entry_tier.value if hasattr(entry_tier, "value") else str(entry_tier)
                entry_ts = entry.get("timestamp", datetime.min.replace(tzinfo=timezone.utc))

                if rt_val in risk_data:
                    risk_data[rt_val] = {
                        "score": round(score, 4),
                        "tier": tier_str,
                        "score_raw": entry.get("score_raw"),
                    }

                if score > overall_score:
                    overall_score = score
                    overall_tier = tier_str
                if entry_ts > last_updated:
                    last_updated = entry_ts

            # Compute trend from history
            all_scores = sorted(entries, key=lambda x: x.get("timestamp", datetime.min.replace(tzinfo=timezone.utc)))
            if len(all_scores) >= 2:
                scores_list = [e.get("score", 0) for e in all_scores]
                slope = (scores_list[-1] - scores_list[0]) / len(scores_list)
                if slope > 0.02:
                    trend = "worsening"
                elif slope < -0.02:
                    trend = "improving"
                else:
                    trend = "stable"
            else:
                trend = "stable"

            # Filter by tier if requested
            if tier and overall_tier != tier:
                continue

            # Derive patient metadata from patient_id
            # In production these would come from a patient registry
            # For now, generate deterministic demo data from the ID
            pid_hash = hash(pid) % 10000
            demo_names = [
                "John Smith", "Mary Johnson", "Robert Williams", "Patricia Brown",
                "James Davis", "Linda Miller", "Michael Wilson", "Barbara Taylor",
                "David Anderson", "Susan Thomas", "Richard Jackson", "Dorothy White",
            ]
            demo_depts = [
                "Cardiology", "Internal Medicine", "ICU", "Surgery",
                "Geriatrics", "Oncology", "Pulmonology", "Neurology",
            ]
            name = demo_names[pid_hash % len(demo_names)]
            age = 40 + (pid_hash % 50)
            dept = demo_depts[pid_hash % len(demo_depts)]

            if department and dept != department:
                continue

            patients.append(
                PatientRiskRow(
                    patient_id=pid,
                    patient_name=name,
                    age=age,
                    department=dept,
                    readmission_risk=risk_data.get("readmission"),
                    deterioration_risk=risk_data.get("deterioration"),
                    mortality_risk=risk_data.get("mortality"),
                    overall_tier=overall_tier,
                    overall_score=round(overall_score, 4),
                    trend=trend,
                    last_updated=last_updated,
                )
            )

        # Sort by overall_score descending (highest risk first)
        patients.sort(key=lambda p: p.overall_score, reverse=True)
        total = len(patients)
        patients = patients[offset : offset + limit]

        return RiskScoresListResponse(total=total, patients=patients)

    except Exception as e:
        raise InternalError(
            message=f"Failed to list risk scores: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )


# ============================================================================
# Population Risk Endpoint (for dashboard overview)
# ============================================================================


class DepartmentRiskSummary(BaseModel):
    """Risk summary for a single department."""

    department: str
    patient_count: int
    avg_risk_score: float
    critical_count: int
    high_count: int


class PopulationRiskResponse(BaseModel):
    """Population-level risk overview for the dashboard."""

    total_patients: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    average_score: float
    worsening_count: int
    tier_distribution: list[dict[str, Any]]
    department_summary: list[DepartmentRiskSummary]


@router.get(
    "/population-risk",
    response_model=PopulationRiskResponse,
    summary="Get population-level risk overview",
    description="Aggregate risk statistics across all monitored patients.",
)
async def get_population_risk() -> PopulationRiskResponse:
    """Get population-level risk overview.

    Aggregates risk scores across all monitored patients and returns
    tier distribution, department breakdown, and trend counts.

    Returns:
        PopulationRiskResponse with aggregate statistics.
    """
    try:
        from app.services.risk_prediction_service import get_risk_prediction_service

        service = get_risk_prediction_service()
        history_map = service._risk_history

        tier_counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        dept_data: dict[str, dict[str, Any]] = {}
        scores: list[float] = []
        worsening_count = 0

        for pid, entries in history_map.items():
            if not entries:
                continue

            # Find latest per risk type, compute overall
            latest_by_type: dict[str, dict[str, Any]] = {}
            for entry in entries:
                rt = entry.get("risk_type")
                rt_val = rt.value if hasattr(rt, "value") else str(rt)
                existing = latest_by_type.get(rt_val)
                entry_ts = entry.get("timestamp", datetime.min.replace(tzinfo=timezone.utc))
                if existing is None or entry_ts > existing.get("timestamp", datetime.min.replace(tzinfo=timezone.utc)):
                    latest_by_type[rt_val] = entry

            overall_score = 0.0
            overall_tier = "low"
            for _, entry in latest_by_type.items():
                s = entry.get("score", 0)
                t = entry.get("tier", "low")
                t_str = t.value if hasattr(t, "value") else str(t)
                if s > overall_score:
                    overall_score = s
                    overall_tier = t_str

            scores.append(overall_score)
            tier_counts[overall_tier] = tier_counts.get(overall_tier, 0) + 1

            # Trend
            sorted_entries = sorted(entries, key=lambda x: x.get("timestamp", datetime.min.replace(tzinfo=timezone.utc)))
            if len(sorted_entries) >= 2:
                sl = [e.get("score", 0) for e in sorted_entries]
                slope = (sl[-1] - sl[0]) / len(sl)
                if slope > 0.02:
                    worsening_count += 1

            # Department
            pid_hash = hash(pid) % 10000
            demo_depts = [
                "Cardiology", "Internal Medicine", "ICU", "Surgery",
                "Geriatrics", "Oncology", "Pulmonology", "Neurology",
            ]
            dept = demo_depts[pid_hash % len(demo_depts)]

            if dept not in dept_data:
                dept_data[dept] = {"count": 0, "scores": [], "critical": 0, "high": 0}
            dept_data[dept]["count"] += 1
            dept_data[dept]["scores"].append(overall_score)
            if overall_tier == "critical":
                dept_data[dept]["critical"] += 1
            elif overall_tier == "high":
                dept_data[dept]["high"] += 1

        total = len(scores)
        avg_score = round(sum(scores) / total, 4) if total > 0 else 0.0

        tier_distribution = []
        for t in ["critical", "high", "medium", "low"]:
            count = tier_counts.get(t, 0)
            tier_distribution.append({
                "tier": t,
                "count": count,
                "percentage": round((count / total) * 100, 1) if total > 0 else 0,
            })

        department_summary = []
        for dept, data in sorted(dept_data.items()):
            department_summary.append(
                DepartmentRiskSummary(
                    department=dept,
                    patient_count=data["count"],
                    avg_risk_score=round(sum(data["scores"]) / len(data["scores"]), 4) if data["scores"] else 0,
                    critical_count=data["critical"],
                    high_count=data["high"],
                )
            )

        return PopulationRiskResponse(
            total_patients=total,
            critical_count=tier_counts.get("critical", 0),
            high_count=tier_counts.get("high", 0),
            medium_count=tier_counts.get("medium", 0),
            low_count=tier_counts.get("low", 0),
            average_score=avg_score,
            worsening_count=worsening_count,
            tier_distribution=tier_distribution,
            department_summary=department_summary,
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to get population risk: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )
