# Immutable Release Checklist

**Document ID**: OPS-P1-035
**Version**: 1.0
**Effective Date**: 2026-02-15
**Owner**: CTO + Operations
**Classification**: Internal — Operational

## Purpose

Define the mandatory release checklist that ties each deployment SHA to its safety verification evidence. No deployment proceeds unless all gates pass.

## Release Artifact

Each release produces an immutable record:

```json
{
  "release_id": "rel-2026-MMDD-NNN",
  "git_sha": "<40-char commit hash>",
  "branch": "master",
  "timestamp": "<ISO 8601>",
  "deployer": "<operator name>",
  "environment": "production",
  "checklist_version": "1.0",
  "gates": { /* see below */ }
}
```

## Pre-Deployment Gates

### Gate 1: Code Quality

- [ ] All backend tests passing (`pytest` exit code 0)
- [ ] Test count: _____ (must not decrease from previous release)
- [ ] Frontend build clean (`npm run build` exit code 0)
- [ ] Lint passing (`ruff check` exit code 0)
- [ ] No new security advisories in dependencies

**Evidence**: CI pipeline URL, test report

### Gate 2: Safety Checks

- [ ] Drug safety regression suite passing
- [ ] OMOP mapping acceptance corpus passing
- [ ] OpenEHR replay validation passing
- [ ] Confidence policy tests passing
- [ ] No PHI in application logs (lint check)

**Evidence**: Test output files

### Gate 3: Security

- [ ] No hardcoded credentials in diff
- [ ] No new endpoints without authentication
- [ ] RBAC test suite passing
- [ ] Dependency audit clean (no critical CVEs)

**Evidence**: Security scan report

### Gate 4: Interoperability

- [ ] FHIR conformance suite passing (if FHIR changes)
- [ ] OpenEHR profile validation passing (if OpenEHR changes)
- [ ] Contract signatures unchanged (unless version bump documented)

**Evidence**: Conformance report

### Gate 5: Operational

- [ ] Database migration tested on staging
- [ ] Rollback procedure verified
- [ ] Monitoring dashboards show staging health
- [ ] On-call engineer notified

**Evidence**: Staging deployment URL, migration log

### Gate 6: Approval

- [ ] Release notes reviewed by CTO
- [ ] Changes in clinical pathways reviewed by Clinical AI Lead
- [ ] Changes in security reviewed by CISO
- [ ] Deployer is authorized operator

**Evidence**: Approval timestamps in release artifact

## Deployment Procedure

```bash
# 1. Tag the release
git tag -a "rel-2026-MMDD-NNN" -m "Release notes here"

# 2. Build production artifacts
docker compose -f docker-compose.prod.yml build

# 3. Run pre-flight checks
./scripts/release_preflight.sh

# 4. Deploy to staging, verify
./scripts/deploy.sh staging

# 5. Run smoke tests on staging
./scripts/smoke_test.sh staging

# 6. Deploy to production
./scripts/deploy.sh production

# 7. Post-deployment verification
curl https://api.sulci.ai/api/v1/health/ready
# Expected: {"status": "ready"}

# 8. Record release artifact
./scripts/record_release.sh
```

## Post-Deployment Monitoring

- **15 minutes**: Check error rates, latency, health endpoints
- **1 hour**: Review application logs for new errors
- **4 hours**: Verify all async jobs processing normally
- **24 hours**: Confirm no regression in clinical metrics

## Rollback Criteria

Automatic rollback if within 4 hours of deployment:
- Error rate >5% (baseline <1%)
- P95 latency >5x baseline
- Any SEV-1 incident attributed to release
- Health check non-ready

## Release History

| Release ID | SHA | Date | Deployer | Gates Passed | Status |
|---|---|---|---|---|---|
| | | | | | |

## Enforcement

- CI pipeline blocks merge to master unless Gate 1-3 pass
- Production deployment script checks for release tag
- Unsigned or untagged deployments are rejected
- Release artifact is write-once (append-only log)
