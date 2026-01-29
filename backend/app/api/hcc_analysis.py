"""HCC Analysis API Endpoints.

Provides HCC (Hierarchical Condition Category) gap analysis
including RAF score calculation, capture opportunities, and
coding recommendations.
"""

from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field, field_validator

from app.api.errors import ErrorCode, NotFoundError
from app.services.hcc_analyzer import (
    get_hcc_analyzer_service,
    HCCCategory,
)
from app.services.terminology_cache import get_hcc_cache

router = APIRouter(prefix="/hcc-analysis", tags=["HCC Analysis"])


# ============================================================================
# Request/Response Models
# ============================================================================


class HCCAnalysisRequest(BaseModel):
    """Request for HCC gap analysis."""

    patient_id: str = Field(..., min_length=1, description="Patient identifier")
    icd10_codes: list[str] = Field(default_factory=list, description="Current ICD-10 codes")
    clinical_notes: str | None = Field(None, description="Clinical note text for NLP analysis")
    age: int | None = Field(None, ge=0, le=150, description="Patient age")
    is_institutional: bool = Field(False, description="Whether patient is in institutional setting")

    @field_validator("icd10_codes")
    @classmethod
    def validate_icd10_codes(cls, v: list[str]) -> list[str]:
        import re
        pattern = re.compile(r"^[A-Z]\d{2}(\.\d{1,4})?$")
        invalid = [c for c in v if not pattern.match(c.upper())]
        if invalid:
            raise ValueError(
                f"Invalid ICD-10 code format: {', '.join(invalid)}. "
                "Expected format: letter + 2 digits, optionally followed by . and 1-4 digits (e.g., E11, E11.65)"
            )
        return [c.upper() for c in v]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "patient_id": "P-12345",
                    "icd10_codes": ["E11.9", "I10", "E78.5"],
                    "clinical_notes": "Patient with poorly controlled type 2 diabetes, hypertension, and hyperlipidemia. Recent HbA1c 9.2%. Diabetic nephropathy suspected.",
                    "age": 68,
                    "is_institutional": False,
                }
            ]
        }
    }


class HCCEvidenceResponse(BaseModel):
    """Evidence supporting an HCC opportunity."""

    source: str
    text: str
    confidence: float


class HCCOpportunityResponse(BaseModel):
    """A potential HCC capture opportunity."""

    hcc_code: str
    hcc_description: str
    category: str
    gap_type: str
    confidence: str
    recommended_icd10: list[str]
    evidence: list[HCCEvidenceResponse]
    raf_impact: float
    coder_notes: str
    priority: int


class HCCAnalysisResponse(BaseModel):
    """Full HCC analysis result."""

    request_id: str
    patient_id: str
    current_raf_score: float
    potential_raf_score: float
    raf_gap: float
    captured_hccs: list[str]
    opportunities: list[HCCOpportunityResponse]
    priority_actions: list[str]
    total_revenue_impact: float | None
    processing_time_ms: float


class HCCDefinitionResponse(BaseModel):
    """An HCC definition."""

    hcc_code: str
    description: str
    category: str
    raf_weight: float
    icd10_codes: list[str]


class HCCMappingResponse(BaseModel):
    """ICD-10 to HCC mapping."""

    icd10_code: str
    hcc_code: str | None


class BatchMappingRequest(BaseModel):
    """Request for batch ICD-10 to HCC mapping."""

    icd10_codes: list[str] = Field(..., min_length=1, max_length=500, description="ICD-10 codes to map")

    @field_validator("icd10_codes")
    @classmethod
    def validate_codes(cls, v: list[str]) -> list[str]:
        return [c.upper().strip() for c in v if c.strip()]


class BatchMappingResponse(BaseModel):
    """Batch ICD-10 to HCC mapping result."""

    total_codes: int
    mapped_count: int
    unmapped_count: int
    mappings: list[HCCMappingResponse]


class HCCStatsResponse(BaseModel):
    """Service statistics."""

    total_hcc_codes: int
    total_icd10_mappings: int
    categories: dict[str, int]


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "/analyze",
    response_model=HCCAnalysisResponse,
    summary="Analyze HCC gaps",
    description="Perform HCC gap analysis for a patient based on current codes and clinical notes.",
)
async def analyze_hcc_gaps(request: HCCAnalysisRequest) -> HCCAnalysisResponse:
    start = time.time()
    service = get_hcc_analyzer_service()

    patient_context = {}
    if request.age:
        patient_context["age"] = request.age
    if request.is_institutional:
        patient_context["is_institutional"] = request.is_institutional

    result = service.analyze_patient(
        clinical_text=request.clinical_notes or "",
        current_icd10_codes=request.icd10_codes,
        patient_context=patient_context,
    )

    opportunities = []
    for i, opp in enumerate(result.opportunities):
        evidence = [
            HCCEvidenceResponse(
                source=e.source_type,
                text=e.source_text,
                confidence=e.confidence,
            )
            for e in (opp.evidence or [])
        ]
        recommended = [opp.recommended_icd10] if opp.recommended_icd10 else opp.supporting_icd10_codes
        opportunities.append(HCCOpportunityResponse(
            hcc_code=opp.hcc_code,
            hcc_description=opp.hcc_description,
            category=opp.category.value if opp.category else "",
            gap_type=opp.gap_type.value if opp.gap_type else "suspect",
            confidence=opp.capture_confidence.value if opp.capture_confidence else "low",
            recommended_icd10=recommended,
            evidence=evidence,
            raf_impact=opp.raf_value,
            coder_notes=opp.coder_notes,
            priority=i + 1,
        ))

    potential_raf = result.current_raf_score + result.total_raf_opportunity

    return HCCAnalysisResponse(
        request_id=str(uuid4()),
        patient_id=request.patient_id,
        current_raf_score=result.current_raf_score,
        potential_raf_score=potential_raf,
        raf_gap=result.total_raf_opportunity,
        captured_hccs=result.current_hccs,
        opportunities=opportunities,
        priority_actions=[opp.coder_notes for opp in result.opportunities[:5] if opp.coder_notes],
        total_revenue_impact=result.total_estimated_revenue,
        processing_time_ms=(time.time() - start) * 1000,
    )


@router.get(
    "/hcc/{hcc_code}",
    response_model=HCCDefinitionResponse,
    summary="Get HCC definition",
)
async def get_hcc_definition(hcc_code: str) -> HCCDefinitionResponse:
    cache = get_hcc_cache()
    cache_key = cache._make_key("hcc_def", hcc_code.upper())
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    service = get_hcc_analyzer_service()
    hcc_def = service.get_hcc_definition(hcc_code)

    if not hcc_def:
        raise NotFoundError(
            message=f"HCC code '{hcc_code}' not found",
            error_code=ErrorCode.NOT_FOUND_CONCEPT,
        )

    result = HCCDefinitionResponse(
        hcc_code=hcc_def.hcc_code,
        description=hcc_def.description,
        category=hcc_def.category.value if hcc_def.category else "",
        raf_weight=hcc_def.raf_community,
        icd10_codes=hcc_def.icd10_codes,
    )
    cache.set(cache_key, result)
    return result


@router.get(
    "/mapping/{icd10_code}",
    response_model=HCCMappingResponse,
    summary="Get ICD-10 to HCC mapping",
)
async def get_icd10_hcc_mapping(icd10_code: str) -> HCCMappingResponse:
    cache = get_hcc_cache()
    cache_key = cache._make_key("icd10_hcc_map", icd10_code.upper())
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    service = get_hcc_analyzer_service()
    hcc_code = service.get_icd10_to_hcc_mapping(icd10_code.upper())

    result = HCCMappingResponse(
        icd10_code=icd10_code.upper(),
        hcc_code=hcc_code,
    )
    cache.set(cache_key, result)
    return result


@router.post(
    "/mapping/batch",
    response_model=BatchMappingResponse,
    summary="Batch ICD-10 to HCC mapping",
    description="Map multiple ICD-10 codes to their HCC categories in a single request.",
)
async def batch_icd10_hcc_mapping(request: BatchMappingRequest) -> BatchMappingResponse:
    service = get_hcc_analyzer_service()
    mappings = []
    for code in request.icd10_codes:
        hcc_code = service.get_icd10_to_hcc_mapping(code)
        mappings.append(HCCMappingResponse(icd10_code=code, hcc_code=hcc_code))

    mapped = [m for m in mappings if m.hcc_code is not None]
    return BatchMappingResponse(
        total_codes=len(mappings),
        mapped_count=len(mapped),
        unmapped_count=len(mappings) - len(mapped),
        mappings=mappings,
    )


@router.get(
    "/codes",
    summary="List all HCC codes",
)
async def list_hcc_codes() -> dict[str, Any]:
    service = get_hcc_analyzer_service()
    codes = service.get_all_hcc_codes()
    return {"total": len(codes), "codes": codes}


@router.get(
    "/stats",
    response_model=HCCStatsResponse,
    summary="Get service statistics",
)
async def get_hcc_stats() -> HCCStatsResponse:
    service = get_hcc_analyzer_service()
    stats = service.get_stats()
    return HCCStatsResponse(
        total_hcc_codes=stats.get("total_hcc_codes", 0),
        total_icd10_mappings=stats.get("total_icd10_mappings", 0),
        categories=stats.get("categories", {}),
    )
