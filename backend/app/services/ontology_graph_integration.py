"""Ontology Mapper to Knowledge Graph Integration.

This service bridges the Clinical Ontology Mapper output to the existing
DatabaseGraphBuilderService, enabling persistent storage of ontology-mapped
clinical notes in the knowledge graph.

Instead of creating a parallel system, this integrates with existing infrastructure:
- Uses existing NodeType and EdgeType from schemas/knowledge_graph.py
- Uses existing DatabaseGraphBuilderService for persistence
- Uses existing KGNode and KGEdge models

Flow:
1. Clinical Note → Ontology Mapper → OntologyMappingResult
2. OntologyMappingResult → This Integration → NodeInput/EdgeInput
3. NodeInput/EdgeInput → DatabaseGraphBuilderService → Database
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.schemas.base import Domain
from app.schemas.knowledge_graph import EdgeType, NodeType
from app.services.clinical_ontology_mapper import (
    ClassifiedToken,
    OntologyCategory,
    OntologyMappingResult,
    Relationship,
    RelationType,
    get_ontology_mapper,
)
from app.services.graph_builder import NodeInput, EdgeInput, GraphResult
from app.services.graph_builder_db import DatabaseGraphBuilderService

logger = logging.getLogger(__name__)


@dataclass
class NoteIngestionResult:
    """Result of ingesting a clinical note into the knowledge graph."""
    note_id: str
    patient_id: str
    nodes_created: int
    edges_created: int
    entities_mapped: int
    relationships_mapped: int
    processing_time_ms: float
    coverage_stats: dict[str, Any]


class OntologyGraphIntegration:
    """Integrates Ontology Mapper output with the Knowledge Graph.

    This service converts ontology mapping results into knowledge graph
    nodes and edges using the existing graph builder infrastructure.

    Example usage:
        >>> integration = OntologyGraphIntegration(session)
        >>> result = integration.ingest_note(
        ...     note_text="Patient presents with chest pain...",
        ...     patient_id="P001",
        ... )
        >>> print(f"Created {result.nodes_created} nodes, {result.edges_created} edges")
    """

    # Mapping from OntologyCategory to NodeType
    CATEGORY_TO_NODE_TYPE = {
        OntologyCategory.DIAGNOSIS: NodeType.CONDITION,
        OntologyCategory.SYMPTOM: NodeType.CONDITION,
        OntologyCategory.FINDING: NodeType.OBSERVATION,
        OntologyCategory.MEDICATION: NodeType.DRUG,
        OntologyCategory.PROCEDURE: NodeType.PROCEDURE,
        OntologyCategory.LAB_TEST: NodeType.MEASUREMENT,
        OntologyCategory.LAB_VALUE: NodeType.MEASUREMENT,
        OntologyCategory.VITAL_SIGN: NodeType.MEASUREMENT,
        OntologyCategory.VITAL_VALUE: NodeType.MEASUREMENT,
        OntologyCategory.IMAGING: NodeType.PROCEDURE,
        OntologyCategory.ALLERGY: NodeType.OBSERVATION,
    }

    # Mapping from OntologyCategory to EdgeType (patient -> entity)
    CATEGORY_TO_EDGE_TYPE = {
        OntologyCategory.DIAGNOSIS: EdgeType.HAS_CONDITION,
        OntologyCategory.SYMPTOM: EdgeType.HAS_CONDITION,
        OntologyCategory.FINDING: EdgeType.HAS_OBSERVATION,
        OntologyCategory.MEDICATION: EdgeType.TAKES_DRUG,
        OntologyCategory.PROCEDURE: EdgeType.HAS_PROCEDURE,
        OntologyCategory.LAB_TEST: EdgeType.HAS_MEASUREMENT,
        OntologyCategory.LAB_VALUE: EdgeType.HAS_MEASUREMENT,
        OntologyCategory.VITAL_SIGN: EdgeType.HAS_MEASUREMENT,
        OntologyCategory.VITAL_VALUE: EdgeType.HAS_MEASUREMENT,
        OntologyCategory.IMAGING: EdgeType.HAS_PROCEDURE,
        OntologyCategory.ALLERGY: EdgeType.HAS_OBSERVATION,
    }

    # Mapping from RelationType to EdgeType
    RELATION_TO_EDGE_TYPE = {
        RelationType.TREATED_WITH: EdgeType.CONDITION_TREATED_BY,
        RelationType.INTERACTS_WITH: EdgeType.HAS_OBSERVATION,  # Drug interactions as observations
        # Most relationships become observations in the simple model
    }

    def __init__(self, session: Session) -> None:
        """Initialize the integration service.

        Args:
            session: SQLAlchemy database session.
        """
        self._session = session
        self._graph_builder = DatabaseGraphBuilderService(session)
        self._ontology_mapper = get_ontology_mapper()

        # Cache for entity resolution (normalized_name -> node_id)
        self._entity_cache: dict[str, UUID] = {}

    def ingest_note(
        self,
        note_text: str,
        patient_id: str,
        note_id: str | None = None,
        encounter_id: str | None = None,
        note_datetime: datetime | None = None,
    ) -> NoteIngestionResult:
        """Ingest a clinical note into the knowledge graph.

        This method:
        1. Processes the note through the ontology mapper
        2. Converts entities to graph nodes
        3. Converts relationships to graph edges
        4. Persists to the database via the graph builder

        Args:
            note_text: The clinical note text.
            patient_id: Patient identifier.
            note_id: Optional note identifier.
            encounter_id: Optional encounter identifier.
            note_datetime: When the note was created.

        Returns:
            NoteIngestionResult with statistics.
        """
        import time
        start_time = time.perf_counter()

        note_id = note_id or f"note_{uuid4().hex[:12]}"
        note_datetime = note_datetime or datetime.now(timezone.utc)

        # Step 1: Process note through ontology mapper
        mapping_result = self._ontology_mapper.map_note(note_text)

        # Step 2: Ensure patient node exists
        patient_node_id = self._graph_builder.create_patient_node(patient_id)

        # Step 3: Convert entities to nodes
        nodes_created = 0
        entity_node_map: dict[int, UUID] = {}  # token id -> node UUID

        for entity in mapping_result.entities:
            node_type = self.CATEGORY_TO_NODE_TYPE.get(entity.category)
            if not node_type:
                continue

            # Create node
            node_id = self._create_entity_node(
                entity=entity,
                patient_id=patient_id,
                node_type=node_type,
                note_id=note_id,
                note_datetime=note_datetime,
            )

            if node_id:
                entity_node_map[id(entity)] = node_id
                nodes_created += 1

                # Create edge from patient to entity
                edge_type = self.CATEGORY_TO_EDGE_TYPE.get(entity.category)
                if edge_type:
                    self._create_patient_entity_edge(
                        patient_id=patient_id,
                        patient_node_id=patient_node_id,
                        entity_node_id=node_id,
                        edge_type=edge_type,
                        note_id=note_id,
                        note_datetime=note_datetime,
                    )

        # Step 4: Convert relationships to edges
        edges_created = 0
        for relationship in mapping_result.relationships:
            edge_created = self._create_relationship_edge(
                relationship=relationship,
                entity_node_map=entity_node_map,
                patient_id=patient_id,
                note_id=note_id,
            )
            if edge_created:
                edges_created += 1

        # Commit changes
        self._session.commit()

        processing_time = (time.perf_counter() - start_time) * 1000

        return NoteIngestionResult(
            note_id=note_id,
            patient_id=patient_id,
            nodes_created=nodes_created,
            edges_created=edges_created,
            entities_mapped=len(mapping_result.entities),
            relationships_mapped=len(mapping_result.relationships),
            processing_time_ms=round(processing_time, 2),
            coverage_stats=mapping_result.coverage_stats,
        )

    def _create_entity_node(
        self,
        entity: ClassifiedToken,
        patient_id: str,
        node_type: NodeType,
        note_id: str,
        note_datetime: datetime,
    ) -> UUID | None:
        """Create a node for a clinical entity.

        Performs entity resolution to avoid duplicates. Concept nodes are
        created with patient_id=None (shared across patients) and only
        carry concept-level properties. Patient-specific metadata belongs
        on the edges.
        """
        # Generate cache key for entity resolution
        # Concept nodes use __shared__ prefix since they are cross-patient
        normalized_name = entity.span.normalized.lower().strip()
        omop_concept_id = self._get_omop_concept_id(entity)
        is_concept = omop_concept_id is not None
        if is_concept:
            cache_key = f"__shared__:{node_type.value}:{normalized_name}"
        else:
            cache_key = f"{patient_id}:{node_type.value}:{normalized_name}"

        # Check cache
        if cache_key in self._entity_cache:
            return self._entity_cache[cache_key]

        # Create node via graph builder - concept nodes get patient_id=None
        node_input = NodeInput(
            patient_id=None if is_concept else patient_id,
            node_type=node_type,
            label=entity.span.text,
            omop_concept_id=omop_concept_id,
            properties={
                "normalized_name": normalized_name,
                "category": entity.category.value,
                "subcategory": entity.subcategory,
                "vocabulary_code": entity.vocabulary_code,
                "vocabulary_system": entity.vocabulary_system,
            },
        )

        node_id = self._graph_builder.create_node(node_input)
        self._entity_cache[cache_key] = node_id
        return node_id

    def _get_omop_concept_id(self, entity: ClassifiedToken) -> int | None:
        """Derive an OMOP-compatible concept ID from the entity's vocabulary code.

        Returns an integer concept ID when the entity carries a numeric
        vocabulary code (e.g. SNOMED-CT, LOINC, RxNorm).  This enables the
        node to be created as a shared concept (patient_id=NULL) and
        deduplicated across patients.

        Returns None when no usable vocabulary code is present, causing the
        node to remain patient-scoped.
        """
        if not entity.vocabulary_code:
            return None
        try:
            return int(entity.vocabulary_code)
        except (TypeError, ValueError):
            return None

    def _create_patient_entity_edge(
        self,
        patient_id: str,
        patient_node_id: UUID,
        entity_node_id: UUID,
        edge_type: EdgeType,
        note_id: str,
        note_datetime: datetime,
    ) -> UUID:
        """Create an edge from patient to entity."""
        edge_input = EdgeInput(
            patient_id=patient_id,
            source_node_id=patient_node_id,
            target_node_id=entity_node_id,
            edge_type=edge_type,
            properties={
                "note_id": note_id,
                "note_datetime": note_datetime.isoformat(),
            },
        )
        return self._graph_builder.create_edge(edge_input)

    def _create_relationship_edge(
        self,
        relationship: Relationship,
        entity_node_map: dict[int, UUID],
        patient_id: str,
        note_id: str,
    ) -> bool:
        """Create an edge for a relationship between entities."""
        source_node_id = entity_node_map.get(id(relationship.subject))
        target_node_id = entity_node_map.get(id(relationship.object))

        if not source_node_id or not target_node_id:
            return False

        # Map relationship type to edge type
        edge_type = self.RELATION_TO_EDGE_TYPE.get(relationship.relation)
        if not edge_type:
            # Default to observation for unmapped relationships
            return False

        edge_input = EdgeInput(
            patient_id=patient_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            edge_type=edge_type,
            properties={
                "relationship_type": relationship.relation.value,
                "confidence": relationship.confidence,
                "note_id": note_id,
                "context": relationship.context,
            },
        )

        self._graph_builder.create_edge(edge_input)
        return True

    def get_patient_graph(self, patient_id: str) -> dict[str, Any]:
        """Get the complete knowledge graph for a patient.

        Returns the graph from the existing graph builder.
        """
        nodes = self._graph_builder.get_nodes_for_patient(patient_id)
        edges = self._graph_builder.get_edges_for_patient(patient_id)

        return {
            "patient_id": patient_id,
            "nodes": [
                {
                    "node_type": n.node_type.value,
                    "label": n.label,
                    "properties": n.properties,
                }
                for n in nodes
            ],
            "edges": [
                {
                    "edge_type": e.edge_type.value,
                    "properties": e.properties,
                }
                for e in edges
            ],
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    def batch_ingest_notes(
        self,
        notes: list[dict[str, Any]],
        patient_id: str,
    ) -> list[NoteIngestionResult]:
        """Ingest multiple notes for a patient.

        Args:
            notes: List of dicts with 'text', 'note_id', 'datetime' keys.
            patient_id: Patient identifier.

        Returns:
            List of NoteIngestionResult for each note.
        """
        results = []
        for note in notes:
            result = self.ingest_note(
                note_text=note["text"],
                patient_id=patient_id,
                note_id=note.get("note_id"),
                note_datetime=note.get("datetime"),
            )
            results.append(result)

        return results


def get_ontology_graph_integration(session: Session) -> OntologyGraphIntegration:
    """Factory function to create an OntologyGraphIntegration instance."""
    return OntologyGraphIntegration(session)
