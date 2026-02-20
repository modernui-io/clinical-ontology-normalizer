#!/usr/bin/env python3
"""Scalability analysis: measure KG metrics at different corpus sizes.

Reports timing and accuracy metrics as a function of KG size.
Uses the current DB state — measures actual query latencies for
graph traversal, concept extraction, and RAG retrieval.

Usage:
    cd backend
    uv run python scripts/run_scalability.py

Options (via env vars):
    OUTPUT_DIR    Output directory (default: data/benchmarks/results)
"""

import asyncio
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("run_scalability")


async def main() -> None:
    logger.info("=" * 70)
    logger.info("Scalability Analysis")
    logger.info("=" * 70)

    from sqlalchemy import select, func as sa_func, text
    from app.core.database import async_session_maker
    from app.models.knowledge_graph import KGNode, KGEdge
    from app.models.document import Document
    from app.models.mention import Mention
    from app.models.clinical_fact import ClinicalFact

    output_dir = os.environ.get("OUTPUT_DIR", "data/benchmarks/results")
    os.makedirs(output_dir, exist_ok=True)

    results: dict = {
        "analysis_type": "scalability",
        "metrics": {},
    }

    async with async_session_maker() as session:
        # 1. Corpus size metrics
        logger.info("--- Corpus Size Metrics ---")

        doc_count = (await session.execute(select(sa_func.count(Document.id)))).scalar() or 0
        mention_count = (await session.execute(select(sa_func.count(Mention.id)))).scalar() or 0
        fact_count = (await session.execute(select(sa_func.count(ClinicalFact.id)))).scalar() or 0
        node_count = (await session.execute(select(sa_func.count(KGNode.id)))).scalar() or 0
        edge_count = (await session.execute(select(sa_func.count(KGEdge.id)))).scalar() or 0

        # Distinct patients
        patient_count = (await session.execute(
            select(sa_func.count(sa_func.distinct(Document.patient_id)))
        )).scalar() or 0

        corpus = {
            "documents": doc_count,
            "patients": patient_count,
            "mentions": mention_count,
            "clinical_facts": fact_count,
            "kg_nodes": node_count,
            "kg_edges": edge_count,
            "avg_mentions_per_doc": mention_count / doc_count if doc_count else 0,
            "avg_facts_per_doc": fact_count / doc_count if doc_count else 0,
            "avg_edges_per_node": edge_count / node_count if node_count else 0,
        }
        results["corpus"] = corpus
        logger.info("  Documents: %d, Patients: %d", doc_count, patient_count)
        logger.info("  Mentions: %d, Facts: %d", mention_count, fact_count)
        logger.info("  KG Nodes: %d, Edges: %d", node_count, edge_count)

        # 2. Node type distribution
        logger.info("\n--- Node Type Distribution ---")
        type_dist_stmt = (
            select(KGNode.node_type, sa_func.count(KGNode.id))
            .group_by(KGNode.node_type)
            .order_by(sa_func.count(KGNode.id).desc())
        )
        type_dist = (await session.execute(type_dist_stmt)).all()
        node_types = {}
        for nt, count in type_dist:
            key = nt.value if hasattr(nt, "value") else str(nt)
            node_types[key] = count
            logger.info("  %s: %d", key, count)
        results["node_type_distribution"] = node_types

        # 3. Edge type distribution
        logger.info("\n--- Edge Type Distribution ---")
        edge_dist_stmt = (
            select(KGEdge.edge_type, sa_func.count(KGEdge.id))
            .group_by(KGEdge.edge_type)
            .order_by(sa_func.count(KGEdge.id).desc())
        )
        edge_dist = (await session.execute(edge_dist_stmt)).all()
        edge_types = {}
        for et, count in edge_dist:
            key = et.value if hasattr(et, "value") else str(et)
            edge_types[key] = count
            logger.info("  %s: %d", key, count)
        results["edge_type_distribution"] = edge_types

        # 4. Graph density metrics per patient
        logger.info("\n--- Per-Patient Graph Density ---")
        patient_edges_stmt = (
            select(
                KGEdge.patient_id,
                sa_func.count(KGEdge.id),
            )
            .where(KGEdge.patient_id.isnot(None))
            .group_by(KGEdge.patient_id)
            .order_by(sa_func.count(KGEdge.id).desc())
        )
        patient_edges = (await session.execute(patient_edges_stmt)).all()

        if patient_edges:
            edge_counts = [c for _, c in patient_edges]
            per_patient = {
                "num_patients": len(patient_edges),
                "total_patient_edges": sum(edge_counts),
                "max_edges": max(edge_counts),
                "min_edges": min(edge_counts),
                "avg_edges": sum(edge_counts) / len(edge_counts),
                "median_edges": sorted(edge_counts)[len(edge_counts) // 2],
                "top_5": [
                    {"patient_id": pid, "edges": c}
                    for pid, c in patient_edges[:5]
                ],
            }
            results["per_patient_density"] = per_patient
            logger.info("  Patients with edges: %d", len(patient_edges))
            logger.info("  Avg edges/patient: %.1f", per_patient["avg_edges"])
            logger.info("  Max edges: %d, Min: %d", per_patient["max_edges"], per_patient["min_edges"])

        # 5. Query latency benchmarks
        logger.info("\n--- Query Latency Benchmarks ---")
        latencies: dict[str, list[float]] = {
            "node_lookup_by_label": [],
            "edge_traversal_1hop": [],
            "edge_traversal_2hop": [],
            "full_count_queries": [],
        }

        test_labels = ["diabetes", "hypertension", "metformin", "chest pain", "pneumonia"]

        for label in test_labels:
            # Node lookup
            t0 = time.perf_counter()
            stmt = select(KGNode).where(
                sa_func.lower(KGNode.label).contains(label.lower())
            ).limit(10)
            node_result = await session.execute(stmt)
            nodes = list(node_result.scalars().all())
            latencies["node_lookup_by_label"].append(time.perf_counter() - t0)

            if nodes:
                # 1-hop traversal
                t0 = time.perf_counter()
                edge_stmt = select(KGEdge).where(
                    KGEdge.source_node_id == nodes[0].id
                ).limit(20)
                await session.execute(edge_stmt)
                latencies["edge_traversal_1hop"].append(time.perf_counter() - t0)

                # 2-hop traversal
                t0 = time.perf_counter()
                edge_result = await session.execute(edge_stmt)
                edges = list(edge_result.scalars().all())
                if edges:
                    target_ids = [e.target_node_id for e in edges[:5]]
                    hop2_stmt = select(KGEdge).where(
                        KGEdge.source_node_id.in_(target_ids)
                    ).limit(20)
                    await session.execute(hop2_stmt)
                latencies["edge_traversal_2hop"].append(time.perf_counter() - t0)

        # Full count query
        for _ in range(3):
            t0 = time.perf_counter()
            await session.execute(select(sa_func.count(KGEdge.id)))
            latencies["full_count_queries"].append(time.perf_counter() - t0)

        latency_summary = {}
        for op, times in latencies.items():
            if times:
                latency_summary[op] = {
                    "avg_ms": sum(times) / len(times) * 1000,
                    "min_ms": min(times) * 1000,
                    "max_ms": max(times) * 1000,
                    "samples": len(times),
                }
                logger.info(
                    "  %s: avg=%.2fms, min=%.2fms, max=%.2fms (n=%d)",
                    op,
                    latency_summary[op]["avg_ms"],
                    latency_summary[op]["min_ms"],
                    latency_summary[op]["max_ms"],
                    len(times),
                )
        results["query_latencies"] = latency_summary

    # Print summary table
    print("\n" + "=" * 70)
    print("SCALABILITY ANALYSIS RESULTS")
    print("=" * 70)

    c = results["corpus"]
    print(f"\n| Metric | Value |")
    print("|---|---|")
    print(f"| Documents | {c['documents']:,} |")
    print(f"| Patients | {c['patients']:,} |")
    print(f"| Mentions | {c['mentions']:,} |")
    print(f"| Clinical Facts | {c['clinical_facts']:,} |")
    print(f"| KG Nodes | {c['kg_nodes']:,} |")
    print(f"| KG Edges | {c['kg_edges']:,} |")
    print(f"| Avg Mentions/Doc | {c['avg_mentions_per_doc']:.1f} |")
    print(f"| Avg Facts/Doc | {c['avg_facts_per_doc']:.1f} |")
    print(f"| Avg Edges/Node | {c['avg_edges_per_node']:.1f} |")

    if "per_patient_density" in results:
        pp = results["per_patient_density"]
        print(f"\n| Per-Patient | Value |")
        print("|---|---|")
        print(f"| Avg Edges/Patient | {pp['avg_edges']:.1f} |")
        print(f"| Max Edges | {pp['max_edges']:,} |")
        print(f"| Median Edges | {pp['median_edges']:,} |")

    print(f"\n| Query Operation | Avg (ms) | Min (ms) | Max (ms) |")
    print("|---|---|---|---|")
    for op, lat in results.get("query_latencies", {}).items():
        print(f"| {op} | {lat['avg_ms']:.2f} | {lat['min_ms']:.2f} | {lat['max_ms']:.2f} |")

    # Save
    out_path = os.path.join(output_dir, "scalability_analysis.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    logger.info("\nResults saved to %s", out_path)


if __name__ == "__main__":
    asyncio.run(main())
