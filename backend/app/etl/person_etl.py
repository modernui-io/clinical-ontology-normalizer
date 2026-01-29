"""Person Table ETL Service.

This module provides ETL (Extract-Transform-Load) functionality for
transforming source patient data into the OMOP CDM Person table.

The ETL process handles:
    - Gender concept mapping (source value → OMOP gender concept)
    - Race concept mapping (source value → OMOP race concept)
    - Ethnicity concept mapping (source value → OMOP ethnicity concept)
    - Date parsing and normalization
    - Location creation and linking
    - Deduplication by source_id

Standard OMOP Concept IDs:
    Gender:
        8507 - MALE
        8532 - FEMALE
        8551 - UNKNOWN
        8570 - AMBIGUOUS

    Race (CDC/OMB categories):
        8527 - White
        8516 - Black or African American
        8515 - Asian
        8657 - American Indian or Alaska Native
        8557 - Native Hawaiian or Other Pacific Islander
        8522 - Other Race
        8552 - Unknown

    Ethnicity:
        38003563 - Hispanic or Latino
        38003564 - Not Hispanic or Latino
        0 - Unknown

Usage:
    from app.etl import PersonETL
    from app.connectors import SourcePatient, Gender

    etl = PersonETL(db_session)

    patient = SourcePatient(
        source_id="PAT001",
        given_name="John",
        family_name="Doe",
        birth_date=datetime(1980, 5, 15),
        gender=Gender.MALE,
        race="White",
        ethnicity="Not Hispanic or Latino"
    )

    person = await etl.transform_and_load(patient)
    print(f"person_id={person.person_id}, gender={person.gender_concept_id}")
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import Gender, SourcePatient
from app.etl.concept_mappings import (
    DEFAULT_ETHNICITY_CONCEPT_ID,
    DEFAULT_GENDER_CONCEPT_ID,
    DEFAULT_RACE_CONCEPT_ID,
    ETHNICITY_CONCEPT_MAP,
    GENDER_CONCEPT_MAP,
    GENDER_SOURCE_MAP,
    RACE_CONCEPT_MAP,
)
from app.models.omop import Location, Person

logger = logging.getLogger(__name__)


@dataclass
class PersonETLConfig:
    """Configuration for Person ETL service.

    Attributes:
        create_locations: Whether to create Location records for addresses.
        deduplicate_by_source: Whether to update existing records or skip.
        batch_size: Number of records to commit in a batch.
        custom_gender_map: Additional gender value mappings.
        custom_race_map: Additional race value mappings.
        custom_ethnicity_map: Additional ethnicity value mappings.
    """

    create_locations: bool = True
    deduplicate_by_source: bool = True
    batch_size: int = 1000
    custom_gender_map: dict[str, int] = field(default_factory=dict)
    custom_race_map: dict[str, int] = field(default_factory=dict)
    custom_ethnicity_map: dict[str, int] = field(default_factory=dict)


@dataclass
class PersonETLResult:
    """Result of Person ETL operation.

    Attributes:
        total_processed: Total number of source patients processed.
        persons_created: Number of new Person records created.
        persons_updated: Number of existing Person records updated.
        persons_skipped: Number of records skipped (duplicates).
        locations_created: Number of Location records created.
        errors: List of error messages.
    """

    total_processed: int = 0
    persons_created: int = 0
    persons_updated: int = 0
    persons_skipped: int = 0
    locations_created: int = 0
    errors: list[str] = field(default_factory=list)


class PersonETL:
    """ETL service for transforming SourcePatient to OMOP Person.

    This service handles the transformation of patient demographics from
    various source formats into the standardized OMOP Person table.

    The transformation includes:
        - Concept mapping for gender, race, ethnicity
        - Date normalization
        - Location creation
        - Source value preservation
        - Deduplication handling

    Example:
        etl = PersonETL(session)
        person = await etl.transform_and_load(source_patient)
    """

    def __init__(
        self,
        session: AsyncSession,
        config: PersonETLConfig | None = None,
    ):
        """Initialize Person ETL service.

        Args:
            session: SQLAlchemy async session.
            config: Optional ETL configuration.
        """
        self.session = session
        self.config = config or PersonETLConfig()

        # Merge custom mappings with defaults
        self._gender_map = {**GENDER_SOURCE_MAP, **self.config.custom_gender_map}
        self._race_map = {**RACE_CONCEPT_MAP, **self.config.custom_race_map}
        self._ethnicity_map = {**ETHNICITY_CONCEPT_MAP, **self.config.custom_ethnicity_map}

        # Cache for source_id to person_id mapping
        self._source_cache: dict[str, int] = {}

    def _map_gender(self, patient: SourcePatient) -> tuple[int, int | None]:
        """Map source gender to OMOP concept ID.

        Args:
            patient: Source patient record.

        Returns:
            Tuple of (gender_concept_id, gender_source_concept_id).
        """
        # First try enum mapping
        if patient.gender:
            concept_id = GENDER_CONCEPT_MAP.get(patient.gender, DEFAULT_GENDER_CONCEPT_ID)
        else:
            concept_id = DEFAULT_GENDER_CONCEPT_ID

        # Try source value mapping if available
        source_concept_id = None
        if patient.raw_data and "gender_code" in patient.raw_data:
            source_val = str(patient.raw_data["gender_code"]).lower().strip()
            source_concept_id = self._gender_map.get(source_val)

        return concept_id, source_concept_id

    def _map_race(self, race_value: str | None) -> tuple[int, int | None]:
        """Map source race value to OMOP concept ID.

        Args:
            race_value: Source race value string.

        Returns:
            Tuple of (race_concept_id, race_source_concept_id).
        """
        if not race_value:
            return DEFAULT_RACE_CONCEPT_ID, None

        normalized = race_value.lower().strip()
        concept_id = self._race_map.get(normalized, DEFAULT_RACE_CONCEPT_ID)

        return concept_id, None

    def _map_ethnicity(self, ethnicity_value: str | None) -> tuple[int, int | None]:
        """Map source ethnicity value to OMOP concept ID.

        Args:
            ethnicity_value: Source ethnicity value string.

        Returns:
            Tuple of (ethnicity_concept_id, ethnicity_source_concept_id).
        """
        if not ethnicity_value:
            return DEFAULT_ETHNICITY_CONCEPT_ID, None

        normalized = ethnicity_value.lower().strip()
        concept_id = self._ethnicity_map.get(normalized, DEFAULT_ETHNICITY_CONCEPT_ID)

        return concept_id, None

    async def _get_or_create_location(self, patient: SourcePatient) -> int | None:
        """Get or create Location record from patient address.

        Args:
            patient: Source patient with address data.

        Returns:
            Location ID or None if no address data.
        """
        if not self.config.create_locations:
            return None

        # Check if we have any address data
        if not any([
            patient.address_line1,
            patient.city,
            patient.state,
            patient.postal_code,
        ]):
            return None

        # Look for existing location
        stmt = select(Location).where(
            Location.address_1 == patient.address_line1,
            Location.city == patient.city,
            Location.state == patient.state,
            Location.zip == patient.postal_code,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            return existing.location_id

        # Create new location
        location = Location(
            address_1=patient.address_line1[:50] if patient.address_line1 else None,
            address_2=patient.address_line2[:50] if patient.address_line2 else None,
            city=patient.city[:50] if patient.city else None,
            state=patient.state[:2] if patient.state else None,
            zip=patient.postal_code[:9] if patient.postal_code else None,
            country_source_value=patient.country[:80] if patient.country else None,
            location_source_value=patient.source_id[:50] if patient.source_id else None,
        )

        self.session.add(location)
        await self.session.flush()

        return location.location_id

    async def _find_existing_person(self, source_id: str) -> Person | None:
        """Find existing Person by source ID.

        Args:
            source_id: Source patient identifier.

        Returns:
            Existing Person or None.
        """
        if source_id in self._source_cache:
            stmt = select(Person).where(Person.person_id == self._source_cache[source_id])
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        stmt = select(Person).where(Person.person_source_value == source_id)
        result = await self.session.execute(stmt)
        person = result.scalar_one_or_none()

        if person:
            self._source_cache[source_id] = person.person_id

        return person

    def _extract_birth_components(self, patient: SourcePatient) -> tuple[int, int | None, int | None, datetime | None]:
        """Extract birth date components from patient.

        Args:
            patient: Source patient record.

        Returns:
            Tuple of (year, month, day, datetime).
        """
        if patient.birth_date:
            return (
                patient.birth_date.year,
                patient.birth_date.month,
                patient.birth_date.day,
                patient.birth_date if isinstance(patient.birth_date, datetime) else None,
            )

        # Default to unknown year (required field)
        return 1900, None, None, None

    async def transform(self, patient: SourcePatient) -> dict[str, Any]:
        """Transform SourcePatient to Person attributes.

        Performs the concept mapping and data transformation without
        persisting to the database.

        Args:
            patient: Source patient record.

        Returns:
            Dictionary of Person attributes.
        """
        # Map demographics
        gender_concept_id, gender_source_concept_id = self._map_gender(patient)
        race_concept_id, race_source_concept_id = self._map_race(patient.race)
        ethnicity_concept_id, ethnicity_source_concept_id = self._map_ethnicity(patient.ethnicity)

        # Extract birth components
        year_of_birth, month_of_birth, day_of_birth, birth_datetime = self._extract_birth_components(patient)

        # Get or create location
        location_id = await self._get_or_create_location(patient)

        # Build gender source value
        gender_source_value = None
        if patient.gender:
            gender_source_value = patient.gender.value
        elif patient.raw_data and "gender" in patient.raw_data:
            gender_source_value = str(patient.raw_data["gender"])[:50]

        return {
            "gender_concept_id": gender_concept_id,
            "year_of_birth": year_of_birth,
            "month_of_birth": month_of_birth,
            "day_of_birth": day_of_birth,
            "birth_datetime": birth_datetime,
            "race_concept_id": race_concept_id,
            "ethnicity_concept_id": ethnicity_concept_id,
            "location_id": location_id,
            "person_source_value": patient.source_id[:50] if patient.source_id else None,
            "gender_source_value": gender_source_value,
            "gender_source_concept_id": gender_source_concept_id,
            "race_source_value": patient.race[:50] if patient.race else None,
            "race_source_concept_id": race_source_concept_id,
            "ethnicity_source_value": patient.ethnicity[:50] if patient.ethnicity else None,
            "ethnicity_source_concept_id": ethnicity_source_concept_id,
        }

    async def transform_and_load(self, patient: SourcePatient) -> Person:
        """Transform and load a single patient to OMOP Person.

        Args:
            patient: Source patient record.

        Returns:
            Created or updated Person record.

        Raises:
            ValueError: If patient has no source_id.
        """
        if not patient.source_id:
            raise ValueError("Patient must have a source_id")

        # Check for existing
        existing = await self._find_existing_person(patient.source_id)

        # Transform
        person_data = await self.transform(patient)

        if existing:
            # Update existing record
            for key, value in person_data.items():
                if value is not None:  # Only update non-null values
                    setattr(existing, key, value)
            await self.session.flush()
            return existing

        # Create new record
        person = Person(**person_data)
        self.session.add(person)
        await self.session.flush()

        # Cache the mapping
        self._source_cache[patient.source_id] = person.person_id

        return person

    async def transform_and_load_batch(
        self,
        patients: list[SourcePatient],
    ) -> PersonETLResult:
        """Transform and load a batch of patients.

        Args:
            patients: List of source patient records.

        Returns:
            ETL result with statistics.
        """
        result = PersonETLResult()

        for patient in patients:
            result.total_processed += 1

            try:
                existing = await self._find_existing_person(patient.source_id) if patient.source_id else None

                if existing and not self.config.deduplicate_by_source:
                    result.persons_skipped += 1
                    continue

                person = await self.transform_and_load(patient)

                if existing:
                    result.persons_updated += 1
                else:
                    result.persons_created += 1

                # Commit in batches
                if result.total_processed % self.config.batch_size == 0:
                    await self.session.commit()

            except Exception as e:
                result.errors.append(f"Error processing {patient.source_id}: {e}")
                logger.warning(f"ETL error for patient {patient.source_id}: {e}")

        # Final commit
        await self.session.commit()

        return result

    def get_stats(self) -> dict[str, Any]:
        """Get ETL service statistics.

        Returns:
            Dictionary with service stats.
        """
        return {
            "cached_mappings": len(self._source_cache),
            "gender_mappings": len(self._gender_map),
            "race_mappings": len(self._race_map),
            "ethnicity_mappings": len(self._ethnicity_map),
        }


# Singleton instance
_person_etl_service: PersonETL | None = None


def get_person_etl_service(
    session: AsyncSession | None = None,
    config: PersonETLConfig | None = None,
) -> PersonETL:
    """Get or create PersonETL service instance.

    Args:
        session: SQLAlchemy async session (required on first call).
        config: Optional ETL configuration.

    Returns:
        PersonETL service instance.

    Raises:
        ValueError: If session not provided on first call.
    """
    global _person_etl_service

    if _person_etl_service is None:
        if session is None:
            raise ValueError("Session required for first initialization")
        _person_etl_service = PersonETL(session, config)

    return _person_etl_service


def reset_person_etl_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _person_etl_service
    _person_etl_service = None
