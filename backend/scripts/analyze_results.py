#!/usr/bin/env python3
"""Analyze experiment results and generate paper tables.

Reads checkpoint/result files from data/benchmarks/results/ and produces:
- Summary statistics
- Comparison tables (markdown + LaTeX)
- Per-task and per-condition breakdowns
- Published baseline comparisons

Usage:
    cd backend
    uv run python scripts/analyze_results.py
"""

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RESULTS_DIR = "data/benchmarks/results"


def analyze_medqa_checkpoint(checkpoint_path: str) -> dict | None:
    """Analyze MedQA checkpoint file for accuracy metrics."""
    if not os.path.exists(checkpoint_path):
        return None

    results = []
    with open(checkpoint_path) as f:
        for line in f:
            line = line.strip()
            if line:
                results.append(json.loads(line))

    if not results:
        return None

    # Filter by condition
    conditions = defaultdict(list)
    for r in results:
        conditions[r.get("condition", "llm_alone")].append(r)

    analysis = {}
    for cond, entries in conditions.items():
        total = len(entries)
        correct = sum(1 for e in entries if e.get("correct"))
        errors = sum(1 for e in entries if e.get("error"))
        valid = total - errors

        valid_entries = [e for e in entries if not e.get("error")]

        step1 = [e for e in valid_entries if e.get("exam_level") == "step1"]
        step23 = [e for e in valid_entries if e.get("exam_level") in ("step2&3", "step2_3")]

        step1_correct = sum(1 for e in step1 if e.get("correct"))
        step23_correct = sum(1 for e in step23 if e.get("correct"))

        analysis[cond] = {
            "total": total,
            "correct": correct,
            "errors": errors,
            "valid": valid,
            "accuracy_all": correct / total if total > 0 else 0,
            "accuracy_valid": correct / valid if valid > 0 else 0,
            "step1_total": len(step1),
            "step1_correct": step1_correct,
            "step1_accuracy": step1_correct / len(step1) if step1 else 0,
            "step23_total": len(step23),
            "step23_correct": step23_correct,
            "step23_accuracy": step23_correct / len(step23) if step23 else 0,
        }

    return analysis


def analyze_clinicalbench_checkpoint(checkpoint_path: str) -> dict | None:
    """Analyze ClinicalBench checkpoint file for per-condition accuracy."""
    if not os.path.exists(checkpoint_path):
        return None

    results = []
    with open(checkpoint_path) as f:
        for line in f:
            line = line.strip()
            if line:
                results.append(json.loads(line))

    if not results:
        return None

    conditions = defaultdict(list)
    for r in results:
        conditions[r.get("condition", "unknown")].append(r)

    analysis = {}
    for cond, entries in conditions.items():
        total = len(entries)
        correct = sum(1 for e in entries if e.get("correct"))
        errors = sum(1 for e in entries if e.get("error"))

        # Per-category breakdown
        cats = defaultdict(lambda: {"total": 0, "correct": 0})
        for e in entries:
            cat = e.get("category", "unknown")
            cats[cat]["total"] += 1
            if e.get("correct"):
                cats[cat]["correct"] += 1

        cat_accuracies = {
            cat: v["correct"] / v["total"] if v["total"] > 0 else 0
            for cat, v in cats.items()
        }

        analysis[cond] = {
            "total": total,
            "correct": correct,
            "errors": errors,
            "accuracy": correct / total if total > 0 else 0,
            "category_accuracies": dict(sorted(cat_accuracies.items())),
        }

    return analysis


def print_medqa_table(analysis: dict) -> None:
    """Print MedQA results table."""
    print("\n## MedQA-USMLE Results")
    print()

    # Published baselines
    baselines = {
        "GPT-4 (2023)": 0.867,
        "Med-PaLM 2 (2023)": 0.865,
        "Claude-3 Opus (2024)": 0.780,
        "Gemma-2 27B": 0.700,
        "Llama-3 70B": 0.739,
    }

    print("| Model / Condition | Accuracy | Step 1 | Step 2&3 | Valid / Total | Errors |")
    print("|---|---|---|---|---|---|")

    for cond, metrics in analysis.items():
        err_note = f"{metrics['errors']}" if metrics['errors'] > 0 else "0"
        print(
            f"| **Ours ({cond})** | "
            f"**{metrics['accuracy_valid']:.1%}** | "
            f"{metrics['step1_accuracy']:.1%} | "
            f"{metrics['step23_accuracy']:.1%} | "
            f"{metrics['valid']} / {metrics['total']} | "
            f"{err_note} |"
        )

    print("|---|---|---|---|---|---|")
    for name, acc in baselines.items():
        print(f"| {name} | {acc:.1%} | — | — | — | — |")

    # Note about errors
    total_errors = sum(m["errors"] for m in analysis.values())
    if total_errors > 0:
        print(f"\n*Note: {total_errors} questions hit API errors (credit exhaustion). "
              f"Accuracy computed on valid responses only. "
              f"Re-run will automatically retry errored questions.*")


def print_clinicalbench_table(analysis: dict) -> None:
    """Print ClinicalBench ablation table."""
    print("\n## ClinicalIntelligenceBench Ablation Results")
    print()

    # Collect all categories
    all_cats = sorted({
        cat
        for cond_data in analysis.values()
        for cat in cond_data.get("category_accuracies", {})
    })

    # Main table
    cat_header = " | ".join(all_cats[:6]) if all_cats else ""
    print(f"| Condition | Accuracy | {cat_header} | N |")
    sep = "|---|---|" + "|".join("---" for _ in all_cats[:6]) + "|---|"
    print(sep)

    condition_order = [
        "C1_llm_alone", "C2_vanilla_rag", "C3_kg_rag",
        "C4_epistemic_kg_rag", "C5_full_system",
    ]

    labels = {
        "C1_llm_alone": "C1: LLM Alone",
        "C2_vanilla_rag": "C2: +Vanilla RAG",
        "C3_kg_rag": "C3: +KG-RAG",
        "C4_epistemic_kg_rag": "C4: +Epistemic",
        "C5_full_system": "C5: Full System",
    }

    for cond in condition_order:
        if cond not in analysis:
            continue
        m = analysis[cond]
        cat_vals = " | ".join(
            f"{m['category_accuracies'].get(cat, 0):.1%}"
            for cat in all_cats[:6]
        )
        print(
            f"| {labels.get(cond, cond)} | "
            f"**{m['accuracy']:.1%}** | "
            f"{cat_vals} | "
            f"{m['total']} |"
        )

    # Deltas
    print("\n### Accuracy Deltas (Condition vs C1)")
    if "C1_llm_alone" in analysis:
        c1_acc = analysis["C1_llm_alone"]["accuracy"]
        for cond in condition_order[1:]:
            if cond in analysis:
                delta = analysis[cond]["accuracy"] - c1_acc
                print(f"  {labels.get(cond, cond)}: {delta:+.1%}")


def print_latex_table(medqa: dict | None, clinicalbench: dict | None) -> None:
    """Print LaTeX tables for the paper."""
    if medqa:
        print("\n### LaTeX: MedQA")
        print("\\begin{tabular}{lcccc}")
        print("\\toprule")
        print("\\textbf{Model} & \\textbf{Accuracy} & \\textbf{Step 1} & \\textbf{Step 2\\&3} & \\textbf{N} \\\\")
        print("\\midrule")
        for cond, m in medqa.items():
            print(
                f"Ours ({cond}) & \\textbf{{{m['accuracy_valid']*100:.1f}\\%}} & "
                f"{m['step1_accuracy']*100:.1f}\\% & {m['step23_accuracy']*100:.1f}\\% & {m['valid']} \\\\"
            )
        print("\\midrule")
        baselines = {"GPT-4": 86.7, "Med-PaLM 2": 86.5, "Claude-3 Opus": 78.0, "Gemma-2 27B": 70.0, "Llama-3 70B": 73.9}
        for name, acc in baselines.items():
            print(f"{name} & {acc:.1f}\\% & -- & -- & -- \\\\")
        print("\\bottomrule")
        print("\\end{tabular}")

    if clinicalbench:
        print("\n### LaTeX: ClinicalIntelligenceBench")
        labels = {
            "C1_llm_alone": "C1: LLM Alone",
            "C2_vanilla_rag": "C2: +Vanilla RAG",
            "C3_kg_rag": "C3: +KG-RAG",
            "C4_epistemic_kg_rag": "C4: +Epistemic KG-RAG",
            "C5_full_system": "C5: Full System",
        }
        print("\\begin{tabular}{lcccc}")
        print("\\toprule")
        print("\\textbf{Condition} & \\textbf{Accuracy} & \\textbf{$\\Delta$ vs C1} & \\textbf{N} \\\\")
        print("\\midrule")
        c1_acc = clinicalbench.get("C1_llm_alone", {}).get("accuracy", 0)
        for cond in ["C1_llm_alone", "C2_vanilla_rag", "C3_kg_rag", "C4_epistemic_kg_rag", "C5_full_system"]:
            if cond in clinicalbench:
                m = clinicalbench[cond]
                delta = m["accuracy"] - c1_acc
                delta_str = f"+{delta:.1f}\\%" if delta > 0 else f"{delta:.1f}\\%"
                if cond == "C1_llm_alone":
                    delta_str = "--"
                print(
                    f"{labels.get(cond, cond)} & {m['accuracy']*100:.1f}\\% & "
                    f"{delta_str} & {m['total']} \\\\"
                )
        print("\\bottomrule")
        print("\\end{tabular}")


def main():
    print("=" * 70)
    print("NeurIPS 2026 — Experiment Results Analysis")
    print("=" * 70)

    # MedQA
    medqa_checkpoint = os.path.join(RESULTS_DIR, "medqa_checkpoint.jsonl")
    medqa = analyze_medqa_checkpoint(medqa_checkpoint)
    if medqa:
        print_medqa_table(medqa)
    else:
        medqa_json = os.path.join(RESULTS_DIR, "..", "medqa_result.json")
        if os.path.exists(medqa_json):
            data = json.load(open(medqa_json))
            print(f"\nMedQA (from JSON): {data.get('evaluated_questions', '?')} questions")
            for cond, cr in data.get("conditions", {}).items():
                print(f"  {cond}: {cr['accuracy']:.1%} ({cr['correct']}/{cr['total']})")
        else:
            print("\nNo MedQA results found.")

    # ClinicalBench
    cb_checkpoint = os.path.join(RESULTS_DIR, "clinicalbench_checkpoint.jsonl")
    clinicalbench = analyze_clinicalbench_checkpoint(cb_checkpoint)
    if clinicalbench:
        print_clinicalbench_table(clinicalbench)
    else:
        cb_json = os.path.join(RESULTS_DIR, "clinicalbench_ablation.json")
        if os.path.exists(cb_json):
            data = json.load(open(cb_json))
            print(f"\nClinicalBench (from JSON): {data.get('total_questions', '?')} questions")
            for cond, cr in data.get("conditions", {}).items():
                print(f"  {cr['label']}: {cr['accuracy']:.1%}")
        else:
            print("\nNo ClinicalBench results found.")

    # DR.KNOWS
    drknows_path = os.path.join(RESULTS_DIR, "drknows_benchmark.json")
    if os.path.exists(drknows_path):
        dk = json.load(open(drknows_path))
        print("\n## DR.KNOWS Benchmark Comparison")
        print(f"Overall score: {dk['overall_score']:.3f} ({dk['comparison']['overall']['percentage_of_baseline']:.1f}% of baseline)")
        metrics = dk.get("metrics", {})
        print(f"  Path discovery: {metrics.get('path_discovery', {}).get('coverage', 0):.1%}")
        print(f"  Reasoning accuracy: {metrics.get('reasoning', {}).get('accuracy', 0):.1%}")
        mh = metrics.get("multi_hop", {})
        print(f"  Multi-hop: 1-hop={mh.get('hop_1', 0):.1%}, 2-hop={mh.get('hop_2', 0):.1%}, 3-hop={mh.get('hop_3', 0):.1%}")

    # Scalability
    scale_path = os.path.join(RESULTS_DIR, "scalability_analysis.json")
    if os.path.exists(scale_path):
        s = json.load(open(scale_path))
        corpus = s.get("corpus", {})
        latencies = s.get("query_latencies", {})
        print("\n## Scalability Analysis")
        print(f"  Documents: {corpus.get('documents', 0)}")
        print(f"  Patients: {corpus.get('patients', 0)}")
        print(f"  KG nodes: {corpus.get('kg_nodes', 0)}, edges: {corpus.get('kg_edges', 0)}")
        print(f"  1-hop traversal: {latencies.get('edge_traversal_1hop', {}).get('avg_ms', 0):.2f}ms")
        print(f"  2-hop traversal: {latencies.get('edge_traversal_2hop', {}).get('avg_ms', 0):.2f}ms")

    # LaTeX tables
    print("\n" + "=" * 70)
    print("LATEX TABLES")
    print("=" * 70)
    print_latex_table(medqa, clinicalbench)

    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
