"""Risk Assessment API endpoints.

Provides:
- POST /risk/mortality - Calculate mortality risk from clinical features
- GET /risk/mortality/{patient_id} - Get stored mortality risk for a patient
- POST /risk/charlson - Calculate Charlson Comorbidity Index from ICD-10 codes
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

def _get_risk_imports():
    """Lazy import to avoid loading sklearn at module level."""
    from app.services.risk_prediction_service import (
        AdmissionType,
        MortalityFeatures,
        calculate_charlson_index,
        get_risk_prediction_service,
    )
    return AdmissionType, MortalityFeatures, calculate_charlson_index, get_risk_prediction_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/risk", tags=["risk"])


# =============================================================================
# Request/Response Models
# =============================================================================


class MortalityRiskRequest(BaseModel):
    """Request to calculate mortality risk."""

    patient_id: str = Field(..., description="Patient identifier")
    age: int = Field(..., ge=0, le=120, description="Patient age")
    admission_type: str = Field(default="emergency", description="Admission type: elective, emergency, urgent, transfer")
    charlson_score: int = Field(default=0, ge=0, description="Charlson Comorbidity Index")
    elixhauser_score: int = Field(default=0, description="Elixhauser Comorbidity Index")
    icu_admission: bool = Field(default=False, description="ICU admission")
    mechanical_ventilation: bool = Field(default=False)
    vasopressor_use: bool = Field(default=False)
    creatinine: float | None = Field(None, description="Creatinine (mg/dL)")
    bilirubin: float | None = Field(None, description="Bilirubin (mg/dL)")
    albumin: float | None = Field(None, description="Albumin (g/dL)")
    platelets: float | None = Field(None, description="Platelets (K/uL)")
    inr: float | None = Field(None, description="INR")

    class Config:
        json_schema_extra = {
            "example": {
                "patient_id": "P12345",
                "age": 72,
                "admission_type": "emergency",
                "charlson_score": 4,
                "elixhauser_score": 3,
                "icu_admission": True,
                "mechanical_ventilation": False,
                "creatinine": 2.1,
            }
        }


class MortalityRiskResponse(BaseModel):
    """Mortality risk assessment result."""

    patient_id: str
    risk_score: float = Field(..., description="Mortality probability (0-1)")
    risk_tier: str = Field(..., description="Risk tier: low, medium, high, critical")
    confidence: float = Field(..., description="Prediction confidence")
    charlson_score: int
    elixhauser_score: int
    percentile: float | None = Field(None, description="Population percentile")


class CharlsonRequest(BaseModel):
    """Request to calculate Charlson Comorbidity Index."""

    icd10_codes: list[str] = Field(..., description="List of ICD-10-CM codes")

    class Config:
        json_schema_extra = {
            "example": {
                "icd10_codes": ["E11.9", "I10", "N18.3", "J44.1"]
            }
        }


class CharlsonResponse(BaseModel):
    """Charlson Comorbidity Index result."""

    score: int = Field(..., description="Charlson Comorbidity Index score")
    conditions_matched: int = Field(..., description="Number of conditions matched")
    icd10_codes_provided: int


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/mortality", response_model=MortalityRiskResponse)
async def calculate_mortality_risk(request: MortalityRiskRequest) -> MortalityRiskResponse:
    """Calculate mortality risk for a patient.

    Uses Charlson and Elixhauser comorbidity indices combined with
    clinical features to predict mortality risk. Returns a risk
    score (0-1), tier classification, and confidence level.
    """
    AdmissionType, MortalityFeatures, _, get_risk_prediction_service = _get_risk_imports()

    try:
        admission = AdmissionType(request.admission_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid admission_type: {request.admission_type}. Must be one of: elective, emergency, urgent, transfer",
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
    )

    service = get_risk_prediction_service()
    result = service.assess_mortality_risk(request.patient_id, features)

    return MortalityRiskResponse(
        patient_id=request.patient_id,
        risk_score=result.score,
        risk_tier=result.tier.value,
        confidence=result.confidence,
        charlson_score=request.charlson_score,
        elixhauser_score=request.elixhauser_score,
        percentile=result.percentile,
    )


@router.get("/mortality/{patient_id}")
async def get_mortality_risk(patient_id: str) -> dict[str, Any]:
    """Get the most recent mortality risk assessment for a patient.

    Returns the stored risk score from the last assessment, or 404
    if no assessment has been performed for this patient.
    """
    _, _, _, get_risk_prediction_service = _get_risk_imports()
    service = get_risk_prediction_service()
    history = service.get_risk_history(patient_id, risk_type="mortality")

    if not history:
        raise HTTPException(
            status_code=404,
            detail=f"No mortality risk assessment found for patient '{patient_id}'",
        )

    latest = history[0]
    return {
        "patient_id": patient_id,
        "risk_score": latest.get("score"),
        "risk_tier": latest.get("tier"),
        "assessed_at": latest.get("timestamp"),
    }


@router.post("/charlson", response_model=CharlsonResponse)
async def calculate_charlson(request: CharlsonRequest) -> CharlsonResponse:
    """Calculate Charlson Comorbidity Index from ICD-10 codes.

    Maps ICD-10-CM codes to Charlson comorbidity categories and
    computes the weighted index score.
    """
    _, _, calculate_charlson_index, _ = _get_risk_imports()
    score = calculate_charlson_index(request.icd10_codes)

    return CharlsonResponse(
        score=score,
        conditions_matched=min(score, len(request.icd10_codes)),
        icd10_codes_provided=len(request.icd10_codes),
    )
