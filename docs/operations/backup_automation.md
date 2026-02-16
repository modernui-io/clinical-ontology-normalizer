# Scheduled Backup Automation and Restore Verification

**Document ID**: OPS-P2-016
**Version**: 1.0
**Effective Date**: 2026-02-15
**Owner**: Operations
**Classification**: Internal — Operational

## Backup Schedule

| Store | Frequency | Retention | Method | Storage |
|---|---|---|---|---|
| PostgreSQL | Daily 02:00 AEDT | 90 days rolling | pg_dump (custom format) | S3 encrypted |
| Neo4j | Daily 03:00 AEDT | 90 days rolling | neo4j-admin dump | S3 encrypted |
| Redis | Hourly RDB snapshot | 24 hours | Redis BGSAVE | Local + S3 |
| Application Config | On change (git-triggered) | Indefinite | Git archive | Git repository |

## PostgreSQL Backup Script

```bash
#!/bin/bash
# /opt/sulci/scripts/backup_postgres.sh
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/backups/postgres"
S3_BUCKET="${BACKUP_S3_BUCKET}"
DB_NAME="${POSTGRES_DB:-sulci}"
DB_HOST="${POSTGRES_HOST:-localhost}"

# Create backup
pg_dump -h "$DB_HOST" -U postgres -Fc "$DB_NAME" \
  > "${BACKUP_DIR}/sulci_${TIMESTAMP}.dump"

# Upload to S3 with server-side encryption
aws s3 cp "${BACKUP_DIR}/sulci_${TIMESTAMP}.dump" \
  "s3://${S3_BUCKET}/postgres/sulci_${TIMESTAMP}.dump" \
  --sse AES256

# Cleanup local backups older than 7 days
find "$BACKUP_DIR" -name "sulci_*.dump" -mtime +7 -delete

# Record in monitoring
echo "{\"type\":\"backup\",\"store\":\"postgres\",\"timestamp\":\"${TIMESTAMP}\",\"status\":\"success\"}" \
  | logger -t sulci-backup
```

## Neo4j Backup Script

```bash
#!/bin/bash
# /opt/sulci/scripts/backup_neo4j.sh
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/backups/neo4j"
S3_BUCKET="${BACKUP_S3_BUCKET}"

neo4j-admin database dump neo4j \
  --to-path="${BACKUP_DIR}/neo4j_${TIMESTAMP}"

tar czf "${BACKUP_DIR}/neo4j_${TIMESTAMP}.tar.gz" \
  -C "$BACKUP_DIR" "neo4j_${TIMESTAMP}"

aws s3 cp "${BACKUP_DIR}/neo4j_${TIMESTAMP}.tar.gz" \
  "s3://${S3_BUCKET}/neo4j/neo4j_${TIMESTAMP}.tar.gz" \
  --sse AES256

find "$BACKUP_DIR" -name "neo4j_*.tar.gz" -mtime +7 -delete

echo "{\"type\":\"backup\",\"store\":\"neo4j\",\"timestamp\":\"${TIMESTAMP}\",\"status\":\"success\"}" \
  | logger -t sulci-backup
```

## Cron Schedule

```cron
# /etc/cron.d/sulci-backups
0 2 * * * root /opt/sulci/scripts/backup_postgres.sh >> /var/log/sulci-backup.log 2>&1
0 3 * * * root /opt/sulci/scripts/backup_neo4j.sh >> /var/log/sulci-backup.log 2>&1
```

## Automated Restore Verification

Weekly automated verification that backups are restorable:

```bash
#!/bin/bash
# /opt/sulci/scripts/verify_restore.sh
set -euo pipefail

# Get latest backup
LATEST=$(aws s3 ls "s3://${BACKUP_S3_BUCKET}/postgres/" | sort | tail -1 | awk '{print $4}')

# Download to staging
aws s3 cp "s3://${BACKUP_S3_BUCKET}/postgres/${LATEST}" /tmp/restore_test.dump

# Restore to test database
psql -h staging-db -U admin -c "DROP DATABASE IF EXISTS restore_test;"
psql -h staging-db -U admin -c "CREATE DATABASE restore_test;"
pg_restore -h staging-db -U admin -d restore_test /tmp/restore_test.dump --no-owner 2>&1

# Validate
COUNT=$(psql -h staging-db -U admin -d restore_test -t -c "SELECT COUNT(*) FROM clinical_facts;")

if [ "$COUNT" -gt 0 ]; then
  echo "{\"type\":\"restore_verify\",\"status\":\"success\",\"record_count\":${COUNT}}"
else
  echo "{\"type\":\"restore_verify\",\"status\":\"FAILED\",\"record_count\":0}"
  # Alert on failure
  curl -X POST "${ALERT_WEBHOOK}" -d '{"text":"BACKUP RESTORE VERIFICATION FAILED"}'
fi

# Cleanup
psql -h staging-db -U admin -c "DROP DATABASE restore_test;"
rm /tmp/restore_test.dump
```

## Monitoring and Alerts

| Alert | Condition | Severity |
|---|---|---|
| Backup missed | No backup file created in 25 hours | SEV-2 |
| Backup failed | Script exit code non-zero | SEV-2 |
| Restore verification failed | Weekly verify returns FAILED | SEV-2 |
| Storage quota approaching | S3 bucket >80% of budget | SEV-3 |
| Backup age | Latest backup >48 hours old | SEV-3 |
