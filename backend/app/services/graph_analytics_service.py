"""Graph Analytics Service.

Provides graph-based analytics for the clinical ontology knowledge graph.

Features:
- Patient similarity (shared conditions, medications, procedures)
- Concept path finding (shortest path between concepts)
- Subgraph extraction for visualization
- Drug-disease relationship traversal
- Community detection for patient clusters
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import Lock
from typing import Any

from app.services.graph_database_service import (
    get_graph_database_service,
    GraphDatabaseService,
)

logger = logging.getLogger(__name__)


class SimilarityMetric(str, Enum):
    """Metrics for measuring similarity."""

    JACCARD = "jaccard"
    COSINE = "cosine"
    OVERLAP = "overlap"
    DICE = "dice"


class NodeCategory(str, Enum):
    """Categories of nodes for filtering."""

    CONDITION = "Condition"
    DRUG = "Drug"
    PROCEDURE = "Procedure"
    MEASUREMENT = "Measurement"
    OBSERVATION = "Observation"
    GENE = "Gene"
    PATHWAY = "Pathway"
    ALL = "All"


@dataclass
class ConceptNode:
    """A concept node in the graph."""

    concept_id: int
    concept_name: str
    vocabulary_id: str
    domain_id: str
    concept_class_id: str | None = None
    synonyms: list[str] = field(default_factory=list)


@dataclass
class GraphEdge:
    """An edge/relationship in the graph."""

    source_id: int
    target_id: int
    relationship_type: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConceptPath:
    """A path between two concepts."""

    start_concept: ConceptNode
    end_concept: ConceptNode
    path_nodes: list[ConceptNode]
    path_relationships: list[str]
    path_length: int
    total_paths_found: int = 1


@dataclass
class SimilarPatient:
    """A patient similar to a reference patient."""

    patient_id: str
    similarity_score: float
    shared_conditions: list[str]
    shared_medications: list[str]
    shared_procedures: list[str]
    shared_measurements: list[str]
    total_shared_features: int


@dataclass
class PatientSubgraph:
    """A subgraph representing a patient's clinical knowledge."""

    patient_id: str
    nodes: list[ConceptNode]
    edges: list[GraphEdge]
    node_count: int
    edge_count: int
    conditions_count: int
    drugs_count: int
    procedures_count: int
    measurements_count: int


@dataclass
class ConceptCluster:
    """A cluster of related concepts."""

    cluster_id: str
    cluster_name: str
    concepts: list[ConceptNode]
    size: int
    centroid_concept_id: int | None = None
    domain: str | None = None


@dataclass
class DrugDiseaseRelationship:
    """Relationship between a drug and disease."""

    drug: ConceptNode
    disease: ConceptNode
    relationship_type: str
    evidence_count: int = 0
    strength: float = 0.0
    mechanism: str | None = None
    references: list[str] = field(default_factory=list)


# Singleton instance
_graph_analytics_service: "GraphAnalyticsService | None" = None
_service_lock = Lock()


class GraphAnalyticsService:
    """Service for graph-based analytics on clinical data.

    Provides methods for:
    - Finding similar patients
    - Concept path finding
    - Subgraph extraction
    - Drug-disease traversal
    - Community detection
    """

    def __init__(
        self,
        graph_service: GraphDatabaseService | None = None,
    ) -> None:
        """Initialize the analytics service.

        Args:
            graph_service: Graph database service. If None, uses singleton.
        """
        self._graph = graph_service or get_graph_database_service()
        self._lock = Lock()

        # Cache for frequently accessed data
        self._concept_cache: dict[int, ConceptNode] = {}
        self._cache_hits = 0
        self._cache_misses = 0

    def get_concept_neighbors(
        self,
        concept_id: int,
        max_depth: int = 1,
        categories: list[NodeCategory] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get neighboring concepts for a given concept.

        Args:
            concept_id: The concept ID to find neighbors for.
            max_depth: Maximum relationship depth (1-3).
            categories: Optional list of categories to filter by.
            limit: Maximum number of neighbors to return.

        Returns:
            List of neighboring concepts with relationship info.
        """
        # Build category filter
        category_filter = ""
        if categories and NodeCategory.ALL not in categories:
            domains = [c.value for c in categories]
            category_filter = f"AND n.domain_id IN {domains}"

        query = f"""
        MATCH (c:Concept {{concept_id: $concept_id}})-[r]-(n:Concept)
        WHERE n.concept_id <> c.concept_id {category_filter}
        RETURN n AS neighbor, type(r) AS relationship,
               CASE WHEN startNode(r) = c THEN 'outgoing' ELSE 'incoming' END AS direction
        LIMIT $limit
        """

        result = self._graph.execute_read(query, {
            "concept_id": concept_id,
            "limit": limit,
        })

        neighbors = []
        for record in result.records:
            neighbor = record.get("neighbor", {})
            neighbors.append({
                "concept": {
                    "concept_id": neighbor.get("concept_id"),
                    "concept_name": neighbor.get("name"),
                    "vocabulary_id": neighbor.get("vocabulary_id"),
                    "domain_id": neighbor.get("domain_id"),
                },
                "relationship": record.get("relationship"),
                "direction": record.get("direction"),
            })

        return neighbors

    def get_concept_ancestors(
        self,
        concept_id: int,
        max_levels: int = 5,
    ) -> list[dict[str, Any]]:
        """Get ancestors of a concept in the hierarchy.

        Args:
            concept_id: The concept ID to find ancestors for.
            max_levels: Maximum levels to traverse up.

        Returns:
            List of ancestor concepts with distance.
        """
        query = """
        MATCH path = (c:Concept {concept_id: $concept_id})-[:IS_A*1..5]->(ancestor:Concept)
        WITH ancestor, length(path) AS distance
        RETURN ancestor, distance
        ORDER BY distance
        """

        result = self._graph.execute_read(query, {
            "concept_id": concept_id,
            "max_levels": max_levels,
        })

        ancestors = []
        for record in result.records:
            anc = record.get("ancestor", {})
            ancestors.append({
                "ancestor": {
                    "concept_id": anc.get("concept_id"),
                    "concept_name": anc.get("name"),
                    "vocabulary_id": anc.get("vocabulary_id"),
                    "domain_id": anc.get("domain_id"),
                },
                "distance": record.get("distance", 1),
            })

        return ancestors

    def get_concept_descendants(
        self,
        concept_id: int,
        max_levels: int = 3,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get descendants of a concept in the hierarchy.

        Args:
            concept_id: The concept ID to find descendants for.
            max_levels: Maximum levels to traverse down.
            limit: Maximum number of descendants.

        Returns:
            List of descendant concepts with distance.
        """
        query = """
        MATCH path = (c:Concept {concept_id: $concept_id})<-[:IS_A*1..3]-(descendant:Concept)
        WITH descendant, length(path) AS distance
        RETURN descendant, distance
        ORDER BY distance
        LIMIT $limit
        """

        result = self._graph.execute_read(query, {
            "concept_id": concept_id,
            "max_levels": max_levels,
            "limit": limit,
        })

        descendants = []
        for record in result.records:
            desc = record.get("descendant", {})
            descendants.append({
                "descendant": {
                    "concept_id": desc.get("concept_id"),
                    "concept_name": desc.get("name"),
                    "vocabulary_id": desc.get("vocabulary_id"),
                    "domain_id": desc.get("domain_id"),
                },
                "distance": record.get("distance", 1),
            })

        return descendants

    def find_concept_path(
        self,
        start_concept_id: int,
        end_concept_id: int,
        max_length: int = 5,
    ) -> ConceptPath | None:
        """Find the shortest path between two concepts.

        Args:
            start_concept_id: Starting concept ID.
            end_concept_id: Ending concept ID.
            max_length: Maximum path length to search.

        Returns:
            ConceptPath or None if no path found.
        """
        query = """
        MATCH (start:Concept {concept_id: $start_id}),
              (end:Concept {concept_id: $end_id}),
              path = shortestPath((start)-[*..5]-(end))
        WITH path, nodes(path) AS path_nodes, relationships(path) AS rels
        RETURN path_nodes, [r IN rels | type(r)] AS relationships,
               length(path) AS path_length
        LIMIT 1
        """

        result = self._graph.execute_read(query, {
            "start_id": start_concept_id,
            "end_id": end_concept_id,
            "max_length": max_length,
        })

        if not result.records:
            return None

        record = result.records[0]
        path_nodes = record.get("path_nodes", [])
        relationships = record.get("relationships", [])
        path_length = record.get("path_length", 0)

        # Convert nodes
        concepts = []
        for node in path_nodes:
            concepts.append(ConceptNode(
                concept_id=node.get("concept_id", 0),
                concept_name=node.get("name", ""),
                vocabulary_id=node.get("vocabulary_id", ""),
                domain_id=node.get("domain_id", ""),
            ))

        if len(concepts) < 2:
            return None

        return ConceptPath(
            start_concept=concepts[0],
            end_concept=concepts[-1],
            path_nodes=concepts,
            path_relationships=relationships,
            path_length=path_length,
        )

    def find_similar_patients(
        self,
        patient_id: str,
        metric: SimilarityMetric = SimilarityMetric.JACCARD,
        min_similarity: float = 0.5,
        limit: int = 10,
    ) -> list[SimilarPatient]:
        """Find patients similar to a given patient.

        Uses shared clinical features (conditions, medications, procedures)
        to calculate similarity.

        Args:
            patient_id: Reference patient ID.
            metric: Similarity metric to use.
            min_similarity: Minimum similarity threshold (0-1).
            limit: Maximum number of similar patients.

        Returns:
            List of SimilarPatient ordered by similarity.
        """
        query = """
        MATCH (p1:Patient {patient_id: $patient_id})-[:HAS_CONDITION]->(c:Concept)
        WITH p1, collect(c.name) AS p1_conditions

        MATCH (p1)-[:HAS_DRUG]->(d:Concept)
        WITH p1, p1_conditions, collect(d.name) AS p1_drugs

        MATCH (p1)-[:HAS_PROCEDURE]->(proc:Concept)
        WITH p1, p1_conditions, p1_drugs, collect(proc.name) AS p1_procedures

        MATCH (p2:Patient)-[:HAS_CONDITION]->(c2:Concept)
        WHERE p2 <> p1
        WITH p1, p1_conditions, p1_drugs, p1_procedures,
             p2, collect(c2.name) AS p2_conditions

        MATCH (p2)-[:HAS_DRUG]->(d2:Concept)
        WITH p1, p1_conditions, p1_drugs, p1_procedures,
             p2, p2_conditions, collect(d2.name) AS p2_drugs

        MATCH (p2)-[:HAS_PROCEDURE]->(proc2:Concept)
        WITH p1, p1_conditions, p1_drugs, p1_procedures,
             p2, p2_conditions, p2_drugs, collect(proc2.name) AS p2_procedures

        WITH p2,
             [x IN p1_conditions WHERE x IN p2_conditions] AS shared_conditions,
             [x IN p1_drugs WHERE x IN p2_drugs] AS shared_drugs,
             [x IN p1_procedures WHERE x IN p2_procedures] AS shared_procedures,
             size(p1_conditions) + size(p1_drugs) + size(p1_procedures) AS p1_total,
             size(p2_conditions) + size(p2_drugs) + size(p2_procedures) AS p2_total

        WITH p2, shared_conditions, shared_drugs, shared_procedures,
             size(shared_conditions) + size(shared_drugs) + size(shared_procedures) AS shared_total,
             p1_total, p2_total

        WITH p2, shared_conditions, shared_drugs, shared_procedures, shared_total,
             toFloat(shared_total) / (p1_total + p2_total - shared_total) AS jaccard_similarity

        WHERE jaccard_similarity >= $min_similarity
        RETURN p2.patient_id AS patient_id,
               jaccard_similarity AS similarity,
               shared_conditions, shared_drugs, shared_procedures
        ORDER BY similarity DESC
        LIMIT $limit
        """

        result = self._graph.execute_read(query, {
            "patient_id": patient_id,
            "min_similarity": min_similarity,
            "limit": limit,
        })

        similar_patients = []
        for record in result.records:
            shared_conditions = record.get("shared_conditions", [])
            shared_drugs = record.get("shared_drugs", [])
            shared_procedures = record.get("shared_procedures", [])

            similar_patients.append(SimilarPatient(
                patient_id=record.get("patient_id", ""),
                similarity_score=record.get("similarity", 0.0),
                shared_conditions=shared_conditions,
                shared_medications=shared_drugs,
                shared_procedures=shared_procedures,
                shared_measurements=[],  # Would need separate query
                total_shared_features=len(shared_conditions) + len(shared_drugs) + len(shared_procedures),
            ))

        return similar_patients

    def get_patient_subgraph(
        self,
        patient_id: str,
        include_categories: list[NodeCategory] | None = None,
        max_relationships: int = 100,
    ) -> PatientSubgraph:
        """Extract a subgraph representing a patient's clinical knowledge.

        Args:
            patient_id: Patient ID.
            include_categories: Categories to include (all if None).
            max_relationships: Maximum relationships to include.

        Returns:
            PatientSubgraph with nodes and edges.
        """
        query = """
        MATCH (p:Patient {patient_id: $patient_id})-[r]->(c:Concept)
        WITH p, r, c
        LIMIT $max_rels

        WITH collect({
            source: p.patient_id,
            target: c.concept_id,
            type: type(r),
            concept: c
        }) AS direct_rels

        UNWIND direct_rels AS dr
        WITH dr.concept AS c, dr, direct_rels

        OPTIONAL MATCH (c)-[r2]-(related:Concept)
        WITH dr, c, collect({
            source: c.concept_id,
            target: related.concept_id,
            type: type(r2),
            concept: related
        })[0..10] AS concept_rels, direct_rels

        RETURN direct_rels, collect(concept_rels) AS extended_rels
        """

        result = self._graph.execute_read(query, {
            "patient_id": patient_id,
            "max_rels": max_relationships,
        })

        # Process results
        nodes: dict[int, ConceptNode] = {}
        edges: list[GraphEdge] = []

        # Track counts by category
        counts = {"Condition": 0, "Drug": 0, "Procedure": 0, "Measurement": 0}

        for record in result.records:
            direct_rels = record.get("direct_rels", [])

            for rel in direct_rels:
                concept = rel.get("concept", {})
                concept_id = concept.get("concept_id")

                if concept_id and concept_id not in nodes:
                    domain = concept.get("domain_id", "")
                    nodes[concept_id] = ConceptNode(
                        concept_id=concept_id,
                        concept_name=concept.get("name", ""),
                        vocabulary_id=concept.get("vocabulary_id", ""),
                        domain_id=domain,
                    )

                    if domain in counts:
                        counts[domain] += 1

                edges.append(GraphEdge(
                    source_id=0,  # Patient
                    target_id=concept_id or 0,
                    relationship_type=rel.get("type", "RELATED"),
                ))

        return PatientSubgraph(
            patient_id=patient_id,
            nodes=list(nodes.values()),
            edges=edges,
            node_count=len(nodes),
            edge_count=len(edges),
            conditions_count=counts["Condition"],
            drugs_count=counts["Drug"],
            procedures_count=counts["Procedure"],
            measurements_count=counts["Measurement"],
        )

    def traverse_drug_disease_relationships(
        self,
        concept_id: int,
        relationship_types: list[str] | None = None,
        max_depth: int = 2,
    ) -> list[DrugDiseaseRelationship]:
        """Traverse drug-disease relationships in the graph.

        Args:
            concept_id: Starting concept (drug or disease).
            relationship_types: Types of relationships to traverse.
            max_depth: Maximum traversal depth.

        Returns:
            List of drug-disease relationships.
        """
        rel_filter = ""
        if relationship_types:
            rel_types = "|".join(relationship_types)
            rel_filter = f":{rel_types}"

        query = f"""
        MATCH (start:Concept {{concept_id: $concept_id}})
        MATCH path = (start)-[r{rel_filter}*1..{max_depth}]-(end:Concept)
        WHERE (start.domain_id = 'Drug' AND end.domain_id = 'Condition')
           OR (start.domain_id = 'Condition' AND end.domain_id = 'Drug')
        WITH start, end, [rel IN relationships(path) | type(rel)] AS rel_types,
             length(path) AS distance
        RETURN start, end, rel_types, distance
        ORDER BY distance
        LIMIT 50
        """

        result = self._graph.execute_read(query, {
            "concept_id": concept_id,
        })

        relationships = []
        for record in result.records:
            start = record.get("start", {})
            end = record.get("end", {})
            rel_types = record.get("rel_types", [])

            # Determine drug and disease
            if start.get("domain_id") == "Drug":
                drug_node = start
                disease_node = end
            else:
                drug_node = end
                disease_node = start

            relationships.append(DrugDiseaseRelationship(
                drug=ConceptNode(
                    concept_id=drug_node.get("concept_id", 0),
                    concept_name=drug_node.get("name", ""),
                    vocabulary_id=drug_node.get("vocabulary_id", ""),
                    domain_id="Drug",
                ),
                disease=ConceptNode(
                    concept_id=disease_node.get("concept_id", 0),
                    concept_name=disease_node.get("name", ""),
                    vocabulary_id=disease_node.get("vocabulary_id", ""),
                    domain_id="Condition",
                ),
                relationship_type=" -> ".join(rel_types) if rel_types else "RELATED",
            ))

        return relationships

    def detect_patient_communities(
        self,
        min_community_size: int = 3,
        max_communities: int = 10,
    ) -> list[ConceptCluster]:
        """Detect communities/clusters of similar patients.

        Uses graph algorithms to identify groups of patients with
        similar clinical profiles.

        Args:
            min_community_size: Minimum patients in a community.
            max_communities: Maximum communities to return.

        Returns:
            List of ConceptCluster representing patient groups.
        """
        # This would typically use Neo4j GDS (Graph Data Science) library
        # For now, we use a simpler approach based on shared conditions
        query = """
        MATCH (p:Patient)-[:HAS_CONDITION]->(c:Concept)
        WITH c, collect(p.patient_id) AS patients, count(p) AS patient_count
        WHERE patient_count >= $min_size
        RETURN c.concept_id AS centroid_id,
               c.name AS cluster_name,
               patients,
               patient_count
        ORDER BY patient_count DESC
        LIMIT $max_communities
        """

        result = self._graph.execute_read(query, {
            "min_size": min_community_size,
            "max_communities": max_communities,
        })

        communities = []
        for i, record in enumerate(result.records):
            patients = record.get("patients", [])

            # Create pseudo-concept nodes for patients
            patient_nodes = [
                ConceptNode(
                    concept_id=hash(pid) % 1000000,  # Generate pseudo ID
                    concept_name=f"Patient {pid}",
                    vocabulary_id="Patient",
                    domain_id="Patient",
                )
                for pid in patients[:20]  # Limit displayed patients
            ]

            communities.append(ConceptCluster(
                cluster_id=f"community_{i+1}",
                cluster_name=record.get("cluster_name", f"Community {i+1}"),
                concepts=patient_nodes,
                size=record.get("patient_count", 0),
                centroid_concept_id=record.get("centroid_id"),
                domain="Patient",
            ))

        return communities

    def search_concepts(
        self,
        query: str,
        categories: list[NodeCategory] | None = None,
        limit: int = 20,
    ) -> list[ConceptNode]:
        """Search for concepts by name.

        Args:
            query: Search query string.
            categories: Categories to filter by.
            limit: Maximum results.

        Returns:
            List of matching concepts.
        """
        # Try full-text search first, fallback to CONTAINS
        category_filter = ""
        if categories and NodeCategory.ALL not in categories:
            domains = [c.value for c in categories]
            category_filter = f"AND c.domain_id IN {domains}"

        cypher = f"""
        MATCH (c:Concept)
        WHERE toLower(c.name) CONTAINS toLower($query) {category_filter}
        RETURN c
        ORDER BY
            CASE WHEN toLower(c.name) = toLower($query) THEN 0 ELSE 1 END,
            c.name
        LIMIT $limit
        """

        result = self._graph.execute_read(cypher, {
            "query": query,
            "limit": limit,
        })

        concepts = []
        for record in result.records:
            c = record.get("c", {})
            concepts.append(ConceptNode(
                concept_id=c.get("concept_id", 0),
                concept_name=c.get("name", ""),
                vocabulary_id=c.get("vocabulary_id", ""),
                domain_id=c.get("domain_id", ""),
                concept_class_id=c.get("concept_class_id"),
                synonyms=c.get("synonyms", []),
            ))

        return concepts

    def get_graph_statistics(self) -> dict[str, Any]:
        """Get overall statistics about the knowledge graph.

        Returns:
            Dictionary with graph statistics.
        """
        queries = {
            "total_concepts": "MATCH (c:Concept) RETURN count(c) AS count",
            "total_patients": "MATCH (p:Patient) RETURN count(p) AS count",
            "total_relationships": "MATCH ()-[r]->() RETURN count(r) AS count",
            "concepts_by_domain": """
                MATCH (c:Concept)
                RETURN c.domain_id AS domain, count(c) AS count
                ORDER BY count DESC
            """,
            "relationship_types": """
                MATCH ()-[r]->()
                RETURN type(r) AS type, count(r) AS count
                ORDER BY count DESC
                LIMIT 10
            """,
        }

        stats: dict[str, Any] = {
            "graph_connected": self._graph.is_connected,
            "mock_mode": self._graph.is_mock_mode,
        }

        for key, query in queries.items():
            try:
                result = self._graph.execute_read(query)
                if "by_domain" in key or "types" in key:
                    stats[key] = {
                        r.get("domain") or r.get("type"): r.get("count")
                        for r in result.records
                    }
                else:
                    stats[key] = result.records[0].get("count", 0) if result.records else 0
            except Exception as e:
                stats[key] = f"Error: {e}"

        return stats

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics.

        Returns:
            Dictionary with service stats.
        """
        return {
            "graph_connected": self._graph.is_connected,
            "mock_mode": self._graph.is_mock_mode,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_size": len(self._concept_cache),
        }


def get_graph_analytics_service() -> GraphAnalyticsService:
    """Get the singleton GraphAnalyticsService instance.

    Returns:
        The GraphAnalyticsService singleton.
    """
    global _graph_analytics_service

    if _graph_analytics_service is None:
        with _service_lock:
            if _graph_analytics_service is None:
                _graph_analytics_service = GraphAnalyticsService()

    return _graph_analytics_service


def reset_graph_analytics_service() -> None:
    """Reset the singleton for testing."""
    global _graph_analytics_service

    with _service_lock:
        _graph_analytics_service = None
