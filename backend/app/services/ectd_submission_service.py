"""eCTD Submission Management Service (eCTD-MGMT).

Manages electronic Common Technical Document submissions: eCTD sequence
planning, module assembly, document lifecycle, submission tracking,
health authority responses, submission plans, and eCTD operational metrics.

Usage:
    from app.services.ectd_submission_service import (
        get_ectd_submission_service,
    )

    svc = get_ectd_submission_service()
    sequences = svc.list_sequences()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.ectd_submission import (
    CTDModule,
    DocumentLifecycle,
    ECTDDocument,
    ECTDDocumentCreate,
    ECTDDocumentUpdate,
    ECTDMetrics,
    ECTDSequence,
    ECTDSequenceCreate,
    ECTDSequenceUpdate,
    ECTDValidation,
    ECTDValidationCreate,
    HAResponse,
    HAResponseCreate,
    HAResponseType,
    HAResponseUpdate,
    RegulatoryRegion,
    SequenceStatus,
    SubmissionPlan,
    SubmissionPlanCreate,
    SubmissionPlanUpdate,
    SubmissionType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class ECTDSubmissionService:
    """In-memory eCTD Submission Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._sequences: dict[str, ECTDSequence] = {}
        self._documents: dict[str, ECTDDocument] = {}
        self._validations: dict[str, ECTDValidation] = {}
        self._ha_responses: dict[str, HAResponse] = {}
        self._plans: dict[str, SubmissionPlan] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic eCTD submission data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Sequences ---
        sequences_data = [
            {
                "id": "SEQ-001",
                "trial_id": EYLEA_TRIAL,
                "sequence_number": "0000",
                "submission_type": SubmissionType.INITIAL,
                "region": RegulatoryRegion.US_FDA,
                "status": SequenceStatus.SUBMITTED,
                "title": "EYLEA HD Initial NDA Submission",
                "description": "Initial NDA for EYLEA HD 8mg intravitreal injection",
                "target_date": now - timedelta(days=90),
                "actual_submission_date": now - timedelta(days=88),
                "acknowledgment_date": now - timedelta(days=85),
                "tracking_number": "NDA-215-376",
                "ectd_version": "4.0",
                "total_documents": 247,
                "total_size_mb": 4523.7,
                "publisher": "Lorenz LifeSciences",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "SEQ-002",
                "trial_id": EYLEA_TRIAL,
                "sequence_number": "0001",
                "submission_type": SubmissionType.RESPONSE,
                "region": RegulatoryRegion.US_FDA,
                "status": SequenceStatus.AUTHORING,
                "title": "EYLEA HD Response to FDA Information Request",
                "description": "Response to FDA IR dated 2025-10-15 regarding CMC stability data",
                "target_date": now + timedelta(days=30),
                "tracking_number": None,
                "ectd_version": "4.0",
                "total_documents": 18,
                "total_size_mb": 312.5,
                "publisher": "Lorenz LifeSciences",
                "created_at": now - timedelta(days=14),
            },
            {
                "id": "SEQ-003",
                "trial_id": EYLEA_TRIAL,
                "sequence_number": "0000",
                "submission_type": SubmissionType.INITIAL,
                "region": RegulatoryRegion.EU_EMA,
                "status": SequenceStatus.SUBMITTED,
                "title": "EYLEA HD MAA Submission to EMA",
                "description": "Marketing Authorisation Application for aflibercept 8mg",
                "target_date": now - timedelta(days=60),
                "actual_submission_date": now - timedelta(days=58),
                "acknowledgment_date": now - timedelta(days=50),
                "tracking_number": "EMEA/H/C/006789",
                "ectd_version": "4.0",
                "total_documents": 312,
                "total_size_mb": 5840.2,
                "publisher": "Lorenz LifeSciences",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "SEQ-004",
                "trial_id": DUPIXENT_TRIAL,
                "sequence_number": "0023",
                "submission_type": SubmissionType.SUPPLEMENT,
                "region": RegulatoryRegion.US_FDA,
                "status": SequenceStatus.SUBMITTED,
                "title": "DUPIXENT sNDA - COPD Indication",
                "description": "Supplemental NDA for dupilumab in moderate-to-severe COPD",
                "target_date": now - timedelta(days=45),
                "actual_submission_date": now - timedelta(days=43),
                "acknowledgment_date": now - timedelta(days=40),
                "tracking_number": "NDA-761-055-S023",
                "ectd_version": "4.0",
                "total_documents": 189,
                "total_size_mb": 3210.8,
                "publisher": "ISI Publishing",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "SEQ-005",
                "trial_id": DUPIXENT_TRIAL,
                "sequence_number": "0024",
                "submission_type": SubmissionType.ANNUAL_REPORT,
                "region": RegulatoryRegion.US_FDA,
                "status": SequenceStatus.QC_REVIEW,
                "title": "DUPIXENT Annual Report 2025",
                "description": "Annual report covering safety and efficacy updates",
                "target_date": now + timedelta(days=15),
                "tracking_number": None,
                "ectd_version": "4.0",
                "total_documents": 42,
                "total_size_mb": 875.3,
                "publisher": "ISI Publishing",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "SEQ-006",
                "trial_id": DUPIXENT_TRIAL,
                "sequence_number": "0003",
                "submission_type": SubmissionType.VARIATION,
                "region": RegulatoryRegion.EU_EMA,
                "status": SequenceStatus.PUBLISHING,
                "title": "DUPIXENT Type II Variation - COPD",
                "description": "Type II variation for new COPD indication in EU",
                "target_date": now + timedelta(days=20),
                "tracking_number": None,
                "ectd_version": "4.0",
                "total_documents": 156,
                "total_size_mb": 2890.1,
                "publisher": "Lorenz LifeSciences",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "SEQ-007",
                "trial_id": DUPIXENT_TRIAL,
                "sequence_number": "0001",
                "submission_type": SubmissionType.INITIAL,
                "region": RegulatoryRegion.JAPAN_PMDA,
                "status": SequenceStatus.ACKNOWLEDGED,
                "title": "DUPIXENT JNDA - Prurigo Nodularis",
                "description": "Japan NDA for dupilumab in prurigo nodularis",
                "target_date": now - timedelta(days=120),
                "actual_submission_date": now - timedelta(days=118),
                "acknowledgment_date": now - timedelta(days=110),
                "tracking_number": "PMDA-2025-0456",
                "ectd_version": "4.0",
                "total_documents": 201,
                "total_size_mb": 3450.9,
                "publisher": "DataVision Japan",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "SEQ-008",
                "trial_id": LIBTAYO_TRIAL,
                "sequence_number": "0010",
                "submission_type": SubmissionType.SUPPLEMENT,
                "region": RegulatoryRegion.US_FDA,
                "status": SequenceStatus.READY,
                "title": "LIBTAYO sBLA - Adjuvant CSCC",
                "description": "Supplemental BLA for cemiplimab adjuvant cutaneous SCC",
                "target_date": now + timedelta(days=5),
                "tracking_number": None,
                "ectd_version": "4.0",
                "total_documents": 134,
                "total_size_mb": 2190.4,
                "publisher": "ISI Publishing",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "SEQ-009",
                "trial_id": LIBTAYO_TRIAL,
                "sequence_number": "0011",
                "submission_type": SubmissionType.RESPONSE,
                "region": RegulatoryRegion.US_FDA,
                "status": SequenceStatus.PLANNING,
                "title": "LIBTAYO Response to FDA CRL",
                "description": "Response to Complete Response Letter for NSCLC combination",
                "target_date": now + timedelta(days=60),
                "tracking_number": None,
                "ectd_version": "4.0",
                "total_documents": 0,
                "total_size_mb": 0,
                "publisher": "Lorenz LifeSciences",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "SEQ-010",
                "trial_id": LIBTAYO_TRIAL,
                "sequence_number": "0002",
                "submission_type": SubmissionType.VARIATION,
                "region": RegulatoryRegion.EU_EMA,
                "status": SequenceStatus.SUBMITTED,
                "title": "LIBTAYO Type II Variation - BCC 2L",
                "description": "Variation for second-line basal cell carcinoma",
                "target_date": now - timedelta(days=30),
                "actual_submission_date": now - timedelta(days=28),
                "acknowledgment_date": now - timedelta(days=22),
                "tracking_number": "EMEA/H/C/004844/II/0012",
                "ectd_version": "4.0",
                "total_documents": 98,
                "total_size_mb": 1720.6,
                "publisher": "Lorenz LifeSciences",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "SEQ-011",
                "trial_id": LIBTAYO_TRIAL,
                "sequence_number": "0001",
                "submission_type": SubmissionType.RENEWAL,
                "region": RegulatoryRegion.UK_MHRA,
                "status": SequenceStatus.SUBMITTED,
                "title": "LIBTAYO MHRA Renewal Application",
                "description": "Marketing authorisation renewal for cemiplimab in UK",
                "target_date": now - timedelta(days=15),
                "actual_submission_date": now - timedelta(days=14),
                "acknowledgment_date": now - timedelta(days=10),
                "tracking_number": "MHRA-PL-2025-7891",
                "ectd_version": "4.0",
                "total_documents": 56,
                "total_size_mb": 890.2,
                "publisher": "ISI Publishing",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "SEQ-012",
                "trial_id": EYLEA_TRIAL,
                "sequence_number": "0001",
                "submission_type": SubmissionType.AMENDMENT,
                "region": RegulatoryRegion.CANADA_HC,
                "status": SequenceStatus.AUTHORING,
                "title": "EYLEA HD NDS Amendment - Health Canada",
                "description": "Amendment to NDS for aflibercept 8mg stability update",
                "target_date": now + timedelta(days=45),
                "tracking_number": None,
                "ectd_version": "4.0",
                "total_documents": 23,
                "total_size_mb": 410.8,
                "publisher": "Lorenz LifeSciences",
                "created_at": now - timedelta(days=20),
            },
        ]

        for data in sequences_data:
            seq = ECTDSequence(**data)
            self._sequences[seq.id] = seq

        # --- 15 Documents ---
        documents_data = [
            {
                "id": "DOC-001",
                "sequence_id": "SEQ-001",
                "module": CTDModule.MODULE_1,
                "section_number": "1.2",
                "title": "FDA Form 356h - Application Form",
                "file_name": "m1-2-form-fda-356h.pdf",
                "lifecycle_operation": DocumentLifecycle.NEW,
                "version": "1.0",
                "page_count": 12,
                "size_kb": 245.6,
                "checksum": "sha256:a1b2c3d4e5f6",
                "author": "Sarah Chen",
                "reviewer": "Michael Rodriguez",
                "approved": True,
                "approved_date": now - timedelta(days=95),
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "DOC-002",
                "sequence_id": "SEQ-001",
                "module": CTDModule.MODULE_2,
                "section_number": "2.5",
                "title": "Clinical Overview",
                "file_name": "m2-5-clinical-overview.pdf",
                "lifecycle_operation": DocumentLifecycle.NEW,
                "version": "1.0",
                "page_count": 85,
                "size_kb": 3420.8,
                "checksum": "sha256:f6e5d4c3b2a1",
                "author": "Dr. James Liu",
                "reviewer": "Dr. Emily Watson",
                "approved": True,
                "approved_date": now - timedelta(days=92),
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "DOC-003",
                "sequence_id": "SEQ-001",
                "module": CTDModule.MODULE_3,
                "section_number": "3.2.S.1",
                "title": "General Information - Drug Substance",
                "file_name": "m3-2-s-1-gen-info.pdf",
                "lifecycle_operation": DocumentLifecycle.NEW,
                "version": "1.0",
                "page_count": 28,
                "size_kb": 1120.3,
                "checksum": "sha256:1a2b3c4d5e6f",
                "author": "Dr. Anita Patel",
                "reviewer": "Robert Kim",
                "approved": True,
                "approved_date": now - timedelta(days=93),
                "created_at": now - timedelta(days=112),
            },
            {
                "id": "DOC-004",
                "sequence_id": "SEQ-001",
                "module": CTDModule.MODULE_4,
                "section_number": "4.2.3",
                "title": "Toxicology Studies - Repeat Dose",
                "file_name": "m4-2-3-repeat-dose-tox.pdf",
                "lifecycle_operation": DocumentLifecycle.NEW,
                "version": "1.0",
                "page_count": 156,
                "size_kb": 8945.2,
                "checksum": "sha256:6f5e4d3c2b1a",
                "author": "Dr. Thomas Meyer",
                "reviewer": "Dr. Lisa Park",
                "approved": True,
                "approved_date": now - timedelta(days=94),
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "DOC-005",
                "sequence_id": "SEQ-001",
                "module": CTDModule.MODULE_5,
                "section_number": "5.3.5.1",
                "title": "Clinical Study Report - PULSAR Phase 3",
                "file_name": "m5-3-5-1-csr-pulsar.pdf",
                "lifecycle_operation": DocumentLifecycle.NEW,
                "version": "1.0",
                "page_count": 423,
                "size_kb": 24500.0,
                "checksum": "sha256:abcdef123456",
                "author": "Dr. Rebecca Stone",
                "reviewer": "Dr. Mark Williams",
                "approved": True,
                "approved_date": now - timedelta(days=91),
                "created_at": now - timedelta(days=118),
            },
            {
                "id": "DOC-006",
                "sequence_id": "SEQ-002",
                "module": CTDModule.MODULE_3,
                "section_number": "3.2.P.8",
                "title": "Stability Data Update - Drug Product",
                "file_name": "m3-2-p-8-stability.pdf",
                "lifecycle_operation": DocumentLifecycle.APPEND,
                "version": "2.0",
                "page_count": 45,
                "size_kb": 2100.5,
                "checksum": "sha256:789abc012def",
                "author": "Dr. Anita Patel",
                "reviewer": None,
                "approved": False,
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "DOC-007",
                "sequence_id": "SEQ-004",
                "module": CTDModule.MODULE_2,
                "section_number": "2.7.3",
                "title": "Summary of Clinical Efficacy - COPD",
                "file_name": "m2-7-3-clin-efficacy-copd.pdf",
                "lifecycle_operation": DocumentLifecycle.NEW,
                "version": "1.0",
                "page_count": 112,
                "size_kb": 5620.4,
                "checksum": "sha256:def012abc789",
                "author": "Dr. Karen Lee",
                "reviewer": "Dr. David Brown",
                "approved": True,
                "approved_date": now - timedelta(days=48),
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "DOC-008",
                "sequence_id": "SEQ-004",
                "module": CTDModule.MODULE_5,
                "section_number": "5.3.5.1",
                "title": "CSR - BOREAS Phase 3 (COPD)",
                "file_name": "m5-3-5-1-csr-boreas.pdf",
                "lifecycle_operation": DocumentLifecycle.NEW,
                "version": "1.0",
                "page_count": 389,
                "size_kb": 22800.0,
                "checksum": "sha256:456789abcdef",
                "author": "Dr. Alan Foster",
                "reviewer": "Dr. Priya Singh",
                "approved": True,
                "approved_date": now - timedelta(days=46),
                "created_at": now - timedelta(days=78),
            },
            {
                "id": "DOC-009",
                "sequence_id": "SEQ-005",
                "module": CTDModule.MODULE_1,
                "section_number": "1.14",
                "title": "Annual Report Narrative",
                "file_name": "m1-14-annual-report.pdf",
                "lifecycle_operation": DocumentLifecycle.NEW,
                "version": "1.0",
                "page_count": 34,
                "size_kb": 1450.2,
                "author": "Jennifer Adams",
                "reviewer": "Michael Rodriguez",
                "approved": False,
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "DOC-010",
                "sequence_id": "SEQ-008",
                "module": CTDModule.MODULE_5,
                "section_number": "5.3.5.1",
                "title": "CSR - EMPOWER-CSCC Adjuvant Phase 3",
                "file_name": "m5-3-5-1-csr-empower-cscc-adj.pdf",
                "lifecycle_operation": DocumentLifecycle.NEW,
                "version": "1.0",
                "page_count": 367,
                "size_kb": 19800.0,
                "checksum": "sha256:fedcba654321",
                "author": "Dr. Natalie Green",
                "reviewer": "Dr. Chris Taylor",
                "approved": True,
                "approved_date": now - timedelta(days=8),
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "DOC-011",
                "sequence_id": "SEQ-003",
                "module": CTDModule.MODULE_1,
                "section_number": "1.0",
                "title": "EU Cover Letter",
                "file_name": "m1-0-eu-cover-letter.pdf",
                "lifecycle_operation": DocumentLifecycle.NEW,
                "version": "1.0",
                "page_count": 4,
                "size_kb": 120.5,
                "checksum": "sha256:aabbccddee11",
                "author": "Sarah Chen",
                "reviewer": "Dr. Emily Watson",
                "approved": True,
                "approved_date": now - timedelta(days=62),
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "DOC-012",
                "sequence_id": "SEQ-006",
                "module": CTDModule.MODULE_2,
                "section_number": "2.5",
                "title": "Clinical Overview - COPD EU Variation",
                "file_name": "m2-5-clinical-overview-copd-eu.pdf",
                "lifecycle_operation": DocumentLifecycle.REPLACE,
                "version": "2.0",
                "page_count": 92,
                "size_kb": 4210.3,
                "author": "Dr. Karen Lee",
                "reviewer": None,
                "approved": False,
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "DOC-013",
                "sequence_id": "SEQ-007",
                "module": CTDModule.MODULE_1,
                "section_number": "1.12",
                "title": "PMDA Application Form (YoShiki)",
                "file_name": "m1-12-pmda-yoshiki.pdf",
                "lifecycle_operation": DocumentLifecycle.NEW,
                "version": "1.0",
                "page_count": 18,
                "size_kb": 560.8,
                "checksum": "sha256:112233445566",
                "author": "Yuki Tanaka",
                "reviewer": "Dr. Haruto Nakamura",
                "approved": True,
                "approved_date": now - timedelta(days=122),
                "created_at": now - timedelta(days=145),
            },
            {
                "id": "DOC-014",
                "sequence_id": "SEQ-010",
                "module": CTDModule.MODULE_2,
                "section_number": "2.7.4",
                "title": "Summary of Clinical Safety - BCC",
                "file_name": "m2-7-4-clin-safety-bcc.pdf",
                "lifecycle_operation": DocumentLifecycle.NEW,
                "version": "1.0",
                "page_count": 78,
                "size_kb": 3890.5,
                "checksum": "sha256:aabb11223344",
                "author": "Dr. Rachel Kim",
                "reviewer": "Dr. Steven White",
                "approved": True,
                "approved_date": now - timedelta(days=32),
                "created_at": now - timedelta(days=65),
            },
            {
                "id": "DOC-015",
                "sequence_id": "SEQ-011",
                "module": CTDModule.MODULE_1,
                "section_number": "1.2",
                "title": "MHRA Renewal Application Form",
                "file_name": "m1-2-mhra-renewal-form.pdf",
                "lifecycle_operation": DocumentLifecycle.NEW,
                "version": "1.0",
                "page_count": 8,
                "size_kb": 198.4,
                "checksum": "sha256:5566778899aa",
                "author": "Amanda Clarke",
                "reviewer": "Dr. James Patterson",
                "approved": True,
                "approved_date": now - timedelta(days=16),
                "created_at": now - timedelta(days=38),
            },
        ]

        for data in documents_data:
            doc = ECTDDocument(**data)
            self._documents[doc.id] = doc

        # --- 12 Validations ---
        validations_data = [
            {
                "id": "VAL-001",
                "sequence_id": "SEQ-001",
                "validation_tool": "Lorenz docuBridge",
                "validation_date": now - timedelta(days=89),
                "passed": True,
                "errors": 0,
                "warnings": 3,
                "error_details": [],
                "validator": "Sarah Chen",
                "report_reference": "VAL-RPT-2025-001",
            },
            {
                "id": "VAL-002",
                "sequence_id": "SEQ-001",
                "validation_tool": "FDA eCTD Validator v4.1",
                "validation_date": now - timedelta(days=88),
                "passed": True,
                "errors": 0,
                "warnings": 1,
                "error_details": [],
                "validator": "Michael Rodriguez",
                "report_reference": "VAL-RPT-2025-002",
            },
            {
                "id": "VAL-003",
                "sequence_id": "SEQ-003",
                "validation_tool": "Lorenz docuBridge",
                "validation_date": now - timedelta(days=59),
                "passed": True,
                "errors": 0,
                "warnings": 5,
                "error_details": [],
                "validator": "Sarah Chen",
                "report_reference": "VAL-RPT-2025-003",
            },
            {
                "id": "VAL-004",
                "sequence_id": "SEQ-004",
                "validation_tool": "ISI Toolbox",
                "validation_date": now - timedelta(days=44),
                "passed": True,
                "errors": 0,
                "warnings": 2,
                "error_details": [],
                "validator": "Jennifer Adams",
                "report_reference": "VAL-RPT-2025-004",
            },
            {
                "id": "VAL-005",
                "sequence_id": "SEQ-005",
                "validation_tool": "ISI Toolbox",
                "validation_date": now - timedelta(days=5),
                "passed": False,
                "errors": 2,
                "warnings": 4,
                "error_details": [
                    "Missing PDF bookmarks in m1-14-annual-report.pdf",
                    "Invalid XML namespace in regional.xml",
                ],
                "validator": "Robert Kim",
                "report_reference": "VAL-RPT-2025-005",
            },
            {
                "id": "VAL-006",
                "sequence_id": "SEQ-006",
                "validation_tool": "Lorenz docuBridge",
                "validation_date": now - timedelta(days=3),
                "passed": False,
                "errors": 1,
                "warnings": 6,
                "error_details": [
                    "Document m2-5-clinical-overview-copd-eu.pdf exceeds 200MB leaf size limit",
                ],
                "validator": "Sarah Chen",
                "report_reference": "VAL-RPT-2025-006",
            },
            {
                "id": "VAL-007",
                "sequence_id": "SEQ-007",
                "validation_tool": "PMDA Gateway Validator",
                "validation_date": now - timedelta(days=119),
                "passed": True,
                "errors": 0,
                "warnings": 0,
                "error_details": [],
                "validator": "Yuki Tanaka",
                "report_reference": "VAL-RPT-2025-007",
            },
            {
                "id": "VAL-008",
                "sequence_id": "SEQ-008",
                "validation_tool": "ISI Toolbox",
                "validation_date": now - timedelta(days=2),
                "passed": True,
                "errors": 0,
                "warnings": 1,
                "error_details": [],
                "validator": "Jennifer Adams",
                "report_reference": "VAL-RPT-2025-008",
            },
            {
                "id": "VAL-009",
                "sequence_id": "SEQ-010",
                "validation_tool": "Lorenz docuBridge",
                "validation_date": now - timedelta(days=29),
                "passed": True,
                "errors": 0,
                "warnings": 2,
                "error_details": [],
                "validator": "Amanda Clarke",
                "report_reference": "VAL-RPT-2025-009",
            },
            {
                "id": "VAL-010",
                "sequence_id": "SEQ-011",
                "validation_tool": "MHRA eCTD Validator",
                "validation_date": now - timedelta(days=15),
                "passed": True,
                "errors": 0,
                "warnings": 0,
                "error_details": [],
                "validator": "Amanda Clarke",
                "report_reference": "VAL-RPT-2025-010",
            },
            {
                "id": "VAL-011",
                "sequence_id": "SEQ-001",
                "validation_tool": "Internal QC Checklist",
                "validation_date": now - timedelta(days=90),
                "passed": True,
                "errors": 0,
                "warnings": 0,
                "error_details": [],
                "validator": "Dr. Emily Watson",
                "report_reference": "VAL-RPT-2025-011",
            },
            {
                "id": "VAL-012",
                "sequence_id": "SEQ-012",
                "validation_tool": "Health Canada eCTD Validator",
                "validation_date": now - timedelta(days=1),
                "passed": False,
                "errors": 3,
                "warnings": 2,
                "error_details": [
                    "Missing mandatory element in m1 regional admin",
                    "Cover letter signature block incomplete",
                    "HC-specific DTD version mismatch",
                ],
                "validator": "Robert Kim",
                "report_reference": "VAL-RPT-2025-012",
            },
        ]

        for data in validations_data:
            val = ECTDValidation(**data)
            self._validations[val.id] = val

        # --- 10 HA Responses ---
        ha_responses_data = [
            {
                "id": "HAR-001",
                "sequence_id": "SEQ-001",
                "response_type": HAResponseType.ACKNOWLEDGMENT,
                "response_date": now - timedelta(days=85),
                "summary": "FDA acknowledged receipt of NDA-215-376",
                "questions": [],
                "action_items": [],
                "status": "closed",
                "resolved_date": now - timedelta(days=85),
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "HAR-002",
                "sequence_id": "SEQ-001",
                "response_type": HAResponseType.INFORMATION_REQUEST,
                "response_date": now - timedelta(days=30),
                "due_date": now + timedelta(days=30),
                "summary": "FDA Information Request regarding CMC stability data",
                "questions": [
                    "Provide 36-month stability data for the 8mg formulation",
                    "Clarify the degradation pathway for impurity A-7",
                    "Submit updated shelf-life specification",
                ],
                "action_items": [
                    "Compile 36-month stability tables from Regeneron QC lab",
                    "Draft degradation pathway analysis report",
                    "Update drug product specification with revised shelf-life",
                ],
                "assigned_to": "Dr. Anita Patel",
                "status": "open",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "HAR-003",
                "sequence_id": "SEQ-003",
                "response_type": HAResponseType.ACKNOWLEDGMENT,
                "response_date": now - timedelta(days=50),
                "summary": "EMA validation of MAA confirmed",
                "questions": [],
                "action_items": [],
                "status": "closed",
                "resolved_date": now - timedelta(days=50),
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "HAR-004",
                "sequence_id": "SEQ-003",
                "response_type": HAResponseType.INFORMATION_REQUEST,
                "response_date": now - timedelta(days=20),
                "due_date": now + timedelta(days=40),
                "summary": "EMA Day 120 List of Questions",
                "questions": [
                    "Provide subgroup analysis by age cohort (>75 years)",
                    "Discuss the clinical significance of the anti-drug antibody findings",
                ],
                "action_items": [
                    "Generate post-hoc subgroup analysis tables",
                    "Prepare immunogenicity clinical assessment",
                ],
                "assigned_to": "Dr. James Liu",
                "status": "open",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "HAR-005",
                "sequence_id": "SEQ-004",
                "response_type": HAResponseType.ACKNOWLEDGMENT,
                "response_date": now - timedelta(days=40),
                "summary": "FDA acknowledged receipt of sNDA for COPD indication",
                "questions": [],
                "action_items": [],
                "status": "closed",
                "resolved_date": now - timedelta(days=40),
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "HAR-006",
                "sequence_id": "SEQ-007",
                "response_type": HAResponseType.ACKNOWLEDGMENT,
                "response_date": now - timedelta(days=110),
                "summary": "PMDA confirmed receipt of JNDA",
                "questions": [],
                "action_items": [],
                "status": "closed",
                "resolved_date": now - timedelta(days=110),
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "HAR-007",
                "sequence_id": "SEQ-007",
                "response_type": HAResponseType.INFORMATION_REQUEST,
                "response_date": now - timedelta(days=60),
                "due_date": now - timedelta(days=5),
                "summary": "PMDA questions on PK bridging study",
                "questions": [
                    "Clarify the PK bridging strategy for Japanese population",
                    "Provide additional ethnic sensitivity analysis",
                ],
                "action_items": [
                    "Submit PK bridging study addendum",
                    "Prepare ethnic sensitivity memo",
                ],
                "assigned_to": "Dr. Haruto Nakamura",
                "status": "open",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "HAR-008",
                "sequence_id": "SEQ-010",
                "response_type": HAResponseType.ACKNOWLEDGMENT,
                "response_date": now - timedelta(days=22),
                "summary": "EMA acknowledged receipt of Type II variation",
                "questions": [],
                "action_items": [],
                "status": "closed",
                "resolved_date": now - timedelta(days=22),
                "created_at": now - timedelta(days=22),
            },
            {
                "id": "HAR-009",
                "sequence_id": "SEQ-011",
                "response_type": HAResponseType.ACKNOWLEDGMENT,
                "response_date": now - timedelta(days=10),
                "summary": "MHRA acknowledged renewal application",
                "questions": [],
                "action_items": [],
                "status": "closed",
                "resolved_date": now - timedelta(days=10),
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "HAR-010",
                "sequence_id": "SEQ-001",
                "response_type": HAResponseType.APPROVABLE,
                "response_date": now - timedelta(days=7),
                "due_date": now + timedelta(days=90),
                "summary": "FDA Approvable letter for NDA-215-376 contingent on CMC amendments",
                "questions": [],
                "action_items": [
                    "Submit CMC stability amendment within 90 days",
                    "Update labeling per FDA comments",
                ],
                "assigned_to": "Dr. Anita Patel",
                "status": "open",
                "created_at": now - timedelta(days=7),
            },
        ]

        for data in ha_responses_data:
            har = HAResponse(**data)
            self._ha_responses[har.id] = har

        # --- 10 Submission Plans ---
        plans_data = [
            {
                "id": "PLAN-001",
                "trial_id": EYLEA_TRIAL,
                "plan_name": "EYLEA HD Global Registration Plan",
                "target_regions": [
                    RegulatoryRegion.US_FDA,
                    RegulatoryRegion.EU_EMA,
                    RegulatoryRegion.JAPAN_PMDA,
                    RegulatoryRegion.CANADA_HC,
                    RegulatoryRegion.UK_MHRA,
                ],
                "planned_sequences": 12,
                "completed_sequences": 3,
                "primary_contact": "Sarah Chen",
                "regulatory_lead": "Dr. Emily Watson",
                "status": "active",
                "notes": "Staggered submission strategy: US first, EU 30 days later, Japan 60 days later",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "PLAN-002",
                "trial_id": DUPIXENT_TRIAL,
                "plan_name": "DUPIXENT COPD sNDA/Variation Plan",
                "target_regions": [
                    RegulatoryRegion.US_FDA,
                    RegulatoryRegion.EU_EMA,
                ],
                "planned_sequences": 6,
                "completed_sequences": 1,
                "primary_contact": "Jennifer Adams",
                "regulatory_lead": "Dr. David Brown",
                "status": "active",
                "notes": "Priority review requested for US; accelerated assessment for EU",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "PLAN-003",
                "trial_id": DUPIXENT_TRIAL,
                "plan_name": "DUPIXENT Prurigo Nodularis Japan Plan",
                "target_regions": [
                    RegulatoryRegion.JAPAN_PMDA,
                ],
                "planned_sequences": 4,
                "completed_sequences": 1,
                "primary_contact": "Yuki Tanaka",
                "regulatory_lead": "Dr. Haruto Nakamura",
                "status": "active",
                "notes": "PK bridging strategy aligned with PMDA pre-submission meeting",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "PLAN-004",
                "trial_id": DUPIXENT_TRIAL,
                "plan_name": "DUPIXENT Annual Reporting Plan 2025",
                "target_regions": [
                    RegulatoryRegion.US_FDA,
                ],
                "planned_sequences": 1,
                "completed_sequences": 0,
                "primary_contact": "Jennifer Adams",
                "regulatory_lead": "Michael Rodriguez",
                "status": "active",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "PLAN-005",
                "trial_id": LIBTAYO_TRIAL,
                "plan_name": "LIBTAYO Adjuvant CSCC sBLA Plan",
                "target_regions": [
                    RegulatoryRegion.US_FDA,
                    RegulatoryRegion.EU_EMA,
                ],
                "planned_sequences": 4,
                "completed_sequences": 0,
                "primary_contact": "Robert Kim",
                "regulatory_lead": "Dr. Chris Taylor",
                "status": "active",
                "notes": "Breakthrough therapy designation — rolling submission eligible",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "PLAN-006",
                "trial_id": LIBTAYO_TRIAL,
                "plan_name": "LIBTAYO BCC EU Variation Plan",
                "target_regions": [
                    RegulatoryRegion.EU_EMA,
                ],
                "planned_sequences": 3,
                "completed_sequences": 1,
                "primary_contact": "Amanda Clarke",
                "regulatory_lead": "Dr. Steven White",
                "status": "active",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "PLAN-007",
                "trial_id": LIBTAYO_TRIAL,
                "plan_name": "LIBTAYO MHRA Post-Brexit Maintenance",
                "target_regions": [
                    RegulatoryRegion.UK_MHRA,
                ],
                "planned_sequences": 2,
                "completed_sequences": 1,
                "primary_contact": "Amanda Clarke",
                "regulatory_lead": "Dr. James Patterson",
                "status": "active",
                "notes": "Renewal + GMP variation pending",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "PLAN-008",
                "trial_id": LIBTAYO_TRIAL,
                "plan_name": "LIBTAYO NSCLC CRL Response Plan",
                "target_regions": [
                    RegulatoryRegion.US_FDA,
                ],
                "planned_sequences": 2,
                "completed_sequences": 0,
                "primary_contact": "Robert Kim",
                "regulatory_lead": "Dr. Natalie Green",
                "status": "active",
                "notes": "CRL response strategy under review with cross-functional team",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "PLAN-009",
                "trial_id": EYLEA_TRIAL,
                "plan_name": "EYLEA HD China NDA Plan",
                "target_regions": [
                    RegulatoryRegion.CHINA_NMPA,
                ],
                "planned_sequences": 3,
                "completed_sequences": 0,
                "primary_contact": "Dr. Wei Zhang",
                "regulatory_lead": "Dr. Emily Watson",
                "status": "active",
                "notes": "Pending bridging study completion; NMPA pre-IND meeting scheduled",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "PLAN-010",
                "trial_id": EYLEA_TRIAL,
                "plan_name": "EYLEA Original - Pediatric Variation (Completed)",
                "target_regions": [
                    RegulatoryRegion.EU_EMA,
                ],
                "planned_sequences": 2,
                "completed_sequences": 2,
                "primary_contact": "Sarah Chen",
                "regulatory_lead": "Dr. Emily Watson",
                "status": "completed",
                "notes": "Pediatric investigation plan completed and approved",
                "created_at": now - timedelta(days=365),
            },
        ]

        for data in plans_data:
            plan = SubmissionPlan(**data)
            self._plans[plan.id] = plan

        logger.info(
            "eCTD Submission demo data seeded: %d sequences, %d documents, "
            "%d validations, %d HA responses, %d plans",
            len(self._sequences),
            len(self._documents),
            len(self._validations),
            len(self._ha_responses),
            len(self._plans),
        )

    # ------------------------------------------------------------------
    # ECTDSequence CRUD
    # ------------------------------------------------------------------

    def create_sequence(self, payload: ECTDSequenceCreate) -> ECTDSequence:
        with self._lock:
            seq_id = f"SEQ-{uuid4().hex[:8].upper()}"
            now = datetime.now(timezone.utc)
            seq = ECTDSequence(
                id=seq_id,
                trial_id=payload.trial_id,
                sequence_number=payload.sequence_number,
                submission_type=payload.submission_type,
                region=payload.region,
                status=SequenceStatus.PLANNING,
                title=payload.title,
                description=payload.description,
                target_date=payload.target_date,
                publisher=payload.publisher,
                created_at=now,
            )
            self._sequences[seq_id] = seq
            return seq

    def get_sequence(self, sequence_id: str) -> ECTDSequence | None:
        return self._sequences.get(sequence_id)

    def list_sequences(
        self,
        trial_id: str | None = None,
        region: RegulatoryRegion | None = None,
        status: SequenceStatus | None = None,
        submission_type: SubmissionType | None = None,
    ) -> list[ECTDSequence]:
        results = list(self._sequences.values())
        if trial_id:
            results = [s for s in results if s.trial_id == trial_id]
        if region:
            results = [s for s in results if s.region == region]
        if status:
            results = [s for s in results if s.status == status]
        if submission_type:
            results = [s for s in results if s.submission_type == submission_type]
        return results

    def update_sequence(
        self, sequence_id: str, payload: ECTDSequenceUpdate
    ) -> ECTDSequence | None:
        with self._lock:
            seq = self._sequences.get(sequence_id)
            if not seq:
                return None
            data = seq.model_dump()
            updates = payload.model_dump(exclude_none=True)
            data.update(updates)
            updated = ECTDSequence(**data)
            self._sequences[sequence_id] = updated
            return updated

    def delete_sequence(self, sequence_id: str) -> bool:
        with self._lock:
            return self._sequences.pop(sequence_id, None) is not None

    # ------------------------------------------------------------------
    # ECTDDocument CRUD
    # ------------------------------------------------------------------

    def create_document(self, payload: ECTDDocumentCreate) -> ECTDDocument:
        with self._lock:
            doc_id = f"DOC-{uuid4().hex[:8].upper()}"
            now = datetime.now(timezone.utc)
            doc = ECTDDocument(
                id=doc_id,
                sequence_id=payload.sequence_id,
                module=payload.module,
                section_number=payload.section_number,
                title=payload.title,
                file_name=payload.file_name,
                lifecycle_operation=payload.lifecycle_operation,
                author=payload.author,
                created_at=now,
            )
            self._documents[doc_id] = doc
            return doc

    def get_document(self, document_id: str) -> ECTDDocument | None:
        return self._documents.get(document_id)

    def list_documents(
        self,
        sequence_id: str | None = None,
        module: CTDModule | None = None,
        approved: bool | None = None,
    ) -> list[ECTDDocument]:
        results = list(self._documents.values())
        if sequence_id:
            results = [d for d in results if d.sequence_id == sequence_id]
        if module:
            results = [d for d in results if d.module == module]
        if approved is not None:
            results = [d for d in results if d.approved == approved]
        return results

    def update_document(
        self, document_id: str, payload: ECTDDocumentUpdate
    ) -> ECTDDocument | None:
        with self._lock:
            doc = self._documents.get(document_id)
            if not doc:
                return None
            data = doc.model_dump()
            updates = payload.model_dump(exclude_none=True)
            if updates.get("approved"):
                updates["approved_date"] = datetime.now(timezone.utc)
            data.update(updates)
            updated = ECTDDocument(**data)
            self._documents[document_id] = updated
            return updated

    def delete_document(self, document_id: str) -> bool:
        with self._lock:
            return self._documents.pop(document_id, None) is not None

    # ------------------------------------------------------------------
    # ECTDValidation CRUD
    # ------------------------------------------------------------------

    def create_validation(self, payload: ECTDValidationCreate) -> ECTDValidation:
        with self._lock:
            val_id = f"VAL-{uuid4().hex[:8].upper()}"
            now = datetime.now(timezone.utc)
            val = ECTDValidation(
                id=val_id,
                sequence_id=payload.sequence_id,
                validation_tool=payload.validation_tool,
                validation_date=now,
                passed=payload.passed,
                errors=payload.errors,
                warnings=payload.warnings,
                error_details=payload.error_details,
                validator=payload.validator,
            )
            self._validations[val_id] = val
            return val

    def get_validation(self, validation_id: str) -> ECTDValidation | None:
        return self._validations.get(validation_id)

    def list_validations(
        self,
        sequence_id: str | None = None,
        passed: bool | None = None,
    ) -> list[ECTDValidation]:
        results = list(self._validations.values())
        if sequence_id:
            results = [v for v in results if v.sequence_id == sequence_id]
        if passed is not None:
            results = [v for v in results if v.passed == passed]
        return results

    def delete_validation(self, validation_id: str) -> bool:
        with self._lock:
            return self._validations.pop(validation_id, None) is not None

    # ------------------------------------------------------------------
    # HAResponse CRUD
    # ------------------------------------------------------------------

    def create_ha_response(self, payload: HAResponseCreate) -> HAResponse:
        with self._lock:
            har_id = f"HAR-{uuid4().hex[:8].upper()}"
            now = datetime.now(timezone.utc)
            har = HAResponse(
                id=har_id,
                sequence_id=payload.sequence_id,
                response_type=payload.response_type,
                response_date=now,
                due_date=payload.due_date,
                summary=payload.summary,
                questions=payload.questions,
                action_items=payload.action_items,
                assigned_to=payload.assigned_to,
                status="open",
                created_at=now,
            )
            self._ha_responses[har_id] = har
            return har

    def get_ha_response(self, response_id: str) -> HAResponse | None:
        return self._ha_responses.get(response_id)

    def list_ha_responses(
        self,
        sequence_id: str | None = None,
        response_type: HAResponseType | None = None,
        status: str | None = None,
    ) -> list[HAResponse]:
        results = list(self._ha_responses.values())
        if sequence_id:
            results = [r for r in results if r.sequence_id == sequence_id]
        if response_type:
            results = [r for r in results if r.response_type == response_type]
        if status:
            results = [r for r in results if r.status == status]
        return results

    def update_ha_response(
        self, response_id: str, payload: HAResponseUpdate
    ) -> HAResponse | None:
        with self._lock:
            har = self._ha_responses.get(response_id)
            if not har:
                return None
            data = har.model_dump()
            updates = payload.model_dump(exclude_none=True)
            if updates.get("status") == "closed" and not data.get("resolved_date"):
                updates["resolved_date"] = datetime.now(timezone.utc)
            data.update(updates)
            updated = HAResponse(**data)
            self._ha_responses[response_id] = updated
            return updated

    def delete_ha_response(self, response_id: str) -> bool:
        with self._lock:
            return self._ha_responses.pop(response_id, None) is not None

    # ------------------------------------------------------------------
    # SubmissionPlan CRUD
    # ------------------------------------------------------------------

    def create_plan(self, payload: SubmissionPlanCreate) -> SubmissionPlan:
        with self._lock:
            plan_id = f"PLAN-{uuid4().hex[:8].upper()}"
            now = datetime.now(timezone.utc)
            plan = SubmissionPlan(
                id=plan_id,
                trial_id=payload.trial_id,
                plan_name=payload.plan_name,
                target_regions=payload.target_regions,
                primary_contact=payload.primary_contact,
                regulatory_lead=payload.regulatory_lead,
                created_at=now,
            )
            self._plans[plan_id] = plan
            return plan

    def get_plan(self, plan_id: str) -> SubmissionPlan | None:
        return self._plans.get(plan_id)

    def list_plans(
        self,
        trial_id: str | None = None,
        status: str | None = None,
    ) -> list[SubmissionPlan]:
        results = list(self._plans.values())
        if trial_id:
            results = [p for p in results if p.trial_id == trial_id]
        if status:
            results = [p for p in results if p.status == status]
        return results

    def update_plan(
        self, plan_id: str, payload: SubmissionPlanUpdate
    ) -> SubmissionPlan | None:
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                return None
            data = plan.model_dump()
            updates = payload.model_dump(exclude_none=True)
            data.update(updates)
            updated = SubmissionPlan(**data)
            self._plans[plan_id] = updated
            return updated

    def delete_plan(self, plan_id: str) -> bool:
        with self._lock:
            return self._plans.pop(plan_id, None) is not None

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> ECTDMetrics:
        sequences = list(self._sequences.values())
        documents = list(self._documents.values())
        validations = list(self._validations.values())
        ha_responses = list(self._ha_responses.values())
        plans = list(self._plans.values())

        sequences_by_status: dict[str, int] = {}
        for s in sequences:
            key = s.status.value
            sequences_by_status[key] = sequences_by_status.get(key, 0) + 1

        sequences_by_type: dict[str, int] = {}
        for s in sequences:
            key = s.submission_type.value
            sequences_by_type[key] = sequences_by_type.get(key, 0) + 1

        sequences_by_region: dict[str, int] = {}
        for s in sequences:
            key = s.region.value
            sequences_by_region[key] = sequences_by_region.get(key, 0) + 1

        documents_by_module: dict[str, int] = {}
        for d in documents:
            key = d.module.value
            documents_by_module[key] = documents_by_module.get(key, 0) + 1

        approved_docs = sum(1 for d in documents if d.approved)

        passed = sum(1 for v in validations if v.passed)
        total_val = len(validations)
        pass_rate = (passed / total_val * 100) if total_val > 0 else 0.0

        responses_by_type: dict[str, int] = {}
        for r in ha_responses:
            key = r.response_type.value
            responses_by_type[key] = responses_by_type.get(key, 0) + 1

        open_responses = sum(1 for r in ha_responses if r.status == "open")
        active_plans = sum(1 for p in plans if p.status == "active")

        return ECTDMetrics(
            total_sequences=len(sequences),
            sequences_by_status=sequences_by_status,
            sequences_by_type=sequences_by_type,
            sequences_by_region=sequences_by_region,
            total_documents=len(documents),
            documents_by_module=documents_by_module,
            approved_documents=approved_docs,
            total_validations=total_val,
            validation_pass_rate_pct=round(pass_rate, 1),
            total_ha_responses=len(ha_responses),
            responses_by_type=responses_by_type,
            open_responses=open_responses,
            total_plans=len(plans),
            active_plans=active_plans,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ECTDSubmissionService | None = None
_instance_lock = threading.Lock()


def get_ectd_submission_service() -> ECTDSubmissionService:
    """Return the singleton ECTDSubmissionService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ECTDSubmissionService()
    return _instance


def reset_ectd_submission_service() -> ECTDSubmissionService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = ECTDSubmissionService()
    return _instance
