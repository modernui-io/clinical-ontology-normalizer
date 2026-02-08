# Disaster Recovery Plan

**Document ID:** COO-1-DR
**Classification:** HIPAA Confidential
**Last Updated:** 2026-02-08
**Review Cadence:** Quarterly
**Owner:** Operations Team

---

## 1. Purpose and Scope

This Disaster Recovery (DR) Plan defines the procedures for recovering the Clinical Ontology Normalizer platform following a service disruption. The platform handles Protected Health Information (PHI) under HIPAA and supports clinical trial patient recruitment, making availability and data integrity critical.

### Systems Covered

| System | Role | Data Classification |
|--------|------|-------------------|
| PostgreSQL (primary database) | Patient data, clinical facts, trial enrollment, OMOP mappings | PHI - Critical |
| Redis | Job queue (RQ), session cache, rate limit state | Transient - Operational |
| Neo4j | Knowledge graph persistence | Derived - Important |
| FastAPI backend (+ RQ workers) | Application logic, NLP pipeline, FHIR import | Stateless - Critical |
| Next.js frontend | User interface | Stateless - Standard |
| Kafka + Zookeeper | HL7v2/FHIR streaming messages | Transient - Important |
| Nginx reverse proxy | TLS termination, routing | Stateless - Standard |

### Recovery Objectives

| Objective | Clinical Data (PHI) | Analytics / Derived Data | Transient State |
|-----------|-------------------|------------------------|-----------------|
| **RPO** (Recovery Point Objective) | 1 hour | 4 hours | Best effort |
| **RTO** (Recovery Time Objective) | 4 hours | 24 hours | 4 hours |
| **MTD** (Maximum Tolerable Downtime) | 8 hours | 48 hours | 24 hours |

---

## 2. Business Impact Analysis

### Critical Systems Ranked by Impact

| Rank | System | Impact if Down | MTD | Dependencies |
|------|--------|---------------|-----|-------------|
| 1 | PostgreSQL | Total platform outage. No patient data, no trial matching, no clinical facts. PHI loss risk. | 4 hours | Volume storage, network |
| 2 | FastAPI backend | No API access. Frontend non-functional. FHIR imports halt. | 4 hours | PostgreSQL, Redis |
| 3 | Redis | Job queue halted. No document processing, no NLP extraction. Background tasks fail. | 8 hours | Network |
| 4 | FHIR import pipeline | No new patient data ingestion. Trial screening stalls on stale data. | 12 hours | Backend, PostgreSQL |
| 5 | NLP pipeline | No new clinical entity extraction. Existing data still queryable. | 12 hours | Backend, Redis, PostgreSQL |
| 6 | Neo4j | Knowledge graph queries fail. Core OMOP functionality unaffected. | 24 hours | Network |
| 7 | Kafka + Zookeeper | Real-time streaming halted. REST-based ingestion unaffected. | 24 hours | Network |
| 8 | Next.js frontend | No web UI. API still accessible programmatically. | 24 hours | Backend |
| 9 | Nginx | No external access (if single proxy). Direct port access possible. | 4 hours | Network |

### Data Loss Impact

- **Patient demographics and clinical notes**: Irreplaceable without re-entry. 1-hour RPO mandatory.
- **Trial eligibility screenings**: Can be re-derived from patient data + trial criteria. 4-hour RPO acceptable.
- **Knowledge graph**: Fully rebuildable from clinical facts. Loss is time cost, not data cost.
- **Job queue state**: In-flight jobs lost. Documents can be resubmitted. Best-effort RPO.

---

## 3. Backup Strategy

### 3.1 PostgreSQL

| Component | Method | Frequency | Retention | Storage |
|-----------|--------|-----------|-----------|---------|
| Base backup | `pg_basebackup` full dump | Daily at 02:00 UTC | 30 days | Encrypted object storage (separate region) |
| WAL archiving | Continuous WAL shipping (`archive_command`) | Continuous | 7 days | Encrypted object storage (separate region) |
| Logical backup | `pg_dump --format=custom` | Weekly (Sunday 03:00 UTC) | 90 days | Encrypted object storage |

**Configuration requirements** (from `docker-compose.prod.yml`):
- `wal_level = replica`
- `archive_mode = on`
- `archive_command` configured to ship to encrypted object storage
- `max_wal_size = 4GB` (already configured)
- All backups encrypted with AES-256 at rest
- Backup credentials stored in Vault, not in environment variables

**Point-in-Time Recovery (PITR)**: Base backup + WAL replay allows recovery to any point within the WAL retention window (7 days).

### 3.2 Redis

| Component | Method | Frequency | Retention |
|-----------|--------|-----------|-----------|
| AOF persistence | `appendonly yes` (already configured) | Continuous | Current state |
| RDB snapshot | `BGSAVE` | Every 15 minutes | 24 hours (96 snapshots) |
| External backup | Copy RDB file to object storage | Daily | 7 days |

Redis data is transient (job queue, session cache). Full loss is tolerable -- jobs can be resubmitted. The primary concern is minimizing queue recovery time.

### 3.3 Neo4j

| Component | Method | Frequency | Retention |
|-----------|--------|-----------|-----------|
| Full backup | `neo4j-admin database dump` | Daily at 04:00 UTC | 14 days |
| Incremental | Transaction log backup | Every 4 hours | 7 days |

Neo4j data is derived from PostgreSQL clinical facts. Complete rebuild is possible via the graph builder pipeline, though it may take several hours for large datasets.

### 3.4 Application Code and Configuration

| Component | Method | Notes |
|-----------|--------|-------|
| Source code | Git repository (multiple remotes) | Immutable history. Tag all releases. |
| Container images | Container registry with immutable tags | Never overwrite production tags. Use SHA digests. |
| Infrastructure config | `docker-compose*.yml`, `k8s/` in Git | Version-controlled. Review all changes. |
| Environment variables | Vault or encrypted secrets manager | Backup Vault seal keys separately. |
| TLS certificates | Vault PKI or ACME provider | Auto-renewal configured. Backup CA chain. |

### 3.5 Document and FHIR Bundle Storage

| Component | Method | Frequency |
|-----------|--------|-----------|
| Uploaded documents | Object storage with versioning enabled | On upload |
| FHIR bundles | Object storage with versioning enabled | On import |
| Cross-region replication | Async replication to secondary region | Continuous |

### 3.6 Encryption Requirements (HIPAA)

- All backups encrypted with AES-256 at rest
- All backup transfers encrypted with TLS 1.2+ in transit
- Encryption keys managed via Vault or cloud KMS (never stored alongside backups)
- Backup access restricted to operations team (principle of least privilege)
- All backup access logged in audit trail

---

## 4. Recovery Procedures

### Tier 1: Service Restart (< 1 hour)

**Trigger**: Single container crash, OOM kill, healthcheck failure.

**Procedure**:
1. Docker/Kubernetes auto-restart handles most cases (`restart: unless-stopped`)
2. Verify healthcheck passes: `curl -f http://localhost:8000/health`
3. Check logs for root cause: `docker logs con-backend --tail 100`
4. If auto-restart fails, manually restart: `docker compose restart backend`
5. Verify readiness: `curl http://localhost:8000/ready`
6. Confirm no data loss by checking recent audit log entries

**Rollback**: If new deployment caused crash, roll back to previous image tag.

### Tier 2: Database Failover / PITR (1-4 hours)

**Trigger**: PostgreSQL data corruption, accidental data deletion, failed migration.

**Procedure**:
1. **Assess scope**: Determine if corruption is limited or systemic
2. **Stop application writes**: Scale backend replicas to 0
3. **Point-in-Time Recovery**:
   a. Identify target recovery time from audit logs
   b. Restore latest base backup preceding the target time
   c. Replay WAL to target time: `recovery_target_time = '<timestamp>'`
   d. Verify data integrity: Run consistency checks on patient, clinical_fact, mention tables
4. **Restart application**: Scale backend replicas back up
5. **Verify**: Run smoke tests against critical API endpoints
6. **Re-process**: Resubmit any documents ingested after recovery point

**Redis recovery** (if needed):
1. Stop Redis container
2. Replace `appendonly.aof` with last known good backup
3. Restart Redis
4. Verify job queue state

### Tier 3: Full Environment Rebuild (4-24 hours)

**Trigger**: Complete infrastructure loss (single region), multiple service corruption.

**Procedure**:
1. **Provision infrastructure**: Deploy from `docker-compose.prod.yml` or `k8s/` manifests
2. **Restore PostgreSQL**:
   a. Deploy fresh PostgreSQL instance
   b. Restore from latest base backup + WAL replay
   c. Run Alembic migrations to confirm schema: `alembic upgrade head`
   d. Verify row counts against backup manifest
3. **Restore Redis**: Deploy fresh instance. Queue state will rebuild on first use.
4. **Restore Neo4j**: Restore from latest dump or rebuild from PostgreSQL data.
5. **Deploy application**:
   a. Pull production container images (pinned SHA digests)
   b. Inject secrets from Vault
   c. Start backend, workers, frontend
   d. Verify all healthchecks pass
6. **Rebuild derived data**:
   a. Trigger knowledge graph rebuild from clinical facts
   b. Resubmit any pending FHIR imports
7. **Validation**:
   a. Run full API smoke test suite
   b. Verify patient count matches pre-incident
   c. Confirm FHIR endpoints respond correctly
   d. Verify audit log continuity

### Tier 4: Cross-Region Failover (24-72 hours)

**Trigger**: Complete region outage, natural disaster, extended infrastructure provider outage.

**Procedure**:
1. **Activate secondary region** infrastructure
2. **Restore PostgreSQL** from cross-region backup replicas
3. **Update DNS** to point to secondary region endpoints
4. **Deploy application stack** in secondary region
5. **Verify TLS certificates** are valid for the domain
6. **Run full validation suite** (same as Tier 3 step 7)
7. **Notify stakeholders** of region change and any data gap
8. **Plan failback** to primary region when available

---

## 5. DR Testing Schedule

| Frequency | Test Type | Scope | Success Criteria |
|-----------|-----------|-------|-----------------|
| **Monthly** | Backup integrity verification | Verify checksums on all backup types. Restore PostgreSQL backup to isolated instance and run read queries. | All checksums pass. Restored DB returns correct patient count. |
| **Quarterly** | Single-service recovery drill | Simulate failure of one critical service (rotate: PostgreSQL, Redis, backend). Execute Tier 1 or Tier 2 recovery. | Service recovered within RTO. No data loss beyond RPO. |
| **Semi-annually** | Full DR exercise | Execute Tier 3 recovery in isolated environment. Rebuild entire stack from backups. | Full environment operational within 24 hours. All smoke tests pass. |
| **Annually** | Cross-region failover test | Execute Tier 4 failover to secondary region. Validate full functionality. Failback to primary. | Failover and failback complete. Data integrity confirmed. |

### Test Documentation Requirements

Each DR test must produce:
- Test date, participants, and scenario description
- Step-by-step execution log with timestamps
- Actual recovery time vs. target (RTO/RPO)
- Issues encountered and resolutions
- Action items for improving the DR plan
- Sign-off by operations lead

---

## 6. Communication Plan

### Escalation Matrix

| Severity | Response Time | Notification Method | Who to Notify |
|----------|--------------|-------------------|--------------|
| **SEV1** (complete outage) | 15 minutes | Phone + SMS + Slack #incidents | On-call engineer, Engineering Lead, CTO, Compliance Officer |
| **SEV2** (partial outage, PHI risk) | 30 minutes | Slack #incidents + Email | On-call engineer, Engineering Lead, Compliance Officer |
| **SEV3** (degraded performance) | 1 hour | Slack #incidents | On-call engineer, Engineering Lead |
| **SEV4** (minor issue, no data risk) | 4 hours | Slack #ops | On-call engineer |

### Notification Order (SEV1/SEV2)

1. On-call engineer acknowledges and begins assessment (0-15 min)
2. Engineering Lead notified with initial assessment (15-30 min)
3. CTO notified if RTO may be exceeded (30-60 min)
4. Compliance Officer notified if PHI exposure suspected (immediately)
5. HIPAA Breach Notification process triggered if PHI confirmed exposed (see section 7)
6. External stakeholders (trial sponsors, partner sites) notified if outage exceeds 4 hours

### Communication Channels

| Channel | Use |
|---------|-----|
| Slack #incidents | Real-time incident coordination |
| Slack #ops | Non-critical operational updates |
| Email distribution list | Formal notifications, post-incident reports |
| Phone tree | SEV1 escalation when Slack unavailable |
| Status page | External stakeholder communication |

---

## 7. HIPAA Considerations

### PHI Protection During Recovery

- All recovery procedures must maintain PHI encryption in transit and at rest
- Temporary recovery environments must meet the same security controls as production
- Recovery team members must have completed HIPAA training and signed BAAs
- No PHI may be copied to personal devices, unsecured storage, or non-BAA environments
- All recovery actions involving PHI access must be logged in the audit trail
- Recovery environments must be decommissioned and securely wiped after use

### Audit Trail Continuity

- The audit service (`app.services.audit_service`) logs all PHI access events
- During recovery, verify audit log continuity -- no gaps allowed
- If audit logs are lost, this must be documented as a potential HIPAA incident
- Post-recovery, verify the last pre-incident audit entry matches the first post-recovery entry
- Audit logs are stored in PostgreSQL and must be included in all backup procedures

### Breach Notification Requirements

If recovery reveals a PHI breach (unauthorized access, data exposure):

1. **Document**: Record the nature, scope, and timeline of the breach
2. **Assess**: Determine if unsecured PHI was compromised
3. **Notify HHS**: Within 60 days if 500+ individuals affected (immediate if significant)
4. **Notify individuals**: Within 60 days via written notice
5. **Notify media**: If 500+ individuals in a single state/jurisdiction
6. **Retain records**: All breach documentation retained for 6 years

### Backup Media Handling

- Backup media (disks, tapes, cloud storage) containing PHI must be tracked in an inventory
- Decommissioned backup media must be securely destroyed (NIST SP 800-88 guidelines)
- Cloud storage deletion must include verification that data is irrecoverable
- Annual audit of backup media inventory against retention policy

---

## Appendix A: Recovery Runbook Quick Reference

```
TIER 1 - Service Restart (< 1 hour)
  docker compose restart <service>
  curl -f http://localhost:8000/health
  curl http://localhost:8000/ready

TIER 2 - Database PITR (1-4 hours)
  1. docker compose stop backend worker
  2. pg_restore --dbname=clinical_ontology <backup_file>
  3. Set recovery_target_time in postgresql.conf
  4. docker compose start postgres
  5. Wait for recovery to complete
  6. docker compose start backend worker
  7. Run smoke tests

TIER 3 - Full Rebuild (4-24 hours)
  1. docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d postgres redis neo4j
  2. Restore PostgreSQL from backup
  3. alembic upgrade head
  4. docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
  5. Rebuild knowledge graph
  6. Run full validation suite

TIER 4 - Cross-Region (24-72 hours)
  1. Activate secondary region infrastructure
  2. Restore from cross-region backups
  3. Update DNS records
  4. Deploy and validate
```

## Appendix B: Contact List

| Role | Name | Phone | Email |
|------|------|-------|-------|
| Primary On-Call | [TBD] | [TBD] | [TBD] |
| Secondary On-Call | [TBD] | [TBD] | [TBD] |
| Engineering Lead | [TBD] | [TBD] | [TBD] |
| CTO | [TBD] | [TBD] | [TBD] |
| HIPAA Privacy Officer | [TBD] | [TBD] | [TBD] |
| HIPAA Security Officer | [TBD] | [TBD] | [TBD] |
| Cloud Provider Support | [TBD] | [TBD] | [TBD] |

---

*This document must be reviewed quarterly and updated after every DR test or actual incident.*
