"""VP-DevOps-5: Pipeline executor job for RQ background processing.

This module provides the background job that executes data pipeline runs.
It is called by the RQ worker when a pipeline run is enqueued.

Usage:
    # Start the RQ worker for pipeline processing:
    rq worker pipeline_processing

    # The job is automatically enqueued when POST /pipelines/{id}/run is called

Architecture:
    1. Pipeline run is created via API (PENDING status)
    2. Job is enqueued to pipeline_processing queue
    3. RQ worker picks up the job and calls execute_pipeline_run()
    4. Job fetches pipeline config and executes data source operations
    5. Status is updated to COMPLETED or FAILED

Dependencies:
    - rq: Redis Queue for background jobs
    - app.services.pipeline_service: Pipeline configuration and status management
    - app.services.data_source_service: Data source operations (fetch, transform, load)
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

logger = logging.getLogger(__name__)


def execute_pipeline_run(run_id: str) -> dict:
    """Execute a pipeline run as a background job.

    This function is called by the RQ worker. It runs synchronously
    within the worker process.

    Args:
        run_id: The UUID of the pipeline run to execute (as string)

    Returns:
        dict with execution results:
            - status: 'completed' or 'failed'
            - records_processed: number of records
            - duration_seconds: execution time
            - error: error message if failed
    """
    from sqlalchemy.orm import Session

    from app.core.database import get_sync_engine
    from app.models.pipeline import PipelineRun, PipelineRunStatus, Pipeline
    from app.services.data_source_service import DataSourceService

    start_time = datetime.now(timezone.utc)
    run_uuid = UUID(run_id)

    logger.info(f"Starting pipeline run execution: {run_id}")

    with Session(get_sync_engine()) as session:
        # Fetch the run
        run = session.query(PipelineRun).filter(PipelineRun.id == run_uuid).first()
        if not run:
            logger.error(f"Pipeline run not found: {run_id}")
            return {"status": "failed", "error": f"Run not found: {run_id}"}

        # Update status to RUNNING
        run.status = PipelineRunStatus.RUNNING
        run.started_at = start_time
        session.commit()

        try:
            # Fetch the pipeline configuration
            pipeline = session.query(Pipeline).filter(Pipeline.id == run.pipeline_id).first()
            if not pipeline:
                raise ValueError(f"Pipeline not found: {run.pipeline_id}")

            logger.info(
                f"Executing pipeline '{pipeline.name}' (run {run_id}), "
                f"source: {pipeline.source_id}"
            )

            # Execute the pipeline steps
            # This is where the actual data processing happens
            records_processed = _execute_pipeline_steps(session, pipeline, run)

            # Update status to COMPLETED
            end_time = datetime.now(timezone.utc)
            run.status = PipelineRunStatus.COMPLETED
            run.completed_at = end_time
            run.records_processed = records_processed
            session.commit()

            duration = (end_time - start_time).total_seconds()
            logger.info(
                f"Pipeline run {run_id} completed: "
                f"{records_processed} records in {duration:.2f}s"
            )

            return {
                "status": "completed",
                "records_processed": records_processed,
                "duration_seconds": duration,
            }

        except Exception as e:
            # Update status to FAILED
            end_time = datetime.now(timezone.utc)
            run.status = PipelineRunStatus.FAILED
            run.completed_at = end_time
            run.error_message = str(e)[:1000]  # Truncate long errors
            session.commit()

            duration = (end_time - start_time).total_seconds()
            logger.exception(f"Pipeline run {run_id} failed after {duration:.2f}s: {e}")

            return {
                "status": "failed",
                "error": str(e),
                "duration_seconds": duration,
            }


def _execute_pipeline_steps(session, pipeline, run) -> int:
    """Execute the actual pipeline data processing steps.

    This is a placeholder implementation. In a full implementation,
    this would:
    1. Connect to the data source (FHIR server, file, etc.)
    2. Fetch new/updated records since last run
    3. Transform records according to pipeline config
    4. Load records into the target tables
    5. Update the pipeline's last_run_at timestamp

    Args:
        session: SQLAlchemy session
        pipeline: Pipeline model instance
        run: PipelineRun model instance

    Returns:
        Number of records processed
    """
    from app.services.data_source_service import DataSourceService

    logger.info(f"Executing pipeline steps for {pipeline.name}")

    # Placeholder: In a real implementation, this would:
    # 1. Get the data source configuration
    # 2. Fetch data based on pipeline.config settings
    # 3. Transform and load the data
    # 4. Return the count of processed records

    # For now, just log and return 0 to indicate no records processed
    # This allows the infrastructure to be tested without full implementation
    logger.warning(
        f"Pipeline execution is a placeholder. "
        f"Full implementation pending for pipeline type: {pipeline.pipeline_type}"
    )

    return 0
