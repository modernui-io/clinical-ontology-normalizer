"""Knowledge Graph FHIR Export API endpoints.

Provides REST endpoints for exporting knowledge graph data to FHIR R4 format:
- Export reasoning chains as Provenance
- Export causal relationships as Evidence
- Export concepts as Library
- Export full graph as Bundle
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.knowledge_graph_fhir_export import (
    KGEdge,
    KGNode,
    KnowledgeGraphFHIRExporter,
    ReasoningChain,
    get_kg_fhir_exporter,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fhir/knowledge-graph", tags=["fhir", "knowledge-graph"])


# =============================================================================
# Request/Response Models
# =============================================================================


class ConceptRequest(BaseModel):
    """Request model for concept export."""

    cui: str | None = Field(None, description="UMLS Concept Unique Identifier")
    name: str = Field(..., description="Concept name")
    semantic_type: str | None = Field(None, description="UMLS semantic type")
    semantic_group: str | None = Field(None, description="UMLS semantic group")
    vocabulary: str | None = Field(None, description="Source vocabulary")
    code: str | None = Field(None, description="Code in source vocabulary")


class EdgeRequest(BaseModel):
    """Request model for edge/relationship."""

    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")
    relationship_type: str = Field(..., description="Relationship type")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence score")
    source_document: str | None = Field(None, description="Source document reference")


class ReasoningStepRequest(BaseModel):
    """Request model for a reasoning step."""

    concept: str = Field(..., description="Concept at this step")
    relation: str | None = Field(None, description="Relation to next step")
    description: str | None = Field(None, description="Step description")


class ReasoningChainRequest(BaseModel):
    """Request model for reasoning chain export."""

    query: str = Field(..., description="Original query/question")
    conclusion: str = Field(..., description="Final conclusion")
    steps: list[ReasoningStepRequest] = Field(
        default_factory=list, description="Reasoning steps"
    )
    concepts: list[ConceptRequest] = Field(
        default_factory=list, description="Concepts in the chain"
    )
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Overall confidence")
    source_documents: list[str] = Field(
        default_factory=list, description="Source document IDs"
    )
    patient_id: str | None = Field(None, description="Patient ID if patient-specific")


class CausalChainRequest(BaseModel):
    """Request model for causal relationship export."""

    cause: ConceptRequest = Field(..., description="Cause concept")
    effect: ConceptRequest = Field(..., description="Effect concept")
    relationship_type: str = Field(..., description="Causal relationship type")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence score")
    source_document: str | None = Field(None, description="Source document")
    supporting_paths: int = Field(1, ge=1, description="Number of supporting paths")


class GraphExportRequest(BaseModel):
    """Request model for full graph export."""

    concepts: list[ConceptRequest] = Field(..., description="Graph concepts")
    edges: list[EdgeRequest] = Field(default_factory=list, description="Graph edges")
    reasoning_chains: list[ReasoningChainRequest] = Field(
        default_factory=list, description="Reasoning chains"
    )
    patient_id: str | None = Field(None, description="Patient ID for scoped export")
    bundle_type: str = Field("collection", description="FHIR Bundle type")


class TemporalExportRequest(BaseModel):
    """Request model for temporal snapshot export."""

    concepts: list[ConceptRequest] = Field(..., description="Graph concepts")
    edges: list[EdgeRequest] = Field(default_factory=list, description="Graph edges")
    as_of_time: datetime = Field(..., description="Point in time for snapshot")
    patient_id: str | None = Field(None, description="Patient ID for scoped export")


# =============================================================================
# Helper Functions
# =============================================================================


def _convert_concept_to_node(concept: ConceptRequest, idx: int) -> KGNode:
    """Convert API concept request to KGNode."""
    return KGNode(
        id=f"concept_{idx}_{concept.cui or concept.name.replace(' ', '_')}",
        cui=concept.cui,
        name=concept.name,
        semantic_type=concept.semantic_type,
        semantic_group=concept.semantic_group,
        vocabulary=concept.vocabulary,
        code=concept.code,
    )


def _convert_edge_request(edge: EdgeRequest) -> KGEdge:
    """Convert API edge request to KGEdge."""
    return KGEdge(
        source_id=edge.source_id,
        target_id=edge.target_id,
        relationship_type=edge.relationship_type,
        confidence=edge.confidence,
        source_document=edge.source_document,
    )


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/provenance", response_model=dict[str, Any])
async def export_reasoning_as_provenance(
    request: ReasoningChainRequest,
) -> dict[str, Any]:
    """Export a reasoning chain as FHIR Provenance resource.

    Converts a multi-hop reasoning chain to a FHIR Provenance resource that:
    - Documents the derivation of a clinical conclusion
    - Tracks source facts used in reasoning
    - Records confidence and reasoning steps

    Args:
        request: Reasoning chain details

    Returns:
        FHIR Provenance resource
    """
    exporter = get_kg_fhir_exporter()

    # Convert concepts to nodes
    nodes = [
        _convert_concept_to_node(c, i) for i, c in enumerate(request.concepts)
    ]

    # Build reasoning chain
    chain = ReasoningChain(
        query=request.query,
        conclusion=request.conclusion,
        steps=[
            {
                "concept": step.concept,
                "relation": step.relation,
                "description": step.description,
            }
            for step in request.steps
        ],
        nodes=nodes,
        confidence=request.confidence,
        source_documents=request.source_documents,
    )

    resource = exporter.export_reasoning_chain_as_provenance(
        chain=chain,
        patient_id=request.patient_id,
    )

    return resource.resource


@router.post("/evidence", response_model=dict[str, Any])
async def export_causal_as_evidence(
    request: CausalChainRequest,
) -> dict[str, Any]:
    """Export a causal relationship as FHIR Evidence resource.

    Converts a causal relationship (cause -> effect) to a FHIR Evidence
    resource suitable for clinical decision support.

    Args:
        request: Causal relationship details

    Returns:
        FHIR Evidence resource
    """
    exporter = get_kg_fhir_exporter()

    cause_node = _convert_concept_to_node(request.cause, 0)
    effect_node = _convert_concept_to_node(request.effect, 1)

    edge = KGEdge(
        source_id=cause_node.id,
        target_id=effect_node.id,
        relationship_type=request.relationship_type,
        confidence=request.confidence,
        source_document=request.source_document,
    )

    resource = exporter.export_causal_chain_as_evidence(
        cause_node=cause_node,
        effect_node=effect_node,
        edge=edge,
        supporting_paths=request.supporting_paths,
    )

    return resource.resource


@router.post("/library", response_model=dict[str, Any])
async def export_concepts_as_library(
    concepts: list[ConceptRequest],
    library_name: str = Query("Clinical Concepts", description="Library name"),
    description: str = Query("", description="Library description"),
) -> dict[str, Any]:
    """Export a set of concepts as FHIR Library resource.

    Packages a collection of clinical concepts into a FHIR Library
    resource for distribution and reuse.

    Args:
        concepts: List of concepts to include
        library_name: Name for the library
        description: Library description

    Returns:
        FHIR Library resource
    """
    if not concepts:
        raise HTTPException(status_code=400, detail="At least one concept required")

    exporter = get_kg_fhir_exporter()

    nodes = [
        _convert_concept_to_node(c, i) for i, c in enumerate(concepts)
    ]

    resource = exporter.export_concepts_as_library(
        nodes=nodes,
        library_name=library_name,
        description=description,
    )

    return resource.resource


@router.post("/bundle", response_model=dict[str, Any])
async def export_graph_as_bundle(
    request: GraphExportRequest,
) -> dict[str, Any]:
    """Export full knowledge graph as FHIR Bundle.

    Exports a complete knowledge graph including:
    - Concepts as Library resources
    - Causal edges as Evidence resources
    - Reasoning chains as Provenance resources

    Args:
        request: Full graph export request

    Returns:
        FHIR Bundle containing all resources
    """
    if not request.concepts:
        raise HTTPException(status_code=400, detail="At least one concept required")

    exporter = get_kg_fhir_exporter()

    # Convert concepts to nodes
    nodes = [
        _convert_concept_to_node(c, i) for i, c in enumerate(request.concepts)
    ]
    node_map = {node.name: node for node in nodes}

    # Convert edges
    edges = [_convert_edge_request(e) for e in request.edges]

    # Convert reasoning chains
    chains = []
    for chain_req in request.reasoning_chains:
        chain_nodes = [
            _convert_concept_to_node(c, i)
            for i, c in enumerate(chain_req.concepts)
        ]
        chains.append(
            ReasoningChain(
                query=chain_req.query,
                conclusion=chain_req.conclusion,
                steps=[
                    {
                        "concept": step.concept,
                        "relation": step.relation,
                        "description": step.description,
                    }
                    for step in chain_req.steps
                ],
                nodes=chain_nodes,
                confidence=chain_req.confidence,
                source_documents=chain_req.source_documents,
            )
        )

    bundle = exporter.export_graph_as_bundle(
        nodes=nodes,
        edges=edges,
        reasoning_chains=chains,
        patient_id=request.patient_id,
        bundle_type=request.bundle_type,
    )

    return bundle


@router.post("/temporal-snapshot", response_model=dict[str, Any])
async def export_temporal_snapshot(
    request: TemporalExportRequest,
) -> dict[str, Any]:
    """Export graph state as of a specific point in time.

    Creates a temporal snapshot of the knowledge graph, filtering
    to only include facts valid at the specified time.

    Args:
        request: Temporal export request with as_of_time

    Returns:
        FHIR Bundle with temporal metadata
    """
    if not request.concepts:
        raise HTTPException(status_code=400, detail="At least one concept required")

    exporter = get_kg_fhir_exporter()

    nodes = [
        _convert_concept_to_node(c, i) for i, c in enumerate(request.concepts)
    ]
    edges = [_convert_edge_request(e) for e in request.edges]

    bundle = exporter.export_temporal_snapshot(
        nodes=nodes,
        edges=edges,
        as_of_time=request.as_of_time,
        patient_id=request.patient_id,
    )

    return bundle


@router.get("/stats", response_model=dict[str, Any])
async def get_export_stats() -> dict[str, Any]:
    """Get knowledge graph FHIR export statistics.

    Returns:
        Export service statistics
    """
    exporter = get_kg_fhir_exporter()

    return {
        "service": "Knowledge Graph FHIR Export",
        "version": "1.0.0",
        "supported_exports": [
            "Provenance (reasoning chains)",
            "Evidence (causal relationships)",
            "Library (concept collections)",
            "Bundle (full graph)",
            "Temporal Snapshot",
        ],
        "fhir_version": "R4",
        "resources_generated": exporter._resource_counter,
    }
