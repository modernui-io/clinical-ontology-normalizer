"""Medical Writing & CSR Generation API endpoints (CLINICAL-11).

Provides comprehensive medical writing operations: document lifecycle management
for CSRs, SAPs, protocols, and investigator brochures; ICH E3-structured section
tracking; review comment workflow; TLF shell programming/validation tracking;
overdue detection; and writing metrics/dashboards.

Endpoints:
    GET    /medical-writing/documents                         - List documents
    GET    /medical-writing/documents/{doc_id}                - Get single document
    POST   /medical-writing/documents                         - Create document
    PUT    /medical-writing/documents/{doc_id}                - Update document
    DELETE /medical-writing/documents/{doc_id}                - Delete document
    POST   /medical-writing/documents/{doc_id}/advance        - Advance document status
    GET    /medical-writing/documents/overdue                  - Overdue documents
    GET    /medical-writing/sections                           - List sections
    GET    /medical-writing/sections/{section_id}              - Get single section
    POST   /medical-writing/sections                           - Create section
    PUT    /medical-writing/sections/{section_id}              - Update section
    DELETE /medical-writing/sections/{section_id}              - Delete section
    GET    /medical-writing/comments                           - List comments
    GET    /medical-writing/comments/{comment_id}              - Get single comment
    POST   /medical-writing/comments                           - Create comment
    PUT    /medical-writing/comments/{comment_id}              - Update comment
    DELETE /medical-writing/comments/{comment_id}              - Delete comment
    GET    /medical-writing/tlf-shells                          - List TLF shells
    GET    /medical-writing/tlf-shells/{tlf_id}                - Get single TLF shell
    POST   /medical-writing/tlf-shells                          - Create TLF shell
    PUT    /medical-writing/tlf-shells/{tlf_id}                - Update TLF shell
    DELETE /medical-writing/tlf-shells/{tlf_id}                - Delete TLF shell
    GET    /medical-writing/metrics                             - Writing metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.medical_writing import (
    DocumentCreate,
    DocumentListResponse,
    DocumentSection,
    DocumentStatus,
    DocumentType,
    DocumentUpdate,
    ICHSection,
    MedicalDocument,
    ProgrammingStatus,
    ResolutionStatus,
    ReviewComment,
    ReviewCommentCreate,
    ReviewCommentListResponse,
    ReviewCommentUpdate,
    ReviewType,
    SectionCreate,
    SectionListResponse,
    SectionStatus,
    SectionUpdate,
    TLFShell,
    TLFShellCreate,
    TLFShellListResponse,
    TLFShellUpdate,
    TLFType,
    WritingMetrics,
)
from app.services.medical_writing_service import get_medical_writing_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/medical-writing",
    tags=["Medical Writing"],
)


# ---------------------------------------------------------------------------
# Document Management
# ---------------------------------------------------------------------------


@router.get(
    "/documents",
    response_model=DocumentListResponse,
    summary="List medical writing documents",
    description="Retrieve documents with optional filtering by trial, type, and status.",
)
async def list_documents(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    document_type: Optional[DocumentType] = Query(None, description="Filter by document type"),
    status: Optional[DocumentStatus] = Query(None, description="Filter by status"),
) -> DocumentListResponse:
    svc = get_medical_writing_service()
    items = svc.list_documents(trial_id=trial_id, document_type=document_type, status=status)
    return DocumentListResponse(items=items, total=len(items))


@router.get(
    "/documents/overdue",
    response_model=DocumentListResponse,
    summary="Get overdue documents",
    description="Retrieve documents past their target date that are not yet approved or submitted.",
)
async def get_overdue_documents() -> DocumentListResponse:
    svc = get_medical_writing_service()
    items = svc.get_overdue_documents()
    return DocumentListResponse(items=items, total=len(items))


@router.get(
    "/documents/{doc_id}",
    response_model=MedicalDocument,
    summary="Get a medical writing document",
)
async def get_document(doc_id: str) -> MedicalDocument:
    svc = get_medical_writing_service()
    doc = svc.get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")
    return doc


@router.post(
    "/documents",
    response_model=MedicalDocument,
    status_code=201,
    summary="Create a medical writing document",
)
async def create_document(payload: DocumentCreate) -> MedicalDocument:
    svc = get_medical_writing_service()
    return svc.create_document(payload)


@router.put(
    "/documents/{doc_id}",
    response_model=MedicalDocument,
    summary="Update a medical writing document",
)
async def update_document(doc_id: str, payload: DocumentUpdate) -> MedicalDocument:
    svc = get_medical_writing_service()
    updated = svc.update_document(doc_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")
    return updated


@router.delete(
    "/documents/{doc_id}",
    status_code=204,
    summary="Delete a medical writing document",
)
async def delete_document(doc_id: str) -> None:
    svc = get_medical_writing_service()
    deleted = svc.delete_document(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")


@router.post(
    "/documents/{doc_id}/advance",
    response_model=MedicalDocument,
    summary="Advance document lifecycle status",
    description="Advance a document to the next lifecycle status: draft -> internal_review -> medical_review -> qc -> final -> approved.",
)
async def advance_document_status(doc_id: str) -> MedicalDocument:
    svc = get_medical_writing_service()
    try:
        result = svc.advance_document_status(doc_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Section Management
# ---------------------------------------------------------------------------


@router.get(
    "/sections",
    response_model=SectionListResponse,
    summary="List document sections",
    description="Retrieve sections with optional filtering by document, status, and ICH section.",
)
async def list_sections(
    document_id: Optional[str] = Query(None, description="Filter by document ID"),
    status: Optional[SectionStatus] = Query(None, description="Filter by section status"),
    ich_section: Optional[ICHSection] = Query(None, description="Filter by ICH E3 section"),
) -> SectionListResponse:
    svc = get_medical_writing_service()
    items = svc.list_sections(document_id=document_id, status=status, ich_section=ich_section)
    return SectionListResponse(items=items, total=len(items))


@router.get(
    "/sections/{section_id}",
    response_model=DocumentSection,
    summary="Get a document section",
)
async def get_section(section_id: str) -> DocumentSection:
    svc = get_medical_writing_service()
    section = svc.get_section(section_id)
    if section is None:
        raise HTTPException(status_code=404, detail=f"Section '{section_id}' not found")
    return section


@router.post(
    "/sections",
    response_model=DocumentSection,
    status_code=201,
    summary="Create a document section",
)
async def create_section(payload: SectionCreate) -> DocumentSection:
    svc = get_medical_writing_service()
    return svc.create_section(payload)


@router.put(
    "/sections/{section_id}",
    response_model=DocumentSection,
    summary="Update a document section",
)
async def update_section(section_id: str, payload: SectionUpdate) -> DocumentSection:
    svc = get_medical_writing_service()
    updated = svc.update_section(section_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Section '{section_id}' not found")
    return updated


@router.delete(
    "/sections/{section_id}",
    status_code=204,
    summary="Delete a document section",
)
async def delete_section(section_id: str) -> None:
    svc = get_medical_writing_service()
    deleted = svc.delete_section(section_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Section '{section_id}' not found")


# ---------------------------------------------------------------------------
# Review Comments
# ---------------------------------------------------------------------------


@router.get(
    "/comments",
    response_model=ReviewCommentListResponse,
    summary="List review comments",
    description="Retrieve comments with optional filtering by document, section, review type, and resolution.",
)
async def list_comments(
    document_id: Optional[str] = Query(None, description="Filter by document ID"),
    section_id: Optional[str] = Query(None, description="Filter by section ID"),
    review_type: Optional[ReviewType] = Query(None, description="Filter by review type"),
    resolution: Optional[ResolutionStatus] = Query(None, description="Filter by resolution status"),
) -> ReviewCommentListResponse:
    svc = get_medical_writing_service()
    items = svc.list_comments(
        document_id=document_id, section_id=section_id,
        review_type=review_type, resolution=resolution,
    )
    return ReviewCommentListResponse(items=items, total=len(items))


@router.get(
    "/comments/{comment_id}",
    response_model=ReviewComment,
    summary="Get a review comment",
)
async def get_comment(comment_id: str) -> ReviewComment:
    svc = get_medical_writing_service()
    comment = svc.get_comment(comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail=f"Comment '{comment_id}' not found")
    return comment


@router.post(
    "/comments",
    response_model=ReviewComment,
    status_code=201,
    summary="Create a review comment",
)
async def create_comment(payload: ReviewCommentCreate) -> ReviewComment:
    svc = get_medical_writing_service()
    try:
        return svc.create_comment(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/comments/{comment_id}",
    response_model=ReviewComment,
    summary="Update a review comment",
)
async def update_comment(comment_id: str, payload: ReviewCommentUpdate) -> ReviewComment:
    svc = get_medical_writing_service()
    updated = svc.update_comment(comment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Comment '{comment_id}' not found")
    return updated


@router.delete(
    "/comments/{comment_id}",
    status_code=204,
    summary="Delete a review comment",
)
async def delete_comment(comment_id: str) -> None:
    svc = get_medical_writing_service()
    deleted = svc.delete_comment(comment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Comment '{comment_id}' not found")


# ---------------------------------------------------------------------------
# TLF Shell Management
# ---------------------------------------------------------------------------


@router.get(
    "/tlf-shells",
    response_model=TLFShellListResponse,
    summary="List TLF shells",
    description="Retrieve TLF (Table, Listing, Figure) shells with optional filtering by trial, type, and programming status.",
)
async def list_tlf_shells(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    tlf_type: Optional[TLFType] = Query(None, description="Filter by TLF type"),
    programming_status: Optional[ProgrammingStatus] = Query(
        None, description="Filter by programming status"
    ),
) -> TLFShellListResponse:
    svc = get_medical_writing_service()
    items = svc.list_tlf_shells(
        trial_id=trial_id, tlf_type=tlf_type, programming_status=programming_status
    )
    return TLFShellListResponse(items=items, total=len(items))


@router.get(
    "/tlf-shells/{tlf_id}",
    response_model=TLFShell,
    summary="Get a TLF shell",
)
async def get_tlf_shell(tlf_id: str) -> TLFShell:
    svc = get_medical_writing_service()
    tlf = svc.get_tlf_shell(tlf_id)
    if tlf is None:
        raise HTTPException(status_code=404, detail=f"TLF shell '{tlf_id}' not found")
    return tlf


@router.post(
    "/tlf-shells",
    response_model=TLFShell,
    status_code=201,
    summary="Create a TLF shell",
)
async def create_tlf_shell(payload: TLFShellCreate) -> TLFShell:
    svc = get_medical_writing_service()
    return svc.create_tlf_shell(payload)


@router.put(
    "/tlf-shells/{tlf_id}",
    response_model=TLFShell,
    summary="Update a TLF shell",
)
async def update_tlf_shell(tlf_id: str, payload: TLFShellUpdate) -> TLFShell:
    svc = get_medical_writing_service()
    updated = svc.update_tlf_shell(tlf_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"TLF shell '{tlf_id}' not found")
    return updated


@router.delete(
    "/tlf-shells/{tlf_id}",
    status_code=204,
    summary="Delete a TLF shell",
)
async def delete_tlf_shell(tlf_id: str) -> None:
    svc = get_medical_writing_service()
    deleted = svc.delete_tlf_shell(tlf_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"TLF shell '{tlf_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=WritingMetrics,
    summary="Get medical writing metrics",
    description="Aggregated metrics across all documents, sections, reviews, and TLF shells.",
)
async def get_metrics() -> WritingMetrics:
    svc = get_medical_writing_service()
    return svc.get_metrics()
