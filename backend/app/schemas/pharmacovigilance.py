"""Pydantic schemas for Pharmacovigilance Signal Management (CLINICAL-4).

Supports the full pharmacovigilance lifecycle:
- ICSR (Individual Case Safety Report) management
- Safety signal detection via disproportionality analysis (PRR, ROR, IC, EBGM)
- Signal classification and assessment workflow
- MedDRA coding and hierarchy navigation
- Periodic safety report generation (PSUR/PBRER/DSUR)
- Regulatory action tracking
- Pharmacovigilance metrics dashboard
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SignalSource(str, Enum):
    """Source from which a pharmacovigilance signal was detected."""

    CLINICAL_TRIAL = "CLINICAL_TRIAL"
    SPONTANEOUS_REPORT = "SPONTANEOUS_REPORT"
    LITERATURE = "LITERATURE"
    SOCIAL_MEDIA = "SOCIAL_MEDIA"
    EHR_DATA = "EHR_DATA"
    REGISTRY = "REGISTRY"
    POST_MARKET_STUDY = "POST_MARKET_STUDY"


class SignalClassification(str, Enum):
    """Lifecycle classification of a pharmacovigilance signal."""

    VALIDATED = "VALIDATED"
    REFUTED = "REFUTED"
    UNDER_EVALUATION = "UNDER_EVALUATION"
    MONITORING = "MONITORING"
    CLOSED = "CLOSED"


class MedDRALevel(str, Enum):
    """MedDRA hierarchy level."""

    SOC = "SOC"
    HLGT = "HLGT"
    HLT = "HLT"
    PT = "PT"
    LLT = "LLT"


class DisproportionalityMethod(str, Enum):
    """Statistical method for disproportionality analysis."""

    PRR = "PRR"
    ROR = "ROR"
    BCPNN = "BCPNN"
    MGPS = "MGPS"
    EBGM = "EBGM"


class CausalityCategory(str, Enum):
    """WHO-UMC causality assessment category."""

    CERTAIN = "CERTAIN"
    PROBABLE = "PROBABLE"
    POSSIBLE = "POSSIBLE"
    UNLIKELY = "UNLIKELY"
    CONDITIONAL = "CONDITIONAL"
    UNASSESSABLE = "UNASSESSABLE"


class RegulatoryActionType(str, Enum):
    """Type of regulatory action taken in response to a safety signal."""

    LABELING_CHANGE = "LABELING_CHANGE"
    REMS = "REMS"
    BOXED_WARNING = "BOXED_WARNING"
    DEAR_HEALTHCARE_PROVIDER = "DEAR_HEALTHCARE_PROVIDER"
    MARKET_WITHDRAWAL = "MARKET_WITHDRAWAL"
    SAFETY_COMMUNICATION = "SAFETY_COMMUNICATION"
    RECALL = "RECALL"


class ICSRStatus(str, Enum):
    """Lifecycle status of an Individual Case Safety Report."""

    INITIAL = "INITIAL"
    FOLLOW_UP = "FOLLOW_UP"
    FINAL = "FINAL"
    NULLIFIED = "NULLIFIED"


class ReportType(str, Enum):
    """Type of periodic safety report."""

    PSUR = "PSUR"
    PBRER = "PBRER"
    DSUR = "DSUR"


class RegulatoryActionStatus(str, Enum):
    """Status of a regulatory action."""

    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    IMPLEMENTED = "IMPLEMENTED"
    CLOSED = "CLOSED"


# ---------------------------------------------------------------------------
# Core Models
# ---------------------------------------------------------------------------


class MedDRATerm(BaseModel):
    """A term in the MedDRA hierarchy."""

    model_config = ConfigDict(from_attributes=True)

    code: str = Field(..., description="MedDRA code")
    term: str = Field(..., description="MedDRA term text")
    level: MedDRALevel = Field(..., description="Hierarchy level")
    parent_code: Optional[str] = Field(None, description="Parent term code")
    soc_code: Optional[str] = Field(None, description="System Organ Class code")


class ICSR(BaseModel):
    """Individual Case Safety Report (E2B/R3 compatible)."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique case identifier")
    case_number: str = Field(..., description="Case reference number")
    patient_age: Optional[int] = Field(None, description="Patient age in years")
    patient_sex: Optional[str] = Field(None, description="Patient sex (M/F/Unknown)")
    reporter_type: str = Field(..., description="Reporter type (Physician, Pharmacist, Consumer, Other)")
    drug_name: str = Field(..., description="Suspect drug name")
    indication: Optional[str] = Field(None, description="Drug indication")
    event_terms: list[str] = Field(default_factory=list, description="List of adverse event terms (MedDRA PTs)")
    onset_date: Optional[datetime] = Field(None, description="Date of adverse event onset")
    outcome: Optional[str] = Field(None, description="Event outcome (Recovered, Not Recovered, Fatal, etc.)")
    seriousness_criteria: list[str] = Field(default_factory=list, description="Seriousness criteria met")
    causality: CausalityCategory = Field(CausalityCategory.POSSIBLE, description="WHO-UMC causality assessment")
    status: ICSRStatus = Field(ICSRStatus.INITIAL, description="Report status")
    received_date: datetime = Field(..., description="Date report was received")
    source: SignalSource = Field(SignalSource.SPONTANEOUS_REPORT, description="Report source")
    country: str = Field("US", description="Country of origin")
    narrative: Optional[str] = Field(None, description="Case narrative")


class ICSRCreate(BaseModel):
    """Create payload for a new ICSR."""

    case_number: str = Field(..., description="Case reference number")
    patient_age: Optional[int] = Field(None, ge=0, le=120, description="Patient age")
    patient_sex: Optional[str] = Field(None, description="Patient sex")
    reporter_type: str = Field("Physician", description="Reporter type")
    drug_name: str = Field(..., description="Suspect drug name")
    indication: Optional[str] = Field(None, description="Drug indication")
    event_terms: list[str] = Field(..., min_length=1, description="Adverse event terms")
    onset_date: Optional[datetime] = Field(None, description="Event onset date")
    outcome: Optional[str] = Field(None, description="Event outcome")
    seriousness_criteria: list[str] = Field(default_factory=list, description="Seriousness criteria")
    causality: CausalityCategory = Field(CausalityCategory.POSSIBLE, description="Causality assessment")
    source: SignalSource = Field(SignalSource.SPONTANEOUS_REPORT, description="Report source")
    country: str = Field("US", description="Country of origin")
    narrative: Optional[str] = Field(None, description="Case narrative")


class ICSRUpdate(BaseModel):
    """Update payload for an existing ICSR."""

    patient_age: Optional[int] = Field(None, ge=0, le=120)
    patient_sex: Optional[str] = None
    event_terms: Optional[list[str]] = None
    onset_date: Optional[datetime] = None
    outcome: Optional[str] = None
    seriousness_criteria: Optional[list[str]] = None
    causality: Optional[CausalityCategory] = None
    status: Optional[ICSRStatus] = None
    narrative: Optional[str] = None


class SignalRecord(BaseModel):
    """A pharmacovigilance safety signal record."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Signal identifier")
    title: str = Field(..., description="Signal title")
    description: str = Field(..., description="Signal description")
    drug_name: str = Field(..., description="Drug associated with signal")
    event_term: str = Field(..., description="Adverse event term (MedDRA PT)")
    meddra_pt_code: Optional[str] = Field(None, description="MedDRA Preferred Term code")
    source: SignalSource = Field(..., description="Signal source")
    classification: SignalClassification = Field(
        SignalClassification.UNDER_EVALUATION, description="Signal classification"
    )
    detected_date: datetime = Field(..., description="Date signal was detected")
    detection_method: Optional[str] = Field(None, description="Method used to detect signal")
    prr: Optional[float] = Field(None, description="Proportional Reporting Ratio")
    ror: Optional[float] = Field(None, description="Reporting Odds Ratio")
    ic025: Optional[float] = Field(None, description="Information Component lower 95% CI (BCPNN)")
    ebgm: Optional[float] = Field(None, description="Empirical Bayesian Geometric Mean (MGPS)")
    case_count: int = Field(0, description="Number of cases supporting signal")
    expected_count: Optional[float] = Field(None, description="Expected case count")
    background_rate: Optional[float] = Field(None, description="Background incidence rate")
    evidence_strength: Optional[str] = Field(None, description="Evidence strength (strong/moderate/weak)")
    assessor: Optional[str] = Field(None, description="Assessor name")
    assessment_date: Optional[datetime] = Field(None, description="Assessment date")
    action_taken: Optional[str] = Field(None, description="Action taken")
    regulatory_action_type: Optional[RegulatoryActionType] = Field(None, description="Regulatory action type")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


class SignalCreate(BaseModel):
    """Create payload for a new signal record."""

    title: str = Field(..., description="Signal title")
    description: str = Field(..., description="Signal description")
    drug_name: str = Field(..., description="Drug name")
    event_term: str = Field(..., description="Adverse event term")
    meddra_pt_code: Optional[str] = Field(None, description="MedDRA PT code")
    source: SignalSource = Field(SignalSource.CLINICAL_TRIAL, description="Source")
    detection_method: Optional[str] = Field(None, description="Detection method")
    case_count: int = Field(0, ge=0, description="Case count")
    expected_count: Optional[float] = Field(None, ge=0, description="Expected count")
    background_rate: Optional[float] = Field(None, ge=0, description="Background rate")


class SignalUpdate(BaseModel):
    """Update payload for an existing signal record."""

    classification: Optional[SignalClassification] = None
    assessor: Optional[str] = None
    assessment_date: Optional[datetime] = None
    action_taken: Optional[str] = None
    regulatory_action_type: Optional[RegulatoryActionType] = None
    evidence_strength: Optional[str] = None
    description: Optional[str] = None
    case_count: Optional[int] = Field(None, ge=0)


class DisproportionalityResult(BaseModel):
    """Result from a disproportionality analysis calculation."""

    model_config = ConfigDict(from_attributes=True)

    method: DisproportionalityMethod = Field(..., description="Statistical method")
    drug: str = Field(..., description="Drug name")
    event: str = Field(..., description="Event term")
    observed: int = Field(..., description="Observed case count")
    expected: float = Field(..., description="Expected case count")
    measure: float = Field(..., description="Disproportionality measure value")
    lower_ci: float = Field(..., description="Lower confidence interval")
    upper_ci: float = Field(..., description="Upper confidence interval")
    signal_detected: bool = Field(..., description="Whether the threshold for signal was met")


class PeriodicSafetyReport(BaseModel):
    """Periodic safety report (PSUR/PBRER/DSUR)."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Report identifier")
    drug_name: str = Field(..., description="Drug name")
    report_type: ReportType = Field(..., description="Report type")
    period_start: datetime = Field(..., description="Reporting period start")
    period_end: datetime = Field(..., description="Reporting period end")
    total_cases: int = Field(0, description="Total cases in period")
    serious_cases: int = Field(0, description="Serious cases in period")
    fatal_cases: int = Field(0, description="Fatal cases in period")
    new_signals: int = Field(0, description="New signals detected")
    updated_signals: int = Field(0, description="Signals updated in period")
    closed_signals: int = Field(0, description="Signals closed in period")
    benefit_risk_assessment: Optional[str] = Field(None, description="Benefit-risk summary")
    submitted_to: Optional[str] = Field(None, description="Regulatory authority")
    submission_date: Optional[datetime] = Field(None, description="Date submitted")
    created_at: datetime = Field(..., description="Record creation timestamp")


class RegulatoryAction(BaseModel):
    """A regulatory action taken in response to a safety signal."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Action identifier")
    signal_id: str = Field(..., description="Associated signal ID")
    action_type: RegulatoryActionType = Field(..., description="Action type")
    agency: str = Field(..., description="Regulatory agency (FDA, EMA, etc.)")
    description: str = Field(..., description="Action description")
    effective_date: Optional[datetime] = Field(None, description="Effective date")
    status: RegulatoryActionStatus = Field(RegulatoryActionStatus.PROPOSED, description="Action status")
    implementation_date: Optional[datetime] = Field(None, description="Implementation date")
    created_at: datetime = Field(..., description="Record creation timestamp")


class RegulatoryActionCreate(BaseModel):
    """Create payload for a new regulatory action."""

    signal_id: str = Field(..., description="Associated signal ID")
    action_type: RegulatoryActionType = Field(..., description="Action type")
    agency: str = Field(..., description="Regulatory agency")
    description: str = Field(..., description="Action description")
    effective_date: Optional[datetime] = Field(None, description="Effective date")


class CaseSeriesResult(BaseModel):
    """Result of a case series analysis for a drug-event pair."""

    model_config = ConfigDict(from_attributes=True)

    drug_name: str = Field(..., description="Drug name")
    event_term: str = Field(..., description="Event term")
    total_cases: int = Field(0, description="Total matching cases")
    serious_count: int = Field(0, description="Serious cases")
    fatal_count: int = Field(0, description="Fatal cases")
    median_age: Optional[float] = Field(None, description="Median patient age")
    sex_distribution: dict[str, int] = Field(default_factory=dict, description="Sex distribution")
    outcome_distribution: dict[str, int] = Field(default_factory=dict, description="Outcome distribution")
    causality_distribution: dict[str, int] = Field(default_factory=dict, description="Causality distribution")
    median_onset_days: Optional[float] = Field(None, description="Median time to onset (days)")
    country_distribution: dict[str, int] = Field(default_factory=dict, description="Country distribution")
    reporter_distribution: dict[str, int] = Field(default_factory=dict, description="Reporter type distribution")
    cases: list[ICSR] = Field(default_factory=list, description="Individual cases")


# ---------------------------------------------------------------------------
# List / paginated response models
# ---------------------------------------------------------------------------


class ICSRListResponse(BaseModel):
    """Paginated response for ICSR queries."""

    items: list[ICSR]
    total: int
    limit: int
    offset: int


class SignalListResponse(BaseModel):
    """Paginated response for signal queries."""

    items: list[SignalRecord]
    total: int
    limit: int
    offset: int


class PeriodicSafetyReportListResponse(BaseModel):
    """Paginated response for periodic safety reports."""

    items: list[PeriodicSafetyReport]
    total: int
    limit: int
    offset: int


class RegulatoryActionListResponse(BaseModel):
    """Paginated response for regulatory actions."""

    items: list[RegulatoryAction]
    total: int
    limit: int
    offset: int


class MedDRASearchResponse(BaseModel):
    """Response for MedDRA term search."""

    terms: list[MedDRATerm]
    total: int


class MedDRAHierarchyResponse(BaseModel):
    """Response for MedDRA hierarchy query."""

    term: MedDRATerm
    ancestors: list[MedDRATerm]
    children: list[MedDRATerm]


class DisproportionalityAnalysisResponse(BaseModel):
    """Response for disproportionality analysis."""

    drug: str
    event: str
    results: list[DisproportionalityResult]
    signal_detected: bool
    strongest_method: Optional[str] = None


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class SignalDetectionRequest(BaseModel):
    """Request to run signal detection for a drug-event pair."""

    drug_name: str = Field(..., description="Drug name")
    event_term: str = Field(..., description="Event term")
    methods: list[DisproportionalityMethod] = Field(
        default_factory=lambda: [
            DisproportionalityMethod.PRR,
            DisproportionalityMethod.ROR,
            DisproportionalityMethod.BCPNN,
            DisproportionalityMethod.EBGM,
        ],
        description="Methods to use",
    )


class GenerateReportRequest(BaseModel):
    """Request to generate a periodic safety report."""

    drug_name: str = Field(..., description="Drug name")
    report_type: ReportType = Field(ReportType.DSUR, description="Report type")
    period_start: datetime = Field(..., description="Period start date")
    period_end: datetime = Field(..., description="Period end date")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class PharmacovigilanceMetrics(BaseModel):
    """Aggregated pharmacovigilance dashboard metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_icsrs: int = Field(0, description="Total ICSRs in system")
    icsrs_by_status: dict[str, int] = Field(default_factory=dict, description="ICSR count by status")
    icsrs_by_source: dict[str, int] = Field(default_factory=dict, description="ICSR count by source")
    icsrs_by_causality: dict[str, int] = Field(default_factory=dict, description="ICSR count by causality")
    total_signals: int = Field(0, description="Total signals")
    signals_by_classification: dict[str, int] = Field(default_factory=dict, description="Signal count by classification")
    validated_signals: int = Field(0, description="Validated signals")
    under_evaluation_signals: int = Field(0, description="Signals under evaluation")
    total_periodic_reports: int = Field(0, description="Total periodic reports")
    total_regulatory_actions: int = Field(0, description="Total regulatory actions")
    top_reported_drugs: list[dict] = Field(default_factory=list, description="Top drugs by report count")
    top_reported_events: list[dict] = Field(default_factory=list, description="Top events by report count")
    serious_case_rate: float = Field(0.0, description="Percentage of serious cases")
    fatal_case_rate: float = Field(0.0, description="Percentage of fatal cases")
    meddra_terms_loaded: int = Field(0, description="Number of MedDRA terms loaded")
