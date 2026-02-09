"""Protocol Amendment Management Service (CLINICAL-16).

Manages protocol amendment lifecycle: creation, IRB coordination across sites,
impact assessment, implementation tracking, re-consent progress, and metrics.

Usage:
    from app.services.protocol_amendment_service import (
        get_protocol_amendment_service,
    )

    svc = get_protocol_amendment_service()
    amendments = svc.list_amendments()
    tracker = svc.get_amendment_tracker("trial-id")
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.protocol_amendment import (
    AmendmentCreate,
    AmendmentImpact,
    AmendmentImpactAssessment,
    AmendmentImplement,
    AmendmentListResponse,
    AmendmentMetrics,
    AmendmentStatus,
    AmendmentSubmit,
    AmendmentTracker,
    AmendmentType,
    AmendmentUpdate,
    IRBStatus,
    IRBSubmission,
    IRBSubmissionCreate,
    IRBSubmissionUpdate,
    ImpactSeverity,
    ProtocolAmendment,
    ReConsentUpdate,
    SiteImplementationStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class ProtocolAmendmentService:
    """In-memory Protocol Amendment Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._amendments: dict[str, ProtocolAmendment] = {}
        self._irb_submissions: dict[str, IRBSubmission] = {}
        self._impact_assessments: dict[str, AmendmentImpactAssessment] = {}
        self._site_implementations: dict[str, dict[str, SiteImplementationStatus]] = {}
        self._re_consent_progress: dict[str, dict[str, ReConsentUpdate]] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic protocol amendment data across clinical trials."""
        now = datetime.now(timezone.utc)

        # --- 6 Amendments across 3 trials ---

        # EYLEA Amendment 1: Eligibility expansion
        amd1 = ProtocolAmendment(
            id="AMD-001",
            trial_id=EYLEA_TRIAL,
            amendment_number=1,
            version_from="3.0",
            version_to="4.0",
            amendment_type=AmendmentType.SUBSTANTIAL,
            status=AmendmentStatus.IMPLEMENTED,
            title="Expansion of Eligibility Criteria for Broader Patient Population",
            rationale="Interim analysis demonstrated safety in broader age range; expanding eligibility to increase enrollment and generalizability of results.",
            description="Expansion of age criteria from 50-75 to 40-85 years. Removal of exclusion for prior anti-VEGF therapy if washout period of 90 days completed. Addition of new stratification factor for prior treatment history.",
            impacted_sections=["Section 4.1", "Section 4.2", "Section 5.1", "Section 9.3"],
            impacted_areas=[
                AmendmentImpact.ENROLLMENT_CRITERIA,
                AmendmentImpact.STATISTICAL_PLAN,
                AmendmentImpact.INFORMED_CONSENT,
            ],
            submitted_date=now - timedelta(days=120),
            approved_date=now - timedelta(days=90),
            implementation_date=now - timedelta(days=75),
            affected_sites=["SITE-101", "SITE-102", "SITE-103", "SITE-104"],
            irb_submissions=[],
            created_at=now - timedelta(days=150),
        )

        # EYLEA Amendment 2: Endpoint change
        amd2 = ProtocolAmendment(
            id="AMD-002",
            trial_id=EYLEA_TRIAL,
            amendment_number=2,
            version_from="4.0",
            version_to="5.0",
            amendment_type=AmendmentType.SUBSTANTIAL,
            status=AmendmentStatus.IRB_APPROVED,
            title="Addition of Secondary Endpoint for Visual Function Assessment",
            rationale="FDA feedback requested additional functional endpoint to supplement anatomical primary endpoint.",
            description="Addition of NEI VFQ-25 composite score as secondary endpoint. New visit window at Week 24 for functional assessment. Updated statistical analysis plan with hierarchical testing.",
            impacted_sections=["Section 3.2", "Section 6.1", "Section 9.1", "Section 9.4"],
            impacted_areas=[
                AmendmentImpact.ENDPOINTS,
                AmendmentImpact.VISIT_SCHEDULE,
                AmendmentImpact.STATISTICAL_PLAN,
            ],
            submitted_date=now - timedelta(days=45),
            approved_date=now - timedelta(days=15),
            implementation_date=None,
            affected_sites=["SITE-101", "SITE-102", "SITE-103", "SITE-104"],
            irb_submissions=[],
            created_at=now - timedelta(days=60),
        )

        # Dupixent Amendment 1: Dosing modification
        amd3 = ProtocolAmendment(
            id="AMD-003",
            trial_id=DUPIXENT_TRIAL,
            amendment_number=1,
            version_from="2.0",
            version_to="3.0",
            amendment_type=AmendmentType.SUBSTANTIAL,
            status=AmendmentStatus.IRB_SUBMITTED,
            title="Dose Modification Based on Interim PK/PD Analysis",
            rationale="Interim PK/PD analysis demonstrated that a lower loading dose achieves equivalent exposure with improved tolerability profile.",
            description="Loading dose reduced from 600mg to 400mg. Maintenance dose frequency changed from Q2W to Q4W for patients achieving adequate response at Week 16. Addition of dose re-escalation criteria.",
            impacted_sections=["Section 5.2", "Section 5.3", "Section 6.2", "Section 7.1"],
            impacted_areas=[
                AmendmentImpact.DOSING,
                AmendmentImpact.VISIT_SCHEDULE,
                AmendmentImpact.SAFETY_MONITORING,
                AmendmentImpact.INFORMED_CONSENT,
            ],
            submitted_date=now - timedelta(days=20),
            approved_date=None,
            implementation_date=None,
            affected_sites=["SITE-103", "SITE-105", "SITE-106"],
            irb_submissions=[],
            created_at=now - timedelta(days=35),
        )

        # Libtayo Amendment 1: Sample size increase
        amd4 = ProtocolAmendment(
            id="AMD-004",
            trial_id=LIBTAYO_TRIAL,
            amendment_number=1,
            version_from="1.0",
            version_to="2.0",
            amendment_type=AmendmentType.SUBSTANTIAL,
            status=AmendmentStatus.SPONSOR_REVIEW,
            title="Sample Size Increase Based on Blinded Interim Event Rate",
            rationale="Blinded interim analysis of event rate indicates lower-than-expected response rate in control arm, requiring sample size increase to maintain study power.",
            description="Sample size increased from 450 to 600 patients. 4 additional clinical sites to be activated. Updated randomization scheme and interim analysis plan. Extended enrollment period by 6 months.",
            impacted_sections=["Section 4.4", "Section 9.1", "Section 9.2", "Section 9.5"],
            impacted_areas=[
                AmendmentImpact.SAMPLE_SIZE,
                AmendmentImpact.STATISTICAL_PLAN,
                AmendmentImpact.ENROLLMENT_CRITERIA,
            ],
            submitted_date=None,
            approved_date=None,
            implementation_date=None,
            affected_sites=["SITE-105", "SITE-106", "SITE-107", "SITE-108"],
            irb_submissions=[],
            created_at=now - timedelta(days=10),
        )

        # Libtayo Amendment 2: Safety monitoring update
        amd5 = ProtocolAmendment(
            id="AMD-005",
            trial_id=LIBTAYO_TRIAL,
            amendment_number=2,
            version_from="2.0",
            version_to="2.1",
            amendment_type=AmendmentType.NON_SUBSTANTIAL,
            status=AmendmentStatus.DRAFT,
            title="Enhanced Safety Monitoring for Immune-Related Adverse Events",
            rationale="Recent safety signal from post-marketing data suggests increased monitoring of hepatic and thyroid function is warranted.",
            description="Addition of monthly thyroid function tests for first 6 months. Liver function monitoring frequency increased from quarterly to monthly. New stopping rules for Grade 3+ hepatotoxicity. Updated investigator brochure safety section.",
            impacted_sections=["Section 7.2", "Section 7.3", "Section 7.5", "Section 8.1"],
            impacted_areas=[
                AmendmentImpact.SAFETY_MONITORING,
                AmendmentImpact.VISIT_SCHEDULE,
                AmendmentImpact.INFORMED_CONSENT,
            ],
            submitted_date=None,
            approved_date=None,
            implementation_date=None,
            affected_sites=["SITE-105", "SITE-106", "SITE-107", "SITE-108"],
            irb_submissions=[],
            created_at=now - timedelta(days=5),
        )

        # Cross-trial administrative amendment
        amd6 = ProtocolAmendment(
            id="AMD-006",
            trial_id=EYLEA_TRIAL,
            amendment_number=3,
            version_from="5.0",
            version_to="5.1",
            amendment_type=AmendmentType.ADMINISTRATIVE,
            status=AmendmentStatus.IMPLEMENTED,
            title="Administrative Update: Sponsor Contact Information and Lab Manual Reference",
            rationale="Updated sponsor medical monitor contact information and corrected laboratory manual version reference.",
            description="Updated sponsor medical monitor name and contact details. Corrected laboratory manual reference from v2.1 to v3.0. Minor typographical corrections in Appendix B.",
            impacted_sections=["Section 1.3", "Appendix A", "Appendix B"],
            impacted_areas=[],
            submitted_date=now - timedelta(days=60),
            approved_date=now - timedelta(days=55),
            implementation_date=now - timedelta(days=50),
            affected_sites=["SITE-101", "SITE-102", "SITE-103", "SITE-104"],
            irb_submissions=[],
            created_at=now - timedelta(days=65),
        )

        for amd in [amd1, amd2, amd3, amd4, amd5, amd6]:
            self._amendments[amd.id] = amd

        # --- 20 IRB Submissions ---
        irb_data = [
            # AMD-001 (EYLEA eligibility expansion) - all 4 sites approved
            {
                "id": "IRB-001", "amendment_id": "AMD-001", "irb_name": "Western IRB",
                "site_id": "SITE-101", "submitted_date": now - timedelta(days=118),
                "status": IRBStatus.APPROVED, "approval_date": now - timedelta(days=95),
                "conditions": None, "continuing_review_date": now + timedelta(days=270),
            },
            {
                "id": "IRB-002", "amendment_id": "AMD-001", "irb_name": "Cleveland Clinic IRB",
                "site_id": "SITE-102", "submitted_date": now - timedelta(days=118),
                "status": IRBStatus.APPROVED, "approval_date": now - timedelta(days=92),
                "conditions": "Minor consent form language revision required",
                "continuing_review_date": now + timedelta(days=273),
            },
            {
                "id": "IRB-003", "amendment_id": "AMD-001", "irb_name": "Johns Hopkins IRB",
                "site_id": "SITE-103", "submitted_date": now - timedelta(days=116),
                "status": IRBStatus.APPROVED, "approval_date": now - timedelta(days=88),
                "conditions": None, "continuing_review_date": now + timedelta(days=277),
            },
            {
                "id": "IRB-004", "amendment_id": "AMD-001", "irb_name": "Mayo Clinic IRB",
                "site_id": "SITE-104", "submitted_date": now - timedelta(days=115),
                "status": IRBStatus.APPROVED, "approval_date": now - timedelta(days=90),
                "conditions": None, "continuing_review_date": now + timedelta(days=275),
            },
            # AMD-002 (EYLEA endpoint change) - 3 approved, 1 pending
            {
                "id": "IRB-005", "amendment_id": "AMD-002", "irb_name": "Western IRB",
                "site_id": "SITE-101", "submitted_date": now - timedelta(days=42),
                "status": IRBStatus.APPROVED, "approval_date": now - timedelta(days=18),
                "conditions": None, "continuing_review_date": now + timedelta(days=347),
            },
            {
                "id": "IRB-006", "amendment_id": "AMD-002", "irb_name": "Cleveland Clinic IRB",
                "site_id": "SITE-102", "submitted_date": now - timedelta(days=42),
                "status": IRBStatus.APPROVED, "approval_date": now - timedelta(days=16),
                "conditions": None, "continuing_review_date": now + timedelta(days=349),
            },
            {
                "id": "IRB-007", "amendment_id": "AMD-002", "irb_name": "Johns Hopkins IRB",
                "site_id": "SITE-103", "submitted_date": now - timedelta(days=40),
                "status": IRBStatus.APPROVED, "approval_date": now - timedelta(days=15),
                "conditions": "Ensure updated consent form describes new functional assessment",
                "continuing_review_date": now + timedelta(days=350),
            },
            {
                "id": "IRB-008", "amendment_id": "AMD-002", "irb_name": "Mayo Clinic IRB",
                "site_id": "SITE-104", "submitted_date": now - timedelta(days=38),
                "status": IRBStatus.PENDING, "approval_date": None,
                "conditions": None, "continuing_review_date": None,
            },
            # AMD-003 (Dupixent dosing) - mixed statuses
            {
                "id": "IRB-009", "amendment_id": "AMD-003", "irb_name": "Johns Hopkins IRB",
                "site_id": "SITE-103", "submitted_date": now - timedelta(days=18),
                "status": IRBStatus.PENDING, "approval_date": None,
                "conditions": None, "continuing_review_date": None,
            },
            {
                "id": "IRB-010", "amendment_id": "AMD-003", "irb_name": "Duke IRB",
                "site_id": "SITE-105", "submitted_date": now - timedelta(days=18),
                "status": IRBStatus.MODIFICATIONS_REQUIRED, "approval_date": None,
                "conditions": "Clarify dose re-escalation criteria in consent form; provide patient-facing dose schedule diagram",
                "continuing_review_date": None,
            },
            {
                "id": "IRB-011", "amendment_id": "AMD-003", "irb_name": "Cedars-Sinai IRB",
                "site_id": "SITE-106", "submitted_date": now - timedelta(days=16),
                "status": IRBStatus.PENDING, "approval_date": None,
                "conditions": None, "continuing_review_date": None,
            },
            # AMD-006 (administrative) - all approved quickly
            {
                "id": "IRB-012", "amendment_id": "AMD-006", "irb_name": "Western IRB",
                "site_id": "SITE-101", "submitted_date": now - timedelta(days=58),
                "status": IRBStatus.APPROVED, "approval_date": now - timedelta(days=55),
                "conditions": None, "continuing_review_date": now + timedelta(days=307),
            },
            {
                "id": "IRB-013", "amendment_id": "AMD-006", "irb_name": "Cleveland Clinic IRB",
                "site_id": "SITE-102", "submitted_date": now - timedelta(days=58),
                "status": IRBStatus.APPROVED, "approval_date": now - timedelta(days=54),
                "conditions": None, "continuing_review_date": now + timedelta(days=311),
            },
            {
                "id": "IRB-014", "amendment_id": "AMD-006", "irb_name": "Johns Hopkins IRB",
                "site_id": "SITE-103", "submitted_date": now - timedelta(days=57),
                "status": IRBStatus.APPROVED, "approval_date": now - timedelta(days=53),
                "conditions": None, "continuing_review_date": now + timedelta(days=312),
            },
            {
                "id": "IRB-015", "amendment_id": "AMD-006", "irb_name": "Mayo Clinic IRB",
                "site_id": "SITE-104", "submitted_date": now - timedelta(days=57),
                "status": IRBStatus.APPROVED, "approval_date": now - timedelta(days=52),
                "conditions": None, "continuing_review_date": now + timedelta(days=313),
            },
            # Additional IRB submissions for variety
            {
                "id": "IRB-016", "amendment_id": "AMD-003", "irb_name": "Central IRB Services",
                "site_id": "SITE-105", "submitted_date": now - timedelta(days=15),
                "status": IRBStatus.DEFERRED, "approval_date": None,
                "conditions": "Deferred pending additional PK data review",
                "continuing_review_date": None,
            },
            {
                "id": "IRB-017", "amendment_id": "AMD-002", "irb_name": "Stanford IRB",
                "site_id": "SITE-108", "submitted_date": now - timedelta(days=35),
                "status": IRBStatus.APPROVED, "approval_date": now - timedelta(days=12),
                "conditions": None, "continuing_review_date": now + timedelta(days=353),
            },
            {
                "id": "IRB-018", "amendment_id": "AMD-001", "irb_name": "Stanford IRB",
                "site_id": "SITE-108", "submitted_date": now - timedelta(days=110),
                "status": IRBStatus.APPROVED, "approval_date": now - timedelta(days=85),
                "conditions": None, "continuing_review_date": now + timedelta(days=280),
            },
            {
                "id": "IRB-019", "amendment_id": "AMD-006", "irb_name": "Stanford IRB",
                "site_id": "SITE-108", "submitted_date": now - timedelta(days=56),
                "status": IRBStatus.NOT_APPLICABLE, "approval_date": None,
                "conditions": "Administrative amendments do not require full board review at this institution",
                "continuing_review_date": None,
            },
            {
                "id": "IRB-020", "amendment_id": "AMD-003", "irb_name": "Mass General IRB",
                "site_id": "SITE-107", "submitted_date": now - timedelta(days=14),
                "status": IRBStatus.PENDING, "approval_date": None,
                "conditions": None, "continuing_review_date": None,
            },
        ]

        for irb in irb_data:
            sub = IRBSubmission(**irb)
            self._irb_submissions[sub.id] = sub

        # Attach IRB submissions to amendments
        for amd_id, amd in self._amendments.items():
            subs = [s for s in self._irb_submissions.values() if s.amendment_id == amd_id]
            amd_data = amd.model_dump()
            amd_data["irb_submissions"] = subs
            self._amendments[amd_id] = ProtocolAmendment(**amd_data)

        # --- Impact Assessments for each amendment ---
        impact_data = [
            {
                "amendment_id": "AMD-001",
                "operational_impact": ImpactSeverity.HIGH,
                "enrollment_impact": ImpactSeverity.HIGH,
                "safety_impact": ImpactSeverity.LOW,
                "cost_impact_estimate": 250000.0,
                "timeline_impact_weeks": 4,
                "re_consent_required": True,
                "training_required": True,
            },
            {
                "amendment_id": "AMD-002",
                "operational_impact": ImpactSeverity.MEDIUM,
                "enrollment_impact": ImpactSeverity.LOW,
                "safety_impact": ImpactSeverity.LOW,
                "cost_impact_estimate": 120000.0,
                "timeline_impact_weeks": 2,
                "re_consent_required": False,
                "training_required": True,
            },
            {
                "amendment_id": "AMD-003",
                "operational_impact": ImpactSeverity.HIGH,
                "enrollment_impact": ImpactSeverity.MEDIUM,
                "safety_impact": ImpactSeverity.HIGH,
                "cost_impact_estimate": 380000.0,
                "timeline_impact_weeks": 6,
                "re_consent_required": True,
                "training_required": True,
            },
            {
                "amendment_id": "AMD-004",
                "operational_impact": ImpactSeverity.HIGH,
                "enrollment_impact": ImpactSeverity.HIGH,
                "safety_impact": ImpactSeverity.LOW,
                "cost_impact_estimate": 850000.0,
                "timeline_impact_weeks": 12,
                "re_consent_required": False,
                "training_required": True,
            },
            {
                "amendment_id": "AMD-005",
                "operational_impact": ImpactSeverity.MEDIUM,
                "enrollment_impact": ImpactSeverity.LOW,
                "safety_impact": ImpactSeverity.HIGH,
                "cost_impact_estimate": 95000.0,
                "timeline_impact_weeks": 3,
                "re_consent_required": True,
                "training_required": True,
            },
            {
                "amendment_id": "AMD-006",
                "operational_impact": ImpactSeverity.LOW,
                "enrollment_impact": ImpactSeverity.LOW,
                "safety_impact": ImpactSeverity.LOW,
                "cost_impact_estimate": 5000.0,
                "timeline_impact_weeks": 0,
                "re_consent_required": False,
                "training_required": False,
            },
        ]

        for imp in impact_data:
            assessment = AmendmentImpactAssessment(**imp)
            self._impact_assessments[imp["amendment_id"]] = assessment

        # --- Site implementation tracking ---
        # AMD-001: fully implemented across all sites
        self._site_implementations["AMD-001"] = {
            "SITE-101": SiteImplementationStatus(
                site_id="SITE-101", irb_status=IRBStatus.APPROVED,
                implemented=True, implementation_date=now - timedelta(days=75),
                re_consent_required=True, re_consent_completed=28, re_consent_total=30,
            ),
            "SITE-102": SiteImplementationStatus(
                site_id="SITE-102", irb_status=IRBStatus.APPROVED,
                implemented=True, implementation_date=now - timedelta(days=72),
                re_consent_required=True, re_consent_completed=22, re_consent_total=22,
            ),
            "SITE-103": SiteImplementationStatus(
                site_id="SITE-103", irb_status=IRBStatus.APPROVED,
                implemented=True, implementation_date=now - timedelta(days=70),
                re_consent_required=True, re_consent_completed=15, re_consent_total=18,
            ),
            "SITE-104": SiteImplementationStatus(
                site_id="SITE-104", irb_status=IRBStatus.APPROVED,
                implemented=True, implementation_date=now - timedelta(days=68),
                re_consent_required=True, re_consent_completed=12, re_consent_total=14,
            ),
        }

        # AMD-002: approved but not yet implemented
        self._site_implementations["AMD-002"] = {
            "SITE-101": SiteImplementationStatus(
                site_id="SITE-101", irb_status=IRBStatus.APPROVED,
                implemented=False, re_consent_required=False,
            ),
            "SITE-102": SiteImplementationStatus(
                site_id="SITE-102", irb_status=IRBStatus.APPROVED,
                implemented=False, re_consent_required=False,
            ),
            "SITE-103": SiteImplementationStatus(
                site_id="SITE-103", irb_status=IRBStatus.APPROVED,
                implemented=False, re_consent_required=False,
            ),
            "SITE-104": SiteImplementationStatus(
                site_id="SITE-104", irb_status=IRBStatus.PENDING,
                implemented=False, re_consent_required=False,
            ),
        }

        # AMD-003: IRB submitted, not yet approved
        self._site_implementations["AMD-003"] = {
            "SITE-103": SiteImplementationStatus(
                site_id="SITE-103", irb_status=IRBStatus.PENDING,
                implemented=False, re_consent_required=True,
                re_consent_completed=0, re_consent_total=18,
            ),
            "SITE-105": SiteImplementationStatus(
                site_id="SITE-105", irb_status=IRBStatus.MODIFICATIONS_REQUIRED,
                implemented=False, re_consent_required=True,
                re_consent_completed=0, re_consent_total=25,
            ),
            "SITE-106": SiteImplementationStatus(
                site_id="SITE-106", irb_status=IRBStatus.PENDING,
                implemented=False, re_consent_required=True,
                re_consent_completed=0, re_consent_total=20,
            ),
        }

        # AMD-006: administrative, fully implemented
        self._site_implementations["AMD-006"] = {
            "SITE-101": SiteImplementationStatus(
                site_id="SITE-101", irb_status=IRBStatus.APPROVED,
                implemented=True, implementation_date=now - timedelta(days=50),
                re_consent_required=False,
            ),
            "SITE-102": SiteImplementationStatus(
                site_id="SITE-102", irb_status=IRBStatus.APPROVED,
                implemented=True, implementation_date=now - timedelta(days=49),
                re_consent_required=False,
            ),
            "SITE-103": SiteImplementationStatus(
                site_id="SITE-103", irb_status=IRBStatus.APPROVED,
                implemented=True, implementation_date=now - timedelta(days=48),
                re_consent_required=False,
            ),
            "SITE-104": SiteImplementationStatus(
                site_id="SITE-104", irb_status=IRBStatus.APPROVED,
                implemented=True, implementation_date=now - timedelta(days=47),
                re_consent_required=False,
            ),
        }

    # ------------------------------------------------------------------
    # Amendment CRUD
    # ------------------------------------------------------------------

    def list_amendments(
        self,
        *,
        trial_id: str | None = None,
        status: AmendmentStatus | None = None,
        amendment_type: AmendmentType | None = None,
    ) -> list[ProtocolAmendment]:
        """List amendments with optional filters."""
        with self._lock:
            result = list(self._amendments.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if status is not None:
            result = [a for a in result if a.status == status]
        if amendment_type is not None:
            result = [a for a in result if a.amendment_type == amendment_type]

        return sorted(result, key=lambda a: a.created_at, reverse=True)

    def get_amendment(self, amendment_id: str) -> ProtocolAmendment | None:
        """Get a single amendment by ID."""
        with self._lock:
            return self._amendments.get(amendment_id)

    def create_amendment(self, payload: AmendmentCreate) -> ProtocolAmendment:
        """Create a new protocol amendment."""
        now = datetime.now(timezone.utc)
        amd_id = f"AMD-{uuid4().hex[:8].upper()}"
        amd = ProtocolAmendment(
            id=amd_id,
            trial_id=payload.trial_id,
            amendment_number=payload.amendment_number,
            version_from=payload.version_from,
            version_to=payload.version_to,
            amendment_type=payload.amendment_type,
            status=AmendmentStatus.DRAFT,
            title=payload.title,
            rationale=payload.rationale,
            description=payload.description,
            impacted_sections=payload.impacted_sections,
            impacted_areas=payload.impacted_areas,
            submitted_date=None,
            approved_date=None,
            implementation_date=None,
            affected_sites=payload.affected_sites,
            irb_submissions=[],
            created_at=now,
        )
        with self._lock:
            self._amendments[amd_id] = amd
            # Initialize site implementations
            self._site_implementations[amd_id] = {}
            for site_id in payload.affected_sites:
                self._site_implementations[amd_id][site_id] = SiteImplementationStatus(
                    site_id=site_id,
                    irb_status=IRBStatus.PENDING,
                    implemented=False,
                )
        logger.info("Created amendment %s: %s", amd_id, payload.title)
        return amd

    def update_amendment(self, amendment_id: str, payload: AmendmentUpdate) -> ProtocolAmendment | None:
        """Update an existing amendment."""
        with self._lock:
            existing = self._amendments.get(amendment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ProtocolAmendment(**data)
            self._amendments[amendment_id] = updated
        return updated

    def delete_amendment(self, amendment_id: str) -> bool:
        """Delete an amendment. Returns True if deleted, False if not found."""
        with self._lock:
            if amendment_id in self._amendments:
                del self._amendments[amendment_id]
                # Clean up related data
                self._impact_assessments.pop(amendment_id, None)
                self._site_implementations.pop(amendment_id, None)
                # Remove related IRB submissions
                to_remove = [
                    k for k, v in self._irb_submissions.items()
                    if v.amendment_id == amendment_id
                ]
                for k in to_remove:
                    del self._irb_submissions[k]
                return True
            return False

    # ------------------------------------------------------------------
    # Amendment Lifecycle
    # ------------------------------------------------------------------

    def submit_amendment(self, amendment_id: str, payload: AmendmentSubmit) -> ProtocolAmendment | None:
        """Submit an amendment for sponsor review."""
        with self._lock:
            existing = self._amendments.get(amendment_id)
            if existing is None:
                return None

            if existing.status not in (AmendmentStatus.DRAFT,):
                raise ValueError(
                    f"Amendment '{amendment_id}' cannot be submitted from status '{existing.status.value}'"
                )

            data = existing.model_dump()
            data["status"] = AmendmentStatus.SPONSOR_REVIEW
            data["submitted_date"] = payload.submitted_date
            updated = ProtocolAmendment(**data)
            self._amendments[amendment_id] = updated
        logger.info("Submitted amendment %s for review", amendment_id)
        return updated

    def approve_amendment(self, amendment_id: str) -> ProtocolAmendment | None:
        """Mark amendment as IRB approved (after all IRBs approve)."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._amendments.get(amendment_id)
            if existing is None:
                return None

            if existing.status not in (AmendmentStatus.IRB_SUBMITTED,):
                raise ValueError(
                    f"Amendment '{amendment_id}' cannot be approved from status '{existing.status.value}'"
                )

            data = existing.model_dump()
            data["status"] = AmendmentStatus.IRB_APPROVED
            data["approved_date"] = now
            updated = ProtocolAmendment(**data)
            self._amendments[amendment_id] = updated
        logger.info("Approved amendment %s", amendment_id)
        return updated

    def implement_amendment(self, amendment_id: str, payload: AmendmentImplement) -> ProtocolAmendment | None:
        """Mark amendment as implemented."""
        with self._lock:
            existing = self._amendments.get(amendment_id)
            if existing is None:
                return None

            if existing.status not in (AmendmentStatus.IRB_APPROVED,):
                raise ValueError(
                    f"Amendment '{amendment_id}' cannot be implemented from status '{existing.status.value}'"
                )

            data = existing.model_dump()
            data["status"] = AmendmentStatus.IMPLEMENTED
            data["implementation_date"] = payload.implementation_date
            updated = ProtocolAmendment(**data)
            self._amendments[amendment_id] = updated
        logger.info("Implemented amendment %s", amendment_id)
        return updated

    def withdraw_amendment(self, amendment_id: str) -> ProtocolAmendment | None:
        """Withdraw an amendment."""
        with self._lock:
            existing = self._amendments.get(amendment_id)
            if existing is None:
                return None

            if existing.status == AmendmentStatus.IMPLEMENTED:
                raise ValueError(
                    f"Amendment '{amendment_id}' cannot be withdrawn after implementation"
                )

            data = existing.model_dump()
            data["status"] = AmendmentStatus.WITHDRAWN
            updated = ProtocolAmendment(**data)
            self._amendments[amendment_id] = updated
        logger.info("Withdrew amendment %s", amendment_id)
        return updated

    # ------------------------------------------------------------------
    # IRB Submissions
    # ------------------------------------------------------------------

    def list_irb_submissions(
        self,
        *,
        amendment_id: str | None = None,
        site_id: str | None = None,
        status: IRBStatus | None = None,
    ) -> list[IRBSubmission]:
        """List IRB submissions with optional filters."""
        with self._lock:
            result = list(self._irb_submissions.values())

        if amendment_id is not None:
            result = [s for s in result if s.amendment_id == amendment_id]
        if site_id is not None:
            result = [s for s in result if s.site_id == site_id]
        if status is not None:
            result = [s for s in result if s.status == status]

        return sorted(result, key=lambda s: s.submitted_date, reverse=True)

    def get_irb_submission(self, submission_id: str) -> IRBSubmission | None:
        """Get a single IRB submission by ID."""
        with self._lock:
            return self._irb_submissions.get(submission_id)

    def create_irb_submission(
        self, amendment_id: str, payload: IRBSubmissionCreate
    ) -> IRBSubmission:
        """Create an IRB submission for an amendment."""
        sub_id = f"IRB-{uuid4().hex[:8].upper()}"

        with self._lock:
            amd = self._amendments.get(amendment_id)
            if amd is None:
                raise ValueError(f"Amendment '{amendment_id}' not found")

            sub = IRBSubmission(
                id=sub_id,
                amendment_id=amendment_id,
                irb_name=payload.irb_name,
                site_id=payload.site_id,
                submitted_date=payload.submitted_date,
                status=IRBStatus.PENDING,
                approval_date=None,
                conditions=None,
                continuing_review_date=None,
            )
            self._irb_submissions[sub_id] = sub

            # Re-attach IRB submissions to amendment
            self._refresh_amendment_irb_list(amendment_id)

        logger.info("Created IRB submission %s for amendment %s", sub_id, amendment_id)
        return sub

    def update_irb_submission(
        self, submission_id: str, payload: IRBSubmissionUpdate
    ) -> IRBSubmission | None:
        """Update an IRB submission."""
        with self._lock:
            existing = self._irb_submissions.get(submission_id)
            if existing is None:
                return None

            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = IRBSubmission(**data)
            self._irb_submissions[submission_id] = updated

            # Update site implementation status if IRB approved
            if updated.status == IRBStatus.APPROVED:
                amd_impls = self._site_implementations.get(updated.amendment_id, {})
                if updated.site_id in amd_impls:
                    impl = amd_impls[updated.site_id]
                    impl_data = impl.model_dump()
                    impl_data["irb_status"] = IRBStatus.APPROVED
                    amd_impls[updated.site_id] = SiteImplementationStatus(**impl_data)

            # Refresh amendment IRB list
            self._refresh_amendment_irb_list(existing.amendment_id)

        return updated

    def _refresh_amendment_irb_list(self, amendment_id: str) -> None:
        """Refresh the embedded IRB submissions list on an amendment.

        Must be called while holding ``_lock``.
        """
        amd = self._amendments.get(amendment_id)
        if amd is None:
            return
        subs = [s for s in self._irb_submissions.values() if s.amendment_id == amendment_id]
        data = amd.model_dump()
        data["irb_submissions"] = subs
        self._amendments[amendment_id] = ProtocolAmendment(**data)

    # ------------------------------------------------------------------
    # Impact Assessments
    # ------------------------------------------------------------------

    def get_impact_assessment(self, amendment_id: str) -> AmendmentImpactAssessment | None:
        """Get impact assessment for an amendment."""
        with self._lock:
            return self._impact_assessments.get(amendment_id)

    def create_impact_assessment(
        self, amendment_id: str, assessment: AmendmentImpactAssessment
    ) -> AmendmentImpactAssessment:
        """Create or update impact assessment for an amendment."""
        with self._lock:
            if amendment_id not in self._amendments:
                raise ValueError(f"Amendment '{amendment_id}' not found")
            self._impact_assessments[amendment_id] = assessment
        logger.info("Created impact assessment for amendment %s", amendment_id)
        return assessment

    # ------------------------------------------------------------------
    # Site Implementation
    # ------------------------------------------------------------------

    def get_site_implementations(self, amendment_id: str) -> list[SiteImplementationStatus]:
        """Get implementation status for all sites for an amendment."""
        with self._lock:
            impls = self._site_implementations.get(amendment_id, {})
            return sorted(impls.values(), key=lambda s: s.site_id)

    def get_site_implementation(
        self, amendment_id: str, site_id: str
    ) -> SiteImplementationStatus | None:
        """Get implementation status for a specific site."""
        with self._lock:
            impls = self._site_implementations.get(amendment_id, {})
            return impls.get(site_id)

    def update_site_implementation(
        self,
        amendment_id: str,
        site_id: str,
        *,
        implemented: bool | None = None,
        implementation_date: datetime | None = None,
    ) -> SiteImplementationStatus | None:
        """Update site implementation status."""
        with self._lock:
            impls = self._site_implementations.get(amendment_id)
            if impls is None:
                return None
            existing = impls.get(site_id)
            if existing is None:
                return None

            data = existing.model_dump()
            if implemented is not None:
                data["implemented"] = implemented
            if implementation_date is not None:
                data["implementation_date"] = implementation_date
            updated = SiteImplementationStatus(**data)
            impls[site_id] = updated
        return updated

    def update_re_consent_progress(
        self,
        amendment_id: str,
        site_id: str,
        payload: ReConsentUpdate,
    ) -> SiteImplementationStatus | None:
        """Update re-consent progress for a site."""
        with self._lock:
            impls = self._site_implementations.get(amendment_id)
            if impls is None:
                return None
            existing = impls.get(site_id)
            if existing is None:
                return None

            data = existing.model_dump()
            data["re_consent_completed"] = payload.completed
            data["re_consent_total"] = payload.total
            updated = SiteImplementationStatus(**data)
            impls[site_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Amendment Tracker
    # ------------------------------------------------------------------

    def get_amendment_tracker(self, trial_id: str) -> AmendmentTracker:
        """Get aggregated amendment tracker for a trial."""
        with self._lock:
            amendments = [
                a for a in self._amendments.values() if a.trial_id == trial_id
            ]

        if not amendments:
            return AmendmentTracker(
                trial_id=trial_id,
                total_amendments=0,
                amendments_by_status={},
                amendments_by_type={},
                avg_approval_days=0.0,
                sites_pending_implementation=0,
                re_consent_progress={"total_required": 0, "completed": 0, "pending": 0},
            )

        # Counts by status and type
        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}
        approval_days_list: list[float] = []

        for amd in amendments:
            by_status[amd.status.value] = by_status.get(amd.status.value, 0) + 1
            by_type[amd.amendment_type.value] = by_type.get(amd.amendment_type.value, 0) + 1
            if amd.submitted_date and amd.approved_date:
                delta = (amd.approved_date - amd.submitted_date).days
                approval_days_list.append(float(delta))

        avg_days = round(sum(approval_days_list) / max(1, len(approval_days_list)), 1)

        # Sites pending implementation
        pending_sites = 0
        total_re_consent_required = 0
        total_re_consent_completed = 0

        with self._lock:
            for amd in amendments:
                impls = self._site_implementations.get(amd.id, {})
                for impl in impls.values():
                    if not impl.implemented:
                        pending_sites += 1
                    if impl.re_consent_required:
                        total_re_consent_required += impl.re_consent_total
                        total_re_consent_completed += impl.re_consent_completed

        return AmendmentTracker(
            trial_id=trial_id,
            total_amendments=len(amendments),
            amendments_by_status=by_status,
            amendments_by_type=by_type,
            avg_approval_days=avg_days,
            sites_pending_implementation=pending_sites,
            re_consent_progress={
                "total_required": total_re_consent_required,
                "completed": total_re_consent_completed,
                "pending": total_re_consent_required - total_re_consent_completed,
            },
        )

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> AmendmentMetrics:
        """Compute aggregated amendment metrics across all trials."""
        with self._lock:
            amendments = list(self._amendments.values())
            irb_submissions = list(self._irb_submissions.values())
            impact_assessments = list(self._impact_assessments.values())
            site_impls = dict(self._site_implementations)

        # By status / type
        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}
        approval_days_list: list[float] = []

        for amd in amendments:
            by_status[amd.status.value] = by_status.get(amd.status.value, 0) + 1
            by_type[amd.amendment_type.value] = by_type.get(amd.amendment_type.value, 0) + 1
            if amd.submitted_date and amd.approved_date:
                delta = (amd.approved_date - amd.submitted_date).days
                approval_days_list.append(float(delta))

        avg_days = round(sum(approval_days_list) / max(1, len(approval_days_list)), 1)

        # IRB submissions by status
        irb_by_status: dict[str, int] = {}
        for sub in irb_submissions:
            irb_by_status[sub.status.value] = irb_by_status.get(sub.status.value, 0) + 1

        # Re-consent count
        re_consent_count = sum(
            1 for ia in impact_assessments if ia.re_consent_required
        )

        # Pending implementations
        pending_sites = 0
        for amd_id, impls in site_impls.items():
            for impl in impls.values():
                if not impl.implemented:
                    pending_sites += 1

        return AmendmentMetrics(
            total_amendments=len(amendments),
            amendments_by_status=by_status,
            amendments_by_type=by_type,
            avg_approval_days=avg_days,
            total_irb_submissions=len(irb_submissions),
            irb_submissions_by_status=irb_by_status,
            amendments_requiring_re_consent=re_consent_count,
            total_sites_pending_implementation=pending_sites,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ProtocolAmendmentService | None = None
_instance_lock = threading.Lock()


def get_protocol_amendment_service() -> ProtocolAmendmentService:
    """Return the singleton ProtocolAmendmentService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ProtocolAmendmentService()
    return _instance


def reset_protocol_amendment_service() -> ProtocolAmendmentService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = ProtocolAmendmentService()
    return _instance
