"""Regulatory Intelligence Service (REG-INTEL).

Tracks regulatory landscape changes, authority communications, guidance updates,
submission tracking across jurisdictions (FDA, EMA, PMDA, TGA, Health Canada),
regulatory risk assessments, and compliance gap analysis for clinical trials.

Usage:
    from app.services.regulatory_intelligence_service import (
        get_regulatory_intelligence_service,
    )

    svc = get_regulatory_intelligence_service()
    items = svc.list_intelligence_items()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.regulatory_intelligence import (
    AuthorityCommunication,
    AuthorityCommunicationCreate,
    AuthorityCommunicationUpdate,
    ComplianceGap,
    ComplianceGapCreate,
    ComplianceGapUpdate,
    GapSeverity,
    GapStatus,
    ImpactLevel,
    IntelligenceItemCreate,
    IntelligenceItemUpdate,
    IntelligenceStatus,
    IntelligenceType,
    RegulatoryAuthority,
    RegulatoryIntelligenceItem,
    RegulatoryIntelligenceMetrics,
    RegulatorySubmissionTracker,
    SubmissionStatus,
    SubmissionTrackerCreate,
    SubmissionTrackerUpdate,
    SubmissionType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class RegulatoryIntelligenceService:
    """In-memory Regulatory Intelligence engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._intelligence_items: dict[str, RegulatoryIntelligenceItem] = {}
        self._submissions: dict[str, RegulatorySubmissionTracker] = {}
        self._compliance_gaps: dict[str, ComplianceGap] = {}
        self._communications: dict[str, AuthorityCommunication] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic regulatory intelligence data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Intelligence Items ---
        items_data = [
            {
                "id": "RI-001",
                "authority": RegulatoryAuthority.FDA,
                "intelligence_type": IntelligenceType.GUIDANCE_UPDATE,
                "title": "FDA Draft Guidance on Retinal Endpoint Adjudication",
                "summary": "FDA released draft guidance on best practices for adjudicating retinal endpoints in ophthalmology trials, including BCVA and OCT-based measurements.",
                "published_date": now - timedelta(days=120),
                "effective_date": now - timedelta(days=60),
                "impact_level": ImpactLevel.HIGH,
                "affected_trials": [EYLEA_TRIAL],
                "affected_therapeutic_areas": ["Ophthalmology"],
                "status": IntelligenceStatus.ASSESSED,
                "assessed_by": "Dr. Sarah Chen",
                "assessed_date": now - timedelta(days=100),
                "action_items": ["Update BCVA endpoint adjudication charter", "Train site staff on new OCT standards"],
                "source_url": "https://www.fda.gov/guidance/retinal-endpoints-2025",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "RI-002",
                "authority": RegulatoryAuthority.EMA,
                "intelligence_type": IntelligenceType.REGULATION_CHANGE,
                "title": "EMA Clinical Trials Regulation Update for Biologics",
                "summary": "EMA updated the Clinical Trials Regulation (CTR) with new requirements for biologic products including enhanced pharmacovigilance reporting.",
                "published_date": now - timedelta(days=90),
                "effective_date": now + timedelta(days=90),
                "impact_level": ImpactLevel.CRITICAL,
                "affected_trials": [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL],
                "affected_therapeutic_areas": ["Ophthalmology", "Dermatology", "Oncology"],
                "status": IntelligenceStatus.ACTION_REQUIRED,
                "assessed_by": "Dr. James Rodriguez",
                "assessed_date": now - timedelta(days=80),
                "action_items": ["Update PV reporting timelines", "Revise DSUR template", "Train CRAs on new CTR requirements"],
                "source_url": "https://www.ema.europa.eu/ctr-update-2025",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "RI-003",
                "authority": RegulatoryAuthority.FDA,
                "intelligence_type": IntelligenceType.SAFETY_ALERT,
                "title": "FDA Safety Communication on Anti-VEGF Therapies",
                "summary": "FDA issued safety communication regarding post-marketing reports of intraocular inflammation with anti-VEGF therapies.",
                "published_date": now - timedelta(days=75),
                "impact_level": ImpactLevel.HIGH,
                "affected_trials": [EYLEA_TRIAL],
                "affected_therapeutic_areas": ["Ophthalmology"],
                "status": IntelligenceStatus.IMPLEMENTED,
                "assessed_by": "Dr. Michael Patel",
                "assessed_date": now - timedelta(days=70),
                "action_items": ["Update informed consent", "Enhance AE monitoring"],
                "source_url": "https://www.fda.gov/safety/anti-vegf-alert",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "RI-004",
                "authority": RegulatoryAuthority.PMDA,
                "intelligence_type": IntelligenceType.ADVISORY_COMMITTEE,
                "title": "PMDA Advisory Committee Review of Dupilumab Pediatric Extension",
                "summary": "PMDA advisory committee reviewed dupilumab data for pediatric atopic dermatitis, recommending additional safety data for ages 6-12.",
                "published_date": now - timedelta(days=60),
                "impact_level": ImpactLevel.MEDIUM,
                "affected_trials": [DUPIXENT_TRIAL],
                "affected_therapeutic_areas": ["Dermatology", "Pediatrics"],
                "status": IntelligenceStatus.ASSESSED,
                "assessed_by": "Dr. Laura Kim",
                "assessed_date": now - timedelta(days=55),
                "action_items": ["Prepare pediatric safety summary", "Coordinate with PMDA liaison"],
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "RI-005",
                "authority": RegulatoryAuthority.FDA,
                "intelligence_type": IntelligenceType.APPROVAL_DECISION,
                "title": "FDA Approval of Competitor Anti-PD-1 Therapy in CSCC",
                "summary": "FDA approved competitor checkpoint inhibitor for cutaneous squamous cell carcinoma, potentially impacting Libtayo market positioning.",
                "published_date": now - timedelta(days=45),
                "impact_level": ImpactLevel.HIGH,
                "affected_trials": [LIBTAYO_TRIAL],
                "affected_therapeutic_areas": ["Oncology"],
                "status": IntelligenceStatus.ASSESSED,
                "assessed_by": "Dr. Catherine Liu",
                "assessed_date": now - timedelta(days=40),
                "action_items": ["Update competitive landscape analysis", "Review trial design implications"],
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "RI-006",
                "authority": RegulatoryAuthority.HEALTH_CANADA,
                "intelligence_type": IntelligenceType.INSPECTION_TREND,
                "title": "Health Canada GCP Inspection Focus on Data Integrity",
                "summary": "Health Canada increased focus on electronic data integrity during GCP inspections, with emphasis on audit trails and source data verification.",
                "published_date": now - timedelta(days=30),
                "impact_level": ImpactLevel.MEDIUM,
                "affected_trials": [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL],
                "affected_therapeutic_areas": ["All"],
                "status": IntelligenceStatus.UNDER_REVIEW,
                "action_items": [],
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "RI-007",
                "authority": RegulatoryAuthority.TGA,
                "intelligence_type": IntelligenceType.GUIDANCE_UPDATE,
                "title": "TGA Updated Biosimilar Guidelines for Ophthalmology Products",
                "summary": "TGA published updated guidelines for biosimilar development in ophthalmology with specific requirements for clinical comparability studies.",
                "published_date": now - timedelta(days=25),
                "impact_level": ImpactLevel.LOW,
                "affected_trials": [EYLEA_TRIAL],
                "affected_therapeutic_areas": ["Ophthalmology"],
                "status": IntelligenceStatus.NEW,
                "action_items": [],
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "RI-008",
                "authority": RegulatoryAuthority.MHRA,
                "intelligence_type": IntelligenceType.POLICY_ANNOUNCEMENT,
                "title": "MHRA Post-Brexit Clinical Trials Regulation Framework",
                "summary": "MHRA announced new standalone clinical trials framework with streamlined approval processes for innovative therapies.",
                "published_date": now - timedelta(days=20),
                "impact_level": ImpactLevel.MEDIUM,
                "affected_trials": [DUPIXENT_TRIAL, LIBTAYO_TRIAL],
                "affected_therapeutic_areas": ["Dermatology", "Oncology"],
                "status": IntelligenceStatus.UNDER_REVIEW,
                "action_items": [],
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "RI-009",
                "authority": RegulatoryAuthority.FDA,
                "intelligence_type": IntelligenceType.ENFORCEMENT_ACTION,
                "title": "FDA Warning Letter to CRO for GCP Violations",
                "summary": "FDA issued warning letter to a major CRO for GCP violations including inadequate monitoring and incomplete source data verification.",
                "published_date": now - timedelta(days=15),
                "impact_level": ImpactLevel.MEDIUM,
                "affected_trials": [EYLEA_TRIAL, DUPIXENT_TRIAL],
                "affected_therapeutic_areas": ["All"],
                "status": IntelligenceStatus.ASSESSED,
                "assessed_by": "Dr. Robert Williams",
                "assessed_date": now - timedelta(days=12),
                "action_items": ["Review CRO monitoring plans", "Verify SDV compliance"],
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "RI-010",
                "authority": RegulatoryAuthority.EMA,
                "intelligence_type": IntelligenceType.GUIDANCE_UPDATE,
                "title": "EMA Guideline on Immunogenicity Assessment of Monoclonal Antibodies",
                "summary": "EMA released updated guideline on immunogenicity assessment with new recommendations for anti-drug antibody testing strategies.",
                "published_date": now - timedelta(days=10),
                "impact_level": ImpactLevel.HIGH,
                "affected_trials": [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL],
                "affected_therapeutic_areas": ["All"],
                "status": IntelligenceStatus.NEW,
                "action_items": [],
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "RI-011",
                "authority": RegulatoryAuthority.ANVISA,
                "intelligence_type": IntelligenceType.REGULATION_CHANGE,
                "title": "ANVISA Updated Requirements for Clinical Trial Authorization",
                "summary": "ANVISA implemented new electronic submission requirements and reduced timelines for clinical trial authorization in Brazil.",
                "published_date": now - timedelta(days=8),
                "impact_level": ImpactLevel.LOW,
                "affected_trials": [LIBTAYO_TRIAL],
                "affected_therapeutic_areas": ["Oncology"],
                "status": IntelligenceStatus.NEW,
                "action_items": [],
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "RI-012",
                "authority": RegulatoryAuthority.NMPA,
                "intelligence_type": IntelligenceType.POLICY_ANNOUNCEMENT,
                "title": "NMPA Fast-Track Designation for Innovative Biologics",
                "summary": "NMPA announced expanded fast-track program for innovative biologic therapies targeting unmet medical needs in China.",
                "published_date": now - timedelta(days=5),
                "impact_level": ImpactLevel.MEDIUM,
                "affected_trials": [DUPIXENT_TRIAL, LIBTAYO_TRIAL],
                "affected_therapeutic_areas": ["Dermatology", "Oncology"],
                "status": IntelligenceStatus.NEW,
                "action_items": [],
                "created_at": now - timedelta(days=5),
            },
        ]

        for item in items_data:
            self._intelligence_items[item["id"]] = RegulatoryIntelligenceItem(**item)

        # --- 10 Submission Trackers ---
        submissions_data = [
            {
                "id": "SUB-001",
                "trial_id": EYLEA_TRIAL,
                "authority": RegulatoryAuthority.FDA,
                "submission_type": SubmissionType.BLA,
                "submission_number": "BLA-761999",
                "title": "EYLEA HD 8mg BLA Supplement for wAMD",
                "status": SubmissionStatus.UNDER_REVIEW,
                "planned_date": now - timedelta(days=180),
                "actual_submission_date": now - timedelta(days=175),
                "target_approval_date": now + timedelta(days=90),
                "lead_reviewer": "Dr. Sarah Chen",
                "assigned_team": ["Dr. Sarah Chen", "Dr. James Rodriguez", "Regulatory Specialist A"],
                "documents_included": ["Module 1", "Module 2.5", "Module 5 CSR"],
                "questions_received": 12,
                "responses_submitted": 10,
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "SUB-002",
                "trial_id": EYLEA_TRIAL,
                "authority": RegulatoryAuthority.EMA,
                "submission_type": SubmissionType.MAA,
                "submission_number": "EMEA/H/C/005678",
                "title": "EYLEA HD MAA for Wet AMD and DME",
                "status": SubmissionStatus.SUBMITTED,
                "planned_date": now - timedelta(days=120),
                "actual_submission_date": now - timedelta(days=115),
                "target_approval_date": now + timedelta(days=150),
                "lead_reviewer": "Dr. James Rodriguez",
                "assigned_team": ["Dr. James Rodriguez", "Regulatory Specialist B"],
                "documents_included": ["eCTD Module 1-5"],
                "questions_received": 0,
                "responses_submitted": 0,
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "SUB-003",
                "trial_id": DUPIXENT_TRIAL,
                "authority": RegulatoryAuthority.FDA,
                "submission_type": SubmissionType.NDA,
                "submission_number": "NDA-215678",
                "title": "Dupixent sNDA for Prurigo Nodularis",
                "status": SubmissionStatus.APPROVED,
                "planned_date": now - timedelta(days=300),
                "actual_submission_date": now - timedelta(days=290),
                "response_date": now - timedelta(days=60),
                "target_approval_date": now - timedelta(days=60),
                "lead_reviewer": "Dr. Laura Kim",
                "assigned_team": ["Dr. Laura Kim", "Dr. Angela Martinez"],
                "documents_included": ["NDA Supplement", "Clinical Study Reports"],
                "questions_received": 8,
                "responses_submitted": 8,
                "created_at": now - timedelta(days=320),
            },
            {
                "id": "SUB-004",
                "trial_id": DUPIXENT_TRIAL,
                "authority": RegulatoryAuthority.PMDA,
                "submission_type": SubmissionType.CTA,
                "submission_number": "CTA-JP-2025-0042",
                "title": "Dupixent CTA for Pediatric Atopic Dermatitis Extension in Japan",
                "status": SubmissionStatus.QUESTIONS_RECEIVED,
                "planned_date": now - timedelta(days=90),
                "actual_submission_date": now - timedelta(days=85),
                "target_approval_date": now + timedelta(days=60),
                "lead_reviewer": "Dr. David Nakamura",
                "assigned_team": ["Dr. David Nakamura", "Japan Regulatory Liaison"],
                "documents_included": ["CTA Application", "Investigator Brochure", "Protocol"],
                "questions_received": 5,
                "responses_submitted": 3,
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "SUB-005",
                "trial_id": LIBTAYO_TRIAL,
                "authority": RegulatoryAuthority.FDA,
                "submission_type": SubmissionType.BLA,
                "submission_number": "BLA-761234",
                "title": "Libtayo BLA Supplement for Advanced NSCLC",
                "status": SubmissionStatus.DRAFTING,
                "planned_date": now + timedelta(days=60),
                "target_approval_date": now + timedelta(days=300),
                "lead_reviewer": "Dr. Catherine Liu",
                "assigned_team": ["Dr. Catherine Liu", "Dr. Andrew Foster", "Regulatory Specialist C"],
                "documents_included": [],
                "questions_received": 0,
                "responses_submitted": 0,
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "SUB-006",
                "trial_id": LIBTAYO_TRIAL,
                "authority": RegulatoryAuthority.EMA,
                "submission_type": SubmissionType.MAA,
                "submission_number": "EMEA/H/C/004567",
                "title": "Libtayo MAA Variation for First-Line NSCLC",
                "status": SubmissionStatus.INTERNAL_REVIEW,
                "planned_date": now + timedelta(days=30),
                "target_approval_date": now + timedelta(days=270),
                "lead_reviewer": "Dr. Andrew Foster",
                "assigned_team": ["Dr. Andrew Foster", "EU Regulatory Specialist"],
                "documents_included": ["Draft Module 2.5"],
                "questions_received": 0,
                "responses_submitted": 0,
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "SUB-007",
                "trial_id": EYLEA_TRIAL,
                "authority": RegulatoryAuthority.FDA,
                "submission_type": SubmissionType.ANNUAL_REPORT,
                "submission_number": "AR-2025-EYLEA",
                "title": "EYLEA Annual Report 2025",
                "status": SubmissionStatus.SUBMITTED,
                "planned_date": now - timedelta(days=30),
                "actual_submission_date": now - timedelta(days=28),
                "lead_reviewer": "Dr. Sarah Chen",
                "assigned_team": ["Dr. Sarah Chen"],
                "documents_included": ["Annual Report", "Safety Update"],
                "questions_received": 0,
                "responses_submitted": 0,
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "SUB-008",
                "trial_id": DUPIXENT_TRIAL,
                "authority": RegulatoryAuthority.FDA,
                "submission_type": SubmissionType.SAFETY_REPORT,
                "submission_number": "SR-2025-DUP-001",
                "title": "Dupixent DSUR 2025",
                "status": SubmissionStatus.SUBMITTED,
                "planned_date": now - timedelta(days=20),
                "actual_submission_date": now - timedelta(days=18),
                "lead_reviewer": "Dr. Angela Martinez",
                "assigned_team": ["Dr. Angela Martinez", "PV Specialist"],
                "documents_included": ["DSUR", "Line Listings"],
                "questions_received": 0,
                "responses_submitted": 0,
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "SUB-009",
                "trial_id": LIBTAYO_TRIAL,
                "authority": RegulatoryAuthority.HEALTH_CANADA,
                "submission_type": SubmissionType.CTA,
                "submission_number": "CTA-CA-2025-0198",
                "title": "Libtayo CTA Amendment for Combination Therapy",
                "status": SubmissionStatus.SUBMITTED,
                "planned_date": now - timedelta(days=45),
                "actual_submission_date": now - timedelta(days=40),
                "lead_reviewer": "Dr. Natalie Wong",
                "assigned_team": ["Dr. Natalie Wong", "Canada Regulatory Liaison"],
                "documents_included": ["CTA Amendment", "Updated Protocol", "Updated IB"],
                "questions_received": 2,
                "responses_submitted": 1,
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "SUB-010",
                "trial_id": DUPIXENT_TRIAL,
                "authority": RegulatoryAuthority.MHRA,
                "submission_type": SubmissionType.AMENDMENT,
                "submission_number": "AMD-UK-2025-DUP",
                "title": "Dupixent Protocol Amendment for MHRA",
                "status": SubmissionStatus.WITHDRAWN,
                "planned_date": now - timedelta(days=60),
                "actual_submission_date": now - timedelta(days=55),
                "lead_reviewer": "Dr. Patricia Sullivan",
                "assigned_team": ["Dr. Patricia Sullivan"],
                "documents_included": ["Protocol Amendment v3"],
                "questions_received": 0,
                "responses_submitted": 0,
                "created_at": now - timedelta(days=70),
            },
        ]

        for sub in submissions_data:
            self._submissions[sub["id"]] = RegulatorySubmissionTracker(**sub)

        # --- 10 Compliance Gaps ---
        gaps_data = [
            {
                "id": "GAP-001",
                "trial_id": EYLEA_TRIAL,
                "authority": RegulatoryAuthority.FDA,
                "regulation_reference": "21 CFR 312.32 - IND Safety Reporting",
                "gap_description": "Delayed IND safety report submissions; 3 reports exceeded 15-day reporting window.",
                "severity": GapSeverity.MAJOR,
                "status": GapStatus.REMEDIATION_PLANNED,
                "identified_date": now - timedelta(days=60),
                "identified_by": "Dr. Sarah Chen",
                "remediation_plan": "Implement automated safety report tracking system with escalation alerts.",
                "remediation_owner": "Dr. Michael Patel",
                "target_resolution_date": now + timedelta(days=30),
            },
            {
                "id": "GAP-002",
                "trial_id": EYLEA_TRIAL,
                "authority": RegulatoryAuthority.EMA,
                "regulation_reference": "EU CTR Article 42 - Annual Safety Reporting",
                "gap_description": "DSUR did not include all required safety data from EU sites.",
                "severity": GapSeverity.MAJOR,
                "status": GapStatus.IN_PROGRESS,
                "identified_date": now - timedelta(days=45),
                "identified_by": "Dr. James Rodriguez",
                "remediation_plan": "Revise DSUR data collection process and add QC checks.",
                "remediation_owner": "Dr. James Rodriguez",
                "target_resolution_date": now + timedelta(days=15),
            },
            {
                "id": "GAP-003",
                "trial_id": DUPIXENT_TRIAL,
                "authority": RegulatoryAuthority.FDA,
                "regulation_reference": "21 CFR 50 - Informed Consent",
                "gap_description": "Informed consent forms at 2 sites did not include updated risk language per latest IB revision.",
                "severity": GapSeverity.CRITICAL,
                "status": GapStatus.RESOLVED,
                "identified_date": now - timedelta(days=90),
                "identified_by": "Dr. Laura Kim",
                "remediation_plan": "Re-consent all affected subjects with updated ICF.",
                "remediation_owner": "Dr. Laura Kim",
                "target_resolution_date": now - timedelta(days=30),
                "resolved_date": now - timedelta(days=35),
                "evidence_of_closure": "All 47 subjects re-consented. Updated ICFs filed. IRB notification submitted.",
            },
            {
                "id": "GAP-004",
                "trial_id": DUPIXENT_TRIAL,
                "authority": RegulatoryAuthority.PMDA,
                "regulation_reference": "Japanese GCP Ordinance Article 32",
                "gap_description": "CRF completion rates at Japan sites below 85% threshold.",
                "severity": GapSeverity.MINOR,
                "status": GapStatus.IN_PROGRESS,
                "identified_date": now - timedelta(days=30),
                "identified_by": "Dr. David Nakamura",
                "remediation_plan": "Deploy additional CRA support to Japan sites. Implement weekly data entry tracking.",
                "remediation_owner": "Dr. David Nakamura",
                "target_resolution_date": now + timedelta(days=45),
            },
            {
                "id": "GAP-005",
                "trial_id": LIBTAYO_TRIAL,
                "authority": RegulatoryAuthority.FDA,
                "regulation_reference": "21 CFR 312.62 - Investigator Records",
                "gap_description": "Source document verification revealed discrepancies at 3 sites between CRF entries and source records for tumor measurements.",
                "severity": GapSeverity.CRITICAL,
                "status": GapStatus.REMEDIATION_PLANNED,
                "identified_date": now - timedelta(days=20),
                "identified_by": "Dr. Catherine Liu",
                "remediation_plan": "Conduct comprehensive SDV audit at affected sites. Implement centralized imaging review.",
                "remediation_owner": "Dr. Andrew Foster",
                "target_resolution_date": now + timedelta(days=60),
            },
            {
                "id": "GAP-006",
                "trial_id": LIBTAYO_TRIAL,
                "authority": RegulatoryAuthority.EMA,
                "regulation_reference": "ICH E6(R2) Section 5.18 - Monitoring",
                "gap_description": "Risk-based monitoring plan not updated after protocol amendment to reflect new safety endpoints.",
                "severity": GapSeverity.MAJOR,
                "status": GapStatus.IDENTIFIED,
                "identified_date": now - timedelta(days=10),
                "identified_by": "Dr. Natalie Wong",
            },
            {
                "id": "GAP-007",
                "trial_id": EYLEA_TRIAL,
                "authority": RegulatoryAuthority.HEALTH_CANADA,
                "regulation_reference": "C.05.012 - Clinical Trial Application Records",
                "gap_description": "TMF filing at Canadian sites incomplete for investigator delegation logs.",
                "severity": GapSeverity.MINOR,
                "status": GapStatus.RESOLVED,
                "identified_date": now - timedelta(days=50),
                "identified_by": "Dr. Thomas Berg",
                "remediation_plan": "Complete TMF filing and implement monthly filing audit.",
                "remediation_owner": "Dr. Thomas Berg",
                "target_resolution_date": now - timedelta(days=20),
                "resolved_date": now - timedelta(days=22),
                "evidence_of_closure": "All delegation logs filed. Monthly audit process documented.",
            },
            {
                "id": "GAP-008",
                "trial_id": DUPIXENT_TRIAL,
                "authority": RegulatoryAuthority.MHRA,
                "regulation_reference": "UK SI 2004/1031 - Clinical Trials Regulations",
                "gap_description": "Substantial amendment not submitted within required timeframe for UK sites.",
                "severity": GapSeverity.MAJOR,
                "status": GapStatus.ACCEPTED,
                "identified_date": now - timedelta(days=40),
                "identified_by": "Dr. Robert Williams",
                "remediation_plan": "Risk accepted due to low patient impact. Documented in quality management system.",
                "remediation_owner": "Dr. Robert Williams",
            },
            {
                "id": "GAP-009",
                "trial_id": LIBTAYO_TRIAL,
                "authority": RegulatoryAuthority.FDA,
                "regulation_reference": "21 CFR 11 - Electronic Records",
                "gap_description": "EDC system audit trail gaps identified during internal audit.",
                "severity": GapSeverity.MAJOR,
                "status": GapStatus.IN_PROGRESS,
                "identified_date": now - timedelta(days=25),
                "identified_by": "Dr. Gregory Harris",
                "remediation_plan": "EDC vendor to deploy patch. Conduct retrospective audit trail review.",
                "remediation_owner": "Dr. Gregory Harris",
                "target_resolution_date": now + timedelta(days=20),
            },
            {
                "id": "GAP-010",
                "trial_id": EYLEA_TRIAL,
                "authority": RegulatoryAuthority.TGA,
                "regulation_reference": "Therapeutic Goods Act 1989 - Clinical Trial Notification",
                "gap_description": "CTN update not filed within 28-day window after protocol amendment.",
                "severity": GapSeverity.MINOR,
                "status": GapStatus.RESOLVED,
                "identified_date": now - timedelta(days=35),
                "identified_by": "Dr. Maria Santos",
                "remediation_plan": "Filed late CTN update with explanation letter.",
                "remediation_owner": "Dr. Maria Santos",
                "target_resolution_date": now - timedelta(days=25),
                "resolved_date": now - timedelta(days=27),
                "evidence_of_closure": "CTN update accepted by TGA. No further action required.",
            },
        ]

        for gap in gaps_data:
            self._compliance_gaps[gap["id"]] = ComplianceGap(**gap)

        # --- 10 Authority Communications ---
        comms_data = [
            {
                "id": "COMM-001",
                "submission_id": "SUB-001",
                "trial_id": EYLEA_TRIAL,
                "authority": RegulatoryAuthority.FDA,
                "direction": "inbound",
                "subject": "Information Request for BLA-761999",
                "content_summary": "FDA requests additional stability data for 8mg formulation and updated comparability protocol.",
                "communication_date": now - timedelta(days=60),
                "response_deadline": now - timedelta(days=30),
                "responded": True,
                "response_date": now - timedelta(days=35),
                "handled_by": "Dr. Sarah Chen",
            },
            {
                "id": "COMM-002",
                "submission_id": "SUB-001",
                "trial_id": EYLEA_TRIAL,
                "authority": RegulatoryAuthority.FDA,
                "direction": "outbound",
                "subject": "Response to Information Request for BLA-761999",
                "content_summary": "Provided requested stability data, comparability protocol, and additional characterization studies.",
                "communication_date": now - timedelta(days=35),
                "handled_by": "Dr. Sarah Chen",
            },
            {
                "id": "COMM-003",
                "submission_id": "SUB-004",
                "trial_id": DUPIXENT_TRIAL,
                "authority": RegulatoryAuthority.PMDA,
                "direction": "inbound",
                "subject": "Questions on Dupixent Pediatric CTA",
                "content_summary": "PMDA raised 5 questions regarding pediatric dosing rationale and safety monitoring plan.",
                "communication_date": now - timedelta(days=40),
                "response_deadline": now - timedelta(days=10),
                "responded": True,
                "response_date": now - timedelta(days=15),
                "handled_by": "Dr. David Nakamura",
            },
            {
                "id": "COMM-004",
                "trial_id": LIBTAYO_TRIAL,
                "authority": RegulatoryAuthority.FDA,
                "direction": "outbound",
                "subject": "Pre-BLA Meeting Request for Libtayo NSCLC",
                "content_summary": "Requested Type B pre-BLA meeting to discuss clinical development strategy for first-line NSCLC indication.",
                "communication_date": now - timedelta(days=25),
                "handled_by": "Dr. Catherine Liu",
            },
            {
                "id": "COMM-005",
                "trial_id": LIBTAYO_TRIAL,
                "authority": RegulatoryAuthority.FDA,
                "direction": "inbound",
                "subject": "Pre-BLA Meeting Scheduling",
                "content_summary": "FDA confirmed Type B meeting scheduled for 60 days from request date.",
                "communication_date": now - timedelta(days=20),
                "response_deadline": now + timedelta(days=10),
                "responded": False,
                "handled_by": "Dr. Catherine Liu",
            },
            {
                "id": "COMM-006",
                "submission_id": "SUB-002",
                "trial_id": EYLEA_TRIAL,
                "authority": RegulatoryAuthority.EMA,
                "direction": "inbound",
                "subject": "Day 120 List of Questions for EYLEA HD MAA",
                "content_summary": "EMA CHMP issued Day 120 list of questions covering clinical efficacy, safety, and quality modules.",
                "communication_date": now - timedelta(days=15),
                "response_deadline": now + timedelta(days=45),
                "responded": False,
                "handled_by": "Dr. James Rodriguez",
            },
            {
                "id": "COMM-007",
                "submission_id": "SUB-009",
                "trial_id": LIBTAYO_TRIAL,
                "authority": RegulatoryAuthority.HEALTH_CANADA,
                "direction": "inbound",
                "subject": "NOL Conditions for Libtayo CTA Amendment",
                "content_summary": "Health Canada issued No Objection Letter with conditions requiring enhanced safety monitoring.",
                "communication_date": now - timedelta(days=10),
                "response_deadline": now + timedelta(days=20),
                "responded": False,
                "handled_by": "Dr. Natalie Wong",
            },
            {
                "id": "COMM-008",
                "trial_id": DUPIXENT_TRIAL,
                "authority": RegulatoryAuthority.MHRA,
                "direction": "outbound",
                "subject": "Notification of Protocol Amendment Withdrawal",
                "content_summary": "Notified MHRA of withdrawal of substantial amendment following internal review decision.",
                "communication_date": now - timedelta(days=50),
                "handled_by": "Dr. Patricia Sullivan",
            },
            {
                "id": "COMM-009",
                "trial_id": EYLEA_TRIAL,
                "authority": RegulatoryAuthority.TGA,
                "direction": "outbound",
                "subject": "Late CTN Update Submission with Explanation",
                "content_summary": "Submitted late CTN update with explanation letter regarding delayed protocol amendment notification.",
                "communication_date": now - timedelta(days=27),
                "handled_by": "Dr. Maria Santos",
            },
            {
                "id": "COMM-010",
                "trial_id": DUPIXENT_TRIAL,
                "authority": RegulatoryAuthority.FDA,
                "direction": "inbound",
                "subject": "DSUR Acknowledgment for Dupixent",
                "content_summary": "FDA acknowledged receipt of Dupixent DSUR 2025. No additional information requested.",
                "communication_date": now - timedelta(days=5),
                "responded": True,
                "response_date": now - timedelta(days=5),
                "handled_by": "Dr. Angela Martinez",
            },
        ]

        for comm in comms_data:
            self._communications[comm["id"]] = AuthorityCommunication(**comm)

    # ------------------------------------------------------------------
    # Intelligence Item Management
    # ------------------------------------------------------------------

    def list_intelligence_items(
        self,
        *,
        authority: RegulatoryAuthority | None = None,
        intelligence_type: IntelligenceType | None = None,
        status: IntelligenceStatus | None = None,
        impact_level: ImpactLevel | None = None,
    ) -> list[RegulatoryIntelligenceItem]:
        """List intelligence items with optional filters."""
        with self._lock:
            result = list(self._intelligence_items.values())

        if authority is not None:
            result = [i for i in result if i.authority == authority]
        if intelligence_type is not None:
            result = [i for i in result if i.intelligence_type == intelligence_type]
        if status is not None:
            result = [i for i in result if i.status == status]
        if impact_level is not None:
            result = [i for i in result if i.impact_level == impact_level]

        return sorted(result, key=lambda i: i.published_date, reverse=True)

    def get_intelligence_item(self, item_id: str) -> RegulatoryIntelligenceItem | None:
        """Get a single intelligence item by ID."""
        with self._lock:
            return self._intelligence_items.get(item_id)

    def create_intelligence_item(self, payload: IntelligenceItemCreate) -> RegulatoryIntelligenceItem:
        """Create a new intelligence item."""
        now = datetime.now(timezone.utc)
        item_id = f"RI-{uuid4().hex[:8].upper()}"
        item = RegulatoryIntelligenceItem(
            id=item_id,
            authority=payload.authority,
            intelligence_type=payload.intelligence_type,
            title=payload.title,
            summary=payload.summary,
            published_date=payload.published_date,
            effective_date=payload.effective_date,
            impact_level=payload.impact_level,
            affected_trials=payload.affected_trials,
            affected_therapeutic_areas=payload.affected_therapeutic_areas,
            status=IntelligenceStatus.NEW,
            source_url=payload.source_url,
            created_at=now,
        )
        with self._lock:
            self._intelligence_items[item_id] = item
        logger.info("Created intelligence item %s: %s", item_id, payload.title)
        return item

    def update_intelligence_item(
        self, item_id: str, payload: IntelligenceItemUpdate
    ) -> RegulatoryIntelligenceItem | None:
        """Update an existing intelligence item."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._intelligence_items.get(item_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            # Auto-set assessed_date when assessed_by is provided
            if "assessed_by" in updates and updates["assessed_by"] is not None:
                if existing.assessed_date is None:
                    updates["assessed_date"] = now
            data.update(updates)
            updated = RegulatoryIntelligenceItem(**data)
            self._intelligence_items[item_id] = updated
        return updated

    def delete_intelligence_item(self, item_id: str) -> bool:
        """Delete an intelligence item. Returns True if deleted."""
        with self._lock:
            if item_id in self._intelligence_items:
                del self._intelligence_items[item_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Submission Tracker Management
    # ------------------------------------------------------------------

    def list_submissions(
        self,
        *,
        trial_id: str | None = None,
        authority: RegulatoryAuthority | None = None,
        status: SubmissionStatus | None = None,
    ) -> list[RegulatorySubmissionTracker]:
        """List submission trackers with optional filters."""
        with self._lock:
            result = list(self._submissions.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if authority is not None:
            result = [s for s in result if s.authority == authority]
        if status is not None:
            result = [s for s in result if s.status == status]

        return sorted(result, key=lambda s: s.planned_date, reverse=True)

    def get_submission(self, submission_id: str) -> RegulatorySubmissionTracker | None:
        """Get a single submission tracker by ID."""
        with self._lock:
            return self._submissions.get(submission_id)

    def create_submission(self, payload: SubmissionTrackerCreate) -> RegulatorySubmissionTracker:
        """Create a new submission tracker."""
        now = datetime.now(timezone.utc)
        sub_id = f"SUB-{uuid4().hex[:8].upper()}"
        submission = RegulatorySubmissionTracker(
            id=sub_id,
            trial_id=payload.trial_id,
            authority=payload.authority,
            submission_type=payload.submission_type,
            submission_number=payload.submission_number,
            title=payload.title,
            status=SubmissionStatus.DRAFTING,
            planned_date=payload.planned_date,
            target_approval_date=payload.target_approval_date,
            lead_reviewer=payload.lead_reviewer,
            assigned_team=payload.assigned_team,
            created_at=now,
        )
        with self._lock:
            self._submissions[sub_id] = submission
        logger.info("Created submission tracker %s: %s", sub_id, payload.title)
        return submission

    def update_submission(
        self, submission_id: str, payload: SubmissionTrackerUpdate
    ) -> RegulatorySubmissionTracker | None:
        """Update an existing submission tracker."""
        with self._lock:
            existing = self._submissions.get(submission_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = RegulatorySubmissionTracker(**data)
            self._submissions[submission_id] = updated
        return updated

    def delete_submission(self, submission_id: str) -> bool:
        """Delete a submission tracker. Returns True if deleted."""
        with self._lock:
            if submission_id in self._submissions:
                del self._submissions[submission_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Compliance Gap Management
    # ------------------------------------------------------------------

    def list_compliance_gaps(
        self,
        *,
        trial_id: str | None = None,
        authority: RegulatoryAuthority | None = None,
        severity: GapSeverity | None = None,
        status: GapStatus | None = None,
    ) -> list[ComplianceGap]:
        """List compliance gaps with optional filters."""
        with self._lock:
            result = list(self._compliance_gaps.values())

        if trial_id is not None:
            result = [g for g in result if g.trial_id == trial_id]
        if authority is not None:
            result = [g for g in result if g.authority == authority]
        if severity is not None:
            result = [g for g in result if g.severity == severity]
        if status is not None:
            result = [g for g in result if g.status == status]

        return sorted(result, key=lambda g: g.identified_date, reverse=True)

    def get_compliance_gap(self, gap_id: str) -> ComplianceGap | None:
        """Get a single compliance gap by ID."""
        with self._lock:
            return self._compliance_gaps.get(gap_id)

    def create_compliance_gap(self, payload: ComplianceGapCreate) -> ComplianceGap:
        """Create a new compliance gap."""
        now = datetime.now(timezone.utc)
        gap_id = f"GAP-{uuid4().hex[:8].upper()}"
        gap = ComplianceGap(
            id=gap_id,
            trial_id=payload.trial_id,
            authority=payload.authority,
            regulation_reference=payload.regulation_reference,
            gap_description=payload.gap_description,
            severity=payload.severity,
            status=GapStatus.IDENTIFIED,
            identified_date=now,
            identified_by=payload.identified_by,
            remediation_plan=payload.remediation_plan,
            remediation_owner=payload.remediation_owner,
            target_resolution_date=payload.target_resolution_date,
        )
        with self._lock:
            self._compliance_gaps[gap_id] = gap
        logger.info("Created compliance gap %s for trial %s", gap_id, payload.trial_id)
        return gap

    def update_compliance_gap(
        self, gap_id: str, payload: ComplianceGapUpdate
    ) -> ComplianceGap | None:
        """Update an existing compliance gap."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._compliance_gaps.get(gap_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            # Auto-set resolved_date when status changes to resolved
            if "status" in updates and updates["status"] == GapStatus.RESOLVED:
                if existing.resolved_date is None:
                    updates["resolved_date"] = now
            data.update(updates)
            updated = ComplianceGap(**data)
            self._compliance_gaps[gap_id] = updated
        return updated

    def delete_compliance_gap(self, gap_id: str) -> bool:
        """Delete a compliance gap. Returns True if deleted."""
        with self._lock:
            if gap_id in self._compliance_gaps:
                del self._compliance_gaps[gap_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Authority Communication Management
    # ------------------------------------------------------------------

    def list_communications(
        self,
        *,
        trial_id: str | None = None,
        authority: RegulatoryAuthority | None = None,
        submission_id: str | None = None,
    ) -> list[AuthorityCommunication]:
        """List authority communications with optional filters."""
        with self._lock:
            result = list(self._communications.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]
        if authority is not None:
            result = [c for c in result if c.authority == authority]
        if submission_id is not None:
            result = [c for c in result if c.submission_id == submission_id]

        return sorted(result, key=lambda c: c.communication_date, reverse=True)

    def get_communication(self, comm_id: str) -> AuthorityCommunication | None:
        """Get a single communication by ID."""
        with self._lock:
            return self._communications.get(comm_id)

    def create_communication(self, payload: AuthorityCommunicationCreate) -> AuthorityCommunication:
        """Create a new authority communication."""
        comm_id = f"COMM-{uuid4().hex[:8].upper()}"
        comm = AuthorityCommunication(
            id=comm_id,
            submission_id=payload.submission_id,
            trial_id=payload.trial_id,
            authority=payload.authority,
            direction=payload.direction,
            subject=payload.subject,
            content_summary=payload.content_summary,
            communication_date=payload.communication_date,
            response_deadline=payload.response_deadline,
            handled_by=payload.handled_by,
        )
        with self._lock:
            self._communications[comm_id] = comm
        logger.info("Created communication %s: %s", comm_id, payload.subject)
        return comm

    def update_communication(
        self, comm_id: str, payload: AuthorityCommunicationUpdate
    ) -> AuthorityCommunication | None:
        """Update an existing communication."""
        with self._lock:
            existing = self._communications.get(comm_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = AuthorityCommunication(**data)
            self._communications[comm_id] = updated
        return updated

    def delete_communication(self, comm_id: str) -> bool:
        """Delete a communication. Returns True if deleted."""
        with self._lock:
            if comm_id in self._communications:
                del self._communications[comm_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self) -> RegulatoryIntelligenceMetrics:
        """Compute aggregated regulatory intelligence metrics."""
        now = datetime.now(timezone.utc)

        with self._lock:
            items = list(self._intelligence_items.values())
            submissions = list(self._submissions.values())
            gaps = list(self._compliance_gaps.values())
            comms = list(self._communications.values())

        # Intelligence items breakdown
        items_by_authority: dict[str, int] = {}
        items_by_type: dict[str, int] = {}
        items_by_status: dict[str, int] = {}
        items_by_impact: dict[str, int] = {}
        for item in items:
            key = item.authority.value
            items_by_authority[key] = items_by_authority.get(key, 0) + 1
            key = item.intelligence_type.value
            items_by_type[key] = items_by_type.get(key, 0) + 1
            key = item.status.value
            items_by_status[key] = items_by_status.get(key, 0) + 1
            key = item.impact_level.value
            items_by_impact[key] = items_by_impact.get(key, 0) + 1

        # Submissions breakdown
        submissions_by_status: dict[str, int] = {}
        submissions_by_authority: dict[str, int] = {}
        pending_submissions = 0
        for sub in submissions:
            key = sub.status.value
            submissions_by_status[key] = submissions_by_status.get(key, 0) + 1
            key = sub.authority.value
            submissions_by_authority[key] = submissions_by_authority.get(key, 0) + 1
            if sub.status in (
                SubmissionStatus.DRAFTING,
                SubmissionStatus.INTERNAL_REVIEW,
                SubmissionStatus.SUBMITTED,
                SubmissionStatus.UNDER_REVIEW,
                SubmissionStatus.QUESTIONS_RECEIVED,
            ):
                pending_submissions += 1

        # Compliance gaps breakdown
        open_gaps = sum(
            1 for g in gaps
            if g.status not in (GapStatus.RESOLVED, GapStatus.ACCEPTED)
        )
        critical_gaps = sum(
            1 for g in gaps
            if g.severity == GapSeverity.CRITICAL
            and g.status not in (GapStatus.RESOLVED, GapStatus.ACCEPTED)
        )
        gaps_by_severity: dict[str, int] = {}
        for g in gaps:
            key = g.severity.value
            gaps_by_severity[key] = gaps_by_severity.get(key, 0) + 1

        # Communications breakdown
        pending_responses = sum(
            1 for c in comms
            if c.response_deadline is not None
            and not c.responded
        )
        overdue_responses = sum(
            1 for c in comms
            if c.response_deadline is not None
            and not c.responded
            and c.response_deadline < now
        )

        return RegulatoryIntelligenceMetrics(
            total_intelligence_items=len(items),
            items_by_authority=items_by_authority,
            items_by_type=items_by_type,
            items_by_status=items_by_status,
            items_by_impact=items_by_impact,
            total_submissions=len(submissions),
            submissions_by_status=submissions_by_status,
            submissions_by_authority=submissions_by_authority,
            pending_submissions=pending_submissions,
            total_compliance_gaps=len(gaps),
            open_gaps=open_gaps,
            critical_gaps=critical_gaps,
            gaps_by_severity=gaps_by_severity,
            total_communications=len(comms),
            pending_responses=pending_responses,
            overdue_responses=overdue_responses,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: RegulatoryIntelligenceService | None = None
_instance_lock = threading.Lock()


def get_regulatory_intelligence_service() -> RegulatoryIntelligenceService:
    """Return the singleton RegulatoryIntelligenceService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = RegulatoryIntelligenceService()
    return _instance


def reset_regulatory_intelligence_service() -> RegulatoryIntelligenceService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = RegulatoryIntelligenceService()
    return _instance
