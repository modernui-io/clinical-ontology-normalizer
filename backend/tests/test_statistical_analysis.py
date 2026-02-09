"""Tests for Statistical Analysis & Interim Analysis Management (CLINICAL-25).

Covers:
- Seed data verification (SAPs, analysis results, interim analyses, sample size calcs, subgroups)
- SAP CRUD (create, read, update, delete, list, filter by trial/status)
- Analysis result CRUD (create, read, delete, list, filter by type/population/significance)
- Interim analysis (list, get, create, alpha spending summary)
- Sample size calculations (list, get, filter by trial)
- Subgroup analyses (list, get, create, filter by result/variable, interaction testing)
- Multiplicity adjustment summary
- Forest plot data generation
- Trial-level result summaries
- Statistical metrics computation
- Error handling (404s, 400s, invalid references)
- Edge cases (empty filters, boundary conditions)
- Singleton pattern behavior
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.statistical_analysis import (
    AnalysisType,
    InterimRecommendation,
    MultiplicityCorrectionMethod,
    PopulationType,
    StatisticalMethod,
)
from app.services.statistical_analysis_service import (
    StatisticalAnalysisService,
    get_stats_service,
    reset_stats_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/statistical-analysis"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_stats_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> StatisticalAnalysisService:
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


def _make_sap_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "version": "1.0",
        "title": "Test SAP for Unit Testing",
        "primary_endpoint": "Test primary endpoint",
        "secondary_endpoints": ["Secondary 1", "Secondary 2"],
        "sample_size_calculation": "Test sample size: 100 per arm",
        "randomization_ratio": "1:1",
        "alpha_level": 0.05,
        "power": 0.90,
        "populations": ["itt", "safety"],
        "analysis_methods": ["t_test", "chi_square"],
        "multiplicity_strategy": "bonferroni",
    }
    defaults.update(overrides)
    return defaults


def _make_result_create(**overrides) -> dict:
    defaults = {
        "plan_id": "SAP-001",
        "trial_id": EYLEA_TRIAL,
        "analysis_type": "primary",
        "endpoint": "Test endpoint",
        "population": "itt",
        "method": "t_test",
        "estimate": 5.0,
        "confidence_interval_lower": 3.0,
        "confidence_interval_upper": 7.0,
        "p_value": 0.01,
        "adjusted_p_value": 0.03,
        "clinically_significant": True,
        "n_treatment": 100,
        "n_control": 100,
        "effect_size": 0.50,
        "test_statistic": 2.58,
    }
    defaults.update(overrides)
    return defaults


def _make_interim_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "analysis_number": 2,
        "planned_info_fraction": 0.75,
        "actual_info_fraction": 0.73,
        "analysis_date": now.isoformat(),
        "alpha_spent": 0.01,
        "cumulative_alpha_spent": 0.013,
        "boundary_crossed": False,
        "recommendation": "continue",
        "dsmb_review_date": (now + timedelta(days=5)).isoformat(),
        "z_statistic": 2.45,
        "efficacy_boundary": 2.36,
        "futility_boundary": 0.50,
        "notes": "Test interim analysis",
    }
    defaults.update(overrides)
    return defaults


def _make_subgroup_create(**overrides) -> dict:
    defaults = {
        "result_id": "AR-001",
        "subgroup_variable": "sex",
        "subgroup_value": "Male",
        "estimate": 9.0,
        "ci_lower": 6.5,
        "ci_upper": 11.5,
        "p_value": 0.001,
        "n": 320,
        "interaction_p_value": 0.65,
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_saps_count(self, svc: StatisticalAnalysisService):
        saps = svc.list_saps()
        assert len(saps) == 3

    def test_seed_saps_trials(self, svc: StatisticalAnalysisService):
        saps = svc.list_saps()
        trial_ids = {s.trial_id for s in saps}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_saps_all_final(self, svc: StatisticalAnalysisService):
        saps = svc.list_saps()
        for s in saps:
            assert s.status == "final"

    def test_seed_eylea_primary_endpoint(self, svc: StatisticalAnalysisService):
        sap = svc.get_sap("SAP-001")
        assert sap is not None
        assert "BCVA" in sap.primary_endpoint
        assert "Week 48" in sap.primary_endpoint

    def test_seed_dupixent_primary_endpoint(self, svc: StatisticalAnalysisService):
        sap = svc.get_sap("SAP-002")
        assert sap is not None
        assert "EASI-75" in sap.primary_endpoint

    def test_seed_libtayo_primary_endpoint(self, svc: StatisticalAnalysisService):
        sap = svc.get_sap("SAP-003")
        assert sap is not None
        assert "ORR" in sap.primary_endpoint
        assert "RECIST" in sap.primary_endpoint

    def test_seed_analysis_results_count(self, svc: StatisticalAnalysisService):
        results = svc.list_analysis_results()
        assert len(results) == 20

    def test_seed_interim_analyses_count(self, svc: StatisticalAnalysisService):
        ias = svc.list_interim_analyses()
        assert len(ias) == 3

    def test_seed_sample_size_calcs_count(self, svc: StatisticalAnalysisService):
        calcs = svc.list_sample_size_calcs()
        assert len(calcs) == 3

    def test_seed_subgroup_analyses_count(self, svc: StatisticalAnalysisService):
        sgs = svc.list_subgroup_analyses()
        assert len(sgs) == 10

    def test_seed_libtayo_interim_boundary_crossed(self, svc: StatisticalAnalysisService):
        ia = svc.get_interim_analysis("IA-003")
        assert ia is not None
        assert ia.boundary_crossed is True
        assert ia.recommendation == InterimRecommendation.STOP_EFFICACY

    def test_seed_eylea_interim_continue(self, svc: StatisticalAnalysisService):
        ia = svc.get_interim_analysis("IA-001")
        assert ia is not None
        assert ia.boundary_crossed is False
        assert ia.recommendation == InterimRecommendation.CONTINUE


# =====================================================================
# SAP CRUD
# =====================================================================


class TestSAPCrud:
    """Test SAP create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_saps(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/saps")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    @pytest.mark.anyio
    async def test_list_saps_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/saps", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_saps_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/saps", params={"status": "final"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_saps_filter_status_draft_empty(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/saps", params={"status": "draft"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_get_sap(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/saps/SAP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SAP-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert "BCVA" in data["primary_endpoint"]

    @pytest.mark.anyio
    async def test_get_sap_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/saps/SAP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_sap(self, client: AsyncClient):
        payload = _make_sap_create()
        resp = await client.post(f"{API_PREFIX}/saps", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test SAP for Unit Testing"
        assert data["status"] == "draft"
        assert data["id"].startswith("SAP-")

    @pytest.mark.anyio
    async def test_create_sap_all_populations(self, client: AsyncClient):
        payload = _make_sap_create(
            populations=["itt", "modified_itt", "per_protocol", "safety", "full_analysis_set"]
        )
        resp = await client.post(f"{API_PREFIX}/saps", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["populations"]) == 5

    @pytest.mark.anyio
    async def test_update_sap(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/saps/SAP-001",
            json={"title": "Updated EYLEA SAP Title", "status": "amended"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated EYLEA SAP Title"
        assert data["status"] == "amended"

    @pytest.mark.anyio
    async def test_update_sap_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/saps/SAP-NONEXISTENT",
            json={"title": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_sap(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/saps/SAP-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/saps/SAP-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_sap_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/saps/SAP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_sap_has_secondary_endpoints(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/saps/SAP-002")
        data = resp.json()
        assert len(data["secondary_endpoints"]) >= 3

    @pytest.mark.anyio
    async def test_sap_has_methods(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/saps/SAP-001")
        data = resp.json()
        assert len(data["analysis_methods"]) >= 2

    @pytest.mark.anyio
    async def test_sap_alpha_level_valid(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/saps/SAP-001")
        data = resp.json()
        assert 0 < data["alpha_level"] <= 0.05

    @pytest.mark.anyio
    async def test_sap_power_valid(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/saps/SAP-001")
        data = resp.json()
        assert 0.8 <= data["power"] <= 1.0


# =====================================================================
# ANALYSIS RESULTS
# =====================================================================


class TestAnalysisResults:
    """Test analysis result CRUD operations."""

    @pytest.mark.anyio
    async def test_list_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 20

    @pytest.mark.anyio
    async def test_list_results_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_results_filter_plan(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results", params={"plan_id": "SAP-002"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["plan_id"] == "SAP-002"

    @pytest.mark.anyio
    async def test_list_results_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results", params={"analysis_type": "primary"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3  # One primary per trial
        for item in data["items"]:
            assert item["analysis_type"] == "primary"

    @pytest.mark.anyio
    async def test_list_results_filter_population(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results", params={"population": "safety"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["population"] == "safety"

    @pytest.mark.anyio
    async def test_list_results_filter_significant(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results", params={"significant_only": True})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["p_value"] < 0.05

    @pytest.mark.anyio
    async def test_get_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results/AR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "AR-001"
        assert data["analysis_type"] == "primary"
        assert "BCVA" in data["endpoint"]

    @pytest.mark.anyio
    async def test_get_result_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results/AR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_result(self, client: AsyncClient):
        payload = _make_result_create()
        resp = await client.post(f"{API_PREFIX}/results", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["endpoint"] == "Test endpoint"
        assert data["id"].startswith("AR-")

    @pytest.mark.anyio
    async def test_create_result_invalid_plan(self, client: AsyncClient):
        payload = _make_result_create(plan_id="SAP-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/results", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_delete_result(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/results/AR-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/results/AR-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_result_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/results/AR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_result_p_value_range(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results")
        data = resp.json()
        for item in data["items"]:
            assert 0 <= item["p_value"] <= 1.0

    @pytest.mark.anyio
    async def test_result_confidence_interval_ordered(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results")
        data = resp.json()
        for item in data["items"]:
            assert item["confidence_interval_lower"] <= item["confidence_interval_upper"]

    @pytest.mark.anyio
    async def test_result_sample_sizes_positive(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results")
        data = resp.json()
        for item in data["items"]:
            assert item["n_treatment"] > 0
            assert item["n_control"] > 0


# =====================================================================
# INTERIM ANALYSES
# =====================================================================


class TestInterimAnalyses:
    """Test interim analysis operations."""

    @pytest.mark.anyio
    async def test_list_interim_analyses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/interim")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_interim_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/interim", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_interim_analysis(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/interim/IA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "IA-001"
        assert data["recommendation"] == "continue"

    @pytest.mark.anyio
    async def test_get_interim_analysis_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/interim/IA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_interim_analysis(self, client: AsyncClient):
        payload = _make_interim_create()
        resp = await client.post(f"{API_PREFIX}/interim", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["analysis_number"] == 2
        assert data["id"].startswith("IA-")

    @pytest.mark.anyio
    async def test_interim_alpha_spent_valid(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/interim")
        data = resp.json()
        for item in data["items"]:
            assert 0 <= item["alpha_spent"] <= 1.0
            assert 0 <= item["cumulative_alpha_spent"] <= 1.0
            assert item["alpha_spent"] <= item["cumulative_alpha_spent"]

    @pytest.mark.anyio
    async def test_interim_info_fraction_valid(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/interim")
        data = resp.json()
        for item in data["items"]:
            assert 0 < item["planned_info_fraction"] <= 1.0
            assert 0 < item["actual_info_fraction"] <= 1.0

    @pytest.mark.anyio
    async def test_libtayo_boundary_crossed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/interim/IA-003")
        data = resp.json()
        assert data["boundary_crossed"] is True
        assert data["recommendation"] == "stop_efficacy"
        assert data["z_statistic"] is not None
        assert data["z_statistic"] > data["efficacy_boundary"]

    def test_interim_sorted_by_trial_and_number(self, svc: StatisticalAnalysisService):
        ias = svc.list_interim_analyses()
        for i in range(1, len(ias)):
            if ias[i].trial_id == ias[i - 1].trial_id:
                assert ias[i].analysis_number >= ias[i - 1].analysis_number


# =====================================================================
# ALPHA SPENDING
# =====================================================================


class TestAlphaSpending:
    """Test alpha spending summary operations."""

    @pytest.mark.anyio
    async def test_alpha_spending_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/interim/alpha-spending/{EYLEA_TRIAL}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["cumulative_alpha_spent"] == 0.003
        assert data["alpha_remaining"] > 0
        assert data["interim_looks"] == 1
        assert data["boundary_crossed"] is False

    @pytest.mark.anyio
    async def test_alpha_spending_libtayo_crossed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/interim/alpha-spending/{LIBTAYO_TRIAL}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["boundary_crossed"] is True
        assert data["cumulative_alpha_spent"] > 0

    @pytest.mark.anyio
    async def test_alpha_spending_no_interim(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/interim/alpha-spending/TRIAL-NONEXISTENT")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cumulative_alpha_spent"] == 0.0
        assert data["interim_looks"] == 0

    def test_alpha_remaining_calculation(self, svc: StatisticalAnalysisService):
        summary = svc.get_alpha_spending_summary(EYLEA_TRIAL)
        assert abs(
            summary["total_alpha"]
            - summary["cumulative_alpha_spent"]
            - summary["alpha_remaining"]
        ) < 1e-6

    def test_alpha_remaining_dupixent(self, svc: StatisticalAnalysisService):
        summary = svc.get_alpha_spending_summary(DUPIXENT_TRIAL)
        assert summary["alpha_remaining"] > 0
        assert summary["alpha_remaining"] < summary["total_alpha"]


# =====================================================================
# SAMPLE SIZE CALCULATIONS
# =====================================================================


class TestSampleSizeCalcs:
    """Test sample size calculation operations."""

    @pytest.mark.anyio
    async def test_list_sample_size_calcs(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sample-size")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_sample_size_calcs_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/sample-size", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_sample_size_calc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sample-size/SS-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SS-001"
        assert data["calculated_n_per_arm"] > 0
        assert data["total_n_with_dropout"] > data["calculated_n_per_arm"]

    @pytest.mark.anyio
    async def test_get_sample_size_calc_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sample-size/SS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_sample_size_dropout_increases_n(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sample-size")
        data = resp.json()
        for item in data["items"]:
            assert item["total_n_with_dropout"] >= item["calculated_n_per_arm"] * 2

    @pytest.mark.anyio
    async def test_sample_size_has_method(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sample-size/SS-002")
        data = resp.json()
        assert len(data["method"]) > 0
        assert len(data["assumptions"]) > 0

    @pytest.mark.anyio
    async def test_sample_size_power_range(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sample-size")
        data = resp.json()
        for item in data["items"]:
            assert 0.8 <= item["power"] <= 1.0
            assert 0 < item["alpha"] <= 0.05


# =====================================================================
# SUBGROUP ANALYSES
# =====================================================================


class TestSubgroupAnalyses:
    """Test subgroup analysis operations."""

    @pytest.mark.anyio
    async def test_list_subgroups(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/subgroups")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_subgroups_filter_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/subgroups", params={"result_id": "AR-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4  # EYLEA primary has 4 subgroups
        for item in data["items"]:
            assert item["result_id"] == "AR-001"

    @pytest.mark.anyio
    async def test_list_subgroups_filter_variable(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/subgroups", params={"subgroup_variable": "age"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2  # age < 65 and >= 65
        for item in data["items"]:
            assert item["subgroup_variable"] == "age"

    @pytest.mark.anyio
    async def test_get_subgroup(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/subgroups/SG-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SG-001"
        assert data["subgroup_variable"] == "age"

    @pytest.mark.anyio
    async def test_get_subgroup_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/subgroups/SG-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_subgroup(self, client: AsyncClient):
        payload = _make_subgroup_create()
        resp = await client.post(f"{API_PREFIX}/subgroups", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["subgroup_variable"] == "sex"
        assert data["id"].startswith("SG-")

    @pytest.mark.anyio
    async def test_create_subgroup_invalid_result(self, client: AsyncClient):
        payload = _make_subgroup_create(result_id="AR-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/subgroups", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_subgroup_interaction_p_values(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/subgroups")
        data = resp.json()
        for item in data["items"]:
            assert 0 <= item["interaction_p_value"] <= 1.0

    @pytest.mark.anyio
    async def test_subgroup_ci_ordered(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/subgroups")
        data = resp.json()
        for item in data["items"]:
            assert item["ci_lower"] <= item["ci_upper"]

    @pytest.mark.anyio
    async def test_pdl1_interaction_significant(self, client: AsyncClient):
        """PD-L1 subgroup should show significant interaction (p=0.02)."""
        resp = await client.get(f"{API_PREFIX}/subgroups/SG-009")
        data = resp.json()
        assert data["interaction_p_value"] < 0.05

    @pytest.mark.anyio
    async def test_age_interaction_not_significant(self, client: AsyncClient):
        """Age subgroup should not show significant interaction."""
        resp = await client.get(f"{API_PREFIX}/subgroups/SG-001")
        data = resp.json()
        assert data["interaction_p_value"] > 0.05


# =====================================================================
# MULTIPLICITY ADJUSTMENTS
# =====================================================================


class TestMultiplicity:
    """Test multiplicity adjustment summaries."""

    @pytest.mark.anyio
    async def test_multiplicity_summary_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/multiplicity/SAP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan_id"] == "SAP-001"
        assert data["multiplicity_method"] == "graphical"
        assert data["total_tests"] > 0
        assert data["primary_tests"] >= 1

    @pytest.mark.anyio
    async def test_multiplicity_summary_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/multiplicity/SAP-002")
        assert resp.status_code == 200
        data = resp.json()
        assert data["multiplicity_method"] == "hochberg"

    @pytest.mark.anyio
    async def test_multiplicity_summary_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/multiplicity/SAP-NONEXISTENT")
        assert resp.status_code == 404

    def test_multiplicity_primary_significant(self, svc: StatisticalAnalysisService):
        summary = svc.get_multiplicity_summary("SAP-001")
        assert summary["primary_significant"] >= 1

    def test_multiplicity_secondary_significant(self, svc: StatisticalAnalysisService):
        summary = svc.get_multiplicity_summary("SAP-002")
        assert summary["secondary_significant"] >= 1


# =====================================================================
# TRIAL-LEVEL SUMMARIES
# =====================================================================


class TestTrialResults:
    """Test trial-level result endpoints."""

    @pytest.mark.anyio
    async def test_trial_results_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials/{EYLEA_TRIAL}/results")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 5
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_trial_results_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials/{DUPIXENT_TRIAL}/results")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 5

    @pytest.mark.anyio
    async def test_trial_results_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials/{LIBTAYO_TRIAL}/results")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 5

    @pytest.mark.anyio
    async def test_trial_results_empty(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials/TRIAL-NONEXISTENT/results")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0


# =====================================================================
# FOREST PLOT DATA
# =====================================================================


class TestForestPlotData:
    """Test forest plot data generation."""

    @pytest.mark.anyio
    async def test_forest_plot_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials/{EYLEA_TRIAL}/forest-plot-data")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert len(data["primary"]) > 0
        assert len(data["subgroups"]) > 0

    @pytest.mark.anyio
    async def test_forest_plot_primary_has_required_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials/{EYLEA_TRIAL}/forest-plot-data")
        data = resp.json()
        for item in data["primary"]:
            assert "estimate" in item
            assert "ci_lower" in item
            assert "ci_upper" in item
            assert "p_value" in item
            assert "endpoint" in item

    @pytest.mark.anyio
    async def test_forest_plot_subgroups_have_interaction(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials/{EYLEA_TRIAL}/forest-plot-data")
        data = resp.json()
        for item in data["subgroups"]:
            assert "interaction_p_value" in item
            assert "subgroup_variable" in item
            assert "subgroup_value" in item

    @pytest.mark.anyio
    async def test_forest_plot_empty_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials/TRIAL-NONEXISTENT/forest-plot-data")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["primary"]) == 0
        assert len(data["subgroups"]) == 0

    @pytest.mark.anyio
    async def test_forest_plot_libtayo_has_subgroups(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials/{LIBTAYO_TRIAL}/forest-plot-data")
        data = resp.json()
        assert len(data["subgroups"]) >= 2  # PD-L1 subgroups


# =====================================================================
# METRICS
# =====================================================================


class TestStatisticalMetrics:
    """Test statistical metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_analyses"] == 20
        assert data["total_saps"] == 3
        assert data["total_sample_size_calcs"] == 3
        assert data["total_subgroup_analyses"] == 10
        assert data["interim_analyses_completed"] == 3
        assert data["significant_results_count"] > 0
        assert data["avg_effect_size"] > 0

    def test_metrics_analyses_by_type(self, svc: StatisticalAnalysisService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.analyses_by_type.values())
        assert total_by_type == metrics.total_analyses

    def test_metrics_has_primary_type(self, svc: StatisticalAnalysisService):
        metrics = svc.get_metrics()
        assert "primary" in metrics.analyses_by_type
        assert metrics.analyses_by_type["primary"] >= 3

    def test_metrics_has_secondary_type(self, svc: StatisticalAnalysisService):
        metrics = svc.get_metrics()
        assert "secondary" in metrics.analyses_by_type

    def test_metrics_has_safety_type(self, svc: StatisticalAnalysisService):
        metrics = svc.get_metrics()
        assert "safety" in metrics.analyses_by_type

    def test_metrics_alpha_remaining(self, svc: StatisticalAnalysisService):
        metrics = svc.get_metrics()
        assert 0 < metrics.alpha_remaining <= 0.05

    def test_metrics_boundary_crossed_count(self, svc: StatisticalAnalysisService):
        metrics = svc.get_metrics()
        assert metrics.trials_with_boundary_crossed == 1  # Only LIBTAYO


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_stats_service()
        svc2 = get_stats_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_stats_service()
        svc2 = reset_stats_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_stats_service()
        svc.delete_sap("SAP-001")
        assert svc.get_sap("SAP-001") is None
        svc2 = reset_stats_service()
        assert svc2.get_sap("SAP-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_saps_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/saps")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_results_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_interim_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/interim")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_subgroups_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/subgroups")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_sample_size_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sample-size")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_result_with_adjusted_p(self, client: AsyncClient):
        payload = _make_result_create(adjusted_p_value=0.045)
        resp = await client.post(f"{API_PREFIX}/results", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["adjusted_p_value"] == 0.045

    @pytest.mark.anyio
    async def test_create_result_without_adjusted_p(self, client: AsyncClient):
        payload = _make_result_create(adjusted_p_value=None)
        resp = await client.post(f"{API_PREFIX}/results", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["adjusted_p_value"] is None

    @pytest.mark.anyio
    async def test_create_sap_with_all_methods(self, client: AsyncClient):
        payload = _make_sap_create(
            analysis_methods=[
                "t_test", "chi_square", "cox_regression",
                "logistic_regression", "ancova", "mmrm",
                "kaplan_meier", "fisher_exact", "wilcoxon", "log_rank",
            ]
        )
        resp = await client.post(f"{API_PREFIX}/saps", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["analysis_methods"]) == 10

    @pytest.mark.anyio
    async def test_interim_create_with_all_fields(self, client: AsyncClient):
        payload = _make_interim_create()
        resp = await client.post(f"{API_PREFIX}/interim", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["z_statistic"] is not None
        assert data["efficacy_boundary"] is not None
        assert data["futility_boundary"] is not None

    @pytest.mark.anyio
    async def test_interim_create_minimal(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = {
            "trial_id": EYLEA_TRIAL,
            "analysis_number": 3,
            "planned_info_fraction": 1.0,
            "actual_info_fraction": 0.98,
            "analysis_date": now.isoformat(),
            "alpha_spent": 0.022,
            "cumulative_alpha_spent": 0.025,
            "boundary_crossed": True,
            "recommendation": "stop_efficacy",
        }
        resp = await client.post(f"{API_PREFIX}/interim", json=payload)
        assert resp.status_code == 201


# =====================================================================
# ANALYSIS TYPE ENUMERATION
# =====================================================================


class TestEnumerations:
    """Test enum values are correctly used throughout the system."""

    @pytest.mark.anyio
    async def test_all_analysis_types_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results")
        data = resp.json()
        types = {item["analysis_type"] for item in data["items"]}
        assert "primary" in types
        assert "secondary" in types
        assert "safety" in types
        assert "exploratory" in types
        assert "sensitivity" in types

    @pytest.mark.anyio
    async def test_population_types_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results")
        data = resp.json()
        populations = {item["population"] for item in data["items"]}
        assert "itt" in populations
        assert "safety" in populations

    @pytest.mark.anyio
    async def test_methods_in_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results")
        data = resp.json()
        methods = {item["method"] for item in data["items"]}
        assert len(methods) >= 5

    @pytest.mark.anyio
    async def test_multiplicity_strategies_in_saps(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/saps")
        data = resp.json()
        strategies = {item["multiplicity_strategy"] for item in data["items"]}
        assert "graphical" in strategies
        assert "hochberg" in strategies
        assert "gatekeeping" in strategies

    @pytest.mark.anyio
    async def test_interim_recommendations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/interim")
        data = resp.json()
        recs = {item["recommendation"] for item in data["items"]}
        assert "continue" in recs
        assert "stop_efficacy" in recs


# =====================================================================
# RESULT DETAILS
# =====================================================================


class TestResultDetails:
    """Test detailed analysis result components."""

    @pytest.mark.anyio
    async def test_eylea_primary_clinically_significant(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results/AR-001")
        data = resp.json()
        assert data["clinically_significant"] is True
        assert data["effect_size"] > 0.5

    @pytest.mark.anyio
    async def test_safety_result_not_significant(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results/AR-005")
        data = resp.json()
        assert data["analysis_type"] == "safety"
        assert data["clinically_significant"] is False
        assert data["p_value"] > 0.05

    @pytest.mark.anyio
    async def test_dupixent_primary_strong_effect(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results/AR-007")
        data = resp.json()
        assert data["analysis_type"] == "primary"
        assert data["p_value"] < 0.001

    @pytest.mark.anyio
    async def test_libtayo_os_hazard_ratio(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results/AR-014")
        data = resp.json()
        assert data["method"] == "cox_regression"
        assert data["estimate"] < 1.0  # Hazard ratio < 1 = treatment benefit

    @pytest.mark.anyio
    async def test_per_protocol_sensitivity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results/AR-002")
        data = resp.json()
        assert data["analysis_type"] == "sensitivity"
        assert data["population"] == "per_protocol"

    @pytest.mark.anyio
    async def test_modified_itt_sensitivity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results/AR-020")
        data = resp.json()
        assert data["population"] == "modified_itt"
        assert data["analysis_type"] == "sensitivity"

    @pytest.mark.anyio
    async def test_post_hoc_analysis(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results/AR-012")
        data = resp.json()
        assert data["analysis_type"] == "post_hoc"
        assert data["population"] == "full_analysis_set"

    @pytest.mark.anyio
    async def test_subgroup_analysis_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results/AR-019")
        data = resp.json()
        assert data["analysis_type"] == "subgroup"


# =====================================================================
# SAP DETAILS
# =====================================================================


class TestSAPDetails:
    """Test detailed SAP components."""

    @pytest.mark.anyio
    async def test_eylea_sap_randomization(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/saps/SAP-001")
        data = resp.json()
        assert data["randomization_ratio"] == "1:1"

    @pytest.mark.anyio
    async def test_dupixent_sap_2_to_1_randomization(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/saps/SAP-002")
        data = resp.json()
        assert data["randomization_ratio"] == "2:1"

    @pytest.mark.anyio
    async def test_eylea_sap_one_sided_alpha(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/saps/SAP-001")
        data = resp.json()
        assert data["alpha_level"] == 0.025  # One-sided

    @pytest.mark.anyio
    async def test_dupixent_sap_two_sided_alpha(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/saps/SAP-002")
        data = resp.json()
        assert data["alpha_level"] == 0.05  # Two-sided

    @pytest.mark.anyio
    async def test_sap_created_before_updated(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/saps/SAP-001")
        data = resp.json()
        created = datetime.fromisoformat(data["created_at"])
        updated = datetime.fromisoformat(data["updated_at"])
        assert created <= updated

    @pytest.mark.anyio
    async def test_libtayo_sap_gatekeeping(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/saps/SAP-003")
        data = resp.json()
        assert data["multiplicity_strategy"] == "gatekeeping"

    @pytest.mark.anyio
    async def test_sap_has_populations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/saps/SAP-002")
        data = resp.json()
        assert len(data["populations"]) >= 3

    @pytest.mark.anyio
    async def test_sap_update_preserves_trial_id(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/saps/SAP-001",
            json={"version": "3.0"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["version"] == "3.0"
