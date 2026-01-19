"""ETL Orchestration Service.

This module provides a high-level orchestration service for managing ETL jobs
that extract data from various clinical sources and transform it into the
OMOP Common Data Model.

The orchestrator handles:
    - Job lifecycle management (create, run, cancel, monitor)
    - Multi-connector support (FHIR, CSV, HL7, C-CDA, Database)
    - Progress tracking with percentage completion
    - Error handling with configurable retry logic
    - Result statistics aggregation

Architecture:
    ETLOrchestrator
        ├── Manages ETLJob instances
        ├── Coordinates SourceConnector extraction
        ├── Delegates to domain-specific ETL services
        └── Publishes progress events via EventStreamService

Usage:
    from app.services.etl_orchestrator import (
        ETLOrchestrator,
        ETLJobConfig,
        get_etl_orchestrator,
    )

    orchestrator = get_etl_orchestrator()

    # Create and run a job
    job = await orchestrator.create_job(
        ETLJobConfig(
            connector_type="fhir",
            connection_string="https://fhir.example.com",
            batch_size=100,
        )
    )
    result = await orchestrator.run_job(job.job_id)
    print(f"Processed {result.statistics.total_records} records")

    # Monitor progress
    status = await orchestrator.get_job_status(job.job_id)
    print(f"Progress: {status.progress_percent}%")

    # Cancel if needed
    await orchestrator.cancel_job(job.job_id)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Callable
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors import (
    CCDAConnector,
    CCDAConnectorConfig,
    ConnectorConfig,
    ConnectorType,
    CSVConnector,
    CSVConnectorConfig,
    DatabaseConnector,
    DatabaseConnectorConfig,
    ExtractionResult,
    FHIRConnector,
    FHIRConnectorConfig,
    HL7v2Connector,
    HL7v2ConnectorConfig,
    SourceConnector,
    SourcePatient,
)
from app.etl import (
    ConditionETL,
    ConditionETLConfig,
    DrugETL,
    DrugETLConfig,
    MeasurementETL,
    MeasurementETLConfig,
    ObservationETL,
    ObservationETLConfig,
    PersonETL,
    PersonETLConfig,
    ProcedureETL,
    ProcedureETLConfig,
    VisitETL,
    VisitETLConfig,
)
from app.services.event_stream import (
    EventType,
    get_event_stream_service,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Constants
# ============================================================================


class ETLJobState(str, Enum):
    """States for an ETL job lifecycle.

    State transitions:
        PENDING -> RUNNING -> COMPLETED
        PENDING -> RUNNING -> FAILED
        PENDING -> RUNNING -> CANCELLED
        PENDING -> CANCELLED
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ETLPhase(str, Enum):
    """Phases within an ETL job execution."""

    CONNECTING = "connecting"
    EXTRACTING_PATIENTS = "extracting_patients"
    EXTRACTING_VISITS = "extracting_visits"
    EXTRACTING_CONDITIONS = "extracting_conditions"
    EXTRACTING_DRUGS = "extracting_drugs"
    EXTRACTING_PROCEDURES = "extracting_procedures"
    EXTRACTING_MEASUREMENTS = "extracting_measurements"
    EXTRACTING_OBSERVATIONS = "extracting_observations"
    TRANSFORMING = "transforming"
    LOADING = "loading"
    FINALIZING = "finalizing"


# Default retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY_SECONDS = 5.0
DEFAULT_RETRY_BACKOFF_MULTIPLIER = 2.0


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class ETLJobStatistics:
    """Statistics collected during ETL job execution.

    Attributes:
        total_records: Total records processed across all types.
        patients_processed: Number of patient records processed.
        visits_processed: Number of visit records processed.
        conditions_processed: Number of condition records processed.
        drugs_processed: Number of drug records processed.
        procedures_processed: Number of procedure records processed.
        measurements_processed: Number of measurement records processed.
        observations_processed: Number of observation records processed.
        records_created: Number of new OMOP records created.
        records_updated: Number of existing OMOP records updated.
        records_skipped: Number of records skipped (duplicates, filtered).
        unmapped_codes: Number of codes that couldn't be mapped to standard concepts.
        retries_performed: Number of retry attempts made.
    """

    total_records: int = 0
    patients_processed: int = 0
    visits_processed: int = 0
    conditions_processed: int = 0
    drugs_processed: int = 0
    procedures_processed: int = 0
    measurements_processed: int = 0
    observations_processed: int = 0
    records_created: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    unmapped_codes: int = 0
    retries_performed: int = 0

    def update_total(self) -> None:
        """Update total_records based on individual counts."""
        self.total_records = (
            self.patients_processed
            + self.visits_processed
            + self.conditions_processed
            + self.drugs_processed
            + self.procedures_processed
            + self.measurements_processed
            + self.observations_processed
        )

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary for serialization."""
        return {
            "total_records": self.total_records,
            "patients_processed": self.patients_processed,
            "visits_processed": self.visits_processed,
            "conditions_processed": self.conditions_processed,
            "drugs_processed": self.drugs_processed,
            "procedures_processed": self.procedures_processed,
            "measurements_processed": self.measurements_processed,
            "observations_processed": self.observations_processed,
            "records_created": self.records_created,
            "records_updated": self.records_updated,
            "records_skipped": self.records_skipped,
            "unmapped_codes": self.unmapped_codes,
            "retries_performed": self.retries_performed,
        }


@dataclass
class ETLJobError:
    """Represents an error that occurred during ETL processing.

    Attributes:
        timestamp: When the error occurred.
        phase: ETL phase when error occurred.
        record_id: Source record ID if applicable.
        error_type: Type/class of the error.
        error_message: Human-readable error description.
        is_retryable: Whether this error can be retried.
        retry_count: Number of retries attempted for this error.
        stack_trace: Optional stack trace for debugging.
    """

    timestamp: datetime
    phase: ETLPhase
    record_id: str | None = None
    error_type: str = ""
    error_message: str = ""
    is_retryable: bool = False
    retry_count: int = 0
    stack_trace: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "phase": self.phase.value,
            "record_id": self.record_id,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "is_retryable": self.is_retryable,
            "retry_count": self.retry_count,
            "stack_trace": self.stack_trace,
        }


@dataclass
class ETLJobProgress:
    """Progress tracking for an ETL job.

    Attributes:
        current_phase: Current execution phase.
        phase_progress_percent: Progress within current phase (0-100).
        overall_progress_percent: Overall job progress (0-100).
        records_in_phase: Records processed in current phase.
        total_records_estimate: Estimated total records (may be updated).
        current_record_id: ID of record currently being processed.
        phases_completed: List of completed phase names.
        eta_seconds: Estimated time remaining in seconds.
    """

    current_phase: ETLPhase = ETLPhase.CONNECTING
    phase_progress_percent: float = 0.0
    overall_progress_percent: float = 0.0
    records_in_phase: int = 0
    total_records_estimate: int = 0
    current_record_id: str | None = None
    phases_completed: list[str] = field(default_factory=list)
    eta_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "current_phase": self.current_phase.value,
            "phase_progress_percent": round(self.phase_progress_percent, 1),
            "overall_progress_percent": round(self.overall_progress_percent, 1),
            "records_in_phase": self.records_in_phase,
            "total_records_estimate": self.total_records_estimate,
            "current_record_id": self.current_record_id,
            "phases_completed": self.phases_completed,
            "eta_seconds": round(self.eta_seconds, 1) if self.eta_seconds else None,
        }


@dataclass
class ETLJobConfig:
    """Configuration for creating an ETL job.

    Attributes:
        connector_type: Type of source connector (fhir, csv, hl7v2, ccda, database).
        connection_string: Connection string/URL for the source.
        source_name: Human-readable name for the source system.
        batch_size: Number of records to process in each batch.
        max_records: Maximum records to process (None = unlimited).
        patient_ids: Optional list of specific patient IDs to process.
        start_date: Optional start date filter for records.
        end_date: Optional end date filter for records.
        max_retries: Maximum retry attempts for failed operations.
        retry_delay_seconds: Initial delay between retries.
        retry_backoff_multiplier: Multiplier for exponential backoff.
        skip_on_error: Continue processing if a record fails.
        max_errors: Stop job after this many errors.
        enable_progress_events: Publish progress events to EventStreamService.
        connector_options: Additional connector-specific options.
        etl_options: Additional ETL-specific options.
    """

    connector_type: str
    connection_string: str
    source_name: str = "default"
    batch_size: int = 100
    max_records: int | None = None
    patient_ids: list[str] | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_delay_seconds: float = DEFAULT_RETRY_DELAY_SECONDS
    retry_backoff_multiplier: float = DEFAULT_RETRY_BACKOFF_MULTIPLIER
    skip_on_error: bool = True
    max_errors: int = 100
    enable_progress_events: bool = True
    connector_options: dict[str, Any] = field(default_factory=dict)
    etl_options: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "connector_type": self.connector_type,
            "connection_string": self.connection_string,
            "source_name": self.source_name,
            "batch_size": self.batch_size,
            "max_records": self.max_records,
            "patient_ids": self.patient_ids,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay_seconds,
            "retry_backoff_multiplier": self.retry_backoff_multiplier,
            "skip_on_error": self.skip_on_error,
            "max_errors": self.max_errors,
            "enable_progress_events": self.enable_progress_events,
        }


@dataclass
class ETLJob:
    """Represents an ETL job with its state and metadata.

    Attributes:
        job_id: Unique identifier for this job.
        state: Current job state.
        config: Job configuration.
        progress: Current progress tracking.
        statistics: Collected statistics.
        errors: List of errors encountered.
        warnings: List of warning messages.
        created_at: When the job was created.
        started_at: When job execution started.
        completed_at: When job execution finished.
        duration_seconds: Total execution time.
        source_patient_mapping: Map of source_id -> person_id for linking.
        source_visit_mapping: Map of source_id -> visit_occurrence_id for linking.
    """

    job_id: UUID
    state: ETLJobState
    config: ETLJobConfig
    progress: ETLJobProgress = field(default_factory=ETLJobProgress)
    statistics: ETLJobStatistics = field(default_factory=ETLJobStatistics)
    errors: list[ETLJobError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    source_patient_mapping: dict[str, int] = field(default_factory=dict)
    source_visit_mapping: dict[str, int] = field(default_factory=dict)

    # Internal control flag
    _cancel_requested: bool = field(default=False, repr=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "job_id": str(self.job_id),
            "state": self.state.value,
            "config": self.config.to_dict(),
            "progress": self.progress.to_dict(),
            "statistics": self.statistics.to_dict(),
            "errors": [e.to_dict() for e in self.errors],
            "warnings": self.warnings,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class ETLJobResult:
    """Result returned after job completion.

    Attributes:
        job_id: Job identifier.
        state: Final job state.
        statistics: Final statistics.
        errors: All errors encountered.
        warnings: All warnings.
        duration_seconds: Total execution time.
        extraction_result: Raw extraction result from connector.
    """

    job_id: UUID
    state: ETLJobState
    statistics: ETLJobStatistics
    errors: list[ETLJobError]
    warnings: list[str]
    duration_seconds: float | None
    extraction_result: ExtractionResult | None = None

    @property
    def success(self) -> bool:
        """Whether the job completed successfully."""
        return self.state == ETLJobState.COMPLETED

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "job_id": str(self.job_id),
            "state": self.state.value,
            "success": self.success,
            "statistics": self.statistics.to_dict(),
            "errors": [e.to_dict() for e in self.errors],
            "warnings": self.warnings,
            "duration_seconds": self.duration_seconds,
        }


# ============================================================================
# ETL Orchestrator Service
# ============================================================================


class ETLOrchestrator:
    """Orchestrates ETL jobs for clinical data transformation to OMOP CDM.

    The orchestrator manages the complete lifecycle of ETL jobs:
    1. Job creation with configuration validation
    2. Source connector instantiation based on type
    3. Coordinated extraction, transformation, and loading
    4. Progress tracking and event publishing
    5. Error handling with retry logic
    6. Job cancellation support

    Example:
        orchestrator = ETLOrchestrator(db_session)

        config = ETLJobConfig(
            connector_type="fhir",
            connection_string="https://fhir.server.com",
        )
        job = await orchestrator.create_job(config)
        result = await orchestrator.run_job(job.job_id)

        print(f"Processed {result.statistics.total_records} records")
        if not result.success:
            for error in result.errors:
                print(f"Error: {error.error_message}")
    """

    def __init__(
        self,
        session: AsyncSession | None = None,
        vocabulary_service: Any | None = None,
    ) -> None:
        """Initialize the ETL orchestrator.

        Args:
            session: SQLAlchemy async session for database operations.
            vocabulary_service: Optional vocabulary service for concept mapping.
        """
        self._session = session
        self._vocabulary_service = vocabulary_service

        # Job registry
        self._jobs: dict[UUID, ETLJob] = {}

        # Lock for thread-safe job management
        self._lock = asyncio.Lock()

        # Track running tasks for cancellation
        self._running_tasks: dict[UUID, asyncio.Task] = {}

        logger.info("ETLOrchestrator initialized")

    # -------------------------------------------------------------------------
    # Job Management
    # -------------------------------------------------------------------------

    async def create_job(self, config: ETLJobConfig) -> ETLJob:
        """Create a new ETL job.

        Args:
            config: Job configuration.

        Returns:
            Created ETLJob in PENDING state.

        Raises:
            ValueError: If configuration is invalid.
        """
        # Validate configuration
        self._validate_config(config)

        job = ETLJob(
            job_id=uuid4(),
            state=ETLJobState.PENDING,
            config=config,
        )

        async with self._lock:
            self._jobs[job.job_id] = job

        logger.info(f"Created ETL job {job.job_id} with connector type {config.connector_type}")
        return job

    async def run_job(self, job_id: UUID) -> ETLJobResult:
        """Execute an ETL job.

        Args:
            job_id: ID of the job to run.

        Returns:
            ETLJobResult with final state and statistics.

        Raises:
            ValueError: If job not found or not in PENDING state.
        """
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")
            if job.state != ETLJobState.PENDING:
                raise ValueError(f"Job {job_id} is not in PENDING state (current: {job.state})")

            job.state = ETLJobState.RUNNING
            job.started_at = datetime.now(UTC)

        # Create task for async execution
        task = asyncio.create_task(self._execute_job(job))
        self._running_tasks[job_id] = task

        try:
            result = await task
        finally:
            self._running_tasks.pop(job_id, None)

        return result

    async def cancel_job(self, job_id: UUID) -> bool:
        """Cancel a running or pending job.

        Args:
            job_id: ID of the job to cancel.

        Returns:
            True if cancellation was successful, False otherwise.
        """
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                logger.warning(f"Attempted to cancel non-existent job {job_id}")
                return False

            if job.state not in (ETLJobState.PENDING, ETLJobState.RUNNING):
                logger.warning(f"Job {job_id} cannot be cancelled (state: {job.state})")
                return False

            job._cancel_requested = True

            if job.state == ETLJobState.PENDING:
                job.state = ETLJobState.CANCELLED
                job.completed_at = datetime.now(UTC)
                logger.info(f"Cancelled pending job {job_id}")
                return True

        # For running jobs, cancel the task
        task = self._running_tasks.get(job_id)
        if task:
            task.cancel()
            logger.info(f"Cancellation requested for running job {job_id}")
            return True

        return False

    async def get_job_status(self, job_id: UUID) -> ETLJob | None:
        """Get current status of a job.

        Args:
            job_id: ID of the job.

        Returns:
            ETLJob with current state, or None if not found.
        """
        return self._jobs.get(job_id)

    async def list_jobs(
        self,
        state: ETLJobState | None = None,
        limit: int = 100,
    ) -> list[ETLJob]:
        """List ETL jobs with optional filtering.

        Args:
            state: Filter by job state.
            limit: Maximum number of jobs to return.

        Returns:
            List of matching ETLJob instances.
        """
        jobs = list(self._jobs.values())

        if state:
            jobs = [j for j in jobs if j.state == state]

        # Sort by created_at descending
        jobs.sort(key=lambda j: j.created_at, reverse=True)

        return jobs[:limit]

    async def delete_job(self, job_id: UUID) -> bool:
        """Delete a completed or failed job from the registry.

        Args:
            job_id: ID of the job to delete.

        Returns:
            True if deleted, False if not found or still running.
        """
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False

            if job.state in (ETLJobState.PENDING, ETLJobState.RUNNING):
                logger.warning(f"Cannot delete active job {job_id}")
                return False

            del self._jobs[job_id]
            logger.info(f"Deleted job {job_id}")
            return True

    # -------------------------------------------------------------------------
    # Job Execution
    # -------------------------------------------------------------------------

    async def _execute_job(self, job: ETLJob) -> ETLJobResult:
        """Execute the ETL job pipeline.

        Args:
            job: The job to execute.

        Returns:
            ETLJobResult with final state and statistics.
        """
        connector: SourceConnector | None = None
        extraction_result: ExtractionResult | None = None

        try:
            # Publish job started event
            await self._publish_progress(job)

            # Create connector
            job.progress.current_phase = ETLPhase.CONNECTING
            connector = self._create_connector(job.config)

            # Connect to source
            connected = await connector.connect()
            if not connected:
                raise ConnectionError(f"Failed to connect to {job.config.source_name}")

            job.progress.phases_completed.append(ETLPhase.CONNECTING.value)

            # Run extraction and transformation phases
            await self._run_extraction_phases(job, connector)

            # Finalize
            job.progress.current_phase = ETLPhase.FINALIZING
            job.statistics.update_total()
            job.progress.phases_completed.append(ETLPhase.FINALIZING.value)

            # Mark as completed
            job.state = ETLJobState.COMPLETED
            job.progress.overall_progress_percent = 100.0

            logger.info(
                f"Job {job.job_id} completed successfully. "
                f"Processed {job.statistics.total_records} records."
            )

        except asyncio.CancelledError:
            job.state = ETLJobState.CANCELLED
            logger.info(f"Job {job.job_id} was cancelled")

        except Exception as e:
            job.state = ETLJobState.FAILED
            error = ETLJobError(
                timestamp=datetime.now(UTC),
                phase=job.progress.current_phase,
                error_type=type(e).__name__,
                error_message=str(e),
                is_retryable=False,
            )
            job.errors.append(error)
            logger.error(f"Job {job.job_id} failed: {e}", exc_info=True)

        finally:
            # Clean up
            if connector:
                try:
                    await connector.disconnect()
                except Exception as e:
                    logger.warning(f"Error disconnecting connector: {e}")

            job.completed_at = datetime.now(UTC)
            if job.started_at:
                job.duration_seconds = (job.completed_at - job.started_at).total_seconds()

            # Publish completion event
            await self._publish_completion(job)

        return ETLJobResult(
            job_id=job.job_id,
            state=job.state,
            statistics=job.statistics,
            errors=job.errors,
            warnings=job.warnings,
            duration_seconds=job.duration_seconds,
            extraction_result=extraction_result,
        )

    async def _run_extraction_phases(
        self,
        job: ETLJob,
        connector: SourceConnector,
    ) -> None:
        """Run all extraction and transformation phases.

        Args:
            job: The ETL job.
            connector: Connected source connector.
        """
        # Define phase weights for progress calculation
        phase_weights = {
            ETLPhase.EXTRACTING_PATIENTS: 0.20,
            ETLPhase.EXTRACTING_VISITS: 0.15,
            ETLPhase.EXTRACTING_CONDITIONS: 0.15,
            ETLPhase.EXTRACTING_DRUGS: 0.15,
            ETLPhase.EXTRACTING_PROCEDURES: 0.10,
            ETLPhase.EXTRACTING_MEASUREMENTS: 0.15,
            ETLPhase.EXTRACTING_OBSERVATIONS: 0.10,
        }

        completed_weight = 0.0

        # Extract and transform patients
        await self._run_patient_phase(job, connector, phase_weights, completed_weight)
        completed_weight += phase_weights[ETLPhase.EXTRACTING_PATIENTS]

        # Extract and transform visits
        await self._run_visit_phase(job, connector, phase_weights, completed_weight)
        completed_weight += phase_weights[ETLPhase.EXTRACTING_VISITS]

        # Extract and transform conditions
        await self._run_condition_phase(job, connector, phase_weights, completed_weight)
        completed_weight += phase_weights[ETLPhase.EXTRACTING_CONDITIONS]

        # Extract and transform drugs
        await self._run_drug_phase(job, connector, phase_weights, completed_weight)
        completed_weight += phase_weights[ETLPhase.EXTRACTING_DRUGS]

        # Extract and transform procedures
        await self._run_procedure_phase(job, connector, phase_weights, completed_weight)
        completed_weight += phase_weights[ETLPhase.EXTRACTING_PROCEDURES]

        # Extract and transform measurements
        await self._run_measurement_phase(job, connector, phase_weights, completed_weight)
        completed_weight += phase_weights[ETLPhase.EXTRACTING_MEASUREMENTS]

        # Extract and transform observations
        await self._run_observation_phase(job, connector, phase_weights, completed_weight)

    async def _run_patient_phase(
        self,
        job: ETLJob,
        connector: SourceConnector,
        phase_weights: dict[ETLPhase, float],
        completed_weight: float,
    ) -> None:
        """Extract and transform patient records."""
        phase = ETLPhase.EXTRACTING_PATIENTS
        job.progress.current_phase = phase
        job.progress.records_in_phase = 0

        if not self._session:
            job.warnings.append("No database session - skipping patient transformation")
            job.progress.phases_completed.append(phase.value)
            return

        person_etl = PersonETL(
            self._session,
            PersonETLConfig(
                batch_size=job.config.batch_size,
                **job.config.etl_options.get("person", {}),
            ),
        )

        count = 0
        async for patient in connector.extract_patients():
            if job._cancel_requested:
                raise asyncio.CancelledError()

            # Check max records limit
            if job.config.max_records and count >= job.config.max_records:
                break

            # Filter by patient IDs if specified
            if job.config.patient_ids and patient.source_id not in job.config.patient_ids:
                continue

            try:
                person = await self._with_retry(
                    lambda p=patient: person_etl.transform_and_load(p),
                    job,
                    phase,
                    patient.source_id,
                )

                # Store mapping for linking other records
                if person:
                    job.source_patient_mapping[patient.source_id] = person.person_id
                    job.statistics.records_created += 1

                count += 1
                job.statistics.patients_processed += 1
                job.progress.records_in_phase = count
                job.progress.current_record_id = patient.source_id

                # Update progress
                self._update_progress(job, phase, phase_weights, completed_weight, count)

                # Publish progress periodically
                if count % 100 == 0:
                    await self._publish_progress(job)

            except Exception as e:
                await self._handle_record_error(job, phase, patient.source_id, e)

        job.progress.phases_completed.append(phase.value)
        await self._publish_progress(job)

    async def _run_visit_phase(
        self,
        job: ETLJob,
        connector: SourceConnector,
        phase_weights: dict[ETLPhase, float],
        completed_weight: float,
    ) -> None:
        """Extract and transform visit records."""
        phase = ETLPhase.EXTRACTING_VISITS
        job.progress.current_phase = phase
        job.progress.records_in_phase = 0

        if not self._session:
            job.progress.phases_completed.append(phase.value)
            return

        visit_etl = VisitETL(
            self._session,
            VisitETLConfig(
                batch_size=job.config.batch_size,
                **job.config.etl_options.get("visit", {}),
            ),
        )

        count = 0
        async for visit in connector.extract_visits():
            if job._cancel_requested:
                raise asyncio.CancelledError()

            # Get person_id from mapping
            person_id = job.source_patient_mapping.get(visit.patient_source_id)
            if not person_id:
                job.warnings.append(f"No person mapping for visit {visit.source_id}")
                continue

            try:
                visit_occ = await self._with_retry(
                    lambda v=visit, pid=person_id: visit_etl.transform_and_load(v, pid),
                    job,
                    phase,
                    visit.source_id,
                )

                if visit_occ:
                    job.source_visit_mapping[visit.source_id] = visit_occ.visit_occurrence_id
                    job.statistics.records_created += 1

                count += 1
                job.statistics.visits_processed += 1
                job.progress.records_in_phase = count
                job.progress.current_record_id = visit.source_id

                self._update_progress(job, phase, phase_weights, completed_weight, count)

                if count % 100 == 0:
                    await self._publish_progress(job)

            except Exception as e:
                await self._handle_record_error(job, phase, visit.source_id, e)

        job.progress.phases_completed.append(phase.value)

    async def _run_condition_phase(
        self,
        job: ETLJob,
        connector: SourceConnector,
        phase_weights: dict[ETLPhase, float],
        completed_weight: float,
    ) -> None:
        """Extract and transform condition records."""
        phase = ETLPhase.EXTRACTING_CONDITIONS
        job.progress.current_phase = phase
        job.progress.records_in_phase = 0

        if not self._session:
            job.progress.phases_completed.append(phase.value)
            return

        condition_etl = ConditionETL(
            self._session,
            ConditionETLConfig(
                batch_size=job.config.batch_size,
                **job.config.etl_options.get("condition", {}),
            ),
            vocabulary_service=self._vocabulary_service,
        )

        count = 0
        async for condition in connector.extract_conditions():
            if job._cancel_requested:
                raise asyncio.CancelledError()

            person_id = job.source_patient_mapping.get(condition.patient_source_id)
            if not person_id:
                continue

            visit_id = job.source_visit_mapping.get(condition.visit_source_id) if condition.visit_source_id else None

            try:
                cond_occ = await self._with_retry(
                    lambda c=condition, pid=person_id, vid=visit_id: condition_etl.transform_and_load(
                        c, pid, vid
                    ),
                    job,
                    phase,
                    condition.source_id,
                )

                if cond_occ:
                    job.statistics.records_created += 1
                    if cond_occ.condition_concept_id == 0:
                        job.statistics.unmapped_codes += 1

                count += 1
                job.statistics.conditions_processed += 1
                job.progress.records_in_phase = count

                self._update_progress(job, phase, phase_weights, completed_weight, count)

                if count % 100 == 0:
                    await self._publish_progress(job)

            except Exception as e:
                await self._handle_record_error(job, phase, condition.source_id, e)

        job.progress.phases_completed.append(phase.value)

    async def _run_drug_phase(
        self,
        job: ETLJob,
        connector: SourceConnector,
        phase_weights: dict[ETLPhase, float],
        completed_weight: float,
    ) -> None:
        """Extract and transform drug/medication records."""
        phase = ETLPhase.EXTRACTING_DRUGS
        job.progress.current_phase = phase
        job.progress.records_in_phase = 0

        if not self._session:
            job.progress.phases_completed.append(phase.value)
            return

        drug_etl = DrugETL(
            self._session,
            DrugETLConfig(
                batch_size=job.config.batch_size,
                **job.config.etl_options.get("drug", {}),
            ),
            vocabulary_service=self._vocabulary_service,
        )

        count = 0
        async for drug in connector.extract_drugs():
            if job._cancel_requested:
                raise asyncio.CancelledError()

            person_id = job.source_patient_mapping.get(drug.patient_source_id)
            if not person_id:
                continue

            visit_id = job.source_visit_mapping.get(drug.visit_source_id) if drug.visit_source_id else None

            try:
                drug_exp = await self._with_retry(
                    lambda d=drug, pid=person_id, vid=visit_id: drug_etl.transform_and_load(
                        d, pid, vid
                    ),
                    job,
                    phase,
                    drug.source_id,
                )

                if drug_exp:
                    job.statistics.records_created += 1
                    if drug_exp.drug_concept_id == 0:
                        job.statistics.unmapped_codes += 1

                count += 1
                job.statistics.drugs_processed += 1
                job.progress.records_in_phase = count

                self._update_progress(job, phase, phase_weights, completed_weight, count)

                if count % 100 == 0:
                    await self._publish_progress(job)

            except Exception as e:
                await self._handle_record_error(job, phase, drug.source_id, e)

        job.progress.phases_completed.append(phase.value)

    async def _run_procedure_phase(
        self,
        job: ETLJob,
        connector: SourceConnector,
        phase_weights: dict[ETLPhase, float],
        completed_weight: float,
    ) -> None:
        """Extract and transform procedure records."""
        phase = ETLPhase.EXTRACTING_PROCEDURES
        job.progress.current_phase = phase
        job.progress.records_in_phase = 0

        if not self._session:
            job.progress.phases_completed.append(phase.value)
            return

        procedure_etl = ProcedureETL(
            self._session,
            ProcedureETLConfig(
                batch_size=job.config.batch_size,
                **job.config.etl_options.get("procedure", {}),
            ),
            vocabulary_service=self._vocabulary_service,
        )

        count = 0
        async for procedure in connector.extract_procedures():
            if job._cancel_requested:
                raise asyncio.CancelledError()

            person_id = job.source_patient_mapping.get(procedure.patient_source_id)
            if not person_id:
                continue

            visit_id = job.source_visit_mapping.get(procedure.visit_source_id) if procedure.visit_source_id else None

            try:
                proc_occ = await self._with_retry(
                    lambda p=procedure, pid=person_id, vid=visit_id: procedure_etl.transform_and_load(
                        p, pid, vid
                    ),
                    job,
                    phase,
                    procedure.source_id,
                )

                if proc_occ:
                    job.statistics.records_created += 1
                    if proc_occ.procedure_concept_id == 0:
                        job.statistics.unmapped_codes += 1

                count += 1
                job.statistics.procedures_processed += 1
                job.progress.records_in_phase = count

                self._update_progress(job, phase, phase_weights, completed_weight, count)

                if count % 100 == 0:
                    await self._publish_progress(job)

            except Exception as e:
                await self._handle_record_error(job, phase, procedure.source_id, e)

        job.progress.phases_completed.append(phase.value)

    async def _run_measurement_phase(
        self,
        job: ETLJob,
        connector: SourceConnector,
        phase_weights: dict[ETLPhase, float],
        completed_weight: float,
    ) -> None:
        """Extract and transform measurement/lab records."""
        phase = ETLPhase.EXTRACTING_MEASUREMENTS
        job.progress.current_phase = phase
        job.progress.records_in_phase = 0

        if not self._session:
            job.progress.phases_completed.append(phase.value)
            return

        measurement_etl = MeasurementETL(
            self._session,
            MeasurementETLConfig(
                batch_size=job.config.batch_size,
                **job.config.etl_options.get("measurement", {}),
            ),
            vocabulary_service=self._vocabulary_service,
        )

        count = 0
        async for measurement in connector.extract_measurements():
            if job._cancel_requested:
                raise asyncio.CancelledError()

            person_id = job.source_patient_mapping.get(measurement.patient_source_id)
            if not person_id:
                continue

            visit_id = job.source_visit_mapping.get(measurement.visit_source_id) if measurement.visit_source_id else None

            try:
                meas_rec = await self._with_retry(
                    lambda m=measurement, pid=person_id, vid=visit_id: measurement_etl.transform_and_load(
                        m, pid, vid
                    ),
                    job,
                    phase,
                    measurement.source_id,
                )

                if meas_rec:
                    job.statistics.records_created += 1
                    if meas_rec.measurement_concept_id == 0:
                        job.statistics.unmapped_codes += 1

                count += 1
                job.statistics.measurements_processed += 1
                job.progress.records_in_phase = count

                self._update_progress(job, phase, phase_weights, completed_weight, count)

                if count % 100 == 0:
                    await self._publish_progress(job)

            except Exception as e:
                await self._handle_record_error(job, phase, measurement.source_id, e)

        job.progress.phases_completed.append(phase.value)

    async def _run_observation_phase(
        self,
        job: ETLJob,
        connector: SourceConnector,
        phase_weights: dict[ETLPhase, float],
        completed_weight: float,
    ) -> None:
        """Extract and transform observation records."""
        phase = ETLPhase.EXTRACTING_OBSERVATIONS
        job.progress.current_phase = phase
        job.progress.records_in_phase = 0

        if not self._session:
            job.progress.phases_completed.append(phase.value)
            return

        observation_etl = ObservationETL(
            self._session,
            ObservationETLConfig(
                batch_size=job.config.batch_size,
                **job.config.etl_options.get("observation", {}),
            ),
            vocabulary_service=self._vocabulary_service,
        )

        count = 0
        async for observation in connector.extract_observations():
            if job._cancel_requested:
                raise asyncio.CancelledError()

            person_id = job.source_patient_mapping.get(observation.patient_source_id)
            if not person_id:
                continue

            visit_id = job.source_visit_mapping.get(observation.visit_source_id) if observation.visit_source_id else None

            try:
                obs_rec = await self._with_retry(
                    lambda o=observation, pid=person_id, vid=visit_id: observation_etl.transform_and_load(
                        o, pid, vid
                    ),
                    job,
                    phase,
                    observation.source_id,
                )

                if obs_rec:
                    job.statistics.records_created += 1
                    if obs_rec.observation_concept_id == 0:
                        job.statistics.unmapped_codes += 1

                count += 1
                job.statistics.observations_processed += 1
                job.progress.records_in_phase = count

                self._update_progress(job, phase, phase_weights, completed_weight, count)

                if count % 100 == 0:
                    await self._publish_progress(job)

            except Exception as e:
                await self._handle_record_error(job, phase, observation.source_id, e)

        job.progress.phases_completed.append(phase.value)

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _validate_config(self, config: ETLJobConfig) -> None:
        """Validate job configuration.

        Args:
            config: Configuration to validate.

        Raises:
            ValueError: If configuration is invalid.
        """
        valid_connector_types = {"fhir", "csv", "hl7v2", "ccda", "database"}
        if config.connector_type.lower() not in valid_connector_types:
            raise ValueError(
                f"Invalid connector type: {config.connector_type}. "
                f"Must be one of: {valid_connector_types}"
            )

        if config.batch_size < 1:
            raise ValueError("batch_size must be at least 1")

        if config.max_retries < 0:
            raise ValueError("max_retries cannot be negative")

        if config.retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds cannot be negative")

    def _create_connector(self, config: ETLJobConfig) -> SourceConnector:
        """Create a source connector based on configuration.

        Args:
            config: Job configuration.

        Returns:
            Configured SourceConnector instance.

        Raises:
            ValueError: If connector type is not supported.
        """
        connector_type = config.connector_type.lower()

        # Common connector config options (base fields)
        common_options = {
            "name": config.source_name,
            "batch_size": config.batch_size,
            "max_records": config.max_records,
            "patient_ids": config.patient_ids,
            "start_date": config.start_date.date() if config.start_date else None,
            "end_date": config.end_date.date() if config.end_date else None,
            "skip_on_error": config.skip_on_error,
            "max_errors": config.max_errors,
        }

        # Merge with connector-specific options
        connector_options = {**common_options, **config.connector_options}

        if connector_type == "fhir":
            return FHIRConnector(
                FHIRConnectorConfig(
                    base_url=config.connection_string,
                    **connector_options,
                )
            )

        elif connector_type == "csv":
            return CSVConnector(
                CSVConnectorConfig(
                    base_dir=config.connection_string,
                    **connector_options,
                )
            )

        elif connector_type == "hl7v2":
            return HL7v2Connector(
                HL7v2ConnectorConfig(
                    messages_dir=config.connection_string,
                    **connector_options,
                )
            )

        elif connector_type == "ccda":
            from pathlib import Path
            return CCDAConnector(
                CCDAConnectorConfig(
                    documents_path=Path(config.connection_string),
                    **connector_options,
                )
            )

        elif connector_type == "database":
            return DatabaseConnector(
                DatabaseConnectorConfig(
                    connection_string=config.connection_string,
                    **connector_options,
                )
            )

        else:
            raise ValueError(f"Unsupported connector type: {connector_type}")

    async def _with_retry(
        self,
        operation: Callable,
        job: ETLJob,
        phase: ETLPhase,
        record_id: str,
    ) -> Any:
        """Execute an operation with retry logic.

        Args:
            operation: Async callable to execute.
            job: Current job for configuration.
            phase: Current ETL phase.
            record_id: ID of the record being processed.

        Returns:
            Result of the operation.

        Raises:
            Exception: If all retries are exhausted.
        """
        last_error: Exception | None = None
        delay = job.config.retry_delay_seconds

        for attempt in range(job.config.max_retries + 1):
            try:
                # Check for asyncio coroutine
                result = operation()
                if asyncio.iscoroutine(result):
                    return await result
                return result

            except Exception as e:
                last_error = e
                is_retryable = self._is_retryable_error(e)

                if attempt < job.config.max_retries and is_retryable:
                    job.statistics.retries_performed += 1
                    logger.warning(
                        f"Retry {attempt + 1}/{job.config.max_retries} for {record_id}: {e}"
                    )
                    await asyncio.sleep(delay)
                    delay *= job.config.retry_backoff_multiplier
                else:
                    raise

        # Should not reach here, but just in case
        if last_error:
            raise last_error

    def _is_retryable_error(self, error: Exception) -> bool:
        """Determine if an error is retryable.

        Args:
            error: The exception to check.

        Returns:
            True if the error can be retried.
        """
        # Network/connection errors are typically retryable
        retryable_types = (
            ConnectionError,
            TimeoutError,
            asyncio.TimeoutError,
        )

        # Check exception type
        if isinstance(error, retryable_types):
            return True

        # Check error message for common transient issues
        error_msg = str(error).lower()
        transient_indicators = [
            "timeout",
            "connection refused",
            "temporarily unavailable",
            "too many requests",
            "rate limit",
            "503",
            "504",
            "429",
        ]

        return any(indicator in error_msg for indicator in transient_indicators)

    async def _handle_record_error(
        self,
        job: ETLJob,
        phase: ETLPhase,
        record_id: str,
        error: Exception,
    ) -> None:
        """Handle an error during record processing.

        Args:
            job: Current job.
            phase: ETL phase where error occurred.
            record_id: ID of the failed record.
            error: The exception that occurred.
        """
        job_error = ETLJobError(
            timestamp=datetime.now(UTC),
            phase=phase,
            record_id=record_id,
            error_type=type(error).__name__,
            error_message=str(error),
            is_retryable=self._is_retryable_error(error),
        )
        job.errors.append(job_error)

        logger.warning(f"Error processing {record_id} in {phase.value}: {error}")

        # Check if we should stop the job
        if len(job.errors) >= job.config.max_errors:
            raise RuntimeError(
                f"Maximum error count ({job.config.max_errors}) reached. "
                f"Stopping job."
            )

        if not job.config.skip_on_error:
            raise error

    def _update_progress(
        self,
        job: ETLJob,
        phase: ETLPhase,
        phase_weights: dict[ETLPhase, float],
        completed_weight: float,
        records_in_phase: int,
    ) -> None:
        """Update job progress calculations.

        Args:
            job: Current job.
            phase: Current phase.
            phase_weights: Weight of each phase for overall progress.
            completed_weight: Sum of weights of completed phases.
            records_in_phase: Records processed in current phase.
        """
        # Estimate progress within phase (using a default estimate if unknown)
        phase_weight = phase_weights.get(phase, 0.1)
        estimated_total = job.progress.total_records_estimate or 1000

        phase_progress = min(records_in_phase / estimated_total, 1.0)
        job.progress.phase_progress_percent = phase_progress * 100

        # Calculate overall progress
        overall = completed_weight + (phase_weight * phase_progress)
        job.progress.overall_progress_percent = min(overall * 100, 99.9)

    async def _publish_progress(self, job: ETLJob) -> None:
        """Publish job progress event.

        Args:
            job: Current job.
        """
        if not job.config.enable_progress_events:
            return

        try:
            service = get_event_stream_service()
            await service.publish_job_event(
                job_id=job.job_id,
                event_type=EventType.JOB_PROGRESS,
                data={
                    "state": job.state.value,
                    "progress": job.progress.to_dict(),
                    "statistics": job.statistics.to_dict(),
                },
            )
        except Exception as e:
            logger.debug(f"Failed to publish progress event: {e}")

    async def _publish_completion(self, job: ETLJob) -> None:
        """Publish job completion event.

        Args:
            job: Completed job.
        """
        if not job.config.enable_progress_events:
            return

        try:
            service = get_event_stream_service()
            await service.publish_job_event(
                job_id=job.job_id,
                event_type=EventType.JOB_COMPLETE,
                data={
                    "state": job.state.value,
                    "statistics": job.statistics.to_dict(),
                    "error_count": len(job.errors),
                    "warning_count": len(job.warnings),
                    "duration_seconds": job.duration_seconds,
                },
            )
        except Exception as e:
            logger.debug(f"Failed to publish completion event: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get orchestrator statistics.

        Returns:
            Dictionary with service statistics.
        """
        jobs_by_state = {state.value: 0 for state in ETLJobState}
        for job in self._jobs.values():
            jobs_by_state[job.state.value] += 1

        return {
            "total_jobs": len(self._jobs),
            "jobs_by_state": jobs_by_state,
            "running_tasks": len(self._running_tasks),
        }


# ============================================================================
# Singleton Management
# ============================================================================

_etl_orchestrator: ETLOrchestrator | None = None


def get_etl_orchestrator(
    session: AsyncSession | None = None,
    vocabulary_service: Any | None = None,
) -> ETLOrchestrator:
    """Get or create the global ETLOrchestrator singleton.

    Args:
        session: SQLAlchemy async session (required on first call).
        vocabulary_service: Optional vocabulary service for concept mapping.

    Returns:
        The global ETLOrchestrator instance.
    """
    global _etl_orchestrator
    if _etl_orchestrator is None:
        _etl_orchestrator = ETLOrchestrator(session, vocabulary_service)
    return _etl_orchestrator


def reset_etl_orchestrator() -> None:
    """Reset the global ETLOrchestrator singleton.

    Useful for testing.
    """
    global _etl_orchestrator
    _etl_orchestrator = None
