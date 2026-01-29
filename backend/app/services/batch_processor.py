"""Batch Processing Service.

Handles batch document uploads and processing with:
- Parallel processing
- Progress tracking
- Error handling and retry
- Status reporting
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import defaultdict
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================


class BatchStatus(Enum):
    """Status of a batch job."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"  # Some succeeded, some failed


class DocumentStatus(Enum):
    """Status of a document in a batch."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class BatchDocument:
    """A document in a batch job."""

    document_id: str
    filename: str
    content: str | bytes | None = None
    content_type: str = "text/plain"
    status: DocumentStatus = DocumentStatus.QUEUED
    progress: float = 0.0
    error: str | None = None
    result: dict[str, Any] | None = None
    started_at: str | None = None
    completed_at: str | None = None
    processing_time_ms: float = 0.0


@dataclass
class BatchJob:
    """A batch processing job."""

    job_id: str
    status: BatchStatus = BatchStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str | None = None
    completed_at: str | None = None

    # Documents
    documents: list[BatchDocument] = field(default_factory=list)
    total_documents: int = 0
    processed_documents: int = 0
    successful_documents: int = 0
    failed_documents: int = 0

    # Progress
    progress_percent: float = 0.0
    current_document: str | None = None
    estimated_remaining_seconds: float | None = None

    # Configuration
    patient_id: str | None = None
    processing_options: dict[str, Any] = field(default_factory=dict)

    # Results
    summary: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


@dataclass
class BatchProgress:
    """Progress update for a batch job."""

    job_id: str
    status: BatchStatus
    progress_percent: float
    processed: int
    total: int
    current_document: str | None = None
    estimated_remaining_seconds: float | None = None
    recent_results: list[dict] = field(default_factory=list)


# ============================================================================
# Batch Processing Service
# ============================================================================


class BatchProcessorService:
    """Service for batch document processing."""

    def __init__(
        self,
        max_workers: int = 4,
        max_concurrent_batches: int = 10,
    ):
        """
        Initialize the batch processor.

        Args:
            max_workers: Maximum parallel workers per batch
            max_concurrent_batches: Maximum concurrent batch jobs
        """
        self._max_workers = max_workers
        self._max_concurrent_batches = max_concurrent_batches
        self._jobs: dict[str, BatchJob] = {}
        self._executors: dict[str, ThreadPoolExecutor] = {}
        self._futures: dict[str, list[Future]] = defaultdict(list)
        self._lock = threading.Lock()
        self._progress_callbacks: dict[str, list[Callable]] = defaultdict(list)

    def create_batch(
        self,
        documents: list[dict[str, Any]],
        patient_id: str | None = None,
        processing_options: dict[str, Any] | None = None,
    ) -> BatchJob:
        """
        Create a new batch job.

        Args:
            documents: List of documents with filename and content
            patient_id: Optional patient ID for all documents
            processing_options: Processing configuration

        Returns:
            Created batch job
        """
        job_id = f"BATCH-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"

        batch_docs = []
        for i, doc in enumerate(documents):
            doc_id = doc.get("document_id", f"{job_id}-DOC-{i:04d}")
            batch_docs.append(BatchDocument(
                document_id=doc_id,
                filename=doc.get("filename", f"document_{i}.txt"),
                content=doc.get("content"),
                content_type=doc.get("content_type", "text/plain"),
            ))

        job = BatchJob(
            job_id=job_id,
            documents=batch_docs,
            total_documents=len(batch_docs),
            patient_id=patient_id,
            processing_options=processing_options or {},
        )

        with self._lock:
            if len([j for j in self._jobs.values() if j.status == BatchStatus.PROCESSING]) >= self._max_concurrent_batches:
                raise RuntimeError("Maximum concurrent batches reached")
            self._jobs[job_id] = job

        return job

    def start_batch(
        self,
        job_id: str,
        processor: Callable[[BatchDocument], dict[str, Any]],
    ) -> BatchJob:
        """
        Start processing a batch job.

        Args:
            job_id: ID of the batch job
            processor: Function to process each document

        Returns:
            Updated batch job
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise ValueError(f"Batch job not found: {job_id}")
            if job.status not in [BatchStatus.PENDING, BatchStatus.FAILED]:
                raise ValueError(f"Batch job cannot be started: {job.status}")

            job.status = BatchStatus.PROCESSING
            job.started_at = datetime.now(timezone.utc).isoformat()

        # Create executor for this job
        executor = ThreadPoolExecutor(max_workers=self._max_workers)
        self._executors[job_id] = executor

        # Submit all documents for processing
        for doc in job.documents:
            if doc.status == DocumentStatus.COMPLETED:
                continue  # Skip already completed (for retry)

            future = executor.submit(self._process_document, job_id, doc, processor)
            self._futures[job_id].append(future)

        # Start monitoring thread
        threading.Thread(
            target=self._monitor_batch,
            args=(job_id,),
            daemon=True,
        ).start()

        return job

    def _process_document(
        self,
        job_id: str,
        doc: BatchDocument,
        processor: Callable[[BatchDocument], dict[str, Any]],
    ) -> dict[str, Any]:
        """Process a single document."""
        doc.status = DocumentStatus.PROCESSING
        doc.started_at = datetime.now(timezone.utc).isoformat()
        start_time = time.time()

        try:
            result = processor(doc)
            doc.status = DocumentStatus.COMPLETED
            doc.result = result
            doc.progress = 1.0

            with self._lock:
                job = self._jobs[job_id]
                job.processed_documents += 1
                job.successful_documents += 1

        except Exception as e:
            doc.status = DocumentStatus.FAILED
            doc.error = str(e)

            with self._lock:
                job = self._jobs[job_id]
                job.processed_documents += 1
                job.failed_documents += 1
                job.errors.append(f"{doc.filename}: {str(e)}")

            result = {"error": str(e)}

        finally:
            doc.completed_at = datetime.now(timezone.utc).isoformat()
            doc.processing_time_ms = (time.time() - start_time) * 1000

        # Update progress
        with self._lock:
            job = self._jobs[job_id]
            job.progress_percent = (job.processed_documents / job.total_documents) * 100
            job.current_document = None

        return result

    def _monitor_batch(self, job_id: str) -> None:
        """Monitor batch job completion."""
        futures = self._futures.get(job_id, [])

        # Wait for all futures
        for future in futures:
            try:
                future.result()
            except Exception:
                pass  # Errors already handled in _process_document

        # Finalize job
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.completed_at = datetime.now(timezone.utc).isoformat()

                if job.failed_documents == 0:
                    job.status = BatchStatus.COMPLETED
                elif job.successful_documents == 0:
                    job.status = BatchStatus.FAILED
                else:
                    job.status = BatchStatus.PARTIAL

                job.progress_percent = 100.0

                # Build summary
                job.summary = {
                    "total_documents": job.total_documents,
                    "successful": job.successful_documents,
                    "failed": job.failed_documents,
                    "total_time_seconds": self._calculate_duration(job.started_at, job.completed_at),
                    "avg_time_per_doc_ms": self._calculate_avg_time(job),
                }

        # Cleanup executor
        if job_id in self._executors:
            self._executors[job_id].shutdown(wait=False)
            del self._executors[job_id]

        # Notify callbacks
        self._notify_progress(job_id)

    def _calculate_duration(self, start: str | None, end: str | None) -> float:
        """Calculate duration in seconds."""
        if not start or not end:
            return 0.0
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
        return (end_dt - start_dt).total_seconds()

    def _calculate_avg_time(self, job: BatchJob) -> float:
        """Calculate average processing time per document."""
        times = [d.processing_time_ms for d in job.documents if d.processing_time_ms > 0]
        return sum(times) / len(times) if times else 0.0

    def get_batch_status(self, job_id: str) -> BatchJob | None:
        """Get status of a batch job."""
        with self._lock:
            return self._jobs.get(job_id)

    def get_batch_progress(self, job_id: str) -> BatchProgress | None:
        """Get progress update for a batch job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None

            # Get recent results
            recent = [
                {
                    "document_id": d.document_id,
                    "filename": d.filename,
                    "status": d.status.value,
                    "processing_time_ms": d.processing_time_ms,
                }
                for d in job.documents
                if d.status in [DocumentStatus.COMPLETED, DocumentStatus.FAILED]
            ][-5:]

            # Estimate remaining time
            remaining = None
            if job.processed_documents > 0 and job.status == BatchStatus.PROCESSING:
                avg_time = self._calculate_avg_time(job) / 1000  # Convert to seconds
                remaining_docs = job.total_documents - job.processed_documents
                remaining = avg_time * remaining_docs

            return BatchProgress(
                job_id=job_id,
                status=job.status,
                progress_percent=job.progress_percent,
                processed=job.processed_documents,
                total=job.total_documents,
                current_document=job.current_document,
                estimated_remaining_seconds=remaining,
                recent_results=recent,
            )

    def cancel_batch(self, job_id: str) -> bool:
        """
        Cancel a batch job.

        Args:
            job_id: ID of the batch job

        Returns:
            True if cancelled successfully
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False

            if job.status not in [BatchStatus.PENDING, BatchStatus.PROCESSING]:
                return False

            job.status = BatchStatus.CANCELLED
            job.completed_at = datetime.now(timezone.utc).isoformat()

        # Shutdown executor
        if job_id in self._executors:
            self._executors[job_id].shutdown(wait=False)
            del self._executors[job_id]

        return True

    def retry_failed(self, job_id: str, processor: Callable) -> BatchJob | None:
        """
        Retry failed documents in a batch.

        Args:
            job_id: ID of the batch job
            processor: Processing function

        Returns:
            Updated batch job
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None

            if job.status not in [BatchStatus.PARTIAL, BatchStatus.FAILED]:
                return None

            # Reset failed documents
            for doc in job.documents:
                if doc.status == DocumentStatus.FAILED:
                    doc.status = DocumentStatus.QUEUED
                    doc.error = None
                    doc.result = None

            job.status = BatchStatus.PENDING
            job.failed_documents = 0
            job.errors.clear()

        return self.start_batch(job_id, processor)

    def list_batches(
        self,
        status: BatchStatus | None = None,
        limit: int = 50,
    ) -> list[BatchJob]:
        """
        List batch jobs.

        Args:
            status: Filter by status
            limit: Maximum number of jobs to return

        Returns:
            List of batch jobs
        """
        with self._lock:
            jobs = list(self._jobs.values())

        if status:
            jobs = [j for j in jobs if j.status == status]

        # Sort by creation time descending
        jobs.sort(key=lambda j: j.created_at, reverse=True)

        return jobs[:limit]

    def subscribe_progress(
        self,
        job_id: str,
        callback: Callable[[BatchProgress], None],
    ) -> None:
        """Subscribe to progress updates for a batch job."""
        self._progress_callbacks[job_id].append(callback)

    def _notify_progress(self, job_id: str) -> None:
        """Notify all progress subscribers."""
        progress = self.get_batch_progress(job_id)
        if progress:
            for callback in self._progress_callbacks.get(job_id, []):
                try:
                    callback(progress)
                except Exception:
                    pass

    def cleanup_completed(self, older_than_hours: int = 24) -> int:
        """
        Clean up completed batch jobs.

        Args:
            older_than_hours: Remove jobs older than this

        Returns:
            Number of jobs removed
        """
        cutoff = datetime.now(timezone.utc).isoformat()
        removed = 0

        with self._lock:
            to_remove = []
            for job_id, job in self._jobs.items():
                if job.status in [BatchStatus.COMPLETED, BatchStatus.CANCELLED, BatchStatus.FAILED]:
                    if job.completed_at:
                        completed = datetime.fromisoformat(job.completed_at)
                        if (datetime.now(timezone.utc) - completed).total_seconds() > older_than_hours * 3600:
                            to_remove.append(job_id)

            for job_id in to_remove:
                del self._jobs[job_id]
                removed += 1

        return removed

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        with self._lock:
            by_status = defaultdict(int)
            for job in self._jobs.values():
                by_status[job.status.value] += 1

            return {
                "total_jobs": len(self._jobs),
                "by_status": dict(by_status),
                "max_workers": self._max_workers,
                "max_concurrent_batches": self._max_concurrent_batches,
                "active_executors": len(self._executors),
            }


# ============================================================================
# Singleton Pattern
# ============================================================================


_service_instance: BatchProcessorService | None = None
_service_lock = threading.Lock()


def get_batch_processor_service() -> BatchProcessorService:
    """Get or create the singleton service instance."""
    global _service_instance

    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = BatchProcessorService()

    return _service_instance


def reset_batch_processor_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _service_instance
    with _service_lock:
        _service_instance = None
