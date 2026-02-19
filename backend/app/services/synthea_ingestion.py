"""Synthea synthetic patient data ingestion service.

Reads Synthea CSV output (patients, encounters, conditions, observations,
medications, procedures) and composes clinical notes from structured data.
Each encounter becomes a Document that flows through the NLP pipeline.
"""

from __future__ import annotations

import csv
import logging
from collections import defaultdict
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_sync_engine
from app.models.document import Document
from app.schemas.base import JobStatus
from app.schemas.synthea import (
    SyntheaImportConfig,
    SyntheaImportProgressResponse,
    SyntheaValidateResponse,
)

logger = logging.getLogger(__name__)

REQUIRED_FILES = {"patients.csv", "encounters.csv", "conditions.csv"}
OPTIONAL_FILES = {"observations.csv", "medications.csv", "procedures.csv"}


class SyntheaIngestionService:
    """Service for ingesting Synthea synthetic patient data."""

    def validate_directory(self, csv_dir: str) -> SyntheaValidateResponse:
        """Validate Synthea output directory structure."""
        errors: list[str] = []
        dir_path = Path(csv_dir)

        if not dir_path.exists():
            return SyntheaValidateResponse(
                valid=False,
                files_found=[],
                files_missing=list(REQUIRED_FILES),
                patient_count=0,
                encounter_count=0,
                condition_count=0,
                observation_count=0,
                medication_count=0,
                procedure_count=0,
                errors=[f"Directory not found: {csv_dir}"],
                sample_patient=None,
            )

        files_found = [f.name for f in dir_path.iterdir() if f.suffix == ".csv"]
        files_missing = [f for f in REQUIRED_FILES if f not in files_found]

        if files_missing:
            errors.append(f"Missing required files: {', '.join(files_missing)}")

        def _count_rows(filename: str) -> int:
            path = dir_path / filename
            if not path.exists():
                return 0
            # Use raw byte counting for speed on large files
            count = 0
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    count += chunk.count(b"\n")
            return max(count - 1, 0)  # minus header

        patient_count = _count_rows("patients.csv")
        encounter_count = _count_rows("encounters.csv")
        condition_count = _count_rows("conditions.csv")
        observation_count = _count_rows("observations.csv")
        medication_count = _count_rows("medications.csv")
        procedure_count = _count_rows("procedures.csv")

        # Sample first patient
        sample_patient = None
        patients_path = dir_path / "patients.csv"
        if patients_path.exists():
            with open(patients_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    sample_patient = {
                        "id": row.get("Id", "")[:8] + "...",
                        "name": f"{row.get('FIRST', '')} {row.get('LAST', '')}",
                        "gender": row.get("GENDER", ""),
                        "birthdate": row.get("BIRTHDATE", ""),
                        "race": row.get("RACE", ""),
                        "city": row.get("CITY", ""),
                        "state": row.get("STATE", ""),
                    }
                    break

        return SyntheaValidateResponse(
            valid=len(errors) == 0,
            files_found=files_found,
            files_missing=files_missing,
            patient_count=patient_count,
            encounter_count=encounter_count,
            condition_count=condition_count,
            observation_count=observation_count,
            medication_count=medication_count,
            procedure_count=procedure_count,
            errors=errors,
            sample_patient=sample_patient,
        )

    def ingest_directory(
        self,
        csv_dir: str,
        config: SyntheaImportConfig,
        batch_id: str,
        progress_callback: object | None = None,
    ) -> dict:
        """Ingest Synthea CSVs, composing clinical notes from encounters."""
        dir_path = Path(csv_dir)

        # Load patient demographics
        patients = self._load_patients(dir_path)

        # Load encounter-level data
        encounters = self._load_encounters(dir_path)
        conditions_by_enc = self._load_by_encounter(dir_path / "conditions.csv", "ENCOUNTER")
        observations_by_enc = self._load_by_encounter(dir_path / "observations.csv", "ENCOUNTER")
        medications_by_enc = self._load_by_encounter(dir_path / "medications.csv", "ENCOUNTER")
        procedures_by_enc = self._load_by_encounter(dir_path / "procedures.csv", "ENCOUNTER")

        processed = 0
        created = 0
        skipped = 0
        failed = 0
        chunk: list[dict] = []

        # Process encounters patient by patient
        patient_ids = list(patients.keys())
        if config.max_patients:
            patient_ids = patient_ids[:config.max_patients]

        for patient_id in patient_ids:
            patient = patients[patient_id]
            patient_encounters = [e for e in encounters if e.get("PATIENT") == patient_id]

            if config.max_encounters_per_patient:
                patient_encounters = patient_encounters[:config.max_encounters_per_patient]

            for enc in patient_encounters:
                enc_id = enc.get("Id", "")
                processed += 1

                note_text = self._compose_note(
                    patient=patient,
                    encounter=enc,
                    conditions=conditions_by_enc.get(enc_id, []),
                    observations=observations_by_enc.get(enc_id, []),
                    medications=medications_by_enc.get(enc_id, []),
                    procedures=procedures_by_enc.get(enc_id, []),
                )

                chunk.append({
                    "encounter_id": enc_id,
                    "patient_id": patient_id,
                    "encounter_class": enc.get("ENCOUNTERCLASS", ""),
                    "encounter_code": enc.get("CODE", ""),
                    "encounter_description": enc.get("DESCRIPTION", ""),
                    "encounter_start": enc.get("START", ""),
                    "text": note_text,
                })

                if len(chunk) >= config.chunk_size:
                    result = self._process_chunk(chunk, config, batch_id)
                    created += result["created"]
                    skipped += result["skipped"]
                    failed += result["failed"]
                    chunk = []

                    if progress_callback:
                        progress_callback(processed, created, skipped, failed)  # type: ignore[operator]

        # Process remaining
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

    def _load_patients(self, dir_path: Path) -> dict[str, dict]:
        """Load patients.csv into a dict keyed by patient ID."""
        patients: dict[str, dict] = {}
        path = dir_path / "patients.csv"
        if not path.exists():
            return patients
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                patients[row["Id"]] = row
        return patients

    def _load_encounters(self, dir_path: Path) -> list[dict]:
        """Load all encounters."""
        path = dir_path / "encounters.csv"
        if not path.exists():
            return []
        with open(path, encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def _load_by_encounter(self, path: Path, encounter_col: str) -> dict[str, list[dict]]:
        """Load a CSV and group rows by encounter ID."""
        grouped: dict[str, list[dict]] = defaultdict(list)
        if not path.exists():
            return grouped
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                enc_id = row.get(encounter_col, "")
                if enc_id:
                    grouped[enc_id].append(row)
        return grouped

    def _compose_note(
        self,
        patient: dict,
        encounter: dict,
        conditions: list[dict],
        observations: list[dict],
        medications: list[dict],
        procedures: list[dict],
    ) -> str:
        """Compose a clinical note from Synthea structured data."""
        lines: list[str] = []

        # Demographics
        first = patient.get("FIRST", "")
        last = patient.get("LAST", "")
        gender = patient.get("GENDER", "Unknown")
        birthdate = patient.get("BIRTHDATE", "")
        race = patient.get("RACE", "")
        ethnicity = patient.get("ETHNICITY", "")
        lines.append(f"PATIENT: {first} {last}")
        lines.append(f"Date of Birth: {birthdate}")
        lines.append(f"Gender: {gender}")
        if race:
            lines.append(f"Race: {race}, Ethnicity: {ethnicity}")
        lines.append("")

        # Encounter
        enc_class = encounter.get("ENCOUNTERCLASS", "")
        enc_desc = encounter.get("DESCRIPTION", "")
        enc_start = encounter.get("START", "")[:10]  # date portion
        enc_stop = encounter.get("STOP", "")[:10] if encounter.get("STOP") else ""
        reason_desc = encounter.get("REASONDESCRIPTION", "")
        lines.append(f"ENCOUNTER: {enc_class} - {enc_desc}")
        lines.append(f"Date: {enc_start}" + (f" to {enc_stop}" if enc_stop else ""))
        if reason_desc:
            lines.append(f"Reason for visit: {reason_desc}")
        lines.append("")

        # Active Conditions
        if conditions:
            lines.append("ACTIVE CONDITIONS:")
            for c in conditions:
                desc = c.get("DESCRIPTION", "Unknown condition")
                code = c.get("CODE", "")
                onset = c.get("START", "")[:10] if c.get("START") else ""
                system = c.get("SYSTEM", "")
                code_label = f" (SNOMED: {code})" if "snomed" in system.lower() and code else ""
                lines.append(f"- {desc}{code_label}, onset {onset}" if onset else f"- {desc}{code_label}")
            lines.append("")

        # Observations / Vitals
        if observations:
            vitals = [o for o in observations if o.get("CATEGORY") == "vital-signs"]
            labs = [o for o in observations if o.get("CATEGORY") != "vital-signs"]

            if vitals:
                lines.append("VITALS:")
                for v in vitals[:10]:  # limit to 10 most relevant
                    desc = v.get("DESCRIPTION", "")
                    value = v.get("VALUE", "")
                    units = v.get("UNITS", "")
                    lines.append(f"- {desc}: {value} {units}")
                lines.append("")

            if labs:
                lines.append("LABORATORY RESULTS:")
                for lab in labs[:15]:  # limit
                    desc = lab.get("DESCRIPTION", "")
                    value = lab.get("VALUE", "")
                    units = lab.get("UNITS", "")
                    lines.append(f"- {desc}: {value} {units}")
                lines.append("")

        # Medications
        if medications:
            lines.append("MEDICATIONS:")
            for m in medications:
                desc = m.get("DESCRIPTION", "Unknown medication")
                reason = m.get("REASONDESCRIPTION", "")
                start = m.get("START", "")[:10] if m.get("START") else ""
                med_line = f"- {desc}"
                if reason:
                    med_line += f" for {reason}"
                if start:
                    med_line += f" (started {start})"
                lines.append(med_line)
            lines.append("")

        # Procedures
        if procedures:
            lines.append("PROCEDURES PERFORMED:")
            for p in procedures:
                desc = p.get("DESCRIPTION", "Unknown procedure")
                code = p.get("CODE", "")
                date = p.get("DATE", "")[:10] if p.get("DATE") else ""
                reason = p.get("REASONDESCRIPTION", "")
                proc_line = f"- {desc}"
                if code:
                    proc_line += f" (SNOMED: {code})"
                if date:
                    proc_line += f" on {date}"
                if reason:
                    proc_line += f" for {reason}"
                lines.append(proc_line)
            lines.append("")

        return "\n".join(lines)

    def _process_chunk(
        self,
        rows: list[dict],
        config: SyntheaImportConfig,
        batch_id: str,
    ) -> dict:
        """Process a chunk of composed notes, creating Documents."""
        created = 0
        skipped = 0
        failed = 0

        with Session(get_sync_engine()) as session:
            for row in rows:
                try:
                    encounter_id = row["encounter_id"]
                    patient_id = row["patient_id"]
                    text = row["text"]

                    if not text.strip():
                        failed += 1
                        continue

                    # Duplicate detection
                    if config.skip_duplicates:
                        existing = session.execute(
                            select(Document.id).where(
                                Document.extra_metadata["synthea_encounter_id"].astext == encounter_id
                            )
                        ).scalar_one_or_none()
                        if existing:
                            skipped += 1
                            continue

                    enc_class = row.get("encounter_class", "")
                    note_type = f"Synthea {enc_class}".strip() if enc_class else "Synthea Encounter"

                    doc = Document(
                        id=str(uuid4()),
                        patient_id=f"SYNTHEA-{patient_id[:8]}",
                        note_type=note_type,
                        text=text,
                        extra_metadata={
                            "synthea_encounter_id": encounter_id,
                            "synthea_patient_id": patient_id,
                            "synthea_encounter_class": enc_class,
                            "synthea_encounter_code": row.get("encounter_code", ""),
                            "synthea_encounter_description": row.get("encounter_description", ""),
                            "synthea_encounter_start": row.get("encounter_start", ""),
                            "synthea_batch_id": batch_id,
                            "source": "synthea",
                        },
                        status=JobStatus.QUEUED if config.enqueue_processing else JobStatus.QUEUED,
                    )
                    session.add(doc)
                    created += 1

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
                    logger.warning(f"Failed to process Synthea encounter: {e}")
                    failed += 1

            session.commit()

        return {"created": created, "skipped": skipped, "failed": failed}

    def get_import_progress(self, batch_id: str) -> SyntheaImportProgressResponse | None:
        """Get progress of an import batch from Redis."""
        try:
            from app.core.redis import get_redis

            redis = get_redis()
            key = f"synthea_import:{batch_id}"
            data = redis.hgetall(key)
            if not data:
                return None

            total = int(data.get(b"total_rows", data.get("total_rows", 0)))
            processed = int(data.get(b"processed", data.get("processed", 0)))
            created_count = int(data.get(b"created", data.get("created", 0)))
            skipped_count = int(data.get(b"skipped", data.get("skipped", 0)))
            failed_count = int(data.get(b"failed", data.get("failed", 0)))
            status = data.get(b"status") or data.get("status", b"processing")
            if isinstance(status, bytes):
                status = status.decode()
            error = data.get(b"error") or data.get("error")
            if isinstance(error, bytes):
                error = error.decode()

            progress = (processed / total * 100) if total > 0 else 0.0

            return SyntheaImportProgressResponse(
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

    def get_metrics(self) -> dict:
        """Compute validation metrics for all Synthea-imported documents."""
        with Session(get_sync_engine()) as session:
            from app.models.clinical_fact import ClinicalFact
            from app.models.mention import Mention, MentionConceptCandidate

            total_docs = session.execute(
                select(func.count(Document.id)).where(
                    Document.extra_metadata["source"].astext == "synthea"
                )
            ).scalar() or 0

            status_rows = session.execute(
                select(Document.status, func.count(Document.id)).where(
                    Document.extra_metadata["source"].astext == "synthea"
                ).group_by(Document.status)
            ).all()
            status_breakdown = {str(row[0].value if hasattr(row[0], 'value') else row[0]): row[1] for row in status_rows}

            doc_ids = session.execute(
                select(Document.id).where(
                    Document.extra_metadata["source"].astext == "synthea"
                )
            ).scalars().all()

            if not doc_ids:
                return {
                    "total_documents": 0,
                    "total_mentions": 0,
                    "total_facts": 0,
                    "concept_coverage_percent": 0.0,
                    "avg_confidence": 0.0,
                    "status_breakdown": status_breakdown,
                    "domain_distribution": [],
                    "encounter_class_distribution": [],
                    "top_unmapped_terms": [],
                    "avg_processing_time_ms": 0.0,
                    "p50_processing_time_ms": 0.0,
                    "p95_processing_time_ms": 0.0,
                    "recent_documents": [],
                }

            total_mentions = session.execute(
                select(func.count(Mention.id)).where(Mention.document_id.in_(doc_ids))
            ).scalar() or 0

            avg_confidence = session.execute(
                select(func.avg(Mention.confidence)).where(Mention.document_id.in_(doc_ids))
            ).scalar() or 0.0

            mentions_with_concepts = session.execute(
                select(func.count(func.distinct(MentionConceptCandidate.mention_id))).where(
                    MentionConceptCandidate.mention_id.in_(
                        select(Mention.id).where(Mention.document_id.in_(doc_ids))
                    )
                )
            ).scalar() or 0

            coverage = (mentions_with_concepts / total_mentions * 100) if total_mentions > 0 else 0.0

            patient_ids = session.execute(
                select(func.distinct(Document.patient_id)).where(
                    Document.extra_metadata["source"].astext == "synthea"
                )
            ).scalars().all()

            total_facts = session.execute(
                select(func.count(ClinicalFact.id)).where(
                    ClinicalFact.patient_id.in_(patient_ids)
                )
            ).scalar() or 0

            domain_rows = session.execute(
                select(ClinicalFact.domain, func.count(ClinicalFact.id)).where(
                    ClinicalFact.patient_id.in_(patient_ids)
                ).group_by(ClinicalFact.domain)
            ).all()
            domain_distribution = [
                {"domain": str(row[0].value if hasattr(row[0], 'value') else row[0]), "count": row[1]}
                for row in domain_rows
            ]

            # Encounter class distribution (unique to Synthea)
            enc_class_rows = session.execute(
                select(
                    Document.extra_metadata["synthea_encounter_class"].astext,
                    func.count(Document.id),
                ).where(
                    Document.extra_metadata["source"].astext == "synthea"
                ).group_by(
                    Document.extra_metadata["synthea_encounter_class"].astext
                ).order_by(func.count(Document.id).desc())
            ).all()
            encounter_class_distribution = [
                {"encounter_class": row[0] or "Unknown", "count": row[1]}
                for row in enc_class_rows
            ]

            # Unmapped terms
            unmapped_rows = session.execute(
                select(Mention.text, func.count(Mention.id).label("cnt"))
                .where(
                    Mention.document_id.in_(doc_ids),
                    ~Mention.id.in_(
                        select(func.distinct(MentionConceptCandidate.mention_id)).where(
                            MentionConceptCandidate.mention_id.in_(
                                select(Mention.id).where(Mention.document_id.in_(doc_ids))
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
                    Document.extra_metadata["source"].astext == "synthea"
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
                    "encounter_class": doc.extra_metadata.get("synthea_encounter_class"),
                    "encounter_description": doc.extra_metadata.get("synthea_encounter_description"),
                }
                for doc in recent_docs
            ]

            # Processing time stats
            processing_times: list[float] = []
            completed_docs = session.execute(
                select(Document.created_at, Document.processed_at).where(
                    Document.extra_metadata["source"].astext == "synthea",
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
                "encounter_class_distribution": encounter_class_distribution,
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

            mentions = session.execute(
                select(Mention).where(Mention.document_id == document_id)
                .order_by(Mention.start_offset)
            ).scalars().all()

            mention_ids = [m.id for m in mentions]

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

            facts = session.execute(
                select(ClinicalFact).where(ClinicalFact.patient_id == doc.patient_id)
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
            coverage_pct = (mapped_count / total * 100) if total > 0 else 0.0

            return {
                "document_id": doc.id,
                "patient_id": doc.patient_id,
                "note_type": doc.note_type,
                "status": doc.status.value if hasattr(doc.status, 'value') else str(doc.status),
                "source_id": doc.extra_metadata.get("synthea_encounter_id"),
                "text_preview": doc.text[:500] + ("..." if len(doc.text) > 500 else ""),
                "text_length": len(doc.text),
                "mentions": mention_list,
                "facts": fact_list,
                "mention_count": total,
                "fact_count": len(fact_list),
                "mapped_mention_count": mapped_count,
                "unmapped_mention_count": unmapped,
                "concept_coverage_percent": round(coverage_pct, 1),
            }
