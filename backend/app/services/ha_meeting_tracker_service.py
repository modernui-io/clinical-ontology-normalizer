"""Health Authority Meeting Tracker (HA-MEET) Service.

Manages health authority interactions: meeting requests, briefing document
preparation, meeting minutes, action item tracking, commitment management,
and HA meeting operational metrics.

Usage:
    from app.services.ha_meeting_tracker_service import (
        get_ha_meeting_tracker_service,
    )

    svc = get_ha_meeting_tracker_service()
    meetings = svc.list_meetings()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.ha_meeting_tracker import (
    ActionPriority,
    BriefingDocument,
    BriefingDocumentCreate,
    BriefingDocumentUpdate,
    CommitmentStatus,
    HACommitment,
    HACommitmentCreate,
    HACommitmentUpdate,
    HAMeeting,
    HAMeetingCreate,
    HAMeetingMetrics,
    HAMeetingUpdate,
    HealthAuthority,
    MeetingActionItem,
    MeetingActionItemCreate,
    MeetingActionItemUpdate,
    MeetingMinutes,
    MeetingMinutesCreate,
    MeetingMinutesUpdate,
    MeetingStatus,
    MeetingType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class HAMeetingTrackerService:
    """In-memory Health Authority Meeting Tracker engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._meetings: dict[str, HAMeeting] = {}
        self._briefing_docs: dict[str, BriefingDocument] = {}
        self._minutes: dict[str, MeetingMinutes] = {}
        self._action_items: dict[str, MeetingActionItem] = {}
        self._commitments: dict[str, HACommitment] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic HA meeting data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 HA Meetings ---
        meetings_data = [
            # EYLEA meetings
            {
                "id": "HAM-001",
                "trial_id": EYLEA_TRIAL,
                "meeting_type": MeetingType.PRE_BLA,
                "health_authority": HealthAuthority.FDA,
                "status": MeetingStatus.COMPLETED,
                "title": "EYLEA HD Pre-BLA Meeting with FDA CDER",
                "objective": "Discuss BLA submission strategy for EYLEA HD 8mg intravitreal injection",
                "request_date": now - timedelta(days=180),
                "scheduled_date": now - timedelta(days=120),
                "actual_date": now - timedelta(days=120),
                "duration_minutes": 60,
                "format": "in_person",
                "key_questions": [
                    "Is the proposed clinical package sufficient for BLA submission?",
                    "Are additional nonclinical studies required for the HD formulation?",
                    "What is the recommended approach for the CMC section?",
                ],
                "attendees": ["Dr. Sarah Kim", "Dr. Michael Chen", "FDA CDER Division Director"],
                "regulatory_lead": "Dr. Sarah Kim",
                "medical_lead": "Dr. Michael Chen",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "HAM-002",
                "trial_id": EYLEA_TRIAL,
                "meeting_type": MeetingType.TYPE_B,
                "health_authority": HealthAuthority.FDA,
                "status": MeetingStatus.COMPLETED,
                "title": "EYLEA HD Type B Meeting - CMC Discussion",
                "objective": "Resolve CMC questions for EYLEA HD manufacturing process",
                "request_date": now - timedelta(days=150),
                "scheduled_date": now - timedelta(days=90),
                "actual_date": now - timedelta(days=90),
                "duration_minutes": 90,
                "format": "teleconference",
                "key_questions": [
                    "Is the proposed manufacturing process acceptable?",
                    "What stability data are required at submission?",
                ],
                "attendees": ["Dr. Sarah Kim", "CMC Lead", "FDA Reviewer"],
                "regulatory_lead": "Dr. Sarah Kim",
                "medical_lead": None,
                "created_at": now - timedelta(days=160),
            },
            {
                "id": "HAM-003",
                "trial_id": EYLEA_TRIAL,
                "meeting_type": MeetingType.SCIENTIFIC_ADVICE,
                "health_authority": HealthAuthority.EMA,
                "status": MeetingStatus.SCHEDULED,
                "title": "EYLEA HD EMA Scientific Advice Procedure",
                "objective": "Obtain EMA scientific advice on European marketing authorization strategy",
                "request_date": now - timedelta(days=60),
                "scheduled_date": now + timedelta(days=30),
                "actual_date": None,
                "duration_minutes": 120,
                "format": "in_person",
                "key_questions": [
                    "Is the Phase 3 data package acceptable for EU MAA?",
                    "Are bridging studies required for EU populations?",
                    "What is the recommended pediatric investigation plan?",
                ],
                "attendees": ["Dr. Sarah Kim", "EU Regulatory Affairs Lead"],
                "regulatory_lead": "Dr. Sarah Kim",
                "medical_lead": "Dr. James Rodriguez",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "HAM-004",
                "trial_id": EYLEA_TRIAL,
                "meeting_type": MeetingType.TYPE_A,
                "health_authority": HealthAuthority.FDA,
                "status": MeetingStatus.BRIEFING_DOC_SUBMITTED,
                "title": "EYLEA HD Type A Safety Meeting",
                "objective": "Discuss post-marketing safety signal in elderly patients",
                "request_date": now - timedelta(days=30),
                "scheduled_date": now + timedelta(days=15),
                "actual_date": None,
                "duration_minutes": 60,
                "format": "teleconference",
                "key_questions": [
                    "Does the safety signal warrant label changes?",
                    "What additional monitoring is recommended?",
                ],
                "attendees": ["Dr. Sarah Kim", "Safety Officer"],
                "regulatory_lead": "Dr. Sarah Kim",
                "medical_lead": "Dr. Elizabeth Chen",
                "created_at": now - timedelta(days=35),
            },
            # DUPIXENT meetings
            {
                "id": "HAM-005",
                "trial_id": DUPIXENT_TRIAL,
                "meeting_type": MeetingType.END_OF_PHASE_2,
                "health_authority": HealthAuthority.FDA,
                "status": MeetingStatus.COMPLETED,
                "title": "Dupixent COPD End-of-Phase 2 Meeting",
                "objective": "Discuss Phase 3 trial design for Dupixent in COPD with type 2 inflammation",
                "request_date": now - timedelta(days=200),
                "scheduled_date": now - timedelta(days=140),
                "actual_date": now - timedelta(days=140),
                "duration_minutes": 90,
                "format": "in_person",
                "key_questions": [
                    "Is the proposed Phase 3 design adequate for NDA submission?",
                    "What is the recommended primary endpoint?",
                    "Are biomarker-based enrichment criteria acceptable?",
                    "What safety database size is required?",
                ],
                "attendees": ["Dr. Laura Martinez", "Dr. David Park", "FDA CDER Reviewer"],
                "regulatory_lead": "Dr. Laura Martinez",
                "medical_lead": "Dr. David Park",
                "created_at": now - timedelta(days=220),
            },
            {
                "id": "HAM-006",
                "trial_id": DUPIXENT_TRIAL,
                "meeting_type": MeetingType.SCIENTIFIC_ADVICE,
                "health_authority": HealthAuthority.EMA,
                "status": MeetingStatus.COMPLETED,
                "title": "Dupixent EMA Scientific Advice - Pediatric Atopic Dermatitis",
                "objective": "Discuss pediatric development plan for Dupixent in AD ages 6 months to 5 years",
                "request_date": now - timedelta(days=160),
                "scheduled_date": now - timedelta(days=100),
                "actual_date": now - timedelta(days=100),
                "duration_minutes": 60,
                "format": "teleconference",
                "key_questions": [
                    "Is the proposed dosing regimen acceptable for the pediatric population?",
                    "What safety monitoring is required for this age group?",
                ],
                "attendees": ["Dr. Laura Martinez", "EMA Pediatric Committee"],
                "regulatory_lead": "Dr. Laura Martinez",
                "medical_lead": "Dr. Angela Martinez",
                "created_at": now - timedelta(days=170),
            },
            {
                "id": "HAM-007",
                "trial_id": DUPIXENT_TRIAL,
                "meeting_type": MeetingType.TYPE_C,
                "health_authority": HealthAuthority.FDA,
                "status": MeetingStatus.REQUEST_SUBMITTED,
                "title": "Dupixent Type C Meeting - Label Expansion Strategy",
                "objective": "Discuss sNDA strategy for adding COPD indication to Dupixent label",
                "request_date": now - timedelta(days=20),
                "scheduled_date": None,
                "actual_date": None,
                "duration_minutes": 60,
                "format": "teleconference",
                "key_questions": [
                    "Can COPD and existing indications share a single NDA?",
                    "What post-marketing commitments are anticipated?",
                ],
                "attendees": ["Dr. Laura Martinez"],
                "regulatory_lead": "Dr. Laura Martinez",
                "medical_lead": None,
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "HAM-008",
                "trial_id": DUPIXENT_TRIAL,
                "meeting_type": MeetingType.PROTOCOL_ASSISTANCE,
                "health_authority": HealthAuthority.PMDA,
                "status": MeetingStatus.PLANNING,
                "title": "Dupixent PMDA Protocol Assistance - Japan Phase 3",
                "objective": "Discuss Japan-specific Phase 3 requirements for Dupixent in COPD",
                "request_date": None,
                "scheduled_date": None,
                "actual_date": None,
                "duration_minutes": 60,
                "format": "teleconference",
                "key_questions": [
                    "Are Japanese bridging studies required?",
                    "What is the acceptable comparator for Japan?",
                ],
                "attendees": [],
                "regulatory_lead": "Dr. Yuki Tanaka",
                "medical_lead": None,
                "created_at": now - timedelta(days=10),
            },
            # LIBTAYO meetings
            {
                "id": "HAM-009",
                "trial_id": LIBTAYO_TRIAL,
                "meeting_type": MeetingType.PRE_NDA,
                "health_authority": HealthAuthority.FDA,
                "status": MeetingStatus.COMPLETED,
                "title": "Libtayo Pre-NDA Meeting - Advanced BCC Indication",
                "objective": "Discuss NDA submission strategy for Libtayo in advanced basal cell carcinoma",
                "request_date": now - timedelta(days=250),
                "scheduled_date": now - timedelta(days=190),
                "actual_date": now - timedelta(days=190),
                "duration_minutes": 90,
                "format": "in_person",
                "key_questions": [
                    "Is the single-arm trial design sufficient for accelerated approval?",
                    "What confirmatory study commitments are expected?",
                    "Is the ORR endpoint with duration of response sufficient?",
                ],
                "attendees": ["Dr. Catherine Liu", "Dr. Andrew Foster", "FDA CDER Oncology Division"],
                "regulatory_lead": "Dr. Catherine Liu",
                "medical_lead": "Dr. Andrew Foster",
                "created_at": now - timedelta(days=260),
            },
            {
                "id": "HAM-010",
                "trial_id": LIBTAYO_TRIAL,
                "meeting_type": MeetingType.TYPE_B,
                "health_authority": HealthAuthority.FDA,
                "status": MeetingStatus.COMPLETED,
                "title": "Libtayo Type B Meeting - NSCLC Combination Therapy",
                "objective": "Discuss Phase 3 design for Libtayo + chemotherapy in first-line NSCLC",
                "request_date": now - timedelta(days=130),
                "scheduled_date": now - timedelta(days=70),
                "actual_date": now - timedelta(days=70),
                "duration_minutes": 90,
                "format": "teleconference",
                "key_questions": [
                    "Is the proposed combination regimen acceptable?",
                    "What is the recommended primary endpoint for the combination study?",
                    "Are there specific biomarker requirements for patient selection?",
                ],
                "attendees": ["Dr. Catherine Liu", "Dr. Andrew Foster", "FDA Reviewer"],
                "regulatory_lead": "Dr. Catherine Liu",
                "medical_lead": "Dr. Andrew Foster",
                "created_at": now - timedelta(days=140),
            },
            {
                "id": "HAM-011",
                "trial_id": LIBTAYO_TRIAL,
                "meeting_type": MeetingType.SCIENTIFIC_ADVICE,
                "health_authority": HealthAuthority.MHRA,
                "status": MeetingStatus.SCHEDULED,
                "title": "Libtayo MHRA Scientific Advice - UK Registration Strategy",
                "objective": "Discuss UK-specific registration strategy post-Brexit for Libtayo indications",
                "request_date": now - timedelta(days=45),
                "scheduled_date": now + timedelta(days=20),
                "actual_date": None,
                "duration_minutes": 60,
                "format": "teleconference",
                "key_questions": [
                    "What data package is required for UK MHRA approval?",
                    "Can the EU MAA dossier be leveraged?",
                ],
                "attendees": ["Dr. Catherine Liu", "UK Regulatory Affairs"],
                "regulatory_lead": "Dr. Catherine Liu",
                "medical_lead": None,
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "HAM-012",
                "trial_id": LIBTAYO_TRIAL,
                "meeting_type": MeetingType.PEDIATRIC,
                "health_authority": HealthAuthority.FDA,
                "status": MeetingStatus.PLANNING,
                "title": "Libtayo Pediatric Study Plan Discussion",
                "objective": "Discuss pediatric development requirements for Libtayo under PREA",
                "request_date": None,
                "scheduled_date": None,
                "actual_date": None,
                "duration_minutes": 60,
                "format": "teleconference",
                "key_questions": [
                    "What pediatric indications should be studied?",
                    "What are the timing requirements for pediatric studies?",
                ],
                "attendees": [],
                "regulatory_lead": "Dr. Catherine Liu",
                "medical_lead": "Dr. Natalie Wong",
                "created_at": now - timedelta(days=15),
            },
        ]

        for m in meetings_data:
            self._meetings[m["id"]] = HAMeeting(**m)

        # --- 12 Briefing Documents ---
        briefing_docs_data = [
            {"id": "BD-001", "meeting_id": "HAM-001", "title": "EYLEA HD Pre-BLA Briefing Document", "version": "2.0", "page_count": 145, "sections": ["Executive Summary", "Clinical Efficacy", "Clinical Safety", "CMC Overview", "Proposed Labeling"], "status": "approved", "author": "Dr. Sarah Kim", "reviewer": "VP Regulatory Affairs", "approved_date": now - timedelta(days=130), "submission_date": now - timedelta(days=125), "ha_receipt_date": now - timedelta(days=124), "created_at": now - timedelta(days=150)},
            {"id": "BD-002", "meeting_id": "HAM-002", "title": "EYLEA HD CMC Briefing Document", "version": "1.1", "page_count": 78, "sections": ["Manufacturing Process", "Analytical Methods", "Stability Data", "Container Closure"], "status": "approved", "author": "CMC Lead", "reviewer": "Dr. Sarah Kim", "approved_date": now - timedelta(days=95), "submission_date": now - timedelta(days=93), "ha_receipt_date": now - timedelta(days=92), "created_at": now - timedelta(days=110)},
            {"id": "BD-003", "meeting_id": "HAM-003", "title": "EYLEA HD EMA Scientific Advice Briefing Book", "version": "1.0", "page_count": 120, "sections": ["Clinical Development Plan", "EU Regulatory Strategy", "Pediatric Investigation Plan"], "status": "draft", "author": "EU Regulatory Affairs Lead", "reviewer": None, "approved_date": None, "submission_date": None, "ha_receipt_date": None, "created_at": now - timedelta(days=40)},
            {"id": "BD-004", "meeting_id": "HAM-004", "title": "EYLEA HD Safety Signal Assessment Package", "version": "1.0", "page_count": 55, "sections": ["Signal Detection", "Case Narratives", "Aggregate Analysis", "Proposed Risk Minimization"], "status": "submitted", "author": "Safety Officer", "reviewer": "Dr. Sarah Kim", "approved_date": now - timedelta(days=18), "submission_date": now - timedelta(days=16), "ha_receipt_date": now - timedelta(days=15), "created_at": now - timedelta(days=28)},
            {"id": "BD-005", "meeting_id": "HAM-005", "title": "Dupixent COPD End-of-Phase 2 Briefing Document", "version": "3.0", "page_count": 180, "sections": ["Phase 2 Results Summary", "Proposed Phase 3 Design", "Biomarker Strategy", "Statistical Analysis Plan"], "status": "approved", "author": "Dr. Laura Martinez", "reviewer": "Chief Medical Officer", "approved_date": now - timedelta(days=145), "submission_date": now - timedelta(days=143), "ha_receipt_date": now - timedelta(days=142), "created_at": now - timedelta(days=170)},
            {"id": "BD-006", "meeting_id": "HAM-006", "title": "Dupixent Pediatric AD Scientific Advice Document", "version": "1.2", "page_count": 95, "sections": ["Pediatric Development Rationale", "Dosing Justification", "Safety Database", "PK Modeling"], "status": "approved", "author": "Dr. Laura Martinez", "reviewer": "Pediatric Expert", "approved_date": now - timedelta(days=105), "submission_date": now - timedelta(days=103), "ha_receipt_date": now - timedelta(days=102), "created_at": now - timedelta(days=130)},
            {"id": "BD-007", "meeting_id": "HAM-009", "title": "Libtayo Pre-NDA Briefing Document - Advanced BCC", "version": "2.1", "page_count": 160, "sections": ["Executive Summary", "Clinical Efficacy", "Clinical Safety", "Benefit-Risk Assessment", "Proposed Labeling"], "status": "approved", "author": "Dr. Catherine Liu", "reviewer": "VP Oncology", "approved_date": now - timedelta(days=195), "submission_date": now - timedelta(days=193), "ha_receipt_date": now - timedelta(days=192), "created_at": now - timedelta(days=220)},
            {"id": "BD-008", "meeting_id": "HAM-010", "title": "Libtayo NSCLC Combination Therapy Briefing Package", "version": "1.0", "page_count": 110, "sections": ["Combination Rationale", "Preclinical Data", "Phase 2 Efficacy", "Proposed Phase 3 Design"], "status": "approved", "author": "Dr. Andrew Foster", "reviewer": "Dr. Catherine Liu", "approved_date": now - timedelta(days=75), "submission_date": now - timedelta(days=73), "ha_receipt_date": now - timedelta(days=72), "created_at": now - timedelta(days=100)},
            {"id": "BD-009", "meeting_id": "HAM-011", "title": "Libtayo MHRA Registration Briefing Document", "version": "0.5", "page_count": 0, "sections": ["UK Regulatory Landscape", "Data Package Summary"], "status": "draft", "author": "UK Regulatory Affairs", "reviewer": None, "approved_date": None, "submission_date": None, "ha_receipt_date": None, "created_at": now - timedelta(days=30)},
            {"id": "BD-010", "meeting_id": "HAM-001", "title": "EYLEA HD Pre-BLA Appendix - Pharmacokinetics", "version": "1.0", "page_count": 42, "sections": ["PK Summary", "Population PK Analysis", "Exposure-Response"], "status": "approved", "author": "PK Lead", "reviewer": "Dr. Sarah Kim", "approved_date": now - timedelta(days=128), "submission_date": now - timedelta(days=125), "ha_receipt_date": now - timedelta(days=124), "created_at": now - timedelta(days=145)},
            {"id": "BD-011", "meeting_id": "HAM-005", "title": "Dupixent COPD Biomarker Appendix", "version": "1.1", "page_count": 65, "sections": ["Biomarker Validation", "Enrichment Criteria", "Companion Diagnostic"], "status": "approved", "author": "Biomarker Lead", "reviewer": "Dr. David Park", "approved_date": now - timedelta(days=143), "submission_date": now - timedelta(days=143), "ha_receipt_date": now - timedelta(days=142), "created_at": now - timedelta(days=165)},
            {"id": "BD-012", "meeting_id": "HAM-009", "title": "Libtayo BCC Real-World Evidence Supplement", "version": "1.0", "page_count": 38, "sections": ["RWE Methodology", "Patient Demographics", "Treatment Outcomes"], "status": "approved", "author": "RWE Lead", "reviewer": "Dr. Catherine Liu", "approved_date": now - timedelta(days=192), "submission_date": now - timedelta(days=193), "ha_receipt_date": now - timedelta(days=192), "created_at": now - timedelta(days=210)},
        ]

        for bd in briefing_docs_data:
            self._briefing_docs[bd["id"]] = BriefingDocument(**bd)

        # --- 10 Meeting Minutes ---
        minutes_data = [
            {"id": "MIN-001", "meeting_id": "HAM-001", "summary": "FDA indicated the clinical package for EYLEA HD is generally acceptable for BLA submission. Agency recommended additional 6-month stability data for the HD formulation. No additional nonclinical studies required.", "key_outcomes": ["BLA package accepted in principle", "Additional stability data requested", "No nonclinical studies required"], "ha_feedback": "Positive overall. FDA receptive to HD formulation approach.", "agreements": ["Submission target Q2 2026", "Stability data to be provided as amendment"], "disagreements": [], "recorded_by": "Dr. Sarah Kim", "approved_by": "VP Regulatory Affairs", "approved_date": now - timedelta(days=115), "created_at": now - timedelta(days=118)},
            {"id": "MIN-002", "meeting_id": "HAM-002", "summary": "CMC discussion focused on manufacturing process validation. FDA agreed proposed process is acceptable. Minor clarification needed on analytical method validation for potency assay.", "key_outcomes": ["Manufacturing process accepted", "Potency assay clarification needed", "Container closure system approved"], "ha_feedback": "Constructive. FDA provided specific guidance on analytical methods.", "agreements": ["Updated potency assay protocol to be submitted", "Stability testing protocol confirmed"], "disagreements": ["FDA preference for additional release specification not agreed"], "recorded_by": "CMC Lead", "approved_by": "Dr. Sarah Kim", "approved_date": now - timedelta(days=85), "created_at": now - timedelta(days=88)},
            {"id": "MIN-003", "meeting_id": "HAM-005", "summary": "FDA endorsed the proposed Phase 3 design for Dupixent in COPD. Agency agreed on exacerbation rate as primary endpoint with FEV1 as key secondary. Biomarker enrichment for eosinophils >= 300 cells/uL accepted.", "key_outcomes": ["Phase 3 design endorsed", "Primary endpoint: annualized moderate-to-severe exacerbation rate", "Biomarker enrichment accepted", "Safety database: 600 patient-years minimum"], "ha_feedback": "Very positive. FDA sees unmet medical need in type 2 COPD.", "agreements": ["Exacerbation rate as primary endpoint", "Biomarker enrichment at eos >= 300", "52-week treatment duration"], "disagreements": [], "recorded_by": "Dr. Laura Martinez", "approved_by": "Chief Medical Officer", "approved_date": now - timedelta(days=135), "created_at": now - timedelta(days=138)},
            {"id": "MIN-004", "meeting_id": "HAM-006", "summary": "EMA Pediatric Committee provided positive scientific advice on Dupixent development in young children with AD. Committee agreed with proposed weight-based dosing and recommended specific PK sampling schedule.", "key_outcomes": ["Weight-based dosing accepted", "PK sampling schedule defined", "Safety monitoring enhanced for ages 6mo-2yr"], "ha_feedback": "Supportive of pediatric development. Emphasized importance of long-term safety data.", "agreements": ["Weight-based dosing tiers", "Enhanced safety monitoring for youngest cohort", "Interim safety review after 50 patients"], "disagreements": [], "recorded_by": "Dr. Laura Martinez", "approved_by": "Dr. Laura Martinez", "approved_date": now - timedelta(days=95), "created_at": now - timedelta(days=98)},
            {"id": "MIN-005", "meeting_id": "HAM-009", "summary": "FDA agreed that single-arm trial with ORR as primary endpoint is acceptable for accelerated approval of Libtayo in advanced BCC. Confirmatory post-marketing study required. Duration of response data considered supportive.", "key_outcomes": ["Accelerated approval pathway agreed", "ORR as primary endpoint accepted", "Confirmatory study required post-approval", "Duration of response as key secondary"], "ha_feedback": "FDA acknowledges high unmet need in advanced BCC. Willing to consider accelerated pathway.", "agreements": ["Accelerated approval based on ORR", "Post-marketing confirmatory randomized trial", "REMS not required at this time"], "disagreements": ["Sponsor proposed 12-month follow-up; FDA requested 18 months minimum"], "recorded_by": "Dr. Catherine Liu", "approved_by": "VP Oncology", "approved_date": now - timedelta(days=185), "created_at": now - timedelta(days=188)},
            {"id": "MIN-006", "meeting_id": "HAM-010", "summary": "FDA discussed Libtayo + chemotherapy combination in first-line NSCLC. Agency agreed with proposed Phase 3 design targeting PD-L1 all-comers population. Recommended OS as co-primary endpoint alongside PFS.", "key_outcomes": ["Phase 3 design agreed", "OS and PFS as co-primary endpoints", "All-comers population accepted", "Interim analysis plan discussed"], "ha_feedback": "Competitive landscape acknowledged. FDA emphasized need for clear differentiation from existing regimens.", "agreements": ["OS and PFS co-primary", "All-comers (no PD-L1 cutoff required)", "Pre-specified interim for futility"], "disagreements": [], "recorded_by": "Dr. Andrew Foster", "approved_by": "Dr. Catherine Liu", "approved_date": now - timedelta(days=65), "created_at": now - timedelta(days=68)},
            {"id": "MIN-007", "meeting_id": "HAM-001", "summary": "Follow-up minutes: Updated responses to FDA preliminary comments on EYLEA HD BLA briefing document, including clarification on non-inferiority margin and long-term extension data.", "key_outcomes": ["Non-inferiority margin justified", "Extension study data summarized"], "ha_feedback": None, "agreements": ["NI margin of 4 letters accepted"], "disagreements": [], "recorded_by": "Dr. Michael Chen", "approved_by": "Dr. Sarah Kim", "approved_date": now - timedelta(days=110), "created_at": now - timedelta(days=112)},
            {"id": "MIN-008", "meeting_id": "HAM-005", "summary": "Follow-up minutes: Additional statistical considerations for Dupixent COPD Phase 3 including multiplicity adjustment strategy and sample size re-estimation.", "key_outcomes": ["Multiplicity strategy agreed", "Adaptive sample size re-estimation approved"], "ha_feedback": None, "agreements": ["Hochberg procedure for multiplicity", "Conditional power-based re-estimation"], "disagreements": [], "recorded_by": "Biostatistician Lead", "approved_by": "Dr. Laura Martinez", "approved_date": now - timedelta(days=130), "created_at": now - timedelta(days=133)},
            {"id": "MIN-009", "meeting_id": "HAM-009", "summary": "Addendum: Detailed discussion of real-world evidence supplement to support Libtayo BCC accelerated approval application, including natural history data and treatment patterns.", "key_outcomes": ["RWE considered supportive but not pivotal", "Natural history comparison acceptable"], "ha_feedback": "FDA open to RWE as supportive evidence.", "agreements": ["RWE supplement to be included in BLA"], "disagreements": [], "recorded_by": "RWE Lead", "approved_by": "Dr. Catherine Liu", "approved_date": now - timedelta(days=180), "created_at": now - timedelta(days=183)},
            {"id": "MIN-010", "meeting_id": "HAM-010", "summary": "Supplementary minutes covering biomarker strategy discussion for Libtayo NSCLC combination study, including PD-L1 testing methodology and exploratory biomarker plan.", "key_outcomes": ["PD-L1 IHC 22C3 assay agreed", "TMB as exploratory biomarker"], "ha_feedback": None, "agreements": ["Centralized PD-L1 testing", "Tissue collection for exploratory biomarkers mandatory"], "disagreements": [], "recorded_by": "Biomarker Lead", "approved_by": "Dr. Andrew Foster", "approved_date": now - timedelta(days=60), "created_at": now - timedelta(days=63)},
        ]

        for mn in minutes_data:
            self._minutes[mn["id"]] = MeetingMinutes(**mn)

        # --- 15 Action Items ---
        action_items_data = [
            {"id": "AI-001", "meeting_id": "HAM-001", "action_description": "Submit 6-month stability data supplement for EYLEA HD BLA", "assigned_to": "CMC Lead", "priority": ActionPriority.HIGH, "due_date": now - timedelta(days=60), "status": CommitmentStatus.COMPLETED, "completed_date": now - timedelta(days=65), "notes": "Stability data submitted ahead of schedule", "created_at": now - timedelta(days=118)},
            {"id": "AI-002", "meeting_id": "HAM-001", "action_description": "Finalize BLA submission package incorporating FDA feedback", "assigned_to": "Dr. Sarah Kim", "priority": ActionPriority.CRITICAL, "due_date": now + timedelta(days=60), "status": CommitmentStatus.IN_PROGRESS, "completed_date": None, "notes": "On track for Q2 submission target", "created_at": now - timedelta(days=118)},
            {"id": "AI-003", "meeting_id": "HAM-002", "action_description": "Update potency assay validation protocol per FDA guidance", "assigned_to": "Analytical Lead", "priority": ActionPriority.HIGH, "due_date": now - timedelta(days=30), "status": CommitmentStatus.COMPLETED, "completed_date": now - timedelta(days=35), "notes": "Protocol updated and revalidated", "created_at": now - timedelta(days=88)},
            {"id": "AI-004", "meeting_id": "HAM-003", "action_description": "Prepare EMA scientific advice briefing book v1.0", "assigned_to": "EU Regulatory Affairs Lead", "priority": ActionPriority.HIGH, "due_date": now + timedelta(days=10), "status": CommitmentStatus.IN_PROGRESS, "completed_date": None, "notes": "Draft in review cycle", "created_at": now - timedelta(days=40)},
            {"id": "AI-005", "meeting_id": "HAM-004", "action_description": "Compile comprehensive safety signal assessment for FDA", "assigned_to": "Safety Officer", "priority": ActionPriority.CRITICAL, "due_date": now - timedelta(days=20), "status": CommitmentStatus.COMPLETED, "completed_date": now - timedelta(days=22), "notes": None, "created_at": now - timedelta(days=35)},
            {"id": "AI-006", "meeting_id": "HAM-005", "action_description": "Finalize Phase 3 protocol incorporating FDA EOP2 feedback", "assigned_to": "Dr. David Park", "priority": ActionPriority.HIGH, "due_date": now - timedelta(days=100), "status": CommitmentStatus.COMPLETED, "completed_date": now - timedelta(days=105), "notes": "Protocol finalized and approved by IRB", "created_at": now - timedelta(days=138)},
            {"id": "AI-007", "meeting_id": "HAM-005", "action_description": "Develop companion diagnostic for eosinophil enrichment", "assigned_to": "Biomarker Lead", "priority": ActionPriority.HIGH, "due_date": now + timedelta(days=90), "status": CommitmentStatus.IN_PROGRESS, "completed_date": None, "notes": "CDx partnership established with Roche Diagnostics", "created_at": now - timedelta(days=138)},
            {"id": "AI-008", "meeting_id": "HAM-006", "action_description": "Implement enhanced safety monitoring for pediatric cohort ages 6mo-2yr", "assigned_to": "Dr. Angela Martinez", "priority": ActionPriority.CRITICAL, "due_date": now - timedelta(days=50), "status": CommitmentStatus.COMPLETED, "completed_date": now - timedelta(days=55), "notes": "Safety monitoring plan approved by DSMB", "created_at": now - timedelta(days=98)},
            {"id": "AI-009", "meeting_id": "HAM-009", "action_description": "Design confirmatory randomized trial for Libtayo BCC post-approval", "assigned_to": "Dr. Andrew Foster", "priority": ActionPriority.HIGH, "due_date": now - timedelta(days=90), "status": CommitmentStatus.COMPLETED, "completed_date": now - timedelta(days=95), "notes": "Confirmatory trial protocol completed", "created_at": now - timedelta(days=188)},
            {"id": "AI-010", "meeting_id": "HAM-009", "action_description": "Extend follow-up to 18 months per FDA recommendation", "assigned_to": "Clinical Operations", "priority": ActionPriority.HIGH, "due_date": now + timedelta(days=120), "status": CommitmentStatus.IN_PROGRESS, "completed_date": None, "notes": "Follow-up ongoing; 12-month data available", "created_at": now - timedelta(days=188)},
            {"id": "AI-011", "meeting_id": "HAM-010", "action_description": "Establish centralized PD-L1 testing laboratory network", "assigned_to": "Biomarker Lead", "priority": ActionPriority.MEDIUM, "due_date": now + timedelta(days=45), "status": CommitmentStatus.IN_PROGRESS, "completed_date": None, "notes": "3 of 5 labs qualified", "created_at": now - timedelta(days=68)},
            {"id": "AI-012", "meeting_id": "HAM-010", "action_description": "Submit Phase 3 protocol to FDA via IND amendment", "assigned_to": "Dr. Catherine Liu", "priority": ActionPriority.HIGH, "due_date": now - timedelta(days=20), "status": CommitmentStatus.COMPLETED, "completed_date": now - timedelta(days=25), "notes": "IND amendment submitted; FDA acknowledged", "created_at": now - timedelta(days=68)},
            {"id": "AI-013", "meeting_id": "HAM-004", "action_description": "Prepare risk minimization action plan for elderly patients", "assigned_to": "Safety Officer", "priority": ActionPriority.HIGH, "due_date": now + timedelta(days=30), "status": CommitmentStatus.OPEN, "completed_date": None, "notes": None, "created_at": now - timedelta(days=30)},
            {"id": "AI-014", "meeting_id": "HAM-007", "action_description": "Prepare Type C meeting briefing document for sNDA strategy", "assigned_to": "Dr. Laura Martinez", "priority": ActionPriority.MEDIUM, "due_date": now + timedelta(days=60), "status": CommitmentStatus.OPEN, "completed_date": None, "notes": None, "created_at": now - timedelta(days=20)},
            {"id": "AI-015", "meeting_id": "HAM-011", "action_description": "Compile UK-specific regulatory dossier for MHRA submission", "assigned_to": "UK Regulatory Affairs", "priority": ActionPriority.MEDIUM, "due_date": now + timedelta(days=75), "status": CommitmentStatus.OPEN, "completed_date": None, "notes": None, "created_at": now - timedelta(days=30)},
        ]

        for ai in action_items_data:
            self._action_items[ai["id"]] = MeetingActionItem(**ai)

        # --- 12 HA Commitments ---
        commitments_data = [
            {"id": "HC-001", "meeting_id": "HAM-001", "trial_id": EYLEA_TRIAL, "commitment_text": "Submit 6-month stability data as BLA amendment prior to filing", "health_authority": HealthAuthority.FDA, "source": "Pre-BLA Meeting Minutes HAM-001", "status": CommitmentStatus.COMPLETED, "due_date": now - timedelta(days=60), "responsible_person": "Dr. Sarah Kim", "completed_date": now - timedelta(days=65), "evidence_reference": "BLA Amendment #001", "regulatory_impact": "Required for BLA acceptance", "created_at": now - timedelta(days=118)},
            {"id": "HC-002", "meeting_id": "HAM-001", "trial_id": EYLEA_TRIAL, "commitment_text": "Submit BLA for EYLEA HD by Q2 2026", "health_authority": HealthAuthority.FDA, "source": "Pre-BLA Meeting Minutes HAM-001", "status": CommitmentStatus.IN_PROGRESS, "due_date": now + timedelta(days=60), "responsible_person": "Dr. Sarah Kim", "completed_date": None, "evidence_reference": None, "regulatory_impact": "Primary regulatory milestone", "created_at": now - timedelta(days=118)},
            {"id": "HC-003", "meeting_id": "HAM-002", "trial_id": EYLEA_TRIAL, "commitment_text": "Provide updated potency assay validation data", "health_authority": HealthAuthority.FDA, "source": "Type B CMC Meeting Minutes HAM-002", "status": CommitmentStatus.COMPLETED, "due_date": now - timedelta(days=30), "responsible_person": "Analytical Lead", "completed_date": now - timedelta(days=35), "evidence_reference": "CMC Amendment #003", "regulatory_impact": "CMC requirement for BLA", "created_at": now - timedelta(days=88)},
            {"id": "HC-004", "meeting_id": "HAM-005", "trial_id": DUPIXENT_TRIAL, "commitment_text": "Conduct Phase 3 with biomarker enrichment at eosinophils >= 300 cells/uL", "health_authority": HealthAuthority.FDA, "source": "EOP2 Meeting Minutes HAM-005", "status": CommitmentStatus.IN_PROGRESS, "due_date": now + timedelta(days=365), "responsible_person": "Dr. Laura Martinez", "completed_date": None, "evidence_reference": None, "regulatory_impact": "Phase 3 registration requirement", "created_at": now - timedelta(days=138)},
            {"id": "HC-005", "meeting_id": "HAM-005", "trial_id": DUPIXENT_TRIAL, "commitment_text": "Achieve minimum 600 patient-years safety exposure in Phase 3", "health_authority": HealthAuthority.FDA, "source": "EOP2 Meeting Minutes HAM-005", "status": CommitmentStatus.IN_PROGRESS, "due_date": now + timedelta(days=365), "responsible_person": "Dr. David Park", "completed_date": None, "evidence_reference": None, "regulatory_impact": "Safety database requirement", "created_at": now - timedelta(days=138)},
            {"id": "HC-006", "meeting_id": "HAM-006", "trial_id": DUPIXENT_TRIAL, "commitment_text": "Implement enhanced safety monitoring for pediatric patients ages 6mo-2yr", "health_authority": HealthAuthority.EMA, "source": "EMA Scientific Advice HAM-006", "status": CommitmentStatus.COMPLETED, "due_date": now - timedelta(days=50), "responsible_person": "Dr. Angela Martinez", "completed_date": now - timedelta(days=55), "evidence_reference": "Safety Monitoring Plan v2.0", "regulatory_impact": "Pediatric development requirement", "created_at": now - timedelta(days=98)},
            {"id": "HC-007", "meeting_id": "HAM-006", "trial_id": DUPIXENT_TRIAL, "commitment_text": "Conduct interim safety review after 50 pediatric patients enrolled", "health_authority": HealthAuthority.EMA, "source": "EMA Scientific Advice HAM-006", "status": CommitmentStatus.OPEN, "due_date": now + timedelta(days=180), "responsible_person": "Dr. Angela Martinez", "completed_date": None, "evidence_reference": None, "regulatory_impact": "Pediatric safety milestone", "created_at": now - timedelta(days=98)},
            {"id": "HC-008", "meeting_id": "HAM-009", "trial_id": LIBTAYO_TRIAL, "commitment_text": "Conduct post-marketing confirmatory randomized trial for BCC indication", "health_authority": HealthAuthority.FDA, "source": "Pre-NDA Meeting Minutes HAM-009", "status": CommitmentStatus.IN_PROGRESS, "due_date": now + timedelta(days=730), "responsible_person": "Dr. Andrew Foster", "completed_date": None, "evidence_reference": "Confirmatory Trial Protocol v1.0", "regulatory_impact": "Post-marketing requirement for accelerated approval", "created_at": now - timedelta(days=188)},
            {"id": "HC-009", "meeting_id": "HAM-009", "trial_id": LIBTAYO_TRIAL, "commitment_text": "Provide 18-month minimum follow-up data for BCC pivotal study", "health_authority": HealthAuthority.FDA, "source": "Pre-NDA Meeting Minutes HAM-009", "status": CommitmentStatus.IN_PROGRESS, "due_date": now + timedelta(days=120), "responsible_person": "Clinical Operations", "completed_date": None, "evidence_reference": None, "regulatory_impact": "Required for NDA submission", "created_at": now - timedelta(days=188)},
            {"id": "HC-010", "meeting_id": "HAM-010", "trial_id": LIBTAYO_TRIAL, "commitment_text": "Use OS and PFS as co-primary endpoints in NSCLC combination Phase 3", "health_authority": HealthAuthority.FDA, "source": "Type B Meeting Minutes HAM-010", "status": CommitmentStatus.IN_PROGRESS, "due_date": now + timedelta(days=540), "responsible_person": "Dr. Catherine Liu", "completed_date": None, "evidence_reference": "Phase 3 Protocol v1.0", "regulatory_impact": "Registration endpoint requirement", "created_at": now - timedelta(days=68)},
            {"id": "HC-011", "meeting_id": "HAM-010", "trial_id": LIBTAYO_TRIAL, "commitment_text": "Implement centralized PD-L1 testing with IHC 22C3 assay", "health_authority": HealthAuthority.FDA, "source": "Type B Meeting Minutes HAM-010", "status": CommitmentStatus.IN_PROGRESS, "due_date": now + timedelta(days=45), "responsible_person": "Biomarker Lead", "completed_date": None, "evidence_reference": None, "regulatory_impact": "Biomarker strategy requirement", "created_at": now - timedelta(days=68)},
            {"id": "HC-012", "meeting_id": "HAM-004", "trial_id": EYLEA_TRIAL, "commitment_text": "Develop risk minimization action plan for elderly patients based on safety signal assessment", "health_authority": HealthAuthority.FDA, "source": "Type A Safety Meeting HAM-004", "status": CommitmentStatus.OPEN, "due_date": now + timedelta(days=30), "responsible_person": "Safety Officer", "completed_date": None, "evidence_reference": None, "regulatory_impact": "Post-marketing safety requirement", "created_at": now - timedelta(days=30)},
        ]

        for hc in commitments_data:
            self._commitments[hc["id"]] = HACommitment(**hc)

    # ------------------------------------------------------------------
    # Meeting Management
    # ------------------------------------------------------------------

    def list_meetings(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[HAMeeting]:
        """List HA meetings with optional trial filter."""
        with self._lock:
            result = list(self._meetings.values())

        if trial_id is not None:
            result = [m for m in result if m.trial_id == trial_id]

        return sorted(result, key=lambda m: m.id)

    def get_meeting(self, meeting_id: str) -> HAMeeting | None:
        """Get a single meeting by ID."""
        with self._lock:
            return self._meetings.get(meeting_id)

    def create_meeting(self, payload: HAMeetingCreate) -> HAMeeting:
        """Create a new HA meeting."""
        now = datetime.now(timezone.utc)
        meeting_id = f"HAM-{uuid4().hex[:8].upper()}"
        meeting = HAMeeting(
            id=meeting_id,
            trial_id=payload.trial_id,
            meeting_type=payload.meeting_type,
            health_authority=payload.health_authority,
            status=MeetingStatus.PLANNING,
            title=payload.title,
            objective=payload.objective,
            regulatory_lead=payload.regulatory_lead,
            medical_lead=payload.medical_lead,
            key_questions=payload.key_questions,
            created_at=now,
        )
        with self._lock:
            self._meetings[meeting_id] = meeting
        logger.info("Created HA meeting %s: %s", meeting_id, payload.title)
        return meeting

    def update_meeting(
        self, meeting_id: str, payload: HAMeetingUpdate
    ) -> HAMeeting | None:
        """Update an existing HA meeting."""
        with self._lock:
            existing = self._meetings.get(meeting_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = HAMeeting(**data)
            self._meetings[meeting_id] = updated
        return updated

    def delete_meeting(self, meeting_id: str) -> bool:
        """Delete a meeting. Returns True if deleted."""
        with self._lock:
            if meeting_id in self._meetings:
                del self._meetings[meeting_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Briefing Document Management
    # ------------------------------------------------------------------

    def list_briefing_docs(
        self,
        *,
        meeting_id: str | None = None,
    ) -> list[BriefingDocument]:
        """List briefing documents with optional meeting filter."""
        with self._lock:
            result = list(self._briefing_docs.values())

        if meeting_id is not None:
            result = [bd for bd in result if bd.meeting_id == meeting_id]

        return sorted(result, key=lambda bd: bd.id)

    def get_briefing_doc(self, doc_id: str) -> BriefingDocument | None:
        """Get a single briefing document by ID."""
        with self._lock:
            return self._briefing_docs.get(doc_id)

    def create_briefing_doc(self, payload: BriefingDocumentCreate) -> BriefingDocument:
        """Create a new briefing document."""
        now = datetime.now(timezone.utc)
        doc_id = f"BD-{uuid4().hex[:8].upper()}"
        doc = BriefingDocument(
            id=doc_id,
            meeting_id=payload.meeting_id,
            title=payload.title,
            version=payload.version,
            author=payload.author,
            sections=payload.sections,
            created_at=now,
        )
        with self._lock:
            self._briefing_docs[doc_id] = doc
        logger.info("Created briefing document %s: %s", doc_id, payload.title)
        return doc

    def update_briefing_doc(
        self, doc_id: str, payload: BriefingDocumentUpdate
    ) -> BriefingDocument | None:
        """Update a briefing document."""
        with self._lock:
            existing = self._briefing_docs.get(doc_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = BriefingDocument(**data)
            self._briefing_docs[doc_id] = updated
        return updated

    def delete_briefing_doc(self, doc_id: str) -> bool:
        """Delete a briefing document. Returns True if deleted."""
        with self._lock:
            if doc_id in self._briefing_docs:
                del self._briefing_docs[doc_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Meeting Minutes Management
    # ------------------------------------------------------------------

    def list_minutes(
        self,
        *,
        meeting_id: str | None = None,
    ) -> list[MeetingMinutes]:
        """List meeting minutes with optional meeting filter."""
        with self._lock:
            result = list(self._minutes.values())

        if meeting_id is not None:
            result = [mn for mn in result if mn.meeting_id == meeting_id]

        return sorted(result, key=lambda mn: mn.id)

    def get_minutes(self, minutes_id: str) -> MeetingMinutes | None:
        """Get a single meeting minutes by ID."""
        with self._lock:
            return self._minutes.get(minutes_id)

    def create_minutes(self, payload: MeetingMinutesCreate) -> MeetingMinutes:
        """Create new meeting minutes."""
        now = datetime.now(timezone.utc)
        minutes_id = f"MIN-{uuid4().hex[:8].upper()}"
        minutes = MeetingMinutes(
            id=minutes_id,
            meeting_id=payload.meeting_id,
            summary=payload.summary,
            recorded_by=payload.recorded_by,
            key_outcomes=payload.key_outcomes,
            agreements=payload.agreements,
            created_at=now,
        )
        with self._lock:
            self._minutes[minutes_id] = minutes
        logger.info("Created meeting minutes %s for meeting %s", minutes_id, payload.meeting_id)
        return minutes

    def update_minutes(
        self, minutes_id: str, payload: MeetingMinutesUpdate
    ) -> MeetingMinutes | None:
        """Update meeting minutes."""
        with self._lock:
            existing = self._minutes.get(minutes_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = MeetingMinutes(**data)
            self._minutes[minutes_id] = updated
        return updated

    def delete_minutes(self, minutes_id: str) -> bool:
        """Delete meeting minutes. Returns True if deleted."""
        with self._lock:
            if minutes_id in self._minutes:
                del self._minutes[minutes_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Action Item Management
    # ------------------------------------------------------------------

    def list_action_items(
        self,
        *,
        meeting_id: str | None = None,
    ) -> list[MeetingActionItem]:
        """List action items with optional meeting filter."""
        with self._lock:
            result = list(self._action_items.values())

        if meeting_id is not None:
            result = [ai for ai in result if ai.meeting_id == meeting_id]

        return sorted(result, key=lambda ai: ai.id)

    def get_action_item(self, item_id: str) -> MeetingActionItem | None:
        """Get a single action item by ID."""
        with self._lock:
            return self._action_items.get(item_id)

    def create_action_item(self, payload: MeetingActionItemCreate) -> MeetingActionItem:
        """Create a new action item."""
        now = datetime.now(timezone.utc)
        item_id = f"AI-{uuid4().hex[:8].upper()}"
        item = MeetingActionItem(
            id=item_id,
            meeting_id=payload.meeting_id,
            action_description=payload.action_description,
            assigned_to=payload.assigned_to,
            priority=payload.priority,
            due_date=payload.due_date,
            created_at=now,
        )
        with self._lock:
            self._action_items[item_id] = item
        logger.info("Created action item %s for meeting %s", item_id, payload.meeting_id)
        return item

    def update_action_item(
        self, item_id: str, payload: MeetingActionItemUpdate
    ) -> MeetingActionItem | None:
        """Update an action item."""
        with self._lock:
            existing = self._action_items.get(item_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = MeetingActionItem(**data)
            self._action_items[item_id] = updated
        return updated

    def delete_action_item(self, item_id: str) -> bool:
        """Delete an action item. Returns True if deleted."""
        with self._lock:
            if item_id in self._action_items:
                del self._action_items[item_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Commitment Management
    # ------------------------------------------------------------------

    def list_commitments(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[HACommitment]:
        """List HA commitments with optional trial filter."""
        with self._lock:
            result = list(self._commitments.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]

        return sorted(result, key=lambda c: c.id)

    def get_commitment(self, commitment_id: str) -> HACommitment | None:
        """Get a single commitment by ID."""
        with self._lock:
            return self._commitments.get(commitment_id)

    def create_commitment(self, payload: HACommitmentCreate) -> HACommitment:
        """Create a new HA commitment."""
        now = datetime.now(timezone.utc)
        commitment_id = f"HC-{uuid4().hex[:8].upper()}"
        commitment = HACommitment(
            id=commitment_id,
            meeting_id=payload.meeting_id,
            trial_id=payload.trial_id,
            commitment_text=payload.commitment_text,
            health_authority=payload.health_authority,
            source=payload.source,
            responsible_person=payload.responsible_person,
            due_date=payload.due_date,
            created_at=now,
        )
        with self._lock:
            self._commitments[commitment_id] = commitment
        logger.info("Created HA commitment %s: %s", commitment_id, payload.commitment_text[:60])
        return commitment

    def update_commitment(
        self, commitment_id: str, payload: HACommitmentUpdate
    ) -> HACommitment | None:
        """Update a commitment."""
        with self._lock:
            existing = self._commitments.get(commitment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = HACommitment(**data)
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

    def get_metrics(self, trial_id: str | None = None) -> HAMeetingMetrics:
        """Compute aggregated HA meeting metrics."""
        now = datetime.now(timezone.utc)

        with self._lock:
            meetings = list(self._meetings.values())
            briefing_docs = list(self._briefing_docs.values())
            minutes = list(self._minutes.values())
            action_items = list(self._action_items.values())
            commitments = list(self._commitments.values())

        if trial_id is not None:
            meetings = [m for m in meetings if m.trial_id == trial_id]
            # Filter briefing docs by meeting IDs in scope
            meeting_ids = {m.id for m in meetings}
            briefing_docs = [bd for bd in briefing_docs if bd.meeting_id in meeting_ids]
            minutes = [mn for mn in minutes if mn.meeting_id in meeting_ids]
            action_items = [ai for ai in action_items if ai.meeting_id in meeting_ids]
            commitments = [c for c in commitments if c.trial_id == trial_id]

        # Meetings by type
        meetings_by_type: dict[str, int] = {}
        for m in meetings:
            key = m.meeting_type.value
            meetings_by_type[key] = meetings_by_type.get(key, 0) + 1

        # Meetings by status
        meetings_by_status: dict[str, int] = {}
        for m in meetings:
            key = m.status.value
            meetings_by_status[key] = meetings_by_status.get(key, 0) + 1

        # Meetings by authority
        meetings_by_authority: dict[str, int] = {}
        for m in meetings:
            key = m.health_authority.value
            meetings_by_authority[key] = meetings_by_authority.get(key, 0) + 1

        # Briefing docs
        approved_docs = sum(1 for bd in briefing_docs if bd.status == "approved")

        # Action items by status
        action_items_by_status: dict[str, int] = {}
        for ai in action_items:
            key = ai.status.value
            action_items_by_status[key] = action_items_by_status.get(key, 0) + 1

        # Overdue actions
        overdue_actions = sum(
            1 for ai in action_items
            if ai.status not in (CommitmentStatus.COMPLETED, CommitmentStatus.WAIVED)
            and ai.due_date < now
        )

        # Commitments by status
        commitments_by_status: dict[str, int] = {}
        for c in commitments:
            key = c.status.value
            commitments_by_status[key] = commitments_by_status.get(key, 0) + 1

        # Overdue commitments
        overdue_commitments = sum(
            1 for c in commitments
            if c.status not in (CommitmentStatus.COMPLETED, CommitmentStatus.WAIVED)
            and c.due_date is not None
            and c.due_date < now
        )

        return HAMeetingMetrics(
            total_meetings=len(meetings),
            meetings_by_type=meetings_by_type,
            meetings_by_status=meetings_by_status,
            meetings_by_authority=meetings_by_authority,
            total_briefing_docs=len(briefing_docs),
            approved_briefing_docs=approved_docs,
            total_minutes=len(minutes),
            total_action_items=len(action_items),
            action_items_by_status=action_items_by_status,
            overdue_actions=overdue_actions,
            total_commitments=len(commitments),
            commitments_by_status=commitments_by_status,
            overdue_commitments=overdue_commitments,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: HAMeetingTrackerService | None = None
_instance_lock = threading.Lock()


def get_ha_meeting_tracker_service() -> HAMeetingTrackerService:
    """Return the singleton HAMeetingTrackerService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = HAMeetingTrackerService()
    return _instance


def reset_ha_meeting_tracker_service() -> HAMeetingTrackerService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = HAMeetingTrackerService()
    return _instance
