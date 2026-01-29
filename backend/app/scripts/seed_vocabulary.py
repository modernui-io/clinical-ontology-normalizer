"""Seed script for loading OMOP vocabulary fixture into database.

Usage:
    python -m app.scripts.seed_vocabulary              # Load basic vocabulary (34 concepts)
    python -m app.scripts.seed_vocabulary --expanded   # Load expanded vocabulary (246 concepts)

This script loads the OMOP concept vocabulary subset from fixtures/omop_vocabulary.json
or the expanded vocabulary from fixtures/omop_vocabulary_expanded.json into the database
for local development and testing.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker, engine
from app.models import Concept, ConceptSynonym

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Path to vocabulary fixtures
# In Docker container, fixtures are at /app/fixtures/
# In local development, they're at backend/../fixtures/
_SCRIPT_DIR = Path(__file__).parent
_BACKEND_DIR = _SCRIPT_DIR.parent.parent  # app/scripts -> app -> backend root
FIXTURES_DIR = _BACKEND_DIR / "fixtures"
# Fallback to project root fixtures if not in backend
if not FIXTURES_DIR.exists():
    FIXTURES_DIR = _BACKEND_DIR.parent / "fixtures"

# Vocabulary file paths
VOCABULARY_FILE = FIXTURES_DIR / "omop_vocabulary.json"
VOCABULARY_FILE_EXPANDED = FIXTURES_DIR / "omop_vocabulary_expanded.json"


async def load_vocabulary_fixture(expanded: bool = False) -> dict[str, Any]:
    """Load vocabulary data from JSON fixture file.

    Args:
        expanded: If True, load the expanded vocabulary (~246 concepts).
                 If False, load the basic vocabulary (~34 concepts).
    """
    vocab_file = VOCABULARY_FILE_EXPANDED if expanded else VOCABULARY_FILE
    if not vocab_file.exists():
        raise FileNotFoundError(f"Vocabulary fixture not found: {vocab_file}")

    logger.info(f"Loading vocabulary from: {vocab_file}")
    with open(vocab_file) as f:
        data: dict[str, Any] = json.load(f)
        return data


async def clear_vocabulary(session: AsyncSession) -> None:
    """Clear existing vocabulary data."""
    # Delete synonyms first (foreign key constraint)
    await session.execute(ConceptSynonym.__table__.delete())
    # Then delete concepts
    await session.execute(Concept.__table__.delete())
    await session.commit()
    logger.info("Cleared existing vocabulary data")


async def seed_concepts(session: AsyncSession, concepts_data: list[dict]) -> dict[int, Concept]:
    """Seed concepts into database.

    Returns:
        Mapping of concept_id to Concept objects for synonym linking.
    """
    concept_map: dict[int, Concept] = {}

    for concept_data in concepts_data:
        concept = Concept(
            concept_id=concept_data["concept_id"],
            concept_name=concept_data["concept_name"],
            domain_id=concept_data["domain_id"],
            vocabulary_id=concept_data["vocabulary_id"],
            concept_class_id=concept_data["concept_class_id"],
            standard_concept=concept_data.get("standard_concept"),
        )
        session.add(concept)
        concept_map[concept_data["concept_id"]] = concept

    await session.commit()
    logger.info(f"Seeded {len(concepts_data)} concepts")

    return concept_map


async def seed_synonyms(
    session: AsyncSession,
    concepts_data: list[dict],
) -> int:
    """Seed concept synonyms into database.

    Synonyms are extracted from the 'synonyms' field of each concept.

    Returns:
        Total number of synonyms seeded.
    """
    synonym_count = 0

    for concept_data in concepts_data:
        concept_id = concept_data["concept_id"]
        synonyms = concept_data.get("synonyms", [])

        for synonym_name in synonyms:
            synonym = ConceptSynonym(
                concept_id=concept_id,
                concept_synonym_name=synonym_name.lower(),  # Normalize to lowercase
                language_concept_id=4180186,  # English
            )
            session.add(synonym)
            synonym_count += 1

    await session.commit()
    logger.info(f"Seeded {synonym_count} concept synonyms")

    return synonym_count


async def verify_seed(session: AsyncSession) -> None:
    """Verify that seeding was successful by querying the database."""
    # Count concepts
    result = await session.execute(select(Concept))
    concepts = result.scalars().all()

    # Count synonyms
    result = await session.execute(select(ConceptSynonym))
    synonyms = result.scalars().all()

    logger.info(f"Verification: {len(concepts)} concepts, {len(synonyms)} synonyms in database")

    # Show sample data by domain
    domains: dict[str, list[str]] = {}
    for concept in concepts:
        domain = concept.domain_id
        if domain not in domains:
            domains[domain] = []
        domains[domain].append(concept.concept_name)

    logger.info("Concepts by domain:")
    for domain, names in sorted(domains.items()):
        logger.info(f"  {domain}: {len(names)} concepts")


async def seed_vocabulary(clear_existing: bool = True, expanded: bool = False) -> None:
    """Main function to seed vocabulary data.

    Args:
        clear_existing: If True, clear existing vocabulary data before seeding.
        expanded: If True, load the expanded vocabulary (~246 concepts).
    """
    logger.info(f"Starting vocabulary seed ({'expanded' if expanded else 'basic'})...")

    # Load fixture data
    vocabulary_data = await load_vocabulary_fixture(expanded=expanded)
    concepts_data = vocabulary_data.get("concepts", [])

    if not concepts_data:
        logger.warning("No concepts found in vocabulary fixture")
        return

    async with async_session_maker() as session:
        if clear_existing:
            await clear_vocabulary(session)

        # Seed concepts
        await seed_concepts(session, concepts_data)

        # Seed synonyms
        await seed_synonyms(session, concepts_data)

        # Verify
        await verify_seed(session)

    logger.info("Vocabulary seed completed successfully!")


async def main() -> None:
    """Entry point for running seed script."""
    parser = argparse.ArgumentParser(
        description="Seed OMOP vocabulary into database"
    )
    parser.add_argument(
        "--expanded",
        action="store_true",
        help="Load expanded vocabulary (~246 concepts) instead of basic (~34 concepts)",
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Don't clear existing vocabulary data before seeding",
    )
    args = parser.parse_args()

    try:
        await seed_vocabulary(
            clear_existing=not args.no_clear,
            expanded=args.expanded,
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
