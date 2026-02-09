"""Threat Intelligence & DLP Service.

CISO-13: Threat intelligence feed management, IOC tracking, DLP policy
enforcement, violation monitoring, and security awareness training for the
clinical trial patient recruitment platform.

Usage:
    from app.services.threat_intelligence_service import (
        get_threat_intelligence_service,
    )

    service = get_threat_intelligence_service()
    indicator = service.create_indicator(
        ioc_type=IOCType.IP_ADDRESS,
        value="192.168.1.100",
        threat_category=ThreatCategory.APT,
        severity=ThreatSeverity.HIGH,
    )
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from threading import Lock
from uuid import uuid4

from app.schemas.threat_intelligence import (
    DLPAction,
    DLPChannel,
    DLPMetrics,
    DLPPattern,
    DLPPolicy,
    DLPPolicyType,
    DLPViolation,
    IOCType,
    SecurityAwarenessTraining,
    ThreatAlert,
    ThreatCategory,
    ThreatFeed,
    ThreatIndicator,
    ThreatMetrics,
    ThreatSeverity,
    ThreatStatus,
    TrainingComplianceRate,
)

logger = logging.getLogger(__name__)

# Singleton instance and lock
_ti_service_instance: ThreatIntelligenceService | None = None
_ti_service_lock = Lock()


class ThreatIntelligenceService:
    """In-memory threat intelligence and DLP management service."""

    def __init__(self) -> None:
        self._indicators: dict[str, ThreatIndicator] = {}
        self._feeds: dict[str, ThreatFeed] = {}
        self._alerts: dict[str, ThreatAlert] = {}
        self._dlp_policies: dict[str, DLPPolicy] = {}
        self._dlp_violations: dict[str, DLPViolation] = {}
        self._trainings: dict[str, SecurityAwarenessTraining] = {}
        self._seed_data()

    # ------------------------------------------------------------------
    # Seed data
    # ------------------------------------------------------------------

    def _seed_data(self) -> None:
        """Populate service with realistic seed data."""
        now = datetime.now(timezone.utc)

        # --- 10 Threat Indicators ---
        seed_indicators = [
            ThreatIndicator(
                id="ioc-001",
                ioc_type=IOCType.IP_ADDRESS,
                value="185.220.101.42",
                threat_category=ThreatCategory.APT,
                severity=ThreatSeverity.CRITICAL,
                description="Known APT28 C2 server",
                source="AlienVault OTX",
                first_seen=now - timedelta(days=30),
                last_seen=now - timedelta(hours=6),
                confidence_score=95.0,
                related_campaigns=["APT28-Healthcare-2025"],
                mitre_techniques=["T1071.001", "T1059.001"],
                status=ThreatStatus.CONFIRMED,
            ),
            ThreatIndicator(
                id="ioc-002",
                ioc_type=IOCType.DOMAIN,
                value="pharma-update.evil.com",
                threat_category=ThreatCategory.PHISHING,
                severity=ThreatSeverity.HIGH,
                description="Phishing domain impersonating pharma portal",
                source="PhishTank",
                first_seen=now - timedelta(days=7),
                last_seen=now - timedelta(hours=2),
                confidence_score=88.0,
                related_campaigns=["PharmPhish-Q1-2025"],
                mitre_techniques=["T1566.001", "T1598.003"],
                status=ThreatStatus.NEW,
            ),
            ThreatIndicator(
                id="ioc-003",
                ioc_type=IOCType.FILE_HASH_SHA256,
                value="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                threat_category=ThreatCategory.RANSOMWARE,
                severity=ThreatSeverity.CRITICAL,
                description="LockBit 3.0 ransomware payload hash",
                source="VirusTotal",
                first_seen=now - timedelta(days=14),
                last_seen=now - timedelta(days=1),
                confidence_score=99.0,
                related_campaigns=["LockBit3-Healthcare"],
                mitre_techniques=["T1486", "T1490"],
                status=ThreatStatus.CONFIRMED,
            ),
            ThreatIndicator(
                id="ioc-004",
                ioc_type=IOCType.EMAIL_ADDRESS,
                value="admin@clinical-trials-update.net",
                threat_category=ThreatCategory.SOCIAL_ENGINEERING,
                severity=ThreatSeverity.MEDIUM,
                description="Social engineering email targeting clinical staff",
                source="Internal SOC",
                first_seen=now - timedelta(days=5),
                last_seen=now - timedelta(days=3),
                confidence_score=72.0,
                related_campaigns=[],
                mitre_techniques=["T1566.002"],
                status=ThreatStatus.UNDER_INVESTIGATION,
            ),
            ThreatIndicator(
                id="ioc-005",
                ioc_type=IOCType.URL,
                value="https://malware-cdn.example.com/payload.exe",
                threat_category=ThreatCategory.ZERO_DAY,
                severity=ThreatSeverity.CRITICAL,
                description="Zero-day exploit delivery URL",
                source="CISA Alert",
                first_seen=now - timedelta(days=2),
                last_seen=now - timedelta(hours=12),
                confidence_score=92.0,
                related_campaigns=["ZeroDay-CVE-2025-1234"],
                mitre_techniques=["T1203", "T1068"],
                status=ThreatStatus.NEW,
            ),
            ThreatIndicator(
                id="ioc-006",
                ioc_type=IOCType.CVE_ID,
                value="CVE-2025-0001",
                threat_category=ThreatCategory.SUPPLY_CHAIN,
                severity=ThreatSeverity.HIGH,
                description="Critical supply chain vulnerability in npm package",
                source="NVD",
                first_seen=now - timedelta(days=10),
                last_seen=now - timedelta(days=1),
                confidence_score=85.0,
                related_campaigns=["SupplyChain-NPM-2025"],
                mitre_techniques=["T1195.002"],
                status=ThreatStatus.CONFIRMED,
            ),
            ThreatIndicator(
                id="ioc-007",
                ioc_type=IOCType.IP_ADDRESS,
                value="10.0.0.99",
                threat_category=ThreatCategory.INSIDER,
                severity=ThreatSeverity.HIGH,
                description="Internal workstation with anomalous data access patterns",
                source="UEBA System",
                first_seen=now - timedelta(days=3),
                last_seen=now - timedelta(hours=1),
                confidence_score=78.0,
                related_campaigns=[],
                mitre_techniques=["T1078", "T1530"],
                status=ThreatStatus.UNDER_INVESTIGATION,
            ),
            ThreatIndicator(
                id="ioc-008",
                ioc_type=IOCType.IP_ADDRESS,
                value="203.0.113.50",
                threat_category=ThreatCategory.CREDENTIAL_STUFFING,
                severity=ThreatSeverity.MEDIUM,
                description="Source of credential stuffing attacks on login portal",
                source="WAF Logs",
                first_seen=now - timedelta(days=20),
                last_seen=now - timedelta(hours=4),
                confidence_score=80.0,
                related_campaigns=["CredStuff-Portal-2025"],
                mitre_techniques=["T1110.004"],
                status=ThreatStatus.CONFIRMED,
            ),
            ThreatIndicator(
                id="ioc-009",
                ioc_type=IOCType.DOMAIN,
                value="exfil-data.attacker.io",
                threat_category=ThreatCategory.DATA_EXFILTRATION,
                severity=ThreatSeverity.CRITICAL,
                description="DNS tunneling domain used for data exfiltration",
                source="DNS Analytics",
                first_seen=now - timedelta(days=1),
                last_seen=now - timedelta(minutes=30),
                confidence_score=91.0,
                related_campaigns=["DataExfil-DNS-2025"],
                mitre_techniques=["T1048.001", "T1071.004"],
                status=ThreatStatus.NEW,
            ),
            ThreatIndicator(
                id="ioc-010",
                ioc_type=IOCType.IP_ADDRESS,
                value="198.51.100.200",
                threat_category=ThreatCategory.DDOS,
                severity=ThreatSeverity.LOW,
                description="Historical DDoS source - mitigated by upstream provider",
                source="Cloudflare",
                first_seen=now - timedelta(days=60),
                last_seen=now - timedelta(days=45),
                confidence_score=65.0,
                related_campaigns=[],
                mitre_techniques=["T1498"],
                status=ThreatStatus.MITIGATED,
            ),
        ]
        for ind in seed_indicators:
            self._indicators[ind.id] = ind

        # --- 4 Threat Feeds ---
        seed_feeds = [
            ThreatFeed(
                id="feed-001",
                name="AlienVault OTX",
                provider="AT&T Cybersecurity",
                url="https://otx.alienvault.com/api/v1/pulses",
                feed_type="STIX",
                update_frequency_hours=4,
                last_updated=now - timedelta(hours=2),
                indicators_count=1245,
                enabled=True,
                api_key_configured=True,
            ),
            ThreatFeed(
                id="feed-002",
                name="CISA Known Exploited Vulnerabilities",
                provider="CISA",
                url="https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
                feed_type="JSON",
                update_frequency_hours=24,
                last_updated=now - timedelta(hours=12),
                indicators_count=892,
                enabled=True,
                api_key_configured=False,
            ),
            ThreatFeed(
                id="feed-003",
                name="Abuse.ch URLhaus",
                provider="abuse.ch",
                url="https://urlhaus-api.abuse.ch/v1/",
                feed_type="CSV",
                update_frequency_hours=1,
                last_updated=now - timedelta(minutes=45),
                indicators_count=5678,
                enabled=True,
                api_key_configured=False,
            ),
            ThreatFeed(
                id="feed-004",
                name="MISP Healthcare ISAC",
                provider="Health-ISAC",
                url="https://misp.health-isac.org/feeds",
                feed_type="STIX",
                update_frequency_hours=6,
                last_updated=now - timedelta(hours=4),
                indicators_count=2340,
                enabled=False,
                api_key_configured=True,
            ),
        ]
        for feed in seed_feeds:
            self._feeds[feed.id] = feed

        # --- 6 Threat Alerts ---
        seed_alerts = [
            ThreatAlert(
                id="alert-001",
                title="APT28 C2 Communication Detected",
                description="Outbound traffic to known APT28 C2 server 185.220.101.42 detected from internal network",
                severity=ThreatSeverity.CRITICAL,
                category=ThreatCategory.APT,
                indicators=["ioc-001"],
                affected_systems=["app-server-01", "db-server-02"],
                detection_method="Network IDS signature match",
                created_at=now - timedelta(hours=6),
                acknowledged=False,
                acknowledged_by=None,
                mitigated=False,
            ),
            ThreatAlert(
                id="alert-002",
                title="Phishing Campaign Targeting Clinical Staff",
                description="Multiple phishing emails detected targeting clinical trial coordinators",
                severity=ThreatSeverity.HIGH,
                category=ThreatCategory.PHISHING,
                indicators=["ioc-002"],
                affected_systems=["email-gateway"],
                detection_method="Email security gateway",
                created_at=now - timedelta(hours=12),
                acknowledged=True,
                acknowledged_by="soc-analyst-1",
                mitigated=False,
            ),
            ThreatAlert(
                id="alert-003",
                title="Ransomware Payload Detected on Endpoint",
                description="LockBit 3.0 payload hash matched on endpoint during scheduled scan",
                severity=ThreatSeverity.CRITICAL,
                category=ThreatCategory.RANSOMWARE,
                indicators=["ioc-003"],
                affected_systems=["workstation-lab-07"],
                detection_method="EDR real-time scan",
                created_at=now - timedelta(days=1),
                acknowledged=True,
                acknowledged_by="soc-analyst-2",
                mitigated=True,
            ),
            ThreatAlert(
                id="alert-004",
                title="Anomalous Data Access from Internal Host",
                description="Insider threat indicators: bulk patient data access from 10.0.0.99 outside business hours",
                severity=ThreatSeverity.HIGH,
                category=ThreatCategory.INSIDER,
                indicators=["ioc-007"],
                affected_systems=["patient-db", "ehr-api"],
                detection_method="UEBA behavioral analysis",
                created_at=now - timedelta(hours=3),
                acknowledged=False,
                acknowledged_by=None,
                mitigated=False,
            ),
            ThreatAlert(
                id="alert-005",
                title="DNS Tunneling Data Exfiltration Attempt",
                description="High-entropy DNS queries to exfil-data.attacker.io indicating DNS tunneling",
                severity=ThreatSeverity.CRITICAL,
                category=ThreatCategory.DATA_EXFILTRATION,
                indicators=["ioc-009"],
                affected_systems=["dns-server", "app-server-03"],
                detection_method="DNS anomaly detection",
                created_at=now - timedelta(minutes=30),
                acknowledged=False,
                acknowledged_by=None,
                mitigated=False,
            ),
            ThreatAlert(
                id="alert-006",
                title="Credential Stuffing Attack on Login Portal",
                description="Sustained credential stuffing attack from 203.0.113.50 targeting patient portal",
                severity=ThreatSeverity.MEDIUM,
                category=ThreatCategory.CREDENTIAL_STUFFING,
                indicators=["ioc-008"],
                affected_systems=["patient-portal", "auth-service"],
                detection_method="WAF rate limiting triggered",
                created_at=now - timedelta(hours=4),
                acknowledged=True,
                acknowledged_by="soc-analyst-1",
                mitigated=True,
            ),
        ]
        for alert in seed_alerts:
            self._alerts[alert.id] = alert

        # --- 8 DLP Policies ---
        seed_dlp_policies = [
            DLPPolicy(
                id="dlp-001",
                name="PHI Detection - Patient Records",
                policy_type=DLPPolicyType.PHI_DETECTION,
                description="Detect protected health information in outbound communications",
                channels=[DLPChannel.EMAIL, DLPChannel.WEB_UPLOAD, DLPChannel.API_ENDPOINT],
                action=DLPAction.BLOCK,
                enabled=True,
                patterns=[
                    DLPPattern(
                        pattern_name="SSN Pattern",
                        regex_pattern=r"\b\d{3}-\d{2}-\d{4}\b",
                        description="Social Security Number format",
                        sample_match="123-45-6789",
                    ),
                    DLPPattern(
                        pattern_name="MRN Pattern",
                        regex_pattern=r"\bMRN[:\s]?\d{6,10}\b",
                        description="Medical Record Number",
                        sample_match="MRN:12345678",
                    ),
                    DLPPattern(
                        pattern_name="DOB Pattern",
                        regex_pattern=r"\b(DOB|Date of Birth)[:\s]?\d{1,2}/\d{1,2}/\d{2,4}\b",
                        description="Date of Birth in context",
                        sample_match="DOB: 01/15/1990",
                    ),
                ],
                sensitivity_threshold=0.9,
                exceptions=["encrypted-export@company.com"],
                violation_count_30d=23,
                last_triggered=now - timedelta(hours=3),
                created_at=now - timedelta(days=180),
                updated_at=now - timedelta(days=5),
            ),
            DLPPolicy(
                id="dlp-002",
                name="PII Detection - Contact Information",
                policy_type=DLPPolicyType.PII_DETECTION,
                description="Detect personally identifiable information such as names, addresses, phone numbers",
                channels=[DLPChannel.EMAIL, DLPChannel.CLOUD_STORAGE, DLPChannel.CLIPBOARD],
                action=DLPAction.ALERT,
                enabled=True,
                patterns=[
                    DLPPattern(
                        pattern_name="Phone Number",
                        regex_pattern=r"\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
                        description="US phone number format",
                        sample_match="(555) 123-4567",
                    ),
                    DLPPattern(
                        pattern_name="Email Address",
                        regex_pattern=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
                        description="Email address pattern",
                        sample_match="patient@example.com",
                    ),
                ],
                sensitivity_threshold=0.7,
                exceptions=[],
                violation_count_30d=45,
                last_triggered=now - timedelta(hours=1),
                created_at=now - timedelta(days=160),
                updated_at=now - timedelta(days=10),
            ),
            DLPPolicy(
                id="dlp-003",
                name="Credential Detection - API Keys & Passwords",
                policy_type=DLPPolicyType.CREDENTIAL_DETECTION,
                description="Detect credentials, API keys, and passwords in communications",
                channels=[DLPChannel.EMAIL, DLPChannel.WEB_UPLOAD, DLPChannel.CLOUD_STORAGE, DLPChannel.API_ENDPOINT],
                action=DLPAction.BLOCK,
                enabled=True,
                patterns=[
                    DLPPattern(
                        pattern_name="AWS Access Key",
                        regex_pattern=r"\bAKIA[0-9A-Z]{16}\b",
                        description="AWS Access Key ID",
                        sample_match="AKIAIOSFODNN7EXAMPLE",
                    ),
                    DLPPattern(
                        pattern_name="Generic API Key",
                        regex_pattern=r"\b(api[_-]?key|apikey)[=:\s]+['\"]?[A-Za-z0-9]{20,}['\"]?\b",
                        description="Generic API key pattern",
                        sample_match="api_key=abcdef1234567890abcdef",
                    ),
                    DLPPattern(
                        pattern_name="Private Key Header",
                        regex_pattern=r"-----BEGIN (RSA |EC )?PRIVATE KEY-----",
                        description="Private key PEM header",
                        sample_match="-----BEGIN PRIVATE KEY-----",
                    ),
                ],
                sensitivity_threshold=0.95,
                exceptions=["security-team@company.com"],
                violation_count_30d=8,
                last_triggered=now - timedelta(days=2),
                created_at=now - timedelta(days=150),
                updated_at=now - timedelta(days=3),
            ),
            DLPPolicy(
                id="dlp-004",
                name="Source Code Protection",
                policy_type=DLPPolicyType.SOURCE_CODE,
                description="Prevent proprietary source code from leaving the organization",
                channels=[DLPChannel.EMAIL, DLPChannel.USB_TRANSFER, DLPChannel.CLOUD_STORAGE],
                action=DLPAction.QUARANTINE,
                enabled=True,
                patterns=[
                    DLPPattern(
                        pattern_name="Python Import",
                        regex_pattern=r"\bfrom\s+app\.\w+\s+import\b",
                        description="Internal Python module imports",
                        sample_match="from app.services import handler",
                    ),
                ],
                sensitivity_threshold=0.85,
                exceptions=["open-source-release@company.com"],
                violation_count_30d=3,
                last_triggered=now - timedelta(days=5),
                created_at=now - timedelta(days=120),
                updated_at=now - timedelta(days=15),
            ),
            DLPPolicy(
                id="dlp-005",
                name="Financial Data - Trial Budget & Payments",
                policy_type=DLPPolicyType.FINANCIAL_DATA,
                description="Detect financial data including trial budgets, payment details, and invoices",
                channels=[DLPChannel.EMAIL, DLPChannel.PRINT, DLPChannel.WEB_UPLOAD],
                action=DLPAction.ENCRYPT,
                enabled=True,
                patterns=[
                    DLPPattern(
                        pattern_name="Credit Card",
                        regex_pattern=r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
                        description="Credit card number",
                        sample_match="4111-1111-1111-1111",
                    ),
                    DLPPattern(
                        pattern_name="Bank Account",
                        regex_pattern=r"\b(account|acct)[#:\s]+\d{8,17}\b",
                        description="Bank account number reference",
                        sample_match="account: 123456789012",
                    ),
                ],
                sensitivity_threshold=0.9,
                exceptions=[],
                violation_count_30d=12,
                last_triggered=now - timedelta(hours=8),
                created_at=now - timedelta(days=140),
                updated_at=now - timedelta(days=7),
            ),
            DLPPolicy(
                id="dlp-006",
                name="Intellectual Property - Study Protocols",
                policy_type=DLPPolicyType.INTELLECTUAL_PROPERTY,
                description="Protect clinical study protocols and proprietary research data",
                channels=[DLPChannel.EMAIL, DLPChannel.USB_TRANSFER, DLPChannel.CLOUD_STORAGE, DLPChannel.PRINT],
                action=DLPAction.BLOCK,
                enabled=True,
                patterns=[
                    DLPPattern(
                        pattern_name="Protocol Identifier",
                        regex_pattern=r"\b(PROTOCOL|STUDY)[-\s]?\d{3,6}[-\s]?[A-Z]{0,3}\b",
                        description="Study protocol number pattern",
                        sample_match="PROTOCOL-12345-AB",
                    ),
                ],
                sensitivity_threshold=0.85,
                exceptions=["regulatory-submissions@company.com"],
                violation_count_30d=5,
                last_triggered=now - timedelta(days=1),
                created_at=now - timedelta(days=130),
                updated_at=now - timedelta(days=2),
            ),
            DLPPolicy(
                id="dlp-007",
                name="HIPAA Compliance - Clinical Notes",
                policy_type=DLPPolicyType.PHI_DETECTION,
                description="Extended PHI detection for clinical notes and trial documentation",
                channels=[DLPChannel.API_ENDPOINT, DLPChannel.WEB_UPLOAD],
                action=DLPAction.REDACT,
                enabled=True,
                patterns=[
                    DLPPattern(
                        pattern_name="Patient Name Context",
                        regex_pattern=r"\b(patient|pt|subject)[:\s]+[A-Z][a-z]+\s[A-Z][a-z]+\b",
                        description="Patient name in clinical context",
                        sample_match="patient: John Smith",
                    ),
                    DLPPattern(
                        pattern_name="Diagnosis Code",
                        regex_pattern=r"\b[A-Z]\d{2}\.\d{1,4}\b",
                        description="ICD-10 diagnosis code",
                        sample_match="E11.65",
                    ),
                ],
                sensitivity_threshold=0.8,
                exceptions=[],
                violation_count_30d=18,
                last_triggered=now - timedelta(hours=2),
                created_at=now - timedelta(days=90),
                updated_at=now - timedelta(days=1),
            ),
            DLPPolicy(
                id="dlp-008",
                name="USB Data Transfer Control",
                policy_type=DLPPolicyType.PII_DETECTION,
                description="Monitor and control USB data transfers containing sensitive information",
                channels=[DLPChannel.USB_TRANSFER],
                action=DLPAction.LOG_ONLY,
                enabled=False,
                patterns=[],
                sensitivity_threshold=0.6,
                exceptions=[],
                violation_count_30d=0,
                last_triggered=None,
                created_at=now - timedelta(days=60),
                updated_at=None,
            ),
        ]
        for policy in seed_dlp_policies:
            self._dlp_policies[policy.id] = policy

        # --- 12 DLP Violations ---
        seed_violations = [
            DLPViolation(
                id="viol-001",
                policy_id="dlp-001",
                channel=DLPChannel.EMAIL,
                user_id="user-101",
                content_summary="Email contained SSN pattern: ***-**-6789",
                data_classification="PHI",
                action_taken=DLPAction.BLOCK,
                timestamp=now - timedelta(hours=3),
                resolved=False,
                resolution_notes=None,
            ),
            DLPViolation(
                id="viol-002",
                policy_id="dlp-001",
                channel=DLPChannel.WEB_UPLOAD,
                user_id="user-102",
                content_summary="File upload contained MRN numbers",
                data_classification="PHI",
                action_taken=DLPAction.BLOCK,
                timestamp=now - timedelta(hours=5),
                resolved=True,
                resolution_notes="User redirected to secure file transfer portal",
            ),
            DLPViolation(
                id="viol-003",
                policy_id="dlp-002",
                channel=DLPChannel.EMAIL,
                user_id="user-103",
                content_summary="Email contained patient phone numbers",
                data_classification="PII",
                action_taken=DLPAction.ALERT,
                timestamp=now - timedelta(hours=1),
                resolved=False,
                resolution_notes=None,
            ),
            DLPViolation(
                id="viol-004",
                policy_id="dlp-002",
                channel=DLPChannel.CLOUD_STORAGE,
                user_id="user-104",
                content_summary="Spreadsheet with patient email addresses uploaded to shared drive",
                data_classification="PII",
                action_taken=DLPAction.ALERT,
                timestamp=now - timedelta(hours=8),
                resolved=True,
                resolution_notes="File removed and re-uploaded to encrypted folder",
            ),
            DLPViolation(
                id="viol-005",
                policy_id="dlp-003",
                channel=DLPChannel.EMAIL,
                user_id="user-105",
                content_summary="Email body contained AWS access key",
                data_classification="Credential",
                action_taken=DLPAction.BLOCK,
                timestamp=now - timedelta(days=2),
                resolved=True,
                resolution_notes="Key rotated immediately, user counseled",
            ),
            DLPViolation(
                id="viol-006",
                policy_id="dlp-003",
                channel=DLPChannel.WEB_UPLOAD,
                user_id="user-106",
                content_summary="GitHub push contained private key file",
                data_classification="Credential",
                action_taken=DLPAction.BLOCK,
                timestamp=now - timedelta(days=1),
                resolved=False,
                resolution_notes=None,
            ),
            DLPViolation(
                id="viol-007",
                policy_id="dlp-004",
                channel=DLPChannel.USB_TRANSFER,
                user_id="user-107",
                content_summary="USB transfer of source code files detected",
                data_classification="Source Code",
                action_taken=DLPAction.QUARANTINE,
                timestamp=now - timedelta(days=5),
                resolved=True,
                resolution_notes="Authorized code review transfer, approved by manager",
            ),
            DLPViolation(
                id="viol-008",
                policy_id="dlp-005",
                channel=DLPChannel.EMAIL,
                user_id="user-108",
                content_summary="Invoice with credit card numbers sent externally",
                data_classification="Financial",
                action_taken=DLPAction.ENCRYPT,
                timestamp=now - timedelta(hours=8),
                resolved=False,
                resolution_notes=None,
            ),
            DLPViolation(
                id="viol-009",
                policy_id="dlp-005",
                channel=DLPChannel.PRINT,
                user_id="user-109",
                content_summary="Print job containing bank account details",
                data_classification="Financial",
                action_taken=DLPAction.ENCRYPT,
                timestamp=now - timedelta(days=3),
                resolved=True,
                resolution_notes="Print redirected to secure printer",
            ),
            DLPViolation(
                id="viol-010",
                policy_id="dlp-006",
                channel=DLPChannel.EMAIL,
                user_id="user-110",
                content_summary="Study protocol document attached to external email",
                data_classification="IP",
                action_taken=DLPAction.BLOCK,
                timestamp=now - timedelta(days=1),
                resolved=False,
                resolution_notes=None,
            ),
            DLPViolation(
                id="viol-011",
                policy_id="dlp-007",
                channel=DLPChannel.API_ENDPOINT,
                user_id="user-111",
                content_summary="API response contained unredacted patient names",
                data_classification="PHI",
                action_taken=DLPAction.REDACT,
                timestamp=now - timedelta(hours=2),
                resolved=True,
                resolution_notes="API response filter updated to redact patient names",
            ),
            DLPViolation(
                id="viol-012",
                policy_id="dlp-007",
                channel=DLPChannel.WEB_UPLOAD,
                user_id="user-112",
                content_summary="Clinical notes uploaded with ICD-10 codes and patient identifiers",
                data_classification="PHI",
                action_taken=DLPAction.REDACT,
                timestamp=now - timedelta(hours=4),
                resolved=False,
                resolution_notes=None,
            ),
        ]
        for viol in seed_violations:
            self._dlp_violations[viol.id] = viol

        # --- 5 Security Awareness Trainings ---
        seed_trainings = [
            SecurityAwarenessTraining(
                id="train-001",
                name="Annual HIPAA Security Training",
                training_type="HIPAA",
                description="Mandatory annual training on HIPAA security rule requirements",
                required_for_roles=["all"],
                completion_deadline=now + timedelta(days=30),
                total_assigned=250,
                total_completed=195,
                pass_rate=94.5,
                phishing_simulation_click_rate=None,
            ),
            SecurityAwarenessTraining(
                id="train-002",
                name="Phishing Awareness - Q1 2025",
                training_type="Phishing",
                description="Quarterly phishing awareness training with simulated exercises",
                required_for_roles=["all"],
                completion_deadline=now + timedelta(days=15),
                total_assigned=250,
                total_completed=220,
                pass_rate=89.0,
                phishing_simulation_click_rate=12.5,
            ),
            SecurityAwarenessTraining(
                id="train-003",
                name="Secure Coding Practices",
                training_type="Developer Security",
                description="Secure coding training for development team covering OWASP Top 10",
                required_for_roles=["developer", "devops", "architect"],
                completion_deadline=now + timedelta(days=45),
                total_assigned=45,
                total_completed=30,
                pass_rate=92.0,
                phishing_simulation_click_rate=None,
            ),
            SecurityAwarenessTraining(
                id="train-004",
                name="Incident Response Procedures",
                training_type="Incident Response",
                description="Training on incident response procedures and escalation paths",
                required_for_roles=["soc-analyst", "security-engineer", "manager"],
                completion_deadline=now - timedelta(days=5),
                total_assigned=30,
                total_completed=28,
                pass_rate=96.0,
                phishing_simulation_click_rate=None,
            ),
            SecurityAwarenessTraining(
                id="train-005",
                name="Social Engineering Defense",
                training_type="Social Engineering",
                description="Recognizing and defending against social engineering attacks",
                required_for_roles=["clinical-staff", "admin", "receptionist"],
                completion_deadline=now + timedelta(days=60),
                total_assigned=80,
                total_completed=45,
                pass_rate=88.0,
                phishing_simulation_click_rate=18.0,
            ),
        ]
        for training in seed_trainings:
            self._trainings[training.id] = training

    # ------------------------------------------------------------------
    # Indicator CRUD
    # ------------------------------------------------------------------

    def list_indicators(
        self,
        *,
        ioc_type: IOCType | None = None,
        threat_category: ThreatCategory | None = None,
        severity: ThreatSeverity | None = None,
        status: ThreatStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ThreatIndicator], int]:
        """List indicators with optional filters."""
        items = list(self._indicators.values())
        if ioc_type is not None:
            items = [i for i in items if i.ioc_type == ioc_type]
        if threat_category is not None:
            items = [i for i in items if i.threat_category == threat_category]
        if severity is not None:
            items = [i for i in items if i.severity == severity]
        if status is not None:
            items = [i for i in items if i.status == status]
        total = len(items)
        return items[offset : offset + limit], total

    def get_indicator(self, indicator_id: str) -> ThreatIndicator | None:
        """Get a single indicator by ID."""
        return self._indicators.get(indicator_id)

    def search_indicator_by_value(self, value: str) -> list[ThreatIndicator]:
        """Search indicators by IOC value (exact or substring)."""
        return [
            i for i in self._indicators.values()
            if value.lower() in i.value.lower()
        ]

    def create_indicator(
        self,
        *,
        ioc_type: IOCType,
        value: str,
        threat_category: ThreatCategory,
        severity: ThreatSeverity,
        description: str = "",
        source: str = "manual",
        confidence_score: float = 50.0,
        related_campaigns: list[str] | None = None,
        mitre_techniques: list[str] | None = None,
    ) -> ThreatIndicator:
        """Create a new threat indicator."""
        now = datetime.now(timezone.utc)
        indicator = ThreatIndicator(
            id=f"ioc-{uuid4().hex[:8]}",
            ioc_type=ioc_type,
            value=value,
            threat_category=threat_category,
            severity=severity,
            description=description,
            source=source,
            first_seen=now,
            last_seen=now,
            confidence_score=confidence_score,
            related_campaigns=related_campaigns or [],
            mitre_techniques=mitre_techniques or [],
            status=ThreatStatus.NEW,
        )
        self._indicators[indicator.id] = indicator
        logger.info("Created threat indicator %s: %s", indicator.id, value)
        return indicator

    def update_indicator(
        self,
        indicator_id: str,
        *,
        severity: ThreatSeverity | None = None,
        description: str | None = None,
        confidence_score: float | None = None,
        status: ThreatStatus | None = None,
        related_campaigns: list[str] | None = None,
        mitre_techniques: list[str] | None = None,
    ) -> ThreatIndicator | None:
        """Update an existing indicator."""
        indicator = self._indicators.get(indicator_id)
        if indicator is None:
            return None
        data = indicator.model_dump()
        if severity is not None:
            data["severity"] = severity
        if description is not None:
            data["description"] = description
        if confidence_score is not None:
            data["confidence_score"] = confidence_score
        if status is not None:
            data["status"] = status
        if related_campaigns is not None:
            data["related_campaigns"] = related_campaigns
        if mitre_techniques is not None:
            data["mitre_techniques"] = mitre_techniques
        data["last_seen"] = datetime.now(timezone.utc)
        updated = ThreatIndicator(**data)
        self._indicators[indicator_id] = updated
        return updated

    def delete_indicator(self, indicator_id: str) -> bool:
        """Delete an indicator."""
        return self._indicators.pop(indicator_id, None) is not None

    # ------------------------------------------------------------------
    # Feed Management
    # ------------------------------------------------------------------

    def list_feeds(self) -> list[ThreatFeed]:
        """List all configured feeds."""
        return list(self._feeds.values())

    def get_feed(self, feed_id: str) -> ThreatFeed | None:
        """Get a single feed by ID."""
        return self._feeds.get(feed_id)

    def create_feed(
        self,
        *,
        name: str,
        provider: str,
        url: str = "",
        feed_type: str = "STIX",
        update_frequency_hours: int = 24,
        enabled: bool = True,
    ) -> ThreatFeed:
        """Create a new threat feed."""
        feed = ThreatFeed(
            id=f"feed-{uuid4().hex[:8]}",
            name=name,
            provider=provider,
            url=url,
            feed_type=feed_type,
            update_frequency_hours=update_frequency_hours,
            last_updated=None,
            indicators_count=0,
            enabled=enabled,
            api_key_configured=False,
        )
        self._feeds[feed.id] = feed
        logger.info("Created threat feed %s: %s", feed.id, name)
        return feed

    def update_feed(
        self,
        feed_id: str,
        *,
        name: str | None = None,
        url: str | None = None,
        update_frequency_hours: int | None = None,
        enabled: bool | None = None,
    ) -> ThreatFeed | None:
        """Update a feed configuration."""
        feed = self._feeds.get(feed_id)
        if feed is None:
            return None
        data = feed.model_dump()
        if name is not None:
            data["name"] = name
        if url is not None:
            data["url"] = url
        if update_frequency_hours is not None:
            data["update_frequency_hours"] = update_frequency_hours
        if enabled is not None:
            data["enabled"] = enabled
        updated = ThreatFeed(**data)
        self._feeds[feed_id] = updated
        return updated

    def delete_feed(self, feed_id: str) -> bool:
        """Delete a feed."""
        return self._feeds.pop(feed_id, None) is not None

    # ------------------------------------------------------------------
    # Alert Management
    # ------------------------------------------------------------------

    def list_alerts(
        self,
        *,
        severity: ThreatSeverity | None = None,
        category: ThreatCategory | None = None,
        acknowledged: bool | None = None,
    ) -> list[ThreatAlert]:
        """List alerts with optional filters."""
        items = list(self._alerts.values())
        if severity is not None:
            items = [a for a in items if a.severity == severity]
        if category is not None:
            items = [a for a in items if a.category == category]
        if acknowledged is not None:
            items = [a for a in items if a.acknowledged == acknowledged]
        return items

    def get_alert(self, alert_id: str) -> ThreatAlert | None:
        """Get a single alert by ID."""
        return self._alerts.get(alert_id)

    def create_alert(
        self,
        *,
        title: str,
        description: str = "",
        severity: ThreatSeverity,
        category: ThreatCategory,
        indicators: list[str] | None = None,
        affected_systems: list[str] | None = None,
        detection_method: str = "",
    ) -> ThreatAlert:
        """Create a new threat alert."""
        alert = ThreatAlert(
            id=f"alert-{uuid4().hex[:8]}",
            title=title,
            description=description,
            severity=severity,
            category=category,
            indicators=indicators or [],
            affected_systems=affected_systems or [],
            detection_method=detection_method,
            created_at=datetime.now(timezone.utc),
            acknowledged=False,
            acknowledged_by=None,
            mitigated=False,
        )
        self._alerts[alert.id] = alert
        logger.info("Created threat alert %s: %s", alert.id, title)
        return alert

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> ThreatAlert | None:
        """Acknowledge an alert."""
        alert = self._alerts.get(alert_id)
        if alert is None:
            return None
        data = alert.model_dump()
        data["acknowledged"] = True
        data["acknowledged_by"] = acknowledged_by
        updated = ThreatAlert(**data)
        self._alerts[alert_id] = updated
        return updated

    def mitigate_alert(self, alert_id: str) -> ThreatAlert | None:
        """Mark an alert as mitigated."""
        alert = self._alerts.get(alert_id)
        if alert is None:
            return None
        data = alert.model_dump()
        data["mitigated"] = True
        updated = ThreatAlert(**data)
        self._alerts[alert_id] = updated
        return updated

    # ------------------------------------------------------------------
    # DLP Policy CRUD
    # ------------------------------------------------------------------

    def list_dlp_policies(
        self,
        *,
        policy_type: DLPPolicyType | None = None,
        enabled: bool | None = None,
    ) -> list[DLPPolicy]:
        """List DLP policies with optional filters."""
        items = list(self._dlp_policies.values())
        if policy_type is not None:
            items = [p for p in items if p.policy_type == policy_type]
        if enabled is not None:
            items = [p for p in items if p.enabled == enabled]
        return items

    def get_dlp_policy(self, policy_id: str) -> DLPPolicy | None:
        """Get a single DLP policy by ID."""
        return self._dlp_policies.get(policy_id)

    def create_dlp_policy(
        self,
        *,
        name: str,
        policy_type: DLPPolicyType,
        description: str = "",
        channels: list[DLPChannel] | None = None,
        action: DLPAction = DLPAction.ALERT,
        enabled: bool = True,
        patterns: list[DLPPattern] | None = None,
        sensitivity_threshold: float = 0.8,
        exceptions: list[str] | None = None,
    ) -> DLPPolicy:
        """Create a new DLP policy."""
        now = datetime.now(timezone.utc)
        policy = DLPPolicy(
            id=f"dlp-{uuid4().hex[:8]}",
            name=name,
            policy_type=policy_type,
            description=description,
            channels=channels or [],
            action=action,
            enabled=enabled,
            patterns=patterns or [],
            sensitivity_threshold=sensitivity_threshold,
            exceptions=exceptions or [],
            violation_count_30d=0,
            last_triggered=None,
            created_at=now,
            updated_at=None,
        )
        self._dlp_policies[policy.id] = policy
        logger.info("Created DLP policy %s: %s", policy.id, name)
        return policy

    def update_dlp_policy(
        self,
        policy_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        channels: list[DLPChannel] | None = None,
        action: DLPAction | None = None,
        enabled: bool | None = None,
        patterns: list[DLPPattern] | None = None,
        sensitivity_threshold: float | None = None,
        exceptions: list[str] | None = None,
    ) -> DLPPolicy | None:
        """Update a DLP policy."""
        policy = self._dlp_policies.get(policy_id)
        if policy is None:
            return None
        data = policy.model_dump()
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description
        if channels is not None:
            data["channels"] = channels
        if action is not None:
            data["action"] = action
        if enabled is not None:
            data["enabled"] = enabled
        if patterns is not None:
            data["patterns"] = [p.model_dump() if isinstance(p, DLPPattern) else p for p in patterns]
        if sensitivity_threshold is not None:
            data["sensitivity_threshold"] = sensitivity_threshold
        if exceptions is not None:
            data["exceptions"] = exceptions
        data["updated_at"] = datetime.now(timezone.utc)
        updated = DLPPolicy(**data)
        self._dlp_policies[policy_id] = updated
        return updated

    def delete_dlp_policy(self, policy_id: str) -> bool:
        """Delete a DLP policy."""
        return self._dlp_policies.pop(policy_id, None) is not None

    def enable_dlp_policy(self, policy_id: str) -> DLPPolicy | None:
        """Enable a DLP policy."""
        return self.update_dlp_policy(policy_id, enabled=True)

    def disable_dlp_policy(self, policy_id: str) -> DLPPolicy | None:
        """Disable a DLP policy."""
        return self.update_dlp_policy(policy_id, enabled=False)

    # ------------------------------------------------------------------
    # DLP Violation Tracking
    # ------------------------------------------------------------------

    def list_violations(
        self,
        *,
        policy_id: str | None = None,
        channel: DLPChannel | None = None,
        resolved: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[DLPViolation], int]:
        """List DLP violations with optional filters."""
        items = list(self._dlp_violations.values())
        if policy_id is not None:
            items = [v for v in items if v.policy_id == policy_id]
        if channel is not None:
            items = [v for v in items if v.channel == channel]
        if resolved is not None:
            items = [v for v in items if v.resolved == resolved]
        total = len(items)
        return items[offset : offset + limit], total

    def get_violation(self, violation_id: str) -> DLPViolation | None:
        """Get a single DLP violation by ID."""
        return self._dlp_violations.get(violation_id)

    def create_violation(
        self,
        *,
        policy_id: str,
        channel: DLPChannel,
        user_id: str = "",
        content_summary: str = "",
        data_classification: str = "",
        action_taken: DLPAction,
    ) -> DLPViolation | None:
        """Record a new DLP violation. Returns None if policy_id not found."""
        if policy_id not in self._dlp_policies:
            return None
        violation = DLPViolation(
            id=f"viol-{uuid4().hex[:8]}",
            policy_id=policy_id,
            channel=channel,
            user_id=user_id,
            content_summary=content_summary,
            data_classification=data_classification,
            action_taken=action_taken,
            timestamp=datetime.now(timezone.utc),
            resolved=False,
            resolution_notes=None,
        )
        self._dlp_violations[violation.id] = violation
        # Update policy violation count
        policy = self._dlp_policies[policy_id]
        data = policy.model_dump()
        data["violation_count_30d"] = data["violation_count_30d"] + 1
        data["last_triggered"] = violation.timestamp
        self._dlp_policies[policy_id] = DLPPolicy(**data)
        return violation

    def resolve_violation(
        self,
        violation_id: str,
        *,
        resolution_notes: str,
    ) -> DLPViolation | None:
        """Resolve a DLP violation."""
        violation = self._dlp_violations.get(violation_id)
        if violation is None:
            return None
        data = violation.model_dump()
        data["resolved"] = True
        data["resolution_notes"] = resolution_notes
        updated = DLPViolation(**data)
        self._dlp_violations[violation_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Training Management
    # ------------------------------------------------------------------

    def list_trainings(self) -> list[SecurityAwarenessTraining]:
        """List all training programs."""
        return list(self._trainings.values())

    def get_training(self, training_id: str) -> SecurityAwarenessTraining | None:
        """Get a single training by ID."""
        return self._trainings.get(training_id)

    def create_training(
        self,
        *,
        name: str,
        training_type: str,
        description: str = "",
        required_for_roles: list[str] | None = None,
        completion_deadline: datetime | None = None,
        total_assigned: int = 0,
    ) -> SecurityAwarenessTraining:
        """Create a new training program."""
        training = SecurityAwarenessTraining(
            id=f"train-{uuid4().hex[:8]}",
            name=name,
            training_type=training_type,
            description=description,
            required_for_roles=required_for_roles or [],
            completion_deadline=completion_deadline,
            total_assigned=total_assigned,
            total_completed=0,
            pass_rate=0.0,
            phishing_simulation_click_rate=None,
        )
        self._trainings[training.id] = training
        logger.info("Created training %s: %s", training.id, name)
        return training

    def update_training(
        self,
        training_id: str,
        *,
        total_completed: int | None = None,
        pass_rate: float | None = None,
        phishing_simulation_click_rate: float | None = None,
    ) -> SecurityAwarenessTraining | None:
        """Update training progress."""
        training = self._trainings.get(training_id)
        if training is None:
            return None
        data = training.model_dump()
        if total_completed is not None:
            data["total_completed"] = total_completed
        if pass_rate is not None:
            data["pass_rate"] = pass_rate
        if phishing_simulation_click_rate is not None:
            data["phishing_simulation_click_rate"] = phishing_simulation_click_rate
        updated = SecurityAwarenessTraining(**data)
        self._trainings[training_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_threat_metrics(self) -> ThreatMetrics:
        """Calculate aggregated threat intelligence metrics."""
        indicators = list(self._indicators.values())
        alerts = list(self._alerts.values())
        feeds = list(self._feeds.values())

        by_category: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        active_threats = 0
        mitre_set: set[str] = set()
        confidence_sum = 0.0

        for ind in indicators:
            cat = ind.threat_category.value
            by_category[cat] = by_category.get(cat, 0) + 1
            sev = ind.severity.value
            by_severity[sev] = by_severity.get(sev, 0) + 1
            if ind.status in (ThreatStatus.NEW, ThreatStatus.UNDER_INVESTIGATION):
                active_threats += 1
            mitre_set.update(ind.mitre_techniques)
            confidence_sum += ind.confidence_score

        mean_confidence = confidence_sum / len(indicators) if indicators else 0.0
        active_feeds = sum(1 for f in feeds if f.enabled)
        unack_alerts = sum(1 for a in alerts if not a.acknowledged)

        return ThreatMetrics(
            total_indicators=len(indicators),
            indicators_by_category=by_category,
            indicators_by_severity=by_severity,
            active_threats=active_threats,
            mitre_technique_coverage=sorted(mitre_set),
            active_feeds=active_feeds,
            total_feeds=len(feeds),
            unacknowledged_alerts=unack_alerts,
            total_alerts=len(alerts),
            mean_confidence_score=round(mean_confidence, 2),
        )

    def get_dlp_metrics(self) -> DLPMetrics:
        """Calculate aggregated DLP metrics."""
        policies = list(self._dlp_policies.values())
        violations = list(self._dlp_violations.values())

        active_policies = sum(1 for p in policies if p.enabled)
        total_violations_30d = sum(p.violation_count_30d for p in policies)

        by_channel: dict[str, int] = {}
        by_policy_type: dict[str, int] = {}
        blocked = 0
        logged = 0
        resolved = 0
        unresolved = 0

        for v in violations:
            ch = v.channel.value
            by_channel[ch] = by_channel.get(ch, 0) + 1
            # Find policy type
            policy = self._dlp_policies.get(v.policy_id)
            if policy:
                pt = policy.policy_type.value
                by_policy_type[pt] = by_policy_type.get(pt, 0) + 1
            if v.action_taken == DLPAction.BLOCK:
                blocked += 1
            elif v.action_taken == DLPAction.LOG_ONLY:
                logged += 1
            if v.resolved:
                resolved += 1
            else:
                unresolved += 1

        return DLPMetrics(
            total_policies=len(policies),
            active_policies=active_policies,
            total_violations_30d=total_violations_30d,
            violations_by_channel=by_channel,
            violations_by_policy_type=by_policy_type,
            blocked_count=blocked,
            logged_count=logged,
            resolved_count=resolved,
            unresolved_count=unresolved,
        )

    def get_training_compliance(self) -> TrainingComplianceRate:
        """Calculate training compliance rates."""
        trainings = list(self._trainings.values())
        if not trainings:
            return TrainingComplianceRate()

        now = datetime.now(timezone.utc)
        total_assigned = sum(t.total_assigned for t in trainings)
        total_completed = sum(t.total_completed for t in trainings)
        overall_completion = (total_completed / total_assigned * 100) if total_assigned > 0 else 0.0

        pass_rates = [t.pass_rate for t in trainings if t.pass_rate > 0]
        overall_pass = sum(pass_rates) / len(pass_rates) if pass_rates else 0.0

        phishing_rates = [
            t.phishing_simulation_click_rate for t in trainings
            if t.phishing_simulation_click_rate is not None
        ]
        avg_phishing = sum(phishing_rates) / len(phishing_rates) if phishing_rates else 0.0

        overdue = sum(
            1 for t in trainings
            if t.completion_deadline is not None
            and t.completion_deadline < now
            and t.total_completed < t.total_assigned
        )

        return TrainingComplianceRate(
            total_trainings=len(trainings),
            overall_completion_rate=round(overall_completion, 2),
            overall_pass_rate=round(overall_pass, 2),
            avg_phishing_click_rate=round(avg_phishing, 2),
            overdue_trainings=overdue,
        )


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------


def get_threat_intelligence_service() -> ThreatIntelligenceService:
    """Get or create the singleton service instance."""
    global _ti_service_instance
    if _ti_service_instance is None:
        with _ti_service_lock:
            if _ti_service_instance is None:
                _ti_service_instance = ThreatIntelligenceService()
    return _ti_service_instance


def reset_threat_intelligence_service() -> None:
    """Reset the singleton (primarily for testing)."""
    global _ti_service_instance
    with _ti_service_lock:
        _ti_service_instance = None
