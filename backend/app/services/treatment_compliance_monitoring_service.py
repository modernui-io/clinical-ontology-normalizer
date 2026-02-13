"""Treatment Compliance Monitoring (TCM-MON) Service.

Manages treatment compliance monitoring operations: dosing records, compliance
assessments, medication accountability logs, and treatment interruption events
with aggregated metrics.

Usage:
    from app.services.treatment_compliance_monitoring_service import (
        get_treatment_compliance_monitoring_service,
    )

    svc = get_treatment_compliance_monitoring_service()
    records = svc.list_dosing_records()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.treatment_compliance_monitoring import (
    AccountabilityAction,
    ComplianceAssessment,
    ComplianceAssessmentCreate,
    ComplianceAssessmentUpdate,
    ComplianceLevel,
    DosingRecord,
    DosingRecordCreate,
    DosingRecordUpdate,
    DosingStatus,
    InterruptionReason,
    InterruptionStatus,
    MedicationAccountabilityLog,
    MedicationAccountabilityLogCreate,
    MedicationAccountabilityLogUpdate,
    TreatmentComplianceMetrics,
    TreatmentInterruptionEvent,
    TreatmentInterruptionEventCreate,
    TreatmentInterruptionEventUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class TreatmentComplianceMonitoringService:
    """In-memory Treatment Compliance Monitoring engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._dosing_records: dict[str, DosingRecord] = {}
        self._compliance_assessments: dict[str, ComplianceAssessment] = {}
        self._medication_accountability_logs: dict[str, MedicationAccountabilityLog] = {}
        self._treatment_interruption_events: dict[str, TreatmentInterruptionEvent] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic treatment compliance data across 3 trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Dosing Records (4 per trial) ---
        dosing_data = [
            # EYLEA
            {
                "id": "DOS-00000001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E001",
                "site_id": "SITE-101",
                "dosing_status": DosingStatus.ADMINISTERED,
                "study_drug_name": "Aflibercept 2mg",
                "dose_amount": 2.0,
                "dose_unit": "mg",
                "route_of_administration": "Intravitreal injection",
                "scheduled_date": now - timedelta(days=90),
                "actual_date": now - timedelta(days=90),
                "visit_number": 1,
                "cycle_number": 1,
                "lot_number": "LOT-EYL-2025A",
                "administered_by": "Dr. Sarah Mitchell",
                "witnessed_by": "RN Jane Foster",
                "reason_not_given": None,
                "notes": "Administered per protocol without complications.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "DOS-00000002",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E002",
                "site_id": "SITE-101",
                "dosing_status": DosingStatus.ADMINISTERED,
                "study_drug_name": "Aflibercept 2mg",
                "dose_amount": 2.0,
                "dose_unit": "mg",
                "route_of_administration": "Intravitreal injection",
                "scheduled_date": now - timedelta(days=60),
                "actual_date": now - timedelta(days=59),
                "visit_number": 2,
                "cycle_number": 1,
                "lot_number": "LOT-EYL-2025A",
                "administered_by": "Dr. Sarah Mitchell",
                "witnessed_by": "RN Jane Foster",
                "reason_not_given": None,
                "notes": None,
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "DOS-00000003",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E003",
                "site_id": "SITE-102",
                "dosing_status": DosingStatus.MISSED,
                "study_drug_name": "Aflibercept 2mg",
                "dose_amount": 2.0,
                "dose_unit": "mg",
                "route_of_administration": "Intravitreal injection",
                "scheduled_date": now - timedelta(days=30),
                "actual_date": None,
                "visit_number": 3,
                "cycle_number": 1,
                "lot_number": None,
                "administered_by": None,
                "witnessed_by": None,
                "reason_not_given": "Patient did not attend visit",
                "notes": "Patient rescheduled for next week.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "DOS-00000004",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E004",
                "site_id": "SITE-102",
                "dosing_status": DosingStatus.DELAYED,
                "study_drug_name": "Aflibercept 2mg",
                "dose_amount": 2.0,
                "dose_unit": "mg",
                "route_of_administration": "Intravitreal injection",
                "scheduled_date": now - timedelta(days=14),
                "actual_date": now - timedelta(days=10),
                "visit_number": 2,
                "cycle_number": 1,
                "lot_number": "LOT-EYL-2025B",
                "administered_by": "Dr. David Park",
                "witnessed_by": "RN Lisa Chen",
                "reason_not_given": None,
                "notes": "Delayed 4 days due to scheduling conflict.",
                "created_at": now - timedelta(days=14),
            },
            # DUPIXENT
            {
                "id": "DOS-00000005",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D001",
                "site_id": "SITE-103",
                "dosing_status": DosingStatus.ADMINISTERED,
                "study_drug_name": "Dupilumab 300mg",
                "dose_amount": 300.0,
                "dose_unit": "mg",
                "route_of_administration": "Subcutaneous injection",
                "scheduled_date": now - timedelta(days=84),
                "actual_date": now - timedelta(days=84),
                "visit_number": 1,
                "cycle_number": 1,
                "lot_number": "LOT-DUP-2025C",
                "administered_by": "Dr. Jennifer Lee",
                "witnessed_by": "RN Mark Torres",
                "reason_not_given": None,
                "notes": "Loading dose administered.",
                "created_at": now - timedelta(days=84),
            },
            {
                "id": "DOS-00000006",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D002",
                "site_id": "SITE-103",
                "dosing_status": DosingStatus.PARTIAL,
                "study_drug_name": "Dupilumab 300mg",
                "dose_amount": 200.0,
                "dose_unit": "mg",
                "route_of_administration": "Subcutaneous injection",
                "scheduled_date": now - timedelta(days=56),
                "actual_date": now - timedelta(days=56),
                "visit_number": 2,
                "cycle_number": 1,
                "lot_number": "LOT-DUP-2025C",
                "administered_by": "Dr. Jennifer Lee",
                "witnessed_by": None,
                "reason_not_given": None,
                "notes": "Only 200mg administered due to injection site reaction.",
                "created_at": now - timedelta(days=56),
            },
            {
                "id": "DOS-00000007",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D003",
                "site_id": "SITE-104",
                "dosing_status": DosingStatus.REFUSED,
                "study_drug_name": "Dupilumab 300mg",
                "dose_amount": 300.0,
                "dose_unit": "mg",
                "route_of_administration": "Subcutaneous injection",
                "scheduled_date": now - timedelta(days=28),
                "actual_date": None,
                "visit_number": 3,
                "cycle_number": 1,
                "lot_number": None,
                "administered_by": None,
                "witnessed_by": None,
                "reason_not_given": "Patient refused due to anxiety about injection",
                "notes": "Counseling provided. Dose rescheduled.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "DOS-00000008",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D004",
                "site_id": "SITE-104",
                "dosing_status": DosingStatus.ADMINISTERED,
                "study_drug_name": "Dupilumab 300mg",
                "dose_amount": 300.0,
                "dose_unit": "mg",
                "route_of_administration": "Subcutaneous injection",
                "scheduled_date": now - timedelta(days=7),
                "actual_date": now - timedelta(days=7),
                "visit_number": 4,
                "cycle_number": 2,
                "lot_number": "LOT-DUP-2025D",
                "administered_by": "Dr. David Park",
                "witnessed_by": "RN Amy Zhang",
                "reason_not_given": None,
                "notes": None,
                "created_at": now - timedelta(days=7),
            },
            # LIBTAYO
            {
                "id": "DOS-00000009",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L001",
                "site_id": "SITE-105",
                "dosing_status": DosingStatus.ADMINISTERED,
                "study_drug_name": "Cemiplimab 350mg",
                "dose_amount": 350.0,
                "dose_unit": "mg",
                "route_of_administration": "Intravenous infusion",
                "scheduled_date": now - timedelta(days=63),
                "actual_date": now - timedelta(days=63),
                "visit_number": 1,
                "cycle_number": 1,
                "lot_number": "LOT-LIB-2025E",
                "administered_by": "Dr. Jennifer Lee",
                "witnessed_by": "RN Carlos Rivera",
                "reason_not_given": None,
                "notes": "First infusion completed over 30 minutes.",
                "created_at": now - timedelta(days=63),
            },
            {
                "id": "DOS-00000010",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L002",
                "site_id": "SITE-105",
                "dosing_status": DosingStatus.HELD,
                "study_drug_name": "Cemiplimab 350mg",
                "dose_amount": 350.0,
                "dose_unit": "mg",
                "route_of_administration": "Intravenous infusion",
                "scheduled_date": now - timedelta(days=42),
                "actual_date": None,
                "visit_number": 2,
                "cycle_number": 1,
                "lot_number": None,
                "administered_by": None,
                "witnessed_by": None,
                "reason_not_given": "Dose held due to Grade 2 hepatotoxicity",
                "notes": "Monitoring liver function. Resume when resolved to Grade 1.",
                "created_at": now - timedelta(days=42),
            },
            {
                "id": "DOS-00000011",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L003",
                "site_id": "SITE-106",
                "dosing_status": DosingStatus.ADMINISTERED,
                "study_drug_name": "Cemiplimab 350mg",
                "dose_amount": 350.0,
                "dose_unit": "mg",
                "route_of_administration": "Intravenous infusion",
                "scheduled_date": now - timedelta(days=21),
                "actual_date": now - timedelta(days=21),
                "visit_number": 3,
                "cycle_number": 2,
                "lot_number": "LOT-LIB-2025F",
                "administered_by": "Dr. Sarah Mitchell",
                "witnessed_by": "RN Jane Foster",
                "reason_not_given": None,
                "notes": "Cycle 2 dose 1. Tolerated well.",
                "created_at": now - timedelta(days=21),
            },
            {
                "id": "DOS-00000012",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L004",
                "site_id": "SITE-106",
                "dosing_status": DosingStatus.ADMINISTERED,
                "study_drug_name": "Cemiplimab 350mg",
                "dose_amount": 350.0,
                "dose_unit": "mg",
                "route_of_administration": "Intravenous infusion",
                "scheduled_date": now - timedelta(days=3),
                "actual_date": now - timedelta(days=3),
                "visit_number": 4,
                "cycle_number": 2,
                "lot_number": "LOT-LIB-2025F",
                "administered_by": "Dr. Sarah Mitchell",
                "witnessed_by": "RN Lisa Chen",
                "reason_not_given": None,
                "notes": None,
                "created_at": now - timedelta(days=3),
            },
        ]

        for d in dosing_data:
            self._dosing_records[d["id"]] = DosingRecord(**d)

        # --- 12 Compliance Assessments (4 per trial) ---
        compliance_data = [
            # EYLEA
            {
                "id": "CAS-00000001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E001",
                "site_id": "SITE-101",
                "compliance_level": ComplianceLevel.FULLY_COMPLIANT,
                "assessment_date": now - timedelta(days=30),
                "assessment_period_start": now - timedelta(days=120),
                "assessment_period_end": now - timedelta(days=30),
                "doses_scheduled": 4,
                "doses_taken": 4,
                "doses_missed": 0,
                "compliance_percentage": 100.0,
                "assessment_method": "Pill count + diary review",
                "pill_count_performed": True,
                "diary_reviewed": True,
                "assessed_by": "CRA Sarah Mitchell",
                "intervention_recommended": False,
                "intervention_description": None,
                "notes": "Excellent compliance throughout study period.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "CAS-00000002",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E003",
                "site_id": "SITE-102",
                "compliance_level": ComplianceLevel.PARTIALLY_COMPLIANT,
                "assessment_date": now - timedelta(days=15),
                "assessment_period_start": now - timedelta(days=90),
                "assessment_period_end": now - timedelta(days=15),
                "doses_scheduled": 3,
                "doses_taken": 1,
                "doses_missed": 2,
                "compliance_percentage": 33.3,
                "assessment_method": "Diary review",
                "pill_count_performed": False,
                "diary_reviewed": True,
                "assessed_by": "CRA David Park",
                "intervention_recommended": True,
                "intervention_description": "Recommend adherence counseling and reminder system.",
                "notes": "Subject missed 2 visits due to transportation issues.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "CAS-00000003",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E002",
                "site_id": "SITE-101",
                "compliance_level": ComplianceLevel.MOSTLY_COMPLIANT,
                "assessment_date": now - timedelta(days=10),
                "assessment_period_start": now - timedelta(days=90),
                "assessment_period_end": now - timedelta(days=10),
                "doses_scheduled": 3,
                "doses_taken": 2,
                "doses_missed": 1,
                "compliance_percentage": 66.7,
                "assessment_method": "Electronic monitoring",
                "pill_count_performed": True,
                "diary_reviewed": False,
                "assessed_by": "CRA Sarah Mitchell",
                "intervention_recommended": False,
                "intervention_description": None,
                "notes": "One delayed dose counted as taken.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "CAS-00000004",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E004",
                "site_id": "SITE-102",
                "compliance_level": ComplianceLevel.MOSTLY_COMPLIANT,
                "assessment_date": now - timedelta(days=5),
                "assessment_period_start": now - timedelta(days=60),
                "assessment_period_end": now - timedelta(days=5),
                "doses_scheduled": 2,
                "doses_taken": 2,
                "doses_missed": 0,
                "compliance_percentage": 85.0,
                "assessment_method": "Pill count",
                "pill_count_performed": True,
                "diary_reviewed": False,
                "assessed_by": "CRA David Park",
                "intervention_recommended": False,
                "intervention_description": None,
                "notes": "One dose delayed but administered within window.",
                "created_at": now - timedelta(days=5),
            },
            # DUPIXENT
            {
                "id": "CAS-00000005",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D001",
                "site_id": "SITE-103",
                "compliance_level": ComplianceLevel.FULLY_COMPLIANT,
                "assessment_date": now - timedelta(days=28),
                "assessment_period_start": now - timedelta(days=84),
                "assessment_period_end": now - timedelta(days=28),
                "doses_scheduled": 4,
                "doses_taken": 4,
                "doses_missed": 0,
                "compliance_percentage": 100.0,
                "assessment_method": "Electronic monitoring + diary",
                "pill_count_performed": True,
                "diary_reviewed": True,
                "assessed_by": "CRA Jennifer Lee",
                "intervention_recommended": False,
                "intervention_description": None,
                "notes": "Fully compliant with all dosing schedules.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "CAS-00000006",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D002",
                "site_id": "SITE-103",
                "compliance_level": ComplianceLevel.PARTIALLY_COMPLIANT,
                "assessment_date": now - timedelta(days=20),
                "assessment_period_start": now - timedelta(days=84),
                "assessment_period_end": now - timedelta(days=20),
                "doses_scheduled": 4,
                "doses_taken": 3,
                "doses_missed": 1,
                "compliance_percentage": 62.5,
                "assessment_method": "Diary review",
                "pill_count_performed": False,
                "diary_reviewed": True,
                "assessed_by": "CRA Jennifer Lee",
                "intervention_recommended": True,
                "intervention_description": "Partial dose at visit 2 due to injection site reaction. Monitor closely.",
                "notes": "Partial dose reduces effective compliance.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "CAS-00000007",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D003",
                "site_id": "SITE-104",
                "compliance_level": ComplianceLevel.NON_COMPLIANT,
                "assessment_date": now - timedelta(days=14),
                "assessment_period_start": now - timedelta(days=84),
                "assessment_period_end": now - timedelta(days=14),
                "doses_scheduled": 4,
                "doses_taken": 1,
                "doses_missed": 3,
                "compliance_percentage": 25.0,
                "assessment_method": "Pill count + investigator review",
                "pill_count_performed": True,
                "diary_reviewed": True,
                "assessed_by": "CRA David Park",
                "intervention_recommended": True,
                "intervention_description": "Formal non-compliance counseling. Consider protocol deviation report.",
                "notes": "Patient refused 1 dose and missed 2 visits.",
                "created_at": now - timedelta(days=14),
            },
            {
                "id": "CAS-00000008",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D004",
                "site_id": "SITE-104",
                "compliance_level": ComplianceLevel.FULLY_COMPLIANT,
                "assessment_date": now - timedelta(days=3),
                "assessment_period_start": now - timedelta(days=56),
                "assessment_period_end": now - timedelta(days=3),
                "doses_scheduled": 4,
                "doses_taken": 4,
                "doses_missed": 0,
                "compliance_percentage": 100.0,
                "assessment_method": "Electronic monitoring",
                "pill_count_performed": True,
                "diary_reviewed": True,
                "assessed_by": "CRA David Park",
                "intervention_recommended": False,
                "intervention_description": None,
                "notes": None,
                "created_at": now - timedelta(days=3),
            },
            # LIBTAYO
            {
                "id": "CAS-00000009",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L001",
                "site_id": "SITE-105",
                "compliance_level": ComplianceLevel.FULLY_COMPLIANT,
                "assessment_date": now - timedelta(days=21),
                "assessment_period_start": now - timedelta(days=63),
                "assessment_period_end": now - timedelta(days=21),
                "doses_scheduled": 3,
                "doses_taken": 3,
                "doses_missed": 0,
                "compliance_percentage": 100.0,
                "assessment_method": "Infusion records review",
                "pill_count_performed": False,
                "diary_reviewed": False,
                "assessed_by": "CRA Jennifer Lee",
                "intervention_recommended": False,
                "intervention_description": None,
                "notes": "All infusions completed per schedule.",
                "created_at": now - timedelta(days=21),
            },
            {
                "id": "CAS-00000010",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L002",
                "site_id": "SITE-105",
                "compliance_level": ComplianceLevel.UNABLE_TO_ASSESS,
                "assessment_date": now - timedelta(days=14),
                "assessment_period_start": now - timedelta(days=63),
                "assessment_period_end": now - timedelta(days=14),
                "doses_scheduled": 3,
                "doses_taken": 1,
                "doses_missed": 0,
                "compliance_percentage": 33.3,
                "assessment_method": "Infusion records review",
                "pill_count_performed": False,
                "diary_reviewed": False,
                "assessed_by": "CRA Jennifer Lee",
                "intervention_recommended": False,
                "intervention_description": None,
                "notes": "Dose held for safety reasons. Not a compliance issue.",
                "created_at": now - timedelta(days=14),
            },
            {
                "id": "CAS-00000011",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L003",
                "site_id": "SITE-106",
                "compliance_level": ComplianceLevel.FULLY_COMPLIANT,
                "assessment_date": now - timedelta(days=7),
                "assessment_period_start": now - timedelta(days=63),
                "assessment_period_end": now - timedelta(days=7),
                "doses_scheduled": 3,
                "doses_taken": 3,
                "doses_missed": 0,
                "compliance_percentage": 100.0,
                "assessment_method": "Infusion records + pharmacy log",
                "pill_count_performed": False,
                "diary_reviewed": False,
                "assessed_by": "CRA Sarah Mitchell",
                "intervention_recommended": False,
                "intervention_description": None,
                "notes": None,
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "CAS-00000012",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L004",
                "site_id": "SITE-106",
                "compliance_level": ComplianceLevel.NOT_ASSESSED,
                "assessment_date": now - timedelta(days=1),
                "assessment_period_start": now - timedelta(days=42),
                "assessment_period_end": now - timedelta(days=1),
                "doses_scheduled": 2,
                "doses_taken": 2,
                "doses_missed": 0,
                "compliance_percentage": 100.0,
                "assessment_method": "Pending full review",
                "pill_count_performed": False,
                "diary_reviewed": False,
                "assessed_by": "CRA Sarah Mitchell",
                "intervention_recommended": False,
                "intervention_description": None,
                "notes": "Assessment in progress.",
                "created_at": now - timedelta(days=1),
            },
        ]

        for c in compliance_data:
            self._compliance_assessments[c["id"]] = ComplianceAssessment(**c)

        # --- 12 Medication Accountability Logs (4 per trial) ---
        accountability_data = [
            # EYLEA
            {
                "id": "MAL-00000001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E001",
                "site_id": "SITE-101",
                "accountability_action": AccountabilityAction.DISPENSED,
                "study_drug_name": "Aflibercept 2mg",
                "lot_number": "LOT-EYL-2025A",
                "quantity_units": 4,
                "quantity_dispensed": 4,
                "quantity_returned": 0,
                "quantity_consumed": 4,
                "quantity_lost": 0,
                "action_date": now - timedelta(days=120),
                "performed_by": "Pharmacist Robert Kim",
                "verified_by": "CRA Sarah Mitchell",
                "storage_conditions_met": True,
                "temperature_excursion": False,
                "notes": "Initial dispensing for subject E001.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "MAL-00000002",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E002",
                "site_id": "SITE-101",
                "accountability_action": AccountabilityAction.DISPENSED,
                "study_drug_name": "Aflibercept 2mg",
                "lot_number": "LOT-EYL-2025A",
                "quantity_units": 4,
                "quantity_dispensed": 4,
                "quantity_returned": 0,
                "quantity_consumed": 2,
                "quantity_lost": 0,
                "action_date": now - timedelta(days=90),
                "performed_by": "Pharmacist Robert Kim",
                "verified_by": "CRA Sarah Mitchell",
                "storage_conditions_met": True,
                "temperature_excursion": False,
                "notes": None,
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "MAL-00000003",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E003",
                "site_id": "SITE-102",
                "accountability_action": AccountabilityAction.RETURNED,
                "study_drug_name": "Aflibercept 2mg",
                "lot_number": "LOT-EYL-2025B",
                "quantity_units": 2,
                "quantity_dispensed": 4,
                "quantity_returned": 2,
                "quantity_consumed": 1,
                "quantity_lost": 1,
                "action_date": now - timedelta(days=14),
                "performed_by": "Pharmacist Maria Santos",
                "verified_by": "CRA David Park",
                "storage_conditions_met": True,
                "temperature_excursion": False,
                "notes": "Partial return. 1 unit unaccounted for.",
                "created_at": now - timedelta(days=14),
            },
            {
                "id": "MAL-00000004",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E004",
                "site_id": "SITE-102",
                "accountability_action": AccountabilityAction.QUARANTINED,
                "study_drug_name": "Aflibercept 2mg",
                "lot_number": "LOT-EYL-2025B",
                "quantity_units": 1,
                "quantity_dispensed": 0,
                "quantity_returned": 0,
                "quantity_consumed": 0,
                "quantity_lost": 0,
                "action_date": now - timedelta(days=7),
                "performed_by": "Pharmacist Maria Santos",
                "verified_by": None,
                "storage_conditions_met": False,
                "temperature_excursion": True,
                "notes": "Temperature excursion detected. Unit quarantined pending review.",
                "created_at": now - timedelta(days=7),
            },
            # DUPIXENT
            {
                "id": "MAL-00000005",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D001",
                "site_id": "SITE-103",
                "accountability_action": AccountabilityAction.DISPENSED,
                "study_drug_name": "Dupilumab 300mg",
                "lot_number": "LOT-DUP-2025C",
                "quantity_units": 8,
                "quantity_dispensed": 8,
                "quantity_returned": 0,
                "quantity_consumed": 4,
                "quantity_lost": 0,
                "action_date": now - timedelta(days=84),
                "performed_by": "Pharmacist Robert Kim",
                "verified_by": "CRA Jennifer Lee",
                "storage_conditions_met": True,
                "temperature_excursion": False,
                "notes": "Initial dispensing for 2-month supply.",
                "created_at": now - timedelta(days=84),
            },
            {
                "id": "MAL-00000006",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D002",
                "site_id": "SITE-103",
                "accountability_action": AccountabilityAction.DISPENSED,
                "study_drug_name": "Dupilumab 300mg",
                "lot_number": "LOT-DUP-2025C",
                "quantity_units": 4,
                "quantity_dispensed": 4,
                "quantity_returned": 0,
                "quantity_consumed": 3,
                "quantity_lost": 0,
                "action_date": now - timedelta(days=56),
                "performed_by": "Pharmacist Robert Kim",
                "verified_by": "CRA Jennifer Lee",
                "storage_conditions_met": True,
                "temperature_excursion": False,
                "notes": None,
                "created_at": now - timedelta(days=56),
            },
            {
                "id": "MAL-00000007",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D003",
                "site_id": "SITE-104",
                "accountability_action": AccountabilityAction.RETURNED,
                "study_drug_name": "Dupilumab 300mg",
                "lot_number": "LOT-DUP-2025D",
                "quantity_units": 3,
                "quantity_dispensed": 4,
                "quantity_returned": 3,
                "quantity_consumed": 1,
                "quantity_lost": 0,
                "action_date": now - timedelta(days=10),
                "performed_by": "Pharmacist Maria Santos",
                "verified_by": "CRA David Park",
                "storage_conditions_met": True,
                "temperature_excursion": False,
                "notes": "Subject non-compliant. Unused units returned.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "MAL-00000008",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D004",
                "site_id": "SITE-104",
                "accountability_action": AccountabilityAction.DESTROYED,
                "study_drug_name": "Dupilumab 300mg",
                "lot_number": "LOT-DUP-2025C",
                "quantity_units": 2,
                "quantity_dispensed": 0,
                "quantity_returned": 0,
                "quantity_consumed": 0,
                "quantity_lost": 0,
                "action_date": now - timedelta(days=3),
                "performed_by": "Pharmacist Maria Santos",
                "verified_by": "CRA David Park",
                "storage_conditions_met": True,
                "temperature_excursion": False,
                "notes": "Expired units destroyed per SOP.",
                "created_at": now - timedelta(days=3),
            },
            # LIBTAYO
            {
                "id": "MAL-00000009",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L001",
                "site_id": "SITE-105",
                "accountability_action": AccountabilityAction.DISPENSED,
                "study_drug_name": "Cemiplimab 350mg",
                "lot_number": "LOT-LIB-2025E",
                "quantity_units": 6,
                "quantity_dispensed": 6,
                "quantity_returned": 0,
                "quantity_consumed": 3,
                "quantity_lost": 0,
                "action_date": now - timedelta(days=63),
                "performed_by": "Pharmacist Robert Kim",
                "verified_by": "CRA Jennifer Lee",
                "storage_conditions_met": True,
                "temperature_excursion": False,
                "notes": "Initial supply for 3 infusion cycles.",
                "created_at": now - timedelta(days=63),
            },
            {
                "id": "MAL-00000010",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L002",
                "site_id": "SITE-105",
                "accountability_action": AccountabilityAction.TRANSFERRED,
                "study_drug_name": "Cemiplimab 350mg",
                "lot_number": "LOT-LIB-2025E",
                "quantity_units": 2,
                "quantity_dispensed": 0,
                "quantity_returned": 0,
                "quantity_consumed": 0,
                "quantity_lost": 0,
                "action_date": now - timedelta(days=35),
                "performed_by": "Pharmacist Robert Kim",
                "verified_by": "CRA Jennifer Lee",
                "storage_conditions_met": True,
                "temperature_excursion": False,
                "notes": "Transferred to SITE-106 due to supply shortage.",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "MAL-00000011",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L003",
                "site_id": "SITE-106",
                "accountability_action": AccountabilityAction.DISPENSED,
                "study_drug_name": "Cemiplimab 350mg",
                "lot_number": "LOT-LIB-2025F",
                "quantity_units": 4,
                "quantity_dispensed": 4,
                "quantity_returned": 0,
                "quantity_consumed": 3,
                "quantity_lost": 0,
                "action_date": now - timedelta(days=42),
                "performed_by": "Pharmacist Maria Santos",
                "verified_by": "CRA Sarah Mitchell",
                "storage_conditions_met": True,
                "temperature_excursion": False,
                "notes": None,
                "created_at": now - timedelta(days=42),
            },
            {
                "id": "MAL-00000012",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L004",
                "site_id": "SITE-106",
                "accountability_action": AccountabilityAction.LOST,
                "study_drug_name": "Cemiplimab 350mg",
                "lot_number": "LOT-LIB-2025F",
                "quantity_units": 1,
                "quantity_dispensed": 0,
                "quantity_returned": 0,
                "quantity_consumed": 0,
                "quantity_lost": 1,
                "action_date": now - timedelta(days=5),
                "performed_by": "Pharmacist Maria Santos",
                "verified_by": None,
                "storage_conditions_met": True,
                "temperature_excursion": False,
                "notes": "1 vial unaccounted for during reconciliation. Investigation initiated.",
                "created_at": now - timedelta(days=5),
            },
        ]

        for a in accountability_data:
            self._medication_accountability_logs[a["id"]] = MedicationAccountabilityLog(**a)

        # --- 12 Treatment Interruption Events (4 per trial) ---
        interruption_data = [
            # EYLEA
            {
                "id": "TIE-00000001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E003",
                "site_id": "SITE-102",
                "interruption_reason": InterruptionReason.PATIENT_REQUEST,
                "interruption_status": InterruptionStatus.RESOLVED,
                "study_drug_name": "Aflibercept 2mg",
                "interruption_date": now - timedelta(days=45),
                "expected_duration_days": 14,
                "actual_duration_days": 18,
                "dose_modification": None,
                "resumption_date": now - timedelta(days=27),
                "resumed_at_same_dose": True,
                "new_dose_amount": None,
                "reported_by": "Dr. David Park",
                "approved_by": "Medical Monitor Dr. Chen",
                "irb_notification_required": False,
                "sponsor_notified": True,
                "notes": "Patient requested break due to travel. Resumed at same dose.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "TIE-00000002",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E004",
                "site_id": "SITE-102",
                "interruption_reason": InterruptionReason.ADVERSE_EVENT,
                "interruption_status": InterruptionStatus.ACTIVE,
                "study_drug_name": "Aflibercept 2mg",
                "interruption_date": now - timedelta(days=10),
                "expected_duration_days": 21,
                "actual_duration_days": 10,
                "dose_modification": "Dose delay per protocol",
                "resumption_date": None,
                "resumed_at_same_dose": None,
                "new_dose_amount": None,
                "reported_by": "Dr. David Park",
                "approved_by": None,
                "irb_notification_required": False,
                "sponsor_notified": True,
                "notes": "Mild ocular inflammation. Monitoring before resumption.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "TIE-00000003",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E001",
                "site_id": "SITE-101",
                "interruption_reason": InterruptionReason.ADMINISTRATIVE,
                "interruption_status": InterruptionStatus.RESOLVED,
                "study_drug_name": "Aflibercept 2mg",
                "interruption_date": now - timedelta(days=75),
                "expected_duration_days": 7,
                "actual_duration_days": 5,
                "dose_modification": None,
                "resumption_date": now - timedelta(days=70),
                "resumed_at_same_dose": True,
                "new_dose_amount": None,
                "reported_by": "CRA Sarah Mitchell",
                "approved_by": "Medical Monitor Dr. Chen",
                "irb_notification_required": False,
                "sponsor_notified": False,
                "notes": "Site equipment maintenance. Brief delay.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "TIE-00000004",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E002",
                "site_id": "SITE-101",
                "interruption_reason": InterruptionReason.SUPPLY_ISSUE,
                "interruption_status": InterruptionStatus.RESOLVED,
                "study_drug_name": "Aflibercept 2mg",
                "interruption_date": now - timedelta(days=50),
                "expected_duration_days": 10,
                "actual_duration_days": 8,
                "dose_modification": None,
                "resumption_date": now - timedelta(days=42),
                "resumed_at_same_dose": True,
                "new_dose_amount": None,
                "reported_by": "Pharmacist Robert Kim",
                "approved_by": "Medical Monitor Dr. Chen",
                "irb_notification_required": False,
                "sponsor_notified": True,
                "notes": "Drug supply delayed in transit. Resolved with emergency shipment.",
                "created_at": now - timedelta(days=50),
            },
            # DUPIXENT
            {
                "id": "TIE-00000005",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D002",
                "site_id": "SITE-103",
                "interruption_reason": InterruptionReason.ADVERSE_EVENT,
                "interruption_status": InterruptionStatus.DOSE_MODIFIED,
                "study_drug_name": "Dupilumab 300mg",
                "interruption_date": now - timedelta(days=56),
                "expected_duration_days": 14,
                "actual_duration_days": 14,
                "dose_modification": "Reduced from 300mg to 200mg",
                "resumption_date": now - timedelta(days=42),
                "resumed_at_same_dose": False,
                "new_dose_amount": 200.0,
                "reported_by": "Dr. Jennifer Lee",
                "approved_by": "Medical Monitor Dr. Chen",
                "irb_notification_required": True,
                "sponsor_notified": True,
                "notes": "Injection site reaction led to dose reduction.",
                "created_at": now - timedelta(days=56),
            },
            {
                "id": "TIE-00000006",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D003",
                "site_id": "SITE-104",
                "interruption_reason": InterruptionReason.PATIENT_REQUEST,
                "interruption_status": InterruptionStatus.PERMANENT,
                "study_drug_name": "Dupilumab 300mg",
                "interruption_date": now - timedelta(days=28),
                "expected_duration_days": 0,
                "actual_duration_days": 28,
                "dose_modification": None,
                "resumption_date": None,
                "resumed_at_same_dose": None,
                "new_dose_amount": None,
                "reported_by": "Dr. David Park",
                "approved_by": "Medical Monitor Dr. Chen",
                "irb_notification_required": True,
                "sponsor_notified": True,
                "notes": "Patient withdrew from study due to injection anxiety.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "TIE-00000007",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D001",
                "site_id": "SITE-103",
                "interruption_reason": InterruptionReason.PROTOCOL_DEVIATION,
                "interruption_status": InterruptionStatus.RESOLVED,
                "study_drug_name": "Dupilumab 300mg",
                "interruption_date": now - timedelta(days=40),
                "expected_duration_days": 7,
                "actual_duration_days": 5,
                "dose_modification": None,
                "resumption_date": now - timedelta(days=35),
                "resumed_at_same_dose": True,
                "new_dose_amount": None,
                "reported_by": "CRA Jennifer Lee",
                "approved_by": "Medical Monitor Dr. Chen",
                "irb_notification_required": False,
                "sponsor_notified": True,
                "notes": "Dosing window exceeded. Protocol deviation documented.",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "TIE-00000008",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D004",
                "site_id": "SITE-104",
                "interruption_reason": InterruptionReason.INVESTIGATOR_DECISION,
                "interruption_status": InterruptionStatus.UNDER_REVIEW,
                "study_drug_name": "Dupilumab 300mg",
                "interruption_date": now - timedelta(days=5),
                "expected_duration_days": 14,
                "actual_duration_days": 5,
                "dose_modification": None,
                "resumption_date": None,
                "resumed_at_same_dose": None,
                "new_dose_amount": None,
                "reported_by": "Dr. David Park",
                "approved_by": None,
                "irb_notification_required": False,
                "sponsor_notified": True,
                "notes": "Lab values trending abnormal. Holding for recheck.",
                "created_at": now - timedelta(days=5),
            },
            # LIBTAYO
            {
                "id": "TIE-00000009",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L002",
                "site_id": "SITE-105",
                "interruption_reason": InterruptionReason.ADVERSE_EVENT,
                "interruption_status": InterruptionStatus.ACTIVE,
                "study_drug_name": "Cemiplimab 350mg",
                "interruption_date": now - timedelta(days=42),
                "expected_duration_days": 28,
                "actual_duration_days": 42,
                "dose_modification": "Dose held pending toxicity resolution",
                "resumption_date": None,
                "resumed_at_same_dose": None,
                "new_dose_amount": None,
                "reported_by": "Dr. Jennifer Lee",
                "approved_by": "Medical Monitor Dr. Chen",
                "irb_notification_required": True,
                "sponsor_notified": True,
                "notes": "Grade 2 hepatotoxicity. ALT 3x ULN. Monitoring biweekly.",
                "created_at": now - timedelta(days=42),
            },
            {
                "id": "TIE-00000010",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L001",
                "site_id": "SITE-105",
                "interruption_reason": InterruptionReason.SUPPLY_ISSUE,
                "interruption_status": InterruptionStatus.RESOLVED,
                "study_drug_name": "Cemiplimab 350mg",
                "interruption_date": now - timedelta(days=35),
                "expected_duration_days": 7,
                "actual_duration_days": 5,
                "dose_modification": None,
                "resumption_date": now - timedelta(days=30),
                "resumed_at_same_dose": True,
                "new_dose_amount": None,
                "reported_by": "Pharmacist Robert Kim",
                "approved_by": "Medical Monitor Dr. Chen",
                "irb_notification_required": False,
                "sponsor_notified": True,
                "notes": "Supply transfer from SITE-106 resolved shortage.",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "TIE-00000011",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L003",
                "site_id": "SITE-106",
                "interruption_reason": InterruptionReason.ADMINISTRATIVE,
                "interruption_status": InterruptionStatus.RESOLVED,
                "study_drug_name": "Cemiplimab 350mg",
                "interruption_date": now - timedelta(days=28),
                "expected_duration_days": 3,
                "actual_duration_days": 2,
                "dose_modification": None,
                "resumption_date": now - timedelta(days=26),
                "resumed_at_same_dose": True,
                "new_dose_amount": None,
                "reported_by": "CRA Sarah Mitchell",
                "approved_by": None,
                "irb_notification_required": False,
                "sponsor_notified": False,
                "notes": "Infusion suite scheduling conflict. Resolved quickly.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "TIE-00000012",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L004",
                "site_id": "SITE-106",
                "interruption_reason": InterruptionReason.INVESTIGATOR_DECISION,
                "interruption_status": InterruptionStatus.TREATMENT_DISCONTINUED,
                "study_drug_name": "Cemiplimab 350mg",
                "interruption_date": now - timedelta(days=2),
                "expected_duration_days": 0,
                "actual_duration_days": 2,
                "dose_modification": None,
                "resumption_date": None,
                "resumed_at_same_dose": None,
                "new_dose_amount": None,
                "reported_by": "Dr. Sarah Mitchell",
                "approved_by": "Medical Monitor Dr. Chen",
                "irb_notification_required": True,
                "sponsor_notified": True,
                "notes": "Disease progression. Treatment discontinued per investigator decision.",
                "created_at": now - timedelta(days=2),
            },
        ]

        for ie in interruption_data:
            self._treatment_interruption_events[ie["id"]] = TreatmentInterruptionEvent(**ie)

    # ------------------------------------------------------------------
    # Dosing Records
    # ------------------------------------------------------------------

    def list_dosing_records(self, *, trial_id: str | None = None) -> list[DosingRecord]:
        """List dosing records with optional trial_id filter."""
        with self._lock:
            result = list(self._dosing_records.values())
        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        return sorted(result, key=lambda r: r.scheduled_date, reverse=True)

    def get_dosing_record(self, record_id: str) -> DosingRecord | None:
        """Get a single dosing record by ID."""
        with self._lock:
            return self._dosing_records.get(record_id)

    def create_dosing_record(self, payload: DosingRecordCreate) -> DosingRecord:
        """Create a new dosing record."""
        now = datetime.now(timezone.utc)
        record_id = f"DOS-{uuid4().hex[:8].upper()}"
        record = DosingRecord(
            id=record_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            site_id=payload.site_id,
            dosing_status=payload.dosing_status,
            study_drug_name=payload.study_drug_name,
            dose_amount=payload.dose_amount,
            dose_unit=payload.dose_unit,
            route_of_administration=payload.route_of_administration,
            scheduled_date=payload.scheduled_date,
            created_at=now,
        )
        with self._lock:
            self._dosing_records[record_id] = record
        logger.info("Created dosing record %s for subject %s", record_id, payload.subject_id)
        return record

    def update_dosing_record(self, record_id: str, payload: DosingRecordUpdate) -> DosingRecord | None:
        """Update an existing dosing record."""
        with self._lock:
            existing = self._dosing_records.get(record_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DosingRecord(**data)
            self._dosing_records[record_id] = updated
        return updated

    def delete_dosing_record(self, record_id: str) -> bool:
        """Delete a dosing record. Returns True if deleted, False if not found."""
        with self._lock:
            if record_id in self._dosing_records:
                del self._dosing_records[record_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Compliance Assessments
    # ------------------------------------------------------------------

    def list_compliance_assessments(self, *, trial_id: str | None = None) -> list[ComplianceAssessment]:
        """List compliance assessments with optional trial_id filter."""
        with self._lock:
            result = list(self._compliance_assessments.values())
        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        return sorted(result, key=lambda a: a.assessment_date, reverse=True)

    def get_compliance_assessment(self, assessment_id: str) -> ComplianceAssessment | None:
        """Get a single compliance assessment by ID."""
        with self._lock:
            return self._compliance_assessments.get(assessment_id)

    def create_compliance_assessment(self, payload: ComplianceAssessmentCreate) -> ComplianceAssessment:
        """Create a new compliance assessment."""
        now = datetime.now(timezone.utc)
        assessment_id = f"CAS-{uuid4().hex[:8].upper()}"
        assessment = ComplianceAssessment(
            id=assessment_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            site_id=payload.site_id,
            compliance_level=payload.compliance_level,
            assessment_date=payload.assessment_date,
            assessment_period_start=payload.assessment_period_start,
            assessment_period_end=payload.assessment_period_end,
            assessment_method=payload.assessment_method,
            assessed_by=payload.assessed_by,
            created_at=now,
        )
        with self._lock:
            self._compliance_assessments[assessment_id] = assessment
        logger.info("Created compliance assessment %s for subject %s", assessment_id, payload.subject_id)
        return assessment

    def update_compliance_assessment(self, assessment_id: str, payload: ComplianceAssessmentUpdate) -> ComplianceAssessment | None:
        """Update an existing compliance assessment."""
        with self._lock:
            existing = self._compliance_assessments.get(assessment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ComplianceAssessment(**data)
            self._compliance_assessments[assessment_id] = updated
        return updated

    def delete_compliance_assessment(self, assessment_id: str) -> bool:
        """Delete a compliance assessment. Returns True if deleted, False if not found."""
        with self._lock:
            if assessment_id in self._compliance_assessments:
                del self._compliance_assessments[assessment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Medication Accountability Logs
    # ------------------------------------------------------------------

    def list_medication_accountability_logs(self, *, trial_id: str | None = None) -> list[MedicationAccountabilityLog]:
        """List medication accountability logs with optional trial_id filter."""
        with self._lock:
            result = list(self._medication_accountability_logs.values())
        if trial_id is not None:
            result = [l for l in result if l.trial_id == trial_id]
        return sorted(result, key=lambda l: l.action_date, reverse=True)

    def get_medication_accountability_log(self, log_id: str) -> MedicationAccountabilityLog | None:
        """Get a single medication accountability log by ID."""
        with self._lock:
            return self._medication_accountability_logs.get(log_id)

    def create_medication_accountability_log(self, payload: MedicationAccountabilityLogCreate) -> MedicationAccountabilityLog:
        """Create a new medication accountability log."""
        now = datetime.now(timezone.utc)
        log_id = f"MAL-{uuid4().hex[:8].upper()}"
        log = MedicationAccountabilityLog(
            id=log_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            site_id=payload.site_id,
            accountability_action=payload.accountability_action,
            study_drug_name=payload.study_drug_name,
            lot_number=payload.lot_number,
            quantity_units=payload.quantity_units,
            action_date=payload.action_date,
            performed_by=payload.performed_by,
            created_at=now,
        )
        with self._lock:
            self._medication_accountability_logs[log_id] = log
        logger.info("Created medication accountability log %s", log_id)
        return log

    def update_medication_accountability_log(self, log_id: str, payload: MedicationAccountabilityLogUpdate) -> MedicationAccountabilityLog | None:
        """Update an existing medication accountability log."""
        with self._lock:
            existing = self._medication_accountability_logs.get(log_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = MedicationAccountabilityLog(**data)
            self._medication_accountability_logs[log_id] = updated
        return updated

    def delete_medication_accountability_log(self, log_id: str) -> bool:
        """Delete a medication accountability log. Returns True if deleted, False if not found."""
        with self._lock:
            if log_id in self._medication_accountability_logs:
                del self._medication_accountability_logs[log_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Treatment Interruption Events
    # ------------------------------------------------------------------

    def list_treatment_interruption_events(self, *, trial_id: str | None = None) -> list[TreatmentInterruptionEvent]:
        """List treatment interruption events with optional trial_id filter."""
        with self._lock:
            result = list(self._treatment_interruption_events.values())
        if trial_id is not None:
            result = [e for e in result if e.trial_id == trial_id]
        return sorted(result, key=lambda e: e.interruption_date, reverse=True)

    def get_treatment_interruption_event(self, event_id: str) -> TreatmentInterruptionEvent | None:
        """Get a single treatment interruption event by ID."""
        with self._lock:
            return self._treatment_interruption_events.get(event_id)

    def create_treatment_interruption_event(self, payload: TreatmentInterruptionEventCreate) -> TreatmentInterruptionEvent:
        """Create a new treatment interruption event."""
        now = datetime.now(timezone.utc)
        event_id = f"TIE-{uuid4().hex[:8].upper()}"
        event = TreatmentInterruptionEvent(
            id=event_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            site_id=payload.site_id,
            interruption_reason=payload.interruption_reason,
            interruption_status=payload.interruption_status,
            study_drug_name=payload.study_drug_name,
            interruption_date=payload.interruption_date,
            reported_by=payload.reported_by,
            created_at=now,
        )
        with self._lock:
            self._treatment_interruption_events[event_id] = event
        logger.info("Created treatment interruption event %s", event_id)
        return event

    def update_treatment_interruption_event(self, event_id: str, payload: TreatmentInterruptionEventUpdate) -> TreatmentInterruptionEvent | None:
        """Update an existing treatment interruption event."""
        with self._lock:
            existing = self._treatment_interruption_events.get(event_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = TreatmentInterruptionEvent(**data)
            self._treatment_interruption_events[event_id] = updated
        return updated

    def delete_treatment_interruption_event(self, event_id: str) -> bool:
        """Delete a treatment interruption event. Returns True if deleted, False if not found."""
        with self._lock:
            if event_id in self._treatment_interruption_events:
                del self._treatment_interruption_events[event_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, *, trial_id: str | None = None) -> TreatmentComplianceMetrics:
        """Compute aggregated treatment compliance metrics."""
        with self._lock:
            dosing = list(self._dosing_records.values())
            assessments = list(self._compliance_assessments.values())
            logs = list(self._medication_accountability_logs.values())
            interruptions = list(self._treatment_interruption_events.values())

        if trial_id is not None:
            dosing = [r for r in dosing if r.trial_id == trial_id]
            assessments = [a for a in assessments if a.trial_id == trial_id]
            logs = [l for l in logs if l.trial_id == trial_id]
            interruptions = [e for e in interruptions if e.trial_id == trial_id]

        # Dosing records by status
        records_by_status: dict[str, int] = {}
        for r in dosing:
            key = r.dosing_status.value
            records_by_status[key] = records_by_status.get(key, 0) + 1

        # Compliance assessments by level
        assessments_by_level: dict[str, int] = {}
        for a in assessments:
            key = a.compliance_level.value
            assessments_by_level[key] = assessments_by_level.get(key, 0) + 1

        # Average compliance percentage
        if assessments:
            avg_compliance = round(
                sum(a.compliance_percentage for a in assessments) / len(assessments), 1
            )
        else:
            avg_compliance = 0.0

        # Accountability logs by action
        logs_by_action: dict[str, int] = {}
        for l in logs:
            key = l.accountability_action.value
            logs_by_action[key] = logs_by_action.get(key, 0) + 1

        # Interruptions by reason
        interruptions_by_reason: dict[str, int] = {}
        for e in interruptions:
            key = e.interruption_reason.value
            interruptions_by_reason[key] = interruptions_by_reason.get(key, 0) + 1

        # Interruptions by status
        interruptions_by_status: dict[str, int] = {}
        for e in interruptions:
            key = e.interruption_status.value
            interruptions_by_status[key] = interruptions_by_status.get(key, 0) + 1

        # Average interruption duration
        if interruptions:
            avg_duration = round(
                sum(e.actual_duration_days for e in interruptions) / len(interruptions), 1
            )
        else:
            avg_duration = 0.0

        return TreatmentComplianceMetrics(
            total_dosing_records=len(dosing),
            records_by_status=records_by_status,
            total_compliance_assessments=len(assessments),
            assessments_by_level=assessments_by_level,
            avg_compliance_percentage=avg_compliance,
            total_accountability_logs=len(logs),
            logs_by_action=logs_by_action,
            total_interruptions=len(interruptions),
            interruptions_by_reason=interruptions_by_reason,
            interruptions_by_status=interruptions_by_status,
            avg_interruption_duration_days=avg_duration,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: TreatmentComplianceMonitoringService | None = None
_instance_lock = threading.Lock()


def get_treatment_compliance_monitoring_service() -> TreatmentComplianceMonitoringService:
    """Return the singleton TreatmentComplianceMonitoringService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = TreatmentComplianceMonitoringService()
    return _instance


def reset_treatment_compliance_monitoring_service() -> TreatmentComplianceMonitoringService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = TreatmentComplianceMonitoringService()
    return _instance
