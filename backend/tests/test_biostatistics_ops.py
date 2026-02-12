"""Tests for Biostatistics Operations (BIOSTATS-OPS) module.

Covers:
- Seed data verification (analyses, decisions, adjustments, reports, futility assessments)
- Interim Analysis CRUD (create, read, update, delete, list, filter by trial/type/status)
- Adaptive Decision CRUD (create, read, delete, list, filter by analysis/outcome)
- Multiplicity Adjustment CRUD (create, read, update, delete, list, filter by trial/method)
- Statistical Report CRUD (create, read, update, delete, list, filter by trial/analysis/type)
- Futility Assessment CRUD (create, read, delete, list, filter by analysis/futility_met)
- Biostatistics metrics computation
- Error handling (404s, validation errors)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.biostatistics_ops import (
    AnalysisStatus,
    AnalysisType,
    BlindingLevel,
    DecisionOutcome,
    MultiplicityMethod,
    ReportType,
)
from app.services.biostatistics_ops_service import (
    BiostatisticsOpsService,
    get_biostatistics_ops_service,
    reset_biostatistics_ops_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/biostatistics-ops"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_biostatistics_ops_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> BiostatisticsOpsService:
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


def _make_analysis_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "analysis_number": 5,
        "analysis_type": "interim",
        "information_fraction": 0.50,
        "planned_date": "2026-06-01T00:00:00Z",
        "events_required": 200,
        "spending_function": "OBrien-Fleming",
        "lead_statistician": "Dr. Test Statistician",
    }
    defaults.update(overrides)
    return defaults


def _make_decision_create(**overrides) -> dict:
    defaults = {
        "analysis_id": "IA-001",
        "outcome": "continue",
        "rationale": "Test rationale for continuing the study.",
        "blinding_level": "unblinded",
        "decided_by": "Dr. Test Decider",
    }
    defaults.update(overrides)
    return defaults


def _make_adjustment_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "method": "bonferroni",
        "family_name": "Test Endpoint Family",
        "endpoints": ["Endpoint A", "Endpoint B"],
        "overall_alpha": 0.05,
        "description": "Test multiplicity adjustment.",
        "statistician": "Dr. Test Statistician",
    }
    defaults.update(overrides)
    return defaults


def _make_report_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "analysis_id": "IA-001",
        "report_type": "dsmb_report",
        "title": "Test Statistical Report",
        "version": "1.0",
        "blinding_level": "unblinded",
        "author": "Dr. Test Author",
        "distribution_list": ["DSMB Chair"],
    }
    defaults.update(overrides)
    return defaults


def _make_futility_create(**overrides) -> dict:
    defaults = {
        "analysis_id": "IA-001",
        "recommendation": "Continue enrollment. Test assessment.",
        "assessed_by": "Dr. Test Assessor",
        "conditional_power": 0.80,
        "predictive_power": 0.75,
        "futility_boundary": 0.20,
        "observed_statistic": 2.0,
        "stochastic_curtailment_pct": 80.0,
    }
    defaults.update(overrides)
    return defaults


# ===========================================================================
# SEED DATA VERIFICATION
# ===========================================================================


class TestSeedDataVerification:
    """Verify the demo seed data is loaded correctly."""

    @pytest.mark.anyio
    async def test_seed_analyses_count(self, svc: BiostatisticsOpsService):
        analyses = svc.list_analyses()
        assert len(analyses) == 12

    @pytest.mark.anyio
    async def test_seed_decisions_count(self, svc: BiostatisticsOpsService):
        decisions = svc.list_decisions()
        assert len(decisions) == 12

    @pytest.mark.anyio
    async def test_seed_adjustments_count(self, svc: BiostatisticsOpsService):
        adjustments = svc.list_adjustments()
        assert len(adjustments) == 10

    @pytest.mark.anyio
    async def test_seed_reports_count(self, svc: BiostatisticsOpsService):
        reports = svc.list_reports()
        assert len(reports) == 12

    @pytest.mark.anyio
    async def test_seed_futility_count(self, svc: BiostatisticsOpsService):
        futility = svc.list_futility_assessments()
        assert len(futility) == 10

    @pytest.mark.anyio
    async def test_seed_analysis_ia001(self, svc: BiostatisticsOpsService):
        a = svc.get_analysis("IA-001")
        assert a is not None
        assert a.trial_id == EYLEA_TRIAL
        assert a.analysis_number == 1
        assert a.analysis_type == AnalysisType.INTERIM
        assert a.information_fraction == 0.25
        assert a.status == AnalysisStatus.COMPLETED

    @pytest.mark.anyio
    async def test_seed_analysis_ia005(self, svc: BiostatisticsOpsService):
        a = svc.get_analysis("IA-005")
        assert a is not None
        assert a.trial_id == DUPIXENT_TRIAL
        assert a.spending_function == "Lan-DeMets"

    @pytest.mark.anyio
    async def test_seed_analysis_ia008(self, svc: BiostatisticsOpsService):
        a = svc.get_analysis("IA-008")
        assert a is not None
        assert a.trial_id == LIBTAYO_TRIAL
        assert a.spending_function == "Pocock"

    @pytest.mark.anyio
    async def test_seed_decision_ad001(self, svc: BiostatisticsOpsService):
        d = svc.get_decision("AD-001")
        assert d is not None
        assert d.analysis_id == "IA-001"
        assert d.outcome == DecisionOutcome.CONTINUE
        assert d.crossed_boundary is False

    @pytest.mark.anyio
    async def test_seed_decision_ad010_efficacy_stop(self, svc: BiostatisticsOpsService):
        d = svc.get_decision("AD-010")
        assert d is not None
        assert d.outcome == DecisionOutcome.STOP_EFFICACY
        assert d.crossed_boundary is True

    @pytest.mark.anyio
    async def test_seed_adjustment_ma001(self, svc: BiostatisticsOpsService):
        adj = svc.get_adjustment("MA-001")
        assert adj is not None
        assert adj.trial_id == EYLEA_TRIAL
        assert adj.method == MultiplicityMethod.ALPHA_SPENDING

    @pytest.mark.anyio
    async def test_seed_report_sr001(self, svc: BiostatisticsOpsService):
        r = svc.get_report("SR-001")
        assert r is not None
        assert r.trial_id == EYLEA_TRIAL
        assert r.report_type == ReportType.DSMB_REPORT
        assert r.status == "approved"

    @pytest.mark.anyio
    async def test_seed_futility_fa001(self, svc: BiostatisticsOpsService):
        f = svc.get_futility_assessment("FA-001")
        assert f is not None
        assert f.analysis_id == "IA-001"
        assert f.futility_met is False

    @pytest.mark.anyio
    async def test_seed_futility_fa008_met(self, svc: BiostatisticsOpsService):
        f = svc.get_futility_assessment("FA-008")
        assert f is not None
        assert f.futility_met is True

    @pytest.mark.anyio
    async def test_seed_analyses_eylea_count(self, svc: BiostatisticsOpsService):
        analyses = svc.list_analyses(trial_id=EYLEA_TRIAL)
        assert len(analyses) == 5

    @pytest.mark.anyio
    async def test_seed_analyses_dupixent_count(self, svc: BiostatisticsOpsService):
        analyses = svc.list_analyses(trial_id=DUPIXENT_TRIAL)
        assert len(analyses) == 3

    @pytest.mark.anyio
    async def test_seed_analyses_libtayo_count(self, svc: BiostatisticsOpsService):
        analyses = svc.list_analyses(trial_id=LIBTAYO_TRIAL)
        assert len(analyses) == 4

    @pytest.mark.anyio
    async def test_seed_futility_met_count(self, svc: BiostatisticsOpsService):
        met = svc.list_futility_assessments(futility_met=True)
        assert len(met) == 3

    @pytest.mark.anyio
    async def test_seed_futility_not_met_count(self, svc: BiostatisticsOpsService):
        not_met = svc.list_futility_assessments(futility_met=False)
        assert len(not_met) == 7


# ===========================================================================
# INTERIM ANALYSIS CRUD - API
# ===========================================================================


class TestInterimAnalysisAPI:
    """API-level tests for interim analysis CRUD."""

    @pytest.mark.anyio
    async def test_list_analyses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/analyses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_analyses_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/analyses", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_analyses_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/analyses", params={"analysis_type": "interim"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["analysis_type"] == "interim"

    @pytest.mark.anyio
    async def test_list_analyses_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/analyses", params={"status": "completed"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_list_analyses_filter_combined(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/analyses",
            params={"trial_id": EYLEA_TRIAL, "analysis_type": "interim", "status": "completed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["analysis_type"] == "interim"
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_list_analyses_filter_no_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/analyses", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.anyio
    async def test_get_analysis(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/analyses/IA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "IA-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_analysis_404(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/analyses/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_analysis(self, client: AsyncClient):
        payload = _make_analysis_create()
        resp = await client.post(f"{API_PREFIX}/analyses", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["analysis_number"] == 5
        assert data["analysis_type"] == "interim"
        assert data["status"] == "planned"
        assert data["id"].startswith("IA-")

    @pytest.mark.anyio
    async def test_create_analysis_increases_count(self, client: AsyncClient):
        payload = _make_analysis_create()
        await client.post(f"{API_PREFIX}/analyses", json=payload)
        resp = await client.get(f"{API_PREFIX}/analyses")
        assert resp.json()["total"] == 13

    @pytest.mark.anyio
    async def test_create_analysis_type_safety(self, client: AsyncClient):
        payload = _make_analysis_create(analysis_type="safety")
        resp = await client.post(f"{API_PREFIX}/analyses", json=payload)
        assert resp.status_code == 201
        assert resp.json()["analysis_type"] == "safety"

    @pytest.mark.anyio
    async def test_create_analysis_type_adaptive(self, client: AsyncClient):
        payload = _make_analysis_create(analysis_type="adaptive")
        resp = await client.post(f"{API_PREFIX}/analyses", json=payload)
        assert resp.status_code == 201
        assert resp.json()["analysis_type"] == "adaptive"

    @pytest.mark.anyio
    async def test_create_analysis_invalid_type(self, client: AsyncClient):
        payload = _make_analysis_create(analysis_type="invalid_type")
        resp = await client.post(f"{API_PREFIX}/analyses", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_analysis_invalid_fraction_too_high(self, client: AsyncClient):
        payload = _make_analysis_create(information_fraction=1.5)
        resp = await client.post(f"{API_PREFIX}/analyses", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_analysis_invalid_fraction_negative(self, client: AsyncClient):
        payload = _make_analysis_create(information_fraction=-0.1)
        resp = await client.post(f"{API_PREFIX}/analyses", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_analysis_invalid_number_zero(self, client: AsyncClient):
        payload = _make_analysis_create(analysis_number=0)
        resp = await client.post(f"{API_PREFIX}/analyses", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_update_analysis(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/analyses/IA-003",
            json={"status": "sap_approved"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "sap_approved"

    @pytest.mark.anyio
    async def test_update_analysis_multiple_fields(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/analyses/IA-003",
            json={
                "status": "data_cut",
                "subjects_enrolled": 450,
                "subjects_analyzed": 400,
                "events_observed": 300,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "data_cut"
        assert data["subjects_enrolled"] == 450
        assert data["subjects_analyzed"] == 400
        assert data["events_observed"] == 300

    @pytest.mark.anyio
    async def test_update_analysis_alpha_spent(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/analyses/IA-003",
            json={"alpha_spent": 0.025, "alpha_remaining": 0.025},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["alpha_spent"] == 0.025
        assert data["alpha_remaining"] == 0.025

    @pytest.mark.anyio
    async def test_update_analysis_404(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/analyses/NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_analysis(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/analyses/IA-012")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_analysis_reduces_count(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/analyses/IA-012")
        resp = await client.get(f"{API_PREFIX}/analyses")
        assert resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_analysis_404(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/analyses/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_then_get_404(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/analyses/IA-012")
        resp = await client.get(f"{API_PREFIX}/analyses/IA-012")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_and_retrieve_roundtrip(self, client: AsyncClient):
        payload = _make_analysis_create(analysis_number=99)
        create_resp = await client.post(f"{API_PREFIX}/analyses", json=payload)
        created = create_resp.json()
        get_resp = await client.get(f"{API_PREFIX}/analyses/{created['id']}")
        assert get_resp.status_code == 200
        assert get_resp.json()["analysis_number"] == 99

    @pytest.mark.anyio
    async def test_list_analyses_filter_type_futility(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/analyses", params={"analysis_type": "futility"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["analysis_type"] == "futility"

    @pytest.mark.anyio
    async def test_list_analyses_filter_status_planned(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/analyses", params={"status": "planned"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2

    @pytest.mark.anyio
    async def test_list_analyses_filter_status_qc_review(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/analyses", params={"status": "qc_review"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    @pytest.mark.anyio
    async def test_list_analyses_filter_status_reported(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/analyses", params={"status": "reported"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1


# ===========================================================================
# ADAPTIVE DECISION CRUD - API
# ===========================================================================


class TestAdaptiveDecisionAPI:
    """API-level tests for adaptive decision CRUD."""

    @pytest.mark.anyio
    async def test_list_decisions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/decisions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_decisions_filter_analysis(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/decisions", params={"analysis_id": "IA-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        for item in data["items"]:
            assert item["analysis_id"] == "IA-001"

    @pytest.mark.anyio
    async def test_list_decisions_filter_outcome_continue(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/decisions", params={"outcome": "continue"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["outcome"] == "continue"

    @pytest.mark.anyio
    async def test_list_decisions_filter_outcome_stop_efficacy(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/decisions", params={"outcome": "stop_for_efficacy"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    @pytest.mark.anyio
    async def test_list_decisions_filter_outcome_modify_dose(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/decisions", params={"outcome": "modify_dose"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    @pytest.mark.anyio
    async def test_list_decisions_filter_no_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/decisions", params={"analysis_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_get_decision(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/decisions/AD-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "AD-001"
        assert data["outcome"] == "continue"

    @pytest.mark.anyio
    async def test_get_decision_404(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/decisions/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_decision(self, client: AsyncClient):
        payload = _make_decision_create()
        resp = await client.post(f"{API_PREFIX}/decisions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["outcome"] == "continue"
        assert data["decided_by"] == "Dr. Test Decider"
        assert data["id"].startswith("AD-")

    @pytest.mark.anyio
    async def test_create_decision_stop_futility(self, client: AsyncClient):
        payload = _make_decision_create(outcome="stop_for_futility")
        resp = await client.post(f"{API_PREFIX}/decisions", json=payload)
        assert resp.status_code == 201
        assert resp.json()["outcome"] == "stop_for_futility"

    @pytest.mark.anyio
    async def test_create_decision_expand_enrollment(self, client: AsyncClient):
        payload = _make_decision_create(outcome="expand_enrollment")
        resp = await client.post(f"{API_PREFIX}/decisions", json=payload)
        assert resp.status_code == 201
        assert resp.json()["outcome"] == "expand_enrollment"

    @pytest.mark.anyio
    async def test_create_decision_with_stats(self, client: AsyncClient):
        payload = _make_decision_create(
            conditional_power=0.85,
            predictive_probability=0.80,
            p_value=0.02,
        )
        resp = await client.post(f"{API_PREFIX}/decisions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["conditional_power"] == 0.85
        assert data["predictive_probability"] == 0.80
        assert data["p_value"] == 0.02

    @pytest.mark.anyio
    async def test_create_decision_invalid_outcome(self, client: AsyncClient):
        payload = _make_decision_create(outcome="invalid_outcome")
        resp = await client.post(f"{API_PREFIX}/decisions", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_decision_increases_count(self, client: AsyncClient):
        payload = _make_decision_create()
        await client.post(f"{API_PREFIX}/decisions", json=payload)
        resp = await client.get(f"{API_PREFIX}/decisions")
        assert resp.json()["total"] == 13

    @pytest.mark.anyio
    async def test_delete_decision(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/decisions/AD-012")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_decision_404(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/decisions/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_decision_reduces_count(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/decisions/AD-012")
        resp = await client.get(f"{API_PREFIX}/decisions")
        assert resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_create_and_retrieve_decision(self, client: AsyncClient):
        payload = _make_decision_create(rationale="Unique test rationale")
        create_resp = await client.post(f"{API_PREFIX}/decisions", json=payload)
        created_id = create_resp.json()["id"]
        get_resp = await client.get(f"{API_PREFIX}/decisions/{created_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["rationale"] == "Unique test rationale"

    @pytest.mark.anyio
    async def test_list_decisions_filter_combined(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/decisions",
            params={"analysis_id": "IA-002", "outcome": "stop_for_efficacy"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["analysis_id"] == "IA-002"
            assert item["outcome"] == "stop_for_efficacy"


# ===========================================================================
# MULTIPLICITY ADJUSTMENT CRUD - API
# ===========================================================================


class TestMultiplicityAdjustmentAPI:
    """API-level tests for multiplicity adjustment CRUD."""

    @pytest.mark.anyio
    async def test_list_adjustments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjustments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_adjustments_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjustments", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_adjustments_filter_method_bonferroni(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjustments", params={"method": "bonferroni"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["method"] == "bonferroni"

    @pytest.mark.anyio
    async def test_list_adjustments_filter_method_graphical(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjustments", params={"method": "graphical"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2

    @pytest.mark.anyio
    async def test_list_adjustments_filter_no_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjustments", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_list_adjustments_filter_combined(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/adjustments",
            params={"trial_id": EYLEA_TRIAL, "method": "bonferroni"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["method"] == "bonferroni"

    @pytest.mark.anyio
    async def test_get_adjustment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjustments/MA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "MA-001"
        assert data["method"] == "alpha_spending"

    @pytest.mark.anyio
    async def test_get_adjustment_404(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjustments/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_adjustment(self, client: AsyncClient):
        payload = _make_adjustment_create()
        resp = await client.post(f"{API_PREFIX}/adjustments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["method"] == "bonferroni"
        assert data["family_name"] == "Test Endpoint Family"
        assert data["id"].startswith("MA-")

    @pytest.mark.anyio
    async def test_create_adjustment_graphical(self, client: AsyncClient):
        payload = _make_adjustment_create(method="graphical")
        resp = await client.post(f"{API_PREFIX}/adjustments", json=payload)
        assert resp.status_code == 201
        assert resp.json()["method"] == "graphical"

    @pytest.mark.anyio
    async def test_create_adjustment_invalid_method(self, client: AsyncClient):
        payload = _make_adjustment_create(method="invalid_method")
        resp = await client.post(f"{API_PREFIX}/adjustments", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_adjustment_invalid_alpha_too_high(self, client: AsyncClient):
        payload = _make_adjustment_create(overall_alpha=1.5)
        resp = await client.post(f"{API_PREFIX}/adjustments", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_adjustment_invalid_alpha_negative(self, client: AsyncClient):
        payload = _make_adjustment_create(overall_alpha=-0.01)
        resp = await client.post(f"{API_PREFIX}/adjustments", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_adjustment_increases_count(self, client: AsyncClient):
        payload = _make_adjustment_create()
        await client.post(f"{API_PREFIX}/adjustments", json=payload)
        resp = await client.get(f"{API_PREFIX}/adjustments")
        assert resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_update_adjustment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/adjustments/MA-003",
            json={"allocated_alphas": {"IA1": 0.005, "IA2": 0.015}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["allocated_alphas"]["IA1"] == 0.005
        assert data["allocated_alphas"]["IA2"] == 0.015

    @pytest.mark.anyio
    async def test_update_adjustment_p_values(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/adjustments/MA-003",
            json={"adjusted_p_values": {"EP1": 0.01, "EP2": 0.03}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["adjusted_p_values"]["EP1"] == 0.01

    @pytest.mark.anyio
    async def test_update_adjustment_rejection(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/adjustments/MA-003",
            json={"rejection_decisions": {"EP1": True, "EP2": False}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["rejection_decisions"]["EP1"] is True
        assert data["rejection_decisions"]["EP2"] is False

    @pytest.mark.anyio
    async def test_update_adjustment_404(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/adjustments/NONEXISTENT",
            json={"allocated_alphas": {}},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_adjustment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/adjustments/MA-010")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_adjustment_404(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/adjustments/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_adjustment_reduces_count(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/adjustments/MA-010")
        resp = await client.get(f"{API_PREFIX}/adjustments")
        assert resp.json()["total"] == 9

    @pytest.mark.anyio
    async def test_create_and_retrieve_adjustment(self, client: AsyncClient):
        payload = _make_adjustment_create(family_name="Unique Family")
        create_resp = await client.post(f"{API_PREFIX}/adjustments", json=payload)
        created_id = create_resp.json()["id"]
        get_resp = await client.get(f"{API_PREFIX}/adjustments/{created_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["family_name"] == "Unique Family"

    @pytest.mark.anyio
    async def test_list_adjustments_filter_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjustments", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 3

    @pytest.mark.anyio
    async def test_list_adjustments_filter_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjustments", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 3


# ===========================================================================
# STATISTICAL REPORT CRUD - API
# ===========================================================================


class TestStatisticalReportAPI:
    """API-level tests for statistical report CRUD."""

    @pytest.mark.anyio
    async def test_list_reports(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_reports_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_reports_filter_analysis(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports", params={"analysis_id": "IA-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        for item in data["items"]:
            assert item["analysis_id"] == "IA-001"

    @pytest.mark.anyio
    async def test_list_reports_filter_type_dsmb(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports", params={"report_type": "dsmb_report"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["report_type"] == "dsmb_report"

    @pytest.mark.anyio
    async def test_list_reports_filter_type_safety(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports", params={"report_type": "safety_report"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["report_type"] == "safety_report"

    @pytest.mark.anyio
    async def test_list_reports_filter_no_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_list_reports_filter_combined(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/reports",
            params={"trial_id": EYLEA_TRIAL, "report_type": "dsmb_report"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["report_type"] == "dsmb_report"

    @pytest.mark.anyio
    async def test_get_report(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports/SR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SR-001"
        assert data["status"] == "approved"

    @pytest.mark.anyio
    async def test_get_report_404(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_report(self, client: AsyncClient):
        payload = _make_report_create()
        resp = await client.post(f"{API_PREFIX}/reports", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Statistical Report"
        assert data["status"] == "draft"
        assert data["id"].startswith("SR-")

    @pytest.mark.anyio
    async def test_create_report_interim(self, client: AsyncClient):
        payload = _make_report_create(report_type="interim_report")
        resp = await client.post(f"{API_PREFIX}/reports", json=payload)
        assert resp.status_code == 201
        assert resp.json()["report_type"] == "interim_report"

    @pytest.mark.anyio
    async def test_create_report_futility(self, client: AsyncClient):
        payload = _make_report_create(report_type="futility_report")
        resp = await client.post(f"{API_PREFIX}/reports", json=payload)
        assert resp.status_code == 201
        assert resp.json()["report_type"] == "futility_report"

    @pytest.mark.anyio
    async def test_create_report_invalid_type(self, client: AsyncClient):
        payload = _make_report_create(report_type="invalid_type")
        resp = await client.post(f"{API_PREFIX}/reports", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_report_increases_count(self, client: AsyncClient):
        payload = _make_report_create()
        await client.post(f"{API_PREFIX}/reports", json=payload)
        resp = await client.get(f"{API_PREFIX}/reports")
        assert resp.json()["total"] == 13

    @pytest.mark.anyio
    async def test_update_report_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reports/SR-005",
            json={"status": "in_review"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_review"

    @pytest.mark.anyio
    async def test_update_report_reviewer(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reports/SR-005",
            json={"reviewer": "Dr. New Reviewer"},
        )
        assert resp.status_code == 200
        assert resp.json()["reviewer"] == "Dr. New Reviewer"

    @pytest.mark.anyio
    async def test_update_report_key_findings(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reports/SR-005",
            json={"key_findings": ["Finding 1", "Finding 2"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["key_findings"]) == 2
        assert "Finding 1" in data["key_findings"]

    @pytest.mark.anyio
    async def test_update_report_404(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reports/NONEXISTENT",
            json={"status": "approved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_report(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/reports/SR-012")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_report_404(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/reports/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_report_reduces_count(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/reports/SR-012")
        resp = await client.get(f"{API_PREFIX}/reports")
        assert resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_create_and_retrieve_report(self, client: AsyncClient):
        payload = _make_report_create(title="Unique Report Title")
        create_resp = await client.post(f"{API_PREFIX}/reports", json=payload)
        created_id = create_resp.json()["id"]
        get_resp = await client.get(f"{API_PREFIX}/reports/{created_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["title"] == "Unique Report Title"

    @pytest.mark.anyio
    async def test_list_reports_filter_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 3

    @pytest.mark.anyio
    async def test_list_reports_filter_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 4

    @pytest.mark.anyio
    async def test_create_report_no_analysis_id(self, client: AsyncClient):
        payload = _make_report_create(analysis_id=None)
        resp = await client.post(f"{API_PREFIX}/reports", json=payload)
        assert resp.status_code == 201
        assert resp.json()["analysis_id"] is None

    @pytest.mark.anyio
    async def test_create_report_blinding_blinded_aggregate(self, client: AsyncClient):
        payload = _make_report_create(blinding_level="blinded_aggregate")
        resp = await client.post(f"{API_PREFIX}/reports", json=payload)
        assert resp.status_code == 201
        assert resp.json()["blinding_level"] == "blinded_aggregate"


# ===========================================================================
# FUTILITY ASSESSMENT CRUD - API
# ===========================================================================


class TestFutilityAssessmentAPI:
    """API-level tests for futility assessment CRUD."""

    @pytest.mark.anyio
    async def test_list_futility_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/futility-assessments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_futility_filter_analysis(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/futility-assessments", params={"analysis_id": "IA-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        for item in data["items"]:
            assert item["analysis_id"] == "IA-001"

    @pytest.mark.anyio
    async def test_list_futility_filter_met_true(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/futility-assessments", params={"futility_met": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["futility_met"] is True

    @pytest.mark.anyio
    async def test_list_futility_filter_met_false(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/futility-assessments", params={"futility_met": False})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 7
        for item in data["items"]:
            assert item["futility_met"] is False

    @pytest.mark.anyio
    async def test_list_futility_filter_no_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/futility-assessments", params={"analysis_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_list_futility_filter_combined(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/futility-assessments",
            params={"analysis_id": "IA-001", "futility_met": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["analysis_id"] == "IA-001"
            assert item["futility_met"] is True

    @pytest.mark.anyio
    async def test_get_futility_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/futility-assessments/FA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "FA-001"
        assert data["conditional_power"] == 0.82

    @pytest.mark.anyio
    async def test_get_futility_assessment_404(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/futility-assessments/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_futility_assessment(self, client: AsyncClient):
        payload = _make_futility_create()
        resp = await client.post(f"{API_PREFIX}/futility-assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["conditional_power"] == 0.80
        assert data["futility_met"] is False
        assert data["id"].startswith("FA-")

    @pytest.mark.anyio
    async def test_create_futility_with_all_fields(self, client: AsyncClient):
        payload = _make_futility_create(
            conditional_power=0.15,
            predictive_power=0.10,
            futility_boundary=0.20,
            observed_statistic=0.5,
            stochastic_curtailment_pct=15.0,
        )
        resp = await client.post(f"{API_PREFIX}/futility-assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["conditional_power"] == 0.15
        assert data["stochastic_curtailment_pct"] == 15.0

    @pytest.mark.anyio
    async def test_create_futility_minimal(self, client: AsyncClient):
        payload = {
            "analysis_id": "IA-001",
            "recommendation": "Continue.",
            "assessed_by": "Dr. Minimal",
        }
        resp = await client.post(f"{API_PREFIX}/futility-assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["conditional_power"] is None
        assert data["futility_met"] is False

    @pytest.mark.anyio
    async def test_create_futility_increases_count(self, client: AsyncClient):
        payload = _make_futility_create()
        await client.post(f"{API_PREFIX}/futility-assessments", json=payload)
        resp = await client.get(f"{API_PREFIX}/futility-assessments")
        assert resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_futility_assessment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/futility-assessments/FA-010")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_futility_404(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/futility-assessments/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_futility_reduces_count(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/futility-assessments/FA-010")
        resp = await client.get(f"{API_PREFIX}/futility-assessments")
        assert resp.json()["total"] == 9

    @pytest.mark.anyio
    async def test_create_and_retrieve_futility(self, client: AsyncClient):
        payload = _make_futility_create(recommendation="Unique recommendation")
        create_resp = await client.post(f"{API_PREFIX}/futility-assessments", json=payload)
        created_id = create_resp.json()["id"]
        get_resp = await client.get(f"{API_PREFIX}/futility-assessments/{created_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["recommendation"] == "Unique recommendation"

    @pytest.mark.anyio
    async def test_list_futility_filter_analysis_ia005(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/futility-assessments", params={"analysis_id": "IA-005"})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 2

    @pytest.mark.anyio
    async def test_list_futility_filter_analysis_ia008(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/futility-assessments", params={"analysis_id": "IA-008"})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 2


# ===========================================================================
# METRICS
# ===========================================================================


class TestBiostatisticsMetrics:
    """Tests for the metrics endpoint."""

    @pytest.mark.anyio
    async def test_metrics_endpoint(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_analyses"] == 12
        assert data["total_decisions"] == 12
        assert data["total_multiplicity_adjustments"] == 10
        assert data["total_reports"] == 12
        assert data["total_futility_assessments"] == 10

    @pytest.mark.anyio
    async def test_metrics_analyses_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_type = data["analyses_by_type"]
        assert "interim" in by_type
        assert by_type["interim"] >= 4

    @pytest.mark.anyio
    async def test_metrics_analyses_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["analyses_by_status"]
        assert "completed" in by_status
        assert by_status["completed"] >= 5

    @pytest.mark.anyio
    async def test_metrics_decisions_by_outcome(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_outcome = data["decisions_by_outcome"]
        assert "continue" in by_outcome
        assert by_outcome["continue"] >= 5

    @pytest.mark.anyio
    async def test_metrics_adjustments_by_method(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_method = data["adjustments_by_method"]
        assert "bonferroni" in by_method
        assert "graphical" in by_method

    @pytest.mark.anyio
    async def test_metrics_reports_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_type = data["reports_by_type"]
        assert "dsmb_report" in by_type
        assert "interim_report" in by_type

    @pytest.mark.anyio
    async def test_metrics_futility_met_count(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["futility_met_count"] == 3

    @pytest.mark.anyio
    async def test_metrics_avg_information_fraction(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert 0.0 < data["avg_information_fraction"] < 1.0

    @pytest.mark.anyio
    async def test_metrics_after_create(self, client: AsyncClient):
        payload = _make_analysis_create()
        await client.post(f"{API_PREFIX}/analyses", json=payload)
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_analyses"] == 13

    @pytest.mark.anyio
    async def test_metrics_after_delete(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/analyses/IA-012")
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_analyses"] == 11

    @pytest.mark.anyio
    async def test_metrics_futility_met_after_delete(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/futility-assessments/FA-008")
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["futility_met_count"] == 2

    @pytest.mark.anyio
    async def test_metrics_has_all_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        expected_fields = [
            "total_analyses",
            "analyses_by_type",
            "analyses_by_status",
            "total_decisions",
            "decisions_by_outcome",
            "total_multiplicity_adjustments",
            "adjustments_by_method",
            "total_reports",
            "reports_by_type",
            "total_futility_assessments",
            "futility_met_count",
            "avg_information_fraction",
        ]
        for field in expected_fields:
            assert field in data


# ===========================================================================
# SERVICE DIRECT TESTS
# ===========================================================================


class TestServiceDirect:
    """Direct service-level tests."""

    @pytest.mark.anyio
    async def test_service_singleton(self):
        svc1 = get_biostatistics_ops_service()
        svc2 = get_biostatistics_ops_service()
        assert svc1 is svc2

    @pytest.mark.anyio
    async def test_service_reset(self):
        svc1 = get_biostatistics_ops_service()
        svc2 = reset_biostatistics_ops_service()
        assert svc1 is not svc2

    @pytest.mark.anyio
    async def test_service_create_analysis(self, svc: BiostatisticsOpsService):
        from app.schemas.biostatistics_ops import InterimAnalysisCreate
        payload = InterimAnalysisCreate(
            trial_id=EYLEA_TRIAL,
            analysis_number=10,
            analysis_type=AnalysisType.INTERIM,
            information_fraction=0.5,
            planned_date=datetime.now(timezone.utc),
            lead_statistician="Dr. Test",
        )
        result = svc.create_analysis(payload)
        assert result.id.startswith("IA-")
        assert result.status == AnalysisStatus.PLANNED

    @pytest.mark.anyio
    async def test_service_get_analysis_none(self, svc: BiostatisticsOpsService):
        result = svc.get_analysis("NONEXISTENT")
        assert result is None

    @pytest.mark.anyio
    async def test_service_update_analysis_none(self, svc: BiostatisticsOpsService):
        from app.schemas.biostatistics_ops import InterimAnalysisUpdate
        result = svc.update_analysis("NONEXISTENT", InterimAnalysisUpdate())
        assert result is None

    @pytest.mark.anyio
    async def test_service_delete_analysis_false(self, svc: BiostatisticsOpsService):
        result = svc.delete_analysis("NONEXISTENT")
        assert result is False

    @pytest.mark.anyio
    async def test_service_create_decision(self, svc: BiostatisticsOpsService):
        from app.schemas.biostatistics_ops import AdaptiveDecisionCreate
        payload = AdaptiveDecisionCreate(
            analysis_id="IA-001",
            outcome=DecisionOutcome.CONTINUE,
            rationale="Test",
            decided_by="Dr. Test",
        )
        result = svc.create_decision(payload)
        assert result.id.startswith("AD-")

    @pytest.mark.anyio
    async def test_service_get_decision_none(self, svc: BiostatisticsOpsService):
        result = svc.get_decision("NONEXISTENT")
        assert result is None

    @pytest.mark.anyio
    async def test_service_delete_decision_false(self, svc: BiostatisticsOpsService):
        result = svc.delete_decision("NONEXISTENT")
        assert result is False

    @pytest.mark.anyio
    async def test_service_create_adjustment(self, svc: BiostatisticsOpsService):
        from app.schemas.biostatistics_ops import MultiplicityAdjustmentCreate
        payload = MultiplicityAdjustmentCreate(
            trial_id=EYLEA_TRIAL,
            method=MultiplicityMethod.BONFERRONI,
            family_name="Test",
            description="Test desc",
            statistician="Dr. Test",
        )
        result = svc.create_adjustment(payload)
        assert result.id.startswith("MA-")

    @pytest.mark.anyio
    async def test_service_get_adjustment_none(self, svc: BiostatisticsOpsService):
        result = svc.get_adjustment("NONEXISTENT")
        assert result is None

    @pytest.mark.anyio
    async def test_service_update_adjustment_none(self, svc: BiostatisticsOpsService):
        from app.schemas.biostatistics_ops import MultiplicityAdjustmentUpdate
        result = svc.update_adjustment("NONEXISTENT", MultiplicityAdjustmentUpdate())
        assert result is None

    @pytest.mark.anyio
    async def test_service_delete_adjustment_false(self, svc: BiostatisticsOpsService):
        result = svc.delete_adjustment("NONEXISTENT")
        assert result is False

    @pytest.mark.anyio
    async def test_service_create_report(self, svc: BiostatisticsOpsService):
        from app.schemas.biostatistics_ops import StatisticalReportCreate
        payload = StatisticalReportCreate(
            trial_id=EYLEA_TRIAL,
            report_type=ReportType.DSMB_REPORT,
            title="Test",
            version="1.0",
            blinding_level=BlindingLevel.UNBLINDED,
            author="Dr. Test",
        )
        result = svc.create_report(payload)
        assert result.id.startswith("SR-")
        assert result.status == "draft"

    @pytest.mark.anyio
    async def test_service_get_report_none(self, svc: BiostatisticsOpsService):
        result = svc.get_report("NONEXISTENT")
        assert result is None

    @pytest.mark.anyio
    async def test_service_update_report_none(self, svc: BiostatisticsOpsService):
        from app.schemas.biostatistics_ops import StatisticalReportUpdate
        result = svc.update_report("NONEXISTENT", StatisticalReportUpdate())
        assert result is None

    @pytest.mark.anyio
    async def test_service_delete_report_false(self, svc: BiostatisticsOpsService):
        result = svc.delete_report("NONEXISTENT")
        assert result is False

    @pytest.mark.anyio
    async def test_service_create_futility(self, svc: BiostatisticsOpsService):
        from app.schemas.biostatistics_ops import FutilityAssessmentCreate
        payload = FutilityAssessmentCreate(
            analysis_id="IA-001",
            recommendation="Test",
            assessed_by="Dr. Test",
        )
        result = svc.create_futility_assessment(payload)
        assert result.id.startswith("FA-")
        assert result.futility_met is False

    @pytest.mark.anyio
    async def test_service_get_futility_none(self, svc: BiostatisticsOpsService):
        result = svc.get_futility_assessment("NONEXISTENT")
        assert result is None

    @pytest.mark.anyio
    async def test_service_delete_futility_false(self, svc: BiostatisticsOpsService):
        result = svc.delete_futility_assessment("NONEXISTENT")
        assert result is False

    @pytest.mark.anyio
    async def test_service_metrics_structure(self, svc: BiostatisticsOpsService):
        metrics = svc.get_metrics()
        assert metrics.total_analyses == 12
        assert metrics.total_decisions == 12
        assert metrics.total_multiplicity_adjustments == 10
        assert metrics.total_reports == 12
        assert metrics.total_futility_assessments == 10
        assert metrics.futility_met_count == 3

    @pytest.mark.anyio
    async def test_service_list_analyses_all_types(self, svc: BiostatisticsOpsService):
        for at in AnalysisType:
            result = svc.list_analyses(analysis_type=at)
            for item in result:
                assert item.analysis_type == at

    @pytest.mark.anyio
    async def test_service_list_analyses_all_statuses(self, svc: BiostatisticsOpsService):
        for status in AnalysisStatus:
            result = svc.list_analyses(status=status)
            for item in result:
                assert item.status == status

    @pytest.mark.anyio
    async def test_service_list_decisions_all_outcomes(self, svc: BiostatisticsOpsService):
        for outcome in DecisionOutcome:
            result = svc.list_decisions(outcome=outcome)
            for item in result:
                assert item.outcome == outcome

    @pytest.mark.anyio
    async def test_service_list_adjustments_all_methods(self, svc: BiostatisticsOpsService):
        for method in MultiplicityMethod:
            result = svc.list_adjustments(method=method)
            for item in result:
                assert item.method == method

    @pytest.mark.anyio
    async def test_service_list_reports_all_types(self, svc: BiostatisticsOpsService):
        for rt in ReportType:
            result = svc.list_reports(report_type=rt)
            for item in result:
                assert item.report_type == rt


# ===========================================================================
# EDGE CASES AND ADDITIONAL COVERAGE
# ===========================================================================


class TestEdgeCases:
    """Edge case and boundary condition tests."""

    @pytest.mark.anyio
    async def test_create_analysis_boundary_fraction_0(self, client: AsyncClient):
        payload = _make_analysis_create(information_fraction=0.0)
        resp = await client.post(f"{API_PREFIX}/analyses", json=payload)
        assert resp.status_code == 201
        assert resp.json()["information_fraction"] == 0.0

    @pytest.mark.anyio
    async def test_create_analysis_boundary_fraction_1(self, client: AsyncClient):
        payload = _make_analysis_create(information_fraction=1.0)
        resp = await client.post(f"{API_PREFIX}/analyses", json=payload)
        assert resp.status_code == 201
        assert resp.json()["information_fraction"] == 1.0

    @pytest.mark.anyio
    async def test_create_adjustment_alpha_0(self, client: AsyncClient):
        payload = _make_adjustment_create(overall_alpha=0.0)
        resp = await client.post(f"{API_PREFIX}/adjustments", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_create_adjustment_alpha_1(self, client: AsyncClient):
        payload = _make_adjustment_create(overall_alpha=1.0)
        resp = await client.post(f"{API_PREFIX}/adjustments", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_create_adjustment_empty_endpoints(self, client: AsyncClient):
        payload = _make_adjustment_create(endpoints=[])
        resp = await client.post(f"{API_PREFIX}/adjustments", json=payload)
        assert resp.status_code == 201
        assert resp.json()["endpoints"] == []

    @pytest.mark.anyio
    async def test_create_report_empty_distribution(self, client: AsyncClient):
        payload = _make_report_create(distribution_list=[])
        resp = await client.post(f"{API_PREFIX}/reports", json=payload)
        assert resp.status_code == 201
        assert resp.json()["distribution_list"] == []

    @pytest.mark.anyio
    async def test_double_delete_analysis(self, client: AsyncClient):
        resp1 = await client.delete(f"{API_PREFIX}/analyses/IA-012")
        assert resp1.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/analyses/IA-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_double_delete_decision(self, client: AsyncClient):
        resp1 = await client.delete(f"{API_PREFIX}/decisions/AD-012")
        assert resp1.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/decisions/AD-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_double_delete_adjustment(self, client: AsyncClient):
        resp1 = await client.delete(f"{API_PREFIX}/adjustments/MA-010")
        assert resp1.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/adjustments/MA-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_double_delete_report(self, client: AsyncClient):
        resp1 = await client.delete(f"{API_PREFIX}/reports/SR-012")
        assert resp1.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/reports/SR-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_double_delete_futility(self, client: AsyncClient):
        resp1 = await client.delete(f"{API_PREFIX}/futility-assessments/FA-010")
        assert resp1.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/futility-assessments/FA-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_update_analysis_empty_body(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/analyses/IA-001", json={})
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_update_adjustment_empty_body(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/adjustments/MA-001", json={})
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_update_report_empty_body(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/reports/SR-001", json={})
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_multiple_analyses(self, client: AsyncClient):
        for i in range(5):
            payload = _make_analysis_create(analysis_number=100 + i)
            resp = await client.post(f"{API_PREFIX}/analyses", json=payload)
            assert resp.status_code == 201
        resp = await client.get(f"{API_PREFIX}/analyses")
        assert resp.json()["total"] == 17

    @pytest.mark.anyio
    async def test_create_multiple_decisions(self, client: AsyncClient):
        for _ in range(3):
            payload = _make_decision_create()
            resp = await client.post(f"{API_PREFIX}/decisions", json=payload)
            assert resp.status_code == 201
        resp = await client.get(f"{API_PREFIX}/decisions")
        assert resp.json()["total"] == 15

    @pytest.mark.anyio
    async def test_create_multiple_reports(self, client: AsyncClient):
        for i in range(3):
            payload = _make_report_create(title=f"Report {i}")
            resp = await client.post(f"{API_PREFIX}/reports", json=payload)
            assert resp.status_code == 201
        resp = await client.get(f"{API_PREFIX}/reports")
        assert resp.json()["total"] == 15

    @pytest.mark.anyio
    async def test_analysis_all_enum_types_via_api(self, client: AsyncClient):
        for at in ["interim", "final", "futility", "safety", "adaptive", "sensitivity", "subgroup"]:
            payload = _make_analysis_create(analysis_type=at)
            resp = await client.post(f"{API_PREFIX}/analyses", json=payload)
            assert resp.status_code == 201
            assert resp.json()["analysis_type"] == at

    @pytest.mark.anyio
    async def test_decision_all_outcome_types_via_api(self, client: AsyncClient):
        for outcome in [
            "continue", "stop_for_efficacy", "stop_for_futility",
            "stop_for_safety", "modify_dose", "expand_enrollment", "reduce_sample_size",
        ]:
            payload = _make_decision_create(outcome=outcome)
            resp = await client.post(f"{API_PREFIX}/decisions", json=payload)
            assert resp.status_code == 201
            assert resp.json()["outcome"] == outcome

    @pytest.mark.anyio
    async def test_adjustment_all_methods_via_api(self, client: AsyncClient):
        for method in [
            "bonferroni", "holm", "hochberg", "gatekeeping",
            "graphical", "alpha_spending", "group_sequential",
        ]:
            payload = _make_adjustment_create(method=method)
            resp = await client.post(f"{API_PREFIX}/adjustments", json=payload)
            assert resp.status_code == 201
            assert resp.json()["method"] == method

    @pytest.mark.anyio
    async def test_report_all_types_via_api(self, client: AsyncClient):
        for rt in [
            "dsmb_report", "interim_report", "futility_report",
            "safety_report", "final_report", "ad_hoc_report",
        ]:
            payload = _make_report_create(report_type=rt)
            resp = await client.post(f"{API_PREFIX}/reports", json=payload)
            assert resp.status_code == 201
            assert resp.json()["report_type"] == rt

    @pytest.mark.anyio
    async def test_report_all_blinding_levels_via_api(self, client: AsyncClient):
        for bl in ["open", "blinded_aggregate", "unblinded", "partially_unblinded"]:
            payload = _make_report_create(blinding_level=bl)
            resp = await client.post(f"{API_PREFIX}/reports", json=payload)
            assert resp.status_code == 201
            assert resp.json()["blinding_level"] == bl

    @pytest.mark.anyio
    async def test_decision_all_blinding_levels_via_api(self, client: AsyncClient):
        for bl in ["open", "blinded_aggregate", "unblinded", "partially_unblinded"]:
            payload = _make_decision_create(blinding_level=bl)
            resp = await client.post(f"{API_PREFIX}/decisions", json=payload)
            assert resp.status_code == 201
            assert resp.json()["blinding_level"] == bl

    @pytest.mark.anyio
    async def test_create_decision_with_dsmb(self, client: AsyncClient):
        payload = _make_decision_create(dsmb_recommendation="Test DSMB recommendation")
        resp = await client.post(f"{API_PREFIX}/decisions", json=payload)
        assert resp.status_code == 201
        assert resp.json()["dsmb_recommendation"] == "Test DSMB recommendation"

    @pytest.mark.anyio
    async def test_update_analysis_actual_date(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/analyses/IA-003",
            json={"actual_date": "2026-07-01T00:00:00Z"},
        )
        assert resp.status_code == 200
        assert resp.json()["actual_date"] is not None

    @pytest.mark.anyio
    async def test_update_analysis_data_cutoff(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/analyses/IA-003",
            json={"data_cutoff_date": "2026-06-25T00:00:00Z"},
        )
        assert resp.status_code == 200
        assert resp.json()["data_cutoff_date"] is not None

    @pytest.mark.anyio
    async def test_seed_data_analysis_types_coverage(self, svc: BiostatisticsOpsService):
        types = {a.analysis_type for a in svc.list_analyses()}
        assert AnalysisType.INTERIM in types
        assert AnalysisType.FINAL in types
        assert AnalysisType.SAFETY in types
        assert AnalysisType.ADAPTIVE in types
        assert AnalysisType.FUTILITY in types
        assert AnalysisType.SUBGROUP in types
        assert AnalysisType.SENSITIVITY in types

    @pytest.mark.anyio
    async def test_seed_data_decision_outcomes_coverage(self, svc: BiostatisticsOpsService):
        outcomes = {d.outcome for d in svc.list_decisions()}
        assert DecisionOutcome.CONTINUE in outcomes
        assert DecisionOutcome.STOP_EFFICACY in outcomes
        assert DecisionOutcome.STOP_SAFETY in outcomes
        assert DecisionOutcome.MODIFY_DOSE in outcomes
        assert DecisionOutcome.EXPAND_ENROLLMENT in outcomes
        assert DecisionOutcome.REDUCE_SAMPLE in outcomes

    @pytest.mark.anyio
    async def test_seed_data_methods_coverage(self, svc: BiostatisticsOpsService):
        methods = {a.method for a in svc.list_adjustments()}
        assert MultiplicityMethod.BONFERRONI in methods
        assert MultiplicityMethod.HOLM in methods
        assert MultiplicityMethod.HOCHBERG in methods
        assert MultiplicityMethod.GATEKEEPING in methods
        assert MultiplicityMethod.GRAPHICAL in methods
        assert MultiplicityMethod.ALPHA_SPENDING in methods
        assert MultiplicityMethod.GROUP_SEQUENTIAL in methods

    @pytest.mark.anyio
    async def test_seed_data_report_types_coverage(self, svc: BiostatisticsOpsService):
        types = {r.report_type for r in svc.list_reports()}
        assert ReportType.DSMB_REPORT in types
        assert ReportType.INTERIM_REPORT in types
        assert ReportType.SAFETY_REPORT in types
        assert ReportType.FUTILITY_REPORT in types
        assert ReportType.AD_HOC_REPORT in types
        assert ReportType.FINAL_REPORT in types
