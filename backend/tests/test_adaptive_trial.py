"""Tests for Adaptive Trial Design Management (ADAPT-TRIAL).

Covers:
- Seed data verification (interim analyses, adaptation decisions, SSR, futility, arm mods)
- Interim analysis CRUD (create, read, update, delete, list, filter by trial/type/outcome)
- Adaptation decision CRUD (create, read, update, delete, list, filter by trial/type/status)
- Sample size re-estimation CRUD (create, read, update, delete, list, filter by trial)
- Futility assessment CRUD (create, read, update, delete, list, filter by trial/result)
- Treatment arm modification CRUD (create, read, update, delete, list, filter by trial/type)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.adaptive_trial import (
    AdaptationType,
    AnalysisOutcome,
    AnalysisType,
    DecisionStatus,
    FutilityResult,
)
from app.services.adaptive_trial_service import (
    AdaptiveTrialService,
    get_adaptive_trial_service,
    reset_adaptive_trial_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/adaptive-trial"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_adaptive_trial_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> AdaptiveTrialService:
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


def _make_interim_analysis_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "analysis_type": "interim",
        "planned_date": (now + timedelta(days=30)).isoformat(),
        "performed_by": "Dr. Test Statistician",
        "analysis_number": 5,
        "spending_function": "OBrien-Fleming",
    }
    defaults.update(overrides)
    return defaults


def _make_adaptation_decision_create(**overrides) -> dict:
    defaults = {
        "trial_id": DUPIXENT_TRIAL,
        "adaptation_type": "sample_size",
        "rationale": "Test rationale for adaptation",
        "proposed_change": "Increase sample size by 10%",
        "proposed_by": "Dr. Test Proposer",
    }
    defaults.update(overrides)
    return defaults


def _make_ssr_create(**overrides) -> dict:
    defaults = {
        "trial_id": LIBTAYO_TRIAL,
        "statistician": "Dr. Test Statistician",
        "original_sample_size": 400,
        "target_power": 0.80,
    }
    defaults.update(overrides)
    return defaults


def _make_futility_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "recommendation": "Continue enrollment pending further data",
        "assessed_by": "Dr. Test Assessor",
        "conditional_power": 0.65,
    }
    defaults.update(overrides)
    return defaults


def _make_tam_create(**overrides) -> dict:
    defaults = {
        "trial_id": LIBTAYO_TRIAL,
        "arm_name": "Test Arm",
        "modification_type": "drop",
        "reason": "Futility in test arm",
        "modified_by": "Dr. Test Modifier",
        "subjects_affected": 25,
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_interim_analyses_count(self, svc: AdaptiveTrialService):
        analyses = svc.list_interim_analyses()
        assert len(analyses) == 12

    def test_seed_adaptation_decisions_count(self, svc: AdaptiveTrialService):
        decisions = svc.list_adaptation_decisions()
        assert len(decisions) == 10

    def test_seed_sample_size_reestimations_count(self, svc: AdaptiveTrialService):
        reestimations = svc.list_sample_size_reestimations()
        assert len(reestimations) == 10

    def test_seed_futility_assessments_count(self, svc: AdaptiveTrialService):
        assessments = svc.list_futility_assessments()
        assert len(assessments) == 10

    def test_seed_treatment_arm_modifications_count(self, svc: AdaptiveTrialService):
        mods = svc.list_treatment_arm_modifications()
        assert len(mods) == 10

    def test_seed_analyses_cover_all_trials(self, svc: AdaptiveTrialService):
        analyses = svc.list_interim_analyses()
        trial_ids = {a.trial_id for a in analyses}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_analyses_have_multiple_types(self, svc: AdaptiveTrialService):
        analyses = svc.list_interim_analyses()
        types = {a.analysis_type for a in analyses}
        assert len(types) >= 4

    def test_seed_decisions_have_multiple_statuses(self, svc: AdaptiveTrialService):
        decisions = svc.list_adaptation_decisions()
        statuses = {d.status for d in decisions}
        assert DecisionStatus.IMPLEMENTED in statuses
        assert DecisionStatus.PROPOSED in statuses

    def test_seed_futility_has_futile_result(self, svc: AdaptiveTrialService):
        assessments = svc.list_futility_assessments()
        results = {a.result for a in assessments}
        assert FutilityResult.FUTILE in results
        assert FutilityResult.NOT_FUTILE in results

    def test_seed_arm_mods_have_drop_type(self, svc: AdaptiveTrialService):
        mods = svc.list_treatment_arm_modifications()
        types = {m.modification_type for m in mods}
        assert "drop" in types
        assert "add" in types


# =====================================================================
# INTERIM ANALYSIS CRUD
# =====================================================================


class TestInterimAnalysisCrud:
    """Test interim analysis CRUD operations."""

    @pytest.mark.anyio
    async def test_list_interim_analyses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/interim-analyses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_interim_analyses_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/interim-analyses", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_interim_analyses_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/interim-analyses", params={"analysis_type": "safety"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["analysis_type"] == "safety"

    @pytest.mark.anyio
    async def test_list_interim_analyses_filter_outcome(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/interim-analyses", params={"outcome": "continue"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["outcome"] == "continue"

    @pytest.mark.anyio
    async def test_get_interim_analysis(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/interim-analyses/IA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "IA-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["analysis_type"] == "interim"

    @pytest.mark.anyio
    async def test_get_interim_analysis_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/interim-analyses/IA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_interim_analysis(self, client: AsyncClient):
        payload = _make_interim_analysis_create()
        resp = await client.post(f"{API_PREFIX}/interim-analyses", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["analysis_type"] == "interim"
        assert data["outcome"] == "pending"
        assert data["id"].startswith("IA-")

    @pytest.mark.anyio
    async def test_update_interim_analysis(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/interim-analyses/IA-011",
            json={"outcome": "continue", "dsmb_reviewed": True, "notes": "Completed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["outcome"] == "continue"
        assert data["dsmb_reviewed"] is True
        assert data["notes"] == "Completed"

    @pytest.mark.anyio
    async def test_update_interim_analysis_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/interim-analyses/IA-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_interim_analysis(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/interim-analyses/IA-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/interim-analyses/IA-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_interim_analysis_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/interim-analyses/IA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# ADAPTATION DECISION CRUD
# =====================================================================


class TestAdaptationDecisionCrud:
    """Test adaptation decision CRUD operations."""

    @pytest.mark.anyio
    async def test_list_adaptation_decisions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adaptation-decisions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_adaptation_decisions_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/adaptation-decisions", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_adaptation_decisions_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/adaptation-decisions", params={"adaptation_type": "sample_size"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["adaptation_type"] == "sample_size"

    @pytest.mark.anyio
    async def test_list_adaptation_decisions_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/adaptation-decisions", params={"status": "implemented"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "implemented"

    @pytest.mark.anyio
    async def test_get_adaptation_decision(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adaptation-decisions/AD-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "AD-001"
        assert data["adaptation_type"] == "population_enrichment"

    @pytest.mark.anyio
    async def test_get_adaptation_decision_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adaptation-decisions/AD-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_adaptation_decision(self, client: AsyncClient):
        payload = _make_adaptation_decision_create()
        resp = await client.post(f"{API_PREFIX}/adaptation-decisions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == DUPIXENT_TRIAL
        assert data["adaptation_type"] == "sample_size"
        assert data["status"] == "proposed"
        assert data["id"].startswith("AD-")

    @pytest.mark.anyio
    async def test_update_adaptation_decision(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/adaptation-decisions/AD-009",
            json={"status": "approved", "approved_by": "Dr. Review Board"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["approved_by"] == "Dr. Review Board"

    @pytest.mark.anyio
    async def test_update_adaptation_decision_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/adaptation-decisions/AD-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_adaptation_decision(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/adaptation-decisions/AD-007")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/adaptation-decisions/AD-007")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_adaptation_decision_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/adaptation-decisions/AD-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# SAMPLE SIZE RE-ESTIMATION CRUD
# =====================================================================


class TestSampleSizeReestimationCrud:
    """Test sample size re-estimation CRUD operations."""

    @pytest.mark.anyio
    async def test_list_reestimations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sample-size-reestimations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_reestimations_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/sample-size-reestimations", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_get_reestimation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sample-size-reestimations/SSR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SSR-001"
        assert data["original_sample_size"] == 300

    @pytest.mark.anyio
    async def test_get_reestimation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sample-size-reestimations/SSR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_reestimation(self, client: AsyncClient):
        payload = _make_ssr_create()
        resp = await client.post(f"{API_PREFIX}/sample-size-reestimations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == LIBTAYO_TRIAL
        assert data["original_sample_size"] == 400
        assert data["id"].startswith("SSR-")

    @pytest.mark.anyio
    async def test_update_reestimation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sample-size-reestimations/SSR-010",
            json={"new_sample_size": 380, "approved_by": "Dr. Approver"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["new_sample_size"] == 380
        assert data["approved_by"] == "Dr. Approver"

    @pytest.mark.anyio
    async def test_update_reestimation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sample-size-reestimations/SSR-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_reestimation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sample-size-reestimations/SSR-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/sample-size-reestimations/SSR-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_reestimation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sample-size-reestimations/SSR-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# FUTILITY ASSESSMENT CRUD
# =====================================================================


class TestFutilityAssessmentCrud:
    """Test futility assessment CRUD operations."""

    @pytest.mark.anyio
    async def test_list_futility_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/futility-assessments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_futility_assessments_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/futility-assessments", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_futility_assessments_filter_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/futility-assessments", params={"result": "futile"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["result"] == "futile"

    @pytest.mark.anyio
    async def test_get_futility_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/futility-assessments/FA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "FA-001"
        assert data["result"] == "not_futile"

    @pytest.mark.anyio
    async def test_get_futility_assessment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/futility-assessments/FA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_futility_assessment(self, client: AsyncClient):
        payload = _make_futility_create()
        resp = await client.post(f"{API_PREFIX}/futility-assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["result"] == "not_futile"
        assert data["id"].startswith("FA-")

    @pytest.mark.anyio
    async def test_update_futility_assessment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/futility-assessments/FA-010",
            json={"result": "not_futile", "dsmb_concurrence": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"] == "not_futile"
        assert data["dsmb_concurrence"] is True

    @pytest.mark.anyio
    async def test_update_futility_assessment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/futility-assessments/FA-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_futility_assessment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/futility-assessments/FA-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/futility-assessments/FA-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_futility_assessment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/futility-assessments/FA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# TREATMENT ARM MODIFICATION CRUD
# =====================================================================


class TestTreatmentArmModificationCrud:
    """Test treatment arm modification CRUD operations."""

    @pytest.mark.anyio
    async def test_list_arm_modifications(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/treatment-arm-modifications")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_arm_modifications_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/treatment-arm-modifications", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_arm_modifications_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/treatment-arm-modifications", params={"modification_type": "drop"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["modification_type"] == "drop"

    @pytest.mark.anyio
    async def test_get_arm_modification(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/treatment-arm-modifications/TAM-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "TAM-001"
        assert data["modification_type"] == "drop"

    @pytest.mark.anyio
    async def test_get_arm_modification_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/treatment-arm-modifications/TAM-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_arm_modification(self, client: AsyncClient):
        payload = _make_tam_create()
        resp = await client.post(f"{API_PREFIX}/treatment-arm-modifications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == LIBTAYO_TRIAL
        assert data["arm_name"] == "Test Arm"
        assert data["modification_type"] == "drop"
        assert data["id"].startswith("TAM-")

    @pytest.mark.anyio
    async def test_update_arm_modification(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/treatment-arm-modifications/TAM-007",
            json={"regulatory_approved": True, "irb_approved": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["regulatory_approved"] is True
        assert data["irb_approved"] is True

    @pytest.mark.anyio
    async def test_update_arm_modification_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/treatment-arm-modifications/TAM-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_arm_modification(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/treatment-arm-modifications/TAM-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/treatment-arm-modifications/TAM-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_arm_modification_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/treatment-arm-modifications/TAM-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestAdaptiveTrialMetrics:
    """Test adaptive trial metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_interim_analyses"] == 12
        assert data["total_adaptations"] == 10
        assert data["total_reestimations"] == 10
        assert data["total_futility_assessments"] == 10
        assert data["total_arm_modifications"] == 10

    @pytest.mark.anyio
    async def test_metrics_analyses_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_type = data["analyses_by_type"]
        total = sum(by_type.values())
        assert total == data["total_interim_analyses"]

    @pytest.mark.anyio
    async def test_metrics_analyses_by_outcome(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_outcome = data["analyses_by_outcome"]
        total = sum(by_outcome.values())
        assert total == data["total_interim_analyses"]

    @pytest.mark.anyio
    async def test_metrics_adaptations_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_type = data["adaptations_by_type"]
        total = sum(by_type.values())
        assert total == data["total_adaptations"]

    @pytest.mark.anyio
    async def test_metrics_adaptations_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["adaptations_by_status"]
        total = sum(by_status.values())
        assert total == data["total_adaptations"]

    @pytest.mark.anyio
    async def test_metrics_implemented_adaptations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["implemented_adaptations"] > 0
        assert data["implemented_adaptations"] <= data["total_adaptations"]

    @pytest.mark.anyio
    async def test_metrics_futility_by_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_result = data["futility_by_result"]
        total = sum(by_result.values())
        assert total == data["total_futility_assessments"]

    @pytest.mark.anyio
    async def test_metrics_arms_dropped_and_added(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["arms_dropped"] >= 1
        assert data["arms_added"] >= 1

    def test_metrics_avg_sample_size_change(self, svc: AdaptiveTrialService):
        metrics = svc.get_metrics()
        # Average should be a reasonable number (some positive, some negative changes)
        assert isinstance(metrics.avg_sample_size_change_pct, float)


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_adaptive_trial_service()
        svc2 = get_adaptive_trial_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_adaptive_trial_service()
        svc2 = reset_adaptive_trial_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_adaptive_trial_service()
        # Delete an analysis
        svc.delete_interim_analysis("IA-001")
        assert svc.get_interim_analysis("IA-001") is None
        # Reset should bring it back
        svc2 = reset_adaptive_trial_service()
        assert svc2.get_interim_analysis("IA-001") is not None


# =====================================================================
# FILTERING AND EDGE CASES
# =====================================================================


class TestFilteringAndEdgeCases:
    """Test filtering combinations and edge cases."""

    @pytest.mark.anyio
    async def test_list_analyses_empty_filter(self, client: AsyncClient):
        """Filter by a trial that has no analyses."""
        resp = await client.get(
            f"{API_PREFIX}/interim-analyses",
            params={"trial_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.anyio
    async def test_list_decisions_empty_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/adaptation-decisions",
            params={"status": "deferred", "trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 200
        # EYLEA doesn't have deferred decisions
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_futility_possibly_futile(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/futility-assessments", params={"result": "possibly_futile"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["result"] == "possibly_futile"

    @pytest.mark.anyio
    async def test_create_analysis_then_retrieve(self, client: AsyncClient):
        """Create an analysis and verify it shows in the list."""
        payload = _make_interim_analysis_create()
        resp = await client.post(f"{API_PREFIX}/interim-analyses", json=payload)
        assert resp.status_code == 201
        created_id = resp.json()["id"]

        resp2 = await client.get(f"{API_PREFIX}/interim-analyses/{created_id}")
        assert resp2.status_code == 200
        assert resp2.json()["id"] == created_id

    @pytest.mark.anyio
    async def test_create_decision_then_update_status(self, client: AsyncClient):
        """Create a decision, then update its status through lifecycle."""
        payload = _make_adaptation_decision_create()
        resp = await client.post(f"{API_PREFIX}/adaptation-decisions", json=payload)
        assert resp.status_code == 201
        decision_id = resp.json()["id"]
        assert resp.json()["status"] == "proposed"

        # Update to under_review
        resp2 = await client.put(
            f"{API_PREFIX}/adaptation-decisions/{decision_id}",
            json={"status": "under_review"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "under_review"

        # Update to approved
        resp3 = await client.put(
            f"{API_PREFIX}/adaptation-decisions/{decision_id}",
            json={"status": "approved", "approved_by": "Dr. Board Chair"},
        )
        assert resp3.status_code == 200
        assert resp3.json()["status"] == "approved"
        assert resp3.json()["approved_by"] == "Dr. Board Chair"

    @pytest.mark.anyio
    async def test_create_and_delete_ssr(self, client: AsyncClient):
        """Create a re-estimation and then delete it."""
        payload = _make_ssr_create()
        resp = await client.post(f"{API_PREFIX}/sample-size-reestimations", json=payload)
        assert resp.status_code == 201
        ssr_id = resp.json()["id"]

        resp2 = await client.delete(f"{API_PREFIX}/sample-size-reestimations/{ssr_id}")
        assert resp2.status_code == 204

        resp3 = await client.get(f"{API_PREFIX}/sample-size-reestimations/{ssr_id}")
        assert resp3.status_code == 404

    @pytest.mark.anyio
    async def test_create_futility_with_analysis_id(self, client: AsyncClient):
        """Create a futility assessment linked to an analysis."""
        payload = _make_futility_create(analysis_id="IA-002")
        resp = await client.post(f"{API_PREFIX}/futility-assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["analysis_id"] == "IA-002"

    @pytest.mark.anyio
    async def test_create_tam_with_decision_id(self, client: AsyncClient):
        """Create a treatment arm modification linked to a decision."""
        payload = _make_tam_create(decision_id="AD-003")
        resp = await client.post(f"{API_PREFIX}/treatment-arm-modifications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["decision_id"] == "AD-003"

    @pytest.mark.anyio
    async def test_analyses_sorted_by_planned_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/interim-analyses")
        data = resp.json()
        dates = [item["planned_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_decisions_sorted_by_decision_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adaptation-decisions")
        data = resp.json()
        dates = [item["decision_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_metrics_after_create_and_delete(self, client: AsyncClient):
        """Metrics should reflect dynamic changes."""
        # Get baseline metrics
        resp1 = await client.get(f"{API_PREFIX}/metrics")
        baseline = resp1.json()

        # Create a new analysis
        payload = _make_interim_analysis_create()
        await client.post(f"{API_PREFIX}/interim-analyses", json=payload)

        resp2 = await client.get(f"{API_PREFIX}/metrics")
        after_create = resp2.json()
        assert after_create["total_interim_analyses"] == baseline["total_interim_analyses"] + 1

        # Delete an analysis
        await client.delete(f"{API_PREFIX}/interim-analyses/IA-012")
        resp3 = await client.get(f"{API_PREFIX}/metrics")
        after_delete = resp3.json()
        assert after_delete["total_interim_analyses"] == baseline["total_interim_analyses"]


# =====================================================================
# ENUM COVERAGE
# =====================================================================


class TestEnumCoverage:
    """Verify enum values are represented in seed data."""

    @pytest.mark.anyio
    async def test_analysis_types_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/interim-analyses")
        data = resp.json()
        types = {item["analysis_type"] for item in data["items"]}
        assert "interim" in types
        assert "safety" in types
        assert "futility" in types
        assert "efficacy" in types
        assert "sample_size_reestimation" in types
        assert "dose_selection" in types

    @pytest.mark.anyio
    async def test_analysis_outcomes_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/interim-analyses")
        data = resp.json()
        outcomes = {item["outcome"] for item in data["items"]}
        assert "continue" in outcomes
        assert "modify" in outcomes
        assert "pending" in outcomes
        assert "stop_efficacy" in outcomes

    @pytest.mark.anyio
    async def test_adaptation_types_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adaptation-decisions")
        data = resp.json()
        types = {item["adaptation_type"] for item in data["items"]}
        assert "sample_size" in types
        assert "treatment_arm_drop" in types
        assert "treatment_arm_add" in types
        assert "dose_modification" in types
        assert "endpoint_change" in types
        assert "population_enrichment" in types
        assert "randomization_ratio" in types

    @pytest.mark.anyio
    async def test_decision_statuses_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adaptation-decisions")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "proposed" in statuses
        assert "under_review" in statuses
        assert "approved" in statuses
        assert "implemented" in statuses
        assert "rejected" in statuses
        assert "deferred" in statuses

    @pytest.mark.anyio
    async def test_futility_results_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/futility-assessments")
        data = resp.json()
        results = {item["result"] for item in data["items"]}
        assert "not_futile" in results
        assert "futile" in results
        assert "possibly_futile" in results
