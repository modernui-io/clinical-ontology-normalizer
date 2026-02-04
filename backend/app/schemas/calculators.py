"""Pydantic Schemas for Data-Driven Calculators API.

Response and request models for exposing data-driven calculator definitions
and calculations via the API.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# =============================================================================
# Criterion Schemas (for calculator definition details)
# =============================================================================


class BooleanCriterionSchema(BaseModel):
    """Boolean scoring criterion (yes/no)."""

    name: str = Field(..., description="Parameter name")
    display_name: str = Field(..., description="Human-readable name")
    points: int = Field(..., description="Points awarded if true")
    type: str = Field(default="boolean", description="Criterion type")
    description: str = Field(default="", description="Clinical description")


class MultiLevelSchema(BaseModel):
    """Level within a multi-level criterion."""

    suffix: str = Field(..., description="Level identifier suffix")
    points: int = Field(..., description="Points for this level")
    display: str = Field(..., description="Display text")


class MultiLevelCriterionSchema(BaseModel):
    """Multi-level scoring criterion (0/1/2 points)."""

    name: str = Field(..., description="Parameter name base")
    display_name: str = Field(..., description="Human-readable category")
    type: str = Field(default="multi_level", description="Criterion type")
    levels: list[MultiLevelSchema] = Field(..., description="Available levels")
    description: str = Field(default="", description="Clinical description")


class ThresholdLevelSchema(BaseModel):
    """Threshold within a threshold criterion."""

    operator: str = Field(..., description="Comparison operator (gt, lt, gte, lte, eq, between)")
    value: float | tuple[float, float] = Field(..., description="Threshold value(s)")
    points: int = Field(..., description="Points for this threshold")
    display: str = Field(..., description="Display text")


class ThresholdCriterionSchema(BaseModel):
    """Threshold-based scoring criterion."""

    name: str = Field(..., description="Parameter name")
    display_name: str = Field(..., description="Human-readable name")
    type: str = Field(default="threshold", description="Criterion type")
    unit: str = Field(default="", description="Unit of measurement")
    thresholds: list[ThresholdLevelSchema] = Field(..., description="Threshold definitions")
    description: str = Field(default="", description="Clinical description")


# =============================================================================
# Interpretation Schema
# =============================================================================


class InterpretationSchema(BaseModel):
    """Score interpretation definition."""

    min_score: float = Field(..., description="Minimum score (inclusive)")
    max_score: float | None = Field(None, description="Maximum score (exclusive)")
    risk_level: str = Field(..., description="Risk classification")
    interpretation: str = Field(..., description="Clinical interpretation")
    recommendations: list[str] = Field(default_factory=list, description="Clinical recommendations")


# =============================================================================
# Provenance Schemas (MDCalc-style evidence documentation)
# =============================================================================


class CitationSchema(BaseModel):
    """Structured citation for literature references."""

    title: str = Field(..., description="Full title of the paper")
    authors: list[str] = Field(default_factory=list, description="List of author names")
    journal: str = Field(..., description="Journal name")
    year: int = Field(..., description="Publication year")
    volume: str | None = Field(None, description="Journal volume")
    pages: str | None = Field(None, description="Page range")
    pmid: str | None = Field(None, description="PubMed ID")
    doi: str | None = Field(None, description="Digital Object Identifier")
    is_original_derivation: bool = Field(False, description="True if original derivation paper")
    pubmed_url: str | None = Field(None, description="Link to PubMed")


class ValidationStudySchema(BaseModel):
    """A validation study that tested the calculator."""

    citation: CitationSchema = Field(..., description="Study citation")
    population: str = Field(..., description="Study population description")
    sample_size: int | None = Field(None, description="Number of patients")
    setting: str | None = Field(None, description="Clinical setting")
    performance_auc: float | None = Field(None, description="Area under ROC curve")
    validation_outcome: str = Field(..., description="Validation outcome classification")
    notes: str | None = Field(None, description="Additional notes")


class ClinicalPearlSchema(BaseModel):
    """A clinical pearl or tip for using the calculator."""

    text: str = Field(..., description="The clinical pearl content")
    category: str = Field("tip", description="Category: interpretation, usage, limitation, tip, warning")
    source: str | None = Field(None, description="Source of this pearl")


class UsageGuidanceSchema(BaseModel):
    """Guidance on when to use and when NOT to use the calculator."""

    when_to_use: list[str] = Field(default_factory=list, description="Appropriate use cases")
    when_not_to_use: list[str] = Field(default_factory=list, description="Contraindications/inappropriate uses")
    target_population: str | None = Field(None, description="Target patient population")
    excluded_populations: list[str] = Field(default_factory=list, description="Populations to exclude")


class GuidelineReferenceSchema(BaseModel):
    """Reference to a clinical guideline that endorses this calculator."""

    guideline_name: str = Field(..., description="Name of the guideline")
    recommendation_class: str | None = Field(None, description="Recommendation class (I, IIa, IIb, III)")
    evidence_level: str | None = Field(None, description="Evidence level (A, B, C)")
    year: int | None = Field(None, description="Guideline year")
    organization: str | None = Field(None, description="Issuing organization")


class CalculatorProvenanceSchema(BaseModel):
    """Complete provenance data for a clinical calculator."""

    # Core provenance
    original_citation: CitationSchema | None = Field(None, description="Original derivation study")
    evidence_level: str | None = Field(None, description="Overall evidence quality (high, moderate, low)")
    evidence_summary: str | None = Field(None, description="Summary of evidence supporting this calculator")

    # Validation
    validation_studies: list[ValidationStudySchema] = Field(
        default_factory=list, description="Validation studies"
    )
    overall_validation: str | None = Field(None, description="Overall validation status")

    # Clinical guidance
    clinical_pearls: list[ClinicalPearlSchema] = Field(
        default_factory=list, description="Clinical pearls and tips"
    )
    pitfalls: list[str] = Field(default_factory=list, description="Common pitfalls to avoid")
    usage_guidance: UsageGuidanceSchema | None = Field(None, description="When to use/not use")

    # Guidelines
    related_guidelines: list[GuidelineReferenceSchema] = Field(
        default_factory=list, description="Guidelines endorsing this calculator"
    )
    related_calculator_ids: list[str] = Field(
        default_factory=list, description="Related calculator IDs"
    )

    # External links
    mdcalc_url: str | None = Field(None, description="MDCalc page URL")


# =============================================================================
# List/Summary Response
# =============================================================================


class DataDrivenCalculatorListItem(BaseModel):
    """Summary of a data-driven calculator for list responses."""

    id: str = Field(..., description="Calculator identifier")
    name: str = Field(..., description="Full display name")
    short_name: str = Field(..., description="Abbreviated name")
    category: str = Field(..., description="Clinical category")
    calc_type: str = Field(..., description="Calculator type (criteria, equation, etc.)")
    description: str = Field(default="", description="Clinical description")


class DataDrivenCalculatorListResponse(BaseModel):
    """Response for listing data-driven calculators."""

    calculators: list[DataDrivenCalculatorListItem] = Field(..., description="List of calculators")
    total_count: int = Field(..., description="Total number of calculators")


# =============================================================================
# Formula Parameter Schema (for equation-type calculators)
# =============================================================================


class FormulaParameterSchema(BaseModel):
    """Parameter definition for equation-based calculators."""

    name: str = Field(..., description="Parameter identifier")
    display_name: str = Field(..., description="Human-readable name")
    unit: str = Field(default="", description="Unit of measurement")
    min_value: float | None = Field(None, description="Minimum allowed value")
    max_value: float | None = Field(None, description="Maximum allowed value")
    description: str = Field(default="", description="Clinical description")


class FormulaSchema(BaseModel):
    """Formula definition for equation-type calculators."""

    formula_text: str = Field(..., description="Human-readable formula description")
    output_unit: str = Field(..., description="Unit of the calculated result")
    precision: int = Field(default=1, description="Decimal places for output")
    parameters: list[FormulaParameterSchema] = Field(
        default_factory=list,
        description="Input parameters for the formula",
    )


# =============================================================================
# Detail Response
# =============================================================================


class DataDrivenCalculatorDetail(BaseModel):
    """Full details of a data-driven calculator."""

    id: str = Field(..., description="Calculator identifier")
    name: str = Field(..., description="Full display name")
    short_name: str = Field(..., description="Abbreviated name")
    category: str = Field(..., description="Clinical category")
    calc_type: str = Field(..., description="Calculator type")
    description: str = Field(default="", description="Clinical description")
    score_unit: str = Field(default="points", description="Unit for the score")
    criteria: list[dict[str, Any]] = Field(
        default_factory=list,
        description="All criteria (boolean, multi_level, threshold)",
    )
    formula: FormulaSchema | None = Field(
        None,
        description="Formula definition for equation-type calculators",
    )
    has_age_scoring: bool = Field(default=False, description="Whether age-based scoring applies")
    interpretations: list[InterpretationSchema] = Field(
        default_factory=list,
        description="Score interpretation rules",
    )
    references: list[str] = Field(default_factory=list, description="Literature references")
    notes: list[str] = Field(default_factory=list, description="Additional clinical notes")
    provenance: CalculatorProvenanceSchema | None = Field(
        None,
        description="Evidence provenance (citations, clinical pearls, guidelines)",
    )


# =============================================================================
# Calculation Request/Response
# =============================================================================


class DataDrivenCalculationRequest(BaseModel):
    """Request to calculate using a data-driven calculator."""

    values: dict[str, bool | int | float] = Field(
        ...,
        description="Criterion values keyed by criterion name",
    )
    age: int | None = Field(
        None,
        ge=0,
        le=150,
        description="Patient age (required for calculators with age-based scoring)",
    )


class DataDrivenCalculationResponse(BaseModel):
    """Result from a data-driven calculation."""

    calculator_id: str = Field(..., description="Calculator identifier")
    calculator_name: str = Field(..., description="Calculator display name")
    score: float = Field(..., description="Calculated score")
    score_unit: str = Field(..., description="Unit of measurement")
    risk_level: str = Field(..., description="Risk classification")
    interpretation: str = Field(..., description="Clinical interpretation")
    recommendations: list[str] = Field(default_factory=list, description="Clinical recommendations")
    components: dict[str, Any] = Field(
        default_factory=dict,
        description="Score breakdown by component",
    )
    references: list[str] = Field(default_factory=list, description="Literature references")
    warnings: list[str] = Field(default_factory=list, description="Any applicable warnings")
