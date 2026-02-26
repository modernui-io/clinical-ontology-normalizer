"""Document Core API endpoints - CRUD operations.

Multi-tenancy: When auth is enabled, documents are scoped to the
authenticated user via owner_id. Admins see all documents.
When auth is disabled, all documents are visible (backward compatible).
"""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import (
    ErrorCode,
    InternalError,
    NotFoundError,
    create_not_found_error,
)
from app.api.middleware.auth_middleware import CurrentUser, get_current_user_optional
from app.core.database import get_db
from app.core.queue import QUEUE_NAMES, enqueue_job
from app.jobs import process_document
from app.models import Document as DocumentModel
from app.models.mention import Mention as MentionModel
from app.schemas import DocumentCreate, JobStatus
from app.schemas.document import Document, DocumentUploadResponse
from app.schemas.mention import Mention
from app.services.nlp_rule_based import RuleBasedNLPService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])

# Type alias for database session dependency (avoids B008 linting issue)
DbSession = Annotated[AsyncSession, Depends(get_db)]


def _apply_owner_filter(stmt, user: CurrentUser | None):
    """Apply owner_id scoping to a query statement.

    - No user (auth disabled): no filter, show all documents.
    - Admin user: no filter, admins see everything.
    - Regular user: filter to owner_id == user.id.
    """
    if user is not None and not user.is_admin():
        stmt = stmt.where(DocumentModel.owner_id == user.id)
    return stmt


class DocumentListResponse(BaseModel):
    """Paginated list of documents."""

    documents: list[Document]
    total: int
    page: int
    page_size: int


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List clinical documents",
    description="Retrieve a paginated list of clinical documents. Scoped to the current user unless admin.",
)
async def list_documents(
    db: DbSession,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    patient_id: str | None = Query(None, description="Filter by patient ID"),
    current_user: CurrentUser | None = Depends(get_current_user_optional),
) -> DocumentListResponse:
    """List clinical documents with pagination.

    When authenticated as a regular user, returns only documents owned by
    that user. Admins see all documents. When auth is disabled, all
    documents are returned.

    Args:
        db: Database session.
        page: Page number (1-indexed).
        page_size: Number of documents per page.
        current_user: Authenticated user (None if auth disabled).

    Returns:
        DocumentListResponse with documents, total count, and pagination info.
    """
    offset = (page - 1) * page_size

    # Count total (excluding soft-deleted), scoped to user
    count_stmt = select(func.count(DocumentModel.id)).where(
        DocumentModel.deleted_at.is_(None)
    )
    if patient_id:
        count_stmt = count_stmt.where(DocumentModel.patient_id == patient_id)
    count_stmt = _apply_owner_filter(count_stmt, current_user)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    # Fetch page of documents, scoped to user
    stmt = (
        select(DocumentModel)
        .where(DocumentModel.deleted_at.is_(None))
        .order_by(DocumentModel.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    if patient_id:
        stmt = stmt.where(DocumentModel.patient_id == patient_id)
    stmt = _apply_owner_filter(stmt, current_user)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    documents = [
        Document(
            id=UUID(row.id),
            patient_id=row.patient_id,
            note_type=row.note_type,
            text=row.text,
            metadata=row.extra_metadata,
            owner_id=row.owner_id,
            status=row.status,
            job_id=row.job_id,
            created_at=row.created_at,
            processed_at=row.processed_at,
        )
        for row in rows
    ]

    return DocumentListResponse(
        documents=documents,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a clinical document",
    description="Upload a clinical note for NLP processing. Returns document ID and job ID for tracking.",
)
async def upload_document(
    document: DocumentCreate,
    db: DbSession,
    current_user: CurrentUser | None = Depends(get_current_user_optional),
) -> DocumentUploadResponse:
    """Upload a clinical document for processing.

    Creates a new document record and queues it for NLP processing.
    The job_id can be used to track processing status. If authenticated,
    the document is tagged with the current user's ID for multi-tenancy.

    Args:
        document: The document to upload.
        db: Database session.
        current_user: Authenticated user (None if auth disabled).

    Returns:
        DocumentUploadResponse with document_id and job_id.
    """
    # Generate job_id upfront
    job_id = uuid4()

    # Create document record with job_id and owner
    db_document = DocumentModel(
        patient_id=document.patient_id,
        note_type=document.note_type,
        text=document.text,
        extra_metadata=document.metadata,
        status=JobStatus.QUEUED,
        job_id=job_id,
        owner_id=current_user.id if current_user else None,
    )
    db.add(db_document)
    await db.flush()  # Get the ID without committing

    # Enqueue processing job
    try:
        enqueue_job(
            process_document,
            str(db_document.id),
            queue_name=QUEUE_NAMES["document"],
            job_id=job_id,
        )
        logger.info(f"Enqueued document processing job {job_id} for document {db_document.id}")
    except ImportError:
        # RQ not available - job won't be processed but API still works
        logger.warning("RQ not available, document will not be processed automatically")
    except Exception as e:
        # Redis not available - log warning but don't fail the upload
        logger.warning(f"Failed to enqueue job: {e}. Document saved but not queued.")

    return DocumentUploadResponse(
        document_id=UUID(db_document.id),
        job_id=job_id,
        status=JobStatus.QUEUED,
    )


@router.get(
    "/{doc_id}",
    response_model=Document,
    summary="Get a clinical document",
    description="Retrieve a clinical document by its ID. Scoped to the current user unless admin.",
)
async def get_document(
    doc_id: UUID,
    db: DbSession,
    current_user: CurrentUser | None = Depends(get_current_user_optional),
) -> Document:
    """Retrieve a clinical document by ID.

    Returns 404 if the document doesn't exist or doesn't belong to
    the current user (unless admin or auth disabled).

    Args:
        doc_id: The UUID of the document to retrieve.
        db: Database session.
        current_user: Authenticated user (None if auth disabled).

    Returns:
        Document with all fields including processing status.

    Raises:
        HTTPException: 404 if document not found or not owned by user.
    """
    stmt = select(DocumentModel).where(DocumentModel.id == str(doc_id))
    stmt = _apply_owner_filter(stmt, current_user)
    result = await db.execute(stmt)
    document = result.scalar_one_or_none()

    if document is None:
        raise create_not_found_error("Document", str(doc_id))

    return Document(
        id=UUID(document.id),
        patient_id=document.patient_id,
        note_type=document.note_type,
        text=document.text,
        metadata=document.extra_metadata,
        owner_id=document.owner_id,
        status=document.status,
        job_id=document.job_id,
        created_at=document.created_at,
        processed_at=document.processed_at,
    )


@router.get(
    "/{doc_id}/mentions",
    response_model=list[Mention],
    summary="Get document mentions",
    description="Retrieve all extracted mentions for a document. Scoped to the current user unless admin.",
)
async def get_document_mentions(
    doc_id: UUID,
    db: DbSession,
    current_user: CurrentUser | None = Depends(get_current_user_optional),
) -> list[Mention]:
    """Get all mentions extracted from a document.

    Args:
        doc_id: The UUID of the document.
        db: Database session.
        current_user: Authenticated user (None if auth disabled).

    Returns:
        List of Mention objects with text spans and attributes.

    Raises:
        HTTPException: 404 if document not found or not owned by user.
    """
    # Verify document exists and user has access
    stmt = select(DocumentModel).where(DocumentModel.id == str(doc_id))
    stmt = _apply_owner_filter(stmt, current_user)
    result = await db.execute(stmt)
    document = result.scalar_one_or_none()

    if document is None:
        raise create_not_found_error("Document", str(doc_id))

    # Get all mentions for this document
    stmt = select(MentionModel).where(MentionModel.document_id == str(doc_id))
    result = await db.execute(stmt)
    mentions = result.scalars().all()

    return [
        Mention(
            id=UUID(m.id),
            document_id=UUID(m.document_id),
            text=m.text,
            start_offset=m.start_offset,
            end_offset=m.end_offset,
            lexical_variant=m.lexical_variant,
            section=m.section,
            assertion=m.assertion,
            temporality=m.temporality,
            experiencer=m.experiencer,
            confidence=m.confidence,
            created_at=m.created_at,
        )
        for m in mentions
    ]


class ExtractPreviewRequest(BaseModel):
    """Request body for live extraction preview."""

    text: str = Field(..., description="Clinical note text to extract from")
    note_type: str | None = Field(None, description="Type of clinical note")


class ExtractedMentionPreview(BaseModel):
    """Preview of an extracted mention (without database IDs)."""

    text: str = Field(..., description="The extracted text span")
    start_offset: int = Field(..., description="Character start position")
    end_offset: int = Field(..., description="Character end position")
    lexical_variant: str = Field(..., description="Normalized form from vocabulary")
    section: str | None = Field(None, description="Clinical section detected")
    assertion: str = Field(..., description="Assertion status (present/absent/possible)")
    temporality: str = Field(..., description="Temporal context (current/past/future)")
    experiencer: str = Field(..., description="Who it applies to (patient/family/other)")
    confidence: float = Field(..., description="Extraction confidence 0.0-1.0")
    domain: str | None = Field(None, description="OMOP domain hint")
    omop_concept_id: int | None = Field(None, description="Matched OMOP concept ID")


class ExtractPreviewResponse(BaseModel):
    """Response from live extraction preview."""

    mentions: list[ExtractedMentionPreview] = Field(..., description="Extracted mentions")
    extraction_time_ms: float = Field(..., description="Time taken for extraction in ms")
    mention_count: int = Field(..., description="Total number of mentions extracted")


@router.post(
    "/preview/extract",
    response_model=ExtractPreviewResponse,
    summary="Preview extraction without saving",
    description="Run NLP extraction on text and return results without saving to database.",
)
async def preview_extraction(
    request: ExtractPreviewRequest,
) -> ExtractPreviewResponse:
    """Run live extraction preview on clinical text.

    This endpoint runs the NLP extraction pipeline on the provided text
    and returns the extracted mentions WITHOUT saving them to the database.
    Useful for testing extraction quality and previewing results.

    Args:
        request: The text to extract from.

    Returns:
        ExtractPreviewResponse with extracted mentions and timing.
    """
    import time

    # Initialize NLP service
    nlp_service = RuleBasedNLPService()

    # Run extraction with timing
    start_time = time.perf_counter()
    extracted = nlp_service.extract_mentions(
        text=request.text,
        document_id=uuid4(),  # Dummy ID for preview
        note_type=request.note_type,
    )
    extraction_time_ms = (time.perf_counter() - start_time) * 1000

    # Convert to preview format
    mentions = [
        ExtractedMentionPreview(
            text=m.text,
            start_offset=m.start_offset,
            end_offset=m.end_offset,
            lexical_variant=m.lexical_variant,
            section=m.section,
            assertion=m.assertion.value,
            temporality=m.temporality.value,
            experiencer=m.experiencer.value,
            confidence=m.confidence,
            domain=m.domain_hint,
            omop_concept_id=m.omop_concept_id,
        )
        for m in extracted
    ]

    return ExtractPreviewResponse(
        mentions=mentions,
        extraction_time_ms=round(extraction_time_ms, 2),
        mention_count=len(mentions),
    )
