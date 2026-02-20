#!/usr/bin/env python3
"""Re-score ClinicalBench ablation results with the LLM judge.

Takes existing ablation JSON results (which contain predicted answers)
and re-evaluates using the LLM judge — avoids re-running the expensive
LLM inference, only runs the judge scoring calls.

Usage:
    cd backend
    uv run python scripts/rescore_with_judge.py

Options (via env vars):
    INPUT_PATH    Path to ablation JSON (default: data/benchmarks/results/clinicalbench_ablation.json)
    OUTPUT_PATH   Path for re-scored output (default: data/benchmarks/results/clinicalbench_judge_rescored.json)
    JUDGE_MODEL   Judge LLM model (default: claude-opus-4-6)
    CONDITION     Re-score only this condition (default: all)
    LIMIT         Limit questions per condition (default: all)
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
logger = logging.getLogger("rescore_judge")


async def main() -> None:
    logger.info("=" * 70)
    logger.info("Re-score with LLM Judge")
    logger.info("=" * 70)

    from app.services.llm_judge import LLMJudge

    input_path = os.environ.get("INPUT_PATH", "data/benchmarks/results/clinicalbench_ablation.json")
    output_path = os.environ.get("OUTPUT_PATH", "data/benchmarks/results/clinicalbench_judge_rescored.json")
    judge_model = os.environ.get("JUDGE_MODEL", "claude-sonnet-4-6")
    only_condition = os.environ.get("CONDITION", "")
    limit = int(os.environ.get("LIMIT", "0")) or None

    if not os.path.exists(input_path):
        logger.error("Input file not found: %s", input_path)
        return

    with open(input_path) as f:
        data = json.load(f)

    logger.info("Input: %s", input_path)
    logger.info("Judge model: %s", judge_model)
    logger.info("Conditions: %s", only_condition or "all")
    logger.info("Limit per condition: %s", limit or "all")
    logger.info("")

    judge = LLMJudge(model=judge_model)

    # Load original benchmark questions for category info
    benchmark_questions = _load_benchmark_questions()

    # Load checkpoint for resume
    checkpoint_path = output_path.replace(".json", "_checkpoint.jsonl")
    checkpoint: dict[str, dict] = {}  # key: f"{condition}:{question_id}"
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    entry = json.loads(line)
                    key = f"{entry.get('condition')}:{entry.get('question_id')}"
                    checkpoint[key] = entry
        logger.info("Resuming: %d questions already judged", len(checkpoint))

    rescored = {
        "source": input_path,
        "judge_model": judge_model,
        "llm_model": data.get("llm_model", "unknown"),
        "total_questions": data.get("total_questions", 0),
        "conditions": {},
    }

    t0 = time.perf_counter()

    for cid, cond_data in data.get("conditions", {}).items():
        if only_condition and cid != only_condition:
            continue

        label = cond_data.get("label", cid)
        per_question = cond_data.get("per_question", [])
        if limit:
            per_question = per_question[:limit]

        logger.info("--- Condition: %s (%s) — %d questions ---", cid, label, len(per_question))

        correct = 0
        total = 0
        category_correct: dict[str, int] = {}
        category_total: dict[str, int] = {}
        rescored_questions: list[dict] = []

        for i, r in enumerate(per_question):
            qid = r["question_id"]
            predicted = r.get("predicted_answer", "")
            expected = r.get("expected_answer", "")
            category = r.get("category", "")

            # Check checkpoint — skip if already judged
            ck_key = f"{cid}:{qid}"
            cached = checkpoint.get(ck_key)
            if cached and not cached.get("error"):
                is_correct = cached.get("correct_judge", False)
                score = cached.get("score_judge", 0.0)
                verdict = None  # We have the cached data
                rescored_questions.append(cached)
                total += 1
                if is_correct:
                    correct += 1
                category_total[category] = category_total.get(category, 0) + 1
                if is_correct:
                    category_correct[category] = category_correct.get(category, 0) + 1
                continue

            # Look up scoring rubric from benchmark questions
            bq = benchmark_questions.get(qid, {})
            scoring_rubric = bq.get("scoring_rubric", {})

            try:
                verdict = await judge.score(
                    question=bq.get("question", qid),
                    expected_answer=expected,
                    predicted_answer=predicted,
                    category=category,
                    scoring_rubric=scoring_rubric,
                )

                is_correct = verdict.overall_correct
                score = verdict.overall_score

            except Exception as exc:
                logger.warning("Judge failed for %s: %s", qid, exc)
                is_correct = False
                score = 0.0
                verdict = None

            total += 1
            if is_correct:
                correct += 1

            category_total[category] = category_total.get(category, 0) + 1
            if is_correct:
                category_correct[category] = category_correct.get(category, 0) + 1

            entry = {
                "condition": cid,
                "question_id": qid,
                "category": category,
                "correct_keyword": r.get("correct", False),
                "correct_judge": is_correct,
                "score_keyword": r.get("score", 0.0),
                "score_judge": score,
                "predicted_answer": predicted[:200],
                "expected_answer": expected[:200],
                "judge_reasoning": verdict.reasoning if verdict else "",
                "judge_scores": {
                    "factual_accuracy": verdict.factual_accuracy if verdict else 0,
                    "assertion_correctness": verdict.assertion_correctness if verdict else 0,
                    "temporal_correctness": verdict.temporal_correctness if verdict else 0,
                    "clinical_safety": verdict.clinical_safety if verdict else 0,
                },
            }
            rescored_questions.append(entry)

            # Save to checkpoint
            with open(checkpoint_path, "a") as ckf:
                ckf.write(json.dumps(entry, default=str) + "\n")

            if (i + 1) % 25 == 0:
                logger.info(
                    "  Progress: %d/%d (%.1f%% correct so far)",
                    i + 1, len(per_question), correct / total * 100 if total else 0,
                )

        accuracy = correct / total if total > 0 else 0.0
        category_accuracies = {
            cat: category_correct.get(cat, 0) / category_total[cat]
            for cat in category_total
        }

        rescored["conditions"][cid] = {
            "label": label,
            "accuracy_keyword": cond_data.get("accuracy", 0),
            "accuracy_judge": accuracy,
            "correct_judge": correct,
            "total": total,
            "category_accuracies_judge": category_accuracies,
            "category_accuracies_keyword": cond_data.get("category_accuracies", {}),
            "per_question": rescored_questions,
        }

        logger.info(
            "  %s: keyword=%.1f%%, judge=%.1f%% (%d/%d)",
            cid, cond_data.get("accuracy", 0) * 100, accuracy * 100, correct, total,
        )

    duration = time.perf_counter() - t0
    rescored["duration_s"] = duration

    # Summary table
    print("\n" + "=" * 70)
    print("KEYWORD vs JUDGE SCORING COMPARISON")
    print("=" * 70)
    print(f"\n| Condition | Keyword | Judge | Δ |")
    print("|---|---|---|---|")
    for cid, cond in rescored["conditions"].items():
        kw = cond["accuracy_keyword"]
        jg = cond["accuracy_judge"]
        delta = jg - kw
        print(f"| {cond['label']} | {kw:.1%} | {jg:.1%} | {delta:+.1%} |")

    # Per-category comparison
    print(f"\n--- Per-Category Judge Accuracy ---")
    all_cats = set()
    for cond in rescored["conditions"].values():
        all_cats.update(cond["category_accuracies_judge"].keys())

    for cat in sorted(all_cats):
        row = f"  {cat:<25}"
        for cid, cond in rescored["conditions"].items():
            acc = cond["category_accuracies_judge"].get(cat, 0)
            row += f" | {acc:.1%}"
        print(row)

    # Export
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(rescored, f, indent=2, default=str)
    logger.info("\nRe-scored results: %s", output_path)

    # Export judge audit log
    log_path = output_path.replace(".json", "_judge_log.json")
    with open(log_path, "w") as f:
        json.dump(judge.export_log_json(), f, indent=2, default=str)
    logger.info("Judge audit log: %s", log_path)

    logger.info("\n" + "=" * 70)
    logger.info("RE-SCORING COMPLETE (%.1fs)", duration)
    logger.info("=" * 70)


def _load_benchmark_questions() -> dict[str, dict]:
    """Load all benchmark questions by ID for rubric lookup."""
    questions: dict[str, dict] = {}
    for task in ["task_a", "task_b", "task_c", "task_d"]:
        path = f"data/benchmarks/{task}.json"
        if not os.path.exists(path):
            continue
        with open(path) as f:
            data = json.load(f)
        for q in data.get("questions", []):
            questions[q["question_id"]] = q
    return questions


if __name__ == "__main__":
    asyncio.run(main())
