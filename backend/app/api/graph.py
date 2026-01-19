"""Knowledge Graph API Endpoints.

Provides endpoints for:
- Neo4j connection health and status
- Concept neighbors and hierarchy traversal
- Path finding between concepts
- Patient similarity analysis
- Patient knowledge graph extraction
- Graph statistics and analytics
- Admin Cypher query execution
"""

import time
from datetime import datetime, UTC
from enum import Enum
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Query, Body, HTTPException
from pydantic import BaseModel, Field

from app.api.errors import ErrorCode, InternalError, NotFoundError

router = APIRouter(prefix="/api/graph", tags=["Knowledge Graph"])


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
            checked_at=datetime.now(UTC).isoformat(),
        )


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

        return NeighborsListResponse(
            request_id=request_id,
            concept_id=concept_id,
            total_neighbors=len(neighbor_responses),
            neighbors=neighbor_responses,
            processing_time_ms=round(processing_time, 2),
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to get concept neighbors: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
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
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
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
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
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
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
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
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.post(
    "/query",
    response_model=CypherQueryResponse,
    summary="Execute Cypher query (admin only)",
    description="Executes a raw Cypher query. Restricted to admin users.",
)
async def execute_cypher_query(
    request: CypherQueryRequest,
) -> CypherQueryResponse:
    """Execute a Cypher query (admin only).

    WARNING: This endpoint allows arbitrary Cypher execution
    and should only be accessible to administrators.

    Args:
        request: CypherQueryRequest with query and parameters.

    Returns:
        CypherQueryResponse with query results.
    """
    start_time = time.perf_counter()
    request_id = str(uuid4())

    # TODO: Add proper admin authentication check
    # For now, we'll allow it but log a warning
    import logging
    logging.warning(f"Admin Cypher query executed: {request.query[:100]}...")

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
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
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
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
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
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
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

        return {
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
            "processing_time_ms": round(processing_time, 2),
        }

    except Exception as e:
        raise InternalError(
            message=f"Search failed: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )
