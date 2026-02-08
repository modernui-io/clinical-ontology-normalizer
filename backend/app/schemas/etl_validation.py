"""ETL Validation schemas for FHIR-to-OMOP pipeline validation.

Dir-CI-3.4: Schemas for ETL round-trip validation, concept mapping accuracy,
and data quality checks on the FHIR import pipeline.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ComparisonType(str, Enum):
    """How two field values were compared."""

    EXACT = "exact"
    FUZZY = "fuzzy"
    MAPPED = "mapped"  # e.g., FHIR code -> OMOP concept_id
    SEMANTIC = "semantic"  # e.g., display text similarity


class FieldComparison(BaseModel):
    """Result of comparing a single field between FHIR source and ClinicalFact target."""

    field_name: str = Field(..., description="Name of the field being compared")
    source_value: str | None = Field(None, description="Value from the FHIR resource")
    target_value: str | None = Field(None, description="Value in the ClinicalFact")
    match: bool = Field(..., description="Whether the values match")
    comparison_type: ComparisonType = Field(
        ..., description="How values were compared"
    )
    message: str | None = Field(
        None, description="Details about mismatch or transformation"
    )


class ETLValidationResult(BaseModel):
    """Result of validating a single FHIR resource -> ClinicalFact round-trip."""

    resource_type: str = Field(..., description="FHIR resource type (Condition, Observation, etc.)")
    resource_id: str | None = Field(None, description="FHIR resource ID")
    field_comparisons: list[FieldComparison] = Field(
        default_factory=list, description="Per-field comparison results"
    )
    overall_match: bool = Field(
        ..., description="True if all critical fields match"
    )
    issues: list[str] = Field(
        default_factory=list, description="List of validation issues found"
    )


class BatchETLValidationResult(BaseModel):
    """Result of validating a batch of FHIR resources."""

    total: int = Field(..., description="Total resources in bundle")
    validated: int = Field(..., description="Number of resources validated")
    passed: int = Field(..., description="Number that passed validation")
    failed: int = Field(..., description="Number that failed validation")
    skipped: int = Field(0, description="Resources skipped (no matching fact)")
    success_rate: float = Field(
        ..., description="Fraction of validated resources that passed (0.0-1.0)"
    )
    data_loss_fields: list[str] = Field(
        default_factory=list,
        description="Field names that lost data during transformation",
    )
    results: list[ETLValidationResult] = Field(
        default_factory=list, description="Per-resource validation results"
    )


class DomainMismatch(BaseModel):
    """A fact whose OMOP concept domain doesn't match its declared domain."""

    fact_id: str = Field(..., description="ClinicalFact ID")
    patient_id: str = Field(..., description="Patient ID")
    concept_name: str = Field(..., description="Concept name")
    declared_domain: str = Field(..., description="Domain set on the fact")
    expected_domain: str | None = Field(
        None, description="Expected domain based on concept_id"
    )
    omop_concept_id: int = Field(..., description="OMOP concept ID")


class ConceptMappingReport(BaseModel):
    """Report on concept mapping accuracy across all ClinicalFacts."""

    total_facts: int = Field(..., description="Total ClinicalFacts examined")
    mapped: int = Field(
        ..., description="Facts with valid (non-zero) OMOP concept IDs"
    )
    unmapped: int = Field(
        ..., description="Facts with zero or missing OMOP concept IDs"
    )
    mapping_rate: float = Field(
        ..., description="Fraction of facts successfully mapped (0.0-1.0)"
    )
    domain_mismatches: list[DomainMismatch] = Field(
        default_factory=list,
        description="Facts whose concept domain doesn't match declared domain",
    )
    domain_mismatch_count: int = Field(
        0, description="Number of domain mismatches"
    )
    by_domain: dict[str, dict[str, int]] = Field(
        default_factory=dict,
        description="Mapping stats broken down by domain (mapped/unmapped counts)",
    )


class DuplicateGroup(BaseModel):
    """A group of duplicate facts (same patient + concept + date)."""

    patient_id: str
    omop_concept_id: int
    concept_name: str
    start_date: str | None
    count: int
    fact_ids: list[str]


class MissingFieldEntry(BaseModel):
    """A fact missing a required field."""

    fact_id: str
    patient_id: str
    missing_fields: list[str]


class RangeViolation(BaseModel):
    """A measurement fact whose value is outside expected range."""

    fact_id: str
    patient_id: str
    concept_name: str
    value: str
    unit: str | None
    reason: str


class ETLQualityReport(BaseModel):
    """Comprehensive ETL quality report."""

    orphaned_count: int = Field(
        ..., description="Facts with no linked source document or evidence"
    )
    duplicate_count: int = Field(
        ..., description="Number of duplicate fact groups detected"
    )
    duplicate_groups: list[DuplicateGroup] = Field(
        default_factory=list, description="Details of duplicate groups"
    )
    missing_fields_count: int = Field(
        ..., description="Facts missing required fields"
    )
    missing_field_entries: list[MissingFieldEntry] = Field(
        default_factory=list, description="Details of facts with missing fields"
    )
    range_violations: list[RangeViolation] = Field(
        default_factory=list,
        description="Measurement facts with out-of-range values",
    )
    range_violation_count: int = Field(
        0, description="Number of range violations"
    )
    total_facts: int = Field(0, description="Total facts examined")
    overall_score: float = Field(
        ...,
        description="Quality score 0.0-1.0 (higher is better)",
    )
