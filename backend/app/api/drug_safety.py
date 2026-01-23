"""Drug Safety API Endpoints.

Provides drug safety checking including contraindications,
warnings, pregnancy/lactation safety, and dosing guidelines.
"""

import time
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.services.drug_safety import (
    get_drug_safety_service,
    SafetyLevel,
)

router = APIRouter(prefix="/drug-safety", tags=["Drug Safety"])


# ============================================================================
# Request/Response Models
# ============================================================================


class PatientContext(BaseModel):
    """Patient context for safety checking."""

    age: int | None = Field(None, ge=0, le=150, description="Patient age in years")
    weight_kg: float | None = Field(None, ge=0, description="Patient weight in kg")
    conditions: list[str] = Field(default_factory=list, description="Active conditions")
    medications: list[str] = Field(default_factory=list, description="Current medications")
    allergies: list[str] = Field(default_factory=list, description="Known allergies")
    pregnant: bool = Field(default=False, description="Whether patient is pregnant")
    lactating: bool = Field(default=False, description="Whether patient is lactating")
    renal_impairment: bool = Field(default=False, description="Renal impairment present")
    hepatic_impairment: bool = Field(default=False, description="Hepatic impairment present")


class SafetyCheckRequest(BaseModel):
    """Request for drug safety check."""

    drug_name: str = Field(..., min_length=1, description="Drug name to check")
    patient: PatientContext = Field(default_factory=PatientContext, description="Patient context")


class ContraindicationResponse(BaseModel):
    """A contraindication entry."""

    condition: str
    severity: str
    rationale: str


class DosingGuidelineResponse(BaseModel):
    """A dosing guideline entry."""

    population: str
    adjustment: str
    reason: str


class SafetyCheckResponse(BaseModel):
    """Response from safety check."""

    request_id: str
    drug_name: str
    normalized_name: str
    overall_safety: str
    contraindications: list[ContraindicationResponse]
    warnings: list[str]
    black_box_warnings: list[str]
    dosing_guidelines: list[DosingGuidelineResponse]
    pregnancy_category: str | None
    lactation_safety: str | None
    adverse_effects: list[str]
    therapeutic_classes: list[str]
    processing_time_ms: float


class DrugProfileResponse(BaseModel):
    """Full drug safety profile."""

    drug_name: str
    generic_name: str
    drug_class: str
    contraindications: list[ContraindicationResponse]
    warnings: list[str]
    black_box_warnings: list[str]
    dosing_guidelines: list[DosingGuidelineResponse]
    pregnancy_category: str | None
    lactation_safety: str | None
    common_adverse_effects: list[str]
    serious_adverse_effects: list[str]
    max_daily_dose: str | None


class DrugSearchResponse(BaseModel):
    """Search results for drug profiles."""

    query: str
    total_results: int
    profiles: list[DrugProfileResponse]


class DrugSafetyStatsResponse(BaseModel):
    """Service statistics."""

    total_profiles: int
    categories: dict[str, int]


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "/check",
    response_model=SafetyCheckResponse,
    summary="Check drug safety",
    description="Check drug safety given patient context including conditions, medications, and demographics.",
)
async def check_drug_safety(request: SafetyCheckRequest) -> SafetyCheckResponse:
    start = time.time()
    service = get_drug_safety_service()

    result = service.check_safety(
        drug=request.drug_name,
        patient_conditions=request.patient.conditions or None,
        age=request.patient.age,
        pregnant=request.patient.pregnant,
        lactating=request.patient.lactating,
    )

    contraindications = [
        ContraindicationResponse(
            condition=cond,
            severity="high",
            rationale=rationale,
        )
        for cond, rationale in result.contraindicated_conditions
    ]

    # Pull black box warnings and dosing from profile if available
    black_box = result.profile.black_box_warnings if result.profile else []
    dosing = [
        DosingGuidelineResponse(
            population=d.population,
            adjustment=d.adjustment,
            reason=d.reason,
        )
        for d in (result.profile.dosing_guidelines if result.profile else [])
    ]
    therapeutic_classes = [result.profile.drug_class] if result.profile else []

    return SafetyCheckResponse(
        request_id=str(uuid4()),
        drug_name=request.drug_name,
        normalized_name=result.drug_name,
        overall_safety=result.overall_safety.value,
        contraindications=contraindications,
        warnings=result.warnings,
        black_box_warnings=black_box,
        dosing_guidelines=dosing,
        pregnancy_category=result.pregnancy_warning,
        lactation_safety=result.lactation_warning,
        adverse_effects=result.cautions,
        therapeutic_classes=therapeutic_classes,
        processing_time_ms=(time.time() - start) * 1000,
    )


@router.get(
    "/profile/{drug_name}",
    response_model=DrugProfileResponse,
    summary="Get drug safety profile",
    description="Get the full safety profile for a drug.",
)
async def get_drug_profile(drug_name: str) -> DrugProfileResponse:
    service = get_drug_safety_service()
    profile = service.get_profile(drug_name)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No safety profile found for '{drug_name}'",
        )

    return DrugProfileResponse(
        drug_name=profile.drug_name,
        generic_name=profile.generic_name,
        drug_class=profile.drug_class,
        contraindications=[
            ContraindicationResponse(
                condition=c.condition,
                severity=c.severity.value,
                rationale=c.rationale,
            )
            for c in profile.contraindications
        ],
        warnings=profile.warnings_precautions,
        black_box_warnings=profile.black_box_warnings,
        dosing_guidelines=[
            DosingGuidelineResponse(
                population=d.population,
                adjustment=d.adjustment,
                reason=d.reason,
            )
            for d in profile.dosing_guidelines
        ],
        pregnancy_category=profile.pregnancy_category.value if profile.pregnancy_category else None,
        lactation_safety=profile.lactation_safety.value if profile.lactation_safety else None,
        common_adverse_effects=profile.common_adverse_effects,
        serious_adverse_effects=profile.serious_adverse_effects,
        max_daily_dose=profile.max_daily_dose or None,
    )


@router.get(
    "/search",
    response_model=DrugSearchResponse,
    summary="Search drug profiles",
    description="Search for drug safety profiles by name.",
)
async def search_drug_profiles(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
) -> DrugSearchResponse:
    service = get_drug_safety_service()
    profiles = service.search_profiles(q, limit=limit)

    return DrugSearchResponse(
        query=q,
        total_results=len(profiles),
        profiles=[
            DrugProfileResponse(
                drug_name=p.drug_name,
                generic_name=p.generic_name,
                drug_class=p.drug_class,
                contraindications=[
                    ContraindicationResponse(
                        condition=c.condition,
                        severity=c.severity.value,
                        rationale=c.rationale,
                    )
                    for c in p.contraindications
                ],
                warnings=p.warnings_precautions,
                black_box_warnings=p.black_box_warnings,
                dosing_guidelines=[
                    DosingGuidelineResponse(
                        population=d.population,
                        adjustment=d.adjustment,
                        reason=d.reason,
                    )
                    for d in p.dosing_guidelines
                ],
                pregnancy_category=p.pregnancy_category.value if p.pregnancy_category else None,
                lactation_safety=p.lactation_safety.value if p.lactation_safety else None,
                common_adverse_effects=p.common_adverse_effects,
                serious_adverse_effects=p.serious_adverse_effects,
                max_daily_dose=p.max_daily_dose or None,
            )
            for p in profiles
        ],
    )


@router.get(
    "/stats",
    response_model=DrugSafetyStatsResponse,
    summary="Get service statistics",
)
async def get_drug_safety_stats() -> DrugSafetyStatsResponse:
    service = get_drug_safety_service()
    stats = service.get_stats()
    return DrugSafetyStatsResponse(
        total_profiles=stats.get("total_profiles", 0),
        categories=stats.get("categories", {}),
    )
