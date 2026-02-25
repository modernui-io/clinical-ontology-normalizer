#!/usr/bin/env python3
"""Seed KG nodes and edges from benchmark question metadata.

Creates lightweight KG entries from the clinical_context and metadata
in benchmark questions, giving C3/C4 conditions graph paths to work with.

v2: Populates temporal fields (temporality, source_document_id, hadm_id)
    and deduplicates edges by (patient, concept, admission) to support
    cross-admission comparison retrieval (C4g change questions).

Usage:
    cd backend
    DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/clinical_ontology" \
        uv run python scripts/seed_benchmark_kg.py [--reseed]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BENCHMARK_DIR = Path("data/benchmarks")
TASK_FILES = ["task_a.json", "task_b.json", "task_c.json", "task_d.json"]


_JUNK_TERMS = {
    # Common English words
    "The", "This", "That", "She", "Her", "His", "Has", "Was", "Did", "Not",
    "For", "And", "With", "From", "Most", "Will", "None", "Also", "Some",
    "Please", "Patient", "Does", "Should", "Would", "Could", "Have", "Been",
    "Between", "Three", "Small", "Mild", "Left", "Right", "Daily", "Once",
    "Twice", "Take", "Apply", "Oral", "Use", "One", "Two", "Per", "Every",
    "Day", "Time", "After", "Before", "Each", "Yes", "Active", "Acute",
    # Prescription/pharmacy noise
    "Tablet", "Capsule", "Solution", "Disp", "Sig", "Refills", "Powder",
    "Cream", "Topical", "Subcutaneous", "Injection", "Pen", "Tablet Sig",
    "Powder Sig", "Topical Cream Apply", "Subcutaneous Solution",
    "Subcutaneous  Insulin Pen", "Admission",
    # Clinical note section headers
    "History", "Assessment", "Diagnosis", "Medications", "Allergies",
    "Physical Exam", "Hospital Course", "Review", "Systems", "Sections",
    "Discharge Instructions", "Present Illness", "Past Medical History",
    "Relevant", "Discharge",
}

# Structured context pattern: "Admission N (ID): concept1, concept2, ..."
_ADMISSION_LIST_RE = re.compile(
    r'Admission\s+\d+\s*\((\d+)\)\s*:\s*(.+?)(?:\.|$)', re.IGNORECASE
)


def extract_concepts_from_structured_context(context: str) -> dict[str, list[str]]:
    """Parse structured clinical_context into per-admission concept lists.

    Returns {hadm_id: [concept1, concept2, ...]} for structured contexts,
    or {"_all": [concepts]} for unstructured text.
    """
    result: dict[str, list[str]] = {}
    for m in _ADMISSION_LIST_RE.finditer(context):
        hadm_id = m.group(1)
        concepts = [c.strip() for c in m.group(2).split(",") if c.strip()]
        result[hadm_id] = concepts
    return result


def extract_concepts_from_context(context: str) -> list[str]:
    """Extract clinical concept terms from clinical context text."""
    concepts = set()

    # Clinical pattern matching (specific terms)
    clinical_patterns = [
        r'\b(diabetes|hypertension|COPD|CHF|DVT|PE|sepsis|pneumonia|atrial fibrillation)\b',
        r'\b(tachycardia|bradycardia|hypotension|fever|afebrile|hypoxia)\b',
        r'\b(crackles|wheezes|rhonchi|edema|murmur|rash|osteomyelitis)\b',
        r'\b(aspirin|metformin|lisinopril|insulin|warfarin|heparin|metoprolol)\b',
        r'\b(prednisone|vancomycin|ceftriaxone|omeprazole|atenolol|losartan)\b',
        r'\b(hydrochlorothiazide|tiotropium|hydrocodone|lactulose|naproxen)\b',
        r'\b(acetaminophen|lovenox|entresto|clotrimazole|furosemide|amlodipine)\b',
        r'\b(CBC|BMP|CMP|ABG|troponin|lactate|creatinine|potassium|sodium)\b',
    ]
    for pattern in clinical_patterns:
        for match in re.finditer(pattern, context, re.IGNORECASE):
            concepts.add(match.group(0).strip())

    # Capitalized multi-word clinical terms (more restrictive)
    for match in re.finditer(r'\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,2})\b', context):
        term = match.group(1)
        if (term not in _JUNK_TERMS
                and not any(j in term for j in ("Sig", "Disp", "Refill", "Instructions"))
                and len(term) > 3):
            concepts.add(term)

    return list(concepts)[:15]


def _build_doc_lookup(engine) -> dict[tuple[str, str], str]:
    """Build (patient_id, hadm_id) -> document_id lookup from documents table."""
    from sqlalchemy import text
    lookup = {}
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT id, patient_id, metadata FROM documents WHERE metadata IS NOT NULL"
        ))
        for row in result:
            patient_id = row[1]
            meta = row[2] if isinstance(row[2], dict) else {}
            hadm_id = meta.get("mimic_hadm_id")
            if hadm_id:
                lookup[(patient_id, str(hadm_id))] = str(row[0])
    return lookup


def _create_node_and_edge(
    concept_text: str,
    patient_id: str,
    hadm_id: str | None,
    edge_type: str,
    assertion: str,
    section: str,
    temporality: str | None,
    doc_lookup: dict,
    seen_nodes: dict,
    seen_edges: set,
    nodes_to_insert: list,
    edges_to_insert: list,
    patient_root_nodes: dict,
) -> None:
    """Create a KG node + edge for a single concept, deduping as needed."""
    node_key = (patient_id, concept_text.lower())
    if node_key not in seen_nodes:
        node_id = str(uuid4())
        seen_nodes[node_key] = node_id
        node_type = "drug" if edge_type == "takes_drug" else "condition" if edge_type == "has_condition" else "observation"
        nodes_to_insert.append({
            "id": node_id,
            "patient_id": patient_id,
            "node_type": node_type,
            "label": concept_text,
            "properties": json.dumps({"source": "benchmark_seed"}),
        })

    target_node_id = seen_nodes[node_key]
    root_id = patient_root_nodes[patient_id]

    edge_key = (patient_id, concept_text.lower(), hadm_id)
    if edge_key in seen_edges:
        return
    seen_edges.add(edge_key)

    source_doc_id = None
    if hadm_id:
        source_doc_id = doc_lookup.get((patient_id, hadm_id))

    edges_to_insert.append({
        "id": str(uuid4()),
        "patient_id": patient_id,
        "source_node_id": root_id,
        "target_node_id": target_node_id,
        "edge_type": edge_type,
        "temporality": temporality,
        "source_document_id": source_doc_id,
        "properties": json.dumps({
            "assertion": assertion,
            "section": section,
            "source": "benchmark_seed",
            "hadm_id": hadm_id,
        }),
    })


def main():
    parser = argparse.ArgumentParser(description="Seed benchmark KG")
    parser.add_argument("--reseed", action="store_true", help="Drop existing KG data and reseed")
    args = parser.parse_args()

    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/clinical_ontology",
    )
    db_url = db_url.replace("asyncpg", "psycopg2").replace("postgresql://", "postgresql+psycopg2://")

    from sqlalchemy import create_engine, text
    engine = create_engine(db_url)

    # Check if KG already seeded
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM kg_nodes"))
        existing = result.scalar()
        if existing and existing > 0:
            if not args.reseed:
                print(f"Database already has {existing} KG nodes. Use --reseed to recreate.")
                return
            print(f"Reseeding: dropping {existing} existing nodes and edges...")
            with engine.begin() as drop_conn:
                drop_conn.execute(text("DELETE FROM kg_edges WHERE properties::text LIKE '%benchmark_seed%'"))
                drop_conn.execute(text("DELETE FROM kg_nodes WHERE properties::text LIKE '%benchmark_seed%'"))

    # Build document lookup for source_document_id
    doc_lookup = _build_doc_lookup(engine)
    print(f"Document lookup: {len(doc_lookup)} (patient, hadm) -> doc_id mappings")

    # Collect questions and build KG entries
    nodes_to_insert = []
    edges_to_insert = []
    patient_root_nodes = {}  # patient_id -> root node UUID
    # Dedup nodes by (patient_id, concept_text) — one node per concept per patient
    seen_nodes = {}  # (patient_id, concept_text) -> node UUID
    # Dedup edges by (patient_id, concept_text, hadm_id) — per-admission edges
    seen_edges = set()

    for task_file in TASK_FILES:
        path = BENCHMARK_DIR / task_file
        if not path.exists():
            continue

        with open(path) as f:
            data = json.load(f)

        for q in data.get("questions", []):
            subject_id = q.get("mimic_subject_id")
            if not subject_id:
                continue

            patient_id = f"MIMIC-{subject_id}"
            context = q.get("clinical_context", "")
            metadata = q.get("metadata", {})
            assertion = metadata.get("assertion", "present")
            section = metadata.get("section", "Unknown")
            domain = metadata.get("domain", "observation")
            temporality = metadata.get("temporality")  # "current", "past", etc.

            # Determine admission ID — questions have different field names
            hadm_id = q.get("mimic_hadm_id")
            if hadm_id:
                hadm_id = str(hadm_id)

            # For change/sequence questions, process both admissions
            hadm_1 = metadata.get("hadm_1")
            hadm_2 = metadata.get("hadm_2")
            subtype = q.get("subtype", "")

            # Create patient root node if not exists
            if patient_id not in patient_root_nodes:
                root_id = str(uuid4())
                patient_root_nodes[patient_id] = root_id
                nodes_to_insert.append({
                    "id": root_id,
                    "patient_id": patient_id,
                    "node_type": "patient",
                    "label": patient_id,
                    "properties": json.dumps({"source": "benchmark_seed"}),
                })

            # Determine edge type from domain
            edge_type = {
                "condition": "has_condition",
                "drug": "takes_drug",
                "procedure": "has_procedure",
                "observation": "has_observation",
                "measurement": "has_measurement",
            }.get(domain, "has_observation")

            # --- Concept extraction strategy depends on question type ---
            if subtype == "change" and hadm_1 and hadm_2:
                # Change questions: use structured context + metadata added/removed lists
                # This gives us per-admission concept sets directly
                structured = extract_concepts_from_structured_context(context)
                meta_added = metadata.get("added", [])
                meta_removed = metadata.get("removed", [])

                # Build per-admission concept lists
                adm1_concepts = structured.get(str(hadm_1), [])
                adm2_concepts = structured.get(str(hadm_2), [])
                # Merge metadata added/removed into the right admission
                for c in meta_added:
                    if c not in adm2_concepts:
                        adm2_concepts.append(c)
                for c in meta_removed:
                    if c not in adm1_concepts:
                        adm1_concepts.append(c)

                # Create edges for admission 1 concepts
                for concept_text in adm1_concepts:
                    _create_node_and_edge(
                        concept_text, patient_id, str(hadm_1), edge_type,
                        assertion, section, temporality, doc_lookup,
                        seen_nodes, seen_edges, nodes_to_insert, edges_to_insert,
                        patient_root_nodes,
                    )
                # Create edges for admission 2 concepts
                for concept_text in adm2_concepts:
                    _create_node_and_edge(
                        concept_text, patient_id, str(hadm_2), edge_type,
                        assertion, section, temporality, doc_lookup,
                        seen_nodes, seen_edges, nodes_to_insert, edges_to_insert,
                        patient_root_nodes,
                    )
                continue  # Skip the generic path below

            # Non-change questions: extract concepts from context text
            concepts = extract_concepts_from_context(context)

            # Extract key clinical term from question (more restrictive regex)
            question_text = q.get("question", "")
            q_match = re.search(
                r'(?:have|has|taking|on|diagnosed with|history of|suffer from)\s+'
                r'([a-zA-Z][a-zA-Z\s]{2,30}?)\?',
                question_text, re.IGNORECASE,
            )
            if q_match:
                key_concept = q_match.group(1).strip().rstrip(".")
                # Filter out question fragments that aren't real concepts
                if (key_concept and len(key_concept) > 2
                        and not any(w in key_concept.lower() for w in
                                    ("been", "the patient", "this patient", "an active", "clinical notes"))):
                    concepts.insert(0, key_concept)

            if hadm_id:
                admission_ids = [hadm_id]
            else:
                admission_ids = [None]

            for concept_text in concepts:
                # Create node (dedup by patient + concept)
                node_key = (patient_id, concept_text.lower())
                if node_key not in seen_nodes:
                    node_id = str(uuid4())
                    seen_nodes[node_key] = node_id

                    node_type = {
                        "condition": "condition",
                        "drug": "drug",
                        "procedure": "procedure",
                        "observation": "observation",
                        "measurement": "measurement",
                    }.get(domain, "observation")

                    nodes_to_insert.append({
                        "id": node_id,
                        "patient_id": patient_id,
                        "node_type": node_type,
                        "label": concept_text[:500],
                        "properties": json.dumps({
                            "assertion": assertion,
                            "section": section,
                            "domain": domain,
                            "source": "benchmark_seed",
                        }),
                    })

                target_node_id = seen_nodes[node_key]
                root_id = patient_root_nodes[patient_id]

                # Create edges (dedup by patient + concept + admission)
                for adm_id in admission_ids:
                    edge_key = (patient_id, concept_text.lower(), adm_id)
                    if edge_key in seen_edges:
                        continue
                    seen_edges.add(edge_key)

                    # Find source document for this patient + admission
                    source_doc_id = None
                    if adm_id:
                        source_doc_id = doc_lookup.get((patient_id, adm_id))

                    edges_to_insert.append({
                        "id": str(uuid4()),
                        "patient_id": patient_id,
                        "source_node_id": root_id,
                        "target_node_id": target_node_id,
                        "edge_type": edge_type,
                        "temporality": temporality,
                        "source_document_id": source_doc_id,
                        "properties": json.dumps({
                            "assertion": assertion,
                            "section": section,
                            "source": "benchmark_seed",
                            "hadm_id": adm_id,
                        }),
                    })

    print(f"Prepared {len(nodes_to_insert)} KG nodes and {len(edges_to_insert)} edges")

    # Count temporal coverage
    with_temp = sum(1 for e in edges_to_insert if e.get("temporality"))
    with_doc = sum(1 for e in edges_to_insert if e.get("source_document_id"))
    with_hadm = sum(1 for e in edges_to_insert if json.loads(e["properties"]).get("hadm_id"))
    print(f"  with temporality: {with_temp}")
    print(f"  with source_document_id: {with_doc}")
    print(f"  with hadm_id: {with_hadm}")

    # Insert in batches
    with engine.begin() as conn:
        for i, node in enumerate(nodes_to_insert):
            conn.execute(
                text("""
                    INSERT INTO kg_nodes (id, patient_id, node_type, label, properties)
                    VALUES (:id, :patient_id, CAST(:node_type AS node_type), :label, CAST(:properties AS jsonb))
                    ON CONFLICT (id) DO NOTHING
                """),
                node,
            )
            if (i + 1) % 500 == 0:
                print(f"  Inserted {i + 1}/{len(nodes_to_insert)} nodes...")

        for i, edge in enumerate(edges_to_insert):
            conn.execute(
                text("""
                    INSERT INTO kg_edges (
                        id, patient_id, source_node_id, target_node_id, edge_type,
                        properties, temporality, source_document_id
                    )
                    VALUES (
                        :id, :patient_id, :source_node_id, :target_node_id,
                        CAST(:edge_type AS edge_type), CAST(:properties AS jsonb),
                        :temporality, :source_document_id
                    )
                    ON CONFLICT (id) DO NOTHING
                """),
                edge,
            )
            if (i + 1) % 500 == 0:
                print(f"  Inserted {i + 1}/{len(edges_to_insert)} edges...")

    # Verify
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM kg_nodes"))
        print(f"Total KG nodes: {result.scalar()}")
        result = conn.execute(text("SELECT COUNT(*) FROM kg_edges"))
        print(f"Total KG edges: {result.scalar()}")
        result = conn.execute(text("SELECT COUNT(*) FROM kg_edges WHERE temporality IS NOT NULL"))
        print(f"  with temporality: {result.scalar()}")
        result = conn.execute(text("SELECT COUNT(*) FROM kg_edges WHERE source_document_id IS NOT NULL"))
        print(f"  with source_document_id: {result.scalar()}")
        result = conn.execute(text("SELECT COUNT(DISTINCT patient_id) FROM kg_nodes"))
        print(f"Unique patients with KG: {result.scalar()}")

    print("Done!")


if __name__ == "__main__":
    main()
