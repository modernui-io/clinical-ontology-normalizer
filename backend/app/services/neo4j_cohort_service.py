"""Neo4j Cohort Service for cross-patient phenotype queries.

Leverages shared concept nodes in Neo4j as natural join points
for cross-patient analysis:
- Patient similarity via Jaccard index on shared concepts
- Phenotype co-occurrence analysis

These queries exploit Neo4j's genuine advantage: set intersection
via shared concept nodes across the full patient population.
"""
# MODULE: graph_rag
# MATURITY: pilot

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.services.graph_database_service import GraphDatabaseService, get_graph_database_service

logger = logging.getLogger(__name__)


@dataclass
class SimilarPatient:
    """A patient similar to the query patient."""

    patient_id: str
    jaccard_similarity: float
    shared_concept_count: int
    shared_concepts: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ConceptCoOccurrence:
    """A concept that co-occurs with the query concept."""

    omop_concept_id: int
    concept_name: str
    node_type: str
    co_occurrence_count: int
    patient_count: int


class Neo4jCohortService:
    """Service for cross-patient cohort analysis via Neo4j.

    Uses shared concept nodes as natural join points for
    computing patient similarity and phenotype co-occurrence.

    Usage:
        service = Neo4jCohortService()
        similar = service.find_similar_patients("P001", min_similarity=0.3)
        co_occurring = service.phenotype_co_occurrence(201826, limit=20)
    """

    def __init__(self, graph_db: GraphDatabaseService | None = None) -> None:
        self._graph_db = graph_db or get_graph_database_service()

    @property
    def is_available(self) -> bool:
        return self._graph_db.is_connected

    def find_similar_patients(
        self,
        patient_id: str,
        min_similarity: float = 0.3,
        limit: int = 10,
    ) -> list[SimilarPatient]:
        """Find patients similar to the given patient via Jaccard similarity.

        Uses shared concept nodes as the intersection set.

        Args:
            patient_id: Query patient identifier.
            min_similarity: Minimum Jaccard similarity threshold.
            limit: Maximum number of similar patients.

        Returns:
            List of SimilarPatient ordered by similarity descending.
        """
        if not self.is_available:
            logger.warning("Neo4j not available for similarity query")
            return []

        cypher = """
        MATCH (p1:Patient {patient_id: $patient_id})-[]->(c:ClinicalFact)
        WITH p1, collect(DISTINCT c.omop_concept_id) AS p1_concepts
        MATCH (p2:Patient)-[]->(c2:ClinicalFact)
        WHERE p2.patient_id <> $patient_id
          AND c2.omop_concept_id IN p1_concepts
        WITH p2, p1_concepts,
             collect(DISTINCT c2.omop_concept_id) AS shared_ids,
             count(DISTINCT c2.omop_concept_id) AS shared_count
        MATCH (p2)-[]->(c3:ClinicalFact)
        WITH p2.patient_id AS similar_id, shared_ids, shared_count,
             p1_concepts,
             count(DISTINCT c3.omop_concept_id) AS p2_total,
             collect(DISTINCT {
               omop_concept_id: c3.omop_concept_id,
               label: c3.label,
               node_type: c3.node_type
             }) AS p2_concepts
        WITH similar_id, shared_ids, shared_count, p2_total, p2_concepts,
             toFloat(shared_count) /
               (size(p1_concepts) + p2_total - shared_count) AS jaccard
        WHERE jaccard >= $min_similarity
        RETURN similar_id, jaccard, shared_count, shared_ids
        ORDER BY jaccard DESC
        LIMIT $limit
        """

        try:
            result = self._graph_db.execute_read(
                cypher,
                {
                    "patient_id": patient_id,
                    "min_similarity": min_similarity,
                    "limit": limit,
                },
            )

            patients = []
            for record in result.records:
                patients.append(SimilarPatient(
                    patient_id=record["similar_id"],
                    jaccard_similarity=record["jaccard"],
                    shared_concept_count=record["shared_count"],
                ))
            return patients

        except Exception as e:
            logger.error("Failed to find similar patients: %s", e)
            return []

    def phenotype_co_occurrence(
        self,
        omop_concept_id: int,
        limit: int = 20,
    ) -> list[ConceptCoOccurrence]:
        """Find concepts that most frequently co-occur with the given concept.

        Queries across all patients who have the given concept to find
        what other concepts appear in those patients' graphs.

        Args:
            omop_concept_id: OMOP concept ID to analyze.
            limit: Maximum co-occurring concepts to return.

        Returns:
            List of ConceptCoOccurrence ordered by co-occurrence count.
        """
        if not self.is_available:
            logger.warning("Neo4j not available for co-occurrence query")
            return []

        cypher = """
        MATCH (target:ClinicalFact {omop_concept_id: $concept_id})
        MATCH (p:Patient)-[]->(target)
        WITH collect(DISTINCT p) AS patients
        UNWIND patients AS p
        MATCH (p)-[]->(c:ClinicalFact)
        WHERE c.omop_concept_id <> $concept_id
          AND c.omop_concept_id IS NOT NULL
        WITH c.omop_concept_id AS co_concept_id,
             c.label AS concept_name,
             c.node_type AS node_type,
             count(DISTINCT p) AS patient_count
        RETURN co_concept_id, concept_name, node_type, patient_count
        ORDER BY patient_count DESC
        LIMIT $limit
        """

        try:
            result = self._graph_db.execute_read(
                cypher,
                {"concept_id": omop_concept_id, "limit": limit},
            )

            co_occurrences = []
            for record in result.records:
                co_occurrences.append(ConceptCoOccurrence(
                    omop_concept_id=record["co_concept_id"],
                    concept_name=record["concept_name"],
                    node_type=record["node_type"],
                    co_occurrence_count=record["patient_count"],
                    patient_count=record["patient_count"],
                ))
            return co_occurrences

        except Exception as e:
            logger.error("Failed to get phenotype co-occurrence: %s", e)
            return []
