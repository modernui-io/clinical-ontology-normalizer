"""Load SNOMED/OMOP lateral relationships into Neo4j.

Reads lateral (non-hierarchical) relationships from the PostgreSQL
omop_concept_relationship table and writes them to Neo4j as typed
edges on shared concept nodes.

This enables multi-hop paths like:
  Pneumonia -[HAS_FINDING_SITE]-> Lung -[FINDING_SITE_OF]-> Lung abscess

Usage:
    python -m scripts.load_snomed_lateral_rels [--batch-size 1000] [--dry-run]
"""

import argparse
import logging
import sys
import time

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# Add parent to path for imports
sys.path.insert(0, ".")

from app.core.config import settings
from app.services.graph_database_service import get_graph_database_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Lateral relationship types to load (non-hierarchical, clinically useful)
LATERAL_RELATIONSHIPS = [
    "Has finding site",
    "Finding site of",
    "Has causative agent",
    "Causative agent of",
    "Has asso morph",
    "Asso morph of",
    "May treat",
    "May be treated by",
    "May cause",
    "May be caused by",
    "May prevent",
    "May be prevented by",
    "Has pathological process",
    "Pathological process of",
]

# Map OMOP relationship_id -> Neo4j relationship type
REL_TO_NEO4J_TYPE = {
    "Has finding site": "HAS_FINDING_SITE",
    "Finding site of": "FINDING_SITE_OF",
    "Has causative agent": "HAS_CAUSATIVE_AGENT",
    "Causative agent of": "CAUSATIVE_AGENT_OF",
    "Has asso morph": "HAS_MORPHOLOGY",
    "Asso morph of": "MORPHOLOGY_OF",
    "May treat": "MAY_TREAT",
    "May be treated by": "MAY_BE_TREATED_BY",
    "May cause": "MAY_CAUSE",
    "May be caused by": "MAY_BE_CAUSED_BY",
    "May prevent": "MAY_PREVENT",
    "May be prevented by": "MAY_BE_PREVENTED_BY",
    "Has pathological process": "HAS_PATHOLOGICAL_PROCESS",
    "Pathological process of": "PATHOLOGICAL_PROCESS_OF",
}


def count_lateral_rels(session: Session) -> int:
    """Count total lateral relationships to load."""
    sql = text("""
        SELECT COUNT(*)
        FROM omop_concept_relationship cr
        WHERE cr.relationship_id = ANY(:rels)
          AND cr.invalid_reason IS NULL
    """)
    result = session.execute(sql, {"rels": LATERAL_RELATIONSHIPS})
    return result.scalar() or 0


def load_lateral_rels(
    session: Session,
    batch_size: int = 1000,
    dry_run: bool = False,
) -> int:
    """Load lateral relationships from PG into Neo4j.

    Returns:
        Total number of relationships loaded.
    """
    graph_db = get_graph_database_service()
    if not graph_db.is_connected:
        logger.error("Neo4j is not available. Cannot load relationships.")
        return 0

    total_count = count_lateral_rels(session)
    logger.info("Found %d lateral relationships to load", total_count)

    if dry_run:
        logger.info("Dry run - would load %d relationships", total_count)
        return 0

    # Process in batches using OFFSET/LIMIT
    loaded = 0
    offset = 0
    start_time = time.time()

    while offset < total_count:
        sql = text("""
            SELECT
                cr.concept_id_1,
                cr.concept_id_2,
                cr.relationship_id,
                c1.concept_name AS source_name,
                c1.domain_id AS source_domain,
                c2.concept_name AS target_name,
                c2.domain_id AS target_domain
            FROM omop_concept_relationship cr
            JOIN omop_concept c1 ON c1.concept_id = cr.concept_id_1
            JOIN omop_concept c2 ON c2.concept_id = cr.concept_id_2
            WHERE cr.relationship_id = ANY(:rels)
              AND cr.invalid_reason IS NULL
            ORDER BY cr.concept_id_1, cr.concept_id_2
            LIMIT :limit OFFSET :offset
        """)
        rows = session.execute(
            sql, {"rels": LATERAL_RELATIONSHIPS, "limit": batch_size, "offset": offset}
        ).fetchall()

        if not rows:
            break

        # Group by Neo4j relationship type for batched UNWIND
        batches: dict[str, list[dict]] = {}
        for row in rows:
            rel_id = row[2]
            neo4j_type = REL_TO_NEO4J_TYPE.get(rel_id)
            if neo4j_type is None:
                continue

            source_node_id = f"{row[4].lower()}_{row[0]}"  # domain_conceptid
            target_node_id = f"{row[6].lower()}_{row[1]}"

            if neo4j_type not in batches:
                batches[neo4j_type] = []
            batches[neo4j_type].append({
                "source_id": source_node_id,
                "target_id": target_node_id,
                "source_concept_id": row[0],
                "target_concept_id": row[1],
                "source_name": row[3],
                "target_name": row[5],
                "relationship_id": rel_id,
            })

        # Write each batch to Neo4j
        for neo4j_type, batch_data in batches.items():
            cypher = f"""
            UNWIND $rels AS row
            MERGE (s:ClinicalFact {{node_id: row.source_id}})
            ON CREATE SET s.label = row.source_name,
                          s.omop_concept_id = row.source_concept_id
            MERGE (t:ClinicalFact {{node_id: row.target_id}})
            ON CREATE SET t.label = row.target_name,
                          t.omop_concept_id = row.target_concept_id
            MERGE (s)-[r:{neo4j_type}]->(t)
            SET r.relationship_id = row.relationship_id,
                r.source = 'omop_lateral',
                r.updated_at = datetime()
            """
            graph_db.execute_write(cypher, {"rels": batch_data})
            loaded += len(batch_data)

        offset += batch_size
        elapsed = time.time() - start_time
        rate = loaded / elapsed if elapsed > 0 else 0
        logger.info(
            "Loaded %d/%d relationships (%.0f/sec)", loaded, total_count, rate
        )

    elapsed = time.time() - start_time
    logger.info(
        "Finished loading %d lateral relationships in %.1fs", loaded, elapsed
    )
    return loaded


def main() -> None:
    parser = argparse.ArgumentParser(description="Load SNOMED lateral rels to Neo4j")
    parser.add_argument("--batch-size", type=int, default=1000, help="Batch size")
    parser.add_argument("--dry-run", action="store_true", help="Count only, don't load")
    args = parser.parse_args()

    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        loaded = load_lateral_rels(
            session, batch_size=args.batch_size, dry_run=args.dry_run
        )
        logger.info("Total loaded: %d", loaded)


if __name__ == "__main__":
    main()
