"""Death Table ETL Service.

This module provides ETL functionality for transforming source death
data into the OMOP CDM Death table.

The Death table stores information about when and how patients died.
Each patient can have at most one death record.

Standard OMOP Death Type Concept IDs:
    32817 - EHR encounter record
    32818 - EHR problem list entry
    32879 - Registry
    32885 - Death certificate
    32886 - Autopsy report

Cause of Death Concept Domains:
    - Condition domain concepts (from ICD-10, SNOMED)
    - Typically ICD-10 underlying cause codes

Usage:
    from app.etl import DeathETL

    etl = DeathETL(db_session)

    death_record = {
        "patient_source_id": "PAT001",
        "death_date": datetime(2024, 6, 15),
        "cause_code": "I25.10",
        "cause_code_system": "ICD10CM",
    }

    death = await etl.transform_and_load(death_record, person_id=1)
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.etl.concept_mappings import (
    CODE_SYSTEM_VOCABULARY_MAP,
    DEATH_TYPE_CONCEPT_MAP,
    DEFAULT_DEATH_TYPE_CONCEPT_ID,
)
from app.models.omop import Death

logger = logging.getLogger(__name__)


# Extended death type mapping for additional categories
DEATH_TYPE_EXTENDED_MAP = {
    **DEATH_TYPE_CONCEPT_MAP,
    "social_security": 32885,
    "ssdi": 32885,  # Social Security Death Index
}


@dataclass
class SourceDeath:
    """Source death record structure.

    Attributes:
        patient_source_id: Source patient identifier.
        death_date: Date of death.
        death_datetime: Optional datetime of death.
        cause_code: Cause of death code (ICD-10, SNOMED).
        cause_code_system: Code system for cause.
        death_type: Type of death record source.
        raw_data: Original source data.
    """

    patient_source_id: str
    death_date: date | datetime
    death_datetime: datetime | None = None
    cause_code: str | None = None
    cause_code_system: str | None = None
    death_type: str | None = None
    raw_data: dict[str, Any] | None = None


@dataclass
class DeathETLConfig:
    """Configuration for Death ETL service."""

    map_cause_to_standard: bool = True
    default_death_type: int = DEFAULT_DEATH_TYPE_CONCEPT_ID


@dataclass
class DeathETLResult:
    """Result of Death ETL operation."""

    total_processed: int = 0
    deaths_created: int = 0
    deaths_updated: int = 0
    deaths_skipped: int = 0
    unmapped_causes: int = 0
    errors: list[str] = field(default_factory=list)


class DeathETL:
    """ETL service for transforming death records to OMOP Death table.

    The Death table has a 1:1 relationship with Person - each person
    can have at most one death record.

    Example:
        etl = DeathETL(session)
        death = await etl.transform_and_load(source_death, person_id=123)
    """

    def __init__(
        self,
        session: AsyncSession,
        config: DeathETLConfig | None = None,
        vocabulary_service: Any | None = None,
    ):
        """Initialize Death ETL service."""
        self.session = session
        self.config = config or DeathETLConfig()
        self.vocabulary_service = vocabulary_service

        self._concept_cache: dict[str, int] = {}

    def _normalize_code_system(self, code_system: str | None) -> str | None:
        """Normalize code system to OMOP vocabulary ID."""
        if not code_system:
            return None
        normalized = code_system.lower().strip()
        return CODE_SYSTEM_VOCABULARY_MAP.get(normalized, code_system)

    async def _lookup_cause_concept_id(
        self,
        code: str,
        code_system: str | None,
    ) -> tuple[int | None, int | None]:
        """Look up OMOP concept ID for cause of death code.

        Returns:
            Tuple of (cause_concept_id, cause_source_concept_id).
        """
        if not code:
            return None, None

        cache_key = f"{code_system}:{code}"

        if cache_key in self._concept_cache:
            concept_id = self._concept_cache[cache_key]
            return concept_id, concept_id

        if self.vocabulary_service and self.config.map_cause_to_standard:
            try:
                vocab_id = self._normalize_code_system(code_system)
                if vocab_id:
                    result = self.vocabulary_service.search_concepts(
                        search_term=code,
                        vocabulary_ids=[vocab_id],
                        exact_match=True,
                    )
                    if result and len(result) > 0:
                        concept_id = result[0].concept_id
                        self._concept_cache[cache_key] = concept_id
                        return concept_id, concept_id
            except Exception as e:
                logger.debug(f"Concept lookup failed for cause {code}: {e}")

        return None, None

    def _determine_death_type(self, death_type: str | None) -> int:
        """Determine death type concept ID."""
        if death_type:
            dtype = death_type.lower().strip()
            concept_id = DEATH_TYPE_EXTENDED_MAP.get(dtype)
            if concept_id:
                return concept_id

        return self.config.default_death_type

    def _normalize_dates(
        self,
        source_death: SourceDeath,
    ) -> tuple[date, datetime | None]:
        """Normalize death date and datetime."""
        death_date: date
        death_datetime: datetime | None = None

        if isinstance(source_death.death_date, datetime):
            death_date = source_death.death_date.date()
            death_datetime = source_death.death_date
        else:
            death_date = source_death.death_date

        # Use explicit datetime if provided
        if source_death.death_datetime:
            death_datetime = source_death.death_datetime

        return death_date, death_datetime

    async def _find_existing_death(self, person_id: int) -> Death | None:
        """Find existing Death record for a person.

        Death table has 1:1 relationship with Person.
        """
        stmt = select(Death).where(Death.person_id == person_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def transform(
        self,
        source_death: SourceDeath,
        person_id: int,
    ) -> dict[str, Any]:
        """Transform source death record to Death attributes."""
        # Map cause of death
        cause_concept_id, cause_source_concept_id = await self._lookup_cause_concept_id(
            source_death.cause_code or "",
            source_death.cause_code_system,
        )

        # Determine death type
        death_type_concept_id = self._determine_death_type(source_death.death_type)

        # Normalize dates
        death_date, death_datetime = self._normalize_dates(source_death)

        # Build cause source value
        cause_source_value = source_death.cause_code
        if source_death.cause_code_system and source_death.cause_code:
            cause_source_value = f"{source_death.cause_code_system}:{source_death.cause_code}"

        return {
            "person_id": person_id,
            "death_date": death_date,
            "death_datetime": death_datetime,
            "death_type_concept_id": death_type_concept_id,
            "cause_concept_id": cause_concept_id,
            "cause_source_value": cause_source_value[:50] if cause_source_value else None,
            "cause_source_concept_id": cause_source_concept_id,
        }

    async def transform_and_load(
        self,
        source_death: SourceDeath,
        person_id: int,
    ) -> Death:
        """Transform and load a death record.

        Note: Death table allows only one record per person.
        If a death record exists, it will be updated.

        Args:
            source_death: Source death record.
            person_id: OMOP person_id.

        Returns:
            Created or updated Death record.
        """
        existing = await self._find_existing_death(person_id)

        death_data = await self.transform(source_death, person_id)

        if existing:
            # Update existing record
            for key, value in death_data.items():
                if value is not None:
                    setattr(existing, key, value)
            await self.session.flush()
            return existing

        # Create new record
        death = Death(**death_data)
        self.session.add(death)
        await self.session.flush()

        return death

    async def transform_and_load_batch(
        self,
        deaths: list[tuple[SourceDeath, int]],  # (source_death, person_id) pairs
    ) -> DeathETLResult:
        """Transform and load a batch of death records."""
        result = DeathETLResult()

        for source_death, person_id in deaths:
            result.total_processed += 1

            try:
                existing = await self._find_existing_death(person_id)

                death = await self.transform_and_load(source_death, person_id)

                if existing:
                    result.deaths_updated += 1
                else:
                    result.deaths_created += 1

                if death.cause_concept_id is None and source_death.cause_code:
                    result.unmapped_causes += 1

            except Exception as e:
                result.errors.append(f"Error processing death for person {person_id}: {e}")
                logger.warning(f"ETL error for death record: {e}")

        await self.session.commit()

        return result

    def get_stats(self) -> dict[str, Any]:
        """Get ETL service statistics."""
        return {
            "cached_concepts": len(self._concept_cache),
        }
