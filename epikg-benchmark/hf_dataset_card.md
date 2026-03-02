---
license: cc-by-4.0
task_categories:
  - question-answering
language:
  - en
version: "1.0.0"
tags:
  - medical
  - clinical-nlp
  - knowledge-graph
  - rag
  - benchmark
  - mimic-iv
  - epistemic-assertions
  - croissant
pretty_name: ClinicalBench
size_categories:
  - n<1K
configs:
  - config_name: questions
    data_files:
      - split: test
        path: questions/test/data.parquet
  - config_name: predictions_opus
    data_files:
      - split: test
        path: predictions_opus/test/data.parquet
  - config_name: predictions_medgemma
    data_files:
      - split: test
        path: predictions_medgemma/test/data.parquet
  - config_name: predictions_gptoss
    data_files:
      - split: test
        path: predictions_gptoss/test/data.parquet
  - config_name: predictions_qwen35
    data_files:
      - split: test
        path: predictions_qwen35/test/data.parquet
  - config_name: llm_judge
    data_files:
      - split: test
        path: llm_judge/test/data.parquet
dataset_info:
  - config_name: questions
    features:
      - name: question_id
        dtype: string
      - name: task
        dtype: string
      - name: category
        dtype: string
      - name: question
        dtype: string
      - name: expected_answer
        dtype: string
      - name: mimic_subject_id
        dtype: int64
      - name: mimic_hadm_id
        dtype: int64
      - name: difficulty
        dtype: string
      - name: assertion_label
        dtype: string
      - name: domain
        dtype: string
      - name: section
        dtype: string
    splits:
      - name: test
        num_examples: 400
  - config_name: predictions_opus
    features:
      - name: question_id
        dtype: string
      - name: model
        dtype: string
      - name: condition
        dtype: string
      - name: predicted_answer
        dtype: string
      - name: correct
        dtype: bool
      - name: score
        dtype: float64
      - name: category
        dtype: string
      - name: latency_ms
        dtype: float64
    splits:
      - name: test
        num_examples: 3200
  - config_name: predictions_medgemma
    features:
      - name: question_id
        dtype: string
      - name: model
        dtype: string
      - name: condition
        dtype: string
      - name: predicted_answer
        dtype: string
      - name: correct
        dtype: bool
      - name: score
        dtype: float64
      - name: category
        dtype: string
      - name: latency_ms
        dtype: float64
    splits:
      - name: test
        num_examples: 800
  - config_name: predictions_gptoss
    features:
      - name: question_id
        dtype: string
      - name: model
        dtype: string
      - name: condition
        dtype: string
      - name: predicted_answer
        dtype: string
      - name: correct
        dtype: bool
      - name: score
        dtype: float64
      - name: category
        dtype: string
      - name: latency_ms
        dtype: float64
    splits:
      - name: test
        num_examples: 800
  - config_name: predictions_qwen35
    features:
      - name: question_id
        dtype: string
      - name: model
        dtype: string
      - name: condition
        dtype: string
      - name: predicted_answer
        dtype: string
      - name: correct
        dtype: bool
      - name: score
        dtype: float64
      - name: category
        dtype: string
      - name: latency_ms
        dtype: float64
    splits:
      - name: test
        num_examples: 800
  - config_name: llm_judge
    features:
      - name: question_id
        dtype: string
      - name: condition
        dtype: string
      - name: judge_score
        dtype: float64
      - name: judge_reason
        dtype: string
    splits:
      - name: test
        num_examples: 800
---

# ClinicalBench: Assertion-Aware Clinical QA Benchmark

ClinicalBench is a benchmark for evaluating clinical question-answering systems on **epistemic assertion reasoning** over longitudinal patient records from [MIMIC-IV](https://physionet.org/content/mimiciv/3.1/).

It accompanies the paper:

> **EpiKG: End-to-End Epistemic Preservation in Clinical Knowledge Graphs for Assertion-Aware Retrieval-Augmented Generation**

## Benchmark Overview

- **400 questions** across 9 assertion categories
- **43 MIMIC-IV patients** with longitudinal clinical records
- **2 task types**: assertion-sensitive (Task A) and temporal reasoning (Task B)
- **4 models evaluated**: Claude Opus 4.6, MedGemma 27B, GPT-OSS 20B, Qwen3.5 35B
- **8 experimental conditions** (ablation ladder from LLM-alone to full KG-RAG)
- **Deterministic keyword evaluator** (fully reproducible, no LLM judge dependency)

### Question Categories

| Category | Task | Description |
|----------|------|-------------|
| Negation | A | Does the system correctly identify negated findings? |
| Uncertainty | A | Does the system preserve hedging language? |
| Family History | A | Does the system distinguish family from patient history? |
| Conditional | A | Does the system recognize conditional clinical statements? |
| Current State | B | Can the system identify what is currently active? |
| Historical | B | Can the system distinguish resolved from active conditions? |
| Sequence | B | Can the system reason about temporal ordering? |
| Change | B | Can the system detect medication/condition changes across admissions? |
| Duration | B | Can the system reason about chronicity and duration? |

### Experimental Conditions

| Condition | Description |
|-----------|-------------|
| C1 | LLM alone (no retrieval) |
| C2 | Vanilla RAG (TF-IDF retrieval) |
| C2b | Dense retrieval RAG (Contriever) |
| C3 | KG-RAG without assertions |
| C4 | KG-RAG with assertions but no intent routing |
| C4g | Intent-aware KG-RAG (full system) |
| C6 | Long-context (full notes, no retrieval) |
| C7 | Deterministic KG lookup (no LLM) |

## Key Results

Accuracy on ClinicalBench (evaluator v2, deterministic keyword scoring):

| Model | C1 (LLM alone) | C4g (Intent-aware) | Delta |
|-------|-----------------|---------------------|-------|
| Claude Opus 4.6 | 21.8% | **69.0%** | **+47.2pp** |
| MedGemma 27B | 26.2% | 57.8% | +31.5pp |
| GPT-OSS 20B | 20.5% | 58.0% | +37.5pp |
| Qwen3.5 35B | 37.0% | 57.5% | +20.5pp |

Physician validation (n=30, blinded): C1 29% correct vs C4g **81% correct** (+52pp).

## Dataset Configs

### `questions` (400 rows)

The benchmark questions with gold-standard expected answers.

```python
from datasets import load_dataset
qs = load_dataset("alexstinard/epikg-clinicalbench", "questions", split="test")
```

### `predictions_opus` (3,200 rows)

Claude Opus 4.6 predictions across all 8 conditions (C1, C2, C2b, C3, C4, C4g, C6, C7).

```python
preds = load_dataset("alexstinard/epikg-clinicalbench", "predictions_opus", split="test")
c4g = preds.filter(lambda x: x["condition"] == "C4g_intent_aware")  # 400 rows
```

### `predictions_medgemma`, `predictions_gptoss`, `predictions_qwen35` (800 rows each)

Cross-model predictions for C1 and C4g conditions only.

### `llm_judge` (800 rows)

LLM-as-judge scores (Claude Opus) for C1 and C4g Opus predictions, with reasoning.

## Evaluation

The deterministic keyword evaluator requires only Python 3.10+ with no dependencies:

```python
from datasets import load_dataset
import json

# Load data
qs = load_dataset("alexstinard/epikg-clinicalbench", "questions", split="test")
preds = load_dataset("alexstinard/epikg-clinicalbench", "predictions_opus", split="test")

# Filter to a condition
c4g = preds.filter(lambda x: x["condition"] == "C4g_intent_aware")

# The 'correct' and 'score' columns contain pre-computed evaluator results.
# To re-evaluate, download evaluator.py from this repo and run:
#   python evaluator.py --questions questions.json --predictions predictions.json
accuracy = sum(c4g["correct"]) / len(c4g)
print(f"C4g accuracy: {accuracy:.1%}")  # Expected: 69.0%
```

The standalone evaluator (`evaluator.py`) is included in this repository for full reproducibility.

## MIMIC-IV Data Access

Questions reference MIMIC-IV patient records via `mimic_subject_id` and `mimic_hadm_id`.
The benchmark itself contains **no protected health information** -- only MIMIC-IV record identifiers.
To verify clinical content against source notes, you need [PhysioNet credentialed access](https://physionet.org/) to MIMIC-IV v3.1.

## Files

| File | Description |
|------|-------------|
| `questions/` | 400 benchmark questions with gold answers |
| `predictions_*/` | Model predictions per condition |
| `llm_judge/` | LLM-as-judge scores and reasoning |
| `evaluator.py` | Deterministic keyword evaluator (standalone) |
| `bootstrap_ci.py` | Bootstrap confidence interval computation |
| `bootstrap_ci_v2.py` | Extended CIs with C4 decomposition |
| `checksums.sha256` | SHA-256 integrity hashes for source JSON |

## Citation

```bibtex
@article{stinard2026epikg,
  title={EpiKG: End-to-End Epistemic Preservation in Clinical Knowledge Graphs for Assertion-Aware Retrieval-Augmented Generation},
  author={Stinard, Alex},
  year={2026}
}
```

## License

CC-BY-4.0. MIMIC-IV source data access requires separate PhysioNet credentials and is subject to the [MIMIC-IV Data Use Agreement](https://physionet.org/content/mimiciv/3.1/).
