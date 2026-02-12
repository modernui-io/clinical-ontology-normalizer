"""Pydantic schemas for Product Complaint Management (PROD-COMPL).

Manages product complaint operations: complaint intake, investigation
tracking, root cause analysis, CAPA linkage, and regulatory reporting
with complaint metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ComplaintCategory(str, Enum):
    PRODUCT_QUALITY = "product_quality"
    PACKAGING = "packaging"
    LABELING = "labeling"
    ADVERSE_EVENT = "adverse_event"
    DEVICE_MALFUNCTION = "device_malfunction"
    COUNTERFEIT = "counterfeit"


class ComplaintSeverity(str, Enum):
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CRITICAL = "critical"
    LIFE_THREATENING = "life_threatening"


class ComplaintStatus(str, Enum):
    RECEIVED = "received"
    ACKNOWLEDGED = "acknowledged"
    UNDER_INVESTIGATION = "under_investigation"
    ROOT_CAUSE_IDENTIFIED = "root_cause_identified"
    RESOLVED = "resolved"
    CLOSED = "closed"


class InvestigationOutcome(str, Enum):
    CONFIRMED = "confirmed"
    NOT_CONFIRMED = "not_confirmed"
    INCONCLUSIVE = "inconclusive"
    DUPLICATE = "duplicate"
    EXPECTED_BEHAVIOR = "expected_behavior"


class RootCauseCategory(str, Enum):
    MANUFACTURING = "manufacturing"
    RAW_MATERIAL = "raw_material"
    STORAGE = "storage"
    TRANSPORTATION = "transportation"
    DESIGN = "design"
    HUMAN_ERROR = "human_error"


class ComplaintIntake(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    complaint_number: str
    category: ComplaintCategory
    severity: ComplaintSeverity = ComplaintSeverity.MINOR
    status: ComplaintStatus = ComplaintStatus.RECEIVED
    product_name: str
    batch_number: str | None = None
    complaint_date: datetime
    reporter_name: str
    reporter_type: str = "investigator"
    site_id: str | None = None
    subject_id: str | None = None
    description: str
    patient_impact: bool = False
    sample_available: bool = False
    sample_received: bool = False
    initial_assessment: str | None = None
    days_open: int = Field(ge=0, default=0)
    received_by: str
    notes: str | None = None
    created_at: datetime


class InvestigationRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    complaint_id: str
    investigation_start_date: datetime
    investigation_end_date: datetime | None = None
    investigator: str
    outcome: InvestigationOutcome | None = None
    testing_performed: list[str] = Field(default_factory=list)
    test_results_summary: str | None = None
    manufacturing_review: bool = False
    distribution_review: bool = False
    trend_analysis_performed: bool = False
    similar_complaints_found: int = Field(ge=0, default=0)
    product_retained: bool = False
    field_alert_considered: bool = False
    recall_considered: bool = False
    reviewed_by: str | None = None
    notes: str | None = None
    created_at: datetime


class RootCauseAnalysis(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    complaint_id: str
    investigation_id: str | None = None
    root_cause_category: RootCauseCategory
    root_cause_description: str
    analysis_method: str = "fishbone"
    contributing_factors: list[str] = Field(default_factory=list)
    evidence_supporting: list[str] = Field(default_factory=list)
    probability_of_recurrence: str = "low"
    impact_scope: str = "isolated"
    identified_by: str
    analysis_date: datetime
    verified: bool = False
    verified_by: str | None = None
    notes: str | None = None
    created_at: datetime


class CAPALinkage(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    complaint_id: str
    root_cause_id: str | None = None
    capa_type: str = "corrective"
    capa_number: str
    description: str
    assigned_to: str
    due_date: datetime
    completed_date: datetime | None = None
    status: str = "open"
    effectiveness_check_required: bool = True
    effectiveness_check_date: datetime | None = None
    effectiveness_confirmed: bool = False
    preventive_measures: list[str] = Field(default_factory=list)
    created_by: str
    approved_by: str | None = None
    notes: str | None = None
    created_at: datetime


class RegulatoryReport(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    complaint_id: str
    report_type: str = "field_alert"
    regulatory_authority: str
    report_number: str | None = None
    submission_date: datetime | None = None
    submission_deadline: datetime | None = None
    days_to_submit: int | None = None
    reportable: bool = True
    reporting_criteria_met: str
    narrative: str | None = None
    follow_up_required: bool = False
    follow_up_number: int = Field(ge=0, default=0)
    acknowledgment_received: bool = False
    prepared_by: str
    reviewed_by: str | None = None
    notes: str | None = None
    created_at: datetime


class ComplaintIntakeCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    complaint_number: str
    category: ComplaintCategory
    product_name: str
    description: str
    reporter_name: str
    received_by: str
    severity: ComplaintSeverity = ComplaintSeverity.MINOR
    batch_number: str | None = None


class ComplaintIntakeUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: ComplaintStatus | None = None
    severity: ComplaintSeverity | None = None
    sample_received: bool | None = None
    initial_assessment: str | None = None
    notes: str | None = None


class InvestigationRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    complaint_id: str
    investigator: str
    testing_performed: list[str] = Field(default_factory=list)


class InvestigationRecordUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    outcome: InvestigationOutcome | None = None
    trend_analysis_performed: bool | None = None
    recall_considered: bool | None = None
    reviewed_by: str | None = None
    notes: str | None = None


class RootCauseAnalysisCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    complaint_id: str
    root_cause_category: RootCauseCategory
    root_cause_description: str
    identified_by: str
    investigation_id: str | None = None
    analysis_method: str = "fishbone"


class RootCauseAnalysisUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    verified: bool | None = None
    verified_by: str | None = None
    probability_of_recurrence: str | None = None
    impact_scope: str | None = None
    notes: str | None = None


class CAPALinkageCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    complaint_id: str
    capa_number: str
    description: str
    assigned_to: str
    due_date: datetime
    created_by: str
    root_cause_id: str | None = None


class CAPALinkageUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str | None = None
    effectiveness_confirmed: bool | None = None
    approved_by: str | None = None
    completed_date: datetime | None = None
    notes: str | None = None


class RegulatoryReportCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    complaint_id: str
    regulatory_authority: str
    reporting_criteria_met: str
    prepared_by: str
    report_type: str = "field_alert"
    submission_deadline: datetime | None = None


class RegulatoryReportUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    acknowledgment_received: bool | None = None
    follow_up_required: bool | None = None
    reviewed_by: str | None = None
    report_number: str | None = None
    notes: str | None = None


class ComplaintIntakeListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ComplaintIntake] = Field(default_factory=list)
    total: int = Field(ge=0)


class InvestigationRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[InvestigationRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


class RootCauseAnalysisListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[RootCauseAnalysis] = Field(default_factory=list)
    total: int = Field(ge=0)


class CAPALinkageListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CAPALinkage] = Field(default_factory=list)
    total: int = Field(ge=0)


class RegulatoryReportListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[RegulatoryReport] = Field(default_factory=list)
    total: int = Field(ge=0)


class ProductComplaintMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_complaints: int = Field(ge=0)
    complaints_by_category: dict[str, int] = Field(default_factory=dict)
    complaints_by_severity: dict[str, int] = Field(default_factory=dict)
    complaints_by_status: dict[str, int] = Field(default_factory=dict)
    avg_days_open: float = Field(ge=0)
    total_investigations: int = Field(ge=0)
    investigations_by_outcome: dict[str, int] = Field(default_factory=dict)
    total_root_causes: int = Field(ge=0)
    root_causes_by_category: dict[str, int] = Field(default_factory=dict)
    total_capas: int = Field(ge=0)
    open_capas: int = Field(ge=0)
    total_regulatory_reports: int = Field(ge=0)
    reports_pending_submission: int = Field(ge=0)
