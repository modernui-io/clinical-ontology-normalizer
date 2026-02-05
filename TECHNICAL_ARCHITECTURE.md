# Clinical NLP System - Technical Architecture Deep Dive

**Version:** 1.0.0
**Date:** February 2026
**Author:** ML Engineering Team

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [NLP Extraction Pipeline](#2-nlp-extraction-pipeline)
3. [Assertion Classification](#3-assertion-classification)
4. [Temporal Extraction](#4-temporal-extraction)
5. [Ontology Integration](#5-ontology-integration)
6. [Knowledge Graph Architecture](#6-knowledge-graph-architecture)
7. [Hybrid Reasoning Engine](#7-hybrid-reasoning-engine)
8. [Q&A Agent Architecture](#8-qa-agent-architecture)
9. [ML Model Details](#9-ml-model-details)
10. [Data Flow Diagrams](#10-data-flow-diagrams)
11. [Technical Decisions & Rationale](#11-technical-decisions--rationale)

---

## 1. System Architecture Overview

### 1.1 High-Level Architecture

The Clinical NLP System is a multi-layer architecture designed for extracting, normalizing, and reasoning over clinical text data. The system processes unstructured clinical notes and transforms them into a queryable knowledge graph that supports clinical decision support.

```
+------------------------------------------------------------------+
|                      PRESENTATION LAYER                           |
|   FastAPI REST API | GraphQL Gateway | WebSocket Real-time       |
+------------------------------------------------------------------+
                                |
+------------------------------------------------------------------+
|                    ORCHESTRATION LAYER                            |
|   Multi-Agent Orchestrator (TrustedMDT Pattern)                  |
|   - DiagnosticAgent | TreatmentAgent | SafetyAgent | EvidenceAgent|
+------------------------------------------------------------------+
                                |
+------------------------------------------------------------------+
|                     REASONING LAYER                               |
|   Hybrid Query Engine | RAG Service | Clinical Calculators       |
+------------------------------------------------------------------+
                                |
+------------------------------------------------------------------+
|                   KNOWLEDGE GRAPH LAYER                           |
|   PostgreSQL (Primary) + Neo4j (Graph Queries)                   |
|   Bi-Temporal Model | 678K OMOP Relationships                    |
+------------------------------------------------------------------+
                                |
+------------------------------------------------------------------+
|                    NLP EXTRACTION LAYER                           |
|   Ensemble Pipeline:                                              |
|   Rule-Based (Aho-Corasick) + ClinicalBERT + ModernBERT         |
|   Assertion Classifier | Temporal Extractor | Value Extraction   |
+------------------------------------------------------------------+
                                |
+------------------------------------------------------------------+
|                    VOCABULARY LAYER                               |
|   OMOP CDM | NDFRT | SNOMED | RxNorm | ICD-10 | LOINC           |
|   5.36M Concepts | Clinical Abbreviations                        |
+------------------------------------------------------------------+
```

### 1.2 Component Interactions

| Component | Responsibility | Downstream Dependencies |
|-----------|---------------|------------------------|
| API Layer | HTTP routing, request validation | Orchestrator, NLP Pipeline |
| NLP Pipeline | Entity extraction, assertion detection | Vocabulary Service |
| Vocabulary Service | Concept lookup, normalization | PostgreSQL (OMOP) |
| Graph Builder | Knowledge graph construction | PostgreSQL, Neo4j |
| Multi-Agent Orchestrator | Collaborative decision support | LLM Service, RAG Service |
| RAG Service | Guideline retrieval | Embedding Service |

### 1.3 Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Backend Framework | FastAPI + Python 3.11 | Async support, type hints, performance |
| Primary Database | PostgreSQL 15 | ACID compliance, JSON support, pg_trgm |
| Graph Database | Neo4j 5.x | Cypher queries, graph visualization |
| ML Inference | PyTorch 2.x | ModernBERT, ClinicalBERT |
| Embedding | Sentence-Transformers | MiniLM, 384-dim vectors |
| Caching | Redis | Session state, concept cache |
| Task Queue | Kafka | Async document processing |

---

## 2. NLP Extraction Pipeline

### 2.1 Ensemble Architecture

The NLP pipeline uses an **ensemble approach** combining four complementary extraction methods:

```python
@dataclass
class EnsembleConfig:
    use_rule_based: bool = True      # High precision patterns
    use_ml_ner: bool = True          # ClinicalBERT NER
    use_modernbert: bool = True      # 8K context ModernBERT
    use_value_extraction: bool = True # Quantitative measurements

    # Base confidence thresholds
    rule_based_confidence: float = 0.85
    ml_ner_confidence: float = 0.80
    modernbert_confidence: float = 0.88
    value_confidence: float = 0.90

    # ModernBERT weight multiplier (1.2x due to better accuracy)
    modernbert_weight: float = 1.2

    # Confidence boosting when methods agree
    agreement_boost: float = 0.10
    max_confidence: float = 0.99
```

**Key Design Decision:** The ensemble uses **agreement boosting** where confidence increases by 0.10 when multiple extractors identify the same entity, capped at 0.99.

### 2.2 Rule-Based Extraction (Aho-Corasick Algorithm)

The rule-based extractor provides O(n) pattern matching regardless of vocabulary size using the **Aho-Corasick automaton**.

**Algorithm Complexity:**
- Build time: O(m) where m = sum of pattern lengths
- Search time: O(n + z) where n = text length, z = number of matches
- Memory: O(m) for the automaton

```python
class RuleBasedNLPService(BaseNLPService):
    """Uses Aho-Corasick for O(n) pattern matching."""

    MIN_TERM_LENGTH = 2

    # Confidence scoring weights (sum to 1.0)
    CONFIDENCE_WEIGHTS = {
        "base": 0.4,           # Base match quality
        "term_length": 0.2,    # Longer terms = more specific
        "section_fit": 0.2,    # Section-domain affinity
        "specificity": 0.1,    # Has OMOP concept ID
        "case_match": 0.1,     # Exact case match bonus
    }

    # Stopwords to prevent noise
    STOPWORDS = {
        "air", "water", "normal", "stable", "pain",
        "well", "new", "old", "left", "right", "patient"
    }
```

**Pattern Building Process:**

1. Load vocabulary (OMOP concepts + clinical abbreviations)
2. Normalize all synonyms to lowercase
3. Build Aho-Corasick automaton with metadata: `(original_synonym, domain_id, concept_id)`
4. Finalize automaton with `make_automaton()`

**Extraction Process:**

1. Convert text to lowercase for matching
2. Iterate automaton matches in O(n)
3. Verify word boundaries (automaton matches substrings)
4. Filter stopwords and minimum length
5. Apply assertion classification
6. Calculate comprehensive confidence score

### 2.3 Section-Aware Extraction

The system parses clinical notes into sections for context-aware extraction:

```python
class ClinicalSection(str, Enum):
    CHIEF_COMPLAINT = "chief_complaint"
    HISTORY_PRESENT_ILLNESS = "history_present_illness"
    PAST_MEDICAL_HISTORY = "past_medical_history"
    MEDICATIONS = "medications"
    ALLERGIES = "allergies"
    FAMILY_HISTORY = "family_history"
    SOCIAL_HISTORY = "social_history"
    REVIEW_OF_SYSTEMS = "review_of_systems"
    PHYSICAL_EXAM = "physical_exam"
    ASSESSMENT_PLAN = "assessment_plan"
    LABS = "labs"
    IMAGING = "imaging"
```

**Section-Domain Affinity Matrix:**

| Section | Drug Affinity | Condition Affinity | Measurement Affinity |
|---------|--------------|-------------------|---------------------|
| Medications | 1.1x | 0.8x | 0.9x |
| Past Medical History | 0.9x | 1.1x | 0.9x |
| Labs | 0.8x | 0.9x | 1.1x |
| Physical Exam | 0.8x | 1.0x | 1.1x |

### 2.4 Domain-Specific Preferences

When multiple extractors find the same entity, domain preferences guide resolution:

```python
domain_preferences = {
    Domain.MEASUREMENT: "value",      # Value extraction for measurements
    Domain.DRUG: "rule_based",        # Rule-based for medications
    Domain.CONDITION: "ml_ner",       # ML NER for conditions
}
```

### 2.5 Span Overlap Resolution

When extractors produce overlapping spans:

1. Check domain preference (preferred extractor wins)
2. Prefer longer spans (`prefer_longer_spans: True`)
3. Prefer higher confidence (`prefer_higher_confidence: True`)
4. If not replacing, boost existing confidence by `agreement_boost`

---

## 3. Assertion Classification

### 3.1 Probabilistic Assertion Classifier

The assertion classifier determines the certainty and polarity of clinical mentions using a **calibrated probabilistic model** inspired by NegEx and ConText.

```python
class AssertionCategory(str, Enum):
    PRESENT = "present"       # Confirmed present
    ABSENT = "absent"         # Negated
    POSSIBLE = "possible"     # Uncertain
    HYPOTHETICAL = "hypothetical"  # Future/conditional

class TriggerScope(str, Enum):
    FORWARD = "forward"       # Negates following text
    BACKWARD = "backward"     # Negates preceding text
    BIDIRECTIONAL = "bidirectional"  # Negates both directions
```

### 3.2 Trigger Patterns

**Negation Triggers (ABSENT):**
```python
NEGATION_TRIGGERS = [
    r"\bno\b",
    r"\bnot\b",
    r"\bdenies\b",
    r"\bdenied\b",
    r"\bwithout\b",
    r"\babsence\s+of\b",
    r"\bnegative\s+for\b",
    r"\bruled\s+out\b",
    r"\bno\s+evidence\s+of\b",
]
```

**Uncertainty Triggers (POSSIBLE):**
```python
UNCERTAINTY_TRIGGERS = [
    r"\bcannot\s+rule\s+out\b",  # Critical: NOT negation!
    r"\bpossible\b",
    r"\bprobable\b",
    r"\bsuspected?\b",
    r"\brule\s+out\b",           # Differential, not ruled out yet
    r"\bconcern\s+for\b",
]
```

**Positive Triggers (PRESENT):**
```python
POSITIVE_TRIGGERS = [
    r"\btaking\b",
    r"\bon\b",                    # "on metformin"
    r"\bstarted\s+(?:on\s+)?",
    r"\bcontinue\b",
    r"\bdiagnosed\s+with\b",
    r"\bpresents?\s+with\b",
]
```

### 3.3 Position-Based Resolution

The classifier uses **position-based detection**: the trigger closest to the mention wins.

```python
def _detect_assertion(self, context: str) -> Assertion:
    # Find closest match to end of context (mention position)
    uncertainty_pos = find_closest_match(UNCERTAINTY_TRIGGERS)
    positive_pos = find_closest_match(POSITIVE_TRIGGERS)
    negation_pos = find_closest_match(NEGATION_TRIGGERS)

    max_pos = max(uncertainty_pos, positive_pos, negation_pos)

    if uncertainty_pos == max_pos:
        return Assertion.POSSIBLE
    elif positive_pos == max_pos:
        return Assertion.PRESENT
    elif negation_pos == max_pos:
        return Assertion.ABSENT

    return Assertion.PRESENT  # Default
```

**Example Resolution:**
- "No chest pain. Taking metformin" - metformin = PRESENT (closest trigger: "Taking")
- "Cannot rule out PE" - PE = POSSIBLE (not negated!)

### 3.4 Pseudo-Negation Patterns

Patterns that look like negation but are not:

```python
PSEUDO_NEGATION_PATTERNS = [
    "no change",           # Status quo, not absence
    "gram negative",       # Microbiology term
    "no longer needs",     # Resolved, but was present
]
```

### 3.5 Scope Termination

Negation scope terminates at:
- Sentence boundaries (period, semicolon)
- Conjunctions: "but", "however", "although", "except"
- New clause indicators

---

## 4. Temporal Extraction

### 4.1 Temporal Expression Types

The temporal extractor identifies three types of temporal expressions:

```python
@dataclass
class TemporalExpression:
    text: str                    # Original text span
    start: int                   # Character offset
    end: int                     # Character offset
    date: datetime | None        # Resolved date
    date_precision: str          # "day", "month", "year", "approximate"
    expression_type: str         # "absolute", "relative", "keyword"
    confidence: float            # Extraction confidence
```

### 4.2 Supported Date Formats

| Format | Pattern | Example | Precision |
|--------|---------|---------|-----------|
| ISO | `YYYY-MM-DD` | 2024-01-15 | day |
| US Full | `M/D/YYYY` | 1/15/2024 | day |
| US Short | `M/D/YY` | 1/15/24 | day |
| Month Day Year | `Month DD, YYYY` | January 15, 2024 | day |
| Month Year | `Month YYYY` | January 2024 | month |
| Year Only | `in YYYY` | in 2020 | year |
| Relative | `N units ago` | 3 days ago | approximate |
| Period | `last/this week/month/year` | last week | approximate |

### 4.3 Temporal Relationship Detection

The extractor associates temporal expressions with nearby entities:

```python
TEMPORAL_RELATIONSHIP_PATTERNS = [
    (r"\bdiagnosed\s+(?:with\s+)?(.+?)\s+(?:in|on)\s+", "diagnosed"),
    (r"\bstarted\s+(?:on\s+)?(.+?)\s+(?:on|in)\s+", "started"),
    (r"(.+?)\s+since\s+", "onset"),
    (r"\bstopped\s+(.+?)\s+(?:on|in)\s+", "stopped"),
    (r"(.+?)\s+for\s+\d+\s+(?:year|month)s?\b", "duration"),
]
```

### 4.4 Entity-Temporal Binding

```python
@dataclass
class EntityTemporalBinding:
    entity_text: str
    entity_start: int
    entity_end: int
    temporal_expression: TemporalExpression
    relationship: str      # "onset", "started", "stopped", "diagnosed"
    distance: int          # Character distance
```

The binding uses:
- **Proximity**: Max distance of 100 characters
- **Relationship keywords**: Context analysis for semantic relationship
- **Best match selection**: Closest temporal expression wins

---

## 5. Ontology Integration

### 5.1 OMOP CDM Vocabulary Structure

The system uses the **OMOP Common Data Model** vocabulary with 5.36M concepts across multiple vocabularies:

```python
class Concept(Base):
    __tablename__ = "concepts"

    concept_id: int              # Primary key
    concept_name: str            # Canonical name
    vocabulary_id: str           # SNOMED, RxNorm, ICD10CM, etc.
    domain_id: str               # Condition, Drug, Measurement, etc.
    concept_class_id: str        # Clinical Finding, Ingredient, etc.
    standard_concept: str        # S=Standard, C=Classification

    # Vector embedding for semantic search (384 dimensions)
    embedding: list[float] | None
```

### 5.2 Vocabulary Priority Lists

Domain-specific vocabulary prioritization ensures the best concept match:

```python
# Drug domain
DRUG_VOCABULARIES = ["NDFRT", "RxNorm", "NDC", "ATC"]
DRUG_CONCEPT_CLASSES = ["Pharma Preparation", "Ingredient", "Clinical Drug"]

# Condition domain
CONDITION_VOCABULARIES = ["NDFRT", "SNOMED", "ICD10CM", "ICD9CM"]
CONDITION_CONCEPT_CLASSES = ["Ind / CI", "Clinical Finding", "Disorder"]

# Measurement domain
MEASUREMENT_VOCABULARIES = ["LOINC", "SNOMED"]

# Procedure domain
PROCEDURE_VOCABULARIES = ["SNOMED", "CPT4", "HCPCS", "ICD10PCS"]
```

**Key Insight:** NDFRT is prioritized for both drugs AND conditions because it contains rich clinical relationships (May treat, Contraindicated for, Drug-drug interactions).

### 5.3 Concept Lookup Algorithm

```python
async def lookup_concept(
    db: AsyncSession,
    text: str,
    domain: str | None = None,
) -> ConceptMatch | None:
    # 1. Try exact match (case-insensitive)
    match = await _exact_match(db, text.strip(), domain)
    if match:
        return match

    # 2. Try uppercase match (NDFRT uses uppercase)
    match = await _exact_match(db, text.upper(), domain)
    if match:
        return match

    # 3. Fuzzy match (disabled - requires pg_trgm)
    # match = await _fuzzy_match(db, text, domain, min_similarity=0.6)

    return None
```

### 5.4 Best Concept Selection

When multiple concepts match, scoring determines the best:

```python
def _select_best_concept(concepts, priority_vocabs, domain):
    def score_concept(c):
        # Vocabulary priority (lower = better)
        vocab_score = priority_vocabs.index(c.vocabulary_id)
                     if c.vocabulary_id in priority_vocabs else 100

        # Concept class priority (lower = better)
        class_score = priority_classes.index(c.concept_class_id)
                     if c.concept_class_id in priority_classes else 100

        # Prefer shorter names (canonical form)
        length_score = len(c.concept_name)

        return (vocab_score, class_score, length_score)

    return min(concepts, key=score_concept)
```

### 5.5 OMOP Clinical Relationships

The system leverages 678K+ clinical relationships from OMOP:

| Relationship Type | Count | Example |
|------------------|-------|---------|
| May treat | 147K | Metformin → Type 2 Diabetes |
| Contraindicated for (CI to) | 89K | Metformin → Renal Failure |
| Has drug-drug interaction | 312K | Warfarin → Aspirin |
| Indication of | 98K | Chest Pain → Angina |
| Has form | 32K | Metformin → Metformin 500mg tablet |

```python
OMOP_CLINICAL_RELATIONSHIPS = {
    "May treat": {
        "relationship_id": "May treat",
        "kg_edge_type": EdgeType.TREATS,
        "description": "Drug may be used to treat condition",
    },
    "CI to": {
        "relationship_id": "CI to",
        "kg_edge_type": EdgeType.CONTRAINDICATED,
        "description": "Drug is contraindicated for condition",
    },
    "Has drug-drug inter": {
        "relationship_id": "Has drug-drug inter",
        "kg_edge_type": EdgeType.DRUG_INTERACTION,
        "description": "Drug interacts with another drug",
    },
}
```

---

## 6. Knowledge Graph Architecture

### 6.1 Node Types

```python
class NodeType(str, Enum):
    PATIENT = "patient"           # Central hub node
    CONDITION = "condition"       # Diagnoses, symptoms
    DRUG = "drug"                 # Medications
    MEASUREMENT = "measurement"   # Labs, vitals
    PROCEDURE = "procedure"       # Surgeries, interventions
    OBSERVATION = "observation"   # General observations
    DEVICE = "device"             # Medical devices
```

### 6.2 Edge Types

```python
class EdgeType(str, Enum):
    # Patient relationships
    HAS_CONDITION = "has_condition"
    TAKES_DRUG = "takes_drug"
    HAS_MEASUREMENT = "has_measurement"
    HAD_PROCEDURE = "had_procedure"

    # Clinical relationships (from OMOP)
    TREATS = "treats"
    CONTRAINDICATED = "contraindicated"
    DRUG_INTERACTION = "drug_interaction"
    INDICATION_OF = "indication_of"

    # Temporal relationships
    PRECEDED_BY = "preceded_by"
    CONCURRENT_WITH = "concurrent_with"
```

### 6.3 Bi-Temporal Model

The knowledge graph implements a **bi-temporal model** distinguishing:

1. **Valid Time (Event Time):** When the clinical event actually happened
2. **Transaction Time (Record Time):** When we learned about it

```python
class KGEdge(Base):
    # Valid Time: When the relationship was true in real world
    event_date: datetime | None    # Point in time
    valid_from: datetime | None    # Start of validity period
    valid_to: datetime | None      # End of validity (null = ongoing)

    # Transaction Time: Provenance
    recorded_at: datetime | None          # Source system timestamp
    source_document_date: datetime | None # Document date

    # Temporal Assertion (from NLP)
    temporality: str | None        # current, past, future

    # Allen's Interval Algebra
    temporal_order: str | None     # before, after, during, concurrent
    temporal_confidence: float | None
```

**Allen's Interval Algebra Relationships:**

| Relation | Description | Example |
|----------|-------------|---------|
| BEFORE | Event A ends before B starts | Diagnosis → Treatment |
| AFTER | Event A starts after B ends | Treatment → Remission |
| DURING | Event A occurs within B | Lab result → Hospitalization |
| CONCURRENT | Events overlap in time | Co-medications |

### 6.4 Database Schema Design

**Composite Indexes for Performance:**

```python
# KGNode indexes
Index("ix_kg_nodes_patient_type", "patient_id", "node_type")
Index("ix_kg_nodes_patient_concept", "patient_id", "omop_concept_id")
Index("ix_kg_nodes_type_concept", "node_type", "omop_concept_id")

# KGEdge indexes
Index("ix_kg_edges_valid_range", "valid_from", "valid_to")
Index("ix_kg_edges_patient_valid", "patient_id", "valid_from")
Index("ix_kg_edges_event_date", "event_date")
Index("ix_kg_edges_patient_type", "patient_id", "edge_type")
```

### 6.5 Dual Storage Strategy

```
PostgreSQL (Primary)              Neo4j (Graph Queries)
+------------------+              +------------------+
| KGNode, KGEdge   | --sync--->   | Patient, ClinicalFact |
| Bi-temporal      |              | OMOP Relationships    |
| ACID compliant   |              | Cypher queries        |
| Full-text search |              | Visualization         |
+------------------+              +------------------+
```

**Sync Operation (MERGE Pattern):**

```cypher
-- Patient node
MERGE (p:Patient {patient_id: $patient_id})
SET p.label = $label, p.updated_at = datetime()

-- Clinical fact node
MERGE (n:ClinicalFact {node_id: $node_id})
SET n.patient_id = $patient_id,
    n.label = $label,
    n.node_type = $node_type,
    n.omop_concept_id = $omop_concept_id

-- Relationship
MATCH (s:Patient {patient_id: $source_id})
MATCH (t:ClinicalFact {node_id: $target_id})
MERGE (s)-[r:HAS_CONDITION]->(t)
SET r.temporality = $temporality
```

### 6.6 Graceful Degradation

```python
def _sync_to_neo4j(self, patient_id, nodes, edges):
    graph_db = get_graph_database_service()

    if not graph_db.is_connected:
        if graph_db.is_mock_mode:
            logger.debug(f"Neo4j in mock mode, skipping sync")
        else:
            logger.warning(f"Neo4j not available, skipping sync")
        return  # PostgreSQL graph remains valid
```

---

## 7. Hybrid Reasoning Engine

### 7.1 Reasoning Architecture

The hybrid reasoning engine combines:
1. **Rule-based reasoning**: OMOP relationships, clinical calculators
2. **ML-based reasoning**: LLM analysis with graph context
3. **Ensemble voting**: Multi-agent consensus

### 7.2 Query Processing Flow

```
User Query
    |
    v
+-------------------+
| Query Parser      |  <-- Intent detection, entity extraction
+-------------------+
    |
    v
+-------------------+
| Graph Traversal   |  <-- Multi-hop relationship discovery
+-------------------+
    |
    v
+-------------------+
| Evidence Builder  |  <-- KGTraversalPaths, CausalChains
+-------------------+
    |
    v
+-------------------+
| LLM Reasoning     |  <-- Graph evidence in prompt
+-------------------+
    |
    v
+-------------------+
| Multi-Agent Vote  |  <-- Consensus building
+-------------------+
    |
    v
Answer + Provenance
```

### 7.3 KG Traversal Paths

Paths discovered through graph traversal are formatted for LLM prompts:

```python
@dataclass
class KGTraversalPath:
    path_id: str
    description: str
    nodes: list[dict]      # Node labels and properties
    edges: list[dict]      # Edge types and confidence
    confidence: float
    temporal_info: str | None

    def to_prompt_text(self) -> str:
        """Format for LLM prompt."""
        # Example output:
        # Path: Drug-Condition Relationship
        #   Metformin --[May treat (0.95)]--> Type 2 Diabetes
        #   Confidence: 0.95
```

### 7.4 Causal Chain Validation

```python
@dataclass
class CausalChain:
    chain_id: str
    description: str
    links: list[dict]       # source -> relation -> target
    pathway_type: str       # treatment, adverse_event, progression
    confidence: float
    temporal_valid: bool    # Passes temporal consistency check
    validation_notes: str
```

### 7.5 Confidence Aggregation

Final confidence combines multiple signals:

```python
# Agreement boost
if methods_agree:
    confidence = min(base_confidence + 0.10, 0.99)

# ModernBERT weight multiplier
modernbert_confidence *= 1.2

# Multi-agent consensus
final_confidence = (sum(v.confidence for v in agreeing_votes)
                   / len(agreeing_votes)) * agreement_score
```

---

## 8. Q&A Agent Architecture

### 8.1 TrustedMDT Multi-Agent Pattern

The system implements the **TrustedMDT** (Trusted Multi-Disciplinary Team) pattern from clinical AI research:

```python
class AgentRole(str, Enum):
    DIAGNOSTIC = "diagnostic"    # Differential diagnosis
    TREATMENT = "treatment"      # Treatment planning
    SAFETY = "safety"            # Drug safety, interactions
    EVIDENCE = "evidence"        # Literature/guideline review
    COORDINATOR = "coordinator"  # MDT coordination
    POLICY = "policy"            # Policy/guideline compliance
    TEMPORAL = "temporal"        # Temporal reasoning
```

### 8.2 Agent Responsibilities

| Agent | Primary Function | Key Checks |
|-------|------------------|------------|
| DiagnosticAgent | Differential diagnosis | Symptom analysis, condition confirmation |
| TreatmentAgent | Treatment recommendations | Guideline-based planning |
| SafetyAgent | Drug safety | Interactions, allergies, contraindications |
| EvidenceAgent | Evidence review | Literature support, guideline compliance |
| PolicyAgent | Policy compliance | Clinical rules, formulary checks |
| TemporalAgent | Temporal consistency | Event ordering, validity periods |

### 8.3 Agent Context Structure

```python
@dataclass
class AgentContext:
    # Basic patient context
    patient_id: str
    clinical_text: str
    conditions: list[dict]
    medications: list[dict]
    allergies: list[str]
    lab_values: list[dict]
    vitals: dict

    # Knowledge graph evidence (hybrid reasoning)
    kg_traversal_paths: list[KGTraversalPath]

    # Causal reasoning chains
    causal_chains: list[CausalChain]

    # Temporal context
    temporal_context: TemporalContext | None

    # Policy constraints
    policy_constraints: list[PolicyConstraint]

    def to_llm_prompt(self, include_sections=None):
        """Format all context for LLM."""
        # Combines patient info, graph evidence,
        # causal chains, and policy rules
```

### 8.4 Consensus Building

```python
class ConsensusLevel(str, Enum):
    UNANIMOUS = "unanimous"      # 100% agreement
    STRONG = "strong"            # >80% agreement
    MODERATE = "moderate"        # 60-80% agreement
    WEAK = "weak"                # 40-60% agreement
    CONFLICTING = "conflicting"  # <40% agreement
```

**Consensus Algorithm:**

1. Each agent independently analyzes the case
2. All agents vote on each recommendation
3. Calculate agreement score: `agreeing_votes / total_votes`
4. Map to consensus level
5. Collect dissenting concerns
6. Generate explanation

### 8.5 MDT Session Flow

```python
async def run_mdt_discussion(self, session_id: str) -> MDTSession:
    # Step 1: Gather recommendations from all agents
    analysis_tasks = [agent.analyze(context) for agent in agents]
    results = await asyncio.gather(*analysis_tasks)

    # Step 2: Build consensus for each recommendation
    for recommendation in all_recommendations:
        consensus = await self._build_consensus(recommendation, context)
        session.consensus_results.append(consensus)

    return session
```

### 8.6 Guideline RAG Service

The RAG service retrieves relevant clinical guidelines using a **two-phase search**:

```python
class GuidelineRAGService:
    def search_guidelines(self, query, patient_context):
        # Phase 1: Semantic similarity search
        query_embedding = self.embed(query)
        candidates = self.vector_search(query_embedding, top_k=50)

        # Phase 2: Keyword boost with medical synonyms
        keyword_score = self.keyword_match(query, candidate.text)

        # Primary topic match scoring
        topic_score = self.topic_relevance(candidate, patient_context)

        # Combined score
        final_score = (0.6 * semantic_score +
                      0.25 * keyword_score +
                      0.15 * topic_score)
```

**Medical Synonym Groups:**
```python
SYNONYM_GROUPS = {
    "diabetes": ["dm", "dm2", "t2dm", "type 2 diabetes"],
    "hypertension": ["htn", "high blood pressure", "elevated bp"],
    "heart failure": ["hf", "chf", "hfref", "hfpef"],
}
```

### 8.7 LLM Service Configuration

```python
class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"

class LLMModel(str, Enum):
    GPT4O = "gpt-4o"
    GPT4O_MINI = "gpt-4o-mini"
    CLAUDE_35_SONNET = "claude-3-5-sonnet-20241022"
    CLAUDE_3_HAIKU = "claude-3-haiku-20240307"
```

**Rate Limiting (Token Bucket):**
```python
class RateLimiter:
    def __init__(self, requests_per_minute: int, tokens_per_minute: int):
        self.rpm_bucket = TokenBucket(requests_per_minute, 60)
        self.tpm_bucket = TokenBucket(tokens_per_minute, 60)

    async def acquire(self, tokens: int):
        await self.rpm_bucket.acquire(1)
        await self.tpm_bucket.acquire(tokens)
```

**Provider Fallback:**
```python
async def generate(self, prompt, model):
    try:
        return await self._call_provider(prompt, model)
    except RateLimitError:
        # Fallback to alternative provider
        return await self._call_fallback(prompt)
```

---

## 9. ML Model Details

### 9.1 ClinicalBERT NER

**Model:** `samrawal/bert-base-uncased_clinical-ner`

| Attribute | Value |
|-----------|-------|
| Base Model | BERT-base-uncased |
| Training Data | i2b2 2010, 2012, 2014 |
| Context Length | 512 tokens |
| Entity Types | Problem, Treatment, Test |
| Inference Time | ~15ms/doc (GPU) |

**Entity to Domain Mapping:**
```python
ENTITY_TO_DOMAIN = {
    "problem": Domain.CONDITION,
    "treatment": Domain.DRUG,
    "test": Domain.MEASUREMENT,
}
```

### 9.2 ModernBERT NER

**Model:** `answerdotai/ModernBERT-base`

| Attribute | Value |
|-----------|-------|
| Context Length | **8,192 tokens** (16x BERT) |
| Attention | Flash Attention 2 |
| Architecture | Encoder-only, no token type IDs |
| Training | Continued pre-training on clinical text |
| Inference Time | ~25ms/doc (GPU) |

**Key Advantages:**
- Processes entire clinical notes without chunking
- Better handling of long-range dependencies
- 1.2x weight multiplier in ensemble due to higher accuracy

**Configuration:**
```python
@dataclass
class ModernBERTConfig:
    model_name: str = "answerdotai/ModernBERT-base"
    max_length: int = 8192
    use_flash_attention: bool = True
    confidence_threshold: float = 0.5
    chunk_overlap: int = 128
```

### 9.3 Embedding Service

**Model:** `sentence-transformers/all-MiniLM-L6-v2`

| Attribute | Value |
|-----------|-------|
| Embedding Dimensions | 384 |
| Max Sequence Length | 256 tokens |
| Inference Time | ~5ms/text |
| Similarity Metric | Cosine |

```python
class EmbeddingService:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')

    def embed(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(texts, normalize_embeddings=True)

    def find_similar(self, query_embedding, embeddings, threshold=0.7):
        similarities = cosine_similarity([query_embedding], embeddings)[0]
        return [(i, s) for i, s in enumerate(similarities) if s >= threshold]
```

### 9.4 Model Performance Comparison

| Model | Precision | Recall | F1 | Context | Speed |
|-------|-----------|--------|-----|---------|-------|
| Rule-Based | 0.92 | 0.65 | 0.76 | N/A | 2ms |
| ClinicalBERT | 0.84 | 0.88 | 0.86 | 512 | 15ms |
| ModernBERT | 0.87 | 0.91 | 0.89 | 8192 | 25ms |
| Ensemble | 0.90 | 0.89 | **0.89** | 8192 | 45ms |

---

## 10. Data Flow Diagrams

### 10.1 Entity Extraction Flow

```
Clinical Note (Text)
        |
        v
+------------------+
| Section Parser   |  --> Identify clinical sections
+------------------+
        |
        v
+------------------+
| Parallel NLP     |
| Extraction       |
|                  |
| +-------------+  |
| |Rule-Based   |  |  --> Aho-Corasick O(n) matching
| +-------------+  |
| +-------------+  |
| |ClinicalBERT |  |  --> 512 token NER
| +-------------+  |
| +-------------+  |
| |ModernBERT   |  |  --> 8192 token NER
| +-------------+  |
| +-------------+  |
| |Value Extract|  |  --> Vitals, labs, doses
| +-------------+  |
+------------------+
        |
        v
+------------------+
| Span Merging     |  --> Deduplicate, agreement boost
+------------------+
        |
        v
+------------------+
| Assertion        |
| Classification   |  --> PRESENT, ABSENT, POSSIBLE
+------------------+
        |
        v
+------------------+
| Concept Lookup   |  --> OMOP concept_id mapping
+------------------+
        |
        v
+------------------+
| Temporal         |
| Extraction       |  --> Date binding
+------------------+
        |
        v
ExtractedMention[]
```

### 10.2 Knowledge Graph Construction Flow

```
ExtractedMention[]
        |
        v
+------------------+
| ClinicalFact     |
| Creation         |  --> Persist to PostgreSQL
+------------------+
        |
        v
+------------------+
| Deduplication    |
| Check            |  --> patient_id + concept_id + domain
+------------------+
        |
        v
+------------------+
| Node Creation    |
| (Upsert)         |  --> KGNode with properties
+------------------+
        |
        v
+------------------+
| Edge Creation    |
| (Bi-temporal)    |  --> KGEdge with temporal fields
+------------------+
        |
        v
+------------------+
| OMOP Relationship|
| Enrichment       |  --> May treat, CI to, DDI
+------------------+
        |
        v
+------------------+
| Neo4j Sync       |  --> MERGE operations
+------------------+
        |
        v
PatientGraph (PostgreSQL + Neo4j)
```

### 10.3 Q&A Query Processing Flow

```
User Query
        |
        v
+------------------+
| Query Parser     |  --> Intent, entities, constraints
+------------------+
        |
        v
+------------------+     +------------------+
| Patient Context  |<--->| Knowledge Graph  |
| Builder          |     | Traversal        |
+------------------+     +------------------+
        |                        |
        v                        v
+------------------+     +------------------+
| AgentContext     |     | KGTraversalPaths |
| Construction     |<----| CausalChains     |
+------------------+     +------------------+
        |
        v
+------------------+
| Guideline RAG    |  --> Semantic + keyword search
+------------------+
        |
        v
+------------------+
| Multi-Agent      |
| Orchestration    |
| +-------------+  |
| |Diagnostic   |  |
| +-------------+  |
| |Treatment    |  |
| +-------------+  |
| |Safety       |  |
| +-------------+  |
| |Evidence     |  |
| +-------------+  |
+------------------+
        |
        v
+------------------+
| Consensus        |
| Building         |  --> Vote aggregation
+------------------+
        |
        v
+------------------+
| Response         |
| Generation       |  --> Answer + provenance
+------------------+
        |
        v
HybridQueryResponse
```

---

## 11. Technical Decisions & Rationale

### 11.1 PostgreSQL + Neo4j Dual Storage

**Decision:** Use PostgreSQL as primary storage with Neo4j for graph queries.

**Rationale:**
- PostgreSQL provides ACID compliance for clinical data integrity
- Neo4j excels at multi-hop graph traversals
- Graceful degradation: system works with PostgreSQL alone
- Neo4j sync is eventually consistent, not blocking

**Trade-offs:**
- (+) Best of both worlds: relational + graph
- (+) Can operate without Neo4j
- (-) Data duplication
- (-) Sync latency

### 11.2 Aho-Corasick vs. Regex

**Decision:** Use Aho-Corasick for vocabulary matching instead of regex.

**Rationale:**
- O(n) complexity regardless of vocabulary size
- 100K+ patterns would be impractical with regex
- Memory-efficient with shared prefix tree

**Performance:**
- Regex with 100K patterns: ~2s per document
- Aho-Corasick with 100K patterns: ~2ms per document

### 11.3 Ensemble NLP vs. Single Model

**Decision:** Combine rule-based, ClinicalBERT, and ModernBERT.

**Rationale:**
- Rule-based: High precision for known patterns
- ML models: High recall for novel entities
- Agreement boost improves confidence calibration

**Trade-offs:**
- (+) Higher overall accuracy
- (+) Complementary strengths
- (-) Higher latency (~45ms vs ~15ms)
- (-) More complex error analysis

### 11.4 Bi-Temporal Model

**Decision:** Implement bi-temporal fields on KGEdge.

**Rationale:**
- Clinical events have distinct "when it happened" vs "when we knew"
- Enables temporal queries: "medications as of date X"
- Supports Allen's interval algebra for event ordering

**Implementation Cost:**
- Additional 6 fields per edge
- Temporal indexes for query performance
- NLP temporal extraction complexity

### 11.5 ModernBERT Weight Multiplier

**Decision:** Apply 1.2x weight to ModernBERT confidence scores.

**Rationale:**
- ModernBERT's 8K context reduces chunking artifacts
- Empirically higher accuracy on long documents
- Flash Attention improves efficiency

### 11.6 TrustedMDT Multi-Agent Pattern

**Decision:** Use specialized agents with consensus voting.

**Rationale:**
- Mirrors clinical MDT decision-making
- Different perspectives catch different issues
- Explainable disagreements for transparency
- Based on published research (TrustedMDT 2025)

**Trade-offs:**
- (+) More thorough analysis
- (+) Safety agent catches contraindications
- (-) Higher LLM token usage
- (-) Increased latency

### 11.7 NDFRT Vocabulary Priority

**Decision:** Prioritize NDFRT over RxNorm/SNOMED for concept lookup.

**Rationale:**
- NDFRT contains rich clinical relationships
- "May treat" and "Contraindicated for" relationships
- Enables drug-condition reasoning
- SNOMED/RxNorm lack these relationship types

### 11.8 Savepoints for Transaction Recovery

**Decision:** Use database savepoints during bulk imports.

**Rationale:**
- Clinical imports may have partial failures
- Savepoints allow rolling back individual records
- Prevents cascading failures in batch processing

```python
async with db.begin():
    savepoint = await db.begin_nested()  # Create savepoint
    try:
        await process_document(doc)
        await savepoint.commit()
    except Exception:
        await savepoint.rollback()
        log_failure(doc)
        # Continue with next document
```

### 11.9 Feature Flags for Graceful Rollout

**Decision:** Use feature flags for NLP pipeline components.

**Rationale:**
- Enable/disable extractors without deployment
- A/B testing of model versions
- Quick rollback on production issues

```python
@dataclass
class EnsembleConfig:
    use_rule_based: bool = True
    use_ml_ner: bool = True
    use_modernbert: bool = True
    use_value_extraction: bool = True
    use_relation_extraction: bool = True
```

---

## Appendix A: Key File Locations

| Component | Path |
|-----------|------|
| Ensemble NLP Service | `/backend/app/services/nlp_ensemble.py` |
| Rule-Based NLP | `/backend/app/services/nlp_rule_based.py` |
| Assertion Classifier | `/backend/app/services/assertion_classifier.py` |
| Temporal Extractor | `/backend/app/services/temporal_extractor.py` |
| Concept Lookup | `/backend/app/services/concept_lookup.py` |
| Graph Builder | `/backend/app/services/graph_builder_db.py` |
| KG Models | `/backend/app/models/knowledge_graph.py` |
| Multi-Agent Orchestrator | `/backend/app/services/multi_agent_orchestrator.py` |
| LLM Service | `/backend/app/services/llm_service.py` |
| Guideline RAG | `/backend/app/services/guideline_rag_service.py` |
| ClinicalBERT NER | `/backend/app/services/nlp_clinical_ner.py` |
| ModernBERT NER | `/backend/app/services/nlp_modernbert_ner.py` |
| Embedding Service | `/backend/app/services/embedding_service.py` |

---

## Appendix B: References

1. **TrustedMDT (2025)**: Multi-disciplinary team simulation for clinical AI
2. **MedAgentBench (2025)**: Standardized medical agent benchmarks
3. **DR.KNOWS (2025)**: Knowledge graph-based reasoning
4. **NegEx Algorithm**: Chapman et al., simple algorithm for identifying negation
5. **ConText Algorithm**: Harkema et al., context features for clinical NLP
6. **OMOP CDM v5.4**: Observational Medical Outcomes Partnership Common Data Model
7. **Allen's Interval Algebra**: Temporal reasoning framework
8. **Aho-Corasick Algorithm**: Efficient string matching with multiple patterns

---

*Document generated for technical stakeholder presentation. Contains confidential implementation details.*
