"""Tests for Interim Analysis Management (IA-MGT).

Covers:
- Seed data verification (analysis plans, data cut definitions, DSMB reviews,
  statistical review outcomes)
- Analysis plan CRUD (create, read, update, delete, list, filter by trial/status)
- Data cut definition CRUD (create, read, update, delete, list, filter by trial/status/plan)
- DSMB review CRUD (create, read, update, delete, list, filter by trial/recommendation/cut)
- Statistical review outcome CRUD (create, read, update, delete, list, filter by trial/outcome/cut)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.interim_analysis import (
    AnalysisPlanStatus,
    DSMBRecommendation,
    DataCutStatus,
    ReviewOutcome,
)
from app.services.interim_analysis_service import (
    InterimAnalysisService,
    get_interim_analysis_service,
    reset_interim_analysis_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/interim-analysis"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_interim_analysis_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> InterimAnalysisService:
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


def _make_plan_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "plan_name": "Test Analysis Plan",
        "version": "1.0",
        "primary_endpoint": "Overall survival at Week 52",
        "authored_by": "Dr. Test Author",
        "planned_analyses_count": 2,
    }
    defaults.update(overrides)
    return defaults


def _make_data_cut_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "analysis_plan_id": "IAP-001",
        "cut_name": "Test Data Cut",
        "responsible_statistician": "Dr. Test Statistician",
        "target_enrollment": 200,
        "target_events": 100,
    }
    defaults.update(overrides)
    return defaults


def _make_dsmb_review_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "data_cut_id": "DCT-001",
        "meeting_date": "2026-01-15T14:00:00Z",
        "meeting_number": 5,
        "chair_name": "Prof. Test Chair",
        "attendees_count": 6,
    }
    defaults.update(overrides)
    return defaults


def _make_outcome_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "data_cut_id": "DCT-001",
        "reviewed_by": "Dr. Test Reviewer",
        "review_date": "2026-01-16T10:00:00Z",
    }
    defaults.update(overrides)
    return defaults


# ===================================================================
# SEED DATA VERIFICATION
# ===================================================================


class TestSeedData:
    """Verify all 4 entity types are seeded with 12 records each."""

    @pytest.mark.anyio
    async def test_seed_analysis_plans(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/analysis-plans")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_seed_data_cut_definitions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-cut-definitions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_dsmb_reviews(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dsmb-reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_statistical_review_outcomes(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/statistical-review-outcomes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12


# ===================================================================
# ANALYSIS PLAN CRUD
# ===================================================================


class TestAnalysisPlanCRUD:
    @pytest.mark.anyio
    async def test_list_analysis_plans(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/analysis-plans")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_analysis_plan(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/analysis-plans/IAP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "IAP-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_analysis_plan_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/analysis-plans/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_analysis_plan(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/analysis-plans", json=_make_plan_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("IAP-")
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["analysis_plan_status"] == "draft"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/analysis-plans")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/analysis-plans", json=_make_plan_create())
        resp2 = await client.get(f"{API_PREFIX}/analysis-plans")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_analysis_plan(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/analysis-plans/IAP-001",
            json={"analysis_plan_status": "completed", "notes": "All analyses done"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["analysis_plan_status"] == "completed"
        assert data["notes"] == "All analyses done"

    @pytest.mark.anyio
    async def test_update_analysis_plan_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/analysis-plans/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_analysis_plan(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/analysis-plans/IAP-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/analysis-plans/IAP-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_analysis_plan_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/analysis-plans/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/analysis-plans", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_filter_by_analysis_plan_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/analysis-plans", params={"analysis_plan_status": "approved"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["analysis_plan_status"] == "approved"


# ===================================================================
# DATA CUT DEFINITION CRUD
# ===================================================================


class TestDataCutDefinitionCRUD:
    @pytest.mark.anyio
    async def test_list_data_cut_definitions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-cut-definitions")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_data_cut_definition(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-cut-definitions/DCT-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "DCT-001"

    @pytest.mark.anyio
    async def test_get_data_cut_definition_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-cut-definitions/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_data_cut_definition(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/data-cut-definitions", json=_make_data_cut_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("DCT-")
        assert data["data_cut_status"] == "planned"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/data-cut-definitions")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/data-cut-definitions", json=_make_data_cut_create())
        resp2 = await client.get(f"{API_PREFIX}/data-cut-definitions")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_data_cut_definition(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/data-cut-definitions/DCT-001",
            json={"data_cut_status": "validated", "notes": "Validated by statistician"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data_cut_status"] == "validated"
        assert data["notes"] == "Validated by statistician"

    @pytest.mark.anyio
    async def test_update_data_cut_definition_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/data-cut-definitions/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_data_cut_definition(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/data-cut-definitions/DCT-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_data_cut_definition_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/data-cut-definitions/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_data_cut_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/data-cut-definitions", params={"data_cut_status": "completed"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["data_cut_status"] == "completed"

    @pytest.mark.anyio
    async def test_filter_by_analysis_plan_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/data-cut-definitions", params={"analysis_plan_id": "IAP-001"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["analysis_plan_id"] == "IAP-001"

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/data-cut-definitions", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL


# ===================================================================
# DSMB REVIEW CRUD
# ===================================================================


class TestDSMBReviewCRUD:
    @pytest.mark.anyio
    async def test_list_dsmb_reviews(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dsmb-reviews")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_dsmb_review(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dsmb-reviews/DSMB-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "DSMB-001"

    @pytest.mark.anyio
    async def test_get_dsmb_review_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dsmb-reviews/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_dsmb_review(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/dsmb-reviews", json=_make_dsmb_review_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("DSMB-")
        assert data["chair_name"] == "Prof. Test Chair"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/dsmb-reviews")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/dsmb-reviews", json=_make_dsmb_review_create())
        resp2 = await client.get(f"{API_PREFIX}/dsmb-reviews")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_dsmb_review(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/dsmb-reviews/DSMB-001",
            json={"dsmb_recommendation": "modify_protocol", "notes": "Protocol change recommended"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dsmb_recommendation"] == "modify_protocol"
        assert data["notes"] == "Protocol change recommended"

    @pytest.mark.anyio
    async def test_update_dsmb_review_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/dsmb-reviews/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_dsmb_review(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/dsmb-reviews/DSMB-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_dsmb_review_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/dsmb-reviews/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_dsmb_recommendation(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/dsmb-reviews",
            params={"dsmb_recommendation": "continue_as_planned"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["dsmb_recommendation"] == "continue_as_planned"

    @pytest.mark.anyio
    async def test_filter_by_data_cut_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/dsmb-reviews", params={"data_cut_id": "DCT-001"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["data_cut_id"] == "DCT-001"

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/dsmb-reviews", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL


# ===================================================================
# STATISTICAL REVIEW OUTCOME CRUD
# ===================================================================


class TestStatisticalReviewOutcomeCRUD:
    @pytest.mark.anyio
    async def test_list_statistical_review_outcomes(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/statistical-review-outcomes")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_statistical_review_outcome(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/statistical-review-outcomes/SRO-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "SRO-001"

    @pytest.mark.anyio
    async def test_get_statistical_review_outcome_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/statistical-review-outcomes/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_statistical_review_outcome(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/statistical-review-outcomes", json=_make_outcome_create()
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("SRO-")
        assert data["reviewed_by"] == "Dr. Test Reviewer"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/statistical-review-outcomes")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/statistical-review-outcomes", json=_make_outcome_create())
        resp2 = await client.get(f"{API_PREFIX}/statistical-review-outcomes")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_statistical_review_outcome(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/statistical-review-outcomes/SRO-001",
            json={"review_outcome": "favorable", "notes": "Positive trend observed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["review_outcome"] == "favorable"
        assert data["notes"] == "Positive trend observed"

    @pytest.mark.anyio
    async def test_update_statistical_review_outcome_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/statistical-review-outcomes/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_statistical_review_outcome(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/statistical-review-outcomes/SRO-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/statistical-review-outcomes/SRO-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_statistical_review_outcome_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/statistical-review-outcomes/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_review_outcome(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/statistical-review-outcomes",
            params={"review_outcome": "favorable"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["review_outcome"] == "favorable"

    @pytest.mark.anyio
    async def test_filter_by_data_cut_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/statistical-review-outcomes", params={"data_cut_id": "DCT-001"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["data_cut_id"] == "DCT-001"

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/statistical-review-outcomes", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL


# ===================================================================
# METRICS
# ===================================================================


class TestMetrics:
    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_analysis_plans" in data
        assert "total_data_cuts" in data
        assert "total_dsmb_reviews" in data
        assert "total_statistical_outcomes" in data
        assert "data_cut_completion_rate" in data
        assert "boundary_crossing_rate" in data

    @pytest.mark.anyio
    async def test_metrics_total_analysis_plans(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_analysis_plans"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_data_cuts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_data_cuts"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_dsmb_reviews(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_dsmb_reviews"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_statistical_outcomes(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_statistical_outcomes"] == 12

    @pytest.mark.anyio
    async def test_metrics_has_breakdowns(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert isinstance(data["plans_by_status"], dict)
        assert isinstance(data["cuts_by_status"], dict)
        assert isinstance(data["reviews_by_recommendation"], dict)
        assert isinstance(data["outcomes_by_result"], dict)

    @pytest.mark.anyio
    async def test_metrics_filtered_by_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_analysis_plans"] == 4  # IAP-001 through IAP-004
        assert data["total_data_cuts"] == 4  # DCT-001 through DCT-004

    def test_metrics_service_level(self, svc: InterimAnalysisService):
        metrics = svc.get_metrics()
        assert metrics.total_analysis_plans == 12
        assert metrics.total_data_cuts == 12
        assert metrics.total_dsmb_reviews == 12
        assert metrics.total_statistical_outcomes == 12


# ===================================================================
# EDGE CASES & UPDATE PRESERVATION
# ===================================================================


class TestEdgeCases:
    @pytest.mark.anyio
    async def test_update_plan_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/analysis-plans/IAP-001")
        original = resp.json()
        original_name = original["plan_name"]

        resp2 = await client.put(
            f"{API_PREFIX}/analysis-plans/IAP-001",
            json={"notes": "Partial update"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["plan_name"] == original_name
        assert updated["notes"] == "Partial update"

    @pytest.mark.anyio
    async def test_update_data_cut_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-cut-definitions/DCT-001")
        original = resp.json()
        original_name = original["cut_name"]

        resp2 = await client.put(
            f"{API_PREFIX}/data-cut-definitions/DCT-001",
            json={"notes": "Updated data cut note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["cut_name"] == original_name

    @pytest.mark.anyio
    async def test_update_dsmb_review_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dsmb-reviews/DSMB-001")
        original = resp.json()
        original_chair = original["chair_name"]

        resp2 = await client.put(
            f"{API_PREFIX}/dsmb-reviews/DSMB-001",
            json={"notes": "Updated review note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["chair_name"] == original_chair

    @pytest.mark.anyio
    async def test_update_outcome_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/statistical-review-outcomes/SRO-001")
        original = resp.json()
        original_reviewer = original["reviewed_by"]

        resp2 = await client.put(
            f"{API_PREFIX}/statistical-review-outcomes/SRO-001",
            json={"notes": "Updated outcome note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["reviewed_by"] == original_reviewer


# ===================================================================
# SINGLETON PATTERN
# ===================================================================


class TestSingleton:
    def test_get_returns_same_instance(self):
        svc1 = get_interim_analysis_service()
        svc2 = get_interim_analysis_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        svc1 = get_interim_analysis_service()
        svc2 = reset_interim_analysis_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_interim_analysis_service()
        svc.delete_analysis_plan("IAP-001")
        assert svc.get_analysis_plan("IAP-001") is None
        svc2 = reset_interim_analysis_service()
        assert svc2.get_analysis_plan("IAP-001") is not None


# ===================================================================
# SERVICE-LEVEL CRUD
# ===================================================================


class TestServiceLevelCRUD:
    def test_list_analysis_plans_service(self, svc: InterimAnalysisService):
        items = svc.list_analysis_plans()
        assert len(items) == 12

    def test_get_analysis_plan_service(self, svc: InterimAnalysisService):
        record = svc.get_analysis_plan("IAP-001")
        assert record is not None
        assert record.id == "IAP-001"

    def test_list_data_cut_definitions_service(self, svc: InterimAnalysisService):
        items = svc.list_data_cut_definitions()
        assert len(items) == 12

    def test_get_data_cut_definition_service(self, svc: InterimAnalysisService):
        record = svc.get_data_cut_definition("DCT-001")
        assert record is not None
        assert record.id == "DCT-001"

    def test_list_dsmb_reviews_service(self, svc: InterimAnalysisService):
        items = svc.list_dsmb_reviews()
        assert len(items) == 12

    def test_get_dsmb_review_service(self, svc: InterimAnalysisService):
        record = svc.get_dsmb_review("DSMB-001")
        assert record is not None
        assert record.id == "DSMB-001"

    def test_list_statistical_review_outcomes_service(self, svc: InterimAnalysisService):
        items = svc.list_statistical_review_outcomes()
        assert len(items) == 12

    def test_get_statistical_review_outcome_service(self, svc: InterimAnalysisService):
        record = svc.get_statistical_review_outcome("SRO-001")
        assert record is not None
        assert record.id == "SRO-001"

    def test_delete_analysis_plan_service(self, svc: InterimAnalysisService):
        assert svc.delete_analysis_plan("IAP-001") is True
        assert svc.get_analysis_plan("IAP-001") is None

    def test_delete_nonexistent_returns_false(self, svc: InterimAnalysisService):
        assert svc.delete_analysis_plan("NONEXISTENT") is False

    def test_filter_plans_by_trial(self, svc: InterimAnalysisService):
        items = svc.list_analysis_plans(trial_id=EYLEA_TRIAL)
        for item in items:
            assert item.trial_id == EYLEA_TRIAL

    def test_filter_plans_by_status(self, svc: InterimAnalysisService):
        items = svc.list_analysis_plans(analysis_plan_status=AnalysisPlanStatus.APPROVED)
        for item in items:
            assert item.analysis_plan_status == AnalysisPlanStatus.APPROVED

    def test_filter_cuts_by_status(self, svc: InterimAnalysisService):
        items = svc.list_data_cut_definitions(data_cut_status=DataCutStatus.COMPLETED)
        for item in items:
            assert item.data_cut_status == DataCutStatus.COMPLETED

    def test_filter_reviews_by_recommendation(self, svc: InterimAnalysisService):
        items = svc.list_dsmb_reviews(dsmb_recommendation=DSMBRecommendation.CONTINUE_AS_PLANNED)
        for item in items:
            assert item.dsmb_recommendation == DSMBRecommendation.CONTINUE_AS_PLANNED

    def test_filter_outcomes_by_result(self, svc: InterimAnalysisService):
        items = svc.list_statistical_review_outcomes(review_outcome=ReviewOutcome.FAVORABLE)
        for item in items:
            assert item.review_outcome == ReviewOutcome.FAVORABLE


# ===================================================================
# BULK / MULTI-ENTITY
# ===================================================================


class TestBulkOperations:
    @pytest.mark.anyio
    async def test_create_multiple_analysis_plans(self, client: AsyncClient):
        for i in range(3):
            resp = await client.post(
                f"{API_PREFIX}/analysis-plans",
                json=_make_plan_create(plan_name=f"Bulk Plan {i}"),
            )
            assert resp.status_code == 201
        resp = await client.get(f"{API_PREFIX}/analysis-plans")
        assert resp.json()["total"] == 15  # 12 seed + 3 new

    @pytest.mark.anyio
    async def test_delete_multiple_outcomes(self, client: AsyncClient):
        for outcome_id in ["SRO-001", "SRO-002", "SRO-003"]:
            resp = await client.delete(f"{API_PREFIX}/statistical-review-outcomes/{outcome_id}")
            assert resp.status_code == 204
        resp = await client.get(f"{API_PREFIX}/statistical-review-outcomes")
        assert resp.json()["total"] == 9  # 12 seed - 3 deleted


# ===================================================================
# RESPONSE STRUCTURE
# ===================================================================


class TestAPIResponseStructure:
    @pytest.mark.anyio
    async def test_analysis_plan_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/analysis-plans/IAP-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "plan_name", "version", "analysis_plan_status",
            "primary_endpoint", "authored_by", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_data_cut_definition_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-cut-definitions/DCT-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "analysis_plan_id", "cut_name", "data_cut_status",
            "responsible_statistician", "blinding_status", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_dsmb_review_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dsmb-reviews/DSMB-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "data_cut_id", "meeting_date", "meeting_number",
            "dsmb_recommendation", "chair_name", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_statistical_review_outcome_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/statistical-review-outcomes/SRO-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "data_cut_id", "review_outcome",
            "reviewed_by", "review_date", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_list_response_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/analysis-plans")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
