"""Cohort Phenotype API Endpoints (CSO-2.3).

Structured phenotype definitions for clinical trial cohort identification.
Replaces simple ILIKE string matching with concept set matching using
OMOP concept IDs, ICD codes, and text patterns.

Endpoints:
- GET  /cohort-phenotypes           - List all phenotype definitions
- GET  /cohort-phenotypes/{name}    - Get specific phenotype
- POST /cohort-phenotypes           - Create/update phenotype definition
- POST /cohort-phenotypes/{name}/match - Test phenotype against patient facts
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.schemas.phenotype import (
    PatientFact,
    Phenotype,
    PhenotypeCreate,
    PhenotypeLibrary,
    PhenotypeMatch,
)
from app.services.phenotype_service import get_phenotype_definition_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cohort-phenotypes", tags=["Cohort Phenotypes"])


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "",
    response_model=PhenotypeLibrary,
    summary="List all phenotype definitions",
    description=(
        "Returns all registered phenotype definitions including pre-loaded "
        "phenotypes for Regeneron clinical trials (DME, Atopic Dermatitis, "
        "Cutaneous SCC)."
    ),
)
def list_phenotypes() -> PhenotypeLibrary:
    """List all registered phenotype definitions."""
    service = get_phenotype_definition_service()
    return service.list_phenotypes()


@router.get(
    "/{name}",
    response_model=Phenotype,
    summary="Get specific phenotype definition",
    description="Returns a single phenotype definition by its unique name.",
)
def get_phenotype(name: str) -> Phenotype:
    """Get a specific phenotype definition by name.

    Args:
        name: The unique phenotype name.

    Returns:
        The phenotype definition.

    Raises:
        HTTPException 404: If phenotype not found.
    """
    service = get_phenotype_definition_service()
    phenotype = service.get_phenotype(name)
    if phenotype is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Phenotype '{name}' not found",
        )
    return phenotype


@router.post(
    "",
    response_model=Phenotype,
    status_code=status.HTTP_201_CREATED,
    summary="Create or update a phenotype definition",
    description=(
        "Register a new phenotype definition or update an existing one. "
        "A phenotype is a structured definition of a clinical condition "
        "using OMOP concept IDs, ICD codes, and text patterns."
    ),
)
def create_phenotype(create: PhenotypeCreate) -> Phenotype:
    """Create or update a phenotype definition.

    Args:
        create: The phenotype definition to register.

    Returns:
        The created/updated phenotype.
    """
    service = get_phenotype_definition_service()
    phenotype = service.define_phenotype_from_schema(create)
    logger.info(f"Created/updated phenotype via API: {create.name}")
    return phenotype


@router.post(
    "/{name}/match",
    response_model=PhenotypeMatch,
    summary="Test phenotype against patient facts",
    description=(
        "Match a phenotype definition against a list of patient clinical facts. "
        "Uses three matching strategies in order of confidence: "
        "OMOP concept ID (1.0), ICD code prefix (0.95), text pattern (0.80)."
    ),
)
def match_phenotype(
    name: str,
    facts: list[PatientFact],
) -> PhenotypeMatch:
    """Test a phenotype against a patient's clinical facts.

    Args:
        name: The phenotype name to test.
        facts: List of patient clinical facts.

    Returns:
        PhenotypeMatch with match status, confidence, and matched facts.

    Raises:
        HTTPException 404: If phenotype not found.
    """
    service = get_phenotype_definition_service()
    phenotype = service.get_phenotype(name)
    if phenotype is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Phenotype '{name}' not found",
        )

    # Convert PatientFact models to dicts for the service
    fact_dicts = [f.model_dump() for f in facts]
    return service.match_phenotype(fact_dicts, phenotype)


@router.delete(
    "/{name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a phenotype definition",
    description="Remove a phenotype definition from the registry.",
)
def delete_phenotype(name: str) -> None:
    """Delete a phenotype definition.

    Args:
        name: The phenotype name to delete.

    Raises:
        HTTPException 404: If phenotype not found.
    """
    service = get_phenotype_definition_service()
    deleted = service.delete_phenotype(name)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Phenotype '{name}' not found",
        )


@router.get(
    "/stats/summary",
    summary="Get phenotype service statistics",
    description="Returns statistics about registered phenotypes.",
)
def get_stats() -> dict[str, Any]:
    """Get phenotype service statistics."""
    service = get_phenotype_definition_service()
    return service.get_stats()
