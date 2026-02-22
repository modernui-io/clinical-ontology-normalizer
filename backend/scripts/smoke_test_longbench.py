#!/usr/bin/env python3
"""Smoke test for the Longitudinal Clinical Benchmark harness.

Tests the full pipeline end-to-end with a small cohort:
1. Cohort selection (or synthetic fallback if DB is empty)
2. Question generation (template-based for speed)
3. Run 2 conditions (B0 + B3) on 2 questions
4. LLM-judge scoring
5. Analysis + markdown output

Usage:
    cd backend
    python scripts/smoke_test_longbench.py [--provider anthropic|ollama] [--model MODEL]
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time

# Ensure the backend app is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("smoke_test_longbench")


def _build_synthetic_cohort():
    """Build a minimal synthetic cohort when no DB patients are available."""
    from app.services.longbench_schemas import (
        CriterionType,
        CriterionWeight,
        LongBenchCohort,
        LongBenchCriterion,
        LongBenchQuestion,
        LongitudinalTier,
        PatientCohortEntry,
        QuestionDomain,
    )

    patients = [
        PatientCohortEntry(
            patient_id="MIMIC-10000935",
            tier=LongitudinalTier.A,
            encounter_count=2,
            total_note_length=3000,
            has_family_history=True,
        ),
        PatientCohortEntry(
            patient_id="MIMIC-10000935",
            tier=LongitudinalTier.C,
            encounter_count=2,  # Same patient, testing tier C path
            total_note_length=3000,
            has_family_history=True,
        ),
    ]

    questions = [
        LongBenchQuestion(
            question_id="smoke_q1",
            patient_id="MIMIC-10000935",
            question_text="What are this patient's active medical conditions?",
            domain=QuestionDomain.PROBLEM_LIST,
            tier=LongitudinalTier.A,
            criteria=[
                LongBenchCriterion(
                    criterion_id="smoke_q1_c0",
                    text="Lists at least one documented condition from the clinical record",
                    criterion_type=CriterionType.SYNTHESIS,
                    weight=CriterionWeight.CRITICAL,
                ),
                LongBenchCriterion(
                    criterion_id="smoke_q1_c1",
                    text="Does not fabricate conditions not present in the evidence",
                    criterion_type=CriterionType.ASSERTION,
                    weight=CriterionWeight.CRITICAL,
                ),
                LongBenchCriterion(
                    criterion_id="smoke_q1_c2",
                    text="Distinguishes active from resolved conditions",
                    criterion_type=CriterionType.CHRONOLOGY,
                    weight=CriterionWeight.IMPORTANT,
                ),
            ],
            encounter_count=2,
            generated_by="smoke_test",
        ),
        LongBenchQuestion(
            question_id="smoke_q2",
            patient_id="MIMIC-10000935",
            question_text="Is there any family history documented, and if so, does it belong to a family member or the patient?",
            domain=QuestionDomain.FAMILY_HISTORY,
            tier=LongitudinalTier.A,
            criteria=[
                LongBenchCriterion(
                    criterion_id="smoke_q2_c0",
                    text="Correctly identifies family history entries if present",
                    criterion_type=CriterionType.EXPERIENCER,
                    weight=CriterionWeight.CRITICAL,
                ),
                LongBenchCriterion(
                    criterion_id="smoke_q2_c1",
                    text="Does not attribute family history conditions to the patient",
                    criterion_type=CriterionType.EXPERIENCER,
                    weight=CriterionWeight.CRITICAL,
                ),
                LongBenchCriterion(
                    criterion_id="smoke_q2_c2",
                    text="Provides clinically relevant context about the family history",
                    criterion_type=CriterionType.SYNTHESIS,
                    weight=CriterionWeight.NICE,
                ),
            ],
            encounter_count=2,
            generated_by="smoke_test",
        ),
    ]

    return LongBenchCohort(
        cohort_id="smoke_test",
        patients=patients,
        questions=questions,
        version="1.0.0",
        metadata={"type": "smoke_test"},
    )


def _try_db_cohort():
    """Attempt to select a real cohort from the database."""
    try:
        from app.core.database import get_sync_engine
        from sqlalchemy.orm import Session
        from app.services.longbench_cohort import LongBenchCohortSelector

        engine = get_sync_engine()
        session = Session(engine)
        selector = LongBenchCohortSelector(session)

        # Try small cohort: 2 patients per tier
        cohort = selector.select_cohort(
            tier_sizes={"A": 2, "B": 2, "C": 2},
            min_note_chars=200,
        )
        session.close()

        if cohort.patients:
            logger.info("Selected %d patients from database", len(cohort.patients))
            return cohort, True
        else:
            logger.info("No patients found in database, using synthetic cohort")
            return None, False
    except Exception as exc:
        logger.info("Database not available (%s), using synthetic cohort", exc)
        return None, False


async def main(provider: str, model: str) -> None:
    t0 = time.perf_counter()
    logger.info("=" * 70)
    logger.info("LONGITUDINAL BENCHMARK SMOKE TEST")
    logger.info("=" * 70)
    logger.info("Provider: %s | Model: %s", provider, model)

    from app.services.longbench_schemas import ConditionID
    from app.services.longbench_runner import (
        LongBenchAnalyzer,
        LongBenchRunConfig,
        LongBenchRunner,
    )
    from app.services.longbench_cohort import cohort_to_json

    # Step 1: Get cohort
    logger.info("\n--- Step 1: Cohort Selection ---")
    db_cohort, has_db = _try_db_cohort()

    if has_db and db_cohort and db_cohort.patients:
        cohort = db_cohort
        # Generate template questions for smoke test (skip LLM generation)
        from app.services.longbench_cohort import LongBenchQuestionGenerator
        gen = LongBenchQuestionGenerator()
        for patient in cohort.patients[:2]:  # Limit to 2 patients
            questions = gen._fallback_template_questions(patient, n=2)
            cohort.questions.extend(questions)
        cohort.patients = cohort.patients[:2]
    else:
        cohort = _build_synthetic_cohort()

    logger.info("Cohort: %d patients, %d questions", len(cohort.patients), len(cohort.questions))
    logger.info("Tier summary: %s", cohort.tier_summary)
    for q in cohort.questions:
        logger.info("  %s [%s, tier=%s]: %s", q.question_id, q.domain.value, q.tier.value, q.question_text[:60])

    # Step 2: Configure run
    logger.info("\n--- Step 2: Run Configuration ---")
    conditions = [ConditionID.B0, ConditionID.B3]  # Just 2 conditions for smoke test
    logger.info("Conditions: %s", [c.value for c in conditions])

    config = LongBenchRunConfig(
        llm_model=model,
        llm_provider=provider,
        judge_model=model,
        judge_provider=provider,
        checkpoint_dir="data/benchmarks/results/longbench_smoke",
    )

    # Step 3: Run
    logger.info("\n--- Step 3: Running Benchmark ---")

    session = None
    if has_db:
        from app.core.database import get_sync_engine
        from sqlalchemy.orm import Session
        engine = get_sync_engine()
        session = Session(engine)

    runner = LongBenchRunner(session)
    report = await runner.run(cohort, config=config, conditions=conditions)

    if session:
        session.close()

    # Step 4: Analysis
    logger.info("\n--- Step 4: Analysis ---")
    logger.info("Total results: %d", len(report.results))

    # Print condition x tier table
    table = LongBenchAnalyzer.to_markdown_table(report.condition_tier_scores)
    print("\n--- Condition x Tier Scores ---")
    print(table)

    # Print criterion type breakdown
    ct_table = LongBenchAnalyzer.to_criterion_type_table(report.condition_tier_scores)
    print("\n--- Criterion Type Breakdown ---")
    print(ct_table)

    # Print per-result detail
    print("\n--- Per-Result Detail ---")
    for r in report.results:
        status = f"{r.normalized_score:.0%}" if not r.error else "ERR"
        answer_preview = r.predicted_answer[:80].replace("\n", " ") if r.predicted_answer else "(empty)"
        print(f"  [{status}] {r.condition.value} | {r.question_id} | {answer_preview}")
        if r.criterion_results:
            for cr in r.criterion_results:
                mark = "+" if cr.satisfied else "-"
                print(f"    {mark} {cr.criterion_id}: {cr.reasoning[:60]}")

    # Step 5: Export
    output_dir = "data/benchmarks/results/longbench_smoke"
    os.makedirs(output_dir, exist_ok=True)

    report_path = os.path.join(output_dir, "smoke_report.json")
    with open(report_path, "w") as f:
        json.dump(LongBenchAnalyzer.report_to_json(report), f, indent=2, default=str)

    cohort_path = os.path.join(output_dir, "smoke_cohort.json")
    with open(cohort_path, "w") as f:
        json.dump(cohort_to_json(cohort), f, indent=2, default=str)

    elapsed = time.perf_counter() - t0
    logger.info("\n" + "=" * 70)
    logger.info("SMOKE TEST COMPLETE (%.1fs)", elapsed)
    logger.info("Report: %s", report_path)
    logger.info("Cohort: %s", cohort_path)
    logger.info("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LongBench smoke test")
    parser.add_argument("--provider", default="anthropic", choices=["anthropic", "ollama"])
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    model = args.model
    if model is None:
        model = "claude-sonnet-4-5-20250929" if args.provider == "anthropic" else "gemma3:27b"

    asyncio.run(main(args.provider, model))
