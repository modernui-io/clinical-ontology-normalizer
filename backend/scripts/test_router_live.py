"""Test PG-native multi-hop query router on live data.

Three-phase traversal: clinical (kg_edges) + vocabulary (concept_relationships)
with virtual node expansion into the full OMOP concepts table.
No Neo4j required — all 3M+ relationships queried directly in PG.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
import time

engine = create_engine("postgresql://postgres:postgres@postgres:5432/clinical_ontology")

with Session(engine) as session:
    from app.services.neo4j_query_router import GraphQueryRouter, MultiHopQuery

    router = GraphQueryRouter(session)
    pid = "TEST66066"

    # Summary stats
    rel_count = session.execute(text("SELECT count(*) FROM concept_relationships")).scalar()
    rel_types = session.execute(text(
        "SELECT count(DISTINCT relationship_id) FROM concept_relationships"
    )).scalar()
    print(f"Vocabulary: {rel_count:,} relationships across {rel_types} types\n")

    # Test 1: 2-hop from Type 2 Diabetes
    start_id = 201826
    print(f"=== 2-hop from Type 2 Diabetes (201826) for {pid} ===")
    t0 = time.time()
    query = MultiHopQuery(
        patient_id=pid,
        start_concept_ids=[start_id],
        max_hops=2,
        min_confidence=0.0,
        max_paths=500,
    )
    paths = router.execute_multi_hop(query)
    elapsed = (time.time() - t0) * 1000

    # Classify by edge source
    edge_dist: dict[str, int] = {}
    for p in paths:
        for e in p.edges:
            edge_dist[e.edge_type] = edge_dist.get(e.edge_type, 0) + 1

    print(f"Found {len(paths)} paths in {elapsed:.0f}ms")
    print("Edge type distribution:")
    for et, cnt in sorted(edge_dist.items(), key=lambda x: -x[1]):
        print(f"  {et}: {cnt}")

    # Show clinical structure paths (anatomy, morphology, causative agent, method)
    anatomy_types = {
        'has_associated_morphology', 'associated_morphology_of',
        'has_finding_site', 'finding_site_of',
        'has_causative_agent', 'causative_agent_of',
        'has_method', 'method_of', 'has_access', 'access_of',
        'has_finding_context', 'finding_context_of',
        'has_associated_finding', 'associated_finding_of',
        'has_interprets', 'interprets_of',
        'occurs_before', 'occurs_after',
        'has_severity', 'severity_of',
    }
    anat = [p for p in paths if any(e.edge_type in anatomy_types for e in p.edges)]
    print(f"\n--- Clinical structure paths (UMLS): {len(anat)} ---")
    for i, p in enumerate(anat[:10]):
        labels = " -> ".join(f"{n.label}({n.node_type})" for n in p.nodes)
        edges = ", ".join(e.edge_type for e in p.edges)
        print(f"  [{i+1}] {labels}")
        print(f"       edges: {edges} | hops: {p.hops}")

    # Show pharmacology paths
    pharma_types = {
        'has_mechanism_of_action', 'mechanism_of_action_of',
        'has_physiologic_effect', 'physiologic_effect_of',
        'has_ingredient', 'ingredient_of',
        'has_pharmacokinetics', 'pharmacokinetics_of',
        'has_metabolism', 'metabolism_of',
    }
    pharma = [p for p in paths if any(e.edge_type in pharma_types for e in p.edges)]
    print(f"\n--- Pharmacology paths: {len(pharma)} ---")
    for i, p in enumerate(pharma[:10]):
        labels = " -> ".join(f"{n.label}({n.node_type})" for n in p.nodes)
        edges = ", ".join(e.edge_type for e in p.edges)
        print(f"  [{i+1}] {labels} | {edges}")

    # Show treatment paths
    treatment_types = {'drug_treats', 'condition_treated_by', 'may_prevent', 'prevented_by'}
    treat = [p for p in paths if any(e.edge_type in treatment_types for e in p.edges)]
    print(f"\n--- Treatment paths: {len(treat)} (showing top 5) ---")
    for i, p in enumerate(treat[:5]):
        labels = " -> ".join(f"{n.label}({n.node_type})" for n in p.nodes)
        edges = ", ".join(e.edge_type for e in p.edges)
        print(f"  [{i+1}] {labels} | {edges}")

    # Test 2: 1-hop (simple JOIN, no CTE)
    print(f"\n=== 1-hop from Diabetes (simple PG JOIN) ===")
    t0 = time.time()
    query1 = MultiHopQuery(
        patient_id=pid,
        start_concept_ids=[start_id],
        max_hops=1,
        min_confidence=0.0,
    )
    paths1 = router.execute_multi_hop(query1)
    elapsed = (time.time() - t0) * 1000
    print(f"Found {len(paths1)} paths in {elapsed:.0f}ms")

    # Test 3: Cross-patient (TEST10101)
    print(f"\n=== 2-hop for TEST10101 ===")
    t0 = time.time()
    query_p2 = MultiHopQuery(
        patient_id="TEST10101",
        start_concept_ids=[201826],
        max_hops=2,
        min_confidence=0.0,
        max_paths=500,
    )
    paths_p2 = router.execute_multi_hop(query_p2)
    elapsed = (time.time() - t0) * 1000
    edge_dist_p2: dict[str, int] = {}
    for p in paths_p2:
        for e in p.edges:
            edge_dist_p2[e.edge_type] = edge_dist_p2.get(e.edge_type, 0) + 1
    print(f"Found {len(paths_p2)} paths in {elapsed:.0f}ms")
    print(f"Edge types: {dict(sorted(edge_dist_p2.items(), key=lambda x: -x[1])[:10])}")
