"""P3-015: Tests for structured release quality gates."""

from __future__ import annotations

import pytest

from app.services.release_quality_gate_service import (
    DEFAULT_GATES,
    GateStatus,
    QualityGate,
    ReleaseGateReport,
    ReleaseQualityGateService,
    get_release_quality_gate_service,
    reset_release_quality_gate_service,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gate(name: str, status: GateStatus, required: bool = True) -> QualityGate:
    return QualityGate(
        gate_name=name,
        owner_role="Test",
        check_function=lambda s=status: s,
        required=required,
    )


# ===========================================================================
# QualityGate model
# ===========================================================================


class TestQualityGateModel:
    def test_default_status_is_skip(self):
        gate = QualityGate(
            gate_name="test",
            owner_role="Dev",
            check_function=lambda: GateStatus.PASS,
        )
        assert gate.status == GateStatus.SKIP

    def test_gate_status_values(self):
        assert GateStatus.PASS.value == "pass"
        assert GateStatus.FAIL.value == "fail"
        assert GateStatus.SKIP.value == "skip"

    def test_required_defaults_true(self):
        gate = QualityGate(
            gate_name="test",
            owner_role="Dev",
            check_function=lambda: GateStatus.PASS,
        )
        assert gate.required is True


# ===========================================================================
# Default gates
# ===========================================================================


class TestDefaultGates:
    def test_six_default_gates(self):
        assert len(DEFAULT_GATES) == 6

    def test_default_gate_names(self):
        names = {g.gate_name for g in DEFAULT_GATES}
        assert "All P0 items closed" in names
        assert "Test suite green" in names
        assert "Security scan clean" in names
        assert "Performance benchmarks pass" in names
        assert "Clinical safety regression pass" in names
        assert "Audit coverage verified" in names

    def test_default_gate_roles(self):
        roles = {g.owner_role for g in DEFAULT_GATES}
        assert roles == {"Program", "CTO", "CISO", "Ops", "Clinical AI", "Compliance"}

    def test_all_defaults_required(self):
        for gate in DEFAULT_GATES:
            assert gate.required is True


# ===========================================================================
# ReleaseQualityGateService
# ===========================================================================


class TestReleaseQualityGateService:
    def test_all_pass(self):
        gates = [
            _gate("G1", GateStatus.PASS),
            _gate("G2", GateStatus.PASS),
        ]
        svc = ReleaseQualityGateService(gates=gates)
        report = svc.evaluate_release_gates()
        assert report.all_passed is True
        assert report.blockers == []
        assert len(report.gates) == 2

    def test_required_failure_blocks(self):
        gates = [
            _gate("G1", GateStatus.PASS),
            _gate("G2", GateStatus.FAIL, required=True),
        ]
        svc = ReleaseQualityGateService(gates=gates)
        report = svc.evaluate_release_gates()
        assert report.all_passed is False
        assert "G2" in report.blockers

    def test_optional_failure_does_not_block(self):
        gates = [
            _gate("G1", GateStatus.PASS),
            _gate("G2", GateStatus.FAIL, required=False),
        ]
        svc = ReleaseQualityGateService(gates=gates)
        report = svc.evaluate_release_gates()
        assert report.all_passed is True
        assert report.blockers == []

    def test_exception_in_check_treated_as_fail(self):
        def _boom() -> GateStatus:
            raise RuntimeError("check crashed")

        gates = [
            QualityGate(
                gate_name="Crasher",
                owner_role="Dev",
                check_function=_boom,
                required=True,
            ),
        ]
        svc = ReleaseQualityGateService(gates=gates)
        report = svc.evaluate_release_gates()
        assert report.all_passed is False
        assert "Crasher" in report.blockers

    def test_skip_status_not_blocking(self):
        gates = [_gate("G1", GateStatus.SKIP, required=True)]
        svc = ReleaseQualityGateService(gates=gates)
        report = svc.evaluate_release_gates()
        # SKIP is not FAIL, so it should not block
        assert report.all_passed is True

    def test_multiple_blockers(self):
        gates = [
            _gate("G1", GateStatus.FAIL),
            _gate("G2", GateStatus.FAIL),
            _gate("G3", GateStatus.PASS),
        ]
        svc = ReleaseQualityGateService(gates=gates)
        report = svc.evaluate_release_gates()
        assert report.all_passed is False
        assert set(report.blockers) == {"G1", "G2"}

    def test_empty_gates_passes(self):
        svc = ReleaseQualityGateService(gates=[])
        report = svc.evaluate_release_gates()
        assert report.all_passed is True
        assert report.gates == []
        assert report.blockers == []

    def test_evaluated_at_populated(self):
        svc = ReleaseQualityGateService(gates=[])
        report = svc.evaluate_release_gates()
        assert report.evaluated_at is not None
        assert "T" in report.evaluated_at  # ISO format

    def test_default_gates_all_pass(self):
        """Default stub checks should all return PASS."""
        svc = ReleaseQualityGateService()
        report = svc.evaluate_release_gates()
        assert report.all_passed is True
        assert len(report.gates) == 6


# ===========================================================================
# ReleaseGateReport
# ===========================================================================


class TestReleaseGateReport:
    def test_report_fields(self):
        report = ReleaseGateReport(
            all_passed=True,
            gates=[],
            blockers=[],
        )
        assert report.all_passed is True
        assert report.gates == []
        assert report.blockers == []
        assert report.evaluated_at is not None


# ===========================================================================
# Singleton
# ===========================================================================


class TestSingleton:
    def test_get_service_returns_instance(self):
        reset_release_quality_gate_service()
        svc = get_release_quality_gate_service()
        assert isinstance(svc, ReleaseQualityGateService)

    def test_singleton_reuses_instance(self):
        reset_release_quality_gate_service()
        svc1 = get_release_quality_gate_service()
        svc2 = get_release_quality_gate_service()
        assert svc1 is svc2

    def test_reset_clears_singleton(self):
        reset_release_quality_gate_service()
        svc1 = get_release_quality_gate_service()
        reset_release_quality_gate_service()
        svc2 = get_release_quality_gate_service()
        assert svc1 is not svc2
