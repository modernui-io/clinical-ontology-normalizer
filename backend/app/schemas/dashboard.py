"""Dashboard response schemas for role-based views."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ==============================================================================
# Shared Components
# ==============================================================================


class CERCitationSummary(BaseModel):
    """Simplified CER citation for dashboard display."""

    claim: str = Field(..., description="Main assertion")
    strength: str = Field(..., description="Citation strength (HIGH/MEDIUM/LOW)")
    evidence_count: int = Field(..., description="Number of supporting evidence items")


class ActionItem(BaseModel):
    """An actionable item for dashboard display."""

    priority: str = Field(..., description="Priority level (high/medium/low)")
    title: str = Field(..., description="Action title")
    description: str = Field(..., description="Action description")
    category: str = Field(..., description="Category of action")
    patient_id: str | None = Field(None, description="Associated patient if applicable")
    estimated_impact: str | None = Field(None, description="Estimated impact (revenue, risk, etc.)")


class DashboardMetadata(BaseModel):
    """Common metadata for all dashboards."""

    generated_at: datetime = Field(..., description="When this dashboard was generated")
    patient_id: str | None = Field(None, description="Patient ID if patient-specific view")
    time_window: str = Field(default="24h", description="Time window for statistics")


# ==============================================================================
# Provider Dashboard
# ==============================================================================


class DiagnosisSummary(BaseModel):
    """Summary of a differential diagnosis."""

    name: str
    probability: float
    urgency: str
    icd10_code: str | None = None
    cer_citation: CERCitationSummary | None = None


class RiskScoreSummary(BaseModel):
    """Summary of a clinical risk score."""

    calculator_name: str
    risk_level: str  # low, moderate, high, very_high
    score_value: float | None = None
    interpretation: str


class DrugAlertSummary(BaseModel):
    """Summary of a drug interaction or safety alert."""

    alert_type: str  # interaction, contraindication, pregnancy, lactation
    severity: str  # major, moderate, minor
    drug1: str
    drug2: str | None = None
    description: str


class ClinicalSummarySummary(BaseModel):
    """Summary of clinical summary data."""

    one_liner: str
    active_problems_count: int
    medication_count: int
    critical_findings: list[str]


class LabInterpretationSummary(BaseModel):
    """Summary of lab interpretation."""

    lab_name: str
    value: float
    unit: str
    interpretation: str  # normal, low, high, critical
    reference_range: str


class ProviderDashboardResponse(BaseModel):
    """Response for GET /dashboard/provider."""

    metadata: DashboardMetadata

    # Clinical Summary
    clinical_summary: ClinicalSummarySummary | None = Field(
        None, description="Patient clinical summary"
    )

    # Differential Diagnoses
    differential_diagnoses: list[DiagnosisSummary] = Field(
        default_factory=list, description="Top differential diagnoses"
    )

    # Risk Scores
    risk_scores: list[RiskScoreSummary] = Field(
        default_factory=list, description="Calculated risk scores"
    )

    # Drug Alerts
    drug_alerts: list[DrugAlertSummary] = Field(
        default_factory=list, description="Active drug alerts"
    )

    # Lab Interpretations
    abnormal_labs: list[LabInterpretationSummary] = Field(
        default_factory=list, description="Abnormal lab values with interpretations"
    )

    # Summary Statistics
    stats: dict[str, Any] = Field(
        default_factory=dict, description="Summary statistics"
    )

    # Actionable Items
    action_items: list[ActionItem] = Field(
        default_factory=list, description="Priority clinical actions"
    )


# ==============================================================================
# Biller Dashboard
# ==============================================================================


class ICD10SuggestionSummary(BaseModel):
    """Summary of an ICD-10 code suggestion."""

    code: str
    description: str
    confidence: str  # high, medium, low
    cer_citation: CERCitationSummary | None = None


class CPTSuggestionSummary(BaseModel):
    """Summary of a CPT code suggestion."""

    code: str
    description: str
    category: str
    confidence: str
    rvu_value: float | None = None


class BillingFindingSummary(BaseModel):
    """Summary of a billing optimization finding."""

    category: str  # upcoding_opportunity, missed_service, bundling_issue, etc.
    severity: str
    title: str
    current_code: str | None = None
    recommended_code: str | None = None
    revenue_impact: float
    cer_citation: CERCitationSummary | None = None


class HCCOpportunitySummary(BaseModel):
    """Summary of an HCC revenue opportunity."""

    hcc_code: str
    description: str
    gap_type: str
    confidence: str
    estimated_revenue: float
    recommended_icd10: str | None = None


class CDIQuerySummary(BaseModel):
    """Summary of a CDI query."""

    query_id: str
    priority: str
    question: str
    gap_category: str
    estimated_impact: float


class BillerDashboardResponse(BaseModel):
    """Response for GET /dashboard/biller."""

    metadata: DashboardMetadata

    # ICD-10 Suggestions
    icd10_suggestions: list[ICD10SuggestionSummary] = Field(
        default_factory=list, description="ICD-10 code suggestions with CER"
    )

    # CPT Suggestions
    cpt_suggestions: list[CPTSuggestionSummary] = Field(
        default_factory=list, description="CPT code suggestions"
    )

    # Billing Optimization
    billing_findings: list[BillingFindingSummary] = Field(
        default_factory=list, description="Billing optimization findings"
    )

    # HCC Opportunities
    hcc_opportunities: list[HCCOpportunitySummary] = Field(
        default_factory=list, description="HCC revenue opportunities"
    )

    # CDI Queries
    cdi_queries: list[CDIQuerySummary] = Field(
        default_factory=list, description="Clinical documentation queries"
    )

    # Revenue Summary
    revenue_summary: dict[str, Any] = Field(
        default_factory=dict, description="Revenue opportunity summary"
    )

    # Actionable Items
    action_items: list[ActionItem] = Field(
        default_factory=list, description="Priority billing actions"
    )


# ==============================================================================
# Quality Dashboard
# ==============================================================================


class ProcessingMetricsSummary(BaseModel):
    """Summary of NLP processing metrics."""

    documents_processed: int
    avg_processing_time_ms: float
    total_extractions: int
    avg_confidence: float
    error_rate: float


class AccuracySummary(BaseModel):
    """Summary of extraction accuracy."""

    entity_type: str
    precision: float
    recall: float
    f1_score: float
    sample_count: int


class EntityDistribution(BaseModel):
    """Distribution of extracted entities."""

    conditions: int = 0
    drugs: int = 0
    measurements: int = 0
    procedures: int = 0
    observations: int = 0


class ErrorSummary(BaseModel):
    """Summary of processing errors."""

    error_type: str
    count: int
    percentage: float


class QualityDashboardResponse(BaseModel):
    """Response for GET /dashboard/quality."""

    metadata: DashboardMetadata

    # Processing Metrics
    processing_metrics: ProcessingMetricsSummary = Field(
        ..., description="NLP processing statistics"
    )

    # Accuracy Metrics
    accuracy_by_entity: list[AccuracySummary] = Field(
        default_factory=list, description="Accuracy metrics by entity type"
    )

    # Entity Distribution
    entity_distribution: EntityDistribution = Field(
        default_factory=EntityDistribution, description="Distribution of extracted entities"
    )

    # Confidence Distribution
    confidence_distribution: dict[str, int] = Field(
        default_factory=dict, description="Confidence score buckets"
    )

    # Error Summary
    top_errors: list[ErrorSummary] = Field(
        default_factory=list, description="Most common errors"
    )

    # Trend Data (for charts)
    processing_trend: list[dict[str, Any]] = Field(
        default_factory=list, description="Processing time trend data"
    )

    # Action Items
    action_items: list[ActionItem] = Field(
        default_factory=list, description="Quality improvement actions"
    )


# ==============================================================================
# Admin Dashboard
# ==============================================================================


class ServiceHealthSummary(BaseModel):
    """Health summary for a service."""

    service_name: str
    status: str  # healthy, degraded, unhealthy
    stats: dict[str, Any] = Field(default_factory=dict)


class SystemStatsSummary(BaseModel):
    """System-wide statistics."""

    total_patients: int = 0
    total_documents: int = 0
    total_extractions: int = 0
    documents_today: int = 0
    documents_this_week: int = 0


class AdminDashboardResponse(BaseModel):
    """Response for GET /dashboard/admin."""

    metadata: DashboardMetadata

    # System Stats
    system_stats: SystemStatsSummary = Field(
        default_factory=SystemStatsSummary, description="System-wide statistics"
    )

    # Service Health (all services)
    service_health: list[ServiceHealthSummary] = Field(
        default_factory=list, description="Health status of all services"
    )

    # Include summaries from other dashboards
    provider_summary: dict[str, Any] = Field(
        default_factory=dict, description="Provider dashboard summary"
    )

    biller_summary: dict[str, Any] = Field(
        default_factory=dict, description="Biller dashboard summary"
    )

    quality_summary: dict[str, Any] = Field(
        default_factory=dict, description="Quality dashboard summary"
    )

    # Action Items (aggregated from all roles)
    all_action_items: list[ActionItem] = Field(
        default_factory=list, description="All priority actions"
    )
