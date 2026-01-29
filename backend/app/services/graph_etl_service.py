"""Graph ETL Service for OMOP Concepts.

Provides ETL functionality for loading OMOP CDM concepts into the
Neo4j knowledge graph database.

Features:
- Load concepts as nodes (Concept ID, name, vocabulary, domain)
- Load concept_ancestor relationships
- Load concept_relationship edges
- Load concept_synonym as node properties
- Incremental update support
- Batch processing for large datasets
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


class ETLStatus(str, Enum):
    """Status of an ETL operation."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeType(str, Enum):
    """Types of nodes in the knowledge graph."""

    CONCEPT = "Concept"
    PATIENT = "Patient"
    CONDITION = "Condition"
    DRUG = "Drug"
    PROCEDURE = "Procedure"
    MEASUREMENT = "Measurement"
    OBSERVATION = "Observation"
    GENE = "Gene"
    PATHWAY = "Pathway"


class RelationshipType(str, Enum):
    """Types of relationships in the knowledge graph."""

    IS_A = "IS_A"
    HAS_ANCESTOR = "HAS_ANCESTOR"
    HAS_DESCENDANT = "HAS_DESCENDANT"
    MAPS_TO = "MAPS_TO"
    HAS_FINDING = "HAS_FINDING"
    HAS_COMPONENT = "HAS_COMPONENT"
    TREATED_BY = "TREATED_BY"
    CAUSES = "CAUSES"
    MAY_TREAT = "MAY_TREAT"
    MAY_PREVENT = "MAY_PREVENT"
    CONTRAINDICATED_WITH = "CONTRAINDICATED_WITH"
    INTERACTS_WITH = "INTERACTS_WITH"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    HAS_CONDITION = "HAS_CONDITION"
    HAS_DRUG = "HAS_DRUG"
    HAS_PROCEDURE = "HAS_PROCEDURE"
    SIMILAR_TO = "SIMILAR_TO"
    REGULATES = "REGULATES"
    INVOLVED_IN = "INVOLVED_IN"


@dataclass
class ConceptNode:
    """A concept node to load into the graph."""

    concept_id: int
    concept_name: str
    vocabulary_id: str
    domain_id: str
    concept_class_id: str
    standard_concept: str | None = None
    concept_code: str | None = None
    valid_start_date: str | None = None
    valid_end_date: str | None = None
    synonyms: list[str] = field(default_factory=list)


@dataclass
class ConceptRelationship:
    """A relationship between concepts."""

    concept_id_1: int
    concept_id_2: int
    relationship_id: str
    relationship_type: RelationshipType
    min_levels_of_separation: int = 0
    max_levels_of_separation: int = 0


@dataclass
class ETLJobResult:
    """Result of an ETL job."""

    job_id: str
    status: ETLStatus
    started_at: str
    completed_at: str | None = None
    nodes_created: int = 0
    nodes_updated: int = 0
    relationships_created: int = 0
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0


@dataclass
class ETLProgress:
    """Progress of an ETL operation."""

    total: int
    processed: int
    percent_complete: float
    current_batch: int
    total_batches: int
    estimated_remaining_ms: float | None = None


# Singleton instance
_graph_etl_service: "GraphETLService | None" = None
_service_lock = Lock()


class GraphETLService:
    """Service for loading OMOP concepts into Neo4j.

    Provides methods for:
    - Loading concepts as nodes
    - Loading concept hierarchies (ancestors)
    - Loading concept relationships
    - Incremental updates
    - Batch processing
    """

    def __init__(
        self,
        graph_service: GraphDatabaseService | None = None,
        batch_size: int = 1000,
    ) -> None:
        """Initialize the ETL service.

        Args:
            graph_service: Graph database service. If None, uses singleton.
            batch_size: Number of records to process per batch.
        """
        self._graph = graph_service or get_graph_database_service()
        self._batch_size = batch_size
        self._lock = Lock()
        self._current_job: ETLJobResult | None = None
        self._progress: ETLProgress | None = None

        # Statistics
        self._total_concepts_loaded = 0
        self._total_relationships_loaded = 0
        self._last_etl_run: str | None = None

    def create_schema(self) -> dict[str, Any]:
        """Create graph database schema (indexes and constraints).

        Returns:
            Schema creation results.
        """
        schema_queries = [
            # Concept node constraints and indexes
            "CREATE CONSTRAINT concept_id_unique IF NOT EXISTS FOR (c:Concept) REQUIRE c.concept_id IS UNIQUE",
            "CREATE INDEX concept_name_idx IF NOT EXISTS FOR (c:Concept) ON (c.concept_name)",
            "CREATE INDEX concept_vocab_idx IF NOT EXISTS FOR (c:Concept) ON (c.vocabulary_id)",
            "CREATE INDEX concept_domain_idx IF NOT EXISTS FOR (c:Concept) ON (c.domain_id)",

            # Patient node constraints
            "CREATE CONSTRAINT patient_id_unique IF NOT EXISTS FOR (p:Patient) REQUIRE p.patient_id IS UNIQUE",

            # Full-text search index for concept names
            "CREATE FULLTEXT INDEX concept_fulltext IF NOT EXISTS FOR (c:Concept) ON EACH [c.concept_name, c.synonyms]",
        ]

        results = []
        for query in schema_queries:
            try:
                result = self._graph.execute_write(query)
                results.append({"query": query, "success": True})
            except Exception as e:
                results.append({"query": query, "success": False, "error": str(e)})
                logger.warning(f"Schema creation warning: {e}")

        return {
            "total_queries": len(schema_queries),
            "successful": sum(1 for r in results if r["success"]),
            "results": results,
        }

    def load_concepts(
        self,
        concepts: list[ConceptNode],
        job_id: str | None = None,
    ) -> ETLJobResult:
        """Load concepts as nodes into the graph.

        Args:
            concepts: List of concepts to load.
            job_id: Optional job identifier.

        Returns:
            ETLJobResult with load statistics.
        """
        import uuid

        job_id = job_id or str(uuid.uuid4())
        start_time = time.perf_counter()

        job = ETLJobResult(
            job_id=job_id,
            status=ETLStatus.RUNNING,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self._current_job = job

        try:
            total_batches = (len(concepts) + self._batch_size - 1) // self._batch_size

            for batch_num in range(total_batches):
                start_idx = batch_num * self._batch_size
                end_idx = min(start_idx + self._batch_size, len(concepts))
                batch = concepts[start_idx:end_idx]

                self._progress = ETLProgress(
                    total=len(concepts),
                    processed=start_idx,
                    percent_complete=(start_idx / len(concepts)) * 100 if concepts else 0,
                    current_batch=batch_num + 1,
                    total_batches=total_batches,
                )

                # Build batch query
                query = """
                UNWIND $concepts AS concept
                MERGE (c:Concept {concept_id: concept.concept_id})
                SET c.concept_name = concept.concept_name,
                    c.vocabulary_id = concept.vocabulary_id,
                    c.domain_id = concept.domain_id,
                    c.concept_class_id = concept.concept_class_id,
                    c.standard_concept = concept.standard_concept,
                    c.concept_code = concept.concept_code,
                    c.synonyms = concept.synonyms,
                    c.updated_at = datetime()
                RETURN count(c) AS nodes_created
                """

                params = {
                    "concepts": [
                        {
                            "concept_id": c.concept_id,
                            "concept_name": c.concept_name,
                            "vocabulary_id": c.vocabulary_id,
                            "domain_id": c.domain_id,
                            "concept_class_id": c.concept_class_id,
                            "standard_concept": c.standard_concept,
                            "concept_code": c.concept_code,
                            "synonyms": c.synonyms,
                        }
                        for c in batch
                    ]
                }

                result = self._graph.execute_write(query, params)

                if result.records:
                    job.nodes_created += result.records[0].get("nodes_created", 0)

            job.status = ETLStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc).isoformat()
            job.duration_ms = (time.perf_counter() - start_time) * 1000

            with self._lock:
                self._total_concepts_loaded += job.nodes_created
                self._last_etl_run = job.completed_at

        except Exception as e:
            job.status = ETLStatus.FAILED
            job.errors.append(str(e))
            job.completed_at = datetime.now(timezone.utc).isoformat()
            job.duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Concept load failed: {e}")

        self._current_job = None
        self._progress = None
        return job

    def load_concept_ancestors(
        self,
        ancestors: list[dict[str, Any]],
        job_id: str | None = None,
    ) -> ETLJobResult:
        """Load concept ancestor relationships.

        Args:
            ancestors: List of ancestor relationships with keys:
                - ancestor_concept_id
                - descendant_concept_id
                - min_levels_of_separation
                - max_levels_of_separation
            job_id: Optional job identifier.

        Returns:
            ETLJobResult with load statistics.
        """
        import uuid

        job_id = job_id or str(uuid.uuid4())
        start_time = time.perf_counter()

        job = ETLJobResult(
            job_id=job_id,
            status=ETLStatus.RUNNING,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        try:
            total_batches = (len(ancestors) + self._batch_size - 1) // self._batch_size

            for batch_num in range(total_batches):
                start_idx = batch_num * self._batch_size
                end_idx = min(start_idx + self._batch_size, len(ancestors))
                batch = ancestors[start_idx:end_idx]

                query = """
                UNWIND $ancestors AS anc
                MATCH (a:Concept {concept_id: anc.ancestor_concept_id})
                MATCH (d:Concept {concept_id: anc.descendant_concept_id})
                MERGE (d)-[r:IS_A]->(a)
                SET r.min_levels_of_separation = anc.min_levels_of_separation,
                    r.max_levels_of_separation = anc.max_levels_of_separation
                RETURN count(r) AS relationships_created
                """

                result = self._graph.execute_write(query, {"ancestors": batch})

                if result.records:
                    job.relationships_created += result.records[0].get("relationships_created", 0)

            job.status = ETLStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc).isoformat()
            job.duration_ms = (time.perf_counter() - start_time) * 1000

            with self._lock:
                self._total_relationships_loaded += job.relationships_created

        except Exception as e:
            job.status = ETLStatus.FAILED
            job.errors.append(str(e))
            job.completed_at = datetime.now(timezone.utc).isoformat()
            job.duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Ancestor load failed: {e}")

        return job

    def load_concept_relationships(
        self,
        relationships: list[ConceptRelationship],
        job_id: str | None = None,
    ) -> ETLJobResult:
        """Load concept relationships.

        Args:
            relationships: List of relationships to load.
            job_id: Optional job identifier.

        Returns:
            ETLJobResult with load statistics.
        """
        import uuid

        job_id = job_id or str(uuid.uuid4())
        start_time = time.perf_counter()

        job = ETLJobResult(
            job_id=job_id,
            status=ETLStatus.RUNNING,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        try:
            # Group relationships by type for efficient batch loading
            by_type: dict[str, list[ConceptRelationship]] = {}
            for rel in relationships:
                rel_type = rel.relationship_type.value
                if rel_type not in by_type:
                    by_type[rel_type] = []
                by_type[rel_type].append(rel)

            for rel_type, rels in by_type.items():
                total_batches = (len(rels) + self._batch_size - 1) // self._batch_size

                for batch_num in range(total_batches):
                    start_idx = batch_num * self._batch_size
                    end_idx = min(start_idx + self._batch_size, len(rels))
                    batch = rels[start_idx:end_idx]

                    # Dynamic relationship type requires APOC or multiple queries
                    # For simplicity, we use a parameterized approach
                    query = f"""
                    UNWIND $relationships AS rel
                    MATCH (c1:Concept {{concept_id: rel.concept_id_1}})
                    MATCH (c2:Concept {{concept_id: rel.concept_id_2}})
                    MERGE (c1)-[r:{rel_type}]->(c2)
                    SET r.relationship_id = rel.relationship_id,
                        r.min_levels = rel.min_levels_of_separation,
                        r.max_levels = rel.max_levels_of_separation
                    RETURN count(r) AS relationships_created
                    """

                    params = {
                        "relationships": [
                            {
                                "concept_id_1": r.concept_id_1,
                                "concept_id_2": r.concept_id_2,
                                "relationship_id": r.relationship_id,
                                "min_levels_of_separation": r.min_levels_of_separation,
                                "max_levels_of_separation": r.max_levels_of_separation,
                            }
                            for r in batch
                        ]
                    }

                    result = self._graph.execute_write(query, params)

                    if result.records:
                        job.relationships_created += result.records[0].get("relationships_created", 0)

            job.status = ETLStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc).isoformat()
            job.duration_ms = (time.perf_counter() - start_time) * 1000

            with self._lock:
                self._total_relationships_loaded += job.relationships_created

        except Exception as e:
            job.status = ETLStatus.FAILED
            job.errors.append(str(e))
            job.completed_at = datetime.now(timezone.utc).isoformat()
            job.duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Relationship load failed: {e}")

        return job

    def load_sample_data(self) -> ETLJobResult:
        """Load sample OMOP concepts for demonstration.

        Returns:
            ETLJobResult with load statistics.
        """
        import uuid

        # Sample concepts spanning multiple domains
        sample_concepts = [
            # Conditions
            ConceptNode(
                concept_id=201826,
                concept_name="Type 2 diabetes mellitus",
                vocabulary_id="SNOMED",
                domain_id="Condition",
                concept_class_id="Clinical Finding",
                standard_concept="S",
                concept_code="44054006",
                synonyms=["T2DM", "Type II diabetes", "Adult-onset diabetes"],
            ),
            ConceptNode(
                concept_id=4329847,
                concept_name="Diabetic retinopathy",
                vocabulary_id="SNOMED",
                domain_id="Condition",
                concept_class_id="Clinical Finding",
                standard_concept="S",
                concept_code="4855003",
                synonyms=["DR", "Diabetic eye disease"],
            ),
            ConceptNode(
                concept_id=316866,
                concept_name="Hypertensive disorder",
                vocabulary_id="SNOMED",
                domain_id="Condition",
                concept_class_id="Clinical Finding",
                standard_concept="S",
                concept_code="38341003",
                synonyms=["Hypertension", "High blood pressure", "HTN"],
            ),
            ConceptNode(
                concept_id=4154314,
                concept_name="Diabetes mellitus",
                vocabulary_id="SNOMED",
                domain_id="Condition",
                concept_class_id="Clinical Finding",
                standard_concept="S",
                concept_code="73211009",
                synonyms=["DM", "Diabetes"],
            ),
            ConceptNode(
                concept_id=4027384,
                concept_name="Disorder of glucose metabolism",
                vocabulary_id="SNOMED",
                domain_id="Condition",
                concept_class_id="Clinical Finding",
                standard_concept="S",
                concept_code="126877002",
            ),
            ConceptNode(
                concept_id=321588,
                concept_name="Heart failure",
                vocabulary_id="SNOMED",
                domain_id="Condition",
                concept_class_id="Clinical Finding",
                standard_concept="S",
                concept_code="84114007",
                synonyms=["CHF", "Congestive heart failure", "HF"],
            ),
            ConceptNode(
                concept_id=77670,
                concept_name="Chest pain",
                vocabulary_id="SNOMED",
                domain_id="Condition",
                concept_class_id="Clinical Finding",
                standard_concept="S",
                concept_code="29857009",
            ),
            ConceptNode(
                concept_id=437663,
                concept_name="Fever",
                vocabulary_id="SNOMED",
                domain_id="Condition",
                concept_class_id="Clinical Finding",
                standard_concept="S",
                concept_code="386661006",
                synonyms=["Pyrexia", "Febrile"],
            ),

            # Drugs
            ConceptNode(
                concept_id=1503297,
                concept_name="Metformin",
                vocabulary_id="RxNorm",
                domain_id="Drug",
                concept_class_id="Ingredient",
                standard_concept="S",
                concept_code="6809",
                synonyms=["Glucophage", "Metformin hydrochloride"],
            ),
            ConceptNode(
                concept_id=1308216,
                concept_name="Lisinopril",
                vocabulary_id="RxNorm",
                domain_id="Drug",
                concept_class_id="Ingredient",
                standard_concept="S",
                concept_code="29046",
                synonyms=["Prinivil", "Zestril"],
            ),
            ConceptNode(
                concept_id=1332418,
                concept_name="Amlodipine",
                vocabulary_id="RxNorm",
                domain_id="Drug",
                concept_class_id="Ingredient",
                standard_concept="S",
                concept_code="17767",
                synonyms=["Norvasc"],
            ),
            ConceptNode(
                concept_id=1510202,
                concept_name="Insulin glargine",
                vocabulary_id="RxNorm",
                domain_id="Drug",
                concept_class_id="Ingredient",
                standard_concept="S",
                concept_code="274783",
                synonyms=["Lantus", "Basaglar"],
            ),
            ConceptNode(
                concept_id=1545958,
                concept_name="Atorvastatin",
                vocabulary_id="RxNorm",
                domain_id="Drug",
                concept_class_id="Ingredient",
                standard_concept="S",
                concept_code="83367",
                synonyms=["Lipitor"],
            ),
            ConceptNode(
                concept_id=1125315,
                concept_name="Aspirin",
                vocabulary_id="RxNorm",
                domain_id="Drug",
                concept_class_id="Ingredient",
                standard_concept="S",
                concept_code="1191",
                synonyms=["ASA", "Acetylsalicylic acid"],
            ),

            # Measurements
            ConceptNode(
                concept_id=4058243,
                concept_name="Hemoglobin A1c/Hemoglobin.total in Blood",
                vocabulary_id="LOINC",
                domain_id="Measurement",
                concept_class_id="Lab Test",
                standard_concept="S",
                concept_code="4548-4",
                synonyms=["HbA1c", "Glycated hemoglobin", "A1C"],
            ),
            ConceptNode(
                concept_id=3004501,
                concept_name="Glucose [Mass/volume] in Blood",
                vocabulary_id="LOINC",
                domain_id="Measurement",
                concept_class_id="Lab Test",
                standard_concept="S",
                concept_code="2345-7",
                synonyms=["Blood glucose", "Blood sugar"],
            ),
            ConceptNode(
                concept_id=3019550,
                concept_name="Creatinine [Mass/volume] in Serum or Plasma",
                vocabulary_id="LOINC",
                domain_id="Measurement",
                concept_class_id="Lab Test",
                standard_concept="S",
                concept_code="2160-0",
                synonyms=["Serum creatinine", "SCr"],
            ),
            ConceptNode(
                concept_id=3013682,
                concept_name="LDL Cholesterol",
                vocabulary_id="LOINC",
                domain_id="Measurement",
                concept_class_id="Lab Test",
                standard_concept="S",
                concept_code="13457-7",
                synonyms=["LDL-C", "Bad cholesterol"],
            ),

            # Procedures
            ConceptNode(
                concept_id=4000479,
                concept_name="Eye exam",
                vocabulary_id="SNOMED",
                domain_id="Procedure",
                concept_class_id="Procedure",
                standard_concept="S",
                concept_code="36228007",
                synonyms=["Ophthalmologic examination", "Eye examination"],
            ),
            ConceptNode(
                concept_id=2107339,
                concept_name="Echocardiography",
                vocabulary_id="SNOMED",
                domain_id="Procedure",
                concept_class_id="Procedure",
                standard_concept="S",
                concept_code="40701008",
                synonyms=["Echo", "Cardiac ultrasound"],
            ),
            ConceptNode(
                concept_id=4080911,
                concept_name="Electrocardiogram",
                vocabulary_id="SNOMED",
                domain_id="Procedure",
                concept_class_id="Procedure",
                standard_concept="S",
                concept_code="29303009",
                synonyms=["ECG", "EKG"],
            ),

            # Genes (for pathway visualization)
            ConceptNode(
                concept_id=45770817,
                concept_name="TCF7L2 gene",
                vocabulary_id="HGNC",
                domain_id="Gene",
                concept_class_id="Gene",
                standard_concept="S",
                concept_code="11641",
                synonyms=["TCF4", "Transcription factor 7-like 2"],
            ),
            ConceptNode(
                concept_id=45770818,
                concept_name="PPARG gene",
                vocabulary_id="HGNC",
                domain_id="Gene",
                concept_class_id="Gene",
                standard_concept="S",
                concept_code="9236",
                synonyms=["PPARgamma", "Peroxisome proliferator-activated receptor gamma"],
            ),
            ConceptNode(
                concept_id=45770819,
                concept_name="SLC2A2 gene",
                vocabulary_id="HGNC",
                domain_id="Gene",
                concept_class_id="Gene",
                standard_concept="S",
                concept_code="11006",
                synonyms=["GLUT2", "Glucose transporter 2"],
            ),
        ]

        # Load concepts first
        job = self.load_concepts(sample_concepts, job_id=str(uuid.uuid4()))

        # Define relationships
        sample_relationships = [
            # Hierarchy relationships (IS_A)
            ConceptRelationship(
                concept_id_1=201826,  # Type 2 diabetes
                concept_id_2=4154314,  # Diabetes mellitus
                relationship_id="116680003",
                relationship_type=RelationshipType.IS_A,
                min_levels_of_separation=1,
                max_levels_of_separation=1,
            ),
            ConceptRelationship(
                concept_id_1=4154314,  # Diabetes mellitus
                concept_id_2=4027384,  # Disorder of glucose metabolism
                relationship_id="116680003",
                relationship_type=RelationshipType.IS_A,
                min_levels_of_separation=1,
                max_levels_of_separation=1,
            ),
            ConceptRelationship(
                concept_id_1=4329847,  # Diabetic retinopathy
                concept_id_2=201826,  # Type 2 diabetes
                relationship_id="42752001",
                relationship_type=RelationshipType.ASSOCIATED_WITH,
            ),

            # Treatment relationships
            ConceptRelationship(
                concept_id_1=1503297,  # Metformin
                concept_id_2=201826,  # Type 2 diabetes
                relationship_id="may_treat",
                relationship_type=RelationshipType.MAY_TREAT,
            ),
            ConceptRelationship(
                concept_id_1=1510202,  # Insulin glargine
                concept_id_2=201826,  # Type 2 diabetes
                relationship_id="may_treat",
                relationship_type=RelationshipType.MAY_TREAT,
            ),
            ConceptRelationship(
                concept_id_1=1308216,  # Lisinopril
                concept_id_2=316866,  # Hypertension
                relationship_id="may_treat",
                relationship_type=RelationshipType.MAY_TREAT,
            ),
            ConceptRelationship(
                concept_id_1=1332418,  # Amlodipine
                concept_id_2=316866,  # Hypertension
                relationship_id="may_treat",
                relationship_type=RelationshipType.MAY_TREAT,
            ),
            ConceptRelationship(
                concept_id_1=1545958,  # Atorvastatin
                concept_id_2=321588,  # Heart failure
                relationship_id="may_prevent",
                relationship_type=RelationshipType.MAY_PREVENT,
            ),

            # Measurement relationships
            ConceptRelationship(
                concept_id_1=4058243,  # HbA1c
                concept_id_2=201826,  # Type 2 diabetes
                relationship_id="measures",
                relationship_type=RelationshipType.ASSOCIATED_WITH,
            ),
            ConceptRelationship(
                concept_id_1=3004501,  # Blood glucose
                concept_id_2=201826,  # Type 2 diabetes
                relationship_id="measures",
                relationship_type=RelationshipType.ASSOCIATED_WITH,
            ),

            # Gene-Disease relationships
            ConceptRelationship(
                concept_id_1=45770817,  # TCF7L2
                concept_id_2=201826,  # Type 2 diabetes
                relationship_id="associated_with",
                relationship_type=RelationshipType.ASSOCIATED_WITH,
            ),
            ConceptRelationship(
                concept_id_1=45770818,  # PPARG
                concept_id_2=201826,  # Type 2 diabetes
                relationship_id="associated_with",
                relationship_type=RelationshipType.ASSOCIATED_WITH,
            ),
            ConceptRelationship(
                concept_id_1=45770819,  # SLC2A2
                concept_id_2=4027384,  # Glucose metabolism disorder
                relationship_id="involved_in",
                relationship_type=RelationshipType.INVOLVED_IN,
            ),

            # Drug-Gene interactions
            ConceptRelationship(
                concept_id_1=1503297,  # Metformin
                concept_id_2=45770818,  # PPARG
                relationship_id="activates",
                relationship_type=RelationshipType.REGULATES,
            ),
        ]

        # Load relationships
        rel_job = self.load_concept_relationships(sample_relationships)

        # Combine results
        job.relationships_created = rel_job.relationships_created
        job.errors.extend(rel_job.errors)

        return job

    def get_progress(self) -> ETLProgress | None:
        """Get current ETL progress.

        Returns:
            Current progress or None if no job running.
        """
        return self._progress

    def get_current_job(self) -> ETLJobResult | None:
        """Get current running job.

        Returns:
            Current job or None if no job running.
        """
        return self._current_job

    def get_stats(self) -> dict[str, Any]:
        """Get ETL service statistics.

        Returns:
            Dictionary with service stats.
        """
        return {
            "graph_connected": self._graph.is_connected,
            "mock_mode": self._graph.is_mock_mode,
            "total_concepts_loaded": self._total_concepts_loaded,
            "total_relationships_loaded": self._total_relationships_loaded,
            "batch_size": self._batch_size,
            "last_etl_run": self._last_etl_run,
            "current_job": self._current_job.job_id if self._current_job else None,
        }


def get_graph_etl_service() -> GraphETLService:
    """Get the singleton GraphETLService instance.

    Returns:
        The GraphETLService singleton.
    """
    global _graph_etl_service

    if _graph_etl_service is None:
        with _service_lock:
            if _graph_etl_service is None:
                _graph_etl_service = GraphETLService()

    return _graph_etl_service


def reset_graph_etl_service() -> None:
    """Reset the singleton for testing."""
    global _graph_etl_service

    with _service_lock:
        _graph_etl_service = None
