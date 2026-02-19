#!/usr/bin/env python3
"""Export 50 MIMIC patients with de-identified names into import-ready CSV."""

import csv
import hashlib
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "mimic_notes.db"
OUTPUT_CSV = Path(__file__).parent / "mimic_50_patients.csv"

# Deterministic fake names (seeded from subject_id hash)
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


def deterministic_name(subject_id: str, index: int) -> tuple[str, str, str]:
    """Generate a deterministic fake name and gender from subject_id."""
    h = int(hashlib.md5(f"{subject_id}-{index}".encode()).hexdigest(), 16)
    gender = "M" if h % 2 == 0 else "F"
    first_names = FIRST_NAMES_M if gender == "M" else FIRST_NAMES_F
    first = first_names[h % len(first_names)]
    last = LAST_NAMES[(h >> 8) % len(LAST_NAMES)]
    return first, last, gender


def deterministic_dob(subject_id: str) -> str:
    """Generate a plausible DOB (age 30-85) from subject_id."""
    h = int(hashlib.md5(f"dob-{subject_id}".encode()).hexdigest(), 16)
    age = 30 + (h % 56)  # 30-85
    year = 2025 - age
    month = 1 + (h >> 8) % 12
    day = 1 + (h >> 16) % 28
    return f"{year}-{month:02d}-{day:02d}"


def main():
    if not DB_PATH.exists():
        print(f"ERROR: {DB_PATH} not found. Run mimic_loader.py first.")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # Get 50 patients with 2+ discharge summaries
    patients = conn.execute("""
        SELECT subject_id, count(*) as note_count
        FROM notes
        WHERE note_type = 'DS'
        GROUP BY subject_id
        HAVING note_count >= 2
        ORDER BY subject_id
        LIMIT 50
    """).fetchall()

    print(f"Selected {len(patients)} patients")

    rows = []
    for i, pat in enumerate(patients):
        subject_id = pat["subject_id"]
        first, last, gender = deterministic_name(str(subject_id), i)
        dob = deterministic_dob(str(subject_id))

        # Get up to 2 discharge summaries per patient
        notes = conn.execute("""
            SELECT note_id, subject_id, hadm_id, note_type, charttime, text
            FROM notes
            WHERE subject_id = ? AND note_type = 'DS'
            ORDER BY charttime DESC
            LIMIT 2
        """, (subject_id,)).fetchall()

        for note in notes:
            rows.append({
                "note_id": note["note_id"],
                "subject_id": subject_id,
                "hadm_id": note["hadm_id"],
                "note_type": "Discharge Summary",
                "charttime": note["charttime"] or "",
                "text": note["text"],
                "patient_name": f"{first} {last}",
                "patient_gender": gender,
                "patient_dob": dob,
            })

    conn.close()

    # Write CSV
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "note_id", "subject_id", "hadm_id", "note_type", "charttime",
            "text", "patient_name", "patient_gender", "patient_dob",
        ])
        writer.writeheader()
        writer.writerows(rows)

    unique_patients = len(set(r["subject_id"] for r in rows))
    print(f"Wrote {len(rows)} notes from {unique_patients} patients to {OUTPUT_CSV}")
    print(f"File size: {OUTPUT_CSV.stat().st_size / 1024 / 1024:.1f} MB")

    # Print sample
    print("\nSample patients:")
    seen = set()
    for r in rows:
        if r["subject_id"] not in seen:
            seen.add(r["subject_id"])
            print(f"  {r['subject_id']} -> {r['patient_name']} ({r['patient_gender']}, DOB {r['patient_dob']})")
            if len(seen) >= 10:
                break


if __name__ == "__main__":
    main()
