#!/usr/bin/env python3
from __future__ import annotations

"""Smoke test for the Longitudinal Clinical Benchmark harness.

Tests the full pipeline end-to-end with a small cohort:
1. Cohort selection (or synthetic fallback if DB is empty)
2. Question generation (template-based or slice benchmark mode)
3. Run selected conditions (B0-B4) on generated questions
4. LLM-judge scoring
5. Analysis + markdown output

Usage:
    cd backend
    python scripts/smoke_test_longbench.py [--provider anthropic|ollama] [--model MODEL] [--slice-bench]
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


def _print_slice_summary(cohort: LongBenchCohort) -> None:
    """Print concise slice/mechanism information for debugging."""
    slice_counts: dict[str, int] = {}
    mechanism_counts: dict[str, int] = {}
    for q in cohort.questions:
        if q.slice_id is not None:
            slice_counts[q.slice_id.value] = slice_counts.get(q.slice_id.value, 0) + 1
        if q.expected_mechanism is not None:
            mechanism_counts[q.expected_mechanism.value] = (
                mechanism_counts.get(q.expected_mechanism.value, 0) + 1
            )

    if slice_counts:
        logger.info("Slice distribution: %s", slice_counts)
    if mechanism_counts:
        logger.info("Mechanism distribution: %s", mechanism_counts)


async def main(
    provider: str,
    model: str,
    slice_bench: bool = False,
    judge_provider: str | None = None,
    judge_model: str | None = None,
) -> None:
    t0 = time.perf_counter()
    judge_provider = judge_provider or provider
    judge_model = judge_model or model
    logger.info("=" * 70)
    logger.info("LONGITUDINAL BENCHMARK SMOKE TEST")
    logger.info("=" * 70)
    logger.info("LLM:   %s / %s", provider, model)
    logger.info("Judge: %s / %s", judge_provider, judge_model)
    logger.info("Slice benchmark mode: %s", "on" if slice_bench else "off")

    from app.services.longbench_schemas import ConditionID
    from app.services.longbench_runner import (
        LongBenchAnalyzer,
        LongBenchRunConfig,
        LongBenchRunner,
    )
    from app.services.longbench_cohort import cohort_to_json
    from app.services.longbench_cohort import (
        LongBenchQuestionGenerator,
        SliceBenchQuestionGenerator,
    )

    # Step 1: Get cohort
    logger.info("\n--- Step 1: Cohort Selection ---")
    db_cohort, has_db = _try_db_cohort()

    if has_db and db_cohort and db_cohort.patients:
        cohort = db_cohort
        # Generate template questions for smoke test (skip LLM generation)
        gen = SliceBenchQuestionGenerator() if slice_bench else LongBenchQuestionGenerator()
        for patient in cohort.patients:
            if slice_bench:
                questions = gen.generate(patient)
            else:
                questions = gen._fallback_template_questions(patient, n=5)
            cohort.questions.extend(questions)
    else:
        cohort = _build_synthetic_cohort()
        if slice_bench:
            gen = SliceBenchQuestionGenerator()
            cohort.questions.extend(
                q for patient in cohort.patients for q in gen.generate(patient)
            )

    _print_slice_summary(cohort)

    logger.info("Cohort: %d patients, %d questions", len(cohort.patients), len(cohort.questions))
    logger.info("Tier summary: %s", cohort.tier_summary)
    for q in cohort.questions:
        logger.info("  %s [%s, tier=%s]: %s", q.question_id, q.domain.value, q.tier.value, q.question_text[:60])

    # Validate slice benchmark text does not mention graph terminology
    if slice_bench:
        banned_terms = {"graph", "edge", "node", "traversal", "knowledge graph"}
        for q in cohort.questions:
            full_text = " ".join([q.question_text] + [c.text for c in q.criteria]).lower()
            if any(term in full_text for term in banned_terms):
                logger.warning(
                    "Potential benchmark leakage in question %s: contains forbidden term",
                    q.question_id,
                )

    # Step 2: Configure run
    logger.info("\n--- Step 2: Run Configuration ---")
    conditions = [ConditionID.B0, ConditionID.B1, ConditionID.B2, ConditionID.B3, ConditionID.B4]
    logger.info("Conditions: %s", [c.value for c in conditions])

    config = LongBenchRunConfig(
        llm_model=model,
        llm_provider=provider,
        judge_model=judge_model,
        judge_provider=judge_provider,
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

    if report.condition_slice_scores:
        print("\n--- Condition × Slice Scores ---")
        print(LongBenchAnalyzer.to_slice_table(report.condition_slice_scores))
        print("\n--- Mechanism-aware B2→B3 / B3→B4 Deltas ---")
        print(LongBenchAnalyzer.to_mechanism_delta_table(report.results, cohort.questions))

    # Bootstrap confidence intervals
    print("\n--- Bootstrap 95% CIs (2000 resamples, seed=42) ---")
    print(f"| Condition | Mean | 95% CI |")
    print(f"|---|---|---|")
    ci_data = {}
    for cond in conditions:
        mean, lo, hi = LongBenchAnalyzer.bootstrap_ci(report.results, cond)
        label = f"{cond.value}"
        ci_data[cond] = {"mean": mean, "ci_lower": lo, "ci_upper": hi}
        print(f"| {label} | {mean:.1%} | [{lo:.1%}, {hi:.1%}] |")

    # Paired condition deltas (B2→B3, B3→B4, B2→B4)
    print("\n--- Paired Condition Deltas (bootstrap 95% CI) ---")
    pairs = [
        (ConditionID.B2, ConditionID.B3, "B2→B3 (KG layer)"),
        (ConditionID.B3, ConditionID.B4, "B3→B4 (guidelines+calc)"),
        (ConditionID.B2, ConditionID.B4, "B2→B4 (full uplift)"),
        (ConditionID.B0, ConditionID.B2, "B0→B2 (RAG uplift)"),
    ]
    paired_data = {}
    for cond_a, cond_b, label in pairs:
        delta = LongBenchAnalyzer.compute_paired_deltas(
            report.results, cond_a, cond_b,
        )
        paired_data[label] = delta
        sig = "*" if delta["ci_lower"] > 0 or delta["ci_upper"] < 0 else "ns"
        print(
            f"  {label}: Δ={delta['mean_delta']:+.1%} "
            f"CI=[{delta['ci_lower']:+.1%}, {delta['ci_upper']:+.1%}] "
            f"n={delta['n_pairs']} {sig}"
        )

    # Criterion leakage check
    print("\n--- Criterion Leakage Check (>50% word overlap) ---")
    flagged = LongBenchAnalyzer.criterion_leakage_check(
        report.results, cohort.questions,
    )
    if flagged:
        for f in flagged:
            print(
                f"  ⚠ {f['condition']} | {f['question_id']} | {f['criterion_id']} "
                f"| overlap={f['overlap']:.0%} | {f['criterion_text']}"
            )
    else:
        print("  No leakage detected.")

    # Print per-result detail
    print("\n--- Per-Result Detail ---")
    for r in report.results:
        status = f"{r.normalized_score:.0%}" if not r.error else "ERR"
        answer_preview = r.predicted_answer[:80].replace("\n", " ") if r.predicted_answer else "(empty)"
        print(f"  [{status}] {r.condition.value} | {r.question_id} ({r.domain}) | {answer_preview}")
        if r.criterion_results:
            for cr in r.criterion_results:
                mark = "+" if cr.satisfied else "-"
                print(f"    {mark} {cr.criterion_id}: {cr.reasoning[:60]}")

    # Step 5: Export
    output_dir = "data/benchmarks/results/longbench_smoke"
    os.makedirs(output_dir, exist_ok=True)

    # Add run metadata to report
    report.metadata.update({
        "llm_model": model,
        "llm_provider": provider,
        "judge_model": model,
        "judge_provider": provider,
        "llm_temperature": 0.0,
        "judge_temperature": 0.0,
        "bootstrap_seed": 42,
        "n_bootstrap": 2000,
        "section_aware_rag": True,
    })

    report_json = LongBenchAnalyzer.report_to_json(report)
    report_json["bootstrap_cis"] = {
        cond.value: ci_data[cond] for cond in conditions
    }
    report_json["paired_deltas"] = paired_data
    if report.condition_slice_scores:
        report_json["condition_slice_scores"] = [
            {
                "condition": s.condition.value,
                "slice_id": s.slice_id.value,
                "n_questions": s.n_questions,
                "mean_score": s.mean_score,
                "std_score": s.std_score,
                "mechanism_scores": s.mechanism_scores,
                "mechanism_counts": s.mechanism_counts,
            }
            for s in report.condition_slice_scores
        ]
        report_json["mechanism_delta_table"] = (
            LongBenchAnalyzer.to_mechanism_delta_table(
                report.results, cohort.questions
            )
        )
    report_json["criterion_leakage"] = flagged
    report_json["slice_bench"] = slice_bench

    report_path = os.path.join(output_dir, "smoke_report.json")
    with open(report_path, "w") as f:
        json.dump(report_json, f, indent=2, default=str)

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
    parser.add_argument("--judge-provider", default=None, choices=["anthropic", "ollama"],
                        help="Provider for judge LLM (defaults to --provider)")
    parser.add_argument("--judge-model", default=None,
                        help="Model for judge LLM (defaults to claude-opus-4-6 for anthropic)")
    parser.add_argument("--slice-bench", action="store_true", help="Run the 18-question slice benchmark")
    args = parser.parse_args()

    model = args.model
    if model is None:
        model = "claude-sonnet-4-5-20250929" if args.provider == "anthropic" else "gemma3:27b"

    judge_provider = args.judge_provider or args.provider
    judge_model = args.judge_model
    if judge_model is None:
        judge_model = "claude-opus-4-6" if judge_provider == "anthropic" else model

    asyncio.run(main(
        args.provider, model,
        slice_bench=args.slice_bench,
        judge_provider=judge_provider,
        judge_model=judge_model,
    ))
