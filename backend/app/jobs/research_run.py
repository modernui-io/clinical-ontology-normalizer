"""Background job for research experiment runs."""

from __future__ import annotations

import logging
import time

from app.models.research_experiment import ExperimentRunStatus
from app.schemas.research import RunCreate
from app.services.research_service import get_research_service

logger = logging.getLogger(__name__)


def run_research_experiment(
    run_id: str,
    experiment_id: str,
    mimic_csv_path: str | None = None,
    max_rows: int | None = None,
    chunk_size: int = 100,
    run_config: dict | None = None,
) -> dict:
    """Background job to execute a research experiment run.

    Steps:
    1. Import MIMIC data (if csv_path provided)
    2. Wait for document processing pipeline to complete
    3. Collect metrics (assertions, mapping, KG, timing)
    4. Mark run as completed
    """
    service = get_research_service()

    try:
        # Update run status to processing
        service.update_run_status(run_id, ExperimentRunStatus.PROCESSING)

        batch_id = None
        document_ids: list[str] = []
        patient_ids: list[str] = []

        # Step 1: Import MIMIC data if path provided
        if mimic_csv_path:
            try:
                from app.services.mimic_ingestion import MimicIngestionService
                from app.schemas.mimic import MimicImportConfig
                from uuid import uuid4

                mimic_service = MimicIngestionService()
                batch_id = str(uuid4())

                with open(mimic_csv_path) as f:
                    csv_content = f.read()

                config = MimicImportConfig(
                    chunk_size=chunk_size,
                    max_rows=max_rows,
                    skip_duplicates=True,
                    enqueue_processing=True,
                )

                start_time = time.perf_counter()
                result = mimic_service.ingest_csv(csv_content, config, batch_id)
                ingest_time_ms = (time.perf_counter() - start_time) * 1000

                logger.info(
                    f"Research run {run_id}: MIMIC ingest complete - "
                    f"{result['created']} docs in {ingest_time_ms:.0f}ms"
                )

                # Record ingest timing metric
                service.record_metric(
                    run_id=run_id,
                    category="timing",
                    metric_name="ingest_time_ms",
                    metric_value=ingest_time_ms,
                    detail=result,
                )

                # Collect document and patient IDs from ingested docs
                from sqlalchemy import select
                from sqlalchemy.orm import Session
                from app.core.database import get_sync_engine
                from app.models.document import Document

                with Session(get_sync_engine()) as session:
                    docs = session.scalars(
                        select(Document).where(
                            Document.extra_metadata["mimic_batch_id"].astext == batch_id
                        )
                    ).all()
                    document_ids = [d.id for d in docs]
                    patient_ids = list({d.patient_id for d in docs if d.patient_id})

            except Exception as e:
                logger.error(f"Research run {run_id}: MIMIC ingest failed: {e}")
                service.update_run_status(
                    run_id, ExperimentRunStatus.FAILED, error=str(e)[:500]
                )
                return {"status": "failed", "error": str(e)}

        # Update run with collected IDs
        service.update_run_status(
            run_id,
            ExperimentRunStatus.PROCESSING,
            document_ids=document_ids,
            patient_ids=patient_ids,
        )

        # Update mimic_batch_id on the run
        if batch_id:
            from sqlalchemy.orm import Session
            from app.core.database import get_sync_engine
            from app.models.research_experiment import ResearchExperimentRun

            with Session(get_sync_engine()) as session:
                run = session.get(ResearchExperimentRun, run_id)
                if run:
                    run.mimic_batch_id = batch_id
                    session.commit()

        # Step 2: Collect assertion analytics
        try:
            analytics = service.get_assertion_analytics(run_id)
            service.record_metric(
                run_id=run_id,
                category="assertion",
                metric_name="total_mentions",
                metric_value=float(analytics.total_mentions),
                detail={"assertion_counts": analytics.assertion_counts},
            )
            for assertion_type, count in analytics.assertion_counts.items():
                service.record_metric(
                    run_id=run_id,
                    category="assertion",
                    metric_name=f"assertion_{assertion_type}",
                    metric_value=float(count),
                )
        except Exception as e:
            logger.warning(f"Research run {run_id}: assertion analytics failed: {e}")

        # Step 3: Collect mapping quality
        try:
            mapping = service.get_mapping_quality(run_id)
            service.record_metric(
                run_id=run_id,
                category="mapping",
                metric_name="coverage_percent",
                metric_value=mapping.coverage_percent,
            )
            service.record_metric(
                run_id=run_id,
                category="mapping",
                metric_name="avg_confidence",
                metric_value=mapping.avg_confidence,
            )
            service.record_metric(
                run_id=run_id,
                category="mapping",
                metric_name="mapped_count",
                metric_value=float(mapping.mapped_count),
            )
            service.record_metric(
                run_id=run_id,
                category="mapping",
                metric_name="unmapped_count",
                metric_value=float(mapping.unmapped_count),
            )
        except Exception as e:
            logger.warning(f"Research run {run_id}: mapping quality failed: {e}")

        # Step 4: Collect KG metrics
        try:
            kg = service.get_kg_metrics(run_id)
            service.record_metric(
                run_id=run_id,
                category="kg",
                metric_name="total_nodes",
                metric_value=float(kg.total_nodes),
            )
            service.record_metric(
                run_id=run_id,
                category="kg",
                metric_name="total_edges",
                metric_value=float(kg.total_edges),
            )
            service.record_metric(
                run_id=run_id,
                category="kg",
                metric_name="unique_concepts",
                metric_value=float(kg.unique_concepts),
            )
            service.record_metric(
                run_id=run_id,
                category="kg",
                metric_name="avg_nodes_per_patient",
                metric_value=kg.avg_nodes_per_patient,
            )
        except Exception as e:
            logger.warning(f"Research run {run_id}: KG metrics failed: {e}")

        # Mark run as completed
        service.update_run_status(run_id, ExperimentRunStatus.COMPLETED)

        return {
            "status": "completed",
            "run_id": run_id,
            "documents": len(document_ids),
            "patients": len(patient_ids),
        }

    except Exception as e:
        logger.exception(f"Research run {run_id} failed: {e}")
        service.update_run_status(
            run_id, ExperimentRunStatus.FAILED, error=str(e)[:500]
        )
        return {"status": "failed", "error": str(e)}
