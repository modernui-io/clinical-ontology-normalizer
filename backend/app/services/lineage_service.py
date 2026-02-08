"""Data Lineage Service.

CDO-1: Data Lineage Tracking - service layer for recording and querying
lineage information about ClinicalFacts.

All operations are async and use the same SQLAlchemy async patterns
as the rest of the codebase.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinical_fact import ClinicalFact
from app.models.data_lineage import DataLineageRecord, SourceType
from app.schemas.lineage import (
    DataLineageRecordResponse,
    LineageSourceDistribution,
    LineageSummary,
    SourceType as SourceTypeSchema,
)

logger = logging.getLogger(__name__)


async def record_lineage(
    session: AsyncSession,
    fact_id: UUID | str,
    source_type: SourceType | str,
    *,
    source_document_id: UUID | str | None = None,
    source_resource_type: str | None = None,
    source_resource_id: str | None = None,
    extraction_method: str | None = None,
    extraction_confidence: float | None = None,
    transformation_chain: list[dict[str, Any]] | None = None,
) -> DataLineageRecord:
    """Record lineage for a ClinicalFact.

    This is designed to be lightweight and non-blocking.
    It creates a single append-only record linking a fact to its origin.

    Args:
        session: Async database session.
        fact_id: UUID of the ClinicalFact.
        source_type: How the fact was produced.
        source_document_id: Optional FK to the source document.
        source_resource_type: FHIR resource type (e.g., "Condition").
        source_resource_id: Original FHIR resource ID.
        extraction_method: Method used (e.g., "fhir_direct_mapping").
        extraction_confidence: Confidence score 0-1.
        transformation_chain: Ordered list of transformations.

    Returns:
        The created DataLineageRecord.
    """
    # Normalize source_type to string value if it's an enum
    if isinstance(source_type, SourceType):
        source_type_val = source_type.value
    else:
        source_type_val = source_type

    record = DataLineageRecord(
        clinical_fact_id=str(fact_id),
        source_type=source_type_val,
        source_document_id=str(source_document_id) if source_document_id else None,
        source_resource_type=source_resource_type,
        source_resource_id=source_resource_id,
        extraction_method=extraction_method,
        extraction_confidence=extraction_confidence,
        transformation_chain=transformation_chain,
    )
    session.add(record)
    await session.flush()

    logger.debug(
        "Recorded lineage for fact %s: source=%s, method=%s",
        fact_id,
        source_type_val,
        extraction_method,
    )
    return record


async def get_fact_lineage(
    session: AsyncSession,
    fact_id: UUID | str,
) -> list[DataLineageRecord]:
    """Get all lineage records for a specific ClinicalFact.

    Args:
        session: Async database session.
        fact_id: UUID of the ClinicalFact.

    Returns:
        List of DataLineageRecord instances (may be empty).
    """
    stmt = (
        select(DataLineageRecord)
        .where(DataLineageRecord.clinical_fact_id == str(fact_id))
        .order_by(DataLineageRecord.created_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_patient_lineage(
    session: AsyncSession,
    patient_id: str,
) -> list[DataLineageRecord]:
    """Get all lineage records for a patient's ClinicalFacts.

    Joins through clinical_facts to find all lineage for a patient.

    Args:
        session: Async database session.
        patient_id: Patient identifier.

    Returns:
        List of DataLineageRecord instances.
    """
    stmt = (
        select(DataLineageRecord)
        .join(ClinicalFact, DataLineageRecord.clinical_fact_id == ClinicalFact.id)
        .where(ClinicalFact.patient_id == patient_id)
        .order_by(DataLineageRecord.created_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_lineage_summary(
    session: AsyncSession,
    patient_id: str,
) -> LineageSummary:
    """Get aggregated lineage statistics for a patient.

    Computes source distribution, average confidence, and
    distinct extraction methods in a small number of queries.

    Args:
        session: Async database session.
        patient_id: Patient identifier.

    Returns:
        LineageSummary with aggregated stats.
    """
    # Base join condition
    base_join = (
        select(DataLineageRecord)
        .join(ClinicalFact, DataLineageRecord.clinical_fact_id == ClinicalFact.id)
        .where(ClinicalFact.patient_id == patient_id)
    )

    # 1. Total count
    count_stmt = select(func.count()).select_from(base_join.subquery())
    total_result = await session.execute(count_stmt)
    total_facts = total_result.scalar() or 0

    if total_facts == 0:
        return LineageSummary(
            patient_id=patient_id,
            total_facts=0,
            source_distribution=[],
            avg_confidence=None,
            extraction_methods=[],
            earliest_record=None,
            latest_record=None,
        )

    # 2. Source distribution
    dist_stmt = (
        select(
            DataLineageRecord.source_type,
            func.count().label("cnt"),
        )
        .join(ClinicalFact, DataLineageRecord.clinical_fact_id == ClinicalFact.id)
        .where(ClinicalFact.patient_id == patient_id)
        .group_by(DataLineageRecord.source_type)
    )
    dist_result = await session.execute(dist_stmt)
    source_distribution = []
    for row in dist_result.all():
        source_distribution.append(
            LineageSourceDistribution(
                source_type=SourceTypeSchema(row[0]),
                count=row[1],
                percentage=round((row[1] / total_facts) * 100, 2),
            )
        )

    # 3. Average confidence
    avg_stmt = (
        select(func.avg(DataLineageRecord.extraction_confidence))
        .join(ClinicalFact, DataLineageRecord.clinical_fact_id == ClinicalFact.id)
        .where(ClinicalFact.patient_id == patient_id)
        .where(DataLineageRecord.extraction_confidence.isnot(None))
    )
    avg_result = await session.execute(avg_stmt)
    avg_confidence_raw = avg_result.scalar()
    avg_confidence = round(float(avg_confidence_raw), 4) if avg_confidence_raw is not None else None

    # 4. Distinct extraction methods
    methods_stmt = (
        select(func.distinct(DataLineageRecord.extraction_method))
        .join(ClinicalFact, DataLineageRecord.clinical_fact_id == ClinicalFact.id)
        .where(ClinicalFact.patient_id == patient_id)
        .where(DataLineageRecord.extraction_method.isnot(None))
    )
    methods_result = await session.execute(methods_stmt)
    extraction_methods = [row[0] for row in methods_result.all()]

    # 5. Time range
    time_stmt = (
        select(
            func.min(DataLineageRecord.created_at),
            func.max(DataLineageRecord.created_at),
        )
        .join(ClinicalFact, DataLineageRecord.clinical_fact_id == ClinicalFact.id)
        .where(ClinicalFact.patient_id == patient_id)
    )
    time_result = await session.execute(time_stmt)
    time_row = time_result.one()

    return LineageSummary(
        patient_id=patient_id,
        total_facts=total_facts,
        source_distribution=source_distribution,
        avg_confidence=avg_confidence,
        extraction_methods=extraction_methods,
        earliest_record=time_row[0],
        latest_record=time_row[1],
    )
