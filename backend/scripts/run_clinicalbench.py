#!/usr/bin/env python3
"""Run ClinicalIntelligenceBench through the 5-condition ablation harness.

Loads the 600 gold-standard questions (Task A-D) and runs them through
all 5 ablation conditions, collecting accuracy and safety metrics.

Usage:
    cd backend
    uv run python scripts/run_clinicalbench.py

Options (via env vars):
    LLM_MODEL          LLM model (default: gemma3:27b)
    LLM_PROVIDER       Provider (default: ollama)
    OLLAMA_BASE_URL    Ollama URL (default: http://host.docker.internal:11434)
    QUESTION_LIMIT     Limit questions per task for testing (default: all)
    TASKS              Comma-separated tasks: a,b,c,d (default: all)
    CONDITIONS         Comma-separated condition IDs (default: all 5)
    USE_LLM_JUDGE      Use LLM judge scoring (default: 0)
    OUTPUT_DIR         Output directory (default: data/benchmarks/results)
"""

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
logger = logging.getLogger("run_clinicalbench")


def load_benchmark_questions(
    tasks: list[str],
    question_limit: int | None = None,
) -> tuple[list, dict[str, int]]:
    """Load benchmark questions from JSON files and convert to QAQuestion format.

    Returns (questions, task_counts) where task_counts maps task name to count.
    """
    from app.services.qa_evaluation import QAQuestion

    all_questions: list[QAQuestion] = []
    task_counts: dict[str, int] = {}

    task_files = {
        "a": "data/benchmarks/task_a.json",
        "b": "data/benchmarks/task_b.json",
        "c": "data/benchmarks/task_c.json",
        "d": "data/benchmarks/task_d.json",
    }

    for task_key in tasks:
        path = task_files.get(task_key)
        if not path or not os.path.exists(path):
            logger.warning("Task %s file not found: %s", task_key, path)
            continue

        with open(path) as f:
            data = json.load(f)

        questions_data = data.get("questions", [])
        if question_limit:
            questions_data = questions_data[:question_limit]

        count = 0
        for q in questions_data:
            patient_id = f"MIMIC-{q['mimic_subject_id']}"
            qa = QAQuestion(
                question_id=q["question_id"],
                question=q["question"],
                category=q["subtype"],
                expected_answer=q["expected_answer"],
                assertion_sensitive=q["task"].startswith("task_a"),
                temporal_sensitive=q["task"].startswith("task_b"),
                difficulty=q.get("difficulty", "medium"),
                clinical_context=q.get("clinical_context", ""),
                scoring_rubric=q.get("scoring_rubric", {}),
                metadata={
                    "task": q["task"],
                    "subtype": q["subtype"],
                    "patient_id": patient_id,
                    "mimic_subject_id": q["mimic_subject_id"],
                    "mimic_hadm_id": q.get("mimic_hadm_id"),
                    "benchmark": "ClinicalIntelligenceBench",
                    **(q.get("metadata", {})),
                },
            )
            all_questions.append(qa)
            count += 1

        task_counts[f"task_{task_key}"] = count
        logger.info("Loaded %d questions from task_%s", count, task_key)

    return all_questions, task_counts


def group_questions_by_patient(questions: list) -> dict[str, list]:
    """Group questions by patient_id for per-patient ablation runs."""
    groups: dict[str, list] = defaultdict(list)
    for q in questions:
        pid = q.metadata.get("patient_id", "unknown")
        groups[pid].append(q)
    return dict(groups)


async def main() -> None:
    t0_global = time.perf_counter()

    logger.info("=" * 70)
    logger.info("ClinicalIntelligenceBench — Full Ablation Experiment")
    logger.info("=" * 70)

    from app.services.ablation_harness import AblationHarness, AblationResult

    # Configuration from env
    llm_model = os.environ.get("LLM_MODEL", "gemma3:27b")
    llm_provider = os.environ.get("LLM_PROVIDER", "ollama")
    ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
    question_limit = int(os.environ.get("QUESTION_LIMIT", "0")) or None
    tasks_str = os.environ.get("TASKS", "a,b,c,d")
    tasks = [t.strip() for t in tasks_str.split(",") if t.strip()]
    conditions_str = os.environ.get("CONDITIONS", "")
    condition_ids = [c.strip() for c in conditions_str.split(",") if c.strip()] or None
    use_llm_judge = os.environ.get("USE_LLM_JUDGE", "0") == "1"
    output_dir = os.environ.get("OUTPUT_DIR", "data/benchmarks/results")

    logger.info("Model: %s (via %s)", llm_model, llm_provider)
    logger.info("Ollama URL: %s", ollama_url)
    logger.info("Tasks: %s", tasks)
    logger.info("Question limit per task: %s", question_limit or "all")
    logger.info("Conditions: %s", condition_ids or "all 5")
    logger.info("LLM judge: %s", use_llm_judge)
    logger.info("Output: %s", output_dir)
    logger.info("")

    # Load questions
    all_questions, task_counts = load_benchmark_questions(tasks, question_limit)
    if not all_questions:
        logger.error("No questions loaded. Check data/benchmarks/ directory.")
        return

    total_q = len(all_questions)
    logger.info("Total questions: %d", total_q)
    for task, count in task_counts.items():
        logger.info("  %s: %d", task, count)

    # Group by patient
    patient_groups = group_questions_by_patient(all_questions)
    logger.info("Unique patients: %d", len(patient_groups))
    logger.info("")

    # Strategy: Run all questions together with a representative patient.
    # The ablation harness retrieves context per-patient, but our benchmark
    # questions embed their own clinical_context, so the harness can use that.
    # For a more rigorous per-patient approach, we'd loop over patient groups.
    #
    # For now: single harness run with all questions, using the most common
    # patient as the primary context patient. Individual questions carry their
    # own context in the clinical_context field.
    primary_patient = max(patient_groups, key=lambda p: len(patient_groups[p]))
    logger.info(
        "Primary patient: %s (%d questions)",
        primary_patient, len(patient_groups[primary_patient]),
    )

    harness = AblationHarness()

    # Checkpoint path for resume support
    checkpoint_path = os.path.join(output_dir, "clinicalbench_checkpoint.jsonl")
    logger.info("Checkpoint: %s", checkpoint_path)

    # Run ablation (resumes from checkpoint if available)
    result = await harness.run(
        patient_id=primary_patient,
        questions=all_questions,
        question_set_name="ClinicalIntelligenceBench",
        llm_model=llm_model,
        llm_provider=llm_provider,
        use_llm_judge=use_llm_judge,
        condition_ids=condition_ids,
        ollama_base_url=ollama_url,
        checkpoint_path=checkpoint_path,
        output_dir=output_dir,
    )

    total_time = time.perf_counter() - t0_global

    # ================================================================
    # Results
    # ================================================================

    logger.info("")
    logger.info("=" * 70)
    logger.info("RESULTS")
    logger.info("=" * 70)

    # Main table
    print("\n" + result.to_markdown_table())

    # Deltas
    deltas = result.compute_deltas()
    print("\n--- Accuracy Deltas ---")
    for pair, delta in deltas.items():
        print(f"  {pair}: accuracy Δ={delta['accuracy_delta']:+.1%}, safety Δ={delta['safety_delta']:+.3f}")

    # Per-task breakdown
    print("\n--- Per-Task Accuracy by Condition ---")
    task_names = sorted(task_counts.keys())
    header = f"| {'Task':<20} | " + " | ".join(f"{cid}" for cid in result.conditions) + " |"
    print(header)
    print("|" + "-" * 22 + "|" + "|".join("-" * (len(cid) + 2) for cid in result.conditions) + "|")

    for task_name in task_names:
        row = f"| {task_name:<20} |"
        for cid, cr in result.conditions.items():
            # Filter results for this task
            task_results = [
                r for r in cr.report.results
                if any(
                    q.metadata.get("task", "").startswith(task_name)
                    for q in all_questions
                    if q.question_id == r.question_id
                )
            ]
            if task_results:
                correct = sum(1 for r in task_results if r.correct)
                acc = correct / len(task_results)
                row += f" {acc:.1%} ({correct}/{len(task_results)}) |"
            else:
                row += " N/A |"
        print(row)

    # Per-condition detail
    print("\n--- Per-Condition Summary ---")
    for cid, cr in result.conditions.items():
        print(f"\n  {cid} ({cr.condition_label}):")
        print(f"    Accuracy: {cr.report.accuracy:.1%} ({cr.report.correct}/{cr.report.total_questions})")
        print(f"    Safety: {cr.safety_score:.3f}")
        print(f"    Latency: {cr.latency_ms:.0f}ms")
        # Show category breakdown
        for cat, acc in sorted(cr.report.category_accuracies.items()):
            print(f"    {cat}: {acc:.1%}")

    # LaTeX table
    print("\n--- LaTeX Table ---")
    print(result.to_latex_table())

    # ================================================================
    # Export
    # ================================================================

    os.makedirs(output_dir, exist_ok=True)

    # Full JSON export
    json_path = os.path.join(output_dir, "clinicalbench_ablation.json")
    with open(json_path, "w") as f:
        json.dump(result.to_json(), f, indent=2, default=str)
    logger.info("\nFull results: %s", json_path)

    # Summary export
    summary = {
        "benchmark": "ClinicalIntelligenceBench",
        "llm_model": llm_model,
        "total_questions": total_q,
        "task_counts": task_counts,
        "total_duration_s": total_time,
        "conditions": {},
    }
    for cid, cr in result.conditions.items():
        summary["conditions"][cid] = {
            "label": cr.condition_label,
            "accuracy": cr.report.accuracy,
            "correct": cr.report.correct,
            "total": cr.report.total_questions,
            "safety": cr.safety_score,
            "category_accuracies": cr.report.category_accuracies,
        }
    summary_path = os.path.join(output_dir, "clinicalbench_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    logger.info("Summary: %s", summary_path)

    logger.info("\n" + "=" * 70)
    logger.info(
        "EXPERIMENT COMPLETE: %d questions × %d conditions in %.1fs (%.1f min)",
        total_q, len(result.conditions), total_time, total_time / 60,
    )
    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
