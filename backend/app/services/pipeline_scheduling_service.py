"""Pipeline Scheduling Service for managing ETL job schedules.

Provides functionality to create and manage scheduled ETL pipeline runs
with support for cron expressions and various schedule patterns.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class ScheduleFrequency(str, Enum):
    """Common schedule frequencies."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"  # Uses cron expression


class ScheduleStatus(str, Enum):
    """Status of a schedule."""

    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


class RunStatus(str, Enum):
    """Status of a pipeline run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PipelineSchedule:
    """Schedule configuration for a pipeline."""

    id: str
    pipeline_id: str
    name: str
    description: str
    frequency: ScheduleFrequency
    cron_expression: str | None  # For custom frequency
    timezone: str
    status: ScheduleStatus
    created_at: datetime
    updated_at: datetime
    created_by: str
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_run_status: RunStatus | None
    retry_on_failure: bool = True
    max_retries: int = 3
    timeout_minutes: int = 60
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineRun:
    """Record of a pipeline execution."""

    id: str
    schedule_id: str
    pipeline_id: str
    status: RunStatus
    started_at: datetime
    completed_at: datetime | None
    duration_seconds: float | None
    records_processed: int
    records_failed: int
    triggered_by: str  # scheduled, manual, retry
    error_message: str | None
    logs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class PipelineSchedulingService:
    """Service for managing pipeline schedules and runs."""

    def __init__(self) -> None:
        """Initialize the pipeline scheduling service."""
        self._schedules: dict[str, PipelineSchedule] = {}
        self._runs: dict[str, PipelineRun] = {}
        self._lock = threading.Lock()
        self._init_sample_schedules()

    def _init_sample_schedules(self) -> None:
        """Initialize sample schedules for demonstration."""
        now = datetime.now(UTC)
        sample_schedules = [
            PipelineSchedule(
                id=str(uuid4()),
                pipeline_id="pl-patient-sync",
                name="Patient Data Sync",
                description="Synchronize patient data from source systems",
                frequency=ScheduleFrequency.DAILY,
                cron_expression=None,
                timezone="America/New_York",
                status=ScheduleStatus.ACTIVE,
                created_at=now,
                updated_at=now,
                created_by="system",
                next_run_at=now + timedelta(hours=6),
                last_run_at=now - timedelta(hours=18),
                last_run_status=RunStatus.COMPLETED,
            ),
            PipelineSchedule(
                id=str(uuid4()),
                pipeline_id="pl-lab-import",
                name="Lab Results Import",
                description="Import laboratory results from LIS",
                frequency=ScheduleFrequency.HOURLY,
                cron_expression=None,
                timezone="America/New_York",
                status=ScheduleStatus.ACTIVE,
                created_at=now,
                updated_at=now,
                created_by="system",
                next_run_at=now + timedelta(minutes=30),
                last_run_at=now - timedelta(minutes=30),
                last_run_status=RunStatus.COMPLETED,
            ),
            PipelineSchedule(
                id=str(uuid4()),
                pipeline_id="pl-claims-process",
                name="Claims Processing",
                description="Process and validate incoming claims",
                frequency=ScheduleFrequency.WEEKLY,
                cron_expression=None,
                timezone="America/New_York",
                status=ScheduleStatus.ACTIVE,
                created_at=now,
                updated_at=now,
                created_by="system",
                next_run_at=now + timedelta(days=3),
                last_run_at=now - timedelta(days=4),
                last_run_status=RunStatus.COMPLETED,
            ),
        ]

        for schedule in sample_schedules:
            self._schedules[schedule.id] = schedule

    def create_schedule(
        self,
        pipeline_id: str,
        name: str,
        description: str,
        frequency: ScheduleFrequency,
        created_by: str,
        cron_expression: str | None = None,
        timezone: str = "UTC",
        retry_on_failure: bool = True,
        max_retries: int = 3,
        timeout_minutes: int = 60,
        metadata: dict[str, Any] | None = None,
    ) -> PipelineSchedule:
        """Create a new pipeline schedule.

        Args:
            pipeline_id: ID of the pipeline to schedule.
            name: Schedule name.
            description: Schedule description.
            frequency: Schedule frequency.
            created_by: User creating the schedule.
            cron_expression: Cron expression for custom frequency.
            timezone: Timezone for scheduling.
            retry_on_failure: Whether to retry on failure.
            max_retries: Maximum retry attempts.
            timeout_minutes: Execution timeout.
            metadata: Additional metadata.

        Returns:
            Created PipelineSchedule.
        """
        schedule_id = str(uuid4())
        now = datetime.now(UTC)

        # Calculate next run time based on frequency
        next_run = self._calculate_next_run(frequency, cron_expression)

        schedule = PipelineSchedule(
            id=schedule_id,
            pipeline_id=pipeline_id,
            name=name,
            description=description,
            frequency=frequency,
            cron_expression=cron_expression,
            timezone=timezone,
            status=ScheduleStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            created_by=created_by,
            next_run_at=next_run,
            last_run_at=None,
            last_run_status=None,
            retry_on_failure=retry_on_failure,
            max_retries=max_retries,
            timeout_minutes=timeout_minutes,
            metadata=metadata or {},
        )

        with self._lock:
            self._schedules[schedule_id] = schedule

        logger.info(f"Created schedule: {schedule_id} for pipeline {pipeline_id}")
        return schedule

    def _calculate_next_run(
        self,
        frequency: ScheduleFrequency,
        cron_expression: str | None = None,
    ) -> datetime:
        """Calculate the next run time based on frequency."""
        now = datetime.now(UTC)

        if frequency == ScheduleFrequency.HOURLY:
            return now + timedelta(hours=1)
        elif frequency == ScheduleFrequency.DAILY:
            return now + timedelta(days=1)
        elif frequency == ScheduleFrequency.WEEKLY:
            return now + timedelta(weeks=1)
        elif frequency == ScheduleFrequency.MONTHLY:
            return now + timedelta(days=30)
        else:
            # Custom - would parse cron expression in production
            return now + timedelta(hours=1)

    def get_schedule(self, schedule_id: str) -> PipelineSchedule | None:
        """Get a schedule by ID."""
        return self._schedules.get(schedule_id)

    def get_schedule_by_pipeline(self, pipeline_id: str) -> PipelineSchedule | None:
        """Get schedule for a specific pipeline."""
        for schedule in self._schedules.values():
            if schedule.pipeline_id == pipeline_id:
                return schedule
        return None

    def list_schedules(
        self,
        pipeline_id: str | None = None,
        status: ScheduleStatus | None = None,
        limit: int = 100,
    ) -> list[PipelineSchedule]:
        """List schedules with optional filtering."""
        schedules = list(self._schedules.values())

        if pipeline_id:
            schedules = [s for s in schedules if s.pipeline_id == pipeline_id]

        if status:
            schedules = [s for s in schedules if s.status == status]

        schedules.sort(key=lambda s: s.updated_at, reverse=True)
        return schedules[:limit]

    def update_schedule(
        self,
        schedule_id: str,
        **updates: Any,
    ) -> PipelineSchedule | None:
        """Update a schedule."""
        with self._lock:
            schedule = self._schedules.get(schedule_id)
            if not schedule:
                return None

            if "name" in updates:
                schedule.name = updates["name"]
            if "description" in updates:
                schedule.description = updates["description"]
            if "frequency" in updates:
                schedule.frequency = ScheduleFrequency(updates["frequency"])
                schedule.next_run_at = self._calculate_next_run(schedule.frequency, schedule.cron_expression)
            if "cron_expression" in updates:
                schedule.cron_expression = updates["cron_expression"]
            if "status" in updates:
                schedule.status = ScheduleStatus(updates["status"])
            if "timezone" in updates:
                schedule.timezone = updates["timezone"]
            if "retry_on_failure" in updates:
                schedule.retry_on_failure = updates["retry_on_failure"]
            if "max_retries" in updates:
                schedule.max_retries = updates["max_retries"]
            if "timeout_minutes" in updates:
                schedule.timeout_minutes = updates["timeout_minutes"]

            schedule.updated_at = datetime.now(UTC)

        logger.info(f"Updated schedule: {schedule_id}")
        return schedule

    def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule."""
        with self._lock:
            if schedule_id in self._schedules:
                del self._schedules[schedule_id]
                logger.info(f"Deleted schedule: {schedule_id}")
                return True
        return False

    def pause_schedule(self, schedule_id: str) -> PipelineSchedule | None:
        """Pause a schedule."""
        return self.update_schedule(schedule_id, status=ScheduleStatus.PAUSED.value)

    def resume_schedule(self, schedule_id: str) -> PipelineSchedule | None:
        """Resume a paused schedule."""
        return self.update_schedule(schedule_id, status=ScheduleStatus.ACTIVE.value)

    def trigger_run(
        self,
        pipeline_id: str,
        triggered_by: str = "manual",
    ) -> PipelineRun:
        """Manually trigger a pipeline run."""
        run_id = str(uuid4())
        now = datetime.now(UTC)

        # Get schedule for the pipeline
        schedule = self.get_schedule_by_pipeline(pipeline_id)
        schedule_id = schedule.id if schedule else "manual"

        run = PipelineRun(
            id=run_id,
            schedule_id=schedule_id,
            pipeline_id=pipeline_id,
            status=RunStatus.PENDING,
            started_at=now,
            completed_at=None,
            duration_seconds=None,
            records_processed=0,
            records_failed=0,
            triggered_by=triggered_by,
            error_message=None,
        )

        with self._lock:
            self._runs[run_id] = run

        logger.info(f"Triggered run: {run_id} for pipeline {pipeline_id}")
        return run

    def get_run(self, run_id: str) -> PipelineRun | None:
        """Get a run by ID."""
        return self._runs.get(run_id)

    def list_runs(
        self,
        pipeline_id: str | None = None,
        schedule_id: str | None = None,
        status: RunStatus | None = None,
        limit: int = 100,
    ) -> list[PipelineRun]:
        """List runs with optional filtering."""
        runs = list(self._runs.values())

        if pipeline_id:
            runs = [r for r in runs if r.pipeline_id == pipeline_id]

        if schedule_id:
            runs = [r for r in runs if r.schedule_id == schedule_id]

        if status:
            runs = [r for r in runs if r.status == status]

        runs.sort(key=lambda r: r.started_at, reverse=True)
        return runs[:limit]

    def get_stats(self) -> dict[str, Any]:
        """Get scheduling statistics."""
        schedules = list(self._schedules.values())
        runs = list(self._runs.values())

        by_status: dict[str, int] = {}
        for schedule in schedules:
            by_status[schedule.status.value] = by_status.get(schedule.status.value, 0) + 1

        by_frequency: dict[str, int] = {}
        for schedule in schedules:
            by_frequency[schedule.frequency.value] = by_frequency.get(schedule.frequency.value, 0) + 1

        runs_by_status: dict[str, int] = {}
        for run in runs:
            runs_by_status[run.status.value] = runs_by_status.get(run.status.value, 0) + 1

        return {
            "total_schedules": len(schedules),
            "active_schedules": by_status.get("active", 0),
            "schedules_by_status": by_status,
            "schedules_by_frequency": by_frequency,
            "total_runs": len(runs),
            "runs_by_status": runs_by_status,
        }


# Singleton instance
_pipeline_scheduling_service: PipelineSchedulingService | None = None
_pipeline_scheduling_lock = threading.Lock()


def get_pipeline_scheduling_service() -> PipelineSchedulingService:
    """Get the singleton PipelineSchedulingService instance."""
    global _pipeline_scheduling_service

    if _pipeline_scheduling_service is None:
        with _pipeline_scheduling_lock:
            if _pipeline_scheduling_service is None:
                logger.info("Creating singleton PipelineSchedulingService instance")
                _pipeline_scheduling_service = PipelineSchedulingService()

    return _pipeline_scheduling_service


def reset_pipeline_scheduling_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _pipeline_scheduling_service
    with _pipeline_scheduling_lock:
        _pipeline_scheduling_service = None
