"""SOC 2 Compliance Service for gap analysis and readiness tracking.

CISO-12: Maps SOC 2 Trust Services Criteria to platform controls,
tracks implementation status, manages evidence, and generates
gap analysis reports with prioritized remediation plans.

Usage:
    from app.services.soc2_service import get_soc2_service

    service = get_soc2_service()
    readiness = service.get_readiness_scores()
    report = service.generate_gap_report()
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from app.schemas.soc2_compliance import (
    CategoryGapSummary,
    CategoryReadiness,
    ControlStatus,
    EvidenceAttachment,
    EvidenceCreate,
    GapReport,
    ReadinessScore,
    RemediationItem,
    RemediationPlan,
    RemediationPriority,
    SOC2Control,
    SOC2ControlUpdate,
    TrustServiceCategory,
)

logger = logging.getLogger(__name__)

# Singleton instance and lock
_soc2_service_instance: SOC2ComplianceService | None = None
_soc2_service_lock = Lock()

# Human-readable category names
CATEGORY_NAMES: dict[TrustServiceCategory, str] = {
    TrustServiceCategory.CC: "Common Criteria (Security)",
    TrustServiceCategory.A: "Availability",
    TrustServiceCategory.PI: "Processing Integrity",
    TrustServiceCategory.C: "Confidentiality",
    TrustServiceCategory.P: "Privacy",
}

# Valid status transitions
VALID_STATUS_TRANSITIONS: dict[ControlStatus, list[ControlStatus]] = {
    ControlStatus.NOT_IMPLEMENTED: [
        ControlStatus.PARTIAL,
        ControlStatus.IMPLEMENTED,
        ControlStatus.NOT_APPLICABLE,
    ],
    ControlStatus.PARTIAL: [
        ControlStatus.IMPLEMENTED,
        ControlStatus.NOT_IMPLEMENTED,
    ],
    ControlStatus.IMPLEMENTED: [
        ControlStatus.PARTIAL,
    ],
    ControlStatus.NOT_APPLICABLE: [
        ControlStatus.NOT_IMPLEMENTED,
    ],
}


def _build_prepopulated_controls() -> list[SOC2Control]:
    """Build the pre-populated SOC 2 controls mapped to platform features.

    Returns 40+ controls across all 5 Trust Service Categories.
    """
    now = datetime.now(timezone.utc)

    controls: list[SOC2Control] = [
        # ===================================================================
        # CC - Common Criteria (Security) - 18 controls
        # ===================================================================
        SOC2Control(
            id="CC1.1",
            category=TrustServiceCategory.CC,
            criterion="CC1.1",
            title="Security Policy and Governance",
            description=(
                "The entity has defined organizational structures, reporting lines, "
                "authorities, and responsibilities for the design, development, "
                "implementation, operation, maintenance, and monitoring of the system."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="Security governance documentation and incident response plan",
            file_reference="docs/security/incident_response_plan.md",
            evidence=[],
            remediation_plan="",
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
        SOC2Control(
            id="CC1.2",
            category=TrustServiceCategory.CC,
            criterion="CC1.2",
            title="Board Oversight and Accountability",
            description=(
                "The board of directors demonstrates independence from management "
                "and exercises oversight of internal control."
            ),
            status=ControlStatus.PARTIAL,
            platform_control="Quality management and CAPA tracking",
            file_reference="app/services/capa_service.py",
            evidence=[],
            remediation_plan=(
                "Formalize board-level security committee charter and "
                "quarterly compliance review process."
            ),
            priority=RemediationPriority.P2,
            effort_hours=40,
            last_assessed=now,
        ),
        SOC2Control(
            id="CC1.3",
            category=TrustServiceCategory.CC,
            criterion="CC1.3",
            title="Management Philosophy and Operating Style",
            description=(
                "Management establishes, with board oversight, structures, "
                "reporting lines, and appropriate authorities and responsibilities."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="Quality management system with CAPA tracking",
            file_reference="app/services/capa_service.py",
            evidence=[],
            priority=RemediationPriority.P2,
            last_assessed=now,
        ),
        SOC2Control(
            id="CC2.1",
            category=TrustServiceCategory.CC,
            criterion="CC2.1",
            title="Information and Communication",
            description=(
                "The entity internally communicates information, including "
                "objectives and responsibilities for internal control."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="Observability dashboards and alerting",
            file_reference="app/services/observability_service.py",
            evidence=[],
            priority=RemediationPriority.P2,
            last_assessed=now,
        ),
        SOC2Control(
            id="CC2.2",
            category=TrustServiceCategory.CC,
            criterion="CC2.2",
            title="External Communication",
            description=(
                "The entity communicates with external parties regarding "
                "matters affecting the functioning of internal control."
            ),
            status=ControlStatus.PARTIAL,
            platform_control="Incident notification capabilities",
            file_reference="app/api/incidents.py",
            evidence=[],
            remediation_plan=(
                "Implement automated external breach notification system "
                "with configurable notification templates."
            ),
            priority=RemediationPriority.P2,
            effort_hours=24,
            last_assessed=now,
        ),
        SOC2Control(
            id="CC3.1",
            category=TrustServiceCategory.CC,
            criterion="CC3.1",
            title="Risk Assessment",
            description=(
                "The entity specifies objectives with sufficient clarity to enable "
                "the identification and assessment of risks."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="Risk scoring and threshold management",
            file_reference="app/services/risk_scoring.py",
            evidence=[],
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
        SOC2Control(
            id="CC3.2",
            category=TrustServiceCategory.CC,
            criterion="CC3.2",
            title="Risk Identification and Analysis",
            description=(
                "The entity identifies risks to the achievement of its objectives "
                "and analyzes risks as a basis for determining how the risks "
                "should be managed."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="Prediction audit and model drift detection",
            file_reference="app/api/prediction_audit.py",
            evidence=[],
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
        SOC2Control(
            id="CC3.3",
            category=TrustServiceCategory.CC,
            criterion="CC3.3",
            title="Fraud Risk Assessment",
            description=(
                "The entity considers the potential for fraud in assessing "
                "risks to the achievement of objectives."
            ),
            status=ControlStatus.PARTIAL,
            platform_control="Audit logging and suspicious access detection",
            file_reference="app/services/data_use_agreement_service.py",
            evidence=[],
            remediation_plan=(
                "Add explicit fraud risk assessment procedures and "
                "automated anomaly detection for user behavior."
            ),
            priority=RemediationPriority.P2,
            effort_hours=32,
            last_assessed=now,
        ),
        SOC2Control(
            id="CC4.1",
            category=TrustServiceCategory.CC,
            criterion="CC4.1",
            title="Monitoring Activities",
            description=(
                "The entity selects, develops, and performs ongoing and/or "
                "separate evaluations to ascertain whether the components "
                "of internal control are present and functioning."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="SLI collection and observability dashboards",
            file_reference="app/api/middleware/sli_collector.py",
            evidence=[],
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
        SOC2Control(
            id="CC5.1",
            category=TrustServiceCategory.CC,
            criterion="CC5.1",
            title="Logical and Physical Access Controls",
            description=(
                "The entity selects and develops control activities that "
                "contribute to the mitigation of risks. Includes RBAC, "
                "authentication, and authorization."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="RBAC permissions system with role-based access",
            file_reference="app/core/permissions.py",
            evidence=[],
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
        SOC2Control(
            id="CC5.2",
            category=TrustServiceCategory.CC,
            criterion="CC5.2",
            title="Technology General Controls",
            description=(
                "The entity also selects and develops general control "
                "activities over technology to support the achievement "
                "of objectives."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="Security headers middleware and rate limiting",
            file_reference="app/api/middleware/security_headers.py",
            evidence=[],
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
        SOC2Control(
            id="CC5.3",
            category=TrustServiceCategory.CC,
            criterion="CC5.3",
            title="Policy Deployment",
            description=(
                "The entity deploys control activities through policies "
                "that establish what is expected and procedures that put "
                "policies into action."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="Policy management and enforcement",
            file_reference="app/api/policy.py",
            evidence=[],
            priority=RemediationPriority.P2,
            last_assessed=now,
        ),
        SOC2Control(
            id="CC6.1",
            category=TrustServiceCategory.CC,
            criterion="CC6.1",
            title="Change Management",
            description=(
                "The entity implements logical access security measures "
                "to protect against threats from sources outside its "
                "system boundaries, including change management."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="CI/CD security workflows and pipeline versioning",
            file_reference=".github/workflows/security.yml",
            evidence=[],
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
        SOC2Control(
            id="CC6.2",
            category=TrustServiceCategory.CC,
            criterion="CC6.2",
            title="User Access Management",
            description=(
                "Prior to issuing system credentials and granting system "
                "access, the entity registers and authorizes new internal "
                "and external users."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="User registration, authentication, and session management",
            file_reference="app/api/auth.py",
            evidence=[],
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
        SOC2Control(
            id="CC6.3",
            category=TrustServiceCategory.CC,
            criterion="CC6.3",
            title="Authentication Mechanisms",
            description=(
                "The entity authorizes, modifies, or removes access to "
                "data, software, functions, and other protected information "
                "assets based on roles."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="JWT authentication with session management",
            file_reference="app/api/auth_sessions.py",
            evidence=[],
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
        SOC2Control(
            id="CC7.1",
            category=TrustServiceCategory.CC,
            criterion="CC7.1",
            title="System Monitoring",
            description=(
                "To meet its objectives, the entity uses detection and "
                "monitoring procedures to identify changes to configurations "
                "that result in the introduction of new vulnerabilities."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="Observability service with metrics, tracing, and alerting",
            file_reference="app/services/observability_service.py",
            evidence=[],
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
        SOC2Control(
            id="CC7.2",
            category=TrustServiceCategory.CC,
            criterion="CC7.2",
            title="Incident Detection and Response",
            description=(
                "The entity monitors system components and operations "
                "to detect anomalies indicative of security incidents."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="Incident management with runbooks",
            file_reference="app/api/incidents.py",
            evidence=[],
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
        SOC2Control(
            id="CC8.1",
            category=TrustServiceCategory.CC,
            criterion="CC8.1",
            title="Incident Response Procedures",
            description=(
                "The entity has defined incident response procedures "
                "including escalation paths and communication plans."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="Incident response plan with PHI breach, unauthorized access, and outage runbooks",
            file_reference="docs/security/incident_runbooks/",
            evidence=[],
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
        # ===================================================================
        # A - Availability - 5 controls
        # ===================================================================
        SOC2Control(
            id="A1.1",
            category=TrustServiceCategory.A,
            criterion="A1.1",
            title="Availability Policy and Objectives",
            description=(
                "The entity maintains, monitors, and evaluates current "
                "processing capacity and use of system components to "
                "manage capacity demand and enable the implementation "
                "of additional capacity."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="Disaster recovery plan and capacity planning documentation",
            file_reference="docs/operations/disaster_recovery_plan.md",
            evidence=[],
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
        SOC2Control(
            id="A1.2",
            category=TrustServiceCategory.A,
            criterion="A1.2",
            title="Backup and Recovery",
            description=(
                "The entity authorizes, designs, develops or acquires, "
                "implements, operates, approves, maintains, and monitors "
                "environmental protections and backup/recovery procedures."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="Backup verification service with automated integrity checks",
            file_reference="app/services/backup_verification_service.py",
            evidence=[],
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
        SOC2Control(
            id="A1.3",
            category=TrustServiceCategory.A,
            criterion="A1.3",
            title="Recovery Testing",
            description=(
                "The entity tests recovery plan procedures supporting "
                "system recovery to meet its objectives."
            ),
            status=ControlStatus.PARTIAL,
            platform_control="Backup status API provides verification",
            file_reference="app/api/backup_status.py",
            evidence=[],
            remediation_plan=(
                "Implement automated quarterly DR testing with "
                "documented results and RTO/RPO validation."
            ),
            priority=RemediationPriority.P2,
            effort_hours=40,
            last_assessed=now,
        ),
        SOC2Control(
            id="A1.4",
            category=TrustServiceCategory.A,
            criterion="A1.4",
            title="Capacity Planning",
            description=(
                "The entity monitors and evaluates current processing "
                "capacity to manage capacity and enable implementation "
                "of additional capacity as needed."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="Capacity planning documentation and observability metrics",
            file_reference="docs/operations/capacity_planning.md",
            evidence=[],
            priority=RemediationPriority.P2,
            last_assessed=now,
        ),
        SOC2Control(
            id="A1.5",
            category=TrustServiceCategory.A,
            criterion="A1.5",
            title="Environmental Protection",
            description=(
                "The entity identifies environmental threats that could "
                "impair system availability and implements protections."
            ),
            status=ControlStatus.NOT_IMPLEMENTED,
            platform_control="",
            file_reference="",
            evidence=[],
            remediation_plan=(
                "Document cloud infrastructure environmental controls "
                "(multi-AZ deployment, auto-scaling policies, health checks)."
            ),
            priority=RemediationPriority.P3,
            effort_hours=16,
            last_assessed=now,
        ),
        # ===================================================================
        # PI - Processing Integrity - 7 controls
        # ===================================================================
        SOC2Control(
            id="PI1.1",
            category=TrustServiceCategory.PI,
            criterion="PI1.1",
            title="Data Validation at Input",
            description=(
                "The entity implements policies and procedures over "
                "system inputs to ensure completeness, accuracy, and "
                "validity of data."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="FHIR validation, OMOP mapping, and Pydantic schema validation",
            file_reference="app/api/fhir_validation.py",
            evidence=[],
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
        SOC2Control(
            id="PI1.2",
            category=TrustServiceCategory.PI,
            criterion="PI1.2",
            title="Processing Completeness",
            description=(
                "The entity implements system processing to ensure "
                "completeness, accuracy, and timeliness of data."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="ETL validation and data completeness checks",
            file_reference="app/api/etl_validation.py",
            evidence=[],
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
        SOC2Control(
            id="PI1.3",
            category=TrustServiceCategory.PI,
            criterion="PI1.3",
            title="Output Validation",
            description=(
                "The entity implements policies and procedures over "
                "system outputs to ensure they are complete, accurate, "
                "and distributed only to intended parties."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="Data quality DQD checks and mapping quality validation",
            file_reference="app/api/data_quality_dqd.py",
            evidence=[],
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
        SOC2Control(
            id="PI1.4",
            category=TrustServiceCategory.PI,
            criterion="PI1.4",
            title="Error Handling",
            description=(
                "The entity implements procedures to detect and handle "
                "errors during processing."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="Error handler middleware with structured error responses",
            file_reference="app/api/middleware/error_handler.py",
            evidence=[],
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
        SOC2Control(
            id="PI1.5",
            category=TrustServiceCategory.PI,
            criterion="PI1.5",
            title="Data Lineage and Traceability",
            description=(
                "The entity maintains records of system inputs and "
                "outputs to support traceability of data processing."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="Data lineage tracking service",
            file_reference="app/api/lineage.py",
            evidence=[],
            priority=RemediationPriority.P2,
            last_assessed=now,
        ),
        SOC2Control(
            id="PI1.6",
            category=TrustServiceCategory.PI,
            criterion="PI1.6",
            title="Data Consistency Checks",
            description=(
                "The entity performs data consistency and reconciliation "
                "checks to ensure processing integrity."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="Data consistency and reconciliation services",
            file_reference="app/api/data_consistency.py",
            evidence=[],
            priority=RemediationPriority.P2,
            last_assessed=now,
        ),
        SOC2Control(
            id="PI1.7",
            category=TrustServiceCategory.PI,
            criterion="PI1.7",
            title="Audit Trail for Processing",
            description=(
                "The entity maintains audit trails for data processing "
                "activities to support investigation and accountability."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="Audit middleware with comprehensive logging",
            file_reference="app/api/middleware/audit.py",
            evidence=[],
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
        # ===================================================================
        # C - Confidentiality - 7 controls
        # ===================================================================
        SOC2Control(
            id="C1.1",
            category=TrustServiceCategory.C,
            criterion="C1.1",
            title="Data Classification",
            description=(
                "The entity identifies and maintains confidential "
                "information to meet its objectives."
            ),
            status=ControlStatus.PARTIAL,
            platform_control="Data governance with data categories (PHI, de-identified, etc.)",
            file_reference="app/schemas/data_governance.py",
            evidence=[],
            remediation_plan=(
                "Implement formal data classification policy with "
                "automated tagging for PHI and confidential data."
            ),
            priority=RemediationPriority.P1,
            effort_hours=24,
            last_assessed=now,
        ),
        SOC2Control(
            id="C1.2",
            category=TrustServiceCategory.C,
            criterion="C1.2",
            title="Encryption at Rest",
            description=(
                "The entity uses encryption to protect confidential "
                "information at rest."
            ),
            status=ControlStatus.NOT_IMPLEMENTED,
            platform_control="",
            file_reference="",
            evidence=[],
            remediation_plan=(
                "Enable PostgreSQL TDE or disk-level encryption. "
                "Configure AES-256 for all data stores containing PHI. "
                "Document encryption key management procedures."
            ),
            priority=RemediationPriority.P1,
            effort_hours=40,
            last_assessed=now,
        ),
        SOC2Control(
            id="C1.3",
            category=TrustServiceCategory.C,
            criterion="CC6.7",
            title="Encryption in Transit",
            description=(
                "The entity uses encryption to protect confidential "
                "information during transmission."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="TLS configuration in nginx and security headers",
            file_reference="nginx/",
            evidence=[],
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
        SOC2Control(
            id="C1.4",
            category=TrustServiceCategory.C,
            criterion="C1.4",
            title="Access Restrictions for Confidential Data",
            description=(
                "The entity restricts access to confidential information "
                "to authorized personnel with a need to know."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="RBAC with granular permissions and DUA enforcement",
            file_reference="app/core/permissions.py",
            evidence=[],
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
        SOC2Control(
            id="C1.5",
            category=TrustServiceCategory.C,
            criterion="C1.5",
            title="Confidential Data Disposal",
            description=(
                "The entity disposes of confidential information in "
                "accordance with its data retention policies."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="Deletion service with certified data disposal",
            file_reference="app/services/deletion_service.py",
            evidence=[],
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
        SOC2Control(
            id="C1.6",
            category=TrustServiceCategory.C,
            criterion="C1.6",
            title="Secret Management",
            description=(
                "The entity manages secrets, API keys, and credentials "
                "with automated rotation and secure storage."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="Secret rotation service with automated key management",
            file_reference="app/services/secret_rotation_service.py",
            evidence=[],
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
        SOC2Control(
            id="C1.7",
            category=TrustServiceCategory.C,
            criterion="C1.7",
            title="Data Use Agreement Enforcement",
            description=(
                "The entity enforces data use agreements to control "
                "access to confidential information."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="DUA management with compliance checking",
            file_reference="app/services/data_use_agreement_service.py",
            evidence=[],
            priority=RemediationPriority.P2,
            last_assessed=now,
        ),
        # ===================================================================
        # P - Privacy - 8 controls
        # ===================================================================
        SOC2Control(
            id="P1.1",
            category=TrustServiceCategory.P,
            criterion="P1.1",
            title="Privacy Notice",
            description=(
                "The entity provides notice to data subjects about its "
                "privacy practices including types of data collected, "
                "how data is used, and with whom data is shared."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="Right-to-deletion policy and consent management",
            file_reference="docs/legal/right_to_deletion_policy.md",
            evidence=[],
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
        SOC2Control(
            id="P2.1",
            category=TrustServiceCategory.P,
            criterion="P2.1",
            title="Consent Management",
            description=(
                "The entity obtains and manages consent for the "
                "collection, use, and disclosure of personal information."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="Consent management API and documentation",
            file_reference="app/api/consent.py",
            evidence=[],
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
        SOC2Control(
            id="P3.1",
            category=TrustServiceCategory.P,
            criterion="P3.1",
            title="Data Collection Limitation",
            description=(
                "Personal information is collected consistent with "
                "the entity's objectives related to privacy."
            ),
            status=ControlStatus.PARTIAL,
            platform_control="FHIR data import with resource filtering",
            file_reference="app/api/fhir.py",
            evidence=[],
            remediation_plan=(
                "Document data minimization procedures for each data "
                "collection point. Implement automated PII scanning "
                "to detect unnecessary data collection."
            ),
            priority=RemediationPriority.P2,
            effort_hours=24,
            last_assessed=now,
        ),
        SOC2Control(
            id="P4.1",
            category=TrustServiceCategory.P,
            criterion="P4.1",
            title="Data Retention and Deletion",
            description=(
                "The entity limits the retention of personal information "
                "to that which is necessary and provides deletion rights."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="Deletion service with right-to-deletion workflow",
            file_reference="app/services/deletion_service.py",
            evidence=[],
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
        SOC2Control(
            id="P5.1",
            category=TrustServiceCategory.P,
            criterion="P5.1",
            title="Data Access Rights",
            description=(
                "The entity grants data subjects access to their "
                "personal information for review and update."
            ),
            status=ControlStatus.PARTIAL,
            platform_control="Patient data access API",
            file_reference="app/api/patients.py",
            evidence=[],
            remediation_plan=(
                "Implement self-service data export endpoint that "
                "generates complete patient data package in standard "
                "format (FHIR Bundle)."
            ),
            priority=RemediationPriority.P2,
            effort_hours=32,
            last_assessed=now,
        ),
        SOC2Control(
            id="P6.1",
            category=TrustServiceCategory.P,
            criterion="P6.1",
            title="Data Disclosure and Sharing",
            description=(
                "The entity discloses personal information to third "
                "parties only for the purposes identified in the "
                "privacy notice and with the consent of data subjects."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="DUA enforcement and access logging",
            file_reference="app/services/data_use_agreement_service.py",
            evidence=[],
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
        SOC2Control(
            id="P7.1",
            category=TrustServiceCategory.P,
            criterion="P7.1",
            title="Data Quality and Accuracy",
            description=(
                "The entity collects and maintains accurate, up-to-date, "
                "complete, and relevant personal information."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="Data quality checks, validation, and reconciliation",
            file_reference="app/api/data_quality_dqd.py",
            evidence=[],
            priority=RemediationPriority.P2,
            last_assessed=now,
        ),
        SOC2Control(
            id="P8.1",
            category=TrustServiceCategory.P,
            criterion="P8.1",
            title="Privacy Incident Management",
            description=(
                "The entity monitors for and responds to privacy "
                "incidents including unauthorized access to personal "
                "information."
            ),
            status=ControlStatus.IMPLEMENTED,
            platform_control="Incident management with PHI breach runbook",
            file_reference="docs/security/incident_runbooks/runbook_phi_breach.md",
            evidence=[],
            priority=RemediationPriority.P1,
            last_assessed=now,
        ),
    ]

    return controls


class SOC2ComplianceService:
    """Service for SOC 2 compliance gap analysis and readiness tracking.

    Maintains a registry of SOC 2 controls mapped to platform features,
    tracks implementation status, manages evidence attachments, and
    generates gap analysis reports with prioritized remediation plans.
    """

    def __init__(self) -> None:
        """Initialize with pre-populated controls."""
        self._controls: dict[str, SOC2Control] = {}
        self._evidence: dict[str, list[EvidenceAttachment]] = {}
        self._load_prepopulated_controls()
        logger.info(
            "SOC2ComplianceService initialized with %d controls",
            len(self._controls),
        )

    def _load_prepopulated_controls(self) -> None:
        """Load pre-populated SOC 2 controls."""
        for control in _build_prepopulated_controls():
            self._controls[control.id] = control
            self._evidence[control.id] = list(control.evidence)

    # ------------------------------------------------------------------
    # Control CRUD
    # ------------------------------------------------------------------

    def get_all_controls(
        self,
        category: TrustServiceCategory | None = None,
        status: ControlStatus | None = None,
    ) -> list[SOC2Control]:
        """Get all controls, optionally filtered by category and/or status."""
        controls = list(self._controls.values())
        if category is not None:
            controls = [c for c in controls if c.category == category]
        if status is not None:
            controls = [c for c in controls if c.status == status]
        return sorted(controls, key=lambda c: c.id)

    def get_control(self, control_id: str) -> SOC2Control | None:
        """Get a single control by ID."""
        return self._controls.get(control_id)

    def update_control(
        self, control_id: str, update: SOC2ControlUpdate
    ) -> SOC2Control | None:
        """Update a control's status, evidence, or remediation plan.

        Validates status transitions:
        - NOT_IMPLEMENTED -> PARTIAL, IMPLEMENTED, NOT_APPLICABLE
        - PARTIAL -> IMPLEMENTED, NOT_IMPLEMENTED
        - IMPLEMENTED -> PARTIAL
        - NOT_APPLICABLE -> NOT_IMPLEMENTED

        Returns the updated control or None if not found.
        """
        control = self._controls.get(control_id)
        if control is None:
            return None

        # Validate status transition if status is being changed
        if update.status is not None and update.status != control.status:
            valid_targets = VALID_STATUS_TRANSITIONS.get(control.status, [])
            if update.status not in valid_targets:
                raise ValueError(
                    f"Invalid status transition from {control.status.value} "
                    f"to {update.status.value}. Valid transitions: "
                    f"{[s.value for s in valid_targets]}"
                )

        # Apply updates
        update_data = update.model_dump(exclude_none=True)
        control_data = control.model_dump()
        control_data.update(update_data)
        control_data["last_assessed"] = datetime.now(timezone.utc)

        # Preserve evidence list
        control_data["evidence"] = self._evidence.get(control_id, [])

        updated = SOC2Control(**control_data)
        self._controls[control_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Evidence management
    # ------------------------------------------------------------------

    def attach_evidence(self, evidence_create: EvidenceCreate) -> EvidenceAttachment:
        """Attach evidence to a control.

        Raises ValueError if control_id not found.
        """
        control = self._controls.get(evidence_create.control_id)
        if control is None:
            raise ValueError(
                f"Control {evidence_create.control_id} not found"
            )

        attachment = EvidenceAttachment(
            id=f"EVD-{uuid4().hex[:8].upper()}",
            control_id=evidence_create.control_id,
            evidence_type=evidence_create.evidence_type,
            title=evidence_create.title,
            description=evidence_create.description,
            file_reference=evidence_create.file_reference,
            collected_at=datetime.now(timezone.utc),
            collected_by="system",
        )

        if evidence_create.control_id not in self._evidence:
            self._evidence[evidence_create.control_id] = []
        self._evidence[evidence_create.control_id].append(attachment)

        # Update the control's evidence list
        control_data = control.model_dump()
        control_data["evidence"] = [
            e.model_dump() for e in self._evidence[evidence_create.control_id]
        ]
        self._controls[evidence_create.control_id] = SOC2Control(**control_data)

        return attachment

    def get_evidence(self, control_id: str) -> list[EvidenceAttachment]:
        """Get all evidence for a control."""
        return self._evidence.get(control_id, [])

    # ------------------------------------------------------------------
    # Readiness scoring
    # ------------------------------------------------------------------

    def get_readiness_scores(self) -> ReadinessScore:
        """Calculate readiness scores per category and overall."""
        category_scores: list[CategoryReadiness] = []
        total_impl = 0
        total_partial = 0
        total_not_impl = 0
        total_na = 0

        for category in TrustServiceCategory:
            controls = self.get_all_controls(category=category)
            impl = sum(1 for c in controls if c.status == ControlStatus.IMPLEMENTED)
            partial = sum(1 for c in controls if c.status == ControlStatus.PARTIAL)
            not_impl = sum(
                1 for c in controls if c.status == ControlStatus.NOT_IMPLEMENTED
            )
            na = sum(
                1 for c in controls if c.status == ControlStatus.NOT_APPLICABLE
            )

            # Readiness = (implemented + 0.5 * partial) / (total - not_applicable)
            applicable = len(controls) - na
            if applicable > 0:
                readiness = ((impl + 0.5 * partial) / applicable) * 100.0
            else:
                readiness = 100.0

            category_scores.append(
                CategoryReadiness(
                    category=category,
                    category_name=CATEGORY_NAMES[category],
                    total_controls=len(controls),
                    implemented=impl,
                    partial=partial,
                    not_implemented=not_impl,
                    not_applicable=na,
                    readiness_percentage=round(readiness, 1),
                )
            )

            total_impl += impl
            total_partial += partial
            total_not_impl += not_impl
            total_na += na

        total = len(self._controls)
        total_applicable = total - total_na
        if total_applicable > 0:
            overall = ((total_impl + 0.5 * total_partial) / total_applicable) * 100.0
        else:
            overall = 100.0

        return ReadinessScore(
            overall_percentage=round(overall, 1),
            categories=category_scores,
            total_controls=total,
            total_implemented=total_impl,
            total_partial=total_partial,
            total_not_implemented=total_not_impl,
            total_not_applicable=total_na,
            assessed_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Remediation planning
    # ------------------------------------------------------------------

    def get_remediation_plan(self) -> RemediationPlan:
        """Generate prioritized remediation plan for all gaps."""
        items: list[RemediationItem] = []

        for control in self._controls.values():
            if control.status in (
                ControlStatus.NOT_IMPLEMENTED,
                ControlStatus.PARTIAL,
            ):
                items.append(
                    RemediationItem(
                        control_id=control.id,
                        category=control.category,
                        title=control.title,
                        current_status=control.status,
                        priority=control.priority,
                        remediation_plan=control.remediation_plan or "Plan not yet defined",
                        effort_hours=control.effort_hours,
                    )
                )

        # Sort by priority (P1 first), then by control ID
        priority_order = {
            RemediationPriority.P1: 0,
            RemediationPriority.P2: 1,
            RemediationPriority.P3: 2,
        }
        items.sort(key=lambda i: (priority_order[i.priority], i.control_id))

        return RemediationPlan(
            total_items=len(items),
            p1_items=sum(1 for i in items if i.priority == RemediationPriority.P1),
            p2_items=sum(1 for i in items if i.priority == RemediationPriority.P2),
            p3_items=sum(1 for i in items if i.priority == RemediationPriority.P3),
            total_effort_hours=sum(i.effort_hours for i in items),
            items=items,
            generated_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Gap report generation
    # ------------------------------------------------------------------

    def generate_gap_report(self) -> GapReport:
        """Generate comprehensive SOC 2 gap analysis report."""
        readiness = self.get_readiness_scores()
        remediation = self.get_remediation_plan()

        category_analysis: list[CategoryGapSummary] = []
        for category in TrustServiceCategory:
            controls = self.get_all_controls(category=category)
            gaps = [
                c
                for c in controls
                if c.status
                in (ControlStatus.NOT_IMPLEMENTED, ControlStatus.PARTIAL)
            ]
            implemented = [
                c for c in controls if c.status == ControlStatus.IMPLEMENTED
            ]

            # Find matching readiness
            cat_readiness = next(
                (cr for cr in readiness.categories if cr.category == category),
                None,
            )
            pct = cat_readiness.readiness_percentage if cat_readiness else 0.0

            category_analysis.append(
                CategoryGapSummary(
                    category=category,
                    category_name=CATEGORY_NAMES[category],
                    readiness_percentage=pct,
                    controls=controls,
                    gaps=gaps,
                    implemented_controls=implemented,
                )
            )

        # Build executive summary
        total = readiness.total_controls
        impl = readiness.total_implemented
        gaps_count = readiness.total_not_implemented + readiness.total_partial
        p1_count = remediation.p1_items

        executive_summary = (
            f"SOC 2 Type II Gap Analysis: {readiness.overall_percentage}% "
            f"overall readiness. {impl} of {total} controls fully implemented, "
            f"{gaps_count} controls require remediation "
            f"({p1_count} are P1 audit blockers). "
            f"Estimated total remediation effort: {remediation.total_effort_hours} hours."
        )

        return GapReport(
            report_id=f"SOC2-GAP-{uuid4().hex[:8].upper()}",
            executive_summary=executive_summary,
            overall_readiness=readiness,
            category_analysis=category_analysis,
            remediation_plan=remediation,
            generated_at=datetime.now(timezone.utc),
        )


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------


def get_soc2_service() -> SOC2ComplianceService:
    """Get or create the singleton SOC2ComplianceService."""
    global _soc2_service_instance
    if _soc2_service_instance is None:
        with _soc2_service_lock:
            if _soc2_service_instance is None:
                _soc2_service_instance = SOC2ComplianceService()
    return _soc2_service_instance


def reset_soc2_service() -> None:
    """Reset the singleton (for testing)."""
    global _soc2_service_instance
    with _soc2_service_lock:
        _soc2_service_instance = None
