"""Publication Planning & Management Service (PUB-PLAN).

Manages scientific publication lifecycle: publication planning, manuscript
tracking, congress abstract submissions, author management, journal
submissions, and publication operational metrics.

Usage:
    from app.services.publication_planning_service import get_publication_planning_service

    svc = get_publication_planning_service()
    plans = svc.list_plans()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.publication_planning import (
    Author,
    AuthorCreate,
    AuthorRole,
    AuthorUpdate,
    CongressSubmission,
    CongressSubmissionCreate,
    CongressSubmissionUpdate,
    CongressTier,
    JournalSubmission,
    JournalSubmissionCreate,
    JournalSubmissionUpdate,
    JournalTier,
    Manuscript,
    ManuscriptCreate,
    ManuscriptUpdate,
    PublicationMetrics,
    PublicationPlan,
    PublicationPlanCreate,
    PublicationPlanUpdate,
    PublicationStatus,
    PublicationType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class PublicationPlanningService:
    """In-memory Publication Planning & Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._plans: dict[str, PublicationPlan] = {}
        self._manuscripts: dict[str, Manuscript] = {}
        self._authors: dict[str, Author] = {}
        self._congress_submissions: dict[str, CongressSubmission] = {}
        self._journal_submissions: dict[str, JournalSubmission] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic publication planning data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Publication Plans ---
        plans_data = [
            {"id": "PP-001", "trial_id": EYLEA_TRIAL, "plan_name": "EYLEA HD Phase 3 Primary Publication Plan", "therapeutic_area": "Ophthalmology", "target_publications": 8, "completed_publications": 3, "status": "active", "publication_lead": "Dr. Sarah Chen", "medical_writer": "Jennifer Walsh", "created_at": now - timedelta(days=365)},
            {"id": "PP-002", "trial_id": EYLEA_TRIAL, "plan_name": "EYLEA DME Long-term Extension Publication Plan", "therapeutic_area": "Ophthalmology", "target_publications": 5, "completed_publications": 2, "status": "active", "publication_lead": "Dr. Michael Torres", "medical_writer": "Emily Park", "created_at": now - timedelta(days=300)},
            {"id": "PP-003", "trial_id": DUPIXENT_TRIAL, "plan_name": "Dupixent Atopic Dermatitis Pivotal Publication Plan", "therapeutic_area": "Immunology/Dermatology", "target_publications": 12, "completed_publications": 7, "status": "active", "publication_lead": "Dr. Anna Kowalski", "medical_writer": "David Lin", "created_at": now - timedelta(days=540)},
            {"id": "PP-004", "trial_id": DUPIXENT_TRIAL, "plan_name": "Dupixent Asthma Phase 3 Publication Plan", "therapeutic_area": "Immunology/Respiratory", "target_publications": 10, "completed_publications": 5, "status": "active", "publication_lead": "Dr. James Patel", "medical_writer": "Sarah Miller", "created_at": now - timedelta(days=480)},
            {"id": "PP-005", "trial_id": DUPIXENT_TRIAL, "plan_name": "Dupixent COPD Publication Plan", "therapeutic_area": "Immunology/Respiratory", "target_publications": 6, "completed_publications": 1, "status": "active", "publication_lead": "Dr. James Patel", "medical_writer": "David Lin", "created_at": now - timedelta(days=200)},
            {"id": "PP-006", "trial_id": LIBTAYO_TRIAL, "plan_name": "Libtayo NSCLC First-Line Publication Plan", "therapeutic_area": "Oncology", "target_publications": 9, "completed_publications": 4, "status": "active", "publication_lead": "Dr. Robert Kim", "medical_writer": "Lisa Chang", "created_at": now - timedelta(days=420)},
            {"id": "PP-007", "trial_id": LIBTAYO_TRIAL, "plan_name": "Libtayo CSCC Pivotal Publication Plan", "therapeutic_area": "Oncology/Dermatology", "target_publications": 7, "completed_publications": 6, "status": "active", "publication_lead": "Dr. Robert Kim", "medical_writer": "Lisa Chang", "created_at": now - timedelta(days=600)},
            {"id": "PP-008", "trial_id": LIBTAYO_TRIAL, "plan_name": "Libtayo BCC Publication Plan", "therapeutic_area": "Oncology/Dermatology", "target_publications": 5, "completed_publications": 2, "status": "active", "publication_lead": "Dr. Elena Vasquez", "medical_writer": "Mark Thompson", "created_at": now - timedelta(days=350)},
            {"id": "PP-009", "trial_id": EYLEA_TRIAL, "plan_name": "EYLEA RVO Subgroup Analysis Plan", "therapeutic_area": "Ophthalmology", "target_publications": 4, "completed_publications": 4, "status": "completed", "publication_lead": "Dr. Sarah Chen", "medical_writer": "Jennifer Walsh", "created_at": now - timedelta(days=700)},
            {"id": "PP-010", "trial_id": DUPIXENT_TRIAL, "plan_name": "Dupixent CRSwNP Publication Plan", "therapeutic_area": "Immunology/ENT", "target_publications": 6, "completed_publications": 3, "status": "active", "publication_lead": "Dr. Anna Kowalski", "medical_writer": "Sarah Miller", "created_at": now - timedelta(days=400)},
            {"id": "PP-011", "trial_id": LIBTAYO_TRIAL, "plan_name": "Libtayo Cervical Cancer Publication Plan", "therapeutic_area": "Oncology/Gynecology", "target_publications": 4, "completed_publications": 0, "status": "active", "publication_lead": "Dr. Elena Vasquez", "medical_writer": "Mark Thompson", "created_at": now - timedelta(days=120)},
            {"id": "PP-012", "trial_id": EYLEA_TRIAL, "plan_name": "EYLEA Pediatric ROP Publication Plan", "therapeutic_area": "Ophthalmology/Pediatrics", "target_publications": 3, "completed_publications": 0, "status": "active", "publication_lead": "Dr. Michael Torres", "medical_writer": "Emily Park", "created_at": now - timedelta(days=90)},
        ]

        for p in plans_data:
            self._plans[p["id"]] = PublicationPlan(**p)

        # --- 15 Manuscripts ---
        manuscripts_data = [
            {"id": "MS-001", "plan_id": "PP-001", "trial_id": EYLEA_TRIAL, "title": "Efficacy and Safety of Aflibercept 8mg in Neovascular AMD: Primary Results from the PULSAR Trial", "publication_type": PublicationType.PRIMARY_MANUSCRIPT, "status": PublicationStatus.PUBLISHED, "target_journal": "New England Journal of Medicine", "journal_tier": JournalTier.HIGH_IMPACT, "impact_factor": 176.1, "submission_date": now - timedelta(days=300), "acceptance_date": now - timedelta(days=240), "publication_date": now - timedelta(days=200), "doi": "10.1056/NEJMoa2304321", "pmid": "38123456", "word_count": 4500, "figure_count": 5, "table_count": 3, "created_at": now - timedelta(days=360)},
            {"id": "MS-002", "plan_id": "PP-001", "trial_id": EYLEA_TRIAL, "title": "Two-Year Outcomes of Aflibercept 8mg Extended Dosing in nAMD", "publication_type": PublicationType.SECONDARY_MANUSCRIPT, "status": PublicationStatus.UNDER_REVIEW, "target_journal": "Ophthalmology", "journal_tier": JournalTier.HIGH_IMPACT, "impact_factor": 13.7, "submission_date": now - timedelta(days=60), "word_count": 3800, "figure_count": 4, "table_count": 4, "created_at": now - timedelta(days=180)},
            {"id": "MS-003", "plan_id": "PP-001", "trial_id": EYLEA_TRIAL, "title": "Patient-Reported Outcomes with EYLEA HD in Neovascular AMD", "publication_type": PublicationType.SECONDARY_MANUSCRIPT, "status": PublicationStatus.INTERNAL_REVIEW, "target_journal": "Retina", "journal_tier": JournalTier.MID_IMPACT, "impact_factor": 4.5, "word_count": 3200, "figure_count": 3, "table_count": 2, "created_at": now - timedelta(days=120)},
            {"id": "MS-004", "plan_id": "PP-003", "trial_id": DUPIXENT_TRIAL, "title": "Dupilumab in Adults with Moderate-to-Severe Atopic Dermatitis: Pivotal Results", "publication_type": PublicationType.PRIMARY_MANUSCRIPT, "status": PublicationStatus.PUBLISHED, "target_journal": "The Lancet", "journal_tier": JournalTier.HIGH_IMPACT, "impact_factor": 168.9, "submission_date": now - timedelta(days=500), "acceptance_date": now - timedelta(days=440), "publication_date": now - timedelta(days=400), "doi": "10.1016/S0140-6736(23)01234-5", "pmid": "37654321", "word_count": 5200, "figure_count": 6, "table_count": 4, "created_at": now - timedelta(days=530)},
            {"id": "MS-005", "plan_id": "PP-003", "trial_id": DUPIXENT_TRIAL, "title": "Long-term Safety of Dupilumab in Atopic Dermatitis: Open-label Extension Data", "publication_type": PublicationType.SECONDARY_MANUSCRIPT, "status": PublicationStatus.PUBLISHED, "target_journal": "Journal of the American Academy of Dermatology", "journal_tier": JournalTier.HIGH_IMPACT, "impact_factor": 11.5, "submission_date": now - timedelta(days=350), "acceptance_date": now - timedelta(days=290), "publication_date": now - timedelta(days=250), "doi": "10.1016/j.jaad.2024.01.050", "pmid": "37876543", "word_count": 4000, "figure_count": 4, "table_count": 5, "created_at": now - timedelta(days=400)},
            {"id": "MS-006", "plan_id": "PP-004", "trial_id": DUPIXENT_TRIAL, "title": "Dupilumab as Add-on Therapy in Uncontrolled Moderate-to-Severe Asthma", "publication_type": PublicationType.PRIMARY_MANUSCRIPT, "status": PublicationStatus.PUBLISHED, "target_journal": "New England Journal of Medicine", "journal_tier": JournalTier.HIGH_IMPACT, "impact_factor": 176.1, "submission_date": now - timedelta(days=460), "acceptance_date": now - timedelta(days=400), "publication_date": now - timedelta(days=370), "doi": "10.1056/NEJMoa2305678", "pmid": "37234567", "word_count": 4800, "figure_count": 5, "table_count": 3, "created_at": now - timedelta(days=475)},
            {"id": "MS-007", "plan_id": "PP-005", "trial_id": DUPIXENT_TRIAL, "title": "Dupilumab in COPD with Type 2 Inflammation: Phase 3 Results", "publication_type": PublicationType.PRIMARY_MANUSCRIPT, "status": PublicationStatus.SUBMITTED, "target_journal": "New England Journal of Medicine", "journal_tier": JournalTier.HIGH_IMPACT, "impact_factor": 176.1, "submission_date": now - timedelta(days=30), "word_count": 4600, "figure_count": 5, "table_count": 4, "created_at": now - timedelta(days=180)},
            {"id": "MS-008", "plan_id": "PP-006", "trial_id": LIBTAYO_TRIAL, "title": "Cemiplimab Monotherapy for First-Line Treatment of Advanced NSCLC with PD-L1 >=50%", "publication_type": PublicationType.PRIMARY_MANUSCRIPT, "status": PublicationStatus.PUBLISHED, "target_journal": "The Lancet", "journal_tier": JournalTier.HIGH_IMPACT, "impact_factor": 168.9, "submission_date": now - timedelta(days=380), "acceptance_date": now - timedelta(days=320), "publication_date": now - timedelta(days=290), "doi": "10.1016/S0140-6736(24)00456-7", "pmid": "37345678", "word_count": 5000, "figure_count": 6, "table_count": 4, "created_at": now - timedelta(days=410)},
            {"id": "MS-009", "plan_id": "PP-006", "trial_id": LIBTAYO_TRIAL, "title": "Biomarker Analysis of Cemiplimab in First-Line NSCLC", "publication_type": PublicationType.SECONDARY_MANUSCRIPT, "status": PublicationStatus.REVISION_REQUESTED, "target_journal": "Journal of Clinical Oncology", "journal_tier": JournalTier.HIGH_IMPACT, "impact_factor": 45.3, "submission_date": now - timedelta(days=120), "word_count": 3500, "figure_count": 4, "table_count": 3, "created_at": now - timedelta(days=200)},
            {"id": "MS-010", "plan_id": "PP-007", "trial_id": LIBTAYO_TRIAL, "title": "Cemiplimab in Advanced Cutaneous Squamous Cell Carcinoma: Final Analysis", "publication_type": PublicationType.PRIMARY_MANUSCRIPT, "status": PublicationStatus.PUBLISHED, "target_journal": "New England Journal of Medicine", "journal_tier": JournalTier.HIGH_IMPACT, "impact_factor": 176.1, "submission_date": now - timedelta(days=560), "acceptance_date": now - timedelta(days=500), "publication_date": now - timedelta(days=470), "doi": "10.1056/NEJMoa2303456", "pmid": "36789012", "word_count": 4200, "figure_count": 5, "table_count": 3, "created_at": now - timedelta(days=590)},
            {"id": "MS-011", "plan_id": "PP-002", "trial_id": EYLEA_TRIAL, "title": "Long-term Visual Acuity with Aflibercept 8mg in DME: Extension Study Results", "publication_type": PublicationType.PRIMARY_MANUSCRIPT, "status": PublicationStatus.IN_DEVELOPMENT, "target_journal": "Diabetes Care", "journal_tier": JournalTier.HIGH_IMPACT, "impact_factor": 14.8, "word_count": 2800, "figure_count": 2, "table_count": 1, "created_at": now - timedelta(days=150)},
            {"id": "MS-012", "plan_id": "PP-010", "trial_id": DUPIXENT_TRIAL, "title": "Dupilumab in CRSwNP: Pooled Analysis of Phase 3 Trials", "publication_type": PublicationType.REVIEW_ARTICLE, "status": PublicationStatus.ACCEPTED, "target_journal": "Journal of Allergy and Clinical Immunology", "journal_tier": JournalTier.HIGH_IMPACT, "impact_factor": 14.2, "submission_date": now - timedelta(days=90), "acceptance_date": now - timedelta(days=20), "word_count": 3600, "figure_count": 4, "table_count": 3, "created_at": now - timedelta(days=200)},
            {"id": "MS-013", "plan_id": "PP-008", "trial_id": LIBTAYO_TRIAL, "title": "Cemiplimab in Locally Advanced BCC After Hedgehog Inhibitor Therapy", "publication_type": PublicationType.PRIMARY_MANUSCRIPT, "status": PublicationStatus.UNDER_REVIEW, "target_journal": "The Lancet Oncology", "journal_tier": JournalTier.HIGH_IMPACT, "impact_factor": 51.1, "submission_date": now - timedelta(days=45), "word_count": 4100, "figure_count": 5, "table_count": 3, "created_at": now - timedelta(days=200)},
            {"id": "MS-014", "plan_id": "PP-004", "trial_id": DUPIXENT_TRIAL, "title": "Health Economics Analysis of Dupilumab in Severe Asthma", "publication_type": PublicationType.SECONDARY_MANUSCRIPT, "status": PublicationStatus.PLANNED, "target_journal": "Value in Health", "journal_tier": JournalTier.MID_IMPACT, "impact_factor": 5.7, "word_count": 0, "figure_count": 0, "table_count": 0, "created_at": now - timedelta(days=60)},
            {"id": "MS-015", "plan_id": "PP-011", "trial_id": LIBTAYO_TRIAL, "title": "Cemiplimab Plus Chemotherapy in Recurrent/Metastatic Cervical Cancer: Phase 3 Results", "publication_type": PublicationType.PRIMARY_MANUSCRIPT, "status": PublicationStatus.IN_DEVELOPMENT, "target_journal": "Journal of Clinical Oncology", "journal_tier": JournalTier.HIGH_IMPACT, "impact_factor": 45.3, "word_count": 1500, "figure_count": 1, "table_count": 0, "created_at": now - timedelta(days=100)},
        ]

        for m in manuscripts_data:
            self._manuscripts[m["id"]] = Manuscript(**m)

        # --- 18 Authors ---
        authors_data = [
            {"id": "AU-001", "manuscript_id": "MS-001", "name": "Dr. Pravin Dugel", "institution": "Retinal Consultants of Arizona", "role": AuthorRole.FIRST_AUTHOR, "orcid": "0000-0001-2345-6789", "email": "pdugel@retinalconsultants.com", "order_position": 1, "contribution_statement": "Study design, data acquisition, data analysis, manuscript drafting", "approved_final": True},
            {"id": "AU-002", "manuscript_id": "MS-001", "name": "Dr. Sarah Chen", "institution": "Regeneron Pharmaceuticals", "role": AuthorRole.CORRESPONDING, "orcid": "0000-0002-3456-7890", "email": "sarah.chen@regeneron.com", "order_position": 2, "contribution_statement": "Study concept, data analysis, critical revision", "approved_final": True},
            {"id": "AU-003", "manuscript_id": "MS-001", "name": "Dr. George Yancopoulos", "institution": "Regeneron Pharmaceuticals", "role": AuthorRole.SENIOR_AUTHOR, "orcid": "0000-0003-4567-8901", "email": "george.yancopoulos@regeneron.com", "order_position": 8, "contribution_statement": "Study oversight, critical revision", "approved_final": True},
            {"id": "AU-004", "manuscript_id": "MS-004", "name": "Dr. Eric Simpson", "institution": "Oregon Health & Science University", "role": AuthorRole.FIRST_AUTHOR, "orcid": "0000-0002-5678-9012", "email": "simpsone@ohsu.edu", "order_position": 1, "contribution_statement": "Study design, patient enrollment, data acquisition, manuscript drafting", "approved_final": True},
            {"id": "AU-005", "manuscript_id": "MS-004", "name": "Dr. Anna Kowalski", "institution": "Regeneron Pharmaceuticals", "role": AuthorRole.CORRESPONDING, "orcid": "0000-0001-6789-0123", "email": "anna.kowalski@regeneron.com", "order_position": 2, "contribution_statement": "Study design, data analysis, critical revision", "approved_final": True},
            {"id": "AU-006", "manuscript_id": "MS-004", "name": "Dr. Peter Zhang", "institution": "Regeneron Pharmaceuticals", "role": AuthorRole.STATISTICIAN, "orcid": "0000-0003-7890-1234", "email": "peter.zhang@regeneron.com", "order_position": 5, "contribution_statement": "Statistical analysis plan, data analysis", "approved_final": True},
            {"id": "AU-007", "manuscript_id": "MS-006", "name": "Dr. Klaus Rabe", "institution": "LungenClinic Grosshansdorf", "role": AuthorRole.FIRST_AUTHOR, "orcid": "0000-0002-8901-2345", "email": "k.rabe@lungenclinic.de", "order_position": 1, "contribution_statement": "Study design, patient enrollment, data acquisition", "approved_final": True},
            {"id": "AU-008", "manuscript_id": "MS-006", "name": "David Lin", "institution": "Regeneron Pharmaceuticals", "role": AuthorRole.MEDICAL_WRITER, "email": "david.lin@regeneron.com", "order_position": 12, "contribution_statement": "Medical writing and editorial assistance", "approved_final": True},
            {"id": "AU-009", "manuscript_id": "MS-008", "name": "Dr. Ahmet Sezer", "institution": "Baskent University", "role": AuthorRole.FIRST_AUTHOR, "orcid": "0000-0001-9012-3456", "email": "asezer@baskent.edu.tr", "order_position": 1, "contribution_statement": "Study design, patient enrollment, data acquisition, manuscript drafting", "approved_final": True},
            {"id": "AU-010", "manuscript_id": "MS-008", "name": "Dr. Robert Kim", "institution": "Regeneron Pharmaceuticals", "role": AuthorRole.CORRESPONDING, "orcid": "0000-0002-0123-4567", "email": "robert.kim@regeneron.com", "order_position": 2, "contribution_statement": "Study concept, data analysis, critical revision", "approved_final": True},
            {"id": "AU-011", "manuscript_id": "MS-010", "name": "Dr. Michael Migden", "institution": "MD Anderson Cancer Center", "role": AuthorRole.FIRST_AUTHOR, "orcid": "0000-0003-1234-5678", "email": "mmigden@mdanderson.org", "order_position": 1, "contribution_statement": "Study design, patient enrollment, data acquisition", "approved_final": True},
            {"id": "AU-012", "manuscript_id": "MS-002", "name": "Dr. Jean-Francois Korobelnik", "institution": "CHU de Bordeaux", "role": AuthorRole.FIRST_AUTHOR, "orcid": "0000-0001-4321-8765", "email": "jfk@chu-bordeaux.fr", "order_position": 1, "contribution_statement": "Study design, data acquisition, manuscript drafting", "approved_final": True},
            {"id": "AU-013", "manuscript_id": "MS-002", "name": "Dr. Sarah Chen", "institution": "Regeneron Pharmaceuticals", "role": AuthorRole.CO_AUTHOR, "email": "sarah.chen@regeneron.com", "order_position": 3, "contribution_statement": "Data analysis, critical revision", "approved_final": True},
            {"id": "AU-014", "manuscript_id": "MS-007", "name": "Dr. Surya Bhatt", "institution": "University of Alabama at Birmingham", "role": AuthorRole.FIRST_AUTHOR, "orcid": "0000-0002-5432-1098", "email": "sbhatt@uabmc.edu", "order_position": 1, "contribution_statement": "Study design, patient enrollment, data acquisition, manuscript drafting", "approved_final": False},
            {"id": "AU-015", "manuscript_id": "MS-009", "name": "Dr. Matthew Hellmann", "institution": "Memorial Sloan Kettering", "role": AuthorRole.FIRST_AUTHOR, "orcid": "0000-0003-6543-2109", "email": "hellmanm@mskcc.org", "order_position": 1, "contribution_statement": "Biomarker analysis, data interpretation, manuscript drafting", "approved_final": False},
            {"id": "AU-016", "manuscript_id": "MS-012", "name": "Dr. Claus Bachert", "institution": "Ghent University Hospital", "role": AuthorRole.FIRST_AUTHOR, "orcid": "0000-0001-7654-3210", "email": "claus.bachert@ugent.be", "order_position": 1, "contribution_statement": "Data analysis, manuscript drafting", "approved_final": True},
            {"id": "AU-017", "manuscript_id": "MS-013", "name": "Dr. Aleksandar Sekulic", "institution": "Mayo Clinic", "role": AuthorRole.FIRST_AUTHOR, "orcid": "0000-0002-8765-4321", "email": "sekulic@mayo.edu", "order_position": 1, "contribution_statement": "Study design, patient enrollment, data acquisition", "approved_final": False},
            {"id": "AU-018", "manuscript_id": "MS-015", "name": "Dr. Bradley Monk", "institution": "HonorHealth Research Institute", "role": AuthorRole.FIRST_AUTHOR, "orcid": "0000-0003-9876-5432", "email": "bmonk@honorhealth.com", "order_position": 1, "contribution_statement": "Study design, patient enrollment, data acquisition", "approved_final": False},
        ]

        for a in authors_data:
            self._authors[a["id"]] = Author(**a)

        # --- 12 Congress Submissions ---
        congress_data = [
            {"id": "CS-001", "plan_id": "PP-001", "trial_id": EYLEA_TRIAL, "congress_name": "American Academy of Ophthalmology (AAO) 2024", "congress_date": now - timedelta(days=120), "congress_tier": CongressTier.TIER_1, "abstract_title": "PULSAR Trial: 96-Week Efficacy of Aflibercept 8mg in nAMD", "submission_type": PublicationType.ORAL_PRESENTATION, "status": PublicationStatus.PUBLISHED, "submission_deadline": now - timedelta(days=200), "submission_date": now - timedelta(days=195), "acceptance_date": now - timedelta(days=160), "presentation_date": now - timedelta(days=120), "presenter": "Dr. Pravin Dugel", "abstract_number": "PA-0234", "created_at": now - timedelta(days=210)},
            {"id": "CS-002", "plan_id": "PP-001", "trial_id": EYLEA_TRIAL, "congress_name": "Association for Research in Vision and Ophthalmology (ARVO) 2025", "congress_date": now + timedelta(days=60), "congress_tier": CongressTier.TIER_1, "abstract_title": "Anatomical Outcomes with EYLEA HD: OCT Subanalysis from PULSAR", "submission_type": PublicationType.POSTER, "status": PublicationStatus.SUBMITTED, "submission_deadline": now - timedelta(days=30), "submission_date": now - timedelta(days=28), "presenter": "Dr. Michael Torres", "created_at": now - timedelta(days=60)},
            {"id": "CS-003", "plan_id": "PP-003", "trial_id": DUPIXENT_TRIAL, "congress_name": "American Academy of Dermatology (AAD) 2024", "congress_date": now - timedelta(days=90), "congress_tier": CongressTier.TIER_1, "abstract_title": "5-Year Safety and Efficacy of Dupilumab in Atopic Dermatitis", "submission_type": PublicationType.ORAL_PRESENTATION, "status": PublicationStatus.PUBLISHED, "submission_deadline": now - timedelta(days=180), "submission_date": now - timedelta(days=175), "acceptance_date": now - timedelta(days=140), "presentation_date": now - timedelta(days=90), "presenter": "Dr. Eric Simpson", "abstract_number": "OP-1456", "created_at": now - timedelta(days=200)},
            {"id": "CS-004", "plan_id": "PP-004", "trial_id": DUPIXENT_TRIAL, "congress_name": "European Respiratory Society (ERS) 2024", "congress_date": now - timedelta(days=150), "congress_tier": CongressTier.TIER_1, "abstract_title": "Dupilumab Reduces Exacerbations in Moderate-to-Severe Asthma: Phase 3 Update", "submission_type": PublicationType.ORAL_PRESENTATION, "status": PublicationStatus.PUBLISHED, "submission_deadline": now - timedelta(days=240), "submission_date": now - timedelta(days=235), "acceptance_date": now - timedelta(days=200), "presentation_date": now - timedelta(days=150), "presenter": "Dr. Klaus Rabe", "abstract_number": "OA-3567", "created_at": now - timedelta(days=250)},
            {"id": "CS-005", "plan_id": "PP-005", "trial_id": DUPIXENT_TRIAL, "congress_name": "American Thoracic Society (ATS) 2025", "congress_date": now + timedelta(days=90), "congress_tier": CongressTier.TIER_1, "abstract_title": "Dupilumab in COPD with Type 2 Inflammation: Primary Endpoint Analysis", "submission_type": PublicationType.ORAL_PRESENTATION, "status": PublicationStatus.SUBMITTED, "submission_deadline": now - timedelta(days=15), "submission_date": now - timedelta(days=12), "presenter": "Dr. Surya Bhatt", "created_at": now - timedelta(days=45)},
            {"id": "CS-006", "plan_id": "PP-006", "trial_id": LIBTAYO_TRIAL, "congress_name": "American Society of Clinical Oncology (ASCO) 2024", "congress_date": now - timedelta(days=240), "congress_tier": CongressTier.TIER_1, "abstract_title": "Cemiplimab vs Pembrolizumab in First-Line NSCLC: Updated OS Analysis", "submission_type": PublicationType.ORAL_PRESENTATION, "status": PublicationStatus.PUBLISHED, "submission_deadline": now - timedelta(days=320), "submission_date": now - timedelta(days=315), "acceptance_date": now - timedelta(days=280), "presentation_date": now - timedelta(days=240), "presenter": "Dr. Ahmet Sezer", "abstract_number": "LBA-9502", "created_at": now - timedelta(days=330)},
            {"id": "CS-007", "plan_id": "PP-006", "trial_id": LIBTAYO_TRIAL, "congress_name": "European Society for Medical Oncology (ESMO) 2024", "congress_date": now - timedelta(days=100), "congress_tier": CongressTier.TIER_1, "abstract_title": "Quality of Life with Cemiplimab in First-Line NSCLC", "submission_type": PublicationType.POSTER, "status": PublicationStatus.PUBLISHED, "submission_deadline": now - timedelta(days=190), "submission_date": now - timedelta(days=185), "acceptance_date": now - timedelta(days=140), "presentation_date": now - timedelta(days=100), "presenter": "Dr. Robert Kim", "abstract_number": "P-1234", "created_at": now - timedelta(days=200)},
            {"id": "CS-008", "plan_id": "PP-007", "trial_id": LIBTAYO_TRIAL, "congress_name": "Society for Investigative Dermatology (SID) 2024", "congress_date": now - timedelta(days=180), "congress_tier": CongressTier.TIER_2, "abstract_title": "Durable Responses with Cemiplimab in Advanced CSCC: 4-Year Follow-up", "submission_type": PublicationType.POSTER, "status": PublicationStatus.PUBLISHED, "submission_deadline": now - timedelta(days=260), "submission_date": now - timedelta(days=255), "acceptance_date": now - timedelta(days=220), "presentation_date": now - timedelta(days=180), "presenter": "Dr. Michael Migden", "abstract_number": "EP-456", "created_at": now - timedelta(days=270)},
            {"id": "CS-009", "plan_id": "PP-008", "trial_id": LIBTAYO_TRIAL, "congress_name": "World Congress of Dermatology (WCD) 2025", "congress_date": now + timedelta(days=120), "congress_tier": CongressTier.TIER_1, "abstract_title": "Cemiplimab in Locally Advanced BCC: Subgroup Analyses", "submission_type": PublicationType.POSTER, "status": PublicationStatus.PLANNED, "submission_deadline": now + timedelta(days=30), "created_at": now - timedelta(days=30)},
            {"id": "CS-010", "plan_id": "PP-010", "trial_id": DUPIXENT_TRIAL, "congress_name": "European Academy of Allergy and Clinical Immunology (EAACI) 2025", "congress_date": now + timedelta(days=150), "congress_tier": CongressTier.TIER_1, "abstract_title": "Pooled Safety Analysis of Dupilumab in CRSwNP", "submission_type": PublicationType.ORAL_PRESENTATION, "status": PublicationStatus.PLANNED, "submission_deadline": now + timedelta(days=45), "created_at": now - timedelta(days=20)},
            {"id": "CS-011", "plan_id": "PP-003", "trial_id": DUPIXENT_TRIAL, "congress_name": "Regeneron Science Day 2024", "congress_date": now - timedelta(days=60), "congress_tier": CongressTier.INTERNAL, "abstract_title": "Dupilumab Mechanism of Action: IL-4/IL-13 Pathway Insights", "submission_type": PublicationType.ORAL_PRESENTATION, "status": PublicationStatus.PUBLISHED, "submission_date": now - timedelta(days=75), "acceptance_date": now - timedelta(days=70), "presentation_date": now - timedelta(days=60), "presenter": "Dr. Anna Kowalski", "created_at": now - timedelta(days=80)},
            {"id": "CS-012", "plan_id": "PP-011", "trial_id": LIBTAYO_TRIAL, "congress_name": "Society of Gynecologic Oncology (SGO) 2025", "congress_date": now + timedelta(days=75), "congress_tier": CongressTier.TIER_2, "abstract_title": "Cemiplimab Plus Chemotherapy in Cervical Cancer: Safety Run-in Data", "submission_type": PublicationType.POSTER, "status": PublicationStatus.SUBMITTED, "submission_deadline": now - timedelta(days=10), "submission_date": now - timedelta(days=8), "presenter": "Dr. Bradley Monk", "created_at": now - timedelta(days=40)},
        ]

        for c in congress_data:
            self._congress_submissions[c["id"]] = CongressSubmission(**c)

        # --- 12 Journal Submissions ---
        journal_data = [
            {"id": "JS-001", "manuscript_id": "MS-001", "journal_name": "New England Journal of Medicine", "submission_date": now - timedelta(days=300), "decision_date": now - timedelta(days=240), "decision": "accepted", "reviewer_comments": ["Excellent methodology and sample size", "Clear presentation of primary and secondary endpoints", "Minor revisions to supplementary tables recommended"], "round_number": 2, "tracking_id": "NEJM-2024-12345"},
            {"id": "JS-002", "manuscript_id": "MS-004", "journal_name": "The Lancet", "submission_date": now - timedelta(days=500), "decision_date": now - timedelta(days=440), "decision": "accepted", "reviewer_comments": ["Landmark trial in atopic dermatitis", "Robust safety data", "Request additional subgroup analyses"], "round_number": 2, "tracking_id": "THELANCET-2023-67890"},
            {"id": "JS-003", "manuscript_id": "MS-006", "journal_name": "New England Journal of Medicine", "submission_date": now - timedelta(days=460), "decision_date": now - timedelta(days=400), "decision": "accepted", "reviewer_comments": ["Important contribution to asthma treatment", "Statistical analysis appropriate", "Clarify biologics-naive subgroup definition"], "round_number": 2, "tracking_id": "NEJM-2023-54321"},
            {"id": "JS-004", "manuscript_id": "MS-008", "journal_name": "The Lancet", "submission_date": now - timedelta(days=380), "decision_date": now - timedelta(days=320), "decision": "accepted", "reviewer_comments": ["Practice-changing results in NSCLC", "Well-designed non-inferiority trial", "Include patient-reported outcomes"], "round_number": 2, "tracking_id": "THELANCET-2024-11223"},
            {"id": "JS-005", "manuscript_id": "MS-010", "journal_name": "New England Journal of Medicine", "submission_date": now - timedelta(days=560), "decision_date": now - timedelta(days=500), "decision": "accepted", "reviewer_comments": ["Significant advance in CSCC treatment", "Durable response rates impressive", "Address rare immune-related AEs in discussion"], "round_number": 1, "tracking_id": "NEJM-2023-98765"},
            {"id": "JS-006", "manuscript_id": "MS-002", "journal_name": "Ophthalmology", "submission_date": now - timedelta(days=60), "reviewer_comments": [], "round_number": 1, "tracking_id": "OPHTHA-2025-34567"},
            {"id": "JS-007", "manuscript_id": "MS-005", "journal_name": "Journal of the American Academy of Dermatology", "submission_date": now - timedelta(days=350), "decision_date": now - timedelta(days=290), "decision": "accepted", "reviewer_comments": ["Valuable long-term safety data", "Comprehensive adverse event reporting"], "round_number": 1, "tracking_id": "JAAD-2024-44556"},
            {"id": "JS-008", "manuscript_id": "MS-007", "journal_name": "New England Journal of Medicine", "submission_date": now - timedelta(days=30), "reviewer_comments": [], "round_number": 1, "tracking_id": "NEJM-2025-77889"},
            {"id": "JS-009", "manuscript_id": "MS-009", "journal_name": "Journal of Clinical Oncology", "submission_date": now - timedelta(days=120), "decision_date": now - timedelta(days=75), "decision": "revision_requested", "reviewer_comments": ["Biomarker methodology needs clarification", "Add validation cohort data", "Expand TMB analysis section"], "revision_due_date": now + timedelta(days=15), "round_number": 1, "tracking_id": "JCO-2025-22334"},
            {"id": "JS-010", "manuscript_id": "MS-012", "journal_name": "Journal of Allergy and Clinical Immunology", "submission_date": now - timedelta(days=90), "decision_date": now - timedelta(days=20), "decision": "accepted", "reviewer_comments": ["Comprehensive pooled analysis", "Statistical methodology appropriate", "Include forest plot for subgroups"], "round_number": 2, "tracking_id": "JACI-2025-55667"},
            {"id": "JS-011", "manuscript_id": "MS-013", "journal_name": "The Lancet Oncology", "submission_date": now - timedelta(days=45), "reviewer_comments": [], "round_number": 1, "tracking_id": "LANCETONCOL-2025-88990"},
            {"id": "JS-012", "manuscript_id": "MS-009", "journal_name": "Annals of Oncology", "submission_date": now - timedelta(days=200), "decision_date": now - timedelta(days=160), "decision": "rejected", "reviewer_comments": ["Insufficient novel findings", "Consider a more specialized journal"], "round_number": 1, "tracking_id": "ANNONC-2024-33445"},
        ]

        for j in journal_data:
            self._journal_submissions[j["id"]] = JournalSubmission(**j)

        logger.info(
            "Seeded publication planning data: %d plans, %d manuscripts, %d authors, %d congress submissions, %d journal submissions",
            len(self._plans),
            len(self._manuscripts),
            len(self._authors),
            len(self._congress_submissions),
            len(self._journal_submissions),
        )

    # ------------------------------------------------------------------
    # Publication Plan Management
    # ------------------------------------------------------------------

    def list_plans(
        self,
        *,
        trial_id: str | None = None,
        status: str | None = None,
    ) -> list[PublicationPlan]:
        """List publication plans with optional filters."""
        with self._lock:
            result = list(self._plans.values())

        if trial_id is not None:
            result = [p for p in result if p.trial_id == trial_id]
        if status is not None:
            result = [p for p in result if p.status == status]

        return sorted(result, key=lambda p: p.id)

    def get_plan(self, plan_id: str) -> PublicationPlan | None:
        """Get a single publication plan by ID."""
        with self._lock:
            return self._plans.get(plan_id)

    def create_plan(self, payload: PublicationPlanCreate) -> PublicationPlan:
        """Create a new publication plan."""
        plan_id = f"PP-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        plan = PublicationPlan(
            id=plan_id,
            trial_id=payload.trial_id,
            plan_name=payload.plan_name,
            therapeutic_area=payload.therapeutic_area,
            publication_lead=payload.publication_lead,
            medical_writer=payload.medical_writer,
            target_publications=0,
            completed_publications=0,
            status="active",
            created_at=now,
        )
        with self._lock:
            self._plans[plan_id] = plan
        logger.info("Created publication plan %s: '%s'", plan_id, payload.plan_name)
        return plan

    def update_plan(
        self, plan_id: str, payload: PublicationPlanUpdate
    ) -> PublicationPlan | None:
        """Update an existing publication plan."""
        with self._lock:
            existing = self._plans.get(plan_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = PublicationPlan(**data)
            self._plans[plan_id] = updated
        return updated

    def delete_plan(self, plan_id: str) -> bool:
        """Delete a publication plan. Returns True if deleted."""
        with self._lock:
            if plan_id in self._plans:
                del self._plans[plan_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Manuscript Management
    # ------------------------------------------------------------------

    def list_manuscripts(
        self,
        *,
        plan_id: str | None = None,
        trial_id: str | None = None,
        status: PublicationStatus | None = None,
        publication_type: PublicationType | None = None,
    ) -> list[Manuscript]:
        """List manuscripts with optional filters."""
        with self._lock:
            result = list(self._manuscripts.values())

        if plan_id is not None:
            result = [m for m in result if m.plan_id == plan_id]
        if trial_id is not None:
            result = [m for m in result if m.trial_id == trial_id]
        if status is not None:
            result = [m for m in result if m.status == status]
        if publication_type is not None:
            result = [m for m in result if m.publication_type == publication_type]

        return sorted(result, key=lambda m: m.id)

    def get_manuscript(self, manuscript_id: str) -> Manuscript | None:
        """Get a single manuscript by ID."""
        with self._lock:
            return self._manuscripts.get(manuscript_id)

    def create_manuscript(self, payload: ManuscriptCreate) -> Manuscript:
        """Create a new manuscript."""
        manuscript_id = f"MS-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        manuscript = Manuscript(
            id=manuscript_id,
            plan_id=payload.plan_id,
            trial_id=payload.trial_id,
            title=payload.title,
            publication_type=payload.publication_type,
            target_journal=payload.target_journal,
            journal_tier=payload.journal_tier,
            status=PublicationStatus.PLANNED,
            word_count=0,
            figure_count=0,
            table_count=0,
            created_at=now,
        )
        with self._lock:
            self._manuscripts[manuscript_id] = manuscript
        logger.info("Created manuscript %s: '%s'", manuscript_id, payload.title)
        return manuscript

    def update_manuscript(
        self, manuscript_id: str, payload: ManuscriptUpdate
    ) -> Manuscript | None:
        """Update an existing manuscript."""
        with self._lock:
            existing = self._manuscripts.get(manuscript_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = Manuscript(**data)
            self._manuscripts[manuscript_id] = updated
        return updated

    def delete_manuscript(self, manuscript_id: str) -> bool:
        """Delete a manuscript. Returns True if deleted."""
        with self._lock:
            if manuscript_id in self._manuscripts:
                del self._manuscripts[manuscript_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Author Management
    # ------------------------------------------------------------------

    def list_authors(
        self,
        *,
        manuscript_id: str | None = None,
        role: AuthorRole | None = None,
    ) -> list[Author]:
        """List authors with optional filters."""
        with self._lock:
            result = list(self._authors.values())

        if manuscript_id is not None:
            result = [a for a in result if a.manuscript_id == manuscript_id]
        if role is not None:
            result = [a for a in result if a.role == role]

        return sorted(result, key=lambda a: a.id)

    def get_author(self, author_id: str) -> Author | None:
        """Get a single author by ID."""
        with self._lock:
            return self._authors.get(author_id)

    def create_author(self, payload: AuthorCreate) -> Author:
        """Create a new author."""
        author_id = f"AU-{uuid4().hex[:8].upper()}"
        author = Author(
            id=author_id,
            manuscript_id=payload.manuscript_id,
            name=payload.name,
            institution=payload.institution,
            role=payload.role,
            order_position=payload.order_position,
            orcid=payload.orcid,
            email=payload.email,
            approved_final=False,
        )
        with self._lock:
            self._authors[author_id] = author
        logger.info("Created author %s: '%s'", author_id, payload.name)
        return author

    def update_author(
        self, author_id: str, payload: AuthorUpdate
    ) -> Author | None:
        """Update an existing author."""
        with self._lock:
            existing = self._authors.get(author_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = Author(**data)
            self._authors[author_id] = updated
        return updated

    def delete_author(self, author_id: str) -> bool:
        """Delete an author. Returns True if deleted."""
        with self._lock:
            if author_id in self._authors:
                del self._authors[author_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Congress Submission Management
    # ------------------------------------------------------------------

    def list_congress_submissions(
        self,
        *,
        plan_id: str | None = None,
        trial_id: str | None = None,
        congress_tier: CongressTier | None = None,
        status: PublicationStatus | None = None,
    ) -> list[CongressSubmission]:
        """List congress submissions with optional filters."""
        with self._lock:
            result = list(self._congress_submissions.values())

        if plan_id is not None:
            result = [c for c in result if c.plan_id == plan_id]
        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]
        if congress_tier is not None:
            result = [c for c in result if c.congress_tier == congress_tier]
        if status is not None:
            result = [c for c in result if c.status == status]

        return sorted(result, key=lambda c: c.id)

    def get_congress_submission(self, submission_id: str) -> CongressSubmission | None:
        """Get a single congress submission by ID."""
        with self._lock:
            return self._congress_submissions.get(submission_id)

    def create_congress_submission(self, payload: CongressSubmissionCreate) -> CongressSubmission:
        """Create a new congress submission."""
        submission_id = f"CS-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        submission = CongressSubmission(
            id=submission_id,
            plan_id=payload.plan_id,
            trial_id=payload.trial_id,
            congress_name=payload.congress_name,
            congress_date=payload.congress_date,
            congress_tier=payload.congress_tier,
            abstract_title=payload.abstract_title,
            submission_type=payload.submission_type,
            status=PublicationStatus.PLANNED,
            created_at=now,
        )
        with self._lock:
            self._congress_submissions[submission_id] = submission
        logger.info("Created congress submission %s: '%s'", submission_id, payload.abstract_title)
        return submission

    def update_congress_submission(
        self, submission_id: str, payload: CongressSubmissionUpdate
    ) -> CongressSubmission | None:
        """Update an existing congress submission."""
        with self._lock:
            existing = self._congress_submissions.get(submission_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CongressSubmission(**data)
            self._congress_submissions[submission_id] = updated
        return updated

    def delete_congress_submission(self, submission_id: str) -> bool:
        """Delete a congress submission. Returns True if deleted."""
        with self._lock:
            if submission_id in self._congress_submissions:
                del self._congress_submissions[submission_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Journal Submission Management
    # ------------------------------------------------------------------

    def list_journal_submissions(
        self,
        *,
        manuscript_id: str | None = None,
        decision: str | None = None,
    ) -> list[JournalSubmission]:
        """List journal submissions with optional filters."""
        with self._lock:
            result = list(self._journal_submissions.values())

        if manuscript_id is not None:
            result = [j for j in result if j.manuscript_id == manuscript_id]
        if decision is not None:
            result = [j for j in result if j.decision == decision]

        return sorted(result, key=lambda j: j.id)

    def get_journal_submission(self, submission_id: str) -> JournalSubmission | None:
        """Get a single journal submission by ID."""
        with self._lock:
            return self._journal_submissions.get(submission_id)

    def create_journal_submission(self, payload: JournalSubmissionCreate) -> JournalSubmission:
        """Create a new journal submission."""
        submission_id = f"JS-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        submission = JournalSubmission(
            id=submission_id,
            manuscript_id=payload.manuscript_id,
            journal_name=payload.journal_name,
            submission_date=now,
            round_number=1,
        )
        with self._lock:
            self._journal_submissions[submission_id] = submission
        logger.info("Created journal submission %s: '%s'", submission_id, payload.journal_name)
        return submission

    def update_journal_submission(
        self, submission_id: str, payload: JournalSubmissionUpdate
    ) -> JournalSubmission | None:
        """Update an existing journal submission."""
        with self._lock:
            existing = self._journal_submissions.get(submission_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = JournalSubmission(**data)
            self._journal_submissions[submission_id] = updated
        return updated

    def delete_journal_submission(self, submission_id: str) -> bool:
        """Delete a journal submission. Returns True if deleted."""
        with self._lock:
            if submission_id in self._journal_submissions:
                del self._journal_submissions[submission_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> PublicationMetrics:
        """Compute aggregated publication metrics."""
        with self._lock:
            plans = list(self._plans.values())
            manuscripts = list(self._manuscripts.values())
            authors = list(self._authors.values())
            congress_subs = list(self._congress_submissions.values())
            journal_subs = list(self._journal_submissions.values())

        # Plans
        active_plans = sum(1 for p in plans if p.status == "active")

        # Manuscripts by status
        manuscripts_by_status: dict[str, int] = {}
        for m in manuscripts:
            key = m.status.value
            manuscripts_by_status[key] = manuscripts_by_status.get(key, 0) + 1

        # Manuscripts by type
        manuscripts_by_type: dict[str, int] = {}
        for m in manuscripts:
            key = m.publication_type.value
            manuscripts_by_type[key] = manuscripts_by_type.get(key, 0) + 1

        # Published count
        published_count = sum(1 for m in manuscripts if m.status == PublicationStatus.PUBLISHED)

        # Congress by tier
        congress_by_tier: dict[str, int] = {}
        for c in congress_subs:
            key = c.congress_tier.value
            congress_by_tier[key] = congress_by_tier.get(key, 0) + 1

        # Accepted congress rate
        congress_decided = [
            c for c in congress_subs
            if c.status in (PublicationStatus.ACCEPTED, PublicationStatus.PUBLISHED, PublicationStatus.REJECTED)
        ]
        if congress_decided:
            accepted_congress = sum(
                1 for c in congress_decided
                if c.status in (PublicationStatus.ACCEPTED, PublicationStatus.PUBLISHED)
            )
            accepted_congress_rate_pct = round((accepted_congress / len(congress_decided)) * 100.0, 1)
        else:
            accepted_congress_rate_pct = 0.0

        # Average review rounds
        subs_with_rounds = [j for j in journal_subs if j.round_number >= 1]
        if subs_with_rounds:
            avg_review_rounds = round(
                sum(j.round_number for j in subs_with_rounds) / len(subs_with_rounds), 1
            )
        else:
            avg_review_rounds = 0.0

        # Average submission to acceptance days
        accepted_subs = [
            j for j in journal_subs
            if j.decision == "accepted" and j.decision_date is not None
        ]
        if accepted_subs:
            total_days = sum(
                (j.decision_date - j.submission_date).total_seconds() / 86400.0
                for j in accepted_subs
            )
            avg_submission_to_acceptance_days = round(total_days / len(accepted_subs), 1)
        else:
            avg_submission_to_acceptance_days = 0.0

        return PublicationMetrics(
            total_plans=len(plans),
            active_plans=active_plans,
            total_manuscripts=len(manuscripts),
            manuscripts_by_status=manuscripts_by_status,
            manuscripts_by_type=manuscripts_by_type,
            published_count=published_count,
            total_authors=len(authors),
            total_congress_submissions=len(congress_subs),
            congress_by_tier=congress_by_tier,
            accepted_congress_rate_pct=accepted_congress_rate_pct,
            total_journal_submissions=len(journal_subs),
            avg_review_rounds=avg_review_rounds,
            avg_submission_to_acceptance_days=avg_submission_to_acceptance_days,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: PublicationPlanningService | None = None
_instance_lock = threading.Lock()


def get_publication_planning_service() -> PublicationPlanningService:
    """Return the singleton PublicationPlanningService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = PublicationPlanningService()
    return _instance


def reset_publication_planning_service() -> PublicationPlanningService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = PublicationPlanningService()
    return _instance
