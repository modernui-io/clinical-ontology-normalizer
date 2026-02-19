#!/usr/bin/env python3
"""Smoke test for the 5-condition ablation harness.

Runs 5 questions through all 5 conditions using a local Ollama model
(free, no API key needed) to verify the harness mechanics work.

Usage:
    cd backend
    uv run python scripts/smoke_test_ablation.py
"""

import asyncio
import json
import logging
import os
import sys

# Ensure the backend app is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("smoke_test")


async def main() -> None:
    logger.info("=" * 70)
    logger.info("ABLATION HARNESS SMOKE TEST")
    logger.info("=" * 70)

    from app.services.ablation_harness import AblationHarness
    from app.services.qa_evaluation import ASSERTION_QUESTIONS

    harness = AblationHarness()

    # Use first 5 assertion questions
    questions = ASSERTION_QUESTIONS[:5]
    logger.info("Questions: %d", len(questions))
    for q in questions:
        logger.info("  %s [%s]: %s", q.question_id, q.category, q.question[:60])

    # Patient with both documents and KG data
    patient_id = "LABS_VITALS_TEST"

    # Use local Ollama model (free, fast)
    llm_model = "gemma3:27b"
    llm_provider = "ollama"

    # Detect Docker environment and adjust Ollama URL
    ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434")

    logger.info("\nPatient: %s", patient_id)
    logger.info("Model: %s (via %s)", llm_model, llm_provider)
    logger.info("Ollama URL: %s", ollama_url)
    logger.info("Conditions: 5 (C1 → C5)")
    logger.info("")

    result = await harness.run(
        patient_id=patient_id,
        questions=questions,
        question_set_name="smoke_test_5",
        llm_model=llm_model,
        llm_provider=llm_provider,
        use_llm_judge=False,  # Use keyword scoring for speed
        ollama_base_url=ollama_url,
    )

    # Print results
    logger.info("\n" + "=" * 70)
    logger.info("RESULTS")
    logger.info("=" * 70)

    print("\n" + result.to_markdown_table())

    # Print deltas
    deltas = result.compute_deltas()
    print("\n--- Accuracy Deltas ---")
    for pair, delta in deltas.items():
        print(f"  {pair}: accuracy Δ={delta['accuracy_delta']:+.1%}, safety Δ={delta['safety_delta']:+.3f}")

    # Print per-condition detail
    print("\n--- Per-Condition Detail ---")
    for cid, cr in result.conditions.items():
        print(f"\n  {cid} ({cr.condition_label}):")
        print(f"    Accuracy: {cr.report.accuracy:.1%} ({cr.report.correct}/{cr.report.total_questions})")
        print(f"    Safety: {cr.safety_score:.3f}")
        print(f"    Latency: {cr.latency_ms:.0f}ms")
        for r in cr.report.results:
            status = "✓" if r.correct else "✗"
            answer_preview = r.predicted_answer[:80].replace("\n", " ") if r.predicted_answer else "(empty)"
            print(f"    {status} {r.question_id}: {answer_preview}")

    # Export JSON
    json_result = result.to_json()
    output_path = "data/benchmarks/smoke_test_result.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(json_result, f, indent=2, default=str)
    logger.info("\nResults exported to %s", output_path)

    # Print LaTeX table
    print("\n--- LaTeX Table ---")
    print(result.to_latex_table())

    logger.info("\n" + "=" * 70)
    logger.info("SMOKE TEST COMPLETE (%.1fs total)", result.total_duration_s)
    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
