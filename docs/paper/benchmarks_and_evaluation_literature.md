# Benchmarks and Evaluation Literature for Epistemic Clinical Knowledge Graphs

**Target venue**: NeurIPS 2026
**Last updated**: 2026-02-18
**Purpose**: Literature survey to inform experimental design, baseline selection, and evaluation protocol

---

## Table of Contents

1. [Clinical NLP Benchmarks and Evaluation](#1-clinical-nlp-benchmarks-and-evaluation)
2. [Evaluation Methodologies for Clinical NLP Systems](#2-evaluation-methodologies-for-clinical-nlp-systems)
3. [Required Baselines](#3-required-baselines)
4. [RAG Evaluation Methods](#4-rag-evaluation-methods)
5. [Knowledge Graph Evaluation](#5-knowledge-graph-evaluation)
6. [Scalability Benchmarks](#6-scalability-benchmarks)
7. [Evaluation Protocol Design](#7-evaluation-protocol-design)
8. [Benchmark Gaps](#8-benchmark-gaps)

---

## 1. Clinical NLP Benchmarks and Evaluation

### 1.1 MedAgentBench

- **What it evaluates**: Agent capabilities of LLMs within medical records contexts. 300 patient-specific clinically derived tasks across 10 categories, written by physicians. Covers 100 realistic patient profiles with over 700,000 data elements in a FHIR-compliant interactive environment.
- **Key metrics**: Task success rate (binary pass/fail per task), overall success rate across categories.
- **Top result**: Claude 3.5 Sonnet achieved the best overall success rate of 69.67% across 12 SOTA LLMs evaluated.
- **Key finding**: Significant variation across task categories indicates current systems are not yet reliable clinical agents.
- **Version 2**: In development for Biocomputing 2026 proceedings, focusing on improving LLM agent design.
- **URL**: https://github.com/stanfordmlgroup/MedAgentBench
- **Publication**: NEJM AI (https://ai.nejm.org/doi/full/10.1056/AIdbp2500144)
- **Relevance**: Directly relevant for evaluating our system's end-to-end clinical reasoning capabilities. The FHIR-compliant environment aligns with our architecture.

### 1.2 DR.KNOWS (Diagnostic Reasoning Knowledge Graph System)

- **What it evaluates**: Diagnostic reasoning quality using knowledge graph-augmented LLMs. Integrates UMLS-based knowledge graphs with LLMs to improve diagnostic predictions from EHR data.
- **Evaluation methodology**: (1) CUI-based Recall/Precision/F1 for concept prediction, (2) ROUGE-L for text generation quality, (3) Human evaluation framework derived from clinical diagnostic safety metrics.
- **Key results**: Prompt-based fine-tuning achieved highest ROUGE-L and CUI F1-scores. Human evaluators found KG-augmented LLM rationales superior to LLM-only rationales.
- **Datasets**: Two real-world EHR datasets from different geographic locations; 4,815 progress notes with SNOMED CT disease/syndrome concepts as ground truth.
- **Publication**: JMIR AI 2025 (https://ai.jmir.org/2025/1/e58670)
- **Relevance**: Directly comparable architecture (KG + LLM for clinical reasoning). Their human evaluation framework is a model for our own evaluation design.

### 1.3 DRAGON Benchmark

- **What it evaluates**: Comprehensive multi-task clinical NLP benchmark with 28 tasks and 28,824 annotated medical reports from five care centers.
- **Key metrics**: DRAGON 2025 test score (0-1 scale, unweighted average of primary metric across all 28 tasks and 5 training runs per task).
- **Key results**: Domain-specific pretraining (0.770) > mixed-domain pretraining (0.756) > general-domain pretraining (0.734, p < 0.005).
- **Note**: Based on Dutch clinical text; cross-lingual generalization would need to be assessed separately.
- **Publication**: npj Digital Medicine 2025 (https://www.nature.com/articles/s41746-025-01626-x)
- **Relevance**: Multi-task evaluation design is a good template for demonstrating system breadth.

### 1.4 MIRAGE (Medical Information Retrieval-Augmented Generation Evaluation)

- **What it evaluates**: RAG systems for medical QA. First benchmark specifically for medical RAG. 7,663 questions from five medical QA datasets.
- **Datasets included**: MMLU-Med (1,089 questions across 6 biomedical tasks), MedQA (medical board exams), PubMedQA, BioASQ, and others.
- **Key metrics**: Accuracy on medical QA with/without retrieval augmentation, zero-shot evaluation, question-only retrieval.
- **Key findings**: MedRAG improves LLM accuracy by up to 18% over chain-of-thought prompting. Discovered log-linear scaling property and "lost-in-the-middle" effects in medical RAG.
- **URL**: https://github.com/Teddy-XiongGZ/MIRAGE
- **Publication**: ACL Findings 2024 (https://aclanthology.org/2024.findings-acl.372/)
- **Relevance**: Primary benchmark for evaluating our GraphRAG component against standard RAG baselines.

### 1.5 Medical QA Benchmarks

#### MedQA
- **What it measures**: Medical knowledge via USMLE-style board exam questions.
- **Scale**: ~12,000+ questions.
- **SOTA performance**: GPT-5 reached 95.84% accuracy (late 2025); Med-Gemini achieved 91.1%.
- **Limitation**: MedQA is the most predictive of clinical performance (Spearman rho = 0.59) but fails to capture patient communication, longitudinal care, and clinical information extraction.
- **URL**: https://www.vals.ai/benchmarks/medqa

#### PubMedQA
- **What it measures**: Biomedical research comprehension from PubMed abstracts (yes/no/maybe).
- **SOTA**: Medical-LLM-78B at 79.6%.
- **Relevance**: Tests evidence synthesis capabilities relevant to our RAG pipeline.

#### emrQA
- **What it measures**: QA over electronic medical records, using templates derived from clinical questions.
- **Relevance**: Closest to our use case of querying patient-specific clinical knowledge graphs.

#### MedMCQA
- **What it measures**: Multi-choice medical QA from Indian medical entrance exams (AIIMS/NEET).
- **Scale**: ~194,000 questions across 2,400 healthcare topics.
- **SOTA**: Yi-34B at 72.6% (OpenMedLM).

#### MedCalc-Bench
- **What it measures**: LLM ability to perform medical calculations (dosing, scoring, etc.).
- **Publication**: OpenReview (https://openreview.net/forum?id=VXohja0vrQ)
- **Relevance**: Tests computational reasoning, relevant to our calculator services.

### 1.6 Assertion Detection Benchmarks

#### i2b2 2010 Assertion Task
- **What it evaluates**: Classification of medical problem mentions into 6 assertion categories: Present, Absent, Associated with Someone Else, Conditional, Hypothetical, Possible.
- **Dataset**: Clinical narratives from the 2010 i2b2/VA shared task.
- **Key results (2025 SOTA)**: Fine-tuned LLM approaches achieve 0.962 overall accuracy, outperforming GPT-4o (0.901) and commercial APIs (AWS Comprehend Medical, Azure AI Text Analytics).
- **Category-specific gains**: Present (+4.2%), Absent (+8.4%), Hypothetical (+23.4%) over GPT-4o.
- **Publication**: 2010 challenge: PMC3168320; 2025 assertion models: arxiv.org/abs/2503.17425
- **Relevance**: Core evaluation for our assertion detection pipeline. The i2b2 dataset is the standard benchmark we must report on.

#### NegEx / ConText Baselines
- **What they detect**: NegEx: negation only. ConText extends to temporality (recent/historical/hypothetical) and experiencer (patient/other).
- **Performance**: ConText on ED reports: Negation (97% recall, 97% precision), Hypothetical (83% recall, 94% precision), Historical (lower performance).
- **Status**: Legacy rule-based systems; remain standard baselines that all new systems must surpass.

### 1.7 MEDIQA Shared Tasks (ClinicalNLP Workshop)

#### MEDIQA-CORR 2024
- **Focus**: Medical error detection and correction in clinical text.
- **Venue**: NAACL-ClinicalNLP 2024.

#### MEDIQA-WV 2025
- **Focus**: Woundcare visual question answering (multimodal clinical QA).
- **Venue**: ClinicalNLP 2025.

#### MEDIQA-EVAL @ ClinicalNLP 2026
- **Focus**: Evaluating metrics for multimodal question answering.
- **URL**: https://www.codabench.org/competitions/12115/
- **Relevance**: The 2026 shared task specifically on evaluation metrics could directly inform our evaluation protocol.

### 1.8 BioKGBench

- **What it evaluates**: Biomedical AI agents' ability to understand literature and interact with knowledge graphs. Two atomic tasks: (1) scientific claim verification from papers, (2) KG question answering (KGQA). Plus a combined agent task (KGCheck) using KGQA + RAG to identify factual errors in KGs.
- **Scale**: 2,000+ data points for atomic tasks, 225 high-quality annotated samples for agent task.
- **Key finding**: SOTA general and biomedical agents performed poorly, indicating significant room for improvement.
- **URL**: https://github.com/westlake-autolab/BioKGBench
- **Publication**: arxiv.org/abs/2407.00466
- **Relevance**: Directly evaluates KG + agent capabilities. The KGCheck task (finding errors in KGs) is closely aligned with epistemic KG quality assurance.

### 1.9 Concept Normalization Shared Tasks

#### n2c2 2019 Clinical Concept Normalization
- **What it evaluates**: Mapping of medical problem/treatment/test mentions to UMLS CUIs (SNOMED CT + RxNorm).
- **Scale**: 100 discharge summaries, 10,919 concept mentions, 3,792 unique concepts.
- **Key results**: Best team accuracy 0.8526; median 0.7733; mean 0.7426. 33 teams participated.
- **Baseline**: Sieve-based normalization achieves 77% accuracy in cross-validation.
- **IAA**: 67.69% pre-adjudication, 74.20% post-adjudication (indicating task difficulty).
- **URL**: https://n2c2.dbmi.hms.harvard.edu/2019-track-3
- **Publication**: PMC7647359

#### SemEval 2014 Task 7 / SemEval 2015 Task 14
- **What they evaluate**: Clinical text analysis including disorder identification and normalization.
- **Relevance**: Earlier iterations of concept normalization evaluation; establish historical baselines.

---

## 2. Evaluation Methodologies for Clinical NLP Systems

### 2.1 Entity Extraction Evaluation

**Strict (Exact) Matching**:
- A true positive requires both entity boundaries AND entity type to exactly match gold standard annotations.
- Most rigorous evaluation; standard for published results.

**Relaxed (Partial/Lenient) Matching**:
- A true positive requires entity type match AND boundary overlap (not exact match).
- More forgiving of minor span boundary errors.

**Token-Based Metrics**:
- Evaluate at individual token level rather than entity span level.
- Tolerates minor boundary errors; intermediate strictness.

**Standard Metrics**: Precision, Recall, F1-score computed under each matching regime.

**Best Practice**: Report both strict and relaxed F1 scores. The clinical NLP community expects strict matching as the primary metric with relaxed matching for context.

### 2.2 Concept Normalization / Mapping Evaluation

**Accuracy**: Percentage of mentions correctly mapped to the target concept (CUI).

**Top-k Accuracy**: Whether the correct CUI appears in the top-k candidates (k=1, 5, 10).

**OMOP-Specific Evaluation**: A transformer-based model achieved 96.5% mapping accuracy for the 200 most common drugs and 83.0% for 200 random drugs in EHR data, outperforming Usagi (OHDSI's standard tool) and direct string matching.

**Challenge**: Mapping accuracy degrades significantly for rare/long-tail concepts. The gap between common (96.5%) and random (83.0%) drug mapping illustrates this.

### 2.3 Assertion / Negation Evaluation

**Standard Task**: 6-class classification on i2b2 2010 categories.

**Metrics**: Per-class precision/recall/F1, macro-averaged F1, overall accuracy.

**Baseline Hierarchy** (ascending performance):
1. NegEx (rule-based, negation only) -- legacy baseline
2. ConText (rule-based, negation + temporality + experiencer)
3. AssertionDL (deep learning, John Snow Labs)
4. Commercial APIs: AWS Comprehend Medical, Azure AI Text Analytics
5. GPT-4o (zero-shot): 0.901 accuracy
6. Fine-tuned clinical LLMs: 0.962 accuracy (current SOTA)

### 2.4 Knowledge Graph Quality Evaluation

**Intrinsic Dimensions**:
- **Accuracy**: Syntactic accuracy (grammar/schema compliance), semantic accuracy (correctness of facts), timeliness (currency of information).
- **Coverage/Completeness**: Extent to which the KG represents the relevant domain.
- **Consistency**: Freedom from contradictions.
- **Density**: Compactness of the graph (edges per node).

**Quantitative Metrics**:
- Node count, edge count, degree distribution (max, average), network density.
- Complex network analysis metrics.

**Human Evaluation**:
- Sampling-based accuracy estimation (humans annotate KG triples as correct/incorrect).
- Key challenge: keeping annotation costs low while maintaining statistical significance.

**KG Embedding Evaluation**:
- Link prediction (MRR, Hits@k).
- Triple classification accuracy.
- Benchmarks: PharmKG (500K+ interconnections), Know2BIO (219K nodes, 6.2M edges).

### 2.5 Inter-Annotator Agreement (IAA)

**Metrics**: Cohen's Kappa (2 annotators), Fleiss' Kappa (3+ annotators), Intra-Class Correlation (ICC).

**Protocol**:
1. Develop evaluation guidelines
2. Train evaluators
3. Initial evaluation on subset
4. Discussion and adjudication
5. Refine guidelines
6. Full annotation

**Key Finding**: Annotators with medical training judge clinical content systematically differently from those without -- medical expertise is essential for clinical NLP annotation.

---

## 3. Required Baselines

### 3.1 Entity Extraction Baselines

| System | Type | Capabilities | Why Required |
|--------|------|-------------|--------------|
| **cTAKES** | Rule-based + ML | NER, assertion, relation extraction, concept mapping to UMLS | Industry-standard open-source clinical NLP. Most-cited baseline. |
| **MedSpaCy** | Rule-based + spaCy | Context detection (negation, experiencer, temporality), section tagging, document classification | Purpose-built for clinical text; strong context/assertion detection. |
| **scispaCy** | Statistical NER | Biomedical NER, entity linking to UMLS/MeSH/GO/HPO | Best in class for abbreviation extraction (F1: 0.86). Widely used academic baseline. |
| **Stanza Biomedical** | Neural (CharLM + CRF) | 8 biomedical NER models + 2 clinical NER models | Outperforms scispaCy on NER; competitive with BioBERT. More computationally efficient than transformer baselines. |
| **MetaMap** | Rule-based | UMLS concept identification, word sense disambiguation | NLM's official tool; gold standard for UMLS concept mapping. |
| **QuickUMLS** | Approximate dictionary matching | Fast UMLS concept extraction | 135x faster than MetaMap/cTAKES with comparable precision/recall. Essential throughput baseline. |
| **CLAMP** | Hybrid (rule + ML) | Clinical NER, assertion, relation extraction | Best F1 on i2b2 exact matching (0.70) and inexact matching (0.94). |
| **Spark NLP Healthcare** | Distributed neural | 600+ pretrained models, NER, assertion, relation extraction, de-identification | Commercial SOTA; outperforms AWS/Azure/GCP by 12-18%. Throughput baseline (80x faster than spaCy). |

### 3.2 Assertion Detection Baselines

| System | Approach | Performance (i2b2) | Why Required |
|--------|----------|-------------------|--------------|
| **NegEx** | Rule-based triggers | ~97% on negation only | Historical baseline; any system must surpass |
| **ConText** | Rule-based triggers | 97%/97% negation; 83%/94% hypothetical | Extended baseline covering all assertion types |
| **AssertionDL** | Deep learning | Competitive with SOTA | John Snow Labs' production system |
| **GPT-4o** | Zero-shot LLM | 0.901 accuracy | Commercial LLM baseline |
| **Fine-tuned clinical LLMs** | Domain-adapted LLM | 0.962 accuracy | Current SOTA to beat |

### 3.3 Concept Normalization Baselines

| System | Top-1 Accuracy (n2c2) | Notes |
|--------|----------------------|-------|
| **Sieve-based baseline** | 77% | Provided with shared task |
| **Best n2c2 system** | 85.26% | Top of 33 competing teams |
| **LLM-augmented** | +7.3% to +21.7% F1 gain | Multi-step LLM + traditional tools |
| **Transformer OMOP mapper** | 96.5% (common drugs) | Newer work specific to OMOP |

### 3.4 RAG Baselines

| System | Approach | Why Required |
|--------|----------|--------------|
| **MedRAG** | KG-elicited reasoning + RAG | SOTA for medical RAG; up to 18% improvement over CoT |
| **Vanilla RAG (BM25 + LLM)** | Standard retrieve-and-generate | Naive baseline; GraphRAG must demonstrably beat this |
| **Chain-of-thought (no retrieval)** | LLM reasoning only | Shows value of retrieval augmentation |

---

## 4. RAG Evaluation Methods

### 4.1 RAGAS Framework Metrics

| Metric | What It Measures | Scale |
|--------|-----------------|-------|
| **Faithfulness** | Factual consistency of response with retrieved context | 0-1 (higher = better) |
| **Answer Relevancy** | How well the response addresses the query | 0-1 |
| **Context Precision** | Proportion of retrieved context that is relevant | 0-1 |
| **Context Recall** | Proportion of needed information that was retrieved | 0-1 |
| **Answer Correctness** | Semantic similarity to ground truth | 0-1 |

### 4.2 Retrieval Metrics

| Metric | Use Case |
|--------|----------|
| **nDCG@k** (k=10 standard) | Ranked retrieval quality; captures position sensitivity. Primary metric for BEIR and TREC DL tracks. |
| **Recall@k** (k=100, 1000) | Coverage of relevant documents in top-k results |
| **Precision@k** | Fraction of top-k that are relevant |
| **MRR** (Mean Reciprocal Rank) | Rank of first relevant result |

### 4.3 Medical Domain-Specific RAG Evaluation

**MIRAGE Benchmark Protocol**:
- Zero-shot evaluation (no demonstrations)
- Question-only retrieval (no answer options given to retriever)
- 41 combinations of corpora x retrievers x LLMs
- Report accuracy improvement over no-retrieval baseline

**Hallucination Detection** (from Cleanlab benchmarking):
- TLM (Trustworthiness Language Model) was most effective for biomedical hallucination detection
- RAGAS Faithfulness provided moderate effectiveness
- LLM self-evaluation was weakest approach

**GraphRAG-Bench Evaluation Protocol** (ICLR 2026):
- Multi-level tasks: fact retrieval (L1), complex reasoning (L2+), contextual summarization, creative generation.
- Evaluates full pipeline: graph construction, knowledge retrieval, answer generation.
- Assesses logical coherence of reasoning process, not just final answer correctness.
- Key caveat: GraphRAG frequently underperforms vanilla RAG on many tasks; must demonstrate clear scenarios where graph structure helps.

**BRINK (Benchmark for Reasoning under Incomplete Knowledge)**:
- Evaluates KG-RAG methods under knowledge incompleteness.
- Particularly relevant for epistemic KGs where uncertainty is explicit.

### 4.4 Human Evaluation Protocols for RAG

**DR.KNOWS Human Evaluation Framework**:
- Derived from diagnostic safety evaluations used in clinical settings.
- Assesses LLMs as diagnostic decision support systems.
- Evaluators compare KG-augmented vs. non-KG-augmented rationales.
- Strong face validity and reliability for evaluating model strengths/weaknesses.

**Standard Human Evaluation Protocol**:
1. Develop evaluation guidelines with clinical domain experts
2. Train evaluators (require medical expertise for clinical content)
3. Pilot evaluation on subset; compute IAA (Cohen's Kappa >= 0.7 target)
4. Adjudication process for disagreements
5. Full evaluation with >= 2 independent annotators per sample
6. Report IAA alongside results

---

## 5. Knowledge Graph Evaluation

### 5.1 Biomedical KG Benchmarks

| Benchmark | Scale | Focus |
|-----------|-------|-------|
| **PharmKG** | 500K+ interconnections (genes, drugs, diseases) | Drug discovery, multi-relational |
| **Know2BIO** | 219K nodes, 6.2M edges | Dual-view biomedical KG; evolving benchmark |
| **PheKnowLator** | Large-scale heterogeneous | Semantically-rich biomedical KG construction |
| **Clinical KG (general)** | 16M+ entities possible | Broad clinical coverage |
| **SNOMED-CT** | Hundreds of thousands of terms | Standard clinical terminology |

### 5.2 KG Quality Metrics

**Structural Metrics**:
- Node count, edge count, density (edges / possible edges)
- Degree distribution: mean degree, max degree, degree histogram
- Connected component analysis
- Clustering coefficient

**Semantic Metrics**:
- Triple accuracy (sampled human annotation)
- Ontology compliance (valid concept types, relation types)
- Temporal consistency (no contradictory temporal assertions)

**Task-Based Metrics**:
- Link prediction: MRR, Hits@1, Hits@10
- Triple classification accuracy
- Downstream task improvement (QA accuracy gain from KG augmentation)

### 5.3 KG Scaling Studies

- Biomedical KGs now reach 200M+ triples
- Graph databases struggle with complex analytics at millions of nodes
- Hybrid architectures (sharding, cloud graph services) are emerging solutions
- SPARQL/Cypher query scaling remains nontrivial at scale

---

## 6. Scalability Benchmarks

### 6.1 Clinical NLP Throughput

| System | Throughput | Notes |
|--------|-----------|-------|
| **QuickUMLS** | 135x faster than MetaMap/cTAKES | Approximate dictionary matching |
| **Spark NLP** | 80x faster than spaCy training; 34% faster than HuggingFace (CPU), 51% faster (GPU) | Distributed processing capable |
| **Optimized pipeline** | 17ms per record (down from 206ms = 12x improvement) | On 550K note corpus |
| **Distributed (Spark)** | Tokenization 20x faster, entity extraction 3.5x faster in cluster mode | vs. standalone mode |

### 6.2 How Clinical NLP Papers Report Throughput

**Standard metrics**:
- Notes/documents per second (or per minute)
- Milliseconds per record
- Total wall-clock time for corpus size

**Scaling techniques reported**:
1. Pipeline replication via multi-threading
2. Intra-annotator threading (decomposing individual annotator tasks)
3. Remote annotator services (scale-out to cluster)

**Energy efficiency metrics** (emerging):
- Tokens per Wh
- Wh per 1,000 notes processed
- kWh per 1,000 patients per year

### 6.3 Knowledge Graph Scaling

- Clinical KGs can reach 16M+ entities in production
- Processing pipelines must handle millions of notes
- Key bottleneck: concept normalization/entity linking (most computationally expensive step)
- Graph query latency matters for interactive applications (target: <100ms for clinical decision support)

---

## 7. Evaluation Protocol Design

### 7.1 Entity Extraction Experiments

**Datasets**: i2b2 2010, MIMIC-III annotated subsets
**Metrics**:
- Strict F1 (primary)
- Relaxed F1 (secondary)
- Per-entity-type breakdown (problems, treatments, tests)
**Baselines**: cTAKES, scispaCy, Stanza, CLAMP, Spark NLP Healthcare
**Statistical test**: Bootstrap confidence intervals, McNemar's test for pairwise comparisons

### 7.2 Assertion Detection Experiments

**Dataset**: i2b2 2010 assertion task
**Metrics**:
- Overall accuracy
- Per-class F1 (Present, Absent, Hypothetical, Possible, Conditional, Associated with Someone Else)
- Macro F1
**Baselines**: NegEx, ConText, AssertionDL, GPT-4o (zero-shot), fine-tuned clinical LLMs
**Analysis**: Confusion matrix per class; error analysis on Hypothetical vs. Possible (known hard distinction)

### 7.3 Concept Normalization Experiments

**Dataset**: n2c2 2019 MCN corpus, SemEval 2014/2015 clinical tasks
**Metrics**:
- Top-1 accuracy (primary)
- Top-5 accuracy
- Accuracy stratified by concept frequency (common vs. rare)
**Baselines**: Sieve-based, MetaMap, QuickUMLS, SOTA neural approaches, LLM-augmented
**OMOP-specific**: Evaluate mapping to OMOP standard concepts using Athena vocabulary as reference

### 7.4 Knowledge Graph Quality Experiments

**Metrics**:
- Structural: node/edge counts, density, degree distribution
- Semantic: sampled triple accuracy (human annotation, n >= 200)
- Epistemic: calibration of confidence scores (ECE, Brier score)
- Task-based: downstream QA accuracy improvement
**Baselines**: DR.KNOWS, standard UMLS-based KG construction
**Novel metrics for epistemic KG**: Uncertainty calibration, selective prediction (accuracy vs. coverage curves)

### 7.5 RAG / GraphRAG Experiments

**Datasets**: MIRAGE benchmark (7,663 questions), MedQA, PubMedQA
**Retrieval metrics**: nDCG@10, Recall@100, Recall@1000
**Generation metrics**: RAGAS Faithfulness, Answer Relevancy, Answer Correctness
**Baselines**: Vanilla RAG (BM25), MedRAG, chain-of-thought (no retrieval)
**GraphRAG-specific**: Use GraphRAG-Bench protocol (fact retrieval, complex reasoning, summarization)
**Hallucination measurement**: TLM-based detection, RAGAS Faithfulness, expert annotation on sample

### 7.6 Scalability Experiments

**Metrics**:
- Throughput: notes per second at varying batch sizes
- Latency: p50, p95, p99 for individual note processing
- KG query latency: time for graph traversal at varying graph sizes (10K, 100K, 1M, 10M nodes)
- Memory footprint
**Baselines**: QuickUMLS (speed), Spark NLP (distributed), cTAKES (traditional)

### 7.7 End-to-End Clinical Reasoning

**Dataset**: MedAgentBench (300 tasks, 100 patient profiles)
**Metrics**: Task success rate per category, overall success rate
**Baselines**: Results for 12 LLMs already published (Claude 3.5 Sonnet at 69.67% as top)
**Analysis**: Per-category breakdown to identify where KG augmentation helps most

---

## 8. Benchmark Gaps

### 8.1 No Benchmark for Epistemic Knowledge Graphs

**Gap**: No existing benchmark evaluates KGs where edges carry explicit uncertainty/confidence scores. Current KG benchmarks assume binary true/false triples.

**What we need**: An evaluation framework for:
- Calibration of edge confidence scores (does 0.8 confidence mean 80% of those triples are true?)
- Selective prediction on KG queries (abstaining when uncertain)
- Uncertainty propagation through multi-hop reasoning
- Impact of epistemic annotations on downstream clinical decisions

**Recommendation**: Create a new evaluation dataset by annotating a subset of clinical KG triples with expert-assessed confidence, then measure calibration metrics (ECE, Brier score) and selective prediction curves.

### 8.2 No Standard for Assertion-Aware KG Evaluation

**Gap**: Assertion detection is evaluated at the mention level (i2b2 task), and KG quality is evaluated at the triple level, but there is no benchmark evaluating whether assertion status is correctly propagated from extracted mentions into KG edges.

**What we need**: Evaluation of end-to-end assertion-to-graph fidelity:
- A negated finding correctly excluded from positive assertions in the KG
- A hypothetical condition correctly tagged with epistemic uncertainty
- Temporal assertions correctly reflected in graph temporality

### 8.3 Limited Evaluation of KG-Augmented RAG in Clinical Settings

**Gap**: GraphRAG-Bench and MIRAGE evaluate general medical QA but not patient-specific clinical reasoning over structured patient graphs. BioKGBench evaluates literature KGs, not patient-level clinical KGs.

**What we need**: A benchmark that evaluates:
- Retrieval from patient-specific subgraphs
- Reasoning that requires combining KG structure with unstructured clinical notes
- Multi-hop clinical queries (e.g., "What medications is this patient on that interact with their new diagnosis?")

### 8.4 Concept Normalization to OMOP (vs. UMLS)

**Gap**: Most concept normalization benchmarks target UMLS CUIs. OMOP uses a different concept hierarchy with standard/non-standard concept distinctions, vocabulary versioning, and concept relationships that differ from UMLS.

**What we need**: An OMOP-specific concept normalization benchmark with:
- Mapping accuracy for standard concepts across domains (conditions, drugs, procedures, measurements)
- Evaluation of concept hierarchy navigation (e.g., mapping to correct granularity level)
- Assessment of temporal vocabulary changes (concept deprecation, replacement)

### 8.5 Cross-Pipeline Evaluation

**Gap**: Most benchmarks evaluate individual components (NER, assertion, normalization) in isolation. No benchmark evaluates error propagation through a full pipeline (extract -> assert -> normalize -> build graph -> query).

**What we need**: End-to-end pipeline evaluation that measures:
- Compound error rates (how NER errors cascade into incorrect KG triples)
- Pipeline robustness (sensitivity to upstream component quality)
- Overall clinical utility (does the full system answer clinical questions correctly?)

### 8.6 Longitudinal and Temporal Evaluation

**Gap**: Current benchmarks use static snapshots. No benchmark evaluates how well systems handle evolving patient records over time, including:
- Updating KGs as new notes arrive
- Resolving contradictions between old and new information
- Tracking disease progression through temporal graph evolution

### 8.7 Throughput Under Clinical Constraints

**Gap**: Scalability benchmarks report throughput on batch processing but rarely evaluate real-time clinical decision support scenarios (target: <2 seconds for point-of-care queries, <100ms for graph traversals).

**What we need**: Latency-focused benchmarks under realistic clinical workloads (concurrent users, mixed query types, real-time note ingestion).

---

## References Summary

### Primary Benchmarks to Use

1. **i2b2 2010** -- entity extraction + assertion detection (PMC3168320)
2. **n2c2 2019** -- concept normalization (PMC7647359)
3. **MIRAGE** -- medical RAG evaluation (ACL Findings 2024)
4. **MedAgentBench** -- end-to-end clinical agent (NEJM AI)
5. **GraphRAG-Bench** -- graph-augmented RAG (ICLR 2026)
6. **BioKGBench** -- KG agent evaluation (arxiv 2407.00466)

### Key Comparison Papers

1. DR.KNOWS -- KG + LLM for diagnosis (JMIR AI 2025)
2. Clinical concept recognition comparison -- 6-system benchmark (Frontiers AI 2022)
3. Assertion detection beyond negation -- comprehensive models (arxiv 2503.17425)
4. Benchmarking biomedical entity linking -- 9-model comparison (PMC11097978)
5. DRAGON -- multi-task clinical NLP (npj Digital Medicine 2025)

### Epistemic Uncertainty References

1. Towards Trustworthy AI in Healthcare: Epistemic Uncertainty Estimation (PMC11856777)
2. Reasoning over Uncertain Knowledge Graphs (EMNLP 2025)
3. Medical Hallucination in Foundation Models (medRxiv 2025)
4. Modeling unknowns: uncertainty-aware ML in healthcare (ScienceDirect 2025)

### Evaluation Framework References

1. RAGAS documentation -- https://docs.ragas.io/
2. KG Quality Management survey (IEEE TKDE, 10.1109/TKDE.2021.3070843)
3. Human evaluation framework for LLMs in healthcare (PMC11437138)
4. Inter-annotator agreement methodology (PubMed 29295103)
