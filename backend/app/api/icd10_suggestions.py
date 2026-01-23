"""ICD-10 Code Suggestion API Endpoints.

Provides ICD-10-CM code suggestions based on clinical text,
diagnoses, and extracted information with CER citations.
"""

import time
from uuid import uuid4

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field, field_validator

from app.api.errors import ErrorCode, NotFoundError
from app.services.icd10_suggester import (
    get_icd10_suggester_service,
    CodeCategory,
)

router = APIRouter(prefix="/icd10-suggestions", tags=["ICD-10 Suggestions"])


# ============================================================================
# Request/Response Models
# ============================================================================


class ICD10SuggestionRequest(BaseModel):
    """Request for ICD-10 code suggestions."""

    text: str = Field(..., min_length=3, description="Clinical text to analyze")
    max_suggestions: int = Field(10, ge=1, le=50, description="Maximum suggestions")
    min_confidence: str = Field("low", description="Minimum confidence: high, medium, low")

    @field_validator("min_confidence")
    @classmethod
    def validate_confidence(cls, v: str) -> str:
        allowed = {"high", "medium", "low"}
        if v.lower() not in allowed:
            raise ValueError(
                f"Invalid confidence level '{v}'. Must be one of: high, medium, low"
            )
        return v.lower()

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "text": "Patient presents with chest pain radiating to left arm, diaphoresis, and shortness of breath. ECG shows ST elevation in leads V1-V4.",
                    "max_suggestions": 5,
                    "min_confidence": "medium",
                }
            ]
        }
    }


class CERCitationResponse(BaseModel):
    """Claim-Evidence-Reasoning for a code suggestion."""

    claim: str
    evidence: list[str]
    reasoning: str
    strength: str
    icd10_guidelines: list[str]


class CodeSuggestionResponse(BaseModel):
    """A single code suggestion."""

    code: str
    description: str
    confidence: str
    category: str
    specificity_note: str | None
    cer_citation: CERCitationResponse
    coding_tips: list[str]
    parent_code: str | None


class SuggestionResultResponse(BaseModel):
    """Full suggestion result."""

    request_id: str
    input_text: str
    total_suggestions: int
    suggestions: list[CodeSuggestionResponse]
    processing_time_ms: float


class ICD10CodeResponse(BaseModel):
    """An ICD-10 code entry."""

    code: str
    description: str
    category: str
    is_billable: bool
    parent_code: str | None
    synonyms: list[str]


class CodeSearchResponse(BaseModel):
    """Search results for ICD-10 codes."""

    query: str
    total_results: int
    offset: int = 0
    limit: int = 20
    has_more: bool = False
    codes: list[ICD10CodeResponse]


class ICD10StatsResponse(BaseModel):
    """Service statistics."""

    total_codes: int
    billable_codes: int
    categories: dict[str, int]


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "/suggest",
    response_model=SuggestionResultResponse,
    summary="Suggest ICD-10 codes",
    description="Analyze clinical text and suggest appropriate ICD-10-CM codes with CER citations.",
)
async def suggest_icd10_codes(request: ICD10SuggestionRequest) -> SuggestionResultResponse:
    start = time.time()
    service = get_icd10_suggester_service()

    result = service.suggest_codes(
        query=request.text,
        max_suggestions=request.max_suggestions,
    )

    suggestions = []
    for s in result.suggestions:
        cer = CERCitationResponse(
            claim=s.cer_citation.claim if s.cer_citation else "",
            evidence=s.cer_citation.evidence if s.cer_citation else [],
            reasoning=s.cer_citation.reasoning if s.cer_citation else "",
            strength=s.cer_citation.strength.value if s.cer_citation else "low",
            icd10_guidelines=s.cer_citation.icd10_guidelines if s.cer_citation else [],
        )
        specificity = None
        if s.more_specific_codes:
            specificity = f"More specific codes available: {', '.join(c[0] for c in s.more_specific_codes[:3])}"
        suggestions.append(CodeSuggestionResponse(
            code=s.code,
            description=s.description,
            confidence=s.confidence.value,
            category=s.category or "",
            specificity_note=specificity,
            cer_citation=cer,
            coding_tips=s.coding_guidance,
            parent_code=None,
        ))

    # Filter by min confidence
    confidence_order = {"high": 3, "medium": 2, "low": 1}
    min_level = confidence_order.get(request.min_confidence, 1)
    suggestions = [
        s for s in suggestions
        if confidence_order.get(s.confidence, 0) >= min_level
    ]

    return SuggestionResultResponse(
        request_id=str(uuid4()),
        input_text=request.text[:200],
        total_suggestions=len(suggestions),
        suggestions=suggestions,
        processing_time_ms=(time.time() - start) * 1000,
    )


@router.get(
    "/code/{code}",
    response_model=ICD10CodeResponse,
    summary="Get ICD-10 code details",
)
async def get_icd10_code(code: str) -> ICD10CodeResponse:
    service = get_icd10_suggester_service()
    icd_code = service.get_code(code.upper())

    if not icd_code:
        raise NotFoundError(
            message=f"ICD-10 code '{code}' not found",
            error_code=ErrorCode.NOT_FOUND_CONCEPT,
        )

    return ICD10CodeResponse(
        code=icd_code.code,
        description=icd_code.description,
        category=icd_code.category.value if icd_code.category else "",
        is_billable=icd_code.is_billable,
        parent_code=icd_code.parent_code,
        synonyms=icd_code.synonyms,
    )


@router.get(
    "/search",
    response_model=CodeSearchResponse,
    summary="Search ICD-10 codes",
    description="Search ICD-10 codes by description or code prefix.",
)
async def search_icd10_codes(
    q: str = Query(..., min_length=2, description="Search query"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Max results per page"),
) -> CodeSearchResponse:
    service = get_icd10_suggester_service()
    # Fetch one extra to determine has_more
    codes = service.search_codes(q, limit=offset + limit + 1)
    total = len(codes)
    page = codes[offset:offset + limit]

    return CodeSearchResponse(
        query=q,
        total_results=total,
        offset=offset,
        limit=limit,
        has_more=total > offset + limit,
        codes=[
            ICD10CodeResponse(
                code=c.code,
                description=c.description,
                category=c.category.value if c.category else "",
                is_billable=c.is_billable,
                parent_code=c.parent_code,
                synonyms=c.synonyms,
            )
            for c in page
        ],
    )


@router.get(
    "/stats",
    response_model=ICD10StatsResponse,
    summary="Get service statistics",
)
async def get_icd10_stats() -> ICD10StatsResponse:
    service = get_icd10_suggester_service()
    stats = service.get_stats()
    return ICD10StatsResponse(
        total_codes=stats.get("total_codes", 0),
        billable_codes=stats.get("billable_codes", 0),
        categories=stats.get("categories", {}),
    )
