#!/bin/bash
# Run all NeurIPS experiments sequentially with checkpointing.
# This avoids concurrent API calls that burn credits faster.
#
# Usage (inside container):
#   bash scripts/run_all_experiments.sh
#
# Each experiment has checkpoint/resume — safe to interrupt and re-run.
# Re-running resumes from the last checkpoint automatically.

set -e

RESULTS_DIR="data/benchmarks/results"
mkdir -p "$RESULTS_DIR"

echo "=============================================="
echo "NeurIPS 2026 Experiment Suite"
echo "Model: ${LLM_MODEL:-claude-opus-4-5-20251101}"
echo "Provider: ${LLM_PROVIDER:-anthropic}"
echo "=============================================="

# 1. MedQA — resume fills in errored questions (~$8 for 308 remaining)
echo ""
echo "[1/3] MedQA-USMLE Benchmark (resume: fills errored questions)"
echo "----------------------------------------------"
uv run python scripts/run_medqa.py 2>&1 | tee "$RESULTS_DIR/medqa_v2.log"

echo ""
echo "[1/3] MedQA COMPLETE"
echo ""

# 2. ClinicalBench — 600 questions × 5 conditions (~8-12 hours, ~$150)
echo "[2/3] ClinicalIntelligenceBench Ablation"
echo "----------------------------------------------"
USE_LLM_JUDGE=1 uv run python scripts/run_clinicalbench.py 2>&1 | tee "$RESULTS_DIR/clinicalbench_v2.log"

echo ""
echo "[2/3] ClinicalBench COMPLETE"
echo ""

# 3. Re-score ClinicalBench with LLM judge (if not already done in step 2)
echo "[3/3] Re-score ClinicalBench with LLM Judge"
echo "----------------------------------------------"
uv run python scripts/rescore_with_judge.py 2>&1 | tee "$RESULTS_DIR/rescore_v2.log"

echo ""
echo "[3/3] Re-score COMPLETE"
echo ""

# Final analysis
echo "=============================================="
echo "Generating final analysis tables..."
echo "=============================================="
uv run python scripts/analyze_results.py

echo ""
echo "=============================================="
echo "ALL EXPERIMENTS FINISHED"
echo "Results in: $RESULTS_DIR"
echo "=============================================="
