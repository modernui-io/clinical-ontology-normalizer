#!/usr/bin/env python3
"""
OMOP CDM Vocabulary Loader for Neo4j.

Loads OMOP vocabulary files (from Athena) into Neo4j for the clinical knowledge graph.
This achieves parity with published systems for concept count.

Files loaded:
- CONCEPT.csv: ~5.6M concepts
- CONCEPT_RELATIONSHIP.csv: ~30M relations
- CONCEPT_SYNONYM.csv: Synonyms

Usage:
    python scripts/load_omop_to_neo4j.py --vocab-path fixtures/umls
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator

sys.path.insert(0, str(Path(__file__).parent.parent))

from neo4j import GraphDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Map OMOP domains to semantic groups for DR.KNOWS compatibility
DOMAIN_TO_SEMANTIC_GROUP = {
    "Condition": "Disorders",
    "Drug": "Chemicals & Drugs",
    "Procedure": "Procedures",
    "Measurement": "Physiology",
    "Observation": "Physiology",
    "Device": "Objects",
    "Spec Anatomic Site": "Anatomy",
    "Provider": "Organizations",
    "Visit": "Procedures",
    "Meas Value": "Concepts & Ideas",
    "Unit": "Concepts & Ideas",
    "Specimen": "Anatomy",
    "Route": "Concepts & Ideas",
    "Type Concept": "Concepts & Ideas",
}


@dataclass
class LoaderStats:
    """Statistics for the loading process."""

    concepts_loaded: int = 0
    relations_loaded: int = 0
    synonyms_loaded: int = 0
    errors: list[str] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)

    @property
    def duration_formatted(self) -> str:
        secs = int(time.time() - self.start_time)
        hours, remainder = divmod(secs, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}h {minutes}m {seconds}s"


class OMOPLoader:
    """Load OMOP vocabulary into Neo4j."""

    def __init__(
        self,
        vocab_path: Path,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "clinical123",
        batch_size: int = 10000,
        limit: int | None = None,
    ):
        self.vocab_path = Path(vocab_path)
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.batch_size = batch_size
        self.limit = limit

        self._driver = None
        self.stats = LoaderStats()
        self._loaded_concept_ids: set[int] = set()

    def connect(self) -> None:
        """Connect to Neo4j."""
        self._driver = GraphDatabase.driver(
            self.neo4j_uri,
            auth=(self.neo4j_user, self.neo4j_password),
            max_connection_lifetime=3600,
            max_connection_pool_size=100,
        )
        with self._driver.session() as session:
            session.run("RETURN 1")
        logger.info(f"Connected to Neo4j at {self.neo4j_uri}")

    def close(self) -> None:
        """Close Neo4j connection."""
        if self._driver:
            self._driver.close()

    def create_schema(self) -> None:
        """Create Neo4j schema for OMOP data."""
        schema_queries = [
            "CREATE CONSTRAINT omop_concept_id IF NOT EXISTS FOR (c:Concept) REQUIRE c.concept_id IS UNIQUE",
            "CREATE INDEX concept_name IF NOT EXISTS FOR (c:Concept) ON (c.name)",
            "CREATE INDEX concept_domain IF NOT EXISTS FOR (c:Concept) ON (c.domain_id)",
            "CREATE INDEX concept_vocabulary IF NOT EXISTS FOR (c:Concept) ON (c.vocabulary_id)",
            "CREATE INDEX concept_code IF NOT EXISTS FOR (c:Concept) ON (c.concept_code)",
            "CREATE INDEX concept_class IF NOT EXISTS FOR (c:Concept) ON (c.concept_class_id)",
        ]

        with self._driver.session() as session:
            for query in schema_queries:
                try:
                    session.run(query)
                except Exception as e:
                    logger.debug(f"Schema query (may exist): {e}")
        logger.info("Schema created")

    def load_concepts(self) -> int:
        """Load concepts from CONCEPT.csv."""
        logger.info("Loading concepts from CONCEPT.csv...")

        filepath = self.vocab_path / "CONCEPT.csv"
        if not filepath.exists():
            logger.error(f"File not found: {filepath}")
            return 0

        batch = []
        loaded = 0

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")

            for row in reader:
                if self.limit and loaded >= self.limit:
                    break

                concept_id = int(row["concept_id"])
                domain_id = row["domain_id"]

                batch.append({
                    "concept_id": concept_id,
                    "name": row["concept_name"],
                    "domain_id": domain_id,
                    "vocabulary_id": row["vocabulary_id"],
                    "concept_class_id": row["concept_class_id"],
                    "standard_concept": row["standard_concept"],
                    "concept_code": row["concept_code"],
                    "semantic_group": DOMAIN_TO_SEMANTIC_GROUP.get(domain_id, "Concepts & Ideas"),
                })

                self._loaded_concept_ids.add(concept_id)

                if len(batch) >= self.batch_size:
                    self._batch_create_concepts(batch)
                    loaded += len(batch)
                    if loaded % 100000 == 0:
                        logger.info(f"Loaded {loaded:,} concepts...")
                    batch = []

        if batch:
            self._batch_create_concepts(batch)
            loaded += len(batch)

        self.stats.concepts_loaded = loaded
        logger.info(f"Loaded {loaded:,} concepts")
        return loaded

    def _batch_create_concepts(self, batch: list[dict]) -> None:
        """Create concepts in batch."""
        query = """
        UNWIND $batch AS c
        MERGE (n:Concept {concept_id: c.concept_id})
        SET n.name = c.name,
            n.domain_id = c.domain_id,
            n.vocabulary_id = c.vocabulary_id,
            n.concept_class_id = c.concept_class_id,
            n.standard_concept = c.standard_concept,
            n.concept_code = c.concept_code,
            n.semantic_group = c.semantic_group
        """
        with self._driver.session() as session:
            session.run(query, batch=batch)

    def load_relationships(self, limit_per_type: int | None = None) -> int:
        """Load relationships from CONCEPT_RELATIONSHIP.csv."""
        logger.info("Loading relationships from CONCEPT_RELATIONSHIP.csv...")

        filepath = self.vocab_path / "CONCEPT_RELATIONSHIP.csv"
        if not filepath.exists():
            logger.error(f"File not found: {filepath}")
            return 0

        # Group by relationship type
        rel_batches: dict[str, list[dict]] = defaultdict(list)
        loaded = 0
        skipped = 0
        type_counts: dict[str, int] = defaultdict(int)

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")

            for row in reader:
                concept_id_1 = int(row["concept_id_1"])
                concept_id_2 = int(row["concept_id_2"])
                rel_id = row["relationship_id"]

                # Skip if concepts not loaded
                if concept_id_1 not in self._loaded_concept_ids or concept_id_2 not in self._loaded_concept_ids:
                    skipped += 1
                    continue

                # Skip self-loops
                if concept_id_1 == concept_id_2:
                    continue

                # Limit per type if specified
                if limit_per_type and type_counts[rel_id] >= limit_per_type:
                    continue

                # Sanitize relationship ID for Neo4j
                safe_rel_id = rel_id.replace(" ", "_").replace("-", "_").upper()

                rel_batches[safe_rel_id].append({
                    "id1": concept_id_1,
                    "id2": concept_id_2,
                })
                type_counts[rel_id] += 1

                # Process when batch gets large
                total_in_batches = sum(len(b) for b in rel_batches.values())
                if total_in_batches >= self.batch_size * 5:
                    loaded += self._flush_relationship_batches(rel_batches)
                    if loaded % 500000 == 0:
                        logger.info(f"Loaded {loaded:,} relationships...")

        # Flush remaining
        loaded += self._flush_relationship_batches(rel_batches)

        self.stats.relations_loaded = loaded
        logger.info(f"Loaded {loaded:,} relationships (skipped {skipped:,})")
        logger.info(f"Top relationship types: {dict(sorted(type_counts.items(), key=lambda x: -x[1])[:10])}")
        return loaded

    def _flush_relationship_batches(self, rel_batches: dict[str, list[dict]]) -> int:
        """Flush relationship batches to Neo4j."""
        loaded = 0
        with self._driver.session() as session:
            for rel_type, rels in list(rel_batches.items()):
                if not rels:
                    continue
                query = f"""
                UNWIND $rels AS r
                MATCH (c1:Concept {{concept_id: r.id1}})
                MATCH (c2:Concept {{concept_id: r.id2}})
                MERGE (c1)-[:{rel_type}]->(c2)
                """
                try:
                    session.run(query, rels=rels)
                    loaded += len(rels)
                except Exception as e:
                    logger.debug(f"Error creating {rel_type}: {e}")
                rel_batches[rel_type] = []
        return loaded

    def load_synonyms(self) -> int:
        """Load synonyms from CONCEPT_SYNONYM.csv."""
        logger.info("Loading synonyms from CONCEPT_SYNONYM.csv...")

        filepath = self.vocab_path / "CONCEPT_SYNONYM.csv"
        if not filepath.exists():
            logger.warning(f"File not found: {filepath}")
            return 0

        # Group synonyms by concept
        concept_synonyms: dict[int, list[str]] = defaultdict(list)
        count = 0

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                concept_id = int(row["concept_id"])
                if concept_id in self._loaded_concept_ids:
                    concept_synonyms[concept_id].append(row["concept_synonym_name"])
                    count += 1

        # Update in batches
        batch = []
        for concept_id, synonyms in concept_synonyms.items():
            batch.append({
                "concept_id": concept_id,
                "synonyms": synonyms[:20],  # Limit synonyms
            })

            if len(batch) >= self.batch_size:
                self._batch_update_synonyms(batch)
                batch = []

        if batch:
            self._batch_update_synonyms(batch)

        self.stats.synonyms_loaded = count
        logger.info(f"Loaded {count:,} synonyms for {len(concept_synonyms):,} concepts")
        return count

    def _batch_update_synonyms(self, batch: list[dict]) -> None:
        """Update synonyms for concepts."""
        query = """
        UNWIND $batch AS item
        MATCH (c:Concept {concept_id: item.concept_id})
        SET c.synonyms = item.synonyms
        """
        with self._driver.session() as session:
            session.run(query, batch=batch)

    def load_all(self, skip_relationships: bool = False) -> LoaderStats:
        """Load all vocabulary data."""
        logger.info("=" * 60)
        logger.info("Starting OMOP vocabulary load to Neo4j")
        logger.info(f"Vocab path: {self.vocab_path}")
        logger.info(f"Limit: {self.limit or 'None'}")
        logger.info("=" * 60)

        try:
            self.connect()
            self.create_schema()
            self.load_concepts()
            self.load_synonyms()

            if not skip_relationships:
                self.load_relationships()

            logger.info("=" * 60)
            logger.info("Load complete!")
            logger.info(f"Concepts: {self.stats.concepts_loaded:,}")
            logger.info(f"Relations: {self.stats.relations_loaded:,}")
            logger.info(f"Synonyms: {self.stats.synonyms_loaded:,}")
            logger.info(f"Duration: {self.stats.duration_formatted}")
            logger.info("=" * 60)

        except Exception as e:
            self.stats.errors.append(str(e))
            logger.error(f"Error: {e}")
            raise
        finally:
            self.close()

        return self.stats


def main():
    parser = argparse.ArgumentParser(description="Load OMOP vocabulary into Neo4j")
    parser.add_argument(
        "--vocab-path",
        type=Path,
        default=Path("fixtures/umls"),
        help="Path to vocabulary files",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of concepts (for testing)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10000,
        help="Batch size for Neo4j operations",
    )
    parser.add_argument(
        "--skip-relationships",
        action="store_true",
        help="Skip loading relationships (faster for testing)",
    )
    parser.add_argument(
        "--neo4j-password",
        type=str,
        default=os.environ.get("NEO4J_PASSWORD", "clinical123"),
        help="Neo4j password",
    )

    args = parser.parse_args()

    if not args.vocab_path.exists():
        logger.error(f"Path not found: {args.vocab_path}")
        sys.exit(1)

    loader = OMOPLoader(
        vocab_path=args.vocab_path,
        neo4j_password=args.neo4j_password,
        batch_size=args.batch_size,
        limit=args.limit,
    )

    loader.load_all(skip_relationships=args.skip_relationships)


if __name__ == "__main__":
    main()
