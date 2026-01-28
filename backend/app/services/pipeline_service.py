"""
Pipeline Service

Service for managing data ingestion pipelines.
Handles CRUD operations, scheduling, and run management.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from croniter import croniter
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.data_source import (
    DataSource,
    Pipeline,
    PipelineRun,
    PipelineRunStatus,
    PipelineStage,
    PipelineStatus,
    ScheduleType,
)

logger = logging.getLogger(__name__)


# Pydantic models for API
class PipelineCreate(BaseModel):
    """Request model for creating a pipeline."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    source_id: UUID

    # Schedule
    schedule_type: ScheduleType = ScheduleType.MANUAL
    schedule_cron: Optional[str] = None  # "0 2 * * *" = 2 AM daily
    schedule_interval_minutes: Optional[int] = None

    # Transformation config
    patient_matching_strategy: str = "deterministic"
    patient_matching_fields: list[str] = Field(default_factory=lambda: ["mrn", "dob", "name"])
    code_mapping_prefer_standard: bool = True
    code_mapping_fallback_to_source: bool = True
    nlp_enrichment_enabled: bool = True
    nlp_process_notes: bool = True
    nlp_extract_values: bool = True
    quality_min_completeness: float = 0.8
    quality_max_error_rate: float = 0.1
    resource_type_filter: Optional[list[str]] = None
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None


class PipelineUpdate(BaseModel):
    """Request model for updating a pipeline."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[PipelineStatus] = None
    is_active: Optional[bool] = None

    schedule_type: Optional[ScheduleType] = None
    schedule_cron: Optional[str] = None
    schedule_interval_minutes: Optional[int] = None

    # Transformation config (only update if provided)
    patient_matching_strategy: Optional[str] = None
    patient_matching_fields: Optional[list[str]] = None
    code_mapping_prefer_standard: Optional[bool] = None
    code_mapping_fallback_to_source: Optional[bool] = None
    nlp_enrichment_enabled: Optional[bool] = None
    nlp_process_notes: Optional[bool] = None
    nlp_extract_values: Optional[bool] = None
    quality_min_completeness: Optional[float] = None
    quality_max_error_rate: Optional[float] = None
    resource_type_filter: Optional[list[str]] = None
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None


class PipelineResponse(BaseModel):
    """Response model for pipeline."""
    id: UUID
    name: str
    description: Optional[str]
    source_id: UUID
    source_name: Optional[str] = None
    status: PipelineStatus
    is_active: bool
    schedule_type: ScheduleType
    schedule_cron: Optional[str]
    schedule_interval_minutes: Optional[int]
    transformation_config: dict
    last_run_at: Optional[datetime]
    last_run_status: Optional[str]
    next_run_at: Optional[datetime]
    total_runs: int
    successful_runs: int
    failed_runs: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PipelineRunResponse(BaseModel):
    """Response model for pipeline run."""
    id: UUID
    pipeline_id: UUID
    pipeline_name: Optional[str] = None
    status: PipelineRunStatus
    current_stage: PipelineStage
    progress_percent: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    records_total: int
    records_processed: int
    records_succeeded: int
    records_failed: int
    records_skipped: int
    stage_statistics: dict
    error_message: Optional[str]
    warnings: list
    triggered_by: str
    created_at: datetime
    duration_seconds: Optional[float] = None
    success_rate: Optional[float] = None

    class Config:
        from_attributes = True


class PipelineService:
    """Service for managing pipelines."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        data: PipelineCreate,
        created_by: Optional[UUID] = None,
    ) -> Pipeline:
        """Create a new pipeline."""
        # Verify source exists
        source = await self.db.get(DataSource, data.source_id)
        if not source:
            raise ValueError(f"Data source not found: {data.source_id}")

        # Validate cron if provided
        if data.schedule_type == ScheduleType.CRON and data.schedule_cron:
            if not self._validate_cron(data.schedule_cron):
                raise ValueError(f"Invalid cron expression: {data.schedule_cron}")

        # Build transformation config
        transformation_config = self._build_transformation_config(data)

        # Calculate next run time
        next_run_at = self._calculate_next_run(
            data.schedule_type,
            data.schedule_cron,
            data.schedule_interval_minutes,
        )

        pipeline = Pipeline(
            name=data.name,
            description=data.description,
            source_id=data.source_id,
            schedule_type=data.schedule_type,
            schedule_cron=data.schedule_cron,
            schedule_interval_minutes=data.schedule_interval_minutes,
            transformation_config=transformation_config,
            next_run_at=next_run_at,
            created_by=created_by,
        )

        self.db.add(pipeline)

        # Flush to ensure pipeline gets its ID before we capture it
        await self.db.flush()
        pipeline_id = pipeline.id

        await self.db.commit()

        # Reload with relationship to avoid lazy-load issues
        pipeline = await self.get(pipeline_id)

        logger.info(f"Created pipeline: {pipeline.id} ({pipeline.name})")
        return pipeline

    async def get(self, pipeline_id: UUID) -> Optional[Pipeline]:
        """Get a pipeline by ID."""
        result = await self.db.execute(
            select(Pipeline)
            .options(selectinload(Pipeline.data_source))
            .where(Pipeline.id == pipeline_id)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        source_id: Optional[UUID] = None,
        status: Optional[PipelineStatus] = None,
        is_active: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Pipeline]:
        """List pipelines with optional filtering."""
        query = select(Pipeline).options(selectinload(Pipeline.data_source))

        if source_id is not None:
            query = query.where(Pipeline.source_id == source_id)
        if status is not None:
            query = query.where(Pipeline.status == status)
        if is_active is not None:
            query = query.where(Pipeline.is_active == is_active)

        query = query.order_by(Pipeline.name).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(
        self,
        pipeline_id: UUID,
        data: PipelineUpdate,
    ) -> Optional[Pipeline]:
        """Update a pipeline."""
        pipeline = await self.get(pipeline_id)
        if not pipeline:
            return None

        # Update basic fields
        if data.name is not None:
            pipeline.name = data.name
        if data.description is not None:
            pipeline.description = data.description
        if data.status is not None:
            pipeline.status = data.status
        if data.is_active is not None:
            pipeline.is_active = data.is_active

        # Update schedule
        schedule_changed = False
        if data.schedule_type is not None:
            pipeline.schedule_type = data.schedule_type
            schedule_changed = True
        if data.schedule_cron is not None:
            if not self._validate_cron(data.schedule_cron):
                raise ValueError(f"Invalid cron expression: {data.schedule_cron}")
            pipeline.schedule_cron = data.schedule_cron
            schedule_changed = True
        if data.schedule_interval_minutes is not None:
            pipeline.schedule_interval_minutes = data.schedule_interval_minutes
            schedule_changed = True

        # Recalculate next run if schedule changed
        if schedule_changed:
            pipeline.next_run_at = self._calculate_next_run(
                pipeline.schedule_type,
                pipeline.schedule_cron,
                pipeline.schedule_interval_minutes,
            )

        # Update transformation config
        config = dict(pipeline.transformation_config) if pipeline.transformation_config else {}
        self._update_transformation_config(config, data)
        pipeline.transformation_config = config

        await self.db.commit()

        # Reload with relationship (refresh doesn't load relationships)
        pipeline = await self.get(pipeline_id)

        logger.info(f"Updated pipeline: {pipeline_id}")
        return pipeline

    async def delete(self, pipeline_id: UUID) -> bool:
        """Delete a pipeline."""
        pipeline = await self.get(pipeline_id)
        if not pipeline:
            return False

        await self.db.delete(pipeline)
        await self.db.commit()

        logger.info(f"Deleted pipeline: {pipeline_id}")
        return True

    async def pause(self, pipeline_id: UUID) -> Optional[Pipeline]:
        """Pause a pipeline's scheduled runs."""
        pipeline = await self.get(pipeline_id)
        if not pipeline:
            return None

        pipeline.status = PipelineStatus.PAUSED
        pipeline.next_run_at = None

        await self.db.commit()

        # Reload with relationship (refresh doesn't load relationships)
        pipeline = await self.get(pipeline_id)

        logger.info(f"Paused pipeline: {pipeline_id}")
        return pipeline

    async def resume(self, pipeline_id: UUID) -> Optional[Pipeline]:
        """Resume a paused pipeline."""
        pipeline = await self.get(pipeline_id)
        if not pipeline:
            return None

        pipeline.status = PipelineStatus.ACTIVE
        pipeline.next_run_at = self._calculate_next_run(
            pipeline.schedule_type,
            pipeline.schedule_cron,
            pipeline.schedule_interval_minutes,
        )

        await self.db.commit()

        # Reload with relationship (refresh doesn't load relationships)
        pipeline = await self.get(pipeline_id)

        logger.info(f"Resumed pipeline: {pipeline_id}")
        return pipeline

    # Run management
    async def create_run(
        self,
        pipeline_id: UUID,
        triggered_by: str = "manual",
        triggered_by_user: Optional[UUID] = None,
    ) -> PipelineRun:
        """Create a new pipeline run."""
        pipeline = await self.get(pipeline_id)
        if not pipeline:
            raise ValueError(f"Pipeline not found: {pipeline_id}")

        run = PipelineRun(
            pipeline_id=pipeline_id,
            triggered_by=triggered_by,
            triggered_by_user=triggered_by_user,
        )

        self.db.add(run)

        # Update pipeline stats
        pipeline.total_runs += 1

        # Flush to ensure run gets its ID before we capture it
        await self.db.flush()
        run_id = run.id

        await self.db.commit()

        # Reload with relationship to avoid lazy-load issues
        run = await self.get_run(run_id)

        logger.info(f"Created pipeline run: {run.id} for pipeline {pipeline_id}")
        return run

    async def get_run(self, run_id: UUID) -> Optional[PipelineRun]:
        """Get a pipeline run by ID."""
        result = await self.db.execute(
            select(PipelineRun)
            .options(selectinload(PipelineRun.pipeline))
            .where(PipelineRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def list_runs(
        self,
        pipeline_id: UUID,
        status: Optional[PipelineRunStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PipelineRun]:
        """List runs for a pipeline."""
        query = select(PipelineRun).where(PipelineRun.pipeline_id == pipeline_id)

        if status is not None:
            query = query.where(PipelineRun.status == status)

        query = query.order_by(PipelineRun.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_run_status(
        self,
        run_id: UUID,
        status: PipelineRunStatus,
        stage: Optional[PipelineStage] = None,
        progress: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> Optional[PipelineRun]:
        """Update run status and progress."""
        run = await self.get_run(run_id)
        if not run:
            return None

        run.status = status

        if stage is not None:
            run.current_stage = stage
        if progress is not None:
            run.progress_percent = progress
        if error_message is not None:
            run.error_message = error_message

        # Set timestamps
        now = datetime.now(timezone.utc)
        if status == PipelineRunStatus.RUNNING and run.started_at is None:
            run.started_at = now
        if status in (
            PipelineRunStatus.COMPLETED,
            PipelineRunStatus.COMPLETED_WITH_WARNINGS,
            PipelineRunStatus.FAILED,
            PipelineRunStatus.CANCELLED,
        ):
            run.completed_at = now

            # Update pipeline stats
            pipeline = await self.get(run.pipeline_id)
            if pipeline:
                pipeline.last_run_at = now
                pipeline.last_run_status = status.value
                if status in (PipelineRunStatus.COMPLETED, PipelineRunStatus.COMPLETED_WITH_WARNINGS):
                    pipeline.successful_runs += 1
                elif status == PipelineRunStatus.FAILED:
                    pipeline.failed_runs += 1

                # Calculate next run
                pipeline.next_run_at = self._calculate_next_run(
                    pipeline.schedule_type,
                    pipeline.schedule_cron,
                    pipeline.schedule_interval_minutes,
                )

        await self.db.commit()

        # Reload with relationship (refresh doesn't load relationships)
        return await self.get_run(run_id)

    async def update_run_statistics(
        self,
        run_id: UUID,
        records_total: Optional[int] = None,
        records_processed: Optional[int] = None,
        records_succeeded: Optional[int] = None,
        records_failed: Optional[int] = None,
        records_skipped: Optional[int] = None,
        stage_statistics: Optional[dict] = None,
        warnings: Optional[list] = None,
    ) -> Optional[PipelineRun]:
        """Update run statistics."""
        run = await self.get_run(run_id)
        if not run:
            return None

        if records_total is not None:
            run.records_total = records_total
        if records_processed is not None:
            run.records_processed = records_processed
        if records_succeeded is not None:
            run.records_succeeded = records_succeeded
        if records_failed is not None:
            run.records_failed = records_failed
        if records_skipped is not None:
            run.records_skipped = records_skipped
        if stage_statistics is not None:
            run.stage_statistics = stage_statistics
        if warnings is not None:
            run.warnings = warnings

        await self.db.commit()

        # Reload with relationship (refresh doesn't load relationships)
        return await self.get_run(run_id)

    async def cancel_run(self, run_id: UUID) -> Optional[PipelineRun]:
        """Cancel a running pipeline."""
        run = await self.get_run(run_id)
        if not run:
            return None

        if run.status not in (PipelineRunStatus.PENDING, PipelineRunStatus.RUNNING):
            raise ValueError(f"Cannot cancel run in status: {run.status}")

        return await self.update_run_status(
            run_id,
            PipelineRunStatus.CANCELLED,
            error_message="Cancelled by user",
        )

    # Get pipelines due for execution
    async def get_due_pipelines(self) -> list[Pipeline]:
        """Get pipelines that are due to run."""
        now = datetime.now(timezone.utc)

        result = await self.db.execute(
            select(Pipeline)
            .where(Pipeline.is_active == True)
            .where(Pipeline.status == PipelineStatus.ACTIVE)
            .where(Pipeline.schedule_type != ScheduleType.MANUAL)
            .where(Pipeline.next_run_at <= now)
            .order_by(Pipeline.next_run_at)
        )

        return list(result.scalars().all())

    # Helper methods
    def _validate_cron(self, cron_expr: str) -> bool:
        """Validate a cron expression."""
        try:
            croniter(cron_expr)
            return True
        except (ValueError, KeyError):
            return False

    def _calculate_next_run(
        self,
        schedule_type: ScheduleType,
        cron_expr: Optional[str],
        interval_minutes: Optional[int],
    ) -> Optional[datetime]:
        """Calculate next scheduled run time."""
        if schedule_type == ScheduleType.MANUAL:
            return None

        now = datetime.now(timezone.utc)

        if schedule_type == ScheduleType.CRON and cron_expr:
            cron = croniter(cron_expr, now)
            return cron.get_next(datetime)

        if schedule_type == ScheduleType.INTERVAL and interval_minutes:
            from datetime import timedelta
            return now + timedelta(minutes=interval_minutes)

        return None

    def _build_transformation_config(self, data: PipelineCreate) -> dict:
        """Build transformation config from create request."""
        return {
            "patient_matching": {
                "strategy": data.patient_matching_strategy,
                "match_fields": data.patient_matching_fields,
            },
            "code_mapping": {
                "prefer_standard": data.code_mapping_prefer_standard,
                "fallback_to_source": data.code_mapping_fallback_to_source,
            },
            "nlp_enrichment": {
                "enabled": data.nlp_enrichment_enabled,
                "process_notes": data.nlp_process_notes,
                "extract_values": data.nlp_extract_values,
            },
            "quality_thresholds": {
                "min_completeness": data.quality_min_completeness,
                "max_error_rate": data.quality_max_error_rate,
            },
            "filters": {
                "resource_types": data.resource_type_filter,
                "date_range": {
                    "start": data.date_range_start,
                    "end": data.date_range_end,
                },
            },
        }

    def _update_transformation_config(self, config: dict, data: PipelineUpdate) -> None:
        """Update transformation config from update request."""
        if "patient_matching" not in config:
            config["patient_matching"] = {}
        if "code_mapping" not in config:
            config["code_mapping"] = {}
        if "nlp_enrichment" not in config:
            config["nlp_enrichment"] = {}
        if "quality_thresholds" not in config:
            config["quality_thresholds"] = {}
        if "filters" not in config:
            config["filters"] = {"date_range": {}}

        if data.patient_matching_strategy is not None:
            config["patient_matching"]["strategy"] = data.patient_matching_strategy
        if data.patient_matching_fields is not None:
            config["patient_matching"]["match_fields"] = data.patient_matching_fields
        if data.code_mapping_prefer_standard is not None:
            config["code_mapping"]["prefer_standard"] = data.code_mapping_prefer_standard
        if data.code_mapping_fallback_to_source is not None:
            config["code_mapping"]["fallback_to_source"] = data.code_mapping_fallback_to_source
        if data.nlp_enrichment_enabled is not None:
            config["nlp_enrichment"]["enabled"] = data.nlp_enrichment_enabled
        if data.nlp_process_notes is not None:
            config["nlp_enrichment"]["process_notes"] = data.nlp_process_notes
        if data.nlp_extract_values is not None:
            config["nlp_enrichment"]["extract_values"] = data.nlp_extract_values
        if data.quality_min_completeness is not None:
            config["quality_thresholds"]["min_completeness"] = data.quality_min_completeness
        if data.quality_max_error_rate is not None:
            config["quality_thresholds"]["max_error_rate"] = data.quality_max_error_rate
        if data.resource_type_filter is not None:
            config["filters"]["resource_types"] = data.resource_type_filter
        if data.date_range_start is not None:
            config["filters"]["date_range"]["start"] = data.date_range_start
        if data.date_range_end is not None:
            config["filters"]["date_range"]["end"] = data.date_range_end

    def to_response(self, pipeline: Pipeline) -> PipelineResponse:
        """Convert Pipeline model to response model."""
        return PipelineResponse(
            id=pipeline.id,
            name=pipeline.name,
            description=pipeline.description,
            source_id=pipeline.source_id,
            source_name=pipeline.data_source.name if pipeline.data_source else None,
            status=pipeline.status,
            is_active=pipeline.is_active,
            schedule_type=pipeline.schedule_type,
            schedule_cron=pipeline.schedule_cron,
            schedule_interval_minutes=pipeline.schedule_interval_minutes,
            transformation_config=pipeline.transformation_config or {},
            last_run_at=pipeline.last_run_at,
            last_run_status=pipeline.last_run_status,
            next_run_at=pipeline.next_run_at,
            total_runs=pipeline.total_runs,
            successful_runs=pipeline.successful_runs,
            failed_runs=pipeline.failed_runs,
            created_at=pipeline.created_at,
            updated_at=pipeline.updated_at,
        )

    def run_to_response(self, run: PipelineRun) -> PipelineRunResponse:
        """Convert PipelineRun model to response model."""
        return PipelineRunResponse(
            id=run.id,
            pipeline_id=run.pipeline_id,
            pipeline_name=run.pipeline.name if run.pipeline else None,
            status=run.status,
            current_stage=run.current_stage,
            progress_percent=run.progress_percent,
            started_at=run.started_at,
            completed_at=run.completed_at,
            records_total=run.records_total,
            records_processed=run.records_processed,
            records_succeeded=run.records_succeeded,
            records_failed=run.records_failed,
            records_skipped=run.records_skipped,
            stage_statistics=run.stage_statistics or {},
            error_message=run.error_message,
            warnings=run.warnings or [],
            triggered_by=run.triggered_by,
            created_at=run.created_at,
            duration_seconds=run.duration_seconds,
            success_rate=run.success_rate,
        )
