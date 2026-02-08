"""Schemas for FHIR R4 resource validation and US Core profile conformance."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class IssueSeverity(str, Enum):
    """Severity level for validation issues, aligned with FHIR OperationOutcome."""

    ERROR = "error"
    WARNING = "warning"
    INFORMATION = "information"


class FHIRValidationIssue(BaseModel):
    """A single validation issue found in a FHIR resource."""

    severity: IssueSeverity = Field(..., description="Issue severity level")
    path: str = Field(..., description="FHIRPath to the problematic element")
    message: str = Field(..., description="Human-readable description of the issue")
    rule_id: str = Field(
        ..., description="Identifier for the validation rule that was violated"
    )


class FHIRValidationResult(BaseModel):
    """Result of validating a single FHIR resource."""

    resource_type: str | None = Field(
        None, description="The resourceType of the validated resource"
    )
    is_valid: bool = Field(..., description="Whether the resource passed validation")
    issues: list[FHIRValidationIssue] = Field(
        default_factory=list, description="List of validation issues found"
    )
    profile_checked: str | None = Field(
        None,
        description="The profile URI that was checked, if any",
    )


class BundleValidationResult(BaseModel):
    """Result of validating an entire FHIR Bundle."""

    total_resources: int = Field(
        ..., description="Total number of resources in the Bundle"
    )
    valid_count: int = Field(
        ..., description="Number of resources that passed validation"
    )
    invalid_count: int = Field(
        ..., description="Number of resources that failed validation"
    )
    results: list[FHIRValidationResult] = Field(
        default_factory=list,
        description="Per-resource validation results",
    )
    bundle_issues: list[FHIRValidationIssue] = Field(
        default_factory=list,
        description="Issues with the Bundle itself (not individual resources)",
    )


class USCoreConformanceResult(BaseModel):
    """Result of checking a FHIR resource against its US Core profile."""

    resource_type: str | None = Field(
        None, description="The resourceType that was checked"
    )
    profile: str = Field(
        ..., description="US Core profile URI that was checked against"
    )
    is_conformant: bool = Field(
        ..., description="Whether the resource conforms to the US Core profile"
    )
    missing_elements: list[str] = Field(
        default_factory=list,
        description="Required US Core elements that are missing",
    )
    issues: list[FHIRValidationIssue] = Field(
        default_factory=list, description="Detailed conformance issues"
    )


# -- Request schemas for API endpoints --


class ValidateResourceRequest(BaseModel):
    """Request body for single-resource validation."""

    resource: dict[str, Any] = Field(
        ..., description="FHIR R4 resource to validate"
    )


class ValidateBundleRequest(BaseModel):
    """Request body for Bundle validation."""

    bundle: dict[str, Any] = Field(
        ..., description="FHIR R4 Bundle to validate"
    )


class USCoreCheckRequest(BaseModel):
    """Request body for US Core conformance check."""

    resource: dict[str, Any] = Field(
        ..., description="FHIR R4 resource to check against US Core profile"
    )
