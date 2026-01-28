"""Vocabulary version service for tracking OMOP concept lifecycle changes.

Provides version import, history tracking, and concept retirement/merge
operations with full provenance and audit logging.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vocabulary import Concept, ConceptRelationship, ConceptStatus

logger = logging.getLogger(__name__)


class VocabularyVersionService:
    """Service for managing vocabulary concept versioning."""

    _instance = None

    async def import_version_update(
        self,
        session: AsyncSession,
        vocabulary_id: str,
        version: str,
        concepts_data: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Import a vocabulary version update.

        Inserts new concepts, updates existing ones, and marks deprecated/retired
        concepts with version tracking.
        """
        added = 0
        updated = 0
        deprecated = 0

        for concept_data in concepts_data:
            concept_id = concept_data.get("concept_id")
            status_str = concept_data.get("status", "active")

            # Look up existing concept
            result = await session.execute(
                select(Concept).where(Concept.concept_id == concept_id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing concept
                existing.concept_name = concept_data.get("concept_name", existing.concept_name)
                existing.domain_id = concept_data.get("domain_id", existing.domain_id)
                existing.vocabulary_version = version
                existing.version_date = datetime.now(timezone.utc).date()

                new_status = ConceptStatus(status_str) if status_str in ConceptStatus.__members__ else ConceptStatus.active
                if new_status != existing.status:
                    existing.status = new_status
                    existing.status_changed_at = datetime.now(timezone.utc)
                    if new_status in (ConceptStatus.deprecated, ConceptStatus.retired):
                        deprecated += 1

                updated += 1
            else:
                # Insert new concept
                new_concept = Concept(
                    concept_id=concept_id,
                    concept_name=concept_data.get("concept_name", ""),
                    domain_id=concept_data.get("domain_id", "Unknown"),
                    vocabulary_id=vocabulary_id,
                    concept_class_id=concept_data.get("concept_class_id", "Clinical Finding"),
                    standard_concept=concept_data.get("standard_concept"),
                    vocabulary_version=version,
                    version_date=datetime.now(timezone.utc).date(),
                    status=ConceptStatus.active,
                )
                session.add(new_concept)
                added += 1

        await session.flush()

        return {
            "vocabulary_id": vocabulary_id,
            "version": version,
            "concepts_processed": len(concepts_data),
            "added": added,
            "updated": updated,
            "deprecated": deprecated,
        }

    async def get_version_history(
        self,
        session: AsyncSession,
        concept_id: int,
    ) -> list[dict[str, Any]]:
        """Get version history for a concept."""
        result = await session.execute(
            select(Concept).where(Concept.concept_id == concept_id)
        )
        concept = result.scalar_one_or_none()
        if not concept:
            return []

        history = [{
            "concept_id": concept.concept_id,
            "concept_name": concept.concept_name,
            "vocabulary_version": concept.vocabulary_version,
            "version_date": str(concept.version_date) if concept.version_date else None,
            "status": concept.status.value if concept.status else "active",
            "status_changed_at": concept.status_changed_at.isoformat() if concept.status_changed_at else None,
            "previous_concept_id": concept.previous_concept_id,
        }]

        # Follow previous_concept_id chain
        current = concept
        visited = {concept.concept_id}
        while current.previous_concept_id and current.previous_concept_id not in visited:
            visited.add(current.previous_concept_id)
            prev_result = await session.execute(
                select(Concept).where(Concept.concept_id == current.previous_concept_id)
            )
            prev = prev_result.scalar_one_or_none()
            if not prev:
                break
            history.append({
                "concept_id": prev.concept_id,
                "concept_name": prev.concept_name,
                "vocabulary_version": prev.vocabulary_version,
                "version_date": str(prev.version_date) if prev.version_date else None,
                "status": prev.status.value if prev.status else "active",
                "status_changed_at": prev.status_changed_at.isoformat() if prev.status_changed_at else None,
                "previous_concept_id": prev.previous_concept_id,
            })
            current = prev

        return history

    async def get_current_version(
        self,
        session: AsyncSession,
        vocabulary_id: str,
    ) -> dict[str, Any]:
        """Get the latest version for a vocabulary."""
        result = await session.execute(
            select(Concept.vocabulary_version, Concept.version_date)
            .where(
                Concept.vocabulary_id == vocabulary_id,
                Concept.vocabulary_version.is_not(None),
            )
            .order_by(Concept.version_date.desc())
            .limit(1)
        )
        row = result.first()
        if not row:
            return {
                "vocabulary_id": vocabulary_id,
                "version": None,
                "version_date": None,
            }

        return {
            "vocabulary_id": vocabulary_id,
            "version": row[0],
            "version_date": str(row[1]) if row[1] else None,
        }

    async def apply_retirement(
        self,
        session: AsyncSession,
        concept_id: int,
        replacement_concept_id: int | None = None,
    ) -> dict[str, Any]:
        """Retire a concept, optionally replacing it with another."""
        result = await session.execute(
            select(Concept).where(Concept.concept_id == concept_id)
        )
        concept = result.scalar_one_or_none()
        if not concept:
            return {"error": "Concept not found"}

        concept.status = ConceptStatus.retired
        concept.status_changed_at = datetime.now(timezone.utc)

        replaced_nodes = 0
        if replacement_concept_id:
            concept.previous_concept_id = replacement_concept_id

            # Update KG nodes that reference this concept
            try:
                from app.models.knowledge_graph import KGNode
                kg_result = await session.execute(
                    select(KGNode).where(KGNode.omop_concept_id == concept_id)
                )
                for node in kg_result.scalars().all():
                    node.omop_concept_id = replacement_concept_id
                    replaced_nodes += 1
            except Exception:
                logger.warning("Could not update KG nodes for retired concept %d", concept_id)

        # Create provenance record for the retirement
        try:
            from app.services.provenance_db_service import get_provenance_db_service
            prov_service = get_provenance_db_service()
            await prov_service.create_provenance_record(
                session=session,
                entity_type="concept",
                entity_id=str(concept_id),
                extraction_method="manual",
                confidence_level="high",
                confidence_score=1.0,
                extracted_text=f"Concept {concept_id} retired"
                    + (f", replaced by {replacement_concept_id}" if replacement_concept_id else ""),
                metadata={
                    "action": "retirement",
                    "replacement_concept_id": replacement_concept_id,
                    "kg_nodes_updated": replaced_nodes,
                },
            )
        except Exception:
            logger.debug("Could not create provenance record for concept retirement")

        await session.flush()

        return {
            "concept_id": concept_id,
            "status": "retired",
            "replacement_concept_id": replacement_concept_id,
            "kg_nodes_updated": replaced_nodes,
        }

    async def apply_merge(
        self,
        session: AsyncSession,
        old_concept_ids: list[int],
        new_concept_id: int,
    ) -> dict[str, Any]:
        """Merge multiple concepts into one."""
        merged_count = 0
        total_kg_updates = 0

        for old_id in old_concept_ids:
            result = await session.execute(
                select(Concept).where(Concept.concept_id == old_id)
            )
            old_concept = result.scalar_one_or_none()
            if not old_concept:
                continue

            old_concept.status = ConceptStatus.merged
            old_concept.status_changed_at = datetime.now(timezone.utc)
            old_concept.previous_concept_id = new_concept_id

            # Update KG nodes
            try:
                from app.models.knowledge_graph import KGNode
                kg_result = await session.execute(
                    select(KGNode).where(KGNode.omop_concept_id == old_id)
                )
                for node in kg_result.scalars().all():
                    node.omop_concept_id = new_concept_id
                    total_kg_updates += 1
            except Exception:
                logger.warning("Could not update KG nodes for merged concept %d", old_id)

            merged_count += 1

        await session.flush()

        return {
            "new_concept_id": new_concept_id,
            "merged_concept_ids": old_concept_ids,
            "merged_count": merged_count,
            "kg_nodes_updated": total_kg_updates,
        }


_service_instance: VocabularyVersionService | None = None


def get_vocabulary_version_service() -> VocabularyVersionService:
    """Get or create the singleton VocabularyVersionService."""
    global _service_instance
    if _service_instance is None:
        _service_instance = VocabularyVersionService()
    return _service_instance
