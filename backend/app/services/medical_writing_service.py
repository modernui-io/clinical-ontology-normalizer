"""Medical Writing & CSR Generation Service (CLINICAL-11).

Manages medical writing operations including document lifecycle management,
ICH E3 section tracking, review comment workflow, TLF shell programming/
validation tracking, overdue detection, and writing metrics.

Usage:
    from app.services.medical_writing_service import (
        get_medical_writing_service,
    )

    svc = get_medical_writing_service()
    docs = svc.list_documents()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.medical_writing import (
    DocumentCreate,
    DocumentListResponse,
    DocumentSection,
    DocumentStatus,
    DocumentType,
    DocumentUpdate,
    ICHSection,
    MedicalDocument,
    ProgrammingStatus,
    ResolutionStatus,
    ReviewComment,
    ReviewCommentCreate,
    ReviewCommentUpdate,
    ReviewType,
    SectionCreate,
    SectionStatus,
    SectionUpdate,
    TLFShell,
    TLFShellCreate,
    TLFShellUpdate,
    TLFType,
    WritingMetrics,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class MedicalWritingService:
    """In-memory Medical Writing engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._documents: dict[str, MedicalDocument] = {}
        self._sections: dict[str, DocumentSection] = {}
        self._comments: dict[str, ReviewComment] = {}
        self._tlf_shells: dict[str, TLFShell] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic medical writing data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 8 Medical Documents across 3 trials ---
        docs_data = [
            {
                "id": "DOC-001",
                "trial_id": EYLEA_TRIAL,
                "document_type": DocumentType.CSR,
                "title": "Clinical Study Report: EYLEA Phase III - Wet AMD",
                "version": "2.0",
                "status": DocumentStatus.MEDICAL_REVIEW,
                "author": "Dr. Sarah Chen",
                "reviewer": "Dr. Michael Torres",
                "created_date": now - timedelta(days=180),
                "last_modified": now - timedelta(days=5),
                "target_date": now + timedelta(days=30),
                "word_count": 45200,
                "sections": [],
                "comments_count": 8,
            },
            {
                "id": "DOC-002",
                "trial_id": DUPIXENT_TRIAL,
                "document_type": DocumentType.CSR,
                "title": "Clinical Study Report: DUPIXENT Phase III - Atopic Dermatitis",
                "version": "1.0",
                "status": DocumentStatus.DRAFT,
                "author": "Dr. Emily Watson",
                "reviewer": None,
                "created_date": now - timedelta(days=90),
                "last_modified": now - timedelta(days=2),
                "target_date": now + timedelta(days=60),
                "word_count": 28500,
                "sections": [],
                "comments_count": 0,
            },
            {
                "id": "DOC-003",
                "trial_id": LIBTAYO_TRIAL,
                "document_type": DocumentType.CSR,
                "title": "Clinical Study Report: LIBTAYO Phase III - NSCLC",
                "version": "1.0",
                "status": DocumentStatus.INTERNAL_REVIEW,
                "author": "Dr. James Park",
                "reviewer": "Dr. Lisa Anderson",
                "created_date": now - timedelta(days=120),
                "last_modified": now - timedelta(days=7),
                "target_date": now + timedelta(days=45),
                "word_count": 38900,
                "sections": [],
                "comments_count": 5,
            },
            {
                "id": "DOC-004",
                "trial_id": EYLEA_TRIAL,
                "document_type": DocumentType.SAP,
                "title": "Statistical Analysis Plan: EYLEA Phase III - Wet AMD",
                "version": "3.0",
                "status": DocumentStatus.APPROVED,
                "author": "Dr. Robert Kim",
                "reviewer": "Dr. Sarah Chen",
                "created_date": now - timedelta(days=240),
                "last_modified": now - timedelta(days=60),
                "target_date": now - timedelta(days=90),
                "word_count": 18500,
                "sections": [],
                "comments_count": 12,
            },
            {
                "id": "DOC-005",
                "trial_id": DUPIXENT_TRIAL,
                "document_type": DocumentType.SAP,
                "title": "Statistical Analysis Plan: DUPIXENT Phase III - Atopic Dermatitis",
                "version": "2.0",
                "status": DocumentStatus.FINAL,
                "author": "Dr. Anna Petrov",
                "reviewer": "Dr. Robert Kim",
                "created_date": now - timedelta(days=200),
                "last_modified": now - timedelta(days=30),
                "target_date": now - timedelta(days=45),
                "word_count": 16200,
                "sections": [],
                "comments_count": 7,
            },
            {
                "id": "DOC-006",
                "trial_id": LIBTAYO_TRIAL,
                "document_type": DocumentType.SAP,
                "title": "Statistical Analysis Plan: LIBTAYO Phase III - NSCLC",
                "version": "1.0",
                "status": DocumentStatus.QC,
                "author": "Dr. Anna Petrov",
                "reviewer": "Dr. James Park",
                "created_date": now - timedelta(days=150),
                "last_modified": now - timedelta(days=10),
                "target_date": now + timedelta(days=14),
                "word_count": 15800,
                "sections": [],
                "comments_count": 3,
            },
            {
                "id": "DOC-007",
                "trial_id": EYLEA_TRIAL,
                "document_type": DocumentType.IB,
                "title": "Investigator's Brochure: Aflibercept (EYLEA) - Edition 15",
                "version": "15.0",
                "status": DocumentStatus.APPROVED,
                "author": "Dr. Michael Torres",
                "reviewer": "Dr. Sarah Chen",
                "created_date": now - timedelta(days=365),
                "last_modified": now - timedelta(days=45),
                "target_date": now - timedelta(days=60),
                "word_count": 62000,
                "sections": [],
                "comments_count": 15,
            },
            {
                "id": "DOC-008",
                "trial_id": DUPIXENT_TRIAL,
                "document_type": DocumentType.PROTOCOL,
                "title": "Protocol Amendment 3: DUPIXENT Phase III - Atopic Dermatitis",
                "version": "3.0",
                "status": DocumentStatus.SUBMITTED,
                "author": "Dr. Emily Watson",
                "reviewer": "Dr. Lisa Anderson",
                "created_date": now - timedelta(days=300),
                "last_modified": now - timedelta(days=90),
                "target_date": now - timedelta(days=120),
                "word_count": 42000,
                "sections": [],
                "comments_count": 20,
            },
        ]

        for d in docs_data:
            self._documents[d["id"]] = MedicalDocument(**d)

        # --- 30 Sections following ICH E3 structure for CSRs ---
        sections_data = [
            # EYLEA CSR (DOC-001) sections
            {"id": "SEC-001", "document_id": "DOC-001", "section_number": "1", "title": "Title Page", "content_summary": "Study title, protocol number, sponsor information", "word_count": 350, "status": SectionStatus.FINAL, "assigned_to": "Dr. Sarah Chen", "ich_section": ICHSection.S1_TITLE},
            {"id": "SEC-002", "document_id": "DOC-001", "section_number": "2", "title": "Synopsis", "content_summary": "Summary of study design, efficacy and safety results", "word_count": 2500, "status": SectionStatus.FINAL, "assigned_to": "Dr. Sarah Chen", "ich_section": ICHSection.S2_SYNOPSIS},
            {"id": "SEC-003", "document_id": "DOC-001", "section_number": "7", "title": "Introduction", "content_summary": "Background on wet AMD and aflibercept mechanism of action", "word_count": 1800, "status": SectionStatus.FINAL, "assigned_to": "Dr. Sarah Chen", "ich_section": ICHSection.S7_INTRODUCTION},
            {"id": "SEC-004", "document_id": "DOC-001", "section_number": "8", "title": "Study Objectives", "content_summary": "Primary and secondary endpoints, estimands", "word_count": 1200, "status": SectionStatus.FINAL, "assigned_to": "Dr. Sarah Chen", "ich_section": ICHSection.S8_STUDY_OBJECTIVES},
            {"id": "SEC-005", "document_id": "DOC-001", "section_number": "9", "title": "Investigational Plan", "content_summary": "Study design, dosing regimen, randomization, blinding", "word_count": 5500, "status": SectionStatus.REVIEW, "assigned_to": "Dr. Michael Torres", "ich_section": ICHSection.S9_INVESTIGATIONAL_PLAN},
            {"id": "SEC-006", "document_id": "DOC-001", "section_number": "10", "title": "Study Patients", "content_summary": "Disposition, demographics, baseline characteristics", "word_count": 4200, "status": SectionStatus.REVIEW, "assigned_to": "Dr. Michael Torres", "ich_section": ICHSection.S10_STUDY_PATIENTS},
            {"id": "SEC-007", "document_id": "DOC-001", "section_number": "11", "title": "Efficacy Evaluation", "content_summary": "Primary efficacy analysis, BCVA change from baseline", "word_count": 8500, "status": SectionStatus.DRAFTING, "assigned_to": "Dr. Sarah Chen", "ich_section": ICHSection.S11_EFFICACY_EVALUATION},
            {"id": "SEC-008", "document_id": "DOC-001", "section_number": "12", "title": "Safety Evaluation", "content_summary": "AE summary, SAEs, deaths, lab abnormalities", "word_count": 7200, "status": SectionStatus.DRAFTING, "assigned_to": "Dr. Sarah Chen", "ich_section": ICHSection.S12_SAFETY_EVALUATION},
            {"id": "SEC-009", "document_id": "DOC-001", "section_number": "13", "title": "Discussion and Conclusions", "content_summary": "Benefit-risk assessment, comparison to prior studies", "word_count": 3200, "status": SectionStatus.NOT_STARTED, "assigned_to": "Dr. Sarah Chen", "ich_section": ICHSection.S13_DISCUSSION},
            {"id": "SEC-010", "document_id": "DOC-001", "section_number": "14", "title": "Tables, Figures, and Graphs", "content_summary": "Reference to TLF package", "word_count": 500, "status": SectionStatus.DRAFTING, "assigned_to": "Dr. Robert Kim", "ich_section": ICHSection.S14_TABLES_FIGURES_GRAPHS},
            # DUPIXENT CSR (DOC-002) sections
            {"id": "SEC-011", "document_id": "DOC-002", "section_number": "1", "title": "Title Page", "content_summary": "Study title, protocol number, sponsor information", "word_count": 320, "status": SectionStatus.FINAL, "assigned_to": "Dr. Emily Watson", "ich_section": ICHSection.S1_TITLE},
            {"id": "SEC-012", "document_id": "DOC-002", "section_number": "2", "title": "Synopsis", "content_summary": "Study synopsis for atopic dermatitis trial", "word_count": 2200, "status": SectionStatus.DRAFTING, "assigned_to": "Dr. Emily Watson", "ich_section": ICHSection.S2_SYNOPSIS},
            {"id": "SEC-013", "document_id": "DOC-002", "section_number": "7", "title": "Introduction", "content_summary": "Background on atopic dermatitis and dupilumab", "word_count": 1600, "status": SectionStatus.DRAFTING, "assigned_to": "Dr. Emily Watson", "ich_section": ICHSection.S7_INTRODUCTION},
            {"id": "SEC-014", "document_id": "DOC-002", "section_number": "9", "title": "Investigational Plan", "content_summary": "Study design, dose selection, treatment arms", "word_count": 4800, "status": SectionStatus.NOT_STARTED, "assigned_to": "Dr. Emily Watson", "ich_section": ICHSection.S9_INVESTIGATIONAL_PLAN},
            {"id": "SEC-015", "document_id": "DOC-002", "section_number": "10", "title": "Study Patients", "content_summary": "Patient disposition and demographics", "word_count": 3500, "status": SectionStatus.NOT_STARTED, "assigned_to": "Dr. Emily Watson", "ich_section": ICHSection.S10_STUDY_PATIENTS},
            {"id": "SEC-016", "document_id": "DOC-002", "section_number": "11", "title": "Efficacy Evaluation", "content_summary": "EASI score, IGA response, pruritus NRS", "word_count": 6800, "status": SectionStatus.NOT_STARTED, "assigned_to": "Dr. Anna Petrov", "ich_section": ICHSection.S11_EFFICACY_EVALUATION},
            {"id": "SEC-017", "document_id": "DOC-002", "section_number": "12", "title": "Safety Evaluation", "content_summary": "Safety analysis for dupilumab", "word_count": 5200, "status": SectionStatus.NOT_STARTED, "assigned_to": "Dr. Emily Watson", "ich_section": ICHSection.S12_SAFETY_EVALUATION},
            {"id": "SEC-018", "document_id": "DOC-002", "section_number": "13", "title": "Discussion and Conclusions", "content_summary": "Benefit-risk discussion", "word_count": 0, "status": SectionStatus.NOT_STARTED, "assigned_to": "Dr. Emily Watson", "ich_section": ICHSection.S13_DISCUSSION},
            {"id": "SEC-019", "document_id": "DOC-002", "section_number": "15", "title": "References", "content_summary": "Literature references", "word_count": 800, "status": SectionStatus.NOT_STARTED, "assigned_to": "Dr. Emily Watson", "ich_section": ICHSection.S15_REFERENCES},
            {"id": "SEC-020", "document_id": "DOC-002", "section_number": "16", "title": "Appendices", "content_summary": "Protocol, SAP, sample CRFs", "word_count": 0, "status": SectionStatus.NOT_STARTED, "assigned_to": "Dr. Emily Watson", "ich_section": ICHSection.S16_APPENDICES},
            # LIBTAYO CSR (DOC-003) sections
            {"id": "SEC-021", "document_id": "DOC-003", "section_number": "1", "title": "Title Page", "content_summary": "Study title and identification", "word_count": 340, "status": SectionStatus.FINAL, "assigned_to": "Dr. James Park", "ich_section": ICHSection.S1_TITLE},
            {"id": "SEC-022", "document_id": "DOC-003", "section_number": "2", "title": "Synopsis", "content_summary": "Synopsis for NSCLC cemiplimab trial", "word_count": 2800, "status": SectionStatus.FINAL, "assigned_to": "Dr. James Park", "ich_section": ICHSection.S2_SYNOPSIS},
            {"id": "SEC-023", "document_id": "DOC-003", "section_number": "9", "title": "Investigational Plan", "content_summary": "Treatment design, PD-1 inhibitor protocol", "word_count": 5200, "status": SectionStatus.REVIEW, "assigned_to": "Dr. Lisa Anderson", "ich_section": ICHSection.S9_INVESTIGATIONAL_PLAN},
            {"id": "SEC-024", "document_id": "DOC-003", "section_number": "10", "title": "Study Patients", "content_summary": "NSCLC patient population and disposition", "word_count": 4000, "status": SectionStatus.REVIEW, "assigned_to": "Dr. Lisa Anderson", "ich_section": ICHSection.S10_STUDY_PATIENTS},
            {"id": "SEC-025", "document_id": "DOC-003", "section_number": "11", "title": "Efficacy Evaluation", "content_summary": "OS, PFS, ORR analysis for cemiplimab", "word_count": 9200, "status": SectionStatus.DRAFTING, "assigned_to": "Dr. James Park", "ich_section": ICHSection.S11_EFFICACY_EVALUATION},
            {"id": "SEC-026", "document_id": "DOC-003", "section_number": "12", "title": "Safety Evaluation", "content_summary": "Immune-related AEs, infusion reactions, deaths", "word_count": 7800, "status": SectionStatus.DRAFTING, "assigned_to": "Dr. James Park", "ich_section": ICHSection.S12_SAFETY_EVALUATION},
            {"id": "SEC-027", "document_id": "DOC-003", "section_number": "13", "title": "Discussion and Conclusions", "content_summary": "Benefit-risk in NSCLC context", "word_count": 2800, "status": SectionStatus.NOT_STARTED, "assigned_to": "Dr. James Park", "ich_section": ICHSection.S13_DISCUSSION},
            {"id": "SEC-028", "document_id": "DOC-003", "section_number": "5", "title": "Ethics", "content_summary": "IRB approvals, informed consent, GCP compliance", "word_count": 1200, "status": SectionStatus.FINAL, "assigned_to": "Dr. Lisa Anderson", "ich_section": ICHSection.S5_ETHICS},
            {"id": "SEC-029", "document_id": "DOC-003", "section_number": "6", "title": "Investigators and Study Sites", "content_summary": "List of investigators and participating sites", "word_count": 900, "status": SectionStatus.FINAL, "assigned_to": "Dr. Lisa Anderson", "ich_section": ICHSection.S6_INVESTIGATORS},
            {"id": "SEC-030", "document_id": "DOC-003", "section_number": "14", "title": "Tables, Figures, and Graphs", "content_summary": "Reference to TLF appendix", "word_count": 450, "status": SectionStatus.DRAFTING, "assigned_to": "Dr. Anna Petrov", "ich_section": ICHSection.S14_TABLES_FIGURES_GRAPHS},
        ]

        for s in sections_data:
            self._sections[s["id"]] = DocumentSection(**s)

        # Update document section lists
        for doc_id in ["DOC-001", "DOC-002", "DOC-003"]:
            doc = self._documents[doc_id]
            doc_sections = [s["id"] for s in sections_data if s["document_id"] == doc_id]
            updated = doc.model_dump()
            updated["sections"] = doc_sections
            self._documents[doc_id] = MedicalDocument(**updated)

        # --- 20 Review Comments ---
        comments_data = [
            {"id": "CMT-001", "document_id": "DOC-001", "section_id": "SEC-005", "reviewer": "Dr. Michael Torres", "review_type": ReviewType.MEDICAL, "comment_text": "Please clarify the dose modification criteria in Section 9.3", "resolution": ResolutionStatus.ACCEPTED, "created_date": now - timedelta(days=20), "resolved_date": now - timedelta(days=15)},
            {"id": "CMT-002", "document_id": "DOC-001", "section_id": "SEC-005", "reviewer": "Dr. Robert Kim", "review_type": ReviewType.STATISTICAL, "comment_text": "Randomization stratification factors should match SAP Table 2", "resolution": ResolutionStatus.ACCEPTED, "created_date": now - timedelta(days=18), "resolved_date": now - timedelta(days=12)},
            {"id": "CMT-003", "document_id": "DOC-001", "section_id": "SEC-006", "reviewer": "Dr. Michael Torres", "review_type": ReviewType.MEDICAL, "comment_text": "Demographics table needs to include prior anti-VEGF therapy", "resolution": ResolutionStatus.OPEN, "created_date": now - timedelta(days=10), "resolved_date": None},
            {"id": "CMT-004", "document_id": "DOC-001", "section_id": "SEC-007", "reviewer": "Dr. Robert Kim", "review_type": ReviewType.STATISTICAL, "comment_text": "Primary analysis should include sensitivity analysis per SAP amendment", "resolution": ResolutionStatus.OPEN, "created_date": now - timedelta(days=8), "resolved_date": None},
            {"id": "CMT-005", "document_id": "DOC-001", "section_id": "SEC-007", "reviewer": "Dr. Lisa Anderson", "review_type": ReviewType.REGULATORY, "comment_text": "Ensure estimand framework aligns with ICH E9(R1) guidance", "resolution": ResolutionStatus.OPEN, "created_date": now - timedelta(days=7), "resolved_date": None},
            {"id": "CMT-006", "document_id": "DOC-001", "section_id": "SEC-008", "reviewer": "Dr. Michael Torres", "review_type": ReviewType.MEDICAL, "comment_text": "Add a narrative for the 2 deaths in the treatment arm", "resolution": ResolutionStatus.OPEN, "created_date": now - timedelta(days=6), "resolved_date": None},
            {"id": "CMT-007", "document_id": "DOC-001", "section_id": None, "reviewer": "QA Team", "review_type": ReviewType.QUALITY, "comment_text": "Cross-references to Table 14.1.1 are broken in current draft", "resolution": ResolutionStatus.OPEN, "created_date": now - timedelta(days=5), "resolved_date": None},
            {"id": "CMT-008", "document_id": "DOC-001", "section_id": None, "reviewer": "Dr. Sarah Chen", "review_type": ReviewType.SCIENTIFIC, "comment_text": "Need updated p-values after database lock correction", "resolution": ResolutionStatus.OPEN, "created_date": now - timedelta(days=3), "resolved_date": None},
            {"id": "CMT-009", "document_id": "DOC-003", "section_id": "SEC-023", "reviewer": "Dr. Lisa Anderson", "review_type": ReviewType.REGULATORY, "comment_text": "Protocol amendment history needs to be complete per ICH E3", "resolution": ResolutionStatus.ACCEPTED, "created_date": now - timedelta(days=25), "resolved_date": now - timedelta(days=20)},
            {"id": "CMT-010", "document_id": "DOC-003", "section_id": "SEC-025", "reviewer": "Dr. Anna Petrov", "review_type": ReviewType.STATISTICAL, "comment_text": "Kaplan-Meier curves need confidence intervals per SAP", "resolution": ResolutionStatus.OPEN, "created_date": now - timedelta(days=12), "resolved_date": None},
            {"id": "CMT-011", "document_id": "DOC-003", "section_id": "SEC-026", "reviewer": "Dr. Michael Torres", "review_type": ReviewType.MEDICAL, "comment_text": "Immune-related AE grading should follow CTCAE v5.0", "resolution": ResolutionStatus.OPEN, "created_date": now - timedelta(days=10), "resolved_date": None},
            {"id": "CMT-012", "document_id": "DOC-003", "section_id": "SEC-024", "reviewer": "Dr. Lisa Anderson", "review_type": ReviewType.REGULATORY, "comment_text": "Patient disposition flow diagram needs CONSORT compliance", "resolution": ResolutionStatus.ACCEPTED, "created_date": now - timedelta(days=22), "resolved_date": now - timedelta(days=18)},
            {"id": "CMT-013", "document_id": "DOC-003", "section_id": None, "reviewer": "QA Team", "review_type": ReviewType.QUALITY, "comment_text": "Table numbering inconsistent between body text and appendix", "resolution": ResolutionStatus.OPEN, "created_date": now - timedelta(days=8), "resolved_date": None},
            {"id": "CMT-014", "document_id": "DOC-004", "section_id": None, "reviewer": "Dr. Sarah Chen", "review_type": ReviewType.SCIENTIFIC, "comment_text": "Primary endpoint definition matches protocol amendment 2", "resolution": ResolutionStatus.ACCEPTED, "created_date": now - timedelta(days=90), "resolved_date": now - timedelta(days=85)},
            {"id": "CMT-015", "document_id": "DOC-004", "section_id": None, "reviewer": "Dr. Lisa Anderson", "review_type": ReviewType.REGULATORY, "comment_text": "Missing intercurrent events strategy per ICH E9(R1)", "resolution": ResolutionStatus.ACCEPTED, "created_date": now - timedelta(days=88), "resolved_date": now - timedelta(days=80)},
            {"id": "CMT-016", "document_id": "DOC-005", "section_id": None, "reviewer": "Dr. Robert Kim", "review_type": ReviewType.STATISTICAL, "comment_text": "Sample size re-estimation procedure needs clarification", "resolution": ResolutionStatus.ACCEPTED, "created_date": now - timedelta(days=60), "resolved_date": now - timedelta(days=55)},
            {"id": "CMT-017", "document_id": "DOC-006", "section_id": None, "reviewer": "Dr. James Park", "review_type": ReviewType.SCIENTIFIC, "comment_text": "Subgroup analysis populations need to align with protocol", "resolution": ResolutionStatus.OPEN, "created_date": now - timedelta(days=14), "resolved_date": None},
            {"id": "CMT-018", "document_id": "DOC-006", "section_id": None, "reviewer": "QA Team", "review_type": ReviewType.QUALITY, "comment_text": "Version control header incorrect on pages 12-15", "resolution": ResolutionStatus.ACCEPTED, "created_date": now - timedelta(days=12), "resolved_date": now - timedelta(days=11)},
            {"id": "CMT-019", "document_id": "DOC-007", "section_id": None, "reviewer": "Dr. Sarah Chen", "review_type": ReviewType.MEDICAL, "comment_text": "Updated preclinical toxicology data from 2025 study needed", "resolution": ResolutionStatus.ACCEPTED, "created_date": now - timedelta(days=50), "resolved_date": now - timedelta(days=46)},
            {"id": "CMT-020", "document_id": "DOC-008", "section_id": None, "reviewer": "Dr. Lisa Anderson", "review_type": ReviewType.REGULATORY, "comment_text": "Amendment justification needs stronger rationale for dose change", "resolution": ResolutionStatus.ACCEPTED, "created_date": now - timedelta(days=100), "resolved_date": now - timedelta(days=95)},
        ]

        for c in comments_data:
            self._comments[c["id"]] = ReviewComment(**c)

        # Update document comment counts
        for doc_id in self._documents:
            count = sum(1 for c in comments_data if c["document_id"] == doc_id)
            if count > 0:
                doc = self._documents[doc_id]
                updated = doc.model_dump()
                updated["comments_count"] = count
                self._documents[doc_id] = MedicalDocument(**updated)

        # --- 25 TLF Shells ---
        tlf_data = [
            # Demographics tables (14.1.x)
            {"id": "TLF-001", "trial_id": EYLEA_TRIAL, "tlf_type": TLFType.TABLE, "number": "14.1.1", "title": "Summary of Demographics and Baseline Characteristics (ITT)", "population": "ITT", "dataset": "ADSL", "programming_status": ProgrammingStatus.VALIDATED, "programmer": "Wei Zhang", "validator": "Maria Garcia"},
            {"id": "TLF-002", "trial_id": EYLEA_TRIAL, "tlf_type": TLFType.TABLE, "number": "14.1.2", "title": "Summary of Demographics and Baseline Characteristics (Safety)", "population": "Safety", "dataset": "ADSL", "programming_status": ProgrammingStatus.VALIDATED, "programmer": "Wei Zhang", "validator": "Maria Garcia"},
            {"id": "TLF-003", "trial_id": EYLEA_TRIAL, "tlf_type": TLFType.TABLE, "number": "14.1.3", "title": "Patient Disposition", "population": "Screened", "dataset": "ADSL", "programming_status": ProgrammingStatus.FINAL, "programmer": "Wei Zhang", "validator": "Maria Garcia"},
            {"id": "TLF-004", "trial_id": DUPIXENT_TRIAL, "tlf_type": TLFType.TABLE, "number": "14.1.1", "title": "Summary of Demographics (ITT Population)", "population": "ITT", "dataset": "ADSL", "programming_status": ProgrammingStatus.IN_PROGRESS, "programmer": "David Lee", "validator": None},
            {"id": "TLF-005", "trial_id": DUPIXENT_TRIAL, "tlf_type": TLFType.TABLE, "number": "14.1.2", "title": "Baseline Disease Characteristics", "population": "ITT", "dataset": "ADSL", "programming_status": ProgrammingStatus.NOT_STARTED, "programmer": "David Lee", "validator": None},
            {"id": "TLF-006", "trial_id": LIBTAYO_TRIAL, "tlf_type": TLFType.TABLE, "number": "14.1.1", "title": "Demographics and Baseline Characteristics", "population": "ITT", "dataset": "ADSL", "programming_status": ProgrammingStatus.VALIDATED, "programmer": "Kenji Tanaka", "validator": "Wei Zhang"},
            # Efficacy tables (14.2.x)
            {"id": "TLF-007", "trial_id": EYLEA_TRIAL, "tlf_type": TLFType.TABLE, "number": "14.2.1", "title": "Primary Efficacy Analysis: Change in BCVA from Baseline", "population": "ITT", "dataset": "ADEFF", "programming_status": ProgrammingStatus.VALIDATED, "programmer": "Maria Garcia", "validator": "Wei Zhang"},
            {"id": "TLF-008", "trial_id": EYLEA_TRIAL, "tlf_type": TLFType.TABLE, "number": "14.2.2", "title": "Secondary Efficacy: Proportion Gaining >= 15 Letters", "population": "ITT", "dataset": "ADEFF", "programming_status": ProgrammingStatus.IN_PROGRESS, "programmer": "Maria Garcia", "validator": None},
            {"id": "TLF-009", "trial_id": DUPIXENT_TRIAL, "tlf_type": TLFType.TABLE, "number": "14.2.1", "title": "Primary Efficacy: EASI-75 Response at Week 16", "population": "ITT", "dataset": "ADEFF", "programming_status": ProgrammingStatus.NOT_STARTED, "programmer": "David Lee", "validator": None},
            {"id": "TLF-010", "trial_id": LIBTAYO_TRIAL, "tlf_type": TLFType.TABLE, "number": "14.2.1", "title": "Primary Efficacy: Overall Survival", "population": "ITT", "dataset": "ADTTE", "programming_status": ProgrammingStatus.FINAL, "programmer": "Kenji Tanaka", "validator": "Maria Garcia"},
            {"id": "TLF-011", "trial_id": LIBTAYO_TRIAL, "tlf_type": TLFType.TABLE, "number": "14.2.2", "title": "Secondary Efficacy: Progression-Free Survival", "population": "ITT", "dataset": "ADTTE", "programming_status": ProgrammingStatus.VALIDATED, "programmer": "Kenji Tanaka", "validator": "Maria Garcia"},
            # Safety tables (14.3.x)
            {"id": "TLF-012", "trial_id": EYLEA_TRIAL, "tlf_type": TLFType.TABLE, "number": "14.3.1", "title": "Overview of Adverse Events", "population": "Safety", "dataset": "ADAE", "programming_status": ProgrammingStatus.VALIDATED, "programmer": "Wei Zhang", "validator": "David Lee"},
            {"id": "TLF-013", "trial_id": EYLEA_TRIAL, "tlf_type": TLFType.TABLE, "number": "14.3.2", "title": "Adverse Events by System Organ Class and Preferred Term", "population": "Safety", "dataset": "ADAE", "programming_status": ProgrammingStatus.IN_PROGRESS, "programmer": "Wei Zhang", "validator": None},
            {"id": "TLF-014", "trial_id": DUPIXENT_TRIAL, "tlf_type": TLFType.TABLE, "number": "14.3.1", "title": "Summary of Treatment-Emergent Adverse Events", "population": "Safety", "dataset": "ADAE", "programming_status": ProgrammingStatus.NOT_STARTED, "programmer": "David Lee", "validator": None},
            {"id": "TLF-015", "trial_id": LIBTAYO_TRIAL, "tlf_type": TLFType.TABLE, "number": "14.3.1", "title": "Overview of Safety: Adverse Events", "population": "Safety", "dataset": "ADAE", "programming_status": ProgrammingStatus.VALIDATED, "programmer": "Kenji Tanaka", "validator": "Wei Zhang"},
            {"id": "TLF-016", "trial_id": LIBTAYO_TRIAL, "tlf_type": TLFType.TABLE, "number": "14.3.2", "title": "Immune-Related Adverse Events", "population": "Safety", "dataset": "ADAE", "programming_status": ProgrammingStatus.IN_PROGRESS, "programmer": "Kenji Tanaka", "validator": None},
            # Listings (16.2.x)
            {"id": "TLF-017", "trial_id": EYLEA_TRIAL, "tlf_type": TLFType.LISTING, "number": "16.2.1", "title": "Listing of Subjects Who Died", "population": "Safety", "dataset": "ADAE", "programming_status": ProgrammingStatus.FINAL, "programmer": "Wei Zhang", "validator": "Maria Garcia"},
            {"id": "TLF-018", "trial_id": EYLEA_TRIAL, "tlf_type": TLFType.LISTING, "number": "16.2.2", "title": "Listing of Subjects with SAEs", "population": "Safety", "dataset": "ADAE", "programming_status": ProgrammingStatus.VALIDATED, "programmer": "Wei Zhang", "validator": "Maria Garcia"},
            {"id": "TLF-019", "trial_id": LIBTAYO_TRIAL, "tlf_type": TLFType.LISTING, "number": "16.2.1", "title": "Listing of Deaths", "population": "Safety", "dataset": "ADAE", "programming_status": ProgrammingStatus.FINAL, "programmer": "Kenji Tanaka", "validator": "David Lee"},
            {"id": "TLF-020", "trial_id": DUPIXENT_TRIAL, "tlf_type": TLFType.LISTING, "number": "16.2.1", "title": "Individual Patient SAE Listings", "population": "Safety", "dataset": "ADAE", "programming_status": ProgrammingStatus.NOT_STARTED, "programmer": None, "validator": None},
            # Figures (Kaplan-Meier, forest plots)
            {"id": "TLF-021", "trial_id": EYLEA_TRIAL, "tlf_type": TLFType.FIGURE, "number": "14.2.1.1", "title": "Mean Change in BCVA from Baseline Over Time", "population": "ITT", "dataset": "ADEFF", "programming_status": ProgrammingStatus.VALIDATED, "programmer": "Maria Garcia", "validator": "Wei Zhang"},
            {"id": "TLF-022", "trial_id": LIBTAYO_TRIAL, "tlf_type": TLFType.FIGURE, "number": "14.2.1.1", "title": "Kaplan-Meier Curve for Overall Survival", "population": "ITT", "dataset": "ADTTE", "programming_status": ProgrammingStatus.FINAL, "programmer": "Kenji Tanaka", "validator": "Maria Garcia"},
            {"id": "TLF-023", "trial_id": LIBTAYO_TRIAL, "tlf_type": TLFType.FIGURE, "number": "14.2.2.1", "title": "Forest Plot: OS Subgroup Analysis", "population": "ITT", "dataset": "ADTTE", "programming_status": ProgrammingStatus.VALIDATED, "programmer": "Kenji Tanaka", "validator": "Maria Garcia"},
            {"id": "TLF-024", "trial_id": LIBTAYO_TRIAL, "tlf_type": TLFType.FIGURE, "number": "14.2.3.1", "title": "Kaplan-Meier Curve for Progression-Free Survival", "population": "ITT", "dataset": "ADTTE", "programming_status": ProgrammingStatus.IN_PROGRESS, "programmer": "Kenji Tanaka", "validator": None},
            {"id": "TLF-025", "trial_id": DUPIXENT_TRIAL, "tlf_type": TLFType.FIGURE, "number": "14.2.1.1", "title": "Forest Plot: EASI-75 Response by Subgroup", "population": "ITT", "dataset": "ADEFF", "programming_status": ProgrammingStatus.NOT_STARTED, "programmer": None, "validator": None},
        ]

        for t in tlf_data:
            self._tlf_shells[t["id"]] = TLFShell(**t)

    # ------------------------------------------------------------------
    # Document Management
    # ------------------------------------------------------------------

    def list_documents(
        self,
        *,
        trial_id: str | None = None,
        document_type: DocumentType | None = None,
        status: DocumentStatus | None = None,
    ) -> list[MedicalDocument]:
        """List documents with optional filters."""
        with self._lock:
            result = list(self._documents.values())

        if trial_id is not None:
            result = [d for d in result if d.trial_id == trial_id]
        if document_type is not None:
            result = [d for d in result if d.document_type == document_type]
        if status is not None:
            result = [d for d in result if d.status == status]

        return sorted(result, key=lambda d: d.last_modified, reverse=True)

    def get_document(self, doc_id: str) -> MedicalDocument | None:
        """Get a single document by ID."""
        with self._lock:
            return self._documents.get(doc_id)

    def create_document(self, payload: DocumentCreate) -> MedicalDocument:
        """Create a new medical document."""
        now = datetime.now(timezone.utc)
        doc_id = f"DOC-{uuid4().hex[:8].upper()}"
        doc = MedicalDocument(
            id=doc_id,
            trial_id=payload.trial_id,
            document_type=payload.document_type,
            title=payload.title,
            version=payload.version,
            status=DocumentStatus.DRAFT,
            author=payload.author,
            reviewer=None,
            created_date=now,
            last_modified=now,
            target_date=payload.target_date,
            word_count=0,
            sections=[],
            comments_count=0,
        )
        with self._lock:
            self._documents[doc_id] = doc
        logger.info("Created document %s: %s", doc_id, payload.title)
        return doc

    def update_document(self, doc_id: str, payload: DocumentUpdate) -> MedicalDocument | None:
        """Update an existing document."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._documents.get(doc_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            data["last_modified"] = now
            updated = MedicalDocument(**data)
            self._documents[doc_id] = updated
        return updated

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document. Returns True if deleted, False if not found."""
        with self._lock:
            if doc_id in self._documents:
                del self._documents[doc_id]
                return True
            return False

    def advance_document_status(self, doc_id: str) -> MedicalDocument | None:
        """Advance document to next lifecycle status.

        Lifecycle: draft -> internal_review -> medical_review -> qc -> final -> approved
        """
        now = datetime.now(timezone.utc)
        status_order = [
            DocumentStatus.DRAFT,
            DocumentStatus.INTERNAL_REVIEW,
            DocumentStatus.MEDICAL_REVIEW,
            DocumentStatus.QC,
            DocumentStatus.FINAL,
            DocumentStatus.APPROVED,
        ]
        with self._lock:
            existing = self._documents.get(doc_id)
            if existing is None:
                return None

            current_idx = -1
            for i, s in enumerate(status_order):
                if s == existing.status:
                    current_idx = i
                    break

            if current_idx < 0 or current_idx >= len(status_order) - 1:
                raise ValueError(
                    f"Document '{doc_id}' cannot be advanced from status '{existing.status.value}'"
                )

            next_status = status_order[current_idx + 1]
            data = existing.model_dump()
            data["status"] = next_status
            data["last_modified"] = now
            updated = MedicalDocument(**data)
            self._documents[doc_id] = updated

        logger.info("Advanced document %s to status %s", doc_id, next_status.value)
        return updated

    def get_overdue_documents(self) -> list[MedicalDocument]:
        """Get documents past target date that are not yet approved/submitted."""
        now = datetime.now(timezone.utc)
        terminal = {DocumentStatus.APPROVED, DocumentStatus.SUBMITTED}
        with self._lock:
            result = [
                d for d in self._documents.values()
                if d.target_date < now and d.status not in terminal
            ]
        return sorted(result, key=lambda d: d.target_date)

    # ------------------------------------------------------------------
    # Section Management
    # ------------------------------------------------------------------

    def list_sections(
        self,
        *,
        document_id: str | None = None,
        status: SectionStatus | None = None,
        ich_section: ICHSection | None = None,
    ) -> list[DocumentSection]:
        """List sections with optional filters."""
        with self._lock:
            result = list(self._sections.values())

        if document_id is not None:
            result = [s for s in result if s.document_id == document_id]
        if status is not None:
            result = [s for s in result if s.status == status]
        if ich_section is not None:
            result = [s for s in result if s.ich_section == ich_section]

        return sorted(result, key=lambda s: (s.document_id, s.section_number))

    def get_section(self, section_id: str) -> DocumentSection | None:
        """Get a single section by ID."""
        with self._lock:
            return self._sections.get(section_id)

    def create_section(self, payload: SectionCreate) -> DocumentSection:
        """Create a new document section."""
        section_id = f"SEC-{uuid4().hex[:8].upper()}"
        section = DocumentSection(
            id=section_id,
            document_id=payload.document_id,
            section_number=payload.section_number,
            title=payload.title,
            content_summary=payload.content_summary,
            word_count=0,
            status=SectionStatus.NOT_STARTED,
            assigned_to=payload.assigned_to,
            ich_section=payload.ich_section,
        )
        with self._lock:
            self._sections[section_id] = section
            # Add to parent document's section list
            doc = self._documents.get(payload.document_id)
            if doc is not None:
                data = doc.model_dump()
                data["sections"] = list(data["sections"]) + [section_id]
                self._documents[payload.document_id] = MedicalDocument(**data)
        logger.info("Created section %s in document %s", section_id, payload.document_id)
        return section

    def update_section(self, section_id: str, payload: SectionUpdate) -> DocumentSection | None:
        """Update a section."""
        with self._lock:
            existing = self._sections.get(section_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DocumentSection(**data)
            self._sections[section_id] = updated
        return updated

    def delete_section(self, section_id: str) -> bool:
        """Delete a section."""
        with self._lock:
            if section_id in self._sections:
                section = self._sections[section_id]
                del self._sections[section_id]
                # Remove from parent document
                doc = self._documents.get(section.document_id)
                if doc is not None:
                    data = doc.model_dump()
                    data["sections"] = [s for s in data["sections"] if s != section_id]
                    self._documents[section.document_id] = MedicalDocument(**data)
                return True
            return False

    # ------------------------------------------------------------------
    # Review Comments
    # ------------------------------------------------------------------

    def list_comments(
        self,
        *,
        document_id: str | None = None,
        section_id: str | None = None,
        review_type: ReviewType | None = None,
        resolution: ResolutionStatus | None = None,
    ) -> list[ReviewComment]:
        """List review comments with optional filters."""
        with self._lock:
            result = list(self._comments.values())

        if document_id is not None:
            result = [c for c in result if c.document_id == document_id]
        if section_id is not None:
            result = [c for c in result if c.section_id == section_id]
        if review_type is not None:
            result = [c for c in result if c.review_type == review_type]
        if resolution is not None:
            result = [c for c in result if c.resolution == resolution]

        return sorted(result, key=lambda c: c.created_date, reverse=True)

    def get_comment(self, comment_id: str) -> ReviewComment | None:
        """Get a single comment by ID."""
        with self._lock:
            return self._comments.get(comment_id)

    def create_comment(self, payload: ReviewCommentCreate) -> ReviewComment:
        """Create a new review comment."""
        now = datetime.now(timezone.utc)
        comment_id = f"CMT-{uuid4().hex[:8].upper()}"

        # Validate document exists
        with self._lock:
            if payload.document_id not in self._documents:
                raise ValueError(f"Document '{payload.document_id}' not found")

        comment = ReviewComment(
            id=comment_id,
            document_id=payload.document_id,
            section_id=payload.section_id,
            reviewer=payload.reviewer,
            review_type=payload.review_type,
            comment_text=payload.comment_text,
            resolution=ResolutionStatus.OPEN,
            created_date=now,
            resolved_date=None,
        )
        with self._lock:
            self._comments[comment_id] = comment
            # Update document comment count
            doc = self._documents.get(payload.document_id)
            if doc is not None:
                data = doc.model_dump()
                data["comments_count"] = data["comments_count"] + 1
                self._documents[payload.document_id] = MedicalDocument(**data)
        logger.info("Created comment %s on document %s", comment_id, payload.document_id)
        return comment

    def update_comment(self, comment_id: str, payload: ReviewCommentUpdate) -> ReviewComment | None:
        """Update a review comment."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._comments.get(comment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set resolved_date when resolution changes from open
            if "resolution" in updates:
                new_res = updates["resolution"]
                if isinstance(new_res, str):
                    new_res = ResolutionStatus(new_res)
                if new_res != ResolutionStatus.OPEN and existing.resolution == ResolutionStatus.OPEN:
                    updates["resolved_date"] = now

            data.update(updates)
            updated = ReviewComment(**data)
            self._comments[comment_id] = updated
        return updated

    def delete_comment(self, comment_id: str) -> bool:
        """Delete a review comment."""
        with self._lock:
            if comment_id in self._comments:
                comment = self._comments[comment_id]
                del self._comments[comment_id]
                # Update document comment count
                doc = self._documents.get(comment.document_id)
                if doc is not None:
                    data = doc.model_dump()
                    data["comments_count"] = max(0, data["comments_count"] - 1)
                    self._documents[comment.document_id] = MedicalDocument(**data)
                return True
            return False

    # ------------------------------------------------------------------
    # TLF Shell Management
    # ------------------------------------------------------------------

    def list_tlf_shells(
        self,
        *,
        trial_id: str | None = None,
        tlf_type: TLFType | None = None,
        programming_status: ProgrammingStatus | None = None,
    ) -> list[TLFShell]:
        """List TLF shells with optional filters."""
        with self._lock:
            result = list(self._tlf_shells.values())

        if trial_id is not None:
            result = [t for t in result if t.trial_id == trial_id]
        if tlf_type is not None:
            result = [t for t in result if t.tlf_type == tlf_type]
        if programming_status is not None:
            result = [t for t in result if t.programming_status == programming_status]

        return sorted(result, key=lambda t: (t.trial_id, t.number))

    def get_tlf_shell(self, tlf_id: str) -> TLFShell | None:
        """Get a single TLF shell by ID."""
        with self._lock:
            return self._tlf_shells.get(tlf_id)

    def create_tlf_shell(self, payload: TLFShellCreate) -> TLFShell:
        """Create a new TLF shell."""
        tlf_id = f"TLF-{uuid4().hex[:8].upper()}"
        tlf = TLFShell(
            id=tlf_id,
            trial_id=payload.trial_id,
            tlf_type=payload.tlf_type,
            number=payload.number,
            title=payload.title,
            population=payload.population,
            dataset=payload.dataset,
            programming_status=ProgrammingStatus.NOT_STARTED,
            programmer=payload.programmer,
            validator=payload.validator,
        )
        with self._lock:
            self._tlf_shells[tlf_id] = tlf
        logger.info("Created TLF shell %s: %s", tlf_id, payload.title)
        return tlf

    def update_tlf_shell(self, tlf_id: str, payload: TLFShellUpdate) -> TLFShell | None:
        """Update a TLF shell."""
        with self._lock:
            existing = self._tlf_shells.get(tlf_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = TLFShell(**data)
            self._tlf_shells[tlf_id] = updated
        return updated

    def delete_tlf_shell(self, tlf_id: str) -> bool:
        """Delete a TLF shell."""
        with self._lock:
            if tlf_id in self._tlf_shells:
                del self._tlf_shells[tlf_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self) -> WritingMetrics:
        """Compute aggregated medical writing operational metrics."""
        now = datetime.now(timezone.utc)

        with self._lock:
            docs = list(self._documents.values())
            comments = list(self._comments.values())
            tlfs = list(self._tlf_shells.values())

        # Documents by status
        by_status: dict[str, int] = {}
        for doc in docs:
            key = doc.status.value
            by_status[key] = by_status.get(key, 0) + 1

        # Documents by type
        by_type: dict[str, int] = {}
        for doc in docs:
            key = doc.document_type.value
            by_type[key] = by_type.get(key, 0) + 1

        # Average review cycle (draft created_date to approved last_modified)
        terminal = {DocumentStatus.APPROVED, DocumentStatus.SUBMITTED}
        approved_docs = [d for d in docs if d.status in terminal]
        if approved_docs:
            total_days = sum(
                (d.last_modified - d.created_date).days for d in approved_docs
            )
            avg_cycle = round(total_days / len(approved_docs), 1)
        else:
            avg_cycle = 0.0

        # Overdue documents
        overdue = sum(
            1 for d in docs
            if d.target_date < now and d.status not in terminal
        )

        # TLF completion percentage
        completed_statuses = {ProgrammingStatus.VALIDATED, ProgrammingStatus.FINAL}
        if tlfs:
            completed_count = sum(1 for t in tlfs if t.programming_status in completed_statuses)
            tlf_pct = round(completed_count / len(tlfs) * 100, 1)
        else:
            tlf_pct = 0.0

        # Active reviews (open comments)
        active_reviews = sum(
            1 for c in comments if c.resolution == ResolutionStatus.OPEN
        )

        return WritingMetrics(
            total_documents=len(docs),
            documents_by_status=by_status,
            documents_by_type=by_type,
            avg_review_cycle_days=avg_cycle,
            overdue_documents=overdue,
            tlf_completion_pct=tlf_pct,
            active_reviews=active_reviews,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: MedicalWritingService | None = None
_instance_lock = threading.Lock()


def get_medical_writing_service() -> MedicalWritingService:
    """Return the singleton MedicalWritingService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = MedicalWritingService()
    return _instance


def reset_medical_writing_service() -> MedicalWritingService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = MedicalWritingService()
    return _instance
