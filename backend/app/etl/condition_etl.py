"""Condition Occurrence Table ETL Service.

This module provides ETL functionality for transforming source condition/diagnosis
data into the OMOP CDM Condition_Occurrence table.

The service handles:
    - ICD-9/ICD-10 to SNOMED CT concept mapping
    - Condition status mapping (active, resolved, etc.)
    - Date normalization
    - Source code preservation

Standard OMOP Condition Type Concept IDs:
    32817 - EHR encounter diagnosis
    32818 - EHR problem list entry
    32819 - EHR order entry
    32821 - EHR administration record
    32840 - Claim diagnosis
    32879 - Registry

Condition Status Concept IDs:
    32893 - Resolved
    32895 - Inactive
    32902 - Preliminary
    32904 - Active
    32906 - Final

Usage:
    from app.etl import ConditionETL
    from app.connectors import SourceCondition, ConditionStatus

    etl = ConditionETL(db_session, vocabulary_service)

    condition = SourceCondition(
        source_id="DX001",
        patient_source_id="PAT001",
        condition_code="E11.9",
        condition_code_system="ICD10CM",
        condition_name="Type 2 diabetes mellitus",
        onset_date=datetime(2024, 1, 15),
        status=ConditionStatus.ACTIVE
    )

    condition_occ = await etl.transform_and_load(condition, person_id=1)
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import ConditionStatus, SourceCondition
from app.etl.concept_mappings import (
    CODE_SYSTEM_VOCABULARY_MAP,
    CONDITION_STATUS_CONCEPT_MAP,
    CONDITION_TYPE_CONCEPT_MAP,
    DEFAULT_CONDITION_TYPE_CONCEPT_ID,
)
from app.models.omop import ConditionOccurrence

logger = logging.getLogger(__name__)


# Local status map using ConditionStatus enum as keys
# Maps to the string-keyed CONDITION_STATUS_CONCEPT_MAP from concept_mappings
CONDITION_STATUS_ENUM_MAP = {
    ConditionStatus.ACTIVE: 32902,  # Active
    ConditionStatus.INACTIVE: 32904,  # Inactive
    ConditionStatus.RESOLVED: 32906,  # Resolved
    ConditionStatus.UNKNOWN: None,
}


@dataclass
class ConditionETLConfig:
    """Configuration for Condition ETL service.

    Attributes:
        map_to_standard: Whether to map source codes to standard concepts.
        preserve_source_codes: Store original codes in source_value.
        default_condition_type: Default condition type concept ID.
        batch_size: Number of records to commit in a batch.
        vocabulary_service: Optional vocabulary service for concept lookup.
    """

    map_to_standard: bool = True
    preserve_source_codes: bool = True
    default_condition_type: int = DEFAULT_CONDITION_TYPE_CONCEPT_ID
    batch_size: int = 1000


@dataclass
class ConditionETLResult:
    """Result of Condition ETL operation.

    Attributes:
        total_processed: Total source conditions processed.
        conditions_created: Number of new records created.
        conditions_updated: Number of existing records updated.
        conditions_skipped: Number skipped.
        unmapped_codes: Number of codes that couldn't be mapped.
        errors: List of error messages.
    """

    total_processed: int = 0
    conditions_created: int = 0
    conditions_updated: int = 0
    conditions_skipped: int = 0
    unmapped_codes: int = 0
    errors: list[str] = field(default_factory=list)


class ConditionETL:
    """ETL service for transforming SourceCondition to OMOP ConditionOccurrence.

    Handles concept mapping, status conversion, and date normalization
    for condition/diagnosis data.

    Example:
        etl = ConditionETL(session)
        condition_occ = await etl.transform_and_load(source_condition, person_id=123)
    """

    def __init__(
        self,
        session: AsyncSession,
        config: ConditionETLConfig | None = None,
        vocabulary_service: Any | None = None,
    ):
        """Initialize Condition ETL service.

        Args:
            session: SQLAlchemy async session.
            config: Optional ETL configuration.
            vocabulary_service: Optional vocabulary service for mapping.
        """
        self.session = session
        self.config = config or ConditionETLConfig()
        self.vocabulary_service = vocabulary_service

        # Cache for source_id to condition_occurrence_id
        self._source_cache: dict[str, int] = {}

        # Cache for code to concept_id mapping
        self._concept_cache: dict[str, int] = {}

    def _normalize_code_system(self, code_system: str | None) -> str | None:
        """Normalize code system name to OMOP vocabulary ID.

        Args:
            code_system: Source code system name or OID.

        Returns:
            OMOP vocabulary ID or None.
        """
        if not code_system:
            return None

        normalized = code_system.lower().strip()
        return CODE_SYSTEM_VOCABULARY_MAP.get(normalized, code_system)

    async def _lookup_concept_id(
        self,
        code: str,
        code_system: str | None,
    ) -> tuple[int, int | None]:
        """Look up OMOP concept ID for a condition code.

        Args:
            code: Condition code (e.g., "E11.9").
            code_system: Code system (e.g., "ICD10CM").

        Returns:
            Tuple of (condition_concept_id, condition_source_concept_id).
        """
        cache_key = f"{code_system}:{code}"

        if cache_key in self._concept_cache:
            concept_id = self._concept_cache[cache_key]
            return concept_id, concept_id

        # Try vocabulary service if available
        if self.vocabulary_service and self.config.map_to_standard:
            try:
                # First get source concept
                source_concept = await self._find_source_concept(code, code_system)
                source_concept_id = source_concept if source_concept else None

                # Then get standard concept via mapping
                standard_concept = await self._find_standard_concept(code, code_system)

                if standard_concept:
                    self._concept_cache[cache_key] = standard_concept
                    return standard_concept, source_concept_id

            except Exception as e:
                logger.debug(f"Concept lookup failed for {code}: {e}")

        # Return 0 (unmapped) if no mapping found
        return 0, None

    async def _find_source_concept(
        self,
        code: str,
        code_system: str | None,
    ) -> int | None:
        """Find source concept ID for a code.

        Args:
            code: Condition code.
            code_system: Code system.

        Returns:
            Source concept ID or None.
        """
        if not self.vocabulary_service:
            return None

        vocab_id = self._normalize_code_system(code_system)
        if not vocab_id:
            return None

        # Query vocabulary service for exact code match
        try:
            result = self.vocabulary_service.search_concepts(
                search_term=code,
                vocabulary_ids=[vocab_id],
                exact_match=True,
            )
            if result and len(result) > 0:
                return result[0].concept_id
        except Exception:
            pass

        return None

    async def _find_standard_concept(
        self,
        code: str,
        code_system: str | None,
    ) -> int | None:
        """Find standard (SNOMED) concept ID for a source code.

        Args:
            code: Source condition code.
            code_system: Source code system.

        Returns:
            Standard concept ID or None.
        """
        if not self.vocabulary_service:
            return None

        vocab_id = self._normalize_code_system(code_system)
        if not vocab_id:
            return None

        # Try to get mapped standard concept
        try:
            # This would use vocabulary_mapping service in a real implementation
            result = self.vocabulary_service.get_standard_concept(
                source_code=code,
                source_vocabulary=vocab_id,
            )
            if result:
                return result.concept_id
        except Exception:
            pass

        return None

    def _map_condition_status(
        self,
        condition: SourceCondition,
    ) -> int | None:
        """Map condition status to OMOP concept ID.

        Args:
            condition: Source condition record.

        Returns:
            Status concept ID or None.
        """
        if condition.status:
            return CONDITION_STATUS_ENUM_MAP.get(condition.status)
        return None

    def _normalize_dates(
        self,
        condition: SourceCondition,
    ) -> tuple[date, datetime | None, date | None, datetime | None]:
        """Normalize condition dates.

        Args:
            condition: Source condition record.

        Returns:
            Tuple of (start_date, start_datetime, end_date, end_datetime).
        """
        # Start date
        start_date: date
        start_datetime: datetime | None = None

        if condition.onset_date:
            if isinstance(condition.onset_date, datetime):
                start_date = condition.onset_date.date()
                start_datetime = condition.onset_date
            else:
                start_date = condition.onset_date
        else:
            start_date = date.today()

        # End date (resolution)
        end_date: date | None = None
        end_datetime: datetime | None = None

        if condition.resolution_date:
            if isinstance(condition.resolution_date, datetime):
                end_date = condition.resolution_date.date()
                end_datetime = condition.resolution_date
            else:
                end_date = condition.resolution_date

        return start_date, start_datetime, end_date, end_datetime

    async def _find_existing_condition(
        self,
        source_id: str,
    ) -> ConditionOccurrence | None:
        """Find existing ConditionOccurrence by source ID.

        Args:
            source_id: Source condition identifier.

        Returns:
            Existing ConditionOccurrence or None.
        """
        if source_id in self._source_cache:
            stmt = select(ConditionOccurrence).where(
                ConditionOccurrence.condition_occurrence_id == self._source_cache[source_id]
            )
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        stmt = select(ConditionOccurrence).where(
            ConditionOccurrence.condition_source_value == source_id
        )
        result = await self.session.execute(stmt)
        condition = result.scalar_one_or_none()

        if condition:
            self._source_cache[source_id] = condition.condition_occurrence_id

        return condition

    async def transform(
        self,
        condition: SourceCondition,
        person_id: int,
        visit_occurrence_id: int | None = None,
        provider_id: int | None = None,
    ) -> dict[str, Any]:
        """Transform SourceCondition to ConditionOccurrence attributes.

        Args:
            condition: Source condition record.
            person_id: OMOP person_id (required).
            visit_occurrence_id: Optional visit link.
            provider_id: Optional provider link.

        Returns:
            Dictionary of ConditionOccurrence attributes.
        """
        # Map concepts
        concept_id, source_concept_id = await self._lookup_concept_id(
            condition.condition_code or "",
            condition.condition_code_system,
        )

        # Map status
        status_concept_id = self._map_condition_status(condition)

        # Normalize dates
        start_date, start_datetime, end_date, end_datetime = self._normalize_dates(condition)

        # Build source value (preserve original code)
        source_value = condition.condition_code
        if condition.condition_code_system:
            source_value = f"{condition.condition_code_system}:{condition.condition_code}"

        return {
            "person_id": person_id,
            "condition_concept_id": concept_id,
            "condition_start_date": start_date,
            "condition_start_datetime": start_datetime,
            "condition_end_date": end_date,
            "condition_end_datetime": end_datetime,
            "condition_type_concept_id": self.config.default_condition_type,
            "condition_status_concept_id": status_concept_id,
            "stop_reason": None,
            "provider_id": provider_id,
            "visit_occurrence_id": visit_occurrence_id,
            "visit_detail_id": None,
            "condition_source_value": source_value[:50] if source_value else None,
            "condition_source_concept_id": source_concept_id,
            "condition_status_source_value": condition.status.value if condition.status else None,
        }

    async def transform_and_load(
        self,
        condition: SourceCondition,
        person_id: int,
        visit_occurrence_id: int | None = None,
        provider_id: int | None = None,
    ) -> ConditionOccurrence:
        """Transform and load a single condition to OMOP ConditionOccurrence.

        Args:
            condition: Source condition record.
            person_id: OMOP person_id (required).
            visit_occurrence_id: Optional visit link.
            provider_id: Optional provider link.

        Returns:
            Created or updated ConditionOccurrence record.

        Raises:
            ValueError: If condition has no source_id.
        """
        if not condition.source_id:
            raise ValueError("Condition must have a source_id")

        # Check for existing
        existing = await self._find_existing_condition(condition.source_id)

        # Transform
        condition_data = await self.transform(
            condition, person_id, visit_occurrence_id, provider_id
        )

        if existing:
            for key, value in condition_data.items():
                if value is not None:
                    setattr(existing, key, value)
            await self.session.flush()
            return existing

        # Create new record
        condition_occ = ConditionOccurrence(**condition_data)
        self.session.add(condition_occ)
        await self.session.flush()

        self._source_cache[condition.source_id] = condition_occ.condition_occurrence_id

        return condition_occ

    async def transform_and_load_batch(
        self,
        conditions: list[tuple[SourceCondition, int, int | None]],
    ) -> ConditionETLResult:
        """Transform and load a batch of conditions.

        Args:
            conditions: List of (SourceCondition, person_id, visit_occurrence_id) tuples.

        Returns:
            ETL result with statistics.
        """
        result = ConditionETLResult()

        for condition, person_id, visit_id in conditions:
            result.total_processed += 1

            try:
                existing = await self._find_existing_condition(condition.source_id) if condition.source_id else None

                condition_occ = await self.transform_and_load(
                    condition, person_id, visit_id
                )

                if existing:
                    result.conditions_updated += 1
                else:
                    result.conditions_created += 1

                # Track unmapped
                if condition_occ.condition_concept_id == 0:
                    result.unmapped_codes += 1

                if result.total_processed % self.config.batch_size == 0:
                    await self.session.commit()

            except Exception as e:
                result.errors.append(f"Error processing {condition.source_id}: {e}")
                logger.warning(f"ETL error for condition {condition.source_id}: {e}")

        await self.session.commit()

        return result

    def get_stats(self) -> dict[str, Any]:
        """Get ETL service statistics."""
        return {
            "cached_mappings": len(self._source_cache),
            "cached_concepts": len(self._concept_cache),
        }
