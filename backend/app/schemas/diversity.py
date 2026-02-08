"""Pydantic schemas for Diversity and Inclusion Analytics (VP-Product-4).

Supports FDA diversity action plan requirements by tracking demographic
representation across the clinical trial screening and enrollment pipeline.

Race categories align with FDA's standard categories per 2024 Diversity
Action Plan guidance.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums for FDA-standard demographic categories
# ---------------------------------------------------------------------------


class Sex(str, Enum):
    """Biological sex categories."""

    MALE = "Male"
    FEMALE = "Female"
    OTHER = "Other"
    UNKNOWN = "Unknown"


class Race(str, Enum):
    """FDA standard race categories.

    Aligned with FDA's 2024 Diversity Action Plan guidance and
    OMB minimum reporting categories.
    """

    AMERICAN_INDIAN_ALASKA_NATIVE = "American Indian/Alaska Native"
    ASIAN = "Asian"
    BLACK_AFRICAN_AMERICAN = "Black/African American"
    NATIVE_HAWAIIAN_PACIFIC_ISLANDER = "Native Hawaiian/Pacific Islander"
    WHITE = "White"
    MULTIPLE = "Multiple"
    UNKNOWN = "Unknown"


class Ethnicity(str, Enum):
    """FDA standard ethnicity categories."""

    HISPANIC_LATINO = "Hispanic/Latino"
    NOT_HISPANIC_LATINO = "Not Hispanic/Latino"
    UNKNOWN = "Unknown"


class PipelineStage(str, Enum):
    """Stages in the trial enrollment pipeline."""

    SCREENED = "screened"
    ELIGIBLE = "eligible"
    ENROLLED = "enrolled"


# ---------------------------------------------------------------------------
# Age bucket constants
# ---------------------------------------------------------------------------

AGE_BUCKETS: list[str] = ["18-30", "31-45", "46-60", "61-75", "75+"]


def age_to_bucket(age: int) -> str:
    """Map a numeric age to an age bucket string."""
    if age <= 30:
        return "18-30"
    elif age <= 45:
        return "31-45"
    elif age <= 60:
        return "46-60"
    elif age <= 75:
        return "61-75"
    else:
        return "75+"


# ---------------------------------------------------------------------------
# Core schemas
# ---------------------------------------------------------------------------


class DemographicRecord(BaseModel):
    """A single patient's demographic data for diversity tracking."""

    patient_id: str = Field(..., description="Patient identifier")
    age: int = Field(..., ge=0, le=150, description="Patient age in years")
    sex: Sex = Field(..., description="Biological sex")
    race: Race = Field(..., description="FDA race category")
    ethnicity: Ethnicity = Field(..., description="FDA ethnicity category")
    pipeline_stage: PipelineStage = Field(
        default=PipelineStage.SCREENED,
        description="Current stage in the enrollment pipeline",
    )
    recorded_at: datetime | None = Field(
        default=None,
        description="When this demographic record was captured",
    )


class DistributionEntry(BaseModel):
    """A single category in a distribution breakdown."""

    category: str = Field(..., description="Category label")
    count: int = Field(default=0, ge=0, description="Number of patients")
    percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="Percentage of total")


class DiversityReport(BaseModel):
    """Aggregate diversity report for a trial.

    Provides demographic breakdowns by age, sex, race, and ethnicity
    across all patients tracked for the trial.
    """

    trial_id: str = Field(..., description="Trial identifier")
    total_patients: int = Field(default=0, ge=0, description="Total patients in report")
    age_distribution: list[DistributionEntry] = Field(
        default_factory=list,
        description="Age distribution across standard buckets",
    )
    sex_distribution: list[DistributionEntry] = Field(
        default_factory=list,
        description="Sex distribution",
    )
    race_distribution: list[DistributionEntry] = Field(
        default_factory=list,
        description="Race distribution (FDA categories)",
    )
    ethnicity_distribution: list[DistributionEntry] = Field(
        default_factory=list,
        description="Ethnicity distribution",
    )
    generated_at: datetime | None = Field(
        default=None,
        description="When this report was generated",
    )


# ---------------------------------------------------------------------------
# Representation targets and checking
# ---------------------------------------------------------------------------


class RepresentationTarget(BaseModel):
    """A single diversity target for a demographic group."""

    group: str = Field(..., description="Demographic dimension (e.g., 'race', 'sex', 'ethnicity', 'age')")
    category: str = Field(..., description="Specific category within the group (e.g., 'Black/African American')")
    target_pct: float = Field(..., ge=0.0, le=100.0, description="Target percentage for this group")
    actual_pct: float = Field(default=0.0, ge=0.0, le=100.0, description="Actual percentage achieved")
    is_met: bool = Field(default=False, description="Whether the target is met")
    gap: float = Field(default=0.0, description="Gap between target and actual (negative = exceeded)")


class RepresentationCheck(BaseModel):
    """Result of checking enrollment demographics against diversity targets."""

    trial_id: str = Field(..., description="Trial identifier")
    targets: list[RepresentationTarget] = Field(
        default_factory=list,
        description="Per-group target comparison results",
    )
    overall_diversity_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Overall diversity score (0-100). Higher is better.",
    )
    underrepresented_groups: list[str] = Field(
        default_factory=list,
        description="Groups that are below their target representation",
    )
    checked_at: datetime | None = Field(
        default=None,
        description="When this check was performed",
    )


# ---------------------------------------------------------------------------
# Pipeline demographics (stage-by-stage analysis)
# ---------------------------------------------------------------------------


class StageDemographics(BaseModel):
    """Demographics for a single pipeline stage."""

    stage: PipelineStage = Field(..., description="Pipeline stage")
    total_patients: int = Field(default=0, ge=0)
    age_distribution: list[DistributionEntry] = Field(default_factory=list)
    sex_distribution: list[DistributionEntry] = Field(default_factory=list)
    race_distribution: list[DistributionEntry] = Field(default_factory=list)
    ethnicity_distribution: list[DistributionEntry] = Field(default_factory=list)


class DropoutAnalysis(BaseModel):
    """Analysis of demographic dropout between pipeline stages."""

    from_stage: str = Field(..., description="Starting stage")
    to_stage: str = Field(..., description="Ending stage")
    group: str = Field(..., description="Demographic dimension")
    category: str = Field(..., description="Specific category")
    from_pct: float = Field(default=0.0, description="Percentage in starting stage")
    to_pct: float = Field(default=0.0, description="Percentage in ending stage")
    change_pct: float = Field(default=0.0, description="Change in percentage (negative = dropout)")
    disproportionate: bool = Field(
        default=False,
        description="Whether this group is disproportionately dropping out",
    )


class PipelineDemographics(BaseModel):
    """Demographics across all pipeline stages with dropout analysis."""

    trial_id: str = Field(..., description="Trial identifier")
    screened_demographics: StageDemographics | None = Field(
        default=None,
        description="Demographics at screening stage",
    )
    eligible_demographics: StageDemographics | None = Field(
        default=None,
        description="Demographics at eligibility stage",
    )
    enrolled_demographics: StageDemographics | None = Field(
        default=None,
        description="Demographics at enrollment stage",
    )
    dropout_analysis: list[DropoutAnalysis] = Field(
        default_factory=list,
        description="Analysis of disproportionate dropout between stages",
    )


# ---------------------------------------------------------------------------
# FDA diversity summary
# ---------------------------------------------------------------------------


class FDADiversitySummary(BaseModel):
    """FDA-format diversity summary for regulatory submissions.

    Structured to support FDA Diversity Action Plan requirements.
    """

    trial_id: str = Field(..., description="Trial identifier")
    report_date: datetime | None = Field(default=None, description="Report generation date")
    total_enrolled: int = Field(default=0, description="Total enrolled patients")
    enrollment_target: int | None = Field(default=None, description="Trial enrollment target")

    # FDA-required demographic tables
    sex_table: list[DistributionEntry] = Field(
        default_factory=list,
        description="Sex distribution table for FDA submission",
    )
    race_table: list[DistributionEntry] = Field(
        default_factory=list,
        description="Race distribution table (FDA categories)",
    )
    ethnicity_table: list[DistributionEntry] = Field(
        default_factory=list,
        description="Ethnicity distribution table",
    )
    age_table: list[DistributionEntry] = Field(
        default_factory=list,
        description="Age distribution table",
    )

    # Diversity action plan metrics
    diversity_targets_met: int = Field(
        default=0,
        description="Number of diversity targets met",
    )
    diversity_targets_total: int = Field(
        default=0,
        description="Total diversity targets set",
    )
    underrepresented_groups: list[str] = Field(
        default_factory=list,
        description="Groups below target representation",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Recommendations for improving diversity",
    )


# ---------------------------------------------------------------------------
# API request schemas
# ---------------------------------------------------------------------------


class SetDiversityTargetsRequest(BaseModel):
    """Request to set diversity targets for a trial."""

    targets: list[RepresentationTarget] = Field(
        ...,
        min_length=1,
        description="Diversity targets to set for the trial",
    )
