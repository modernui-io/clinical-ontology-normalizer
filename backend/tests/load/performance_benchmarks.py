"""Performance benchmark definitions and regression detection.

Defines SLA targets per endpoint, stores / loads baseline results, and
compares current runs against the baseline to flag regressions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tests.load.load_test_runner import LoadTestResult, results_to_json


# ---------------------------------------------------------------------------
# SLA target catalogue (aligned with VPE-4 SLA doc)
# ---------------------------------------------------------------------------

@dataclass
class SLATarget:
    """Latency and availability SLA for one endpoint."""

    endpoint_pattern: str
    p95_latency_ms: float
    p99_latency_ms: float
    max_error_rate_pct: float = 1.0  # max acceptable error percentage
    description: str = ""


# Default SLA targets for the clinical trial platform
DEFAULT_SLA_TARGETS: list[SLATarget] = [
    SLATarget(
        endpoint_pattern="Health Check",
        p95_latency_ms=50.0,
        p99_latency_ms=100.0,
        max_error_rate_pct=0.1,
        description="Health endpoint must respond quickly",
    ),
    SLATarget(
        endpoint_pattern="List Patients",
        p95_latency_ms=500.0,
        p99_latency_ms=1000.0,
        max_error_rate_pct=1.0,
        description="Patient listing with pagination",
    ),
    SLATarget(
        endpoint_pattern="List Trials",
        p95_latency_ms=500.0,
        p99_latency_ms=1000.0,
        max_error_rate_pct=1.0,
        description="Trial listing with pagination",
    ),
    SLATarget(
        endpoint_pattern="Screen Patients",
        p95_latency_ms=3000.0,
        p99_latency_ms=5000.0,
        max_error_rate_pct=2.0,
        description="Compute-intensive patient screening",
    ),
    SLATarget(
        endpoint_pattern="Data Quality Mapping",
        p95_latency_ms=2000.0,
        p99_latency_ms=4000.0,
        max_error_rate_pct=1.0,
        description="Data quality analytics query",
    ),
]


def find_sla_target(
    endpoint_name: str,
    targets: list[SLATarget] | None = None,
) -> SLATarget | None:
    """Find the SLA target whose pattern matches *endpoint_name*."""
    for t in targets or DEFAULT_SLA_TARGETS:
        if t.endpoint_pattern in endpoint_name:
            return t
    return None


# ---------------------------------------------------------------------------
# SLA evaluation
# ---------------------------------------------------------------------------

@dataclass
class SLAEvaluation:
    """Result of evaluating one endpoint against its SLA target."""

    endpoint: str
    p95_passed: bool
    p99_passed: bool
    error_rate_passed: bool
    overall_passed: bool
    details: str = ""


def evaluate_sla(
    result: LoadTestResult,
    targets: list[SLATarget] | None = None,
) -> SLAEvaluation:
    """Check *result* against the matching SLA target.

    Returns an :class:`SLAEvaluation` with pass/fail for each criterion.
    If no SLA target matches, all checks pass by default.
    """
    target = find_sla_target(result.endpoint, targets)
    if target is None:
        return SLAEvaluation(
            endpoint=result.endpoint,
            p95_passed=True,
            p99_passed=True,
            error_rate_passed=True,
            overall_passed=True,
            details="No SLA target defined",
        )

    p95_ok = result.latency_p95_ms <= target.p95_latency_ms
    p99_ok = result.latency_p99_ms <= target.p99_latency_ms
    err_ok = result.error_rate <= target.max_error_rate_pct
    overall = p95_ok and p99_ok and err_ok

    parts: list[str] = []
    if not p95_ok:
        parts.append(f"p95 {result.latency_p95_ms}ms > {target.p95_latency_ms}ms")
    if not p99_ok:
        parts.append(f"p99 {result.latency_p99_ms}ms > {target.p99_latency_ms}ms")
    if not err_ok:
        parts.append(f"error_rate {result.error_rate}% > {target.max_error_rate_pct}%")

    return SLAEvaluation(
        endpoint=result.endpoint,
        p95_passed=p95_ok,
        p99_passed=p99_ok,
        error_rate_passed=err_ok,
        overall_passed=overall,
        details="; ".join(parts) if parts else "All SLA targets met",
    )


def evaluate_all_slas(
    results: list[LoadTestResult],
    targets: list[SLATarget] | None = None,
) -> list[SLAEvaluation]:
    """Evaluate SLAs for every result."""
    return [evaluate_sla(r, targets) for r in results]


# ---------------------------------------------------------------------------
# Regression detection
# ---------------------------------------------------------------------------

@dataclass
class RegressionCheck:
    """Comparison of current result to a stored baseline for one endpoint."""

    endpoint: str
    baseline_p95_ms: float
    current_p95_ms: float
    change_pct: float
    severity: str  # "ok", "warning", "failure"
    message: str = ""


WARNING_THRESHOLD_PCT = 20.0   # > 20% latency increase = warning
FAILURE_THRESHOLD_PCT = 50.0   # > 50% latency increase = failure


def detect_regression(
    current: LoadTestResult,
    baseline: dict[str, Any],
    warning_pct: float = WARNING_THRESHOLD_PCT,
    failure_pct: float = FAILURE_THRESHOLD_PCT,
) -> RegressionCheck:
    """Compare *current* result against a baseline dict.

    The *baseline* dict should have at minimum a ``latency_p95_ms`` key.
    """
    baseline_p95 = baseline.get("latency_p95_ms", 0.0)
    current_p95 = current.latency_p95_ms

    if baseline_p95 <= 0:
        return RegressionCheck(
            endpoint=current.endpoint,
            baseline_p95_ms=0.0,
            current_p95_ms=current_p95,
            change_pct=0.0,
            severity="ok",
            message="No baseline available",
        )

    change_pct = ((current_p95 - baseline_p95) / baseline_p95) * 100.0

    if change_pct > failure_pct:
        severity = "failure"
        msg = f"Regression: p95 increased {change_pct:.1f}% (>{failure_pct}% threshold)"
    elif change_pct > warning_pct:
        severity = "warning"
        msg = f"Warning: p95 increased {change_pct:.1f}% (>{warning_pct}% threshold)"
    else:
        severity = "ok"
        msg = f"OK: p95 changed {change_pct:+.1f}%"

    return RegressionCheck(
        endpoint=current.endpoint,
        baseline_p95_ms=round(baseline_p95, 2),
        current_p95_ms=round(current_p95, 2),
        change_pct=round(change_pct, 2),
        severity=severity,
        message=msg,
    )


def detect_all_regressions(
    current_results: list[LoadTestResult],
    baselines: dict[str, dict[str, Any]],
    warning_pct: float = WARNING_THRESHOLD_PCT,
    failure_pct: float = FAILURE_THRESHOLD_PCT,
) -> list[RegressionCheck]:
    """Run regression detection for all current results against baselines.

    *baselines* is keyed by endpoint name.
    """
    checks: list[RegressionCheck] = []
    for r in current_results:
        bl = baselines.get(r.endpoint, {})
        checks.append(detect_regression(r, bl, warning_pct, failure_pct))
    return checks


# ---------------------------------------------------------------------------
# Baseline persistence
# ---------------------------------------------------------------------------

DEFAULT_BASELINE_PATH = Path(__file__).parent / "baseline_results.json"


def save_baseline(
    results: list[LoadTestResult],
    path: Path | str = DEFAULT_BASELINE_PATH,
) -> None:
    """Persist results as the new baseline."""
    data = {r.endpoint: d for r, d in zip(results, results_to_json(results))}
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_baseline(
    path: Path | str = DEFAULT_BASELINE_PATH,
) -> dict[str, dict[str, Any]]:
    """Load previously saved baseline. Returns empty dict if file missing."""
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Report helpers
# ---------------------------------------------------------------------------

def regression_report_markdown(checks: list[RegressionCheck]) -> str:
    """Generate a Markdown table summarising regression checks."""
    lines: list[str] = [
        "# Regression Report",
        "",
        "| Endpoint | Baseline p95 | Current p95 | Change | Severity |",
        "|----------|-------------|-------------|--------|----------|",
    ]
    for c in checks:
        lines.append(
            f"| {c.endpoint} | {c.baseline_p95_ms}ms | {c.current_p95_ms}ms "
            f"| {c.change_pct:+.1f}% | {c.severity.upper()} |"
        )
    lines.append("")
    has_failure = any(c.severity == "failure" for c in checks)
    has_warning = any(c.severity == "warning" for c in checks)
    if has_failure:
        lines.append("**RESULT: REGRESSION DETECTED**")
    elif has_warning:
        lines.append("**RESULT: WARNINGS - review recommended**")
    else:
        lines.append("**RESULT: NO REGRESSIONS**")
    lines.append("")
    return "\n".join(lines)
