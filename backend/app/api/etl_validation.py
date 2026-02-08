"""ETL Validation API endpoints.

Dir-CI-3.4: Provides endpoints to validate the FHIR-to-OMOP ETL pipeline:
- POST /data-quality/etl/validate-resource - Validate single resource round-trip
- GET  /data-quality/etl/concept-accuracy  - Concept mapping accuracy report
- GET  /data-quality/etl/quality-checks    - Run ETL quality checks
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.etl_validation import (
    BatchETLValidationResult,
    ConceptMappingReport,
    ETLQualityReport,
    ETLValidationResult,
)
from app.services.etl_validation_service import ETLValidationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data-quality/etl", tags=["data-quality", "etl-validation"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ValidateResourceRequest(BaseModel):
    """Request body for single resource round-trip validation."""

    fhir_resource: dict[str, Any] = Field(
        ..., description="The source FHIR resource dict"
    )
    clinical_fact: dict[str, Any] = Field(
        ..., description="The resulting ClinicalFact dict"
    )


class ValidateBatchRequest(BaseModel):
    """Request body for batch validation."""

    fhir_bundle: dict[str, Any] = Field(
        ..., description="FHIR Bundle with entries"
    )
    clinical_facts: list[dict[str, Any]] = Field(
        ..., description="List of ClinicalFact dicts produced by the ETL"
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/validate-resource",
    response_model=ETLValidationResult,
    summary="Validate single FHIR resource round-trip",
    description=(
        "Compare a source FHIR resource against a resulting ClinicalFact to "
        "verify the ETL pipeline preserved concept mapping, dates, patient "
        "reference, values, and provenance."
    ),
)
async def validate_resource(
    request: ValidateResourceRequest,
) -> ETLValidationResult:
    """Validate a single FHIR resource -> ClinicalFact round-trip."""
    service = ETLValidationService()
    return service.validate_etl_round_trip(
        fhir_resource=request.fhir_resource,
        clinical_fact=request.clinical_fact,
    )


@router.post(
    "/validate-batch",
    response_model=BatchETLValidationResult,
    summary="Validate batch FHIR bundle round-trip",
    description=(
        "Validate all resources in a FHIR bundle against their corresponding "
        "ClinicalFacts. Returns aggregate stats and per-resource results."
    ),
)
async def validate_batch(
    request: ValidateBatchRequest,
) -> BatchETLValidationResult:
    """Validate a batch of FHIR resources from a bundle."""
    service = ETLValidationService()
    return service.validate_batch_etl(
        fhir_bundle=request.fhir_bundle,
        clinical_facts=request.clinical_facts,
    )


@router.get(
    "/concept-accuracy",
    response_model=ConceptMappingReport,
    summary="Concept mapping accuracy report",
    description=(
        "Analyze all ClinicalFacts in the database to report on OMOP concept "
        "mapping accuracy, including unmapped rates and domain mismatches."
    ),
)
async def get_concept_accuracy(
    session: AsyncSession = Depends(get_db),
) -> ConceptMappingReport:
    """Get concept mapping accuracy report."""
    service = ETLValidationService()
    return await service.validate_concept_mapping_accuracy(session)


@router.get(
    "/quality-checks",
    response_model=ETLQualityReport,
    summary="Run ETL quality checks",
    description=(
        "Run comprehensive quality checks on all ClinicalFacts: orphaned facts, "
        "duplicates, missing required fields, and value range violations."
    ),
)
async def run_quality_checks(
    session: AsyncSession = Depends(get_db),
) -> ETLQualityReport:
    """Run ETL quality checks."""
    service = ETLValidationService()
    return await service.run_etl_quality_checks(session)
