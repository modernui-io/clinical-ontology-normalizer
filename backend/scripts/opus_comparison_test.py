#!/usr/bin/env python3
"""Targeted Opus vs MedGemma comparison on weak-category questions.

Runs 30 specific questions (5 per category: change, current_state, historical,
duration, uncertainty, family_history) through C4g with both models.

Usage:
    cd backend
    # Opus only (MedGemma results already exist from v2 run):
    python scripts/opus_comparison_test.py --provider anthropic
    # MedGemma re-run with fixed code:
    python scripts/opus_comparison_test.py --provider ollama --ollama-url http://host.docker.internal:11434
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
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("app.services.nlp_entity").setLevel(logging.WARNING)
logging.getLogger("app.services.section_parser").setLevel(logging.WARNING)
logger = logging.getLogger("opus_compare")


def load_targeted_questions(qid_file: str | None = None) -> list:
    """Load pre-selected questions from a question ID file."""
    from app.services.qa_evaluation import QAQuestion

    # Load question IDs
    qid_path = qid_file or "data/benchmarks/results/opus_test_qids.json"
    if not os.path.exists(qid_path):
        logger.error("No question IDs file at %s", qid_path)
        return []
    with open(qid_path) as f:
        target_qids = set(json.load(f))

    # Load all benchmark questions
    all_qs = {}
    for task_file in ["data/benchmarks/task_a.json", "data/benchmarks/task_b.json"]:
        if not os.path.exists(task_file):
            continue
        with open(task_file) as f:
            data = json.load(f)
        for q in data["questions"]:
            all_qs[q["question_id"]] = q

    # Build QAQuestion objects for selected IDs
    questions = []
    for qid in sorted(target_qids):
        q = all_qs.get(qid)
        if not q:
            logger.warning("Question %s not found in benchmark files", qid)
            continue
        patient_id = f"MIMIC-{q['mimic_subject_id']}"
        subtype = q.get("subtype", "unknown")
        task = q.get("task", "unknown")
        questions.append(QAQuestion(
            question_id=q["question_id"],
            question=q["question"],
            category=subtype,
            expected_answer=q["expected_answer"],
            temporal_sensitive=(task == "task_b"),
            assertion_sensitive=(task == "task_a"),
            metadata={
                "task": task,
                "subtype": subtype,
                "patient_id": patient_id,
                "mimic_subject_id": q["mimic_subject_id"],
                "mimic_hadm_id": q.get("mimic_hadm_id"),
                **(q.get("metadata", {})),
            },
        ))

    return questions


async def main() -> None:
    parser = argparse.ArgumentParser(description="Opus vs MedGemma comparison")
    parser.add_argument("--provider", default="anthropic", choices=["ollama", "anthropic"])
    parser.add_argument("--model", default=None)
    parser.add_argument("--ollama-url", default="http://host.docker.internal:11434")
    parser.add_argument("--qids-file", default=None, help="Path to JSON file with question IDs")
    parser.add_argument("--condition", default="C4g_intent_aware", help="Condition ID to run")
    args = parser.parse_args()

    model = args.model
    if model is None:
        model = "gemma3:27b" if args.provider == "ollama" else "claude-opus-4-20250514"

    logger.info("=" * 70)
    logger.info("Opus Comparison Test — 30 Targeted Questions")
    logger.info("Model: %s (via %s)", model, args.provider)
    logger.info("=" * 70)

    questions = load_targeted_questions(qid_file=args.qids_file)
    if not questions:
        logger.error("No questions loaded.")
        return

    by_cat = defaultdict(list)
    for q in questions:
        by_cat[q.category].append(q)
    for cat, qs in sorted(by_cat.items()):
        logger.info("  %s: %d questions", cat, len(qs))

    from app.services.ablation_harness import AblationHarness
    from collections import Counter

    harness = AblationHarness()
    patient_counts = Counter(q.metadata.get("patient_id", "unknown") for q in questions)
    primary_patient = patient_counts.most_common(1)[0][0]

    model_label = "opus" if "opus" in model.lower() or "claude" in model.lower() else "medgemma"
    condition_suffix = f"_{args.condition}" if args.condition != "C4g_intent_aware" else ""
    output_dir = f"data/benchmarks/results/opus_compare"
    os.makedirs(output_dir, exist_ok=True)
    checkpoint_path = os.path.join(output_dir, f"compare_{model_label}{condition_suffix}_checkpoint.jsonl")

    t0 = time.perf_counter()

    result = await harness.run(
        patient_id=primary_patient,
        questions=questions,
        question_set_name=f"opus_compare_{model_label}",
        llm_model=model,
        llm_provider=args.provider,
        use_llm_judge=False,
        condition_ids=[args.condition],
        ollama_base_url=args.ollama_url,
        checkpoint_path=checkpoint_path,
        output_dir=output_dir,
    )

    elapsed = time.perf_counter() - t0

    # Results
    print("\n" + "=" * 70)
    print(f"RESULTS — {model_label.upper()} on 30 Targeted Questions")
    print("=" * 70)
    print(f"Model: {model} | Duration: {elapsed:.1f}s")

    c4g = result.conditions.get(args.condition)
    if c4g:
        n_total = len(questions)
        n_correct = sum(1 for q in c4g.report.per_question.values() if q.get("correct"))
        print(f"\nOverall C4g: {c4g.report.accuracy:.1%} ({n_correct}/{n_total})")
        print(f"\n{'Category':<18} {'Score':>8} {'Detail':>12}")
        print("-" * 42)
        for cat in sorted(c4g.report.category_accuracies.keys()):
            acc = c4g.report.category_accuracies[cat]
            n_cat = len([q for q in questions if q.category == cat])
            n_correct = round(acc * n_cat)
            print(f"{cat:<18} {acc:>7.0%} ({n_correct}/{n_cat})")

        # Save per-question details
        output_path = os.path.join(output_dir, f"compare_{model_label}_result.json")
        with open(output_path, "w") as f:
            json.dump({
                "model": model,
                "provider": args.provider,
                "n_questions": len(questions),
                "duration_s": elapsed,
                "accuracy": c4g.report.accuracy,
                "category_scores": c4g.report.category_accuracies,
                "per_question": c4g.report.per_question,
            }, f, indent=2, default=str)
        logger.info("Saved to %s", output_path)
    else:
        print("ERROR: No C4g results")


if __name__ == "__main__":
    asyncio.run(main())
