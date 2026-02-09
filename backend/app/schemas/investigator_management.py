"""Pydantic schemas for Investigator Performance Management (CMO-11).

Tracks investigator qualifications, certifications, performance scorecards,
inspection records, training compliance, and workload capacity for
multi-site clinical trial operations.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class InvestigatorRole(str, Enum):
    """Role an investigator holds within a clinical trial."""

    PRINCIPAL_INVESTIGATOR = "principal_investigator"
    SUB_INVESTIGATOR = "sub_investigator"
    CO_INVESTIGATOR = "co_investigator"
    STUDY_COORDINATOR = "study_coordinator"


class CertificationType(str, Enum):
    """Types of certifications required for clinical trial investigators."""

    GCP_TRAINING = "gcp_training"
    IATA_DANGEROUS_GOODS = "iata_dangerous_goods"
    HUMAN_SUBJECTS_PROTECTION = "human_subjects_protection"
    CV_UPDATED = "cv_updated"
    MEDICAL_LICENSE = "medical_license"
    DEA_LICENSE = "dea_license"
    PROTOCOL_TRAINING = "protocol_training"
    IRB_APPROVAL = "irb_approval"


class PerformanceRating(str, Enum):
    """Overall performance rating for investigator scorecards."""

    EXCEPTIONAL = "exceptional"
    ABOVE_AVERAGE = "above_average"
    AVERAGE = "average"
    BELOW_AVERAGE = "below_average"
    UNACCEPTABLE = "unacceptable"


class InspectionResult(str, Enum):
    """Outcome classification from a regulatory inspection."""

    NO_FINDINGS = "no_findings"
    MINOR_FINDINGS = "minor_findings"
    MAJOR_FINDINGS = "major_findings"
    OFFICIAL_ACTION_INDICATED = "official_action_indicated"
    CRITICAL = "critical"


class TrainingStatus(str, Enum):
    """Status of a training record."""

    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    OVERDUE = "overdue"
    NOT_STARTED = "not_started"
    EXPIRED = "expired"


# ---------------------------------------------------------------------------
# Core investigator record
# ---------------------------------------------------------------------------

class Investigator(BaseModel):
    """A clinical trial investigator with qualifications and metrics."""

    id: str = Field(..., description="Unique investigator identifier")
    name: str = Field(..., description="Full name of the investigator")
    role: InvestigatorRole = Field(..., description="Role within the trial")
    site_id: str = Field(..., description="Associated site identifier")
    site_name: str = Field(..., description="Associated site display name")
    email: str = Field(..., description="Contact email address")
    specialty: str = Field(..., description="Medical specialty")
    medical_license_number: str | None = Field(None, description="Medical license number")
    npi_number: str | None = Field(None, description="National Provider Identifier")
    years_experience: int = Field(0, ge=0, description="Years of clinical trial experience")
    trials_conducted: int = Field(0, ge=0, description="Total trials conducted historically")
    active_trials: int = Field(0, ge=0, description="Number of currently active trials")
    certifications: list[str] = Field(default_factory=list, description="List of certification type names held")
    performance_score: float | None = Field(None, ge=0.0, le=100.0, description="Current overall performance score")
    last_performance_review: str | None = Field(None, description="ISO date of last performance review")
    created_at: str = Field(..., description="ISO datetime when the record was created")
    updated_at: str | None = Field(None, description="ISO datetime of last update")


# ---------------------------------------------------------------------------
# Certification
# ---------------------------------------------------------------------------

class InvestigatorCertification(BaseModel):
    """A certification held by an investigator."""

    id: str = Field(..., description="Unique certification record identifier")
    investigator_id: str = Field(..., description="Associated investigator identifier")
    certification_type: CertificationType = Field(..., description="Type of certification")
    issued_date: str = Field(..., description="ISO date when issued")
    expiry_date: str | None = Field(None, description="ISO date of expiry")
    status: TrainingStatus = Field(..., description="Current certification status")
    issuing_authority: str = Field(..., description="Organization that issued the certification")
    certificate_number: str | None = Field(None, description="Unique certificate number")


# ---------------------------------------------------------------------------
# Performance scorecard
# ---------------------------------------------------------------------------

class InvestigatorScorecard(BaseModel):
    """Quarterly performance scorecard for an investigator."""

    id: str = Field(..., description="Unique scorecard identifier")
    investigator_id: str = Field(..., description="Associated investigator identifier")
    period_start: str = Field(..., description="ISO date of evaluation period start")
    period_end: str = Field(..., description="ISO date of evaluation period end")
    enrollment_target: int = Field(0, ge=0, description="Target enrollment for the period")
    enrollment_actual: int = Field(0, ge=0, description="Actual enrollment achieved")
    enrollment_rate: float = Field(0.0, ge=0.0, description="Enrollment rate (actual / target)")
    screen_failure_rate: float = Field(0.0, ge=0.0, le=1.0, description="Rate of screen failures")
    protocol_deviation_count: int = Field(0, ge=0, description="Protocol deviations during period")
    query_response_time_days: float = Field(0.0, ge=0.0, description="Average query response time in days")
    data_quality_score: float = Field(0.0, ge=0.0, le=100.0, description="Data quality score out of 100")
    patient_retention_rate: float = Field(0.0, ge=0.0, le=1.0, description="Patient retention rate")
    ae_reporting_timeliness: float = Field(0.0, ge=0.0, le=100.0, description="AE reporting timeliness score")
    overall_rating: PerformanceRating = Field(..., description="Overall rating for the period")
    strengths: list[str] = Field(default_factory=list, description="Identified strengths")
    improvement_areas: list[str] = Field(default_factory=list, description="Areas for improvement")


# ---------------------------------------------------------------------------
# Inspection record
# ---------------------------------------------------------------------------

class InspectionRecord(BaseModel):
    """Record of a regulatory inspection at an investigator site."""

    id: str = Field(..., description="Unique inspection record identifier")
    investigator_id: str = Field(..., description="Associated investigator identifier")
    site_id: str = Field(..., description="Associated site identifier")
    inspection_date: str = Field(..., description="ISO date of inspection")
    inspector_name: str = Field(..., description="Name of the inspector")
    inspection_type: str = Field(..., description="Type of inspection (e.g. routine, for-cause)")
    result: InspectionResult = Field(..., description="Inspection outcome")
    findings: list[str] = Field(default_factory=list, description="List of findings")
    corrective_actions: list[str] = Field(default_factory=list, description="Required corrective actions")
    follow_up_date: str | None = Field(None, description="ISO date of scheduled follow-up")


# ---------------------------------------------------------------------------
# Training record
# ---------------------------------------------------------------------------

class TrainingRecord(BaseModel):
    """A training record for an investigator."""

    id: str = Field(..., description="Unique training record identifier")
    investigator_id: str = Field(..., description="Associated investigator identifier")
    training_name: str = Field(..., description="Name of the training course")
    training_type: CertificationType = Field(..., description="Type of training")
    required_by: str = Field(..., description="ISO date by which training is required")
    completed_date: str | None = Field(None, description="ISO date when training was completed")
    status: TrainingStatus = Field(..., description="Current status of the training")
    valid_until: str | None = Field(None, description="ISO date until which training is valid")


# ---------------------------------------------------------------------------
# Workload analysis
# ---------------------------------------------------------------------------

class InvestigatorWorkload(BaseModel):
    """Workload and capacity metrics for an investigator."""

    investigator_id: str = Field(..., description="Investigator identifier")
    investigator_name: str = Field(..., description="Investigator display name")
    active_trial_count: int = Field(0, ge=0, description="Number of active trials")
    total_patients: int = Field(0, ge=0, description="Total patients across all trials")
    enrollment_capacity: int = Field(0, ge=0, description="Maximum enrollment capacity")
    utilization_percent: float = Field(0.0, ge=0.0, le=100.0, description="Capacity utilization percentage")


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class InvestigatorCreateRequest(BaseModel):
    """Request to create a new investigator record."""

    name: str = Field(..., description="Full name of the investigator")
    role: InvestigatorRole = Field(..., description="Role within the trial")
    site_id: str = Field(..., description="Associated site identifier")
    site_name: str = Field(..., description="Associated site display name")
    email: str = Field(..., description="Contact email address")
    specialty: str = Field(..., description="Medical specialty")
    medical_license_number: str | None = Field(None, description="Medical license number")
    npi_number: str | None = Field(None, description="National Provider Identifier")
    years_experience: int = Field(0, ge=0, description="Years of clinical trial experience")
    trials_conducted: int = Field(0, ge=0, description="Total trials conducted historically")
    active_trials: int = Field(0, ge=0, description="Number of currently active trials")


class ScorecardCreateRequest(BaseModel):
    """Request to create a new performance scorecard."""

    investigator_id: str = Field(..., description="Associated investigator identifier")
    period_start: str = Field(..., description="ISO date of evaluation period start")
    period_end: str = Field(..., description="ISO date of evaluation period end")
    enrollment_target: int = Field(0, ge=0, description="Target enrollment for the period")
    enrollment_actual: int = Field(0, ge=0, description="Actual enrollment achieved")
    screen_failure_rate: float = Field(0.0, ge=0.0, le=1.0, description="Rate of screen failures")
    protocol_deviation_count: int = Field(0, ge=0, description="Protocol deviations during period")
    query_response_time_days: float = Field(0.0, ge=0.0, description="Average query response time in days")
    data_quality_score: float = Field(0.0, ge=0.0, le=100.0, description="Data quality score out of 100")
    patient_retention_rate: float = Field(0.0, ge=0.0, le=1.0, description="Patient retention rate")
    ae_reporting_timeliness: float = Field(0.0, ge=0.0, le=100.0, description="AE reporting timeliness score")


class InspectionCreateRequest(BaseModel):
    """Request to create a new inspection record."""

    investigator_id: str = Field(..., description="Associated investigator identifier")
    site_id: str = Field(..., description="Associated site identifier")
    inspection_date: str = Field(..., description="ISO date of inspection")
    inspector_name: str = Field(..., description="Name of the inspector")
    inspection_type: str = Field("routine", description="Type of inspection")
    result: InspectionResult = Field(..., description="Inspection outcome")
    findings: list[str] = Field(default_factory=list, description="List of findings")
    corrective_actions: list[str] = Field(default_factory=list, description="Required corrective actions")
    follow_up_date: str | None = Field(None, description="ISO date of scheduled follow-up")


class TrainingCreateRequest(BaseModel):
    """Request to create a new training record."""

    investigator_id: str = Field(..., description="Associated investigator identifier")
    training_name: str = Field(..., description="Name of the training course")
    training_type: CertificationType = Field(..., description="Type of training")
    required_by: str = Field(..., description="ISO date by which training is required")
    completed_date: str | None = Field(None, description="ISO date when completed")
    status: TrainingStatus = Field(TrainingStatus.NOT_STARTED, description="Current status")
    valid_until: str | None = Field(None, description="ISO date until which training is valid")


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class InvestigatorListResponse(BaseModel):
    """Paginated list of investigators."""

    investigators: list[Investigator] = Field(default_factory=list)
    total: int = Field(ge=0)


class ScorecardListResponse(BaseModel):
    """List of performance scorecards."""

    scorecards: list[InvestigatorScorecard] = Field(default_factory=list)
    total: int = Field(ge=0)


# ---------------------------------------------------------------------------
# Metrics and reports
# ---------------------------------------------------------------------------

class InvestigatorMetrics(BaseModel):
    """Aggregate investigator performance metrics."""

    total_investigators: int = Field(ge=0, description="Total number of investigators")
    by_role: dict[str, int] = Field(default_factory=dict, description="Count by role")
    avg_performance_score: float = Field(0.0, ge=0.0, description="Average performance score across all investigators")
    avg_years_experience: float = Field(0.0, ge=0.0, description="Average years of experience")
    certification_compliance_rate: float = Field(
        0.0, ge=0.0, le=100.0, description="Percentage of investigators with all certs current",
    )
    training_completion_rate: float = Field(
        0.0, ge=0.0, le=100.0, description="Percentage of training records marked completed",
    )
    inspection_readiness_score: float = Field(
        0.0, ge=0.0, le=100.0, description="Overall inspection readiness score",
    )
    active_trial_avg: float = Field(0.0, ge=0.0, description="Average active trials per investigator")


class CertificationExpiryAlert(BaseModel):
    """Alert for a certification approaching expiry."""

    investigator_id: str = Field(..., description="Investigator identifier")
    investigator_name: str = Field(..., description="Investigator name")
    certification_type: CertificationType = Field(..., description="Type of certification")
    expiry_date: str = Field(..., description="ISO date of expiry")
    days_until_expiry: int = Field(..., description="Days until expiry (negative = expired)")
    severity: str = Field(..., description="Severity: critical, warning, info")


class CertificationExpiryReport(BaseModel):
    """Report of upcoming and expired certifications."""

    alerts: list[CertificationExpiryAlert] = Field(default_factory=list)
    total_expiring_30_days: int = Field(0, ge=0, description="Certs expiring within 30 days")
    total_expiring_60_days: int = Field(0, ge=0, description="Certs expiring within 60 days")
    total_expiring_90_days: int = Field(0, ge=0, description="Certs expiring within 90 days")
    total_expired: int = Field(0, ge=0, description="Currently expired certs")


class WorkloadReport(BaseModel):
    """Workload analysis across all investigators."""

    workloads: list[InvestigatorWorkload] = Field(default_factory=list)
    avg_utilization: float = Field(0.0, ge=0.0, le=100.0, description="Average utilization percent")
    overloaded_count: int = Field(0, ge=0, description="Number of investigators above 90% utilization")
    available_count: int = Field(0, ge=0, description="Number of investigators below 50% utilization")


class TrainingGapAnalysis(BaseModel):
    """Training gap analysis for an investigator."""

    investigator_id: str = Field(..., description="Investigator identifier")
    investigator_name: str = Field(..., description="Investigator name")
    completed_count: int = Field(0, ge=0, description="Number of completed trainings")
    overdue_count: int = Field(0, ge=0, description="Number of overdue trainings")
    in_progress_count: int = Field(0, ge=0, description="Number of in-progress trainings")
    not_started_count: int = Field(0, ge=0, description="Number of not-started trainings")
    expired_count: int = Field(0, ge=0, description="Number of expired trainings")
    compliance_rate: float = Field(0.0, ge=0.0, le=100.0, description="Training compliance rate")
    gaps: list[str] = Field(default_factory=list, description="List of training gaps identified")


class PerformanceRanking(BaseModel):
    """Performance ranking entry for an investigator."""

    rank: int = Field(..., ge=1, description="Rank position")
    investigator_id: str = Field(..., description="Investigator identifier")
    investigator_name: str = Field(..., description="Investigator name")
    role: InvestigatorRole = Field(..., description="Investigator role")
    site_name: str = Field(..., description="Site name")
    performance_score: float = Field(0.0, ge=0.0, le=100.0, description="Overall performance score")
    enrollment_rate: float = Field(0.0, ge=0.0, description="Enrollment rate")
    data_quality_score: float = Field(0.0, ge=0.0, le=100.0, description="Data quality score")


class PerformanceRankingResponse(BaseModel):
    """Ranked list of investigators by performance."""

    rankings: list[PerformanceRanking] = Field(default_factory=list)
    total: int = Field(ge=0)


class InvestigatorMatchResult(BaseModel):
    """Result of investigator matching for new trial assignment."""

    investigator_id: str = Field(..., description="Investigator identifier")
    investigator_name: str = Field(..., description="Investigator name")
    role: InvestigatorRole = Field(..., description="Role")
    site_name: str = Field(..., description="Site name")
    available_capacity: int = Field(0, ge=0, description="Available enrollment capacity")
    performance_score: float = Field(0.0, ge=0.0, le=100.0, description="Performance score")
    match_score: float = Field(0.0, ge=0.0, le=100.0, description="Overall match score combining factors")
    certifications_valid: bool = Field(True, description="Whether all required certifications are current")
