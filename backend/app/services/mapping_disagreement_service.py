"""Mapping Disagreement Service.

P2-011: Tracks and reports disagreements between rule-based, ML,
and ensemble concept mapping results for quality review.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DisagreementRecord:
    """A single mapping disagreement between pipelines."""

    mention_text: str
    rule_result: str | None
    ml_result: str | None
    ensemble_result: str | None
    agreement: bool
    entity_type: str = ""


@dataclass
class DisagreementSummary:
    """Aggregate disagreement statistics."""

    total_mappings: int
    agreement_rate: float
    top_disagreements: list[DisagreementRecord] = field(default_factory=list)


class MappingDisagreementService:
    """Service for tracking and querying concept mapping disagreements.

    Maintains an in-memory store of disagreement records that can be
    populated during pipeline execution and queried by the dashboard.
    """

    def __init__(self) -> None:
        self._records: list[DisagreementRecord] = []

    def add_record(self, record: DisagreementRecord) -> None:
        """Add a disagreement record.

        Args:
            record: The disagreement record to store.
        """
        self._records.append(record)

    def add_mapping_result(
        self,
        mention_text: str,
        rule_result: str | None,
        ml_result: str | None,
        ensemble_result: str | None,
        entity_type: str = "",
    ) -> DisagreementRecord:
        """Record a mapping result from all three pipelines.

        Automatically determines agreement based on whether rule and ML
        results match. The ensemble result is tracked for reference.

        Args:
            mention_text: The original mention text.
            rule_result: Concept name from rule-based mapper (None if unmapped).
            ml_result: Concept name from ML mapper (None if unmapped).
            ensemble_result: Concept name from ensemble (None if unmapped).
            entity_type: Entity type (e.g., "condition", "drug").

        Returns:
            The created DisagreementRecord.
        """
        agreement = rule_result == ml_result
        record = DisagreementRecord(
            mention_text=mention_text,
            rule_result=rule_result,
            ml_result=ml_result,
            ensemble_result=ensemble_result,
            agreement=agreement,
            entity_type=entity_type,
        )
        self._records.append(record)
        return record

    def get_disagreement_summary(self) -> DisagreementSummary:
        """Get aggregate disagreement statistics.

        Returns:
            DisagreementSummary with total mappings, agreement rate,
            and the top disagreements (those where agreement=False).
        """
        total = len(self._records)
        if total == 0:
            return DisagreementSummary(
                total_mappings=0,
                agreement_rate=100.0,
                top_disagreements=[],
            )

        agreed = sum(1 for r in self._records if r.agreement)
        agreement_rate = (agreed / total) * 100.0
        disagreements = [r for r in self._records if not r.agreement]

        return DisagreementSummary(
            total_mappings=total,
            agreement_rate=round(agreement_rate, 2),
            top_disagreements=disagreements[:50],
        )

    def get_disagreements_by_type(
        self, entity_type: str
    ) -> list[DisagreementRecord]:
        """Get disagreement records filtered by entity type.

        Args:
            entity_type: Entity type to filter by (e.g., "condition").

        Returns:
            List of DisagreementRecords matching the entity type.
        """
        return [
            r
            for r in self._records
            if r.entity_type == entity_type and not r.agreement
        ]

    def get_all_records(self) -> list[DisagreementRecord]:
        """Return all stored records."""
        return list(self._records)

    def clear(self) -> None:
        """Clear all stored records."""
        self._records.clear()


# Module-level singleton
_service: MappingDisagreementService | None = None


def get_mapping_disagreement_service() -> MappingDisagreementService:
    """Get or create the mapping disagreement service singleton."""
    global _service
    if _service is None:
        _service = MappingDisagreementService()
    return _service


def reset_mapping_disagreement_service() -> None:
    """Reset the singleton (for testing)."""
    global _service
    _service = None
