"""Knowledge Graph API Endpoints.

Provides endpoints for:
- Neo4j connection health and status
- Concept neighbors and hierarchy traversal
- Path finding between concepts
- Multi-hop reasoning (DR.KNOWS pattern)
- Evidence aggregation and path scoring
- Patient similarity analysis
- Patient knowledge graph extraction
- Graph statistics and analytics
- Admin Cypher query execution
"""

import hashlib
import json
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Query, Body, HTTPException, Depends
from pydantic import BaseModel, Field

from app.api.errors import ErrorCode, InternalError, NotFoundError
from app.api.middleware.auth_middleware import CurrentUser, require_admin
from app.services.kg_cache_service import get_kg_cache_service, CacheType

router = APIRouter(prefix="/graph", tags=["Knowledge Graph"])
reasoning_router = APIRouter(prefix="/graph/reasoning", tags=["Knowledge Graph Reasoning"])


# ============================================================================
# Enums
# ============================================================================


class NodeCategoryAPI(str, Enum):
    """Categories of nodes for filtering."""

    CONDITION = "Condition"
    DRUG = "Drug"
    PROCEDURE = "Procedure"
    MEASUREMENT = "Measurement"
    OBSERVATION = "Observation"
    GENE = "Gene"
    PATHWAY = "Pathway"
    ALL = "All"


class SimilarityMetricAPI(str, Enum):
    """Metrics for measuring similarity."""

    JACCARD = "jaccard"
    COSINE = "cosine"
    OVERLAP = "overlap"
    DICE = "dice"


class ConnectionStatusAPI(str, Enum):
    """Connection status values."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    MOCK_MODE = "mock_mode"


class SemanticGroupAPI(str, Enum):
    """UMLS Semantic Groups for filtering reasoning paths."""

    ANAT = "ANAT"  # Anatomy
    CHEM = "CHEM"  # Chemicals & Drugs
    DISO = "DISO"  # Disorders
    GENE = "GENE"  # Genes & Molecular Sequences
    GEOG = "GEOG"  # Geographic Areas
    LIVB = "LIVB"  # Living Beings
    OBJC = "OBJC"  # Objects
    OCCU = "OCCU"  # Occupations
    ORGA = "ORGA"  # Organizations
    PHEN = "PHEN"  # Phenomena
    PHYS = "PHYS"  # Physiology
    PROC = "PROC"  # Procedures
    CONC = "CONC"  # Concepts & Ideas


# ============================================================================
# Request/Response Models
# ============================================================================


class HealthResponse(BaseModel):
    """Response for health check endpoint."""

    status: ConnectionStatusAPI = Field(..., description="Connection status")
    latency_ms: float | None = Field(None, description="Connection latency in ms")
    server_version: str | None = Field(None, description="Neo4j server version")
    database: str | None = Field(None, description="Database name")
    error_message: str | None = Field(None, description="Error message if any")
    checked_at: str = Field(..., description="Timestamp of health check")


class ConceptResponse(BaseModel):
    """A concept node response."""

    concept_id: int = Field(..., description="OMOP concept ID")
    concept_name: str = Field(..., description="Concept name")
    vocabulary_id: str = Field(..., description="Source vocabulary")
    domain_id: str = Field(..., description="Clinical domain")
    concept_class_id: str | None = Field(None, description="Concept class")
    synonyms: list[str] = Field(default_factory=list, description="Concept synonyms")


class NeighborResponse(BaseModel):
    """A concept neighbor response."""

    concept: ConceptResponse = Field(..., description="Neighboring concept")
    relationship: str = Field(..., description="Relationship type")
    direction: str = Field(..., description="Relationship direction (incoming/outgoing)")


class NeighborsListResponse(BaseModel):
    """Response for concept neighbors."""

    request_id: str = Field(..., description="Request identifier")
    concept_id: int = Field(..., description="Source concept ID")
    total_neighbors: int = Field(..., description="Total neighbors returned")
    neighbors: list[NeighborResponse] = Field(..., description="List of neighbors")
    processing_time_ms: float = Field(..., description="Processing time in ms")


class AncestorResponse(BaseModel):
    """A concept ancestor response."""

    ancestor: ConceptResponse = Field(..., description="Ancestor concept")
    distance: int = Field(..., description="Distance from source concept")


class AncestorsListResponse(BaseModel):
    """Response for concept ancestors."""

    request_id: str = Field(..., description="Request identifier")
    concept_id: int = Field(..., description="Source concept ID")
    total_ancestors: int = Field(..., description="Total ancestors returned")
    ancestors: list[AncestorResponse] = Field(..., description="List of ancestors")
    processing_time_ms: float = Field(..., description="Processing time in ms")


class PathRequest(BaseModel):
    """Request for finding path between concepts."""

    start_concept_id: int = Field(..., description="Starting concept ID")
    end_concept_id: int = Field(..., description="Ending concept ID")
    max_length: int = Field(5, ge=1, le=10, description="Maximum path length")


class PathResponse(BaseModel):
    """Response for concept path."""

    request_id: str = Field(..., description="Request identifier")
    start_concept: ConceptResponse = Field(..., description="Starting concept")
    end_concept: ConceptResponse = Field(..., description="Ending concept")
    path_nodes: list[ConceptResponse] = Field(..., description="Nodes in path")
    path_relationships: list[str] = Field(..., description="Relationships in path")
    path_length: int = Field(..., description="Path length")
    found: bool = Field(..., description="Whether a path was found")
    processing_time_ms: float = Field(..., description="Processing time in ms")


class SimilarPatientResponse(BaseModel):
    """A similar patient response."""

    patient_id: str = Field(..., description="Patient identifier")
    similarity_score: float = Field(..., ge=0, le=1, description="Similarity score (0-1)")
    shared_conditions: list[str] = Field(..., description="Shared conditions")
    shared_medications: list[str] = Field(..., description="Shared medications")
    shared_procedures: list[str] = Field(..., description="Shared procedures")
    total_shared_features: int = Field(..., description="Total shared features")


class SimilarPatientsResponse(BaseModel):
    """Response for similar patients."""

    request_id: str = Field(..., description="Request identifier")
    patient_id: str = Field(..., description="Reference patient ID")
    total_similar: int = Field(..., description="Total similar patients found")
    similar_patients: list[SimilarPatientResponse] = Field(..., description="Similar patients")
    metric_used: SimilarityMetricAPI = Field(..., description="Similarity metric used")
    processing_time_ms: float = Field(..., description="Processing time in ms")


class GraphEdgeResponse(BaseModel):
    """A graph edge response."""

    source_id: int | str = Field(..., description="Source node ID")
    target_id: int | str = Field(..., description="Target node ID")
    relationship_type: str = Field(..., description="Relationship type")
    properties: dict[str, Any] = Field(default_factory=dict, description="Edge properties")


class PatientSubgraphResponse(BaseModel):
    """Response for patient subgraph."""

    request_id: str = Field(..., description="Request identifier")
    patient_id: str = Field(..., description="Patient identifier")
    nodes: list[ConceptResponse] = Field(..., description="Nodes in subgraph")
    edges: list[GraphEdgeResponse] = Field(..., description="Edges in subgraph")
    node_count: int = Field(..., description="Total node count")
    edge_count: int = Field(..., description="Total edge count")
    conditions_count: int = Field(..., description="Condition count")
    drugs_count: int = Field(..., description="Drug count")
    procedures_count: int = Field(..., description="Procedure count")
    measurements_count: int = Field(..., description="Measurement count")
    processing_time_ms: float = Field(..., description="Processing time in ms")


class CypherQueryRequest(BaseModel):
    """Request for executing a Cypher query (admin only)."""

    query: str = Field(..., description="Cypher query to execute")
    parameters: dict[str, Any] | None = Field(None, description="Query parameters")


class CypherQueryResponse(BaseModel):
    """Response for Cypher query execution."""

    request_id: str = Field(..., description="Request identifier")
    query: str = Field(..., description="Executed query")
    records: list[dict[str, Any]] = Field(..., description="Result records")
    record_count: int = Field(..., description="Number of records")
    execution_time_ms: float = Field(..., description="Query execution time in ms")


class GraphStatsResponse(BaseModel):
    """Response for graph statistics."""

    request_id: str = Field(..., description="Request identifier")
    graph_connected: bool = Field(..., description="Whether connected to Neo4j")
    mock_mode: bool = Field(..., description="Whether running in mock mode")
    total_concepts: int = Field(..., description="Total concept count")
    total_patients: int = Field(..., description="Total patient count")
    total_relationships: int = Field(..., description="Total relationship count")
    concepts_by_domain: dict[str, int] = Field(..., description="Concepts by domain")
    relationship_types: dict[str, int] = Field(..., description="Relationship type counts")


# ============================================================================
# Multi-hop Reasoning Models (DR.KNOWS Pattern)
# ============================================================================


class MultiHopRequest(BaseModel):
    """Request for multi-hop reasoning queries.

    Implements the DR.KNOWS pattern for traversing the clinical knowledge graph
    to find treatment paths, related conditions, and supporting evidence.
    """

    seed_concepts: list[int] = Field(
        ...,
        description="List of OMOP concept IDs to start reasoning from",
        min_length=1,
        max_length=10,
    )
    max_hops: int = Field(
        5,
        ge=1,
        le=10,
        description="Maximum path length (hops) to traverse",
    )
    semantic_groups: list[SemanticGroupAPI] | None = Field(
        None,
        description="Filter target nodes by UMLS semantic groups (e.g., DISO, CHEM, PROC)",
    )
    target_domains: list[str] | None = Field(
        None,
        description="Filter target nodes by OMOP domain_id (e.g., Condition, Drug, Procedure)",
    )
    min_confidence: float = Field(
        0.1,
        ge=0.0,
        le=1.0,
        description="Minimum path confidence score (0-1)",
    )
    top_k: int = Field(
        20,
        ge=1,
        le=100,
        description="Maximum number of paths to return",
    )
    include_evidence: bool = Field(
        True,
        description="Include supporting evidence metadata in response",
    )


class ReasoningNodeResponse(BaseModel):
    """A node in a reasoning path."""

    concept_id: int = Field(..., description="OMOP concept ID")
    concept_name: str = Field(..., description="Concept name")
    vocabulary_id: str = Field(..., description="Source vocabulary (SNOMED, RxNorm, etc.)")
    domain_id: str = Field(..., description="OMOP domain (Condition, Drug, etc.)")
    semantic_group: str | None = Field(None, description="UMLS semantic group")
    semantic_type: str | None = Field(None, description="UMLS semantic type code")


class ReasoningEdgeResponse(BaseModel):
    """An edge (relationship) in a reasoning path."""

    relationship_type: str = Field(..., description="Relationship type (e.g., IS_A, TREATS)")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Edge confidence score")
    source_vocabulary: str | None = Field(None, description="Vocabulary source for relationship")


class ReasoningPathResponse(BaseModel):
    """A single reasoning path from seed to target."""

    path_id: str = Field(..., description="Unique path identifier")
    nodes: list[ReasoningNodeResponse] = Field(..., description="Nodes in the path")
    edges: list[ReasoningEdgeResponse] = Field(..., description="Edges connecting nodes")
    hops: int = Field(..., description="Number of hops in path")
    score: float = Field(..., ge=0.0, le=1.0, description="Overall path confidence score")
    semantic_coherence: float = Field(
        1.0,
        ge=0.0,
        le=1.0,
        description="Semantic coherence score based on type transitions",
    )


class EvidenceAggregation(BaseModel):
    """Aggregated evidence from multiple reasoning paths."""

    conclusion_concept_id: int = Field(..., description="Target concept ID")
    conclusion_name: str = Field(..., description="Target concept name")
    total_paths: int = Field(..., description="Number of paths supporting this conclusion")
    avg_confidence: float = Field(..., description="Average confidence across paths")
    semantic_types: list[str] = Field(..., description="Unique semantic types reached")
    reasoning_summary: str = Field(..., description="Human-readable reasoning summary")


class MultiHopResponse(BaseModel):
    """Response for multi-hop reasoning queries."""

    request_id: str = Field(..., description="Request identifier")
    seed_concepts: list[int] = Field(..., description="Input seed concept IDs")
    total_paths: int = Field(..., description="Total paths found")
    paths: list[ReasoningPathResponse] = Field(..., description="Reasoning paths")
    evidence: list[EvidenceAggregation] | None = Field(
        None,
        description="Aggregated evidence (if include_evidence=True)",
    )
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    truncated: bool = Field(False, description="Whether results were truncated to top_k")
    cached: bool = Field(False, description="Whether result was served from cache")


class ScorePathsRequest(BaseModel):
    """Request for scoring reasoning paths."""

    paths: list[list[int]] = Field(
        ...,
        description="List of paths, each path is a list of concept IDs",
        min_length=1,
        max_length=50,
    )
    scoring_method: str = Field(
        "confidence_decay",
        description="Scoring method: confidence_decay, semantic_coherence, hybrid",
    )
    decay_factor: float = Field(
        0.9,
        ge=0.5,
        le=1.0,
        description="Decay factor per hop for confidence_decay method",
    )


class ScoredPathResponse(BaseModel):
    """A path with its computed score."""

    path: list[ReasoningNodeResponse] = Field(..., description="Nodes in the path")
    score: float = Field(..., ge=0.0, le=1.0, description="Computed score")
    confidence_component: float = Field(..., description="Confidence-based score component")
    coherence_component: float = Field(..., description="Semantic coherence component")
    breakdown: dict[str, float] = Field(..., description="Score breakdown by component")


class ScorePathsResponse(BaseModel):
    """Response for path scoring."""

    request_id: str = Field(..., description="Request identifier")
    scored_paths: list[ScoredPathResponse] = Field(..., description="Scored paths")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")


# ============================================================================
# Temporal Graph Reasoning Models
# ============================================================================


class TreatmentPathRequest(BaseModel):
    """Request for finding treatment paths for a condition."""

    condition_concept_id: int = Field(
        ...,
        description="OMOP concept ID of the condition to find treatments for",
    )
    max_hops: int = Field(
        3,
        ge=1,
        le=5,
        description="Maximum hops to search for treatments",
    )
    top_k: int = Field(
        10,
        ge=1,
        le=50,
        description="Maximum number of treatment paths to return",
    )


class ContraindicationCheckRequest(BaseModel):
    """Request for checking drug contraindications."""

    drug_concept_id: int = Field(
        ...,
        description="OMOP concept ID of the drug to check",
    )
    patient_condition_ids: list[int] = Field(
        ...,
        description="List of patient's current condition concept IDs",
        min_length=1,
    )


class TreatmentPathResult(BaseModel):
    """A treatment path result."""

    drug_concept_id: int = Field(..., description="Target drug concept ID")
    drug_name: str = Field(..., description="Drug name")
    path_score: float = Field(..., description="Path confidence score")
    hops: int = Field(..., description="Number of hops")
    path_nodes: list[ReasoningNodeResponse] = Field(..., description="Nodes in path")
    evidence_sources: list[str] = Field(default_factory=list, description="Evidence sources")


class TreatmentPathResponse(BaseModel):
    """Response for treatment path search."""

    request_id: str = Field(..., description="Request identifier")
    condition_concept_id: int = Field(..., description="Input condition ID")
    condition_name: str = Field(..., description="Condition name")
    treatment_paths: list[TreatmentPathResult] = Field(..., description="Treatment paths found")
    total_paths: int = Field(..., description="Total paths found")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")


class ContraindicationResult(BaseModel):
    """A contraindication result."""

    condition_concept_id: int = Field(..., description="Contraindicated condition ID")
    condition_name: str = Field(..., description="Condition name")
    relationship_type: str = Field(..., description="Type of contraindication relationship")
    severity: str = Field("moderate", description="Severity: low, moderate, high, critical")
    evidence_path: list[str] = Field(..., description="Path explaining contraindication")


class ContraindicationResponse(BaseModel):
    """Response for contraindication check."""

    request_id: str = Field(..., description="Request identifier")
    drug_concept_id: int = Field(..., description="Input drug ID")
    drug_name: str = Field(..., description="Drug name")
    contraindications: list[ContraindicationResult] = Field(
        ...,
        description="Found contraindications",
    )
    is_safe: bool = Field(..., description="True if no contraindications found")
    total_checked: int = Field(..., description="Total conditions checked")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")


class EvidenceAggregationRequest(BaseModel):
    """Request for aggregating evidence from reasoning paths."""

    seed_concept_ids: list[int] = Field(
        ...,
        description="Seed concepts to start reasoning from",
        min_length=1,
        max_length=10,
    )
    question_type: str = Field(
        "treatment",
        description="Type of question: treatment, diagnosis, prognosis",
    )
    max_hops: int = Field(4, ge=1, le=6, description="Maximum hops for reasoning")
    top_k_paths: int = Field(20, ge=1, le=100, description="Top paths to consider")


class EvidenceConclusion(BaseModel):
    """An evidence-supported conclusion."""

    concept_id: int = Field(..., description="Conclusion concept ID")
    concept_name: str = Field(..., description="Conclusion concept name")
    confidence: float = Field(..., description="Confidence score")
    supporting_paths: int = Field(..., description="Number of supporting paths")
    semantic_types: list[str] = Field(..., description="Semantic types reached")
    reasoning_chain: list[str] = Field(..., description="Simplified reasoning chain")


class EvidenceAggregationResponse(BaseModel):
    """Response for evidence aggregation."""

    request_id: str = Field(..., description="Request identifier")
    seed_concepts: list[int] = Field(..., description="Input seed concepts")
    question_type: str = Field(..., description="Question type processed")
    conclusions: list[EvidenceConclusion] = Field(..., description="Evidence conclusions")
    total_paths_analyzed: int = Field(..., description="Total paths analyzed")
    unique_conclusions: int = Field(..., description="Unique conclusions found")
    avg_confidence: float = Field(..., description="Average confidence")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")


# ============================================================================
# API Endpoints
# ============================================================================


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check Neo4j connection health",
    description="Returns the status of the Neo4j database connection.",
)
async def health_check() -> HealthResponse:
    """Check Neo4j connection health.

    Returns connection status, latency, and server information.
    """
    try:
        from app.services.graph_database_service import get_graph_database_service

        service = get_graph_database_service()
        result = service.health_check()

        return HealthResponse(
            status=ConnectionStatusAPI(result.status.value),
            latency_ms=result.latency_ms,
            server_version=result.server_version,
            database=result.database,
            error_message=result.error_message,
            checked_at=result.checked_at,
        )

    except Exception as e:
        return HealthResponse(
            status=ConnectionStatusAPI.ERROR,
            error_message=str(e),
            checked_at=datetime.now(timezone.utc).isoformat(),
        )


@router.get(
    "/cache/stats",
    summary="Get cache statistics",
    description="Returns statistics about the query cache including hit rate and memory usage.",
)
async def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics.

    Returns hit rate, memory usage, and cache size information.
    """
    cache_service = get_kg_cache_service()
    stats = cache_service.get_stats()
    return stats.to_dict()


@router.delete(
    "/cache/clear",
    summary="Clear the query cache",
    description="Clears all cached query results. Use sparingly.",
)
async def clear_cache() -> dict[str, Any]:
    """Clear the query cache.

    Returns the number of entries cleared.
    """
    cache_service = get_kg_cache_service()
    cleared = cache_service.clear()
    return {"cleared": cleared, "message": f"Cleared {cleared} cache entries"}


@router.get(
    "/concepts/{concept_id}/neighbors",
    response_model=NeighborsListResponse,
    summary="Get related concepts",
    description="Returns concepts related to the specified concept.",
)
async def get_concept_neighbors(
    concept_id: int,
    max_depth: int = Query(1, ge=1, le=3, description="Maximum relationship depth"),
    categories: list[NodeCategoryAPI] | None = Query(None, description="Filter by categories"),
    limit: int = Query(50, ge=1, le=200, description="Maximum neighbors to return"),
) -> NeighborsListResponse:
    """Get neighboring concepts for a given concept.

    Args:
        concept_id: The OMOP concept ID to find neighbors for.
        max_depth: Maximum relationship depth to traverse.
        categories: Optional list of categories to filter by.
        limit: Maximum number of neighbors to return.

    Returns:
        NeighborsListResponse with related concepts.
    """
    start_time = time.perf_counter()
    request_id = str(uuid4())

    try:
        from app.services.graph_analytics_service import (
            get_graph_analytics_service,
            NodeCategory,
        )

        # Check cache
        cache_service = get_kg_cache_service()
        cat_str = ",".join(sorted(c.value for c in categories)) if categories else ""
        cache_key = f"neighbors:{concept_id}:{max_depth}:{cat_str}:{limit}"
        cached = cache_service.get(CacheType.RELATIONSHIP, cache_key)
        if cached:
            cached["request_id"] = request_id
            return NeighborsListResponse(**cached)

        service = get_graph_analytics_service()

        # Convert API categories to service categories
        cat_filter = None
        if categories:
            cat_filter = [NodeCategory(c.value) for c in categories]

        neighbors = service.get_concept_neighbors(
            concept_id=concept_id,
            max_depth=max_depth,
            categories=cat_filter,
            limit=limit,
        )

        processing_time = (time.perf_counter() - start_time) * 1000

        neighbor_responses = []
        for n in neighbors:
            concept = n.get("concept", {})
            neighbor_responses.append(NeighborResponse(
                concept=ConceptResponse(
                    concept_id=concept.get("concept_id", 0),
                    concept_name=concept.get("concept_name", ""),
                    vocabulary_id=concept.get("vocabulary_id", ""),
                    domain_id=concept.get("domain_id", ""),
                ),
                relationship=n.get("relationship", "RELATED"),
                direction=n.get("direction", "outgoing"),
            ))

        result = NeighborsListResponse(
            request_id=request_id,
            concept_id=concept_id,
            total_neighbors=len(neighbor_responses),
            neighbors=neighbor_responses,
            processing_time_ms=round(processing_time, 2),
        )

        # Cache the result (serialize to dict for storage)
        cache_service.put(CacheType.RELATIONSHIP, cache_key, result.model_dump())

        return result

    except Exception as e:
        raise InternalError(
            message=f"Failed to get concept neighbors: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )


@router.get(
    "/concepts/{concept_id}/ancestors",
    response_model=AncestorsListResponse,
    summary="Get concept hierarchy",
    description="Returns ancestors of a concept in the ontology hierarchy.",
)
async def get_concept_ancestors(
    concept_id: int,
    max_levels: int = Query(5, ge=1, le=10, description="Maximum levels to traverse"),
) -> AncestorsListResponse:
    """Get ancestors of a concept in the hierarchy.

    Args:
        concept_id: The OMOP concept ID to find ancestors for.
        max_levels: Maximum levels to traverse up the hierarchy.

    Returns:
        AncestorsListResponse with ancestor concepts.
    """
    start_time = time.perf_counter()
    request_id = str(uuid4())

    try:
        from app.services.graph_analytics_service import get_graph_analytics_service

        service = get_graph_analytics_service()

        ancestors = service.get_concept_ancestors(
            concept_id=concept_id,
            max_levels=max_levels,
        )

        processing_time = (time.perf_counter() - start_time) * 1000

        ancestor_responses = []
        for a in ancestors:
            anc = a.get("ancestor", {})
            ancestor_responses.append(AncestorResponse(
                ancestor=ConceptResponse(
                    concept_id=anc.get("concept_id", 0),
                    concept_name=anc.get("concept_name", ""),
                    vocabulary_id=anc.get("vocabulary_id", ""),
                    domain_id=anc.get("domain_id", ""),
                ),
                distance=a.get("distance", 1),
            ))

        return AncestorsListResponse(
            request_id=request_id,
            concept_id=concept_id,
            total_ancestors=len(ancestor_responses),
            ancestors=ancestor_responses,
            processing_time_ms=round(processing_time, 2),
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to get concept ancestors: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )


@router.post(
    "/concepts/path",
    response_model=PathResponse,
    summary="Find path between concepts",
    description="Finds the shortest path between two concepts in the knowledge graph.",
)
async def find_concept_path(
    request: PathRequest,
) -> PathResponse:
    """Find the shortest path between two concepts.

    Args:
        request: PathRequest with start and end concept IDs.

    Returns:
        PathResponse with the path if found.
    """
    start_time = time.perf_counter()
    request_id = str(uuid4())

    try:
        from app.services.graph_analytics_service import get_graph_analytics_service

        service = get_graph_analytics_service()

        path = service.find_concept_path(
            start_concept_id=request.start_concept_id,
            end_concept_id=request.end_concept_id,
            max_length=request.max_length,
        )

        processing_time = (time.perf_counter() - start_time) * 1000

        if path is None:
            return PathResponse(
                request_id=request_id,
                start_concept=ConceptResponse(
                    concept_id=request.start_concept_id,
                    concept_name="Unknown",
                    vocabulary_id="",
                    domain_id="",
                ),
                end_concept=ConceptResponse(
                    concept_id=request.end_concept_id,
                    concept_name="Unknown",
                    vocabulary_id="",
                    domain_id="",
                ),
                path_nodes=[],
                path_relationships=[],
                path_length=0,
                found=False,
                processing_time_ms=round(processing_time, 2),
            )

        path_nodes = [
            ConceptResponse(
                concept_id=n.concept_id,
                concept_name=n.concept_name,
                vocabulary_id=n.vocabulary_id,
                domain_id=n.domain_id,
            )
            for n in path.path_nodes
        ]

        return PathResponse(
            request_id=request_id,
            start_concept=ConceptResponse(
                concept_id=path.start_concept.concept_id,
                concept_name=path.start_concept.concept_name,
                vocabulary_id=path.start_concept.vocabulary_id,
                domain_id=path.start_concept.domain_id,
            ),
            end_concept=ConceptResponse(
                concept_id=path.end_concept.concept_id,
                concept_name=path.end_concept.concept_name,
                vocabulary_id=path.end_concept.vocabulary_id,
                domain_id=path.end_concept.domain_id,
            ),
            path_nodes=path_nodes,
            path_relationships=path.path_relationships,
            path_length=path.path_length,
            found=True,
            processing_time_ms=round(processing_time, 2),
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to find concept path: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )


@router.get(
    "/patients/{patient_id}/similar",
    response_model=SimilarPatientsResponse,
    summary="Find similar patients",
    description="Finds patients similar to the specified patient based on clinical features.",
)
async def find_similar_patients(
    patient_id: str,
    metric: SimilarityMetricAPI = Query(SimilarityMetricAPI.JACCARD, description="Similarity metric"),
    min_similarity: float = Query(0.5, ge=0, le=1, description="Minimum similarity threshold"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
) -> SimilarPatientsResponse:
    """Find patients similar to a given patient.

    Args:
        patient_id: Reference patient ID.
        metric: Similarity metric to use.
        min_similarity: Minimum similarity threshold (0-1).
        limit: Maximum number of similar patients.

    Returns:
        SimilarPatientsResponse with similar patients.
    """
    start_time = time.perf_counter()
    request_id = str(uuid4())

    try:
        from app.services.graph_analytics_service import (
            get_graph_analytics_service,
            SimilarityMetric,
        )

        service = get_graph_analytics_service()

        similar = service.find_similar_patients(
            patient_id=patient_id,
            metric=SimilarityMetric(metric.value),
            min_similarity=min_similarity,
            limit=limit,
        )

        processing_time = (time.perf_counter() - start_time) * 1000

        similar_responses = [
            SimilarPatientResponse(
                patient_id=p.patient_id,
                similarity_score=p.similarity_score,
                shared_conditions=p.shared_conditions,
                shared_medications=p.shared_medications,
                shared_procedures=p.shared_procedures,
                total_shared_features=p.total_shared_features,
            )
            for p in similar
        ]

        return SimilarPatientsResponse(
            request_id=request_id,
            patient_id=patient_id,
            total_similar=len(similar_responses),
            similar_patients=similar_responses,
            metric_used=metric,
            processing_time_ms=round(processing_time, 2),
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to find similar patients: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )


@router.get(
    "/patients/{patient_id}/subgraph",
    response_model=PatientSubgraphResponse,
    summary="Get patient knowledge graph",
    description="Extracts the knowledge subgraph for a patient including conditions, drugs, and procedures.",
)
async def get_patient_subgraph(
    patient_id: str,
    categories: list[NodeCategoryAPI] | None = Query(None, description="Categories to include"),
    max_relationships: int = Query(100, ge=1, le=500, description="Maximum relationships"),
) -> PatientSubgraphResponse:
    """Extract a subgraph representing a patient's clinical knowledge.

    Args:
        patient_id: Patient ID.
        categories: Categories to include (all if None).
        max_relationships: Maximum relationships to include.

    Returns:
        PatientSubgraphResponse with nodes and edges.
    """
    start_time = time.perf_counter()
    request_id = str(uuid4())

    try:
        from app.services.graph_analytics_service import (
            get_graph_analytics_service,
            NodeCategory,
        )

        service = get_graph_analytics_service()

        cat_filter = None
        if categories:
            cat_filter = [NodeCategory(c.value) for c in categories]

        subgraph = service.get_patient_subgraph(
            patient_id=patient_id,
            include_categories=cat_filter,
            max_relationships=max_relationships,
        )

        processing_time = (time.perf_counter() - start_time) * 1000

        node_responses = [
            ConceptResponse(
                concept_id=n.concept_id,
                concept_name=n.concept_name,
                vocabulary_id=n.vocabulary_id,
                domain_id=n.domain_id,
            )
            for n in subgraph.nodes
        ]

        edge_responses = [
            GraphEdgeResponse(
                source_id=e.source_id,
                target_id=e.target_id,
                relationship_type=e.relationship_type,
                properties=e.properties,
            )
            for e in subgraph.edges
        ]

        return PatientSubgraphResponse(
            request_id=request_id,
            patient_id=patient_id,
            nodes=node_responses,
            edges=edge_responses,
            node_count=subgraph.node_count,
            edge_count=subgraph.edge_count,
            conditions_count=subgraph.conditions_count,
            drugs_count=subgraph.drugs_count,
            procedures_count=subgraph.procedures_count,
            measurements_count=subgraph.measurements_count,
            processing_time_ms=round(processing_time, 2),
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to get patient subgraph: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )


@router.post(
    "/query",
    response_model=CypherQueryResponse,
    summary="Execute Cypher query (admin only)",
    description="Executes a raw Cypher query. Restricted to admin users.",
)
async def execute_cypher_query(
    request: CypherQueryRequest,
    current_user: CurrentUser = Depends(require_admin),
) -> CypherQueryResponse:
    """Execute a Cypher query (admin only).

    WARNING: This endpoint allows arbitrary Cypher execution
    and should only be accessible to administrators.

    Requires admin role via require_admin dependency.

    Args:
        request: CypherQueryRequest with query and parameters.
        current_user: Authenticated admin user (injected via dependency).

    Returns:
        CypherQueryResponse with query results.
    """
    import logging

    start_time = time.perf_counter()
    request_id = str(uuid4())

    # Log admin action for audit trail
    logging.info(
        f"Admin Cypher query by user={current_user.user_id}: {request.query[:100]}..."
    )

    try:
        from app.services.graph_database_service import get_graph_database_service

        service = get_graph_database_service()

        # Determine if this is a write query
        query_lower = request.query.lower().strip()
        is_write = any(
            query_lower.startswith(kw)
            for kw in ["create", "merge", "set", "delete", "remove", "detach"]
        )

        result = service.execute_query(
            query=request.query,
            parameters=request.parameters,
            write=is_write,
        )

        processing_time = (time.perf_counter() - start_time) * 1000

        return CypherQueryResponse(
            request_id=request_id,
            query=request.query,
            records=result.records,
            record_count=len(result.records),
            execution_time_ms=round(processing_time, 2),
        )

    except Exception as e:
        raise InternalError(
            message=f"Query execution failed: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )


@router.get(
    "/stats",
    response_model=GraphStatsResponse,
    summary="Get graph statistics",
    description="Returns statistics about the knowledge graph.",
)
async def get_graph_stats() -> GraphStatsResponse:
    """Get statistics about the knowledge graph.

    Returns node counts, relationship counts, and domain distributions.
    """
    request_id = str(uuid4())

    try:
        from app.services.graph_analytics_service import get_graph_analytics_service

        service = get_graph_analytics_service()
        stats = service.get_graph_statistics()

        return GraphStatsResponse(
            request_id=request_id,
            graph_connected=stats.get("graph_connected", False),
            mock_mode=stats.get("mock_mode", True),
            total_concepts=stats.get("total_concepts", 0),
            total_patients=stats.get("total_patients", 0),
            total_relationships=stats.get("total_relationships", 0),
            concepts_by_domain=stats.get("concepts_by_domain", {}),
            relationship_types=stats.get("relationship_types", {}),
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to get graph stats: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )


@router.post(
    "/etl/load-sample",
    summary="Load sample graph data",
    description="Loads sample OMOP concepts into the graph for demonstration.",
)
async def load_sample_data() -> dict[str, Any]:
    """Load sample OMOP concepts for demonstration.

    This endpoint loads a small set of sample concepts and relationships
    to demonstrate the knowledge graph functionality.
    """
    try:
        from app.services.graph_etl_service import get_graph_etl_service

        service = get_graph_etl_service()

        # Create schema first
        schema_result = service.create_schema()

        # Load sample data
        etl_result = service.load_sample_data()

        return {
            "status": "success",
            "schema_created": schema_result.get("successful", 0),
            "nodes_created": etl_result.nodes_created,
            "relationships_created": etl_result.relationships_created,
            "duration_ms": etl_result.duration_ms,
            "errors": etl_result.errors,
        }

    except Exception as e:
        raise InternalError(
            message=f"Failed to load sample data: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )


@router.get(
    "/concepts/search",
    summary="Search concepts",
    description="Search for concepts by name in the knowledge graph.",
)
async def search_concepts(
    q: str = Query(..., min_length=2, description="Search query"),
    categories: list[NodeCategoryAPI] | None = Query(None, description="Filter by categories"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
) -> dict[str, Any]:
    """Search for concepts by name.

    Args:
        q: Search query string.
        categories: Optional categories to filter by.
        limit: Maximum results to return.

    Returns:
        Dictionary with matching concepts.
    """
    start_time = time.perf_counter()
    request_id = str(uuid4())

    try:
        from app.services.graph_analytics_service import (
            get_graph_analytics_service,
            NodeCategory,
        )

        # Check cache first
        cache_service = get_kg_cache_service()
        cat_str = ",".join(sorted(c.value for c in categories)) if categories else ""
        cache_key = f"search:{q}:{cat_str}:{limit}"
        cached = cache_service.get(CacheType.CONCEPT, cache_key)
        if cached:
            cached["request_id"] = request_id
            cached["cached"] = True
            cached["processing_time_ms"] = round((time.perf_counter() - start_time) * 1000, 2)
            return cached

        service = get_graph_analytics_service()

        cat_filter = None
        if categories:
            cat_filter = [NodeCategory(c.value) for c in categories]

        concepts = service.search_concepts(
            query=q,
            categories=cat_filter,
            limit=limit,
        )

        processing_time = (time.perf_counter() - start_time) * 1000

        result = {
            "request_id": request_id,
            "query": q,
            "total_results": len(concepts),
            "concepts": [
                {
                    "concept_id": c.concept_id,
                    "concept_name": c.concept_name,
                    "vocabulary_id": c.vocabulary_id,
                    "domain_id": c.domain_id,
                    "concept_class_id": c.concept_class_id,
                    "synonyms": c.synonyms,
                }
                for c in concepts
            ],
            "cached": False,
            "processing_time_ms": round(processing_time, 2),
        }

        # Cache the result
        cache_service.put(CacheType.CONCEPT, cache_key, result)

        return result

    except Exception as e:
        raise InternalError(
            message=f"Search failed: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )


# ============================================================================
# Multi-Hop Reasoning Endpoints (DR.KNOWS Pattern)
# ============================================================================


@reasoning_router.post(
    "/multi-hop",
    response_model=MultiHopResponse,
    summary="Execute multi-hop reasoning",
    description="""
    Perform multi-hop reasoning through the clinical knowledge graph.

    Implements the DR.KNOWS pattern:
    1. Start from seed concepts (conditions, drugs, procedures)
    2. Traverse up to max_hops following semantic relations
    3. Score paths by confidence and semantic coherence
    4. Return top-k paths with supporting evidence

    Example: Find treatment paths from "Type 2 Diabetes" (concept_id: 201826)
    to related drugs and procedures.
    """,
)
async def multi_hop_reasoning(
    request: MultiHopRequest,
) -> MultiHopResponse:
    """Execute multi-hop reasoning from seed concepts.

    Args:
        request: MultiHopRequest with seed concepts and parameters.

    Returns:
        MultiHopResponse with reasoning paths and evidence.
    """
    start_time = time.perf_counter()
    request_id = str(uuid4())

    # Generate cache key from request parameters
    cache_params = {
        "seeds": sorted(request.seed_concepts),
        "hops": request.max_hops,
        "min_conf": request.min_confidence,
        "top_k": request.top_k,
        "domains": sorted(request.target_domains) if request.target_domains else None,
        "groups": sorted(g.value for g in request.semantic_groups) if request.semantic_groups else None,
        "evidence": request.include_evidence,
    }
    cache_key = hashlib.md5(json.dumps(cache_params, sort_keys=True).encode()).hexdigest()

    # Check cache first
    cache_service = get_kg_cache_service()
    cached_result = cache_service.get(CacheType.QUERY_RESULT, f"multi_hop:{cache_key}")
    if cached_result:
        processing_time = (time.perf_counter() - start_time) * 1000
        cached_result["request_id"] = request_id
        cached_result["processing_time_ms"] = round(processing_time, 2)
        cached_result["cached"] = True
        return MultiHopResponse(**cached_result)

    try:
        from app.services.graph_database_service import get_graph_database_service

        service = get_graph_database_service()

        # Build domain filter clause
        domain_filter = ""
        if request.target_domains:
            domains_str = ", ".join(f"'{d}'" for d in request.target_domains)
            domain_filter = f"AND end.domain_id IN [{domains_str}]"

        # Build semantic group filter clause
        semantic_filter = ""
        if request.semantic_groups:
            groups_str = ", ".join(f"'{g.value}'" for g in request.semantic_groups)
            semantic_filter = f"AND end.semantic_group IN [{groups_str}]"

        # Build the multi-hop query
        query = f"""
        UNWIND $seed_ids AS seed_id
        MATCH (start:Concept {{concept_id: seed_id}})
        MATCH path = (start)-[*1..{request.max_hops}]-(end:Concept)
        WHERE end <> start
          {domain_filter}
          {semantic_filter}
        WITH path,
             nodes(path) AS path_nodes,
             relationships(path) AS path_rels,
             length(path) AS hops,
             reduce(score = 1.0, r IN relationships(path) |
                    score * coalesce(r.confidence, 1.0) * 0.9
             ) AS path_score
        WHERE path_score >= $min_confidence
        RETURN path_nodes, path_rels, hops, path_score
        ORDER BY path_score DESC
        LIMIT $top_k
        """

        result = service.execute_read(
            query,
            parameters={
                "seed_ids": request.seed_concepts,
                "min_confidence": request.min_confidence,
                "top_k": request.top_k,
            },
        )

        # Convert results to response model
        paths: list[ReasoningPathResponse] = []
        conclusions: dict[int, list[ReasoningPathResponse]] = {}

        for record in result.records:
            path_nodes = record.get("path_nodes", [])
            path_rels = record.get("path_rels", [])
            hops = record.get("hops", 0)
            path_score = record.get("path_score", 1.0)

            # Convert nodes
            nodes = []
            for n in path_nodes:
                if isinstance(n, dict):
                    node_data = n
                else:
                    node_data = dict(n) if hasattr(n, "__iter__") else {"concept_id": 0, "name": "Unknown"}

                nodes.append(ReasoningNodeResponse(
                    concept_id=node_data.get("concept_id", 0),
                    concept_name=node_data.get("name", node_data.get("concept_name", "")),
                    vocabulary_id=node_data.get("vocabulary_id", ""),
                    domain_id=node_data.get("domain_id", ""),
                    semantic_group=node_data.get("semantic_group"),
                    semantic_type=node_data.get("semantic_type"),
                ))

            # Convert edges
            edges = []
            for r in path_rels:
                if isinstance(r, dict):
                    rel_data = r
                    rel_type = rel_data.get("type", "RELATED")
                else:
                    rel_data = dict(r) if hasattr(r, "__iter__") else {}
                    rel_type = type(r).__name__ if hasattr(r, "__class__") else "RELATED"

                edges.append(ReasoningEdgeResponse(
                    relationship_type=rel_type,
                    confidence=rel_data.get("confidence", 1.0),
                    source_vocabulary=rel_data.get("vocabulary", None),
                ))

            path_response = ReasoningPathResponse(
                path_id=str(uuid4()),
                nodes=nodes,
                edges=edges,
                hops=hops,
                score=float(path_score),
                semantic_coherence=1.0,
            )
            paths.append(path_response)

            # Track conclusions for evidence aggregation
            if nodes and request.include_evidence:
                end_concept_id = nodes[-1].concept_id
                if end_concept_id not in conclusions:
                    conclusions[end_concept_id] = []
                conclusions[end_concept_id].append(path_response)

        # Build evidence aggregation if requested
        evidence = None
        if request.include_evidence and conclusions:
            evidence = []
            for concept_id, supporting_paths in conclusions.items():
                if supporting_paths:
                    end_node = supporting_paths[0].nodes[-1] if supporting_paths[0].nodes else None
                    avg_conf = sum(p.score for p in supporting_paths) / len(supporting_paths)

                    # Collect unique semantic types
                    semantic_types = set()
                    for p in supporting_paths:
                        for n in p.nodes:
                            if n.semantic_type:
                                semantic_types.add(n.semantic_type)

                    # Build reasoning summary
                    summary = f"{len(supporting_paths)} path(s) support reaching {end_node.concept_name if end_node else 'unknown'}"

                    evidence.append(EvidenceAggregation(
                        conclusion_concept_id=concept_id,
                        conclusion_name=end_node.concept_name if end_node else "",
                        total_paths=len(supporting_paths),
                        avg_confidence=round(avg_conf, 4),
                        semantic_types=list(semantic_types),
                        reasoning_summary=summary,
                    ))

            # Sort by confidence
            evidence.sort(key=lambda e: e.avg_confidence, reverse=True)

        processing_time = (time.perf_counter() - start_time) * 1000

        response = MultiHopResponse(
            request_id=request_id,
            seed_concepts=request.seed_concepts,
            total_paths=len(paths),
            paths=paths,
            evidence=evidence,
            processing_time_ms=round(processing_time, 2),
            truncated=len(result.records) >= request.top_k,
        )

        # Cache the result (excluding request_id and processing_time which change)
        cache_data = response.model_dump()
        del cache_data["request_id"]
        del cache_data["processing_time_ms"]
        cache_service.put(CacheType.QUERY_RESULT, f"multi_hop:{cache_key}", cache_data)

        return response

    except Exception as e:
        import logging
        logging.exception("Multi-hop reasoning failed")
        raise InternalError(
            message=f"Multi-hop reasoning failed: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )


@reasoning_router.post(
    "/score-paths",
    response_model=ScorePathsResponse,
    summary="Score reasoning paths",
    description="""
    Score and rank reasoning paths based on confidence decay and semantic coherence.

    Scoring methods:
    - confidence_decay: Score decreases exponentially with each hop
    - semantic_coherence: Score based on semantic type transitions
    - hybrid: Combination of both methods
    """,
)
async def score_paths(
    request: ScorePathsRequest,
) -> ScorePathsResponse:
    """Score a list of reasoning paths.

    Args:
        request: ScorePathsRequest with paths to score.

    Returns:
        ScorePathsResponse with scored and ranked paths.
    """
    start_time = time.perf_counter()
    request_id = str(uuid4())

    try:
        from app.services.graph_database_service import get_graph_database_service

        service = get_graph_database_service()

        scored_paths: list[ScoredPathResponse] = []

        for path_ids in request.paths:
            if not path_ids:
                continue

            # Fetch concept details for each node in path
            query = """
            UNWIND $concept_ids AS cid
            MATCH (c:Concept {concept_id: cid})
            RETURN c.concept_id AS concept_id,
                   c.name AS name,
                   c.vocabulary_id AS vocabulary_id,
                   c.domain_id AS domain_id,
                   c.semantic_group AS semantic_group,
                   c.semantic_type AS semantic_type
            """

            result = service.execute_read(
                query,
                parameters={"concept_ids": path_ids},
            )

            # Build concept map
            concept_map = {}
            for record in result.records:
                concept_map[record["concept_id"]] = record

            # Build path nodes in order
            nodes = []
            for cid in path_ids:
                c = concept_map.get(cid, {})
                nodes.append(ReasoningNodeResponse(
                    concept_id=cid,
                    concept_name=c.get("name", "Unknown"),
                    vocabulary_id=c.get("vocabulary_id", ""),
                    domain_id=c.get("domain_id", ""),
                    semantic_group=c.get("semantic_group"),
                    semantic_type=c.get("semantic_type"),
                ))

            # Calculate scores
            hops = len(path_ids) - 1
            confidence_score = request.decay_factor ** hops

            # Semantic coherence: penalize transitions that don't make clinical sense
            coherence_score = 1.0
            domain_transitions = []
            for i in range(len(nodes) - 1):
                d1 = nodes[i].domain_id
                d2 = nodes[i + 1].domain_id
                domain_transitions.append(f"{d1}->{d2}")
                # Common clinical transitions get higher scores
                if (d1, d2) in [
                    ("Condition", "Drug"),
                    ("Drug", "Condition"),
                    ("Condition", "Procedure"),
                    ("Procedure", "Condition"),
                    ("Measurement", "Condition"),
                    ("Condition", "Measurement"),
                ]:
                    coherence_score *= 1.0
                elif d1 == d2:
                    coherence_score *= 0.95  # Same domain slightly penalized
                else:
                    coherence_score *= 0.8  # Unusual transitions

            # Hybrid score
            if request.scoring_method == "confidence_decay":
                final_score = confidence_score
            elif request.scoring_method == "semantic_coherence":
                final_score = coherence_score
            else:  # hybrid
                final_score = (confidence_score * 0.6) + (coherence_score * 0.4)

            scored_paths.append(ScoredPathResponse(
                path=nodes,
                score=round(final_score, 4),
                confidence_component=round(confidence_score, 4),
                coherence_component=round(coherence_score, 4),
                breakdown={
                    "hops": hops,
                    "decay_factor": request.decay_factor,
                    "domain_transitions": len(domain_transitions),
                },
            ))

        # Sort by score
        scored_paths.sort(key=lambda p: p.score, reverse=True)

        processing_time = (time.perf_counter() - start_time) * 1000

        return ScorePathsResponse(
            request_id=request_id,
            scored_paths=scored_paths,
            processing_time_ms=round(processing_time, 2),
        )

    except Exception as e:
        import logging
        logging.exception("Path scoring failed")
        raise InternalError(
            message=f"Path scoring failed: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )


@reasoning_router.post(
    "/find-treatments",
    response_model=TreatmentPathResponse,
    summary="Find treatment paths for a condition",
    description="""
    Find drug treatments for a given condition by traversing the knowledge graph.

    Searches for paths from the condition to drugs via relationships like:
    - may_treat / treats
    - is_a (hierarchy) + may_treat
    - has_mechanism_of_action

    Returns ranked treatment paths with confidence scores.
    """,
)
async def find_treatment_paths(
    request: TreatmentPathRequest,
) -> TreatmentPathResponse:
    """Find treatment paths from a condition to drugs.

    Args:
        request: TreatmentPathRequest with condition ID.

    Returns:
        TreatmentPathResponse with treatment paths.
    """
    start_time = time.perf_counter()
    request_id = str(uuid4())

    try:
        from app.services.graph_database_service import get_graph_database_service

        service = get_graph_database_service()

        # Get condition name first
        name_result = service.execute_read(
            "MATCH (c:Concept {concept_id: $cid}) RETURN c.name AS name",
            parameters={"cid": request.condition_concept_id},
        )
        condition_name = "Unknown"
        if name_result.records:
            condition_name = name_result.records[0].get("name", "Unknown")

        # Find treatment paths
        query = f"""
        MATCH (condition:Concept {{concept_id: $condition_id}})
        MATCH path = (condition)-[*1..{request.max_hops}]-(drug:Concept)
        WHERE drug.domain_id = 'Drug'
          AND drug <> condition
        WITH path,
             nodes(path) AS path_nodes,
             relationships(path) AS path_rels,
             length(path) AS hops,
             drug,
             reduce(score = 1.0, r IN relationships(path) |
                    score * coalesce(r.confidence, 1.0) * 0.85
             ) AS path_score
        RETURN drug.concept_id AS drug_id,
               drug.name AS drug_name,
               path_score,
               hops,
               [n IN path_nodes | {{
                   concept_id: n.concept_id,
                   name: n.name,
                   vocabulary_id: n.vocabulary_id,
                   domain_id: n.domain_id,
                   semantic_group: n.semantic_group
               }}] AS path_nodes_data
        ORDER BY path_score DESC
        LIMIT $top_k
        """

        result = service.execute_read(
            query,
            parameters={
                "condition_id": request.condition_concept_id,
                "top_k": request.top_k,
            },
        )

        treatment_paths: list[TreatmentPathResult] = []
        for record in result.records:
            path_nodes_data = record.get("path_nodes_data", [])
            nodes = []
            for nd in path_nodes_data:
                if isinstance(nd, dict):
                    nodes.append(ReasoningNodeResponse(
                        concept_id=nd.get("concept_id", 0),
                        concept_name=nd.get("name", ""),
                        vocabulary_id=nd.get("vocabulary_id", ""),
                        domain_id=nd.get("domain_id", ""),
                        semantic_group=nd.get("semantic_group"),
                    ))

            treatment_paths.append(TreatmentPathResult(
                drug_concept_id=record.get("drug_id", 0),
                drug_name=record.get("drug_name", ""),
                path_score=float(record.get("path_score", 0)),
                hops=record.get("hops", 0),
                path_nodes=nodes,
                evidence_sources=[],
            ))

        processing_time = (time.perf_counter() - start_time) * 1000

        return TreatmentPathResponse(
            request_id=request_id,
            condition_concept_id=request.condition_concept_id,
            condition_name=condition_name,
            treatment_paths=treatment_paths,
            total_paths=len(treatment_paths),
            processing_time_ms=round(processing_time, 2),
        )

    except Exception as e:
        import logging
        logging.exception("Treatment path search failed")
        raise InternalError(
            message=f"Treatment path search failed: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )


@reasoning_router.post(
    "/check-contraindications",
    response_model=ContraindicationResponse,
    summary="Check drug contraindications",
    description="""
    Check if a drug has contraindications with the patient's current conditions.

    Searches for paths between the drug and patient conditions that indicate:
    - contraindicated_with relationships
    - interacts_with relationships
    - adverse_event associations

    Returns found contraindications with severity levels.
    """,
)
async def check_contraindications(
    request: ContraindicationCheckRequest,
) -> ContraindicationResponse:
    """Check drug contraindications against patient conditions.

    Args:
        request: ContraindicationCheckRequest with drug and conditions.

    Returns:
        ContraindicationResponse with contraindication results.
    """
    start_time = time.perf_counter()
    request_id = str(uuid4())

    try:
        from app.services.graph_database_service import get_graph_database_service

        service = get_graph_database_service()

        # Get drug name
        name_result = service.execute_read(
            "MATCH (d:Concept {concept_id: $did}) RETURN d.name AS name",
            parameters={"did": request.drug_concept_id},
        )
        drug_name = "Unknown"
        if name_result.records:
            drug_name = name_result.records[0].get("name", "Unknown")

        # Check contraindications via graph paths
        # Look for paths that connect drug to patient conditions
        query = """
        MATCH (drug:Concept {concept_id: $drug_id})
        UNWIND $condition_ids AS cond_id
        MATCH (condition:Concept {concept_id: cond_id})
        OPTIONAL MATCH path = shortestPath((drug)-[*..3]-(condition))
        WITH drug, condition, path,
             CASE WHEN path IS NOT NULL THEN
                 [r IN relationships(path) WHERE type(r) IN ['CONTRAINDICATED_WITH', 'INTERACTS_WITH', 'HAS_ADVERSE_EVENT'] | type(r)]
             ELSE [] END AS contraindication_rels
        WHERE size(contraindication_rels) > 0 OR path IS NULL
        RETURN condition.concept_id AS condition_id,
               condition.name AS condition_name,
               contraindication_rels,
               CASE WHEN path IS NOT NULL THEN [n IN nodes(path) | n.name] ELSE [] END AS path_names
        """

        result = service.execute_read(
            query,
            parameters={
                "drug_id": request.drug_concept_id,
                "condition_ids": request.patient_condition_ids,
            },
        )

        contraindications: list[ContraindicationResult] = []
        for record in result.records:
            ci_rels = record.get("contraindication_rels", [])
            if ci_rels:  # Has contraindication relationship
                # Determine severity based on relationship type
                if "CONTRAINDICATED_WITH" in ci_rels:
                    severity = "high"
                elif "HAS_ADVERSE_EVENT" in ci_rels:
                    severity = "moderate"
                else:
                    severity = "low"

                contraindications.append(ContraindicationResult(
                    condition_concept_id=record.get("condition_id", 0),
                    condition_name=record.get("condition_name", ""),
                    relationship_type=ci_rels[0] if ci_rels else "UNKNOWN",
                    severity=severity,
                    evidence_path=record.get("path_names", []),
                ))

        processing_time = (time.perf_counter() - start_time) * 1000

        return ContraindicationResponse(
            request_id=request_id,
            drug_concept_id=request.drug_concept_id,
            drug_name=drug_name,
            contraindications=contraindications,
            is_safe=len(contraindications) == 0,
            total_checked=len(request.patient_condition_ids),
            processing_time_ms=round(processing_time, 2),
        )

    except Exception as e:
        import logging
        logging.exception("Contraindication check failed")
        raise InternalError(
            message=f"Contraindication check failed: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )


@reasoning_router.post(
    "/aggregate-evidence",
    response_model=EvidenceAggregationResponse,
    summary="Aggregate evidence from reasoning paths",
    description="""
    Aggregate evidence from multiple reasoning paths into clinical conclusions.

    Combines path scores and semantic analysis to produce:
    - Ranked conclusions with confidence scores
    - Supporting path counts
    - Reasoning chains for explainability

    Useful for clinical decision support with evidence-based reasoning.
    """,
)
async def aggregate_evidence(
    request: EvidenceAggregationRequest,
) -> EvidenceAggregationResponse:
    """Aggregate evidence from reasoning paths.

    Args:
        request: EvidenceAggregationRequest with parameters.

    Returns:
        EvidenceAggregationResponse with aggregated conclusions.
    """
    start_time = time.perf_counter()
    request_id = str(uuid4())

    try:
        from app.services.graph_database_service import get_graph_database_service

        service = get_graph_database_service()

        # Determine target domain based on question type
        target_domain = "Drug"
        if request.question_type == "diagnosis":
            target_domain = "Condition"
        elif request.question_type == "prognosis":
            target_domain = "Observation"

        # Find paths to aggregate
        query = f"""
        UNWIND $seed_ids AS seed_id
        MATCH (start:Concept {{concept_id: seed_id}})
        MATCH path = (start)-[*1..{request.max_hops}]-(end:Concept)
        WHERE end.domain_id = $target_domain
          AND end <> start
        WITH end,
             collect({{
                 path_score: reduce(s = 1.0, r IN relationships(path) | s * 0.9),
                 hops: length(path),
                 path_names: [n IN nodes(path) | n.name]
             }}) AS paths_data
        WITH end,
             paths_data,
             size(paths_data) AS path_count,
             reduce(total = 0.0, p IN paths_data | total + p.path_score) / size(paths_data) AS avg_score
        WHERE path_count > 0
        RETURN end.concept_id AS concept_id,
               end.name AS concept_name,
               end.semantic_type AS semantic_type,
               path_count,
               avg_score,
               paths_data[0].path_names AS sample_path
        ORDER BY avg_score DESC
        LIMIT $top_k
        """

        result = service.execute_read(
            query,
            parameters={
                "seed_ids": request.seed_concept_ids,
                "target_domain": target_domain,
                "top_k": request.top_k_paths,
            },
        )

        conclusions: list[EvidenceConclusion] = []
        total_paths = 0

        for record in result.records:
            path_count = record.get("path_count", 0)
            total_paths += path_count

            sample_path = record.get("sample_path", [])
            if sample_path and len(sample_path) > 5:
                sample_path = sample_path[:3] + ["..."] + sample_path[-2:]

            conclusions.append(EvidenceConclusion(
                concept_id=record.get("concept_id", 0),
                concept_name=record.get("concept_name", ""),
                confidence=round(float(record.get("avg_score", 0)), 4),
                supporting_paths=path_count,
                semantic_types=[record.get("semantic_type")] if record.get("semantic_type") else [],
                reasoning_chain=sample_path,
            ))

        processing_time = (time.perf_counter() - start_time) * 1000

        avg_confidence = 0.0
        if conclusions:
            avg_confidence = sum(c.confidence for c in conclusions) / len(conclusions)

        return EvidenceAggregationResponse(
            request_id=request_id,
            seed_concepts=request.seed_concept_ids,
            question_type=request.question_type,
            conclusions=conclusions,
            total_paths_analyzed=total_paths,
            unique_conclusions=len(conclusions),
            avg_confidence=round(avg_confidence, 4),
            processing_time_ms=round(processing_time, 2),
        )

    except Exception as e:
        import logging
        logging.exception("Evidence aggregation failed")
        raise InternalError(
            message=f"Evidence aggregation failed: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
        )
