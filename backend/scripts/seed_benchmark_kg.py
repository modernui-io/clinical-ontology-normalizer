#!/usr/bin/env python3
"""Seed KG nodes and edges from benchmark question metadata.

Creates lightweight KG entries from the clinical_context and metadata
in benchmark questions, giving C3/C4 conditions graph paths to work with.

Usage:
    cd backend
    DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/clinical_ontology" \
        uv run python scripts/seed_benchmark_kg.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BENCHMARK_DIR = Path("data/benchmarks")
TASK_FILES = ["task_a.json", "task_b.json", "task_c.json", "task_d.json"]


def extract_concepts_from_context(context: str) -> list[str]:
    """Extract clinical concept terms from clinical context text."""
    # Common clinical terms to look for
    concepts = set()

    # Look for capitalized clinical terms
    for match in re.finditer(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', context):
        term = match.group(1)
        if len(term) > 3 and term not in {"The", "This", "That", "She", "Her", "His", "Has", "Was", "Did", "Not", "For", "And", "With", "From", "Most", "Will", "None", "Also", "Some"}:
            concepts.add(term)

    # Look for common clinical patterns
    clinical_patterns = [
        r'\b(diabetes|hypertension|COPD|CHF|DVT|PE|sepsis|pneumonia|atrial fibrillation)\b',
        r'\b(tachycardia|bradycardia|hypotension|fever|afebrile|hypoxia)\b',
        r'\b(crackles|wheezes|rhonchi|edema|murmur|rash)\b',
        r'\b(aspirin|metformin|lisinopril|insulin|warfarin|heparin|metoprolol)\b',
        r'\b(CBC|BMP|CMP|ABG|troponin|lactate|creatinine|potassium|sodium)\b',
        r'(?:HR|heart rate)\s*[:=]?\s*(\d+)',
        r'(?:BP|blood pressure)\s*[:=]?\s*(\d+/\d+)',
        r'(?:Temp|temperature)\s*[:=]?\s*(\d+\.?\d*)',
        r'(?:SpO2|O2 sat)\s*[:=]?\s*(\d+)',
    ]
    for pattern in clinical_patterns:
        for match in re.finditer(pattern, context, re.IGNORECASE):
            concepts.add(match.group(0).strip())

    return list(concepts)[:15]  # Limit per question


def main():
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
            print(f"Database already has {existing} KG nodes. Skipping seed.")
            return

    # Collect questions and build KG entries
    nodes_to_insert = []
    edges_to_insert = []
    patient_root_nodes = {}  # patient_id -> root node UUID
    seen_concepts = {}  # (patient_id, concept_text) -> node UUID

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

            # Extract concepts from context
            concepts = extract_concepts_from_context(context)

            # Also use the question itself as a concept source
            question_text = q.get("question", "")
            # Extract the key clinical term from the question
            # e.g., "Does the patient have crackles?" -> "crackles"
            q_match = re.search(r'(?:have|has|taking|on|diagnosed with|history of)\s+(.+?)\?', question_text, re.IGNORECASE)
            if q_match:
                key_concept = q_match.group(1).strip().rstrip(".")
                if key_concept and len(key_concept) > 2:
                    concepts.insert(0, key_concept)  # Primary concept first

            for concept_text in concepts:
                concept_key = (patient_id, concept_text.lower())

                if concept_key not in seen_concepts:
                    node_id = str(uuid4())
                    seen_concepts[concept_key] = node_id

                    # Determine node type from domain
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

                    # Create edge from patient root to concept
                    root_id = patient_root_nodes[patient_id]
                    edge_type = {
                        "condition": "has_condition",
                        "drug": "takes_drug",
                        "procedure": "has_procedure",
                        "observation": "has_observation",
                        "measurement": "has_measurement",
                    }.get(domain, "has_observation")

                    edges_to_insert.append({
                        "id": str(uuid4()),
                        "patient_id": patient_id,
                        "source_node_id": root_id,
                        "target_node_id": node_id,
                        "edge_type": edge_type,
                        "properties": json.dumps({
                            "assertion": assertion,
                            "section": section,
                            "source": "benchmark_seed",
                        }),
                    })

    print(f"Prepared {len(nodes_to_insert)} KG nodes and {len(edges_to_insert)} edges")

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
                    INSERT INTO kg_edges (id, patient_id, source_node_id, target_node_id, edge_type, properties)
                    VALUES (:id, :patient_id, :source_node_id, :target_node_id, CAST(:edge_type AS edge_type), CAST(:properties AS jsonb))
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
        result = conn.execute(text("SELECT COUNT(DISTINCT patient_id) FROM kg_nodes"))
        print(f"Unique patients with KG: {result.scalar()}")

    print("Done!")


if __name__ == "__main__":
    main()
