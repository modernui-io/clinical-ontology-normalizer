"""Phenotype definition schemas for cohort identification (CSO-2.3).

Provides structured phenotype definitions that use OMOP concept IDs,
ICD codes, and text patterns for precise cohort identification,
replacing simple ILIKE string matching.

A "phenotype" is a computable definition of a clinical condition
using multiple code systems for maximum recall:
  - OMOP concept IDs (standard vocabulary)
  - ICD-10-CM codes (billing/administrative)
  - Text patterns (NLP-extracted concept names)
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class PhenotypeMatchMethod(str, Enum):
    """How a phenotype was matched against patient data."""

    CONCEPT_ID = "concept_id"  # Matched via OMOP concept ID
    ICD_CODE = "icd_code"  # Matched via ICD-10 code
    TEXT_PATTERN = "text_pattern"  # Matched via text pattern on concept_name


class PhenotypeCreate(BaseModel):
    """Request body for creating/updating a phenotype definition."""

    name: str = Field(
        ...,
        description="Unique name for the phenotype (e.g., 'type_2_diabetes')",
        min_length=1,
        max_length=255,
    )
    domain: str = Field(
        ...,
        description="Clinical domain (condition, drug, measurement, procedure, observation)",
    )
    concept_ids: list[int] = Field(
        default_factory=list,
        description="OMOP standard concept IDs that define this phenotype",
    )
    icd_codes: list[str] = Field(
        default_factory=list,
        description="ICD-10-CM codes (prefix matching supported, e.g., 'E11' matches 'E11.9')",
    )
    text_patterns: list[str] = Field(
        default_factory=list,
        description="Case-insensitive text patterns matched against concept_name",
    )
    description: str = Field(
        default="",
        description="Human-readable description of the phenotype",
    )
    version: str = Field(
        default="1.0",
        description="Version of this phenotype definition",
    )


class Phenotype(BaseModel):
    """A structured phenotype definition for cohort identification."""

    name: str = Field(..., description="Unique identifier name")
    domain: str = Field(..., description="Clinical domain")
    concept_ids: list[int] = Field(default_factory=list, description="OMOP concept IDs")
    icd_codes: list[str] = Field(default_factory=list, description="ICD-10-CM codes")
    text_patterns: list[str] = Field(default_factory=list, description="Text patterns")
    description: str = Field(default="", description="Description")
    version: str = Field(default="1.0", description="Version")
    created_at: datetime | None = Field(None, description="When this phenotype was created")


class MatchedFact(BaseModel):
    """A clinical fact that matched a phenotype criterion."""

    fact_id: str = Field(..., description="ID of the matched ClinicalFact")
    concept_name: str = Field(..., description="Concept name from the fact")
    omop_concept_id: int = Field(..., description="OMOP concept ID from the fact")
    source_code: str | None = Field(None, description="Source code (ICD, etc.) if available")
    confidence: float = Field(..., description="Confidence of the underlying fact")
    match_method: PhenotypeMatchMethod = Field(
        ..., description="How this fact matched the phenotype"
    )


class PhenotypeMatch(BaseModel):
    """Result of matching a phenotype against a patient's clinical facts."""

    phenotype_name: str = Field(..., description="Name of the phenotype tested")
    matched: bool = Field(..., description="Whether the phenotype matched")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall confidence of the match (0.0 to 1.0)",
    )
    matched_facts: list[MatchedFact] = Field(
        default_factory=list,
        description="Clinical facts that matched the phenotype",
    )
    match_methods: list[PhenotypeMatchMethod] = Field(
        default_factory=list,
        description="Which matching methods produced hits",
    )
    concept_id_matches: int = Field(
        default=0, description="Number of facts matched by OMOP concept ID"
    )
    icd_code_matches: int = Field(
        default=0, description="Number of facts matched by ICD code"
    )
    text_pattern_matches: int = Field(
        default=0, description="Number of facts matched by text pattern"
    )


class PhenotypeLibrary(BaseModel):
    """Collection of all registered phenotype definitions."""

    phenotypes: list[Phenotype] = Field(
        default_factory=list, description="All registered phenotypes"
    )
    total: int = Field(default=0, description="Total count of phenotypes")


class PatientFactsInput(BaseModel):
    """Input for phenotype matching - a list of patient clinical facts."""

    patient_id: str = Field(..., description="Patient identifier")
    facts: list[PatientFact] = Field(
        default_factory=list,
        description="Clinical facts to match against the phenotype",
    )


class PatientFact(BaseModel):
    """Simplified representation of a clinical fact for phenotype matching."""

    fact_id: str = Field(..., description="Fact ID")
    omop_concept_id: int = Field(..., description="OMOP concept ID")
    concept_name: str = Field(..., description="Concept name")
    domain: str = Field(..., description="Clinical domain")
    source_code: str | None = Field(None, description="Source code (e.g., ICD-10)")
    confidence: float = Field(default=1.0, description="Fact confidence")
    assertion: str = Field(default="present", description="Assertion status")


# Fix forward reference - PatientFactsInput references PatientFact
PatientFactsInput.model_rebuild()
