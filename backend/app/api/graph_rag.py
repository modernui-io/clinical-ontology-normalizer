"""Graph RAG API endpoints for AI agent access to the knowledge graph.

This module provides query interfaces that allow AI agents (LLMs) to:
1. Search the knowledge graph with semantic queries
2. Retrieve relevant clinical entities with provenance
3. Answer clinical questions with evidence from the graph
4. Navigate relationships between clinical concepts

The Graph RAG pattern combines graph-based retrieval with augmented generation,
enabling LLMs to provide deterministic answers with probabilistic reasoning
and full citation/provenance tracking.
"""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.knowledge_graph import KGNode, KGEdge

router = APIRouter(prefix="/graph-rag", tags=["Graph RAG"])


# ============================================================================
# Schema Models for Graph RAG
# ============================================================================


class GraphEntity(BaseModel):
    """A node from the knowledge graph with metadata."""
    id: str
    node_type: str
    label: str
    properties: dict[str, Any]
    source_date: str | None = None
    provenance: str = Field(description="Citation reference for this entity")


class GraphRelationship(BaseModel):
    """A relationship between entities."""
    source_id: str
    source_label: str
    relationship_type: str
    target_id: str
    target_label: str
    properties: dict[str, Any] = {}


class GraphSearchResult(BaseModel):
    """Result from a graph search query."""
    query: str
    patient_id: str
    entities: list[GraphEntity]
    relationships: list[GraphRelationship]
    total_entities: int
    total_relationships: int
    provenance_summary: str = Field(description="Summary of data sources")


class ClinicalAnswer(BaseModel):
    """A clinical answer with evidence from the knowledge graph."""
    question: str
    answer: str
    confidence: str = Field(description="high, medium, or low")
    evidence: list[GraphEntity]
    supporting_relationships: list[GraphRelationship]
    citations: list[str]
    reasoning: str = Field(description="Step-by-step reasoning for the answer")


class PatientSummary(BaseModel):
    """Comprehensive patient summary from the knowledge graph."""
    patient_id: str
    conditions: list[GraphEntity]
    medications: list[GraphEntity]
    recent_labs: list[GraphEntity]
    procedures: list[GraphEntity]
    observations: list[GraphEntity]
    treatment_relationships: list[GraphRelationship]
    complication_relationships: list[GraphRelationship]
    summary_text: str


# ============================================================================
# Graph RAG Query Endpoints
# ============================================================================


@router.get("/search/{patient_id}", response_model=GraphSearchResult)
async def search_graph(
    patient_id: str,
    query: Annotated[str, Query(description="Natural language search query")],
    node_types: Annotated[list[str] | None, Query(description="Filter by node types")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    include_relationships: Annotated[bool, Query()] = True,
    db: AsyncSession = Depends(get_db),
) -> GraphSearchResult:
    """
    Search the patient's knowledge graph with a natural language query.

    This endpoint allows AI agents to:
    - Search for clinical concepts by name, description, or value
    - Filter by entity type (condition, drug, measurement, procedure, observation)
    - Retrieve related entities through graph traversal
    - Get provenance information for each result

    Example queries:
    - "heart failure medications" → finds drugs treating HFrEF
    - "creatinine values" → finds all creatinine measurements with dates
    - "diabetes complications" → finds conditions linked to diabetes
    """
    # Build search terms from the query
    search_terms = query.lower().split()

    # Search nodes by label or properties
    stmt = select(KGNode).where(KGNode.patient_id == patient_id)

    # Add node type filter if specified
    if node_types:
        stmt = stmt.where(KGNode.node_type.in_(node_types))

    # Execute query
    result = await db.execute(stmt)
    all_nodes = result.scalars().all()

    # Filter nodes by search terms (simple text matching)
    matching_nodes = []
    for node in all_nodes:
        label_lower = node.label.lower()
        props_str = str(node.properties).lower() if node.properties else ""

        # Check if any search term matches
        if any(term in label_lower or term in props_str for term in search_terms):
            matching_nodes.append(node)

    # Limit results
    matching_nodes = matching_nodes[:limit]

    # Convert to GraphEntity with provenance
    entities = []
    for node in matching_nodes:
        props = node.properties or {}
        source_date = props.get('extracted_date', 'unknown')
        source_notes = props.get('source_notes', [])

        provenance = f"Source: Note(s) {source_notes}, Date: {source_date}"

        entities.append(GraphEntity(
            id=str(node.id),
            node_type=node.node_type,
            label=node.label,
            properties=props,
            source_date=source_date,
            provenance=provenance,
        ))

    # Get relationships if requested
    relationships = []
    if include_relationships and matching_nodes:
        node_ids = [str(n.id) for n in matching_nodes]

        edge_stmt = select(KGEdge).where(
            and_(
                KGEdge.patient_id == patient_id,
                or_(
                    KGEdge.source_node_id.in_(node_ids),
                    KGEdge.target_node_id.in_(node_ids)
                )
            )
        )
        edge_result = await db.execute(edge_stmt)
        edges = edge_result.scalars().all()

        # Need to get labels for source/target nodes
        all_node_ids = set()
        for edge in edges:
            all_node_ids.add(edge.source_node_id)
            all_node_ids.add(edge.target_node_id)

        node_labels = {}
        if all_node_ids:
            label_stmt = select(KGNode.id, KGNode.label).where(
                KGNode.id.in_(list(all_node_ids))
            )
            label_result = await db.execute(label_stmt)
            for row in label_result:
                node_labels[str(row.id)] = row.label

        for edge in edges:
            relationships.append(GraphRelationship(
                source_id=str(edge.source_node_id),
                source_label=node_labels.get(str(edge.source_node_id), "Unknown"),
                relationship_type=edge.edge_type,
                target_id=str(edge.target_node_id),
                target_label=node_labels.get(str(edge.target_node_id), "Unknown"),
                properties=edge.properties or {},
            ))

    # Build provenance summary
    dates = set()
    for e in entities:
        if e.source_date and e.source_date != 'unknown':
            dates.add(e.source_date)

    provenance_summary = f"Data from {len(dates)} dates: {', '.join(sorted(dates))}" if dates else "No date information available"

    return GraphSearchResult(
        query=query,
        patient_id=patient_id,
        entities=entities,
        relationships=relationships,
        total_entities=len(entities),
        total_relationships=len(relationships),
        provenance_summary=provenance_summary,
    )


@router.get("/patient-summary/{patient_id}", response_model=PatientSummary)
async def get_patient_summary(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
) -> PatientSummary:
    """
    Get a comprehensive patient summary from the knowledge graph.

    This is the primary endpoint for AI agents to get a complete overview
    of a patient's clinical state, including:
    - Active conditions
    - Current medications
    - Recent lab values
    - Procedures performed
    - Clinical observations
    - Treatment relationships (which drugs treat which conditions)
    - Complication relationships (which conditions led to others)

    Use this for:
    - Initial patient context before answering clinical questions
    - Generating patient summaries
    - Understanding the full clinical picture
    """
    # Get all nodes for the patient
    stmt = select(KGNode).where(KGNode.patient_id == patient_id)
    result = await db.execute(stmt)
    all_nodes = result.scalars().all()

    # Get all edges for the patient
    edge_stmt = select(KGEdge).where(KGEdge.patient_id == patient_id)
    edge_result = await db.execute(edge_stmt)
    all_edges = edge_result.scalars().all()

    # Categorize nodes
    conditions = []
    medications = []
    measurements = []
    procedures = []
    observations = []

    # Build node lookup for relationship labels
    node_lookup = {str(n.id): n.label for n in all_nodes}

    for node in all_nodes:
        props = node.properties or {}
        source_date = props.get('extracted_date', 'unknown')
        source_notes = props.get('source_notes', [])
        provenance = f"Source: Note(s) {source_notes}, Date: {source_date}"

        entity = GraphEntity(
            id=str(node.id),
            node_type=node.node_type,
            label=node.label,
            properties=props,
            source_date=source_date,
            provenance=provenance,
        )

        if node.node_type == 'condition':
            conditions.append(entity)
        elif node.node_type == 'drug':
            medications.append(entity)
        elif node.node_type == 'measurement':
            measurements.append(entity)
        elif node.node_type == 'procedure':
            procedures.append(entity)
        elif node.node_type == 'observation':
            observations.append(entity)

    # Sort measurements by date (most recent first)
    measurements.sort(key=lambda x: x.source_date or '', reverse=True)

    # Categorize relationships
    treatment_rels = []
    complication_rels = []

    for edge in all_edges:
        rel = GraphRelationship(
            source_id=str(edge.source_node_id),
            source_label=node_lookup.get(str(edge.source_node_id), "Unknown"),
            relationship_type=edge.edge_type,
            target_id=str(edge.target_node_id),
            target_label=node_lookup.get(str(edge.target_node_id), "Unknown"),
            properties=edge.properties or {},
        )

        if edge.edge_type in ('condition_treated_by', 'drug_treats'):
            treatment_rels.append(rel)
        elif edge.properties and edge.properties.get('relationship') == 'complication_of':
            complication_rels.append(rel)

    # Generate summary text
    summary_parts = []
    summary_parts.append(f"Patient {patient_id} has {len(conditions)} conditions, "
                        f"is on {len(medications)} medications.")

    if conditions:
        condition_names = [c.label for c in conditions[:5]]
        summary_parts.append(f"Key conditions: {', '.join(condition_names)}")

    if medications:
        med_names = [m.label for m in medications[:5]]
        summary_parts.append(f"Key medications: {', '.join(med_names)}")

    summary_text = " ".join(summary_parts)

    return PatientSummary(
        patient_id=patient_id,
        conditions=conditions,
        medications=medications,
        recent_labs=measurements[:20],  # Most recent 20 labs
        procedures=procedures,
        observations=observations,
        treatment_relationships=treatment_rels,
        complication_relationships=complication_rels,
        summary_text=summary_text,
    )


@router.post("/answer", response_model=ClinicalAnswer)
async def answer_clinical_question(
    patient_id: Annotated[str, Query(description="Patient identifier")],
    question: Annotated[str, Query(description="Clinical question to answer")],
    db: AsyncSession = Depends(get_db),
) -> ClinicalAnswer:
    """
    Answer a clinical question using evidence from the knowledge graph.

    This endpoint performs graph-based retrieval to find relevant entities
    and relationships, then formulates an answer with citations.

    The response includes:
    - The direct answer to the question
    - Confidence level based on available evidence
    - All supporting evidence (entities and relationships)
    - Citations to source data
    - Step-by-step reasoning

    Example questions:
    - "What medications is this patient taking for heart failure?"
    - "What is the patient's most recent creatinine value?"
    - "Does this patient have any drug allergies?"
    - "What are the complications of this patient's diabetes?"
    """
    # Parse question to extract key terms
    question_lower = question.lower()

    # Determine what type of information is being requested
    query_type = None
    search_terms = []

    if any(word in question_lower for word in ['medication', 'drug', 'taking', 'prescribed']):
        query_type = 'medications'
        search_terms = ['drug']
    elif any(word in question_lower for word in ['condition', 'diagnosis', 'disease', 'problem']):
        query_type = 'conditions'
        search_terms = ['condition']
    elif any(word in question_lower for word in ['lab', 'value', 'level', 'result', 'creatinine', 'hemoglobin', 'potassium']):
        query_type = 'labs'
        search_terms = ['measurement']
    elif any(word in question_lower for word in ['procedure', 'surgery', 'operation']):
        query_type = 'procedures'
        search_terms = ['procedure']
    elif any(word in question_lower for word in ['allergy', 'allergic']):
        query_type = 'allergies'
        search_terms = ['observation', 'allergy']

    # Search for relevant entities
    stmt = select(KGNode).where(KGNode.patient_id == patient_id)

    # Add type filter if determined
    if search_terms and search_terms[0] in ['drug', 'condition', 'measurement', 'procedure', 'observation']:
        stmt = stmt.where(KGNode.node_type == search_terms[0])

    result = await db.execute(stmt)
    all_nodes = result.scalars().all()

    # Further filter by question keywords
    stop_words = ['what', 'does', 'this', 'patient', 'have', 'taking', 'for', 'the', 'most', 'recent', 'are', 'their', 'tell', 'about', 'list', 'show']
    keywords = [word for word in question_lower.split()
                if len(word) > 3 and word not in stop_words]

    relevant_nodes = []
    for node in all_nodes:
        label_lower = node.label.lower()
        props_str = str(node.properties).lower() if node.properties else ""

        # Check if any keyword matches or if query type matches node type
        keyword_match = any(kw in label_lower or kw in props_str for kw in keywords) if keywords else False
        type_match = (query_type == 'conditions' and node.node_type == 'condition') or \
                     (query_type == 'medications' and node.node_type == 'drug') or \
                     (query_type == 'labs' and node.node_type == 'measurement') or \
                     (query_type == 'procedures' and node.node_type == 'procedure') or \
                     (query_type == 'allergies' and 'allergy' in label_lower)

        if keyword_match or type_match or not keywords:
            relevant_nodes.append(node)

    # Get related edges
    node_ids = [str(n.id) for n in relevant_nodes[:50]]
    relationships = []

    if node_ids:
        edge_stmt = select(KGEdge).where(
            and_(
                KGEdge.patient_id == patient_id,
                or_(
                    KGEdge.source_node_id.in_(node_ids),
                    KGEdge.target_node_id.in_(node_ids)
                )
            )
        )
        edge_result = await db.execute(edge_stmt)
        edges = edge_result.scalars().all()

        # Get all node labels
        all_node_ids = set()
        for edge in edges:
            all_node_ids.add(edge.source_node_id)
            all_node_ids.add(edge.target_node_id)

        node_labels = {}
        if all_node_ids:
            label_stmt = select(KGNode.id, KGNode.label).where(
                KGNode.id.in_(list(all_node_ids))
            )
            label_result = await db.execute(label_stmt)
            for row in label_result:
                node_labels[str(row.id)] = row.label

        for edge in edges:
            relationships.append(GraphRelationship(
                source_id=str(edge.source_node_id),
                source_label=node_labels.get(str(edge.source_node_id), "Unknown"),
                relationship_type=edge.edge_type,
                target_id=str(edge.target_node_id),
                target_label=node_labels.get(str(edge.target_node_id), "Unknown"),
                properties=edge.properties or {},
            ))

    # Build evidence list
    evidence = []
    citations = []

    for node in relevant_nodes[:10]:  # Limit to top 10
        props = node.properties or {}
        source_date = props.get('extracted_date', 'unknown')
        source_notes = props.get('source_notes', [])
        provenance = f"[{node.label}] from Note(s) {source_notes} on {source_date}"

        evidence.append(GraphEntity(
            id=str(node.id),
            node_type=node.node_type,
            label=node.label,
            properties=props,
            source_date=source_date,
            provenance=provenance,
        ))

        citations.append(provenance)

    # Generate answer based on evidence
    if not evidence:
        answer = "No relevant information found in the patient's knowledge graph."
        confidence = "low"
        reasoning = "No matching entities were found for the query terms."
    else:
        # Build answer from evidence
        entity_labels = [e.label for e in evidence]

        if query_type == 'medications':
            answer = f"Patient is taking: {', '.join(entity_labels[:10])}"
            confidence = "high" if len(evidence) > 0 else "low"
            reasoning = f"Found {len(evidence)} medication(s) in the knowledge graph."
        elif query_type == 'conditions':
            answer = f"Patient has the following conditions: {', '.join(entity_labels[:10])}"
            confidence = "high"
            reasoning = f"Found {len(evidence)} condition(s) documented."
        elif query_type == 'labs':
            # For labs, include values
            lab_parts = []
            for e in evidence[:5]:
                value = e.properties.get('value', '')
                unit = e.properties.get('unit', '')
                lab_parts.append(f"{e.label}: {value} {unit}")
            answer = f"Lab values: {'; '.join(lab_parts)}"
            confidence = "high"
            reasoning = f"Found {len(evidence)} lab measurement(s)."
        elif query_type == 'allergies':
            allergy_entities = [e for e in evidence if 'allergy' in e.label.lower()]
            if allergy_entities:
                answer = f"Patient has allergies to: {', '.join(e.label for e in allergy_entities)}"
                confidence = "high"
            else:
                answer = "No allergies documented in the knowledge graph."
                confidence = "medium"
            reasoning = f"Searched observation nodes for allergy information."
        else:
            answer = f"Based on the knowledge graph: {', '.join(entity_labels[:5])}"
            confidence = "medium"
            reasoning = f"Found {len(evidence)} relevant entities."

    return ClinicalAnswer(
        question=question,
        answer=answer,
        confidence=confidence,
        evidence=evidence,
        supporting_relationships=relationships[:20],
        citations=citations,
        reasoning=reasoning,
    )


@router.get("/traverse/{patient_id}/{node_id}", response_model=dict)
async def traverse_from_node(
    patient_id: str,
    node_id: str,
    depth: Annotated[int, Query(ge=1, le=3)] = 1,
    relationship_types: Annotated[list[str] | None, Query()] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Traverse the knowledge graph starting from a specific node.

    This allows AI agents to explore relationships from a known entity,
    useful for:
    - Finding what treats a condition
    - Finding complications of a disease
    - Finding all measurements related to a concept

    Parameters:
    - node_id: Starting node UUID
    - depth: How many hops to traverse (1-3)
    - relationship_types: Filter by edge types

    Returns nodes and edges reachable within the specified depth.
    """
    # Get the starting node
    node_stmt = select(KGNode).where(
        and_(KGNode.patient_id == patient_id, KGNode.id == node_id)
    )
    node_result = await db.execute(node_stmt)
    start_node = node_result.scalar_one_or_none()

    if not start_node:
        raise HTTPException(status_code=404, detail="Node not found")

    # Collect nodes and edges by traversing
    visited_nodes = {node_id}
    current_frontier = [node_id]
    all_nodes = [start_node]
    all_edges = []

    for _ in range(depth):
        if not current_frontier:
            break

        # Find edges from current frontier
        edge_stmt = select(KGEdge).where(
            and_(
                KGEdge.patient_id == patient_id,
                or_(
                    KGEdge.source_node_id.in_(current_frontier),
                    KGEdge.target_node_id.in_(current_frontier)
                )
            )
        )

        if relationship_types:
            edge_stmt = edge_stmt.where(KGEdge.edge_type.in_(relationship_types))

        edge_result = await db.execute(edge_stmt)
        edges = edge_result.scalars().all()

        # Collect new node IDs
        new_node_ids = set()
        for edge in edges:
            all_edges.append(edge)
            if edge.source_node_id not in visited_nodes:
                new_node_ids.add(edge.source_node_id)
            if edge.target_node_id not in visited_nodes:
                new_node_ids.add(edge.target_node_id)

        # Fetch new nodes
        if new_node_ids:
            new_node_stmt = select(KGNode).where(KGNode.id.in_(list(new_node_ids)))
            new_node_result = await db.execute(new_node_stmt)
            new_nodes = new_node_result.scalars().all()
            all_nodes.extend(new_nodes)

        visited_nodes.update(new_node_ids)
        current_frontier = list(new_node_ids)

    # Format response
    return {
        "start_node": {
            "id": str(start_node.id),
            "label": start_node.label,
            "node_type": start_node.node_type,
        },
        "traversal_depth": depth,
        "nodes": [
            {
                "id": str(n.id),
                "label": n.label,
                "node_type": n.node_type,
                "properties": n.properties or {},
            }
            for n in all_nodes
        ],
        "edges": [
            {
                "source_id": str(e.source_node_id),
                "target_id": str(e.target_node_id),
                "edge_type": e.edge_type,
                "properties": e.properties or {},
            }
            for e in all_edges
        ],
        "total_nodes": len(all_nodes),
        "total_edges": len(all_edges),
    }


@router.get("/concepts/{patient_id}", response_model=dict)
async def get_unique_concepts(
    patient_id: str,
    node_type: Annotated[str | None, Query()] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get all unique clinical concepts for a patient.

    This endpoint returns a deduplicated list of clinical concepts
    (conditions, medications, etc.) without temporal duplicates.

    Useful for AI agents to get a quick overview of:
    - What conditions the patient has
    - What medications they're on
    - What procedures they've had

    This is different from the full graph which includes temporal measurements.
    """
    stmt = select(KGNode.node_type, KGNode.label).where(
        KGNode.patient_id == patient_id
    ).distinct()

    if node_type:
        stmt = stmt.where(KGNode.node_type == node_type)

    result = await db.execute(stmt)
    rows = result.all()

    # Group by type
    concepts_by_type: dict[str, list[str]] = {}
    for row in rows:
        ntype = row.node_type
        label = row.label

        # Skip temporal labels (contain date info)
        if ' on ' in label and ('/' in label or 'Note_' in label):
            # Extract base concept from temporal label
            base_label = label.split(' (')[0] if ' (' in label else label
            label = base_label

        if ntype not in concepts_by_type:
            concepts_by_type[ntype] = []

        if label not in concepts_by_type[ntype]:
            concepts_by_type[ntype].append(label)

    return {
        "patient_id": patient_id,
        "concepts_by_type": concepts_by_type,
        "total_unique_concepts": sum(len(v) for v in concepts_by_type.values()),
    }
