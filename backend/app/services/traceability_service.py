"""Requirements Traceability Service (VP-Quality-3).

Provides comprehensive requirements traceability tracking across the full
lifecycle: requirements -> design -> code -> tests -> validation.

Pre-populated with 40+ requirements mapped to actual platform source files.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.schemas.traceability import (
    AffectedRequirement,
    CoverageLevel,
    CoverageReport,
    CoverageSummary,
    GapItem,
    GapReport,
    ImpactAnalysisRequest,
    ImpactAnalysisResponse,
    MatrixRow,
    RequirementCategory,
    RequirementCreate,
    RequirementPriority,
    RequirementResponse,
    RequirementStatus,
    RequirementUpdate,
    TraceabilityMatrix,
    TraceLink,
    TraceLevelKind,
    TraceLinks,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal data record
# ---------------------------------------------------------------------------


class _RequirementRecord:
    """Internal mutable record for a requirement."""

    __slots__ = (
        "id",
        "title",
        "description",
        "category",
        "priority",
        "status",
        "source",
        "trace_links",
        "created_at",
        "updated_at",
    )

    def __init__(
        self,
        id: str,
        title: str,
        description: str,
        category: RequirementCategory,
        priority: RequirementPriority,
        status: RequirementStatus,
        source: str,
        trace_links: TraceLinks | None = None,
    ) -> None:
        self.id = id
        self.title = title
        self.description = description
        self.category = category
        self.priority = priority
        self.status = status
        self.source = source
        self.trace_links = trace_links or TraceLinks()
        now = datetime.now(timezone.utc)
        self.created_at = now
        self.updated_at = now


# ---------------------------------------------------------------------------
# Coverage helpers
# ---------------------------------------------------------------------------


def _compute_coverage(links: TraceLinks) -> CoverageLevel:
    """Determine coverage level from trace links."""
    has_code = len(links.code_refs) > 0
    has_tests = len(links.test_refs) > 0
    has_validation = len(links.validation_refs) > 0

    if has_code and has_tests and has_validation:
        return CoverageLevel.FULLY_COVERED
    if has_code and has_tests:
        return CoverageLevel.TESTED_UNVALIDATED
    if has_code:
        return CoverageLevel.IMPLEMENTED_UNTESTED
    return CoverageLevel.NOT_IMPLEMENTED


def _record_to_response(rec: _RequirementRecord) -> RequirementResponse:
    """Convert internal record to API response."""
    return RequirementResponse(
        id=rec.id,
        title=rec.title,
        description=rec.description,
        category=rec.category,
        priority=rec.priority,
        status=rec.status,
        source=rec.source,
        trace_links=rec.trace_links,
        coverage_level=_compute_coverage(rec.trace_links),
        created_at=rec.created_at,
        updated_at=rec.updated_at,
    )


# ---------------------------------------------------------------------------
# Pre-populated seed requirements
# ---------------------------------------------------------------------------


def _build_seed_requirements() -> list[_RequirementRecord]:
    """Build 40+ pre-populated requirements mapped to actual platform code."""
    seeds: list[_RequirementRecord] = []

    def _add(
        id: str,
        title: str,
        description: str,
        category: RequirementCategory,
        priority: RequirementPriority,
        status: RequirementStatus,
        source: str,
        design_refs: list[tuple[str, str]] | None = None,
        code_refs: list[tuple[str, str]] | None = None,
        test_refs: list[tuple[str, str]] | None = None,
        validation_refs: list[tuple[str, str]] | None = None,
    ) -> None:
        links = TraceLinks(
            design_refs=[TraceLink(ref=r, description=d, verified=True) for r, d in (design_refs or [])],
            code_refs=[TraceLink(ref=r, description=d, verified=True) for r, d in (code_refs or [])],
            test_refs=[TraceLink(ref=r, description=d, verified=True) for r, d in (test_refs or [])],
            validation_refs=[TraceLink(ref=r, description=d, verified=True) for r, d in (validation_refs or [])],
        )
        seeds.append(
            _RequirementRecord(
                id=id,
                title=title,
                description=description,
                category=category,
                priority=priority,
                status=status,
                source=source,
                trace_links=links,
            )
        )

    # -----------------------------------------------------------------------
    # FUNCTIONAL requirements
    # -----------------------------------------------------------------------
    _add(
        "REQ-FUNC-001",
        "FHIR R4 resource import",
        "System shall import clinical data from FHIR R4 resources including Patient, Condition, Observation, MedicationRequest, Procedure, and DiagnosticReport.",
        RequirementCategory.FUNCTIONAL,
        RequirementPriority.P1,
        RequirementStatus.VALIDATED,
        "HL7 FHIR R4 Specification",
        design_refs=[("docs/architecture/fhir_import.md", "FHIR import architecture")],
        code_refs=[
            ("backend/app/services/fhir_import.py", "FHIR import service"),
            ("backend/app/api/fhir.py", "FHIR API endpoints"),
        ],
        test_refs=[("backend/tests/test_fhir_import_comprehensive.py", "Comprehensive FHIR import tests")],
        validation_refs=[("docs/quality/validation/fhir_r4_conformance.md", "FHIR R4 conformance validation")],
    )

    _add(
        "REQ-FUNC-002",
        "Trial eligibility screening",
        "System shall screen patients against clinical trial inclusion/exclusion criteria and produce scored eligibility results.",
        RequirementCategory.FUNCTIONAL,
        RequirementPriority.P1,
        RequirementStatus.TESTED,
        "Clinical Operations",
        design_refs=[("specs/trial_screening.md", "Trial screening design spec")],
        code_refs=[
            ("backend/app/services/trial_eligibility_service.py", "Trial eligibility engine"),
            ("backend/app/api/trials.py", "Trials API endpoints"),
        ],
        test_refs=[
            ("backend/tests/test_trial_eligibility.py", "Trial eligibility unit tests"),
            ("backend/tests/test_trial_screening_comprehensive.py", "Comprehensive screening tests"),
        ],
    )

    _add(
        "REQ-FUNC-003",
        "NLP clinical entity extraction",
        "System shall extract clinical entities (conditions, medications, procedures, lab results) from unstructured clinical text using rule-based and ML approaches.",
        RequirementCategory.FUNCTIONAL,
        RequirementPriority.P1,
        RequirementStatus.VALIDATED,
        "Clinical Informatics",
        design_refs=[("docs/architecture/nlp_pipeline.md", "NLP pipeline architecture")],
        code_refs=[
            ("backend/app/services/nlp.py", "Core NLP service"),
            ("backend/app/services/nlp_rule_based.py", "Rule-based NLP extraction"),
            ("backend/app/services/nlp_ensemble.py", "NLP ensemble service"),
            ("backend/app/services/nlp_entity_service.py", "Entity extraction service"),
            ("backend/app/services/extraction_pipeline.py", "Extraction pipeline"),
        ],
        test_refs=[
            ("backend/tests/test_nlp_service.py", "NLP service tests"),
            ("backend/tests/test_nlp_rule_based.py", "Rule-based NLP tests"),
            ("backend/tests/test_nlp_advanced.py", "Advanced NLP tests"),
            ("backend/tests/test_nlp_coverage.py", "NLP coverage tests"),
        ],
        validation_refs=[("docs/quality/validation/nlp_accuracy.md", "NLP extraction accuracy validation")],
    )

    _add(
        "REQ-FUNC-004",
        "OMOP concept mapping",
        "System shall map extracted clinical entities to standardized OMOP CDM concepts using vocabulary lookup and fuzzy matching.",
        RequirementCategory.FUNCTIONAL,
        RequirementPriority.P1,
        RequirementStatus.VALIDATED,
        "OHDSI OMOP CDM v5.4",
        design_refs=[("docs/architecture/omop_mapping.md", "OMOP mapping architecture")],
        code_refs=[
            ("backend/app/services/mapping.py", "Core mapping service"),
            ("backend/app/services/mapping_db.py", "Database-backed mapping"),
            ("backend/app/services/mapping_sql.py", "SQL mapping queries"),
        ],
        test_refs=[
            ("backend/tests/test_mapping_service.py", "Mapping service tests"),
            ("backend/tests/test_mapping_accuracy.py", "Mapping accuracy tests"),
        ],
        validation_refs=[("docs/quality/validation/omop_mapping_accuracy.md", "OMOP mapping accuracy validation")],
    )

    _add(
        "REQ-FUNC-005",
        "Clinical fact construction",
        "System shall construct normalized ClinicalFact records from extracted mentions with full provenance tracking.",
        RequirementCategory.FUNCTIONAL,
        RequirementPriority.P1,
        RequirementStatus.TESTED,
        "Clinical Informatics",
        code_refs=[
            ("backend/app/services/fact_builder.py", "Fact builder service"),
            ("backend/app/services/fact_builder_db.py", "DB-backed fact builder"),
        ],
        test_refs=[
            ("backend/tests/test_fact_builder.py", "Fact builder tests"),
            ("backend/tests/test_fact_builder_service.py", "Fact builder service tests"),
            ("backend/tests/test_fact_builder_db.py", "Fact builder DB tests"),
        ],
    )

    _add(
        "REQ-FUNC-006",
        "Knowledge graph construction",
        "System shall build a patient-centric knowledge graph from clinical facts with typed nodes and edges.",
        RequirementCategory.FUNCTIONAL,
        RequirementPriority.P2,
        RequirementStatus.TESTED,
        "Clinical Informatics",
        code_refs=[
            ("backend/app/services/graph_builder.py", "Graph builder service"),
            ("backend/app/services/graph_builder_db.py", "DB-backed graph builder"),
        ],
        test_refs=[
            ("backend/tests/test_graph_builder.py", "Graph builder tests"),
            ("backend/tests/test_graph_builder_service.py", "Graph builder service tests"),
            ("backend/tests/test_graph_builder_db.py", "Graph builder DB tests"),
        ],
    )

    _add(
        "REQ-FUNC-007",
        "FHIR R4 resource export",
        "System shall export clinical data as valid FHIR R4 resources for interoperability.",
        RequirementCategory.FUNCTIONAL,
        RequirementPriority.P2,
        RequirementStatus.IMPLEMENTED,
        "HL7 FHIR R4 Specification",
        code_refs=[
            ("backend/app/services/fhir_exporter.py", "FHIR export service"),
            ("backend/app/api/export.py", "Export API endpoints"),
        ],
    )

    _add(
        "REQ-FUNC-008",
        "Drug safety signal detection",
        "System shall detect drug-drug interactions and adverse event signals from patient clinical data.",
        RequirementCategory.FUNCTIONAL,
        RequirementPriority.P1,
        RequirementStatus.VALIDATED,
        "FDA Drug Safety",
        design_refs=[("docs/architecture/drug_safety.md", "Drug safety architecture")],
        code_refs=[
            ("backend/app/services/drug_safety.py", "Drug safety service"),
            ("backend/app/api/drug_safety.py", "Drug safety API"),
        ],
        test_refs=[("backend/tests/test_drug_safety.py", "Drug safety tests")],
        validation_refs=[("docs/quality/validation/drug_interaction_accuracy.md", "DDI detection validation")],
    )

    _add(
        "REQ-FUNC-009",
        "Clinical calculator engine",
        "System shall provide validated clinical calculators (CHA2DS2-VASc, MELD, Wells, etc.) for clinical decision support.",
        RequirementCategory.FUNCTIONAL,
        RequirementPriority.P2,
        RequirementStatus.TESTED,
        "Clinical Decision Support",
        code_refs=[
            ("backend/app/services/clinical_calculators.py", "Clinical calculator service"),
            ("backend/app/api/calculators.py", "Calculators API"),
        ],
        test_refs=[("backend/tests/test_nlp_service.py", "Calculator validation tests")],
    )

    _add(
        "REQ-FUNC-010",
        "Differential diagnosis support",
        "System shall generate ranked differential diagnoses based on patient symptoms and findings.",
        RequirementCategory.FUNCTIONAL,
        RequirementPriority.P2,
        RequirementStatus.IMPLEMENTED,
        "Clinical Decision Support",
        code_refs=[
            ("backend/app/services/differential_diagnosis.py", "DDx service"),
            ("backend/app/api/differential_diagnosis.py", "DDx API"),
        ],
    )

    _add(
        "REQ-FUNC-011",
        "Patient consent management",
        "System shall manage patient consent records for data use, trial participation, and PHI access.",
        RequirementCategory.FUNCTIONAL,
        RequirementPriority.P1,
        RequirementStatus.TESTED,
        "HIPAA / IRB Requirements",
        code_refs=[
            ("backend/app/services/consent_service.py", "Consent management service"),
            ("backend/app/api/consent.py", "Consent API"),
        ],
        test_refs=[("backend/tests/test_consent_service.py", "Consent service tests")],
    )

    _add(
        "REQ-FUNC-012",
        "Document ingestion pipeline",
        "System shall ingest clinical documents in multiple formats and extract structured data via NLP pipeline.",
        RequirementCategory.FUNCTIONAL,
        RequirementPriority.P1,
        RequirementStatus.TESTED,
        "Clinical Operations",
        code_refs=[
            ("backend/app/services/extraction_pipeline.py", "Document extraction pipeline"),
            ("backend/app/api/documents/", "Documents API package"),
        ],
        test_refs=[("backend/tests/test_nlp_service.py", "Document processing tests")],
    )

    _add(
        "REQ-FUNC-013",
        "Bulk patient screening",
        "System shall support batch screening of patient cohorts against trial criteria.",
        RequirementCategory.FUNCTIONAL,
        RequirementPriority.P2,
        RequirementStatus.IMPLEMENTED,
        "Clinical Operations",
        code_refs=[
            ("backend/app/api/bulk_screening.py", "Bulk screening API"),
        ],
    )

    _add(
        "REQ-FUNC-014",
        "Screening result analytics",
        "System shall provide analytics on screening results including pass/fail rates and screen failure reasons.",
        RequirementCategory.FUNCTIONAL,
        RequirementPriority.P2,
        RequirementStatus.IMPLEMENTED,
        "Clinical Operations",
        code_refs=[
            ("backend/app/api/screening_results.py", "Screening results API"),
            ("backend/app/api/screen_failure_analytics.py", "Screen failure analytics"),
        ],
    )

    _add(
        "REQ-FUNC-015",
        "Patient diversity analytics",
        "System shall track and report on patient diversity metrics for clinical trial recruitment.",
        RequirementCategory.FUNCTIONAL,
        RequirementPriority.P2,
        RequirementStatus.IMPLEMENTED,
        "FDA Diversity Guidelines",
        code_refs=[
            ("backend/app/api/diversity_analytics.py", "Diversity analytics API"),
        ],
    )

    _add(
        "REQ-FUNC-016",
        "Cohort management",
        "System shall support creation, modification, and querying of patient cohorts.",
        RequirementCategory.FUNCTIONAL,
        RequirementPriority.P2,
        RequirementStatus.IMPLEMENTED,
        "Clinical Operations",
        code_refs=[
            ("backend/app/api/cohorts.py", "Cohorts API"),
            ("backend/app/api/cohort_phenotypes.py", "Cohort phenotypes API"),
        ],
    )

    _add(
        "REQ-FUNC-017",
        "GraphRAG clinical querying",
        "System shall support natural language querying of the clinical knowledge graph using RAG.",
        RequirementCategory.FUNCTIONAL,
        RequirementPriority.P3,
        RequirementStatus.IMPLEMENTED,
        "Clinical Informatics",
        code_refs=[
            ("backend/app/api/graph_rag.py", "GraphRAG API"),
        ],
    )

    _add(
        "REQ-FUNC-018",
        "CDISC data standards support",
        "System shall support CDISC SDTM/ADaM data standards for regulatory submissions.",
        RequirementCategory.FUNCTIONAL,
        RequirementPriority.P2,
        RequirementStatus.IMPLEMENTED,
        "FDA/CDISC",
        code_refs=[
            ("backend/app/api/cdisc.py", "CDISC API"),
        ],
    )

    _add(
        "REQ-FUNC-019",
        "Site management",
        "System shall manage clinical trial site information and performance metrics.",
        RequirementCategory.FUNCTIONAL,
        RequirementPriority.P2,
        RequirementStatus.IMPLEMENTED,
        "Clinical Operations",
        code_refs=[
            ("backend/app/api/sites.py", "Sites API"),
        ],
    )

    _add(
        "REQ-FUNC-020",
        "ROI dashboard",
        "System shall provide return-on-investment analytics for trial recruitment optimization.",
        RequirementCategory.FUNCTIONAL,
        RequirementPriority.P3,
        RequirementStatus.IMPLEMENTED,
        "Business Operations",
        code_refs=[
            ("backend/app/api/roi_dashboard.py", "ROI dashboard API"),
        ],
    )

    # -----------------------------------------------------------------------
    # SECURITY requirements
    # -----------------------------------------------------------------------
    _add(
        "REQ-SEC-001",
        "Role-based access control",
        "System shall enforce role-based access control (RBAC) on all API endpoints with fine-grained permissions.",
        RequirementCategory.SECURITY,
        RequirementPriority.P1,
        RequirementStatus.VALIDATED,
        "HIPAA Security Rule",
        design_refs=[("docs/architecture/rbac.md", "RBAC design")],
        code_refs=[
            ("backend/app/api/middleware/auth_middleware.py", "Auth middleware with RBAC"),
            ("backend/app/api/auth.py", "Authentication API"),
        ],
        test_refs=[("backend/tests/test_audit.py", "Auth/RBAC tests")],
        validation_refs=[("docs/quality/validation/rbac_validation.md", "RBAC validation evidence")],
    )

    _add(
        "REQ-SEC-002",
        "Audit logging",
        "System shall maintain immutable audit logs for all data access and modifications with user identity, timestamp, and action details.",
        RequirementCategory.SECURITY,
        RequirementPriority.P1,
        RequirementStatus.VALIDATED,
        "21 CFR Part 11 / HIPAA",
        design_refs=[("docs/architecture/audit.md", "Audit logging architecture")],
        code_refs=[
            ("backend/app/services/audit_service.py", "Audit service"),
            ("backend/app/services/audit_integrity_service.py", "Audit integrity service"),
            ("backend/app/api/middleware/audit.py", "Audit middleware"),
        ],
        test_refs=[("backend/tests/test_audit.py", "Audit logging tests")],
        validation_refs=[("docs/quality/validation/audit_completeness.md", "Audit completeness validation")],
    )

    _add(
        "REQ-SEC-003",
        "PHI data protection",
        "System shall identify, track, and protect Protected Health Information (PHI) across all data flows.",
        RequirementCategory.SECURITY,
        RequirementPriority.P1,
        RequirementStatus.TESTED,
        "HIPAA Privacy Rule",
        code_refs=[
            ("backend/app/services/phi_audit_service.py", "PHI audit service"),
        ],
        test_refs=[("backend/tests/test_phi_audit.py", "PHI audit tests")],
    )

    _add(
        "REQ-SEC-004",
        "Authentication and session management",
        "System shall implement secure authentication with session management, token rotation, and multi-factor support.",
        RequirementCategory.SECURITY,
        RequirementPriority.P1,
        RequirementStatus.IMPLEMENTED,
        "NIST 800-63",
        code_refs=[
            ("backend/app/api/auth.py", "Authentication API"),
            ("backend/app/api/auth_sessions.py", "Session management API"),
        ],
    )

    _add(
        "REQ-SEC-005",
        "Secret management and rotation",
        "System shall manage and automatically rotate secrets, API keys, and credentials.",
        RequirementCategory.SECURITY,
        RequirementPriority.P1,
        RequirementStatus.TESTED,
        "SOC 2 / NIST 800-53",
        code_refs=[
            ("backend/app/api/secret_rotation.py", "Secret rotation API"),
        ],
        test_refs=[("backend/tests/test_secret_rotation.py", "Secret rotation tests")],
    )

    _add(
        "REQ-SEC-006",
        "Data encryption at rest and in transit",
        "System shall encrypt all PHI and sensitive data at rest (AES-256) and in transit (TLS 1.2+).",
        RequirementCategory.SECURITY,
        RequirementPriority.P1,
        RequirementStatus.DESIGNED,
        "HIPAA Security Rule",
        design_refs=[("docs/architecture/encryption.md", "Encryption architecture")],
    )

    _add(
        "REQ-SEC-007",
        "Security headers",
        "System shall set appropriate security headers (CSP, HSTS, X-Frame-Options, etc.) on all responses.",
        RequirementCategory.SECURITY,
        RequirementPriority.P2,
        RequirementStatus.IMPLEMENTED,
        "OWASP",
        code_refs=[
            ("backend/app/api/middleware/security_headers.py", "Security headers middleware"),
        ],
    )

    _add(
        "REQ-SEC-008",
        "Rate limiting",
        "System shall enforce rate limits on API endpoints to prevent abuse and DoS attacks.",
        RequirementCategory.SECURITY,
        RequirementPriority.P2,
        RequirementStatus.IMPLEMENTED,
        "OWASP",
        code_refs=[
            ("backend/app/api/middleware/rate_limit.py", "Rate limiting middleware"),
        ],
    )

    # -----------------------------------------------------------------------
    # REGULATORY requirements
    # -----------------------------------------------------------------------
    _add(
        "REQ-REG-001",
        "HIPAA compliance",
        "System shall comply with HIPAA Privacy and Security Rules including consent management, BAA support, and data deletion capabilities.",
        RequirementCategory.REGULATORY,
        RequirementPriority.P1,
        RequirementStatus.TESTED,
        "HIPAA (45 CFR Parts 160, 164)",
        design_refs=[("docs/legal/hipaa_compliance.md", "HIPAA compliance framework")],
        code_refs=[
            ("backend/app/services/consent_service.py", "Consent management"),
            ("backend/app/services/deletion_service.py", "Data deletion service"),
            ("backend/app/services/phi_audit_service.py", "PHI audit"),
        ],
        test_refs=[
            ("backend/tests/test_consent_service.py", "Consent tests"),
            ("backend/tests/test_phi_audit.py", "PHI audit tests"),
        ],
    )

    _add(
        "REQ-REG-002",
        "21 CFR Part 11 electronic records",
        "System shall comply with 21 CFR Part 11 for electronic records including audit trails, electronic signatures, and access controls.",
        RequirementCategory.REGULATORY,
        RequirementPriority.P1,
        RequirementStatus.TESTED,
        "FDA 21 CFR Part 11",
        design_refs=[("docs/legal/21cfr11_compliance.md", "21 CFR Part 11 compliance")],
        code_refs=[
            ("backend/app/services/audit_service.py", "Audit trail service"),
            ("backend/app/services/audit_integrity_service.py", "Audit integrity verification"),
        ],
        test_refs=[("backend/tests/test_audit.py", "Audit compliance tests")],
    )

    _add(
        "REQ-REG-003",
        "SOC 2 compliance",
        "System shall implement SOC 2 Type II controls for security, availability, processing integrity, confidentiality, and privacy.",
        RequirementCategory.REGULATORY,
        RequirementPriority.P1,
        RequirementStatus.TESTED,
        "AICPA SOC 2",
        code_refs=[
            ("backend/app/services/soc2_service.py", "SOC 2 compliance service"),
            ("backend/app/api/soc2_compliance.py", "SOC 2 API"),
        ],
        test_refs=[("backend/tests/test_soc2_compliance.py", "SOC 2 compliance tests")],
    )

    _add(
        "REQ-REG-004",
        "FHIR validation compliance",
        "System shall validate all FHIR resources against HL7 FHIR R4 profiles and implementation guides.",
        RequirementCategory.REGULATORY,
        RequirementPriority.P2,
        RequirementStatus.IMPLEMENTED,
        "HL7 FHIR R4",
        code_refs=[
            ("backend/app/api/fhir_validation.py", "FHIR validation API"),
        ],
    )

    _add(
        "REQ-REG-005",
        "Data governance framework",
        "System shall implement a data governance framework with data use agreements, retention policies, and access tracking.",
        RequirementCategory.REGULATORY,
        RequirementPriority.P1,
        RequirementStatus.IMPLEMENTED,
        "HIPAA / GDPR",
        code_refs=[
            ("backend/app/api/data_governance.py", "Data governance API"),
        ],
    )

    _add(
        "REQ-REG-006",
        "Terminology governance",
        "System shall provide terminology governance capabilities for managing clinical vocabularies and value sets.",
        RequirementCategory.REGULATORY,
        RequirementPriority.P2,
        RequirementStatus.IMPLEMENTED,
        "OHDSI / HL7",
        code_refs=[
            ("backend/app/api/terminology_governance.py", "Terminology governance API"),
            ("backend/app/api/valuesets.py", "Value sets API"),
        ],
    )

    _add(
        "REQ-REG-007",
        "Criteria fidelity monitoring",
        "System shall monitor fidelity of trial eligibility criteria implementation against protocol specifications.",
        RequirementCategory.REGULATORY,
        RequirementPriority.P2,
        RequirementStatus.IMPLEMENTED,
        "ICH GCP",
        code_refs=[
            ("backend/app/api/criteria_fidelity.py", "Criteria fidelity API"),
        ],
    )

    # -----------------------------------------------------------------------
    # NON-FUNCTIONAL requirements (performance, reliability, usability)
    # -----------------------------------------------------------------------
    _add(
        "REQ-PERF-001",
        "API latency under 2s at p95",
        "System shall maintain API response time below 2 seconds at the 95th percentile for all standard operations.",
        RequirementCategory.NON_FUNCTIONAL,
        RequirementPriority.P1,
        RequirementStatus.IMPLEMENTED,
        "SLA Requirements",
        code_refs=[
            ("backend/app/api/middleware/sli_collector.py", "SLI metrics collection"),
            ("backend/app/api/metrics.py", "Metrics API"),
        ],
    )

    _add(
        "REQ-PERF-002",
        "Horizontal scalability",
        "System shall support horizontal scaling via containerization and stateless service design.",
        RequirementCategory.NON_FUNCTIONAL,
        RequirementPriority.P2,
        RequirementStatus.TESTED,
        "Infrastructure Requirements",
        design_refs=[("docs/architecture/scalability.md", "Scalability architecture")],
        code_refs=[
            ("backend/app/api/scalability_audit.py", "Scalability audit API"),
        ],
        test_refs=[("backend/tests/test_scalability_audit.py", "Scalability tests")],
    )

    _add(
        "REQ-PERF-003",
        "Data quality monitoring",
        "System shall continuously monitor data quality metrics including completeness, consistency, and accuracy.",
        RequirementCategory.NON_FUNCTIONAL,
        RequirementPriority.P2,
        RequirementStatus.TESTED,
        "Data Quality Standards",
        code_refs=[
            ("backend/app/api/data_completeness.py", "Data completeness API"),
            ("backend/app/api/data_consistency.py", "Data consistency API"),
            ("backend/app/api/data_quality_dqd.py", "Data quality dashboard API"),
            ("backend/app/api/mapping_quality.py", "Mapping quality API"),
        ],
        test_refs=[("backend/tests/test_mapping_quality.py", "Mapping quality tests")],
    )

    _add(
        "REQ-PERF-004",
        "Observability and monitoring",
        "System shall provide comprehensive observability including distributed tracing, metrics collection, and alerting.",
        RequirementCategory.NON_FUNCTIONAL,
        RequirementPriority.P2,
        RequirementStatus.TESTED,
        "SRE Requirements",
        code_refs=[
            ("backend/app/api/observability.py", "Observability API"),
            ("backend/app/api/alert_rules.py", "Alert rules API"),
        ],
        test_refs=[("backend/tests/test_observability.py", "Observability tests")],
    )

    _add(
        "REQ-PERF-005",
        "Model drift detection",
        "System shall detect and alert on model drift for ML-based NLP and prediction models.",
        RequirementCategory.NON_FUNCTIONAL,
        RequirementPriority.P2,
        RequirementStatus.TESTED,
        "MLOps Requirements",
        code_refs=[
            ("backend/app/api/drift_detection.py", "Drift detection API"),
        ],
        test_refs=[("backend/tests/test_drift_detection.py", "Drift detection tests")],
    )

    _add(
        "REQ-PERF-006",
        "Fairness and bias auditing",
        "System shall audit ML models for fairness across demographic groups and detect potential biases.",
        RequirementCategory.NON_FUNCTIONAL,
        RequirementPriority.P2,
        RequirementStatus.TESTED,
        "FDA AI/ML Guidance",
        code_refs=[
            ("backend/app/api/fairness_audit.py", "Fairness audit API"),
        ],
        test_refs=[("backend/tests/test_fairness_audit.py", "Fairness audit tests")],
    )

    _add(
        "REQ-PERF-007",
        "ETL validation",
        "System shall validate ETL pipeline outputs for data integrity and transformation accuracy.",
        RequirementCategory.NON_FUNCTIONAL,
        RequirementPriority.P2,
        RequirementStatus.IMPLEMENTED,
        "Data Engineering",
        code_refs=[
            ("backend/app/api/etl_validation.py", "ETL validation API"),
            ("backend/app/api/etl.py", "ETL API"),
        ],
    )

    _add(
        "REQ-PERF-008",
        "Backup and recovery",
        "System shall maintain regular backups and support point-in-time recovery for all critical data.",
        RequirementCategory.NON_FUNCTIONAL,
        RequirementPriority.P1,
        RequirementStatus.IMPLEMENTED,
        "Business Continuity",
        code_refs=[
            ("backend/app/api/backup_status.py", "Backup status API"),
        ],
    )

    _add(
        "REQ-PERF-009",
        "Incident management",
        "System shall track and manage operational incidents with severity classification and escalation procedures.",
        RequirementCategory.NON_FUNCTIONAL,
        RequirementPriority.P2,
        RequirementStatus.IMPLEMENTED,
        "ITIL / SRE",
        code_refs=[
            ("backend/app/api/incidents.py", "Incidents API"),
        ],
    )

    _add(
        "REQ-PERF-010",
        "Quality management (CAPA)",
        "System shall support Corrective and Preventive Action (CAPA) tracking and IQ/OQ/PQ qualification protocols.",
        RequirementCategory.NON_FUNCTIONAL,
        RequirementPriority.P1,
        RequirementStatus.TESTED,
        "GxP / Quality Management",
        code_refs=[
            ("backend/app/api/quality_management.py", "Quality management API"),
        ],
        test_refs=[("backend/tests/test_quality_management.py", "Quality management tests")],
    )

    _add(
        "REQ-PERF-011",
        "Pipeline versioning and lineage",
        "System shall track pipeline versions and data lineage for reproducibility and auditing.",
        RequirementCategory.NON_FUNCTIONAL,
        RequirementPriority.P2,
        RequirementStatus.IMPLEMENTED,
        "Data Engineering",
        code_refs=[
            ("backend/app/api/pipeline_version.py", "Pipeline version API"),
            ("backend/app/api/lineage.py", "Data lineage API"),
        ],
    )

    _add(
        "REQ-PERF-012",
        "Validation study framework",
        "System shall support formal validation studies with gold standard comparison and statistical analysis.",
        RequirementCategory.NON_FUNCTIONAL,
        RequirementPriority.P2,
        RequirementStatus.IMPLEMENTED,
        "Clinical Validation",
        code_refs=[
            ("backend/app/api/validation_study.py", "Validation study API"),
            ("backend/app/api/gold_standard.py", "Gold standard API"),
        ],
    )

    return seeds


# ---------------------------------------------------------------------------
# Traceability Service
# ---------------------------------------------------------------------------


class TraceabilityService:
    """Service for managing requirements traceability across the full lifecycle.

    Tracks requirements -> design -> code -> test -> validation linkages
    and provides coverage analysis, gap detection, and impact analysis.
    """

    def __init__(self) -> None:
        self._requirements: dict[str, _RequirementRecord] = {}
        self._next_seq: dict[str, int] = {
            "FUNC": 100,
            "SEC": 100,
            "REG": 100,
            "PERF": 100,
        }
        # Load seed requirements
        for rec in _build_seed_requirements():
            self._requirements[rec.id] = rec
            # Track highest sequence per prefix
            prefix = rec.id.split("-")[1]  # e.g. FUNC, SEC, REG, PERF
            try:
                seq = int(rec.id.split("-")[2])
                if seq >= self._next_seq.get(prefix, 0):
                    self._next_seq[prefix] = seq + 1
            except (ValueError, IndexError):
                pass

        logger.info(
            "TraceabilityService initialized with %d requirements",
            len(self._requirements),
        )

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def list_requirements(
        self,
        category: RequirementCategory | None = None,
        priority: RequirementPriority | None = None,
        status: RequirementStatus | None = None,
        coverage: CoverageLevel | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[RequirementResponse], int]:
        """List requirements with optional filters and pagination."""
        records = list(self._requirements.values())

        # Apply filters
        if category is not None:
            records = [r for r in records if r.category == category]
        if priority is not None:
            records = [r for r in records if r.priority == priority]
        if status is not None:
            records = [r for r in records if r.status == status]
        if coverage is not None:
            records = [r for r in records if _compute_coverage(r.trace_links) == coverage]

        # Sort by ID
        records.sort(key=lambda r: r.id)
        total = len(records)

        # Paginate
        start = (page - 1) * page_size
        end = start + page_size
        page_records = records[start:end]

        return [_record_to_response(r) for r in page_records], total

    def get_requirement(self, requirement_id: str) -> RequirementResponse | None:
        """Get a single requirement by ID."""
        rec = self._requirements.get(requirement_id)
        if rec is None:
            return None
        return _record_to_response(rec)

    def create_requirement(self, data: RequirementCreate) -> RequirementResponse:
        """Create a new requirement."""
        if data.id and data.id in self._requirements:
            raise ValueError(f"Requirement {data.id} already exists")

        # Generate ID if not provided
        req_id = data.id
        if not req_id:
            prefix_map = {
                RequirementCategory.FUNCTIONAL: "FUNC",
                RequirementCategory.NON_FUNCTIONAL: "PERF",
                RequirementCategory.REGULATORY: "REG",
                RequirementCategory.SECURITY: "SEC",
            }
            prefix = prefix_map[data.category]
            seq = self._next_seq.get(prefix, 100)
            req_id = f"REQ-{prefix}-{seq:03d}"
            self._next_seq[prefix] = seq + 1

        rec = _RequirementRecord(
            id=req_id,
            title=data.title,
            description=data.description,
            category=data.category,
            priority=data.priority,
            status=data.status,
            source=data.source,
            trace_links=data.trace_links,
        )
        self._requirements[req_id] = rec
        logger.info("Created requirement %s: %s", req_id, data.title)
        return _record_to_response(rec)

    def update_requirement(self, requirement_id: str, data: RequirementUpdate) -> RequirementResponse | None:
        """Update an existing requirement."""
        rec = self._requirements.get(requirement_id)
        if rec is None:
            return None

        if data.title is not None:
            rec.title = data.title
        if data.description is not None:
            rec.description = data.description
        if data.category is not None:
            rec.category = data.category
        if data.priority is not None:
            rec.priority = data.priority
        if data.status is not None:
            rec.status = data.status
        if data.source is not None:
            rec.source = data.source
        if data.trace_links is not None:
            rec.trace_links = data.trace_links
        rec.updated_at = datetime.now(timezone.utc)

        logger.info("Updated requirement %s", requirement_id)
        return _record_to_response(rec)

    def delete_requirement(self, requirement_id: str) -> bool:
        """Delete a requirement. Returns True if deleted."""
        if requirement_id in self._requirements:
            del self._requirements[requirement_id]
            return True
        return False

    # ------------------------------------------------------------------
    # Coverage analysis
    # ------------------------------------------------------------------

    def get_coverage_report(self) -> CoverageReport:
        """Generate comprehensive coverage analysis report."""
        summary = self._compute_coverage_summary()
        all_reqs = [_record_to_response(r) for r in sorted(self._requirements.values(), key=lambda r: r.id)]
        return CoverageReport(
            summary=summary,
            requirements=all_reqs,
            generated_at=datetime.now(timezone.utc),
        )

    def _compute_coverage_summary(self) -> CoverageSummary:
        """Compute coverage summary statistics."""
        total = len(self._requirements)
        counts = {
            CoverageLevel.FULLY_COVERED: 0,
            CoverageLevel.TESTED_UNVALIDATED: 0,
            CoverageLevel.IMPLEMENTED_UNTESTED: 0,
            CoverageLevel.NOT_IMPLEMENTED: 0,
        }
        by_category: dict[str, dict[str, int]] = {}
        by_priority: dict[str, dict[str, int]] = {}

        for rec in self._requirements.values():
            level = _compute_coverage(rec.trace_links)
            counts[level] += 1

            # Category breakdown
            cat = rec.category.value
            if cat not in by_category:
                by_category[cat] = {lv.value: 0 for lv in CoverageLevel}
            by_category[cat][level.value] += 1

            # Priority breakdown
            pri = rec.priority.value
            if pri not in by_priority:
                by_priority[pri] = {lv.value: 0 for lv in CoverageLevel}
            by_priority[pri][level.value] += 1

        pct = (counts[CoverageLevel.FULLY_COVERED] / total * 100) if total > 0 else 0.0

        return CoverageSummary(
            total_requirements=total,
            fully_covered=counts[CoverageLevel.FULLY_COVERED],
            tested_unvalidated=counts[CoverageLevel.TESTED_UNVALIDATED],
            implemented_untested=counts[CoverageLevel.IMPLEMENTED_UNTESTED],
            not_implemented=counts[CoverageLevel.NOT_IMPLEMENTED],
            coverage_percentage=round(pct, 1),
            by_category=by_category,
            by_priority=by_priority,
        )

    # ------------------------------------------------------------------
    # Gap analysis
    # ------------------------------------------------------------------

    def get_gap_report(self) -> GapReport:
        """Identify requirements with incomplete traceability."""
        gaps: list[GapItem] = []

        for rec in sorted(self._requirements.values(), key=lambda r: r.id):
            level = _compute_coverage(rec.trace_links)
            if level == CoverageLevel.FULLY_COVERED:
                continue

            missing: list[TraceLevelKind] = []
            if not rec.trace_links.design_refs:
                missing.append(TraceLevelKind.DESIGN)
            if not rec.trace_links.code_refs:
                missing.append(TraceLevelKind.CODE)
            if not rec.trace_links.test_refs:
                missing.append(TraceLevelKind.TEST)
            if not rec.trace_links.validation_refs:
                missing.append(TraceLevelKind.VALIDATION)

            recommendation = self._generate_gap_recommendation(rec, missing)

            gaps.append(
                GapItem(
                    requirement_id=rec.id,
                    requirement_title=rec.title,
                    category=rec.category,
                    priority=rec.priority,
                    missing_levels=missing,
                    coverage_level=level,
                    recommendation=recommendation,
                )
            )

        critical = sum(1 for g in gaps if g.priority == RequirementPriority.P1)

        return GapReport(
            gaps=gaps,
            total_gaps=len(gaps),
            critical_gaps=critical,
            generated_at=datetime.now(timezone.utc),
        )

    def _generate_gap_recommendation(
        self,
        rec: _RequirementRecord,
        missing: list[TraceLevelKind],
    ) -> str:
        """Generate a recommendation string for closing a gap."""
        parts: list[str] = []
        if TraceLevelKind.CODE in missing:
            parts.append("Implement the requirement in code")
        if TraceLevelKind.TEST in missing:
            parts.append("Add automated tests")
        if TraceLevelKind.DESIGN in missing:
            parts.append("Create design documentation")
        if TraceLevelKind.VALIDATION in missing:
            parts.append("Complete formal validation")

        priority_prefix = ""
        if rec.priority in (RequirementPriority.P1, RequirementPriority.P2):
            priority_prefix = f"[{rec.priority.value} PRIORITY] "

        return f"{priority_prefix}{'; '.join(parts)}."

    # ------------------------------------------------------------------
    # Impact analysis
    # ------------------------------------------------------------------

    def analyze_impact(self, request: ImpactAnalysisRequest) -> ImpactAnalysisResponse:
        """Analyze impact of code changes on requirements."""
        affected: list[AffectedRequirement] = []
        changed_set = set(request.changed_files)

        for rec in sorted(self._requirements.values(), key=lambda r: r.id):
            matched_code: list[str] = []
            matched_tests: list[str] = []

            for link in rec.trace_links.code_refs:
                for changed in changed_set:
                    if self._paths_match(link.ref, changed):
                        matched_code.append(link.ref)
                        break

            for link in rec.trace_links.test_refs:
                for changed in changed_set:
                    if self._paths_match(link.ref, changed):
                        matched_tests.append(link.ref)
                        break

            if matched_code or matched_tests:
                risk = self._assess_risk(rec, matched_code, matched_tests)
                affected.append(
                    AffectedRequirement(
                        requirement_id=rec.id,
                        requirement_title=rec.title,
                        category=rec.category,
                        priority=rec.priority,
                        status=rec.status,
                        matched_code_refs=matched_code,
                        matched_test_refs=matched_tests,
                        risk_level=risk,
                    )
                )

        risk_summary: dict[str, int] = {}
        for a in affected:
            risk_summary[a.risk_level] = risk_summary.get(a.risk_level, 0) + 1

        recommendations = self._generate_impact_recommendations(affected)

        return ImpactAnalysisResponse(
            changed_files=request.changed_files,
            affected_requirements=affected,
            total_affected=len(affected),
            risk_summary=risk_summary,
            recommendations=recommendations,
            generated_at=datetime.now(timezone.utc),
        )

    def _paths_match(self, ref_path: str, changed_path: str) -> bool:
        """Check if a reference path matches a changed file path.

        Handles both exact matches and partial path matches (e.g. a directory
        reference matching files within it).
        """
        # Normalize: strip leading "./" or "/"
        ref_norm = ref_path.lstrip("./")
        changed_norm = changed_path.lstrip("./")

        # Exact match
        if ref_norm == changed_norm:
            return True

        # Directory match: ref ends with "/" and changed starts with it
        if ref_norm.endswith("/") and changed_norm.startswith(ref_norm):
            return True

        # File within referenced directory
        if changed_norm.startswith(ref_norm + "/"):
            return True

        # Base filename match (e.g. "fhir_import.py" matches "backend/app/services/fhir_import.py")
        ref_base = ref_norm.rsplit("/", 1)[-1] if "/" in ref_norm else ref_norm
        changed_base = changed_norm.rsplit("/", 1)[-1] if "/" in changed_norm else changed_norm
        if ref_base == changed_base and ref_base:
            return True

        return False

    def _assess_risk(
        self,
        rec: _RequirementRecord,
        matched_code: list[str],
        matched_tests: list[str],
    ) -> str:
        """Assess risk level of a change on a requirement."""
        # P1 + code change + no test change = CRITICAL
        if rec.priority == RequirementPriority.P1 and matched_code and not matched_tests:
            return "CRITICAL"
        # P1 + code change + test change = HIGH
        if rec.priority == RequirementPriority.P1 and matched_code:
            return "HIGH"
        # P2 + code change = MEDIUM
        if rec.priority == RequirementPriority.P2 and matched_code:
            return "MEDIUM"
        # Test-only changes or lower priority
        return "LOW"

    def _generate_impact_recommendations(self, affected: list[AffectedRequirement]) -> list[str]:
        """Generate recommendations based on impact analysis."""
        recommendations: list[str] = []
        critical = [a for a in affected if a.risk_level == "CRITICAL"]
        high = [a for a in affected if a.risk_level == "HIGH"]

        if critical:
            ids = ", ".join(a.requirement_id for a in critical)
            recommendations.append(
                f"CRITICAL: {len(critical)} P1 requirement(s) affected without test coverage update ({ids}). "
                "Run full regression tests before merging."
            )
        if high:
            ids = ", ".join(a.requirement_id for a in high)
            recommendations.append(
                f"HIGH: {len(high)} P1 requirement(s) affected with test changes ({ids}). "
                "Verify test coverage is adequate."
            )
        if not critical and not high:
            recommendations.append("No critical or high-risk impacts identified. Standard review process applies.")

        return recommendations

    # ------------------------------------------------------------------
    # Full matrix
    # ------------------------------------------------------------------

    def get_matrix(self) -> TraceabilityMatrix:
        """Generate the full traceability matrix."""
        rows: list[MatrixRow] = []

        for rec in sorted(self._requirements.values(), key=lambda r: r.id):
            level = _compute_coverage(rec.trace_links)
            rows.append(
                MatrixRow(
                    requirement_id=rec.id,
                    requirement_title=rec.title,
                    category=rec.category,
                    priority=rec.priority,
                    status=rec.status,
                    design_count=len(rec.trace_links.design_refs),
                    code_count=len(rec.trace_links.code_refs),
                    test_count=len(rec.trace_links.test_refs),
                    validation_count=len(rec.trace_links.validation_refs),
                    coverage_level=level,
                    design_refs=[l.ref for l in rec.trace_links.design_refs],
                    code_refs=[l.ref for l in rec.trace_links.code_refs],
                    test_refs=[l.ref for l in rec.trace_links.test_refs],
                    validation_refs=[l.ref for l in rec.trace_links.validation_refs],
                )
            )

        summary = self._compute_coverage_summary()
        return TraceabilityMatrix(
            rows=rows,
            summary=summary,
            generated_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return service statistics."""
        summary = self._compute_coverage_summary()
        return {
            "total_requirements": summary.total_requirements,
            "fully_covered": summary.fully_covered,
            "coverage_percentage": summary.coverage_percentage,
            "critical_gaps": sum(
                1
                for r in self._requirements.values()
                if r.priority == RequirementPriority.P1
                and _compute_coverage(r.trace_links) != CoverageLevel.FULLY_COVERED
            ),
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_service_instance: TraceabilityService | None = None


def get_traceability_service() -> TraceabilityService:
    """Get or create the singleton TraceabilityService."""
    global _service_instance
    if _service_instance is None:
        _service_instance = TraceabilityService()
    return _service_instance
