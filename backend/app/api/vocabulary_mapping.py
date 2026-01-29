"""Vocabulary Mapping API Endpoints.

Provides endpoints for cross-vocabulary translation:
- Map source codes (ICD-10, CPT, NDC) to OMOP standard concepts
- Batch mapping for multiple codes
- Unmapped code reporting
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.vocabulary_mapping import (
    BatchMappingResult,
    MappingResult,
    SourceVocabulary,
    TargetVocabulary,
    VocabularyMappingService,
)

router = APIRouter(prefix="/vocabulary-mapping", tags=["Vocabulary Mapping"])


# ============================================================================
# Request/Response Models
# ============================================================================


class MapCodeRequest(BaseModel):
    """Request to map a source code to OMOP standard concept."""

    code: str = Field(..., description="The source code (e.g., 'J18.9' for ICD-10)")
    source_vocabulary: str = Field(
        ..., description="Source vocabulary (ICD10CM, CPT4, NDC, etc.)"
    )
    target_vocabulary: str | None = Field(
        None, description="Target vocabulary override (default: auto-select)"
    )


class MapCodeResponse(BaseModel):
    """Response from single code mapping."""

    source_code: str
    source_vocabulary: str
    source_concept_id: int | None = None
    source_concept_name: str | None = None
    target_concept_id: int | None = None
    target_concept_name: str | None = None
    target_vocabulary: str | None = None
    mapping_type: str
    confidence: str
    confidence_score: float
    relationship_id: str | None = None
    is_mapped: bool
    unmapped_reason: str | None = None


class BatchMapRequest(BaseModel):
    """Request to map multiple codes."""

    codes: list[MapCodeRequest] = Field(
        ..., min_length=1, max_length=1000, description="List of codes to map"
    )


class BatchMapResponse(BaseModel):
    """Response from batch mapping."""

    total_codes: int
    mapped_count: int
    unmapped_count: int
    mapping_rate: float
    high_confidence_count: int
    medium_confidence_count: int
    low_confidence_count: int
    results: list[MapCodeResponse]
    unmapped_codes: list[str]


class UnmappedReportRequest(BaseModel):
    """Request for unmapped code report."""

    codes: list[MapCodeRequest] = Field(
        ..., min_length=1, max_length=5000, description="List of codes to check"
    )


class UnmappedReportResponse(BaseModel):
    """Response with unmapped code report."""

    total_codes: int
    unmapped_count: int
    unmapped_rate: float
    unmapped_by_vocabulary: dict[str, list[str]]
    unmapped_codes: list[str]
    suggestion: str


# ============================================================================
# Helper Functions
# ============================================================================


def _result_to_response(result: MappingResult) -> MapCodeResponse:
    """Convert MappingResult to API response model."""
    return MapCodeResponse(
        source_code=result.source_code,
        source_vocabulary=result.source_vocabulary,
        source_concept_id=result.source_concept_id,
        source_concept_name=result.source_concept_name,
        target_concept_id=result.target_concept_id,
        target_concept_name=result.target_concept_name,
        target_vocabulary=result.target_vocabulary,
        mapping_type=result.mapping_type.value,
        confidence=result.confidence.value,
        confidence_score=result.confidence_score,
        relationship_id=result.relationship_id,
        is_mapped=result.is_mapped,
        unmapped_reason=result.unmapped_reason,
    )


def _batch_result_to_response(result: BatchMappingResult) -> BatchMapResponse:
    """Convert BatchMappingResult to API response model."""
    return BatchMapResponse(
        total_codes=result.total_codes,
        mapped_count=result.mapped_count,
        unmapped_count=result.unmapped_count,
        mapping_rate=round(result.mapping_rate, 3),
        high_confidence_count=result.high_confidence_count,
        medium_confidence_count=result.medium_confidence_count,
        low_confidence_count=result.low_confidence_count,
        results=[_result_to_response(r) for r in result.results],
        unmapped_codes=result.unmapped_codes,
    )


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "/map",
    response_model=MapCodeResponse,
    summary="Map a source code to OMOP standard concept",
    description="Translate a code from source vocabulary (ICD-10, CPT, NDC, etc.) "
    "to the corresponding OMOP standard concept (SNOMED, RxNorm, LOINC).",
)
async def map_code(request: MapCodeRequest) -> MapCodeResponse:
    """Map a single source code to OMOP standard concept.

    This endpoint uses OMOP concept_relationship data to find the standard
    concept that the source code maps to.

    Supported source vocabularies:
    - ICD10CM → SNOMED CT (conditions)
    - ICD10PCS → SNOMED CT (procedures)
    - CPT4 → SNOMED CT (procedures)
    - NDC → RxNorm (drugs)
    - LOINC → LOINC (measurements)

    Args:
        request: The source code and vocabulary

    Returns:
        Mapping result with confidence score and target concept
    """
    try:
        source_vocab = SourceVocabulary(request.source_vocabulary)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source vocabulary: {request.source_vocabulary}. "
            f"Valid options: {[v.value for v in SourceVocabulary]}",
        )

    target_vocab = None
    if request.target_vocabulary:
        try:
            target_vocab = TargetVocabulary(request.target_vocabulary)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid target vocabulary: {request.target_vocabulary}. "
                f"Valid options: {[v.value for v in TargetVocabulary]}",
            )

    service = VocabularyMappingService()
    result = service.map_code(request.code, source_vocab, target_vocab)

    return _result_to_response(result)


@router.post(
    "/batch",
    response_model=BatchMapResponse,
    summary="Map multiple codes in batch",
    description="Efficiently map multiple source codes to OMOP standard concepts.",
)
async def batch_map_codes(request: BatchMapRequest) -> BatchMapResponse:
    """Map multiple source codes to OMOP standard concepts.

    This endpoint processes multiple codes efficiently and returns
    mapping statistics along with individual results.

    Args:
        request: List of codes to map

    Returns:
        Batch mapping result with statistics and individual mappings
    """
    codes = []
    for code_req in request.codes:
        try:
            source_vocab = SourceVocabulary(code_req.source_vocabulary)
            codes.append((code_req.code, source_vocab))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid source vocabulary: {code_req.source_vocabulary}",
            )

    service = VocabularyMappingService()
    result = service.batch_map_codes(codes)

    return _batch_result_to_response(result)


@router.post(
    "/unmapped-report",
    response_model=UnmappedReportResponse,
    summary="Generate unmapped code report",
    description="Analyze a set of codes and report which ones cannot be mapped.",
)
async def get_unmapped_report(
    request: UnmappedReportRequest,
) -> UnmappedReportResponse:
    """Generate a report of unmapped codes.

    This endpoint is useful for identifying codes that need local
    mapping definitions or vocabulary updates.

    Args:
        request: List of codes to check

    Returns:
        Report with unmapped code details organized by vocabulary
    """
    codes = []
    for code_req in request.codes:
        try:
            source_vocab = SourceVocabulary(code_req.source_vocabulary)
            codes.append((code_req.code, source_vocab))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid source vocabulary: {code_req.source_vocabulary}",
            )

    service = VocabularyMappingService()
    report = service.get_unmapped_report(codes)

    return UnmappedReportResponse(
        total_codes=report["total_codes"],
        unmapped_count=report["unmapped_count"],
        unmapped_rate=round(report["unmapped_rate"], 3),
        unmapped_by_vocabulary=report["unmapped_by_vocabulary"],
        unmapped_codes=report["unmapped_codes"],
        suggestion=report["suggestion"],
    )


@router.get(
    "/vocabularies/source",
    summary="List supported source vocabularies",
    description="Get list of vocabularies that can be mapped from.",
)
async def list_source_vocabularies() -> list[str]:
    """List supported source vocabularies."""
    return [v.value for v in SourceVocabulary]


@router.get(
    "/vocabularies/target",
    summary="List supported target vocabularies",
    description="Get list of standard vocabularies that can be mapped to.",
)
async def list_target_vocabularies() -> list[str]:
    """List supported target vocabularies."""
    return [v.value for v in TargetVocabulary]
