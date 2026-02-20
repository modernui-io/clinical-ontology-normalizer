#!/usr/bin/env python3
"""Run DR.KNOWS benchmark against the real PostgreSQL-backed KG.

Evaluates path discovery, reasoning accuracy, semantic coverage,
knowledge coverage, and multi-hop metrics. Compares against published
DR.KNOWS baseline.

Usage:
    cd backend
    uv run python scripts/run_drknows.py

Options (via env vars):
    OUTPUT_DIR    Output directory (default: data/benchmarks/results)
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
logger = logging.getLogger("run_drknows")


async def main() -> None:
    logger.info("=" * 70)
    logger.info("DR.KNOWS Benchmark (Real KG)")
    logger.info("=" * 70)

    from app.core.database import async_session_maker
    from app.services.drknows_benchmark_service import get_drknows_benchmark_service

    output_dir = os.environ.get("OUTPUT_DIR", "data/benchmarks/results")
    os.makedirs(output_dir, exist_ok=True)

    t0 = time.perf_counter()

    async with async_session_maker() as session:
        service = get_drknows_benchmark_service(db_session=session)
        result = await service.run_full_benchmark(None)

    duration = time.perf_counter() - t0

    report = service.export_benchmark_report(result)
    report["duration_s"] = duration

    # Print summary
    print("\n" + "=" * 70)
    print("DR.KNOWS BENCHMARK RESULTS")
    print("=" * 70)

    metrics = report["metrics"]
    comparison = report["comparison"]

    print(f"\nOverall Score: {report['overall_score']:.4f}")
    print(f"DR.KNOWS Baseline: {comparison['overall']['baseline']:.4f}")
    print(f"Delta: {comparison['overall']['delta']:+.4f} ({comparison['overall']['percentage_of_baseline']:.1f}% of baseline)")
    print(f"Assessment: {comparison.get('assessment', 'N/A')}")

    print(f"\n| Metric | Our System | DR.KNOWS | Delta |")
    print("|---|---|---|---|")

    pd = metrics["path_discovery"]
    bl_pd = comparison["path_discovery"]
    print(f"| Path Discovery | {pd['coverage']:.1%} | {bl_pd['baseline_coverage']:.1%} | {bl_pd['delta']:+.1%} |")

    rs = metrics["reasoning"]
    bl_rs = comparison["reasoning"]
    print(f"| Reasoning Accuracy | {rs['accuracy']:.1%} | {bl_rs['baseline_accuracy']:.1%} | {bl_rs['delta']:+.1%} |")

    sc = metrics["semantic_coverage"]
    print(f"| Semantic Coverage | {sc['type_coverage']:.1%} | 91.2% | {sc['type_coverage'] - 0.912:+.1%} |")

    mh = metrics["multi_hop"]
    for hop in [1, 2, 3, 4]:
        key = f"hop_{hop}"
        ours = mh.get(key, 0)
        bl = comparison["multi_hop"].get(key, {}).get("baseline", 0) if key in comparison.get("multi_hop", {}) else 0
        if bl:
            print(f"| {hop}-Hop Accuracy | {ours:.1%} | {bl:.1%} | {ours - bl:+.1%} |")
        else:
            print(f"| {hop}-Hop Accuracy | {ours:.1%} | N/A | N/A |")

    print(f"\nDuration: {duration:.1f}s")

    # Save results
    out_path = os.path.join(output_dir, "drknows_benchmark.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info("Results saved to %s", out_path)

    logger.info("\n" + "=" * 70)
    logger.info("DR.KNOWS BENCHMARK COMPLETE (%.1fs)", duration)
    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
