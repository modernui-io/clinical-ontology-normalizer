"""Clinical Hold Management (CHM-MGT) Service.

Manages clinical hold operations: hold events, impact assessments, corrective
action plans, restart authorizations, and clinical hold metrics.

Usage:
    from app.services.clinical_hold_management_service import (
        get_clinical_hold_management_service,
    )

    svc = get_clinical_hold_management_service()
    holds = svc.list_hold_events()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.clinical_hold_management import (
    ActionPlanStatus,
    ClinicalHoldMetrics,
    CorrectiveActionPlan,
    CorrectiveActionPlanCreate,
    CorrectiveActionPlanUpdate,
    HoldEvent,
    HoldEventCreate,
    HoldEventUpdate,
    HoldStatus,
    HoldType,
    ImpactAssessment,
    ImpactAssessmentCreate,
    ImpactAssessmentUpdate,
    ImpactSeverity,
    RestartAuthorization,
    RestartAuthorizationCreate,
    RestartAuthorizationUpdate,
    RestartDecision,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class ClinicalHoldManagementService:
    """In-memory Clinical Hold Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._hold_events: dict[str, HoldEvent] = {}
        self._impact_assessments: dict[str, ImpactAssessment] = {}
        self._corrective_action_plans: dict[str, CorrectiveActionPlan] = {}
        self._restart_authorizations: dict[str, RestartAuthorization] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic clinical hold data across three trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Hold Events (4 per trial) ---
        hold_events_data = [
            # EYLEA trial
            {
                "id": "HLD-00000001",
                "trial_id": EYLEA_TRIAL,
                "hold_type": HoldType.FULL_CLINICAL_HOLD,
                "hold_status": HoldStatus.LIFTED,
                "hold_reason": "Unexpected serious adverse events in treatment arm - retinal detachment cluster",
                "issuing_authority": "FDA CDER",
                "hold_date": now - timedelta(days=180),
                "notification_date": now - timedelta(days=179),
                "affected_sites_count": 24,
                "affected_subjects_count": 312,
                "protocol_sections_affected": "Sections 5.1, 6.2, 8.3 - Dosing, Safety Monitoring, Stopping Rules",
                "regulatory_reference": "FDA-2025-CL-0042",
                "lift_date": now - timedelta(days=120),
                "lifted_by": "Dr. Sarah Chen, FDA Division Director",
                "notes": "Hold lifted after DSMB review and protocol amendment",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "HLD-00000002",
                "trial_id": EYLEA_TRIAL,
                "hold_type": HoldType.PARTIAL_CLINICAL_HOLD,
                "hold_status": HoldStatus.ACTIVE,
                "hold_reason": "Dose-limiting toxicity observed in high-dose cohort",
                "issuing_authority": "FDA CDER",
                "hold_date": now - timedelta(days=30),
                "notification_date": now - timedelta(days=29),
                "affected_sites_count": 8,
                "affected_subjects_count": 45,
                "protocol_sections_affected": "Section 4.2 - High-dose arm only",
                "regulatory_reference": "FDA-2026-CL-0018",
                "lift_date": None,
                "lifted_by": None,
                "notes": "High-dose arm suspended; low-dose and mid-dose continue",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "HLD-00000003",
                "trial_id": EYLEA_TRIAL,
                "hold_type": HoldType.VOLUNTARY_PAUSE,
                "hold_status": HoldStatus.LIFTED,
                "hold_reason": "Manufacturing quality signal in drug product batch FP-2025-087",
                "issuing_authority": "Regeneron Internal QA",
                "hold_date": now - timedelta(days=90),
                "notification_date": now - timedelta(days=90),
                "affected_sites_count": 24,
                "affected_subjects_count": 0,
                "protocol_sections_affected": "Section 7.1 - Investigational Product Management",
                "regulatory_reference": None,
                "lift_date": now - timedelta(days=75),
                "lifted_by": "VP Quality Assurance",
                "notes": "Batch quarantined and replaced; no patient exposure confirmed",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "HLD-00000004",
                "trial_id": EYLEA_TRIAL,
                "hold_type": HoldType.SAFETY_PAUSE,
                "hold_status": HoldStatus.UNDER_REVIEW,
                "hold_reason": "Potential drug-drug interaction signal with concomitant anti-VEGF therapy",
                "issuing_authority": "Regeneron Pharmacovigilance",
                "hold_date": now - timedelta(days=10),
                "notification_date": now - timedelta(days=10),
                "affected_sites_count": 5,
                "affected_subjects_count": 18,
                "protocol_sections_affected": "Section 5.3 - Concomitant Medications",
                "regulatory_reference": None,
                "lift_date": None,
                "lifted_by": None,
                "notes": "Signal under evaluation by safety committee",
                "created_at": now - timedelta(days=10),
            },
            # DUPIXENT trial
            {
                "id": "HLD-00000005",
                "trial_id": DUPIXENT_TRIAL,
                "hold_type": HoldType.REGULATORY_SUSPENSION,
                "hold_status": HoldStatus.LIFTED,
                "hold_reason": "GCP inspection findings at three European sites",
                "issuing_authority": "EMA",
                "hold_date": now - timedelta(days=150),
                "notification_date": now - timedelta(days=148),
                "affected_sites_count": 3,
                "affected_subjects_count": 67,
                "protocol_sections_affected": "Sections 9.1, 9.2 - Data Management, Source Data Verification",
                "regulatory_reference": "EMA/INS/2025/0891",
                "lift_date": now - timedelta(days=90),
                "lifted_by": "EMA GCP Inspectors",
                "notes": "CAPA implemented and verified; inspection closed satisfactorily",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "HLD-00000006",
                "trial_id": DUPIXENT_TRIAL,
                "hold_type": HoldType.FULL_CLINICAL_HOLD,
                "hold_status": HoldStatus.ACTIVE,
                "hold_reason": "Anaphylaxis events exceeding protocol-defined threshold",
                "issuing_authority": "FDA CDER",
                "hold_date": now - timedelta(days=21),
                "notification_date": now - timedelta(days=20),
                "affected_sites_count": 18,
                "affected_subjects_count": 234,
                "protocol_sections_affected": "Sections 5.1, 6.1, 8.1 - Safety, Dosing, Emergency Procedures",
                "regulatory_reference": "FDA-2026-CL-0023",
                "lift_date": None,
                "lifted_by": None,
                "notes": "All dosing suspended pending DSMB emergency review",
                "created_at": now - timedelta(days=21),
            },
            {
                "id": "HLD-00000007",
                "trial_id": DUPIXENT_TRIAL,
                "hold_type": HoldType.ADMINISTRATIVE_HOLD,
                "hold_status": HoldStatus.LIFTED,
                "hold_reason": "IND annual report submission delayed beyond 60-day deadline",
                "issuing_authority": "FDA CDER",
                "hold_date": now - timedelta(days=200),
                "notification_date": now - timedelta(days=199),
                "affected_sites_count": 0,
                "affected_subjects_count": 0,
                "protocol_sections_affected": None,
                "regulatory_reference": "FDA-2025-CL-0031",
                "lift_date": now - timedelta(days=185),
                "lifted_by": "FDA Regulatory Project Manager",
                "notes": "Annual report submitted and accepted",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "HLD-00000008",
                "trial_id": DUPIXENT_TRIAL,
                "hold_type": HoldType.SAFETY_PAUSE,
                "hold_status": HoldStatus.ESCALATED,
                "hold_reason": "Hepatotoxicity signal detected in post-hoc analysis",
                "issuing_authority": "Regeneron Safety Committee",
                "hold_date": now - timedelta(days=7),
                "notification_date": now - timedelta(days=7),
                "affected_sites_count": 18,
                "affected_subjects_count": 234,
                "protocol_sections_affected": "Section 5.2 - Hepatic Monitoring",
                "regulatory_reference": None,
                "lift_date": None,
                "lifted_by": None,
                "notes": "Escalated to FDA for review; enhanced liver monitoring initiated",
                "created_at": now - timedelta(days=7),
            },
            # LIBTAYO trial
            {
                "id": "HLD-00000009",
                "trial_id": LIBTAYO_TRIAL,
                "hold_type": HoldType.PARTIAL_CLINICAL_HOLD,
                "hold_status": HoldStatus.LIFTED,
                "hold_reason": "Immune-related adverse events above expected rate in combination arm",
                "issuing_authority": "FDA CDER",
                "hold_date": now - timedelta(days=120),
                "notification_date": now - timedelta(days=119),
                "affected_sites_count": 12,
                "affected_subjects_count": 89,
                "protocol_sections_affected": "Section 4.3 - Combination Therapy Arm",
                "regulatory_reference": "FDA-2025-CL-0056",
                "lift_date": now - timedelta(days=60),
                "lifted_by": "Dr. James Wilson, FDA CDER",
                "notes": "Protocol amended with enhanced immune monitoring; combination arm resumed",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "HLD-00000010",
                "trial_id": LIBTAYO_TRIAL,
                "hold_type": HoldType.FULL_CLINICAL_HOLD,
                "hold_status": HoldStatus.ACTIVE,
                "hold_reason": "Fatal treatment-related adverse event under investigation",
                "issuing_authority": "FDA CDER",
                "hold_date": now - timedelta(days=14),
                "notification_date": now - timedelta(days=13),
                "affected_sites_count": 15,
                "affected_subjects_count": 156,
                "protocol_sections_affected": "All treatment sections",
                "regulatory_reference": "FDA-2026-CL-0029",
                "lift_date": None,
                "lifted_by": None,
                "notes": "Root cause analysis in progress; autopsy results pending",
                "created_at": now - timedelta(days=14),
            },
            {
                "id": "HLD-00000011",
                "trial_id": LIBTAYO_TRIAL,
                "hold_type": HoldType.VOLUNTARY_PAUSE,
                "hold_status": HoldStatus.MODIFIED,
                "hold_reason": "Biomarker data suggests need for patient stratification revision",
                "issuing_authority": "Regeneron Clinical Development",
                "hold_date": now - timedelta(days=45),
                "notification_date": now - timedelta(days=45),
                "affected_sites_count": 15,
                "affected_subjects_count": 0,
                "protocol_sections_affected": "Section 3.1 - Eligibility Criteria, Section 4.1 - Stratification",
                "regulatory_reference": None,
                "lift_date": None,
                "lifted_by": None,
                "notes": "Enrollment paused while protocol amendment finalized; existing patients continue",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "HLD-00000012",
                "trial_id": LIBTAYO_TRIAL,
                "hold_type": HoldType.REGULATORY_SUSPENSION,
                "hold_status": HoldStatus.EXPIRED,
                "hold_reason": "PMDA requested additional preclinical data for Japanese sites",
                "issuing_authority": "PMDA",
                "hold_date": now - timedelta(days=240),
                "notification_date": now - timedelta(days=238),
                "affected_sites_count": 4,
                "affected_subjects_count": 28,
                "protocol_sections_affected": "Japan-specific addendum",
                "regulatory_reference": "PMDA-2025-CT-0012",
                "lift_date": now - timedelta(days=180),
                "lifted_by": "PMDA Review Division",
                "notes": "Additional preclinical data accepted; Japanese sites reactivated",
                "created_at": now - timedelta(days=240),
            },
        ]

        for h in hold_events_data:
            self._hold_events[h["id"]] = HoldEvent(**h)

        # --- 12 Impact Assessments (4 per trial) ---
        impact_data = [
            # EYLEA
            {
                "id": "IMA-00000001",
                "trial_id": EYLEA_TRIAL,
                "hold_event_id": "HLD-00000001",
                "impact_severity": ImpactSeverity.CRITICAL,
                "assessment_area": "Patient Safety",
                "impact_description": "312 subjects required safety follow-up visits; 3 subjects hospitalized",
                "affected_endpoints": "Primary efficacy endpoint, key secondary safety endpoints",
                "enrollment_impact": "Enrollment suspended for 60 days across all sites",
                "timeline_impact_days": 90,
                "financial_impact_usd": 4500000.0,
                "assessed_by": "Dr. Maria Rodriguez, Chief Medical Officer",
                "assessment_date": now - timedelta(days=175),
                "mitigation_strategy": "Enhanced safety monitoring protocol; DSMB charter amended",
                "notes": "Comprehensive safety review completed",
                "created_at": now - timedelta(days=175),
            },
            {
                "id": "IMA-00000002",
                "trial_id": EYLEA_TRIAL,
                "hold_event_id": "HLD-00000002",
                "impact_severity": ImpactSeverity.HIGH,
                "assessment_area": "Enrollment & Timeline",
                "impact_description": "High-dose cohort enrollment halted; 45 subjects require dose modification",
                "affected_endpoints": "High-dose efficacy comparisons",
                "enrollment_impact": "High-dose arm enrollment suspended indefinitely",
                "timeline_impact_days": 60,
                "financial_impact_usd": 1200000.0,
                "assessed_by": "Dr. James Park, VP Clinical Operations",
                "assessment_date": now - timedelta(days=28),
                "mitigation_strategy": "Dose de-escalation protocol for affected subjects",
                "notes": None,
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "IMA-00000003",
                "trial_id": EYLEA_TRIAL,
                "hold_event_id": "HLD-00000003",
                "impact_severity": ImpactSeverity.MODERATE,
                "assessment_area": "Supply Chain",
                "impact_description": "Drug supply interrupted for 15 days; no patient dosing missed",
                "affected_endpoints": None,
                "enrollment_impact": "New enrollment paused for 2 weeks",
                "timeline_impact_days": 15,
                "financial_impact_usd": 350000.0,
                "assessed_by": "Lisa Thompson, Director Supply Chain",
                "assessment_date": now - timedelta(days=88),
                "mitigation_strategy": "Emergency batch production authorized; backup supplier engaged",
                "notes": "No impact on data integrity",
                "created_at": now - timedelta(days=88),
            },
            {
                "id": "IMA-00000004",
                "trial_id": EYLEA_TRIAL,
                "hold_event_id": "HLD-00000004",
                "impact_severity": ImpactSeverity.LOW,
                "assessment_area": "Concomitant Medication Protocol",
                "impact_description": "5 sites with patients on concomitant anti-VEGF require protocol clarification",
                "affected_endpoints": None,
                "enrollment_impact": "Minimal - affects small subset of patients",
                "timeline_impact_days": 14,
                "financial_impact_usd": 75000.0,
                "assessed_by": "Dr. Amanda Foster, Medical Monitor",
                "assessment_date": now - timedelta(days=8),
                "mitigation_strategy": "Protocol clarification letter to affected sites",
                "notes": "Under review by safety committee",
                "created_at": now - timedelta(days=8),
            },
            # DUPIXENT
            {
                "id": "IMA-00000005",
                "trial_id": DUPIXENT_TRIAL,
                "hold_event_id": "HLD-00000005",
                "impact_severity": ImpactSeverity.HIGH,
                "assessment_area": "Data Integrity",
                "impact_description": "GCP findings at 3 EU sites; data from 67 subjects requires audit",
                "affected_endpoints": "All endpoints from affected sites pending verification",
                "enrollment_impact": "Affected sites paused; other sites continued",
                "timeline_impact_days": 60,
                "financial_impact_usd": 2100000.0,
                "assessed_by": "Dr. Robert Kim, VP Quality",
                "assessment_date": now - timedelta(days=145),
                "mitigation_strategy": "100% SDV at affected sites; additional monitoring visits",
                "notes": "CAPA implementation verified by independent audit",
                "created_at": now - timedelta(days=145),
            },
            {
                "id": "IMA-00000006",
                "trial_id": DUPIXENT_TRIAL,
                "hold_event_id": "HLD-00000006",
                "impact_severity": ImpactSeverity.CRITICAL,
                "assessment_area": "Patient Safety",
                "impact_description": "4 anaphylaxis events across 3 sites; emergency protocols activated",
                "affected_endpoints": "Primary and all secondary endpoints",
                "enrollment_impact": "All enrollment and dosing suspended",
                "timeline_impact_days": 120,
                "financial_impact_usd": 8500000.0,
                "assessed_by": "Dr. Maria Rodriguez, Chief Medical Officer",
                "assessment_date": now - timedelta(days=19),
                "mitigation_strategy": "Root cause analysis; epinephrine auto-injector protocol addition",
                "notes": "DSMB emergency meeting convened",
                "created_at": now - timedelta(days=19),
            },
            {
                "id": "IMA-00000007",
                "trial_id": DUPIXENT_TRIAL,
                "hold_event_id": "HLD-00000007",
                "impact_severity": ImpactSeverity.MINIMAL,
                "assessment_area": "Regulatory Compliance",
                "impact_description": "Administrative delay; no impact on ongoing patient treatment",
                "affected_endpoints": None,
                "enrollment_impact": "No enrollment impact",
                "timeline_impact_days": 15,
                "financial_impact_usd": 25000.0,
                "assessed_by": "Karen White, Regulatory Affairs Director",
                "assessment_date": now - timedelta(days=198),
                "mitigation_strategy": "Expedited annual report preparation process implemented",
                "notes": "Process improvement implemented to prevent recurrence",
                "created_at": now - timedelta(days=198),
            },
            {
                "id": "IMA-00000008",
                "trial_id": DUPIXENT_TRIAL,
                "hold_event_id": "HLD-00000008",
                "impact_severity": ImpactSeverity.HIGH,
                "assessment_area": "Hepatic Safety",
                "impact_description": "Liver enzyme elevations above 5x ULN in 8 subjects",
                "affected_endpoints": "Safety endpoints; potential impact on benefit-risk assessment",
                "enrollment_impact": "All enrollment paused pending hepatic safety review",
                "timeline_impact_days": 90,
                "financial_impact_usd": 3200000.0,
                "assessed_by": "Dr. Patricia Nguyen, Hepatologist Consultant",
                "assessment_date": now - timedelta(days=5),
                "mitigation_strategy": "Enhanced hepatic monitoring; Hy's Law assessment initiated",
                "notes": "FDA notification submitted",
                "created_at": now - timedelta(days=5),
            },
            # LIBTAYO
            {
                "id": "IMA-00000009",
                "trial_id": LIBTAYO_TRIAL,
                "hold_event_id": "HLD-00000009",
                "impact_severity": ImpactSeverity.HIGH,
                "assessment_area": "Immune Safety",
                "impact_description": "Grade 3-4 immune-related AEs in 12% of combination arm vs 4% expected",
                "affected_endpoints": "Combination arm efficacy and safety endpoints",
                "enrollment_impact": "Combination arm suspended; monotherapy continued",
                "timeline_impact_days": 60,
                "financial_impact_usd": 2800000.0,
                "assessed_by": "Dr. Kevin Chang, Immunology Lead",
                "assessment_date": now - timedelta(days=115),
                "mitigation_strategy": "Immune monitoring intensification; steroid prophylaxis protocol",
                "notes": "Protocol amendment approved by all IRBs",
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "IMA-00000010",
                "trial_id": LIBTAYO_TRIAL,
                "hold_event_id": "HLD-00000010",
                "impact_severity": ImpactSeverity.CRITICAL,
                "assessment_area": "Patient Safety",
                "impact_description": "Fatal treatment-related pneumonitis; causal relationship under assessment",
                "affected_endpoints": "All efficacy and safety endpoints",
                "enrollment_impact": "Complete enrollment and dosing suspension",
                "timeline_impact_days": 180,
                "financial_impact_usd": 12000000.0,
                "assessed_by": "Dr. Maria Rodriguez, Chief Medical Officer",
                "assessment_date": now - timedelta(days=12),
                "mitigation_strategy": "Comprehensive safety review; independent adjudication committee",
                "notes": "Autopsy results expected in 4-6 weeks",
                "created_at": now - timedelta(days=12),
            },
            {
                "id": "IMA-00000011",
                "trial_id": LIBTAYO_TRIAL,
                "hold_event_id": "HLD-00000011",
                "impact_severity": ImpactSeverity.MODERATE,
                "assessment_area": "Protocol Design",
                "impact_description": "Biomarker data indicates suboptimal patient stratification",
                "affected_endpoints": "Primary endpoint statistical power may be affected",
                "enrollment_impact": "New enrollment paused; existing patients continue treatment",
                "timeline_impact_days": 45,
                "financial_impact_usd": 900000.0,
                "assessed_by": "Dr. Steven Lee, Biostatistics Head",
                "assessment_date": now - timedelta(days=42),
                "mitigation_strategy": "Protocol amendment with revised stratification criteria",
                "notes": "Statistical analysis plan update in progress",
                "created_at": now - timedelta(days=42),
            },
            {
                "id": "IMA-00000012",
                "trial_id": LIBTAYO_TRIAL,
                "hold_event_id": "HLD-00000012",
                "impact_severity": ImpactSeverity.MODERATE,
                "assessment_area": "Regional Regulatory",
                "impact_description": "Japanese sites suspended; 28 subjects transitioned to follow-up only",
                "affected_endpoints": "Japan subgroup analysis impacted",
                "enrollment_impact": "Japan enrollment paused for 60 days",
                "timeline_impact_days": 60,
                "financial_impact_usd": 1500000.0,
                "assessed_by": "Yuki Tanaka, Japan Regulatory Lead",
                "assessment_date": now - timedelta(days=235),
                "mitigation_strategy": "Accelerated preclinical data package submission to PMDA",
                "notes": "All data accepted; sites reactivated",
                "created_at": now - timedelta(days=235),
            },
        ]

        for ia in impact_data:
            self._impact_assessments[ia["id"]] = ImpactAssessment(**ia)

        # --- 12 Corrective Action Plans (4 per trial) ---
        cap_data = [
            # EYLEA
            {
                "id": "CAP-00000001",
                "trial_id": EYLEA_TRIAL,
                "hold_event_id": "HLD-00000001",
                "action_plan_status": ActionPlanStatus.COMPLETED,
                "plan_title": "Retinal Safety Enhancement CAPA",
                "plan_description": "Comprehensive corrective and preventive actions for retinal detachment cluster",
                "corrective_actions": "1. Enhanced retinal screening at baseline and monthly; 2. Protocol amendment for stopping rules; 3. Independent safety monitoring board established",
                "preventive_actions": "Site-level retinal safety training; updated IC forms with enhanced risk disclosure",
                "responsible_party": "Dr. Maria Rodriguez, CMO",
                "submission_date": now - timedelta(days=165),
                "approval_date": now - timedelta(days=150),
                "approved_by": "FDA CDER Review Division",
                "target_completion_date": now - timedelta(days=120),
                "actual_completion_date": now - timedelta(days=122),
                "regulatory_submission_id": "FDA-SUB-2025-0891",
                "notes": "All corrective actions verified; hold lifted",
                "created_at": now - timedelta(days=170),
            },
            {
                "id": "CAP-00000002",
                "trial_id": EYLEA_TRIAL,
                "hold_event_id": "HLD-00000002",
                "action_plan_status": ActionPlanStatus.IN_PROGRESS,
                "plan_title": "High-Dose DLT Remediation Plan",
                "plan_description": "Address dose-limiting toxicity in high-dose cohort",
                "corrective_actions": "1. Dose de-escalation for all high-dose subjects; 2. PK/PD modeling for dose optimization; 3. Enhanced toxicity monitoring",
                "preventive_actions": "Revised dose escalation criteria for future cohorts",
                "responsible_party": "Dr. James Park, VP Clinical Operations",
                "submission_date": now - timedelta(days=25),
                "approval_date": None,
                "approved_by": None,
                "target_completion_date": now + timedelta(days=30),
                "actual_completion_date": None,
                "regulatory_submission_id": None,
                "notes": "PK/PD modeling 60% complete",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "CAP-00000003",
                "trial_id": EYLEA_TRIAL,
                "hold_event_id": "HLD-00000003",
                "action_plan_status": ActionPlanStatus.COMPLETED,
                "plan_title": "Drug Product Quality CAPA",
                "plan_description": "Corrective actions for manufacturing quality signal",
                "corrective_actions": "1. Batch quarantine and destruction; 2. Root cause analysis of manufacturing deviation; 3. Process validation of replacement batch",
                "preventive_actions": "Enhanced release testing; dual-supplier qualification",
                "responsible_party": "Lisa Thompson, Director Supply Chain",
                "submission_date": now - timedelta(days=85),
                "approval_date": now - timedelta(days=80),
                "approved_by": "VP Quality Assurance",
                "target_completion_date": now - timedelta(days=75),
                "actual_completion_date": now - timedelta(days=76),
                "regulatory_submission_id": None,
                "notes": "Manufacturing CAPA closed; replacement supply validated",
                "created_at": now - timedelta(days=88),
            },
            {
                "id": "CAP-00000004",
                "trial_id": EYLEA_TRIAL,
                "hold_event_id": "HLD-00000004",
                "action_plan_status": ActionPlanStatus.DRAFT,
                "plan_title": "Anti-VEGF Interaction Assessment Plan",
                "plan_description": "Evaluate and mitigate potential drug-drug interaction signal",
                "corrective_actions": "1. Retrospective analysis of concomitant anti-VEGF use; 2. PK interaction study design; 3. Protocol clarification for investigators",
                "preventive_actions": None,
                "responsible_party": "Dr. Amanda Foster, Medical Monitor",
                "submission_date": None,
                "approval_date": None,
                "approved_by": None,
                "target_completion_date": now + timedelta(days=45),
                "actual_completion_date": None,
                "regulatory_submission_id": None,
                "notes": "Draft plan under internal review",
                "created_at": now - timedelta(days=8),
            },
            # DUPIXENT
            {
                "id": "CAP-00000005",
                "trial_id": DUPIXENT_TRIAL,
                "hold_event_id": "HLD-00000005",
                "action_plan_status": ActionPlanStatus.COMPLETED,
                "plan_title": "GCP Compliance Remediation - EU Sites",
                "plan_description": "Address GCP inspection findings at three European sites",
                "corrective_actions": "1. 100% SDV at affected sites; 2. Site staff retraining; 3. Process standardization for source data documentation",
                "preventive_actions": "Quarterly GCP compliance audits; centralized monitoring enhancement",
                "responsible_party": "Dr. Robert Kim, VP Quality",
                "submission_date": now - timedelta(days=140),
                "approval_date": now - timedelta(days=130),
                "approved_by": "EMA GCP Inspectors",
                "target_completion_date": now - timedelta(days=95),
                "actual_completion_date": now - timedelta(days=92),
                "regulatory_submission_id": "EMA-CAPA-2025-0891",
                "notes": "All corrective actions verified; inspection closed",
                "created_at": now - timedelta(days=145),
            },
            {
                "id": "CAP-00000006",
                "trial_id": DUPIXENT_TRIAL,
                "hold_event_id": "HLD-00000006",
                "action_plan_status": ActionPlanStatus.SUBMITTED,
                "plan_title": "Anaphylaxis Safety CAPA",
                "plan_description": "Comprehensive plan to address anaphylaxis events and prevent recurrence",
                "corrective_actions": "1. Root cause analysis of all 4 events; 2. Allergen screening panel addition; 3. Mandatory epinephrine auto-injector at all sites; 4. 2-hour post-dose observation period",
                "preventive_actions": "Pre-treatment allergen screening; updated emergency response protocol",
                "responsible_party": "Dr. Maria Rodriguez, CMO",
                "submission_date": now - timedelta(days=14),
                "approval_date": None,
                "approved_by": None,
                "target_completion_date": now + timedelta(days=60),
                "actual_completion_date": None,
                "regulatory_submission_id": "FDA-SUB-2026-0023",
                "notes": "Submitted to FDA; awaiting review response",
                "created_at": now - timedelta(days=18),
            },
            {
                "id": "CAP-00000007",
                "trial_id": DUPIXENT_TRIAL,
                "hold_event_id": "HLD-00000007",
                "action_plan_status": ActionPlanStatus.COMPLETED,
                "plan_title": "IND Annual Report Process Improvement",
                "plan_description": "Prevent future delays in IND annual report submissions",
                "corrective_actions": "1. Late submission filed; 2. Process audit of regulatory submission workflow",
                "preventive_actions": "Automated submission deadline tracking; 90-day advance preparation start",
                "responsible_party": "Karen White, Regulatory Affairs Director",
                "submission_date": now - timedelta(days=195),
                "approval_date": now - timedelta(days=190),
                "approved_by": "VP Regulatory Affairs",
                "target_completion_date": now - timedelta(days=185),
                "actual_completion_date": now - timedelta(days=186),
                "regulatory_submission_id": None,
                "notes": "Process improvement implemented successfully",
                "created_at": now - timedelta(days=198),
            },
            {
                "id": "CAP-00000008",
                "trial_id": DUPIXENT_TRIAL,
                "hold_event_id": "HLD-00000008",
                "action_plan_status": ActionPlanStatus.UNDER_REVIEW,
                "plan_title": "Hepatotoxicity Signal Investigation Plan",
                "plan_description": "Investigation and mitigation plan for liver enzyme elevation signal",
                "corrective_actions": "1. Enhanced hepatic monitoring schedule; 2. Hy's Law assessment for all affected subjects; 3. Hepatology consultation for subjects with ALT > 5x ULN",
                "preventive_actions": "Baseline hepatic panel requirement; liver function exclusion criteria revision",
                "responsible_party": "Dr. Patricia Nguyen, Hepatologist Consultant",
                "submission_date": now - timedelta(days=3),
                "approval_date": None,
                "approved_by": None,
                "target_completion_date": now + timedelta(days=45),
                "actual_completion_date": None,
                "regulatory_submission_id": None,
                "notes": "Under medical review committee evaluation",
                "created_at": now - timedelta(days=5),
            },
            # LIBTAYO
            {
                "id": "CAP-00000009",
                "trial_id": LIBTAYO_TRIAL,
                "hold_event_id": "HLD-00000009",
                "action_plan_status": ActionPlanStatus.COMPLETED,
                "plan_title": "Immune-Related AE Mitigation CAPA",
                "plan_description": "Address elevated irAE rate in combination arm",
                "corrective_actions": "1. Steroid prophylaxis protocol for combination arm; 2. Enhanced immune monitoring schedule; 3. irAE management training for all sites",
                "preventive_actions": "Immune biomarker panel for patient selection; irAE early detection algorithm",
                "responsible_party": "Dr. Kevin Chang, Immunology Lead",
                "submission_date": now - timedelta(days=110),
                "approval_date": now - timedelta(days=100),
                "approved_by": "FDA CDER Review Division",
                "target_completion_date": now - timedelta(days=65),
                "actual_completion_date": now - timedelta(days=62),
                "regulatory_submission_id": "FDA-SUB-2025-0056",
                "notes": "CAPA completed; combination arm resumed with enhanced monitoring",
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "CAP-00000010",
                "trial_id": LIBTAYO_TRIAL,
                "hold_event_id": "HLD-00000010",
                "action_plan_status": ActionPlanStatus.DRAFT,
                "plan_title": "Fatal AE Investigation and Safety Plan",
                "plan_description": "Comprehensive investigation of fatal treatment-related pneumonitis",
                "corrective_actions": "1. Autopsy review and causality assessment; 2. Retrospective analysis of all pneumonitis events; 3. Independent adjudication of all respiratory AEs",
                "preventive_actions": None,
                "responsible_party": "Dr. Maria Rodriguez, CMO",
                "submission_date": None,
                "approval_date": None,
                "approved_by": None,
                "target_completion_date": now + timedelta(days=90),
                "actual_completion_date": None,
                "regulatory_submission_id": None,
                "notes": "Awaiting autopsy results before finalizing plan",
                "created_at": now - timedelta(days=12),
            },
            {
                "id": "CAP-00000011",
                "trial_id": LIBTAYO_TRIAL,
                "hold_event_id": "HLD-00000011",
                "action_plan_status": ActionPlanStatus.APPROVED,
                "plan_title": "Patient Stratification Protocol Amendment",
                "plan_description": "Revise patient stratification based on biomarker data",
                "corrective_actions": "1. Updated eligibility criteria with biomarker requirements; 2. Central lab biomarker assay validation; 3. Amended randomization scheme",
                "preventive_actions": "Adaptive enrichment design for future studies",
                "responsible_party": "Dr. Steven Lee, Biostatistics Head",
                "submission_date": now - timedelta(days=35),
                "approval_date": now - timedelta(days=20),
                "approved_by": "Clinical Development Committee",
                "target_completion_date": now + timedelta(days=15),
                "actual_completion_date": None,
                "regulatory_submission_id": None,
                "notes": "Protocol amendment submitted to IRBs; awaiting approvals",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "CAP-00000012",
                "trial_id": LIBTAYO_TRIAL,
                "hold_event_id": "HLD-00000012",
                "action_plan_status": ActionPlanStatus.COMPLETED,
                "plan_title": "PMDA Preclinical Data Package",
                "plan_description": "Compile and submit additional preclinical data to PMDA",
                "corrective_actions": "1. Preclinical toxicology data compilation; 2. Japanese-specific bridging study summary; 3. PMDA submission package preparation",
                "preventive_actions": "Early engagement with PMDA for future regulatory requirements",
                "responsible_party": "Yuki Tanaka, Japan Regulatory Lead",
                "submission_date": now - timedelta(days=230),
                "approval_date": now - timedelta(days=200),
                "approved_by": "PMDA Review Division",
                "target_completion_date": now - timedelta(days=185),
                "actual_completion_date": now - timedelta(days=182),
                "regulatory_submission_id": "PMDA-SUB-2025-0012",
                "notes": "Data accepted; Japanese sites reactivated",
                "created_at": now - timedelta(days=235),
            },
        ]

        for c in cap_data:
            self._corrective_action_plans[c["id"]] = CorrectiveActionPlan(**c)

        # --- 12 Restart Authorizations (4 per trial) ---
        restart_data = [
            # EYLEA
            {
                "id": "RSA-00000001",
                "trial_id": EYLEA_TRIAL,
                "hold_event_id": "HLD-00000001",
                "restart_decision": RestartDecision.APPROVED,
                "authorization_authority": "FDA CDER",
                "decision_date": now - timedelta(days=120),
                "conditions": "Enhanced retinal monitoring at weeks 4, 8, 12; DSMB review after next 50 subjects",
                "protocol_modifications_required": True,
                "consent_updates_required": True,
                "site_retraining_required": True,
                "monitoring_plan_changes": "Monthly safety data reviews; centralized retinal image assessment",
                "restart_date": now - timedelta(days=115),
                "sites_reactivated_count": 24,
                "authorized_by": "Dr. Sarah Chen, FDA Division Director",
                "notes": "Full restart authorized with enhanced safety conditions",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "RSA-00000002",
                "trial_id": EYLEA_TRIAL,
                "hold_event_id": "HLD-00000002",
                "restart_decision": RestartDecision.PENDING,
                "authorization_authority": "FDA CDER",
                "decision_date": None,
                "conditions": None,
                "protocol_modifications_required": True,
                "consent_updates_required": False,
                "site_retraining_required": False,
                "monitoring_plan_changes": None,
                "restart_date": None,
                "sites_reactivated_count": 0,
                "authorized_by": None,
                "notes": "Awaiting PK/PD modeling results and dose optimization proposal",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "RSA-00000003",
                "trial_id": EYLEA_TRIAL,
                "hold_event_id": "HLD-00000003",
                "restart_decision": RestartDecision.APPROVED,
                "authorization_authority": "Regeneron Internal QA",
                "decision_date": now - timedelta(days=75),
                "conditions": "Replacement batch validated; all affected sites receive new supply",
                "protocol_modifications_required": False,
                "consent_updates_required": False,
                "site_retraining_required": False,
                "monitoring_plan_changes": "Supply chain verification at next monitoring visit",
                "restart_date": now - timedelta(days=74),
                "sites_reactivated_count": 24,
                "authorized_by": "VP Quality Assurance",
                "notes": "Voluntary pause lifted; supply chain restored",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "RSA-00000004",
                "trial_id": EYLEA_TRIAL,
                "hold_event_id": "HLD-00000004",
                "restart_decision": RestartDecision.PENDING,
                "authorization_authority": "Regeneron Safety Committee",
                "decision_date": None,
                "conditions": None,
                "protocol_modifications_required": False,
                "consent_updates_required": False,
                "site_retraining_required": False,
                "monitoring_plan_changes": None,
                "restart_date": None,
                "sites_reactivated_count": 0,
                "authorized_by": None,
                "notes": "Pending safety committee review outcome",
                "created_at": now - timedelta(days=8),
            },
            # DUPIXENT
            {
                "id": "RSA-00000005",
                "trial_id": DUPIXENT_TRIAL,
                "hold_event_id": "HLD-00000005",
                "restart_decision": RestartDecision.CONDITIONAL_APPROVAL,
                "authorization_authority": "EMA",
                "decision_date": now - timedelta(days=90),
                "conditions": "Quarterly GCP audits at affected sites for 12 months; centralized monitoring",
                "protocol_modifications_required": False,
                "consent_updates_required": False,
                "site_retraining_required": True,
                "monitoring_plan_changes": "Enhanced SDV schedule; monthly data quality reports",
                "restart_date": now - timedelta(days=88),
                "sites_reactivated_count": 3,
                "authorized_by": "EMA GCP Inspectors",
                "notes": "Conditional restart with enhanced oversight",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "RSA-00000006",
                "trial_id": DUPIXENT_TRIAL,
                "hold_event_id": "HLD-00000006",
                "restart_decision": RestartDecision.PENDING,
                "authorization_authority": "FDA CDER",
                "decision_date": None,
                "conditions": None,
                "protocol_modifications_required": True,
                "consent_updates_required": True,
                "site_retraining_required": True,
                "monitoring_plan_changes": None,
                "restart_date": None,
                "sites_reactivated_count": 0,
                "authorized_by": None,
                "notes": "Awaiting FDA review of anaphylaxis CAPA submission",
                "created_at": now - timedelta(days=14),
            },
            {
                "id": "RSA-00000007",
                "trial_id": DUPIXENT_TRIAL,
                "hold_event_id": "HLD-00000007",
                "restart_decision": RestartDecision.APPROVED,
                "authorization_authority": "FDA CDER",
                "decision_date": now - timedelta(days=185),
                "conditions": None,
                "protocol_modifications_required": False,
                "consent_updates_required": False,
                "site_retraining_required": False,
                "monitoring_plan_changes": None,
                "restart_date": now - timedelta(days=185),
                "sites_reactivated_count": 0,
                "authorized_by": "FDA Regulatory Project Manager",
                "notes": "Administrative hold lifted; no operational changes needed",
                "created_at": now - timedelta(days=185),
            },
            {
                "id": "RSA-00000008",
                "trial_id": DUPIXENT_TRIAL,
                "hold_event_id": "HLD-00000008",
                "restart_decision": RestartDecision.DEFERRED,
                "authorization_authority": "Regeneron Safety Committee",
                "decision_date": now - timedelta(days=2),
                "conditions": "Decision deferred pending hepatology expert panel review",
                "protocol_modifications_required": True,
                "consent_updates_required": True,
                "site_retraining_required": False,
                "monitoring_plan_changes": "Weekly liver function test monitoring for all active subjects",
                "restart_date": None,
                "sites_reactivated_count": 0,
                "authorized_by": None,
                "notes": "Expert panel convening next week",
                "created_at": now - timedelta(days=5),
            },
            # LIBTAYO
            {
                "id": "RSA-00000009",
                "trial_id": LIBTAYO_TRIAL,
                "hold_event_id": "HLD-00000009",
                "restart_decision": RestartDecision.CONDITIONAL_APPROVAL,
                "authorization_authority": "FDA CDER",
                "decision_date": now - timedelta(days=60),
                "conditions": "Steroid prophylaxis mandatory; immune monitoring at each visit; irAE management training",
                "protocol_modifications_required": True,
                "consent_updates_required": True,
                "site_retraining_required": True,
                "monitoring_plan_changes": "Bi-weekly immune safety data review; centralized irAE adjudication",
                "restart_date": now - timedelta(days=58),
                "sites_reactivated_count": 12,
                "authorized_by": "Dr. James Wilson, FDA CDER",
                "notes": "Combination arm restarted with enhanced immune safety measures",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "RSA-00000010",
                "trial_id": LIBTAYO_TRIAL,
                "hold_event_id": "HLD-00000010",
                "restart_decision": RestartDecision.PENDING,
                "authorization_authority": "FDA CDER",
                "decision_date": None,
                "conditions": None,
                "protocol_modifications_required": True,
                "consent_updates_required": True,
                "site_retraining_required": True,
                "monitoring_plan_changes": None,
                "restart_date": None,
                "sites_reactivated_count": 0,
                "authorized_by": None,
                "notes": "Pending autopsy results and root cause determination",
                "created_at": now - timedelta(days=12),
            },
            {
                "id": "RSA-00000011",
                "trial_id": LIBTAYO_TRIAL,
                "hold_event_id": "HLD-00000011",
                "restart_decision": RestartDecision.CONDITIONAL_APPROVAL,
                "authorization_authority": "Clinical Development Committee",
                "decision_date": now - timedelta(days=20),
                "conditions": "Protocol amendment with revised stratification must be IRB-approved",
                "protocol_modifications_required": True,
                "consent_updates_required": True,
                "site_retraining_required": True,
                "monitoring_plan_changes": "Biomarker verification at screening; central lab confirmation",
                "restart_date": None,
                "sites_reactivated_count": 0,
                "authorized_by": "VP Clinical Development",
                "notes": "Awaiting IRB approvals for protocol amendment",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "RSA-00000012",
                "trial_id": LIBTAYO_TRIAL,
                "hold_event_id": "HLD-00000012",
                "restart_decision": RestartDecision.APPROVED,
                "authorization_authority": "PMDA",
                "decision_date": now - timedelta(days=180),
                "conditions": "Additional safety reporting to PMDA every 6 months",
                "protocol_modifications_required": False,
                "consent_updates_required": False,
                "site_retraining_required": False,
                "monitoring_plan_changes": "PMDA-specific safety reporting schedule added",
                "restart_date": now - timedelta(days=178),
                "sites_reactivated_count": 4,
                "authorized_by": "PMDA Review Division",
                "notes": "Japanese sites reactivated with additional PMDA reporting",
                "created_at": now - timedelta(days=180),
            },
        ]

        for r in restart_data:
            self._restart_authorizations[r["id"]] = RestartAuthorization(**r)

    # ------------------------------------------------------------------
    # Hold Events
    # ------------------------------------------------------------------

    def list_hold_events(self, *, trial_id: str | None = None) -> list[HoldEvent]:
        """List hold events with optional trial filter."""
        with self._lock:
            result = list(self._hold_events.values())

        if trial_id is not None:
            result = [h for h in result if h.trial_id == trial_id]

        return sorted(result, key=lambda h: h.hold_date, reverse=True)

    def get_hold_event(self, hold_event_id: str) -> HoldEvent | None:
        """Get a single hold event by ID."""
        with self._lock:
            return self._hold_events.get(hold_event_id)

    def create_hold_event(self, payload: HoldEventCreate) -> HoldEvent:
        """Create a new hold event."""
        now = datetime.now(timezone.utc)
        event_id = f"HLD-{uuid4().hex[:8].upper()}"
        event = HoldEvent(
            id=event_id,
            trial_id=payload.trial_id,
            hold_type=payload.hold_type,
            hold_status=payload.hold_status,
            hold_reason=payload.hold_reason,
            issuing_authority=payload.issuing_authority,
            hold_date=payload.hold_date,
            created_at=now,
        )
        with self._lock:
            self._hold_events[event_id] = event
        logger.info("Created hold event %s for trial %s", event_id, payload.trial_id)
        return event

    def update_hold_event(self, hold_event_id: str, payload: HoldEventUpdate) -> HoldEvent | None:
        """Update an existing hold event."""
        with self._lock:
            existing = self._hold_events.get(hold_event_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = HoldEvent(**data)
            self._hold_events[hold_event_id] = updated
        return updated

    def delete_hold_event(self, hold_event_id: str) -> bool:
        """Delete a hold event. Returns True if deleted, False if not found."""
        with self._lock:
            if hold_event_id in self._hold_events:
                del self._hold_events[hold_event_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Impact Assessments
    # ------------------------------------------------------------------

    def list_impact_assessments(self, *, trial_id: str | None = None) -> list[ImpactAssessment]:
        """List impact assessments with optional trial filter."""
        with self._lock:
            result = list(self._impact_assessments.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]

        return sorted(result, key=lambda a: a.assessment_date, reverse=True)

    def get_impact_assessment(self, assessment_id: str) -> ImpactAssessment | None:
        """Get a single impact assessment by ID."""
        with self._lock:
            return self._impact_assessments.get(assessment_id)

    def create_impact_assessment(self, payload: ImpactAssessmentCreate) -> ImpactAssessment:
        """Create a new impact assessment."""
        now = datetime.now(timezone.utc)
        assessment_id = f"IMA-{uuid4().hex[:8].upper()}"
        assessment = ImpactAssessment(
            id=assessment_id,
            trial_id=payload.trial_id,
            hold_event_id=payload.hold_event_id,
            impact_severity=payload.impact_severity,
            assessment_area=payload.assessment_area,
            impact_description=payload.impact_description,
            assessed_by=payload.assessed_by,
            assessment_date=payload.assessment_date,
            created_at=now,
        )
        with self._lock:
            self._impact_assessments[assessment_id] = assessment
        logger.info("Created impact assessment %s for hold %s", assessment_id, payload.hold_event_id)
        return assessment

    def update_impact_assessment(self, assessment_id: str, payload: ImpactAssessmentUpdate) -> ImpactAssessment | None:
        """Update an existing impact assessment."""
        with self._lock:
            existing = self._impact_assessments.get(assessment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ImpactAssessment(**data)
            self._impact_assessments[assessment_id] = updated
        return updated

    def delete_impact_assessment(self, assessment_id: str) -> bool:
        """Delete an impact assessment. Returns True if deleted."""
        with self._lock:
            if assessment_id in self._impact_assessments:
                del self._impact_assessments[assessment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Corrective Action Plans
    # ------------------------------------------------------------------

    def list_corrective_action_plans(self, *, trial_id: str | None = None) -> list[CorrectiveActionPlan]:
        """List corrective action plans with optional trial filter."""
        with self._lock:
            result = list(self._corrective_action_plans.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]

        return sorted(result, key=lambda c: c.created_at, reverse=True)

    def get_corrective_action_plan(self, plan_id: str) -> CorrectiveActionPlan | None:
        """Get a single corrective action plan by ID."""
        with self._lock:
            return self._corrective_action_plans.get(plan_id)

    def create_corrective_action_plan(self, payload: CorrectiveActionPlanCreate) -> CorrectiveActionPlan:
        """Create a new corrective action plan."""
        now = datetime.now(timezone.utc)
        plan_id = f"CAP-{uuid4().hex[:8].upper()}"
        plan = CorrectiveActionPlan(
            id=plan_id,
            trial_id=payload.trial_id,
            hold_event_id=payload.hold_event_id,
            action_plan_status=payload.action_plan_status,
            plan_title=payload.plan_title,
            plan_description=payload.plan_description,
            corrective_actions=payload.corrective_actions,
            responsible_party=payload.responsible_party,
            created_at=now,
        )
        with self._lock:
            self._corrective_action_plans[plan_id] = plan
        logger.info("Created corrective action plan %s for hold %s", plan_id, payload.hold_event_id)
        return plan

    def update_corrective_action_plan(self, plan_id: str, payload: CorrectiveActionPlanUpdate) -> CorrectiveActionPlan | None:
        """Update an existing corrective action plan."""
        with self._lock:
            existing = self._corrective_action_plans.get(plan_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CorrectiveActionPlan(**data)
            self._corrective_action_plans[plan_id] = updated
        return updated

    def delete_corrective_action_plan(self, plan_id: str) -> bool:
        """Delete a corrective action plan. Returns True if deleted."""
        with self._lock:
            if plan_id in self._corrective_action_plans:
                del self._corrective_action_plans[plan_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Restart Authorizations
    # ------------------------------------------------------------------

    def list_restart_authorizations(self, *, trial_id: str | None = None) -> list[RestartAuthorization]:
        """List restart authorizations with optional trial filter."""
        with self._lock:
            result = list(self._restart_authorizations.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]

        return sorted(result, key=lambda r: r.created_at, reverse=True)

    def get_restart_authorization(self, auth_id: str) -> RestartAuthorization | None:
        """Get a single restart authorization by ID."""
        with self._lock:
            return self._restart_authorizations.get(auth_id)

    def create_restart_authorization(self, payload: RestartAuthorizationCreate) -> RestartAuthorization:
        """Create a new restart authorization."""
        now = datetime.now(timezone.utc)
        auth_id = f"RSA-{uuid4().hex[:8].upper()}"
        auth = RestartAuthorization(
            id=auth_id,
            trial_id=payload.trial_id,
            hold_event_id=payload.hold_event_id,
            restart_decision=payload.restart_decision,
            authorization_authority=payload.authorization_authority,
            created_at=now,
        )
        with self._lock:
            self._restart_authorizations[auth_id] = auth
        logger.info("Created restart authorization %s for hold %s", auth_id, payload.hold_event_id)
        return auth

    def update_restart_authorization(self, auth_id: str, payload: RestartAuthorizationUpdate) -> RestartAuthorization | None:
        """Update an existing restart authorization."""
        with self._lock:
            existing = self._restart_authorizations.get(auth_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = RestartAuthorization(**data)
            self._restart_authorizations[auth_id] = updated
        return updated

    def delete_restart_authorization(self, auth_id: str) -> bool:
        """Delete a restart authorization. Returns True if deleted."""
        with self._lock:
            if auth_id in self._restart_authorizations:
                del self._restart_authorizations[auth_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> ClinicalHoldMetrics:
        """Compute aggregated clinical hold metrics, optionally filtered by trial."""
        with self._lock:
            holds = list(self._hold_events.values())
            assessments = list(self._impact_assessments.values())
            plans = list(self._corrective_action_plans.values())
            restarts = list(self._restart_authorizations.values())

        if trial_id is not None:
            holds = [h for h in holds if h.trial_id == trial_id]
            assessments = [a for a in assessments if a.trial_id == trial_id]
            plans = [p for p in plans if p.trial_id == trial_id]
            restarts = [r for r in restarts if r.trial_id == trial_id]

        # Holds by type
        holds_by_type: dict[str, int] = {}
        for h in holds:
            key = h.hold_type.value
            holds_by_type[key] = holds_by_type.get(key, 0) + 1

        # Holds by status
        holds_by_status: dict[str, int] = {}
        for h in holds:
            key = h.hold_status.value
            holds_by_status[key] = holds_by_status.get(key, 0) + 1

        # Assessments by severity
        assessments_by_severity: dict[str, int] = {}
        for a in assessments:
            key = a.impact_severity.value
            assessments_by_severity[key] = assessments_by_severity.get(key, 0) + 1

        # Plans by status
        plans_by_status: dict[str, int] = {}
        for p in plans:
            key = p.action_plan_status.value
            plans_by_status[key] = plans_by_status.get(key, 0) + 1

        # Restarts by decision
        restarts_by_decision: dict[str, int] = {}
        for r in restarts:
            key = r.restart_decision.value
            restarts_by_decision[key] = restarts_by_decision.get(key, 0) + 1

        # Average hold duration (for holds that have been lifted)
        durations: list[float] = []
        for h in holds:
            if h.lift_date is not None:
                duration = (h.lift_date - h.hold_date).total_seconds() / 86400.0
                durations.append(duration)

        avg_duration = round(sum(durations) / len(durations), 1) if durations else 0.0

        return ClinicalHoldMetrics(
            total_hold_events=len(holds),
            holds_by_type=holds_by_type,
            holds_by_status=holds_by_status,
            total_impact_assessments=len(assessments),
            assessments_by_severity=assessments_by_severity,
            total_action_plans=len(plans),
            plans_by_status=plans_by_status,
            total_restart_authorizations=len(restarts),
            restarts_by_decision=restarts_by_decision,
            avg_hold_duration_days=avg_duration,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ClinicalHoldManagementService | None = None
_instance_lock = threading.Lock()


def get_clinical_hold_management_service() -> ClinicalHoldManagementService:
    """Return the singleton ClinicalHoldManagementService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ClinicalHoldManagementService()
    return _instance


def reset_clinical_hold_management_service() -> ClinicalHoldManagementService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = ClinicalHoldManagementService()
    return _instance
