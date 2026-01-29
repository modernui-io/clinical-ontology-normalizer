"""Document Search API endpoints - Search and filter endpoints."""

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents", "search"])


# ============================================================================
# Enhanced Vocabulary Search Endpoint
# ============================================================================


class VocabularySearchRequest(BaseModel):
    """Request body for vocabulary search."""

    query: str = Field(..., description="Search query (term, abbreviation, or natural language)")
    limit: int = Field(10, ge=1, le=100, description="Maximum number of results")
    use_semantic: bool = Field(False, description="Use semantic similarity search (slower but finds related terms)")


class VocabularyConceptResult(BaseModel):
    """A single vocabulary concept result."""

    concept_id: int = Field(..., description="OMOP concept ID")
    concept_name: str = Field(..., description="Standard concept name")
    concept_code: str = Field(..., description="Source vocabulary code")
    vocabulary_id: str = Field(..., description="Source vocabulary (SNOMED, RxNorm, etc.)")
    domain: str = Field(..., description="OMOP domain (Condition, Drug, Measurement, etc.)")
    synonyms: list[str] = Field(..., description="All known synonyms")
    similarity_score: float | None = Field(None, description="Similarity score (for semantic search)")


class VocabularySearchResponse(BaseModel):
    """Response from vocabulary search."""

    results: list[VocabularyConceptResult] = Field(..., description="Matching concepts")
    search_time_ms: float = Field(..., description="Time taken for search in ms")
    result_count: int = Field(..., description="Number of results returned")
    search_mode: str = Field(..., description="Search mode used (text or semantic)")
    stats: dict[str, int | bool] = Field(..., description="Vocabulary statistics")


@router.post(
    "/vocabulary/search",
    response_model=VocabularySearchResponse,
    summary="Search enhanced OMOP vocabulary",
    description="Search for OMOP concepts using text matching or semantic similarity.",
)
async def search_vocabulary(
    request: VocabularySearchRequest,
) -> VocabularySearchResponse:
    """Search the enhanced OMOP vocabulary.

    This endpoint provides two search modes:
    - **Text search**: Fast exact and partial matching against concept names and synonyms.
      Automatically expands clinical abbreviations (HTN->hypertension, DM->diabetes, etc.)
    - **Semantic search**: Uses sentence embeddings to find conceptually similar terms.
      Useful for natural language queries like "sugar disease" -> diabetes.

    The vocabulary includes:
    - 269+ concepts across Conditions, Drugs, Measurements, Procedures
    - UMLS-style synonym expansion with 100+ clinical abbreviations
    - American/British spelling variations (anemia/anaemia, tumor/tumour)

    Args:
        request: Search query and options.

    Returns:
        VocabularySearchResponse with matching concepts and statistics.
    """
    import time
    from app.services.vocabulary_enhanced import get_enhanced_vocabulary_service

    start_time = time.perf_counter()

    # Get enhanced vocabulary service
    service = get_enhanced_vocabulary_service(
        use_embeddings=request.use_semantic,
        use_automaton=False,  # Not needed for search
    )

    results: list[VocabularyConceptResult] = []
    search_mode = "text"

    if request.use_semantic:
        # Semantic similarity search
        search_mode = "semantic"
        matches = service.semantic_search(request.query, limit=request.limit)
        for concept, score in matches:
            results.append(
                VocabularyConceptResult(
                    concept_id=concept.concept_id,
                    concept_name=concept.concept_name,
                    concept_code=concept.concept_code,
                    vocabulary_id=concept.vocabulary_id,
                    domain=concept.domain.value if hasattr(concept.domain, "value") else str(concept.domain),
                    synonyms=concept.synonyms[:10],  # Limit synonyms for response size
                    similarity_score=round(score, 4),
                )
            )
    else:
        # Fast text search
        matches = service.search(request.query, limit=request.limit)
        for concept in matches:
            results.append(
                VocabularyConceptResult(
                    concept_id=concept.concept_id,
                    concept_name=concept.concept_name,
                    concept_code=concept.concept_code,
                    vocabulary_id=concept.vocabulary_id,
                    domain=concept.domain.value if hasattr(concept.domain, "value") else str(concept.domain),
                    synonyms=concept.synonyms[:10],
                    similarity_score=None,
                )
            )

    search_time_ms = (time.perf_counter() - start_time) * 1000

    # Get vocabulary statistics
    stats = service.get_enhanced_stats()

    return VocabularySearchResponse(
        results=results,
        search_time_ms=round(search_time_ms, 2),
        result_count=len(results),
        search_mode=search_mode,
        stats=stats,
    )


# ============================================================================
# Semantic Search & QA Endpoints
# ============================================================================


class SearchRequest(BaseModel):
    """Request for semantic search."""

    query: str = Field(..., description="Search query")
    patient_id: str | None = Field(None, description="Filter by patient")
    search_type: str = Field("hybrid", description="keyword, semantic, hybrid")
    max_results: int = Field(10, description="Maximum results")


class SearchResultResponse(BaseModel):
    """A search result."""

    document_id: str
    content: str
    score: float
    highlights: list[str] = []


class SearchResponse(BaseModel):
    """Search response."""

    query: str
    search_type: str
    results: list[SearchResultResponse]
    total_results: int
    search_time_ms: float
    suggestions: list[str] = []


class QARequest(BaseModel):
    """Request for question answering."""

    question: str = Field(..., description="Question to answer")
    patient_id: str | None = Field(None, description="Patient context")
    context: str | None = Field(None, description="Additional context")


class AnswerResponse(BaseModel):
    """Answer with evidence."""

    text: str
    confidence: float
    evidence: list[str]
    source_documents: list[str]


class QAResponse(BaseModel):
    """QA response."""

    question: str
    question_type: str
    answer: AnswerResponse
    related_concepts: list[str]
    follow_up_questions: list[str]
    response_time_ms: float


@router.post(
    "/search/semantic",
    response_model=SearchResponse,
    tags=["search"],
    summary="Semantic search over clinical notes",
)
async def semantic_search(
    request: SearchRequest,
) -> SearchResponse:
    """Perform semantic search over indexed clinical notes."""
    from app.services.semantic_qa import SemanticQAService, SearchType

    service = SemanticQAService()

    search_type_map = {
        "keyword": SearchType.KEYWORD,
        "semantic": SearchType.SEMANTIC,
        "hybrid": SearchType.HYBRID,
    }

    result = service.search(
        request.query,
        search_type_map.get(request.search_type, SearchType.HYBRID),
        patient_id=request.patient_id,
        max_results=request.max_results,
    )

    return SearchResponse(
        query=result.query,
        search_type=result.search_type.value,
        results=[
            SearchResultResponse(
                document_id=r.document_id,
                content=r.content,
                score=r.score,
                highlights=r.highlights,
            )
            for r in result.results
        ],
        total_results=result.total_results,
        search_time_ms=result.search_time_ms,
        suggestions=result.suggestions,
    )


@router.post(
    "/search/qa",
    response_model=QAResponse,
    tags=["search"],
    summary="Answer clinical questions",
)
async def answer_question(
    request: QARequest,
) -> QAResponse:
    """Answer a clinical question using indexed documents."""
    from app.services.semantic_qa import SemanticQAService

    service = SemanticQAService()

    result = service.answer_question(
        request.question,
        patient_id=request.patient_id,
        context=request.context,
    )

    return QAResponse(
        question=result.question,
        question_type=result.question_type.value,
        answer=AnswerResponse(
            text=result.answer.text,
            confidence=result.answer.confidence,
            evidence=result.answer.evidence,
            source_documents=result.answer.source_documents,
        ),
        related_concepts=result.related_concepts,
        follow_up_questions=result.follow_up_questions,
        response_time_ms=result.response_time_ms,
    )
