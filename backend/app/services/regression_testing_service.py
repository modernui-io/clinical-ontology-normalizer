"""Regression Test Orchestration Service.

QA-4: Singleton service managing test cases, suites, runs, coverage,
flaky test detection, trend analysis, impact analysis, and test health
dashboards.  All data is seeded in-memory at first access.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta
from typing import Any

from app.schemas.regression_testing import (
    CoverageListResponse,
    EstimatedRunTime,
    FlakyRootCause,
    FlakyTestListResponse,
    FlakyTestReport,
    ImpactAnalysisRequest,
    ImpactAnalysisResponse,
    PrioritizedTestList,
    RegressionTrend,
    TestCase,
    TestCaseCreate,
    TestCaseListResponse,
    TestCaseResult,
    TestCaseUpdate,
    TestCoverage,
    TestHealthDashboard,
    TestMetrics,
    TestPriority,
    TestRun,
    TestRunListResponse,
    TestRunStatus,
    TestStatus,
    TestSuite,
    TestSuiteCreate,
    TestSuiteListResponse,
    TestSuiteType,
    TestSuiteUpdate,
    TrendResponse,
    TriggerTestRunRequest,
    TriggerType,
)

# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_service: RegressionTestingService | None = None


def get_regression_testing_service() -> RegressionTestingService:
    """Return the singleton (creating + seeding on first call)."""
    global _service
    if _service is None:
        _service = RegressionTestingService()
    return _service


def reset_regression_testing_service() -> None:
    """Tear down singleton (used by tests)."""
    global _service
    _service = None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class RegressionTestingService:
    """Manages regression test orchestration."""

    def __init__(self) -> None:
        self._test_cases: dict[str, TestCase] = {}
        self._test_suites: dict[str, TestSuite] = {}
        self._test_runs: dict[str, TestRun] = {}
        self._coverage: dict[str, TestCoverage] = {}
        self._flaky_reports: dict[str, FlakyTestReport] = {}
        self._trends: list[RegressionTrend] = []
        self._seed()

    # ------------------------------------------------------------------
    # Seed data
    # ------------------------------------------------------------------

    def _seed(self) -> None:
        now = datetime.utcnow()

        # --- 30 test cases across all suite types ---
        modules = [
            "patient_screening", "trial_matching", "consent_management",
            "data_ingestion", "fhir_import", "billing_engine",
            "auth_service", "knowledge_graph", "nlp_pipeline",
            "drug_safety",
        ]
        suite_types = list(TestSuiteType)
        priorities = list(TestPriority)

        tc_defs: list[dict[str, Any]] = []
        for i in range(30):
            mod = modules[i % len(modules)]
            st = suite_types[i % len(suite_types)]
            pri = priorities[i % len(priorities)]
            tc_defs.append({
                "id": f"tc-{i+1:03d}",
                "name": f"Test {mod.replace('_', ' ').title()} - Case {i+1}",
                "description": f"Validates {mod} functionality scenario {i+1}",
                "suite_type": st,
                "priority": pri,
                "module": mod,
                "tags": [mod, st.value.lower(), pri.value.lower()],
                "expected_duration_ms": 500 + (i * 200),
                "flaky_rate": round(0.02 * (i % 5), 2),
                "last_run_status": TestStatus.PASSED if i % 7 != 0 else TestStatus.FAILED,
                "last_run_at": now - timedelta(hours=i),
                "created_at": now - timedelta(days=60),
                "updated_at": now - timedelta(hours=i),
                "owner": f"team-{mod.split('_')[0]}",
                "automated": i % 10 != 9,
                "preconditions": [f"Database seeded for {mod}"],
                "steps": [
                    f"Setup {mod} context",
                    f"Execute scenario {i+1}",
                    "Assert expected outcome",
                ],
            })

        for d in tc_defs:
            tc = TestCase(**d)
            self._test_cases[tc.id] = tc

        # --- 6 test suites ---
        suite_defs: list[dict[str, Any]] = [
            {
                "id": "suite-smoke",
                "name": "Smoke Tests",
                "suite_type": TestSuiteType.SMOKE,
                "description": "Quick sanity checks for critical paths",
                "test_case_ids": [f"tc-{i+1:03d}" for i in range(5)],
                "trigger_types": [TriggerType.ON_COMMIT, TriggerType.ON_DEPLOY],
                "schedule_cron": "*/30 * * * *",
                "estimated_duration_minutes": 5,
                "parallelizable": True,
                "max_parallel": 5,
                "environment_requirements": ["DATABASE_URL"],
                "enabled": True,
            },
            {
                "id": "suite-regression",
                "name": "Full Regression Suite",
                "suite_type": TestSuiteType.REGRESSION,
                "description": "Comprehensive regression coverage",
                "test_case_ids": [f"tc-{i+1:03d}" for i in range(30)],
                "trigger_types": [TriggerType.ON_MERGE, TriggerType.SCHEDULED],
                "schedule_cron": "0 2 * * *",
                "estimated_duration_minutes": 45,
                "parallelizable": True,
                "max_parallel": 8,
                "environment_requirements": ["DATABASE_URL", "REDIS_URL"],
                "enabled": True,
            },
            {
                "id": "suite-integration",
                "name": "Integration Tests",
                "suite_type": TestSuiteType.INTEGRATION,
                "description": "Cross-service integration validation",
                "test_case_ids": [f"tc-{i+1:03d}" for i in range(5, 15)],
                "trigger_types": [TriggerType.ON_PR, TriggerType.MANUAL],
                "schedule_cron": None,
                "estimated_duration_minutes": 20,
                "parallelizable": True,
                "max_parallel": 4,
                "environment_requirements": ["DATABASE_URL", "REDIS_URL", "NEO4J_URL"],
                "enabled": True,
            },
            {
                "id": "suite-e2e",
                "name": "End-to-End Tests",
                "suite_type": TestSuiteType.E2E,
                "description": "Full user-journey validation",
                "test_case_ids": [f"tc-{i+1:03d}" for i in range(15, 25)],
                "trigger_types": [TriggerType.ON_MERGE, TriggerType.SCHEDULED],
                "schedule_cron": "0 4 * * *",
                "estimated_duration_minutes": 60,
                "parallelizable": False,
                "max_parallel": 1,
                "environment_requirements": ["DATABASE_URL", "REDIS_URL", "NEO4J_URL", "BROWSER"],
                "enabled": True,
            },
            {
                "id": "suite-performance",
                "name": "Performance Tests",
                "suite_type": TestSuiteType.PERFORMANCE,
                "description": "Load and stress testing",
                "test_case_ids": [f"tc-{i+1:03d}" for i in range(25, 30)],
                "trigger_types": [TriggerType.SCHEDULED, TriggerType.MANUAL],
                "schedule_cron": "0 3 * * 1",
                "estimated_duration_minutes": 30,
                "parallelizable": False,
                "max_parallel": 1,
                "environment_requirements": ["DATABASE_URL", "LOAD_GEN"],
                "enabled": True,
            },
            {
                "id": "suite-compliance",
                "name": "Compliance Tests",
                "suite_type": TestSuiteType.COMPLIANCE,
                "description": "HIPAA, SOC2, and regulatory compliance checks",
                "test_case_ids": [f"tc-{i+1:03d}" for i in [0, 6, 13, 20, 27]],
                "trigger_types": [TriggerType.ON_DEPLOY, TriggerType.SCHEDULED],
                "schedule_cron": "0 6 * * *",
                "estimated_duration_minutes": 15,
                "parallelizable": True,
                "max_parallel": 3,
                "environment_requirements": ["DATABASE_URL"],
                "enabled": True,
            },
        ]

        for d in suite_defs:
            d["created_at"] = now - timedelta(days=90)
            d["updated_at"] = now - timedelta(days=1)
            suite = TestSuite(**d)
            self._test_suites[suite.id] = suite

        # --- 10 test runs (8 completed, 1 running, 1 queued) ---
        statuses_for_runs = (
            [TestRunStatus.COMPLETED] * 8
            + [TestRunStatus.RUNNING, TestRunStatus.QUEUED]
        )
        suite_ids_cycle = [
            "suite-smoke", "suite-regression", "suite-integration",
            "suite-e2e", "suite-performance", "suite-smoke",
            "suite-regression", "suite-compliance",
            "suite-smoke", "suite-regression",
        ]

        for idx in range(10):
            run_id = f"run-{idx+1:03d}"
            s_id = suite_ids_cycle[idx]
            suite_obj = self._test_suites[s_id]
            run_status = statuses_for_runs[idx]
            started = now - timedelta(hours=10 - idx) if run_status != TestRunStatus.QUEUED else None
            completed = (
                started + timedelta(minutes=suite_obj.estimated_duration_minutes)
                if started and run_status == TestRunStatus.COMPLETED
                else None
            )
            dur = (
                suite_obj.estimated_duration_minutes * 60.0
                if run_status == TestRunStatus.COMPLETED
                else None
            )

            # Build per-test results for completed / running
            results: list[TestCaseResult] = []
            total = len(suite_obj.test_case_ids)
            passed = 0
            failed = 0
            skipped = 0
            flaky_count = 0
            blocked_count = 0

            if run_status in (TestRunStatus.COMPLETED, TestRunStatus.RUNNING):
                for j, tc_id in enumerate(suite_obj.test_case_ids):
                    tc_obj = self._test_cases.get(tc_id)
                    if j % 11 == 0:
                        st = TestStatus.FAILED
                        failed += 1
                    elif j % 13 == 0:
                        st = TestStatus.FLAKY
                        flaky_count += 1
                    elif j % 17 == 0:
                        st = TestStatus.SKIPPED
                        skipped += 1
                    elif j % 19 == 0:
                        st = TestStatus.BLOCKED
                        blocked_count += 1
                    else:
                        st = TestStatus.PASSED
                        passed += 1

                    results.append(
                        TestCaseResult(
                            test_case_id=tc_id,
                            test_case_name=tc_obj.name if tc_obj else tc_id,
                            status=st,
                            duration_ms=tc_obj.expected_duration_ms if tc_obj else 1000,
                            error_message="Assertion failed" if st == TestStatus.FAILED else None,
                            stack_trace="at test.py:42" if st == TestStatus.FAILED else None,
                            retry_count=1 if st == TestStatus.FLAKY else 0,
                            screenshots=[],
                        )
                    )

            pr = round(passed / total * 100, 2) if total > 0 else 0.0

            run = TestRun(
                id=run_id,
                suite_id=s_id,
                suite_name=suite_obj.name,
                status=run_status,
                trigger_type=TriggerType.MANUAL if idx % 3 == 0 else TriggerType.SCHEDULED,
                triggered_by="ci-bot" if idx % 2 == 0 else "qa-engineer",
                build_version=f"v1.{idx}.0-rc{idx+1}",
                environment="staging" if idx % 2 == 0 else "development",
                started_at=started,
                completed_at=completed,
                duration_seconds=dur,
                total_tests=total,
                passed=passed,
                failed=failed,
                skipped=skipped,
                flaky=flaky_count,
                blocked=blocked_count,
                pass_rate=pr,
                results=results,
                artifacts_url=f"https://artifacts.example.com/runs/{run_id}" if run_status == TestRunStatus.COMPLETED else None,
            )
            self._test_runs[run.id] = run

        # --- 5 flaky test reports ---
        for fi in range(5):
            tc_id = f"tc-{fi*5 + 3:03d}"
            tc_obj = self._test_cases.get(tc_id)
            causes = list(FlakyRootCause)
            report = FlakyTestReport(
                test_case_id=tc_id,
                test_case_name=tc_obj.name if tc_obj else tc_id,
                flaky_rate=round(0.05 + fi * 0.04, 2),
                total_runs_30d=30 + fi * 10,
                failures_30d=2 + fi * 2,
                last_flaky_run=now - timedelta(days=fi),
                root_cause_category=causes[fi % len(causes)],
                triaged=fi < 2,
            )
            self._flaky_reports[report.test_case_id] = report

        # --- 8 coverage entries ---
        for ci, mod in enumerate(modules[:8]):
            cov_pct = round(70 + ci * 3.5, 1)
            branch_pct = round(cov_pct - 10, 1)
            total_lines = 1000 + ci * 500
            covered = int(total_lines * cov_pct / 100)
            self._coverage[mod] = TestCoverage(
                module=mod,
                total_lines=total_lines,
                covered_lines=covered,
                coverage_percent=cov_pct,
                branch_coverage_percent=branch_pct,
                uncovered_functions=[
                    f"{mod}_edge_case_{k}" for k in range(3 - min(ci, 2))
                ],
            )

        # --- Trend data (14 days) ---
        for di in range(14):
            day = now - timedelta(days=13 - di)
            self._trends.append(
                RegressionTrend(
                    date=day.strftime("%Y-%m-%d"),
                    total_tests=25 + di,
                    pass_rate=round(90 + di * 0.5, 1),
                    avg_duration_seconds=round(120 - di * 2, 1),
                    new_failures=max(0, 3 - di // 4),
                    resolved_failures=1 + di // 5,
                )
            )

    # ------------------------------------------------------------------
    # Test Case CRUD
    # ------------------------------------------------------------------

    def list_test_cases(
        self,
        *,
        suite_type: TestSuiteType | None = None,
        priority: TestPriority | None = None,
        module: str | None = None,
        tag: str | None = None,
        automated: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> TestCaseListResponse:
        items = list(self._test_cases.values())
        if suite_type:
            items = [t for t in items if t.suite_type == suite_type]
        if priority:
            items = [t for t in items if t.priority == priority]
        if module:
            items = [t for t in items if t.module == module]
        if tag:
            items = [t for t in items if tag in t.tags]
        if automated is not None:
            items = [t for t in items if t.automated == automated]
        total = len(items)
        return TestCaseListResponse(items=items[offset: offset + limit], total=total, limit=limit, offset=offset)

    def get_test_case(self, test_case_id: str) -> TestCase | None:
        return self._test_cases.get(test_case_id)

    def create_test_case(self, payload: TestCaseCreate) -> TestCase:
        tc_id = f"tc-{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow()
        tc = TestCase(
            id=tc_id,
            name=payload.name,
            description=payload.description,
            suite_type=payload.suite_type,
            priority=payload.priority,
            module=payload.module,
            tags=payload.tags,
            expected_duration_ms=payload.expected_duration_ms,
            owner=payload.owner,
            automated=payload.automated,
            preconditions=payload.preconditions,
            steps=payload.steps,
            created_at=now,
            updated_at=now,
        )
        self._test_cases[tc.id] = tc
        return tc

    def update_test_case(self, test_case_id: str, payload: TestCaseUpdate) -> TestCase | None:
        tc = self._test_cases.get(test_case_id)
        if not tc:
            return None
        updates = payload.model_dump(exclude_none=True)
        updated = tc.model_copy(update={**updates, "updated_at": datetime.utcnow()})
        self._test_cases[test_case_id] = updated
        return updated

    def delete_test_case(self, test_case_id: str) -> bool:
        return self._test_cases.pop(test_case_id, None) is not None

    # ------------------------------------------------------------------
    # Test Suite CRUD
    # ------------------------------------------------------------------

    def list_test_suites(
        self,
        *,
        suite_type: TestSuiteType | None = None,
        enabled: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> TestSuiteListResponse:
        items = list(self._test_suites.values())
        if suite_type:
            items = [s for s in items if s.suite_type == suite_type]
        if enabled is not None:
            items = [s for s in items if s.enabled == enabled]
        total = len(items)
        return TestSuiteListResponse(items=items[offset: offset + limit], total=total, limit=limit, offset=offset)

    def get_test_suite(self, suite_id: str) -> TestSuite | None:
        return self._test_suites.get(suite_id)

    def create_test_suite(self, payload: TestSuiteCreate) -> TestSuite:
        sid = f"suite-{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow()
        suite = TestSuite(
            id=sid,
            name=payload.name,
            suite_type=payload.suite_type,
            description=payload.description,
            test_case_ids=payload.test_case_ids,
            trigger_types=payload.trigger_types,
            schedule_cron=payload.schedule_cron,
            estimated_duration_minutes=payload.estimated_duration_minutes,
            parallelizable=payload.parallelizable,
            max_parallel=payload.max_parallel,
            environment_requirements=payload.environment_requirements,
            enabled=payload.enabled,
            created_at=now,
            updated_at=now,
        )
        self._test_suites[suite.id] = suite
        return suite

    def update_test_suite(self, suite_id: str, payload: TestSuiteUpdate) -> TestSuite | None:
        suite = self._test_suites.get(suite_id)
        if not suite:
            return None
        updates = payload.model_dump(exclude_none=True)
        updated = suite.model_copy(update={**updates, "updated_at": datetime.utcnow()})
        self._test_suites[suite_id] = updated
        return updated

    def delete_test_suite(self, suite_id: str) -> bool:
        return self._test_suites.pop(suite_id, None) is not None

    def enable_suite(self, suite_id: str) -> TestSuite | None:
        suite = self._test_suites.get(suite_id)
        if not suite:
            return None
        updated = suite.model_copy(update={"enabled": True, "updated_at": datetime.utcnow()})
        self._test_suites[suite_id] = updated
        return updated

    def disable_suite(self, suite_id: str) -> TestSuite | None:
        suite = self._test_suites.get(suite_id)
        if not suite:
            return None
        updated = suite.model_copy(update={"enabled": False, "updated_at": datetime.utcnow()})
        self._test_suites[suite_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Test Runs
    # ------------------------------------------------------------------

    def trigger_test_run(self, request: TriggerTestRunRequest) -> TestRun | None:
        suite = self._test_suites.get(request.suite_id)
        if not suite:
            return None
        now = datetime.utcnow()
        run_id = f"run-{uuid.uuid4().hex[:8]}"
        total = len(suite.test_case_ids)

        # Simulate immediate execution for a small suite
        results: list[TestCaseResult] = []
        passed = 0
        failed = 0
        skipped = 0
        flaky_count = 0
        blocked_count = 0

        for j, tc_id in enumerate(suite.test_case_ids):
            tc = self._test_cases.get(tc_id)
            if j % 9 == 0 and j > 0:
                st = TestStatus.FAILED
                failed += 1
            else:
                st = TestStatus.PASSED
                passed += 1
            results.append(
                TestCaseResult(
                    test_case_id=tc_id,
                    test_case_name=tc.name if tc else tc_id,
                    status=st,
                    duration_ms=tc.expected_duration_ms if tc else 1000,
                    error_message="Simulated failure" if st == TestStatus.FAILED else None,
                    retry_count=0,
                )
            )

        pr = round(passed / total * 100, 2) if total > 0 else 0.0
        dur = suite.estimated_duration_minutes * 60.0

        run = TestRun(
            id=run_id,
            suite_id=suite.id,
            suite_name=suite.name,
            status=TestRunStatus.COMPLETED,
            trigger_type=request.trigger_type,
            triggered_by=request.triggered_by,
            build_version=request.build_version,
            environment=request.environment,
            started_at=now,
            completed_at=now + timedelta(seconds=dur),
            duration_seconds=dur,
            total_tests=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            flaky=flaky_count,
            blocked=blocked_count,
            pass_rate=pr,
            results=results,
            artifacts_url=f"https://artifacts.example.com/runs/{run_id}",
        )
        self._test_runs[run.id] = run
        return run

    def list_test_runs(
        self,
        *,
        suite_id: str | None = None,
        status: TestRunStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> TestRunListResponse:
        items = list(self._test_runs.values())
        if suite_id:
            items = [r for r in items if r.suite_id == suite_id]
        if status:
            items = [r for r in items if r.status == status]
        # Sort by most recent first
        items.sort(key=lambda r: r.started_at or datetime.min, reverse=True)
        total = len(items)
        return TestRunListResponse(items=items[offset: offset + limit], total=total, limit=limit, offset=offset)

    def get_test_run(self, run_id: str) -> TestRun | None:
        return self._test_runs.get(run_id)

    def get_run_results(self, run_id: str) -> list[TestCaseResult]:
        run = self._test_runs.get(run_id)
        return run.results if run else []

    # ------------------------------------------------------------------
    # Coverage
    # ------------------------------------------------------------------

    def list_coverage(self) -> CoverageListResponse:
        items = list(self._coverage.values())
        total_lines = sum(c.total_lines for c in items)
        covered_lines = sum(c.covered_lines for c in items)
        overall = round(covered_lines / total_lines * 100, 2) if total_lines > 0 else 0.0
        return CoverageListResponse(items=items, total=len(items), overall_coverage=overall)

    def get_module_coverage(self, module: str) -> TestCoverage | None:
        return self._coverage.get(module)

    # ------------------------------------------------------------------
    # Flaky Tests
    # ------------------------------------------------------------------

    def list_flaky_tests(self, *, triaged: bool | None = None) -> FlakyTestListResponse:
        items = list(self._flaky_reports.values())
        if triaged is not None:
            items = [f for f in items if f.triaged == triaged]
        items.sort(key=lambda f: f.flaky_rate, reverse=True)
        return FlakyTestListResponse(items=items, total=len(items))

    def get_flaky_report(self, test_case_id: str) -> FlakyTestReport | None:
        return self._flaky_reports.get(test_case_id)

    def triage_flaky_test(
        self, test_case_id: str, root_cause: FlakyRootCause, triaged: bool = True
    ) -> FlakyTestReport | None:
        report = self._flaky_reports.get(test_case_id)
        if not report:
            return None
        updated = report.model_copy(update={"root_cause_category": root_cause, "triaged": triaged})
        self._flaky_reports[test_case_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Trends
    # ------------------------------------------------------------------

    def get_regression_trends(self, *, days: int = 14) -> TrendResponse:
        items = self._trends[-days:] if days < len(self._trends) else self._trends
        return TrendResponse(items=items, total_days=len(items))

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def get_test_health_dashboard(self) -> TestHealthDashboard:
        all_tc = list(self._test_cases.values())
        total_tc = len(all_tc)
        automated = sum(1 for t in all_tc if t.automated)
        manual = total_tc - automated
        automation_rate = round(automated / total_tc * 100, 2) if total_tc > 0 else 0.0

        completed_runs = [r for r in self._test_runs.values() if r.status == TestRunStatus.COMPLETED]
        overall_pass = (
            round(sum(r.pass_rate for r in completed_runs) / len(completed_runs), 2)
            if completed_runs
            else 0.0
        )
        avg_dur = (
            round(sum(r.duration_seconds or 0 for r in completed_runs) / len(completed_runs), 2)
            if completed_runs
            else 0.0
        )

        flaky_items = list(self._flaky_reports.values())
        avg_flaky = (
            round(sum(f.flaky_rate for f in flaky_items) / len(flaky_items), 4)
            if flaky_items
            else 0.0
        )

        p0_cases = [t for t in all_tc if t.priority == TestPriority.P0_CRITICAL and t.last_run_status is not None]
        p0_pass = round(sum(1 for t in p0_cases if t.last_run_status == TestStatus.PASSED) / len(p0_cases) * 100, 2) if p0_cases else 0.0
        p1_cases = [t for t in all_tc if t.priority == TestPriority.P1_HIGH and t.last_run_status is not None]
        p1_pass = round(sum(1 for t in p1_cases if t.last_run_status == TestStatus.PASSED) / len(p1_cases) * 100, 2) if p1_cases else 0.0

        metrics = TestMetrics(
            total_test_cases=total_tc,
            total_automated=automated,
            total_manual=manual,
            automation_rate=automation_rate,
            overall_pass_rate=overall_pass,
            avg_duration_seconds=avg_dur,
            total_runs_30d=len(completed_runs),
            flaky_test_count=len(flaky_items),
            avg_flaky_rate=avg_flaky,
            p0_pass_rate=p0_pass,
            p1_pass_rate=p1_pass,
            coverage_by_module=list(self._coverage.values()),
        )

        enabled_suites = sum(1 for s in self._test_suites.values() if s.enabled)
        disabled_suites = len(self._test_suites) - enabled_suites

        # Health score: blend of pass rate, automation, coverage, flaky
        cov = self.list_coverage()
        health = min(100.0, round(
            overall_pass * 0.4
            + automation_rate * 0.2
            + cov.overall_coverage * 0.25
            + (100 - avg_flaky * 100) * 0.15,
            1,
        ))

        recent = sorted(
            self._test_runs.values(),
            key=lambda r: r.started_at or datetime.min,
            reverse=True,
        )[:5]

        return TestHealthDashboard(
            metrics=metrics,
            recent_runs=list(recent),
            flaky_reports=flaky_items,
            trends=self._trends[-7:],
            suites_enabled=enabled_suites,
            suites_disabled=disabled_suites,
            next_scheduled_run=datetime.utcnow() + timedelta(hours=1),
            health_score=health,
        )

    # ------------------------------------------------------------------
    # Impact Analysis
    # ------------------------------------------------------------------

    def analyze_impact(self, request: ImpactAnalysisRequest) -> ImpactAnalysisResponse:
        affected_ids: set[str] = set()
        for tc in self._test_cases.values():
            if tc.module in request.changed_modules:
                affected_ids.add(tc.id)
            elif request.include_dependent:
                # Simple heuristic: if module shares a prefix with changed module
                for cm in request.changed_modules:
                    if tc.module.split("_")[0] == cm.split("_")[0]:
                        affected_ids.add(tc.id)

        affected = [self._test_cases[tid] for tid in affected_ids if tid in self._test_cases]
        est_ms = sum(t.expected_duration_ms for t in affected)
        est_min = round(est_ms / 60000, 2)

        # Recommend suite type based on count
        if len(affected) <= 5:
            rec = TestSuiteType.SMOKE
        elif len(affected) <= 15:
            rec = TestSuiteType.INTEGRATION
        else:
            rec = TestSuiteType.REGRESSION

        return ImpactAnalysisResponse(
            changed_modules=request.changed_modules,
            affected_test_ids=sorted(affected_ids),
            affected_test_count=len(affected_ids),
            estimated_duration_minutes=est_min,
            recommended_suite_type=rec,
        )

    # ------------------------------------------------------------------
    # Estimated Run Time
    # ------------------------------------------------------------------

    def estimate_run_time(self, suite_id: str) -> EstimatedRunTime | None:
        suite = self._test_suites.get(suite_id)
        if not suite:
            return None
        total_ms = 0
        for tc_id in suite.test_case_ids:
            tc = self._test_cases.get(tc_id)
            total_ms += tc.expected_duration_ms if tc else 1000
        sequential_min = round(total_ms / 60000, 2)
        parallel_min = round(sequential_min / suite.max_parallel, 2) if suite.parallelizable else sequential_min
        return EstimatedRunTime(
            suite_id=suite_id,
            test_count=len(suite.test_case_ids),
            sequential_minutes=sequential_min,
            parallel_minutes=parallel_min,
            max_parallel=suite.max_parallel,
        )

    # ------------------------------------------------------------------
    # Prioritization
    # ------------------------------------------------------------------

    def get_prioritized_tests(
        self,
        *,
        suite_type: TestSuiteType | None = None,
        limit: int = 50,
    ) -> PrioritizedTestList:
        items = list(self._test_cases.values())
        if suite_type:
            items = [t for t in items if t.suite_type == suite_type]

        priority_order = {
            TestPriority.P0_CRITICAL: 0,
            TestPriority.P1_HIGH: 1,
            TestPriority.P2_MEDIUM: 2,
            TestPriority.P3_LOW: 3,
        }
        items.sort(key=lambda t: (priority_order.get(t.priority, 99), -t.flaky_rate))
        selected = items[:limit]
        est_ms = sum(t.expected_duration_ms for t in selected)
        return PrioritizedTestList(
            items=selected,
            total=len(selected),
            estimated_duration_minutes=round(est_ms / 60000, 2),
        )

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        return {
            "test_cases": len(self._test_cases),
            "test_suites": len(self._test_suites),
            "test_runs": len(self._test_runs),
            "coverage_entries": len(self._coverage),
            "flaky_reports": len(self._flaky_reports),
            "trend_days": len(self._trends),
        }
