"""Semantic Search API endpoints.

Provides intelligent search across clinical terminology vocabularies with:
- Natural language semantic search
- Cross-vocabulary mapping (ICD-10 <-> SNOMED <-> RxNorm)
- Similarity search for related concepts
- Autocomplete suggestions
- Result clustering by concept type
"""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, Field

from app.api.errors import ErrorCode, NotFoundError, ValidationError
from app.services.semantic_search_service import (
    ClusterResult,
    CrosswalkMapping,
    MatchType,
    SearchResult,
    SemanticSearchService,
    VocabularyType,
    get_semantic_search_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["Semantic Search"])


# ============================================================================
# Request/Response Models
# ============================================================================


class SemanticSearchRequest(BaseModel):
    """Request body for semantic search."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Natural language search query (e.g., 'heart failure', 'diabetes medications')",
    )
    vocabularies: list[str] | None = Field(
        None,
        description="Vocabularies to search: ICD10CM, SNOMED, RxNorm, CPT4, LOINC, or ALL",
    )
    domains: list[str] | None = Field(
        None,
        description="Clinical domains to filter: Condition, Drug, Procedure, Measurement, Observation",
    )
    top_k: int = Field(
        20,
        ge=1,
        le=100,
        description="Maximum number of results to return",
    )
    threshold: float = Field(
        0.3,
        ge=0.0,
        le=1.0,
        description="Minimum relevance score threshold (0-1)",
    )
    include_fuzzy: bool = Field(
        True,
        description="Include fuzzy matches for typo tolerance",
    )
    expand_query: bool = Field(
        True,
        description="Expand query with synonyms and abbreviations",
    )


class SimilarConceptsRequest(BaseModel):
    """Request body for finding similar concepts."""

    concept_id: int = Field(..., description="Source concept ID to find similar concepts for")
    vocabularies: list[str] | None = Field(
        None,
        description="Target vocabularies to search for similar concepts",
    )
    top_k: int = Field(
        10,
        ge=1,
        le=50,
        description="Maximum number of similar concepts to return",
    )
    threshold: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score threshold",
    )


class CrosswalkRequest(BaseModel):
    """Request body for cross-vocabulary mapping."""

    concept_id: int = Field(..., description="Source concept ID to map")
    target_vocabulary: str = Field(
        ...,
        description="Target vocabulary: ICD10CM, SNOMED, RxNorm, CPT4, LOINC",
    )


class ClusterRequest(BaseModel):
    """Request body for clustering search results."""

    results: list[dict[str, Any]] = Field(
        ...,
        description="Search results to cluster (from semantic search)",
    )


class SearchResultResponse(BaseModel):
    """Single search result in API response."""

    concept_id: int
    concept_code: str
    concept_name: str
    vocabulary_id: str
    domain_id: str
    score: float
    match_type: str
    matched_term: str | None = None
    explanation: str | None = None
    synonyms: list[str] = []
    crosswalk: dict[str, list[dict[str, Any]]] = {}


class SemanticSearchResponse(BaseModel):
    """Response from semantic search."""

    query: str
    expanded_queries: list[str]
    results: list[SearchResultResponse]
    total: int
    vocabularies_searched: list[str]
    search_time_ms: float


class SimilarConceptsResponse(BaseModel):
    """Response from similar concepts search."""

    source_concept_id: int
    source_concept_name: str
    results: list[SearchResultResponse]
    total: int


class CrosswalkMappingResponse(BaseModel):
    """Single crosswalk mapping in API response."""

    source_concept_id: int
    source_vocabulary: str
    source_code: str
    source_name: str
    target_concept_id: int
    target_vocabulary: str
    target_code: str
    target_name: str
    mapping_type: str
    confidence: float


class CrosswalkResponse(BaseModel):
    """Response from crosswalk mapping."""

    source_concept_id: int
    source_vocabulary: str
    source_name: str
    target_vocabulary: str
    mappings: list[CrosswalkMappingResponse]
    total: int


class SuggestionResponse(BaseModel):
    """Single autocomplete suggestion."""

    concept_id: int
    concept_code: str
    concept_name: str
    vocabulary_id: str
    domain_id: str
    display: str


class SuggestionsResponse(BaseModel):
    """Response from autocomplete suggestions."""

    prefix: str
    suggestions: list[SuggestionResponse]
    total: int


class ClusterResultResponse(BaseModel):
    """Single cluster in API response."""

    cluster_id: str
    cluster_name: str
    concept_type: str
    results: list[SearchResultResponse]
    total_count: int


class ClusterResponse(BaseModel):
    """Response from clustering."""

    clusters: list[ClusterResultResponse]
    total_clusters: int
    total_results: int


class ServiceStatsResponse(BaseModel):
    """Service statistics response."""

    total_concepts: int
    vocabularies: dict[str, int]
    domains: dict[str, int]
    unique_codes: int
    indexed_synonyms: int
    load_time_ms: float


# ============================================================================
# Helper Functions
# ============================================================================


def _parse_vocabulary_types(vocabularies: list[str] | None) -> list[VocabularyType] | None:
    """Parse vocabulary strings to VocabularyType enums."""
    if not vocabularies:
        return None

    result = []
    for vocab in vocabularies:
        try:
            if vocab.upper() == "ALL":
                result.append(VocabularyType.ALL)
            else:
                # Try to match vocabulary names
                vocab_upper = vocab.upper()
                if vocab_upper in ("ICD10", "ICD10CM", "ICD-10", "ICD-10-CM"):
                    result.append(VocabularyType.ICD10)
                elif vocab_upper in ("SNOMED", "SNOMEDCT", "SNOMED-CT"):
                    result.append(VocabularyType.SNOMED)
                elif vocab_upper in ("RXNORM", "RX"):
                    result.append(VocabularyType.RXNORM)
                elif vocab_upper in ("CPT", "CPT4", "CPT-4"):
                    result.append(VocabularyType.CPT)
                elif vocab_upper in ("LOINC",):
                    result.append(VocabularyType.LOINC)
                else:
                    logger.warning(f"Unknown vocabulary type: {vocab}")
        except ValueError:
            logger.warning(f"Invalid vocabulary type: {vocab}")

    return result if result else None


def _convert_search_result(result: SearchResult) -> SearchResultResponse:
    """Convert internal SearchResult to API response."""
    return SearchResultResponse(
        concept_id=result.concept_id,
        concept_code=result.concept_code,
        concept_name=result.concept_name,
        vocabulary_id=result.vocabulary_id,
        domain_id=result.domain_id,
        score=round(result.score, 4),
        match_type=result.match_type.value,
        matched_term=result.matched_term,
        explanation=result.explanation,
        synonyms=result.synonyms,
        crosswalk=result.crosswalk,
    )


def _convert_crosswalk_mapping(mapping: CrosswalkMapping) -> CrosswalkMappingResponse:
    """Convert internal CrosswalkMapping to API response."""
    return CrosswalkMappingResponse(
        source_concept_id=mapping.source_concept_id,
        source_vocabulary=mapping.source_vocabulary,
        source_code=mapping.source_code,
        source_name=mapping.source_name,
        target_concept_id=mapping.target_concept_id,
        target_vocabulary=mapping.target_vocabulary,
        target_code=mapping.target_code,
        target_name=mapping.target_name,
        mapping_type=mapping.mapping_type,
        confidence=round(mapping.confidence, 4),
    )


# ============================================================================
# API Endpoints
# ============================================================================


@router.post(
    "/semantic",
    response_model=SemanticSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic search across vocabularies",
    description="""
Search clinical terminologies using natural language. This endpoint supports:

- **Multi-vocabulary search**: Search across ICD-10, SNOMED CT, RxNorm, CPT, and LOINC
- **Semantic matching**: Find concepts even without exact text matches
- **Query expansion**: Automatically expands abbreviations (DM -> diabetes, HTN -> hypertension)
- **Fuzzy matching**: Handles typos and spelling variations
- **Relevance ranking**: Results sorted by TF-IDF and BM25 scores

Example queries:
- "heart failure" - finds CHF, congestive heart failure, cardiac insufficiency
- "diabetes medications" - finds metformin, insulin, GLP-1 agonists
- "MI" - expands to myocardial infarction
    """,
)
async def semantic_search(request: SemanticSearchRequest) -> SemanticSearchResponse:
    """Perform semantic search across clinical vocabularies."""
    import time

    start_time = time.perf_counter()

    logger.info(
        f"Semantic search: query='{request.query}', "
        f"vocabularies={request.vocabularies}, domains={request.domains}"
    )

    service = get_semantic_search_service()

    # Parse vocabulary types
    vocab_types = _parse_vocabulary_types(request.vocabularies)

    # Expand query to show what was searched
    expanded_queries = service.expand_query(request.query) if request.expand_query else [request.query]

    # Perform search
    results = service.search_semantic(
        query=request.query,
        vocabularies=vocab_types,
        domains=request.domains,
        top_k=request.top_k,
        threshold=request.threshold,
        include_fuzzy=request.include_fuzzy,
        expand_query=request.expand_query,
    )

    search_time_ms = (time.perf_counter() - start_time) * 1000

    # Convert results
    converted_results = [_convert_search_result(r) for r in results]

    # Determine which vocabularies were searched
    if request.vocabularies:
        vocabs_searched = request.vocabularies
    else:
        vocabs_searched = ["ICD10CM", "SNOMED", "RxNorm", "CPT4", "LOINC"]

    return SemanticSearchResponse(
        query=request.query,
        expanded_queries=expanded_queries,
        results=converted_results,
        total=len(converted_results),
        vocabularies_searched=vocabs_searched,
        search_time_ms=round(search_time_ms, 2),
    )


@router.post(
    "/similar",
    response_model=SimilarConceptsResponse,
    status_code=status.HTTP_200_OK,
    summary="Find similar concepts",
    description="""
Find concepts semantically similar to a given concept. Useful for:

- **Concept exploration**: Discover related terminology
- **Code alternatives**: Find equivalent codes in the same vocabulary
- **Clinical synonyms**: Identify different ways to express the same condition
    """,
)
async def find_similar_concepts(request: SimilarConceptsRequest) -> SimilarConceptsResponse:
    """Find concepts similar to a given concept."""
    logger.info(f"Find similar: concept_id={request.concept_id}, vocabularies={request.vocabularies}")

    service = get_semantic_search_service()

    # Get source concept
    source = service.get_concept(request.concept_id)
    if not source:
        raise NotFoundError(
            message=f"Concept with ID {request.concept_id} not found",
            error_code=ErrorCode.NOT_FOUND_CONCEPT,
        )

    # Parse vocabulary types
    vocab_types = _parse_vocabulary_types(request.vocabularies)

    # Find similar concepts
    results = service.find_similar(
        concept_id=request.concept_id,
        vocabularies=vocab_types,
        top_k=request.top_k,
        threshold=request.threshold,
    )

    # Convert results
    converted_results = [_convert_search_result(r) for r in results]

    return SimilarConceptsResponse(
        source_concept_id=request.concept_id,
        source_concept_name=source.concept_name,
        results=converted_results,
        total=len(converted_results),
    )


@router.post(
    "/crosswalk",
    response_model=CrosswalkResponse,
    status_code=status.HTTP_200_OK,
    summary="Map between vocabularies",
    description="""
Map a concept from one vocabulary to equivalent concepts in another vocabulary.

Supported mappings:
- **ICD-10 <-> SNOMED CT**: Condition code crosswalks
- **RxNorm <-> NDC**: Drug code crosswalks
- **SNOMED <-> ICD-10**: Diagnosis mappings
- **Any vocabulary pair**: Uses semantic similarity for unmapped concepts
    """,
)
async def crosswalk_mapping(request: CrosswalkRequest) -> CrosswalkResponse:
    """Map a concept to equivalent concepts in another vocabulary."""
    logger.info(f"Crosswalk: concept_id={request.concept_id}, target={request.target_vocabulary}")

    service = get_semantic_search_service()

    # Get source concept
    source = service.get_concept(request.concept_id)
    if not source:
        raise NotFoundError(
            message=f"Concept with ID {request.concept_id} not found",
            error_code=ErrorCode.NOT_FOUND_CONCEPT,
        )

    # Parse target vocabulary
    target_types = _parse_vocabulary_types([request.target_vocabulary])
    if not target_types:
        raise ValidationError(
            message=f"Invalid target vocabulary: {request.target_vocabulary}",
            error_code=ErrorCode.VALIDATION_FIELD_INVALID,
        )

    target_vocab = target_types[0]

    # Get crosswalk mappings
    mappings = service.crosswalk(request.concept_id, target_vocab)

    # Convert mappings
    converted_mappings = [_convert_crosswalk_mapping(m) for m in mappings]

    return CrosswalkResponse(
        source_concept_id=source.concept_id,
        source_vocabulary=source.vocabulary_id,
        source_name=source.concept_name,
        target_vocabulary=request.target_vocabulary,
        mappings=converted_mappings,
        total=len(converted_mappings),
    )


@router.get(
    "/suggest",
    response_model=SuggestionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Autocomplete suggestions",
    description="""
Get autocomplete suggestions for a search prefix. Used for:

- **Search autocomplete**: Real-time suggestions as user types
- **Code lookup**: Find codes by prefix (e.g., "E11" for ICD-10 diabetes codes)
- **Name completion**: Complete partial concept names
    """,
)
async def get_suggestions(
    prefix: Annotated[str, Query(min_length=1, max_length=100, description="Search prefix for autocomplete")],
    vocabularies: Annotated[str | None, Query(description="Comma-separated vocabulary filter")] = None,
    limit: Annotated[int, Query(ge=1, le=50, description="Maximum suggestions")] = 10,
) -> SuggestionsResponse:
    """Get autocomplete suggestions for a prefix."""
    logger.debug(f"Suggestions: prefix='{prefix}', vocabularies={vocabularies}, limit={limit}")

    service = get_semantic_search_service()

    # Parse vocabularies from comma-separated string
    vocab_list = vocabularies.split(",") if vocabularies else None
    vocab_types = _parse_vocabulary_types(vocab_list)

    # Get suggestions
    suggestions = service.get_suggestions(
        prefix=prefix,
        vocabularies=vocab_types,
        limit=limit,
    )

    # Convert to response format
    converted = [
        SuggestionResponse(
            concept_id=s["concept_id"],
            concept_code=s["concept_code"],
            concept_name=s["concept_name"],
            vocabulary_id=s["vocabulary_id"],
            domain_id=s["domain_id"],
            display=s["display"],
        )
        for s in suggestions
    ]

    return SuggestionsResponse(
        prefix=prefix,
        suggestions=converted,
        total=len(converted),
    )


@router.post(
    "/cluster",
    response_model=ClusterResponse,
    status_code=status.HTTP_200_OK,
    summary="Cluster search results",
    description="""
Cluster search results by vocabulary and domain. Useful for:

- **Organized display**: Group results by type (conditions, drugs, procedures)
- **Result exploration**: See distribution across vocabularies
- **Filtering**: Quickly navigate to specific result types
    """,
)
async def cluster_results(request: ClusterRequest) -> ClusterResponse:
    """Cluster search results by concept type."""
    logger.info(f"Clustering {len(request.results)} results")

    # Convert input dicts to SearchResult objects
    results = []
    for r in request.results:
        try:
            results.append(SearchResult(
                concept_id=r.get("concept_id", 0),
                concept_code=r.get("concept_code", ""),
                concept_name=r.get("concept_name", ""),
                vocabulary_id=r.get("vocabulary_id", ""),
                domain_id=r.get("domain_id", ""),
                score=r.get("score", 0.0),
                match_type=MatchType(r.get("match_type", "semantic")),
                matched_term=r.get("matched_term"),
                explanation=r.get("explanation"),
                synonyms=r.get("synonyms", []),
            ))
        except Exception as e:
            logger.warning(f"Error converting result: {e}")
            continue

    service = get_semantic_search_service()
    clusters = service.cluster_results(results)

    # Convert to response format
    converted_clusters = []
    total_results = 0
    for cluster in clusters:
        converted_results = [_convert_search_result(r) for r in cluster.results]
        converted_clusters.append(ClusterResultResponse(
            cluster_id=cluster.cluster_id,
            cluster_name=cluster.cluster_name,
            concept_type=cluster.concept_type,
            results=converted_results,
            total_count=cluster.total_count,
        ))
        total_results += cluster.total_count

    return ClusterResponse(
        clusters=converted_clusters,
        total_clusters=len(converted_clusters),
        total_results=total_results,
    )


@router.get(
    "/stats",
    response_model=ServiceStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get service statistics",
    description="Returns statistics about the semantic search service including loaded vocabularies and concept counts.",
)
async def get_stats() -> ServiceStatsResponse:
    """Get semantic search service statistics."""
    service = get_semantic_search_service()
    stats = service.get_stats()

    return ServiceStatsResponse(
        total_concepts=stats.get("total_concepts", 0),
        vocabularies=stats.get("vocabularies", {}),
        domains=stats.get("domains", {}),
        unique_codes=stats.get("unique_codes", 0),
        indexed_synonyms=stats.get("indexed_synonyms", 0),
        load_time_ms=stats.get("load_time_ms", 0),
    )


@router.get(
    "/concept/{concept_id}",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get concept details",
    description="Get detailed information about a specific concept by ID.",
)
async def get_concept(concept_id: int) -> dict[str, Any]:
    """Get concept details by ID."""
    service = get_semantic_search_service()
    concept = service.get_concept(concept_id)

    if not concept:
        raise NotFoundError(
            message=f"Concept with ID {concept_id} not found",
            error_code=ErrorCode.NOT_FOUND_CONCEPT,
        )

    return {
        "concept_id": concept.concept_id,
        "concept_code": concept.concept_code,
        "concept_name": concept.concept_name,
        "vocabulary_id": concept.vocabulary_id,
        "domain_id": concept.domain_id,
        "concept_class_id": concept.concept_class_id,
        "standard_concept": concept.standard_concept,
        "synonyms": concept.synonyms,
        "semantic_type": concept.semantic_type,
        "parents": concept.parents,
        "children": concept.children,
        "crosswalk_mappings": concept.crosswalk_mappings,
    }
