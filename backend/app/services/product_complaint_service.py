"""Product Complaint Management Service (PROD-COMPL).

Manages product complaint operations: complaint intake, investigation
tracking, root cause analysis, CAPA linkage, and regulatory reporting
with complaint metrics.

Usage:
    from app.services.product_complaint_service import (
        get_product_complaint_service,
    )

    svc = get_product_complaint_service()
    complaints = svc.list_complaint_intakes()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.product_complaint import (
    CAPALinkage,
    CAPALinkageCreate,
    CAPALinkageUpdate,
    ComplaintCategory,
    ComplaintIntake,
    ComplaintIntakeCreate,
    ComplaintIntakeUpdate,
    ComplaintSeverity,
    ComplaintStatus,
    InvestigationOutcome,
    InvestigationRecord,
    InvestigationRecordCreate,
    InvestigationRecordUpdate,
    ProductComplaintMetrics,
    RegulatoryReport,
    RegulatoryReportCreate,
    RegulatoryReportUpdate,
    RootCauseAnalysis,
    RootCauseAnalysisCreate,
    RootCauseAnalysisUpdate,
    RootCauseCategory,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class ProductComplaintService:
    """In-memory Product Complaint Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._complaint_intakes: dict[str, ComplaintIntake] = {}
        self._investigation_records: dict[str, InvestigationRecord] = {}
        self._root_cause_analyses: dict[str, RootCauseAnalysis] = {}
        self._capa_linkages: dict[str, CAPALinkage] = {}
        self._regulatory_reports: dict[str, RegulatoryReport] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic product complaint data."""
        now = datetime.now(timezone.utc)

        # --- 12 Complaint Intakes ---
        intakes_data = [
            {
                "id": "CI-001",
                "trial_id": EYLEA_TRIAL,
                "complaint_number": "COMPL-2025-0001",
                "category": ComplaintCategory.PRODUCT_QUALITY,
                "severity": ComplaintSeverity.MODERATE,
                "status": ComplaintStatus.RESOLVED,
                "product_name": "EYLEA 2mg/0.05mL",
                "batch_number": "EYL-B2024-1001",
                "complaint_date": now - timedelta(days=180),
                "reporter_name": "Dr. Sarah Chen",
                "reporter_type": "investigator",
                "site_id": "SITE-101",
                "subject_id": "SUBJ-1001",
                "description": "Particulate matter observed in pre-filled syringe prior to administration. Product withheld from use.",
                "patient_impact": False,
                "sample_available": True,
                "sample_received": True,
                "initial_assessment": "Visible particles in solution. Retained for lab analysis.",
                "days_open": 45,
                "received_by": "QA Specialist Janet Morris",
                "notes": "Complaint resolved after investigation confirmed isolated manufacturing defect.",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "CI-002",
                "trial_id": EYLEA_TRIAL,
                "complaint_number": "COMPL-2025-0002",
                "category": ComplaintCategory.PACKAGING,
                "severity": ComplaintSeverity.MINOR,
                "status": ComplaintStatus.CLOSED,
                "product_name": "EYLEA 2mg/0.05mL",
                "batch_number": "EYL-B2024-1002",
                "complaint_date": now - timedelta(days=160),
                "reporter_name": "Nurse Patricia Walsh",
                "reporter_type": "site_staff",
                "site_id": "SITE-102",
                "subject_id": None,
                "description": "Outer carton label partially detached upon receipt. Product integrity not affected.",
                "patient_impact": False,
                "sample_available": True,
                "sample_received": True,
                "initial_assessment": "Packaging adhesive failure. Product quality unaffected.",
                "days_open": 14,
                "received_by": "QA Specialist Janet Morris",
                "notes": "Closed after corrective action issued to packaging vendor.",
                "created_at": now - timedelta(days=160),
            },
            {
                "id": "CI-003",
                "trial_id": EYLEA_TRIAL,
                "complaint_number": "COMPL-2025-0003",
                "category": ComplaintCategory.DEVICE_MALFUNCTION,
                "severity": ComplaintSeverity.MAJOR,
                "status": ComplaintStatus.UNDER_INVESTIGATION,
                "product_name": "EYLEA 2mg/0.05mL Pre-filled Syringe",
                "batch_number": "EYL-B2024-1003",
                "complaint_date": now - timedelta(days=45),
                "reporter_name": "Dr. James Wright",
                "reporter_type": "investigator",
                "site_id": "SITE-103",
                "subject_id": "SUBJ-1042",
                "description": "Pre-filled syringe plunger rod stuck during injection attempt. Full dose not delivered to patient.",
                "patient_impact": True,
                "sample_available": True,
                "sample_received": True,
                "initial_assessment": "Device malfunction with partial dose delivery. Patient monitored for 48h, no adverse effects.",
                "days_open": 45,
                "received_by": "QA Manager Robert Kim",
                "notes": "Investigation ongoing. Similar complaints being tracked.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "CI-004",
                "trial_id": EYLEA_TRIAL,
                "complaint_number": "COMPL-2025-0004",
                "category": ComplaintCategory.ADVERSE_EVENT,
                "severity": ComplaintSeverity.CRITICAL,
                "status": ComplaintStatus.ROOT_CAUSE_IDENTIFIED,
                "product_name": "EYLEA 2mg/0.05mL",
                "batch_number": "EYL-B2024-1004",
                "complaint_date": now - timedelta(days=90),
                "reporter_name": "Dr. Maria Lopez",
                "reporter_type": "investigator",
                "site_id": "SITE-104",
                "subject_id": "SUBJ-1088",
                "description": "Severe ocular inflammation 24 hours post-injection. Suspected product contamination.",
                "patient_impact": True,
                "sample_available": True,
                "sample_received": True,
                "initial_assessment": "Serious AE with possible product quality nexus. Expedited investigation initiated.",
                "days_open": 90,
                "received_by": "QA Manager Robert Kim",
                "notes": "Root cause identified as endotoxin contamination in specific batch.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "CI-005",
                "trial_id": DUPIXENT_TRIAL,
                "complaint_number": "COMPL-2025-0005",
                "category": ComplaintCategory.LABELING,
                "severity": ComplaintSeverity.MODERATE,
                "status": ComplaintStatus.RESOLVED,
                "product_name": "DUPIXENT 300mg/2mL",
                "batch_number": "DUP-B2024-2001",
                "complaint_date": now - timedelta(days=120),
                "reporter_name": "Pharmacist Thomas Green",
                "reporter_type": "pharmacist",
                "site_id": "SITE-201",
                "subject_id": None,
                "description": "Expiry date printed incorrectly on secondary packaging. Actual expiry confirmed via batch records.",
                "patient_impact": False,
                "sample_available": True,
                "sample_received": True,
                "initial_assessment": "Labeling error affecting expiry date. Batch records confirm correct expiry.",
                "days_open": 30,
                "received_by": "QA Specialist Angela Park",
                "notes": "Resolved. All affected units recalled from sites. CAPA issued.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "CI-006",
                "trial_id": DUPIXENT_TRIAL,
                "complaint_number": "COMPL-2025-0006",
                "category": ComplaintCategory.PRODUCT_QUALITY,
                "severity": ComplaintSeverity.MAJOR,
                "status": ComplaintStatus.UNDER_INVESTIGATION,
                "product_name": "DUPIXENT 300mg/2mL",
                "batch_number": "DUP-B2024-2002",
                "complaint_date": now - timedelta(days=30),
                "reporter_name": "Dr. David Patel",
                "reporter_type": "investigator",
                "site_id": "SITE-202",
                "subject_id": "SUBJ-2015",
                "description": "Solution appears turbid and discolored upon visual inspection. Product not administered.",
                "patient_impact": False,
                "sample_available": True,
                "sample_received": False,
                "initial_assessment": "Potential aggregation or degradation. Sample requested for analysis.",
                "days_open": 30,
                "received_by": "QA Specialist Angela Park",
                "notes": "Awaiting sample receipt for laboratory analysis.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "CI-007",
                "trial_id": DUPIXENT_TRIAL,
                "complaint_number": "COMPL-2025-0007",
                "category": ComplaintCategory.PACKAGING,
                "severity": ComplaintSeverity.MINOR,
                "status": ComplaintStatus.ACKNOWLEDGED,
                "product_name": "DUPIXENT 200mg/1.14mL Pen",
                "batch_number": "DUP-B2024-2003",
                "complaint_date": now - timedelta(days=15),
                "reporter_name": "Site Coordinator Lisa Nguyen",
                "reporter_type": "site_staff",
                "site_id": "SITE-203",
                "subject_id": None,
                "description": "Blister pack seal appears weakened on 3 of 12 units received. No damage to pens observed.",
                "patient_impact": False,
                "sample_available": True,
                "sample_received": False,
                "initial_assessment": "Minor packaging integrity concern. Visual inspection suggests no product impact.",
                "days_open": 15,
                "received_by": "QA Specialist Angela Park",
                "notes": None,
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "CI-008",
                "trial_id": DUPIXENT_TRIAL,
                "complaint_number": "COMPL-2025-0008",
                "category": ComplaintCategory.COUNTERFEIT,
                "severity": ComplaintSeverity.LIFE_THREATENING,
                "status": ComplaintStatus.UNDER_INVESTIGATION,
                "product_name": "DUPIXENT 300mg/2mL",
                "batch_number": "DUP-UNKNOWN-001",
                "complaint_date": now - timedelta(days=10),
                "reporter_name": "Dr. William Torres",
                "reporter_type": "investigator",
                "site_id": "SITE-204",
                "subject_id": None,
                "description": "Suspected counterfeit product received. Holographic security feature missing from label. Serialization code unverifiable.",
                "patient_impact": False,
                "sample_available": True,
                "sample_received": True,
                "initial_assessment": "High-priority counterfeit investigation. Product quarantined. Supply chain review initiated.",
                "days_open": 10,
                "received_by": "QA Manager Robert Kim",
                "notes": "Law enforcement notification under consideration.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "CI-009",
                "trial_id": LIBTAYO_TRIAL,
                "complaint_number": "COMPL-2025-0009",
                "category": ComplaintCategory.PRODUCT_QUALITY,
                "severity": ComplaintSeverity.MODERATE,
                "status": ComplaintStatus.RESOLVED,
                "product_name": "LIBTAYO 350mg/7mL",
                "batch_number": "LIB-B2024-3001",
                "complaint_date": now - timedelta(days=150),
                "reporter_name": "Dr. Angela Park",
                "reporter_type": "investigator",
                "site_id": "SITE-301",
                "subject_id": "SUBJ-3005",
                "description": "Vial stopper loose upon receipt. Sterility potentially compromised.",
                "patient_impact": False,
                "sample_available": True,
                "sample_received": True,
                "initial_assessment": "Stopper integrity failure. Product not used. Replacement vial sent.",
                "days_open": 28,
                "received_by": "QA Specialist Janet Morris",
                "notes": "Resolved. Manufacturing review identified torque specification issue.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "CI-010",
                "trial_id": LIBTAYO_TRIAL,
                "complaint_number": "COMPL-2025-0010",
                "category": ComplaintCategory.DEVICE_MALFUNCTION,
                "severity": ComplaintSeverity.MODERATE,
                "status": ComplaintStatus.RECEIVED,
                "product_name": "LIBTAYO 350mg/7mL IV Infusion Set",
                "batch_number": "LIB-B2024-3002",
                "complaint_date": now - timedelta(days=5),
                "reporter_name": "Nurse Michael Brown",
                "reporter_type": "site_staff",
                "site_id": "SITE-302",
                "subject_id": "SUBJ-3022",
                "description": "IV infusion line filter clogged within first 10 minutes of administration. Infusion interrupted.",
                "patient_impact": True,
                "sample_available": True,
                "sample_received": False,
                "initial_assessment": "Pending initial review.",
                "days_open": 5,
                "received_by": "QA Specialist Janet Morris",
                "notes": None,
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "CI-011",
                "trial_id": LIBTAYO_TRIAL,
                "complaint_number": "COMPL-2025-0011",
                "category": ComplaintCategory.LABELING,
                "severity": ComplaintSeverity.MINOR,
                "status": ComplaintStatus.CLOSED,
                "product_name": "LIBTAYO 350mg/7mL",
                "batch_number": "LIB-B2024-3003",
                "complaint_date": now - timedelta(days=200),
                "reporter_name": "Pharmacist Karen Lee",
                "reporter_type": "pharmacist",
                "site_id": "SITE-303",
                "subject_id": None,
                "description": "Storage temperature range on carton label differs from IB specification. Label shows 2-8C, IB states 2-25C for short-term.",
                "patient_impact": False,
                "sample_available": False,
                "sample_received": False,
                "initial_assessment": "Labeling discrepancy. IB is correct. Label reflects long-term storage only.",
                "days_open": 7,
                "received_by": "QA Specialist Angela Park",
                "notes": "Closed. Label is technically correct for long-term storage. Clarification sent to site.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "CI-012",
                "trial_id": LIBTAYO_TRIAL,
                "complaint_number": "COMPL-2025-0012",
                "category": ComplaintCategory.ADVERSE_EVENT,
                "severity": ComplaintSeverity.CRITICAL,
                "status": ComplaintStatus.UNDER_INVESTIGATION,
                "product_name": "LIBTAYO 350mg/7mL",
                "batch_number": "LIB-B2024-3004",
                "complaint_date": now - timedelta(days=20),
                "reporter_name": "Dr. Angela Park",
                "reporter_type": "investigator",
                "site_id": "SITE-301",
                "subject_id": "SUBJ-3031",
                "description": "Grade 3 infusion-related reaction within 5 minutes of start. Suspected product quality issue after 2 similar events with same batch.",
                "patient_impact": True,
                "sample_available": True,
                "sample_received": True,
                "initial_assessment": "Cluster of infusion reactions from single batch. Urgent batch review initiated.",
                "days_open": 20,
                "received_by": "QA Manager Robert Kim",
                "notes": "Third event from batch LIB-B2024-3004. Batch hold placed.",
                "created_at": now - timedelta(days=20),
            },
        ]

        for c in intakes_data:
            self._complaint_intakes[c["id"]] = ComplaintIntake(**c)

        # --- 10 Investigation Records ---
        investigations_data = [
            {
                "id": "INV-001",
                "trial_id": EYLEA_TRIAL,
                "complaint_id": "CI-001",
                "investigation_start_date": now - timedelta(days=178),
                "investigation_end_date": now - timedelta(days=135),
                "investigator": "QA Investigator Mark Stevens",
                "outcome": InvestigationOutcome.CONFIRMED,
                "testing_performed": ["visual_inspection", "particulate_count", "subvisible_particle_analysis"],
                "test_results_summary": "USP <788> testing confirmed particle count above specification. Identified as silicone oil droplets from syringe barrel.",
                "manufacturing_review": True,
                "distribution_review": False,
                "trend_analysis_performed": True,
                "similar_complaints_found": 2,
                "product_retained": True,
                "field_alert_considered": False,
                "recall_considered": False,
                "reviewed_by": "QA Manager Robert Kim",
                "notes": "Root cause: silicone oil siliconization process deviation in batch.",
                "created_at": now - timedelta(days=178),
            },
            {
                "id": "INV-002",
                "trial_id": EYLEA_TRIAL,
                "complaint_id": "CI-002",
                "investigation_start_date": now - timedelta(days=158),
                "investigation_end_date": now - timedelta(days=146),
                "investigator": "QA Investigator Lisa Chen",
                "outcome": InvestigationOutcome.CONFIRMED,
                "testing_performed": ["adhesive_testing", "environmental_simulation"],
                "test_results_summary": "Adhesive bond strength below specification at high humidity. Vendor raw material change identified.",
                "manufacturing_review": False,
                "distribution_review": True,
                "trend_analysis_performed": True,
                "similar_complaints_found": 5,
                "product_retained": True,
                "field_alert_considered": False,
                "recall_considered": False,
                "reviewed_by": "QA Manager Robert Kim",
                "notes": "Packaging vendor corrective action confirmed.",
                "created_at": now - timedelta(days=158),
            },
            {
                "id": "INV-003",
                "trial_id": EYLEA_TRIAL,
                "complaint_id": "CI-003",
                "investigation_start_date": now - timedelta(days=43),
                "investigation_end_date": None,
                "investigator": "QA Investigator Mark Stevens",
                "outcome": None,
                "testing_performed": ["plunger_force_testing", "dimensional_analysis", "lubrication_assessment"],
                "test_results_summary": "Preliminary results show increased plunger breakout force. Full analysis pending.",
                "manufacturing_review": True,
                "distribution_review": False,
                "trend_analysis_performed": True,
                "similar_complaints_found": 3,
                "product_retained": True,
                "field_alert_considered": True,
                "recall_considered": False,
                "reviewed_by": None,
                "notes": "Investigation ongoing. Expedited timeline due to patient impact.",
                "created_at": now - timedelta(days=43),
            },
            {
                "id": "INV-004",
                "trial_id": EYLEA_TRIAL,
                "complaint_id": "CI-004",
                "investigation_start_date": now - timedelta(days=88),
                "investigation_end_date": now - timedelta(days=50),
                "investigator": "QA Senior Investigator Dr. Helen Park",
                "outcome": InvestigationOutcome.CONFIRMED,
                "testing_performed": ["endotoxin_testing", "sterility_testing", "environmental_monitoring_review", "process_deviation_review"],
                "test_results_summary": "Endotoxin levels 3x above specification. Environmental monitoring showed excursion in filling area during batch production.",
                "manufacturing_review": True,
                "distribution_review": False,
                "trend_analysis_performed": True,
                "similar_complaints_found": 1,
                "product_retained": True,
                "field_alert_considered": True,
                "recall_considered": True,
                "reviewed_by": "VP Quality Dr. William Torres",
                "notes": "Serious quality event. Batch recall initiated. Regulatory notification filed.",
                "created_at": now - timedelta(days=88),
            },
            {
                "id": "INV-005",
                "trial_id": DUPIXENT_TRIAL,
                "complaint_id": "CI-005",
                "investigation_start_date": now - timedelta(days=118),
                "investigation_end_date": now - timedelta(days=90),
                "investigator": "QA Investigator Lisa Chen",
                "outcome": InvestigationOutcome.CONFIRMED,
                "testing_performed": ["label_verification", "print_batch_review", "artwork_review"],
                "test_results_summary": "Print run used incorrect artwork version. Human error in artwork selection at print vendor.",
                "manufacturing_review": False,
                "distribution_review": True,
                "trend_analysis_performed": True,
                "similar_complaints_found": 0,
                "product_retained": False,
                "field_alert_considered": False,
                "recall_considered": True,
                "reviewed_by": "QA Manager Robert Kim",
                "notes": "All affected units identified and recalled from 3 sites.",
                "created_at": now - timedelta(days=118),
            },
            {
                "id": "INV-006",
                "trial_id": DUPIXENT_TRIAL,
                "complaint_id": "CI-006",
                "investigation_start_date": now - timedelta(days=28),
                "investigation_end_date": None,
                "investigator": "QA Investigator Mark Stevens",
                "outcome": None,
                "testing_performed": ["visual_inspection", "turbidity_measurement"],
                "test_results_summary": "Pending full laboratory analysis upon sample receipt.",
                "manufacturing_review": False,
                "distribution_review": False,
                "trend_analysis_performed": False,
                "similar_complaints_found": 0,
                "product_retained": False,
                "field_alert_considered": False,
                "recall_considered": False,
                "reviewed_by": None,
                "notes": "Awaiting sample. Site contacted for expedited shipment.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "INV-007",
                "trial_id": DUPIXENT_TRIAL,
                "complaint_id": "CI-008",
                "investigation_start_date": now - timedelta(days=9),
                "investigation_end_date": None,
                "investigator": "QA Senior Investigator Dr. Helen Park",
                "outcome": None,
                "testing_performed": ["serialization_verification", "holographic_analysis", "chemical_fingerprinting"],
                "test_results_summary": "Preliminary chemical fingerprinting shows differences from reference standard. Full analysis in progress.",
                "manufacturing_review": True,
                "distribution_review": True,
                "trend_analysis_performed": True,
                "similar_complaints_found": 0,
                "product_retained": True,
                "field_alert_considered": True,
                "recall_considered": True,
                "reviewed_by": None,
                "notes": "High-priority investigation. Supply chain audit initiated at all distribution points.",
                "created_at": now - timedelta(days=9),
            },
            {
                "id": "INV-008",
                "trial_id": LIBTAYO_TRIAL,
                "complaint_id": "CI-009",
                "investigation_start_date": now - timedelta(days=148),
                "investigation_end_date": now - timedelta(days=122),
                "investigator": "QA Investigator Lisa Chen",
                "outcome": InvestigationOutcome.CONFIRMED,
                "testing_performed": ["stopper_integrity_testing", "torque_measurement", "container_closure_integrity"],
                "test_results_summary": "Capping machine torque setting drifted below specification. Stopper not fully seated.",
                "manufacturing_review": True,
                "distribution_review": False,
                "trend_analysis_performed": True,
                "similar_complaints_found": 1,
                "product_retained": True,
                "field_alert_considered": False,
                "recall_considered": False,
                "reviewed_by": "QA Manager Robert Kim",
                "notes": "Manufacturing corrective action implemented. Torque monitoring frequency increased.",
                "created_at": now - timedelta(days=148),
            },
            {
                "id": "INV-009",
                "trial_id": LIBTAYO_TRIAL,
                "complaint_id": "CI-012",
                "investigation_start_date": now - timedelta(days=18),
                "investigation_end_date": None,
                "investigator": "QA Senior Investigator Dr. Helen Park",
                "outcome": None,
                "testing_performed": ["potency_testing", "aggregation_analysis", "endotoxin_testing", "host_cell_protein_analysis"],
                "test_results_summary": "Elevated aggregate levels detected. Full characterization in progress.",
                "manufacturing_review": True,
                "distribution_review": True,
                "trend_analysis_performed": True,
                "similar_complaints_found": 2,
                "product_retained": True,
                "field_alert_considered": True,
                "recall_considered": True,
                "reviewed_by": None,
                "notes": "Urgent investigation. Batch hold in place. 3 infusion reactions from same batch.",
                "created_at": now - timedelta(days=18),
            },
            {
                "id": "INV-010",
                "trial_id": LIBTAYO_TRIAL,
                "complaint_id": "CI-011",
                "investigation_start_date": now - timedelta(days=198),
                "investigation_end_date": now - timedelta(days=193),
                "investigator": "QA Investigator Lisa Chen",
                "outcome": InvestigationOutcome.NOT_CONFIRMED,
                "testing_performed": ["label_review", "ib_cross_reference"],
                "test_results_summary": "Label is correct per approved artwork. IB contains additional short-term storage allowance not on label.",
                "manufacturing_review": False,
                "distribution_review": False,
                "trend_analysis_performed": False,
                "similar_complaints_found": 0,
                "product_retained": False,
                "field_alert_considered": False,
                "recall_considered": False,
                "reviewed_by": "QA Specialist Angela Park",
                "notes": "No defect. Clarification letter sent to reporting site.",
                "created_at": now - timedelta(days=198),
            },
        ]

        for inv in investigations_data:
            self._investigation_records[inv["id"]] = InvestigationRecord(**inv)

        # --- 10 Root Cause Analyses ---
        rca_data = [
            {
                "id": "RCA-001",
                "trial_id": EYLEA_TRIAL,
                "complaint_id": "CI-001",
                "investigation_id": "INV-001",
                "root_cause_category": RootCauseCategory.MANUFACTURING,
                "root_cause_description": "Silicone oil siliconization process exceeded specification limits due to nozzle calibration drift.",
                "analysis_method": "fishbone",
                "contributing_factors": ["nozzle_calibration_drift", "preventive_maintenance_delay", "siliconization_monitoring_gap"],
                "evidence_supporting": ["particle_identification_report", "process_deviation_log", "equipment_calibration_records"],
                "probability_of_recurrence": "low",
                "impact_scope": "single_batch",
                "identified_by": "QA Investigator Mark Stevens",
                "analysis_date": now - timedelta(days=140),
                "verified": True,
                "verified_by": "QA Manager Robert Kim",
                "notes": "Nozzle replaced and calibration procedure updated.",
                "created_at": now - timedelta(days=140),
            },
            {
                "id": "RCA-002",
                "trial_id": EYLEA_TRIAL,
                "complaint_id": "CI-002",
                "investigation_id": "INV-002",
                "root_cause_category": RootCauseCategory.RAW_MATERIAL,
                "root_cause_description": "Packaging vendor changed adhesive supplier without notification. New adhesive fails at >75% RH.",
                "analysis_method": "5_why",
                "contributing_factors": ["vendor_change_notification_failure", "incoming_qc_testing_gap", "humidity_specification_absent"],
                "evidence_supporting": ["adhesive_test_report", "vendor_audit_findings", "environmental_monitoring_data"],
                "probability_of_recurrence": "low",
                "impact_scope": "multiple_batches",
                "identified_by": "QA Investigator Lisa Chen",
                "analysis_date": now - timedelta(days=148),
                "verified": True,
                "verified_by": "QA Manager Robert Kim",
                "notes": "Vendor required to notify all material changes. Incoming QC updated.",
                "created_at": now - timedelta(days=148),
            },
            {
                "id": "RCA-003",
                "trial_id": EYLEA_TRIAL,
                "complaint_id": "CI-004",
                "investigation_id": "INV-004",
                "root_cause_category": RootCauseCategory.MANUFACTURING,
                "root_cause_description": "HVAC system malfunction during filling operation resulted in clean room classification excursion. Endotoxin contamination from non-sterile air ingress.",
                "analysis_method": "fault_tree",
                "contributing_factors": ["hvac_filter_failure", "environmental_monitoring_delay", "operator_response_time"],
                "evidence_supporting": ["environmental_monitoring_report", "hvac_maintenance_log", "endotoxin_test_results", "batch_record_review"],
                "probability_of_recurrence": "medium",
                "impact_scope": "single_batch",
                "identified_by": "QA Senior Investigator Dr. Helen Park",
                "analysis_date": now - timedelta(days=55),
                "verified": True,
                "verified_by": "VP Quality Dr. William Torres",
                "notes": "Critical finding. HVAC redundancy system being installed.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "RCA-004",
                "trial_id": DUPIXENT_TRIAL,
                "complaint_id": "CI-005",
                "investigation_id": "INV-005",
                "root_cause_category": RootCauseCategory.HUMAN_ERROR,
                "root_cause_description": "Print operator selected incorrect artwork version (v2.1 instead of v2.3) from document control system. System allowed selection of superseded versions.",
                "analysis_method": "fishbone",
                "contributing_factors": ["document_control_system_limitation", "operator_training_gap", "artwork_versioning_confusion"],
                "evidence_supporting": ["print_batch_record", "document_control_audit_trail", "operator_interview_notes"],
                "probability_of_recurrence": "medium",
                "impact_scope": "single_batch",
                "identified_by": "QA Investigator Lisa Chen",
                "analysis_date": now - timedelta(days=95),
                "verified": True,
                "verified_by": "QA Manager Robert Kim",
                "notes": "Document control system upgrade planned to prevent superseded version access.",
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "RCA-005",
                "trial_id": LIBTAYO_TRIAL,
                "complaint_id": "CI-009",
                "investigation_id": "INV-008",
                "root_cause_category": RootCauseCategory.MANUFACTURING,
                "root_cause_description": "Capping machine torque setting drifted 15% below specification over 8-hour production run. Insufficient in-process torque monitoring frequency.",
                "analysis_method": "5_why",
                "contributing_factors": ["torque_monitoring_frequency_insufficient", "capping_machine_wear", "in_process_control_gap"],
                "evidence_supporting": ["torque_trend_data", "capping_machine_maintenance_log", "in_process_control_records"],
                "probability_of_recurrence": "low",
                "impact_scope": "single_batch",
                "identified_by": "QA Investigator Lisa Chen",
                "analysis_date": now - timedelta(days=125),
                "verified": True,
                "verified_by": "QA Manager Robert Kim",
                "notes": "Torque monitoring increased from every 2 hours to every 30 minutes.",
                "created_at": now - timedelta(days=125),
            },
            {
                "id": "RCA-006",
                "trial_id": EYLEA_TRIAL,
                "complaint_id": "CI-003",
                "investigation_id": "INV-003",
                "root_cause_category": RootCauseCategory.DESIGN,
                "root_cause_description": "Pre-filled syringe plunger stopper formulation shows increased friction at lower temperatures within specified storage range.",
                "analysis_method": "fishbone",
                "contributing_factors": ["stopper_material_selection", "temperature_range_specification", "lubrication_adequacy"],
                "evidence_supporting": ["plunger_force_data_vs_temperature", "stopper_material_specification", "competitor_benchmarking"],
                "probability_of_recurrence": "high",
                "impact_scope": "all_batches",
                "identified_by": "QA Investigator Mark Stevens",
                "analysis_date": now - timedelta(days=25),
                "verified": False,
                "verified_by": None,
                "notes": "Pending verification. Design change evaluation in progress.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "RCA-007",
                "trial_id": DUPIXENT_TRIAL,
                "complaint_id": "CI-008",
                "investigation_id": "INV-007",
                "root_cause_category": RootCauseCategory.TRANSPORTATION,
                "root_cause_description": "Suspected diversion from authorized distribution chain. Product traceability gap between regional depot and site.",
                "analysis_method": "fault_tree",
                "contributing_factors": ["distribution_chain_gap", "serialization_verification_gap", "depot_security_vulnerability"],
                "evidence_supporting": ["serialization_audit_trail", "distribution_records", "chemical_fingerprint_comparison"],
                "probability_of_recurrence": "medium",
                "impact_scope": "isolated",
                "identified_by": "QA Senior Investigator Dr. Helen Park",
                "analysis_date": now - timedelta(days=5),
                "verified": False,
                "verified_by": None,
                "notes": "Under active investigation. Law enforcement engaged.",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "RCA-008",
                "trial_id": LIBTAYO_TRIAL,
                "complaint_id": "CI-012",
                "investigation_id": "INV-009",
                "root_cause_category": RootCauseCategory.STORAGE,
                "root_cause_description": "Temperature excursion during warehouse storage caused protein aggregation. Cold chain monitoring gap identified between manufacturing and warehouse intake.",
                "analysis_method": "fishbone",
                "contributing_factors": ["cold_chain_monitoring_gap", "warehouse_intake_delay", "temperature_logger_battery_failure"],
                "evidence_supporting": ["temperature_logger_data", "aggregation_analysis_report", "warehouse_intake_records"],
                "probability_of_recurrence": "medium",
                "impact_scope": "single_batch",
                "identified_by": "QA Senior Investigator Dr. Helen Park",
                "analysis_date": now - timedelta(days=8),
                "verified": False,
                "verified_by": None,
                "notes": "Preliminary finding. Awaiting full temperature mapping data.",
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "RCA-009",
                "trial_id": EYLEA_TRIAL,
                "complaint_id": "CI-001",
                "investigation_id": "INV-001",
                "root_cause_category": RootCauseCategory.MANUFACTURING,
                "root_cause_description": "Secondary root cause: inadequate visual inspection training for siliconization defects. Inspector missed visible particles during 100% inspection.",
                "analysis_method": "5_why",
                "contributing_factors": ["visual_inspection_training_gap", "inspection_fatigue", "lighting_specification"],
                "evidence_supporting": ["inspection_training_records", "defect_library_review", "lighting_measurement_report"],
                "probability_of_recurrence": "low",
                "impact_scope": "process_wide",
                "identified_by": "QA Investigator Mark Stevens",
                "analysis_date": now - timedelta(days=135),
                "verified": True,
                "verified_by": "QA Manager Robert Kim",
                "notes": "Visual inspection training program enhanced. Defect library updated.",
                "created_at": now - timedelta(days=135),
            },
            {
                "id": "RCA-010",
                "trial_id": LIBTAYO_TRIAL,
                "complaint_id": "CI-011",
                "investigation_id": "INV-010",
                "root_cause_category": RootCauseCategory.DESIGN,
                "root_cause_description": "Labeling design does not include short-term storage allowance information approved in IB. Design gap between regulatory approval and label content.",
                "analysis_method": "fishbone",
                "contributing_factors": ["label_content_review_gap", "ib_label_synchronization", "regulatory_approval_tracking"],
                "evidence_supporting": ["ib_storage_section", "approved_label_artwork", "regulatory_approval_timeline"],
                "probability_of_recurrence": "low",
                "impact_scope": "all_batches",
                "identified_by": "QA Investigator Lisa Chen",
                "analysis_date": now - timedelta(days=195),
                "verified": True,
                "verified_by": "QA Specialist Angela Park",
                "notes": "Label update requested to include short-term storage information.",
                "created_at": now - timedelta(days=195),
            },
        ]

        for rca in rca_data:
            self._root_cause_analyses[rca["id"]] = RootCauseAnalysis(**rca)

        # --- 10 CAPA Linkages ---
        capa_data = [
            {
                "id": "CAPA-001",
                "trial_id": EYLEA_TRIAL,
                "complaint_id": "CI-001",
                "root_cause_id": "RCA-001",
                "capa_type": "corrective",
                "capa_number": "CAPA-2025-001",
                "description": "Replace siliconization nozzle and recalibrate equipment. Update calibration SOP to include monthly verification.",
                "assigned_to": "Manufacturing Lead David Park",
                "due_date": now - timedelta(days=110),
                "completed_date": now - timedelta(days=115),
                "status": "closed",
                "effectiveness_check_required": True,
                "effectiveness_check_date": now - timedelta(days=80),
                "effectiveness_confirmed": True,
                "preventive_measures": ["monthly_nozzle_calibration", "in_process_particle_monitoring"],
                "created_by": "QA Manager Robert Kim",
                "approved_by": "VP Quality Dr. William Torres",
                "notes": "Effectiveness confirmed. No recurrence in 3 subsequent batches.",
                "created_at": now - timedelta(days=138),
            },
            {
                "id": "CAPA-002",
                "trial_id": EYLEA_TRIAL,
                "complaint_id": "CI-002",
                "root_cause_id": "RCA-002",
                "capa_type": "corrective",
                "capa_number": "CAPA-2025-002",
                "description": "Issue non-conformance to packaging vendor. Require formal change notification for all material changes.",
                "assigned_to": "Supplier Quality Manager Susan Lee",
                "due_date": now - timedelta(days=120),
                "completed_date": now - timedelta(days=125),
                "status": "closed",
                "effectiveness_check_required": True,
                "effectiveness_check_date": now - timedelta(days=60),
                "effectiveness_confirmed": True,
                "preventive_measures": ["vendor_change_notification_agreement", "incoming_qc_humidity_testing"],
                "created_by": "QA Manager Robert Kim",
                "approved_by": "VP Quality Dr. William Torres",
                "notes": "Vendor has implemented change notification system.",
                "created_at": now - timedelta(days=146),
            },
            {
                "id": "CAPA-003",
                "trial_id": EYLEA_TRIAL,
                "complaint_id": "CI-004",
                "root_cause_id": "RCA-003",
                "capa_type": "corrective",
                "capa_number": "CAPA-2025-003",
                "description": "Install redundant HVAC system for filling suite. Implement real-time environmental monitoring with automatic filling line stop.",
                "assigned_to": "Facilities Director James Wong",
                "due_date": now + timedelta(days=30),
                "completed_date": None,
                "status": "in_progress",
                "effectiveness_check_required": True,
                "effectiveness_check_date": None,
                "effectiveness_confirmed": False,
                "preventive_measures": ["hvac_redundancy", "real_time_environmental_monitoring", "automatic_line_stop"],
                "created_by": "VP Quality Dr. William Torres",
                "approved_by": "VP Quality Dr. William Torres",
                "notes": "Capital project approved. Installation 60% complete.",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "CAPA-004",
                "trial_id": EYLEA_TRIAL,
                "complaint_id": "CI-004",
                "root_cause_id": "RCA-003",
                "capa_type": "preventive",
                "capa_number": "CAPA-2025-004",
                "description": "Implement endotoxin rapid testing at filling line for every batch. Current method takes 48h; rapid method provides results in 1h.",
                "assigned_to": "QC Lab Manager Dr. Anna Schmidt",
                "due_date": now + timedelta(days=60),
                "completed_date": None,
                "status": "open",
                "effectiveness_check_required": True,
                "effectiveness_check_date": None,
                "effectiveness_confirmed": False,
                "preventive_measures": ["rapid_endotoxin_testing", "real_time_release_testing"],
                "created_by": "VP Quality Dr. William Torres",
                "approved_by": None,
                "notes": "Validation of rapid endotoxin method in progress.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "CAPA-005",
                "trial_id": DUPIXENT_TRIAL,
                "complaint_id": "CI-005",
                "root_cause_id": "RCA-004",
                "capa_type": "corrective",
                "capa_number": "CAPA-2025-005",
                "description": "Upgrade document control system to prevent access to superseded artwork versions. Implement mandatory version verification step.",
                "assigned_to": "Document Control Manager Patricia Walsh",
                "due_date": now - timedelta(days=30),
                "completed_date": now - timedelta(days=35),
                "status": "closed",
                "effectiveness_check_required": True,
                "effectiveness_check_date": now - timedelta(days=10),
                "effectiveness_confirmed": True,
                "preventive_measures": ["system_access_control", "mandatory_version_verification", "operator_retraining"],
                "created_by": "QA Manager Robert Kim",
                "approved_by": "QA Manager Robert Kim",
                "notes": "System upgraded. Superseded versions now read-only. Operators retrained.",
                "created_at": now - timedelta(days=92),
            },
            {
                "id": "CAPA-006",
                "trial_id": LIBTAYO_TRIAL,
                "complaint_id": "CI-009",
                "root_cause_id": "RCA-005",
                "capa_type": "corrective",
                "capa_number": "CAPA-2025-006",
                "description": "Increase in-process torque monitoring frequency from every 2 hours to every 30 minutes. Replace worn capping head components.",
                "assigned_to": "Manufacturing Lead Sarah Kim",
                "due_date": now - timedelta(days=100),
                "completed_date": now - timedelta(days=105),
                "status": "closed",
                "effectiveness_check_required": True,
                "effectiveness_check_date": now - timedelta(days=70),
                "effectiveness_confirmed": True,
                "preventive_measures": ["increased_torque_monitoring", "capping_head_replacement_schedule"],
                "created_by": "QA Manager Robert Kim",
                "approved_by": "QA Manager Robert Kim",
                "notes": "No torque excursions since implementation.",
                "created_at": now - timedelta(days=123),
            },
            {
                "id": "CAPA-007",
                "trial_id": EYLEA_TRIAL,
                "complaint_id": "CI-003",
                "root_cause_id": "RCA-006",
                "capa_type": "preventive",
                "capa_number": "CAPA-2025-007",
                "description": "Evaluate alternative plunger stopper formulation with improved low-temperature friction properties. Initiate design change assessment.",
                "assigned_to": "Device Engineering Lead Dr. Kevin Zhao",
                "due_date": now + timedelta(days=90),
                "completed_date": None,
                "status": "open",
                "effectiveness_check_required": True,
                "effectiveness_check_date": None,
                "effectiveness_confirmed": False,
                "preventive_measures": ["stopper_material_upgrade", "extended_temperature_testing"],
                "created_by": "QA Manager Robert Kim",
                "approved_by": None,
                "notes": "Three candidate stopper formulations under evaluation.",
                "created_at": now - timedelta(days=22),
            },
            {
                "id": "CAPA-008",
                "trial_id": DUPIXENT_TRIAL,
                "complaint_id": "CI-008",
                "root_cause_id": "RCA-007",
                "capa_type": "corrective",
                "capa_number": "CAPA-2025-008",
                "description": "Implement end-to-end serialization verification at all distribution chain handoff points. Audit all regional depots.",
                "assigned_to": "Supply Chain Director Michael Brown",
                "due_date": now + timedelta(days=45),
                "completed_date": None,
                "status": "in_progress",
                "effectiveness_check_required": True,
                "effectiveness_check_date": None,
                "effectiveness_confirmed": False,
                "preventive_measures": ["serialization_verification_at_handoff", "depot_security_audit", "chain_of_custody_tracking"],
                "created_by": "VP Quality Dr. William Torres",
                "approved_by": "VP Quality Dr. William Torres",
                "notes": "3 of 7 depots audited. Serialization system deployment 50% complete.",
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "CAPA-009",
                "trial_id": LIBTAYO_TRIAL,
                "complaint_id": "CI-012",
                "root_cause_id": "RCA-008",
                "capa_type": "corrective",
                "capa_number": "CAPA-2025-009",
                "description": "Install continuous cold chain monitoring between manufacturing and warehouse. Implement automated alerts for temperature excursions.",
                "assigned_to": "Warehouse Manager Thomas Green",
                "due_date": now + timedelta(days=21),
                "completed_date": None,
                "status": "in_progress",
                "effectiveness_check_required": True,
                "effectiveness_check_date": None,
                "effectiveness_confirmed": False,
                "preventive_measures": ["continuous_cold_chain_monitoring", "automated_temperature_alerts", "intake_process_redesign"],
                "created_by": "QA Manager Robert Kim",
                "approved_by": "VP Quality Dr. William Torres",
                "notes": "IoT temperature sensors ordered. Expected installation within 2 weeks.",
                "created_at": now - timedelta(days=6),
            },
            {
                "id": "CAPA-010",
                "trial_id": EYLEA_TRIAL,
                "complaint_id": "CI-001",
                "root_cause_id": "RCA-009",
                "capa_type": "preventive",
                "capa_number": "CAPA-2025-010",
                "description": "Enhance visual inspection training program with updated defect library. Install improved inspection lighting per ISO 3951-2 recommendations.",
                "assigned_to": "Training Manager Lisa Nguyen",
                "due_date": now - timedelta(days=90),
                "completed_date": now - timedelta(days=95),
                "status": "closed",
                "effectiveness_check_required": True,
                "effectiveness_check_date": now - timedelta(days=50),
                "effectiveness_confirmed": True,
                "preventive_measures": ["enhanced_defect_library", "improved_inspection_lighting", "annual_requalification"],
                "created_by": "QA Manager Robert Kim",
                "approved_by": "QA Manager Robert Kim",
                "notes": "All inspectors retrained and requalified. Defect detection rate improved 25%.",
                "created_at": now - timedelta(days=133),
            },
        ]

        for c in capa_data:
            self._capa_linkages[c["id"]] = CAPALinkage(**c)

        # --- 10 Regulatory Reports ---
        reg_data = [
            {
                "id": "RR-001",
                "trial_id": EYLEA_TRIAL,
                "complaint_id": "CI-004",
                "report_type": "field_alert",
                "regulatory_authority": "FDA",
                "report_number": "FA-2025-EYLEA-001",
                "submission_date": now - timedelta(days=85),
                "submission_deadline": now - timedelta(days=83),
                "days_to_submit": 5,
                "reportable": True,
                "reporting_criteria_met": "Product quality defect with patient adverse event. 21 CFR 314.81(b)(1) field alert report required.",
                "narrative": "Endotoxin contamination identified in batch EYL-B2024-1004. One confirmed adverse event (severe ocular inflammation).",
                "follow_up_required": True,
                "follow_up_number": 2,
                "acknowledgment_received": True,
                "prepared_by": "Regulatory Affairs Specialist Maria Garcia",
                "reviewed_by": "VP Quality Dr. William Torres",
                "notes": "FDA acknowledged. Follow-up #2 submitted with investigation completion.",
                "created_at": now - timedelta(days=86),
            },
            {
                "id": "RR-002",
                "trial_id": EYLEA_TRIAL,
                "complaint_id": "CI-004",
                "report_type": "mdr",
                "regulatory_authority": "FDA",
                "report_number": "MDR-2025-EYLEA-001",
                "submission_date": now - timedelta(days=80),
                "submission_deadline": now - timedelta(days=75),
                "days_to_submit": 10,
                "reportable": True,
                "reporting_criteria_met": "Device-related adverse event with serious injury. 21 CFR 803 MDR required for pre-filled syringe as combination product.",
                "narrative": "Pre-filled syringe batch associated with serious ocular adverse event. Device component (container/closure) contributed to contamination.",
                "follow_up_required": True,
                "follow_up_number": 1,
                "acknowledgment_received": True,
                "prepared_by": "Regulatory Affairs Specialist Maria Garcia",
                "reviewed_by": "VP Quality Dr. William Torres",
                "notes": "MDR filed within 30-day timeframe. Follow-up pending final investigation.",
                "created_at": now - timedelta(days=82),
            },
            {
                "id": "RR-003",
                "trial_id": EYLEA_TRIAL,
                "complaint_id": "CI-003",
                "report_type": "field_alert",
                "regulatory_authority": "FDA",
                "report_number": None,
                "submission_date": None,
                "submission_deadline": now + timedelta(days=5),
                "days_to_submit": None,
                "reportable": True,
                "reporting_criteria_met": "Device malfunction with patient impact. Potential field alert per 21 CFR 314.81(b)(1).",
                "narrative": None,
                "follow_up_required": False,
                "follow_up_number": 0,
                "acknowledgment_received": False,
                "prepared_by": "Regulatory Affairs Specialist Maria Garcia",
                "reviewed_by": None,
                "notes": "Pending investigation completion for submission.",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "RR-004",
                "trial_id": DUPIXENT_TRIAL,
                "complaint_id": "CI-005",
                "report_type": "field_alert",
                "regulatory_authority": "FDA",
                "report_number": "FA-2025-DUP-001",
                "submission_date": now - timedelta(days=110),
                "submission_deadline": now - timedelta(days=105),
                "days_to_submit": 10,
                "reportable": True,
                "reporting_criteria_met": "Labeling error affecting product identification. 21 CFR 314.81(b)(1) field alert required.",
                "narrative": "Incorrect expiry date on secondary packaging for batch DUP-B2024-2001. All affected units recalled.",
                "follow_up_required": False,
                "follow_up_number": 0,
                "acknowledgment_received": True,
                "prepared_by": "Regulatory Affairs Specialist Thomas Green",
                "reviewed_by": "QA Manager Robert Kim",
                "notes": "Single submission. Investigation and recall completed before filing.",
                "created_at": now - timedelta(days=112),
            },
            {
                "id": "RR-005",
                "trial_id": DUPIXENT_TRIAL,
                "complaint_id": "CI-008",
                "report_type": "field_alert",
                "regulatory_authority": "FDA",
                "report_number": "FA-2025-DUP-002",
                "submission_date": now - timedelta(days=8),
                "submission_deadline": now - timedelta(days=7),
                "days_to_submit": 2,
                "reportable": True,
                "reporting_criteria_met": "Suspected counterfeit product. Immediate notification per FDA Counterfeit Drug Task Force guidance.",
                "narrative": "Suspected counterfeit DUPIXENT identified at clinical site. Product quarantined. Investigation ongoing.",
                "follow_up_required": True,
                "follow_up_number": 0,
                "acknowledgment_received": True,
                "prepared_by": "VP Quality Dr. William Torres",
                "reviewed_by": "VP Quality Dr. William Torres",
                "notes": "Expedited submission. FDA Office of Criminal Investigations notified.",
                "created_at": now - timedelta(days=9),
            },
            {
                "id": "RR-006",
                "trial_id": DUPIXENT_TRIAL,
                "complaint_id": "CI-008",
                "report_type": "field_alert",
                "regulatory_authority": "EMA",
                "report_number": "FA-2025-DUP-EU-001",
                "submission_date": now - timedelta(days=7),
                "submission_deadline": now - timedelta(days=3),
                "days_to_submit": 3,
                "reportable": True,
                "reporting_criteria_met": "Suspected falsified medicinal product per EU FMD. Rapid alert notification required.",
                "narrative": "Suspected counterfeit DUPIXENT identified at EU clinical site. Product quarantined pending investigation.",
                "follow_up_required": True,
                "follow_up_number": 0,
                "acknowledgment_received": False,
                "prepared_by": "EU Regulatory Affairs Specialist Karen Lee",
                "reviewed_by": "VP Quality Dr. William Torres",
                "notes": "Submitted via EU Rapid Alert System. Awaiting EMA acknowledgment.",
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "RR-007",
                "trial_id": LIBTAYO_TRIAL,
                "complaint_id": "CI-012",
                "report_type": "field_alert",
                "regulatory_authority": "FDA",
                "report_number": "FA-2025-LIB-001",
                "submission_date": now - timedelta(days=15),
                "submission_deadline": now - timedelta(days=13),
                "days_to_submit": 5,
                "reportable": True,
                "reporting_criteria_met": "Product quality complaint cluster with patient adverse events. 21 CFR 314.81(b)(1) field alert required.",
                "narrative": "Three infusion-related reactions from single batch LIB-B2024-3004. Batch placed on hold. Investigation ongoing.",
                "follow_up_required": True,
                "follow_up_number": 1,
                "acknowledgment_received": True,
                "prepared_by": "Regulatory Affairs Specialist Maria Garcia",
                "reviewed_by": "VP Quality Dr. William Torres",
                "notes": "Follow-up #1 with preliminary root cause submitted.",
                "created_at": now - timedelta(days=17),
            },
            {
                "id": "RR-008",
                "trial_id": LIBTAYO_TRIAL,
                "complaint_id": "CI-012",
                "report_type": "safety_report",
                "regulatory_authority": "Health Canada",
                "report_number": "SR-2025-LIB-CA-001",
                "submission_date": now - timedelta(days=14),
                "submission_deadline": now - timedelta(days=10),
                "days_to_submit": 6,
                "reportable": True,
                "reporting_criteria_met": "Serious adverse drug reaction cluster. C.01.017 reporting required.",
                "narrative": "Three Grade 3 infusion reactions from batch LIB-B2024-3004 at Canadian sites. Batch on hold.",
                "follow_up_required": True,
                "follow_up_number": 0,
                "acknowledgment_received": False,
                "prepared_by": "Canadian Regulatory Affairs Specialist John Adams",
                "reviewed_by": "QA Manager Robert Kim",
                "notes": "Submitted to Health Canada Vigilance Program.",
                "created_at": now - timedelta(days=16),
            },
            {
                "id": "RR-009",
                "trial_id": LIBTAYO_TRIAL,
                "complaint_id": "CI-009",
                "report_type": "field_alert",
                "regulatory_authority": "FDA",
                "report_number": "FA-2025-LIB-002",
                "submission_date": now - timedelta(days=140),
                "submission_deadline": now - timedelta(days=137),
                "days_to_submit": 10,
                "reportable": True,
                "reporting_criteria_met": "Container closure integrity failure. Sterility compromise potential. 21 CFR 314.81(b)(1) field alert.",
                "narrative": "Vial stopper integrity failure in batch LIB-B2024-3001. Capping torque drift identified as root cause.",
                "follow_up_required": False,
                "follow_up_number": 0,
                "acknowledgment_received": True,
                "prepared_by": "Regulatory Affairs Specialist Thomas Green",
                "reviewed_by": "QA Manager Robert Kim",
                "notes": "Closed. Corrective action completed and verified.",
                "created_at": now - timedelta(days=142),
            },
            {
                "id": "RR-010",
                "trial_id": EYLEA_TRIAL,
                "complaint_id": "CI-001",
                "report_type": "annual_report",
                "regulatory_authority": "FDA",
                "report_number": "AR-2025-EYLEA-Q1",
                "submission_date": now - timedelta(days=60),
                "submission_deadline": now - timedelta(days=45),
                "days_to_submit": None,
                "reportable": True,
                "reporting_criteria_met": "Annual product quality review including complaint trending. 21 CFR 314.81(b)(2).",
                "narrative": "Quarterly complaint trend report for EYLEA clinical trial material. 4 complaints in reporting period.",
                "follow_up_required": False,
                "follow_up_number": 0,
                "acknowledgment_received": True,
                "prepared_by": "Regulatory Affairs Specialist Maria Garcia",
                "reviewed_by": "QA Manager Robert Kim",
                "notes": "Routine annual report. No action items from FDA.",
                "created_at": now - timedelta(days=62),
            },
        ]

        for r in reg_data:
            self._regulatory_reports[r["id"]] = RegulatoryReport(**r)

    # ------------------------------------------------------------------
    # Complaint Intakes
    # ------------------------------------------------------------------

    def list_complaint_intakes(
        self,
        *,
        trial_id: str | None = None,
        category: ComplaintCategory | None = None,
        severity: ComplaintSeverity | None = None,
        status: ComplaintStatus | None = None,
    ) -> list[ComplaintIntake]:
        """List complaint intakes with optional filters."""
        with self._lock:
            result = list(self._complaint_intakes.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]
        if category is not None:
            result = [c for c in result if c.category == category]
        if severity is not None:
            result = [c for c in result if c.severity == severity]
        if status is not None:
            result = [c for c in result if c.status == status]

        return sorted(result, key=lambda c: c.complaint_date, reverse=True)

    def get_complaint_intake(self, intake_id: str) -> ComplaintIntake | None:
        """Get a single complaint intake by ID."""
        with self._lock:
            return self._complaint_intakes.get(intake_id)

    def create_complaint_intake(self, payload: ComplaintIntakeCreate) -> ComplaintIntake:
        """Create a new complaint intake."""
        now = datetime.now(timezone.utc)
        intake_id = f"CI-{uuid4().hex[:8].upper()}"
        intake = ComplaintIntake(
            id=intake_id,
            trial_id=payload.trial_id,
            complaint_number=payload.complaint_number,
            category=payload.category,
            severity=payload.severity,
            status=ComplaintStatus.RECEIVED,
            product_name=payload.product_name,
            batch_number=payload.batch_number,
            complaint_date=now,
            reporter_name=payload.reporter_name,
            reporter_type="investigator",
            site_id=None,
            subject_id=None,
            description=payload.description,
            patient_impact=False,
            sample_available=False,
            sample_received=False,
            initial_assessment=None,
            days_open=0,
            received_by=payload.received_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._complaint_intakes[intake_id] = intake
        logger.info("Created complaint intake %s for trial %s", intake_id, payload.trial_id)
        return intake

    def update_complaint_intake(
        self, intake_id: str, payload: ComplaintIntakeUpdate
    ) -> ComplaintIntake | None:
        """Update an existing complaint intake."""
        with self._lock:
            existing = self._complaint_intakes.get(intake_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ComplaintIntake(**data)
            self._complaint_intakes[intake_id] = updated
        return updated

    def delete_complaint_intake(self, intake_id: str) -> bool:
        """Delete a complaint intake. Returns True if deleted."""
        with self._lock:
            if intake_id in self._complaint_intakes:
                del self._complaint_intakes[intake_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Investigation Records
    # ------------------------------------------------------------------

    def list_investigation_records(
        self,
        *,
        trial_id: str | None = None,
        complaint_id: str | None = None,
        outcome: InvestigationOutcome | None = None,
    ) -> list[InvestigationRecord]:
        """List investigation records with optional filters."""
        with self._lock:
            result = list(self._investigation_records.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if complaint_id is not None:
            result = [r for r in result if r.complaint_id == complaint_id]
        if outcome is not None:
            result = [r for r in result if r.outcome == outcome]

        return sorted(result, key=lambda r: r.investigation_start_date, reverse=True)

    def get_investigation_record(self, record_id: str) -> InvestigationRecord | None:
        """Get a single investigation record by ID."""
        with self._lock:
            return self._investigation_records.get(record_id)

    def create_investigation_record(self, payload: InvestigationRecordCreate) -> InvestigationRecord:
        """Create a new investigation record."""
        now = datetime.now(timezone.utc)
        record_id = f"INV-{uuid4().hex[:8].upper()}"
        record = InvestigationRecord(
            id=record_id,
            trial_id=payload.trial_id,
            complaint_id=payload.complaint_id,
            investigation_start_date=now,
            investigation_end_date=None,
            investigator=payload.investigator,
            outcome=None,
            testing_performed=payload.testing_performed,
            test_results_summary=None,
            manufacturing_review=False,
            distribution_review=False,
            trend_analysis_performed=False,
            similar_complaints_found=0,
            product_retained=False,
            field_alert_considered=False,
            recall_considered=False,
            reviewed_by=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._investigation_records[record_id] = record
        logger.info("Created investigation record %s for complaint %s", record_id, payload.complaint_id)
        return record

    def update_investigation_record(
        self, record_id: str, payload: InvestigationRecordUpdate
    ) -> InvestigationRecord | None:
        """Update an existing investigation record."""
        with self._lock:
            existing = self._investigation_records.get(record_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = InvestigationRecord(**data)
            self._investigation_records[record_id] = updated
        return updated

    def delete_investigation_record(self, record_id: str) -> bool:
        """Delete an investigation record. Returns True if deleted."""
        with self._lock:
            if record_id in self._investigation_records:
                del self._investigation_records[record_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Root Cause Analyses
    # ------------------------------------------------------------------

    def list_root_cause_analyses(
        self,
        *,
        trial_id: str | None = None,
        complaint_id: str | None = None,
        root_cause_category: RootCauseCategory | None = None,
    ) -> list[RootCauseAnalysis]:
        """List root cause analyses with optional filters."""
        with self._lock:
            result = list(self._root_cause_analyses.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if complaint_id is not None:
            result = [r for r in result if r.complaint_id == complaint_id]
        if root_cause_category is not None:
            result = [r for r in result if r.root_cause_category == root_cause_category]

        return sorted(result, key=lambda r: r.analysis_date, reverse=True)

    def get_root_cause_analysis(self, analysis_id: str) -> RootCauseAnalysis | None:
        """Get a single root cause analysis by ID."""
        with self._lock:
            return self._root_cause_analyses.get(analysis_id)

    def create_root_cause_analysis(self, payload: RootCauseAnalysisCreate) -> RootCauseAnalysis:
        """Create a new root cause analysis."""
        now = datetime.now(timezone.utc)
        analysis_id = f"RCA-{uuid4().hex[:8].upper()}"
        analysis = RootCauseAnalysis(
            id=analysis_id,
            trial_id=payload.trial_id,
            complaint_id=payload.complaint_id,
            investigation_id=payload.investigation_id,
            root_cause_category=payload.root_cause_category,
            root_cause_description=payload.root_cause_description,
            analysis_method=payload.analysis_method,
            contributing_factors=[],
            evidence_supporting=[],
            probability_of_recurrence="low",
            impact_scope="isolated",
            identified_by=payload.identified_by,
            analysis_date=now,
            verified=False,
            verified_by=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._root_cause_analyses[analysis_id] = analysis
        logger.info("Created root cause analysis %s for complaint %s", analysis_id, payload.complaint_id)
        return analysis

    def update_root_cause_analysis(
        self, analysis_id: str, payload: RootCauseAnalysisUpdate
    ) -> RootCauseAnalysis | None:
        """Update an existing root cause analysis."""
        with self._lock:
            existing = self._root_cause_analyses.get(analysis_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = RootCauseAnalysis(**data)
            self._root_cause_analyses[analysis_id] = updated
        return updated

    def delete_root_cause_analysis(self, analysis_id: str) -> bool:
        """Delete a root cause analysis. Returns True if deleted."""
        with self._lock:
            if analysis_id in self._root_cause_analyses:
                del self._root_cause_analyses[analysis_id]
                return True
            return False

    # ------------------------------------------------------------------
    # CAPA Linkages
    # ------------------------------------------------------------------

    def list_capa_linkages(
        self,
        *,
        trial_id: str | None = None,
        complaint_id: str | None = None,
        status: str | None = None,
    ) -> list[CAPALinkage]:
        """List CAPA linkages with optional filters."""
        with self._lock:
            result = list(self._capa_linkages.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]
        if complaint_id is not None:
            result = [c for c in result if c.complaint_id == complaint_id]
        if status is not None:
            result = [c for c in result if c.status == status]

        return sorted(result, key=lambda c: c.due_date, reverse=True)

    def get_capa_linkage(self, linkage_id: str) -> CAPALinkage | None:
        """Get a single CAPA linkage by ID."""
        with self._lock:
            return self._capa_linkages.get(linkage_id)

    def create_capa_linkage(self, payload: CAPALinkageCreate) -> CAPALinkage:
        """Create a new CAPA linkage."""
        now = datetime.now(timezone.utc)
        linkage_id = f"CAPA-{uuid4().hex[:8].upper()}"
        linkage = CAPALinkage(
            id=linkage_id,
            trial_id=payload.trial_id,
            complaint_id=payload.complaint_id,
            root_cause_id=payload.root_cause_id,
            capa_type="corrective",
            capa_number=payload.capa_number,
            description=payload.description,
            assigned_to=payload.assigned_to,
            due_date=payload.due_date,
            completed_date=None,
            status="open",
            effectiveness_check_required=True,
            effectiveness_check_date=None,
            effectiveness_confirmed=False,
            preventive_measures=[],
            created_by=payload.created_by,
            approved_by=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._capa_linkages[linkage_id] = linkage
        logger.info("Created CAPA linkage %s for complaint %s", linkage_id, payload.complaint_id)
        return linkage

    def update_capa_linkage(
        self, linkage_id: str, payload: CAPALinkageUpdate
    ) -> CAPALinkage | None:
        """Update an existing CAPA linkage."""
        with self._lock:
            existing = self._capa_linkages.get(linkage_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CAPALinkage(**data)
            self._capa_linkages[linkage_id] = updated
        return updated

    def delete_capa_linkage(self, linkage_id: str) -> bool:
        """Delete a CAPA linkage. Returns True if deleted."""
        with self._lock:
            if linkage_id in self._capa_linkages:
                del self._capa_linkages[linkage_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Regulatory Reports
    # ------------------------------------------------------------------

    def list_regulatory_reports(
        self,
        *,
        trial_id: str | None = None,
        complaint_id: str | None = None,
        report_type: str | None = None,
        regulatory_authority: str | None = None,
    ) -> list[RegulatoryReport]:
        """List regulatory reports with optional filters."""
        with self._lock:
            result = list(self._regulatory_reports.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if complaint_id is not None:
            result = [r for r in result if r.complaint_id == complaint_id]
        if report_type is not None:
            result = [r for r in result if r.report_type == report_type]
        if regulatory_authority is not None:
            result = [r for r in result if r.regulatory_authority == regulatory_authority]

        return sorted(result, key=lambda r: r.created_at, reverse=True)

    def get_regulatory_report(self, report_id: str) -> RegulatoryReport | None:
        """Get a single regulatory report by ID."""
        with self._lock:
            return self._regulatory_reports.get(report_id)

    def create_regulatory_report(self, payload: RegulatoryReportCreate) -> RegulatoryReport:
        """Create a new regulatory report."""
        now = datetime.now(timezone.utc)
        report_id = f"RR-{uuid4().hex[:8].upper()}"
        report = RegulatoryReport(
            id=report_id,
            trial_id=payload.trial_id,
            complaint_id=payload.complaint_id,
            report_type=payload.report_type,
            regulatory_authority=payload.regulatory_authority,
            report_number=None,
            submission_date=None,
            submission_deadline=payload.submission_deadline,
            days_to_submit=None,
            reportable=True,
            reporting_criteria_met=payload.reporting_criteria_met,
            narrative=None,
            follow_up_required=False,
            follow_up_number=0,
            acknowledgment_received=False,
            prepared_by=payload.prepared_by,
            reviewed_by=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._regulatory_reports[report_id] = report
        logger.info("Created regulatory report %s for complaint %s", report_id, payload.complaint_id)
        return report

    def update_regulatory_report(
        self, report_id: str, payload: RegulatoryReportUpdate
    ) -> RegulatoryReport | None:
        """Update an existing regulatory report."""
        with self._lock:
            existing = self._regulatory_reports.get(report_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = RegulatoryReport(**data)
            self._regulatory_reports[report_id] = updated
        return updated

    def delete_regulatory_report(self, report_id: str) -> bool:
        """Delete a regulatory report. Returns True if deleted."""
        with self._lock:
            if report_id in self._regulatory_reports:
                del self._regulatory_reports[report_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> ProductComplaintMetrics:
        """Compute aggregate product complaint metrics."""
        with self._lock:
            complaints = list(self._complaint_intakes.values())
            investigations = list(self._investigation_records.values())
            root_causes = list(self._root_cause_analyses.values())
            capas = list(self._capa_linkages.values())
            reports = list(self._regulatory_reports.values())

        # Complaints by category
        complaints_by_category: dict[str, int] = {}
        for c in complaints:
            key = c.category.value
            complaints_by_category[key] = complaints_by_category.get(key, 0) + 1

        # Complaints by severity
        complaints_by_severity: dict[str, int] = {}
        for c in complaints:
            key = c.severity.value
            complaints_by_severity[key] = complaints_by_severity.get(key, 0) + 1

        # Complaints by status
        complaints_by_status: dict[str, int] = {}
        for c in complaints:
            key = c.status.value
            complaints_by_status[key] = complaints_by_status.get(key, 0) + 1

        # Average days open
        days_list = [c.days_open for c in complaints]
        avg_days_open = round(sum(days_list) / max(1, len(days_list)), 1) if days_list else 0.0

        # Investigations by outcome
        investigations_by_outcome: dict[str, int] = {}
        for inv in investigations:
            key = inv.outcome.value if inv.outcome is not None else "pending"
            investigations_by_outcome[key] = investigations_by_outcome.get(key, 0) + 1

        # Root causes by category
        root_causes_by_category: dict[str, int] = {}
        for rca in root_causes:
            key = rca.root_cause_category.value
            root_causes_by_category[key] = root_causes_by_category.get(key, 0) + 1

        # Open CAPAs
        open_capas = sum(1 for c in capas if c.status in ("open", "in_progress"))

        # Reports pending submission
        reports_pending = sum(1 for r in reports if r.submission_date is None)

        return ProductComplaintMetrics(
            total_complaints=len(complaints),
            complaints_by_category=complaints_by_category,
            complaints_by_severity=complaints_by_severity,
            complaints_by_status=complaints_by_status,
            avg_days_open=avg_days_open,
            total_investigations=len(investigations),
            investigations_by_outcome=investigations_by_outcome,
            total_root_causes=len(root_causes),
            root_causes_by_category=root_causes_by_category,
            total_capas=len(capas),
            open_capas=open_capas,
            total_regulatory_reports=len(reports),
            reports_pending_submission=reports_pending,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ProductComplaintService | None = None
_instance_lock = threading.Lock()


def get_product_complaint_service() -> ProductComplaintService:
    """Return the singleton ProductComplaintService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ProductComplaintService()
    return _instance


def reset_product_complaint_service() -> ProductComplaintService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = ProductComplaintService()
    return _instance
