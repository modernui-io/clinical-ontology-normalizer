# Legal/Provider Contract Gate for External LLM with PHI Exposure

**Document ID**: GOV-P1-034
**Version**: 1.0
**Effective Date**: 2026-02-15
**Owner**: CISO + Legal
**Classification**: Internal — Governance

## Purpose

Define the mandatory review and approval process before any external LLM provider can receive data that may contain or be derived from Protected Health Information (PHI).

## Scope

Applies to ALL external model/inference providers used by the platform, including:
- Primary LLM providers (cloud inference APIs)
- Embedding model providers
- Specialized clinical NLP services
- Any third-party API that receives patient-derived text

## Approved Provider Registry

Only providers listed in this registry may receive PHI-adjacent data.

| Provider | Use Case | Contract Status | PHI Tier | Approved Date | Review Due |
|---|---|---|---|---|---|
| (None approved yet) | | | | | |

### PHI Tiers

| Tier | Description | Contract Requirements |
|---|---|---|
| Tier 0 — No PHI | Only anonymized/synthetic data | Standard API terms |
| Tier 1 — De-identified | Statistically de-identified per HIPAA Safe Harbor | BAA + de-identification attestation |
| Tier 2 — Limited PHI | Dates, ages, locations (limited dataset) | BAA + data use agreement |
| Tier 3 — Full PHI | Direct identifiers possible | BAA + HIPAA compliance attestation + security review |

## Approval Process

### Step 1: Provider Assessment

Before any contract negotiation:

- [ ] Provider's security posture documented (SOC 2, ISO 27001, HITRUST)
- [ ] Data processing location identified (must meet residency requirements)
- [ ] Data retention policy reviewed (ideally zero retention)
- [ ] Model training policy reviewed (must not train on our data)
- [ ] Incident response capabilities assessed
- [ ] Sub-processor list reviewed

### Step 2: Legal Review

- [ ] Business Associate Agreement (BAA) executed (if Tier 1+)
- [ ] Data Processing Agreement reviewed by Legal
- [ ] Indemnification and liability terms acceptable
- [ ] Termination and data deletion clauses present
- [ ] Jurisdiction and governing law acceptable

### Step 3: Technical Review

- [ ] API security reviewed (TLS 1.2+, authentication, rate limiting)
- [ ] Data in transit encryption verified
- [ ] Data at rest encryption at provider confirmed
- [ ] Audit logging available from provider
- [ ] Failover and SLA terms documented

### Step 4: CISO Sign-Off

- [ ] Risk assessment completed
- [ ] Residual risk acceptable given PHI tier
- [ ] Monitoring plan for provider compliance
- [ ] Annual review schedule set

### Step 5: CIO/CTO Approval

- [ ] Business justification documented
- [ ] Cost implications reviewed
- [ ] Alternatives evaluated and documented
- [ ] Provider added to approved registry

## Runtime Enforcement

### Technical Controls

The platform enforces provider approval at runtime:

1. **Provider routing policy** (`backend/app/core/config.py`): Only approved provider endpoints allowed
2. **PHI gate** (P0-017): Requests to unapproved endpoints blocked with error code
3. **Audit logging**: All external model calls logged with provider ID, data tier, timestamp
4. **Circuit breaker**: Automatic fallback to rule-based processing if provider unavailable

### Configuration

```python
APPROVED_LLM_PROVIDERS = {
    # "anthropic": {
    #     "endpoint": "https://api.anthropic.com/v1",
    #     "phi_tier": 0,
    #     "baa_status": "not_required",
    #     "approved_date": "2026-XX-XX",
    # },
}

# Block any provider not in approved list
ENFORCE_PROVIDER_REGISTRY = True
```

## Review Cadence

- **Quarterly**: Review all approved providers for compliance changes
- **Annually**: Full re-assessment of each provider
- **On change**: Any provider terms change triggers re-review
- **On incident**: Security incident at provider triggers immediate assessment

## Revocation

If a provider's approval is revoked:
1. Immediately route all traffic to fallback (rule-based)
2. Notify affected teams
3. Document reason for revocation
4. Remove from approved registry
5. Assess data exposure during approval period
