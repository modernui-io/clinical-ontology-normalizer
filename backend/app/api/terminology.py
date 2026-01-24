"""FHIR R4 Terminology Services API endpoints.

This module provides FHIR R4 compliant REST API endpoints for terminology services.

Endpoints:
- POST /fhir/CodeSystem/$lookup - Returns concept details
- POST /fhir/CodeSystem/$validate-code - Validates a code
- POST /fhir/ValueSet/$expand - Expands a ValueSet
- POST /fhir/ConceptMap/$translate - Translates between code systems
- POST /fhir/CodeSystem/$subsumes - Tests subsumption relationship
- POST /fhir/ConceptMap/$closure - Computes transitive closure of relationships
- GET /fhir/CodeSystem/{id} - Gets a CodeSystem resource
- GET /fhir/ValueSet/{id} - Gets a ValueSet resource

All responses are FHIR R4 compliant, returning Parameters or resource types
as appropriate for each operation.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.fhir_terminology import (
    Coding,
    FHIRParametersBuilder,
    get_fhir_terminology_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fhir", tags=["terminology"])


# =============================================================================
# Request Models
# =============================================================================

class LookupRequest(BaseModel):
    """Request for $lookup operation."""

    system: str = Field(..., description="The code system URI")
    code: str = Field(..., description="The code to look up")
    version: str | None = Field(None, description="Code system version")
    coding: dict[str, Any] | None = Field(
        None,
        description="Alternative: provide coding with system and code"
    )
    property: list[str] | None = Field(
        None,
        description="Properties to return"
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "system": "http://snomed.info/sct",
                "code": "73211009"
            }
        }


class ValidateCodeRequest(BaseModel):
    """Request for $validate-code operation."""

    url: str | None = Field(None, description="ValueSet URL for validation")
    system: str = Field(..., description="The code system URI")
    code: str = Field(..., description="The code to validate")
    display: str | None = Field(None, description="Display text to validate")
    version: str | None = Field(None, description="Code system version")
    coding: dict[str, Any] | None = Field(
        None,
        description="Alternative: provide coding with system, code, and optional display"
    )
    codeableConcept: dict[str, Any] | None = Field(
        None,
        description="Alternative: provide CodeableConcept"
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "system": "http://snomed.info/sct",
                "code": "73211009",
                "display": "Diabetes mellitus"
            }
        }


class ExpandRequest(BaseModel):
    """Request for $expand operation."""

    url: str = Field(
        ...,
        description="The ValueSet URL to expand"
    )
    valueSet: dict[str, Any] | None = Field(
        None,
        description="Alternative: provide a complete ValueSet resource"
    )
    filter: str | None = Field(
        None,
        description="Text filter to apply during expansion"
    )
    offset: int = Field(
        0,
        description="Offset for pagination",
        ge=0
    )
    count: int = Field(
        100,
        description="Maximum number of codes to return",
        ge=1,
        le=1000
    )
    includeDesignations: bool = Field(
        False,
        description="Include designations in expansion"
    )
    activeOnly: bool = Field(
        False,
        description="Only include active codes"
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "url": "http://example.org/ValueSet/common-conditions",
                "filter": "diabetes",
                "count": 50
            }
        }


class TranslateRequest(BaseModel):
    """Request for $translate operation."""

    url: str | None = Field(
        None,
        description="ConceptMap URL to use for translation"
    )
    conceptMap: dict[str, Any] | None = Field(
        None,
        description="Alternative: provide a ConceptMap resource"
    )
    system: str = Field(
        ...,
        description="Source code system URI"
    )
    code: str = Field(
        ...,
        description="The code to translate"
    )
    version: str | None = Field(
        None,
        description="Source code system version"
    )
    source: str | None = Field(
        None,
        description="Source ValueSet URI"
    )
    coding: dict[str, Any] | None = Field(
        None,
        description="Alternative: provide source coding"
    )
    codeableConcept: dict[str, Any] | None = Field(
        None,
        description="Alternative: provide source CodeableConcept"
    )
    target: str | None = Field(
        None,
        description="Target ValueSet URI"
    )
    targetSystem: str = Field(
        ...,
        description="Target code system URI"
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "system": "http://snomed.info/sct",
                "code": "73211009",
                "targetSystem": "http://hl7.org/fhir/sid/icd-10-cm"
            }
        }


class ClosureRequest(BaseModel):
    """Request for $closure operation."""

    name: str = Field(
        ...,
        description="Identifier for the closure table"
    )
    concept: list[dict[str, Any]] = Field(
        ...,
        description="Concepts to include in the closure (list of Coding objects with system, code, display)"
    )
    version: str | None = Field(
        None,
        description="Code system version"
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "name": "diabetes-closure",
                "concept": [
                    {"system": "http://snomed.info/sct", "code": "73211009", "display": "Diabetes mellitus"},
                    {"system": "http://snomed.info/sct", "code": "46635009", "display": "Diabetes mellitus type 1"},
                    {"system": "http://snomed.info/sct", "code": "44054006", "display": "Diabetes mellitus type 2"}
                ]
            }
        }


class SubsumesRequest(BaseModel):
    """Request for $subsumes operation."""

    system: str = Field(
        ...,
        description="The code system URI"
    )
    codeA: str = Field(
        ...,
        description="The first code (potential subsumer)"
    )
    codeB: str = Field(
        ...,
        description="The second code (potentially subsumed)"
    )
    version: str | None = Field(
        None,
        description="Code system version"
    )
    codingA: dict[str, Any] | None = Field(
        None,
        description="Alternative: provide first coding"
    )
    codingB: dict[str, Any] | None = Field(
        None,
        description="Alternative: provide second coding"
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "system": "http://snomed.info/sct",
                "codeA": "73211009",
                "codeB": "46635009"
            }
        }


# =============================================================================
# $lookup Operation
# =============================================================================

@router.post("/CodeSystem/$lookup", response_model=None)
async def lookup_code(request: LookupRequest) -> dict[str, Any]:
    """Look up a code in a code system.

    Returns concept details including display name, designations, and properties.

    This is a FHIR R4 compliant $lookup operation.

    Args:
        request: Lookup request with system and code

    Returns:
        FHIR Parameters resource with lookup results

    Raises:
        HTTPException: 404 if code not found, 400 for invalid request
    """
    service = get_fhir_terminology_service()

    # Handle alternative coding parameter
    system = request.system
    code = request.code
    if request.coding:
        system = request.coding.get("system", system)
        code = request.coding.get("code", code)

    if not system or not code:
        raise HTTPException(
            status_code=400,
            detail={
                "resourceType": "OperationOutcome",
                "issue": [{
                    "severity": "error",
                    "code": "required",
                    "diagnostics": "Both system and code are required"
                }]
            }
        )

    result = service.lookup(
        system=system,
        code=code,
        version=request.version,
        properties=request.property
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "resourceType": "OperationOutcome",
                "issue": [{
                    "severity": "error",
                    "code": "not-found",
                    "diagnostics": f"Code '{code}' not found in system '{system}'"
                }]
            }
        )

    return FHIRParametersBuilder.build_lookup_parameters(result)


@router.get("/CodeSystem/$lookup", response_model=None)
async def lookup_code_get(
    system: str = Query(..., description="The code system URI"),
    code: str = Query(..., description="The code to look up"),
    version: str | None = Query(None, description="Code system version"),
) -> dict[str, Any]:
    """Look up a code in a code system (GET variant).

    GET variant of the $lookup operation for simpler queries.
    """
    service = get_fhir_terminology_service()

    result = service.lookup(system=system, code=code, version=version)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "resourceType": "OperationOutcome",
                "issue": [{
                    "severity": "error",
                    "code": "not-found",
                    "diagnostics": f"Code '{code}' not found in system '{system}'"
                }]
            }
        )

    return FHIRParametersBuilder.build_lookup_parameters(result)


# =============================================================================
# $validate-code Operation
# =============================================================================

@router.post("/CodeSystem/$validate-code", response_model=None)
async def validate_code(request: ValidateCodeRequest) -> dict[str, Any]:
    """Validate that a code is valid within a code system.

    This is a FHIR R4 compliant $validate-code operation.

    Args:
        request: Validation request with system, code, and optional display

    Returns:
        FHIR Parameters resource with validation result
    """
    service = get_fhir_terminology_service()

    # Handle alternative parameters
    system = request.system
    code = request.code
    display = request.display

    if request.coding:
        system = request.coding.get("system", system)
        code = request.coding.get("code", code)
        display = request.coding.get("display", display)

    if request.codeableConcept:
        codings = request.codeableConcept.get("coding", [])
        if codings:
            system = codings[0].get("system", system)
            code = codings[0].get("code", code)
            display = codings[0].get("display", display)

    if not system or not code:
        raise HTTPException(
            status_code=400,
            detail={
                "resourceType": "OperationOutcome",
                "issue": [{
                    "severity": "error",
                    "code": "required",
                    "diagnostics": "Both system and code are required"
                }]
            }
        )

    result = service.validate_code(
        system=system,
        code=code,
        display=display,
        version=request.version
    )

    return FHIRParametersBuilder.build_validate_code_parameters(result)


@router.get("/CodeSystem/$validate-code", response_model=None)
async def validate_code_get(
    system: str = Query(..., description="The code system URI"),
    code: str = Query(..., description="The code to validate"),
    display: str | None = Query(None, description="Display text to validate"),
    version: str | None = Query(None, description="Code system version"),
) -> dict[str, Any]:
    """Validate that a code is valid (GET variant)."""
    service = get_fhir_terminology_service()

    result = service.validate_code(
        system=system,
        code=code,
        display=display,
        version=version
    )

    return FHIRParametersBuilder.build_validate_code_parameters(result)


# =============================================================================
# $expand Operation
# =============================================================================

@router.post("/ValueSet/$expand", response_model=None)
async def expand_valueset(request: ExpandRequest) -> dict[str, Any]:
    """Expand a ValueSet to list its contained codes.

    This is a FHIR R4 compliant $expand operation.

    Args:
        request: Expansion request with ValueSet URL and optional filter

    Returns:
        FHIR ValueSet resource with expansion
    """
    service = get_fhir_terminology_service()

    # Get URL from request or inline ValueSet
    url = request.url
    if request.valueSet and not url:
        url = request.valueSet.get("url", "")

    if not url:
        raise HTTPException(
            status_code=400,
            detail={
                "resourceType": "OperationOutcome",
                "issue": [{
                    "severity": "error",
                    "code": "required",
                    "diagnostics": "ValueSet URL is required"
                }]
            }
        )

    expansion = service.expand(
        value_set_url=url,
        filter_text=request.filter,
        offset=request.offset,
        count=request.count
    )

    if expansion is None:
        raise HTTPException(
            status_code=404,
            detail={
                "resourceType": "OperationOutcome",
                "issue": [{
                    "severity": "error",
                    "code": "not-found",
                    "diagnostics": f"ValueSet '{url}' not found or could not be expanded"
                }]
            }
        )

    return FHIRParametersBuilder.build_expansion_valueset(url, expansion)


@router.get("/ValueSet/$expand", response_model=None)
async def expand_valueset_get(
    url: str = Query(..., description="The ValueSet URL to expand"),
    filter: str | None = Query(None, description="Text filter to apply"),
    offset: int = Query(0, ge=0, alias="_offset", description="Offset for pagination"),
    count: int = Query(20, ge=1, le=100, alias="_count", description="Maximum codes to return (max 100)"),
) -> dict[str, Any]:
    """Expand a ValueSet (GET variant)."""
    service = get_fhir_terminology_service()

    expansion = service.expand(
        value_set_url=url,
        filter_text=filter,
        offset=offset,
        count=count
    )

    if expansion is None:
        raise HTTPException(
            status_code=404,
            detail={
                "resourceType": "OperationOutcome",
                "issue": [{
                    "severity": "error",
                    "code": "not-found",
                    "diagnostics": f"ValueSet '{url}' not found"
                }]
            }
        )

    return FHIRParametersBuilder.build_expansion_valueset(url, expansion)


# =============================================================================
# $translate Operation
# =============================================================================

@router.post("/ConceptMap/$translate", response_model=None)
async def translate_code(request: TranslateRequest) -> dict[str, Any]:
    """Translate a code from one code system to another.

    This is a FHIR R4 compliant $translate operation.

    Args:
        request: Translation request with source system/code and target system

    Returns:
        FHIR Parameters resource with translation matches
    """
    service = get_fhir_terminology_service()

    # Handle alternative parameters
    system = request.system
    code = request.code

    if request.coding:
        system = request.coding.get("system", system)
        code = request.coding.get("code", code)

    if request.codeableConcept:
        codings = request.codeableConcept.get("coding", [])
        if codings:
            system = codings[0].get("system", system)
            code = codings[0].get("code", code)

    if not system or not code or not request.targetSystem:
        raise HTTPException(
            status_code=400,
            detail={
                "resourceType": "OperationOutcome",
                "issue": [{
                    "severity": "error",
                    "code": "required",
                    "diagnostics": "system, code, and targetSystem are required"
                }]
            }
        )

    result = service.translate(
        source_system=system,
        code=code,
        target_system=request.targetSystem,
        concept_map_url=request.url
    )

    return FHIRParametersBuilder.build_translate_parameters(result)


@router.get("/ConceptMap/$translate", response_model=None)
async def translate_code_get(
    system: str = Query(..., description="Source code system URI"),
    code: str = Query(..., description="The code to translate"),
    targetSystem: str = Query(..., description="Target code system URI"),
    url: str | None = Query(None, description="ConceptMap URL to use"),
) -> dict[str, Any]:
    """Translate a code (GET variant)."""
    service = get_fhir_terminology_service()

    result = service.translate(
        source_system=system,
        code=code,
        target_system=targetSystem,
        concept_map_url=url
    )

    return FHIRParametersBuilder.build_translate_parameters(result)


# =============================================================================
# $subsumes Operation
# =============================================================================

@router.post("/CodeSystem/$subsumes", response_model=None)
async def test_subsumes(request: SubsumesRequest) -> dict[str, Any]:
    """Test the subsumption relationship between two codes.

    Tests if codeA subsumes codeB (i.e., codeA is an ancestor of codeB).

    This is a FHIR R4 compliant $subsumes operation.

    Args:
        request: Subsumption request with system and two codes

    Returns:
        FHIR Parameters resource with subsumption outcome:
        - "equivalent": The codes are equivalent
        - "subsumes": codeA subsumes codeB
        - "subsumed-by": codeB subsumes codeA
        - "not-subsumed": Neither code subsumes the other
    """
    service = get_fhir_terminology_service()

    # Handle alternative parameters
    system = request.system
    codeA = request.codeA
    codeB = request.codeB

    if request.codingA:
        system = request.codingA.get("system", system)
        codeA = request.codingA.get("code", codeA)

    if request.codingB:
        system = request.codingB.get("system", system)
        codeB = request.codingB.get("code", codeB)

    if not system or not codeA or not codeB:
        raise HTTPException(
            status_code=400,
            detail={
                "resourceType": "OperationOutcome",
                "issue": [{
                    "severity": "error",
                    "code": "required",
                    "diagnostics": "system, codeA, and codeB are required"
                }]
            }
        )

    result = service.subsumes(
        system=system,
        codeA=codeA,
        codeB=codeB
    )

    return FHIRParametersBuilder.build_subsumes_parameters(result)


@router.get("/CodeSystem/$subsumes", response_model=None)
async def test_subsumes_get(
    system: str = Query(..., description="The code system URI"),
    codeA: str = Query(..., description="The first code (potential subsumer)"),
    codeB: str = Query(..., description="The second code (potentially subsumed)"),
) -> dict[str, Any]:
    """Test subsumption relationship (GET variant)."""
    service = get_fhir_terminology_service()

    result = service.subsumes(system=system, codeA=codeA, codeB=codeB)

    return FHIRParametersBuilder.build_subsumes_parameters(result)


# =============================================================================
# $closure Operation
# =============================================================================

@router.post("/ConceptMap/$closure", response_model=None)
async def closure_operation(request: ClosureRequest) -> dict[str, Any]:
    """Compute the transitive closure of subsumption relationships.

    Given a set of concepts, returns a ConceptMap containing all subsumption
    relationships between them (direct and transitive).

    This is a FHIR R4 compliant $closure operation. It is primarily useful
    for hierarchical code systems like SNOMED CT and ICD-10-CM.

    Args:
        request: Closure request with name and list of concepts

    Returns:
        FHIR ConceptMap resource with closure relationships

    Raises:
        HTTPException: 400 if request is invalid
    """
    service = get_fhir_terminology_service()

    if not request.concept:
        raise HTTPException(
            status_code=400,
            detail={
                "resourceType": "OperationOutcome",
                "issue": [{
                    "severity": "error",
                    "code": "required",
                    "diagnostics": "At least one concept is required"
                }]
            }
        )

    # Convert request concepts to Coding objects
    concepts: list[Coding] = []
    for c in request.concept:
        system = c.get("system", "")
        code = c.get("code", "")
        display = c.get("display", "")

        if not system or not code:
            raise HTTPException(
                status_code=400,
                detail={
                    "resourceType": "OperationOutcome",
                    "issue": [{
                        "severity": "error",
                        "code": "required",
                        "diagnostics": "Each concept must have 'system' and 'code'"
                    }]
                }
            )

        concepts.append(Coding(system=system, code=code, display=display))

    result = service.closure(name=request.name, concepts=concepts)

    return FHIRParametersBuilder.build_closure_concept_map(result)


# =============================================================================
# CodeSystem Resource Endpoints
# =============================================================================

@router.get("/CodeSystem/{system_id}", response_model=None)
async def get_code_system(system_id: str) -> dict[str, Any]:
    """Get a CodeSystem resource by ID.

    Supported code systems:
    - snomed-ct (SNOMED CT)
    - icd-10-cm (ICD-10-CM)
    - rxnorm (RxNorm)
    - cpt (CPT)
    - loinc (LOINC)

    Args:
        system_id: The code system identifier

    Returns:
        FHIR CodeSystem resource

    Raises:
        HTTPException: 404 if code system not found
    """
    service = get_fhir_terminology_service()

    code_system = service.get_code_system(system_id)

    if code_system is None:
        raise HTTPException(
            status_code=404,
            detail={
                "resourceType": "OperationOutcome",
                "issue": [{
                    "severity": "error",
                    "code": "not-found",
                    "diagnostics": f"CodeSystem '{system_id}' not found. "
                                   f"Supported: snomed-ct, icd-10-cm, rxnorm, cpt, loinc"
                }]
            }
        )

    return code_system


@router.get("/CodeSystem", response_model=None)
async def list_code_systems(
    _count: int = Query(20, ge=1, le=100, alias="_count", description="Number of results per page"),
    _offset: int = Query(0, ge=0, alias="_offset", description="Offset for pagination"),
) -> dict[str, Any]:
    """List all available code systems with pagination.

    Returns:
        FHIR Bundle with available CodeSystem resources and pagination links
    """
    service = get_fhir_terminology_service()
    stats = service.get_stats()

    all_entries = []
    for system_id, system_stats in stats.get("code_systems", {}).items():
        code_system = service.get_code_system(system_id)
        if code_system:
            all_entries.append({
                "fullUrl": f"CodeSystem/{system_id}",
                "resource": code_system
            })

    total = len(all_entries)
    paginated_entries = all_entries[_offset:_offset + _count]

    links = [{"relation": "self", "url": f"/fhir/CodeSystem?_count={_count}&_offset={_offset}"}]
    if _offset + _count < total:
        links.append({"relation": "next", "url": f"/fhir/CodeSystem?_count={_count}&_offset={_offset + _count}"})
    if _offset > 0:
        prev_offset = max(0, _offset - _count)
        links.append({"relation": "previous", "url": f"/fhir/CodeSystem?_count={_count}&_offset={prev_offset}"})

    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": total,
        "link": links,
        "entry": paginated_entries
    }


# =============================================================================
# ValueSet Resource Endpoints
# =============================================================================

@router.get("/ValueSet/{value_set_id}", response_model=None)
async def get_value_set(value_set_id: str) -> dict[str, Any]:
    """Get a ValueSet resource by ID.

    Supported value sets:
    - common-conditions
    - common-medications
    - common-procedures
    - common-lab-tests

    Args:
        value_set_id: The value set identifier

    Returns:
        FHIR ValueSet resource

    Raises:
        HTTPException: 404 if value set not found
    """
    service = get_fhir_terminology_service()

    value_set = service.get_value_set(value_set_id)

    if value_set is None:
        raise HTTPException(
            status_code=404,
            detail={
                "resourceType": "OperationOutcome",
                "issue": [{
                    "severity": "error",
                    "code": "not-found",
                    "diagnostics": f"ValueSet '{value_set_id}' not found. "
                                   f"Supported: common-conditions, common-medications, "
                                   f"common-procedures, common-lab-tests"
                }]
            }
        )

    return value_set


@router.get("/ValueSet", response_model=None)
async def list_value_sets(
    _count: int = Query(20, ge=1, le=100, alias="_count", description="Number of results per page"),
    _offset: int = Query(0, ge=0, alias="_offset", description="Offset for pagination"),
) -> dict[str, Any]:
    """List all available value sets with pagination.

    Returns:
        FHIR Bundle with available ValueSet resources and pagination links
    """
    service = get_fhir_terminology_service()

    value_set_ids = [
        "common-conditions",
        "common-medications",
        "common-procedures",
        "common-lab-tests"
    ]

    all_entries = []
    for vs_id in value_set_ids:
        value_set = service.get_value_set(vs_id)
        if value_set:
            all_entries.append({
                "fullUrl": f"ValueSet/{vs_id}",
                "resource": value_set
            })

    total = len(all_entries)
    paginated_entries = all_entries[_offset:_offset + _count]

    links = [{"relation": "self", "url": f"/fhir/ValueSet?_count={_count}&_offset={_offset}"}]
    if _offset + _count < total:
        links.append({"relation": "next", "url": f"/fhir/ValueSet?_count={_count}&_offset={_offset + _count}"})
    if _offset > 0:
        prev_offset = max(0, _offset - _count)
        links.append({"relation": "previous", "url": f"/fhir/ValueSet?_count={_count}&_offset={prev_offset}"})

    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": total,
        "link": links,
        "entry": paginated_entries
    }


# =============================================================================
# Statistics Endpoint
# =============================================================================

@router.get("/terminology/stats", response_model=None)
async def get_terminology_stats() -> dict[str, Any]:
    """Get statistics about available terminology data.

    Returns:
        Statistics for all loaded code systems including concept counts.
    """
    service = get_fhir_terminology_service()
    return service.get_stats()
