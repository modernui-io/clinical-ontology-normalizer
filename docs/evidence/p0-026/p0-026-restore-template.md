# P0-026 Backup Restore Drill Evidence

- Operator: ___
- Timestamp (UTC): ___
- Environment: staging/stage-dr

## PostgreSQL Restore

- Backup source:
- Backup method: PITR (WAL archive + base backup)
- Restore start:
- Restore complete:
- RTO (seconds):
- Row-count validation:
  - Table: clinical_facts — expected: ___ actual: ___
  - Table: kg_nodes — expected: ___ actual: ___
  - Table: kg_edges — expected: ___ actual: ___
- Integrity checks (pg_restore --clean --if-exists):
- Health check (/api/v1/health/ready):
- Result: PASS / FAIL

## Neo4j Restore

- Backup source:
- Backup method: neo4j-admin backup/restore
- Restore start:
- Restore complete:
- RTO (seconds):
- Consistency check (neo4j-admin consistency-checker):
- Node count validation: expected: ___ actual: ___
- Edge count validation: expected: ___ actual: ___
- Result: PASS / FAIL

## Final Evidence

- Overall PASS/FAIL:
- Combined RTO (max of PG + Neo4j):
- Issues encountered:
- Corrective actions:
- Reference: docs/operations/backup_restore_drill.md
