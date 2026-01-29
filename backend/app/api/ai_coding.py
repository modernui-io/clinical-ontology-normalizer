"""AI-Powered Auto-Coding API endpoints.

This module provides REST API endpoints for AI-powered clinical code suggestions.

Endpoints:
- POST /api/ai-coding/suggest - Get code suggestions for clinical text
- POST /api/ai-coding/validate - Validate a set of codes
- POST /api/ai-coding/hcc - Calculate HCC risk scores
- GET /api/ai-coding/rules - Get coding rules and guidelines
- GET /api/ai-coding/stats - Get service statistics
- GET /api/ai-coding/code/{code} - Get details for a specific code
- GET /api/ai-coding/search - Search for codes
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any

from app.services.ai_coding_service import (
    get_ai_coding_service,
    CodeType,
    ConfidenceLevel,
    CodingOpportunityType,
)

router = APIRouter(prefix="/ai-coding", tags=["AI Coding"])


# ============================================================================
# Request/Response Models
# ============================================================================

class SuggestCodesRequest(BaseModel):
    """Request for code suggestions."""

    clinical_text: str = Field(
        ...,
        min_length=10,
        description="Clinical documentation text to analyze"
    )
    max_diagnosis_codes: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of diagnosis codes to suggest"
    )
    max_procedure_codes: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of procedure codes to suggest"
    )
    include_hcc: bool = Field(
        default=True,
        description="Whether to include HCC risk analysis"
    )
    encounter_context: dict[str, Any] | None = Field(
        default=None,
        description="Optional encounter context (new_patient, setting, etc.)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "clinical_text": "Patient is a 65 year old male with history of type 2 diabetes mellitus with diabetic nephropathy, hypertension, and COPD. Labs show A1c 8.2%, creatinine 1.8. Patient reports increased shortness of breath. Chest x-ray ordered.",
                    "max_diagnosis_codes": 10,
                    "max_procedure_codes": 5,
                    "include_hcc": True,
                    "encounter_context": {
                        "new_patient": False,
                        "setting": "office"
                    }
                }
            ]
        }
    }


class EvidenceSnippetResponse(BaseModel):
    """Evidence snippet from clinical text."""

    text: str
    start_offset: int
    end_offset: int
    relevance_score: float
    highlight_terms: list[str]


class CodeSuggestionResponse(BaseModel):
    """A suggested medical code."""

    code: str
    code_type: str
    description: str
    confidence: str
    confidence_score: float
    evidence_snippets: list[EvidenceSnippetResponse]
    match_reason: str
    category: str
    is_billable: bool
    parent_code: str | None
    more_specific_codes: list[tuple[str, str]]
    related_codes: list[tuple[str, str]]
    hcc_code: str | None
    hcc_description: str | None
    raf_value: float
    coding_tips: list[str]
    use_additional_code: str | None
    code_first: str | None


class CodingOpportunityResponse(BaseModel):
    """A coding opportunity."""

    opportunity_type: str
    current_code: str | None
    suggested_code: str | None
    description: str
    impact: str
    evidence_text: str
    priority: str


class ValidationIssueResponse(BaseModel):
    """A validation issue."""

    issue_type: str
    severity: str
    codes_involved: list[str]
    message: str
    suggestion: str


class HCCDetailResponse(BaseModel):
    """HCC detail information."""

    hcc_code: str
    icd10_code: str
    icd10_description: str
    raf_value: float


class HCCRiskResponse(BaseModel):
    """HCC risk calculation result."""

    total_raf_score: float
    hcc_codes: list[str]
    hcc_details: list[HCCDetailResponse]
    estimated_annual_revenue: float
    opportunities: list[CodingOpportunityResponse]


class SuggestCodesResponse(BaseModel):
    """Response with code suggestions."""

    request_id: str
    text_length: int
    analysis_timestamp: str
    processing_time_ms: float
    diagnosis_codes: list[CodeSuggestionResponse]
    procedure_codes: list[CodeSuggestionResponse]
    coding_opportunities: list[CodingOpportunityResponse]
    validation_issues: list[ValidationIssueResponse]
    hcc_analysis: HCCRiskResponse | None
    em_code: CodeSuggestionResponse | None
    em_rationale: str
    total_diagnosis_suggestions: int
    total_procedure_suggestions: int
    high_confidence_count: int


class ValidateCodesRequest(BaseModel):
    """Request to validate codes."""

    diagnosis_codes: list[str] = Field(
        default_factory=list,
        description="List of ICD-10 diagnosis codes to validate"
    )
    procedure_codes: list[str] = Field(
        default_factory=list,
        description="List of CPT procedure codes to validate"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "diagnosis_codes": ["E11.21", "I10", "J44.9"],
                    "procedure_codes": ["99214", "93000", "71046"]
                }
            ]
        }
    }


class ValidateCodesResponse(BaseModel):
    """Response from code validation."""

    is_valid: bool
    issues: list[ValidationIssueResponse]
    summary: str


class CalculateHCCRequest(BaseModel):
    """Request to calculate HCC risk."""

    icd10_codes: list[str] = Field(
        ...,
        min_length=1,
        description="List of ICD-10 diagnosis codes"
    )
    clinical_text: str | None = Field(
        default=None,
        description="Optional clinical text for opportunity analysis"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "icd10_codes": ["E11.21", "I50.22", "N18.4", "J44.9"],
                    "clinical_text": "Patient has diabetes with nephropathy, heart failure, CKD stage 4, and COPD."
                }
            ]
        }
    }


class CodingRuleResponse(BaseModel):
    """A coding rule or guideline."""

    rule_id: str
    category: str
    title: str
    description: str
    codes_affected: list[str]
    examples: list[str]
    source: str


class CodingRulesResponse(BaseModel):
    """Response with coding rules."""

    rules: list[CodingRuleResponse]
    total_count: int


class ServiceStatsResponse(BaseModel):
    """Service statistics."""

    total_icd10_codes: int
    total_cpt_codes: int
    total_icd10_synonyms: int
    total_cpt_synonyms: int
    hcc_mappings: int


class CodeDetailsResponse(BaseModel):
    """Details for a specific code."""

    code: str
    description: str
    synonyms: list[str]
    category: str | None
    is_billable: bool | None
    hcc_code: str | None
    raf_value: float | None


class CodeSearchRequest(BaseModel):
    """Request to search for codes."""

    query: str = Field(..., min_length=2, description="Search query")
    code_type: str = Field(default="ICD10", description="Code type: ICD10 or CPT")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum results")


class CodeSearchResponse(BaseModel):
    """Response from code search."""

    results: list[CodeDetailsResponse]
    total_count: int


# ============================================================================
# Helper Functions
# ============================================================================

def _convert_evidence_snippet(snippet) -> EvidenceSnippetResponse:
    """Convert EvidenceSnippet to response model."""
    return EvidenceSnippetResponse(
        text=snippet.text,
        start_offset=snippet.start_offset,
        end_offset=snippet.end_offset,
        relevance_score=snippet.relevance_score,
        highlight_terms=snippet.highlight_terms,
    )


def _convert_code_suggestion(suggestion) -> CodeSuggestionResponse:
    """Convert CodeSuggestion to response model."""
    return CodeSuggestionResponse(
        code=suggestion.code,
        code_type=suggestion.code_type.value,
        description=suggestion.description,
        confidence=suggestion.confidence.value,
        confidence_score=suggestion.confidence_score,
        evidence_snippets=[_convert_evidence_snippet(e) for e in suggestion.evidence_snippets],
        match_reason=suggestion.match_reason,
        category=suggestion.category,
        is_billable=suggestion.is_billable,
        parent_code=suggestion.parent_code,
        more_specific_codes=suggestion.more_specific_codes,
        related_codes=suggestion.related_codes,
        hcc_code=suggestion.hcc_code,
        hcc_description=suggestion.hcc_description,
        raf_value=suggestion.raf_value,
        coding_tips=suggestion.coding_tips,
        use_additional_code=suggestion.use_additional_code,
        code_first=suggestion.code_first,
    )


def _convert_coding_opportunity(opportunity) -> CodingOpportunityResponse:
    """Convert CodingOpportunity to response model."""
    return CodingOpportunityResponse(
        opportunity_type=opportunity.opportunity_type.value,
        current_code=opportunity.current_code,
        suggested_code=opportunity.suggested_code,
        description=opportunity.description,
        impact=opportunity.impact,
        evidence_text=opportunity.evidence_text,
        priority=opportunity.priority,
    )


def _convert_validation_issue(issue) -> ValidationIssueResponse:
    """Convert ValidationIssue to response model."""
    return ValidationIssueResponse(
        issue_type=issue.issue_type,
        severity=issue.severity,
        codes_involved=issue.codes_involved,
        message=issue.message,
        suggestion=issue.suggestion,
    )


def _convert_hcc_risk(result) -> HCCRiskResponse:
    """Convert HCCRiskResult to response model."""
    return HCCRiskResponse(
        total_raf_score=result.total_raf_score,
        hcc_codes=result.hcc_codes,
        hcc_details=[
            HCCDetailResponse(
                hcc_code=d['hcc_code'],
                icd10_code=d['icd10_code'],
                icd10_description=d['icd10_description'],
                raf_value=d['raf_value'],
            )
            for d in result.hcc_details
        ],
        estimated_annual_revenue=result.estimated_annual_revenue,
        opportunities=[_convert_coding_opportunity(o) for o in result.opportunities],
    )


# ============================================================================
# API Endpoints
# ============================================================================

@router.post(
    "/suggest",
    response_model=SuggestCodesResponse,
    summary="Suggest codes for clinical text",
    description="Analyze clinical documentation and suggest ICD-10 and CPT codes with confidence scores and evidence."
)
async def suggest_codes(request: SuggestCodesRequest) -> SuggestCodesResponse:
    """Get code suggestions for clinical text.

    This endpoint analyzes clinical documentation using TF-IDF text matching
    and pattern recognition to suggest appropriate medical codes.

    Features:
    - ICD-10-CM diagnosis code suggestions
    - CPT procedure code suggestions
    - E/M level determination
    - HCC risk analysis
    - Evidence snippets from the clinical text
    - Coding opportunities identification
    """
    service = get_ai_coding_service()

    result = service.suggest_codes(
        clinical_text=request.clinical_text,
        max_diagnosis_codes=request.max_diagnosis_codes,
        max_procedure_codes=request.max_procedure_codes,
        include_hcc=request.include_hcc,
        encounter_context=request.encounter_context,
    )

    return SuggestCodesResponse(
        request_id=result.request_id,
        text_length=result.text_length,
        analysis_timestamp=result.analysis_timestamp,
        processing_time_ms=result.processing_time_ms,
        diagnosis_codes=[_convert_code_suggestion(s) for s in result.diagnosis_codes],
        procedure_codes=[_convert_code_suggestion(s) for s in result.procedure_codes],
        coding_opportunities=[_convert_coding_opportunity(o) for o in result.coding_opportunities],
        validation_issues=[_convert_validation_issue(i) for i in result.validation_issues],
        hcc_analysis=_convert_hcc_risk(result.hcc_analysis) if result.hcc_analysis else None,
        em_code=_convert_code_suggestion(result.em_code) if result.em_code else None,
        em_rationale=result.em_rationale,
        total_diagnosis_suggestions=result.total_diagnosis_suggestions,
        total_procedure_suggestions=result.total_procedure_suggestions,
        high_confidence_count=result.high_confidence_count,
    )


@router.post(
    "/validate",
    response_model=ValidateCodesResponse,
    summary="Validate a set of codes",
    description="Validate ICD-10 and CPT codes for issues like invalid codes, duplicates, and bundling conflicts."
)
async def validate_codes(request: ValidateCodesRequest) -> ValidateCodesResponse:
    """Validate a set of codes.

    This endpoint checks codes for:
    - Invalid or unrecognized codes
    - Duplicate codes
    - Bundling conflicts (codes that shouldn't be billed together)
    - Other coding rule violations
    """
    if not request.diagnosis_codes and not request.procedure_codes:
        raise HTTPException(
            status_code=400,
            detail="At least one diagnosis or procedure code must be provided"
        )

    service = get_ai_coding_service()

    issues = service.validate_codes(
        diagnosis_codes=request.diagnosis_codes,
        procedure_codes=request.procedure_codes,
    )

    # Determine if valid
    has_errors = any(i.severity == "error" for i in issues)
    is_valid = not has_errors

    # Generate summary
    if not issues:
        summary = "All codes validated successfully"
    else:
        error_count = sum(1 for i in issues if i.severity == "error")
        warning_count = sum(1 for i in issues if i.severity == "warning")
        info_count = sum(1 for i in issues if i.severity == "info")

        parts = []
        if error_count:
            parts.append(f"{error_count} error(s)")
        if warning_count:
            parts.append(f"{warning_count} warning(s)")
        if info_count:
            parts.append(f"{info_count} info message(s)")

        summary = f"Validation found: {', '.join(parts)}"

    return ValidateCodesResponse(
        is_valid=is_valid,
        issues=[_convert_validation_issue(i) for i in issues],
        summary=summary,
    )


@router.post(
    "/hcc",
    response_model=HCCRiskResponse,
    summary="Calculate HCC risk scores",
    description="Calculate HCC risk scores and RAF values from ICD-10 diagnosis codes."
)
async def calculate_hcc(request: CalculateHCCRequest) -> HCCRiskResponse:
    """Calculate HCC risk scores.

    This endpoint calculates:
    - Total RAF (Risk Adjustment Factor) score
    - HCC codes mapped from ICD-10 codes
    - Estimated annual revenue impact
    - Potential HCC opportunities from clinical text
    """
    service = get_ai_coding_service()

    result = service.calculate_hcc_risk(
        icd10_codes=request.icd10_codes,
        clinical_text=request.clinical_text,
    )

    return _convert_hcc_risk(result)


@router.get(
    "/rules",
    response_model=CodingRulesResponse,
    summary="Get coding rules and guidelines",
    description="Get coding rules and guidelines, optionally filtered by category."
)
async def get_coding_rules(
    category: str | None = Query(None, description="Filter by category (e.g., 'E/M', 'bundling', 'HCC')")
) -> CodingRulesResponse:
    """Get coding rules and guidelines.

    Returns rules for:
    - E/M coding (MDM vs time)
    - Diagnosis sequencing
    - Code specificity
    - Bundling rules
    - HCC documentation requirements
    """
    service = get_ai_coding_service()

    rules = service.get_coding_rules(category=category)

    return CodingRulesResponse(
        rules=[
            CodingRuleResponse(
                rule_id=r.rule_id,
                category=r.category,
                title=r.title,
                description=r.description,
                codes_affected=r.codes_affected,
                examples=r.examples,
                source=r.source,
            )
            for r in rules
        ],
        total_count=len(rules),
    )


@router.get(
    "/stats",
    response_model=ServiceStatsResponse,
    summary="Get service statistics",
    description="Get statistics about the AI coding service including code counts and capabilities."
)
async def get_stats() -> ServiceStatsResponse:
    """Get service statistics."""
    service = get_ai_coding_service()
    stats = service.get_stats()

    return ServiceStatsResponse(
        total_icd10_codes=stats['total_icd10_codes'],
        total_cpt_codes=stats['total_cpt_codes'],
        total_icd10_synonyms=stats['total_icd10_synonyms'],
        total_cpt_synonyms=stats['total_cpt_synonyms'],
        hcc_mappings=stats['hcc_mappings'],
    )


@router.get(
    "/code/{code}",
    response_model=CodeDetailsResponse,
    summary="Get code details",
    description="Get details for a specific ICD-10 or CPT code."
)
async def get_code_details(
    code: str,
    code_type: str = Query("ICD10", description="Code type: ICD10 or CPT"),
) -> CodeDetailsResponse:
    """Get details for a specific code."""
    service = get_ai_coding_service()

    # Parse code type
    try:
        ct = CodeType[code_type.upper()]
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid code type: {code_type}. Use 'ICD10' or 'CPT'."
        )

    details = service.get_code_details(code, ct)

    if not details:
        raise HTTPException(
            status_code=404,
            detail=f"Code not found: {code}"
        )

    # Get HCC info if ICD-10
    hcc_code = None
    raf_value = None
    if ct == CodeType.ICD10:
        hcc_code = service._icd10_to_hcc.get(code)
        if hcc_code:
            raf_value = service._hcc_raf_values.get(hcc_code, 0.0)

    return CodeDetailsResponse(
        code=details.get('code', code),
        description=details.get('description', ''),
        synonyms=details.get('synonyms', []),
        category=details.get('category'),
        is_billable=details.get('is_billable'),
        hcc_code=hcc_code,
        raf_value=raf_value,
    )


@router.get(
    "/search",
    response_model=CodeSearchResponse,
    summary="Search for codes",
    description="Search for ICD-10 or CPT codes by description or synonym."
)
async def search_codes(
    query: str = Query(..., min_length=2, description="Search query"),
    code_type: str = Query("ICD10", description="Code type: ICD10 or CPT"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
) -> CodeSearchResponse:
    """Search for codes by description or synonym."""
    service = get_ai_coding_service()

    # Parse code type
    try:
        ct = CodeType[code_type.upper()]
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid code type: {code_type}. Use 'ICD10' or 'CPT'."
        )

    results = service.search_codes(query, ct, limit)

    return CodeSearchResponse(
        results=[
            CodeDetailsResponse(
                code=r.get('code', ''),
                description=r.get('description', ''),
                synonyms=r.get('synonyms', []),
                category=r.get('category'),
                is_billable=r.get('is_billable'),
                hcc_code=service._icd10_to_hcc.get(r.get('code')) if ct == CodeType.ICD10 else None,
                raf_value=service._hcc_raf_values.get(service._icd10_to_hcc.get(r.get('code'))) if ct == CodeType.ICD10 and r.get('code') in service._icd10_to_hcc else None,
            )
            for r in results
        ],
        total_count=len(results),
    )
