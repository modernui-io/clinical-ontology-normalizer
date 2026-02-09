"""Tests for CI/CD Pipeline Configuration & Management (DEVOPS-5).

Covers:
- Seed data verification (configs and runs)
- Pipeline config CRUD (create, read, update, delete, list with filters)
- Pipeline run triggering and simulation
- Run listing with filters (config_id, status, branch, limit)
- Aggregate and per-config metrics
- Optimization analysis and recommendations
- Duration estimation (p50/p95)
- Flaky stage detection
- Stage enum listing
- Error handling (404, validation, edge cases)
- Service singleton reset
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.cicd_pipeline import (
    PipelineStage,
    PipelineStatus,
    RetryConfig,
    StageConfig,
    TriggerType,
)
from app.services.cicd_pipeline_service import (
    get_cicd_pipeline_service,
    reset_cicd_pipeline_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_PREFIX = "/api/v1/cicd-pipeline"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_service():
    """Reset the singleton service before each test for isolation."""
    reset_cicd_pipeline_service()
    svc = get_cicd_pipeline_service()
    yield svc
    reset_cicd_pipeline_service()


@pytest.fixture
def svc(clean_service):
    """Shorthand for the fresh service."""
    return clean_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_config_payload(
    name: str = "Test Pipeline",
    description: str = "A test pipeline",
    trigger: str = "PUSH",
    branch_pattern: str = "main",
    stages: list | None = None,
    env_vars: dict | None = None,
    timeout_minutes: int = 60,
) -> dict:
    """Build a pipeline config create payload."""
    return {
        "name": name,
        "description": description,
        "trigger": trigger,
        "branch_pattern": branch_pattern,
        "stages": stages or [],
        "env_vars": env_vars or {},
        "timeout_minutes": timeout_minutes,
        "retry_config": {"max_retries": 2, "retry_delay_seconds": 30, "retry_on_stages": []},
    }


def _make_stage(
    stage: str = "BUILD",
    name: str = "Build Step",
    commands: list[str] | None = None,
    timeout_minutes: int = 10,
    depends_on: list[str] | None = None,
    allow_failure: bool = False,
) -> dict:
    """Build a stage config dict."""
    return {
        "stage": stage,
        "name": name,
        "commands": commands or ["echo hello"],
        "timeout_minutes": timeout_minutes,
        "depends_on": depends_on or [],
        "allow_failure": allow_failure,
        "environment": "ci",
        "artifacts": [],
    }


# ===========================================================================
# SEED DATA VERIFICATION
# ===========================================================================


class TestSeedData:
    """Verify the service boots with expected seed data."""

    def test_seed_configs_count(self, svc):
        """Service initializes with 3 pipeline configs."""
        configs = svc.list_configs()
        assert len(configs) == 3

    def test_seed_config_ids(self, svc):
        """Seed config IDs are PIPE-001, PIPE-002, PIPE-003."""
        config_ids = {c.id for c in svc.list_configs()}
        assert config_ids == {"PIPE-001", "PIPE-002", "PIPE-003"}

    def test_seed_main_pipeline(self, svc):
        """PIPE-001 is the Main CI/CD Pipeline with PUSH trigger."""
        config = svc.get_config("PIPE-001")
        assert config is not None
        assert config.name == "Main CI/CD Pipeline"
        assert config.trigger == TriggerType.PUSH
        assert config.branch_pattern == "main"

    def test_seed_main_pipeline_stages(self, svc):
        """PIPE-001 has 11 stages."""
        config = svc.get_config("PIPE-001")
        assert config is not None
        assert len(config.stages) == 11

    def test_seed_pr_pipeline(self, svc):
        """PIPE-002 is the PR Validation Pipeline."""
        config = svc.get_config("PIPE-002")
        assert config is not None
        assert config.name == "PR Validation Pipeline"
        assert config.trigger == TriggerType.PR
        assert config.branch_pattern == "feature/*"

    def test_seed_pr_pipeline_stages(self, svc):
        """PIPE-002 has 5 stages."""
        config = svc.get_config("PIPE-002")
        assert config is not None
        assert len(config.stages) == 5

    def test_seed_security_pipeline(self, svc):
        """PIPE-003 is the Nightly Security Pipeline."""
        config = svc.get_config("PIPE-003")
        assert config is not None
        assert config.name == "Nightly Security Pipeline"
        assert config.trigger == TriggerType.SCHEDULE

    def test_seed_security_pipeline_stages(self, svc):
        """PIPE-003 has 3 stages."""
        config = svc.get_config("PIPE-003")
        assert config is not None
        assert len(config.stages) == 3

    def test_seed_runs_count(self, svc):
        """Service initializes with 12 seed runs."""
        runs = svc.list_runs(limit=200)
        assert len(runs) == 12

    def test_seed_runs_for_main(self, svc):
        """PIPE-001 has 6 seed runs."""
        runs = svc.list_runs(config_id="PIPE-001", limit=200)
        assert len(runs) == 6

    def test_seed_runs_for_pr(self, svc):
        """PIPE-002 has 4 seed runs."""
        runs = svc.list_runs(config_id="PIPE-002", limit=200)
        assert len(runs) == 4

    def test_seed_runs_for_security(self, svc):
        """PIPE-003 has 2 seed runs."""
        runs = svc.list_runs(config_id="PIPE-003", limit=200)
        assert len(runs) == 2

    def test_seed_run_ids(self, svc):
        """Seed runs have IDs RUN-001 through RUN-012."""
        runs = svc.list_runs(limit=200)
        run_ids = {r.id for r in runs}
        expected = {f"RUN-{i:03d}" for i in range(1, 13)}
        assert run_ids == expected

    def test_seed_run_statuses(self, svc):
        """Seed runs include both PASSED and FAILED statuses."""
        runs = svc.list_runs(limit=200)
        statuses = {r.status for r in runs}
        assert PipelineStatus.PASSED in statuses
        assert PipelineStatus.FAILED in statuses

    def test_seed_main_retry_config(self, svc):
        """PIPE-001 retry config includes UNIT_TEST and E2E_TEST stages."""
        config = svc.get_config("PIPE-001")
        assert config is not None
        assert config.retry_config.max_retries == 2
        assert PipelineStage.UNIT_TEST in config.retry_config.retry_on_stages
        assert PipelineStage.E2E_TEST in config.retry_config.retry_on_stages

    def test_seed_config_env_vars(self, svc):
        """PIPE-001 has NODE_ENV and PYTHON_ENV env vars."""
        config = svc.get_config("PIPE-001")
        assert config is not None
        assert config.env_vars["NODE_ENV"] == "production"
        assert config.env_vars["PYTHON_ENV"] == "ci"

    def test_seed_config_timestamps(self, svc):
        """Seed configs have valid created_at and updated_at timestamps."""
        for config in svc.list_configs():
            assert config.created_at is not None
            assert config.updated_at is not None
            assert config.created_at <= config.updated_at

    def test_seed_run_stage_results(self, svc):
        """Each seed run has stage results matching its config."""
        run = svc.get_run("RUN-001")
        assert run is not None
        config = svc.get_config(run.config_id)
        assert config is not None
        assert len(run.stages_results) == len(config.stages)

    def test_seed_failed_run_has_skipped_stages(self, svc):
        """Failed runs skip stages after the failure point."""
        run = svc.get_run("RUN-003")
        assert run is not None
        assert run.status == PipelineStatus.FAILED
        statuses = [sr.status for sr in run.stages_results]
        assert PipelineStatus.FAILED in statuses
        assert PipelineStatus.SKIPPED in statuses


# ===========================================================================
# CONFIG CRUD - SERVICE LAYER
# ===========================================================================


class TestConfigCRUDService:
    """Test config CRUD operations directly on the service."""

    def test_list_configs_all(self, svc):
        """list_configs without filter returns all configs."""
        configs = svc.list_configs()
        assert len(configs) == 3

    def test_list_configs_filter_push(self, svc):
        """list_configs with trigger=PUSH returns only PUSH configs."""
        configs = svc.list_configs(trigger=TriggerType.PUSH)
        assert all(c.trigger == TriggerType.PUSH for c in configs)
        assert len(configs) == 1

    def test_list_configs_filter_pr(self, svc):
        """list_configs with trigger=PR returns only PR configs."""
        configs = svc.list_configs(trigger=TriggerType.PR)
        assert all(c.trigger == TriggerType.PR for c in configs)
        assert len(configs) == 1

    def test_list_configs_filter_schedule(self, svc):
        """list_configs with trigger=SCHEDULE returns only SCHEDULE configs."""
        configs = svc.list_configs(trigger=TriggerType.SCHEDULE)
        assert all(c.trigger == TriggerType.SCHEDULE for c in configs)
        assert len(configs) == 1

    def test_list_configs_filter_manual(self, svc):
        """list_configs with trigger=MANUAL returns no configs (none seeded)."""
        configs = svc.list_configs(trigger=TriggerType.MANUAL)
        assert len(configs) == 0

    def test_get_config_existing(self, svc):
        """get_config returns the config when it exists."""
        config = svc.get_config("PIPE-001")
        assert config is not None
        assert config.id == "PIPE-001"

    def test_get_config_not_found(self, svc):
        """get_config returns None for unknown ID."""
        config = svc.get_config("PIPE-999")
        assert config is None

    def test_create_config(self, svc):
        """create_config creates a new config with generated ID."""
        from app.schemas.cicd_pipeline import PipelineConfigCreateRequest

        req = PipelineConfigCreateRequest(
            name="New Pipeline",
            description="A new test pipeline",
            trigger=TriggerType.MANUAL,
            branch_pattern="release/*",
            stages=[],
            env_vars={"MY_VAR": "my_val"},
            timeout_minutes=30,
            retry_config=RetryConfig(max_retries=3, retry_delay_seconds=60),
        )
        config = svc.create_config(req)
        assert config.name == "New Pipeline"
        assert config.trigger == TriggerType.MANUAL
        assert config.id.startswith("PIPE-")
        assert config.env_vars["MY_VAR"] == "my_val"
        assert config.timeout_minutes == 30

    def test_create_config_with_stages(self, svc):
        """create_config with stages preserves stage definitions."""
        from app.schemas.cicd_pipeline import PipelineConfigCreateRequest

        stages = [
            StageConfig(
                stage=PipelineStage.BUILD,
                name="Build",
                commands=["make build"],
                timeout_minutes=10,
            ),
            StageConfig(
                stage=PipelineStage.UNIT_TEST,
                name="Tests",
                commands=["make test"],
                timeout_minutes=15,
                depends_on=[PipelineStage.BUILD],
            ),
        ]
        req = PipelineConfigCreateRequest(
            name="Staged Pipeline",
            trigger=TriggerType.PUSH,
            stages=stages,
        )
        config = svc.create_config(req)
        assert len(config.stages) == 2
        assert config.stages[0].stage == PipelineStage.BUILD
        assert config.stages[1].depends_on == [PipelineStage.BUILD]

    def test_update_config(self, svc):
        """update_config modifies specified fields."""
        from app.schemas.cicd_pipeline import PipelineConfigUpdateRequest

        req = PipelineConfigUpdateRequest(name="Updated Name", timeout_minutes=90)
        updated = svc.update_config("PIPE-001", req)
        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.timeout_minutes == 90
        # Unchanged fields remain
        assert updated.trigger == TriggerType.PUSH

    def test_update_config_not_found(self, svc):
        """update_config returns None for unknown ID."""
        from app.schemas.cicd_pipeline import PipelineConfigUpdateRequest

        req = PipelineConfigUpdateRequest(name="X")
        result = svc.update_config("PIPE-999", req)
        assert result is None

    def test_update_config_updated_at(self, svc):
        """update_config refreshes updated_at timestamp."""
        from app.schemas.cicd_pipeline import PipelineConfigUpdateRequest

        original = svc.get_config("PIPE-001")
        assert original is not None
        req = PipelineConfigUpdateRequest(description="New description")
        updated = svc.update_config("PIPE-001", req)
        assert updated is not None
        assert updated.updated_at >= original.updated_at

    def test_delete_config(self, svc):
        """delete_config removes the config and associated runs."""
        assert svc.delete_config("PIPE-002") is True
        assert svc.get_config("PIPE-002") is None
        assert len(svc.list_runs(config_id="PIPE-002")) == 0

    def test_delete_config_not_found(self, svc):
        """delete_config returns False for unknown ID."""
        assert svc.delete_config("PIPE-999") is False

    def test_delete_config_does_not_affect_others(self, svc):
        """Deleting one config leaves others intact."""
        svc.delete_config("PIPE-002")
        assert svc.get_config("PIPE-001") is not None
        assert svc.get_config("PIPE-003") is not None

    def test_create_then_get(self, svc):
        """Creating a config and fetching it returns the same data."""
        from app.schemas.cicd_pipeline import PipelineConfigCreateRequest

        req = PipelineConfigCreateRequest(
            name="Round Trip",
            trigger=TriggerType.PR,
        )
        created = svc.create_config(req)
        fetched = svc.get_config(created.id)
        assert fetched is not None
        assert fetched.name == created.name
        assert fetched.id == created.id


# ===========================================================================
# RUN OPERATIONS - SERVICE LAYER
# ===========================================================================


class TestRunOperationsService:
    """Test run operations directly on the service."""

    def test_list_runs_all(self, svc):
        """list_runs without filter returns seed runs (up to limit)."""
        runs = svc.list_runs(limit=200)
        assert len(runs) == 12

    def test_list_runs_filter_by_config(self, svc):
        """list_runs filters by config_id."""
        runs = svc.list_runs(config_id="PIPE-001")
        assert all(r.config_id == "PIPE-001" for r in runs)

    def test_list_runs_filter_by_status_passed(self, svc):
        """list_runs filters by PASSED status."""
        runs = svc.list_runs(status=PipelineStatus.PASSED, limit=200)
        assert all(r.status == PipelineStatus.PASSED for r in runs)

    def test_list_runs_filter_by_status_failed(self, svc):
        """list_runs filters by FAILED status."""
        runs = svc.list_runs(status=PipelineStatus.FAILED, limit=200)
        assert all(r.status == PipelineStatus.FAILED for r in runs)
        assert len(runs) > 0

    def test_list_runs_filter_by_branch(self, svc):
        """list_runs filters by branch."""
        runs = svc.list_runs(branch="main", limit=200)
        assert all(r.branch == "main" for r in runs)

    def test_list_runs_combined_filters(self, svc):
        """list_runs supports multiple filters simultaneously."""
        runs = svc.list_runs(config_id="PIPE-001", status=PipelineStatus.PASSED, limit=200)
        assert all(r.config_id == "PIPE-001" and r.status == PipelineStatus.PASSED for r in runs)

    def test_list_runs_limit(self, svc):
        """list_runs respects limit parameter."""
        runs = svc.list_runs(limit=3)
        assert len(runs) <= 3

    def test_list_runs_sorted_newest_first(self, svc):
        """list_runs returns runs sorted by started_at descending."""
        runs = svc.list_runs(limit=200)
        for i in range(len(runs) - 1):
            assert runs[i].started_at >= runs[i + 1].started_at

    def test_get_run_existing(self, svc):
        """get_run returns a run when it exists."""
        run = svc.get_run("RUN-001")
        assert run is not None
        assert run.id == "RUN-001"

    def test_get_run_not_found(self, svc):
        """get_run returns None for unknown ID."""
        run = svc.get_run("RUN-999")
        assert run is None

    def test_trigger_pipeline(self, svc):
        """trigger_pipeline creates a new run for an existing config."""
        run = svc.trigger_pipeline(config_id="PIPE-001", branch="develop", commit_sha="abc123")
        assert run is not None
        assert run.config_id == "PIPE-001"
        assert run.branch == "develop"
        assert run.commit_sha == "abc123"
        assert run.trigger_type == TriggerType.MANUAL
        assert run.status in (PipelineStatus.PASSED, PipelineStatus.FAILED)
        assert len(run.stages_results) > 0

    def test_trigger_pipeline_not_found(self, svc):
        """trigger_pipeline returns None for unknown config."""
        run = svc.trigger_pipeline(config_id="PIPE-999")
        assert run is None

    def test_trigger_pipeline_generates_commit_sha(self, svc):
        """trigger_pipeline with HEAD generates a commit SHA."""
        run = svc.trigger_pipeline(config_id="PIPE-002", commit_sha="HEAD")
        assert run is not None
        assert run.commit_sha != "HEAD"
        assert len(run.commit_sha) == 12

    def test_trigger_pipeline_adds_to_runs(self, svc):
        """After triggering, the new run is retrievable."""
        run = svc.trigger_pipeline(config_id="PIPE-001")
        assert run is not None
        fetched = svc.get_run(run.id)
        assert fetched is not None
        assert fetched.id == run.id

    def test_trigger_pipeline_stage_results_match_config(self, svc):
        """Triggered run has stage results for each config stage."""
        config = svc.get_config("PIPE-002")
        assert config is not None
        run = svc.trigger_pipeline(config_id="PIPE-002")
        assert run is not None
        assert len(run.stages_results) == len(config.stages)

    def test_trigger_pipeline_triggered_by(self, svc):
        """trigger_pipeline records who triggered the run."""
        run = svc.trigger_pipeline(config_id="PIPE-001", triggered_by="test-user")
        assert run is not None
        assert run.triggered_by == "test-user"

    def test_trigger_pipeline_duration_positive(self, svc):
        """Triggered run has positive duration."""
        run = svc.trigger_pipeline(config_id="PIPE-001")
        assert run is not None
        assert run.duration_seconds > 0

    def test_trigger_pipeline_timestamps(self, svc):
        """Triggered run has valid started_at and completed_at."""
        run = svc.trigger_pipeline(config_id="PIPE-001")
        assert run is not None
        assert run.started_at is not None
        assert run.completed_at is not None
        assert run.completed_at >= run.started_at


# ===========================================================================
# METRICS - SERVICE LAYER
# ===========================================================================


class TestMetricsService:
    """Test metrics computation on the service."""

    def test_aggregate_metrics(self, svc):
        """get_metrics returns aggregate metrics across all runs."""
        metrics = svc.get_metrics()
        assert metrics.total_runs == 12
        assert metrics.success_rate > 0
        assert metrics.avg_duration_seconds > 0

    def test_per_config_metrics(self, svc):
        """get_metrics scoped to a config returns correct total."""
        metrics = svc.get_metrics(config_id="PIPE-001")
        assert metrics.total_runs == 6

    def test_metrics_success_rate_bounded(self, svc):
        """Success rate is between 0 and 100."""
        metrics = svc.get_metrics()
        assert 0 <= metrics.success_rate <= 100

    def test_metrics_by_stage_success(self, svc):
        """by_stage_success contains per-stage success rates."""
        metrics = svc.get_metrics()
        assert len(metrics.by_stage_success) > 0
        for rate in metrics.by_stage_success.values():
            assert 0 <= rate <= 100

    def test_metrics_slowest_stages(self, svc):
        """slowest_stages returns up to 5 stage names."""
        metrics = svc.get_metrics()
        assert len(metrics.slowest_stages) <= 5
        assert all(isinstance(s, str) for s in metrics.slowest_stages)

    def test_metrics_most_failed_stages(self, svc):
        """most_failed_stages identifies stages with failures."""
        metrics = svc.get_metrics()
        assert isinstance(metrics.most_failed_stages, list)

    def test_metrics_runs_per_day(self, svc):
        """runs_per_day_avg is a positive number."""
        metrics = svc.get_metrics()
        assert metrics.runs_per_day_avg > 0

    def test_metrics_empty_config(self, svc):
        """Metrics for a config with no runs returns zeros."""
        from app.schemas.cicd_pipeline import PipelineConfigCreateRequest

        req = PipelineConfigCreateRequest(name="Empty", trigger=TriggerType.MANUAL)
        config = svc.create_config(req)
        metrics = svc.get_metrics(config_id=config.id)
        assert metrics.total_runs == 0
        assert metrics.success_rate == 0
        assert metrics.avg_duration_seconds == 0

    def test_metrics_flaky_count(self, svc):
        """Aggregate metrics include flaky test count."""
        metrics = svc.get_metrics()
        assert isinstance(metrics.flaky_tests_count, int)
        assert metrics.flaky_tests_count >= 0


# ===========================================================================
# OPTIMIZATIONS - SERVICE LAYER
# ===========================================================================


class TestOptimizationsService:
    """Test optimization analysis on the service."""

    def test_optimizations_for_main(self, svc):
        """analyze_optimizations returns recommendations for PIPE-001."""
        opts = svc.analyze_optimizations("PIPE-001")
        assert len(opts) > 0

    def test_optimizations_have_recommendations(self, svc):
        """Each optimization has a non-empty recommendation string."""
        opts = svc.analyze_optimizations("PIPE-001")
        for opt in opts:
            assert opt.recommendation
            assert len(opt.recommendation) > 0

    def test_optimizations_confidence_bounded(self, svc):
        """Optimization confidence is between 0.0 and 1.0."""
        opts = svc.analyze_optimizations("PIPE-001")
        for opt in opts:
            assert 0.0 <= opt.confidence <= 1.0

    def test_optimizations_savings_nonneg(self, svc):
        """Estimated savings are non-negative."""
        opts = svc.analyze_optimizations("PIPE-001")
        for opt in opts:
            assert opt.estimated_savings_seconds >= 0

    def test_optimizations_cache_recommendation(self, svc):
        """Cache recommendation appears for pipelines with install commands."""
        opts = svc.analyze_optimizations("PIPE-001")
        recommendations = " ".join(o.recommendation for o in opts)
        assert "cache" in recommendations.lower() or "Cache" in recommendations

    def test_optimizations_skip_unchanged(self, svc):
        """Skip-unchanged-stages recommendation appears for pipelines with >3 stages."""
        opts = svc.analyze_optimizations("PIPE-001")
        recommendations = " ".join(o.recommendation for o in opts)
        assert "skip" in recommendations.lower() or "change" in recommendations.lower()

    def test_optimizations_for_nonexistent(self, svc):
        """analyze_optimizations returns empty list for unknown config."""
        opts = svc.analyze_optimizations("PIPE-999")
        assert opts == []

    def test_optimizations_affected_stages(self, svc):
        """Each optimization lists affected stages."""
        opts = svc.analyze_optimizations("PIPE-001")
        for opt in opts:
            assert isinstance(opt.affected_stages, list)


# ===========================================================================
# DURATION ESTIMATION - SERVICE LAYER
# ===========================================================================


class TestDurationEstimationService:
    """Test duration estimation on the service."""

    def test_duration_estimate_main(self, svc):
        """estimate_pipeline_duration returns estimates for PIPE-001."""
        est = svc.estimate_pipeline_duration("PIPE-001")
        assert est.config_id == "PIPE-001"
        assert est.sample_size > 0
        assert est.p50_seconds > 0
        assert est.p95_seconds > 0

    def test_duration_estimate_p95_gte_p50(self, svc):
        """p95 duration >= p50 duration."""
        est = svc.estimate_pipeline_duration("PIPE-001")
        assert est.p95_seconds >= est.p50_seconds

    def test_duration_estimate_no_passed_runs(self, svc):
        """Duration estimate for config with no passed runs returns zeros."""
        # Delete PIPE-003's passing run by re-seeding would be complex,
        # so create a new config with no runs
        from app.schemas.cicd_pipeline import PipelineConfigCreateRequest

        req = PipelineConfigCreateRequest(name="No Runs", trigger=TriggerType.MANUAL)
        config = svc.create_config(req)
        est = svc.estimate_pipeline_duration(config.id)
        assert est.sample_size == 0
        assert est.p50_seconds == 0
        assert est.p95_seconds == 0


# ===========================================================================
# FLAKY STAGE DETECTION - SERVICE LAYER
# ===========================================================================


class TestFlakyStageDetectionService:
    """Test flaky stage detection on the service."""

    def test_flaky_stages_returns_list(self, svc):
        """get_flaky_stages returns a list of FlakyStageEntry."""
        flaky = svc.get_flaky_stages()
        assert isinstance(flaky, list)

    def test_flaky_stages_have_valid_rates(self, svc):
        """Flaky stage entries have rates in [0.05, 0.50]."""
        flaky = svc.get_flaky_stages()
        for entry in flaky:
            assert 0.05 <= entry.flaky_rate <= 0.50

    def test_flaky_stages_sorted_by_rate(self, svc):
        """Flaky stages are sorted by flaky_rate descending."""
        flaky = svc.get_flaky_stages()
        for i in range(len(flaky) - 1):
            assert flaky[i].flaky_rate >= flaky[i + 1].flaky_rate

    def test_flaky_stages_have_counts(self, svc):
        """Each flaky stage entry has total_runs >= 2 and failed_runs > 0."""
        flaky = svc.get_flaky_stages()
        for entry in flaky:
            assert entry.total_runs >= 2
            assert entry.failed_runs > 0


# ===========================================================================
# STATS - SERVICE LAYER
# ===========================================================================


class TestStatsService:
    """Test stats method on the service."""

    def test_stats_keys(self, svc):
        """get_stats returns total_configs and total_runs."""
        stats = svc.get_stats()
        assert "total_configs" in stats
        assert "total_runs" in stats

    def test_stats_values(self, svc):
        """get_stats values match actual counts."""
        stats = svc.get_stats()
        assert stats["total_configs"] == 3
        assert stats["total_runs"] == 12


# ===========================================================================
# API ENDPOINT TESTS
# ===========================================================================


class TestListConfigsAPI:
    """Test GET /configs endpoint."""

    @pytest.mark.anyio
    async def test_list_configs(self):
        """GET /configs returns all configs."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/configs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    @pytest.mark.anyio
    async def test_list_configs_filter_trigger(self):
        """GET /configs?trigger=PUSH filters by trigger."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/configs", params={"trigger": "PUSH"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["trigger"] == "PUSH"

    @pytest.mark.anyio
    async def test_list_configs_filter_no_match(self):
        """GET /configs?trigger=MANUAL returns empty when none match."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/configs", params={"trigger": "MANUAL"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0


class TestGetConfigAPI:
    """Test GET /configs/{config_id} endpoint."""

    @pytest.mark.anyio
    async def test_get_config(self):
        """GET /configs/PIPE-001 returns the config."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/configs/PIPE-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PIPE-001"
        assert data["name"] == "Main CI/CD Pipeline"

    @pytest.mark.anyio
    async def test_get_config_not_found(self):
        """GET /configs/PIPE-999 returns 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/configs/PIPE-999")
        assert resp.status_code == 404


class TestCreateConfigAPI:
    """Test POST /configs endpoint."""

    @pytest.mark.anyio
    async def test_create_config(self):
        """POST /configs creates a new config."""
        payload = _create_config_payload(name="API Created Pipeline", trigger="MANUAL")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"{API_PREFIX}/configs", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "API Created Pipeline"
        assert data["trigger"] == "MANUAL"
        assert data["id"].startswith("PIPE-")

    @pytest.mark.anyio
    async def test_create_config_with_stages(self):
        """POST /configs creates config with stage definitions."""
        stages = [_make_stage("BUILD", "Build"), _make_stage("LINT", "Lint", depends_on=["BUILD"])]
        payload = _create_config_payload(name="Staged", stages=stages)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"{API_PREFIX}/configs", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["stages"]) == 2

    @pytest.mark.anyio
    async def test_create_config_minimal(self):
        """POST /configs with minimal fields succeeds."""
        payload = {"name": "Minimal", "trigger": "PUSH"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"{API_PREFIX}/configs", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_create_config_missing_name(self):
        """POST /configs without name returns 422."""
        payload = {"trigger": "PUSH"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"{API_PREFIX}/configs", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_config_invalid_trigger(self):
        """POST /configs with invalid trigger returns 422."""
        payload = {"name": "Bad Trigger", "trigger": "INVALID_TRIGGER"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"{API_PREFIX}/configs", json=payload)
        assert resp.status_code == 422


class TestUpdateConfigAPI:
    """Test PUT /configs/{config_id} endpoint."""

    @pytest.mark.anyio
    async def test_update_config(self):
        """PUT /configs/PIPE-001 updates the config."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.put(
                f"{API_PREFIX}/configs/PIPE-001",
                json={"name": "Updated Pipeline"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Pipeline"
        assert data["id"] == "PIPE-001"

    @pytest.mark.anyio
    async def test_update_config_partial(self):
        """PUT with partial update preserves unchanged fields."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.put(
                f"{API_PREFIX}/configs/PIPE-001",
                json={"description": "New desc"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == "New desc"
        assert data["name"] == "Main CI/CD Pipeline"

    @pytest.mark.anyio
    async def test_update_config_not_found(self):
        """PUT /configs/PIPE-999 returns 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.put(
                f"{API_PREFIX}/configs/PIPE-999",
                json={"name": "X"},
            )
        assert resp.status_code == 404


class TestDeleteConfigAPI:
    """Test DELETE /configs/{config_id} endpoint."""

    @pytest.mark.anyio
    async def test_delete_config(self):
        """DELETE /configs/PIPE-002 returns 204."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.delete(f"{API_PREFIX}/configs/PIPE-002")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_config_not_found(self):
        """DELETE /configs/PIPE-999 returns 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.delete(f"{API_PREFIX}/configs/PIPE-999")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_config_removes_runs(self):
        """After deleting a config, its runs are also removed."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            await ac.delete(f"{API_PREFIX}/configs/PIPE-002")
            resp = await ac.get(f"{API_PREFIX}/runs", params={"config_id": "PIPE-002"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0


class TestTriggerPipelineAPI:
    """Test POST /configs/{config_id}/trigger endpoint."""

    @pytest.mark.anyio
    async def test_trigger_pipeline(self):
        """POST trigger creates a new run."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                f"{API_PREFIX}/configs/PIPE-001/trigger",
                json={"branch": "develop", "commit_sha": "abc123", "triggered_by": "tester"},
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["config_id"] == "PIPE-001"
        assert data["branch"] == "develop"
        assert data["triggered_by"] == "tester"

    @pytest.mark.anyio
    async def test_trigger_pipeline_defaults(self):
        """POST trigger with default body works."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                f"{API_PREFIX}/configs/PIPE-001/trigger",
                json={},
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["branch"] == "main"
        assert data["triggered_by"] == "manual"

    @pytest.mark.anyio
    async def test_trigger_pipeline_not_found(self):
        """POST trigger for unknown config returns 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                f"{API_PREFIX}/configs/PIPE-999/trigger",
                json={},
            )
        assert resp.status_code == 404


class TestListRunsAPI:
    """Test GET /runs endpoint."""

    @pytest.mark.anyio
    async def test_list_runs_all(self):
        """GET /runs returns all seed runs."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_runs_filter_config(self):
        """GET /runs?config_id=PIPE-001 filters by config."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/runs", params={"config_id": "PIPE-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(r["config_id"] == "PIPE-001" for r in data["items"])

    @pytest.mark.anyio
    async def test_list_runs_filter_status(self):
        """GET /runs?status=FAILED filters by status."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/runs", params={"status": "FAILED"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(r["status"] == "FAILED" for r in data["items"])

    @pytest.mark.anyio
    async def test_list_runs_filter_branch(self):
        """GET /runs?branch=main filters by branch."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/runs", params={"branch": "main"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(r["branch"] == "main" for r in data["items"])

    @pytest.mark.anyio
    async def test_list_runs_limit(self):
        """GET /runs?limit=3 returns at most 3 runs."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/runs", params={"limit": 3})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 3

    @pytest.mark.anyio
    async def test_list_runs_combined_filters(self):
        """GET /runs with multiple filters works."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(
                f"{API_PREFIX}/runs",
                params={"config_id": "PIPE-001", "status": "PASSED", "branch": "main"},
            )
        assert resp.status_code == 200
        data = resp.json()
        for r in data["items"]:
            assert r["config_id"] == "PIPE-001"
            assert r["status"] == "PASSED"
            assert r["branch"] == "main"


class TestGetRunAPI:
    """Test GET /runs/{run_id} endpoint."""

    @pytest.mark.anyio
    async def test_get_run(self):
        """GET /runs/RUN-001 returns the run."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/runs/RUN-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RUN-001"

    @pytest.mark.anyio
    async def test_get_run_not_found(self):
        """GET /runs/RUN-999 returns 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/runs/RUN-999")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_run_has_stage_results(self):
        """GET /runs/RUN-001 includes stage results."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/runs/RUN-001")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["stages_results"]) > 0


class TestAggregateMetricsAPI:
    """Test GET /metrics endpoint."""

    @pytest.mark.anyio
    async def test_aggregate_metrics(self):
        """GET /metrics returns aggregate metrics."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_runs"] == 12
        assert "success_rate" in data
        assert "avg_duration_seconds" in data


class TestConfigMetricsAPI:
    """Test GET /configs/{config_id}/metrics endpoint."""

    @pytest.mark.anyio
    async def test_config_metrics(self):
        """GET /configs/PIPE-001/metrics returns scoped metrics."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/configs/PIPE-001/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_runs"] == 6

    @pytest.mark.anyio
    async def test_config_metrics_not_found(self):
        """GET /configs/PIPE-999/metrics returns 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/configs/PIPE-999/metrics")
        assert resp.status_code == 404


class TestOptimizationsAPI:
    """Test GET /configs/{config_id}/optimizations endpoint."""

    @pytest.mark.anyio
    async def test_optimizations(self):
        """GET /configs/PIPE-001/optimizations returns recommendations."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/configs/PIPE-001/optimizations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["config_id"] == "PIPE-001"
        assert len(data["optimizations"]) > 0
        assert data["total_estimated_savings_seconds"] > 0

    @pytest.mark.anyio
    async def test_optimizations_not_found(self):
        """GET /configs/PIPE-999/optimizations returns 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/configs/PIPE-999/optimizations")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_optimizations_structure(self):
        """Each optimization has recommendation, savings, affected_stages, confidence."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/configs/PIPE-001/optimizations")
        assert resp.status_code == 200
        data = resp.json()
        for opt in data["optimizations"]:
            assert "recommendation" in opt
            assert "estimated_savings_seconds" in opt
            assert "affected_stages" in opt
            assert "confidence" in opt


class TestDurationEstimateAPI:
    """Test GET /configs/{config_id}/duration-estimate endpoint."""

    @pytest.mark.anyio
    async def test_duration_estimate(self):
        """GET /configs/PIPE-001/duration-estimate returns estimates."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/configs/PIPE-001/duration-estimate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["config_id"] == "PIPE-001"
        assert data["sample_size"] > 0
        assert data["p50_seconds"] > 0
        assert data["p95_seconds"] >= data["p50_seconds"]

    @pytest.mark.anyio
    async def test_duration_estimate_not_found(self):
        """GET /configs/PIPE-999/duration-estimate returns 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/configs/PIPE-999/duration-estimate")
        assert resp.status_code == 404


class TestFlakyStagesAPI:
    """Test GET /flaky-stages endpoint."""

    @pytest.mark.anyio
    async def test_flaky_stages(self):
        """GET /flaky-stages returns flaky stage detection results."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/flaky-stages")
        assert resp.status_code == 200
        data = resp.json()
        assert "flaky_stages" in data
        assert "total" in data
        assert data["total"] == len(data["flaky_stages"])

    @pytest.mark.anyio
    async def test_flaky_stages_structure(self):
        """Each flaky stage entry has stage, flaky_rate, total_runs, failed_runs."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/flaky-stages")
        assert resp.status_code == 200
        data = resp.json()
        for entry in data["flaky_stages"]:
            assert "stage" in entry
            assert "flaky_rate" in entry
            assert "total_runs" in entry
            assert "failed_runs" in entry


class TestStagesAPI:
    """Test GET /stages endpoint."""

    @pytest.mark.anyio
    async def test_list_stages(self):
        """GET /stages returns all pipeline stage enum values."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/stages")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == len(PipelineStage)
        values = {s["value"] for s in data}
        assert "BUILD" in values
        assert "DEPLOY_PRODUCTION" in values

    @pytest.mark.anyio
    async def test_list_stages_structure(self):
        """Each stage has value and label."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/stages")
        assert resp.status_code == 200
        data = resp.json()
        for stage in data:
            assert "value" in stage
            assert "label" in stage


# ===========================================================================
# EDGE CASES AND ERROR HANDLING
# ===========================================================================


class TestEdgeCases:
    """Edge cases and error handling."""

    @pytest.mark.anyio
    async def test_update_with_empty_body(self):
        """PUT with empty body is valid (no fields updated)."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.put(f"{API_PREFIX}/configs/PIPE-001", json={})
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_then_trigger_then_get_run(self):
        """Full workflow: create config, trigger run, fetch run."""
        payload = _create_config_payload(
            name="Workflow Test",
            trigger="MANUAL",
            stages=[_make_stage("BUILD", "Build")],
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            create_resp = await ac.post(f"{API_PREFIX}/configs", json=payload)
            assert create_resp.status_code == 201
            config_id = create_resp.json()["id"]

            trigger_resp = await ac.post(
                f"{API_PREFIX}/configs/{config_id}/trigger",
                json={"branch": "feature/test", "commit_sha": "deadbeef1234"},
            )
            assert trigger_resp.status_code == 201
            run_id = trigger_resp.json()["id"]

            get_resp = await ac.get(f"{API_PREFIX}/runs/{run_id}")
            assert get_resp.status_code == 200
            run_data = get_resp.json()
            assert run_data["config_id"] == config_id
            assert run_data["branch"] == "feature/test"

    @pytest.mark.anyio
    async def test_delete_then_trigger_returns_404(self):
        """Triggering a deleted config returns 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            await ac.delete(f"{API_PREFIX}/configs/PIPE-002")
            resp = await ac.post(f"{API_PREFIX}/configs/PIPE-002/trigger", json={})
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_then_get_returns_404(self):
        """Getting a deleted config returns 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            await ac.delete(f"{API_PREFIX}/configs/PIPE-002")
            resp = await ac.get(f"{API_PREFIX}/configs/PIPE-002")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_trigger_with_custom_commit_sha(self):
        """Triggering with a custom commit SHA preserves it."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                f"{API_PREFIX}/configs/PIPE-001/trigger",
                json={"commit_sha": "custom12sha3"},
            )
        assert resp.status_code == 201
        assert resp.json()["commit_sha"] == "custom12sha3"

    @pytest.mark.anyio
    async def test_list_runs_for_nonexistent_config(self):
        """Listing runs for a nonexistent config returns empty list."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/runs", params={"config_id": "PIPE-999"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_list_runs_for_nonexistent_branch(self):
        """Listing runs for a nonexistent branch returns empty list."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/runs", params={"branch": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_service_reset(self):
        """reset_cicd_pipeline_service clears the singleton."""
        svc1 = get_cicd_pipeline_service()
        reset_cicd_pipeline_service()
        svc2 = get_cicd_pipeline_service()
        assert svc1 is not svc2

    def test_multiple_creates_unique_ids(self, svc):
        """Creating multiple configs produces unique IDs."""
        from app.schemas.cicd_pipeline import PipelineConfigCreateRequest

        ids = set()
        for i in range(5):
            req = PipelineConfigCreateRequest(name=f"Pipeline {i}", trigger=TriggerType.MANUAL)
            config = svc.create_config(req)
            ids.add(config.id)
        assert len(ids) == 5

    def test_multiple_triggers_unique_run_ids(self, svc):
        """Triggering multiple runs produces unique run IDs."""
        ids = set()
        for _ in range(5):
            run = svc.trigger_pipeline(config_id="PIPE-002")
            assert run is not None
            ids.add(run.id)
        assert len(ids) == 5

    @pytest.mark.anyio
    async def test_update_config_trigger_type(self):
        """Updating trigger type works."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.put(
                f"{API_PREFIX}/configs/PIPE-001",
                json={"trigger": "SCHEDULE"},
            )
        assert resp.status_code == 200
        assert resp.json()["trigger"] == "SCHEDULE"

    @pytest.mark.anyio
    async def test_update_config_env_vars(self):
        """Updating env_vars works."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.put(
                f"{API_PREFIX}/configs/PIPE-001",
                json={"env_vars": {"NEW_VAR": "new_val"}},
            )
        assert resp.status_code == 200
        assert resp.json()["env_vars"]["NEW_VAR"] == "new_val"

    @pytest.mark.anyio
    async def test_update_config_stages(self):
        """Updating stages replaces the stage list."""
        new_stages = [_make_stage("BUILD", "Build"), _make_stage("LINT", "Lint")]
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.put(
                f"{API_PREFIX}/configs/PIPE-001",
                json={"stages": new_stages},
            )
        assert resp.status_code == 200
        assert len(resp.json()["stages"]) == 2

    @pytest.mark.anyio
    async def test_update_config_retry_config(self):
        """Updating retry_config works."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.put(
                f"{API_PREFIX}/configs/PIPE-001",
                json={"retry_config": {"max_retries": 5, "retry_delay_seconds": 120, "retry_on_stages": []}},
            )
        assert resp.status_code == 200
        assert resp.json()["retry_config"]["max_retries"] == 5

    @pytest.mark.anyio
    async def test_run_stage_result_fields(self):
        """Stage results have expected fields."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/runs/RUN-001")
        assert resp.status_code == 200
        sr = resp.json()["stages_results"][0]
        assert "stage" in sr
        assert "status" in sr
        assert "duration_seconds" in sr
        assert "output_summary" in sr

    @pytest.mark.anyio
    async def test_config_list_after_create_and_delete(self):
        """Config count is correct after creates and deletes."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # Start with 3
            resp = await ac.get(f"{API_PREFIX}/configs")
            assert resp.json()["total"] == 3

            # Create one -> 4
            payload = _create_config_payload(name="Extra")
            await ac.post(f"{API_PREFIX}/configs", json=payload)
            resp = await ac.get(f"{API_PREFIX}/configs")
            assert resp.json()["total"] == 4

            # Delete one -> 3
            await ac.delete(f"{API_PREFIX}/configs/PIPE-003")
            resp = await ac.get(f"{API_PREFIX}/configs")
            assert resp.json()["total"] == 3

    @pytest.mark.anyio
    async def test_optimizations_for_pr_pipeline(self):
        """Optimizations work for PIPE-002 (PR pipeline)."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/configs/PIPE-002/optimizations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["config_id"] == "PIPE-002"

    @pytest.mark.anyio
    async def test_optimizations_for_security_pipeline(self):
        """Optimizations work for PIPE-003 (security pipeline)."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/configs/PIPE-003/optimizations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["config_id"] == "PIPE-003"

    @pytest.mark.anyio
    async def test_duration_estimate_pr_pipeline(self):
        """Duration estimate works for PIPE-002."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/configs/PIPE-002/duration-estimate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["config_id"] == "PIPE-002"

    @pytest.mark.anyio
    async def test_config_metrics_pr_pipeline(self):
        """Metrics work for PIPE-002."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/configs/PIPE-002/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_runs"] == 4

    @pytest.mark.anyio
    async def test_config_metrics_security_pipeline(self):
        """Metrics work for PIPE-003."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/configs/PIPE-003/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_runs"] == 2

    def test_seed_run_commit_sha_format(self, svc):
        """Seed runs have 12-character hex commit SHAs."""
        for run in svc.list_runs(limit=200):
            assert len(run.commit_sha) == 12

    def test_seed_run_durations_positive(self, svc):
        """All seed runs have positive total duration."""
        for run in svc.list_runs(limit=200):
            assert run.duration_seconds > 0

    def test_seed_run_triggered_by_populated(self, svc):
        """All seed runs have non-empty triggered_by."""
        for run in svc.list_runs(limit=200):
            assert run.triggered_by

    def test_passed_run_no_failed_stages(self, svc):
        """A passed run has no FAILED stages (except allow_failure)."""
        run = svc.get_run("RUN-001")
        assert run is not None
        assert run.status == PipelineStatus.PASSED
        for sr in run.stages_results:
            assert sr.status != PipelineStatus.FAILED or sr.stage == PipelineStage.SECURITY_SCAN

    def test_failed_run_has_error_message(self, svc):
        """A failed run's failed stage has an error message."""
        run = svc.get_run("RUN-003")
        assert run is not None
        assert run.status == PipelineStatus.FAILED
        failed_stages = [sr for sr in run.stages_results if sr.status == PipelineStatus.FAILED]
        assert len(failed_stages) > 0
        for fs in failed_stages:
            assert fs.error_message is not None

    @pytest.mark.anyio
    async def test_limit_validation_min(self):
        """GET /runs?limit=0 returns 422 (below minimum)."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/runs", params={"limit": 0})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_limit_validation_max(self):
        """GET /runs?limit=201 returns 422 (above maximum)."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/runs", params={"limit": 201})
        assert resp.status_code == 422
