"""EDC/CTMS Integration Roadmap Service (Partnership-2).

Manages integration planning, readiness assessment, effort estimation,
and data mapping between the Clinical Ontology Normalizer platform and
external clinical trial systems:

- Medidata Rave (EDC)
- Veeva Vault CTMS
- Oracle Siebel CTMS
- REDCap (EDC)
- Flatiron OncoEMR
- Epic (EHR)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.schemas.integration_roadmap import (
    AuthMethod,
    CapabilityReadiness,
    DataDomain,
    DataFlowDirection,
    DataFormat,
    DataMappingTemplate,
    EffortEstimate,
    FieldMapping,
    FieldMappingDirection,
    IntegrationCategory,
    IntegrationListResponse,
    IntegrationPattern,
    IntegrationRoadmap,
    IntegrationSpec,
    IntegrationSummary,
    IntegrationSystem,
    ReadinessAssessment,
    ReadinessStatus,
    RoadmapMilestone,
    RoadmapPhase,
    RoadmapPhaseDetail,
    SyncMethod,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_integration_roadmap_service: IntegrationRoadmapService | None = None


def get_integration_roadmap_service() -> IntegrationRoadmapService:
    """Return global singleton IntegrationRoadmapService instance."""
    global _integration_roadmap_service
    if _integration_roadmap_service is None:
        _integration_roadmap_service = IntegrationRoadmapService()
    return _integration_roadmap_service


def reset_integration_roadmap_service() -> None:
    """Reset the global singleton (for testing)."""
    global _integration_roadmap_service
    _integration_roadmap_service = None


# ---------------------------------------------------------------------------
# Integration Specifications (static data)
# ---------------------------------------------------------------------------

_INTEGRATION_SPECS: dict[IntegrationSystem, IntegrationSpec] = {
    IntegrationSystem.MEDIDATA_RAVE: IntegrationSpec(
        system=IntegrationSystem.MEDIDATA_RAVE,
        display_name="Medidata Rave",
        vendor="Dassault Systemes (Medidata Solutions)",
        category=IntegrationCategory.EDC,
        description=(
            "Industry-leading EDC platform used by top pharma companies for "
            "clinical trial data capture. Supports CDISC ODM-XML for study "
            "event data exchange and REST API for programmatic access."
        ),
        pattern=IntegrationPattern(
            data_flow=DataFlowDirection.BIDIRECTIONAL,
            auth_methods=[AuthMethod.OAUTH2, AuthMethod.API_KEY],
            data_formats=[DataFormat.CDISC_ODM, DataFormat.CUSTOM_JSON],
            sync_methods=[SyncMethod.REAL_TIME, SyncMethod.BATCH],
            api_type="REST",
            api_version="v1",
        ),
        data_domains=[
            DataDomain(
                name="Study Events",
                description="Study visits, forms, and event data",
                fhir_resource_types=["Encounter", "Observation"],
                cdisc_domains=["SE", "SV"],
            ),
            DataDomain(
                name="Subject Data",
                description="Subject demographics and enrollment status",
                fhir_resource_types=["Patient", "ResearchSubject"],
                cdisc_domains=["DM", "DS"],
            ),
            DataDomain(
                name="Clinical Data",
                description="Lab results, vital signs, adverse events",
                fhir_resource_types=[
                    "Observation", "Condition", "AdverseEvent",
                ],
                cdisc_domains=["LB", "VS", "AE"],
            ),
            DataDomain(
                name="Study Design",
                description="Protocol, study arms, visit schedules",
                fhir_resource_types=[
                    "ResearchStudy", "PlanDefinition", "ActivityDefinition",
                ],
                cdisc_domains=["TA", "TE", "TV"],
            ),
        ],
        documentation_url="https://developer.medidata.com/",
        typical_customers=[
            "Top 20 pharma", "Large CROs", "Biotech companies",
        ],
    ),
    IntegrationSystem.VEEVA_VAULT_CTMS: IntegrationSpec(
        system=IntegrationSystem.VEEVA_VAULT_CTMS,
        display_name="Veeva Vault CTMS",
        vendor="Veeva Systems",
        category=IntegrationCategory.CTMS,
        description=(
            "Cloud-based CTMS for managing clinical trial operations including "
            "study planning, site management, subject enrollment tracking, "
            "and milestone monitoring. REST API with comprehensive object model."
        ),
        pattern=IntegrationPattern(
            data_flow=DataFlowDirection.BIDIRECTIONAL,
            auth_methods=[AuthMethod.OAUTH2],
            data_formats=[DataFormat.CUSTOM_JSON, DataFormat.CSV],
            sync_methods=[SyncMethod.REAL_TIME, SyncMethod.BATCH],
            api_type="REST",
            api_version="v24.1",
        ),
        data_domains=[
            DataDomain(
                name="Study Management",
                description="Study configuration, arms, milestones",
                fhir_resource_types=["ResearchStudy", "PlanDefinition"],
                cdisc_domains=[],
            ),
            DataDomain(
                name="Site Management",
                description="Site activation, personnel, performance",
                fhir_resource_types=["Organization", "Location"],
                cdisc_domains=[],
            ),
            DataDomain(
                name="Subject Enrollment",
                description="Subject screening, enrollment, disposition",
                fhir_resource_types=["ResearchSubject", "Patient"],
                cdisc_domains=["DM", "DS"],
            ),
            DataDomain(
                name="Monitoring",
                description="Site visits, queries, issue tracking",
                fhir_resource_types=["Encounter", "Task"],
                cdisc_domains=[],
            ),
        ],
        documentation_url="https://developer.veevavault.com/",
        typical_customers=[
            "Top 20 pharma", "Large CROs", "Mid-size biotech",
        ],
    ),
    IntegrationSystem.ORACLE_SIEBEL_CTMS: IntegrationSpec(
        system=IntegrationSystem.ORACLE_SIEBEL_CTMS,
        display_name="Oracle Siebel CTMS",
        vendor="Oracle Corporation",
        category=IntegrationCategory.CTMS,
        description=(
            "Legacy CTMS platform widely deployed in large pharma for enrollment "
            "tracking, site management, and trial operations. Supports both "
            "SOAP and REST APIs with complex data model."
        ),
        pattern=IntegrationPattern(
            data_flow=DataFlowDirection.BIDIRECTIONAL,
            auth_methods=[AuthMethod.BASIC_AUTH, AuthMethod.CERTIFICATE],
            data_formats=[
                DataFormat.CUSTOM_XML, DataFormat.CUSTOM_JSON,
            ],
            sync_methods=[SyncMethod.BATCH, SyncMethod.ON_DEMAND],
            api_type="SOAP/REST",
            api_version="22.x",
        ),
        data_domains=[
            DataDomain(
                name="Enrollment Tracking",
                description="Subject enrollment status and projections",
                fhir_resource_types=["ResearchSubject"],
                cdisc_domains=["DM", "DS"],
            ),
            DataDomain(
                name="Site Management",
                description="Site selection, activation, performance",
                fhir_resource_types=["Organization", "Location"],
                cdisc_domains=[],
            ),
            DataDomain(
                name="Study Configuration",
                description="Protocol details and study setup",
                fhir_resource_types=["ResearchStudy"],
                cdisc_domains=[],
            ),
        ],
        documentation_url="https://docs.oracle.com/en/industries/life-sciences/",
        typical_customers=[
            "Legacy pharma installations", "Large CROs",
        ],
    ),
    IntegrationSystem.REDCAP: IntegrationSpec(
        system=IntegrationSystem.REDCAP,
        display_name="REDCap",
        vendor="Vanderbilt University",
        category=IntegrationCategory.EDC,
        description=(
            "Widely used web-based EDC for academic research and smaller trials. "
            "Simple REST API for data dictionary management, record creation, "
            "and export. Supports branching logic and calculated fields."
        ),
        pattern=IntegrationPattern(
            data_flow=DataFlowDirection.BIDIRECTIONAL,
            auth_methods=[AuthMethod.API_KEY],
            data_formats=[DataFormat.CUSTOM_JSON, DataFormat.CSV],
            sync_methods=[
                SyncMethod.ON_DEMAND, SyncMethod.BATCH,
            ],
            api_type="REST",
            api_version="v10.6+",
        ),
        data_domains=[
            DataDomain(
                name="Data Dictionary",
                description="Form definitions, field metadata, branching logic",
                fhir_resource_types=["Questionnaire"],
                cdisc_domains=[],
            ),
            DataDomain(
                name="Records",
                description="Subject records with form data",
                fhir_resource_types=[
                    "QuestionnaireResponse", "Patient", "Observation",
                ],
                cdisc_domains=["DM", "LB", "VS"],
            ),
            DataDomain(
                name="Events & Arms",
                description="Longitudinal event schedules and study arms",
                fhir_resource_types=["PlanDefinition", "ResearchStudy"],
                cdisc_domains=["TA", "TE"],
            ),
            DataDomain(
                name="Reports",
                description="Pre-defined and custom report exports",
                fhir_resource_types=[],
                cdisc_domains=[],
            ),
        ],
        documentation_url="https://projectredcap.org/resources/api/",
        typical_customers=[
            "Academic medical centers", "Investigator-initiated trials",
            "Small-mid biotech",
        ],
    ),
    IntegrationSystem.FLATIRON_ONCOEMR: IntegrationSpec(
        system=IntegrationSystem.FLATIRON_ONCOEMR,
        display_name="Flatiron OncoEMR",
        vendor="Flatiron Health (Roche)",
        category=IntegrationCategory.EMR,
        description=(
            "Oncology-specific EMR providing structured clinical data for "
            "cancer patients. FHIR R4 API with oncology-specific extensions "
            "for tumor staging, biomarkers, and treatment regimens."
        ),
        pattern=IntegrationPattern(
            data_flow=DataFlowDirection.INBOUND,
            auth_methods=[AuthMethod.OAUTH2],
            data_formats=[DataFormat.FHIR_R4],
            sync_methods=[SyncMethod.REAL_TIME, SyncMethod.BATCH],
            api_type="REST (FHIR R4)",
            api_version="R4",
        ),
        data_domains=[
            DataDomain(
                name="Oncology Demographics",
                description="Cancer patient demographics and insurance",
                fhir_resource_types=["Patient", "Coverage"],
                cdisc_domains=["DM"],
            ),
            DataDomain(
                name="Tumor Data",
                description="Staging, histology, biomarker results",
                fhir_resource_types=[
                    "Condition", "Observation", "DiagnosticReport",
                ],
                cdisc_domains=["TU", "TR", "RS"],
            ),
            DataDomain(
                name="Treatment",
                description="Chemotherapy, immunotherapy, radiation regimens",
                fhir_resource_types=[
                    "MedicationRequest", "MedicationAdministration", "Procedure",
                ],
                cdisc_domains=["CM", "EC"],
            ),
            DataDomain(
                name="Lab Results",
                description="CBC, CMP, tumor markers, genomic panels",
                fhir_resource_types=[
                    "Observation", "DiagnosticReport",
                ],
                cdisc_domains=["LB"],
            ),
        ],
        documentation_url="https://flatiron.com/oncology-data/",
        typical_customers=[
            "Oncology practices", "Cancer research networks",
            "Pharma (oncology trials)",
        ],
    ),
    IntegrationSystem.EPIC: IntegrationSpec(
        system=IntegrationSystem.EPIC,
        display_name="Epic",
        vendor="Epic Systems Corporation",
        category=IntegrationCategory.EHR,
        description=(
            "Market-leading EHR system deployed in major health systems. "
            "SMART on FHIR API for patient matching, clinical data access, "
            "and order integration. Supports CDS Hooks for decision support."
        ),
        pattern=IntegrationPattern(
            data_flow=DataFlowDirection.BIDIRECTIONAL,
            auth_methods=[AuthMethod.OAUTH2],
            data_formats=[DataFormat.FHIR_R4, DataFormat.HL7V2],
            sync_methods=[
                SyncMethod.REAL_TIME, SyncMethod.ON_DEMAND,
            ],
            api_type="SMART on FHIR",
            api_version="R4 (May 2024+)",
        ),
        data_domains=[
            DataDomain(
                name="Patient Demographics",
                description="Patient matching, demographics, contacts",
                fhir_resource_types=[
                    "Patient", "RelatedPerson",
                ],
                cdisc_domains=["DM"],
            ),
            DataDomain(
                name="Clinical Data",
                description="Problems, medications, allergies, vitals",
                fhir_resource_types=[
                    "Condition", "MedicationRequest",
                    "AllergyIntolerance", "Observation",
                ],
                cdisc_domains=["MH", "CM", "VS"],
            ),
            DataDomain(
                name="Orders",
                description="Lab orders, procedure orders, referrals",
                fhir_resource_types=[
                    "ServiceRequest", "MedicationRequest", "Task",
                ],
                cdisc_domains=[],
            ),
            DataDomain(
                name="Encounters",
                description="Visit history, admissions, appointments",
                fhir_resource_types=[
                    "Encounter", "Appointment",
                ],
                cdisc_domains=["SV"],
            ),
        ],
        documentation_url="https://fhir.epic.com/",
        typical_customers=[
            "Large health systems", "Academic medical centers",
            "Community hospitals",
        ],
    ),
}


# ---------------------------------------------------------------------------
# Readiness data (static capability assessment)
# ---------------------------------------------------------------------------

_PLATFORM_CAPABILITIES: dict[str, tuple[ReadinessStatus, float, str | None, float]] = {
    # capability: (status, coverage_pct, gap_description, effort_weeks)
    "fhir_r4_compliance": (
        ReadinessStatus.IMPLEMENTED, 95.0,
        "Minor gaps in specialty FHIR profiles (e.g., mCODE)",
        1.0,
    ),
    "cdisc_odm_support": (
        ReadinessStatus.NEEDS_DEVELOPMENT, 10.0,
        "ODM-XML parser and generator need full implementation; "
        "CDISC domain mapping templates required",
        8.0,
    ),
    "hl7v2_support": (
        ReadinessStatus.PARTIAL, 40.0,
        "ADT messages supported; ORU/ORM message types need implementation",
        4.0,
    ),
    "webhook_infrastructure": (
        ReadinessStatus.IMPLEMENTED, 90.0,
        "Webhook delivery and retry implemented; "
        "need vendor-specific payload transformers",
        1.0,
    ),
    "etl_pipeline": (
        ReadinessStatus.IMPLEMENTED, 85.0,
        "Core ETL operational; need custom connectors per vendor",
        2.0,
    ),
    "oauth2_client": (
        ReadinessStatus.IMPLEMENTED, 90.0,
        "OAuth2 authorization code and client credentials flows implemented; "
        "need vendor-specific token refresh handling",
        0.5,
    ),
    "certificate_auth": (
        ReadinessStatus.NEEDS_DEVELOPMENT, 5.0,
        "mTLS certificate management infrastructure not built",
        3.0,
    ),
    "smart_on_fhir": (
        ReadinessStatus.IMPLEMENTED, 92.0,
        "SMART App Launch and standalone launch supported; "
        "EHR launch context fully operational",
        0.5,
    ),
    "patient_matching": (
        ReadinessStatus.IMPLEMENTED, 88.0,
        "MPI-based matching implemented; probabilistic matching available",
        1.0,
    ),
    "data_mapping_engine": (
        ReadinessStatus.PARTIAL, 60.0,
        "FHIR-to-OMOP mapping operational; need CDISC and vendor-specific mappers",
        4.0,
    ),
    "batch_import_export": (
        ReadinessStatus.IMPLEMENTED, 85.0,
        "Bulk FHIR export implemented; need CSV/ODM batch handlers",
        2.0,
    ),
    "audit_trail": (
        ReadinessStatus.IMPLEMENTED, 95.0,
        "HIPAA-compliant audit logging operational",
        0.0,
    ),
    "soap_client": (
        ReadinessStatus.NEEDS_DEVELOPMENT, 0.0,
        "No SOAP client infrastructure; needed for Oracle Siebel integration",
        4.0,
    ),
    "cds_hooks": (
        ReadinessStatus.IMPLEMENTED, 88.0,
        "CDS Hooks service operational for clinical decision support",
        0.5,
    ),
}

# Capability requirements per system
_SYSTEM_CAPABILITIES: dict[IntegrationSystem, list[str]] = {
    IntegrationSystem.MEDIDATA_RAVE: [
        "cdisc_odm_support", "oauth2_client", "etl_pipeline",
        "data_mapping_engine", "webhook_infrastructure", "audit_trail",
        "batch_import_export",
    ],
    IntegrationSystem.VEEVA_VAULT_CTMS: [
        "oauth2_client", "etl_pipeline", "data_mapping_engine",
        "webhook_infrastructure", "audit_trail", "batch_import_export",
    ],
    IntegrationSystem.ORACLE_SIEBEL_CTMS: [
        "soap_client", "certificate_auth", "etl_pipeline",
        "data_mapping_engine", "batch_import_export", "audit_trail",
    ],
    IntegrationSystem.REDCAP: [
        "etl_pipeline", "data_mapping_engine", "batch_import_export",
        "audit_trail",
    ],
    IntegrationSystem.FLATIRON_ONCOEMR: [
        "fhir_r4_compliance", "oauth2_client", "etl_pipeline",
        "patient_matching", "data_mapping_engine", "webhook_infrastructure",
        "audit_trail",
    ],
    IntegrationSystem.EPIC: [
        "fhir_r4_compliance", "smart_on_fhir", "oauth2_client",
        "patient_matching", "hl7v2_support", "cds_hooks",
        "data_mapping_engine", "audit_trail",
    ],
}

# Phase assignments
_SYSTEM_PHASES: dict[IntegrationSystem, RoadmapPhase] = {
    IntegrationSystem.REDCAP: RoadmapPhase.PHASE_1,
    IntegrationSystem.EPIC: RoadmapPhase.PHASE_1,
    IntegrationSystem.MEDIDATA_RAVE: RoadmapPhase.PHASE_2,
    IntegrationSystem.VEEVA_VAULT_CTMS: RoadmapPhase.PHASE_3,
    IntegrationSystem.FLATIRON_ONCOEMR: RoadmapPhase.PHASE_3,
    IntegrationSystem.ORACLE_SIEBEL_CTMS: RoadmapPhase.PHASE_4,
}

# Effort estimates per system (total_weeks, headcount, engineer_weeks)
_EFFORT_DATA: dict[IntegrationSystem, tuple[int, int, int, list[str], list[str], list[str]]] = {
    IntegrationSystem.REDCAP: (
        6, 2, 10,
        [
            "Implement REDCap API client (token-based auth)",
            "Build data dictionary importer and form mapper",
            "Create record push/pull pipeline",
            "Implement event/arm mapping to platform schema",
            "Build validation and error handling",
            "Integration testing with REDCap sandbox",
        ],
        [
            "REDCap API version differences across institutions",
            "Custom field types may need special handling",
        ],
        [],
    ),
    IntegrationSystem.EPIC: (
        8, 3, 18,
        [
            "Configure SMART on FHIR app registration",
            "Implement EHR launch context handler",
            "Build patient matching via FHIR Patient search",
            "Create clinical data sync (Conditions, Meds, Labs)",
            "Implement CDS Hooks integration for trial alerts",
            "Build HL7v2 ADT/ORU message handler",
            "End-to-end testing with Epic sandbox",
        ],
        [
            "Epic app review process can take 4-8 weeks",
            "Health system-specific FHIR profiles may vary",
            "HL7v2 message format varies by implementation",
        ],
        [],
    ),
    IntegrationSystem.MEDIDATA_RAVE: (
        10, 3, 24,
        [
            "Build CDISC ODM-XML parser and generator",
            "Implement Medidata REST API client",
            "Create study event data adapter",
            "Build subject enrollment sync pipeline",
            "Implement clinical data exchange (labs, vitals, AEs)",
            "Create CDISC domain mapping templates",
            "Build real-time webhook event handler",
            "Validation testing with Medidata sandbox",
        ],
        [
            "CDISC ODM complexity requires careful implementation",
            "Medidata API access requires partnership agreement",
            "Study-specific ODM configurations vary significantly",
        ],
        ["Phase 1 completion (FHIR infrastructure hardened)"],
    ),
    IntegrationSystem.VEEVA_VAULT_CTMS: (
        8, 2, 14,
        [
            "Implement Veeva Vault REST API client",
            "Build study management object mapper",
            "Create site management sync pipeline",
            "Implement enrollment tracking integration",
            "Build monitoring visit data exchange",
            "Integration testing with Vault sandbox",
        ],
        [
            "Veeva object model is complex and heavily customized per client",
            "Vault API rate limits may affect batch operations",
        ],
        ["Phase 1 completion"],
    ),
    IntegrationSystem.FLATIRON_ONCOEMR: (
        8, 2, 14,
        [
            "Implement Flatiron FHIR R4 client with oncology extensions",
            "Build tumor data mapper (staging, biomarkers)",
            "Create treatment regimen sync pipeline",
            "Implement oncology lab result handler",
            "Build mCODE profile support",
            "Integration testing with Flatiron sandbox",
        ],
        [
            "Oncology-specific FHIR profiles require domain expertise",
            "Flatiron data access requires partnership agreement",
        ],
        ["Phase 1 completion (FHIR infrastructure)"],
    ),
    IntegrationSystem.ORACLE_SIEBEL_CTMS: (
        12, 3, 28,
        [
            "Build SOAP client infrastructure",
            "Implement certificate-based authentication",
            "Create Siebel business object mappers",
            "Build enrollment tracking adapter",
            "Implement site management sync",
            "Create batch data exchange pipeline",
            "Build error handling for legacy API quirks",
            "Extensive testing with Siebel test environment",
        ],
        [
            "Legacy SOAP APIs can be brittle and poorly documented",
            "Certificate management adds operational complexity",
            "Siebel customizations vary wildly between deployments",
            "May require on-premise connectivity (VPN/dedicated link)",
        ],
        [
            "Phase 2 completion (CDISC adapter reusable)",
            "Certificate auth infrastructure (from Phase 4 prep)",
        ],
    ),
}


# ---------------------------------------------------------------------------
# Data mapping templates
# ---------------------------------------------------------------------------

_DATA_MAPPINGS: dict[IntegrationSystem, list[DataMappingTemplate]] = {
    IntegrationSystem.REDCAP: [
        DataMappingTemplate(
            system=IntegrationSystem.REDCAP,
            display_name="REDCap",
            data_domain="Subject Records",
            source_format=DataFormat.FHIR_R4,
            target_format=DataFormat.CUSTOM_JSON,
            field_mappings=[
                FieldMapping(
                    platform_field="Patient.id",
                    platform_type="string",
                    target_field="record_id",
                    target_type="string",
                    direction=FieldMappingDirection.BIDIRECTIONAL,
                    required=True,
                ),
                FieldMapping(
                    platform_field="Patient.name[0].given[0]",
                    platform_type="string",
                    target_field="first_name",
                    target_type="string",
                    direction=FieldMappingDirection.SOURCE_TO_TARGET,
                    required=True,
                ),
                FieldMapping(
                    platform_field="Patient.name[0].family",
                    platform_type="string",
                    target_field="last_name",
                    target_type="string",
                    direction=FieldMappingDirection.SOURCE_TO_TARGET,
                    required=True,
                ),
                FieldMapping(
                    platform_field="Patient.birthDate",
                    platform_type="date",
                    target_field="dob",
                    target_type="date (YYYY-MM-DD)",
                    direction=FieldMappingDirection.BIDIRECTIONAL,
                    required=True,
                ),
                FieldMapping(
                    platform_field="Patient.gender",
                    platform_type="code",
                    target_field="sex",
                    target_type="integer (0=Female, 1=Male)",
                    direction=FieldMappingDirection.BIDIRECTIONAL,
                    transform="Map FHIR gender code to REDCap integer",
                    required=True,
                ),
                FieldMapping(
                    platform_field="ResearchSubject.status",
                    platform_type="code",
                    target_field="enrollment_status",
                    target_type="integer (coded)",
                    direction=FieldMappingDirection.BIDIRECTIONAL,
                    transform="Map FHIR status to REDCap coded value",
                    required=True,
                ),
            ],
            unmapped_source_fields=["Patient.telecom", "Patient.address"],
            unmapped_target_fields=["redcap_event_name", "redcap_repeat_instrument"],
            mapping_coverage_pct=75.0,
        ),
    ],
    IntegrationSystem.EPIC: [
        DataMappingTemplate(
            system=IntegrationSystem.EPIC,
            display_name="Epic",
            data_domain="Patient Clinical Data",
            source_format=DataFormat.FHIR_R4,
            target_format=DataFormat.FHIR_R4,
            field_mappings=[
                FieldMapping(
                    platform_field="Patient.identifier",
                    platform_type="Identifier[]",
                    target_field="Patient.identifier",
                    target_type="Identifier[]",
                    direction=FieldMappingDirection.BIDIRECTIONAL,
                    transform="Match on MRN system identifier",
                    required=True,
                ),
                FieldMapping(
                    platform_field="Condition.code",
                    platform_type="CodeableConcept",
                    target_field="Condition.code",
                    target_type="CodeableConcept",
                    direction=FieldMappingDirection.TARGET_TO_SOURCE,
                    transform="Validate against platform OMOP mapping",
                    required=True,
                ),
                FieldMapping(
                    platform_field="MedicationRequest.medicationCodeableConcept",
                    platform_type="CodeableConcept",
                    target_field="MedicationRequest.medicationCodeableConcept",
                    target_type="CodeableConcept",
                    direction=FieldMappingDirection.TARGET_TO_SOURCE,
                    transform="Map RxNorm codes via OMOP vocabulary",
                    required=True,
                ),
                FieldMapping(
                    platform_field="Observation.code",
                    platform_type="CodeableConcept",
                    target_field="Observation.code",
                    target_type="CodeableConcept",
                    direction=FieldMappingDirection.TARGET_TO_SOURCE,
                    transform="Map LOINC codes for lab results",
                    required=True,
                ),
                FieldMapping(
                    platform_field="Observation.valueQuantity",
                    platform_type="Quantity",
                    target_field="Observation.valueQuantity",
                    target_type="Quantity",
                    direction=FieldMappingDirection.TARGET_TO_SOURCE,
                    transform="UCUM unit normalization",
                    required=True,
                ),
            ],
            unmapped_source_fields=[],
            unmapped_target_fields=["Encounter.class", "Encounter.type"],
            mapping_coverage_pct=85.0,
        ),
    ],
    IntegrationSystem.MEDIDATA_RAVE: [
        DataMappingTemplate(
            system=IntegrationSystem.MEDIDATA_RAVE,
            display_name="Medidata Rave",
            data_domain="Study Event Data",
            source_format=DataFormat.FHIR_R4,
            target_format=DataFormat.CDISC_ODM,
            field_mappings=[
                FieldMapping(
                    platform_field="ResearchSubject.identifier",
                    platform_type="Identifier",
                    target_field="SubjectData/@SubjectKey",
                    target_type="string",
                    direction=FieldMappingDirection.BIDIRECTIONAL,
                    required=True,
                ),
                FieldMapping(
                    platform_field="ResearchStudy.identifier",
                    platform_type="Identifier",
                    target_field="ClinicalData/@StudyOID",
                    target_type="OID",
                    direction=FieldMappingDirection.SOURCE_TO_TARGET,
                    required=True,
                ),
                FieldMapping(
                    platform_field="Encounter.period.start",
                    platform_type="dateTime",
                    target_field="StudyEventData/@StartDate",
                    target_type="date",
                    direction=FieldMappingDirection.BIDIRECTIONAL,
                    transform="ISO 8601 to ODM date format",
                    required=True,
                ),
                FieldMapping(
                    platform_field="Observation.code",
                    platform_type="CodeableConcept",
                    target_field="ItemData/@ItemOID",
                    target_type="OID",
                    direction=FieldMappingDirection.BIDIRECTIONAL,
                    transform="Map LOINC/SNOMED to Medidata item OID via study config",
                    required=True,
                ),
                FieldMapping(
                    platform_field="Observation.valueQuantity.value",
                    platform_type="decimal",
                    target_field="ItemData/@Value",
                    target_type="string",
                    direction=FieldMappingDirection.BIDIRECTIONAL,
                    required=True,
                ),
            ],
            unmapped_source_fields=["Observation.interpretation"],
            unmapped_target_fields=[
                "AuditRecord", "Signature", "Annotation",
            ],
            mapping_coverage_pct=70.0,
        ),
    ],
    IntegrationSystem.VEEVA_VAULT_CTMS: [
        DataMappingTemplate(
            system=IntegrationSystem.VEEVA_VAULT_CTMS,
            display_name="Veeva Vault CTMS",
            data_domain="Enrollment Management",
            source_format=DataFormat.FHIR_R4,
            target_format=DataFormat.CUSTOM_JSON,
            field_mappings=[
                FieldMapping(
                    platform_field="ResearchStudy.identifier",
                    platform_type="Identifier",
                    target_field="study__v.id",
                    target_type="string",
                    direction=FieldMappingDirection.BIDIRECTIONAL,
                    required=True,
                ),
                FieldMapping(
                    platform_field="ResearchSubject.status",
                    platform_type="code",
                    target_field="subject__v.status__v",
                    target_type="picklist",
                    direction=FieldMappingDirection.BIDIRECTIONAL,
                    transform="Map FHIR status to Vault picklist value",
                    required=True,
                ),
                FieldMapping(
                    platform_field="Organization.name",
                    platform_type="string",
                    target_field="site__v.name__v",
                    target_type="string",
                    direction=FieldMappingDirection.BIDIRECTIONAL,
                    required=True,
                ),
                FieldMapping(
                    platform_field="ResearchSubject.period.start",
                    platform_type="dateTime",
                    target_field="subject__v.screening_date__v",
                    target_type="date",
                    direction=FieldMappingDirection.SOURCE_TO_TARGET,
                    required=True,
                ),
            ],
            unmapped_source_fields=["ResearchSubject.assignedArm"],
            unmapped_target_fields=["subject__v.randomization_number__v"],
            mapping_coverage_pct=72.0,
        ),
    ],
    IntegrationSystem.FLATIRON_ONCOEMR: [
        DataMappingTemplate(
            system=IntegrationSystem.FLATIRON_ONCOEMR,
            display_name="Flatiron OncoEMR",
            data_domain="Oncology Clinical Data",
            source_format=DataFormat.FHIR_R4,
            target_format=DataFormat.FHIR_R4,
            field_mappings=[
                FieldMapping(
                    platform_field="Patient.identifier",
                    platform_type="Identifier[]",
                    target_field="Patient.identifier",
                    target_type="Identifier[]",
                    direction=FieldMappingDirection.TARGET_TO_SOURCE,
                    required=True,
                ),
                FieldMapping(
                    platform_field="Condition.code",
                    platform_type="CodeableConcept",
                    target_field="Condition.code",
                    target_type="CodeableConcept",
                    direction=FieldMappingDirection.TARGET_TO_SOURCE,
                    transform="Map ICD-10/SNOMED oncology codes via OMOP",
                    required=True,
                    notes="Includes mCODE primary cancer condition profile",
                ),
                FieldMapping(
                    platform_field="Observation.code (TNM staging)",
                    platform_type="CodeableConcept",
                    target_field="Observation.code",
                    target_type="CodeableConcept",
                    direction=FieldMappingDirection.TARGET_TO_SOURCE,
                    transform="mCODE TNM staging observation mapping",
                    required=True,
                ),
                FieldMapping(
                    platform_field="MedicationRequest.medicationCodeableConcept",
                    platform_type="CodeableConcept",
                    target_field="MedicationRequest.medicationCodeableConcept",
                    target_type="CodeableConcept",
                    direction=FieldMappingDirection.TARGET_TO_SOURCE,
                    transform="Map chemotherapy/immunotherapy regimen codes",
                    required=True,
                ),
            ],
            unmapped_source_fields=[],
            unmapped_target_fields=[
                "Observation.component (genomic variants)",
            ],
            mapping_coverage_pct=78.0,
        ),
    ],
    IntegrationSystem.ORACLE_SIEBEL_CTMS: [
        DataMappingTemplate(
            system=IntegrationSystem.ORACLE_SIEBEL_CTMS,
            display_name="Oracle Siebel CTMS",
            data_domain="Enrollment Tracking",
            source_format=DataFormat.FHIR_R4,
            target_format=DataFormat.CUSTOM_XML,
            field_mappings=[
                FieldMapping(
                    platform_field="ResearchStudy.identifier",
                    platform_type="Identifier",
                    target_field="ClinicalTrial/ProtocolNumber",
                    target_type="string",
                    direction=FieldMappingDirection.BIDIRECTIONAL,
                    required=True,
                ),
                FieldMapping(
                    platform_field="ResearchSubject.identifier",
                    platform_type="Identifier",
                    target_field="Subject/SubjectNumber",
                    target_type="string",
                    direction=FieldMappingDirection.BIDIRECTIONAL,
                    required=True,
                ),
                FieldMapping(
                    platform_field="ResearchSubject.status",
                    platform_type="code",
                    target_field="Subject/EnrollmentStatus",
                    target_type="picklist",
                    direction=FieldMappingDirection.BIDIRECTIONAL,
                    transform="Map FHIR status to Siebel LOV value",
                    required=True,
                ),
                FieldMapping(
                    platform_field="Organization.identifier",
                    platform_type="Identifier",
                    target_field="Site/SiteNumber",
                    target_type="string",
                    direction=FieldMappingDirection.BIDIRECTIONAL,
                    required=True,
                ),
            ],
            unmapped_source_fields=["ResearchSubject.assignedArm"],
            unmapped_target_fields=[
                "Subject/RandomizationDate",
                "Subject/ScreenFailReason",
                "Site/IRBApprovalDate",
            ],
            mapping_coverage_pct=58.0,
        ),
    ],
}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class IntegrationRoadmapService:
    """Service for managing EDC/CTMS integration roadmap planning.

    Provides integration specifications, readiness assessments, phased
    roadmap planning, effort estimation, and data mapping templates
    for six target clinical trial systems.
    """

    def __init__(self) -> None:
        self._specs = dict(_INTEGRATION_SPECS)
        self._capabilities = dict(_PLATFORM_CAPABILITIES)
        self._system_capabilities = dict(_SYSTEM_CAPABILITIES)
        self._system_phases = dict(_SYSTEM_PHASES)
        self._effort_data = dict(_EFFORT_DATA)
        self._data_mappings = dict(_DATA_MAPPINGS)
        logger.info(
            "IntegrationRoadmapService initialized with %d target systems",
            len(self._specs),
        )

    # ------------------------------------------------------------------
    # Integration listing
    # ------------------------------------------------------------------

    def list_integrations(self) -> IntegrationListResponse:
        """List all target integration systems."""
        return IntegrationListResponse(
            total=len(self._specs),
            integrations=list(self._specs.values()),
        )

    def get_integration(self, system: str) -> IntegrationSpec | None:
        """Get integration specification for a specific system."""
        try:
            key = IntegrationSystem(system)
        except ValueError:
            return None
        return self._specs.get(key)

    def get_system_ids(self) -> list[str]:
        """Return all valid system identifiers."""
        return [s.value for s in self._specs]

    # ------------------------------------------------------------------
    # Readiness assessment
    # ------------------------------------------------------------------

    def assess_readiness(self, system: str) -> ReadinessAssessment | None:
        """Assess integration readiness for a specific system."""
        try:
            key = IntegrationSystem(system)
        except ValueError:
            return None

        if key not in self._specs:
            return None

        spec = self._specs[key]
        required_caps = self._system_capabilities.get(key, [])
        cap_assessments: list[CapabilityReadiness] = []

        for cap_name in required_caps:
            if cap_name in self._capabilities:
                status, coverage, gap, effort = self._capabilities[cap_name]
                cap_assessments.append(
                    CapabilityReadiness(
                        capability=cap_name,
                        status=status,
                        description=self._capability_description(cap_name),
                        coverage_pct=coverage,
                        gap_description=gap,
                        estimated_effort_weeks=effort,
                    )
                )

        # Calculate overall readiness
        if cap_assessments:
            overall = sum(c.coverage_pct for c in cap_assessments) / len(cap_assessments)
        else:
            overall = 0.0

        # Identify blockers
        blockers = [
            f"{c.capability}: {c.gap_description}"
            for c in cap_assessments
            if c.status == ReadinessStatus.NEEDS_DEVELOPMENT and c.gap_description
        ]

        # Identify prerequisites
        prerequisites: list[str] = []
        phase = self._system_phases.get(key, RoadmapPhase.PHASE_4)
        if phase != RoadmapPhase.PHASE_1:
            prerequisites.append(
                "Complete Phase 1 integrations (REDCap + Epic) to harden FHIR infrastructure"
            )
        if key == IntegrationSystem.ORACLE_SIEBEL_CTMS:
            prerequisites.append("Build SOAP client infrastructure")
            prerequisites.append("Implement certificate-based authentication")

        return ReadinessAssessment(
            system=key,
            display_name=spec.display_name,
            overall_readiness_pct=round(overall, 1),
            capabilities=cap_assessments,
            blockers=blockers,
            prerequisites=prerequisites,
            recommended_phase=phase,
        )

    def _capability_description(self, cap_name: str) -> str:
        """Return a human-readable description for a capability."""
        descriptions: dict[str, str] = {
            "fhir_r4_compliance": "FHIR R4 resource parsing, validation, and exchange",
            "cdisc_odm_support": "CDISC ODM-XML parsing, generation, and domain mapping",
            "hl7v2_support": "HL7 v2.x message parsing and generation (ADT, ORU, ORM)",
            "webhook_infrastructure": "Webhook delivery, retry, and payload transformation",
            "etl_pipeline": "Extract-Transform-Load pipeline for data ingestion",
            "oauth2_client": "OAuth 2.0 client for authorization code and client credentials flows",
            "certificate_auth": "Mutual TLS (mTLS) certificate-based authentication",
            "smart_on_fhir": "SMART on FHIR app launch and authorization",
            "patient_matching": "Patient identity matching (MPI-based and probabilistic)",
            "data_mapping_engine": "Configurable data mapping between clinical data standards",
            "batch_import_export": "Bulk data import and export (FHIR, CSV, ODM)",
            "audit_trail": "HIPAA-compliant audit logging and compliance reporting",
            "soap_client": "SOAP web service client for legacy system integration",
            "cds_hooks": "CDS Hooks for clinical decision support integration",
        }
        return descriptions.get(cap_name, f"Platform capability: {cap_name}")

    # ------------------------------------------------------------------
    # Roadmap
    # ------------------------------------------------------------------

    def get_roadmap(self) -> IntegrationRoadmap:
        """Generate the complete phased integration roadmap."""
        phases: list[RoadmapPhaseDetail] = []

        phase_configs: list[tuple[RoadmapPhase, str, str, str, list[RoadmapMilestone]]] = [
            (
                RoadmapPhase.PHASE_1,
                "FHIR-Native Integrations",
                "REDCap and Epic integrations leveraging existing FHIR R4 "
                "and SMART on FHIR capabilities for lowest-effort, highest-value impact.",
                "Both systems support FHIR R4 natively; platform already has "
                "FHIR compliance (95%) and SMART on FHIR (92%). Minimal new "
                "development needed.",
                [
                    RoadmapMilestone(
                        name="REDCap API Integration",
                        description="Complete REDCap REST API client with data dictionary sync",
                        target_week=4,
                        deliverables=[
                            "REDCap API client library",
                            "Data dictionary importer",
                            "Record push/pull pipeline",
                        ],
                    ),
                    RoadmapMilestone(
                        name="Epic SMART on FHIR Launch",
                        description="Complete Epic SMART on FHIR app with patient matching",
                        target_week=6,
                        deliverables=[
                            "SMART on FHIR app registration",
                            "Patient matching service",
                            "Clinical data sync pipeline",
                        ],
                    ),
                    RoadmapMilestone(
                        name="Phase 1 Validation",
                        description="End-to-end testing and sandbox validation",
                        target_week=8,
                        deliverables=[
                            "Integration test suite",
                            "Performance benchmarks",
                            "Documentation and runbooks",
                        ],
                    ),
                ],
            ),
            (
                RoadmapPhase.PHASE_2,
                "CDISC EDC Integration",
                "Medidata Rave integration requiring CDISC ODM adapter development. "
                "Builds foundational CDISC capability reusable in later phases.",
                "Medidata Rave is the dominant EDC in pharma; CDISC ODM support "
                "is a strategic capability. Phase 1 hardens FHIR infrastructure "
                "reused here.",
                [
                    RoadmapMilestone(
                        name="CDISC ODM Engine",
                        description="CDISC ODM-XML parser and generator",
                        target_week=4,
                        deliverables=[
                            "ODM-XML parser library",
                            "ODM-XML generator",
                            "CDISC domain mapping templates",
                        ],
                    ),
                    RoadmapMilestone(
                        name="Medidata API Integration",
                        description="Complete Medidata REST API client with study event sync",
                        target_week=7,
                        deliverables=[
                            "Medidata API client",
                            "Study event adapter",
                            "Subject enrollment sync",
                        ],
                    ),
                    RoadmapMilestone(
                        name="Phase 2 Validation",
                        description="End-to-end testing with Medidata sandbox",
                        target_week=10,
                        deliverables=[
                            "ODM round-trip validation",
                            "Clinical data exchange tests",
                            "Production readiness review",
                        ],
                    ),
                ],
            ),
            (
                RoadmapPhase.PHASE_3,
                "CTMS + Oncology EMR",
                "Veeva Vault CTMS and Flatiron OncoEMR integrations. "
                "Veeva uses REST API; Flatiron uses FHIR R4 with oncology extensions.",
                "Veeva and Flatiron are high-value targets for pharma partnerships. "
                "REST API and FHIR R4 patterns are already proven from earlier phases.",
                [
                    RoadmapMilestone(
                        name="Veeva Vault Integration",
                        description="Veeva REST API client with enrollment management",
                        target_week=6,
                        deliverables=[
                            "Veeva API client",
                            "Study/site/subject sync",
                            "Enrollment tracking pipeline",
                        ],
                    ),
                    RoadmapMilestone(
                        name="Flatiron OncoEMR Integration",
                        description="Flatiron FHIR R4 client with mCODE support",
                        target_week=6,
                        deliverables=[
                            "Oncology FHIR client",
                            "mCODE profile support",
                            "Tumor data mapper",
                        ],
                    ),
                    RoadmapMilestone(
                        name="Phase 3 Validation",
                        description="Cross-system integration testing",
                        target_week=8,
                        deliverables=[
                            "Multi-system test suite",
                            "Performance under load",
                            "Operational runbooks",
                        ],
                    ),
                ],
            ),
            (
                RoadmapPhase.PHASE_4,
                "Legacy CTMS Adapter",
                "Oracle Siebel CTMS integration requiring SOAP client and "
                "certificate authentication infrastructure.",
                "Oracle Siebel is the most complex integration due to legacy "
                "SOAP APIs and certificate auth. Deferred to final phase to "
                "avoid blocking higher-value integrations.",
                [
                    RoadmapMilestone(
                        name="SOAP Infrastructure",
                        description="SOAP client library with certificate auth",
                        target_week=4,
                        deliverables=[
                            "SOAP client library",
                            "Certificate management service",
                            "mTLS connectivity",
                        ],
                    ),
                    RoadmapMilestone(
                        name="Siebel Integration",
                        description="Complete Siebel business object mapping and sync",
                        target_week=9,
                        deliverables=[
                            "Siebel object mapper",
                            "Enrollment tracking adapter",
                            "Site management sync",
                        ],
                    ),
                    RoadmapMilestone(
                        name="Phase 4 Validation",
                        description="Legacy system integration testing",
                        target_week=12,
                        deliverables=[
                            "End-to-end validation",
                            "Error handling verification",
                            "Production deployment plan",
                        ],
                    ),
                ],
            ),
        ]

        for phase_enum, title, desc, rationale, milestones in phase_configs:
            systems = [
                s for s, p in self._system_phases.items() if p == phase_enum
            ]
            effort_estimates = [
                self._build_effort_estimate(s) for s in systems
            ]
            total_weeks = max(
                (e.total_weeks for e in effort_estimates), default=0
            )
            total_ew = sum(e.engineer_weeks for e in effort_estimates)

            phases.append(
                RoadmapPhaseDetail(
                    phase=phase_enum,
                    title=title,
                    description=desc,
                    systems=systems,
                    rationale=rationale,
                    total_weeks=total_weeks,
                    total_engineer_weeks=total_ew,
                    milestones=milestones,
                    effort_estimates=effort_estimates,
                )
            )

        grand_total_weeks = sum(p.total_weeks for p in phases)
        grand_total_ew = sum(p.total_engineer_weeks for p in phases)

        return IntegrationRoadmap(
            generated_at=datetime.now(timezone.utc),
            total_systems=len(self._specs),
            total_weeks=grand_total_weeks,
            total_engineer_weeks=grand_total_ew,
            phases=phases,
        )

    def _build_effort_estimate(self, system: IntegrationSystem) -> EffortEstimate:
        """Build effort estimate for a system."""
        data = self._effort_data.get(system)
        if data is None:
            return EffortEstimate(
                system=system,
                display_name=self._specs[system].display_name,
                phase=self._system_phases.get(system, RoadmapPhase.PHASE_4),
                total_weeks=0,
                engineering_headcount=0,
                engineer_weeks=0,
            )
        total_weeks, headcount, ew, tasks, risks, deps = data
        return EffortEstimate(
            system=system,
            display_name=self._specs[system].display_name,
            phase=self._system_phases.get(system, RoadmapPhase.PHASE_4),
            total_weeks=total_weeks,
            engineering_headcount=headcount,
            engineer_weeks=ew,
            tasks=tasks,
            risks=risks,
            dependencies=deps,
        )

    # ------------------------------------------------------------------
    # Data mapping
    # ------------------------------------------------------------------

    def get_data_mapping(self, system: str) -> list[DataMappingTemplate] | None:
        """Get data mapping templates for a specific system."""
        try:
            key = IntegrationSystem(system)
        except ValueError:
            return None

        if key not in self._data_mappings:
            return None

        return self._data_mappings[key]

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def get_summary(self) -> IntegrationSummary:
        """Get overall integration status summary."""
        # Systems by category
        cat_counts: dict[str, int] = {}
        for spec in self._specs.values():
            cat = spec.category.value
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        # Systems by phase
        phase_systems: dict[str, list[str]] = {}
        for system, phase in self._system_phases.items():
            phase_key = phase.value
            if phase_key not in phase_systems:
                phase_systems[phase_key] = []
            phase_systems[phase_key].append(
                self._specs[system].display_name
            )

        # Readiness per system
        readiness_scores: dict[str, float] = {}
        for system in self._specs:
            assessment = self.assess_readiness(system.value)
            if assessment:
                readiness_scores[assessment.display_name] = (
                    assessment.overall_readiness_pct
                )

        avg_readiness = (
            sum(readiness_scores.values()) / len(readiness_scores)
            if readiness_scores
            else 0.0
        )

        highest = max(readiness_scores, key=readiness_scores.get) if readiness_scores else None  # type: ignore[arg-type]
        lowest = min(readiness_scores, key=readiness_scores.get) if readiness_scores else None  # type: ignore[arg-type]

        # Total effort
        roadmap = self.get_roadmap()

        # Implemented vs needs-development capabilities
        implemented = [
            name for name, (status, *_) in self._capabilities.items()
            if status == ReadinessStatus.IMPLEMENTED
        ]
        gaps = [
            name for name, (status, *_) in self._capabilities.items()
            if status in (ReadinessStatus.NEEDS_DEVELOPMENT, ReadinessStatus.PARTIAL)
        ]

        return IntegrationSummary(
            generated_at=datetime.now(timezone.utc),
            total_systems=len(self._specs),
            systems_by_category=cat_counts,
            average_readiness_pct=round(avg_readiness, 1),
            systems_by_phase=phase_systems,
            total_effort_weeks=roadmap.total_engineer_weeks,
            total_calendar_weeks=roadmap.total_weeks,
            highest_readiness_system=highest,
            lowest_readiness_system=lowest,
            implemented_capabilities=implemented,
            gaps_requiring_development=gaps,
        )
