"""Reprocessing Service for failed clinical notes.

P2-021: Provides deterministic reprocessing of documents that failed
NLP extraction, with idempotency guards and error tracking.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.schemas.base import JobStatus

logger = logging.getLogger(__name__)


class ReprocessingStatus(str, Enum):
    """Outcome of a reprocessing attempt."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class FailedNote:
    """A document that failed processing."""

    document_id: str
    patient_id: str
    note_type: str
    status: str
    error: str | None = None


@dataclass
class ReprocessingResult:
    """Result of a single reprocessing attempt."""

    document_id: str
    status: ReprocessingStatus
    error: str | None = None
    previous_error: str | None = None


class ReprocessingService:
    """Service for managing reprocessing of failed documents.

    Provides methods to query failed documents and re-submit them
    to the processing pipeline. Enforces idempotency by skipping
    documents that already completed unless force=True.
    """

    async def get_failed_notes(
        self,
        session: AsyncSession,
        patient_id: str | None = None,
    ) -> list[FailedNote]:
        """Get all documents with FAILED status.

        Args:
            session: Async database session.
            patient_id: Optional patient filter. If None, returns all failed.

        Returns:
            List of FailedNote with document details and error info.
        """
        query = select(Document).where(Document.status == JobStatus.FAILED)
        if patient_id is not None:
            query = query.where(Document.patient_id == patient_id)

        result = await session.execute(query)
        documents = result.scalars().all()

        notes: list[FailedNote] = []
        for doc in documents:
            error = None
            if doc.extra_metadata and isinstance(doc.extra_metadata, dict):
                error = doc.extra_metadata.get("error")

            notes.append(
                FailedNote(
                    document_id=str(doc.id),
                    patient_id=doc.patient_id,
                    note_type=doc.note_type,
                    status=doc.status.value if hasattr(doc.status, "value") else str(doc.status),
                    error=error,
                )
            )

        logger.info(
            "Found %d failed notes%s",
            len(notes),
            f" for patient_id={patient_id}" if patient_id else "",
        )
        return notes

    async def reprocess_note(
        self,
        session: AsyncSession,
        document_id: str,
        *,
        force: bool = False,
    ) -> ReprocessingResult:
        """Reprocess a single document through the extraction pipeline.

        Idempotency: if the document is already COMPLETED and force=False,
        the reprocessing is skipped. If force=True, the document is reset
        to QUEUED regardless of current status.

        Args:
            session: Async database session.
            document_id: UUID of the document to reprocess.
            force: If True, reprocess even if already completed.

        Returns:
            ReprocessingResult with outcome details.
        """
        query = select(Document).where(Document.id == document_id)
        result = await session.execute(query)
        document = result.scalar_one_or_none()

        if document is None:
            logger.warning("Document not found for reprocessing: %s", document_id)
            return ReprocessingResult(
                document_id=document_id,
                status=ReprocessingStatus.FAILED,
                error="Document not found",
            )

        current_status = (
            document.status.value
            if hasattr(document.status, "value")
            else str(document.status)
        )

        # Capture previous error from metadata
        previous_error = None
        if document.extra_metadata and isinstance(document.extra_metadata, dict):
            previous_error = document.extra_metadata.get("error")

        # Idempotency: skip if already completed (unless forced)
        if current_status == JobStatus.COMPLETED.value and not force:
            logger.info(
                "Skipping reprocessing for already-completed document %s (use force=True to override)",
                document_id,
            )
            return ReprocessingResult(
                document_id=document_id,
                status=ReprocessingStatus.SKIPPED,
                previous_error=previous_error,
            )

        # Reset document to QUEUED for reprocessing
        try:
            document.status = JobStatus.QUEUED
            document.processed_at = None
            # Preserve error history in metadata
            meta = dict(document.extra_metadata) if document.extra_metadata else {}
            if previous_error:
                meta["previous_error"] = previous_error
                meta.pop("error", None)
            document.extra_metadata = meta

            await session.flush()

            logger.info(
                "Document %s reset to QUEUED for reprocessing (previous_status=%s)",
                document_id,
                current_status,
            )

            return ReprocessingResult(
                document_id=document_id,
                status=ReprocessingStatus.SUCCESS,
                previous_error=previous_error,
            )

        except Exception as e:
            logger.exception("Failed to reprocess document %s: %s", document_id, e)
            return ReprocessingResult(
                document_id=document_id,
                status=ReprocessingStatus.FAILED,
                error=str(e),
                previous_error=previous_error,
            )


# Module-level singleton
_service: ReprocessingService | None = None


def get_reprocessing_service() -> ReprocessingService:
    """Get or create the reprocessing service singleton."""
    global _service
    if _service is None:
        _service = ReprocessingService()
    return _service


def reset_reprocessing_service() -> None:
    """Reset the singleton (for testing)."""
    global _service
    _service = None
