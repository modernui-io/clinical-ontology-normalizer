"""Procedure Occurrence Table ETL Service.

This module provides ETL functionality for transforming source procedure
data into the OMOP CDM Procedure_Occurrence table.

The service handles:
    - CPT/HCPCS/ICD-10-PCS to SNOMED CT concept mapping
    - Procedure date normalization
    - Provider/visit linking

Standard OMOP Procedure Type Concept IDs:
    32817 - EHR encounter record
    32821 - EHR administration record
    32840 - Claim procedure
    32879 - Registry
    44786631 - Primary Procedure
    44786632 - Secondary Procedure

Usage:
    from app.etl import ProcedureETL
    from app.connectors import SourceProcedure, ProcedureStatus

    etl = ProcedureETL(db_session)

    procedure = SourceProcedure(
        source_id="PROC001",
        patient_source_id="PAT001",
        procedure_code="99213",
        procedure_code_system="CPT",
        procedure_name="Office visit, est patient",
        procedure_date=datetime(2024, 1, 15),
        status=ProcedureStatus.COMPLETED
    )

    proc_occ = await etl.transform_and_load(procedure, person_id=1)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import ProcedureStatus, SourceProcedure
from app.etl.concept_mappings import (
    CODE_SYSTEM_VOCABULARY_MAP,
    DEFAULT_PROCEDURE_TYPE_CONCEPT_ID,
    PROCEDURE_TYPE_CONCEPT_MAP,
)
from app.models.omop import ProcedureOccurrence

logger = logging.getLogger(__name__)


# Extended procedure type mapping for additional categories
PROCEDURE_TYPE_EXTENDED_MAP = {
    **PROCEDURE_TYPE_CONCEPT_MAP,
    "primary": 44786631,
    "secondary": 44786632,
}

# Procedure Status to OMOP handling (module-specific, not in concept_mappings)
PROCEDURE_STATUS_MAP = {
    ProcedureStatus.COMPLETED: True,  # Include in CDM
    ProcedureStatus.IN_PROGRESS: True,
    ProcedureStatus.NOT_DONE: False,  # May exclude
    ProcedureStatus.UNKNOWN: True,
}


@dataclass
class ProcedureETLConfig:
    """Configuration for Procedure ETL service."""

    map_to_standard: bool = True
    preserve_source_codes: bool = True
    default_procedure_type: int = DEFAULT_PROCEDURE_TYPE_CONCEPT_ID
    include_cancelled: bool = False
    batch_size: int = 1000


@dataclass
class ProcedureETLResult:
    """Result of Procedure ETL operation."""

    total_processed: int = 0
    procedures_created: int = 0
    procedures_updated: int = 0
    procedures_skipped: int = 0
    unmapped_codes: int = 0
    errors: list[str] = field(default_factory=list)


class ProcedureETL:
    """ETL service for transforming SourceProcedure to OMOP ProcedureOccurrence.

    Handles CPT/HCPCS mapping and procedure status filtering.

    Example:
        etl = ProcedureETL(session)
        proc_occ = await etl.transform_and_load(source_procedure, person_id=123)
    """

    def __init__(
        self,
        session: AsyncSession,
        config: ProcedureETLConfig | None = None,
        vocabulary_service: Any | None = None,
    ):
        """Initialize Procedure ETL service."""
        self.session = session
        self.config = config or ProcedureETLConfig()
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
        """Look up OMOP concept ID for a procedure code."""
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

    def _normalize_dates(
        self,
        procedure: SourceProcedure,
    ) -> tuple[date, datetime | None, date | None, datetime | None]:
        """Normalize procedure dates."""
        proc_date: date
        proc_datetime: datetime | None = None

        if procedure.procedure_date:
            if isinstance(procedure.procedure_date, datetime):
                proc_date = procedure.procedure_date.date()
                proc_datetime = procedure.procedure_date
            else:
                proc_date = procedure.procedure_date
        else:
            proc_date = date.today()

        # End date (typically same day for procedures)
        end_date: date | None = None
        end_datetime: datetime | None = None

        if procedure.end_date:
            if isinstance(procedure.end_date, datetime):
                end_date = procedure.end_date.date()
                end_datetime = procedure.end_date
            else:
                end_date = procedure.end_date

        return proc_date, proc_datetime, end_date, end_datetime

    def _should_include_procedure(self, procedure: SourceProcedure) -> bool:
        """Check if procedure should be included in CDM."""
        if not procedure.status:
            return True

        if procedure.status == ProcedureStatus.NOT_DONE:
            return self.config.include_cancelled

        return PROCEDURE_STATUS_MAP.get(procedure.status, True)

    async def _find_existing_procedure(
        self,
        source_id: str,
    ) -> ProcedureOccurrence | None:
        """Find existing ProcedureOccurrence by source ID."""
        if source_id in self._source_cache:
            stmt = select(ProcedureOccurrence).where(
                ProcedureOccurrence.procedure_occurrence_id == self._source_cache[source_id]
            )
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        stmt = select(ProcedureOccurrence).where(
            ProcedureOccurrence.procedure_source_value == source_id
        )
        result = await self.session.execute(stmt)
        proc = result.scalar_one_or_none()

        if proc:
            self._source_cache[source_id] = proc.procedure_occurrence_id

        return proc

    async def transform(
        self,
        procedure: SourceProcedure,
        person_id: int,
        visit_occurrence_id: int | None = None,
        provider_id: int | None = None,
    ) -> dict[str, Any]:
        """Transform SourceProcedure to ProcedureOccurrence attributes."""
        # Map concepts
        concept_id, source_concept_id = await self._lookup_concept_id(
            procedure.procedure_code or "",
            procedure.procedure_code_system,
        )

        # Normalize dates
        proc_date, proc_datetime, end_date, end_datetime = self._normalize_dates(procedure)

        # Build source value
        source_value = procedure.procedure_code
        if procedure.procedure_code_system:
            source_value = f"{procedure.procedure_code_system}:{procedure.procedure_code}"

        return {
            "person_id": person_id,
            "procedure_concept_id": concept_id,
            "procedure_date": proc_date,
            "procedure_datetime": proc_datetime,
            "procedure_end_date": end_date,
            "procedure_end_datetime": end_datetime,
            "procedure_type_concept_id": self.config.default_procedure_type,
            "modifier_concept_id": None,
            "quantity": procedure.quantity,
            "provider_id": provider_id,
            "visit_occurrence_id": visit_occurrence_id,
            "visit_detail_id": None,
            "procedure_source_value": source_value[:50] if source_value else None,
            "procedure_source_concept_id": source_concept_id,
            "modifier_source_value": procedure.modifier[:50] if procedure.modifier else None,
        }

    async def transform_and_load(
        self,
        procedure: SourceProcedure,
        person_id: int,
        visit_occurrence_id: int | None = None,
        provider_id: int | None = None,
    ) -> ProcedureOccurrence | None:
        """Transform and load a single procedure.

        Returns:
            Created/updated ProcedureOccurrence or None if skipped.
        """
        if not procedure.source_id:
            raise ValueError("Procedure must have a source_id")

        # Check if should include
        if not self._should_include_procedure(procedure):
            return None

        existing = await self._find_existing_procedure(procedure.source_id)

        proc_data = await self.transform(
            procedure, person_id, visit_occurrence_id, provider_id
        )

        if existing:
            for key, value in proc_data.items():
                if value is not None:
                    setattr(existing, key, value)
            await self.session.flush()
            return existing

        proc_occ = ProcedureOccurrence(**proc_data)
        self.session.add(proc_occ)
        await self.session.flush()

        self._source_cache[procedure.source_id] = proc_occ.procedure_occurrence_id

        return proc_occ

    async def transform_and_load_batch(
        self,
        procedures: list[tuple[SourceProcedure, int, int | None]],
    ) -> ProcedureETLResult:
        """Transform and load a batch of procedures."""
        result = ProcedureETLResult()

        for procedure, person_id, visit_id in procedures:
            result.total_processed += 1

            try:
                existing = await self._find_existing_procedure(procedure.source_id) if procedure.source_id else None

                proc_occ = await self.transform_and_load(
                    procedure, person_id, visit_id
                )

                if proc_occ is None:
                    result.procedures_skipped += 1
                elif existing:
                    result.procedures_updated += 1
                else:
                    result.procedures_created += 1

                if proc_occ and proc_occ.procedure_concept_id == 0:
                    result.unmapped_codes += 1

                if result.total_processed % self.config.batch_size == 0:
                    await self.session.commit()

            except Exception as e:
                result.errors.append(f"Error processing {procedure.source_id}: {e}")
                logger.warning(f"ETL error for procedure {procedure.source_id}: {e}")

        await self.session.commit()

        return result

    def get_stats(self) -> dict[str, Any]:
        """Get ETL service statistics."""
        return {
            "cached_mappings": len(self._source_cache),
            "cached_concepts": len(self._concept_cache),
        }
