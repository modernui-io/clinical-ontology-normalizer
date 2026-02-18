"""Build and sync patient graphs to Neo4j for all patients with clinical facts."""
import sys
import time
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

engine = create_engine("postgresql://postgres:postgres@postgres:5432/clinical_ontology")

with Session(engine) as session:
    # Find all patients with clinical facts
    patients = session.execute(text(
        "SELECT patient_id, count(*) as fact_count FROM clinical_facts "
        "GROUP BY patient_id ORDER BY count(*) DESC"
    )).fetchall()

    print(f"Found {len(patients)} patients with clinical facts")

    from app.services.graph_builder_db import DatabaseGraphBuilderService

    for patient_id, fact_count in patients:
        start = time.time()
        svc = DatabaseGraphBuilderService(session)
        try:
            result = svc.build_graph_for_patient(patient_id)
            session.commit()
            elapsed = time.time() - start
            print(f"  {patient_id}: {result.nodes_created} nodes, {result.edges_created} edges ({elapsed:.1f}s) [facts: {fact_count}]")
        except Exception as e:
            session.rollback()
            print(f"  {patient_id}: FAILED - {e}")

    # Summary
    node_count = session.execute(text("SELECT count(*) FROM kg_nodes WHERE deleted_at IS NULL")).scalar()
    edge_count = session.execute(text("SELECT count(*) FROM kg_edges")).scalar()
    concept_edges = session.execute(text(
        "SELECT edge_type::text, count(*) FROM kg_edges "
        "WHERE edge_type::text IN ('drug_treats','condition_treated_by','may_cause','has_finding_site','caused_by','has_morphology') "
        "GROUP BY edge_type"
    )).fetchall()
    print(f"\nTotal: {node_count} nodes, {edge_count} edges")
    print(f"Concept->concept edges: {dict({str(r[0]): r[1] for r in concept_edges})}")
