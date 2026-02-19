# Related Work: Epistemic Clinical Knowledge Graphs

## 1. Medical RAG and Clinical KG at Top ML Venues (2024–2026)

### 1.1 DoctorRAG (NeurIPS 2025)
- **Authors:** Lu, Fu et al.
- **Contribution:** Emulates doctor-like reasoning by integrating explicit clinical knowledge and implicit case-based experience. Hybrid retrieval with conceptual tags. Med-TextGrad module for output fidelity.
- **URL:** https://arxiv.org/abs/2505.19538
- **Gap:** No patient-specific KG. No assertion/negation modeling. No temporal reasoning.

### 1.2 GFM-RAG (NeurIPS 2025)
- **Authors:** Luo et al.
- **Contribution:** First graph foundation model (8M params) for unseen datasets. Trained on 60 KGs with 14M+ triples. KG-index from documents, pre-trained GNN retriever. SOTA on multi-hop QA.
- **URL:** https://arxiv.org/abs/2502.01113
- **Gap:** General-purpose, not clinical. No OMOP alignment. No assertion or temporal modeling.

### 1.3 MedRAG (WWW 2025)
- **Contribution:** Four-tier hierarchical diagnostic KG. Dynamic integration with similar EHRs for LLM reasoning.
- **URL:** https://arxiv.org/abs/2502.04413
- **Gap:** Disease-centric, not patient-centric. No assertion status. No temporal modeling.

### 1.4 Medical-Graph-RAG (ACL 2025)
- **Authors:** Wu et al.
- **Contribution:** Triple Graph Construction + U-Retrieval linking documents to credible medical sources. Validated on 9 benchmarks + 2 fact-checking datasets.
- **URL:** https://aclanthology.org/2025.acl-long.1381/
- **Gap:** Graph from external sources, not patient notes. No assertion awareness.

### 1.5 KARE (ICLR 2025)
- **Authors:** Jiang et al.
- **Contribution:** KG community-level retrieval (inspired by Microsoft GraphRAG) with LLM reasoning. Multi-source KG from biomedical databases. Outperforms by 10.8–15.0% on MIMIC-III/IV.
- **URL:** https://arxiv.org/abs/2410.04585
- **Gap:** Population-level KG, not patient-level from clinical text. No assertion-aware extraction.

### 1.6 Microsoft GraphRAG (2024)
- **Authors:** Edge et al. (Microsoft Research)
- **Contribution:** Foundational GraphRAG framework. LLM builds entity KG, pregenerates community summaries.
- **URL:** https://arxiv.org/abs/2404.16130
- **Gap:** General-purpose. No clinical ontology, assertion, or temporal modeling.

---

## 2. Clinical KG Construction Systems

### 2.1 Multi-LLM KG-RAG (arXiv, Jan 2026)
- **Contribution:** End-to-end clinical KG from free text. Multi-agent prompting + schema-constrained RAG. Entropy-based uncertainty scoring. Ontology-aligned RDF/OWL (SNOMED CT, LOINC, RxNorm). Applied to PDAC/BRCA oncology cohorts.
- **URL:** https://arxiv.org/abs/2601.01844
- **Gap:** LLM-only extraction. No assertion tracking through pipeline. No bi-temporal modeling. No patient KG.

### 2.2 AutoRD (JMIR Medical Informatics, 2024)
- **Contribution:** End-to-end rare disease KG using GPT-4 with HPO/Orphanet ontologies. Entity extraction F1: 83.5%.
- **URL:** https://medinform.jmir.org/2024/1/e60665
- **Gap:** Literature-focused, not clinical notes. No assertion modeling. No temporal structure.

### 2.3 RECAP-KG (JBI, 2024)
- **Contribution:** KGs from messy GP notes using SNOMED-CT. Handles abbreviations, typos.
- **URL:** https://arxiv.org/abs/2306.17175
- **Gap:** COVID-focused. Limited assertion modeling. No temporal graph. No OMOP.

### 2.4 FHIR-Ontop-OMOP (JBI, 2022)
- **Contribution:** Virtual clinical KGs from OMOP via R2RML mappings to FHIR RDF triples.
- **URL:** https://pmc.ncbi.nlm.nih.gov/articles/PMC9561043/
- **Gap:** From structured OMOP data, not clinical text. No NLP extraction.

---

## 3. Assertion Detection in Clinical NLP

### 3.1 Foundational Work
- **NegEx** (Chapman et al., 2001) — Simple trigger-based negation detection. ~97% accuracy on negation.
- **ConText** (Harkema et al., 2009) — Extended NegEx with temporality + experiencer. 97% negation, 83% hypothetical recall.
- **NegBio** (Peng et al., 2018) — Dependency-graph based negation for radiology.
- **NegBERT** (Khandelwal & Sawant, 2020) — Transformer-based negation detection.

### 3.2 i2b2 2010 Shared Task (Uzuner et al., 2011)
- Established 6-class assertion taxonomy: present, absent, possible, conditional, hypothetical, associated_with_someone_else. 21 systems evaluated. Became the de facto standard. Critically, designed for extraction annotation only — did not address downstream persistence or retrieval.
- **URL:** https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3168320/

### 3.3 Beyond Negation Detection (Gul et al., ECIR 2025)
- Fine-tuned LLM: 0.962 accuracy (vs. GPT-4o: 0.901, commercial APIs lower). Excels on Hypothetical (+23.4%). Integrated into Spark NLP.
- **URL:** https://arxiv.org/abs/2503.17425
- **Gap:** Detection-only — assertion not propagated into KG or used in retrieval.

### 3.4 LLM Assertion Detection (PMC, 2025)
- Tree of Thought, Chain of Thought, LoRA fine-tuning. Micro-F1: 0.89 on i2b2 2010.
- **URL:** https://pmc.ncbi.nlm.nih.gov/articles/PMC11908446/

---

## 4. Temporal Knowledge Graphs (Clinical)

### 4.1 TEO — Time Event Ontology (Li et al., JAMIA 2020)
- Formal temporal ontology with Allen's interval algebra (13 relations). Evaluated on Mayo Clinic EHR data (>95% temporal expression coverage). Handles periodic/recurring events, approximative time.
- **URL:** https://pmc.ncbi.nlm.nih.gov/articles/PMC7647306/
- **Relation to ours:** TEO is an annotation ontology; ours places Allen's relations directly on KG edges as first-class attributes.

### 4.2 MedTKG (IEEE JBHI, 2024)
- Temporal KG with time-stamped snapshots. Integrates SNOMED CT hierarchy. Evaluated on MIMIC-III for future disorder prediction.
- **URL:** https://pubmed.ncbi.nlm.nih.gov/38635388/
- **Gap:** Event time only (single temporal dimension). No assertion status. Focus on prediction.

### 4.3 Zep/Graphiti (arXiv, Jan 2025)
- Bitemporal model: valid time + transaction time on every edge. SOTA on Deep Memory Retrieval (94.8%).
- **URL:** https://arxiv.org/abs/2501.13956
- **Gap:** Conversational AI, not clinical. No NLP-asserted temporality as third dimension. No assertion status. No clinical ontology.

### 4.4 Temporal Clinical Outcome Prediction (arXiv, Feb 2025)
- Patient care pathways as temporal KGs for outcome prediction.
- **URL:** https://arxiv.org/abs/2502.21138
- **Gap:** No assertion-awareness. No valid time vs. transaction time distinction.

### 4.5 Temporal Cohort Logic (PMC, 2023)
- Formalizes Allen's algebra as modal operators for cohort selection.
- **URL:** https://pmc.ncbi.nlm.nih.gov/articles/PMC10148298/

---

## 5. Epistemic Status in Knowledge Representation

### 5.1 ORCA Ontology
- Lightweight ontology for certainty in scientific knowledge. Distinguishes dubitative from doxastic knowledge.
- **URL:** https://experts.illinois.edu/en/publications/formalising-uncertainty-an-ontology-of-reasoning-certainty-and-at

### 5.2 Ontology-Epistemology Divide (Ceusters & Smith, 2015)
- Biomedical terms represent not just reality but states of knowledge/ignorance: detectability, modality, uncertainty, vagueness.
- **URL:** https://pmc.ncbi.nlm.nih.gov/articles/PMC4346778/

### 5.3 Uncertainty in Biomedical KGs (Computers in Biology and Medicine, 2024)
- Quantifies uncertainty of KG facts from textual evidence. Confidence scores by averaging factuality across evidence. One of few works modeling uncertainty at the KG fact level.
- **URL:** https://pubmed.ncbi.nlm.nih.gov/39541901/

---

## 6. Clinical Standards

### 6.1 OMOP CDM
- `condition_status_concept_id` added in v5.3 but has no designated vocabulary. Negated conditions explicitly excluded from CONDITION_OCCURRENCE (stored in OBSERVATION). Fundamentally loses assertion status for uncertain/negated conditions during ETL.

### 6.2 FHIR
- `Condition.verificationStatus`: unconfirmed, provisional, differential, confirmed, refuted, entered-in-error. Richer than OMOP but limited to conditions, no "possible", "conditional", or "family_history".

### 6.3 SNOMED CT
- Post-coordination supports assertion-like semantics but rarely implemented in production. Assertion tied to terminology layer, not persisted as KG metadata.

---

## 7. Surveys

### 7.1 Patient-Centric KG Survey (Al Khatib et al., Frontiers AI, 2024)
- Comprehensive PCKG survey. Identifies temporal relationships as frequently overlooked. Multi-hop reasoning superior to single-hop. Does NOT identify assertion preservation as a concern.
- **URL:** https://arxiv.org/abs/2402.12608

### 7.2 Healthcare KG Systematic Review (Abu-Salih et al., J Big Data, 2023)
- First taxonomy of healthcare KG construction (~560 articles). Assertion status not identified as concern — suggesting it is an overlooked problem.
- **URL:** https://journalofbigdata.springeropen.com/articles/10.1186/s40537-023-00774-9

### 7.3 GraphRAG Survey (ACM TOIS, 2025)
- No surveyed system models assertion status or clinical epistemic status.
- **URL:** https://dl.acm.org/doi/10.1145/3777378

---

## 8. Gap Analysis Summary

### The Assertion Preservation Gap

| System | Assertion Detection | Assertion in Facts | Assertion in KG | Assertion in Query/RAG |
|---|---|---|---|---|
| cTAKES | Yes (NegEx + module) | Annotation only | No | No |
| medSpaCy | Yes (ConText) | Annotation only | No | No |
| Spark NLP Healthcare | Yes (6-class) | Yes (triples) | Unclear | Unclear |
| OMOP CDM | condition_status_concept_id | Partial (conditions only) | N/A | Unreliable |
| FHIR | verificationStatus | Yes (conditions only) | N/A | N/A |
| **EpiKG (ours)** | **Yes (7-class)** | **Yes (ClinicalFact.assertion)** | **Yes (KGEdge.properties)** | **Yes (filtering in RAG)** |

**Conclusion:** No published system demonstrates end-to-end assertion preservation from NLP extraction through knowledge graph construction to query-time retrieval.

### The Temporal Modeling Gap

| System | Valid Time | Transaction Time | NLP Temporality | Allen's Algebra |
|---|---|---|---|---|
| MedTKG | Event time only | No | No | No |
| Zep/Graphiti | t_valid, t_invalid | Yes | No | No |
| TEO | Annotation-level | No | No | Yes (13 relations) |
| **EpiKG (ours)** | **event_date, valid_from/to** | **recorded_at, source_doc_date** | **CURRENT/PAST/FUTURE** | **9 relations on edges** |

### The Integrated System Gap

| Capability | DoctorRAG | GFM-RAG | MedRAG | Med-Graph-RAG | KARE | Multi-LLM KG | MedTKG | **EpiKG** |
|---|---|---|---|---|---|---|---|---|
| Patient-level KG from notes | No | No | Partial | No | No | No | Yes | **Yes** |
| OMOP concept mapping | No | No | No | Partial | Partial | SNOMED | No | **Yes** |
| Full assertion status (7 types) | No | No | No | No | No | No | No | **Yes** |
| Tri-temporal modeling | No | No | No | No | No | No | Partial | **Yes** |
| Assertion-aware retrieval | No | No | No | No | No | No | No | **Yes** |
| Experiencer tracking | No | No | No | No | No | No | No | **Yes** |
| Allen's temporal algebra | No | No | No | No | No | No | No | **Yes** |
| Graph-augmented RAG | No | Yes | Yes | Yes | Yes | No | No | **Yes** |
