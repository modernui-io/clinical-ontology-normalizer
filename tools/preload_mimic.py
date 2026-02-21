#!/usr/bin/env python3
"""Bulk-preload MIMIC patients from SQLite into PostgreSQL + RQ pipeline.

Streams directly from mimic_notes.db → PostgreSQL documents table,
enqueuing NLP processing jobs along the way. Avoids loading entire
CSVs into memory.

Usage:
    # Preload all discharge summaries (highest clinical value)
    python tools/preload_mimic.py --category "Discharge Summary"

    # Preload with a patient limit (for testing)
    python tools/preload_mimic.py --category "Discharge Summary" --max-patients 100

    # Preload radiology reports
    python tools/preload_mimic.py --category "Radiology Report" --max-patients 1000

    # Preload everything
    python tools/preload_mimic.py --all

    # Dry run (count only, no writes)
    python tools/preload_mimic.py --category "Discharge Summary" --dry-run

    # Skip NLP queueing (import only, process later)
    python tools/preload_mimic.py --category "Discharge Summary" --no-enqueue

Prerequisites:
    - Backend running or at least PostgreSQL + Redis available
    - Run from project root: python tools/preload_mimic.py
    - For NLP processing: start workers with backend/scripts/run_worker.sh
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import signal
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

# Add backend to path so we can import app modules
BACKEND_DIR = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# Load .env before importing app modules, but override DEBUG to suppress SQL echo
from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")
os.environ["DEBUG"] = "false"  # Prevent engine echo=True flooding logs

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.database import get_sync_engine
from app.models.document import Document
from app.schemas.base import JobStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(message)s",
    datefmt="%H:%M:%S",
)
# Suppress noisy SQLAlchemy logging
for _name in ("sqlalchemy.engine", "sqlalchemy.engine.Engine", "sqlalchemy.pool"):
    logging.getLogger(_name).setLevel(logging.WARNING)
logger = logging.getLogger("preload_mimic")

DB_PATH = Path(__file__).parent / "mimic_notes.db"

# Deterministic fake names (same logic as export_mimic_sample.py)
FIRST_NAMES_M = [
    "James", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas",
    "Charles", "Christopher", "Daniel", "Matthew", "Anthony", "Mark", "Donald",
    "Steven", "Paul", "Andrew", "Joshua", "Kenneth", "Kevin", "Brian", "George",
    "Timothy", "Ronald", "Edward", "Jason", "Jeffrey", "Ryan", "Jacob",
]
FIRST_NAMES_F = [
    "Mary", "Patricia", "Jennifer", "Linda", "Barbara", "Elizabeth", "Susan", "Jessica",
    "Sarah", "Karen", "Lisa", "Nancy", "Betty", "Margaret", "Sandra", "Ashley",
    "Dorothy", "Kimberly", "Emily", "Donna", "Michelle", "Carol", "Amanda", "Melissa",
    "Deborah", "Stephanie", "Rebecca", "Sharon", "Laura", "Cynthia",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
    "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen",
    "Hill", "Flores", "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera",
    "Campbell", "Mitchell", "Carter", "Roberts",
]


# Graceful shutdown
_shutdown_requested = False

def _handle_signal(signum, frame):
    global _shutdown_requested
    _shutdown_requested = True
    logger.warning("Shutdown requested — finishing current batch...")

signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


def deterministic_name(subject_id: str, index: int = 0) -> tuple[str, str, str]:
    h = int(hashlib.md5(f"{subject_id}-{index}".encode()).hexdigest(), 16)
    gender = "M" if h % 2 == 0 else "F"
    first_names = FIRST_NAMES_M if gender == "M" else FIRST_NAMES_F
    first = first_names[h % len(first_names)]
    last = LAST_NAMES[(h >> 8) % len(LAST_NAMES)]
    return first, last, gender


def deterministic_dob(subject_id: str) -> str:
    h = int(hashlib.md5(f"dob-{subject_id}".encode()).hexdigest(), 16)
    age = 30 + (h % 56)
    year = 2025 - age
    month = 1 + (h >> 8) % 12
    day = 1 + (h >> 16) % 28
    return f"{year}-{month:02d}-{day:02d}"


def get_existing_mimic_note_ids(pg_session: Session) -> set[str]:
    """Get set of already-imported MIMIC note_ids from PostgreSQL."""
    try:
        # DB column is "metadata" but SQLAlchemy attribute is "extra_metadata"
        rows = pg_session.execute(
            text("SELECT metadata->>'mimic_note_id' FROM documents WHERE metadata->>'source' = 'mimic-iv-note'")
        ).scalars().all()
        return {r for r in rows if r}
    except Exception as e:
        logger.warning(f"Could not check existing note IDs: {e}")
        return set()


def count_notes(sqlite_conn: sqlite3.Connection, category: str | None) -> tuple[int, int]:
    """Count notes and patients for a category."""
    where = "WHERE note_category = ?" if category else ""
    params = (category,) if category else ()

    row = sqlite_conn.execute(
        f"SELECT COUNT(*), COUNT(DISTINCT subject_id) FROM notes {where}", params
    ).fetchone()
    return row[0], row[1]


def stream_patients(
    sqlite_conn: sqlite3.Connection,
    category: str | None,
    max_patients: int | None,
) -> list[str]:
    """Get list of patient subject_ids to process."""
    where = "WHERE note_category = ?" if category else ""
    params: list = [category] if category else []

    limit = f"LIMIT {max_patients}" if max_patients else ""

    query = f"""
        SELECT subject_id, COUNT(*) as note_count
        FROM notes {where}
        GROUP BY subject_id
        ORDER BY note_count DESC, subject_id
        {limit}
    """
    rows = sqlite_conn.execute(query, params).fetchall()
    return [r[0] for r in rows]


def preload(
    category: str | None,
    max_patients: int | None,
    dry_run: bool,
    enqueue: bool,
    batch_size: int,
    skip_duplicates: bool,
):
    if not DB_PATH.exists():
        logger.error(f"MIMIC database not found: {DB_PATH}")
        sys.exit(1)

    sqlite_conn = sqlite3.connect(str(DB_PATH))
    sqlite_conn.row_factory = sqlite3.Row

    # Summary
    cat_label = category or "ALL"
    note_count, patient_count = count_notes(sqlite_conn, category)
    logger.info(f"MIMIC SQLite: {note_count:,} notes across {patient_count:,} patients [{cat_label}]")

    if max_patients:
        logger.info(f"Limiting to {max_patients:,} patients")

    # Get patient list (ordered by note count descending — richest patients first)
    patient_ids = stream_patients(sqlite_conn, category, max_patients)
    logger.info(f"Selected {len(patient_ids):,} patients to preload")

    if dry_run:
        # Count total notes for selected patients
        placeholders = ",".join("?" * len(patient_ids))
        where_cat = f"AND note_category = '{category}'" if category else ""
        total = sqlite_conn.execute(
            f"SELECT COUNT(*) FROM notes WHERE subject_id IN ({placeholders}) {where_cat}",
            patient_ids,
        ).fetchone()[0]
        logger.info(f"DRY RUN: Would import {total:,} notes from {len(patient_ids):,} patients")

        # Estimate time
        est_hours = total * 0.1 / 3600  # 100ms per doc
        logger.info(f"Estimated NLP processing time: {est_hours:.1f} hours (1 worker)")
        sqlite_conn.close()
        return

    # Connect to PostgreSQL
    engine = get_sync_engine()

    # Get already-imported note IDs for duplicate detection
    existing_note_ids: set[str] = set()
    if skip_duplicates:
        with Session(engine) as session:
            existing_note_ids = get_existing_mimic_note_ids(session)
        logger.info(f"Found {len(existing_note_ids):,} already-imported MIMIC notes")

    # Setup RQ connection
    rq_available = False
    if enqueue:
        try:
            from app.core.queue import enqueue_job
            from app.jobs.document_processing import process_document
            rq_available = True
            logger.info("RQ queue available — will enqueue NLP processing jobs")
        except Exception as e:
            logger.warning(f"RQ not available ({e}) — documents will be imported but not processed")

    # Main import loop
    batch_id = str(uuid4())
    total_created = 0
    total_skipped = 0
    total_failed = 0
    total_notes = 0
    patients_done = 0
    start_time = time.time()

    for patient_idx, subject_id in enumerate(patient_ids):
        if _shutdown_requested:
            logger.warning("Graceful shutdown — stopping after current patient")
            break

        # Fetch all notes for this patient
        where_cat = "AND note_category = ?" if category else ""
        params = [subject_id] + ([category] if category else [])
        notes = sqlite_conn.execute(
            f"SELECT note_id, subject_id, hadm_id, note_type, note_category, charttime, text "
            f"FROM notes WHERE subject_id = ? {where_cat} ORDER BY charttime DESC",
            params,
        ).fetchall()

        # Generate deterministic demographics
        first, last, gender = deterministic_name(subject_id, patient_idx)
        dob = deterministic_dob(subject_id)
        patient_name = f"{first} {last}"

        batch_docs: list[Document] = []

        with Session(engine) as session:
            for note in notes:
                total_notes += 1
                note_id = note["note_id"]
                note_text = note["text"]

                if not note_text or not note_text.strip():
                    total_failed += 1
                    continue

                # Skip duplicates
                if skip_duplicates and str(note_id) in existing_note_ids:
                    total_skipped += 1
                    continue

                doc_id = str(uuid4())
                note_type_display = note["note_category"] or note["note_type"] or "Clinical Note"

                meta = {
                    "mimic_note_id": str(note_id),
                    "mimic_subject_id": subject_id,
                    "mimic_hadm_id": note["hadm_id"] or "",
                    "mimic_batch_id": batch_id,
                    "source": "mimic-iv-note",
                    "patient_name": patient_name,
                    "patient_gender": gender,
                    "patient_dob": dob,
                }

                doc = Document(
                    id=doc_id,
                    patient_id=f"MIMIC-{subject_id}",
                    note_type=note_type_display,
                    text=note_text,
                    extra_metadata=meta,
                    status=JobStatus.QUEUED,
                )

                session.add(doc)
                batch_docs.append(doc)
                total_created += 1

                # Track for duplicate detection
                existing_note_ids.add(str(note_id))

            # Commit this patient's documents
            if batch_docs:
                session.commit()

                # Enqueue NLP processing
                if rq_available:
                    for doc in batch_docs:
                        try:
                            enqueue_job(
                                process_document,
                                doc.id,
                                queue_name="document_processing",
                            )
                        except Exception as e:
                            logger.warning(f"Failed to enqueue doc {doc.id}: {e}")

        patients_done += 1

        # Progress logging
        if patients_done % 100 == 0 or patients_done == len(patient_ids):
            elapsed = time.time() - start_time
            rate = total_notes / elapsed if elapsed > 0 else 0
            eta_min = (len(patient_ids) - patients_done) / (patients_done / elapsed) / 60 if patients_done > 0 else 0
            logger.info(
                f"Progress: {patients_done:,}/{len(patient_ids):,} patients | "
                f"{total_created:,} created, {total_skipped:,} skipped, {total_failed:,} failed | "
                f"{rate:,.0f} notes/sec | ETA: {eta_min:.0f}m"
            )

    sqlite_conn.close()

    elapsed = time.time() - start_time
    logger.info("=" * 70)
    logger.info(f"PRELOAD COMPLETE [{cat_label}]")
    logger.info(f"  Patients processed:  {patients_done:,}")
    logger.info(f"  Notes scanned:       {total_notes:,}")
    logger.info(f"  Documents created:   {total_created:,}")
    logger.info(f"  Duplicates skipped:  {total_skipped:,}")
    logger.info(f"  Failed/empty:        {total_failed:,}")
    logger.info(f"  Batch ID:            {batch_id}")
    logger.info(f"  Time:                {elapsed:.1f}s ({elapsed/60:.1f}m)")
    if rq_available and total_created > 0:
        est_hours = total_created * 0.1 / 3600
        logger.info(f"  NLP queue:           {total_created:,} jobs queued")
        logger.info(f"  Est. NLP time:       {est_hours:.1f}h (1 worker), {est_hours/4:.1f}h (4 workers)")
        logger.info(f"  Start workers:       cd backend && bash scripts/run_worker.sh")
    logger.info("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Bulk-preload MIMIC patients from SQLite into PostgreSQL + RQ pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with 50 patients first
  python tools/preload_mimic.py --category "Discharge Summary" --max-patients 50

  # Dry run to see counts
  python tools/preload_mimic.py --category "Discharge Summary" --dry-run

  # Full discharge summary preload (331K notes, ~9h NLP with 1 worker)
  python tools/preload_mimic.py --category "Discharge Summary"

  # Radiology reports (2.3M notes — run with --max-patients first)
  python tools/preload_mimic.py --category "Radiology Report" --max-patients 5000

  # Import without NLP (process later by starting workers)
  python tools/preload_mimic.py --category "Discharge Summary" --no-enqueue

After preloading, start RQ workers for NLP processing:
  cd backend && bash scripts/run_worker.sh
        """,
    )
    parser.add_argument(
        "--category",
        choices=["Discharge Summary", "Radiology Report", "ED Triage"],
        help="Note category to preload (default: all)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Preload all categories",
    )
    parser.add_argument(
        "--max-patients",
        type=int,
        default=None,
        help="Maximum number of patients to preload (ordered by note count, richest first)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count only, don't import anything",
    )
    parser.add_argument(
        "--no-enqueue",
        action="store_true",
        help="Import documents but don't enqueue NLP processing",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Commit batch size (default: 100)",
    )
    parser.add_argument(
        "--no-skip-duplicates",
        action="store_true",
        help="Don't skip already-imported notes (default: skip duplicates)",
    )

    args = parser.parse_args()

    if not args.category and not args.all:
        parser.error("Specify --category or --all")

    categories = (
        [args.category] if args.category
        else ["Discharge Summary", "Radiology Report", "ED Triage"]
    )

    for cat in categories:
        if _shutdown_requested:
            break
        preload(
            category=cat,
            max_patients=args.max_patients,
            dry_run=args.dry_run,
            enqueue=not args.no_enqueue,
            batch_size=args.batch_size,
            skip_duplicates=not args.no_skip_duplicates,
        )


if __name__ == "__main__":
    main()
