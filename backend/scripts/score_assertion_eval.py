#!/usr/bin/env python3
"""Score physician annotations of assertion classifier predictions.

Reads the annotated JSONL and computes:
1. Overall accuracy (micro)
2. Per-class P/R/F1 (sklearn classification_report)
3. Confusion matrix (7x7)
4. Cohen's kappa (multi-class)
5. 95% Wilson CIs on per-class accuracy
6. Error analysis: disagreements grouped by type
7. LaTeX table fragment for paper appendix

Usage:
    cd backend
    uv run python3 scripts/score_assertion_eval.py
"""

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ANNOTATED_PATH = Path(__file__).parent.parent / "data" / "benchmarks" / "assertion_eval_annotated.jsonl"
RESULTS_PATH = Path(__file__).parent.parent / "data" / "benchmarks" / "assertion_eval_results.json"

ASSERTION_ORDER = [
    "present", "absent", "possible", "historical",
    "conditional", "hypothetical", "family_history",
]


def wilson_ci(n_correct: int, n_total: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a proportion."""
    if n_total == 0:
        return (0.0, 0.0)
    p = n_correct / n_total
    denom = 1 + z**2 / n_total
    center = (p + z**2 / (2 * n_total)) / denom
    spread = z * math.sqrt((p * (1 - p) + z**2 / (4 * n_total)) / n_total) / denom
    return (max(0.0, center - spread), min(1.0, center + spread))


def load_annotations() -> list[dict]:
    if not ANNOTATED_PATH.exists():
        print(f"Annotated file not found: {ANNOTATED_PATH}")
        print("Run annotate_assertions.py first.")
        sys.exit(1)
    items = []
    with open(ANNOTATED_PATH) as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                if item.get("gold_label"):
                    items.append(item)
    return items


def main():
    from sklearn.metrics import (
        classification_report,
        cohen_kappa_score,
        confusion_matrix,
    )

    items = load_annotations()
    n = len(items)
    if n == 0:
        print("No annotations found. Run annotate_assertions.py first.")
        sys.exit(1)
    print(f"Loaded {n} annotated mentions\n")

    y_true = [item["gold_label"] for item in items]
    y_pred = [item["classifier_prediction"] for item in items]

    # Filter to labels that actually appear
    labels_present = sorted(
        set(y_true) | set(y_pred),
        key=lambda x: ASSERTION_ORDER.index(x) if x in ASSERTION_ORDER else 99,
    )

    # 1. Overall accuracy
    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    accuracy = correct / n
    acc_lo, acc_hi = wilson_ci(correct, n)
    print(f"{'='*60}")
    print(f"OVERALL ACCURACY: {accuracy:.1%} ({correct}/{n})")
    print(f"95% Wilson CI: [{acc_lo:.1%}, {acc_hi:.1%}]")
    print(f"{'='*60}\n")

    # 2. Classification report
    print("PER-CLASS METRICS (sklearn classification_report):")
    print(classification_report(y_true, y_pred, labels=labels_present, zero_division=0))

    # 3. Confusion matrix
    cm = confusion_matrix(y_true, y_pred, labels=labels_present)
    print("CONFUSION MATRIX (rows=gold, cols=predicted):")
    header = f"{'':>15}" + "".join(f" {l[:8]:>8}" for l in labels_present)
    print(header)
    for i, label in enumerate(labels_present):
        row = f"{label:>15}" + "".join(f" {cm[i,j]:>8}" for j in range(len(labels_present)))
        print(row)

    # 4. Cohen's kappa
    kappa = cohen_kappa_score(y_true, y_pred, labels=labels_present)
    print(f"\nCohen's kappa: {kappa:.3f}")

    # 5. Per-class accuracy with Wilson CIs
    print(f"\nPER-CLASS ACCURACY (Wilson 95% CI):")
    print(f"{'Assertion':<18} {'n':>4} {'Acc':>7} {'CI':>20}")
    print("-" * 55)
    per_class_results = {}
    for label in labels_present:
        n_class = sum(1 for t in y_true if t == label)
        n_correct = sum(1 for t, p in zip(y_true, y_pred) if t == label and t == p)
        acc = n_correct / n_class if n_class else 0
        lo, hi = wilson_ci(n_correct, n_class)
        per_class_results[label] = {
            "n": n_class, "correct": n_correct, "accuracy": acc,
            "ci_low": lo, "ci_high": hi,
        }
        print(f"{label:<18} {n_class:>4} {acc:>6.1%} [{lo:.1%}, {hi:.1%}]")

    # 6. Error analysis
    print(f"\n{'='*60}")
    print("ERROR ANALYSIS")
    print(f"{'='*60}")
    errors = [(item, item["gold_label"], item["classifier_prediction"])
              for item in items
              if item["gold_label"] != item["classifier_prediction"]]
    print(f"Total errors: {len(errors)}/{n} ({len(errors)/n:.1%})")

    error_types = Counter()
    for item, gold, pred in errors:
        error_types[f"{pred} -> {gold}"] += 1
    print(f"\nError patterns (predicted -> gold):")
    for pattern, count in error_types.most_common():
        print(f"  {pattern:<35} {count:>3}")

    # Show example errors per type
    print(f"\nExample errors:")
    shown_types = set()
    for item, gold, pred in errors:
        key = f"{pred}->{gold}"
        if key not in shown_types and len(shown_types) < 10:
            shown_types.add(key)
            mention = item["mention_text"][:40]
            ctx = item["context_window"][:80].replace(">>>", "[").replace("<<<", "]")
            print(f"  [{pred} -> {gold}] \"{mention}\"")
            print(f"    {ctx}...")

    # 7. LaTeX table
    print(f"\n{'='*60}")
    print("LATEX TABLE FRAGMENT (for paper appendix)")
    print(f"{'='*60}")

    # Get sklearn report as dict for P/R/F1
    report = classification_report(
        y_true, y_pred, labels=labels_present, output_dict=True, zero_division=0
    )

    latex = r"""\begin{table}[ht]
\centering
\small
\caption{Intrinsic assertion classifier evaluation on """ + str(n) + r""" physician-annotated
  MIMIC-IV mentions (stratified sample from 43 ClinicalBench patients).}
\label{tab:assertion_intrinsic}
\begin{tabular}{@{}lrrrr@{}}
\toprule
Assertion & $n$ & P & R & F1 \\
\midrule
"""
    for label in labels_present:
        r = report[label]
        n_label = int(r["support"])
        p_val = r["precision"]
        r_val = r["recall"]
        f1_val = r["f1-score"]
        display = label.replace("_", r"\_").capitalize()
        latex += f"{display} & {n_label} & {p_val:.3f} & {r_val:.3f} & {f1_val:.3f} \\\\\n"

    weighted = report["weighted avg"]
    latex += r"""\midrule
\textbf{Weighted avg} & """ + str(n) + f" & {weighted['precision']:.3f} & {weighted['recall']:.3f} & {weighted['f1-score']:.3f}"
    latex += r""" \\
\bottomrule
\end{tabular}
\end{table}"""

    print(latex)

    # Also print Cohen's kappa line for paper
    print(f"\n% Cohen's kappa: {kappa:.3f}")
    print(f"% Overall accuracy: {accuracy:.1%} [{acc_lo:.1%}, {acc_hi:.1%}]")

    # 8. Save JSON results
    results = {
        "n": n,
        "overall_accuracy": round(accuracy, 4),
        "overall_ci": [round(acc_lo, 4), round(acc_hi, 4)],
        "cohens_kappa": round(kappa, 4),
        "per_class": per_class_results,
        "confusion_matrix": {
            "labels": labels_present,
            "matrix": cm.tolist(),
        },
        "error_patterns": dict(error_types.most_common()),
        "classification_report": report,
    }
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved results to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
