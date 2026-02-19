#!/usr/bin/env python3
"""Run QA ablation experiments for NeurIPS 2026 paper.

Usage:
    # Run all QA experiments for a specific patient
    python scripts/run_qa_experiments.py --patient-id P001

    # Run only the assertion ablation (Experiment 2)
    python scripts/run_qa_experiments.py --patient-id P001 --experiment assertion

    # Run with a specific LLM model
    python scripts/run_qa_experiments.py --patient-id P001 --model claude-haiku-4-5-20251001

    # Run across multiple patients
    python scripts/run_qa_experiments.py --all-patients --limit 10

    # Dry run — show what would be executed without calling LLM
    python scripts/run_qa_experiments.py --patient-id P001 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import get_sync_engine
from app.services.qa_experiment_executor import (
    QAExperimentExecutor,
    QARunConfig,
    print_ablation_table,
)
from app.services.qa_evaluation import (
    ASSERTION_QUESTIONS,
    TEMPORAL_QUESTIONS,
    RAG_QUESTIONS,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_qa_experiments")


def get_patient_ids(limit: int | None = None) -> list[str]:
    """Get patient IDs from the database that have KG data."""
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session
    from app.models.knowledge_graph import KGEdge

    with Session(get_sync_engine()) as session:
        query = (
            select(KGEdge.patient_id)
            .where(KGEdge.patient_id.isnot(None), KGEdge.deleted_at.is_(None))
            .group_by(KGEdge.patient_id)
            .having(func.count(KGEdge.id) >= 5)  # At least 5 edges
            .order_by(func.count(KGEdge.id).desc())
        )
        if limit:
            query = query.limit(limit)

        return [row for row in session.scalars(query).all()]


def dry_run_summary() -> None:
    """Print experiment summary without executing anything."""
    print("\n=== DRY RUN: QA Experiment Summary ===\n")

    print(f"Experiment 2 — Assertion Ablation:")
    print(f"  Questions: {len(ASSERTION_QUESTIONS)}")
    print(f"  Conditions: no_assertion, assertion_extracted_only, full_epistemic")
    print(f"  Total LLM calls: {len(ASSERTION_QUESTIONS) * 3}")
    cats = {}
    for q in ASSERTION_QUESTIONS:
        cats[q.category] = cats.get(q.category, 0) + 1
    for cat, count in sorted(cats.items()):
        print(f"    {cat}: {count} questions")

    print(f"\nExperiment 3 — Temporal Ablation:")
    print(f"  Questions: {len(TEMPORAL_QUESTIONS)}")
    print(f"  Conditions: no_temporal, timestamps_only, full_bitemporal")
    print(f"  Total LLM calls: {len(TEMPORAL_QUESTIONS) * 3}")

    print(f"\nExperiment 4 — GraphRAG Comparison:")
    print(f"  Questions: {len(RAG_QUESTIONS)}")
    print(f"  Conditions: doc_only, graph_only, graph_plus_doc, graph_plus_doc_plus_guidelines")
    print(f"  Total LLM calls: {len(RAG_QUESTIONS) * 4}")

    total = (
        len(ASSERTION_QUESTIONS) * 3
        + len(TEMPORAL_QUESTIONS) * 3
        + len(RAG_QUESTIONS) * 4
    )
    print(f"\nTotal LLM calls per patient: {total}")
    print(f"Estimated cost (Sonnet API): ~${total * 0.003:.2f}")
    print(f"Estimated cost (Haiku API):  ~${total * 0.0005:.2f}")
    print(f"Estimated cost (Ollama):     $0.00 (local)")
    print(f"Estimated time (Sonnet API): ~{total * 2 / 60:.0f} minutes")
    print(f"Estimated time (Ollama 27B): ~{total * 8 / 60:.0f} minutes")
    print()
    print("Recommended local models:")
    print("  --provider ollama --model alibayram/medgemma:27b    (best quality, ~8s/q)")
    print("  --provider ollama --model nemotron-3-nano:30b       (good reasoning, ~8s/q)")
    print("  --provider ollama --model qwen3:latest              (fast 8B, ~2s/q)")


async def run_experiments(
    patient_ids: list[str],
    experiment: str,
    model: str,
    provider: str,
    output_dir: str,
) -> None:
    """Run experiments across patients and save results."""
    executor = QAExperimentExecutor()
    all_results = {}

    for pid in patient_ids:
        logger.info("=" * 60)
        logger.info("Patient: %s", pid)
        logger.info("=" * 60)

        patient_results = {}

        if experiment in ("all", "assertion"):
            logger.info("Running Experiment 2: Assertion Ablation")
            reports = await executor.run_assertion_ablation(
                patient_id=pid, llm_provider=provider, llm_model=model,
            )
            patient_results["exp2_assertion"] = {
                cond: {
                    "accuracy": r.accuracy,
                    "correct": r.correct,
                    "total": r.total_questions,
                    "category_accuracies": r.category_accuracies,
                    "avg_latency_ms": r.avg_latency_ms,
                    "results": [
                        {
                            "question_id": res.question_id,
                            "category": res.category,
                            "correct": res.correct,
                            "score": res.score,
                            "predicted": res.predicted_answer[:200],
                            "expected": res.expected_answer[:200],
                            "latency_ms": res.latency_ms,
                            "error": res.error,
                        }
                        for res in r.results
                    ],
                }
                for cond, r in reports.items()
            }

            print("\n" + print_ablation_table(reports))

        if experiment in ("all", "temporal"):
            logger.info("Running Experiment 3: Temporal Ablation")
            reports = await executor.run_temporal_ablation(
                patient_id=pid, llm_provider=provider, llm_model=model,
            )
            patient_results["exp3_temporal"] = {
                cond: {
                    "accuracy": r.accuracy,
                    "correct": r.correct,
                    "total": r.total_questions,
                    "category_accuracies": r.category_accuracies,
                    "avg_latency_ms": r.avg_latency_ms,
                }
                for cond, r in reports.items()
            }

            print("\n" + print_ablation_table(reports))

        if experiment in ("all", "graphrag"):
            logger.info("Running Experiment 4: GraphRAG Comparison")
            reports = await executor.run_graphrag_comparison(
                patient_id=pid, llm_provider=provider, llm_model=model,
            )
            patient_results["exp4_graphrag"] = {
                cond: {
                    "accuracy": r.accuracy,
                    "correct": r.correct,
                    "total": r.total_questions,
                    "category_accuracies": r.category_accuracies,
                    "avg_latency_ms": r.avg_latency_ms,
                }
                for cond, r in reports.items()
            }

            print("\n" + print_ablation_table(reports))

        all_results[pid] = patient_results

    # Save results
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    results_file = out_path / "qa_experiment_results.json"
    results_file.write_text(json.dumps(all_results, indent=2, default=str))
    logger.info("Results saved to %s", results_file)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run QA ablation experiments")
    parser.add_argument("--patient-id", type=str, help="Specific patient ID")
    parser.add_argument("--all-patients", action="store_true", help="Run for all patients with KG data")
    parser.add_argument("--limit", type=int, default=10, help="Max patients for --all-patients")
    parser.add_argument(
        "--experiment",
        choices=["all", "assertion", "temporal", "graphrag"],
        default="all",
        help="Which experiment to run",
    )
    parser.add_argument("--model", default="claude-sonnet-4-5-20250929", help="LLM model to use")
    parser.add_argument("--provider", default="anthropic", help="LLM provider")
    parser.add_argument("--output-dir", default="results/qa_experiments", help="Output directory")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without executing")

    args = parser.parse_args()

    if args.dry_run:
        dry_run_summary()
        return

    if args.patient_id:
        patient_ids = [args.patient_id]
    elif args.all_patients:
        patient_ids = get_patient_ids(limit=args.limit)
        if not patient_ids:
            logger.error("No patients with KG data found in database")
            sys.exit(1)
        logger.info("Found %d patients with KG data", len(patient_ids))
    else:
        parser.error("Specify --patient-id or --all-patients")

    asyncio.run(
        run_experiments(
            patient_ids=patient_ids,
            experiment=args.experiment,
            model=args.model,
            provider=args.provider,
            output_dir=args.output_dir,
        )
    )


if __name__ == "__main__":
    main()
