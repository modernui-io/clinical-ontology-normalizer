"""Experiment runner for NeurIPS 2026 paper.

Creates and executes the 6 paper experiments using existing ResearchService
infrastructure. Supports running on already-imported datasets (MTSamples,
Synthea) without requiring CSV re-ingestion.

Experiments:
1. End-to-End Pipeline Evaluation
2. Assertion Preservation Ablation
3. Temporal Reasoning Ablation
4. Graph-RAG vs Document-RAG
5. Benchmark Comparison (MedAgentBench + DR.KNOWS)
6. Scalability Analysis
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_sync_engine
from app.models.clinical_fact import ClinicalFact
from app.models.document import Document
from app.models.knowledge_graph import KGEdge, KGNode
from app.models.mention import Mention, MentionConceptCandidate
from app.models.research_experiment import (
    ExperimentRunStatus,
    MetricCategory,
    ResearchExperimentRun,
)
from app.schemas.research import ExperimentConfig, ExperimentCreate
from app.services.research_service import get_research_service

logger = logging.getLogger(__name__)


# ============================================================================
# Dataset helpers
# ============================================================================


@dataclass
class DatasetSlice:
    """A slice of documents from a dataset for experiment runs."""

    source: str
    document_ids: list[str] = field(default_factory=list)
    patient_ids: list[str] = field(default_factory=list)
    doc_count: int = 0


def get_dataset_documents(source: str, limit: int | None = None) -> DatasetSlice:
    """Query existing documents by source (mtsamples, synthea, mimic)."""
    with Session(get_sync_engine()) as session:
        query = select(Document).where(
            Document.extra_metadata["source"].astext == source,
            Document.deleted_at.is_(None),
        )
        if limit:
            query = query.limit(limit)

        docs = session.scalars(query).all()
        doc_ids = [d.id for d in docs]
        patient_ids = list({d.patient_id for d in docs if d.patient_id})

        return DatasetSlice(
            source=source,
            document_ids=doc_ids,
            patient_ids=patient_ids,
            doc_count=len(doc_ids),
        )


def get_all_datasets() -> dict[str, DatasetSlice]:
    """Get document counts for all available datasets."""
    datasets = {}
    for source in ("mtsamples", "synthea", "mimic"):
        ds = get_dataset_documents(source)
        if ds.doc_count > 0:
            datasets[source] = ds
    return datasets


# ============================================================================
# Extended metric collectors
# ============================================================================


def collect_assertion_metrics(
    session: Session, document_ids: list[str], run_id: str
) -> dict[str, float]:
    """Collect detailed assertion metrics for a set of documents."""
    service = get_research_service()
    mentions = session.scalars(
        select(Mention).where(Mention.document_id.in_(document_ids))
    ).all()

    total = len(mentions)
    if total == 0:
        return {}

    # Assertion distribution
    assertion_counts: dict[str, int] = {}
    temporality_counts: dict[str, int] = {}
    experiencer_counts: dict[str, int] = {}

    for m in mentions:
        assertion = getattr(m, "assertion", None) or "present"
        a_str = assertion.value if hasattr(assertion, "value") else str(assertion)
        assertion_counts[a_str] = assertion_counts.get(a_str, 0) + 1

        temporality = getattr(m, "temporality", None)
        if temporality:
            t_str = temporality.value if hasattr(temporality, "value") else str(temporality)
            temporality_counts[t_str] = temporality_counts.get(t_str, 0) + 1

        experiencer = getattr(m, "experiencer", None)
        if experiencer:
            e_str = experiencer.value if hasattr(experiencer, "value") else str(experiencer)
            experiencer_counts[e_str] = experiencer_counts.get(e_str, 0) + 1

    metrics = {"total_mentions": float(total)}

    # Record per-assertion counts
    for assertion_type, count in assertion_counts.items():
        key = f"assertion_{assertion_type}"
        metrics[key] = float(count)
        service.record_metric(run_id, "assertion", key, float(count))

    # Assertion diversity (non-present ratio)
    non_present = total - assertion_counts.get("present", 0)
    metrics["non_present_ratio"] = non_present / total if total > 0 else 0.0

    # Record aggregate assertion metrics
    service.record_metric(run_id, "assertion", "total_mentions", float(total))
    service.record_metric(
        run_id, "assertion", "non_present_ratio", metrics["non_present_ratio"],
        detail={"assertion_counts": assertion_counts},
    )
    service.record_metric(
        run_id, "assertion", "temporality_distribution", float(len(temporality_counts)),
        detail={"temporality_counts": temporality_counts},
    )
    service.record_metric(
        run_id, "assertion", "experiencer_distribution", float(len(experiencer_counts)),
        detail={"experiencer_counts": experiencer_counts},
    )

    return metrics


def collect_mapping_metrics(
    session: Session, document_ids: list[str], run_id: str
) -> dict[str, float]:
    """Collect OMOP mapping quality metrics."""
    service = get_research_service()

    mentions = session.scalars(
        select(Mention).where(Mention.document_id.in_(document_ids))
    ).all()

    mention_ids = [m.id for m in mentions]
    total = len(mentions)
    if total == 0:
        return {}

    candidates = session.scalars(
        select(MentionConceptCandidate).where(
            MentionConceptCandidate.mention_id.in_(mention_ids)
        )
    ).all()

    mapped_ids = {c.mention_id for c in candidates}
    mapped = len(mapped_ids)
    coverage = mapped / total if total > 0 else 0.0

    confidences = [c.confidence for c in candidates if c.confidence is not None]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

    # Top-1 accuracy: how many mentions have a high-confidence top candidate
    top1_correct = sum(1 for c in candidates if c.confidence and c.confidence >= 0.8)
    top1_accuracy = top1_correct / mapped if mapped > 0 else 0.0

    # Domain coverage
    domain_stats: dict[str, dict[str, int]] = {}
    for m in mentions:
        domain = getattr(m, "domain", "unknown") or "unknown"
        if domain not in domain_stats:
            domain_stats[domain] = {"total": 0, "mapped": 0}
        domain_stats[domain]["total"] += 1
        if m.id in mapped_ids:
            domain_stats[domain]["mapped"] += 1

    metrics = {
        "total_mentions": float(total),
        "mapped_count": float(mapped),
        "coverage_percent": coverage * 100,
        "avg_confidence": avg_conf,
        "top1_accuracy": top1_accuracy,
    }

    service.record_metric(run_id, "mapping", "coverage_percent", coverage * 100)
    service.record_metric(run_id, "mapping", "avg_confidence", avg_conf)
    service.record_metric(run_id, "mapping", "top1_accuracy", top1_accuracy)
    service.record_metric(run_id, "mapping", "mapped_count", float(mapped))
    service.record_metric(run_id, "mapping", "unmapped_count", float(total - mapped))
    service.record_metric(
        run_id, "mapping", "domain_coverage", float(len(domain_stats)),
        detail={d: s["mapped"] / s["total"] if s["total"] > 0 else 0.0 for d, s in domain_stats.items()},
    )

    return metrics


def collect_kg_metrics(
    session: Session, patient_ids: list[str], run_id: str
) -> dict[str, float]:
    """Collect knowledge graph structural metrics."""
    service = get_research_service()

    if not patient_ids:
        return {}

    # Node metrics
    total_nodes = session.scalar(
        select(func.count(KGNode.id)).where(
            KGNode.patient_id.in_(patient_ids),
            KGNode.deleted_at.is_(None),
        )
    ) or 0

    # Shared concept nodes (patient_id IS NULL connected to these patients)
    shared_nodes = session.scalar(
        select(func.count(func.distinct(KGEdge.target_node_id))).where(
            KGEdge.patient_id.in_(patient_ids),
            KGEdge.deleted_at.is_(None),
        )
    ) or 0

    total_edges = session.scalar(
        select(func.count(KGEdge.id)).where(
            KGEdge.patient_id.in_(patient_ids),
            KGEdge.deleted_at.is_(None),
        )
    ) or 0

    unique_concepts = session.scalar(
        select(func.count(func.distinct(KGNode.omop_concept_id))).where(
            KGNode.patient_id.in_(patient_ids),
            KGNode.deleted_at.is_(None),
            KGNode.omop_concept_id.isnot(None),
        )
    ) or 0

    # Shared concept dedup ratio
    total_concept_refs = session.scalar(
        select(func.count(KGEdge.target_node_id)).where(
            KGEdge.patient_id.in_(patient_ids),
            KGEdge.deleted_at.is_(None),
        )
    ) or 0

    global_shared = session.scalar(
        select(func.count(KGNode.id)).where(
            KGNode.patient_id.is_(None),
            KGNode.omop_concept_id.isnot(None),
            KGNode.deleted_at.is_(None),
        )
    ) or 0

    dedup_ratio = global_shared / total_concept_refs if total_concept_refs > 0 else 0.0

    # Edge type distribution
    edge_type_counts = session.execute(
        select(KGEdge.edge_type, func.count(KGEdge.id))
        .where(
            KGEdge.patient_id.in_(patient_ids),
            KGEdge.deleted_at.is_(None),
        )
        .group_by(KGEdge.edge_type)
    ).all()

    edge_type_dist = {str(et): ct for et, ct in edge_type_counts}

    # Temporal coverage: edges with temporal info
    temporal_edges = session.scalar(
        select(func.count(KGEdge.id)).where(
            KGEdge.patient_id.in_(patient_ids),
            KGEdge.deleted_at.is_(None),
            KGEdge.event_date.isnot(None) | KGEdge.valid_from.isnot(None),
        )
    ) or 0

    temporal_coverage = temporal_edges / total_edges if total_edges > 0 else 0.0

    patient_count = len(patient_ids)
    avg_nodes = total_nodes / patient_count if patient_count > 0 else 0.0
    avg_edges = total_edges / patient_count if patient_count > 0 else 0.0

    # Graph density = edges / (nodes * (nodes - 1)) for directed graph
    density = total_edges / (total_nodes * max(total_nodes - 1, 1)) if total_nodes > 1 else 0.0

    metrics = {
        "total_nodes": float(total_nodes),
        "total_edges": float(total_edges),
        "unique_concepts": float(unique_concepts),
        "shared_concept_nodes": float(global_shared),
        "dedup_ratio": dedup_ratio,
        "avg_nodes_per_patient": avg_nodes,
        "avg_edges_per_patient": avg_edges,
        "graph_density": density,
        "temporal_coverage": temporal_coverage,
    }

    for key, val in metrics.items():
        service.record_metric(
            run_id, "kg", key, val,
            detail={"edge_type_distribution": edge_type_dist} if key == "total_edges" else None,
        )

    return metrics


def collect_nlp_metrics(
    session: Session, document_ids: list[str], run_id: str
) -> dict[str, float]:
    """Collect NLP extraction quality metrics."""
    service = get_research_service()

    mentions = session.scalars(
        select(Mention).where(Mention.document_id.in_(document_ids))
    ).all()

    total = len(mentions)
    if total == 0:
        return {}

    # Confidence distribution
    confidences = [m.confidence for m in mentions if hasattr(m, "confidence") and m.confidence is not None]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    # Mentions per document
    doc_mention_counts: dict[str, int] = {}
    for m in mentions:
        doc_mention_counts[m.document_id] = doc_mention_counts.get(m.document_id, 0) + 1

    avg_mentions_per_doc = total / len(document_ids) if document_ids else 0.0

    # Domain distribution
    domain_counts: dict[str, int] = {}
    for m in mentions:
        domain = getattr(m, "domain", "unknown") or "unknown"
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

    # Unique entity text count (type diversity)
    unique_texts = len({m.text for m in mentions if hasattr(m, "text") and m.text})

    metrics = {
        "total_mentions": float(total),
        "avg_confidence": avg_confidence,
        "avg_mentions_per_doc": avg_mentions_per_doc,
        "unique_entity_texts": float(unique_texts),
        "entity_diversity": unique_texts / total if total > 0 else 0.0,
    }

    for key, val in metrics.items():
        service.record_metric(
            run_id, "nlp", key, val,
            detail={"domain_counts": domain_counts} if key == "total_mentions" else None,
        )

    return metrics


def collect_timing_metrics(
    session: Session, document_ids: list[str], run_id: str
) -> dict[str, float]:
    """Collect pipeline timing from document processing metadata."""
    service = get_research_service()

    docs = session.scalars(
        select(Document).where(Document.id.in_(document_ids))
    ).all()

    timings: list[float] = []
    for doc in docs:
        meta = doc.extra_metadata or {}
        if "processing_time_ms" in meta:
            timings.append(float(meta["processing_time_ms"]))

    if not timings:
        # Estimate from document count and mention count
        mention_count = session.scalar(
            select(func.count(Mention.id)).where(Mention.document_id.in_(document_ids))
        ) or 0

        metrics = {
            "documents_timed": 0.0,
            "documents_total": float(len(document_ids)),
            "mentions_total": float(mention_count),
        }
        for key, val in metrics.items():
            service.record_metric(run_id, "timing", key, val)
        return metrics

    import statistics as stats

    avg_ms = stats.mean(timings)
    p50_ms = stats.median(timings)
    p95_ms = sorted(timings)[int(len(timings) * 0.95)] if len(timings) >= 20 else max(timings)

    metrics = {
        "avg_total_ms": avg_ms,
        "p50_total_ms": p50_ms,
        "p95_total_ms": p95_ms,
        "documents_timed": float(len(timings)),
        "seconds_per_doc": avg_ms / 1000.0,
    }

    for key, val in metrics.items():
        service.record_metric(run_id, "timing", key, val)

    return metrics


# ============================================================================
# Experiment Definitions
# ============================================================================


EXPERIMENT_DEFINITIONS = {
    "exp1_pipeline_eval": {
        "name": "Exp 1: End-to-End Pipeline Evaluation",
        "description": (
            "Evaluate the full EpiKG pipeline across MIMIC-IV-Note, MTSamples, "
            "and Synthea datasets. Measures entity extraction quality, concept "
            "coverage, assertion accuracy, KG density, and throughput."
        ),
        "hypothesis": (
            "The EpiKG pipeline achieves competitive entity extraction F1, "
            "high concept coverage, and high assertion accuracy across diverse "
            "clinical note sources while maintaining practical throughput."
        ),
        "config": {
            "assertion_aware": True,
            "graph_rag": True,
            "nlp_method": "ensemble",
            "kg_construction": True,
        },
        "tags": ["pipeline", "e2e", "neurips2026"],
        "datasets": ["mtsamples", "synthea"],
        "metric_categories": ["nlp", "mapping", "assertion", "kg", "timing"],
    },
    "exp2_assertion_ablation": {
        "name": "Exp 2: Assertion Preservation Ablation",
        "description": (
            "Ablation study comparing QA accuracy across three assertion conditions: "
            "no_assertion (all PRESENT), assertion_extracted_only, and full_epistemic. "
            "Tests whether end-to-end assertion preservation improves downstream reasoning."
        ),
        "hypothesis": (
            "Full epistemic condition significantly outperforms no_assertion, with "
            "largest gains on negation-sensitive and uncertainty-sensitive questions."
        ),
        "config": {
            "assertion_aware": True,
            "graph_rag": True,
            "nlp_method": "ensemble",
            "kg_construction": True,
        },
        "tags": ["ablation", "assertion", "key_result", "neurips2026"],
        "conditions": ["no_assertion", "assertion_extracted_only", "full_epistemic"],
        "datasets": ["mtsamples", "synthea"],
        "metric_categories": ["assertion", "rag"],
    },
    "exp3_temporal_ablation": {
        "name": "Exp 3: Temporal Reasoning Ablation",
        "description": (
            "Ablation study comparing temporal QA accuracy across three conditions: "
            "no_temporal, timestamps_only, and full_bitemporal with Allen's algebra."
        ),
        "hypothesis": (
            "Bi-temporal modeling with Allen's interval algebra improves temporal "
            "clinical QA accuracy over timestamp-only and no-temporal baselines."
        ),
        "config": {
            "assertion_aware": True,
            "graph_rag": True,
            "nlp_method": "ensemble",
            "kg_construction": True,
        },
        "tags": ["ablation", "temporal", "neurips2026"],
        "conditions": ["no_temporal", "timestamps_only", "full_bitemporal"],
        "datasets": ["mtsamples", "synthea"],
        "metric_categories": ["kg", "rag", "timing"],
    },
    "exp4_graphrag_comparison": {
        "name": "Exp 4: Graph-RAG vs Document-RAG",
        "description": (
            "Compare graph-augmented retrieval against document-only retrieval. "
            "Four conditions: doc_only, graph_only, graph+doc, graph+doc+guidelines."
        ),
        "hypothesis": (
            "Graph-augmented retrieval outperforms document-only retrieval for "
            "clinical reasoning, with largest gains on multi-hop and cross-concept queries."
        ),
        "config": {
            "assertion_aware": True,
            "graph_rag": True,
            "nlp_method": "ensemble",
            "kg_construction": True,
        },
        "tags": ["comparison", "graphrag", "neurips2026"],
        "conditions": ["doc_only", "graph_only", "graph_plus_doc", "graph_plus_doc_plus_guidelines"],
        "datasets": ["mtsamples", "synthea"],
        "metric_categories": ["rag"],
    },
    "exp5_benchmark": {
        "name": "Exp 5: Benchmark Comparison",
        "description": (
            "Evaluate EpiKG against MedAgentBench and DR.KNOWS benchmarks. "
            "Compare with published baselines from Claude 3.5, GPT-4o, etc."
        ),
        "hypothesis": (
            "EpiKG with assertion-aware GraphRAG achieves competitive or superior "
            "performance on clinical reasoning benchmarks."
        ),
        "config": {
            "assertion_aware": True,
            "graph_rag": True,
            "nlp_method": "ensemble",
            "kg_construction": True,
        },
        "tags": ["benchmark", "medagentbench", "drknows", "neurips2026"],
        "datasets": ["mtsamples"],
        "metric_categories": ["rag"],
    },
    "exp6_scalability": {
        "name": "Exp 6: Scalability Analysis",
        "description": (
            "Measure pipeline throughput, KG growth, and query latency at "
            "increasing scale points: 100, 1K, 10K, 100K notes."
        ),
        "hypothesis": (
            "The pipeline scales sub-linearly in throughput and the shared concept "
            "architecture provides increasing deduplication benefits at larger scale."
        ),
        "config": {
            "assertion_aware": True,
            "graph_rag": True,
            "nlp_method": "ensemble",
            "kg_construction": True,
        },
        "tags": ["scalability", "performance", "neurips2026"],
        "datasets": ["mtsamples", "synthea"],
        "metric_categories": ["kg", "timing"],
    },
}


# ============================================================================
# Experiment Runner
# ============================================================================


class ExperimentRunner:
    """Creates and executes NeurIPS 2026 paper experiments."""

    def __init__(self) -> None:
        self.service = get_research_service()

    def create_all_experiments(self) -> dict[str, str]:
        """Create all 6 experiment definitions. Returns {key: experiment_id}."""
        experiment_ids = {}

        for key, defn in EXPERIMENT_DEFINITIONS.items():
            config = ExperimentConfig(**defn["config"])
            exp = self.service.create_experiment(
                ExperimentCreate(
                    name=defn["name"],
                    description=defn["description"],
                    hypothesis=defn["hypothesis"],
                    config=config,
                    tags=defn["tags"],
                ),
                created_by="neurips2026_runner",
            )
            experiment_ids[key] = exp.id
            logger.info(f"Created experiment: {defn['name']} -> {exp.id}")

        return experiment_ids

    def run_pipeline_evaluation(self, experiment_id: str) -> list[str]:
        """Experiment 1: Run pipeline evaluation on all available datasets."""
        run_ids = []
        datasets = get_all_datasets()

        for source, ds in datasets.items():
            if ds.doc_count == 0:
                logger.warning(f"Skipping {source}: no documents found")
                continue

            run = self.service.create_run(
                experiment_id=experiment_id,
                run_config={"dataset": source, "doc_count": ds.doc_count},
            )
            if not run:
                continue

            run_id = run.id
            run_ids.append(run_id)

            self.service.update_run_status(
                run_id,
                ExperimentRunStatus.PROCESSING,
                document_ids=ds.document_ids,
                patient_ids=ds.patient_ids,
            )

            logger.info(f"Exp 1 [{source}]: Processing {ds.doc_count} docs, {len(ds.patient_ids)} patients")

            try:
                with Session(get_sync_engine()) as session:
                    t0 = time.perf_counter()

                    collect_nlp_metrics(session, ds.document_ids, run_id)
                    collect_mapping_metrics(session, ds.document_ids, run_id)
                    collect_assertion_metrics(session, ds.document_ids, run_id)
                    collect_kg_metrics(session, ds.patient_ids, run_id)
                    collect_timing_metrics(session, ds.document_ids, run_id)

                    elapsed = time.perf_counter() - t0
                    self.service.record_metric(
                        run_id, "timing", "metric_collection_seconds", elapsed,
                    )

                self.service.update_run_status(run_id, ExperimentRunStatus.COMPLETED)
                logger.info(f"Exp 1 [{source}]: Completed in {elapsed:.1f}s")

            except Exception as e:
                logger.exception(f"Exp 1 [{source}] failed: {e}")
                self.service.update_run_status(
                    run_id, ExperimentRunStatus.FAILED, error=str(e)[:500]
                )

        return run_ids

    # Map ablation conditions to GraphRAG mode parameters
    ASSERTION_CONDITION_TO_MODE = {
        "no_assertion": "none",
        "assertion_extracted_only": "extracted_only",
        "full_epistemic": "full",
    }

    TEMPORAL_CONDITION_TO_MODE = {
        "no_temporal": "no_temporal",
        "timestamps_only": "timestamps_only",
        "full_bitemporal": "full_bitemporal",
    }

    RETRIEVAL_CONDITION_TO_MODE = {
        "doc_only": "doc_only",
        "graph_only": "graph_only",
        "graph_plus_doc": "graph_plus_doc",
        "graph_plus_doc_plus_guidelines": "graph_plus_doc_plus_guidelines",
    }

    def run_assertion_ablation(self, experiment_id: str) -> list[str]:
        """Experiment 2: Assertion preservation ablation study.

        Creates 3 runs per dataset (one per condition) and collects
        assertion-specific metrics. Each condition configures GraphRAG
        with a different assertion_mode:
        - no_assertion: assertion_mode="none" (all treated as PRESENT)
        - assertion_extracted_only: assertion_mode="extracted_only" (in prompt, not scoring)
        - full_epistemic: assertion_mode="full" (scoring + prompt)

        QA evaluation is handled separately by the QAEvaluationService,
        which receives the assertion_mode to configure the RAG pipeline.
        """
        run_ids = []
        conditions = ["no_assertion", "assertion_extracted_only", "full_epistemic"]
        datasets = get_all_datasets()

        for source, ds in datasets.items():
            if ds.doc_count == 0:
                continue

            for condition in conditions:
                assertion_mode = self.ASSERTION_CONDITION_TO_MODE[condition]

                run = self.service.create_run(
                    experiment_id=experiment_id,
                    run_config={
                        "dataset": source,
                        "condition": condition,
                        "assertion_mode": assertion_mode,
                        "doc_count": ds.doc_count,
                    },
                )
                if not run:
                    continue

                run_id = run.id
                run_ids.append(run_id)

                self.service.update_run_status(
                    run_id,
                    ExperimentRunStatus.PROCESSING,
                    document_ids=ds.document_ids,
                    patient_ids=ds.patient_ids,
                )

                logger.info(f"Exp 2 [{source}/{condition}]: Processing {ds.doc_count} docs (assertion_mode={assertion_mode})")

                try:
                    with Session(get_sync_engine()) as session:
                        # Collect assertion metrics for this condition
                        collect_assertion_metrics(session, ds.document_ids, run_id)

                        # Record condition-specific metrics with mode parameter
                        self.service.record_metric(
                            run_id, "assertion", "condition_type",
                            float(conditions.index(condition)),
                            detail={
                                "condition": condition,
                                "assertion_mode": assertion_mode,
                                "description": {
                                    "no_assertion": "All assertions ignored; scoring and prompt treat everything as PRESENT",
                                    "assertion_extracted_only": "Assertion in prompt text but no score modification",
                                    "full_epistemic": "Full 7-value assertion through KG scoring and prompt",
                                }[condition],
                            },
                        )

                        # Collect KG metrics to show assertion impact on graph structure
                        collect_kg_metrics(session, ds.patient_ids, run_id)

                    self.service.update_run_status(run_id, ExperimentRunStatus.COMPLETED)
                    logger.info(f"Exp 2 [{source}/{condition}]: Completed")

                except Exception as e:
                    logger.exception(f"Exp 2 [{source}/{condition}] failed: {e}")
                    self.service.update_run_status(
                        run_id, ExperimentRunStatus.FAILED, error=str(e)[:500]
                    )

        return run_ids

    def run_temporal_ablation(self, experiment_id: str) -> list[str]:
        """Experiment 3: Temporal reasoning ablation study.

        Each condition configures GraphRAG with a different temporal_mode:
        - no_temporal: temporal_mode="no_temporal" (no temporal scoring or context)
        - timestamps_only: temporal_mode="timestamps_only" (event_date but no temporality enum)
        - full_bitemporal: temporal_mode="full_bitemporal" (full Allen's algebra)
        """
        run_ids = []
        conditions = ["no_temporal", "timestamps_only", "full_bitemporal"]
        datasets = get_all_datasets()

        for source, ds in datasets.items():
            if ds.doc_count == 0:
                continue

            for condition in conditions:
                temporal_mode = self.TEMPORAL_CONDITION_TO_MODE[condition]

                run = self.service.create_run(
                    experiment_id=experiment_id,
                    run_config={
                        "dataset": source,
                        "condition": condition,
                        "temporal_mode": temporal_mode,
                        "doc_count": ds.doc_count,
                    },
                )
                if not run:
                    continue

                run_id = run.id
                run_ids.append(run_id)

                self.service.update_run_status(
                    run_id,
                    ExperimentRunStatus.PROCESSING,
                    document_ids=ds.document_ids,
                    patient_ids=ds.patient_ids,
                )

                logger.info(f"Exp 3 [{source}/{condition}]: Processing (temporal_mode={temporal_mode})")

                try:
                    with Session(get_sync_engine()) as session:
                        # KG metrics include temporal coverage
                        collect_kg_metrics(session, ds.patient_ids, run_id)

                        # Temporal-specific metrics
                        total_edges = session.scalar(
                            select(func.count(KGEdge.id)).where(
                                KGEdge.patient_id.in_(ds.patient_ids),
                                KGEdge.deleted_at.is_(None),
                            )
                        ) or 0

                        edges_with_event_date = session.scalar(
                            select(func.count(KGEdge.id)).where(
                                KGEdge.patient_id.in_(ds.patient_ids),
                                KGEdge.deleted_at.is_(None),
                                KGEdge.event_date.isnot(None),
                            )
                        ) or 0

                        edges_with_valid_range = session.scalar(
                            select(func.count(KGEdge.id)).where(
                                KGEdge.patient_id.in_(ds.patient_ids),
                                KGEdge.deleted_at.is_(None),
                                KGEdge.valid_from.isnot(None),
                            )
                        ) or 0

                        edges_with_temporality = session.scalar(
                            select(func.count(KGEdge.id)).where(
                                KGEdge.patient_id.in_(ds.patient_ids),
                                KGEdge.deleted_at.is_(None),
                                KGEdge.temporality.isnot(None),
                            )
                        ) or 0

                        edges_with_temporal_order = session.scalar(
                            select(func.count(KGEdge.id)).where(
                                KGEdge.patient_id.in_(ds.patient_ids),
                                KGEdge.deleted_at.is_(None),
                                KGEdge.temporal_order.isnot(None),
                            )
                        ) or 0

                        # Record temporal metrics
                        self.service.record_metric(run_id, "kg", "edges_with_event_date", float(edges_with_event_date))
                        self.service.record_metric(run_id, "kg", "edges_with_valid_range", float(edges_with_valid_range))
                        self.service.record_metric(run_id, "kg", "edges_with_temporality", float(edges_with_temporality))
                        self.service.record_metric(run_id, "kg", "edges_with_temporal_order", float(edges_with_temporal_order))
                        self.service.record_metric(
                            run_id, "kg", "temporal_completeness",
                            edges_with_event_date / total_edges if total_edges > 0 else 0.0,
                        )

                        # Condition-specific recording with mode parameter
                        self.service.record_metric(
                            run_id, "kg", "condition_type",
                            float(conditions.index(condition)),
                            detail={"condition": condition, "temporal_mode": temporal_mode},
                        )

                    self.service.update_run_status(run_id, ExperimentRunStatus.COMPLETED)
                    logger.info(f"Exp 3 [{source}/{condition}]: Completed")

                except Exception as e:
                    logger.exception(f"Exp 3 [{source}/{condition}] failed: {e}")
                    self.service.update_run_status(
                        run_id, ExperimentRunStatus.FAILED, error=str(e)[:500]
                    )

        return run_ids

    def run_graphrag_comparison(self, experiment_id: str) -> list[str]:
        """Experiment 4: Graph-RAG vs Document-RAG comparison.

        Each condition configures GraphRAG with a different retrieval_mode:
        - doc_only: retrieval_mode="doc_only" (no graph traversal)
        - graph_only: retrieval_mode="graph_only" (no document retrieval)
        - graph_plus_doc: retrieval_mode="graph_plus_doc" (both)
        - graph_plus_doc_plus_guidelines: retrieval_mode="graph_plus_doc_plus_guidelines" (full)

        Actual QA evaluation is handled by QAEvaluationService; this collects
        structural metrics.
        """
        run_ids = []
        conditions = ["doc_only", "graph_only", "graph_plus_doc", "graph_plus_doc_plus_guidelines"]
        datasets = get_all_datasets()

        for source, ds in datasets.items():
            if ds.doc_count == 0:
                continue

            for condition in conditions:
                retrieval_mode = self.RETRIEVAL_CONDITION_TO_MODE[condition]

                run = self.service.create_run(
                    experiment_id=experiment_id,
                    run_config={
                        "dataset": source,
                        "condition": condition,
                        "retrieval_mode": retrieval_mode,
                        "doc_count": ds.doc_count,
                    },
                )
                if not run:
                    continue

                run_id = run.id
                run_ids.append(run_id)

                self.service.update_run_status(
                    run_id,
                    ExperimentRunStatus.PROCESSING,
                    document_ids=ds.document_ids,
                    patient_ids=ds.patient_ids,
                )

                logger.info(f"Exp 4 [{source}/{condition}]: Processing (retrieval_mode={retrieval_mode})")

                try:
                    with Session(get_sync_engine()) as session:
                        # Base metrics for all conditions
                        collect_kg_metrics(session, ds.patient_ids, run_id)

                        # Record condition with mode parameter
                        self.service.record_metric(
                            run_id, "rag", "condition_type",
                            float(conditions.index(condition)),
                            detail={"condition": condition, "retrieval_mode": retrieval_mode},
                        )

                        # Condition-specific context size metrics
                        if condition in ("graph_only", "graph_plus_doc", "graph_plus_doc_plus_guidelines"):
                            # Count available graph paths
                            edge_count = session.scalar(
                                select(func.count(KGEdge.id)).where(
                                    KGEdge.patient_id.in_(ds.patient_ids),
                                    KGEdge.deleted_at.is_(None),
                                )
                            ) or 0
                            self.service.record_metric(
                                run_id, "rag", "available_graph_edges", float(edge_count),
                            )

                    self.service.update_run_status(run_id, ExperimentRunStatus.COMPLETED)
                    logger.info(f"Exp 4 [{source}/{condition}]: Completed")

                except Exception as e:
                    logger.exception(f"Exp 4 [{source}/{condition}] failed: {e}")
                    self.service.update_run_status(
                        run_id, ExperimentRunStatus.FAILED, error=str(e)[:500]
                    )

        return run_ids

    def run_scalability_analysis(self, experiment_id: str) -> list[str]:
        """Experiment 6: Scalability analysis at different scale points."""
        run_ids = []
        datasets = get_all_datasets()

        # Test at available scale points
        all_doc_ids: list[str] = []
        all_patient_ids: list[str] = []
        for ds in datasets.values():
            all_doc_ids.extend(ds.document_ids)
            all_patient_ids.extend(ds.patient_ids)

        all_patient_ids = list(set(all_patient_ids))
        total_docs = len(all_doc_ids)

        # Scale points based on available data
        scale_points = [min(total_docs, n) for n in [10, 50, 100, total_docs] if n <= total_docs]
        scale_points = sorted(set(scale_points))

        for scale in scale_points:
            doc_slice = all_doc_ids[:scale]
            patient_slice = list({
                pid for did in doc_slice
                for ds in datasets.values()
                if did in ds.document_ids
                for pid in ds.patient_ids
            })

            # Simpler patient slice: get patient IDs for these docs
            with Session(get_sync_engine()) as session:
                patient_slice = list(session.scalars(
                    select(func.distinct(Document.patient_id)).where(
                        Document.id.in_(doc_slice)
                    )
                ).all())

            run = self.service.create_run(
                experiment_id=experiment_id,
                run_config={
                    "scale_point": scale,
                    "total_available": total_docs,
                },
            )
            if not run:
                continue

            run_id = run.id
            run_ids.append(run_id)

            self.service.update_run_status(
                run_id,
                ExperimentRunStatus.PROCESSING,
                document_ids=doc_slice,
                patient_ids=patient_slice,
            )

            logger.info(f"Exp 6 [scale={scale}]: Processing {scale} docs, {len(patient_slice)} patients")

            try:
                with Session(get_sync_engine()) as session:
                    t0 = time.perf_counter()
                    collect_kg_metrics(session, patient_slice, run_id)
                    collect_timing_metrics(session, doc_slice, run_id)
                    elapsed = time.perf_counter() - t0

                    self.service.record_metric(run_id, "timing", "metric_collection_seconds", elapsed)
                    self.service.record_metric(run_id, "timing", "scale_point", float(scale))

                self.service.update_run_status(run_id, ExperimentRunStatus.COMPLETED)
                logger.info(f"Exp 6 [scale={scale}]: Completed in {elapsed:.1f}s")

            except Exception as e:
                logger.exception(f"Exp 6 [scale={scale}] failed: {e}")
                self.service.update_run_status(
                    run_id, ExperimentRunStatus.FAILED, error=str(e)[:500]
                )

        return run_ids

    def run_all(self) -> dict[str, dict]:
        """Run all experiments and return results summary."""
        logger.info("Creating all 6 paper experiments...")
        experiment_ids = self.create_all_experiments()

        results = {}

        # Experiment 1: Pipeline Evaluation
        logger.info("=" * 60)
        logger.info("Running Experiment 1: End-to-End Pipeline Evaluation")
        logger.info("=" * 60)
        exp1_runs = self.run_pipeline_evaluation(experiment_ids["exp1_pipeline_eval"])
        self.service.start_experiment(experiment_ids["exp1_pipeline_eval"])
        if exp1_runs:
            self.service.complete_experiment(experiment_ids["exp1_pipeline_eval"])
        results["exp1"] = {"experiment_id": experiment_ids["exp1_pipeline_eval"], "run_ids": exp1_runs}

        # Experiment 2: Assertion Ablation
        logger.info("=" * 60)
        logger.info("Running Experiment 2: Assertion Preservation Ablation")
        logger.info("=" * 60)
        exp2_runs = self.run_assertion_ablation(experiment_ids["exp2_assertion_ablation"])
        self.service.start_experiment(experiment_ids["exp2_assertion_ablation"])
        if exp2_runs:
            self.service.complete_experiment(experiment_ids["exp2_assertion_ablation"])
        results["exp2"] = {"experiment_id": experiment_ids["exp2_assertion_ablation"], "run_ids": exp2_runs}

        # Experiment 3: Temporal Ablation
        logger.info("=" * 60)
        logger.info("Running Experiment 3: Temporal Reasoning Ablation")
        logger.info("=" * 60)
        exp3_runs = self.run_temporal_ablation(experiment_ids["exp3_temporal_ablation"])
        self.service.start_experiment(experiment_ids["exp3_temporal_ablation"])
        if exp3_runs:
            self.service.complete_experiment(experiment_ids["exp3_temporal_ablation"])
        results["exp3"] = {"experiment_id": experiment_ids["exp3_temporal_ablation"], "run_ids": exp3_runs}

        # Experiment 4: Graph-RAG Comparison
        logger.info("=" * 60)
        logger.info("Running Experiment 4: Graph-RAG vs Document-RAG")
        logger.info("=" * 60)
        exp4_runs = self.run_graphrag_comparison(experiment_ids["exp4_graphrag_comparison"])
        self.service.start_experiment(experiment_ids["exp4_graphrag_comparison"])
        if exp4_runs:
            self.service.complete_experiment(experiment_ids["exp4_graphrag_comparison"])
        results["exp4"] = {"experiment_id": experiment_ids["exp4_graphrag_comparison"], "run_ids": exp4_runs}

        # Experiment 5: Benchmarks (placeholder — requires LLM calls)
        logger.info("=" * 60)
        logger.info("Experiment 5: Benchmark Comparison (creating experiment definition)")
        logger.info("=" * 60)
        results["exp5"] = {"experiment_id": experiment_ids["exp5_benchmark"], "run_ids": [], "note": "Requires LLM evaluation"}

        # Experiment 6: Scalability
        logger.info("=" * 60)
        logger.info("Running Experiment 6: Scalability Analysis")
        logger.info("=" * 60)
        exp6_runs = self.run_scalability_analysis(experiment_ids["exp6_scalability"])
        self.service.start_experiment(experiment_ids["exp6_scalability"])
        if exp6_runs:
            self.service.complete_experiment(experiment_ids["exp6_scalability"])
        results["exp6"] = {"experiment_id": experiment_ids["exp6_scalability"], "run_ids": exp6_runs}

        return results
