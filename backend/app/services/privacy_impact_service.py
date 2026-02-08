"""Privacy Impact Assessment (DPIA) Service.

CLO-4: Manages the lifecycle of Privacy Impact Assessments compliant
with GDPR Article 35 and HIPAA for the clinical trial patient
recruitment platform.

Provides:
- PIA creation, update, and state transitions
- Processing activity tracking
- Privacy risk identification with auto-calculated scores
- Mitigation tracking and verification
- DPO approval workflow
- Supervisory authority consultation checks
- Overdue review detection
- PIA program metrics
- Pre-populated templates and sample PIAs

Usage:
    from app.services.privacy_impact_service import get_privacy_impact_service

    service = get_privacy_impact_service()
    pia = service.create_pia(
        title="Patient Screening Pipeline",
        description="Assessment of patient data processing",
        assessor="privacy-officer",
    )
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from threading import Lock
from uuid import uuid4

from app.schemas.privacy_impact import (
    AffectedRight,
    ConsultationCheckResponse,
    DataCategoryType,
    DataProcessingActivity,
    DataSubjectType,
    LegalBasis,
    MitigationStatus,
    PIAMetrics,
    PIARecord,
    PIAStatus,
    PIATemplate,
    PIATemplateQuestion,
    PrivacyRisk,
    RiskImpact,
    RiskLevel,
    RiskLikelihood,
)

logger = logging.getLogger(__name__)

# Singleton instance and lock
_pia_service_instance: PrivacyImpactService | None = None
_pia_service_lock = Lock()


# ---------------------------------------------------------------------------
# Valid PIA state transitions
# ---------------------------------------------------------------------------

VALID_PIA_TRANSITIONS: dict[PIAStatus, list[PIAStatus]] = {
    PIAStatus.DRAFT: [PIAStatus.IN_REVIEW],
    PIAStatus.IN_REVIEW: [PIAStatus.APPROVED, PIAStatus.REQUIRES_MITIGATION, PIAStatus.DRAFT],
    PIAStatus.APPROVED: [PIAStatus.COMPLETED, PIAStatus.ARCHIVED],
    PIAStatus.REQUIRES_MITIGATION: [PIAStatus.MITIGATIONS_IN_PROGRESS, PIAStatus.DRAFT],
    PIAStatus.MITIGATIONS_IN_PROGRESS: [PIAStatus.IN_REVIEW, PIAStatus.DRAFT],
    PIAStatus.COMPLETED: [PIAStatus.ARCHIVED],
    PIAStatus.ARCHIVED: [],  # Terminal state
}


# ---------------------------------------------------------------------------
# Risk level calculation
# ---------------------------------------------------------------------------


def calculate_risk_level(score: int) -> RiskLevel:
    """Calculate risk level from a risk score.

    Args:
        score: Risk score (1-25).

    Returns:
        RiskLevel based on score thresholds.
    """
    if score <= 6:
        return RiskLevel.LOW
    elif score <= 12:
        return RiskLevel.MEDIUM
    elif score <= 19:
        return RiskLevel.HIGH
    else:
        return RiskLevel.CRITICAL


# ---------------------------------------------------------------------------
# PrivacyImpactService
# ---------------------------------------------------------------------------


class PrivacyImpactService:
    """Service for managing Privacy Impact Assessments.

    Uses in-memory storage with thread-safe access.
    Production deployments should persist to the database.
    """

    def __init__(self) -> None:
        """Initialize the PIA service with empty storage and seed data."""
        self._pias: dict[str, PIARecord] = {}
        self._templates: dict[str, PIATemplate] = {}
        self._lock = Lock()
        self._seed_templates()
        self._seed_examples()
        logger.info(
            "PrivacyImpactService initialized with %d PIAs and %d templates",
            len(self._pias),
            len(self._templates),
        )

    # ------------------------------------------------------------------
    # Seeding
    # ------------------------------------------------------------------

    def _seed_templates(self) -> None:
        """Pre-populate PIA templates."""
        standard = PIATemplate(
            id="TPL-001",
            name="Standard PIA",
            description="Standard Privacy Impact Assessment template for routine data processing activities.",
            default_questions=self._get_standard_questions(),
        )
        high_risk = PIATemplate(
            id="TPL-002",
            name="High-Risk Clinical Data PIA",
            description=(
                "Enhanced PIA template for high-risk clinical data processing "
                "involving special category data, genetic information, or "
                "automated decision-making."
            ),
            default_questions=self._get_standard_questions() + self._get_high_risk_questions(),
        )
        self._templates[standard.id] = standard
        self._templates[high_risk.id] = high_risk

    def _get_standard_questions(self) -> list[PIATemplateQuestion]:
        """Return standard assessment questions across categories."""
        return [
            # Data Collection
            PIATemplateQuestion(
                category="Data Collection",
                question="What personal data is collected and from whom?",
                guidance="List all categories of personal data and data subjects.",
            ),
            PIATemplateQuestion(
                category="Data Collection",
                question="Is the data collected directly from the data subject or from a third party?",
                guidance="Identify the source of data and any intermediaries.",
            ),
            PIATemplateQuestion(
                category="Data Collection",
                question="What is the lawful basis for collecting this data?",
                guidance="Identify the GDPR Article 6 basis and any Article 9 conditions for special category data.",
            ),
            PIATemplateQuestion(
                category="Data Collection",
                question="Is consent obtained, and how is it documented?",
                guidance="Describe the consent mechanism, granularity, and withdrawal process.",
            ),
            # Processing
            PIATemplateQuestion(
                category="Processing",
                question="What processing operations are performed on the data?",
                guidance="Describe all operations including collection, storage, use, and deletion.",
            ),
            PIATemplateQuestion(
                category="Processing",
                question="Is there any automated decision-making or profiling?",
                guidance="Identify if decisions are made without human intervention and their impact.",
            ),
            PIATemplateQuestion(
                category="Processing",
                question="Are there any data transformations such as pseudonymization or aggregation?",
                guidance="Describe any techniques used to reduce identifiability.",
            ),
            PIATemplateQuestion(
                category="Processing",
                question="What is the purpose limitation for this processing activity?",
                guidance="Ensure processing is limited to the stated purpose only.",
            ),
            # Storage
            PIATemplateQuestion(
                category="Storage",
                question="Where is the data stored and what security measures are in place?",
                guidance="Identify storage locations, encryption, and access controls.",
            ),
            PIATemplateQuestion(
                category="Storage",
                question="What is the data retention period and deletion policy?",
                guidance="Specify how long data is kept and the secure deletion procedure.",
            ),
            PIATemplateQuestion(
                category="Storage",
                question="Are backups encrypted and how are they managed?",
                guidance="Describe backup frequency, encryption, and retention.",
            ),
            PIATemplateQuestion(
                category="Storage",
                question="How is data integrity maintained during storage?",
                guidance="Describe checksums, versioning, and corruption detection mechanisms.",
            ),
            # Sharing
            PIATemplateQuestion(
                category="Sharing",
                question="Is data shared with third parties, and under what agreements?",
                guidance="List all third parties and the legal basis for sharing.",
            ),
            PIATemplateQuestion(
                category="Sharing",
                question="Are there any cross-border data transfers?",
                guidance="Identify transfers outside the EEA and the safeguards in place.",
            ),
            PIATemplateQuestion(
                category="Sharing",
                question="What data minimization measures are applied before sharing?",
                guidance="Describe de-identification or aggregation before transfer.",
            ),
            # Security
            PIATemplateQuestion(
                category="Security",
                question="What technical security measures protect the data?",
                guidance="Describe encryption, firewalls, intrusion detection, and monitoring.",
            ),
            PIATemplateQuestion(
                category="Security",
                question="What organizational security measures are in place?",
                guidance="Describe access policies, training, and incident response procedures.",
            ),
            PIATemplateQuestion(
                category="Security",
                question="How are security breaches detected and reported?",
                guidance="Describe breach detection, notification timelines, and escalation procedures.",
            ),
            PIATemplateQuestion(
                category="Security",
                question="Is there a data breach response plan?",
                guidance="Describe the plan for notifying authorities and data subjects within 72 hours.",
            ),
            # Rights
            PIATemplateQuestion(
                category="Rights",
                question="How can data subjects exercise their right of access?",
                guidance="Describe the process for Subject Access Requests (SARs).",
            ),
            PIATemplateQuestion(
                category="Rights",
                question="How is the right to erasure (right to be forgotten) supported?",
                guidance="Describe the deletion process and any retention exceptions.",
            ),
            PIATemplateQuestion(
                category="Rights",
                question="How is data portability supported?",
                guidance="Describe the format and mechanism for data export.",
            ),
            PIATemplateQuestion(
                category="Rights",
                question="How can data subjects object to processing?",
                guidance="Describe the objection mechanism and how processing is halted.",
            ),
            PIATemplateQuestion(
                category="Rights",
                question="How are data subject requests tracked and fulfilled within required timelines?",
                guidance="Describe the workflow and SLA for fulfilling requests within 30 days.",
            ),
        ]

    def _get_high_risk_questions(self) -> list[PIATemplateQuestion]:
        """Return additional questions for high-risk clinical PIAs."""
        return [
            PIATemplateQuestion(
                category="Data Collection",
                question="Does the processing involve special category data (health, genetic, biometric)?",
                guidance="Identify Article 9 GDPR conditions for processing special category data.",
            ),
            PIATemplateQuestion(
                category="Processing",
                question="Is the automated decision-making used for clinical trial eligibility?",
                guidance="Assess whether GDPR Article 22 applies and if human oversight is sufficient.",
            ),
            PIATemplateQuestion(
                category="Security",
                question="What additional safeguards exist for genetic and genomic data?",
                guidance="Describe enhanced encryption, access controls, and consent mechanisms for genetic data.",
            ),
            PIATemplateQuestion(
                category="Sharing",
                question="Are data transfers to non-EU countries covered by adequacy decisions or SCCs?",
                guidance="Verify Standard Contractual Clauses or adequacy decisions for all transfers.",
            ),
            PIATemplateQuestion(
                category="Rights",
                question="How is meaningful information about automated decision logic provided?",
                guidance="Ensure transparency about algorithm logic, significance, and consequences.",
            ),
        ]

    def _seed_examples(self) -> None:
        """Pre-populate sample PIAs for demonstration."""
        now = datetime.now(timezone.utc)

        # 1. Patient Screening Pipeline - COMPLETED
        screening_pia = PIARecord(
            id="PIA-001",
            title="Patient Screening Pipeline",
            description=(
                "Privacy impact assessment for the automated patient screening "
                "pipeline that processes clinical notes, lab results, and demographic "
                "data to identify potential trial candidates."
            ),
            status=PIAStatus.COMPLETED,
            processing_activities=[
                DataProcessingActivity(
                    id="ACT-001-01",
                    name="Clinical Note Ingestion",
                    description="Ingest and parse clinical notes from EHR systems",
                    data_categories=[DataCategoryType.CLINICAL, DataCategoryType.IDENTIFIERS],
                    processing_purpose="Extract clinical entities for trial eligibility screening",
                    legal_basis=LegalBasis.CONSENT,
                    data_subjects=[DataSubjectType.PATIENTS],
                    retention_period_months=72,
                    cross_border_transfer=False,
                    automated_decision_making=False,
                    third_party_sharing=False,
                    third_parties=[],
                ),
                DataProcessingActivity(
                    id="ACT-001-02",
                    name="Lab Result Processing",
                    description="Process laboratory results for eligibility criteria matching",
                    data_categories=[DataCategoryType.CLINICAL, DataCategoryType.DEMOGRAPHICS],
                    processing_purpose="Match lab values against trial inclusion/exclusion criteria",
                    legal_basis=LegalBasis.CONSENT,
                    data_subjects=[DataSubjectType.PATIENTS],
                    retention_period_months=72,
                    cross_border_transfer=False,
                    automated_decision_making=True,
                    third_party_sharing=False,
                    third_parties=[],
                ),
                DataProcessingActivity(
                    id="ACT-001-03",
                    name="Screening Decision Generation",
                    description="Generate screening recommendations based on criteria matching",
                    data_categories=[DataCategoryType.CLINICAL, DataCategoryType.DEMOGRAPHICS],
                    processing_purpose="Produce eligibility recommendations for clinical staff review",
                    legal_basis=LegalBasis.CONSENT,
                    data_subjects=[DataSubjectType.PATIENTS],
                    retention_period_months=72,
                    cross_border_transfer=False,
                    automated_decision_making=True,
                    third_party_sharing=False,
                    third_parties=[],
                ),
            ],
            identified_risks=[
                PrivacyRisk(
                    id="RISK-001-01",
                    title="Unauthorized access to screening results",
                    description="Risk of unauthorized personnel accessing patient screening outcomes",
                    likelihood=RiskLikelihood.UNLIKELY,
                    impact=RiskImpact.MAJOR,
                    risk_score=8,
                    risk_level=RiskLevel.MEDIUM,
                    affected_rights=[AffectedRight.ACCESS, AffectedRight.RESTRICTION],
                    mitigation_measures=[
                        "Role-based access control (RBAC) on screening endpoints",
                        "Audit logging of all screening data access",
                    ],
                    residual_risk_score=4,
                    mitigation_status=MitigationStatus.VERIFIED,
                ),
                PrivacyRisk(
                    id="RISK-001-02",
                    title="Re-identification from screening criteria",
                    description="Combination of screening criteria could enable patient re-identification",
                    likelihood=RiskLikelihood.RARE,
                    impact=RiskImpact.SEVERE,
                    risk_score=5,
                    risk_level=RiskLevel.LOW,
                    affected_rights=[AffectedRight.ERASURE, AffectedRight.OBJECTION],
                    mitigation_measures=[
                        "Minimum necessary data principle enforced",
                        "K-anonymity checks on query results",
                    ],
                    residual_risk_score=3,
                    mitigation_status=MitigationStatus.VERIFIED,
                ),
                PrivacyRisk(
                    id="RISK-001-03",
                    title="Bias in automated screening decisions",
                    description="Algorithmic bias may disproportionately affect certain patient populations",
                    likelihood=RiskLikelihood.POSSIBLE,
                    impact=RiskImpact.MODERATE,
                    risk_score=9,
                    risk_level=RiskLevel.MEDIUM,
                    affected_rights=[AffectedRight.OBJECTION],
                    mitigation_measures=[
                        "Regular fairness audits on screening algorithm",
                        "Human review required for all screening decisions",
                        "Diversity analytics monitoring dashboard",
                    ],
                    residual_risk_score=4,
                    mitigation_status=MitigationStatus.IMPLEMENTED,
                ),
                PrivacyRisk(
                    id="RISK-001-04",
                    title="Excessive data retention",
                    description="Screening data retained beyond the necessary period",
                    likelihood=RiskLikelihood.UNLIKELY,
                    impact=RiskImpact.MINOR,
                    risk_score=4,
                    risk_level=RiskLevel.LOW,
                    affected_rights=[AffectedRight.ERASURE],
                    mitigation_measures=[
                        "Automated data retention policy enforcement",
                        "Quarterly retention compliance review",
                    ],
                    residual_risk_score=2,
                    mitigation_status=MitigationStatus.VERIFIED,
                ),
            ],
            assessor="privacy-officer",
            reviewer="chief-privacy-officer",
            dpo_approval=True,
            dpo_approval_date=now - timedelta(days=30),
            necessity_assessment="Processing is necessary for legitimate clinical trial recruitment under patient consent.",
            proportionality_assessment="Data collection is limited to what is strictly necessary for screening criteria evaluation.",
            consultation_required=False,
            created_at=now - timedelta(days=60),
            updated_at=now - timedelta(days=30),
            completed_at=now - timedelta(days=30),
            next_review_date=now + timedelta(days=335),
        )

        # 2. FHIR Data Import - APPROVED
        fhir_pia = PIARecord(
            id="PIA-002",
            title="FHIR Data Import",
            description=(
                "Assessment of the FHIR R4 data import pipeline that ingests "
                "patient records from external EHR systems for trial matching."
            ),
            status=PIAStatus.APPROVED,
            processing_activities=[
                DataProcessingActivity(
                    id="ACT-002-01",
                    name="FHIR Resource Ingestion",
                    description="Import FHIR R4 resources (Patient, Condition, Observation) from EHR systems",
                    data_categories=[
                        DataCategoryType.CLINICAL,
                        DataCategoryType.DEMOGRAPHICS,
                        DataCategoryType.IDENTIFIERS,
                    ],
                    processing_purpose="Ingest structured clinical data for trial eligibility screening",
                    legal_basis=LegalBasis.CONSENT,
                    data_subjects=[DataSubjectType.PATIENTS],
                    retention_period_months=72,
                    cross_border_transfer=False,
                    automated_decision_making=False,
                    third_party_sharing=True,
                    third_parties=["EHR Vendor (Metriport)"],
                ),
            ],
            identified_risks=[
                PrivacyRisk(
                    id="RISK-002-01",
                    title="Data exposure during FHIR transmission",
                    description="Patient data could be intercepted during FHIR API calls",
                    likelihood=RiskLikelihood.RARE,
                    impact=RiskImpact.SEVERE,
                    risk_score=5,
                    risk_level=RiskLevel.LOW,
                    affected_rights=[AffectedRight.ACCESS],
                    mitigation_measures=[
                        "TLS 1.3 encryption for all FHIR API communications",
                        "mTLS authentication with EHR endpoints",
                    ],
                    residual_risk_score=2,
                    mitigation_status=MitigationStatus.VERIFIED,
                ),
                PrivacyRisk(
                    id="RISK-002-02",
                    title="Insufficient data validation on import",
                    description="Malformed or excessive FHIR data could violate data minimization",
                    likelihood=RiskLikelihood.UNLIKELY,
                    impact=RiskImpact.MODERATE,
                    risk_score=6,
                    risk_level=RiskLevel.LOW,
                    affected_rights=[AffectedRight.RECTIFICATION],
                    mitigation_measures=[
                        "FHIR profile validation on all incoming resources",
                        "Data minimization filter on import pipeline",
                    ],
                    residual_risk_score=3,
                    mitigation_status=MitigationStatus.IMPLEMENTED,
                ),
                PrivacyRisk(
                    id="RISK-002-03",
                    title="Third-party vendor data handling",
                    description="EHR vendor may retain copies of transmitted data",
                    likelihood=RiskLikelihood.POSSIBLE,
                    impact=RiskImpact.MAJOR,
                    risk_score=12,
                    risk_level=RiskLevel.MEDIUM,
                    affected_rights=[AffectedRight.ERASURE, AffectedRight.PORTABILITY],
                    mitigation_measures=[
                        "Data processing agreement with vendor",
                        "Annual vendor compliance audit",
                    ],
                    residual_risk_score=6,
                    mitigation_status=MitigationStatus.IMPLEMENTED,
                ),
            ],
            assessor="data-protection-analyst",
            reviewer="privacy-officer",
            dpo_approval=True,
            dpo_approval_date=now - timedelta(days=15),
            necessity_assessment="FHIR data import is necessary for accurate, standards-based clinical trial screening.",
            proportionality_assessment="Only clinically relevant FHIR resources are imported; non-relevant data is filtered out.",
            consultation_required=False,
            created_at=now - timedelta(days=45),
            updated_at=now - timedelta(days=15),
            completed_at=None,
            next_review_date=now + timedelta(days=350),
        )

        # 3. Knowledge Graph Analytics - IN_REVIEW
        kg_pia = PIARecord(
            id="PIA-003",
            title="Knowledge Graph Analytics",
            description=(
                "Privacy assessment of the clinical knowledge graph that links "
                "patient conditions, medications, and lab results across multiple "
                "data sources including cross-border research institutions."
            ),
            status=PIAStatus.IN_REVIEW,
            processing_activities=[
                DataProcessingActivity(
                    id="ACT-003-01",
                    name="Knowledge Graph Construction",
                    description="Build patient-centric knowledge graph from clinical facts",
                    data_categories=[
                        DataCategoryType.CLINICAL,
                        DataCategoryType.DEMOGRAPHICS,
                        DataCategoryType.GENETIC,
                    ],
                    processing_purpose="Link clinical concepts for comprehensive patient profiling",
                    legal_basis=LegalBasis.LEGITIMATE_INTEREST,
                    data_subjects=[DataSubjectType.PATIENTS],
                    retention_period_months=60,
                    cross_border_transfer=True,
                    automated_decision_making=False,
                    third_party_sharing=True,
                    third_parties=["EU Research Consortium", "Academic Medical Center (UK)"],
                ),
                DataProcessingActivity(
                    id="ACT-003-02",
                    name="Graph Analytics Queries",
                    description="Run analytical queries against the knowledge graph for research insights",
                    data_categories=[DataCategoryType.CLINICAL, DataCategoryType.GENETIC],
                    processing_purpose="Research analytics and cohort discovery",
                    legal_basis=LegalBasis.LEGITIMATE_INTEREST,
                    data_subjects=[DataSubjectType.PATIENTS, DataSubjectType.RESEARCHERS],
                    retention_period_months=60,
                    cross_border_transfer=True,
                    automated_decision_making=False,
                    third_party_sharing=False,
                    third_parties=[],
                ),
            ],
            identified_risks=[
                PrivacyRisk(
                    id="RISK-003-01",
                    title="Cross-border genetic data transfer without adequacy decision",
                    description="Genetic data transferred to non-EEA research partners without adequate safeguards",
                    likelihood=RiskLikelihood.POSSIBLE,
                    impact=RiskImpact.SEVERE,
                    risk_score=15,
                    risk_level=RiskLevel.HIGH,
                    affected_rights=[AffectedRight.PORTABILITY, AffectedRight.OBJECTION],
                    mitigation_measures=[],
                    residual_risk_score=None,
                    mitigation_status=MitigationStatus.PENDING,
                ),
                PrivacyRisk(
                    id="RISK-003-02",
                    title="Re-identification through graph traversal",
                    description="Knowledge graph relationships could enable re-identification of pseudonymized patients",
                    likelihood=RiskLikelihood.LIKELY,
                    impact=RiskImpact.MAJOR,
                    risk_score=16,
                    risk_level=RiskLevel.HIGH,
                    affected_rights=[AffectedRight.ERASURE, AffectedRight.RESTRICTION],
                    mitigation_measures=[],
                    residual_risk_score=None,
                    mitigation_status=MitigationStatus.PENDING,
                ),
                PrivacyRisk(
                    id="RISK-003-03",
                    title="Insufficient purpose limitation on graph queries",
                    description="Research queries may exceed the scope of original consent",
                    likelihood=RiskLikelihood.POSSIBLE,
                    impact=RiskImpact.MODERATE,
                    risk_score=9,
                    risk_level=RiskLevel.MEDIUM,
                    affected_rights=[AffectedRight.OBJECTION],
                    mitigation_measures=[],
                    residual_risk_score=None,
                    mitigation_status=MitigationStatus.PENDING,
                ),
                PrivacyRisk(
                    id="RISK-003-04",
                    title="Genetic data without explicit consent",
                    description="Processing of genetic data requires specific GDPR Article 9 basis",
                    likelihood=RiskLikelihood.UNLIKELY,
                    impact=RiskImpact.SEVERE,
                    risk_score=10,
                    risk_level=RiskLevel.MEDIUM,
                    affected_rights=[AffectedRight.ACCESS, AffectedRight.ERASURE],
                    mitigation_measures=[],
                    residual_risk_score=None,
                    mitigation_status=MitigationStatus.PENDING,
                ),
                PrivacyRisk(
                    id="RISK-003-05",
                    title="Unauthorized researcher access to identifiable data",
                    description="Researchers may gain access to identifiable patient data through graph APIs",
                    likelihood=RiskLikelihood.UNLIKELY,
                    impact=RiskImpact.MAJOR,
                    risk_score=8,
                    risk_level=RiskLevel.MEDIUM,
                    affected_rights=[AffectedRight.ACCESS, AffectedRight.RESTRICTION],
                    mitigation_measures=[],
                    residual_risk_score=None,
                    mitigation_status=MitigationStatus.PENDING,
                ),
            ],
            assessor="privacy-officer",
            reviewer=None,
            dpo_approval=False,
            dpo_approval_date=None,
            necessity_assessment="Knowledge graph analytics supports clinical research and trial recruitment.",
            proportionality_assessment=None,
            consultation_required=False,
            created_at=now - timedelta(days=20),
            updated_at=now - timedelta(days=5),
            completed_at=None,
            next_review_date=None,
        )

        # 4. Trial Matching Algorithm - REQUIRES_MITIGATION
        trial_pia = PIARecord(
            id="PIA-004",
            title="Trial Matching Algorithm",
            description=(
                "Assessment of the automated trial matching algorithm that uses "
                "machine learning to match patients to clinical trials based on "
                "their clinical profile, demographics, and genomic data."
            ),
            status=PIAStatus.REQUIRES_MITIGATION,
            processing_activities=[
                DataProcessingActivity(
                    id="ACT-004-01",
                    name="ML Feature Extraction",
                    description="Extract features from patient data for ML model input",
                    data_categories=[
                        DataCategoryType.CLINICAL,
                        DataCategoryType.DEMOGRAPHICS,
                        DataCategoryType.GENETIC,
                        DataCategoryType.BEHAVIORAL,
                    ],
                    processing_purpose="Prepare patient features for automated trial matching",
                    legal_basis=LegalBasis.CONSENT,
                    data_subjects=[DataSubjectType.PATIENTS],
                    retention_period_months=36,
                    cross_border_transfer=False,
                    automated_decision_making=True,
                    third_party_sharing=False,
                    third_parties=[],
                ),
                DataProcessingActivity(
                    id="ACT-004-02",
                    name="Trial Matching Prediction",
                    description="Run ML model to predict patient-trial compatibility scores",
                    data_categories=[
                        DataCategoryType.CLINICAL,
                        DataCategoryType.GENETIC,
                    ],
                    processing_purpose="Generate ranked trial match recommendations",
                    legal_basis=LegalBasis.CONSENT,
                    data_subjects=[DataSubjectType.PATIENTS],
                    retention_period_months=36,
                    cross_border_transfer=False,
                    automated_decision_making=True,
                    third_party_sharing=True,
                    third_parties=["Trial Sponsor (de-identified results only)"],
                ),
            ],
            identified_risks=[
                PrivacyRisk(
                    id="RISK-004-01",
                    title="Automated decision-making on special category data",
                    description="ML model makes automated decisions using health and genetic data without adequate human oversight",
                    likelihood=RiskLikelihood.LIKELY,
                    impact=RiskImpact.SEVERE,
                    risk_score=20,
                    risk_level=RiskLevel.CRITICAL,
                    affected_rights=[AffectedRight.OBJECTION, AffectedRight.ACCESS],
                    mitigation_measures=[],
                    residual_risk_score=None,
                    mitigation_status=MitigationStatus.PENDING,
                ),
                PrivacyRisk(
                    id="RISK-004-02",
                    title="Discriminatory trial matching outcomes",
                    description="ML model may discriminate against underrepresented populations",
                    likelihood=RiskLikelihood.POSSIBLE,
                    impact=RiskImpact.SEVERE,
                    risk_score=15,
                    risk_level=RiskLevel.HIGH,
                    affected_rights=[AffectedRight.OBJECTION, AffectedRight.RECTIFICATION],
                    mitigation_measures=[],
                    residual_risk_score=None,
                    mitigation_status=MitigationStatus.PENDING,
                ),
                PrivacyRisk(
                    id="RISK-004-03",
                    title="Insufficient transparency in ML decision logic",
                    description="Patients cannot understand how the matching algorithm works",
                    likelihood=RiskLikelihood.ALMOST_CERTAIN,
                    impact=RiskImpact.MODERATE,
                    risk_score=15,
                    risk_level=RiskLevel.HIGH,
                    affected_rights=[AffectedRight.ACCESS],
                    mitigation_measures=[],
                    residual_risk_score=None,
                    mitigation_status=MitigationStatus.PENDING,
                ),
                PrivacyRisk(
                    id="RISK-004-04",
                    title="Genetic data leakage to trial sponsors",
                    description="De-identification may be insufficient for genetic data shared with sponsors",
                    likelihood=RiskLikelihood.UNLIKELY,
                    impact=RiskImpact.SEVERE,
                    risk_score=10,
                    risk_level=RiskLevel.MEDIUM,
                    affected_rights=[AffectedRight.ERASURE, AffectedRight.PORTABILITY],
                    mitigation_measures=[],
                    residual_risk_score=None,
                    mitigation_status=MitigationStatus.PENDING,
                ),
                PrivacyRisk(
                    id="RISK-004-05",
                    title="Model training data retention",
                    description="Training datasets containing patient data may be retained indefinitely",
                    likelihood=RiskLikelihood.POSSIBLE,
                    impact=RiskImpact.MAJOR,
                    risk_score=12,
                    risk_level=RiskLevel.MEDIUM,
                    affected_rights=[AffectedRight.ERASURE],
                    mitigation_measures=[],
                    residual_risk_score=None,
                    mitigation_status=MitigationStatus.PENDING,
                ),
                PrivacyRisk(
                    id="RISK-004-06",
                    title="Consent withdrawal impact on ML model",
                    description="Patient consent withdrawal does not retroactively affect trained models",
                    likelihood=RiskLikelihood.LIKELY,
                    impact=RiskImpact.MODERATE,
                    risk_score=12,
                    risk_level=RiskLevel.MEDIUM,
                    affected_rights=[AffectedRight.ERASURE, AffectedRight.OBJECTION],
                    mitigation_measures=[],
                    residual_risk_score=None,
                    mitigation_status=MitigationStatus.PENDING,
                ),
            ],
            assessor="data-protection-analyst",
            reviewer=None,
            dpo_approval=False,
            dpo_approval_date=None,
            necessity_assessment="Automated trial matching is necessary to efficiently connect patients with appropriate clinical trials.",
            proportionality_assessment="Current data usage exceeds what is strictly necessary; data minimization review is required.",
            consultation_required=True,
            created_at=now - timedelta(days=14),
            updated_at=now - timedelta(days=3),
            completed_at=None,
            next_review_date=None,
        )

        for pia in [screening_pia, fhir_pia, kg_pia, trial_pia]:
            self._pias[pia.id] = pia

    # ------------------------------------------------------------------
    # PIA CRUD
    # ------------------------------------------------------------------

    def create_pia(
        self,
        title: str,
        description: str,
        assessor: str,
    ) -> PIARecord:
        """Create a new PIA in DRAFT status.

        Args:
            title: PIA title.
            description: PIA description.
            assessor: Person conducting the assessment.

        Returns:
            The created PIARecord.
        """
        now = datetime.now(timezone.utc)
        pia_id = f"PIA-{uuid4().hex[:8].upper()}"

        pia = PIARecord(
            id=pia_id,
            title=title,
            description=description,
            status=PIAStatus.DRAFT,
            processing_activities=[],
            identified_risks=[],
            assessor=assessor,
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            self._pias[pia_id] = pia

        logger.info("PIA created: id=%s, title=%s", pia_id, title)
        return pia

    def get_pia(self, pia_id: str) -> PIARecord | None:
        """Retrieve a PIA by ID.

        Args:
            pia_id: The unique PIA identifier.

        Returns:
            The PIARecord if found, otherwise None.
        """
        with self._lock:
            return self._pias.get(pia_id)

    def list_pias(
        self,
        status: PIAStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[PIARecord], int]:
        """List PIAs with optional filters.

        Args:
            status: Filter by PIA status.
            limit: Max results to return.
            offset: Pagination offset.

        Returns:
            Tuple of (filtered PIAs, total count).
        """
        with self._lock:
            pias = list(self._pias.values())

        if status is not None:
            pias = [p for p in pias if p.status == status]

        pias.sort(key=lambda p: p.created_at, reverse=True)
        total = len(pias)
        paginated = pias[offset : offset + limit]

        return paginated, total

    def update_pia(
        self,
        pia_id: str,
        title: str | None = None,
        description: str | None = None,
        assessor: str | None = None,
        reviewer: str | None = None,
        necessity_assessment: str | None = None,
        proportionality_assessment: str | None = None,
        next_review_date: datetime | None = None,
    ) -> PIARecord:
        """Update PIA fields.

        Args:
            pia_id: The PIA to update.
            title: Updated title.
            description: Updated description.
            assessor: Updated assessor.
            reviewer: Updated reviewer.
            necessity_assessment: Updated necessity assessment.
            proportionality_assessment: Updated proportionality assessment.
            next_review_date: Updated next review date.

        Returns:
            The updated PIARecord.

        Raises:
            ValueError: If PIA not found.
        """
        with self._lock:
            pia = self._pias.get(pia_id)
            if pia is None:
                raise ValueError(f"PIA not found: {pia_id}")

            updates: dict = {"updated_at": datetime.now(timezone.utc)}
            if title is not None:
                updates["title"] = title
            if description is not None:
                updates["description"] = description
            if assessor is not None:
                updates["assessor"] = assessor
            if reviewer is not None:
                updates["reviewer"] = reviewer
            if necessity_assessment is not None:
                updates["necessity_assessment"] = necessity_assessment
            if proportionality_assessment is not None:
                updates["proportionality_assessment"] = proportionality_assessment
            if next_review_date is not None:
                updates["next_review_date"] = next_review_date

            updated = pia.model_copy(update=updates)
            self._pias[pia_id] = updated

        logger.info("PIA updated: id=%s", pia_id)
        return updated

    # ------------------------------------------------------------------
    # Processing Activities
    # ------------------------------------------------------------------

    def add_processing_activity(
        self,
        pia_id: str,
        name: str,
        description: str,
        data_categories: list[DataCategoryType],
        processing_purpose: str,
        legal_basis: LegalBasis,
        data_subjects: list[DataSubjectType],
        retention_period_months: int,
        cross_border_transfer: bool = False,
        automated_decision_making: bool = False,
        third_party_sharing: bool = False,
        third_parties: list[str] | None = None,
    ) -> PIARecord:
        """Add a processing activity to a PIA.

        Args:
            pia_id: The PIA to add the activity to.
            name: Activity name.
            description: Activity description.
            data_categories: Categories of data processed.
            processing_purpose: Purpose of the processing.
            legal_basis: Legal basis for processing.
            data_subjects: Types of data subjects.
            retention_period_months: Retention period in months.
            cross_border_transfer: Whether data is transferred cross-border.
            automated_decision_making: Whether automated decisions are made.
            third_party_sharing: Whether data is shared with third parties.
            third_parties: List of third parties.

        Returns:
            The updated PIARecord.

        Raises:
            ValueError: If PIA not found.
        """
        with self._lock:
            pia = self._pias.get(pia_id)
            if pia is None:
                raise ValueError(f"PIA not found: {pia_id}")

            activity = DataProcessingActivity(
                id=f"ACT-{uuid4().hex[:8].upper()}",
                name=name,
                description=description,
                data_categories=data_categories,
                processing_purpose=processing_purpose,
                legal_basis=legal_basis,
                data_subjects=data_subjects,
                retention_period_months=retention_period_months,
                cross_border_transfer=cross_border_transfer,
                automated_decision_making=automated_decision_making,
                third_party_sharing=third_party_sharing,
                third_parties=third_parties or [],
            )

            activities = list(pia.processing_activities) + [activity]
            updated = pia.model_copy(
                update={
                    "processing_activities": activities,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            self._pias[pia_id] = updated

        logger.info("Processing activity added to PIA %s: %s", pia_id, name)
        return updated

    # ------------------------------------------------------------------
    # Privacy Risks
    # ------------------------------------------------------------------

    def add_risk(
        self,
        pia_id: str,
        title: str,
        description: str,
        likelihood: RiskLikelihood,
        impact: RiskImpact,
        affected_rights: list[AffectedRight] | None = None,
    ) -> PIARecord:
        """Add an identified risk to a PIA with auto-calculated risk score and level.

        Args:
            pia_id: The PIA to add the risk to.
            title: Risk title.
            description: Risk description.
            likelihood: Risk likelihood.
            impact: Risk impact.
            affected_rights: Data subject rights affected.

        Returns:
            The updated PIARecord.

        Raises:
            ValueError: If PIA not found.
        """
        risk_score = likelihood.value * impact.value
        risk_level = calculate_risk_level(risk_score)

        with self._lock:
            pia = self._pias.get(pia_id)
            if pia is None:
                raise ValueError(f"PIA not found: {pia_id}")

            risk = PrivacyRisk(
                id=f"RISK-{uuid4().hex[:8].upper()}",
                title=title,
                description=description,
                likelihood=likelihood,
                impact=impact,
                risk_score=risk_score,
                risk_level=risk_level,
                affected_rights=affected_rights or [],
                mitigation_measures=[],
                residual_risk_score=None,
                mitigation_status=MitigationStatus.PENDING,
            )

            risks = list(pia.identified_risks) + [risk]
            updated = pia.model_copy(
                update={
                    "identified_risks": risks,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            self._pias[pia_id] = updated

        logger.info(
            "Risk added to PIA %s: %s (score=%d, level=%s)",
            pia_id,
            title,
            risk_score,
            risk_level.value,
        )
        return updated

    def update_risk_mitigation(
        self,
        pia_id: str,
        risk_id: str,
        mitigation_measures: list[str],
        residual_risk_score: int,
    ) -> PIARecord:
        """Update mitigation measures for a risk.

        Args:
            pia_id: The PIA containing the risk.
            risk_id: The risk to update.
            mitigation_measures: Updated mitigation measures.
            residual_risk_score: Risk score after mitigation.

        Returns:
            The updated PIARecord.

        Raises:
            ValueError: If PIA or risk not found.
        """
        with self._lock:
            pia = self._pias.get(pia_id)
            if pia is None:
                raise ValueError(f"PIA not found: {pia_id}")

            updated_risks = []
            found = False
            for risk in pia.identified_risks:
                if risk.id == risk_id:
                    found = True
                    updated_risk = risk.model_copy(
                        update={
                            "mitigation_measures": mitigation_measures,
                            "residual_risk_score": residual_risk_score,
                            "mitigation_status": MitigationStatus.IN_PROGRESS,
                        }
                    )
                    updated_risks.append(updated_risk)
                else:
                    updated_risks.append(risk)

            if not found:
                raise ValueError(f"Risk not found: {risk_id}")

            updated = pia.model_copy(
                update={
                    "identified_risks": updated_risks,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            self._pias[pia_id] = updated

        logger.info("Risk mitigation updated for PIA %s, risk %s", pia_id, risk_id)
        return updated

    # ------------------------------------------------------------------
    # Workflow transitions
    # ------------------------------------------------------------------

    def submit_for_review(self, pia_id: str) -> PIARecord:
        """Submit a PIA for review (DRAFT -> IN_REVIEW).

        Args:
            pia_id: The PIA to submit.

        Returns:
            The updated PIARecord.

        Raises:
            ValueError: If PIA not found or invalid transition.
        """
        return self._transition(pia_id, PIAStatus.IN_REVIEW)

    def approve_pia(self, pia_id: str, reviewer: str) -> PIARecord:
        """Approve a PIA (IN_REVIEW -> APPROVED).

        All HIGH and CRITICAL risks must have mitigation measures before approval.

        Args:
            pia_id: The PIA to approve.
            reviewer: The reviewer approving the PIA.

        Returns:
            The updated PIARecord.

        Raises:
            ValueError: If PIA not found, invalid transition, or unmitigated high risks.
        """
        with self._lock:
            pia = self._pias.get(pia_id)
            if pia is None:
                raise ValueError(f"PIA not found: {pia_id}")

            # Check for unmitigated HIGH/CRITICAL risks
            unmitigated = [
                r
                for r in pia.identified_risks
                if r.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
                and r.mitigation_status in (MitigationStatus.PENDING,)
            ]
            if unmitigated:
                risk_titles = [r.title for r in unmitigated]
                raise ValueError(
                    f"Cannot approve PIA with unmitigated HIGH/CRITICAL risks: {risk_titles}"
                )

            valid_next = VALID_PIA_TRANSITIONS.get(pia.status, [])
            if PIAStatus.APPROVED not in valid_next:
                raise ValueError(
                    f"Invalid PIA status transition: {pia.status.value} -> APPROVED. "
                    f"Valid transitions: {[s.value for s in valid_next]}"
                )

            updated = pia.model_copy(
                update={
                    "status": PIAStatus.APPROVED,
                    "reviewer": reviewer,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            self._pias[pia_id] = updated

        logger.info("PIA approved: id=%s, reviewer=%s", pia_id, reviewer)
        return updated

    def request_dpo_approval(self, pia_id: str) -> PIARecord:
        """Flag a PIA for DPO review and approval.

        Args:
            pia_id: The PIA to flag for DPO approval.

        Returns:
            The updated PIARecord.

        Raises:
            ValueError: If PIA not found.
        """
        with self._lock:
            pia = self._pias.get(pia_id)
            if pia is None:
                raise ValueError(f"PIA not found: {pia_id}")

            updated = pia.model_copy(
                update={
                    "dpo_approval": True,
                    "dpo_approval_date": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            self._pias[pia_id] = updated

        logger.info("DPO approval requested for PIA: %s", pia_id)
        return updated

    def _transition(self, pia_id: str, target: PIAStatus) -> PIARecord:
        """Perform a state transition on a PIA.

        Args:
            pia_id: The PIA to transition.
            target: The target status.

        Returns:
            The updated PIARecord.

        Raises:
            ValueError: If PIA not found or invalid transition.
        """
        with self._lock:
            pia = self._pias.get(pia_id)
            if pia is None:
                raise ValueError(f"PIA not found: {pia_id}")

            valid_next = VALID_PIA_TRANSITIONS.get(pia.status, [])
            if target not in valid_next:
                raise ValueError(
                    f"Invalid PIA status transition: {pia.status.value} -> {target.value}. "
                    f"Valid transitions: {[s.value for s in valid_next]}"
                )

            updates: dict = {
                "status": target,
                "updated_at": datetime.now(timezone.utc),
            }
            if target == PIAStatus.COMPLETED:
                updates["completed_at"] = datetime.now(timezone.utc)

            updated = pia.model_copy(update=updates)
            self._pias[pia_id] = updated

        logger.info("PIA transitioned: id=%s, %s -> %s", pia_id, pia.status.value, target.value)
        return updated

    # ------------------------------------------------------------------
    # Consultation & Overdue
    # ------------------------------------------------------------------

    def check_consultation_required(self, pia_id: str) -> ConsultationCheckResponse:
        """Check if supervisory authority consultation is required.

        Returns True if:
        - Any risk is CRITICAL after mitigation, OR
        - Automated decision-making on special category data (CLINICAL, GENETIC)

        Args:
            pia_id: The PIA to check.

        Returns:
            ConsultationCheckResponse with result and reasons.

        Raises:
            ValueError: If PIA not found.
        """
        with self._lock:
            pia = self._pias.get(pia_id)
            if pia is None:
                raise ValueError(f"PIA not found: {pia_id}")

        reasons: list[str] = []

        # Check for CRITICAL residual risks
        for risk in pia.identified_risks:
            residual = risk.residual_risk_score
            if residual is not None and residual >= 20:
                reasons.append(
                    f"Risk '{risk.title}' has CRITICAL residual risk score ({residual})"
                )
            elif risk.risk_level == RiskLevel.CRITICAL and risk.residual_risk_score is None:
                reasons.append(
                    f"Risk '{risk.title}' has unmitigated CRITICAL risk level"
                )

        # Check for automated decision-making on special category data
        special_categories = {DataCategoryType.CLINICAL, DataCategoryType.GENETIC}
        for activity in pia.processing_activities:
            if activity.automated_decision_making:
                data_cats = set(activity.data_categories)
                if data_cats & special_categories:
                    reasons.append(
                        f"Activity '{activity.name}' uses automated decision-making "
                        f"on special category data ({', '.join(c.value for c in data_cats & special_categories)})"
                    )

        required = len(reasons) > 0

        # Update the PIA's consultation_required flag
        if required != pia.consultation_required:
            with self._lock:
                updated = pia.model_copy(
                    update={
                        "consultation_required": required,
                        "updated_at": datetime.now(timezone.utc),
                    }
                )
                self._pias[pia_id] = updated

        return ConsultationCheckResponse(
            consultation_required=required,
            reasons=reasons,
        )

    def get_overdue_reviews(self) -> list[PIARecord]:
        """Get PIAs that are past their next_review_date.

        Returns:
            List of overdue PIARecords.
        """
        now = datetime.now(timezone.utc)
        with self._lock:
            return [
                p
                for p in self._pias.values()
                if p.next_review_date is not None
                and p.next_review_date < now
                and p.status not in (PIAStatus.ARCHIVED,)
            ]

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> PIAMetrics:
        """Calculate aggregated PIA program metrics.

        Returns:
            PIAMetrics with program-level statistics.
        """
        with self._lock:
            all_pias = list(self._pias.values())

        total = len(all_pias)

        # Count by status
        by_status: dict[str, int] = {}
        for s in PIAStatus:
            count = sum(1 for p in all_pias if p.status == s)
            if count > 0:
                by_status[s.value] = count

        # High risk count: PIAs with at least one HIGH or CRITICAL risk
        high_risk_count = sum(
            1
            for p in all_pias
            if any(
                r.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
                for r in p.identified_risks
            )
        )

        # Open mitigations
        open_mitigations = sum(
            1
            for p in all_pias
            for r in p.identified_risks
            if r.mitigation_status in (MitigationStatus.PENDING, MitigationStatus.IN_PROGRESS)
        )

        # Average risk score
        all_scores = [
            r.risk_score for p in all_pias for r in p.identified_risks
        ]
        avg_risk_score = sum(all_scores) / len(all_scores) if all_scores else 0.0

        # Processing activities stats
        all_activities = [
            a for p in all_pias for a in p.processing_activities
        ]
        processing_activities_assessed = len(all_activities)
        cross_border_count = sum(
            1 for a in all_activities if a.cross_border_transfer
        )
        automated_decision_count = sum(
            1 for a in all_activities if a.automated_decision_making
        )

        return PIAMetrics(
            total_assessments=total,
            by_status=by_status,
            high_risk_count=high_risk_count,
            open_mitigations=open_mitigations,
            avg_risk_score=round(avg_risk_score, 2),
            processing_activities_assessed=processing_activities_assessed,
            cross_border_count=cross_border_count,
            automated_decision_count=automated_decision_count,
        )

    # ------------------------------------------------------------------
    # Templates
    # ------------------------------------------------------------------

    def get_templates(self) -> list[PIATemplate]:
        """List all PIA templates.

        Returns:
            List of PIATemplate objects.
        """
        with self._lock:
            return list(self._templates.values())

    def get_template(self, template_id: str) -> PIATemplate | None:
        """Get a PIA template by ID.

        Args:
            template_id: Template identifier.

        Returns:
            PIATemplate if found, None otherwise.
        """
        with self._lock:
            return self._templates.get(template_id)

    # ------------------------------------------------------------------
    # Service Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return service statistics for health checks."""
        with self._lock:
            total_pias = len(self._pias)
            total_templates = len(self._templates)
        return {
            "total_pias": total_pias,
            "total_templates": total_templates,
        }


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------


def get_privacy_impact_service() -> PrivacyImpactService:
    """Get or create the singleton PrivacyImpactService instance."""
    global _pia_service_instance
    if _pia_service_instance is None:
        with _pia_service_lock:
            if _pia_service_instance is None:
                _pia_service_instance = PrivacyImpactService()
    return _pia_service_instance


def reset_privacy_impact_service() -> None:
    """Reset the singleton for testing."""
    global _pia_service_instance
    with _pia_service_lock:
        _pia_service_instance = None
