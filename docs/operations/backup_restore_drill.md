# Backup Restore Drill — PostgreSQL and Neo4j

**Document ID**: OPS-P0-026
**Version**: 1.0
**Effective Date**: 2026-02-15
**Owner**: Operations
**Classification**: Internal — Operational

## Purpose

Document the procedure for executing a backup restore drill for both PostgreSQL (primary datastore) and Neo4j (knowledge graph). This drill must be executed at least once before pilot go-live, with results recorded as evidence.

## Prerequisites

- [ ] Backup automation running (daily PostgreSQL, daily Neo4j)
- [ ] Restore target environment provisioned (staging or DR)
- [ ] Network access to backup storage (S3/GCS/local)
- [ ] DBA or authorized operator identified

## PostgreSQL Backup Restore Drill

### Step 1: Verify Latest Backup Exists

```bash
# List recent backups
aws s3 ls s3://${BACKUP_BUCKET}/postgres/ --recursive | sort | tail -5

# Or for local backups
ls -la /var/backups/postgres/ | tail -5
```

**Record**: Backup timestamp, size, location.

### Step 2: Restore to Staging

```bash
# Create restore target database
psql -h staging-db -U admin -c "CREATE DATABASE sulci_restore_drill;"

# Restore from backup
pg_restore -h staging-db -U admin -d sulci_restore_drill \
  /path/to/backup/sulci_$(date +%Y%m%d).dump \
  --no-owner --no-privileges --verbose 2>&1 | tee restore_drill.log
```

### Step 3: Validate Data Integrity

```sql
-- Check table counts match production
SELECT 'clinical_facts' AS table_name, COUNT(*) FROM clinical_facts
UNION ALL
SELECT 'kg_nodes', COUNT(*) FROM kg_nodes
UNION ALL
SELECT 'kg_edges', COUNT(*) FROM kg_edges
UNION ALL
SELECT 'data_lineage', COUNT(*) FROM data_lineage
UNION ALL
SELECT 'documents', COUNT(*) FROM documents;
```

```sql
-- Verify recent data present
SELECT MAX(created_at) AS latest_record FROM clinical_facts;
-- Should be within backup window (< 24 hours old)
```

### Step 4: Application Smoke Test

```bash
# Point staging app at restored DB and run health check
curl https://staging-restored/api/v1/health/ready
# Expected: {"status": "ready"}

# Run a sample query
curl -X POST https://staging-restored/api/v1/openehr/archetypes
# Expected: 200 with archetype list
```

### Step 5: Measure Recovery Time

| Metric | Value |
|---|---|
| Backup size | |
| Download time | |
| Restore time | |
| Validation time | |
| **Total RTO** | |

### Step 6: Cleanup

```bash
psql -h staging-db -U admin -c "DROP DATABASE sulci_restore_drill;"
```

## Neo4j Backup Restore Drill

### Step 1: Verify Latest Backup

```bash
# Check Neo4j backup location
ls -la /var/backups/neo4j/ | tail -5
# Or cloud storage
aws s3 ls s3://${BACKUP_BUCKET}/neo4j/ --recursive | sort | tail -5
```

### Step 2: Restore to Staging

```bash
# Stop staging Neo4j instance
neo4j stop

# Restore from backup
neo4j-admin database restore \
  --from-path=/path/to/backup/neo4j-$(date +%Y%m%d) \
  --database=neo4j \
  --overwrite-destination

# Start Neo4j
neo4j start
```

### Step 3: Validate Graph Integrity

```cypher
// Count nodes by type
MATCH (n) RETURN labels(n)[0] AS type, COUNT(n) AS count ORDER BY count DESC;

// Count edges by type
MATCH ()-[r]->() RETURN type(r) AS type, COUNT(r) AS count ORDER BY count DESC;

// Verify patient connectivity
MATCH (p:Patient)-[r]->(n) RETURN p.patient_id, COUNT(r) LIMIT 10;
```

### Step 4: Measure Recovery Time

| Metric | Value |
|---|---|
| Backup size | |
| Restore time | |
| Validation time | |
| **Total RTO** | |

## Evidence Record Template

| Field | Value |
|---|---|
| Drill Date | |
| Operator | |
| PostgreSQL Backup Date | |
| PostgreSQL RTO | |
| PostgreSQL Data Verified | YES / NO |
| Neo4j Backup Date | |
| Neo4j RTO | |
| Neo4j Data Verified | YES / NO |
| Overall Status | PASS / FAIL |
| Issues Found | |
| Corrective Actions | |
| Approved By | |

## Schedule

- Pre-pilot: Execute full drill, record evidence
- Monthly during pilot: Execute automated restore validation
- Quarterly post-pilot: Full manual drill with report
