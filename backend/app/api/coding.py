"""Auto-Coding API Endpoints.

Provides AI-powered clinical coding services:
- Auto-code: Extract clinical concepts and suggest codes
- Batch coding: Process multiple texts
- Code validation: Verify proposed codes against clinical text

This module combines:
- NLP extraction (ensemble + advanced enhancements)
- OMOP vocabulary mapping
- ICD-10/CPT code suggestion
"""

import time
from enum import Enum
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.errors import ErrorCode, InternalError

router = APIRouter(prefix="/coding", tags=["Auto-Coding"])


# ============================================================================
# Enums and Types
# ============================================================================


class CodeSystem(str, Enum):
    """Supported code systems."""

    ICD10CM = "ICD10CM"
    ICD10PCS = "ICD10PCS"
    CPT = "CPT"
    SNOMED = "SNOMED"
    LOINC = "LOINC"
    RXNORM = "RxNorm"
    NDC = "NDC"
    HCPCS = "HCPCS"
    MEDDRA = "MedDRA"
    CDISC = "CDISC"


class ConfidenceLevel(str, Enum):
    """Confidence level for code suggestions."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AssertionStatus(str, Enum):
    """Assertion status for extracted concepts."""

    PRESENT = "present"
    ABSENT = "absent"
    POSSIBLE = "possible"
    CONDITIONAL = "conditional"
    HYPOTHETICAL = "hypothetical"
    FAMILY_HISTORY = "family_history"


# ============================================================================
# Request/Response Models
# ============================================================================


class AutoCodeRequest(BaseModel):
    """Request for auto-coding clinical text."""

    text: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="Clinical text to code (progress note, discharge summary, etc.)",
    )
    code_systems: list[CodeSystem] = Field(
        default=[CodeSystem.ICD10CM, CodeSystem.CPT],
        description="Code systems to return suggestions for",
    )
    include_negated: bool = Field(
        default=False,
        description="Include codes for negated findings (e.g., 'denies chest pain')",
    )
    include_historical: bool = Field(
        default=True,
        description="Include codes for historical conditions",
    )
    max_codes_per_concept: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum code suggestions per extracted concept",
    )
    min_confidence: ConfidenceLevel = Field(
        default=ConfidenceLevel.LOW,
        description="Minimum confidence threshold for code suggestions",
    )
    note_type: str | None = Field(
        default=None,
        description="Note type hint (progress_note, discharge_summary, operative_note, etc.)",
    )


class ExtractedConcept(BaseModel):
    """An extracted clinical concept from the text."""

    id: str = Field(..., description="Unique identifier for this extraction")
    text: str = Field(..., description="Original text span")
    normalized_text: str = Field(..., description="Normalized/expanded text")
    start_offset: int = Field(..., description="Start character offset in source text")
    end_offset: int = Field(..., description="End character offset in source text")
    domain: str = Field(..., description="Clinical domain (Condition, Drug, Procedure, etc.)")
    assertion: AssertionStatus = Field(..., description="Assertion status")
    laterality: str | None = Field(None, description="Laterality if applicable (left, right, bilateral)")
    temporality: str = Field(..., description="Temporality (current, historical, future)")
    confidence: float = Field(..., ge=0, le=1, description="Extraction confidence")

    # Advanced NLP enhancements
    abbreviation_expansion: str | None = Field(
        None, description="Expanded abbreviation if detected (PE -> pulmonary embolism)"
    )
    compound_modifier: str | None = Field(
        None, description="Compound condition modifier (e.g., 'with reduced EF' for HFrEF)"
    )
    negation_trigger: str | None = Field(
        None, description="Negation trigger if negated (e.g., 'denies', 'no')"
    )


class CodeSuggestion(BaseModel):
    """A suggested code for an extracted concept."""

    code: str = Field(..., description="The code value")
    code_system: CodeSystem = Field(..., description="Code system")
    description: str = Field(..., description="Code description")
    confidence: ConfidenceLevel = Field(..., description="Suggestion confidence")
    confidence_score: float = Field(..., ge=0, le=1, description="Numeric confidence score")
    match_type: str = Field(..., description="How the code was matched (exact, semantic, fuzzy)")
    match_explanation: str = Field(..., description="Explanation of why this code was suggested")
    is_billable: bool = Field(default=True, description="Whether the code is billable")
    more_specific_available: bool = Field(
        default=False, description="Whether more specific codes exist"
    )


class ConceptWithCodes(BaseModel):
    """An extracted concept with its suggested codes."""

    concept: ExtractedConcept = Field(..., description="The extracted concept")
    suggested_codes: list[CodeSuggestion] = Field(
        default_factory=list, description="Suggested codes for this concept"
    )
    omop_concept_id: int | None = Field(
        None, description="OMOP standard concept ID if mapped"
    )
    omop_concept_name: str | None = Field(
        None, description="OMOP concept name"
    )


class CodingSummary(BaseModel):
    """Summary statistics for the coding operation."""

    total_concepts_extracted: int = Field(..., description="Total concepts extracted")
    concepts_with_codes: int = Field(..., description="Concepts that received code suggestions")
    concepts_negated: int = Field(..., description="Concepts marked as negated/absent")
    codes_by_system: dict[str, int] = Field(
        default_factory=dict, description="Count of codes by system"
    )
    high_confidence_codes: int = Field(..., description="Number of high-confidence suggestions")
    processing_time_ms: float = Field(..., description="Total processing time in milliseconds")


class AutoCodeResponse(BaseModel):
    """Response from auto-coding."""

    request_id: str = Field(..., description="Unique request identifier")
    text_length: int = Field(..., description="Length of input text")
    concepts: list[ConceptWithCodes] = Field(..., description="Extracted concepts with codes")
    summary: CodingSummary = Field(..., description="Coding summary statistics")
    warnings: list[str] = Field(default_factory=list, description="Any warnings or notes")


class BatchCodeRequest(BaseModel):
    """Request for batch coding multiple texts."""

    texts: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of clinical texts to code",
    )
    code_systems: list[CodeSystem] = Field(
        default=[CodeSystem.ICD10CM],
        description="Code systems to return",
    )
    max_codes_per_concept: int = Field(default=3, ge=1, le=10)


class BatchCodeItem(BaseModel):
    """Result for a single text in batch coding."""

    index: int = Field(..., description="Index of this text in the input list")
    text_preview: str = Field(..., description="First 100 chars of the text")
    concepts_extracted: int = Field(..., description="Number of concepts extracted")
    codes_suggested: int = Field(..., description="Number of codes suggested")
    top_codes: list[CodeSuggestion] = Field(..., description="Top suggested codes")
    error: str | None = Field(None, description="Error message if processing failed")


class BatchCodeResponse(BaseModel):
    """Response from batch coding."""

    request_id: str = Field(..., description="Unique request identifier")
    total_texts: int = Field(..., description="Total texts processed")
    successful: int = Field(..., description="Successfully processed")
    failed: int = Field(..., description="Failed to process")
    results: list[BatchCodeItem] = Field(..., description="Results for each text")
    total_time_ms: float = Field(..., description="Total processing time")


# ============================================================================
# Auto-Code Endpoint
# ============================================================================


@router.post(
    "/auto-code",
    response_model=AutoCodeResponse,
    summary="Auto-code clinical text",
    description="Extract clinical concepts and suggest codes using AI-powered NLP.",
)
async def auto_code(request: AutoCodeRequest) -> AutoCodeResponse:
    """Auto-code clinical text using NLP extraction and vocabulary mapping.

    This endpoint performs:
    1. **NLP Extraction**: Identifies clinical concepts (conditions, procedures, drugs, etc.)
    2. **Advanced Enhancement**: Disambiguates abbreviations, detects negation boundaries,
       extracts laterality, and identifies compound conditions
    3. **OMOP Mapping**: Maps concepts to OMOP standard vocabulary
    4. **Code Suggestion**: Suggests ICD-10, CPT, and other codes with confidence scores

    The response includes:
    - Extracted concepts with their text spans and attributes
    - Suggested codes for each concept with explanations
    - Summary statistics and processing metrics

    Args:
        request: Clinical text and coding configuration.

    Returns:
        AutoCodeResponse with concepts, codes, and summary.
    """
    start_time = time.perf_counter()
    request_id = str(uuid4())

    try:
        # Import services
        from app.services import (
            get_advanced_nlp_service,
            get_ensemble_nlp_service,
            get_icd10_suggester_service,
            get_cpt_suggester_service,
        )

        # Step 1: NLP Extraction
        ensemble = get_ensemble_nlp_service()
        mentions = ensemble.extract_mentions(request.text, str(uuid4()))

        # Step 2: Advanced NLP Enhancements
        advanced = get_advanced_nlp_service()
        enhanced_mentions = advanced.enhance_mentions(request.text, mentions)

        # Step 3: Build concepts with codes
        concepts_with_codes: list[ConceptWithCodes] = []
        codes_by_system: dict[str, int] = {}
        high_confidence_count = 0
        negated_count = 0

        icd10_service = None
        cpt_service = None

        if CodeSystem.ICD10CM in request.code_systems:
            icd10_service = get_icd10_suggester_service()
        if CodeSystem.CPT in request.code_systems:
            cpt_service = get_cpt_suggester_service()

        for em in enhanced_mentions:
            mention = em.mention
            enhancement = em.enhancement

            # Determine assertion status
            assertion = AssertionStatus.PRESENT
            if mention.assertion.value == "absent":
                assertion = AssertionStatus.ABSENT
                negated_count += 1
                if not request.include_negated:
                    continue
            elif mention.assertion.value == "possible":
                assertion = AssertionStatus.POSSIBLE
            elif mention.assertion.value == "conditional":
                assertion = AssertionStatus.CONDITIONAL
            elif mention.temporality == "historical":
                if not request.include_historical:
                    continue

            # Build normalized text
            normalized = mention.text
            if enhancement.disambiguated_term:
                normalized = enhancement.disambiguated_term
            if enhancement.compound_condition_text:
                normalized = enhancement.compound_condition_text

            # Create extracted concept
            concept = ExtractedConcept(
                id=str(uuid4()),
                text=mention.text,
                normalized_text=normalized,
                start_offset=mention.start_offset,
                end_offset=mention.end_offset,
                domain=mention.domain or "Unknown",
                assertion=assertion,
                laterality=enhancement.laterality.value if enhancement.laterality else None,
                temporality=mention.temporality,
                confidence=mention.confidence,
                abbreviation_expansion=enhancement.disambiguated_term,
                compound_modifier=enhancement.linked_modifier,
                negation_trigger=enhancement.negation_trigger,
            )

            # Suggest codes
            suggested_codes: list[CodeSuggestion] = []

            # ICD-10 codes for conditions
            if (
                icd10_service
                and mention.domain in ("Condition", "Observation", None)
                and assertion != AssertionStatus.ABSENT
            ):
                try:
                    icd_result = icd10_service.suggest_codes(
                        query=normalized,
                        max_suggestions=request.max_codes_per_concept,
                    )
                    for s in icd_result.suggestions:
                        conf_level = ConfidenceLevel(s.confidence.value)
                        if _passes_confidence_threshold(conf_level, request.min_confidence):
                            suggested_codes.append(
                                CodeSuggestion(
                                    code=s.code,
                                    code_system=CodeSystem.ICD10CM,
                                    description=s.description,
                                    confidence=conf_level,
                                    confidence_score=_confidence_to_score(conf_level),
                                    match_type=_infer_match_type(s.match_reason),
                                    match_explanation=s.match_reason,
                                    is_billable=s.is_billable,
                                    more_specific_available=len(s.more_specific_codes) > 0,
                                )
                            )
                            codes_by_system["ICD10CM"] = codes_by_system.get("ICD10CM", 0) + 1
                            if conf_level == ConfidenceLevel.HIGH:
                                high_confidence_count += 1
                except Exception:
                    pass  # Continue if ICD-10 suggestion fails

            # CPT codes for procedures
            if cpt_service and mention.domain == "Procedure":
                try:
                    cpt_result = cpt_service.suggest_codes(
                        query=normalized,
                        clinical_context={},
                        max_suggestions=request.max_codes_per_concept,
                    )
                    for s in cpt_result.suggestions:
                        conf_level = ConfidenceLevel(s.confidence.value)
                        if _passes_confidence_threshold(conf_level, request.min_confidence):
                            suggested_codes.append(
                                CodeSuggestion(
                                    code=s.code,
                                    code_system=CodeSystem.CPT,
                                    description=s.description,
                                    confidence=conf_level,
                                    confidence_score=_confidence_to_score(conf_level),
                                    match_type="semantic",
                                    match_explanation=s.cer_citation.claim if s.cer_citation else "Procedure match",
                                    is_billable=True,
                                    more_specific_available=len(s.alternative_codes) > 0,
                                )
                            )
                            codes_by_system["CPT"] = codes_by_system.get("CPT", 0) + 1
                            if conf_level == ConfidenceLevel.HIGH:
                                high_confidence_count += 1
                except Exception:
                    pass  # Continue if CPT suggestion fails

            # Add OMOP concept if available
            omop_id = mention.omop_concept_id

            concepts_with_codes.append(
                ConceptWithCodes(
                    concept=concept,
                    suggested_codes=suggested_codes,
                    omop_concept_id=omop_id,
                    omop_concept_name=normalized if omop_id else None,
                )
            )

        # Build summary
        processing_time = (time.perf_counter() - start_time) * 1000
        concepts_with_codes_count = sum(1 for c in concepts_with_codes if c.suggested_codes)

        summary = CodingSummary(
            total_concepts_extracted=len(concepts_with_codes),
            concepts_with_codes=concepts_with_codes_count,
            concepts_negated=negated_count,
            codes_by_system=codes_by_system,
            high_confidence_codes=high_confidence_count,
            processing_time_ms=round(processing_time, 2),
        )

        # Warnings
        warnings = []
        if len(concepts_with_codes) == 0:
            warnings.append("No clinical concepts were extracted from the text.")
        if concepts_with_codes_count == 0 and len(concepts_with_codes) > 0:
            warnings.append("Concepts were extracted but no codes could be suggested.")

        return AutoCodeResponse(
            request_id=request_id,
            text_length=len(request.text),
            concepts=concepts_with_codes,
            summary=summary,
            warnings=warnings,
        )

    except Exception as e:
        raise InternalError(
            message=f"Auto-coding failed: {str(e)}",
            error_code=ErrorCode.INTERNAL_NLP_ERROR,
        )


# ============================================================================
# Batch Coding Endpoint
# ============================================================================


@router.post(
    "/batch",
    response_model=BatchCodeResponse,
    summary="Batch code multiple texts",
    description="Process multiple clinical texts for coding in a single request.",
)
async def batch_code(request: BatchCodeRequest) -> BatchCodeResponse:
    """Batch code multiple clinical texts.

    Efficiently processes multiple texts in a single request.
    Returns summary results for each text with top suggested codes.

    Args:
        request: List of texts and coding configuration.

    Returns:
        BatchCodeResponse with results for each text.
    """
    start_time = time.perf_counter()
    request_id = str(uuid4())

    results: list[BatchCodeItem] = []
    successful = 0
    failed = 0

    for i, text in enumerate(request.texts):
        try:
            # Use auto_code for each text
            auto_request = AutoCodeRequest(
                text=text,
                code_systems=request.code_systems,
                max_codes_per_concept=request.max_codes_per_concept,
            )
            response = await auto_code(auto_request)

            # Collect top codes across all concepts
            all_codes = []
            for c in response.concepts:
                all_codes.extend(c.suggested_codes)

            # Sort by confidence and take top 5
            all_codes.sort(key=lambda x: x.confidence_score, reverse=True)
            top_codes = all_codes[:5]

            results.append(
                BatchCodeItem(
                    index=i,
                    text_preview=text[:100] + "..." if len(text) > 100 else text,
                    concepts_extracted=response.summary.total_concepts_extracted,
                    codes_suggested=sum(response.summary.codes_by_system.values()),
                    top_codes=top_codes,
                    error=None,
                )
            )
            successful += 1

        except Exception as e:
            results.append(
                BatchCodeItem(
                    index=i,
                    text_preview=text[:100] + "..." if len(text) > 100 else text,
                    concepts_extracted=0,
                    codes_suggested=0,
                    top_codes=[],
                    error=str(e),
                )
            )
            failed += 1

    total_time = (time.perf_counter() - start_time) * 1000

    return BatchCodeResponse(
        request_id=request_id,
        total_texts=len(request.texts),
        successful=successful,
        failed=failed,
        results=results,
        total_time_ms=round(total_time, 2),
    )


# ============================================================================
# Code Validation Endpoint
# ============================================================================


class ValidateCodeRequest(BaseModel):
    """Request to validate a code against clinical text."""

    text: str = Field(..., description="Clinical text to validate against")
    code: str = Field(..., description="Code to validate")
    code_system: CodeSystem = Field(..., description="Code system")


class ValidationResult(BaseModel):
    """Result of code validation."""

    code: str = Field(..., description="The code that was validated")
    code_system: CodeSystem = Field(..., description="Code system")
    code_description: str = Field(..., description="Code description")
    is_supported: bool = Field(..., description="Whether the code is supported by the text")
    confidence: ConfidenceLevel = Field(..., description="Confidence in the validation")
    supporting_evidence: list[str] = Field(
        default_factory=list, description="Text spans supporting this code"
    )
    concerns: list[str] = Field(
        default_factory=list, description="Any concerns about this code assignment"
    )


class ValidateCodeResponse(BaseModel):
    """Response from code validation."""

    request_id: str = Field(..., description="Unique request identifier")
    validation: ValidationResult = Field(..., description="Validation result")
    alternative_codes: list[CodeSuggestion] = Field(
        default_factory=list, description="Alternative codes that may be more appropriate"
    )


@router.post(
    "/validate",
    response_model=ValidateCodeResponse,
    summary="Validate a code against clinical text",
    description="Check if a proposed code is supported by the clinical documentation.",
)
async def validate_code(request: ValidateCodeRequest) -> ValidateCodeResponse:
    """Validate a proposed code against clinical text.

    Checks whether a code is supported by the clinical documentation and
    provides evidence for the validation decision.

    Args:
        request: Text, code, and code system to validate.

    Returns:
        ValidateCodeResponse with validation result and alternatives.
    """
    request_id = str(uuid4())

    try:
        # Run auto-coding on the text
        auto_request = AutoCodeRequest(
            text=request.text,
            code_systems=[request.code_system],
            include_negated=True,
        )
        auto_response = await auto_code(auto_request)

        # Check if the code was suggested
        is_supported = False
        confidence = ConfidenceLevel.LOW
        supporting_evidence = []
        concerns = []
        code_description = request.code

        for concept in auto_response.concepts:
            for suggestion in concept.suggested_codes:
                if suggestion.code.upper() == request.code.upper():
                    is_supported = True
                    confidence = suggestion.confidence
                    code_description = suggestion.description
                    supporting_evidence.append(
                        f"Found in text: '{concept.concept.text}' ({concept.concept.assertion.value})"
                    )

                    if concept.concept.assertion == AssertionStatus.ABSENT:
                        concerns.append(
                            f"The concept '{concept.concept.text}' is negated in the text"
                        )
                        is_supported = False

        if not is_supported and len(concerns) == 0:
            concerns.append(
                f"Code {request.code} was not matched to any concepts in the text"
            )

        # Collect alternative codes
        alternatives = []
        for concept in auto_response.concepts:
            for suggestion in concept.suggested_codes:
                if suggestion.code.upper() != request.code.upper():
                    alternatives.append(suggestion)

        # Deduplicate and take top 5
        seen = set()
        unique_alternatives = []
        for alt in alternatives:
            if alt.code not in seen:
                seen.add(alt.code)
                unique_alternatives.append(alt)
        unique_alternatives = sorted(
            unique_alternatives, key=lambda x: x.confidence_score, reverse=True
        )[:5]

        return ValidateCodeResponse(
            request_id=request_id,
            validation=ValidationResult(
                code=request.code,
                code_system=request.code_system,
                code_description=code_description,
                is_supported=is_supported,
                confidence=confidence,
                supporting_evidence=supporting_evidence,
                concerns=concerns,
            ),
            alternative_codes=unique_alternatives,
        )

    except Exception as e:
        raise InternalError(
            message=f"Code validation failed: {str(e)}",
            error_code=ErrorCode.INTERNAL_NLP_ERROR,
        )


# ============================================================================
# Helper Functions
# ============================================================================


def _passes_confidence_threshold(level: ConfidenceLevel, threshold: ConfidenceLevel) -> bool:
    """Check if a confidence level passes the threshold."""
    levels = {ConfidenceLevel.HIGH: 3, ConfidenceLevel.MEDIUM: 2, ConfidenceLevel.LOW: 1}
    return levels[level] >= levels[threshold]


def _confidence_to_score(level: ConfidenceLevel) -> float:
    """Convert confidence level to numeric score."""
    scores = {ConfidenceLevel.HIGH: 0.9, ConfidenceLevel.MEDIUM: 0.7, ConfidenceLevel.LOW: 0.5}
    return scores[level]


def _infer_match_type(match_reason: str) -> str:
    """Infer match type from match reason string."""
    reason_lower = match_reason.lower()
    if "exact" in reason_lower:
        return "exact"
    if "synonym" in reason_lower or "alias" in reason_lower:
        return "synonym"
    if "semantic" in reason_lower or "similar" in reason_lower:
        return "semantic"
    if "partial" in reason_lower or "fuzzy" in reason_lower:
        return "fuzzy"
    return "semantic"
