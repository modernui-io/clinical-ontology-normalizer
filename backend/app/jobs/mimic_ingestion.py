"""MIMIC-IV-Note CSV ingestion background job.

Follows the pattern from document_processing.py — runs as an RQ worker job,
stores progress in Redis for polling.
"""

from __future__ import annotations

import logging

from app.services.mimic_ingestion import MimicIngestionService
from app.schemas.mimic import MimicImportConfig

logger = logging.getLogger(__name__)


def run_mimic_import(
    csv_content: str,
    batch_id: str,
    chunk_size: int = 100,
    max_rows: int | None = None,
    skip_duplicates: bool = True,
    enqueue_processing: bool = True,
    total_rows: int = 0,
) -> dict:
    """Background job to ingest a MIMIC CSV.

    Stores progress in a Redis hash at key `mimic_import:{batch_id}`.

    Args:
        csv_content: Raw CSV string.
        batch_id: Unique batch identifier.
        chunk_size: Documents per batch commit.
        max_rows: Max rows to process (None = all).
        skip_duplicates: Whether to skip existing note_ids.
        enqueue_processing: Whether to enqueue NLP jobs.
        total_rows: Pre-counted total for progress tracking.

    Returns:
        Summary dict with final counts.
    """
    logger.info(f"Starting MIMIC import batch_id={batch_id}, total_rows={total_rows}")

    try:
        from app.core.redis import get_redis

        redis = get_redis()
    except Exception:
        redis = None

    key = f"mimic_import:{batch_id}"

    def _set_progress(status: str, **kwargs: object) -> None:
        if redis is None:
            return
        data = {"status": status, "total_rows": str(total_rows), **{k: str(v) for k, v in kwargs.items()}}
        redis.hset(key, mapping=data)
        redis.expire(key, 86400)  # 24h TTL

    _set_progress("processing", processed=0, created=0, skipped=0, failed=0)

    config = MimicImportConfig(
        chunk_size=chunk_size,
        max_rows=max_rows,
        skip_duplicates=skip_duplicates,
        enqueue_processing=enqueue_processing,
    )

    service = MimicIngestionService()

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
        logger.info(f"MIMIC import completed batch_id={batch_id}: {result}")
        return result

    except Exception as e:
        logger.exception(f"MIMIC import failed batch_id={batch_id}: {e}")
        _set_progress("failed", error=str(e)[:500])
        return {"processed": 0, "created": 0, "skipped": 0, "failed": 0, "error": str(e)}
