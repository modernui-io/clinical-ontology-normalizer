"""Tests for Safety Signal Detection (Pharmacovigilance).

Covers:
- Seed data verification (signals, evaluations)
- Signal CRUD (create, read, update, delete, list, filters)
- Signal lifecycle transitions (evaluate, confirm, refute, close)
- Signal evaluations (create, list)
- Signal detection metrics
- Error handling (404s, 400s, invalid lifecycle transitions)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.signal_detection import (
    DisproportionalityMethod,
    SignalPriority,
    SignalSource,
    SignalStatus,
)
from app.services.signal_detection_service import (
    SignalDetectionService,
    get_signal_detection_service,
    reset_signal_detection_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_PREFIX = "/api/v1/signal-detection"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_signal_detection_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> SignalDetectionService:
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


def _make_signal_create(**overrides) -> dict:
    defaults = {
        "title": "Test signal for adverse reaction",
        "description": "A test signal describing a potential adverse reaction.",
        "priority": "high",
        "source": "clinical_trial",
        "drug_name": "TestDrug",
        "trial_ids": ["TRIAL-001"],
        "preferred_term": "Headache",
        "soc": "Nervous system disorders",
        "observed_count": 20,
        "expected_count": 5.0,
        "disproportionality_score": 4.0,
        "method_used": "prr",
        "reporter": "Test Reporter",
    }
    defaults.update(overrides)
    return defaults


def _make_evaluation_create(**overrides) -> dict:
    defaults = {
        "evaluator": "Dr. Test Evaluator",
        "conclusion": "Signal appears to be valid based on evidence.",
        "supporting_evidence": "20 cases observed versus 5 expected.",
        "recommendation": "Continue monitoring and initiate formal review.",
        "causality_assessment": "probable",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_signals_count(self, svc: SignalDetectionService):
        signals = svc.list_signals()
        assert len(signals) == 10

    def test_seed_signals_all_statuses_present(self, svc: SignalDetectionService):
        signals = svc.list_signals()
        statuses = {s.status for s in signals}
        assert SignalStatus.NEW in statuses
        assert SignalStatus.UNDER_EVALUATION in statuses
        assert SignalStatus.CONFIRMED in statuses
        assert SignalStatus.REFUTED in statuses
        assert SignalStatus.CLOSED in statuses

    def test_seed_signals_all_priorities_present(self, svc: SignalDetectionService):
        signals = svc.list_signals()
        priorities = {s.priority for s in signals}
        assert SignalPriority.URGENT in priorities
        assert SignalPriority.HIGH in priorities
        assert SignalPriority.MEDIUM in priorities
        assert SignalPriority.LOW in priorities

    def test_seed_signals_all_sources_present(self, svc: SignalDetectionService):
        signals = svc.list_signals()
        sources = {s.source for s in signals}
        assert SignalSource.SPONTANEOUS_REPORTS in sources
        assert SignalSource.CLINICAL_TRIAL in sources
        assert SignalSource.LITERATURE in sources
        assert SignalSource.REGISTRY in sources
        assert SignalSource.REAL_WORLD_DATA in sources

    def test_seed_evaluations_count(self, svc: SignalDetectionService):
        # Count all evaluations across all signals
        all_evals = []
        for sig in svc.list_signals():
            all_evals.extend(svc.list_evaluations(sig.id))
        assert len(all_evals) == 6

    def test_seed_signal_has_expected_fields(self, svc: SignalDetectionService):
        signal = svc.get_signal("SIG-001")
        assert signal is not None
        assert signal.signal_number == "SIG-2026-001"
        assert signal.drug_name == "Dupilumab"
        assert signal.preferred_term == "Hepatotoxicity"
        assert signal.method_used == DisproportionalityMethod.PRR


# =====================================================================
# SIGNAL CRUD
# =====================================================================


class TestSignalCrud:
    """Test signal create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_signals(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_signals_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals", params={"status": "new"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "new"
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_list_signals_filter_priority(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals", params={"priority": "urgent"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["priority"] == "urgent"
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_list_signals_filter_source(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals", params={"source": "clinical_trial"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["source"] == "clinical_trial"
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_list_signals_filter_drug_name(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals", params={"drug_name": "Dupilumab"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["drug_name"] == "Dupilumab"
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_get_signal(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals/SIG-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SIG-001"
        assert data["drug_name"] == "Dupilumab"

    @pytest.mark.anyio
    async def test_get_signal_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals/SIG-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_signal(self, client: AsyncClient):
        payload = _make_signal_create()
        resp = await client.post(f"{API_PREFIX}/signals", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test signal for adverse reaction"
        assert data["status"] == "new"
        assert data["id"].startswith("SIG-")

    @pytest.mark.anyio
    async def test_update_signal(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/signals/SIG-001",
            json={"title": "Updated signal title", "priority": "urgent"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated signal title"
        assert data["priority"] == "urgent"

    @pytest.mark.anyio
    async def test_update_signal_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/signals/SIG-NONEXISTENT",
            json={"title": "Updated"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_signal(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/signals/SIG-003")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/signals/SIG-003")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_signal_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/signals/SIG-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_signal_removes_evaluations(self, client: AsyncClient):
        """Deleting a signal also removes its evaluations."""
        # SIG-001 has evaluations
        resp = await client.get(f"{API_PREFIX}/signals/SIG-001/evaluations")
        assert resp.status_code == 200
        assert resp.json()["total"] > 0
        # Delete the signal
        resp = await client.delete(f"{API_PREFIX}/signals/SIG-001")
        assert resp.status_code == 204
        # Evaluations should be gone (signal not found)
        resp = await client.get(f"{API_PREFIX}/signals/SIG-001/evaluations")
        assert resp.status_code == 404


# =====================================================================
# SIGNAL LIFECYCLE TRANSITIONS
# =====================================================================


class TestSignalLifecycle:
    """Test signal lifecycle transitions."""

    @pytest.mark.anyio
    async def test_evaluate_signal(self, client: AsyncClient):
        """Transition a NEW signal to UNDER_EVALUATION."""
        resp = await client.post(f"{API_PREFIX}/signals/SIG-003/evaluate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "under_evaluation"
        assert data["evaluation_start_date"] is not None

    @pytest.mark.anyio
    async def test_evaluate_signal_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/signals/SIG-NONEXISTENT/evaluate")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_evaluate_signal_wrong_status(self, client: AsyncClient):
        """Cannot evaluate a signal that is not in 'new' status."""
        # SIG-001 is under_evaluation
        resp = await client.post(f"{API_PREFIX}/signals/SIG-001/evaluate")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_confirm_signal(self, client: AsyncClient):
        """Confirm a signal that is under_evaluation."""
        # SIG-001 is under_evaluation
        resp = await client.post(f"{API_PREFIX}/signals/SIG-001/confirm")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "confirmed"
        assert data["confirmed_date"] is not None

    @pytest.mark.anyio
    async def test_confirm_signal_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/signals/SIG-NONEXISTENT/confirm")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_confirm_signal_wrong_status(self, client: AsyncClient):
        """Cannot confirm a signal that is not under_evaluation."""
        # SIG-003 is new
        resp = await client.post(f"{API_PREFIX}/signals/SIG-003/confirm")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_refute_signal(self, client: AsyncClient):
        """Refute a signal that is under_evaluation."""
        # SIG-005 is under_evaluation
        resp = await client.post(f"{API_PREFIX}/signals/SIG-005/refute")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "refuted"
        assert data["closed_date"] is not None

    @pytest.mark.anyio
    async def test_refute_signal_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/signals/SIG-NONEXISTENT/refute")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_refute_signal_wrong_status(self, client: AsyncClient):
        """Cannot refute a signal that is not under_evaluation."""
        # SIG-003 is new
        resp = await client.post(f"{API_PREFIX}/signals/SIG-003/refute")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_close_signal_from_confirmed(self, client: AsyncClient):
        """Close a confirmed signal."""
        # SIG-002 is confirmed
        resp = await client.post(f"{API_PREFIX}/signals/SIG-002/close")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "closed"
        assert data["closed_date"] is not None

    @pytest.mark.anyio
    async def test_close_signal_from_refuted(self, client: AsyncClient):
        """Close a refuted signal."""
        # SIG-004 is refuted
        resp = await client.post(f"{API_PREFIX}/signals/SIG-004/close")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "closed"

    @pytest.mark.anyio
    async def test_close_signal_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/signals/SIG-NONEXISTENT/close")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_close_signal_wrong_status(self, client: AsyncClient):
        """Cannot close a signal that is not confirmed or refuted."""
        # SIG-003 is new
        resp = await client.post(f"{API_PREFIX}/signals/SIG-003/close")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_full_lifecycle_new_to_closed(self, client: AsyncClient):
        """Walk a signal through the full lifecycle: new -> evaluate -> confirm -> close."""
        # SIG-003 is new
        resp = await client.post(f"{API_PREFIX}/signals/SIG-003/evaluate")
        assert resp.status_code == 200
        assert resp.json()["status"] == "under_evaluation"

        resp = await client.post(f"{API_PREFIX}/signals/SIG-003/confirm")
        assert resp.status_code == 200
        assert resp.json()["status"] == "confirmed"

        resp = await client.post(f"{API_PREFIX}/signals/SIG-003/close")
        assert resp.status_code == 200
        assert resp.json()["status"] == "closed"


# =====================================================================
# SIGNAL EVALUATIONS
# =====================================================================


class TestSignalEvaluations:
    """Test signal evaluation operations."""

    @pytest.mark.anyio
    async def test_list_evaluations_for_signal(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals/SIG-002/evaluations")
        assert resp.status_code == 200
        data = resp.json()
        # SIG-002 has 2 evaluations (EVAL-002, EVAL-003)
        assert data["total"] == 2
        for item in data["items"]:
            assert item["signal_id"] == "SIG-002"

    @pytest.mark.anyio
    async def test_list_evaluations_signal_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals/SIG-NONEXISTENT/evaluations")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_evaluations_signal_no_evals(self, client: AsyncClient):
        """Signal with no evaluations returns empty list."""
        # SIG-003 (new) has no evaluations
        resp = await client.get(f"{API_PREFIX}/signals/SIG-003/evaluations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.anyio
    async def test_create_evaluation(self, client: AsyncClient):
        payload = _make_evaluation_create()
        resp = await client.post(f"{API_PREFIX}/signals/SIG-001/evaluations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["signal_id"] == "SIG-001"
        assert data["evaluator"] == "Dr. Test Evaluator"
        assert data["id"].startswith("EVAL-")

    @pytest.mark.anyio
    async def test_create_evaluation_signal_not_found(self, client: AsyncClient):
        payload = _make_evaluation_create()
        resp = await client.post(f"{API_PREFIX}/signals/SIG-NONEXISTENT/evaluations", json=payload)
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestSignalMetrics:
    """Test signal detection metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_signals"] == 10
        assert data["total_evaluations"] == 6
        assert data["avg_disproportionality_score"] > 0
        assert data["confirmed_signals"] > 0
        assert data["refuted_signals"] > 0
        assert data["open_signals"] > 0
        assert data["urgent_signals"] > 0

    @pytest.mark.anyio
    async def test_metrics_signals_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_status = sum(data["signals_by_status"].values())
        assert total_by_status == data["total_signals"]

    @pytest.mark.anyio
    async def test_metrics_signals_by_priority(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_priority = sum(data["signals_by_priority"].values())
        assert total_by_priority == data["total_signals"]

    @pytest.mark.anyio
    async def test_metrics_signals_by_source(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_source = sum(data["signals_by_source"].values())
        assert total_by_source == data["total_signals"]

    def test_metrics_open_signals_count(self, svc: SignalDetectionService):
        metrics = svc.get_metrics()
        signals = svc.list_signals()
        open_count = sum(
            1 for s in signals
            if s.status in (SignalStatus.NEW, SignalStatus.UNDER_EVALUATION)
        )
        assert metrics.open_signals == open_count

    def test_metrics_urgent_signals_count(self, svc: SignalDetectionService):
        metrics = svc.get_metrics()
        signals = svc.list_signals()
        urgent_count = sum(1 for s in signals if s.priority == SignalPriority.URGENT)
        assert metrics.urgent_signals == urgent_count

    def test_metrics_after_signal_creation(self, svc: SignalDetectionService):
        """Metrics update after creating a new signal."""
        from app.schemas.signal_detection import SignalCreate
        before = svc.get_metrics()
        svc.create_signal(SignalCreate(
            title="New test signal",
            description="Description",
            priority=SignalPriority.LOW,
            source=SignalSource.LITERATURE,
            drug_name="TestDrug",
            preferred_term="Nausea",
            soc="Gastrointestinal disorders",
            observed_count=10,
            expected_count=3.0,
            disproportionality_score=3.3,
            method_used=DisproportionalityMethod.PRR,
            reporter="Test",
        ))
        after = svc.get_metrics()
        assert after.total_signals == before.total_signals + 1


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_signal_detection_service()
        svc2 = get_signal_detection_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_signal_detection_service()
        svc2 = reset_signal_detection_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_signal_detection_service()
        svc.delete_signal("SIG-001")
        assert svc.get_signal("SIG-001") is None
        svc2 = reset_signal_detection_service()
        assert svc2.get_signal("SIG-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_signals_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_signals_nonexistent_drug(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals", params={"drug_name": "NonexistentDrug"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_create_signal_with_all_fields(self, client: AsyncClient):
        payload = _make_signal_create(
            assigned_evaluator="Dr. Test",
            trial_ids=["TRIAL-001", "TRIAL-002"],
        )
        resp = await client.post(f"{API_PREFIX}/signals", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["assigned_evaluator"] == "Dr. Test"
        assert len(data["trial_ids"]) == 2

    @pytest.mark.anyio
    async def test_create_signal_all_methods(self, client: AsyncClient):
        for method in ["prr", "ror", "bcpnn", "mgps", "ebgm"]:
            payload = _make_signal_create(method_used=method, title=f"Signal {method}")
            resp = await client.post(f"{API_PREFIX}/signals", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["method_used"] == method

    @pytest.mark.anyio
    async def test_create_signal_all_sources(self, client: AsyncClient):
        for source in ["spontaneous_reports", "clinical_trial", "literature", "registry", "real_world_data"]:
            payload = _make_signal_create(source=source, title=f"Signal {source}")
            resp = await client.post(f"{API_PREFIX}/signals", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["source"] == source

    @pytest.mark.anyio
    async def test_create_signal_all_priorities(self, client: AsyncClient):
        for priority in ["urgent", "high", "medium", "low"]:
            payload = _make_signal_create(priority=priority, title=f"Signal {priority}")
            resp = await client.post(f"{API_PREFIX}/signals", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["priority"] == priority

    @pytest.mark.anyio
    async def test_signal_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals/SIG-001")
        data = resp.json()
        assert "id" in data
        assert "signal_number" in data
        assert "title" in data
        assert "description" in data
        assert "status" in data
        assert "priority" in data
        assert "source" in data
        assert "detected_date" in data
        assert "drug_name" in data
        assert "preferred_term" in data
        assert "soc" in data
        assert "observed_count" in data
        assert "expected_count" in data
        assert "disproportionality_score" in data
        assert "method_used" in data
        assert "reporter" in data

    @pytest.mark.anyio
    async def test_signals_sorted_by_detected_date_descending(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals")
        data = resp.json()
        dates = [item["detected_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_update_signal_partial(self, client: AsyncClient):
        """Partial update should only change specified fields."""
        resp = await client.get(f"{API_PREFIX}/signals/SIG-001")
        original = resp.json()
        resp = await client.put(
            f"{API_PREFIX}/signals/SIG-001",
            json={"action_taken": "New action taken"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["action_taken"] == "New action taken"
        # Other fields unchanged
        assert data["title"] == original["title"]
        assert data["drug_name"] == original["drug_name"]
