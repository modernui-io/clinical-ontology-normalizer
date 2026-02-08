"""HITRUST CSF v11 Compliance Service for certification roadmap tracking.

CISO-13: Maps HITRUST CSF v11 control categories to platform controls,
tracks maturity levels, manages evidence, and generates certification
roadmaps with phased remediation plans.

Usage:
    from app.services.hitrust_service import get_hitrust_service

    service = get_hitrust_service()
    readiness = service.get_readiness_scores()
    roadmap = service.generate_roadmap()
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from app.schemas.hitrust_compliance import (
    CategoryReadiness,
    CategorySummary,
    CertificationRoadmap,
    EvidenceAttachment,
    EvidenceCreate,
    HITRUSTCategory,
    HITRUSTControl,
    HITRUSTControlUpdate,
    MaturityLevel,
    ReadinessScore,
    RoadmapItem,
    RoadmapPhase,
    RoadmapPhaseDetail,
)

logger = logging.getLogger(__name__)

# Singleton instance and lock
_hitrust_service_instance: HITRUSTComplianceService | None = None
_hitrust_service_lock = Lock()

# Human-readable category names
CATEGORY_NAMES: dict[HITRUSTCategory, str] = {
    HITRUSTCategory.INFORMATION_SECURITY_MANAGEMENT: "Information Security Management Program",
    HITRUSTCategory.ACCESS_CONTROL: "Access Control",
    HITRUSTCategory.HUMAN_RESOURCES_SECURITY: "Human Resources Security",
    HITRUSTCategory.RISK_MANAGEMENT: "Risk Management",
    HITRUSTCategory.SECURITY_POLICY: "Security Policy",
    HITRUSTCategory.ORGANIZATION_OF_INFORMATION_SECURITY: "Organization of Information Security",
    HITRUSTCategory.COMPLIANCE: "Compliance",
    HITRUSTCategory.ASSET_MANAGEMENT: "Asset Management",
    HITRUSTCategory.PHYSICAL_AND_ENVIRONMENTAL_SECURITY: "Physical and Environmental Security",
    HITRUSTCategory.COMMUNICATIONS_AND_OPERATIONS_MANAGEMENT: "Communications and Operations Management",
    HITRUSTCategory.INFORMATION_SYSTEMS_ACQUISITION_DEVELOPMENT_MAINTENANCE: "Information Systems Acquisition, Development, and Maintenance",
    HITRUSTCategory.INFORMATION_SECURITY_INCIDENT_MANAGEMENT: "Information Security Incident Management",
    HITRUSTCategory.BUSINESS_CONTINUITY_MANAGEMENT: "Business Continuity Management",
    HITRUSTCategory.PRIVACY_PRACTICES: "Privacy Practices",
}

# Maturity level numeric scores (for averaging)
MATURITY_SCORES: dict[MaturityLevel, int] = {
    MaturityLevel.NOT_STARTED: 0,
    MaturityLevel.POLICY: 1,
    MaturityLevel.PROCEDURE: 2,
    MaturityLevel.IMPLEMENTED: 3,
    MaturityLevel.MEASURED: 4,
    MaturityLevel.MANAGED: 5,
}

# Valid maturity level transitions (must advance or regress by at most one level)
VALID_MATURITY_TRANSITIONS: dict[MaturityLevel, list[MaturityLevel]] = {
    MaturityLevel.NOT_STARTED: [MaturityLevel.POLICY],
    MaturityLevel.POLICY: [MaturityLevel.NOT_STARTED, MaturityLevel.PROCEDURE],
    MaturityLevel.PROCEDURE: [MaturityLevel.POLICY, MaturityLevel.IMPLEMENTED],
    MaturityLevel.IMPLEMENTED: [MaturityLevel.PROCEDURE, MaturityLevel.MEASURED],
    MaturityLevel.MEASURED: [MaturityLevel.IMPLEMENTED, MaturityLevel.MANAGED],
    MaturityLevel.MANAGED: [MaturityLevel.MEASURED],
}

# Roadmap phase names and descriptions
PHASE_INFO: dict[RoadmapPhase, dict[str, str]] = {
    RoadmapPhase.PHASE_1: {
        "name": "Quick Wins",
        "description": (
            "Address low-effort, high-impact controls that can be "
            "completed rapidly to establish baseline compliance."
        ),
    },
    RoadmapPhase.PHASE_2: {
        "name": "Foundational Controls",
        "description": (
            "Implement core security controls required for HITRUST "
            "certification including access control, risk management, "
            "and security policy frameworks."
        ),
    },
    RoadmapPhase.PHASE_3: {
        "name": "Advanced Controls",
        "description": (
            "Deploy advanced controls including continuous monitoring, "
            "incident response maturation, and privacy practice "
            "enhancements."
        ),
    },
    RoadmapPhase.PHASE_4: {
        "name": "Certification Readiness",
        "description": (
            "Final preparation for HITRUST certification including "
            "evidence collection, internal audit, and assessor "
            "preparation."
        ),
    },
}

# Estimated weeks per phase
PHASE_DURATION_WEEKS: dict[RoadmapPhase, int] = {
    RoadmapPhase.PHASE_1: 4,
    RoadmapPhase.PHASE_2: 12,
    RoadmapPhase.PHASE_3: 10,
    RoadmapPhase.PHASE_4: 6,
}


def _build_prepopulated_controls() -> list[HITRUSTControl]:
    """Build the pre-populated HITRUST CSF v11 controls mapped to platform features.

    Returns 50+ controls across all 14 categories.
    """
    now = datetime.now(timezone.utc)

    controls: list[HITRUSTControl] = [
        # ===================================================================
        # Category 0: Information Security Management Program (4 controls)
        # ===================================================================
        HITRUSTControl(
            id="00.a",
            category=HITRUSTCategory.INFORMATION_SECURITY_MANAGEMENT,
            title="Information Security Management Program",
            description=(
                "A formal information security management program has been "
                "established and is maintained to provide governance, oversight, "
                "and direction for information security activities."
            ),
            maturity_level=MaturityLevel.IMPLEMENTED,
            platform_control="Security governance with incident response plan and runbooks",
            file_reference="docs/security/incident_response_plan.md",
            roadmap_phase=RoadmapPhase.PHASE_1,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="00.b",
            category=HITRUSTCategory.INFORMATION_SECURITY_MANAGEMENT,
            title="Information Security Roles and Responsibilities",
            description=(
                "Information security roles and responsibilities are defined "
                "and assigned to ensure accountability for security activities."
            ),
            maturity_level=MaturityLevel.POLICY,
            platform_control="RBAC system with defined roles",
            file_reference="app/core/permissions.py",
            gap_description="Roles documented in code but formal RACI matrix not published",
            remediation_plan=(
                "Create formal RACI matrix for security roles. "
                "Publish security responsibility assignments."
            ),
            roadmap_phase=RoadmapPhase.PHASE_1,
            effort_hours=16,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="00.c",
            category=HITRUSTCategory.INFORMATION_SECURITY_MANAGEMENT,
            title="Security Program Review",
            description=(
                "The information security program is reviewed at planned "
                "intervals or when significant changes occur."
            ),
            maturity_level=MaturityLevel.NOT_STARTED,
            gap_description="No formal periodic review process for security program",
            remediation_plan=(
                "Establish quarterly security program review process. "
                "Define review criteria and reporting templates."
            ),
            roadmap_phase=RoadmapPhase.PHASE_3,
            effort_hours=24,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="00.d",
            category=HITRUSTCategory.INFORMATION_SECURITY_MANAGEMENT,
            title="Security Metrics and Reporting",
            description=(
                "Security metrics are collected, analyzed, and reported "
                "to management to support decision-making."
            ),
            maturity_level=MaturityLevel.IMPLEMENTED,
            platform_control="Observability service with metrics collection and SLI tracking",
            file_reference="app/services/observability_service.py",
            roadmap_phase=RoadmapPhase.PHASE_1,
            last_assessed=now,
        ),
        # ===================================================================
        # Category 1: Access Control (6 controls)
        # ===================================================================
        HITRUSTControl(
            id="01.a",
            category=HITRUSTCategory.ACCESS_CONTROL,
            title="Access Control Policy",
            description=(
                "An access control policy is established, documented, and "
                "reviewed based on business and security requirements."
            ),
            maturity_level=MaturityLevel.IMPLEMENTED,
            platform_control="RBAC system with role-based permissions",
            file_reference="app/core/permissions.py",
            roadmap_phase=RoadmapPhase.PHASE_1,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="01.b",
            category=HITRUSTCategory.ACCESS_CONTROL,
            title="User Registration and De-registration",
            description=(
                "A formal user registration and de-registration process "
                "is implemented for granting and revoking access."
            ),
            maturity_level=MaturityLevel.IMPLEMENTED,
            platform_control="User management with registration and authentication",
            file_reference="app/api/auth.py",
            roadmap_phase=RoadmapPhase.PHASE_1,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="01.c",
            category=HITRUSTCategory.ACCESS_CONTROL,
            title="Privilege Management",
            description=(
                "The allocation and use of privileged access rights "
                "is restricted and controlled."
            ),
            maturity_level=MaturityLevel.IMPLEMENTED,
            platform_control="Admin role enforcement and permission checking middleware",
            file_reference="app/api/middleware/auth.py",
            roadmap_phase=RoadmapPhase.PHASE_1,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="01.d",
            category=HITRUSTCategory.ACCESS_CONTROL,
            title="Session Management",
            description=(
                "User sessions are managed with appropriate timeout and "
                "termination controls."
            ),
            maturity_level=MaturityLevel.IMPLEMENTED,
            platform_control="Session management with token expiry and revocation",
            file_reference="app/api/auth_sessions.py",
            roadmap_phase=RoadmapPhase.PHASE_1,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="01.e",
            category=HITRUSTCategory.ACCESS_CONTROL,
            title="Password Policy",
            description=(
                "Password management controls enforce complexity, history, "
                "and rotation requirements."
            ),
            maturity_level=MaturityLevel.PROCEDURE,
            platform_control="Authentication system with password hashing",
            file_reference="app/api/auth.py",
            gap_description="Password complexity rules exist but rotation not enforced",
            remediation_plan=(
                "Implement password rotation enforcement. "
                "Add password history tracking to prevent reuse."
            ),
            roadmap_phase=RoadmapPhase.PHASE_2,
            effort_hours=16,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="01.f",
            category=HITRUSTCategory.ACCESS_CONTROL,
            title="Multi-Factor Authentication",
            description=(
                "Multi-factor authentication is required for access "
                "to systems containing sensitive data."
            ),
            maturity_level=MaturityLevel.NOT_STARTED,
            gap_description="MFA not yet implemented for platform access",
            remediation_plan=(
                "Implement TOTP-based MFA for all user accounts. "
                "Require MFA for admin and PHI access. "
                "Support hardware security keys for privileged users."
            ),
            roadmap_phase=RoadmapPhase.PHASE_2,
            effort_hours=40,
            last_assessed=now,
        ),
        # ===================================================================
        # Category 2: Human Resources Security (3 controls)
        # ===================================================================
        HITRUSTControl(
            id="02.a",
            category=HITRUSTCategory.HUMAN_RESOURCES_SECURITY,
            title="Roles and Responsibilities",
            description=(
                "Security roles and responsibilities of employees, "
                "contractors, and third-party users are defined and documented."
            ),
            maturity_level=MaturityLevel.POLICY,
            platform_control="Role definitions in permission system",
            file_reference="app/core/permissions.py",
            gap_description="Technical roles defined but HR security roles not formalized",
            remediation_plan=(
                "Formalize HR security responsibilities in onboarding "
                "and employment agreements."
            ),
            roadmap_phase=RoadmapPhase.PHASE_2,
            effort_hours=20,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="02.b",
            category=HITRUSTCategory.HUMAN_RESOURCES_SECURITY,
            title="Security Awareness Training",
            description=(
                "All employees receive appropriate security awareness "
                "training and regular updates in organizational policies."
            ),
            maturity_level=MaturityLevel.NOT_STARTED,
            gap_description="No formal security awareness training program",
            remediation_plan=(
                "Develop security awareness training program covering "
                "HIPAA, PHI handling, and incident reporting. "
                "Implement annual training with completion tracking."
            ),
            roadmap_phase=RoadmapPhase.PHASE_2,
            effort_hours=40,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="02.c",
            category=HITRUSTCategory.HUMAN_RESOURCES_SECURITY,
            title="Termination Process",
            description=(
                "Access rights are removed upon termination and "
                "return of assets is managed."
            ),
            maturity_level=MaturityLevel.PROCEDURE,
            platform_control="User deactivation capabilities in auth system",
            file_reference="app/api/users.py",
            gap_description="Manual process exists but not fully automated",
            remediation_plan=(
                "Automate access revocation on termination. "
                "Implement automated asset return tracking."
            ),
            roadmap_phase=RoadmapPhase.PHASE_2,
            effort_hours=16,
            last_assessed=now,
        ),
        # ===================================================================
        # Category 3: Risk Management (4 controls)
        # ===================================================================
        HITRUSTControl(
            id="03.a",
            category=HITRUSTCategory.RISK_MANAGEMENT,
            title="Risk Assessment Process",
            description=(
                "A formal risk assessment process identifies, analyzes, "
                "and evaluates information security risks."
            ),
            maturity_level=MaturityLevel.IMPLEMENTED,
            platform_control="Risk scoring and threshold management",
            file_reference="app/services/risk_scoring.py",
            roadmap_phase=RoadmapPhase.PHASE_1,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="03.b",
            category=HITRUSTCategory.RISK_MANAGEMENT,
            title="Risk Treatment",
            description=(
                "Risk treatment plans are developed and implemented "
                "for identified risks."
            ),
            maturity_level=MaturityLevel.PROCEDURE,
            platform_control="Risk threshold and alert rules",
            file_reference="app/api/risk_thresholds.py",
            gap_description="Risk thresholds configured but formal treatment plans not documented",
            remediation_plan=(
                "Document risk treatment plans for each identified risk. "
                "Implement risk acceptance workflow."
            ),
            roadmap_phase=RoadmapPhase.PHASE_2,
            effort_hours=24,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="03.c",
            category=HITRUSTCategory.RISK_MANAGEMENT,
            title="Risk Monitoring",
            description=(
                "Risks are continuously monitored and risk assessments "
                "are reviewed at planned intervals."
            ),
            maturity_level=MaturityLevel.IMPLEMENTED,
            platform_control="Drift detection and prediction audit service",
            file_reference="app/services/drift_detection_service.py",
            roadmap_phase=RoadmapPhase.PHASE_1,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="03.d",
            category=HITRUSTCategory.RISK_MANAGEMENT,
            title="Third-Party Risk Management",
            description=(
                "Risks from third-party service providers are identified, "
                "assessed, and managed."
            ),
            maturity_level=MaturityLevel.NOT_STARTED,
            gap_description="No formal third-party risk assessment process",
            remediation_plan=(
                "Implement vendor risk assessment questionnaire. "
                "Create third-party risk register. "
                "Establish periodic vendor security reviews."
            ),
            roadmap_phase=RoadmapPhase.PHASE_3,
            effort_hours=32,
            last_assessed=now,
        ),
        # ===================================================================
        # Category 4: Security Policy (3 controls)
        # ===================================================================
        HITRUSTControl(
            id="04.a",
            category=HITRUSTCategory.SECURITY_POLICY,
            title="Information Security Policy",
            description=(
                "An information security policy document is approved, "
                "published, and communicated to all relevant parties."
            ),
            maturity_level=MaturityLevel.POLICY,
            platform_control="Security policies and incident response documentation",
            file_reference="docs/security/incident_response_plan.md",
            gap_description="Incident response plan exists but comprehensive security policy not published",
            remediation_plan=(
                "Draft comprehensive information security policy. "
                "Obtain management approval and publish to all staff."
            ),
            roadmap_phase=RoadmapPhase.PHASE_1,
            effort_hours=24,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="04.b",
            category=HITRUSTCategory.SECURITY_POLICY,
            title="Policy Review",
            description=(
                "Information security policy is reviewed at planned "
                "intervals and updated as needed."
            ),
            maturity_level=MaturityLevel.NOT_STARTED,
            gap_description="No formal policy review cadence established",
            remediation_plan=(
                "Establish annual security policy review process. "
                "Assign policy owners and reviewers."
            ),
            roadmap_phase=RoadmapPhase.PHASE_3,
            effort_hours=16,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="04.c",
            category=HITRUSTCategory.SECURITY_POLICY,
            title="Policy Enforcement",
            description=(
                "Mechanisms are in place to enforce compliance with "
                "information security policies."
            ),
            maturity_level=MaturityLevel.IMPLEMENTED,
            platform_control="Policy management and enforcement API",
            file_reference="app/api/policy.py",
            roadmap_phase=RoadmapPhase.PHASE_1,
            last_assessed=now,
        ),
        # ===================================================================
        # Category 5: Organization of Information Security (3 controls)
        # ===================================================================
        HITRUSTControl(
            id="05.a",
            category=HITRUSTCategory.ORGANIZATION_OF_INFORMATION_SECURITY,
            title="Internal Organization",
            description=(
                "Management demonstrates commitment to information security "
                "through clear direction and assignment of responsibilities."
            ),
            maturity_level=MaturityLevel.POLICY,
            platform_control="Quality management and CAPA tracking",
            file_reference="app/services/capa_service.py",
            gap_description="Quality management system exists but formal security organization not documented",
            remediation_plan=(
                "Define security organization structure. "
                "Establish security steering committee."
            ),
            roadmap_phase=RoadmapPhase.PHASE_2,
            effort_hours=20,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="05.b",
            category=HITRUSTCategory.ORGANIZATION_OF_INFORMATION_SECURITY,
            title="Contact with Authorities",
            description=(
                "Appropriate contacts with relevant authorities are maintained."
            ),
            maturity_level=MaturityLevel.PROCEDURE,
            platform_control="Incident notification with escalation paths",
            file_reference="docs/security/incident_runbooks/",
            gap_description="Incident runbooks exist but regulatory contact list not formalized",
            remediation_plan=(
                "Maintain formal contact list for regulators, law enforcement, "
                "and HITRUST assessors."
            ),
            roadmap_phase=RoadmapPhase.PHASE_3,
            effort_hours=8,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="05.c",
            category=HITRUSTCategory.ORGANIZATION_OF_INFORMATION_SECURITY,
            title="Contact with Special Interest Groups",
            description=(
                "Appropriate contacts with special interest groups, "
                "security forums, and professional associations are maintained."
            ),
            maturity_level=MaturityLevel.NOT_STARTED,
            gap_description="No formal participation in security information sharing",
            remediation_plan=(
                "Join H-ISAC (Health Information Sharing and Analysis Center). "
                "Subscribe to relevant threat intelligence feeds."
            ),
            roadmap_phase=RoadmapPhase.PHASE_4,
            effort_hours=8,
            last_assessed=now,
        ),
        # ===================================================================
        # Category 6: Compliance (4 controls)
        # ===================================================================
        HITRUSTControl(
            id="06.a",
            category=HITRUSTCategory.COMPLIANCE,
            title="HIPAA Compliance",
            description=(
                "The organization ensures compliance with HIPAA Privacy "
                "and Security Rules for handling protected health information."
            ),
            maturity_level=MaturityLevel.IMPLEMENTED,
            platform_control="HIPAA-compliant audit logging and PHI access tracking",
            file_reference="app/api/middleware/audit.py",
            roadmap_phase=RoadmapPhase.PHASE_1,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="06.b",
            category=HITRUSTCategory.COMPLIANCE,
            title="Regulatory Compliance Monitoring",
            description=(
                "The organization monitors and adapts to changes in "
                "applicable laws, regulations, and contractual requirements."
            ),
            maturity_level=MaturityLevel.PROCEDURE,
            platform_control="SOC 2 compliance tracking service",
            file_reference="app/services/soc2_service.py",
            gap_description="SOC 2 tracking exists but broader regulatory monitoring not formalized",
            remediation_plan=(
                "Implement regulatory change monitoring process. "
                "Subscribe to regulatory update services."
            ),
            roadmap_phase=RoadmapPhase.PHASE_3,
            effort_hours=20,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="06.c",
            category=HITRUSTCategory.COMPLIANCE,
            title="Audit and Assessment",
            description=(
                "Regular internal audits and assessments verify "
                "compliance with security policies and standards."
            ),
            maturity_level=MaturityLevel.IMPLEMENTED,
            platform_control="AI audit service and fairness audit capabilities",
            file_reference="app/api/ai_audit.py",
            roadmap_phase=RoadmapPhase.PHASE_1,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="06.d",
            category=HITRUSTCategory.COMPLIANCE,
            title="Data Protection Impact Assessment",
            description=(
                "Data protection impact assessments are conducted for "
                "processing activities involving personal data."
            ),
            maturity_level=MaturityLevel.NOT_STARTED,
            gap_description="No formal DPIA process established",
            remediation_plan=(
                "Create DPIA template and process. "
                "Conduct DPIAs for all PHI processing activities. "
                "Establish DPIA review cadence."
            ),
            roadmap_phase=RoadmapPhase.PHASE_3,
            effort_hours=32,
            last_assessed=now,
        ),
        # ===================================================================
        # Category 7: Asset Management (3 controls)
        # ===================================================================
        HITRUSTControl(
            id="07.a",
            category=HITRUSTCategory.ASSET_MANAGEMENT,
            title="Asset Inventory",
            description=(
                "An inventory of all assets associated with information "
                "and information processing facilities is maintained."
            ),
            maturity_level=MaturityLevel.PROCEDURE,
            platform_control="Infrastructure service with component tracking",
            file_reference="app/services/infrastructure_service.py",
            gap_description="Technical infrastructure tracked but complete asset inventory not maintained",
            remediation_plan=(
                "Build comprehensive asset inventory including hardware, "
                "software, data, and personnel assets. "
                "Implement automated discovery."
            ),
            roadmap_phase=RoadmapPhase.PHASE_2,
            effort_hours=24,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="07.b",
            category=HITRUSTCategory.ASSET_MANAGEMENT,
            title="Data Classification",
            description=(
                "Information is classified in terms of legal requirements, "
                "value, criticality, and sensitivity."
            ),
            maturity_level=MaturityLevel.IMPLEMENTED,
            platform_control="Data governance with data classification and categorization",
            file_reference="app/schemas/data_governance.py",
            roadmap_phase=RoadmapPhase.PHASE_1,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="07.c",
            category=HITRUSTCategory.ASSET_MANAGEMENT,
            title="Media Handling and Disposal",
            description=(
                "Procedures for the management and disposal of removable "
                "media and information assets are implemented."
            ),
            maturity_level=MaturityLevel.NOT_STARTED,
            gap_description="No formal media handling and disposal procedures",
            remediation_plan=(
                "Document media handling procedures. "
                "Implement certified data destruction process. "
                "Track disposal with certificates of destruction."
            ),
            roadmap_phase=RoadmapPhase.PHASE_3,
            effort_hours=16,
            last_assessed=now,
        ),
        # ===================================================================
        # Category 8: Physical and Environmental Security (3 controls)
        # ===================================================================
        HITRUSTControl(
            id="08.a",
            category=HITRUSTCategory.PHYSICAL_AND_ENVIRONMENTAL_SECURITY,
            title="Physical Security Perimeter",
            description=(
                "Security perimeters are used to protect areas that contain "
                "information and information processing facilities."
            ),
            maturity_level=MaturityLevel.NOT_STARTED,
            gap_description="Cloud-hosted platform; physical security delegated to cloud provider",
            remediation_plan=(
                "Document cloud provider physical security controls. "
                "Obtain SOC 2 reports from cloud providers. "
                "Map cloud provider controls to HITRUST requirements."
            ),
            roadmap_phase=RoadmapPhase.PHASE_3,
            effort_hours=16,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="08.b",
            category=HITRUSTCategory.PHYSICAL_AND_ENVIRONMENTAL_SECURITY,
            title="Equipment Security",
            description=(
                "Equipment is sited and protected to reduce risks "
                "from environmental threats and unauthorized access."
            ),
            maturity_level=MaturityLevel.NOT_STARTED,
            gap_description="Cloud infrastructure; equipment security managed by provider",
            remediation_plan=(
                "Document reliance on cloud provider equipment security. "
                "Verify provider compliance certifications."
            ),
            roadmap_phase=RoadmapPhase.PHASE_3,
            effort_hours=8,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="08.c",
            category=HITRUSTCategory.PHYSICAL_AND_ENVIRONMENTAL_SECURITY,
            title="Environmental Controls",
            description=(
                "Environmental controls protect against damage from fire, "
                "flood, earthquake, and other natural or man-made disasters."
            ),
            maturity_level=MaturityLevel.NOT_STARTED,
            gap_description="Cloud-hosted; environmental controls at provider level",
            remediation_plan=(
                "Document cloud provider environmental controls. "
                "Ensure multi-region deployment for disaster recovery."
            ),
            roadmap_phase=RoadmapPhase.PHASE_3,
            effort_hours=8,
            last_assessed=now,
        ),
        # ===================================================================
        # Category 9: Communications and Operations Management (5 controls)
        # ===================================================================
        HITRUSTControl(
            id="09.a",
            category=HITRUSTCategory.COMMUNICATIONS_AND_OPERATIONS_MANAGEMENT,
            title="Operational Procedures",
            description=(
                "Operating procedures are documented, maintained, and "
                "made available to all users who need them."
            ),
            maturity_level=MaturityLevel.IMPLEMENTED,
            platform_control="Observability service with operational dashboards",
            file_reference="app/services/observability_service.py",
            roadmap_phase=RoadmapPhase.PHASE_1,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="09.b",
            category=HITRUSTCategory.COMMUNICATIONS_AND_OPERATIONS_MANAGEMENT,
            title="Change Management",
            description=(
                "Changes to information processing facilities and systems "
                "are controlled through a formal change management process."
            ),
            maturity_level=MaturityLevel.IMPLEMENTED,
            platform_control="CI/CD pipeline with security workflows",
            file_reference=".github/workflows/security.yml",
            roadmap_phase=RoadmapPhase.PHASE_1,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="09.c",
            category=HITRUSTCategory.COMMUNICATIONS_AND_OPERATIONS_MANAGEMENT,
            title="Logging and Monitoring",
            description=(
                "Audit logs recording user activities, exceptions, and "
                "information security events are produced and kept."
            ),
            maturity_level=MaturityLevel.MANAGED,
            platform_control="Structured logging with audit middleware and SLI collection",
            file_reference="app/core/logging_config.py",
            roadmap_phase=RoadmapPhase.PHASE_1,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="09.d",
            category=HITRUSTCategory.COMMUNICATIONS_AND_OPERATIONS_MANAGEMENT,
            title="Network Security",
            description=(
                "Networks are managed and controlled to protect information "
                "in systems and applications."
            ),
            maturity_level=MaturityLevel.PROCEDURE,
            platform_control="Security headers middleware, CORS configuration, and rate limiting",
            file_reference="app/api/middleware/security_headers.py",
            gap_description="Application-level network security implemented; infrastructure-level controls need documentation",
            remediation_plan=(
                "Document network segmentation strategy. "
                "Implement network-level firewall rules. "
                "Configure WAF for public endpoints."
            ),
            roadmap_phase=RoadmapPhase.PHASE_2,
            effort_hours=24,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="09.e",
            category=HITRUSTCategory.COMMUNICATIONS_AND_OPERATIONS_MANAGEMENT,
            title="Malware Protection",
            description=(
                "Detection, prevention, and recovery controls are implemented "
                "to protect against malware."
            ),
            maturity_level=MaturityLevel.NOT_STARTED,
            gap_description="No formal malware protection strategy documented",
            remediation_plan=(
                "Implement container image scanning in CI/CD. "
                "Deploy runtime container security monitoring. "
                "Document malware protection strategy."
            ),
            roadmap_phase=RoadmapPhase.PHASE_2,
            effort_hours=24,
            last_assessed=now,
        ),
        # ===================================================================
        # Category 10: Information Systems Acquisition, Development, Maintenance (5 controls)
        # ===================================================================
        HITRUSTControl(
            id="10.a",
            category=HITRUSTCategory.INFORMATION_SYSTEMS_ACQUISITION_DEVELOPMENT_MAINTENANCE,
            title="Security Requirements Analysis",
            description=(
                "Information security requirements are included in "
                "requirements for new information systems or enhancements."
            ),
            maturity_level=MaturityLevel.IMPLEMENTED,
            platform_control="API contract service with security validation",
            file_reference="app/services/api_contract_service.py",
            roadmap_phase=RoadmapPhase.PHASE_1,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="10.b",
            category=HITRUSTCategory.INFORMATION_SYSTEMS_ACQUISITION_DEVELOPMENT_MAINTENANCE,
            title="Secure Development Policy",
            description=(
                "Rules for the development of software and systems "
                "are established and applied within the organization."
            ),
            maturity_level=MaturityLevel.IMPLEMENTED,
            platform_control="Security CI workflows with linting, type checking, and vulnerability scanning",
            file_reference=".github/workflows/security.yml",
            roadmap_phase=RoadmapPhase.PHASE_1,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="10.c",
            category=HITRUSTCategory.INFORMATION_SYSTEMS_ACQUISITION_DEVELOPMENT_MAINTENANCE,
            title="Application Security Testing",
            description=(
                "Testing of security functionality is carried out "
                "during development."
            ),
            maturity_level=MaturityLevel.IMPLEMENTED,
            platform_control="Comprehensive test suite with security test cases",
            file_reference="backend/tests/",
            roadmap_phase=RoadmapPhase.PHASE_1,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="10.d",
            category=HITRUSTCategory.INFORMATION_SYSTEMS_ACQUISITION_DEVELOPMENT_MAINTENANCE,
            title="System Acceptance Testing",
            description=(
                "Acceptance testing programs and criteria are established "
                "for new information systems and upgrades."
            ),
            maturity_level=MaturityLevel.PROCEDURE,
            platform_control="Validation study and gold standard testing framework",
            file_reference="app/api/validation_study.py",
            gap_description="Validation testing exists but formal acceptance criteria not documented",
            remediation_plan=(
                "Document formal system acceptance criteria. "
                "Create acceptance testing checklist for deployments."
            ),
            roadmap_phase=RoadmapPhase.PHASE_2,
            effort_hours=16,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="10.e",
            category=HITRUSTCategory.INFORMATION_SYSTEMS_ACQUISITION_DEVELOPMENT_MAINTENANCE,
            title="Vulnerability Management",
            description=(
                "Technical vulnerabilities are identified, evaluated, "
                "and appropriate measures are taken to address risk."
            ),
            maturity_level=MaturityLevel.PROCEDURE,
            platform_control="Dependency scanning and security workflows",
            file_reference=".github/workflows/security.yml",
            gap_description="Automated scanning exists but vulnerability management process not fully documented",
            remediation_plan=(
                "Establish formal vulnerability management process. "
                "Define SLAs for vulnerability remediation by severity. "
                "Implement vulnerability tracking dashboard."
            ),
            roadmap_phase=RoadmapPhase.PHASE_2,
            effort_hours=24,
            last_assessed=now,
        ),
        # ===================================================================
        # Category 11: Information Security Incident Management (4 controls)
        # ===================================================================
        HITRUSTControl(
            id="11.a",
            category=HITRUSTCategory.INFORMATION_SECURITY_INCIDENT_MANAGEMENT,
            title="Incident Management Procedures",
            description=(
                "Management responsibilities and procedures are established "
                "to ensure a quick, effective, and orderly response to incidents."
            ),
            maturity_level=MaturityLevel.MANAGED,
            platform_control="Incident management API with comprehensive runbooks",
            file_reference="docs/security/incident_response_plan.md",
            roadmap_phase=RoadmapPhase.PHASE_1,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="11.b",
            category=HITRUSTCategory.INFORMATION_SECURITY_INCIDENT_MANAGEMENT,
            title="Incident Reporting",
            description=(
                "Information security events are reported through "
                "appropriate management channels as quickly as possible."
            ),
            maturity_level=MaturityLevel.IMPLEMENTED,
            platform_control="Incident tracking API with severity classification",
            file_reference="app/api/incidents.py",
            roadmap_phase=RoadmapPhase.PHASE_1,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="11.c",
            category=HITRUSTCategory.INFORMATION_SECURITY_INCIDENT_MANAGEMENT,
            title="PHI Breach Response",
            description=(
                "Procedures for responding to breaches involving "
                "protected health information (PHI) are defined and tested."
            ),
            maturity_level=MaturityLevel.IMPLEMENTED,
            platform_control="PHI breach runbook with notification procedures",
            file_reference="docs/security/incident_runbooks/runbook_phi_breach.md",
            roadmap_phase=RoadmapPhase.PHASE_1,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="11.d",
            category=HITRUSTCategory.INFORMATION_SECURITY_INCIDENT_MANAGEMENT,
            title="Lessons Learned",
            description=(
                "Knowledge gained from information security incidents "
                "is used to improve incident response and reduce future risk."
            ),
            maturity_level=MaturityLevel.PROCEDURE,
            platform_control="Incident runbooks with post-incident review procedures",
            file_reference="docs/security/incident_runbooks/",
            gap_description="Runbooks exist but formal lessons-learned process not documented",
            remediation_plan=(
                "Implement formal post-incident review process. "
                "Create lessons-learned template. "
                "Track remediation actions from reviews."
            ),
            roadmap_phase=RoadmapPhase.PHASE_3,
            effort_hours=16,
            last_assessed=now,
        ),
        # ===================================================================
        # Category 12: Business Continuity Management (4 controls)
        # ===================================================================
        HITRUSTControl(
            id="12.a",
            category=HITRUSTCategory.BUSINESS_CONTINUITY_MANAGEMENT,
            title="Business Continuity Planning",
            description=(
                "A managed process is developed and maintained for business "
                "continuity that addresses information security requirements."
            ),
            maturity_level=MaturityLevel.PROCEDURE,
            platform_control="Disaster recovery plan documentation",
            file_reference="docs/operations/disaster_recovery_plan.md",
            gap_description="DR plan documented but full BCP not established",
            remediation_plan=(
                "Develop comprehensive Business Continuity Plan. "
                "Define RTOs and RPOs for all critical services. "
                "Conduct business impact analysis."
            ),
            roadmap_phase=RoadmapPhase.PHASE_2,
            effort_hours=40,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="12.b",
            category=HITRUSTCategory.BUSINESS_CONTINUITY_MANAGEMENT,
            title="Backup and Recovery",
            description=(
                "Backup copies of information and software are taken "
                "and tested regularly."
            ),
            maturity_level=MaturityLevel.IMPLEMENTED,
            platform_control="Backup verification service with automated integrity checks",
            file_reference="app/services/backup_verification_service.py",
            roadmap_phase=RoadmapPhase.PHASE_1,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="12.c",
            category=HITRUSTCategory.BUSINESS_CONTINUITY_MANAGEMENT,
            title="Recovery Testing",
            description=(
                "Business continuity plans are tested and updated regularly "
                "to ensure they are up to date and effective."
            ),
            maturity_level=MaturityLevel.NOT_STARTED,
            gap_description="No formal BCP/DR testing program",
            remediation_plan=(
                "Establish quarterly DR testing schedule. "
                "Define test scenarios and success criteria. "
                "Document test results and remediation."
            ),
            roadmap_phase=RoadmapPhase.PHASE_3,
            effort_hours=32,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="12.d",
            category=HITRUSTCategory.BUSINESS_CONTINUITY_MANAGEMENT,
            title="Redundancy and Failover",
            description=(
                "Information processing facilities are implemented with "
                "redundancy sufficient to meet availability requirements."
            ),
            maturity_level=MaturityLevel.PROCEDURE,
            platform_control="Capacity planning and scalability audit",
            file_reference="docs/operations/capacity_planning.md",
            gap_description="Capacity planning exists but automated failover not fully implemented",
            remediation_plan=(
                "Implement automated failover for critical services. "
                "Configure multi-region deployment. "
                "Test failover procedures quarterly."
            ),
            roadmap_phase=RoadmapPhase.PHASE_2,
            effort_hours=40,
            last_assessed=now,
        ),
        # ===================================================================
        # Category 13: Privacy Practices (5 controls)
        # ===================================================================
        HITRUSTControl(
            id="13.a",
            category=HITRUSTCategory.PRIVACY_PRACTICES,
            title="Consent Management",
            description=(
                "The organization obtains and manages consent for the "
                "collection, use, and disclosure of personal information."
            ),
            maturity_level=MaturityLevel.IMPLEMENTED,
            platform_control="Consent management API with granular consent tracking",
            file_reference="app/services/consent_service.py",
            roadmap_phase=RoadmapPhase.PHASE_1,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="13.b",
            category=HITRUSTCategory.PRIVACY_PRACTICES,
            title="Data Subject Rights",
            description=(
                "Procedures are established to handle data subject "
                "access, correction, and deletion requests."
            ),
            maturity_level=MaturityLevel.IMPLEMENTED,
            platform_control="Deletion service with right-to-deletion workflow",
            file_reference="app/services/deletion_service.py",
            roadmap_phase=RoadmapPhase.PHASE_1,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="13.c",
            category=HITRUSTCategory.PRIVACY_PRACTICES,
            title="Privacy Notice",
            description=(
                "Privacy notices are provided to data subjects describing "
                "data collection, use, retention, and sharing practices."
            ),
            maturity_level=MaturityLevel.POLICY,
            platform_control="Right-to-deletion policy documentation",
            file_reference="docs/legal/right_to_deletion_policy.md",
            gap_description="Deletion policy exists but comprehensive privacy notice not published",
            remediation_plan=(
                "Draft comprehensive privacy notice. "
                "Implement privacy notice presentation in application. "
                "Ensure notice covers all data processing activities."
            ),
            roadmap_phase=RoadmapPhase.PHASE_2,
            effort_hours=20,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="13.d",
            category=HITRUSTCategory.PRIVACY_PRACTICES,
            title="Data Minimization",
            description=(
                "Personal information collection is limited to what "
                "is necessary for the identified purpose."
            ),
            maturity_level=MaturityLevel.PROCEDURE,
            platform_control="FHIR data import with resource filtering",
            file_reference="app/api/fhir.py",
            gap_description="Data filtering exists but formal minimization policy not documented",
            remediation_plan=(
                "Document data minimization procedures for each data "
                "collection point. Implement automated PII scanning."
            ),
            roadmap_phase=RoadmapPhase.PHASE_2,
            effort_hours=16,
            last_assessed=now,
        ),
        HITRUSTControl(
            id="13.e",
            category=HITRUSTCategory.PRIVACY_PRACTICES,
            title="Data Retention and Disposal",
            description=(
                "Personal information is retained only as long as necessary "
                "and disposed of securely when no longer needed."
            ),
            maturity_level=MaturityLevel.IMPLEMENTED,
            platform_control="Data governance with retention policies and certified deletion",
            file_reference="app/services/deletion_service.py",
            roadmap_phase=RoadmapPhase.PHASE_1,
            last_assessed=now,
        ),
    ]

    return controls


class HITRUSTComplianceService:
    """Service for HITRUST CSF v11 compliance tracking and certification roadmap.

    Maintains a registry of HITRUST controls mapped to platform features,
    tracks maturity levels, manages evidence attachments, and generates
    certification roadmaps with phased remediation plans.
    """

    def __init__(self) -> None:
        """Initialize with pre-populated controls."""
        self._controls: dict[str, HITRUSTControl] = {}
        self._evidence: dict[str, list[EvidenceAttachment]] = {}
        self._load_prepopulated_controls()
        logger.info(
            "HITRUSTComplianceService initialized with %d controls",
            len(self._controls),
        )

    def _load_prepopulated_controls(self) -> None:
        """Load pre-populated HITRUST CSF controls."""
        for control in _build_prepopulated_controls():
            self._controls[control.id] = control
            self._evidence[control.id] = list(control.evidence)

    # ------------------------------------------------------------------
    # Control CRUD
    # ------------------------------------------------------------------

    def get_all_controls(
        self,
        category: HITRUSTCategory | None = None,
        maturity_level: MaturityLevel | None = None,
    ) -> list[HITRUSTControl]:
        """Get all controls, optionally filtered by category and/or maturity level."""
        controls = list(self._controls.values())
        if category is not None:
            controls = [c for c in controls if c.category == category]
        if maturity_level is not None:
            controls = [c for c in controls if c.maturity_level == maturity_level]
        return sorted(controls, key=lambda c: c.id)

    def get_control(self, control_id: str) -> HITRUSTControl | None:
        """Get a single control by ID."""
        return self._controls.get(control_id)

    def update_control(
        self, control_id: str, update: HITRUSTControlUpdate
    ) -> HITRUSTControl | None:
        """Update a control's maturity level, evidence, or remediation plan.

        Validates maturity level transitions - must advance or regress
        by at most one level:
        - NOT_STARTED -> POLICY
        - POLICY -> NOT_STARTED, PROCEDURE
        - PROCEDURE -> POLICY, IMPLEMENTED
        - IMPLEMENTED -> PROCEDURE, MEASURED
        - MEASURED -> IMPLEMENTED, MANAGED
        - MANAGED -> MEASURED

        Returns the updated control or None if not found.
        """
        control = self._controls.get(control_id)
        if control is None:
            return None

        # Validate maturity level transition if being changed
        if (
            update.maturity_level is not None
            and update.maturity_level != control.maturity_level
        ):
            valid_targets = VALID_MATURITY_TRANSITIONS.get(
                control.maturity_level, []
            )
            if update.maturity_level not in valid_targets:
                raise ValueError(
                    f"Invalid maturity transition from {control.maturity_level.value} "
                    f"to {update.maturity_level.value}. Valid transitions: "
                    f"{[s.value for s in valid_targets]}"
                )

        # Apply updates
        update_data = update.model_dump(exclude_none=True)
        control_data = control.model_dump()
        control_data.update(update_data)
        control_data["last_assessed"] = datetime.now(timezone.utc)

        # Preserve evidence list
        control_data["evidence"] = self._evidence.get(control_id, [])

        updated = HITRUSTControl(**control_data)
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
            id=f"HEVD-{uuid4().hex[:8].upper()}",
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
        self._controls[evidence_create.control_id] = HITRUSTControl(**control_data)

        return attachment

    def get_evidence(self, control_id: str) -> list[EvidenceAttachment]:
        """Get all evidence for a control."""
        return self._evidence.get(control_id, [])

    # ------------------------------------------------------------------
    # Readiness scoring
    # ------------------------------------------------------------------

    def _maturity_score(self, level: MaturityLevel) -> int:
        """Get numeric score for a maturity level."""
        return MATURITY_SCORES[level]

    def get_readiness_scores(self) -> ReadinessScore:
        """Calculate readiness scores per category and overall.

        Readiness percentage = (average_maturity / 5.0) * 100
        where 5.0 is the max maturity score (MANAGED).
        """
        category_scores: list[CategoryReadiness] = []
        all_scores: list[int] = []
        total_maturity_dist: dict[str, int] = {
            level.value: 0 for level in MaturityLevel
        }

        for category in HITRUSTCategory:
            controls = self.get_all_controls(category=category)
            if not controls:
                continue

            # Calculate maturity distribution
            dist: dict[str, int] = {level.value: 0 for level in MaturityLevel}
            scores: list[int] = []
            for c in controls:
                dist[c.maturity_level.value] += 1
                total_maturity_dist[c.maturity_level.value] += 1
                score = self._maturity_score(c.maturity_level)
                scores.append(score)
                all_scores.append(score)

            avg_score = sum(scores) / len(scores)
            readiness_pct = (avg_score / 5.0) * 100.0

            category_scores.append(
                CategoryReadiness(
                    category=category,
                    category_name=CATEGORY_NAMES[category],
                    total_controls=len(controls),
                    maturity_distribution=dist,
                    average_maturity_score=round(avg_score, 2),
                    readiness_percentage=round(readiness_pct, 1),
                )
            )

        # Overall scores
        overall_avg = sum(all_scores) / len(all_scores) if all_scores else 0
        overall_pct = (overall_avg / 5.0) * 100.0

        # Estimate effort to certification
        total_effort = sum(
            c.effort_hours
            for c in self._controls.values()
            if c.maturity_level != MaturityLevel.MANAGED
        )

        return ReadinessScore(
            overall_percentage=round(overall_pct, 1),
            overall_maturity_score=round(overall_avg, 2),
            categories=category_scores,
            total_controls=len(self._controls),
            maturity_distribution=total_maturity_dist,
            estimated_effort_to_certification=total_effort,
            assessed_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Category summary
    # ------------------------------------------------------------------

    def get_category_summaries(self) -> list[CategorySummary]:
        """Get summary for each HITRUST category."""
        summaries: list[CategorySummary] = []

        for category in HITRUSTCategory:
            controls = self.get_all_controls(category=category)
            if not controls:
                continue

            scores = [self._maturity_score(c.maturity_level) for c in controls]
            avg_score = sum(scores) / len(scores)
            readiness_pct = (avg_score / 5.0) * 100.0

            # Find controls with gaps (not at target maturity)
            gaps = [
                c.id
                for c in controls
                if self._maturity_score(c.maturity_level)
                < self._maturity_score(c.target_maturity)
            ]

            summaries.append(
                CategorySummary(
                    category=category,
                    category_name=CATEGORY_NAMES[category],
                    total_controls=len(controls),
                    average_maturity_score=round(avg_score, 2),
                    readiness_percentage=round(readiness_pct, 1),
                    top_gaps=gaps[:5],  # Top 5 gaps
                )
            )

        return summaries

    # ------------------------------------------------------------------
    # Roadmap generation
    # ------------------------------------------------------------------

    def generate_roadmap(self) -> CertificationRoadmap:
        """Generate phased HITRUST certification roadmap."""
        readiness = self.get_readiness_scores()

        phases: list[RoadmapPhaseDetail] = []
        total_effort = 0

        for phase in RoadmapPhase:
            # Find controls assigned to this phase that need work
            items: list[RoadmapItem] = []
            for control in self._controls.values():
                if (
                    control.roadmap_phase == phase
                    and self._maturity_score(control.maturity_level)
                    < self._maturity_score(control.target_maturity)
                ):
                    items.append(
                        RoadmapItem(
                            control_id=control.id,
                            category=control.category,
                            title=control.title,
                            current_maturity=control.maturity_level,
                            target_maturity=control.target_maturity,
                            effort_hours=control.effort_hours,
                            remediation_plan=control.remediation_plan
                            or "Advance maturity level through documentation and implementation",
                        )
                    )

            # Sort items by category then control ID
            items.sort(key=lambda i: (i.category.value, i.control_id))

            phase_effort = sum(i.effort_hours for i in items)
            total_effort += phase_effort

            info = PHASE_INFO[phase]
            phases.append(
                RoadmapPhaseDetail(
                    phase=phase,
                    phase_name=info["name"],
                    description=info["description"],
                    estimated_duration_weeks=PHASE_DURATION_WEEKS[phase],
                    total_effort_hours=phase_effort,
                    items=items,
                )
            )

        total_weeks = sum(PHASE_DURATION_WEEKS[p] for p in RoadmapPhase)

        return CertificationRoadmap(
            overall_readiness=readiness,
            phases=phases,
            total_effort_hours=total_effort,
            estimated_total_weeks=total_weeks,
            generated_at=datetime.now(timezone.utc),
        )


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------


def get_hitrust_service() -> HITRUSTComplianceService:
    """Get or create the singleton HITRUSTComplianceService."""
    global _hitrust_service_instance
    if _hitrust_service_instance is None:
        with _hitrust_service_lock:
            if _hitrust_service_instance is None:
                _hitrust_service_instance = HITRUSTComplianceService()
    return _hitrust_service_instance


def reset_hitrust_service() -> None:
    """Reset the singleton (for testing)."""
    global _hitrust_service_instance
    with _hitrust_service_lock:
        _hitrust_service_instance = None
