"""Job functions for background processing with RQ."""

from __future__ import annotations

from app.jobs.document_processing import process_document

__all__ = ["process_document"]
