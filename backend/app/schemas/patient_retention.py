"""Pydantic schemas for Patient Retention Analytics (CMO-12).

Pharma-grade patient retention analytics system that tracks patient dropout
risk, generates Kaplan-Meier retention curves, manages retention interventions,
and provides site-level retention comparisons for clinical trials.
"""

from __future__ import annotations

from datetime import date as DateType
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RetentionRiskLevel(str, Enum):
    """Patient retention risk classification."""

    VERY_HIGH = "VERY_HIGH"
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    MINIMAL = "MINIMAL"


class DropoutReason(str, Enum):
    """Reason a patient dropped out of a clinical trial."""

    ADVERSE_EVENT = "ADVERSE_EVENT"
    LACK_OF_EFFICACY = "LACK_OF_EFFICACY"
    PROTOCOL_BURDEN = "PROTOCOL_BURDEN"
    TRAVEL_DISTANCE = "TRAVEL_DISTANCE"
    LOST_TO_FOLLOWUP = "LOST_TO_FOLLOWUP"
    WITHDRAWAL_CONSENT = "WITHDRAWAL_CONSENT"
    PHYSICIAN_DECISION = "PHYSICIAN_DECISION"
    COMPETING_TRIAL = "COMPETING_TRIAL"
    INSURANCE_CHANGE = "INSURANCE_CHANGE"
    RELOCATION = "RELOCATION"
    OTHER = "OTHER"


class InterventionType(str, Enum):
    """Type of retention intervention applied to a patient."""

    PHONE_CALL = "PHONE_CALL"
    HOME_VISIT = "HOME_VISIT"
    TRANSPORTATION_ASSISTANCE = "TRANSPORTATION_ASSISTANCE"
    SCHEDULE_FLEXIBILITY = "SCHEDULE_FLEXIBILITY"
    FINANCIAL_SUPPORT = "FINANCIAL_SUPPORT"
    CAREGIVER_SUPPORT = "CAREGIVER_SUPPORT"
    TELEHEALTH_OPTION = "TELEHEALTH_OPTION"
    REMINDER_SYSTEM = "REMINDER_SYSTEM"
    PATIENT_EDUCATION = "PATIENT_EDUCATION"
    GIFT_CARD = "GIFT_CARD"


class PatientPhase(str, Enum):
    """Current phase of a patient in a clinical trial."""

    SCREENING = "SCREENING"
    ENROLLED = "ENROLLED"
    ACTIVE_TREATMENT = "ACTIVE_TREATMENT"
    FOLLOW_UP = "FOLLOW_UP"
    COMPLETED = "COMPLETED"
    DROPPED_OUT = "DROPPED_OUT"


class RetentionMetricType(str, Enum):
    """Scope of retention metric aggregation."""

    OVERALL = "OVERALL"
    BY_SITE = "BY_SITE"
    BY_TRIAL = "BY_TRIAL"
    BY_PHASE = "BY_PHASE"
    BY_DEMOGRAPHICS = "BY_DEMOGRAPHICS"


# ---------------------------------------------------------------------------
# Core data models
# ---------------------------------------------------------------------------


class RetentionRiskFactor(BaseModel):
    """A single risk factor contributing to patient dropout risk."""

    model_config = ConfigDict(from_attributes=True)

    factor_name: str = Field(..., description="Name of the risk factor")
    weight: float = Field(..., ge=0, le=1.0, description="Weight of this factor in the scoring model")
    score: float = Field(..., ge=0, le=100.0, description="Score for this factor (0-100)")
    description: str = Field("", description="Human-readable description of the risk factor")


class RetentionIntervention(BaseModel):
    """A retention intervention applied to a patient."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique intervention identifier")
    patient_id: str = Field(..., description="Patient identifier")
    intervention_type: InterventionType = Field(..., description="Type of intervention")
    applied_date: DateType = Field(..., description="Date intervention was applied")
    applied_by: str = Field("", description="Name of person who applied the intervention")
    outcome: Optional[str] = Field(None, description="Outcome of the intervention")
    notes: str = Field("", description="Additional notes about the intervention")
    cost: float = Field(0.0, ge=0, description="Cost of the intervention in USD")


class PatientRetentionProfile(BaseModel):
    """Retention profile for a single patient in a clinical trial."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique profile identifier")
    patient_id: str = Field(..., description="Patient identifier")
    trial_id: str = Field(..., description="Trial identifier")
    site_id: str = Field(..., description="Site identifier")
    phase: PatientPhase = Field(..., description="Current patient phase")
    enrolled_date: DateType = Field(..., description="Date patient was enrolled")
    last_visit_date: Optional[DateType] = Field(None, description="Date of last visit")
    next_visit_date: Optional[DateType] = Field(None, description="Date of next scheduled visit")
    visits_completed: int = Field(0, ge=0, description="Number of visits completed")
    visits_scheduled: int = Field(0, ge=0, description="Total number of visits scheduled")
    missed_visits: int = Field(0, ge=0, description="Number of missed visits")
    risk_level: RetentionRiskLevel = Field(RetentionRiskLevel.MINIMAL, description="Current risk level")
    risk_score: float = Field(0.0, ge=0, le=100.0, description="Composite risk score (0-100)")
    risk_factors: list[RetentionRiskFactor] = Field(default_factory=list, description="Individual risk factors")
    interventions_applied: list[str] = Field(default_factory=list, description="IDs of interventions applied")
    dropped_out: bool = Field(False, description="Whether the patient has dropped out")
    dropout_date: Optional[DateType] = Field(None, description="Date of dropout if applicable")
    dropout_reason: Optional[DropoutReason] = Field(None, description="Reason for dropout if applicable")


class DropoutPrediction(BaseModel):
    """Predicted dropout risk for a patient."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str = Field(..., description="Patient identifier")
    risk_score: float = Field(..., ge=0, le=100.0, description="Predicted dropout risk score (0-100)")
    risk_level: RetentionRiskLevel = Field(..., description="Predicted risk level")
    top_risk_factors: list[RetentionRiskFactor] = Field(default_factory=list, description="Top contributing risk factors")
    recommended_interventions: list[InterventionType] = Field(default_factory=list, description="Recommended interventions")
    prediction_confidence: float = Field(..., ge=0, le=1.0, description="Confidence in the prediction (0-1)")
    prediction_date: DateType = Field(..., description="Date of prediction")


class RetentionCurvePoint(BaseModel):
    """A single point on a retention survival curve."""

    model_config = ConfigDict(from_attributes=True)

    day: int = Field(..., ge=0, description="Day since enrollment")
    patients_at_risk: int = Field(..., ge=0, description="Number of patients at risk at this time point")
    events: int = Field(0, ge=0, description="Number of dropout events at this time point")
    censored: int = Field(0, ge=0, description="Number of censored observations at this time point")
    survival_probability: float = Field(..., ge=0, le=1.0, description="Kaplan-Meier survival probability")


class RetentionCurve(BaseModel):
    """Kaplan-Meier retention survival curve for a trial."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    data_points: list[RetentionCurvePoint] = Field(default_factory=list, description="Survival curve data points")
    kaplan_meier_estimate: float = Field(..., ge=0, le=1.0, description="Current Kaplan-Meier survival estimate")
    median_retention_days: Optional[int] = Field(None, ge=0, description="Median retention time in days")
    retention_at_30d: Optional[float] = Field(None, ge=0, le=1.0, description="Retention probability at 30 days")
    retention_at_90d: Optional[float] = Field(None, ge=0, le=1.0, description="Retention probability at 90 days")
    retention_at_180d: Optional[float] = Field(None, ge=0, le=1.0, description="Retention probability at 180 days")
    retention_at_365d: Optional[float] = Field(None, ge=0, le=1.0, description="Retention probability at 365 days")


class SiteRetentionComparison(BaseModel):
    """Retention performance comparison for a single site."""

    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., description="Site identifier")
    site_name: str = Field(..., description="Human-readable site name")
    retention_rate: float = Field(..., ge=0, le=1.0, description="Overall retention rate at site")
    dropout_rate: float = Field(..., ge=0, le=1.0, description="Overall dropout rate at site")
    avg_days_retained: float = Field(..., ge=0, description="Average days patients retained at site")
    intervention_count: int = Field(0, ge=0, description="Number of interventions applied at site")
    cost_per_retained: float = Field(0.0, ge=0, description="Cost per retained patient in USD")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ProfileCreateRequest(BaseModel):
    """Request to create a new patient retention profile."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str = Field(..., min_length=1, description="Patient identifier")
    trial_id: str = Field(..., min_length=1, description="Trial identifier")
    site_id: str = Field(..., min_length=1, description="Site identifier")
    phase: PatientPhase = Field(PatientPhase.ENROLLED, description="Initial patient phase")
    enrolled_date: DateType = Field(..., description="Date patient was enrolled")
    visits_scheduled: int = Field(0, ge=0, description="Total visits scheduled")


class ProfileUpdateRequest(BaseModel):
    """Request to update a patient retention profile."""

    model_config = ConfigDict(from_attributes=True)

    phase: Optional[PatientPhase] = Field(None, description="Updated patient phase")
    last_visit_date: Optional[DateType] = Field(None, description="Updated last visit date")
    next_visit_date: Optional[DateType] = Field(None, description="Updated next visit date")
    visits_completed: Optional[int] = Field(None, ge=0, description="Updated visits completed")
    missed_visits: Optional[int] = Field(None, ge=0, description="Updated missed visits")
    dropped_out: Optional[bool] = Field(None, description="Whether the patient dropped out")
    dropout_date: Optional[DateType] = Field(None, description="Date of dropout")
    dropout_reason: Optional[DropoutReason] = Field(None, description="Reason for dropout")


class InterventionCreateRequest(BaseModel):
    """Request to create a new retention intervention."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str = Field(..., min_length=1, description="Patient identifier")
    intervention_type: InterventionType = Field(..., description="Type of intervention")
    applied_by: str = Field("", description="Person applying the intervention")
    notes: str = Field("", description="Additional notes")
    cost: float = Field(0.0, ge=0, description="Cost of intervention in USD")


class InterventionUpdateRequest(BaseModel):
    """Request to update an intervention outcome."""

    model_config = ConfigDict(from_attributes=True)

    outcome: Optional[str] = Field(None, description="Outcome of the intervention")
    notes: Optional[str] = Field(None, description="Updated notes")


class ProfileListResponse(BaseModel):
    """Response containing a list of patient retention profiles."""

    model_config = ConfigDict(from_attributes=True)

    items: list[PatientRetentionProfile] = Field(..., description="List of profiles")
    total: int = Field(..., ge=0, description="Total number of profiles")


class InterventionListResponse(BaseModel):
    """Response containing a list of retention interventions."""

    model_config = ConfigDict(from_attributes=True)

    items: list[RetentionIntervention] = Field(..., description="List of interventions")
    total: int = Field(..., ge=0, description="Total number of interventions")


class CohortAnalysis(BaseModel):
    """Cohort analysis results for retention segmentation."""

    model_config = ConfigDict(from_attributes=True)

    cohort_name: str = Field(..., description="Name of the cohort")
    cohort_size: int = Field(..., ge=0, description="Number of patients in cohort")
    retention_rate: float = Field(..., ge=0, le=1.0, description="Retention rate for the cohort")
    dropout_rate: float = Field(..., ge=0, le=1.0, description="Dropout rate for the cohort")
    avg_risk_score: float = Field(..., ge=0, le=100.0, description="Average risk score for the cohort")
    avg_days_retained: float = Field(..., ge=0, description="Average days retained for the cohort")
    intervention_count: int = Field(0, ge=0, description="Total interventions applied to cohort")


class InterventionEffectiveness(BaseModel):
    """Effectiveness analysis for a specific intervention type."""

    model_config = ConfigDict(from_attributes=True)

    intervention_type: InterventionType = Field(..., description="Type of intervention")
    total_applied: int = Field(..., ge=0, description="Number of times applied")
    successful_outcomes: int = Field(0, ge=0, description="Number of successful outcomes")
    success_rate: float = Field(0.0, ge=0, le=1.0, description="Success rate")
    avg_cost: float = Field(0.0, ge=0, description="Average cost per intervention")
    total_cost: float = Field(0.0, ge=0, description="Total cost of this intervention type")
    retained_after: int = Field(0, ge=0, description="Patients retained after receiving this intervention")
    dropped_after: int = Field(0, ge=0, description="Patients who dropped out after receiving this intervention")


class RetentionMetrics(BaseModel):
    """Aggregate retention metrics across trials."""

    model_config = ConfigDict(from_attributes=True)

    total_patients: int = Field(..., ge=0, description="Total patients tracked")
    active_patients: int = Field(..., ge=0, description="Currently active patients")
    dropped_out_patients: int = Field(..., ge=0, description="Total patients who dropped out")
    completed_patients: int = Field(..., ge=0, description="Patients who completed the trial")
    overall_retention_rate: float = Field(..., ge=0, le=1.0, description="Overall retention rate")
    overall_dropout_rate: float = Field(..., ge=0, le=1.0, description="Overall dropout rate")
    avg_risk_score: float = Field(..., ge=0, le=100.0, description="Average risk score across patients")
    high_risk_count: int = Field(0, ge=0, description="Number of patients at HIGH or VERY_HIGH risk")
    total_interventions: int = Field(0, ge=0, description="Total interventions applied")
    total_intervention_cost: float = Field(0.0, ge=0, description="Total cost of all interventions")
    cost_per_retained_patient: float = Field(0.0, ge=0, description="Average cost per retained patient")
    avg_days_retained: float = Field(0.0, ge=0, description="Average days retained across all patients")


class RetentionDashboard(BaseModel):
    """Comprehensive retention dashboard with all analytics."""

    model_config = ConfigDict(from_attributes=True)

    metrics: RetentionMetrics = Field(..., description="Aggregate retention metrics")
    risk_distribution: dict[str, int] = Field(default_factory=dict, description="Count of patients by risk level")
    phase_distribution: dict[str, int] = Field(default_factory=dict, description="Count of patients by phase")
    dropout_reasons: dict[str, int] = Field(default_factory=dict, description="Count of dropouts by reason")
    site_comparisons: list[SiteRetentionComparison] = Field(default_factory=list, description="Site-level comparisons")
    top_risk_patients: list[PatientRetentionProfile] = Field(default_factory=list, description="Top at-risk patients")
    intervention_effectiveness: list[InterventionEffectiveness] = Field(
        default_factory=list, description="Effectiveness of each intervention type"
    )
    retention_curves: list[RetentionCurve] = Field(default_factory=list, description="Retention curves per trial")
