"""Tests for Health Economics & Outcomes Research (HEOR) module.

Covers:
- Seed data verification (studies, CE results, budget models, dossiers, payer evidence)
- Study CRUD (create, read, update, delete, list, filter by trial/type/status/country)
- Cost-effectiveness result CRUD with auto-compute cost_effective logic
- Budget impact model CRUD (create, read, update, delete, list, filter by study)
- Value dossier CRUD (create, read, update, delete, list, filter by trial/status/market/payer/grade)
- Payer evidence CRUD (create, read, update, delete, list, filter by dossier/type/country)
- Metrics computation (studies by type/status, CE results by model, avg ICER, dossier stats)
- Error handling (404s on missing entities)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.heor import (
    AnalysisType,
    BudgetImpactModelCreate,
    BudgetImpactModelUpdate,
    CostEffectivenessResultCreate,
    CostEffectivenessResultUpdate,
    DossierStatus,
    EvidenceGrade,
    HEORStudyCreate,
    HEORStudyUpdate,
    ModelType,
    PayerEvidenceCreate,
    PayerEvidenceUpdate,
    PayerType,
    StudyStatus,
    ValueDossierCreate,
    ValueDossierUpdate,
)
from app.services.heor_service import (
    HEORService,
    get_heor_service,
    reset_heor_service,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/heor"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_heor_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> HEORService:
    return fresh_service


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ===========================================================================
# SEED DATA VERIFICATION
# ===========================================================================


class TestSeedData:
    """Verify seed data is populated correctly."""

    @pytest.mark.anyio
    async def test_seed_studies_count(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 11

    @pytest.mark.anyio
    async def test_seed_ce_results_count(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ce-results")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 10

    @pytest.mark.anyio
    async def test_seed_budget_models_count(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/budget-models")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 10

    @pytest.mark.anyio
    async def test_seed_dossiers_count(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dossiers")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 10

    @pytest.mark.anyio
    async def test_seed_payer_evidence_count(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/payer-evidence")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 12

    @pytest.mark.anyio
    async def test_seed_study_001_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/heor-study-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["trial_id"] == EYLEA_TRIAL
        assert body["analysis_type"] == "cost_effectiveness"
        assert body["status"] == "completed"
        assert body["country"] == "US"
        assert "Ranibizumab" in body["comparator"]

    @pytest.mark.anyio
    async def test_seed_ce_result_001_cost_effective(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ce-results/ce-result-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["icer"] == 42500.0
        assert body["wtp_threshold"] == 50000.0
        assert body["cost_effective"] is True

    @pytest.mark.anyio
    async def test_seed_ce_result_010_not_cost_effective(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ce-results/ce-result-010")
        assert resp.status_code == 200
        body = resp.json()
        assert body["icer"] == 125000.0
        assert body["wtp_threshold"] == 100000.0
        assert body["cost_effective"] is False

    @pytest.mark.anyio
    async def test_seed_budget_model_001(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/budget-models/bim-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["target_population_size"] == 250000
        assert body["cumulative_budget_impact"] == 450000000.0

    @pytest.mark.anyio
    async def test_seed_dossier_001_approved(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dossiers/dossier-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "approved"
        assert body["evidence_grade"] == "high"
        assert body["product_name"] == "EYLEA (aflibercept)"

    @pytest.mark.anyio
    async def test_seed_payer_evidence_001(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/payer-evidence/pe-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["payer_name"] == "Aetna"
        assert body["payer_type"] == "commercial"
        assert body["outcome"] == "Favorable"

    @pytest.mark.anyio
    async def test_seed_eylea_studies(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 4

    @pytest.mark.anyio
    async def test_seed_dupixent_studies(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 3

    @pytest.mark.anyio
    async def test_seed_libtayo_studies(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 3


# ===========================================================================
# STUDY CRUD
# ===========================================================================


class TestStudyCRUD:
    """Full CRUD tests for HEOR studies."""

    @pytest.mark.anyio
    async def test_create_study(self, client: AsyncClient):
        payload = HEORStudyCreate(
            trial_id=EYLEA_TRIAL,
            title="New CEA Study",
            analysis_type=AnalysisType.COST_EFFECTIVENESS,
            comparator="Faricimab",
            perspective="US Healthcare Payer",
            time_horizon="Lifetime",
            principal_analyst="Dr. Test User",
            country="US",
            data_sources=["Trial A", "Trial B"],
        ).model_dump()
        resp = await client.post(f"{API_PREFIX}/studies", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "New CEA Study"
        assert body["status"] == "planned"
        assert body["id"] is not None

    @pytest.mark.anyio
    async def test_create_study_with_discount_rate(self, client: AsyncClient):
        payload = HEORStudyCreate(
            trial_id=DUPIXENT_TRIAL,
            title="CUA with Custom Discount",
            analysis_type=AnalysisType.COST_UTILITY,
            comparator="Placebo",
            perspective="Societal",
            time_horizon="20 years",
            discount_rate_pct=5.0,
            principal_analyst="Dr. Discount",
            country="UK",
        ).model_dump()
        resp = await client.post(f"{API_PREFIX}/studies", json=payload)
        assert resp.status_code == 201
        assert resp.json()["discount_rate_pct"] == 5.0

    @pytest.mark.anyio
    async def test_get_study(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/heor-study-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "heor-study-001"

    @pytest.mark.anyio
    async def test_get_study_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_study_status(self, client: AsyncClient):
        payload = HEORStudyUpdate(status=StudyStatus.PUBLISHED).model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/studies/heor-study-001", json=payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "published"

    @pytest.mark.anyio
    async def test_update_study_title(self, client: AsyncClient):
        payload = HEORStudyUpdate(title="Updated Title").model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/studies/heor-study-002", json=payload)
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"

    @pytest.mark.anyio
    async def test_update_study_target_publication(self, client: AsyncClient):
        payload = HEORStudyUpdate(target_publication="JAMA").model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/studies/heor-study-003", json=payload)
        assert resp.status_code == 200
        assert resp.json()["target_publication"] == "JAMA"

    @pytest.mark.anyio
    async def test_update_study_not_found(self, client: AsyncClient):
        payload = HEORStudyUpdate(title="Nope").model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/studies/nonexistent", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_study(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/studies/heor-study-011")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/studies/heor-study-011")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_study_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/studies/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_studies_no_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 11

    @pytest.mark.anyio
    async def test_filter_studies_by_analysis_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/studies",
            params={"analysis_type": "cost_effectiveness"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        for item in items:
            assert item["analysis_type"] == "cost_effectiveness"

    @pytest.mark.anyio
    async def test_filter_studies_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies", params={"status": "completed"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        for item in items:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_filter_studies_by_country(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies", params={"country": "UK"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        for item in items:
            assert item["country"] == "UK"

    @pytest.mark.anyio
    async def test_filter_studies_by_country_case_insensitive(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies", params={"country": "us"})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.anyio
    async def test_filter_studies_by_trial_id(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        items = resp.json()["items"]
        for item in items:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_filter_studies_empty_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies", params={"country": "Antarctica"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_create_and_retrieve_study(self, client: AsyncClient):
        payload = HEORStudyCreate(
            trial_id=LIBTAYO_TRIAL,
            title="Roundtrip Study",
            analysis_type=AnalysisType.BUDGET_IMPACT,
            comparator="Standard of Care",
            perspective="Medicare",
            time_horizon="3 years",
            principal_analyst="Dr. Roundtrip",
            country="US",
        ).model_dump()
        resp = await client.post(f"{API_PREFIX}/studies", json=payload)
        study_id = resp.json()["id"]
        resp2 = await client.get(f"{API_PREFIX}/studies/{study_id}")
        assert resp2.status_code == 200
        assert resp2.json()["title"] == "Roundtrip Study"


# ===========================================================================
# COST-EFFECTIVENESS RESULTS CRUD
# ===========================================================================


class TestCEResultCRUD:
    """Full CRUD tests for cost-effectiveness results."""

    @pytest.mark.anyio
    async def test_create_ce_result_auto_cost_effective_true(self, client: AsyncClient):
        payload = CostEffectivenessResultCreate(
            study_id="heor-study-001",
            model_type=ModelType.MARKOV,
            icer=30000.0,
            wtp_threshold=50000.0,
            analyst="Dr. Test",
        ).model_dump()
        resp = await client.post(f"{API_PREFIX}/ce-results", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["cost_effective"] is True

    @pytest.mark.anyio
    async def test_create_ce_result_auto_cost_effective_false(self, client: AsyncClient):
        payload = CostEffectivenessResultCreate(
            study_id="heor-study-001",
            model_type=ModelType.DECISION_TREE,
            icer=75000.0,
            wtp_threshold=50000.0,
            analyst="Dr. Test",
        ).model_dump()
        resp = await client.post(f"{API_PREFIX}/ce-results", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["cost_effective"] is False

    @pytest.mark.anyio
    async def test_create_ce_result_equal_icer_wtp(self, client: AsyncClient):
        payload = CostEffectivenessResultCreate(
            study_id="heor-study-001",
            model_type=ModelType.MARKOV,
            icer=50000.0,
            wtp_threshold=50000.0,
            analyst="Dr. Test",
        ).model_dump()
        resp = await client.post(f"{API_PREFIX}/ce-results", json=payload)
        assert resp.status_code == 201
        assert resp.json()["cost_effective"] is True

    @pytest.mark.anyio
    async def test_create_ce_result_no_icer_null_cost_effective(self, client: AsyncClient):
        payload = CostEffectivenessResultCreate(
            study_id="heor-study-009",
            model_type=ModelType.PARTITIONED_SURVIVAL,
            wtp_threshold=100000.0,
            analyst="Dr. Test",
        ).model_dump()
        resp = await client.post(f"{API_PREFIX}/ce-results", json=payload)
        assert resp.status_code == 201
        assert resp.json()["cost_effective"] is None

    @pytest.mark.anyio
    async def test_create_ce_result_no_wtp_null_cost_effective(self, client: AsyncClient):
        payload = CostEffectivenessResultCreate(
            study_id="heor-study-009",
            model_type=ModelType.MICROSIMULATION,
            icer=45000.0,
            analyst="Dr. Test",
        ).model_dump()
        resp = await client.post(f"{API_PREFIX}/ce-results", json=payload)
        assert resp.status_code == 201
        assert resp.json()["cost_effective"] is None

    @pytest.mark.anyio
    async def test_create_ce_result_with_incremental_values(self, client: AsyncClient):
        payload = CostEffectivenessResultCreate(
            study_id="heor-study-005",
            model_type=ModelType.HYBRID,
            icer=55000.0,
            incremental_cost=27500.0,
            incremental_qaly=0.50,
            incremental_ly=0.35,
            wtp_threshold=100000.0,
            analyst="Dr. Detailed",
        ).model_dump()
        resp = await client.post(f"{API_PREFIX}/ce-results", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["incremental_cost"] == 27500.0
        assert body["incremental_qaly"] == 0.50
        assert body["incremental_ly"] == 0.35
        assert body["cost_effective"] is True

    @pytest.mark.anyio
    async def test_get_ce_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ce-results/ce-result-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "ce-result-001"

    @pytest.mark.anyio
    async def test_get_ce_result_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ce-results/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_ce_result_icer(self, client: AsyncClient):
        payload = CostEffectivenessResultUpdate(icer=35000.0).model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/ce-results/ce-result-001", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["icer"] == 35000.0
        assert body["cost_effective"] is True  # 35K < 50K WTP

    @pytest.mark.anyio
    async def test_update_ce_result_sensitivity(self, client: AsyncClient):
        payload = CostEffectivenessResultUpdate(
            sensitivity_analysis_type="Threshold analysis"
        ).model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/ce-results/ce-result-002", json=payload)
        assert resp.status_code == 200
        assert resp.json()["sensitivity_analysis_type"] == "Threshold analysis"

    @pytest.mark.anyio
    async def test_update_ce_result_nmb(self, client: AsyncClient):
        payload = CostEffectivenessResultUpdate(nmb=5000.0).model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/ce-results/ce-result-003", json=payload)
        assert resp.status_code == 200
        assert resp.json()["nmb"] == 5000.0

    @pytest.mark.anyio
    async def test_update_ce_result_confidence_intervals(self, client: AsyncClient):
        payload = CostEffectivenessResultUpdate(
            confidence_interval_low=20000.0,
            confidence_interval_high=70000.0,
        ).model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/ce-results/ce-result-004", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["confidence_interval_low"] == 20000.0
        assert body["confidence_interval_high"] == 70000.0

    @pytest.mark.anyio
    async def test_update_ce_result_probability_pct(self, client: AsyncClient):
        payload = CostEffectivenessResultUpdate(
            probability_cost_effective_pct=90.0,
        ).model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/ce-results/ce-result-005", json=payload)
        assert resp.status_code == 200
        assert resp.json()["probability_cost_effective_pct"] == 90.0

    @pytest.mark.anyio
    async def test_update_ce_result_not_found(self, client: AsyncClient):
        payload = CostEffectivenessResultUpdate(icer=1.0).model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/ce-results/nonexistent", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_ce_result(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/ce-results/ce-result-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/ce-results/ce-result-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_ce_result_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/ce-results/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_ce_results_no_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ce-results")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 10

    @pytest.mark.anyio
    async def test_filter_ce_results_by_study(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/ce-results", params={"study_id": "heor-study-001"}
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 3
        for item in items:
            assert item["study_id"] == "heor-study-001"

    @pytest.mark.anyio
    async def test_filter_ce_results_by_model_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/ce-results", params={"model_type": "markov"}
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        for item in items:
            assert item["model_type"] == "markov"

    @pytest.mark.anyio
    async def test_filter_ce_results_empty(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/ce-results", params={"study_id": "nonexistent-study"}
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_create_and_retrieve_ce_result(self, client: AsyncClient):
        payload = CostEffectivenessResultCreate(
            study_id="heor-study-005",
            model_type=ModelType.DISCRETE_EVENT,
            icer=60000.0,
            wtp_threshold=100000.0,
            analyst="Dr. Roundtrip",
        ).model_dump()
        resp = await client.post(f"{API_PREFIX}/ce-results", json=payload)
        result_id = resp.json()["id"]
        resp2 = await client.get(f"{API_PREFIX}/ce-results/{result_id}")
        assert resp2.status_code == 200
        assert resp2.json()["icer"] == 60000.0


# ===========================================================================
# BUDGET IMPACT MODEL CRUD
# ===========================================================================


class TestBudgetModelCRUD:
    """Full CRUD tests for budget impact models."""

    @pytest.mark.anyio
    async def test_create_budget_model(self, client: AsyncClient):
        payload = BudgetImpactModelCreate(
            study_id="heor-study-003",
            target_population_size=100000,
            market_share_year1_pct=10.0,
            market_share_year2_pct=20.0,
            market_share_year3_pct=30.0,
            drug_cost_per_patient=15000.0,
            comparator_cost_per_patient=12000.0,
            assumptions=["Assumption 1", "Assumption 2"],
            modeler="Dr. Budget",
        ).model_dump()
        resp = await client.post(f"{API_PREFIX}/budget-models", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["target_population_size"] == 100000
        assert body["total_budget_impact_year1"] is None

    @pytest.mark.anyio
    async def test_create_budget_model_zero_costs(self, client: AsyncClient):
        payload = BudgetImpactModelCreate(
            study_id="heor-study-008",
            target_population_size=0,
            market_share_year1_pct=0.0,
            market_share_year2_pct=0.0,
            market_share_year3_pct=0.0,
            drug_cost_per_patient=0.0,
            comparator_cost_per_patient=0.0,
            modeler="Dr. Zero",
        ).model_dump()
        resp = await client.post(f"{API_PREFIX}/budget-models", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_get_budget_model(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/budget-models/bim-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "bim-001"

    @pytest.mark.anyio
    async def test_get_budget_model_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/budget-models/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_budget_model_impact(self, client: AsyncClient):
        payload = BudgetImpactModelUpdate(
            total_budget_impact_year1=100000000.0,
            total_budget_impact_year2=200000000.0,
            total_budget_impact_year3=300000000.0,
            cumulative_budget_impact=600000000.0,
            pmpm_impact=1.0,
        ).model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/budget-models/bim-001", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_budget_impact_year1"] == 100000000.0
        assert body["cumulative_budget_impact"] == 600000000.0
        assert body["pmpm_impact"] == 1.0

    @pytest.mark.anyio
    async def test_update_budget_model_partial(self, client: AsyncClient):
        payload = BudgetImpactModelUpdate(pmpm_impact=2.5).model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/budget-models/bim-002", json=payload)
        assert resp.status_code == 200
        assert resp.json()["pmpm_impact"] == 2.5

    @pytest.mark.anyio
    async def test_update_budget_model_not_found(self, client: AsyncClient):
        payload = BudgetImpactModelUpdate(pmpm_impact=1.0).model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/budget-models/nonexistent", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_budget_model(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/budget-models/bim-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/budget-models/bim-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_budget_model_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/budget-models/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_budget_models_no_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/budget-models")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 10

    @pytest.mark.anyio
    async def test_filter_budget_models_by_study(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/budget-models", params={"study_id": "heor-study-003"}
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 2
        for item in items:
            assert item["study_id"] == "heor-study-003"

    @pytest.mark.anyio
    async def test_filter_budget_models_empty(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/budget-models", params={"study_id": "nonexistent"}
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_create_and_retrieve_budget_model(self, client: AsyncClient):
        payload = BudgetImpactModelCreate(
            study_id="heor-study-008",
            target_population_size=50000,
            market_share_year1_pct=20.0,
            market_share_year2_pct=35.0,
            market_share_year3_pct=45.0,
            drug_cost_per_patient=150000.0,
            comparator_cost_per_patient=30000.0,
            modeler="Dr. Roundtrip",
        ).model_dump()
        resp = await client.post(f"{API_PREFIX}/budget-models", json=payload)
        model_id = resp.json()["id"]
        resp2 = await client.get(f"{API_PREFIX}/budget-models/{model_id}")
        assert resp2.status_code == 200
        assert resp2.json()["target_population_size"] == 50000

    @pytest.mark.anyio
    async def test_budget_model_negative_impact(self, client: AsyncClient):
        """Budget impact model with negative (cost-saving) cumulative."""
        resp = await client.get(f"{API_PREFIX}/budget-models/bim-006")
        assert resp.status_code == 200
        body = resp.json()
        assert body["cumulative_budget_impact"] < 0
        assert body["pmpm_impact"] < 0


# ===========================================================================
# VALUE DOSSIER CRUD
# ===========================================================================


class TestDossierCRUD:
    """Full CRUD tests for value dossiers."""

    @pytest.mark.anyio
    async def test_create_dossier(self, client: AsyncClient):
        payload = ValueDossierCreate(
            trial_id=EYLEA_TRIAL,
            product_name="EYLEA HD",
            indication="Wet AMD",
            target_payer_type=PayerType.COMMERCIAL,
            target_market="US",
            clinical_value_summary="Test clinical summary",
            economic_value_summary="Test economic summary",
            unmet_need_description="Test unmet need",
            key_messages=["Message 1", "Message 2"],
            author="Dr. Dossier Author",
        ).model_dump()
        resp = await client.post(f"{API_PREFIX}/dossiers", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "draft"
        assert body["evidence_grade"] == "moderate"
        assert body["product_name"] == "EYLEA HD"

    @pytest.mark.anyio
    async def test_create_dossier_minimal(self, client: AsyncClient):
        payload = ValueDossierCreate(
            trial_id=LIBTAYO_TRIAL,
            product_name="LIBTAYO",
            indication="BCC",
            target_payer_type=PayerType.MEDICARE,
            target_market="US",
            clinical_value_summary="Minimal clinical",
            economic_value_summary="Minimal economic",
            unmet_need_description="Minimal unmet need",
            author="Dr. Minimal",
        ).model_dump()
        resp = await client.post(f"{API_PREFIX}/dossiers", json=payload)
        assert resp.status_code == 201
        assert resp.json()["key_messages"] == []

    @pytest.mark.anyio
    async def test_get_dossier(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dossiers/dossier-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "dossier-001"

    @pytest.mark.anyio
    async def test_get_dossier_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dossiers/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_dossier_status(self, client: AsyncClient):
        payload = ValueDossierUpdate(status=DossierStatus.SUBMITTED).model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/dossiers/dossier-004", json=payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "submitted"

    @pytest.mark.anyio
    async def test_update_dossier_evidence_grade(self, client: AsyncClient):
        payload = ValueDossierUpdate(evidence_grade=EvidenceGrade.HIGH).model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/dossiers/dossier-005", json=payload)
        assert resp.status_code == 200
        assert resp.json()["evidence_grade"] == "high"

    @pytest.mark.anyio
    async def test_update_dossier_reviewer(self, client: AsyncClient):
        payload = ValueDossierUpdate(reviewer="New Reviewer").model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/dossiers/dossier-006", json=payload)
        assert resp.status_code == 200
        assert resp.json()["reviewer"] == "New Reviewer"

    @pytest.mark.anyio
    async def test_update_dossier_key_messages(self, client: AsyncClient):
        payload = ValueDossierUpdate(key_messages=["New Message 1"]).model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/dossiers/dossier-001", json=payload)
        assert resp.status_code == 200
        assert resp.json()["key_messages"] == ["New Message 1"]

    @pytest.mark.anyio
    async def test_update_dossier_supporting_studies(self, client: AsyncClient):
        payload = ValueDossierUpdate(supporting_studies=["study-x"]).model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/dossiers/dossier-002", json=payload)
        assert resp.status_code == 200
        assert resp.json()["supporting_studies"] == ["study-x"]

    @pytest.mark.anyio
    async def test_update_dossier_not_found(self, client: AsyncClient):
        payload = ValueDossierUpdate(status=DossierStatus.DRAFT).model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/dossiers/nonexistent", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_dossier(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/dossiers/dossier-009")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/dossiers/dossier-009")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_dossier_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/dossiers/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_dossiers_no_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dossiers")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 10

    @pytest.mark.anyio
    async def test_filter_dossiers_by_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/dossiers", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        for item in items:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_filter_dossiers_by_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/dossiers", params={"status": "approved"}
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        for item in items:
            assert item["status"] == "approved"

    @pytest.mark.anyio
    async def test_filter_dossiers_by_target_market(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/dossiers", params={"target_market": "US"}
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        for item in items:
            assert item["target_market"] == "US"

    @pytest.mark.anyio
    async def test_filter_dossiers_by_target_market_case_insensitive(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/dossiers", params={"target_market": "uk"}
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 1

    @pytest.mark.anyio
    async def test_filter_dossiers_by_payer_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/dossiers", params={"target_payer_type": "medicare"}
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        for item in items:
            assert item["target_payer_type"] == "medicare"

    @pytest.mark.anyio
    async def test_filter_dossiers_by_evidence_grade(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/dossiers", params={"evidence_grade": "high"}
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        for item in items:
            assert item["evidence_grade"] == "high"

    @pytest.mark.anyio
    async def test_filter_dossiers_empty(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/dossiers", params={"target_market": "Mars"}
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_create_and_retrieve_dossier(self, client: AsyncClient):
        payload = ValueDossierCreate(
            trial_id=DUPIXENT_TRIAL,
            product_name="DUPIXENT",
            indication="Prurigo Nodularis",
            target_payer_type=PayerType.COMMERCIAL,
            target_market="US",
            clinical_value_summary="Roundtrip clinical",
            economic_value_summary="Roundtrip economic",
            unmet_need_description="Roundtrip unmet need",
            author="Dr. Roundtrip",
        ).model_dump()
        resp = await client.post(f"{API_PREFIX}/dossiers", json=payload)
        dossier_id = resp.json()["id"]
        resp2 = await client.get(f"{API_PREFIX}/dossiers/{dossier_id}")
        assert resp2.status_code == 200
        assert resp2.json()["indication"] == "Prurigo Nodularis"


# ===========================================================================
# PAYER EVIDENCE CRUD
# ===========================================================================


class TestPayerEvidenceCRUD:
    """Full CRUD tests for payer evidence records."""

    @pytest.mark.anyio
    async def test_create_payer_evidence(self, client: AsyncClient):
        payload = PayerEvidenceCreate(
            dossier_id="dossier-001",
            payer_name="Humana",
            payer_type=PayerType.COMMERCIAL,
            country="US",
            contact_person="Dr. Humana Contact",
        ).model_dump()
        resp = await client.post(f"{API_PREFIX}/payer-evidence", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["payer_name"] == "Humana"
        assert body["outcome"] is None

    @pytest.mark.anyio
    async def test_create_payer_evidence_medicare(self, client: AsyncClient):
        payload = PayerEvidenceCreate(
            dossier_id="dossier-003",
            payer_name="Medicare Advantage Plan",
            payer_type=PayerType.MEDICARE,
            country="US",
            contact_person="MA Program Director",
        ).model_dump()
        resp = await client.post(f"{API_PREFIX}/payer-evidence", json=payload)
        assert resp.status_code == 201
        assert resp.json()["payer_type"] == "medicare"

    @pytest.mark.anyio
    async def test_get_payer_evidence(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/payer-evidence/pe-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "pe-001"

    @pytest.mark.anyio
    async def test_get_payer_evidence_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/payer-evidence/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_payer_evidence_outcome(self, client: AsyncClient):
        payload = PayerEvidenceUpdate(
            outcome="Approved",
            coverage_decision="Preferred formulary listing",
        ).model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/payer-evidence/pe-002", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["outcome"] == "Approved"
        assert body["coverage_decision"] == "Preferred formulary listing"

    @pytest.mark.anyio
    async def test_update_payer_evidence_restrictions(self, client: AsyncClient):
        payload = PayerEvidenceUpdate(
            restrictions=["Prior auth required", "Specialist only"],
        ).model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/payer-evidence/pe-003", json=payload)
        assert resp.status_code == 200
        assert len(resp.json()["restrictions"]) == 2

    @pytest.mark.anyio
    async def test_update_payer_evidence_feedback(self, client: AsyncClient):
        payload = PayerEvidenceUpdate(
            feedback_summary="Additional real-world data requested",
        ).model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/payer-evidence/pe-006", json=payload)
        assert resp.status_code == 200
        assert "real-world" in resp.json()["feedback_summary"]

    @pytest.mark.anyio
    async def test_update_payer_evidence_not_found(self, client: AsyncClient):
        payload = PayerEvidenceUpdate(outcome="Rejected").model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/payer-evidence/nonexistent", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_payer_evidence(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/payer-evidence/pe-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/payer-evidence/pe-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_payer_evidence_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/payer-evidence/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_payer_evidence_no_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/payer-evidence")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 12

    @pytest.mark.anyio
    async def test_filter_payer_evidence_by_dossier(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/payer-evidence", params={"dossier_id": "dossier-001"}
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 2
        for item in items:
            assert item["dossier_id"] == "dossier-001"

    @pytest.mark.anyio
    async def test_filter_payer_evidence_by_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/payer-evidence", params={"payer_type": "commercial"}
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        for item in items:
            assert item["payer_type"] == "commercial"

    @pytest.mark.anyio
    async def test_filter_payer_evidence_by_country(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/payer-evidence", params={"country": "US"}
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        for item in items:
            assert item["country"] == "US"

    @pytest.mark.anyio
    async def test_filter_payer_evidence_by_country_case_insensitive(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/payer-evidence", params={"country": "canada"}
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.anyio
    async def test_filter_payer_evidence_empty(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/payer-evidence", params={"country": "Narnia"}
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_create_and_retrieve_payer_evidence(self, client: AsyncClient):
        payload = PayerEvidenceCreate(
            dossier_id="dossier-002",
            payer_name="OptumRx",
            payer_type=PayerType.COMMERCIAL,
            country="US",
            contact_person="Dr. Optum",
        ).model_dump()
        resp = await client.post(f"{API_PREFIX}/payer-evidence", json=payload)
        ev_id = resp.json()["id"]
        resp2 = await client.get(f"{API_PREFIX}/payer-evidence/{ev_id}")
        assert resp2.status_code == 200
        assert resp2.json()["payer_name"] == "OptumRx"


# ===========================================================================
# METRICS
# ===========================================================================


class TestMetrics:
    """Metrics endpoint tests."""

    @pytest.mark.anyio
    async def test_metrics_total_studies(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_studies"] >= 11

    @pytest.mark.anyio
    async def test_metrics_studies_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        body = resp.json()
        sbt = body["studies_by_type"]
        assert "cost_effectiveness" in sbt
        assert "cost_utility" in sbt
        assert "budget_impact" in sbt

    @pytest.mark.anyio
    async def test_metrics_studies_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        body = resp.json()
        sbs = body["studies_by_status"]
        assert "completed" in sbs
        assert "planned" in sbs

    @pytest.mark.anyio
    async def test_metrics_total_ce_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        body = resp.json()
        assert body["total_ce_results"] >= 10

    @pytest.mark.anyio
    async def test_metrics_results_by_model(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        body = resp.json()
        rbm = body["results_by_model"]
        assert "markov" in rbm
        assert "decision_tree" in rbm

    @pytest.mark.anyio
    async def test_metrics_cost_effective_count(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        body = resp.json()
        assert body["cost_effective_count"] >= 7

    @pytest.mark.anyio
    async def test_metrics_total_budget_models(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        body = resp.json()
        assert body["total_budget_models"] >= 10

    @pytest.mark.anyio
    async def test_metrics_total_dossiers(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        body = resp.json()
        assert body["total_dossiers"] >= 10

    @pytest.mark.anyio
    async def test_metrics_dossiers_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        body = resp.json()
        dbs = body["dossiers_by_status"]
        assert "draft" in dbs
        assert "approved" in dbs

    @pytest.mark.anyio
    async def test_metrics_total_payer_submissions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        body = resp.json()
        assert body["total_payer_submissions"] >= 12

    @pytest.mark.anyio
    async def test_metrics_payer_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        body = resp.json()
        pbt = body["payer_by_type"]
        assert "commercial" in pbt
        assert "medicare" in pbt

    @pytest.mark.anyio
    async def test_metrics_avg_icer(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        body = resp.json()
        assert body["avg_icer"] is not None
        assert body["avg_icer"] > 0

    @pytest.mark.anyio
    async def test_metrics_avg_icer_excludes_none(self, svc: HEORService):
        """avg_icer should only average results with non-None icer values."""
        metrics = svc.get_metrics()
        # ce-result-007 has icer=None and should not be included
        ce_results = svc.list_ce_results()
        icer_values = [r.icer for r in ce_results if r.icer is not None]
        expected_avg = sum(icer_values) / len(icer_values)
        assert abs(metrics.avg_icer - expected_avg) < 0.01

    @pytest.mark.anyio
    async def test_metrics_after_create(self, client: AsyncClient):
        # Create a new study and verify metrics incremented
        resp = await client.get(f"{API_PREFIX}/metrics")
        initial_total = resp.json()["total_studies"]
        payload = HEORStudyCreate(
            trial_id=EYLEA_TRIAL,
            title="Metrics Test Study",
            analysis_type=AnalysisType.META_ANALYSIS,
            comparator="Multiple",
            perspective="Societal",
            time_horizon="N/A",
            principal_analyst="Dr. Metrics",
            country="US",
        ).model_dump()
        await client.post(f"{API_PREFIX}/studies", json=payload)
        resp2 = await client.get(f"{API_PREFIX}/metrics")
        assert resp2.json()["total_studies"] == initial_total + 1

    @pytest.mark.anyio
    async def test_metrics_after_delete(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        initial_total = resp.json()["total_studies"]
        await client.delete(f"{API_PREFIX}/studies/heor-study-011")
        resp2 = await client.get(f"{API_PREFIX}/metrics")
        assert resp2.json()["total_studies"] == initial_total - 1

    @pytest.mark.anyio
    async def test_metrics_cost_effective_after_create_ce(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        initial_ce = resp.json()["cost_effective_count"]
        payload = CostEffectivenessResultCreate(
            study_id="heor-study-001",
            model_type=ModelType.MARKOV,
            icer=10000.0,
            wtp_threshold=50000.0,
            analyst="Dr. Metrics CE",
        ).model_dump()
        await client.post(f"{API_PREFIX}/ce-results", json=payload)
        resp2 = await client.get(f"{API_PREFIX}/metrics")
        assert resp2.json()["cost_effective_count"] == initial_ce + 1


# ===========================================================================
# SERVICE UNIT TESTS
# ===========================================================================


class TestServiceDirect:
    """Direct service tests (no HTTP)."""

    @pytest.mark.anyio
    async def test_singleton_returns_same_instance(self):
        svc1 = get_heor_service()
        svc2 = get_heor_service()
        assert svc1 is svc2

    @pytest.mark.anyio
    async def test_reset_returns_new_instance(self):
        svc1 = get_heor_service()
        svc2 = reset_heor_service()
        assert svc1 is not svc2

    @pytest.mark.anyio
    async def test_study_create_assigns_uuid(self, svc: HEORService):
        study = svc.create_study(HEORStudyCreate(
            trial_id=EYLEA_TRIAL,
            title="UUID Test",
            analysis_type=AnalysisType.COST_EFFECTIVENESS,
            comparator="Test",
            perspective="Test",
            time_horizon="1 year",
            principal_analyst="Dr. UUID",
            country="US",
        ))
        assert len(study.id) == 36  # UUID format

    @pytest.mark.anyio
    async def test_study_create_default_status(self, svc: HEORService):
        study = svc.create_study(HEORStudyCreate(
            trial_id=DUPIXENT_TRIAL,
            title="Default Status Test",
            analysis_type=AnalysisType.COST_UTILITY,
            comparator="Placebo",
            perspective="Payer",
            time_horizon="Lifetime",
            principal_analyst="Dr. Default",
            country="UK",
        ))
        assert study.status == StudyStatus.PLANNED

    @pytest.mark.anyio
    async def test_ce_result_auto_compute_true(self, svc: HEORService):
        result = svc.create_ce_result(CostEffectivenessResultCreate(
            study_id="heor-study-001",
            model_type=ModelType.MARKOV,
            icer=25000.0,
            wtp_threshold=50000.0,
            analyst="Dr. Auto",
        ))
        assert result.cost_effective is True

    @pytest.mark.anyio
    async def test_ce_result_auto_compute_false(self, svc: HEORService):
        result = svc.create_ce_result(CostEffectivenessResultCreate(
            study_id="heor-study-001",
            model_type=ModelType.MARKOV,
            icer=75000.0,
            wtp_threshold=50000.0,
            analyst="Dr. Auto",
        ))
        assert result.cost_effective is False

    @pytest.mark.anyio
    async def test_ce_result_auto_compute_null_when_no_icer(self, svc: HEORService):
        result = svc.create_ce_result(CostEffectivenessResultCreate(
            study_id="heor-study-001",
            model_type=ModelType.MARKOV,
            wtp_threshold=50000.0,
            analyst="Dr. Auto",
        ))
        assert result.cost_effective is None

    @pytest.mark.anyio
    async def test_ce_result_auto_compute_null_when_no_wtp(self, svc: HEORService):
        result = svc.create_ce_result(CostEffectivenessResultCreate(
            study_id="heor-study-001",
            model_type=ModelType.MARKOV,
            icer=25000.0,
            analyst="Dr. Auto",
        ))
        assert result.cost_effective is None

    @pytest.mark.anyio
    async def test_update_ce_result_recomputes_cost_effective(self, svc: HEORService):
        # ce-result-010 has icer=125000, wtp=100000, cost_effective=False
        updated = svc.update_ce_result(
            "ce-result-010",
            CostEffectivenessResultUpdate(icer=50000.0),
        )
        assert updated is not None
        assert updated.cost_effective is True  # 50K <= 100K

    @pytest.mark.anyio
    async def test_dossier_default_status_and_grade(self, svc: HEORService):
        dossier = svc.create_dossier(ValueDossierCreate(
            trial_id=LIBTAYO_TRIAL,
            product_name="Test",
            indication="Test",
            target_payer_type=PayerType.COMMERCIAL,
            target_market="US",
            clinical_value_summary="Test",
            economic_value_summary="Test",
            unmet_need_description="Test",
            author="Dr. Test",
        ))
        assert dossier.status == DossierStatus.DRAFT
        assert dossier.evidence_grade == EvidenceGrade.MODERATE

    @pytest.mark.anyio
    async def test_payer_evidence_create_default_fields(self, svc: HEORService):
        ev = svc.create_payer_evidence(PayerEvidenceCreate(
            dossier_id="dossier-001",
            payer_name="Test Payer",
            payer_type=PayerType.COMMERCIAL,
            country="US",
            contact_person="Test Contact",
        ))
        assert ev.outcome is None
        assert ev.coverage_decision is None
        assert ev.restrictions == []

    @pytest.mark.anyio
    async def test_metrics_avg_icer_all_deleted(self, svc: HEORService):
        """If all CE results deleted, avg_icer should be None."""
        for rid in list(svc._ce_results.keys()):
            svc.delete_ce_result(rid)
        metrics = svc.get_metrics()
        assert metrics.avg_icer is None
        assert metrics.total_ce_results == 0

    @pytest.mark.anyio
    async def test_list_studies_combined_filters(self, svc: HEORService):
        items = svc.list_studies(
            trial_id=EYLEA_TRIAL,
            analysis_type=AnalysisType.COST_EFFECTIVENESS,
            country="US",
        )
        assert len(items) >= 1
        for s in items:
            assert s.trial_id == EYLEA_TRIAL
            assert s.analysis_type == AnalysisType.COST_EFFECTIVENESS
            assert s.country == "US"

    @pytest.mark.anyio
    async def test_list_dossiers_combined_filters(self, svc: HEORService):
        items = svc.list_dossiers(
            trial_id=DUPIXENT_TRIAL,
            evidence_grade=EvidenceGrade.HIGH,
        )
        for d in items:
            assert d.trial_id == DUPIXENT_TRIAL
            assert d.evidence_grade == EvidenceGrade.HIGH

    @pytest.mark.anyio
    async def test_list_payer_evidence_combined_filters(self, svc: HEORService):
        items = svc.list_payer_evidence(
            dossier_id="dossier-001",
            payer_type=PayerType.COMMERCIAL,
            country="US",
        )
        for p in items:
            assert p.dossier_id == "dossier-001"
            assert p.payer_type == PayerType.COMMERCIAL
            assert p.country == "US"


# ===========================================================================
# EDGE CASES & ERROR HANDLING
# ===========================================================================


class TestEdgeCases:
    """Edge cases and error handling."""

    @pytest.mark.anyio
    async def test_double_delete_study(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/studies/heor-study-001")
        assert resp.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/studies/heor-study-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_double_delete_ce_result(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/ce-results/ce-result-001")
        assert resp.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/ce-results/ce-result-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_double_delete_budget_model(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/budget-models/bim-001")
        assert resp.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/budget-models/bim-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_double_delete_dossier(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/dossiers/dossier-001")
        assert resp.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/dossiers/dossier-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_double_delete_payer_evidence(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/payer-evidence/pe-001")
        assert resp.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/payer-evidence/pe-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_update_deleted_study(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/studies/heor-study-001")
        payload = HEORStudyUpdate(title="Ghost").model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/studies/heor-study-001", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_deleted_ce_result(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/ce-results/ce-result-001")
        payload = CostEffectivenessResultUpdate(icer=1.0).model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/ce-results/ce-result-001", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_deleted_budget_model(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/budget-models/bim-001")
        payload = BudgetImpactModelUpdate(pmpm_impact=99.0).model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/budget-models/bim-001", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_deleted_dossier(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/dossiers/dossier-001")
        payload = ValueDossierUpdate(status=DossierStatus.APPROVED).model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/dossiers/dossier-001", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_deleted_payer_evidence(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/payer-evidence/pe-001")
        payload = PayerEvidenceUpdate(outcome="Denied").model_dump(exclude_unset=True)
        resp = await client.put(f"{API_PREFIX}/payer-evidence/pe-001", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_empty_studies_after_delete_all(self, svc: HEORService):
        for sid in list(svc._studies.keys()):
            svc.delete_study(sid)
        items = svc.list_studies()
        assert len(items) == 0

    @pytest.mark.anyio
    async def test_empty_ce_results_after_delete_all(self, svc: HEORService):
        for rid in list(svc._ce_results.keys()):
            svc.delete_ce_result(rid)
        items = svc.list_ce_results()
        assert len(items) == 0

    @pytest.mark.anyio
    async def test_create_study_data_sources_empty(self, client: AsyncClient):
        payload = HEORStudyCreate(
            trial_id=EYLEA_TRIAL,
            title="No Data Sources",
            analysis_type=AnalysisType.COST_EFFECTIVENESS,
            comparator="Test",
            perspective="Test",
            time_horizon="1 year",
            principal_analyst="Dr. NoData",
            country="US",
        ).model_dump()
        resp = await client.post(f"{API_PREFIX}/studies", json=payload)
        assert resp.status_code == 201
        assert resp.json()["data_sources"] == []

    @pytest.mark.anyio
    async def test_budget_model_with_assumptions(self, client: AsyncClient):
        payload = BudgetImpactModelCreate(
            study_id="heor-study-001",
            target_population_size=100,
            market_share_year1_pct=50.0,
            market_share_year2_pct=60.0,
            market_share_year3_pct=70.0,
            drug_cost_per_patient=1000.0,
            comparator_cost_per_patient=500.0,
            assumptions=["A1", "A2", "A3"],
            modeler="Dr. Assumptions",
        ).model_dump()
        resp = await client.post(f"{API_PREFIX}/budget-models", json=payload)
        assert resp.status_code == 201
        assert len(resp.json()["assumptions"]) == 3

    @pytest.mark.anyio
    async def test_ce_result_seed_007_null_icer(self, client: AsyncClient):
        """ce-result-007 has null ICER (protocol_development study)."""
        resp = await client.get(f"{API_PREFIX}/ce-results/ce-result-007")
        assert resp.status_code == 200
        body = resp.json()
        assert body["icer"] is None
        assert body["cost_effective"] is None

    @pytest.mark.anyio
    async def test_multiple_filters_no_overlap(self, client: AsyncClient):
        """Applying multiple conflicting filters returns empty."""
        resp = await client.get(
            f"{API_PREFIX}/studies",
            params={
                "trial_id": EYLEA_TRIAL,
                "analysis_type": "cost_utility",
                "country": "Germany",
            },
        )
        assert resp.status_code == 200
        # EYLEA has no cost_utility study in Germany
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_study_default_discount_rate(self, client: AsyncClient):
        payload = HEORStudyCreate(
            trial_id=EYLEA_TRIAL,
            title="Default Discount Rate",
            analysis_type=AnalysisType.COST_EFFECTIVENESS,
            comparator="Test",
            perspective="Test",
            time_horizon="Lifetime",
            principal_analyst="Dr. Default",
            country="US",
        ).model_dump()
        resp = await client.post(f"{API_PREFIX}/studies", json=payload)
        assert resp.status_code == 201
        assert resp.json()["discount_rate_pct"] == 3.0
