"""Synthea synthetic patient data ingestion background job."""

from __future__ import annotations

import logging

from app.services.synthea_ingestion import SyntheaIngestionService
from app.schemas.synthea import SyntheaImportConfig

logger = logging.getLogger(__name__)


def run_synthea_import(
    csv_dir: str,
    batch_id: str,
    chunk_size: int = 100,
    max_patients: int | None = None,
    max_encounters_per_patient: int | None = None,
    skip_duplicates: bool = True,
    enqueue_processing: bool = True,
    total_rows: int = 0,
) -> dict:
    """Background job to ingest Synthea CSV directory."""
    logger.info(f"Starting Synthea import batch_id={batch_id}, csv_dir={csv_dir}")

    try:
        from app.core.redis import get_redis
        redis = get_redis()
    except Exception:
        redis = None

    key = f"synthea_import:{batch_id}"

    def _set_progress(status: str, **kwargs: object) -> None:
        if redis is None:
            return
        data = {"status": status, "total_rows": str(total_rows), **{k: str(v) for k, v in kwargs.items()}}
        redis.hset(key, mapping=data)
        redis.expire(key, 86400)

    _set_progress("processing", processed=0, created=0, skipped=0, failed=0)

    config = SyntheaImportConfig(
        chunk_size=chunk_size,
        max_patients=max_patients,
        max_encounters_per_patient=max_encounters_per_patient,
        skip_duplicates=skip_duplicates,
        enqueue_processing=enqueue_processing,
    )

    service = SyntheaIngestionService()

    def progress_callback(processed: int, created: int, skipped: int, failed: int) -> None:
        _set_progress("processing", processed=processed, created=created, skipped=skipped, failed=failed)

    try:
        result = service.ingest_directory(csv_dir, config, batch_id, progress_callback)
        _set_progress(
            "completed",
            processed=result["processed"],
            created=result["created"],
            skipped=result["skipped"],
            failed=result["failed"],
        )
        logger.info(f"Synthea import completed batch_id={batch_id}: {result}")
        return result

    except Exception as e:
        logger.exception(f"Synthea import failed batch_id={batch_id}: {e}")
        _set_progress("failed", error=str(e)[:500])
        return {"processed": 0, "created": 0, "skipped": 0, "failed": 0, "error": str(e)}
