# Tenant Onboarding Automation and Preflight Validation

**Document ID**: OPS-P2-023
**Version**: 1.0
**Effective Date**: 2026-02-15
**Owner**: CIO + Interoperability
**Classification**: Internal — Operational

## Purpose

Define repeatable, automated onboarding for new tenants/sites, including preflight validation checks that must pass before any clinical data flows.

## Onboarding Sequence

### Phase 1: Provisioning (Automated)

```bash
# /opt/sulci/scripts/onboard_tenant.sh <tenant_id> <tenant_name> <region>
./onboard_tenant.sh au-mel-royal "Royal Melbourne Hospital" au-east
```

Steps:
1. Create tenant record in `organizations` table
2. Provision database schema (if multi-schema) or partition
3. Generate API credentials (client_id + client_secret)
4. Configure RBAC roles (admin, clinician, readonly, api)
5. Set data residency policy (region lock)
6. Enable audit logging for tenant
7. Create initial admin user account

### Phase 2: Integration Setup

1. Configure source connector (Meditech, FHIR, OpenEHR)
2. Upload mapping contract for tenant's EHR variant
3. Configure code system normalization overrides (if needed)
4. Set up webhook/callback URLs for async notifications
5. Test connectivity from platform to tenant's systems

### Phase 3: Preflight Validation

Automated checks that must all pass:

```python
PREFLIGHT_CHECKS = [
    {
        "name": "tenant_exists",
        "check": "SELECT COUNT(*) FROM organizations WHERE tenant_id = :tid",
        "expected": 1,
    },
    {
        "name": "rbac_configured",
        "check": "Verify admin role exists for tenant",
        "expected": True,
    },
    {
        "name": "connector_reachable",
        "check": "Test source system connectivity",
        "expected": "connected",
    },
    {
        "name": "mapping_contract_valid",
        "check": "Verify contract signature matches",
        "expected": True,
    },
    {
        "name": "sample_import_succeeds",
        "check": "Import 1 test composition",
        "expected": "success",
    },
    {
        "name": "audit_logging_active",
        "check": "Verify audit events generated for test actions",
        "expected": True,
    },
    {
        "name": "data_residency_enforced",
        "check": "Verify storage location matches policy",
        "expected": True,
    },
    {
        "name": "encryption_verified",
        "check": "Confirm TLS for all data paths",
        "expected": True,
    },
]
```

### Phase 4: Go-Live

- [ ] All preflight checks pass
- [ ] Integration onboarding checklist complete (P1-030)
- [ ] Tenant admin trained on platform access
- [ ] Support channel configured
- [ ] Monitoring dashboards include new tenant
- [ ] Operations Lead approval

## Offboarding Procedure

When a tenant leaves:

1. Disable all API credentials
2. Export tenant data per retention policy
3. Archive to cold storage
4. Delete from hot database after grace period (30 days)
5. Remove RBAC configurations
6. Update monitoring to exclude tenant
7. Record offboarding in audit log

## Automation Status

| Step | Current State | Target State |
|---|---|---|
| Provisioning | Semi-automated | Fully scripted |
| Integration | Manual | Scripted with connector templates |
| Preflight | Manual checklist | Automated test suite |
| Go-live | Manual approval | Approval gate in deployment pipeline |
| Offboarding | Manual | Scripted with confirmation gates |
