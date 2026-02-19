# Experiment Plan: EpiKG NeurIPS 2026

## Overview

Six experiments using the existing `ResearchExperiment` model and `ResearchService`, with the 6-category metric framework (NLP, mapping, assertion, KG, RAG, timing).

---

## Experiment 1: End-to-End Pipeline Evaluation

### Hypothesis
The EpiKG pipeline achieves competitive entity extraction F1, high concept coverage, and high assertion accuracy across diverse clinical note sources while maintaining practical throughput.

### Datasets
| Dataset | Documents | Status |
|---|---|---|
| MIMIC-IV-Note | 1,000 (sampled) | Downloading |
| MTSamples | 99 | Imported, NLP-processed |
| Synthea | 50 | Imported, NLP-processed |

### Metrics (by MetricCategory)
| Category | Metric | Target |
|---|---|---|
| NLP | Entity extraction F1 (strict) | >0.80 |
| NLP | Entity extraction F1 (relaxed) | >0.88 |
| MAPPING | Concept coverage (% mentions mapped to OMOP) | >0.75 |
| MAPPING | Top-1 concept accuracy | >0.80 |
| ASSERTION | Overall assertion accuracy | >0.90 |
| ASSERTION | Per-class F1 (present, absent, possible, conditional, hypothetical, family_history, historical) | Report all |
| KG | Nodes per patient (mean) | Report |
| KG | Edges per patient (mean) | Report |
| KG | Graph density | Report |
| KG | Shared concept dedup ratio | Report |
| TIMING | Seconds per document (NLP) | <5s |
| TIMING | Seconds per document (full pipeline) | <15s |

### Baselines
- cTAKES (entity extraction + assertion)
- scispaCy (entity extraction)
- MedSpaCy/ConText (assertion detection)
- MetaMap/QuickUMLS (concept mapping)

### Execution
Uses `ResearchService.create_experiment()` with config:
```json
{
  "experiment_type": "pipeline_evaluation",
  "datasets": ["mimic_iv_note", "mtsamples", "synthea"],
  "metrics": ["nlp", "mapping", "assertion", "kg", "timing"],
  "sample_size": {"mimic": 1000, "mtsamples": 99, "synthea": 50}
}
```

---

## Experiment 2: Assertion Preservation Ablation (KEY RESULT)

### Hypothesis
Preserving epistemic assertion status end-to-end significantly improves downstream clinical QA accuracy, particularly for assertion-sensitive questions (negation, uncertainty, family history).

### Conditions
| Condition | Description |
|---|---|
| **no_assertion** | All mentions treated as PRESENT (assertion stripped) |
| **assertion_extracted_only** | Assertion detected but NOT propagated to KG or RAG |
| **full_epistemic** | Full 7-value assertion carried through KG to RAG |

### Question Set
50 assertion-sensitive clinical questions per condition (150 total), stratified:
- 15 negation-sensitive ("Does the patient have diabetes?" when note says "denies diabetes")
- 10 uncertainty-sensitive ("Is pneumonia confirmed?" when note says "possible pneumonia")
- 10 family-history-sensitive ("Does the patient have breast cancer?" when family history)
- 10 temporal-sensitive ("Is the patient currently on warfarin?" when historical)
- 5 conditional-sensitive ("Should we give metformin?" when conditional recommendation)

### Metrics
| Metric | Description |
|---|---|
| QA Accuracy | Correct answer rate per condition |
| Assertion Fidelity | % of KG edges with correct assertion status |
| False Positive Rate | Negated conditions returned as positive evidence |
| Clinical Safety Score | Weighted score penalizing dangerous assertion errors |

### Expected Result
Full epistemic condition significantly outperforms no_assertion, with largest gains on negation-sensitive and uncertainty-sensitive questions.

---

## Experiment 3: Temporal Reasoning Ablation

### Hypothesis
Bi-temporal modeling with Allen's interval algebra improves temporal clinical QA accuracy over timestamp-only and no-temporal baselines.

### Conditions
| Condition | Description |
|---|---|
| **no_temporal** | All temporal fields stripped from KG edges |
| **timestamps_only** | event_date preserved but no valid_from/to, no temporality, no temporal_order |
| **full_bitemporal** | All 3 temporal dimensions + Allen's algebra |

### Question Set
100 temporal clinical questions, stratified:
- 30 "current state" questions ("What medications is the patient currently taking?")
- 25 "historical" questions ("What was the patient's diagnosis in 2023?")
- 20 "sequence" questions ("Was the surgery before or after the infection?")
- 15 "duration" questions ("How long has the patient been on metformin?")
- 10 "change" questions ("Has the patient's blood pressure improved since starting lisinopril?")

### Metrics
| Metric | Description |
|---|---|
| Temporal QA Accuracy | Correct answer rate per condition |
| Temporal Precision | Correct temporal ordering in answers |
| Timeline Completeness | % of relevant events included |
| Temporal Conflict Detection | # of correctly flagged contradictions |

---

## Experiment 4: Graph-RAG vs Document-RAG

### Hypothesis
Graph-augmented retrieval outperforms document-only retrieval for clinical reasoning, with the largest gains on multi-hop and cross-concept queries.

### Conditions
| Condition | Description |
|---|---|
| **doc_only** | Standard document RAG (BM25 retrieval + LLM) |
| **graph_only** | KG traversal paths only, no documents |
| **graph_plus_doc** | Full GraphRAG (KG paths + documents) |
| **graph_plus_doc_plus_guidelines** | GraphRAG + 1,202 guideline sections |

### Question Set
200 clinical QA questions, stratified:
- 50 single-hop ("What is the patient's latest HbA1c?")
- 50 multi-hop ("What medications treat the patient's conditions that interact with their current drugs?")
- 50 reasoning ("Is the patient's treatment appropriate given their comorbidities?")
- 50 guideline-sensitive ("Does the patient meet criteria for statin therapy?")

### Metrics
| Metric | Description |
|---|---|
| QA Accuracy | Correct answer rate per condition |
| RAGAS Faithfulness | Factual consistency with retrieved context |
| RAGAS Answer Relevancy | How well response addresses query |
| nDCG@5 | Retrieval quality |
| Reasoning Trace Quality | Expert-rated reasoning chain quality (1–5 scale) |

### Expected Result
graph_plus_doc_plus_guidelines > graph_plus_doc > doc_only, with graph_only competitive on multi-hop but weaker on detail questions.

---

## Experiment 5: Benchmark Comparison

### 5A: MedAgentBench

**Service:** `backend/app/services/medagentbench_service.py`
- 300 tasks across 100 patient profiles
- 5 categories (BenchmarkCategory enum)
- Measure: Task success rate, per-category breakdown

**Baselines** (published results):
- Claude 3.5 Sonnet: 69.67% (top in published results)
- GPT-4o, Gemini, Llama 3.1 405B, etc.

### 5B: DR.KNOWS

**Service:** `backend/app/services/drknows_benchmark_service.py`
- KG + LLM diagnostic reasoning evaluation
- Human evaluation framework from clinical diagnostic safety

**Metrics:**
- Diagnostic accuracy
- KG-augmented vs. non-KG-augmented rationale quality
- Expert-rated reasoning quality

---

## Experiment 6: Scalability Analysis

### Hypothesis
The pipeline scales sub-linearly in throughput and the shared concept architecture provides increasing deduplication benefits at larger scale.

### Test Points
| Scale | Notes | Expected KG Nodes | Expected KG Edges |
|---|---|---|---|
| 100 notes | Small | ~2K | ~5K |
| 1,000 notes | Medium | ~15K | ~40K |
| 10,000 notes | Large | ~80K | ~250K |
| 100,000 notes | XL (MIMIC-scale) | ~300K | ~1M |

### Metrics
| Metric | Description |
|---|---|
| Throughput | Notes/second at each scale |
| NLP Latency | p50, p95, p99 per note |
| KG Build Time | Total wall-clock for graph construction |
| Graph Query Latency | p50, p95 for 1-hop, 2-hop, 3-hop traversals |
| Shared Concept Dedup Ratio | (unique concepts) / (total concept references) |
| CTE vs Neo4j Latency | PostgreSQL CTE query vs Neo4j Cypher for multi-hop |
| Memory Footprint | Peak memory during processing |

### Expected Result
Shared concept dedup ratio increases with scale (more patients share more concepts). CTE competitive with Neo4j for ≤3 hops.

---

## Execution Plan

### Phase B-1: Dataset Preparation
1. Complete MIMIC-IV-Note download and sample 1K notes
2. Run full NLP pipeline on MIMIC sample
3. Build KGs for all datasets
4. Verify metric collection infrastructure

### Phase B-2: Run Experiments (via ResearchService)
1. Create experiments via API/Research Lab UI
2. Execute runs with different configs
3. Collect metrics into ResearchExperimentMetric table

### Phase B-3: Analysis & Figures
1. Generate comparison tables
2. Create ablation plots
3. Export LaTeX tables via ResearchService export

### Phase B-4: Paper Writing
1. Introduction + Related Work (from docs/paper/related_work.md)
2. System Description (from docs/paper/contributions.md)
3. Experiments + Results
4. Discussion + Limitations
5. Conclusion

---

## Evaluation Standards

### Statistical Rigor
- Bootstrap 95% confidence intervals on all metrics
- McNemar's test for pairwise system comparisons
- Cohen's Kappa for inter-annotator agreement (where applicable)

### Reproducibility
- All experiments tracked via ResearchExperiment model
- Configs stored as JSON in experiment records
- Random seeds fixed and recorded
- Full provenance from experiment → runs → metrics

### Clinical Review
- Subset of QA answers reviewed by clinical domain expert
- Safety-critical assertion errors flagged and analyzed
- Error analysis on systematic failure modes
