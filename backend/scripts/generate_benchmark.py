#!/usr/bin/env python3
"""Generate ClinicalIntelligenceBench question sets from MIMIC-IV data.

Produces 600 gold-standard QA questions across 4 tasks:
  Task A: 200 negation-aware fact retrieval questions
  Task B: 200 temporal clinical reasoning questions
  Task C: 100 calculator-grounded decision questions
  Task D: 100 multi-source fusion questions

Usage:
    cd backend
    uv run python scripts/generate_benchmark.py

Output:
    data/benchmarks/task_a.json
    data/benchmarks/task_b.json
    data/benchmarks/task_c.json
    data/benchmarks/task_d.json
"""

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
logger = logging.getLogger("generate_benchmark")


def main() -> None:
    logger.info("=" * 70)
    logger.info("ClinicalIntelligenceBench — Question Generation")
    logger.info("=" * 70)

    t0 = time.perf_counter()

    from sqlalchemy.orm import Session

    from app.core.database import get_sync_engine
    from app.services.benchmark_generator import BenchmarkGenerator

    engine = get_sync_engine()

    with Session(engine) as session:
        generator = BenchmarkGenerator(session)

        # Generate all 4 tasks
        question_sets = generator.generate_all(
            task_a_count=200,
            task_b_count=200,
            task_c_count=100,
            task_d_count=100,
        )

        # Export to JSON
        output_dir = "data/benchmarks"
        paths = generator.export_to_json(question_sets, output_dir=output_dir)

    elapsed = time.perf_counter() - t0

    # Print summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("GENERATION COMPLETE (%.1fs)", elapsed)
    logger.info("=" * 70)

    total = 0
    for name, qs in question_sets.items():
        logger.info(
            "  %s: %d questions | subtypes: %s",
            name, qs.total_count, qs.subtype_distribution,
        )
        total += qs.total_count

    logger.info("")
    logger.info("  TOTAL: %d questions", total)
    logger.info("  Output: %s", ", ".join(paths))

    # Print sample questions
    logger.info("")
    logger.info("--- Sample Questions ---")
    for name, qs in question_sets.items():
        if qs.questions:
            q = qs.questions[0]
            logger.info("  [%s] %s", q.subtype, q.question[:80])
            logger.info("    Expected: %s", q.expected_answer[:80])


if __name__ == "__main__":
    main()
