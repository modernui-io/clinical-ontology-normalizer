"""Tests for Pharmacogenomics Management (PGx-MGT).

Covers:
- Seed data verification (interactions, genotype-phenotypes, test orders, variants, recommendations)
- Drug-gene interaction CRUD (create, read, update, delete, list)
- Genotype-phenotype CRUD
- PGx test order CRUD (with trial_id filter)
- Variant result CRUD (with trial_id filter)
- Dosing recommendation CRUD (with trial_id filter)
- Metrics computation
- Error handling (404s)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.pharmacogenomics_service import (
    PharmacogenomicsService,
    reset_pharmacogenomics_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/pharmacogenomics"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_pharmacogenomics_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> PharmacogenomicsService:
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


def _make_interaction_create(**overrides) -> dict:
    defaults = {
        "drug_name": "TestDrug",
        "gene_symbol": "CYP2D6",
        "interaction_type": "pharmacokinetic",
        "evidence_level": "1a",
        "clinical_significance": "Test significance",
        "guideline_source": "CPIC",
        "description": "Test drug-gene interaction",
    }
    defaults.update(overrides)
    return defaults


def _make_gp_create(**overrides) -> dict:
    defaults = {
        "gene_symbol": "CYP2D6",
        "diplotype": "*1/*10",
        "phenotype": "Intermediate Metabolizer",
        "metabolizer_status": "intermediate",
        "allele_1": "*1",
        "allele_2": "*10",
        "reference_source": "CPIC",
    }
    defaults.update(overrides)
    return defaults


def _make_test_order_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "PT-9999",
        "site_id": "SITE-101",
        "panel_name": "Test PGx Panel",
        "genes_tested": ["CYP2D6", "CYP2C19"],
        "ordered_by": "Dr. Test",
    }
    defaults.update(overrides)
    return defaults


def _make_variant_create(**overrides) -> dict:
    defaults = {
        "test_order_id": "PTO-001",
        "subject_id": "PT-1001",
        "gene_symbol": "CYP2D6",
        "variant_name": "rs1234567",
        "zygosity": "heterozygous",
    }
    defaults.update(overrides)
    return defaults


def _make_recommendation_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "PT-1001",
        "drug_name": "Aflibercept",
        "gene_symbol": "VEGFA",
        "metabolizer_status": "normal",
        "action": "standard_dose",
        "standard_dose": "2 mg intravitreal q8w",
        "recommendation_text": "Standard dose recommended.",
        "evidence_level": "1a",
        "guideline_source": "CPIC",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_interactions_count(self, svc: PharmacogenomicsService):
        items = svc.list_drug_gene_interactions()
        assert len(items) == 12

    def test_seed_genotype_phenotypes_count(self, svc: PharmacogenomicsService):
        items = svc.list_genotype_phenotypes()
        assert len(items) == 12

    def test_seed_test_orders_count(self, svc: PharmacogenomicsService):
        items = svc.list_test_orders()
        assert len(items) == 12

    def test_seed_variant_results_count(self, svc: PharmacogenomicsService):
        items = svc.list_variant_results()
        assert len(items) == 12

    def test_seed_dosing_recommendations_count(self, svc: PharmacogenomicsService):
        items = svc.list_dosing_recommendations()
        assert len(items) == 12

    def test_seed_test_orders_per_trial(self, svc: PharmacogenomicsService):
        eylea = svc.list_test_orders(trial_id=EYLEA_TRIAL)
        dupixent = svc.list_test_orders(trial_id=DUPIXENT_TRIAL)
        libtayo = svc.list_test_orders(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) == 4
        assert len(dupixent) == 4
        assert len(libtayo) == 4

    def test_seed_recommendations_per_trial(self, svc: PharmacogenomicsService):
        eylea = svc.list_dosing_recommendations(trial_id=EYLEA_TRIAL)
        dupixent = svc.list_dosing_recommendations(trial_id=DUPIXENT_TRIAL)
        libtayo = svc.list_dosing_recommendations(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) == 4
        assert len(dupixent) == 4
        assert len(libtayo) == 4

    def test_seed_interactions_have_fields(self, svc: PharmacogenomicsService):
        interaction = svc.get_drug_gene_interaction("DGI-001")
        assert interaction is not None
        assert interaction.drug_name == "Aflibercept"
        assert interaction.gene_symbol == "VEGFA"
        assert interaction.actionable is True

    def test_seed_variant_has_fields(self, svc: PharmacogenomicsService):
        variant = svc.get_variant_result("VR-001")
        assert variant is not None
        assert variant.gene_symbol == "VEGFA"
        assert variant.zygosity == "heterozygous"


# =====================================================================
# DRUG-GENE INTERACTION CRUD
# =====================================================================


class TestDrugGeneInteractionCrud:
    """Test drug-gene interaction CRUD operations."""

    @pytest.mark.anyio
    async def test_list_interactions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-gene-interactions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_get_interaction(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-gene-interactions/DGI-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DGI-001"
        assert data["drug_name"] == "Aflibercept"

    @pytest.mark.anyio
    async def test_get_interaction_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-gene-interactions/DGI-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_interaction(self, client: AsyncClient):
        payload = _make_interaction_create()
        resp = await client.post(f"{API_PREFIX}/drug-gene-interactions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["drug_name"] == "TestDrug"
        assert data["id"].startswith("DGI-")

    @pytest.mark.anyio
    async def test_update_interaction(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/drug-gene-interactions/DGI-001",
            json={"actionable": False, "clinical_significance": "Updated significance"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["actionable"] is False
        assert data["clinical_significance"] == "Updated significance"

    @pytest.mark.anyio
    async def test_update_interaction_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/drug-gene-interactions/DGI-NONEXISTENT",
            json={"actionable": False},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_interaction(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/drug-gene-interactions/DGI-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/drug-gene-interactions/DGI-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_interaction_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/drug-gene-interactions/DGI-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# GENOTYPE-PHENOTYPE CRUD
# =====================================================================


class TestGenotypePhenotypeCrud:
    """Test genotype-phenotype CRUD operations."""

    @pytest.mark.anyio
    async def test_list_genotype_phenotypes(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/genotype-phenotypes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_get_genotype_phenotype(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/genotype-phenotypes/GP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "GP-001"
        assert data["gene_symbol"] == "CYP2D6"

    @pytest.mark.anyio
    async def test_get_genotype_phenotype_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/genotype-phenotypes/GP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_genotype_phenotype(self, client: AsyncClient):
        payload = _make_gp_create()
        resp = await client.post(f"{API_PREFIX}/genotype-phenotypes", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["diplotype"] == "*1/*10"
        assert data["id"].startswith("GP-")

    @pytest.mark.anyio
    async def test_update_genotype_phenotype(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/genotype-phenotypes/GP-001",
            json={"frequency_european_pct": 42.5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["frequency_european_pct"] == 42.5

    @pytest.mark.anyio
    async def test_update_genotype_phenotype_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/genotype-phenotypes/GP-NONEXISTENT",
            json={"frequency_european_pct": 42.5},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_genotype_phenotype(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/genotype-phenotypes/GP-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/genotype-phenotypes/GP-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_genotype_phenotype_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/genotype-phenotypes/GP-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# PGX TEST ORDER CRUD
# =====================================================================


class TestTestOrderCrud:
    """Test PGx test order CRUD operations."""

    @pytest.mark.anyio
    async def test_list_test_orders(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/test-orders")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_test_orders_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/test-orders", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_test_order(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/test-orders/PTO-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PTO-001"
        assert data["panel_name"] == "Ophthalmic PGx Panel"

    @pytest.mark.anyio
    async def test_get_test_order_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/test-orders/PTO-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_test_order(self, client: AsyncClient):
        payload = _make_test_order_create()
        resp = await client.post(f"{API_PREFIX}/test-orders", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["subject_id"] == "PT-9999"
        assert data["status"] == "ordered"
        assert data["id"].startswith("PTO-")

    @pytest.mark.anyio
    async def test_update_test_order(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/test-orders/PTO-008",
            json={"status": "sample_collected", "lab_accession": "LAB-TEST-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "sample_collected"
        assert data["lab_accession"] == "LAB-TEST-001"

    @pytest.mark.anyio
    async def test_update_test_order_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/test-orders/PTO-NONEXISTENT",
            json={"status": "cancelled"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_test_order(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/test-orders/PTO-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/test-orders/PTO-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_test_order_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/test-orders/PTO-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# VARIANT RESULT CRUD
# =====================================================================


class TestVariantResultCrud:
    """Test variant result CRUD operations."""

    @pytest.mark.anyio
    async def test_list_variant_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/variant-results")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_variant_results_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/variant-results", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        # EYLEA trial has PTO-001, PTO-002, PTO-003, PTO-004
        # VR-001, VR-002 (PTO-001), VR-003 (PTO-002), VR-011 (PTO-003) = 4
        assert data["total"] == 4

    @pytest.mark.anyio
    async def test_get_variant_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/variant-results/VR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "VR-001"
        assert data["gene_symbol"] == "VEGFA"

    @pytest.mark.anyio
    async def test_get_variant_result_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/variant-results/VR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_variant_result(self, client: AsyncClient):
        payload = _make_variant_create()
        resp = await client.post(f"{API_PREFIX}/variant-results", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["variant_name"] == "rs1234567"
        assert data["id"].startswith("VR-")

    @pytest.mark.anyio
    async def test_update_variant_result(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/variant-results/VR-003",
            json={"significance": "likely_pathogenic", "interpretation": "Updated interpretation", "reviewed_by": "Dr. Test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["significance"] == "likely_pathogenic"
        assert data["reviewed_by"] == "Dr. Test"

    @pytest.mark.anyio
    async def test_update_variant_result_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/variant-results/VR-NONEXISTENT",
            json={"significance": "benign"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_variant_result(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/variant-results/VR-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/variant-results/VR-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_variant_result_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/variant-results/VR-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# DOSING RECOMMENDATION CRUD
# =====================================================================


class TestDosingRecommendationCrud:
    """Test dosing recommendation CRUD operations."""

    @pytest.mark.anyio
    async def test_list_dosing_recommendations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dosing-recommendations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_dosing_recommendations_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dosing-recommendations", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_get_dosing_recommendation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dosing-recommendations/DR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DR-001"
        assert data["drug_name"] == "Aflibercept"

    @pytest.mark.anyio
    async def test_get_dosing_recommendation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dosing-recommendations/DR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_dosing_recommendation(self, client: AsyncClient):
        payload = _make_recommendation_create()
        resp = await client.post(f"{API_PREFIX}/dosing-recommendations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["drug_name"] == "Aflibercept"
        assert data["id"].startswith("DR-")

    @pytest.mark.anyio
    async def test_update_dosing_recommendation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/dosing-recommendations/DR-004",
            json={"accepted": True, "accepted_by": "Dr. Williams"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["accepted"] is True
        assert data["accepted_by"] == "Dr. Williams"

    @pytest.mark.anyio
    async def test_update_dosing_recommendation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/dosing-recommendations/DR-NONEXISTENT",
            json={"accepted": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_dosing_recommendation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/dosing-recommendations/DR-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/dosing-recommendations/DR-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_dosing_recommendation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/dosing-recommendations/DR-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestPharmacogenomicsMetrics:
    """Test pharmacogenomics metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_interactions"] == 12
        assert data["total_genotype_phenotypes"] == 12
        assert data["total_test_orders"] == 12
        assert data["total_variant_results"] == 12
        assert data["total_recommendations"] == 12
        assert data["avg_turnaround_days"] > 0
        assert 0.0 <= data["recommendation_acceptance_pct"] <= 100.0

    @pytest.mark.anyio
    async def test_get_metrics_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_test_orders"] == 4
        assert data["total_recommendations"] == 4

    @pytest.mark.anyio
    async def test_get_metrics_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_test_orders"] == 0
        assert data["total_recommendations"] == 0

    def test_metrics_actionable_count(self, svc: PharmacogenomicsService):
        metrics = svc.get_metrics()
        actionable = sum(1 for i in svc.list_drug_gene_interactions() if i.actionable)
        assert metrics.actionable_interactions == actionable

    def test_metrics_orders_by_status(self, svc: PharmacogenomicsService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.orders_by_status.values())
        assert total_by_status == metrics.total_test_orders

    def test_metrics_interactions_by_evidence(self, svc: PharmacogenomicsService):
        metrics = svc.get_metrics()
        total_by_evidence = sum(metrics.interactions_by_evidence.values())
        assert total_by_evidence == metrics.total_interactions

    def test_metrics_acceptance_rate(self, svc: PharmacogenomicsService):
        metrics = svc.get_metrics()
        recs = svc.list_dosing_recommendations()
        decided = [r for r in recs if r.accepted is not None]
        accepted = sum(1 for r in decided if r.accepted is True)
        expected_pct = round(accepted / len(decided) * 100.0, 1) if decided else 0.0
        assert abs(metrics.recommendation_acceptance_pct - expected_pct) < 0.2


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_reset_creates_fresh_instance(self):
        from app.services.pharmacogenomics_service import get_pharmacogenomics_service
        svc1 = get_pharmacogenomics_service()
        svc2 = reset_pharmacogenomics_service()
        assert svc1 is not svc2

    def test_get_service_returns_same_instance(self):
        from app.services.pharmacogenomics_service import get_pharmacogenomics_service
        svc1 = get_pharmacogenomics_service()
        svc2 = get_pharmacogenomics_service()
        assert svc1 is svc2

    def test_reset_reseeds_data(self):
        from app.services.pharmacogenomics_service import get_pharmacogenomics_service
        svc = get_pharmacogenomics_service()
        svc.delete_drug_gene_interaction("DGI-001")
        assert svc.get_drug_gene_interaction("DGI-001") is None
        svc2 = reset_pharmacogenomics_service()
        assert svc2.get_drug_gene_interaction("DGI-001") is not None


# =====================================================================
# EDGE CASES
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_all_entities_no_filters(self, client: AsyncClient):
        for path in [
            "drug-gene-interactions",
            "genotype-phenotypes",
            "test-orders",
            "variant-results",
            "dosing-recommendations",
        ]:
            resp = await client.get(f"{API_PREFIX}/{path}")
            assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_filter_empty_trial(self, client: AsyncClient):
        for path in ["test-orders", "variant-results", "dosing-recommendations"]:
            resp = await client.get(f"{API_PREFIX}/{path}", params={"trial_id": "NONEXISTENT"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 0

    @pytest.mark.anyio
    async def test_interaction_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-gene-interactions/DGI-001")
        data = resp.json()
        assert "id" in data
        assert "drug_name" in data
        assert "gene_symbol" in data
        assert "evidence_level" in data
        assert "actionable" in data
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_test_order_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/test-orders/PTO-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "subject_id" in data
        assert "panel_name" in data
        assert "genes_tested" in data
        assert "status" in data

    @pytest.mark.anyio
    async def test_variant_result_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/variant-results/VR-001")
        data = resp.json()
        assert "id" in data
        assert "test_order_id" in data
        assert "gene_symbol" in data
        assert "variant_name" in data
        assert "zygosity" in data
        assert "significance" in data

    @pytest.mark.anyio
    async def test_dosing_recommendation_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dosing-recommendations/DR-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "drug_name" in data
        assert "gene_symbol" in data
        assert "metabolizer_status" in data
        assert "action" in data
        assert "standard_dose" in data
        assert "recommendation_text" in data

    @pytest.mark.anyio
    async def test_metrics_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "total_interactions" in data
        assert "actionable_interactions" in data
        assert "interactions_by_evidence" in data
        assert "total_genotype_phenotypes" in data
        assert "genotypes_by_metabolizer" in data
        assert "total_test_orders" in data
        assert "orders_by_status" in data
        assert "avg_turnaround_days" in data
        assert "total_variant_results" in data
        assert "variants_by_significance" in data
        assert "total_recommendations" in data
        assert "recommendations_by_action" in data
        assert "recommendation_acceptance_pct" in data

    def test_reported_orders_have_turnaround(self, svc: PharmacogenomicsService):
        orders = svc.list_test_orders()
        for o in orders:
            if o.status.value == "reported":
                assert o.turnaround_days is not None
                assert o.turnaround_days > 0

    def test_cancelled_order_no_lab_accession(self, svc: PharmacogenomicsService):
        order = svc.get_test_order("PTO-012")
        assert order is not None
        assert order.status.value == "cancelled"
        assert order.lab_accession is None
