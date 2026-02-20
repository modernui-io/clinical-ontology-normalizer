# EpiKG: NeurIPS 2026 Paper

## Paper Title

**EpiKG: End-to-End Epistemic Knowledge Graph Construction and Graph-Augmented Retrieval for Clinical Reasoning**

## Status

- [x] Phase A: Research & Paper Strategy (completed 2026-02-18)
- [x] Phase B-1: Experiment Infrastructure (completed 2026-02-18)
- [~] Phase B-2: Run Experiments on Live Data (in progress)
  - [x] MedQA-USMLE: 965/1273 valid, 81.6% accuracy (308 credit-error retries pending)
  - [x] DR.KNOWS benchmark: 42.0% overall (49.7% of baseline)
  - [x] Scalability analysis: 3,100 nodes, 8,803 edges, <1ms traversal
  - [ ] ClinicalIntelligenceBench: 600q × 5 conditions (blocked on API credits until Mar 1)
  - [ ] LLM Judge re-scoring (blocked on API credits)
  - [ ] MedQA error retries (blocked on API credits)
- [ ] Phase C: Paper Writing
- [ ] Phase D: Submission

## Target Venue

**NeurIPS 2026** — Sydney, Australia, December 6–12, 2026

| Milestone | Estimated Date |
|---|---|
| Abstract deadline | ~May 10–17, 2026 |
| Full paper deadline | ~May 14–21, 2026 |
| Supplementary materials | ~May 21–28, 2026 |
| Notifications | ~September 2026 |
| Camera-ready | ~October 2026 |

Format: 9 content pages + unlimited references/appendix. Double-blind review. NeurIPS LaTeX template.

Alternative tracks: Datasets & Benchmarks (if releasing assertion-annotated KG dataset).

## Core Thesis

Existing clinical KG and medical RAG systems discard epistemic metadata (negation, uncertainty, hypotheticality, experiencer attribution) during knowledge graph construction, leading to retrieval that conflates denied conditions with confirmed ones and ignores temporal validity. We present the first end-to-end system that preserves seven-class assertion status, tri-temporal modeling, and experiencer attribution from NLP extraction through knowledge graph construction to graph-augmented retrieval.

## Four Contributions

1. **Epistemic KG Schema** — 7-value assertion system (present/absent/possible/conditional/hypothetical/family_history/historical) carried end-to-end from NLP extraction through OMOP mapping, fact construction, KG materialization, and retrieval

2. **Tri-Temporal KG with Allen's Interval Algebra** — Three temporal dimensions (valid time, transaction time, NLP-asserted temporality) with 9 Allen interval algebra relations enabling temporal clinical queries

3. **Shared Concept Node Architecture** — Global concept deduplication with patient-specific edges, enabling both per-patient and cross-patient cohort queries on a unified graph with assertion statistics

4. **Assertion-Aware Graph-Augmented Retrieval** — 6-step GraphRAG pipeline traversing both patient KG edges AND 20M+ OMOP vocabulary relationships, with temporality-aware and confidence-weighted scoring

## Key Differentiator

No published system demonstrates end-to-end assertion preservation from NLP extraction through knowledge graph construction to query-time retrieval. The literature review confirms this gap across 25+ surveyed systems.

## Experiments

| # | Experiment | Key Metric | Status |
|---|---|---|---|
| 1 | MedQA-USMLE (1,273 MCQ) | Accuracy vs published baselines | **81.6% (965 valid)** — 308 retries pending |
| 2 | ClinicalIntelligenceBench (600q × 5 conditions) | Ablation accuracy per condition | Blocked on API credits (Mar 1) |
| 3 | DR.KNOWS KG Reasoning | Multi-hop reasoning, path discovery | **42.0% (49.7% of baseline)** |
| 4 | Scalability Analysis | Throughput, query latency, dedup ratio | **Complete** (0.57ms 1-hop, 0.75ms 2-hop) |
| 5 | LLM Judge Re-scoring | Judge vs keyword accuracy comparison | Blocked on API credits |
| 6 | Physician Evaluation | Blind clinical review, 100 held-out questions | Infrastructure built, recruitment pending |

## Datasets

- MIMIC-IV-Note (1K sample) — downloading
- MTSamples (99 docs) — imported, NLP-processed
- Synthea (50 docs) — imported, NLP-processed

## Artifacts

| File | Contents |
|---|---|
| `docs/paper/README.md` | This file — overview and status |
| `docs/paper/related_work.md` | Literature review (25+ papers) |
| `docs/paper/experiment_plan.md` | Detailed experiment design |
| `docs/paper/contributions.md` | Core claims with code evidence |
| `docs/paper/benchmarks_and_evaluation_literature.md` | Benchmarks & evaluation methodology |

## Phase B Infrastructure (New)

| File | Role |
|---|---|
| `backend/app/services/experiment_runner.py` | Core experiment execution — creates/runs all 6 experiments |
| `backend/app/services/qa_evaluation.py` | QA question sets + scoring for ablation experiments |
| `backend/scripts/run_experiments.py` | CLI to execute experiments (`--all`, `--exp N`, `--export`) |
| `backend/tests/test_experiment_runner.py` | 34 tests (all passing) |
| `backend/app/api/research.py` | Extended with NeurIPS experiment API endpoints |

## Key Comparison Papers

| Paper | Venue | Gap vs. Ours |
|---|---|---|
| DoctorRAG | NeurIPS 2025 | No patient KG, no assertion, no temporal |
| GFM-RAG | NeurIPS 2025 | General-purpose, no clinical semantics |
| MedRAG | WWW 2025 | Disease-centric KG, no assertion status |
| Medical-Graph-RAG | ACL 2025 | External sources, no patient notes |
| KARE | ICLR 2025 | Population-level KG, no assertion |
| Multi-LLM KG-RAG | arXiv Jan 2026 | LLM-only extraction, no assertion tracking |
| MedTKG | IEEE JBHI 2024 | Single temporal dimension only |
| Zep/Graphiti | arXiv Jan 2025 | Bitemporal but no clinical, no assertion |
| Beyond Negation Detection | ECIR 2025 | Detection only, not propagated to KG |

## Codebase Entry Points

| File | Role | Lines |
|---|---|---|
| `backend/app/services/graph_augmented_rag.py` | Core GraphRAG pipeline | 1,384 |
| `backend/app/models/knowledge_graph.py` | KGNode/KGEdge with bi-temporal fields | 316 |
| `backend/app/services/assertion_classifier.py` | Probabilistic assertion classifier | 501 |
| `backend/app/services/graph_builder_db.py` | KG construction with shared concepts | 1,221 |
| `backend/app/services/nlp_ensemble.py` | Ensemble NLP extraction | 605 |
| `backend/app/services/research_service.py` | Experiment tracking & metrics | ~700 |
| `backend/app/services/experiment_runner.py` | NeurIPS experiment execution engine | ~600 |
| `backend/app/services/qa_evaluation.py` | QA question sets + scoring | ~600 |
| `backend/app/schemas/base.py` | Assertion/Temporality/Experiencer enums | 80 |
| `backend/app/schemas/knowledge_graph.py` | TemporalOrder (9 Allen relations) | 276 |
