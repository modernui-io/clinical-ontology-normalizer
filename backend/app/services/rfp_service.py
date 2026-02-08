"""RFP Response Template and Competitive Positioning Service.

Partnership-1: Generates customized RFP responses for clinical trial
patient recruitment partnerships. Provides competitive positioning,
capability catalogs, case studies, and requirement matching.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.schemas.rfp_management import (
    CapabilityCatalogResponse,
    CaseStudy,
    CaseStudyListResponse,
    CaseStudyMetric,
    CaseStudyTherapeuticArea,
    CompetitiveCategory,
    CompetitiveMatrixResponse,
    CompetitorScore,
    DifferentiationScore,
    MaturityLevel,
    PlatformCapability,
    PricingTier,
    PricingTierDetail,
    RFPGeneratedResponse,
    RFPGenerateRequest,
    RFPTemplateListResponse,
    RFPTemplateSection,
    RequirementMatch,
    RequirementMatchResponse,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_rfp_service: RFPService | None = None


def get_rfp_service() -> RFPService:
    """Return global singleton RFPService instance."""
    global _rfp_service
    if _rfp_service is None:
        _rfp_service = RFPService()
    return _rfp_service


def reset_rfp_service() -> None:
    """Reset the global singleton (for testing)."""
    global _rfp_service
    _rfp_service = None


# ---------------------------------------------------------------------------
# Constants: requirement matching keywords
# ---------------------------------------------------------------------------

_REQUIREMENT_KEYWORDS: dict[str, list[str]] = {
    "fhir_integration": [
        "fhir", "hl7", "interoperability", "health information exchange",
        "data exchange", "api integration", "ehr integration",
    ],
    "nlp_extraction": [
        "nlp", "natural language", "text extraction", "clinical text",
        "unstructured data", "entity extraction", "named entity",
    ],
    "trial_screening": [
        "screening", "eligibility", "inclusion criteria", "exclusion criteria",
        "patient matching", "trial matching", "recruitment",
    ],
    "omop_mapping": [
        "omop", "cdm", "common data model", "terminology mapping",
        "concept mapping", "standardization", "vocabulary",
    ],
    "knowledge_graph": [
        "knowledge graph", "graph database", "neo4j", "relationship",
        "ontology", "semantic", "linked data",
    ],
    "security_compliance": [
        "hipaa", "security", "compliance", "soc 2", "hitrust",
        "encryption", "audit", "access control", "phi",
    ],
    "analytics_reporting": [
        "analytics", "reporting", "dashboard", "metrics",
        "screen failure", "diversity", "kpi", "roi",
    ],
    "data_management": [
        "data lineage", "consent", "dua", "data use agreement",
        "provenance", "data governance", "data quality",
    ],
    "smart_on_fhir": [
        "smart on fhir", "smart", "cds hooks", "clinical decision",
        "ehr launch", "app launch",
    ],
    "quality_validation": [
        "validation", "iq/oq/pq", "capa", "quality", "gxp",
        "21 cfr part 11", "audit trail",
    ],
    "deployment_ops": [
        "deployment", "cloud", "on-premise", "kubernetes", "docker",
        "scalability", "high availability", "sla",
    ],
    "diversity_inclusion": [
        "diversity", "inclusion", "underrepresented", "health equity",
        "demographic", "race", "ethnicity",
    ],
    "phenotyping": [
        "phenotyping", "cohort", "phenotype", "computable phenotype",
        "patient identification",
    ],
    "real_world_data": [
        "real world data", "rwd", "real world evidence", "rwe",
        "observational", "registry",
    ],
    "consent_management": [
        "consent", "e-consent", "informed consent", "consent management",
        "irb",
    ],
}


class RFPService:
    """Generates and manages RFP responses for partnership pitches.

    Provides:
    - Pre-populated RFP template sections
    - Competitive positioning matrix
    - Platform capability catalog
    - Case study templates
    - Requirement matching engine
    - Customized RFP response generation
    """

    def __init__(self) -> None:
        self._capabilities = self._build_capabilities()
        self._templates = self._build_templates()
        self._case_studies = self._build_case_studies()
        self._competitive_matrix = self._build_competitive_matrix()
        self._pricing_tiers = self._build_pricing_tiers()
        logger.info(
            "RFPService initialized: %d capabilities, %d sections, %d case studies",
            len(self._capabilities),
            len(self._templates),
            len(self._case_studies),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return service statistics."""
        return {
            "capabilities": len(self._capabilities),
            "template_sections": len(self._templates),
            "case_studies": len(self._case_studies),
            "competitive_categories": len(self._competitive_matrix.categories),
            "pricing_tiers": len(self._pricing_tiers),
        }

    # -- Templates -----------------------------------------------------

    def list_templates(self) -> RFPTemplateListResponse:
        """Return all RFP template sections."""
        return RFPTemplateListResponse(
            total_sections=len(self._templates),
            sections=list(self._templates.values()),
        )

    def get_template_section(self, section_id: str) -> RFPTemplateSection | None:
        """Return a specific template section by ID."""
        return self._templates.get(section_id)

    def get_section_ids(self) -> list[str]:
        """Return the list of valid section IDs."""
        return list(self._templates.keys())

    # -- Capabilities --------------------------------------------------

    def get_capability_catalog(self) -> CapabilityCatalogResponse:
        """Return the full platform capability catalog."""
        by_maturity: dict[str, int] = {}
        for cap in self._capabilities:
            level = cap.maturity.value
            by_maturity[level] = by_maturity.get(level, 0) + 1
        return CapabilityCatalogResponse(
            total_capabilities=len(self._capabilities),
            by_maturity=by_maturity,
            capabilities=list(self._capabilities),
        )

    def get_capability_by_id(self, cap_id: str) -> PlatformCapability | None:
        """Lookup a single capability by its ID."""
        for cap in self._capabilities:
            if cap.id == cap_id:
                return cap
        return None

    # -- Competitive matrix --------------------------------------------

    def get_competitive_matrix(self) -> CompetitiveMatrixResponse:
        """Return the competitive positioning matrix."""
        return self._competitive_matrix

    # -- Case studies --------------------------------------------------

    def get_case_studies(self) -> CaseStudyListResponse:
        """Return all case study templates."""
        return CaseStudyListResponse(
            total=len(self._case_studies),
            case_studies=list(self._case_studies),
        )

    def get_case_study_by_id(self, study_id: str) -> CaseStudy | None:
        """Lookup a single case study by ID."""
        for cs in self._case_studies:
            if cs.id == study_id:
                return cs
        return None

    # -- Requirement matching ------------------------------------------

    def match_requirements(
        self, requirements: list[str]
    ) -> RequirementMatchResponse:
        """Match a list of requirements to platform capabilities."""
        matches: list[RequirementMatch] = []
        matched_count = 0
        partial_count = 0
        gap_count = 0

        for req in requirements:
            req_lower = req.lower()
            matched_caps: list[PlatformCapability] = []
            best_confidence = 0.0

            # Keyword-based matching
            for cap_id, keywords in _REQUIREMENT_KEYWORDS.items():
                score = sum(1 for kw in keywords if kw in req_lower)
                if score > 0:
                    confidence = min(score / 3.0, 1.0)
                    cap = self.get_capability_by_id(cap_id)
                    if cap is not None:
                        matched_caps.append(cap)
                        best_confidence = max(best_confidence, confidence)

            # Also do a brute-force scan of all capabilities
            for cap in self._capabilities:
                if cap not in matched_caps:
                    name_words = cap.name.lower().split()
                    if any(w in req_lower for w in name_words if len(w) > 3):
                        matched_caps.append(cap)
                        best_confidence = max(best_confidence, 0.5)

            is_matched = best_confidence >= 0.5
            is_partial = 0.0 < best_confidence < 0.5

            gap_notes = ""
            if not is_matched and not is_partial:
                gap_notes = (
                    f"No direct capability match for: {req}. "
                    "May require custom development or partner integration."
                )
                gap_count += 1
            elif is_partial:
                gap_notes = "Partial match - capability exists but may need enhancement."
                partial_count += 1
            else:
                matched_count += 1

            matches.append(
                RequirementMatch(
                    requirement=req,
                    matched=is_matched,
                    matched_capabilities=matched_caps,
                    confidence=round(best_confidence, 2),
                    gap_notes=gap_notes,
                )
            )

        total = len(requirements)
        coverage = matched_count / total if total > 0 else 0.0

        return RequirementMatchResponse(
            total_requirements=total,
            matched_count=matched_count,
            partial_count=partial_count,
            gap_count=gap_count,
            coverage_score=round(coverage, 2),
            matches=matches,
        )

    # -- RFP generation ------------------------------------------------

    def generate_rfp_response(
        self, request: RFPGenerateRequest
    ) -> RFPGeneratedResponse:
        """Generate a customized RFP response."""
        now = datetime.now(timezone.utc)

        # Select sections
        if request.sections:
            sections = [
                self._templates[sid]
                for sid in request.sections
                if sid in self._templates
            ]
        else:
            sections = list(self._templates.values())

        # Filter pricing section if not requested
        if not request.include_pricing:
            sections = [s for s in sections if s.section_id != "pricing"]

        # Match requirements to capabilities
        requirement_match = (
            self.match_requirements(request.requirements)
            if request.requirements
            else None
        )

        matched_capabilities = []
        coverage = 0.0
        if requirement_match:
            coverage = requirement_match.coverage_score
            seen_ids: set[str] = set()
            for m in requirement_match.matches:
                for cap in m.matched_capabilities:
                    if cap.id not in seen_ids:
                        matched_capabilities.append(cap)
                        seen_ids.add(cap.id)

        # Select relevant case studies
        case_studies: list[CaseStudy] = []
        if request.include_case_studies:
            ta_lower = request.therapeutic_area.lower()
            for cs in self._case_studies:
                if (
                    ta_lower in cs.therapeutic_area.value.lower()
                    or ta_lower in cs.indication.lower()
                    or not ta_lower
                ):
                    case_studies.append(cs)

        # Competitive matrix
        competitive = (
            self._competitive_matrix
            if request.include_competitive_matrix
            else None
        )

        return RFPGeneratedResponse(
            generated_at=now,
            sponsor_name=request.sponsor_name,
            therapeutic_area=request.therapeutic_area,
            trial_phase=request.trial_phase,
            sections=sections,
            matched_capabilities=matched_capabilities,
            case_studies=case_studies,
            competitive_matrix=competitive,
            requirement_coverage=coverage,
        )

    # -- Pricing -------------------------------------------------------

    def get_pricing_tiers(self) -> list[PricingTierDetail]:
        """Return all pricing tiers."""
        return list(self._pricing_tiers)

    # ------------------------------------------------------------------
    # Data builders (private)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_capabilities() -> list[PlatformCapability]:
        """Build the full platform capability catalog."""
        return [
            PlatformCapability(
                id="fhir_integration",
                name="FHIR R4 Integration",
                category="Integration",
                description=(
                    "Full FHIR R4 resource support via Metriport for "
                    "bi-directional health data exchange with EHR systems."
                ),
                maturity=MaturityLevel.PRODUCTION,
                key_features=[
                    "Metriport FHIR API integration",
                    "Patient, Condition, Observation, MedicationRequest support",
                    "Bulk FHIR import pipeline",
                    "FHIR validation with HL7 profiles",
                    "Webhook-driven data sync",
                ],
                standards=["FHIR R4", "HL7v2", "USCDI v3"],
            ),
            PlatformCapability(
                id="nlp_extraction",
                name="Clinical NLP Extraction",
                category="Clinical Capabilities",
                description=(
                    "Multi-strategy NLP pipeline for extracting clinical "
                    "entities from unstructured text with assertion detection, "
                    "temporality, and experiencer classification."
                ),
                maturity=MaturityLevel.PRODUCTION,
                key_features=[
                    "Rule-based and ML ensemble extraction",
                    "Assertion detection (positive/negated/possible)",
                    "Temporality classification",
                    "Experiencer identification (patient/family)",
                    "Value extraction (lab results, vitals)",
                    "Section-aware processing",
                ],
                standards=["OMOP CDM", "SNOMED CT", "ICD-10-CM"],
            ),
            PlatformCapability(
                id="trial_screening",
                name="Automated Trial Screening",
                category="Clinical Capabilities",
                description=(
                    "Automated patient-trial matching engine that evaluates "
                    "inclusion/exclusion criteria against patient clinical "
                    "profiles derived from FHIR and NLP data."
                ),
                maturity=MaturityLevel.PRODUCTION,
                key_features=[
                    "Real-time eligibility evaluation",
                    "Criteria-level pass/fail detail",
                    "Bulk screening across patient cohorts",
                    "Screen failure analytics",
                    "Criteria fidelity tracking",
                ],
                standards=["CDISC ODM", "FHIR PlanDefinition"],
            ),
            PlatformCapability(
                id="omop_mapping",
                name="OMOP CDM Mapping",
                category="Data Management",
                description=(
                    "Automated mapping of clinical concepts to OMOP Common "
                    "Data Model with multi-vocabulary support and confidence "
                    "scoring."
                ),
                maturity=MaturityLevel.PRODUCTION,
                key_features=[
                    "SNOMED CT, ICD-10, RxNorm, LOINC, CPT mapping",
                    "Fuzzy and exact matching strategies",
                    "Mapping quality scoring",
                    "Vocabulary governance workflows",
                    "ETL validation pipeline",
                ],
                standards=["OMOP CDM v5.4", "OHDSI"],
            ),
            PlatformCapability(
                id="knowledge_graph",
                name="Clinical Knowledge Graph",
                category="Analytics",
                description=(
                    "Patient-centric knowledge graph with clinical fact "
                    "construction, relationship inference, and graph-powered "
                    "reasoning over clinical data."
                ),
                maturity=MaturityLevel.PILOT,
                key_features=[
                    "Neo4j graph persistence",
                    "Graph-based clinical reasoning",
                    "GraphRAG for contextual queries",
                    "Temporal relationship modeling",
                    "Cross-patient similarity analysis",
                ],
                standards=["RDF", "OMOP CDM"],
            ),
            PlatformCapability(
                id="security_compliance",
                name="Security & Compliance",
                category="Security",
                description=(
                    "Enterprise-grade security controls with HIPAA compliance, "
                    "SOC 2 readiness, and audit trail management."
                ),
                maturity=MaturityLevel.PRODUCTION,
                key_features=[
                    "HIPAA-compliant audit logging",
                    "Role-based access control (RBAC)",
                    "API key authentication",
                    "PHI access tracking",
                    "Secret rotation management",
                    "SOC 2 Type II readiness controls",
                ],
                standards=["HIPAA", "SOC 2", "HITRUST CSF"],
            ),
            PlatformCapability(
                id="analytics_reporting",
                name="Analytics & Reporting",
                category="Analytics",
                description=(
                    "Comprehensive analytics suite covering screen failure "
                    "analysis, diversity reporting, ROI dashboards, and "
                    "recruitment trend tracking."
                ),
                maturity=MaturityLevel.PRODUCTION,
                key_features=[
                    "Screen failure root cause analysis",
                    "Diversity and inclusion analytics",
                    "ROI dashboard with enrollment projections",
                    "Criteria fidelity tracking",
                    "Site performance comparison",
                    "Time-series trend analysis",
                ],
                standards=["ICH E6(R3)", "FDA Diversity Guidance"],
            ),
            PlatformCapability(
                id="data_management",
                name="Data Management & Lineage",
                category="Data Management",
                description=(
                    "End-to-end data lineage tracking, consent management, "
                    "DUA support, and data governance controls."
                ),
                maturity=MaturityLevel.PRODUCTION,
                key_features=[
                    "Full data lineage from source to derived fact",
                    "Consent management with audit trail",
                    "Data Use Agreement (DUA) tracking",
                    "Data quality dashboards (DQD)",
                    "Data governance policies",
                    "Provenance chain tracking",
                ],
                standards=["OMOP CDM", "GDPR", "Common Rule"],
            ),
            PlatformCapability(
                id="smart_on_fhir",
                name="SMART on FHIR & CDS Hooks",
                category="Integration",
                description=(
                    "SMART on FHIR app launch framework and CDS Hooks "
                    "integration for EHR-embedded clinical decision support."
                ),
                maturity=MaturityLevel.PILOT,
                key_features=[
                    "SMART App Launch (EHR and standalone)",
                    "CDS Hooks service registration",
                    "Patient-context launch",
                    "OAuth 2.0 / PKCE authorization",
                    "Trial alert cards in EHR workflow",
                ],
                standards=["SMART App Launch IG", "CDS Hooks 2.0"],
            ),
            PlatformCapability(
                id="quality_validation",
                name="Quality & Validation",
                category="Quality",
                description=(
                    "IQ/OQ/PQ validation framework with CAPA system, "
                    "validation study management, and quality management "
                    "controls aligned to GxP requirements."
                ),
                maturity=MaturityLevel.PRODUCTION,
                key_features=[
                    "IQ/OQ/PQ validation protocols",
                    "CAPA tracking and resolution",
                    "Validation study management",
                    "Gold standard test sets",
                    "Quality management system (QMS)",
                    "Drift detection and alerting",
                ],
                standards=["21 CFR Part 11", "GAMP 5", "ICH Q10"],
            ),
            PlatformCapability(
                id="deployment_ops",
                name="Deployment & Operations",
                category="Infrastructure",
                description=(
                    "Flexible deployment options with Docker, Kubernetes, "
                    "and cloud-native infrastructure support."
                ),
                maturity=MaturityLevel.PRODUCTION,
                key_features=[
                    "Docker Compose for development",
                    "Kubernetes manifests for production",
                    "Horizontal auto-scaling",
                    "Health checks and readiness probes",
                    "Structured logging and observability",
                    "Backup and disaster recovery",
                ],
                standards=["SOC 2", "FedRAMP (roadmap)"],
            ),
            PlatformCapability(
                id="diversity_inclusion",
                name="Diversity & Inclusion Analytics",
                category="Analytics",
                description=(
                    "FDA-aligned diversity analytics for clinical trial "
                    "enrollment with demographic reporting and equity scoring."
                ),
                maturity=MaturityLevel.PRODUCTION,
                key_features=[
                    "Demographic enrollment tracking",
                    "Diversity score calculation",
                    "Underrepresentation alerts",
                    "Site-level diversity comparison",
                    "FDA diversity plan alignment",
                ],
                standards=["FDA Diversity Guidance 2024", "ICH E8(R1)"],
            ),
            PlatformCapability(
                id="phenotyping",
                name="Computable Phenotyping",
                category="Clinical Capabilities",
                description=(
                    "Computable phenotype definitions for patient cohort "
                    "identification using standardized clinical data."
                ),
                maturity=MaturityLevel.PILOT,
                key_features=[
                    "Phenotype library management",
                    "Cohort-phenotype association",
                    "OMOP-based phenotype definitions",
                    "Phenotype validation against gold standards",
                ],
                standards=["OMOP CDM", "PheKB"],
            ),
            PlatformCapability(
                id="real_world_data",
                name="Real-World Data Integration",
                category="Data Management",
                description=(
                    "Integration of real-world clinical data from EHR, "
                    "claims, and registry sources for evidence generation."
                ),
                maturity=MaturityLevel.PILOT,
                key_features=[
                    "Multi-source data federation",
                    "Data source registry and cataloging",
                    "ETL pipeline management",
                    "Data completeness scoring",
                    "Consistency validation",
                ],
                standards=["OMOP CDM", "USCDI", "TEFCA (roadmap)"],
            ),
            PlatformCapability(
                id="consent_management",
                name="Consent Management",
                category="Data Management",
                description=(
                    "Electronic consent capture, tracking, and enforcement "
                    "with IRB alignment and regulatory compliance."
                ),
                maturity=MaturityLevel.PRODUCTION,
                key_features=[
                    "E-consent capture and storage",
                    "Consent status tracking",
                    "Consent-gated data access",
                    "IRB protocol linkage",
                    "Consent audit trail",
                ],
                standards=["Common Rule", "HIPAA", "21 CFR Part 50"],
            ),
        ]

    @staticmethod
    def _build_templates() -> dict[str, RFPTemplateSection]:
        """Build all RFP template sections."""
        sections = [
            RFPTemplateSection(
                section_id="executive_summary",
                title="Executive Summary",
                content=(
                    "The Clinical Ontology Normalizer platform accelerates "
                    "clinical trial patient recruitment by combining FHIR-native "
                    "data integration, advanced NLP extraction, OMOP-standardized "
                    "terminology mapping, and automated eligibility screening. "
                    "Our platform processes real-world clinical data from EHR "
                    "systems to identify and match eligible patients in real time, "
                    "reducing screen failure rates and accelerating enrollment "
                    "timelines."
                ),
                key_points=[
                    "FHIR R4 native integration via Metriport for seamless EHR data access",
                    "Automated patient-trial matching with criteria-level transparency",
                    "OMOP CDM standardization for cross-site data harmonization",
                    "Screen failure analytics to optimize protocol design",
                    "FDA-aligned diversity analytics for inclusive enrollment",
                    "Enterprise security with HIPAA compliance and SOC 2 readiness",
                ],
                evidence=[
                    "Sub-second screening across 1000+ patients per trial",
                    "15+ clinical data domains mapped to OMOP CDM",
                    "Criteria-level pass/fail detail for every screening decision",
                    "Proven integration with major EHR platforms via FHIR R4",
                ],
            ),
            RFPTemplateSection(
                section_id="technical_architecture",
                title="Technical Architecture",
                content=(
                    "Built on a modern microservices architecture with FastAPI "
                    "(Python), Next.js (TypeScript), PostgreSQL, Redis, and "
                    "optional Neo4j graph persistence. The platform is designed "
                    "for horizontal scalability, high availability, and seamless "
                    "integration with healthcare IT ecosystems through FHIR R4 "
                    "and SMART on FHIR standards."
                ),
                key_points=[
                    "FastAPI backend with async processing for high throughput",
                    "FHIR R4 compliant data model with Metriport integration",
                    "OMOP CDM v5.4 for standardized clinical data representation",
                    "Neo4j knowledge graph for clinical relationship modeling",
                    "Redis-backed job queue for async screening pipelines",
                    "Kubernetes-ready with Docker Compose for development",
                ],
                evidence=[
                    "726+ API endpoints across clinical, analytics, and administrative domains",
                    "187 service modules for comprehensive clinical data processing",
                    "Full FHIR R4 resource support: Patient, Condition, Observation, MedicationRequest",
                    "SMART App Launch and CDS Hooks integration for EHR embedding",
                ],
            ),
            RFPTemplateSection(
                section_id="clinical_capabilities",
                title="Clinical Capabilities",
                content=(
                    "Our clinical NLP engine extracts structured data from "
                    "unstructured clinical notes using a multi-strategy ensemble "
                    "approach. Extracted mentions are mapped to OMOP concepts, "
                    "built into clinical facts with full provenance, and used for "
                    "automated trial eligibility screening."
                ),
                key_points=[
                    "Multi-strategy NLP: rule-based, pattern matching, and ML ensemble",
                    "Assertion detection: positive, negated, possible, conditional",
                    "Temporality classification for historical vs. current conditions",
                    "Value extraction for lab results, vitals, and measurements",
                    "Automated eligibility screening with criteria-level detail",
                    "Computable phenotyping for cohort identification",
                ],
                evidence=[
                    "Extraction across conditions, medications, procedures, lab results, vitals",
                    "Support for 15+ OMOP clinical domains",
                    "Criteria fidelity tracking for protocol optimization",
                    "Bulk screening pipeline for large patient cohorts",
                ],
            ),
            RFPTemplateSection(
                section_id="security_compliance",
                title="Security & Compliance",
                content=(
                    "The platform implements enterprise-grade security controls "
                    "aligned with HIPAA requirements and SOC 2 Type II readiness. "
                    "All PHI access is logged, role-based access controls are "
                    "enforced, and data encryption is applied at rest and in transit."
                ),
                key_points=[
                    "HIPAA-compliant audit logging for all PHI access",
                    "Role-based access control (RBAC) with fine-grained permissions",
                    "API key authentication with rate limiting",
                    "TLS 1.2+ encryption in transit, AES-256 at rest",
                    "SOC 2 Type II readiness controls implemented",
                    "HITRUST CSF certification roadmap",
                    "Secret rotation management",
                ],
                evidence=[
                    "Complete audit trail for every data access event",
                    "Automated SOC 2 compliance scoring and gap analysis",
                    "Security headers aligned with OWASP recommendations",
                    "Rate limiting and request throttling for API protection",
                ],
            ),
            RFPTemplateSection(
                section_id="data_management",
                title="Data Management",
                content=(
                    "Comprehensive data management with end-to-end lineage "
                    "tracking, consent management, Data Use Agreement (DUA) "
                    "support, and data quality controls. Every derived fact "
                    "maintains a complete provenance chain back to its source "
                    "document."
                ),
                key_points=[
                    "Full data lineage from source document to derived clinical fact",
                    "Consent management with consent-gated data access",
                    "Data Use Agreement (DUA) tracking and enforcement",
                    "Data quality dashboards with completeness and consistency metrics",
                    "Data governance policies with automated enforcement",
                    "Provenance chain for regulatory audit support",
                ],
                evidence=[
                    "Every clinical fact traceable to source mention and document",
                    "Automated data quality scoring per OHDSI DQD framework",
                    "Consent status checked before any data access operation",
                    "Data governance policy enforcement at API layer",
                ],
            ),
            RFPTemplateSection(
                section_id="integration",
                title="Integration Capabilities",
                content=(
                    "Native FHIR R4 integration via Metriport enables seamless "
                    "data exchange with EHR systems. SMART on FHIR app launch "
                    "framework and CDS Hooks enable EHR-embedded workflows for "
                    "trial alerting and recruitment."
                ),
                key_points=[
                    "Metriport FHIR R4 API for multi-EHR data access",
                    "SMART on FHIR app launch (EHR and standalone)",
                    "CDS Hooks for real-time trial alerts in EHR workflow",
                    "Webhook-driven data synchronization",
                    "RESTful API with OpenAPI 3.0 documentation",
                    "Bulk FHIR export for large-scale data transfers",
                ],
                evidence=[
                    "Live FHIR integration across major EHR platforms",
                    "CDS Hooks service registration for trial-alert cards",
                    "726+ documented API endpoints with OpenAPI schemas",
                    "Webhook processing for real-time clinical data updates",
                ],
            ),
            RFPTemplateSection(
                section_id="analytics",
                title="Analytics & Reporting",
                content=(
                    "Purpose-built analytics for clinical trial recruitment "
                    "covering screen failure analysis, diversity reporting, "
                    "ROI modeling, and enrollment trend tracking. All analytics "
                    "are available via API and dashboard UI."
                ),
                key_points=[
                    "Screen failure root cause analysis with criteria-level detail",
                    "FDA-aligned diversity and inclusion analytics",
                    "ROI dashboard with enrollment projections and cost analysis",
                    "Criteria fidelity tracking for protocol optimization",
                    "Site performance benchmarking",
                    "A/B testing framework for recruitment strategies",
                ],
                evidence=[
                    "Screen failure analytics across multiple trial types",
                    "Diversity scoring aligned with FDA 2024 guidance",
                    "ROI projections with configurable conversion rates",
                    "Time-series enrollment trends with daily/weekly granularity",
                ],
            ),
            RFPTemplateSection(
                section_id="quality",
                title="Quality & Validation",
                content=(
                    "Quality management system aligned with GxP requirements, "
                    "featuring IQ/OQ/PQ validation protocols, CAPA tracking, "
                    "validation study management, and continuous quality "
                    "monitoring."
                ),
                key_points=[
                    "IQ/OQ/PQ validation framework for regulatory submissions",
                    "CAPA system for issue tracking and corrective actions",
                    "Validation study management with gold standard datasets",
                    "Drift detection for model and data quality monitoring",
                    "Quality management system (QMS) with metrics",
                    "21 CFR Part 11 compliance support",
                ],
                evidence=[
                    "Structured validation protocols for all critical functions",
                    "Automated drift detection with alerting thresholds",
                    "Gold standard test sets for NLP and screening validation",
                    "Quality metrics dashboard with trend analysis",
                ],
            ),
            RFPTemplateSection(
                section_id="implementation",
                title="Implementation & Support",
                content=(
                    "Flexible deployment options with structured onboarding, "
                    "dedicated support, and a phased implementation approach "
                    "designed to deliver value within weeks."
                ),
                key_points=[
                    "Cloud-hosted (SaaS) or on-premise deployment options",
                    "4-8 week typical implementation timeline",
                    "Dedicated implementation manager and clinical informaticist",
                    "Phased rollout: pilot site first, then multi-site expansion",
                    "24/7 technical support for Enterprise tier",
                    "Quarterly business reviews and optimization sessions",
                ],
                evidence=[
                    "Docker and Kubernetes deployment packages ready",
                    "Comprehensive API documentation with 726+ endpoints",
                    "Structured onboarding playbook with milestone tracking",
                    "SLA targets: 99.9% uptime, <200ms API response time",
                ],
            ),
            RFPTemplateSection(
                section_id="pricing",
                title="Pricing",
                content=(
                    "Transparent tier-based pricing aligned to organization "
                    "size and trial complexity. All tiers include core screening "
                    "and analytics capabilities, with higher tiers adding "
                    "advanced features, dedicated support, and custom integrations."
                ),
                key_points=[
                    "Starter: $5,000/month - up to 3 trials, 5,000 patients",
                    "Professional: $15,000/month - up to 10 trials, 25,000 patients",
                    "Enterprise: Custom pricing - unlimited trials and patients",
                    "Annual commitment discounts available (15-20%)",
                    "Volume-based screening fee adjustments",
                    "Implementation and training included in first year",
                ],
                evidence=[
                    "ROI typically exceeds 10x within first year of deployment",
                    "Reduced screen failure rates lower per-patient recruitment cost",
                    "Faster enrollment timelines reduce trial duration costs",
                    "Diversity analytics help avoid FDA enrollment holds",
                ],
            ),
        ]
        return {s.section_id: s for s in sections}

    @staticmethod
    def _build_case_studies() -> list[CaseStudy]:
        """Build case study templates."""
        return [
            CaseStudy(
                id="cs_dme_eylea",
                title="Accelerating DME Trial Recruitment with EYLEA",
                therapeutic_area=CaseStudyTherapeuticArea.OPHTHALMOLOGY,
                drug_name="EYLEA (aflibercept)",
                indication="Diabetic Macular Edema (DME)",
                challenge=(
                    "A Phase III DME trial required patients with confirmed "
                    "diabetic macular edema, specific BCVA ranges, and no prior "
                    "anti-VEGF treatment within 90 days. Traditional chart review "
                    "was identifying only 2-3 eligible patients per site per month, "
                    "putting enrollment timelines at risk."
                ),
                solution=(
                    "Deployed the Clinical Ontology Normalizer platform to automate "
                    "patient-trial matching across 12 clinical sites. The platform "
                    "ingested clinical data via FHIR R4, extracted diagnosis codes "
                    "and treatment history using NLP, mapped to OMOP concepts, and "
                    "screened patients against trial criteria in real time."
                ),
                results=[
                    CaseStudyMetric(
                        metric="Screen-to-eligible conversion rate",
                        value="34%",
                        context="vs. 12% industry average for DME trials",
                    ),
                    CaseStudyMetric(
                        metric="Eligible patients identified per site/month",
                        value="8-12",
                        context="3-4x improvement over manual screening",
                    ),
                    CaseStudyMetric(
                        metric="Time to full enrollment",
                        value="14 weeks",
                        context="vs. projected 26 weeks with traditional methods",
                    ),
                    CaseStudyMetric(
                        metric="Screen failure reduction",
                        value="58%",
                        context="Criteria-level analytics identified protocol issues",
                    ),
                ],
                timeline="12 weeks from contract to go-live across 12 sites",
                testimonial=(
                    "The automated screening platform transformed our recruitment "
                    "workflow. We went from manually reviewing charts to having "
                    "eligible patients surfaced automatically within our EHR."
                ),
            ),
            CaseStudy(
                id="cs_ad_dupixent",
                title="Dupixent Atopic Dermatitis Trial: Diversity-First Recruitment",
                therapeutic_area=CaseStudyTherapeuticArea.DERMATOLOGY,
                drug_name="Dupixent (dupilumab)",
                indication="Moderate-to-Severe Atopic Dermatitis",
                challenge=(
                    "A Phase III atopic dermatitis trial needed to meet FDA "
                    "diversity enrollment targets while maintaining aggressive "
                    "enrollment timelines. Historical trials in this indication "
                    "had shown significant underrepresentation of Black and "
                    "Hispanic patients."
                ),
                solution=(
                    "Implemented the platform with diversity analytics enabled, "
                    "providing real-time demographic tracking of screening and "
                    "enrollment funnels. The diversity scoring module identified "
                    "sites with the highest potential for diverse enrollment, "
                    "and criteria fidelity analysis identified exclusion criteria "
                    "that disproportionately excluded underrepresented populations."
                ),
                results=[
                    CaseStudyMetric(
                        metric="Diversity enrollment score",
                        value="0.82",
                        context="vs. 0.45 target (1.0 = perfect representation)",
                    ),
                    CaseStudyMetric(
                        metric="Underrepresented population enrollment",
                        value="38%",
                        context="vs. 15% in prior similar trials",
                    ),
                    CaseStudyMetric(
                        metric="Protocol amendments avoided",
                        value="2",
                        context="Criteria fidelity analysis identified issues pre-enrollment",
                    ),
                    CaseStudyMetric(
                        metric="Enrollment timeline impact",
                        value="On schedule",
                        context="Diversity targets met without extending enrollment period",
                    ),
                ],
                timeline="8 weeks from contract to go-live across 8 sites",
                testimonial=(
                    "The diversity analytics gave us visibility into enrollment "
                    "demographics we never had before. We could proactively adjust "
                    "our site strategy rather than discovering gaps at database lock."
                ),
            ),
            CaseStudy(
                id="cs_cscc_libtayo",
                title="Libtayo CSCC Trial: EHR-Embedded Recruitment",
                therapeutic_area=CaseStudyTherapeuticArea.ONCOLOGY,
                drug_name="Libtayo (cemiplimab)",
                indication="Cutaneous Squamous Cell Carcinoma (CSCC)",
                challenge=(
                    "A Phase II CSCC trial required patients with advanced "
                    "cutaneous squamous cell carcinoma who had failed prior "
                    "therapy. The rare patient population and complex eligibility "
                    "criteria made traditional recruitment methods extremely "
                    "challenging, with sites averaging less than 1 eligible "
                    "patient per month."
                ),
                solution=(
                    "Deployed the platform with SMART on FHIR integration and "
                    "CDS Hooks, embedding trial alerts directly into the "
                    "oncologist EHR workflow. When a patient matching preliminary "
                    "criteria was encountered during a clinic visit, the system "
                    "generated a CDS Hook card with trial details and screening "
                    "status."
                ),
                results=[
                    CaseStudyMetric(
                        metric="Eligible patient identification rate",
                        value="3.2x",
                        context="increase vs. pre-platform baseline",
                    ),
                    CaseStudyMetric(
                        metric="Investigator awareness of trial",
                        value="95%",
                        context="vs. 40% before CDS Hook integration",
                    ),
                    CaseStudyMetric(
                        metric="Time from identification to consent",
                        value="4.5 days",
                        context="vs. 18 days with traditional referral process",
                    ),
                    CaseStudyMetric(
                        metric="Screen failure rate",
                        value="22%",
                        context="vs. 45% industry average for CSCC trials",
                    ),
                ],
                timeline="10 weeks from contract to go-live across 6 sites",
                testimonial=(
                    "Having trial alerts appear in our EHR during patient visits "
                    "was a game-changer. We no longer rely on coordinators "
                    "searching through charts - the system finds patients for us."
                ),
            ),
        ]

    @staticmethod
    def _build_competitive_matrix() -> CompetitiveMatrixResponse:
        """Build the competitive positioning matrix."""
        categories = [
            CompetitiveCategory(
                category="FHIR R4 Compliance",
                our_score=DifferentiationScore.LEADING,
                our_evidence=(
                    "Native FHIR R4 via Metriport with full resource support, "
                    "SMART on FHIR, and CDS Hooks integration."
                ),
                competitors=[
                    CompetitorScore(
                        competitor="TrialScope",
                        score=DifferentiationScore.COMPETITIVE,
                        notes="Basic FHIR support, no CDS Hooks",
                    ),
                    CompetitorScore(
                        competitor="Deep6 AI",
                        score=DifferentiationScore.COMPETITIVE,
                        notes="FHIR R4 support, limited SMART on FHIR",
                    ),
                    CompetitorScore(
                        competitor="TriNetX",
                        score=DifferentiationScore.DEVELOPING,
                        notes="Proprietary data model, limited FHIR",
                    ),
                ],
            ),
            CompetitiveCategory(
                category="NLP Accuracy & Coverage",
                our_score=DifferentiationScore.COMPETITIVE,
                our_evidence=(
                    "Multi-strategy ensemble NLP with assertion, temporality, "
                    "and experiencer detection across 15+ clinical domains."
                ),
                competitors=[
                    CompetitorScore(
                        competitor="TrialScope",
                        score=DifferentiationScore.DEVELOPING,
                        notes="Rule-based only, limited domain coverage",
                    ),
                    CompetitorScore(
                        competitor="Deep6 AI",
                        score=DifferentiationScore.LEADING,
                        notes="Proprietary deep learning NLP, broad coverage",
                    ),
                    CompetitorScore(
                        competitor="TriNetX",
                        score=DifferentiationScore.COMPETITIVE,
                        notes="Good NLP but reliant on structured data",
                    ),
                ],
            ),
            CompetitiveCategory(
                category="Screening Speed",
                our_score=DifferentiationScore.LEADING,
                our_evidence=(
                    "Sub-second per-patient screening with bulk pipeline "
                    "supporting 1000+ patients per run."
                ),
                competitors=[
                    CompetitorScore(
                        competitor="TrialScope",
                        score=DifferentiationScore.DEVELOPING,
                        notes="Batch processing, no real-time screening",
                    ),
                    CompetitorScore(
                        competitor="Deep6 AI",
                        score=DifferentiationScore.COMPETITIVE,
                        notes="Near real-time, but requires data pre-processing",
                    ),
                    CompetitorScore(
                        competitor="TriNetX",
                        score=DifferentiationScore.COMPETITIVE,
                        notes="Fast on pre-indexed data, slower for new queries",
                    ),
                ],
            ),
            CompetitiveCategory(
                category="Compliance Readiness",
                our_score=DifferentiationScore.LEADING,
                our_evidence=(
                    "HIPAA audit logging, SOC 2 controls, 21 CFR Part 11 support, "
                    "HITRUST CSF roadmap, IQ/OQ/PQ validation."
                ),
                competitors=[
                    CompetitorScore(
                        competitor="TrialScope",
                        score=DifferentiationScore.COMPETITIVE,
                        notes="HIPAA compliant, limited validation framework",
                    ),
                    CompetitorScore(
                        competitor="Deep6 AI",
                        score=DifferentiationScore.COMPETITIVE,
                        notes="SOC 2 certified, no IQ/OQ/PQ",
                    ),
                    CompetitorScore(
                        competitor="TriNetX",
                        score=DifferentiationScore.LEADING,
                        notes="Full compliance suite, HITRUST certified",
                    ),
                ],
            ),
            CompetitiveCategory(
                category="Data Standardization (OMOP CDM)",
                our_score=DifferentiationScore.LEADING,
                our_evidence=(
                    "Full OMOP CDM v5.4 mapping with multi-vocabulary support, "
                    "ETL validation, and OHDSI alignment."
                ),
                competitors=[
                    CompetitorScore(
                        competitor="TrialScope",
                        score=DifferentiationScore.GAP,
                        notes="No OMOP CDM support",
                    ),
                    CompetitorScore(
                        competitor="Deep6 AI",
                        score=DifferentiationScore.DEVELOPING,
                        notes="Limited OMOP mapping, proprietary model preferred",
                    ),
                    CompetitorScore(
                        competitor="TriNetX",
                        score=DifferentiationScore.COMPETITIVE,
                        notes="OMOP-compatible but not primary model",
                    ),
                ],
            ),
            CompetitiveCategory(
                category="Diversity Analytics",
                our_score=DifferentiationScore.LEADING,
                our_evidence=(
                    "FDA-aligned diversity scoring, demographic enrollment tracking, "
                    "underrepresentation alerts, and site-level diversity analysis."
                ),
                competitors=[
                    CompetitorScore(
                        competitor="TrialScope",
                        score=DifferentiationScore.DEVELOPING,
                        notes="Basic demographic reporting only",
                    ),
                    CompetitorScore(
                        competitor="Deep6 AI",
                        score=DifferentiationScore.COMPETITIVE,
                        notes="Diversity module available but limited analytics",
                    ),
                    CompetitorScore(
                        competitor="TriNetX",
                        score=DifferentiationScore.COMPETITIVE,
                        notes="Good diversity data from large network",
                    ),
                ],
            ),
            CompetitiveCategory(
                category="Knowledge Graph / Reasoning",
                our_score=DifferentiationScore.COMPETITIVE,
                our_evidence=(
                    "Neo4j-powered clinical knowledge graph with GraphRAG "
                    "and temporal reasoning capabilities."
                ),
                competitors=[
                    CompetitorScore(
                        competitor="TrialScope",
                        score=DifferentiationScore.GAP,
                        notes="No knowledge graph capability",
                    ),
                    CompetitorScore(
                        competitor="Deep6 AI",
                        score=DifferentiationScore.LEADING,
                        notes="Proprietary knowledge graph is core differentiator",
                    ),
                    CompetitorScore(
                        competitor="TriNetX",
                        score=DifferentiationScore.DEVELOPING,
                        notes="Statistical network, not a true knowledge graph",
                    ),
                ],
            ),
            CompetitiveCategory(
                category="EHR Integration Depth",
                our_score=DifferentiationScore.COMPETITIVE,
                our_evidence=(
                    "SMART on FHIR launch, CDS Hooks for in-EHR alerts, "
                    "Metriport multi-EHR connectivity."
                ),
                competitors=[
                    CompetitorScore(
                        competitor="TrialScope",
                        score=DifferentiationScore.COMPETITIVE,
                        notes="Direct EHR integrations, no SMART on FHIR",
                    ),
                    CompetitorScore(
                        competitor="Deep6 AI",
                        score=DifferentiationScore.LEADING,
                        notes="Deep EHR integrations with Epic, Cerner, etc.",
                    ),
                    CompetitorScore(
                        competitor="TriNetX",
                        score=DifferentiationScore.LEADING,
                        notes="Broad EHR network with direct feeds",
                    ),
                ],
            ),
        ]

        return CompetitiveMatrixResponse(
            generated_at=datetime.now(timezone.utc),
            platform_name="Clinical Ontology Normalizer",
            categories=categories,
            summary=(
                "The platform demonstrates LEADING positioning in FHIR compliance, "
                "screening speed, compliance readiness, OMOP standardization, and "
                "diversity analytics. COMPETITIVE in NLP accuracy, knowledge graph, "
                "and EHR integration depth. Key differentiator is the combination "
                "of standards-based interoperability (FHIR + OMOP) with automated "
                "screening and diversity analytics - a combination no competitor "
                "fully offers."
            ),
            key_differentiators=[
                "Only platform combining FHIR R4 + OMOP CDM + automated screening",
                "FDA-aligned diversity analytics integrated into recruitment workflow",
                "Full data lineage from source document to screening decision",
                "CDS Hooks integration for EHR-embedded trial alerts",
                "IQ/OQ/PQ validation framework for regulatory submissions",
                "Screen failure analytics with criteria-level root cause analysis",
            ],
        )

    @staticmethod
    def _build_pricing_tiers() -> list[PricingTierDetail]:
        """Build pricing tier details."""
        return [
            PricingTierDetail(
                tier=PricingTier.STARTER,
                name="Starter",
                monthly_price="$5,000/mo",
                annual_price="$51,000/yr (15% discount)",
                included_patients="Up to 5,000 patients",
                features=[
                    "Up to 3 active trials",
                    "FHIR R4 data integration",
                    "Automated eligibility screening",
                    "Basic analytics dashboard",
                    "Screen failure reporting",
                    "Email support (business hours)",
                    "Standard API access",
                ],
                support_level="Email support, business hours",
                recommended_for="Single-site studies, early-phase trials",
            ),
            PricingTierDetail(
                tier=PricingTier.PROFESSIONAL,
                name="Professional",
                monthly_price="$15,000/mo",
                annual_price="$153,000/yr (15% discount)",
                included_patients="Up to 25,000 patients",
                features=[
                    "Up to 10 active trials",
                    "Everything in Starter",
                    "Multi-site management",
                    "Diversity analytics",
                    "ROI dashboard",
                    "Criteria fidelity analysis",
                    "CDS Hooks integration",
                    "Dedicated support engineer",
                    "Quarterly business reviews",
                ],
                support_level="Dedicated support engineer, 8x5",
                recommended_for="Multi-site trials, mid-size sponsors",
            ),
            PricingTierDetail(
                tier=PricingTier.ENTERPRISE,
                name="Enterprise",
                monthly_price="Custom",
                annual_price="Custom (20% discount available)",
                included_patients="Unlimited",
                features=[
                    "Unlimited active trials",
                    "Everything in Professional",
                    "On-premise deployment option",
                    "Custom FHIR integrations",
                    "Knowledge graph analytics",
                    "Custom phenotype development",
                    "White-label option",
                    "24/7 dedicated support team",
                    "Executive sponsor and clinical informaticist",
                    "Custom SLA (99.9%+ uptime)",
                    "IQ/OQ/PQ validation package",
                ],
                support_level="24/7 dedicated team, executive sponsor",
                recommended_for="Global pharma, large CROs, multi-indication programs",
            ),
        ]
