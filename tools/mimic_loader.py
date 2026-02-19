"""Load MIMIC-IV notes into SQLite with FTS5 full-text search."""

import csv
import gzip
import sqlite3
import sys
import time

DB_PATH = "/Users/alexstinard/projects/brainstorm/jan-14-2026/tools/mimic_notes.db"

DISCHARGE_GZ = "/Users/alexstinard/Downloads/mimic-iv-note-2.2/note/discharge.csv.gz"
RADIOLOGY_GZ = "/Users/alexstinard/Downloads/mimic-iv-note-2.2/note/radiology.csv.gz"
ED_TRIAGE_GZ = "/Volumes/Claude Code 4T 1225/clinical-datasets/mimic-iv-ed-2.2/ed/triage.csv.gz"


def create_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS notes")
    c.execute("DROP TABLE IF EXISTS notes_fts")
    c.execute("""
        CREATE TABLE notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id TEXT,
            subject_id TEXT,
            hadm_id TEXT,
            note_type TEXT,
            note_category TEXT,
            charttime TEXT,
            text TEXT
        )
    """)
    c.execute("CREATE INDEX idx_note_type ON notes(note_category)")
    c.execute("CREATE INDEX idx_subject ON notes(subject_id)")
    c.execute("""
        CREATE VIRTUAL TABLE notes_fts USING fts5(
            note_id, subject_id, note_category, text,
            content='notes',
            content_rowid='id'
        )
    """)
    conn.commit()
    return conn


def load_gz_csv(conn, gz_path, category, note_type_col="note_type"):
    print(f"\nLoading {category} from {gz_path}...")
    c = conn.cursor()
    count = 0
    batch = []
    start = time.time()

    with gzip.open(gz_path, "rt", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            text = row.get("text", row.get("chiefcomplaint", ""))
            if not text or not text.strip():
                continue

            batch.append((
                row.get("note_id", f"{category}-{count}"),
                row.get("subject_id", ""),
                row.get("hadm_id", row.get("stay_id", "")),
                row.get(note_type_col, category),
                category,
                row.get("charttime", ""),
                text,
            ))
            count += 1

            if len(batch) >= 5000:
                c.executemany(
                    "INSERT INTO notes (note_id, subject_id, hadm_id, note_type, note_category, charttime, text) VALUES (?,?,?,?,?,?,?)",
                    batch,
                )
                conn.commit()
                elapsed = time.time() - start
                rate = count / elapsed if elapsed > 0 else 0
                print(f"  {count:>10,} rows  ({rate:,.0f}/sec)", end="\r", flush=True)
                batch = []

    if batch:
        c.executemany(
            "INSERT INTO notes (note_id, subject_id, hadm_id, note_type, note_category, charttime, text) VALUES (?,?,?,?,?,?,?)",
            batch,
        )
        conn.commit()

    elapsed = time.time() - start
    print(f"  {count:>10,} rows  ({elapsed:.1f}s)          ")
    return count


def build_fts(conn):
    print("\nBuilding full-text search index...")
    start = time.time()
    c = conn.cursor()
    c.execute("""
        INSERT INTO notes_fts(rowid, note_id, subject_id, note_category, text)
        SELECT id, note_id, subject_id, note_category, text FROM notes
    """)
    conn.commit()
    elapsed = time.time() - start
    print(f"  FTS index built ({elapsed:.1f}s)")


def main():
    print("=" * 60)
    print("MIMIC-IV Note Loader → SQLite + FTS5")
    print("=" * 60)

    conn = create_db()
    total = 0

    total += load_gz_csv(conn, DISCHARGE_GZ, "Discharge Summary")
    total += load_gz_csv(conn, RADIOLOGY_GZ, "Radiology Report")

    try:
        total += load_gz_csv(conn, ED_TRIAGE_GZ, "ED Triage", note_type_col="acuity")
    except Exception as e:
        print(f"  Skipped ED Triage: {e}")

    build_fts(conn)

    c = conn.cursor()
    c.execute("SELECT note_category, COUNT(*) FROM notes GROUP BY note_category")
    print("\n" + "=" * 60)
    print("Summary:")
    for cat, cnt in c.fetchall():
        print(f"  {cat:25s} {cnt:>12,}")
    print(f"  {'TOTAL':25s} {total:>12,}")
    print(f"\nDatabase: {DB_PATH}")
    print(f"Size: {round(sqlite3.connect(DB_PATH).execute('PRAGMA page_count').fetchone()[0] * sqlite3.connect(DB_PATH).execute('PRAGMA page_size').fetchone()[0] / 1024 / 1024 / 1024, 2)} GB")
    print("=" * 60)

    conn.close()


if __name__ == "__main__":
    main()
