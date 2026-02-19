"""MTSamples CSV ingestion background job."""

from __future__ import annotations

import logging

from app.services.mtsamples_ingestion import MtsamplesIngestionService
from app.schemas.mtsamples import MtsamplesImportConfig

logger = logging.getLogger(__name__)


def run_mtsamples_import(
    csv_content: str,
    batch_id: str,
    chunk_size: int = 100,
    max_rows: int | None = None,
    skip_duplicates: bool = True,
    enqueue_processing: bool = True,
    total_rows: int = 0,
) -> dict:
    """Background job to ingest an MTSamples CSV."""
    logger.info(f"Starting MTSamples import batch_id={batch_id}, total_rows={total_rows}")

    try:
        from app.core.redis import get_redis
        redis = get_redis()
    except Exception:
        redis = None

    key = f"mtsamples_import:{batch_id}"

    def _set_progress(status: str, **kwargs: object) -> None:
        if redis is None:
            return
        data = {"status": status, "total_rows": str(total_rows), **{k: str(v) for k, v in kwargs.items()}}
        redis.hset(key, mapping=data)
        redis.expire(key, 86400)

    _set_progress("processing", processed=0, created=0, skipped=0, failed=0)

    config = MtsamplesImportConfig(
        chunk_size=chunk_size,
        max_rows=max_rows,
        skip_duplicates=skip_duplicates,
        enqueue_processing=enqueue_processing,
    )

    service = MtsamplesIngestionService()

    def progress_callback(processed: int, created: int, skipped: int, failed: int) -> None:
        _set_progress("processing", processed=processed, created=created, skipped=skipped, failed=failed)

    try:
        result = service.ingest_csv(csv_content, config, batch_id, progress_callback)
        _set_progress(
            "completed",
            processed=result["processed"],
            created=result["created"],
            skipped=result["skipped"],
            failed=result["failed"],
        )
        logger.info(f"MTSamples import completed batch_id={batch_id}: {result}")
        return result

    except Exception as e:
        logger.exception(f"MTSamples import failed batch_id={batch_id}: {e}")
        _set_progress("failed", error=str(e)[:500])
        return {"processed": 0, "created": 0, "skipped": 0, "failed": 0, "error": str(e)}
