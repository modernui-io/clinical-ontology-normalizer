"""Value Set schemas for clinical trial criteria matching.

Dir-CI-3.3: Pydantic schemas for value set management.  A value set is a
curated list of codes from one or more code systems (SNOMED, ICD-10, LOINC,
RxNorm) that define a clinical concept for matching purposes.

Example:
    "Diabetes Mellitus" value set = {
        ICD-10: E10, E10.9, E11, E11.9, E13;
        SNOMED: 73211009, 44054006, 46635009
    }
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class CodeSystem(str, Enum):
    """Supported clinical code systems."""

    ICD10CM = "ICD10CM"
    SNOMED = "SNOMED"
    LOINC = "LOINC"
    RXNORM = "RxNorm"
    CPT = "CPT"


# =============================================================================
# Core Models
# =============================================================================


class CodeMember(BaseModel):
    """A single code member within a value set."""

    code: str = Field(..., description="The code value (e.g., 'E11.9')")
    code_system: CodeSystem = Field(..., description="Code system this code belongs to")
    display_name: str = Field("", description="Human-readable display name")
    is_active: bool = Field(True, description="Whether this code is currently active")

    model_config = {"json_schema_extra": {
        "example": {
            "code": "E11.9",
            "code_system": "ICD10CM",
            "display_name": "Type 2 diabetes mellitus without complications",
            "is_active": True,
        }
    }}


class ValueSetSchema(BaseModel):
    """A curated list of codes defining a clinical concept for matching."""

    name: str = Field(..., description="Unique name for the value set")
    oid: str | None = Field(None, description="Object Identifier (OID) for the value set")
    version: str = Field("1.0.0", description="Semantic version string")
    description: str | None = Field(None, description="Human-readable description")
    code_system: CodeSystem | None = Field(
        None,
        description="Primary code system (None if multi-system)",
    )
    codes: list[CodeMember] = Field(
        default_factory=list,
        description="Codes belonging to this value set",
    )
    domain: str | None = Field(
        None,
        description="Clinical domain (e.g., 'Endocrinology', 'Dermatology')",
    )
    created_at: datetime | None = Field(None, description="Creation timestamp")
    updated_at: datetime | None = Field(None, description="Last update timestamp")

    model_config = {"json_schema_extra": {
        "example": {
            "name": "diabetes_mellitus",
            "oid": "2.16.840.1.113883.3.464.1003.103.12.1001",
            "version": "1.0.0",
            "description": "Diabetes Mellitus diagnosis codes",
            "code_system": "ICD10CM",
            "codes": [
                {
                    "code": "E11",
                    "code_system": "ICD10CM",
                    "display_name": "Type 2 diabetes mellitus",
                    "is_active": True,
                }
            ],
            "domain": "Endocrinology",
        }
    }}


# =============================================================================
# Expansion and Membership Schemas
# =============================================================================


class ValueSetExpansion(BaseModel):
    """Result of expanding a value set to all its constituent codes.

    Expansion resolves hierarchical codes (e.g., ICD-10 prefix matching)
    to produce a flat list of all matching codes.
    """

    value_set_name: str = Field(..., description="Name of the expanded value set")
    total_codes: int = Field(..., description="Total number of codes in expansion")
    codes: list[CodeMember] = Field(
        default_factory=list,
        description="All codes in the expansion",
    )


class MembershipCheck(BaseModel):
    """Result of checking whether a code belongs to a value set."""

    code: str = Field(..., description="The code that was checked")
    code_system: str = Field(..., description="Code system of the checked code")
    value_set_name: str = Field(..., description="Value set checked against")
    is_member: bool = Field(..., description="Whether the code is a member")
    matched_code: str | None = Field(
        None,
        description="The code in the value set that matched (may differ for hierarchical matches)",
    )


# =============================================================================
# API Request / Response Schemas
# =============================================================================


class ValueSetCreate(BaseModel):
    """Request schema for creating a new value set."""

    name: str = Field(..., description="Unique name for the value set")
    oid: str | None = Field(None, description="OID for the value set")
    code_system: CodeSystem | None = Field(None, description="Primary code system")
    codes: list[CodeMember] = Field(
        default_factory=list,
        description="Initial codes",
    )
    description: str | None = Field(None, description="Description")
    version: str = Field("1.0.0", description="Version string")
    domain: str | None = Field(None, description="Clinical domain")


class ValueSetUpdate(BaseModel):
    """Request schema for updating a value set."""

    codes_to_add: list[CodeMember] = Field(
        default_factory=list,
        description="Codes to add to the value set",
    )
    codes_to_remove: list[CodeMember] = Field(
        default_factory=list,
        description="Codes to remove from the value set",
    )
    new_version: str | None = Field(
        None,
        description="New version string (required when modifying codes)",
    )


class ValueSetListResponse(BaseModel):
    """Response containing a list of value sets."""

    value_sets: list[ValueSetSchema] = Field(
        default_factory=list,
        description="List of value sets",
    )
    total: int = Field(0, description="Total count")
