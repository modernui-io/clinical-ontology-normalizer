# Architecture Scalability Audit (CTO-1)

## Executive Summary

This document presents the architecture scalability audit for the Clinical Ontology Normalizer platform. The audit evaluates eight core architectural components, projects resource requirements across four patient-count tiers (1K to 1M), and provides a prioritized remediation roadmap.

**Overall Scalability Score: ~60/100 (Grade D)**

The platform is well-architected for its current scale (< 10K patients) but requires targeted improvements to support 100K+ patients. The primary bottlenecks are in the PostgreSQL database layer, the NLP processing pipeline, and the trial screening engine.

### Key Findings

- **2 critical bottlenecks**: PostgreSQL connection pooling and index coverage for screening queries
- **3 high-risk components**: PostgreSQL, NLP pipeline, trial screening
- **3 medium-risk components**: Neo4j, FastAPI workers, knowledge graph
- **1 low-risk component**: Redis
- **Estimated cost at 1M patients**: ~$7,000-10,000/month (cloud infrastructure only)

---

## Component Analysis

### 1. PostgreSQL (Risk: HIGH)

**Role**: Primary relational database storing all application data.

| Metric | Value |
|--------|-------|
| Current Capacity | ~500 queries/s with connection pooling |
| Max Capacity | ~2,000 queries/s (single instance, tuned) |
| Scaling Strategy | Vertical (upgrade instance size) |
| Current Utilization | ~35% |

**Concerns**:
- Connection pool uses SQLAlchemy async defaults (5-20 connections). At horizontal scale with 10+ workers, this will exceed PostgreSQL's default max_connections (100).
- clinical_facts table grows at ~100 rows per patient. At 1M patients, this means ~100M rows without partitioning.
- Several query patterns are O(n) without composite indexes.
- No read replicas configured for analytics workloads.

**Recommendations**:
1. Deploy PgBouncer in transaction-pooling mode (CRITICAL)
2. Add composite indexes for screening queries (CRITICAL)
3. Implement hash partitioning on clinical_facts by patient_id (HIGH)
4. Add read replicas for analytics/dashboard queries (MEDIUM)

### 2. Redis (Risk: LOW)

**Role**: In-memory cache and job queue backend.

| Metric | Value |
|--------|-------|
| Current Capacity | ~10,000 ops/s |
| Max Capacity | 100,000+ ops/s (Redis Cluster) |
| Scaling Strategy | Horizontal (Redis Cluster) |
| Current Utilization | ~15% |

**Concerns**:
- No maxmemory or eviction policy configured (defaults to noeviction, which will cause errors when memory is exhausted)
- Memory projection: ~1MB per 1K patients for cache entries

**Recommendations**:
1. Configure maxmemory and allkeys-lru eviction policy (HIGH)
2. Monitor cache hit rates (MEDIUM)
3. Consider Redis Cluster for horizontal scaling at >100K patients (LOW)

### 3. Neo4j (Risk: MEDIUM)

**Role**: Graph database for knowledge graph storage and traversal.

| Metric | Value |
|--------|-------|
| Current Capacity | ~200 traversals/s (depth <= 3) |
| Max Capacity | ~1,000 traversals/s (with index optimization) |
| Scaling Strategy | Vertical |
| Current Utilization | ~20% |

**Concerns**:
- Some Cypher queries have unbounded traversal depth, which can cause OOM or timeout at scale
- Community edition is single-instance only (no clustering)
- At 1M patients: ~80M nodes, ~200M edges

**Recommendations**:
1. Add traversal depth limits to all Cypher queries (MEDIUM)
2. Implement graph result pagination (MEDIUM)
3. Consider Neo4j Enterprise for causal clustering at scale (LOW)

### 4. FastAPI Workers (Risk: MEDIUM)

**Role**: Async web framework serving 726+ API endpoints.

| Metric | Value |
|--------|-------|
| Current Capacity | ~1,000 req/s (4 workers) |
| Max Capacity | 5,000+ req/s (horizontal scaling) |
| Scaling Strategy | Horizontal |
| Current Utilization | ~25% |

**Concerns**:
- ~30% of endpoints use synchronous database calls, blocking the event loop
- 9 middleware layers add per-request overhead
- Default 4 uvicorn workers; should scale with CPU cores

**Recommendations**:
1. Audit and convert sync-to-async on I/O paths (MEDIUM)
2. Increase worker count to 2x CPU cores (LOW)
3. Deploy behind load balancer for horizontal scaling (LOW)

### 5. NLP Pipeline (Risk: HIGH)

**Role**: Clinical NLP extraction (rule-based + ML ensemble).

| Metric | Value |
|--------|-------|
| Current Capacity | ~50 documents/min (CPU-only) |
| Max Capacity | ~500 documents/min (dedicated GPU workers) |
| Scaling Strategy | Horizontal |
| Current Utilization | ~40% |

**Concerns**:
- Processing is synchronous (inline with API request), blocking the caller
- No batch processing support for bulk document ingestion
- No GPU acceleration configured
- Vocabulary cache loaded per-worker (~50MB)

**Recommendations**:
1. Offload NLP to dedicated worker pool with Redis-backed queue (MEDIUM)
2. Implement batch processing with configurable concurrency (MEDIUM)
3. Consider GPU acceleration for ML models (LOW)

### 6. FHIR Import (Risk: MEDIUM)

**Role**: FHIR R4 resource import pipeline (Patient, Condition, Observation, etc.).

| Metric | Value |
|--------|-------|
| Current Capacity | ~100 resources/s (synchronous) |
| Max Capacity | ~1,000 resources/s (async worker pool) |
| Scaling Strategy | Horizontal |
| Current Utilization | ~30% |

**Concerns**:
- Webhook processing is synchronous, blocking during parsing
- Throughput bottleneck at JSON parsing + DB writes
- Basic retry strategy (exponential backoff)

**Recommendations**:
1. Add webhook ingestion queue (Redis-backed) to absorb burst traffic (MEDIUM)
2. Implement batch resource parsing (LOW)

### 7. Trial Screening (Risk: HIGH)

**Role**: Patient-trial eligibility screening engine.

| Metric | Value |
|--------|-------|
| Current Capacity | ~200 screenings/min (sequential) |
| Max Capacity | ~5,000 screenings/min (parallel workers) |
| Scaling Strategy | Horizontal |
| Current Utilization | ~45% |

**Concerns**:
- Worst-case complexity: O(patients x trials x criteria)
- No criterion result caching (recalculates each time)
- Limited batch parallelism
- Linear scaling with patient count

**Recommendations**:
1. Implement parallel screening with patient-level partitioning (HIGH)
2. Cache trial criteria evaluations (HIGH)
3. Pre-compute common criterion checks (MEDIUM)

### 8. Knowledge Graph (Risk: MEDIUM)

**Role**: Clinical knowledge graph for queries, reasoning, and GraphRAG.

| Metric | Value |
|--------|-------|
| Current Capacity | ~100 graph queries/s |
| Max Capacity | ~500 graph queries/s (with caching) |
| Scaling Strategy | Caching |
| Current Utilization | ~25% |

**Concerns**:
- Node growth: ~80 nodes per patient (8M at 100K, 80M at 1M patients)
- Edge growth: ~200 edges per patient (20M at 100K, 200M at 1M patients)
- No graph result caching configured

**Recommendations**:
1. Implement materialized graph summaries for common queries (LOW)
2. Add graph result caching with TTL (LOW)

---

## Growth Projections

### Resource Requirements by Tier

| Metric | 1K Patients | 10K Patients | 100K Patients | 1M Patients |
|--------|-------------|--------------|---------------|-------------|
| vCPUs | 2-4 | 4-6 | 22+ | 202+ |
| Memory (GB) | 4-8 | 8-12 | 44+ | 404+ |
| Storage (GB) | ~1 | ~6 | ~60 | ~600 |
| Network (Mbps) | 10-15 | 15-20 | 60+ | 510+ |
| DB Rows | ~1.1M | ~11.5M | ~114.6M | ~1.15B |
| KG Nodes | 80K | 800K | 8M | 80M |
| KG Edges | 200K | 2M | 20M | 200M |

### Cost Projections (Monthly, USD)

| Tier | Compute | Memory | Storage | Network | Total |
|------|---------|--------|---------|---------|-------|
| 1K | $70 | $20 | $0.10 | $5 | ~$100 |
| 10K | $140 | $40 | $0.60 | $8 | ~$200 |
| 100K | $770 | $220 | $6 | $30 | ~$1,000 |
| 1M | $7,070 | $2,020 | $60 | $255 | ~$9,400 |

*Note: Estimates based on on-demand cloud pricing. Reserved instances can reduce costs by 30-60%.*

### Key Table Size Projections

| Table | Rows/Patient | 1K | 10K | 100K | 1M |
|-------|-------------|-----|------|------|-----|
| clinical_facts | 100 | 48.8MB | 488MB | 4.8GB | 47.7GB |
| mentions | 250 | 61.0MB | 610MB | 6.0GB | 59.6GB |
| mention_concept_candidates | 500 | 183.1MB | 1.8GB | 17.9GB | 178.8GB |
| documents | 5 | 19.5MB | 195MB | 1.9GB | 19.1GB |
| screening_results | 10 | 3.7MB | 36.6MB | 366MB | 3.6GB |
| patients | 1 | 976.6KB | 9.5MB | 97.7MB | 976.6MB |

---

## Database Analysis

### Query Performance Concerns

| Query Pattern | Complexity | Risk at Scale |
|--------------|-----------|---------------|
| Patient lookup by ID | O(1) | None |
| Clinical facts by patient | O(log n) | Low |
| Full-text document search | O(n) | HIGH - needs GIN index |
| Trial screening criteria | O(n) | HIGH - needs optimization |
| Screening aggregation | O(n) | MEDIUM - needs materialized views |
| KG subgraph extraction | O(n log n) | MEDIUM - needs depth limits |

### Recommended Indexes

1. `clinical_facts(patient_id, fact_type, created_at)` - btree - for screening queries
2. `screening_results(trial_id, patient_id, status)` - btree - for dashboard aggregation
3. `documents(content)` - GIN - for full-text search
4. `mentions(document_id, concept_id)` - btree - for NLP concept mapping
5. `kg_edges(source_id, target_id, relationship_type)` - btree - for graph traversal

### Partitioning Strategy

1. **clinical_facts** - Hash partition by `patient_id` (32 partitions)
2. **mentions** - Hash partition by `document_id` (16 partitions)
3. **screening_results** - Range partition by `created_at` (monthly, 12 partitions)

---

## Horizontal Scaling Readiness

| Service | Type | Horizontally Scalable | Session Affinity |
|---------|------|----------------------|-----------------|
| FastAPI Workers | Stateless | Yes | No |
| NLP Pipeline | Stateless | Yes | No |
| Trial Screening | Stateless | Yes | No |
| FHIR Import | Stateless | Yes | No |
| PostgreSQL | Stateful | No (read replicas) | Yes |
| Redis | Stateful | Yes (Cluster) | No |
| Neo4j | Stateful | No (Enterprise only) | Yes |

### Event-Driven Architecture Opportunities

1. NLP processing via Redis-backed task queue
2. FHIR import via webhook ingestion queue
3. Batch screening via event-driven re-screening on data change
4. CDC (Change Data Capture) for PostgreSQL event streaming
5. Redis Streams for real-time event processing

---

## Prioritized Remediation Roadmap

### Phase 1: Critical (Week 1-2)

| # | Action | Component | Effort | Impact |
|---|--------|-----------|--------|--------|
| 1 | Deploy PgBouncer connection pooler | PostgreSQL | Low | High |
| 2 | Add composite indexes for screening queries | PostgreSQL | Low | High |

### Phase 2: High Priority (Week 3-4)

| # | Action | Component | Effort | Impact |
|---|--------|-----------|--------|--------|
| 3 | Implement table partitioning for clinical_facts | PostgreSQL | Medium | High |
| 4 | Configure Redis maxmemory and eviction policy | Redis | Low | Medium |
| 5 | Implement batch screening with parallelization | Trial Screening | Medium | High |

### Phase 3: Medium Priority (Month 2)

| # | Action | Component | Effort | Impact |
|---|--------|-----------|--------|--------|
| 6 | Add graph traversal depth limits | Neo4j | Low | Medium |
| 7 | Audit and convert sync-to-async on I/O paths | FastAPI | Medium | Medium |
| 8 | Implement NLP processing queue with backpressure | NLP Pipeline | High | High |
| 9 | Add webhook ingestion queue | FHIR Import | Medium | Medium |

### Phase 4: Low Priority (Month 3+)

| # | Action | Component | Effort | Impact |
|---|--------|-----------|--------|--------|
| 10 | Implement graph summarization for large subgraphs | Knowledge Graph | High | Medium |

---

## API Reference

All endpoints are under `/api/v1/architecture/scalability`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Full scalability audit report |
| GET | `/components` | All component analyses |
| GET | `/components/{name}` | Single component detail |
| GET | `/projections` | Growth projections (1K-1M) |
| GET | `/recommendations` | Prioritized recommendations |
| GET | `/database` | Database-specific analysis |
| POST | `/simulate` | Simulate load at given patient count |

### Load Simulation Request

```json
{
  "patient_count": 100000,
  "concurrent_users": 200,
  "screening_rate_per_hour": 1000
}
```

---

## Conclusion

The platform's architecture is fundamentally sound for a clinical trial recruitment system. The primary scalability constraints are in the database layer and compute-intensive processing pipelines. Implementing the Phase 1 and Phase 2 actions (PgBouncer, composite indexes, table partitioning, and batch screening) will enable the platform to handle 100K+ patients. For 1M+ patients, the full roadmap including NLP worker pools and graph optimization should be completed.
