"""Generate embeddings for OMOP concepts for semantic search.

This script pre-computes embeddings for concepts in the database,
enabling fast semantic similarity search without runtime embedding.

Usage:
    # Generate embeddings for all concepts without embeddings
    python -m app.scripts.generate_concept_embeddings

    # Limit to specific domains
    python -m app.scripts.generate_concept_embeddings --domains Condition Drug

    # Limit to specific vocabularies
    python -m app.scripts.generate_concept_embeddings --vocabularies SNOMED RxNorm

    # Process specific batch size
    python -m app.scripts.generate_concept_embeddings --batch-size 100

    # Limit total concepts
    python -m app.scripts.generate_concept_embeddings --max-concepts 50000
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from typing import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.database import get_sync_engine
from app.models.vocabulary import Concept
from app.services.embedding_service import EmbeddingService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_BATCH_SIZE = 128
DEFAULT_MAX_CONCEPTS = 100_000

# Priority domains for embedding generation
PRIORITY_DOMAINS = ["Condition", "Drug", "Measurement", "Procedure"]


def count_concepts_without_embeddings(
    session: Session,
    domains: Sequence[str] | None = None,
    vocabularies: Sequence[str] | None = None,
) -> int:
    """Count concepts that need embeddings generated."""
    stmt = select(func.count()).select_from(Concept).where(Concept.embedding.is_(None))

    if domains:
        stmt = stmt.where(Concept.domain_id.in_(domains))
    if vocabularies:
        stmt = stmt.where(Concept.vocabulary_id.in_(vocabularies))

    result = session.execute(stmt)
    return result.scalar() or 0


def get_concepts_batch(
    session: Session,
    offset: int,
    batch_size: int,
    domains: Sequence[str] | None = None,
    vocabularies: Sequence[str] | None = None,
) -> list[Concept]:
    """Get a batch of concepts without embeddings."""
    stmt = (
        select(Concept)
        .where(Concept.embedding.is_(None))
    )

    if domains:
        stmt = stmt.where(Concept.domain_id.in_(domains))
    if vocabularies:
        stmt = stmt.where(Concept.vocabulary_id.in_(vocabularies))

    # Order by domain priority, then by concept_id for consistency
    stmt = (
        stmt
        .order_by(Concept.domain_id, Concept.concept_id)
        .offset(offset)
        .limit(batch_size)
    )

    result = session.execute(stmt)
    return list(result.scalars().all())


def generate_embeddings(
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_concepts: int = DEFAULT_MAX_CONCEPTS,
    domains: Sequence[str] | None = None,
    vocabularies: Sequence[str] | None = None,
) -> int:
    """Generate embeddings for concepts in the database.

    Args:
        batch_size: Number of concepts to process at once.
        max_concepts: Maximum total concepts to process.
        domains: Optional list of domains to filter.
        vocabularies: Optional list of vocabularies to filter.

    Returns:
        Number of concepts updated with embeddings.
    """
    logger.info("Initializing embedding service...")
    embedding_service = EmbeddingService()

    # Force model initialization
    _ = embedding_service.encode("test")
    logger.info("Embedding model loaded successfully")

    engine = get_sync_engine()
    total_updated = 0
    start_time = time.time()

    with Session(engine) as session:
        # Count total concepts needing embeddings
        total_without = count_concepts_without_embeddings(session, domains, vocabularies)
        logger.info(f"Found {total_without} concepts without embeddings")

        if total_without == 0:
            logger.info("All concepts already have embeddings")
            return 0

        # Limit to max_concepts
        to_process = min(total_without, max_concepts)
        logger.info(f"Will process {to_process} concepts (max={max_concepts})")

        offset = 0
        batch_num = 0

        while total_updated < to_process:
            batch_start = time.time()

            # Get batch of concepts
            concepts = get_concepts_batch(
                session, offset, batch_size, domains, vocabularies
            )

            if not concepts:
                break

            # Generate embeddings for concept names
            texts = [c.concept_name for c in concepts]
            embeddings = embedding_service.encode_batch(texts, batch_size=batch_size)

            # Update concepts with embeddings
            for concept, embedding in zip(concepts, embeddings):
                concept.embedding = embedding
                total_updated += 1

            session.commit()

            batch_time = time.time() - batch_start
            rate = len(concepts) / batch_time
            elapsed = time.time() - start_time
            eta = (to_process - total_updated) / rate if rate > 0 else 0

            batch_num += 1
            logger.info(
                f"Batch {batch_num}: {total_updated}/{to_process} "
                f"({100 * total_updated / to_process:.1f}%) "
                f"| {rate:.1f} concepts/sec | ETA: {eta / 60:.1f} min"
            )

            offset += batch_size

            # Check if we've hit the limit
            if total_updated >= to_process:
                break

    total_time = time.time() - start_time
    logger.info(
        f"Completed! Generated embeddings for {total_updated} concepts "
        f"in {total_time / 60:.1f} minutes "
        f"({total_updated / total_time:.1f} concepts/sec)"
    )

    return total_updated


def main() -> None:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Generate embeddings for OMOP concepts"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Batch size for embedding generation (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--max-concepts",
        type=int,
        default=DEFAULT_MAX_CONCEPTS,
        help=f"Maximum concepts to process (default: {DEFAULT_MAX_CONCEPTS})",
    )
    parser.add_argument(
        "--domains",
        nargs="+",
        help="Filter to specific domains (e.g., Condition Drug)",
    )
    parser.add_argument(
        "--vocabularies",
        nargs="+",
        help="Filter to specific vocabularies (e.g., SNOMED RxNorm)",
    )
    parser.add_argument(
        "--priority-only",
        action="store_true",
        help="Only process priority domains (Condition, Drug, Measurement, Procedure)",
    )

    args = parser.parse_args()

    domains = args.domains
    if args.priority_only and not domains:
        domains = PRIORITY_DOMAINS
        logger.info(f"Using priority domains: {domains}")

    try:
        updated = generate_embeddings(
            batch_size=args.batch_size,
            max_concepts=args.max_concepts,
            domains=domains,
            vocabularies=args.vocabularies,
        )
        sys.exit(0 if updated >= 0 else 1)
    except Exception as e:
        logger.error(f"Failed to generate embeddings: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
