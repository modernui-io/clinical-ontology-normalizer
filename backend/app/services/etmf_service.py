"""Electronic Trial Master File (eTMF) Service (CLINICAL-5).

Manages TMF documents, compliance rules, inspection checklists, and metrics
per the DIA TMF Reference Model across all 11 zones for clinical trials.

Singleton service with in-memory storage and comprehensive seed data for
three Regeneron trial programs.

Usage:
    from app.services.etmf_service import get_etmf_service

    svc = get_etmf_service()
    doc = svc.create_document(...)
    metrics = svc.get_metrics(trial_id=...)
"""

from __future__ import annotations

import logging
import threading
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.etmf import (
    ArtifactType,
    BulkImportRequest,
    BulkImportResponse,
    ComplianceRule,
    ComplianceRuleCreate,
    ComplianceRuleUpdate,
    ComplianceStatus,
    DocumentApprovalRequest,
    DocumentReviewRequest,
    DocumentSignature,
    DocumentStatus,
    ExpiringDocumentsResponse,
    InspectionChecklist,
    InspectionChecklistCreate,
    InspectionFinding,
    InspectionFindingCreate,
    InspectionReadiness,
    MissingDocumentsResponse,
    SignatureRequest,
    SignatureType,
    TMFDocument,
    TMFDocumentCreate,
    TMFDocumentUpdate,
    TMFMetrics,
    TMFSection,
    TMFZone,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Valid status transitions
# ---------------------------------------------------------------------------

VALID_STATUS_TRANSITIONS: dict[DocumentStatus, set[DocumentStatus]] = {
    DocumentStatus.DRAFT: {
        DocumentStatus.UNDER_REVIEW,
        DocumentStatus.WITHDRAWN,
    },
    DocumentStatus.UNDER_REVIEW: {
        DocumentStatus.DRAFT,
        DocumentStatus.APPROVED,
        DocumentStatus.WITHDRAWN,
    },
    DocumentStatus.APPROVED: {
        DocumentStatus.EFFECTIVE,
        DocumentStatus.SUPERSEDED,
        DocumentStatus.WITHDRAWN,
    },
    DocumentStatus.EFFECTIVE: {
        DocumentStatus.SUPERSEDED,
        DocumentStatus.ARCHIVED,
    },
    DocumentStatus.SUPERSEDED: {
        DocumentStatus.ARCHIVED,
    },
    DocumentStatus.ARCHIVED: set(),  # terminal
    DocumentStatus.WITHDRAWN: set(),  # terminal
}

# ---------------------------------------------------------------------------
# Trial IDs (Regeneron demo)
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class ETMFService:
    """Electronic Trial Master File management service."""

    def __init__(self) -> None:
        self._documents: dict[str, TMFDocument] = {}
        self._compliance_rules: dict[str, ComplianceRule] = {}
        self._inspection_checklists: dict[str, InspectionChecklist] = {}
        self._lock = threading.Lock()
        self._seed_data()

    # -----------------------------------------------------------------------
    # Seed Data
    # -----------------------------------------------------------------------

    def _seed_data(self) -> None:
        """Populate demo data: 40 documents, 20 compliance rules, 2 checklists."""
        now = datetime.now(timezone.utc)
        today = date.today()

        # --- 20 Compliance Rules (covering all zones) ---
        rules_defs: list[dict] = [
            {"name": "Protocol Required", "zone": TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS, "artifact_type": ArtifactType.PROTOCOL, "required": True, "part11": True, "gdpr": False, "freq": 365, "ret": 15},
            {"name": "Informed Consent Form Required", "zone": TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS, "artifact_type": ArtifactType.ICF, "required": True, "part11": True, "gdpr": True, "freq": 180, "ret": 15},
            {"name": "Investigator Brochure Required", "zone": TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS, "artifact_type": ArtifactType.IB, "required": True, "part11": True, "gdpr": False, "freq": 365, "ret": 15},
            {"name": "IRB Approval Required", "zone": TMFZone.ZONE_03_IRB_IEC, "artifact_type": ArtifactType.IRB_APPROVAL, "required": True, "part11": True, "gdpr": False, "freq": 365, "ret": 15},
            {"name": "SAE Report Filing", "zone": TMFZone.ZONE_07_SAFETY_REPORTING, "artifact_type": ArtifactType.SAE_REPORT, "required": True, "part11": True, "gdpr": True, "freq": 0, "ret": 25},
            {"name": "CRF Completion", "zone": TMFZone.ZONE_10_DATA_MANAGEMENT, "artifact_type": ArtifactType.CRF, "required": True, "part11": True, "gdpr": True, "freq": 90, "ret": 15},
            {"name": "Statistical Analysis Plan", "zone": TMFZone.ZONE_11_STATISTICS, "artifact_type": ArtifactType.SAP, "required": True, "part11": False, "gdpr": False, "freq": 365, "ret": 15},
            {"name": "Clinical Study Report", "zone": TMFZone.ZONE_11_STATISTICS, "artifact_type": ArtifactType.CSR, "required": True, "part11": True, "gdpr": False, "freq": 0, "ret": 25},
            {"name": "Monitoring Report", "zone": TMFZone.ZONE_05_SITE_MANAGEMENT, "artifact_type": ArtifactType.MONITORING_REPORT, "required": True, "part11": False, "gdpr": False, "freq": 90, "ret": 15},
            {"name": "Delegation Log", "zone": TMFZone.ZONE_05_SITE_MANAGEMENT, "artifact_type": ArtifactType.DELEGATION_LOG, "required": True, "part11": True, "gdpr": False, "freq": 180, "ret": 15},
            {"name": "Financial Disclosure", "zone": TMFZone.ZONE_01_TRIAL_MANAGEMENT, "artifact_type": ArtifactType.FINANCIAL_DISCLOSURE, "required": True, "part11": False, "gdpr": True, "freq": 365, "ret": 15},
            {"name": "Investigator CV", "zone": TMFZone.ZONE_05_SITE_MANAGEMENT, "artifact_type": ArtifactType.CV, "required": True, "part11": False, "gdpr": True, "freq": 365, "ret": 15},
            {"name": "Medical License", "zone": TMFZone.ZONE_05_SITE_MANAGEMENT, "artifact_type": ArtifactType.MEDICAL_LICENSE, "required": True, "part11": False, "gdpr": False, "freq": 365, "ret": 15},
            {"name": "Site Contract", "zone": TMFZone.ZONE_05_SITE_MANAGEMENT, "artifact_type": ArtifactType.SITE_CONTRACT, "required": True, "part11": False, "gdpr": True, "freq": 0, "ret": 15},
            {"name": "Drug Accountability Log", "zone": TMFZone.ZONE_06_IP_MANAGEMENT, "artifact_type": ArtifactType.DRUG_ACCOUNTABILITY, "required": True, "part11": True, "gdpr": False, "freq": 90, "ret": 15},
            {"name": "Protocol Regulatory Filing", "zone": TMFZone.ZONE_04_REGULATORY, "artifact_type": ArtifactType.PROTOCOL, "required": True, "part11": True, "gdpr": False, "freq": 365, "ret": 25},
            {"name": "Lab Certification", "zone": TMFZone.ZONE_08_CENTRAL_AND_LOCAL_TESTING, "artifact_type": ArtifactType.MEDICAL_LICENSE, "required": True, "part11": False, "gdpr": False, "freq": 365, "ret": 15},
            {"name": "Third Party Agreements", "zone": TMFZone.ZONE_09_THIRD_PARTIES, "artifact_type": ArtifactType.SITE_CONTRACT, "required": True, "part11": False, "gdpr": True, "freq": 365, "ret": 15},
            {"name": "Data Management Plan", "zone": TMFZone.ZONE_10_DATA_MANAGEMENT, "artifact_type": ArtifactType.CRF, "required": True, "part11": True, "gdpr": True, "freq": 365, "ret": 15},
            {"name": "Trial Management Plan", "zone": TMFZone.ZONE_01_TRIAL_MANAGEMENT, "artifact_type": ArtifactType.PROTOCOL, "required": True, "part11": False, "gdpr": False, "freq": 365, "ret": 15},
        ]

        for i, rd in enumerate(rules_defs):
            rule_id = f"rule-{i+1:03d}"
            self._compliance_rules[rule_id] = ComplianceRule(
                id=rule_id,
                name=rd["name"],
                zone=rd["zone"],
                artifact_type=rd["artifact_type"],
                description=f"Compliance rule: {rd['name']}",
                required=rd["required"],
                review_frequency_days=rd["freq"],
                retention_years=rd["ret"],
                part11_requirement=rd["part11"],
                gdpr_requirement=rd["gdpr"],
            )

        # --- 40 TMF Documents across all 11 zones for 3 trials ---
        docs_defs: list[dict] = [
            # ZONE 01 - Trial Management (4 docs)
            {"trial": EYLEA_TRIAL, "zone": TMFZone.ZONE_01_TRIAL_MANAGEMENT, "art": ArtifactType.FINANCIAL_DISCLOSURE, "title": "Eylea HD Financial Disclosure - PI Smith", "status": DocumentStatus.EFFECTIVE, "p11": True, "gdpr": True, "days_ago": 120, "expiry_days": 45},
            {"trial": EYLEA_TRIAL, "zone": TMFZone.ZONE_01_TRIAL_MANAGEMENT, "art": ArtifactType.PROTOCOL, "title": "Eylea HD Trial Management Plan v2.0", "status": DocumentStatus.EFFECTIVE, "p11": True, "gdpr": False, "days_ago": 90, "expiry_days": 200},
            {"trial": DUPIXENT_TRIAL, "zone": TMFZone.ZONE_01_TRIAL_MANAGEMENT, "art": ArtifactType.FINANCIAL_DISCLOSURE, "title": "Dupixent Financial Disclosure - PI Johnson", "status": DocumentStatus.APPROVED, "p11": True, "gdpr": True, "days_ago": 60, "expiry_days": 300},
            {"trial": LIBTAYO_TRIAL, "zone": TMFZone.ZONE_01_TRIAL_MANAGEMENT, "art": ArtifactType.PROTOCOL, "title": "Libtayo Trial Management Plan v1.0", "status": DocumentStatus.DRAFT, "p11": False, "gdpr": False, "days_ago": 5, "expiry_days": None},
            # ZONE 02 - Central Trial Docs (6 docs)
            {"trial": EYLEA_TRIAL, "zone": TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS, "art": ArtifactType.PROTOCOL, "title": "Eylea HD Phase III Protocol v3.1", "status": DocumentStatus.EFFECTIVE, "p11": True, "gdpr": False, "days_ago": 180, "expiry_days": 180},
            {"trial": EYLEA_TRIAL, "zone": TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS, "art": ArtifactType.ICF, "title": "Eylea HD Informed Consent Form v2.0", "status": DocumentStatus.EFFECTIVE, "p11": True, "gdpr": True, "days_ago": 150, "expiry_days": 90},
            {"trial": EYLEA_TRIAL, "zone": TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS, "art": ArtifactType.IB, "title": "Eylea HD Investigator Brochure v5.0", "status": DocumentStatus.EFFECTIVE, "p11": True, "gdpr": False, "days_ago": 200, "expiry_days": 60},
            {"trial": DUPIXENT_TRIAL, "zone": TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS, "art": ArtifactType.PROTOCOL, "title": "Dupixent Atopic Dermatitis Protocol v2.0", "status": DocumentStatus.EFFECTIVE, "p11": True, "gdpr": False, "days_ago": 100, "expiry_days": 250},
            {"trial": DUPIXENT_TRIAL, "zone": TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS, "art": ArtifactType.ICF, "title": "Dupixent AD ICF v1.3", "status": DocumentStatus.UNDER_REVIEW, "p11": True, "gdpr": True, "days_ago": 20, "expiry_days": None},
            {"trial": LIBTAYO_TRIAL, "zone": TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS, "art": ArtifactType.PROTOCOL, "title": "Libtayo NSCLC Protocol v1.0", "status": DocumentStatus.APPROVED, "p11": True, "gdpr": False, "days_ago": 30, "expiry_days": 365},
            # ZONE 03 - IRB/IEC (3 docs)
            {"trial": EYLEA_TRIAL, "zone": TMFZone.ZONE_03_IRB_IEC, "art": ArtifactType.IRB_APPROVAL, "title": "IRB Approval - Eylea HD Protocol v3.1", "status": DocumentStatus.EFFECTIVE, "p11": True, "gdpr": False, "days_ago": 175, "expiry_days": 185},
            {"trial": DUPIXENT_TRIAL, "zone": TMFZone.ZONE_03_IRB_IEC, "art": ArtifactType.IRB_APPROVAL, "title": "IRB Approval - Dupixent AD Protocol v2.0", "status": DocumentStatus.EFFECTIVE, "p11": True, "gdpr": False, "days_ago": 95, "expiry_days": 270},
            {"trial": LIBTAYO_TRIAL, "zone": TMFZone.ZONE_03_IRB_IEC, "art": ArtifactType.IRB_APPROVAL, "title": "IRB Approval - Libtayo NSCLC Protocol", "status": DocumentStatus.DRAFT, "p11": False, "gdpr": False, "days_ago": 10, "expiry_days": None},
            {"trial": EYLEA_TRIAL, "zone": TMFZone.ZONE_03_IRB_IEC, "art": ArtifactType.IRB_APPROVAL, "title": "IRB Amendment Approval - Eylea HD Protocol v3.1 Amendment 2", "status": DocumentStatus.APPROVED, "p11": True, "gdpr": False, "days_ago": 30, "expiry_days": 335},
            # ZONE 04 - Regulatory (3 docs)
            {"trial": EYLEA_TRIAL, "zone": TMFZone.ZONE_04_REGULATORY, "art": ArtifactType.PROTOCOL, "title": "FDA IND Submission - Eylea HD", "status": DocumentStatus.EFFECTIVE, "p11": True, "gdpr": False, "days_ago": 365, "expiry_days": 365},
            {"trial": DUPIXENT_TRIAL, "zone": TMFZone.ZONE_04_REGULATORY, "art": ArtifactType.PROTOCOL, "title": "FDA IND Submission - Dupixent AD", "status": DocumentStatus.EFFECTIVE, "p11": True, "gdpr": False, "days_ago": 300, "expiry_days": 400},
            {"trial": LIBTAYO_TRIAL, "zone": TMFZone.ZONE_04_REGULATORY, "art": ArtifactType.PROTOCOL, "title": "EMA IMPD - Libtayo NSCLC", "status": DocumentStatus.UNDER_REVIEW, "p11": True, "gdpr": True, "days_ago": 15, "expiry_days": None},
            # ZONE 05 - Site Management (6 docs)
            {"trial": EYLEA_TRIAL, "zone": TMFZone.ZONE_05_SITE_MANAGEMENT, "art": ArtifactType.MONITORING_REPORT, "title": "Site 001 Monitoring Visit Report #5", "status": DocumentStatus.APPROVED, "p11": False, "gdpr": False, "days_ago": 14, "expiry_days": None},
            {"trial": EYLEA_TRIAL, "zone": TMFZone.ZONE_05_SITE_MANAGEMENT, "art": ArtifactType.DELEGATION_LOG, "title": "Eylea HD Delegation Log - Site 001", "status": DocumentStatus.EFFECTIVE, "p11": True, "gdpr": False, "days_ago": 60, "expiry_days": 120},
            {"trial": EYLEA_TRIAL, "zone": TMFZone.ZONE_05_SITE_MANAGEMENT, "art": ArtifactType.CV, "title": "Dr. Smith CV - Principal Investigator", "status": DocumentStatus.EFFECTIVE, "p11": False, "gdpr": True, "days_ago": 200, "expiry_days": 25},
            {"trial": DUPIXENT_TRIAL, "zone": TMFZone.ZONE_05_SITE_MANAGEMENT, "art": ArtifactType.SITE_CONTRACT, "title": "Dupixent Site 002 Clinical Trial Agreement", "status": DocumentStatus.EFFECTIVE, "p11": False, "gdpr": True, "days_ago": 150, "expiry_days": 400},
            {"trial": DUPIXENT_TRIAL, "zone": TMFZone.ZONE_05_SITE_MANAGEMENT, "art": ArtifactType.MEDICAL_LICENSE, "title": "Dr. Johnson Medical License", "status": DocumentStatus.EFFECTIVE, "p11": False, "gdpr": False, "days_ago": 250, "expiry_days": 15},
            {"trial": LIBTAYO_TRIAL, "zone": TMFZone.ZONE_05_SITE_MANAGEMENT, "art": ArtifactType.MONITORING_REPORT, "title": "Libtayo Site Selection Visit Report", "status": DocumentStatus.DRAFT, "p11": False, "gdpr": False, "days_ago": 3, "expiry_days": None},
            # ZONE 06 - IP Management (3 docs)
            {"trial": EYLEA_TRIAL, "zone": TMFZone.ZONE_06_IP_MANAGEMENT, "art": ArtifactType.DRUG_ACCOUNTABILITY, "title": "Eylea HD Drug Accountability Log - Site 001", "status": DocumentStatus.EFFECTIVE, "p11": True, "gdpr": False, "days_ago": 30, "expiry_days": 60},
            {"trial": DUPIXENT_TRIAL, "zone": TMFZone.ZONE_06_IP_MANAGEMENT, "art": ArtifactType.DRUG_ACCOUNTABILITY, "title": "Dupixent Drug Accountability Log - Site 002", "status": DocumentStatus.EFFECTIVE, "p11": True, "gdpr": False, "days_ago": 45, "expiry_days": 45},
            {"trial": LIBTAYO_TRIAL, "zone": TMFZone.ZONE_06_IP_MANAGEMENT, "art": ArtifactType.DRUG_ACCOUNTABILITY, "title": "Libtayo Drug Accountability Log - Site 003", "status": DocumentStatus.DRAFT, "p11": False, "gdpr": False, "days_ago": 2, "expiry_days": None},
            # ZONE 07 - Safety Reporting (3 docs)
            {"trial": EYLEA_TRIAL, "zone": TMFZone.ZONE_07_SAFETY_REPORTING, "art": ArtifactType.SAE_REPORT, "title": "SAE Report #001 - Eylea HD Ocular Event", "status": DocumentStatus.EFFECTIVE, "p11": True, "gdpr": True, "days_ago": 45, "expiry_days": None},
            {"trial": DUPIXENT_TRIAL, "zone": TMFZone.ZONE_07_SAFETY_REPORTING, "art": ArtifactType.SAE_REPORT, "title": "SAE Report #003 - Dupixent Allergic Reaction", "status": DocumentStatus.APPROVED, "p11": True, "gdpr": True, "days_ago": 20, "expiry_days": None},
            {"trial": LIBTAYO_TRIAL, "zone": TMFZone.ZONE_07_SAFETY_REPORTING, "art": ArtifactType.SAE_REPORT, "title": "SAE Report #005 - Libtayo Immune Event", "status": DocumentStatus.UNDER_REVIEW, "p11": True, "gdpr": True, "days_ago": 5, "expiry_days": None},
            # ZONE 08 - Central & Local Testing (2 docs)
            {"trial": EYLEA_TRIAL, "zone": TMFZone.ZONE_08_CENTRAL_AND_LOCAL_TESTING, "art": ArtifactType.MEDICAL_LICENSE, "title": "Central Lab Certification - Quest Diagnostics", "status": DocumentStatus.EFFECTIVE, "p11": False, "gdpr": False, "days_ago": 300, "expiry_days": 65},
            {"trial": DUPIXENT_TRIAL, "zone": TMFZone.ZONE_08_CENTRAL_AND_LOCAL_TESTING, "art": ArtifactType.MEDICAL_LICENSE, "title": "Local Lab Accreditation - Site 002", "status": DocumentStatus.EFFECTIVE, "p11": False, "gdpr": False, "days_ago": 200, "expiry_days": 165},
            {"trial": LIBTAYO_TRIAL, "zone": TMFZone.ZONE_08_CENTRAL_AND_LOCAL_TESTING, "art": ArtifactType.MEDICAL_LICENSE, "title": "Libtayo Central Lab Certification - Covance", "status": DocumentStatus.DRAFT, "p11": False, "gdpr": False, "days_ago": 8, "expiry_days": None},
            # ZONE 09 - Third Parties (2 docs)
            {"trial": EYLEA_TRIAL, "zone": TMFZone.ZONE_09_THIRD_PARTIES, "art": ArtifactType.SITE_CONTRACT, "title": "CRO Agreement - Eylea HD (Parexel)", "status": DocumentStatus.EFFECTIVE, "p11": False, "gdpr": True, "days_ago": 365, "expiry_days": 365},
            {"trial": DUPIXENT_TRIAL, "zone": TMFZone.ZONE_09_THIRD_PARTIES, "art": ArtifactType.SITE_CONTRACT, "title": "IXRS Vendor Agreement - Dupixent", "status": DocumentStatus.EFFECTIVE, "p11": False, "gdpr": True, "days_ago": 200, "expiry_days": 500},
            # ZONE 10 - Data Management (3 docs)
            {"trial": EYLEA_TRIAL, "zone": TMFZone.ZONE_10_DATA_MANAGEMENT, "art": ArtifactType.CRF, "title": "Eylea HD Electronic CRF Specification v2.0", "status": DocumentStatus.EFFECTIVE, "p11": True, "gdpr": True, "days_ago": 150, "expiry_days": 210},
            {"trial": DUPIXENT_TRIAL, "zone": TMFZone.ZONE_10_DATA_MANAGEMENT, "art": ArtifactType.CRF, "title": "Dupixent eCRF Specification v1.5", "status": DocumentStatus.EFFECTIVE, "p11": True, "gdpr": True, "days_ago": 100, "expiry_days": 265},
            {"trial": LIBTAYO_TRIAL, "zone": TMFZone.ZONE_10_DATA_MANAGEMENT, "art": ArtifactType.CRF, "title": "Libtayo CRF Design Draft", "status": DocumentStatus.DRAFT, "p11": False, "gdpr": False, "days_ago": 7, "expiry_days": None},
            # ZONE 11 - Statistics (3 docs)
            {"trial": EYLEA_TRIAL, "zone": TMFZone.ZONE_11_STATISTICS, "art": ArtifactType.SAP, "title": "Eylea HD Statistical Analysis Plan v2.1", "status": DocumentStatus.EFFECTIVE, "p11": False, "gdpr": False, "days_ago": 90, "expiry_days": 275},
            {"trial": EYLEA_TRIAL, "zone": TMFZone.ZONE_11_STATISTICS, "art": ArtifactType.CSR, "title": "Eylea HD Interim CSR", "status": DocumentStatus.UNDER_REVIEW, "p11": True, "gdpr": False, "days_ago": 10, "expiry_days": None},
            {"trial": DUPIXENT_TRIAL, "zone": TMFZone.ZONE_11_STATISTICS, "art": ArtifactType.SAP, "title": "Dupixent AD SAP v1.0", "status": DocumentStatus.APPROVED, "p11": False, "gdpr": False, "days_ago": 40, "expiry_days": 325},
        ]

        for i, dd in enumerate(docs_defs):
            doc_id = f"tmf-doc-{i+1:03d}"
            uploaded_at = now - timedelta(days=dd["days_ago"])
            expiry = today + timedelta(days=dd["expiry_days"]) if dd["expiry_days"] is not None else None

            # Build signatures for effective / approved docs
            sigs: list[DocumentSignature] = []
            if dd["status"] in (DocumentStatus.EFFECTIVE, DocumentStatus.APPROVED):
                sigs.append(DocumentSignature(
                    signer_name="Dr. Sarah Mitchell",
                    signer_role="Sponsor Medical Monitor",
                    signature_type=SignatureType.ELECTRONIC,
                    signed_at=uploaded_at + timedelta(days=5),
                    reason="approval",
                ))

            effective_date = (uploaded_at + timedelta(days=10)).date() if dd["status"] == DocumentStatus.EFFECTIVE else None
            approved_at_val = uploaded_at + timedelta(days=7) if dd["status"] in (DocumentStatus.APPROVED, DocumentStatus.EFFECTIVE) else None
            reviewed_at_val = uploaded_at + timedelta(days=3) if dd["status"] not in (DocumentStatus.DRAFT,) else None

            compliance = ComplianceStatus.COMPLIANT if dd["p11"] else ComplianceStatus.NOT_ASSESSED

            self._documents[doc_id] = TMFDocument(
                id=doc_id,
                trial_id=dd["trial"],
                zone=dd["zone"],
                artifact_type=dd["art"],
                title=dd["title"],
                description=f"Auto-generated seed document for {dd['title']}",
                version="1.0",
                status=dd["status"],
                file_path=f"/tmf/{dd['trial']}/{dd['zone'].value}/{doc_id}.pdf",
                file_size_bytes=50000 + i * 12345,
                mime_type="application/pdf",
                uploaded_by="seed_system",
                uploaded_at=uploaded_at,
                reviewed_by="Dr. Review Panel" if reviewed_at_val else None,
                reviewed_at=reviewed_at_val,
                approved_by="Dr. Sarah Mitchell" if approved_at_val else None,
                approved_at=approved_at_val,
                effective_date=effective_date,
                expiry_date=expiry,
                site_id=f"SITE-{(i % 5) + 1:03d}" if dd["zone"] in (TMFZone.ZONE_05_SITE_MANAGEMENT, TMFZone.ZONE_06_IP_MANAGEMENT) else None,
                country="US" if i % 3 == 0 else ("EU" if i % 3 == 1 else "UK"),
                signatures=sigs,
                metadata_tags={"source": "seed", "zone": dd["zone"].value},
                compliance_status=compliance,
                part11_compliant=dd["p11"],
                gdpr_compliant=dd["gdpr"],
            )

        # --- 2 Inspection Checklists ---
        self._inspection_checklists["chk-001"] = InspectionChecklist(
            id="chk-001",
            trial_id=EYLEA_TRIAL,
            inspector_name="FDA Inspector Williams",
            inspection_type="routine",
            inspection_date=today + timedelta(days=30),
            zones_reviewed=[
                TMFZone.ZONE_01_TRIAL_MANAGEMENT,
                TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS,
                TMFZone.ZONE_03_IRB_IEC,
                TMFZone.ZONE_05_SITE_MANAGEMENT,
                TMFZone.ZONE_07_SAFETY_REPORTING,
            ],
            findings=[
                InspectionFinding(
                    zone=TMFZone.ZONE_05_SITE_MANAGEMENT,
                    description="PI CV nearing expiry - renewal required",
                    severity="minor",
                    corrective_action="Request updated CV from PI",
                    due_date=today + timedelta(days=14),
                    resolved=False,
                ),
                InspectionFinding(
                    zone=TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS,
                    description="IB version 5.0 approaching expiry",
                    severity="major",
                    corrective_action="Initiate IB update process",
                    due_date=today + timedelta(days=30),
                    resolved=False,
                ),
            ],
            overall_readiness=InspectionReadiness.AT_RISK,
            created_at=now - timedelta(days=7),
        )

        self._inspection_checklists["chk-002"] = InspectionChecklist(
            id="chk-002",
            trial_id=DUPIXENT_TRIAL,
            inspector_name="EMA Auditor Bergmann",
            inspection_type="pre-approval",
            inspection_date=today + timedelta(days=60),
            zones_reviewed=[
                TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS,
                TMFZone.ZONE_04_REGULATORY,
                TMFZone.ZONE_06_IP_MANAGEMENT,
                TMFZone.ZONE_10_DATA_MANAGEMENT,
                TMFZone.ZONE_11_STATISTICS,
            ],
            findings=[
                InspectionFinding(
                    zone=TMFZone.ZONE_06_IP_MANAGEMENT,
                    description="Drug accountability log review due",
                    severity="minor",
                    corrective_action="Schedule quarterly IP review",
                    due_date=today + timedelta(days=20),
                    resolved=False,
                ),
            ],
            overall_readiness=InspectionReadiness.IN_PREPARATION,
            created_at=now - timedelta(days=3),
        )

        logger.info(
            "eTMF service seeded: %d documents, %d rules, %d checklists",
            len(self._documents),
            len(self._compliance_rules),
            len(self._inspection_checklists),
        )

    # -----------------------------------------------------------------------
    # Document CRUD
    # -----------------------------------------------------------------------

    def list_documents(
        self,
        trial_id: str | None = None,
        zone: TMFZone | None = None,
        artifact_type: ArtifactType | None = None,
        status: DocumentStatus | None = None,
        site_id: str | None = None,
        country: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[TMFDocument], int]:
        """List documents with optional filters."""
        with self._lock:
            docs = list(self._documents.values())

        if trial_id:
            docs = [d for d in docs if d.trial_id == trial_id]
        if zone:
            docs = [d for d in docs if d.zone == zone]
        if artifact_type:
            docs = [d for d in docs if d.artifact_type == artifact_type]
        if status:
            docs = [d for d in docs if d.status == status]
        if site_id:
            docs = [d for d in docs if d.site_id == site_id]
        if country:
            docs = [d for d in docs if d.country == country]

        total = len(docs)
        docs.sort(key=lambda d: d.uploaded_at, reverse=True)
        return docs[offset: offset + limit], total

    def get_document(self, document_id: str) -> TMFDocument | None:
        """Get a single document by ID."""
        with self._lock:
            return self._documents.get(document_id)

    def create_document(self, req: TMFDocumentCreate) -> TMFDocument:
        """Create a new TMF document."""
        now = datetime.now(timezone.utc)
        doc_id = f"tmf-doc-{uuid4().hex[:8]}"

        doc = TMFDocument(
            id=doc_id,
            trial_id=req.trial_id,
            zone=req.zone,
            artifact_type=req.artifact_type,
            title=req.title,
            description=req.description,
            version=req.version,
            status=DocumentStatus.DRAFT,
            file_path=req.file_path,
            file_size_bytes=req.file_size_bytes,
            mime_type=req.mime_type,
            uploaded_by=req.uploaded_by,
            uploaded_at=now,
            effective_date=req.effective_date,
            expiry_date=req.expiry_date,
            site_id=req.site_id,
            country=req.country,
            metadata_tags=req.metadata_tags,
            compliance_status=ComplianceStatus.NOT_ASSESSED,
            part11_compliant=False,
            gdpr_compliant=False,
        )

        with self._lock:
            self._documents[doc_id] = doc
        logger.info("Created TMF document %s: %s", doc_id, req.title)
        return doc

    def update_document(self, document_id: str, req: TMFDocumentUpdate) -> TMFDocument | None:
        """Update a TMF document."""
        with self._lock:
            doc = self._documents.get(document_id)
            if not doc:
                return None

            data = doc.model_dump()
            updates = req.model_dump(exclude_none=True)

            # Validate status transition if status is being changed
            if "status" in updates and updates["status"] != doc.status:
                new_status = updates["status"]
                allowed = VALID_STATUS_TRANSITIONS.get(doc.status, set())
                if new_status not in allowed:
                    raise ValueError(
                        f"Invalid status transition: {doc.status.value} -> {new_status.value}. "
                        f"Allowed: {[s.value for s in allowed]}"
                    )

            data.update(updates)
            updated = TMFDocument(**data)
            self._documents[document_id] = updated
            return updated

    def delete_document(self, document_id: str) -> bool:
        """Delete a TMF document."""
        with self._lock:
            if document_id in self._documents:
                del self._documents[document_id]
                return True
            return False

    # -----------------------------------------------------------------------
    # Version Management
    # -----------------------------------------------------------------------

    def create_new_version(self, document_id: str, new_version: str) -> TMFDocument | None:
        """Create a new version of a document, superseding the old one."""
        with self._lock:
            original = self._documents.get(document_id)
            if not original:
                return None

            # Supersede the original if it is effective
            if original.status == DocumentStatus.EFFECTIVE:
                orig_data = original.model_dump()
                orig_data["status"] = DocumentStatus.SUPERSEDED
                self._documents[document_id] = TMFDocument(**orig_data)

            # Create the new version
            new_id = f"tmf-doc-{uuid4().hex[:8]}"
            now = datetime.now(timezone.utc)
            new_doc = TMFDocument(
                id=new_id,
                trial_id=original.trial_id,
                zone=original.zone,
                artifact_type=original.artifact_type,
                title=original.title,
                description=f"New version {new_version} of {original.title}",
                version=new_version,
                status=DocumentStatus.DRAFT,
                file_path=original.file_path.replace(document_id, new_id) if original.file_path else "",
                file_size_bytes=original.file_size_bytes,
                mime_type=original.mime_type,
                uploaded_by=original.uploaded_by,
                uploaded_at=now,
                site_id=original.site_id,
                country=original.country,
                metadata_tags={**original.metadata_tags, "previous_version": document_id},
                compliance_status=ComplianceStatus.NOT_ASSESSED,
                part11_compliant=False,
                gdpr_compliant=False,
            )
            self._documents[new_id] = new_doc

        logger.info("Created new version %s of document %s", new_version, document_id)
        return new_doc

    # -----------------------------------------------------------------------
    # Approval Workflow
    # -----------------------------------------------------------------------

    def submit_for_review(self, document_id: str, req: DocumentReviewRequest) -> TMFDocument | None:
        """Submit a document for review (DRAFT -> UNDER_REVIEW)."""
        with self._lock:
            doc = self._documents.get(document_id)
            if not doc:
                return None

            if doc.status != DocumentStatus.DRAFT:
                raise ValueError(f"Document must be DRAFT to submit for review (current: {doc.status.value})")

            data = doc.model_dump()
            data["status"] = DocumentStatus.UNDER_REVIEW
            data["reviewed_by"] = req.reviewed_by
            data["reviewed_at"] = datetime.now(timezone.utc)
            updated = TMFDocument(**data)
            self._documents[document_id] = updated
            return updated

    def approve_document(self, document_id: str, req: DocumentApprovalRequest) -> TMFDocument | None:
        """Approve a document (UNDER_REVIEW -> APPROVED)."""
        with self._lock:
            doc = self._documents.get(document_id)
            if not doc:
                return None

            if doc.status != DocumentStatus.UNDER_REVIEW:
                raise ValueError(f"Document must be UNDER_REVIEW to approve (current: {doc.status.value})")

            now = datetime.now(timezone.utc)
            data = doc.model_dump()
            data["status"] = DocumentStatus.APPROVED
            data["approved_by"] = req.approved_by
            data["approved_at"] = now
            if req.effective_date:
                data["effective_date"] = req.effective_date
            updated = TMFDocument(**data)
            self._documents[document_id] = updated
            return updated

    def make_effective(self, document_id: str) -> TMFDocument | None:
        """Make an approved document effective (APPROVED -> EFFECTIVE)."""
        with self._lock:
            doc = self._documents.get(document_id)
            if not doc:
                return None

            if doc.status != DocumentStatus.APPROVED:
                raise ValueError(f"Document must be APPROVED to make effective (current: {doc.status.value})")

            data = doc.model_dump()
            data["status"] = DocumentStatus.EFFECTIVE
            if not data.get("effective_date"):
                data["effective_date"] = date.today()
            updated = TMFDocument(**data)
            self._documents[document_id] = updated
            return updated

    def add_signature(self, document_id: str, req: SignatureRequest) -> TMFDocument | None:
        """Add a signature to a document."""
        with self._lock:
            doc = self._documents.get(document_id)
            if not doc:
                return None

            sig = DocumentSignature(
                signer_name=req.signer_name,
                signer_role=req.signer_role,
                signature_type=req.signature_type,
                signed_at=datetime.now(timezone.utc),
                reason=req.reason,
            )

            data = doc.model_dump()
            data["signatures"] = list(data["signatures"]) + [sig.model_dump()]
            updated = TMFDocument(**data)
            self._documents[document_id] = updated
            return updated

    # -----------------------------------------------------------------------
    # Zone Completeness Analysis
    # -----------------------------------------------------------------------

    def get_zone_completeness(self, trial_id: str) -> list[TMFSection]:
        """Analyze completeness per zone for a trial."""
        with self._lock:
            trial_docs = [d for d in self._documents.values() if d.trial_id == trial_id]

        # Count required docs from rules per zone
        zone_expected: dict[TMFZone, int] = Counter()
        for rule in self._compliance_rules.values():
            if rule.required:
                zone_expected[rule.zone] += 1

        sections: list[TMFSection] = []
        for zone in TMFZone:
            zone_docs = [d for d in trial_docs if d.zone == zone]
            expected = zone_expected.get(zone, 1)
            actual = len(zone_docs)
            pct = min(100.0, (actual / expected) * 100.0) if expected > 0 else 100.0

            # Missing docs: rules that have no matching document
            zone_rules = [r for r in self._compliance_rules.values() if r.zone == zone and r.required]
            missing: list[str] = []
            for rule in zone_rules:
                has_match = any(
                    d.artifact_type == rule.artifact_type
                    for d in zone_docs
                )
                if not has_match:
                    missing.append(rule.name)

            # Overdue: effective docs past expiry
            today = date.today()
            overdue = [
                d.title for d in zone_docs
                if d.expiry_date and d.expiry_date < today
            ]

            compliance = ComplianceStatus.COMPLIANT if pct >= 80.0 and not missing else (
                ComplianceStatus.PARTIALLY_COMPLIANT if pct >= 50.0 else ComplianceStatus.NON_COMPLIANT
            )

            sections.append(TMFSection(
                zone=zone,
                artifact_type=None,
                expected_documents=expected,
                actual_documents=actual,
                completeness_percent=round(pct, 1),
                compliance_status=compliance,
                missing_documents=missing,
                overdue_documents=overdue,
            ))

        return sections

    # -----------------------------------------------------------------------
    # Compliance Rules
    # -----------------------------------------------------------------------

    def list_compliance_rules(
        self,
        zone: TMFZone | None = None,
        artifact_type: ArtifactType | None = None,
    ) -> list[ComplianceRule]:
        """List compliance rules with optional filters."""
        rules = list(self._compliance_rules.values())
        if zone:
            rules = [r for r in rules if r.zone == zone]
        if artifact_type:
            rules = [r for r in rules if r.artifact_type == artifact_type]
        return rules

    def get_compliance_rule(self, rule_id: str) -> ComplianceRule | None:
        """Get a single compliance rule."""
        return self._compliance_rules.get(rule_id)

    def create_compliance_rule(self, req: ComplianceRuleCreate) -> ComplianceRule:
        """Create a new compliance rule."""
        rule_id = f"rule-{uuid4().hex[:8]}"
        rule = ComplianceRule(
            id=rule_id,
            name=req.name,
            zone=req.zone,
            artifact_type=req.artifact_type,
            description=req.description,
            required=req.required,
            review_frequency_days=req.review_frequency_days,
            retention_years=req.retention_years,
            part11_requirement=req.part11_requirement,
            gdpr_requirement=req.gdpr_requirement,
        )
        with self._lock:
            self._compliance_rules[rule_id] = rule
        return rule

    def update_compliance_rule(self, rule_id: str, req: ComplianceRuleUpdate) -> ComplianceRule | None:
        """Update a compliance rule."""
        with self._lock:
            rule = self._compliance_rules.get(rule_id)
            if not rule:
                return None
            data = rule.model_dump()
            data.update(req.model_dump(exclude_none=True))
            updated = ComplianceRule(**data)
            self._compliance_rules[rule_id] = updated
            return updated

    def delete_compliance_rule(self, rule_id: str) -> bool:
        """Delete a compliance rule."""
        with self._lock:
            if rule_id in self._compliance_rules:
                del self._compliance_rules[rule_id]
                return True
            return False

    # -----------------------------------------------------------------------
    # Inspection Readiness
    # -----------------------------------------------------------------------

    def assess_inspection_readiness(self, trial_id: str) -> InspectionReadiness:
        """Assess overall inspection readiness for a trial."""
        sections = self.get_zone_completeness(trial_id)
        if not sections:
            return InspectionReadiness.NOT_READY

        avg_completeness = sum(s.completeness_percent for s in sections) / len(sections)
        non_compliant = sum(1 for s in sections if s.compliance_status == ComplianceStatus.NON_COMPLIANT)
        has_missing = any(s.missing_documents for s in sections)

        if avg_completeness >= 90.0 and non_compliant == 0:
            return InspectionReadiness.READY
        elif avg_completeness >= 70.0 and non_compliant <= 2:
            return InspectionReadiness.AT_RISK
        elif avg_completeness >= 50.0:
            return InspectionReadiness.IN_PREPARATION
        else:
            return InspectionReadiness.NOT_READY

    # -----------------------------------------------------------------------
    # Document Expiry Tracking
    # -----------------------------------------------------------------------

    def get_expiring_documents(self, days_ahead: int = 30, trial_id: str | None = None) -> list[TMFDocument]:
        """Get documents expiring within the given window."""
        today = date.today()
        cutoff = today + timedelta(days=days_ahead)

        with self._lock:
            docs = list(self._documents.values())

        if trial_id:
            docs = [d for d in docs if d.trial_id == trial_id]

        expiring = [
            d for d in docs
            if d.expiry_date and today <= d.expiry_date <= cutoff
            and d.status not in (DocumentStatus.ARCHIVED, DocumentStatus.WITHDRAWN, DocumentStatus.SUPERSEDED)
        ]
        expiring.sort(key=lambda d: d.expiry_date)  # type: ignore[arg-type]
        return expiring

    # -----------------------------------------------------------------------
    # Part 11 Compliance Check
    # -----------------------------------------------------------------------

    def check_part11_compliance(self, trial_id: str | None = None) -> dict:
        """Check 21 CFR Part 11 compliance across documents."""
        with self._lock:
            docs = list(self._documents.values())

        if trial_id:
            docs = [d for d in docs if d.trial_id == trial_id]

        if not docs:
            return {"total": 0, "compliant": 0, "non_compliant": 0, "rate": 0.0, "issues": []}

        # Only check docs that have rules requiring Part 11
        part11_rules = {
            (r.zone, r.artifact_type)
            for r in self._compliance_rules.values()
            if r.part11_requirement
        }

        relevant = [d for d in docs if (d.zone, d.artifact_type) in part11_rules]
        if not relevant:
            return {"total": 0, "compliant": 0, "non_compliant": 0, "rate": 100.0, "issues": []}

        compliant = [d for d in relevant if d.part11_compliant]
        non_compliant = [d for d in relevant if not d.part11_compliant]

        issues = [
            {"document_id": d.id, "title": d.title, "zone": d.zone.value, "issue": "Missing Part 11 compliance"}
            for d in non_compliant
        ]

        rate = (len(compliant) / len(relevant)) * 100.0 if relevant else 100.0

        return {
            "total": len(relevant),
            "compliant": len(compliant),
            "non_compliant": len(non_compliant),
            "rate": round(rate, 1),
            "issues": issues,
        }

    # -----------------------------------------------------------------------
    # GDPR Compliance Check
    # -----------------------------------------------------------------------

    def check_gdpr_compliance(self, trial_id: str | None = None) -> dict:
        """Check GDPR compliance across documents."""
        with self._lock:
            docs = list(self._documents.values())

        if trial_id:
            docs = [d for d in docs if d.trial_id == trial_id]

        if not docs:
            return {"total": 0, "compliant": 0, "non_compliant": 0, "rate": 0.0, "issues": []}

        gdpr_rules = {
            (r.zone, r.artifact_type)
            for r in self._compliance_rules.values()
            if r.gdpr_requirement
        }

        relevant = [d for d in docs if (d.zone, d.artifact_type) in gdpr_rules]
        if not relevant:
            return {"total": 0, "compliant": 0, "non_compliant": 0, "rate": 100.0, "issues": []}

        compliant = [d for d in relevant if d.gdpr_compliant]
        non_compliant = [d for d in relevant if not d.gdpr_compliant]

        issues = [
            {"document_id": d.id, "title": d.title, "zone": d.zone.value, "issue": "Missing GDPR compliance"}
            for d in non_compliant
        ]

        rate = (len(compliant) / len(relevant)) * 100.0 if relevant else 100.0

        return {
            "total": len(relevant),
            "compliant": len(compliant),
            "non_compliant": len(non_compliant),
            "rate": round(rate, 1),
            "issues": issues,
        }

    # -----------------------------------------------------------------------
    # TMF Metrics
    # -----------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> TMFMetrics:
        """Get aggregated eTMF metrics."""
        with self._lock:
            docs = list(self._documents.values())

        if trial_id:
            docs = [d for d in docs if d.trial_id == trial_id]

        by_zone: dict[str, int] = Counter()
        by_status: dict[str, int] = Counter()
        for d in docs:
            by_zone[d.zone.value] += 1
            by_status[d.status.value] += 1

        # Pending signatures: docs that are approved but have no signatures
        pending_sigs = sum(1 for d in docs if d.status == DocumentStatus.APPROVED and not d.signatures)

        # Overdue reviews: under_review for more than 14 days
        now = datetime.now(timezone.utc)
        overdue_reviews = sum(
            1 for d in docs
            if d.status == DocumentStatus.UNDER_REVIEW
            and d.reviewed_at
            and (now - d.reviewed_at).days > 14
        )

        # Part 11 compliance rate
        p11_check = self.check_part11_compliance(trial_id)
        p11_rate = p11_check["rate"]

        # Expiring within 30 days
        expiring_30d = len(self.get_expiring_documents(30, trial_id))

        # Completeness
        if trial_id:
            sections = self.get_zone_completeness(trial_id)
            completeness = sum(s.completeness_percent for s in sections) / len(sections) if sections else 0.0
        else:
            completeness = 0.0
            trial_ids = set(d.trial_id for d in docs)
            if trial_ids:
                all_pcts = []
                for tid in trial_ids:
                    sects = self.get_zone_completeness(tid)
                    all_pcts.extend(s.completeness_percent for s in sects)
                completeness = sum(all_pcts) / len(all_pcts) if all_pcts else 0.0

        # Compliance percentage
        compliant_count = sum(1 for d in docs if d.compliance_status == ComplianceStatus.COMPLIANT)
        compliance_pct = (compliant_count / len(docs)) * 100.0 if docs else 0.0

        readiness = self.assess_inspection_readiness(trial_id) if trial_id else InspectionReadiness.IN_PREPARATION

        return TMFMetrics(
            total_documents=len(docs),
            by_zone=dict(by_zone),
            by_status=dict(by_status),
            completeness_percent=round(completeness, 1),
            compliance_percent=round(compliance_pct, 1),
            overdue_reviews=overdue_reviews,
            pending_signatures=pending_sigs,
            inspection_readiness=readiness,
            part11_compliance_rate=round(p11_rate, 1),
            documents_expiring_30d=expiring_30d,
        )

    # -----------------------------------------------------------------------
    # Inspection Checklists
    # -----------------------------------------------------------------------

    def list_inspection_checklists(
        self,
        trial_id: str | None = None,
    ) -> list[InspectionChecklist]:
        """List inspection checklists."""
        with self._lock:
            checklists = list(self._inspection_checklists.values())
        if trial_id:
            checklists = [c for c in checklists if c.trial_id == trial_id]
        return checklists

    def get_inspection_checklist(self, checklist_id: str) -> InspectionChecklist | None:
        """Get a single inspection checklist."""
        return self._inspection_checklists.get(checklist_id)

    def create_inspection_checklist(self, req: InspectionChecklistCreate) -> InspectionChecklist:
        """Create a new inspection checklist."""
        chk_id = f"chk-{uuid4().hex[:8]}"
        checklist = InspectionChecklist(
            id=chk_id,
            trial_id=req.trial_id,
            inspector_name=req.inspector_name,
            inspection_type=req.inspection_type,
            inspection_date=req.inspection_date,
            zones_reviewed=req.zones_reviewed,
            findings=[],
            overall_readiness=InspectionReadiness.IN_PREPARATION,
            created_at=datetime.now(timezone.utc),
        )
        with self._lock:
            self._inspection_checklists[chk_id] = checklist
        return checklist

    def delete_inspection_checklist(self, checklist_id: str) -> bool:
        """Delete an inspection checklist."""
        with self._lock:
            if checklist_id in self._inspection_checklists:
                del self._inspection_checklists[checklist_id]
                return True
            return False

    def add_inspection_finding(
        self, checklist_id: str, req: InspectionFindingCreate
    ) -> InspectionChecklist | None:
        """Add a finding to an inspection checklist."""
        with self._lock:
            chk = self._inspection_checklists.get(checklist_id)
            if not chk:
                return None

            finding = InspectionFinding(
                zone=req.zone,
                description=req.description,
                severity=req.severity,
                corrective_action=req.corrective_action,
                due_date=req.due_date,
                resolved=False,
            )

            data = chk.model_dump()
            data["findings"] = list(data["findings"]) + [finding.model_dump()]

            # Update readiness based on findings severity
            critical_count = sum(
                1 for f in data["findings"] if f.get("severity") == "critical" and not f.get("resolved")
            )
            major_count = sum(
                1 for f in data["findings"] if f.get("severity") == "major" and not f.get("resolved")
            )

            if critical_count > 0:
                data["overall_readiness"] = InspectionReadiness.NOT_READY
            elif major_count > 0:
                data["overall_readiness"] = InspectionReadiness.AT_RISK
            else:
                data["overall_readiness"] = InspectionReadiness.IN_PREPARATION

            updated = InspectionChecklist(**data)
            self._inspection_checklists[checklist_id] = updated
            return updated

    def resolve_inspection_finding(
        self, checklist_id: str, finding_index: int
    ) -> InspectionChecklist | None:
        """Resolve a finding in an inspection checklist."""
        with self._lock:
            chk = self._inspection_checklists.get(checklist_id)
            if not chk:
                return None

            data = chk.model_dump()
            findings = data.get("findings", [])
            if finding_index < 0 or finding_index >= len(findings):
                raise ValueError(f"Finding index {finding_index} out of range (0-{len(findings)-1})")

            findings[finding_index]["resolved"] = True
            data["findings"] = findings

            # Re-assess readiness
            unresolved_critical = sum(
                1 for f in findings if f.get("severity") == "critical" and not f.get("resolved")
            )
            unresolved_major = sum(
                1 for f in findings if f.get("severity") == "major" and not f.get("resolved")
            )

            if unresolved_critical > 0:
                data["overall_readiness"] = InspectionReadiness.NOT_READY
            elif unresolved_major > 0:
                data["overall_readiness"] = InspectionReadiness.AT_RISK
            elif all(f.get("resolved") for f in findings):
                data["overall_readiness"] = InspectionReadiness.READY
            else:
                data["overall_readiness"] = InspectionReadiness.IN_PREPARATION

            updated = InspectionChecklist(**data)
            self._inspection_checklists[checklist_id] = updated
            return updated

    # -----------------------------------------------------------------------
    # Missing Document Identification
    # -----------------------------------------------------------------------

    def get_missing_documents(self, trial_id: str) -> MissingDocumentsResponse:
        """Identify missing documents for a trial per compliance rules."""
        sections = self.get_zone_completeness(trial_id)
        missing_sections = [s for s in sections if s.missing_documents]
        total_missing = sum(len(s.missing_documents) for s in missing_sections)

        return MissingDocumentsResponse(
            trial_id=trial_id,
            missing=missing_sections,
            total_missing=total_missing,
        )

    # -----------------------------------------------------------------------
    # Bulk Document Import
    # -----------------------------------------------------------------------

    def bulk_import(self, req: BulkImportRequest) -> BulkImportResponse:
        """Bulk import documents."""
        imported_ids: list[str] = []
        errors: list[str] = []

        for i, doc_req in enumerate(req.documents):
            try:
                doc = self.create_document(doc_req)
                imported_ids.append(doc.id)
            except Exception as e:
                errors.append(f"Document {i}: {str(e)}")

        return BulkImportResponse(
            imported=len(imported_ids),
            failed=len(errors),
            document_ids=imported_ids,
            errors=errors,
        )

    # -----------------------------------------------------------------------
    # Stats
    # -----------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Get service statistics."""
        return {
            "total_documents": len(self._documents),
            "total_compliance_rules": len(self._compliance_rules),
            "total_inspection_checklists": len(self._inspection_checklists),
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ETMFService | None = None
_instance_lock = threading.Lock()


def get_etmf_service() -> ETMFService:
    """Get or create the singleton eTMF service."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ETMFService()
    return _instance


def reset_etmf_service() -> ETMFService:
    """Reset the singleton (for testing). Returns a fresh instance."""
    global _instance
    with _instance_lock:
        _instance = ETMFService()
    return _instance
    return _instance
