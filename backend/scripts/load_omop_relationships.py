#!/usr/bin/env python3
"""Load only relationships into Neo4j (concepts must be loaded first)."""

from __future__ import annotations

import csv
import logging
import time
from collections import defaultdict
from pathlib import Path

from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def load_relationships(
    vocab_path: Path = Path("fixtures/umls"),
    neo4j_uri: str = "bolt://localhost:7687",
    neo4j_password: str = "clinical123",
    batch_size: int = 50000,
):
    """Load relationships from CONCEPT_RELATIONSHIP.csv."""
    driver = GraphDatabase.driver(neo4j_uri, auth=("neo4j", neo4j_password))

    # Get loaded concept IDs
    logger.info("Getting loaded concept IDs...")
    with driver.session() as session:
        result = session.run("MATCH (c:Concept) RETURN c.concept_id as id")
        loaded_ids = {r["id"] for r in result}
    logger.info(f"Found {len(loaded_ids):,} concepts")

    filepath = vocab_path / "CONCEPT_RELATIONSHIP.csv"
    logger.info(f"Loading relationships from {filepath}")

    start_time = time.time()
    loaded = 0
    skipped = 0
    batch: dict[str, list] = defaultdict(list)

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")

        for row in reader:
            id1 = int(row["concept_id_1"])
            id2 = int(row["concept_id_2"])
            rel_id = row["relationship_id"]

            if id1 not in loaded_ids or id2 not in loaded_ids:
                skipped += 1
                continue

            if id1 == id2:
                continue

            safe_rel = rel_id.replace(" ", "_").replace("-", "_").upper()
            batch[safe_rel].append({"id1": id1, "id2": id2})

            total = sum(len(v) for v in batch.values())
            if total >= batch_size:
                loaded += flush_batch(driver, batch)
                batch.clear()
                if loaded % 1000000 == 0:
                    elapsed = time.time() - start_time
                    rate = loaded / elapsed if elapsed > 0 else 0
                    logger.info(f"Loaded {loaded:,} relationships ({rate:,.0f}/sec)")

    # Final flush
    loaded += flush_batch(driver, batch)

    elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info(f"Loaded {loaded:,} relationships in {elapsed/60:.1f} minutes")
    logger.info(f"Skipped {skipped:,} (missing concepts)")
    logger.info("=" * 60)

    driver.close()


def flush_batch(driver, batch: dict[str, list]) -> int:
    """Flush a batch of relationships to Neo4j - sequentially to avoid deadlocks."""
    loaded = 0
    for rel_type, rels in batch.items():
        if not rels:
            continue
        try:
            with driver.session() as session:
                query = f"""
                UNWIND $rels AS r
                MATCH (c1:Concept {{concept_id: r.id1}})
                MATCH (c2:Concept {{concept_id: r.id2}})
                MERGE (c1)-[:{rel_type}]->(c2)
                """
                session.run(query, rels=rels)
                loaded += len(rels)
        except Exception as e:
            logger.warning(f"Error on {rel_type}: {e}")
    return loaded


if __name__ == "__main__":
    load_relationships()
