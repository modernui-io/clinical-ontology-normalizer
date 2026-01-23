"""Drug Safety API Endpoints.

Provides drug safety checking including contraindications,
warnings, pregnancy/lactation safety, and dosing guidelines.
"""

import time
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field, field_validator, model_validator

from app.api.errors import ErrorCode, InternalError, NotFoundError
from app.services.drug_safety import (
    get_drug_safety_service,
    SafetyLevel,
)
from app.services.terminology_cache import get_drug_cache

router = APIRouter(prefix="/drug-safety", tags=["Drug Safety"])


# ============================================================================
# Request/Response Models
# ============================================================================


class PatientContext(BaseModel):
    """Patient context for safety checking."""

    age: int | None = Field(None, ge=0, le=150, description="Patient age in years")
    weight_kg: float | None = Field(None, ge=0, le=700, description="Patient weight in kg")
    conditions: list[str] = Field(default_factory=list, description="Active conditions")
    medications: list[str] = Field(default_factory=list, description="Current medications")
    allergies: list[str] = Field(default_factory=list, description="Known allergies")
    pregnant: bool = Field(default=False, description="Whether patient is pregnant")
    lactating: bool = Field(default=False, description="Whether patient is lactating")
    renal_impairment: bool = Field(default=False, description="Renal impairment present")
    hepatic_impairment: bool = Field(default=False, description="Hepatic impairment present")

    @field_validator("conditions", "medications", "allergies")
    @classmethod
    def validate_string_lists(cls, v: list[str]) -> list[str]:
        cleaned = [s.strip() for s in v if s.strip()]
        if len(cleaned) != len(v):
            raise ValueError("List items must be non-empty strings")
        return cleaned


class SafetyCheckRequest(BaseModel):
    """Request for drug safety check."""

    drug_name: str = Field(..., min_length=1, description="Drug name to check")
    patient: PatientContext = Field(default_factory=PatientContext, description="Patient context")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "drug_name": "warfarin",
                    "patient": {
                        "age": 72,
                        "conditions": ["atrial fibrillation", "hypertension"],
                        "medications": ["lisinopril", "aspirin"],
                        "pregnant": False,
                        "renal_impairment": True,
                    },
                }
            ]
        }
    }


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
    offset: int = 0
    limit: int = 10
    has_more: bool = False
    profiles: list[DrugProfileResponse]


class DrugSafetyStatsResponse(BaseModel):
    """Service statistics."""

    total_profiles: int
    categories: dict[str, int]


class InteractionCheckRequest(BaseModel):
    """Request for drug interaction check."""

    medications: list[str] = Field(..., min_length=2, max_length=50, description="List of medications to check")

    @field_validator("medications")
    @classmethod
    def validate_medications(cls, v: list[str]) -> list[str]:
        cleaned = [s.strip() for s in v if s.strip()]
        if len(cleaned) < 2:
            raise ValueError("At least 2 medications are required for interaction checking")
        return cleaned


class InteractionResponse(BaseModel):
    """A single drug interaction."""

    drug_a: str
    drug_b: str
    severity: str
    description: str
    mechanism: str
    clinical_effect: str
    management: str


class InteractionCheckResponse(BaseModel):
    """Result of drug interaction check."""

    request_id: str
    drugs_checked: list[str]
    total_interactions: int
    major_count: int
    moderate_count: int
    minor_count: int
    interactions: list[InteractionResponse]
    processing_time_ms: float


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
    cache = get_drug_cache()
    cache_key = cache._make_key("drug_profile", drug_name.lower())
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    service = get_drug_safety_service()
    profile = service.get_profile(drug_name)

    if not profile:
        raise NotFoundError(
            message=f"No safety profile found for '{drug_name}'",
            error_code=ErrorCode.NOT_FOUND_RESOURCE,
        )

    result = DrugProfileResponse(
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
    cache.set(cache_key, result)
    return result


@router.get(
    "/search",
    response_model=DrugSearchResponse,
    summary="Search drug profiles",
    description="Search for drug safety profiles by name.",
)
async def search_drug_profiles(
    q: str = Query(..., min_length=2, description="Search query"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(10, ge=1, le=50, description="Max results per page"),
) -> DrugSearchResponse:
    cache = get_drug_cache()
    cache_key = cache._make_key("drug_search", q.lower(), offset=offset, limit=limit)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    service = get_drug_safety_service()
    profiles = service.search_profiles(q, limit=offset + limit + 1)
    total = len(profiles)
    page = profiles[offset:offset + limit]

    result = DrugSearchResponse(
        query=q,
        total_results=total,
        offset=offset,
        limit=limit,
        has_more=total > offset + limit,
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
            for p in page
        ],
    )
    cache.set(cache_key, result)
    return result


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


@router.post(
    "/interactions",
    response_model=InteractionCheckResponse,
    summary="Check drug interactions",
    description="Check for known drug-drug interactions among a list of medications.",
)
async def check_drug_interactions(request: InteractionCheckRequest) -> InteractionCheckResponse:
    start = time.time()
    service = get_drug_safety_service()

    result = service.check_interactions(request.medications)

    interactions = [
        InteractionResponse(
            drug_a=i.drug_a,
            drug_b=i.drug_b,
            severity=i.severity,
            description=i.description,
            mechanism=i.mechanism,
            clinical_effect=i.clinical_effect,
            management=i.management,
        )
        for i in result.interactions_found
    ]

    return InteractionCheckResponse(
        request_id=str(uuid4()),
        drugs_checked=result.drugs_checked,
        total_interactions=result.total_interactions,
        major_count=sum(1 for i in interactions if i.severity == "major"),
        moderate_count=sum(1 for i in interactions if i.severity == "moderate"),
        minor_count=sum(1 for i in interactions if i.severity == "minor"),
        interactions=interactions,
        processing_time_ms=(time.time() - start) * 1000,
    )
