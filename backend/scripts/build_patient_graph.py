#!/usr/bin/env python3
"""
Script to build a knowledge graph for a patient from clinical text.

This script directly inserts nodes and edges into the database to build
a knowledge graph from extracted clinical entities.

Usage:
    python scripts/build_patient_graph.py
"""

import sys
import os
import uuid
from datetime import datetime, UTC

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2


# Clinical entities extracted from the synthetic patient notes
PATIENT_ID = "TEST12345"

# Diagnoses/Conditions
CONDITIONS = [
    ("HFrEF", "Heart failure with reduced ejection fraction, EF ~25%"),
    ("Atrial fibrillation", "Persistent atrial fibrillation"),
    ("CAD", "Coronary artery disease, status post CABG"),
    ("CKD Stage 4", "Chronic kidney disease stage 4, eGFR ~22"),
    ("Type 2 diabetes", "Type 2 diabetes mellitus"),
    ("Hypertension", "Essential hypertension"),
    ("OSA", "Obstructive sleep apnea"),
    ("Anemia", "Chronic anemia, normocytic"),
    ("CABG", "Status post coronary artery bypass grafting"),
    ("Edema", "Bilateral lower extremity edema"),
    ("JVD", "Jugular venous distension"),
    ("Systolic murmur", "Grade II/VI systolic murmur at apex"),
]

# Medications
MEDICATIONS = [
    ("Carvedilol", "25 mg PO BID"),
    ("Lisinopril", "20 mg PO daily"),
    ("Furosemide", "40 mg PO BID"),
    ("Spironolactone", "25 mg PO daily"),
    ("Apixaban", "5 mg PO BID"),
    ("Metformin", "500 mg PO BID"),
    ("Insulin glargine", "20 units subcutaneous at bedtime"),
    ("Atorvastatin", "80 mg PO at bedtime"),
    ("Aspirin", "81 mg PO daily"),
    ("Ferrous sulfate", "325 mg PO daily"),
]

# Lab Results / Measurements
MEASUREMENTS = [
    ("Hemoglobin", "10.2 g/dL", "Low"),
    ("Hematocrit", "31%", "Low"),
    ("BUN", "52 mg/dL", "High"),
    ("Creatinine", "2.8 mg/dL", "High"),
    ("eGFR", "22 mL/min/1.73m2", "Low"),
    ("Sodium", "138 mEq/L", "Normal"),
    ("Potassium", "4.8 mEq/L", "Normal"),
    ("BNP", "850 pg/mL", "High"),
    ("HbA1c", "7.4%", "Elevated"),
    ("Blood pressure", "128/78 mmHg", "Normal"),
    ("Heart rate", "72 bpm", "Normal"),
    ("Temperature", "98.2 F", "Normal"),
    ("SpO2", "96%", "Normal"),
    ("Weight", "95 kg", ""),
    ("BMI", "29.1", "Overweight"),
]

# Procedures
PROCEDURES = [
    ("CABG", "Coronary artery bypass grafting, 3 vessels"),
    ("Echocardiogram", "Ordered - baseline EF assessment"),
    ("CPAP therapy", "Uses CPAP nightly for OSA"),
]

# Allergies
ALLERGIES = [
    ("Penicillin", "Rash"),
]

# Treatment mappings
TREATMENT_MAPPINGS = [
    ("HFrEF", ["Carvedilol", "Lisinopril", "Furosemide", "Spironolactone"]),
    ("Atrial fibrillation", ["Apixaban", "Carvedilol"]),
    ("Type 2 diabetes", ["Metformin", "Insulin glargine"]),
    ("Hypertension", ["Lisinopril", "Carvedilol"]),
    ("CAD", ["Atorvastatin", "Aspirin"]),
    ("Anemia", ["Ferrous sulfate"]),
]


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host='localhost',
        port=5432,
        database='clinical_ontology',
        user='alexstinard'
    )


def insert_node(cur, patient_id, node_type, label, properties):
    """Insert a node and return its ID."""
    node_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO kg_nodes (id, patient_id, node_type, label, properties, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
        (node_id, patient_id, node_type, label, properties, datetime.now(UTC))
    )
    return node_id


def insert_edge(cur, patient_id, source_id, target_id, edge_type, properties='{}'):
    """Insert an edge."""
    edge_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO kg_edges (id, patient_id, source_node_id, target_node_id, edge_type, properties, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (edge_id, patient_id, source_id, target_id, edge_type, properties, datetime.now(UTC))
    )
    return edge_id


def build_knowledge_graph():
    """Build the knowledge graph for the patient."""

    print(f"Building knowledge graph for patient {PATIENT_ID}...")

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # First, clear any existing data for this patient
        cur.execute("DELETE FROM kg_edges WHERE patient_id = %s", (PATIENT_ID,))
        cur.execute("DELETE FROM kg_nodes WHERE patient_id = %s", (PATIENT_ID,))
        print("Cleared existing graph data")

        nodes_created = 0
        edges_created = 0

        # Create patient node
        patient_node_id = insert_node(
            cur, PATIENT_ID, 'patient', f"Patient {PATIENT_ID}",
            '{"age": 64, "sex": "Male", "dob": "1961-04-12"}'
        )
        nodes_created += 1
        print(f"Created patient node: {patient_node_id}")

        # Create condition nodes and edges
        condition_node_ids = {}
        for name, description in CONDITIONS:
            props = f'{{"description": "{description}", "assertion": "present"}}'
            node_id = insert_node(cur, PATIENT_ID, 'condition', name, props)
            condition_node_ids[name] = node_id
            nodes_created += 1

            insert_edge(cur, PATIENT_ID, patient_node_id, node_id, 'has_condition')
            edges_created += 1

        print(f"Created {len(CONDITIONS)} condition nodes")

        # Create medication nodes and edges
        medication_node_ids = {}
        for name, dosage in MEDICATIONS:
            props = f'{{"dosage": "{dosage}"}}'
            node_id = insert_node(cur, PATIENT_ID, 'drug', name, props)
            medication_node_ids[name] = node_id
            nodes_created += 1

            insert_edge(cur, PATIENT_ID, patient_node_id, node_id, 'takes_drug')
            edges_created += 1

        print(f"Created {len(MEDICATIONS)} medication nodes")

        # Create measurement nodes and edges
        for name, value, status in MEASUREMENTS:
            props = f'{{"value": "{value}", "status": "{status}"}}'
            node_id = insert_node(cur, PATIENT_ID, 'measurement', name, props)
            nodes_created += 1

            insert_edge(cur, PATIENT_ID, patient_node_id, node_id, 'has_measurement')
            edges_created += 1

        print(f"Created {len(MEASUREMENTS)} measurement nodes")

        # Create procedure nodes and edges
        for name, description in PROCEDURES:
            props = f'{{"description": "{description}"}}'
            node_id = insert_node(cur, PATIENT_ID, 'procedure', name, props)
            nodes_created += 1

            insert_edge(cur, PATIENT_ID, patient_node_id, node_id, 'has_procedure')
            edges_created += 1

        print(f"Created {len(PROCEDURES)} procedure nodes")

        # Create observation nodes (allergies) and edges
        for allergen, reaction in ALLERGIES:
            props = f'{{"allergen": "{allergen}", "reaction": "{reaction}"}}'
            node_id = insert_node(cur, PATIENT_ID, 'observation', f"Allergy: {allergen}", props)
            nodes_created += 1

            insert_edge(cur, PATIENT_ID, patient_node_id, node_id, 'has_observation')
            edges_created += 1

        print(f"Created {len(ALLERGIES)} observation nodes")

        # Create treatment relationships (condition -> medication)
        for condition_name, med_names in TREATMENT_MAPPINGS:
            if condition_name in condition_node_ids:
                for med_name in med_names:
                    if med_name in medication_node_ids:
                        insert_edge(
                            cur, PATIENT_ID,
                            condition_node_ids[condition_name],
                            medication_node_ids[med_name],
                            'condition_treated_by'
                        )
                        edges_created += 1

        print("Created treatment relationships")

        # Commit all changes
        conn.commit()

        print(f"\n=== Knowledge Graph Built ===")
        print(f"Total nodes created: {nodes_created}")
        print(f"Total edges created: {edges_created}")
        print(f"\nNode breakdown:")
        print(f"  - Patient: 1")
        print(f"  - Conditions: {len(CONDITIONS)}")
        print(f"  - Medications: {len(MEDICATIONS)}")
        print(f"  - Measurements: {len(MEASUREMENTS)}")
        print(f"  - Procedures: {len(PROCEDURES)}")
        print(f"  - Observations: {len(ALLERGIES)}")
        print(f"\n✅ Knowledge graph built successfully!")
        print(f"View at: http://localhost:3000/patients/{PATIENT_ID}/graph")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error building graph: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    build_knowledge_graph()
