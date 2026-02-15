"""P3-015: Structured quality gates for release candidates.

Defines role-based quality gates that must pass before a release candidate
can be promoted. Each gate has an owner role, a check function, and a
required flag indicating whether failure blocks the release.

Default gates:
  1. All P0 items closed          (Program)
  2. Test suite green             (CTO)
  3. Security scan clean          (CISO)
  4. Performance benchmarks pass  (Ops)
  5. Clinical safety regression   (Clinical AI)
  6. Audit coverage verified      (Compliance)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable

logger = logging.getLogger(__name__)


class GateStatus(Enum):
    """Result status of a quality gate evaluation."""

    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"


@dataclass
class QualityGate:
    """A single quality gate for release readiness."""

    gate_name: str
    owner_role: str
    check_function: Callable[[], GateStatus]
    required: bool = True
    status: GateStatus = GateStatus.SKIP


@dataclass
class ReleaseGateReport:
    """Aggregated result of all quality gate evaluations."""

    all_passed: bool
    gates: list[QualityGate]
    blockers: list[str]
    evaluated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Default gate check functions (stubs -- replaced in production via DI)
# ---------------------------------------------------------------------------


def _check_p0_items_closed() -> GateStatus:
    """Check that all P0 backlog items are closed."""
    logger.info("Checking: all P0 items closed")
    return GateStatus.PASS


def _check_test_suite_green() -> GateStatus:
    """Check that the full test suite passes."""
    logger.info("Checking: test suite green")
    return GateStatus.PASS


def _check_security_scan_clean() -> GateStatus:
    """Check that the security scan has no critical findings."""
    logger.info("Checking: security scan clean")
    return GateStatus.PASS


def _check_performance_benchmarks() -> GateStatus:
    """Check that performance benchmarks meet thresholds."""
    logger.info("Checking: performance benchmarks pass")
    return GateStatus.PASS


def _check_clinical_safety_regression() -> GateStatus:
    """Check that clinical safety regression tests pass."""
    logger.info("Checking: clinical safety regression pass")
    return GateStatus.PASS


def _check_audit_coverage() -> GateStatus:
    """Check that audit coverage meets requirements."""
    logger.info("Checking: audit coverage verified")
    return GateStatus.PASS


# ---------------------------------------------------------------------------
# Default gate definitions
# ---------------------------------------------------------------------------

DEFAULT_GATES: list[QualityGate] = [
    QualityGate(
        gate_name="All P0 items closed",
        owner_role="Program",
        check_function=_check_p0_items_closed,
        required=True,
    ),
    QualityGate(
        gate_name="Test suite green",
        owner_role="CTO",
        check_function=_check_test_suite_green,
        required=True,
    ),
    QualityGate(
        gate_name="Security scan clean",
        owner_role="CISO",
        check_function=_check_security_scan_clean,
        required=True,
    ),
    QualityGate(
        gate_name="Performance benchmarks pass",
        owner_role="Ops",
        check_function=_check_performance_benchmarks,
        required=True,
    ),
    QualityGate(
        gate_name="Clinical safety regression pass",
        owner_role="Clinical AI",
        check_function=_check_clinical_safety_regression,
        required=True,
    ),
    QualityGate(
        gate_name="Audit coverage verified",
        owner_role="Compliance",
        check_function=_check_audit_coverage,
        required=True,
    ),
]


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ReleaseQualityGateService:
    """Evaluates quality gates for release candidates."""

    def __init__(self, gates: list[QualityGate] | None = None) -> None:
        if gates is not None:
            self._gates = gates
        else:
            # Deep-copy defaults so mutations don't leak between calls
            self._gates = [
                QualityGate(
                    gate_name=g.gate_name,
                    owner_role=g.owner_role,
                    check_function=g.check_function,
                    required=g.required,
                )
                for g in DEFAULT_GATES
            ]

    @property
    def gates(self) -> list[QualityGate]:
        return list(self._gates)

    def evaluate_release_gates(self) -> ReleaseGateReport:
        """Run all gates and produce a release gate report."""
        blockers: list[str] = []

        for gate in self._gates:
            try:
                gate.status = gate.check_function()
            except Exception as exc:
                logger.error(
                    "Gate '%s' raised an exception: %s", gate.gate_name, exc,
                )
                gate.status = GateStatus.FAIL

            if gate.status == GateStatus.FAIL and gate.required:
                blockers.append(gate.gate_name)

        all_passed = len(blockers) == 0

        report = ReleaseGateReport(
            all_passed=all_passed,
            gates=list(self._gates),
            blockers=blockers,
        )

        logger.info(
            "Release gate evaluation complete: %s (%d blockers)",
            "PASSED" if all_passed else "BLOCKED",
            len(blockers),
        )

        return report


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_instance: ReleaseQualityGateService | None = None


def get_release_quality_gate_service() -> ReleaseQualityGateService:
    """Get the singleton ReleaseQualityGateService."""
    global _instance
    if _instance is None:
        _instance = ReleaseQualityGateService()
    return _instance


def reset_release_quality_gate_service() -> None:
    """Reset the singleton (for testing)."""
    global _instance
    _instance = None
