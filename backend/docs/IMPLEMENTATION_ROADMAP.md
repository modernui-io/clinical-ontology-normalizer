# Implementation Roadmap: Achieving DR.KNOWS Parity

**Date**: January 22, 2026
**Target**: 4.5M UMLS concepts, 15M relations, 5+ hop reasoning, 110K document scale

---

## Priority Levels

| Priority | Definition | Timeline |
|----------|------------|----------|
| **P0** | Critical infrastructure - blocks everything else | Week 1 |
| **P1** | Core data loading - enables reasoning | Weeks 2-3 |
| **P2** | API integration - exposes capabilities | Weeks 3-4 |
| **P3** | Optimization & validation - production readiness | Weeks 5-6 |

---

## P0: Critical Infrastructure (Week 1)

### Neo4j Deployment

- [ ] **P0-1**: Install Docker and verify it's running
  ```bash
  docker --version
  ```

- [ ] **P0-2**: Deploy Neo4j 5.15+ Enterprise container
  ```bash
  docker run -d \
    --name neo4j-clinical \
    -p 7474:7474 -p 7687:7687 \
    -e NEO4J_AUTH=neo4j/clinical123 \
    -e NEO4J_PLUGINS='["apoc", "graph-data-science"]' \
    -v neo4j_data:/data \
    neo4j:5.15-enterprise
  ```

- [ ] **P0-3**: Configure environment variables in `.env`
  ```
  NEO4J_URI=bolt://localhost:7687
  NEO4J_USER=neo4j
  NEO4J_PASSWORD=clinical123
  ```

- [ ] **P0-4**: Update `app/core/config.py` to load Neo4j settings

- [ ] **P0-5**: Verify Neo4j connection from Python
  ```python
  from neo4j import GraphDatabase
  driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "clinical123"))
  driver.verify_connectivity()
  ```

### **TEST CHECKPOINT P0-T1**: Neo4j Health Check
```bash
curl http://localhost:7474/db/neo4j/cluster/available
# Expected: true
```

- [ ] **P0-6**: Execute schema creation queries from `graph_etl_service.py`
  - Create constraints (patient_id, concept_cui)
  - Create indexes (concept_name, vocabulary, fact_patient, fact_date)
  - Create full-text search index

- [ ] **P0-7**: Disable mock mode in `graph_database_service.py`
  - Set `_mock_mode = False` when Neo4j available

### **TEST CHECKPOINT P0-T2**: Schema Verification
```cypher
SHOW CONSTRAINTS;
SHOW INDEXES;
-- Expected: 4+ constraints, 5+ indexes
```

---

## P1: UMLS Data Loading (Weeks 2-3)

### UMLS License & Download

- [ ] **P1-1**: Verify UMLS license at https://uts.nlm.nih.gov/uts/
  - If not licensed, apply (takes 1-3 days)

- [ ] **P1-2**: Download UMLS Knowledge Sources (Full Release)
  - Files needed: MRCONSO.RRF, MRREL.RRF, MRSTY.RRF, MRDEF.RRF

- [ ] **P1-3**: Create `fixtures/umls/` directory (gitignored)
  ```bash
  mkdir -p fixtures/umls
  echo "fixtures/umls/*.RRF" >> .gitignore
  ```

### UMLS Loader Implementation

- [ ] **P1-4**: Implement `scripts/load_umls_to_neo4j.py` - Concept loader
  - Parse MRCONSO.RRF (4.5M rows)
  - Batch insert in chunks of 10,000
  - Track progress with logging

- [ ] **P1-5**: Add semantic type loading from MRSTY.RRF
  - Map 127 semantic types to concepts
  - Assign semantic groups (15 groups)

- [ ] **P1-6**: Add relation loading from MRREL.RRF
  - Key relations: RO, RB, RN, PAR, CHD, SY
  - 15M relations in batches of 50,000

### **TEST CHECKPOINT P1-T1**: Initial Load (100K concepts)
```cypher
MATCH (c:Concept) RETURN count(c);
-- Expected: >= 100,000
```

- [ ] **P1-7**: Load first 100K UMLS concepts (test batch)
  - Verify schema integrity
  - Measure load time (~10 min expected)

- [ ] **P1-8**: Load full MRCONSO.RRF (4.5M concepts)
  - Estimated time: 2-4 hours
  - Memory requirement: 16GB+

### **TEST CHECKPOINT P1-T2**: Full Concept Load
```cypher
MATCH (c:Concept) RETURN count(c);
-- Expected: ~4,500,000

MATCH (c:Concept) WHERE c.semantic_type IS NOT NULL RETURN count(c);
-- Expected: ~4,500,000 (all should have types)
```

- [ ] **P1-9**: Load MRREL.RRF relations (15M)
  - Estimated time: 4-6 hours
  - Create indexes before load for performance

- [ ] **P1-10**: Load clinical vocabularies subset
  - SNOMED-CT concepts with full hierarchy
  - RxNorm drugs with ingredients
  - LOINC lab tests with panels
  - ICD-10 with excludes/includes

### **TEST CHECKPOINT P1-T3**: Relation Load
```cypher
MATCH ()-[r]->() RETURN count(r);
-- Expected: >= 15,000,000

MATCH (c1:Concept)-[:IS_A]->(c2:Concept) RETURN count(*) LIMIT 1;
-- Expected: > 0 (hierarchy exists)
```

- [ ] **P1-11**: Build CUI-to-vocabulary mappings
  - SNOMED code → CUI
  - RxNorm RxCUI → CUI
  - ICD-10 code → CUI
  - Store in lookup tables

- [ ] **P1-12**: Update vocabulary services to use CUI lookups
  - `snomed_service.py`: Add `get_cui()` method
  - `rxnorm_service.py`: Add `get_cui()` method
  - `icd10_suggester.py`: Add `get_cui()` method

### **TEST CHECKPOINT P1-T4**: Cross-Vocabulary Query
```cypher
// Find diabetes concepts across vocabularies
MATCH (c:Concept)
WHERE c.name CONTAINS 'diabetes' AND c.vocabulary IN ['SNOMEDCT_US', 'ICD10CM', 'RXNORM']
RETURN c.vocabulary, count(c);
-- Expected: Results from all 3 vocabularies
```

---

## P2: API Integration (Weeks 3-4)

### Multi-Hop Reasoning API

- [ ] **P2-1**: Create new endpoint in `app/api/graph.py`
  ```python
  @router.post("/graph/reasoning/multi-hop")
  async def multi_hop_reasoning(query: MultiHopQuery):
      # Calls neo4j_temporal_service.multi_hop_reasoning()
  ```

- [ ] **P2-2**: Expose semantic type filtering in API
  - Filter by UMLS semantic groups (DISO, CHEM, PROC, etc.)
  - Support inclusion/exclusion lists

- [ ] **P2-3**: Add path scoring endpoint
  ```python
  @router.post("/graph/reasoning/score-paths")
  async def score_reasoning_paths(paths: List[Path]):
      # Returns scored paths with confidence decay
  ```

### **TEST CHECKPOINT P2-T1**: Multi-Hop Query
```bash
curl -X POST http://localhost:8000/graph/reasoning/multi-hop \
  -H "Content-Type: application/json" \
  -d '{"seed_cui": "C0011849", "max_hops": 5, "semantic_groups": ["DISO", "CHEM"]}'
# Expected: Paths from diabetes to treatments
```

- [ ] **P2-4**: Integrate temporal service into graph API
  - Expose `find_treatment_paths()`
  - Expose `find_contraindications()`
  - Expose `aggregate_evidence()`

- [ ] **P2-5**: Update graph RAG endpoint to use UMLS
  - Connect `/graph-rag/search` to Neo4j backend
  - Add CUI-based retrieval

- [ ] **P2-6**: Add evidence aggregation endpoint
  ```python
  @router.post("/graph/reasoning/aggregate-evidence")
  async def aggregate_evidence(paths: List[ReasoningPath]):
      # Combines multiple paths into clinical conclusions
  ```

### Cross-Vocabulary Integration

- [ ] **P2-7**: Create vocabulary bridge service
  - `app/services/vocabulary_bridge.py`
  - Route queries across SNOMED ↔ ICD-10 ↔ RxNorm via CUI

- [ ] **P2-8**: Update Clinical Intelligence Agent
  - Add `ACTION_GRAPH_REASONING` action type
  - Connect to multi-hop reasoning

- [ ] **P2-9**: Add Graph RAG to Hybrid Analyzer
  - Retrieve relevant paths before LLM call
  - Include in structured context

### **TEST CHECKPOINT P2-T2**: Cross-Vocabulary Bridge
```python
# Test: Find RxNorm drugs that treat SNOMED condition
from app.services.vocabulary_bridge import VocabularyBridge
bridge = VocabularyBridge()
drugs = bridge.find_treatments_for_condition(snomed_code="73211009")  # Diabetes
assert len(drugs) > 0
```

- [ ] **P2-10**: Update agent API to include reasoning capabilities
  - `/agent/analyze` endpoint uses graph reasoning
  - Include evidence paths in response

---

## P3: Optimization & Validation (Weeks 5-6)

### Performance Optimization

- [ ] **P3-1**: Pre-compute embeddings for all UMLS concepts
  - Estimated: ~8 hours for 4.5M concepts
  - Storage: ~7GB for 384-dim vectors

- [ ] **P3-2**: Create Neo4j vector index
  ```cypher
  CALL db.index.vector.createNodeIndex(
    'concept_embeddings', 'Concept', 'embedding', 384, 'cosine'
  );
  ```

- [ ] **P3-3**: Implement query caching layer
  - Cache frequent multi-hop queries
  - TTL: 1 hour for reasoning paths

- [ ] **P3-4**: Add connection pooling optimization
  - Tune Neo4j pool size based on load testing
  - Add circuit breaker for Neo4j failures

### **TEST CHECKPOINT P3-T1**: Query Performance
```python
import time
start = time.time()
result = await neo4j_service.multi_hop_reasoning(seed_cui="C0011849", max_hops=5)
elapsed = time.time() - start
assert elapsed < 2.0  # Target: <2s for 5-hop
```

### Benchmark Validation

- [ ] **P3-5**: Run DR.KNOWS benchmark suite
  ```python
  from app.services.drknows_benchmark_service import DRKnowsBenchmarkService
  service = DRKnowsBenchmarkService()
  results = await service.run_full_benchmark()
  ```

- [ ] **P3-6**: Compare against DR.KNOWS baselines
  | Metric | DR.KNOWS | Our Target |
  |--------|----------|------------|
  | Diagnostic accuracy | 78% | >= 78% |
  | Evidence retrieval | 85% | >= 85% |
  | Citation accuracy | 92% | >= 92% |

- [ ] **P3-7**: Run MedAgentBench (300 tasks)
  ```python
  from app.services.medagentbench_service import MedAgentBenchService
  service = MedAgentBenchService()
  results = await service.run_benchmark(categories=["all"])
  ```

### **TEST CHECKPOINT P3-T2**: Benchmark Results
```python
# Target metrics
assert results["path_discovery"]["path_coverage"] >= 0.84
assert results["reasoning"]["accuracy"] >= 0.84
assert results["multi_hop"]["hop_5_plus_accuracy"] >= 0.76
```

- [ ] **P3-8**: Document benchmark results in `docs/BENCHMARK_RESULTS.md`

### Scale Testing

- [ ] **P3-9**: Prepare 10K clinical note test corpus
  - Mix of note types (progress, discharge, consult)
  - Realistic clinical content

- [ ] **P3-10**: Run NLP pipeline at 10K scale
  ```python
  results = await ensemble_service.batch_extract(notes[:10000])
  # Measure: throughput, accuracy, memory
  ```

- [ ] **P3-11**: Run full pipeline at 100K scale (if resources allow)
  - Document throughput (target: 10K docs/hour)

### **TEST CHECKPOINT P3-T3**: Scale Performance
```python
# Target: 10K docs/hour minimum
docs_per_hour = 10000 / elapsed_hours
assert docs_per_hour >= 10000
```

### Safety Validation

- [ ] **P3-12**: Test hallucination rate on medical claims
  - Extract claims from LLM responses
  - Verify against knowledge graph
  - Target: <5% unsupported claims

- [ ] **P3-13**: Test negation handling accuracy
  - Corpus of negated findings
  - Target: >95% correct assertion detection

- [ ] **P3-14**: Test contraindication detection
  - Drug-condition pairs with known contraindications
  - Target: >90% recall on safety alerts

### **TEST CHECKPOINT P3-T4**: Safety Metrics
```python
assert hallucination_rate < 0.05
assert negation_accuracy > 0.95
assert contraindication_recall > 0.90
```

---

## Final Deliverables

- [ ] **P3-15**: Update README.md with new capabilities

- [ ] **P3-16**: Create API documentation for new endpoints

- [ ] **P3-17**: Write deployment guide for Neo4j + UMLS

- [ ] **P3-18**: Create monitoring dashboard (Grafana)
  - Query latency metrics
  - Concept/relation counts
  - Error rates

---

## Summary: 40 Steps

| Priority | Steps | Focus |
|----------|-------|-------|
| P0 | 1-7 | Neo4j Infrastructure |
| P1 | 8-22 | UMLS Data Loading |
| P2 | 23-32 | API Integration |
| P3 | 33-40 | Optimization & Validation |

### Test Checkpoints

| Checkpoint | After Step | Validates |
|------------|------------|-----------|
| P0-T1 | P0-5 | Neo4j health |
| P0-T2 | P0-7 | Schema creation |
| P1-T1 | P1-7 | Initial 100K load |
| P1-T2 | P1-8 | Full concept load |
| P1-T3 | P1-9 | Relation load |
| P1-T4 | P1-12 | Cross-vocabulary |
| P2-T1 | P2-3 | Multi-hop API |
| P2-T2 | P2-9 | Vocabulary bridge |
| P3-T1 | P3-4 | Query performance |
| P3-T2 | P3-7 | Benchmark results |
| P3-T3 | P3-11 | Scale performance |
| P3-T4 | P3-14 | Safety metrics |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| UMLS license delay | Start with SNOMED-CT full release (400K concepts) |
| Neo4j performance | Use Neo4j Enterprise with clustering if needed |
| Memory constraints | Implement streaming for large UMLS files |
| Migration complexity | Keep PostgreSQL as fallback, gradual migration |

---

## Resource Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| Memory | 16GB | 32GB |
| Storage | 50GB | 100GB |
| CPU | 4 cores | 8 cores |
| GPU | Optional | Recommended for embeddings |

---

*This roadmap achieves parity with DR.KNOWS while maintaining existing API contracts.*
