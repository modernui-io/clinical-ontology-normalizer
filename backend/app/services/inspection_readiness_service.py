"""Inspection Readiness Service.

Manages regulatory inspection preparation including mock inspections, inspection
checklists, document readiness, CAPA tracking, inspector observations, and
readiness scoring for FDA/EMA/PMDA inspections.

Usage:
    from app.services.inspection_readiness_service import (
        get_inspection_readiness_service,
    )

    svc = get_inspection_readiness_service()
    inspections = svc.list_inspections()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.inspection_readiness import (
    CAPA,
    CAPACreate,
    CAPAStatus,
    CAPAUpdate,
    CategoryScore,
    ChecklistCategory,
    ChecklistItemStatus,
    FindingSeverity,
    InspectionEvent,
    InspectionEventCreate,
    InspectionEventStatus,
    InspectionEventUpdate,
    InspectionFinding,
    InspectionFindingCreate,
    InspectionFindingUpdate,
    InspectionMetrics,
    InspectionOutcome,
    InspectionType,
    ReadinessAssessment,
    ReadinessAssessmentCreate,
    ReadinessAssessmentUpdate,
    ReadinessChecklist,
    ReadinessChecklistCreate,
    ReadinessChecklistUpdate,
    ReadinessStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

# Readiness score thresholds
READINESS_CRITICAL = 50.0
READINESS_NEEDS_ATTENTION = 70.0
READINESS_READY = 85.0


class InspectionReadinessService:
    """In-memory Inspection Readiness engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._inspections: dict[str, InspectionEvent] = {}
        self._assessments: dict[str, ReadinessAssessment] = {}
        self._checklists: dict[str, ReadinessChecklist] = {}
        self._findings: dict[str, InspectionFinding] = {}
        self._capas: dict[str, CAPA] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic inspection readiness data."""
        now = datetime.now(timezone.utc)

        # --- 5 Inspection Events ---
        inspections_data = [
            {
                "id": "INSP-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "inspection_type": InspectionType.FDA_ROUTINE,
                "scheduled_date": now - timedelta(days=90),
                "actual_date": now - timedelta(days=88),
                "inspector_name": "Dr. Patricia Wells",
                "inspector_agency": "FDA CDER",
                "status": InspectionEventStatus.COMPLETED,
                "outcome": InspectionOutcome.NO_ACTION_INDICATED,
                "duration_days": 3,
                "scope": "GCP compliance, informed consent, data integrity",
                "findings_count": 2,
                "observations": "Site generally well-organized. Minor documentation gaps noted.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "INSP-002",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "inspection_type": InspectionType.FDA_FOR_CAUSE,
                "scheduled_date": now - timedelta(days=45),
                "actual_date": now - timedelta(days=44),
                "inspector_name": "Dr. James Harrington",
                "inspector_agency": "FDA CDER",
                "status": InspectionEventStatus.COMPLETED,
                "outcome": InspectionOutcome.VOLUNTARY_ACTION_INDICATED,
                "duration_days": 5,
                "scope": "Protocol adherence, SAE reporting, source data verification",
                "findings_count": 4,
                "observations": "Several protocol deviations found. SAE reporting delays documented.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "INSP-003",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "inspection_type": InspectionType.EMA_GCP,
                "scheduled_date": now + timedelta(days=30),
                "actual_date": None,
                "inspector_name": "Dr. Sophie Laurent",
                "inspector_agency": "EMA",
                "status": InspectionEventStatus.SCHEDULED,
                "outcome": InspectionOutcome.PENDING,
                "duration_days": 4,
                "scope": "Full GCP inspection - data management, safety reporting, pharmacy",
                "findings_count": 0,
                "observations": None,
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "INSP-004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "inspection_type": InspectionType.MOCK,
                "scheduled_date": now - timedelta(days=10),
                "actual_date": now - timedelta(days=10),
                "inspector_name": "Dr. Michael Chen",
                "inspector_agency": "Internal QA",
                "status": InspectionEventStatus.COMPLETED,
                "outcome": InspectionOutcome.NOT_APPLICABLE,
                "duration_days": 2,
                "scope": "Pre-inspection readiness mock audit covering all domains",
                "findings_count": 3,
                "observations": "Good overall readiness. Training records need updating.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "INSP-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-107",
                "inspection_type": InspectionType.FDA_PRE_APPROVAL,
                "scheduled_date": now + timedelta(days=60),
                "actual_date": None,
                "inspector_name": "Dr. Robert Kim",
                "inspector_agency": "FDA CDER",
                "status": InspectionEventStatus.SCHEDULED,
                "outcome": InspectionOutcome.PENDING,
                "duration_days": 5,
                "scope": "Pre-approval inspection: manufacturing, clinical data, labeling",
                "findings_count": 0,
                "observations": None,
                "created_at": now - timedelta(days=10),
            },
        ]

        for insp in inspections_data:
            self._inspections[insp["id"]] = InspectionEvent(**insp)

        # --- 5 Readiness Assessments ---
        assessments_data = [
            {
                "id": "RA-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "assessment_date": now - timedelta(days=100),
                "assessed_by": "Laura Thompson",
                "overall_score": 92.0,
                "overall_status": ReadinessStatus.READY,
                "category_scores": [
                    CategoryScore(category=ChecklistCategory.DOCUMENTATION, score=95.0, items_total=5, items_complete=5),
                    CategoryScore(category=ChecklistCategory.FACILITIES, score=90.0, items_total=3, items_complete=3),
                    CategoryScore(category=ChecklistCategory.PERSONNEL, score=88.0, items_total=4, items_complete=3),
                    CategoryScore(category=ChecklistCategory.TRAINING, score=95.0, items_total=3, items_complete=3),
                ],
                "gaps_identified": 1,
                "action_items_count": 2,
                "next_assessment_date": now + timedelta(days=60),
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "RA-002",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "assessment_date": now - timedelta(days=60),
                "assessed_by": "Mark Stevens",
                "overall_score": 58.0,
                "overall_status": ReadinessStatus.NEEDS_ATTENTION,
                "category_scores": [
                    CategoryScore(category=ChecklistCategory.DOCUMENTATION, score=60.0, items_total=5, items_complete=3),
                    CategoryScore(category=ChecklistCategory.PROCESSES, score=45.0, items_total=4, items_complete=2),
                    CategoryScore(category=ChecklistCategory.SYSTEMS, score=70.0, items_total=3, items_complete=2),
                    CategoryScore(category=ChecklistCategory.QUALITY, score=55.0, items_total=4, items_complete=2),
                ],
                "gaps_identified": 6,
                "action_items_count": 8,
                "next_assessment_date": now + timedelta(days=14),
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "RA-003",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "assessment_date": now - timedelta(days=20),
                "assessed_by": "Laura Thompson",
                "overall_score": 42.0,
                "overall_status": ReadinessStatus.CRITICAL_GAPS,
                "category_scores": [
                    CategoryScore(category=ChecklistCategory.DOCUMENTATION, score=35.0, items_total=5, items_complete=1),
                    CategoryScore(category=ChecklistCategory.PERSONNEL, score=50.0, items_total=4, items_complete=2),
                    CategoryScore(category=ChecklistCategory.TRAINING, score=30.0, items_total=3, items_complete=1),
                    CategoryScore(category=ChecklistCategory.QUALITY, score=52.0, items_total=4, items_complete=2),
                ],
                "gaps_identified": 10,
                "action_items_count": 15,
                "next_assessment_date": now + timedelta(days=7),
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "RA-004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "assessment_date": now - timedelta(days=15),
                "assessed_by": "Laura Thompson",
                "overall_score": 78.0,
                "overall_status": ReadinessStatus.IN_PROGRESS,
                "category_scores": [
                    CategoryScore(category=ChecklistCategory.DOCUMENTATION, score=85.0, items_total=5, items_complete=4),
                    CategoryScore(category=ChecklistCategory.FACILITIES, score=90.0, items_total=3, items_complete=3),
                    CategoryScore(category=ChecklistCategory.PERSONNEL, score=70.0, items_total=4, items_complete=3),
                    CategoryScore(category=ChecklistCategory.TRAINING, score=65.0, items_total=3, items_complete=2),
                ],
                "gaps_identified": 3,
                "action_items_count": 4,
                "next_assessment_date": now + timedelta(days=30),
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "RA-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-107",
                "assessment_date": now - timedelta(days=5),
                "assessed_by": "Mark Stevens",
                "overall_score": 35.0,
                "overall_status": ReadinessStatus.CRITICAL_GAPS,
                "category_scores": [
                    CategoryScore(category=ChecklistCategory.DOCUMENTATION, score=30.0, items_total=5, items_complete=1),
                    CategoryScore(category=ChecklistCategory.SYSTEMS, score=40.0, items_total=3, items_complete=1),
                    CategoryScore(category=ChecklistCategory.PROCESSES, score=25.0, items_total=4, items_complete=1),
                    CategoryScore(category=ChecklistCategory.QUALITY, score=45.0, items_total=4, items_complete=2),
                ],
                "gaps_identified": 12,
                "action_items_count": 18,
                "next_assessment_date": now + timedelta(days=7),
                "created_at": now - timedelta(days=5),
            },
        ]

        for asmt in assessments_data:
            self._assessments[asmt["id"]] = ReadinessAssessment(**asmt)

        # --- 18 Checklist Items ---
        checklists_data = [
            # RA-001 checklists (SITE-101 - ready)
            {"id": "CL-001", "assessment_id": "RA-001", "category": ChecklistCategory.DOCUMENTATION, "item_description": "Investigator Brochure current version on file", "required": True, "status": ChecklistItemStatus.COMPLETE, "evidence_reference": "ISF-001/IB-v5.2", "verified_by": "Laura Thompson", "verified_date": now - timedelta(days=100)},
            {"id": "CL-002", "assessment_id": "RA-001", "category": ChecklistCategory.DOCUMENTATION, "item_description": "All protocol amendments filed and signed", "required": True, "status": ChecklistItemStatus.COMPLETE, "evidence_reference": "ISF-001/PROT-AMD-3", "verified_by": "Laura Thompson", "verified_date": now - timedelta(days=100)},
            {"id": "CL-003", "assessment_id": "RA-001", "category": ChecklistCategory.DOCUMENTATION, "item_description": "IRB/IEC approval letters current", "required": True, "status": ChecklistItemStatus.COMPLETE, "evidence_reference": "ISF-001/IRB-2025-12", "verified_by": "Laura Thompson", "verified_date": now - timedelta(days=100)},
            {"id": "CL-004", "assessment_id": "RA-001", "category": ChecklistCategory.FACILITIES, "item_description": "IP storage temperature logs reviewed", "required": True, "status": ChecklistItemStatus.COMPLETE, "evidence_reference": "PHARM-LOG-Q4-2025", "verified_by": "Laura Thompson", "verified_date": now - timedelta(days=100)},
            {"id": "CL-005", "assessment_id": "RA-001", "category": ChecklistCategory.PERSONNEL, "item_description": "Delegation of authority log up to date", "required": True, "status": ChecklistItemStatus.COMPLETE, "evidence_reference": "ISF-001/DOA-v8", "verified_by": "Laura Thompson", "verified_date": now - timedelta(days=100)},
            {"id": "CL-006", "assessment_id": "RA-001", "category": ChecklistCategory.TRAINING, "item_description": "GCP training certificates current for all staff", "required": True, "status": ChecklistItemStatus.COMPLETE, "evidence_reference": "TRAINING-GCP-2025", "verified_by": "Laura Thompson", "verified_date": now - timedelta(days=100)},
            # RA-002 checklists (SITE-103 - needs attention)
            {"id": "CL-007", "assessment_id": "RA-002", "category": ChecklistCategory.DOCUMENTATION, "item_description": "Source document templates standardized", "required": True, "status": ChecklistItemStatus.IN_PROGRESS, "evidence_reference": None, "notes": "Templates being updated to match protocol amendment 3"},
            {"id": "CL-008", "assessment_id": "RA-002", "category": ChecklistCategory.PROCESSES, "item_description": "SAE reporting workflow documented and tested", "required": True, "status": ChecklistItemStatus.NEEDS_REMEDIATION, "evidence_reference": None, "notes": "Current workflow has gaps in escalation procedures"},
            {"id": "CL-009", "assessment_id": "RA-002", "category": ChecklistCategory.SYSTEMS, "item_description": "EDC system validation documentation complete", "required": True, "status": ChecklistItemStatus.COMPLETE, "evidence_reference": "VAL-EDC-2025-Q3", "verified_by": "Mark Stevens", "verified_date": now - timedelta(days=60)},
            {"id": "CL-010", "assessment_id": "RA-002", "category": ChecklistCategory.QUALITY, "item_description": "Internal audit findings addressed", "required": True, "status": ChecklistItemStatus.IN_PROGRESS, "evidence_reference": None, "notes": "3 of 5 audit findings remediated"},
            # RA-003 checklists (SITE-105 - critical gaps)
            {"id": "CL-011", "assessment_id": "RA-003", "category": ChecklistCategory.DOCUMENTATION, "item_description": "Regulatory correspondence file organized", "required": True, "status": ChecklistItemStatus.NOT_STARTED, "evidence_reference": None, "notes": "File needs complete reorganization"},
            {"id": "CL-012", "assessment_id": "RA-003", "category": ChecklistCategory.PERSONNEL, "item_description": "Sub-investigator CVs and medical licenses current", "required": True, "status": ChecklistItemStatus.NEEDS_REMEDIATION, "evidence_reference": None, "notes": "2 sub-investigators have expired licenses"},
            {"id": "CL-013", "assessment_id": "RA-003", "category": ChecklistCategory.TRAINING, "item_description": "Protocol-specific training completed for all staff", "required": True, "status": ChecklistItemStatus.NOT_STARTED, "evidence_reference": None, "notes": "3 new staff members untrained"},
            {"id": "CL-014", "assessment_id": "RA-003", "category": ChecklistCategory.QUALITY, "item_description": "CAPA tracking system operational", "required": True, "status": ChecklistItemStatus.IN_PROGRESS, "evidence_reference": None},
            # RA-004 checklists (SITE-101 - in progress, second assessment)
            {"id": "CL-015", "assessment_id": "RA-004", "category": ChecklistCategory.DOCUMENTATION, "item_description": "Informed consent form version control verified", "required": True, "status": ChecklistItemStatus.COMPLETE, "evidence_reference": "ICF-CTRL-v3", "verified_by": "Laura Thompson", "verified_date": now - timedelta(days=15)},
            {"id": "CL-016", "assessment_id": "RA-004", "category": ChecklistCategory.TRAINING, "item_description": "Annual GCP refresher training documented", "required": True, "status": ChecklistItemStatus.IN_PROGRESS, "evidence_reference": None, "notes": "2 of 6 staff completed refresher"},
            {"id": "CL-017", "assessment_id": "RA-004", "category": ChecklistCategory.FACILITIES, "item_description": "Laboratory certification and accreditation current", "required": True, "status": ChecklistItemStatus.COMPLETE, "evidence_reference": "LAB-CERT-2026", "verified_by": "Laura Thompson", "verified_date": now - timedelta(days=15)},
            {"id": "CL-018", "assessment_id": "RA-004", "category": ChecklistCategory.PERSONNEL, "item_description": "Financial disclosure forms collected from all investigators", "required": False, "status": ChecklistItemStatus.NOT_APPLICABLE, "evidence_reference": None, "notes": "Not required for this phase"},
        ]

        for cl in checklists_data:
            self._checklists[cl["id"]] = ReadinessChecklist(**cl)

        # --- 7 Inspection Findings ---
        findings_data = [
            # INSP-001 findings (SITE-101, FDA routine)
            {
                "id": "IF-001",
                "inspection_id": "INSP-001",
                "finding_number": "F-001",
                "severity": FindingSeverity.MINOR,
                "category": ChecklistCategory.DOCUMENTATION,
                "description": "Delegation of authority log not updated within 30 days of personnel change",
                "root_cause": "Administrative oversight during staff transition",
                "regulatory_reference": "21 CFR 312.62",
                "response_due_date": now - timedelta(days=60),
                "response_submitted": True,
                "response_accepted": True,
                "created_at": now - timedelta(days=88),
            },
            {
                "id": "IF-002",
                "inspection_id": "INSP-001",
                "finding_number": "F-002",
                "severity": FindingSeverity.OBSERVATION,
                "category": ChecklistCategory.FACILITIES,
                "description": "Temperature monitoring log for IP storage had 2 gaps in recording",
                "root_cause": None,
                "regulatory_reference": "21 CFR 312.62(a)",
                "response_due_date": now - timedelta(days=60),
                "response_submitted": True,
                "response_accepted": True,
                "created_at": now - timedelta(days=88),
            },
            # INSP-002 findings (SITE-103, FDA for-cause)
            {
                "id": "IF-003",
                "inspection_id": "INSP-002",
                "finding_number": "F-001",
                "severity": FindingSeverity.CRITICAL,
                "category": ChecklistCategory.PROCESSES,
                "description": "SAE not reported to sponsor within 24 hours for 4 events over 6-month period",
                "root_cause": "Inadequate SAE reporting workflow and lack of backup notification system",
                "regulatory_reference": "21 CFR 312.32, ICH E6(R2) 4.11",
                "response_due_date": now - timedelta(days=15),
                "response_submitted": True,
                "response_accepted": False,
                "created_at": now - timedelta(days=44),
            },
            {
                "id": "IF-004",
                "inspection_id": "INSP-002",
                "finding_number": "F-002",
                "severity": FindingSeverity.MAJOR,
                "category": ChecklistCategory.DOCUMENTATION,
                "description": "Source documents did not match CRF entries for 8 out of 50 monitored data points",
                "root_cause": "Inconsistent data entry practices and insufficient source data verification",
                "regulatory_reference": "ICH E6(R2) 6.4.9",
                "response_due_date": now - timedelta(days=15),
                "response_submitted": True,
                "response_accepted": True,
                "created_at": now - timedelta(days=44),
            },
            {
                "id": "IF-005",
                "inspection_id": "INSP-002",
                "finding_number": "F-003",
                "severity": FindingSeverity.MAJOR,
                "category": ChecklistCategory.PERSONNEL,
                "description": "Principal investigator not adequately supervising sub-investigators",
                "root_cause": "PI overcommitted across multiple trials with insufficient delegation",
                "regulatory_reference": "21 CFR 312.60, ICH E6(R2) 4.2",
                "response_due_date": now + timedelta(days=15),
                "response_submitted": False,
                "response_accepted": False,
                "created_at": now - timedelta(days=44),
            },
            # INSP-004 findings (SITE-101, mock)
            {
                "id": "IF-006",
                "inspection_id": "INSP-004",
                "finding_number": "F-001",
                "severity": FindingSeverity.MINOR,
                "category": ChecklistCategory.TRAINING,
                "description": "Two staff members missing annual GCP refresher training certificates",
                "root_cause": "Training tracking system not sending automated reminders",
                "regulatory_reference": "ICH E6(R2) 2.8",
                "response_due_date": now + timedelta(days=30),
                "response_submitted": False,
                "response_accepted": False,
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "IF-007",
                "inspection_id": "INSP-004",
                "finding_number": "F-002",
                "severity": FindingSeverity.OBSERVATION,
                "category": ChecklistCategory.SYSTEMS,
                "description": "EDC audit trail review process not formally documented",
                "root_cause": None,
                "regulatory_reference": "21 CFR Part 11",
                "response_due_date": now + timedelta(days=45),
                "response_submitted": False,
                "response_accepted": False,
                "created_at": now - timedelta(days=10),
            },
        ]

        for fnd in findings_data:
            self._findings[fnd["id"]] = InspectionFinding(**fnd)

        # --- 6 CAPAs ---
        capas_data = [
            {
                "id": "CAPA-001",
                "finding_id": "IF-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "description": "Update delegation of authority log process",
                "root_cause_analysis": "No formal process for timely DOA updates; relied on manual tracking",
                "corrective_action": "Update DOA within 7 days of any personnel change; implement checklist for staff transitions",
                "preventive_action": "Implement automated notification system for DOA updates triggered by HR system changes",
                "assigned_to": "Sarah Mitchell",
                "due_date": now - timedelta(days=45),
                "completed_date": now - timedelta(days=50),
                "verified_by": "Laura Thompson",
                "verification_date": now - timedelta(days=40),
                "status": CAPAStatus.CLOSED,
                "effectiveness_check": True,
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "CAPA-002",
                "finding_id": "IF-003",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "description": "Overhaul SAE reporting workflow",
                "root_cause_analysis": "SAE notification relied on single point of contact with no backup system; email-based reporting susceptible to delays",
                "corrective_action": "Implement dual-notification SAE reporting with primary and backup contacts; deploy electronic SAE capture system with automated escalation",
                "preventive_action": "Monthly SAE reporting compliance audits; quarterly SAE simulation drills; real-time SAE dashboard for management oversight",
                "assigned_to": "Dr. Emily Nakamura",
                "due_date": now + timedelta(days=10),
                "completed_date": None,
                "verified_by": None,
                "verification_date": None,
                "status": CAPAStatus.IN_PROGRESS,
                "effectiveness_check": False,
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "CAPA-003",
                "finding_id": "IF-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "description": "Improve source data verification process",
                "root_cause_analysis": "Inconsistent data entry practices between site staff; no standardized SDV checklist",
                "corrective_action": "Create standardized SDV checklist; retrain all data entry staff; implement dual-entry for critical data points",
                "preventive_action": "Quarterly SDV audits by quality team; implement real-time data discrepancy alerts in EDC system",
                "assigned_to": "Mark Stevens",
                "due_date": now - timedelta(days=5),
                "completed_date": None,
                "verified_by": None,
                "verification_date": None,
                "status": CAPAStatus.OVERDUE,
                "effectiveness_check": False,
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "CAPA-004",
                "finding_id": "IF-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "description": "Address PI oversight deficiencies",
                "root_cause_analysis": "PI managing 4 concurrent trials with inadequate sub-investigator delegation framework",
                "corrective_action": "Reduce PI trial load to maximum 2 concurrent studies; formalize sub-investigator supervision schedule with documented reviews",
                "preventive_action": "Implement PI workload assessment tool; require documented supervision plan before trial activation",
                "assigned_to": "Dr. Emily Nakamura",
                "due_date": now + timedelta(days=30),
                "completed_date": None,
                "verified_by": None,
                "verification_date": None,
                "status": CAPAStatus.OPEN,
                "effectiveness_check": False,
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "CAPA-005",
                "finding_id": "IF-006",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "description": "Remediate training tracking gaps",
                "root_cause_analysis": "Training management system lacks automated reminder functionality; manual tracking spreadsheet not maintained",
                "corrective_action": "Complete GCP refresher training for both staff members within 2 weeks; migrate to automated training tracking system",
                "preventive_action": "Deploy learning management system with automated expiry notifications 60/30/7 days before certificate expiry",
                "assigned_to": "Sarah Mitchell",
                "due_date": now + timedelta(days=14),
                "completed_date": None,
                "verified_by": None,
                "verification_date": None,
                "status": CAPAStatus.PENDING_VERIFICATION,
                "effectiveness_check": False,
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "CAPA-006",
                "finding_id": "IF-007",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "description": "Document EDC audit trail review process",
                "root_cause_analysis": "Audit trail review performed ad hoc without formal SOP; process knowledge limited to one team member",
                "corrective_action": "Draft and approve SOP for EDC audit trail review including frequency, scope, and documentation requirements",
                "preventive_action": "Include audit trail review SOP in site initiation package; add to annual QMS review cycle",
                "assigned_to": "Mark Stevens",
                "due_date": now + timedelta(days=35),
                "completed_date": None,
                "verified_by": None,
                "verification_date": None,
                "status": CAPAStatus.OPEN,
                "effectiveness_check": False,
                "created_at": now - timedelta(days=10),
            },
        ]

        for capa in capas_data:
            self._capas[capa["id"]] = CAPA(**capa)

    # ------------------------------------------------------------------
    # Inspection Events
    # ------------------------------------------------------------------

    def list_inspections(
        self,
        *,
        trial_id: str | None = None,
        site_id: str | None = None,
        inspection_type: InspectionType | None = None,
        status: InspectionEventStatus | None = None,
    ) -> list[InspectionEvent]:
        """List inspection events with optional filters."""
        with self._lock:
            result = list(self._inspections.values())

        if trial_id is not None:
            result = [i for i in result if i.trial_id == trial_id]
        if site_id is not None:
            result = [i for i in result if i.site_id == site_id]
        if inspection_type is not None:
            result = [i for i in result if i.inspection_type == inspection_type]
        if status is not None:
            result = [i for i in result if i.status == status]

        return sorted(result, key=lambda i: i.scheduled_date, reverse=True)

    def get_inspection(self, inspection_id: str) -> InspectionEvent | None:
        """Get a single inspection event by ID."""
        with self._lock:
            return self._inspections.get(inspection_id)

    def schedule_inspection(self, payload: InspectionEventCreate) -> InspectionEvent:
        """Schedule a new inspection event."""
        now = datetime.now(timezone.utc)
        insp_id = f"INSP-{uuid4().hex[:8].upper()}"
        event = InspectionEvent(
            id=insp_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            inspection_type=payload.inspection_type,
            scheduled_date=payload.scheduled_date,
            actual_date=None,
            inspector_name=payload.inspector_name,
            inspector_agency=payload.inspector_agency,
            status=InspectionEventStatus.SCHEDULED,
            outcome=InspectionOutcome.PENDING,
            duration_days=payload.duration_days,
            scope=payload.scope,
            findings_count=0,
            observations=None,
            created_at=now,
        )
        with self._lock:
            self._inspections[insp_id] = event
        logger.info("Scheduled inspection %s for site %s", insp_id, payload.site_id)
        return event

    def update_inspection(self, inspection_id: str, payload: InspectionEventUpdate) -> InspectionEvent | None:
        """Update an existing inspection event."""
        with self._lock:
            existing = self._inspections.get(inspection_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = InspectionEvent(**data)
            self._inspections[inspection_id] = updated
        return updated

    def delete_inspection(self, inspection_id: str) -> bool:
        """Delete an inspection event. Returns True if deleted."""
        with self._lock:
            if inspection_id in self._inspections:
                del self._inspections[inspection_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Readiness Assessments
    # ------------------------------------------------------------------

    def list_assessments(
        self,
        *,
        trial_id: str | None = None,
        site_id: str | None = None,
        status: ReadinessStatus | None = None,
    ) -> list[ReadinessAssessment]:
        """List readiness assessments with optional filters."""
        with self._lock:
            result = list(self._assessments.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if site_id is not None:
            result = [a for a in result if a.site_id == site_id]
        if status is not None:
            result = [a for a in result if a.overall_status == status]

        return sorted(result, key=lambda a: a.assessment_date, reverse=True)

    def get_assessment(self, assessment_id: str) -> ReadinessAssessment | None:
        """Get a single readiness assessment by ID."""
        with self._lock:
            return self._assessments.get(assessment_id)

    def conduct_assessment(self, payload: ReadinessAssessmentCreate) -> ReadinessAssessment:
        """Create a new readiness assessment and auto-generate checklists."""
        now = datetime.now(timezone.utc)
        asmt_id = f"RA-{uuid4().hex[:8].upper()}"

        assessment = ReadinessAssessment(
            id=asmt_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            assessment_date=now,
            assessed_by=payload.assessed_by,
            overall_score=0.0,
            overall_status=ReadinessStatus.NOT_ASSESSED,
            category_scores=[],
            gaps_identified=0,
            action_items_count=0,
            next_assessment_date=now + timedelta(days=30),
            created_at=now,
        )
        with self._lock:
            self._assessments[asmt_id] = assessment

        logger.info("Conducted readiness assessment %s for site %s", asmt_id, payload.site_id)
        return assessment

    def update_assessment(self, assessment_id: str, payload: ReadinessAssessmentUpdate) -> ReadinessAssessment | None:
        """Update a readiness assessment."""
        with self._lock:
            existing = self._assessments.get(assessment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ReadinessAssessment(**data)
            self._assessments[assessment_id] = updated
        return updated

    def delete_assessment(self, assessment_id: str) -> bool:
        """Delete a readiness assessment. Returns True if deleted."""
        with self._lock:
            if assessment_id in self._assessments:
                del self._assessments[assessment_id]
                return True
            return False

    def score_readiness(self, assessment_id: str) -> ReadinessAssessment | None:
        """Calculate readiness score based on checklist completion for an assessment.

        Computes per-category scores and an overall weighted score, then
        determines the readiness status based on threshold levels.
        """
        with self._lock:
            existing = self._assessments.get(assessment_id)
            if existing is None:
                return None

            # Get all checklist items for this assessment
            items = [
                cl for cl in self._checklists.values()
                if cl.assessment_id == assessment_id
            ]

        if not items:
            return existing

        # Group by category and compute per-category scores
        by_category: dict[ChecklistCategory, list[ReadinessChecklist]] = {}
        for item in items:
            by_category.setdefault(item.category, []).append(item)

        category_scores: list[CategoryScore] = []
        total_required = 0
        total_complete = 0
        gaps = 0

        for cat, cat_items in by_category.items():
            applicable = [i for i in cat_items if i.status != ChecklistItemStatus.NOT_APPLICABLE]
            if not applicable:
                category_scores.append(
                    CategoryScore(category=cat, score=100.0, items_total=0, items_complete=0)
                )
                continue

            complete = sum(1 for i in applicable if i.status == ChecklistItemStatus.COMPLETE)
            needs_remediation = sum(1 for i in applicable if i.status == ChecklistItemStatus.NEEDS_REMEDIATION)
            required_count = sum(1 for i in applicable if i.required)
            required_complete = sum(
                1 for i in applicable if i.required and i.status == ChecklistItemStatus.COMPLETE
            )

            score = (complete / len(applicable)) * 100.0 if applicable else 0.0
            category_scores.append(
                CategoryScore(
                    category=cat,
                    score=round(score, 1),
                    items_total=len(applicable),
                    items_complete=complete,
                )
            )

            total_required += required_count
            total_complete += required_complete
            gaps += needs_remediation + sum(
                1 for i in applicable
                if i.required and i.status in (ChecklistItemStatus.NOT_STARTED, ChecklistItemStatus.NEEDS_REMEDIATION)
            )

        # Overall score = average of category scores
        overall_score = round(
            sum(cs.score for cs in category_scores) / max(1, len(category_scores)), 1
        )

        # Determine status
        if overall_score >= READINESS_READY:
            overall_status = ReadinessStatus.READY
        elif overall_score >= READINESS_NEEDS_ATTENTION:
            overall_status = ReadinessStatus.IN_PROGRESS
        elif overall_score >= READINESS_CRITICAL:
            overall_status = ReadinessStatus.NEEDS_ATTENTION
        else:
            overall_status = ReadinessStatus.CRITICAL_GAPS

        now = datetime.now(timezone.utc)
        data = existing.model_dump()
        data["overall_score"] = overall_score
        data["overall_status"] = overall_status
        data["category_scores"] = category_scores
        data["gaps_identified"] = gaps
        data["assessment_date"] = now

        updated = ReadinessAssessment(**data)
        with self._lock:
            self._assessments[assessment_id] = updated

        logger.info(
            "Scored readiness for assessment %s: %.1f (%s)",
            assessment_id, overall_score, overall_status.value,
        )
        return updated

    # ------------------------------------------------------------------
    # Checklists
    # ------------------------------------------------------------------

    def list_checklists(
        self,
        *,
        assessment_id: str | None = None,
        category: ChecklistCategory | None = None,
        status: ChecklistItemStatus | None = None,
    ) -> list[ReadinessChecklist]:
        """List checklist items with optional filters."""
        with self._lock:
            result = list(self._checklists.values())

        if assessment_id is not None:
            result = [cl for cl in result if cl.assessment_id == assessment_id]
        if category is not None:
            result = [cl for cl in result if cl.category == category]
        if status is not None:
            result = [cl for cl in result if cl.status == status]

        return sorted(result, key=lambda cl: cl.id)

    def get_checklist(self, checklist_id: str) -> ReadinessChecklist | None:
        """Get a single checklist item by ID."""
        with self._lock:
            return self._checklists.get(checklist_id)

    def create_checklist(self, payload: ReadinessChecklistCreate) -> ReadinessChecklist:
        """Create a new checklist item."""
        cl_id = f"CL-{uuid4().hex[:8].upper()}"
        cl = ReadinessChecklist(
            id=cl_id,
            assessment_id=payload.assessment_id,
            category=payload.category,
            item_description=payload.item_description,
            required=payload.required,
            status=ChecklistItemStatus.NOT_STARTED,
            evidence_reference=None,
            notes=None,
            verified_by=None,
            verified_date=None,
        )
        with self._lock:
            # Validate assessment exists
            if payload.assessment_id not in self._assessments:
                raise ValueError(f"Assessment '{payload.assessment_id}' not found")
            self._checklists[cl_id] = cl
        logger.info("Created checklist item %s for assessment %s", cl_id, payload.assessment_id)
        return cl

    def update_checklist(self, checklist_id: str, payload: ReadinessChecklistUpdate) -> ReadinessChecklist | None:
        """Update a checklist item."""
        with self._lock:
            existing = self._checklists.get(checklist_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ReadinessChecklist(**data)
            self._checklists[checklist_id] = updated
        return updated

    def delete_checklist(self, checklist_id: str) -> bool:
        """Delete a checklist item. Returns True if deleted."""
        with self._lock:
            if checklist_id in self._checklists:
                del self._checklists[checklist_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Inspection Findings
    # ------------------------------------------------------------------

    def list_findings(
        self,
        *,
        inspection_id: str | None = None,
        severity: FindingSeverity | None = None,
        category: ChecklistCategory | None = None,
    ) -> list[InspectionFinding]:
        """List inspection findings with optional filters."""
        with self._lock:
            result = list(self._findings.values())

        if inspection_id is not None:
            result = [f for f in result if f.inspection_id == inspection_id]
        if severity is not None:
            result = [f for f in result if f.severity == severity]
        if category is not None:
            result = [f for f in result if f.category == category]

        return sorted(result, key=lambda f: f.created_at, reverse=True)

    def get_finding(self, finding_id: str) -> InspectionFinding | None:
        """Get a single inspection finding by ID."""
        with self._lock:
            return self._findings.get(finding_id)

    def record_finding(self, payload: InspectionFindingCreate) -> InspectionFinding:
        """Record a new inspection finding."""
        now = datetime.now(timezone.utc)
        finding_id = f"IF-{uuid4().hex[:8].upper()}"

        with self._lock:
            # Validate inspection exists
            inspection = self._inspections.get(payload.inspection_id)
            if inspection is None:
                raise ValueError(f"Inspection '{payload.inspection_id}' not found")

            # Auto-generate finding number
            existing_count = sum(
                1 for f in self._findings.values()
                if f.inspection_id == payload.inspection_id
            )
            finding_number = f"F-{existing_count + 1:03d}"

            finding = InspectionFinding(
                id=finding_id,
                inspection_id=payload.inspection_id,
                finding_number=finding_number,
                severity=payload.severity,
                category=payload.category,
                description=payload.description,
                root_cause=payload.root_cause,
                regulatory_reference=payload.regulatory_reference,
                response_due_date=payload.response_due_date,
                response_submitted=False,
                response_accepted=False,
                created_at=now,
            )
            self._findings[finding_id] = finding

            # Update inspection findings count
            data = inspection.model_dump()
            data["findings_count"] = existing_count + 1
            self._inspections[payload.inspection_id] = InspectionEvent(**data)

        logger.info(
            "Recorded finding %s (%s) for inspection %s",
            finding_id, payload.severity.value, payload.inspection_id,
        )
        return finding

    def update_finding(self, finding_id: str, payload: InspectionFindingUpdate) -> InspectionFinding | None:
        """Update an inspection finding."""
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
        """Delete an inspection finding. Returns True if deleted."""
        with self._lock:
            if finding_id in self._findings:
                del self._findings[finding_id]
                return True
            return False

    # ------------------------------------------------------------------
    # CAPAs
    # ------------------------------------------------------------------

    def list_capas(
        self,
        *,
        trial_id: str | None = None,
        site_id: str | None = None,
        status: CAPAStatus | None = None,
        finding_id: str | None = None,
    ) -> list[CAPA]:
        """List CAPAs with optional filters."""
        with self._lock:
            result = list(self._capas.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]
        if site_id is not None:
            result = [c for c in result if c.site_id == site_id]
        if status is not None:
            result = [c for c in result if c.status == status]
        if finding_id is not None:
            result = [c for c in result if c.finding_id == finding_id]

        return sorted(result, key=lambda c: c.due_date)

    def get_capa(self, capa_id: str) -> CAPA | None:
        """Get a single CAPA by ID."""
        with self._lock:
            return self._capas.get(capa_id)

    def create_capa(self, payload: CAPACreate) -> CAPA:
        """Create a new CAPA."""
        now = datetime.now(timezone.utc)
        capa_id = f"CAPA-{uuid4().hex[:8].upper()}"

        with self._lock:
            # Validate finding exists
            if payload.finding_id not in self._findings:
                raise ValueError(f"Finding '{payload.finding_id}' not found")

        capa = CAPA(
            id=capa_id,
            finding_id=payload.finding_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            description=payload.description,
            root_cause_analysis=payload.root_cause_analysis,
            corrective_action=payload.corrective_action,
            preventive_action=payload.preventive_action,
            assigned_to=payload.assigned_to,
            due_date=payload.due_date,
            completed_date=None,
            verified_by=None,
            verification_date=None,
            status=CAPAStatus.OPEN,
            effectiveness_check=False,
            created_at=now,
        )
        with self._lock:
            self._capas[capa_id] = capa
        logger.info("Created CAPA %s for finding %s", capa_id, payload.finding_id)
        return capa

    def update_capa(self, capa_id: str, payload: CAPAUpdate) -> CAPA | None:
        """Update a CAPA."""
        with self._lock:
            existing = self._capas.get(capa_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-handle status transitions
            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = CAPAStatus(new_status)
                if new_status == CAPAStatus.CLOSED and existing.status != CAPAStatus.CLOSED:
                    if "completed_date" not in updates or updates["completed_date"] is None:
                        updates["completed_date"] = datetime.now(timezone.utc)

            data.update(updates)
            updated = CAPA(**data)
            self._capas[capa_id] = updated
        return updated

    def delete_capa(self, capa_id: str) -> bool:
        """Delete a CAPA. Returns True if deleted."""
        with self._lock:
            if capa_id in self._capas:
                del self._capas[capa_id]
                return True
            return False

    def get_overdue_capas(self) -> list[CAPA]:
        """Get CAPAs that are past their due date and not closed."""
        now = datetime.now(timezone.utc)
        with self._lock:
            result = [
                c for c in self._capas.values()
                if c.status in (CAPAStatus.OPEN, CAPAStatus.IN_PROGRESS, CAPAStatus.OVERDUE)
                and c.due_date < now
            ]
        return sorted(result, key=lambda c: c.due_date)

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> InspectionMetrics:
        """Compute aggregated inspection readiness metrics."""
        now = datetime.now(timezone.utc)

        with self._lock:
            inspections = list(self._inspections.values())
            assessments = list(self._assessments.values())
            checklists = list(self._checklists.values())
            findings = list(self._findings.values())
            capas = list(self._capas.values())

        # Inspections by type
        by_type: dict[str, int] = {}
        for insp in inspections:
            key = insp.inspection_type.value
            by_type[key] = by_type.get(key, 0) + 1

        # Inspections by status
        by_status: dict[str, int] = {}
        for insp in inspections:
            key = insp.status.value
            by_status[key] = by_status.get(key, 0) + 1

        # Average readiness score
        avg_score = 0.0
        if assessments:
            avg_score = round(
                sum(a.overall_score for a in assessments) / len(assessments), 1
            )

        # Assessments by status
        asmt_by_status: dict[str, int] = {}
        for asmt in assessments:
            key = asmt.overall_status.value
            asmt_by_status[key] = asmt_by_status.get(key, 0) + 1

        # Checklist completion
        applicable_items = [
            cl for cl in checklists if cl.status != ChecklistItemStatus.NOT_APPLICABLE
        ]
        complete_items = sum(
            1 for cl in applicable_items if cl.status == ChecklistItemStatus.COMPLETE
        )
        completion_rate = round(
            (complete_items / max(1, len(applicable_items))) * 100.0, 1
        )

        # Findings by severity
        by_severity: dict[str, int] = {}
        for fnd in findings:
            key = fnd.severity.value
            by_severity[key] = by_severity.get(key, 0) + 1

        # CAPAs by status
        capas_by_status: dict[str, int] = {}
        overdue_count = 0
        open_count = 0
        for capa in capas:
            key = capa.status.value
            capas_by_status[key] = capas_by_status.get(key, 0) + 1
            if capa.status in (CAPAStatus.OPEN, CAPAStatus.IN_PROGRESS, CAPAStatus.OVERDUE) and capa.due_date < now:
                overdue_count += 1
            if capa.status in (CAPAStatus.OPEN, CAPAStatus.IN_PROGRESS):
                open_count += 1

        # Sites ready / critical
        sites_ready = sum(
            1 for a in assessments if a.overall_status == ReadinessStatus.READY
        )
        sites_critical = sum(
            1 for a in assessments if a.overall_status == ReadinessStatus.CRITICAL_GAPS
        )

        return InspectionMetrics(
            total_inspections=len(inspections),
            inspections_by_type=by_type,
            inspections_by_status=by_status,
            total_assessments=len(assessments),
            average_readiness_score=avg_score,
            assessments_by_status=asmt_by_status,
            total_checklist_items=len(checklists),
            checklist_completion_rate=completion_rate,
            total_findings=len(findings),
            findings_by_severity=by_severity,
            total_capas=len(capas),
            capas_by_status=capas_by_status,
            overdue_capas=overdue_count,
            open_capas=open_count,
            sites_ready=sites_ready,
            sites_with_critical_gaps=sites_critical,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: InspectionReadinessService | None = None
_instance_lock = threading.Lock()


def get_inspection_readiness_service() -> InspectionReadinessService:
    """Return the singleton InspectionReadinessService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = InspectionReadinessService()
    return _instance


def reset_inspection_readiness_service() -> InspectionReadinessService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = InspectionReadinessService()
    return _instance
