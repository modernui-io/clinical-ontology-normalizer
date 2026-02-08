"""Pydantic schemas for Fairness Audits (VP-DS-5).

Supports bias detection in clinical trial screening by tracking
demographic parity, equal opportunity, predictive parity, individual
fairness, and intersectional analysis across protected groups.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ProtectedAttribute(str, Enum):
    """Protected demographic attributes for fairness analysis."""

    AGE_GROUP = "age_group"
    SEX = "sex"
    RACE = "race"
    ETHNICITY = "ethnicity"


class BiasRecommendationType(str, Enum):
    """Types of bias mitigation recommendations."""

    CRITERIA_REVIEW = "CRITERIA_REVIEW"
    DATA_COLLECTION = "DATA_COLLECTION"
    THRESHOLD_ADJUSTMENT = "THRESHOLD_ADJUSTMENT"
    NO_ACTION = "NO_ACTION"


class AuditStatus(str, Enum):
    """Status of a fairness audit."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class ScreeningOutcome(str, Enum):
    """Outcome of a screening decision."""

    PASSED = "passed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Screening outcome record
# ---------------------------------------------------------------------------


class ScreeningOutcomeRecord(BaseModel):
    """A single patient's screening outcome with demographics."""

    patient_id: str = Field(..., description="Patient identifier")
    trial_id: str = Field(..., description="Trial identifier")
    screening_result: ScreeningOutcome = Field(
        ..., description="Whether patient passed screening"
    )
    actually_eligible: bool | None = Field(
        default=None,
        description="Ground truth eligibility (for equal opportunity / predictive parity)",
    )
    age_group: str | None = Field(
        default=None, description="Age group bucket (e.g., '18-30', '31-45')"
    )
    sex: str | None = Field(default=None, description="Biological sex")
    race: str | None = Field(default=None, description="Race category")
    ethnicity: str | None = Field(default=None, description="Ethnicity category")
    clinical_features: dict[str, float] | None = Field(
        default=None,
        description="Clinical feature vector for individual fairness analysis",
    )
    recorded_at: datetime | None = Field(
        default=None, description="When this outcome was recorded"
    )


# ---------------------------------------------------------------------------
# Group-level fairness results
# ---------------------------------------------------------------------------


class GroupRate(BaseModel):
    """Pass rate for a single demographic group."""

    group_value: str = Field(..., description="Group value (e.g., 'Male', 'White')")
    total: int = Field(default=0, ge=0, description="Total patients in group")
    passed: int = Field(default=0, ge=0, description="Patients who passed screening")
    rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Pass rate")


class DemographicParityResult(BaseModel):
    """Demographic parity analysis for a single attribute."""

    attribute: ProtectedAttribute = Field(
        ..., description="Protected attribute analyzed"
    )
    group_rates: list[GroupRate] = Field(
        default_factory=list, description="Per-group pass rates"
    )
    min_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Minimum group pass rate"
    )
    max_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Maximum group pass rate"
    )
    disparity_ratio: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="min_rate / max_rate (1.0 = perfect parity)",
    )
    four_fifths_violated: bool = Field(
        default=False,
        description="True if disparity ratio < 0.8 (adverse impact)",
    )


class EqualOpportunityResult(BaseModel):
    """Equal opportunity analysis for a single attribute.

    Measures true positive rates (TPR) across groups: among patients who
    are actually eligible, does each group have an equal chance of being
    correctly identified as eligible?
    """

    attribute: ProtectedAttribute = Field(
        ..., description="Protected attribute analyzed"
    )
    group_tpr: list[GroupRate] = Field(
        default_factory=list,
        description="Per-group true positive rates (rate = TPR)",
    )
    min_tpr: float = Field(default=0.0, ge=0.0, le=1.0)
    max_tpr: float = Field(default=0.0, ge=0.0, le=1.0)
    disparity_ratio: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="min_tpr / max_tpr",
    )
    four_fifths_violated: bool = Field(default=False)


class PredictiveParityResult(BaseModel):
    """Predictive parity analysis for a single attribute.

    Measures positive predictive value (PPV) across groups: among patients
    predicted eligible (passed screening), is the actual eligibility rate
    the same across groups?
    """

    attribute: ProtectedAttribute = Field(
        ..., description="Protected attribute analyzed"
    )
    group_ppv: list[GroupRate] = Field(
        default_factory=list,
        description="Per-group positive predictive values (rate = PPV)",
    )
    min_ppv: float = Field(default=0.0, ge=0.0, le=1.0)
    max_ppv: float = Field(default=0.0, ge=0.0, le=1.0)
    disparity_ratio: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="min_ppv / max_ppv",
    )
    four_fifths_violated: bool = Field(default=False)


class IndividualFairnessPair(BaseModel):
    """A pair of similar patients with potentially different outcomes."""

    patient_a_id: str = Field(..., description="First patient ID")
    patient_b_id: str = Field(..., description="Second patient ID")
    similarity: float = Field(
        ..., ge=0.0, le=1.0, description="Clinical similarity score"
    )
    same_outcome: bool = Field(
        ..., description="Whether both patients had the same screening outcome"
    )


class IndividualFairnessResult(BaseModel):
    """Individual fairness analysis results."""

    total_pairs_checked: int = Field(
        default=0, ge=0, description="Number of similar patient pairs checked"
    )
    consistent_pairs: int = Field(
        default=0, ge=0, description="Pairs with same outcome"
    )
    inconsistent_pairs: int = Field(
        default=0, ge=0, description="Pairs with different outcomes"
    )
    consistency_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fraction of similar pairs with consistent outcomes",
    )
    flagged_pairs: list[IndividualFairnessPair] = Field(
        default_factory=list,
        description="Pairs flagged as inconsistent (similar patients, different outcomes)",
    )
    similarity_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Threshold used to define 'similar' patients",
    )


class IntersectionalGroupRate(BaseModel):
    """Pass rate for an intersectional demographic group."""

    group_key: str = Field(
        ...,
        description="Intersectional group key (e.g., 'race=White+sex=Male')",
    )
    attributes: dict[str, str] = Field(
        ..., description="Attribute values for this group"
    )
    total: int = Field(default=0, ge=0)
    passed: int = Field(default=0, ge=0)
    rate: float = Field(default=0.0, ge=0.0, le=1.0)


class IntersectionalAnalysisResult(BaseModel):
    """Intersectional analysis across multiple attributes."""

    attribute_combination: list[ProtectedAttribute] = Field(
        ..., description="Attributes combined for intersectional analysis"
    )
    group_rates: list[IntersectionalGroupRate] = Field(
        default_factory=list, description="Per-intersectional-group pass rates"
    )
    min_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    max_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    disparity_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    four_fifths_violated: bool = Field(default=False)


# ---------------------------------------------------------------------------
# Bias recommendations
# ---------------------------------------------------------------------------


class BiasRecommendation(BaseModel):
    """A recommendation for mitigating detected bias."""

    recommendation_type: BiasRecommendationType = Field(
        ..., description="Category of recommendation"
    )
    attribute: ProtectedAttribute | None = Field(
        default=None, description="Affected attribute"
    )
    description: str = Field(
        ..., description="Human-readable recommendation"
    )
    severity: str = Field(
        default="medium",
        description="Severity: low, medium, high",
    )
    details: dict[str, str | float] | None = Field(
        default=None, description="Additional details"
    )


# ---------------------------------------------------------------------------
# Aggregate fairness metrics
# ---------------------------------------------------------------------------


class FairnessMetrics(BaseModel):
    """Aggregated fairness metrics for a trial audit."""

    demographic_parity: list[DemographicParityResult] = Field(
        default_factory=list,
        description="Demographic parity results per protected attribute",
    )
    equal_opportunity: list[EqualOpportunityResult] = Field(
        default_factory=list,
        description="Equal opportunity results per protected attribute",
    )
    predictive_parity: list[PredictiveParityResult] = Field(
        default_factory=list,
        description="Predictive parity results per protected attribute",
    )
    individual_fairness: IndividualFairnessResult | None = Field(
        default=None, description="Individual fairness analysis"
    )
    intersectional: list[IntersectionalAnalysisResult] = Field(
        default_factory=list,
        description="Intersectional analysis results",
    )
    overall_fairness_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall fairness score (1.0 = perfectly fair)",
    )


# ---------------------------------------------------------------------------
# Audit configuration
# ---------------------------------------------------------------------------


class FairnessAuditConfig(BaseModel):
    """Configuration for a fairness audit."""

    four_fifths_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Threshold for four-fifths rule (default: 0.8)",
    )
    similarity_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Threshold for individual fairness similarity",
    )
    min_group_size: int = Field(
        default=5,
        ge=1,
        description="Minimum group size to include in analysis",
    )
    attributes_to_audit: list[ProtectedAttribute] = Field(
        default_factory=lambda: list(ProtectedAttribute),
        description="Which protected attributes to audit",
    )
    intersectional_attributes: list[list[ProtectedAttribute]] | None = Field(
        default=None,
        description="Attribute combinations for intersectional analysis",
    )


# ---------------------------------------------------------------------------
# Audit request / response
# ---------------------------------------------------------------------------


class FairnessAuditCreate(BaseModel):
    """Request to create a fairness audit for a trial."""

    trial_id: str = Field(..., description="Trial to audit")
    config: FairnessAuditConfig | None = Field(
        default=None, description="Audit configuration (uses defaults if omitted)"
    )
    plan_demographics: dict[str, dict[str, float]] | None = Field(
        default=None,
        description="FDA diversity plan demographics for compliance checking",
    )


class FDAComplianceResult(BaseModel):
    """FDA diversity plan compliance checking result."""

    plan_demographics: dict[str, dict[str, float]] = Field(
        ..., description="Planned demographics"
    )
    actual_demographics: dict[str, dict[str, float]] = Field(
        ..., description="Actual demographics from screening"
    )
    compliance_gaps: list[str] = Field(
        default_factory=list,
        description="Demographic groups below plan targets",
    )
    is_compliant: bool = Field(
        default=False,
        description="Whether overall demographics meet plan requirements",
    )


class FairnessAuditResponse(BaseModel):
    """Full fairness audit report."""

    audit_id: str = Field(..., description="Unique audit identifier")
    trial_id: str = Field(..., description="Trial that was audited")
    status: AuditStatus = Field(
        default=AuditStatus.COMPLETED, description="Audit status"
    )
    config: FairnessAuditConfig = Field(
        ..., description="Configuration used for this audit"
    )
    metrics: FairnessMetrics = Field(
        ..., description="Fairness metrics computed"
    )
    recommendations: list[BiasRecommendation] = Field(
        default_factory=list, description="Bias mitigation recommendations"
    )
    total_records: int = Field(
        default=0, ge=0, description="Total screening records analyzed"
    )
    created_at: datetime | None = Field(
        default=None, description="When the audit was created"
    )
    fda_compliance: FDAComplianceResult | None = Field(
        default=None,
        description="FDA diversity plan compliance results",
    )


# ---------------------------------------------------------------------------
# Trend tracking
# ---------------------------------------------------------------------------


class FairnessTrendPoint(BaseModel):
    """A single point in a fairness metric trend."""

    audit_id: str = Field(..., description="Audit that produced this data point")
    timestamp: datetime = Field(..., description="When the audit was run")
    overall_fairness_score: float = Field(
        default=0.0, ge=0.0, le=1.0
    )
    demographic_parity_avg: float = Field(
        default=0.0, ge=0.0, le=1.0
    )
    equal_opportunity_avg: float = Field(
        default=0.0, ge=0.0, le=1.0
    )
    predictive_parity_avg: float = Field(
        default=0.0, ge=0.0, le=1.0
    )


class FairnessTrend(BaseModel):
    """Fairness metric trends over time for a trial."""

    trial_id: str = Field(..., description="Trial identifier")
    data_points: list[FairnessTrendPoint] = Field(
        default_factory=list, description="Trend data points"
    )
    trend_direction: str = Field(
        default="stable",
        description="Overall trend: improving, declining, stable",
    )


# ---------------------------------------------------------------------------
# Platform summary
# ---------------------------------------------------------------------------


class TrialFairnessSummary(BaseModel):
    """Summary of fairness for a single trial."""

    trial_id: str = Field(..., description="Trial identifier")
    latest_fairness_score: float = Field(
        default=0.0, ge=0.0, le=1.0
    )
    total_audits: int = Field(default=0, ge=0)
    has_violations: bool = Field(default=False)
    last_audit_at: datetime | None = Field(default=None)


class PlatformFairnessSummary(BaseModel):
    """Platform-wide fairness summary across all trials."""

    total_trials_audited: int = Field(
        default=0, ge=0, description="Number of trials with audits"
    )
    total_audits: int = Field(
        default=0, ge=0, description="Total audits run"
    )
    average_fairness_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Average fairness score across all trials",
    )
    trials_with_violations: int = Field(
        default=0, ge=0, description="Trials with four-fifths rule violations"
    )
    trial_summaries: list[TrialFairnessSummary] = Field(
        default_factory=list,
        description="Per-trial fairness summaries",
    )
    generated_at: datetime | None = Field(
        default=None, description="When this summary was generated"
    )


# ---------------------------------------------------------------------------
# API request for recording screening outcomes
# ---------------------------------------------------------------------------


class RecordScreeningOutcomeRequest(BaseModel):
    """Request to record a screening outcome with demographics."""

    outcome: ScreeningOutcomeRecord = Field(
        ..., description="Screening outcome to record"
    )
