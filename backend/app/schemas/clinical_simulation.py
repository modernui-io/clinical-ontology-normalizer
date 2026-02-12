"""Pydantic schemas for Clinical Trial Simulation (SIM-TRIAL).

Manages clinical trial simulation operations: enrollment simulations,
outcome modeling, resource forecasting, scenario comparison,
and sensitivity analysis with simulation metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SimulationType(str, Enum):
    ENROLLMENT = "enrollment"
    OUTCOME = "outcome"
    RESOURCE = "resource"
    COST = "cost"
    ADAPTIVE = "adaptive"
    FULL_TRIAL = "full_trial"


class SimulationStatus(str, Enum):
    CONFIGURED = "configured"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class ModelType(str, Enum):
    MONTE_CARLO = "monte_carlo"
    MARKOV = "markov"
    DISCRETE_EVENT = "discrete_event"
    AGENT_BASED = "agent_based"
    BAYESIAN = "bayesian"
    DETERMINISTIC = "deterministic"


class ScenarioType(str, Enum):
    BASELINE = "baseline"
    OPTIMISTIC = "optimistic"
    PESSIMISTIC = "pessimistic"
    BEST_CASE = "best_case"
    WORST_CASE = "worst_case"
    CUSTOM = "custom"


class ParameterType(str, Enum):
    ENROLLMENT_RATE = "enrollment_rate"
    DROPOUT_RATE = "dropout_rate"
    EVENT_RATE = "event_rate"
    TREATMENT_EFFECT = "treatment_effect"
    COST_PER_PATIENT = "cost_per_patient"
    SITE_ACTIVATION_RATE = "site_activation_rate"


class EnrollmentSimulation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    simulation_name: str
    simulation_type: SimulationType = SimulationType.ENROLLMENT
    status: SimulationStatus = SimulationStatus.CONFIGURED
    model_type: ModelType = ModelType.MONTE_CARLO
    num_iterations: int = Field(ge=1, default=10000)
    target_enrollment: int = Field(ge=0, default=0)
    num_sites: int = Field(ge=0, default=0)
    enrollment_rate_per_site_month: float = Field(ge=0, default=0.0)
    screening_failure_rate_pct: float = Field(ge=0, le=100, default=20.0)
    dropout_rate_pct: float = Field(ge=0, le=100, default=15.0)
    median_time_to_target_weeks: float | None = None
    p10_time_weeks: float | None = None
    p90_time_weeks: float | None = None
    probability_on_time: float | None = None
    run_date: datetime | None = None
    run_duration_seconds: float | None = None
    created_by: str
    notes: str | None = None
    created_at: datetime


class OutcomeModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    model_name: str
    model_type: ModelType
    status: SimulationStatus = SimulationStatus.CONFIGURED
    primary_endpoint: str
    assumed_effect_size: float | None = None
    assumed_control_rate: float | None = None
    assumed_treatment_rate: float | None = None
    sample_size: int = Field(ge=0, default=0)
    power: float = Field(ge=0, le=1.0, default=0.80)
    alpha: float = Field(ge=0, le=1.0, default=0.05)
    num_iterations: int = Field(ge=1, default=10000)
    simulated_power: float | None = None
    probability_success: float | None = None
    expected_effect_ci_lower: float | None = None
    expected_effect_ci_upper: float | None = None
    run_date: datetime | None = None
    created_by: str
    notes: str | None = None
    created_at: datetime


class ResourceForecast(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    forecast_name: str
    status: SimulationStatus = SimulationStatus.CONFIGURED
    forecast_horizon_months: int = Field(ge=1, default=24)
    total_sites_planned: int = Field(ge=0, default=0)
    cra_fte_required: float = Field(ge=0, default=0.0)
    data_manager_fte: float = Field(ge=0, default=0.0)
    medical_monitor_fte: float = Field(ge=0, default=0.0)
    total_cost_estimate: float = Field(ge=0, default=0.0)
    cost_per_patient: float = Field(ge=0, default=0.0)
    monthly_burn_rate: float = Field(ge=0, default=0.0)
    peak_enrollment_month: int | None = None
    peak_resource_month: int | None = None
    run_date: datetime | None = None
    created_by: str
    notes: str | None = None
    created_at: datetime


class ScenarioComparison(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    comparison_name: str
    scenario_type: ScenarioType
    baseline_simulation_id: str | None = None
    comparison_simulation_id: str | None = None
    parameter_varied: str
    baseline_value: float | None = None
    comparison_value: float | None = None
    baseline_outcome: float | None = None
    comparison_outcome: float | None = None
    delta_pct: float | None = None
    recommendation: str | None = None
    is_preferred: bool = False
    analyzed_by: str
    analysis_date: datetime
    notes: str | None = None
    created_at: datetime


class SensitivityAnalysis(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    analysis_name: str
    simulation_id: str | None = None
    parameter_type: ParameterType
    parameter_name: str
    base_value: float
    min_value: float
    max_value: float
    step_count: int = Field(ge=2, default=10)
    results: list[dict] = Field(default_factory=list)
    most_sensitive_parameter: str | None = None
    tornado_rank: int | None = None
    impact_on_outcome_pct: float | None = None
    analyzed_by: str
    analysis_date: datetime
    notes: str | None = None
    created_at: datetime


class EnrollmentSimulationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    simulation_name: str
    created_by: str
    model_type: ModelType = ModelType.MONTE_CARLO
    num_iterations: int = Field(ge=1, default=10000)
    target_enrollment: int = Field(ge=0, default=0)


class EnrollmentSimulationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: SimulationStatus | None = None
    median_time_to_target_weeks: float | None = None
    probability_on_time: float | None = None
    enrollment_rate_per_site_month: float | None = None
    notes: str | None = None


class OutcomeModelCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    model_name: str
    model_type: ModelType
    primary_endpoint: str
    created_by: str
    sample_size: int = Field(ge=0, default=0)


class OutcomeModelUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: SimulationStatus | None = None
    simulated_power: float | None = None
    probability_success: float | None = None
    assumed_effect_size: float | None = None
    notes: str | None = None


class ResourceForecastCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    forecast_name: str
    created_by: str
    forecast_horizon_months: int = Field(ge=1, default=24)
    total_sites_planned: int = Field(ge=0, default=0)


class ResourceForecastUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: SimulationStatus | None = None
    total_cost_estimate: float | None = None
    monthly_burn_rate: float | None = None
    cost_per_patient: float | None = None
    notes: str | None = None


class ScenarioComparisonCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    comparison_name: str
    scenario_type: ScenarioType
    parameter_varied: str
    analyzed_by: str
    baseline_simulation_id: str | None = None


class ScenarioComparisonUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    is_preferred: bool | None = None
    recommendation: str | None = None
    comparison_outcome: float | None = None
    notes: str | None = None


class SensitivityAnalysisCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    analysis_name: str
    parameter_type: ParameterType
    parameter_name: str
    base_value: float
    min_value: float
    max_value: float
    analyzed_by: str
    simulation_id: str | None = None


class SensitivityAnalysisUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    most_sensitive_parameter: str | None = None
    impact_on_outcome_pct: float | None = None
    tornado_rank: int | None = None
    notes: str | None = None


class EnrollmentSimulationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[EnrollmentSimulation] = Field(default_factory=list)
    total: int = Field(ge=0)


class OutcomeModelListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[OutcomeModel] = Field(default_factory=list)
    total: int = Field(ge=0)


class ResourceForecastListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ResourceForecast] = Field(default_factory=list)
    total: int = Field(ge=0)


class ScenarioComparisonListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ScenarioComparison] = Field(default_factory=list)
    total: int = Field(ge=0)


class SensitivityAnalysisListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SensitivityAnalysis] = Field(default_factory=list)
    total: int = Field(ge=0)


class ClinicalSimulationMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_enrollment_sims: int = Field(ge=0)
    sims_by_status: dict[str, int] = Field(default_factory=dict)
    sims_by_model: dict[str, int] = Field(default_factory=dict)
    total_outcome_models: int = Field(ge=0)
    avg_simulated_power: float = Field(ge=0)
    total_resource_forecasts: int = Field(ge=0)
    total_forecast_cost: float = Field(ge=0)
    total_scenario_comparisons: int = Field(ge=0)
    scenarios_by_type: dict[str, int] = Field(default_factory=dict)
    total_sensitivity_analyses: int = Field(ge=0)
    analyses_by_parameter: dict[str, int] = Field(default_factory=dict)
