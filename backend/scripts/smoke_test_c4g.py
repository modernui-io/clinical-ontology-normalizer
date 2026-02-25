#!/usr/bin/env python3
"""Smoke test for C4g intent-aware retrieval vs C4 baseline.

Runs 5 questions per weak category (change, current_state, historical)
+ 5 from a strong category (negation) as a regression check.
Total: 20 questions × 2 conditions = 40 LLM calls.

Usage:
    cd backend
    python scripts/smoke_test_c4g.py [--provider ollama|anthropic] [--model MODEL]
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
# Quiet down noisy loggers
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("app.services.nlp_entity").setLevel(logging.WARNING)
logging.getLogger("app.services.section_parser").setLevel(logging.WARNING)
logger = logging.getLogger("smoke_c4g")


def load_smoke_questions(n_per_category: int = 5) -> list:
    """Load a small balanced subset: 5 per weak category + 5 negation (strong baseline)."""
    from app.services.qa_evaluation import QAQuestion

    questions: list[QAQuestion] = []

    # Task B: temporal categories (change, current_state, historical)
    task_b_path = "data/benchmarks/task_b.json"
    if os.path.exists(task_b_path):
        with open(task_b_path) as f:
            data = json.load(f)
        by_subtype: dict[str, list] = defaultdict(list)
        for q in data["questions"]:
            by_subtype[q["subtype"]].append(q)
        for subtype in ["change", "current_state", "historical"]:
            for q in by_subtype[subtype][:n_per_category]:
                patient_id = f"MIMIC-{q['mimic_subject_id']}"
                questions.append(QAQuestion(
                    question_id=q["question_id"],
                    question=q["question"],
                    category=q["subtype"],
                    expected_answer=q["expected_answer"],
                    temporal_sensitive=True,
                    metadata={
                        "task": q["task"],
                        "subtype": q["subtype"],
                        "patient_id": patient_id,
                        "mimic_subject_id": q["mimic_subject_id"],
                        "mimic_hadm_id": q.get("mimic_hadm_id"),
                        **(q.get("metadata", {})),
                    },
                ))

    # Task A: negation (strong category — regression check)
    task_a_path = "data/benchmarks/task_a.json"
    if os.path.exists(task_a_path):
        with open(task_a_path) as f:
            data = json.load(f)
        negation_qs = [q for q in data["questions"] if q["subtype"] == "negation"]
        for q in negation_qs[:n_per_category]:
            patient_id = f"MIMIC-{q['mimic_subject_id']}"
            questions.append(QAQuestion(
                question_id=q["question_id"],
                question=q["question"],
                category=q["subtype"],
                expected_answer=q["expected_answer"],
                assertion_sensitive=True,
                metadata={
                    "task": q["task"],
                    "subtype": q["subtype"],
                    "patient_id": patient_id,
                    "mimic_subject_id": q["mimic_subject_id"],
                    "mimic_hadm_id": q.get("mimic_hadm_id"),
                    **(q.get("metadata", {})),
                },
            ))

    return questions


async def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test C4g vs C4")
    parser.add_argument("--provider", default="ollama", choices=["ollama", "anthropic"])
    parser.add_argument("--model", default=None)
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--n-per-category", type=int, default=5)
    args = parser.parse_args()

    model = args.model
    if model is None:
        model = "gemma3:27b" if args.provider == "ollama" else "claude-sonnet-4-5-20250929"

    logger.info("=" * 70)
    logger.info("C4g Intent-Aware Smoke Test")
    logger.info("Model: %s (via %s)", model, args.provider)
    logger.info("=" * 70)

    questions = load_smoke_questions(args.n_per_category)
    if not questions:
        logger.error("No questions loaded. Check data/benchmarks/ directory.")
        return

    by_cat = defaultdict(list)
    for q in questions:
        by_cat[q.category].append(q)
    for cat, qs in sorted(by_cat.items()):
        logger.info("  %s: %d questions", cat, len(qs))

    from app.services.ablation_harness import AblationHarness

    harness = AblationHarness()

    # Find the most common patient for primary context
    from collections import Counter
    patient_counts = Counter(q.metadata.get("patient_id", "unknown") for q in questions)
    primary_patient = patient_counts.most_common(1)[0][0]

    output_dir = "data/benchmarks/results/c4g_smoke"
    os.makedirs(output_dir, exist_ok=True)
    checkpoint_path = os.path.join(output_dir, "c4g_smoke_checkpoint.jsonl")

    t0 = time.perf_counter()

    # Run both C4 (baseline) and C4g (intent-aware) on the same questions
    result = await harness.run(
        patient_id=primary_patient,
        questions=questions,
        question_set_name="C4g_smoke_test",
        llm_model=model,
        llm_provider=args.provider,
        use_llm_judge=False,
        condition_ids=["C4_epistemic_kg_rag", "C4g_intent_aware"],
        ollama_base_url=args.ollama_url,
        checkpoint_path=checkpoint_path,
        output_dir=output_dir,
    )

    elapsed = time.perf_counter() - t0

    # ================================================================
    # Results
    # ================================================================
    print("\n" + "=" * 70)
    print("RESULTS — C4g Smoke Test")
    print("=" * 70)
    print(f"\nModel: {model} | Provider: {args.provider}")
    print(f"Questions: {len(questions)} | Duration: {elapsed:.1f}s")

    # Main table
    print("\n" + result.to_markdown_table())

    # Per-category breakdown (the key comparison)
    print("\n--- Per-Category Accuracy: C4 vs C4g ---")
    print(f"| {'Category':<16} | {'C4':>8} | {'C4g':>8} | {'Delta':>8} |")
    print(f"|{'-'*18}|{'-'*10}|{'-'*10}|{'-'*10}|")

    for cond_id in ["C4_epistemic_kg_rag", "C4g_intent_aware"]:
        if cond_id not in result.conditions:
            logger.warning("Condition %s not in results", cond_id)

    c4_results = result.conditions.get("C4_epistemic_kg_rag")
    c4g_results = result.conditions.get("C4g_intent_aware")

    if c4_results and c4g_results:
        c4_by_cat = c4_results.report.category_accuracies
        c4g_by_cat = c4g_results.report.category_accuracies

        target_cats = ["change", "current_state", "historical", "negation"]
        for cat in target_cats:
            c4_acc = c4_by_cat.get(cat, 0)
            c4g_acc = c4g_by_cat.get(cat, 0)
            delta = c4g_acc - c4_acc
            marker = "***" if delta > 0.05 else ("!!!" if delta < -0.03 else "")
            print(f"| {cat:<16} | {c4_acc:>7.1%} | {c4g_acc:>7.1%} | {delta:>+7.1%} | {marker}")

        # Overall
        c4_overall = c4_results.report.accuracy
        c4g_overall = c4g_results.report.accuracy
        delta_overall = c4g_overall - c4_overall
        print(f"| {'OVERALL':<16} | {c4_overall:>7.1%} | {c4g_overall:>7.1%} | {delta_overall:>+7.1%} |")

    # Gate check
    print("\n--- Gate Criteria ---")
    if c4_results and c4g_results:
        c4_by_cat = c4_results.report.category_accuracies
        c4g_by_cat = c4g_results.report.category_accuracies

        gates_passed = True
        # Weak categories: each must improve by >=+5pp
        for cat in ["change", "current_state", "historical"]:
            c4_acc = c4_by_cat.get(cat, 0)
            c4g_acc = c4g_by_cat.get(cat, 0)
            delta = c4g_acc - c4_acc
            passed = delta >= 0.05
            gates_passed = gates_passed and passed
            status = "PASS" if passed else "FAIL"
            print(f"  {cat}: {delta:+.1%} (need >=+5pp) [{status}]")

        # Strong category: no worse than -3pp
        for cat in ["negation"]:
            c4_acc = c4_by_cat.get(cat, 0)
            c4g_acc = c4g_by_cat.get(cat, 0)
            delta = c4g_acc - c4_acc
            passed = delta >= -0.03
            gates_passed = gates_passed and passed
            status = "PASS" if passed else "FAIL"
            print(f"  {cat}: {delta:+.1%} (need >=-3pp) [{status}]")

        print(f"\n  Overall gate: {'PASS' if gates_passed else 'FAIL'}")
    else:
        print("  Could not compute gates — missing condition results.")

    # Save full results
    output_path = os.path.join(output_dir, "c4g_smoke_result.json")
    with open(output_path, "w") as f:
        json.dump({
            "model": model,
            "provider": args.provider,
            "n_questions": len(questions),
            "duration_s": elapsed,
            "conditions": {
                cid: {
                    "accuracy": cr.report.accuracy,
                    "category_scores": cr.report.category_accuracies,
                }
                for cid, cr in result.conditions.items()
            },
        }, f, indent=2, default=str)
    logger.info("Results saved to %s", output_path)


if __name__ == "__main__":
    asyncio.run(main())
