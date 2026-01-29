"""LLM API Endpoints.

Provides AI-powered clinical summarization using external LLMs:
- POST /llm/summarize - Summarize clinical text
- POST /llm/assessment - Generate Assessment and Plan
- POST /llm/key-findings - Extract key clinical findings
- POST /llm/discharge-summary - Generate discharge summary

PHI Note: Ensure clinical text is properly de-identified before
using these endpoints if sending to external LLM providers.
"""

import logging
import time
from enum import Enum
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm", tags=["LLM Clinical Summarization"])


# ============================================================================
# Enums and Types
# ============================================================================


class SummaryLengthParam(str, Enum):
    """Summary length preference."""

    BRIEF = "brief"
    STANDARD = "standard"
    DETAILED = "detailed"


class LLMProviderParam(str, Enum):
    """LLM provider selection."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class FindingCategory(str, Enum):
    """Categories of clinical findings."""

    DIAGNOSIS = "diagnosis"
    SYMPTOM = "symptom"
    LAB = "lab"
    VITAL = "vital"
    MEDICATION = "medication"
    PROCEDURE = "procedure"


class FindingSignificance(str, Enum):
    """Significance level of findings."""

    CRITICAL = "critical"
    IMPORTANT = "important"
    ROUTINE = "routine"


# ============================================================================
# Request/Response Models
# ============================================================================


class SummarizeRequest(BaseModel):
    """Request to summarize clinical text."""

    text: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="Clinical text to summarize (e.g., progress note, discharge summary)",
    )
    length: SummaryLengthParam = Field(
        default=SummaryLengthParam.STANDARD,
        description="Desired summary length",
    )
    focus_sections: list[str] | None = Field(
        default=None,
        description="Specific sections to emphasize (e.g., 'assessment', 'medications')",
    )
    provider: LLMProviderParam | None = Field(
        default=None,
        description="LLM provider to use (uses default from config if not specified)",
    )
    model: str | None = Field(
        default=None,
        description="Specific model to use (e.g., 'gpt-4o', 'claude-3-sonnet')",
    )


class SummarizeResponse(BaseModel):
    """Response from summarization."""

    request_id: str = Field(..., description="Unique request identifier")
    summary: str = Field(..., description="Generated clinical summary")
    key_points: list[str] = Field(
        default_factory=list, description="Key points extracted from the summary"
    )
    word_count: int = Field(..., description="Word count of the summary")
    token_usage: int = Field(..., description="Total tokens used")
    cost_usd: float = Field(..., description="Estimated cost in USD")
    latency_ms: float = Field(..., description="Processing time in milliseconds")
    model_used: str = Field(..., description="LLM model used")
    warnings: list[str] = Field(
        default_factory=list, description="Any warnings (e.g., PHI detected)"
    )


class AssessmentRequest(BaseModel):
    """Request to generate Assessment and Plan."""

    findings: str = Field(
        ...,
        min_length=1,
        max_length=30000,
        description="Clinical findings to generate A&P from",
    )
    include_icd10: bool = Field(
        default=True,
        description="Include ICD-10 code suggestions",
    )
    max_problems: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Maximum number of problems to include",
    )
    provider: LLMProviderParam | None = Field(
        default=None,
        description="LLM provider to use",
    )
    model: str | None = Field(
        default=None,
        description="Specific model to use",
    )


class AssessmentPlanItem(BaseModel):
    """A single problem in the Assessment and Plan."""

    problem_number: int = Field(..., description="Problem number (priority order)")
    problem: str = Field(..., description="Problem description")
    assessment: str = Field(..., description="Assessment for this problem")
    plan_items: list[str] = Field(
        default_factory=list, description="Plan items for this problem"
    )
    icd10_codes: list[str] = Field(
        default_factory=list, description="Suggested ICD-10 codes"
    )


class AssessmentResponse(BaseModel):
    """Response from A&P generation."""

    request_id: str = Field(..., description="Unique request identifier")
    items: list[AssessmentPlanItem] = Field(
        ..., description="Assessment and Plan items"
    )
    full_text: str = Field(..., description="Full A&P text as generated")
    total_problems: int = Field(..., description="Total problems identified")
    token_usage: int = Field(..., description="Total tokens used")
    cost_usd: float = Field(..., description="Estimated cost in USD")
    latency_ms: float = Field(..., description="Processing time in milliseconds")
    model_used: str = Field(..., description="LLM model used")


class KeyFindingsRequest(BaseModel):
    """Request to extract key findings."""

    text: str = Field(
        ...,
        min_length=1,
        max_length=30000,
        description="Clinical text to extract findings from",
    )
    categories: list[FindingCategory] | None = Field(
        default=None,
        description="Specific categories to focus on",
    )
    max_findings: int = Field(
        default=20,
        ge=1,
        le=50,
        description="Maximum findings to return",
    )
    provider: LLMProviderParam | None = Field(
        default=None,
        description="LLM provider to use",
    )
    model: str | None = Field(
        default=None,
        description="Specific model to use",
    )


class KeyFinding(BaseModel):
    """A key clinical finding."""

    finding: str = Field(..., description="The finding description")
    category: str = Field(..., description="Finding category")
    significance: FindingSignificance = Field(..., description="Clinical significance")
    context: str | None = Field(None, description="Additional context")


class KeyFindingsResponse(BaseModel):
    """Response from key findings extraction."""

    request_id: str = Field(..., description="Unique request identifier")
    findings: list[KeyFinding] = Field(..., description="Extracted key findings")
    critical_count: int = Field(..., description="Number of critical findings")
    important_count: int = Field(..., description="Number of important findings")
    routine_count: int = Field(..., description="Number of routine findings")
    token_usage: int = Field(..., description="Total tokens used")
    cost_usd: float = Field(..., description="Estimated cost in USD")
    latency_ms: float = Field(..., description="Processing time in milliseconds")
    model_used: str = Field(..., description="LLM model used")


class EncounterInput(BaseModel):
    """Input data for a clinical encounter."""

    encounter_id: str = Field(..., description="Encounter identifier")
    date: str = Field(..., description="Encounter date (ISO format)")
    encounter_type: str = Field(
        ..., description="Type: admission, progress, procedure, consultation"
    )
    text: str = Field(..., description="Encounter note text")
    diagnoses: list[str] = Field(
        default_factory=list, description="Diagnoses documented"
    )
    procedures: list[str] = Field(
        default_factory=list, description="Procedures performed"
    )
    medications: list[str] = Field(
        default_factory=list, description="Medications prescribed"
    )


class DischargeSummaryRequest(BaseModel):
    """Request to generate discharge summary."""

    encounters: list[EncounterInput] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Clinical encounters during hospitalization",
    )
    include_med_reconciliation: bool = Field(
        default=True,
        description="Include medication reconciliation section",
    )
    include_patient_education: bool = Field(
        default=True,
        description="Include patient education points",
    )
    provider: LLMProviderParam | None = Field(
        default=None,
        description="LLM provider to use",
    )
    model: str | None = Field(
        default=None,
        description="Specific model to use",
    )


class DischargeSummaryResponse(BaseModel):
    """Response from discharge summary generation."""

    request_id: str = Field(..., description="Unique request identifier")
    summary: str = Field(..., description="Full discharge summary text")
    admission_date: str | None = Field(None, description="Admission date")
    discharge_date: str | None = Field(None, description="Discharge date")
    length_of_stay_days: int | None = Field(None, description="Length of stay in days")
    discharge_diagnoses: list[str] = Field(
        default_factory=list, description="Discharge diagnoses"
    )
    discharge_medications: list[str] = Field(
        default_factory=list, description="Discharge medications"
    )
    follow_up_instructions: list[str] = Field(
        default_factory=list, description="Follow-up instructions"
    )
    sections: dict[str, str] = Field(
        default_factory=dict, description="Named sections of the summary"
    )
    token_usage: int = Field(..., description="Total tokens used")
    cost_usd: float = Field(..., description="Estimated cost in USD")
    latency_ms: float = Field(..., description="Processing time in milliseconds")
    model_used: str = Field(..., description="LLM model used")


class LLMServiceStats(BaseModel):
    """Statistics for the LLM service."""

    provider: str = Field(..., description="Default LLM provider")
    model: str = Field(..., description="Default model")
    total_requests: int = Field(..., description="Total API requests made")
    total_tokens: int = Field(..., description="Total tokens used")
    total_cost_usd: float = Field(..., description="Total estimated cost")
    available_providers: list[str] = Field(..., description="Configured providers")


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "/summarize",
    response_model=SummarizeResponse,
    summary="Summarize clinical text",
    description="Generate a concise clinical summary using LLM.",
)
async def summarize_clinical_text(request: SummarizeRequest) -> SummarizeResponse:
    """Summarize clinical text using LLM.

    This endpoint uses an external LLM (OpenAI or Anthropic) to generate
    concise, accurate clinical summaries.

    **PHI Warning**: Ensure text is properly de-identified before using
    this endpoint if PHI protection is required.

    Args:
        request: Clinical text and summarization options.

    Returns:
        SummarizeResponse with generated summary.
    """
    request_id = str(uuid4())

    try:
        from app.services.llm_summarizer import (
            ClinicalSection,
            SummaryLength,
            get_clinical_summarizer_llm,
        )
        from app.services.llm_service import LLMProvider

        summarizer = get_clinical_summarizer_llm()

        # Map length parameter
        length_map = {
            SummaryLengthParam.BRIEF: SummaryLength.BRIEF,
            SummaryLengthParam.STANDARD: SummaryLength.STANDARD,
            SummaryLengthParam.DETAILED: SummaryLength.DETAILED,
        }
        length = length_map.get(request.length, SummaryLength.STANDARD)

        # Map provider parameter
        provider = None
        if request.provider:
            provider = LLMProvider(request.provider.value)

        # Map focus sections
        focus_sections = None
        if request.focus_sections:
            focus_sections = []
            for section in request.focus_sections:
                try:
                    focus_sections.append(ClinicalSection(section.lower()))
                except ValueError:
                    pass  # Ignore invalid sections

        result = await summarizer.summarize_clinical_note(
            text=request.text,
            length=length,
            focus_sections=focus_sections,
            model=request.model,
            provider=provider,
        )

        return SummarizeResponse(
            request_id=request_id,
            summary=result.summary,
            key_points=result.key_points,
            word_count=result.word_count,
            token_usage=result.token_usage,
            cost_usd=round(result.cost_usd, 6),
            latency_ms=result.latency_ms,
            model_used=result.model_used,
            warnings=result.warnings,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # VP-Security-5: Log full error, return sanitized message
        logger.error(f"Summarization failed: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Summarization failed. Please try again.")


@router.post(
    "/assessment",
    response_model=AssessmentResponse,
    summary="Generate Assessment and Plan",
    description="Generate an Assessment and Plan section from clinical findings.",
)
async def generate_assessment(request: AssessmentRequest) -> AssessmentResponse:
    """Generate Assessment and Plan from clinical findings.

    Creates a structured A&P section with prioritized problems,
    assessments, and plan items. Optionally includes ICD-10 suggestions.

    Args:
        request: Clinical findings and generation options.

    Returns:
        AssessmentResponse with structured A&P.
    """
    request_id = str(uuid4())

    try:
        from app.services.llm_summarizer import get_clinical_summarizer_llm
        from app.services.llm_service import LLMProvider

        summarizer = get_clinical_summarizer_llm()

        # Map provider
        provider = None
        if request.provider:
            provider = LLMProvider(request.provider.value)

        result = await summarizer.generate_assessment_plan(
            findings=request.findings,
            include_icd10=request.include_icd10,
            max_problems=request.max_problems,
            model=request.model,
            provider=provider,
        )

        # Convert items to response format
        items = [
            AssessmentPlanItem(
                problem_number=item.problem_number,
                problem=item.problem,
                assessment=item.assessment,
                plan_items=item.plan_items,
                icd10_codes=item.icd10_codes,
            )
            for item in result.items
        ]

        return AssessmentResponse(
            request_id=request_id,
            items=items,
            full_text=result.summary,
            total_problems=result.total_problems,
            token_usage=result.token_usage,
            cost_usd=round(result.cost_usd, 6),
            latency_ms=result.latency_ms,
            model_used=result.model_used,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # VP-Security-5: Log full error, return sanitized message
        logger.error(f"Assessment generation failed: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500, detail="Assessment generation failed. Please try again."
        )


@router.post(
    "/key-findings",
    response_model=KeyFindingsResponse,
    summary="Extract key clinical findings",
    description="Extract and prioritize key clinical findings from text.",
)
async def extract_key_findings(request: KeyFindingsRequest) -> KeyFindingsResponse:
    """Extract key clinical findings from text.

    Identifies and prioritizes clinical findings by significance
    (critical, important, routine) and category.

    Args:
        request: Clinical text and extraction options.

    Returns:
        KeyFindingsResponse with extracted findings.
    """
    request_id = str(uuid4())

    try:
        from app.services.llm_summarizer import get_clinical_summarizer_llm
        from app.services.llm_service import LLMProvider

        summarizer = get_clinical_summarizer_llm()

        # Map provider
        provider = None
        if request.provider:
            provider = LLMProvider(request.provider.value)

        # Map categories
        categories = None
        if request.categories:
            categories = [cat.value for cat in request.categories]

        result = await summarizer.extract_key_findings(
            text=request.text,
            categories=categories,
            max_findings=request.max_findings,
            model=request.model,
            provider=provider,
        )

        # Convert findings to response format
        findings = []
        for f in result.findings:
            try:
                sig = FindingSignificance(f.significance)
            except ValueError:
                sig = FindingSignificance.ROUTINE

            findings.append(
                KeyFinding(
                    finding=f.finding,
                    category=f.category,
                    significance=sig,
                    context=f.context,
                )
            )

        return KeyFindingsResponse(
            request_id=request_id,
            findings=findings,
            critical_count=result.critical_count,
            important_count=result.important_count,
            routine_count=result.routine_count,
            token_usage=result.token_usage,
            cost_usd=round(result.cost_usd, 6),
            latency_ms=result.latency_ms,
            model_used=result.model_used,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # VP-Security-5: Log full error, return sanitized message
        logger.error(f"Key findings extraction failed: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500, detail="Key findings extraction failed. Please try again."
        )


@router.post(
    "/discharge-summary",
    response_model=DischargeSummaryResponse,
    summary="Generate discharge summary",
    description="Generate a comprehensive discharge summary from encounter data.",
)
async def generate_discharge_summary(
    request: DischargeSummaryRequest,
) -> DischargeSummaryResponse:
    """Generate discharge summary from encounter data.

    Creates a comprehensive discharge summary including hospital course,
    discharge diagnoses, medications, and follow-up instructions.

    Args:
        request: Encounter data and generation options.

    Returns:
        DischargeSummaryResponse with generated summary.
    """
    request_id = str(uuid4())

    try:
        from app.services.llm_summarizer import (
            EncounterData,
            get_clinical_summarizer_llm,
        )
        from app.services.llm_service import LLMProvider

        summarizer = get_clinical_summarizer_llm()

        # Map provider
        provider = None
        if request.provider:
            provider = LLMProvider(request.provider.value)

        # Convert encounters
        encounters = [
            EncounterData(
                encounter_id=enc.encounter_id,
                date=enc.date,
                encounter_type=enc.encounter_type,
                text=enc.text,
                diagnoses=enc.diagnoses,
                procedures=enc.procedures,
                medications=enc.medications,
            )
            for enc in request.encounters
        ]

        result = await summarizer.generate_discharge_summary(
            encounters=encounters,
            include_med_reconciliation=request.include_med_reconciliation,
            include_patient_education=request.include_patient_education,
            model=request.model,
            provider=provider,
        )

        return DischargeSummaryResponse(
            request_id=request_id,
            summary=result.summary,
            admission_date=result.admission_date,
            discharge_date=result.discharge_date,
            length_of_stay_days=result.length_of_stay_days,
            discharge_diagnoses=result.discharge_diagnoses,
            discharge_medications=result.discharge_medications,
            follow_up_instructions=result.follow_up_instructions,
            sections=result.sections,
            token_usage=result.token_usage,
            cost_usd=round(result.cost_usd, 6),
            latency_ms=result.latency_ms,
            model_used=result.model_used,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # VP-Security-5: Log full error, return sanitized message
        logger.error(f"Discharge summary generation failed: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500, detail="Discharge summary generation failed. Please try again."
        )


@router.get(
    "/stats",
    response_model=LLMServiceStats,
    summary="Get LLM service statistics",
    description="Get usage statistics for the LLM service.",
)
async def get_llm_stats() -> LLMServiceStats:
    """Get LLM service statistics.

    Returns usage metrics including total requests, tokens used,
    and estimated costs.

    Returns:
        LLMServiceStats with service metrics.
    """
    try:
        from app.services.llm_service import get_llm_service

        service = get_llm_service()
        stats = service.get_stats()

        return LLMServiceStats(
            provider=stats.get("provider", "unknown"),
            model=stats.get("model", "unknown"),
            total_requests=stats.get("total_requests", 0),
            total_tokens=stats.get("total_tokens", 0),
            total_cost_usd=round(stats.get("total_cost_usd", 0), 4),
            available_providers=stats.get("available_providers", []),
        )

    except Exception as e:
        # VP-Security-5: Log full error, return sanitized message
        logger.error(f"Failed to get LLM stats: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get stats. Please try again."
        )


@router.get(
    "/providers",
    summary="Get available LLM providers",
    description="List configured and available LLM providers.",
)
async def get_available_providers() -> dict:
    """Get available LLM providers.

    Returns list of providers that are properly configured
    with API keys and ready to use.

    Returns:
        Dictionary with available providers and their status.
    """
    try:
        from app.services.llm_service import get_llm_service, LLMProvider

        service = get_llm_service()
        available = service.get_available_providers()

        return {
            "available_providers": [p.value for p in available],
            "default_provider": service.config.provider.value,
            "default_model": service.config.model,
            "provider_status": {
                "openai": LLMProvider.OPENAI in available,
                "anthropic": LLMProvider.ANTHROPIC in available,
            },
        }

    except Exception as e:
        # VP-Security-5: Log full error, return sanitized message
        logger.error(f"Failed to get providers: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get providers. Please try again."
        )
