"""Value Set Management API Endpoints.

This module provides REST API endpoints for value set management:
- CRUD operations for value sets
- Expansion of value sets to codes
- Validation of codes against value sets
- Version history
- Import/Export (FHIR ValueSet format, CSV)

All endpoints follow FHIR R4 conventions where applicable.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.services.value_set_service import (
    FilterOperator,
    InclusionRule,
    InclusionRuleType,
    ValueSetCode,
    ValueSetStatus,
    ValueSetType,
    get_value_set_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/valuesets", tags=["valuesets"])


# =============================================================================
# Request/Response Models
# =============================================================================


class ValueSetCodeModel(BaseModel):
    """A code in a value set."""

    system: str = Field(..., description="Code system URI")
    code: str = Field(..., description="Code value")
    display: str = Field("", description="Display name")
    version: str | None = Field(None, description="Code system version")
    inactive: bool = Field(False, description="Whether code is inactive")
    abstract: bool = Field(False, description="Whether code is abstract")

    class Config:
        json_schema_extra = {
            "example": {
                "system": "http://snomed.info/sct",
                "code": "73211009",
                "display": "Diabetes mellitus",
            }
        }


class InclusionRuleModel(BaseModel):
    """A rule for including codes in an intensional value set."""

    rule_type: str = Field(..., description="Type of rule: code, filter, descendants, ancestors, value_set")
    system: str = Field(..., description="Code system URI")
    code: str | None = Field(None, description="Code for code/descendants/ancestors rules")
    filter_property: str | None = Field(None, description="Property for filter rules")
    filter_operator: str | None = Field(None, description="Operator for filter rules")
    filter_value: str | None = Field(None, description="Value for filter rules")
    value_set_id: str | None = Field(None, description="Value set ID for value_set rules")
    include: bool = Field(True, description="True for include, False for exclude")

    class Config:
        json_schema_extra = {
            "example": {
                "rule_type": "descendants",
                "system": "http://snomed.info/sct",
                "code": "73211009",
                "include": True,
            }
        }


class CreateValueSetRequest(BaseModel):
    """Request to create a new value set."""

    name: str = Field(..., description="Internal name of the value set")
    title: str | None = Field(None, description="Human-readable title")
    description: str | None = Field(None, description="Description of the value set")
    url: str | None = Field(None, description="Canonical URL")
    version: str = Field("1.0.0", description="Version string")
    status: str = Field("draft", description="Status: draft, active, retired")
    value_set_type: str = Field("extensional", description="Type: extensional or intensional")
    codes: list[ValueSetCodeModel] = Field(default_factory=list, description="Codes for extensional value sets")
    rules: list[InclusionRuleModel] = Field(default_factory=list, description="Rules for intensional value sets")
    publisher: str | None = Field(None, description="Publisher name")
    purpose: str | None = Field(None, description="Purpose of the value set")
    copyright: str | None = Field(None, description="Copyright notice")
    experimental: bool = Field(False, description="Whether this is experimental")
    immutable: bool = Field(False, description="Whether this is immutable")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "DiabetesDiagnoses",
                "title": "Diabetes Diagnoses",
                "description": "ICD-10 codes for diabetes mellitus",
                "status": "draft",
                "value_set_type": "extensional",
                "codes": [
                    {
                        "system": "http://hl7.org/fhir/sid/icd-10-cm",
                        "code": "E11.9",
                        "display": "Type 2 diabetes mellitus without complications",
                    }
                ],
            }
        }


class UpdateValueSetRequest(BaseModel):
    """Request to update a value set."""

    name: str | None = Field(None, description="Internal name")
    title: str | None = Field(None, description="Human-readable title")
    description: str | None = Field(None, description="Description")
    url: str | None = Field(None, description="Canonical URL")
    status: str | None = Field(None, description="Status: draft, active, retired")
    codes: list[ValueSetCodeModel] | None = Field(None, description="Codes (extensional only)")
    rules: list[InclusionRuleModel] | None = Field(None, description="Rules (intensional only)")
    publisher: str | None = Field(None, description="Publisher name")
    purpose: str | None = Field(None, description="Purpose")
    copyright: str | None = Field(None, description="Copyright notice")


class AddCodeRequest(BaseModel):
    """Request to add a code to a value set."""

    system: str = Field(..., description="Code system URI")
    code: str = Field(..., description="Code value")
    display: str = Field("", description="Display name")
    version: str | None = Field(None, description="Code system version")


class AddRuleRequest(BaseModel):
    """Request to add a rule to a value set."""

    rule_type: str = Field(..., description="Type of rule")
    system: str = Field(..., description="Code system URI")
    code: str | None = Field(None, description="Code value")
    filter_property: str | None = Field(None)
    filter_operator: str | None = Field(None)
    filter_value: str | None = Field(None)
    value_set_id: str | None = Field(None)
    include: bool = Field(True)


class CreateVersionRequest(BaseModel):
    """Request to create a new version."""

    new_version: str = Field(..., description="New version string")
    status: str = Field("draft", description="Status for the new version")
    notes: str | None = Field(None, description="Version notes")


class ExpandRequest(BaseModel):
    """Request to expand a value set."""

    filter: str | None = Field(None, description="Text filter")
    offset: int = Field(0, ge=0, description="Pagination offset")
    count: int = Field(1000, ge=1, le=10000, description="Maximum codes to return")
    active_only: bool = Field(False, description="Only include active codes")


class ValidateCodeRequest(BaseModel):
    """Request to validate a code."""

    system: str = Field(..., description="Code system URI")
    code: str = Field(..., description="Code value")
    display: str | None = Field(None, description="Display name to validate")


class ImportCSVRequest(BaseModel):
    """Request to import from CSV."""

    name: str = Field(..., description="Name for the value set")
    system: str = Field(..., description="Code system for all codes")
    title: str | None = Field(None, description="Title")
    description: str | None = Field(None, description="Description")
    code_column: str = Field("code", description="Name of the code column")
    display_column: str = Field("display", description="Name of the display column")


class ValueSetResponse(BaseModel):
    """Response containing a value set."""

    id: str
    name: str
    title: str | None
    description: str | None
    url: str | None
    version: str
    status: str
    value_set_type: str
    code_count: int
    rule_count: int
    publisher: str | None
    purpose: str | None
    copyright: str | None
    experimental: bool
    immutable: bool
    created_at: str
    updated_at: str


class ValueSetListResponse(BaseModel):
    """Response containing a list of value sets."""

    value_sets: list[ValueSetResponse]
    total: int
    offset: int
    limit: int


class ExpansionResponse(BaseModel):
    """Response containing value set expansion."""

    value_set_id: str
    value_set_url: str | None
    timestamp: str
    total: int
    offset: int
    codes: list[ValueSetCodeModel]


class ValidationResponse(BaseModel):
    """Response from code validation."""

    valid: bool
    message: str | None
    display: str | None
    code: str | None
    system: str | None


class VersionHistoryItem(BaseModel):
    """A version history item."""

    version_id: str
    version: str
    status: str
    created_at: str
    created_by: str | None
    notes: str | None
    code_count: int


class VersionHistoryResponse(BaseModel):
    """Response containing version history."""

    value_set_id: str
    versions: list[VersionHistoryItem]


# =============================================================================
# Helper Functions
# =============================================================================


def _to_response(vs: Any) -> ValueSetResponse:
    """Convert a ValueSet to a response model."""
    return ValueSetResponse(
        id=vs.id,
        name=vs.name,
        title=vs.title,
        description=vs.description,
        url=vs.url,
        version=vs.version,
        status=vs.status.value,
        value_set_type=vs.value_set_type.value,
        code_count=len(vs.codes),
        rule_count=len(vs.rules),
        publisher=vs.publisher,
        purpose=vs.purpose,
        copyright=vs.copyright,
        experimental=vs.experimental,
        immutable=vs.immutable,
        created_at=vs.created_at.isoformat(),
        updated_at=vs.updated_at.isoformat(),
    )


def _parse_codes(codes: list[ValueSetCodeModel]) -> list[ValueSetCode]:
    """Parse code models to ValueSetCode objects."""
    return [
        ValueSetCode(
            system=c.system,
            code=c.code,
            display=c.display,
            version=c.version,
            inactive=c.inactive,
            abstract=c.abstract,
        )
        for c in codes
    ]


def _parse_rules(rules: list[InclusionRuleModel]) -> list[InclusionRule]:
    """Parse rule models to InclusionRule objects."""
    result = []
    for r in rules:
        operator = None
        if r.filter_operator:
            try:
                operator = FilterOperator(r.filter_operator)
            except ValueError:
                operator = FilterOperator.EQUALS

        result.append(
            InclusionRule(
                rule_type=InclusionRuleType(r.rule_type),
                system=r.system,
                code=r.code,
                filter_property=r.filter_property,
                filter_operator=operator,
                filter_value=r.filter_value,
                value_set_id=r.value_set_id,
                include=r.include,
            )
        )
    return result


# =============================================================================
# CRUD Endpoints
# =============================================================================


@router.get("", response_model=ValueSetListResponse)
async def list_value_sets(
    status: str | None = Query(None, description="Filter by status"),
    value_set_type: str | None = Query(None, description="Filter by type"),
    search: str | None = Query(None, description="Search term"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
) -> ValueSetListResponse:
    """List all value sets with optional filtering and pagination.

    Args:
        status: Filter by status (draft, active, retired)
        value_set_type: Filter by type (extensional, intensional)
        search: Search term for name/title/description
        offset: Pagination offset
        limit: Maximum results to return

    Returns:
        List of value sets with total count
    """
    service = get_value_set_service()

    # Parse status filter
    status_filter = None
    if status:
        try:
            status_filter = ValueSetStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Must be one of: draft, active, retired",
            )

    # Parse type filter
    type_filter = None
    if value_set_type:
        try:
            type_filter = ValueSetType(value_set_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid type: {value_set_type}. Must be one of: extensional, intensional",
            )

    value_sets, total = service.list(
        status=status_filter,
        value_set_type=type_filter,
        search=search,
        offset=offset,
        limit=limit,
    )

    return ValueSetListResponse(
        value_sets=[_to_response(vs) for vs in value_sets],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.post("", response_model=ValueSetResponse)
async def create_value_set(request: CreateValueSetRequest) -> ValueSetResponse:
    """Create a new value set.

    Args:
        request: Value set creation request

    Returns:
        The created value set
    """
    service = get_value_set_service()

    try:
        # Parse status
        status = ValueSetStatus(request.status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {request.status}")

    try:
        # Parse type
        vs_type = ValueSetType(request.value_set_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid type: {request.value_set_type}")

    try:
        vs = service.create(
            name=request.name,
            value_set_type=vs_type,
            title=request.title,
            description=request.description,
            url=request.url,
            version=request.version,
            status=status,
            codes=_parse_codes(request.codes) if request.codes else None,
            rules=_parse_rules(request.rules) if request.rules else None,
            publisher=request.publisher,
            purpose=request.purpose,
            copyright=request.copyright,
            experimental=request.experimental,
            immutable=request.immutable,
        )
        return _to_response(vs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{value_set_id}", response_model=ValueSetResponse)
async def get_value_set(value_set_id: str) -> ValueSetResponse:
    """Get a value set by ID.

    Args:
        value_set_id: The value set ID

    Returns:
        The value set
    """
    service = get_value_set_service()
    vs = service.get(value_set_id)

    if not vs:
        raise HTTPException(status_code=404, detail=f"Value set '{value_set_id}' not found")

    return _to_response(vs)


@router.put("/{value_set_id}", response_model=ValueSetResponse)
async def update_value_set(value_set_id: str, request: UpdateValueSetRequest) -> ValueSetResponse:
    """Update an existing value set.

    Args:
        value_set_id: The value set ID
        request: Update request

    Returns:
        The updated value set
    """
    service = get_value_set_service()

    # Parse status if provided
    status = None
    if request.status:
        try:
            status = ValueSetStatus(request.status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {request.status}")

    try:
        vs = service.update(
            value_set_id=value_set_id,
            name=request.name,
            title=request.title,
            description=request.description,
            url=request.url,
            status=status,
            codes=_parse_codes(request.codes) if request.codes else None,
            rules=_parse_rules(request.rules) if request.rules else None,
            publisher=request.publisher,
            purpose=request.purpose,
            copyright=request.copyright,
        )

        if not vs:
            raise HTTPException(status_code=404, detail=f"Value set '{value_set_id}' not found")

        return _to_response(vs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{value_set_id}")
async def delete_value_set(value_set_id: str) -> dict[str, str]:
    """Delete a value set.

    Args:
        value_set_id: The value set ID

    Returns:
        Success message
    """
    service = get_value_set_service()

    if not service.delete(value_set_id):
        raise HTTPException(status_code=404, detail=f"Value set '{value_set_id}' not found")

    return {"message": f"Value set '{value_set_id}' deleted successfully"}


# =============================================================================
# Code Management Endpoints
# =============================================================================


@router.post("/{value_set_id}/codes", response_model=ValueSetResponse)
async def add_code(value_set_id: str, request: AddCodeRequest) -> ValueSetResponse:
    """Add a code to an extensional value set.

    Args:
        value_set_id: The value set ID
        request: Code to add

    Returns:
        The updated value set
    """
    service = get_value_set_service()

    try:
        vs = service.add_code(
            value_set_id=value_set_id,
            code=ValueSetCode(
                system=request.system,
                code=request.code,
                display=request.display,
                version=request.version,
            ),
        )

        if not vs:
            raise HTTPException(status_code=404, detail=f"Value set '{value_set_id}' not found")

        return _to_response(vs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{value_set_id}/codes")
async def remove_code(
    value_set_id: str,
    system: str = Query(..., description="Code system"),
    code: str = Query(..., description="Code value"),
) -> ValueSetResponse:
    """Remove a code from an extensional value set.

    Args:
        value_set_id: The value set ID
        system: Code system
        code: Code value

    Returns:
        The updated value set
    """
    service = get_value_set_service()

    try:
        vs = service.remove_code(value_set_id=value_set_id, system=system, code=code)

        if not vs:
            raise HTTPException(status_code=404, detail=f"Value set '{value_set_id}' not found")

        return _to_response(vs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{value_set_id}/rules", response_model=ValueSetResponse)
async def add_rule(value_set_id: str, request: AddRuleRequest) -> ValueSetResponse:
    """Add a rule to an intensional value set.

    Args:
        value_set_id: The value set ID
        request: Rule to add

    Returns:
        The updated value set
    """
    service = get_value_set_service()

    try:
        operator = None
        if request.filter_operator:
            operator = FilterOperator(request.filter_operator)

        vs = service.add_rule(
            value_set_id=value_set_id,
            rule=InclusionRule(
                rule_type=InclusionRuleType(request.rule_type),
                system=request.system,
                code=request.code,
                filter_property=request.filter_property,
                filter_operator=operator,
                filter_value=request.filter_value,
                value_set_id=request.value_set_id,
                include=request.include,
            ),
        )

        if not vs:
            raise HTTPException(status_code=404, detail=f"Value set '{value_set_id}' not found")

        return _to_response(vs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{value_set_id}/rules/{rule_index}")
async def remove_rule(value_set_id: str, rule_index: int) -> ValueSetResponse:
    """Remove a rule from an intensional value set.

    Args:
        value_set_id: The value set ID
        rule_index: Index of the rule to remove

    Returns:
        The updated value set
    """
    service = get_value_set_service()

    try:
        vs = service.remove_rule(value_set_id=value_set_id, rule_index=rule_index)

        if not vs:
            raise HTTPException(status_code=404, detail=f"Value set '{value_set_id}' not found")

        return _to_response(vs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Expansion and Validation Endpoints
# =============================================================================


@router.post("/{value_set_id}/expand", response_model=ExpansionResponse)
async def expand_value_set(value_set_id: str, request: ExpandRequest | None = None) -> ExpansionResponse:
    """Expand a value set to its contained codes.

    For extensional value sets, returns the enumerated codes.
    For intensional value sets, evaluates the rules to produce codes.

    Args:
        value_set_id: The value set ID
        request: Expansion parameters

    Returns:
        The expansion result with codes
    """
    service = get_value_set_service()

    # Use defaults if no request provided
    if request is None:
        request = ExpandRequest()

    expansion = service.expand(
        value_set_id=value_set_id,
        filter_text=request.filter,
        offset=request.offset,
        count=request.count,
        active_only=request.active_only,
    )

    if not expansion:
        raise HTTPException(status_code=404, detail=f"Value set '{value_set_id}' not found")

    return ExpansionResponse(
        value_set_id=expansion.value_set_id,
        value_set_url=expansion.value_set_url,
        timestamp=expansion.timestamp.isoformat(),
        total=expansion.total,
        offset=expansion.offset,
        codes=[
            ValueSetCodeModel(
                system=c.system,
                code=c.code,
                display=c.display,
                version=c.version,
                inactive=c.inactive,
                abstract=c.abstract,
            )
            for c in expansion.codes
        ],
    )


@router.get("/{value_set_id}/expand", response_model=ExpansionResponse)
async def expand_value_set_get(
    value_set_id: str,
    filter: str | None = Query(None, description="Text filter"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    count: int = Query(1000, ge=1, le=10000, description="Maximum codes"),
    active_only: bool = Query(False, description="Only active codes"),
) -> ExpansionResponse:
    """Expand a value set (GET variant for simple queries)."""
    request = ExpandRequest(filter=filter, offset=offset, count=count, active_only=active_only)
    return await expand_value_set(value_set_id, request)


@router.post("/{value_set_id}/validate", response_model=ValidationResponse)
async def validate_code(value_set_id: str, request: ValidateCodeRequest) -> ValidationResponse:
    """Validate that a code is in a value set.

    Args:
        value_set_id: The value set ID
        request: Code to validate

    Returns:
        Validation result
    """
    service = get_value_set_service()

    result = service.validate_code(
        value_set_id=value_set_id,
        system=request.system,
        code=request.code,
        display=request.display,
    )

    return ValidationResponse(
        valid=result.valid,
        message=result.message,
        display=result.display,
        code=result.code,
        system=result.system,
    )


@router.get("/{value_set_id}/validate", response_model=ValidationResponse)
async def validate_code_get(
    value_set_id: str,
    system: str = Query(..., description="Code system"),
    code: str = Query(..., description="Code value"),
    display: str | None = Query(None, description="Display name"),
) -> ValidationResponse:
    """Validate a code (GET variant)."""
    request = ValidateCodeRequest(system=system, code=code, display=display)
    return await validate_code(value_set_id, request)


# =============================================================================
# Version History Endpoints
# =============================================================================


@router.get("/{value_set_id}/versions", response_model=VersionHistoryResponse)
async def get_version_history(value_set_id: str) -> VersionHistoryResponse:
    """Get the version history of a value set.

    Args:
        value_set_id: The value set ID

    Returns:
        Version history
    """
    service = get_value_set_service()

    # Check if value set exists
    vs = service.get(value_set_id)
    if not vs:
        raise HTTPException(status_code=404, detail=f"Value set '{value_set_id}' not found")

    history = service.get_version_history(value_set_id)

    return VersionHistoryResponse(
        value_set_id=value_set_id,
        versions=[
            VersionHistoryItem(
                version_id=v.version_id,
                version=v.version,
                status=v.status.value,
                created_at=v.created_at.isoformat(),
                created_by=v.created_by,
                notes=v.notes,
                code_count=v.code_count,
            )
            for v in history
        ],
    )


@router.post("/{value_set_id}/versions", response_model=ValueSetResponse)
async def create_version(value_set_id: str, request: CreateVersionRequest) -> ValueSetResponse:
    """Create a new version of a value set.

    Args:
        value_set_id: The value set ID
        request: Version creation request

    Returns:
        The updated value set
    """
    service = get_value_set_service()

    try:
        status = ValueSetStatus(request.status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {request.status}")

    vs = service.create_version(
        value_set_id=value_set_id,
        new_version=request.new_version,
        status=status,
        notes=request.notes,
    )

    if not vs:
        raise HTTPException(status_code=404, detail=f"Value set '{value_set_id}' not found")

    return _to_response(vs)


@router.post("/{value_set_id}/activate", response_model=ValueSetResponse)
async def activate_value_set(value_set_id: str) -> ValueSetResponse:
    """Activate a value set (change status from draft to active).

    Args:
        value_set_id: The value set ID

    Returns:
        The updated value set
    """
    service = get_value_set_service()

    try:
        vs = service.activate(value_set_id)

        if not vs:
            raise HTTPException(status_code=404, detail=f"Value set '{value_set_id}' not found")

        return _to_response(vs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{value_set_id}/retire", response_model=ValueSetResponse)
async def retire_value_set(value_set_id: str) -> ValueSetResponse:
    """Retire a value set.

    Args:
        value_set_id: The value set ID

    Returns:
        The updated value set
    """
    service = get_value_set_service()

    vs = service.retire(value_set_id)

    if not vs:
        raise HTTPException(status_code=404, detail=f"Value set '{value_set_id}' not found")

    return _to_response(vs)


# =============================================================================
# Import/Export Endpoints
# =============================================================================


@router.post("/import", response_model=ValueSetResponse)
async def import_value_set(fhir_value_set: dict[str, Any]) -> ValueSetResponse:
    """Import a value set from FHIR ValueSet format.

    Args:
        fhir_value_set: FHIR ValueSet resource

    Returns:
        The imported value set
    """
    service = get_value_set_service()

    if fhir_value_set.get("resourceType") != "ValueSet":
        raise HTTPException(
            status_code=400,
            detail="Invalid FHIR resource. Expected resourceType: ValueSet",
        )

    try:
        vs = service.import_fhir(fhir_value_set)
        return _to_response(vs)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to import value set: {str(e)}")


@router.post("/import/csv", response_model=ValueSetResponse)
async def import_csv(
    file: UploadFile = File(..., description="CSV file to import"),
    name: str = Form(..., description="Name for the value set"),
    system: str = Form(..., description="Code system for all codes"),
    title: str | None = Form(None, description="Title"),
    description: str | None = Form(None, description="Description"),
    code_column: str = Form("code", description="Name of code column"),
    display_column: str = Form("display", description="Name of display column"),
) -> ValueSetResponse:
    """Import a value set from CSV format.

    Args:
        file: CSV file
        name: Name for the value set
        system: Code system
        title: Optional title
        description: Optional description
        code_column: Name of the code column
        display_column: Name of the display column

    Returns:
        The imported value set
    """
    service = get_value_set_service()

    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV file")

    try:
        contents = await file.read()
        csv_data = contents.decode("utf-8")

        vs = service.import_csv(
            csv_data=csv_data,
            name=name,
            system=system,
            title=title,
            description=description,
            code_column=code_column,
            display_column=display_column,
        )
        return _to_response(vs)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to import CSV: {str(e)}")


@router.get("/{value_set_id}/export")
async def export_value_set(
    value_set_id: str,
    format: str = Query("fhir", description="Export format: fhir or csv"),
    include_expansion: bool = Query(False, description="Include expansion in FHIR export"),
) -> Response:
    """Export a value set to FHIR or CSV format.

    Args:
        value_set_id: The value set ID
        format: Export format (fhir or csv)
        include_expansion: Include expansion in FHIR export

    Returns:
        Exported data
    """
    service = get_value_set_service()

    if format == "fhir":
        fhir_vs = service.export_fhir(value_set_id, include_expansion=include_expansion)
        if not fhir_vs:
            raise HTTPException(status_code=404, detail=f"Value set '{value_set_id}' not found")

        return Response(
            content=str(fhir_vs),
            media_type="application/fhir+json",
            headers={
                "Content-Disposition": f'attachment; filename="{value_set_id}.json"'
            },
        )

    elif format == "csv":
        csv_data = service.export_csv(value_set_id)
        if not csv_data:
            raise HTTPException(status_code=404, detail=f"Value set '{value_set_id}' not found")

        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{value_set_id}.csv"'
            },
        )

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid format: {format}. Must be 'fhir' or 'csv'",
        )


# =============================================================================
# Statistics Endpoint
# =============================================================================


@router.get("/stats", response_model=dict)
async def get_stats() -> dict[str, Any]:
    """Get statistics about value sets.

    Returns:
        Value set statistics
    """
    service = get_value_set_service()
    return service.get_stats()
