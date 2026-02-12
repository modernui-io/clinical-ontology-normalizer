"""Investigator Brochure Management Service (IB-MGMT).

Manages investigator brochure operations: IB version tracking,
safety update records, distribution management, revision history,
and acknowledgment records with compliance metrics.

Usage:
    from app.services.investigator_brochure_service import (
        get_investigator_brochure_service,
    )

    svc = get_investigator_brochure_service()
    versions = svc.list_ib_versions()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.investigator_brochure import (
    AcknowledgmentRecord,
    AcknowledgmentRecordCreate,
    AcknowledgmentRecordUpdate,
    AcknowledgmentStatus,
    DistributionMethod,
    DistributionRecord,
    DistributionRecordCreate,
    DistributionRecordUpdate,
    IBStatus,
    IBVersion,
    IBVersionCreate,
    IBVersionUpdate,
    InvestigatorBrochureMetrics,
    RevisionHistory,
    RevisionHistoryCreate,
    RevisionHistoryUpdate,
    RevisionScope,
    SafetyUpdate,
    SafetyUpdateCreate,
    SafetyUpdateUpdate,
    UpdateType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class InvestigatorBrochureService:
    """In-memory Investigator Brochure Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._ib_versions: dict[str, IBVersion] = {}
        self._safety_updates: dict[str, SafetyUpdate] = {}
        self._distribution_records: dict[str, DistributionRecord] = {}
        self._revision_histories: dict[str, RevisionHistory] = {}
        self._acknowledgment_records: dict[str, AcknowledgmentRecord] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic investigator brochure data."""
        now = datetime.now(timezone.utc)

        # --- 12 IB Versions ---
        versions_data = [
            {
                "id": "IBV-001",
                "trial_id": EYLEA_TRIAL,
                "version_number": "1.0",
                "edition_number": 1,
                "status": IBStatus.SUPERSEDED,
                "effective_date": now - timedelta(days=720),
                "superseded_date": now - timedelta(days=360),
                "page_count": 185,
                "sections_updated": [],
                "preclinical_data_current": True,
                "clinical_data_current": False,
                "safety_data_cutoff": now - timedelta(days=750),
                "approved_by": "Dr. William Torres",
                "approval_date": now - timedelta(days=725),
                "authored_by": "Dr. Sarah Chen",
                "regulatory_references": ["ICH E6(R2)", "21 CFR 312.23"],
                "notes": "Initial IB for EYLEA Phase III program.",
                "created_at": now - timedelta(days=730),
            },
            {
                "id": "IBV-002",
                "trial_id": EYLEA_TRIAL,
                "version_number": "2.0",
                "edition_number": 2,
                "status": IBStatus.SUPERSEDED,
                "effective_date": now - timedelta(days=360),
                "superseded_date": now - timedelta(days=90),
                "page_count": 210,
                "sections_updated": ["Section 5.3 Clinical Efficacy", "Section 6.1 Adverse Events"],
                "preclinical_data_current": True,
                "clinical_data_current": True,
                "safety_data_cutoff": now - timedelta(days=380),
                "approved_by": "Dr. William Torres",
                "approval_date": now - timedelta(days=365),
                "authored_by": "Dr. Sarah Chen",
                "regulatory_references": ["ICH E6(R2)", "21 CFR 312.23", "EMA/CHMP/ICH/135/1995"],
                "notes": "Major update incorporating Phase II results and updated safety profile.",
                "created_at": now - timedelta(days=370),
            },
            {
                "id": "IBV-003",
                "trial_id": EYLEA_TRIAL,
                "version_number": "3.0",
                "edition_number": 3,
                "status": IBStatus.DISTRIBUTED,
                "effective_date": now - timedelta(days=90),
                "superseded_date": None,
                "page_count": 245,
                "sections_updated": ["Section 4.2 Pharmacokinetics", "Section 5.3 Clinical Efficacy", "Section 6.2 Serious Adverse Events"],
                "preclinical_data_current": True,
                "clinical_data_current": True,
                "safety_data_cutoff": now - timedelta(days=100),
                "approved_by": "Dr. William Torres",
                "approval_date": now - timedelta(days=95),
                "authored_by": "Dr. Sarah Chen",
                "regulatory_references": ["ICH E6(R2)", "21 CFR 312.23", "EMA/CHMP/ICH/135/1995"],
                "notes": "Current version with interim efficacy data and updated safety information.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "IBV-004",
                "trial_id": DUPIXENT_TRIAL,
                "version_number": "1.0",
                "edition_number": 1,
                "status": IBStatus.SUPERSEDED,
                "effective_date": now - timedelta(days=540),
                "superseded_date": now - timedelta(days=180),
                "page_count": 165,
                "sections_updated": [],
                "preclinical_data_current": True,
                "clinical_data_current": False,
                "safety_data_cutoff": now - timedelta(days=560),
                "approved_by": "Dr. David Patel",
                "approval_date": now - timedelta(days=545),
                "authored_by": "Dr. Maria Lopez",
                "regulatory_references": ["ICH E6(R2)", "21 CFR 312.23"],
                "notes": "Initial IB for DUPIXENT dermatitis program.",
                "created_at": now - timedelta(days=550),
            },
            {
                "id": "IBV-005",
                "trial_id": DUPIXENT_TRIAL,
                "version_number": "2.0",
                "edition_number": 2,
                "status": IBStatus.DISTRIBUTED,
                "effective_date": now - timedelta(days=180),
                "superseded_date": None,
                "page_count": 198,
                "sections_updated": ["Section 5.1 Clinical Pharmacology", "Section 6.1 Adverse Events", "Section 7 Precautions"],
                "preclinical_data_current": True,
                "clinical_data_current": True,
                "safety_data_cutoff": now - timedelta(days=200),
                "approved_by": "Dr. David Patel",
                "approval_date": now - timedelta(days=185),
                "authored_by": "Dr. Maria Lopez",
                "regulatory_references": ["ICH E6(R2)", "21 CFR 312.23", "EMA/CHMP/ICH/135/1995"],
                "notes": "Updated with Phase II safety data and dose-response findings.",
                "created_at": now - timedelta(days=190),
            },
            {
                "id": "IBV-006",
                "trial_id": DUPIXENT_TRIAL,
                "version_number": "3.0",
                "edition_number": 3,
                "status": IBStatus.UNDER_REVIEW,
                "effective_date": None,
                "superseded_date": None,
                "page_count": 220,
                "sections_updated": ["Section 5.3 Clinical Efficacy", "Section 6.2 Serious Adverse Events", "Section 8 Summary of Data"],
                "preclinical_data_current": True,
                "clinical_data_current": True,
                "safety_data_cutoff": now - timedelta(days=30),
                "approved_by": None,
                "approval_date": None,
                "authored_by": "Dr. Robert Kim",
                "regulatory_references": ["ICH E6(R2)", "21 CFR 312.23"],
                "notes": "Pending review. Incorporates sample size re-estimation rationale.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "IBV-007",
                "trial_id": LIBTAYO_TRIAL,
                "version_number": "1.0",
                "edition_number": 1,
                "status": IBStatus.SUPERSEDED,
                "effective_date": now - timedelta(days=600),
                "superseded_date": now - timedelta(days=300),
                "page_count": 175,
                "sections_updated": [],
                "preclinical_data_current": True,
                "clinical_data_current": False,
                "safety_data_cutoff": now - timedelta(days=620),
                "approved_by": "Dr. William Torres",
                "approval_date": now - timedelta(days=605),
                "authored_by": "Dr. Angela Park",
                "regulatory_references": ["ICH E6(R2)", "21 CFR 312.23"],
                "notes": "Initial IB for LIBTAYO oncology program.",
                "created_at": now - timedelta(days=610),
            },
            {
                "id": "IBV-008",
                "trial_id": LIBTAYO_TRIAL,
                "version_number": "2.0",
                "edition_number": 2,
                "status": IBStatus.SUPERSEDED,
                "effective_date": now - timedelta(days=300),
                "superseded_date": now - timedelta(days=120),
                "page_count": 205,
                "sections_updated": ["Section 4.3 Immunogenicity", "Section 5.2 Dose Selection", "Section 6.1 Adverse Events"],
                "preclinical_data_current": True,
                "clinical_data_current": True,
                "safety_data_cutoff": now - timedelta(days=320),
                "approved_by": "Dr. William Torres",
                "approval_date": now - timedelta(days=305),
                "authored_by": "Dr. Angela Park",
                "regulatory_references": ["ICH E6(R2)", "21 CFR 312.23", "EMA/CHMP/ICH/135/1995"],
                "notes": "Updated with dose-finding results and immune-related AE data.",
                "created_at": now - timedelta(days=310),
            },
            {
                "id": "IBV-009",
                "trial_id": LIBTAYO_TRIAL,
                "version_number": "3.0",
                "edition_number": 3,
                "status": IBStatus.DISTRIBUTED,
                "effective_date": now - timedelta(days=120),
                "superseded_date": None,
                "page_count": 260,
                "sections_updated": ["Section 5.3 Clinical Efficacy", "Section 6.2 Serious Adverse Events", "Section 6.3 Immune-Related AEs"],
                "preclinical_data_current": True,
                "clinical_data_current": True,
                "safety_data_cutoff": now - timedelta(days=130),
                "approved_by": "Dr. William Torres",
                "approval_date": now - timedelta(days=125),
                "authored_by": "Dr. Angela Park",
                "regulatory_references": ["ICH E6(R2)", "21 CFR 312.23", "EMA/CHMP/ICH/135/1995"],
                "notes": "Current version post arm-drop adaptation. Updated safety profile for high-dose arm.",
                "created_at": now - timedelta(days=130),
            },
            {
                "id": "IBV-010",
                "trial_id": EYLEA_TRIAL,
                "version_number": "3.1",
                "edition_number": 4,
                "status": IBStatus.DRAFT,
                "effective_date": None,
                "superseded_date": None,
                "page_count": 250,
                "sections_updated": ["Section 6.4 Post-Marketing Safety Data"],
                "preclinical_data_current": True,
                "clinical_data_current": True,
                "safety_data_cutoff": now - timedelta(days=10),
                "approved_by": None,
                "approval_date": None,
                "authored_by": "Dr. Sarah Chen",
                "regulatory_references": ["ICH E6(R2)"],
                "notes": "Draft addendum for post-marketing safety data integration.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "IBV-011",
                "trial_id": LIBTAYO_TRIAL,
                "version_number": "3.1",
                "edition_number": 4,
                "status": IBStatus.APPROVED,
                "effective_date": now - timedelta(days=15),
                "superseded_date": None,
                "page_count": 265,
                "sections_updated": ["Section 6.3 Immune-Related AEs"],
                "preclinical_data_current": True,
                "clinical_data_current": True,
                "safety_data_cutoff": now - timedelta(days=20),
                "approved_by": "Dr. William Torres",
                "approval_date": now - timedelta(days=18),
                "authored_by": "Dr. Angela Park",
                "regulatory_references": ["ICH E6(R2)", "21 CFR 312.23"],
                "notes": "Safety addendum approved, pending distribution.",
                "created_at": now - timedelta(days=22),
            },
            {
                "id": "IBV-012",
                "trial_id": DUPIXENT_TRIAL,
                "version_number": "1.1",
                "edition_number": 1,
                "status": IBStatus.RETIRED,
                "effective_date": now - timedelta(days=500),
                "superseded_date": now - timedelta(days=540),
                "page_count": 170,
                "sections_updated": ["Section 3.2 Toxicology"],
                "preclinical_data_current": True,
                "clinical_data_current": False,
                "safety_data_cutoff": now - timedelta(days=520),
                "approved_by": "Dr. David Patel",
                "approval_date": now - timedelta(days=505),
                "authored_by": "Dr. Maria Lopez",
                "regulatory_references": ["ICH E6(R2)"],
                "notes": "Retired minor edition. Superseded by v2.0.",
                "created_at": now - timedelta(days=510),
            },
        ]

        for v in versions_data:
            self._ib_versions[v["id"]] = IBVersion(**v)

        # --- 12 Safety Updates ---
        safety_data = [
            {
                "id": "SU-001",
                "trial_id": EYLEA_TRIAL,
                "ib_version_id": "IBV-002",
                "update_type": UpdateType.SAFETY_DRIVEN,
                "update_date": now - timedelta(days=350),
                "safety_signal": "Increased incidence of intraocular inflammation in Q4W dosing arm",
                "affected_sections": ["Section 6.1 Adverse Events", "Section 7 Precautions"],
                "new_risk_identified": True,
                "risk_category": "moderate",
                "regulatory_notification_required": True,
                "regulatory_notified": True,
                "notification_date": now - timedelta(days=348),
                "dsmb_informed": True,
                "investigator_notification_required": True,
                "days_to_distribute": 14,
                "prepared_by": "Dr. Sarah Chen",
                "reviewed_by": "Dr. James Wright",
                "notes": "IND safety report filed. Investigators notified within 14 days.",
                "created_at": now - timedelta(days=350),
            },
            {
                "id": "SU-002",
                "trial_id": EYLEA_TRIAL,
                "ib_version_id": "IBV-003",
                "update_type": UpdateType.NEW_DATA,
                "update_date": now - timedelta(days=85),
                "safety_signal": "Updated cardiovascular safety profile from long-term follow-up data",
                "affected_sections": ["Section 6.2 Serious Adverse Events"],
                "new_risk_identified": False,
                "risk_category": "low",
                "regulatory_notification_required": False,
                "regulatory_notified": False,
                "notification_date": None,
                "dsmb_informed": True,
                "investigator_notification_required": True,
                "days_to_distribute": 30,
                "prepared_by": "Dr. Sarah Chen",
                "reviewed_by": "Dr. William Torres",
                "notes": "No new risks. Confirms favorable CV safety profile.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "SU-003",
                "trial_id": DUPIXENT_TRIAL,
                "ib_version_id": "IBV-005",
                "update_type": UpdateType.SAFETY_DRIVEN,
                "update_date": now - timedelta(days=160),
                "safety_signal": "Conjunctivitis reported at higher rate than anticipated in atopic dermatitis population",
                "affected_sections": ["Section 6.1 Adverse Events", "Section 6.3 Special Populations"],
                "new_risk_identified": True,
                "risk_category": "moderate",
                "regulatory_notification_required": True,
                "regulatory_notified": True,
                "notification_date": now - timedelta(days=158),
                "dsmb_informed": True,
                "investigator_notification_required": True,
                "days_to_distribute": 7,
                "prepared_by": "Dr. Maria Lopez",
                "reviewed_by": "Dr. David Patel",
                "notes": "Urgent safety update. 7-day distribution requirement.",
                "created_at": now - timedelta(days=160),
            },
            {
                "id": "SU-004",
                "trial_id": DUPIXENT_TRIAL,
                "ib_version_id": "IBV-005",
                "update_type": UpdateType.SCHEDULED,
                "update_date": now - timedelta(days=90),
                "safety_signal": "Annual safety update with cumulative exposure data analysis",
                "affected_sections": ["Section 6.1 Adverse Events", "Section 8 Summary of Data"],
                "new_risk_identified": False,
                "risk_category": "low",
                "regulatory_notification_required": False,
                "regulatory_notified": False,
                "notification_date": None,
                "dsmb_informed": True,
                "investigator_notification_required": True,
                "days_to_distribute": 30,
                "prepared_by": "Dr. Robert Kim",
                "reviewed_by": "Dr. Maria Lopez",
                "notes": "Routine annual safety update. No new safety concerns.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "SU-005",
                "trial_id": LIBTAYO_TRIAL,
                "ib_version_id": "IBV-008",
                "update_type": UpdateType.SAFETY_DRIVEN,
                "update_date": now - timedelta(days=280),
                "safety_signal": "Immune-related hepatitis observed in 3 subjects on high-dose arm",
                "affected_sections": ["Section 6.2 Serious Adverse Events", "Section 6.3 Immune-Related AEs"],
                "new_risk_identified": True,
                "risk_category": "high",
                "regulatory_notification_required": True,
                "regulatory_notified": True,
                "notification_date": now - timedelta(days=279),
                "dsmb_informed": True,
                "investigator_notification_required": True,
                "days_to_distribute": 3,
                "prepared_by": "Dr. Angela Park",
                "reviewed_by": "Dr. William Torres",
                "notes": "SUSAR reported. Emergency distribution within 3 days.",
                "created_at": now - timedelta(days=280),
            },
            {
                "id": "SU-006",
                "trial_id": LIBTAYO_TRIAL,
                "ib_version_id": "IBV-009",
                "update_type": UpdateType.REGULATORY_REQUEST,
                "update_date": now - timedelta(days=110),
                "safety_signal": "FDA requested updated hepatotoxicity data with dose-response analysis",
                "affected_sections": ["Section 6.2 Serious Adverse Events"],
                "new_risk_identified": False,
                "risk_category": "moderate",
                "regulatory_notification_required": True,
                "regulatory_notified": True,
                "notification_date": now - timedelta(days=108),
                "dsmb_informed": True,
                "investigator_notification_required": True,
                "days_to_distribute": 14,
                "prepared_by": "Dr. Angela Park",
                "reviewed_by": "Dr. William Torres",
                "notes": "Response to FDA information request. Dose-response analysis included.",
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "SU-007",
                "trial_id": LIBTAYO_TRIAL,
                "ib_version_id": "IBV-009",
                "update_type": UpdateType.NEW_DATA,
                "update_date": now - timedelta(days=60),
                "safety_signal": "Updated immune-related adverse event management guidelines based on emerging data",
                "affected_sections": ["Section 6.3 Immune-Related AEs", "Section 7 Precautions"],
                "new_risk_identified": False,
                "risk_category": "low",
                "regulatory_notification_required": False,
                "regulatory_notified": False,
                "notification_date": None,
                "dsmb_informed": True,
                "investigator_notification_required": True,
                "days_to_distribute": 30,
                "prepared_by": "Dr. Angela Park",
                "reviewed_by": "Dr. James Wright",
                "notes": "Management guidelines updated. No new risk signals.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "SU-008",
                "trial_id": EYLEA_TRIAL,
                "ib_version_id": "IBV-003",
                "update_type": UpdateType.CORRECTION,
                "update_date": now - timedelta(days=40),
                "safety_signal": "Correction to adverse event coding in Table 6.1.2 (MedDRA term reclassification)",
                "affected_sections": ["Section 6.1 Adverse Events"],
                "new_risk_identified": False,
                "risk_category": "low",
                "regulatory_notification_required": False,
                "regulatory_notified": False,
                "notification_date": None,
                "dsmb_informed": False,
                "investigator_notification_required": True,
                "days_to_distribute": 30,
                "prepared_by": "Dr. James Wright",
                "reviewed_by": "Dr. Sarah Chen",
                "notes": "Administrative correction. No impact on benefit-risk assessment.",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "SU-009",
                "trial_id": DUPIXENT_TRIAL,
                "ib_version_id": None,
                "update_type": UpdateType.SAFETY_DRIVEN,
                "update_date": now - timedelta(days=15),
                "safety_signal": "New case of eosinophilic pneumonia under investigation",
                "affected_sections": ["Section 6.2 Serious Adverse Events"],
                "new_risk_identified": True,
                "risk_category": "high",
                "regulatory_notification_required": True,
                "regulatory_notified": False,
                "notification_date": None,
                "dsmb_informed": True,
                "investigator_notification_required": True,
                "days_to_distribute": 3,
                "prepared_by": "Dr. Robert Kim",
                "reviewed_by": None,
                "notes": "Under investigation. Causality assessment pending.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "SU-010",
                "trial_id": EYLEA_TRIAL,
                "ib_version_id": "IBV-002",
                "update_type": UpdateType.SCHEDULED,
                "update_date": now - timedelta(days=400),
                "safety_signal": "Routine semi-annual safety data review and IB update assessment",
                "affected_sections": ["Section 6.1 Adverse Events", "Section 8 Summary of Data"],
                "new_risk_identified": False,
                "risk_category": "low",
                "regulatory_notification_required": False,
                "regulatory_notified": False,
                "notification_date": None,
                "dsmb_informed": True,
                "investigator_notification_required": False,
                "days_to_distribute": 0,
                "prepared_by": "Dr. Sarah Chen",
                "reviewed_by": "Dr. William Torres",
                "notes": "No IB update required at this cycle.",
                "created_at": now - timedelta(days=400),
            },
            {
                "id": "SU-011",
                "trial_id": LIBTAYO_TRIAL,
                "ib_version_id": "IBV-009",
                "update_type": UpdateType.SAFETY_DRIVEN,
                "update_date": now - timedelta(days=5),
                "safety_signal": "Stevens-Johnson syndrome reported in one subject receiving combination therapy",
                "affected_sections": ["Section 6.2 Serious Adverse Events", "Section 6.4 Dermatologic AEs"],
                "new_risk_identified": True,
                "risk_category": "high",
                "regulatory_notification_required": True,
                "regulatory_notified": True,
                "notification_date": now - timedelta(days=4),
                "dsmb_informed": True,
                "investigator_notification_required": True,
                "days_to_distribute": 1,
                "prepared_by": "Dr. Angela Park",
                "reviewed_by": "Dr. William Torres",
                "notes": "SUSAR filed within 24 hours. Emergency investigator notification.",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "SU-012",
                "trial_id": DUPIXENT_TRIAL,
                "ib_version_id": "IBV-005",
                "update_type": UpdateType.NEW_DATA,
                "update_date": now - timedelta(days=45),
                "safety_signal": "Long-term extension study data confirms sustained safety profile at 52 weeks",
                "affected_sections": ["Section 5.3 Clinical Efficacy", "Section 8 Summary of Data"],
                "new_risk_identified": False,
                "risk_category": "low",
                "regulatory_notification_required": False,
                "regulatory_notified": False,
                "notification_date": None,
                "dsmb_informed": True,
                "investigator_notification_required": True,
                "days_to_distribute": 30,
                "prepared_by": "Dr. Maria Lopez",
                "reviewed_by": "Dr. Robert Kim",
                "notes": "Favorable long-term safety. Supports continued benefit-risk balance.",
                "created_at": now - timedelta(days=45),
            },
        ]

        for s in safety_data:
            self._safety_updates[s["id"]] = SafetyUpdate(**s)

        # --- 12 Distribution Records ---
        distribution_data = [
            {
                "id": "DR-001",
                "trial_id": EYLEA_TRIAL,
                "ib_version_id": "IBV-003",
                "site_id": "SITE-101",
                "investigator_name": "Dr. Robert Anderson",
                "distribution_method": DistributionMethod.ELECTRONIC,
                "distribution_date": now - timedelta(days=85),
                "received_date": now - timedelta(days=84),
                "receipt_confirmed": True,
                "prior_version_recalled": True,
                "recall_date": now - timedelta(days=83),
                "tracking_number": "ETR-2024-001",
                "distributed_by": "Clinical Operations Team",
                "notes": "Electronic distribution via secure portal.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "DR-002",
                "trial_id": EYLEA_TRIAL,
                "ib_version_id": "IBV-003",
                "site_id": "SITE-102",
                "investigator_name": "Dr. Patricia Williams",
                "distribution_method": DistributionMethod.PORTAL,
                "distribution_date": now - timedelta(days=85),
                "received_date": now - timedelta(days=82),
                "receipt_confirmed": True,
                "prior_version_recalled": True,
                "recall_date": now - timedelta(days=81),
                "tracking_number": "PTL-2024-002",
                "distributed_by": "Clinical Operations Team",
                "notes": "Investigator portal download confirmed.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "DR-003",
                "trial_id": EYLEA_TRIAL,
                "ib_version_id": "IBV-003",
                "site_id": "SITE-103",
                "investigator_name": "Dr. Michael Thompson",
                "distribution_method": DistributionMethod.REGISTERED_MAIL,
                "distribution_date": now - timedelta(days=85),
                "received_date": now - timedelta(days=78),
                "receipt_confirmed": True,
                "prior_version_recalled": True,
                "recall_date": now - timedelta(days=77),
                "tracking_number": "RM-2024-003",
                "distributed_by": "Document Control",
                "notes": "Registered mail with return receipt requested.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "DR-004",
                "trial_id": DUPIXENT_TRIAL,
                "ib_version_id": "IBV-005",
                "site_id": "SITE-201",
                "investigator_name": "Dr. Jennifer Lee",
                "distribution_method": DistributionMethod.ELECTRONIC,
                "distribution_date": now - timedelta(days=175),
                "received_date": now - timedelta(days=174),
                "receipt_confirmed": True,
                "prior_version_recalled": True,
                "recall_date": now - timedelta(days=173),
                "tracking_number": "ETR-2024-004",
                "distributed_by": "Clinical Operations Team",
                "notes": None,
                "created_at": now - timedelta(days=175),
            },
            {
                "id": "DR-005",
                "trial_id": DUPIXENT_TRIAL,
                "ib_version_id": "IBV-005",
                "site_id": "SITE-202",
                "investigator_name": "Dr. David Chang",
                "distribution_method": DistributionMethod.HYBRID,
                "distribution_date": now - timedelta(days=175),
                "received_date": now - timedelta(days=170),
                "receipt_confirmed": True,
                "prior_version_recalled": True,
                "recall_date": now - timedelta(days=169),
                "tracking_number": "HYB-2024-005",
                "distributed_by": "Regional CRA",
                "notes": "Electronic copy followed by paper copy at site visit.",
                "created_at": now - timedelta(days=175),
            },
            {
                "id": "DR-006",
                "trial_id": DUPIXENT_TRIAL,
                "ib_version_id": "IBV-005",
                "site_id": "SITE-203",
                "investigator_name": "Dr. Sophia Martinez",
                "distribution_method": DistributionMethod.PAPER,
                "distribution_date": now - timedelta(days=175),
                "received_date": None,
                "receipt_confirmed": False,
                "prior_version_recalled": False,
                "recall_date": None,
                "tracking_number": "PPR-2024-006",
                "distributed_by": "Document Control",
                "notes": "Awaiting receipt confirmation from site.",
                "created_at": now - timedelta(days=175),
            },
            {
                "id": "DR-007",
                "trial_id": LIBTAYO_TRIAL,
                "ib_version_id": "IBV-009",
                "site_id": "SITE-301",
                "investigator_name": "Dr. Richard Brown",
                "distribution_method": DistributionMethod.ELECTRONIC,
                "distribution_date": now - timedelta(days=115),
                "received_date": now - timedelta(days=114),
                "receipt_confirmed": True,
                "prior_version_recalled": True,
                "recall_date": now - timedelta(days=113),
                "tracking_number": "ETR-2024-007",
                "distributed_by": "Clinical Operations Team",
                "notes": None,
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "DR-008",
                "trial_id": LIBTAYO_TRIAL,
                "ib_version_id": "IBV-009",
                "site_id": "SITE-302",
                "investigator_name": "Dr. Emily Watson",
                "distribution_method": DistributionMethod.PORTAL,
                "distribution_date": now - timedelta(days=115),
                "received_date": now - timedelta(days=113),
                "receipt_confirmed": True,
                "prior_version_recalled": True,
                "recall_date": now - timedelta(days=112),
                "tracking_number": "PTL-2024-008",
                "distributed_by": "Clinical Operations Team",
                "notes": None,
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "DR-009",
                "trial_id": LIBTAYO_TRIAL,
                "ib_version_id": "IBV-009",
                "site_id": "SITE-303",
                "investigator_name": "Dr. Kevin Harris",
                "distribution_method": DistributionMethod.ELECTRONIC,
                "distribution_date": now - timedelta(days=115),
                "received_date": now - timedelta(days=112),
                "receipt_confirmed": True,
                "prior_version_recalled": True,
                "recall_date": now - timedelta(days=111),
                "tracking_number": "ETR-2024-009",
                "distributed_by": "Clinical Operations Team",
                "notes": "Confirmed via read-receipt.",
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "DR-010",
                "trial_id": EYLEA_TRIAL,
                "ib_version_id": "IBV-003",
                "site_id": "SITE-104",
                "investigator_name": "Dr. Linda Jackson",
                "distribution_method": DistributionMethod.ELECTRONIC,
                "distribution_date": now - timedelta(days=80),
                "received_date": now - timedelta(days=79),
                "receipt_confirmed": True,
                "prior_version_recalled": False,
                "recall_date": None,
                "tracking_number": "ETR-2024-010",
                "distributed_by": "Clinical Operations Team",
                "notes": "New site activation. No prior version to recall.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "DR-011",
                "trial_id": LIBTAYO_TRIAL,
                "ib_version_id": "IBV-009",
                "site_id": "SITE-304",
                "investigator_name": "Dr. Thomas Nguyen",
                "distribution_method": DistributionMethod.REGISTERED_MAIL,
                "distribution_date": now - timedelta(days=110),
                "received_date": None,
                "receipt_confirmed": False,
                "prior_version_recalled": False,
                "recall_date": None,
                "tracking_number": "RM-2024-011",
                "distributed_by": "Document Control",
                "notes": "International site. Mail delivery pending.",
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "DR-012",
                "trial_id": DUPIXENT_TRIAL,
                "ib_version_id": "IBV-005",
                "site_id": "SITE-204",
                "investigator_name": "Dr. Rachel Green",
                "distribution_method": DistributionMethod.ELECTRONIC,
                "distribution_date": now - timedelta(days=170),
                "received_date": now - timedelta(days=169),
                "receipt_confirmed": True,
                "prior_version_recalled": True,
                "recall_date": now - timedelta(days=168),
                "tracking_number": "ETR-2024-012",
                "distributed_by": "Clinical Operations Team",
                "notes": None,
                "created_at": now - timedelta(days=170),
            },
        ]

        for d in distribution_data:
            self._distribution_records[d["id"]] = DistributionRecord(**d)

        # --- 12 Revision Histories ---
        revision_data = [
            {
                "id": "RH-001",
                "trial_id": EYLEA_TRIAL,
                "ib_version_id": "IBV-002",
                "revision_date": now - timedelta(days=365),
                "revision_scope": RevisionScope.MAJOR,
                "section_number": "5.3",
                "section_title": "Clinical Efficacy",
                "change_description": "Incorporated Phase II efficacy results including primary endpoint data",
                "rationale": "Phase II study completed; data supports efficacy claims",
                "data_source": "EYLEA-PH2-001 CSR",
                "regulatory_driven": False,
                "safety_driven": False,
                "pages_affected": 18,
                "revised_by": "Dr. Sarah Chen",
                "approved_by": "Dr. William Torres",
                "created_at": now - timedelta(days=370),
            },
            {
                "id": "RH-002",
                "trial_id": EYLEA_TRIAL,
                "ib_version_id": "IBV-002",
                "revision_date": now - timedelta(days=365),
                "revision_scope": RevisionScope.MAJOR,
                "section_number": "6.1",
                "section_title": "Adverse Events",
                "change_description": "Updated AE tables with cumulative Phase I/II safety data",
                "rationale": "Integrated safety analysis from all completed studies",
                "data_source": "ISS-EYLEA-2024",
                "regulatory_driven": False,
                "safety_driven": True,
                "pages_affected": 12,
                "revised_by": "Dr. James Wright",
                "approved_by": "Dr. William Torres",
                "created_at": now - timedelta(days=370),
            },
            {
                "id": "RH-003",
                "trial_id": EYLEA_TRIAL,
                "ib_version_id": "IBV-003",
                "revision_date": now - timedelta(days=95),
                "revision_scope": RevisionScope.MAJOR,
                "section_number": "4.2",
                "section_title": "Pharmacokinetics",
                "change_description": "Added population PK analysis results and exposure-response data",
                "rationale": "PopPK analysis completed supporting dose selection rationale",
                "data_source": "EYLEA-POPPK-001",
                "regulatory_driven": True,
                "safety_driven": False,
                "pages_affected": 15,
                "revised_by": "Dr. Sarah Chen",
                "approved_by": "Dr. William Torres",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "RH-004",
                "trial_id": DUPIXENT_TRIAL,
                "ib_version_id": "IBV-005",
                "revision_date": now - timedelta(days=185),
                "revision_scope": RevisionScope.MAJOR,
                "section_number": "5.1",
                "section_title": "Clinical Pharmacology",
                "change_description": "Updated clinical pharmacology section with PK/PD modeling results",
                "rationale": "New modeling data available from dose-ranging study",
                "data_source": "DUP-PKPD-002",
                "regulatory_driven": False,
                "safety_driven": False,
                "pages_affected": 10,
                "revised_by": "Dr. Maria Lopez",
                "approved_by": "Dr. David Patel",
                "created_at": now - timedelta(days=190),
            },
            {
                "id": "RH-005",
                "trial_id": DUPIXENT_TRIAL,
                "ib_version_id": "IBV-005",
                "revision_date": now - timedelta(days=185),
                "revision_scope": RevisionScope.SAFETY_ADDENDUM,
                "section_number": "6.1",
                "section_title": "Adverse Events",
                "change_description": "Added conjunctivitis as identified risk with frequency and management",
                "rationale": "Safety signal identified requiring IB update per ICH E6",
                "data_source": "DUP-SAFETY-RPT-003",
                "regulatory_driven": True,
                "safety_driven": True,
                "pages_affected": 5,
                "revised_by": "Dr. Maria Lopez",
                "approved_by": "Dr. David Patel",
                "created_at": now - timedelta(days=190),
            },
            {
                "id": "RH-006",
                "trial_id": LIBTAYO_TRIAL,
                "ib_version_id": "IBV-008",
                "revision_date": now - timedelta(days=305),
                "revision_scope": RevisionScope.MAJOR,
                "section_number": "4.3",
                "section_title": "Immunogenicity",
                "change_description": "Added immunogenicity assessment results from Phase I/II",
                "rationale": "ADA analysis completed; low immunogenicity confirmed",
                "data_source": "LIB-IMMUNO-001",
                "regulatory_driven": True,
                "safety_driven": False,
                "pages_affected": 8,
                "revised_by": "Dr. Angela Park",
                "approved_by": "Dr. William Torres",
                "created_at": now - timedelta(days=310),
            },
            {
                "id": "RH-007",
                "trial_id": LIBTAYO_TRIAL,
                "ib_version_id": "IBV-009",
                "revision_date": now - timedelta(days=125),
                "revision_scope": RevisionScope.SAFETY_ADDENDUM,
                "section_number": "6.3",
                "section_title": "Immune-Related Adverse Events",
                "change_description": "Comprehensive irAE section added with management algorithms",
                "rationale": "Multiple irAE types identified requiring structured management guidance",
                "data_source": "LIB-IRAE-ANALYSIS-001",
                "regulatory_driven": True,
                "safety_driven": True,
                "pages_affected": 22,
                "revised_by": "Dr. Angela Park",
                "approved_by": "Dr. William Torres",
                "created_at": now - timedelta(days=130),
            },
            {
                "id": "RH-008",
                "trial_id": LIBTAYO_TRIAL,
                "ib_version_id": "IBV-009",
                "revision_date": now - timedelta(days=125),
                "revision_scope": RevisionScope.MAJOR,
                "section_number": "5.3",
                "section_title": "Clinical Efficacy",
                "change_description": "Updated efficacy data post arm-drop with revised analyses",
                "rationale": "Arm-drop adaptation required updated efficacy presentation",
                "data_source": "LIB-PH3-INTERIM-002",
                "regulatory_driven": False,
                "safety_driven": False,
                "pages_affected": 14,
                "revised_by": "Dr. Angela Park",
                "approved_by": "Dr. William Torres",
                "created_at": now - timedelta(days=130),
            },
            {
                "id": "RH-009",
                "trial_id": EYLEA_TRIAL,
                "ib_version_id": "IBV-003",
                "revision_date": now - timedelta(days=95),
                "revision_scope": RevisionScope.MINOR,
                "section_number": "6.2",
                "section_title": "Serious Adverse Events",
                "change_description": "Updated SAE listing and frequency tables",
                "rationale": "Routine safety data update for IB version 3.0",
                "data_source": "EYLEA-SAE-LISTING-Q4",
                "regulatory_driven": False,
                "safety_driven": True,
                "pages_affected": 6,
                "revised_by": "Dr. James Wright",
                "approved_by": "Dr. William Torres",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "RH-010",
                "trial_id": DUPIXENT_TRIAL,
                "ib_version_id": "IBV-005",
                "revision_date": now - timedelta(days=185),
                "revision_scope": RevisionScope.MINOR,
                "section_number": "7",
                "section_title": "Precautions",
                "change_description": "Updated precautions to include conjunctivitis monitoring guidance",
                "rationale": "Consequential update following Section 6.1 changes",
                "data_source": None,
                "regulatory_driven": False,
                "safety_driven": True,
                "pages_affected": 3,
                "revised_by": "Dr. Maria Lopez",
                "approved_by": "Dr. David Patel",
                "created_at": now - timedelta(days=190),
            },
            {
                "id": "RH-011",
                "trial_id": EYLEA_TRIAL,
                "ib_version_id": "IBV-003",
                "revision_date": now - timedelta(days=40),
                "revision_scope": RevisionScope.ADMINISTRATIVE,
                "section_number": "6.1",
                "section_title": "Adverse Events",
                "change_description": "MedDRA version upgrade from 25.1 to 26.0; term reclassifications applied",
                "rationale": "Routine MedDRA dictionary update per SOP",
                "data_source": "MedDRA v26.0",
                "regulatory_driven": False,
                "safety_driven": False,
                "pages_affected": 4,
                "revised_by": "Dr. James Wright",
                "approved_by": "Dr. Sarah Chen",
                "created_at": now - timedelta(days=42),
            },
            {
                "id": "RH-012",
                "trial_id": LIBTAYO_TRIAL,
                "ib_version_id": "IBV-009",
                "revision_date": now - timedelta(days=15),
                "revision_scope": RevisionScope.FULL_REWRITE,
                "section_number": "6.4",
                "section_title": "Dermatologic Adverse Events",
                "change_description": "New section added for dermatologic AEs including SJS/TEN risk assessment",
                "rationale": "Stevens-Johnson syndrome case reported; new section required",
                "data_source": "LIB-SUSAR-2024-015",
                "regulatory_driven": True,
                "safety_driven": True,
                "pages_affected": 8,
                "revised_by": "Dr. Angela Park",
                "approved_by": None,
                "created_at": now - timedelta(days=18),
            },
        ]

        for r in revision_data:
            self._revision_histories[r["id"]] = RevisionHistory(**r)

        # --- 12 Acknowledgment Records ---
        acknowledgment_data = [
            {
                "id": "ACK-001",
                "trial_id": EYLEA_TRIAL,
                "ib_version_id": "IBV-003",
                "distribution_id": "DR-001",
                "investigator_name": "Dr. Robert Anderson",
                "site_id": "SITE-101",
                "status": AcknowledgmentStatus.ACKNOWLEDGED,
                "sent_date": now - timedelta(days=85),
                "due_date": now - timedelta(days=71),
                "acknowledged_date": now - timedelta(days=82),
                "reminder_count": 0,
                "last_reminder_date": None,
                "escalation_date": None,
                "signature_on_file": True,
                "managed_by": "Clinical Operations Team",
                "notes": "Prompt acknowledgment within 3 days.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "ACK-002",
                "trial_id": EYLEA_TRIAL,
                "ib_version_id": "IBV-003",
                "distribution_id": "DR-002",
                "investigator_name": "Dr. Patricia Williams",
                "site_id": "SITE-102",
                "status": AcknowledgmentStatus.ACKNOWLEDGED,
                "sent_date": now - timedelta(days=85),
                "due_date": now - timedelta(days=71),
                "acknowledged_date": now - timedelta(days=75),
                "reminder_count": 1,
                "last_reminder_date": now - timedelta(days=78),
                "escalation_date": None,
                "signature_on_file": True,
                "managed_by": "Clinical Operations Team",
                "notes": "One reminder needed before acknowledgment.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "ACK-003",
                "trial_id": EYLEA_TRIAL,
                "ib_version_id": "IBV-003",
                "distribution_id": "DR-003",
                "investigator_name": "Dr. Michael Thompson",
                "site_id": "SITE-103",
                "status": AcknowledgmentStatus.ACKNOWLEDGED,
                "sent_date": now - timedelta(days=85),
                "due_date": now - timedelta(days=71),
                "acknowledged_date": now - timedelta(days=70),
                "reminder_count": 2,
                "last_reminder_date": now - timedelta(days=73),
                "escalation_date": None,
                "signature_on_file": True,
                "managed_by": "Clinical Operations Team",
                "notes": "Acknowledged on due date after two reminders.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "ACK-004",
                "trial_id": DUPIXENT_TRIAL,
                "ib_version_id": "IBV-005",
                "distribution_id": "DR-004",
                "investigator_name": "Dr. Jennifer Lee",
                "site_id": "SITE-201",
                "status": AcknowledgmentStatus.ACKNOWLEDGED,
                "sent_date": now - timedelta(days=175),
                "due_date": now - timedelta(days=161),
                "acknowledged_date": now - timedelta(days=172),
                "reminder_count": 0,
                "last_reminder_date": None,
                "escalation_date": None,
                "signature_on_file": True,
                "managed_by": "Clinical Operations Team",
                "notes": None,
                "created_at": now - timedelta(days=175),
            },
            {
                "id": "ACK-005",
                "trial_id": DUPIXENT_TRIAL,
                "ib_version_id": "IBV-005",
                "distribution_id": "DR-005",
                "investigator_name": "Dr. David Chang",
                "site_id": "SITE-202",
                "status": AcknowledgmentStatus.ACKNOWLEDGED,
                "sent_date": now - timedelta(days=175),
                "due_date": now - timedelta(days=161),
                "acknowledged_date": now - timedelta(days=165),
                "reminder_count": 1,
                "last_reminder_date": now - timedelta(days=168),
                "escalation_date": None,
                "signature_on_file": True,
                "managed_by": "Regional CRA",
                "notes": None,
                "created_at": now - timedelta(days=175),
            },
            {
                "id": "ACK-006",
                "trial_id": DUPIXENT_TRIAL,
                "ib_version_id": "IBV-005",
                "distribution_id": "DR-006",
                "investigator_name": "Dr. Sophia Martinez",
                "site_id": "SITE-203",
                "status": AcknowledgmentStatus.OVERDUE,
                "sent_date": now - timedelta(days=175),
                "due_date": now - timedelta(days=161),
                "acknowledged_date": None,
                "reminder_count": 3,
                "last_reminder_date": now - timedelta(days=150),
                "escalation_date": now - timedelta(days=145),
                "signature_on_file": False,
                "managed_by": "Document Control",
                "notes": "Overdue. Escalated to clinical project manager.",
                "created_at": now - timedelta(days=175),
            },
            {
                "id": "ACK-007",
                "trial_id": LIBTAYO_TRIAL,
                "ib_version_id": "IBV-009",
                "distribution_id": "DR-007",
                "investigator_name": "Dr. Richard Brown",
                "site_id": "SITE-301",
                "status": AcknowledgmentStatus.ACKNOWLEDGED,
                "sent_date": now - timedelta(days=115),
                "due_date": now - timedelta(days=101),
                "acknowledged_date": now - timedelta(days=112),
                "reminder_count": 0,
                "last_reminder_date": None,
                "escalation_date": None,
                "signature_on_file": True,
                "managed_by": "Clinical Operations Team",
                "notes": None,
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "ACK-008",
                "trial_id": LIBTAYO_TRIAL,
                "ib_version_id": "IBV-009",
                "distribution_id": "DR-008",
                "investigator_name": "Dr. Emily Watson",
                "site_id": "SITE-302",
                "status": AcknowledgmentStatus.ACKNOWLEDGED,
                "sent_date": now - timedelta(days=115),
                "due_date": now - timedelta(days=101),
                "acknowledged_date": now - timedelta(days=108),
                "reminder_count": 0,
                "last_reminder_date": None,
                "escalation_date": None,
                "signature_on_file": True,
                "managed_by": "Clinical Operations Team",
                "notes": None,
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "ACK-009",
                "trial_id": LIBTAYO_TRIAL,
                "ib_version_id": "IBV-009",
                "distribution_id": "DR-009",
                "investigator_name": "Dr. Kevin Harris",
                "site_id": "SITE-303",
                "status": AcknowledgmentStatus.ACKNOWLEDGED,
                "sent_date": now - timedelta(days=115),
                "due_date": now - timedelta(days=101),
                "acknowledged_date": now - timedelta(days=105),
                "reminder_count": 1,
                "last_reminder_date": now - timedelta(days=108),
                "escalation_date": None,
                "signature_on_file": True,
                "managed_by": "Clinical Operations Team",
                "notes": None,
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "ACK-010",
                "trial_id": LIBTAYO_TRIAL,
                "ib_version_id": "IBV-009",
                "distribution_id": "DR-011",
                "investigator_name": "Dr. Thomas Nguyen",
                "site_id": "SITE-304",
                "status": AcknowledgmentStatus.ESCALATED,
                "sent_date": now - timedelta(days=110),
                "due_date": now - timedelta(days=96),
                "acknowledged_date": None,
                "reminder_count": 4,
                "last_reminder_date": now - timedelta(days=80),
                "escalation_date": now - timedelta(days=75),
                "signature_on_file": False,
                "managed_by": "Document Control",
                "notes": "Escalated to sponsor medical director. International site communication challenges.",
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "ACK-011",
                "trial_id": EYLEA_TRIAL,
                "ib_version_id": "IBV-003",
                "distribution_id": "DR-010",
                "investigator_name": "Dr. Linda Jackson",
                "site_id": "SITE-104",
                "status": AcknowledgmentStatus.PENDING,
                "sent_date": now - timedelta(days=80),
                "due_date": now - timedelta(days=66),
                "acknowledged_date": None,
                "reminder_count": 0,
                "last_reminder_date": None,
                "escalation_date": None,
                "signature_on_file": False,
                "managed_by": "Clinical Operations Team",
                "notes": "Recently distributed. Awaiting acknowledgment.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "ACK-012",
                "trial_id": DUPIXENT_TRIAL,
                "ib_version_id": "IBV-005",
                "distribution_id": "DR-012",
                "investigator_name": "Dr. Rachel Green",
                "site_id": "SITE-204",
                "status": AcknowledgmentStatus.WAIVED,
                "sent_date": now - timedelta(days=170),
                "due_date": now - timedelta(days=156),
                "acknowledged_date": None,
                "reminder_count": 0,
                "last_reminder_date": None,
                "escalation_date": None,
                "signature_on_file": False,
                "managed_by": "Clinical Operations Team",
                "notes": "Site closed before acknowledgment window. Waived per SOP.",
                "created_at": now - timedelta(days=170),
            },
        ]

        for a in acknowledgment_data:
            self._acknowledgment_records[a["id"]] = AcknowledgmentRecord(**a)

    # ------------------------------------------------------------------
    # IB Versions
    # ------------------------------------------------------------------

    def list_ib_versions(
        self,
        *,
        trial_id: str | None = None,
        status: IBStatus | None = None,
    ) -> list[IBVersion]:
        """List IB versions with optional filters."""
        with self._lock:
            result = list(self._ib_versions.values())

        if trial_id is not None:
            result = [v for v in result if v.trial_id == trial_id]
        if status is not None:
            result = [v for v in result if v.status == status]

        return sorted(result, key=lambda v: v.created_at, reverse=True)

    def get_ib_version(self, version_id: str) -> IBVersion | None:
        """Get a single IB version by ID."""
        with self._lock:
            return self._ib_versions.get(version_id)

    def create_ib_version(self, payload: IBVersionCreate) -> IBVersion:
        """Create a new IB version."""
        now = datetime.now(timezone.utc)
        version_id = f"IBV-{uuid4().hex[:8].upper()}"
        version = IBVersion(
            id=version_id,
            trial_id=payload.trial_id,
            version_number=payload.version_number,
            edition_number=payload.edition_number,
            status=IBStatus.DRAFT,
            effective_date=None,
            superseded_date=None,
            page_count=payload.page_count,
            sections_updated=[],
            preclinical_data_current=True,
            clinical_data_current=True,
            safety_data_cutoff=None,
            approved_by=None,
            approval_date=None,
            authored_by=payload.authored_by,
            regulatory_references=[],
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._ib_versions[version_id] = version
        logger.info("Created IB version %s for trial %s", version_id, payload.trial_id)
        return version

    def update_ib_version(
        self, version_id: str, payload: IBVersionUpdate
    ) -> IBVersion | None:
        """Update an existing IB version."""
        with self._lock:
            existing = self._ib_versions.get(version_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = IBVersion(**data)
            self._ib_versions[version_id] = updated
        return updated

    def delete_ib_version(self, version_id: str) -> bool:
        """Delete an IB version. Returns True if deleted."""
        with self._lock:
            if version_id in self._ib_versions:
                del self._ib_versions[version_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Safety Updates
    # ------------------------------------------------------------------

    def list_safety_updates(
        self,
        *,
        trial_id: str | None = None,
        update_type: UpdateType | None = None,
    ) -> list[SafetyUpdate]:
        """List safety updates with optional filters."""
        with self._lock:
            result = list(self._safety_updates.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if update_type is not None:
            result = [s for s in result if s.update_type == update_type]

        return sorted(result, key=lambda s: s.update_date, reverse=True)

    def get_safety_update(self, update_id: str) -> SafetyUpdate | None:
        """Get a single safety update by ID."""
        with self._lock:
            return self._safety_updates.get(update_id)

    def create_safety_update(self, payload: SafetyUpdateCreate) -> SafetyUpdate:
        """Create a new safety update."""
        now = datetime.now(timezone.utc)
        update_id = f"SU-{uuid4().hex[:8].upper()}"
        update = SafetyUpdate(
            id=update_id,
            trial_id=payload.trial_id,
            ib_version_id=payload.ib_version_id,
            update_type=payload.update_type,
            update_date=now,
            safety_signal=payload.safety_signal,
            affected_sections=[],
            new_risk_identified=payload.new_risk_identified,
            risk_category="low",
            regulatory_notification_required=False,
            regulatory_notified=False,
            notification_date=None,
            dsmb_informed=False,
            investigator_notification_required=True,
            days_to_distribute=0,
            prepared_by=payload.prepared_by,
            reviewed_by=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._safety_updates[update_id] = update
        logger.info("Created safety update %s for trial %s", update_id, payload.trial_id)
        return update

    def update_safety_update(
        self, update_id: str, payload: SafetyUpdateUpdate
    ) -> SafetyUpdate | None:
        """Update an existing safety update."""
        with self._lock:
            existing = self._safety_updates.get(update_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SafetyUpdate(**data)
            self._safety_updates[update_id] = updated
        return updated

    def delete_safety_update(self, update_id: str) -> bool:
        """Delete a safety update. Returns True if deleted."""
        with self._lock:
            if update_id in self._safety_updates:
                del self._safety_updates[update_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Distribution Records
    # ------------------------------------------------------------------

    def list_distribution_records(
        self,
        *,
        trial_id: str | None = None,
        distribution_method: DistributionMethod | None = None,
    ) -> list[DistributionRecord]:
        """List distribution records with optional filters."""
        with self._lock:
            result = list(self._distribution_records.values())

        if trial_id is not None:
            result = [d for d in result if d.trial_id == trial_id]
        if distribution_method is not None:
            result = [d for d in result if d.distribution_method == distribution_method]

        return sorted(result, key=lambda d: d.distribution_date, reverse=True)

    def get_distribution_record(self, record_id: str) -> DistributionRecord | None:
        """Get a single distribution record by ID."""
        with self._lock:
            return self._distribution_records.get(record_id)

    def create_distribution_record(self, payload: DistributionRecordCreate) -> DistributionRecord:
        """Create a new distribution record."""
        now = datetime.now(timezone.utc)
        record_id = f"DR-{uuid4().hex[:8].upper()}"
        record = DistributionRecord(
            id=record_id,
            trial_id=payload.trial_id,
            ib_version_id=payload.ib_version_id,
            site_id=payload.site_id,
            investigator_name=payload.investigator_name,
            distribution_method=payload.distribution_method,
            distribution_date=now,
            received_date=None,
            receipt_confirmed=False,
            prior_version_recalled=False,
            recall_date=None,
            tracking_number=None,
            distributed_by=payload.distributed_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._distribution_records[record_id] = record
        logger.info("Created distribution record %s for trial %s", record_id, payload.trial_id)
        return record

    def update_distribution_record(
        self, record_id: str, payload: DistributionRecordUpdate
    ) -> DistributionRecord | None:
        """Update an existing distribution record."""
        with self._lock:
            existing = self._distribution_records.get(record_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DistributionRecord(**data)
            self._distribution_records[record_id] = updated
        return updated

    def delete_distribution_record(self, record_id: str) -> bool:
        """Delete a distribution record. Returns True if deleted."""
        with self._lock:
            if record_id in self._distribution_records:
                del self._distribution_records[record_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Revision History
    # ------------------------------------------------------------------

    def list_revision_histories(
        self,
        *,
        trial_id: str | None = None,
        revision_scope: RevisionScope | None = None,
    ) -> list[RevisionHistory]:
        """List revision histories with optional filters."""
        with self._lock:
            result = list(self._revision_histories.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if revision_scope is not None:
            result = [r for r in result if r.revision_scope == revision_scope]

        return sorted(result, key=lambda r: r.revision_date, reverse=True)

    def get_revision_history(self, revision_id: str) -> RevisionHistory | None:
        """Get a single revision history by ID."""
        with self._lock:
            return self._revision_histories.get(revision_id)

    def create_revision_history(self, payload: RevisionHistoryCreate) -> RevisionHistory:
        """Create a new revision history entry."""
        now = datetime.now(timezone.utc)
        revision_id = f"RH-{uuid4().hex[:8].upper()}"
        revision = RevisionHistory(
            id=revision_id,
            trial_id=payload.trial_id,
            ib_version_id=payload.ib_version_id,
            revision_date=now,
            revision_scope=payload.revision_scope,
            section_number=payload.section_number,
            section_title=payload.section_title,
            change_description=payload.change_description,
            rationale=payload.rationale,
            data_source=None,
            regulatory_driven=False,
            safety_driven=False,
            pages_affected=payload.pages_affected,
            revised_by=payload.revised_by,
            approved_by=None,
            created_at=now,
        )
        with self._lock:
            self._revision_histories[revision_id] = revision
        logger.info("Created revision history %s for trial %s", revision_id, payload.trial_id)
        return revision

    def update_revision_history(
        self, revision_id: str, payload: RevisionHistoryUpdate
    ) -> RevisionHistory | None:
        """Update an existing revision history entry."""
        with self._lock:
            existing = self._revision_histories.get(revision_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = RevisionHistory(**data)
            self._revision_histories[revision_id] = updated
        return updated

    def delete_revision_history(self, revision_id: str) -> bool:
        """Delete a revision history entry. Returns True if deleted."""
        with self._lock:
            if revision_id in self._revision_histories:
                del self._revision_histories[revision_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Acknowledgment Records
    # ------------------------------------------------------------------

    def list_acknowledgment_records(
        self,
        *,
        trial_id: str | None = None,
        status: AcknowledgmentStatus | None = None,
    ) -> list[AcknowledgmentRecord]:
        """List acknowledgment records with optional filters."""
        with self._lock:
            result = list(self._acknowledgment_records.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if status is not None:
            result = [a for a in result if a.status == status]

        return sorted(result, key=lambda a: a.sent_date, reverse=True)

    def get_acknowledgment_record(self, record_id: str) -> AcknowledgmentRecord | None:
        """Get a single acknowledgment record by ID."""
        with self._lock:
            return self._acknowledgment_records.get(record_id)

    def create_acknowledgment_record(
        self, payload: AcknowledgmentRecordCreate
    ) -> AcknowledgmentRecord:
        """Create a new acknowledgment record."""
        now = datetime.now(timezone.utc)
        record_id = f"ACK-{uuid4().hex[:8].upper()}"
        record = AcknowledgmentRecord(
            id=record_id,
            trial_id=payload.trial_id,
            ib_version_id=payload.ib_version_id,
            distribution_id=payload.distribution_id,
            investigator_name=payload.investigator_name,
            site_id=payload.site_id,
            status=AcknowledgmentStatus.PENDING,
            sent_date=now,
            due_date=None,
            acknowledged_date=None,
            reminder_count=0,
            last_reminder_date=None,
            escalation_date=None,
            signature_on_file=False,
            managed_by=payload.managed_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._acknowledgment_records[record_id] = record
        logger.info("Created acknowledgment record %s for trial %s", record_id, payload.trial_id)
        return record

    def update_acknowledgment_record(
        self, record_id: str, payload: AcknowledgmentRecordUpdate
    ) -> AcknowledgmentRecord | None:
        """Update an existing acknowledgment record."""
        with self._lock:
            existing = self._acknowledgment_records.get(record_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = AcknowledgmentRecord(**data)
            self._acknowledgment_records[record_id] = updated
        return updated

    def delete_acknowledgment_record(self, record_id: str) -> bool:
        """Delete an acknowledgment record. Returns True if deleted."""
        with self._lock:
            if record_id in self._acknowledgment_records:
                del self._acknowledgment_records[record_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> InvestigatorBrochureMetrics:
        """Compute aggregated investigator brochure metrics."""
        with self._lock:
            versions = list(self._ib_versions.values())
            safety_updates = list(self._safety_updates.values())
            distributions = list(self._distribution_records.values())
            revisions = list(self._revision_histories.values())
            acknowledgments = list(self._acknowledgment_records.values())

        # Versions by status
        versions_by_status: dict[str, int] = {}
        for v in versions:
            key = v.status.value
            versions_by_status[key] = versions_by_status.get(key, 0) + 1

        # Current versions (distributed or approved)
        current_versions = sum(
            1 for v in versions
            if v.status in (IBStatus.DISTRIBUTED, IBStatus.APPROVED)
        )

        # Updates by type
        updates_by_type: dict[str, int] = {}
        for s in safety_updates:
            key = s.update_type.value
            updates_by_type[key] = updates_by_type.get(key, 0) + 1

        # New risks identified
        new_risks = sum(1 for s in safety_updates if s.new_risk_identified)

        # Distributions confirmed
        distributions_confirmed = sum(1 for d in distributions if d.receipt_confirmed)

        # Revisions by scope
        revisions_by_scope: dict[str, int] = {}
        for r in revisions:
            key = r.revision_scope.value
            revisions_by_scope[key] = revisions_by_scope.get(key, 0) + 1

        # Acknowledgments by status
        acknowledgments_by_status: dict[str, int] = {}
        for a in acknowledgments:
            key = a.status.value
            acknowledgments_by_status[key] = acknowledgments_by_status.get(key, 0) + 1

        # Overdue acknowledgments
        overdue = sum(
            1 for a in acknowledgments
            if a.status in (AcknowledgmentStatus.OVERDUE, AcknowledgmentStatus.ESCALATED)
        )

        return InvestigatorBrochureMetrics(
            total_versions=len(versions),
            versions_by_status=versions_by_status,
            current_versions=current_versions,
            total_safety_updates=len(safety_updates),
            updates_by_type=updates_by_type,
            new_risks_identified=new_risks,
            total_distributions=len(distributions),
            distributions_confirmed=distributions_confirmed,
            total_revisions=len(revisions),
            revisions_by_scope=revisions_by_scope,
            total_acknowledgments=len(acknowledgments),
            acknowledgments_by_status=acknowledgments_by_status,
            overdue_acknowledgments=overdue,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: InvestigatorBrochureService | None = None
_instance_lock = threading.Lock()


def get_investigator_brochure_service() -> InvestigatorBrochureService:
    """Return the singleton InvestigatorBrochureService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = InvestigatorBrochureService()
    return _instance


def reset_investigator_brochure_service() -> InvestigatorBrochureService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = InvestigatorBrochureService()
    return _instance
