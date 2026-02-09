"""Pydantic schemas for CI/CD Pipeline Configuration & Management (DEVOPS-5).

Defines pipeline configurations, stage definitions, run results, metrics,
and optimization recommendations for clinical trial platform CI/CD management.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class PipelineStage(str, Enum):
    """Stages that can appear in a CI/CD pipeline."""

    BUILD = "BUILD"
    LINT = "LINT"
    TYPECHECK = "TYPECHECK"
    UNIT_TEST = "UNIT_TEST"
    INTEGRATION_TEST = "INTEGRATION_TEST"
    SECURITY_SCAN = "SECURITY_SCAN"
    DOCKER_BUILD = "DOCKER_BUILD"
    DEPLOY_STAGING = "DEPLOY_STAGING"
    E2E_TEST = "E2E_TEST"
    DEPLOY_PRODUCTION = "DEPLOY_PRODUCTION"
    POST_DEPLOY_VERIFY = "POST_DEPLOY_VERIFY"


class PipelineStatus(str, Enum):
    """Status of a pipeline run or individual stage."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


class TriggerType(str, Enum):
    """How a pipeline run is triggered."""

    PUSH = "PUSH"
    PR = "PR"
    SCHEDULE = "SCHEDULE"
    MANUAL = "MANUAL"


# ---------------------------------------------------------------------------
# Stage Configuration
# ---------------------------------------------------------------------------


class StageConfig(BaseModel):
    """Configuration for a single pipeline stage."""

    model_config = ConfigDict(populate_by_name=True)

    stage: PipelineStage = Field(description="The pipeline stage type")
    name: str = Field(description="Human-readable stage name")
    commands: list[str] = Field(default_factory=list, description="Commands to execute")
    timeout_minutes: int = Field(default=10, description="Max duration for this stage")
    depends_on: list[PipelineStage] = Field(
        default_factory=list, description="Stages that must complete before this one"
    )
    allow_failure: bool = Field(default=False, description="Whether stage failure is non-blocking")
    environment: str = Field(default="ci", description="Target environment for this stage")
    artifacts: list[str] = Field(default_factory=list, description="Artifact paths produced by this stage")


# ---------------------------------------------------------------------------
# Retry Configuration
# ---------------------------------------------------------------------------


class RetryConfig(BaseModel):
    """Retry configuration for pipeline runs."""

    model_config = ConfigDict(populate_by_name=True)

    max_retries: int = Field(default=2, description="Maximum number of retries")
    retry_delay_seconds: int = Field(default=30, description="Delay between retries in seconds")
    retry_on_stages: list[PipelineStage] = Field(
        default_factory=list, description="Stages eligible for retry"
    )


# ---------------------------------------------------------------------------
# Pipeline Configuration
# ---------------------------------------------------------------------------


class PipelineConfig(BaseModel):
    """Full configuration for a CI/CD pipeline."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(description="Unique pipeline configuration ID")
    name: str = Field(description="Pipeline name")
    description: str = Field(default="", description="Pipeline description")
    trigger: TriggerType = Field(description="How this pipeline is triggered")
    branch_pattern: str = Field(default="*", description="Branch pattern to match")
    stages: list[StageConfig] = Field(default_factory=list, description="Ordered stage definitions")
    env_vars: dict[str, str] = Field(default_factory=dict, description="Environment variables")
    timeout_minutes: int = Field(default=60, description="Overall pipeline timeout")
    retry_config: RetryConfig = Field(default_factory=RetryConfig, description="Retry settings")
    created_at: datetime = Field(description="When the config was created")
    updated_at: datetime = Field(description="When the config was last updated")


# ---------------------------------------------------------------------------
# Stage Result
# ---------------------------------------------------------------------------


class StageResult(BaseModel):
    """Result of a single stage execution."""

    model_config = ConfigDict(populate_by_name=True)

    stage: PipelineStage = Field(description="The stage that ran")
    status: PipelineStatus = Field(description="Outcome of the stage")
    started_at: datetime | None = Field(default=None, description="When the stage started")
    completed_at: datetime | None = Field(default=None, description="When the stage completed")
    duration_seconds: float = Field(default=0.0, description="Duration in seconds")
    output_summary: str = Field(default="", description="Summary of stage output")
    error_message: str | None = Field(default=None, description="Error message if failed")


# ---------------------------------------------------------------------------
# Pipeline Run
# ---------------------------------------------------------------------------


class PipelineRun(BaseModel):
    """Record of a single pipeline execution."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(description="Unique run ID")
    config_id: str = Field(description="Reference to the pipeline config")
    trigger_type: TriggerType = Field(description="How this run was triggered")
    branch: str = Field(description="Branch this run targeted")
    commit_sha: str = Field(description="Git commit SHA")
    status: PipelineStatus = Field(description="Overall run status")
    stages_results: list[StageResult] = Field(
        default_factory=list, description="Results for each stage"
    )
    started_at: datetime = Field(description="When the run started")
    completed_at: datetime | None = Field(default=None, description="When the run completed")
    duration_seconds: float = Field(default=0.0, description="Total duration in seconds")
    triggered_by: str = Field(default="system", description="Who or what triggered the run")


# ---------------------------------------------------------------------------
# Pipeline Metrics
# ---------------------------------------------------------------------------


class PipelineMetrics(BaseModel):
    """Aggregate metrics for pipeline performance analysis."""

    model_config = ConfigDict(populate_by_name=True)

    total_runs: int = Field(default=0, description="Total number of pipeline runs")
    success_rate: float = Field(default=0.0, description="Percentage of successful runs")
    avg_duration_seconds: float = Field(default=0.0, description="Average run duration")
    by_stage_success: dict[str, float] = Field(
        default_factory=dict, description="Success rate per stage"
    )
    slowest_stages: list[str] = Field(
        default_factory=list, description="Stages sorted by avg duration (slowest first)"
    )
    most_failed_stages: list[str] = Field(
        default_factory=list, description="Stages sorted by failure rate (most failed first)"
    )
    runs_per_day_avg: float = Field(default=0.0, description="Average runs per day")
    flaky_tests_count: int = Field(default=0, description="Number of flaky test detections")


# ---------------------------------------------------------------------------
# Pipeline Optimization
# ---------------------------------------------------------------------------


class PipelineOptimization(BaseModel):
    """An optimization recommendation for a pipeline."""

    model_config = ConfigDict(populate_by_name=True)

    recommendation: str = Field(description="Description of the recommendation")
    estimated_savings_seconds: float = Field(
        default=0.0, description="Estimated time savings per run"
    )
    affected_stages: list[str] = Field(
        default_factory=list, description="Stages affected by the recommendation"
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence score 0.0..1.0"
    )


# ---------------------------------------------------------------------------
# Request / Response wrappers
# ---------------------------------------------------------------------------


class PipelineConfigCreateRequest(BaseModel):
    """Request body for creating a pipeline config."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(description="Pipeline name")
    description: str = Field(default="", description="Pipeline description")
    trigger: TriggerType = Field(description="Trigger type")
    branch_pattern: str = Field(default="*", description="Branch glob pattern")
    stages: list[StageConfig] = Field(default_factory=list, description="Stage definitions")
    env_vars: dict[str, str] = Field(default_factory=dict, description="Environment variables")
    timeout_minutes: int = Field(default=60, description="Overall timeout")
    retry_config: RetryConfig = Field(default_factory=RetryConfig, description="Retry settings")


class PipelineConfigUpdateRequest(BaseModel):
    """Request body for updating a pipeline config."""

    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, description="Updated name")
    description: str | None = Field(default=None, description="Updated description")
    trigger: TriggerType | None = Field(default=None, description="Updated trigger type")
    branch_pattern: str | None = Field(default=None, description="Updated branch pattern")
    stages: list[StageConfig] | None = Field(default=None, description="Updated stages")
    env_vars: dict[str, str] | None = Field(default=None, description="Updated env vars")
    timeout_minutes: int | None = Field(default=None, description="Updated timeout")
    retry_config: RetryConfig | None = Field(default=None, description="Updated retry config")


class TriggerPipelineRequest(BaseModel):
    """Request body for manually triggering a pipeline."""

    model_config = ConfigDict(populate_by_name=True)

    branch: str = Field(default="main", description="Branch to build")
    commit_sha: str = Field(default="HEAD", description="Commit SHA to build")
    triggered_by: str = Field(default="manual", description="Who triggered the run")


class PipelineConfigListResponse(BaseModel):
    """Paginated list of pipeline configurations."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[PipelineConfig] = Field(default_factory=list)
    total: int = Field(default=0)


class PipelineRunListResponse(BaseModel):
    """Paginated list of pipeline runs."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[PipelineRun] = Field(default_factory=list)
    total: int = Field(default=0)


class PipelineOptimizationListResponse(BaseModel):
    """List of optimization recommendations."""

    model_config = ConfigDict(populate_by_name=True)

    config_id: str = Field(description="Pipeline config analysed")
    optimizations: list[PipelineOptimization] = Field(default_factory=list)
    total_estimated_savings_seconds: float = Field(default=0.0)


class FlakyStageEntry(BaseModel):
    """A stage identified as flaky."""

    model_config = ConfigDict(populate_by_name=True)

    stage: str = Field(description="Stage name")
    flaky_rate: float = Field(description="Rate of intermittent failures 0.0..1.0")
    total_runs: int = Field(description="Total runs examined")
    failed_runs: int = Field(description="Runs where stage failed")


class FlakyStagesResponse(BaseModel):
    """Response listing flaky stages across pipelines."""

    model_config = ConfigDict(populate_by_name=True)

    flaky_stages: list[FlakyStageEntry] = Field(default_factory=list)
    total: int = Field(default=0)


class DurationEstimate(BaseModel):
    """Estimated pipeline duration from historical data."""

    model_config = ConfigDict(populate_by_name=True)

    config_id: str = Field(description="Pipeline config ID")
    p50_seconds: float = Field(default=0.0, description="Median duration")
    p95_seconds: float = Field(default=0.0, description="95th percentile duration")
    sample_size: int = Field(default=0, description="Number of runs in the sample")
