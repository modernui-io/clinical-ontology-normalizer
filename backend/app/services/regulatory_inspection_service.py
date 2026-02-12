"""Regulatory Inspection Management Service (REG-INSP).

Manages inspection operations: inspection scheduling, finding tracking,
CAPA response preparation, mock inspection management, inspection readiness
assessment, commitment tracking, and regulatory inspection operational metrics.

Usage:
    from app.services.regulatory_inspection_service import (
        get_regulatory_inspection_service,
    )

    svc = get_regulatory_inspection_service()
    inspections = svc.list_inspections()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.regulatory_inspection import (
    FindingClassification,
    FindingSeverity,
    Inspection,
    InspectionAuthority,
    InspectionCommitment,
    InspectionCommitmentCreate,
    InspectionCommitmentUpdate,
    InspectionCreate,
    InspectionFinding,
    InspectionFindingCreate,
    InspectionFindingUpdate,
    InspectionStatus,
    InspectionType,
    InspectionUpdate,
    MockInspection,
    MockInspectionCreate,
    MockInspectionUpdate,
    ReadinessAssessment,
    ReadinessAssessmentCreate,
    ReadinessAssessmentUpdate,
    RegulatoryInspectionMetrics,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class RegulatoryInspectionService:
    """In-memory Regulatory Inspection Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._inspections: dict[str, Inspection] = {}
        self._findings: dict[str, InspectionFinding] = {}
        self._mock_inspections: dict[str, MockInspection] = {}
        self._readiness_assessments: dict[str, ReadinessAssessment] = {}
        self._commitments: dict[str, InspectionCommitment] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic inspection data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Inspections ---
        inspections_data = [
            {
                "id": "INSP-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "inspection_type": InspectionType.PRE_APPROVAL,
                "authority": InspectionAuthority.FDA,
                "status": InspectionStatus.COMPLETED,
                "title": "FDA Pre-Approval Inspection - EYLEA HD Phase 3",
                "scope": "GCP compliance, data integrity, source document verification for pivotal efficacy endpoints",
                "announced_date": now - timedelta(days=120),
                "start_date": now - timedelta(days=90),
                "end_date": now - timedelta(days=85),
                "duration_days": 5,
                "inspectors": ["Dr. Sarah Mitchell", "John Baker"],
                "areas_covered": ["informed consent", "source data verification", "adverse event reporting", "investigational product accountability"],
                "sponsor_lead": "Dr. Rebecca Foster",
                "site_contact": "Dr. James Chen",
                "outcome": "No critical findings. Two minor observations issued.",
                "response_due_date": now - timedelta(days=55),
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "INSP-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "inspection_type": InspectionType.ROUTINE_GCP,
                "authority": InspectionAuthority.EMA,
                "status": InspectionStatus.RESPONSE_SUBMITTED,
                "title": "EMA Routine GCP Inspection - EYLEA HD European Sites",
                "scope": "GCP compliance review for EU clinical sites participating in EYLEA HD program",
                "announced_date": now - timedelta(days=100),
                "start_date": now - timedelta(days=75),
                "end_date": now - timedelta(days=72),
                "duration_days": 3,
                "inspectors": ["Dr. Marie Laurent", "Dr. Hans Weber"],
                "areas_covered": ["protocol compliance", "data management", "safety reporting", "TMF completeness"],
                "sponsor_lead": "Dr. Thomas Eriksson",
                "site_contact": "Dr. Anna Schmidt",
                "outcome": "One major finding related to delayed SAE reporting. CAPA required.",
                "response_due_date": now - timedelta(days=42),
                "created_at": now - timedelta(days=130),
            },
            {
                "id": "INSP-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": None,
                "inspection_type": InspectionType.SYSTEMS,
                "authority": InspectionAuthority.FDA,
                "status": InspectionStatus.CLOSED,
                "title": "FDA Systems Inspection - Regeneron Sponsor Facilities",
                "scope": "Sponsor oversight systems, quality management, computerized systems validation",
                "announced_date": now - timedelta(days=200),
                "start_date": now - timedelta(days=180),
                "end_date": now - timedelta(days=175),
                "duration_days": 5,
                "inspectors": ["Dr. Patricia Gomez", "Robert Huang", "Lisa Patterson"],
                "areas_covered": ["quality management system", "CAPA processes", "vendor oversight", "computerized systems", "training records"],
                "sponsor_lead": "Dr. William Park",
                "site_contact": None,
                "outcome": "Satisfactory. Minor recommendations for vendor oversight documentation.",
                "response_due_date": None,
                "created_at": now - timedelta(days=220),
            },
            {
                "id": "INSP-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "inspection_type": InspectionType.ROUTINE_GCP,
                "authority": InspectionAuthority.FDA,
                "status": InspectionStatus.COMPLETED,
                "title": "FDA Routine GCP Inspection - Dupixent Atopic Dermatitis Phase 3",
                "scope": "GCP compliance, EASI scoring consistency, photographic documentation review",
                "announced_date": now - timedelta(days=80),
                "start_date": now - timedelta(days=60),
                "end_date": now - timedelta(days=57),
                "duration_days": 3,
                "inspectors": ["Dr. Karen White", "Michael Torres"],
                "areas_covered": ["EASI scoring", "IGA assessment", "photographic documentation", "informed consent", "IP management"],
                "sponsor_lead": "Dr. Angela Martinez",
                "site_contact": "Dr. Robert Williams",
                "outcome": "Two findings: one major (EASI scoring inconsistency), one minor (consent form version).",
                "response_due_date": now - timedelta(days=27),
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "INSP-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-105",
                "inspection_type": InspectionType.FOR_CAUSE,
                "authority": InspectionAuthority.FDA,
                "status": InspectionStatus.RESPONSE_REQUIRED,
                "title": "FDA For-Cause Inspection - Dupixent Data Integrity Concerns",
                "scope": "Investigation of reported data integrity concerns at clinical site including falsification allegations",
                "announced_date": now - timedelta(days=45),
                "start_date": now - timedelta(days=30),
                "end_date": now - timedelta(days=26),
                "duration_days": 4,
                "inspectors": ["Dr. David Park", "Jennifer Collins", "Dr. Anthony Rivera"],
                "areas_covered": ["source data verification", "data integrity", "principal investigator oversight", "staff qualifications", "audit trail review"],
                "sponsor_lead": "Dr. Catherine Liu",
                "site_contact": "Dr. Mark Thompson",
                "outcome": "Critical finding: evidence of data fabrication for 3 subjects. Form 483 issued.",
                "response_due_date": now + timedelta(days=5),
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "INSP-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-106",
                "inspection_type": InspectionType.ROUTINE_GCP,
                "authority": InspectionAuthority.PMDA,
                "status": InspectionStatus.COMPLETED,
                "title": "PMDA GCP Inspection - Dupixent Japanese Sites",
                "scope": "GCP compliance review for Japanese clinical sites in Dupixent atopic dermatitis program",
                "announced_date": now - timedelta(days=140),
                "start_date": now - timedelta(days=110),
                "end_date": now - timedelta(days=107),
                "duration_days": 3,
                "inspectors": ["Dr. Takeshi Yamamoto", "Dr. Yuki Tanaka"],
                "areas_covered": ["informed consent", "protocol compliance", "safety reporting", "IP management"],
                "sponsor_lead": "Dr. David Nakamura",
                "site_contact": "Dr. Haruki Sato",
                "outcome": "No critical findings. Two observations regarding consent documentation translation.",
                "response_due_date": now - timedelta(days=77),
                "created_at": now - timedelta(days=160),
            },
            {
                "id": "INSP-007",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "inspection_type": InspectionType.PRE_APPROVAL,
                "authority": InspectionAuthority.FDA,
                "status": InspectionStatus.IN_PROGRESS,
                "title": "FDA Pre-Approval Inspection - Libtayo NSCLC Frontline",
                "scope": "Pre-approval inspection for sBLA: RECIST assessment, tumor response evaluation, PFS endpoint verification",
                "announced_date": now - timedelta(days=20),
                "start_date": now - timedelta(days=3),
                "end_date": None,
                "duration_days": 0,
                "inspectors": ["Dr. Lisa Chen", "Dr. Mark Anderson"],
                "areas_covered": ["RECIST 1.1 assessments", "independent radiology review", "PFS/OS endpoints", "informed consent"],
                "sponsor_lead": "Dr. Andrew Foster",
                "site_contact": "Dr. Catherine Liu",
                "outcome": None,
                "response_due_date": None,
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "INSP-008",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-108",
                "inspection_type": InspectionType.ROUTINE_GCP,
                "authority": InspectionAuthority.MHRA,
                "status": InspectionStatus.ANNOUNCED,
                "title": "MHRA GCP Inspection - Libtayo UK Sites",
                "scope": "Routine GCP compliance review for UK clinical sites in Libtayo oncology program",
                "announced_date": now - timedelta(days=10),
                "start_date": now + timedelta(days=14),
                "end_date": None,
                "duration_days": 0,
                "inspectors": [],
                "areas_covered": [],
                "sponsor_lead": "Dr. Natalie Wong",
                "site_contact": "Dr. James Bradford",
                "outcome": None,
                "response_due_date": None,
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "INSP-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": None,
                "inspection_type": InspectionType.SYSTEMS,
                "authority": InspectionAuthority.EMA,
                "status": InspectionStatus.COMPLETED,
                "title": "EMA Pharmacovigilance Systems Inspection",
                "scope": "Pharmacovigilance system master file review, signal detection processes, PSUR preparation",
                "announced_date": now - timedelta(days=160),
                "start_date": now - timedelta(days=140),
                "end_date": now - timedelta(days=136),
                "duration_days": 4,
                "inspectors": ["Dr. Pierre Dubois", "Dr. Claudia Rossi"],
                "areas_covered": ["PSMF", "signal detection", "PSUR preparation", "ICSR processing", "risk management"],
                "sponsor_lead": "Dr. Gregory Harris",
                "site_contact": None,
                "outcome": "Two major findings related to signal detection timeliness and ICSR quality review.",
                "response_due_date": now - timedelta(days=100),
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "INSP-010",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "inspection_type": InspectionType.DIRECTED,
                "authority": InspectionAuthority.HEALTH_CANADA,
                "status": InspectionStatus.PLANNED,
                "title": "Health Canada Directed Inspection - EYLEA HD Canadian Sites",
                "scope": "Directed inspection following signal from periodic safety report review",
                "announced_date": None,
                "start_date": now + timedelta(days=30),
                "end_date": None,
                "duration_days": 0,
                "inspectors": [],
                "areas_covered": [],
                "sponsor_lead": "Dr. Rebecca Foster",
                "site_contact": "Dr. Michelle Tremblay",
                "outcome": None,
                "response_due_date": None,
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "INSP-011",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "inspection_type": InspectionType.ROUTINE_GCP,
                "authority": InspectionAuthority.TGA,
                "status": InspectionStatus.COMPLETED,
                "title": "TGA GCP Inspection - Dupixent Australian Sites",
                "scope": "Routine GCP compliance for Australian sites in Dupixent program",
                "announced_date": now - timedelta(days=170),
                "start_date": now - timedelta(days=150),
                "end_date": now - timedelta(days=147),
                "duration_days": 3,
                "inspectors": ["Dr. Sarah Reynolds"],
                "areas_covered": ["informed consent", "data management", "IP accountability"],
                "sponsor_lead": "Dr. Angela Martinez",
                "site_contact": "Dr. Peter Walsh",
                "outcome": "No significant findings. One recommendation for consent process improvement.",
                "response_due_date": None,
                "created_at": now - timedelta(days=190),
            },
            {
                "id": "INSP-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "inspection_type": InspectionType.ROUTINE_GCP,
                "authority": InspectionAuthority.FDA,
                "status": InspectionStatus.CLOSED,
                "title": "FDA Routine GCP Inspection - Libtayo CSCC Pivotal",
                "scope": "GCP compliance review for pivotal CSCC study sites",
                "announced_date": now - timedelta(days=250),
                "start_date": now - timedelta(days=230),
                "end_date": now - timedelta(days=227),
                "duration_days": 3,
                "inspectors": ["Dr. Karen White"],
                "areas_covered": ["tumor assessments", "response criteria", "safety reporting", "informed consent"],
                "sponsor_lead": "Dr. Andrew Foster",
                "site_contact": "Dr. Catherine Liu",
                "outcome": "Satisfactory outcome. One minor observation regarding visit window documentation.",
                "response_due_date": None,
                "created_at": now - timedelta(days=270),
            },
        ]

        for i in inspections_data:
            self._inspections[i["id"]] = Inspection(**i)

        # --- 15 Inspection Findings ---
        findings_data = [
            {
                "id": "FND-001",
                "inspection_id": "INSP-001",
                "finding_number": "483-2024-001-01",
                "severity": FindingSeverity.MINOR,
                "classification": FindingClassification.MINOR_FINDING,
                "description": "Informed consent forms for 2 subjects were signed after the screening visit procedures were initiated.",
                "regulatory_reference": "21 CFR 50.25",
                "area": "informed consent",
                "root_cause": "Site staff initiated screening labs before confirming signed ICF",
                "response_text": "Corrective training provided to all site staff on ICF timing requirements.",
                "response_status": "accepted",
                "response_due_date": now - timedelta(days=55),
                "response_submitted_date": now - timedelta(days=60),
                "capa_required": False,
                "capa_id": None,
                "assigned_to": "Dr. James Chen",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "FND-002",
                "inspection_id": "INSP-001",
                "finding_number": "483-2024-001-02",
                "severity": FindingSeverity.MINOR,
                "classification": FindingClassification.MINOR_FINDING,
                "description": "Temperature monitoring logs for investigational product storage showed a 2-hour gap on March 15, 2024.",
                "regulatory_reference": "21 CFR 312.62",
                "area": "investigational product accountability",
                "root_cause": "Temporary sensor malfunction; backup manual monitoring was not initiated immediately",
                "response_text": "Backup monitoring SOP updated. Redundant temperature sensor installed.",
                "response_status": "accepted",
                "response_due_date": now - timedelta(days=55),
                "response_submitted_date": now - timedelta(days=58),
                "capa_required": False,
                "capa_id": None,
                "assigned_to": "Dr. James Chen",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "FND-003",
                "inspection_id": "INSP-002",
                "finding_number": "EMA-2024-002-01",
                "severity": FindingSeverity.MAJOR,
                "classification": FindingClassification.MAJOR_FINDING,
                "description": "Systematic delays in SAE reporting: 4 of 12 SAEs were reported to sponsor more than 24 hours after site awareness.",
                "regulatory_reference": "ICH E6(R2) 4.11.1",
                "area": "safety reporting",
                "root_cause": "Inadequate after-hours SAE reporting process; PI delegation log incomplete",
                "response_text": "Implemented 24/7 SAE reporting hotline. Updated delegation log. Retrained all staff.",
                "response_status": "submitted",
                "response_due_date": now - timedelta(days=42),
                "response_submitted_date": now - timedelta(days=45),
                "capa_required": True,
                "capa_id": "CAPA-2024-003",
                "assigned_to": "Dr. Anna Schmidt",
                "created_at": now - timedelta(days=72),
            },
            {
                "id": "FND-004",
                "inspection_id": "INSP-004",
                "finding_number": "483-2024-004-01",
                "severity": FindingSeverity.MAJOR,
                "classification": FindingClassification.MAJOR_FINDING,
                "description": "EASI scoring inconsistency: inter-rater variability exceeding acceptable thresholds for 6 of 20 assessed subjects.",
                "regulatory_reference": "21 CFR 312.62",
                "area": "EASI scoring",
                "root_cause": "Insufficient calibration training for EASI raters; no ongoing inter-rater reliability checks",
                "response_text": "Mandatory re-certification for all EASI raters. Implemented quarterly inter-rater reliability testing.",
                "response_status": "pending",
                "response_due_date": now - timedelta(days=27),
                "response_submitted_date": None,
                "capa_required": True,
                "capa_id": "CAPA-2024-004",
                "assigned_to": "Dr. Robert Williams",
                "created_at": now - timedelta(days=57),
            },
            {
                "id": "FND-005",
                "inspection_id": "INSP-004",
                "finding_number": "483-2024-004-02",
                "severity": FindingSeverity.MINOR,
                "classification": FindingClassification.MINOR_FINDING,
                "description": "Consent form version 3.1 was used for 1 subject after version 3.2 was approved by the IRB.",
                "regulatory_reference": "21 CFR 50.25",
                "area": "informed consent",
                "root_cause": "Delayed distribution of updated consent forms to sub-investigator",
                "response_text": None,
                "response_status": "pending",
                "response_due_date": now - timedelta(days=27),
                "response_submitted_date": None,
                "capa_required": False,
                "capa_id": None,
                "assigned_to": "Dr. Robert Williams",
                "created_at": now - timedelta(days=57),
            },
            {
                "id": "FND-006",
                "inspection_id": "INSP-005",
                "finding_number": "483-2024-005-01",
                "severity": FindingSeverity.CRITICAL,
                "classification": FindingClassification.FORM_483,
                "description": "Evidence of data fabrication: EASI scores, vital signs, and lab results for subjects DUP-2015, DUP-2016, DUP-2017 were fabricated.",
                "regulatory_reference": "21 CFR 312.70",
                "area": "data integrity",
                "root_cause": "Research coordinator fabricated data for subjects who missed multiple visits",
                "response_text": None,
                "response_status": "pending",
                "response_due_date": now + timedelta(days=5),
                "response_submitted_date": None,
                "capa_required": True,
                "capa_id": "CAPA-2024-006",
                "assigned_to": "Dr. Catherine Liu",
                "created_at": now - timedelta(days=26),
            },
            {
                "id": "FND-007",
                "inspection_id": "INSP-005",
                "finding_number": "483-2024-005-02",
                "severity": FindingSeverity.MAJOR,
                "classification": FindingClassification.FORM_483,
                "description": "Inadequate PI oversight: PI failed to supervise research coordinator activities and review source documents.",
                "regulatory_reference": "21 CFR 312.60",
                "area": "principal investigator oversight",
                "root_cause": "PI did not perform regular source data review; no co-signature requirements for key data",
                "response_text": None,
                "response_status": "pending",
                "response_due_date": now + timedelta(days=5),
                "response_submitted_date": None,
                "capa_required": True,
                "capa_id": "CAPA-2024-007",
                "assigned_to": "Dr. Catherine Liu",
                "created_at": now - timedelta(days=26),
            },
            {
                "id": "FND-008",
                "inspection_id": "INSP-006",
                "finding_number": "PMDA-2024-006-01",
                "severity": FindingSeverity.OBSERVATION,
                "classification": FindingClassification.RECOMMENDATION,
                "description": "Minor inconsistencies in Japanese translation of consent form regarding withdrawal procedures.",
                "regulatory_reference": "J-GCP Article 50",
                "area": "informed consent",
                "root_cause": "Translation review did not include back-translation verification",
                "response_text": "Back-translation process implemented for all future consent form translations.",
                "response_status": "accepted",
                "response_due_date": now - timedelta(days=77),
                "response_submitted_date": now - timedelta(days=80),
                "capa_required": False,
                "capa_id": None,
                "assigned_to": "Dr. Haruki Sato",
                "created_at": now - timedelta(days=107),
            },
            {
                "id": "FND-009",
                "inspection_id": "INSP-006",
                "finding_number": "PMDA-2024-006-02",
                "severity": FindingSeverity.OBSERVATION,
                "classification": FindingClassification.RECOMMENDATION,
                "description": "Recommendation to improve documentation of concomitant medication reconciliation.",
                "regulatory_reference": "J-GCP Article 47",
                "area": "data management",
                "root_cause": "Concomitant medication log updates were delayed relative to visit dates",
                "response_text": "Real-time concomitant medication entry required at each visit.",
                "response_status": "accepted",
                "response_due_date": now - timedelta(days=77),
                "response_submitted_date": now - timedelta(days=79),
                "capa_required": False,
                "capa_id": None,
                "assigned_to": "Dr. Haruki Sato",
                "created_at": now - timedelta(days=107),
            },
            {
                "id": "FND-010",
                "inspection_id": "INSP-009",
                "finding_number": "EMA-2024-009-01",
                "severity": FindingSeverity.MAJOR,
                "classification": FindingClassification.MAJOR_FINDING,
                "description": "Signal detection activities not performed within required timeframes for 3 safety signals identified in PSUR cycle.",
                "regulatory_reference": "GVP Module IX",
                "area": "signal detection",
                "root_cause": "Insufficient staffing in signal management team during PSUR preparation period",
                "response_text": "Hired 2 additional signal management specialists. Implemented automated signal screening tool.",
                "response_status": "accepted",
                "response_due_date": now - timedelta(days=100),
                "response_submitted_date": now - timedelta(days=105),
                "capa_required": True,
                "capa_id": "CAPA-2024-010",
                "assigned_to": "Dr. Gregory Harris",
                "created_at": now - timedelta(days=136),
            },
            {
                "id": "FND-011",
                "inspection_id": "INSP-009",
                "finding_number": "EMA-2024-009-02",
                "severity": FindingSeverity.MAJOR,
                "classification": FindingClassification.MAJOR_FINDING,
                "description": "ICSR quality review process did not identify 5 cases with incorrect MedDRA coding.",
                "regulatory_reference": "GVP Module VI",
                "area": "ICSR processing",
                "root_cause": "Quality review checklist did not include MedDRA coding verification step",
                "response_text": "Updated QC checklist to include mandatory MedDRA coding verification. Retrospective review of all ICSRs initiated.",
                "response_status": "accepted",
                "response_due_date": now - timedelta(days=100),
                "response_submitted_date": now - timedelta(days=103),
                "capa_required": True,
                "capa_id": "CAPA-2024-011",
                "assigned_to": "Dr. Gregory Harris",
                "created_at": now - timedelta(days=136),
            },
            {
                "id": "FND-012",
                "inspection_id": "INSP-012",
                "finding_number": "483-2023-012-01",
                "severity": FindingSeverity.MINOR,
                "classification": FindingClassification.MINOR_FINDING,
                "description": "Visit window deviations for 3 subjects not documented as protocol deviations.",
                "regulatory_reference": "21 CFR 312.62",
                "area": "protocol compliance",
                "root_cause": "Site staff unfamiliar with protocol deviation reporting requirements for visit windows",
                "response_text": "Protocol deviation training completed for all staff. Visit window tracker implemented in EDC.",
                "response_status": "accepted",
                "response_due_date": now - timedelta(days=190),
                "response_submitted_date": now - timedelta(days=195),
                "capa_required": False,
                "capa_id": None,
                "assigned_to": "Dr. Catherine Liu",
                "created_at": now - timedelta(days=227),
            },
            {
                "id": "FND-013",
                "inspection_id": "INSP-011",
                "finding_number": "TGA-2024-011-01",
                "severity": FindingSeverity.OBSERVATION,
                "classification": FindingClassification.RECOMMENDATION,
                "description": "Recommendation to enhance consent process documentation for subjects with limited English proficiency.",
                "regulatory_reference": "TGA GCP Guidelines",
                "area": "informed consent",
                "root_cause": "No formal process for documenting interpreter-assisted consent procedures",
                "response_text": "Interpreter-assisted consent SOP developed and implemented.",
                "response_status": "accepted",
                "response_due_date": None,
                "response_submitted_date": now - timedelta(days=140),
                "capa_required": False,
                "capa_id": None,
                "assigned_to": "Dr. Peter Walsh",
                "created_at": now - timedelta(days=147),
            },
            {
                "id": "FND-014",
                "inspection_id": "INSP-005",
                "finding_number": "483-2024-005-03",
                "severity": FindingSeverity.MAJOR,
                "classification": FindingClassification.FORM_483,
                "description": "Failure to maintain adequate and accurate case histories: missing source documents for 5 subject visits.",
                "regulatory_reference": "21 CFR 312.62(b)",
                "area": "source data verification",
                "root_cause": "Research coordinator did not maintain original source documents for fabricated visits",
                "response_text": None,
                "response_status": "pending",
                "response_due_date": now + timedelta(days=5),
                "response_submitted_date": None,
                "capa_required": True,
                "capa_id": "CAPA-2024-014",
                "assigned_to": "Dr. Catherine Liu",
                "created_at": now - timedelta(days=26),
            },
            {
                "id": "FND-015",
                "inspection_id": "INSP-002",
                "finding_number": "EMA-2024-002-02",
                "severity": FindingSeverity.MINOR,
                "classification": FindingClassification.MINOR_FINDING,
                "description": "Trial master file missing signed monitoring visit reports for 2 of 15 monitoring visits.",
                "regulatory_reference": "ICH E6(R2) 8.3",
                "area": "TMF completeness",
                "root_cause": "CRA failed to upload signed reports within required timeline",
                "response_text": "Monitoring report upload reminders implemented. TMF completeness checks added to monitoring plan.",
                "response_status": "submitted",
                "response_due_date": now - timedelta(days=42),
                "response_submitted_date": now - timedelta(days=44),
                "capa_required": False,
                "capa_id": None,
                "assigned_to": "Dr. Anna Schmidt",
                "created_at": now - timedelta(days=72),
            },
        ]

        for f in findings_data:
            self._findings[f["id"]] = InspectionFinding(**f)

        # --- 10 Mock Inspections ---
        mock_inspections_data = [
            {
                "id": "MOCK-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "mock_type": "full",
                "target_authority": InspectionAuthority.FDA,
                "planned_date": now - timedelta(days=130),
                "actual_date": now - timedelta(days=130),
                "status": "completed",
                "lead_auditor": "Dr. Jennifer Walsh",
                "audit_team": ["Dr. Jennifer Walsh", "Sarah Kim", "Michael Brown"],
                "findings_count": 5,
                "critical_findings": 0,
                "readiness_score_pct": 88.5,
                "recommendations": ["Update ICF tracking process", "Improve IP temperature monitoring", "Enhance source document filing"],
                "created_at": now - timedelta(days=140),
            },
            {
                "id": "MOCK-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "mock_type": "focused",
                "target_authority": InspectionAuthority.EMA,
                "planned_date": now - timedelta(days=110),
                "actual_date": now - timedelta(days=110),
                "status": "completed",
                "lead_auditor": "Dr. Thomas Eriksson",
                "audit_team": ["Dr. Thomas Eriksson", "Maria Gonzalez"],
                "findings_count": 3,
                "critical_findings": 0,
                "readiness_score_pct": 82.0,
                "recommendations": ["Improve SAE reporting timeliness", "Update delegation log", "Enhance TMF filing discipline"],
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "MOCK-003",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "mock_type": "full",
                "target_authority": InspectionAuthority.FDA,
                "planned_date": now - timedelta(days=95),
                "actual_date": now - timedelta(days=95),
                "status": "completed",
                "lead_auditor": "Dr. Angela Martinez",
                "audit_team": ["Dr. Angela Martinez", "Robert Chen", "Lisa Park"],
                "findings_count": 7,
                "critical_findings": 1,
                "readiness_score_pct": 75.0,
                "recommendations": ["EASI rater re-certification required", "Consent form version control improvement", "Source document organization needed"],
                "created_at": now - timedelta(days=105),
            },
            {
                "id": "MOCK-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-105",
                "mock_type": "full",
                "target_authority": InspectionAuthority.FDA,
                "planned_date": now - timedelta(days=65),
                "actual_date": now - timedelta(days=65),
                "status": "completed",
                "lead_auditor": "Dr. Catherine Liu",
                "audit_team": ["Dr. Catherine Liu", "David Park", "Jennifer Collins"],
                "findings_count": 12,
                "critical_findings": 3,
                "readiness_score_pct": 52.0,
                "recommendations": ["Urgent: address data integrity concerns", "PI oversight improvement needed", "Staff retraining required"],
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "MOCK-005",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "mock_type": "full",
                "target_authority": InspectionAuthority.FDA,
                "planned_date": now - timedelta(days=40),
                "actual_date": now - timedelta(days=40),
                "status": "completed",
                "lead_auditor": "Dr. Andrew Foster",
                "audit_team": ["Dr. Andrew Foster", "Dr. Natalie Wong", "Kevin Taylor"],
                "findings_count": 4,
                "critical_findings": 0,
                "readiness_score_pct": 91.5,
                "recommendations": ["Minor RECIST documentation improvements", "Update radiology review SOP"],
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "MOCK-006",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-108",
                "mock_type": "focused",
                "target_authority": InspectionAuthority.MHRA,
                "planned_date": now - timedelta(days=25),
                "actual_date": now - timedelta(days=25),
                "status": "completed",
                "lead_auditor": "Dr. Natalie Wong",
                "audit_team": ["Dr. Natalie Wong", "James Bradford"],
                "findings_count": 3,
                "critical_findings": 0,
                "readiness_score_pct": 85.0,
                "recommendations": ["Enhance consent withdrawal documentation", "Update SAE narrative quality"],
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "MOCK-007",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "mock_type": "tabletop",
                "target_authority": InspectionAuthority.HEALTH_CANADA,
                "planned_date": now + timedelta(days=10),
                "actual_date": None,
                "status": "planned",
                "lead_auditor": "Dr. Rebecca Foster",
                "audit_team": ["Dr. Rebecca Foster", "Michelle Tremblay"],
                "findings_count": 0,
                "critical_findings": 0,
                "readiness_score_pct": None,
                "recommendations": [],
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "MOCK-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-106",
                "mock_type": "full",
                "target_authority": InspectionAuthority.PMDA,
                "planned_date": now - timedelta(days=155),
                "actual_date": now - timedelta(days=155),
                "status": "completed",
                "lead_auditor": "Dr. David Nakamura",
                "audit_team": ["Dr. David Nakamura", "Dr. Yuki Tanaka", "Haruki Sato"],
                "findings_count": 2,
                "critical_findings": 0,
                "readiness_score_pct": 90.0,
                "recommendations": ["Improve consent form translation QC", "Enhance concomitant medication documentation"],
                "created_at": now - timedelta(days=165),
            },
            {
                "id": "MOCK-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": None,
                "mock_type": "systems",
                "target_authority": InspectionAuthority.EMA,
                "planned_date": now - timedelta(days=170),
                "actual_date": now - timedelta(days=170),
                "status": "completed",
                "lead_auditor": "Dr. Gregory Harris",
                "audit_team": ["Dr. Gregory Harris", "Pierre Dubois"],
                "findings_count": 6,
                "critical_findings": 0,
                "readiness_score_pct": 78.0,
                "recommendations": ["Strengthen signal detection staffing", "Improve ICSR QC process", "Update PSMF"],
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "MOCK-010",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "mock_type": "focused",
                "target_authority": InspectionAuthority.FDA,
                "planned_date": now + timedelta(days=20),
                "actual_date": None,
                "status": "planned",
                "lead_auditor": "Dr. Jennifer Walsh",
                "audit_team": ["Dr. Jennifer Walsh"],
                "findings_count": 0,
                "critical_findings": 0,
                "readiness_score_pct": None,
                "recommendations": [],
                "created_at": now - timedelta(days=2),
            },
        ]

        for m in mock_inspections_data:
            self._mock_inspections[m["id"]] = MockInspection(**m)

        # --- 10 Readiness Assessments ---
        readiness_data = [
            {
                "id": "RA-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "target_authority": InspectionAuthority.FDA,
                "assessment_date": now - timedelta(days=125),
                "overall_score_pct": 88.5,
                "document_readiness_pct": 92.0,
                "process_readiness_pct": 85.0,
                "staff_readiness_pct": 90.0,
                "system_readiness_pct": 87.0,
                "gaps_identified": ["ICF tracking process needs improvement", "IP temperature monitoring gaps"],
                "remediation_plan": "Complete ICF tracking tool implementation by Week 4. Install redundant temperature sensors by Week 2.",
                "assessed_by": "Dr. Jennifer Walsh",
                "next_assessment_date": now - timedelta(days=95),
                "created_at": now - timedelta(days=125),
            },
            {
                "id": "RA-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "target_authority": InspectionAuthority.EMA,
                "assessment_date": now - timedelta(days=105),
                "overall_score_pct": 82.0,
                "document_readiness_pct": 80.0,
                "process_readiness_pct": 78.0,
                "staff_readiness_pct": 85.0,
                "system_readiness_pct": 85.0,
                "gaps_identified": ["SAE reporting delays", "TMF incomplete", "Delegation log outdated"],
                "remediation_plan": "Implement 24/7 SAE hotline. TMF gap analysis and filing sprint by Week 3.",
                "assessed_by": "Dr. Thomas Eriksson",
                "next_assessment_date": now - timedelta(days=75),
                "created_at": now - timedelta(days=105),
            },
            {
                "id": "RA-003",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "target_authority": InspectionAuthority.FDA,
                "assessment_date": now - timedelta(days=90),
                "overall_score_pct": 75.0,
                "document_readiness_pct": 78.0,
                "process_readiness_pct": 70.0,
                "staff_readiness_pct": 72.0,
                "system_readiness_pct": 80.0,
                "gaps_identified": ["EASI rater inter-reliability below threshold", "Consent form version control weak", "Source document organization poor"],
                "remediation_plan": "Mandatory EASI re-certification by Week 2. Consent version control audit. Source document reorganization.",
                "assessed_by": "Dr. Angela Martinez",
                "next_assessment_date": now - timedelta(days=60),
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "RA-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-105",
                "target_authority": InspectionAuthority.FDA,
                "assessment_date": now - timedelta(days=60),
                "overall_score_pct": 52.0,
                "document_readiness_pct": 45.0,
                "process_readiness_pct": 50.0,
                "staff_readiness_pct": 55.0,
                "system_readiness_pct": 58.0,
                "gaps_identified": ["Data integrity concerns", "Inadequate PI oversight", "Staff qualification gaps", "Source document missing"],
                "remediation_plan": "Urgent investigation initiated. Site placed on enhanced monitoring. PI remediation plan required.",
                "assessed_by": "Dr. Catherine Liu",
                "next_assessment_date": now - timedelta(days=30),
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "RA-005",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "target_authority": InspectionAuthority.FDA,
                "assessment_date": now - timedelta(days=35),
                "overall_score_pct": 91.5,
                "document_readiness_pct": 93.0,
                "process_readiness_pct": 90.0,
                "staff_readiness_pct": 92.0,
                "system_readiness_pct": 91.0,
                "gaps_identified": ["Minor RECIST documentation improvements needed"],
                "remediation_plan": "RECIST documentation SOP update. Radiology review training refresh.",
                "assessed_by": "Dr. Andrew Foster",
                "next_assessment_date": now - timedelta(days=5),
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "RA-006",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-108",
                "target_authority": InspectionAuthority.MHRA,
                "assessment_date": now - timedelta(days=20),
                "overall_score_pct": 85.0,
                "document_readiness_pct": 87.0,
                "process_readiness_pct": 83.0,
                "staff_readiness_pct": 86.0,
                "system_readiness_pct": 84.0,
                "gaps_identified": ["Consent withdrawal documentation improvement", "SAE narrative quality enhancement"],
                "remediation_plan": "Consent withdrawal checklist implementation. SAE narrative writing training session scheduled.",
                "assessed_by": "Dr. Natalie Wong",
                "next_assessment_date": now + timedelta(days=10),
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "RA-007",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "target_authority": InspectionAuthority.HEALTH_CANADA,
                "assessment_date": now - timedelta(days=8),
                "overall_score_pct": 79.0,
                "document_readiness_pct": 82.0,
                "process_readiness_pct": 76.0,
                "staff_readiness_pct": 80.0,
                "system_readiness_pct": 78.0,
                "gaps_identified": ["Safety signal documentation incomplete", "Training records need updating"],
                "remediation_plan": "Complete safety signal documentation by Week 2. Training records audit and update.",
                "assessed_by": "Dr. Rebecca Foster",
                "next_assessment_date": now + timedelta(days=22),
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "RA-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-106",
                "target_authority": InspectionAuthority.PMDA,
                "assessment_date": now - timedelta(days=150),
                "overall_score_pct": 90.0,
                "document_readiness_pct": 91.0,
                "process_readiness_pct": 88.0,
                "staff_readiness_pct": 92.0,
                "system_readiness_pct": 89.0,
                "gaps_identified": ["Translation QC process improvement", "Concomitant medication documentation"],
                "remediation_plan": "Back-translation verification process. Real-time medication entry at visits.",
                "assessed_by": "Dr. David Nakamura",
                "next_assessment_date": now - timedelta(days=120),
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "RA-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": None,
                "target_authority": InspectionAuthority.EMA,
                "assessment_date": now - timedelta(days=165),
                "overall_score_pct": 78.0,
                "document_readiness_pct": 80.0,
                "process_readiness_pct": 75.0,
                "staff_readiness_pct": 77.0,
                "system_readiness_pct": 80.0,
                "gaps_identified": ["Signal detection staffing", "ICSR QC process", "PSMF update needed"],
                "remediation_plan": "Hire 2 signal management specialists. Update ICSR QC checklist. PSMF revision by Month 2.",
                "assessed_by": "Dr. Gregory Harris",
                "next_assessment_date": now - timedelta(days=135),
                "created_at": now - timedelta(days=165),
            },
            {
                "id": "RA-010",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "target_authority": InspectionAuthority.FDA,
                "assessment_date": now - timedelta(days=95),
                "overall_score_pct": 93.0,
                "document_readiness_pct": 95.0,
                "process_readiness_pct": 91.0,
                "staff_readiness_pct": 94.0,
                "system_readiness_pct": 92.0,
                "gaps_identified": ["Minor documentation gaps in visit logs"],
                "remediation_plan": "Visit log review and completion. Ongoing monitoring.",
                "assessed_by": "Dr. Jennifer Walsh",
                "next_assessment_date": now - timedelta(days=65),
                "created_at": now - timedelta(days=95),
            },
        ]

        for r in readiness_data:
            self._readiness_assessments[r["id"]] = ReadinessAssessment(**r)

        # --- 12 Inspection Commitments ---
        commitments_data = [
            {
                "id": "CMT-001",
                "inspection_id": "INSP-001",
                "finding_id": "FND-001",
                "commitment_text": "Implement electronic ICF tracking system to ensure all consent forms are signed before any study procedures.",
                "authority": InspectionAuthority.FDA,
                "due_date": now - timedelta(days=25),
                "status": "completed",
                "responsible_person": "Dr. James Chen",
                "completed_date": now - timedelta(days=30),
                "evidence_reference": "ICF-TRACKER-IMPL-2024-001",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "CMT-002",
                "inspection_id": "INSP-001",
                "finding_id": "FND-002",
                "commitment_text": "Install redundant temperature monitoring sensors and update backup monitoring SOP.",
                "authority": InspectionAuthority.FDA,
                "due_date": now - timedelta(days=25),
                "status": "completed",
                "responsible_person": "Dr. James Chen",
                "completed_date": now - timedelta(days=28),
                "evidence_reference": "TEMP-MON-UPGRADE-2024-001",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "CMT-003",
                "inspection_id": "INSP-002",
                "finding_id": "FND-003",
                "commitment_text": "Establish 24/7 SAE reporting hotline and retrain all site staff on SAE reporting timelines.",
                "authority": InspectionAuthority.EMA,
                "due_date": now - timedelta(days=12),
                "status": "completed",
                "responsible_person": "Dr. Anna Schmidt",
                "completed_date": now - timedelta(days=15),
                "evidence_reference": "SAE-HOTLINE-2024-001",
                "created_at": now - timedelta(days=42),
            },
            {
                "id": "CMT-004",
                "inspection_id": "INSP-004",
                "finding_id": "FND-004",
                "commitment_text": "Complete mandatory re-certification for all EASI raters and implement quarterly inter-rater reliability testing.",
                "authority": InspectionAuthority.FDA,
                "due_date": now + timedelta(days=3),
                "status": "in_progress",
                "responsible_person": "Dr. Robert Williams",
                "completed_date": None,
                "evidence_reference": None,
                "created_at": now - timedelta(days=27),
            },
            {
                "id": "CMT-005",
                "inspection_id": "INSP-005",
                "finding_id": "FND-006",
                "commitment_text": "Terminate research coordinator. Initiate retrospective audit of all data entered by the coordinator. Report affected subjects to IRB and FDA.",
                "authority": InspectionAuthority.FDA,
                "due_date": now + timedelta(days=5),
                "status": "in_progress",
                "responsible_person": "Dr. Catherine Liu",
                "completed_date": None,
                "evidence_reference": None,
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "CMT-006",
                "inspection_id": "INSP-005",
                "finding_id": "FND-007",
                "commitment_text": "Implement mandatory PI co-signature requirement for all key data entries and weekly source data review.",
                "authority": InspectionAuthority.FDA,
                "due_date": now + timedelta(days=5),
                "status": "open",
                "responsible_person": "Dr. Catherine Liu",
                "completed_date": None,
                "evidence_reference": None,
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "CMT-007",
                "inspection_id": "INSP-009",
                "finding_id": "FND-010",
                "commitment_text": "Hire 2 additional signal management specialists and implement automated signal screening tool.",
                "authority": InspectionAuthority.EMA,
                "due_date": now - timedelta(days=70),
                "status": "completed",
                "responsible_person": "Dr. Gregory Harris",
                "completed_date": now - timedelta(days=75),
                "evidence_reference": "SIGNAL-MGMT-HIRE-2024",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "CMT-008",
                "inspection_id": "INSP-009",
                "finding_id": "FND-011",
                "commitment_text": "Update ICSR quality review checklist to include MedDRA coding verification. Complete retrospective review of all ICSRs.",
                "authority": InspectionAuthority.EMA,
                "due_date": now - timedelta(days=70),
                "status": "completed",
                "responsible_person": "Dr. Gregory Harris",
                "completed_date": now - timedelta(days=72),
                "evidence_reference": "ICSR-QC-UPDATE-2024",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "CMT-009",
                "inspection_id": "INSP-005",
                "finding_id": "FND-014",
                "commitment_text": "Reconstruct source documents from hospital medical records where available. Document reconstruction process and notify IRB.",
                "authority": InspectionAuthority.FDA,
                "due_date": now + timedelta(days=15),
                "status": "open",
                "responsible_person": "Dr. Catherine Liu",
                "completed_date": None,
                "evidence_reference": None,
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "CMT-010",
                "inspection_id": "INSP-004",
                "finding_id": "FND-005",
                "commitment_text": "Implement consent form version tracking system and immediate distribution protocol for updated consent forms.",
                "authority": InspectionAuthority.FDA,
                "due_date": now + timedelta(days=3),
                "status": "in_progress",
                "responsible_person": "Dr. Robert Williams",
                "completed_date": None,
                "evidence_reference": None,
                "created_at": now - timedelta(days=27),
            },
            {
                "id": "CMT-011",
                "inspection_id": "INSP-002",
                "finding_id": "FND-015",
                "commitment_text": "Implement monitoring report upload deadline tracking with automated reminders.",
                "authority": InspectionAuthority.EMA,
                "due_date": now - timedelta(days=12),
                "status": "completed",
                "responsible_person": "Dr. Anna Schmidt",
                "completed_date": now - timedelta(days=14),
                "evidence_reference": "TMF-UPLOAD-TRACKER-2024",
                "created_at": now - timedelta(days=42),
            },
            {
                "id": "CMT-012",
                "inspection_id": "INSP-012",
                "finding_id": "FND-012",
                "commitment_text": "Implement automated visit window deviation detection in EDC and protocol deviation training for all staff.",
                "authority": InspectionAuthority.FDA,
                "due_date": now - timedelta(days=160),
                "status": "completed",
                "responsible_person": "Dr. Catherine Liu",
                "completed_date": now - timedelta(days=165),
                "evidence_reference": "VISIT-WINDOW-EDC-2023",
                "created_at": now - timedelta(days=190),
            },
        ]

        for c in commitments_data:
            self._commitments[c["id"]] = InspectionCommitment(**c)

    # ------------------------------------------------------------------
    # Inspection CRUD
    # ------------------------------------------------------------------

    def list_inspections(
        self,
        *,
        trial_id: str | None = None,
        status: InspectionStatus | None = None,
        authority: InspectionAuthority | None = None,
        inspection_type: InspectionType | None = None,
    ) -> list[Inspection]:
        """List inspections with optional filters."""
        with self._lock:
            result = list(self._inspections.values())

        if trial_id is not None:
            result = [i for i in result if i.trial_id == trial_id]
        if status is not None:
            result = [i for i in result if i.status == status]
        if authority is not None:
            result = [i for i in result if i.authority == authority]
        if inspection_type is not None:
            result = [i for i in result if i.inspection_type == inspection_type]

        return sorted(result, key=lambda i: i.created_at, reverse=True)

    def get_inspection(self, inspection_id: str) -> Inspection | None:
        """Get a single inspection by ID."""
        with self._lock:
            return self._inspections.get(inspection_id)

    def create_inspection(self, payload: InspectionCreate) -> Inspection:
        """Create a new inspection."""
        now = datetime.now(timezone.utc)
        inspection_id = f"INSP-{uuid4().hex[:8].upper()}"
        inspection = Inspection(
            id=inspection_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            inspection_type=payload.inspection_type,
            authority=payload.authority,
            status=InspectionStatus.PLANNED,
            title=payload.title,
            scope=payload.scope,
            sponsor_lead=payload.sponsor_lead,
            site_contact=payload.site_contact,
            created_at=now,
        )
        with self._lock:
            self._inspections[inspection_id] = inspection
        logger.info("Created inspection %s: %s", inspection_id, payload.title)
        return inspection

    def update_inspection(
        self, inspection_id: str, payload: InspectionUpdate
    ) -> Inspection | None:
        """Update an existing inspection."""
        with self._lock:
            existing = self._inspections.get(inspection_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = Inspection(**data)
            self._inspections[inspection_id] = updated
        return updated

    def delete_inspection(self, inspection_id: str) -> bool:
        """Delete an inspection. Returns True if deleted."""
        with self._lock:
            if inspection_id in self._inspections:
                del self._inspections[inspection_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Finding CRUD
    # ------------------------------------------------------------------

    def list_findings(
        self,
        *,
        inspection_id: str | None = None,
        severity: FindingSeverity | None = None,
        classification: FindingClassification | None = None,
    ) -> list[InspectionFinding]:
        """List findings with optional filters."""
        with self._lock:
            result = list(self._findings.values())

        if inspection_id is not None:
            result = [f for f in result if f.inspection_id == inspection_id]
        if severity is not None:
            result = [f for f in result if f.severity == severity]
        if classification is not None:
            result = [f for f in result if f.classification == classification]

        return sorted(result, key=lambda f: f.created_at, reverse=True)

    def get_finding(self, finding_id: str) -> InspectionFinding | None:
        """Get a single finding by ID."""
        with self._lock:
            return self._findings.get(finding_id)

    def create_finding(self, payload: InspectionFindingCreate) -> InspectionFinding:
        """Create a new inspection finding."""
        now = datetime.now(timezone.utc)
        finding_id = f"FND-{uuid4().hex[:8].upper()}"
        finding = InspectionFinding(
            id=finding_id,
            inspection_id=payload.inspection_id,
            finding_number=payload.finding_number,
            severity=payload.severity,
            classification=payload.classification,
            description=payload.description,
            regulatory_reference=payload.regulatory_reference,
            area=payload.area,
            assigned_to=payload.assigned_to,
            created_at=now,
        )
        with self._lock:
            self._findings[finding_id] = finding
        logger.info("Created finding %s for inspection %s", finding_id, payload.inspection_id)
        return finding

    def update_finding(
        self, finding_id: str, payload: InspectionFindingUpdate
    ) -> InspectionFinding | None:
        """Update an existing finding."""
        with self._lock:
            existing = self._findings.get(finding_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = InspectionFinding(**data)
            self._findings[finding_id] = updated
        return updated

    def delete_finding(self, finding_id: str) -> bool:
        """Delete a finding. Returns True if deleted."""
        with self._lock:
            if finding_id in self._findings:
                del self._findings[finding_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Mock Inspection CRUD
    # ------------------------------------------------------------------

    def list_mock_inspections(
        self,
        *,
        trial_id: str | None = None,
        status: str | None = None,
    ) -> list[MockInspection]:
        """List mock inspections with optional filters."""
        with self._lock:
            result = list(self._mock_inspections.values())

        if trial_id is not None:
            result = [m for m in result if m.trial_id == trial_id]
        if status is not None:
            result = [m for m in result if m.status == status]

        return sorted(result, key=lambda m: m.created_at, reverse=True)

    def get_mock_inspection(self, mock_id: str) -> MockInspection | None:
        """Get a single mock inspection by ID."""
        with self._lock:
            return self._mock_inspections.get(mock_id)

    def create_mock_inspection(self, payload: MockInspectionCreate) -> MockInspection:
        """Create a new mock inspection."""
        now = datetime.now(timezone.utc)
        mock_id = f"MOCK-{uuid4().hex[:8].upper()}"
        mock = MockInspection(
            id=mock_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            mock_type=payload.mock_type,
            target_authority=payload.target_authority,
            planned_date=payload.planned_date,
            lead_auditor=payload.lead_auditor,
            created_at=now,
        )
        with self._lock:
            self._mock_inspections[mock_id] = mock
        logger.info("Created mock inspection %s for trial %s", mock_id, payload.trial_id)
        return mock

    def update_mock_inspection(
        self, mock_id: str, payload: MockInspectionUpdate
    ) -> MockInspection | None:
        """Update an existing mock inspection."""
        with self._lock:
            existing = self._mock_inspections.get(mock_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = MockInspection(**data)
            self._mock_inspections[mock_id] = updated
        return updated

    def delete_mock_inspection(self, mock_id: str) -> bool:
        """Delete a mock inspection. Returns True if deleted."""
        with self._lock:
            if mock_id in self._mock_inspections:
                del self._mock_inspections[mock_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Readiness Assessment CRUD
    # ------------------------------------------------------------------

    def list_readiness_assessments(
        self,
        *,
        trial_id: str | None = None,
        target_authority: InspectionAuthority | None = None,
    ) -> list[ReadinessAssessment]:
        """List readiness assessments with optional filters."""
        with self._lock:
            result = list(self._readiness_assessments.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if target_authority is not None:
            result = [r for r in result if r.target_authority == target_authority]

        return sorted(result, key=lambda r: r.assessment_date, reverse=True)

    def get_readiness_assessment(self, assessment_id: str) -> ReadinessAssessment | None:
        """Get a single readiness assessment by ID."""
        with self._lock:
            return self._readiness_assessments.get(assessment_id)

    def create_readiness_assessment(self, payload: ReadinessAssessmentCreate) -> ReadinessAssessment:
        """Create a new readiness assessment."""
        now = datetime.now(timezone.utc)
        assessment_id = f"RA-{uuid4().hex[:8].upper()}"
        assessment = ReadinessAssessment(
            id=assessment_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            target_authority=payload.target_authority,
            assessment_date=now,
            assessed_by=payload.assessed_by,
            created_at=now,
        )
        with self._lock:
            self._readiness_assessments[assessment_id] = assessment
        logger.info("Created readiness assessment %s for trial %s", assessment_id, payload.trial_id)
        return assessment

    def update_readiness_assessment(
        self, assessment_id: str, payload: ReadinessAssessmentUpdate
    ) -> ReadinessAssessment | None:
        """Update an existing readiness assessment."""
        with self._lock:
            existing = self._readiness_assessments.get(assessment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ReadinessAssessment(**data)
            self._readiness_assessments[assessment_id] = updated
        return updated

    def delete_readiness_assessment(self, assessment_id: str) -> bool:
        """Delete a readiness assessment. Returns True if deleted."""
        with self._lock:
            if assessment_id in self._readiness_assessments:
                del self._readiness_assessments[assessment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Commitment CRUD
    # ------------------------------------------------------------------

    def list_commitments(
        self,
        *,
        inspection_id: str | None = None,
        status: str | None = None,
    ) -> list[InspectionCommitment]:
        """List commitments with optional filters."""
        with self._lock:
            result = list(self._commitments.values())

        if inspection_id is not None:
            result = [c for c in result if c.inspection_id == inspection_id]
        if status is not None:
            result = [c for c in result if c.status == status]

        return sorted(result, key=lambda c: c.due_date, reverse=True)

    def get_commitment(self, commitment_id: str) -> InspectionCommitment | None:
        """Get a single commitment by ID."""
        with self._lock:
            return self._commitments.get(commitment_id)

    def create_commitment(self, payload: InspectionCommitmentCreate) -> InspectionCommitment:
        """Create a new inspection commitment."""
        now = datetime.now(timezone.utc)
        commitment_id = f"CMT-{uuid4().hex[:8].upper()}"
        commitment = InspectionCommitment(
            id=commitment_id,
            inspection_id=payload.inspection_id,
            finding_id=payload.finding_id,
            commitment_text=payload.commitment_text,
            authority=payload.authority,
            due_date=payload.due_date,
            responsible_person=payload.responsible_person,
            created_at=now,
        )
        with self._lock:
            self._commitments[commitment_id] = commitment
        logger.info("Created commitment %s for inspection %s", commitment_id, payload.inspection_id)
        return commitment

    def update_commitment(
        self, commitment_id: str, payload: InspectionCommitmentUpdate
    ) -> InspectionCommitment | None:
        """Update an existing commitment."""
        with self._lock:
            existing = self._commitments.get(commitment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            # Auto-set completed_date when status changes to completed
            if updates.get("status") == "completed" and existing.completed_date is None:
                data["completed_date"] = datetime.now(timezone.utc)
            updated = InspectionCommitment(**data)
            self._commitments[commitment_id] = updated
        return updated

    def delete_commitment(self, commitment_id: str) -> bool:
        """Delete a commitment. Returns True if deleted."""
        with self._lock:
            if commitment_id in self._commitments:
                del self._commitments[commitment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> RegulatoryInspectionMetrics:
        """Compute aggregated regulatory inspection metrics."""
        with self._lock:
            inspections = list(self._inspections.values())
            findings = list(self._findings.values())
            mock_inspections = list(self._mock_inspections.values())
            readiness_assessments = list(self._readiness_assessments.values())
            commitments = list(self._commitments.values())

        # Filter by trial if specified
        if trial_id is not None:
            inspections = [i for i in inspections if i.trial_id == trial_id]
            inspection_ids = {i.id for i in inspections}
            findings = [f for f in findings if f.inspection_id in inspection_ids]
            mock_inspections = [m for m in mock_inspections if m.trial_id == trial_id]
            readiness_assessments = [r for r in readiness_assessments if r.trial_id == trial_id]
            commitments = [c for c in commitments if c.inspection_id in inspection_ids]

        # Inspections by type
        inspections_by_type: dict[str, int] = {}
        for i in inspections:
            key = i.inspection_type.value
            inspections_by_type[key] = inspections_by_type.get(key, 0) + 1

        # Inspections by authority
        inspections_by_authority: dict[str, int] = {}
        for i in inspections:
            key = i.authority.value
            inspections_by_authority[key] = inspections_by_authority.get(key, 0) + 1

        # Inspections by status
        inspections_by_status: dict[str, int] = {}
        for i in inspections:
            key = i.status.value
            inspections_by_status[key] = inspections_by_status.get(key, 0) + 1

        # Findings by severity
        findings_by_severity: dict[str, int] = {}
        for f in findings:
            key = f.severity.value
            findings_by_severity[key] = findings_by_severity.get(key, 0) + 1

        # Open findings
        open_findings = sum(1 for f in findings if f.response_status == "pending")

        # Average readiness score
        completed_assessments = [
            r for r in readiness_assessments if r.overall_score_pct > 0
        ]
        avg_readiness = 0.0
        if completed_assessments:
            avg_readiness = round(
                sum(r.overall_score_pct for r in completed_assessments) / len(completed_assessments),
                1,
            )

        # Overdue commitments
        now = datetime.now(timezone.utc)
        overdue_commitments = sum(
            1 for c in commitments
            if c.status not in ("completed",) and c.due_date < now
        )

        return RegulatoryInspectionMetrics(
            total_inspections=len(inspections),
            inspections_by_type=inspections_by_type,
            inspections_by_authority=inspections_by_authority,
            inspections_by_status=inspections_by_status,
            total_findings=len(findings),
            findings_by_severity=findings_by_severity,
            open_findings=open_findings,
            total_mock_inspections=len(mock_inspections),
            avg_readiness_score_pct=avg_readiness,
            total_commitments=len(commitments),
            overdue_commitments=overdue_commitments,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: RegulatoryInspectionService | None = None
_instance_lock = threading.Lock()


def get_regulatory_inspection_service() -> RegulatoryInspectionService:
    """Return the singleton RegulatoryInspectionService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = RegulatoryInspectionService()
    return _instance


def reset_regulatory_inspection_service() -> RegulatoryInspectionService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = RegulatoryInspectionService()
    return _instance
