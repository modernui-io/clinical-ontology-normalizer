"""FHIR R4 Validation API endpoints.

Dir-CI-3.2: Endpoints for validating FHIR resources against R4 base spec
and US Core profile requirements.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.schemas.fhir_validation import (
    BundleValidationResult,
    FHIRValidationResult,
    USCoreConformanceResult,
    ValidateBundleRequest,
    ValidateResourceRequest,
    USCoreCheckRequest,
)
from app.services.fhir_validator import get_fhir_validator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fhir", tags=["fhir-validation"])


@router.post(
    "/validate",
    response_model=FHIRValidationResult,
    summary="Validate a single FHIR R4 resource",
    description=(
        "Validates a FHIR R4 resource against the base specification. "
        "Checks resourceType, required fields, date formats, reference "
        "format, and coding system validity."
    ),
)
async def validate_resource(
    request: ValidateResourceRequest,
) -> FHIRValidationResult:
    """Validate a single FHIR R4 resource."""
    validator = get_fhir_validator()
    return validator.validate_resource(request.resource)


@router.post(
    "/validate-bundle",
    response_model=BundleValidationResult,
    summary="Validate a FHIR R4 Bundle",
    description=(
        "Validates a FHIR R4 Bundle and each resource it contains. "
        "Returns per-resource validation results plus bundle-level issues."
    ),
)
async def validate_bundle(
    request: ValidateBundleRequest,
) -> BundleValidationResult:
    """Validate a FHIR R4 Bundle and its contained resources."""
    validator = get_fhir_validator()
    return validator.validate_bundle(request.bundle)


@router.post(
    "/us-core-check",
    response_model=USCoreConformanceResult,
    summary="Check US Core profile conformance",
    description=(
        "Checks a FHIR R4 resource against its US Core STU3.1.1 profile. "
        "Supported resource types: Patient, Condition, Observation, "
        "MedicationRequest, Procedure."
    ),
)
async def us_core_check(
    request: USCoreCheckRequest,
) -> USCoreConformanceResult:
    """Check a FHIR resource against its US Core profile."""
    validator = get_fhir_validator()
    return validator.check_us_core_conformance(request.resource)
