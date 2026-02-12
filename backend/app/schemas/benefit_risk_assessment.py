"""Pydantic schemas for Benefit-Risk Assessment (CLINICAL-8).

Manages structured benefit-risk assessment operations: assessment lifecycle
(draft through finalization/supersession), benefit outcome quantification with
effect sizes and clinical significance, risk outcome characterization with
incidence rates and management strategies, multi-criteria decision analysis
frameworks (FDA BRF, EMA Effects Table, MCDA, PrOACT-URL, Incremental Net
Benefit), and aggregate benefit-risk metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AssessmentStatus(str, Enum):
    """Lifecycle status of a benefit-risk assessment."""

    DRAFT = "draft"
    IN_REVIEW = "in_review"
    FINALIZED = "finalized"
    SUPERSEDED = "superseded"


class AssessmentFramework(str, Enum):
    """Structured framework used for benefit-risk evaluation."""

    FDA_BRF = "fda_brf"
    EMA_EFFECTS_TABLE = "ema_effects_table"
    MCDA = "mcda"
    PROACT_URL = "proact_url"
    INCREMENTAL_NET_BENEFIT = "incremental_net_benefit"


class OutcomeCategory(str, Enum):
    """Category of a clinical outcome in benefit-risk analysis."""

    EFFICACY = "efficacy"
    SAFETY = "safety"
    TOLERABILITY = "tolerability"
    CONVENIENCE = "convenience"
    QUALITY_OF_LIFE = "quality_of_life"


class SeverityLevel(str, Enum):
    """Clinical severity level for an outcome."""

    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    LIFE_THREATENING = "life_threatening"
    FATAL = "fatal"


class LikelihoodLevel(str, Enum):
    """Frequency/likelihood classification for an outcome."""

    VERY_COMMON = "very_common"
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    VERY_RARE = "very_rare"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class BenefitRiskAssessment(BaseModel):
    """A structured benefit-risk assessment for a drug/indication pair."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique assessment identifier")
    trial_id: str = Field(..., description="Associated clinical trial identifier")
    drug_name: str = Field(..., description="Name of the drug being assessed")
    indication: str = Field(..., description="Therapeutic indication under evaluation")
    comparator: str = Field(..., description="Comparator (e.g., placebo, active comparator)")
    assessment_number: int = Field(
        ..., ge=1, description="Sequential assessment number within the trial"
    )
    version: int = Field(default=1, ge=1, description="Version of this assessment")
    status: AssessmentStatus = Field(
        default=AssessmentStatus.DRAFT, description="Current lifecycle status"
    )
    framework: AssessmentFramework = Field(
        ..., description="Benefit-risk evaluation framework used"
    )
    assessor: str = Field(..., description="Name of the primary assessor")
    assessment_date: datetime = Field(..., description="Date the assessment was created")
    finalized_date: datetime | None = Field(
        None, description="Date the assessment was finalized"
    )
    overall_conclusion: str | None = Field(
        None, description="Overall benefit-risk conclusion narrative"
    )
    regulatory_context: str | None = Field(
        None,
        description="Regulatory context (e.g., pre-NDA, post-marketing, pediatric extension)",
    )
    target_population: str | None = Field(
        None,
        description="Description of the target patient population",
    )


class BenefitOutcome(BaseModel):
    """A quantified benefit outcome within a benefit-risk assessment."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique benefit outcome identifier")
    assessment_id: str = Field(
        ..., description="Parent benefit-risk assessment identifier"
    )
    outcome_name: str = Field(..., description="Name of the benefit outcome")
    category: OutcomeCategory = Field(..., description="Outcome category")
    description: str = Field(
        ..., description="Detailed description of the benefit outcome"
    )
    effect_size: float | None = Field(
        None, description="Measured effect size (e.g., hazard ratio, odds ratio)"
    )
    confidence_interval: str | None = Field(
        None, description="Confidence interval for the effect size (e.g., '0.55-0.78')"
    )
    p_value: float | None = Field(
        None, ge=0.0, le=1.0, description="Statistical p-value"
    )
    clinical_significance: str | None = Field(
        None,
        description="Narrative assessment of clinical significance",
    )
    severity: SeverityLevel | None = Field(
        None, description="Severity of the condition the benefit addresses"
    )
    likelihood: LikelihoodLevel | None = Field(
        None, description="Likelihood of achieving the benefit"
    )
    weight: float = Field(
        default=1.0,
        ge=0.0,
        le=10.0,
        description="Relative weight for multi-criteria decision analysis",
    )
    data_source: str | None = Field(
        None, description="Source of evidence (e.g., Phase III RCT, meta-analysis)"
    )
    evidence_quality: str | None = Field(
        None, description="Quality of evidence (e.g., high, moderate, low)"
    )


class RiskOutcome(BaseModel):
    """A quantified risk outcome within a benefit-risk assessment."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique risk outcome identifier")
    assessment_id: str = Field(
        ..., description="Parent benefit-risk assessment identifier"
    )
    outcome_name: str = Field(..., description="Name of the risk outcome")
    category: OutcomeCategory = Field(..., description="Outcome category")
    description: str = Field(
        ..., description="Detailed description of the risk outcome"
    )
    incidence_rate: float | None = Field(
        None,
        ge=0.0,
        description="Incidence rate (e.g., events per 100 patient-years)",
    )
    relative_risk: float | None = Field(
        None, ge=0.0, description="Relative risk compared to comparator"
    )
    severity: SeverityLevel = Field(..., description="Severity level of the risk")
    likelihood: LikelihoodLevel = Field(
        ..., description="Likelihood of the risk occurring"
    )
    reversibility: str | None = Field(
        None,
        description="Whether the risk is reversible (e.g., reversible, partially reversible, irreversible)",
    )
    management_strategy: str | None = Field(
        None,
        description="Risk management/mitigation strategy",
    )
    weight: float = Field(
        default=1.0,
        ge=0.0,
        le=10.0,
        description="Relative weight for multi-criteria decision analysis",
    )
    data_source: str | None = Field(
        None, description="Source of evidence (e.g., Phase III RCT, post-marketing)"
    )


class BenefitRiskMetrics(BaseModel):
    """Aggregated metrics across benefit-risk assessments."""

    model_config = ConfigDict(from_attributes=True)

    total_assessments: int = Field(ge=0, description="Total assessments")
    assessments_by_status: dict[str, int] = Field(
        default_factory=dict, description="Assessment counts by status"
    )
    assessments_by_framework: dict[str, int] = Field(
        default_factory=dict, description="Assessment counts by framework"
    )
    total_benefit_outcomes: int = Field(ge=0, description="Total benefit outcomes")
    total_risk_outcomes: int = Field(ge=0, description="Total risk outcomes")
    avg_benefits_per_assessment: float = Field(
        ge=0.0, description="Average benefit outcomes per assessment"
    )
    avg_risks_per_assessment: float = Field(
        ge=0.0, description="Average risk outcomes per assessment"
    )
    finalized_assessments: int = Field(
        ge=0, description="Number of finalized assessments"
    )
    superseded_assessments: int = Field(
        ge=0, description="Number of superseded assessments"
    )


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class AssessmentCreate(BaseModel):
    """Request to create a new benefit-risk assessment."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    drug_name: str = Field(..., description="Drug name")
    indication: str = Field(..., description="Therapeutic indication")
    comparator: str = Field(..., description="Comparator")
    framework: AssessmentFramework = Field(..., description="Evaluation framework")
    assessor: str = Field(..., description="Primary assessor")
    overall_conclusion: str | None = Field(None, description="Overall conclusion")
    regulatory_context: str | None = Field(None, description="Regulatory context")
    target_population: str | None = Field(None, description="Target population")


class AssessmentUpdate(BaseModel):
    """Request to update an existing benefit-risk assessment."""

    model_config = ConfigDict(from_attributes=True)

    drug_name: str | None = Field(None, description="Drug name")
    indication: str | None = Field(None, description="Indication")
    comparator: str | None = Field(None, description="Comparator")
    framework: AssessmentFramework | None = Field(None, description="Framework")
    assessor: str | None = Field(None, description="Assessor")
    overall_conclusion: str | None = Field(None, description="Overall conclusion")
    regulatory_context: str | None = Field(None, description="Regulatory context")
    target_population: str | None = Field(None, description="Target population")


class BenefitOutcomeCreate(BaseModel):
    """Request to create a benefit outcome."""

    model_config = ConfigDict(from_attributes=True)

    outcome_name: str = Field(..., description="Outcome name")
    category: OutcomeCategory = Field(..., description="Outcome category")
    description: str = Field(..., description="Description")
    effect_size: float | None = Field(None, description="Effect size")
    confidence_interval: str | None = Field(None, description="Confidence interval")
    p_value: float | None = Field(None, ge=0.0, le=1.0, description="P-value")
    clinical_significance: str | None = Field(None, description="Clinical significance")
    severity: SeverityLevel | None = Field(None, description="Severity")
    likelihood: LikelihoodLevel | None = Field(None, description="Likelihood")
    weight: float = Field(default=1.0, ge=0.0, le=10.0, description="Weight")
    data_source: str | None = Field(None, description="Data source")
    evidence_quality: str | None = Field(None, description="Evidence quality")


class BenefitOutcomeUpdate(BaseModel):
    """Request to update a benefit outcome."""

    model_config = ConfigDict(from_attributes=True)

    outcome_name: str | None = Field(None, description="Outcome name")
    category: OutcomeCategory | None = Field(None, description="Outcome category")
    description: str | None = Field(None, description="Description")
    effect_size: float | None = Field(None, description="Effect size")
    confidence_interval: str | None = Field(None, description="Confidence interval")
    p_value: float | None = Field(None, ge=0.0, le=1.0, description="P-value")
    clinical_significance: str | None = Field(None, description="Clinical significance")
    severity: SeverityLevel | None = Field(None, description="Severity")
    likelihood: LikelihoodLevel | None = Field(None, description="Likelihood")
    weight: float | None = Field(None, ge=0.0, le=10.0, description="Weight")
    data_source: str | None = Field(None, description="Data source")
    evidence_quality: str | None = Field(None, description="Evidence quality")


class RiskOutcomeCreate(BaseModel):
    """Request to create a risk outcome."""

    model_config = ConfigDict(from_attributes=True)

    outcome_name: str = Field(..., description="Outcome name")
    category: OutcomeCategory = Field(..., description="Outcome category")
    description: str = Field(..., description="Description")
    incidence_rate: float | None = Field(None, ge=0.0, description="Incidence rate")
    relative_risk: float | None = Field(None, ge=0.0, description="Relative risk")
    severity: SeverityLevel = Field(..., description="Severity level")
    likelihood: LikelihoodLevel = Field(..., description="Likelihood")
    reversibility: str | None = Field(None, description="Reversibility")
    management_strategy: str | None = Field(None, description="Management strategy")
    weight: float = Field(default=1.0, ge=0.0, le=10.0, description="Weight")
    data_source: str | None = Field(None, description="Data source")


class RiskOutcomeUpdate(BaseModel):
    """Request to update a risk outcome."""

    model_config = ConfigDict(from_attributes=True)

    outcome_name: str | None = Field(None, description="Outcome name")
    category: OutcomeCategory | None = Field(None, description="Outcome category")
    description: str | None = Field(None, description="Description")
    incidence_rate: float | None = Field(None, ge=0.0, description="Incidence rate")
    relative_risk: float | None = Field(None, ge=0.0, description="Relative risk")
    severity: SeverityLevel | None = Field(None, description="Severity")
    likelihood: LikelihoodLevel | None = Field(None, description="Likelihood")
    reversibility: str | None = Field(None, description="Reversibility")
    management_strategy: str | None = Field(None, description="Management strategy")
    weight: float | None = Field(None, ge=0.0, le=10.0, description="Weight")
    data_source: str | None = Field(None, description="Data source")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class AssessmentListResponse(BaseModel):
    """List of benefit-risk assessments."""

    model_config = ConfigDict(from_attributes=True)

    items: list[BenefitRiskAssessment] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class BenefitOutcomeListResponse(BaseModel):
    """List of benefit outcomes."""

    model_config = ConfigDict(from_attributes=True)

    items: list[BenefitOutcome] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class RiskOutcomeListResponse(BaseModel):
    """List of risk outcomes."""

    model_config = ConfigDict(from_attributes=True)

    items: list[RiskOutcome] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")
