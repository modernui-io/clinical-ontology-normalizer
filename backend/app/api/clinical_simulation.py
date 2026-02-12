"""Clinical Trial Simulation API endpoints (SIM-TRIAL).

Provides comprehensive clinical trial simulation operations: enrollment
simulations, outcome modeling, resource forecasting, scenario comparison,
sensitivity analysis, and simulation metrics.

Endpoints:
    GET    /clinical-simulation/enrollment-simulations                    - List enrollment simulations
    GET    /clinical-simulation/enrollment-simulations/{simulation_id}    - Get single simulation
    POST   /clinical-simulation/enrollment-simulations                    - Create simulation
    PUT    /clinical-simulation/enrollment-simulations/{simulation_id}    - Update simulation
    DELETE /clinical-simulation/enrollment-simulations/{simulation_id}    - Delete simulation
    GET    /clinical-simulation/outcome-models                            - List outcome models
    GET    /clinical-simulation/outcome-models/{model_id}                 - Get single model
    POST   /clinical-simulation/outcome-models                            - Create model
    PUT    /clinical-simulation/outcome-models/{model_id}                 - Update model
    DELETE /clinical-simulation/outcome-models/{model_id}                 - Delete model
    GET    /clinical-simulation/resource-forecasts                        - List resource forecasts
    GET    /clinical-simulation/resource-forecasts/{forecast_id}          - Get single forecast
    POST   /clinical-simulation/resource-forecasts                        - Create forecast
    PUT    /clinical-simulation/resource-forecasts/{forecast_id}          - Update forecast
    DELETE /clinical-simulation/resource-forecasts/{forecast_id}          - Delete forecast
    GET    /clinical-simulation/scenario-comparisons                      - List scenario comparisons
    GET    /clinical-simulation/scenario-comparisons/{comparison_id}      - Get single comparison
    POST   /clinical-simulation/scenario-comparisons                      - Create comparison
    PUT    /clinical-simulation/scenario-comparisons/{comparison_id}      - Update comparison
    DELETE /clinical-simulation/scenario-comparisons/{comparison_id}      - Delete comparison
    GET    /clinical-simulation/sensitivity-analyses                      - List sensitivity analyses
    GET    /clinical-simulation/sensitivity-analyses/{analysis_id}        - Get single analysis
    POST   /clinical-simulation/sensitivity-analyses                      - Create analysis
    PUT    /clinical-simulation/sensitivity-analyses/{analysis_id}        - Update analysis
    DELETE /clinical-simulation/sensitivity-analyses/{analysis_id}        - Delete analysis
    GET    /clinical-simulation/metrics                                   - Simulation metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.clinical_simulation import (
    ClinicalSimulationMetrics,
    EnrollmentSimulation,
    EnrollmentSimulationCreate,
    EnrollmentSimulationListResponse,
    EnrollmentSimulationUpdate,
    ModelType,
    OutcomeModel,
    OutcomeModelCreate,
    OutcomeModelListResponse,
    OutcomeModelUpdate,
    ParameterType,
    ResourceForecast,
    ResourceForecastCreate,
    ResourceForecastListResponse,
    ResourceForecastUpdate,
    ScenarioComparison,
    ScenarioComparisonCreate,
    ScenarioComparisonListResponse,
    ScenarioComparisonUpdate,
    ScenarioType,
    SensitivityAnalysis,
    SensitivityAnalysisCreate,
    SensitivityAnalysisListResponse,
    SensitivityAnalysisUpdate,
    SimulationStatus,
)
from app.services.clinical_simulation_service import get_clinical_simulation_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/clinical-simulation",
    tags=["Clinical Simulation"],
)


# ---------------------------------------------------------------------------
# Enrollment Simulations
# ---------------------------------------------------------------------------


@router.get(
    "/enrollment-simulations",
    response_model=EnrollmentSimulationListResponse,
    summary="List enrollment simulations",
    description="Retrieve enrollment simulations with optional filtering by trial, status, and model type.",
)
async def list_enrollment_simulations(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[SimulationStatus] = Query(None, description="Filter by status"),
    model_type: Optional[ModelType] = Query(None, description="Filter by model type"),
) -> EnrollmentSimulationListResponse:
    svc = get_clinical_simulation_service()
    items = svc.list_enrollment_simulations(
        trial_id=trial_id, status=status, model_type=model_type
    )
    return EnrollmentSimulationListResponse(items=items, total=len(items))


@router.get(
    "/enrollment-simulations/{simulation_id}",
    response_model=EnrollmentSimulation,
    summary="Get an enrollment simulation",
)
async def get_enrollment_simulation(simulation_id: str) -> EnrollmentSimulation:
    svc = get_clinical_simulation_service()
    sim = svc.get_enrollment_simulation(simulation_id)
    if sim is None:
        raise HTTPException(
            status_code=404, detail=f"Enrollment simulation '{simulation_id}' not found"
        )
    return sim


@router.post(
    "/enrollment-simulations",
    response_model=EnrollmentSimulation,
    status_code=201,
    summary="Create an enrollment simulation",
)
async def create_enrollment_simulation(payload: EnrollmentSimulationCreate) -> EnrollmentSimulation:
    svc = get_clinical_simulation_service()
    return svc.create_enrollment_simulation(payload)


@router.put(
    "/enrollment-simulations/{simulation_id}",
    response_model=EnrollmentSimulation,
    summary="Update an enrollment simulation",
)
async def update_enrollment_simulation(
    simulation_id: str, payload: EnrollmentSimulationUpdate
) -> EnrollmentSimulation:
    svc = get_clinical_simulation_service()
    updated = svc.update_enrollment_simulation(simulation_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Enrollment simulation '{simulation_id}' not found"
        )
    return updated


@router.delete(
    "/enrollment-simulations/{simulation_id}",
    status_code=204,
    summary="Delete an enrollment simulation",
)
async def delete_enrollment_simulation(simulation_id: str) -> None:
    svc = get_clinical_simulation_service()
    deleted = svc.delete_enrollment_simulation(simulation_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Enrollment simulation '{simulation_id}' not found"
        )


# ---------------------------------------------------------------------------
# Outcome Models
# ---------------------------------------------------------------------------


@router.get(
    "/outcome-models",
    response_model=OutcomeModelListResponse,
    summary="List outcome models",
    description="Retrieve outcome models with optional filtering by trial, status, and model type.",
)
async def list_outcome_models(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[SimulationStatus] = Query(None, description="Filter by status"),
    model_type: Optional[ModelType] = Query(None, description="Filter by model type"),
) -> OutcomeModelListResponse:
    svc = get_clinical_simulation_service()
    items = svc.list_outcome_models(
        trial_id=trial_id, status=status, model_type=model_type
    )
    return OutcomeModelListResponse(items=items, total=len(items))


@router.get(
    "/outcome-models/{model_id}",
    response_model=OutcomeModel,
    summary="Get an outcome model",
)
async def get_outcome_model(model_id: str) -> OutcomeModel:
    svc = get_clinical_simulation_service()
    model = svc.get_outcome_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Outcome model '{model_id}' not found")
    return model


@router.post(
    "/outcome-models",
    response_model=OutcomeModel,
    status_code=201,
    summary="Create an outcome model",
)
async def create_outcome_model(payload: OutcomeModelCreate) -> OutcomeModel:
    svc = get_clinical_simulation_service()
    return svc.create_outcome_model(payload)


@router.put(
    "/outcome-models/{model_id}",
    response_model=OutcomeModel,
    summary="Update an outcome model",
)
async def update_outcome_model(
    model_id: str, payload: OutcomeModelUpdate
) -> OutcomeModel:
    svc = get_clinical_simulation_service()
    updated = svc.update_outcome_model(model_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Outcome model '{model_id}' not found")
    return updated


@router.delete(
    "/outcome-models/{model_id}",
    status_code=204,
    summary="Delete an outcome model",
)
async def delete_outcome_model(model_id: str) -> None:
    svc = get_clinical_simulation_service()
    deleted = svc.delete_outcome_model(model_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Outcome model '{model_id}' not found")


# ---------------------------------------------------------------------------
# Resource Forecasts
# ---------------------------------------------------------------------------


@router.get(
    "/resource-forecasts",
    response_model=ResourceForecastListResponse,
    summary="List resource forecasts",
    description="Retrieve resource forecasts with optional filtering by trial and status.",
)
async def list_resource_forecasts(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[SimulationStatus] = Query(None, description="Filter by status"),
) -> ResourceForecastListResponse:
    svc = get_clinical_simulation_service()
    items = svc.list_resource_forecasts(trial_id=trial_id, status=status)
    return ResourceForecastListResponse(items=items, total=len(items))


@router.get(
    "/resource-forecasts/{forecast_id}",
    response_model=ResourceForecast,
    summary="Get a resource forecast",
)
async def get_resource_forecast(forecast_id: str) -> ResourceForecast:
    svc = get_clinical_simulation_service()
    forecast = svc.get_resource_forecast(forecast_id)
    if forecast is None:
        raise HTTPException(
            status_code=404, detail=f"Resource forecast '{forecast_id}' not found"
        )
    return forecast


@router.post(
    "/resource-forecasts",
    response_model=ResourceForecast,
    status_code=201,
    summary="Create a resource forecast",
)
async def create_resource_forecast(payload: ResourceForecastCreate) -> ResourceForecast:
    svc = get_clinical_simulation_service()
    return svc.create_resource_forecast(payload)


@router.put(
    "/resource-forecasts/{forecast_id}",
    response_model=ResourceForecast,
    summary="Update a resource forecast",
)
async def update_resource_forecast(
    forecast_id: str, payload: ResourceForecastUpdate
) -> ResourceForecast:
    svc = get_clinical_simulation_service()
    updated = svc.update_resource_forecast(forecast_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Resource forecast '{forecast_id}' not found"
        )
    return updated


@router.delete(
    "/resource-forecasts/{forecast_id}",
    status_code=204,
    summary="Delete a resource forecast",
)
async def delete_resource_forecast(forecast_id: str) -> None:
    svc = get_clinical_simulation_service()
    deleted = svc.delete_resource_forecast(forecast_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Resource forecast '{forecast_id}' not found"
        )


# ---------------------------------------------------------------------------
# Scenario Comparisons
# ---------------------------------------------------------------------------


@router.get(
    "/scenario-comparisons",
    response_model=ScenarioComparisonListResponse,
    summary="List scenario comparisons",
    description="Retrieve scenario comparisons with optional filtering by trial and scenario type.",
)
async def list_scenario_comparisons(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    scenario_type: Optional[ScenarioType] = Query(None, description="Filter by scenario type"),
) -> ScenarioComparisonListResponse:
    svc = get_clinical_simulation_service()
    items = svc.list_scenario_comparisons(
        trial_id=trial_id, scenario_type=scenario_type
    )
    return ScenarioComparisonListResponse(items=items, total=len(items))


@router.get(
    "/scenario-comparisons/{comparison_id}",
    response_model=ScenarioComparison,
    summary="Get a scenario comparison",
)
async def get_scenario_comparison(comparison_id: str) -> ScenarioComparison:
    svc = get_clinical_simulation_service()
    comparison = svc.get_scenario_comparison(comparison_id)
    if comparison is None:
        raise HTTPException(
            status_code=404, detail=f"Scenario comparison '{comparison_id}' not found"
        )
    return comparison


@router.post(
    "/scenario-comparisons",
    response_model=ScenarioComparison,
    status_code=201,
    summary="Create a scenario comparison",
)
async def create_scenario_comparison(payload: ScenarioComparisonCreate) -> ScenarioComparison:
    svc = get_clinical_simulation_service()
    return svc.create_scenario_comparison(payload)


@router.put(
    "/scenario-comparisons/{comparison_id}",
    response_model=ScenarioComparison,
    summary="Update a scenario comparison",
)
async def update_scenario_comparison(
    comparison_id: str, payload: ScenarioComparisonUpdate
) -> ScenarioComparison:
    svc = get_clinical_simulation_service()
    updated = svc.update_scenario_comparison(comparison_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Scenario comparison '{comparison_id}' not found"
        )
    return updated


@router.delete(
    "/scenario-comparisons/{comparison_id}",
    status_code=204,
    summary="Delete a scenario comparison",
)
async def delete_scenario_comparison(comparison_id: str) -> None:
    svc = get_clinical_simulation_service()
    deleted = svc.delete_scenario_comparison(comparison_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Scenario comparison '{comparison_id}' not found"
        )


# ---------------------------------------------------------------------------
# Sensitivity Analyses
# ---------------------------------------------------------------------------


@router.get(
    "/sensitivity-analyses",
    response_model=SensitivityAnalysisListResponse,
    summary="List sensitivity analyses",
    description="Retrieve sensitivity analyses with optional filtering by trial and parameter type.",
)
async def list_sensitivity_analyses(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    parameter_type: Optional[ParameterType] = Query(None, description="Filter by parameter type"),
) -> SensitivityAnalysisListResponse:
    svc = get_clinical_simulation_service()
    items = svc.list_sensitivity_analyses(
        trial_id=trial_id, parameter_type=parameter_type
    )
    return SensitivityAnalysisListResponse(items=items, total=len(items))


@router.get(
    "/sensitivity-analyses/{analysis_id}",
    response_model=SensitivityAnalysis,
    summary="Get a sensitivity analysis",
)
async def get_sensitivity_analysis(analysis_id: str) -> SensitivityAnalysis:
    svc = get_clinical_simulation_service()
    analysis = svc.get_sensitivity_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(
            status_code=404, detail=f"Sensitivity analysis '{analysis_id}' not found"
        )
    return analysis


@router.post(
    "/sensitivity-analyses",
    response_model=SensitivityAnalysis,
    status_code=201,
    summary="Create a sensitivity analysis",
)
async def create_sensitivity_analysis(payload: SensitivityAnalysisCreate) -> SensitivityAnalysis:
    svc = get_clinical_simulation_service()
    return svc.create_sensitivity_analysis(payload)


@router.put(
    "/sensitivity-analyses/{analysis_id}",
    response_model=SensitivityAnalysis,
    summary="Update a sensitivity analysis",
)
async def update_sensitivity_analysis(
    analysis_id: str, payload: SensitivityAnalysisUpdate
) -> SensitivityAnalysis:
    svc = get_clinical_simulation_service()
    updated = svc.update_sensitivity_analysis(analysis_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Sensitivity analysis '{analysis_id}' not found"
        )
    return updated


@router.delete(
    "/sensitivity-analyses/{analysis_id}",
    status_code=204,
    summary="Delete a sensitivity analysis",
)
async def delete_sensitivity_analysis(analysis_id: str) -> None:
    svc = get_clinical_simulation_service()
    deleted = svc.delete_sensitivity_analysis(analysis_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Sensitivity analysis '{analysis_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=ClinicalSimulationMetrics,
    summary="Get clinical simulation metrics",
    description="Aggregated metrics across all clinical trial simulation operations.",
)
async def get_metrics() -> ClinicalSimulationMetrics:
    svc = get_clinical_simulation_service()
    return svc.get_metrics()
