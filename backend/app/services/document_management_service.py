"""Clinical Document Management Service (DOC-MGMT).

Manages clinical trial document lifecycle: document creation, version control,
review and approval workflows, regulatory filing, archival, document access
control, and document metrics.

Usage:
    from app.services.document_management_service import (
        get_document_management_service,
    )

    svc = get_document_management_service()
    documents = svc.list_documents()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.document_management import (
    AccessLevel,
    ClinicalDocument,
    ClinicalDocumentCreate,
    ClinicalDocumentUpdate,
    DocumentFiling,
    DocumentFilingCreate,
    DocumentManagementMetrics,
    DocumentReview,
    DocumentReviewCreate,
    DocumentReviewUpdate,
    DocumentStatus,
    DocumentType,
    DocumentVersion,
    DocumentVersionCreate,
    ReviewDecision,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class DocumentManagementService:
    """In-memory Clinical Document Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._documents: dict[str, ClinicalDocument] = {}
        self._versions: dict[str, DocumentVersion] = {}
        self._reviews: dict[str, DocumentReview] = {}
        self._filings: dict[str, DocumentFiling] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic document management data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Clinical Documents ---
        documents_data = [
            # EYLEA trial documents
            {"id": "DOC-001", "trial_id": EYLEA_TRIAL, "document_type": DocumentType.PROTOCOL, "title": "EYLEA HD Phase 3 Protocol - Wet AMD", "document_number": "REGN-EYLEA-PROT-001", "version": "3.0", "status": DocumentStatus.EFFECTIVE, "author": "Dr. George Yancopoulos", "owner": "Clinical Development", "access_level": AccessLevel.CONFIDENTIAL, "effective_date": now - timedelta(days=180), "expiry_date": None, "file_reference": "/docs/eylea/protocol_v3.0.pdf", "file_size_bytes": 2457600, "page_count": 142, "tags": ["protocol", "wet-amd", "phase-3"], "created_at": now - timedelta(days=365), "updated_at": now - timedelta(days=30)},
            {"id": "DOC-002", "trial_id": EYLEA_TRIAL, "document_type": DocumentType.INVESTIGATOR_BROCHURE, "title": "EYLEA HD Investigator Brochure", "document_number": "REGN-EYLEA-IB-001", "version": "5.0", "status": DocumentStatus.EFFECTIVE, "author": "Dr. Robert Vitti", "owner": "Medical Affairs", "access_level": AccessLevel.CONFIDENTIAL, "effective_date": now - timedelta(days=120), "expiry_date": None, "file_reference": "/docs/eylea/ib_v5.0.pdf", "file_size_bytes": 3145728, "page_count": 198, "tags": ["investigator-brochure", "safety", "pharmacology"], "created_at": now - timedelta(days=400), "updated_at": now - timedelta(days=45)},
            {"id": "DOC-003", "trial_id": EYLEA_TRIAL, "document_type": DocumentType.ICF, "title": "EYLEA HD Informed Consent Form - US Sites", "document_number": "REGN-EYLEA-ICF-US-001", "version": "2.1", "status": DocumentStatus.APPROVED, "author": "Regulatory Affairs Team", "owner": "Regulatory Affairs", "access_level": AccessLevel.INTERNAL, "effective_date": now - timedelta(days=90), "expiry_date": None, "file_reference": "/docs/eylea/icf_us_v2.1.pdf", "file_size_bytes": 524288, "page_count": 28, "tags": ["icf", "consent", "us-sites"], "created_at": now - timedelta(days=200), "updated_at": now - timedelta(days=60)},
            {"id": "DOC-004", "trial_id": EYLEA_TRIAL, "document_type": DocumentType.SAP, "title": "EYLEA HD Statistical Analysis Plan", "document_number": "REGN-EYLEA-SAP-001", "version": "1.2", "status": DocumentStatus.IN_REVIEW, "author": "Dr. Amy Liu", "owner": "Biostatistics", "access_level": AccessLevel.CONFIDENTIAL, "effective_date": None, "expiry_date": None, "file_reference": "/docs/eylea/sap_v1.2.pdf", "file_size_bytes": 1048576, "page_count": 86, "tags": ["sap", "statistics", "analysis-plan"], "created_at": now - timedelta(days=150), "updated_at": now - timedelta(days=10)},

            # Dupixent trial documents
            {"id": "DOC-005", "trial_id": DUPIXENT_TRIAL, "document_type": DocumentType.PROTOCOL, "title": "Dupixent Phase 3b Protocol - Atopic Dermatitis", "document_number": "REGN-DUP-PROT-001", "version": "2.0", "status": DocumentStatus.EFFECTIVE, "author": "Dr. Naimish Patel", "owner": "Clinical Development", "access_level": AccessLevel.CONFIDENTIAL, "effective_date": now - timedelta(days=240), "expiry_date": None, "file_reference": "/docs/dupixent/protocol_v2.0.pdf", "file_size_bytes": 2097152, "page_count": 128, "tags": ["protocol", "atopic-dermatitis", "phase-3b"], "created_at": now - timedelta(days=400), "updated_at": now - timedelta(days=50)},
            {"id": "DOC-006", "trial_id": DUPIXENT_TRIAL, "document_type": DocumentType.MONITORING_PLAN, "title": "Dupixent Site Monitoring Plan", "document_number": "REGN-DUP-MP-001", "version": "1.1", "status": DocumentStatus.EFFECTIVE, "author": "Clinical Operations", "owner": "Clinical Operations", "access_level": AccessLevel.INTERNAL, "effective_date": now - timedelta(days=200), "expiry_date": None, "file_reference": "/docs/dupixent/monitoring_plan_v1.1.pdf", "file_size_bytes": 786432, "page_count": 54, "tags": ["monitoring", "site-management", "risk-based"], "created_at": now - timedelta(days=300), "updated_at": now - timedelta(days=80)},
            {"id": "DOC-007", "trial_id": DUPIXENT_TRIAL, "document_type": DocumentType.DATA_MANAGEMENT_PLAN, "title": "Dupixent Data Management Plan", "document_number": "REGN-DUP-DMP-001", "version": "1.0", "status": DocumentStatus.APPROVED, "author": "Data Management Team", "owner": "Data Management", "access_level": AccessLevel.INTERNAL, "effective_date": now - timedelta(days=180), "expiry_date": None, "file_reference": "/docs/dupixent/dmp_v1.0.pdf", "file_size_bytes": 655360, "page_count": 42, "tags": ["data-management", "crf", "edit-checks"], "created_at": now - timedelta(days=250), "updated_at": now - timedelta(days=100)},
            {"id": "DOC-008", "trial_id": DUPIXENT_TRIAL, "document_type": DocumentType.SAFETY_PLAN, "title": "Dupixent Safety Management Plan", "document_number": "REGN-DUP-SMP-001", "version": "2.0", "status": DocumentStatus.DRAFT, "author": "Pharmacovigilance Team", "owner": "Drug Safety", "access_level": AccessLevel.RESTRICTED, "effective_date": None, "expiry_date": None, "file_reference": "/docs/dupixent/safety_plan_v2.0_draft.pdf", "file_size_bytes": 917504, "page_count": 68, "tags": ["safety", "pharmacovigilance", "sae-reporting"], "created_at": now - timedelta(days=60), "updated_at": now - timedelta(days=5)},

            # Libtayo trial documents
            {"id": "DOC-009", "trial_id": LIBTAYO_TRIAL, "document_type": DocumentType.PROTOCOL, "title": "Libtayo Phase 3 Protocol - Advanced CSCC", "document_number": "REGN-LIB-PROT-001", "version": "4.0", "status": DocumentStatus.EFFECTIVE, "author": "Dr. Israel Lowy", "owner": "Clinical Development", "access_level": AccessLevel.CONFIDENTIAL, "effective_date": now - timedelta(days=150), "expiry_date": None, "file_reference": "/docs/libtayo/protocol_v4.0.pdf", "file_size_bytes": 2621440, "page_count": 156, "tags": ["protocol", "cscc", "immuno-oncology"], "created_at": now - timedelta(days=500), "updated_at": now - timedelta(days=25)},
            {"id": "DOC-010", "trial_id": LIBTAYO_TRIAL, "document_type": DocumentType.CSR, "title": "Libtayo Interim Clinical Study Report", "document_number": "REGN-LIB-CSR-INT-001", "version": "1.0", "status": DocumentStatus.SUPERSEDED, "author": "Medical Writing Team", "owner": "Medical Writing", "access_level": AccessLevel.RESTRICTED, "effective_date": now - timedelta(days=300), "expiry_date": now - timedelta(days=100), "file_reference": "/docs/libtayo/csr_interim_v1.0.pdf", "file_size_bytes": 5242880, "page_count": 312, "tags": ["csr", "interim", "efficacy-analysis"], "created_at": now - timedelta(days=350), "updated_at": now - timedelta(days=100)},
            {"id": "DOC-011", "trial_id": LIBTAYO_TRIAL, "document_type": DocumentType.REGULATORY_SUBMISSION, "title": "Libtayo sBLA Submission Package - CSCC", "document_number": "REGN-LIB-REG-001", "version": "1.0", "status": DocumentStatus.ARCHIVED, "author": "Regulatory Affairs", "owner": "Regulatory Affairs", "access_level": AccessLevel.RESTRICTED, "effective_date": now - timedelta(days=400), "expiry_date": None, "file_reference": "/docs/libtayo/sbla_submission_v1.0.pdf", "file_size_bytes": 10485760, "page_count": 524, "tags": ["regulatory", "sbla", "fda-submission"], "created_at": now - timedelta(days=450), "updated_at": now - timedelta(days=200)},
            {"id": "DOC-012", "trial_id": LIBTAYO_TRIAL, "document_type": DocumentType.SITE_TRAINING, "title": "Libtayo Site Training Materials - irAE Management", "document_number": "REGN-LIB-TRN-001", "version": "2.0", "status": DocumentStatus.EFFECTIVE, "author": "Medical Affairs", "owner": "Medical Affairs", "access_level": AccessLevel.PUBLIC, "effective_date": now - timedelta(days=100), "expiry_date": None, "file_reference": "/docs/libtayo/training_irae_v2.0.pdf", "file_size_bytes": 1572864, "page_count": 96, "tags": ["training", "irae", "site-materials"], "created_at": now - timedelta(days=200), "updated_at": now - timedelta(days=40)},
        ]

        for d in documents_data:
            self._documents[d["id"]] = ClinicalDocument(**d)

        # --- 15 Document Versions ---
        versions_data = [
            {"id": "VER-001", "document_id": "DOC-001", "version": "1.0", "change_summary": "Initial protocol draft submitted for internal review", "changed_by": "Dr. George Yancopoulos", "change_date": now - timedelta(days=365), "previous_version_id": None, "file_reference": "/docs/eylea/protocol_v1.0.pdf"},
            {"id": "VER-002", "document_id": "DOC-001", "version": "2.0", "change_summary": "Added secondary endpoints per FDA feedback. Updated inclusion criteria.", "changed_by": "Dr. George Yancopoulos", "change_date": now - timedelta(days=270), "previous_version_id": "VER-001", "file_reference": "/docs/eylea/protocol_v2.0.pdf"},
            {"id": "VER-003", "document_id": "DOC-001", "version": "3.0", "change_summary": "Amendment 2: Extended treatment period to 96 weeks per DSMB recommendation.", "changed_by": "Dr. George Yancopoulos", "change_date": now - timedelta(days=180), "previous_version_id": "VER-002", "file_reference": "/docs/eylea/protocol_v3.0.pdf"},
            {"id": "VER-004", "document_id": "DOC-002", "version": "4.0", "change_summary": "Updated safety data from ongoing studies. New preclinical findings added.", "changed_by": "Dr. Robert Vitti", "change_date": now - timedelta(days=200), "previous_version_id": None, "file_reference": "/docs/eylea/ib_v4.0.pdf"},
            {"id": "VER-005", "document_id": "DOC-002", "version": "5.0", "change_summary": "Incorporated post-marketing safety data. Updated risk-benefit assessment.", "changed_by": "Dr. Robert Vitti", "change_date": now - timedelta(days=120), "previous_version_id": "VER-004", "file_reference": "/docs/eylea/ib_v5.0.pdf"},
            {"id": "VER-006", "document_id": "DOC-003", "version": "1.0", "change_summary": "Initial ICF based on approved protocol v2.0", "changed_by": "Regulatory Affairs Team", "change_date": now - timedelta(days=200), "previous_version_id": None, "file_reference": "/docs/eylea/icf_us_v1.0.pdf"},
            {"id": "VER-007", "document_id": "DOC-003", "version": "2.0", "change_summary": "Updated per IRB feedback. Added new risk disclosures.", "changed_by": "Regulatory Affairs Team", "change_date": now - timedelta(days=120), "previous_version_id": "VER-006", "file_reference": "/docs/eylea/icf_us_v2.0.pdf"},
            {"id": "VER-008", "document_id": "DOC-003", "version": "2.1", "change_summary": "Minor formatting corrections and typo fixes per IRB comments.", "changed_by": "Regulatory Affairs Team", "change_date": now - timedelta(days=90), "previous_version_id": "VER-007", "file_reference": "/docs/eylea/icf_us_v2.1.pdf"},
            {"id": "VER-009", "document_id": "DOC-005", "version": "1.0", "change_summary": "Initial Dupixent protocol for atopic dermatitis phase 3b study", "changed_by": "Dr. Naimish Patel", "change_date": now - timedelta(days=400), "previous_version_id": None, "file_reference": "/docs/dupixent/protocol_v1.0.pdf"},
            {"id": "VER-010", "document_id": "DOC-005", "version": "2.0", "change_summary": "Protocol amendment 1: Added adolescent cohort and updated EASI scoring criteria.", "changed_by": "Dr. Naimish Patel", "change_date": now - timedelta(days=240), "previous_version_id": "VER-009", "file_reference": "/docs/dupixent/protocol_v2.0.pdf"},
            {"id": "VER-011", "document_id": "DOC-009", "version": "3.0", "change_summary": "Protocol amendment 2: Added RECIST 1.1 central review. Updated PFS definition.", "changed_by": "Dr. Israel Lowy", "change_date": now - timedelta(days=300), "previous_version_id": None, "file_reference": "/docs/libtayo/protocol_v3.0.pdf"},
            {"id": "VER-012", "document_id": "DOC-009", "version": "4.0", "change_summary": "Amendment 3: Added pseudoprogression criteria and iRECIST assessment schedule.", "changed_by": "Dr. Israel Lowy", "change_date": now - timedelta(days=150), "previous_version_id": "VER-011", "file_reference": "/docs/libtayo/protocol_v4.0.pdf"},
            {"id": "VER-013", "document_id": "DOC-012", "version": "1.0", "change_summary": "Initial site training materials for irAE identification and management", "changed_by": "Medical Affairs", "change_date": now - timedelta(days=200), "previous_version_id": None, "file_reference": "/docs/libtayo/training_irae_v1.0.pdf"},
            {"id": "VER-014", "document_id": "DOC-012", "version": "2.0", "change_summary": "Updated management algorithms per new ASCO guidelines. Added case studies.", "changed_by": "Medical Affairs", "change_date": now - timedelta(days=100), "previous_version_id": "VER-013", "file_reference": "/docs/libtayo/training_irae_v2.0.pdf"},
            {"id": "VER-015", "document_id": "DOC-004", "version": "1.2", "change_summary": "Updated primary analysis methods. Added sensitivity analyses per FDA request.", "changed_by": "Dr. Amy Liu", "change_date": now - timedelta(days=10), "previous_version_id": None, "file_reference": "/docs/eylea/sap_v1.2.pdf"},
        ]

        for v in versions_data:
            self._versions[v["id"]] = DocumentVersion(**v)

        # --- 15 Document Reviews ---
        reviews_data = [
            {"id": "REV-001", "document_id": "DOC-001", "version_id": "VER-003", "reviewer": "Dr. Leonard Schleifer", "reviewer_role": "Chief Executive Officer", "assigned_date": now - timedelta(days=195), "due_date": now - timedelta(days=185), "completed_date": now - timedelta(days=188), "decision": ReviewDecision.APPROVED, "comments": "Protocol amendment approved. Extends treatment window appropriately."},
            {"id": "REV-002", "document_id": "DOC-001", "version_id": "VER-003", "reviewer": "Dr. Robert Vitti", "reviewer_role": "VP Clinical Research", "assigned_date": now - timedelta(days=195), "due_date": now - timedelta(days=185), "completed_date": now - timedelta(days=190), "decision": ReviewDecision.APPROVED_WITH_COMMENTS, "comments": "Approved. Suggest adding clarity on rescue therapy criteria in section 6.3."},
            {"id": "REV-003", "document_id": "DOC-002", "version_id": "VER-005", "reviewer": "Dr. Sarah Chen", "reviewer_role": "Safety Officer", "assigned_date": now - timedelta(days=135), "due_date": now - timedelta(days=125), "completed_date": now - timedelta(days=128), "decision": ReviewDecision.APPROVED, "comments": "IB update incorporates all relevant safety findings. Approved for distribution."},
            {"id": "REV-004", "document_id": "DOC-003", "version_id": "VER-008", "reviewer": "IRB Central Committee", "reviewer_role": "Ethics Review Board", "assigned_date": now - timedelta(days=100), "due_date": now - timedelta(days=85), "completed_date": now - timedelta(days=92), "decision": ReviewDecision.APPROVED, "comments": "ICF meets all regulatory requirements. Approved for use at US sites."},
            {"id": "REV-005", "document_id": "DOC-004", "version_id": "VER-015", "reviewer": "Dr. Michael Brown", "reviewer_role": "Head of Biostatistics", "assigned_date": now - timedelta(days=15), "due_date": now - timedelta(days=5), "completed_date": None, "decision": None, "comments": None},
            {"id": "REV-006", "document_id": "DOC-004", "version_id": "VER-015", "reviewer": "FDA Statistical Reviewer", "reviewer_role": "Regulatory Reviewer", "assigned_date": now - timedelta(days=15), "due_date": now - timedelta(days=1), "completed_date": None, "decision": None, "comments": None},
            {"id": "REV-007", "document_id": "DOC-005", "version_id": "VER-010", "reviewer": "Dr. Naimish Patel", "reviewer_role": "Study Director", "assigned_date": now - timedelta(days=255), "due_date": now - timedelta(days=245), "completed_date": now - timedelta(days=248), "decision": ReviewDecision.APPROVED, "comments": "Protocol amendment meets all objectives. Adolescent cohort design is sound."},
            {"id": "REV-008", "document_id": "DOC-005", "version_id": "VER-010", "reviewer": "Ethics Committee", "reviewer_role": "Ethics Review Board", "assigned_date": now - timedelta(days=255), "due_date": now - timedelta(days=240), "completed_date": now - timedelta(days=243), "decision": ReviewDecision.APPROVED_WITH_COMMENTS, "comments": "Approved with request to update adolescent assent form."},
            {"id": "REV-009", "document_id": "DOC-008", "version_id": None, "reviewer": "Dr. Patricia Sullivan", "reviewer_role": "Pharmacovigilance Lead", "assigned_date": now - timedelta(days=8), "due_date": now + timedelta(days=7), "completed_date": None, "decision": None, "comments": None},
            {"id": "REV-010", "document_id": "DOC-009", "version_id": "VER-012", "reviewer": "Dr. Israel Lowy", "reviewer_role": "VP Immuno-Oncology", "assigned_date": now - timedelta(days=165), "due_date": now - timedelta(days=155), "completed_date": now - timedelta(days=158), "decision": ReviewDecision.APPROVED, "comments": "Pseudoprogression criteria are well-defined. Amendment approved."},
            {"id": "REV-011", "document_id": "DOC-009", "version_id": "VER-012", "reviewer": "DSMB Chair", "reviewer_role": "Safety Monitoring Board", "assigned_date": now - timedelta(days=165), "due_date": now - timedelta(days=150), "completed_date": now - timedelta(days=153), "decision": ReviewDecision.APPROVED, "comments": "iRECIST criteria appropriate. Safety monitoring plan adequate."},
            {"id": "REV-012", "document_id": "DOC-010", "version_id": None, "reviewer": "Regulatory Affairs Lead", "reviewer_role": "Regulatory Reviewer", "assigned_date": now - timedelta(days=360), "due_date": now - timedelta(days=345), "completed_date": now - timedelta(days=348), "decision": ReviewDecision.REVISION_REQUIRED, "comments": "CSR needs additional sensitivity analyses for the ITT population."},
            {"id": "REV-013", "document_id": "DOC-011", "version_id": None, "reviewer": "FDA Submission Team", "reviewer_role": "Regulatory Reviewer", "assigned_date": now - timedelta(days=420), "due_date": now - timedelta(days=405), "completed_date": now - timedelta(days=410), "decision": ReviewDecision.APPROVED, "comments": "Submission package complete. Ready for FDA filing."},
            {"id": "REV-014", "document_id": "DOC-006", "version_id": None, "reviewer": "Clinical Operations Director", "reviewer_role": "Operations Lead", "assigned_date": now - timedelta(days=215), "due_date": now - timedelta(days=205), "completed_date": now - timedelta(days=208), "decision": ReviewDecision.APPROVED, "comments": "Monitoring plan covers all risk-based monitoring requirements."},
            {"id": "REV-015", "document_id": "DOC-007", "version_id": None, "reviewer": "Data Management Lead", "reviewer_role": "Data Management", "assigned_date": now - timedelta(days=260), "due_date": now - timedelta(days=248), "completed_date": now - timedelta(days=251), "decision": ReviewDecision.APPROVED_WITH_COMMENTS, "comments": "Approved. Recommend adding edit check specifications for lab data."},
        ]

        for r in reviews_data:
            self._reviews[r["id"]] = DocumentReview(**r)

        # --- 12 Document Filings ---
        filings_data = [
            {"id": "FIL-001", "document_id": "DOC-001", "filing_location": "eTMF/Trial Master File/Protocol", "filed_by": "Regulatory Affairs", "filed_date": now - timedelta(days=178), "regulatory_authority": "FDA", "filing_reference": "IND-2024-EYLEA-PROT-003", "confirmed": True},
            {"id": "FIL-002", "document_id": "DOC-001", "filing_location": "eTMF/Trial Master File/Protocol", "filed_by": "Regulatory Affairs", "filed_date": now - timedelta(days=175), "regulatory_authority": "EMA", "filing_reference": "CTA-2024-EYLEA-PROT-003", "confirmed": True},
            {"id": "FIL-003", "document_id": "DOC-002", "filing_location": "eTMF/Trial Master File/Investigator Brochure", "filed_by": "Medical Affairs", "filed_date": now - timedelta(days=118), "regulatory_authority": "FDA", "filing_reference": "IND-EYLEA-IB-005", "confirmed": True},
            {"id": "FIL-004", "document_id": "DOC-003", "filing_location": "eTMF/Site Documents/ICF", "filed_by": "Site Management", "filed_date": now - timedelta(days=88), "regulatory_authority": None, "filing_reference": "IRB-EYLEA-ICF-US-2.1", "confirmed": True},
            {"id": "FIL-005", "document_id": "DOC-005", "filing_location": "eTMF/Trial Master File/Protocol", "filed_by": "Regulatory Affairs", "filed_date": now - timedelta(days=238), "regulatory_authority": "FDA", "filing_reference": "IND-DUP-PROT-002", "confirmed": True},
            {"id": "FIL-006", "document_id": "DOC-006", "filing_location": "eTMF/Operations/Monitoring Plan", "filed_by": "Clinical Operations", "filed_date": now - timedelta(days=198), "regulatory_authority": None, "filing_reference": None, "confirmed": True},
            {"id": "FIL-007", "document_id": "DOC-009", "filing_location": "eTMF/Trial Master File/Protocol", "filed_by": "Regulatory Affairs", "filed_date": now - timedelta(days=148), "regulatory_authority": "FDA", "filing_reference": "IND-LIB-PROT-004", "confirmed": True},
            {"id": "FIL-008", "document_id": "DOC-009", "filing_location": "eTMF/Trial Master File/Protocol", "filed_by": "Regulatory Affairs", "filed_date": now - timedelta(days=145), "regulatory_authority": "EMA", "filing_reference": "CTA-LIB-PROT-004", "confirmed": True},
            {"id": "FIL-009", "document_id": "DOC-011", "filing_location": "Regulatory Submissions/sBLA", "filed_by": "Regulatory Affairs", "filed_date": now - timedelta(days=398), "regulatory_authority": "FDA", "filing_reference": "sBLA-761183-CSCC", "confirmed": True},
            {"id": "FIL-010", "document_id": "DOC-010", "filing_location": "eTMF/Reports/CSR", "filed_by": "Medical Writing", "filed_date": now - timedelta(days=348), "regulatory_authority": None, "filing_reference": None, "confirmed": False},
            {"id": "FIL-011", "document_id": "DOC-012", "filing_location": "eTMF/Training Materials", "filed_by": "Medical Affairs", "filed_date": now - timedelta(days=98), "regulatory_authority": None, "filing_reference": None, "confirmed": True},
            {"id": "FIL-012", "document_id": "DOC-007", "filing_location": "eTMF/Data Management", "filed_by": "Data Management", "filed_date": now - timedelta(days=178), "regulatory_authority": None, "filing_reference": None, "confirmed": True},
        ]

        for f in filings_data:
            self._filings[f["id"]] = DocumentFiling(**f)

    # ------------------------------------------------------------------
    # Document Management
    # ------------------------------------------------------------------

    def list_documents(
        self,
        *,
        trial_id: str | None = None,
        document_type: DocumentType | None = None,
        status: DocumentStatus | None = None,
        access_level: AccessLevel | None = None,
    ) -> list[ClinicalDocument]:
        """List clinical documents with optional filters."""
        with self._lock:
            result = list(self._documents.values())

        if trial_id is not None:
            result = [d for d in result if d.trial_id == trial_id]
        if document_type is not None:
            result = [d for d in result if d.document_type == document_type]
        if status is not None:
            result = [d for d in result if d.status == status]
        if access_level is not None:
            result = [d for d in result if d.access_level == access_level]

        return sorted(result, key=lambda d: d.id)

    def get_document(self, document_id: str) -> ClinicalDocument | None:
        """Get a single document by ID."""
        with self._lock:
            return self._documents.get(document_id)

    def create_document(self, payload: ClinicalDocumentCreate) -> ClinicalDocument:
        """Create a new clinical document."""
        now = datetime.now(timezone.utc)
        document_id = f"DOC-{uuid4().hex[:8].upper()}"
        document = ClinicalDocument(
            id=document_id,
            trial_id=payload.trial_id,
            document_type=payload.document_type,
            title=payload.title,
            document_number=payload.document_number,
            version=payload.version,
            status=DocumentStatus.DRAFT,
            author=payload.author,
            owner=payload.owner,
            access_level=payload.access_level,
            tags=payload.tags,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._documents[document_id] = document
        logger.info("Created document %s: %s", document_id, payload.title)
        return document

    def update_document(
        self, document_id: str, payload: ClinicalDocumentUpdate
    ) -> ClinicalDocument | None:
        """Update an existing document."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._documents.get(document_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            data["updated_at"] = now
            updated = ClinicalDocument(**data)
            self._documents[document_id] = updated
        return updated

    def delete_document(self, document_id: str) -> bool:
        """Delete a document. Returns True if deleted."""
        with self._lock:
            if document_id in self._documents:
                del self._documents[document_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Version Management
    # ------------------------------------------------------------------

    def list_versions(
        self,
        *,
        document_id: str | None = None,
    ) -> list[DocumentVersion]:
        """List document versions with optional filter."""
        with self._lock:
            result = list(self._versions.values())

        if document_id is not None:
            result = [v for v in result if v.document_id == document_id]

        return sorted(result, key=lambda v: v.change_date, reverse=True)

    def get_version(self, version_id: str) -> DocumentVersion | None:
        """Get a single version by ID."""
        with self._lock:
            return self._versions.get(version_id)

    def create_version(self, payload: DocumentVersionCreate) -> DocumentVersion | None:
        """Create a new document version. Updates parent document's version and updated_at."""
        now = datetime.now(timezone.utc)
        version_id = f"VER-{uuid4().hex[:8].upper()}"

        with self._lock:
            # Validate document exists
            document = self._documents.get(payload.document_id)
            if document is None:
                return None

            version = DocumentVersion(
                id=version_id,
                document_id=payload.document_id,
                version=payload.version,
                change_summary=payload.change_summary,
                changed_by=payload.changed_by,
                change_date=now,
            )
            self._versions[version_id] = version

            # Update parent document's version and updated_at
            doc_data = document.model_dump()
            doc_data["version"] = payload.version
            doc_data["updated_at"] = now
            self._documents[payload.document_id] = ClinicalDocument(**doc_data)

        logger.info("Created version %s for document %s", version_id, payload.document_id)
        return version

    # ------------------------------------------------------------------
    # Review Management
    # ------------------------------------------------------------------

    def list_reviews(
        self,
        *,
        document_id: str | None = None,
        reviewer: str | None = None,
        decision: ReviewDecision | None = None,
    ) -> list[DocumentReview]:
        """List document reviews with optional filters."""
        with self._lock:
            result = list(self._reviews.values())

        if document_id is not None:
            result = [r for r in result if r.document_id == document_id]
        if reviewer is not None:
            result = [r for r in result if r.reviewer == reviewer]
        if decision is not None:
            result = [r for r in result if r.decision == decision]

        return sorted(result, key=lambda r: r.assigned_date, reverse=True)

    def get_review(self, review_id: str) -> DocumentReview | None:
        """Get a single review by ID."""
        with self._lock:
            return self._reviews.get(review_id)

    def create_review(self, payload: DocumentReviewCreate) -> DocumentReview | None:
        """Create a new document review."""
        now = datetime.now(timezone.utc)
        review_id = f"REV-{uuid4().hex[:8].upper()}"

        with self._lock:
            # Validate document exists
            document = self._documents.get(payload.document_id)
            if document is None:
                return None

            review = DocumentReview(
                id=review_id,
                document_id=payload.document_id,
                version_id=payload.version_id,
                reviewer=payload.reviewer,
                reviewer_role=payload.reviewer_role,
                assigned_date=now,
                due_date=payload.due_date,
            )
            self._reviews[review_id] = review

        logger.info("Created review %s for document %s", review_id, payload.document_id)
        return review

    def update_review(
        self, review_id: str, payload: DocumentReviewUpdate
    ) -> DocumentReview | None:
        """Update a document review. Sets completed_date when decision is provided."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._reviews.get(review_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set completed_date when decision is provided
            if "decision" in updates and updates["decision"] is not None:
                if existing.completed_date is None:
                    updates["completed_date"] = now

            data.update(updates)
            updated = DocumentReview(**data)
            self._reviews[review_id] = updated
        return updated

    def delete_review(self, review_id: str) -> bool:
        """Delete a review. Returns True if deleted."""
        with self._lock:
            if review_id in self._reviews:
                del self._reviews[review_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Filing Management
    # ------------------------------------------------------------------

    def list_filings(
        self,
        *,
        document_id: str | None = None,
    ) -> list[DocumentFiling]:
        """List document filings with optional filter."""
        with self._lock:
            result = list(self._filings.values())

        if document_id is not None:
            result = [f for f in result if f.document_id == document_id]

        return sorted(result, key=lambda f: f.filed_date, reverse=True)

    def get_filing(self, filing_id: str) -> DocumentFiling | None:
        """Get a single filing by ID."""
        with self._lock:
            return self._filings.get(filing_id)

    def create_filing(self, payload: DocumentFilingCreate) -> DocumentFiling | None:
        """Create a new document filing."""
        now = datetime.now(timezone.utc)
        filing_id = f"FIL-{uuid4().hex[:8].upper()}"

        with self._lock:
            # Validate document exists
            document = self._documents.get(payload.document_id)
            if document is None:
                return None

            filing = DocumentFiling(
                id=filing_id,
                document_id=payload.document_id,
                filing_location=payload.filing_location,
                filed_by=payload.filed_by,
                filed_date=now,
                regulatory_authority=payload.regulatory_authority,
                filing_reference=payload.filing_reference,
            )
            self._filings[filing_id] = filing

        logger.info("Created filing %s for document %s", filing_id, payload.document_id)
        return filing

    def delete_filing(self, filing_id: str) -> bool:
        """Delete a filing. Returns True if deleted."""
        with self._lock:
            if filing_id in self._filings:
                del self._filings[filing_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> DocumentManagementMetrics:
        """Compute aggregated document management metrics."""
        now = datetime.now(timezone.utc)

        with self._lock:
            documents = list(self._documents.values())
            reviews = list(self._reviews.values())
            versions = list(self._versions.values())
            filings = list(self._filings.values())

        if trial_id is not None:
            documents = [d for d in documents if d.trial_id == trial_id]
            doc_ids = {d.id for d in documents}
            reviews = [r for r in reviews if r.document_id in doc_ids]
            versions = [v for v in versions if v.document_id in doc_ids]
            filings = [f for f in filings if f.document_id in doc_ids]

        # Documents by type
        documents_by_type: dict[str, int] = {}
        for d in documents:
            key = d.document_type.value
            documents_by_type[key] = documents_by_type.get(key, 0) + 1

        # Documents by status
        documents_by_status: dict[str, int] = {}
        for d in documents:
            key = d.status.value
            documents_by_status[key] = documents_by_status.get(key, 0) + 1

        # Review metrics
        pending_reviews = sum(1 for r in reviews if r.completed_date is None)
        overdue_reviews = sum(
            1 for r in reviews
            if r.completed_date is None and r.due_date < now
        )

        # Reviews by decision
        reviews_by_decision: dict[str, int] = {}
        for r in reviews:
            if r.decision is not None:
                key = r.decision.value
                reviews_by_decision[key] = reviews_by_decision.get(key, 0) + 1

        # Confirmed filings
        confirmed_filings = sum(1 for f in filings if f.confirmed)

        # Average review days (for completed reviews)
        completed_reviews = [r for r in reviews if r.completed_date is not None]
        if completed_reviews:
            total_days = sum(
                (r.completed_date - r.assigned_date).total_seconds() / 86400.0
                for r in completed_reviews
            )
            avg_review_days = round(total_days / len(completed_reviews), 1)
        else:
            avg_review_days = 0.0

        return DocumentManagementMetrics(
            total_documents=len(documents),
            documents_by_type=documents_by_type,
            documents_by_status=documents_by_status,
            total_versions=len(versions),
            total_reviews=len(reviews),
            pending_reviews=pending_reviews,
            overdue_reviews=overdue_reviews,
            reviews_by_decision=reviews_by_decision,
            total_filings=len(filings),
            confirmed_filings=confirmed_filings,
            avg_review_days=avg_review_days,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: DocumentManagementService | None = None
_instance_lock = threading.Lock()


def get_document_management_service() -> DocumentManagementService:
    """Return the singleton DocumentManagementService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = DocumentManagementService()
    return _instance


def reset_document_management_service() -> DocumentManagementService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = DocumentManagementService()
    return _instance
