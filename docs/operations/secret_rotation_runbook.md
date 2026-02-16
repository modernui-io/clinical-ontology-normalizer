# Secret Rotation Tooling and Operational Runbooks

**Document ID**: SEC-P3-012
**Version**: 1.0
**Effective Date**: 2026-02-15
**Owner**: Security + Operations
**Classification**: Internal — Security

## Purpose

Define the secret rotation procedures, tooling, and drill schedule for all credentials used by the platform.

## Secret Inventory

| Secret | Store | Rotation Period | Auto-Rotate | Owner |
|---|---|---|---|---|
| PostgreSQL password | Env/Secrets Manager | 90 days | Yes (target) | Operations |
| Redis password | Env/Secrets Manager | 90 days | Yes (target) | Operations |
| Neo4j password | Env/Secrets Manager | 90 days | Yes (target) | Operations |
| API signing key | Secrets Manager | 180 days | Yes | Security |
| JWT secret | Secrets Manager | 90 days | No (rolling) | Security |
| LLM provider API key | Secrets Manager | 90 days | No | Security |
| S3 access credentials | IAM role | N/A (role-based) | N/A | Operations |
| SMTP credentials | Secrets Manager | 180 days | No | Operations |
| Webhook signing secret | Secrets Manager | 180 days | No | Operations |

## Rotation Procedure

### Database Credentials (PostgreSQL, Redis, Neo4j)

```bash
#!/bin/bash
# /opt/sulci/scripts/rotate_db_credentials.sh
set -euo pipefail

DB_TYPE="$1"  # postgres, redis, neo4j
NEW_PASSWORD=$(openssl rand -base64 32)

# 1. Update password in secrets manager
aws secretsmanager update-secret \
  --secret-id "sulci/${DB_TYPE}/password" \
  --secret-string "${NEW_PASSWORD}"

# 2. Update password on database server
case "$DB_TYPE" in
  postgres)
    psql -h "$POSTGRES_HOST" -U admin -c \
      "ALTER USER sulci_app PASSWORD '${NEW_PASSWORD}';"
    ;;
  redis)
    redis-cli -h "$REDIS_HOST" CONFIG SET requirepass "${NEW_PASSWORD}"
    ;;
  neo4j)
    cypher-shell -u neo4j "ALTER CURRENT USER SET PASSWORD FROM '${OLD_PASSWORD}' TO '${NEW_PASSWORD}';"
    ;;
esac

# 3. Restart application to pick up new credentials
# (or use dynamic secret refresh if implemented)
kubectl rollout restart deployment/sulci-api

# 4. Verify connectivity
sleep 30
curl -f https://api.internal/api/v1/health/ready || {
  echo "ROTATION FAILED - ROLLING BACK"
  # Rollback steps here
  exit 1
}

echo "Rotation successful for ${DB_TYPE}"
```

### API Key Rotation

1. Generate new key in provider dashboard
2. Add new key to Secrets Manager (keep old key active)
3. Deploy with new key configuration
4. Verify new key works (test API call)
5. Revoke old key in provider dashboard
6. Remove old key from Secrets Manager

### JWT Secret Rolling Rotation

JWT secrets use rolling rotation to avoid invalidating active tokens:

1. Add new secret as `JWT_SECRET_NEW` alongside `JWT_SECRET`
2. Deploy — app signs with new, validates with both
3. Wait for token TTL to expire (default: 24 hours)
4. Promote: Move `JWT_SECRET_NEW` to `JWT_SECRET`, remove old
5. Deploy final configuration

## Drill Schedule

| Frequency | Activity |
|---|---|
| Monthly | Rotate one database credential in staging |
| Quarterly | Full rotation drill in staging (all secrets) |
| Semi-annually | Production rotation of non-critical secrets |
| Annually | Full production rotation with downtime window |

## Monitoring

- Alert if any secret exceeds rotation period by >7 days
- Alert if rotation script fails
- Dashboard showing secret ages and next rotation dates
- Post-rotation health check verification

## Emergency Rotation (Credential Compromise)

If a credential is suspected compromised:

1. **Immediately**: Generate new credential
2. **Within 15 min**: Deploy new credential to all services
3. **Within 30 min**: Revoke compromised credential
4. **Within 1 hour**: Verify no unauthorized access during exposure
5. **Within 24 hours**: Complete incident report
