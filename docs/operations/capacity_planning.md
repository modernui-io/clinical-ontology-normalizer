# Capacity Planning

**Document ID:** COO-1-CP
**Last Updated:** 2026-02-08
**Review Cadence:** Quarterly
**Owner:** Operations Team

---

## 1. Current Resource Utilization Estimates

Based on production configuration in `docker-compose.prod.yml`.

### Compute Resources

| Service | CPU Limit | Memory Limit | Replicas | Estimated Baseline CPU | Estimated Baseline Memory |
|---------|-----------|-------------|----------|----------------------|-------------------------|
| PostgreSQL | 2 cores | 4 GB | 1 | 15-30% | 50-60% (shared_buffers=1GB) |
| Redis | 1 core | 1 GB | 1 | 5-10% | 20-40% (maxmemory=768MB) |
| Neo4j | 2 cores | 4 GB | 1 | 10-20% | 60-70% (heap 2GB + pagecache 1GB) |
| Backend API | 2 cores | 2 GB | 2 | 20-40% | 40-60% |
| RQ Worker | 1 core | 1 GB | 2 | 10-30% (bursty) | 30-50% |
| Kafka | 2 cores | 2 GB | 1 | 10-15% | 40-50% |
| Zookeeper | 0.5 cores | 512 MB | 1 | 5% | 30% |
| Frontend | 1 core | 512 MB | 2 | 5-10% | 30-40% |
| Nginx | 0.5 cores | 256 MB | 1 | 2-5% | 10-20% |

### Storage

| Volume | Current Estimated Size | Growth Rate | Notes |
|--------|----------------------|-------------|-------|
| `postgres_data` | 5-20 GB | ~1 GB/month per 1K patients | WAL + data + indexes |
| `redis_data` | 100-500 MB | Stable (eviction policy) | Bounded by maxmemory |
| `neo4j_data` | 2-10 GB | ~500 MB/month per 1K patients | Graph nodes + relationships |
| `kafka_data` | 1-5 GB | ~200 MB/day | 7-day retention configured |
| Object storage (documents) | 1-50 GB | ~100 MB per 1K documents | Clinical notes, FHIR bundles |

---

## 2. Growth Projections

### Patient and Data Volume Projections

| Metric | Current (estimate) | 6 Months | 12 Months | 24 Months |
|--------|-------------------|----------|-----------|-----------|
| Active patients | 1,000 | 5,000 | 15,000 | 50,000 |
| Clinical documents | 5,000 | 25,000 | 100,000 | 400,000 |
| Clinical facts | 50,000 | 250,000 | 1,000,000 | 5,000,000 |
| Active trials | 5 | 20 | 50 | 150 |
| Trial screenings/day | 100 | 500 | 2,000 | 10,000 |
| FHIR imports/day | 50 | 200 | 1,000 | 5,000 |
| KG nodes | 100,000 | 500,000 | 2,000,000 | 10,000,000 |
| KG edges | 300,000 | 1,500,000 | 6,000,000 | 30,000,000 |
| Concurrent API users | 10 | 50 | 200 | 500 |

### API Request Volume Projections

| Endpoint Category | Current RPS | 6 Months | 12 Months | 24 Months |
|-------------------|-------------|----------|-----------|-----------|
| Patient CRUD | 5 | 25 | 100 | 300 |
| Document ingestion | 2 | 10 | 50 | 200 |
| NLP extraction | 2 | 10 | 50 | 200 |
| Trial screening | 1 | 5 | 20 | 100 |
| FHIR operations | 3 | 15 | 60 | 200 |
| Graph queries | 1 | 5 | 20 | 50 |
| Health/metrics | 10 | 10 | 10 | 10 |

---

## 3. Scaling Triggers

### Automatic Scaling Thresholds

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| CPU utilization (sustained 5 min) | > 60% | > 80% | Add replicas / scale up |
| Memory utilization | > 70% | > 85% | Scale up memory / add replicas |
| DB connections (max_connections=200) | > 50% (100) | > 75% (150) | Add connection pooler (PgBouncer) |
| DB disk usage | > 60% | > 80% | Expand volume / archive old data |
| Redis memory (maxmemory=768MB) | > 70% (538 MB) | > 90% (691 MB) | Increase maxmemory / add node |
| API response time (p95) | > 500ms | > 2s | Profile + optimize / add replicas |
| Job queue depth | > 100 pending | > 500 pending | Add worker replicas |
| Kafka consumer lag | > 1,000 messages | > 10,000 messages | Add consumer instances |
| Error rate (5xx) | > 1% | > 5% | Investigate + remediate |

### Scaling Decision Matrix

| Growth Milestone | Infrastructure Change Required |
|-----------------|-------------------------------|
| 5,000 patients | Add PgBouncer connection pooler. Increase Redis maxmemory to 2GB. |
| 15,000 patients | PostgreSQL read replicas. Backend scaled to 4 replicas. Workers scaled to 4. |
| 50,000 patients | Dedicated PostgreSQL server (16 cores, 64GB RAM). Neo4j cluster (3 nodes). Kafka cluster (3 brokers). |
| 100,000+ patients | Sharded PostgreSQL or managed database service. Kubernetes autoscaling. Multi-region deployment. |

---

## 4. Database Growth Projections

### PostgreSQL Table Growth Estimates

| Table | Avg Row Size | Rows at 5K Patients | Rows at 50K Patients | Storage at 50K |
|-------|-------------|---------------------|---------------------|----------------|
| `patient` | 500 B | 5,000 | 50,000 | ~25 MB |
| `document` | 2 KB (metadata) | 25,000 | 400,000 | ~800 MB |
| `mention` | 300 B | 250,000 | 5,000,000 | ~1.5 GB |
| `mention_concept_candidate` | 200 B | 500,000 | 10,000,000 | ~2 GB |
| `clinical_fact` | 400 B | 125,000 | 2,500,000 | ~1 GB |
| `audit_log` | 1 KB | 500,000 | 20,000,000 | ~20 GB |
| `trial` | 5 KB | 50 | 150 | ~1 MB |
| `trial_screening` | 1 KB | 50,000 | 2,000,000 | ~2 GB |
| **Total (estimated)** | - | - | - | **~30 GB data + ~15 GB indexes** |

### Index Strategy

- Primary key indexes: automatic
- Foreign key indexes: on all FK columns
- Frequently queried columns: `patient_id`, `document_id`, `concept_id`, `created_at`
- Full-text search: GIN indexes on clinical text fields
- Partial indexes: on `status` columns for active/pending records
- Index size typically 30-50% of data size

### Archival Policy

| Data Type | Active Window | Archive After | Deletion After |
|-----------|--------------|---------------|---------------|
| Clinical documents | Indefinite | Never (PHI retention) | Per retention policy (6+ years) |
| Audit logs | 90 days (hot) | 90 days to cold storage | 6 years (HIPAA requirement) |
| Job queue history | 7 days | 30 days | 90 days |
| Screening results | 1 year | 1 year | 7 years |
| Knowledge graph snapshots | Current | Weekly snapshots for 90 days | 1 year |

---

## 5. Cost Model

### Per-Unit Cost Estimates

| Resource | Unit | Estimated Monthly Cost | Notes |
|----------|------|----------------------|-------|
| Compute (backend) | Per replica | $50-150 | 2 CPU, 2 GB RAM |
| Compute (worker) | Per replica | $30-80 | 1 CPU, 1 GB RAM |
| PostgreSQL | Per GB stored | $0.10-0.25 | Managed DB pricing |
| PostgreSQL | Per IOPS | $0.01-0.05 | Provisioned IOPS if needed |
| Redis | Per GB memory | $10-30 | Managed Redis pricing |
| Neo4j | Per instance | $100-500 | Self-hosted or AuraDB |
| Object storage | Per GB | $0.02-0.05 | S3-compatible |
| Object storage | Per 10K requests | $0.004-0.01 | GET/PUT operations |
| Backup storage | Per GB | $0.01-0.03 | Separate region |
| Network egress | Per GB | $0.05-0.12 | Cross-region transfer |

### Cost Per Business Unit

| Business Metric | Estimated Monthly Cost | Calculation Basis |
|----------------|----------------------|-------------------|
| Per patient (active) | $0.50-2.00 | Storage + compute share |
| Per document processed | $0.01-0.05 | NLP compute + storage |
| Per trial screening | $0.005-0.02 | Compute per evaluation |
| Per FHIR import | $0.02-0.10 | Parse + store + index |
| Per knowledge graph query | $0.001-0.005 | Neo4j compute share |

### Projected Monthly Infrastructure Costs

| Scale | Patients | Estimated Monthly Cost |
|-------|----------|----------------------|
| Small | 1,000 | $200-500 |
| Medium | 5,000 | $500-1,500 |
| Large | 15,000 | $1,500-4,000 |
| Enterprise | 50,000 | $4,000-12,000 |

*Costs are estimates and vary significantly by cloud provider, region, and commitment level (reserved vs. on-demand). Managed database services typically 2-3x self-hosted compute cost but reduce operational burden.*

---

## 6. Monitoring and Alerting

### Key Capacity Metrics to Track

- PostgreSQL: `pg_stat_activity` connection count, `pg_database_size`, table bloat ratio, replication lag
- Redis: `used_memory` vs `maxmemory`, `connected_clients`, `instantaneous_ops_per_sec`
- Neo4j: heap usage, page cache hit ratio, active transactions, store size
- Application: request rate, error rate, p50/p95/p99 latency, queue depth
- Infrastructure: CPU, memory, disk I/O, network I/O per container

### Capacity Review Triggers

- Any metric hitting "Warning" threshold for 7+ consecutive days
- Storage growth exceeding projection by 50%+
- New trial onboarding with 5,000+ expected patients
- Quarterly capacity review meeting (regardless of metrics)

---

*This document must be reviewed quarterly and updated when scaling actions are taken or projections change.*
