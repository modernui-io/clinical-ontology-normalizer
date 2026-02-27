# EpiKG Benchmark: ClinicalBench Reproducibility Package

Reproducibility data and evaluation code for:

> **EpiKG: End-to-End Epistemic Preservation in Clinical Knowledge Graphs
> for Assertion-Aware Retrieval-Augmented Generation**

## Contents

```
epikg-benchmark/
├── clinicalbench/
│   ├── questions.json          # 400 questions (9 categories, 45 MIMIC-IV patients)
│   └── evaluator.py            # Deterministic keyword evaluator
├── results/
│   ├── opus/                   # Claude Opus 4.6 predictions
│   │   ├── C1_llm_alone.json
│   │   ├── C4_epistemic_kg_rag.json
│   │   ├── C4g_intent_aware.json
│   │   └── C6_long_context.json
│   └── medgemma/               # MedGemma 27B predictions
│       ├── C1_llm_alone.json
│       └── C4g_intent_aware.json
├── checksums.sha256            # SHA-256 integrity hashes
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

Re-scored with the standalone evaluator (deterministic, no LLM judge):

| Condition | Model | Accuracy | n |
|-----------|-------|----------|---|
| C1: LLM Alone | Claude Opus 4.6 | 49.5% | 400 |
| C4: Epistemic KG-RAG | Claude Opus 4.6 | 60.8% | 400 |
| C4g: Intent-Aware KG-RAG | Claude Opus 4.6 | 77.0% | 400 |
| C6: Long Context | Claude Opus 4.6 | 41.8% | 400 |
| C1: LLM Alone | MedGemma 27B | 52.5% | 400 |
| C4g: Intent-Aware KG-RAG | MedGemma 27B | 66.2% | 399 |

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

The benchmark questions, evaluator code, and model predictions are released for
research reproducibility. MIMIC-IV data access requires separate PhysioNet credentials
and is subject to the MIMIC-IV Data Use Agreement.
