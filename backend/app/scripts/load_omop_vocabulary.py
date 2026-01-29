"""Load OMOP vocabulary from Athena CSV files.

Downloads vocabulary from Athena (athena.ohdsi.org) and loads into database.

Usage:
    # Load from local CSV files (after downloading from Athena)
    python -m app.scripts.load_omop_vocabulary --path /path/to/vocab/

    # Load specific vocabularies only
    python -m app.scripts.load_omop_vocabulary --path /path/to/vocab/ --vocabularies SNOMED,RxNorm,LOINC

    # Load specific domains only
    python -m app.scripts.load_omop_vocabulary --path /path/to/vocab/ --domains Condition,Drug,Measurement

Requirements:
    1. Register at https://athena.ohdsi.org (free)
    2. Download vocabularies (select SNOMED, RxNorm, LOINC at minimum)
    3. Extract the downloaded zip file
    4. Run this script pointing to the extracted directory
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

# Default vocabularies to load (most useful for clinical NLP)
DEFAULT_VOCABULARIES = {
    "SNOMED",      # Clinical findings, conditions, procedures
    "RxNorm",      # Drugs
    "LOINC",       # Lab tests, measurements
    "RxNorm Extension",  # Additional drug concepts
}

# Default domains to load
DEFAULT_DOMAINS = {
    "Condition",
    "Drug",
    "Measurement",
    "Procedure",
    "Observation",
    "Device",
}


async def clear_vocabulary(session: AsyncSession) -> None:
    """Clear existing vocabulary data."""
    await session.execute(text("DELETE FROM concept_synonyms"))
    await session.execute(text("DELETE FROM concepts"))
    await session.commit()
    logger.info("Cleared existing vocabulary data")


async def load_concepts(
    session: AsyncSession,
    concept_file: Path,
    vocabularies: set[str] | None = None,
    domains: set[str] | None = None,
    batch_size: int = 10000,
) -> int:
    """Load concepts from CONCEPT.csv.

    Args:
        session: Database session
        concept_file: Path to CONCEPT.csv
        vocabularies: Set of vocabulary_ids to include (None = all)
        domains: Set of domain_ids to include (None = all)
        batch_size: Number of rows to insert per batch

    Returns:
        Number of concepts loaded
    """
    logger.info(f"Loading concepts from {concept_file}")

    if vocabularies:
        logger.info(f"Filtering to vocabularies: {vocabularies}")
    if domains:
        logger.info(f"Filtering to domains: {domains}")

    count = 0
    batch = []

    with open(concept_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")

        for row in reader:
            # Apply filters
            if vocabularies and row["vocabulary_id"] not in vocabularies:
                continue
            if domains and row["domain_id"] not in domains:
                continue

            # Only load standard concepts (S) and classification concepts (C)
            standard = row.get("standard_concept", "")
            if standard not in ("S", "C", ""):
                continue

            batch.append({
                "concept_id": int(row["concept_id"]),
                "concept_name": row["concept_name"][:500],  # Truncate if needed
                "domain_id": row["domain_id"],
                "vocabulary_id": row["vocabulary_id"],
                "concept_class_id": row["concept_class_id"],
                "standard_concept": standard if standard else None,
            })

            if len(batch) >= batch_size:
                await _insert_concepts_batch(session, batch)
                count += len(batch)
                logger.info(f"Loaded {count:,} concepts...")
                batch = []

        # Insert remaining
        if batch:
            await _insert_concepts_batch(session, batch)
            count += len(batch)

    await session.commit()
    logger.info(f"Loaded {count:,} concepts total")
    return count


async def _insert_concepts_batch(session: AsyncSession, batch: list[dict]) -> None:
    """Insert a batch of concepts."""
    await session.execute(
        text("""
            INSERT INTO concepts (id, concept_id, concept_name, domain_id, vocabulary_id, concept_class_id, standard_concept)
            VALUES (gen_random_uuid(), :concept_id, :concept_name, :domain_id, :vocabulary_id, :concept_class_id, :standard_concept)
            ON CONFLICT (concept_id) DO UPDATE SET
                concept_name = EXCLUDED.concept_name,
                domain_id = EXCLUDED.domain_id,
                vocabulary_id = EXCLUDED.vocabulary_id,
                concept_class_id = EXCLUDED.concept_class_id,
                standard_concept = EXCLUDED.standard_concept
        """),
        batch
    )


async def load_synonyms(
    session: AsyncSession,
    synonym_file: Path,
    batch_size: int = 10000,
) -> int:
    """Load concept synonyms from CONCEPT_SYNONYM.csv.

    Only loads synonyms for concepts that exist in the database.

    Args:
        session: Database session
        synonym_file: Path to CONCEPT_SYNONYM.csv
        batch_size: Number of rows to insert per batch

    Returns:
        Number of synonyms loaded
    """
    logger.info(f"Loading synonyms from {synonym_file}")

    # Get set of concept_ids we have loaded
    result = await session.execute(text("SELECT concept_id FROM concepts"))
    valid_concept_ids = {row[0] for row in result.fetchall()}
    logger.info(f"Found {len(valid_concept_ids):,} concepts to match synonyms against")

    count = 0
    batch = []

    with open(synonym_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")

        for row in reader:
            concept_id = int(row["concept_id"])

            # Skip synonyms for concepts we didn't load
            if concept_id not in valid_concept_ids:
                continue

            synonym_name = row["concept_synonym_name"].lower()[:500]

            batch.append({
                "concept_id": concept_id,
                "concept_synonym_name": synonym_name,
                "language_concept_id": int(row.get("language_concept_id", 4180186)),
            })

            if len(batch) >= batch_size:
                await _insert_synonyms_batch(session, batch)
                count += len(batch)
                logger.info(f"Loaded {count:,} synonyms...")
                batch = []

        # Insert remaining
        if batch:
            await _insert_synonyms_batch(session, batch)
            count += len(batch)

    await session.commit()
    logger.info(f"Loaded {count:,} synonyms total")
    return count


async def _insert_synonyms_batch(session: AsyncSession, batch: list[dict]) -> None:
    """Insert a batch of synonyms."""
    await session.execute(
        text("""
            INSERT INTO concept_synonyms (id, concept_id, concept_synonym_name, language_concept_id)
            VALUES (gen_random_uuid(), :concept_id, :concept_synonym_name, :language_concept_id)
            ON CONFLICT DO NOTHING
        """),
        batch
    )


async def load_vocabulary(
    vocab_path: Path,
    vocabularies: set[str] | None = None,
    domains: set[str] | None = None,
    clear_existing: bool = True,
) -> dict[str, int]:
    """Load OMOP vocabulary from directory.

    Args:
        vocab_path: Path to directory containing CONCEPT.csv and CONCEPT_SYNONYM.csv
        vocabularies: Set of vocabulary_ids to load (None = default set)
        domains: Set of domain_ids to load (None = default set)
        clear_existing: Whether to clear existing data first

    Returns:
        Dictionary with counts of loaded concepts and synonyms
    """
    concept_file = vocab_path / "CONCEPT.csv"
    synonym_file = vocab_path / "CONCEPT_SYNONYM.csv"

    if not concept_file.exists():
        raise FileNotFoundError(f"CONCEPT.csv not found in {vocab_path}")

    # Use defaults if not specified
    if vocabularies is None:
        vocabularies = DEFAULT_VOCABULARIES
    if domains is None:
        domains = DEFAULT_DOMAINS

    async with async_session_maker() as session:
        if clear_existing:
            await clear_vocabulary(session)

        concept_count = await load_concepts(
            session, concept_file, vocabularies, domains
        )

        synonym_count = 0
        if synonym_file.exists():
            synonym_count = await load_synonyms(session, synonym_file)
        else:
            logger.warning("CONCEPT_SYNONYM.csv not found, skipping synonyms")

        # Log summary by domain
        result = await session.execute(text("""
            SELECT domain_id, COUNT(*)
            FROM concepts
            GROUP BY domain_id
            ORDER BY COUNT(*) DESC
        """))
        logger.info("Concepts by domain:")
        for domain, count in result.fetchall():
            logger.info(f"  {domain}: {count:,}")

    return {
        "concepts": concept_count,
        "synonyms": synonym_count,
    }


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Load OMOP vocabulary from Athena CSV files"
    )
    parser.add_argument(
        "--path",
        type=Path,
        required=True,
        help="Path to directory containing CONCEPT.csv and CONCEPT_SYNONYM.csv",
    )
    parser.add_argument(
        "--vocabularies",
        type=str,
        default=None,
        help="Comma-separated list of vocabulary_ids to load (default: SNOMED,RxNorm,LOINC)",
    )
    parser.add_argument(
        "--domains",
        type=str,
        default=None,
        help="Comma-separated list of domain_ids to load (default: Condition,Drug,Measurement,Procedure,Observation,Device)",
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Don't clear existing vocabulary data",
    )

    args = parser.parse_args()

    vocabularies = None
    if args.vocabularies:
        vocabularies = set(v.strip() for v in args.vocabularies.split(","))

    domains = None
    if args.domains:
        domains = set(d.strip() for d in args.domains.split(","))

    try:
        result = await load_vocabulary(
            args.path,
            vocabularies=vocabularies,
            domains=domains,
            clear_existing=not args.no_clear,
        )
        logger.info(f"Load complete: {result['concepts']:,} concepts, {result['synonyms']:,} synonyms")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
