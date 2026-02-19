# Core Contributions with Code Evidence

## Contribution 1: Epistemic KG Schema — End-to-End Assertion Preservation

### Claim
A 7-value assertion taxonomy carried end-to-end from NLP extraction through OMOP concept mapping, clinical fact construction, KG edge materialization, and graph-augmented retrieval. No prior system preserves epistemic status across all these stages.

### The 7-Value Assertion Enum
**File:** `backend/app/schemas/base.py:8-17`
```python
class Assertion(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"           # Negated
    POSSIBLE = "possible"       # Uncertain
    CONDITIONAL = "conditional" # Conditional statement
    HYPOTHETICAL = "hypothetical" # Hypothetical scenario
    FAMILY_HISTORY = "family_history" # Family history mention
    HISTORICAL = "historical"   # Past/former condition
```

This extends the i2b2 2010 canonical 6-class taxonomy by separating HISTORICAL from FAMILY_HISTORY, providing finer granularity than any standard.

### Stage 1: NLP Extraction — Probabilistic Assertion Classifier
**File:** `backend/app/services/assertion_classifier.py` (501 lines)

The `ProbabilisticAssertionClassifier` provides calibrated confidence scores (not binary classification) using:
- **4 trigger categories:** ABSENT (36 patterns, conf 0.85–0.98), UNCERTAIN (36 patterns, conf 0.30–0.75), HYPOTHETICAL (16 patterns, conf 0.20–0.40), PRESENT (13 patterns, conf 0.85–0.98)
- **Scope-aware matching:** FORWARD, BACKWARD, BIDIRECTIONAL triggers with max_scope_tokens
- **Pseudo-negation handling:** 9 patterns like "no change", "gram negative" that look like negations but aren't
- **Scope termination:** 15 termination patterns ("but", "however", "although", etc.)
- **Priority ordering:** ABSENT > UNCERTAIN > HYPOTHETICAL > PRESENT at equal distance

### Stage 2: Ensemble NLP — Domain-Preference Routing
**File:** `backend/app/services/nlp_ensemble.py:46-80`

The `EnsembleConfig` combines rule-based + ML NER (ModernBERT, 8K context) + value extraction with:
- Agreement boosting: +0.10 when multiple extractors agree
- Domain preferences: measurements → value extraction, drugs → rule-based, conditions → ML NER

Assertion status is preserved on every `ExtractedMention` through the ensemble merge.

### Stage 3: KG Edge Materialization
**File:** `backend/app/services/graph_builder_db.py:1200-1221`

Assertion is stored on KGEdge properties (per-patient semantics on shared concept nodes):
```python
def get_negated_nodes(self, patient_id: str) -> list[NodeInput]:
    """With shared concept nodes, negation is stored on the edge
    (per-patient assertion), not on the node itself."""
```

### Stage 4: Graph-Augmented Retrieval — Assertion-Aware Scoring
**File:** `backend/app/services/graph_augmented_rag.py:1324-1369`

The `_score_and_filter_edges` function scores edges by:
1. Base confidence (temporal_confidence)
2. Query-relevant edge types get +0.2 boost
3. Current temporality preferred over historical (+0.1)
4. Edges below MIN_TRAVERSAL_CONFIDENCE (0.3) are pruned

### Evidence Chain
```
Physician Note → NLP Extraction (assertion_classifier.py: Assertion enum)
  → Ensemble Merge (nlp_ensemble.py: preserved on ExtractedMention)
  → ClinicalFact (fact_builder_db.py: ClinicalFact.assertion field)
  → KGEdge (graph_builder_db.py: edge.properties.assertion)
  → GraphRAG Retrieval (graph_augmented_rag.py: temporality-aware scoring)
```

### Novelty vs. Prior Art
- **i2b2 2010:** 6 classes, extraction-only, no downstream persistence
- **Beyond Negation Detection (2025):** Detection-only, integrated into Spark NLP but unclear KG propagation
- **OMOP CDM:** `condition_status_concept_id` unreliable, negated conditions excluded from CONDITION_OCCURRENCE
- **FHIR:** `verificationStatus` limited to conditions, different taxonomy
- **EpiKG:** 7 classes, persisted through all stages, used in retrieval scoring

---

## Contribution 2: Tri-Temporal KG with Allen's Interval Algebra

### Claim
Three temporal dimensions on KG edges — valid time, transaction time, and NLP-asserted temporality — with 9 Allen interval algebra relations. No prior system combines all three dimensions.

### Tri-Temporal Edge Schema
**File:** `backend/app/models/knowledge_graph.py:190-265`

```
KGEdge:
  # 1. VALID TIME (Event Time)
  event_date      — When the clinical event occurred (point in time)
  valid_from      — When relationship became true (start of validity)
  valid_to        — When relationship ceased (null = ongoing)

  # 2. TRANSACTION TIME (Record Time)
  recorded_at         — When recorded in source system
  source_document_date — Date of source document
  created_at          — When edge created in KG (inherited from Base)

  # 3. TEMPORAL ASSERTION (NLP-derived)
  temporality     — CURRENT / PAST / FUTURE (from NLP extraction)
```

### Allen's 9 Interval Algebra Relations
**File:** `backend/app/schemas/knowledge_graph.py:76-99`

```python
class TemporalOrder(str, Enum):
    BEFORE = "before"       # A ends before B starts
    AFTER = "after"         # A starts after B ends
    DURING = "during"       # A within timespan of B
    CONTAINS = "contains"   # A contains B (inverse of DURING)
    OVERLAPS = "overlaps"   # A overlaps start of B
    STARTS = "starts"       # A starts at same time as B
    FINISHES = "finishes"   # A ends at same time as B
    CONCURRENT = "concurrent" # Approximately same time
    UNKNOWN = "unknown"     # Cannot be determined
```

Stored on `KGEdge.temporal_order` with `temporal_confidence` (0–1 float).

### Temporal Indexes
**File:** `backend/app/models/knowledge_graph.py:281-290`
- `ix_kg_edges_valid_range` — Composite index on (valid_from, valid_to)
- `ix_kg_edges_patient_valid` — Composite index on (patient_id, valid_from)
- `ix_kg_edges_event_date` — Indexed column

### Temporal Context in GraphRAG
**File:** `backend/app/services/graph_augmented_rag.py:112-119`

The `TemporalContext` dataclass provides:
- `event_timeline` — Events in chronological order
- `temporal_conflicts` — Detected conflicts
- `current_state` — What's true now
- `historical_state` — What was true in the past

### Novelty vs. Prior Art
- **MedTKG (2024):** Event time only (1 dimension)
- **Zep/Graphiti (2025):** Bitemporal (valid + transaction) but no NLP-asserted temporality, no clinical domain
- **TEO (2020):** Allen's algebra as annotation ontology, not KG edge attributes
- **TCL (2023):** Allen's algebra as modal logic operators, not stored on edges
- **EpiKG:** Tri-temporal + 9 Allen relations as first-class edge attributes

---

## Contribution 3: Shared Concept Node Architecture

### Claim
Global concept deduplication with patient-specific edges enables both per-patient and cross-patient cohort queries on a unified graph with assertion statistics per concept.

### Shared Node Design
**File:** `backend/app/models/knowledge_graph.py:22-118`

```python
class KGNode(SoftDeleteMixin, Base):
    """Nodes can be:
    - Patient nodes (patient_id set)
    - Shared concept nodes (patient_id=NULL, shared across patients)

    Shared concept nodes are deduplicated by (node_type, omop_concept_id).
    Patient-specific relationships expressed through KGEdge."""
```

### Unique Index for Deduplication
**File:** `backend/app/models/knowledge_graph.py:98-106`
```python
Index(
    "ix_kg_nodes_global_concept",
    "node_type", "omop_concept_id",
    unique=True,
    postgresql_where=text(
        "patient_id IS NULL AND omop_concept_id IS NOT NULL AND deleted_at IS NULL"
    ),
)
```

### Cross-Patient Statistics with Assertion Breakdown
**File:** `backend/app/schemas/knowledge_graph.py:265-276`

```python
class ConceptStatisticsResponse(BaseModel):
    omop_concept_id: int
    concept_name: str
    node_type: str
    patient_count: int
    assertion_breakdown: dict[str, int]  # e.g., {"present": 45, "absent": 12, "possible": 3}
```

### Batch Deduplication in Graph Construction
**File:** `backend/app/services/graph_builder_db.py:470-650`

The `_batch_create_nodes` method:
1. Computes dedup keys, filters cached
2. Batch SELECT for existing shared concepts
3. Separates shared concepts from patient-specific nodes
4. Batch upsert for deduplication

### Novelty vs. Prior Art
- No prior clinical KG system provides per-concept assertion statistics across patients
- Standard KGs either duplicate concept nodes per patient (no cross-patient queries) or lack patient-level assertion semantics
- OntoMerger (2022) handles node deduplication but not assertion-aware statistics

---

## Contribution 4: Assertion-Aware Graph-Augmented Retrieval

### Claim
A 6-step GraphRAG pipeline traversing both patient KG edges and OMOP vocabulary relationships (20M+), with temporality-aware and confidence-weighted scoring.

### 6-Step Pipeline
**File:** `backend/app/services/graph_augmented_rag.py:1-15`

```
1. Extract concepts from query via NLP + OMOP lookup + label fallback
2. Traverse patient KG (2-3 hops, bidirectional BFS)
3. Query temporal context (batch-optimized)
4. Retrieve applicable clinical guidelines (GuidelineRAGService, 1,202 sections)
5. Serialize graph paths as structured context
6. Combine with document retrieval for comprehensive context
```

### Step 1: Hybrid Concept Extraction
**File:** `backend/app/services/graph_augmented_rag.py:397-460`

Three tiers:
1. NLP entity extraction from query text
2. OMOP concept ID enrichment via async DB lookup
3. Label-based fallback matching

### Step 2: Multi-Hop Traversal with OMOP Vocabulary
**File:** `backend/app/services/graph_augmented_rag.py:725-788`

For 2+ hop queries, uses the PG-native `GraphQueryRouter` which traverses **both** `kg_edges` AND `concept_relationships` (20M+ OMOP vocabulary relationships) in a single CTE:

```python
from app.services.neo4j_query_router import GraphQueryRouter, MultiHopQuery
router = GraphQueryRouter(self._session)
query = MultiHopQuery(
    patient_id=patient_id,
    start_concept_ids=start_concept_ids,
    max_hops=max_hops, max_paths=max_paths,
    min_confidence=MIN_TRAVERSAL_CONFIDENCE,
)
router_paths = router.execute_multi_hop(query)
```

### Step 4: Edge Scoring with Temporality Awareness
**File:** `backend/app/services/graph_augmented_rag.py:1324-1369`

```python
def _score_and_filter_edges(edges, query_concepts):
    # Base score = temporal_confidence
    # +0.2 for query-relevant edge types
    # +0.1 for current temporality (vs historical)
    # Pruned if < MIN_TRAVERSAL_CONFIDENCE (0.3)
```

### LLM Prompt Serialization
**File:** `backend/app/services/graph_augmented_rag.py:143-196`

The `GraphAugmentedContext.to_llm_prompt()` method serializes:
- Graph Evidence (paths with confidence + temporality)
- Temporal Context (timeline, current state, conflicts)
- Applicable Policy Rules (from guidelines)
- Retrieved Documents

### Causal Reasoning Integration
**File:** `backend/app/services/graph_augmented_rag.py:42-47`

Causal language patterns (caused by, leads to, side effects, treatment for, etc.) trigger causal reasoning edge traversal.

### Edge Types Supporting Rich Traversal
**File:** `backend/app/schemas/knowledge_graph.py:35-73`

24 edge types including:
- Patient→Entity: has_condition, takes_drug, has_measurement, has_procedure
- Entity→Entity: condition_treated_by, drug_treats, symptom_of, monitors, drug_interaction
- OMOP: has_finding_site, has_morphology
- Narrative: precedes, follows, caused_by, resulted_in, admitted_for, discharged_with
- Provenance: extracted_from, occurred_on

---

## Supporting System Scale

| Component | Scale |
|---|---|
| Clinical calculators | 201 (`calculator_definitions.py`, 12,716 lines) |
| Guideline sections | 1,202 (`guideline_rag_service.py`) |
| OMOP vocabulary relationships | 20M+ (traversed by GraphQueryRouter) |
| NLP ensemble models | 3 (rule-based + ML NER + ModernBERT 8K context) |
| Assertion trigger patterns | 101 total (36 absent + 36 uncertain + 16 hypothetical + 13 present) |
| Benchmark services | MedAgentBench + DR.KNOWS (pre-built) |
| Edge types | 24 (including 8 narrative/causal) |
| Node types | 13 (including 5 narrative/episodic) |
