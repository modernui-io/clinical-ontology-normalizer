"""Data Lineage API endpoints.

CDO-1: Data Lineage Tracking - REST endpoints for querying lineage
information about ClinicalFacts.

Endpoints:
    GET /lineage/facts/{fact_id}              - Lineage for a single fact
    GET /lineage/patients/{patient_id}        - All lineage for a patient
    GET /lineage/patients/{patient_id}/summary - Summary stats for a patient
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.lineage import DataLineageRecordResponse, LineageSummary
from app.services import lineage_service

router = APIRouter(prefix="/lineage", tags=["lineage"])


@router.get(
    "/facts/{fact_id}",
    response_model=list[DataLineageRecordResponse],
    summary="Get lineage for a clinical fact",
    description="Returns all lineage records showing where a ClinicalFact came from and how it was derived.",
)
async def get_fact_lineage(
    fact_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[DataLineageRecordResponse]:
    """Get lineage records for a specific ClinicalFact."""
    records = await lineage_service.get_fact_lineage(db, fact_id)
    return [DataLineageRecordResponse.model_validate(r) for r in records]


@router.get(
    "/patients/{patient_id}",
    response_model=list[DataLineageRecordResponse],
    summary="Get lineage for all patient facts",
    description="Returns all lineage records for every ClinicalFact belonging to a patient.",
)
async def get_patient_lineage(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[DataLineageRecordResponse]:
    """Get all lineage records for a patient's ClinicalFacts."""
    records = await lineage_service.get_patient_lineage(db, patient_id)
    return [DataLineageRecordResponse.model_validate(r) for r in records]


@router.get(
    "/patients/{patient_id}/summary",
    response_model=LineageSummary,
    summary="Get lineage summary for a patient",
    description="Returns aggregated lineage statistics including source distribution, average confidence, and extraction methods.",
)
async def get_patient_lineage_summary(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
) -> LineageSummary:
    """Get aggregated lineage statistics for a patient."""
    return await lineage_service.get_lineage_summary(db, patient_id)
