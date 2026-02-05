"""Load OMOP concept relationships from Athena CSV files.

Loads the CONCEPT_RELATIONSHIP.csv file which contains mappings between
vocabularies (ICD-10 to SNOMED, NDC to RxNorm, etc.).

Usage:
    # Load all relationships
    python -m app.scripts.load_concept_relationships --path /path/to/vocab/

    # Load only "Maps to" relationships (most useful for cross-vocab mapping)
    python -m app.scripts.load_concept_relationships --path /path/to/vocab/ --relationships "Maps to"

    # Load mapping relationships only
    python -m app.scripts.load_concept_relationships --path /path/to/vocab/ --mapping-only
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import logging
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Key relationships for cross-vocabulary mapping
MAPPING_RELATIONSHIPS = {
    "Maps to",       # Source to standard mapping
    "Mapped from",   # Reverse of "Maps to"
}

# Hierarchical relationships
HIERARCHY_RELATIONSHIPS = {
    "Is a",         # Child to parent
    "Subsumes",     # Parent to child (reverse of "Is a")
}


async def clear_relationships(session: AsyncSession) -> None:
    """Clear existing relationship data."""
    await session.execute(text("DELETE FROM concept_relationships"))
    await session.commit()
    logger.info("Cleared existing relationship data")


async def load_relationships(
    session: AsyncSession,
    relationship_file: Path,
    relationship_types: set[str] | None = None,
    batch_size: int = 10000,
) -> int:
    """Load concept relationships from CONCEPT_RELATIONSHIP.csv.

    Args:
        session: Database session
        relationship_file: Path to CONCEPT_RELATIONSHIP.csv
        relationship_types: Set of relationship_ids to include (None = all)
        batch_size: Number of rows to insert per batch

    Returns:
        Number of relationships loaded
    """
    logger.info(f"Loading relationships from {relationship_file}")

    if relationship_types:
        logger.info(f"Filtering to relationship types: {relationship_types}")

    # Get set of concept_ids we have loaded (for filtering)
    result = await session.execute(text("SELECT concept_id FROM concepts"))
    valid_concept_ids = {row[0] for row in result.fetchall()}
    logger.info(f"Found {len(valid_concept_ids):,} concepts to match relationships against")

    count = 0
    skipped = 0
    batch = []

    with open(relationship_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")

        for row in reader:
            relationship_id = row["relationship_id"]

            # Apply relationship filter
            if relationship_types and relationship_id not in relationship_types:
                continue

            concept_id_1 = int(row["concept_id_1"])
            concept_id_2 = int(row["concept_id_2"])

            # Skip if either concept is not in our loaded vocabulary
            if concept_id_1 not in valid_concept_ids or concept_id_2 not in valid_concept_ids:
                skipped += 1
                continue

            # Skip invalid relationships
            if row.get("invalid_reason"):
                skipped += 1
                continue

            batch.append({
                "concept_id_1": concept_id_1,
                "concept_id_2": concept_id_2,
                "relationship_id": relationship_id,
                "valid_start_date": row.get("valid_start_date"),
                "valid_end_date": row.get("valid_end_date"),
                "invalid_reason": row.get("invalid_reason") or None,
            })

            if len(batch) >= batch_size:
                await _insert_relationships_batch(session, batch)
                count += len(batch)
                logger.info(f"Loaded {count:,} relationships (skipped {skipped:,})...")
                batch = []

        # Insert remaining
        if batch:
            await _insert_relationships_batch(session, batch)
            count += len(batch)

    await session.commit()
    logger.info(f"Loaded {count:,} relationships total (skipped {skipped:,} due to missing concepts or invalid)")
    return count


async def _insert_relationships_batch(session: AsyncSession, batch: list[dict]) -> None:
    """Insert a batch of relationships."""
    # Simplify batch to only include columns that exist in the table
    simplified_batch = [
        {
            "concept_id_1": r["concept_id_1"],
            "concept_id_2": r["concept_id_2"],
            "relationship_id": r["relationship_id"],
        }
        for r in batch
    ]
    await session.execute(
        text("""
            INSERT INTO concept_relationships (id, concept_id_1, concept_id_2, relationship_id)
            VALUES (gen_random_uuid(), :concept_id_1, :concept_id_2, :relationship_id)
            ON CONFLICT DO NOTHING
        """),
        simplified_batch
    )


async def load_vocabulary_relationships(
    vocab_path: Path,
    relationship_types: set[str] | None = None,
    clear_existing: bool = True,
) -> dict[str, int]:
    """Load OMOP concept relationships from directory.

    Args:
        vocab_path: Path to directory containing CONCEPT_RELATIONSHIP.csv
        relationship_types: Set of relationship_ids to load (None = all)
        clear_existing: Whether to clear existing data first

    Returns:
        Dictionary with counts of loaded relationships
    """
    relationship_file = vocab_path / "CONCEPT_RELATIONSHIP.csv"

    if not relationship_file.exists():
        raise FileNotFoundError(f"CONCEPT_RELATIONSHIP.csv not found in {vocab_path}")

    async with async_session_maker() as session:
        if clear_existing:
            await clear_relationships(session)

        relationship_count = await load_relationships(
            session, relationship_file, relationship_types
        )

        # Log summary by relationship type
        result = await session.execute(text("""
            SELECT relationship_id, COUNT(*)
            FROM concept_relationships
            GROUP BY relationship_id
            ORDER BY COUNT(*) DESC
            LIMIT 20
        """))
        logger.info("Relationships by type (top 20):")
        for rel_type, count in result.fetchall():
            logger.info(f"  {rel_type}: {count:,}")

    return {
        "relationships": relationship_count,
    }


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Load OMOP concept relationships from Athena CSV files"
    )
    parser.add_argument(
        "--path",
        type=Path,
        required=True,
        help="Path to directory containing CONCEPT_RELATIONSHIP.csv",
    )
    parser.add_argument(
        "--relationships",
        type=str,
        default=None,
        help="Comma-separated list of relationship_ids to load (default: all)",
    )
    parser.add_argument(
        "--mapping-only",
        action="store_true",
        help="Load only mapping relationships (Maps to, Mapped from)",
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Don't clear existing relationship data",
    )

    args = parser.parse_args()

    relationship_types = None
    if args.mapping_only:
        relationship_types = MAPPING_RELATIONSHIPS
    elif args.relationships:
        relationship_types = set(r.strip() for r in args.relationships.split(","))

    try:
        result = await load_vocabulary_relationships(
            args.path,
            relationship_types=relationship_types,
            clear_existing=not args.no_clear,
        )
        logger.info(f"Load complete: {result['relationships']:,} relationships")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
