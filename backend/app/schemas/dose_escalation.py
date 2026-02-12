"""Pydantic schemas for Dose Escalation Management (DOSE-ESC).

Manages dose-finding operations: dose level definitions, escalation decisions,
dose-limiting toxicity tracking, PK/PD modeling, recommended phase 2 dose
determination, and dose escalation operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class EscalationDesign(str, Enum):
    THREE_PLUS_THREE = "3+3"
    BOIN = "boin"
    CRM = "crm"
    MCRM = "modified_crm"
    ACCELERATED = "accelerated_titration"
    ROLLING_SIX = "rolling_six"
    I_THREE_PLUS_THREE = "i3+3"


class DoseLevelStatus(str, Enum):
    PLANNED = "planned"
    ENROLLING = "enrolling"
    COMPLETED = "completed"
    EXPANDED = "expanded"
    SKIPPED = "skipped"
    CLOSED_TOXICITY = "closed_toxicity"


class DLTGrade(str, Enum):
    GRADE_3 = "grade_3"
    GRADE_4 = "grade_4"
    GRADE_5 = "grade_5"


class EscalationDecision(str, Enum):
    ESCALATE = "escalate"
    STAY = "stay"
    DE_ESCALATE = "de_escalate"
    EXPAND = "expand"
    STOP = "stop"
    RP2D_DECLARED = "rp2d_declared"


class PKParameter(str, Enum):
    CMAX = "cmax"
    TMAX = "tmax"
    AUC_0_INF = "auc_0_inf"
    AUC_0_T = "auc_0_t"
    HALF_LIFE = "half_life"
    CLEARANCE = "clearance"
    VOLUME_DIST = "volume_distribution"


class DoseLevel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    cohort_number: int = Field(ge=1)
    dose_amount: float
    dose_unit: str
    route: str
    schedule: str
    status: DoseLevelStatus = DoseLevelStatus.PLANNED
    design: EscalationDesign
    target_enrollment: int = Field(ge=0, default=3)
    actual_enrollment: int = Field(ge=0, default=0)
    dlt_count: int = Field(ge=0, default=0)
    dlt_rate_pct: float = Field(ge=0, le=100, default=0)
    evaluation_period_days: int = Field(ge=1, default=28)
    start_date: datetime | None = None
    completion_date: datetime | None = None
    created_at: datetime


class DLTEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    dose_level_id: str
    trial_id: str
    subject_id: str
    dlt_grade: DLTGrade
    toxicity_term: str
    organ_system: str
    onset_day: int = Field(ge=1)
    resolved: bool = False
    resolution_day: int | None = None
    attribution: str = "possible"
    dose_modification: str | None = None
    reported_by: str
    reported_date: datetime
    reviewed_by: str | None = None
    created_at: datetime


class CohortDecision(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    dose_level_id: str
    trial_id: str
    decision: EscalationDecision
    rationale: str
    dlt_rate_observed: float = Field(ge=0, le=100, default=0)
    target_toxicity_rate: float = Field(ge=0, le=100, default=33.3)
    model_recommendation: str | None = None
    safety_review_date: datetime
    committee_members: list[str] = Field(default_factory=list)
    next_dose_level_id: str | None = None
    approved_by: str
    created_at: datetime


class PKResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    dose_level_id: str
    trial_id: str
    subject_id: str
    parameter: PKParameter
    value: float
    unit: str
    time_point_hours: float | None = None
    dose_proportional: bool | None = None
    food_effect: bool = False
    sample_matrix: str = "plasma"
    bioanalytical_method: str | None = None
    below_lloq: bool = False
    created_at: datetime


class RP2DRecommendation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    recommended_dose: float
    dose_unit: str
    recommended_schedule: str
    selected_dose_level_id: str
    safety_summary: str
    efficacy_signals: str | None = None
    pk_rationale: str | None = None
    exposure_target: str | None = None
    therapeutic_index: float | None = None
    total_subjects_evaluated: int = Field(ge=0, default=0)
    overall_dlt_rate_pct: float = Field(ge=0, le=100, default=0)
    status: str = "proposed"
    proposed_by: str
    approved_by: str | None = None
    proposed_date: datetime
    approved_date: datetime | None = None
    created_at: datetime


class DoseLevelCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    cohort_number: int = Field(ge=1)
    dose_amount: float
    dose_unit: str
    route: str
    schedule: str
    design: EscalationDesign
    target_enrollment: int = Field(ge=0, default=3)
    evaluation_period_days: int = Field(ge=1, default=28)


class DoseLevelUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: DoseLevelStatus | None = None
    actual_enrollment: int | None = None
    dlt_count: int | None = None
    dlt_rate_pct: float | None = None


class DLTEventCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    dose_level_id: str
    trial_id: str
    subject_id: str
    dlt_grade: DLTGrade
    toxicity_term: str
    organ_system: str
    onset_day: int = Field(ge=1)
    attribution: str = "possible"
    reported_by: str


class DLTEventUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    resolved: bool | None = None
    resolution_day: int | None = None
    dose_modification: str | None = None
    reviewed_by: str | None = None


class CohortDecisionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    dose_level_id: str
    trial_id: str
    decision: EscalationDecision
    rationale: str
    safety_review_date: datetime
    approved_by: str
    dlt_rate_observed: float = Field(ge=0, le=100, default=0)
    committee_members: list[str] = Field(default_factory=list)
    next_dose_level_id: str | None = None


class CohortDecisionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    model_recommendation: str | None = None
    target_toxicity_rate: float | None = None


class PKResultCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    dose_level_id: str
    trial_id: str
    subject_id: str
    parameter: PKParameter
    value: float
    unit: str
    time_point_hours: float | None = None
    sample_matrix: str = "plasma"


class PKResultUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    dose_proportional: bool | None = None
    bioanalytical_method: str | None = None
    below_lloq: bool | None = None


class RP2DRecommendationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    recommended_dose: float
    dose_unit: str
    recommended_schedule: str
    selected_dose_level_id: str
    safety_summary: str
    proposed_by: str
    total_subjects_evaluated: int = Field(ge=0, default=0)
    overall_dlt_rate_pct: float = Field(ge=0, le=100, default=0)


class RP2DRecommendationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str | None = None
    approved_by: str | None = None
    efficacy_signals: str | None = None
    pk_rationale: str | None = None


class DoseLevelListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DoseLevel] = Field(default_factory=list)
    total: int = Field(ge=0)


class DLTEventListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DLTEvent] = Field(default_factory=list)
    total: int = Field(ge=0)


class CohortDecisionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CohortDecision] = Field(default_factory=list)
    total: int = Field(ge=0)


class PKResultListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[PKResult] = Field(default_factory=list)
    total: int = Field(ge=0)


class RP2DRecommendationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[RP2DRecommendation] = Field(default_factory=list)
    total: int = Field(ge=0)


class DoseEscalationMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_dose_levels: int = Field(ge=0)
    levels_by_status: dict[str, int] = Field(default_factory=dict)
    levels_by_design: dict[str, int] = Field(default_factory=dict)
    total_subjects_enrolled: int = Field(ge=0)
    total_dlts: int = Field(ge=0)
    overall_dlt_rate_pct: float = Field(ge=0, le=100)
    dlts_by_grade: dict[str, int] = Field(default_factory=dict)
    total_decisions: int = Field(ge=0)
    decisions_by_type: dict[str, int] = Field(default_factory=dict)
    total_pk_results: int = Field(ge=0)
    total_rp2d_recommendations: int = Field(ge=0)
    rp2d_approved: int = Field(ge=0)
