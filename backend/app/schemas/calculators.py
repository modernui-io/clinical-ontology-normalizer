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
    has_age_scoring: bool = Field(default=False, description="Whether age-based scoring applies")
    interpretations: list[InterpretationSchema] = Field(
        default_factory=list,
        description="Score interpretation rules",
    )
    references: list[str] = Field(default_factory=list, description="Literature references")
    notes: list[str] = Field(default_factory=list, description="Additional clinical notes")


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
