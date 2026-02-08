"""Data Classification Service.

Manages the data classification inventory, classification levels, handling rules,
review tracking, and reclassification workflows for the clinical trial patient
recruitment platform.

CLO-3: Data Classification Policy and Handling Procedures

Usage:
    from app.services.data_classification_service import get_data_classification_service

    svc = get_data_classification_service()
    assets = svc.list_assets()
    rules = svc.get_handling_rules(ClassificationLevel.RESTRICTED)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Optional

from app.schemas.data_classification import (
    AccessControlRequirements,
    ClassificationLevel,
    ClassificationLevelDefinition,
    ClassificationSummary,
    DataAssetCreate,
    DataAssetResponse,
    DataAssetUpdate,
    DataRole,
    HandlingRules,
    IncidentResponse,
    ReclassificationRequest,
    ReclassificationResponse,
    ReclassificationStatus,
    RetentionRequirements,
    SharingRestrictions,
    StorageRequirements,
    TransmissionRequirements,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Classification Level Definitions
# ---------------------------------------------------------------------------

CLASSIFICATION_LEVELS: dict[ClassificationLevel, ClassificationLevelDefinition] = {
    ClassificationLevel.PUBLIC: ClassificationLevelDefinition(
        level=ClassificationLevel.PUBLIC,
        name="Public",
        description=(
            "Information intended for public disclosure. Unauthorized disclosure "
            "would have no adverse impact on the organization or individuals."
        ),
        examples=[
            "Marketing materials",
            "General trial information (NCT numbers, conditions studied)",
            "Public API documentation",
            "Landing page content",
            "Published research abstracts",
        ],
        color="#22c55e",
        severity_order=0,
    ),
    ClassificationLevel.INTERNAL: ClassificationLevelDefinition(
        level=ClassificationLevel.INTERNAL,
        name="Internal",
        description=(
            "Information intended for internal use only. Unauthorized disclosure "
            "could cause minor operational disruption but no regulatory violation."
        ),
        examples=[
            "Internal analytics dashboards",
            "Aggregated and anonymized reports",
            "System performance logs",
            "OMOP vocabulary reference data",
            "API usage metrics",
            "Operational playbooks",
        ],
        color="#3b82f6",
        severity_order=1,
    ),
    ClassificationLevel.CONFIDENTIAL: ClassificationLevelDefinition(
        level=ClassificationLevel.CONFIDENTIAL,
        name="Confidential",
        description=(
            "Sensitive business or de-identified patient data. Unauthorized disclosure "
            "could cause significant reputational, financial, or competitive harm."
        ),
        examples=[
            "De-identified patient data",
            "Trial protocol details and amendments",
            "Business metrics and financial data",
            "Internal audit reports (without patient data)",
            "Vendor contracts and SLAs",
            "Employee information",
        ],
        color="#f59e0b",
        severity_order=2,
    ),
    ClassificationLevel.RESTRICTED: ClassificationLevelDefinition(
        level=ClassificationLevel.RESTRICTED,
        name="Restricted",
        description=(
            "Highest sensitivity data requiring maximum protection. Includes PHI, PII, "
            "credentials, and encryption keys. Unauthorized disclosure could result in "
            "regulatory penalties (HIPAA), legal liability, and patient harm."
        ),
        examples=[
            "Protected Health Information (PHI)",
            "Personally Identifiable Information (PII)",
            "Database credentials and API keys",
            "Encryption keys and certificates",
            "Audit logs containing patient data",
            "Screening results with patient identifiers",
            "Consent records with signatures",
        ],
        color="#ef4444",
        severity_order=3,
    ),
}

# ---------------------------------------------------------------------------
# Handling Rules per Classification Level
# ---------------------------------------------------------------------------

HANDLING_RULES: dict[ClassificationLevel, HandlingRules] = {
    ClassificationLevel.PUBLIC: HandlingRules(
        classification_level=ClassificationLevel.PUBLIC,
        storage=StorageRequirements(
            encryption_at_rest=False,
            encryption_algorithm=None,
            isolated_storage=False,
            backup_encrypted=False,
            geographic_restrictions=None,
        ),
        access_control=AccessControlRequirements(
            authentication_required=False,
            mfa_required=False,
            rbac_required=False,
            minimum_role=None,
            dua_required=False,
            need_to_know=False,
            access_logging="none",
        ),
        transmission=TransmissionRequirements(
            encryption_in_transit=False,
            minimum_tls_version=None,
            vpn_required=False,
            secure_channel_only=False,
        ),
        retention=RetentionRequirements(
            default_retention_days=None,
            disposal_method="standard_delete",
            disposal_verification=False,
            legal_hold_eligible=False,
        ),
        incident_response=IncidentResponse(
            notification_required=False,
            notification_timeline_hours=None,
            breach_report_required=False,
            hhs_notification=False,
            patient_notification=False,
            severity="low",
        ),
        sharing=SharingRestrictions(
            internal_sharing="unrestricted",
            external_sharing="unrestricted",
            third_party_sharing="unrestricted",
            de_identification_required=False,
        ),
    ),
    ClassificationLevel.INTERNAL: HandlingRules(
        classification_level=ClassificationLevel.INTERNAL,
        storage=StorageRequirements(
            encryption_at_rest=False,
            encryption_algorithm=None,
            isolated_storage=False,
            backup_encrypted=True,
            geographic_restrictions=None,
        ),
        access_control=AccessControlRequirements(
            authentication_required=True,
            mfa_required=False,
            rbac_required=False,
            minimum_role="viewer",
            dua_required=False,
            need_to_know=False,
            access_logging="standard",
        ),
        transmission=TransmissionRequirements(
            encryption_in_transit=True,
            minimum_tls_version="1.2",
            vpn_required=False,
            secure_channel_only=False,
        ),
        retention=RetentionRequirements(
            default_retention_days=730,
            disposal_method="standard_delete",
            disposal_verification=False,
            legal_hold_eligible=False,
        ),
        incident_response=IncidentResponse(
            notification_required=False,
            notification_timeline_hours=None,
            breach_report_required=False,
            hhs_notification=False,
            patient_notification=False,
            severity="medium",
        ),
        sharing=SharingRestrictions(
            internal_sharing="authenticated",
            external_sharing="with_approval",
            third_party_sharing="with_approval",
            de_identification_required=False,
        ),
    ),
    ClassificationLevel.CONFIDENTIAL: HandlingRules(
        classification_level=ClassificationLevel.CONFIDENTIAL,
        storage=StorageRequirements(
            encryption_at_rest=True,
            encryption_algorithm="AES-256",
            isolated_storage=False,
            backup_encrypted=True,
            geographic_restrictions="US-only",
        ),
        access_control=AccessControlRequirements(
            authentication_required=True,
            mfa_required=False,
            rbac_required=True,
            minimum_role="analyst",
            dua_required=False,
            need_to_know=True,
            access_logging="full",
        ),
        transmission=TransmissionRequirements(
            encryption_in_transit=True,
            minimum_tls_version="1.2",
            vpn_required=False,
            secure_channel_only=True,
        ),
        retention=RetentionRequirements(
            default_retention_days=2190,
            disposal_method="secure_erase",
            disposal_verification=True,
            legal_hold_eligible=True,
        ),
        incident_response=IncidentResponse(
            notification_required=True,
            notification_timeline_hours=72,
            breach_report_required=True,
            hhs_notification=False,
            patient_notification=False,
            severity="high",
        ),
        sharing=SharingRestrictions(
            internal_sharing="role_based",
            external_sharing="dua_required",
            third_party_sharing="dua_required",
            de_identification_required=True,
        ),
    ),
    ClassificationLevel.RESTRICTED: HandlingRules(
        classification_level=ClassificationLevel.RESTRICTED,
        storage=StorageRequirements(
            encryption_at_rest=True,
            encryption_algorithm="AES-256-GCM",
            isolated_storage=True,
            backup_encrypted=True,
            geographic_restrictions="US-only, HIPAA-compliant facility",
        ),
        access_control=AccessControlRequirements(
            authentication_required=True,
            mfa_required=True,
            rbac_required=True,
            minimum_role="clinician",
            dua_required=True,
            need_to_know=True,
            access_logging="full",
        ),
        transmission=TransmissionRequirements(
            encryption_in_transit=True,
            minimum_tls_version="1.3",
            vpn_required=True,
            secure_channel_only=True,
        ),
        retention=RetentionRequirements(
            default_retention_days=2190,
            disposal_method="crypto_shred",
            disposal_verification=True,
            legal_hold_eligible=True,
        ),
        incident_response=IncidentResponse(
            notification_required=True,
            notification_timeline_hours=24,
            breach_report_required=True,
            hhs_notification=True,
            patient_notification=True,
            severity="critical",
        ),
        sharing=SharingRestrictions(
            internal_sharing="role_based",
            external_sharing="prohibited",
            third_party_sharing="prohibited",
            de_identification_required=True,
        ),
    ),
}

# ---------------------------------------------------------------------------
# Data Governance Roles
# ---------------------------------------------------------------------------

DATA_ROLES: list[DataRole] = [
    DataRole(
        role_name="Data Owner",
        description=(
            "Senior leader accountable for the data asset. Approves classification, "
            "access requests, and reclassification. Ensures compliance with policies."
        ),
        responsibilities=[
            "Approve initial data classification",
            "Authorize access to data assets",
            "Review and approve reclassification requests",
            "Ensure compliance with retention policies",
            "Participate in periodic classification reviews",
        ],
        required_for_levels=[
            ClassificationLevel.CONFIDENTIAL,
            ClassificationLevel.RESTRICTED,
        ],
    ),
    DataRole(
        role_name="Data Steward",
        description=(
            "Subject matter expert responsible for day-to-day data quality, metadata "
            "management, and classification accuracy."
        ),
        responsibilities=[
            "Maintain accurate metadata and classification",
            "Conduct periodic classification reviews",
            "Identify data quality issues",
            "Recommend reclassification when needed",
            "Train staff on data handling procedures",
        ],
        required_for_levels=[
            ClassificationLevel.INTERNAL,
            ClassificationLevel.CONFIDENTIAL,
            ClassificationLevel.RESTRICTED,
        ],
    ),
    DataRole(
        role_name="Data Custodian",
        description=(
            "IT/infrastructure team responsible for implementing technical controls "
            "that enforce the classification policy (encryption, access controls, backups)."
        ),
        responsibilities=[
            "Implement encryption per classification requirements",
            "Configure access controls and RBAC",
            "Manage backups and disaster recovery",
            "Monitor for unauthorized access",
            "Execute disposal procedures",
        ],
        required_for_levels=[
            ClassificationLevel.INTERNAL,
            ClassificationLevel.CONFIDENTIAL,
            ClassificationLevel.RESTRICTED,
        ],
    ),
    DataRole(
        role_name="Privacy Officer",
        description=(
            "Oversees compliance with HIPAA, state privacy laws, and organizational "
            "privacy policies. Reviews all RESTRICTED data handling."
        ),
        responsibilities=[
            "Review RESTRICTED data asset classifications",
            "Conduct privacy impact assessments",
            "Investigate potential breaches",
            "Ensure HIPAA compliance",
            "Approve external data sharing agreements",
        ],
        required_for_levels=[
            ClassificationLevel.RESTRICTED,
        ],
    ),
]

# ---------------------------------------------------------------------------
# Pre-populated Data Assets (30+ mapped to platform data)
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc)

_PRE_POPULATED_ASSETS: list[dict] = [
    # RESTRICTED - PHI / PII / credentials
    {
        "name": "clinical_facts",
        "description": "Normalized clinical facts derived from patient documents. Contains diagnosis codes, lab values, medications linked to patient identifiers.",
        "classification_level": ClassificationLevel.RESTRICTED,
        "data_owner": "Chief Medical Officer",
        "data_steward": "Clinical Data Manager",
        "storage_location": "PostgreSQL: clinical_facts table",
        "retention_period_days": 2190,
        "encryption_required": True,
        "access_restrictions": ["clinician", "data_manager", "admin"],
        "review_frequency_days": 90,
        "tags": ["phi", "patient_data", "clinical"],
    },
    {
        "name": "kg_nodes",
        "description": "Knowledge graph nodes representing patients, conditions, medications, and procedures with patient-linked identifiers.",
        "classification_level": ClassificationLevel.RESTRICTED,
        "data_owner": "Chief Medical Officer",
        "data_steward": "Graph Data Engineer",
        "storage_location": "Neo4j / PostgreSQL: kg_nodes table",
        "retention_period_days": 2190,
        "encryption_required": True,
        "access_restrictions": ["clinician", "data_manager", "admin"],
        "review_frequency_days": 90,
        "tags": ["phi", "knowledge_graph", "patient_data"],
    },
    {
        "name": "kg_edges",
        "description": "Knowledge graph edges representing relationships between clinical entities. May contain temporal and patient-specific relationship data.",
        "classification_level": ClassificationLevel.RESTRICTED,
        "data_owner": "Chief Medical Officer",
        "data_steward": "Graph Data Engineer",
        "storage_location": "Neo4j / PostgreSQL: kg_edges table",
        "retention_period_days": 2190,
        "encryption_required": True,
        "access_restrictions": ["clinician", "data_manager", "admin"],
        "review_frequency_days": 90,
        "tags": ["phi", "knowledge_graph", "patient_data"],
    },
    {
        "name": "screening_results",
        "description": "Patient eligibility screening results for clinical trials. Contains patient identifiers, eligibility criteria outcomes, and match scores.",
        "classification_level": ClassificationLevel.RESTRICTED,
        "data_owner": "VP Clinical Operations",
        "data_steward": "Clinical Data Manager",
        "storage_location": "PostgreSQL: screening_results table",
        "retention_period_days": 2190,
        "encryption_required": True,
        "access_restrictions": ["clinician", "site_coordinator", "admin"],
        "review_frequency_days": 90,
        "tags": ["phi", "screening", "trial_recruitment"],
    },
    {
        "name": "patient_records",
        "description": "Core patient demographic and identification records including name, DOB, MRN, SSN (if collected), and contact information.",
        "classification_level": ClassificationLevel.RESTRICTED,
        "data_owner": "Chief Medical Officer",
        "data_steward": "Clinical Data Manager",
        "storage_location": "PostgreSQL: patients table",
        "retention_period_days": 2190,
        "encryption_required": True,
        "access_restrictions": ["clinician", "admin"],
        "review_frequency_days": 90,
        "tags": ["phi", "pii", "patient_data", "demographics"],
    },
    {
        "name": "clinical_documents",
        "description": "Raw clinical notes, discharge summaries, pathology reports, and other unstructured clinical text containing PHI.",
        "classification_level": ClassificationLevel.RESTRICTED,
        "data_owner": "Chief Medical Officer",
        "data_steward": "Clinical Data Manager",
        "storage_location": "PostgreSQL: documents table + object storage",
        "retention_period_days": 2190,
        "encryption_required": True,
        "access_restrictions": ["clinician", "admin"],
        "review_frequency_days": 90,
        "tags": ["phi", "clinical_notes", "unstructured"],
    },
    {
        "name": "consent_records",
        "description": "Patient informed consent records including signatures, consent dates, and consent form versions.",
        "classification_level": ClassificationLevel.RESTRICTED,
        "data_owner": "VP Clinical Operations",
        "data_steward": "Regulatory Affairs Manager",
        "storage_location": "PostgreSQL: consent_records table",
        "retention_period_days": 2190,
        "encryption_required": True,
        "access_restrictions": ["clinician", "site_coordinator", "admin"],
        "review_frequency_days": 90,
        "tags": ["phi", "consent", "regulatory"],
    },
    {
        "name": "fhir_resources",
        "description": "FHIR R4 resources (Patient, Observation, Condition, etc.) exchanged with EHR systems containing PHI.",
        "classification_level": ClassificationLevel.RESTRICTED,
        "data_owner": "Chief Medical Officer",
        "data_steward": "Integration Engineer",
        "storage_location": "PostgreSQL: fhir_resources table",
        "retention_period_days": 2190,
        "encryption_required": True,
        "access_restrictions": ["clinician", "integration_admin", "admin"],
        "review_frequency_days": 90,
        "tags": ["phi", "fhir", "interoperability"],
    },
    {
        "name": "mentions",
        "description": "NLP-extracted clinical mentions with text spans, offsets, and assertion attributes linked to patient documents.",
        "classification_level": ClassificationLevel.RESTRICTED,
        "data_owner": "Chief Medical Officer",
        "data_steward": "NLP Engineer",
        "storage_location": "PostgreSQL: mentions table",
        "retention_period_days": 2190,
        "encryption_required": True,
        "access_restrictions": ["clinician", "data_scientist", "admin"],
        "review_frequency_days": 90,
        "tags": ["phi", "nlp", "extraction"],
    },
    {
        "name": "database_credentials",
        "description": "PostgreSQL, Redis, and Neo4j connection strings, passwords, and authentication tokens.",
        "classification_level": ClassificationLevel.RESTRICTED,
        "data_owner": "CTO",
        "data_steward": "DevOps Lead",
        "storage_location": "Environment variables / HashiCorp Vault",
        "retention_period_days": None,
        "encryption_required": True,
        "access_restrictions": ["devops", "admin"],
        "review_frequency_days": 90,
        "tags": ["credentials", "infrastructure", "secrets"],
    },
    {
        "name": "encryption_keys",
        "description": "AES-256 encryption keys, TLS certificates, and JWT signing keys used for data protection.",
        "classification_level": ClassificationLevel.RESTRICTED,
        "data_owner": "CTO",
        "data_steward": "Security Engineer",
        "storage_location": "AWS KMS / HashiCorp Vault",
        "retention_period_days": None,
        "encryption_required": True,
        "access_restrictions": ["security_admin"],
        "review_frequency_days": 90,
        "tags": ["credentials", "encryption", "secrets"],
    },
    {
        "name": "audit_logs_with_phi",
        "description": "HIPAA audit trail entries that contain patient identifiers, accessed resources, and user actions on PHI.",
        "classification_level": ClassificationLevel.RESTRICTED,
        "data_owner": "Privacy Officer",
        "data_steward": "Compliance Analyst",
        "storage_location": "PostgreSQL: audit_logs table (PHI partition)",
        "retention_period_days": 2190,
        "encryption_required": True,
        "access_restrictions": ["compliance", "privacy_officer", "admin"],
        "review_frequency_days": 90,
        "tags": ["phi", "audit", "compliance", "hipaa"],
    },
    {
        "name": "diagnostic_reports",
        "description": "Structured diagnostic reports (lab results, imaging, pathology) linked to patient records.",
        "classification_level": ClassificationLevel.RESTRICTED,
        "data_owner": "Chief Medical Officer",
        "data_steward": "Clinical Data Manager",
        "storage_location": "PostgreSQL: diagnostic_reports table",
        "retention_period_days": 2190,
        "encryption_required": True,
        "access_restrictions": ["clinician", "admin"],
        "review_frequency_days": 90,
        "tags": ["phi", "diagnostics", "lab_results"],
    },
    # CONFIDENTIAL - De-identified data, trial protocols, business metrics
    {
        "name": "audit_logs_system",
        "description": "System-level audit logs recording API calls, configuration changes, and operational events (no patient data).",
        "classification_level": ClassificationLevel.CONFIDENTIAL,
        "data_owner": "CTO",
        "data_steward": "DevOps Lead",
        "storage_location": "PostgreSQL: audit_logs table (system partition)",
        "retention_period_days": 2190,
        "encryption_required": True,
        "access_restrictions": ["admin", "compliance"],
        "review_frequency_days": 180,
        "tags": ["audit", "system", "operations"],
    },
    {
        "name": "trial_definitions",
        "description": "Clinical trial protocol definitions including eligibility criteria, study design, endpoints, and sponsor details.",
        "classification_level": ClassificationLevel.CONFIDENTIAL,
        "data_owner": "VP Clinical Operations",
        "data_steward": "Clinical Operations Manager",
        "storage_location": "PostgreSQL: trials table",
        "retention_period_days": 2190,
        "encryption_required": True,
        "access_restrictions": ["clinician", "site_coordinator", "admin"],
        "review_frequency_days": 180,
        "tags": ["trial", "protocol", "confidential"],
    },
    {
        "name": "de_identified_datasets",
        "description": "De-identified patient datasets used for research analytics, cohort analysis, and recruitment optimization.",
        "classification_level": ClassificationLevel.CONFIDENTIAL,
        "data_owner": "VP Clinical Operations",
        "data_steward": "Data Scientist Lead",
        "storage_location": "PostgreSQL: de_identified_exports table",
        "retention_period_days": 1095,
        "encryption_required": True,
        "access_restrictions": ["data_scientist", "analyst", "admin"],
        "review_frequency_days": 180,
        "tags": ["de_identified", "research", "analytics"],
    },
    {
        "name": "business_metrics",
        "description": "Revenue projections, customer acquisition costs, site performance metrics, and financial forecasts.",
        "classification_level": ClassificationLevel.CONFIDENTIAL,
        "data_owner": "CFO",
        "data_steward": "Finance Manager",
        "storage_location": "PostgreSQL: business_metrics table",
        "retention_period_days": 2555,
        "encryption_required": True,
        "access_restrictions": ["executive", "finance", "admin"],
        "review_frequency_days": 180,
        "tags": ["financial", "business", "metrics"],
    },
    {
        "name": "vendor_contracts",
        "description": "Contracts, SLAs, BAAs, and procurement records for technology vendors and CRO partners.",
        "classification_level": ClassificationLevel.CONFIDENTIAL,
        "data_owner": "VP Operations",
        "data_steward": "Procurement Manager",
        "storage_location": "Document management system",
        "retention_period_days": 2555,
        "encryption_required": True,
        "access_restrictions": ["executive", "legal", "procurement", "admin"],
        "review_frequency_days": 365,
        "tags": ["contracts", "vendor", "legal"],
    },
    {
        "name": "dua_records",
        "description": "Data Use Agreement records tracking permitted uses, parties, and compliance status.",
        "classification_level": ClassificationLevel.CONFIDENTIAL,
        "data_owner": "Privacy Officer",
        "data_steward": "Compliance Analyst",
        "storage_location": "PostgreSQL: data_use_agreements table",
        "retention_period_days": 2190,
        "encryption_required": True,
        "access_restrictions": ["compliance", "legal", "admin"],
        "review_frequency_days": 180,
        "tags": ["dua", "compliance", "governance"],
    },
    {
        "name": "incident_records",
        "description": "Security and privacy incident records, investigation findings, and remediation actions.",
        "classification_level": ClassificationLevel.CONFIDENTIAL,
        "data_owner": "CISO",
        "data_steward": "Security Analyst",
        "storage_location": "PostgreSQL: incidents table",
        "retention_period_days": 2190,
        "encryption_required": True,
        "access_restrictions": ["security", "compliance", "admin"],
        "review_frequency_days": 180,
        "tags": ["incidents", "security", "compliance"],
    },
    {
        "name": "roi_analytics",
        "description": "Return on investment calculations, site enrollment projections, and recruitment cost analyses.",
        "classification_level": ClassificationLevel.CONFIDENTIAL,
        "data_owner": "VP Clinical Operations",
        "data_steward": "Analytics Lead",
        "storage_location": "PostgreSQL: roi_dashboard tables",
        "retention_period_days": 1825,
        "encryption_required": True,
        "access_restrictions": ["executive", "analyst", "admin"],
        "review_frequency_days": 180,
        "tags": ["analytics", "roi", "business"],
    },
    # INTERNAL - Operational data, reference data
    {
        "name": "api_metrics",
        "description": "API request/response metrics, latency measurements, error rates, and throughput statistics.",
        "classification_level": ClassificationLevel.INTERNAL,
        "data_owner": "CTO",
        "data_steward": "Platform Engineer",
        "storage_location": "Prometheus / PostgreSQL: api_metrics table",
        "retention_period_days": 365,
        "encryption_required": False,
        "access_restrictions": ["engineer", "devops", "admin"],
        "review_frequency_days": 365,
        "tags": ["metrics", "operational", "monitoring"],
    },
    {
        "name": "omop_vocabulary",
        "description": "OMOP CDM vocabulary tables (concepts, relationships, synonyms) used as reference data for terminology mapping.",
        "classification_level": ClassificationLevel.INTERNAL,
        "data_owner": "Chief Medical Officer",
        "data_steward": "Terminology Specialist",
        "storage_location": "PostgreSQL: omop_vocabulary tables",
        "retention_period_days": None,
        "encryption_required": False,
        "access_restrictions": ["engineer", "clinician", "admin"],
        "review_frequency_days": 365,
        "tags": ["vocabulary", "omop", "reference_data"],
    },
    {
        "name": "system_configuration",
        "description": "Application configuration settings, feature flags, and environment parameters (non-secret).",
        "classification_level": ClassificationLevel.INTERNAL,
        "data_owner": "CTO",
        "data_steward": "DevOps Lead",
        "storage_location": "Environment variables / config files",
        "retention_period_days": None,
        "encryption_required": False,
        "access_restrictions": ["engineer", "devops", "admin"],
        "review_frequency_days": 365,
        "tags": ["configuration", "infrastructure"],
    },
    {
        "name": "nlp_model_artifacts",
        "description": "Trained NLP model weights, tokenizer configs, and evaluation metrics for clinical text extraction.",
        "classification_level": ClassificationLevel.INTERNAL,
        "data_owner": "CTO",
        "data_steward": "ML Engineer",
        "storage_location": "Model registry / object storage",
        "retention_period_days": 1095,
        "encryption_required": False,
        "access_restrictions": ["ml_engineer", "data_scientist", "admin"],
        "review_frequency_days": 365,
        "tags": ["ml", "models", "nlp"],
    },
    {
        "name": "job_queue_metadata",
        "description": "Background job queue state, task metadata, and processing statistics from Redis/Celery.",
        "classification_level": ClassificationLevel.INTERNAL,
        "data_owner": "CTO",
        "data_steward": "Platform Engineer",
        "storage_location": "Redis",
        "retention_period_days": 30,
        "encryption_required": False,
        "access_restrictions": ["engineer", "devops", "admin"],
        "review_frequency_days": 365,
        "tags": ["jobs", "queue", "operational"],
    },
    {
        "name": "aggregated_diversity_reports",
        "description": "Aggregated trial enrollment diversity statistics (no individual patient data).",
        "classification_level": ClassificationLevel.INTERNAL,
        "data_owner": "VP Clinical Operations",
        "data_steward": "Analytics Lead",
        "storage_location": "PostgreSQL: diversity_analytics tables",
        "retention_period_days": 1825,
        "encryption_required": False,
        "access_restrictions": ["analyst", "compliance", "admin"],
        "review_frequency_days": 365,
        "tags": ["analytics", "diversity", "aggregated"],
    },
    {
        "name": "data_quality_reports",
        "description": "Data quality assessment results, completeness scores, and consistency check outcomes.",
        "classification_level": ClassificationLevel.INTERNAL,
        "data_owner": "CTO",
        "data_steward": "Data Quality Engineer",
        "storage_location": "PostgreSQL: data_quality tables",
        "retention_period_days": 730,
        "encryption_required": False,
        "access_restrictions": ["engineer", "analyst", "admin"],
        "review_frequency_days": 365,
        "tags": ["data_quality", "operational"],
    },
    # PUBLIC - Marketing, general info
    {
        "name": "landing_page_content",
        "description": "Public-facing website content including marketing copy, feature descriptions, and trial search interface.",
        "classification_level": ClassificationLevel.PUBLIC,
        "data_owner": "VP Marketing",
        "data_steward": "Content Manager",
        "storage_location": "Frontend static assets / CMS",
        "retention_period_days": None,
        "encryption_required": False,
        "access_restrictions": [],
        "review_frequency_days": 365,
        "tags": ["marketing", "website", "public"],
    },
    {
        "name": "public_trial_listings",
        "description": "Publicly available trial information including NCT numbers, conditions studied, phase, and general eligibility.",
        "classification_level": ClassificationLevel.PUBLIC,
        "data_owner": "VP Clinical Operations",
        "data_steward": "Clinical Operations Manager",
        "storage_location": "PostgreSQL: trial_listings view (public subset)",
        "retention_period_days": None,
        "encryption_required": False,
        "access_restrictions": [],
        "review_frequency_days": 365,
        "tags": ["trials", "public", "listings"],
    },
    {
        "name": "api_documentation",
        "description": "OpenAPI/Swagger documentation, developer guides, and integration instructions for public APIs.",
        "classification_level": ClassificationLevel.PUBLIC,
        "data_owner": "CTO",
        "data_steward": "Technical Writer",
        "storage_location": "Frontend: /api/v1/docs endpoint",
        "retention_period_days": None,
        "encryption_required": False,
        "access_restrictions": [],
        "review_frequency_days": 365,
        "tags": ["documentation", "api", "public"],
    },
    {
        "name": "published_research",
        "description": "Published research abstracts, white papers, and conference presentations about the platform.",
        "classification_level": ClassificationLevel.PUBLIC,
        "data_owner": "Chief Medical Officer",
        "data_steward": "Research Communications",
        "storage_location": "Document management / website",
        "retention_period_days": None,
        "encryption_required": False,
        "access_restrictions": [],
        "review_frequency_days": 365,
        "tags": ["research", "publications", "public"],
    },
]


# ---------------------------------------------------------------------------
# Service Implementation
# ---------------------------------------------------------------------------


class DataClassificationService:
    """Manages data classification inventory and handling procedures.

    Thread-safe singleton service that maintains an in-memory registry of
    data assets, classification levels, and handling rules.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._assets: dict[str, DataAssetResponse] = {}
        self._reclassification_requests: dict[str, ReclassificationResponse] = {}
        self._audit_trail: list[dict] = []
        self._populate_default_assets()

    # ----- Bootstrap -----

    def _populate_default_assets(self) -> None:
        """Populate the inventory with pre-defined platform data assets."""
        now = datetime.now(timezone.utc)
        for asset_def in _PRE_POPULATED_ASSETS:
            asset_id = f"asset-{uuid.uuid4().hex[:12]}"
            level = asset_def["classification_level"]
            review_freq = asset_def.get("review_frequency_days", 365)
            last_reviewed = now - timedelta(days=30)  # recently reviewed
            next_review = last_reviewed + timedelta(days=review_freq)

            self._assets[asset_id] = DataAssetResponse(
                asset_id=asset_id,
                name=asset_def["name"],
                description=asset_def["description"],
                classification_level=level,
                data_owner=asset_def["data_owner"],
                data_steward=asset_def.get("data_steward"),
                storage_location=asset_def["storage_location"],
                retention_period_days=asset_def.get("retention_period_days"),
                encryption_required=asset_def.get("encryption_required", False),
                access_restrictions=asset_def.get("access_restrictions", []),
                review_frequency_days=review_freq,
                last_reviewed=last_reviewed,
                next_review_due=next_review,
                is_overdue=False,
                created_at=now,
                updated_at=now,
                tags=asset_def.get("tags", []),
                handling_rules=HANDLING_RULES.get(level),
            )

    # ----- Classification Levels -----

    def get_classification_levels(self) -> list[ClassificationLevelDefinition]:
        """Return all classification level definitions ordered by severity."""
        return sorted(CLASSIFICATION_LEVELS.values(), key=lambda x: x.severity_order)

    def get_classification_level(self, level: ClassificationLevel) -> ClassificationLevelDefinition:
        """Return a specific classification level definition."""
        return CLASSIFICATION_LEVELS[level]

    # ----- Handling Rules -----

    def get_handling_rules(self, level: Optional[ClassificationLevel] = None) -> list[HandlingRules]:
        """Return handling rules, optionally filtered by level."""
        if level is not None:
            rule = HANDLING_RULES.get(level)
            return [rule] if rule else []
        return sorted(
            HANDLING_RULES.values(),
            key=lambda x: CLASSIFICATION_LEVELS[x.classification_level].severity_order,
        )

    def get_handling_rules_for_level(self, level: ClassificationLevel) -> HandlingRules:
        """Return handling rules for a specific level."""
        return HANDLING_RULES[level]

    # ----- Data Roles -----

    def get_data_roles(self) -> list[DataRole]:
        """Return all data governance role definitions."""
        return DATA_ROLES

    # ----- Asset CRUD -----

    def register_asset(self, create: DataAssetCreate) -> DataAssetResponse:
        """Register a new data asset in the inventory."""
        with self._lock:
            asset_id = f"asset-{uuid.uuid4().hex[:12]}"
            now = datetime.now(timezone.utc)
            level = create.classification_level
            next_review = now + timedelta(days=create.review_frequency_days)

            asset = DataAssetResponse(
                asset_id=asset_id,
                name=create.name,
                description=create.description,
                classification_level=level,
                data_owner=create.data_owner,
                data_steward=create.data_steward,
                storage_location=create.storage_location,
                retention_period_days=create.retention_period_days,
                encryption_required=create.encryption_required,
                access_restrictions=create.access_restrictions or [],
                review_frequency_days=create.review_frequency_days,
                last_reviewed=now,
                next_review_due=next_review,
                is_overdue=False,
                created_at=now,
                updated_at=now,
                tags=create.tags or [],
                handling_rules=HANDLING_RULES.get(level),
            )
            self._assets[asset_id] = asset

            self._audit_trail.append({
                "action": "asset_registered",
                "asset_id": asset_id,
                "asset_name": create.name,
                "classification_level": level.value,
                "timestamp": now.isoformat(),
            })

            logger.info(f"Registered data asset: {create.name} ({level.value})")
            return asset

    def get_asset(self, asset_id: str) -> Optional[DataAssetResponse]:
        """Return a data asset by ID."""
        return self._assets.get(asset_id)

    def get_asset_by_name(self, name: str) -> Optional[DataAssetResponse]:
        """Return a data asset by name."""
        for asset in self._assets.values():
            if asset.name == name:
                return asset
        return None

    def list_assets(
        self,
        classification_level: Optional[ClassificationLevel] = None,
        tag: Optional[str] = None,
        owner: Optional[str] = None,
    ) -> list[DataAssetResponse]:
        """List all data assets with optional filters."""
        assets = list(self._assets.values())

        if classification_level is not None:
            assets = [a for a in assets if a.classification_level == classification_level]

        if tag is not None:
            assets = [a for a in assets if tag in a.tags]

        if owner is not None:
            assets = [a for a in assets if a.data_owner == owner]

        return sorted(
            assets,
            key=lambda a: (
                CLASSIFICATION_LEVELS[a.classification_level].severity_order,
                a.name,
            ),
            reverse=True,
        )

    def update_asset(self, asset_id: str, update: DataAssetUpdate) -> Optional[DataAssetResponse]:
        """Update a data asset (partial update)."""
        with self._lock:
            asset = self._assets.get(asset_id)
            if asset is None:
                return None

            now = datetime.now(timezone.utc)
            old_level = asset.classification_level

            # Apply partial updates
            update_data = update.model_dump(exclude_unset=True)
            asset_data = asset.model_dump()
            for key, value in update_data.items():
                asset_data[key] = value

            asset_data["updated_at"] = now

            # If classification changed, update handling rules
            new_level = asset_data.get("classification_level", old_level)
            if isinstance(new_level, str):
                new_level = ClassificationLevel(new_level)
            asset_data["handling_rules"] = HANDLING_RULES.get(new_level)

            # Recalculate review dates
            freq = asset_data.get("review_frequency_days", 365)
            last_reviewed = asset_data.get("last_reviewed")
            if last_reviewed:
                if isinstance(last_reviewed, str):
                    last_reviewed = datetime.fromisoformat(last_reviewed)
                asset_data["next_review_due"] = last_reviewed + timedelta(days=freq)
                asset_data["is_overdue"] = asset_data["next_review_due"] < now

            updated_asset = DataAssetResponse(**asset_data)
            self._assets[asset_id] = updated_asset

            self._audit_trail.append({
                "action": "asset_updated",
                "asset_id": asset_id,
                "asset_name": updated_asset.name,
                "changes": list(update_data.keys()),
                "old_level": old_level.value if old_level != new_level else None,
                "new_level": new_level.value if old_level != new_level else None,
                "timestamp": now.isoformat(),
            })

            logger.info(f"Updated data asset: {updated_asset.name}")
            return updated_asset

    # ----- Overdue Reviews -----

    def get_overdue_reviews(self) -> list[DataAssetResponse]:
        """Return all assets with overdue classification reviews."""
        now = datetime.now(timezone.utc)
        overdue = []
        for asset in self._assets.values():
            if asset.next_review_due and asset.next_review_due < now:
                # Update is_overdue flag
                asset_data = asset.model_dump()
                asset_data["is_overdue"] = True
                updated = DataAssetResponse(**asset_data)
                self._assets[asset.asset_id] = updated
                overdue.append(updated)
        return sorted(
            overdue,
            key=lambda a: a.next_review_due or datetime.min.replace(tzinfo=timezone.utc),
        )

    def mark_reviewed(self, asset_id: str, reviewer: str) -> Optional[DataAssetResponse]:
        """Mark an asset as reviewed, resetting the review clock."""
        with self._lock:
            asset = self._assets.get(asset_id)
            if asset is None:
                return None

            now = datetime.now(timezone.utc)
            asset_data = asset.model_dump()
            asset_data["last_reviewed"] = now
            asset_data["next_review_due"] = now + timedelta(days=asset.review_frequency_days)
            asset_data["is_overdue"] = False
            asset_data["updated_at"] = now

            updated = DataAssetResponse(**asset_data)
            self._assets[asset_id] = updated

            self._audit_trail.append({
                "action": "review_completed",
                "asset_id": asset_id,
                "reviewer": reviewer,
                "timestamp": now.isoformat(),
            })

            return updated

    # ----- Reclassification Workflow -----

    def request_reclassification(self, request: ReclassificationRequest) -> ReclassificationResponse:
        """Submit a reclassification request for a data asset."""
        with self._lock:
            asset = self._assets.get(request.asset_id)
            if asset is None:
                raise ValueError(f"Asset not found: {request.asset_id}")

            if request.current_level != asset.classification_level:
                raise ValueError(
                    f"Current level mismatch: asset is {asset.classification_level.value}, "
                    f"request says {request.current_level.value}"
                )

            if request.requested_level == request.current_level:
                raise ValueError("Requested level is the same as current level")

            request_id = f"reclass-{uuid.uuid4().hex[:12]}"
            now = datetime.now(timezone.utc)

            response = ReclassificationResponse(
                request_id=request_id,
                asset_id=request.asset_id,
                asset_name=asset.name,
                current_level=request.current_level,
                requested_level=request.requested_level,
                justification=request.justification,
                requested_by=request.requested_by,
                status=ReclassificationStatus.PENDING,
                created_at=now,
            )
            self._reclassification_requests[request_id] = response

            self._audit_trail.append({
                "action": "reclassification_requested",
                "request_id": request_id,
                "asset_id": request.asset_id,
                "from_level": request.current_level.value,
                "to_level": request.requested_level.value,
                "requested_by": request.requested_by,
                "timestamp": now.isoformat(),
            })

            logger.info(
                f"Reclassification requested: {asset.name} "
                f"{request.current_level.value} -> {request.requested_level.value}"
            )
            return response

    def review_reclassification(
        self,
        request_id: str,
        approve: bool,
        reviewer: str,
        notes: Optional[str] = None,
    ) -> Optional[ReclassificationResponse]:
        """Approve or reject a reclassification request."""
        with self._lock:
            req = self._reclassification_requests.get(request_id)
            if req is None:
                return None

            if req.status != ReclassificationStatus.PENDING:
                raise ValueError(f"Request is not pending: {req.status.value}")

            now = datetime.now(timezone.utc)
            new_status = ReclassificationStatus.APPROVED if approve else ReclassificationStatus.REJECTED

            req_data = req.model_dump()
            req_data["status"] = new_status
            req_data["reviewer"] = reviewer
            req_data["review_notes"] = notes
            req_data["reviewed_at"] = now

            updated_req = ReclassificationResponse(**req_data)
            self._reclassification_requests[request_id] = updated_req

            # If approved, update the asset classification
            if approve:
                asset = self._assets.get(req.asset_id)
                if asset is not None:
                    asset_data = asset.model_dump()
                    asset_data["classification_level"] = req.requested_level
                    asset_data["handling_rules"] = HANDLING_RULES.get(req.requested_level)
                    asset_data["updated_at"] = now
                    # Update encryption requirement based on new level rules
                    new_rules = HANDLING_RULES.get(req.requested_level)
                    if new_rules:
                        asset_data["encryption_required"] = new_rules.storage.encryption_at_rest
                    self._assets[req.asset_id] = DataAssetResponse(**asset_data)

            self._audit_trail.append({
                "action": "reclassification_reviewed",
                "request_id": request_id,
                "decision": "approved" if approve else "rejected",
                "reviewer": reviewer,
                "notes": notes,
                "timestamp": now.isoformat(),
            })

            return updated_req

    def list_reclassification_requests(
        self,
        status: Optional[ReclassificationStatus] = None,
    ) -> list[ReclassificationResponse]:
        """List reclassification requests with optional status filter."""
        requests = list(self._reclassification_requests.values())
        if status is not None:
            requests = [r for r in requests if r.status == status]
        return sorted(requests, key=lambda r: r.created_at, reverse=True)

    # ----- Summary -----

    def get_summary(self) -> ClassificationSummary:
        """Generate summary statistics for the classification inventory."""
        now = datetime.now(timezone.utc)
        assets = list(self._assets.values())
        total = len(assets)

        by_level: dict[str, int] = {}
        for level in ClassificationLevel:
            by_level[level.value] = sum(
                1 for a in assets if a.classification_level == level
            )

        overdue = sum(
            1 for a in assets
            if a.next_review_due and a.next_review_due < now
        )

        pending_reclass = sum(
            1 for r in self._reclassification_requests.values()
            if r.status == ReclassificationStatus.PENDING
        )

        encrypted_count = sum(1 for a in assets if a.encryption_required)
        encryption_pct = (encrypted_count / total * 100) if total > 0 else 0.0

        dua_required = sum(
            1 for a in assets
            if a.handling_rules and a.handling_rules.access_control.dua_required
        )

        return ClassificationSummary(
            total_assets=total,
            by_level=by_level,
            overdue_reviews=overdue,
            pending_reclassifications=pending_reclass,
            encryption_coverage=round(encryption_pct, 1),
            assets_with_dua_requirement=dua_required,
            last_updated=now,
        )

    # ----- Audit Trail -----

    def get_audit_trail(self, limit: int = 100) -> list[dict]:
        """Return recent audit trail entries."""
        return self._audit_trail[-limit:]


# ---------------------------------------------------------------------------
# Singleton management
# ---------------------------------------------------------------------------

_service: Optional[DataClassificationService] = None
_service_lock = Lock()


def get_data_classification_service() -> DataClassificationService:
    """Return the singleton DataClassificationService instance."""
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = DataClassificationService()
    return _service


def reset_data_classification_service() -> None:
    """Reset the singleton (for testing)."""
    global _service
    _service = None
