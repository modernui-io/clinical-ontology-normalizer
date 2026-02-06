# Clinical Ontology Normalizer: Technical Deep Dive

**Prepared for:** HCA Healthcare - Full Stack Engineering & ML Leadership
**Date:** February 2026

---

## Executive Summary

This platform transforms unstructured clinical notes into standardized, queryable medical knowledge. It addresses the core challenge in healthcare IT: **80% of clinical data is trapped in unstructured text**.

**Key Differentiators:**
- **Hybrid NLP Pipeline**: Rule-based (O(n) Aho-Corasick) + ModernBERT (8K context) ensemble
- **OMOP + FHIR Native**: Full terminology standardization with bidirectional interoperability
- **Negation-Aware**: Clinically critical - "no diabetes" ≠ "diabetes"
- **Production-Ready**: HIPAA audit trail, bi-temporal knowledge graphs, confidence quantification

---

## 1. Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         Clinical Data Sources                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ Clinical     │  │ FHIR R4      │  │ HL7v2        │  │ CSV/         │    │
│  │ Notes        │  │ Servers      │  │ Messages     │  │ Flat Files   │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
└─────────┼──────────────────┼──────────────────┼──────────────────┼─────────┘
          │                  │                  │                  │
          ▼                  ▼                  ▼                  ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                       INGESTION LAYER (Kafka + REST)                        │
│  • Streaming: HL7v2 ADT/ORU, FHIR Subscriptions                            │
│  • Batch: Document upload, FHIR $everything, CSV import                    │
│  • De-identification hooks (PHI stripping before processing)               │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                         NLP EXTRACTION LAYER                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    ENSEMBLE ORCHESTRATION                            │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │   │
│  │  │ Rule-Based   │  │ ModernBERT   │  │ Value        │               │   │
│  │  │ Aho-Corasick │  │ NER (8K ctx) │  │ Extraction   │               │   │
│  │  │ O(n) scan    │  │ Flash Attn   │  │ (Labs/Vitals)│               │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │   │
│  │                           │                                          │   │
│  │                  ┌────────┴────────┐                                 │   │
│  │                  │ Span Dedup +    │                                 │   │
│  │                  │ Confidence Merge│                                 │   │
│  │                  └─────────────────┘                                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              ASSERTION CLASSIFICATION (Scope-Aware)                  │   │
│  │  • Negation: "no evidence of", "denies", "ruled out"                │   │
│  │  • Uncertainty: "possible", "likely", "cannot rule out"             │   │
│  │  • Temporality: "history of", "presented with", "plan to"           │   │
│  │  • Experiencer: "mother has", "patient denies"                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                      TERMINOLOGY MAPPING LAYER                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              SQL-Based OMOP Vocabulary (5.36M Concepts)              │   │
│  │                                                                      │   │
│  │  Stage 1: Exact Match (concept_name)        → Score: 1.00           │   │
│  │  Stage 2: Synonym Match (ConceptSynonym)    → Score: 0.95           │   │
│  │  Stage 3: Prefix/Contains Match             → Score: 0.30-0.90      │   │
│  │  Stage 4: Word-Based Jaccard Similarity     → Score: 0.30-1.00      │   │
│  │                                                                      │   │
│  │  Vocabularies: SNOMED-CT, ICD-10, RxNorm, LOINC, CPT, HCPCS         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                        FACT BUILDING LAYER                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      ClinicalFact Construction                       │   │
│  │                                                                      │   │
│  │  Dedup Key: patient_id:omop_concept_id:assertion:temporality        │   │
│  │                                                                      │   │
│  │  Evidence Merge: confidence = 1 - (1-a)(1-b)                        │   │
│  │  (Multiple sources increase confidence, never exceed 1.0)           │   │
│  │                                                                      │   │
│  │  CRITICAL: Negated facts stored separately, not merged              │   │
│  │  "Patient has diabetes" ≠ "Patient denies diabetes"                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                      KNOWLEDGE GRAPH LAYER                                  │
│  ┌────────────────────────────────┐  ┌────────────────────────────────┐   │
│  │  PostgreSQL (Primary Storage)  │  │   Neo4j (Graph Analytics)      │   │
│  │  • KGNode: entities            │  │   • Traversal queries          │   │
│  │  • KGEdge: relationships       │  │   • Path analysis              │   │
│  │  • Bi-temporal semantics       │  │   • Visualization              │   │
│  │  • Vector embeddings (384-dim) │  │   • Graceful degradation       │   │
│  └────────────────────────────────┘  └────────────────────────────────┘   │
│                                                                             │
│  Temporal Model:                                                            │
│  • Valid Time: When clinical event occurred (event_date, valid_from/to)    │
│  • Transaction Time: When recorded (recorded_at, source_document_date)     │
│  • Temporal Assertion: NLP-derived (current, past, future)                 │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                   CLINICAL DECISION SUPPORT LAYER                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Drug         │  │ ICD-10/CPT   │  │ Differential │  │ Clinical     │   │
│  │ Interactions │  │ Suggestions  │  │ Diagnosis    │  │ Calculators  │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                     │
│  │ HCC Gap      │  │ Drug Safety  │  │ Quality      │                     │
│  │ Analysis     │  │ Profiles     │  │ Measures     │                     │
│  └──────────────┘  └──────────────┘  └──────────────┘                     │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                         EXPORT LAYER                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ OMOP CDM     │  │ FHIR R4      │  │ CSV/JSON     │  │ Real-time    │   │
│  │ Export       │  │ Resources    │  │ Bulk Export  │  │ WebSocket    │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. NLP/ML Architecture Deep Dive

### 2.1 Why Hybrid? The Best of Both Worlds

| Approach | Strengths | Weaknesses | Our Use |
|----------|-----------|------------|---------|
| **Rule-Based (Aho-Corasick)** | Deterministic, explainable, fast O(n) | Misses novel expressions | Drugs, labs, known diagnoses |
| **ML NER (ModernBERT)** | Context-aware, handles variation | Slower, less explainable | Conditions, symptoms, procedures |
| **Ensemble** | Combines strengths | Complexity | Overlap boosts confidence |

### 2.2 Aho-Corasick: O(n) Vocabulary Matching

**Why Aho-Corasick instead of regex?**
```
Traditional Regex:    O(n × m) where m = pattern count
                      100K patterns × 50K chars = 5 billion operations

Aho-Corasick:         O(n + z) where z = match count
                      100K patterns × 50K chars = ~50K operations
                      Pattern count doesn't affect time!
```

**Implementation:**
```python
# Build automaton from 150K filtered OMOP concepts
automaton = ahocorasick.Automaton()
for concept in vocabulary:
    for synonym in concept.synonyms:
        automaton.add_word(synonym.lower(), (synonym, concept_id))
automaton.make_automaton()

# Single pass extraction
for end_index, (synonym, concept_id) in automaton.iter(text.lower()):
    if is_word_boundary(text, start, end):
        mentions.append(ExtractedMention(...))
```

### 2.3 ModernBERT: 8K Context with Flash Attention

**Why ModernBERT over ClinicalBERT?**

| Feature | ClinicalBERT | ModernBERT |
|---------|--------------|------------|
| Context window | 512 tokens (~1.2K chars) | 8,192 tokens (~20K chars) |
| Chunking needed | Yes (average note: 2-5K chars) | Rarely |
| Memory scaling | O(n²) attention | O(n) Flash Attention 2 |
| Chunk boundary errors | Common | Eliminated |

**Smart Device Detection:**
```python
if torch.cuda.is_available():
    device = "cuda"
elif torch.backends.mps.is_available():
    device = "mps"  # Apple Silicon
else:
    device = "cpu"
```

### 2.4 Ensemble Merge Strategy

```python
# Priority: domain-specific preferences
domain_preferences = {
    "measurement": "value",      # Regex best for "BP 120/80"
    "drug": "rule_based",        # Vocabulary matching for medications
    "condition": "ml_ner",       # ML best for symptom variation
}

# Overlap resolution (>50% span overlap)
if both_sources_found_entity:
    if domain in preferences:
        keep = preferred_source
    else:
        keep = longer_span or higher_confidence

    # Agreement boost: +0.10 confidence when sources agree
    merged_confidence = min(0.99, base + 0.10)
```

### 2.5 Assertion Classification (Critical for Clinical Accuracy)

**Why This Matters:**
- "Patient has hypertension" → assertion=PRESENT
- "Patient denies hypertension" → assertion=ABSENT
- "Cannot rule out MI" → assertion=POSSIBLE

**If you treat these the same, you get clinically dangerous errors.**

**Scope-Aware Trigger Matching:**
```python
@dataclass(frozen=True)
class AssertionTrigger:
    pattern: str              # "no evidence of"
    category: AssertionCategory  # ABSENT
    confidence: float         # 0.98 (calibrated per trigger)
    scope: TriggerScope       # FORWARD, BACKWARD, BIDIRECTIONAL
    max_scope_tokens: int     # 6 tokens max distance

# Examples (calibrated from clinical validation):
ABSENT_TRIGGERS = [
    ("no evidence of", ABSENT, 0.98, FORWARD),
    ("denies", ABSENT, 0.97, FORWARD),
    ("ruled out", ABSENT, 0.96, BIDIRECTIONAL),
    ("resolved", ABSENT, 0.86, BACKWARD),
]

UNCERTAIN_TRIGGERS = [
    ("possible", UNCERTAIN, 0.55, BIDIRECTIONAL),
    ("cannot rule out", UNCERTAIN, 0.45, FORWARD),
]

# Pseudo-negation handling (override)
# "no change in diabetes" → NOT negated, diabetes is PRESENT
PSEUDO_TRIGGERS = ["no change", "no improvement", "no worsening"]
```

---

## 3. Terminology Mapping Architecture

### 3.1 Why SQL-Based Instead of In-Memory?

**Problem:** OMOP vocabulary = 5.36M concepts. Loading to memory:
- 8+ GB RAM per worker
- 30+ second cold start
- OOM kills in containerized environments

**Solution:** SQL-based with smart indexing:
```sql
-- Indexes for fast lookup
CREATE INDEX ix_concept_name ON concept(concept_name);
CREATE INDEX ix_concept_synonym ON concept_synonym(concept_synonym_name);
CREATE INDEX ix_concept_domain ON concept(domain_id, vocabulary_id);
```

### 3.2 Four-Stage Matching Hierarchy

```
Input: "diabetic nephropathy"

Stage 1: Exact concept_name match
  → "Diabetic nephropathy" = concept_id 443597 (score: 1.00)
  → FOUND, return

Stage 2: Synonym match (if Stage 1 fails)
  → Check ConceptSynonym table
  → "diabetic kidney disease" maps to 443597 (score: 0.95)

Stage 3: Prefix/contains (if Stage 2 fails)
  → LIKE 'diabetic nephropathy%'
  → Score = 0.3 + (input_len / concept_name_len)

Stage 4: Word-based Jaccard (last resort)
  → Extract words: {"diabetic", "nephropathy"}
  → Find concepts with overlapping words
  → Jaccard = |intersection| / |union|
```

### 3.3 Confidence Merge Formula

When multiple sources identify the same clinical fact:

```
merged = 1 - (1 - conf_a) × (1 - conf_b)

Example:
  NLP source: 0.80 confidence
  FHIR import: 0.90 confidence

  merged = 1 - (0.20 × 0.10) = 0.98

Properties:
  • Never exceeds 1.0
  • Converges with more evidence
  • Independent source assumption
```

---

## 4. Knowledge Graph Design

### 4.1 Bi-Temporal Model (Beyond Standard OMOP)

```
Standard OMOP: Single timestamp (event_date)

Our Model: Three temporal dimensions

┌─────────────────────────────────────────────────────────────────┐
│ VALID TIME (When the clinical event occurred)                  │
│   • event_date: Point in time                                  │
│   • valid_from / valid_to: Interval (ongoing = valid_to NULL)  │
├─────────────────────────────────────────────────────────────────┤
│ TRANSACTION TIME (When it was recorded)                        │
│   • recorded_at: Source system timestamp                       │
│   • source_document_date: Document date                        │
│   • created_at: KG insertion time                              │
├─────────────────────────────────────────────────────────────────┤
│ TEMPORAL ASSERTION (NLP-derived)                               │
│   • temporality: current, past, future                         │
│   • temporal_order: before, during, after, concurrent          │
│   • temporal_confidence: 0-1                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Use Case:** "What medications was patient on during their hospitalization?"
```sql
SELECT drug.*
FROM kg_edges e
JOIN kg_nodes drug ON e.target_node_id = drug.id
WHERE e.edge_type = 'TAKES_DRUG'
  AND e.valid_from <= hospitalization_end
  AND (e.valid_to IS NULL OR e.valid_to >= hospitalization_start)
```

### 4.2 Provenance Chain (Full Lineage)

```
User Query: "Why does this patient have diabetes?"
     │
     ▼
ReasoningTrace: Step-by-step query execution
     │
     ▼
ClinicalFact: {concept: "Type 2 DM", assertion: PRESENT, confidence: 0.96}
     │
     ▼
FactEvidence: [
    {type: MENTION, source_id: mention-123, weight: 0.95},
    {type: FHIR_IMPORT, source_id: fhir-456, weight: 1.0}
]
     │
     ▼
Mention: {text: "Type 2 diabetes", document_id: doc-789,
          span: [1234, 1249], section: "Assessment"}
     │
     ▼
Document: {id: doc-789, note_type: "Progress Note",
           created_at: "2024-02-15"}
     │
     ▼
AuditLog: {action: CREATE, user: "nlp_pipeline",
           timestamp: "2024-02-15T10:30:00Z"}
```

---

## 5. FHIR + OMOP Interoperability

### 5.1 Bidirectional Translation

```
FHIR Import:
  Patient (FHIR) → KGNode(PATIENT) + demographics
  Condition → ClinicalFact + KGNode + KGEdge(HAS_CONDITION)
  MedicationRequest → ClinicalFact + KGEdge(TAKES_DRUG)
  Observation → ClinicalFact (lab values)

  Assertion Mapping:
    clinicalStatus=active → assertion=PRESENT
    clinicalStatus=inactive → assertion=ABSENT
    verificationStatus=refuted → assertion=ABSENT

FHIR Export:
  ClinicalFact → Condition (with clinicalStatus from assertion)
  ClinicalFact → MedicationStatement
  ClinicalFact → Observation (labs/vitals)

  Generates proper Bundle with references
```

### 5.2 OMOP CDM Alignment

**Conformance Level:** ~80% aligned with extensions for negation

| OMOP Table | Our Mapping | Notes |
|------------|-------------|-------|
| PERSON | Patient demographics | Full alignment |
| CONDITION_OCCURRENCE | ClinicalFact (assertion=PRESENT only) | Negated excluded |
| DRUG_EXPOSURE | ClinicalFact (assertion=PRESENT only) | Negated excluded |
| MEASUREMENT | ClinicalFact with value/unit | Full alignment |
| NOTE_NLP | **All extractions including negated** | term_exists='N' for ABSENT |

**Critical:** Negated findings preserved in NOTE_NLP, not false-positived into occurrence tables.

---

## 6. Clinical Decision Support

### 6.1 Implemented Capabilities

| Module | Function | Evidence Base |
|--------|----------|---------------|
| Drug Interactions | DDI checking with severity | FDA labels, clinical guidelines |
| Drug Safety | Contraindications, pregnancy/lactation | FDA categories, UpToDate |
| ICD-10 Suggester | Code recommendation with CER | AHA coding guidelines |
| CPT Suggester | Procedure codes with documentation req | CMS documentation |
| HCC Analyzer | Risk adjustment gap analysis | CMS HCC Model V28 |
| Clinical Calculators | 50+ validated tools | Published equations |

### 6.2 Claim-Evidence-Reasoning Framework

Every suggestion includes:
```json
{
  "claim": "E11.22 (Type 2 DM with CKD) is appropriate",
  "evidence": "Documentation: 'diabetic nephropathy', 'creatinine 2.1'",
  "reasoning": "ICD-10 coding guidelines require specificity...",
  "confidence": "HIGH",
  "guidelines": "Use additional code for CKD stage (N18.x)"
}
```

### 6.3 Important Limitations (Transparency)

| Module | Limitation | Mitigation |
|--------|------------|------------|
| Drug Interactions | ~40 core interactions | Expandable via fixtures, integrates RxNorm |
| Differential Dx | ~30 diagnosis templates | Designed as suggestion, not autonomous |
| HCC Analysis | Revenue-focused, compliance risk | Clear documentation, audit trail |
| Condition Matching | Substring search | Planned: fuzzy matching, NLP |

---

## 7. HIPAA Compliance & Audit

### 7.1 Automatic PHI Detection

```python
PHI_PATTERNS = {
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "mrn": r"(?:MRN|mrn)[:\s]*([A-Z0-9]{6,12})",
    "phone": r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "dob": r"\b(?:DOB|dob|Date of Birth)[:\s]*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
}

# Automatic classification of PHI-containing resources
PHI_RESOURCE_TYPES = {"DOCUMENT", "PATIENT", "CLINICAL_FACT", "MENTION", "KG"}
```

### 7.2 Audit Log Schema

```sql
CREATE TABLE audit_log (
    id UUID PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    user_id VARCHAR NOT NULL,
    action VARCHAR NOT NULL,  -- read/create/update/delete/export
    resource_type VARCHAR NOT NULL,
    resource_id VARCHAR,
    patient_id VARCHAR,       -- For patient-centric queries
    phi_accessed BOOLEAN,     -- Critical for compliance reports
    ip_address VARCHAR,
    success BOOLEAN,
    error_message TEXT
);

-- Compliance query indexes
CREATE INDEX ix_audit_user_time ON audit_log(user_id, timestamp);
CREATE INDEX ix_audit_patient_time ON audit_log(patient_id, timestamp);
CREATE INDEX ix_audit_phi ON audit_log(phi_accessed, timestamp);
```

### 7.3 Export Formats

- **JSON:** Full audit records for integration
- **CSV:** Tabular for spreadsheet analysis
- **HIPAA Format:** Standardized compliance report structure

---

## 8. Tech Stack Summary

| Layer | Technology | Why |
|-------|------------|-----|
| **Frontend** | Next.js 16, D3.js, TanStack Query | Modern React SSR, graph visualization |
| **Backend** | FastAPI, SQLAlchemy 2.0 (async) | Async-first, type-safe, auto-docs |
| **Database** | PostgreSQL 16 | Reliability, pg_trgm for fuzzy match |
| **Graph** | Neo4j 5 (optional) | Graph queries, graceful degradation |
| **Queue** | Redis + RQ | Simple, reliable job processing |
| **NLP** | spaCy, ModernBERT, pyahocorasick | Hybrid extraction pipeline |
| **ML** | Transformers, sentence-transformers | BERT-based NER, embeddings |
| **Streaming** | Kafka 7.5 (optional) | HL7v2/FHIR real-time ingestion |
| **Container** | Docker, Kubernetes | Production deployment |

---

## 9. Performance Characteristics

| Operation | Latency | Throughput |
|-----------|---------|------------|
| Document NLP (rule-based) | 50-100ms per page | 100+ docs/minute |
| Document NLP (ModernBERT) | 200-500ms per page | 20-50 docs/minute |
| OMOP concept lookup | 5-15ms | 1000+ queries/sec |
| Knowledge graph build | 100-200ms per patient | Async background |
| FHIR export | 50-100ms per patient | 500+ patients/minute |

---

## 10. Deployment Options

### Local Development
```bash
docker-compose up -d
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Production (Kubernetes)
```bash
kubectl apply -k k8s/overlays/production
```

### Environment Configuration
```bash
# Core services
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://...
NEO4J_URI=bolt://...  # Optional

# ML models
PREWARM_ML_MODELS=true  # Load at startup vs lazy
USE_DB_VOCABULARY=true  # SQL-based vocabulary

# FHIR integration
FHIR_BASE_URL=http://hapi-fhir:8090/fhir
```

---

## 11. What We'd Build Next

1. **Fuzzy condition matching** - Move from substring to embedding-based
2. **Temporal reasoning** - Infer medication durations from clinical context
3. **Active learning** - Feedback loop for NLP model improvement
4. **USCDI compliance** - Full US Core Data for Interoperability alignment
5. **CDS Hooks** - Real-time clinical decision support integration

---

## Contact

For technical questions or demo requests, please reach out.
