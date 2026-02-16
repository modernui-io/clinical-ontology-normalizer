# Data Retention Policy and Archival Controls for PHI

**Document ID**: GOV-P1-028
**Version**: 1.0
**Effective Date**: 2026-02-15
**Owner**: Compliance + Operations
**Classification**: Internal — Governance

## Purpose

Define retention periods, archival procedures, and deletion controls for all data stores containing Protected Health Information (PHI).

## Scope

All data stores in the clinical AI platform:
- PostgreSQL (clinical facts, documents, mentions, lineage, audit logs)
- Neo4j (knowledge graph nodes and edges)
- Redis (transient job queue data)
- Object storage (uploaded documents, exports)
- Log aggregation (application logs, access logs)

## Retention Periods

| Data Category | Store | Retention Period | Legal Basis |
|---|---|---|---|
| Clinical Facts | PostgreSQL | 7 years from creation | HIPAA, Australian Privacy Act |
| Source Documents | PostgreSQL + Object Storage | 7 years from upload | Medical records retention |
| Knowledge Graph | Neo4j | Until patient record deletion | Derived from clinical facts |
| Data Lineage | PostgreSQL | 7 years (matches clinical facts) | Audit trail requirement |
| Audit Logs | PostgreSQL + Log Aggregation | 7 years | HIPAA audit requirements |
| Job Queue Data | Redis | 72 hours | Transient operational data |
| Application Logs | Log Aggregation | 90 days (no PHI in logs) | Operational |
| Access Logs | Log Aggregation | 1 year | Security monitoring |
| Backup Archives | Object Storage | 90 days rolling | Disaster recovery |
| Export Artifacts | Object Storage | 30 days after generation | Transient delivery |

## Archival Procedures

### Annual Archival (Clinical Data >5 years)

1. Identify clinical facts older than 5 years with no recent access
2. Export to encrypted archival format (AES-256)
3. Transfer to cold storage tier (S3 Glacier / equivalent)
4. Verify archive integrity (checksum comparison)
5. Remove from hot database after archive verification
6. Record archival event in audit log

### Deletion Controls

**Pre-deletion checklist**:
- [ ] Retention period expired for ALL related records
- [ ] No active legal hold on patient/organization
- [ ] No pending audit or investigation
- [ ] Archival copy verified in cold storage
- [ ] Approval from Compliance Officer

**Deletion procedure**:
1. Soft-delete: Mark records as `deleted_at` with timestamp
2. Grace period: 30 days for recovery
3. Hard-delete: Permanent removal after grace period
4. Cascade: Delete dependent records (lineage, KG edges, mentions)
5. Audit: Record deletion event with operator, reason, scope

### Legal Hold Override

When a legal hold is active:
- ALL deletion jobs skip records tagged with hold ID
- Retention period timer pauses
- Hold must be explicitly released by Legal + Compliance
- Attempted deletion of held records triggers SEV-2 alert

## Automated Enforcement

### Retention Job

```python
# Scheduled daily at 02:00 AEDT
# backend/app/services/retention_enforcement.py

RETENTION_CONFIG = {
    "clinical_facts": {"retention_days": 2555, "archive_after_days": 1825},
    "documents": {"retention_days": 2555, "archive_after_days": 1825},
    "audit_logs": {"retention_days": 2555, "archive_after_days": 1825},
    "application_logs": {"retention_days": 90},
    "job_queue": {"retention_days": 3},
    "export_artifacts": {"retention_days": 30},
    "backup_archives": {"retention_days": 90},
}
```

### Monitoring

- Weekly report: Data volumes by retention tier
- Alert: Any deletion without matching audit record
- Alert: Archival job failure
- Monthly: Compliance review of retention adherence

## Data Residency

All PHI data must reside in the jurisdiction specified by the tenant's data residency policy:
- Australian pilot: All data in AU-EAST region
- No cross-border transfer without explicit consent and legal review
- Backup and archival storage in same region

## Audit Evidence

| Field | Value |
|---|---|
| Policy Review Date | |
| Reviewer | |
| Next Review | |
| Archival Job Status | Active / Inactive |
| Last Archival Run | |
| Records Archived | |
| Records Deleted | |
| Legal Holds Active | |
