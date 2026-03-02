# Qwen3.5:35b ClinicalBench Run — Provenance

## Run Configuration
- **Run ID**: qwen35_compare_20260302_v3 (v1: num_predict=4096+thinking→51% empties; v2: num_predict=1536+/no_think→42.9% empties; v3: template-level thinking suppression)
- **Start time**: 2026-03-02 (v3)
- **Git commit**: (current HEAD)
- **Model**: qwen3.5-direct (custom Modelfile from qwen3.5:35b weights, Q4_K_M quantization)
- **Model blob**: sha256-d838916ba05b9d908e9c3fecf16273b942a99aae94d1725c3e9fdd772522cf1a (same weights as qwen3.5:35b)
- **Thinking suppression**: Custom Modelfile template injects pre-filled empty `<think>\n</think>\n` block at start of assistant response. This tricks the model into skipping its thinking phase entirely, producing direct answers. No RENDERER/PARSER directives (avoids Ollama 0.17.4's thinking field separation). `/no_think` prompt suffix disabled. `<think>` stripping regex retained as safety net.
- **Provider**: Ollama 0.17.4 (http://host.docker.internal:11434)
- **Container image**: sha256:36be143d5ca02e8c18420570c04f28e0eb22f545367c7aaf77026b792a124d44 (Debian bookworm, Python 3.11.11)
- **Conditions**: C1_llm_alone, C4g_intent_aware
- **Questions**: 400 (Task A: 200, Task B: 200)
- **Temperature**: 0
- **top_p**: default (1.0)
- **num_ctx**: 24576
- **num_predict**: 4096
- **Timeout**: 300s per question (with 2 retries on connection/timeout errors)
- **Max retries**: 2 (fail fast — don't compound timeouts)
- **Evaluator**: keyword v2 (with abstention detection)
- **Smoke test**: 66/66 C1 questions, zero empties, avg 3.0s/question
- **Command**: `docker exec -d con-backend bash /app/scripts/run_qwen35_overnight.sh`
- **Env vars**: LLM_MODEL=qwen3.5-direct, LLM_PROVIDER=ollama, OLLAMA_BASE_URL=http://host.docker.internal:11434, OLLAMA_QWEN_NUM_PREDICT=4096, OLLAMA_QWEN_NUM_CTX=24576, OLLAMA_QWEN_TIMEOUT=300, OLLAMA_QWEN_NO_THINK=0, OLLAMA_MAX_RETRIES=2, TASKS=a,b, USE_LLM_JUDGE=0, OUTPUT_DIR=data/benchmarks/results/qwen35_compare

## File Hashes (SHA-256 prefix)
- task_a.json: ca4a2340e13499e8
- task_b.json: 91da747454065eb5
- evaluator.py: 744a83f3ee2c6b82
- qa_experiment_executor.py: 09fce55b409f994e
- ablation_harness.py: d0492f2f9f3a1972
- run_qwen35_overnight.sh: (created this run)

## Timeout/Missing Policy
- If <400 predictions for a condition, missing questions are scored as incorrect
- Same policy as MedGemma (which had 399/400 for C4g, 1 timeout)
- Explicit note added to any results table

## Scoring Protocol
1. Do NOT trust in-run `correct` flags from checkpoint
2. Rescore ALL predictions from raw `predicted_answer` using `epikg-benchmark/clinicalbench/evaluator.py` (v2)
3. Same n=400 denominator, same 9 categories, same hard longitudinal subset (change + current_state + historical, n=130)
4. Compute question-level BCa bootstrap 95% CIs (n=2000, seed 42)
5. Compute patient-level cluster BCa bootstrap CIs (43 patients)
6. McNemar's test on paired C1 vs C4g (same question universe)
7. Report abstention rate for C1 vs C4g

## Outputs
- Checkpoint: clinicalbench_checkpoint.jsonl (per-question, resumable, immutable folder)
- Log: qwen35_overnight.log
- Final exports: epikg-benchmark/results/qwen35/C1_llm_alone.json, C4g_intent_aware.json
- SHA-256 manifest: generated at completion

## Post-Run Audit Table
(To be filled after completion)

| Metric | Value | Source file | Script |
|--------|-------|-------------|--------|
| C1 overall accuracy | — | C1_llm_alone.json | evaluator.py v2 |
| C4g overall accuracy | — | C4g_intent_aware.json | evaluator.py v2 |
| C4g−C1 delta | — | bootstrap_ci.py | BCa n=2000 |
| C4g−C1 CI (question) | — | bootstrap_ci.py | BCa seed 42 |
| C4g−C1 CI (patient) | — | bootstrap_ci.py | cluster BCa |
| McNemar χ² | — | bootstrap_ci.py | paired |
| C1 abstention rate | — | evaluator.py v2 | abstention gate |
| C4g abstention rate | — | evaluator.py v2 | abstention gate |
| Hard longitudinal Δ | — | evaluator.py v2 | n=130 subset |
| n (C1) | — | checkpoint | unique question_ids |
| n (C4g) | — | checkpoint | unique question_ids |
