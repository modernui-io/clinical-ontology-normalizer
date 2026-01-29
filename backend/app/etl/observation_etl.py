"""Observation Table ETL Service.

This module provides ETL functionality for transforming source observation
data (allergies, social history, clinical findings) into the OMOP CDM
Observation table.

The Observation table captures clinical facts that don't fit in other
clinical event tables (conditions, drugs, procedures, measurements).

Common observation types:
    - Allergies and adverse reactions
    - Social history (smoking, alcohol, substance use)
    - Family history
    - Clinical findings (symptoms, signs)
    - Administrative observations

Standard OMOP Observation Type Concept IDs:
    32817 - EHR encounter record
    32818 - EHR problem list entry
    32879 - Registry
    44814721 - Patient reported
    44814722 - Clinician reported

Usage:
    from app.etl import ObservationETL
    from app.connectors import SourceObservation

    etl = ObservationETL(db_session)

    observation = SourceObservation(
        source_id="OBS001",
        patient_source_id="PAT001",
        observation_code="160573003",
        observation_code_system="SNOMED",
        observation_name="Alcohol user",
        observation_type="social_history",
        observation_date=datetime(2024, 1, 15),
        value_text="Occasional"
    )

    obs = await etl.transform_and_load(observation, person_id=1)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import SourceObservation
from app.etl.concept_mappings import (
    CODE_SYSTEM_VOCABULARY_MAP,
    DEFAULT_OBSERVATION_TYPE_CONCEPT_ID,
    OBSERVATION_TYPE_CONCEPT_MAP,
    QUALIFIER_CONCEPT_MAP,
    VALUE_CONCEPT_MAP,
)
from app.models.omop import Observation

logger = logging.getLogger(__name__)


# Extended observation type mapping for additional categories
OBSERVATION_TYPE_EXTENDED_MAP = {
    **OBSERVATION_TYPE_CONCEPT_MAP,
    "problem_list": 32818,
    "clinician_reported": 44814722,
    "allergy": 32817,
    "social_history": 32817,
    "family_history": 32817,
}

# Extended value concept mapping for observation-specific values
VALUE_CONCEPT_EXTENDED_MAP = {
    **VALUE_CONCEPT_MAP,
    # Yes/No - additional mappings
    "true": 4188539,
    "false": 4188540,
    # Smoking status
    "current smoker": 4298794,
    "former smoker": 4310250,
    "never smoker": 4144272,
    "non-smoker": 4144272,
    # Alcohol
    "current drinker": 4041306,
    "former drinker": 4041306,
    "non-drinker": 4144272,
    # Allergy severity
    "mild": 4116186,
    "moderate": 4116186,
    "severe": 4087703,
}

# Extended qualifier concept mapping
QUALIFIER_CONCEPT_EXTENDED_MAP = {
    **QUALIFIER_CONCEPT_MAP,
    "primary": 4030450,
    "secondary": 4030451,
    "confirmed": 4188540,
    "suspected": 4266367,
}


@dataclass
class ObservationETLConfig:
    """Configuration for Observation ETL service."""

    map_to_standard: bool = True
    preserve_source_codes: bool = True
    default_observation_type: int = DEFAULT_OBSERVATION_TYPE_CONCEPT_ID
    batch_size: int = 1000


@dataclass
class ObservationETLResult:
    """Result of Observation ETL operation."""

    total_processed: int = 0
    observations_created: int = 0
    observations_updated: int = 0
    observations_skipped: int = 0
    unmapped_codes: int = 0
    errors: list[str] = field(default_factory=list)


class ObservationETL:
    """ETL service for transforming SourceObservation to OMOP Observation.

    Handles concept mapping for various observation types including
    allergies, social history, and clinical findings.

    Example:
        etl = ObservationETL(session)
        obs = await etl.transform_and_load(source_observation, person_id=123)
    """

    def __init__(
        self,
        session: AsyncSession,
        config: ObservationETLConfig | None = None,
        vocabulary_service: Any | None = None,
    ):
        """Initialize Observation ETL service."""
        self.session = session
        self.config = config or ObservationETLConfig()
        self.vocabulary_service = vocabulary_service

        self._source_cache: dict[str, int] = {}
        self._concept_cache: dict[str, int] = {}

    def _normalize_code_system(self, code_system: str | None) -> str | None:
        """Normalize code system to OMOP vocabulary ID."""
        if not code_system:
            return None
        normalized = code_system.lower().strip()
        return CODE_SYSTEM_VOCABULARY_MAP.get(normalized, code_system)

    async def _lookup_concept_id(
        self,
        code: str,
        code_system: str | None,
    ) -> tuple[int, int | None]:
        """Look up OMOP concept ID for an observation code."""
        cache_key = f"{code_system}:{code}"

        if cache_key in self._concept_cache:
            concept_id = self._concept_cache[cache_key]
            return concept_id, concept_id

        if self.vocabulary_service and self.config.map_to_standard:
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
                logger.debug(f"Concept lookup failed for {code}: {e}")

        return 0, None

    def _parse_value(
        self,
        observation: SourceObservation,
    ) -> tuple[Decimal | None, str | None, int | None]:
        """Parse observation value.

        Returns:
            Tuple of (value_as_number, value_as_string, value_as_concept_id).
        """
        value_as_number: Decimal | None = None
        value_as_string: str | None = None
        value_as_concept_id: int | None = None

        # Try numeric value
        if observation.value_numeric is not None:
            try:
                value_as_number = Decimal(str(observation.value_numeric))
            except (ValueError, TypeError):
                pass

        # Process text value
        if observation.value_text:
            value_as_string = observation.value_text[:60]

            # Try to map to concept
            normalized = observation.value_text.lower().strip()
            value_as_concept_id = VALUE_CONCEPT_EXTENDED_MAP.get(normalized)

        return value_as_number, value_as_string, value_as_concept_id

    def _map_unit_concept(self, unit: str | None) -> int | None:
        """Map unit to OMOP concept ID."""
        # Common units
        unit_map = {
            "%": 8554,
            "pack-years": 8510,
            "years": 9448,
            "days": 8512,
            "months": 9439,
        }
        if not unit:
            return None
        return unit_map.get(unit.lower())

    def _determine_observation_type(
        self,
        observation: SourceObservation,
    ) -> int:
        """Determine observation type concept ID."""
        if observation.observation_type:
            obs_type = observation.observation_type.lower()
            concept_id = OBSERVATION_TYPE_EXTENDED_MAP.get(obs_type)
            if concept_id:
                return concept_id

        return self.config.default_observation_type

    def _normalize_date(
        self,
        observation: SourceObservation,
    ) -> tuple[date, datetime | None]:
        """Normalize observation date."""
        obs_date: date
        obs_datetime: datetime | None = None

        if observation.observation_date:
            if isinstance(observation.observation_date, datetime):
                obs_date = observation.observation_date.date()
                obs_datetime = observation.observation_date
            else:
                obs_date = observation.observation_date
        else:
            obs_date = date.today()

        return obs_date, obs_datetime

    async def _find_existing_observation(
        self,
        source_id: str,
    ) -> Observation | None:
        """Find existing Observation by source ID."""
        if source_id in self._source_cache:
            stmt = select(Observation).where(
                Observation.observation_id == self._source_cache[source_id]
            )
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        stmt = select(Observation).where(
            Observation.observation_source_value == source_id
        )
        result = await self.session.execute(stmt)
        obs = result.scalar_one_or_none()

        if obs:
            self._source_cache[source_id] = obs.observation_id

        return obs

    async def transform(
        self,
        observation: SourceObservation,
        person_id: int,
        visit_occurrence_id: int | None = None,
        provider_id: int | None = None,
    ) -> dict[str, Any]:
        """Transform SourceObservation to Observation attributes."""
        # Map concepts
        concept_id, source_concept_id = await self._lookup_concept_id(
            observation.observation_code or "",
            observation.observation_code_system,
        )

        # Parse values
        value_as_number, value_as_string, value_as_concept_id = self._parse_value(observation)

        # Map unit
        unit_concept_id = self._map_unit_concept(observation.unit)

        # Normalize date
        obs_date, obs_datetime = self._normalize_date(observation)

        # Determine type
        type_concept_id = self._determine_observation_type(observation)

        # Build source value
        source_value = observation.observation_code
        if observation.observation_code_system:
            source_value = f"{observation.observation_code_system}:{observation.observation_code}"

        return {
            "person_id": person_id,
            "observation_concept_id": concept_id,
            "observation_date": obs_date,
            "observation_datetime": obs_datetime,
            "observation_type_concept_id": type_concept_id,
            "value_as_number": value_as_number,
            "value_as_string": value_as_string,
            "value_as_concept_id": value_as_concept_id,
            "qualifier_concept_id": None,
            "unit_concept_id": unit_concept_id,
            "provider_id": provider_id,
            "visit_occurrence_id": visit_occurrence_id,
            "visit_detail_id": None,
            "observation_source_value": source_value[:50] if source_value else None,
            "observation_source_concept_id": source_concept_id,
            "unit_source_value": observation.unit[:50] if observation.unit else None,
            "qualifier_source_value": None,
            "value_source_value": observation.value_text[:50] if observation.value_text else None,
            "observation_event_id": None,
            "obs_event_field_concept_id": None,
        }

    async def transform_and_load(
        self,
        observation: SourceObservation,
        person_id: int,
        visit_occurrence_id: int | None = None,
        provider_id: int | None = None,
    ) -> Observation:
        """Transform and load a single observation."""
        if not observation.source_id:
            raise ValueError("Observation must have a source_id")

        existing = await self._find_existing_observation(observation.source_id)

        obs_data = await self.transform(
            observation, person_id, visit_occurrence_id, provider_id
        )

        if existing:
            for key, value in obs_data.items():
                if value is not None:
                    setattr(existing, key, value)
            await self.session.flush()
            return existing

        obs = Observation(**obs_data)
        self.session.add(obs)
        await self.session.flush()

        self._source_cache[observation.source_id] = obs.observation_id

        return obs

    async def transform_and_load_batch(
        self,
        observations: list[tuple[SourceObservation, int, int | None]],
    ) -> ObservationETLResult:
        """Transform and load a batch of observations."""
        result = ObservationETLResult()

        for observation, person_id, visit_id in observations:
            result.total_processed += 1

            try:
                existing = await self._find_existing_observation(observation.source_id) if observation.source_id else None

                obs = await self.transform_and_load(
                    observation, person_id, visit_id
                )

                if existing:
                    result.observations_updated += 1
                else:
                    result.observations_created += 1

                if obs.observation_concept_id == 0:
                    result.unmapped_codes += 1

                if result.total_processed % self.config.batch_size == 0:
                    await self.session.commit()

            except Exception as e:
                result.errors.append(f"Error processing {observation.source_id}: {e}")
                logger.warning(f"ETL error for observation {observation.source_id}: {e}")

        await self.session.commit()

        return result

    def get_stats(self) -> dict[str, Any]:
        """Get ETL service statistics."""
        return {
            "cached_mappings": len(self._source_cache),
            "cached_concepts": len(self._concept_cache),
        }
