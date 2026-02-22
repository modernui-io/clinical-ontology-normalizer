#!/usr/bin/env python3
"""Statistical analysis for NeurIPS 2026 experiment results.

Provides:
- Bootstrap confidence intervals for per-condition accuracy
- McNemar's test for pairwise significance between conditions
- Cohen's d for effect size estimation
- Bonferroni correction for multiple comparisons
- LaTeX table generation with CIs and p-values

Usage:
    cd backend
    uv run python scripts/statistical_analysis.py [checkpoint_path]

Or import and use programmatically:
    from scripts.statistical_analysis import bootstrap_ci, mcnemar_test
"""

from __future__ import annotations

import json
import math
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# Bootstrap confidence intervals
# ============================================================================


def bootstrap_ci(
    scores: list[bool | int],
    n_bootstrap: int = 10000,
    ci: float = 0.95,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Compute bootstrap confidence interval for accuracy.

    Args:
        scores: List of binary outcomes (True/1 = correct, False/0 = incorrect).
        n_bootstrap: Number of bootstrap resamples.
        ci: Confidence level (default 0.95 for 95% CI).
        seed: Random seed for reproducibility.

    Returns:
        Tuple of (point_estimate, ci_lower, ci_upper).
    """
    if not scores:
        return 0.0, 0.0, 0.0

    rng = random.Random(seed)
    n = len(scores)
    point_estimate = sum(scores) / n

    boot_means: list[float] = []
    for _ in range(n_bootstrap):
        sample = rng.choices(scores, k=n)
        boot_means.append(sum(sample) / n)

    boot_means.sort()
    alpha = 1 - ci
    lower_idx = int(math.floor(alpha / 2 * n_bootstrap))
    upper_idx = int(math.ceil((1 - alpha / 2) * n_bootstrap)) - 1

    # Clamp indices
    lower_idx = max(0, min(lower_idx, n_bootstrap - 1))
    upper_idx = max(0, min(upper_idx, n_bootstrap - 1))

    return point_estimate, boot_means[lower_idx], boot_means[upper_idx]


# ============================================================================
# McNemar's test for paired binary outcomes
# ============================================================================


def mcnemar_test(
    results_a: list[bool | int],
    results_b: list[bool | int],
) -> tuple[float, float]:
    """McNemar's test for paired binary outcomes.

    Tests whether two conditions have significantly different accuracy
    on the same set of questions.

    Args:
        results_a: Binary outcomes for condition A (per question).
        results_b: Binary outcomes for condition B (per question).

    Returns:
        Tuple of (chi_squared_statistic, p_value).

    Raises:
        ValueError: If input lists have different lengths.
    """
    if len(results_a) != len(results_b):
        raise ValueError(
            f"Results must have same length: {len(results_a)} vs {len(results_b)}"
        )

    # Count discordant pairs
    # b: A correct, B incorrect
    # c: A incorrect, B correct
    b = sum(1 for a, bv in zip(results_a, results_b) if a and not bv)
    c = sum(1 for a, bv in zip(results_a, results_b) if not a and bv)

    if b + c == 0:
        return 0.0, 1.0  # No discordant pairs

    # McNemar's chi-squared with continuity correction
    chi2 = (abs(b - c) - 1) ** 2 / (b + c)

    # Approximate p-value from chi-squared distribution (1 df)
    p_value = _chi2_sf(chi2, df=1)

    return chi2, p_value


def _chi2_sf(x: float, df: int = 1) -> float:
    """Survival function (1 - CDF) for chi-squared distribution.

    Uses the regularized incomplete gamma function approximation.
    For df=1, this simplifies to 1 - erf(sqrt(x/2)).
    """
    if x <= 0:
        return 1.0
    if df == 1:
        return math.erfc(math.sqrt(x / 2))
    # General case: use incomplete gamma function approximation
    # For df=1, the above is exact. For other df, use series expansion.
    a = df / 2.0
    return _regularized_gamma_q(a, x / 2.0)


def _regularized_gamma_q(a: float, x: float) -> float:
    """Upper regularized incomplete gamma function Q(a, x) = 1 - P(a, x).

    Uses continued fraction approximation (Lentz's method).
    """
    if x < a + 1:
        return 1.0 - _regularized_gamma_p_series(a, x)
    return _regularized_gamma_q_cf(a, x)


def _regularized_gamma_p_series(a: float, x: float, max_iter: int = 200) -> float:
    """Lower regularized incomplete gamma via series expansion."""
    if x == 0:
        return 0.0
    ap = a
    s = 1.0 / a
    ds = s
    for _ in range(max_iter):
        ap += 1
        ds *= x / ap
        s += ds
        if abs(ds) < abs(s) * 1e-15:
            break
    return s * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _regularized_gamma_q_cf(a: float, x: float, max_iter: int = 200) -> float:
    """Upper regularized incomplete gamma via continued fraction."""
    b0 = x + 1 - a
    c = 1e30
    d = 1.0 / b0 if b0 != 0 else 1e30
    h = d
    for i in range(1, max_iter + 1):
        an = -i * (i - a)
        bn = x + 2 * i + 1 - a
        d = bn + an * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = bn + an / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-15:
            break
    return h * math.exp(-x + a * math.log(x) - math.lgamma(a))


# ============================================================================
# Effect size: Cohen's d
# ============================================================================


def cohens_d(group1: list[bool | int], group2: list[bool | int]) -> float:
    """Compute Cohen's d effect size between two groups of binary outcomes.

    Args:
        group1: Binary outcomes for group 1.
        group2: Binary outcomes for group 2.

    Returns:
        Cohen's d (positive means group2 > group1).
    """
    n1, n2 = len(group1), len(group2)
    if n1 == 0 or n2 == 0:
        return 0.0

    mean1 = sum(group1) / n1
    mean2 = sum(group2) / n2

    var1 = sum((x - mean1) ** 2 for x in group1) / max(n1 - 1, 1)
    var2 = sum((x - mean2) ** 2 for x in group2) / max(n2 - 1, 1)

    pooled_std = math.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / max(n1 + n2 - 2, 1))

    if pooled_std == 0:
        return 0.0

    return (mean2 - mean1) / pooled_std


# ============================================================================
# Multiple comparison correction
# ============================================================================


def bonferroni_correction(
    p_values: list[float],
    n_comparisons: int | None = None,
) -> list[float]:
    """Apply Bonferroni correction to p-values.

    Args:
        p_values: List of uncorrected p-values.
        n_comparisons: Number of comparisons (defaults to len(p_values)).

    Returns:
        List of corrected p-values (capped at 1.0).
    """
    n = n_comparisons or len(p_values)
    return [min(p * n, 1.0) for p in p_values]


# ============================================================================
# LaTeX table generation
# ============================================================================


def latex_results_table(
    condition_results: dict[str, list[bool | int]],
    condition_labels: dict[str, str] | None = None,
    baseline_condition: str = "C1_llm_alone",
    n_bootstrap: int = 10000,
) -> str:
    """Generate a LaTeX table with accuracy, CIs, and pairwise p-values.

    Args:
        condition_results: Dict mapping condition name -> list of binary outcomes.
        condition_labels: Optional human-readable labels for conditions.
        baseline_condition: Condition to compare against for p-values.
        n_bootstrap: Number of bootstrap resamples for CIs.

    Returns:
        LaTeX table as a string.
    """
    if condition_labels is None:
        condition_labels = {
            "C1_llm_alone": "C1: LLM Alone",
            "C2_vanilla_rag": "C2: +Vanilla RAG",
            "C3_kg_rag": "C3: +KG-RAG",
            "C4_epistemic_kg_rag": "C4: +Epistemic KG-RAG",
            "C5_full_system": "C5: Full System",
        }

    condition_order = [
        "C1_llm_alone", "C2_vanilla_rag", "C3_kg_rag",
        "C4_epistemic_kg_rag", "C5_full_system",
    ]

    # Compute stats
    stats: dict[str, dict] = {}
    for cond in condition_order:
        if cond not in condition_results:
            continue
        results = condition_results[cond]
        acc, ci_lo, ci_hi = bootstrap_ci(results, n_bootstrap=n_bootstrap)
        stats[cond] = {
            "accuracy": acc,
            "ci_lower": ci_lo,
            "ci_upper": ci_hi,
            "n": len(results),
        }

    # Pairwise McNemar vs baseline
    baseline_results = condition_results.get(baseline_condition, [])
    p_values_raw: list[float] = []
    p_value_map: dict[str, float] = {}

    for cond in condition_order:
        if cond == baseline_condition or cond not in condition_results:
            continue
        _, p = mcnemar_test(baseline_results, condition_results[cond])
        p_values_raw.append(p)
        p_value_map[cond] = p

    # Bonferroni correction
    corrected = bonferroni_correction(p_values_raw)
    corrected_map: dict[str, float] = {}
    idx = 0
    for cond in condition_order:
        if cond == baseline_condition or cond not in condition_results:
            continue
        corrected_map[cond] = corrected[idx]
        idx += 1

    # Cohen's d vs baseline
    d_map: dict[str, float] = {}
    for cond in condition_order:
        if cond == baseline_condition or cond not in condition_results:
            continue
        d_map[cond] = cohens_d(baseline_results, condition_results[cond])

    # Build LaTeX
    lines = [
        "\\begin{tabular}{lccccc}",
        "\\toprule",
        "\\textbf{Condition} & \\textbf{Accuracy} & \\textbf{95\\% CI} & "
        "\\textbf{$\\Delta$ vs C1} & \\textbf{$p$ (corrected)} & \\textbf{Cohen's $d$} \\\\",
        "\\midrule",
    ]

    for cond in condition_order:
        if cond not in stats:
            continue
        s = stats[cond]
        label = condition_labels.get(cond, cond)
        acc_str = f"{s['accuracy'] * 100:.1f}\\%"
        ci_str = f"[{s['ci_lower'] * 100:.1f}, {s['ci_upper'] * 100:.1f}]"

        if cond == baseline_condition:
            delta_str = "--"
            p_str = "--"
            d_str = "--"
        else:
            delta = s["accuracy"] - stats.get(baseline_condition, {}).get("accuracy", 0)
            delta_str = f"+{delta * 100:.1f}pp" if delta > 0 else f"{delta * 100:.1f}pp"
            p_val = corrected_map.get(cond, 1.0)
            if p_val < 0.001:
                p_str = "$<$0.001"
            elif p_val < 0.01:
                p_str = f"{p_val:.3f}"
            elif p_val < 0.05:
                p_str = f"{p_val:.3f}*"
            else:
                p_str = f"{p_val:.3f}"
            d_val = d_map.get(cond, 0.0)
            d_str = f"{d_val:.2f}"

        lines.append(f"{label} & {acc_str} & {ci_str} & {delta_str} & {p_str} & {d_str} \\\\")

    lines.extend([
        "\\bottomrule",
        "\\end{tabular}",
    ])

    return "\n".join(lines)


# ============================================================================
# Markdown results table with CIs
# ============================================================================


def markdown_results_table(
    condition_results: dict[str, list[bool | int]],
    condition_labels: dict[str, str] | None = None,
    baseline_condition: str = "C1_llm_alone",
    n_bootstrap: int = 10000,
) -> str:
    """Generate a Markdown table with accuracy, CIs, and p-values."""
    if condition_labels is None:
        condition_labels = {
            "C1_llm_alone": "C1: LLM Alone",
            "C2_vanilla_rag": "C2: +Vanilla RAG",
            "C3_kg_rag": "C3: +KG-RAG",
            "C4_epistemic_kg_rag": "C4: +Epistemic KG-RAG",
            "C5_full_system": "C5: Full System",
        }

    condition_order = [
        "C1_llm_alone", "C2_vanilla_rag", "C3_kg_rag",
        "C4_epistemic_kg_rag", "C5_full_system",
    ]

    baseline_results = condition_results.get(baseline_condition, [])

    lines = [
        "| Condition | Accuracy | 95% CI | Delta vs C1 | p-value | Cohen's d | N |",
        "|---|---|---|---|---|---|---|",
    ]

    for cond in condition_order:
        if cond not in condition_results:
            continue
        results = condition_results[cond]
        acc, ci_lo, ci_hi = bootstrap_ci(results, n_bootstrap=n_bootstrap)
        label = condition_labels.get(cond, cond)

        if cond == baseline_condition:
            lines.append(
                f"| {label} | {acc:.1%} | [{ci_lo:.1%}, {ci_hi:.1%}] | -- | -- | -- | {len(results)} |"
            )
        else:
            _, p = mcnemar_test(baseline_results, results)
            d = cohens_d(baseline_results, results)
            baseline_acc = sum(baseline_results) / len(baseline_results) if baseline_results else 0
            delta = acc - baseline_acc
            delta_str = f"+{delta:.1%}" if delta > 0 else f"{delta:.1%}"
            p_str = f"<0.001" if p < 0.001 else f"{p:.3f}"
            lines.append(
                f"| {label} | **{acc:.1%}** | [{ci_lo:.1%}, {ci_hi:.1%}] | {delta_str} | {p_str} | {d:.2f} | {len(results)} |"
            )

    return "\n".join(lines)


# ============================================================================
# Load checkpoint and extract per-condition binary results
# ============================================================================


def load_condition_results(checkpoint_path: str) -> dict[str, list[bool]]:
    """Load checkpoint JSONL and extract per-condition binary outcomes.

    Returns:
        Dict mapping condition -> list of bool (correct/incorrect per question).
    """
    condition_results: dict[str, list[bool]] = defaultdict(list)

    with open(checkpoint_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if entry.get("error"):
                continue  # Skip errored questions
            cond = entry.get("condition", "unknown")
            correct = bool(entry.get("correct", False))
            condition_results[cond].append(correct)

    return dict(condition_results)


# ============================================================================
# Per-category statistical breakdown
# ============================================================================


def per_category_stats(
    checkpoint_path: str,
    n_bootstrap: int = 10000,
) -> dict[str, dict[str, dict]]:
    """Compute per-category accuracy with CIs for each condition.

    Returns:
        Nested dict: {condition: {category: {accuracy, ci_lower, ci_upper, n}}}.
    """
    # Load data grouped by (condition, category)
    data: dict[str, dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))

    with open(checkpoint_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if entry.get("error"):
                continue
            cond = entry.get("condition", "unknown")
            cat = entry.get("category", "unknown")
            correct = bool(entry.get("correct", False))
            data[cond][cat].append(correct)

    result: dict[str, dict[str, dict]] = {}
    for cond, cats in data.items():
        result[cond] = {}
        for cat, scores in cats.items():
            acc, ci_lo, ci_hi = bootstrap_ci(scores, n_bootstrap=n_bootstrap)
            result[cond][cat] = {
                "accuracy": acc,
                "ci_lower": ci_lo,
                "ci_upper": ci_hi,
                "n": len(scores),
            }

    return result


# ============================================================================
# CLI entry point
# ============================================================================


def main():
    """Run statistical analysis on checkpoint file."""
    results_dir = Path("data/benchmarks/results")

    # Default checkpoint path
    checkpoint = str(results_dir / "clinicalbench_checkpoint.jsonl")
    if len(sys.argv) > 1:
        checkpoint = sys.argv[1]

    if not os.path.exists(checkpoint):
        print(f"Checkpoint not found: {checkpoint}")
        print("Usage: python scripts/statistical_analysis.py [checkpoint_path]")
        sys.exit(1)

    print("=" * 70)
    print("NeurIPS 2026 — Statistical Analysis")
    print("=" * 70)

    # Load results
    condition_results = load_condition_results(checkpoint)
    print(f"\nLoaded {sum(len(v) for v in condition_results.values())} results "
          f"across {len(condition_results)} conditions\n")

    # Per-condition accuracy with CIs
    print("## Accuracy with 95% Bootstrap CIs\n")
    for cond, results in sorted(condition_results.items()):
        acc, ci_lo, ci_hi = bootstrap_ci(results)
        print(f"  {cond}: {acc:.1%} [{ci_lo:.1%}, {ci_hi:.1%}] (n={len(results)})")

    # Pairwise McNemar tests
    baseline = "C1_llm_alone"
    if baseline in condition_results:
        print(f"\n## Pairwise McNemar Tests (vs {baseline})\n")
        p_values = []
        comparisons = []
        for cond in sorted(condition_results):
            if cond == baseline:
                continue
            chi2, p = mcnemar_test(condition_results[baseline], condition_results[cond])
            p_values.append(p)
            comparisons.append(cond)
            d = cohens_d(condition_results[baseline], condition_results[cond])
            print(f"  {cond}: chi2={chi2:.2f}, p={p:.4f}, Cohen's d={d:.2f}")

        # Bonferroni correction
        corrected = bonferroni_correction(p_values)
        print(f"\n## Bonferroni-Corrected p-values ({len(comparisons)} comparisons)\n")
        for cond, p_corr in zip(comparisons, corrected):
            sig = "*" if p_corr < 0.05 else ""
            print(f"  {cond}: p_corrected={p_corr:.4f} {sig}")

    # Markdown table
    print("\n## Results Table (Markdown)\n")
    print(markdown_results_table(condition_results))

    # LaTeX table
    print("\n## Results Table (LaTeX)\n")
    print(latex_results_table(condition_results))

    # Per-category breakdown
    print("\n## Per-Category Breakdown\n")
    cat_stats = per_category_stats(checkpoint)
    for cond in sorted(cat_stats):
        print(f"\n  {cond}:")
        for cat, s in sorted(cat_stats[cond].items()):
            print(
                f"    {cat}: {s['accuracy']:.1%} "
                f"[{s['ci_lower']:.1%}, {s['ci_upper']:.1%}] (n={s['n']})"
            )


if __name__ == "__main__":
    main()
