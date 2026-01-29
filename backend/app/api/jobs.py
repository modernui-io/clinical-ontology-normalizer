"""Job status API endpoints."""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.queue import RQ_AVAILABLE, get_job_result, get_job_status
from app.models import Document
from app.schemas.base import JobStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])

# Type alias for database session dependency
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get(
    "/{job_id}",
    summary="Get job status",
    description="Get the current status of a background processing job.",
)
async def get_job_status_endpoint(
    job_id: UUID,
    db: DbSession,
) -> dict:
    """Get the status of a job.

    First checks the database for document status, then optionally
    queries Redis/RQ for more detailed job information.

    Args:
        job_id: The UUID of the job to check.
        db: Database session.

    Returns:
        Dictionary with job status information.
    """
    # First, try to find a document with this job_id
    stmt = select(Document).where(Document.job_id == job_id)
    result = await db.execute(stmt)
    document = result.scalar_one_or_none()

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found",
        )

    response = {
        "job_id": str(job_id),
        "document_id": document.id,
        "status": document.status.value,
        "created_at": document.created_at.isoformat() if document.created_at else None,
        "processed_at": document.processed_at.isoformat() if document.processed_at else None,
    }

    # If RQ is available, try to get more detailed job info
    if RQ_AVAILABLE:
        try:
            rq_status = get_job_status(str(job_id))
            if rq_status:
                response["rq_status"] = rq_status

            # If job is finished, include result
            if document.status == JobStatus.COMPLETED:
                job_result = get_job_result(str(job_id))
                if job_result:
                    response["result"] = job_result
        except Exception as e:
            # RQ lookup failed, but we still have DB status
            logger.warning(f"Failed to get RQ job status: {e}")

    return response


@router.get(
    "/{job_id}/result",
    summary="Get job result",
    description="Get the result of a completed job.",
)
async def get_job_result_endpoint(
    job_id: UUID,
    db: DbSession,
) -> dict:
    """Get the result of a completed job.

    Args:
        job_id: The UUID of the job to check.
        db: Database session.

    Returns:
        Dictionary with job result if completed.
    """
    # First, find the document
    stmt = select(Document).where(Document.job_id == job_id)
    result = await db.execute(stmt)
    document = result.scalar_one_or_none()

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found",
        )

    if document.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is not completed. Current status: {document.status.value}",
        )

    response = {
        "job_id": str(job_id),
        "document_id": document.id,
        "status": document.status.value,
        "processed_at": document.processed_at.isoformat() if document.processed_at else None,
    }

    # Try to get result from RQ if available
    if RQ_AVAILABLE:
        try:
            job_result = get_job_result(str(job_id))
            if job_result:
                response["result"] = job_result
        except Exception as e:
            logger.warning(f"Failed to get RQ job result: {e}")

    return response
