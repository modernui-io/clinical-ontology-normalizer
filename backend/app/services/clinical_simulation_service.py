"""Clinical Trial Simulation Service (SIM-TRIAL).

Manages clinical trial simulation operations: enrollment simulations,
outcome modeling, resource forecasting, scenario comparison,
and sensitivity analysis with simulation metrics.

Usage:
    from app.services.clinical_simulation_service import (
        get_clinical_simulation_service,
    )

    svc = get_clinical_simulation_service()
    simulations = svc.list_enrollment_simulations()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.clinical_simulation import (
    ClinicalSimulationMetrics,
    EnrollmentSimulation,
    EnrollmentSimulationCreate,
    EnrollmentSimulationUpdate,
    ModelType,
    OutcomeModel,
    OutcomeModelCreate,
    OutcomeModelUpdate,
    ParameterType,
    ResourceForecast,
    ResourceForecastCreate,
    ResourceForecastUpdate,
    ScenarioComparison,
    ScenarioComparisonCreate,
    ScenarioComparisonUpdate,
    ScenarioType,
    SensitivityAnalysis,
    SensitivityAnalysisCreate,
    SensitivityAnalysisUpdate,
    SimulationStatus,
    SimulationType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class ClinicalSimulationService:
    """In-memory Clinical Trial Simulation engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._enrollment_simulations: dict[str, EnrollmentSimulation] = {}
        self._outcome_models: dict[str, OutcomeModel] = {}
        self._resource_forecasts: dict[str, ResourceForecast] = {}
        self._scenario_comparisons: dict[str, ScenarioComparison] = {}
        self._sensitivity_analyses: dict[str, SensitivityAnalysis] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic clinical trial simulation data."""
        now = datetime.now(timezone.utc)

        # --- 12 Enrollment Simulations ---
        enrollment_data = [
            {
                "id": "ES-001",
                "trial_id": EYLEA_TRIAL,
                "simulation_name": "EYLEA Baseline Enrollment Model",
                "simulation_type": SimulationType.ENROLLMENT,
                "status": SimulationStatus.COMPLETED,
                "model_type": ModelType.MONTE_CARLO,
                "num_iterations": 10000,
                "target_enrollment": 300,
                "num_sites": 45,
                "enrollment_rate_per_site_month": 1.8,
                "screening_failure_rate_pct": 22.0,
                "dropout_rate_pct": 12.0,
                "median_time_to_target_weeks": 42.5,
                "p10_time_weeks": 36.0,
                "p90_time_weeks": 52.0,
                "probability_on_time": 0.72,
                "run_date": now - timedelta(days=180),
                "run_duration_seconds": 45.2,
                "created_by": "Dr. Sarah Chen",
                "notes": "Baseline enrollment projection for EYLEA Phase III.",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "ES-002",
                "trial_id": EYLEA_TRIAL,
                "simulation_name": "EYLEA Accelerated Enrollment",
                "simulation_type": SimulationType.ENROLLMENT,
                "status": SimulationStatus.COMPLETED,
                "model_type": ModelType.MONTE_CARLO,
                "num_iterations": 10000,
                "target_enrollment": 300,
                "num_sites": 60,
                "enrollment_rate_per_site_month": 2.1,
                "screening_failure_rate_pct": 20.0,
                "dropout_rate_pct": 10.0,
                "median_time_to_target_weeks": 34.0,
                "p10_time_weeks": 28.0,
                "p90_time_weeks": 42.0,
                "probability_on_time": 0.88,
                "run_date": now - timedelta(days=170),
                "run_duration_seconds": 48.7,
                "created_by": "Dr. Sarah Chen",
                "notes": "Accelerated scenario with 60 sites and improved screening.",
                "created_at": now - timedelta(days=170),
            },
            {
                "id": "ES-003",
                "trial_id": DUPIXENT_TRIAL,
                "simulation_name": "DUPIXENT Global Enrollment Forecast",
                "simulation_type": SimulationType.ENROLLMENT,
                "status": SimulationStatus.COMPLETED,
                "model_type": ModelType.DISCRETE_EVENT,
                "num_iterations": 15000,
                "target_enrollment": 360,
                "num_sites": 80,
                "enrollment_rate_per_site_month": 1.5,
                "screening_failure_rate_pct": 25.0,
                "dropout_rate_pct": 18.0,
                "median_time_to_target_weeks": 48.0,
                "p10_time_weeks": 40.0,
                "p90_time_weeks": 60.0,
                "probability_on_time": 0.65,
                "run_date": now - timedelta(days=150),
                "run_duration_seconds": 62.3,
                "created_by": "Dr. Maria Lopez",
                "notes": "Global enrollment model accounting for regional variability.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "ES-004",
                "trial_id": DUPIXENT_TRIAL,
                "simulation_name": "DUPIXENT Post-SSR Enrollment Update",
                "simulation_type": SimulationType.ENROLLMENT,
                "status": SimulationStatus.COMPLETED,
                "model_type": ModelType.MONTE_CARLO,
                "num_iterations": 10000,
                "target_enrollment": 360,
                "num_sites": 85,
                "enrollment_rate_per_site_month": 1.6,
                "screening_failure_rate_pct": 23.0,
                "dropout_rate_pct": 16.0,
                "median_time_to_target_weeks": 44.0,
                "p10_time_weeks": 38.0,
                "p90_time_weeks": 54.0,
                "probability_on_time": 0.70,
                "run_date": now - timedelta(days=80),
                "run_duration_seconds": 41.8,
                "created_by": "Dr. Robert Kim",
                "notes": "Updated model after sample size re-estimation to 360.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "ES-005",
                "trial_id": LIBTAYO_TRIAL,
                "simulation_name": "LIBTAYO Oncology Enrollment Baseline",
                "simulation_type": SimulationType.ENROLLMENT,
                "status": SimulationStatus.COMPLETED,
                "model_type": ModelType.BAYESIAN,
                "num_iterations": 20000,
                "target_enrollment": 400,
                "num_sites": 100,
                "enrollment_rate_per_site_month": 1.2,
                "screening_failure_rate_pct": 30.0,
                "dropout_rate_pct": 20.0,
                "median_time_to_target_weeks": 56.0,
                "p10_time_weeks": 48.0,
                "p90_time_weeks": 68.0,
                "probability_on_time": 0.55,
                "run_date": now - timedelta(days=200),
                "run_duration_seconds": 78.5,
                "created_by": "Dr. Angela Park",
                "notes": "Baseline oncology enrollment model. Higher screening failure expected.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "ES-006",
                "trial_id": LIBTAYO_TRIAL,
                "simulation_name": "LIBTAYO Post Arm-Drop Enrollment",
                "simulation_type": SimulationType.ENROLLMENT,
                "status": SimulationStatus.COMPLETED,
                "model_type": ModelType.BAYESIAN,
                "num_iterations": 20000,
                "target_enrollment": 340,
                "num_sites": 95,
                "enrollment_rate_per_site_month": 1.3,
                "screening_failure_rate_pct": 28.0,
                "dropout_rate_pct": 18.0,
                "median_time_to_target_weeks": 44.0,
                "p10_time_weeks": 38.0,
                "p90_time_weeks": 54.0,
                "probability_on_time": 0.68,
                "run_date": now - timedelta(days=120),
                "run_duration_seconds": 72.1,
                "created_by": "Dr. Angela Park",
                "notes": "Updated after low-dose arm drop. Reduced target enrollment.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "ES-007",
                "trial_id": EYLEA_TRIAL,
                "simulation_name": "EYLEA Conservative Scenario",
                "simulation_type": SimulationType.ENROLLMENT,
                "status": SimulationStatus.COMPLETED,
                "model_type": ModelType.MONTE_CARLO,
                "num_iterations": 10000,
                "target_enrollment": 300,
                "num_sites": 40,
                "enrollment_rate_per_site_month": 1.5,
                "screening_failure_rate_pct": 28.0,
                "dropout_rate_pct": 15.0,
                "median_time_to_target_weeks": 52.0,
                "p10_time_weeks": 44.0,
                "p90_time_weeks": 64.0,
                "probability_on_time": 0.50,
                "run_date": now - timedelta(days=175),
                "run_duration_seconds": 43.9,
                "created_by": "Dr. James Wright",
                "notes": "Conservative scenario with fewer sites and higher screening failure.",
                "created_at": now - timedelta(days=175),
            },
            {
                "id": "ES-008",
                "trial_id": DUPIXENT_TRIAL,
                "simulation_name": "DUPIXENT Pessimistic Enrollment",
                "simulation_type": SimulationType.ENROLLMENT,
                "status": SimulationStatus.COMPLETED,
                "model_type": ModelType.DISCRETE_EVENT,
                "num_iterations": 15000,
                "target_enrollment": 360,
                "num_sites": 70,
                "enrollment_rate_per_site_month": 1.2,
                "screening_failure_rate_pct": 30.0,
                "dropout_rate_pct": 22.0,
                "median_time_to_target_weeks": 58.0,
                "p10_time_weeks": 50.0,
                "p90_time_weeks": 72.0,
                "probability_on_time": 0.40,
                "run_date": now - timedelta(days=145),
                "run_duration_seconds": 58.2,
                "created_by": "Dr. Maria Lopez",
                "notes": "Worst-case enrollment scenario for budget planning.",
                "created_at": now - timedelta(days=145),
            },
            {
                "id": "ES-009",
                "trial_id": LIBTAYO_TRIAL,
                "simulation_name": "LIBTAYO Adaptive Enrollment Model",
                "simulation_type": SimulationType.ADAPTIVE,
                "status": SimulationStatus.RUNNING,
                "model_type": ModelType.AGENT_BASED,
                "num_iterations": 25000,
                "target_enrollment": 320,
                "num_sites": 90,
                "enrollment_rate_per_site_month": 1.4,
                "screening_failure_rate_pct": 26.0,
                "dropout_rate_pct": 16.0,
                "median_time_to_target_weeks": None,
                "p10_time_weeks": None,
                "p90_time_weeks": None,
                "probability_on_time": None,
                "run_date": now - timedelta(hours=2),
                "run_duration_seconds": None,
                "created_by": "Dr. Angela Park",
                "notes": "Agent-based model incorporating site-level heterogeneity.",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "ES-010",
                "trial_id": EYLEA_TRIAL,
                "simulation_name": "EYLEA Final Enrollment Summary",
                "simulation_type": SimulationType.FULL_TRIAL,
                "status": SimulationStatus.COMPLETED,
                "model_type": ModelType.DETERMINISTIC,
                "num_iterations": 1,
                "target_enrollment": 225,
                "num_sites": 45,
                "enrollment_rate_per_site_month": 2.0,
                "screening_failure_rate_pct": 20.0,
                "dropout_rate_pct": 10.0,
                "median_time_to_target_weeks": 30.0,
                "p10_time_weeks": 30.0,
                "p90_time_weeks": 30.0,
                "probability_on_time": 1.0,
                "run_date": now - timedelta(days=25),
                "run_duration_seconds": 0.5,
                "created_by": "Dr. Sarah Chen",
                "notes": "Final deterministic summary post early stopping for efficacy.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "ES-011",
                "trial_id": DUPIXENT_TRIAL,
                "simulation_name": "DUPIXENT Planned Re-simulation",
                "simulation_type": SimulationType.ENROLLMENT,
                "status": SimulationStatus.CONFIGURED,
                "model_type": ModelType.MONTE_CARLO,
                "num_iterations": 10000,
                "target_enrollment": 370,
                "num_sites": 90,
                "enrollment_rate_per_site_month": 0.0,
                "screening_failure_rate_pct": 20.0,
                "dropout_rate_pct": 15.0,
                "median_time_to_target_weeks": None,
                "p10_time_weeks": None,
                "p90_time_weeks": None,
                "probability_on_time": None,
                "run_date": None,
                "run_duration_seconds": None,
                "created_by": "Dr. Robert Kim",
                "notes": "Awaiting updated site activation data.",
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "ES-012",
                "trial_id": LIBTAYO_TRIAL,
                "simulation_name": "LIBTAYO Combination Arm Enrollment",
                "simulation_type": SimulationType.ENROLLMENT,
                "status": SimulationStatus.CONFIGURED,
                "model_type": ModelType.MONTE_CARLO,
                "num_iterations": 10000,
                "target_enrollment": 80,
                "num_sites": 50,
                "enrollment_rate_per_site_month": 0.0,
                "screening_failure_rate_pct": 25.0,
                "dropout_rate_pct": 15.0,
                "median_time_to_target_weeks": None,
                "p10_time_weeks": None,
                "p90_time_weeks": None,
                "probability_on_time": None,
                "run_date": None,
                "run_duration_seconds": None,
                "created_by": "Dr. Angela Park",
                "notes": "Pending approval of combination arm addition.",
                "created_at": now - timedelta(days=2),
            },
        ]

        for e in enrollment_data:
            self._enrollment_simulations[e["id"]] = EnrollmentSimulation(**e)

        # --- 10 Outcome Models ---
        outcome_data = [
            {
                "id": "OM-001",
                "trial_id": EYLEA_TRIAL,
                "model_name": "EYLEA Primary Efficacy Power",
                "model_type": ModelType.MONTE_CARLO,
                "status": SimulationStatus.COMPLETED,
                "primary_endpoint": "BCVA change from baseline at Week 48",
                "assumed_effect_size": 0.35,
                "assumed_control_rate": 0.30,
                "assumed_treatment_rate": 0.65,
                "sample_size": 300,
                "power": 0.80,
                "alpha": 0.05,
                "num_iterations": 10000,
                "simulated_power": 0.87,
                "probability_success": 0.82,
                "expected_effect_ci_lower": 0.22,
                "expected_effect_ci_upper": 0.48,
                "run_date": now - timedelta(days=180),
                "created_by": "Dr. Sarah Chen",
                "notes": "Primary power analysis for EYLEA Phase III.",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "OM-002",
                "trial_id": EYLEA_TRIAL,
                "model_name": "EYLEA Bayesian Outcome Model",
                "model_type": ModelType.BAYESIAN,
                "status": SimulationStatus.COMPLETED,
                "primary_endpoint": "BCVA change from baseline at Week 48",
                "assumed_effect_size": 0.38,
                "assumed_control_rate": 0.28,
                "assumed_treatment_rate": 0.66,
                "sample_size": 225,
                "power": 0.80,
                "alpha": 0.05,
                "num_iterations": 20000,
                "simulated_power": 0.94,
                "probability_success": 0.91,
                "expected_effect_ci_lower": 0.28,
                "expected_effect_ci_upper": 0.52,
                "run_date": now - timedelta(days=28),
                "created_by": "Dr. Sarah Chen",
                "notes": "Updated Bayesian model post early stopping decision.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "OM-003",
                "trial_id": DUPIXENT_TRIAL,
                "model_name": "DUPIXENT EASI-75 Response Model",
                "model_type": ModelType.MONTE_CARLO,
                "status": SimulationStatus.COMPLETED,
                "primary_endpoint": "EASI-75 response rate at Week 16",
                "assumed_effect_size": 0.30,
                "assumed_control_rate": 0.15,
                "assumed_treatment_rate": 0.45,
                "sample_size": 360,
                "power": 0.80,
                "alpha": 0.05,
                "num_iterations": 10000,
                "simulated_power": 0.78,
                "probability_success": 0.72,
                "expected_effect_ci_lower": 0.18,
                "expected_effect_ci_upper": 0.42,
                "run_date": now - timedelta(days=90),
                "created_by": "Dr. Maria Lopez",
                "notes": "Power analysis post SSR. Marginal power with increased N.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "OM-004",
                "trial_id": DUPIXENT_TRIAL,
                "model_name": "DUPIXENT Markov Disease Progression",
                "model_type": ModelType.MARKOV,
                "status": SimulationStatus.COMPLETED,
                "primary_endpoint": "Disease state transition probabilities",
                "assumed_effect_size": 0.25,
                "assumed_control_rate": None,
                "assumed_treatment_rate": None,
                "sample_size": 360,
                "power": 0.80,
                "alpha": 0.05,
                "num_iterations": 5000,
                "simulated_power": 0.75,
                "probability_success": 0.68,
                "expected_effect_ci_lower": 0.15,
                "expected_effect_ci_upper": 0.38,
                "run_date": now - timedelta(days=60),
                "created_by": "Dr. Robert Kim",
                "notes": "Markov model for long-term disease progression outcomes.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "OM-005",
                "trial_id": LIBTAYO_TRIAL,
                "model_name": "LIBTAYO OS Primary Endpoint",
                "model_type": ModelType.MONTE_CARLO,
                "status": SimulationStatus.COMPLETED,
                "primary_endpoint": "Overall survival hazard ratio",
                "assumed_effect_size": 0.30,
                "assumed_control_rate": 0.40,
                "assumed_treatment_rate": 0.55,
                "sample_size": 400,
                "power": 0.80,
                "alpha": 0.05,
                "num_iterations": 10000,
                "simulated_power": 0.82,
                "probability_success": 0.76,
                "expected_effect_ci_lower": 0.18,
                "expected_effect_ci_upper": 0.44,
                "run_date": now - timedelta(days=200),
                "created_by": "Dr. Angela Park",
                "notes": "Baseline OS power analysis for three-arm design.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "OM-006",
                "trial_id": LIBTAYO_TRIAL,
                "model_name": "LIBTAYO Post Arm-Drop Power",
                "model_type": ModelType.MONTE_CARLO,
                "status": SimulationStatus.COMPLETED,
                "primary_endpoint": "Overall survival hazard ratio",
                "assumed_effect_size": 0.35,
                "assumed_control_rate": 0.40,
                "assumed_treatment_rate": 0.58,
                "sample_size": 340,
                "power": 0.90,
                "alpha": 0.05,
                "num_iterations": 15000,
                "simulated_power": 0.88,
                "probability_success": 0.84,
                "expected_effect_ci_lower": 0.24,
                "expected_effect_ci_upper": 0.50,
                "run_date": now - timedelta(days=65),
                "created_by": "Dr. Angela Park",
                "notes": "Updated power after dropping low-dose arm. Strong effect in high dose.",
                "created_at": now - timedelta(days=65),
            },
            {
                "id": "OM-007",
                "trial_id": EYLEA_TRIAL,
                "model_name": "EYLEA Secondary Endpoint Power",
                "model_type": ModelType.DETERMINISTIC,
                "status": SimulationStatus.COMPLETED,
                "primary_endpoint": "Proportion gaining >=15 ETDRS letters",
                "assumed_effect_size": 0.20,
                "assumed_control_rate": 0.25,
                "assumed_treatment_rate": 0.45,
                "sample_size": 300,
                "power": 0.80,
                "alpha": 0.025,
                "num_iterations": 1,
                "simulated_power": 0.85,
                "probability_success": 0.80,
                "expected_effect_ci_lower": 0.12,
                "expected_effect_ci_upper": 0.30,
                "run_date": now - timedelta(days=178),
                "created_by": "Dr. James Wright",
                "notes": "Key secondary endpoint power with multiplicity-adjusted alpha.",
                "created_at": now - timedelta(days=178),
            },
            {
                "id": "OM-008",
                "trial_id": DUPIXENT_TRIAL,
                "model_name": "DUPIXENT IGA Response Model",
                "model_type": ModelType.BAYESIAN,
                "status": SimulationStatus.COMPLETED,
                "primary_endpoint": "IGA 0/1 response at Week 16",
                "assumed_effect_size": 0.28,
                "assumed_control_rate": 0.08,
                "assumed_treatment_rate": 0.36,
                "sample_size": 360,
                "power": 0.80,
                "alpha": 0.05,
                "num_iterations": 10000,
                "simulated_power": 0.91,
                "probability_success": 0.86,
                "expected_effect_ci_lower": 0.20,
                "expected_effect_ci_upper": 0.40,
                "run_date": now - timedelta(days=85),
                "created_by": "Dr. Maria Lopez",
                "notes": "Co-primary endpoint IGA analysis. Higher power than EASI-75.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "OM-009",
                "trial_id": LIBTAYO_TRIAL,
                "model_name": "LIBTAYO PFS Outcome Model",
                "model_type": ModelType.MONTE_CARLO,
                "status": SimulationStatus.RUNNING,
                "primary_endpoint": "Progression-free survival",
                "assumed_effect_size": 0.32,
                "assumed_control_rate": 0.35,
                "assumed_treatment_rate": 0.52,
                "sample_size": 320,
                "power": 0.80,
                "alpha": 0.05,
                "num_iterations": 10000,
                "simulated_power": None,
                "probability_success": None,
                "expected_effect_ci_lower": None,
                "expected_effect_ci_upper": None,
                "run_date": now - timedelta(hours=1),
                "created_by": "Dr. Angela Park",
                "notes": "Secondary PFS endpoint simulation in progress.",
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "OM-010",
                "trial_id": LIBTAYO_TRIAL,
                "model_name": "LIBTAYO Combination Arm Power",
                "model_type": ModelType.MONTE_CARLO,
                "status": SimulationStatus.CONFIGURED,
                "primary_endpoint": "Overall survival hazard ratio",
                "assumed_effect_size": 0.40,
                "assumed_control_rate": 0.40,
                "assumed_treatment_rate": 0.62,
                "sample_size": 80,
                "power": 0.80,
                "alpha": 0.05,
                "num_iterations": 10000,
                "simulated_power": None,
                "probability_success": None,
                "expected_effect_ci_lower": None,
                "expected_effect_ci_upper": None,
                "run_date": None,
                "created_by": "Dr. Angela Park",
                "notes": "Planned power analysis for proposed combination arm.",
                "created_at": now - timedelta(days=2),
            },
        ]

        for o in outcome_data:
            self._outcome_models[o["id"]] = OutcomeModel(**o)

        # --- 10 Resource Forecasts ---
        resource_data = [
            {
                "id": "RF-001",
                "trial_id": EYLEA_TRIAL,
                "forecast_name": "EYLEA Baseline Resource Forecast",
                "status": SimulationStatus.COMPLETED,
                "forecast_horizon_months": 24,
                "total_sites_planned": 45,
                "cra_fte_required": 12.5,
                "data_manager_fte": 4.0,
                "medical_monitor_fte": 2.0,
                "total_cost_estimate": 45000000.0,
                "cost_per_patient": 150000.0,
                "monthly_burn_rate": 1875000.0,
                "peak_enrollment_month": 10,
                "peak_resource_month": 14,
                "run_date": now - timedelta(days=180),
                "created_by": "Dr. Sarah Chen",
                "notes": "Baseline resource forecast for EYLEA Phase III.",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "RF-002",
                "trial_id": EYLEA_TRIAL,
                "forecast_name": "EYLEA Post Early-Stop Resource Update",
                "status": SimulationStatus.COMPLETED,
                "forecast_horizon_months": 12,
                "total_sites_planned": 45,
                "cra_fte_required": 8.0,
                "data_manager_fte": 3.0,
                "medical_monitor_fte": 1.5,
                "total_cost_estimate": 28000000.0,
                "cost_per_patient": 124444.0,
                "monthly_burn_rate": 2333333.0,
                "peak_enrollment_month": 8,
                "peak_resource_month": 10,
                "run_date": now - timedelta(days=25),
                "created_by": "Dr. Sarah Chen",
                "notes": "Updated forecast after early stopping. Reduced horizon and resources.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "RF-003",
                "trial_id": DUPIXENT_TRIAL,
                "forecast_name": "DUPIXENT Global Resource Plan",
                "status": SimulationStatus.COMPLETED,
                "forecast_horizon_months": 30,
                "total_sites_planned": 80,
                "cra_fte_required": 18.0,
                "data_manager_fte": 6.0,
                "medical_monitor_fte": 3.0,
                "total_cost_estimate": 72000000.0,
                "cost_per_patient": 200000.0,
                "monthly_burn_rate": 2400000.0,
                "peak_enrollment_month": 14,
                "peak_resource_month": 18,
                "run_date": now - timedelta(days=150),
                "created_by": "Dr. Maria Lopez",
                "notes": "Global resource forecast with 80 sites across 15 countries.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "RF-004",
                "trial_id": DUPIXENT_TRIAL,
                "forecast_name": "DUPIXENT Post-SSR Budget Update",
                "status": SimulationStatus.COMPLETED,
                "forecast_horizon_months": 33,
                "total_sites_planned": 85,
                "cra_fte_required": 20.0,
                "data_manager_fte": 7.0,
                "medical_monitor_fte": 3.5,
                "total_cost_estimate": 82000000.0,
                "cost_per_patient": 227778.0,
                "monthly_burn_rate": 2484848.0,
                "peak_enrollment_month": 16,
                "peak_resource_month": 20,
                "run_date": now - timedelta(days=75),
                "created_by": "Dr. Robert Kim",
                "notes": "Budget increase of $10M following SSR to 360 subjects.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "RF-005",
                "trial_id": LIBTAYO_TRIAL,
                "forecast_name": "LIBTAYO Oncology Resource Baseline",
                "status": SimulationStatus.COMPLETED,
                "forecast_horizon_months": 36,
                "total_sites_planned": 100,
                "cra_fte_required": 25.0,
                "data_manager_fte": 8.0,
                "medical_monitor_fte": 4.0,
                "total_cost_estimate": 120000000.0,
                "cost_per_patient": 300000.0,
                "monthly_burn_rate": 3333333.0,
                "peak_enrollment_month": 18,
                "peak_resource_month": 24,
                "run_date": now - timedelta(days=200),
                "created_by": "Dr. Angela Park",
                "notes": "Baseline oncology resource forecast. Higher per-patient costs.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "RF-006",
                "trial_id": LIBTAYO_TRIAL,
                "forecast_name": "LIBTAYO Post Arm-Drop Resource Plan",
                "status": SimulationStatus.COMPLETED,
                "forecast_horizon_months": 30,
                "total_sites_planned": 95,
                "cra_fte_required": 22.0,
                "data_manager_fte": 7.0,
                "medical_monitor_fte": 3.5,
                "total_cost_estimate": 102000000.0,
                "cost_per_patient": 300000.0,
                "monthly_burn_rate": 3400000.0,
                "peak_enrollment_month": 14,
                "peak_resource_month": 20,
                "run_date": now - timedelta(days=115),
                "created_by": "Dr. Angela Park",
                "notes": "Savings of $18M from arm drop offset by per-patient cost maintenance.",
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "RF-007",
                "trial_id": EYLEA_TRIAL,
                "forecast_name": "EYLEA Close-Out Resource Plan",
                "status": SimulationStatus.COMPLETED,
                "forecast_horizon_months": 6,
                "total_sites_planned": 45,
                "cra_fte_required": 6.0,
                "data_manager_fte": 5.0,
                "medical_monitor_fte": 1.0,
                "total_cost_estimate": 8000000.0,
                "cost_per_patient": 35556.0,
                "monthly_burn_rate": 1333333.0,
                "peak_enrollment_month": None,
                "peak_resource_month": 2,
                "run_date": now - timedelta(days=20),
                "created_by": "Dr. James Wright",
                "notes": "Close-out phase resource allocation after early stopping.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "RF-008",
                "trial_id": DUPIXENT_TRIAL,
                "forecast_name": "DUPIXENT Regional Resource Breakdown",
                "status": SimulationStatus.COMPLETED,
                "forecast_horizon_months": 30,
                "total_sites_planned": 85,
                "cra_fte_required": 20.0,
                "data_manager_fte": 6.5,
                "medical_monitor_fte": 3.0,
                "total_cost_estimate": 78000000.0,
                "cost_per_patient": 216667.0,
                "monthly_burn_rate": 2600000.0,
                "peak_enrollment_month": 15,
                "peak_resource_month": 19,
                "run_date": now - timedelta(days=60),
                "created_by": "Dr. Maria Lopez",
                "notes": "Regional breakdown: NA 45%, EU 35%, APAC 20%.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "RF-009",
                "trial_id": LIBTAYO_TRIAL,
                "forecast_name": "LIBTAYO Combination Arm Resource Add",
                "status": SimulationStatus.CONFIGURED,
                "forecast_horizon_months": 18,
                "total_sites_planned": 50,
                "cra_fte_required": 8.0,
                "data_manager_fte": 3.0,
                "medical_monitor_fte": 2.0,
                "total_cost_estimate": 32000000.0,
                "cost_per_patient": 400000.0,
                "monthly_burn_rate": 1777778.0,
                "peak_enrollment_month": None,
                "peak_resource_month": None,
                "run_date": None,
                "created_by": "Dr. Angela Park",
                "notes": "Incremental resource forecast for proposed combination arm.",
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "RF-010",
                "trial_id": DUPIXENT_TRIAL,
                "forecast_name": "DUPIXENT Long-Term Follow-Up Resources",
                "status": SimulationStatus.CONFIGURED,
                "forecast_horizon_months": 12,
                "total_sites_planned": 85,
                "cra_fte_required": 5.0,
                "data_manager_fte": 4.0,
                "medical_monitor_fte": 1.5,
                "total_cost_estimate": 15000000.0,
                "cost_per_patient": 41667.0,
                "monthly_burn_rate": 1250000.0,
                "peak_enrollment_month": None,
                "peak_resource_month": 3,
                "run_date": None,
                "created_by": "Dr. Robert Kim",
                "notes": "Long-term follow-up phase resource planning.",
                "created_at": now - timedelta(days=5),
            },
        ]

        for r in resource_data:
            self._resource_forecasts[r["id"]] = ResourceForecast(**r)

        # --- 10 Scenario Comparisons ---
        scenario_data = [
            {
                "id": "SC-001",
                "trial_id": EYLEA_TRIAL,
                "comparison_name": "EYLEA 45 vs 60 Sites",
                "scenario_type": ScenarioType.OPTIMISTIC,
                "baseline_simulation_id": "ES-001",
                "comparison_simulation_id": "ES-002",
                "parameter_varied": "num_sites",
                "baseline_value": 45.0,
                "comparison_value": 60.0,
                "baseline_outcome": 42.5,
                "comparison_outcome": 34.0,
                "delta_pct": -20.0,
                "recommendation": "Adding 15 sites reduces median enrollment time by 20%. Cost-benefit favorable.",
                "is_preferred": True,
                "analyzed_by": "Dr. Sarah Chen",
                "analysis_date": now - timedelta(days=168),
                "notes": "Site expansion scenario strongly preferred.",
                "created_at": now - timedelta(days=168),
            },
            {
                "id": "SC-002",
                "trial_id": EYLEA_TRIAL,
                "comparison_name": "EYLEA Baseline vs Conservative",
                "scenario_type": ScenarioType.PESSIMISTIC,
                "baseline_simulation_id": "ES-001",
                "comparison_simulation_id": "ES-007",
                "parameter_varied": "enrollment_rate_per_site_month",
                "baseline_value": 1.8,
                "comparison_value": 1.5,
                "baseline_outcome": 42.5,
                "comparison_outcome": 52.0,
                "delta_pct": 22.4,
                "recommendation": "Conservative scenario delays by 9.5 weeks. Contingency budget needed.",
                "is_preferred": False,
                "analyzed_by": "Dr. James Wright",
                "analysis_date": now - timedelta(days=172),
                "notes": "Risk assessment for enrollment delay.",
                "created_at": now - timedelta(days=172),
            },
            {
                "id": "SC-003",
                "trial_id": DUPIXENT_TRIAL,
                "comparison_name": "DUPIXENT Pre vs Post SSR",
                "scenario_type": ScenarioType.BASELINE,
                "baseline_simulation_id": "ES-003",
                "comparison_simulation_id": "ES-004",
                "parameter_varied": "target_enrollment",
                "baseline_value": 300.0,
                "comparison_value": 360.0,
                "baseline_outcome": 48.0,
                "comparison_outcome": 44.0,
                "delta_pct": -8.3,
                "recommendation": "SSR improves enrollment time despite larger N due to site expansion.",
                "is_preferred": True,
                "analyzed_by": "Dr. Maria Lopez",
                "analysis_date": now - timedelta(days=78),
                "notes": "Counterintuitive result: more subjects but faster enrollment.",
                "created_at": now - timedelta(days=78),
            },
            {
                "id": "SC-004",
                "trial_id": DUPIXENT_TRIAL,
                "comparison_name": "DUPIXENT Optimistic vs Pessimistic",
                "scenario_type": ScenarioType.WORST_CASE,
                "baseline_simulation_id": "ES-003",
                "comparison_simulation_id": "ES-008",
                "parameter_varied": "dropout_rate_pct",
                "baseline_value": 18.0,
                "comparison_value": 22.0,
                "baseline_outcome": 48.0,
                "comparison_outcome": 58.0,
                "delta_pct": 20.8,
                "recommendation": "Worst case adds 10 weeks. Mitigation: patient retention program.",
                "is_preferred": False,
                "analyzed_by": "Dr. Maria Lopez",
                "analysis_date": now - timedelta(days=140),
                "notes": "Dropout rate sensitivity most impactful scenario variable.",
                "created_at": now - timedelta(days=140),
            },
            {
                "id": "SC-005",
                "trial_id": LIBTAYO_TRIAL,
                "comparison_name": "LIBTAYO Pre vs Post Arm-Drop",
                "scenario_type": ScenarioType.BASELINE,
                "baseline_simulation_id": "ES-005",
                "comparison_simulation_id": "ES-006",
                "parameter_varied": "target_enrollment",
                "baseline_value": 400.0,
                "comparison_value": 340.0,
                "baseline_outcome": 56.0,
                "comparison_outcome": 44.0,
                "delta_pct": -21.4,
                "recommendation": "Arm drop saves 12 weeks and $18M. Clear benefit.",
                "is_preferred": True,
                "analyzed_by": "Dr. Angela Park",
                "analysis_date": now - timedelta(days=115),
                "notes": "Arm drop was operationally beneficial.",
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "SC-006",
                "trial_id": LIBTAYO_TRIAL,
                "comparison_name": "LIBTAYO Screening Rate Impact",
                "scenario_type": ScenarioType.CUSTOM,
                "baseline_simulation_id": "ES-005",
                "comparison_simulation_id": None,
                "parameter_varied": "screening_failure_rate_pct",
                "baseline_value": 30.0,
                "comparison_value": 20.0,
                "baseline_outcome": 56.0,
                "comparison_outcome": 46.0,
                "delta_pct": -17.9,
                "recommendation": "Improving screening by 10pp saves 10 weeks. Invest in pre-screening.",
                "is_preferred": True,
                "analyzed_by": "Dr. Angela Park",
                "analysis_date": now - timedelta(days=190),
                "notes": "Pre-screening protocol could dramatically improve timelines.",
                "created_at": now - timedelta(days=190),
            },
            {
                "id": "SC-007",
                "trial_id": EYLEA_TRIAL,
                "comparison_name": "EYLEA Resource Comparison: Baseline vs Close-Out",
                "scenario_type": ScenarioType.BASELINE,
                "baseline_simulation_id": None,
                "comparison_simulation_id": None,
                "parameter_varied": "monthly_burn_rate",
                "baseline_value": 1875000.0,
                "comparison_value": 1333333.0,
                "baseline_outcome": 45000000.0,
                "comparison_outcome": 8000000.0,
                "delta_pct": -82.2,
                "recommendation": "Close-out costs significantly reduced. Savings of $37M.",
                "is_preferred": True,
                "analyzed_by": "Dr. Sarah Chen",
                "analysis_date": now - timedelta(days=18),
                "notes": "Early stopping yielded substantial cost savings.",
                "created_at": now - timedelta(days=18),
            },
            {
                "id": "SC-008",
                "trial_id": DUPIXENT_TRIAL,
                "comparison_name": "DUPIXENT Power: MC vs Bayesian",
                "scenario_type": ScenarioType.CUSTOM,
                "baseline_simulation_id": None,
                "comparison_simulation_id": None,
                "parameter_varied": "simulated_power",
                "baseline_value": 0.78,
                "comparison_value": 0.91,
                "baseline_outcome": 0.72,
                "comparison_outcome": 0.86,
                "delta_pct": 19.4,
                "recommendation": "Bayesian model yields higher probability of success. Consider adaptive design.",
                "is_preferred": True,
                "analyzed_by": "Dr. Robert Kim",
                "analysis_date": now - timedelta(days=82),
                "notes": "Comparing Monte Carlo vs Bayesian outcome models.",
                "created_at": now - timedelta(days=82),
            },
            {
                "id": "SC-009",
                "trial_id": LIBTAYO_TRIAL,
                "comparison_name": "LIBTAYO Mono vs Combination Power",
                "scenario_type": ScenarioType.BEST_CASE,
                "baseline_simulation_id": None,
                "comparison_simulation_id": None,
                "parameter_varied": "assumed_effect_size",
                "baseline_value": 0.35,
                "comparison_value": 0.40,
                "baseline_outcome": 0.88,
                "comparison_outcome": 0.94,
                "delta_pct": 6.8,
                "recommendation": "Combination arm expected to have higher power. Supports arm addition.",
                "is_preferred": True,
                "analyzed_by": "Dr. Angela Park",
                "analysis_date": now - timedelta(days=7),
                "notes": "Best-case scenario supports combination arm proposal.",
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "SC-010",
                "trial_id": LIBTAYO_TRIAL,
                "comparison_name": "LIBTAYO Site Count Sensitivity",
                "scenario_type": ScenarioType.CUSTOM,
                "baseline_simulation_id": "ES-006",
                "comparison_simulation_id": None,
                "parameter_varied": "num_sites",
                "baseline_value": 95.0,
                "comparison_value": 110.0,
                "baseline_outcome": 44.0,
                "comparison_outcome": 38.0,
                "delta_pct": -13.6,
                "recommendation": "Adding 15 sites reduces time by 6 weeks. Evaluate activation capacity.",
                "is_preferred": False,
                "analyzed_by": "Dr. Angela Park",
                "analysis_date": now - timedelta(days=50),
                "notes": "Site expansion feasibility under review.",
                "created_at": now - timedelta(days=50),
            },
        ]

        for s in scenario_data:
            self._scenario_comparisons[s["id"]] = ScenarioComparison(**s)

        # --- 10 Sensitivity Analyses ---
        sensitivity_data = [
            {
                "id": "SA-001",
                "trial_id": EYLEA_TRIAL,
                "analysis_name": "EYLEA Enrollment Rate Sensitivity",
                "simulation_id": "ES-001",
                "parameter_type": ParameterType.ENROLLMENT_RATE,
                "parameter_name": "enrollment_rate_per_site_month",
                "base_value": 1.8,
                "min_value": 1.0,
                "max_value": 3.0,
                "step_count": 10,
                "results": [
                    {"value": 1.0, "outcome": 68.0},
                    {"value": 1.4, "outcome": 52.0},
                    {"value": 1.8, "outcome": 42.5},
                    {"value": 2.2, "outcome": 36.0},
                    {"value": 3.0, "outcome": 28.0},
                ],
                "most_sensitive_parameter": "enrollment_rate_per_site_month",
                "tornado_rank": 1,
                "impact_on_outcome_pct": 60.0,
                "analyzed_by": "Dr. Sarah Chen",
                "analysis_date": now - timedelta(days=175),
                "notes": "Enrollment rate is the most impactful parameter.",
                "created_at": now - timedelta(days=175),
            },
            {
                "id": "SA-002",
                "trial_id": EYLEA_TRIAL,
                "analysis_name": "EYLEA Dropout Rate Sensitivity",
                "simulation_id": "ES-001",
                "parameter_type": ParameterType.DROPOUT_RATE,
                "parameter_name": "dropout_rate_pct",
                "base_value": 12.0,
                "min_value": 5.0,
                "max_value": 25.0,
                "step_count": 10,
                "results": [
                    {"value": 5.0, "outcome": 38.0},
                    {"value": 12.0, "outcome": 42.5},
                    {"value": 18.0, "outcome": 48.0},
                    {"value": 25.0, "outcome": 56.0},
                ],
                "most_sensitive_parameter": "dropout_rate_pct",
                "tornado_rank": 2,
                "impact_on_outcome_pct": 42.0,
                "analyzed_by": "Dr. Sarah Chen",
                "analysis_date": now - timedelta(days=175),
                "notes": "Dropout rate second most impactful. Mitigation strategies needed.",
                "created_at": now - timedelta(days=175),
            },
            {
                "id": "SA-003",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_name": "DUPIXENT Event Rate Sensitivity",
                "simulation_id": "ES-003",
                "parameter_type": ParameterType.EVENT_RATE,
                "parameter_name": "response_rate",
                "base_value": 0.45,
                "min_value": 0.30,
                "max_value": 0.60,
                "step_count": 10,
                "results": [
                    {"value": 0.30, "outcome": 0.55},
                    {"value": 0.40, "outcome": 0.70},
                    {"value": 0.45, "outcome": 0.78},
                    {"value": 0.55, "outcome": 0.92},
                    {"value": 0.60, "outcome": 0.96},
                ],
                "most_sensitive_parameter": "response_rate",
                "tornado_rank": 1,
                "impact_on_outcome_pct": 74.5,
                "analyzed_by": "Dr. Maria Lopez",
                "analysis_date": now - timedelta(days=145),
                "notes": "Treatment response rate dominates power outcome.",
                "created_at": now - timedelta(days=145),
            },
            {
                "id": "SA-004",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_name": "DUPIXENT Treatment Effect Sensitivity",
                "simulation_id": "ES-003",
                "parameter_type": ParameterType.TREATMENT_EFFECT,
                "parameter_name": "assumed_effect_size",
                "base_value": 0.30,
                "min_value": 0.15,
                "max_value": 0.45,
                "step_count": 10,
                "results": [
                    {"value": 0.15, "outcome": 0.40},
                    {"value": 0.22, "outcome": 0.58},
                    {"value": 0.30, "outcome": 0.78},
                    {"value": 0.38, "outcome": 0.90},
                    {"value": 0.45, "outcome": 0.97},
                ],
                "most_sensitive_parameter": "assumed_effect_size",
                "tornado_rank": 2,
                "impact_on_outcome_pct": 67.5,
                "analyzed_by": "Dr. Maria Lopez",
                "analysis_date": now - timedelta(days=142),
                "notes": "Effect size uncertainty is key risk factor.",
                "created_at": now - timedelta(days=142),
            },
            {
                "id": "SA-005",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_name": "LIBTAYO Cost Per Patient Sensitivity",
                "simulation_id": None,
                "parameter_type": ParameterType.COST_PER_PATIENT,
                "parameter_name": "cost_per_patient",
                "base_value": 300000.0,
                "min_value": 200000.0,
                "max_value": 450000.0,
                "step_count": 10,
                "results": [
                    {"value": 200000.0, "outcome": 80000000.0},
                    {"value": 250000.0, "outcome": 100000000.0},
                    {"value": 300000.0, "outcome": 120000000.0},
                    {"value": 400000.0, "outcome": 160000000.0},
                    {"value": 450000.0, "outcome": 180000000.0},
                ],
                "most_sensitive_parameter": "cost_per_patient",
                "tornado_rank": 1,
                "impact_on_outcome_pct": 125.0,
                "analyzed_by": "Dr. Angela Park",
                "analysis_date": now - timedelta(days=195),
                "notes": "Cost per patient drives total budget more than any other factor.",
                "created_at": now - timedelta(days=195),
            },
            {
                "id": "SA-006",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_name": "LIBTAYO Site Activation Rate Sensitivity",
                "simulation_id": "ES-005",
                "parameter_type": ParameterType.SITE_ACTIVATION_RATE,
                "parameter_name": "site_activation_rate_per_month",
                "base_value": 5.0,
                "min_value": 2.0,
                "max_value": 10.0,
                "step_count": 10,
                "results": [
                    {"value": 2.0, "outcome": 72.0},
                    {"value": 4.0, "outcome": 60.0},
                    {"value": 5.0, "outcome": 56.0},
                    {"value": 8.0, "outcome": 48.0},
                    {"value": 10.0, "outcome": 44.0},
                ],
                "most_sensitive_parameter": "site_activation_rate_per_month",
                "tornado_rank": 3,
                "impact_on_outcome_pct": 50.0,
                "analyzed_by": "Dr. Angela Park",
                "analysis_date": now - timedelta(days=192),
                "notes": "Site activation rate critically impacts early enrollment timeline.",
                "created_at": now - timedelta(days=192),
            },
            {
                "id": "SA-007",
                "trial_id": EYLEA_TRIAL,
                "analysis_name": "EYLEA Screening Failure Sensitivity",
                "simulation_id": "ES-001",
                "parameter_type": ParameterType.DROPOUT_RATE,
                "parameter_name": "screening_failure_rate_pct",
                "base_value": 22.0,
                "min_value": 10.0,
                "max_value": 40.0,
                "step_count": 10,
                "results": [
                    {"value": 10.0, "outcome": 36.0},
                    {"value": 15.0, "outcome": 39.0},
                    {"value": 22.0, "outcome": 42.5},
                    {"value": 30.0, "outcome": 48.0},
                    {"value": 40.0, "outcome": 56.0},
                ],
                "most_sensitive_parameter": "screening_failure_rate_pct",
                "tornado_rank": 3,
                "impact_on_outcome_pct": 47.1,
                "analyzed_by": "Dr. James Wright",
                "analysis_date": now - timedelta(days=172),
                "notes": "Screening failure impacts enrollment but less than rate and dropout.",
                "created_at": now - timedelta(days=172),
            },
            {
                "id": "SA-008",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_name": "DUPIXENT Cost Per Patient Impact",
                "simulation_id": None,
                "parameter_type": ParameterType.COST_PER_PATIENT,
                "parameter_name": "cost_per_patient",
                "base_value": 200000.0,
                "min_value": 150000.0,
                "max_value": 300000.0,
                "step_count": 10,
                "results": [
                    {"value": 150000.0, "outcome": 54000000.0},
                    {"value": 200000.0, "outcome": 72000000.0},
                    {"value": 250000.0, "outcome": 90000000.0},
                    {"value": 300000.0, "outcome": 108000000.0},
                ],
                "most_sensitive_parameter": "cost_per_patient",
                "tornado_rank": 1,
                "impact_on_outcome_pct": 100.0,
                "analyzed_by": "Dr. Robert Kim",
                "analysis_date": now - timedelta(days=72),
                "notes": "Linear cost sensitivity. Budget planning critical.",
                "created_at": now - timedelta(days=72),
            },
            {
                "id": "SA-009",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_name": "LIBTAYO Enrollment Rate Impact on Timeline",
                "simulation_id": "ES-006",
                "parameter_type": ParameterType.ENROLLMENT_RATE,
                "parameter_name": "enrollment_rate_per_site_month",
                "base_value": 1.3,
                "min_value": 0.8,
                "max_value": 2.0,
                "step_count": 10,
                "results": [
                    {"value": 0.8, "outcome": 62.0},
                    {"value": 1.0, "outcome": 52.0},
                    {"value": 1.3, "outcome": 44.0},
                    {"value": 1.6, "outcome": 38.0},
                    {"value": 2.0, "outcome": 32.0},
                ],
                "most_sensitive_parameter": "enrollment_rate_per_site_month",
                "tornado_rank": 1,
                "impact_on_outcome_pct": 68.2,
                "analyzed_by": "Dr. Angela Park",
                "analysis_date": now - timedelta(days=110),
                "notes": "Post arm-drop enrollment rate sensitivity.",
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "SA-010",
                "trial_id": EYLEA_TRIAL,
                "analysis_name": "EYLEA Treatment Effect on Power",
                "simulation_id": None,
                "parameter_type": ParameterType.TREATMENT_EFFECT,
                "parameter_name": "assumed_effect_size",
                "base_value": 0.35,
                "min_value": 0.20,
                "max_value": 0.50,
                "step_count": 10,
                "results": [
                    {"value": 0.20, "outcome": 0.55},
                    {"value": 0.28, "outcome": 0.72},
                    {"value": 0.35, "outcome": 0.87},
                    {"value": 0.42, "outcome": 0.94},
                    {"value": 0.50, "outcome": 0.98},
                ],
                "most_sensitive_parameter": "assumed_effect_size",
                "tornado_rank": 1,
                "impact_on_outcome_pct": 78.2,
                "analyzed_by": "Dr. Sarah Chen",
                "analysis_date": now - timedelta(days=170),
                "notes": "Treatment effect is strongest driver of study power.",
                "created_at": now - timedelta(days=170),
            },
        ]

        for sa in sensitivity_data:
            self._sensitivity_analyses[sa["id"]] = SensitivityAnalysis(**sa)

    # ------------------------------------------------------------------
    # Enrollment Simulations
    # ------------------------------------------------------------------

    def list_enrollment_simulations(
        self,
        *,
        trial_id: str | None = None,
        status: SimulationStatus | None = None,
        model_type: ModelType | None = None,
    ) -> list[EnrollmentSimulation]:
        """List enrollment simulations with optional filters."""
        with self._lock:
            result = list(self._enrollment_simulations.values())

        if trial_id is not None:
            result = [e for e in result if e.trial_id == trial_id]
        if status is not None:
            result = [e for e in result if e.status == status]
        if model_type is not None:
            result = [e for e in result if e.model_type == model_type]

        return sorted(result, key=lambda e: e.created_at, reverse=True)

    def get_enrollment_simulation(self, simulation_id: str) -> EnrollmentSimulation | None:
        """Get a single enrollment simulation by ID."""
        with self._lock:
            return self._enrollment_simulations.get(simulation_id)

    def create_enrollment_simulation(self, payload: EnrollmentSimulationCreate) -> EnrollmentSimulation:
        """Create a new enrollment simulation."""
        now = datetime.now(timezone.utc)
        sim_id = f"ES-{uuid4().hex[:8].upper()}"
        sim = EnrollmentSimulation(
            id=sim_id,
            trial_id=payload.trial_id,
            simulation_name=payload.simulation_name,
            simulation_type=SimulationType.ENROLLMENT,
            status=SimulationStatus.CONFIGURED,
            model_type=payload.model_type,
            num_iterations=payload.num_iterations,
            target_enrollment=payload.target_enrollment,
            num_sites=0,
            enrollment_rate_per_site_month=0.0,
            screening_failure_rate_pct=20.0,
            dropout_rate_pct=15.0,
            median_time_to_target_weeks=None,
            p10_time_weeks=None,
            p90_time_weeks=None,
            probability_on_time=None,
            run_date=None,
            run_duration_seconds=None,
            created_by=payload.created_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._enrollment_simulations[sim_id] = sim
        logger.info("Created enrollment simulation %s for trial %s", sim_id, payload.trial_id)
        return sim

    def update_enrollment_simulation(
        self, simulation_id: str, payload: EnrollmentSimulationUpdate
    ) -> EnrollmentSimulation | None:
        """Update an existing enrollment simulation."""
        with self._lock:
            existing = self._enrollment_simulations.get(simulation_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = EnrollmentSimulation(**data)
            self._enrollment_simulations[simulation_id] = updated
        return updated

    def delete_enrollment_simulation(self, simulation_id: str) -> bool:
        """Delete an enrollment simulation. Returns True if deleted."""
        with self._lock:
            if simulation_id in self._enrollment_simulations:
                del self._enrollment_simulations[simulation_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Outcome Models
    # ------------------------------------------------------------------

    def list_outcome_models(
        self,
        *,
        trial_id: str | None = None,
        status: SimulationStatus | None = None,
        model_type: ModelType | None = None,
    ) -> list[OutcomeModel]:
        """List outcome models with optional filters."""
        with self._lock:
            result = list(self._outcome_models.values())

        if trial_id is not None:
            result = [o for o in result if o.trial_id == trial_id]
        if status is not None:
            result = [o for o in result if o.status == status]
        if model_type is not None:
            result = [o for o in result if o.model_type == model_type]

        return sorted(result, key=lambda o: o.created_at, reverse=True)

    def get_outcome_model(self, model_id: str) -> OutcomeModel | None:
        """Get a single outcome model by ID."""
        with self._lock:
            return self._outcome_models.get(model_id)

    def create_outcome_model(self, payload: OutcomeModelCreate) -> OutcomeModel:
        """Create a new outcome model."""
        now = datetime.now(timezone.utc)
        model_id = f"OM-{uuid4().hex[:8].upper()}"
        model = OutcomeModel(
            id=model_id,
            trial_id=payload.trial_id,
            model_name=payload.model_name,
            model_type=payload.model_type,
            status=SimulationStatus.CONFIGURED,
            primary_endpoint=payload.primary_endpoint,
            assumed_effect_size=None,
            assumed_control_rate=None,
            assumed_treatment_rate=None,
            sample_size=payload.sample_size,
            power=0.80,
            alpha=0.05,
            num_iterations=10000,
            simulated_power=None,
            probability_success=None,
            expected_effect_ci_lower=None,
            expected_effect_ci_upper=None,
            run_date=None,
            created_by=payload.created_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._outcome_models[model_id] = model
        logger.info("Created outcome model %s for trial %s", model_id, payload.trial_id)
        return model

    def update_outcome_model(
        self, model_id: str, payload: OutcomeModelUpdate
    ) -> OutcomeModel | None:
        """Update an existing outcome model."""
        with self._lock:
            existing = self._outcome_models.get(model_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = OutcomeModel(**data)
            self._outcome_models[model_id] = updated
        return updated

    def delete_outcome_model(self, model_id: str) -> bool:
        """Delete an outcome model. Returns True if deleted."""
        with self._lock:
            if model_id in self._outcome_models:
                del self._outcome_models[model_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Resource Forecasts
    # ------------------------------------------------------------------

    def list_resource_forecasts(
        self,
        *,
        trial_id: str | None = None,
        status: SimulationStatus | None = None,
    ) -> list[ResourceForecast]:
        """List resource forecasts with optional filters."""
        with self._lock:
            result = list(self._resource_forecasts.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if status is not None:
            result = [r for r in result if r.status == status]

        return sorted(result, key=lambda r: r.created_at, reverse=True)

    def get_resource_forecast(self, forecast_id: str) -> ResourceForecast | None:
        """Get a single resource forecast by ID."""
        with self._lock:
            return self._resource_forecasts.get(forecast_id)

    def create_resource_forecast(self, payload: ResourceForecastCreate) -> ResourceForecast:
        """Create a new resource forecast."""
        now = datetime.now(timezone.utc)
        forecast_id = f"RF-{uuid4().hex[:8].upper()}"
        forecast = ResourceForecast(
            id=forecast_id,
            trial_id=payload.trial_id,
            forecast_name=payload.forecast_name,
            status=SimulationStatus.CONFIGURED,
            forecast_horizon_months=payload.forecast_horizon_months,
            total_sites_planned=payload.total_sites_planned,
            cra_fte_required=0.0,
            data_manager_fte=0.0,
            medical_monitor_fte=0.0,
            total_cost_estimate=0.0,
            cost_per_patient=0.0,
            monthly_burn_rate=0.0,
            peak_enrollment_month=None,
            peak_resource_month=None,
            run_date=None,
            created_by=payload.created_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._resource_forecasts[forecast_id] = forecast
        logger.info("Created resource forecast %s for trial %s", forecast_id, payload.trial_id)
        return forecast

    def update_resource_forecast(
        self, forecast_id: str, payload: ResourceForecastUpdate
    ) -> ResourceForecast | None:
        """Update an existing resource forecast."""
        with self._lock:
            existing = self._resource_forecasts.get(forecast_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ResourceForecast(**data)
            self._resource_forecasts[forecast_id] = updated
        return updated

    def delete_resource_forecast(self, forecast_id: str) -> bool:
        """Delete a resource forecast. Returns True if deleted."""
        with self._lock:
            if forecast_id in self._resource_forecasts:
                del self._resource_forecasts[forecast_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Scenario Comparisons
    # ------------------------------------------------------------------

    def list_scenario_comparisons(
        self,
        *,
        trial_id: str | None = None,
        scenario_type: ScenarioType | None = None,
    ) -> list[ScenarioComparison]:
        """List scenario comparisons with optional filters."""
        with self._lock:
            result = list(self._scenario_comparisons.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if scenario_type is not None:
            result = [s for s in result if s.scenario_type == scenario_type]

        return sorted(result, key=lambda s: s.analysis_date, reverse=True)

    def get_scenario_comparison(self, comparison_id: str) -> ScenarioComparison | None:
        """Get a single scenario comparison by ID."""
        with self._lock:
            return self._scenario_comparisons.get(comparison_id)

    def create_scenario_comparison(self, payload: ScenarioComparisonCreate) -> ScenarioComparison:
        """Create a new scenario comparison."""
        now = datetime.now(timezone.utc)
        comparison_id = f"SC-{uuid4().hex[:8].upper()}"
        comparison = ScenarioComparison(
            id=comparison_id,
            trial_id=payload.trial_id,
            comparison_name=payload.comparison_name,
            scenario_type=payload.scenario_type,
            baseline_simulation_id=payload.baseline_simulation_id,
            comparison_simulation_id=None,
            parameter_varied=payload.parameter_varied,
            baseline_value=None,
            comparison_value=None,
            baseline_outcome=None,
            comparison_outcome=None,
            delta_pct=None,
            recommendation=None,
            is_preferred=False,
            analyzed_by=payload.analyzed_by,
            analysis_date=now,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._scenario_comparisons[comparison_id] = comparison
        logger.info("Created scenario comparison %s for trial %s", comparison_id, payload.trial_id)
        return comparison

    def update_scenario_comparison(
        self, comparison_id: str, payload: ScenarioComparisonUpdate
    ) -> ScenarioComparison | None:
        """Update an existing scenario comparison."""
        with self._lock:
            existing = self._scenario_comparisons.get(comparison_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ScenarioComparison(**data)
            self._scenario_comparisons[comparison_id] = updated
        return updated

    def delete_scenario_comparison(self, comparison_id: str) -> bool:
        """Delete a scenario comparison. Returns True if deleted."""
        with self._lock:
            if comparison_id in self._scenario_comparisons:
                del self._scenario_comparisons[comparison_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Sensitivity Analyses
    # ------------------------------------------------------------------

    def list_sensitivity_analyses(
        self,
        *,
        trial_id: str | None = None,
        parameter_type: ParameterType | None = None,
    ) -> list[SensitivityAnalysis]:
        """List sensitivity analyses with optional filters."""
        with self._lock:
            result = list(self._sensitivity_analyses.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if parameter_type is not None:
            result = [s for s in result if s.parameter_type == parameter_type]

        return sorted(result, key=lambda s: s.analysis_date, reverse=True)

    def get_sensitivity_analysis(self, analysis_id: str) -> SensitivityAnalysis | None:
        """Get a single sensitivity analysis by ID."""
        with self._lock:
            return self._sensitivity_analyses.get(analysis_id)

    def create_sensitivity_analysis(self, payload: SensitivityAnalysisCreate) -> SensitivityAnalysis:
        """Create a new sensitivity analysis."""
        now = datetime.now(timezone.utc)
        analysis_id = f"SA-{uuid4().hex[:8].upper()}"
        analysis = SensitivityAnalysis(
            id=analysis_id,
            trial_id=payload.trial_id,
            analysis_name=payload.analysis_name,
            simulation_id=payload.simulation_id,
            parameter_type=payload.parameter_type,
            parameter_name=payload.parameter_name,
            base_value=payload.base_value,
            min_value=payload.min_value,
            max_value=payload.max_value,
            step_count=10,
            results=[],
            most_sensitive_parameter=None,
            tornado_rank=None,
            impact_on_outcome_pct=None,
            analyzed_by=payload.analyzed_by,
            analysis_date=now,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._sensitivity_analyses[analysis_id] = analysis
        logger.info("Created sensitivity analysis %s for trial %s", analysis_id, payload.trial_id)
        return analysis

    def update_sensitivity_analysis(
        self, analysis_id: str, payload: SensitivityAnalysisUpdate
    ) -> SensitivityAnalysis | None:
        """Update an existing sensitivity analysis."""
        with self._lock:
            existing = self._sensitivity_analyses.get(analysis_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SensitivityAnalysis(**data)
            self._sensitivity_analyses[analysis_id] = updated
        return updated

    def delete_sensitivity_analysis(self, analysis_id: str) -> bool:
        """Delete a sensitivity analysis. Returns True if deleted."""
        with self._lock:
            if analysis_id in self._sensitivity_analyses:
                del self._sensitivity_analyses[analysis_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> ClinicalSimulationMetrics:
        """Compute aggregated clinical simulation metrics."""
        with self._lock:
            enrollments = list(self._enrollment_simulations.values())
            outcomes = list(self._outcome_models.values())
            resources = list(self._resource_forecasts.values())
            scenarios = list(self._scenario_comparisons.values())
            sensitivities = list(self._sensitivity_analyses.values())

        # Sims by status
        sims_by_status: dict[str, int] = {}
        for e in enrollments:
            key = e.status.value
            sims_by_status[key] = sims_by_status.get(key, 0) + 1

        # Sims by model type
        sims_by_model: dict[str, int] = {}
        for e in enrollments:
            key = e.model_type.value
            sims_by_model[key] = sims_by_model.get(key, 0) + 1

        # Average simulated power (from completed outcome models)
        powers = [o.simulated_power for o in outcomes if o.simulated_power is not None]
        avg_power = round(sum(powers) / max(1, len(powers)), 4) if powers else 0.0

        # Total forecast cost
        total_forecast_cost = sum(r.total_cost_estimate for r in resources)

        # Scenarios by type
        scenarios_by_type: dict[str, int] = {}
        for s in scenarios:
            key = s.scenario_type.value
            scenarios_by_type[key] = scenarios_by_type.get(key, 0) + 1

        # Analyses by parameter type
        analyses_by_parameter: dict[str, int] = {}
        for sa in sensitivities:
            key = sa.parameter_type.value
            analyses_by_parameter[key] = analyses_by_parameter.get(key, 0) + 1

        return ClinicalSimulationMetrics(
            total_enrollment_sims=len(enrollments),
            sims_by_status=sims_by_status,
            sims_by_model=sims_by_model,
            total_outcome_models=len(outcomes),
            avg_simulated_power=avg_power,
            total_resource_forecasts=len(resources),
            total_forecast_cost=total_forecast_cost,
            total_scenario_comparisons=len(scenarios),
            scenarios_by_type=scenarios_by_type,
            total_sensitivity_analyses=len(sensitivities),
            analyses_by_parameter=analyses_by_parameter,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ClinicalSimulationService | None = None
_instance_lock = threading.Lock()


def get_clinical_simulation_service() -> ClinicalSimulationService:
    """Return the singleton ClinicalSimulationService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ClinicalSimulationService()
    return _instance


def reset_clinical_simulation_service() -> ClinicalSimulationService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = ClinicalSimulationService()
    return _instance
