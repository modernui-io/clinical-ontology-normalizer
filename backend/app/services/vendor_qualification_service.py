"""Vendor Qualification & Oversight Service (QA-VENDOR).

Manages CRO, central lab, and service provider qualification, performance
monitoring, quality agreements, risk assessments, and vendor scorecards
for clinical trial operations.

Usage:
    from app.services.vendor_qualification_service import (
        get_vendor_qualification_service,
    )

    svc = get_vendor_qualification_service()
    vendors = svc.list_vendors()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.vendor_qualification import (
    AgreementStatus,
    PerformanceRating,
    QualificationStatus,
    QualityAgreement,
    QualityAgreementCreate,
    QualityAgreementUpdate,
    RiskLevel,
    Vendor,
    VendorAssessment,
    VendorAssessmentCreate,
    VendorCategory,
    VendorCreate,
    VendorQualificationMetrics,
    VendorRiskAssessment,
    VendorRiskAssessmentCreate,
    VendorUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class VendorQualificationService:
    """In-memory Vendor Qualification & Oversight engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._vendors: dict[str, Vendor] = {}
        self._agreements: dict[str, QualityAgreement] = {}
        self._assessments: dict[str, VendorAssessment] = {}
        self._risk_assessments: dict[str, VendorRiskAssessment] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic vendor qualification data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Vendors ---
        vendors_data = [
            {
                "id": "VND-001",
                "name": "Covance Drug Development (LabCorp)",
                "category": VendorCategory.CRO,
                "qualification_status": QualificationStatus.QUALIFIED,
                "risk_level": RiskLevel.LOW,
                "contact_name": "Jennifer Walsh",
                "contact_email": "jennifer.walsh@covance.com",
                "country": "United States",
                "services_provided": ["Phase I-IV clinical monitoring", "Data management", "Biostatistics", "Regulatory affairs"],
                "qualification_date": now - timedelta(days=365),
                "requalification_due_date": now + timedelta(days=180),
                "active_trials": [EYLEA_TRIAL, DUPIXENT_TRIAL],
                "overall_rating": PerformanceRating.EXCELLENT,
                "created_at": now - timedelta(days=730),
            },
            {
                "id": "VND-002",
                "name": "ICON Clinical Research",
                "category": VendorCategory.CRO,
                "qualification_status": QualificationStatus.QUALIFIED,
                "risk_level": RiskLevel.LOW,
                "contact_name": "Brian McAllister",
                "contact_email": "brian.mcallister@iconplc.com",
                "country": "Ireland",
                "services_provided": ["Full-service CRO", "Adaptive trial design", "Oncology expertise", "Regulatory strategy"],
                "qualification_date": now - timedelta(days=300),
                "requalification_due_date": now + timedelta(days=240),
                "active_trials": [LIBTAYO_TRIAL],
                "overall_rating": PerformanceRating.GOOD,
                "created_at": now - timedelta(days=600),
            },
            {
                "id": "VND-003",
                "name": "Q2 Solutions (IQVIA)",
                "category": VendorCategory.CENTRAL_LAB,
                "qualification_status": QualificationStatus.QUALIFIED,
                "risk_level": RiskLevel.LOW,
                "contact_name": "Dr. Rachel Kim",
                "contact_email": "rachel.kim@q2labsolutions.com",
                "country": "United States",
                "services_provided": ["Central laboratory services", "Biomarker analysis", "Genomics", "Specialty testing"],
                "qualification_date": now - timedelta(days=400),
                "requalification_due_date": now + timedelta(days=145),
                "active_trials": [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL],
                "overall_rating": PerformanceRating.EXCELLENT,
                "created_at": now - timedelta(days=800),
            },
            {
                "id": "VND-004",
                "name": "Signant Health (formerly Bracket)",
                "category": VendorCategory.IRT_PROVIDER,
                "qualification_status": QualificationStatus.QUALIFIED,
                "risk_level": RiskLevel.MEDIUM,
                "contact_name": "Thomas Grant",
                "contact_email": "thomas.grant@signanthealth.com",
                "country": "United States",
                "services_provided": ["RTSM/IRT systems", "eCOA/ePRO", "Patient randomization", "Drug supply management"],
                "qualification_date": now - timedelta(days=200),
                "requalification_due_date": now + timedelta(days=345),
                "active_trials": [EYLEA_TRIAL, DUPIXENT_TRIAL],
                "overall_rating": PerformanceRating.GOOD,
                "created_at": now - timedelta(days=500),
            },
            {
                "id": "VND-005",
                "name": "Medidata Solutions (Dassault)",
                "category": VendorCategory.EDC_PROVIDER,
                "qualification_status": QualificationStatus.QUALIFIED,
                "risk_level": RiskLevel.LOW,
                "contact_name": "Lisa Nguyen",
                "contact_email": "lisa.nguyen@medidata.com",
                "country": "United States",
                "services_provided": ["Rave EDC platform", "RBQM analytics", "Clinical data management", "21 CFR Part 11 compliance"],
                "qualification_date": now - timedelta(days=500),
                "requalification_due_date": now + timedelta(days=45),
                "active_trials": [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL],
                "overall_rating": PerformanceRating.EXCELLENT,
                "created_at": now - timedelta(days=900),
            },
            {
                "id": "VND-006",
                "name": "Sharp Clinical Services",
                "category": VendorCategory.PACKAGING,
                "qualification_status": QualificationStatus.QUALIFIED,
                "risk_level": RiskLevel.MEDIUM,
                "contact_name": "David Armstrong",
                "contact_email": "david.armstrong@sharpclinical.com",
                "country": "United States",
                "services_provided": ["Clinical packaging", "Labeling", "Serialization", "Cold chain packaging"],
                "qualification_date": now - timedelta(days=250),
                "requalification_due_date": now + timedelta(days=295),
                "active_trials": [EYLEA_TRIAL, LIBTAYO_TRIAL],
                "overall_rating": PerformanceRating.GOOD,
                "created_at": now - timedelta(days=550),
            },
            {
                "id": "VND-007",
                "name": "Marken (UPS Healthcare)",
                "category": VendorCategory.LOGISTICS,
                "qualification_status": QualificationStatus.QUALIFIED,
                "risk_level": RiskLevel.MEDIUM,
                "contact_name": "Sarah Collins",
                "contact_email": "sarah.collins@marken.com",
                "country": "United Kingdom",
                "services_provided": ["Clinical trial logistics", "Cold chain management", "Direct-to-patient delivery", "Depot management"],
                "qualification_date": now - timedelta(days=180),
                "requalification_due_date": now + timedelta(days=365),
                "active_trials": [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL],
                "overall_rating": PerformanceRating.ACCEPTABLE,
                "created_at": now - timedelta(days=400),
            },
            {
                "id": "VND-008",
                "name": "Bioclinica (Clario)",
                "category": VendorCategory.IMAGING,
                "qualification_status": QualificationStatus.CONDITIONALLY_QUALIFIED,
                "risk_level": RiskLevel.HIGH,
                "contact_name": "Dr. Mark Peterson",
                "contact_email": "mark.peterson@clario.com",
                "country": "United States",
                "services_provided": ["Medical imaging", "Cardiac safety (ECG)", "Imaging endpoint adjudication", "Reader training"],
                "qualification_date": now - timedelta(days=90),
                "requalification_due_date": now + timedelta(days=90),
                "active_trials": [EYLEA_TRIAL, LIBTAYO_TRIAL],
                "overall_rating": PerformanceRating.BELOW_EXPECTATIONS,
                "created_at": now - timedelta(days=365),
            },
            {
                "id": "VND-009",
                "name": "PPD Bioanalytical Lab (Thermo Fisher)",
                "category": VendorCategory.BIOANALYTICAL_LAB,
                "qualification_status": QualificationStatus.QUALIFIED,
                "risk_level": RiskLevel.LOW,
                "contact_name": "Dr. Amanda Foster",
                "contact_email": "amanda.foster@ppd.com",
                "country": "United States",
                "services_provided": ["PK/PD analysis", "Immunogenicity testing", "Biomarker assay development", "Method validation"],
                "qualification_date": now - timedelta(days=350),
                "requalification_due_date": now + timedelta(days=195),
                "active_trials": [DUPIXENT_TRIAL, LIBTAYO_TRIAL],
                "overall_rating": PerformanceRating.EXCELLENT,
                "created_at": now - timedelta(days=700),
            },
            {
                "id": "VND-010",
                "name": "Argus Safety (Oracle Health Sciences)",
                "category": VendorCategory.SAFETY_DATABASE,
                "qualification_status": QualificationStatus.REQUALIFICATION_DUE,
                "risk_level": RiskLevel.HIGH,
                "contact_name": "Robert Chen",
                "contact_email": "robert.chen@oracle.com",
                "country": "United States",
                "services_provided": ["Safety database management", "ICSR processing", "Signal detection", "Regulatory reporting (CIOMS/MedWatch)"],
                "qualification_date": now - timedelta(days=600),
                "requalification_due_date": now - timedelta(days=15),
                "active_trials": [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL],
                "overall_rating": PerformanceRating.ACCEPTABLE,
                "created_at": now - timedelta(days=900),
            },
            {
                "id": "VND-011",
                "name": "Trilogy Writing & Consulting",
                "category": VendorCategory.MEDICAL_WRITING,
                "qualification_status": QualificationStatus.QUALIFIED,
                "risk_level": RiskLevel.LOW,
                "contact_name": "Dr. Katherine Wells",
                "contact_email": "katherine.wells@trilogywriting.com",
                "country": "Germany",
                "services_provided": ["CSR writing", "Protocol development", "IB updates", "Regulatory submissions"],
                "qualification_date": now - timedelta(days=270),
                "requalification_due_date": now + timedelta(days=275),
                "active_trials": [DUPIXENT_TRIAL, LIBTAYO_TRIAL],
                "overall_rating": PerformanceRating.GOOD,
                "created_at": now - timedelta(days=500),
            },
            {
                "id": "VND-012",
                "name": "Parexel International",
                "category": VendorCategory.CRO,
                "qualification_status": QualificationStatus.DISQUALIFIED,
                "risk_level": RiskLevel.CRITICAL,
                "contact_name": "James O'Brien",
                "contact_email": "james.obrien@parexel.com",
                "country": "United States",
                "services_provided": ["Phase I-IV CRO services", "Regulatory consulting", "Post-market surveillance"],
                "qualification_date": now - timedelta(days=500),
                "requalification_due_date": None,
                "active_trials": [],
                "overall_rating": PerformanceRating.UNACCEPTABLE,
                "created_at": now - timedelta(days=1000),
            },
        ]

        for v in vendors_data:
            self._vendors[v["id"]] = Vendor(**v)

        # --- 15 Quality Agreements ---
        agreements_data = [
            {"id": "QA-001", "vendor_id": "VND-001", "trial_id": EYLEA_TRIAL, "agreement_number": "QA-2024-001", "title": "Covance CRO Services - EYLEA HD Phase III", "status": AgreementStatus.EXECUTED, "effective_date": now - timedelta(days=300), "expiry_date": now + timedelta(days=430), "signed_by_sponsor": "Dr. George Yancopoulos", "signed_by_vendor": "Jennifer Walsh", "key_terms": ["GCP compliance", "Source data verification >95%", "Query resolution <5 business days", "SAE reporting <24 hours"], "created_at": now - timedelta(days=320)},
            {"id": "QA-002", "vendor_id": "VND-001", "trial_id": DUPIXENT_TRIAL, "agreement_number": "QA-2024-002", "title": "Covance CRO Services - Dupixent Atopic Dermatitis Phase III", "status": AgreementStatus.EXECUTED, "effective_date": now - timedelta(days=280), "expiry_date": now + timedelta(days=450), "signed_by_sponsor": "Dr. George Yancopoulos", "signed_by_vendor": "Jennifer Walsh", "key_terms": ["GCP compliance", "Monitoring visit frequency biweekly", "EASI scoring quality assurance", "Data lock readiness"], "created_at": now - timedelta(days=300)},
            {"id": "QA-003", "vendor_id": "VND-002", "trial_id": LIBTAYO_TRIAL, "agreement_number": "QA-2024-003", "title": "ICON CRO Services - Libtayo Oncology Phase III", "status": AgreementStatus.EXECUTED, "effective_date": now - timedelta(days=250), "expiry_date": now + timedelta(days=480), "signed_by_sponsor": "Dr. Israel Lowy", "signed_by_vendor": "Brian McAllister", "key_terms": ["Oncology protocol compliance", "RECIST 1.1 assessment QC", "irAE reporting <12 hours", "DSMB coordination"], "created_at": now - timedelta(days=270)},
            {"id": "QA-004", "vendor_id": "VND-003", "trial_id": EYLEA_TRIAL, "agreement_number": "QA-2024-004", "title": "Q2 Solutions Central Lab - EYLEA HD Ocular Biomarkers", "status": AgreementStatus.EXECUTED, "effective_date": now - timedelta(days=350), "expiry_date": now + timedelta(days=380), "signed_by_sponsor": "Dr. Nicholas Bhatt", "signed_by_vendor": "Dr. Rachel Kim", "key_terms": ["Sample turnaround <48 hours", "CLIA/CAP accreditation maintained", "Temperature excursion reporting", "Biomarker assay validation"], "created_at": now - timedelta(days=370)},
            {"id": "QA-005", "vendor_id": "VND-003", "trial_id": DUPIXENT_TRIAL, "agreement_number": "QA-2024-005", "title": "Q2 Solutions Central Lab - Dupixent Immunology Panel", "status": AgreementStatus.EXECUTED, "effective_date": now - timedelta(days=340), "expiry_date": now + timedelta(days=390), "signed_by_sponsor": "Dr. Nicholas Bhatt", "signed_by_vendor": "Dr. Rachel Kim", "key_terms": ["IgE/cytokine panel consistency", "External quality assessment participation", "Specimen stability protocols", "Result reconciliation monthly"], "created_at": now - timedelta(days=360)},
            {"id": "QA-006", "vendor_id": "VND-004", "trial_id": EYLEA_TRIAL, "agreement_number": "QA-2024-006", "title": "Signant Health IRT - EYLEA HD Randomization System", "status": AgreementStatus.EXECUTED, "effective_date": now - timedelta(days=180), "expiry_date": now + timedelta(days=550), "signed_by_sponsor": "Dr. David Weinreich", "signed_by_vendor": "Thomas Grant", "key_terms": ["System uptime >99.5%", "Randomization stratification accuracy", "Emergency unblinding <30 min", "21 CFR Part 11 compliance"], "created_at": now - timedelta(days=200)},
            {"id": "QA-007", "vendor_id": "VND-005", "trial_id": EYLEA_TRIAL, "agreement_number": "QA-2024-007", "title": "Medidata Rave EDC - EYLEA HD Data Management", "status": AgreementStatus.EXECUTED, "effective_date": now - timedelta(days=450), "expiry_date": now + timedelta(days=280), "signed_by_sponsor": "Dr. David Weinreich", "signed_by_vendor": "Lisa Nguyen", "key_terms": ["EDC system validation", "Edit check programming", "Data migration support", "Audit trail maintenance"], "created_at": now - timedelta(days=470)},
            {"id": "QA-008", "vendor_id": "VND-006", "trial_id": EYLEA_TRIAL, "agreement_number": "QA-2024-008", "title": "Sharp Clinical Packaging - EYLEA HD Intravitreal Kits", "status": AgreementStatus.EXECUTED, "effective_date": now - timedelta(days=220), "expiry_date": now + timedelta(days=510), "signed_by_sponsor": "VP Clinical Supply", "signed_by_vendor": "David Armstrong", "key_terms": ["Cold chain 2-8C compliance", "Blinding integrity verification", "Serialization per EU FMD", "Shelf life monitoring"], "created_at": now - timedelta(days=240)},
            {"id": "QA-009", "vendor_id": "VND-007", "trial_id": DUPIXENT_TRIAL, "agreement_number": "QA-2024-009", "title": "Marken Logistics - Dupixent Global Distribution", "status": AgreementStatus.UNDER_REVIEW, "effective_date": None, "expiry_date": None, "signed_by_sponsor": None, "signed_by_vendor": None, "key_terms": ["Temperature monitoring during transit", "Customs clearance SLA", "Direct-to-patient capability", "GDP compliance"], "created_at": now - timedelta(days=30)},
            {"id": "QA-010", "vendor_id": "VND-008", "trial_id": EYLEA_TRIAL, "agreement_number": "QA-2024-010", "title": "Clario Imaging - EYLEA HD OCT Reading Center", "status": AgreementStatus.EXECUTED, "effective_date": now - timedelta(days=80), "expiry_date": now + timedelta(days=650), "signed_by_sponsor": "Dr. Nicholas Bhatt", "signed_by_vendor": "Dr. Mark Peterson", "key_terms": ["OCT grading consistency >90%", "Reader certification required", "Inter-reader variability <5%", "Masked reading protocol"], "created_at": now - timedelta(days=100)},
            {"id": "QA-011", "vendor_id": "VND-009", "trial_id": DUPIXENT_TRIAL, "agreement_number": "QA-2024-011", "title": "PPD Bioanalytical - Dupixent PK/ADA Analysis", "status": AgreementStatus.EXECUTED, "effective_date": now - timedelta(days=300), "expiry_date": now + timedelta(days=430), "signed_by_sponsor": "Dr. Neil Stahl", "signed_by_vendor": "Dr. Amanda Foster", "key_terms": ["Validated assay methods", "Incurred sample reanalysis", "ADA tiered testing approach", "GLP compliance"], "created_at": now - timedelta(days=320)},
            {"id": "QA-012", "vendor_id": "VND-010", "trial_id": EYLEA_TRIAL, "agreement_number": "QA-2024-012", "title": "Oracle Argus - EYLEA HD Safety Database", "status": AgreementStatus.EXPIRED, "effective_date": now - timedelta(days=600), "expiry_date": now - timedelta(days=15), "signed_by_sponsor": "VP Pharmacovigilance", "signed_by_vendor": "Robert Chen", "key_terms": ["E2B(R3) compliance", "ICSR processing <3 business days", "MedDRA coding accuracy", "Periodic safety report support"], "created_at": now - timedelta(days=620)},
            {"id": "QA-013", "vendor_id": "VND-011", "trial_id": LIBTAYO_TRIAL, "agreement_number": "QA-2024-013", "title": "Trilogy Medical Writing - Libtayo CSR & Regulatory", "status": AgreementStatus.EXECUTED, "effective_date": now - timedelta(days=200), "expiry_date": now + timedelta(days=530), "signed_by_sponsor": "VP Regulatory Affairs", "signed_by_vendor": "Dr. Katherine Wells", "key_terms": ["ICH E3 compliance", "CSR draft <60 days post-DBL", "Regulatory response <10 business days", "QC review process"], "created_at": now - timedelta(days=220)},
            {"id": "QA-014", "vendor_id": "VND-003", "trial_id": LIBTAYO_TRIAL, "agreement_number": "QA-2024-014", "title": "Q2 Solutions Central Lab - Libtayo Tumor Biomarkers", "status": AgreementStatus.DRAFT, "effective_date": None, "expiry_date": None, "signed_by_sponsor": None, "signed_by_vendor": None, "key_terms": ["PD-L1 IHC scoring standardization", "ctDNA analysis", "TMB assessment", "Sample shipping logistics"], "created_at": now - timedelta(days=10)},
            {"id": "QA-015", "vendor_id": "VND-012", "trial_id": EYLEA_TRIAL, "agreement_number": "QA-2023-015", "title": "Parexel CRO Services - EYLEA Legacy Trial (Terminated)", "status": AgreementStatus.TERMINATED, "effective_date": now - timedelta(days=500), "expiry_date": now - timedelta(days=200), "signed_by_sponsor": "VP Clinical Operations", "signed_by_vendor": "James O'Brien", "key_terms": ["GCP compliance", "Site monitoring", "Data management", "Regulatory filings"], "created_at": now - timedelta(days=520)},
        ]

        for a in agreements_data:
            self._agreements[a["id"]] = QualityAgreement(**a)

        # --- 15 Vendor Assessments ---
        assessments_data = [
            {"id": "VA-001", "vendor_id": "VND-001", "trial_id": EYLEA_TRIAL, "assessment_date": now - timedelta(days=30), "assessor": "Dr. Sarah Mitchell", "quality_score": 95.0, "timeliness_score": 92.0, "communication_score": 90.0, "compliance_score": 98.0, "rating": PerformanceRating.EXCELLENT, "strengths": ["Outstanding GCP compliance", "Proactive risk identification", "Experienced monitors"], "improvements_needed": ["Faster CRF query resolution"], "notes": "Annual performance review - consistently high performer."},
            {"id": "VA-002", "vendor_id": "VND-001", "trial_id": DUPIXENT_TRIAL, "assessment_date": now - timedelta(days=25), "assessor": "Dr. Sarah Mitchell", "quality_score": 93.0, "timeliness_score": 88.0, "communication_score": 91.0, "compliance_score": 96.0, "rating": PerformanceRating.EXCELLENT, "strengths": ["Strong therapeutic expertise", "Efficient site activation", "Quality source data review"], "improvements_needed": ["Monitoring report timeliness"], "notes": "Strong performance across all Dupixent sites."},
            {"id": "VA-003", "vendor_id": "VND-002", "trial_id": LIBTAYO_TRIAL, "assessment_date": now - timedelta(days=45), "assessor": "Dr. Michael Torres", "quality_score": 85.0, "timeliness_score": 82.0, "communication_score": 88.0, "compliance_score": 90.0, "rating": PerformanceRating.GOOD, "strengths": ["Oncology domain expertise", "Adaptive design capability", "Strong project management"], "improvements_needed": ["Reduce monitoring visit backlog", "Improve data entry timeliness"], "notes": "Good overall but minor delays in some regions."},
            {"id": "VA-004", "vendor_id": "VND-003", "trial_id": EYLEA_TRIAL, "assessment_date": now - timedelta(days=60), "assessor": "Dr. Emily Richards", "quality_score": 97.0, "timeliness_score": 95.0, "communication_score": 93.0, "compliance_score": 99.0, "rating": PerformanceRating.EXCELLENT, "strengths": ["Exceptional sample processing speed", "Zero temperature excursions", "Proactive alerts on out-of-range results"], "improvements_needed": [], "notes": "Top-tier central lab performance."},
            {"id": "VA-005", "vendor_id": "VND-004", "trial_id": EYLEA_TRIAL, "assessment_date": now - timedelta(days=90), "assessor": "Dr. James Park", "quality_score": 80.0, "timeliness_score": 78.0, "communication_score": 82.0, "compliance_score": 85.0, "rating": PerformanceRating.GOOD, "strengths": ["Reliable randomization system", "Good training materials"], "improvements_needed": ["System response time during peak hours", "Help desk availability"], "notes": "Meets expectations with room for improvement in system performance."},
            {"id": "VA-006", "vendor_id": "VND-005", "trial_id": DUPIXENT_TRIAL, "assessment_date": now - timedelta(days=40), "assessor": "Dr. Linda Chen", "quality_score": 94.0, "timeliness_score": 96.0, "communication_score": 92.0, "compliance_score": 97.0, "rating": PerformanceRating.EXCELLENT, "strengths": ["Industry-leading EDC platform", "Excellent edit check design", "Responsive support team"], "improvements_needed": ["Custom report generation speed"], "notes": "Consistently excellent EDC service delivery."},
            {"id": "VA-007", "vendor_id": "VND-006", "trial_id": EYLEA_TRIAL, "assessment_date": now - timedelta(days=75), "assessor": "Supply Chain Manager", "quality_score": 82.0, "timeliness_score": 79.0, "communication_score": 80.0, "compliance_score": 88.0, "rating": PerformanceRating.GOOD, "strengths": ["Cold chain integrity maintained", "Good serialization tracking"], "improvements_needed": ["Label verification turnaround", "Secondary packaging quality checks"], "notes": "Solid packaging performance with minor labeling delays."},
            {"id": "VA-008", "vendor_id": "VND-007", "trial_id": DUPIXENT_TRIAL, "assessment_date": now - timedelta(days=50), "assessor": "Logistics Director", "quality_score": 72.0, "timeliness_score": 68.0, "communication_score": 75.0, "compliance_score": 78.0, "rating": PerformanceRating.ACCEPTABLE, "strengths": ["Global coverage", "Customs expertise"], "improvements_needed": ["On-time delivery rate below target", "Temperature excursion rate", "Communication on delays"], "notes": "Below target on timeliness metrics. CAPA initiated for delivery delays."},
            {"id": "VA-009", "vendor_id": "VND-008", "trial_id": EYLEA_TRIAL, "assessment_date": now - timedelta(days=20), "assessor": "Dr. Nicholas Bhatt", "quality_score": 62.0, "timeliness_score": 58.0, "communication_score": 65.0, "compliance_score": 70.0, "rating": PerformanceRating.BELOW_EXPECTATIONS, "strengths": ["Advanced imaging technology"], "improvements_needed": ["OCT grading consistency", "Reader turnaround time", "Inter-reader variability above threshold", "Training completion rate"], "notes": "Conditionally qualified pending corrective actions. Reader retraining required."},
            {"id": "VA-010", "vendor_id": "VND-009", "trial_id": DUPIXENT_TRIAL, "assessment_date": now - timedelta(days=35), "assessor": "Dr. Amanda Foster", "quality_score": 96.0, "timeliness_score": 94.0, "communication_score": 91.0, "compliance_score": 98.0, "rating": PerformanceRating.EXCELLENT, "strengths": ["Method validation excellence", "ISR compliance >97%", "Rapid assay troubleshooting"], "improvements_needed": [], "notes": "Best-in-class bioanalytical services."},
            {"id": "VA-011", "vendor_id": "VND-010", "trial_id": EYLEA_TRIAL, "assessment_date": now - timedelta(days=15), "assessor": "PV Operations Lead", "quality_score": 70.0, "timeliness_score": 65.0, "communication_score": 72.0, "compliance_score": 74.0, "rating": PerformanceRating.ACCEPTABLE, "strengths": ["Established E2B infrastructure", "MedDRA coding accuracy"], "improvements_needed": ["ICSR processing backlog", "System upgrade needed", "Requalification overdue", "Periodic report delays"], "notes": "Requalification overdue. System upgrade planned for next quarter."},
            {"id": "VA-012", "vendor_id": "VND-011", "trial_id": LIBTAYO_TRIAL, "assessment_date": now - timedelta(days=55), "assessor": "Regulatory Writing Lead", "quality_score": 87.0, "timeliness_score": 84.0, "communication_score": 89.0, "compliance_score": 91.0, "rating": PerformanceRating.GOOD, "strengths": ["High-quality scientific writing", "Regulatory expertise", "Responsive to feedback"], "improvements_needed": ["First-draft timeline adherence"], "notes": "Strong medical writing support for Libtayo regulatory submissions."},
            {"id": "VA-013", "vendor_id": "VND-012", "trial_id": EYLEA_TRIAL, "assessment_date": now - timedelta(days=200), "assessor": "VP Clinical Operations", "quality_score": 35.0, "timeliness_score": 30.0, "communication_score": 40.0, "compliance_score": 28.0, "rating": PerformanceRating.UNACCEPTABLE, "strengths": [], "improvements_needed": ["Critical GCP violations", "Unreported protocol deviations", "Inadequate monitor training", "Data integrity concerns"], "notes": "Vendor disqualified following for-cause audit. All studies transitioned to alternative CRO."},
            {"id": "VA-014", "vendor_id": "VND-003", "trial_id": LIBTAYO_TRIAL, "assessment_date": now - timedelta(days=80), "assessor": "Dr. Emily Richards", "quality_score": 91.0, "timeliness_score": 89.0, "communication_score": 87.0, "compliance_score": 94.0, "rating": PerformanceRating.EXCELLENT, "strengths": ["Consistent biomarker results", "Robust sample tracking system", "Excellent inter-lab correlation"], "improvements_needed": ["PD-L1 staining batch variation"], "notes": "Excellent performance on tumor biomarker program."},
            {"id": "VA-015", "vendor_id": "VND-005", "trial_id": LIBTAYO_TRIAL, "assessment_date": now - timedelta(days=100), "assessor": "Data Management Lead", "quality_score": 90.0, "timeliness_score": 93.0, "communication_score": 88.0, "compliance_score": 95.0, "rating": PerformanceRating.EXCELLENT, "strengths": ["Seamless EDC deployment", "Excellent RBQM analytics", "Strong validation framework"], "improvements_needed": ["Complex form rendering speed"], "notes": "Rave platform continues to perform well across oncology trials."},
        ]

        for a in assessments_data:
            overall = (a["quality_score"] + a["timeliness_score"] + a["communication_score"] + a["compliance_score"]) / 4.0
            a["overall_score"] = round(overall, 1)
            self._assessments[a["id"]] = VendorAssessment(**a)

        # --- 12 Risk Assessments ---
        risk_assessments_data = [
            {"id": "VRA-001", "vendor_id": "VND-001", "assessed_date": now - timedelta(days=60), "assessed_by": "Quality Assurance Director", "risk_level": RiskLevel.LOW, "risk_factors": ["Large vendor with multiple ongoing programs"], "mitigation_plan": "Standard oversight per qualified vendor SOP.", "next_review_date": now + timedelta(days=120)},
            {"id": "VRA-002", "vendor_id": "VND-002", "assessed_date": now - timedelta(days=45), "assessed_by": "Quality Assurance Director", "risk_level": RiskLevel.LOW, "risk_factors": ["International operations across multiple jurisdictions", "First engagement for oncology"], "mitigation_plan": "Enhanced monitoring for first 6 months. Quarterly oversight calls.", "next_review_date": now + timedelta(days=90)},
            {"id": "VRA-003", "vendor_id": "VND-003", "assessed_date": now - timedelta(days=90), "assessed_by": "Lab Operations Manager", "risk_level": RiskLevel.LOW, "risk_factors": ["High sample volume across 3 trials"], "mitigation_plan": "Monthly sample volume capacity review. Backup lab identified.", "next_review_date": now + timedelta(days=90)},
            {"id": "VRA-004", "vendor_id": "VND-004", "assessed_date": now - timedelta(days=100), "assessed_by": "IT Systems Manager", "risk_level": RiskLevel.MEDIUM, "risk_factors": ["System integration complexity", "Peak usage performance concerns", "Single point of failure for randomization"], "mitigation_plan": "Quarterly system performance testing. Disaster recovery drill annually. Backup randomization procedure documented.", "next_review_date": now + timedelta(days=60)},
            {"id": "VRA-005", "vendor_id": "VND-005", "assessed_date": now - timedelta(days=120), "assessed_by": "Data Management Director", "risk_level": RiskLevel.LOW, "risk_factors": ["Platform dependency across all trials"], "mitigation_plan": "Annual vendor audit. Data migration plan maintained as contingency.", "next_review_date": now + timedelta(days=60)},
            {"id": "VRA-006", "vendor_id": "VND-007", "assessed_date": now - timedelta(days=30), "assessed_by": "Supply Chain Director", "risk_level": RiskLevel.MEDIUM, "risk_factors": ["Recent delivery delays in APAC region", "Temperature excursions above threshold", "Customs clearance bottlenecks"], "mitigation_plan": "Weekly tracking calls. Secondary logistics partner identified for APAC. Enhanced temperature monitoring.", "next_review_date": now + timedelta(days=30)},
            {"id": "VRA-007", "vendor_id": "VND-008", "assessed_date": now - timedelta(days=15), "assessed_by": "Medical Director Ophthalmology", "risk_level": RiskLevel.HIGH, "risk_factors": ["OCT grading inconsistency >10%", "Reader turnaround time above SLA", "Insufficient certified readers", "Recent staff turnover in reading center"], "mitigation_plan": "Reader retraining program initiated. Additional readers to be certified within 60 days. Weekly quality metrics review.", "next_review_date": now + timedelta(days=30)},
            {"id": "VRA-008", "vendor_id": "VND-010", "assessed_date": now - timedelta(days=10), "assessed_by": "PV Operations Director", "risk_level": RiskLevel.HIGH, "risk_factors": ["Requalification overdue by 15 days", "ICSR processing backlog", "Legacy system nearing end-of-life", "Key personnel departures"], "mitigation_plan": "Urgent requalification audit scheduled. Interim oversight enhanced to weekly reviews. System migration timeline accelerated.", "next_review_date": now + timedelta(days=14)},
            {"id": "VRA-009", "vendor_id": "VND-012", "assessed_date": now - timedelta(days=200), "assessed_by": "VP Quality Assurance", "risk_level": RiskLevel.CRITICAL, "risk_factors": ["GCP violations identified in for-cause audit", "Unreported protocol deviations", "Data integrity findings", "Inadequate CAPA response"], "mitigation_plan": "Vendor disqualified. All studies transitioned. Regulatory notification submitted. Lessons learned incorporated.", "next_review_date": None},
            {"id": "VRA-010", "vendor_id": "VND-006", "assessed_date": now - timedelta(days=70), "assessed_by": "Supply Chain Manager", "risk_level": RiskLevel.MEDIUM, "risk_factors": ["Label verification delays", "Secondary packaging inconsistencies"], "mitigation_plan": "Additional QC checkpoint added. Labeling SOP revision. Monthly quality review meetings.", "next_review_date": now + timedelta(days=60)},
            {"id": "VRA-011", "vendor_id": "VND-009", "assessed_date": now - timedelta(days=50), "assessed_by": "Lab Operations Manager", "risk_level": RiskLevel.LOW, "risk_factors": ["High demand for immunogenicity testing capacity"], "mitigation_plan": "Capacity planning review. Advance scheduling for peak periods.", "next_review_date": now + timedelta(days=120)},
            {"id": "VRA-012", "vendor_id": "VND-011", "assessed_date": now - timedelta(days=40), "assessed_by": "Regulatory Writing Lead", "risk_level": RiskLevel.LOW, "risk_factors": ["Timeline pressure on concurrent CSRs"], "mitigation_plan": "Staggered deliverable schedule. Backup writers identified.", "next_review_date": now + timedelta(days=90)},
        ]

        for r in risk_assessments_data:
            self._risk_assessments[r["id"]] = VendorRiskAssessment(**r)

    # ------------------------------------------------------------------
    # Vendor Management
    # ------------------------------------------------------------------

    def list_vendors(
        self,
        *,
        category: VendorCategory | None = None,
        qualification_status: QualificationStatus | None = None,
        risk_level: RiskLevel | None = None,
        trial_id: str | None = None,
    ) -> list[Vendor]:
        """List vendors with optional filters."""
        with self._lock:
            result = list(self._vendors.values())

        if category is not None:
            result = [v for v in result if v.category == category]
        if qualification_status is not None:
            result = [v for v in result if v.qualification_status == qualification_status]
        if risk_level is not None:
            result = [v for v in result if v.risk_level == risk_level]
        if trial_id is not None:
            result = [v for v in result if trial_id in v.active_trials]

        return sorted(result, key=lambda v: v.id)

    def get_vendor(self, vendor_id: str) -> Vendor | None:
        """Get a single vendor by ID."""
        with self._lock:
            return self._vendors.get(vendor_id)

    def create_vendor(self, payload: VendorCreate) -> Vendor:
        """Create a new vendor."""
        now = datetime.now(timezone.utc)
        vendor_id = f"VND-{uuid4().hex[:8].upper()}"
        vendor = Vendor(
            id=vendor_id,
            name=payload.name,
            category=payload.category,
            qualification_status=QualificationStatus.PENDING,
            risk_level=payload.risk_level,
            contact_name=payload.contact_name,
            contact_email=payload.contact_email,
            country=payload.country,
            services_provided=payload.services_provided,
            qualification_date=None,
            requalification_due_date=None,
            active_trials=[],
            overall_rating=None,
            created_at=now,
        )
        with self._lock:
            self._vendors[vendor_id] = vendor
        logger.info("Created vendor %s: %s", vendor_id, payload.name)
        return vendor

    def update_vendor(
        self, vendor_id: str, payload: VendorUpdate
    ) -> Vendor | None:
        """Update an existing vendor."""
        with self._lock:
            existing = self._vendors.get(vendor_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = Vendor(**data)
            self._vendors[vendor_id] = updated
        return updated

    def delete_vendor(self, vendor_id: str) -> bool:
        """Delete a vendor. Returns True if deleted."""
        with self._lock:
            if vendor_id in self._vendors:
                del self._vendors[vendor_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Quality Agreements
    # ------------------------------------------------------------------

    def list_agreements(
        self,
        *,
        vendor_id: str | None = None,
        trial_id: str | None = None,
        status: AgreementStatus | None = None,
    ) -> list[QualityAgreement]:
        """List quality agreements with optional filters."""
        with self._lock:
            result = list(self._agreements.values())

        if vendor_id is not None:
            result = [a for a in result if a.vendor_id == vendor_id]
        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if status is not None:
            result = [a for a in result if a.status == status]

        return sorted(result, key=lambda a: a.id)

    def get_agreement(self, agreement_id: str) -> QualityAgreement | None:
        """Get a single quality agreement by ID."""
        with self._lock:
            return self._agreements.get(agreement_id)

    def create_agreement(self, payload: QualityAgreementCreate) -> QualityAgreement:
        """Create a new quality agreement."""
        now = datetime.now(timezone.utc)

        # Validate vendor exists
        with self._lock:
            if payload.vendor_id not in self._vendors:
                raise ValueError(f"Vendor '{payload.vendor_id}' not found")

        agreement_id = f"QA-{uuid4().hex[:8].upper()}"
        agreement = QualityAgreement(
            id=agreement_id,
            vendor_id=payload.vendor_id,
            trial_id=payload.trial_id,
            agreement_number=payload.agreement_number,
            title=payload.title,
            status=AgreementStatus.DRAFT,
            effective_date=payload.effective_date,
            expiry_date=payload.expiry_date,
            signed_by_sponsor=None,
            signed_by_vendor=None,
            key_terms=payload.key_terms,
            created_at=now,
        )
        with self._lock:
            self._agreements[agreement_id] = agreement
        logger.info("Created quality agreement %s: %s", agreement_id, payload.title)
        return agreement

    def update_agreement(
        self, agreement_id: str, payload: QualityAgreementUpdate
    ) -> QualityAgreement | None:
        """Update a quality agreement."""
        with self._lock:
            existing = self._agreements.get(agreement_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = QualityAgreement(**data)
            self._agreements[agreement_id] = updated
        return updated

    def delete_agreement(self, agreement_id: str) -> bool:
        """Delete a quality agreement. Returns True if deleted."""
        with self._lock:
            if agreement_id in self._agreements:
                del self._agreements[agreement_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Vendor Assessments
    # ------------------------------------------------------------------

    def list_assessments(
        self,
        *,
        vendor_id: str | None = None,
        trial_id: str | None = None,
        rating: PerformanceRating | None = None,
    ) -> list[VendorAssessment]:
        """List vendor assessments with optional filters."""
        with self._lock:
            result = list(self._assessments.values())

        if vendor_id is not None:
            result = [a for a in result if a.vendor_id == vendor_id]
        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if rating is not None:
            result = [a for a in result if a.rating == rating]

        return sorted(result, key=lambda a: a.assessment_date, reverse=True)

    def get_assessment(self, assessment_id: str) -> VendorAssessment | None:
        """Get a single vendor assessment by ID."""
        with self._lock:
            return self._assessments.get(assessment_id)

    def create_assessment(self, payload: VendorAssessmentCreate) -> VendorAssessment:
        """Create a new vendor assessment."""
        now = datetime.now(timezone.utc)

        # Validate vendor exists
        with self._lock:
            if payload.vendor_id not in self._vendors:
                raise ValueError(f"Vendor '{payload.vendor_id}' not found")

        assessment_id = f"VA-{uuid4().hex[:8].upper()}"
        overall_score = round(
            (payload.quality_score + payload.timeliness_score
             + payload.communication_score + payload.compliance_score) / 4.0,
            1,
        )
        assessment = VendorAssessment(
            id=assessment_id,
            vendor_id=payload.vendor_id,
            trial_id=payload.trial_id,
            assessment_date=now,
            assessor=payload.assessor,
            quality_score=payload.quality_score,
            timeliness_score=payload.timeliness_score,
            communication_score=payload.communication_score,
            compliance_score=payload.compliance_score,
            overall_score=overall_score,
            rating=payload.rating,
            strengths=payload.strengths,
            improvements_needed=payload.improvements_needed,
            notes=payload.notes,
        )
        with self._lock:
            self._assessments[assessment_id] = assessment
        logger.info(
            "Created vendor assessment %s: vendor=%s overall=%.1f",
            assessment_id, payload.vendor_id, overall_score,
        )
        return assessment

    def delete_assessment(self, assessment_id: str) -> bool:
        """Delete a vendor assessment. Returns True if deleted."""
        with self._lock:
            if assessment_id in self._assessments:
                del self._assessments[assessment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Risk Assessments
    # ------------------------------------------------------------------

    def list_risk_assessments(
        self,
        *,
        vendor_id: str | None = None,
        risk_level: RiskLevel | None = None,
    ) -> list[VendorRiskAssessment]:
        """List vendor risk assessments with optional filters."""
        with self._lock:
            result = list(self._risk_assessments.values())

        if vendor_id is not None:
            result = [r for r in result if r.vendor_id == vendor_id]
        if risk_level is not None:
            result = [r for r in result if r.risk_level == risk_level]

        return sorted(result, key=lambda r: r.assessed_date, reverse=True)

    def get_risk_assessment(self, risk_assessment_id: str) -> VendorRiskAssessment | None:
        """Get a single risk assessment by ID."""
        with self._lock:
            return self._risk_assessments.get(risk_assessment_id)

    def create_risk_assessment(
        self, payload: VendorRiskAssessmentCreate
    ) -> VendorRiskAssessment:
        """Create a new vendor risk assessment."""
        now = datetime.now(timezone.utc)

        # Validate vendor exists
        with self._lock:
            if payload.vendor_id not in self._vendors:
                raise ValueError(f"Vendor '{payload.vendor_id}' not found")

        risk_id = f"VRA-{uuid4().hex[:8].upper()}"
        risk_assessment = VendorRiskAssessment(
            id=risk_id,
            vendor_id=payload.vendor_id,
            assessed_date=now,
            assessed_by=payload.assessed_by,
            risk_level=payload.risk_level,
            risk_factors=payload.risk_factors,
            mitigation_plan=payload.mitigation_plan,
            next_review_date=payload.next_review_date,
        )
        with self._lock:
            self._risk_assessments[risk_id] = risk_assessment
        logger.info(
            "Created risk assessment %s: vendor=%s risk=%s",
            risk_id, payload.vendor_id, payload.risk_level.value,
        )
        return risk_assessment

    def delete_risk_assessment(self, risk_assessment_id: str) -> bool:
        """Delete a risk assessment. Returns True if deleted."""
        with self._lock:
            if risk_assessment_id in self._risk_assessments:
                del self._risk_assessments[risk_assessment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self) -> VendorQualificationMetrics:
        """Compute aggregated vendor qualification metrics."""
        with self._lock:
            vendors = list(self._vendors.values())
            agreements = list(self._agreements.values())
            assessments = list(self._assessments.values())
            risk_assessments = list(self._risk_assessments.values())

        # Vendors by category
        vendors_by_category: dict[str, int] = {}
        for v in vendors:
            key = v.category.value
            vendors_by_category[key] = vendors_by_category.get(key, 0) + 1

        # Vendors by status
        vendors_by_status: dict[str, int] = {}
        for v in vendors:
            key = v.qualification_status.value
            vendors_by_status[key] = vendors_by_status.get(key, 0) + 1

        # Vendors by risk
        vendors_by_risk: dict[str, int] = {}
        for v in vendors:
            key = v.risk_level.value
            vendors_by_risk[key] = vendors_by_risk.get(key, 0) + 1

        # Agreements by status
        agreements_by_status: dict[str, int] = {}
        for a in agreements:
            key = a.status.value
            agreements_by_status[key] = agreements_by_status.get(key, 0) + 1

        # Average scores
        avg_quality = 0.0
        avg_overall = 0.0
        if assessments:
            avg_quality = round(
                sum(a.quality_score for a in assessments) / len(assessments), 1
            )
            avg_overall = round(
                sum(a.overall_score for a in assessments) / len(assessments), 1
            )

        # High risk vendors (risk level HIGH or CRITICAL)
        high_risk_vendor_ids = {
            r.vendor_id for r in risk_assessments
            if r.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        }
        high_risk_count = len(high_risk_vendor_ids)

        # Requalification due
        now = datetime.now(timezone.utc)
        requalification_due_count = sum(
            1 for v in vendors
            if v.qualification_status == QualificationStatus.REQUALIFICATION_DUE
            or (
                v.requalification_due_date is not None
                and v.requalification_due_date <= now
            )
        )

        return VendorQualificationMetrics(
            total_vendors=len(vendors),
            vendors_by_category=vendors_by_category,
            vendors_by_status=vendors_by_status,
            vendors_by_risk=vendors_by_risk,
            total_agreements=len(agreements),
            agreements_by_status=agreements_by_status,
            total_assessments=len(assessments),
            avg_quality_score=avg_quality,
            avg_overall_score=avg_overall,
            total_risk_assessments=len(risk_assessments),
            high_risk_vendors=high_risk_count,
            requalification_due=requalification_due_count,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: VendorQualificationService | None = None
_instance_lock = threading.Lock()


def get_vendor_qualification_service() -> VendorQualificationService:
    """Return the singleton VendorQualificationService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = VendorQualificationService()
    return _instance


def reset_vendor_qualification_service() -> VendorQualificationService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = VendorQualificationService()
    return _instance
