# Kafka HA Strategy Decision

**Document ID**: OPS-P2-014
**Version**: 1.0
**Effective Date**: 2026-02-15
**Owner**: CTO + Operations
**Classification**: Internal — Architecture Decision

## Decision Summary

**Recommended**: Managed Kafka service (AWS MSK or Confluent Cloud) for production, self-hosted single-broker for development/staging.

## Options Evaluated

### Option A: Managed Service (AWS MSK / Confluent Cloud)

| Aspect | Assessment |
|---|---|
| HA/Reliability | Built-in multi-AZ, automatic broker replacement |
| Operations | Zero broker management, automated patching |
| Cost | ~$500-1500/month for pilot-scale (3 brokers) |
| Scaling | Automatic broker scaling, partition rebalancing |
| Compliance | SOC 2, HIPAA-eligible (MSK), encryption at rest/transit |
| Monitoring | CloudWatch/Confluent metrics built-in |

**Pros**: No operational burden, guaranteed SLA, compliance certifications.
**Cons**: Higher cost, vendor lock-in risk, less control over tuning.

### Option B: Self-Hosted Multi-Broker (3-broker cluster)

| Aspect | Assessment |
|---|---|
| HA/Reliability | Manual multi-AZ setup, manual broker recovery |
| Operations | Broker management, ZooKeeper/KRaft, patching, monitoring |
| Cost | ~$200-400/month infrastructure + ops time |
| Scaling | Manual partition rebalancing |
| Compliance | Must self-certify encryption, access controls |
| Monitoring | Must deploy Kafka metrics + alerting |

**Pros**: Lower infrastructure cost, full control, no vendor dependency.
**Cons**: Significant ops overhead, requires Kafka expertise, risk of misconfiguration.

### Option C: Redis Streams (Replace Kafka)

| Aspect | Assessment |
|---|---|
| HA/Reliability | Redis Sentinel or Cluster mode |
| Operations | Already running Redis for cache/queue |
| Cost | No additional infrastructure |
| Scaling | Limited partition semantics |
| Compliance | Already in stack |
| Monitoring | Already monitored |

**Pros**: Simplifies stack, no new infrastructure.
**Cons**: Limited ordering guarantees, no native consumer groups at Kafka scale, not designed for durable event streaming.

## Recommendation

**Phase 1 (Pilot)**: Option C — Redis Streams for async job messaging. The pilot workload (<100 messages/min) does not justify Kafka operational complexity. The existing Redis infrastructure with queue separation (P2-015 complete) handles this volume.

**Phase 2 (Scale)**: Migrate to Option A — Managed Kafka when:
- Message volume exceeds 1000/min sustained
- Multi-site replication required
- Event replay/audit requirements demand durable log
- Second site onboarded requiring cross-region messaging

## Migration Path

```
Phase 1: Redis Streams (current)
  ↓ Trigger: >1000 msg/min or multi-site
Phase 2: AWS MSK (managed Kafka)
  ↓ Trigger: Multi-region or >10K msg/min
Phase 3: Confluent Cloud (if multi-cloud)
```

## Approval

| Role | Name | Date |
|---|---|---|
| CTO | | |
| Operations Lead | | |
