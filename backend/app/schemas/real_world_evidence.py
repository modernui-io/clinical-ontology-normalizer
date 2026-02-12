"""Pydantic schemas for Real-World Evidence (RWE) Integration & Analysis.

Manages RWE operations: patient registries, real-world outcome tracking,
comparative effectiveness studies, health economic analyses (CEA/CUA/CBA),
and RWE data packages for regulatory submissions to FDA/EMA.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DataSourceType(str, Enum):
    """Type of real-world data source."""

    EHR = "ehr"
    CLAIMS = "claims"
    REGISTRY = "registry"
    PATIENT_REPORTED = "patient_reported"
    WEARABLE = "wearable"
    LAB_SYSTEM = "lab_system"
    PHARMACY = "pharmacy"


class StudyDesign(str, Enum):
    """Design of an RWE study."""

    RETROSPECTIVE_COHORT = "retrospective_cohort"
    PROSPECTIVE_COHORT = "prospective_cohort"
    CASE_CONTROL = "case_control"
    CROSS_SECTIONAL = "cross_sectional"
    PRAGMATIC_TRIAL = "pragmatic_trial"


class OutcomeType(str, Enum):
    """Type of real-world outcome being measured."""

    EFFECTIVENESS = "effectiveness"
    SAFETY = "safety"
    PATIENT_REPORTED = "patient_reported"
    ECONOMIC = "economic"
    COMPOSITE = "composite"


class AnalysisStatus(str, Enum):
    """Lifecycle status of an RWE analysis or study."""

    PLANNED = "planned"
    DATA_COLLECTION = "data_collection"
    ANALYSIS = "analysis"
    PEER_REVIEW = "peer_review"
    PUBLISHED = "published"
    SUBMITTED_TO_FDA = "submitted_to_fda"


class EvidenceGrade(str, Enum):
    """GRADE framework evidence quality rating."""

    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    VERY_LOW = "very_low"
    INSUFFICIENT = "insufficient"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class RWEDataSource(BaseModel):
    """A real-world data source used in RWE studies."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique data source identifier")
    name: str = Field(..., description="Data source name")
    data_source_type: DataSourceType = Field(..., description="Type of data source")
    description: str = Field(..., description="Detailed description of the data source")
    patient_count: int = Field(ge=0, description="Number of patients in the data source")
    date_range_start: datetime = Field(..., description="Start of data coverage period")
    date_range_end: datetime = Field(..., description="End of data coverage period")
    geographic_coverage: list[str] = Field(
        default_factory=list, description="Geographic regions covered"
    )
    data_elements: list[str] = Field(
        default_factory=list, description="Types of data elements available"
    )
    refresh_frequency: str = Field(..., description="How often the data is refreshed (e.g., daily, weekly, monthly)")
    data_lag_days: int = Field(ge=0, description="Average number of days between event and data availability")
    quality_score: float = Field(
        ge=0.0, le=100.0, description="Overall data quality score (0-100)"
    )
    vendor: str = Field(..., description="Data vendor or provider organization")
    contract_id: str | None = Field(None, description="Associated data licensing contract ID")


class RWEStudy(BaseModel):
    """A real-world evidence study or analysis project."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique study identifier")
    trial_id: str = Field(..., description="Associated clinical trial identifier")
    study_name: str = Field(..., description="Name of the RWE study")
    study_design: StudyDesign = Field(..., description="Study design type")
    indication: str = Field(..., description="Therapeutic indication being studied")
    comparator: str = Field(..., description="Comparator treatment or standard of care")
    primary_endpoint: str = Field(..., description="Primary study endpoint")
    secondary_endpoints: list[str] = Field(
        default_factory=list, description="Secondary study endpoints"
    )
    target_population: str = Field(..., description="Description of the target patient population")
    sample_size: int = Field(ge=0, description="Target or achieved sample size")
    status: AnalysisStatus = Field(
        default=AnalysisStatus.PLANNED, description="Current study status"
    )
    start_date: datetime = Field(..., description="Study start date")
    completion_date: datetime | None = Field(None, description="Study completion date")
    lead_analyst: str = Field(..., description="Lead analyst or principal investigator")
    protocol_document: str | None = Field(None, description="Reference to study protocol document")


class RealWorldOutcome(BaseModel):
    """A measured outcome from an RWE study."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique outcome identifier")
    study_id: str = Field(..., description="Associated RWE study identifier")
    outcome_type: OutcomeType = Field(..., description="Type of outcome")
    outcome_name: str = Field(..., description="Name of the outcome measure")
    measurement_method: str = Field(..., description="Method used to measure the outcome")
    timepoint: str = Field(..., description="Timepoint of measurement (e.g., 6 months, 1 year)")
    result_value: float = Field(..., description="Observed result value")
    confidence_interval_lower: float = Field(..., description="Lower bound of 95% confidence interval")
    confidence_interval_upper: float = Field(..., description="Upper bound of 95% confidence interval")
    p_value: float | None = Field(None, ge=0.0, le=1.0, description="Statistical p-value")
    clinical_significance: str = Field(..., description="Assessment of clinical significance")
    evidence_grade: EvidenceGrade = Field(..., description="GRADE evidence quality rating")
    population_size: int = Field(ge=0, description="Size of the population analyzed")


class ComparativeEffectiveness(BaseModel):
    """Results from a comparative effectiveness analysis."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique comparative effectiveness identifier")
    study_id: str = Field(..., description="Associated RWE study identifier")
    treatment_arm: str = Field(..., description="Treatment arm name")
    comparator_arm: str = Field(..., description="Comparator arm name")
    endpoint: str = Field(..., description="Endpoint being compared")
    hazard_ratio: float | None = Field(None, description="Hazard ratio (time-to-event)")
    odds_ratio: float | None = Field(None, description="Odds ratio (binary outcomes)")
    relative_risk: float | None = Field(None, description="Relative risk")
    absolute_risk_reduction: float | None = Field(None, description="Absolute risk reduction")
    nnt: int | None = Field(None, ge=1, description="Number needed to treat")
    nnh: int | None = Field(None, ge=1, description="Number needed to harm")
    favors: str = Field(..., description="Which arm the result favors")
    statistical_method: str = Field(..., description="Statistical method used for comparison")


class HealthEconomicAnalysis(BaseModel):
    """Health economic analysis results (CEA, CUA, CBA)."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique health economics identifier")
    study_id: str = Field(..., description="Associated RWE study identifier")
    analysis_type: str = Field(..., description="Type of economic analysis (CEA, CUA, CBA)")
    perspective: str = Field(..., description="Analysis perspective (payer, societal, healthcare system)")
    time_horizon: str = Field(..., description="Time horizon of the analysis (e.g., lifetime, 5 years)")
    discount_rate: float = Field(ge=0.0, le=1.0, description="Annual discount rate applied")
    cost_per_qaly: float | None = Field(None, description="Cost per quality-adjusted life year")
    incremental_cost: float = Field(..., description="Incremental cost vs comparator")
    incremental_effectiveness: float = Field(..., description="Incremental effectiveness vs comparator")
    icer: float | None = Field(None, description="Incremental cost-effectiveness ratio")
    willingness_to_pay_threshold: float = Field(
        ..., description="Willingness-to-pay threshold used for evaluation"
    )
    cost_effective: bool = Field(..., description="Whether the treatment is cost-effective at the threshold")
    sensitivity_analysis_results: dict[str, float] = Field(
        default_factory=dict,
        description="Key sensitivity analysis results (parameter -> ICER)",
    )


class RWESubmissionPackage(BaseModel):
    """An RWE data package prepared for regulatory submission."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique submission package identifier")
    study_id: str = Field(..., description="Associated RWE study identifier")
    regulatory_authority: str = Field(..., description="Target regulatory authority (e.g., FDA, EMA, PMDA)")
    submission_date: datetime | None = Field(None, description="Date of submission")
    package_type: str = Field(
        ..., description="Type of submission package (e.g., supplemental NDA, label expansion, post-market)"
    )
    data_sources_included: list[str] = Field(
        default_factory=list, description="Data source IDs included in the package"
    )
    methodology_summary: str = Field(..., description="Summary of analytical methodology")
    key_findings: list[str] = Field(
        default_factory=list, description="Key findings from the RWE analysis"
    )
    status: AnalysisStatus = Field(
        default=AnalysisStatus.PLANNED, description="Submission package status"
    )
    reviewer_feedback: str | None = Field(None, description="Feedback from regulatory reviewers")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class RWEDataSourceCreate(BaseModel):
    """Request to create a new RWE data source."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Data source name")
    data_source_type: DataSourceType = Field(..., description="Type of data source")
    description: str = Field(..., description="Detailed description")
    patient_count: int = Field(ge=0, description="Number of patients")
    date_range_start: datetime = Field(..., description="Data coverage start")
    date_range_end: datetime = Field(..., description="Data coverage end")
    geographic_coverage: list[str] = Field(default_factory=list, description="Geographic regions")
    data_elements: list[str] = Field(default_factory=list, description="Data elements available")
    refresh_frequency: str = Field(..., description="Refresh frequency")
    data_lag_days: int = Field(ge=0, description="Data lag in days")
    quality_score: float = Field(ge=0.0, le=100.0, description="Quality score")
    vendor: str = Field(..., description="Data vendor")
    contract_id: str | None = Field(None, description="Contract ID")


class RWEDataSourceUpdate(BaseModel):
    """Request to update an RWE data source."""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = Field(None, description="Data source name")
    description: str | None = Field(None, description="Description")
    patient_count: int | None = Field(None, ge=0, description="Patient count")
    date_range_end: datetime | None = Field(None, description="Data coverage end")
    refresh_frequency: str | None = Field(None, description="Refresh frequency")
    data_lag_days: int | None = Field(None, ge=0, description="Data lag")
    quality_score: float | None = Field(None, ge=0.0, le=100.0, description="Quality score")
    contract_id: str | None = Field(None, description="Contract ID")


class RWEStudyCreate(BaseModel):
    """Request to create/initiate a new RWE study."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Associated trial ID")
    study_name: str = Field(..., description="Study name")
    study_design: StudyDesign = Field(..., description="Study design")
    indication: str = Field(..., description="Therapeutic indication")
    comparator: str = Field(..., description="Comparator treatment")
    primary_endpoint: str = Field(..., description="Primary endpoint")
    secondary_endpoints: list[str] = Field(default_factory=list, description="Secondary endpoints")
    target_population: str = Field(..., description="Target population")
    sample_size: int = Field(ge=0, description="Target sample size")
    lead_analyst: str = Field(..., description="Lead analyst")
    protocol_document: str | None = Field(None, description="Protocol document reference")


class RWEStudyUpdate(BaseModel):
    """Request to update an RWE study."""

    model_config = ConfigDict(from_attributes=True)

    study_name: str | None = Field(None, description="Study name")
    status: AnalysisStatus | None = Field(None, description="Study status")
    sample_size: int | None = Field(None, ge=0, description="Sample size")
    completion_date: datetime | None = Field(None, description="Completion date")
    lead_analyst: str | None = Field(None, description="Lead analyst")
    protocol_document: str | None = Field(None, description="Protocol document")


class RealWorldOutcomeCreate(BaseModel):
    """Request to record a real-world outcome."""

    model_config = ConfigDict(from_attributes=True)

    study_id: str = Field(..., description="Study ID")
    outcome_type: OutcomeType = Field(..., description="Outcome type")
    outcome_name: str = Field(..., description="Outcome name")
    measurement_method: str = Field(..., description="Measurement method")
    timepoint: str = Field(..., description="Timepoint")
    result_value: float = Field(..., description="Result value")
    confidence_interval_lower: float = Field(..., description="CI lower bound")
    confidence_interval_upper: float = Field(..., description="CI upper bound")
    p_value: float | None = Field(None, ge=0.0, le=1.0, description="P-value")
    clinical_significance: str = Field(..., description="Clinical significance assessment")
    evidence_grade: EvidenceGrade = Field(..., description="Evidence grade")
    population_size: int = Field(ge=0, description="Population size")


class RealWorldOutcomeUpdate(BaseModel):
    """Request to update a real-world outcome."""

    model_config = ConfigDict(from_attributes=True)

    result_value: float | None = Field(None, description="Result value")
    confidence_interval_lower: float | None = Field(None, description="CI lower")
    confidence_interval_upper: float | None = Field(None, description="CI upper")
    p_value: float | None = Field(None, ge=0.0, le=1.0, description="P-value")
    clinical_significance: str | None = Field(None, description="Clinical significance")
    evidence_grade: EvidenceGrade | None = Field(None, description="Evidence grade")
    population_size: int | None = Field(None, ge=0, description="Population size")


class ComparativeEffectivenessCreate(BaseModel):
    """Request to record a comparative effectiveness analysis."""

    model_config = ConfigDict(from_attributes=True)

    study_id: str = Field(..., description="Study ID")
    treatment_arm: str = Field(..., description="Treatment arm")
    comparator_arm: str = Field(..., description="Comparator arm")
    endpoint: str = Field(..., description="Endpoint")
    hazard_ratio: float | None = Field(None, description="Hazard ratio")
    odds_ratio: float | None = Field(None, description="Odds ratio")
    relative_risk: float | None = Field(None, description="Relative risk")
    absolute_risk_reduction: float | None = Field(None, description="Absolute risk reduction")
    nnt: int | None = Field(None, ge=1, description="NNT")
    nnh: int | None = Field(None, ge=1, description="NNH")
    favors: str = Field(..., description="Which arm favored")
    statistical_method: str = Field(..., description="Statistical method")


class ComparativeEffectivenessUpdate(BaseModel):
    """Request to update a comparative effectiveness record."""

    model_config = ConfigDict(from_attributes=True)

    hazard_ratio: float | None = Field(None, description="Hazard ratio")
    odds_ratio: float | None = Field(None, description="Odds ratio")
    relative_risk: float | None = Field(None, description="Relative risk")
    absolute_risk_reduction: float | None = Field(None, description="Absolute risk reduction")
    nnt: int | None = Field(None, ge=1, description="NNT")
    nnh: int | None = Field(None, ge=1, description="NNH")
    favors: str | None = Field(None, description="Which arm favored")


class HealthEconomicAnalysisCreate(BaseModel):
    """Request to create a health economic analysis."""

    model_config = ConfigDict(from_attributes=True)

    study_id: str = Field(..., description="Study ID")
    analysis_type: str = Field(..., description="Analysis type (CEA, CUA, CBA)")
    perspective: str = Field(..., description="Analysis perspective")
    time_horizon: str = Field(..., description="Time horizon")
    discount_rate: float = Field(ge=0.0, le=1.0, description="Discount rate")
    cost_per_qaly: float | None = Field(None, description="Cost per QALY")
    incremental_cost: float = Field(..., description="Incremental cost")
    incremental_effectiveness: float = Field(..., description="Incremental effectiveness")
    icer: float | None = Field(None, description="ICER")
    willingness_to_pay_threshold: float = Field(..., description="WTP threshold")
    cost_effective: bool = Field(..., description="Is cost-effective")
    sensitivity_analysis_results: dict[str, float] = Field(
        default_factory=dict, description="Sensitivity analysis results"
    )


class HealthEconomicAnalysisUpdate(BaseModel):
    """Request to update a health economic analysis."""

    model_config = ConfigDict(from_attributes=True)

    cost_per_qaly: float | None = Field(None, description="Cost per QALY")
    incremental_cost: float | None = Field(None, description="Incremental cost")
    incremental_effectiveness: float | None = Field(None, description="Incremental effectiveness")
    icer: float | None = Field(None, description="ICER")
    willingness_to_pay_threshold: float | None = Field(None, description="WTP threshold")
    cost_effective: bool | None = Field(None, description="Is cost-effective")
    sensitivity_analysis_results: dict[str, float] | None = Field(
        None, description="Sensitivity analysis results"
    )


class RWESubmissionPackageCreate(BaseModel):
    """Request to create an RWE submission package."""

    model_config = ConfigDict(from_attributes=True)

    study_id: str = Field(..., description="Study ID")
    regulatory_authority: str = Field(..., description="Regulatory authority")
    package_type: str = Field(..., description="Package type")
    data_sources_included: list[str] = Field(default_factory=list, description="Data source IDs")
    methodology_summary: str = Field(..., description="Methodology summary")
    key_findings: list[str] = Field(default_factory=list, description="Key findings")


class RWESubmissionPackageUpdate(BaseModel):
    """Request to update an RWE submission package."""

    model_config = ConfigDict(from_attributes=True)

    submission_date: datetime | None = Field(None, description="Submission date")
    status: AnalysisStatus | None = Field(None, description="Status")
    key_findings: list[str] | None = Field(None, description="Key findings")
    reviewer_feedback: str | None = Field(None, description="Reviewer feedback")
    methodology_summary: str | None = Field(None, description="Methodology summary")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class RWEDataSourceListResponse(BaseModel):
    """List of RWE data sources."""

    model_config = ConfigDict(from_attributes=True)

    items: list[RWEDataSource] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class RWEStudyListResponse(BaseModel):
    """List of RWE studies."""

    model_config = ConfigDict(from_attributes=True)

    items: list[RWEStudy] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class RealWorldOutcomeListResponse(BaseModel):
    """List of real-world outcomes."""

    model_config = ConfigDict(from_attributes=True)

    items: list[RealWorldOutcome] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class ComparativeEffectivenessListResponse(BaseModel):
    """List of comparative effectiveness analyses."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ComparativeEffectiveness] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class HealthEconomicAnalysisListResponse(BaseModel):
    """List of health economic analyses."""

    model_config = ConfigDict(from_attributes=True)

    items: list[HealthEconomicAnalysis] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class RWESubmissionPackageListResponse(BaseModel):
    """List of RWE submission packages."""

    model_config = ConfigDict(from_attributes=True)

    items: list[RWESubmissionPackage] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Metrics / dashboard
# ---------------------------------------------------------------------------


class RWEMetrics(BaseModel):
    """Aggregated Real-World Evidence operational metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_data_sources: int = Field(ge=0, description="Total registered data sources")
    total_patients_across_sources: int = Field(ge=0, description="Total patients across all sources")
    average_data_quality_score: float = Field(ge=0.0, description="Average quality score across sources")
    total_studies: int = Field(ge=0, description="Total RWE studies")
    studies_by_status: dict[str, int] = Field(
        default_factory=dict, description="Study counts by status"
    )
    studies_by_design: dict[str, int] = Field(
        default_factory=dict, description="Study counts by design type"
    )
    total_outcomes: int = Field(ge=0, description="Total recorded outcomes")
    outcomes_by_type: dict[str, int] = Field(
        default_factory=dict, description="Outcome counts by type"
    )
    total_comparative_analyses: int = Field(ge=0, description="Total comparative effectiveness analyses")
    total_health_economic_analyses: int = Field(ge=0, description="Total health economic analyses")
    cost_effective_treatments: int = Field(ge=0, description="Number of cost-effective treatments identified")
    total_submission_packages: int = Field(ge=0, description="Total submission packages")
    submissions_by_authority: dict[str, int] = Field(
        default_factory=dict, description="Submission counts by regulatory authority"
    )
    average_evidence_grade: str = Field(
        default="", description="Most common evidence grade across outcomes"
    )
