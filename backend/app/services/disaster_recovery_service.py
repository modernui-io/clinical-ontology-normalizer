"""Disaster Recovery Runbooks & RTO/RPO Management service (VPE-7).

Manages disaster recovery runbooks, test tracking, compliance metrics,
and communication plans for clinical trial patient recruitment platform.

Usage:
    from app.services.disaster_recovery_service import get_disaster_recovery_service

    service = get_disaster_recovery_service()
    runbooks = service.list_runbooks()
    metrics = service.get_metrics()
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from threading import Lock
from uuid import uuid4

from app.schemas.disaster_recovery import (
    CommunicationPlanResponse,
    DisasterCategory,
    DisasterRecoveryRunbook,
    DRMetrics,
    DRTestResult,
    RecordTestRequest,
    RecoveryTier,
    RunbookCreateRequest,
    RunbookStatus,
    RunbookStep,
    RunbookUpdateRequest,
    RunbookValidation,
    TestHistoryResponse,
    TestResult,
)

logger = logging.getLogger(__name__)

# Singleton instance and lock
_dr_instance: DisasterRecoveryService | None = None
_dr_lock = Lock()


# ---------------------------------------------------------------------------
# Overdue thresholds (days since last test)
# ---------------------------------------------------------------------------

OVERDUE_THRESHOLDS: dict[RecoveryTier, int] = {
    RecoveryTier.TIER_1_CRITICAL: 90,
    RecoveryTier.TIER_2_HIGH: 180,
    RecoveryTier.TIER_3_MEDIUM: 365,
    RecoveryTier.TIER_4_LOW: 365,
}


class DisasterRecoveryService:
    """Manages DR runbooks, test records, and compliance metrics."""

    def __init__(self) -> None:
        self._runbooks: dict[str, DisasterRecoveryRunbook] = {}
        self._test_results: dict[str, list[DRTestResult]] = {}  # runbook_id -> tests
        self._populate_seed_data()

    # -----------------------------------------------------------------------
    # Seed data
    # -----------------------------------------------------------------------

    def _populate_seed_data(self) -> None:
        """Pre-populate runbooks and test results."""
        now = datetime.now(timezone.utc)

        seed_runbooks: list[DisasterRecoveryRunbook] = [
            # 1. PostgreSQL failover
            DisasterRecoveryRunbook(
                id="DR-001",
                title="PostgreSQL Primary Failover",
                category=DisasterCategory.DATABASE_FAILURE,
                tier=RecoveryTier.TIER_1_CRITICAL,
                status=RunbookStatus.TESTED,
                rto_minutes=30,
                rpo_minutes=5,
                steps=[
                    RunbookStep(
                        step_number=1,
                        title="Detect failure",
                        description="Confirm primary database is unreachable via health checks and PgBouncer status",
                        responsible_role="SRE On-Call",
                        estimated_minutes=2,
                        commands=["pg_isready -h primary-db -p 5432", "pgbouncer show databases"],
                        verification_criteria="Health check returns connection refused or timeout",
                        rollback_instructions="N/A - detection only",
                    ),
                    RunbookStep(
                        step_number=2,
                        title="Notify incident commander",
                        description="Page the incident commander and open an incident channel",
                        responsible_role="SRE On-Call",
                        estimated_minutes=2,
                        verification_criteria="Incident channel created and IC acknowledged",
                        rollback_instructions="N/A",
                    ),
                    RunbookStep(
                        step_number=3,
                        title="Verify replication lag",
                        description="Check WAL replay lag on standby to confirm RPO compliance",
                        responsible_role="DBA",
                        estimated_minutes=3,
                        commands=["SELECT pg_last_wal_replay_lsn(), pg_last_wal_receive_lsn()"],
                        verification_criteria="Replication lag < 5 minutes",
                        rollback_instructions="If lag exceeds RPO, escalate to CTO",
                    ),
                    RunbookStep(
                        step_number=4,
                        title="Promote standby",
                        description="Promote the standby PostgreSQL instance to primary",
                        responsible_role="DBA",
                        estimated_minutes=5,
                        commands=["pg_ctl promote -D /var/lib/postgresql/data"],
                        verification_criteria="Standby accepts write connections",
                        rollback_instructions="If promotion fails, attempt manual timeline switch",
                    ),
                    RunbookStep(
                        step_number=5,
                        title="Update connection strings",
                        description="Point PgBouncer and application configs to new primary",
                        responsible_role="SRE On-Call",
                        estimated_minutes=3,
                        commands=["kubectl set env deployment/app DATABASE_URL=..."],
                        verification_criteria="Application connects to new primary without errors",
                        rollback_instructions="Revert environment variable to old primary",
                    ),
                    RunbookStep(
                        step_number=6,
                        title="Validate application health",
                        description="Run smoke tests against the application to verify read/write operations",
                        responsible_role="SRE On-Call",
                        estimated_minutes=5,
                        commands=["curl -f http://localhost:8000/health", "python -m pytest tests/smoke/"],
                        verification_criteria="All smoke tests pass; health endpoint returns 200",
                        rollback_instructions="If smoke tests fail, rollback connection strings and investigate",
                    ),
                    RunbookStep(
                        step_number=7,
                        title="Rebuild standby",
                        description="Set up a new standby from the promoted primary using pg_basebackup",
                        responsible_role="DBA",
                        estimated_minutes=30,
                        commands=["pg_basebackup -h new-primary -D /var/lib/postgresql/data -R"],
                        verification_criteria="New standby streaming replication established",
                        rollback_instructions="Retry pg_basebackup with different parameters",
                    ),
                    RunbookStep(
                        step_number=8,
                        title="Post-incident review",
                        description="Document timeline, root cause, and corrective actions",
                        responsible_role="Incident Commander",
                        estimated_minutes=60,
                        verification_criteria="Post-mortem document published within 48 hours",
                        rollback_instructions="N/A",
                    ),
                ],
                prerequisites=[
                    "Standby PostgreSQL instance running with streaming replication",
                    "PgBouncer configured for connection pooling",
                    "Monitoring alerts configured for replication lag",
                    "DBA on-call rotation established",
                ],
                communication_plan=[
                    "Page incident commander via PagerDuty",
                    "Create #incident-db-failover Slack channel",
                    "Notify clinical operations team within 15 minutes",
                    "Send status update to stakeholders every 30 minutes",
                    "Post resolution summary within 2 hours of recovery",
                ],
                escalation_contacts=[
                    {"name": "DB Team Lead", "role": "DBA Lead", "phone": "+1-555-0101", "email": "dba-lead@example.com"},
                    {"name": "VP Engineering", "role": "Escalation", "phone": "+1-555-0102", "email": "vpe@example.com"},
                    {"name": "CTO", "role": "Executive", "phone": "+1-555-0103", "email": "cto@example.com"},
                ],
                last_tested=now - timedelta(days=45),
                test_result=TestResult.PASS,
                next_test_due=now + timedelta(days=45),
                created_at=now - timedelta(days=180),
                updated_at=now - timedelta(days=45),
                approved_by="VP Engineering",
                version=3,
            ),
            # 2. Redis cluster recovery
            DisasterRecoveryRunbook(
                id="DR-002",
                title="Redis Cluster Recovery",
                category=DisasterCategory.DATABASE_FAILURE,
                tier=RecoveryTier.TIER_2_HIGH,
                status=RunbookStatus.APPROVED,
                rto_minutes=60,
                rpo_minutes=15,
                steps=[
                    RunbookStep(
                        step_number=1,
                        title="Detect Redis failure",
                        description="Identify failed Redis nodes through Sentinel monitoring",
                        responsible_role="SRE On-Call",
                        estimated_minutes=3,
                        commands=["redis-cli -h sentinel ping", "redis-cli cluster info"],
                        verification_criteria="Sentinel reports node as down",
                        rollback_instructions="N/A - detection only",
                    ),
                    RunbookStep(
                        step_number=2,
                        title="Trigger Sentinel failover",
                        description="Initiate automatic or manual failover via Redis Sentinel",
                        responsible_role="SRE On-Call",
                        estimated_minutes=5,
                        commands=["redis-cli -h sentinel SENTINEL failover mymaster"],
                        verification_criteria="New master elected and accepting writes",
                        rollback_instructions="Manual slot migration if automatic failover fails",
                    ),
                    RunbookStep(
                        step_number=3,
                        title="Verify application connectivity",
                        description="Ensure all application instances reconnect to new master",
                        responsible_role="SRE On-Call",
                        estimated_minutes=5,
                        verification_criteria="Application logs show successful Redis connections",
                        rollback_instructions="Restart application pods if connection pool is stale",
                    ),
                    RunbookStep(
                        step_number=4,
                        title="Rebuild failed node",
                        description="Replace failed Redis node and rejoin cluster",
                        responsible_role="SRE On-Call",
                        estimated_minutes=15,
                        commands=["redis-cli cluster replicate <new-master-id>"],
                        verification_criteria="Node shows as replica in cluster info",
                        rollback_instructions="Provision new VM and start fresh Redis instance",
                    ),
                    RunbookStep(
                        step_number=5,
                        title="Verify cache warming",
                        description="Check that critical cache keys are being repopulated",
                        responsible_role="SRE On-Call",
                        estimated_minutes=10,
                        verification_criteria="Cache hit rate returns to baseline within 30 minutes",
                        rollback_instructions="Trigger manual cache warm-up job",
                    ),
                    RunbookStep(
                        step_number=6,
                        title="Close incident",
                        description="Document findings and close incident ticket",
                        responsible_role="Incident Commander",
                        estimated_minutes=30,
                        verification_criteria="Incident ticket closed with root cause and corrective actions",
                        rollback_instructions="N/A",
                    ),
                ],
                prerequisites=[
                    "Redis Sentinel configured with 3+ sentinels",
                    "Application uses Sentinel-aware Redis client",
                    "Cache warming scripts available",
                ],
                communication_plan=[
                    "Alert SRE team via PagerDuty",
                    "Notify application team of potential cache miss increase",
                    "Update status page if user-facing impact detected",
                ],
                escalation_contacts=[
                    {"name": "Platform Lead", "role": "SRE Lead", "phone": "+1-555-0201", "email": "sre-lead@example.com"},
                    {"name": "VP Engineering", "role": "Escalation", "phone": "+1-555-0102", "email": "vpe@example.com"},
                ],
                last_tested=now - timedelta(days=120),
                test_result=TestResult.PASS,
                next_test_due=now + timedelta(days=60),
                created_at=now - timedelta(days=150),
                updated_at=now - timedelta(days=120),
                approved_by="SRE Lead",
                version=2,
            ),
            # 3. Application deployment rollback
            DisasterRecoveryRunbook(
                id="DR-003",
                title="Application Deployment Rollback",
                category=DisasterCategory.APPLICATION_OUTAGE,
                tier=RecoveryTier.TIER_1_CRITICAL,
                status=RunbookStatus.TESTED,
                rto_minutes=15,
                rpo_minutes=0,
                steps=[
                    RunbookStep(
                        step_number=1,
                        title="Identify bad deployment",
                        description="Correlate error spike with recent deployment via deploy log",
                        responsible_role="SRE On-Call",
                        estimated_minutes=3,
                        commands=["kubectl rollout history deployment/app"],
                        verification_criteria="Error rate spike correlates with deployment timestamp",
                        rollback_instructions="N/A - investigation only",
                    ),
                    RunbookStep(
                        step_number=2,
                        title="Initiate rollback",
                        description="Roll back Kubernetes deployment to previous revision",
                        responsible_role="SRE On-Call",
                        estimated_minutes=2,
                        commands=["kubectl rollout undo deployment/app"],
                        verification_criteria="Previous revision pods are running and healthy",
                        rollback_instructions="If undo fails, manually set image to known-good tag",
                    ),
                    RunbookStep(
                        step_number=3,
                        title="Verify rollback health",
                        description="Confirm error rates return to baseline and health checks pass",
                        responsible_role="SRE On-Call",
                        estimated_minutes=5,
                        commands=["curl -f http://localhost:8000/health"],
                        verification_criteria="Error rate below threshold; health returns 200",
                        rollback_instructions="If errors persist, check if database migration is incompatible",
                    ),
                    RunbookStep(
                        step_number=4,
                        title="Notify release team",
                        description="Inform release engineering of the rollback and block pipeline",
                        responsible_role="SRE On-Call",
                        estimated_minutes=3,
                        verification_criteria="Release pipeline paused; team acknowledged",
                        rollback_instructions="N/A",
                    ),
                    RunbookStep(
                        step_number=5,
                        title="Root cause analysis",
                        description="Investigate the failed deployment and document findings",
                        responsible_role="Release Engineer",
                        estimated_minutes=60,
                        verification_criteria="Root cause identified and fix PR opened",
                        rollback_instructions="N/A",
                    ),
                ],
                prerequisites=[
                    "Kubernetes deployment with revision history enabled",
                    "Monitoring dashboards with error rate alerts",
                    "CI/CD pipeline with deployment tracking",
                ],
                communication_plan=[
                    "Notify release channel of rollback",
                    "Update deployment status in release tracker",
                    "Brief engineering leadership if customer-facing impact",
                ],
                escalation_contacts=[
                    {"name": "Release Lead", "role": "Release Engineering", "phone": "+1-555-0301", "email": "release@example.com"},
                    {"name": "VP Engineering", "role": "Escalation", "phone": "+1-555-0102", "email": "vpe@example.com"},
                ],
                last_tested=now - timedelta(days=30),
                test_result=TestResult.PASS,
                next_test_due=now + timedelta(days=60),
                created_at=now - timedelta(days=200),
                updated_at=now - timedelta(days=30),
                approved_by="VP Engineering",
                version=4,
            ),
            # 4. Cloud region failover
            DisasterRecoveryRunbook(
                id="DR-004",
                title="Cloud Region Failover",
                category=DisasterCategory.CLOUD_REGION_FAILURE,
                tier=RecoveryTier.TIER_2_HIGH,
                status=RunbookStatus.APPROVED,
                rto_minutes=120,
                rpo_minutes=30,
                steps=[
                    RunbookStep(step_number=1, title="Confirm regional outage", description="Verify cloud provider status page and cross-region health checks", responsible_role="SRE On-Call", estimated_minutes=5, verification_criteria="Cloud provider confirms regional degradation", rollback_instructions="N/A"),
                    RunbookStep(step_number=2, title="Activate DR region", description="Enable compute and networking resources in DR region", responsible_role="SRE On-Call", estimated_minutes=10, commands=["terraform apply -var region=us-west-2"], verification_criteria="DR region infrastructure healthy", rollback_instructions="terraform destroy DR region resources"),
                    RunbookStep(step_number=3, title="Promote DR database", description="Promote cross-region read replica to primary", responsible_role="DBA", estimated_minutes=15, verification_criteria="DR database accepts writes", rollback_instructions="Revert to original primary when region recovers"),
                    RunbookStep(step_number=4, title="Update DNS", description="Switch DNS records to point to DR region load balancer", responsible_role="SRE On-Call", estimated_minutes=5, commands=["aws route53 change-resource-record-sets ..."], verification_criteria="DNS resolves to DR region IPs", rollback_instructions="Revert DNS records"),
                    RunbookStep(step_number=5, title="Deploy application", description="Deploy latest application version to DR region Kubernetes cluster", responsible_role="Release Engineer", estimated_minutes=15, commands=["kubectl --context dr-cluster apply -f k8s/"], verification_criteria="All pods running and passing health checks", rollback_instructions="Scale down DR deployments"),
                    RunbookStep(step_number=6, title="Verify data integrity", description="Run data consistency checks between DR and backup", responsible_role="DBA", estimated_minutes=15, verification_criteria="Consistency checks pass with < 0.01% discrepancy", rollback_instructions="Restore from backup if integrity issues found"),
                    RunbookStep(step_number=7, title="Redirect traffic", description="Update load balancer to serve traffic from DR region", responsible_role="SRE On-Call", estimated_minutes=5, verification_criteria="Users can access application from DR region", rollback_instructions="Revert load balancer configuration"),
                    RunbookStep(step_number=8, title="Smoke test", description="Run end-to-end smoke tests against DR deployment", responsible_role="QA", estimated_minutes=15, verification_criteria="All critical user flows pass", rollback_instructions="Escalate to engineering if smoke tests fail"),
                    RunbookStep(step_number=9, title="Notify stakeholders", description="Send status update to clinical operations and sponsors", responsible_role="Incident Commander", estimated_minutes=5, verification_criteria="Stakeholders acknowledged communication", rollback_instructions="N/A"),
                    RunbookStep(step_number=10, title="Plan failback", description="Document failback procedure for when primary region recovers", responsible_role="SRE Lead", estimated_minutes=30, verification_criteria="Failback plan documented and reviewed", rollback_instructions="N/A"),
                ],
                prerequisites=[
                    "Cross-region database replication configured",
                    "DR region infrastructure provisioned (cold standby)",
                    "DNS TTL set to 60 seconds for quick failover",
                    "Terraform state for DR region maintained",
                ],
                communication_plan=[
                    "Activate major incident bridge call",
                    "Notify clinical operations within 10 minutes",
                    "Update external status page",
                    "Brief C-suite on impact and ETA",
                    "Send hourly updates until resolved",
                ],
                escalation_contacts=[
                    {"name": "SRE Lead", "role": "SRE", "phone": "+1-555-0401", "email": "sre-lead@example.com"},
                    {"name": "CTO", "role": "Executive", "phone": "+1-555-0103", "email": "cto@example.com"},
                    {"name": "VP Clinical Ops", "role": "Business", "phone": "+1-555-0402", "email": "vp-clinical@example.com"},
                ],
                last_tested=now - timedelta(days=200),
                test_result=TestResult.PARTIAL,
                next_test_due=now - timedelta(days=20),
                created_at=now - timedelta(days=365),
                updated_at=now - timedelta(days=200),
                approved_by="CTO",
                version=2,
            ),
            # 5. Ransomware response
            DisasterRecoveryRunbook(
                id="DR-005",
                title="Ransomware Incident Response",
                category=DisasterCategory.RANSOMWARE,
                tier=RecoveryTier.TIER_1_CRITICAL,
                status=RunbookStatus.APPROVED,
                rto_minutes=60,
                rpo_minutes=60,
                steps=[
                    RunbookStep(step_number=1, title="Isolate affected systems", description="Immediately disconnect affected systems from the network", responsible_role="Security Team", estimated_minutes=5, commands=["iptables -A INPUT -j DROP", "iptables -A OUTPUT -j DROP"], verification_criteria="Affected systems have no network connectivity", rollback_instructions="Remove firewall rules after remediation"),
                    RunbookStep(step_number=2, title="Preserve evidence", description="Take forensic snapshots of affected systems before any remediation", responsible_role="Security Team", estimated_minutes=10, verification_criteria="Disk images captured and stored securely", rollback_instructions="N/A"),
                    RunbookStep(step_number=3, title="Assess blast radius", description="Determine which systems, data, and users are affected", responsible_role="Security Lead", estimated_minutes=15, verification_criteria="Complete inventory of affected assets documented", rollback_instructions="N/A"),
                    RunbookStep(step_number=4, title="Notify legal and compliance", description="Engage legal team, compliance, and law enforcement if required", responsible_role="CISO", estimated_minutes=5, verification_criteria="Legal and compliance teams engaged", rollback_instructions="N/A"),
                    RunbookStep(step_number=5, title="Activate backup restoration", description="Begin restoring from clean, verified backups", responsible_role="DBA", estimated_minutes=30, verification_criteria="Backup integrity verified and restoration started", rollback_instructions="Try alternative backup if primary backup is corrupted"),
                    RunbookStep(step_number=6, title="Rotate all credentials", description="Reset all passwords, API keys, tokens, and certificates", responsible_role="Security Team", estimated_minutes=15, verification_criteria="All credentials rotated and old ones revoked", rollback_instructions="N/A - forward only"),
                    RunbookStep(step_number=7, title="Patch vulnerability", description="Identify and patch the initial attack vector", responsible_role="Security Team", estimated_minutes=30, verification_criteria="Vulnerability patched and verified", rollback_instructions="Apply compensating control if patch unavailable"),
                    RunbookStep(step_number=8, title="Restore services", description="Bring services back online in priority order", responsible_role="SRE On-Call", estimated_minutes=30, verification_criteria="Critical services operational and healthy", rollback_instructions="Re-isolate if reinfection detected"),
                    RunbookStep(step_number=9, title="Verify data integrity", description="Run integrity checks on restored data", responsible_role="DBA", estimated_minutes=30, verification_criteria="Data integrity checks pass", rollback_instructions="Restore from earlier backup point"),
                    RunbookStep(step_number=10, title="Enhanced monitoring", description="Deploy enhanced monitoring and threat hunting rules", responsible_role="Security Team", estimated_minutes=15, verification_criteria="Enhanced monitoring active with alerts configured", rollback_instructions="N/A"),
                    RunbookStep(step_number=11, title="Regulatory notification", description="File required notifications (HIPAA breach, state regulations)", responsible_role="Compliance Officer", estimated_minutes=30, verification_criteria="All required notifications filed within regulatory timelines", rollback_instructions="N/A"),
                    RunbookStep(step_number=12, title="Post-incident review", description="Conduct thorough post-mortem and update security controls", responsible_role="CISO", estimated_minutes=120, verification_criteria="Post-mortem document published; action items assigned", rollback_instructions="N/A"),
                ],
                prerequisites=[
                    "Incident response plan documented and distributed",
                    "Backup verification run weekly with integrity checks",
                    "Forensics toolkit available and team trained",
                    "Legal counsel and cyber insurance contacts on file",
                    "Law enforcement contacts established",
                ],
                communication_plan=[
                    "Activate security incident bridge immediately",
                    "Notify CISO and CTO within 5 minutes",
                    "Engage legal counsel within 15 minutes",
                    "Notify affected users per HIPAA breach notification rules",
                    "File HHS breach notification within 60 days",
                    "Coordinate with law enforcement as advised by legal",
                ],
                escalation_contacts=[
                    {"name": "CISO", "role": "Security", "phone": "+1-555-0501", "email": "ciso@example.com"},
                    {"name": "CTO", "role": "Executive", "phone": "+1-555-0103", "email": "cto@example.com"},
                    {"name": "Legal Counsel", "role": "Legal", "phone": "+1-555-0502", "email": "legal@example.com"},
                    {"name": "Cyber Insurance", "role": "Insurance", "phone": "+1-555-0503", "email": "insurance@example.com"},
                ],
                last_tested=None,
                test_result=None,
                next_test_due=now - timedelta(days=30),
                created_at=now - timedelta(days=120),
                updated_at=now - timedelta(days=90),
                approved_by="CISO",
                version=1,
            ),
            # 6. Data corruption recovery
            DisasterRecoveryRunbook(
                id="DR-006",
                title="Data Corruption Recovery",
                category=DisasterCategory.DATA_CORRUPTION,
                tier=RecoveryTier.TIER_2_HIGH,
                status=RunbookStatus.TESTED,
                rto_minutes=180,
                rpo_minutes=60,
                steps=[
                    RunbookStep(step_number=1, title="Identify corruption scope", description="Determine which tables and records are affected using checksums", responsible_role="DBA", estimated_minutes=15, verification_criteria="Corrupted tables and row ranges identified", rollback_instructions="N/A"),
                    RunbookStep(step_number=2, title="Stop writes to affected tables", description="Put affected tables in read-only mode to prevent further corruption", responsible_role="DBA", estimated_minutes=5, commands=["ALTER TABLE ... SET (autovacuum_enabled = false)"], verification_criteria="No writes reaching affected tables", rollback_instructions="Re-enable writes"),
                    RunbookStep(step_number=3, title="Assess backup availability", description="Identify most recent clean backup before corruption occurred", responsible_role="DBA", estimated_minutes=10, verification_criteria="Clean backup identified with timestamp before corruption", rollback_instructions="Check off-site backups if primary backup unavailable"),
                    RunbookStep(step_number=4, title="Set up parallel restore environment", description="Restore clean backup to a temporary database for comparison", responsible_role="DBA", estimated_minutes=30, verification_criteria="Temporary database with clean data available", rollback_instructions="Clean up temporary database"),
                    RunbookStep(step_number=5, title="Generate repair queries", description="Create SQL scripts to repair corrupted data from clean backup", responsible_role="DBA", estimated_minutes=30, verification_criteria="Repair scripts generated and reviewed by second DBA", rollback_instructions="Revert repair scripts"),
                    RunbookStep(step_number=6, title="Apply repairs", description="Execute repair scripts with transaction wrapping", responsible_role="DBA", estimated_minutes=15, verification_criteria="Repair queries complete without errors", rollback_instructions="ROLLBACK transaction"),
                    RunbookStep(step_number=7, title="Verify data integrity", description="Run full integrity checks and compare row counts", responsible_role="DBA", estimated_minutes=20, verification_criteria="All integrity checks pass; row counts match expected values", rollback_instructions="Repeat repair from earlier backup"),
                    RunbookStep(step_number=8, title="Resume normal operations", description="Re-enable writes and restore normal processing", responsible_role="DBA", estimated_minutes=5, verification_criteria="Application functioning normally with no errors", rollback_instructions="Re-disable writes and investigate"),
                    RunbookStep(step_number=9, title="Root cause analysis", description="Investigate what caused the corruption and implement preventive measures", responsible_role="DBA Lead", estimated_minutes=120, verification_criteria="Root cause identified and preventive measures implemented", rollback_instructions="N/A"),
                ],
                prerequisites=[
                    "Automated backup system with point-in-time recovery",
                    "Data integrity monitoring with checksum verification",
                    "Staging environment available for parallel restore",
                ],
                communication_plan=[
                    "Notify DBA team immediately",
                    "Inform clinical operations of potential data impact",
                    "Update stakeholders on recovery progress hourly",
                ],
                escalation_contacts=[
                    {"name": "DBA Lead", "role": "DBA", "phone": "+1-555-0601", "email": "dba-lead@example.com"},
                    {"name": "VP Engineering", "role": "Escalation", "phone": "+1-555-0102", "email": "vpe@example.com"},
                ],
                last_tested=now - timedelta(days=90),
                test_result=TestResult.PASS,
                next_test_due=now + timedelta(days=90),
                created_at=now - timedelta(days=250),
                updated_at=now - timedelta(days=90),
                approved_by="DBA Lead",
                version=2,
            ),
            # 7. DNS failure recovery
            DisasterRecoveryRunbook(
                id="DR-007",
                title="DNS Failure Recovery",
                category=DisasterCategory.DNS_FAILURE,
                tier=RecoveryTier.TIER_3_MEDIUM,
                status=RunbookStatus.APPROVED,
                rto_minutes=30,
                rpo_minutes=0,
                steps=[
                    RunbookStep(step_number=1, title="Confirm DNS failure", description="Verify DNS resolution failures are not client-side", responsible_role="SRE On-Call", estimated_minutes=5, commands=["dig @8.8.8.8 app.example.com", "nslookup app.example.com"], verification_criteria="DNS queries to multiple resolvers fail", rollback_instructions="N/A"),
                    RunbookStep(step_number=2, title="Switch to backup DNS provider", description="Update NS records or activate secondary DNS provider", responsible_role="SRE On-Call", estimated_minutes=10, commands=["aws route53 update-hosted-zone ..."], verification_criteria="DNS resolution working through backup provider", rollback_instructions="Revert NS record changes"),
                    RunbookStep(step_number=3, title="Flush DNS caches", description="Clear CDN and proxy DNS caches to pick up changes faster", responsible_role="SRE On-Call", estimated_minutes=5, commands=["cloudflare purge cache", "kubectl rollout restart deployment/nginx"], verification_criteria="New DNS records propagating globally", rollback_instructions="N/A"),
                    RunbookStep(step_number=4, title="Monitor propagation", description="Monitor DNS propagation across global resolvers", responsible_role="SRE On-Call", estimated_minutes=30, verification_criteria="DNS resolves correctly from all major regions", rollback_instructions="Investigate regional propagation issues"),
                ],
                prerequisites=[
                    "Secondary DNS provider configured",
                    "DNS TTL configured low enough for quick failover (60s)",
                    "DNS monitoring with alerting",
                ],
                communication_plan=[
                    "Notify SRE team",
                    "Update status page with DNS issue notification",
                    "Advise users to flush local DNS cache if needed",
                ],
                escalation_contacts=[
                    {"name": "SRE Lead", "role": "SRE", "phone": "+1-555-0701", "email": "sre-lead@example.com"},
                ],
                last_tested=now - timedelta(days=400),
                test_result=TestResult.PASS,
                next_test_due=now - timedelta(days=35),
                created_at=now - timedelta(days=400),
                updated_at=now - timedelta(days=400),
                approved_by="SRE Lead",
                version=1,
            ),
            # 8. Certificate rotation emergency
            DisasterRecoveryRunbook(
                id="DR-008",
                title="Emergency Certificate Rotation",
                category=DisasterCategory.CERTIFICATE_EXPIRY,
                tier=RecoveryTier.TIER_3_MEDIUM,
                status=RunbookStatus.REVIEWED,
                rto_minutes=60,
                rpo_minutes=0,
                steps=[
                    RunbookStep(step_number=1, title="Identify expiring/expired certificates", description="List all certificates and identify the affected ones", responsible_role="Security Team", estimated_minutes=5, commands=["openssl x509 -enddate -noout -in /etc/ssl/cert.pem"], verification_criteria="Affected certificates identified with expiry dates", rollback_instructions="N/A"),
                    RunbookStep(step_number=2, title="Generate new certificates", description="Request new certificates from CA or generate via ACME", responsible_role="Security Team", estimated_minutes=10, commands=["certbot certonly --dns-route53 -d app.example.com"], verification_criteria="New certificates issued and validated", rollback_instructions="Use backup certificate if ACME fails"),
                    RunbookStep(step_number=3, title="Deploy certificates", description="Deploy new certificates to load balancers and application servers", responsible_role="SRE On-Call", estimated_minutes=10, commands=["kubectl create secret tls app-cert --cert=cert.pem --key=key.pem"], verification_criteria="New certificates deployed and services restarted", rollback_instructions="Rollback to previous certificate secret"),
                    RunbookStep(step_number=4, title="Verify TLS connectivity", description="Test HTTPS connectivity from multiple locations", responsible_role="SRE On-Call", estimated_minutes=5, commands=["openssl s_client -connect app.example.com:443"], verification_criteria="TLS handshake succeeds with new certificate", rollback_instructions="Check certificate chain and intermediate certs"),
                    RunbookStep(step_number=5, title="Update certificate monitoring", description="Update monitoring to track new certificate expiry dates", responsible_role="SRE On-Call", estimated_minutes=5, verification_criteria="New certificate expiry tracked in monitoring system", rollback_instructions="N/A"),
                    RunbookStep(step_number=6, title="Update renewal automation", description="Ensure automated renewal is configured for new certificates", responsible_role="Security Team", estimated_minutes=15, verification_criteria="Auto-renewal cron/timer configured and tested", rollback_instructions="Manual renewal scheduled as fallback"),
                ],
                prerequisites=[
                    "Certificate authority account configured",
                    "ACME client (certbot) installed",
                    "DNS validation capability for wildcard certs",
                ],
                communication_plan=[
                    "Notify security team of certificate emergency",
                    "Inform users if TLS errors are expected during rotation",
                ],
                escalation_contacts=[
                    {"name": "Security Lead", "role": "Security", "phone": "+1-555-0801", "email": "security@example.com"},
                    {"name": "SRE Lead", "role": "SRE", "phone": "+1-555-0701", "email": "sre-lead@example.com"},
                ],
                last_tested=None,
                test_result=None,
                next_test_due=now + timedelta(days=180),
                created_at=now - timedelta(days=100),
                updated_at=now - timedelta(days=80),
                approved_by=None,
                version=1,
            ),
            # 9. Third-party API outage
            DisasterRecoveryRunbook(
                id="DR-009",
                title="Third-Party API Outage Response",
                category=DisasterCategory.THIRD_PARTY_OUTAGE,
                tier=RecoveryTier.TIER_3_MEDIUM,
                status=RunbookStatus.APPROVED,
                rto_minutes=240,
                rpo_minutes=0,
                steps=[
                    RunbookStep(step_number=1, title="Confirm third-party outage", description="Verify outage via provider status page and independent testing", responsible_role="SRE On-Call", estimated_minutes=5, verification_criteria="Provider status page confirms issue or independent tests fail", rollback_instructions="N/A"),
                    RunbookStep(step_number=2, title="Activate circuit breaker", description="Enable circuit breaker to prevent cascading failures", responsible_role="SRE On-Call", estimated_minutes=5, commands=["kubectl set env deployment/app CIRCUIT_BREAKER_ENABLED=true"], verification_criteria="Circuit breaker active; graceful degradation in effect", rollback_instructions="Disable circuit breaker when provider recovers"),
                    RunbookStep(step_number=3, title="Enable fallback mode", description="Switch to cached data or alternative provider if available", responsible_role="SRE On-Call", estimated_minutes=10, verification_criteria="Fallback mode active; users see degraded but functional experience", rollback_instructions="Disable fallback mode"),
                    RunbookStep(step_number=4, title="Monitor provider recovery", description="Set up alerts for provider recovery and test periodically", responsible_role="SRE On-Call", estimated_minutes=60, verification_criteria="Provider recovery detected; services back to normal", rollback_instructions="Continue monitoring"),
                    RunbookStep(step_number=5, title="Restore full functionality", description="Disable fallback mode and verify full integration", responsible_role="SRE On-Call", estimated_minutes=15, verification_criteria="Full functionality restored; all API calls succeeding", rollback_instructions="Re-enable fallback if integration issues persist"),
                ],
                prerequisites=[
                    "Circuit breaker pattern implemented for external APIs",
                    "Fallback/cache mode available for critical integrations",
                    "Provider status page monitoring configured",
                ],
                communication_plan=[
                    "Notify clinical ops of degraded functionality",
                    "Update internal status page",
                    "Contact provider support for ETA",
                ],
                escalation_contacts=[
                    {"name": "Integration Lead", "role": "Engineering", "phone": "+1-555-0901", "email": "integration@example.com"},
                ],
                last_tested=now - timedelta(days=60),
                test_result=TestResult.PASS,
                next_test_due=now + timedelta(days=305),
                created_at=now - timedelta(days=180),
                updated_at=now - timedelta(days=60),
                approved_by="VP Engineering",
                version=1,
            ),
            # 10. Key compromise response
            DisasterRecoveryRunbook(
                id="DR-010",
                title="Cryptographic Key Compromise Response",
                category=DisasterCategory.KEY_COMPROMISE,
                tier=RecoveryTier.TIER_1_CRITICAL,
                status=RunbookStatus.APPROVED,
                rto_minutes=45,
                rpo_minutes=0,
                steps=[
                    RunbookStep(step_number=1, title="Confirm key compromise", description="Verify that the key has been compromised through security analysis", responsible_role="Security Team", estimated_minutes=5, verification_criteria="Compromise confirmed via audit logs or threat intelligence", rollback_instructions="N/A"),
                    RunbookStep(step_number=2, title="Revoke compromised key", description="Immediately revoke the compromised key from all systems", responsible_role="Security Team", estimated_minutes=5, commands=["aws kms disable-key --key-id <KEY_ID>"], verification_criteria="Key disabled and no longer usable", rollback_instructions="Re-enable only after investigation confirms false alarm"),
                    RunbookStep(step_number=3, title="Generate replacement key", description="Generate new cryptographic key material", responsible_role="Security Team", estimated_minutes=5, commands=["aws kms create-key --description 'Replacement key'"], verification_criteria="New key generated and tested", rollback_instructions="Use backup key if generation fails"),
                    RunbookStep(step_number=4, title="Re-encrypt affected data", description="Re-encrypt all data that was encrypted with the compromised key", responsible_role="Security Team", estimated_minutes=30, verification_criteria="All affected data re-encrypted with new key", rollback_instructions="Re-attempt with different batch size if timeout"),
                    RunbookStep(step_number=5, title="Update key references", description="Update all configuration and environment variables referencing the old key", responsible_role="SRE On-Call", estimated_minutes=10, commands=["kubectl set env deployment/app ENCRYPTION_KEY_ID=<NEW_KEY_ID>"], verification_criteria="All services using new key ID", rollback_instructions="Revert key references if services fail"),
                    RunbookStep(step_number=6, title="Audit access", description="Review all access to the compromised key and identify potential data exposure", responsible_role="Security Lead", estimated_minutes=30, verification_criteria="Complete access audit documented", rollback_instructions="N/A"),
                    RunbookStep(step_number=7, title="Assess regulatory impact", description="Determine if breach notification is required under HIPAA or other regulations", responsible_role="Compliance Officer", estimated_minutes=15, verification_criteria="Regulatory impact assessment complete", rollback_instructions="N/A"),
                    RunbookStep(step_number=8, title="Post-incident hardening", description="Implement additional key management controls to prevent recurrence", responsible_role="Security Lead", estimated_minutes=60, verification_criteria="Enhanced key management controls deployed", rollback_instructions="N/A"),
                ],
                prerequisites=[
                    "Key management system (KMS) in use",
                    "Key rotation procedures documented",
                    "Audit logging enabled for key access",
                    "Data encryption inventory maintained",
                ],
                communication_plan=[
                    "Notify CISO immediately",
                    "Brief legal and compliance within 30 minutes",
                    "Assess breach notification requirements",
                    "Update security incident tracker",
                ],
                escalation_contacts=[
                    {"name": "CISO", "role": "Security", "phone": "+1-555-0501", "email": "ciso@example.com"},
                    {"name": "CTO", "role": "Executive", "phone": "+1-555-0103", "email": "cto@example.com"},
                    {"name": "Compliance Officer", "role": "Compliance", "phone": "+1-555-1001", "email": "compliance@example.com"},
                ],
                last_tested=now - timedelta(days=60),
                test_result=TestResult.PARTIAL,
                next_test_due=now + timedelta(days=30),
                created_at=now - timedelta(days=150),
                updated_at=now - timedelta(days=60),
                approved_by="CISO",
                version=2,
            ),
        ]

        for rb in seed_runbooks:
            self._runbooks[rb.id] = rb
            self._test_results[rb.id] = []

        # Pre-populate test results for runbooks that have been tested
        seed_tests: list[DRTestResult] = [
            DRTestResult(
                id="DRT-001",
                runbook_id="DR-001",
                test_date=now - timedelta(days=45),
                tester="SRE Team Lead",
                actual_rto_minutes=25.0,
                actual_rpo_minutes=3.0,
                rto_met=True,
                rpo_met=True,
                result=TestResult.PASS,
                issues_found=["Standby promotion took 7 minutes instead of expected 5"],
                lessons_learned=["Pre-stage promotion scripts to reduce time"],
                steps_completed=8,
                total_steps=8,
            ),
            DRTestResult(
                id="DRT-002",
                runbook_id="DR-003",
                test_date=now - timedelta(days=30),
                tester="Release Engineer",
                actual_rto_minutes=12.0,
                actual_rpo_minutes=0.0,
                rto_met=True,
                rpo_met=True,
                result=TestResult.PASS,
                issues_found=[],
                lessons_learned=["Rollback is faster with pre-built container images cached"],
                steps_completed=5,
                total_steps=5,
            ),
            DRTestResult(
                id="DRT-003",
                runbook_id="DR-006",
                test_date=now - timedelta(days=90),
                tester="DBA Team",
                actual_rto_minutes=160.0,
                actual_rpo_minutes=45.0,
                rto_met=True,
                rpo_met=True,
                result=TestResult.PASS,
                issues_found=["Parallel restore environment took longer to provision"],
                lessons_learned=["Keep warm standby for restore environment"],
                steps_completed=9,
                total_steps=9,
            ),
            DRTestResult(
                id="DRT-004",
                runbook_id="DR-004",
                test_date=now - timedelta(days=200),
                tester="SRE Team",
                actual_rto_minutes=150.0,
                actual_rpo_minutes=40.0,
                rto_met=False,
                rpo_met=False,
                result=TestResult.PARTIAL,
                issues_found=[
                    "DR region infrastructure provisioning exceeded expected time",
                    "Database promotion had replication lag > RPO",
                ],
                lessons_learned=[
                    "Keep DR region in warm standby instead of cold",
                    "Improve replication monitoring for cross-region setup",
                ],
                steps_completed=8,
                total_steps=10,
            ),
        ]

        for tr in seed_tests:
            self._test_results[tr.runbook_id].append(tr)

        logger.info(
            "Disaster recovery service initialized with %d runbooks and %d test results",
            len(self._runbooks),
            sum(len(v) for v in self._test_results.values()),
        )

    # -----------------------------------------------------------------------
    # CRUD
    # -----------------------------------------------------------------------

    def create_runbook(self, req: RunbookCreateRequest) -> DisasterRecoveryRunbook:
        """Create a new DR runbook."""
        now = datetime.now(timezone.utc)
        runbook_id = f"DR-{uuid4().hex[:8].upper()}"
        runbook = DisasterRecoveryRunbook(
            id=runbook_id,
            title=req.title,
            category=req.category,
            tier=req.tier,
            status=RunbookStatus.DRAFT,
            rto_minutes=req.rto_minutes,
            rpo_minutes=req.rpo_minutes,
            steps=req.steps,
            prerequisites=req.prerequisites,
            communication_plan=req.communication_plan,
            escalation_contacts=req.escalation_contacts,
            created_at=now,
            updated_at=now,
            approved_by=req.approved_by,
            version=1,
        )
        self._runbooks[runbook_id] = runbook
        self._test_results[runbook_id] = []
        logger.info("Created DR runbook %s: %s", runbook_id, req.title)
        return runbook

    def update_runbook(
        self, runbook_id: str, req: RunbookUpdateRequest
    ) -> DisasterRecoveryRunbook | None:
        """Update an existing DR runbook. Returns None if not found."""
        runbook = self._runbooks.get(runbook_id)
        if runbook is None:
            return None

        now = datetime.now(timezone.utc)
        data = runbook.model_dump()

        for field, value in req.model_dump(exclude_none=True).items():
            data[field] = value

        data["updated_at"] = now
        data["version"] = runbook.version + 1

        updated = DisasterRecoveryRunbook(**data)
        self._runbooks[runbook_id] = updated
        logger.info("Updated DR runbook %s (v%d)", runbook_id, updated.version)
        return updated

    def get_runbook(self, runbook_id: str) -> DisasterRecoveryRunbook | None:
        """Get a single runbook by ID."""
        return self._runbooks.get(runbook_id)

    def list_runbooks(
        self,
        category: DisasterCategory | None = None,
        tier: RecoveryTier | None = None,
        status: RunbookStatus | None = None,
    ) -> list[DisasterRecoveryRunbook]:
        """List runbooks with optional filters."""
        result = list(self._runbooks.values())
        if category is not None:
            result = [r for r in result if r.category == category]
        if tier is not None:
            result = [r for r in result if r.tier == tier]
        if status is not None:
            result = [r for r in result if r.status == status]
        return result

    def delete_runbook(self, runbook_id: str) -> bool:
        """Delete a runbook. Returns True if found and deleted."""
        if runbook_id in self._runbooks:
            del self._runbooks[runbook_id]
            self._test_results.pop(runbook_id, None)
            logger.info("Deleted DR runbook %s", runbook_id)
            return True
        return False

    # -----------------------------------------------------------------------
    # Test management
    # -----------------------------------------------------------------------

    def record_test(
        self, runbook_id: str, req: RecordTestRequest
    ) -> DRTestResult | None:
        """Record a DR test execution and update runbook accordingly.

        Returns None if runbook not found.
        """
        runbook = self._runbooks.get(runbook_id)
        if runbook is None:
            return None

        now = datetime.now(timezone.utc)
        test_id = f"DRT-{uuid4().hex[:8].upper()}"

        rto_met = req.actual_rto_minutes <= runbook.rto_minutes
        rpo_met = req.actual_rpo_minutes <= runbook.rpo_minutes

        test_result = DRTestResult(
            id=test_id,
            runbook_id=runbook_id,
            test_date=now,
            tester=req.tester,
            actual_rto_minutes=req.actual_rto_minutes,
            actual_rpo_minutes=req.actual_rpo_minutes,
            rto_met=rto_met,
            rpo_met=rpo_met,
            result=req.result,
            issues_found=req.issues_found,
            lessons_learned=req.lessons_learned,
            steps_completed=req.steps_completed,
            total_steps=req.total_steps,
        )

        self._test_results.setdefault(runbook_id, []).append(test_result)

        # Update runbook with test info
        threshold_days = OVERDUE_THRESHOLDS.get(runbook.tier, 365)
        data = runbook.model_dump()
        data["last_tested"] = now
        data["test_result"] = req.result
        data["next_test_due"] = now + timedelta(days=threshold_days)
        data["updated_at"] = now
        if runbook.status != RunbookStatus.OUTDATED:
            data["status"] = RunbookStatus.TESTED
        self._runbooks[runbook_id] = DisasterRecoveryRunbook(**data)

        logger.info(
            "Recorded DR test %s for runbook %s: result=%s rto_met=%s rpo_met=%s",
            test_id,
            runbook_id,
            req.result.value,
            rto_met,
            rpo_met,
        )
        return test_result

    def get_test_history(self, runbook_id: str) -> TestHistoryResponse | None:
        """Get test result history for a runbook. Returns None if runbook not found."""
        if runbook_id not in self._runbooks:
            return None
        tests = self._test_results.get(runbook_id, [])
        return TestHistoryResponse(
            runbook_id=runbook_id,
            tests=tests,
            total=len(tests),
        )

    # -----------------------------------------------------------------------
    # Metrics & analysis
    # -----------------------------------------------------------------------

    def get_metrics(self) -> DRMetrics:
        """Calculate aggregate DR program metrics."""
        runbooks = list(self._runbooks.values())
        total = len(runbooks)

        by_category: dict[str, int] = {}
        by_tier: dict[str, int] = {}
        by_status: dict[str, int] = {}

        for rb in runbooks:
            by_category[rb.category.value] = by_category.get(rb.category.value, 0) + 1
            by_tier[rb.tier.value] = by_tier.get(rb.tier.value, 0) + 1
            by_status[rb.status.value] = by_status.get(rb.status.value, 0) + 1

        # Tested percentage
        tested_count = sum(1 for rb in runbooks if rb.last_tested is not None)
        tested_pct = (tested_count / total * 100) if total > 0 else 0.0

        # Collect all test results
        all_tests: list[DRTestResult] = []
        for tests in self._test_results.values():
            all_tests.extend(tests)

        if all_tests:
            rto_compliance = sum(1 for t in all_tests if t.rto_met) / len(all_tests) * 100
            rpo_compliance = sum(1 for t in all_tests if t.rpo_met) / len(all_tests) * 100
            mean_rto = sum(t.actual_rto_minutes for t in all_tests) / len(all_tests)
            mean_rpo = sum(t.actual_rpo_minutes for t in all_tests) / len(all_tests)
        else:
            rto_compliance = 0.0
            rpo_compliance = 0.0
            mean_rto = 0.0
            mean_rpo = 0.0

        overdue = len(self.get_overdue_tests())

        # Last full DR test: most recent test date
        last_full = None
        if all_tests:
            last_full = max(t.test_date for t in all_tests)

        return DRMetrics(
            total_runbooks=total,
            by_category=by_category,
            by_tier=by_tier,
            by_status=by_status,
            tested_percentage=round(tested_pct, 1),
            rto_compliance_rate=round(rto_compliance, 1),
            rpo_compliance_rate=round(rpo_compliance, 1),
            mean_actual_rto=round(mean_rto, 1),
            mean_actual_rpo=round(mean_rpo, 1),
            overdue_tests_count=overdue,
            last_full_dr_test=last_full,
        )

    def get_overdue_tests(self) -> list[DisasterRecoveryRunbook]:
        """Return runbooks with overdue testing based on tier thresholds.

        Overdue thresholds:
        - TIER_1_CRITICAL: >90 days since last test
        - TIER_2_HIGH: >180 days since last test
        - TIER_3_MEDIUM / TIER_4_LOW: >365 days since last test
        - Never tested: always overdue
        """
        now = datetime.now(timezone.utc)
        overdue: list[DisasterRecoveryRunbook] = []

        for rb in self._runbooks.values():
            threshold_days = OVERDUE_THRESHOLDS.get(rb.tier, 365)
            if rb.last_tested is None:
                overdue.append(rb)
            elif (now - rb.last_tested).days > threshold_days:
                overdue.append(rb)

        return overdue

    def validate_runbook(self, runbook_id: str) -> RunbookValidation | None:
        """Validate runbook completeness.

        Checks:
        - Has at least one step
        - All steps have verification criteria
        - All steps have a responsible role
        - Has at least one escalation contact
        - Has a communication plan
        - Has prerequisites listed

        Returns None if runbook not found.
        """
        rb = self._runbooks.get(runbook_id)
        if rb is None:
            return None

        now = datetime.now(timezone.utc)
        issues: list[str] = []

        if not rb.steps:
            issues.append("Runbook has no recovery steps defined")

        for step in rb.steps:
            if not step.verification_criteria:
                issues.append(
                    f"Step {step.step_number} ('{step.title}') missing verification criteria"
                )
            if not step.responsible_role:
                issues.append(
                    f"Step {step.step_number} ('{step.title}') missing responsible role"
                )

        if not rb.escalation_contacts:
            issues.append("No escalation contacts defined")

        if not rb.communication_plan:
            issues.append("No communication plan defined")

        if not rb.prerequisites:
            issues.append("No prerequisites listed")

        return RunbookValidation(
            runbook_id=runbook_id,
            is_valid=len(issues) == 0,
            issues=issues,
            checked_at=now,
        )

    def get_communication_plan(
        self, runbook_id: str
    ) -> CommunicationPlanResponse | None:
        """Return escalation and communication details for a runbook.

        Returns None if runbook not found.
        """
        rb = self._runbooks.get(runbook_id)
        if rb is None:
            return None

        return CommunicationPlanResponse(
            runbook_id=rb.id,
            runbook_title=rb.title,
            category=rb.category,
            tier=rb.tier,
            communication_plan=rb.communication_plan,
            escalation_contacts=rb.escalation_contacts,
        )

    # -----------------------------------------------------------------------
    # Reset (for tests)
    # -----------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all data and re-seed. For testing only."""
        self._runbooks.clear()
        self._test_results.clear()
        self._populate_seed_data()


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------


def get_disaster_recovery_service() -> DisasterRecoveryService:
    """Return singleton DisasterRecoveryService instance."""
    global _dr_instance
    if _dr_instance is None:
        with _dr_lock:
            if _dr_instance is None:
                _dr_instance = DisasterRecoveryService()
    return _dr_instance


def reset_disaster_recovery_service() -> None:
    """Reset the singleton (for tests)."""
    global _dr_instance
    with _dr_lock:
        _dr_instance = None
