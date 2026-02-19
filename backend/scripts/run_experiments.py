#!/usr/bin/env python3
"""Run NeurIPS 2026 paper experiments.

Usage:
    python -m scripts.run_experiments --all           # Run all 6 experiments
    python -m scripts.run_experiments --exp 1         # Run specific experiment
    python -m scripts.run_experiments --exp 1 2 3     # Run multiple experiments
    python -m scripts.run_experiments --list-datasets  # Show available datasets
    python -m scripts.run_experiments --status         # Show experiment status
    python -m scripts.run_experiments --export latex   # Export results as LaTeX

Run from backend/ directory:
    cd backend && python -m scripts.run_experiments --all
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.experiment_runner import (
    ExperimentRunner,
    get_all_datasets,
    get_dataset_documents,
)
from app.services.research_service import get_research_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("run_experiments")


def list_datasets() -> None:
    """Show available datasets and document counts."""
    print("\n=== Available Datasets ===\n")
    datasets = get_all_datasets()

    if not datasets:
        print("No datasets found. Import data first:")
        print("  - MTSamples: POST /api/documents/mtsamples/import")
        print("  - Synthea:   POST /api/documents/synthea/import")
        print("  - MIMIC:     POST /api/documents/mimic/import")
        return

    total_docs = 0
    total_patients = 0

    for source, ds in datasets.items():
        print(f"  {source:15s}  {ds.doc_count:5d} documents  {len(ds.patient_ids):5d} patients")
        total_docs += ds.doc_count
        total_patients += len(ds.patient_ids)

    print(f"  {'─' * 45}")
    print(f"  {'TOTAL':15s}  {total_docs:5d} documents  {total_patients:5d} patients")
    print()


def show_status() -> None:
    """Show experiment status."""
    service = get_research_service()
    experiments, total = service.list_experiments(limit=50)

    if not experiments:
        print("\nNo experiments found. Run with --all to create and execute experiments.")
        return

    print(f"\n=== Experiments ({total} total) ===\n")
    print(f"  {'ID':8s}  {'Status':12s}  {'Runs':5s}  {'Name'}")
    print(f"  {'─' * 70}")

    for exp in experiments:
        status = exp.status
        name = exp.name[:50]
        exp_id = exp.id[:8]
        print(f"  {exp_id}  {status:12s}  {exp.run_count:5d}  {name}")

    # Show metrics summary for completed experiments
    completed = [e for e in experiments if e.status == "completed"]
    if completed:
        print(f"\n=== Completed Experiment Summaries ===\n")
        for exp in completed:
            print(f"  {exp.name}")
            if exp.summary_metrics:
                for key, val in sorted(exp.summary_metrics.items()):
                    if isinstance(val, dict):
                        mean = val.get("mean", 0)
                        print(f"    {key:40s}  mean={mean:.4f}")
                    else:
                        print(f"    {key:40s}  {val}")
            print()


def run_experiments(exp_numbers: list[int]) -> None:
    """Run specified experiments."""
    runner = ExperimentRunner()

    # First check datasets
    datasets = get_all_datasets()
    if not datasets:
        print("ERROR: No datasets available. Import data first.")
        sys.exit(1)

    print(f"\nAvailable data: {', '.join(f'{s}: {ds.doc_count} docs' for s, ds in datasets.items())}\n")

    # Create all experiment definitions
    print("Creating experiment definitions...")
    experiment_ids = runner.create_all_experiments()

    exp_map = {
        1: ("exp1_pipeline_eval", runner.run_pipeline_evaluation),
        2: ("exp2_assertion_ablation", runner.run_assertion_ablation),
        3: ("exp3_temporal_ablation", runner.run_temporal_ablation),
        4: ("exp4_graphrag_comparison", runner.run_graphrag_comparison),
        5: ("exp5_benchmark", None),  # Requires LLM — placeholder
        6: ("exp6_scalability", runner.run_scalability_analysis),
    }

    results = {}
    service = get_research_service()

    for num in exp_numbers:
        if num not in exp_map:
            print(f"WARNING: Unknown experiment number {num}, skipping.")
            continue

        key, runner_fn = exp_map[num]
        exp_id = experiment_ids[key]

        if runner_fn is None:
            print(f"\nExperiment {num} ({key}): Requires LLM evaluation — skipping automated run.")
            print(f"  Created experiment ID: {exp_id}")
            results[num] = {"experiment_id": exp_id, "run_ids": [], "note": "Requires LLM"}
            continue

        print(f"\n{'=' * 60}")
        print(f"Running Experiment {num}: {key}")
        print(f"{'=' * 60}")

        service.start_experiment(exp_id)
        run_ids = runner_fn(exp_id)

        if run_ids:
            service.complete_experiment(exp_id)
            print(f"  Completed: {len(run_ids)} runs")

            # Print metric summary
            for rid in run_ids:
                run = service.get_run(rid)
                if run:
                    config = run.run_config or {}
                    label = config.get("dataset", config.get("condition", config.get("scale_point", "run")))
                    metrics = service.get_run_metrics(rid)
                    print(f"\n  Run [{label}]: {run.metric_count} metrics")
                    for m in metrics[:10]:
                        print(f"    {m.category}/{m.metric_name}: {m.metric_value:.4f}")
                    if len(metrics) > 10:
                        print(f"    ... and {len(metrics) - 10} more metrics")
        else:
            print(f"  No runs completed (no data available?)")

        results[num] = {"experiment_id": exp_id, "run_ids": run_ids}

    # Print summary
    print(f"\n{'=' * 60}")
    print("EXPERIMENT EXECUTION SUMMARY")
    print(f"{'=' * 60}")
    for num, res in sorted(results.items()):
        n_runs = len(res.get("run_ids", []))
        note = res.get("note", "")
        print(f"  Exp {num}: {n_runs} runs  {note}")


def export_results(fmt: str) -> None:
    """Export all completed experiment results."""
    service = get_research_service()
    experiments, _ = service.list_experiments(status="completed")

    if not experiments:
        print("No completed experiments to export.")
        return

    # Collect all run IDs from completed experiments
    all_run_ids = []
    for exp in experiments:
        runs, _ = service.list_runs(exp.id)
        for r in runs:
            if r.status == "completed":
                all_run_ids.append(r.id)

    if not all_run_ids:
        print("No completed runs to export.")
        return

    export = service.export_metrics(all_run_ids, format=fmt)
    print(f"\n=== Export ({fmt}) ===\n")
    print(export.content)

    # Also save to file
    output_dir = Path(__file__).resolve().parent.parent / "docs" / "paper" / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / export.filename
    output_file.write_text(export.content)
    print(f"\nSaved to: {output_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run NeurIPS 2026 paper experiments")
    parser.add_argument("--all", action="store_true", help="Run all 6 experiments")
    parser.add_argument("--exp", type=int, nargs="+", help="Run specific experiment(s) by number (1-6)")
    parser.add_argument("--list-datasets", action="store_true", help="Show available datasets")
    parser.add_argument("--status", action="store_true", help="Show experiment status")
    parser.add_argument("--export", choices=["csv", "json", "latex"], help="Export results")

    args = parser.parse_args()

    if args.list_datasets:
        list_datasets()
    elif args.status:
        show_status()
    elif args.export:
        export_results(args.export)
    elif args.all:
        run_experiments([1, 2, 3, 4, 5, 6])
    elif args.exp:
        run_experiments(args.exp)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
