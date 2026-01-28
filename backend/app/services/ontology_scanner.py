"""Ontology update scanner for detecting available vocabulary updates.

Compares current vocabulary versions against a metadata table to identify
vocabularies that have newer versions available.
"""

import logging
from typing import Any

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vocabulary import Concept, ConceptStatus

logger = logging.getLogger(__name__)

# Known vocabulary metadata (in a production system this would come from
# a metadata table or external API like UMLS/Athena).
VOCABULARY_METADATA: dict[str, dict[str, Any]] = {
    "SNOMED": {
        "name": "SNOMED CT",
        "latest_version": "2026-01",
        "release_url": "https://www.nlm.nih.gov/healthit/snomedct/",
        "update_frequency": "biannual",
    },
    "ICD10CM": {
        "name": "ICD-10-CM",
        "latest_version": "2026",
        "release_url": "https://www.cms.gov/medicare/coding",
        "update_frequency": "annual",
    },
    "RxNorm": {
        "name": "RxNorm",
        "latest_version": "2026-01-06",
        "release_url": "https://www.nlm.nih.gov/research/umls/rxnorm/",
        "update_frequency": "monthly",
    },
    "LOINC": {
        "name": "LOINC",
        "latest_version": "2.78",
        "release_url": "https://loinc.org/downloads/",
        "update_frequency": "biannual",
    },
    "CPT4": {
        "name": "CPT-4",
        "latest_version": "2026",
        "release_url": "https://www.ama-assn.org/practice-management/cpt",
        "update_frequency": "annual",
    },
}


async def scan_for_updates(
    session: AsyncSession,
    vocabulary_id: str,
) -> dict[str, Any]:
    """Scan a single vocabulary for available updates.

    Compares current version in the database against known latest version.
    """
    # Get current version from database
    result = await session.execute(
        select(
            Concept.vocabulary_version,
            func.count(Concept.id).label("concept_count"),
        )
        .where(Concept.vocabulary_id == vocabulary_id)
        .group_by(Concept.vocabulary_version)
        .order_by(Concept.vocabulary_version.desc())
    )
    rows = result.all()

    current_version = rows[0][0] if rows else None
    total_concepts = sum(r[1] for r in rows)

    # Check concept statuses
    status_result = await session.execute(
        select(
            Concept.status,
            func.count(Concept.id),
        )
        .where(Concept.vocabulary_id == vocabulary_id)
        .group_by(Concept.status)
    )
    status_counts = {row[0].value if hasattr(row[0], "value") else str(row[0]): row[1] for row in status_result.all()}

    metadata = VOCABULARY_METADATA.get(vocabulary_id, {})
    latest_version = metadata.get("latest_version")

    update_available = False
    if current_version and latest_version:
        update_available = current_version != latest_version

    return {
        "vocabulary_id": vocabulary_id,
        "vocabulary_name": metadata.get("name", vocabulary_id),
        "current_version": current_version,
        "latest_version": latest_version,
        "update_available": update_available,
        "total_concepts": total_concepts,
        "status_breakdown": status_counts,
        "version_count": len(rows),
        "update_frequency": metadata.get("update_frequency"),
        "release_url": metadata.get("release_url"),
    }


async def check_all_vocabularies(
    session: AsyncSession,
) -> dict[str, Any]:
    """Check update status for all configured vocabularies in the database."""
    # Get distinct vocabulary IDs
    result = await session.execute(
        select(distinct(Concept.vocabulary_id))
    )
    vocab_ids = [row[0] for row in result.all()]

    results = []
    updates_available = 0
    for vocab_id in vocab_ids:
        scan = await scan_for_updates(session, vocab_id)
        results.append(scan)
        if scan["update_available"]:
            updates_available += 1

    return {
        "vocabularies": results,
        "total_vocabularies": len(results),
        "updates_available": updates_available,
        "scan_timestamp": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
    }
