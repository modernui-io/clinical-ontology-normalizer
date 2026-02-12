"""Tests for Clinical Trial Simulation (SIM-TRIAL).

Covers:
- Seed data verification (enrollment sims, outcome models, resource forecasts,
  scenario comparisons, sensitivity analyses)
- Enrollment simulation CRUD (create, read, update, delete, list, filter by trial/status/model)
- Outcome model CRUD (create, read, update, delete, list, filter by trial/status/model)
- Resource forecast CRUD (create, read, update, delete, list, filter by trial/status)
- Scenario comparison CRUD (create, read, update, delete, list, filter by trial/type)
- Sensitivity analysis CRUD (create, read, update, delete, list, filter by trial/parameter)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.clinical_simulation import (
    ModelType,
    ParameterType,
    ScenarioType,
    SimulationStatus,
    SimulationType,
)
from app.services.clinical_simulation_service import (
    ClinicalSimulationService,
    get_clinical_simulation_service,
    reset_clinical_simulation_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/clinical-simulation"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_clinical_simulation_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ClinicalSimulationService:
    """Shorthand for the fresh service."""
    return fresh_service


@pytest.fixture
async def client():
    """Async HTTP client for API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_enrollment_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "simulation_name": "Test Enrollment Simulation",
        "created_by": "Dr. Test Analyst",
        "model_type": "monte_carlo",
        "num_iterations": 5000,
        "target_enrollment": 200,
    }
    defaults.update(overrides)
    return defaults


def _make_outcome_create(**overrides) -> dict:
    defaults = {
        "trial_id": DUPIXENT_TRIAL,
        "model_name": "Test Outcome Model",
        "model_type": "monte_carlo",
        "primary_endpoint": "EASI-75 response at Week 16",
        "created_by": "Dr. Test Statistician",
        "sample_size": 300,
    }
    defaults.update(overrides)
    return defaults


def _make_resource_create(**overrides) -> dict:
    defaults = {
        "trial_id": LIBTAYO_TRIAL,
        "forecast_name": "Test Resource Forecast",
        "created_by": "Dr. Test Planner",
        "forecast_horizon_months": 18,
        "total_sites_planned": 50,
    }
    defaults.update(overrides)
    return defaults


def _make_scenario_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "comparison_name": "Test Scenario Comparison",
        "scenario_type": "optimistic",
        "parameter_varied": "num_sites",
        "analyzed_by": "Dr. Test Analyst",
    }
    defaults.update(overrides)
    return defaults


def _make_sensitivity_create(**overrides) -> dict:
    defaults = {
        "trial_id": DUPIXENT_TRIAL,
        "analysis_name": "Test Sensitivity Analysis",
        "parameter_type": "enrollment_rate",
        "parameter_name": "enrollment_rate_per_site_month",
        "base_value": 1.5,
        "min_value": 0.5,
        "max_value": 3.0,
        "analyzed_by": "Dr. Test Analyst",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_enrollment_simulations_count(self, svc: ClinicalSimulationService):
        sims = svc.list_enrollment_simulations()
        assert len(sims) == 12

    def test_seed_outcome_models_count(self, svc: ClinicalSimulationService):
        models = svc.list_outcome_models()
        assert len(models) == 10

    def test_seed_resource_forecasts_count(self, svc: ClinicalSimulationService):
        forecasts = svc.list_resource_forecasts()
        assert len(forecasts) == 10

    def test_seed_scenario_comparisons_count(self, svc: ClinicalSimulationService):
        comparisons = svc.list_scenario_comparisons()
        assert len(comparisons) == 10

    def test_seed_sensitivity_analyses_count(self, svc: ClinicalSimulationService):
        analyses = svc.list_sensitivity_analyses()
        assert len(analyses) == 10

    def test_seed_enrollment_sims_cover_all_trials(self, svc: ClinicalSimulationService):
        sims = svc.list_enrollment_simulations()
        trial_ids = {s.trial_id for s in sims}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_enrollment_sims_have_multiple_statuses(self, svc: ClinicalSimulationService):
        sims = svc.list_enrollment_simulations()
        statuses = {s.status for s in sims}
        assert SimulationStatus.COMPLETED in statuses
        assert SimulationStatus.CONFIGURED in statuses

    def test_seed_enrollment_sims_have_multiple_model_types(self, svc: ClinicalSimulationService):
        sims = svc.list_enrollment_simulations()
        types = {s.model_type for s in sims}
        assert len(types) >= 4

    def test_seed_outcome_models_cover_all_trials(self, svc: ClinicalSimulationService):
        models = svc.list_outcome_models()
        trial_ids = {m.trial_id for m in models}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_scenario_comparisons_have_multiple_types(self, svc: ClinicalSimulationService):
        comparisons = svc.list_scenario_comparisons()
        types = {c.scenario_type for c in comparisons}
        assert len(types) >= 4

    def test_seed_sensitivity_analyses_have_multiple_parameters(self, svc: ClinicalSimulationService):
        analyses = svc.list_sensitivity_analyses()
        param_types = {a.parameter_type for a in analyses}
        assert len(param_types) >= 4


# =====================================================================
# ENROLLMENT SIMULATION CRUD
# =====================================================================


class TestEnrollmentSimulationCrud:
    """Test enrollment simulation CRUD operations."""

    @pytest.mark.anyio
    async def test_list_enrollment_simulations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/enrollment-simulations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_enrollment_simulations_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/enrollment-simulations", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_enrollment_simulations_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/enrollment-simulations", params={"status": "completed"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_list_enrollment_simulations_filter_model_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/enrollment-simulations", params={"model_type": "bayesian"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["model_type"] == "bayesian"

    @pytest.mark.anyio
    async def test_get_enrollment_simulation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/enrollment-simulations/ES-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ES-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["simulation_type"] == "enrollment"

    @pytest.mark.anyio
    async def test_get_enrollment_simulation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/enrollment-simulations/ES-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_enrollment_simulation(self, client: AsyncClient):
        payload = _make_enrollment_create()
        resp = await client.post(f"{API_PREFIX}/enrollment-simulations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["status"] == "configured"
        assert data["id"].startswith("ES-")

    @pytest.mark.anyio
    async def test_update_enrollment_simulation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/enrollment-simulations/ES-011",
            json={"status": "running", "enrollment_rate_per_site_month": 1.8, "notes": "Started"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["enrollment_rate_per_site_month"] == 1.8
        assert data["notes"] == "Started"

    @pytest.mark.anyio
    async def test_update_enrollment_simulation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/enrollment-simulations/ES-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_enrollment_simulation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/enrollment-simulations/ES-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/enrollment-simulations/ES-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_enrollment_simulation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/enrollment-simulations/ES-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# OUTCOME MODEL CRUD
# =====================================================================


class TestOutcomeModelCrud:
    """Test outcome model CRUD operations."""

    @pytest.mark.anyio
    async def test_list_outcome_models(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/outcome-models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_outcome_models_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/outcome-models", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_outcome_models_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/outcome-models", params={"status": "completed"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_list_outcome_models_filter_model_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/outcome-models", params={"model_type": "bayesian"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["model_type"] == "bayesian"

    @pytest.mark.anyio
    async def test_get_outcome_model(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/outcome-models/OM-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "OM-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_outcome_model_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/outcome-models/OM-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_outcome_model(self, client: AsyncClient):
        payload = _make_outcome_create()
        resp = await client.post(f"{API_PREFIX}/outcome-models", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == DUPIXENT_TRIAL
        assert data["status"] == "configured"
        assert data["id"].startswith("OM-")

    @pytest.mark.anyio
    async def test_update_outcome_model(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/outcome-models/OM-010",
            json={"status": "running", "simulated_power": 0.92, "notes": "Running sim"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["simulated_power"] == 0.92
        assert data["notes"] == "Running sim"

    @pytest.mark.anyio
    async def test_update_outcome_model_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/outcome-models/OM-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_outcome_model(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/outcome-models/OM-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/outcome-models/OM-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_outcome_model_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/outcome-models/OM-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# RESOURCE FORECAST CRUD
# =====================================================================


class TestResourceForecastCrud:
    """Test resource forecast CRUD operations."""

    @pytest.mark.anyio
    async def test_list_resource_forecasts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/resource-forecasts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_resource_forecasts_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/resource-forecasts", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_resource_forecasts_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/resource-forecasts", params={"status": "configured"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "configured"

    @pytest.mark.anyio
    async def test_get_resource_forecast(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/resource-forecasts/RF-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RF-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_resource_forecast_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/resource-forecasts/RF-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_resource_forecast(self, client: AsyncClient):
        payload = _make_resource_create()
        resp = await client.post(f"{API_PREFIX}/resource-forecasts", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == LIBTAYO_TRIAL
        assert data["status"] == "configured"
        assert data["id"].startswith("RF-")

    @pytest.mark.anyio
    async def test_update_resource_forecast(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/resource-forecasts/RF-010",
            json={"total_cost_estimate": 16000000.0, "monthly_burn_rate": 1400000.0, "notes": "Updated"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cost_estimate"] == 16000000.0
        assert data["monthly_burn_rate"] == 1400000.0
        assert data["notes"] == "Updated"

    @pytest.mark.anyio
    async def test_update_resource_forecast_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/resource-forecasts/RF-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_resource_forecast(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/resource-forecasts/RF-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/resource-forecasts/RF-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_resource_forecast_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/resource-forecasts/RF-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# SCENARIO COMPARISON CRUD
# =====================================================================


class TestScenarioComparisonCrud:
    """Test scenario comparison CRUD operations."""

    @pytest.mark.anyio
    async def test_list_scenario_comparisons(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/scenario-comparisons")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_scenario_comparisons_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/scenario-comparisons", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_scenario_comparisons_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/scenario-comparisons", params={"scenario_type": "baseline"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["scenario_type"] == "baseline"

    @pytest.mark.anyio
    async def test_get_scenario_comparison(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/scenario-comparisons/SC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SC-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_scenario_comparison_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/scenario-comparisons/SC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_scenario_comparison(self, client: AsyncClient):
        payload = _make_scenario_create()
        resp = await client.post(f"{API_PREFIX}/scenario-comparisons", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["scenario_type"] == "optimistic"
        assert data["is_preferred"] is False
        assert data["id"].startswith("SC-")

    @pytest.mark.anyio
    async def test_update_scenario_comparison(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/scenario-comparisons/SC-010",
            json={"is_preferred": True, "recommendation": "Expand sites", "notes": "Updated"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_preferred"] is True
        assert data["recommendation"] == "Expand sites"
        assert data["notes"] == "Updated"

    @pytest.mark.anyio
    async def test_update_scenario_comparison_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/scenario-comparisons/SC-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_scenario_comparison(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/scenario-comparisons/SC-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/scenario-comparisons/SC-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_scenario_comparison_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/scenario-comparisons/SC-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# SENSITIVITY ANALYSIS CRUD
# =====================================================================


class TestSensitivityAnalysisCrud:
    """Test sensitivity analysis CRUD operations."""

    @pytest.mark.anyio
    async def test_list_sensitivity_analyses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sensitivity-analyses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_sensitivity_analyses_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/sensitivity-analyses", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_sensitivity_analyses_filter_parameter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/sensitivity-analyses", params={"parameter_type": "enrollment_rate"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["parameter_type"] == "enrollment_rate"

    @pytest.mark.anyio
    async def test_get_sensitivity_analysis(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sensitivity-analyses/SA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SA-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["parameter_type"] == "enrollment_rate"

    @pytest.mark.anyio
    async def test_get_sensitivity_analysis_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sensitivity-analyses/SA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_sensitivity_analysis(self, client: AsyncClient):
        payload = _make_sensitivity_create()
        resp = await client.post(f"{API_PREFIX}/sensitivity-analyses", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == DUPIXENT_TRIAL
        assert data["parameter_type"] == "enrollment_rate"
        assert data["id"].startswith("SA-")

    @pytest.mark.anyio
    async def test_update_sensitivity_analysis(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sensitivity-analyses/SA-010",
            json={"most_sensitive_parameter": "effect_size", "tornado_rank": 1, "notes": "Updated"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["most_sensitive_parameter"] == "effect_size"
        assert data["tornado_rank"] == 1
        assert data["notes"] == "Updated"

    @pytest.mark.anyio
    async def test_update_sensitivity_analysis_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sensitivity-analyses/SA-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_sensitivity_analysis(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sensitivity-analyses/SA-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/sensitivity-analyses/SA-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_sensitivity_analysis_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sensitivity-analyses/SA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestClinicalSimulationMetrics:
    """Test clinical simulation metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_enrollment_sims"] == 12
        assert data["total_outcome_models"] == 10
        assert data["total_resource_forecasts"] == 10
        assert data["total_scenario_comparisons"] == 10
        assert data["total_sensitivity_analyses"] == 10

    @pytest.mark.anyio
    async def test_metrics_sims_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["sims_by_status"]
        total = sum(by_status.values())
        assert total == data["total_enrollment_sims"]

    @pytest.mark.anyio
    async def test_metrics_sims_by_model(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_model = data["sims_by_model"]
        total = sum(by_model.values())
        assert total == data["total_enrollment_sims"]

    @pytest.mark.anyio
    async def test_metrics_avg_simulated_power(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["avg_simulated_power"] > 0
        assert data["avg_simulated_power"] <= 1.0

    @pytest.mark.anyio
    async def test_metrics_total_forecast_cost(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_forecast_cost"] > 0

    @pytest.mark.anyio
    async def test_metrics_scenarios_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_type = data["scenarios_by_type"]
        total = sum(by_type.values())
        assert total == data["total_scenario_comparisons"]

    @pytest.mark.anyio
    async def test_metrics_analyses_by_parameter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_param = data["analyses_by_parameter"]
        total = sum(by_param.values())
        assert total == data["total_sensitivity_analyses"]


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_clinical_simulation_service()
        svc2 = get_clinical_simulation_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_clinical_simulation_service()
        svc2 = reset_clinical_simulation_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_clinical_simulation_service()
        # Delete a simulation
        svc.delete_enrollment_simulation("ES-001")
        assert svc.get_enrollment_simulation("ES-001") is None
        # Reset should bring it back
        svc2 = reset_clinical_simulation_service()
        assert svc2.get_enrollment_simulation("ES-001") is not None


# =====================================================================
# FILTERING AND EDGE CASES
# =====================================================================


class TestFilteringAndEdgeCases:
    """Test filtering combinations and edge cases."""

    @pytest.mark.anyio
    async def test_list_enrollments_empty_filter(self, client: AsyncClient):
        """Filter by a trial that has no simulations."""
        resp = await client.get(
            f"{API_PREFIX}/enrollment-simulations",
            params={"trial_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.anyio
    async def test_list_outcomes_empty_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/outcome-models",
            params={"status": "failed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_scenarios_filter_best_case(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/scenario-comparisons", params={"scenario_type": "best_case"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["scenario_type"] == "best_case"

    @pytest.mark.anyio
    async def test_create_enrollment_then_retrieve(self, client: AsyncClient):
        """Create a simulation and verify it shows in the list."""
        payload = _make_enrollment_create()
        resp = await client.post(f"{API_PREFIX}/enrollment-simulations", json=payload)
        assert resp.status_code == 201
        created_id = resp.json()["id"]

        resp2 = await client.get(f"{API_PREFIX}/enrollment-simulations/{created_id}")
        assert resp2.status_code == 200
        assert resp2.json()["id"] == created_id

    @pytest.mark.anyio
    async def test_create_outcome_then_update_status(self, client: AsyncClient):
        """Create an outcome model, then update through lifecycle."""
        payload = _make_outcome_create()
        resp = await client.post(f"{API_PREFIX}/outcome-models", json=payload)
        assert resp.status_code == 201
        model_id = resp.json()["id"]
        assert resp.json()["status"] == "configured"

        # Update to running
        resp2 = await client.put(
            f"{API_PREFIX}/outcome-models/{model_id}",
            json={"status": "running"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "running"

        # Update to completed with results
        resp3 = await client.put(
            f"{API_PREFIX}/outcome-models/{model_id}",
            json={"status": "completed", "simulated_power": 0.85, "probability_success": 0.80},
        )
        assert resp3.status_code == 200
        assert resp3.json()["status"] == "completed"
        assert resp3.json()["simulated_power"] == 0.85

    @pytest.mark.anyio
    async def test_create_and_delete_resource_forecast(self, client: AsyncClient):
        """Create a resource forecast and then delete it."""
        payload = _make_resource_create()
        resp = await client.post(f"{API_PREFIX}/resource-forecasts", json=payload)
        assert resp.status_code == 201
        forecast_id = resp.json()["id"]

        resp2 = await client.delete(f"{API_PREFIX}/resource-forecasts/{forecast_id}")
        assert resp2.status_code == 204

        resp3 = await client.get(f"{API_PREFIX}/resource-forecasts/{forecast_id}")
        assert resp3.status_code == 404

    @pytest.mark.anyio
    async def test_create_sensitivity_with_simulation_id(self, client: AsyncClient):
        """Create a sensitivity analysis linked to a simulation."""
        payload = _make_sensitivity_create(simulation_id="ES-001")
        resp = await client.post(f"{API_PREFIX}/sensitivity-analyses", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["simulation_id"] == "ES-001"

    @pytest.mark.anyio
    async def test_create_scenario_with_baseline_sim_id(self, client: AsyncClient):
        """Create a scenario comparison linked to a baseline simulation."""
        payload = _make_scenario_create(baseline_simulation_id="ES-001")
        resp = await client.post(f"{API_PREFIX}/scenario-comparisons", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["baseline_simulation_id"] == "ES-001"

    @pytest.mark.anyio
    async def test_enrollments_sorted_by_created_at_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/enrollment-simulations")
        data = resp.json()
        dates = [item["created_at"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_scenarios_sorted_by_analysis_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/scenario-comparisons")
        data = resp.json()
        dates = [item["analysis_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_metrics_after_create_and_delete(self, client: AsyncClient):
        """Metrics should reflect dynamic changes."""
        # Get baseline metrics
        resp1 = await client.get(f"{API_PREFIX}/metrics")
        baseline = resp1.json()

        # Create a new enrollment simulation
        payload = _make_enrollment_create()
        await client.post(f"{API_PREFIX}/enrollment-simulations", json=payload)

        resp2 = await client.get(f"{API_PREFIX}/metrics")
        after_create = resp2.json()
        assert after_create["total_enrollment_sims"] == baseline["total_enrollment_sims"] + 1

        # Delete a simulation
        await client.delete(f"{API_PREFIX}/enrollment-simulations/ES-012")
        resp3 = await client.get(f"{API_PREFIX}/metrics")
        after_delete = resp3.json()
        assert after_delete["total_enrollment_sims"] == baseline["total_enrollment_sims"]


# =====================================================================
# ENUM COVERAGE
# =====================================================================


class TestEnumCoverage:
    """Verify enum values are represented in seed data."""

    @pytest.mark.anyio
    async def test_simulation_statuses_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/enrollment-simulations")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "completed" in statuses
        assert "configured" in statuses
        assert "running" in statuses

    @pytest.mark.anyio
    async def test_model_types_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/enrollment-simulations")
        data = resp.json()
        types = {item["model_type"] for item in data["items"]}
        assert "monte_carlo" in types
        assert "bayesian" in types
        assert "discrete_event" in types
        assert "agent_based" in types
        assert "deterministic" in types

    @pytest.mark.anyio
    async def test_simulation_types_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/enrollment-simulations")
        data = resp.json()
        types = {item["simulation_type"] for item in data["items"]}
        assert "enrollment" in types
        assert "adaptive" in types
        assert "full_trial" in types

    @pytest.mark.anyio
    async def test_scenario_types_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/scenario-comparisons")
        data = resp.json()
        types = {item["scenario_type"] for item in data["items"]}
        assert "baseline" in types
        assert "optimistic" in types
        assert "pessimistic" in types
        assert "best_case" in types
        assert "worst_case" in types
        assert "custom" in types

    @pytest.mark.anyio
    async def test_parameter_types_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sensitivity-analyses")
        data = resp.json()
        types = {item["parameter_type"] for item in data["items"]}
        assert "enrollment_rate" in types
        assert "dropout_rate" in types
        assert "event_rate" in types
        assert "treatment_effect" in types
        assert "cost_per_patient" in types
        assert "site_activation_rate" in types

    @pytest.mark.anyio
    async def test_outcome_model_types_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/outcome-models")
        data = resp.json()
        types = {item["model_type"] for item in data["items"]}
        assert "monte_carlo" in types
        assert "bayesian" in types
        assert "markov" in types
        assert "deterministic" in types
