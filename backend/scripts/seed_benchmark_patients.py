#!/usr/bin/env python3
"""Seed the database with documents from benchmark question clinical_context.

Creates one document per unique (patient_id, hadm_id) from the benchmark
question files, using the clinical_context as the document text.

This allows the RAG pipeline (C2-C5) to find patient data for the experiment.

Usage:
    cd backend
    DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/clinical_ontology" \
        uv run python scripts/seed_benchmark_patients.py
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BENCHMARK_DIR = Path("data/benchmarks")
TASK_FILES = ["task_a.json", "task_b.json", "task_c.json", "task_d.json"]


def main():
    # Collect all clinical_context per (patient_id, hadm_id)
    patient_docs: dict[tuple[str, int | None], list[str]] = defaultdict(list)
    question_count = 0

    for task_file in TASK_FILES:
        path = BENCHMARK_DIR / task_file
        if not path.exists():
            print(f"  Skipping {task_file} (not found)")
            continue

        with open(path) as f:
            data = json.load(f)

        questions = data.get("questions", [])
        for q in questions:
            question_count += 1
            subject_id = q.get("mimic_subject_id")
            hadm_id = q.get("mimic_hadm_id")
            context = q.get("clinical_context", "")

            if subject_id and context:
                patient_id = f"MIMIC-{subject_id}"
                patient_docs[(patient_id, hadm_id)].append(context)

    print(f"Found {question_count} questions across {len(TASK_FILES)} task files")
    print(f"Unique (patient, admission) pairs: {len(patient_docs)}")

    # Connect to database
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/clinical_ontology",
    )
    # Ensure sync driver
    db_url = db_url.replace("asyncpg", "psycopg2").replace("postgresql://", "postgresql+psycopg2://")

    from sqlalchemy import create_engine, text
    engine = create_engine(db_url)

    # Check if users table requires foreign key
    with engine.connect() as conn:
        # Check for existing documents
        result = conn.execute(text("SELECT COUNT(*) FROM documents"))
        existing = result.scalar()
        if existing and existing > 0:
            print(f"Database already has {existing} documents. Skipping seed.")
            return

    # Build documents from clinical contexts
    # Merge all contexts per (patient_id, hadm_id) into a single document
    docs_to_insert = []
    for (patient_id, hadm_id), contexts in patient_docs.items():
        # Deduplicate and merge contexts
        unique_contexts = list(dict.fromkeys(contexts))  # preserve order, dedupe
        merged_text = "\n\n---\n\n".join(unique_contexts)

        doc_id = str(uuid4())
        docs_to_insert.append({
            "id": doc_id,
            "patient_id": patient_id,
            "note_type": "Discharge summary",
            "text": merged_text,
            "metadata": json.dumps({
                "source": "benchmark_seed",
                "mimic_hadm_id": hadm_id,
            }),
            "status": "completed",
        })

    print(f"Inserting {len(docs_to_insert)} documents...")

    with engine.begin() as conn:
        for doc in docs_to_insert:
            conn.execute(
                text("""
                    INSERT INTO documents (id, patient_id, note_type, text, metadata, status)
                    VALUES (:id, :patient_id, :note_type, :text, CAST(:meta AS jsonb), :status)
                """),
                {**doc, "meta": doc["metadata"]},
            )

    print(f"Done! Inserted {len(docs_to_insert)} documents.")

    # Verify
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM documents"))
        print(f"Total documents in database: {result.scalar()}")

        result = conn.execute(text("SELECT COUNT(DISTINCT patient_id) FROM documents"))
        print(f"Unique patients: {result.scalar()}")


if __name__ == "__main__":
    main()
