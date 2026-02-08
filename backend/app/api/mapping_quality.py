"""Mapping Quality API endpoints.

CTO-4: OMOP Mapping Quality - endpoints for coverage dashboard,
unmapped terms, domain coverage breakdown, and quality trends.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.mapping_quality import (
    MappingQualityReport,
    MappingTrendReport,
    UnmappedTerm,
    DomainCoverage,
)
from app.services.mapping_quality_service import get_mapping_quality_service

router = APIRouter(prefix="/data-quality/mapping", tags=["Data Quality"])


@router.get(
    "",
    response_model=MappingQualityReport,
    summary="Overall mapping quality report",
    description=(
        "Returns comprehensive OMOP mapping quality metrics including "
        "coverage percentage, confidence distribution, ambiguity rate, "
        "domain coverage, and mapping source breakdown."
    ),
)
async def get_mapping_quality_report(
    domain: str | None = Query(None, description="Filter by OMOP domain"),
    db: AsyncSession = Depends(get_db),
) -> MappingQualityReport:
    """Get overall mapping quality report."""
    service = get_mapping_quality_service()
    return await service.get_mapping_quality_report(db, domain_filter=domain)


@router.get(
    "/unmapped",
    response_model=list[UnmappedTerm],
    summary="Top unmapped terms",
    description=(
        "Returns the most frequently occurring mention texts that have "
        "no OMOP concept candidates, sorted by frequency descending."
    ),
)
async def get_unmapped_terms(
    limit: int = Query(50, ge=1, le=500, description="Max terms to return"),
    domain: str | None = Query(None, description="Filter by domain"),
    db: AsyncSession = Depends(get_db),
) -> list[UnmappedTerm]:
    """Get top unmapped terms."""
    service = get_mapping_quality_service()
    return await service.get_unmapped_terms(db, limit=limit, domain=domain)


@router.get(
    "/coverage",
    response_model=list[DomainCoverage],
    summary="Per-domain coverage breakdown",
    description=(
        "Returns mapping coverage statistics broken down by OMOP domain "
        "(condition, drug, procedure, measurement, observation, etc.)."
    ),
)
async def get_domain_coverage(
    db: AsyncSession = Depends(get_db),
) -> list[DomainCoverage]:
    """Get per-domain coverage breakdown."""
    service = get_mapping_quality_service()
    return await service.get_mapping_coverage_by_domain(db)


@router.get(
    "/trends",
    response_model=MappingTrendReport,
    summary="Quality metrics over time",
    description=(
        "Returns mapping quality trend data over the specified period, "
        "showing daily coverage, mention counts, and average confidence."
    ),
)
async def get_mapping_trends(
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    db: AsyncSession = Depends(get_db),
) -> MappingTrendReport:
    """Get mapping quality trends over time."""
    service = get_mapping_quality_service()
    return await service.get_mapping_trends(db, days=days)
