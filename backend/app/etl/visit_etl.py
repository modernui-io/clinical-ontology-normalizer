"""Visit Occurrence Table ETL Service.

This module provides ETL functionality for transforming source visit data
into the OMOP CDM Visit_Occurrence and Visit_Detail tables.

Standard OMOP Visit Concept IDs:
    9201 - Inpatient Visit
    9202 - Outpatient Visit
    9203 - Emergency Room Visit
    9204 - Emergency Room and Inpatient Visit
    262 - Emergency Room - Hospital
    581476 - Home Visit
    581477 - Office Visit
    581478 - Telehealth Visit
    32037 - Intensive Care

Visit Type Concept IDs (data provenance):
    32817 - EHR encounter record
    32818 - EHR problem list entry
    32819 - EHR order entry
    32821 - EHR administration record
    32879 - Registry

Usage:
    from app.etl import VisitETL
    from app.connectors import SourceVisit, VisitType

    etl = VisitETL(db_session)

    visit = SourceVisit(
        source_id="VISIT001",
        patient_source_id="PAT001",
        visit_type=VisitType.INPATIENT,
        start_date=datetime(2024, 1, 15),
        end_date=datetime(2024, 1, 18)
    )

    visit_occurrence = await etl.transform_and_load(visit, person_id=1)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import SourceVisit, VisitType
from app.etl.concept_mappings import VISIT_CONCEPT_MAP
from app.models.omop import VisitOccurrence

logger = logging.getLogger(__name__)


# Visit concept map using VisitType enum as keys (extends string-keyed VISIT_CONCEPT_MAP)
VISIT_TYPE_ENUM_MAP = {
    VisitType.INPATIENT: 9201,
    VisitType.OUTPATIENT: 9202,
    VisitType.EMERGENCY: 9203,
    VisitType.OBSERVATION: 9201,  # Map to inpatient
    VisitType.HOME: 581476,  # Home Visit
    VisitType.TELEHEALTH: 581478,  # Telehealth Visit (note: different from VISIT_CONCEPT_MAP's 5083)
    VisitType.UNKNOWN: 9202,  # Default to outpatient
}

# Visit source value to concept mapping
VISIT_SOURCE_MAP = {
    # Inpatient
    "inpatient": 9201,
    "inp": 9201,
    "ip": 9201,
    "hospital": 9201,
    "admitted": 9201,
    "admission": 9201,
    "acute": 9201,
    "imp": 9201,  # HL7 encounter type
    # Outpatient
    "outpatient": 9202,
    "outp": 9202,
    "op": 9202,
    "clinic": 9202,
    "ambulatory": 9202,
    "amb": 9202,  # HL7 encounter type
    # Emergency
    "emergency": 9203,
    "er": 9203,
    "ed": 9203,
    "emer": 9203,  # HL7 encounter type
    "emergent": 9203,
    # Combined ER + Inpatient
    "emergency to inpatient": 9204,
    "er to ip": 9204,
    # Home
    "home": 581476,
    "home visit": 581476,
    "hh": 581476,  # HL7 encounter type
    # Office
    "office": 581477,
    "office visit": 581477,
    "vr": 581477,  # HL7 virtual
    # Telehealth
    "telehealth": 581478,
    "telemedicine": 581478,
    "virtual": 581478,
    "phone": 581478,
    "video": 581478,
    # Long-term care
    "long term care": 42898160,
    "ltc": 42898160,
    "nursing home": 42898160,
    "snf": 42898160,  # Skilled Nursing Facility
}

# Default visit type concept (EHR encounter record)
DEFAULT_VISIT_TYPE_CONCEPT_ID = 32817


@dataclass
class VisitETLConfig:
    """Configuration for Visit ETL service.

    Attributes:
        default_visit_concept_id: Default visit concept if none mapped.
        infer_end_date: Whether to use start date if end date missing.
        create_visit_details: Whether to create Visit_Detail records.
        batch_size: Number of records to commit in a batch.
        custom_visit_map: Additional visit type mappings.
    """

    default_visit_concept_id: int = 9202  # Outpatient
    infer_end_date: bool = True
    create_visit_details: bool = False
    batch_size: int = 1000
    custom_visit_map: dict[str, int] = field(default_factory=dict)


@dataclass
class VisitETLResult:
    """Result of Visit ETL operation.

    Attributes:
        total_processed: Total source visits processed.
        visits_created: Number of new VisitOccurrence records.
        visits_updated: Number of existing records updated.
        visits_skipped: Number of records skipped.
        errors: List of error messages.
    """

    total_processed: int = 0
    visits_created: int = 0
    visits_updated: int = 0
    visits_skipped: int = 0
    errors: list[str] = field(default_factory=list)


class VisitETL:
    """ETL service for transforming SourceVisit to OMOP VisitOccurrence.

    Handles transformation of visits/encounters from various source formats
    into the standardized OMOP Visit_Occurrence table.

    Example:
        etl = VisitETL(session)
        visit_occ = await etl.transform_and_load(source_visit, person_id=123)
    """

    def __init__(
        self,
        session: AsyncSession,
        config: VisitETLConfig | None = None,
    ):
        """Initialize Visit ETL service.

        Args:
            session: SQLAlchemy async session.
            config: Optional ETL configuration.
        """
        self.session = session
        self.config = config or VisitETLConfig()

        # Merge custom mappings
        self._visit_map = {**VISIT_SOURCE_MAP, **self.config.custom_visit_map}

        # Cache for source_id to visit_occurrence_id
        self._source_cache: dict[str, int] = {}

    def _map_visit_concept(self, visit: SourceVisit) -> int:
        """Map source visit type to OMOP concept ID.

        Args:
            visit: Source visit record.

        Returns:
            OMOP visit concept ID.
        """
        # First try enum mapping
        if visit.visit_type:
            concept_id = VISIT_TYPE_ENUM_MAP.get(visit.visit_type)
            if concept_id:
                return concept_id

        # Try source value mapping
        if visit.visit_source_value:
            normalized = visit.visit_source_value.lower().strip()
            concept_id = self._visit_map.get(normalized)
            if concept_id:
                return concept_id

        # Try raw data
        if visit.raw_data and "encounter_type" in visit.raw_data:
            enc_type = str(visit.raw_data["encounter_type"]).lower().strip()
            concept_id = self._visit_map.get(enc_type)
            if concept_id:
                return concept_id

        return self.config.default_visit_concept_id

    def _normalize_dates(
        self,
        visit: SourceVisit,
    ) -> tuple[date, datetime | None, date, datetime | None]:
        """Normalize visit start and end dates.

        Args:
            visit: Source visit record.

        Returns:
            Tuple of (start_date, start_datetime, end_date, end_datetime).
        """
        # Start date/datetime
        start_date: date
        start_datetime: datetime | None = None

        if visit.start_date:
            if isinstance(visit.start_date, datetime):
                start_date = visit.start_date.date()
                start_datetime = visit.start_date
            else:
                start_date = visit.start_date
        else:
            # Use current date if no start date (shouldn't happen)
            start_date = date.today()

        # End date/datetime
        end_date: date
        end_datetime: datetime | None = None

        if visit.end_date:
            if isinstance(visit.end_date, datetime):
                end_date = visit.end_date.date()
                end_datetime = visit.end_date
            else:
                end_date = visit.end_date
        elif self.config.infer_end_date:
            # Use start date if end date missing
            end_date = start_date
            end_datetime = start_datetime
        else:
            end_date = start_date

        return start_date, start_datetime, end_date, end_datetime

    async def _find_existing_visit(self, source_id: str) -> VisitOccurrence | None:
        """Find existing VisitOccurrence by source ID.

        Args:
            source_id: Source visit identifier.

        Returns:
            Existing VisitOccurrence or None.
        """
        if source_id in self._source_cache:
            stmt = select(VisitOccurrence).where(
                VisitOccurrence.visit_occurrence_id == self._source_cache[source_id]
            )
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        stmt = select(VisitOccurrence).where(
            VisitOccurrence.visit_source_value == source_id
        )
        result = await self.session.execute(stmt)
        visit = result.scalar_one_or_none()

        if visit:
            self._source_cache[source_id] = visit.visit_occurrence_id

        return visit

    async def transform(
        self,
        visit: SourceVisit,
        person_id: int,
        provider_id: int | None = None,
        care_site_id: int | None = None,
    ) -> dict[str, Any]:
        """Transform SourceVisit to VisitOccurrence attributes.

        Args:
            visit: Source visit record.
            person_id: OMOP person_id (required).
            provider_id: Optional OMOP provider_id.
            care_site_id: Optional OMOP care_site_id.

        Returns:
            Dictionary of VisitOccurrence attributes.
        """
        # Map visit concept
        visit_concept_id = self._map_visit_concept(visit)

        # Normalize dates
        start_date, start_datetime, end_date, end_datetime = self._normalize_dates(visit)

        # Build source value
        source_value = visit.visit_source_value
        if not source_value and visit.visit_type:
            source_value = visit.visit_type.value

        return {
            "person_id": person_id,
            "visit_concept_id": visit_concept_id,
            "visit_start_date": start_date,
            "visit_start_datetime": start_datetime,
            "visit_end_date": end_date,
            "visit_end_datetime": end_datetime,
            "visit_type_concept_id": DEFAULT_VISIT_TYPE_CONCEPT_ID,
            "provider_id": provider_id,
            "care_site_id": care_site_id,
            "visit_source_value": source_value[:50] if source_value else None,
            "visit_source_concept_id": None,
            "admitted_from_concept_id": None,
            "admitted_from_source_value": None,
            "discharged_to_concept_id": None,
            "discharged_to_source_value": None,
            "preceding_visit_occurrence_id": None,
        }

    async def transform_and_load(
        self,
        visit: SourceVisit,
        person_id: int,
        provider_id: int | None = None,
        care_site_id: int | None = None,
    ) -> VisitOccurrence:
        """Transform and load a single visit to OMOP VisitOccurrence.

        Args:
            visit: Source visit record.
            person_id: OMOP person_id (required).
            provider_id: Optional OMOP provider_id.
            care_site_id: Optional OMOP care_site_id.

        Returns:
            Created or updated VisitOccurrence record.

        Raises:
            ValueError: If visit has no source_id.
        """
        if not visit.source_id:
            raise ValueError("Visit must have a source_id")

        # Check for existing
        existing = await self._find_existing_visit(visit.source_id)

        # Transform
        visit_data = await self.transform(visit, person_id, provider_id, care_site_id)

        if existing:
            # Update existing record
            for key, value in visit_data.items():
                if value is not None:
                    setattr(existing, key, value)
            await self.session.flush()
            return existing

        # Create new record
        visit_occurrence = VisitOccurrence(**visit_data)
        self.session.add(visit_occurrence)
        await self.session.flush()

        # Cache the mapping
        self._source_cache[visit.source_id] = visit_occurrence.visit_occurrence_id

        return visit_occurrence

    async def transform_and_load_batch(
        self,
        visits: list[tuple[SourceVisit, int]],  # (visit, person_id) pairs
    ) -> VisitETLResult:
        """Transform and load a batch of visits.

        Args:
            visits: List of (SourceVisit, person_id) tuples.

        Returns:
            ETL result with statistics.
        """
        result = VisitETLResult()

        for visit, person_id in visits:
            result.total_processed += 1

            try:
                existing = await self._find_existing_visit(visit.source_id) if visit.source_id else None

                visit_occ = await self.transform_and_load(visit, person_id)

                if existing:
                    result.visits_updated += 1
                else:
                    result.visits_created += 1

                # Commit in batches
                if result.total_processed % self.config.batch_size == 0:
                    await self.session.commit()

            except Exception as e:
                result.errors.append(f"Error processing {visit.source_id}: {e}")
                logger.warning(f"ETL error for visit {visit.source_id}: {e}")

        # Final commit
        await self.session.commit()

        return result

    def get_stats(self) -> dict[str, Any]:
        """Get ETL service statistics."""
        return {
            "cached_mappings": len(self._source_cache),
            "visit_mappings": len(self._visit_map),
        }
