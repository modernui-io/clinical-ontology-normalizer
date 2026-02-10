"""Clinical Document Management API endpoints (DOC-MGMT).

Provides comprehensive document management operations: document creation, version
control, review and approval workflows, regulatory filing, document access control,
and document metrics.

Endpoints:
    GET    /document-management/documents                       - List documents
    GET    /document-management/documents/{document_id}         - Get single document
    POST   /document-management/documents                       - Create document
    PUT    /document-management/documents/{document_id}         - Update document
    DELETE /document-management/documents/{document_id}         - Delete document
    GET    /document-management/versions                        - List versions
    GET    /document-management/versions/{version_id}           - Get single version
    POST   /document-management/versions                        - Create version
    GET    /document-management/reviews                         - List reviews
    GET    /document-management/reviews/{review_id}             - Get single review
    POST   /document-management/reviews                         - Create review
    PUT    /document-management/reviews/{review_id}             - Update review
    DELETE /document-management/reviews/{review_id}             - Delete review
    GET    /document-management/filings                         - List filings
    GET    /document-management/filings/{filing_id}             - Get single filing
    POST   /document-management/filings                         - Create filing
    DELETE /document-management/filings/{filing_id}             - Delete filing
    GET    /document-management/metrics                         - Document metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.document_management import (
    AccessLevel,
    ClinicalDocument,
    ClinicalDocumentCreate,
    ClinicalDocumentListResponse,
    ClinicalDocumentUpdate,
    DocumentFiling,
    DocumentFilingCreate,
    DocumentFilingListResponse,
    DocumentManagementMetrics,
    DocumentReview,
    DocumentReviewCreate,
    DocumentReviewListResponse,
    DocumentReviewUpdate,
    DocumentStatus,
    DocumentType,
    DocumentVersion,
    DocumentVersionCreate,
    DocumentVersionListResponse,
    ReviewDecision,
)
from app.services.document_management_service import get_document_management_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/document-management",
    tags=["Document Management"],
)


# ---------------------------------------------------------------------------
# Document Management
# ---------------------------------------------------------------------------


@router.get(
    "/documents",
    response_model=ClinicalDocumentListResponse,
    summary="List clinical documents",
    description="Retrieve clinical documents with optional filtering by trial, type, status, and access level.",
)
async def list_documents(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    document_type: Optional[DocumentType] = Query(None, description="Filter by document type"),
    status: Optional[DocumentStatus] = Query(None, description="Filter by status"),
    access_level: Optional[AccessLevel] = Query(None, description="Filter by access level"),
) -> ClinicalDocumentListResponse:
    svc = get_document_management_service()
    items = svc.list_documents(
        trial_id=trial_id, document_type=document_type,
        status=status, access_level=access_level,
    )
    return ClinicalDocumentListResponse(items=items, total=len(items))


@router.get(
    "/documents/{document_id}",
    response_model=ClinicalDocument,
    summary="Get a clinical document",
)
async def get_document(document_id: str) -> ClinicalDocument:
    svc = get_document_management_service()
    document = svc.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")
    return document


@router.post(
    "/documents",
    response_model=ClinicalDocument,
    status_code=201,
    summary="Create a clinical document",
)
async def create_document(payload: ClinicalDocumentCreate) -> ClinicalDocument:
    svc = get_document_management_service()
    return svc.create_document(payload)


@router.put(
    "/documents/{document_id}",
    response_model=ClinicalDocument,
    summary="Update a clinical document",
)
async def update_document(
    document_id: str, payload: ClinicalDocumentUpdate
) -> ClinicalDocument:
    svc = get_document_management_service()
    updated = svc.update_document(document_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")
    return updated


@router.delete(
    "/documents/{document_id}",
    status_code=204,
    summary="Delete a clinical document",
)
async def delete_document(document_id: str) -> None:
    svc = get_document_management_service()
    deleted = svc.delete_document(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")


# ---------------------------------------------------------------------------
# Version Management
# ---------------------------------------------------------------------------


@router.get(
    "/versions",
    response_model=DocumentVersionListResponse,
    summary="List document versions",
    description="Retrieve document versions with optional filtering by document.",
)
async def list_versions(
    document_id: Optional[str] = Query(None, description="Filter by document ID"),
) -> DocumentVersionListResponse:
    svc = get_document_management_service()
    items = svc.list_versions(document_id=document_id)
    return DocumentVersionListResponse(items=items, total=len(items))


@router.get(
    "/versions/{version_id}",
    response_model=DocumentVersion,
    summary="Get a document version",
)
async def get_version(version_id: str) -> DocumentVersion:
    svc = get_document_management_service()
    version = svc.get_version(version_id)
    if version is None:
        raise HTTPException(status_code=404, detail=f"Version '{version_id}' not found")
    return version


@router.post(
    "/versions",
    response_model=DocumentVersion,
    status_code=201,
    summary="Create a document version",
    description="Create a new version for a document. Updates the parent document's version and timestamp.",
)
async def create_version(payload: DocumentVersionCreate) -> DocumentVersion:
    svc = get_document_management_service()
    version = svc.create_version(payload)
    if version is None:
        raise HTTPException(status_code=404, detail=f"Document '{payload.document_id}' not found")
    return version


# ---------------------------------------------------------------------------
# Review Management
# ---------------------------------------------------------------------------


@router.get(
    "/reviews",
    response_model=DocumentReviewListResponse,
    summary="List document reviews",
    description="Retrieve document reviews with optional filtering by document, reviewer, and decision.",
)
async def list_reviews(
    document_id: Optional[str] = Query(None, description="Filter by document ID"),
    reviewer: Optional[str] = Query(None, description="Filter by reviewer name"),
    decision: Optional[ReviewDecision] = Query(None, description="Filter by review decision"),
) -> DocumentReviewListResponse:
    svc = get_document_management_service()
    items = svc.list_reviews(
        document_id=document_id, reviewer=reviewer, decision=decision,
    )
    return DocumentReviewListResponse(items=items, total=len(items))


@router.get(
    "/reviews/{review_id}",
    response_model=DocumentReview,
    summary="Get a document review",
)
async def get_review(review_id: str) -> DocumentReview:
    svc = get_document_management_service()
    review = svc.get_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found")
    return review


@router.post(
    "/reviews",
    response_model=DocumentReview,
    status_code=201,
    summary="Create a document review",
    description="Create a new review for a document. Validates that the document exists.",
)
async def create_review(payload: DocumentReviewCreate) -> DocumentReview:
    svc = get_document_management_service()
    review = svc.create_review(payload)
    if review is None:
        raise HTTPException(status_code=404, detail=f"Document '{payload.document_id}' not found")
    return review


@router.put(
    "/reviews/{review_id}",
    response_model=DocumentReview,
    summary="Update a document review",
    description="Update a review. Automatically sets completed_date when a decision is provided.",
)
async def update_review(
    review_id: str, payload: DocumentReviewUpdate
) -> DocumentReview:
    svc = get_document_management_service()
    updated = svc.update_review(review_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found")
    return updated


@router.delete(
    "/reviews/{review_id}",
    status_code=204,
    summary="Delete a document review",
)
async def delete_review(review_id: str) -> None:
    svc = get_document_management_service()
    deleted = svc.delete_review(review_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found")


# ---------------------------------------------------------------------------
# Filing Management
# ---------------------------------------------------------------------------


@router.get(
    "/filings",
    response_model=DocumentFilingListResponse,
    summary="List document filings",
    description="Retrieve document filings with optional filtering by document.",
)
async def list_filings(
    document_id: Optional[str] = Query(None, description="Filter by document ID"),
) -> DocumentFilingListResponse:
    svc = get_document_management_service()
    items = svc.list_filings(document_id=document_id)
    return DocumentFilingListResponse(items=items, total=len(items))


@router.get(
    "/filings/{filing_id}",
    response_model=DocumentFiling,
    summary="Get a document filing",
)
async def get_filing(filing_id: str) -> DocumentFiling:
    svc = get_document_management_service()
    filing = svc.get_filing(filing_id)
    if filing is None:
        raise HTTPException(status_code=404, detail=f"Filing '{filing_id}' not found")
    return filing


@router.post(
    "/filings",
    response_model=DocumentFiling,
    status_code=201,
    summary="Create a document filing",
    description="Create a new filing for a document. Validates that the document exists.",
)
async def create_filing(payload: DocumentFilingCreate) -> DocumentFiling:
    svc = get_document_management_service()
    filing = svc.create_filing(payload)
    if filing is None:
        raise HTTPException(status_code=404, detail=f"Document '{payload.document_id}' not found")
    return filing


@router.delete(
    "/filings/{filing_id}",
    status_code=204,
    summary="Delete a document filing",
)
async def delete_filing(filing_id: str) -> None:
    svc = get_document_management_service()
    deleted = svc.delete_filing(filing_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Filing '{filing_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=DocumentManagementMetrics,
    summary="Get document management metrics",
    description="Aggregated document management metrics including document counts by type/status, "
                "review statistics, filing counts, and average review turnaround time.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> DocumentManagementMetrics:
    svc = get_document_management_service()
    return svc.get_metrics(trial_id=trial_id)
