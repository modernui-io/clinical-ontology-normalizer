"""Drug Exposure Table ETL Service.

This module provides ETL functionality for transforming source medication
data into the OMOP CDM Drug_Exposure table.

The service handles:
    - NDC/RxNorm/ATC concept mapping
    - Drug status mapping
    - Dose and route normalization
    - Date handling

Standard OMOP Drug Type Concept IDs:
    32817 - EHR encounter record
    32818 - EHR problem list entry
    32838 - EHR dispensing record
    32839 - EHR prescription
    32840 - Claim drug record
    32879 - Registry

Drug Route Concept IDs (common):
    4128794 - Oral
    4302612 - Intravenous
    4132161 - Subcutaneous
    4303155 - Intramuscular
    45956874 - Inhalation
    4186832 - Topical
    4302254 - Transdermal

Usage:
    from app.etl import DrugETL
    from app.connectors import SourceDrug, DrugStatus

    etl = DrugETL(db_session)

    drug = SourceDrug(
        source_id="MED001",
        patient_source_id="PAT001",
        drug_code="00591-2505-01",
        drug_code_system="NDC",
        drug_name="Metformin 500mg",
        start_date=datetime(2024, 1, 15),
        status=DrugStatus.ACTIVE,
        dose_value="500",
        dose_unit="mg",
        route="oral"
    )

    drug_exposure = await etl.transform_and_load(drug, person_id=1)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import DrugStatus, SourceDrug
from app.etl.concept_mappings import (
    CODE_SYSTEM_VOCABULARY_MAP,
    DEFAULT_DRUG_TYPE_CONCEPT_ID,
    DRUG_TYPE_CONCEPT_MAP,
    ROUTE_CONCEPT_MAP,
)
from app.models.omop import DrugExposure

logger = logging.getLogger(__name__)


@dataclass
class DrugETLConfig:
    """Configuration for Drug ETL service.

    Attributes:
        map_to_standard: Map source codes to RxNorm.
        preserve_source_codes: Store original codes.
        default_drug_type: Default drug type concept.
        default_days_supply: Default days supply if not specified.
        batch_size: Commit batch size.
    """

    map_to_standard: bool = True
    preserve_source_codes: bool = True
    default_drug_type: int = DEFAULT_DRUG_TYPE_CONCEPT_ID
    default_days_supply: int = 30
    batch_size: int = 1000


@dataclass
class DrugETLResult:
    """Result of Drug ETL operation."""

    total_processed: int = 0
    drugs_created: int = 0
    drugs_updated: int = 0
    drugs_skipped: int = 0
    unmapped_codes: int = 0
    errors: list[str] = field(default_factory=list)


class DrugETL:
    """ETL service for transforming SourceDrug to OMOP DrugExposure.

    Handles NDC/RxNorm mapping, route normalization, and dose handling.

    Example:
        etl = DrugETL(session)
        drug_exp = await etl.transform_and_load(source_drug, person_id=123)
    """

    def __init__(
        self,
        session: AsyncSession,
        config: DrugETLConfig | None = None,
        vocabulary_service: Any | None = None,
    ):
        """Initialize Drug ETL service.

        Args:
            session: SQLAlchemy async session.
            config: Optional ETL configuration.
            vocabulary_service: Optional vocabulary service for mapping.
        """
        self.session = session
        self.config = config or DrugETLConfig()
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
        """Look up OMOP concept ID for a drug code.

        Returns:
            Tuple of (drug_concept_id, drug_source_concept_id).
        """
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

    def _map_route_concept(self, route: str | None) -> int | None:
        """Map route to OMOP concept ID."""
        if not route:
            return None
        normalized = route.lower().strip()
        return ROUTE_CONCEPT_MAP.get(normalized)

    def _parse_quantity(self, dose_value: str | None) -> Decimal | None:
        """Parse dose value to decimal quantity."""
        if not dose_value:
            return None
        try:
            # Remove non-numeric characters except decimal
            cleaned = "".join(c for c in dose_value if c.isdigit() or c == ".")
            if cleaned:
                return Decimal(cleaned)
        except (ValueError, TypeError):
            pass
        return None

    def _normalize_dates(
        self,
        drug: SourceDrug,
    ) -> tuple[date, datetime | None, date, datetime | None]:
        """Normalize drug start and end dates."""
        # Start date
        start_date: date
        start_datetime: datetime | None = None

        if drug.start_date:
            if isinstance(drug.start_date, datetime):
                start_date = drug.start_date.date()
                start_datetime = drug.start_date
            else:
                start_date = drug.start_date
        else:
            start_date = date.today()

        # End date
        end_date: date
        end_datetime: datetime | None = None

        if drug.end_date:
            if isinstance(drug.end_date, datetime):
                end_date = drug.end_date.date()
                end_datetime = drug.end_date
            else:
                end_date = drug.end_date
        else:
            # Calculate from days supply
            from datetime import timedelta
            end_date = start_date + timedelta(days=self.config.default_days_supply)

        return start_date, start_datetime, end_date, end_datetime

    async def _find_existing_drug(self, source_id: str) -> DrugExposure | None:
        """Find existing DrugExposure by source ID."""
        if source_id in self._source_cache:
            stmt = select(DrugExposure).where(
                DrugExposure.drug_exposure_id == self._source_cache[source_id]
            )
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        stmt = select(DrugExposure).where(
            DrugExposure.drug_source_value == source_id
        )
        result = await self.session.execute(stmt)
        drug = result.scalar_one_or_none()

        if drug:
            self._source_cache[source_id] = drug.drug_exposure_id

        return drug

    async def transform(
        self,
        drug: SourceDrug,
        person_id: int,
        visit_occurrence_id: int | None = None,
        provider_id: int | None = None,
    ) -> dict[str, Any]:
        """Transform SourceDrug to DrugExposure attributes.

        Args:
            drug: Source drug record.
            person_id: OMOP person_id.
            visit_occurrence_id: Optional visit link.
            provider_id: Optional provider link.

        Returns:
            Dictionary of DrugExposure attributes.
        """
        # Map concepts
        concept_id, source_concept_id = await self._lookup_concept_id(
            drug.drug_code or "",
            drug.drug_code_system,
        )

        # Map route
        route_concept_id = self._map_route_concept(drug.route)

        # Normalize dates
        start_date, start_datetime, end_date, end_datetime = self._normalize_dates(drug)

        # Parse quantity
        quantity = self._parse_quantity(drug.dose_value)

        # Calculate days supply
        days_supply = None
        if start_date and end_date:
            days_supply = (end_date - start_date).days

        # Build source value
        source_value = drug.drug_code
        if drug.drug_code_system:
            source_value = f"{drug.drug_code_system}:{drug.drug_code}"

        return {
            "person_id": person_id,
            "drug_concept_id": concept_id,
            "drug_exposure_start_date": start_date,
            "drug_exposure_start_datetime": start_datetime,
            "drug_exposure_end_date": end_date,
            "drug_exposure_end_datetime": end_datetime,
            "verbatim_end_date": end_date,
            "drug_type_concept_id": self.config.default_drug_type,
            "stop_reason": drug.stop_reason[:20] if drug.stop_reason else None,
            "refills": drug.refills,
            "quantity": quantity,
            "days_supply": days_supply,
            "sig": drug.sig,
            "route_concept_id": route_concept_id,
            "lot_number": drug.lot_number[:50] if drug.lot_number else None,
            "provider_id": provider_id,
            "visit_occurrence_id": visit_occurrence_id,
            "visit_detail_id": None,
            "drug_source_value": source_value[:50] if source_value else None,
            "drug_source_concept_id": source_concept_id,
            "route_source_value": drug.route[:50] if drug.route else None,
            "dose_unit_source_value": drug.dose_unit[:50] if drug.dose_unit else None,
        }

    async def transform_and_load(
        self,
        drug: SourceDrug,
        person_id: int,
        visit_occurrence_id: int | None = None,
        provider_id: int | None = None,
    ) -> DrugExposure:
        """Transform and load a single drug to OMOP DrugExposure.

        Args:
            drug: Source drug record.
            person_id: OMOP person_id.
            visit_occurrence_id: Optional visit link.
            provider_id: Optional provider link.

        Returns:
            Created or updated DrugExposure record.
        """
        if not drug.source_id:
            raise ValueError("Drug must have a source_id")

        existing = await self._find_existing_drug(drug.source_id)

        drug_data = await self.transform(
            drug, person_id, visit_occurrence_id, provider_id
        )

        if existing:
            for key, value in drug_data.items():
                if value is not None:
                    setattr(existing, key, value)
            await self.session.flush()
            return existing

        drug_exposure = DrugExposure(**drug_data)
        self.session.add(drug_exposure)
        await self.session.flush()

        self._source_cache[drug.source_id] = drug_exposure.drug_exposure_id

        return drug_exposure

    async def transform_and_load_batch(
        self,
        drugs: list[tuple[SourceDrug, int, int | None]],
    ) -> DrugETLResult:
        """Transform and load a batch of drugs."""
        result = DrugETLResult()

        for drug, person_id, visit_id in drugs:
            result.total_processed += 1

            try:
                existing = await self._find_existing_drug(drug.source_id) if drug.source_id else None

                drug_exp = await self.transform_and_load(drug, person_id, visit_id)

                if existing:
                    result.drugs_updated += 1
                else:
                    result.drugs_created += 1

                if drug_exp.drug_concept_id == 0:
                    result.unmapped_codes += 1

                if result.total_processed % self.config.batch_size == 0:
                    await self.session.commit()

            except Exception as e:
                result.errors.append(f"Error processing {drug.source_id}: {e}")
                logger.warning(f"ETL error for drug {drug.source_id}: {e}")

        await self.session.commit()

        return result

    def get_stats(self) -> dict[str, Any]:
        """Get ETL service statistics."""
        return {
            "cached_mappings": len(self._source_cache),
            "cached_concepts": len(self._concept_cache),
        }
