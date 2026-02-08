"""Performance Benchmarking & SLA Management Service (CTO-9).

Provides in-memory benchmark recording, SLA definition & compliance
monitoring, trend analysis with regression detection, benchmark suites,
and version comparison for a pharma-regulated clinical trial platform.
"""

from __future__ import annotations

import logging
import math
import random
import threading
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.schemas.performance_benchmarks import (
    BenchmarkCategory,
    BenchmarkResult,
    BenchmarkSuite,
    BenchmarkSuiteEntry,
    BenchmarkSuiteRunResult,
    Environment,
    OperationSummary,
    PerformanceMetrics,
    PerformanceTrend,
    RegressionAlert,
    RegressionReport,
    SLAComplianceSummary,
    SLADefinition,
    SLAStatus,
    SLATier,
    TrendDataPoint,
    TrendDirection,
    VersionComparison,
    VersionComparisonEntry,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REGRESSION_THRESHOLD_PCT = 20.0  # p99 increase > 20% = regression


# ---------------------------------------------------------------------------
# Seed-data helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hours_ago(h: int) -> datetime:
    return _now() - timedelta(hours=h)


def _days_ago(d: int) -> datetime:
    return _now() - timedelta(days=d)


def _make_id() -> str:
    return str(uuid4())


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class PerformanceBenchmarkService:
    """In-memory performance benchmark and SLA management service."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._benchmarks: list[BenchmarkResult] = []
        self._slas: list[SLADefinition] = []
        self._suites: list[BenchmarkSuite] = []
        self._populate_seed_data()

    # -----------------------------------------------------------------------
    # Seed data
    # -----------------------------------------------------------------------

    def _populate_seed_data(self) -> None:
        """Pre-populate SLAs, historical benchmarks, and suites."""
        self._seed_slas()
        self._seed_benchmarks()
        self._seed_suites()

    def _seed_slas(self) -> None:
        """Create 18 SLA definitions across all categories."""
        defs = [
            # API_LATENCY
            (BenchmarkCategory.API_LATENCY, "GET /patients", SLATier.GOLD, 30, 120, 400, 500),
            (BenchmarkCategory.API_LATENCY, "GET /patients/{id}", SLATier.PLATINUM, 10, 40, 80, 1000),
            (BenchmarkCategory.API_LATENCY, "POST /documents", SLATier.SILVER, 100, 500, 1500, 200),
            (BenchmarkCategory.API_LATENCY, "GET /health", SLATier.PLATINUM, 5, 15, 50, 2000),
            # DATABASE_QUERY
            (BenchmarkCategory.DATABASE_QUERY, "patient_search", SLATier.GOLD, 20, 80, 300, 800),
            (BenchmarkCategory.DATABASE_QUERY, "document_lookup", SLATier.GOLD, 15, 60, 250, 1000),
            # NLP_PIPELINE
            (BenchmarkCategory.NLP_PIPELINE, "entity_extraction", SLATier.SILVER, 200, 800, 1800, 100),
            (BenchmarkCategory.NLP_PIPELINE, "assertion_detection", SLATier.SILVER, 150, 600, 1500, 150),
            # FHIR_IMPORT
            (BenchmarkCategory.FHIR_IMPORT, "bundle_import", SLATier.BRONZE, 500, 2000, 8000, 50),
            (BenchmarkCategory.FHIR_IMPORT, "resource_validate", SLATier.SILVER, 50, 200, 1000, 300),
            # TRIAL_SCREENING
            (BenchmarkCategory.TRIAL_SCREENING, "screen_patient", SLATier.GOLD, 80, 300, 450, 400),
            (BenchmarkCategory.TRIAL_SCREENING, "batch_screen", SLATier.SILVER, 500, 1200, 1800, 80),
            (BenchmarkCategory.TRIAL_SCREENING, "eligibility_check", SLATier.GOLD, 40, 150, 400, 600),
            # KG_QUERY
            (BenchmarkCategory.KG_QUERY, "traversal_2hop", SLATier.GOLD, 25, 100, 350, 700),
            (BenchmarkCategory.KG_QUERY, "subgraph_extract", SLATier.SILVER, 100, 400, 1200, 200),
            # DOCUMENT_PROCESSING
            (BenchmarkCategory.DOCUMENT_PROCESSING, "ocr_extract", SLATier.BRONZE, 1000, 3000, 8000, 30),
            (BenchmarkCategory.DOCUMENT_PROCESSING, "pdf_parse", SLATier.SILVER, 200, 800, 1800, 100),
            # BULK_EXPORT
            (BenchmarkCategory.BULK_EXPORT, "fhir_bulk_export", SLATier.BRONZE, 2000, 5000, 9000, 10),
        ]
        for cat, op, tier, p50, p95, p99, tput in defs:
            self._slas.append(
                SLADefinition(
                    id=_make_id(),
                    category=cat,
                    operation_name=op,
                    tier=tier,
                    target_p50_ms=p50,
                    target_p95_ms=p95,
                    target_p99_ms=p99,
                    target_throughput_rps=tput,
                    measurement_window_hours=24,
                    breach_threshold_pct=5.0,
                )
            )

    def _seed_benchmarks(self) -> None:
        """Create 36 historical benchmark results (4-5 per category)."""
        random.seed(42)  # deterministic seed data
        entries: list[tuple[BenchmarkCategory, str, float, float, float, float, str]] = [
            # API_LATENCY
            (BenchmarkCategory.API_LATENCY, "GET /patients", 25, 100, 350, 550, "1.0.0"),
            (BenchmarkCategory.API_LATENCY, "GET /patients", 28, 110, 380, 520, "1.1.0"),
            (BenchmarkCategory.API_LATENCY, "GET /patients/{id}", 8, 35, 70, 1100, "1.0.0"),
            (BenchmarkCategory.API_LATENCY, "GET /patients/{id}", 9, 38, 75, 1050, "1.1.0"),
            (BenchmarkCategory.API_LATENCY, "POST /documents", 90, 450, 1300, 220, "1.0.0"),
            (BenchmarkCategory.API_LATENCY, "GET /health", 3, 10, 40, 2500, "1.0.0"),
            # DATABASE_QUERY
            (BenchmarkCategory.DATABASE_QUERY, "patient_search", 18, 70, 260, 850, "1.0.0"),
            (BenchmarkCategory.DATABASE_QUERY, "patient_search", 19, 75, 280, 830, "1.1.0"),
            (BenchmarkCategory.DATABASE_QUERY, "document_lookup", 12, 50, 200, 1100, "1.0.0"),
            (BenchmarkCategory.DATABASE_QUERY, "document_lookup", 13, 55, 220, 1050, "1.1.0"),
            # NLP_PIPELINE
            (BenchmarkCategory.NLP_PIPELINE, "entity_extraction", 180, 700, 1600, 110, "1.0.0"),
            (BenchmarkCategory.NLP_PIPELINE, "entity_extraction", 190, 750, 1700, 105, "1.1.0"),
            (BenchmarkCategory.NLP_PIPELINE, "assertion_detection", 130, 500, 1300, 160, "1.0.0"),
            (BenchmarkCategory.NLP_PIPELINE, "assertion_detection", 140, 550, 1350, 155, "1.1.0"),
            # FHIR_IMPORT
            (BenchmarkCategory.FHIR_IMPORT, "bundle_import", 450, 1800, 7000, 55, "1.0.0"),
            (BenchmarkCategory.FHIR_IMPORT, "bundle_import", 480, 1900, 7500, 52, "1.1.0"),
            (BenchmarkCategory.FHIR_IMPORT, "resource_validate", 40, 170, 800, 350, "1.0.0"),
            (BenchmarkCategory.FHIR_IMPORT, "resource_validate", 45, 180, 850, 340, "1.1.0"),
            # TRIAL_SCREENING
            (BenchmarkCategory.TRIAL_SCREENING, "screen_patient", 70, 260, 400, 430, "1.0.0"),
            (BenchmarkCategory.TRIAL_SCREENING, "screen_patient", 75, 280, 420, 420, "1.1.0"),
            (BenchmarkCategory.TRIAL_SCREENING, "batch_screen", 450, 1100, 1650, 85, "1.0.0"),
            (BenchmarkCategory.TRIAL_SCREENING, "batch_screen", 470, 1150, 1700, 82, "1.1.0"),
            (BenchmarkCategory.TRIAL_SCREENING, "eligibility_check", 35, 130, 350, 650, "1.0.0"),
            (BenchmarkCategory.TRIAL_SCREENING, "eligibility_check", 38, 140, 370, 630, "1.1.0"),
            # KG_QUERY
            (BenchmarkCategory.KG_QUERY, "traversal_2hop", 22, 90, 300, 750, "1.0.0"),
            (BenchmarkCategory.KG_QUERY, "traversal_2hop", 23, 95, 320, 730, "1.1.0"),
            (BenchmarkCategory.KG_QUERY, "subgraph_extract", 90, 350, 1050, 220, "1.0.0"),
            (BenchmarkCategory.KG_QUERY, "subgraph_extract", 95, 370, 1100, 210, "1.1.0"),
            # DOCUMENT_PROCESSING
            (BenchmarkCategory.DOCUMENT_PROCESSING, "ocr_extract", 900, 2700, 7200, 32, "1.0.0"),
            (BenchmarkCategory.DOCUMENT_PROCESSING, "ocr_extract", 950, 2800, 7500, 30, "1.1.0"),
            (BenchmarkCategory.DOCUMENT_PROCESSING, "pdf_parse", 180, 700, 1600, 110, "1.0.0"),
            (BenchmarkCategory.DOCUMENT_PROCESSING, "pdf_parse", 190, 750, 1650, 108, "1.1.0"),
            # BULK_EXPORT
            (BenchmarkCategory.BULK_EXPORT, "fhir_bulk_export", 1800, 4500, 8200, 12, "1.0.0"),
            (BenchmarkCategory.BULK_EXPORT, "fhir_bulk_export", 1900, 4700, 8500, 11, "1.1.0"),
            # Extra entries for variety
            (BenchmarkCategory.API_LATENCY, "POST /documents", 95, 470, 1350, 215, "1.1.0"),
            (BenchmarkCategory.API_LATENCY, "GET /health", 4, 12, 45, 2400, "1.1.0"),
        ]

        for i, (cat, op, p50, p95, p99, tput, ver) in enumerate(entries):
            jitter = random.uniform(0.95, 1.05)
            min_ms = p50 * 0.3 * jitter
            max_ms = p99 * 1.4 * jitter
            mean_ms = (p50 + p95) / 2 * jitter
            std_dev = (p95 - p50) * 0.4 * jitter
            self._benchmarks.append(
                BenchmarkResult(
                    id=_make_id(),
                    category=cat,
                    operation_name=op,
                    p50_ms=round(p50 * jitter, 2),
                    p95_ms=round(p95 * jitter, 2),
                    p99_ms=round(p99 * jitter, 2),
                    max_ms=round(max_ms, 2),
                    min_ms=round(min_ms, 2),
                    mean_ms=round(mean_ms, 2),
                    std_dev_ms=round(std_dev, 2),
                    throughput_rps=round(tput * jitter, 2),
                    sample_count=random.randint(500, 5000),
                    measured_at=_hours_ago(len(entries) - i),
                    environment=Environment.PRODUCTION,
                    version=ver,
                )
            )

    def _seed_suites(self) -> None:
        """Create two benchmark suites."""
        self._suites.append(
            BenchmarkSuite(
                id=_make_id(),
                name="Core API Suite",
                description="Benchmarks for core patient-facing API endpoints",
                benchmarks=[
                    BenchmarkSuiteEntry(category=BenchmarkCategory.API_LATENCY, operation_name="GET /patients"),
                    BenchmarkSuiteEntry(category=BenchmarkCategory.API_LATENCY, operation_name="GET /patients/{id}"),
                    BenchmarkSuiteEntry(category=BenchmarkCategory.API_LATENCY, operation_name="POST /documents"),
                    BenchmarkSuiteEntry(category=BenchmarkCategory.API_LATENCY, operation_name="GET /health"),
                    BenchmarkSuiteEntry(category=BenchmarkCategory.DATABASE_QUERY, operation_name="patient_search"),
                    BenchmarkSuiteEntry(category=BenchmarkCategory.DATABASE_QUERY, operation_name="document_lookup"),
                    BenchmarkSuiteEntry(category=BenchmarkCategory.KG_QUERY, operation_name="traversal_2hop"),
                ],
                last_run=_hours_ago(2),
                schedule_cron="0 */6 * * *",
            )
        )
        self._suites.append(
            BenchmarkSuite(
                id=_make_id(),
                name="Clinical Pipeline Suite",
                description="Benchmarks for NLP, FHIR, screening, and export pipelines",
                benchmarks=[
                    BenchmarkSuiteEntry(category=BenchmarkCategory.NLP_PIPELINE, operation_name="entity_extraction"),
                    BenchmarkSuiteEntry(category=BenchmarkCategory.NLP_PIPELINE, operation_name="assertion_detection"),
                    BenchmarkSuiteEntry(category=BenchmarkCategory.FHIR_IMPORT, operation_name="bundle_import"),
                    BenchmarkSuiteEntry(category=BenchmarkCategory.FHIR_IMPORT, operation_name="resource_validate"),
                    BenchmarkSuiteEntry(category=BenchmarkCategory.TRIAL_SCREENING, operation_name="screen_patient"),
                    BenchmarkSuiteEntry(category=BenchmarkCategory.TRIAL_SCREENING, operation_name="batch_screen"),
                    BenchmarkSuiteEntry(category=BenchmarkCategory.TRIAL_SCREENING, operation_name="eligibility_check"),
                    BenchmarkSuiteEntry(category=BenchmarkCategory.DOCUMENT_PROCESSING, operation_name="pdf_parse"),
                    BenchmarkSuiteEntry(category=BenchmarkCategory.BULK_EXPORT, operation_name="fhir_bulk_export"),
                ],
                last_run=_hours_ago(6),
                schedule_cron="0 0 * * *",
            )
        )

    # -----------------------------------------------------------------------
    # Benchmark CRUD
    # -----------------------------------------------------------------------

    def record_benchmark(
        self,
        category: BenchmarkCategory,
        operation_name: str,
        results_dict: dict[str, Any],
    ) -> BenchmarkResult:
        """Record a new benchmark measurement."""
        result = BenchmarkResult(
            id=_make_id(),
            category=category,
            operation_name=operation_name,
            p50_ms=results_dict.get("p50_ms", 0),
            p95_ms=results_dict.get("p95_ms", 0),
            p99_ms=results_dict.get("p99_ms", 0),
            max_ms=results_dict.get("max_ms", 0),
            min_ms=results_dict.get("min_ms", 0),
            mean_ms=results_dict.get("mean_ms", 0),
            std_dev_ms=results_dict.get("std_dev_ms", 0),
            throughput_rps=results_dict.get("throughput_rps", 0),
            sample_count=results_dict.get("sample_count", 1),
            measured_at=_now(),
            environment=Environment(results_dict.get("environment", "dev")),
            version=results_dict.get("version", "1.0.0"),
        )
        with self._lock:
            self._benchmarks.append(result)
        logger.info("Recorded benchmark %s/%s id=%s", category.value, operation_name, result.id)
        return result

    def get_benchmarks(
        self,
        category: BenchmarkCategory | None = None,
        operation_name: str | None = None,
        limit: int = 50,
    ) -> list[BenchmarkResult]:
        """Query benchmark results with optional filters."""
        with self._lock:
            results = list(self._benchmarks)
        if category is not None:
            results = [r for r in results if r.category == category]
        if operation_name is not None:
            results = [r for r in results if r.operation_name == operation_name]
        # Most recent first
        results.sort(key=lambda r: r.measured_at, reverse=True)
        return results[:limit]

    def get_benchmark(self, benchmark_id: str) -> BenchmarkResult | None:
        """Get a single benchmark result by ID."""
        with self._lock:
            for b in self._benchmarks:
                if b.id == benchmark_id:
                    return b
        return None

    # -----------------------------------------------------------------------
    # SLA CRUD
    # -----------------------------------------------------------------------

    def create_sla(
        self,
        category: BenchmarkCategory,
        operation_name: str,
        tier: SLATier,
        target_p50_ms: float,
        target_p95_ms: float,
        target_p99_ms: float,
        target_throughput_rps: float = 0.0,
        measurement_window_hours: int = 24,
        breach_threshold_pct: float = 5.0,
    ) -> SLADefinition:
        """Create a new SLA definition."""
        sla = SLADefinition(
            id=_make_id(),
            category=category,
            operation_name=operation_name,
            tier=tier,
            target_p50_ms=target_p50_ms,
            target_p95_ms=target_p95_ms,
            target_p99_ms=target_p99_ms,
            target_throughput_rps=target_throughput_rps,
            measurement_window_hours=measurement_window_hours,
            breach_threshold_pct=breach_threshold_pct,
        )
        with self._lock:
            self._slas.append(sla)
        logger.info("Created SLA %s for %s/%s", sla.id, category.value, operation_name)
        return sla

    def update_sla(self, sla_id: str, updates: dict[str, Any]) -> SLADefinition | None:
        """Update an existing SLA definition."""
        with self._lock:
            for i, sla in enumerate(self._slas):
                if sla.id == sla_id:
                    data = sla.model_dump()
                    for k, v in updates.items():
                        if v is not None and k in data:
                            data[k] = v
                    updated = SLADefinition(**data)
                    self._slas[i] = updated
                    return updated
        return None

    def get_sla(self, sla_id: str) -> SLADefinition | None:
        """Get a single SLA definition by ID."""
        with self._lock:
            for s in self._slas:
                if s.id == sla_id:
                    return s
        return None

    def list_slas(self, category: BenchmarkCategory | None = None) -> list[SLADefinition]:
        """List SLA definitions, optionally filtered by category."""
        with self._lock:
            slas = list(self._slas)
        if category is not None:
            slas = [s for s in slas if s.category == category]
        return slas

    def delete_sla(self, sla_id: str) -> bool:
        """Delete an SLA definition. Returns True if deleted."""
        with self._lock:
            for i, s in enumerate(self._slas):
                if s.id == sla_id:
                    self._slas.pop(i)
                    return True
        return False

    # -----------------------------------------------------------------------
    # SLA compliance
    # -----------------------------------------------------------------------

    def check_sla_compliance(self, sla_id: str) -> SLAStatus | None:
        """Check current compliance for a single SLA."""
        sla = self.get_sla(sla_id)
        if sla is None:
            return None

        # Get latest benchmark for this operation/category
        benchmarks = self.get_benchmarks(
            category=sla.category, operation_name=sla.operation_name, limit=30
        )
        if not benchmarks:
            # No data: assume compliant with zeros
            return SLAStatus(
                sla_id=sla.id,
                operation_name=sla.operation_name,
                category=sla.category,
                tier=sla.tier,
                current_p50=0,
                current_p95=0,
                current_p99=0,
                current_throughput=0,
                p50_met=True,
                p95_met=True,
                p99_met=True,
                throughput_met=True,
                overall_compliance=True,
                compliance_pct_30d=100.0,
                last_breach=None,
                breach_count_30d=0,
            )

        latest = benchmarks[0]
        p50_met = latest.p50_ms <= sla.target_p50_ms
        p95_met = latest.p95_ms <= sla.target_p95_ms
        p99_met = latest.p99_ms <= sla.target_p99_ms
        throughput_met = (
            latest.throughput_rps >= sla.target_throughput_rps
            if sla.target_throughput_rps > 0
            else True
        )
        overall = p50_met and p95_met and p99_met and throughput_met

        # Calculate 30-day compliance
        thirty_days_ago = _now() - timedelta(days=30)
        recent = [b for b in benchmarks if b.measured_at >= thirty_days_ago]
        breach_count = 0
        last_breach: datetime | None = None
        for b in recent:
            b_ok = (
                b.p50_ms <= sla.target_p50_ms
                and b.p95_ms <= sla.target_p95_ms
                and b.p99_ms <= sla.target_p99_ms
            )
            if not b_ok:
                breach_count += 1
                if last_breach is None or b.measured_at > last_breach:
                    last_breach = b.measured_at

        compliance_pct = (
            ((len(recent) - breach_count) / len(recent) * 100) if recent else 100.0
        )

        return SLAStatus(
            sla_id=sla.id,
            operation_name=sla.operation_name,
            category=sla.category,
            tier=sla.tier,
            current_p50=latest.p50_ms,
            current_p95=latest.p95_ms,
            current_p99=latest.p99_ms,
            current_throughput=latest.throughput_rps,
            p50_met=p50_met,
            p95_met=p95_met,
            p99_met=p99_met,
            throughput_met=throughput_met,
            overall_compliance=overall,
            compliance_pct_30d=round(compliance_pct, 2),
            last_breach=last_breach,
            breach_count_30d=breach_count,
        )

    def check_all_sla_compliance(self) -> SLAComplianceSummary:
        """Batch check compliance for all SLAs."""
        statuses: list[SLAStatus] = []
        with self._lock:
            sla_ids = [s.id for s in self._slas]

        for sla_id in sla_ids:
            status = self.check_sla_compliance(sla_id)
            if status is not None:
                statuses.append(status)

        compliant = sum(1 for s in statuses if s.overall_compliance)
        total = len(statuses)
        rate = (compliant / total * 100) if total > 0 else 100.0

        return SLAComplianceSummary(
            total_slas=total,
            compliant=compliant,
            non_compliant=total - compliant,
            compliance_rate=round(rate, 2),
            statuses=statuses,
        )

    # -----------------------------------------------------------------------
    # Trend analysis
    # -----------------------------------------------------------------------

    def get_performance_trends(
        self,
        category: BenchmarkCategory,
        operation_name: str,
        days: int = 30,
    ) -> PerformanceTrend:
        """Compute performance trend for an operation over the given window."""
        cutoff = _now() - timedelta(days=days)
        benchmarks = self.get_benchmarks(category=category, operation_name=operation_name, limit=500)
        points_in_window = [
            b for b in benchmarks if b.measured_at >= cutoff
        ]
        # Chronological order
        points_in_window.sort(key=lambda b: b.measured_at)

        data_points = [
            TrendDataPoint(
                timestamp=b.measured_at,
                p50=b.p50_ms,
                p95=b.p95_ms,
                p99=b.p99_ms,
                throughput=b.throughput_rps,
            )
            for b in points_in_window
        ]

        direction = TrendDirection.STABLE
        regression = False

        if len(points_in_window) >= 2:
            first_p99 = points_in_window[0].p99_ms
            last_p99 = points_in_window[-1].p99_ms
            if first_p99 > 0:
                change_pct = ((last_p99 - first_p99) / first_p99) * 100
                if change_pct > _REGRESSION_THRESHOLD_PCT:
                    direction = TrendDirection.DEGRADING
                    regression = True
                elif change_pct < -10:
                    direction = TrendDirection.IMPROVING

        return PerformanceTrend(
            category=category,
            operation_name=operation_name,
            data_points=data_points,
            trend_direction=direction,
            regression_detected=regression,
        )

    def detect_regressions(self) -> RegressionReport:
        """Scan all operations for performance regressions."""
        # Identify all unique (category, operation) pairs
        with self._lock:
            pairs = {(b.category, b.operation_name) for b in self._benchmarks}

        alerts: list[RegressionAlert] = []
        for cat, op in pairs:
            trend = self.get_performance_trends(cat, op, days=30)
            if trend.regression_detected and len(trend.data_points) >= 2:
                first = trend.data_points[0]
                last = trend.data_points[-1]
                change_pct = (
                    ((last.p99 - first.p99) / first.p99 * 100) if first.p99 > 0 else 0
                )
                alerts.append(
                    RegressionAlert(
                        category=cat,
                        operation_name=op,
                        previous_p99=first.p99,
                        current_p99=last.p99,
                        change_pct=round(change_pct, 2),
                        detected_at=_now(),
                    )
                )

        return RegressionReport(
            total_operations_scanned=len(pairs),
            regressions_found=len(alerts),
            alerts=alerts,
        )

    # -----------------------------------------------------------------------
    # Aggregate metrics
    # -----------------------------------------------------------------------

    def get_metrics(self) -> PerformanceMetrics:
        """Compute program-wide performance metrics."""
        with self._lock:
            benchmarks = list(self._benchmarks)
            slas = list(self._slas)

        # Categories covered
        categories = {b.category for b in benchmarks}

        # Latest p99 per operation
        latest_by_op: dict[tuple[BenchmarkCategory, str], BenchmarkResult] = {}
        for b in sorted(benchmarks, key=lambda x: x.measured_at):
            latest_by_op[(b.category, b.operation_name)] = b

        all_p99 = [b.p99_ms for b in latest_by_op.values()]
        mean_p99 = sum(all_p99) / len(all_p99) if all_p99 else 0

        # Compliance rate
        compliance = self.check_all_sla_compliance()

        # Detect regressions for degraded list
        regressions = self.detect_regressions()
        degraded = [
            OperationSummary(
                operation_name=a.operation_name,
                category=a.category,
                latest_p99=a.current_p99,
            )
            for a in regressions.alerts
        ]

        # Top/worst performers
        sorted_ops = sorted(latest_by_op.values(), key=lambda b: b.p99_ms)
        top = [
            OperationSummary(
                operation_name=b.operation_name,
                category=b.category,
                latest_p99=b.p99_ms,
            )
            for b in sorted_ops[:5]
        ]
        worst = [
            OperationSummary(
                operation_name=b.operation_name,
                category=b.category,
                latest_p99=b.p99_ms,
            )
            for b in sorted_ops[-5:]
        ]

        return PerformanceMetrics(
            total_slas=len(slas),
            sla_compliance_rate=compliance.compliance_rate,
            total_benchmarks=len(benchmarks),
            categories_covered=len(categories),
            mean_p99_across_all=round(mean_p99, 2),
            degraded_operations=degraded,
            top_performers=top,
            worst_performers=worst,
        )

    # -----------------------------------------------------------------------
    # Benchmark suites
    # -----------------------------------------------------------------------

    def create_suite(
        self,
        name: str,
        description: str = "",
        benchmarks: list[dict[str, str]] | None = None,
        schedule_cron: str | None = None,
    ) -> BenchmarkSuite:
        """Create a new benchmark suite."""
        entries = [
            BenchmarkSuiteEntry(
                category=BenchmarkCategory(b["category"]),
                operation_name=b["operation_name"],
            )
            for b in (benchmarks or [])
        ]
        suite = BenchmarkSuite(
            id=_make_id(),
            name=name,
            description=description,
            benchmarks=entries,
            schedule_cron=schedule_cron,
        )
        with self._lock:
            self._suites.append(suite)
        return suite

    def get_suite(self, suite_id: str) -> BenchmarkSuite | None:
        """Get a benchmark suite by ID."""
        with self._lock:
            for s in self._suites:
                if s.id == suite_id:
                    return s
        return None

    def list_suites(self) -> list[BenchmarkSuite]:
        """List all benchmark suites."""
        with self._lock:
            return list(self._suites)

    def run_suite(self, suite_id: str) -> BenchmarkSuiteRunResult | None:
        """Run a benchmark suite, generating synthetic results for each entry."""
        suite = self.get_suite(suite_id)
        if suite is None:
            return None

        started = _now()
        results: list[BenchmarkResult] = []

        for entry in suite.benchmarks:
            # Generate synthetic but realistic results based on existing data
            existing = self.get_benchmarks(
                category=entry.category,
                operation_name=entry.operation_name,
                limit=1,
            )
            if existing:
                base = existing[0]
                jitter = random.uniform(0.9, 1.1)
                p50 = base.p50_ms * jitter
                p95 = base.p95_ms * jitter
                p99 = base.p99_ms * jitter
                tput = base.throughput_rps * jitter
            else:
                p50, p95, p99, tput = 50, 200, 500, 100

            result = self.record_benchmark(
                category=entry.category,
                operation_name=entry.operation_name,
                results_dict={
                    "p50_ms": round(p50, 2),
                    "p95_ms": round(p95, 2),
                    "p99_ms": round(p99, 2),
                    "max_ms": round(p99 * 1.3, 2),
                    "min_ms": round(p50 * 0.3, 2),
                    "mean_ms": round((p50 + p95) / 2, 2),
                    "std_dev_ms": round((p95 - p50) * 0.4, 2),
                    "throughput_rps": round(tput, 2),
                    "sample_count": random.randint(500, 3000),
                    "environment": "production",
                    "version": "1.1.0",
                },
            )
            results.append(result)

        completed = _now()

        # Update suite last_run
        with self._lock:
            for i, s in enumerate(self._suites):
                if s.id == suite_id:
                    data = s.model_dump()
                    data["last_run"] = completed
                    self._suites[i] = BenchmarkSuite(**data)
                    break

        return BenchmarkSuiteRunResult(
            suite_id=suite_id,
            suite_name=suite.name,
            started_at=started,
            completed_at=completed,
            results=results,
        )

    # -----------------------------------------------------------------------
    # Version comparison
    # -----------------------------------------------------------------------

    def compare_versions(self, version_a: str, version_b: str) -> VersionComparison:
        """Compare performance metrics between two application versions."""
        with self._lock:
            benchmarks = list(self._benchmarks)

        # Latest per (category, operation) for each version
        latest_a: dict[tuple[BenchmarkCategory, str], BenchmarkResult] = {}
        latest_b: dict[tuple[BenchmarkCategory, str], BenchmarkResult] = {}

        for b in sorted(benchmarks, key=lambda x: x.measured_at):
            key = (b.category, b.operation_name)
            if b.version == version_a:
                latest_a[key] = b
            elif b.version == version_b:
                latest_b[key] = b

        all_keys = set(latest_a.keys()) | set(latest_b.keys())
        entries: list[VersionComparisonEntry] = []
        improved = degraded = unchanged = 0

        for key in sorted(all_keys, key=lambda k: (k[0].value, k[1])):
            a = latest_a.get(key)
            b = latest_b.get(key)
            a_p99 = a.p99_ms if a else 0
            b_p99 = b.p99_ms if b else 0
            a_p50 = a.p50_ms if a else 0
            b_p50 = b.p50_ms if b else 0
            delta = b_p99 - a_p99
            delta_pct = (delta / a_p99 * 100) if a_p99 > 0 else 0

            is_improved = delta < -1  # at least 1ms improvement
            is_degraded = delta > 1
            if is_improved:
                improved += 1
            elif is_degraded:
                degraded += 1
            else:
                unchanged += 1

            entries.append(
                VersionComparisonEntry(
                    operation_name=key[1],
                    category=key[0],
                    version_a_p99=a_p99,
                    version_b_p99=b_p99,
                    version_a_p50=a_p50,
                    version_b_p50=b_p50,
                    delta_p99_ms=round(delta, 2),
                    delta_p99_pct=round(delta_pct, 2),
                    improved=is_improved,
                )
            )

        return VersionComparison(
            version_a=version_a,
            version_b=version_b,
            total_operations=len(entries),
            improved=improved,
            degraded=degraded,
            unchanged=unchanged,
            entries=entries,
        )


# ---------------------------------------------------------------------------
# Singleton management
# ---------------------------------------------------------------------------

_service_instance: PerformanceBenchmarkService | None = None
_service_lock = threading.Lock()


def get_performance_benchmark_service() -> PerformanceBenchmarkService:
    """Return the singleton PerformanceBenchmarkService instance."""
    global _service_instance
    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = PerformanceBenchmarkService()
                logger.info("PerformanceBenchmarkService initialized")
    return _service_instance


def reset_performance_benchmark_service() -> None:
    """Reset the singleton (for testing)."""
    global _service_instance
    with _service_lock:
        _service_instance = None
