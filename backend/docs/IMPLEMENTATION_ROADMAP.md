# Implementation Roadmap: Achieving DR.KNOWS Parity

**Date**: January 22, 2026
**Target**: 4.5M UMLS concepts, 15M relations, 5+ hop reasoning, 110K document scale

---

## Priority Levels

| Priority | Definition | Timeline | Steps |
|----------|------------|----------|-------|
| **P0** | Critical infrastructure - blocks everything else | Week 1 | 7 steps |
| **P1** | Core data loading - enables reasoning | Weeks 2-3 | 12 steps |
| **P2** | API integration - exposes capabilities | Weeks 3-4 | 10 steps |
| **P3** | Optimization & validation - production readiness | Weeks 5-6 | 18 steps |

**Total: 47 steps with 12 test checkpoints**

---

## P0: Critical Infrastructure (Week 1)

### Steps P0-1 to P0-7

| Step | Task | Validation |
|------|------|------------|
| **P0-1** | Install Docker and verify it's running | `docker --version` returns version |
| **P0-2** | Deploy Neo4j 5.15+ Enterprise container | Container running on ports 7474/7687 |
| **P0-3** | Configure environment variables in `.env` | NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD set |
| **P0-4** | Update `app/core/config.py` to load Neo4j settings | Config loads without errors |
| **P0-5** | Verify Neo4j connection from Python | `driver.verify_connectivity()` passes |
| **P0-6** | Execute schema creation queries (constraints, indexes) | 4+ constraints, 5+ indexes created |
| **P0-7** | Disable mock mode in `graph_database_service.py` | Real queries execute against Neo4j |

### Commands Reference

```bash
# P0-1: Verify Docker
docker --version

# P0-2: Deploy Neo4j
docker run -d \
  --name neo4j-clinical \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/clinical123 \
  -e NEO4J_PLUGINS='["apoc", "graph-data-science"]' \
  -v neo4j_data:/data \
  neo4j:5.15-enterprise

# P0-3: Environment variables
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=clinical123
```

### Test Checkpoints

| Checkpoint | After Step | Test | Expected Result |
|------------|------------|------|-----------------|
| **P0-T1** | P0-5 | `curl http://localhost:7474/db/neo4j/cluster/available` | `true` |
| **P0-T2** | P0-7 | `SHOW CONSTRAINTS; SHOW INDEXES;` | 4+ constraints, 5+ indexes |

---

## P1: UMLS Data Loading (Weeks 2-3)

### Steps P1-1 to P1-12

| Step | Task | Validation |
|------|------|------------|
| **P1-1** | Verify UMLS license at uts.nlm.nih.gov | License active or application submitted |
| **P1-2** | Download UMLS Knowledge Sources (Full Release) | MRCONSO.RRF, MRREL.RRF, MRSTY.RRF, MRDEF.RRF downloaded |
| **P1-3** | Create `fixtures/umls/` directory (gitignored) | Directory exists, added to .gitignore |
| **P1-4** | Implement `load_umls_to_neo4j.py` - Concept loader | Script parses MRCONSO.RRF correctly |
| **P1-5** | Add semantic type loading from MRSTY.RRF | 127 semantic types mapped to concepts |
| **P1-6** | Add relation loading from MRREL.RRF | RO, RB, RN, PAR, CHD, SY relation types supported |
| **P1-7** | Load first 100K UMLS concepts (test batch) | `MATCH (c:Concept) RETURN count(c)` >= 100,000 |
| **P1-8** | Load full MRCONSO.RRF (4.5M concepts) | ~4,500,000 concepts in Neo4j |
| **P1-9** | Load MRREL.RRF relations (15M) | >= 15,000,000 relationships created |
| **P1-10** | Load clinical vocabularies subset with hierarchies | SNOMED, RxNorm, LOINC hierarchies traversable |
| **P1-11** | Build CUI-to-vocabulary mappings | SNOMED→CUI, RxNorm→CUI, ICD-10→CUI lookups work |
| **P1-12** | Update vocabulary services to use CUI lookups | `get_cui()` methods return valid CUIs |

### Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `fixtures/umls/` | Create | Store UMLS RRF files (gitignored) |
| `scripts/load_umls_to_neo4j.py` | Implement | Batch load UMLS into Neo4j |
| `app/services/snomed_service.py` | Add `get_cui()` | CUI lookup for SNOMED codes |
| `app/services/rxnorm_service.py` | Add `get_cui()` | CUI lookup for RxNorm codes |
| `app/services/icd10_suggester.py` | Add `get_cui()` | CUI lookup for ICD-10 codes |

### Test Checkpoints

| Checkpoint | After Step | Test | Expected Result |
|------------|------------|------|-----------------|
| **P1-T1** | P1-7 | `MATCH (c:Concept) RETURN count(c)` | >= 100,000 |
| **P1-T2** | P1-8 | `MATCH (c:Concept) RETURN count(c)` | ~4,500,000 |
| **P1-T3** | P1-9 | `MATCH ()-[r]->() RETURN count(r)` | >= 15,000,000 |
| **P1-T4** | P1-12 | Cross-vocabulary query for "diabetes" | Results from SNOMED, ICD-10, RxNorm |

### Estimated Load Times

| Data | Records | Batch Size | Estimated Time |
|------|---------|------------|----------------|
| MRCONSO (concepts) | 4.5M | 10,000 | 2-4 hours |
| MRSTY (semantic types) | 4.5M | 50,000 | 30-60 min |
| MRREL (relations) | 15M | 50,000 | 4-6 hours |

---

## P2: API Integration (Weeks 3-4)

### Steps P2-1 to P2-10

| Step | Task | Validation |
|------|------|------------|
| **P2-1** | Create `/graph/reasoning/multi-hop` endpoint | Endpoint returns paths up to 5 hops |
| **P2-2** | Expose semantic type filtering in API | Filter by DISO, CHEM, PROC, ANAT groups |
| **P2-3** | Add `/graph/reasoning/score-paths` endpoint | Returns scored paths with confidence decay |
| **P2-4** | Integrate temporal service into graph API | `find_treatment_paths()`, `find_contraindications()` exposed |
| **P2-5** | Update graph RAG endpoint to use UMLS | `/graph-rag/search` queries Neo4j backend |
| **P2-6** | Add `/graph/reasoning/aggregate-evidence` endpoint | Combines multiple paths into conclusions |
| **P2-7** | Create vocabulary bridge service | Cross-vocabulary routing via CUI works |
| **P2-8** | Update Clinical Intelligence Agent with graph reasoning | `ACTION_GRAPH_REASONING` action type added |
| **P2-9** | Add Graph RAG to Hybrid Analyzer | Reasoning paths included in LLM context |
| **P2-10** | Update agent API to include reasoning capabilities | `/agent/analyze` uses graph reasoning |

### New API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/graph/reasoning/multi-hop` | POST | Execute multi-hop reasoning queries |
| `/graph/reasoning/score-paths` | POST | Score and rank reasoning paths |
| `/graph/reasoning/aggregate-evidence` | POST | Combine paths into clinical conclusions |

### Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `app/api/graph.py` | Add endpoints | Multi-hop reasoning API |
| `app/services/vocabulary_bridge.py` | Create | Cross-vocabulary routing |
| `app/services/clinical_intelligence_agent.py` | Add action | Graph reasoning action type |
| `app/services/hybrid_clinical_analyzer.py` | Integrate | Graph RAG in LLM context |

### Test Checkpoints

| Checkpoint | After Step | Test | Expected Result |
|------------|------------|------|-----------------|
| **P2-T1** | P2-3 | POST `/graph/reasoning/multi-hop` with diabetes CUI | Treatment paths returned |
| **P2-T2** | P2-9 | `VocabularyBridge.find_treatments_for_condition()` | Cross-vocabulary drugs found |

### Sample API Request

```bash
# P2-T1: Multi-hop reasoning test
curl -X POST http://localhost:8000/graph/reasoning/multi-hop \
  -H "Content-Type: application/json" \
  -d '{
    "seed_cui": "C0011849",
    "max_hops": 5,
    "semantic_groups": ["DISO", "CHEM"],
    "min_confidence": 0.5
  }'
```

---

## P3: Optimization & Validation (Weeks 5-6)

### Steps P3-1 to P3-18

#### Performance Optimization (P3-1 to P3-4)

| Step | Task | Validation |
|------|------|------------|
| **P3-1** | Pre-compute embeddings for all UMLS concepts | 4.5M embeddings generated (~7GB storage) |
| **P3-2** | Create Neo4j vector index | Vector similarity search returns results |
| **P3-3** | Implement query caching layer | Cache hit rate > 50% on repeated queries |
| **P3-4** | Add connection pooling optimization | Pool tuned based on load testing |

#### Benchmark Validation (P3-5 to P3-8)

| Step | Task | Validation |
|------|------|------------|
| **P3-5** | Run DR.KNOWS benchmark suite | Full benchmark completes without errors |
| **P3-6** | Compare against DR.KNOWS baselines | Accuracy >= 78%, Evidence >= 85%, Citation >= 92% |
| **P3-7** | Run MedAgentBench (300 tasks) | All 7 categories evaluated |
| **P3-8** | Document benchmark results | `docs/BENCHMARK_RESULTS.md` created |

#### Scale Testing (P3-9 to P3-11)

| Step | Task | Validation |
|------|------|------------|
| **P3-9** | Prepare 10K clinical note test corpus | Mix of progress, discharge, consult notes |
| **P3-10** | Run NLP pipeline at 10K scale | Throughput and accuracy measured |
| **P3-11** | Run full pipeline at 100K scale | Throughput >= 10K docs/hour |

#### Safety Validation (P3-12 to P3-14)

| Step | Task | Validation |
|------|------|------------|
| **P3-12** | Test hallucination rate on medical claims | < 5% unsupported claims |
| **P3-13** | Test negation handling accuracy | > 95% correct assertion detection |
| **P3-14** | Test contraindication detection | > 90% recall on safety alerts |

#### Documentation (P3-15 to P3-18)

| Step | Task | Validation |
|------|------|------------|
| **P3-15** | Update README.md with new capabilities | Documentation reflects current state |
| **P3-16** | Create API documentation for new endpoints | OpenAPI spec updated |
| **P3-17** | Write deployment guide for Neo4j + UMLS | `docs/DEPLOYMENT.md` created |
| **P3-18** | Create monitoring dashboard (Grafana) | Query latency, counts, errors visible |

### Test Checkpoints

| Checkpoint | After Step | Test | Expected Result |
|------------|------------|------|-----------------|
| **P3-T1** | P3-4 | 5-hop query execution time | < 2 seconds |
| **P3-T2** | P3-7 | DR.KNOWS benchmark metrics | Meet published baselines |
| **P3-T3** | P3-11 | Document processing throughput | >= 10,000 docs/hour |
| **P3-T4** | P3-14 | Safety metric validation | All thresholds pass |

### DR.KNOWS Baseline Targets

| Metric | DR.KNOWS Published | Our Target | Pass Criteria |
|--------|-------------------|------------|---------------|
| Diagnostic accuracy | 78% | >= 78% | Must meet |
| Evidence retrieval | 85% | >= 85% | Must meet |
| Citation accuracy | 92% | >= 92% | Must meet |
| Path coverage | 84.7% | >= 84% | Must meet |
| 5-hop accuracy | 76.8% | >= 75% | Must meet |
| Latency (p95) | < 2s | < 2s | Must meet |

### Safety Thresholds

| Metric | Threshold | Consequence if Failed |
|--------|-----------|----------------------|
| Hallucination rate | < 5% | Block deployment |
| Negation accuracy | > 95% | Block deployment |
| Contraindication recall | > 90% | Block deployment |

---

## Summary

### Step Count by Priority

| Priority | Steps | Key Deliverable |
|----------|-------|-----------------|
| **P0** | P0-1 → P0-7 (7 steps) | Neo4j running with schema |
| **P1** | P1-1 → P1-12 (12 steps) | 4.5M concepts + 15M relations loaded |
| **P2** | P2-1 → P2-10 (10 steps) | Multi-hop reasoning API live |
| **P3** | P3-1 → P3-18 (18 steps) | Validated at DR.KNOWS parity |
| **Total** | **47 steps** | Production-ready clinical KG |

### Test Checkpoint Summary

| Phase | Checkpoints | Purpose |
|-------|-------------|---------|
| P0 | P0-T1, P0-T2 | Infrastructure validation |
| P1 | P1-T1, P1-T2, P1-T3, P1-T4 | Data loading validation |
| P2 | P2-T1, P2-T2 | API functionality validation |
| P3 | P3-T1, P3-T2, P3-T3, P3-T4 | Performance & safety validation |

### Resource Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| Memory | 16GB | 32GB |
| Storage | 50GB | 100GB |
| CPU | 4 cores | 8 cores |
| GPU | Optional | Recommended for embeddings |

### Risk Mitigation

| Risk | Mitigation Strategy |
|------|---------------------|
| UMLS license delay | Start with SNOMED-CT full release (400K concepts) |
| Neo4j performance issues | Use Neo4j Enterprise with clustering if needed |
| Memory constraints | Implement streaming for large UMLS files |
| Migration complexity | Keep PostgreSQL as fallback, gradual migration |

---

## Quick Reference: All Steps

```
P0: Infrastructure (Week 1)
├── P0-1: Install Docker
├── P0-2: Deploy Neo4j container
├── P0-3: Configure environment variables
├── P0-4: Update config.py
├── P0-5: Verify Neo4j connection
├── P0-6: Execute schema creation
└── P0-7: Disable mock mode

P1: Data Loading (Weeks 2-3)
├── P1-1: Verify UMLS license
├── P1-2: Download UMLS files
├── P1-3: Create fixtures/umls directory
├── P1-4: Implement concept loader
├── P1-5: Add semantic type loading
├── P1-6: Add relation loading
├── P1-7: Load 100K test batch
├── P1-8: Load full 4.5M concepts
├── P1-9: Load 15M relations
├── P1-10: Load vocabulary hierarchies
├── P1-11: Build CUI mappings
└── P1-12: Update vocabulary services

P2: API Integration (Weeks 3-4)
├── P2-1: Create multi-hop endpoint
├── P2-2: Add semantic type filtering
├── P2-3: Add path scoring endpoint
├── P2-4: Integrate temporal service
├── P2-5: Update graph RAG endpoint
├── P2-6: Add evidence aggregation
├── P2-7: Create vocabulary bridge
├── P2-8: Update Clinical Intelligence Agent
├── P2-9: Add Graph RAG to Hybrid Analyzer
└── P2-10: Update agent API

P3: Optimization & Validation (Weeks 5-6)
├── P3-1: Pre-compute embeddings
├── P3-2: Create vector index
├── P3-3: Implement query caching
├── P3-4: Optimize connection pooling
├── P3-5: Run DR.KNOWS benchmark
├── P3-6: Compare against baselines
├── P3-7: Run MedAgentBench
├── P3-8: Document benchmark results
├── P3-9: Prepare 10K test corpus
├── P3-10: Run NLP at 10K scale
├── P3-11: Run pipeline at 100K scale
├── P3-12: Test hallucination rate
├── P3-13: Test negation accuracy
├── P3-14: Test contraindication detection
├── P3-15: Update README
├── P3-16: Create API documentation
├── P3-17: Write deployment guide
└── P3-18: Create Grafana dashboard
```

---

*This roadmap achieves parity with DR.KNOWS while maintaining existing API contracts.*
