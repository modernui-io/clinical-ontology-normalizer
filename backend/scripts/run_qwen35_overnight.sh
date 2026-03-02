#!/bin/bash
# Overnight Qwen3.5:35b benchmark run — C1 + C4g on all 400 ClinicalBench questions
#
# Usage: docker exec -d con-backend bash /app/scripts/run_qwen35_overnight.sh
#
# Output: data/benchmarks/results/qwen35_compare/
# Log: data/benchmarks/results/qwen35_overnight.log

set -e

export LLM_MODEL=qwen3.5-direct
export LLM_PROVIDER=ollama
export OLLAMA_BASE_URL=http://host.docker.internal:11434
export OLLAMA_QWEN_NUM_PREDICT=4096
export OLLAMA_QWEN_NUM_CTX=24576
export OLLAMA_QWEN_TIMEOUT=300
export OLLAMA_QWEN_NO_THINK=0
export OLLAMA_MAX_RETRIES=2
export OLLAMA_TIMEOUT=180
export TASKS=a,b
export USE_LLM_JUDGE=0
export OUTPUT_DIR=data/benchmarks/results/qwen35_compare

LOG=$OUTPUT_DIR/qwen35_overnight.log
mkdir -p $OUTPUT_DIR

echo "$(date) === Qwen3.5:35b overnight run starting ===" | tee -a $LOG

# C1 — LLM alone (no retrieval context)
echo "$(date) === Starting C1_llm_alone ===" | tee -a $LOG
CONDITIONS=C1_llm_alone uv run python scripts/run_clinicalbench.py >> $LOG 2>&1
echo "$(date) === C1 COMPLETE ===" | tee -a $LOG

# C4g — Intent-aware KG-RAG (full system)
echo "$(date) === Starting C4g_intent_aware ===" | tee -a $LOG
CONDITIONS=C4g_intent_aware uv run python scripts/run_clinicalbench.py >> $LOG 2>&1
echo "$(date) === C4g COMPLETE ===" | tee -a $LOG

echo "$(date) === ALL DONE ===" | tee -a $LOG

# Quick summary
echo "" | tee -a $LOG
echo "=== RESULTS SUMMARY ===" | tee -a $LOG
CP=$OUTPUT_DIR/clinicalbench_checkpoint.jsonl
for COND in C1_llm_alone C4g_intent_aware; do
    COUNT=$(grep -c "$COND" $CP 2>/dev/null || echo 0)
    echo "  $COND: $COUNT predictions" | tee -a $LOG
done
