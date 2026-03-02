# EpiKG Benchmark: ClinicalBench Reproducibility Package

Reproducibility data and evaluation code for:

> **EpiKG: End-to-End Epistemic Preservation in Clinical Knowledge Graphs
> for Assertion-Aware Retrieval-Augmented Generation**

**HuggingFace Dataset**: https://huggingface.co/datasets/alexstinard/epikg-clinicalbench

```python
from datasets import load_dataset
qs = load_dataset("alexstinard/epikg-clinicalbench", "questions", split="test")
preds = load_dataset("alexstinard/epikg-clinicalbench", "predictions_opus", split="test")
```

## Contents

```
epikg-benchmark/
├── clinicalbench/
│   ├── questions.json          # 400 questions (9 categories, 43 MIMIC-IV patients)
│   ├── evaluator.py            # Deterministic keyword evaluator v2
│   └── llm_judge.py            # LLM-as-judge evaluator
├── results/
│   ├── opus/                   # Claude Opus 4.6 predictions (8 conditions)
│   │   ├── C1_llm_alone.json
│   │   ├── C2_vanilla_rag.json
│   │   ├── C2b_dense_rag.json
│   │   ├── C3_kg_rag.json
│   │   ├── C4_epistemic_kg_rag.json
│   │   ├── C4g_intent_aware.json
│   │   ├── C6_long_context.json
│   │   └── C7_deterministic.json
│   ├── medgemma/               # MedGemma 27B (C1, C4g)
│   ├── gptoss/                 # GPT-OSS 20B (C1, C4g)
│   ├── qwen35/                 # Qwen3.5 35B (C1, C4g)
│   └── llm_judge/              # LLM-as-judge results
├── bootstrap_ci.py             # Bootstrap confidence intervals
├── bootstrap_ci_v2.py          # Extended CIs with C4 decomposition
├── checksums.sha256            # SHA-256 integrity hashes
├── croissant.json              # Croissant metadata (ML Commons)
├── export_benchmark.py         # Script used to generate this package
└── README.md
```

## Quick Start

```bash
# Score Opus C4g (intent-aware KG-RAG)
cd clinicalbench
python evaluator.py --questions questions.json --predictions ../results/opus/C4g_intent_aware.json

# Score Opus C1 (LLM alone baseline)
python evaluator.py --questions questions.json --predictions ../results/opus/C1_llm_alone.json
```

## Expected Results

Evaluator v2 results (deterministic keyword scoring with abstention detection):

| Condition | Model | Accuracy | n |
|-----------|-------|----------|---|
| C7: Deterministic KG | — | 3.8% | 400 |
| C1: LLM Alone | Claude Opus 4.6 | 21.8% | 400 |
| C2: Vanilla RAG (TF-IDF) | Claude Opus 4.6 | 52.2% | 400 |
| C2b: Dense RAG (Contriever) | Claude Opus 4.6 | 50.7% | 400 |
| C3: KG-RAG (no assertions) | Claude Opus 4.6 | 50.0% | 400 |
| C4: KG-RAG (assertions, no routing) | Claude Opus 4.6 | 46.8% | 400 |
| C4g: Intent-Aware KG-RAG | Claude Opus 4.6 | 69.0% | 400 |
| C6: Long Context | Claude Opus 4.6 | 39.0% | 400 |
| C1: LLM Alone | MedGemma 27B | 26.2% | 400 |
| C4g: Intent-Aware KG-RAG | MedGemma 27B | 57.8% | 400 |
| C1: LLM Alone | GPT-OSS 20B | 20.5% | 400 |
| C4g: Intent-Aware KG-RAG | GPT-OSS 20B | 58.0% | 400 |
| C1: LLM Alone | Qwen3.5 35B | 37.0% | 400 |
| C4g: Intent-Aware KG-RAG | Qwen3.5 35B | 57.5% | 400 |

Note: The `correct` column in prediction files contains checkpoint-recorded values
from experiment runtime, which may differ from evaluator v2 rescoring. Use the
standalone evaluator for authoritative accuracy numbers.

## Evaluator Design

The evaluator is fully deterministic — no LLM judge, no randomness. Each of the
9 question categories has a category-specific scoring function:

**Task A (Assertion-sensitive):**
- **Negation**: Word-boundary matching for negation keywords; correct if prediction and gold agree on negation polarity
- **Uncertainty**: Presence of hedging/uncertainty language (possible, suspected, likely, etc.)
- **Family History**: Distinguishes family history from patient's own conditions
- **Conditional**: Presence of conditional language (if, pending, depending, etc.)

**Task B (Temporal reasoning):**
- **Current State / Historical**: Temporal keyword matching with section-name stripping to avoid false positives from "Past Medical History" headers
- **Sequence / Change**: Term overlap between predicted and expected answers, with bonus for ordering keywords
- **Duration**: Duration keyword matching plus chronicity direction (chronic vs acute)

Threshold: binary categories require keyword presence; term-overlap categories use ≥0.3 threshold.

## Data Format

### Questions (`questions.json`)

```json
{
  "question_id": "bench_a_negation_01a73bf1",
  "task": "assertion_qa",
  "category": "negation",
  "question": "Does this patient have bowel obstruction?",
  "expected_answer": "No. The documentation explicitly states...",
  "mimic_subject_id": 10001338,
  "mimic_hadm_id": 29000879,
  "assertion_label": "negated",
  "domain": "diagnosis",
  "section": "discharge_diagnosis"
}
```

### Predictions (`results/opus/C4g_intent_aware.json`)

```json
{
  "question_id": "bench_a_negation_01a73bf1",
  "predicted_answer": "No, the patient does not have bowel obstruction...",
  "correct": true,
  "score": 1.0,
  "category": "negation"
}
```

Note: The `correct` and `score` fields in prediction files are checkpoint-recorded
values from experiment runtime. Re-scoring with the standalone evaluator may produce
slightly different results due to evaluator refinements made after some experiments
were run.

## MIMIC-IV Data Access

Questions reference MIMIC-IV patient records via `mimic_subject_id` and `mimic_hadm_id`.
To verify the clinical content, you need PhysioNet credentialed access:

1. Complete CITI training at https://physionet.org/
2. Request access to MIMIC-IV v3.1
3. Use subject/hadm IDs to look up the referenced clinical notes

## Integrity Verification

```bash
sha256sum -c checksums.sha256
```

## License

CC-BY-4.0. The benchmark questions, evaluator code, and model predictions are released
for research reproducibility. MIMIC-IV source data access requires separate PhysioNet
credentials and is subject to the MIMIC-IV Data Use Agreement.
