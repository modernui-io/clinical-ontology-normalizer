# VP Data Science / ML -- Executive Review

**Date:** 2026-02-06
**Author:** VP Data Science & Machine Learning
**Audience:** CTO, Engineering Leadership
**Scope:** AI/ML infrastructure, NLP pipeline, model lifecycle, and strategic roadmap

---

## Executive Summary

The ML/AI stack has real depth. Unlike many healthcare platforms that bolt on a single model and call it "AI-powered," this codebase contains a genuinely layered NLP pipeline (rule-based -> transformer -> ensemble), a nascent GraphRAG system with temporal reasoning, and infrastructure scaffolding for model lifecycle management and federated learning. The production NLP layers are solid. The ML platform layers (registry, fine-tuning, federated) are well-designed scaffolds that need to be connected to real compute and storage. The highest-ROI path forward is hardening the NLP ensemble and GraphRAG for production clinical use before expanding into model training infrastructure.

**Overall AI/ML Maturity: Pilot-to-Production transition for NLP, Scaffold for ML Platform.**

---

## 1. NLP Pipeline Assessment

### Architecture: Rule-Based -> Transformer -> Ensemble

This is a textbook-correct clinical NLP architecture. The layered approach is exactly what you want for healthcare:

**Rule-Based Layer** (`nlp_rule_based.py`, `assertion_classifier.py`, `section_parser.py`, `value_extraction.py`, `relation_extraction.py`) -- **Maturity: Production**

- High-precision extraction for well-defined patterns: medication doses, vitals, lab values
- Section-aware parsing (H&P, discharge summaries, progress notes)
- Assertion classification (present, absent, possible) with clinical-grade negation handling
- Strong test coverage across dedicated test suites
- This is the extraction backbone and it works. No changes needed.

**Transformer NER Layer** (`nlp_clinical_ner.py`, `nlp_modernbert_ner.py`) -- **Maturity: Pilot**

- `ClinicalNERService`: Uses HuggingFace `samrawal/bert-base-uncased_clinical-ner` with fallback chain to BioBERT variants. 512-token context with sentence-boundary-aware chunking. Handles BIO tags, maps to OMOP domains, detects assertion/temporality/experiencer from context patterns.
- `ModernBERTNERService`: 8192-token context window via `answerdotai/ModernBERT-base`, Flash Attention 2 support, Apple MPS awareness. Eliminates chunking for most clinical documents. Weighted 1.2x in the ensemble due to expected accuracy gains on long-range dependencies.
- Both services use lazy singleton initialization with double-checked locking. Both gracefully degrade: if transformers/torch not installed, they silently fall back.

**Key concern**: Neither model is fine-tuned on clinical NER data. The `samrawal/bert-base-uncased_clinical-ner` model is a community checkpoint with limited validation. ModernBERT-base is a general-purpose architecture, not fine-tuned for token classification at all. The code treats it as an NER model but it ships as a masked language model -- the pipeline would need a fine-tuned head to produce meaningful NER output.

**Ensemble Layer** (`nlp_ensemble.py`) -- **Maturity: Pilot**

- Orchestrates all extractors with configurable enable/disable per method
- Span overlap detection with 50% threshold, domain-specific preferences (prefer rule-based for drugs, ML for conditions, value extraction for measurements)
- Confidence boosting when multiple methods agree (+0.10, capped at 0.99)
- Reports extraction statistics with timing
- Clean separation of concerns -- each extractor is independent

**Advanced Post-Processing** (`nlp_advanced.py`) -- **Maturity: Production**

This is genuinely impressive work:
- Context-aware abbreviation disambiguation for 15+ clinical abbreviations (PE -> pulmonary embolism vs. physical exam, scored by surrounding context indicators)
- Clause-boundary-aware negation: respects "but", "however", ";" boundaries, handles both pre-mention ("no chest pain") and post-mention ("PE ruled out") negation
- Compound condition extraction: "heart failure with reduced EF" -> HFrEF, embedded abbreviation detection (AECOPD, ESRD, T2DM)
- Ordered laterality matching: bilateral/unilateral checked before left/right to prevent "b/l" mismatches
- 904 lines of carefully crafted clinical logic. This is domain expertise encoded as software.

### NLP Pipeline Verdict

The rule-based + advanced post-processing layers are production-grade. The transformer layer is architecturally sound but running on suboptimal model checkpoints. The ensemble orchestration is well-designed. **This is 80% of the way to a production clinical NLP pipeline.**

### NLP Gaps

| Gap | Impact | Effort |
|-----|--------|--------|
| No fine-tuned clinical NER model | Transformer layer produces mediocre entity extraction | Medium (fine-tune on i2b2/n2c2 or in-house annotations) |
| No model performance benchmarking | Cannot measure or report extraction quality | Low (add benchmark suite against gold-standard corpus) |
| No A/B framework for ensemble weights | Cannot optimize ensemble configuration empirically | Medium |
| Assertion detection uses regex, not learned model | Misses complex negation patterns | Medium-High (train NegBERT-style model) |
| No active learning loop | Cannot improve from clinician corrections | High |

---

## 2. LLM Integration Strategy

### Current State

**Narrative Extractor** (`narrative_extractor.py`) -- **Maturity: Pilot**

- Dual-provider architecture: Ollama (local) preferred, Claude API (cloud) as fallback
- Model preference chain for Ollama: BioMistral -> MedGemma 27B -> Meditron -> Mistral -> LLaMA 3.1
- Uses entity-grounded prompting: pre-extracted entities are injected into the prompt to prevent hallucination. This is exactly the right pattern.
- Extracts structured JSON: admission reason (primary problem, contributing factors), hospital course (temporally ordered key events with causal links), discharge plan (disposition, follow-up, medications)
- 180-second timeout for Ollama, 15K character text limit, temperature 0.0 for deterministic output
- Claude model hardcoded to `claude-sonnet-4-20250514` -- appropriate choice for structured extraction

### LLM Strategy Assessment

The Ollama-first, Claude-fallback architecture is pragmatically correct for healthcare:

**Local LLM (Ollama) -- Use for:**
- Narrative extraction (where data cannot leave the environment)
- Real-time clinical decision support (latency matters)
- High-volume batch processing (cost control)
- PHI-containing workloads (regulatory simplicity)

**Cloud LLM (Claude API) -- Use for:**
- Complex multi-step reasoning (guideline application, differential diagnosis)
- Low-volume, high-quality extraction tasks
- Fallback when local models produce low-confidence output
- Development and evaluation (gold-standard comparisons)

### LLM Gaps

| Gap | Recommendation |
|-----|----------------|
| No confidence calibration on LLM output | Add structured output validation + confidence scoring |
| No LLM output caching | Add semantic cache for repeated patterns |
| No prompt versioning | Version prompts alongside model versions |
| Hardcoded model selections | Make model selection configurable per task |
| No LLM observability | Add token usage, latency, and quality metrics per call |
| No human-in-the-loop review | Add clinician review queue for low-confidence extractions |

---

## 3. GraphRAG and Knowledge Reasoning

### Current State

**GraphAugmentedRAGService** (`graph_augmented_rag.py`) -- **Maturity: Pilot**

Architecture is solid conceptually:
1. Extract concepts from query (currently keyword-based, not NER-based)
2. Find matching nodes in patient's KG (SQLAlchemy queries against KGNode/KGEdge)
3. BFS traversal up to 3 hops from seed nodes (max 10 paths, top 5 starting nodes)
4. Build temporal context from edge event_date metadata (current vs. historical state)
5. Serialize graph paths + temporal context + policy constraints + retrieved documents into structured LLM prompt

Both sync and async session support. Path classification (condition_treatment, comorbidity, patient_medication). Confidence propagation through paths (min confidence across edges).

### GraphRAG Potential

This is one of the highest-potential components in the system. Patient knowledge graphs + temporal reasoning + LLM context augmentation is a genuinely differentiated capability. Very few healthcare platforms have this.

### GraphRAG Gaps

| Gap | Impact | Priority |
|-----|--------|----------|
| Concept extraction is keyword-based, not NER-linked | Poor recall on query understanding | P0 -- wire the ensemble NLP into query concept extraction |
| Document retrieval is a placeholder (returns []) | No grounding in source documents | P0 -- integrate with vector store / SemanticQA |
| Policy constraints are a placeholder (returns []) | No guideline grounding | P1 -- integrate with guideline RAG service |
| No path scoring/ranking | All paths weighted equally regardless of clinical relevance | P1 |
| BFS traversal is O(n^k) without pruning | Performance risk on large graphs | P2 -- add beam search or weighted traversal |
| No graph embedding for semantic similarity | Cannot find "similar" patient subgraphs | P2 |
| Temporal conflict detection is stubbed | Cannot flag contradictory clinical facts | P1 |

---

## 4. Model Lifecycle Management

### Model Registry (`model_registry_service.py`) -- **Maturity: Scaffold**

- In-memory registry with lifecycle stages: development -> staging -> production -> archived
- Version management with automatic promotion/demotion
- Performance metric tracking per version
- Pre-loaded with sample models (mortality risk, readmission)
- Clean API: register, version, transition, list, delete

### ML Model Service (`ml_model_service.py`) -- **Maturity: Scaffold**

- Comprehensive Pydantic schemas for model metadata, performance metrics, predictions
- Feature engineering utilities (normalization, encoding, binning, age calculation)
- Training pipeline supporting LogisticRegression, RandomForest, GradientBoosting (sklearn)
- Evaluation suite: AUC-ROC, AUC-PR, calibration curves, Brier score, feature importance
- Batch prediction API with risk tier classification
- Mock prediction simulation for demo (deterministic based on patient_id hash)

**The good**: The schemas and API contracts are well-designed. The evaluation metrics are clinically relevant (Brier score and calibration are critical for risk models). Feature importance tracking enables explainability.

**The bad**: Everything runs in-memory with mock data. No persistent artifact store, no experiment tracking (MLflow/W&B), no model serving infrastructure, no A/B testing framework, no data drift monitoring.

### LLM Fine-Tuning Pipeline (`llm_finetuning.py`, `llm_finetuning_service.py`) -- **Maturity: Scaffold**

- Full REST API: dataset management, job management, model management, deployment, inference
- Supports: LoRA, QLoRA, prefix tuning, adapter methods
- Base models: BioBERT, ClinicalBERT, PubMedBERT, LLaMA 7B/13B, Mistral 7B
- Tasks: NER, text classification, relation extraction, QA, summarization
- Comprehensive request/response models with validation

This is a well-designed API contract for a fine-tuning platform, but the backing service uses simulated training/evaluation. No connection to actual GPU compute, no experiment tracking, no model artifact persistence.

### Model Lifecycle Verdict

The contracts are production-quality. The implementations are demonstrations. This is the right order of operations -- you want the API right before you invest in infrastructure. But there is significant work to connect these to real training and serving infrastructure.

---

## 5. Federated Learning Assessment

### Current State (`federated_learning_service.py`) -- **Maturity: Scaffold**

This is an impressively complete scaffold:

- **Federation management**: Create/join federations, participant registration with role assignment (coordinator/participant), data size validation
- **Aggregation protocols**: FedAvg (weighted averaging), FedProx (proximal regularization for heterogeneous data), Secure Aggregation (simulated mask-based protocol)
- **Privacy mechanisms**: Gradient clipping, local DP, central DP with calibrated Gaussian noise, privacy budget tracking via composition theorem
- **Local training simulation**: Mock data generation with org-specific distribution shifts (simulating real-world data heterogeneity), multi-epoch local training loop
- **Model types**: Readmission prediction, mortality risk, length of stay, phenotyping, treatment response
- **Metrics**: Per-round loss/AUC/accuracy tracking, convergence estimation, privacy budget accounting

The code demonstrates deep understanding of the federated learning literature (FedAvg, FedProx, DP composition, secure aggregation). The mock data generator creates realistic org-specific distribution shifts, which is important for testing heterogeneity handling.

### Should We Invest Now?

**No. Not yet.**

Federated learning requires:
1. Multiple organizations with real data (requires BAAs, governance, trust frameworks)
2. Secure compute infrastructure at each site (requires deployment at partner hospitals)
3. Network infrastructure for gradient exchange (requires secure channels, possibly TEFCA integration)
4. Regulatory clarity on cross-org model training with patient data

The current platform does not yet have a single production deployment. Investing in multi-org federated infrastructure before achieving single-org production readiness is premature optimization.

**Recommendation**: Keep the scaffold. Do not invest engineering effort here until (a) the core NLP pipeline and GraphRAG are production-grade, (b) there are at least 2 partner organizations with signed agreements, and (c) single-site model training is proven with real clinical data.

The scaffold has value as a demonstration of capability and as an API contract for future work. Estimated time to production: 12-18 months after prerequisites are met.

---

## 6. Responsible AI Assessment

### What Exists

- **Explainability**: Feature importance tracking in ML model service, SHAP-like feature contributions in prediction results, human-readable explanation strings
- **Confidence calibration**: Brier score, calibration curves (prob_true vs prob_pred), expected calibration error in ModelPerformance schema
- **Assertion awareness**: Negation detection, uncertainty detection, experiencer detection (patient vs. family) in NLP pipeline -- critical for avoiding false positives
- **Entity grounding**: Narrative extractor grounds LLM output against pre-extracted entities to prevent hallucination

### What Is Missing

| Missing Capability | Risk Level | Recommendation |
|-------------------|------------|----------------|
| **Bias detection / fairness metrics** | HIGH | No demographic parity, equalized odds, or disparate impact metrics. Models could perform differently across race, age, sex, insurance type. Must add before any production deployment of risk models. |
| **Model cards** | MEDIUM | No standardized documentation of model intended use, limitations, training data demographics, performance across subgroups |
| **Data shift monitoring** | HIGH | No detection of training-serving skew. Clinical practice changes, EHR system migrations, and seasonal patterns will cause model degradation silently. |
| **Audit trail for predictions** | HIGH | Risk predictions that influence clinical decisions must be logged with model version, input features, and output for retrospective audit |
| **Human oversight workflow** | HIGH | No mechanism for clinician review/override of AI-generated outputs, no feedback loop to improve models |
| **Adversarial robustness** | LOW | Less relevant for clinical NLP than for consumer-facing systems, but adversarial clinical notes (copy-forward artifacts, template text) can fool NER |

### Responsible AI Verdict

The NLP pipeline has good foundational practices (negation awareness, confidence scoring, entity grounding). The ML model service has calibration infrastructure. But there are zero fairness/bias metrics, no model cards, and no prediction audit trail. **These must be addressed before deploying any risk prediction models to production.**

---

## 7. AI/ML Roadmap: Highest-ROI Investments

### Tier 1: Must-Do Before Production (Q1-Q2 2026)

| Investment | ROI Rationale | Effort |
|-----------|---------------|--------|
| Fine-tune clinical NER model on i2b2/n2c2 data | Transforms transformer layer from demo to clinically useful. Single biggest quality lever. | 3-4 weeks |
| Wire ensemble NLP into GraphRAG concept extraction | Currently keyword-based, missing most queries. Unlocks the full GraphRAG value proposition. | 1-2 weeks |
| Add NLP benchmark suite (precision/recall/F1 by entity type) | Cannot improve what you cannot measure. Required for any clinical validation claim. | 2-3 weeks |
| Implement bias/fairness metrics for risk models | Regulatory requirement. Cannot deploy risk predictions without demonstrating equitable performance. | 3-4 weeks |
| Add prediction audit logging | Clinical AI governance requirement. Every prediction that influences care must be traceable. | 2 weeks |

### Tier 2: High-Value, Medium-Term (Q3 2026)

| Investment | ROI Rationale | Effort |
|-----------|---------------|--------|
| Integrate GraphRAG document retrieval with vector store | Completes the RAG pipeline. Without document grounding, GraphRAG only uses graph paths. | 4-6 weeks |
| Connect ML model service to persistent artifact store (MLflow or equivalent) | Required for model reproducibility and governance. In-memory storage is unacceptable for production. | 4 weeks |
| Implement LLM output confidence calibration | Enables automated routing of low-confidence extractions to human review. | 3 weeks |
| Add active learning pipeline for NLP corrections | Clinical users correct NER output -> corrections feed back into training data. Compounding improvement. | 6-8 weeks |
| Deploy model monitoring (data drift, prediction drift) | Models degrade silently. Monitoring detects degradation before it causes clinical harm. | 4-5 weeks |

### Tier 3: Strategic, Longer-Term (Q4 2026+)

| Investment | ROI Rationale |
|-----------|---------------|
| Fine-tuning pipeline connected to real GPU compute | Enables domain-specific model training on proprietary clinical data |
| Graph neural networks for patient similarity | Enables "similar patient" queries and cohort discovery |
| Federated learning pilot with 2-3 partner organizations | Only after single-site is proven |
| Multi-modal extraction (combining clinical text + structured EHR data) | Higher-quality predictions from richer feature sets |

---

## 8. Top 5 AI/ML Priorities for Next Quarter

1. **Fine-tune a clinical NER model and benchmark it.** The transformer NER layer is architecturally correct but running on generic checkpoints. Fine-tuning on clinical NER data (i2b2 2010/2012, n2c2 2018) and establishing benchmark metrics (target: F1 > 0.85 for conditions, > 0.90 for medications) is the single highest-ROI AI investment. Without this, the ensemble's ML component is decorative.

2. **Complete the GraphRAG pipeline by integrating NLP concept extraction and document retrieval.** The graph traversal and temporal reasoning components are genuinely differentiated technology. But the query concept extraction is keyword-based and document retrieval returns empty lists. Wiring the ensemble NLP into concept extraction and connecting a vector store for document retrieval will complete the pipeline and unlock the full value of the knowledge graph investment.

3. **Add fairness metrics and prediction audit logging to the ML model service.** Before any risk model touches production, we need demographic parity analysis, equalized odds computation, and a persistent audit log of every prediction. This is non-negotiable for healthcare AI deployment and will be required for any regulatory review or customer due diligence.

4. **Build an NLP quality measurement framework with gold-standard evaluation.** Create a benchmark corpus (500+ annotated clinical notes), automate precision/recall/F1 computation per entity type, and run the ensemble against it in CI. This enables data-driven optimization of ensemble weights, confidence thresholds, and extractor selection. Without measurement, all tuning is guesswork.

5. **Implement LLM observability and prompt versioning.** The narrative extractor and coding assistant use LLMs without tracking token usage, latency, output quality, or prompt versions. Add structured logging for every LLM call (model, prompt hash, token count, latency, confidence), version prompts in source control, and build a dashboard for LLM cost/quality monitoring. This is operational hygiene that compounds in value.

---

## Appendix: Module Maturity Summary

| Module | Lines | Maturity | External Dependencies |
|--------|-------|----------|----------------------|
| `nlp_rule_based.py` + supporting modules | ~2,000 | Production | None |
| `nlp_advanced.py` | 904 | Production | None |
| `nlp_clinical_ner.py` | 602 | Pilot | spaCy, transformers, torch |
| `nlp_modernbert_ner.py` | 617 | Pilot | transformers, torch, flash-attn |
| `nlp_ensemble.py` | 605 | Pilot | All NLP dependencies |
| `narrative_extractor.py` | 474 | Pilot | httpx (Ollama), anthropic (Claude) |
| `graph_augmented_rag.py` | 760 | Pilot | SQLAlchemy, KG models |
| `model_registry_service.py` | 364 | Scaffold | None (in-memory) |
| `ml_model_service.py` | 935 | Scaffold | numpy, sklearn |
| `federated_learning_service.py` | 1,603 | Scaffold | numpy, pandas |
| `llm_finetuning.py` (API) | 670 | Scaffold | FastAPI |

---

*This review is based on static code analysis of the repository as of 2026-02-06. Maturity assessments reflect code completeness and test coverage, not runtime validation against production workloads.*
