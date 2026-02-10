"""Site Audit Management Service (QA-AUDIT).

Manages GCP audits, regulatory inspections, sponsor-initiated audits, CRO
audits, and for-cause audits at clinical trial sites. Covers audit planning,
execution, findings classification, CAPA tracking, audit report lifecycle,
and audit metrics.

Usage:
    from app.services.site_audit_service import get_site_audit_service

    svc = get_site_audit_service()
    audits = svc.list_audits()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.site_audit import (
    AuditCAPA,
    AuditCAPACreate,
    AuditCAPAUpdate,
    AuditFinding,
    AuditFindingCreate,
    AuditFindingUpdate,
    AuditReport,
    AuditReportCreate,
    AuditReportUpdate,
    AuditStatus,
    AuditType,
    CAPAStatus,
    FindingClassification,
    FindingStatus,
    ReportStatus,
    SiteAudit,
    SiteAuditCreate,
    SiteAuditMetrics,
    SiteAuditUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class SiteAuditService:
    """In-memory Site Audit Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._audits: dict[str, SiteAudit] = {}
        self._findings: dict[str, AuditFinding] = {}
        self._capas: dict[str, AuditCAPA] = {}
        self._reports: dict[str, AuditReport] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic site audit data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Site Audits ---
        audits_data = [
            # EYLEA trial audits
            {"id": "AUD-001", "trial_id": EYLEA_TRIAL, "site_id": "SITE-101", "site_name": "Bascom Palmer Eye Institute", "audit_type": AuditType.ROUTINE, "status": AuditStatus.FINALIZED, "planned_date": now - timedelta(days=120), "actual_start_date": now - timedelta(days=118), "actual_end_date": now - timedelta(days=115), "lead_auditor": "Jennifer Walsh", "audit_team": ["Jennifer Walsh", "Mark Stevens", "Lisa Chen"], "scope": "GCP compliance review covering informed consent, source data verification, IP accountability, and safety reporting", "regulatory_authority": None, "created_at": now - timedelta(days=150)},
            {"id": "AUD-002", "trial_id": EYLEA_TRIAL, "site_id": "SITE-102", "site_name": "Wills Eye Hospital", "audit_type": AuditType.FOR_CAUSE, "status": AuditStatus.FINALIZED, "planned_date": now - timedelta(days=90), "actual_start_date": now - timedelta(days=88), "actual_end_date": now - timedelta(days=86), "lead_auditor": "Robert Kim", "audit_team": ["Robert Kim", "Sarah Davis"], "scope": "For-cause audit triggered by protocol deviation trend analysis. Focus on eligibility verification and randomization procedures", "regulatory_authority": None, "created_at": now - timedelta(days=100)},
            {"id": "AUD-003", "trial_id": EYLEA_TRIAL, "site_id": "SITE-103", "site_name": "Cole Eye Institute", "audit_type": AuditType.REGULATORY_INSPECTION, "status": AuditStatus.CLOSED, "planned_date": now - timedelta(days=60), "actual_start_date": now - timedelta(days=58), "actual_end_date": now - timedelta(days=55), "lead_auditor": "FDA Inspector", "audit_team": ["FDA Inspector", "Jennifer Walsh"], "scope": "FDA pre-approval inspection covering data integrity, safety reporting, and GCP compliance", "regulatory_authority": "FDA", "created_at": now - timedelta(days=75)},
            {"id": "AUD-004", "trial_id": EYLEA_TRIAL, "site_id": "SITE-101", "site_name": "Bascom Palmer Eye Institute", "audit_type": AuditType.CRO_OVERSIGHT, "status": AuditStatus.IN_PROGRESS, "planned_date": now - timedelta(days=10), "actual_start_date": now - timedelta(days=8), "actual_end_date": None, "lead_auditor": "Mark Stevens", "audit_team": ["Mark Stevens", "Amy Rodriguez"], "scope": "CRO oversight audit focusing on monitoring visit quality, query resolution timelines, and data management practices", "regulatory_authority": None, "created_at": now - timedelta(days=20)},
            # Dupixent trial audits
            {"id": "AUD-005", "trial_id": DUPIXENT_TRIAL, "site_id": "SITE-104", "site_name": "NYU Langone Dermatology", "audit_type": AuditType.ROUTINE, "status": AuditStatus.FINALIZED, "planned_date": now - timedelta(days=100), "actual_start_date": now - timedelta(days=98), "actual_end_date": now - timedelta(days=95), "lead_auditor": "Patricia Hernandez", "audit_team": ["Patricia Hernandez", "David Park", "Nicole Brown"], "scope": "Routine GCP audit covering EASI scoring consistency, photography procedures, informed consent, and drug accountability", "regulatory_authority": None, "created_at": now - timedelta(days=130)},
            {"id": "AUD-006", "trial_id": DUPIXENT_TRIAL, "site_id": "SITE-105", "site_name": "Oregon Health & Science University", "audit_type": AuditType.SYSTEMS_AUDIT, "status": AuditStatus.REPORT_REVIEW, "planned_date": now - timedelta(days=45), "actual_start_date": now - timedelta(days=43), "actual_end_date": now - timedelta(days=40), "lead_auditor": "David Park", "audit_team": ["David Park", "Lisa Chen"], "scope": "Systems audit of EDC configuration, data validation rules, and electronic signature compliance (21 CFR Part 11)", "regulatory_authority": None, "created_at": now - timedelta(days=60)},
            {"id": "AUD-007", "trial_id": DUPIXENT_TRIAL, "site_id": "SITE-106", "site_name": "Northwestern Medicine", "audit_type": AuditType.VENDOR_AUDIT, "status": AuditStatus.SCHEDULED, "planned_date": now + timedelta(days=15), "actual_start_date": None, "actual_end_date": None, "lead_auditor": "Nicole Brown", "audit_team": ["Nicole Brown", "Patricia Hernandez"], "scope": "Central laboratory vendor audit covering sample handling, assay validation, and result reporting timelines", "regulatory_authority": None, "created_at": now - timedelta(days=10)},
            {"id": "AUD-008", "trial_id": DUPIXENT_TRIAL, "site_id": "SITE-104", "site_name": "NYU Langone Dermatology", "audit_type": AuditType.PRE_APPROVAL, "status": AuditStatus.PLANNED, "planned_date": now + timedelta(days=45), "actual_start_date": None, "actual_end_date": None, "lead_auditor": "Patricia Hernandez", "audit_team": ["Patricia Hernandez", "Robert Kim"], "scope": "Pre-approval inspection readiness assessment covering TMF completeness, key data integrity, and regulatory submission data", "regulatory_authority": None, "created_at": now - timedelta(days=5)},
            # Libtayo trial audits
            {"id": "AUD-009", "trial_id": LIBTAYO_TRIAL, "site_id": "SITE-107", "site_name": "Memorial Sloan Kettering", "audit_type": AuditType.ROUTINE, "status": AuditStatus.FINALIZED, "planned_date": now - timedelta(days=80), "actual_start_date": now - timedelta(days=78), "actual_end_date": now - timedelta(days=75), "lead_auditor": "Thomas Grant", "audit_team": ["Thomas Grant", "Maria Santos", "Kevin O'Brien"], "scope": "Routine GCP audit covering RECIST assessments, tumor measurements, safety reporting, and biospecimen handling", "regulatory_authority": None, "created_at": now - timedelta(days=110)},
            {"id": "AUD-010", "trial_id": LIBTAYO_TRIAL, "site_id": "SITE-108", "site_name": "MD Anderson Cancer Center", "audit_type": AuditType.REGULATORY_INSPECTION, "status": AuditStatus.FINALIZED, "planned_date": now - timedelta(days=50), "actual_start_date": now - timedelta(days=48), "actual_end_date": now - timedelta(days=44), "lead_auditor": "EMA Inspector", "audit_team": ["EMA Inspector", "Thomas Grant"], "scope": "EMA GCP inspection covering informed consent, adverse event reporting, and investigational product management", "regulatory_authority": "EMA", "created_at": now - timedelta(days=65)},
            {"id": "AUD-011", "trial_id": LIBTAYO_TRIAL, "site_id": "SITE-107", "site_name": "Memorial Sloan Kettering", "audit_type": AuditType.FOR_CAUSE, "status": AuditStatus.REPORT_DRAFTING, "planned_date": now - timedelta(days=25), "actual_start_date": now - timedelta(days=23), "actual_end_date": now - timedelta(days=20), "lead_auditor": "Kevin O'Brien", "audit_team": ["Kevin O'Brien", "Maria Santos"], "scope": "For-cause audit triggered by SAE reporting delays. Focus on safety event detection, reporting timelines, and investigator notification procedures", "regulatory_authority": None, "created_at": now - timedelta(days=35)},
            {"id": "AUD-012", "trial_id": LIBTAYO_TRIAL, "site_id": "SITE-108", "site_name": "MD Anderson Cancer Center", "audit_type": AuditType.CRO_OVERSIGHT, "status": AuditStatus.SCHEDULED, "planned_date": now + timedelta(days=30), "actual_start_date": None, "actual_end_date": None, "lead_auditor": "Thomas Grant", "audit_team": ["Thomas Grant", "Kevin O'Brien"], "scope": "CRO oversight audit covering monitoring reports, issue escalation processes, and site management activities", "regulatory_authority": None, "created_at": now - timedelta(days=8)},
        ]

        for a in audits_data:
            self._audits[a["id"]] = SiteAudit(**a)

        # --- 18 Audit Findings ---
        findings_data = [
            # AUD-001 findings (EYLEA routine audit)
            {"id": "FND-001", "audit_id": "AUD-001", "finding_number": "AUD-001-F01", "classification": FindingClassification.MINOR, "area": "Informed Consent", "description": "Consent form version 3.1 was used for 2 subjects after version 3.2 was approved. Both subjects re-consented within 14 days.", "evidence": "Consent tracking log entries for PT-1002 and PT-1003; IRB approval letter dated 2025-08-15", "regulation_reference": "ICH E6(R2) 4.8.2", "status": FindingStatus.CLOSED, "response_deadline": now - timedelta(days=90), "site_response": "Corrective action implemented. Updated consent tracking procedures and added version verification checklist.", "created_at": now - timedelta(days=115)},
            {"id": "FND-002", "audit_id": "AUD-001", "finding_number": "AUD-001-F02", "classification": FindingClassification.OBSERVATION, "area": "Source Data", "description": "Minor inconsistencies noted between source worksheets and EDC entries for 3 BCVA assessments. All discrepancies were within acceptable tolerance.", "evidence": "Source data verification worksheets for visits V4, V6 for subjects PT-1001, PT-1004, PT-1005", "regulation_reference": None, "status": FindingStatus.CLOSED, "response_deadline": now - timedelta(days=90), "site_response": "Additional training provided to data entry staff on BCVA transcription procedures.", "created_at": now - timedelta(days=115)},
            # AUD-002 findings (EYLEA for-cause audit)
            {"id": "FND-003", "audit_id": "AUD-002", "finding_number": "AUD-002-F01", "classification": FindingClassification.MAJOR, "area": "Eligibility", "description": "Subject PT-1008 enrolled with baseline BCVA of 78 letters, exceeding the maximum of 75 letters per inclusion criterion 3. Protocol deviation not reported within required timeframe.", "evidence": "Screening BCVA chart for PT-1008; Eligibility checklist signed by Dr. Rodriguez; Protocol v4.0 section 5.1", "regulation_reference": "ICH E6(R2) 4.5.1", "status": FindingStatus.CAPA_ASSIGNED, "response_deadline": now - timedelta(days=60), "site_response": "Root cause analysis completed. PI oversight of eligibility verification enhanced.", "created_at": now - timedelta(days=86)},
            {"id": "FND-004", "audit_id": "AUD-002", "finding_number": "AUD-002-F02", "classification": FindingClassification.MAJOR, "area": "Randomization", "description": "Randomization code for PT-1009 was accessed by unblinded personnel 48 hours before the planned unblinding visit, creating a potential unblinding event.", "evidence": "IXRS access log entries; User role assignment matrix; SOP-RAND-003 section 4.2", "regulation_reference": "ICH E6(R2) 5.15", "status": FindingStatus.IN_REMEDIATION, "response_deadline": now - timedelta(days=55), "site_response": "IXRS access controls have been tightened. Role-based access review completed.", "created_at": now - timedelta(days=86)},
            {"id": "FND-005", "audit_id": "AUD-002", "finding_number": "AUD-002-F03", "classification": FindingClassification.MINOR, "area": "IP Accountability", "description": "Temperature excursion recorded for IP shipment on 2025-09-10 (2.1 degrees C above range for 45 minutes). Excursion report was filed but stability assessment was delayed by 5 days.", "evidence": "Temperature monitoring log; Excursion report ER-2025-042; IP accountability log", "regulation_reference": "ICH E6(R2) 5.14.3", "status": FindingStatus.CLOSED, "response_deadline": now - timedelta(days=60), "site_response": "Stability assessment confirmed product remained within acceptable parameters. Excursion response SOP updated to require 48-hour assessment turnaround.", "created_at": now - timedelta(days=86)},
            # AUD-003 findings (EYLEA FDA inspection)
            {"id": "FND-006", "audit_id": "AUD-003", "finding_number": "AUD-003-F01", "classification": FindingClassification.CRITICAL, "area": "Data Integrity", "description": "Audit trail entries for 5 EDC corrections showed timestamps that do not match the documented correction dates in the query resolution log, raising data integrity concerns.", "evidence": "EDC audit trail report; Query resolution log for subjects PT-1001, PT-1003, PT-1005, PT-1007, PT-1010; 21 CFR Part 11 compliance checklist", "regulation_reference": "21 CFR 11.10(e)", "status": FindingStatus.CAPA_ASSIGNED, "response_deadline": now - timedelta(days=30), "site_response": "Full investigation initiated. IT team conducting audit trail reconciliation across all subjects.", "created_at": now - timedelta(days=55)},
            {"id": "FND-007", "audit_id": "AUD-003", "finding_number": "AUD-003-F02", "classification": FindingClassification.MAJOR, "area": "Safety Reporting", "description": "Two SAEs (injection site endophthalmitis for PT-1005 and retinal detachment for PT-1007) were reported to the sponsor 3 and 5 days late respectively, exceeding the 24-hour reporting requirement.", "evidence": "SAE source documents; Sponsor notification timestamps; Safety reporting SOP-SAF-001", "regulation_reference": "ICH E6(R2) 4.11.1", "status": FindingStatus.CAPA_ASSIGNED, "response_deadline": now - timedelta(days=25), "site_response": "Safety reporting workflow redesigned with automated notification triggers.", "created_at": now - timedelta(days=55)},
            # AUD-005 findings (Dupixent routine audit)
            {"id": "FND-008", "audit_id": "AUD-005", "finding_number": "AUD-005-F01", "classification": FindingClassification.MINOR, "area": "EASI Scoring", "description": "EASI scoring inter-rater variability exceeded 15% threshold for 4 of 20 subjects audited. Individual component scores showed largest discrepancy in erythema assessment.", "evidence": "EASI scoring comparison worksheets; Training completion records; Photography comparison records", "regulation_reference": None, "status": FindingStatus.CLOSED, "response_deadline": now - timedelta(days=70), "site_response": "Additional EASI scoring calibration training conducted for all raters. Inter-rater reliability re-assessment showed improvement to within 8% threshold.", "created_at": now - timedelta(days=95)},
            {"id": "FND-009", "audit_id": "AUD-005", "finding_number": "AUD-005-F02", "classification": FindingClassification.OBSERVATION, "area": "Drug Accountability", "description": "IP dispensing log for site pharmacy showed minor documentation gaps: 3 entries missing pharmacist initials.", "evidence": "IP dispensing log pages 12, 15, 18; Pharmacy SOP-PHARM-002", "regulation_reference": None, "status": FindingStatus.CLOSED, "response_deadline": now - timedelta(days=70), "site_response": "Pharmacist reminded of documentation requirements. Weekly log review implemented.", "created_at": now - timedelta(days=95)},
            # AUD-006 findings (Dupixent systems audit)
            {"id": "FND-010", "audit_id": "AUD-006", "finding_number": "AUD-006-F01", "classification": FindingClassification.MAJOR, "area": "EDC System", "description": "EDC edit check for EASI total score calculation was incorrectly configured, allowing scores above the maximum of 72 to be saved without triggering a validation error.", "evidence": "EDC validation rules specification v2.3; Test case results showing score of 78 accepted; Affected subjects list (3 records)", "regulation_reference": "21 CFR 11.10(a)", "status": FindingStatus.OPEN, "response_deadline": now - timedelta(days=15), "site_response": None, "created_at": now - timedelta(days=40)},
            {"id": "FND-011", "audit_id": "AUD-006", "finding_number": "AUD-006-F02", "classification": FindingClassification.MINOR, "area": "Electronic Signatures", "description": "Two users shared login credentials for EDC system access on one occasion, documented in the IT incident log.", "evidence": "IT incident report INC-2025-0892; User access log showing concurrent sessions; 21 CFR Part 11 training records", "regulation_reference": "21 CFR 11.10(d)", "status": FindingStatus.VERIFICATION_PENDING, "response_deadline": now - timedelta(days=20), "site_response": "Users retrained on electronic signature requirements. Multi-factor authentication implemented.", "created_at": now - timedelta(days=40)},
            # AUD-009 findings (Libtayo routine audit)
            {"id": "FND-012", "audit_id": "AUD-009", "finding_number": "AUD-009-F01", "classification": FindingClassification.MINOR, "area": "RECIST Assessments", "description": "Target lesion measurements for 2 subjects showed minor measurement variability (>10% but <20%) between blinded independent central review and site assessment.", "evidence": "BICR comparison report; Site radiology worksheets for PT-3002, PT-3005; RECIST 1.1 guidelines section 4.4", "regulation_reference": None, "status": FindingStatus.CLOSED, "response_deadline": now - timedelta(days=50), "site_response": "Radiologist calibration training completed. Measurement technique standardized.", "created_at": now - timedelta(days=75)},
            {"id": "FND-013", "audit_id": "AUD-009", "finding_number": "AUD-009-F02", "classification": FindingClassification.OBSERVATION, "area": "Biospecimen Handling", "description": "Temperature monitoring log for biospecimen freezer showed a 10-minute gap in continuous monitoring on 2025-10-02 due to probe maintenance.", "evidence": "Freezer temperature log; Probe maintenance record; Biospecimen SOP-BIO-004", "regulation_reference": None, "status": FindingStatus.CLOSED, "response_deadline": now - timedelta(days=50), "site_response": "Backup probe installed to ensure continuous monitoring during maintenance.", "created_at": now - timedelta(days=75)},
            # AUD-010 findings (Libtayo EMA inspection)
            {"id": "FND-014", "audit_id": "AUD-010", "finding_number": "AUD-010-F01", "classification": FindingClassification.CRITICAL, "area": "Adverse Event Reporting", "description": "Three immune-related adverse events (irAEs) were downgraded in severity without documented medical justification. Grade 3 hepatitis for PT-3004 was changed to Grade 2 without supporting lab values.", "evidence": "AE CRF pages for PT-3004, PT-3006, PT-3008; Laboratory results; Medical monitor review notes; CTCAE v5.0 grading criteria", "regulation_reference": "ICH E6(R2) 4.11", "status": FindingStatus.IN_REMEDIATION, "response_deadline": now - timedelta(days=20), "site_response": "All irAE gradings under comprehensive re-review by medical monitor. Training on CTCAE grading scheduled for all investigators.", "created_at": now - timedelta(days=44)},
            {"id": "FND-015", "audit_id": "AUD-010", "finding_number": "AUD-010-F02", "classification": FindingClassification.MAJOR, "area": "IP Management", "description": "Investigational product temperature storage records showed two undocumented excursions over 30 days, each exceeding the upper limit by 1.5 degrees C for approximately 2 hours.", "evidence": "IP storage temperature logs; Excursion assessment forms (missing); IP accountability ledger", "regulation_reference": "ICH E6(R2) 5.14.3", "status": FindingStatus.CAPA_ASSIGNED, "response_deadline": now - timedelta(days=15), "site_response": "Retrospective excursion assessments completed. Automated alert system being installed for temperature monitoring.", "created_at": now - timedelta(days=44)},
            # AUD-011 findings (Libtayo for-cause audit)
            {"id": "FND-016", "audit_id": "AUD-011", "finding_number": "AUD-011-F01", "classification": FindingClassification.CRITICAL, "area": "Safety Reporting", "description": "Systematic pattern identified: 8 of 15 SAEs reported to sponsor beyond the 24-hour window. Median reporting delay was 72 hours. Root cause linked to inadequate after-hours safety reporting procedures.", "evidence": "SAE reporting timeline analysis; After-hours call log; Safety reporting SOP-SAF-002; Investigator delegation log", "regulation_reference": "ICH E6(R2) 4.11.1", "status": FindingStatus.OPEN, "response_deadline": now - timedelta(days=5), "site_response": None, "created_at": now - timedelta(days=20)},
            {"id": "FND-017", "audit_id": "AUD-011", "finding_number": "AUD-011-F02", "classification": FindingClassification.MAJOR, "area": "Investigator Oversight", "description": "Principal investigator did not personally review and sign 4 of 15 SAE reports. Sub-investigator signatures were present but PI co-signature was missing.", "evidence": "SAE report forms; Delegation of authority log; PI activity log for the affected reporting periods", "regulation_reference": "ICH E6(R2) 4.1.5", "status": FindingStatus.OPEN, "response_deadline": now - timedelta(days=5), "site_response": None, "created_at": now - timedelta(days=20)},
            {"id": "FND-018", "audit_id": "AUD-011", "finding_number": "AUD-011-F03", "classification": FindingClassification.MINOR, "area": "Documentation", "description": "Study delegation log not updated to reflect departure of two study coordinators who left the site 6 weeks prior to audit.", "evidence": "Delegation log v5; HR records confirming departure dates; Training matrix", "regulation_reference": "ICH E6(R2) 4.2.5", "status": FindingStatus.OPEN, "response_deadline": now - timedelta(days=5), "site_response": None, "created_at": now - timedelta(days=20)},
        ]

        for f in findings_data:
            self._findings[f["id"]] = AuditFinding(**f)

        # --- 10 CAPAs ---
        capas_data = [
            {"id": "CAPA-001", "finding_id": "FND-001", "audit_id": "AUD-001", "corrective_action": "Re-consent all affected subjects using current approved consent form version", "preventive_action": "Implement automated consent version tracking in site management system with alerts for new IRB approvals", "responsible_party": "Dr. James Rodriguez", "due_date": now - timedelta(days=80), "status": CAPAStatus.CLOSED, "completion_date": now - timedelta(days=85), "verification_date": now - timedelta(days=75), "verified_by": "Jennifer Walsh", "effectiveness_evidence": "Post-implementation review showed 100% consent version compliance over 60-day monitoring period"},
            {"id": "CAPA-002", "finding_id": "FND-003", "audit_id": "AUD-002", "corrective_action": "Conduct retrospective eligibility review for all enrolled subjects. Document protocol deviation for PT-1008 with medical rationale for continued participation.", "preventive_action": "Implement dual-verification eligibility checklist requiring independent review by both PI and study coordinator before randomization", "responsible_party": "Dr. James Rodriguez", "due_date": now - timedelta(days=30), "status": CAPAStatus.IN_PROGRESS, "completion_date": None, "verification_date": None, "verified_by": None, "effectiveness_evidence": None},
            {"id": "CAPA-003", "finding_id": "FND-004", "audit_id": "AUD-002", "corrective_action": "Review all IXRS access logs for the past 6 months. Revoke access for personnel not requiring unblinded access.", "preventive_action": "Implement quarterly IXRS access reviews and add two-factor authentication for unblinding functions", "responsible_party": "Mark Stevens", "due_date": now - timedelta(days=25), "status": CAPAStatus.IN_PROGRESS, "completion_date": None, "verification_date": None, "verified_by": None, "effectiveness_evidence": None},
            {"id": "CAPA-004", "finding_id": "FND-006", "audit_id": "AUD-003", "corrective_action": "Complete full audit trail reconciliation for all EDC corrections across all subjects. Document findings and corrections.", "preventive_action": "Implement automated audit trail timestamp validation. Establish monthly data integrity checks comparing EDC audit trail with query resolution logs.", "responsible_party": "Lisa Chen", "due_date": now - timedelta(days=10), "status": CAPAStatus.PLANNED, "completion_date": None, "verification_date": None, "verified_by": None, "effectiveness_evidence": None},
            {"id": "CAPA-005", "finding_id": "FND-007", "audit_id": "AUD-003", "corrective_action": "Implement automated SAE notification system with escalation triggers at 12-hour and 20-hour marks", "preventive_action": "Establish 24/7 safety reporting hotline. Create backup reporting chain when primary reporter is unavailable.", "responsible_party": "Dr. Sarah Thompson", "due_date": now - timedelta(days=5), "status": CAPAStatus.PLANNED, "completion_date": None, "verification_date": None, "verified_by": None, "effectiveness_evidence": None},
            {"id": "CAPA-006", "finding_id": "FND-008", "audit_id": "AUD-005", "corrective_action": "Conduct EASI scoring calibration session with standardized photographs for all raters", "preventive_action": "Implement quarterly inter-rater reliability assessments with remediation training for raters exceeding 10% variability", "responsible_party": "Dr. Angela Martinez", "due_date": now - timedelta(days=60), "status": CAPAStatus.VERIFIED, "completion_date": now - timedelta(days=65), "verification_date": now - timedelta(days=55), "verified_by": "Patricia Hernandez", "effectiveness_evidence": "Post-training inter-rater reliability assessment showed all raters within 8% threshold. 90-day follow-up confirmed sustained improvement."},
            {"id": "CAPA-007", "finding_id": "FND-014", "audit_id": "AUD-010", "corrective_action": "Comprehensive re-review of all irAE gradings by independent medical monitor. Correct any misgraded events in the database.", "preventive_action": "Implement mandatory CTCAE grading review by medical monitor for all Grade 2+ immune-related adverse events before database entry", "responsible_party": "Dr. Catherine Liu", "due_date": now + timedelta(days=10), "status": CAPAStatus.IN_PROGRESS, "completion_date": None, "verification_date": None, "verified_by": None, "effectiveness_evidence": None},
            {"id": "CAPA-008", "finding_id": "FND-015", "audit_id": "AUD-010", "corrective_action": "Complete retrospective excursion assessments for both undocumented events. Assess impact on IP integrity.", "preventive_action": "Install continuous temperature monitoring system with automated alerts at +/- 0.5 degrees C from storage limits. Establish excursion response SOP with 4-hour documentation requirement.", "responsible_party": "Kevin O'Brien", "due_date": now + timedelta(days=5), "status": CAPAStatus.IN_PROGRESS, "completion_date": None, "verification_date": None, "verified_by": None, "effectiveness_evidence": None},
            {"id": "CAPA-009", "finding_id": "FND-011", "audit_id": "AUD-006", "corrective_action": "Terminate shared credentials immediately. Issue unique credentials to all affected users.", "preventive_action": "Deploy multi-factor authentication for EDC system. Implement automated detection of concurrent sessions from same credentials.", "responsible_party": "David Park", "due_date": now - timedelta(days=10), "status": CAPAStatus.COMPLETED, "completion_date": now - timedelta(days=12), "verification_date": None, "verified_by": None, "effectiveness_evidence": None},
            {"id": "CAPA-010", "finding_id": "FND-005", "audit_id": "AUD-002", "corrective_action": "Complete stability assessment for excursion event and document results in IP accountability log", "preventive_action": "Update excursion response SOP to require stability assessment initiation within 48 hours. Add excursion tracking to site management dashboard.", "responsible_party": "Mark Stevens", "due_date": now - timedelta(days=50), "status": CAPAStatus.CLOSED, "completion_date": now - timedelta(days=55), "verification_date": now - timedelta(days=45), "verified_by": "Robert Kim", "effectiveness_evidence": "Subsequent excursion events (2) were assessed within 24 hours. Updated SOP followed correctly."},
        ]

        for c in capas_data:
            self._capas[c["id"]] = AuditCAPA(**c)

        # --- 6 Audit Reports ---
        reports_data = [
            {"id": "RPT-001", "audit_id": "AUD-001", "report_number": "AUD-001-RPT", "title": "Routine GCP Audit Report - Bascom Palmer Eye Institute (EYLEA HD)", "executive_summary": "Routine GCP audit of Site-101 identified 1 minor finding related to consent form version control and 1 observation regarding source data transcription. Overall site compliance is satisfactory with well-maintained essential documents and strong investigator oversight.", "status": ReportStatus.DISTRIBUTED, "author": "Jennifer Walsh", "reviewed_by": "Robert Kim", "approved_by": "VP Quality Assurance", "approved_date": now - timedelta(days=100), "total_findings": 2, "critical_findings": 0, "major_findings": 0, "minor_findings": 1, "observations": 1, "distribution_list": ["VP Quality Assurance", "Medical Monitor", "Clinical Operations Lead", "Site File"], "created_at": now - timedelta(days=110)},
            {"id": "RPT-002", "audit_id": "AUD-002", "report_number": "AUD-002-RPT", "title": "For-Cause Audit Report - Wills Eye Hospital (EYLEA HD)", "executive_summary": "For-cause audit triggered by protocol deviation trends identified 2 major findings related to eligibility verification and randomization access controls, and 1 minor finding on IP temperature excursion response. CAPAs have been initiated for all findings.", "status": ReportStatus.APPROVED, "author": "Robert Kim", "reviewed_by": "Jennifer Walsh", "approved_by": "VP Quality Assurance", "approved_date": now - timedelta(days=70), "total_findings": 3, "critical_findings": 0, "major_findings": 2, "minor_findings": 1, "observations": 0, "distribution_list": ["VP Quality Assurance", "Medical Monitor", "Clinical Operations Lead"], "created_at": now - timedelta(days=80)},
            {"id": "RPT-003", "audit_id": "AUD-003", "report_number": "AUD-003-RPT", "title": "FDA Pre-Approval Inspection Report - Cole Eye Institute (EYLEA HD)", "executive_summary": "FDA inspection identified 1 critical finding on data integrity (audit trail discrepancies) and 1 major finding on SAE reporting delays. Immediate corrective actions initiated. Formal FDA response (CAPA plan) submitted within 15 business days.", "status": ReportStatus.DISTRIBUTED, "author": "Jennifer Walsh", "reviewed_by": "VP Quality Assurance", "approved_by": "Chief Medical Officer", "approved_date": now - timedelta(days=40), "total_findings": 2, "critical_findings": 1, "major_findings": 1, "minor_findings": 0, "observations": 0, "distribution_list": ["Chief Medical Officer", "VP Quality Assurance", "VP Regulatory Affairs", "Medical Monitor", "Clinical Operations Lead", "Legal"], "created_at": now - timedelta(days=50)},
            {"id": "RPT-004", "audit_id": "AUD-005", "report_number": "AUD-005-RPT", "title": "Routine GCP Audit Report - NYU Langone Dermatology (Dupixent)", "executive_summary": "Routine audit showed good GCP compliance overall. 1 minor finding on EASI scoring variability and 1 observation on IP dispensing documentation gaps. Site demonstrated strong investigator engagement and organized trial master file.", "status": ReportStatus.DISTRIBUTED, "author": "Patricia Hernandez", "reviewed_by": "David Park", "approved_by": "VP Quality Assurance", "approved_date": now - timedelta(days=80), "total_findings": 2, "critical_findings": 0, "major_findings": 0, "minor_findings": 1, "observations": 1, "distribution_list": ["VP Quality Assurance", "Medical Monitor", "Clinical Operations Lead", "Site File"], "created_at": now - timedelta(days=90)},
            {"id": "RPT-005", "audit_id": "AUD-009", "report_number": "AUD-009-RPT", "title": "Routine GCP Audit Report - Memorial Sloan Kettering (Libtayo)", "executive_summary": "Routine audit found minor RECIST measurement variability and a brief biospecimen monitoring gap. Overall compliance is strong with exemplary safety reporting practices and well-organized source documentation.", "status": ReportStatus.DISTRIBUTED, "author": "Thomas Grant", "reviewed_by": "Maria Santos", "approved_by": "VP Quality Assurance", "approved_date": now - timedelta(days=60), "total_findings": 2, "critical_findings": 0, "major_findings": 0, "minor_findings": 1, "observations": 1, "distribution_list": ["VP Quality Assurance", "Medical Monitor", "Clinical Operations Lead", "Site File"], "created_at": now - timedelta(days=70)},
            {"id": "RPT-006", "audit_id": "AUD-010", "report_number": "AUD-010-RPT", "title": "EMA GCP Inspection Report - MD Anderson Cancer Center (Libtayo)", "executive_summary": "EMA inspection revealed 1 critical finding on irAE grading practices and 1 major finding on IP temperature monitoring. Immediate corrective actions implemented. Formal EMA response submitted.", "status": ReportStatus.APPROVED, "author": "Thomas Grant", "reviewed_by": "VP Quality Assurance", "approved_by": "Chief Medical Officer", "approved_date": now - timedelta(days=30), "total_findings": 2, "critical_findings": 1, "major_findings": 1, "minor_findings": 0, "observations": 0, "distribution_list": ["Chief Medical Officer", "VP Quality Assurance", "VP Regulatory Affairs", "Medical Monitor"], "created_at": now - timedelta(days=40)},
        ]

        for r in reports_data:
            self._reports[r["id"]] = AuditReport(**r)

    # ------------------------------------------------------------------
    # Audit CRUD
    # ------------------------------------------------------------------

    def list_audits(
        self,
        *,
        trial_id: str | None = None,
        status: AuditStatus | None = None,
        audit_type: AuditType | None = None,
    ) -> list[SiteAudit]:
        """List site audits with optional filters."""
        with self._lock:
            result = list(self._audits.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if status is not None:
            result = [a for a in result if a.status == status]
        if audit_type is not None:
            result = [a for a in result if a.audit_type == audit_type]

        return sorted(result, key=lambda a: a.planned_date, reverse=True)

    def get_audit(self, audit_id: str) -> SiteAudit | None:
        """Get a single audit by ID."""
        with self._lock:
            return self._audits.get(audit_id)

    def create_audit(self, payload: SiteAuditCreate) -> SiteAudit:
        """Create a new site audit."""
        now = datetime.now(timezone.utc)
        audit_id = f"AUD-{uuid4().hex[:8].upper()}"
        audit = SiteAudit(
            id=audit_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            site_name=payload.site_name,
            audit_type=payload.audit_type,
            status=AuditStatus.PLANNED,
            planned_date=payload.planned_date,
            actual_start_date=None,
            actual_end_date=None,
            lead_auditor=payload.lead_auditor,
            audit_team=payload.audit_team,
            scope=payload.scope,
            regulatory_authority=payload.regulatory_authority,
            created_at=now,
        )
        with self._lock:
            self._audits[audit_id] = audit
        logger.info("Created site audit %s for site %s", audit_id, payload.site_id)
        return audit

    def update_audit(
        self, audit_id: str, payload: SiteAuditUpdate
    ) -> SiteAudit | None:
        """Update an existing audit."""
        with self._lock:
            existing = self._audits.get(audit_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SiteAudit(**data)
            self._audits[audit_id] = updated
        return updated

    def delete_audit(self, audit_id: str) -> bool:
        """Delete an audit. Returns True if deleted."""
        with self._lock:
            if audit_id in self._audits:
                del self._audits[audit_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Finding CRUD
    # ------------------------------------------------------------------

    def list_findings(
        self,
        *,
        audit_id: str | None = None,
        classification: FindingClassification | None = None,
        status: FindingStatus | None = None,
    ) -> list[AuditFinding]:
        """List audit findings with optional filters."""
        with self._lock:
            result = list(self._findings.values())

        if audit_id is not None:
            result = [f for f in result if f.audit_id == audit_id]
        if classification is not None:
            result = [f for f in result if f.classification == classification]
        if status is not None:
            result = [f for f in result if f.status == status]

        return sorted(result, key=lambda f: f.created_at, reverse=True)

    def get_finding(self, finding_id: str) -> AuditFinding | None:
        """Get a single finding by ID."""
        with self._lock:
            return self._findings.get(finding_id)

    def create_finding(self, payload: AuditFindingCreate) -> AuditFinding:
        """Create a new audit finding."""
        now = datetime.now(timezone.utc)
        finding_id = f"FND-{uuid4().hex[:8].upper()}"
        finding = AuditFinding(
            id=finding_id,
            audit_id=payload.audit_id,
            finding_number=payload.finding_number,
            classification=payload.classification,
            area=payload.area,
            description=payload.description,
            evidence=payload.evidence,
            regulation_reference=payload.regulation_reference,
            status=FindingStatus.OPEN,
            response_deadline=payload.response_deadline,
            site_response=None,
            created_at=now,
        )
        with self._lock:
            self._findings[finding_id] = finding
        logger.info("Created audit finding %s for audit %s", finding_id, payload.audit_id)
        return finding

    def update_finding(
        self, finding_id: str, payload: AuditFindingUpdate
    ) -> AuditFinding | None:
        """Update an existing finding."""
        with self._lock:
            existing = self._findings.get(finding_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = AuditFinding(**data)
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
    # CAPA CRUD
    # ------------------------------------------------------------------

    def list_capas(
        self,
        *,
        audit_id: str | None = None,
        finding_id: str | None = None,
        status: CAPAStatus | None = None,
    ) -> list[AuditCAPA]:
        """List CAPAs with optional filters."""
        with self._lock:
            result = list(self._capas.values())

        if audit_id is not None:
            result = [c for c in result if c.audit_id == audit_id]
        if finding_id is not None:
            result = [c for c in result if c.finding_id == finding_id]
        if status is not None:
            result = [c for c in result if c.status == status]

        return sorted(result, key=lambda c: c.due_date, reverse=True)

    def get_capa(self, capa_id: str) -> AuditCAPA | None:
        """Get a single CAPA by ID."""
        with self._lock:
            return self._capas.get(capa_id)

    def create_capa(self, payload: AuditCAPACreate) -> AuditCAPA:
        """Create a new CAPA."""
        capa_id = f"CAPA-{uuid4().hex[:8].upper()}"
        capa = AuditCAPA(
            id=capa_id,
            finding_id=payload.finding_id,
            audit_id=payload.audit_id,
            corrective_action=payload.corrective_action,
            preventive_action=payload.preventive_action,
            responsible_party=payload.responsible_party,
            due_date=payload.due_date,
            status=CAPAStatus.PLANNED,
            completion_date=None,
            verification_date=None,
            verified_by=None,
            effectiveness_evidence=None,
        )
        with self._lock:
            self._capas[capa_id] = capa
        logger.info("Created CAPA %s for finding %s", capa_id, payload.finding_id)
        return capa

    def update_capa(
        self, capa_id: str, payload: AuditCAPAUpdate
    ) -> AuditCAPA | None:
        """Update an existing CAPA."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._capas.get(capa_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set completion_date when status moves to completed
            if "status" in updates:
                if updates["status"] == CAPAStatus.COMPLETED and existing.completion_date is None:
                    updates["completion_date"] = now
                if updates["status"] == CAPAStatus.VERIFIED and existing.verification_date is None:
                    updates["verification_date"] = now

            data.update(updates)
            updated = AuditCAPA(**data)
            self._capas[capa_id] = updated
        return updated

    def delete_capa(self, capa_id: str) -> bool:
        """Delete a CAPA. Returns True if deleted."""
        with self._lock:
            if capa_id in self._capas:
                del self._capas[capa_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Report CRUD
    # ------------------------------------------------------------------

    def list_reports(
        self,
        *,
        audit_id: str | None = None,
        status: ReportStatus | None = None,
    ) -> list[AuditReport]:
        """List audit reports with optional filters."""
        with self._lock:
            result = list(self._reports.values())

        if audit_id is not None:
            result = [r for r in result if r.audit_id == audit_id]
        if status is not None:
            result = [r for r in result if r.status == status]

        return sorted(result, key=lambda r: r.created_at, reverse=True)

    def get_report(self, report_id: str) -> AuditReport | None:
        """Get a single report by ID."""
        with self._lock:
            return self._reports.get(report_id)

    def create_report(self, payload: AuditReportCreate) -> AuditReport:
        """Create a new audit report."""
        now = datetime.now(timezone.utc)
        report_id = f"RPT-{uuid4().hex[:8].upper()}"
        report = AuditReport(
            id=report_id,
            audit_id=payload.audit_id,
            report_number=payload.report_number,
            title=payload.title,
            executive_summary=payload.executive_summary,
            status=ReportStatus.DRAFT,
            author=payload.author,
            reviewed_by=None,
            approved_by=None,
            approved_date=None,
            total_findings=0,
            critical_findings=0,
            major_findings=0,
            minor_findings=0,
            observations=0,
            distribution_list=[],
            created_at=now,
        )
        with self._lock:
            self._reports[report_id] = report
        logger.info("Created audit report %s for audit %s", report_id, payload.audit_id)
        return report

    def update_report(
        self, report_id: str, payload: AuditReportUpdate
    ) -> AuditReport | None:
        """Update an existing report."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._reports.get(report_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set approved_date when status moves to approved
            if "status" in updates:
                if updates["status"] == ReportStatus.APPROVED and existing.approved_date is None:
                    updates["approved_date"] = now

            data.update(updates)
            updated = AuditReport(**data)
            self._reports[report_id] = updated
        return updated

    def delete_report(self, report_id: str) -> bool:
        """Delete a report. Returns True if deleted."""
        with self._lock:
            if report_id in self._reports:
                del self._reports[report_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> SiteAuditMetrics:
        """Compute aggregated site audit metrics."""
        with self._lock:
            audits = list(self._audits.values())
            findings = list(self._findings.values())
            capas = list(self._capas.values())
            reports = list(self._reports.values())

        # Filter by trial if specified
        if trial_id is not None:
            audit_ids = {a.id for a in audits if a.trial_id == trial_id}
            audits = [a for a in audits if a.trial_id == trial_id]
            findings = [f for f in findings if f.audit_id in audit_ids]
            capas = [c for c in capas if c.audit_id in audit_ids]
            reports = [r for r in reports if r.audit_id in audit_ids]

        # Audits by type
        audits_by_type: dict[str, int] = {}
        for a in audits:
            key = a.audit_type.value
            audits_by_type[key] = audits_by_type.get(key, 0) + 1

        # Audits by status
        audits_by_status: dict[str, int] = {}
        for a in audits:
            key = a.status.value
            audits_by_status[key] = audits_by_status.get(key, 0) + 1

        # Findings by classification
        findings_by_classification: dict[str, int] = {}
        for f in findings:
            key = f.classification.value
            findings_by_classification[key] = findings_by_classification.get(key, 0) + 1

        # Open/closed findings
        open_findings = sum(1 for f in findings if f.status != FindingStatus.CLOSED)
        closed_findings = sum(1 for f in findings if f.status == FindingStatus.CLOSED)

        # CAPA metrics
        open_capas = sum(
            1 for c in capas
            if c.status not in (CAPAStatus.CLOSED, CAPAStatus.VERIFIED)
        )
        overdue_capas = sum(
            1 for c in capas
            if c.status == CAPAStatus.OVERDUE
            or (
                c.status not in (CAPAStatus.CLOSED, CAPAStatus.VERIFIED, CAPAStatus.COMPLETED)
                and c.due_date < datetime.now(timezone.utc)
            )
        )

        # Report metrics
        approved_reports = sum(
            1 for r in reports
            if r.status in (ReportStatus.APPROVED, ReportStatus.DISTRIBUTED)
        )

        # Avg findings per audit
        avg_findings = (
            len(findings) / len(audits) if audits else 0.0
        )

        return SiteAuditMetrics(
            total_audits=len(audits),
            audits_by_type=audits_by_type,
            audits_by_status=audits_by_status,
            total_findings=len(findings),
            findings_by_classification=findings_by_classification,
            open_findings=open_findings,
            closed_findings=closed_findings,
            total_capas=len(capas),
            open_capas=open_capas,
            overdue_capas=overdue_capas,
            total_reports=len(reports),
            approved_reports=approved_reports,
            avg_findings_per_audit=round(avg_findings, 1),
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: SiteAuditService | None = None
_instance_lock = threading.Lock()


def get_site_audit_service() -> SiteAuditService:
    """Return the singleton SiteAuditService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = SiteAuditService()
    return _instance


def reset_site_audit_service() -> SiteAuditService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = SiteAuditService()
    return _instance
