"""Site Initiation & Activation Service (CLINICAL-17).

Manages the full lifecycle of clinical trial site initiation: site selection,
qualification visits, regulatory document collection, site readiness assessment,
activation milestones, and essential documents tracking from the CRO perspective.

Usage:
    from app.services.site_initiation_service import (
        get_site_initiation_service,
    )

    svc = get_site_initiation_service()
    sites = svc.list_sites()
    metrics = svc.get_activation_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.site_initiation import (
    DocumentStatus,
    DocumentType,
    MilestoneStatus,
    MilestoneType,
    MilestoneUpdate,
    QualificationRecommendation,
    QualificationVisit,
    QualificationVisitCreate,
    ReadinessAssessment,
    ReadinessCategory,
    ReadinessUpdate,
    RegulatoryDocument,
    RegulatoryDocumentCreate,
    RegulatoryDocumentUpdate,
    SiteActivationMetrics,
    SiteInitiation,
    SiteInitiationCreate,
    SiteInitiationUpdate,
    SiteMilestone,
    SiteStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

# Valid lifecycle transitions
_VALID_TRANSITIONS: dict[SiteStatus, list[SiteStatus]] = {
    SiteStatus.IDENTIFIED: [SiteStatus.SELECTED],
    SiteStatus.SELECTED: [SiteStatus.QUALIFICATION_VISIT],
    SiteStatus.QUALIFICATION_VISIT: [SiteStatus.REGULATORY_SUBMITTED, SiteStatus.IDENTIFIED],
    SiteStatus.REGULATORY_SUBMITTED: [SiteStatus.ACTIVATED],
    SiteStatus.ACTIVATED: [SiteStatus.ENROLLING, SiteStatus.CLOSED],
    SiteStatus.ENROLLING: [SiteStatus.CLOSED],
    SiteStatus.CLOSED: [],
}


class SiteInitiationService:
    """In-memory Site Initiation & Activation engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._sites: dict[str, SiteInitiation] = {}
        self._qualification_visits: dict[str, QualificationVisit] = {}
        self._regulatory_documents: dict[str, RegulatoryDocument] = {}
        self._milestones: dict[str, SiteMilestone] = {}
        self._readiness_assessments: dict[str, ReadinessAssessment] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic site initiation data across clinical trials."""
        now = datetime.now(timezone.utc)

        # --- 10 Sites across 3 trials ---

        # EYLEA Trial - 4 sites in various stages
        site1 = SiteInitiation(
            id="SINIT-001",
            trial_id=EYLEA_TRIAL,
            site_number="1001",
            site_name="Bascom Palmer Eye Institute - Site 1001",
            principal_investigator="Dr. Philip Rosenfeld",
            institution="Bascom Palmer Eye Institute",
            country="US",
            status=SiteStatus.ENROLLING,
            target_enrollment=35,
            current_enrollment=22,
            qualification_visits=[],
            regulatory_documents=[],
            milestones=[],
            activation_date=now - timedelta(days=120),
            created_at=now - timedelta(days=240),
        )

        site2 = SiteInitiation(
            id="SINIT-002",
            trial_id=EYLEA_TRIAL,
            site_number="1002",
            site_name="Wills Eye Hospital - Site 1002",
            principal_investigator="Dr. Carl Regillo",
            institution="Wills Eye Hospital",
            country="US",
            status=SiteStatus.ACTIVATED,
            target_enrollment=30,
            current_enrollment=8,
            qualification_visits=[],
            regulatory_documents=[],
            milestones=[],
            activation_date=now - timedelta(days=45),
            created_at=now - timedelta(days=200),
        )

        site3 = SiteInitiation(
            id="SINIT-003",
            trial_id=EYLEA_TRIAL,
            site_number="1003",
            site_name="Retina Associates of Cleveland - Site 1003",
            principal_investigator="Dr. Lawrence Yannuzzi",
            institution="Cleveland Clinic Cole Eye Institute",
            country="US",
            status=SiteStatus.REGULATORY_SUBMITTED,
            target_enrollment=25,
            current_enrollment=0,
            qualification_visits=[],
            regulatory_documents=[],
            milestones=[],
            activation_date=None,
            created_at=now - timedelta(days=150),
        )

        site4 = SiteInitiation(
            id="SINIT-004",
            trial_id=EYLEA_TRIAL,
            site_number="1004",
            site_name="Duke Eye Center - Site 1004",
            principal_investigator="Dr. Sharon Fekrat",
            institution="Duke University Medical Center",
            country="US",
            status=SiteStatus.QUALIFICATION_VISIT,
            target_enrollment=20,
            current_enrollment=0,
            qualification_visits=[],
            regulatory_documents=[],
            milestones=[],
            activation_date=None,
            created_at=now - timedelta(days=90),
        )

        # DUPIXENT Trial - 3 sites
        site5 = SiteInitiation(
            id="SINIT-005",
            trial_id=DUPIXENT_TRIAL,
            site_number="2001",
            site_name="National Jewish Health - Site 2001",
            principal_investigator="Dr. Michael Wechsler",
            institution="National Jewish Health",
            country="US",
            status=SiteStatus.ENROLLING,
            target_enrollment=40,
            current_enrollment=31,
            qualification_visits=[],
            regulatory_documents=[],
            milestones=[],
            activation_date=now - timedelta(days=180),
            created_at=now - timedelta(days=300),
        )

        site6 = SiteInitiation(
            id="SINIT-006",
            trial_id=DUPIXENT_TRIAL,
            site_number="2002",
            site_name="Northwestern Dermatology - Site 2002",
            principal_investigator="Dr. Jonathan Silverberg",
            institution="Northwestern University Feinberg School of Medicine",
            country="US",
            status=SiteStatus.ACTIVATED,
            target_enrollment=30,
            current_enrollment=5,
            qualification_visits=[],
            regulatory_documents=[],
            milestones=[],
            activation_date=now - timedelta(days=30),
            created_at=now - timedelta(days=160),
        )

        site7 = SiteInitiation(
            id="SINIT-007",
            trial_id=DUPIXENT_TRIAL,
            site_number="2003",
            site_name="Icahn School of Medicine - Site 2003",
            principal_investigator="Dr. Emma Guttman-Yassky",
            institution="Mount Sinai Hospital",
            country="US",
            status=SiteStatus.SELECTED,
            target_enrollment=25,
            current_enrollment=0,
            qualification_visits=[],
            regulatory_documents=[],
            milestones=[],
            activation_date=None,
            created_at=now - timedelta(days=60),
        )

        # LIBTAYO Trial - 3 sites
        site8 = SiteInitiation(
            id="SINIT-008",
            trial_id=LIBTAYO_TRIAL,
            site_number="3001",
            site_name="Memorial Sloan Kettering - Site 3001",
            principal_investigator="Dr. Matthew Hellmann",
            institution="Memorial Sloan Kettering Cancer Center",
            country="US",
            status=SiteStatus.ENROLLING,
            target_enrollment=45,
            current_enrollment=38,
            qualification_visits=[],
            regulatory_documents=[],
            milestones=[],
            activation_date=now - timedelta(days=210),
            created_at=now - timedelta(days=350),
        )

        site9 = SiteInitiation(
            id="SINIT-009",
            trial_id=LIBTAYO_TRIAL,
            site_number="3002",
            site_name="MD Anderson Cancer Center - Site 3002",
            principal_investigator="Dr. Aung Naing",
            institution="University of Texas MD Anderson Cancer Center",
            country="US",
            status=SiteStatus.REGULATORY_SUBMITTED,
            target_enrollment=35,
            current_enrollment=0,
            qualification_visits=[],
            regulatory_documents=[],
            milestones=[],
            activation_date=None,
            created_at=now - timedelta(days=100),
        )

        site10 = SiteInitiation(
            id="SINIT-010",
            trial_id=LIBTAYO_TRIAL,
            site_number="3003",
            site_name="Dana-Farber Cancer Institute - Site 3003",
            principal_investigator="Dr. Osama Rahma",
            institution="Dana-Farber Cancer Institute",
            country="US",
            status=SiteStatus.IDENTIFIED,
            target_enrollment=30,
            current_enrollment=0,
            qualification_visits=[],
            regulatory_documents=[],
            milestones=[],
            activation_date=None,
            created_at=now - timedelta(days=20),
        )

        for site in [site1, site2, site3, site4, site5, site6, site7, site8, site9, site10]:
            self._sites[site.id] = site

        # --- Qualification Visits ---
        qv_data = [
            # SINIT-001: completed qualification
            {
                "id": "QV-001", "site_id": "SINIT-001",
                "visit_date": now - timedelta(days=220),
                "attendees": ["Dr. Philip Rosenfeld", "Sarah Chen (CRA)", "Mark Wilson (Medical Monitor)"],
                "findings": "Excellent retinal imaging facilities with OCT and fluorescein angiography. Experienced staff with 50+ clinical trial participations. Adequate patient volume estimated at 15-20 eligible patients per month. Storage meets ALCOA+ requirements.",
                "recommendation": QualificationRecommendation.APPROVED,
                "action_items": ["Update delegation log", "Complete GCP refresher training for 2 new coordinators"],
                "created_at": now - timedelta(days=220),
            },
            # SINIT-002: approved with conditions
            {
                "id": "QV-002", "site_id": "SINIT-002",
                "visit_date": now - timedelta(days=180),
                "attendees": ["Dr. Carl Regillo", "Sarah Chen (CRA)", "James Park (QA)"],
                "findings": "Strong ophthalmology program. PI has extensive anti-VEGF experience. Pharmacy needs temperature monitoring upgrade for investigational product storage. Research coordinator team well organized.",
                "recommendation": QualificationRecommendation.APPROVED_WITH_CONDITIONS,
                "action_items": ["Install continuous temperature monitoring system in pharmacy", "Add backup coordinator to delegation log"],
                "created_at": now - timedelta(days=180),
            },
            # SINIT-004: recent qualification visit
            {
                "id": "QV-003", "site_id": "SINIT-004",
                "visit_date": now - timedelta(days=75),
                "attendees": ["Dr. Sharon Fekrat", "Lisa Martinez (CRA)", "Mark Wilson (Medical Monitor)"],
                "findings": "Duke Eye Center has world-class facilities. PI has significant publications in retinal diseases. Need to expand coordinator capacity. IT infrastructure supports EDC requirements. Patient recruitment pool estimated at 8-12 per month.",
                "recommendation": QualificationRecommendation.APPROVED_WITH_CONDITIONS,
                "action_items": ["Hire additional research coordinator", "Validate EDC system access", "Schedule investigator meeting"],
                "created_at": now - timedelta(days=75),
            },
            # SINIT-005: completed qualification
            {
                "id": "QV-004", "site_id": "SINIT-005",
                "visit_date": now - timedelta(days=280),
                "attendees": ["Dr. Michael Wechsler", "Robert Kim (CRA)", "Alice Thompson (Study Manager)"],
                "findings": "Leading institution for respiratory and immunology research. PI is KOL in severe asthma. Dedicated clinical trials unit with 12 beds. Pulmonary function testing lab is NIOSH-certified. Estimated recruitment of 20+ patients per month.",
                "recommendation": QualificationRecommendation.APPROVED,
                "action_items": ["Finalize delegation log", "Complete protocol training"],
                "created_at": now - timedelta(days=280),
            },
            # SINIT-006: approved recently
            {
                "id": "QV-005", "site_id": "SINIT-006",
                "visit_date": now - timedelta(days=140),
                "attendees": ["Dr. Jonathan Silverberg", "Robert Kim (CRA)", "Diana Patel (QA)"],
                "findings": "Strong dermatology department with established clinical research infrastructure. Good patient flow through dermatology clinic. SCORAD and EASI assessment capabilities confirmed. Minor issue with source document template needing updates.",
                "recommendation": QualificationRecommendation.APPROVED_WITH_CONDITIONS,
                "action_items": ["Update source document templates", "Install secure document storage for regulatory files"],
                "created_at": now - timedelta(days=140),
            },
            # SINIT-008: completed qualification
            {
                "id": "QV-006", "site_id": "SINIT-008",
                "visit_date": now - timedelta(days=330),
                "attendees": ["Dr. Matthew Hellmann", "Jennifer Adams (CRA)", "Thomas Lee (Medical Monitor)"],
                "findings": "Tier-1 cancer center with unmatched immuno-oncology program. PI leads checkpoint inhibitor research globally. Dedicated phase I unit. Biomarker lab on-site with CLIA certification. Patient volume exceeds requirement.",
                "recommendation": QualificationRecommendation.APPROVED,
                "action_items": ["Complete biomarker lab qualification", "Validate tumor assessment imaging protocol"],
                "created_at": now - timedelta(days=330),
            },
            # SINIT-009: approved with conditions
            {
                "id": "QV-007", "site_id": "SINIT-009",
                "visit_date": now - timedelta(days=85),
                "attendees": ["Dr. Aung Naing", "Jennifer Adams (CRA)", "Karen O'Brien (Study Manager)"],
                "findings": "MD Anderson has premier oncology infrastructure. Phase I clinical trials program is among the largest in the US. Minor concerns about coordinator availability due to competing trials. RECIST-trained radiologists available.",
                "recommendation": QualificationRecommendation.APPROVED_WITH_CONDITIONS,
                "action_items": ["Assign dedicated coordinator from trial operations pool", "Confirm radiology read schedule"],
                "created_at": now - timedelta(days=85),
            },
        ]

        for qv in qv_data:
            visit = QualificationVisit(**qv)
            self._qualification_visits[visit.id] = visit

        # Attach qualification visits to sites
        for site_id, site in self._sites.items():
            visits = [v for v in self._qualification_visits.values() if v.site_id == site_id]
            if visits:
                data = site.model_dump()
                data["qualification_visits"] = visits
                self._sites[site_id] = SiteInitiation(**data)

        # --- Regulatory Documents ---
        doc_data = [
            # SINIT-001: fully approved (enrolling site)
            {"id": "DOC-001", "site_id": "SINIT-001", "doc_type": DocumentType.IRB_APPROVAL, "status": DocumentStatus.APPROVED, "submitted_date": now - timedelta(days=200), "approved_date": now - timedelta(days=170), "expiry_date": now + timedelta(days=195), "notes": None, "version": "1.0"},
            {"id": "DOC-002", "site_id": "SINIT-001", "doc_type": DocumentType.INFORMED_CONSENT, "status": DocumentStatus.APPROVED, "submitted_date": now - timedelta(days=200), "approved_date": now - timedelta(days=168), "expiry_date": None, "notes": "Version 4.0 with eligibility expansion", "version": "4.0"},
            {"id": "DOC-003", "site_id": "SINIT-001", "doc_type": DocumentType.FDA_1572, "status": DocumentStatus.APPROVED, "submitted_date": now - timedelta(days=210), "approved_date": now - timedelta(days=205), "expiry_date": None, "notes": None, "version": "1.0"},
            {"id": "DOC-004", "site_id": "SINIT-001", "doc_type": DocumentType.SITE_CONTRACT, "status": DocumentStatus.APPROVED, "submitted_date": now - timedelta(days=190), "approved_date": now - timedelta(days=160), "expiry_date": None, "notes": "Executed contract", "version": "2.0"},
            {"id": "DOC-005", "site_id": "SINIT-001", "doc_type": DocumentType.CV_PRINCIPAL_INVESTIGATOR, "status": DocumentStatus.APPROVED, "submitted_date": now - timedelta(days=215), "approved_date": now - timedelta(days=212), "expiry_date": now + timedelta(days=150), "notes": None, "version": "1.0"},
            # SINIT-003: regulatory submitted (some pending)
            {"id": "DOC-006", "site_id": "SINIT-003", "doc_type": DocumentType.IRB_APPROVAL, "status": DocumentStatus.UNDER_REVIEW, "submitted_date": now - timedelta(days=30), "approved_date": None, "expiry_date": None, "notes": "Submitted to Cleveland Clinic IRB", "version": "1.0"},
            {"id": "DOC-007", "site_id": "SINIT-003", "doc_type": DocumentType.INFORMED_CONSENT, "status": DocumentStatus.SUBMITTED, "submitted_date": now - timedelta(days=28), "approved_date": None, "expiry_date": None, "notes": None, "version": "5.0"},
            {"id": "DOC-008", "site_id": "SINIT-003", "doc_type": DocumentType.FDA_1572, "status": DocumentStatus.APPROVED, "submitted_date": now - timedelta(days=50), "approved_date": now - timedelta(days=45), "expiry_date": None, "notes": None, "version": "1.0"},
            {"id": "DOC-009", "site_id": "SINIT-003", "doc_type": DocumentType.BUDGET_AGREEMENT, "status": DocumentStatus.UNDER_REVIEW, "submitted_date": now - timedelta(days=25), "approved_date": None, "expiry_date": None, "notes": "Awaiting finance review", "version": "1.0"},
            # SINIT-005: fully approved (enrolling site)
            {"id": "DOC-010", "site_id": "SINIT-005", "doc_type": DocumentType.IRB_APPROVAL, "status": DocumentStatus.APPROVED, "submitted_date": now - timedelta(days=260), "approved_date": now - timedelta(days=230), "expiry_date": now + timedelta(days=135), "notes": None, "version": "1.0"},
            {"id": "DOC-011", "site_id": "SINIT-005", "doc_type": DocumentType.INFORMED_CONSENT, "status": DocumentStatus.APPROVED, "submitted_date": now - timedelta(days=260), "approved_date": now - timedelta(days=228), "expiry_date": None, "notes": None, "version": "3.0"},
            {"id": "DOC-012", "site_id": "SINIT-005", "doc_type": DocumentType.DELEGATION_LOG, "status": DocumentStatus.APPROVED, "submitted_date": now - timedelta(days=250), "approved_date": now - timedelta(days=248), "expiry_date": None, "notes": "8 staff members delegated", "version": "3.0"},
            # SINIT-008: fully approved (enrolling site)
            {"id": "DOC-013", "site_id": "SINIT-008", "doc_type": DocumentType.IRB_APPROVAL, "status": DocumentStatus.APPROVED, "submitted_date": now - timedelta(days=310), "approved_date": now - timedelta(days=280), "expiry_date": now + timedelta(days=85), "notes": None, "version": "1.0"},
            {"id": "DOC-014", "site_id": "SINIT-008", "doc_type": DocumentType.INFORMED_CONSENT, "status": DocumentStatus.APPROVED, "submitted_date": now - timedelta(days=310), "approved_date": now - timedelta(days=278), "expiry_date": None, "notes": None, "version": "2.0"},
            {"id": "DOC-015", "site_id": "SINIT-008", "doc_type": DocumentType.LAB_CERTIFICATION, "status": DocumentStatus.APPROVED, "submitted_date": now - timedelta(days=320), "approved_date": now - timedelta(days=315), "expiry_date": now + timedelta(days=50), "notes": "CLIA certified biomarker lab", "version": "1.0"},
            # SINIT-009: regulatory submitted
            {"id": "DOC-016", "site_id": "SINIT-009", "doc_type": DocumentType.IRB_APPROVAL, "status": DocumentStatus.SUBMITTED, "submitted_date": now - timedelta(days=40), "approved_date": None, "expiry_date": None, "notes": "Submitted to MD Anderson IRB", "version": "1.0"},
            {"id": "DOC-017", "site_id": "SINIT-009", "doc_type": DocumentType.FINANCIAL_DISCLOSURE, "status": DocumentStatus.APPROVED, "submitted_date": now - timedelta(days=60), "approved_date": now - timedelta(days=55), "expiry_date": None, "notes": None, "version": "1.0"},
            # SINIT-002: activated site
            {"id": "DOC-018", "site_id": "SINIT-002", "doc_type": DocumentType.IRB_APPROVAL, "status": DocumentStatus.APPROVED, "submitted_date": now - timedelta(days=100), "approved_date": now - timedelta(days=70), "expiry_date": now + timedelta(days=295), "notes": None, "version": "1.0"},
            {"id": "DOC-019", "site_id": "SINIT-002", "doc_type": DocumentType.INFORMED_CONSENT, "status": DocumentStatus.APPROVED, "submitted_date": now - timedelta(days=100), "approved_date": now - timedelta(days=68), "expiry_date": None, "notes": None, "version": "5.0"},
            {"id": "DOC-020", "site_id": "SINIT-002", "doc_type": DocumentType.TRAINING_CERTIFICATE, "status": DocumentStatus.APPROVED, "submitted_date": now - timedelta(days=55), "approved_date": now - timedelta(days=53), "expiry_date": now + timedelta(days=310), "notes": "GCP and protocol-specific training", "version": "1.0"},
            # SINIT-006: recently activated
            {"id": "DOC-021", "site_id": "SINIT-006", "doc_type": DocumentType.IRB_APPROVAL, "status": DocumentStatus.APPROVED, "submitted_date": now - timedelta(days=80), "approved_date": now - timedelta(days=50), "expiry_date": now + timedelta(days=315), "notes": None, "version": "1.0"},
            {"id": "DOC-022", "site_id": "SINIT-006", "doc_type": DocumentType.SITE_CONTRACT, "status": DocumentStatus.APPROVED, "submitted_date": now - timedelta(days=90), "approved_date": now - timedelta(days=55), "expiry_date": None, "notes": None, "version": "1.0"},
            # SINIT-004: in qualification (minimal docs)
            {"id": "DOC-023", "site_id": "SINIT-004", "doc_type": DocumentType.CV_PRINCIPAL_INVESTIGATOR, "status": DocumentStatus.SUBMITTED, "submitted_date": now - timedelta(days=70), "approved_date": None, "expiry_date": None, "notes": None, "version": "1.0"},
            {"id": "DOC-024", "site_id": "SINIT-004", "doc_type": DocumentType.FINANCIAL_DISCLOSURE, "status": DocumentStatus.NOT_SUBMITTED, "submitted_date": None, "approved_date": None, "expiry_date": None, "notes": "Awaiting PI signature", "version": None},
        ]

        for doc in doc_data:
            rd = RegulatoryDocument(**doc)
            self._regulatory_documents[rd.id] = rd

        # Attach regulatory documents to sites
        for site_id, site in self._sites.items():
            docs = [d for d in self._regulatory_documents.values() if d.site_id == site_id]
            if docs:
                data = site.model_dump()
                data["regulatory_documents"] = docs
                self._sites[site_id] = SiteInitiation(**data)

        # --- Milestones ---
        milestone_data = [
            # SINIT-001: fully activated and enrolling
            {"id": "MS-001", "site_id": "SINIT-001", "milestone_type": MilestoneType.SITE_IDENTIFIED, "target_date": now - timedelta(days=245), "actual_date": now - timedelta(days=240), "status": MilestoneStatus.COMPLETED, "notes": None},
            {"id": "MS-002", "site_id": "SINIT-001", "milestone_type": MilestoneType.QUALIFICATION_VISIT_COMPLETE, "target_date": now - timedelta(days=215), "actual_date": now - timedelta(days=220), "status": MilestoneStatus.COMPLETED, "notes": "Completed ahead of schedule"},
            {"id": "MS-003", "site_id": "SINIT-001", "milestone_type": MilestoneType.IRB_APPROVAL, "target_date": now - timedelta(days=175), "actual_date": now - timedelta(days=170), "status": MilestoneStatus.COMPLETED, "notes": None},
            {"id": "MS-004", "site_id": "SINIT-001", "milestone_type": MilestoneType.SITE_ACTIVATED, "target_date": now - timedelta(days=130), "actual_date": now - timedelta(days=120), "status": MilestoneStatus.COMPLETED, "notes": None},
            {"id": "MS-005", "site_id": "SINIT-001", "milestone_type": MilestoneType.FIRST_PATIENT_SCREENED, "target_date": now - timedelta(days=110), "actual_date": now - timedelta(days=105), "status": MilestoneStatus.COMPLETED, "notes": "First patient screened within target window"},
            # SINIT-003: regulatory stage
            {"id": "MS-006", "site_id": "SINIT-003", "milestone_type": MilestoneType.SITE_IDENTIFIED, "target_date": now - timedelta(days=155), "actual_date": now - timedelta(days=150), "status": MilestoneStatus.COMPLETED, "notes": None},
            {"id": "MS-007", "site_id": "SINIT-003", "milestone_type": MilestoneType.QUALIFICATION_VISIT_COMPLETE, "target_date": now - timedelta(days=120), "actual_date": now - timedelta(days=115), "status": MilestoneStatus.COMPLETED, "notes": None},
            {"id": "MS-008", "site_id": "SINIT-003", "milestone_type": MilestoneType.IRB_SUBMISSION, "target_date": now - timedelta(days=35), "actual_date": now - timedelta(days=30), "status": MilestoneStatus.COMPLETED, "notes": None},
            {"id": "MS-009", "site_id": "SINIT-003", "milestone_type": MilestoneType.IRB_APPROVAL, "target_date": now - timedelta(days=5), "actual_date": None, "status": MilestoneStatus.OVERDUE, "notes": "IRB review taking longer than expected"},
            {"id": "MS-010", "site_id": "SINIT-003", "milestone_type": MilestoneType.SITE_ACTIVATED, "target_date": now + timedelta(days=20), "actual_date": None, "status": MilestoneStatus.PENDING, "notes": None},
            # SINIT-005: fully activated (dupixent)
            {"id": "MS-011", "site_id": "SINIT-005", "milestone_type": MilestoneType.SITE_IDENTIFIED, "target_date": now - timedelta(days=305), "actual_date": now - timedelta(days=300), "status": MilestoneStatus.COMPLETED, "notes": None},
            {"id": "MS-012", "site_id": "SINIT-005", "milestone_type": MilestoneType.SITE_ACTIVATED, "target_date": now - timedelta(days=185), "actual_date": now - timedelta(days=180), "status": MilestoneStatus.COMPLETED, "notes": None},
            {"id": "MS-013", "site_id": "SINIT-005", "milestone_type": MilestoneType.FIRST_PATIENT_SCREENED, "target_date": now - timedelta(days=170), "actual_date": now - timedelta(days=165), "status": MilestoneStatus.COMPLETED, "notes": None},
            # SINIT-008: fully activated (libtayo)
            {"id": "MS-014", "site_id": "SINIT-008", "milestone_type": MilestoneType.SITE_IDENTIFIED, "target_date": now - timedelta(days=355), "actual_date": now - timedelta(days=350), "status": MilestoneStatus.COMPLETED, "notes": None},
            {"id": "MS-015", "site_id": "SINIT-008", "milestone_type": MilestoneType.SITE_ACTIVATED, "target_date": now - timedelta(days=215), "actual_date": now - timedelta(days=210), "status": MilestoneStatus.COMPLETED, "notes": None},
            {"id": "MS-016", "site_id": "SINIT-008", "milestone_type": MilestoneType.FIRST_PATIENT_SCREENED, "target_date": now - timedelta(days=200), "actual_date": now - timedelta(days=195), "status": MilestoneStatus.COMPLETED, "notes": None},
            # SINIT-009: regulatory submitted
            {"id": "MS-017", "site_id": "SINIT-009", "milestone_type": MilestoneType.SITE_IDENTIFIED, "target_date": now - timedelta(days=105), "actual_date": now - timedelta(days=100), "status": MilestoneStatus.COMPLETED, "notes": None},
            {"id": "MS-018", "site_id": "SINIT-009", "milestone_type": MilestoneType.QUALIFICATION_VISIT_COMPLETE, "target_date": now - timedelta(days=80), "actual_date": now - timedelta(days=85), "status": MilestoneStatus.COMPLETED, "notes": "Completed ahead of schedule"},
            {"id": "MS-019", "site_id": "SINIT-009", "milestone_type": MilestoneType.IRB_SUBMISSION, "target_date": now - timedelta(days=45), "actual_date": now - timedelta(days=40), "status": MilestoneStatus.COMPLETED, "notes": None},
            {"id": "MS-020", "site_id": "SINIT-009", "milestone_type": MilestoneType.IRB_APPROVAL, "target_date": now + timedelta(days=5), "actual_date": None, "status": MilestoneStatus.IN_PROGRESS, "notes": "Under review"},
            # SINIT-010: just identified
            {"id": "MS-021", "site_id": "SINIT-010", "milestone_type": MilestoneType.SITE_IDENTIFIED, "target_date": now - timedelta(days=25), "actual_date": now - timedelta(days=20), "status": MilestoneStatus.COMPLETED, "notes": None},
            {"id": "MS-022", "site_id": "SINIT-010", "milestone_type": MilestoneType.CONFIDENTIALITY_AGREEMENT, "target_date": now - timedelta(days=10), "actual_date": None, "status": MilestoneStatus.OVERDUE, "notes": "Awaiting legal review"},
            {"id": "MS-023", "site_id": "SINIT-010", "milestone_type": MilestoneType.FEASIBILITY_COMPLETE, "target_date": now + timedelta(days=15), "actual_date": None, "status": MilestoneStatus.PENDING, "notes": None},
            {"id": "MS-024", "site_id": "SINIT-010", "milestone_type": MilestoneType.SITE_SELECTED, "target_date": now + timedelta(days=30), "actual_date": None, "status": MilestoneStatus.PENDING, "notes": None},
        ]

        for ms in milestone_data:
            milestone = SiteMilestone(**ms)
            self._milestones[milestone.id] = milestone

        # Attach milestones to sites
        for site_id, site in self._sites.items():
            ms_list = [m for m in self._milestones.values() if m.site_id == site_id]
            if ms_list:
                data = site.model_dump()
                data["milestones"] = ms_list
                self._sites[site_id] = SiteInitiation(**data)

        # --- Readiness Assessments ---
        readiness_data = [
            {
                "site_id": "SINIT-001",
                "category_scores": {
                    ReadinessCategory.REGULATORY.value: 100.0,
                    ReadinessCategory.STAFFING.value: 95.0,
                    ReadinessCategory.FACILITIES.value: 100.0,
                    ReadinessCategory.EQUIPMENT.value: 100.0,
                    ReadinessCategory.PHARMACY.value: 100.0,
                    ReadinessCategory.LABORATORY.value: 95.0,
                    ReadinessCategory.TRAINING.value: 100.0,
                    ReadinessCategory.IT_SYSTEMS.value: 90.0,
                },
                "overall_score": 97.5,
                "blockers": [],
                "assessed_date": now - timedelta(days=125),
                "assessed_by": "Sarah Chen (CRA)",
            },
            {
                "site_id": "SINIT-002",
                "category_scores": {
                    ReadinessCategory.REGULATORY.value: 100.0,
                    ReadinessCategory.STAFFING.value: 85.0,
                    ReadinessCategory.FACILITIES.value: 90.0,
                    ReadinessCategory.EQUIPMENT.value: 95.0,
                    ReadinessCategory.PHARMACY.value: 100.0,
                    ReadinessCategory.LABORATORY.value: 90.0,
                    ReadinessCategory.TRAINING.value: 95.0,
                    ReadinessCategory.IT_SYSTEMS.value: 85.0,
                },
                "overall_score": 92.5,
                "blockers": [],
                "assessed_date": now - timedelta(days=50),
                "assessed_by": "Sarah Chen (CRA)",
            },
            {
                "site_id": "SINIT-003",
                "category_scores": {
                    ReadinessCategory.REGULATORY.value: 60.0,
                    ReadinessCategory.STAFFING.value: 80.0,
                    ReadinessCategory.FACILITIES.value: 90.0,
                    ReadinessCategory.EQUIPMENT.value: 85.0,
                    ReadinessCategory.PHARMACY.value: 75.0,
                    ReadinessCategory.LABORATORY.value: 90.0,
                    ReadinessCategory.TRAINING.value: 70.0,
                    ReadinessCategory.IT_SYSTEMS.value: 80.0,
                },
                "overall_score": 78.8,
                "blockers": ["IRB approval pending", "Informed consent not yet approved", "Budget agreement under review"],
                "assessed_date": now - timedelta(days=15),
                "assessed_by": "Lisa Martinez (CRA)",
            },
            {
                "site_id": "SINIT-004",
                "category_scores": {
                    ReadinessCategory.REGULATORY.value: 30.0,
                    ReadinessCategory.STAFFING.value: 60.0,
                    ReadinessCategory.FACILITIES.value: 85.0,
                    ReadinessCategory.EQUIPMENT.value: 80.0,
                    ReadinessCategory.PHARMACY.value: 50.0,
                    ReadinessCategory.LABORATORY.value: 75.0,
                    ReadinessCategory.TRAINING.value: 40.0,
                    ReadinessCategory.IT_SYSTEMS.value: 70.0,
                },
                "overall_score": 61.3,
                "blockers": ["Regulatory package incomplete", "Additional coordinator needed", "Protocol training not completed", "Pharmacy qualification pending"],
                "assessed_date": now - timedelta(days=10),
                "assessed_by": "Lisa Martinez (CRA)",
            },
            {
                "site_id": "SINIT-005",
                "category_scores": {
                    ReadinessCategory.REGULATORY.value: 100.0,
                    ReadinessCategory.STAFFING.value: 100.0,
                    ReadinessCategory.FACILITIES.value: 100.0,
                    ReadinessCategory.EQUIPMENT.value: 100.0,
                    ReadinessCategory.PHARMACY.value: 100.0,
                    ReadinessCategory.LABORATORY.value: 100.0,
                    ReadinessCategory.TRAINING.value: 100.0,
                    ReadinessCategory.IT_SYSTEMS.value: 95.0,
                },
                "overall_score": 99.4,
                "blockers": [],
                "assessed_date": now - timedelta(days=185),
                "assessed_by": "Robert Kim (CRA)",
            },
            {
                "site_id": "SINIT-008",
                "category_scores": {
                    ReadinessCategory.REGULATORY.value: 100.0,
                    ReadinessCategory.STAFFING.value: 100.0,
                    ReadinessCategory.FACILITIES.value: 100.0,
                    ReadinessCategory.EQUIPMENT.value: 100.0,
                    ReadinessCategory.PHARMACY.value: 100.0,
                    ReadinessCategory.LABORATORY.value: 100.0,
                    ReadinessCategory.TRAINING.value: 100.0,
                    ReadinessCategory.IT_SYSTEMS.value: 100.0,
                },
                "overall_score": 100.0,
                "blockers": [],
                "assessed_date": now - timedelta(days=215),
                "assessed_by": "Jennifer Adams (CRA)",
            },
            {
                "site_id": "SINIT-009",
                "category_scores": {
                    ReadinessCategory.REGULATORY.value: 50.0,
                    ReadinessCategory.STAFFING.value: 75.0,
                    ReadinessCategory.FACILITIES.value: 95.0,
                    ReadinessCategory.EQUIPMENT.value: 90.0,
                    ReadinessCategory.PHARMACY.value: 85.0,
                    ReadinessCategory.LABORATORY.value: 95.0,
                    ReadinessCategory.TRAINING.value: 80.0,
                    ReadinessCategory.IT_SYSTEMS.value: 90.0,
                },
                "overall_score": 82.5,
                "blockers": ["IRB approval pending", "Dedicated coordinator assignment pending"],
                "assessed_date": now - timedelta(days=20),
                "assessed_by": "Jennifer Adams (CRA)",
            },
        ]

        for ra in readiness_data:
            assessment = ReadinessAssessment(**ra)
            self._readiness_assessments[ra["site_id"]] = assessment

    # ------------------------------------------------------------------
    # Site CRUD
    # ------------------------------------------------------------------

    def list_sites(
        self,
        *,
        trial_id: str | None = None,
        status: SiteStatus | None = None,
        country: str | None = None,
    ) -> list[SiteInitiation]:
        """List sites with optional filters."""
        with self._lock:
            result = list(self._sites.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if status is not None:
            result = [s for s in result if s.status == status]
        if country is not None:
            result = [s for s in result if s.country == country]

        return sorted(result, key=lambda s: s.created_at, reverse=True)

    def get_site(self, site_id: str) -> SiteInitiation | None:
        """Get a single site by ID."""
        with self._lock:
            return self._sites.get(site_id)

    def create_site(self, payload: SiteInitiationCreate) -> SiteInitiation:
        """Create a new site initiation record."""
        now = datetime.now(timezone.utc)
        site_id = f"SINIT-{uuid4().hex[:8].upper()}"
        site = SiteInitiation(
            id=site_id,
            trial_id=payload.trial_id,
            site_number=payload.site_number,
            site_name=payload.site_name,
            principal_investigator=payload.principal_investigator,
            institution=payload.institution,
            country=payload.country,
            status=SiteStatus.IDENTIFIED,
            target_enrollment=payload.target_enrollment,
            current_enrollment=0,
            qualification_visits=[],
            regulatory_documents=[],
            milestones=[],
            activation_date=None,
            created_at=now,
        )

        # Auto-create initial milestone
        ms_id = f"MS-{uuid4().hex[:8].upper()}"
        milestone = SiteMilestone(
            id=ms_id,
            site_id=site_id,
            milestone_type=MilestoneType.SITE_IDENTIFIED,
            target_date=now,
            actual_date=now,
            status=MilestoneStatus.COMPLETED,
            notes="Auto-created on site creation",
        )

        with self._lock:
            self._milestones[ms_id] = milestone
            site_data = site.model_dump()
            site_data["milestones"] = [milestone]
            site = SiteInitiation(**site_data)
            self._sites[site_id] = site

        logger.info("Created site initiation %s: %s", site_id, payload.site_name)
        return site

    def update_site(self, site_id: str, payload: SiteInitiationUpdate) -> SiteInitiation | None:
        """Update an existing site initiation record."""
        with self._lock:
            existing = self._sites.get(site_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SiteInitiation(**data)
            self._sites[site_id] = updated
        return updated

    def delete_site(self, site_id: str) -> bool:
        """Delete a site. Returns True if deleted, False if not found."""
        with self._lock:
            if site_id in self._sites:
                del self._sites[site_id]
                # Clean up related data
                self._readiness_assessments.pop(site_id, None)
                to_remove_qv = [k for k, v in self._qualification_visits.items() if v.site_id == site_id]
                for k in to_remove_qv:
                    del self._qualification_visits[k]
                to_remove_doc = [k for k, v in self._regulatory_documents.items() if v.site_id == site_id]
                for k in to_remove_doc:
                    del self._regulatory_documents[k]
                to_remove_ms = [k for k, v in self._milestones.items() if v.site_id == site_id]
                for k in to_remove_ms:
                    del self._milestones[k]
                return True
            return False

    # ------------------------------------------------------------------
    # Lifecycle Transitions
    # ------------------------------------------------------------------

    def _transition_status(self, site_id: str, target_status: SiteStatus) -> SiteInitiation | None:
        """Attempt a lifecycle transition. Returns None if site not found, raises ValueError on invalid transition."""
        with self._lock:
            existing = self._sites.get(site_id)
            if existing is None:
                return None

            valid = _VALID_TRANSITIONS.get(existing.status, [])
            if target_status not in valid:
                raise ValueError(
                    f"Site '{site_id}' cannot transition from '{existing.status.value}' to '{target_status.value}'"
                )

            data = existing.model_dump()
            data["status"] = target_status

            if target_status == SiteStatus.ACTIVATED:
                data["activation_date"] = datetime.now(timezone.utc)

            updated = SiteInitiation(**data)
            self._sites[site_id] = updated
        logger.info("Transitioned site %s to %s", site_id, target_status.value)
        return updated

    def submit_for_qualification(self, site_id: str) -> SiteInitiation | None:
        """Transition site from identified to selected."""
        return self._transition_status(site_id, SiteStatus.SELECTED)

    def complete_qualification(self, site_id: str) -> SiteInitiation | None:
        """Transition site from selected to qualification_visit."""
        return self._transition_status(site_id, SiteStatus.QUALIFICATION_VISIT)

    def submit_regulatory(self, site_id: str) -> SiteInitiation | None:
        """Transition site from qualification_visit to regulatory_submitted."""
        return self._transition_status(site_id, SiteStatus.REGULATORY_SUBMITTED)

    def activate_site(self, site_id: str) -> SiteInitiation | None:
        """Transition site from regulatory_submitted to activated."""
        return self._transition_status(site_id, SiteStatus.ACTIVATED)

    def begin_enrollment(self, site_id: str) -> SiteInitiation | None:
        """Transition site from activated to enrolling."""
        return self._transition_status(site_id, SiteStatus.ENROLLING)

    def close_site(self, site_id: str) -> SiteInitiation | None:
        """Transition site to closed (from activated or enrolling)."""
        return self._transition_status(site_id, SiteStatus.CLOSED)

    # ------------------------------------------------------------------
    # Qualification Visits
    # ------------------------------------------------------------------

    def list_qualification_visits(self, site_id: str) -> list[QualificationVisit]:
        """List qualification visits for a site."""
        with self._lock:
            return sorted(
                [v for v in self._qualification_visits.values() if v.site_id == site_id],
                key=lambda v: v.visit_date,
                reverse=True,
            )

    def add_qualification_visit(
        self, site_id: str, payload: QualificationVisitCreate
    ) -> QualificationVisit:
        """Add a qualification visit to a site."""
        now = datetime.now(timezone.utc)
        visit_id = f"QV-{uuid4().hex[:8].upper()}"

        with self._lock:
            site = self._sites.get(site_id)
            if site is None:
                raise ValueError(f"Site '{site_id}' not found")

            visit = QualificationVisit(
                id=visit_id,
                site_id=site_id,
                visit_date=payload.visit_date,
                attendees=payload.attendees,
                findings=payload.findings,
                recommendation=payload.recommendation,
                action_items=payload.action_items,
                created_at=now,
            )
            self._qualification_visits[visit_id] = visit
            self._refresh_site_qualification_visits(site_id)

        logger.info("Added qualification visit %s to site %s", visit_id, site_id)
        return visit

    def _refresh_site_qualification_visits(self, site_id: str) -> None:
        """Refresh embedded qualification visits. Must hold _lock."""
        site = self._sites.get(site_id)
        if site is None:
            return
        visits = [v for v in self._qualification_visits.values() if v.site_id == site_id]
        data = site.model_dump()
        data["qualification_visits"] = visits
        self._sites[site_id] = SiteInitiation(**data)

    # ------------------------------------------------------------------
    # Regulatory Documents
    # ------------------------------------------------------------------

    def list_regulatory_documents(
        self,
        site_id: str,
        *,
        doc_type: DocumentType | None = None,
        status: DocumentStatus | None = None,
    ) -> list[RegulatoryDocument]:
        """List regulatory documents for a site."""
        with self._lock:
            result = [d for d in self._regulatory_documents.values() if d.site_id == site_id]

        if doc_type is not None:
            result = [d for d in result if d.doc_type == doc_type]
        if status is not None:
            result = [d for d in result if d.status == status]

        return result

    def add_regulatory_document(
        self, site_id: str, payload: RegulatoryDocumentCreate
    ) -> RegulatoryDocument:
        """Add a regulatory document to a site."""
        doc_id = f"DOC-{uuid4().hex[:8].upper()}"

        with self._lock:
            site = self._sites.get(site_id)
            if site is None:
                raise ValueError(f"Site '{site_id}' not found")

            status = DocumentStatus.SUBMITTED if payload.submitted_date else DocumentStatus.NOT_SUBMITTED
            doc = RegulatoryDocument(
                id=doc_id,
                site_id=site_id,
                doc_type=payload.doc_type,
                status=status,
                submitted_date=payload.submitted_date,
                approved_date=None,
                expiry_date=None,
                notes=payload.notes,
                version=payload.version,
            )
            self._regulatory_documents[doc_id] = doc
            self._refresh_site_regulatory_documents(site_id)

        logger.info("Added regulatory document %s to site %s", doc_id, site_id)
        return doc

    def update_regulatory_document(
        self, doc_id: str, payload: RegulatoryDocumentUpdate
    ) -> RegulatoryDocument | None:
        """Update a regulatory document."""
        with self._lock:
            existing = self._regulatory_documents.get(doc_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = RegulatoryDocument(**data)
            self._regulatory_documents[doc_id] = updated
            self._refresh_site_regulatory_documents(existing.site_id)
        return updated

    def get_regulatory_document(self, doc_id: str) -> RegulatoryDocument | None:
        """Get a single regulatory document by ID."""
        with self._lock:
            return self._regulatory_documents.get(doc_id)

    def _refresh_site_regulatory_documents(self, site_id: str) -> None:
        """Refresh embedded regulatory documents. Must hold _lock."""
        site = self._sites.get(site_id)
        if site is None:
            return
        docs = [d for d in self._regulatory_documents.values() if d.site_id == site_id]
        data = site.model_dump()
        data["regulatory_documents"] = docs
        self._sites[site_id] = SiteInitiation(**data)

    # ------------------------------------------------------------------
    # Readiness Assessment
    # ------------------------------------------------------------------

    def get_readiness_assessment(self, site_id: str) -> ReadinessAssessment | None:
        """Get the readiness assessment for a site."""
        with self._lock:
            return self._readiness_assessments.get(site_id)

    def update_readiness(self, site_id: str, payload: ReadinessUpdate) -> ReadinessAssessment | None:
        """Update or create the readiness assessment for a site."""
        now = datetime.now(timezone.utc)
        with self._lock:
            if site_id not in self._sites:
                raise ValueError(f"Site '{site_id}' not found")

            scores = payload.category_scores
            overall = round(sum(scores.values()) / max(1, len(scores)), 1) if scores else 0.0

            assessment = ReadinessAssessment(
                site_id=site_id,
                category_scores=scores,
                overall_score=overall,
                blockers=payload.blockers,
                assessed_date=now,
                assessed_by=payload.assessed_by,
            )
            self._readiness_assessments[site_id] = assessment
        logger.info("Updated readiness assessment for site %s (score: %.1f)", site_id, overall)
        return assessment

    # ------------------------------------------------------------------
    # Milestones
    # ------------------------------------------------------------------

    def get_milestones(self, site_id: str) -> list[SiteMilestone]:
        """Get all milestones for a site."""
        with self._lock:
            return sorted(
                [m for m in self._milestones.values() if m.site_id == site_id],
                key=lambda m: m.target_date,
            )

    def update_milestone(self, milestone_id: str, payload: MilestoneUpdate) -> SiteMilestone | None:
        """Update a milestone."""
        with self._lock:
            existing = self._milestones.get(milestone_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SiteMilestone(**data)
            self._milestones[milestone_id] = updated
            self._refresh_site_milestones(existing.site_id)
        return updated

    def _refresh_site_milestones(self, site_id: str) -> None:
        """Refresh embedded milestones. Must hold _lock."""
        site = self._sites.get(site_id)
        if site is None:
            return
        ms_list = [m for m in self._milestones.values() if m.site_id == site_id]
        data = site.model_dump()
        data["milestones"] = ms_list
        self._sites[site_id] = SiteInitiation(**data)

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_activation_metrics(self) -> SiteActivationMetrics:
        """Compute aggregated site activation metrics."""
        with self._lock:
            sites = list(self._sites.values())
            docs = list(self._regulatory_documents.values())
            assessments = list(self._readiness_assessments.values())

        # Sites by status
        by_status: dict[str, int] = {}
        activation_days: list[float] = []
        activated_count = 0
        pending_count = 0

        for site in sites:
            by_status[site.status.value] = by_status.get(site.status.value, 0) + 1
            if site.status in (SiteStatus.ACTIVATED, SiteStatus.ENROLLING):
                activated_count += 1
                if site.activation_date and site.created_at:
                    days = (site.activation_date - site.created_at).days
                    activation_days.append(float(days))
            elif site.status != SiteStatus.CLOSED:
                pending_count += 1

        avg_days = round(sum(activation_days) / max(1, len(activation_days)), 1)

        # Documents by status
        docs_by_status: dict[str, int] = {}
        for doc in docs:
            docs_by_status[doc.status.value] = docs_by_status.get(doc.status.value, 0) + 1

        # Average readiness score
        readiness_scores = [a.overall_score for a in assessments]
        avg_readiness = round(sum(readiness_scores) / max(1, len(readiness_scores)), 1)

        # Bottleneck analysis: find categories most often appearing as lowest score
        bottleneck_counts: dict[str, int] = {}
        for a in assessments:
            if a.category_scores:
                min_score = min(a.category_scores.values())
                for cat, score in a.category_scores.items():
                    if score == min_score and score < 80.0:
                        bottleneck_counts[cat] = bottleneck_counts.get(cat, 0) + 1

        bottleneck_categories = sorted(
            bottleneck_counts.keys(), key=lambda c: bottleneck_counts[c], reverse=True
        )[:5]

        # Average target enrollment
        enrollments = [s.target_enrollment for s in sites if s.target_enrollment > 0]
        avg_enrollment = round(sum(enrollments) / max(1, len(enrollments)), 1)

        return SiteActivationMetrics(
            total_sites=len(sites),
            sites_by_status=by_status,
            avg_days_to_activate=avg_days,
            sites_activated=activated_count,
            sites_pending_activation=pending_count,
            avg_readiness_score=avg_readiness,
            total_regulatory_documents=len(docs),
            documents_by_status=docs_by_status,
            bottleneck_categories=bottleneck_categories,
            avg_target_enrollment=avg_enrollment,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: SiteInitiationService | None = None
_instance_lock = threading.Lock()


def get_site_initiation_service() -> SiteInitiationService:
    """Return the singleton SiteInitiationService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = SiteInitiationService()
    return _instance


def reset_site_initiation_service() -> SiteInitiationService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = SiteInitiationService()
    return _instance
