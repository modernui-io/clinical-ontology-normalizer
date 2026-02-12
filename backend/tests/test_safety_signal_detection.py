"""Tests for Safety Signal Detection (SAFETY-SIGNAL).

Covers:
- Seed data verification (signals, evaluations, reviews, analyses, reports)
- Safety Signal CRUD (create, read, update, delete, list, filter by trial_id)
- Signal Evaluation CRUD (create, read, delete, list, filter by signal_id)
- Cumulative Review CRUD (create, read, delete, list, filter by signal_id)
- Disproportionality Analysis CRUD (create, read, update, delete, list, filter)
- Aggregate Safety Report CRUD (create, read, update, delete, list, filter)
- Metrics computation
- Error handling (404s, validation errors)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.safety_signal_detection import (
    AggregateSafetyReportCreate,
    AggregateSafetyReportUpdate,
    CausalityAssessment,
    CumulativeReviewCreate,
    DisproportionalityAnalysisCreate,
    DisproportionalityAnalysisUpdate,
    ReportPeriod,
    SafetySignalCreate,
    SafetySignalUpdate,
    SignalEvaluationCreate,
    SignalMethod,
    SignalPriority,
    SignalStatus,
)
from app.services.safety_signal_detection_service import (
    SafetySignalDetectionService,
    get_safety_signal_detection_service,
    reset_safety_signal_detection_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/safety-signal-detection"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_safety_signal_detection_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> SafetySignalDetectionService:
    return fresh_service


# ---------------------------------------------------------------------------
# Seed data verification - Signals
# ---------------------------------------------------------------------------


class TestSeedSignals:
    @pytest.mark.anyio
    async def test_seed_signals_count(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        assert len(signals) == 12

    @pytest.mark.anyio
    async def test_seed_signals_eylea(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals(trial_id=EYLEA_TRIAL)
        assert len(signals) == 4

    @pytest.mark.anyio
    async def test_seed_signals_dupixent(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals(trial_id=DUPIXENT_TRIAL)
        assert len(signals) == 4

    @pytest.mark.anyio
    async def test_seed_signals_libtayo(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals(trial_id=LIBTAYO_TRIAL)
        assert len(signals) == 4

    @pytest.mark.anyio
    async def test_seed_signal_has_required_fields(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        for s in signals:
            assert s.id
            assert s.trial_id
            assert s.signal_name
            assert s.preferred_term
            assert s.drug_name
            assert s.detected_by
            assert s.detected_date
            assert s.created_at

    @pytest.mark.anyio
    async def test_seed_signal_statuses(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        statuses = {s.status for s in signals}
        assert SignalStatus.CONFIRMED in statuses
        assert SignalStatus.UNDER_EVALUATION in statuses
        assert SignalStatus.DETECTED in statuses

    @pytest.mark.anyio
    async def test_seed_signal_priorities(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        priorities = {s.priority for s in signals}
        assert SignalPriority.CRITICAL in priorities
        assert SignalPriority.HIGH in priorities
        assert SignalPriority.MEDIUM in priorities
        assert SignalPriority.LOW in priorities

    @pytest.mark.anyio
    async def test_seed_signal_methods(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        methods = {s.detection_method for s in signals}
        assert len(methods) >= 4


# ---------------------------------------------------------------------------
# Seed data verification - Evaluations
# ---------------------------------------------------------------------------


class TestSeedEvaluations:
    @pytest.mark.anyio
    async def test_seed_evaluations_count(self, svc: SafetySignalDetectionService):
        evals = svc.list_evaluations()
        assert len(evals) == 10

    @pytest.mark.anyio
    async def test_seed_evaluation_has_required_fields(self, svc: SafetySignalDetectionService):
        evals = svc.list_evaluations()
        for e in evals:
            assert e.id
            assert e.signal_id
            assert e.evaluator
            assert e.clinical_significance
            assert e.overall_assessment
            assert e.recommendation

    @pytest.mark.anyio
    async def test_seed_evaluation_causality_distribution(self, svc: SafetySignalDetectionService):
        evals = svc.list_evaluations()
        causalities = {e.overall_assessment for e in evals}
        assert len(causalities) >= 3


# ---------------------------------------------------------------------------
# Seed data verification - Cumulative Reviews
# ---------------------------------------------------------------------------


class TestSeedCumulativeReviews:
    @pytest.mark.anyio
    async def test_seed_reviews_count(self, svc: SafetySignalDetectionService):
        reviews = svc.list_cumulative_reviews()
        assert len(reviews) == 10

    @pytest.mark.anyio
    async def test_seed_review_has_required_fields(self, svc: SafetySignalDetectionService):
        reviews = svc.list_cumulative_reviews()
        for r in reviews:
            assert r.id
            assert r.signal_id
            assert r.reviewer
            assert r.conclusion
            assert r.review_period

    @pytest.mark.anyio
    async def test_seed_review_incidence_rate(self, svc: SafetySignalDetectionService):
        reviews = svc.list_cumulative_reviews()
        for r in reviews:
            if r.total_exposure_patient_years > 0:
                assert r.incidence_rate is not None


# ---------------------------------------------------------------------------
# Seed data verification - Analyses
# ---------------------------------------------------------------------------


class TestSeedAnalyses:
    @pytest.mark.anyio
    async def test_seed_analyses_count(self, svc: SafetySignalDetectionService):
        analyses = svc.list_analyses()
        assert len(analyses) == 10

    @pytest.mark.anyio
    async def test_seed_analysis_has_required_fields(self, svc: SafetySignalDetectionService):
        analyses = svc.list_analyses()
        for a in analyses:
            assert a.id
            assert a.trial_id
            assert a.analysis_name
            assert a.method
            assert a.run_by
            assert a.status == "completed"

    @pytest.mark.anyio
    async def test_seed_analyses_by_trial(self, svc: SafetySignalDetectionService):
        for trial_id in [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL]:
            analyses = svc.list_analyses(trial_id=trial_id)
            assert len(analyses) >= 2


# ---------------------------------------------------------------------------
# Seed data verification - Aggregate Reports
# ---------------------------------------------------------------------------


class TestSeedAggregateReports:
    @pytest.mark.anyio
    async def test_seed_reports_count(self, svc: SafetySignalDetectionService):
        reports = svc.list_aggregate_reports()
        assert len(reports) == 10

    @pytest.mark.anyio
    async def test_seed_report_has_required_fields(self, svc: SafetySignalDetectionService):
        reports = svc.list_aggregate_reports()
        for r in reports:
            assert r.id
            assert r.trial_id
            assert r.report_type
            assert r.period
            assert r.author
            assert r.total_subjects_exposed >= 0

    @pytest.mark.anyio
    async def test_seed_reports_by_trial(self, svc: SafetySignalDetectionService):
        for trial_id in [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL]:
            reports = svc.list_aggregate_reports(trial_id=trial_id)
            assert len(reports) >= 2


# ---------------------------------------------------------------------------
# Safety Signals - API CRUD
# ---------------------------------------------------------------------------


class TestSignalsAPI:
    @pytest.mark.anyio
    async def test_list_signals(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/signals")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 12
        assert len(body["items"]) == 12

    @pytest.mark.anyio
    async def test_list_signals_filter_trial(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/signals", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 4
        for item in body["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_signals_filter_dupixent(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/signals", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        assert resp.json()["total"] == 4

    @pytest.mark.anyio
    async def test_list_signals_filter_libtayo(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/signals", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        assert resp.json()["total"] == 4

    @pytest.mark.anyio
    async def test_list_signals_filter_nonexistent_trial(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/signals", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_create_signal(self):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "signal_name": "New test signal",
            "preferred_term": "Test PT",
            "detection_method": SignalMethod.PRR.value,
            "drug_name": "Aflibercept",
            "detected_by": "Test User",
            "observed_cases": 5,
            "expected_cases": 2.0,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/signals", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["signal_name"] == "New test signal"
        assert body["trial_id"] == EYLEA_TRIAL
        assert body["status"] == SignalStatus.DETECTED.value
        assert body["id"]

    @pytest.mark.anyio
    async def test_create_signal_with_priority(self):
        payload = {
            "trial_id": DUPIXENT_TRIAL,
            "signal_name": "Critical signal",
            "preferred_term": "Critical PT",
            "detection_method": SignalMethod.BAYESIAN.value,
            "priority": SignalPriority.CRITICAL.value,
            "drug_name": "Dupilumab",
            "detected_by": "Automated System",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/signals", json=payload)
        assert resp.status_code == 201
        assert resp.json()["priority"] == SignalPriority.CRITICAL.value

    @pytest.mark.anyio
    async def test_create_signal_default_priority(self):
        payload = {
            "trial_id": LIBTAYO_TRIAL,
            "signal_name": "Default priority signal",
            "preferred_term": "Default PT",
            "detection_method": SignalMethod.ROR.value,
            "drug_name": "Cemiplimab",
            "detected_by": "Dr. Test",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/signals", json=payload)
        assert resp.status_code == 201
        assert resp.json()["priority"] == SignalPriority.MEDIUM.value

    @pytest.mark.anyio
    async def test_get_signal(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        sig_id = signals[0].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/signals/{sig_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == sig_id

    @pytest.mark.anyio
    async def test_get_signal_not_found(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/signals/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_signal_status(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        sig_id = signals[0].id
        payload = {"status": SignalStatus.CLOSED.value}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.put(f"{API_PREFIX}/signals/{sig_id}", json=payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == SignalStatus.CLOSED.value

    @pytest.mark.anyio
    async def test_update_signal_priority(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        sig_id = signals[0].id
        payload = {"priority": SignalPriority.CRITICAL.value}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.put(f"{API_PREFIX}/signals/{sig_id}", json=payload)
        assert resp.status_code == 200
        assert resp.json()["priority"] == SignalPriority.CRITICAL.value

    @pytest.mark.anyio
    async def test_update_signal_causality(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        sig_id = signals[0].id
        payload = {"causality": CausalityAssessment.CERTAIN.value}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.put(f"{API_PREFIX}/signals/{sig_id}", json=payload)
        assert resp.status_code == 200
        assert resp.json()["causality"] == CausalityAssessment.CERTAIN.value

    @pytest.mark.anyio
    async def test_update_signal_assigned_to(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        sig_id = signals[0].id
        payload = {"assigned_to": "Dr. New Assignee"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.put(f"{API_PREFIX}/signals/{sig_id}", json=payload)
        assert resp.status_code == 200
        assert resp.json()["assigned_to"] == "Dr. New Assignee"

    @pytest.mark.anyio
    async def test_update_signal_prr_value(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        sig_id = signals[0].id
        payload = {"prr_value": 5.55}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.put(f"{API_PREFIX}/signals/{sig_id}", json=payload)
        assert resp.status_code == 200
        assert resp.json()["prr_value"] == 5.55

    @pytest.mark.anyio
    async def test_update_signal_ror_value(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        sig_id = signals[0].id
        payload = {"ror_value": 3.14}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.put(f"{API_PREFIX}/signals/{sig_id}", json=payload)
        assert resp.status_code == 200
        assert resp.json()["ror_value"] == 3.14

    @pytest.mark.anyio
    async def test_update_signal_ebgm_value(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        sig_id = signals[0].id
        payload = {"ebgm_value": 4.20}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.put(f"{API_PREFIX}/signals/{sig_id}", json=payload)
        assert resp.status_code == 200
        assert resp.json()["ebgm_value"] == 4.20

    @pytest.mark.anyio
    async def test_update_signal_not_found(self):
        payload = {"status": SignalStatus.CLOSED.value}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.put(f"{API_PREFIX}/signals/nonexistent", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_signal_multiple_fields(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        sig_id = signals[0].id
        payload = {
            "status": SignalStatus.ONGOING_MONITORING.value,
            "priority": SignalPriority.HIGH.value,
            "assigned_to": "Dr. Multi-update",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.put(f"{API_PREFIX}/signals/{sig_id}", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == SignalStatus.ONGOING_MONITORING.value
        assert body["priority"] == SignalPriority.HIGH.value
        assert body["assigned_to"] == "Dr. Multi-update"

    @pytest.mark.anyio
    async def test_delete_signal(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        sig_id = signals[0].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.delete(f"{API_PREFIX}/signals/{sig_id}")
        assert resp.status_code == 204
        # Verify deleted
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/signals/{sig_id}")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_signal_not_found(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.delete(f"{API_PREFIX}/signals/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_signal_reduces_count(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        initial = len(signals)
        sig_id = signals[0].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            await ac.delete(f"{API_PREFIX}/signals/{sig_id}")
            resp = await ac.get(f"{API_PREFIX}/signals")
        assert resp.json()["total"] == initial - 1

    @pytest.mark.anyio
    async def test_create_and_get_signal_roundtrip(self):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "signal_name": "Roundtrip signal",
            "preferred_term": "Roundtrip PT",
            "detection_method": SignalMethod.EBGM.value,
            "drug_name": "Aflibercept",
            "detected_by": "Roundtrip Test",
            "meddra_code": "10099999",
            "soc": "Test SOC",
            "comparator": "Sham",
            "observed_cases": 10,
            "expected_cases": 3.5,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            create_resp = await ac.post(f"{API_PREFIX}/signals", json=payload)
            sig_id = create_resp.json()["id"]
            get_resp = await ac.get(f"{API_PREFIX}/signals/{sig_id}")
        assert get_resp.status_code == 200
        body = get_resp.json()
        assert body["signal_name"] == "Roundtrip signal"
        assert body["meddra_code"] == "10099999"
        assert body["soc"] == "Test SOC"
        assert body["comparator"] == "Sham"
        assert body["observed_cases"] == 10
        assert body["expected_cases"] == 3.5

    @pytest.mark.anyio
    async def test_create_signal_increments_total(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/signals")
            initial = resp.json()["total"]
            payload = {
                "trial_id": EYLEA_TRIAL,
                "signal_name": "Increment test",
                "preferred_term": "Inc PT",
                "detection_method": SignalMethod.PRR.value,
                "drug_name": "Aflibercept",
                "detected_by": "Test",
            }
            await ac.post(f"{API_PREFIX}/signals", json=payload)
            resp = await ac.get(f"{API_PREFIX}/signals")
            assert resp.json()["total"] == initial + 1

    @pytest.mark.anyio
    async def test_create_signal_validation_missing_fields(self):
        payload = {"trial_id": EYLEA_TRIAL}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/signals", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_signal_invalid_method(self):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "signal_name": "Bad method",
            "preferred_term": "PT",
            "detection_method": "invalid_method",
            "drug_name": "Drug",
            "detected_by": "Test",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/signals", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_signal_invalid_priority(self):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "signal_name": "Bad priority",
            "preferred_term": "PT",
            "detection_method": SignalMethod.PRR.value,
            "priority": "invalid_priority",
            "drug_name": "Drug",
            "detected_by": "Test",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/signals", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_signal_negative_observed_cases(self):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "signal_name": "Neg cases",
            "preferred_term": "PT",
            "detection_method": SignalMethod.PRR.value,
            "drug_name": "Drug",
            "detected_by": "Test",
            "observed_cases": -1,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/signals", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_signal_negative_expected_cases(self):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "signal_name": "Neg expected",
            "preferred_term": "PT",
            "detection_method": SignalMethod.PRR.value,
            "drug_name": "Drug",
            "detected_by": "Test",
            "expected_cases": -1.0,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/signals", json=payload)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Signal Evaluations - API CRUD
# ---------------------------------------------------------------------------


class TestEvaluationsAPI:
    @pytest.mark.anyio
    async def test_list_evaluations(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/evaluations")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 10
        assert len(body["items"]) == 10

    @pytest.mark.anyio
    async def test_list_evaluations_filter_signal(self, svc: SafetySignalDetectionService):
        evals = svc.list_evaluations()
        signal_id = evals[0].signal_id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/evaluations", params={"signal_id": signal_id})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["signal_id"] == signal_id

    @pytest.mark.anyio
    async def test_list_evaluations_filter_nonexistent(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/evaluations", params={"signal_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_create_evaluation(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        signal_id = signals[0].id
        payload = {
            "signal_id": signal_id,
            "evaluator": "Dr. Test Eval",
            "clinical_significance": "Test significance",
            "overall_assessment": CausalityAssessment.POSSIBLE.value,
            "recommendation": "Test recommendation",
            "action_items": ["Item 1", "Item 2"],
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/evaluations", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["signal_id"] == signal_id
        assert body["evaluator"] == "Dr. Test Eval"
        assert body["overall_assessment"] == CausalityAssessment.POSSIBLE.value
        assert body["action_items"] == ["Item 1", "Item 2"]

    @pytest.mark.anyio
    async def test_create_evaluation_with_biological_plausibility(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        signal_id = signals[0].id
        payload = {
            "signal_id": signal_id,
            "evaluator": "Dr. Bio",
            "clinical_significance": "Significant",
            "overall_assessment": CausalityAssessment.PROBABLE.value,
            "recommendation": "Continue monitoring",
            "biological_plausibility": "Strong mechanism known",
            "temporal_relationship": True,
            "dose_response": True,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/evaluations", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["biological_plausibility"] == "Strong mechanism known"
        assert body["temporal_relationship"] is True
        assert body["dose_response"] is True

    @pytest.mark.anyio
    async def test_create_evaluation_empty_action_items(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        signal_id = signals[0].id
        payload = {
            "signal_id": signal_id,
            "evaluator": "Dr. Empty",
            "clinical_significance": "Minor",
            "overall_assessment": CausalityAssessment.UNLIKELY.value,
            "recommendation": "No action",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/evaluations", json=payload)
        assert resp.status_code == 201
        assert resp.json()["action_items"] == []

    @pytest.mark.anyio
    async def test_get_evaluation(self, svc: SafetySignalDetectionService):
        evals = svc.list_evaluations()
        eval_id = evals[0].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/evaluations/{eval_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == eval_id

    @pytest.mark.anyio
    async def test_get_evaluation_not_found(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/evaluations/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_evaluation(self, svc: SafetySignalDetectionService):
        evals = svc.list_evaluations()
        eval_id = evals[0].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.delete(f"{API_PREFIX}/evaluations/{eval_id}")
        assert resp.status_code == 204
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/evaluations/{eval_id}")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_evaluation_not_found(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.delete(f"{API_PREFIX}/evaluations/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_evaluation_reduces_count(self, svc: SafetySignalDetectionService):
        evals = svc.list_evaluations()
        initial = len(evals)
        eval_id = evals[0].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            await ac.delete(f"{API_PREFIX}/evaluations/{eval_id}")
            resp = await ac.get(f"{API_PREFIX}/evaluations")
        assert resp.json()["total"] == initial - 1

    @pytest.mark.anyio
    async def test_create_evaluation_validation_missing_fields(self):
        payload = {"signal_id": "some-id"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/evaluations", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_evaluation_invalid_assessment(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        payload = {
            "signal_id": signals[0].id,
            "evaluator": "Dr. Invalid",
            "clinical_significance": "Test",
            "overall_assessment": "invalid_value",
            "recommendation": "Test",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/evaluations", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_evaluation_roundtrip(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        payload = {
            "signal_id": signals[0].id,
            "evaluator": "Dr. Roundtrip",
            "clinical_significance": "Roundtrip significance",
            "overall_assessment": CausalityAssessment.CERTAIN.value,
            "recommendation": "Roundtrip recommendation",
            "action_items": ["Action A", "Action B", "Action C"],
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            create_resp = await ac.post(f"{API_PREFIX}/evaluations", json=payload)
            eval_id = create_resp.json()["id"]
            get_resp = await ac.get(f"{API_PREFIX}/evaluations/{eval_id}")
        body = get_resp.json()
        assert body["evaluator"] == "Dr. Roundtrip"
        assert body["overall_assessment"] == CausalityAssessment.CERTAIN.value
        assert len(body["action_items"]) == 3


# ---------------------------------------------------------------------------
# Cumulative Reviews - API CRUD
# ---------------------------------------------------------------------------


class TestCumulativeReviewsAPI:
    @pytest.mark.anyio
    async def test_list_reviews(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/cumulative-reviews")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 10

    @pytest.mark.anyio
    async def test_list_reviews_filter_signal(self, svc: SafetySignalDetectionService):
        reviews = svc.list_cumulative_reviews()
        signal_id = reviews[0].signal_id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/cumulative-reviews", params={"signal_id": signal_id})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["signal_id"] == signal_id

    @pytest.mark.anyio
    async def test_list_reviews_filter_nonexistent(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/cumulative-reviews", params={"signal_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_create_review(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        signal_id = signals[0].id
        payload = {
            "signal_id": signal_id,
            "review_period": ReportPeriod.QUARTERLY.value,
            "cumulative_cases": 25,
            "new_cases_in_period": 5,
            "total_exposure_patient_years": 1500.0,
            "reviewer": "Dr. Test Reviewer",
            "conclusion": "Rate within expected range",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/cumulative-reviews", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["signal_id"] == signal_id
        assert body["cumulative_cases"] == 25
        assert body["incidence_rate"] is not None

    @pytest.mark.anyio
    async def test_create_review_zero_exposure(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        payload = {
            "signal_id": signals[0].id,
            "review_period": ReportPeriod.MONTHLY.value,
            "cumulative_cases": 0,
            "new_cases_in_period": 0,
            "total_exposure_patient_years": 0.0,
            "reviewer": "Dr. Zero",
            "conclusion": "No exposure",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/cumulative-reviews", json=payload)
        assert resp.status_code == 201
        assert resp.json()["incidence_rate"] is None

    @pytest.mark.anyio
    async def test_create_review_with_next_review_date(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        next_date = (datetime.now(timezone.utc) + timedelta(days=90)).isoformat()
        payload = {
            "signal_id": signals[0].id,
            "review_period": ReportPeriod.SEMI_ANNUAL.value,
            "cumulative_cases": 30,
            "new_cases_in_period": 8,
            "total_exposure_patient_years": 2000.0,
            "reviewer": "Dr. Next",
            "conclusion": "Schedule next review",
            "next_review_date": next_date,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/cumulative-reviews", json=payload)
        assert resp.status_code == 201
        assert resp.json()["next_review_date"] is not None

    @pytest.mark.anyio
    async def test_get_review(self, svc: SafetySignalDetectionService):
        reviews = svc.list_cumulative_reviews()
        rev_id = reviews[0].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/cumulative-reviews/{rev_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == rev_id

    @pytest.mark.anyio
    async def test_get_review_not_found(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/cumulative-reviews/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_review(self, svc: SafetySignalDetectionService):
        reviews = svc.list_cumulative_reviews()
        rev_id = reviews[0].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.delete(f"{API_PREFIX}/cumulative-reviews/{rev_id}")
        assert resp.status_code == 204
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/cumulative-reviews/{rev_id}")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_review_not_found(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.delete(f"{API_PREFIX}/cumulative-reviews/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_review_reduces_count(self, svc: SafetySignalDetectionService):
        reviews = svc.list_cumulative_reviews()
        initial = len(reviews)
        rev_id = reviews[0].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            await ac.delete(f"{API_PREFIX}/cumulative-reviews/{rev_id}")
            resp = await ac.get(f"{API_PREFIX}/cumulative-reviews")
        assert resp.json()["total"] == initial - 1

    @pytest.mark.anyio
    async def test_create_review_validation_missing_fields(self):
        payload = {"signal_id": "some-id"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/cumulative-reviews", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_review_invalid_period(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        payload = {
            "signal_id": signals[0].id,
            "review_period": "invalid",
            "cumulative_cases": 5,
            "new_cases_in_period": 2,
            "total_exposure_patient_years": 100.0,
            "reviewer": "Dr. Test",
            "conclusion": "Test",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/cumulative-reviews", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_review_negative_cases(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        payload = {
            "signal_id": signals[0].id,
            "review_period": ReportPeriod.QUARTERLY.value,
            "cumulative_cases": -1,
            "new_cases_in_period": 0,
            "total_exposure_patient_years": 100.0,
            "reviewer": "Dr. Test",
            "conclusion": "Test",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/cumulative-reviews", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_review_roundtrip(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        payload = {
            "signal_id": signals[0].id,
            "review_period": ReportPeriod.ANNUAL.value,
            "cumulative_cases": 50,
            "new_cases_in_period": 15,
            "total_exposure_patient_years": 5000.0,
            "reviewer": "Dr. Roundtrip",
            "conclusion": "Roundtrip conclusion",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            create_resp = await ac.post(f"{API_PREFIX}/cumulative-reviews", json=payload)
            rev_id = create_resp.json()["id"]
            get_resp = await ac.get(f"{API_PREFIX}/cumulative-reviews/{rev_id}")
        body = get_resp.json()
        assert body["cumulative_cases"] == 50
        assert body["reviewer"] == "Dr. Roundtrip"


# ---------------------------------------------------------------------------
# Disproportionality Analyses - API CRUD
# ---------------------------------------------------------------------------


class TestAnalysesAPI:
    @pytest.mark.anyio
    async def test_list_analyses(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/analyses")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 10

    @pytest.mark.anyio
    async def test_list_analyses_filter_trial(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/analyses", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_analyses_filter_dupixent(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/analyses", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 2

    @pytest.mark.anyio
    async def test_list_analyses_filter_libtayo(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/analyses", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 2

    @pytest.mark.anyio
    async def test_list_analyses_filter_nonexistent(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/analyses", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_create_analysis(self):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        payload = {
            "trial_id": EYLEA_TRIAL,
            "analysis_name": "Test PRR Analysis",
            "method": SignalMethod.PRR.value,
            "data_cutoff_date": cutoff,
            "min_case_count": 3,
            "run_by": "Test Runner",
            "threshold_prr": 2.0,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/analyses", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["analysis_name"] == "Test PRR Analysis"
        assert body["status"] == "running"
        assert body["signals_detected"] == 0
        assert body["total_events_analyzed"] == 0

    @pytest.mark.anyio
    async def test_create_analysis_with_ror_threshold(self):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        payload = {
            "trial_id": DUPIXENT_TRIAL,
            "analysis_name": "Test ROR Analysis",
            "method": SignalMethod.ROR.value,
            "data_cutoff_date": cutoff,
            "run_by": "Test",
            "threshold_ror": 2.5,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/analyses", json=payload)
        assert resp.status_code == 201
        assert resp.json()["threshold_ror"] == 2.5

    @pytest.mark.anyio
    async def test_get_analysis(self, svc: SafetySignalDetectionService):
        analyses = svc.list_analyses()
        analysis_id = analyses[0].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/analyses/{analysis_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == analysis_id

    @pytest.mark.anyio
    async def test_get_analysis_not_found(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/analyses/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_analysis_status(self, svc: SafetySignalDetectionService):
        analyses = svc.list_analyses()
        analysis_id = analyses[0].id
        payload = {"status": "failed"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.put(f"{API_PREFIX}/analyses/{analysis_id}", json=payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"

    @pytest.mark.anyio
    async def test_update_analysis_signals_detected(self, svc: SafetySignalDetectionService):
        analyses = svc.list_analyses()
        analysis_id = analyses[0].id
        payload = {"signals_detected": 10, "total_events_analyzed": 5000}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.put(f"{API_PREFIX}/analyses/{analysis_id}", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["signals_detected"] == 10
        assert body["total_events_analyzed"] == 5000

    @pytest.mark.anyio
    async def test_update_analysis_report_reference(self, svc: SafetySignalDetectionService):
        analyses = svc.list_analyses()
        analysis_id = analyses[0].id
        payload = {"report_reference": "RPT-NEW-2025-0001"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.put(f"{API_PREFIX}/analyses/{analysis_id}", json=payload)
        assert resp.status_code == 200
        assert resp.json()["report_reference"] == "RPT-NEW-2025-0001"

    @pytest.mark.anyio
    async def test_update_analysis_not_found(self):
        payload = {"status": "completed"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.put(f"{API_PREFIX}/analyses/nonexistent", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_analysis(self, svc: SafetySignalDetectionService):
        analyses = svc.list_analyses()
        analysis_id = analyses[0].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.delete(f"{API_PREFIX}/analyses/{analysis_id}")
        assert resp.status_code == 204
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/analyses/{analysis_id}")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_analysis_not_found(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.delete(f"{API_PREFIX}/analyses/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_analysis_reduces_count(self, svc: SafetySignalDetectionService):
        analyses = svc.list_analyses()
        initial = len(analyses)
        analysis_id = analyses[0].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            await ac.delete(f"{API_PREFIX}/analyses/{analysis_id}")
            resp = await ac.get(f"{API_PREFIX}/analyses")
        assert resp.json()["total"] == initial - 1

    @pytest.mark.anyio
    async def test_create_analysis_validation_missing_fields(self):
        payload = {"trial_id": EYLEA_TRIAL}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/analyses", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_analysis_invalid_method(self):
        cutoff = datetime.now(timezone.utc).isoformat()
        payload = {
            "trial_id": EYLEA_TRIAL,
            "analysis_name": "Bad method",
            "method": "invalid",
            "data_cutoff_date": cutoff,
            "run_by": "Test",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/analyses", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_analysis_invalid_min_case_count(self):
        cutoff = datetime.now(timezone.utc).isoformat()
        payload = {
            "trial_id": EYLEA_TRIAL,
            "analysis_name": "Bad min count",
            "method": SignalMethod.PRR.value,
            "data_cutoff_date": cutoff,
            "run_by": "Test",
            "min_case_count": 0,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/analyses", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_analysis_roundtrip(self):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        payload = {
            "trial_id": LIBTAYO_TRIAL,
            "analysis_name": "Roundtrip Analysis",
            "method": SignalMethod.BAYESIAN.value,
            "data_cutoff_date": cutoff,
            "run_by": "Dr. Roundtrip",
            "min_case_count": 5,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            create_resp = await ac.post(f"{API_PREFIX}/analyses", json=payload)
            analysis_id = create_resp.json()["id"]
            get_resp = await ac.get(f"{API_PREFIX}/analyses/{analysis_id}")
        body = get_resp.json()
        assert body["analysis_name"] == "Roundtrip Analysis"
        assert body["method"] == SignalMethod.BAYESIAN.value
        assert body["min_case_count"] == 5


# ---------------------------------------------------------------------------
# Aggregate Safety Reports - API CRUD
# ---------------------------------------------------------------------------


class TestAggregateReportsAPI:
    @pytest.mark.anyio
    async def test_list_reports(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/aggregate-reports")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 10

    @pytest.mark.anyio
    async def test_list_reports_filter_trial(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/aggregate-reports", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_reports_filter_dupixent(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/aggregate-reports", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 2

    @pytest.mark.anyio
    async def test_list_reports_filter_libtayo(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/aggregate-reports", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 2

    @pytest.mark.anyio
    async def test_list_reports_filter_nonexistent(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/aggregate-reports", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_create_report(self):
        period_start = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        period_end = datetime.now(timezone.utc).isoformat()
        payload = {
            "trial_id": EYLEA_TRIAL,
            "report_type": "DSUR",
            "period": ReportPeriod.QUARTERLY.value,
            "period_start": period_start,
            "period_end": period_end,
            "total_subjects_exposed": 500,
            "author": "Dr. Test Author",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/aggregate-reports", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["report_type"] == "DSUR"
        assert body["total_subjects_exposed"] == 500
        assert body["total_aes"] == 0
        assert body["total_saes"] == 0

    @pytest.mark.anyio
    async def test_create_report_various_types(self):
        for report_type in ["DSUR", "PBRER", "PSUR", "IND Safety Report"]:
            period_start = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            period_end = datetime.now(timezone.utc).isoformat()
            payload = {
                "trial_id": DUPIXENT_TRIAL,
                "report_type": report_type,
                "period": ReportPeriod.MONTHLY.value,
                "period_start": period_start,
                "period_end": period_end,
                "total_subjects_exposed": 100,
                "author": "Test",
            }
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
                resp = await ac.post(f"{API_PREFIX}/aggregate-reports", json=payload)
            assert resp.status_code == 201
            assert resp.json()["report_type"] == report_type

    @pytest.mark.anyio
    async def test_get_report(self, svc: SafetySignalDetectionService):
        reports = svc.list_aggregate_reports()
        report_id = reports[0].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/aggregate-reports/{report_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == report_id

    @pytest.mark.anyio
    async def test_get_report_not_found(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/aggregate-reports/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_report_aes(self, svc: SafetySignalDetectionService):
        reports = svc.list_aggregate_reports()
        report_id = reports[0].id
        payload = {"total_aes": 999, "total_saes": 50}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.put(f"{API_PREFIX}/aggregate-reports/{report_id}", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_aes"] == 999
        assert body["total_saes"] == 50

    @pytest.mark.anyio
    async def test_update_report_deaths(self, svc: SafetySignalDetectionService):
        reports = svc.list_aggregate_reports()
        report_id = reports[0].id
        payload = {"deaths": 5}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.put(f"{API_PREFIX}/aggregate-reports/{report_id}", json=payload)
        assert resp.status_code == 200
        assert resp.json()["deaths"] == 5

    @pytest.mark.anyio
    async def test_update_report_benefit_risk(self, svc: SafetySignalDetectionService):
        reports = svc.list_aggregate_reports()
        report_id = reports[0].id
        payload = {"benefit_risk_conclusion": "Updated conclusion"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.put(f"{API_PREFIX}/aggregate-reports/{report_id}", json=payload)
        assert resp.status_code == 200
        assert resp.json()["benefit_risk_conclusion"] == "Updated conclusion"

    @pytest.mark.anyio
    async def test_update_report_reviewer(self, svc: SafetySignalDetectionService):
        reports = svc.list_aggregate_reports()
        report_id = reports[0].id
        payload = {"reviewer": "Dr. New Reviewer"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.put(f"{API_PREFIX}/aggregate-reports/{report_id}", json=payload)
        assert resp.status_code == 200
        assert resp.json()["reviewer"] == "Dr. New Reviewer"

    @pytest.mark.anyio
    async def test_update_report_new_signals(self, svc: SafetySignalDetectionService):
        reports = svc.list_aggregate_reports()
        report_id = reports[0].id
        payload = {"new_signals": 7}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.put(f"{API_PREFIX}/aggregate-reports/{report_id}", json=payload)
        assert resp.status_code == 200
        assert resp.json()["new_signals"] == 7

    @pytest.mark.anyio
    async def test_update_report_not_found(self):
        payload = {"total_aes": 100}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.put(f"{API_PREFIX}/aggregate-reports/nonexistent", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_report(self, svc: SafetySignalDetectionService):
        reports = svc.list_aggregate_reports()
        report_id = reports[0].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.delete(f"{API_PREFIX}/aggregate-reports/{report_id}")
        assert resp.status_code == 204
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/aggregate-reports/{report_id}")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_report_not_found(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.delete(f"{API_PREFIX}/aggregate-reports/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_report_reduces_count(self, svc: SafetySignalDetectionService):
        reports = svc.list_aggregate_reports()
        initial = len(reports)
        report_id = reports[0].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            await ac.delete(f"{API_PREFIX}/aggregate-reports/{report_id}")
            resp = await ac.get(f"{API_PREFIX}/aggregate-reports")
        assert resp.json()["total"] == initial - 1

    @pytest.mark.anyio
    async def test_create_report_validation_missing_fields(self):
        payload = {"trial_id": EYLEA_TRIAL}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/aggregate-reports", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_report_invalid_period(self):
        period_start = datetime.now(timezone.utc).isoformat()
        period_end = datetime.now(timezone.utc).isoformat()
        payload = {
            "trial_id": EYLEA_TRIAL,
            "report_type": "DSUR",
            "period": "invalid_period",
            "period_start": period_start,
            "period_end": period_end,
            "total_subjects_exposed": 100,
            "author": "Test",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/aggregate-reports", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_report_negative_subjects(self):
        period_start = datetime.now(timezone.utc).isoformat()
        period_end = datetime.now(timezone.utc).isoformat()
        payload = {
            "trial_id": EYLEA_TRIAL,
            "report_type": "DSUR",
            "period": ReportPeriod.QUARTERLY.value,
            "period_start": period_start,
            "period_end": period_end,
            "total_subjects_exposed": -1,
            "author": "Test",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/aggregate-reports", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_report_roundtrip(self):
        period_start = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        period_end = datetime.now(timezone.utc).isoformat()
        payload = {
            "trial_id": LIBTAYO_TRIAL,
            "report_type": "Ad Hoc Report",
            "period": ReportPeriod.AD_HOC.value,
            "period_start": period_start,
            "period_end": period_end,
            "total_subjects_exposed": 250,
            "author": "Dr. Roundtrip Author",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            create_resp = await ac.post(f"{API_PREFIX}/aggregate-reports", json=payload)
            report_id = create_resp.json()["id"]
            get_resp = await ac.get(f"{API_PREFIX}/aggregate-reports/{report_id}")
        body = get_resp.json()
        assert body["report_type"] == "Ad Hoc Report"
        assert body["total_subjects_exposed"] == 250
        assert body["author"] == "Dr. Roundtrip Author"

    @pytest.mark.anyio
    async def test_update_report_multiple_fields(self, svc: SafetySignalDetectionService):
        reports = svc.list_aggregate_reports()
        report_id = reports[0].id
        payload = {
            "total_aes": 500,
            "total_saes": 25,
            "deaths": 3,
            "new_signals": 2,
            "benefit_risk_conclusion": "Multi-update conclusion",
            "reviewer": "Dr. Multi",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.put(f"{API_PREFIX}/aggregate-reports/{report_id}", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_aes"] == 500
        assert body["total_saes"] == 25
        assert body["deaths"] == 3
        assert body["new_signals"] == 2
        assert body["benefit_risk_conclusion"] == "Multi-update conclusion"
        assert body["reviewer"] == "Dr. Multi"


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class TestMetricsAPI:
    @pytest.mark.anyio
    async def test_get_metrics(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_signals"] == 12
        assert body["total_evaluations"] == 10
        assert body["total_cumulative_reviews"] == 10
        assert body["total_analyses"] == 10
        assert body["total_aggregate_reports"] == 10

    @pytest.mark.anyio
    async def test_metrics_signals_by_status(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/metrics")
        body = resp.json()
        by_status = body["signals_by_status"]
        assert isinstance(by_status, dict)
        assert len(by_status) > 0
        total = sum(by_status.values())
        assert total == 12

    @pytest.mark.anyio
    async def test_metrics_signals_by_priority(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/metrics")
        body = resp.json()
        by_priority = body["signals_by_priority"]
        assert isinstance(by_priority, dict)
        total = sum(by_priority.values())
        assert total == 12

    @pytest.mark.anyio
    async def test_metrics_signals_by_method(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/metrics")
        body = resp.json()
        by_method = body["signals_by_method"]
        assert isinstance(by_method, dict)
        total = sum(by_method.values())
        assert total == 12

    @pytest.mark.anyio
    async def test_metrics_confirmed_signals(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/metrics")
        body = resp.json()
        assert body["confirmed_signals"] >= 3  # EYLEA, DUPIXENT, LIBTAYO each have confirmed signals

    @pytest.mark.anyio
    async def test_metrics_evaluations_by_causality(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/metrics")
        body = resp.json()
        by_causality = body["evaluations_by_causality"]
        assert isinstance(by_causality, dict)
        total = sum(by_causality.values())
        assert total == 10

    @pytest.mark.anyio
    async def test_metrics_reports_by_period(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/metrics")
        body = resp.json()
        by_period = body["reports_by_period"]
        assert isinstance(by_period, dict)
        total = sum(by_period.values())
        assert total == 10

    @pytest.mark.anyio
    async def test_metrics_avg_signal_to_evaluation_days(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/metrics")
        body = resp.json()
        assert body["avg_signal_to_evaluation_days"] >= 0

    @pytest.mark.anyio
    async def test_metrics_after_create_signal(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/metrics")
            initial_total = resp.json()["total_signals"]
            payload = {
                "trial_id": EYLEA_TRIAL,
                "signal_name": "Metrics test signal",
                "preferred_term": "MTest",
                "detection_method": SignalMethod.PRR.value,
                "drug_name": "Aflibercept",
                "detected_by": "Test",
            }
            await ac.post(f"{API_PREFIX}/signals", json=payload)
            resp = await ac.get(f"{API_PREFIX}/metrics")
            assert resp.json()["total_signals"] == initial_total + 1

    @pytest.mark.anyio
    async def test_metrics_after_delete_signal(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        sig_id = signals[0].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/metrics")
            initial_total = resp.json()["total_signals"]
            await ac.delete(f"{API_PREFIX}/signals/{sig_id}")
            resp = await ac.get(f"{API_PREFIX}/metrics")
            assert resp.json()["total_signals"] == initial_total - 1

    @pytest.mark.anyio
    async def test_metrics_after_create_evaluation(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/metrics")
            initial_total = resp.json()["total_evaluations"]
            payload = {
                "signal_id": signals[0].id,
                "evaluator": "Dr. Metric",
                "clinical_significance": "Test",
                "overall_assessment": CausalityAssessment.POSSIBLE.value,
                "recommendation": "Test",
            }
            await ac.post(f"{API_PREFIX}/evaluations", json=payload)
            resp = await ac.get(f"{API_PREFIX}/metrics")
            assert resp.json()["total_evaluations"] == initial_total + 1

    @pytest.mark.anyio
    async def test_metrics_after_delete_evaluation(self, svc: SafetySignalDetectionService):
        evals = svc.list_evaluations()
        eval_id = evals[0].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/metrics")
            initial_total = resp.json()["total_evaluations"]
            await ac.delete(f"{API_PREFIX}/evaluations/{eval_id}")
            resp = await ac.get(f"{API_PREFIX}/metrics")
            assert resp.json()["total_evaluations"] == initial_total - 1

    @pytest.mark.anyio
    async def test_metrics_after_create_review(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/metrics")
            initial_total = resp.json()["total_cumulative_reviews"]
            payload = {
                "signal_id": signals[0].id,
                "review_period": ReportPeriod.QUARTERLY.value,
                "cumulative_cases": 10,
                "new_cases_in_period": 3,
                "total_exposure_patient_years": 500.0,
                "reviewer": "Dr. Metric",
                "conclusion": "Test",
            }
            await ac.post(f"{API_PREFIX}/cumulative-reviews", json=payload)
            resp = await ac.get(f"{API_PREFIX}/metrics")
            assert resp.json()["total_cumulative_reviews"] == initial_total + 1

    @pytest.mark.anyio
    async def test_metrics_after_create_analysis(self):
        cutoff = datetime.now(timezone.utc).isoformat()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/metrics")
            initial_total = resp.json()["total_analyses"]
            payload = {
                "trial_id": EYLEA_TRIAL,
                "analysis_name": "Metrics analysis",
                "method": SignalMethod.PRR.value,
                "data_cutoff_date": cutoff,
                "run_by": "Test",
            }
            await ac.post(f"{API_PREFIX}/analyses", json=payload)
            resp = await ac.get(f"{API_PREFIX}/metrics")
            assert resp.json()["total_analyses"] == initial_total + 1

    @pytest.mark.anyio
    async def test_metrics_after_create_report(self):
        period_start = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        period_end = datetime.now(timezone.utc).isoformat()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/metrics")
            initial_total = resp.json()["total_aggregate_reports"]
            payload = {
                "trial_id": EYLEA_TRIAL,
                "report_type": "DSUR",
                "period": ReportPeriod.QUARTERLY.value,
                "period_start": period_start,
                "period_end": period_end,
                "total_subjects_exposed": 100,
                "author": "Test",
            }
            await ac.post(f"{API_PREFIX}/aggregate-reports", json=payload)
            resp = await ac.get(f"{API_PREFIX}/metrics")
            assert resp.json()["total_aggregate_reports"] == initial_total + 1


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------


class TestServiceDirect:
    @pytest.mark.anyio
    async def test_service_singleton(self):
        svc1 = get_safety_signal_detection_service()
        svc2 = get_safety_signal_detection_service()
        assert svc1 is svc2

    @pytest.mark.anyio
    async def test_service_reset(self):
        svc1 = get_safety_signal_detection_service()
        svc2 = reset_safety_signal_detection_service()
        assert svc1 is not svc2

    @pytest.mark.anyio
    async def test_service_reset_preserves_seed_data(self):
        svc = reset_safety_signal_detection_service()
        assert len(svc.list_signals()) == 12
        assert len(svc.list_evaluations()) == 10
        assert len(svc.list_cumulative_reviews()) == 10
        assert len(svc.list_analyses()) == 10
        assert len(svc.list_aggregate_reports()) == 10

    @pytest.mark.anyio
    async def test_service_create_signal_returns_detected_status(self, svc: SafetySignalDetectionService):
        payload = SafetySignalCreate(
            trial_id=EYLEA_TRIAL,
            signal_name="Direct test",
            preferred_term="DT",
            detection_method=SignalMethod.PRR,
            drug_name="Aflibercept",
            detected_by="Test",
        )
        signal = svc.create_signal(payload)
        assert signal.status == SignalStatus.DETECTED

    @pytest.mark.anyio
    async def test_service_update_nonexistent_signal(self, svc: SafetySignalDetectionService):
        payload = SafetySignalUpdate(status=SignalStatus.CLOSED)
        result = svc.update_signal("nonexistent", payload)
        assert result is None

    @pytest.mark.anyio
    async def test_service_delete_nonexistent_signal(self, svc: SafetySignalDetectionService):
        assert svc.delete_signal("nonexistent") is False

    @pytest.mark.anyio
    async def test_service_get_nonexistent_signal(self, svc: SafetySignalDetectionService):
        assert svc.get_signal("nonexistent") is None

    @pytest.mark.anyio
    async def test_service_create_evaluation_sets_date(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        payload = SignalEvaluationCreate(
            signal_id=signals[0].id,
            evaluator="Test",
            clinical_significance="Test",
            overall_assessment=CausalityAssessment.POSSIBLE,
            recommendation="Test",
        )
        ev = svc.create_evaluation(payload)
        assert ev.evaluation_date is not None

    @pytest.mark.anyio
    async def test_service_create_review_calculates_incidence_rate(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        payload = CumulativeReviewCreate(
            signal_id=signals[0].id,
            review_period=ReportPeriod.QUARTERLY,
            cumulative_cases=20,
            new_cases_in_period=5,
            total_exposure_patient_years=1000.0,
            reviewer="Test",
            conclusion="Test",
        )
        review = svc.create_cumulative_review(payload)
        assert review.incidence_rate == pytest.approx(20.0, abs=0.01)  # 20/1000*1000

    @pytest.mark.anyio
    async def test_service_create_review_zero_exposure_no_rate(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        payload = CumulativeReviewCreate(
            signal_id=signals[0].id,
            review_period=ReportPeriod.MONTHLY,
            cumulative_cases=0,
            new_cases_in_period=0,
            total_exposure_patient_years=0.0,
            reviewer="Test",
            conclusion="Test",
        )
        review = svc.create_cumulative_review(payload)
        assert review.incidence_rate is None

    @pytest.mark.anyio
    async def test_service_create_analysis_running_status(self, svc: SafetySignalDetectionService):
        payload = DisproportionalityAnalysisCreate(
            trial_id=EYLEA_TRIAL,
            analysis_name="Test",
            method=SignalMethod.PRR,
            data_cutoff_date=datetime.now(timezone.utc),
            run_by="Test",
        )
        analysis = svc.create_analysis(payload)
        assert analysis.status == "running"
        assert analysis.signals_detected == 0

    @pytest.mark.anyio
    async def test_service_update_nonexistent_analysis(self, svc: SafetySignalDetectionService):
        payload = DisproportionalityAnalysisUpdate(status="completed")
        result = svc.update_analysis("nonexistent", payload)
        assert result is None

    @pytest.mark.anyio
    async def test_service_create_aggregate_report_defaults(self, svc: SafetySignalDetectionService):
        payload = AggregateSafetyReportCreate(
            trial_id=EYLEA_TRIAL,
            report_type="DSUR",
            period=ReportPeriod.ANNUAL,
            period_start=datetime.now(timezone.utc) - timedelta(days=365),
            period_end=datetime.now(timezone.utc),
            total_subjects_exposed=1000,
            author="Test",
        )
        report = svc.create_aggregate_report(payload)
        assert report.total_aes == 0
        assert report.total_saes == 0
        assert report.deaths == 0
        assert report.new_signals == 0

    @pytest.mark.anyio
    async def test_service_update_nonexistent_report(self, svc: SafetySignalDetectionService):
        payload = AggregateSafetyReportUpdate(total_aes=100)
        result = svc.update_aggregate_report("nonexistent", payload)
        assert result is None

    @pytest.mark.anyio
    async def test_service_delete_nonexistent_evaluation(self, svc: SafetySignalDetectionService):
        assert svc.delete_evaluation("nonexistent") is False

    @pytest.mark.anyio
    async def test_service_delete_nonexistent_review(self, svc: SafetySignalDetectionService):
        assert svc.delete_cumulative_review("nonexistent") is False

    @pytest.mark.anyio
    async def test_service_delete_nonexistent_analysis(self, svc: SafetySignalDetectionService):
        assert svc.delete_analysis("nonexistent") is False

    @pytest.mark.anyio
    async def test_service_delete_nonexistent_report(self, svc: SafetySignalDetectionService):
        assert svc.delete_aggregate_report("nonexistent") is False

    @pytest.mark.anyio
    async def test_service_get_nonexistent_evaluation(self, svc: SafetySignalDetectionService):
        assert svc.get_evaluation("nonexistent") is None

    @pytest.mark.anyio
    async def test_service_get_nonexistent_review(self, svc: SafetySignalDetectionService):
        assert svc.get_cumulative_review("nonexistent") is None

    @pytest.mark.anyio
    async def test_service_get_nonexistent_analysis(self, svc: SafetySignalDetectionService):
        assert svc.get_analysis("nonexistent") is None

    @pytest.mark.anyio
    async def test_service_get_nonexistent_report(self, svc: SafetySignalDetectionService):
        assert svc.get_aggregate_report("nonexistent") is None

    @pytest.mark.anyio
    async def test_service_metrics_structure(self, svc: SafetySignalDetectionService):
        metrics = svc.get_metrics()
        assert metrics.total_signals >= 0
        assert isinstance(metrics.signals_by_status, dict)
        assert isinstance(metrics.signals_by_priority, dict)
        assert isinstance(metrics.signals_by_method, dict)
        assert metrics.confirmed_signals >= 0
        assert metrics.total_evaluations >= 0
        assert isinstance(metrics.evaluations_by_causality, dict)
        assert metrics.total_cumulative_reviews >= 0
        assert metrics.total_analyses >= 0
        assert metrics.total_aggregate_reports >= 0
        assert isinstance(metrics.reports_by_period, dict)
        assert metrics.avg_signal_to_evaluation_days >= 0


# ---------------------------------------------------------------------------
# Edge cases and additional coverage
# ---------------------------------------------------------------------------


class TestEdgeCases:
    @pytest.mark.anyio
    async def test_create_signal_with_all_optional_fields(self):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "signal_name": "Full signal",
            "preferred_term": "Full PT",
            "meddra_code": "10099001",
            "soc": "Full SOC",
            "detection_method": SignalMethod.EBGM.value,
            "priority": SignalPriority.HIGH.value,
            "drug_name": "Aflibercept",
            "comparator": "Ranibizumab",
            "observed_cases": 25,
            "expected_cases": 10.5,
            "detected_by": "Full Test",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/signals", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["meddra_code"] == "10099001"
        assert body["soc"] == "Full SOC"
        assert body["comparator"] == "Ranibizumab"

    @pytest.mark.anyio
    async def test_create_signal_zero_observed_cases(self):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "signal_name": "Zero cases",
            "preferred_term": "Zero PT",
            "detection_method": SignalMethod.PRR.value,
            "drug_name": "Aflibercept",
            "detected_by": "Test",
            "observed_cases": 0,
            "expected_cases": 0.0,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/signals", json=payload)
        assert resp.status_code == 201
        assert resp.json()["observed_cases"] == 0

    @pytest.mark.anyio
    async def test_signal_update_preserves_other_fields(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        sig = signals[0]
        original_name = sig.signal_name
        original_drug = sig.drug_name
        payload = {"status": SignalStatus.CLOSED.value}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.put(f"{API_PREFIX}/signals/{sig.id}", json=payload)
        body = resp.json()
        assert body["signal_name"] == original_name
        assert body["drug_name"] == original_drug
        assert body["status"] == SignalStatus.CLOSED.value

    @pytest.mark.anyio
    async def test_multiple_evaluations_for_same_signal(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        signal_id = signals[0].id
        for i in range(3):
            payload = {
                "signal_id": signal_id,
                "evaluator": f"Dr. Eval {i}",
                "clinical_significance": f"Significance {i}",
                "overall_assessment": CausalityAssessment.POSSIBLE.value,
                "recommendation": f"Recommendation {i}",
            }
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
                resp = await ac.post(f"{API_PREFIX}/evaluations", json=payload)
                assert resp.status_code == 201

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/evaluations", params={"signal_id": signal_id})
        # Original seed data + 3 new ones
        assert resp.json()["total"] >= 3

    @pytest.mark.anyio
    async def test_all_signal_methods_accepted(self):
        for method in SignalMethod:
            payload = {
                "trial_id": EYLEA_TRIAL,
                "signal_name": f"Method {method.value}",
                "preferred_term": "PT",
                "detection_method": method.value,
                "drug_name": "Drug",
                "detected_by": "Test",
            }
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
                resp = await ac.post(f"{API_PREFIX}/signals", json=payload)
            assert resp.status_code == 201, f"Failed for method {method.value}"

    @pytest.mark.anyio
    async def test_all_signal_priorities_accepted(self):
        for priority in SignalPriority:
            payload = {
                "trial_id": EYLEA_TRIAL,
                "signal_name": f"Priority {priority.value}",
                "preferred_term": "PT",
                "detection_method": SignalMethod.PRR.value,
                "priority": priority.value,
                "drug_name": "Drug",
                "detected_by": "Test",
            }
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
                resp = await ac.post(f"{API_PREFIX}/signals", json=payload)
            assert resp.status_code == 201, f"Failed for priority {priority.value}"

    @pytest.mark.anyio
    async def test_all_report_periods_accepted(self):
        for period in ReportPeriod:
            period_start = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            period_end = datetime.now(timezone.utc).isoformat()
            payload = {
                "trial_id": EYLEA_TRIAL,
                "report_type": "Test",
                "period": period.value,
                "period_start": period_start,
                "period_end": period_end,
                "total_subjects_exposed": 100,
                "author": "Test",
            }
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
                resp = await ac.post(f"{API_PREFIX}/aggregate-reports", json=payload)
            assert resp.status_code == 201, f"Failed for period {period.value}"

    @pytest.mark.anyio
    async def test_all_causality_assessments_accepted(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        for assessment in CausalityAssessment:
            payload = {
                "signal_id": signals[0].id,
                "evaluator": f"Dr. {assessment.value}",
                "clinical_significance": "Test",
                "overall_assessment": assessment.value,
                "recommendation": "Test",
            }
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
                resp = await ac.post(f"{API_PREFIX}/evaluations", json=payload)
            assert resp.status_code == 201, f"Failed for assessment {assessment.value}"

    @pytest.mark.anyio
    async def test_all_review_periods_accepted(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        for period in ReportPeriod:
            payload = {
                "signal_id": signals[0].id,
                "review_period": period.value,
                "cumulative_cases": 5,
                "new_cases_in_period": 1,
                "total_exposure_patient_years": 100.0,
                "reviewer": "Test",
                "conclusion": "Test",
            }
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
                resp = await ac.post(f"{API_PREFIX}/cumulative-reviews", json=payload)
            assert resp.status_code == 201, f"Failed for period {period.value}"

    @pytest.mark.anyio
    async def test_empty_update_preserves_all_fields(self, svc: SafetySignalDetectionService):
        signals = svc.list_signals()
        sig = signals[0]
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.put(f"{API_PREFIX}/signals/{sig.id}", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["signal_name"] == sig.signal_name
        assert body["status"] == sig.status.value

    @pytest.mark.anyio
    async def test_analysis_update_preserves_other_fields(self, svc: SafetySignalDetectionService):
        analyses = svc.list_analyses()
        analysis = analyses[0]
        original_name = analysis.analysis_name
        payload = {"status": "updated_status"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.put(f"{API_PREFIX}/analyses/{analysis.id}", json=payload)
        body = resp.json()
        assert body["analysis_name"] == original_name
        assert body["status"] == "updated_status"

    @pytest.mark.anyio
    async def test_report_update_preserves_other_fields(self, svc: SafetySignalDetectionService):
        reports = svc.list_aggregate_reports()
        report = reports[0]
        original_type = report.report_type
        payload = {"total_aes": 9999}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.put(f"{API_PREFIX}/aggregate-reports/{report.id}", json=payload)
        body = resp.json()
        assert body["report_type"] == original_type
        assert body["total_aes"] == 9999

    @pytest.mark.anyio
    async def test_concurrent_creates_no_data_loss(self, svc: SafetySignalDetectionService):
        """Create multiple signals sequentially and verify all exist."""
        created_ids = []
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            for i in range(5):
                payload = {
                    "trial_id": EYLEA_TRIAL,
                    "signal_name": f"Concurrent {i}",
                    "preferred_term": "PT",
                    "detection_method": SignalMethod.PRR.value,
                    "drug_name": "Drug",
                    "detected_by": "Test",
                }
                resp = await ac.post(f"{API_PREFIX}/signals", json=payload)
                assert resp.status_code == 201
                created_ids.append(resp.json()["id"])

            # Verify all exist
            for sig_id in created_ids:
                resp = await ac.get(f"{API_PREFIX}/signals/{sig_id}")
                assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_delete_all_seed_signals(self, svc: SafetySignalDetectionService):
        """Delete all seed signals one by one."""
        signals = svc.list_signals()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            for s in signals:
                resp = await ac.delete(f"{API_PREFIX}/signals/{s.id}")
                assert resp.status_code == 204
            resp = await ac.get(f"{API_PREFIX}/signals")
            assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_metrics_with_no_data(self, svc: SafetySignalDetectionService):
        """Clear all data and check metrics return zeros."""
        # Clear all data manually
        svc._signals.clear()
        svc._evaluations.clear()
        svc._cumulative_reviews.clear()
        svc._analyses.clear()
        svc._aggregate_reports.clear()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_signals"] == 0
        assert body["confirmed_signals"] == 0
        assert body["total_evaluations"] == 0
        assert body["total_cumulative_reviews"] == 0
        assert body["total_analyses"] == 0
        assert body["total_aggregate_reports"] == 0
        assert body["avg_signal_to_evaluation_days"] == 0

    @pytest.mark.anyio
    async def test_create_signal_each_status_via_update(self, svc: SafetySignalDetectionService):
        """Create a signal and cycle through all statuses."""
        payload = {
            "trial_id": EYLEA_TRIAL,
            "signal_name": "Status cycle",
            "preferred_term": "PT",
            "detection_method": SignalMethod.PRR.value,
            "drug_name": "Drug",
            "detected_by": "Test",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/signals", json=payload)
            sig_id = resp.json()["id"]
            for status in SignalStatus:
                resp = await ac.put(f"{API_PREFIX}/signals/{sig_id}", json={"status": status.value})
                assert resp.status_code == 200
                assert resp.json()["status"] == status.value

    @pytest.mark.anyio
    async def test_list_signals_no_filter_returns_all(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get(f"{API_PREFIX}/signals")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_create_signal_empty_body(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/signals", json={})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_evaluation_empty_body(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/evaluations", json={})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_review_empty_body(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/cumulative-reviews", json={})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_analysis_empty_body(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/analyses", json={})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_report_empty_body(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.post(f"{API_PREFIX}/aggregate-reports", json={})
        assert resp.status_code == 422
