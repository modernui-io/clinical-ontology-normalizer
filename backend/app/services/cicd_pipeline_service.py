"""CI/CD Pipeline Configuration & Management service (DEVOPS-5).

Manages pipeline configurations, runs, metrics, and optimization
recommendations for the clinical trial patient recruitment platform.

Usage:
    from app.services.cicd_pipeline_service import get_cicd_pipeline_service

    service = get_cicd_pipeline_service()
    configs = service.list_configs()
    metrics = service.get_metrics("PIPE-001")
"""

from __future__ import annotations

import hashlib
import logging
import random
from datetime import datetime, timedelta, timezone
from threading import Lock
from uuid import uuid4

from app.schemas.cicd_pipeline import (
    DurationEstimate,
    FlakyStageEntry,
    PipelineConfig,
    PipelineConfigCreateRequest,
    PipelineConfigUpdateRequest,
    PipelineMetrics,
    PipelineOptimization,
    PipelineRun,
    PipelineStage,
    PipelineStatus,
    RetryConfig,
    StageConfig,
    StageResult,
    TriggerType,
)

logger = logging.getLogger(__name__)

# Singleton instance and lock
_cicd_instance: CICDPipelineService | None = None
_cicd_lock = Lock()


class CICDPipelineService:
    """Manages CI/CD pipeline configs, runs, and analytics."""

    def __init__(self) -> None:
        self._configs: dict[str, PipelineConfig] = {}
        self._runs: dict[str, PipelineRun] = {}  # run_id -> PipelineRun
        self._populate_seed_data()

    # -----------------------------------------------------------------------
    # Seed data
    # -----------------------------------------------------------------------

    def _populate_seed_data(self) -> None:
        """Pre-populate 3 pipeline configs and 10-15 runs with varied results."""
        now = datetime.now(timezone.utc)

        # ---- Pipeline Config 1: Main CI Pipeline ----
        main_stages = [
            StageConfig(
                stage=PipelineStage.BUILD,
                name="Install & Build",
                commands=["npm ci", "npm run build", "pip install -e '.[dev]'"],
                timeout_minutes=10,
                depends_on=[],
                artifacts=["dist/", "build/"],
            ),
            StageConfig(
                stage=PipelineStage.LINT,
                name="Lint Check",
                commands=["ruff check backend/", "npm run lint"],
                timeout_minutes=5,
                depends_on=[PipelineStage.BUILD],
            ),
            StageConfig(
                stage=PipelineStage.TYPECHECK,
                name="Type Check",
                commands=["mypy backend/app/", "npx tsc --noEmit"],
                timeout_minutes=8,
                depends_on=[PipelineStage.BUILD],
            ),
            StageConfig(
                stage=PipelineStage.UNIT_TEST,
                name="Unit Tests",
                commands=["pytest backend/tests/ -x --tb=short", "npm run test -- --ci"],
                timeout_minutes=15,
                depends_on=[PipelineStage.LINT, PipelineStage.TYPECHECK],
                artifacts=["coverage/", "test-results/"],
            ),
            StageConfig(
                stage=PipelineStage.INTEGRATION_TEST,
                name="Integration Tests",
                commands=["pytest backend/tests/integration/ -x --tb=short"],
                timeout_minutes=20,
                depends_on=[PipelineStage.UNIT_TEST],
            ),
            StageConfig(
                stage=PipelineStage.SECURITY_SCAN,
                name="Security Scan",
                commands=["trivy fs --severity HIGH,CRITICAL .", "bandit -r backend/app/"],
                timeout_minutes=10,
                depends_on=[PipelineStage.BUILD],
                allow_failure=True,
            ),
            StageConfig(
                stage=PipelineStage.DOCKER_BUILD,
                name="Docker Build",
                commands=["docker build -t app:$COMMIT_SHA ."],
                timeout_minutes=15,
                depends_on=[PipelineStage.UNIT_TEST, PipelineStage.SECURITY_SCAN],
                artifacts=["docker-image"],
            ),
            StageConfig(
                stage=PipelineStage.DEPLOY_STAGING,
                name="Deploy to Staging",
                commands=["kubectl apply -f k8s/staging/", "kubectl rollout status deployment/app -n staging"],
                timeout_minutes=10,
                depends_on=[PipelineStage.DOCKER_BUILD],
                environment="staging",
            ),
            StageConfig(
                stage=PipelineStage.E2E_TEST,
                name="E2E Tests",
                commands=["npx playwright test --project=chromium"],
                timeout_minutes=20,
                depends_on=[PipelineStage.DEPLOY_STAGING],
                environment="staging",
                artifacts=["playwright-report/"],
            ),
            StageConfig(
                stage=PipelineStage.DEPLOY_PRODUCTION,
                name="Deploy to Production",
                commands=["kubectl apply -f k8s/production/", "kubectl rollout status deployment/app -n production"],
                timeout_minutes=15,
                depends_on=[PipelineStage.E2E_TEST],
                environment="production",
            ),
            StageConfig(
                stage=PipelineStage.POST_DEPLOY_VERIFY,
                name="Post-Deploy Verification",
                commands=["curl -f https://api.example.com/health", "python scripts/smoke_test.py"],
                timeout_minutes=5,
                depends_on=[PipelineStage.DEPLOY_PRODUCTION],
                environment="production",
            ),
        ]

        self._configs["PIPE-001"] = PipelineConfig(
            id="PIPE-001",
            name="Main CI/CD Pipeline",
            description="Full build, test, and deploy pipeline for main branch pushes",
            trigger=TriggerType.PUSH,
            branch_pattern="main",
            stages=main_stages,
            env_vars={"NODE_ENV": "production", "PYTHON_ENV": "ci"},
            timeout_minutes=120,
            retry_config=RetryConfig(
                max_retries=2,
                retry_delay_seconds=30,
                retry_on_stages=[PipelineStage.UNIT_TEST, PipelineStage.E2E_TEST],
            ),
            created_at=now - timedelta(days=90),
            updated_at=now - timedelta(days=5),
        )

        # ---- Pipeline Config 2: PR Validation Pipeline ----
        pr_stages = [
            StageConfig(
                stage=PipelineStage.BUILD,
                name="Install & Build",
                commands=["npm ci", "pip install -e '.[dev]'"],
                timeout_minutes=10,
                depends_on=[],
            ),
            StageConfig(
                stage=PipelineStage.LINT,
                name="Lint Check",
                commands=["ruff check backend/", "npm run lint"],
                timeout_minutes=5,
                depends_on=[PipelineStage.BUILD],
            ),
            StageConfig(
                stage=PipelineStage.TYPECHECK,
                name="Type Check",
                commands=["mypy backend/app/"],
                timeout_minutes=8,
                depends_on=[PipelineStage.BUILD],
            ),
            StageConfig(
                stage=PipelineStage.UNIT_TEST,
                name="Unit Tests",
                commands=["pytest backend/tests/ -x --tb=short"],
                timeout_minutes=15,
                depends_on=[PipelineStage.LINT, PipelineStage.TYPECHECK],
                artifacts=["coverage/"],
            ),
            StageConfig(
                stage=PipelineStage.SECURITY_SCAN,
                name="Security Scan",
                commands=["trivy fs --severity HIGH,CRITICAL ."],
                timeout_minutes=10,
                depends_on=[PipelineStage.BUILD],
                allow_failure=True,
            ),
        ]

        self._configs["PIPE-002"] = PipelineConfig(
            id="PIPE-002",
            name="PR Validation Pipeline",
            description="Lightweight checks for pull request validation",
            trigger=TriggerType.PR,
            branch_pattern="feature/*",
            stages=pr_stages,
            env_vars={"PYTHON_ENV": "ci"},
            timeout_minutes=45,
            retry_config=RetryConfig(max_retries=1, retry_delay_seconds=15),
            created_at=now - timedelta(days=85),
            updated_at=now - timedelta(days=10),
        )

        # ---- Pipeline Config 3: Nightly Security Pipeline ----
        security_stages = [
            StageConfig(
                stage=PipelineStage.BUILD,
                name="Install Dependencies",
                commands=["pip install -e '.[dev]'", "npm ci"],
                timeout_minutes=10,
                depends_on=[],
            ),
            StageConfig(
                stage=PipelineStage.SECURITY_SCAN,
                name="Full Security Scan",
                commands=[
                    "trivy fs --severity LOW,MEDIUM,HIGH,CRITICAL .",
                    "bandit -r backend/app/ -ll",
                    "safety check",
                    "npm audit --audit-level=moderate",
                ],
                timeout_minutes=30,
                depends_on=[PipelineStage.BUILD],
                artifacts=["security-reports/"],
            ),
            StageConfig(
                stage=PipelineStage.INTEGRATION_TEST,
                name="Security Integration Tests",
                commands=["pytest backend/tests/security/ -x --tb=short"],
                timeout_minutes=20,
                depends_on=[PipelineStage.SECURITY_SCAN],
            ),
        ]

        self._configs["PIPE-003"] = PipelineConfig(
            id="PIPE-003",
            name="Nightly Security Pipeline",
            description="Comprehensive security scanning run nightly",
            trigger=TriggerType.SCHEDULE,
            branch_pattern="main",
            stages=security_stages,
            env_vars={"SCAN_DEPTH": "full"},
            timeout_minutes=90,
            retry_config=RetryConfig(max_retries=1, retry_delay_seconds=60),
            created_at=now - timedelta(days=60),
            updated_at=now - timedelta(days=3),
        )

        # ---- Seed pipeline runs ----
        self._seed_runs(now)

    def _seed_runs(self, now: datetime) -> None:
        """Generate 12 varied pipeline runs."""
        random.seed(42)  # deterministic for tests

        run_templates: list[dict] = [
            # Main pipeline - 6 runs
            {"config_id": "PIPE-001", "branch": "main", "trigger": TriggerType.PUSH, "by": "github-actions", "status": PipelineStatus.PASSED, "days_ago": 1},
            {"config_id": "PIPE-001", "branch": "main", "trigger": TriggerType.PUSH, "by": "github-actions", "status": PipelineStatus.PASSED, "days_ago": 2},
            {"config_id": "PIPE-001", "branch": "main", "trigger": TriggerType.PUSH, "by": "github-actions", "status": PipelineStatus.FAILED, "days_ago": 3, "fail_stage": PipelineStage.E2E_TEST},
            {"config_id": "PIPE-001", "branch": "main", "trigger": TriggerType.PUSH, "by": "github-actions", "status": PipelineStatus.PASSED, "days_ago": 5},
            {"config_id": "PIPE-001", "branch": "main", "trigger": TriggerType.MANUAL, "by": "dev-lead", "status": PipelineStatus.PASSED, "days_ago": 7},
            {"config_id": "PIPE-001", "branch": "main", "trigger": TriggerType.PUSH, "by": "github-actions", "status": PipelineStatus.FAILED, "days_ago": 10, "fail_stage": PipelineStage.UNIT_TEST},
            # PR pipeline - 4 runs
            {"config_id": "PIPE-002", "branch": "feature/trial-matching", "trigger": TriggerType.PR, "by": "dev-a", "status": PipelineStatus.PASSED, "days_ago": 1},
            {"config_id": "PIPE-002", "branch": "feature/patient-import", "trigger": TriggerType.PR, "by": "dev-b", "status": PipelineStatus.FAILED, "days_ago": 2, "fail_stage": PipelineStage.LINT},
            {"config_id": "PIPE-002", "branch": "feature/fhir-export", "trigger": TriggerType.PR, "by": "dev-c", "status": PipelineStatus.PASSED, "days_ago": 4},
            {"config_id": "PIPE-002", "branch": "feature/patient-import", "trigger": TriggerType.PR, "by": "dev-b", "status": PipelineStatus.PASSED, "days_ago": 2},
            # Security pipeline - 2 runs
            {"config_id": "PIPE-003", "branch": "main", "trigger": TriggerType.SCHEDULE, "by": "cron", "status": PipelineStatus.PASSED, "days_ago": 1},
            {"config_id": "PIPE-003", "branch": "main", "trigger": TriggerType.SCHEDULE, "by": "cron", "status": PipelineStatus.FAILED, "days_ago": 2, "fail_stage": PipelineStage.SECURITY_SCAN},
        ]

        for idx, tmpl in enumerate(run_templates, start=1):
            run_id = f"RUN-{idx:03d}"
            config = self._configs[tmpl["config_id"]]
            started = now - timedelta(days=tmpl["days_ago"], hours=random.randint(0, 12))
            fail_stage = tmpl.get("fail_stage")
            overall_status: PipelineStatus = tmpl["status"]

            stage_results: list[StageResult] = []
            cursor = started
            for sc in config.stages:
                if overall_status == PipelineStatus.FAILED and fail_stage == sc.stage:
                    dur = random.uniform(5.0, 30.0)
                    stage_results.append(StageResult(
                        stage=sc.stage,
                        status=PipelineStatus.FAILED,
                        started_at=cursor,
                        completed_at=cursor + timedelta(seconds=dur),
                        duration_seconds=round(dur, 2),
                        output_summary=f"{sc.name} failed",
                        error_message=f"Stage {sc.stage.value} failed: exit code 1",
                    ))
                    cursor += timedelta(seconds=dur)
                    # Remaining stages are skipped
                    for remaining in config.stages[config.stages.index(sc) + 1:]:
                        stage_results.append(StageResult(
                            stage=remaining.stage,
                            status=PipelineStatus.SKIPPED,
                            output_summary="Skipped due to earlier failure",
                        ))
                    break
                else:
                    dur = random.uniform(10.0, 120.0)
                    stage_results.append(StageResult(
                        stage=sc.stage,
                        status=PipelineStatus.PASSED,
                        started_at=cursor,
                        completed_at=cursor + timedelta(seconds=dur),
                        duration_seconds=round(dur, 2),
                        output_summary=f"{sc.name} completed successfully",
                    ))
                    cursor += timedelta(seconds=dur)

            total_dur = sum(sr.duration_seconds for sr in stage_results)
            sha = hashlib.sha1(f"commit-{idx}".encode()).hexdigest()[:12]

            self._runs[run_id] = PipelineRun(
                id=run_id,
                config_id=tmpl["config_id"],
                trigger_type=tmpl["trigger"],
                branch=tmpl["branch"],
                commit_sha=sha,
                status=overall_status,
                stages_results=stage_results,
                started_at=started,
                completed_at=cursor,
                duration_seconds=round(total_dur, 2),
                triggered_by=tmpl["by"],
            )

        random.seed()  # restore default randomness

    # -----------------------------------------------------------------------
    # Config CRUD
    # -----------------------------------------------------------------------

    def list_configs(
        self,
        trigger: TriggerType | None = None,
    ) -> list[PipelineConfig]:
        """List pipeline configs, optionally filtering by trigger type."""
        configs = list(self._configs.values())
        if trigger is not None:
            configs = [c for c in configs if c.trigger == trigger]
        return configs

    def get_config(self, config_id: str) -> PipelineConfig | None:
        """Get a single pipeline config by ID."""
        return self._configs.get(config_id)

    def create_config(self, req: PipelineConfigCreateRequest) -> PipelineConfig:
        """Create a new pipeline config."""
        now = datetime.now(timezone.utc)
        config_id = f"PIPE-{uuid4().hex[:6].upper()}"
        config = PipelineConfig(
            id=config_id,
            name=req.name,
            description=req.description,
            trigger=req.trigger,
            branch_pattern=req.branch_pattern,
            stages=req.stages,
            env_vars=req.env_vars,
            timeout_minutes=req.timeout_minutes,
            retry_config=req.retry_config,
            created_at=now,
            updated_at=now,
        )
        self._configs[config_id] = config
        logger.info("Created pipeline config %s: %s", config_id, req.name)
        return config

    def update_config(self, config_id: str, req: PipelineConfigUpdateRequest) -> PipelineConfig | None:
        """Update an existing pipeline config. Returns None if not found."""
        config = self._configs.get(config_id)
        if config is None:
            return None

        now = datetime.now(timezone.utc)
        updates: dict = {}
        for field in ("name", "description", "trigger", "branch_pattern", "stages", "env_vars", "timeout_minutes", "retry_config"):
            val = getattr(req, field, None)
            if val is not None:
                updates[field] = val
        updates["updated_at"] = now

        updated = config.model_copy(update=updates)
        self._configs[config_id] = updated
        logger.info("Updated pipeline config %s", config_id)
        return updated

    def delete_config(self, config_id: str) -> bool:
        """Delete a pipeline config. Returns False if not found."""
        if config_id not in self._configs:
            return False
        del self._configs[config_id]
        # Also remove associated runs
        self._runs = {k: v for k, v in self._runs.items() if v.config_id != config_id}
        logger.info("Deleted pipeline config %s", config_id)
        return True

    # -----------------------------------------------------------------------
    # Run CRUD
    # -----------------------------------------------------------------------

    def list_runs(
        self,
        config_id: str | None = None,
        status: PipelineStatus | None = None,
        branch: str | None = None,
        limit: int = 50,
    ) -> list[PipelineRun]:
        """List pipeline runs with optional filters, newest first."""
        runs = list(self._runs.values())
        if config_id is not None:
            runs = [r for r in runs if r.config_id == config_id]
        if status is not None:
            runs = [r for r in runs if r.status == status]
        if branch is not None:
            runs = [r for r in runs if r.branch == branch]
        runs.sort(key=lambda r: r.started_at, reverse=True)
        return runs[:limit]

    def get_run(self, run_id: str) -> PipelineRun | None:
        """Get a single pipeline run by ID."""
        return self._runs.get(run_id)

    def trigger_pipeline(
        self,
        config_id: str,
        branch: str = "main",
        commit_sha: str = "HEAD",
        triggered_by: str = "manual",
    ) -> PipelineRun | None:
        """Simulate a pipeline run for the given config. Returns None if config not found."""
        config = self._configs.get(config_id)
        if config is None:
            return None

        now = datetime.now(timezone.utc)
        run_id = f"RUN-{uuid4().hex[:6].upper()}"

        if commit_sha == "HEAD":
            commit_sha = hashlib.sha1(f"{run_id}-{now.isoformat()}".encode()).hexdigest()[:12]

        stage_results: list[StageResult] = []
        cursor = now
        overall_status = PipelineStatus.PASSED

        for sc in config.stages:
            # Simulate ~5% chance of failure for non-allow_failure stages
            failed = not sc.allow_failure and random.random() < 0.05
            dur = random.uniform(8.0, 90.0)

            if failed:
                stage_results.append(StageResult(
                    stage=sc.stage,
                    status=PipelineStatus.FAILED,
                    started_at=cursor,
                    completed_at=cursor + timedelta(seconds=dur),
                    duration_seconds=round(dur, 2),
                    output_summary=f"{sc.name} failed",
                    error_message=f"Stage {sc.stage.value} failed: simulated failure",
                ))
                cursor += timedelta(seconds=dur)
                overall_status = PipelineStatus.FAILED
                # Skip remaining stages
                for remaining in config.stages[config.stages.index(sc) + 1:]:
                    stage_results.append(StageResult(
                        stage=remaining.stage,
                        status=PipelineStatus.SKIPPED,
                        output_summary="Skipped due to earlier failure",
                    ))
                break
            else:
                status_out = PipelineStatus.PASSED
                if sc.allow_failure and random.random() < 0.2:
                    status_out = PipelineStatus.FAILED  # allow_failure stages can fail

                stage_results.append(StageResult(
                    stage=sc.stage,
                    status=status_out,
                    started_at=cursor,
                    completed_at=cursor + timedelta(seconds=dur),
                    duration_seconds=round(dur, 2),
                    output_summary=f"{sc.name} completed"
                    if status_out == PipelineStatus.PASSED
                    else f"{sc.name} failed (non-blocking)",
                ))
                cursor += timedelta(seconds=dur)

        total_dur = sum(sr.duration_seconds for sr in stage_results)

        run = PipelineRun(
            id=run_id,
            config_id=config_id,
            trigger_type=TriggerType.MANUAL,
            branch=branch,
            commit_sha=commit_sha,
            status=overall_status,
            stages_results=stage_results,
            started_at=now,
            completed_at=cursor,
            duration_seconds=round(total_dur, 2),
            triggered_by=triggered_by,
        )
        self._runs[run_id] = run
        logger.info("Triggered pipeline run %s for config %s", run_id, config_id)
        return run

    # -----------------------------------------------------------------------
    # Metrics
    # -----------------------------------------------------------------------

    def get_metrics(self, config_id: str | None = None) -> PipelineMetrics:
        """Calculate pipeline metrics. Optionally scoped to a single config."""
        runs = list(self._runs.values())
        if config_id is not None:
            runs = [r for r in runs if r.config_id == config_id]

        if not runs:
            return PipelineMetrics()

        total = len(runs)
        passed = sum(1 for r in runs if r.status == PipelineStatus.PASSED)
        success_rate = round((passed / total) * 100, 2) if total else 0.0
        avg_dur = round(sum(r.duration_seconds for r in runs) / total, 2) if total else 0.0

        # Per-stage success rate
        stage_runs: dict[str, list[PipelineStatus]] = {}
        stage_durations: dict[str, list[float]] = {}
        for r in runs:
            for sr in r.stages_results:
                key = sr.stage.value
                stage_runs.setdefault(key, []).append(sr.status)
                if sr.duration_seconds > 0:
                    stage_durations.setdefault(key, []).append(sr.duration_seconds)

        by_stage_success: dict[str, float] = {}
        most_failed: list[tuple[str, float]] = []
        for stage, statuses in stage_runs.items():
            non_skipped = [s for s in statuses if s != PipelineStatus.SKIPPED]
            if non_skipped:
                p = sum(1 for s in non_skipped if s == PipelineStatus.PASSED) / len(non_skipped)
                by_stage_success[stage] = round(p * 100, 2)
                fail_rate = 1.0 - p
                if fail_rate > 0:
                    most_failed.append((stage, fail_rate))

        most_failed.sort(key=lambda x: x[1], reverse=True)

        # Slowest stages
        avg_stage_dur: list[tuple[str, float]] = []
        for stage, durs in stage_durations.items():
            avg_stage_dur.append((stage, sum(durs) / len(durs)))
        avg_stage_dur.sort(key=lambda x: x[1], reverse=True)

        # Runs per day
        if len(runs) >= 2:
            dates = sorted(r.started_at for r in runs)
            span_days = max((dates[-1] - dates[0]).total_seconds() / 86400, 1)
            runs_per_day = round(total / span_days, 2)
        else:
            runs_per_day = float(total)

        # Flaky count
        flaky = self._detect_flaky_stages(runs)

        return PipelineMetrics(
            total_runs=total,
            success_rate=success_rate,
            avg_duration_seconds=avg_dur,
            by_stage_success=by_stage_success,
            slowest_stages=[s for s, _ in avg_stage_dur[:5]],
            most_failed_stages=[s for s, _ in most_failed[:5]],
            runs_per_day_avg=runs_per_day,
            flaky_tests_count=len(flaky),
        )

    # -----------------------------------------------------------------------
    # Optimizations
    # -----------------------------------------------------------------------

    def analyze_optimizations(self, config_id: str) -> list[PipelineOptimization]:
        """Generate optimization recommendations for a pipeline config."""
        config = self._configs.get(config_id)
        if config is None:
            return []

        optimizations: list[PipelineOptimization] = []
        runs = [r for r in self._runs.values() if r.config_id == config_id]

        # 1. Parallelize independent stages
        parallelizable: list[str] = []
        for sc in config.stages:
            if not sc.depends_on:
                parallelizable.append(sc.stage.value)
        if len(parallelizable) > 1:
            optimizations.append(PipelineOptimization(
                recommendation=f"Parallelize independent stages: {', '.join(parallelizable)}",
                estimated_savings_seconds=45.0,
                affected_stages=parallelizable,
                confidence=0.85,
            ))

        # 2. Cache dependencies
        has_install = any("npm ci" in cmd or "pip install" in cmd for sc in config.stages for cmd in sc.commands)
        if has_install:
            optimizations.append(PipelineOptimization(
                recommendation="Cache npm and pip dependencies between runs to skip re-installation",
                estimated_savings_seconds=60.0,
                affected_stages=[PipelineStage.BUILD.value],
                confidence=0.9,
            ))

        # 3. Skip unchanged stages
        if len(config.stages) > 3:
            optimizations.append(PipelineOptimization(
                recommendation="Use file-change detection to skip unchanged stages (lint, typecheck)",
                estimated_savings_seconds=30.0,
                affected_stages=[PipelineStage.LINT.value, PipelineStage.TYPECHECK.value],
                confidence=0.7,
            ))

        # 4. Slow stage detection
        if runs:
            stage_durs: dict[str, list[float]] = {}
            for r in runs:
                for sr in r.stages_results:
                    if sr.duration_seconds > 0:
                        stage_durs.setdefault(sr.stage.value, []).append(sr.duration_seconds)
            for stage, durs in stage_durs.items():
                avg = sum(durs) / len(durs)
                if avg > 60.0:
                    optimizations.append(PipelineOptimization(
                        recommendation=f"Stage {stage} averages {avg:.0f}s - consider splitting or optimizing",
                        estimated_savings_seconds=avg * 0.3,
                        affected_stages=[stage],
                        confidence=0.65,
                    ))

        return optimizations

    # -----------------------------------------------------------------------
    # Flaky stage detection
    # -----------------------------------------------------------------------

    def _detect_flaky_stages(self, runs: list[PipelineRun] | None = None) -> list[FlakyStageEntry]:
        """Detect stages with intermittent failures (passed and failed across runs)."""
        if runs is None:
            runs = list(self._runs.values())

        stage_outcomes: dict[str, list[PipelineStatus]] = {}
        for r in runs:
            for sr in r.stages_results:
                if sr.status != PipelineStatus.SKIPPED:
                    stage_outcomes.setdefault(sr.stage.value, []).append(sr.status)

        flaky: list[FlakyStageEntry] = []
        for stage, statuses in stage_outcomes.items():
            total = len(statuses)
            if total < 2:
                continue
            failed = sum(1 for s in statuses if s == PipelineStatus.FAILED)
            passed = sum(1 for s in statuses if s == PipelineStatus.PASSED)
            if failed > 0 and passed > 0:
                rate = round(failed / total, 4)
                # Only flag if failure rate is between 5% and 50% (true flakiness range)
                if 0.05 <= rate <= 0.50:
                    flaky.append(FlakyStageEntry(
                        stage=stage,
                        flaky_rate=rate,
                        total_runs=total,
                        failed_runs=failed,
                    ))

        flaky.sort(key=lambda f: f.flaky_rate, reverse=True)
        return flaky

    def get_flaky_stages(self) -> list[FlakyStageEntry]:
        """Public API for flaky stage detection."""
        return self._detect_flaky_stages()

    # -----------------------------------------------------------------------
    # Duration estimation
    # -----------------------------------------------------------------------

    def estimate_pipeline_duration(self, config_id: str) -> DurationEstimate:
        """Estimate pipeline duration from historical p50/p95."""
        runs = [r for r in self._runs.values() if r.config_id == config_id and r.status == PipelineStatus.PASSED]

        if not runs:
            return DurationEstimate(config_id=config_id, p50_seconds=0.0, p95_seconds=0.0, sample_size=0)

        durations = sorted(r.duration_seconds for r in runs)
        n = len(durations)
        p50_idx = int(n * 0.5)
        p95_idx = min(int(n * 0.95), n - 1)

        return DurationEstimate(
            config_id=config_id,
            p50_seconds=round(durations[p50_idx], 2),
            p95_seconds=round(durations[p95_idx], 2),
            sample_size=n,
        )

    # -----------------------------------------------------------------------
    # Stats
    # -----------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return summary stats for health endpoints."""
        return {
            "total_configs": len(self._configs),
            "total_runs": len(self._runs),
        }


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------


def get_cicd_pipeline_service() -> CICDPipelineService:
    """Get or create the singleton CICDPipelineService."""
    global _cicd_instance
    if _cicd_instance is None:
        with _cicd_lock:
            if _cicd_instance is None:
                _cicd_instance = CICDPipelineService()
    return _cicd_instance


def reset_cicd_pipeline_service() -> None:
    """Reset the singleton (for tests)."""
    global _cicd_instance
    with _cicd_lock:
        _cicd_instance = None
