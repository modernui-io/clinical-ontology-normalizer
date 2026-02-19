#!/usr/bin/env python3
"""Run EHRNoteQA benchmark through the 5-condition ablation harness.

Requires:
  - EHRNoteQA.jsonl from PhysioNet (credentialed access)
  - MIMIC patients ingested into our database

Usage:
    cd backend
    uv run python scripts/run_ehrnoteqa.py

Options (via env vars):
    EHRNOTEQA_PATH     Path to EHRNoteQA.jsonl (default: data/benchmarks/EHRNoteQA.jsonl)
    LLM_MODEL          LLM model (default: gemma3:27b)
    LLM_PROVIDER       Provider (default: ollama)
    OLLAMA_BASE_URL    Ollama URL (default: http://host.docker.internal:11434)
    QUESTION_LIMIT     Limit questions for testing (default: all)
    CONDITIONS         Comma-separated condition IDs (default: all 5)
"""

import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("run_ehrnoteqa")


async def main() -> None:
    logger.info("=" * 70)
    logger.info("EHRNoteQA Benchmark Evaluation")
    logger.info("=" * 70)

    from sqlalchemy.orm import Session

    from app.core.database import get_sync_engine
    from app.services.ehrnoteqa_evaluator import EHRNoteQAEvaluator

    # Configuration from env
    ehrnoteqa_path = os.environ.get("EHRNOTEQA_PATH", "data/benchmarks/EHRNoteQA.jsonl")
    llm_model = os.environ.get("LLM_MODEL", "gemma3:27b")
    llm_provider = os.environ.get("LLM_PROVIDER", "ollama")
    ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
    question_limit = int(os.environ.get("QUESTION_LIMIT", "0")) or None
    conditions_str = os.environ.get("CONDITIONS", "")
    condition_ids = [c.strip() for c in conditions_str.split(",") if c.strip()] or None

    logger.info("Dataset: %s", ehrnoteqa_path)
    logger.info("Model: %s (via %s)", llm_model, llm_provider)
    logger.info("Ollama URL: %s", ollama_url)
    logger.info("Question limit: %s", question_limit or "all")
    logger.info("Conditions: %s", condition_ids or "all 5")
    logger.info("")

    # Load evaluator
    evaluator = EHRNoteQAEvaluator()
    evaluator.load(ehrnoteqa_path)
    logger.info("Loaded %d EHRNoteQA questions", evaluator.total_questions)

    # Check patient coverage
    engine = get_sync_engine()
    with Session(engine) as session:
        coverage = evaluator.check_patient_coverage(session)
        logger.info(
            "Patient coverage: %d/%d (%.1f%%)",
            coverage["available"], coverage["required"],
            coverage["coverage"] * 100,
        )
        if coverage["missing"]:
            logger.info("Missing patients: %d", len(coverage["missing"]))

        # Filter to available patients
        patient_filter = set(coverage["available_ids"]) if coverage["available_ids"] else None

    if not patient_filter:
        logger.error("No EHRNoteQA patients found in database. Ingest MIMIC data first.")
        return

    # Run evaluation
    result = await evaluator.run(
        llm_model=llm_model,
        llm_provider=llm_provider,
        question_limit=question_limit,
        ollama_base_url=ollama_url,
        condition_ids=condition_ids,
        patient_filter=patient_filter,
    )

    # Print results
    logger.info("")
    logger.info("=" * 70)
    logger.info("RESULTS")
    logger.info("=" * 70)
    print("\n" + result.to_markdown())

    # Per-condition MCQ accuracy
    print("\n--- MCQ Accuracy per Condition ---")
    for cid, acc in result.condition_accuracies.items():
        correct = result.condition_correct.get(cid, 0)
        print(f"  {cid}: {acc:.1%} ({correct}/{result.evaluated_questions})")

    # Export JSON
    output_path = "data/benchmarks/ehrnoteqa_result.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    export_data = {
        "benchmark": "EHRNoteQA",
        "total_questions": result.total_questions,
        "evaluated_questions": result.evaluated_questions,
        "skipped_patients": result.skipped_patients,
        "condition_accuracies": result.condition_accuracies,
        "condition_correct": result.condition_correct,
        "duration_s": result.duration_s,
    }
    if result.ablation_result:
        export_data["ablation"] = result.ablation_result.to_json()
    with open(output_path, "w") as f:
        json.dump(export_data, f, indent=2, default=str)
    logger.info("\nResults exported to %s", output_path)

    logger.info("\n" + "=" * 70)
    logger.info("EVALUATION COMPLETE (%.1fs)", result.duration_s)
    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
