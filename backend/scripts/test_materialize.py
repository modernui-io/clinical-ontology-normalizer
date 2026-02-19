"""Quick test: materialize concept->concept edges for a patient."""
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

engine = create_engine("postgresql://postgres:postgres@postgres:5432/clinical_ontology")

with Session(engine) as session:
    # Count existing concept->concept edges
    existing = session.execute(text(
        "SELECT edge_type::text, count(*) FROM kg_edges "
        "WHERE edge_type::text IN ('drug_treats','condition_treated_by','may_cause','has_finding_site','caused_by','has_morphology') "
        "GROUP BY edge_type"
    )).fetchall()
    print("BEFORE:", {str(r[0]): r[1] for r in existing})

    # Load graph builder and populate node cache
    from app.services.graph_builder_db import DatabaseGraphBuilderService
    from app.services.graph_builder import NodeInput
    from app.models.knowledge_graph import KGNode

    svc = DatabaseGraphBuilderService(session)

    nodes = session.query(KGNode).filter(KGNode.deleted_at == None).all()
    for n in nodes:
        svc._uuid_to_node[n.id] = NodeInput(
            patient_id=n.patient_id,
            node_type=n.node_type,
            label=n.label,
            omop_concept_id=n.omop_concept_id,
            properties=n.properties or {},
        )
    print(f"Loaded {len(nodes)} nodes into cache")

    patient_id = sys.argv[1] if len(sys.argv) > 1 else "TEST66066"
    count = svc._materialize_concept_edges(patient_id)
    session.commit()
    print(f"MATERIALIZED: {count} new concept edges for {patient_id}")

    # Count after
    after = session.execute(text(
        "SELECT edge_type::text, count(*) FROM kg_edges "
        "WHERE edge_type::text IN ('drug_treats','condition_treated_by','may_cause','has_finding_site','caused_by','has_morphology') "
        "GROUP BY edge_type"
    )).fetchall()
    print("AFTER:", {str(r[0]): r[1] for r in after})
