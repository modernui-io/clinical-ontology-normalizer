"""Build the omop_concept_ancestor closure table from concept_relationship IS_A edges.

Iterative BFS algorithm (not recursive CTE) for better memory control with
large vocabularies like SNOMED CT.

Algorithm:
    1. Optionally truncate omop_concept_ancestor
    2. Seed: insert direct "Is a" relationships at distance 1
    3. Iterate: for each distance N, join existing ancestors at distance N
       with direct "Is a" edges to discover distance N+1. Repeat until no
       new rows (max 25 iterations for SNOMED depth safety).
    4. Self-loops: insert (concept_id, concept_id, 0, 0) for every concept
       that participates in the hierarchy.
    5. ANALYZE: update planner statistics.

Usage:
    python -m scripts.build_concept_ancestor [--truncate] [--batch-size=50000] [--max-depth=25]
"""
from __future__ import annotations

import argparse
import logging
import sys
import time

from sqlalchemy import text
from sqlalchemy.orm import Session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def build_ancestor_table(
    *,
    truncate: bool = False,
    batch_size: int = 50_000,
    max_depth: int = 25,
) -> None:
    """Build the concept_ancestor closure table."""
    from app.core.database import get_sync_engine

    engine = get_sync_engine()

    with Session(engine) as session:
        t0 = time.perf_counter()

        # ---- Step 1: Optionally truncate ----
        if truncate:
            logger.info("Truncating omop_concept_ancestor...")
            session.execute(text("TRUNCATE TABLE omop_concept_ancestor"))
            session.commit()

        # ---- Step 2: Seed direct "Is a" relationships at distance 1 ----
        logger.info("Seeding direct 'Is a' relationships (distance=1)...")
        seed_sql = text("""
            INSERT INTO omop_concept_ancestor
                (descendant_concept_id, ancestor_concept_id,
                 min_levels_of_separation, max_levels_of_separation)
            SELECT cr.concept_id_1, cr.concept_id_2, 1, 1
            FROM omop_concept_relationship cr
            WHERE cr.relationship_id = 'Is a'
              AND cr.invalid_reason IS NULL
            ON CONFLICT (ancestor_concept_id, descendant_concept_id) DO NOTHING
        """)
        result = session.execute(seed_sql)
        total_inserted = result.rowcount or 0
        session.commit()
        logger.info("Seeded %d direct IS_A edges", total_inserted)

        # ---- Step 3: Iterative BFS expansion ----
        for depth in range(2, max_depth + 1):
            logger.info("Expanding depth %d...", depth)

            expand_sql = text("""
                INSERT INTO omop_concept_ancestor
                    (descendant_concept_id, ancestor_concept_id,
                     min_levels_of_separation, max_levels_of_separation)
                SELECT DISTINCT
                    ca.descendant_concept_id,
                    direct.concept_id_2,
                    :depth,
                    :depth
                FROM omop_concept_ancestor ca
                JOIN omop_concept_relationship direct
                    ON direct.concept_id_1 = ca.ancestor_concept_id
                   AND direct.relationship_id = 'Is a'
                   AND direct.invalid_reason IS NULL
                WHERE ca.min_levels_of_separation = :prev_depth
                ON CONFLICT (ancestor_concept_id, descendant_concept_id)
                DO UPDATE SET
                    min_levels_of_separation = LEAST(
                        omop_concept_ancestor.min_levels_of_separation,
                        EXCLUDED.min_levels_of_separation
                    ),
                    max_levels_of_separation = GREATEST(
                        omop_concept_ancestor.max_levels_of_separation,
                        EXCLUDED.max_levels_of_separation
                    )
            """)
            result = session.execute(
                expand_sql, {"depth": depth, "prev_depth": depth - 1}
            )
            new_rows = result.rowcount or 0
            session.commit()
            total_inserted += new_rows
            logger.info("Depth %d: %d new/updated rows", depth, new_rows)

            if new_rows == 0:
                logger.info("No new rows at depth %d — BFS complete", depth)
                break

        # ---- Step 4: Self-loops (distance 0) ----
        logger.info("Inserting self-loops (distance=0)...")
        self_loop_sql = text("""
            INSERT INTO omop_concept_ancestor
                (descendant_concept_id, ancestor_concept_id,
                 min_levels_of_separation, max_levels_of_separation)
            SELECT DISTINCT concept_id, concept_id, 0, 0
            FROM (
                SELECT descendant_concept_id AS concept_id
                FROM omop_concept_ancestor
                UNION
                SELECT ancestor_concept_id AS concept_id
                FROM omop_concept_ancestor
            ) participating
            ON CONFLICT (ancestor_concept_id, descendant_concept_id) DO NOTHING
        """)
        result = session.execute(self_loop_sql)
        self_loop_count = result.rowcount or 0
        session.commit()
        logger.info("Inserted %d self-loops", self_loop_count)

        # ---- Step 5: ANALYZE ----
        logger.info("Running ANALYZE on omop_concept_ancestor...")
        session.execute(text("ANALYZE omop_concept_ancestor"))
        session.commit()

        elapsed = time.perf_counter() - t0

        # Final count
        row = session.execute(
            text("SELECT COUNT(*) FROM omop_concept_ancestor")
        ).fetchone()
        total_rows = row[0] if row else 0

        logger.info(
            "Done in %.1fs. Total rows in omop_concept_ancestor: %d "
            "(inserted %d edges + %d self-loops)",
            elapsed, total_rows, total_inserted, self_loop_count,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build omop_concept_ancestor closure table from IS_A edges"
    )
    parser.add_argument(
        "--truncate", action="store_true",
        help="Truncate omop_concept_ancestor before building",
    )
    parser.add_argument(
        "--batch-size", type=int, default=50_000,
        help="Batch size for inserts (default: 50000)",
    )
    parser.add_argument(
        "--max-depth", type=int, default=25,
        help="Maximum BFS depth (default: 25, safe for SNOMED)",
    )
    args = parser.parse_args()

    build_ancestor_table(
        truncate=args.truncate,
        batch_size=args.batch_size,
        max_depth=args.max_depth,
    )


if __name__ == "__main__":
    main()
