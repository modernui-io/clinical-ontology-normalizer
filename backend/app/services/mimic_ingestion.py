"""MIMIC-IV-Note CSV ingestion service.

Parses MIMIC discharge summary CSVs and creates Document records that flow
through the existing NLP -> OMOP mapping -> fact building pipeline unchanged.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_sync_engine
from app.models.document import Document
from app.schemas.base import JobStatus
from app.schemas.mimic import (
    MimicImportConfig,
    MimicImportProgressResponse,
    MimicValidateResponse,
)

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {"note_id", "subject_id", "hadm_id", "note_type", "text"}


class MimicIngestionService:
    """Service for ingesting MIMIC-IV-Note CSV files."""

    def validate_csv(self, csv_content: str, max_sample_rows: int = 5) -> MimicValidateResponse:
        """Validate CSV structure without importing."""
        errors: list[str] = []
        sample_rows: list[dict] = []

        try:
            reader = csv.DictReader(io.StringIO(csv_content))
            if reader.fieldnames is None:
                return MimicValidateResponse(
                    valid=False,
                    total_rows=0,
                    columns_found=[],
                    columns_missing=list(REQUIRED_COLUMNS),
                    sample_rows=[],
                    errors=["CSV has no header row"],
                )

            columns_found = list(reader.fieldnames)
            columns_missing = [c for c in REQUIRED_COLUMNS if c not in columns_found]

            if columns_missing:
                errors.append(f"Missing required columns: {', '.join(columns_missing)}")

            row_count = 0
            for row in reader:
                row_count += 1
                if len(sample_rows) < max_sample_rows:
                    # Truncate text for preview
                    preview_row = dict(row)
                    if "text" in preview_row and preview_row["text"]:
                        preview_row["text"] = preview_row["text"][:200] + (
                            "..." if len(preview_row["text"]) > 200 else ""
                        )
                    sample_rows.append(preview_row)

                # Validate required fields have values in first 100 rows
                if row_count <= 100 and not columns_missing:
                    for col in REQUIRED_COLUMNS:
                        if not row.get(col, "").strip():
                            errors.append(f"Row {row_count}: empty value for '{col}'")
                            break

            return MimicValidateResponse(
                valid=len(errors) == 0,
                total_rows=row_count,
                columns_found=columns_found,
                columns_missing=columns_missing,
                sample_rows=sample_rows,
                errors=errors[:20],  # Cap error list
            )

        except csv.Error as e:
            return MimicValidateResponse(
                valid=False,
                total_rows=0,
                columns_found=[],
                columns_missing=list(REQUIRED_COLUMNS),
                sample_rows=[],
                errors=[f"CSV parse error: {e}"],
            )

    def count_csv_rows(self, csv_content: str) -> int:
        """Count total data rows in CSV."""
        reader = csv.DictReader(io.StringIO(csv_content))
        return sum(1 for _ in reader)

    def ingest_csv(
        self,
        csv_content: str,
        config: MimicImportConfig,
        batch_id: str,
        progress_callback: object | None = None,
    ) -> dict:
        """Ingest a MIMIC CSV, creating Document records in chunks.

        Args:
            csv_content: Raw CSV string.
            config: Import configuration.
            batch_id: Unique batch identifier for tracking.
            progress_callback: Optional callable(processed, created, skipped, failed).

        Returns:
            Summary dict with counts.
        """
        reader = csv.DictReader(io.StringIO(csv_content))
        processed = 0
        created = 0
        skipped = 0
        failed = 0
        chunk: list[dict] = []

        for row in reader:
            if config.max_rows and processed >= config.max_rows:
                break

            processed += 1
            chunk.append(row)

            if len(chunk) >= config.chunk_size:
                result = self._process_chunk(chunk, config, batch_id)
                created += result["created"]
                skipped += result["skipped"]
                failed += result["failed"]
                chunk = []

                if progress_callback:
                    progress_callback(processed, created, skipped, failed)  # type: ignore[operator]

        # Process remaining rows
        if chunk:
            result = self._process_chunk(chunk, config, batch_id)
            created += result["created"]
            skipped += result["skipped"]
            failed += result["failed"]

            if progress_callback:
                progress_callback(processed, created, skipped, failed)  # type: ignore[operator]

        return {
            "processed": processed,
            "created": created,
            "skipped": skipped,
            "failed": failed,
        }

    def _process_chunk(
        self,
        rows: list[dict],
        config: MimicImportConfig,
        batch_id: str,
    ) -> dict:
        """Process a chunk of CSV rows, creating Documents."""
        created = 0
        skipped = 0
        failed = 0

        with Session(get_sync_engine()) as session:
            for row in rows:
                try:
                    note_id = row.get("note_id", "").strip()
                    subject_id = row.get("subject_id", "").strip()
                    hadm_id = row.get("hadm_id", "").strip()
                    note_type = row.get("note_type", "").strip()
                    text = row.get("text", "").strip()

                    if not all([note_id, subject_id, text]):
                        failed += 1
                        continue

                    # Duplicate detection
                    if config.skip_duplicates:
                        existing = session.execute(
                            select(Document.id).where(
                                Document.extra_metadata["mimic_note_id"].astext == note_id
                            )
                        ).scalar_one_or_none()
                        if existing:
                            skipped += 1
                            continue

                    doc = Document(
                        id=str(uuid4()),
                        patient_id=f"MIMIC-{subject_id}",
                        note_type=note_type or "Discharge Summary",
                        text=text,
                        extra_metadata={
                            "mimic_note_id": note_id,
                            "mimic_subject_id": subject_id,
                            "mimic_hadm_id": hadm_id,
                            "mimic_batch_id": batch_id,
                            "source": "mimic-iv-note",
                        },
                        status=JobStatus.QUEUED if config.enqueue_processing else JobStatus.QUEUED,
                    )
                    session.add(doc)
                    created += 1

                    # Enqueue for NLP processing
                    if config.enqueue_processing:
                        try:
                            from app.core.queue import enqueue_job
                            from app.jobs.document_processing import process_document

                            enqueue_job(
                                process_document,
                                doc.id,
                                queue_name="document_processing",
                            )
                        except Exception as e:
                            logger.warning(f"Failed to enqueue doc {doc.id}: {e}")

                except Exception as e:
                    logger.warning(f"Failed to process MIMIC row: {e}")
                    failed += 1

            session.commit()

        return {"created": created, "skipped": skipped, "failed": failed}

    def get_import_progress(self, batch_id: str) -> MimicImportProgressResponse | None:
        """Get progress of an import batch from Redis."""
        try:
            from app.core.redis import get_redis

            redis = get_redis()
            key = f"mimic_import:{batch_id}"
            data = redis.hgetall(key)
            if not data:
                return None

            total = int(data.get(b"total_rows", data.get("total_rows", 0)))
            processed = int(data.get(b"processed", data.get("processed", 0)))
            created_count = int(data.get(b"created", data.get("created", 0)))
            skipped_count = int(data.get(b"skipped", data.get("skipped", 0)))
            failed_count = int(data.get(b"failed", data.get("failed", 0)))
            status = (data.get(b"status") or data.get("status", b"processing"))
            if isinstance(status, bytes):
                status = status.decode()
            error = data.get(b"error") or data.get("error")
            if isinstance(error, bytes):
                error = error.decode()

            progress = (processed / total * 100) if total > 0 else 0.0

            return MimicImportProgressResponse(
                batch_id=batch_id,
                status=status,
                total_rows=total,
                processed=processed,
                created=created_count,
                skipped=skipped_count,
                failed=failed_count,
                progress_percent=round(progress, 1),
                error=error if error else None,
            )
        except Exception as e:
            logger.warning(f"Failed to get import progress for {batch_id}: {e}")
            return None

    def get_mimic_metrics(self) -> dict:
        """Compute validation metrics for all MIMIC-imported documents."""
        with Session(get_sync_engine()) as session:
            from app.models.clinical_fact import ClinicalFact
            from app.models.mention import Mention, MentionConceptCandidate

            # Total MIMIC documents
            total_docs = session.execute(
                select(func.count(Document.id)).where(
                    Document.extra_metadata["source"].astext == "mimic-iv-note"
                )
            ).scalar() or 0

            # Status breakdown
            status_rows = session.execute(
                select(Document.status, func.count(Document.id)).where(
                    Document.extra_metadata["source"].astext == "mimic-iv-note"
                ).group_by(Document.status)
            ).all()
            status_breakdown = {str(row[0].value if hasattr(row[0], 'value') else row[0]): row[1] for row in status_rows}

            # Get MIMIC document IDs for join queries
            mimic_doc_ids = session.execute(
                select(Document.id).where(
                    Document.extra_metadata["source"].astext == "mimic-iv-note"
                )
            ).scalars().all()

            if not mimic_doc_ids:
                return {
                    "total_documents": 0,
                    "total_mentions": 0,
                    "total_facts": 0,
                    "concept_coverage_percent": 0.0,
                    "avg_confidence": 0.0,
                    "status_breakdown": status_breakdown,
                    "domain_distribution": [],
                    "top_unmapped_terms": [],
                    "avg_processing_time_ms": 0.0,
                    "p50_processing_time_ms": 0.0,
                    "p95_processing_time_ms": 0.0,
                    "recent_documents": [],
                }

            # Total mentions from MIMIC docs
            total_mentions = session.execute(
                select(func.count(Mention.id)).where(
                    Mention.document_id.in_(mimic_doc_ids)
                )
            ).scalar() or 0

            # Avg confidence
            avg_confidence = session.execute(
                select(func.avg(Mention.confidence)).where(
                    Mention.document_id.in_(mimic_doc_ids)
                )
            ).scalar() or 0.0

            # Mentions with at least one concept candidate (coverage)
            mentions_with_concepts = session.execute(
                select(func.count(func.distinct(MentionConceptCandidate.mention_id))).where(
                    MentionConceptCandidate.mention_id.in_(
                        select(Mention.id).where(Mention.document_id.in_(mimic_doc_ids))
                    )
                )
            ).scalar() or 0

            coverage = (mentions_with_concepts / total_mentions * 100) if total_mentions > 0 else 0.0

            # Get patient IDs for MIMIC docs
            mimic_patient_ids = session.execute(
                select(func.distinct(Document.patient_id)).where(
                    Document.extra_metadata["source"].astext == "mimic-iv-note"
                )
            ).scalars().all()

            # Total facts
            total_facts = session.execute(
                select(func.count(ClinicalFact.id)).where(
                    ClinicalFact.patient_id.in_(mimic_patient_ids)
                )
            ).scalar() or 0

            # Domain distribution
            domain_rows = session.execute(
                select(ClinicalFact.domain, func.count(ClinicalFact.id)).where(
                    ClinicalFact.patient_id.in_(mimic_patient_ids)
                ).group_by(ClinicalFact.domain)
            ).all()
            domain_distribution = [
                {"domain": str(row[0].value if hasattr(row[0], 'value') else row[0]), "count": row[1]}
                for row in domain_rows
            ]

            # Top unmapped terms (mentions without concept candidates)
            mapped_mention_ids = select(func.distinct(MentionConceptCandidate.mention_id)).where(
                MentionConceptCandidate.mention_id.in_(
                    select(Mention.id).where(Mention.document_id.in_(mimic_doc_ids))
                )
            ).scalar_subquery()

            unmapped_rows = session.execute(
                select(Mention.text, func.count(Mention.id).label("cnt"))
                .where(
                    Mention.document_id.in_(mimic_doc_ids),
                    ~Mention.id.in_(
                        select(func.distinct(MentionConceptCandidate.mention_id)).where(
                            MentionConceptCandidate.mention_id.in_(
                                select(Mention.id).where(Mention.document_id.in_(mimic_doc_ids))
                            )
                        )
                    ),
                )
                .group_by(Mention.text)
                .order_by(func.count(Mention.id).desc())
                .limit(20)
            ).all()
            top_unmapped = [{"term": row[0], "count": row[1], "sample_document_ids": []} for row in unmapped_rows]

            # Recent documents
            recent_docs = session.execute(
                select(Document).where(
                    Document.extra_metadata["source"].astext == "mimic-iv-note"
                ).order_by(Document.created_at.desc()).limit(10)
            ).scalars().all()
            recent_list = [
                {
                    "id": doc.id,
                    "patient_id": doc.patient_id,
                    "note_type": doc.note_type,
                    "status": doc.status.value if hasattr(doc.status, 'value') else str(doc.status),
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                    "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
                    "mimic_note_id": doc.extra_metadata.get("mimic_note_id"),
                }
                for doc in recent_docs
            ]

            # Processing time stats (from documents that have processed_at)
            # Approximate: processed_at - created_at
            processing_times: list[float] = []
            completed_docs = session.execute(
                select(Document.created_at, Document.processed_at).where(
                    Document.extra_metadata["source"].astext == "mimic-iv-note",
                    Document.processed_at.isnot(None),
                    Document.created_at.isnot(None),
                )
            ).all()
            for row in completed_docs:
                if row[0] and row[1]:
                    delta = (row[1] - row[0]).total_seconds() * 1000
                    processing_times.append(delta)

            processing_times.sort()
            avg_time = sum(processing_times) / len(processing_times) if processing_times else 0.0
            p50_time = processing_times[len(processing_times) // 2] if processing_times else 0.0
            p95_idx = int(len(processing_times) * 0.95)
            p95_time = processing_times[min(p95_idx, len(processing_times) - 1)] if processing_times else 0.0

            return {
                "total_documents": total_docs,
                "total_mentions": total_mentions,
                "total_facts": total_facts,
                "concept_coverage_percent": round(coverage, 1),
                "avg_confidence": round(float(avg_confidence), 3),
                "status_breakdown": status_breakdown,
                "domain_distribution": domain_distribution,
                "top_unmapped_terms": top_unmapped,
                "avg_processing_time_ms": round(avg_time, 1),
                "p50_processing_time_ms": round(p50_time, 1),
                "p95_processing_time_ms": round(p95_time, 1),
                "recent_documents": recent_list,
            }

    def get_document_pipeline_results(self, document_id: str) -> dict | None:
        """Get full pipeline results for a single document."""
        with Session(get_sync_engine()) as session:
            from app.models.clinical_fact import ClinicalFact
            from app.models.mention import Mention, MentionConceptCandidate

            doc = session.execute(
                select(Document).where(Document.id == document_id)
            ).scalar_one_or_none()

            if not doc:
                return None

            # Get all mentions for this document
            mentions = session.execute(
                select(Mention).where(Mention.document_id == document_id)
                .order_by(Mention.start_offset)
            ).scalars().all()

            mention_ids = [m.id for m in mentions]

            # Get top concept candidate for each mention (rank 1)
            candidate_map: dict[str, object] = {}
            if mention_ids:
                candidates = session.execute(
                    select(MentionConceptCandidate).where(
                        MentionConceptCandidate.mention_id.in_(mention_ids),
                        MentionConceptCandidate.rank == 1,
                    )
                ).scalars().all()
                for c in candidates:
                    candidate_map[c.mention_id] = c

            # Build mention list with mappings
            mention_list = []
            mapped_count = 0
            for m in mentions:
                c = candidate_map.get(m.id)
                if c:
                    mapped_count += 1
                mention_list.append({
                    "id": m.id,
                    "text": m.text,
                    "start_offset": m.start_offset,
                    "end_offset": m.end_offset,
                    "section": m.section,
                    "assertion": m.assertion.value if hasattr(m.assertion, 'value') else str(m.assertion),
                    "temporality": m.temporality.value if hasattr(m.temporality, 'value') else str(m.temporality),
                    "experiencer": m.experiencer.value if hasattr(m.experiencer, 'value') else str(m.experiencer),
                    "confidence": m.confidence,
                    "concept_name": c.concept_name if c else None,
                    "omop_concept_id": c.omop_concept_id if c else None,
                    "vocabulary_id": c.vocabulary_id if c else None,
                    "domain_id": c.domain_id if c else None,
                    "mapping_score": c.score if c else None,
                    "mapping_method": c.method if c else None,
                })

            # Get facts for this patient (scoped to MIMIC)
            facts = session.execute(
                select(ClinicalFact).where(
                    ClinicalFact.patient_id == doc.patient_id,
                )
            ).scalars().all()

            fact_list = [
                {
                    "id": f.id,
                    "domain": f.domain.value if hasattr(f.domain, 'value') else str(f.domain),
                    "omop_concept_id": f.omop_concept_id,
                    "concept_name": f.concept_name,
                    "assertion": f.assertion.value if hasattr(f.assertion, 'value') else str(f.assertion),
                    "temporality": f.temporality.value if hasattr(f.temporality, 'value') else str(f.temporality),
                    "experiencer": f.experiencer.value if hasattr(f.experiencer, 'value') else str(f.experiencer),
                    "confidence": f.confidence,
                }
                for f in facts
            ]

            total = len(mentions)
            unmapped = total - mapped_count
            coverage = (mapped_count / total * 100) if total > 0 else 0.0

            return {
                "document_id": doc.id,
                "patient_id": doc.patient_id,
                "note_type": doc.note_type,
                "status": doc.status.value if hasattr(doc.status, 'value') else str(doc.status),
                "mimic_note_id": doc.extra_metadata.get("mimic_note_id"),
                "text_preview": doc.text[:500] + ("..." if len(doc.text) > 500 else ""),
                "text_length": len(doc.text),
                "mentions": mention_list,
                "facts": fact_list,
                "mention_count": total,
                "fact_count": len(fact_list),
                "mapped_mention_count": mapped_count,
                "unmapped_mention_count": unmapped,
                "concept_coverage_percent": round(coverage, 1),
            }
