"""CPT Code Suggestion API Endpoints.

Provides CPT code suggestions for procedures and E/M services
with documentation requirements and CER citations.
"""

import time
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field, field_validator

from app.services.cpt_suggester import (
    get_cpt_suggester_service,
    check_bundling,
    CPTCategory,
)
from app.services.terminology_cache import get_cpt_cache

router = APIRouter(prefix="/cpt-suggestions", tags=["CPT Suggestions"])


# ============================================================================
# Request/Response Models
# ============================================================================


class CPTSuggestionRequest(BaseModel):
    """Request for CPT code suggestions."""

    text: str = Field(..., min_length=3, description="Clinical/procedure text to analyze")
    max_suggestions: int = Field(10, ge=1, le=50, description="Maximum suggestions")
    include_em: bool = Field(True, description="Include E/M code analysis")


class EMLevelRequest(BaseModel):
    """Request for E/M level calculation."""

    time_spent_minutes: int | None = Field(None, ge=1, le=480, description="Total time in minutes")
    is_new_patient: bool = Field(False, description="Whether this is a new patient")
    setting: str = Field("office", description="Setting: office, inpatient, emergency")
    mdm_elements: dict | None = Field(None, description="MDM element assessments")

    @field_validator("setting")
    @classmethod
    def validate_setting(cls, v: str) -> str:
        allowed = {"office", "inpatient", "emergency"}
        if v.lower() not in allowed:
            raise ValueError(
                f"Invalid setting '{v}'. Must be one of: office, inpatient, emergency"
            )
        return v.lower()


class CERCitationResponse(BaseModel):
    """Claim-Evidence-Reasoning for a code suggestion."""

    claim: str
    evidence: list[str]
    reasoning: str
    strength: str


class DocumentationRequirementResponse(BaseModel):
    """Documentation needed for a code."""

    element: str
    required: bool
    description: str


class CPTSuggestionResponse(BaseModel):
    """A single CPT code suggestion."""

    code: str
    description: str
    confidence: str
    category: str
    rvu_work: float | None
    rvu_total: float | None
    cer_citation: CERCitationResponse
    documentation_requirements: list[DocumentationRequirementResponse]
    coding_tips: list[str]


class CPTSuggestionResultResponse(BaseModel):
    """Full suggestion result."""

    request_id: str
    input_text: str
    total_suggestions: int
    suggestions: list[CPTSuggestionResponse]
    documentation_gaps: list[str]
    processing_time_ms: float


class EMLevelResponse(BaseModel):
    """E/M level calculation result."""

    request_id: str
    recommended_code: str
    recommended_level: int
    mdm_complexity: str
    time_based_code: str | None
    documentation_elements: dict[str, bool]
    rationale: str
    processing_time_ms: float


class CPTCodeResponse(BaseModel):
    """A CPT code entry."""

    code: str
    description: str
    category: str
    rvu_work: float | None
    rvu_total: float | None


class CPTSearchResponse(BaseModel):
    """Search results for CPT codes."""

    query: str
    total_results: int
    offset: int = 0
    limit: int = 20
    has_more: bool = False
    codes: list[CPTCodeResponse]


class CPTStatsResponse(BaseModel):
    """Service statistics."""

    total_codes: int
    categories: dict[str, int]


class BundlingCheckRequest(BaseModel):
    """Request for CPT bundling check."""

    cpt_codes: list[str] = Field(..., min_length=2, max_length=50, description="CPT codes to check")


class BundlingRuleResponse(BaseModel):
    """A bundling rule match."""

    comprehensive_code: str
    comprehensive_description: str
    component_codes: list[str]
    component_descriptions: list[str]
    rationale: str


class BundlingCheckResponse(BaseModel):
    """Result of bundling analysis."""

    request_id: str
    codes_checked: list[str]
    bundling_opportunities: list[BundlingRuleResponse]
    unbundling_alerts: list[BundlingRuleResponse]
    total_issues: int
    processing_time_ms: float


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "/suggest",
    response_model=CPTSuggestionResultResponse,
    summary="Suggest CPT codes",
    description="Analyze clinical/procedure text and suggest appropriate CPT codes.",
)
async def suggest_cpt_codes(request: CPTSuggestionRequest) -> CPTSuggestionResultResponse:
    start = time.time()
    service = get_cpt_suggester_service()

    result = service.suggest_codes_from_text(
        clinical_text=request.text,
        max_suggestions=request.max_suggestions,
    )

    suggestions = []
    for s in result.suggestions:
        cer = CERCitationResponse(
            claim=s.rationale,
            evidence=[s.evidence_text] if s.evidence_text else [],
            reasoning=s.rationale,
            strength="medium" if s.confidence > 0.6 else "low",
        )
        suggestions.append(CPTSuggestionResponse(
            code=s.code,
            description=s.description,
            confidence=f"{s.confidence:.0%}",
            category=s.category,
            rvu_work=s.work_rvu,
            rvu_total=None,
            cer_citation=cer,
            documentation_requirements=[],
            coding_tips=[],
        ))

    return CPTSuggestionResultResponse(
        request_id=str(uuid4()),
        input_text=request.text[:200],
        total_suggestions=len(suggestions),
        suggestions=suggestions,
        documentation_gaps=[],
        processing_time_ms=(time.time() - start) * 1000,
    )


@router.post(
    "/em-level",
    response_model=EMLevelResponse,
    summary="Calculate E/M level",
    description="Calculate appropriate E/M code level from clinical note text.",
)
async def calculate_em_level(request: EMLevelRequest) -> EMLevelResponse:
    start = time.time()
    service = get_cpt_suggester_service()

    result = service.calculate_em_level(
        time_spent_minutes=request.time_spent_minutes,
        mdm_elements=request.mdm_elements,
        is_new_patient=request.is_new_patient,
        setting=request.setting,
    )

    return EMLevelResponse(
        request_id=str(uuid4()),
        recommended_code=result.code,
        recommended_level=int(result.code[-1]) if result.code and result.code[-1].isdigit() else 0,
        mdm_complexity=result.mdm_level or "unknown",
        time_based_code=result.code if result.calculation_method == "time" else None,
        documentation_elements={},
        rationale=result.rationale,
        processing_time_ms=(time.time() - start) * 1000,
    )


@router.get(
    "/search",
    response_model=CPTSearchResponse,
    summary="Search CPT codes",
)
async def search_cpt_codes(
    q: str = Query(..., min_length=2, description="Search query"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Max results per page"),
) -> CPTSearchResponse:
    cache = get_cpt_cache()
    cache_key = cache._make_key("cpt_search", q.lower(), offset=offset, limit=limit)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    service = get_cpt_suggester_service()
    codes = service.search_codes(q, limit=offset + limit + 1)
    total = len(codes)
    page = codes[offset:offset + limit]

    result = CPTSearchResponse(
        query=q,
        total_results=total,
        offset=offset,
        limit=limit,
        has_more=total > offset + limit,
        codes=[
            CPTCodeResponse(
                code=c.code,
                description=c.description,
                category=c.category.value if c.category else "",
                rvu_work=c.work_rvu,
                rvu_total=None,
            )
            for c in page
        ],
    )
    cache.set(cache_key, result)
    return result


@router.get(
    "/stats",
    response_model=CPTStatsResponse,
    summary="Get service statistics",
)
async def get_cpt_stats() -> CPTStatsResponse:
    service = get_cpt_suggester_service()
    stats = service.get_stats()
    return CPTStatsResponse(
        total_codes=stats.get("total_codes", 0),
        categories=stats.get("categories", {}),
    )


@router.post(
    "/bundling-check",
    response_model=BundlingCheckResponse,
    summary="Check CPT code bundling",
    description="Analyze CPT codes for bundling opportunities and unbundling alerts.",
)
async def check_cpt_bundling(request: BundlingCheckRequest) -> BundlingCheckResponse:
    start = time.time()
    result = check_bundling(request.cpt_codes)

    opportunities = [
        BundlingRuleResponse(
            comprehensive_code=r.comprehensive_code,
            comprehensive_description=r.comprehensive_desc,
            component_codes=r.component_codes,
            component_descriptions=r.component_descs,
            rationale=r.rationale,
        )
        for r in result.bundling_opportunities
    ]
    alerts = [
        BundlingRuleResponse(
            comprehensive_code=r.comprehensive_code,
            comprehensive_description=r.comprehensive_desc,
            component_codes=r.component_codes,
            component_descriptions=r.component_descs,
            rationale=r.rationale,
        )
        for r in result.unbundling_alerts
    ]

    return BundlingCheckResponse(
        request_id=str(uuid4()),
        codes_checked=result.codes_checked,
        bundling_opportunities=opportunities,
        unbundling_alerts=alerts,
        total_issues=len(opportunities) + len(alerts),
        processing_time_ms=(time.time() - start) * 1000,
    )
