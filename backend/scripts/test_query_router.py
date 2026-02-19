"""Test Neo4j query router on live data."""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

engine = create_engine("postgresql://postgres:postgres@postgres:5432/clinical_ontology")

with Session(engine) as session:
    from app.services.neo4j_query_router import Neo4jQueryRouter, MultiHopQuery

    router = Neo4jQueryRouter(session)
    print(f"Neo4j available: {router.neo4j_available}")

    # Query: find multi-hop paths from Diabetes (201826) for TEST66066
    query = MultiHopQuery(
        patient_id="TEST66066",
        start_concept_ids=[201826],  # Diabetes
        max_hops=2,
        min_confidence=0.0,
    )

    paths = router.execute_multi_hop(query)
    print(f"\nFound {len(paths)} paths from Diabetes (concept 201826) for TEST66066:")
    for i, p in enumerate(paths[:5]):
        node_labels = " -> ".join(f"{n.label}({n.node_type})" for n in p.nodes)
        edge_types = ", ".join(e.edge_type for e in p.edges)
        print(f"  [{i+1}] {node_labels}")
        print(f"       edges: {edge_types} | hops: {p.hops} | confidence: {p.path_confidence:.2f} | source: {p.source}")

    # Also try 1-hop (should always use PG)
    query1 = MultiHopQuery(
        patient_id="TEST66066",
        start_concept_ids=[201826],
        max_hops=1,
        min_confidence=0.0,
    )
    paths1 = router.execute_multi_hop(query1)
    print(f"\n1-hop paths: {len(paths1)} (always PG)")
    for i, p in enumerate(paths1[:3]):
        node_labels = " -> ".join(f"{n.label}({n.node_type})" for n in p.nodes)
        print(f"  [{i+1}] {node_labels} | {p.source}")
