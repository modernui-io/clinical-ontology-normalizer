"""Pydantic schemas for Protocol Design & Optimization (PROTO-DESIGN).

Manages protocol development lifecycle: protocol elements, endpoint definitions,
sample size calculations, schedule of assessments, protocol simulations, and
protocol design metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ProtocolPhase(str, Enum):
    PHASE_1 = "phase_1"
    PHASE_1B = "phase_1b"
    PHASE_2 = "phase_2"
    PHASE_2B = "phase_2b"
    PHASE_3 = "phase_3"
    PHASE_3B = "phase_3b"
    PHASE_4 = "phase_4"


class DesignType(str, Enum):
    PARALLEL = "parallel"
    CROSSOVER = "crossover"
    FACTORIAL = "factorial"
    ADAPTIVE = "adaptive"
    BASKET = "basket"
    UMBRELLA = "umbrella"
    PLATFORM = "platform"
    SINGLE_ARM = "single_arm"


class EndpointCategory(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    EXPLORATORY = "exploratory"
    SAFETY = "safety"
    PHARMACOKINETIC = "pharmacokinetic"
    BIOMARKER = "biomarker"
    PATIENT_REPORTED = "patient_reported"


class AssessmentType(str, Enum):
    PHYSICAL_EXAM = "physical_exam"
    VITAL_SIGNS = "vital_signs"
    LAB_WORK = "lab_work"
    ECG = "ecg"
    IMAGING = "imaging"
    QUESTIONNAIRE = "questionnaire"
    BIOMARKER = "biomarker"
    PK_SAMPLE = "pk_sample"
    ADVERSE_EVENT = "adverse_event"
    CONCOMITANT_MED = "concomitant_medication"


class SimulationStatus(str, Enum):
    CONFIGURED = "configured"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DesignStatus(str, Enum):
    CONCEPT = "concept"
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    FINALIZED = "finalized"
    AMENDED = "amended"


class ProtocolElement(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    protocol_version: str
    phase: ProtocolPhase
    design_type: DesignType
    status: DesignStatus = DesignStatus.CONCEPT
    title: str
    indication: str
    target_population: str
    treatment_arms: list[str] = Field(default_factory=list)
    randomization_ratio: str | None = None
    blinding: str = "double_blind"
    planned_enrollment: int = Field(ge=0, default=0)
    treatment_duration_weeks: int = Field(ge=0, default=0)
    follow_up_duration_weeks: int = Field(ge=0, default=0)
    countries: list[str] = Field(default_factory=list)
    sites_planned: int = Field(ge=0, default=0)
    author: str
    created_at: datetime


class EndpointDefinition(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    protocol_id: str
    category: EndpointCategory
    name: str
    description: str
    measurement_tool: str
    timepoint: str
    statistical_method: str
    clinically_meaningful_difference: str | None = None
    regulatory_accepted: bool | None = None
    validated_instrument: bool = True


class SampleSizeCalc(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    protocol_id: str
    endpoint_id: str | None = None
    alpha: float = Field(ge=0, le=1, default=0.05)
    power: float = Field(ge=0, le=1, default=0.80)
    effect_size: float | None = None
    dropout_rate_pct: float = Field(ge=0, le=100, default=10)
    sample_per_arm: int = Field(ge=0, default=0)
    total_sample: int = Field(ge=0, default=0)
    method: str
    assumptions: list[str] = Field(default_factory=list)
    calculated_by: str
    calculation_date: datetime


class ScheduleOfAssessments(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    protocol_id: str
    visit_name: str
    visit_number: int = Field(ge=0)
    day: int
    window_minus_days: int = Field(ge=0, default=0)
    window_plus_days: int = Field(ge=0, default=0)
    assessments: list[AssessmentType] = Field(default_factory=list)
    mandatory: bool = True
    estimated_duration_minutes: int = Field(ge=0, default=0)
    notes: str | None = None


class ProtocolSimulation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    protocol_id: str
    simulation_name: str
    status: SimulationStatus = SimulationStatus.CONFIGURED
    iterations: int = Field(ge=1, default=1000)
    enrollment_rate_per_month: float = Field(ge=0)
    dropout_rate_pct: float = Field(ge=0, le=100)
    effect_size: float | None = None
    predicted_power: float | None = None
    predicted_duration_months: float | None = None
    predicted_cost: float | None = None
    success_probability_pct: float | None = None
    run_date: datetime | None = None
    run_by: str


class ProtocolElementCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    protocol_version: str
    phase: ProtocolPhase
    design_type: DesignType
    title: str
    indication: str
    target_population: str
    treatment_arms: list[str] = Field(default_factory=list)
    blinding: str = "double_blind"
    planned_enrollment: int = Field(ge=0, default=0)
    author: str


class ProtocolElementUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: DesignStatus | None = None
    treatment_arms: list[str] | None = None
    randomization_ratio: str | None = None
    planned_enrollment: int | None = None
    treatment_duration_weeks: int | None = None
    follow_up_duration_weeks: int | None = None
    countries: list[str] | None = None
    sites_planned: int | None = None


class EndpointDefinitionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    protocol_id: str
    category: EndpointCategory
    name: str
    description: str
    measurement_tool: str
    timepoint: str
    statistical_method: str
    clinically_meaningful_difference: str | None = None


class SampleSizeCalcCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    protocol_id: str
    endpoint_id: str | None = None
    alpha: float = Field(ge=0, le=1, default=0.05)
    power: float = Field(ge=0, le=1, default=0.80)
    effect_size: float | None = None
    dropout_rate_pct: float = Field(ge=0, le=100, default=10)
    sample_per_arm: int = Field(ge=0, default=0)
    total_sample: int = Field(ge=0, default=0)
    method: str
    assumptions: list[str] = Field(default_factory=list)
    calculated_by: str


class ScheduleOfAssessmentsCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    protocol_id: str
    visit_name: str
    visit_number: int = Field(ge=0)
    day: int
    window_minus_days: int = Field(ge=0, default=0)
    window_plus_days: int = Field(ge=0, default=0)
    assessments: list[AssessmentType] = Field(default_factory=list)
    mandatory: bool = True
    estimated_duration_minutes: int = Field(ge=0, default=0)


class ProtocolSimulationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    protocol_id: str
    simulation_name: str
    iterations: int = Field(ge=1, default=1000)
    enrollment_rate_per_month: float = Field(ge=0)
    dropout_rate_pct: float = Field(ge=0, le=100)
    effect_size: float | None = None
    run_by: str


class ProtocolSimulationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: SimulationStatus | None = None
    predicted_power: float | None = None
    predicted_duration_months: float | None = None
    predicted_cost: float | None = None
    success_probability_pct: float | None = None


class ProtocolElementListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ProtocolElement] = Field(default_factory=list)
    total: int = Field(ge=0)


class EndpointDefinitionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[EndpointDefinition] = Field(default_factory=list)
    total: int = Field(ge=0)


class SampleSizeCalcListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SampleSizeCalc] = Field(default_factory=list)
    total: int = Field(ge=0)


class ScheduleOfAssessmentsListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ScheduleOfAssessments] = Field(default_factory=list)
    total: int = Field(ge=0)


class ProtocolSimulationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ProtocolSimulation] = Field(default_factory=list)
    total: int = Field(ge=0)


class ProtocolDesignMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_protocols: int = Field(ge=0)
    protocols_by_phase: dict[str, int] = Field(default_factory=dict)
    protocols_by_design: dict[str, int] = Field(default_factory=dict)
    protocols_by_status: dict[str, int] = Field(default_factory=dict)
    total_endpoints: int = Field(ge=0)
    endpoints_by_category: dict[str, int] = Field(default_factory=dict)
    total_sample_calcs: int = Field(ge=0)
    total_schedule_visits: int = Field(ge=0)
    avg_visit_duration_minutes: float = Field(ge=0)
    total_simulations: int = Field(ge=0)
    simulations_by_status: dict[str, int] = Field(default_factory=dict)
    avg_predicted_power: float | None = None
