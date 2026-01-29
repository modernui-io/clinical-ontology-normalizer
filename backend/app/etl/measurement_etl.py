"""Measurement Table ETL Service.

This module provides ETL functionality for transforming source measurement
data (lab results, vital signs) into the OMOP CDM Measurement table.

The service handles:
    - LOINC concept mapping
    - Unit standardization to UCUM
    - Reference range handling
    - Value type detection (numeric vs categorical)

Standard OMOP Measurement Type Concept IDs:
    32817 - EHR encounter record
    32836 - EHR vital signs
    32856 - Lab
    32879 - Registry

Common Vital Sign LOINC Codes:
    8310-5 - Body temperature
    8867-4 - Heart rate
    9279-1 - Respiratory rate
    8480-6 - Systolic BP
    8462-4 - Diastolic BP
    29463-7 - Body weight
    8302-2 - Body height
    39156-5 - BMI
    2708-6 - Oxygen saturation

Usage:
    from app.etl import MeasurementETL
    from app.connectors import SourceMeasurement

    etl = MeasurementETL(db_session)

    measurement = SourceMeasurement(
        source_id="LAB001",
        patient_source_id="PAT001",
        measurement_code="2345-7",
        measurement_code_system="LOINC",
        measurement_name="Glucose [Mass/volume] in Serum",
        value_numeric=126.0,
        unit="mg/dL",
        measurement_date=datetime(2024, 1, 15),
        range_low=70.0,
        range_high=100.0,
        abnormal_flag="H"
    )

    meas = await etl.transform_and_load(measurement, person_id=1)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import SourceMeasurement
from app.etl.concept_mappings import (
    CODE_SYSTEM_VOCABULARY_MAP,
    DEFAULT_MEASUREMENT_TYPE_CONCEPT_ID,
    MEASUREMENT_TYPE_CONCEPT_MAP,
    OPERATOR_CONCEPT_MAP,
    UNIT_CONCEPT_MAP,
)
from app.models.omop import Measurement

logger = logging.getLogger(__name__)


@dataclass
class MeasurementETLConfig:
    """Configuration for Measurement ETL service."""

    map_to_standard: bool = True
    preserve_source_codes: bool = True
    default_measurement_type: int = DEFAULT_MEASUREMENT_TYPE_CONCEPT_ID
    batch_size: int = 1000


@dataclass
class MeasurementETLResult:
    """Result of Measurement ETL operation."""

    total_processed: int = 0
    measurements_created: int = 0
    measurements_updated: int = 0
    measurements_skipped: int = 0
    unmapped_codes: int = 0
    errors: list[str] = field(default_factory=list)


class MeasurementETL:
    """ETL service for transforming SourceMeasurement to OMOP Measurement.

    Handles LOINC mapping, unit standardization, and value processing.

    Example:
        etl = MeasurementETL(session)
        meas = await etl.transform_and_load(source_measurement, person_id=123)
    """

    def __init__(
        self,
        session: AsyncSession,
        config: MeasurementETLConfig | None = None,
        vocabulary_service: Any | None = None,
    ):
        """Initialize Measurement ETL service."""
        self.session = session
        self.config = config or MeasurementETLConfig()
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
        """Look up OMOP concept ID for a measurement code."""
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

    def _map_unit_concept(self, unit: str | None) -> int | None:
        """Map unit string to OMOP concept ID."""
        if not unit:
            return None
        # Try exact match first
        concept_id = UNIT_CONCEPT_MAP.get(unit)
        if concept_id:
            return concept_id
        # Try lowercase
        return UNIT_CONCEPT_MAP.get(unit.lower())

    def _parse_value(
        self,
        measurement: SourceMeasurement,
    ) -> tuple[Decimal | None, int | None, int | None]:
        """Parse measurement value.

        Returns:
            Tuple of (value_as_number, value_as_concept_id, operator_concept_id).
        """
        # Numeric value
        value_as_number: Decimal | None = None
        value_as_concept_id: int | None = None
        operator_concept_id: int | None = None

        if measurement.value_numeric is not None:
            try:
                value_as_number = Decimal(str(measurement.value_numeric))
            except (ValueError, TypeError):
                pass

        # Check for operator prefix in text value
        if measurement.value_text:
            text = measurement.value_text.strip()
            for op, concept in OPERATOR_CONCEPT_MAP.items():
                if text.startswith(op):
                    operator_concept_id = concept
                    # Try to extract number
                    try:
                        num_part = text[len(op):].strip()
                        value_as_number = Decimal(num_part)
                    except (ValueError, TypeError):
                        pass
                    break

            # Check for categorical values
            if value_as_number is None:
                # Could map to value_as_concept_id for coded values
                # (positive/negative, detected/not detected, etc.)
                pass

        return value_as_number, value_as_concept_id, operator_concept_id

    def _parse_range(
        self,
        measurement: SourceMeasurement,
    ) -> tuple[Decimal | None, Decimal | None]:
        """Parse reference range values."""
        range_low: Decimal | None = None
        range_high: Decimal | None = None

        if measurement.range_low is not None:
            try:
                range_low = Decimal(str(measurement.range_low))
            except (ValueError, TypeError):
                pass

        if measurement.range_high is not None:
            try:
                range_high = Decimal(str(measurement.range_high))
            except (ValueError, TypeError):
                pass

        return range_low, range_high

    def _normalize_date(
        self,
        measurement: SourceMeasurement,
    ) -> tuple[date, datetime | None]:
        """Normalize measurement date."""
        meas_date: date
        meas_datetime: datetime | None = None

        if measurement.measurement_date:
            if isinstance(measurement.measurement_date, datetime):
                meas_date = measurement.measurement_date.date()
                meas_datetime = measurement.measurement_date
            else:
                meas_date = measurement.measurement_date
        else:
            meas_date = date.today()

        return meas_date, meas_datetime

    def _determine_measurement_type(
        self,
        measurement: SourceMeasurement,
    ) -> int:
        """Determine measurement type concept ID."""
        # Check measurement_type field
        if measurement.measurement_type:
            mtype = measurement.measurement_type.lower()
            concept_id = MEASUREMENT_TYPE_CONCEPT_MAP.get(mtype)
            if concept_id:
                return concept_id

        # Check code system for hints
        if measurement.measurement_code_system:
            if "loinc" in measurement.measurement_code_system.lower():
                # Could further distinguish lab vs vital based on LOINC code
                return 32856  # Lab

        return self.config.default_measurement_type

    async def _find_existing_measurement(
        self,
        source_id: str,
    ) -> Measurement | None:
        """Find existing Measurement by source ID."""
        if source_id in self._source_cache:
            stmt = select(Measurement).where(
                Measurement.measurement_id == self._source_cache[source_id]
            )
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        stmt = select(Measurement).where(
            Measurement.measurement_source_value == source_id
        )
        result = await self.session.execute(stmt)
        meas = result.scalar_one_or_none()

        if meas:
            self._source_cache[source_id] = meas.measurement_id

        return meas

    async def transform(
        self,
        measurement: SourceMeasurement,
        person_id: int,
        visit_occurrence_id: int | None = None,
        provider_id: int | None = None,
    ) -> dict[str, Any]:
        """Transform SourceMeasurement to Measurement attributes."""
        # Map concepts
        concept_id, source_concept_id = await self._lookup_concept_id(
            measurement.measurement_code or "",
            measurement.measurement_code_system,
        )

        # Map unit
        unit_concept_id = self._map_unit_concept(measurement.unit)

        # Parse values
        value_as_number, value_as_concept_id, operator_concept_id = self._parse_value(measurement)

        # Parse range
        range_low, range_high = self._parse_range(measurement)

        # Normalize date
        meas_date, meas_datetime = self._normalize_date(measurement)

        # Determine type
        type_concept_id = self._determine_measurement_type(measurement)

        # Build source value
        source_value = measurement.measurement_code
        if measurement.measurement_code_system:
            source_value = f"{measurement.measurement_code_system}:{measurement.measurement_code}"

        return {
            "person_id": person_id,
            "measurement_concept_id": concept_id,
            "measurement_date": meas_date,
            "measurement_datetime": meas_datetime,
            "measurement_time": None,
            "measurement_type_concept_id": type_concept_id,
            "operator_concept_id": operator_concept_id,
            "value_as_number": value_as_number,
            "value_as_concept_id": value_as_concept_id,
            "unit_concept_id": unit_concept_id,
            "range_low": range_low,
            "range_high": range_high,
            "provider_id": provider_id,
            "visit_occurrence_id": visit_occurrence_id,
            "visit_detail_id": None,
            "measurement_source_value": source_value[:50] if source_value else None,
            "measurement_source_concept_id": source_concept_id,
            "unit_source_value": measurement.unit[:50] if measurement.unit else None,
            "unit_source_concept_id": None,
            "value_source_value": measurement.value_text[:50] if measurement.value_text else None,
            "measurement_event_id": None,
            "meas_event_field_concept_id": None,
        }

    async def transform_and_load(
        self,
        measurement: SourceMeasurement,
        person_id: int,
        visit_occurrence_id: int | None = None,
        provider_id: int | None = None,
    ) -> Measurement:
        """Transform and load a single measurement."""
        if not measurement.source_id:
            raise ValueError("Measurement must have a source_id")

        existing = await self._find_existing_measurement(measurement.source_id)

        meas_data = await self.transform(
            measurement, person_id, visit_occurrence_id, provider_id
        )

        if existing:
            for key, value in meas_data.items():
                if value is not None:
                    setattr(existing, key, value)
            await self.session.flush()
            return existing

        meas = Measurement(**meas_data)
        self.session.add(meas)
        await self.session.flush()

        self._source_cache[measurement.source_id] = meas.measurement_id

        return meas

    async def transform_and_load_batch(
        self,
        measurements: list[tuple[SourceMeasurement, int, int | None]],
    ) -> MeasurementETLResult:
        """Transform and load a batch of measurements."""
        result = MeasurementETLResult()

        for measurement, person_id, visit_id in measurements:
            result.total_processed += 1

            try:
                existing = await self._find_existing_measurement(measurement.source_id) if measurement.source_id else None

                meas = await self.transform_and_load(
                    measurement, person_id, visit_id
                )

                if existing:
                    result.measurements_updated += 1
                else:
                    result.measurements_created += 1

                if meas.measurement_concept_id == 0:
                    result.unmapped_codes += 1

                if result.total_processed % self.config.batch_size == 0:
                    await self.session.commit()

            except Exception as e:
                result.errors.append(f"Error processing {measurement.source_id}: {e}")
                logger.warning(f"ETL error for measurement {measurement.source_id}: {e}")

        await self.session.commit()

        return result

    def get_stats(self) -> dict[str, Any]:
        """Get ETL service statistics."""
        return {
            "cached_mappings": len(self._source_cache),
            "cached_concepts": len(self._concept_cache),
        }
