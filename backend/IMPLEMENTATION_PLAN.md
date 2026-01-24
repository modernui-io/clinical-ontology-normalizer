# Implementation Plan: Achieving Parity with Published Medical AI Systems

## Executive Summary

Our current system has solid foundations but lacks the scale and infrastructure of published research systems. This plan outlines steps to achieve parity with:

- **DR.KNOWS** (JMIR 2025): 4.5M UMLS concepts, 15M relations
- **Neo4j Healthcare Framework** (medRxiv 2025): 625,708 nodes, 2,189,093 relationships
- **ClinicalMind Platform** (PMC 2025): 110,000 clinical documents with real-time analytics

---

## Current State vs Target State

| Metric | Current | Target | Gap |
|--------|---------|--------|-----|
| **Concepts** | 80K SNOMED | 4.5M UMLS | 56x increase |
| **Relations** | ~500 mappings | 15M UMLS relations | 30,000x increase |
| **Graph DB** | PostgreSQL (arrays) | Neo4j native graph | Architecture change |
| **Patient Nodes** | 400/patient | 600K+ total | Scale infrastructure |
| **Semantic Types** | None | 127 UMLS STY | New capability |
| **Multi-hop Reasoning** | 1-3 hops | Unlimited with pruning | Algorithm enhancement |

---

## Phase 1: Neo4j Infrastructure (Week 1)

### 1.1 Install Neo4j
```bash
# Docker installation
docker run -d \
  --name neo4j-clinical \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/clinical123 \
  -e NEO4J_PLUGINS='["apoc", "graph-data-science"]' \
  -v neo4j_data:/data \
  neo4j:5.15-enterprise
```

### 1.2 Update Configuration
- Add Neo4j connection settings to `app/core/config.py`
- Configure connection pooling for production load
- Enable APOC procedures for graph algorithms

### 1.3 Schema Design
```cypher
// Patient-centric clinical graph
CREATE CONSTRAINT patient_id IF NOT EXISTS FOR (p:Patient) REQUIRE p.patient_id IS UNIQUE;
CREATE CONSTRAINT concept_cui IF NOT EXISTS FOR (c:Concept) REQUIRE c.cui IS UNIQUE;

// Node types matching UMLS
(:Patient {patient_id, mrn, demographics})
(:Concept {cui, name, semantic_type, vocabulary, code})
(:ClinicalFact {id, value, unit, date, assertion, source_note})
(:Document {id, type, date, author, section})

// Edge types matching UMLS relations
-[:HAS_FINDING {date, assertion, confidence}]->
-[:TAKES_MEDICATION {start_date, end_date, dose}]->
-[:IS_A]->  // UMLS hierarchy
-[:TREATS]->
-[:CAUSES]->
-[:MAY_TREAT]->
-[:CONTRAINDICATED_WITH]->
```

---

## Phase 2: UMLS Metathesaurus Integration (Week 2-3)

### 2.1 Obtain UMLS License
- Apply at: https://uts.nlm.nih.gov/uts/signup-login
- Download: UMLS Knowledge Sources (Full Release)
- Files needed:
  - `MRCONSO.RRF` - Concepts (4.5M rows)
  - `MRREL.RRF` - Relations (15M rows)
  - `MRSTY.RRF` - Semantic Types
  - `MRDEF.RRF` - Definitions
  - `MRSAT.RRF` - Attributes

### 2.2 UMLS Loader Script
Create `scripts/load_umls_to_neo4j.py`:

```python
"""
Load UMLS Metathesaurus into Neo4j.

Expected runtime: 2-4 hours for full load
Memory requirement: 16GB+ recommended
"""

import csv
from neo4j import GraphDatabase

class UMLSLoader:
    SEMANTIC_GROUPS = {
        'T047': 'Disease or Syndrome',
        'T121': 'Pharmacologic Substance',
        'T184': 'Sign or Symptom',
        'T059': 'Laboratory Procedure',
        'T033': 'Finding',
        # ... 127 total semantic types
    }

    def load_concepts(self, mrconso_path: str):
        """Load 4.5M concepts from MRCONSO.RRF"""
        # Batch insert in chunks of 10,000
        pass

    def load_relations(self, mrrel_path: str):
        """Load 15M relations from MRREL.RRF"""
        # Key relation types: RO, RB, RN, PAR, CHD
        pass

    def load_semantic_types(self, mrsty_path: str):
        """Assign semantic types to concepts"""
        pass
```

### 2.3 Key UMLS Relations to Index
| Relation | Meaning | Use Case |
|----------|---------|----------|
| `RO` | Has relationship | General associations |
| `RB` | Broader than | Hierarchy up |
| `RN` | Narrower than | Hierarchy down |
| `PAR` | Parent | Direct parent |
| `CHD` | Child | Direct child |
| `SY` | Synonym | Term normalization |
| `may_treat` | Treatment | Drug-disease links |
| `contraindicated_with` | Safety | Drug interactions |

---

## Phase 3: Graph RAG Enhancement (Week 3-4)

### 3.1 Multi-hop Reasoning (DR.KNOWS Pattern)
```python
def multi_hop_reasoning(self, patient_id: str, question: str, max_hops: int = 5):
    """
    Implement DR.KNOWS-style multi-hop reasoning.

    1. Extract entities from question
    2. Find seed nodes in patient graph
    3. Traverse up to max_hops following semantic relations
    4. Score paths by relevance to question
    5. Return top-k paths with provenance
    """
    # Cypher query for path finding
    query = """
    MATCH path = (start:Concept {cui: $seed_cui})-[*1..{max_hops}]-(end:Concept)
    WHERE end.semantic_type IN $target_types
    WITH path,
         reduce(score = 1.0, r IN relationships(path) | score * r.weight) as path_score
    ORDER BY path_score DESC
    LIMIT $top_k
    RETURN path, path_score
    """
```

### 3.2 Evidence Aggregation
```python
def aggregate_evidence(self, paths: list[Path]) -> ClinicalAnswer:
    """
    Aggregate evidence from multiple reasoning paths.

    - Combine supporting evidence
    - Track provenance for each claim
    - Calculate confidence based on path convergence
    """
    pass
```

### 3.3 Semantic Type Filtering
```python
DIAGNOSTIC_TYPES = ['T047', 'T048', 'T191']  # Disease, Mental disorder, Neoplasm
THERAPEUTIC_TYPES = ['T121', 'T200']  # Drug, Clinical drug
FINDING_TYPES = ['T033', 'T184', 'T034']  # Finding, Sign/Symptom, Lab result

def filter_by_semantic_type(self, query_type: str) -> list[str]:
    """Return appropriate semantic type filters for query."""
    if query_type == 'diagnosis':
        return DIAGNOSTIC_TYPES
    elif query_type == 'treatment':
        return THERAPEUTIC_TYPES
    # ...
```

---

## Phase 4: Scale Infrastructure (Week 4-5)

### 4.1 Neo4j Optimization
```cypher
// Create indexes for fast lookup
CREATE INDEX concept_name IF NOT EXISTS FOR (c:Concept) ON (c.name);
CREATE INDEX concept_vocabulary IF NOT EXISTS FOR (c:Concept) ON (c.vocabulary);
CREATE INDEX fact_patient IF NOT EXISTS FOR (f:ClinicalFact) ON (f.patient_id);
CREATE INDEX fact_date IF NOT EXISTS FOR (f:ClinicalFact) ON (f.date);

// Full-text search index
CREATE FULLTEXT INDEX concept_search IF NOT EXISTS
FOR (c:Concept) ON EACH [c.name, c.synonyms];
```

### 4.2 Batch Processing Pipeline
```python
class BatchGraphBuilder:
    """Process clinical documents at scale."""

    async def process_documents(self, documents: list[Document], batch_size: int = 1000):
        """
        Process documents in parallel batches.

        Target: 110,000 documents (ClinicalMind parity)
        Expected: ~10,000 docs/hour with full NLP
        """
        pass
```

### 4.3 Embedding Generation at Scale
```python
# Pre-compute embeddings for all 4.5M concepts
# Use GPU acceleration if available
# Store in Neo4j as vector properties

async def generate_all_embeddings(self):
    """
    Generate embeddings for UMLS concepts.

    Time estimate: ~8 hours for 4.5M concepts
    Storage: ~7GB for 384-dim embeddings
    """
    pass
```

---

## Phase 5: Validation & Benchmarking (Week 5-6)

### 5.1 MedAgentBench Integration
Use Stanford's MedAgentBench to validate:
- 300 clinically-derived tasks
- Average 2.3 steps per task
- Measure completion rate and accuracy

### 5.2 Comparison Metrics
| Metric | DR.KNOWS | Our Target |
|--------|----------|------------|
| Diagnostic accuracy | 78% | >= 78% |
| Evidence retrieval | 85% | >= 85% |
| Citation accuracy | 92% | >= 92% |
| Latency (p95) | <2s | <2s |

### 5.3 Safety Evaluation
- Hallucination rate measurement
- Negation handling accuracy
- Contraindication detection

---

## File Structure After Implementation

```
backend/
├── app/
│   ├── services/
│   │   ├── neo4j_service.py          # Neo4j connection management
│   │   ├── umls_service.py           # UMLS concept lookup
│   │   ├── graph_reasoning.py        # Multi-hop reasoning
│   │   └── evidence_aggregator.py    # Evidence synthesis
│   ├── api/
│   │   └── graph_rag.py              # Enhanced with Neo4j backend
│   └── models/
│       └── neo4j_models.py           # Cypher query builders
├── scripts/
│   ├── load_umls_to_neo4j.py         # UMLS loader
│   ├── migrate_pg_to_neo4j.py        # Migration script
│   └── benchmark_graph_rag.py        # Performance testing
└── fixtures/
    └── umls/                         # UMLS RRF files (not committed)
```

---

## Dependencies to Add

```toml
# pyproject.toml additions
[project.dependencies]
neo4j = ">=5.15.0"
neo4j-driver = ">=5.15.0"

[project.optional-dependencies]
graph = [
    "py2neo>=2021.1",
    "neomodel>=5.2.0",
]
```

---

## Timeline Summary

| Week | Deliverable | Validation |
|------|-------------|------------|
| 1 | Neo4j running, schema deployed | Connection test passes |
| 2 | UMLS loader built | 100K concepts loaded |
| 3 | Full UMLS loaded (4.5M) | Query performance <100ms |
| 4 | Multi-hop reasoning | 5-hop paths in <500ms |
| 5 | Scale testing | 100K documents processed |
| 6 | Benchmarking complete | Parity with DR.KNOWS metrics |

---

## Risk Mitigation

1. **UMLS License Delay**: Start with SNOMED-CT full release (400K concepts)
2. **Neo4j Performance**: Use Neo4j Enterprise with clustering if needed
3. **Memory Constraints**: Implement streaming for large UMLS files
4. **Migration Complexity**: Keep PostgreSQL as fallback, gradual migration

---

## Next Steps

1. [ ] Set up Neo4j Docker container
2. [ ] Apply for UMLS license (if not already obtained)
3. [ ] Create `load_umls_to_neo4j.py` script
4. [ ] Migrate existing patient graphs to Neo4j
5. [ ] Implement multi-hop reasoning algorithm
6. [ ] Run MedAgentBench validation

---

*This plan achieves parity with published systems while maintaining our existing API contracts.*
