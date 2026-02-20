#!/usr/bin/env python3
"""Run MedQA-USMLE benchmark evaluation.

Downloads MedQA test set from HuggingFace if not present locally,
then evaluates with the specified LLM.

Usage:
    cd backend
    uv run python scripts/run_medqa.py

Options (via env vars):
    MEDQA_PATH          Path to MedQA test JSONL (default: data/benchmarks/medqa_test.jsonl)
    LLM_MODEL           LLM model (default: gemma3:27b)
    LLM_PROVIDER        Provider (default: ollama)
    OLLAMA_BASE_URL     Ollama URL (default: http://host.docker.internal:11434)
    QUESTION_LIMIT      Limit questions for testing (default: all)
    INCLUDE_ONTOLOGY    Run ontology-augmented condition too (default: 0)
    BATCH_SIZE          Progress log interval (default: 50)
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
logger = logging.getLogger("run_medqa")


def download_medqa(output_path: str) -> None:
    """Download MedQA test set from HuggingFace API."""
    import urllib.request

    logger.info("Downloading MedQA test set from HuggingFace...")

    # HuggingFace datasets API — get the test split as JSONL
    url = (
        "https://datasets-server.huggingface.co/rows?"
        "dataset=GBaker%2FMedQA-USMLE-4-options&config=default&split=test&offset=0&length=2000"
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Download in pages (API returns max 100 rows at a time)
    all_rows: list[dict] = []
    offset = 0
    page_size = 100

    while True:
        page_url = (
            "https://datasets-server.huggingface.co/rows?"
            f"dataset=GBaker%2FMedQA-USMLE-4-options&config=default&split=test"
            f"&offset={offset}&length={page_size}"
        )
        logger.info("  Fetching offset=%d...", offset)

        req = urllib.request.Request(page_url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())

        rows = data.get("rows", [])
        if not rows:
            break

        for row_wrapper in rows:
            row = row_wrapper.get("row", row_wrapper)
            all_rows.append(row)

        offset += len(rows)
        if len(rows) < page_size:
            break

    # Write as JSONL
    with open(output_path, "w") as f:
        for row in all_rows:
            f.write(json.dumps(row) + "\n")

    logger.info("Downloaded %d MedQA test questions to %s", len(all_rows), output_path)


async def main() -> None:
    logger.info("=" * 70)
    logger.info("MedQA-USMLE Benchmark Evaluation")
    logger.info("=" * 70)

    from app.services.medqa_evaluator import MedQAEvaluator

    # Configuration from env
    medqa_path = os.environ.get("MEDQA_PATH", "data/benchmarks/medqa_test.jsonl")
    llm_model = os.environ.get("LLM_MODEL", "gemma3:27b")
    llm_provider = os.environ.get("LLM_PROVIDER", "ollama")
    ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
    question_limit = int(os.environ.get("QUESTION_LIMIT", "0")) or None
    include_ontology = os.environ.get("INCLUDE_ONTOLOGY", "0") == "1"
    batch_size = int(os.environ.get("BATCH_SIZE", "50"))

    logger.info("Dataset: %s", medqa_path)
    logger.info("Model: %s (via %s)", llm_model, llm_provider)
    logger.info("Ollama URL: %s", ollama_url)
    logger.info("Question limit: %s", question_limit or "all")
    logger.info("Ontology condition: %s", include_ontology)
    logger.info("")

    # Download if not present
    if not os.path.exists(medqa_path):
        logger.info("MedQA test file not found locally, downloading...")
        try:
            download_medqa(medqa_path)
        except Exception as exc:
            logger.error("Failed to download MedQA: %s", exc)
            logger.error(
                "Please download manually from "
                "https://huggingface.co/datasets/GBaker/MedQA-USMLE-4-options"
            )
            return

    # Load evaluator
    evaluator = MedQAEvaluator()
    evaluator.load(medqa_path, split="test")
    logger.info("Loaded %d MedQA questions", evaluator.total_questions)

    # Show distribution
    step1 = sum(1 for q in evaluator._questions if q.metadata.get("exam_level") == "step1")
    step23 = sum(
        1 for q in evaluator._questions
        if q.metadata.get("exam_level") in ("step2&3", "step2_3")
    )
    logger.info("  Step 1: %d | Step 2&3: %d | Other: %d", step1, step23, len(evaluator._questions) - step1 - step23)

    # Checkpoint path for resume support
    checkpoint_path = os.environ.get(
        "CHECKPOINT_PATH",
        "data/benchmarks/results/medqa_checkpoint.jsonl",
    )
    os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
    logger.info("Checkpoint: %s", checkpoint_path)

    # Run evaluation (resumes from checkpoint if available)
    result = await evaluator.run(
        llm_model=llm_model,
        llm_provider=llm_provider,
        question_limit=question_limit,
        ollama_base_url=ollama_url,
        include_ontology_condition=include_ontology,
        batch_size=batch_size,
        checkpoint_path=checkpoint_path,
    )

    # Print results
    logger.info("")
    logger.info("=" * 70)
    logger.info("RESULTS")
    logger.info("=" * 70)
    print("\n" + result.to_markdown())

    # Export JSON
    output_path = "data/benchmarks/medqa_result.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result.to_json(), f, indent=2, default=str)
    logger.info("\nResults exported to %s", output_path)

    logger.info("\n" + "=" * 70)
    logger.info("EVALUATION COMPLETE (%.1fs)", result.duration_s)
    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
