"""Clinical Trial Risk Management Service (RISK-MGMT).

Manages trial-level risk identification, risk assessment, risk mitigation
planning, risk monitoring, risk reviews, issue escalation, and risk metrics.

Usage:
    from app.services.risk_management_service import (
        get_risk_management_service,
    )

    svc = get_risk_management_service()
    risks = svc.list_risks()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.risk_management import (
    IssueStatus,
    MitigationStatus,
    RiskCategory,
    RiskImpact,
    RiskIssue,
    RiskIssueCreate,
    RiskIssueUpdate,
    RiskLevel,
    RiskManagementMetrics,
    RiskMitigation,
    RiskMitigationCreate,
    RiskMitigationUpdate,
    RiskProbability,
    RiskReview,
    RiskReviewCreate,
    RiskStatus,
    TrialRisk,
    TrialRiskCreate,
    TrialRiskUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

# ---------------------------------------------------------------------------
# Probability x Impact -> Risk Level matrix
# ---------------------------------------------------------------------------

_RISK_MATRIX: dict[tuple[RiskProbability, RiskImpact], RiskLevel] = {
    # RARE
    (RiskProbability.RARE, RiskImpact.NEGLIGIBLE): RiskLevel.LOW,
    (RiskProbability.RARE, RiskImpact.MINOR): RiskLevel.LOW,
    (RiskProbability.RARE, RiskImpact.MODERATE): RiskLevel.LOW,
    (RiskProbability.RARE, RiskImpact.MAJOR): RiskLevel.MEDIUM,
    (RiskProbability.RARE, RiskImpact.CATASTROPHIC): RiskLevel.HIGH,
    # UNLIKELY
    (RiskProbability.UNLIKELY, RiskImpact.NEGLIGIBLE): RiskLevel.LOW,
    (RiskProbability.UNLIKELY, RiskImpact.MINOR): RiskLevel.LOW,
    (RiskProbability.UNLIKELY, RiskImpact.MODERATE): RiskLevel.MEDIUM,
    (RiskProbability.UNLIKELY, RiskImpact.MAJOR): RiskLevel.MEDIUM,
    (RiskProbability.UNLIKELY, RiskImpact.CATASTROPHIC): RiskLevel.HIGH,
    # POSSIBLE
    (RiskProbability.POSSIBLE, RiskImpact.NEGLIGIBLE): RiskLevel.LOW,
    (RiskProbability.POSSIBLE, RiskImpact.MINOR): RiskLevel.MEDIUM,
    (RiskProbability.POSSIBLE, RiskImpact.MODERATE): RiskLevel.MEDIUM,
    (RiskProbability.POSSIBLE, RiskImpact.MAJOR): RiskLevel.HIGH,
    (RiskProbability.POSSIBLE, RiskImpact.CATASTROPHIC): RiskLevel.CRITICAL,
    # LIKELY
    (RiskProbability.LIKELY, RiskImpact.NEGLIGIBLE): RiskLevel.LOW,
    (RiskProbability.LIKELY, RiskImpact.MINOR): RiskLevel.MEDIUM,
    (RiskProbability.LIKELY, RiskImpact.MODERATE): RiskLevel.HIGH,
    (RiskProbability.LIKELY, RiskImpact.MAJOR): RiskLevel.HIGH,
    (RiskProbability.LIKELY, RiskImpact.CATASTROPHIC): RiskLevel.CRITICAL,
    # ALMOST_CERTAIN
    (RiskProbability.ALMOST_CERTAIN, RiskImpact.NEGLIGIBLE): RiskLevel.MEDIUM,
    (RiskProbability.ALMOST_CERTAIN, RiskImpact.MINOR): RiskLevel.MEDIUM,
    (RiskProbability.ALMOST_CERTAIN, RiskImpact.MODERATE): RiskLevel.HIGH,
    (RiskProbability.ALMOST_CERTAIN, RiskImpact.MAJOR): RiskLevel.CRITICAL,
    (RiskProbability.ALMOST_CERTAIN, RiskImpact.CATASTROPHIC): RiskLevel.CRITICAL,
}


def compute_risk_level(probability: RiskProbability, impact: RiskImpact) -> RiskLevel:
    """Compute risk level from probability x impact matrix."""
    return _RISK_MATRIX.get((probability, impact), RiskLevel.MEDIUM)


class RiskManagementService:
    """In-memory Clinical Trial Risk Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._risks: dict[str, TrialRisk] = {}
        self._mitigations: dict[str, RiskMitigation] = {}
        self._reviews: dict[str, RiskReview] = {}
        self._issues: dict[str, RiskIssue] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic risk management data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Trial Risks ---
        risks_data = [
            # EYLEA risks
            {
                "id": "RSK-001", "trial_id": EYLEA_TRIAL,
                "risk_title": "Endophthalmitis post-injection infection risk",
                "category": RiskCategory.SAFETY,
                "description": "Risk of endophthalmitis following intravitreal injection of EYLEA HD, which could lead to vision loss and SAE reporting obligations.",
                "probability": RiskProbability.UNLIKELY,
                "impact": RiskImpact.CATASTROPHIC,
                "risk_level": RiskLevel.HIGH,
                "status": RiskStatus.MITIGATING,
                "identified_by": "Dr. Elizabeth Chen",
                "identified_date": now - timedelta(days=180),
                "owner": "Dr. James Rodriguez",
                "affected_areas": ["patient safety", "regulatory reporting", "site training"],
                "triggers": ["infection rate > 0.05%", "cluster of events at single site"],
                "residual_risk_level": RiskLevel.MEDIUM,
                "last_reviewed": now - timedelta(days=14),
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "RSK-002", "trial_id": EYLEA_TRIAL,
                "risk_title": "OCT imaging quality variability across sites",
                "category": RiskCategory.QUALITY,
                "description": "Inconsistent OCT image quality across investigational sites may compromise BCVA endpoint adjudication accuracy.",
                "probability": RiskProbability.POSSIBLE,
                "impact": RiskImpact.MAJOR,
                "risk_level": RiskLevel.HIGH,
                "status": RiskStatus.MONITORING,
                "identified_by": "Dr. Sarah Thompson",
                "identified_date": now - timedelta(days=150),
                "owner": "Dr. Laura Kim",
                "affected_areas": ["endpoint adjudication", "data quality", "site monitoring"],
                "triggers": ["image rejection rate > 10%", "adjudication indeterminate rate > 5%"],
                "residual_risk_level": RiskLevel.MEDIUM,
                "last_reviewed": now - timedelta(days=7),
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "RSK-003", "trial_id": EYLEA_TRIAL,
                "risk_title": "Patient recruitment delays in Asia-Pacific region",
                "category": RiskCategory.OPERATIONAL,
                "description": "Slower than expected enrollment at APAC sites threatens study timeline and database lock dates.",
                "probability": RiskProbability.LIKELY,
                "impact": RiskImpact.MAJOR,
                "risk_level": RiskLevel.HIGH,
                "status": RiskStatus.ASSESSED,
                "identified_by": "Clinical Operations Lead",
                "identified_date": now - timedelta(days=120),
                "owner": "Regional Operations Director",
                "affected_areas": ["enrollment timeline", "study budget", "site activation"],
                "triggers": ["enrollment < 70% of target at month 12", "site activation delays > 4 weeks"],
                "residual_risk_level": None,
                "last_reviewed": now - timedelta(days=30),
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "RSK-004", "trial_id": EYLEA_TRIAL,
                "risk_title": "Regulatory submission delay due to protocol amendments",
                "category": RiskCategory.REGULATORY,
                "description": "Frequent protocol amendments may delay FDA supplemental BLA submission timeline for EYLEA HD.",
                "probability": RiskProbability.POSSIBLE,
                "impact": RiskImpact.MAJOR,
                "risk_level": RiskLevel.HIGH,
                "status": RiskStatus.IDENTIFIED,
                "identified_by": "Regulatory Affairs Director",
                "identified_date": now - timedelta(days=60),
                "owner": "VP Regulatory Affairs",
                "affected_areas": ["submission timeline", "regulatory strategy", "protocol management"],
                "triggers": ["> 2 substantial amendments", "FDA type A meeting request"],
                "residual_risk_level": None,
                "last_reviewed": None,
                "created_at": now - timedelta(days=60),
            },
            # DUPIXENT risks
            {
                "id": "RSK-005", "trial_id": DUPIXENT_TRIAL,
                "risk_title": "Injection site reaction severity escalation",
                "category": RiskCategory.SAFETY,
                "description": "Increased incidence and severity of injection site reactions in the high-dose cohort may trigger DSMB review.",
                "probability": RiskProbability.POSSIBLE,
                "impact": RiskImpact.MAJOR,
                "risk_level": RiskLevel.HIGH,
                "status": RiskStatus.MITIGATING,
                "identified_by": "Dr. Robert Williams",
                "identified_date": now - timedelta(days=200),
                "owner": "Dr. Angela Martinez",
                "affected_areas": ["patient safety", "dose selection", "DSMB review"],
                "triggers": ["ISR grade >= 3 rate > 5%", "any ISR requiring hospitalization"],
                "residual_risk_level": RiskLevel.MEDIUM,
                "last_reviewed": now - timedelta(days=10),
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "RSK-006", "trial_id": DUPIXENT_TRIAL,
                "risk_title": "EASI scoring inconsistency between raters",
                "category": RiskCategory.QUALITY,
                "description": "Inter-rater variability in EASI scoring may introduce measurement bias and affect primary endpoint analysis.",
                "probability": RiskProbability.LIKELY,
                "impact": RiskImpact.MODERATE,
                "risk_level": RiskLevel.HIGH,
                "status": RiskStatus.MONITORING,
                "identified_by": "Dr. David Nakamura",
                "identified_date": now - timedelta(days=160),
                "owner": "Dr. Patricia Sullivan",
                "affected_areas": ["endpoint reliability", "statistical analysis", "training"],
                "triggers": ["inter-rater kappa < 0.6", "scoring outliers > 15%"],
                "residual_risk_level": RiskLevel.LOW,
                "last_reviewed": now - timedelta(days=5),
                "created_at": now - timedelta(days=160),
            },
            {
                "id": "RSK-007", "trial_id": DUPIXENT_TRIAL,
                "risk_title": "Supply chain disruption for prefilled syringes",
                "category": RiskCategory.SUPPLY,
                "description": "Single-source manufacturer for Dupixent prefilled syringes creates supply chain vulnerability.",
                "probability": RiskProbability.UNLIKELY,
                "impact": RiskImpact.CATASTROPHIC,
                "risk_level": RiskLevel.HIGH,
                "status": RiskStatus.MITIGATING,
                "identified_by": "Supply Chain Manager",
                "identified_date": now - timedelta(days=140),
                "owner": "VP Supply Chain",
                "affected_areas": ["drug supply", "patient dosing continuity", "site inventory"],
                "triggers": ["inventory < 6 weeks supply", "manufacturer quality deviation"],
                "residual_risk_level": RiskLevel.MEDIUM,
                "last_reviewed": now - timedelta(days=21),
                "created_at": now - timedelta(days=140),
            },
            {
                "id": "RSK-008", "trial_id": DUPIXENT_TRIAL,
                "risk_title": "Budget overrun from additional safety monitoring",
                "category": RiskCategory.FINANCIAL,
                "description": "Unplanned additional safety monitoring visits and lab tests increasing per-patient costs beyond budget.",
                "probability": RiskProbability.LIKELY,
                "impact": RiskImpact.MODERATE,
                "risk_level": RiskLevel.HIGH,
                "status": RiskStatus.ASSESSED,
                "identified_by": "Finance Director",
                "identified_date": now - timedelta(days=90),
                "owner": "Clinical Finance Manager",
                "affected_areas": ["study budget", "site payments", "resource allocation"],
                "triggers": ["per-patient cost > 120% of budget", "unplanned visits > 2 per patient"],
                "residual_risk_level": None,
                "last_reviewed": now - timedelta(days=45),
                "created_at": now - timedelta(days=90),
            },
            # LIBTAYO risks
            {
                "id": "RSK-009", "trial_id": LIBTAYO_TRIAL,
                "risk_title": "Immune-related adverse event (irAE) severity",
                "category": RiskCategory.SAFETY,
                "description": "Checkpoint inhibitor therapy carries risk of severe irAEs including colitis, pneumonitis, and hepatitis requiring treatment discontinuation.",
                "probability": RiskProbability.POSSIBLE,
                "impact": RiskImpact.CATASTROPHIC,
                "risk_level": RiskLevel.CRITICAL,
                "status": RiskStatus.MITIGATING,
                "identified_by": "Dr. Catherine Liu",
                "identified_date": now - timedelta(days=220),
                "owner": "Dr. Andrew Foster",
                "affected_areas": ["patient safety", "treatment discontinuation", "regulatory reporting"],
                "triggers": ["grade 4 irAE occurrence", "irAE-related death", "irAE rate > expected CI"],
                "residual_risk_level": RiskLevel.HIGH,
                "last_reviewed": now - timedelta(days=3),
                "created_at": now - timedelta(days=220),
            },
            {
                "id": "RSK-010", "trial_id": LIBTAYO_TRIAL,
                "risk_title": "RECIST 1.1 pseudoprogression misclassification",
                "category": RiskCategory.SCIENTIFIC,
                "description": "Pseudoprogression in immunotherapy may lead to premature treatment discontinuation if misclassified as true progression per RECIST 1.1.",
                "probability": RiskProbability.POSSIBLE,
                "impact": RiskImpact.MAJOR,
                "risk_level": RiskLevel.HIGH,
                "status": RiskStatus.MONITORING,
                "identified_by": "Dr. Natalie Wong",
                "identified_date": now - timedelta(days=170),
                "owner": "Dr. Gregory Harris",
                "affected_areas": ["endpoint classification", "treatment decisions", "BICR"],
                "triggers": ["pseudoprogression rate > 10%", "discordance between BICR and site assessment"],
                "residual_risk_level": RiskLevel.MEDIUM,
                "last_reviewed": now - timedelta(days=12),
                "created_at": now - timedelta(days=170),
            },
            {
                "id": "RSK-011", "trial_id": LIBTAYO_TRIAL,
                "risk_title": "Negative media coverage impacting trial reputation",
                "category": RiskCategory.REPUTATIONAL,
                "description": "Negative media coverage of checkpoint inhibitor toxicity could impact patient willingness to enroll and site participation.",
                "probability": RiskProbability.UNLIKELY,
                "impact": RiskImpact.MODERATE,
                "risk_level": RiskLevel.MEDIUM,
                "status": RiskStatus.MONITORING,
                "identified_by": "Corporate Communications",
                "identified_date": now - timedelta(days=100),
                "owner": "Head of Patient Engagement",
                "affected_areas": ["patient recruitment", "public relations", "site engagement"],
                "triggers": ["major media article on irAE deaths", "patient advocacy group statement"],
                "residual_risk_level": RiskLevel.LOW,
                "last_reviewed": now - timedelta(days=30),
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "RSK-012", "trial_id": LIBTAYO_TRIAL,
                "risk_title": "Comparator arm drug supply shortage",
                "category": RiskCategory.OPERATIONAL,
                "description": "Potential shortage of comparator chemotherapy agent could halt randomization and compromise study integrity.",
                "probability": RiskProbability.RARE,
                "impact": RiskImpact.CATASTROPHIC,
                "risk_level": RiskLevel.HIGH,
                "status": RiskStatus.IDENTIFIED,
                "identified_by": "Clinical Supply Manager",
                "identified_date": now - timedelta(days=45),
                "owner": "VP Clinical Operations",
                "affected_areas": ["randomization", "study continuity", "regulatory compliance"],
                "triggers": ["comparator stock < 3 months", "manufacturer supply alert"],
                "residual_risk_level": None,
                "last_reviewed": None,
                "created_at": now - timedelta(days=45),
            },
        ]

        for r in risks_data:
            self._risks[r["id"]] = TrialRisk(**r)

        # --- 15 Risk Mitigations ---
        mitigations_data = [
            # RSK-001 mitigations (endophthalmitis)
            {"id": "MIT-001", "risk_id": "RSK-001", "action": "Implement standardized aseptic injection technique training for all sites", "responsible_party": "Medical Monitor", "due_date": now - timedelta(days=150), "status": MitigationStatus.IMPLEMENTED, "completion_date": now - timedelta(days=155), "effectiveness_notes": "Training completed at 100% of sites. Infection rate within target.", "cost_estimate": 45000.0},
            {"id": "MIT-002", "risk_id": "RSK-001", "action": "Deploy post-injection monitoring checklist at all sites", "responsible_party": "Clinical Operations", "due_date": now - timedelta(days=120), "status": MitigationStatus.EFFECTIVE, "completion_date": now - timedelta(days=125), "effectiveness_notes": "Checklist adoption > 95%. Zero endophthalmitis cases since deployment.", "cost_estimate": 12000.0},
            {"id": "MIT-003", "risk_id": "RSK-001", "action": "Establish rapid SAE reporting hotline for injection-related AEs", "responsible_party": "Pharmacovigilance", "due_date": now + timedelta(days=30), "status": MitigationStatus.IN_PROGRESS, "completion_date": None, "effectiveness_notes": None, "cost_estimate": 25000.0},
            # RSK-002 mitigations (OCT quality)
            {"id": "MIT-004", "risk_id": "RSK-002", "action": "Centralize OCT image quality review with automated grading", "responsible_party": "Imaging Core Lab", "due_date": now - timedelta(days=90), "status": MitigationStatus.IMPLEMENTED, "completion_date": now - timedelta(days=95), "effectiveness_notes": "Image rejection rate reduced from 15% to 4%.", "cost_estimate": 80000.0},
            {"id": "MIT-005", "risk_id": "RSK-002", "action": "Provide site-level OCT operator retraining for failing sites", "responsible_party": "Site Management", "due_date": now + timedelta(days=15), "status": MitigationStatus.PLANNED, "completion_date": None, "effectiveness_notes": None, "cost_estimate": 35000.0},
            # RSK-005 mitigations (injection site reactions)
            {"id": "MIT-006", "risk_id": "RSK-005", "action": "Implement pre-injection ice application protocol", "responsible_party": "Medical Affairs", "due_date": now - timedelta(days=170), "status": MitigationStatus.EFFECTIVE, "completion_date": now - timedelta(days=175), "effectiveness_notes": "ISR severity reduced by 40% with pre-cooling protocol.", "cost_estimate": 5000.0},
            {"id": "MIT-007", "risk_id": "RSK-005", "action": "Develop patient injection site rotation guidance", "responsible_party": "Nursing Lead", "due_date": now - timedelta(days=130), "status": MitigationStatus.IMPLEMENTED, "completion_date": now - timedelta(days=135), "effectiveness_notes": "Guidance distributed to all sites and patients.", "cost_estimate": 8000.0},
            # RSK-006 mitigations (EASI scoring)
            {"id": "MIT-008", "risk_id": "RSK-006", "action": "Conduct central EASI scoring calibration workshop", "responsible_party": "Dermatology CRO", "due_date": now - timedelta(days=100), "status": MitigationStatus.EFFECTIVE, "completion_date": now - timedelta(days=105), "effectiveness_notes": "Post-workshop inter-rater kappa improved from 0.52 to 0.78.", "cost_estimate": 60000.0},
            # RSK-007 mitigations (supply chain)
            {"id": "MIT-009", "risk_id": "RSK-007", "action": "Qualify secondary prefilled syringe manufacturer", "responsible_party": "CMC Lead", "due_date": now + timedelta(days=90), "status": MitigationStatus.IN_PROGRESS, "completion_date": None, "effectiveness_notes": None, "cost_estimate": 500000.0},
            {"id": "MIT-010", "risk_id": "RSK-007", "action": "Increase safety stock to 12 weeks at distribution centers", "responsible_party": "Supply Chain", "due_date": now - timedelta(days=60), "status": MitigationStatus.IMPLEMENTED, "completion_date": now - timedelta(days=65), "effectiveness_notes": "Safety stock increased. Current inventory at 14 weeks.", "cost_estimate": 200000.0},
            # RSK-009 mitigations (irAE severity)
            {"id": "MIT-011", "risk_id": "RSK-009", "action": "Implement irAE management algorithm per NCCN guidelines", "responsible_party": "Medical Monitor", "due_date": now - timedelta(days=200), "status": MitigationStatus.EFFECTIVE, "completion_date": now - timedelta(days=205), "effectiveness_notes": "Algorithm adopted at all sites. Time to irAE treatment reduced by 48 hours.", "cost_estimate": 30000.0},
            {"id": "MIT-012", "risk_id": "RSK-009", "action": "Establish irAE specialty consultation network", "responsible_party": "Clinical Operations", "due_date": now - timedelta(days=180), "status": MitigationStatus.IMPLEMENTED, "completion_date": now - timedelta(days=185), "effectiveness_notes": "Network of 25 specialists available for consultation within 24 hours.", "cost_estimate": 75000.0},
            {"id": "MIT-013", "risk_id": "RSK-009", "action": "Deploy real-time irAE signal detection dashboard", "responsible_party": "Pharmacovigilance", "due_date": now + timedelta(days=45), "status": MitigationStatus.IN_PROGRESS, "completion_date": None, "effectiveness_notes": None, "cost_estimate": 120000.0},
            # RSK-010 mitigations (pseudoprogression)
            {"id": "MIT-014", "risk_id": "RSK-010", "action": "Add confirmatory scan requirement per iRECIST criteria", "responsible_party": "Imaging Committee", "due_date": now - timedelta(days=140), "status": MitigationStatus.EFFECTIVE, "completion_date": now - timedelta(days=145), "effectiveness_notes": "Confirmatory scans preventing 3 premature discontinuations.", "cost_estimate": 40000.0},
            # RSK-003 mitigation (overdue)
            {"id": "MIT-015", "risk_id": "RSK-003", "action": "Activate additional APAC investigational sites", "responsible_party": "Regional Operations", "due_date": now - timedelta(days=10), "status": MitigationStatus.PLANNED, "completion_date": None, "effectiveness_notes": None, "cost_estimate": 150000.0},
        ]

        for m in mitigations_data:
            self._mitigations[m["id"]] = RiskMitigation(**m)

        # --- 10 Risk Reviews ---
        reviews_data = [
            {"id": "RVW-001", "risk_id": "RSK-001", "review_date": now - timedelta(days=14), "reviewer": "Dr. Elizabeth Chen", "current_probability": RiskProbability.UNLIKELY, "current_impact": RiskImpact.CATASTROPHIC, "current_risk_level": RiskLevel.HIGH, "notes": "Infection rate remains within acceptable limits. Mitigation measures effective. Continue monitoring.", "action_items": ["Review SAE reports monthly", "Audit aseptic technique at 5 sites"], "next_review_date": now + timedelta(days=30)},
            {"id": "RVW-002", "risk_id": "RSK-002", "review_date": now - timedelta(days=7), "reviewer": "Dr. Laura Kim", "current_probability": RiskProbability.UNLIKELY, "current_impact": RiskImpact.MAJOR, "current_risk_level": RiskLevel.MEDIUM, "notes": "Image quality significantly improved after central review implementation. Downgrading probability.", "action_items": ["Schedule retraining for 3 underperforming sites"], "next_review_date": now + timedelta(days=30)},
            {"id": "RVW-003", "risk_id": "RSK-005", "review_date": now - timedelta(days=10), "reviewer": "Dr. Angela Martinez", "current_probability": RiskProbability.POSSIBLE, "current_impact": RiskImpact.MAJOR, "current_risk_level": RiskLevel.HIGH, "notes": "ISR rates stable in high-dose cohort. Pre-cooling protocol showing benefit. No grade >= 3 events.", "action_items": ["Continue monitoring ISR rates by cohort"], "next_review_date": now + timedelta(days=14)},
            {"id": "RVW-004", "risk_id": "RSK-006", "review_date": now - timedelta(days=5), "reviewer": "Dr. Patricia Sullivan", "current_probability": RiskProbability.UNLIKELY, "current_impact": RiskImpact.MODERATE, "current_risk_level": RiskLevel.MEDIUM, "notes": "Inter-rater agreement improved to kappa 0.78 after calibration. Risk effectively mitigated.", "action_items": ["Conduct quarterly recalibration sessions"], "next_review_date": now + timedelta(days=90)},
            {"id": "RVW-005", "risk_id": "RSK-009", "review_date": now - timedelta(days=3), "reviewer": "Dr. Catherine Liu", "current_probability": RiskProbability.POSSIBLE, "current_impact": RiskImpact.CATASTROPHIC, "current_risk_level": RiskLevel.CRITICAL, "notes": "One grade 4 colitis event this month. irAE management algorithm followed. Patient recovered. Risk remains critical.", "action_items": ["Review all irAE cases at next DSMB", "Update irAE management guidelines"], "next_review_date": now + timedelta(days=14)},
            {"id": "RVW-006", "risk_id": "RSK-010", "review_date": now - timedelta(days=12), "reviewer": "Dr. Gregory Harris", "current_probability": RiskProbability.POSSIBLE, "current_impact": RiskImpact.MAJOR, "current_risk_level": RiskLevel.HIGH, "notes": "Two cases of suspected pseudoprogression identified and managed per iRECIST. Confirmatory scans prevented premature discontinuation.", "action_items": ["Present pseudoprogression cases at investigator meeting"], "next_review_date": now + timedelta(days=30)},
            {"id": "RVW-007", "risk_id": "RSK-007", "review_date": now - timedelta(days=21), "reviewer": "VP Supply Chain", "current_probability": RiskProbability.UNLIKELY, "current_impact": RiskImpact.CATASTROPHIC, "current_risk_level": RiskLevel.HIGH, "notes": "Safety stock increased to 14 weeks. Secondary manufacturer qualification on track. Risk partially mitigated.", "action_items": ["Monitor secondary manufacturer audit timeline", "Review inventory levels monthly"], "next_review_date": now + timedelta(days=30)},
            {"id": "RVW-008", "risk_id": "RSK-003", "review_date": now - timedelta(days=30), "reviewer": "Regional Operations Director", "current_probability": RiskProbability.LIKELY, "current_impact": RiskImpact.MAJOR, "current_risk_level": RiskLevel.HIGH, "notes": "APAC enrollment at 58% of target. Three additional sites proposed for activation. Timeline impact under assessment.", "action_items": ["Submit site activation packages for 3 new APAC sites", "Assess feasibility of enrollment extension"], "next_review_date": now + timedelta(days=14)},
            {"id": "RVW-009", "risk_id": "RSK-011", "review_date": now - timedelta(days=30), "reviewer": "Head of Patient Engagement", "current_probability": RiskProbability.UNLIKELY, "current_impact": RiskImpact.MODERATE, "current_risk_level": RiskLevel.MEDIUM, "notes": "No significant negative media coverage in past quarter. Patient recruitment metrics stable.", "action_items": ["Monitor media landscape quarterly"], "next_review_date": now + timedelta(days=90)},
            {"id": "RVW-010", "risk_id": "RSK-008", "review_date": now - timedelta(days=45), "reviewer": "Clinical Finance Manager", "current_probability": RiskProbability.LIKELY, "current_impact": RiskImpact.MODERATE, "current_risk_level": RiskLevel.HIGH, "notes": "Per-patient costs currently at 115% of budget. Additional safety visits contributing to overrun. Budget revision under review.", "action_items": ["Submit budget amendment request", "Negotiate volume discounts with central labs"], "next_review_date": now + timedelta(days=30)},
        ]

        for rv in reviews_data:
            self._reviews[rv["id"]] = RiskReview(**rv)

        # --- 10 Risk Issues ---
        issues_data = [
            {"id": "ISS-001", "trial_id": EYLEA_TRIAL, "risk_id": "RSK-001", "title": "Endophthalmitis case at SITE-103", "description": "Single case of endophthalmitis reported 48 hours post-injection at SITE-103. Patient treated with intravitreal antibiotics.", "category": RiskCategory.SAFETY, "severity": RiskLevel.CRITICAL, "status": IssueStatus.RESOLVED, "reported_by": "SITE-103 PI", "reported_date": now - timedelta(days=70), "assigned_to": "Dr. James Rodriguez", "resolution": "Root cause analysis completed. Aseptic technique deficiency identified. Site retrained.", "resolved_date": now - timedelta(days=55)},
            {"id": "ISS-002", "trial_id": EYLEA_TRIAL, "risk_id": "RSK-002", "title": "Batch of poor quality OCT images from SITE-102", "description": "12 consecutive OCT scans from SITE-102 failed central quality review. Equipment calibration suspected.", "category": RiskCategory.QUALITY, "severity": RiskLevel.HIGH, "status": IssueStatus.RESOLVED, "reported_by": "Imaging Core Lab", "reported_date": now - timedelta(days=45), "assigned_to": "Site Manager", "resolution": "OCT device recalibrated. Operator retrained. Re-scans completed for affected patients.", "resolved_date": now - timedelta(days=30)},
            {"id": "ISS-003", "trial_id": EYLEA_TRIAL, "risk_id": "RSK-003", "title": "Zero enrollment at SITE-108 for 8 consecutive weeks", "description": "SITE-108 in Japan has not enrolled any patients for 8 weeks despite active screening.", "category": RiskCategory.OPERATIONAL, "severity": RiskLevel.HIGH, "status": IssueStatus.INVESTIGATING, "reported_by": "Regional Monitor", "reported_date": now - timedelta(days=20), "assigned_to": "APAC Regional Lead", "resolution": None, "resolved_date": None},
            {"id": "ISS-004", "trial_id": DUPIXENT_TRIAL, "risk_id": "RSK-005", "title": "Grade 3 injection site reaction requiring ER visit", "description": "Patient PT-2015 experienced grade 3 ISR with significant swelling and pain requiring emergency room evaluation.", "category": RiskCategory.SAFETY, "severity": RiskLevel.HIGH, "status": IssueStatus.RESOLVED, "reported_by": "SITE-106 PI", "reported_date": now - timedelta(days=35), "assigned_to": "Dr. Angela Martinez", "resolution": "Patient recovered fully. Event reported as SAE. No protocol changes required per DSMB review.", "resolved_date": now - timedelta(days=20)},
            {"id": "ISS-005", "trial_id": DUPIXENT_TRIAL, "risk_id": "RSK-006", "title": "Significant EASI scoring discrepancy at SITE-104", "description": "SITE-104 EASI scores consistently 20% higher than central photographic assessment for 5 patients.", "category": RiskCategory.QUALITY, "severity": RiskLevel.MEDIUM, "status": IssueStatus.ACTION_REQUIRED, "reported_by": "Data Management", "reported_date": now - timedelta(days=15), "assigned_to": "Dermatology CRO Lead", "resolution": None, "resolved_date": None},
            {"id": "ISS-006", "trial_id": DUPIXENT_TRIAL, "risk_id": None, "title": "IRT system downtime during randomization window", "description": "Interactive Response Technology system experienced 4-hour outage during peak randomization period affecting 3 sites.", "category": RiskCategory.OPERATIONAL, "severity": RiskLevel.HIGH, "status": IssueStatus.RESOLVED, "reported_by": "IT Systems Manager", "reported_date": now - timedelta(days=25), "assigned_to": "IRT Vendor Lead", "resolution": "System restored. Root cause: database failover failure. Vendor implementing redundancy improvements.", "resolved_date": now - timedelta(days=24)},
            {"id": "ISS-007", "trial_id": LIBTAYO_TRIAL, "risk_id": "RSK-009", "title": "Grade 4 immune-mediated colitis event", "description": "Patient PT-3012 developed grade 4 colitis requiring ICU admission and IV immunosuppression.", "category": RiskCategory.SAFETY, "severity": RiskLevel.CRITICAL, "status": IssueStatus.OPEN, "reported_by": "SITE-107 PI", "reported_date": now - timedelta(days=5), "assigned_to": "Dr. Andrew Foster", "resolution": None, "resolved_date": None},
            {"id": "ISS-008", "trial_id": LIBTAYO_TRIAL, "risk_id": "RSK-010", "title": "BICR and site disagree on progression status for PT-3006", "description": "Blinded Independent Central Review classified PT-3006 as progressive disease while site assessment indicates pseudoprogression.", "category": RiskCategory.SCIENTIFIC, "severity": RiskLevel.HIGH, "status": IssueStatus.INVESTIGATING, "reported_by": "BICR Chair", "reported_date": now - timedelta(days=28), "assigned_to": "Dr. Natalie Wong", "resolution": None, "resolved_date": None},
            {"id": "ISS-009", "trial_id": LIBTAYO_TRIAL, "risk_id": None, "title": "Missing informed consent documentation at SITE-108", "description": "GCP audit identified missing re-consent documentation for protocol amendment 3 at SITE-108 affecting 8 patients.", "category": RiskCategory.REGULATORY, "severity": RiskLevel.HIGH, "status": IssueStatus.ACTION_REQUIRED, "reported_by": "GCP Auditor", "reported_date": now - timedelta(days=12), "assigned_to": "Quality Assurance Lead", "resolution": None, "resolved_date": None},
            {"id": "ISS-010", "trial_id": LIBTAYO_TRIAL, "risk_id": "RSK-012", "title": "Comparator drug expiry date approaching at 2 sites", "description": "Cisplatin stock at SITE-107 and SITE-108 approaching expiry in 6 weeks. Replacement shipment needed.", "category": RiskCategory.SUPPLY, "severity": RiskLevel.MEDIUM, "status": IssueStatus.OPEN, "reported_by": "Clinical Supply Coordinator", "reported_date": now - timedelta(days=8), "assigned_to": "Supply Chain Manager", "resolution": None, "resolved_date": None},
        ]

        for iss in issues_data:
            self._issues[iss["id"]] = RiskIssue(**iss)

    # ------------------------------------------------------------------
    # Risk Management
    # ------------------------------------------------------------------

    def list_risks(
        self,
        *,
        trial_id: str | None = None,
        category: RiskCategory | None = None,
        risk_level: RiskLevel | None = None,
        status: RiskStatus | None = None,
    ) -> list[TrialRisk]:
        """List trial risks with optional filters."""
        with self._lock:
            result = list(self._risks.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if category is not None:
            result = [r for r in result if r.category == category]
        if risk_level is not None:
            result = [r for r in result if r.risk_level == risk_level]
        if status is not None:
            result = [r for r in result if r.status == status]

        return sorted(result, key=lambda r: r.identified_date, reverse=True)

    def get_risk(self, risk_id: str) -> TrialRisk | None:
        """Get a single risk by ID."""
        with self._lock:
            return self._risks.get(risk_id)

    def create_risk(self, payload: TrialRiskCreate) -> TrialRisk:
        """Create a new trial risk."""
        now = datetime.now(timezone.utc)
        risk_id = f"RSK-{uuid4().hex[:8].upper()}"
        computed_level = compute_risk_level(payload.probability, payload.impact)
        risk = TrialRisk(
            id=risk_id,
            trial_id=payload.trial_id,
            risk_title=payload.risk_title,
            category=payload.category,
            description=payload.description,
            probability=payload.probability,
            impact=payload.impact,
            risk_level=computed_level,
            status=RiskStatus.IDENTIFIED,
            identified_by=payload.identified_by,
            identified_date=now,
            owner=payload.owner,
            affected_areas=payload.affected_areas,
            triggers=payload.triggers,
            residual_risk_level=None,
            last_reviewed=None,
            closed_date=None,
            created_at=now,
        )
        with self._lock:
            self._risks[risk_id] = risk
        logger.info("Created risk %s: %s", risk_id, payload.risk_title)
        return risk

    def update_risk(
        self, risk_id: str, payload: TrialRiskUpdate
    ) -> TrialRisk | None:
        """Update an existing risk."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._risks.get(risk_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Recompute risk level if probability or impact changed
            new_prob = updates.get("probability", existing.probability)
            new_impact = updates.get("impact", existing.impact)
            if "probability" in updates or "impact" in updates:
                updates["risk_level"] = compute_risk_level(new_prob, new_impact)

            # Auto-set closed_date when status changes to closed
            if "status" in updates and updates["status"] == RiskStatus.CLOSED:
                if existing.status != RiskStatus.CLOSED:
                    data["closed_date"] = now

            data.update(updates)
            updated = TrialRisk(**data)
            self._risks[risk_id] = updated
        return updated

    def delete_risk(self, risk_id: str) -> bool:
        """Delete a risk. Returns True if deleted."""
        with self._lock:
            if risk_id in self._risks:
                del self._risks[risk_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Mitigation Management
    # ------------------------------------------------------------------

    def list_mitigations(
        self,
        *,
        risk_id: str | None = None,
        status: MitigationStatus | None = None,
    ) -> list[RiskMitigation]:
        """List mitigations with optional filters."""
        with self._lock:
            result = list(self._mitigations.values())

        if risk_id is not None:
            result = [m for m in result if m.risk_id == risk_id]
        if status is not None:
            result = [m for m in result if m.status == status]

        return sorted(result, key=lambda m: m.due_date)

    def get_mitigation(self, mitigation_id: str) -> RiskMitigation | None:
        """Get a single mitigation by ID."""
        with self._lock:
            return self._mitigations.get(mitigation_id)

    def create_mitigation(self, payload: RiskMitigationCreate) -> RiskMitigation | None:
        """Create a new mitigation. Returns None if risk_id not found."""
        with self._lock:
            if payload.risk_id not in self._risks:
                return None

        mitigation_id = f"MIT-{uuid4().hex[:8].upper()}"
        mitigation = RiskMitigation(
            id=mitigation_id,
            risk_id=payload.risk_id,
            action=payload.action,
            responsible_party=payload.responsible_party,
            due_date=payload.due_date,
            status=MitigationStatus.PLANNED,
            completion_date=None,
            effectiveness_notes=None,
            cost_estimate=payload.cost_estimate,
        )
        with self._lock:
            self._mitigations[mitigation_id] = mitigation
        logger.info("Created mitigation %s for risk %s", mitigation_id, payload.risk_id)
        return mitigation

    def update_mitigation(
        self, mitigation_id: str, payload: RiskMitigationUpdate
    ) -> RiskMitigation | None:
        """Update an existing mitigation."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._mitigations.get(mitigation_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set completion_date when status changes to implemented or effective
            if "status" in updates and updates["status"] in (
                MitigationStatus.IMPLEMENTED,
                MitigationStatus.EFFECTIVE,
            ):
                if existing.completion_date is None:
                    data["completion_date"] = now

            data.update(updates)
            updated = RiskMitigation(**data)
            self._mitigations[mitigation_id] = updated
        return updated

    def delete_mitigation(self, mitigation_id: str) -> bool:
        """Delete a mitigation. Returns True if deleted."""
        with self._lock:
            if mitigation_id in self._mitigations:
                del self._mitigations[mitigation_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Review Management
    # ------------------------------------------------------------------

    def list_reviews(
        self,
        *,
        risk_id: str | None = None,
    ) -> list[RiskReview]:
        """List risk reviews with optional filter."""
        with self._lock:
            result = list(self._reviews.values())

        if risk_id is not None:
            result = [r for r in result if r.risk_id == risk_id]

        return sorted(result, key=lambda r: r.review_date, reverse=True)

    def get_review(self, review_id: str) -> RiskReview | None:
        """Get a single review by ID."""
        with self._lock:
            return self._reviews.get(review_id)

    def create_review(self, payload: RiskReviewCreate) -> RiskReview | None:
        """Create a risk review. Returns None if risk_id not found.

        Also updates the associated risk's last_reviewed date.
        """
        now = datetime.now(timezone.utc)
        with self._lock:
            risk = self._risks.get(payload.risk_id)
            if risk is None:
                return None

        review_id = f"RVW-{uuid4().hex[:8].upper()}"
        review = RiskReview(
            id=review_id,
            risk_id=payload.risk_id,
            review_date=now,
            reviewer=payload.reviewer,
            current_probability=payload.current_probability,
            current_impact=payload.current_impact,
            current_risk_level=payload.current_risk_level,
            notes=payload.notes,
            action_items=payload.action_items,
            next_review_date=payload.next_review_date,
        )

        with self._lock:
            self._reviews[review_id] = review
            # Update risk's last_reviewed date
            existing_risk = self._risks.get(payload.risk_id)
            if existing_risk is not None:
                risk_data = existing_risk.model_dump()
                risk_data["last_reviewed"] = now
                self._risks[payload.risk_id] = TrialRisk(**risk_data)

        logger.info("Created review %s for risk %s", review_id, payload.risk_id)
        return review

    # ------------------------------------------------------------------
    # Issue Management
    # ------------------------------------------------------------------

    def list_issues(
        self,
        *,
        trial_id: str | None = None,
        risk_id: str | None = None,
        status: IssueStatus | None = None,
        severity: RiskLevel | None = None,
        category: RiskCategory | None = None,
    ) -> list[RiskIssue]:
        """List risk issues with optional filters."""
        with self._lock:
            result = list(self._issues.values())

        if trial_id is not None:
            result = [i for i in result if i.trial_id == trial_id]
        if risk_id is not None:
            result = [i for i in result if i.risk_id == risk_id]
        if status is not None:
            result = [i for i in result if i.status == status]
        if severity is not None:
            result = [i for i in result if i.severity == severity]
        if category is not None:
            result = [i for i in result if i.category == category]

        return sorted(result, key=lambda i: i.reported_date, reverse=True)

    def get_issue(self, issue_id: str) -> RiskIssue | None:
        """Get a single issue by ID."""
        with self._lock:
            return self._issues.get(issue_id)

    def create_issue(self, payload: RiskIssueCreate) -> RiskIssue:
        """Create a new risk issue."""
        now = datetime.now(timezone.utc)
        issue_id = f"ISS-{uuid4().hex[:8].upper()}"
        issue = RiskIssue(
            id=issue_id,
            trial_id=payload.trial_id,
            risk_id=payload.risk_id,
            title=payload.title,
            description=payload.description,
            category=payload.category,
            severity=payload.severity,
            status=IssueStatus.OPEN,
            reported_by=payload.reported_by,
            reported_date=now,
            assigned_to=payload.assigned_to,
            resolution=None,
            resolved_date=None,
        )
        with self._lock:
            self._issues[issue_id] = issue
        logger.info("Created issue %s: %s", issue_id, payload.title)
        return issue

    def update_issue(
        self, issue_id: str, payload: RiskIssueUpdate
    ) -> RiskIssue | None:
        """Update an existing issue."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._issues.get(issue_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set resolved_date when status changes to resolved or closed
            if "status" in updates and updates["status"] in (
                IssueStatus.RESOLVED,
                IssueStatus.CLOSED,
            ):
                if existing.resolved_date is None:
                    data["resolved_date"] = now

            data.update(updates)
            updated = RiskIssue(**data)
            self._issues[issue_id] = updated
        return updated

    def delete_issue(self, issue_id: str) -> bool:
        """Delete an issue. Returns True if deleted."""
        with self._lock:
            if issue_id in self._issues:
                del self._issues[issue_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> RiskManagementMetrics:
        """Compute aggregated risk management metrics."""
        now = datetime.now(timezone.utc)
        with self._lock:
            risks = list(self._risks.values())
            mitigations = list(self._mitigations.values())
            reviews = list(self._reviews.values())
            issues = list(self._issues.values())

        if trial_id is not None:
            risks = [r for r in risks if r.trial_id == trial_id]
            # Filter mitigations to those linked to filtered risks
            risk_ids = {r.id for r in risks}
            mitigations = [m for m in mitigations if m.risk_id in risk_ids]
            reviews = [rv for rv in reviews if rv.risk_id in risk_ids]
            issues = [i for i in issues if i.trial_id == trial_id]

        # Risks by category
        risks_by_category: dict[str, int] = {}
        for r in risks:
            key = r.category.value
            risks_by_category[key] = risks_by_category.get(key, 0) + 1

        # Risks by level
        risks_by_level: dict[str, int] = {}
        for r in risks:
            key = r.risk_level.value
            risks_by_level[key] = risks_by_level.get(key, 0) + 1

        # Risks by status
        risks_by_status: dict[str, int] = {}
        for r in risks:
            key = r.status.value
            risks_by_status[key] = risks_by_status.get(key, 0) + 1

        # Open risks (not closed)
        open_risks = sum(1 for r in risks if r.status != RiskStatus.CLOSED)

        # Critical risks
        critical_risks = sum(1 for r in risks if r.risk_level == RiskLevel.CRITICAL)

        # Mitigations by status
        mitigations_by_status: dict[str, int] = {}
        for m in mitigations:
            key = m.status.value
            mitigations_by_status[key] = mitigations_by_status.get(key, 0) + 1

        # Overdue mitigations (due_date < now and status not implemented/effective)
        overdue_mitigations = sum(
            1 for m in mitigations
            if m.due_date < now
            and m.status not in (MitigationStatus.IMPLEMENTED, MitigationStatus.EFFECTIVE)
        )

        # Open issues
        open_issues = sum(
            1 for i in issues
            if i.status not in (IssueStatus.RESOLVED, IssueStatus.CLOSED)
        )

        # Issues by severity
        issues_by_severity: dict[str, int] = {}
        for i in issues:
            key = i.severity.value
            issues_by_severity[key] = issues_by_severity.get(key, 0) + 1

        return RiskManagementMetrics(
            total_risks=len(risks),
            risks_by_category=risks_by_category,
            risks_by_level=risks_by_level,
            risks_by_status=risks_by_status,
            open_risks=open_risks,
            critical_risks=critical_risks,
            total_mitigations=len(mitigations),
            mitigations_by_status=mitigations_by_status,
            overdue_mitigations=overdue_mitigations,
            total_reviews=len(reviews),
            total_issues=len(issues),
            open_issues=open_issues,
            issues_by_severity=issues_by_severity,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: RiskManagementService | None = None
_instance_lock = threading.Lock()


def get_risk_management_service() -> RiskManagementService:
    """Return the singleton RiskManagementService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = RiskManagementService()
    return _instance


def reset_risk_management_service() -> RiskManagementService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = RiskManagementService()
    return _instance
