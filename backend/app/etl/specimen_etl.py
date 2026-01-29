"""Specimen Table ETL Service.

This module provides ETL functionality for transforming source specimen
data into the OMOP CDM Specimen table.

The service handles:
    - FHIR Specimen resource mapping
    - SNOMED specimen type concept mapping
    - Anatomic site mapping
    - Quantity and unit normalization

FHIR R4 Specimen Resource Mapping:
    Specimen -> OMOP Specimen table
        - type -> specimen_concept_id (SNOMED specimen types)
        - collection.collectedDateTime -> specimen_date/datetime
        - collection.quantity -> quantity
        - collection.bodySite -> anatomic_site_concept_id
        - condition -> disease_status_concept_id

Standard OMOP Specimen Type Concept IDs:
    32817 - EHR encounter record
    32821 - EHR administration record
    32879 - Registry

Common SNOMED Specimen Types:
    122555007 - Venous blood specimen
    122556008 - Arterial blood specimen
    119364003 - Serum specimen
    122575003 - Urine specimen
    122580007 - Cerebrospinal fluid specimen
    119376003 - Tissue specimen
    258500001 - Nasopharyngeal swab
    119361006 - Plasma specimen

Usage:
    from app.etl import SpecimenETL, SpecimenETLConfig
    from app.connectors import SourceSpecimen

    etl = SpecimenETL(db_session)

    specimen = SourceSpecimen(
        source_id="SPEC001",
        patient_source_id="PAT001",
        specimen_code="122555007",
        specimen_code_system="SNOMED",
        specimen_type="Venous blood specimen",
        collected_datetime=datetime(2024, 1, 15, 10, 30),
        quantity_value=5.0,
        quantity_unit="mL"
    )

    spec = await etl.transform_and_load(specimen, person_id=1)
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.etl.concept_mappings import (
    CODE_SYSTEM_VOCABULARY_MAP,
    DEFAULT_SPECIMEN_TYPE_CONCEPT_ID,
    SPECIMEN_TYPE_CONCEPT_MAP,
    UCUM_UNIT_CONCEPT_MAP,
)
from app.models.omop import Specimen

logger = logging.getLogger(__name__)


# Extended specimen type mapping for additional categories
SPECIMEN_TYPE_EXTENDED_MAP = {
    **SPECIMEN_TYPE_CONCEPT_MAP,
    "ehr": 32817,           # EHR encounter record
    "ehr_admin": 32821,     # EHR administration record
    "registry": 32879,      # Registry
    "lab": 32817,           # Lab system
    "pathology": 32817,     # Pathology
    "biobank": 32879,       # Biobank/registry
}


class SpecimenStatus:
    """Status values for specimen records (FHIR Specimen.status)."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNSATISFACTORY = "unsatisfactory"
    ENTERED_IN_ERROR = "entered-in-error"
    UNKNOWN = "unknown"


# Specimen Status to OMOP handling
SPECIMEN_STATUS_MAP = {
    SpecimenStatus.AVAILABLE: True,          # Include in CDM
    SpecimenStatus.UNAVAILABLE: True,        # Include (historical)
    SpecimenStatus.UNSATISFACTORY: True,     # Include (for documentation)
    SpecimenStatus.ENTERED_IN_ERROR: False,  # Exclude
    SpecimenStatus.UNKNOWN: True,            # Include
}


@dataclass
class SourceSpecimen:
    """Standardized specimen record from source systems.

    Maps to OMOP Specimen table.
    Represents FHIR Specimen resource.
    """

    source_id: str
    source_system: str = ""
    patient_source_id: str = ""

    # Specimen identification
    specimen_code: str | None = None
    specimen_code_system: str | None = None
    specimen_type: str | None = None  # Display text

    # Status
    status: str = SpecimenStatus.UNKNOWN

    # Collection timing
    collected_datetime: datetime | None = None
    received_datetime: datetime | None = None

    # Quantity
    quantity_value: float | None = None
    quantity_unit: str | None = None
    quantity_unit_code: str | None = None  # UCUM code

    # Anatomic site (collection body site)
    body_site_code: str | None = None
    body_site_code_system: str | None = None
    body_site_text: str | None = None

    # Disease status (condition at time of collection)
    disease_status_code: str | None = None
    disease_status_text: str | None = None

    # Container information
    container_type: str | None = None
    container_description: str | None = None

    # Processing information
    processing_method: str | None = None
    additive: str | None = None

    # Accession identifier
    accession_identifier: str | None = None

    # Parent specimen (for derived specimens)
    parent_specimen_id: str | None = None

    # Additional metadata
    raw_data: dict[str, Any] = field(default_factory=dict)
    extracted_at: datetime = field(default_factory=datetime.now)


@dataclass
class SpecimenETLConfig:
    """Configuration for Specimen ETL service."""

    map_to_standard: bool = True
    preserve_source_codes: bool = True
    default_specimen_type: int = DEFAULT_SPECIMEN_TYPE_CONCEPT_ID
    include_entered_in_error: bool = False
    batch_size: int = 1000


@dataclass
class SpecimenETLResult:
    """Result of Specimen ETL operation."""

    total_processed: int = 0
    specimens_created: int = 0
    specimens_updated: int = 0
    specimens_skipped: int = 0
    unmapped_codes: int = 0
    errors: list[str] = field(default_factory=list)


class SpecimenETL:
    """ETL service for transforming SourceSpecimen to OMOP Specimen.

    Handles FHIR Specimen resource mapping to OMOP CDM format.

    Example:
        etl = SpecimenETL(session)
        specimen = await etl.transform_and_load(source_specimen, person_id=123)
    """

    def __init__(
        self,
        session: AsyncSession,
        config: SpecimenETLConfig | None = None,
        vocabulary_service: Any | None = None,
    ):
        """Initialize Specimen ETL service.

        Args:
            session: SQLAlchemy async session for database operations.
            config: Optional ETL configuration.
            vocabulary_service: Optional vocabulary service for concept mapping.
        """
        self.session = session
        self.config = config or SpecimenETLConfig()
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
        domain_id: str = "Specimen",
    ) -> tuple[int, int | None]:
        """Look up OMOP concept ID for a specimen code.

        Args:
            code: Specimen code (SNOMED, etc.)
            code_system: Code system identifier
            domain_id: OMOP domain ID to search

        Returns:
            Tuple of (standard_concept_id, source_concept_id)
        """
        cache_key = f"{code_system}:{code}:{domain_id}"

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
                        domain_ids=[domain_id],
                        exact_match=True,
                    )
                    if result and len(result) > 0:
                        concept_id = result[0].concept_id
                        self._concept_cache[cache_key] = concept_id
                        return concept_id, concept_id
            except Exception as e:
                logger.debug(f"Concept lookup failed for specimen code {code}: {e}")

        # Return 0 for unmapped codes
        return 0, None

    async def _lookup_unit_concept_id(self, unit: str | None) -> int | None:
        """Look up OMOP concept ID for a unit.

        Args:
            unit: Unit string or UCUM code

        Returns:
            OMOP unit concept ID or None
        """
        if not unit:
            return None

        # Check static mapping first
        unit_lower = unit.lower().strip()
        if unit_lower in UCUM_UNIT_CONCEPT_MAP:
            return UCUM_UNIT_CONCEPT_MAP[unit_lower]

        # Try vocabulary service lookup
        if self.vocabulary_service:
            try:
                result = self.vocabulary_service.search_concepts(
                    search_term=unit,
                    vocabulary_ids=["UCUM"],
                    exact_match=True,
                )
                if result and len(result) > 0:
                    return result[0].concept_id
            except Exception:
                pass

        return None

    def _normalize_dates(
        self,
        specimen: SourceSpecimen,
    ) -> tuple[date, datetime | None]:
        """Normalize specimen dates.

        Args:
            specimen: Source specimen record

        Returns:
            Tuple of (specimen_date, specimen_datetime)
        """
        specimen_date: date
        specimen_datetime: datetime | None = None

        # Priority: collected_datetime > received_datetime > today
        if specimen.collected_datetime:
            if isinstance(specimen.collected_datetime, datetime):
                specimen_date = specimen.collected_datetime.date()
                specimen_datetime = specimen.collected_datetime
            else:
                specimen_date = specimen.collected_datetime
        elif specimen.received_datetime:
            if isinstance(specimen.received_datetime, datetime):
                specimen_date = specimen.received_datetime.date()
                specimen_datetime = specimen.received_datetime
            else:
                specimen_date = specimen.received_datetime
        else:
            specimen_date = date.today()

        return specimen_date, specimen_datetime

    def _should_include_specimen(self, specimen: SourceSpecimen) -> bool:
        """Check if specimen should be included in CDM.

        Args:
            specimen: Source specimen record

        Returns:
            True if specimen should be included
        """
        if not specimen.status:
            return True

        if specimen.status == SpecimenStatus.ENTERED_IN_ERROR:
            return self.config.include_entered_in_error

        return SPECIMEN_STATUS_MAP.get(specimen.status, True)

    async def _find_existing_specimen(
        self,
        source_id: str,
    ) -> Specimen | None:
        """Find existing Specimen by source ID.

        Args:
            source_id: Source system specimen ID

        Returns:
            Existing Specimen or None
        """
        if source_id in self._source_cache:
            stmt = select(Specimen).where(
                Specimen.specimen_id == self._source_cache[source_id]
            )
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        stmt = select(Specimen).where(
            Specimen.specimen_source_id == source_id
        )
        result = await self.session.execute(stmt)
        specimen = result.scalar_one_or_none()

        if specimen:
            self._source_cache[source_id] = specimen.specimen_id

        return specimen

    async def transform(
        self,
        specimen: SourceSpecimen,
        person_id: int,
    ) -> dict[str, Any]:
        """Transform SourceSpecimen to Specimen attributes.

        Args:
            specimen: Source specimen record
            person_id: OMOP person_id

        Returns:
            Dictionary of Specimen attributes
        """
        # Map specimen concept
        specimen_concept_id, _ = await self._lookup_concept_id(
            specimen.specimen_code or "",
            specimen.specimen_code_system,
            domain_id="Specimen",
        )

        # Map anatomic site concept
        anatomic_site_concept_id = None
        if specimen.body_site_code:
            anatomic_site_concept_id, _ = await self._lookup_concept_id(
                specimen.body_site_code,
                specimen.body_site_code_system or "SNOMED",
                domain_id="Spec Anatomic Site",
            )

        # Map disease status concept
        disease_status_concept_id = None
        if specimen.disease_status_code:
            disease_status_concept_id, _ = await self._lookup_concept_id(
                specimen.disease_status_code,
                "SNOMED",
                domain_id="Observation",
            )

        # Map unit concept
        unit_concept_id = await self._lookup_unit_concept_id(
            specimen.quantity_unit or specimen.quantity_unit_code
        )

        # Normalize dates
        specimen_date, specimen_datetime = self._normalize_dates(specimen)

        # Build source value
        source_value = specimen.specimen_code
        if specimen.specimen_code_system and specimen.specimen_code:
            source_value = f"{specimen.specimen_code_system}:{specimen.specimen_code}"
        elif specimen.specimen_type:
            source_value = specimen.specimen_type

        # Convert quantity to Decimal
        quantity: Decimal | None = None
        if specimen.quantity_value is not None:
            quantity = Decimal(str(specimen.quantity_value))

        return {
            "person_id": person_id,
            "specimen_concept_id": specimen_concept_id,
            "specimen_type_concept_id": self.config.default_specimen_type,
            "specimen_date": specimen_date,
            "specimen_datetime": specimen_datetime,
            "quantity": quantity,
            "unit_concept_id": unit_concept_id,
            "anatomic_site_concept_id": anatomic_site_concept_id,
            "disease_status_concept_id": disease_status_concept_id,
            "specimen_source_id": specimen.source_id[:50] if specimen.source_id else None,
            "specimen_source_value": source_value[:50] if source_value else None,
            "unit_source_value": specimen.quantity_unit[:50] if specimen.quantity_unit else None,
            "anatomic_site_source_value": specimen.body_site_text[:50] if specimen.body_site_text else None,
            "disease_status_source_value": specimen.disease_status_text[:50] if specimen.disease_status_text else None,
        }

    async def transform_and_load(
        self,
        specimen: SourceSpecimen,
        person_id: int,
    ) -> Specimen | None:
        """Transform and load a single specimen record.

        Args:
            specimen: Source specimen record
            person_id: OMOP person_id

        Returns:
            Created/updated Specimen or None if skipped
        """
        if not specimen.source_id:
            raise ValueError("Specimen must have a source_id")

        # Check if should include
        if not self._should_include_specimen(specimen):
            return None

        existing = await self._find_existing_specimen(specimen.source_id)

        specimen_data = await self.transform(specimen, person_id)

        if existing:
            for key, value in specimen_data.items():
                if value is not None:
                    setattr(existing, key, value)
            await self.session.flush()
            return existing

        spec = Specimen(**specimen_data)
        self.session.add(spec)
        await self.session.flush()

        self._source_cache[specimen.source_id] = spec.specimen_id

        return spec

    async def transform_and_load_batch(
        self,
        specimens: list[tuple[SourceSpecimen, int]],
    ) -> SpecimenETLResult:
        """Transform and load a batch of specimens.

        Args:
            specimens: List of tuples (SourceSpecimen, person_id)

        Returns:
            SpecimenETLResult with statistics
        """
        result = SpecimenETLResult()

        for specimen, person_id in specimens:
            result.total_processed += 1

            try:
                existing = await self._find_existing_specimen(specimen.source_id) if specimen.source_id else None

                spec = await self.transform_and_load(specimen, person_id)

                if spec is None:
                    result.specimens_skipped += 1
                elif existing:
                    result.specimens_updated += 1
                else:
                    result.specimens_created += 1

                if spec and spec.specimen_concept_id == 0:
                    result.unmapped_codes += 1

                if result.total_processed % self.config.batch_size == 0:
                    await self.session.commit()

            except Exception as e:
                result.errors.append(f"Error processing specimen {specimen.source_id}: {e}")
                logger.warning(f"ETL error for specimen {specimen.source_id}: {e}")

        await self.session.commit()

        return result

    @staticmethod
    def from_fhir_specimen(resource: dict[str, Any], source_system: str = "fhir") -> SourceSpecimen:
        """Create SourceSpecimen from FHIR Specimen resource.

        Args:
            resource: FHIR Specimen JSON resource
            source_system: Source system identifier

        Returns:
            SourceSpecimen instance
        """
        specimen = SourceSpecimen(
            source_id=resource.get("id", ""),
            source_system=source_system,
            raw_data=resource,
        )

        # Patient reference
        subject = resource.get("subject", {})
        if subject.get("reference"):
            specimen.patient_source_id = subject["reference"].replace("Patient/", "")

        # Specimen type
        specimen_type = resource.get("type", {})
        if specimen_type.get("coding"):
            coding = specimen_type["coding"][0]
            specimen.specimen_code = coding.get("code")
            specimen.specimen_code_system = coding.get("system")
            specimen.specimen_type = coding.get("display") or specimen_type.get("text")

        # Status
        specimen.status = resource.get("status", SpecimenStatus.UNKNOWN)

        # Accession identifier
        accession = resource.get("accessionIdentifier", {})
        specimen.accession_identifier = accession.get("value")

        # Collection information
        collection = resource.get("collection", {})

        # Collection timing
        collected = collection.get("collectedDateTime") or collection.get("collectedPeriod", {})
        if isinstance(collected, str):
            try:
                specimen.collected_datetime = datetime.fromisoformat(
                    collected.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass
        elif isinstance(collected, dict):
            if collected.get("start"):
                try:
                    specimen.collected_datetime = datetime.fromisoformat(
                        collected["start"].replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    pass

        # Collection quantity
        quantity = collection.get("quantity", {})
        specimen.quantity_value = quantity.get("value")
        specimen.quantity_unit = quantity.get("unit")
        specimen.quantity_unit_code = quantity.get("code")  # UCUM code

        # Body site
        body_site = collection.get("bodySite", {})
        if body_site.get("coding"):
            coding = body_site["coding"][0]
            specimen.body_site_code = coding.get("code")
            specimen.body_site_code_system = coding.get("system")
        specimen.body_site_text = body_site.get("text")

        # Received time
        if resource.get("receivedTime"):
            try:
                specimen.received_datetime = datetime.fromisoformat(
                    resource["receivedTime"].replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

        # Processing information
        processing = resource.get("processing", [])
        if processing:
            proc = processing[0]
            procedure = proc.get("procedure", {})
            if procedure.get("coding"):
                specimen.processing_method = procedure["coding"][0].get("display")

            additive = proc.get("additive", [])
            if additive:
                add_ref = additive[0]
                if add_ref.get("display"):
                    specimen.additive = add_ref["display"]

        # Container information
        containers = resource.get("container", [])
        if containers:
            container = containers[0]
            container_type = container.get("type", {})
            if container_type.get("coding"):
                specimen.container_type = container_type["coding"][0].get("display")
            specimen.container_description = container.get("description")

        # Condition (disease status)
        conditions = resource.get("condition", [])
        if conditions:
            cond = conditions[0]
            if cond.get("coding"):
                coding = cond["coding"][0]
                specimen.disease_status_code = coding.get("code")
            specimen.disease_status_text = cond.get("text")

        # Parent specimen
        parents = resource.get("parent", [])
        if parents:
            parent_ref = parents[0].get("reference", "")
            specimen.parent_specimen_id = parent_ref.replace("Specimen/", "")

        return specimen

    def get_stats(self) -> dict[str, Any]:
        """Get ETL service statistics.

        Returns:
            Dictionary with service statistics
        """
        return {
            "cached_mappings": len(self._source_cache),
            "cached_concepts": len(self._concept_cache),
        }
