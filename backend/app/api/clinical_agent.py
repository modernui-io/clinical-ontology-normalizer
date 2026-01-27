"""Clinical Agent API for bulk document processing and hybrid querying.

Provides endpoints for:
- Bulk document import with NLP processing
- Knowledge graph building from extracted entities
- Hybrid EHR + Knowledge Graph querying with LLM reasoning
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Document as DocumentModel
from app.models.clinical_fact import ClinicalFact
from app.models.knowledge_graph import KGEdge, KGNode
from app.models.mention import Mention as MentionModel
from app.schemas.base import Domain, JobStatus
from app.schemas.knowledge_graph import EdgeType, NodeType
from app.services.nlp_rule_based import RuleBasedNLPService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clinical-agent", tags=["Clinical Agent"])


# =============================================================================
# Request/Response Models
# =============================================================================


class ClinicalNote(BaseModel):
    """Single clinical note for bulk import."""

    note_id: str = Field(..., description="Unique identifier for this note")
    note_type: str = Field(..., description="Type: progress_note, discharge_summary, etc.")
    date: str = Field(..., description="Note date (YYYY-MM-DD)")
    text: str = Field(..., description="Clinical note text content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class BulkImportRequest(BaseModel):
    """Request for bulk document import."""

    patient_id: str = Field(..., description="Patient identifier")
    notes: list[ClinicalNote] = Field(..., min_length=1, max_length=500, description="List of clinical notes")
    build_knowledge_graph: bool = Field(True, description="Build knowledge graph after import")

    model_config = {
        "json_schema_extra": {
            "example": {
                "patient_id": "TEST12345",
                "notes": [
                    {
                        "note_id": "note_001",
                        "note_type": "progress_note",
                        "date": "2024-01-15",
                        "text": "Patient presents with type 2 diabetes, hypertension. Taking metformin 1000mg BID.",
                        "metadata": {"provider": "Dr. Smith"}
                    }
                ],
                "build_knowledge_graph": True
            }
        }
    }


class ExtractedEntity(BaseModel):
    """Entity extracted from clinical text."""

    text: str = Field(..., description="Extracted text span")
    entity_type: str = Field(..., description="CONDITION, DRUG, MEASUREMENT, PROCEDURE")
    confidence: float = Field(..., ge=0, le=1, description="Extraction confidence")
    assertion: str = Field("PRESENT", description="PRESENT, ABSENT, POSSIBLE")
    omop_concept_id: int | None = Field(None, description="Mapped OMOP concept ID")
    note_id: str = Field("frontend", description="Source note ID")


class BuildGraphFromEntitiesRequest(BaseModel):
    """Request to build knowledge graph from pre-extracted entities."""

    patient_id: str = Field(..., description="Patient identifier")
    entities: list[ExtractedEntity] = Field(..., min_length=1, max_length=5000, description="Pre-extracted entities")

    model_config = {
        "json_schema_extra": {
            "example": {
                "patient_id": "TEST67890",
                "entities": [
                    {
                        "text": "sickle cell disease",
                        "entity_type": "CONDITION",
                        "confidence": 0.95,
                        "assertion": "PRESENT",
                        "omop_concept_id": 4322024,
                        "note_id": "frontend"
                    },
                    {
                        "text": "hydroxyurea",
                        "entity_type": "DRUG",
                        "confidence": 0.92,
                        "assertion": "PRESENT",
                        "omop_concept_id": 1305058,
                        "note_id": "frontend"
                    }
                ]
            }
        }
    }


class BuildGraphResponse(BaseModel):
    """Response from building graph from pre-extracted entities."""

    patient_id: str
    entities_processed: int
    knowledge_graph: KnowledgeGraphSummary
    processing_time_ms: float


class ImportedNote(BaseModel):
    """Result for a single imported note."""

    note_id: str
    document_id: UUID
    entity_count: int
    entities: list[ExtractedEntity]


class BulkImportResponse(BaseModel):
    """Response from bulk document import."""

    patient_id: str
    total_notes: int
    total_entities: int
    notes: list[ImportedNote]
    knowledge_graph: KnowledgeGraphSummary | None = None
    processing_time_ms: float


class KnowledgeGraphSummary(BaseModel):
    """Summary of knowledge graph for a patient."""

    patient_id: str
    node_count: int
    edge_count: int
    conditions: list[str]
    medications: list[str]
    measurements: list[str]
    procedures: list[str]


class KGNodeResponse(BaseModel):
    """Knowledge graph node for API response."""

    id: str
    node_type: str
    label: str
    omop_concept_id: int | None
    properties: dict


class KGEdgeResponse(BaseModel):
    """Knowledge graph edge for API response."""

    id: str
    source_id: str
    target_id: str
    edge_type: str
    properties: dict


class PatientGraphResponse(BaseModel):
    """Complete patient knowledge graph."""

    patient_id: str
    nodes: list[KGNodeResponse]
    edges: list[KGEdgeResponse]
    summary: KnowledgeGraphSummary


class HybridQueryRequest(BaseModel):
    """Request for hybrid EHR + KG query."""

    question: str = Field(..., min_length=3, description="Natural language question")
    include_evidence: bool = Field(True, description="Include source evidence in response")
    max_results: int = Field(10, ge=1, le=50, description="Maximum results to return")

    model_config = {
        "json_schema_extra": {
            "example": {
                "question": "What medications is the patient taking for diabetes?",
                "include_evidence": True,
                "max_results": 10
            }
        }
    }


class EvidenceSource(BaseModel):
    """Evidence from a clinical note."""

    note_id: str
    note_type: str
    note_date: str
    excerpt: str
    relevance_score: float


class HybridQueryResponse(BaseModel):
    """Response from hybrid query."""

    question: str
    answer: str
    confidence: float
    sources: list[str]
    entities_found: list[ExtractedEntity]
    evidence: list[EvidenceSource] = []
    knowledge_graph_paths: list[dict] = []
    reasoning: str | None = None
    guideline_citations: list[dict] = []


# =============================================================================
# Helper Functions
# =============================================================================


def _domain_to_node_type(domain: str) -> NodeType:
    """Map domain string to NodeType."""
    mapping = {
        "CONDITION": NodeType.CONDITION,
        "DRUG": NodeType.DRUG,
        "MEASUREMENT": NodeType.MEASUREMENT,
        "PROCEDURE": NodeType.PROCEDURE,
        "OBSERVATION": NodeType.OBSERVATION,
    }
    return mapping.get(domain.upper(), NodeType.OBSERVATION)


def _node_type_to_edge_type(node_type: NodeType) -> EdgeType:
    """Map node type to patient edge type."""
    mapping = {
        NodeType.CONDITION: EdgeType.HAS_CONDITION,
        NodeType.DRUG: EdgeType.TAKES_DRUG,
        NodeType.MEASUREMENT: EdgeType.HAS_MEASUREMENT,
        NodeType.PROCEDURE: EdgeType.HAS_PROCEDURE,
        NodeType.OBSERVATION: EdgeType.HAS_OBSERVATION,
    }
    return mapping.get(node_type, EdgeType.HAS_OBSERVATION)


# =============================================================================
# API Endpoints
# =============================================================================


@router.post(
    "/import",
    response_model=BulkImportResponse,
    summary="Bulk import clinical documents",
    description="Import multiple clinical notes, extract entities via NLP, and optionally build knowledge graph.",
)
async def bulk_import_documents(
    request: BulkImportRequest,
    db: AsyncSession = Depends(get_db),
) -> BulkImportResponse:
    """Bulk import clinical documents with NLP processing.

    This endpoint:
    1. Stores all documents in the database
    2. Runs NLP extraction on each document
    3. Optionally builds a patient knowledge graph
    """
    start_time = datetime.now(timezone.utc)

    # Initialize NLP service
    nlp_service = RuleBasedNLPService()

    imported_notes: list[ImportedNote] = []
    all_entities: list[ExtractedEntity] = []

    # Process each note
    for note in request.notes:
        # Create document record
        doc_id = str(uuid4())
        db_document = DocumentModel(
            id=doc_id,
            patient_id=request.patient_id,
            note_type=note.note_type,
            text=note.text,
            extra_metadata={
                **note.metadata,
                "original_note_id": note.note_id,
                "note_date": note.date,
            },
            status=JobStatus.COMPLETED,
            processed_at=datetime.now(timezone.utc),
        )
        db.add(db_document)

        # Extract entities using NLP
        try:
            mentions = nlp_service.extract_mentions(note.text, doc_id)

            note_entities: list[ExtractedEntity] = []
            for mention in mentions:
                # Map domain_hint to entity_type (Condition, Drug, etc.)
                domain = getattr(mention, 'domain_hint', None) or 'OBSERVATION'
                entity_type = domain.upper() if domain else 'OBSERVATION'

                entity = ExtractedEntity(
                    text=mention.text,
                    entity_type=entity_type,
                    confidence=mention.confidence,
                    assertion=str(getattr(mention, 'assertion', 'PRESENT')),
                    omop_concept_id=getattr(mention, 'omop_concept_id', None),
                    note_id=note.note_id,
                )
                note_entities.append(entity)
                all_entities.append(entity)

                # Store mention in database
                # Get enum values properly (strip "EnumName." prefix if present)
                assertion_val = getattr(mention, 'assertion', 'PRESENT')
                if hasattr(assertion_val, 'value'):
                    assertion_val = assertion_val.value
                else:
                    assertion_val = str(assertion_val).split('.')[-1]  # "Assertion.PRESENT" -> "PRESENT"

                temporality_val = getattr(mention, 'temporality', 'CURRENT')
                if hasattr(temporality_val, 'value'):
                    temporality_val = temporality_val.value
                else:
                    temporality_val = str(temporality_val).split('.')[-1]

                experiencer_val = getattr(mention, 'experiencer', 'PATIENT')
                if hasattr(experiencer_val, 'value'):
                    experiencer_val = experiencer_val.value
                else:
                    experiencer_val = str(experiencer_val).split('.')[-1]

                db_mention = MentionModel(
                    id=str(uuid4()),
                    document_id=doc_id,
                    text=mention.text,
                    start_offset=mention.start_offset,
                    end_offset=mention.end_offset,
                    lexical_variant=mention.text.lower(),
                    section=getattr(mention, 'section', None),
                    assertion=assertion_val,
                    temporality=temporality_val,
                    experiencer=experiencer_val,
                    confidence=mention.confidence,
                )
                db.add(db_mention)

            imported_notes.append(ImportedNote(
                note_id=note.note_id,
                document_id=UUID(doc_id),
                entity_count=len(note_entities),
                entities=note_entities,
            ))

        except Exception as e:
            logger.error(f"NLP extraction failed for note {note.note_id}: {e}")
            imported_notes.append(ImportedNote(
                note_id=note.note_id,
                document_id=UUID(doc_id),
                entity_count=0,
                entities=[],
            ))

    # Commit documents and mentions
    await db.commit()

    # Build knowledge graph if requested
    kg_summary = None
    if request.build_knowledge_graph:
        kg_summary = await _build_patient_knowledge_graph(
            db, request.patient_id, all_entities
        )
        await db.commit()

    end_time = datetime.now(timezone.utc)
    processing_time_ms = (end_time - start_time).total_seconds() * 1000

    return BulkImportResponse(
        patient_id=request.patient_id,
        total_notes=len(request.notes),
        total_entities=len(all_entities),
        notes=imported_notes,
        knowledge_graph=kg_summary,
        processing_time_ms=round(processing_time_ms, 2),
    )


@router.post(
    "/build-graph",
    response_model=BuildGraphResponse,
    summary="Build knowledge graph from pre-extracted entities",
    description="Build a patient knowledge graph using entities already extracted by the frontend NLP.",
)
async def build_graph_from_entities(
    request: BuildGraphFromEntitiesRequest,
    db: AsyncSession = Depends(get_db),
) -> BuildGraphResponse:
    """Build knowledge graph from pre-extracted entities.

    This endpoint accepts entities that have already been extracted by the frontend
    NLP service, allowing the richer extraction results to be used for graph building.
    """
    start_time = datetime.now(timezone.utc)

    # Build the knowledge graph directly from provided entities
    kg_summary = await _build_patient_knowledge_graph(
        db, request.patient_id, request.entities
    )
    await db.commit()

    end_time = datetime.now(timezone.utc)
    processing_time_ms = (end_time - start_time).total_seconds() * 1000

    return BuildGraphResponse(
        patient_id=request.patient_id,
        entities_processed=len(request.entities),
        knowledge_graph=kg_summary,
        processing_time_ms=round(processing_time_ms, 2),
    )


async def _build_patient_knowledge_graph(
    db: AsyncSession,
    patient_id: str,
    entities: list[ExtractedEntity],
) -> KnowledgeGraphSummary:
    """Build knowledge graph from extracted entities."""

    # Clear existing graph for this patient
    await db.execute(
        delete(KGEdge).where(KGEdge.patient_id == patient_id)
    )
    await db.execute(
        delete(KGNode).where(KGNode.patient_id == patient_id)
    )

    # Create patient node
    patient_node_id = str(uuid4())
    patient_node = KGNode(
        id=patient_node_id,
        patient_id=patient_id,
        node_type=NodeType.PATIENT,
        label=f"Patient {patient_id}",
        omop_concept_id=None,
        properties={"created_at": datetime.now(timezone.utc).isoformat()},
    )
    db.add(patient_node)

    # Track unique entities (deduplicate by text + type)
    seen_entities: dict[str, str] = {}  # (text_lower, type) -> node_id
    conditions: list[str] = []
    medications: list[str] = []
    measurements: list[str] = []
    procedures: list[str] = []

    node_count = 1  # Patient node
    edge_count = 0

    for entity in entities:
        # Skip low confidence entities
        if entity.confidence < 0.5:
            continue

        # Skip negated entities for graph (but could include with property)
        if entity.assertion == "ABSENT":
            continue

        entity_key = f"{entity.text.lower()}|{entity.entity_type}"

        if entity_key not in seen_entities:
            # Create new node
            node_id = str(uuid4())
            node_type = _domain_to_node_type(entity.entity_type)

            entity_node = KGNode(
                id=node_id,
                patient_id=patient_id,
                node_type=node_type,
                label=entity.text,
                omop_concept_id=entity.omop_concept_id,
                properties={
                    "assertion": entity.assertion,
                    "confidence": entity.confidence,
                    "source_notes": [entity.note_id],
                },
            )
            db.add(entity_node)
            seen_entities[entity_key] = node_id
            node_count += 1

            # Create edge from patient to entity
            edge_type = _node_type_to_edge_type(node_type)
            edge = KGEdge(
                id=str(uuid4()),
                patient_id=patient_id,
                source_node_id=patient_node_id,
                target_node_id=node_id,
                edge_type=edge_type,
                properties={"first_noted": entity.note_id},
            )
            db.add(edge)
            edge_count += 1

            # Track for summary
            if node_type == NodeType.CONDITION:
                conditions.append(entity.text)
            elif node_type == NodeType.DRUG:
                medications.append(entity.text)
            elif node_type == NodeType.MEASUREMENT:
                measurements.append(entity.text)
            elif node_type == NodeType.PROCEDURE:
                procedures.append(entity.text)
        else:
            # Update existing node with additional source note
            # (In production, would update the properties)
            pass

    # Create treatment relationships (Drug -> treats -> Condition)
    # This is a simplified heuristic - in production use clinical knowledge
    for drug_key, drug_node_id in seen_entities.items():
        if "|DRUG" not in drug_key:
            continue
        drug_text = drug_key.split("|")[0]

        # Simple matching: metformin -> diabetes, lisinopril -> hypertension
        treatment_map = {
            "metformin": ["diabetes", "dm", "dm2", "type 2 diabetes"],
            "lisinopril": ["hypertension", "htn", "high blood pressure"],
            "atorvastatin": ["hyperlipidemia", "cholesterol"],
            "aspirin": ["coronary", "cad", "mi", "heart"],
            "furosemide": ["heart failure", "chf", "edema", "hfref"],
            "carvedilol": ["heart failure", "chf", "hfref"],
            "apixaban": ["afib", "atrial fibrillation", "dvt", "pe"],
            "warfarin": ["afib", "atrial fibrillation", "dvt"],
            "amlodipine": ["hypertension", "htn"],
            "insulin": ["diabetes", "dm", "dm2"],
        }

        for drug_pattern, condition_patterns in treatment_map.items():
            if drug_pattern in drug_text.lower():
                for condition_key, condition_node_id in seen_entities.items():
                    if "|CONDITION" not in condition_key:
                        continue
                    condition_text = condition_key.split("|")[0]

                    if any(cp in condition_text.lower() for cp in condition_patterns):
                        # Create treats relationship
                        treats_edge = KGEdge(
                            id=str(uuid4()),
                            patient_id=patient_id,
                            source_node_id=drug_node_id,
                            target_node_id=condition_node_id,
                            edge_type=EdgeType.DRUG_TREATS,
                            properties={"inferred": True},
                        )
                        db.add(treats_edge)
                        edge_count += 1

    return KnowledgeGraphSummary(
        patient_id=patient_id,
        node_count=node_count,
        edge_count=edge_count,
        conditions=list(set(conditions))[:20],
        medications=list(set(medications))[:20],
        measurements=list(set(measurements))[:20],
        procedures=list(set(procedures))[:20],
    )


@router.get(
    "/graph/{patient_id}",
    response_model=PatientGraphResponse,
    summary="Get patient knowledge graph",
    description="Retrieve the complete knowledge graph for a patient.",
)
async def get_patient_graph(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
) -> PatientGraphResponse:
    """Get the knowledge graph for a patient."""

    # Get all nodes for patient
    nodes_result = await db.execute(
        select(KGNode).where(KGNode.patient_id == patient_id)
    )
    nodes = nodes_result.scalars().all()

    if not nodes:
        raise HTTPException(
            status_code=404,
            detail=f"No knowledge graph found for patient {patient_id}"
        )

    # Get all edges for patient
    edges_result = await db.execute(
        select(KGEdge).where(KGEdge.patient_id == patient_id)
    )
    edges = edges_result.scalars().all()

    # Build response
    node_responses = [
        KGNodeResponse(
            id=str(n.id),
            node_type=n.node_type.value if hasattr(n.node_type, 'value') else str(n.node_type),
            label=n.label,
            omop_concept_id=n.omop_concept_id,
            properties=n.properties or {},
        )
        for n in nodes
    ]

    edge_responses = [
        KGEdgeResponse(
            id=str(e.id),
            source_id=str(e.source_node_id),
            target_id=str(e.target_node_id),
            edge_type=e.edge_type.value if hasattr(e.edge_type, 'value') else str(e.edge_type),
            properties=e.properties or {},
        )
        for e in edges
    ]

    # Build summary
    conditions = [n.label for n in nodes if n.node_type == NodeType.CONDITION]
    medications = [n.label for n in nodes if n.node_type == NodeType.DRUG]
    measurements = [n.label for n in nodes if n.node_type == NodeType.MEASUREMENT]
    procedures = [n.label for n in nodes if n.node_type == NodeType.PROCEDURE]

    summary = KnowledgeGraphSummary(
        patient_id=patient_id,
        node_count=len(nodes),
        edge_count=len(edges),
        conditions=conditions[:20],
        medications=medications[:20],
        measurements=measurements[:20],
        procedures=procedures[:20],
    )

    return PatientGraphResponse(
        patient_id=patient_id,
        nodes=node_responses,
        edges=edge_responses,
        summary=summary,
    )


@router.post(
    "/query/{patient_id}",
    response_model=HybridQueryResponse,
    summary="Query patient data with hybrid reasoning",
    description="Ask natural language questions combining EHR data and knowledge graph.",
)
async def hybrid_query(
    patient_id: str,
    request: HybridQueryRequest,
    db: AsyncSession = Depends(get_db),
) -> HybridQueryResponse:
    """Hybrid query combining EHR and knowledge graph.

    This endpoint:
    1. Searches documents for relevant mentions
    2. Queries the knowledge graph for related entities
    3. Combines results with reasoning
    """
    question = request.question.lower()

    # Get patient's documents (optional - may not exist for hybrid-built graphs)
    docs_result = await db.execute(
        select(DocumentModel).where(DocumentModel.patient_id == patient_id)
    )
    documents = list(docs_result.scalars().all())

    # Get knowledge graph nodes
    nodes_result = await db.execute(
        select(KGNode).where(KGNode.patient_id == patient_id)
    )
    nodes = list(nodes_result.scalars().all())

    if not documents and not nodes:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for patient {patient_id}"
        )

    # Simple keyword-based relevance scoring
    relevant_entities: list[ExtractedEntity] = []
    evidence_sources: list[EvidenceSource] = []

    # Determine query intent
    query_keywords = {
        "medication": ["medication", "drug", "taking", "prescribed", "medicine"],
        "condition": ["diagnosis", "condition", "disease", "problem", "have", "has"],
        "lab": ["lab", "test", "result", "level", "value"],
        "vital": ["vital", "blood pressure", "heart rate", "temperature"],
    }

    query_type = "general"
    for qtype, keywords in query_keywords.items():
        if any(kw in question for kw in keywords):
            query_type = qtype
            break

    # Filter nodes by query type
    target_node_types = {
        "medication": [NodeType.DRUG],
        "condition": [NodeType.CONDITION],
        "lab": [NodeType.MEASUREMENT],
        "vital": [NodeType.MEASUREMENT],
        "general": [NodeType.CONDITION, NodeType.DRUG, NodeType.MEASUREMENT, NodeType.PROCEDURE],
    }

    matching_nodes = [
        n for n in nodes
        if n.node_type in target_node_types.get(query_type, [])
    ]

    # Build entities from matching nodes
    for node in matching_nodes[:request.max_results]:
        relevant_entities.append(ExtractedEntity(
            text=node.label,
            entity_type=node.node_type.value if hasattr(node.node_type, 'value') else str(node.node_type),
            confidence=node.properties.get("confidence", 0.9) if node.properties else 0.9,
            assertion=node.properties.get("assertion", "PRESENT") if node.properties else "PRESENT",
            omop_concept_id=node.omop_concept_id,
            note_id=node.properties.get("source_notes", ["unknown"])[0] if node.properties else "unknown",
        ))

    # Find evidence in documents (only if documents exist)
    if request.include_evidence and documents:
        search_terms = [n.label.lower() for n in matching_nodes[:5]]

        for doc in documents[:20]:
            doc_text = doc.text.lower()
            relevance = sum(1 for term in search_terms if term in doc_text)

            if relevance > 0:
                # Extract relevant excerpt
                excerpt = doc.text[:300] + "..." if len(doc.text) > 300 else doc.text

                evidence_sources.append(EvidenceSource(
                    note_id=doc.extra_metadata.get("original_note_id", str(doc.id)),
                    note_type=doc.note_type,
                    note_date=doc.extra_metadata.get("note_date", "unknown"),
                    excerpt=excerpt,
                    relevance_score=min(relevance / len(search_terms), 1.0) if search_terms else 0.5,
                ))

        # Sort by relevance
        evidence_sources.sort(key=lambda x: x.relevance_score, reverse=True)
        evidence_sources = evidence_sources[:5]

    # Build clinical context for LLM
    conditions = [n.label for n in nodes if n.node_type == NodeType.CONDITION]
    medications = [n.label for n in nodes if n.node_type == NodeType.DRUG]
    measurements = [n.label for n in nodes if n.node_type == NodeType.MEASUREMENT]
    procedures = [n.label for n in nodes if n.node_type == NodeType.PROCEDURE]

    clinical_context = f"""Patient ID: {patient_id}

Knowledge Graph Summary ({len(nodes)} nodes):
- Conditions ({len(conditions)}): {', '.join(conditions[:30]) if conditions else 'None recorded'}
- Medications ({len(medications)}): {', '.join(medications[:30]) if medications else 'None recorded'}
- Measurements ({len(measurements)}): {', '.join(measurements[:30]) if measurements else 'None recorded'}
- Procedures ({len(procedures)}): {', '.join(procedures[:30]) if procedures else 'None recorded'}"""

    # Add document evidence if available
    if evidence_sources:
        clinical_context += "\n\nRelevant Clinical Notes:"
        for ev in evidence_sources[:3]:
            clinical_context += f"\n[{ev.note_type} - {ev.note_date}]: {ev.excerpt}"

    # Retrieve relevant clinical guidelines via RAG
    guideline_citations_data: list[dict] = []
    guideline_context = ""
    try:
        from app.services.guideline_rag_service import get_guideline_rag_service

        rag_service = get_guideline_rag_service()

        # Two-pool search: topic-relevant (raw question) + patient-relevant (with context)
        # This ensures guidelines matching the question topic always surface,
        # even when the patient's existing conditions dominate scoring.
        topic_citations = rag_service.search(
            query=request.question,
            top_k=3,
            min_score=0.25,
        )
        patient_citations = rag_service.search(
            query=request.question,
            patient_conditions=conditions,
            patient_medications=medications,
            patient_measurements=measurements,
            top_k=5,
            min_score=0.3,
        )
        # Merge: topic results first, then patient results (deduplicated)
        seen_ids: set[str] = set()
        citations = []
        for c in topic_citations + patient_citations:
            if c.section.section_id not in seen_ids:
                seen_ids.add(c.section.section_id)
                citations.append(c)
            if len(citations) >= 5:
                break

        if citations:
            guideline_context = "\n\nClinical Guideline References:"
            for i, citation in enumerate(citations, 1):
                sec = citation.section
                guideline_context += (
                    f"\n[Guideline {i}] {sec.guideline} — {sec.section_title} "
                    f"(Evidence: {sec.evidence_grade}, {sec.recommendation_level}): "
                    f"{sec.recommendation_text}"
                )
                guideline_citations_data.append({
                    "guideline_number": i,
                    "section_id": sec.section_id,
                    "guideline": sec.guideline,
                    "section_title": sec.section_title,
                    "recommendation_text": sec.recommendation_text,
                    "evidence_grade": sec.evidence_grade,
                    "recommendation_level": sec.recommendation_level,
                    "relevance_score": citation.score,
                    "match_reasons": citation.match_reasons,
                })

            logger.info(f"Retrieved {len(citations)} guideline sections for query")

    except Exception as e:
        logger.warning(f"Guideline RAG retrieval failed, proceeding without: {e}")

    # Use LLM to generate answer
    try:
        from app.services.llm_service import get_llm_service, LLMProvider

        llm = get_llm_service()

        system_prompt = """You are a clinical decision support assistant analyzing a patient's electronic health record data.
You have access to a knowledge graph built from the patient's clinical notes.

Guidelines:
- Answer questions based ONLY on the provided clinical data and guideline references
- Be specific and cite relevant entities from the knowledge graph
- When clinical guideline references are provided, incorporate them into your answer using [Guideline N] citation format
- Distinguish between patient-specific data (from the knowledge graph) and general recommendations (from guidelines)
- If the data is insufficient, say so clearly
- Use clinical terminology appropriately
- Keep answers concise but thorough (2-4 sentences for simple questions, more for complex ones)
- Never fabricate information not present in the data or guidelines"""

        user_prompt = f"""{clinical_context}{guideline_context}

Question: {request.question}

Provide a clear, evidence-based answer using the clinical data above."""
        if guideline_citations_data:
            user_prompt += " Reference relevant guidelines using [Guideline N] citations where applicable."

        response = await llm.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            provider=LLMProvider.ANTHROPIC,
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            temperature=0.2,
        )

        answer = response.content
        model_used = response.model
        confidence = min(0.95, 0.6 + len(relevant_entities) * 0.03 + len(evidence_sources) * 0.08)
        # Boost confidence for guideline matches
        confidence = min(0.95, confidence + len(guideline_citations_data) * 0.05)
        guideline_info = f", {len(guideline_citations_data)} guideline references" if guideline_citations_data else ""
        reasoning = (
            f"Answered using {model_used} with {len(nodes)} KG nodes, "
            f"{len(evidence_sources)} evidence sources{guideline_info}. "
            f"Latency: {response.latency_ms:.0f}ms, "
            f"Tokens: {response.token_usage.total_tokens}"
        )

    except Exception as e:
        logger.warning(f"LLM query failed, falling back to template: {e}")
        # Fallback to simple template if LLM fails
        if query_type == "medication":
            meds_list = [e.text for e in relevant_entities if e.entity_type.upper() == "DRUG"]
            answer = f"The patient is taking: {', '.join(meds_list[:10])}." if meds_list else "No medications found."
        elif query_type == "condition":
            conds_list = [e.text for e in relevant_entities if e.entity_type.upper() == "CONDITION"]
            answer = f"The patient has: {', '.join(conds_list[:10])}." if conds_list else "No conditions found."
        else:
            answer = f"Found {len(relevant_entities)} relevant findings." if relevant_entities else "No relevant information found."
        confidence = 0.5
        reasoning = f"Fallback template (LLM error: {e}). Query type: '{query_type}'."

    # Build sources list including both documents and guidelines
    sources = [f"Document: {e.note_id}" for e in evidence_sources]
    for gc in guideline_citations_data:
        sources.append(f"Guideline: {gc['guideline']} — {gc['section_title']}")

    return HybridQueryResponse(
        question=request.question,
        answer=answer,
        confidence=round(confidence, 2),
        sources=sources,
        entities_found=relevant_entities[:request.max_results],
        evidence=evidence_sources if request.include_evidence else [],
        knowledge_graph_paths=[],
        reasoning=reasoning,
        guideline_citations=guideline_citations_data,
    )


@router.delete(
    "/graph/{patient_id}",
    summary="Delete patient knowledge graph",
    description="Remove all knowledge graph data for a patient.",
)
async def delete_patient_graph(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a patient's knowledge graph."""

    # Delete edges first (foreign key constraint)
    edges_result = await db.execute(
        delete(KGEdge).where(KGEdge.patient_id == patient_id)
    )
    edges_deleted = edges_result.rowcount

    # Delete nodes
    nodes_result = await db.execute(
        delete(KGNode).where(KGNode.patient_id == patient_id)
    )
    nodes_deleted = nodes_result.rowcount

    await db.commit()

    return {
        "patient_id": patient_id,
        "nodes_deleted": nodes_deleted,
        "edges_deleted": edges_deleted,
    }


@router.get(
    "/patients",
    summary="List patients with knowledge graphs",
    description="Get list of patients that have knowledge graphs.",
)
async def list_patients_with_graphs(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    """List patients with knowledge graphs."""

    # Get distinct patient IDs with node counts
    result = await db.execute(
        select(
            KGNode.patient_id,
            func.count(KGNode.id).label("node_count")
        )
        .group_by(KGNode.patient_id)
        .order_by(func.count(KGNode.id).desc())
        .offset(offset)
        .limit(limit)
    )

    patients = [
        {"patient_id": row[0], "node_count": row[1]}
        for row in result.all()
    ]

    return {
        "total": len(patients),
        "patients": patients,
    }
