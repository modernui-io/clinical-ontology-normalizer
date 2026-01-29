"""OMOP CDM export API endpoints."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_sync_engine
from app.models.document import Document as DocumentModel
from app.models.mention import Mention as MentionModel
from app.services.export import (
    NoteExport,
    NoteNLPExport,
    document_to_note_export,
    mention_to_note_nlp_export,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["Export"])


class OMOPExportResponse(BaseModel):
    """Response model for OMOP export endpoint."""

    patient_id: str = Field(..., description="Patient identifier")
    notes: list[NoteExport] = Field(default_factory=list, description="NOTE table rows")
    note_nlp_records: list[NoteNLPExport] = Field(
        default_factory=list, description="NOTE_NLP table rows"
    )
    note_count: int = Field(0, description="Number of notes exported")
    note_nlp_count: int = Field(0, description="Number of NLP records exported")
    export_format: str = Field("OMOP CDM v5.4", description="Export format version")


@router.get(
    "/omop/{patient_id}",
    response_model=OMOPExportResponse,
    summary="Export patient data in OMOP format",
    description="Export clinical documents and NLP mentions for a patient in OMOP CDM format.",
)
def export_patient_omop(
    patient_id: str,
    include_notes: Annotated[
        bool, Query(description="Include NOTE table rows")
    ] = True,
    include_nlp: Annotated[
        bool, Query(description="Include NOTE_NLP table rows")
    ] = True,
) -> OMOPExportResponse:
    """Export patient data in OMOP CDM format.

    Exports documents and NLP-extracted mentions to OMOP format:
    - NOTE table: Document metadata and text
    - NOTE_NLP table: Extracted mentions with assertion info

    IMPORTANT: Negated mentions (assertion=absent) are exported with
    term_exists='N' to preserve negation information in OMOP format.

    Args:
        patient_id: Patient identifier
        include_notes: Whether to include NOTE table rows
        include_nlp: Whether to include NOTE_NLP table rows

    Returns:
        OMOPExportResponse with exported data

    Raises:
        HTTPException: 404 if patient has no data
    """
    logger.info(f"Exporting OMOP data for patient_id={patient_id}")

    notes: list[NoteExport] = []
    note_nlp_records: list[NoteNLPExport] = []

    with Session(get_sync_engine()) as session:
        # Get all documents for patient
        if include_notes:
            doc_stmt = select(DocumentModel).where(
                DocumentModel.patient_id == patient_id
            )
            docs = session.execute(doc_stmt).scalars().all()

            for doc in docs:
                note_export = document_to_note_export(doc)
                notes.append(note_export)

            logger.info(f"Exported {len(notes)} notes for patient_id={patient_id}")

        # Get all mentions for patient's documents
        if include_nlp:
            # Get mentions with concept candidates loaded
            mention_stmt = (
                select(MentionModel)
                .join(DocumentModel, MentionModel.document_id == DocumentModel.id)
                .where(DocumentModel.patient_id == patient_id)
                .options(selectinload(MentionModel.concept_candidates))
            )
            mentions = session.execute(mention_stmt).scalars().all()

            for mention in mentions:
                nlp_export = mention_to_note_nlp_export(mention)
                note_nlp_records.append(nlp_export)

            logger.info(
                f"Exported {len(note_nlp_records)} NLP records for patient_id={patient_id}"
            )

        # Check if we found any data
        if not notes and not note_nlp_records:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No data found for patient {patient_id}",
            )

    return OMOPExportResponse(
        patient_id=patient_id,
        notes=notes,
        note_nlp_records=note_nlp_records,
        note_count=len(notes),
        note_nlp_count=len(note_nlp_records),
    )
