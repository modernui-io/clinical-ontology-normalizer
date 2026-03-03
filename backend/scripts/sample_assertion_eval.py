#!/usr/bin/env python3
"""Sample ~200 mentions from ClinicalBench patients for assertion classifier evaluation.

Produces a stratified sample across assertion types, with context windows
for physician annotation. Output: backend/data/benchmarks/assertion_eval_sample.jsonl

Usage:
    cd backend
    uv run python3 scripts/sample_assertion_eval.py
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Sampling targets per assertion type
SAMPLE_TARGETS = {
    "present": 50,
    "absent": 50,
    "possible": 30,
    "historical": 30,
    "conditional": 15,
    "hypothetical": 15,
    "family_history": 10,  # via experiencer=FAMILY
}

CONTEXT_WINDOW = 200  # chars before/after mention
SEED = 0.42


def get_patient_ids():
    """Load ClinicalBench patient IDs from benchmark files."""
    patient_ids = set()
    for fname in ["task_a.json", "task_b.json"]:
        path = os.path.join(os.path.dirname(__file__), "..", "data", "benchmarks", fname)
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            for q in data["questions"]:
                patient_ids.add(q["mimic_subject_id"])
    return patient_ids


def extract_context(doc_text: str, start: int, end: int) -> str:
    """Extract ±CONTEXT_WINDOW chars around mention, marking it with >>> <<<."""
    ctx_start = max(0, start - CONTEXT_WINDOW)
    ctx_end = min(len(doc_text), end + CONTEXT_WINDOW)
    before = doc_text[ctx_start:start]
    mention = doc_text[start:end]
    after = doc_text[end:ctx_end]
    return f"{before}>>>{mention}<<<{after}"


def main():
    import logging
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    from sqlalchemy import text
    from app.core.database import get_sync_engine

    engine = get_sync_engine()
    patient_ids = get_patient_ids()
    pids = [f"MIMIC-{pid}" for pid in patient_ids]

    print(f"ClinicalBench patients: {len(patient_ids)}")

    output_path = Path(__file__).parent.parent / "data" / "benchmarks" / "assertion_eval_sample.jsonl"
    samples = []

    with engine.connect() as conn:
        # Set seed for reproducible random sampling
        conn.execute(text("SELECT SETSEED(:seed)"), {"seed": SEED})

        # Get counts per assertion type for our patients
        result = conn.execute(text("""
            SELECT m.assertion, COUNT(*) as cnt
            FROM mentions m
            JOIN documents d ON m.document_id = d.id
            WHERE d.patient_id = ANY(:pids)
            GROUP BY m.assertion
            ORDER BY cnt DESC
        """), {"pids": pids})
        db_counts = {row[0]: row[1] for row in result.fetchall()}

        print(f"\nAssertion distribution in DB:")
        total_db = sum(db_counts.values())
        for assertion, count in sorted(db_counts.items(), key=lambda x: -x[1]):
            print(f"  {assertion:<20} {count:>6} ({count/total_db*100:>5.1f}%)")
        print(f"  {'TOTAL':<20} {total_db:>6}")

        # Also check family experiencer mentions
        result = conn.execute(text("""
            SELECT COUNT(*) FROM mentions m
            JOIN documents d ON m.document_id = d.id
            WHERE d.patient_id = ANY(:pids) AND m.experiencer = 'family'
        """), {"pids": pids})
        family_count = result.scalar()
        print(f"\n  experiencer=FAMILY:  {family_count:>6}")

        # Sample each assertion type
        for assertion, target in SAMPLE_TARGETS.items():
            if assertion == "family_history":
                # Special case: sample by experiencer=FAMILY
                query = text("""
                    SELECT m.id, m.text, m.start_offset, m.end_offset,
                           m.assertion, m.confidence, m.experiencer,
                           d.id as doc_id, d.patient_id, d.note_type, d.text as doc_text
                    FROM mentions m
                    JOIN documents d ON m.document_id = d.id
                    WHERE d.patient_id = ANY(:pids)
                      AND m.experiencer = 'family'
                    ORDER BY RANDOM()
                    LIMIT :lim
                """)
                params = {"pids": pids, "lim": target}
            else:
                query = text("""
                    SELECT m.id, m.text, m.start_offset, m.end_offset,
                           m.assertion, m.confidence, m.experiencer,
                           d.id as doc_id, d.patient_id, d.note_type, d.text as doc_text
                    FROM mentions m
                    JOIN documents d ON m.document_id = d.id
                    WHERE d.patient_id = ANY(:pids)
                      AND m.assertion = :assertion
                    ORDER BY RANDOM()
                    LIMIT :lim
                """)
                params = {"pids": pids, "assertion": assertion, "lim": target}

            # Re-seed before each stratum for reproducibility
            conn.execute(text("SELECT SETSEED(:seed)"), {"seed": SEED})
            result = conn.execute(query, params)
            rows = result.fetchall()

            for row in rows:
                context = extract_context(
                    row.doc_text, row.start_offset, row.end_offset
                )
                samples.append({
                    "mention_id": str(row.id),
                    "mention_text": row.text,
                    "start_offset": row.start_offset,
                    "end_offset": row.end_offset,
                    "document_id": str(row.doc_id),
                    "patient_id": row.patient_id,
                    "note_type": row.note_type,
                    "context_window": context,
                    "classifier_prediction": row.assertion
                        if assertion != "family_history" else "family_history",
                    "classifier_confidence": row.confidence,
                    "experiencer": row.experiencer,
                    "gold_label": None,
                })

            actual = len(rows)
            avail = db_counts.get(assertion, family_count if assertion == "family_history" else 0)
            status = "ALL" if actual < target else "sampled"
            print(f"  {assertion:<20} {actual:>3}/{target} ({status}, {avail} available)")

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for s in samples:
            f.write(json.dumps(s) + "\n")

    print(f"\nWrote {len(samples)} samples to {output_path}")

    # Summary
    from collections import Counter
    pred_counts = Counter(s["classifier_prediction"] for s in samples)
    print(f"\nSample breakdown:")
    for pred, cnt in sorted(pred_counts.items(), key=lambda x: -x[1]):
        print(f"  {pred:<20} {cnt:>3}")


if __name__ == "__main__":
    main()
