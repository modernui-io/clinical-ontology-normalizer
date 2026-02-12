"""Medical Information Services (MED-INFO) Management Service.

Manages medical information operations: inquiry management, standard response
documents, product FAQ libraries, field medical insights, scientific
communication tracking, and medical information operational metrics.

Usage:
    from app.services.medical_information_service import (
        get_medical_information_service,
    )

    svc = get_medical_information_service()
    inquiries = svc.list_inquiries()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.medical_information import (
    DocumentType,
    FieldMedicalInsight,
    FieldMedicalInsightCreate,
    FieldMedicalInsightUpdate,
    InquiryCategory,
    InquirySource,
    InquiryStatus,
    MedicalInformationMetrics,
    MedicalInquiry,
    MedicalInquiryCreate,
    MedicalInquiryUpdate,
    ProductFAQ,
    ProductFAQCreate,
    ProductFAQUpdate,
    ResponseType,
    ScientificCommunication,
    ScientificCommunicationCreate,
    ScientificCommunicationUpdate,
    StandardResponseDoc,
    StandardResponseDocCreate,
    StandardResponseDocUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class MedicalInformationService:
    """In-memory Medical Information Services engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._inquiries: dict[str, MedicalInquiry] = {}
        self._standard_responses: dict[str, StandardResponseDoc] = {}
        self._faqs: dict[str, ProductFAQ] = {}
        self._insights: dict[str, FieldMedicalInsight] = {}
        self._communications: dict[str, ScientificCommunication] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic medical information data across Regeneron products."""
        now = datetime.now(timezone.utc)

        # --- 12 Medical Inquiries ---
        inquiries_data = [
            {"id": "INQ-001", "trial_id": EYLEA_TRIAL, "product_name": "EYLEA HD", "inquiry_source": InquirySource.HCP, "category": InquiryCategory.DOSING, "status": InquiryStatus.CLOSED, "question_text": "What is the recommended dosing interval for EYLEA HD in wet AMD after the loading phase?", "response_text": "After monthly loading doses, EYLEA HD 8 mg is administered every 8-16 weeks based on disease activity.", "response_type": ResponseType.STANDARD, "requester_name": "Dr. Sarah Mitchell", "requester_institution": "Duke Eye Center", "requester_country": "US", "assigned_to": "MedInfo Specialist A", "received_date": now - timedelta(days=60), "response_date": now - timedelta(days=57), "turnaround_days": 3, "follow_up_required": False, "adverse_event_reported": False, "created_at": now - timedelta(days=60)},
            {"id": "INQ-002", "trial_id": EYLEA_TRIAL, "product_name": "EYLEA HD", "inquiry_source": InquirySource.HCP, "category": InquiryCategory.EFFICACY, "status": InquiryStatus.CLOSED, "question_text": "How does EYLEA HD compare to the standard 2 mg formulation in visual acuity outcomes?", "response_text": "PULSAR trial data demonstrate EYLEA HD 8 mg non-inferiority in BCVA gains with extended dosing intervals.", "response_type": ResponseType.LITERATURE_SEARCH, "requester_name": "Dr. James Wong", "requester_institution": "Bascom Palmer Eye Institute", "requester_country": "US", "assigned_to": "MedInfo Specialist B", "received_date": now - timedelta(days=55), "response_date": now - timedelta(days=50), "turnaround_days": 5, "follow_up_required": False, "adverse_event_reported": False, "created_at": now - timedelta(days=55)},
            {"id": "INQ-003", "trial_id": None, "product_name": "EYLEA HD", "inquiry_source": InquirySource.PATIENT, "category": InquiryCategory.STORAGE, "status": InquiryStatus.CLOSED, "question_text": "How should EYLEA HD be stored at the clinic?", "response_text": "Store in the original carton under refrigeration at 2-8 degrees C. Protect from light.", "response_type": ResponseType.STANDARD, "requester_name": "Patient inquiry via call center", "requester_institution": None, "requester_country": "US", "assigned_to": "MedInfo Specialist A", "received_date": now - timedelta(days=50), "response_date": now - timedelta(days=49), "turnaround_days": 1, "follow_up_required": False, "adverse_event_reported": False, "created_at": now - timedelta(days=50)},
            {"id": "INQ-004", "trial_id": DUPIXENT_TRIAL, "product_name": "Dupixent", "inquiry_source": InquirySource.HCP, "category": InquiryCategory.SAFETY, "status": InquiryStatus.CLOSED, "question_text": "What is the incidence of conjunctivitis in Dupixent-treated atopic dermatitis patients?", "response_text": "Conjunctivitis was reported in approximately 10% of patients in pivotal AD trials.", "response_type": ResponseType.STANDARD, "requester_name": "Dr. Angela Torres", "requester_institution": "NYU Langone Dermatology", "requester_country": "US", "assigned_to": "MedInfo Specialist C", "received_date": now - timedelta(days=45), "response_date": now - timedelta(days=43), "turnaround_days": 2, "follow_up_required": False, "adverse_event_reported": True, "created_at": now - timedelta(days=45)},
            {"id": "INQ-005", "trial_id": DUPIXENT_TRIAL, "product_name": "Dupixent", "inquiry_source": InquirySource.PHARMACIST, "category": InquiryCategory.DRUG_INTERACTIONS, "status": InquiryStatus.CLOSED, "question_text": "Are there known drug interactions between Dupixent and live vaccines?", "response_text": "Avoid use of live vaccines during Dupixent treatment. Non-live vaccines may be administered.", "response_type": ResponseType.STANDARD, "requester_name": "PharmD Lisa Chen", "requester_institution": "CVS Specialty Pharmacy", "requester_country": "US", "assigned_to": "MedInfo Specialist C", "received_date": now - timedelta(days=40), "response_date": now - timedelta(days=38), "turnaround_days": 2, "follow_up_required": False, "adverse_event_reported": False, "created_at": now - timedelta(days=40)},
            {"id": "INQ-006", "trial_id": None, "product_name": "Dupixent", "inquiry_source": InquirySource.PAYER, "category": InquiryCategory.REIMBURSEMENT, "status": InquiryStatus.CLOSED, "question_text": "What prior authorization criteria does Regeneron support for Dupixent in CRSwNP?", "response_text": "Detailed reimbursement support materials and prior auth guidance provided via Dupixent MyWay.", "response_type": ResponseType.CUSTOM, "requester_name": "John Davis", "requester_institution": "Aetna Pharmacy", "requester_country": "US", "assigned_to": "MedInfo Specialist D", "received_date": now - timedelta(days=35), "response_date": now - timedelta(days=30), "turnaround_days": 5, "follow_up_required": True, "adverse_event_reported": False, "created_at": now - timedelta(days=35)},
            {"id": "INQ-007", "trial_id": LIBTAYO_TRIAL, "product_name": "Libtayo", "inquiry_source": InquirySource.HCP, "category": InquiryCategory.EFFICACY, "status": InquiryStatus.CLOSED, "question_text": "What is the overall response rate for Libtayo in advanced CSCC?", "response_text": "In the pivotal study, Libtayo demonstrated an ORR of approximately 47% in advanced CSCC patients.", "response_type": ResponseType.LITERATURE_SEARCH, "requester_name": "Dr. Robert Kim", "requester_institution": "MD Anderson Cancer Center", "requester_country": "US", "assigned_to": "MedInfo Specialist E", "received_date": now - timedelta(days=30), "response_date": now - timedelta(days=26), "turnaround_days": 4, "follow_up_required": False, "adverse_event_reported": False, "created_at": now - timedelta(days=30)},
            {"id": "INQ-008", "trial_id": LIBTAYO_TRIAL, "product_name": "Libtayo", "inquiry_source": InquirySource.HCP, "category": InquiryCategory.SAFETY, "status": InquiryStatus.SENT, "question_text": "What immune-related adverse events are most commonly associated with Libtayo?", "response_text": "Immune-mediated reactions include pneumonitis, hepatitis, colitis, endocrinopathies, and skin reactions.", "response_type": ResponseType.STANDARD, "requester_name": "Dr. Catherine Park", "requester_institution": "Dana-Farber Cancer Institute", "requester_country": "US", "assigned_to": "MedInfo Specialist E", "received_date": now - timedelta(days=25), "response_date": now - timedelta(days=22), "turnaround_days": 3, "follow_up_required": True, "adverse_event_reported": True, "created_at": now - timedelta(days=25)},
            {"id": "INQ-009", "trial_id": None, "product_name": "Libtayo", "inquiry_source": InquirySource.CAREGIVER, "category": InquiryCategory.DOSING, "status": InquiryStatus.APPROVED, "question_text": "What is the recommended dose of Libtayo for non-small cell lung cancer?", "response_text": "Libtayo 350 mg administered as an intravenous infusion every 3 weeks.", "response_type": ResponseType.STANDARD, "requester_name": "Maria Gonzalez (caregiver)", "requester_institution": None, "requester_country": "US", "assigned_to": "MedInfo Specialist E", "received_date": now - timedelta(days=15), "response_date": now - timedelta(days=13), "turnaround_days": 2, "follow_up_required": False, "adverse_event_reported": False, "created_at": now - timedelta(days=15)},
            {"id": "INQ-010", "trial_id": DUPIXENT_TRIAL, "product_name": "Dupixent", "inquiry_source": InquirySource.HCP, "category": InquiryCategory.OFF_LABEL, "status": InquiryStatus.IN_REVIEW, "question_text": "Is there clinical evidence supporting Dupixent use in bullous pemphigoid?", "response_text": None, "response_type": None, "requester_name": "Dr. Emily Lawson", "requester_institution": "Stanford Dermatology", "requester_country": "US", "assigned_to": "MedInfo Specialist C", "received_date": now - timedelta(days=10), "response_date": None, "turnaround_days": None, "follow_up_required": False, "adverse_event_reported": False, "created_at": now - timedelta(days=10)},
            {"id": "INQ-011", "trial_id": None, "product_name": "EYLEA HD", "inquiry_source": InquirySource.REGULATORY, "category": InquiryCategory.CLINICAL_TRIAL, "status": InquiryStatus.RECEIVED, "question_text": "Provide summary of ongoing EYLEA HD clinical trials in diabetic retinopathy.", "response_text": None, "response_type": None, "requester_name": "FDA CDER Review Division", "requester_institution": "FDA", "requester_country": "US", "assigned_to": None, "received_date": now - timedelta(days=5), "response_date": None, "turnaround_days": None, "follow_up_required": False, "adverse_event_reported": False, "created_at": now - timedelta(days=5)},
            {"id": "INQ-012", "trial_id": None, "product_name": "Dupixent", "inquiry_source": InquirySource.INTERNAL, "category": InquiryCategory.AVAILABILITY, "status": InquiryStatus.RESPONSE_DRAFTED, "question_text": "When will the Dupixent pre-filled pen be available in the EU market?", "response_text": "Draft: EU launch of Dupixent pre-filled pen is anticipated in Q3 2026, pending regulatory approval.", "response_type": ResponseType.CUSTOM, "requester_name": "Commercial Strategy Team", "requester_institution": "Regeneron", "requester_country": "US", "assigned_to": "MedInfo Specialist D", "received_date": now - timedelta(days=8), "response_date": None, "turnaround_days": None, "follow_up_required": False, "adverse_event_reported": False, "created_at": now - timedelta(days=8)},
        ]

        for inq in inquiries_data:
            self._inquiries[inq["id"]] = MedicalInquiry(**inq)

        # --- 12 Standard Response Documents ---
        standard_responses_data = [
            {"id": "SRD-001", "product_name": "EYLEA HD", "document_type": DocumentType.STANDARD_RESPONSE, "title": "EYLEA HD Dosing and Administration in Wet AMD", "version": "3.1", "content_summary": "Comprehensive dosing guidance for EYLEA HD 8 mg in neovascular AMD including loading phase and maintenance intervals.", "category": InquiryCategory.DOSING, "effective_date": now - timedelta(days=180), "expiry_date": now + timedelta(days=185), "active": True, "usage_count": 87, "author": "Dr. Lisa Park", "reviewer": "Dr. James Chen", "approved_by": "Dr. Michael Adams", "approved_date": now - timedelta(days=182), "created_at": now - timedelta(days=190)},
            {"id": "SRD-002", "product_name": "EYLEA HD", "document_type": DocumentType.SCIENTIFIC_RESPONSE, "title": "EYLEA HD PULSAR Trial Efficacy Summary", "version": "2.0", "content_summary": "Summary of PULSAR trial results: BCVA gains, dosing interval comparisons, and non-inferiority analysis.", "category": InquiryCategory.EFFICACY, "effective_date": now - timedelta(days=150), "expiry_date": now + timedelta(days=215), "active": True, "usage_count": 124, "author": "Dr. Sarah Kim", "reviewer": "Dr. Robert Williams", "approved_by": "Dr. Michael Adams", "approved_date": now - timedelta(days=152), "created_at": now - timedelta(days=160)},
            {"id": "SRD-003", "product_name": "EYLEA HD", "document_type": DocumentType.STANDARD_RESPONSE, "title": "EYLEA HD Storage and Handling", "version": "1.2", "content_summary": "Storage requirements, handling procedures, and stability data for EYLEA HD prefilled syringes.", "category": InquiryCategory.STORAGE, "effective_date": now - timedelta(days=120), "expiry_date": None, "active": True, "usage_count": 45, "author": "PharmD Rachel Green", "reviewer": None, "approved_by": "Dr. Michael Adams", "approved_date": now - timedelta(days=122), "created_at": now - timedelta(days=130)},
            {"id": "SRD-004", "product_name": "Dupixent", "document_type": DocumentType.STANDARD_RESPONSE, "title": "Dupixent Safety Profile in Atopic Dermatitis", "version": "4.2", "content_summary": "Comprehensive safety data from pivotal AD trials including conjunctivitis incidence, injection site reactions, and long-term safety.", "category": InquiryCategory.SAFETY, "effective_date": now - timedelta(days=200), "expiry_date": now + timedelta(days=165), "active": True, "usage_count": 203, "author": "Dr. Angela Martinez", "reviewer": "Dr. David Nakamura", "approved_by": "Dr. Patricia Sullivan", "approved_date": now - timedelta(days=202), "created_at": now - timedelta(days=210)},
            {"id": "SRD-005", "product_name": "Dupixent", "document_type": DocumentType.STANDARD_RESPONSE, "title": "Dupixent Drug Interaction Guidance", "version": "2.1", "content_summary": "Known drug interactions, vaccine co-administration guidance, and CYP substrate considerations for dupilumab.", "category": InquiryCategory.DRUG_INTERACTIONS, "effective_date": now - timedelta(days=100), "expiry_date": now + timedelta(days=265), "active": True, "usage_count": 78, "author": "PharmD Thomas Lee", "reviewer": "Dr. Angela Martinez", "approved_by": "Dr. Patricia Sullivan", "approved_date": now - timedelta(days=102), "created_at": now - timedelta(days=110)},
            {"id": "SRD-006", "product_name": "Dupixent", "document_type": DocumentType.PRODUCT_MONOGRAPH, "title": "Dupixent Full Prescribing Information Summary", "version": "8.0", "content_summary": "Complete prescribing information summary for all approved Dupixent indications.", "category": InquiryCategory.EFFICACY, "effective_date": now - timedelta(days=90), "expiry_date": now + timedelta(days=275), "active": True, "usage_count": 312, "author": "Regulatory Affairs Team", "reviewer": "Dr. Patricia Sullivan", "approved_by": "VP Medical Affairs", "approved_date": now - timedelta(days=92), "created_at": now - timedelta(days=100)},
            {"id": "SRD-007", "product_name": "Libtayo", "document_type": DocumentType.STANDARD_RESPONSE, "title": "Libtayo Efficacy in Advanced CSCC", "version": "3.0", "content_summary": "Overall response rate, duration of response, and survival data for cemiplimab in cutaneous squamous cell carcinoma.", "category": InquiryCategory.EFFICACY, "effective_date": now - timedelta(days=140), "expiry_date": now + timedelta(days=225), "active": True, "usage_count": 156, "author": "Dr. Catherine Liu", "reviewer": "Dr. Andrew Foster", "approved_by": "Dr. Gregory Harris", "approved_date": now - timedelta(days=142), "created_at": now - timedelta(days=150)},
            {"id": "SRD-008", "product_name": "Libtayo", "document_type": DocumentType.STANDARD_RESPONSE, "title": "Libtayo Immune-Related Adverse Event Management", "version": "2.3", "content_summary": "Identification, grading, and management of immune-mediated adverse reactions with Libtayo.", "category": InquiryCategory.SAFETY, "effective_date": now - timedelta(days=110), "expiry_date": now + timedelta(days=255), "active": True, "usage_count": 189, "author": "Dr. Natalie Wong", "reviewer": "Dr. Catherine Liu", "approved_by": "Dr. Gregory Harris", "approved_date": now - timedelta(days=112), "created_at": now - timedelta(days=120)},
            {"id": "SRD-009", "product_name": "Libtayo", "document_type": DocumentType.SCIENTIFIC_RESPONSE, "title": "Libtayo Mechanism of Action and PD-1 Pathway", "version": "1.5", "content_summary": "Scientific overview of cemiplimab mechanism, PD-1 pathway blockade, and immune activation in oncology.", "category": InquiryCategory.EFFICACY, "effective_date": now - timedelta(days=80), "expiry_date": None, "active": True, "usage_count": 67, "author": "Dr. Maria Santos", "reviewer": "Dr. Andrew Foster", "approved_by": "Dr. Gregory Harris", "approved_date": now - timedelta(days=82), "created_at": now - timedelta(days=90)},
            {"id": "SRD-010", "product_name": "EYLEA HD", "document_type": DocumentType.FIELD_ALERT, "title": "EYLEA HD Cold Chain Requirements Update", "version": "1.0", "content_summary": "Updated cold chain requirements and temperature excursion handling procedures for EYLEA HD distribution.", "category": InquiryCategory.STORAGE, "effective_date": now - timedelta(days=30), "expiry_date": now + timedelta(days=335), "active": True, "usage_count": 23, "author": "Supply Chain Medical Affairs", "reviewer": "PharmD Rachel Green", "approved_by": "Dr. Michael Adams", "approved_date": now - timedelta(days=32), "created_at": now - timedelta(days=35)},
            {"id": "SRD-011", "product_name": "Dupixent", "document_type": DocumentType.FAQ, "title": "Dupixent Patient FAQ Compilation", "version": "5.0", "content_summary": "Compiled frequently asked questions from patients regarding Dupixent self-injection technique, side effects, and support programs.", "category": InquiryCategory.SAFETY, "effective_date": now - timedelta(days=60), "expiry_date": now + timedelta(days=305), "active": True, "usage_count": 445, "author": "Patient Education Team", "reviewer": "Dr. Angela Martinez", "approved_by": "Dr. Patricia Sullivan", "approved_date": now - timedelta(days=62), "created_at": now - timedelta(days=70)},
            {"id": "SRD-012", "product_name": "Libtayo", "document_type": DocumentType.STANDARD_RESPONSE, "title": "Libtayo Dosing in NSCLC", "version": "2.0", "content_summary": "Dosing recommendations for Libtayo monotherapy in first-line NSCLC with PD-L1 expression >= 50%.", "category": InquiryCategory.DOSING, "effective_date": now - timedelta(days=70), "expiry_date": now + timedelta(days=295), "active": False, "usage_count": 98, "author": "Dr. Catherine Liu", "reviewer": "Dr. Natalie Wong", "approved_by": "Dr. Gregory Harris", "approved_date": now - timedelta(days=72), "created_at": now - timedelta(days=80)},
        ]

        for srd in standard_responses_data:
            self._standard_responses[srd["id"]] = StandardResponseDoc(**srd)

        # --- 12 Product FAQs ---
        faqs_data = [
            {"id": "FAQ-001", "product_name": "EYLEA HD", "category": InquiryCategory.DOSING, "question": "What is the recommended dosing schedule for EYLEA HD?", "answer": "EYLEA HD 8 mg is administered by intravitreal injection monthly for the first 3-4 months, then every 8-16 weeks.", "version": "2.0", "active": True, "view_count": 1250, "helpful_count": 980, "last_updated": now - timedelta(days=30), "author": "Medical Information Team"},
            {"id": "FAQ-002", "product_name": "EYLEA HD", "category": InquiryCategory.SAFETY, "question": "What are the most common side effects of EYLEA HD?", "answer": "Common side effects include conjunctival hemorrhage, eye pain, cataract, vitreous floaters, and increased intraocular pressure.", "version": "1.5", "active": True, "view_count": 890, "helpful_count": 720, "last_updated": now - timedelta(days=45), "author": "Medical Information Team"},
            {"id": "FAQ-003", "product_name": "EYLEA HD", "category": InquiryCategory.STORAGE, "question": "How should EYLEA HD be stored?", "answer": "Store refrigerated at 2-8 degrees C in the original carton to protect from light. Do not freeze.", "version": "1.0", "active": True, "view_count": 560, "helpful_count": 490, "last_updated": now - timedelta(days=60), "author": "Pharmacy Affairs"},
            {"id": "FAQ-004", "product_name": "Dupixent", "category": InquiryCategory.DOSING, "question": "What is the dosing regimen for Dupixent in atopic dermatitis?", "answer": "For adults: 600 mg loading dose (two 300 mg injections) followed by 300 mg every other week.", "version": "3.0", "active": True, "view_count": 2340, "helpful_count": 1890, "last_updated": now - timedelta(days=20), "author": "Medical Information Team"},
            {"id": "FAQ-005", "product_name": "Dupixent", "category": InquiryCategory.SAFETY, "question": "Can Dupixent cause eye problems?", "answer": "Conjunctivitis and keratitis have been reported. Patients should report new or worsening eye symptoms to their healthcare provider.", "version": "2.0", "active": True, "view_count": 1780, "helpful_count": 1420, "last_updated": now - timedelta(days=25), "author": "Medical Information Team"},
            {"id": "FAQ-006", "product_name": "Dupixent", "category": InquiryCategory.DRUG_INTERACTIONS, "question": "Can I get vaccines while taking Dupixent?", "answer": "Avoid live vaccines. Inactivated or non-live vaccines may be administered during Dupixent treatment.", "version": "1.5", "active": True, "view_count": 980, "helpful_count": 810, "last_updated": now - timedelta(days=35), "author": "Pharmacy Affairs"},
            {"id": "FAQ-007", "product_name": "Dupixent", "category": InquiryCategory.AVAILABILITY, "question": "Is Dupixent available in a pre-filled pen?", "answer": "Yes, Dupixent is available as a pre-filled syringe and pre-filled pen for subcutaneous injection.", "version": "2.0", "active": True, "view_count": 1120, "helpful_count": 950, "last_updated": now - timedelta(days=15), "author": "Medical Information Team"},
            {"id": "FAQ-008", "product_name": "Libtayo", "category": InquiryCategory.DOSING, "question": "What is the recommended dose of Libtayo?", "answer": "Libtayo 350 mg administered as an intravenous infusion over 30 minutes every 3 weeks.", "version": "2.0", "active": True, "view_count": 670, "helpful_count": 540, "last_updated": now - timedelta(days=40), "author": "Medical Information Team"},
            {"id": "FAQ-009", "product_name": "Libtayo", "category": InquiryCategory.SAFETY, "question": "What immune-related side effects can Libtayo cause?", "answer": "Immune-mediated adverse reactions including pneumonitis, colitis, hepatitis, endocrinopathies, nephritis, and skin reactions.", "version": "2.5", "active": True, "view_count": 890, "helpful_count": 720, "last_updated": now - timedelta(days=28), "author": "Medical Information Team"},
            {"id": "FAQ-010", "product_name": "Libtayo", "category": InquiryCategory.EFFICACY, "question": "What cancers is Libtayo approved to treat?", "answer": "Libtayo is approved for advanced cutaneous squamous cell carcinoma, basal cell carcinoma, and non-small cell lung cancer.", "version": "3.0", "active": True, "view_count": 1450, "helpful_count": 1200, "last_updated": now - timedelta(days=10), "author": "Medical Information Team"},
            {"id": "FAQ-011", "product_name": "EYLEA HD", "category": InquiryCategory.EFFICACY, "question": "What conditions is EYLEA HD approved to treat?", "answer": "EYLEA HD is approved for wet age-related macular degeneration, diabetic macular edema, and diabetic retinopathy.", "version": "1.0", "active": True, "view_count": 780, "helpful_count": 650, "last_updated": now - timedelta(days=50), "author": "Medical Information Team"},
            {"id": "FAQ-012", "product_name": "Dupixent", "category": InquiryCategory.OFF_LABEL, "question": "Is Dupixent used for conditions other than atopic dermatitis?", "answer": "Dupixent is FDA-approved for multiple indications including asthma, CRSwNP, eosinophilic esophagitis, COPD, and prurigo nodularis.", "version": "4.0", "active": False, "view_count": 340, "helpful_count": 280, "last_updated": now - timedelta(days=90), "author": "Medical Information Team"},
        ]

        for faq in faqs_data:
            self._faqs[faq["id"]] = ProductFAQ(**faq)

        # --- 12 Field Medical Insights ---
        insights_data = [
            {"id": "FMI-001", "product_name": "EYLEA HD", "trial_id": EYLEA_TRIAL, "insight_type": "Unmet Need", "description": "Retinal specialists express strong interest in extended dosing intervals to reduce treatment burden for wet AMD patients.", "therapeutic_area": "Ophthalmology", "region": "US Northeast", "source": "Advisory Board Meeting", "impact_assessment": "High - supports EYLEA HD value proposition", "action_required": True, "action_taken": "Incorporated into MSL talking points", "reported_by": "MSL Dr. Karen Lee", "reported_date": now - timedelta(days=90), "reviewed_by": "Regional Medical Director", "created_at": now - timedelta(days=90)},
            {"id": "FMI-002", "product_name": "EYLEA HD", "trial_id": EYLEA_TRIAL, "insight_type": "Competitive Intelligence", "description": "Competitor anti-VEGF agents gaining traction with retina specialists in academic centers.", "therapeutic_area": "Ophthalmology", "region": "US West", "source": "KOL Meeting", "impact_assessment": "Medium - need proactive engagement", "action_required": True, "action_taken": "Scheduled targeted MSL outreach", "reported_by": "MSL Dr. David Park", "reported_date": now - timedelta(days=75), "reviewed_by": "Regional Medical Director", "created_at": now - timedelta(days=75)},
            {"id": "FMI-003", "product_name": "EYLEA HD", "trial_id": None, "insight_type": "Clinical Practice", "description": "Community ophthalmologists report challenges with insurance coverage for EYLEA HD transitions from standard EYLEA.", "therapeutic_area": "Ophthalmology", "region": "US Southeast", "source": "Field Visit", "impact_assessment": "High - affects adoption", "action_required": True, "action_taken": None, "reported_by": "MSL Dr. Jennifer Walsh", "reported_date": now - timedelta(days=60), "reviewed_by": None, "created_at": now - timedelta(days=60)},
            {"id": "FMI-004", "product_name": "Dupixent", "trial_id": DUPIXENT_TRIAL, "insight_type": "Clinical Practice", "description": "Dermatologists increasingly using Dupixent as first-line biologic for moderate-to-severe AD in adults.", "therapeutic_area": "Dermatology", "region": "US Midwest", "source": "Medical Conference", "impact_assessment": "Positive - aligns with treatment guidelines", "action_required": False, "action_taken": None, "reported_by": "MSL Dr. Michael Brown", "reported_date": now - timedelta(days=55), "reviewed_by": "Medical Director Immunology", "created_at": now - timedelta(days=55)},
            {"id": "FMI-005", "product_name": "Dupixent", "trial_id": DUPIXENT_TRIAL, "insight_type": "Safety Signal", "description": "Three KOLs independently reported observing facial erythema in pediatric AD patients on Dupixent.", "therapeutic_area": "Dermatology", "region": "US Northeast", "source": "KOL Interaction", "impact_assessment": "Requires pharmacovigilance follow-up", "action_required": True, "action_taken": "Forwarded to Drug Safety for evaluation", "reported_by": "MSL Dr. Amy Richardson", "reported_date": now - timedelta(days=45), "reviewed_by": "Medical Director Immunology", "created_at": now - timedelta(days=45)},
            {"id": "FMI-006", "product_name": "Dupixent", "trial_id": None, "insight_type": "Unmet Need", "description": "Allergists seeking data on Dupixent combination with allergen immunotherapy in comorbid asthma-AD patients.", "therapeutic_area": "Immunology", "region": "US South", "source": "Advisory Board", "impact_assessment": "Medium - potential research opportunity", "action_required": False, "action_taken": None, "reported_by": "MSL Dr. Thomas Green", "reported_date": now - timedelta(days=40), "reviewed_by": None, "created_at": now - timedelta(days=40)},
            {"id": "FMI-007", "product_name": "Libtayo", "trial_id": LIBTAYO_TRIAL, "insight_type": "Clinical Practice", "description": "Oncologists report favorable real-world outcomes with Libtayo in elderly CSCC patients ineligible for surgery.", "therapeutic_area": "Oncology", "region": "US West", "source": "Congress Symposium", "impact_assessment": "Positive - supports real-world evidence generation", "action_required": False, "action_taken": None, "reported_by": "MSL Dr. Sandra Martinez", "reported_date": now - timedelta(days=35), "reviewed_by": "Regional Medical Director Oncology", "created_at": now - timedelta(days=35)},
            {"id": "FMI-008", "product_name": "Libtayo", "trial_id": LIBTAYO_TRIAL, "insight_type": "Competitive Intelligence", "description": "Community oncologists comparing Libtayo with pembrolizumab for first-line NSCLC; need differentiation data.", "therapeutic_area": "Oncology", "region": "US Midwest", "source": "Tumor Board Observation", "impact_assessment": "High - competitive threat", "action_required": True, "action_taken": "Developed comparative data slide deck", "reported_by": "MSL Dr. Peter Chen", "reported_date": now - timedelta(days=28), "reviewed_by": "Medical Director Oncology", "created_at": now - timedelta(days=28)},
            {"id": "FMI-009", "product_name": "Libtayo", "trial_id": None, "insight_type": "Unmet Need", "description": "Dermatologic oncologists requesting data on Libtayo in adjuvant setting for high-risk resected CSCC.", "therapeutic_area": "Oncology", "region": "EU", "source": "ESMO Congress", "impact_assessment": "High - potential indication expansion", "action_required": True, "action_taken": None, "reported_by": "MSL Dr. Hans Mueller", "reported_date": now - timedelta(days=20), "reviewed_by": None, "created_at": now - timedelta(days=20)},
            {"id": "FMI-010", "product_name": "EYLEA HD", "trial_id": EYLEA_TRIAL, "insight_type": "Educational Gap", "description": "Some retina fellows unclear on EYLEA HD vs standard EYLEA distinction; need targeted fellowship education.", "therapeutic_area": "Ophthalmology", "region": "US Northeast", "source": "Fellowship Program Visit", "impact_assessment": "Medium - long-term KOL development", "action_required": True, "action_taken": "Developed fellowship education program", "reported_by": "MSL Dr. Karen Lee", "reported_date": now - timedelta(days=15), "reviewed_by": "Regional Medical Director", "created_at": now - timedelta(days=15)},
            {"id": "FMI-011", "product_name": "Dupixent", "trial_id": None, "insight_type": "Market Access", "description": "Several payer medical directors questioned comparative effectiveness data for Dupixent vs JAK inhibitors in AD.", "therapeutic_area": "Dermatology", "region": "US National", "source": "Payer Advisory Board", "impact_assessment": "High - affects formulary positioning", "action_required": True, "action_taken": "Preparing HEOR evidence package", "reported_by": "MSL Dr. Amy Richardson", "reported_date": now - timedelta(days=10), "reviewed_by": "VP Medical Affairs", "created_at": now - timedelta(days=10)},
            {"id": "FMI-012", "product_name": "Libtayo", "trial_id": LIBTAYO_TRIAL, "insight_type": "Safety Signal", "description": "Two investigators reported delayed-onset immune-mediated arthritis at 12+ months of Libtayo treatment.", "therapeutic_area": "Oncology", "region": "US Southeast", "source": "Investigator Meeting", "impact_assessment": "Requires safety review", "action_required": True, "action_taken": "Reported to pharmacovigilance", "reported_by": "MSL Dr. Sandra Martinez", "reported_date": now - timedelta(days=5), "reviewed_by": "Medical Director Oncology", "created_at": now - timedelta(days=5)},
        ]

        for ins in insights_data:
            self._insights[ins["id"]] = FieldMedicalInsight(**ins)

        # --- 12 Scientific Communications ---
        communications_data = [
            {"id": "SCI-001", "product_name": "EYLEA HD", "communication_type": "Medical Letter", "title": "EYLEA HD PULSAR 48-Week Efficacy Update", "audience": "Retinal Specialists", "channel": "Email", "content_summary": "48-week efficacy data from PULSAR trial showing sustained BCVA gains with EYLEA HD 8 mg.", "status": "sent", "scheduled_date": now - timedelta(days=60), "sent_date": now - timedelta(days=60), "recipients_count": 2500, "open_rate_pct": 42.5, "author": "Medical Communications Team", "approved_by": "Dr. Michael Adams", "created_at": now - timedelta(days=65)},
            {"id": "SCI-002", "product_name": "EYLEA HD", "communication_type": "Congress Highlights", "title": "AAO 2025 EYLEA HD Data Highlights", "audience": "Ophthalmologists", "channel": "Web Portal", "content_summary": "Key data presentations from AAO 2025 featuring EYLEA HD real-world evidence and new indication data.", "status": "sent", "scheduled_date": now - timedelta(days=45), "sent_date": now - timedelta(days=45), "recipients_count": 5200, "open_rate_pct": 38.7, "author": "Medical Communications Team", "approved_by": "Dr. Michael Adams", "created_at": now - timedelta(days=50)},
            {"id": "SCI-003", "product_name": "Dupixent", "communication_type": "Dear HCP Letter", "title": "Dupixent New Indication: COPD Approval", "audience": "Pulmonologists and Allergists", "channel": "Direct Mail", "content_summary": "Notification to HCPs regarding FDA approval of Dupixent for COPD with type 2 inflammation.", "status": "sent", "scheduled_date": now - timedelta(days=40), "sent_date": now - timedelta(days=40), "recipients_count": 8900, "open_rate_pct": 55.2, "author": "Regulatory Communications", "approved_by": "Dr. Patricia Sullivan", "created_at": now - timedelta(days=45)},
            {"id": "SCI-004", "product_name": "Dupixent", "communication_type": "Slide Deck", "title": "Dupixent Mechanism of Action and Clinical Evidence", "audience": "Healthcare Professionals", "channel": "MSL Presentation", "content_summary": "Comprehensive slide deck covering IL-4/IL-13 pathway, clinical trial data across indications.", "status": "sent", "scheduled_date": now - timedelta(days=30), "sent_date": now - timedelta(days=30), "recipients_count": 450, "open_rate_pct": None, "author": "Medical Affairs", "approved_by": "Dr. Patricia Sullivan", "created_at": now - timedelta(days=35)},
            {"id": "SCI-005", "product_name": "Dupixent", "communication_type": "Newsletter", "title": "Dupixent Q4 2025 Medical Update", "audience": "Dermatologists", "channel": "Email", "content_summary": "Quarterly update with new publications, congress highlights, and real-world evidence for Dupixent.", "status": "sent", "scheduled_date": now - timedelta(days=20), "sent_date": now - timedelta(days=20), "recipients_count": 6300, "open_rate_pct": 33.8, "author": "Medical Communications Team", "approved_by": "Dr. Patricia Sullivan", "created_at": now - timedelta(days=25)},
            {"id": "SCI-006", "product_name": "Libtayo", "communication_type": "Medical Letter", "title": "Libtayo Updated Survival Data in Advanced CSCC", "audience": "Oncologists", "channel": "Email", "content_summary": "Updated overall survival and duration of response data from long-term follow-up of CSCC pivotal study.", "status": "sent", "scheduled_date": now - timedelta(days=50), "sent_date": now - timedelta(days=50), "recipients_count": 3200, "open_rate_pct": 41.3, "author": "Medical Communications Team", "approved_by": "Dr. Gregory Harris", "created_at": now - timedelta(days=55)},
            {"id": "SCI-007", "product_name": "Libtayo", "communication_type": "Congress Highlights", "title": "ASCO 2025 Libtayo Immuno-Oncology Updates", "audience": "Oncology Community", "channel": "Web Portal", "content_summary": "Summary of Libtayo-related presentations at ASCO 2025 including combination therapy data.", "status": "sent", "scheduled_date": now - timedelta(days=35), "sent_date": now - timedelta(days=35), "recipients_count": 7800, "open_rate_pct": 44.1, "author": "Medical Communications Team", "approved_by": "Dr. Gregory Harris", "created_at": now - timedelta(days=40)},
            {"id": "SCI-008", "product_name": "Libtayo", "communication_type": "Safety Communication", "title": "Libtayo irAE Management Guidelines Update", "audience": "Oncologists and Pharmacists", "channel": "Email", "content_summary": "Updated immune-related adverse event management guidelines with new grading and treatment algorithms.", "status": "sent", "scheduled_date": now - timedelta(days=25), "sent_date": now - timedelta(days=25), "recipients_count": 4500, "open_rate_pct": 52.6, "author": "Drug Safety Communications", "approved_by": "Dr. Gregory Harris", "created_at": now - timedelta(days=30)},
            {"id": "SCI-009", "product_name": "EYLEA HD", "communication_type": "Webinar Invitation", "title": "EYLEA HD in Clinical Practice: Expert Panel Discussion", "audience": "Retinal Specialists", "channel": "Email", "content_summary": "Invitation to live webinar featuring expert panel discussion on EYLEA HD clinical experience.", "status": "approved", "scheduled_date": now + timedelta(days=14), "sent_date": None, "recipients_count": 0, "open_rate_pct": None, "author": "Medical Education Team", "approved_by": "Dr. Michael Adams", "created_at": now - timedelta(days=10)},
            {"id": "SCI-010", "product_name": "Dupixent", "communication_type": "Newsletter", "title": "Dupixent Q1 2026 Pipeline Update", "audience": "Allergists and Immunologists", "channel": "Email", "content_summary": "Upcoming Dupixent data presentations and new trial enrollment opportunities.", "status": "draft", "scheduled_date": now + timedelta(days=30), "sent_date": None, "recipients_count": 0, "open_rate_pct": None, "author": "Medical Communications Team", "approved_by": None, "created_at": now - timedelta(days=5)},
            {"id": "SCI-011", "product_name": "Libtayo", "communication_type": "Medical Letter", "title": "Libtayo Cervical Cancer Data Update", "audience": "Gynecologic Oncologists", "channel": "Direct Mail", "content_summary": "Efficacy and safety data from Libtayo trials in advanced cervical cancer.", "status": "draft", "scheduled_date": now + timedelta(days=21), "sent_date": None, "recipients_count": 0, "open_rate_pct": None, "author": "Medical Affairs Oncology", "approved_by": None, "created_at": now - timedelta(days=8)},
            {"id": "SCI-012", "product_name": "EYLEA HD", "communication_type": "Slide Deck", "title": "EYLEA HD vs Anti-VEGF Competitors: Scientific Differentiation", "audience": "MSL Team", "channel": "Internal Training", "content_summary": "Internal MSL training deck on scientific differentiation of EYLEA HD from competing anti-VEGF agents.", "status": "approved", "scheduled_date": now + timedelta(days=7), "sent_date": None, "recipients_count": 0, "open_rate_pct": None, "author": "Medical Strategy Team", "approved_by": "VP Medical Affairs", "created_at": now - timedelta(days=12)},
        ]

        for comm in communications_data:
            self._communications[comm["id"]] = ScientificCommunication(**comm)

    # ------------------------------------------------------------------
    # Medical Inquiry CRUD
    # ------------------------------------------------------------------

    def list_inquiries(
        self,
        *,
        trial_id: str | None = None,
        product_name: str | None = None,
    ) -> list[MedicalInquiry]:
        """List medical inquiries with optional filters."""
        with self._lock:
            result = list(self._inquiries.values())

        if trial_id is not None:
            result = [i for i in result if i.trial_id == trial_id]
        if product_name is not None:
            result = [i for i in result if i.product_name == product_name]

        return sorted(result, key=lambda i: i.received_date, reverse=True)

    def get_inquiry(self, inquiry_id: str) -> MedicalInquiry | None:
        """Get a single inquiry by ID."""
        with self._lock:
            return self._inquiries.get(inquiry_id)

    def create_inquiry(self, payload: MedicalInquiryCreate) -> MedicalInquiry:
        """Create a new medical inquiry."""
        now = datetime.now(timezone.utc)
        inquiry_id = f"INQ-{uuid4().hex[:8].upper()}"
        inquiry = MedicalInquiry(
            id=inquiry_id,
            trial_id=payload.trial_id,
            product_name=payload.product_name,
            inquiry_source=payload.inquiry_source,
            category=payload.category,
            status=InquiryStatus.RECEIVED,
            question_text=payload.question_text,
            requester_name=payload.requester_name,
            requester_institution=payload.requester_institution,
            requester_country=payload.requester_country,
            received_date=now,
            created_at=now,
        )
        with self._lock:
            self._inquiries[inquiry_id] = inquiry
        logger.info("Created medical inquiry %s for %s", inquiry_id, payload.product_name)
        return inquiry

    def update_inquiry(
        self, inquiry_id: str, payload: MedicalInquiryUpdate
    ) -> MedicalInquiry | None:
        """Update an existing medical inquiry."""
        with self._lock:
            existing = self._inquiries.get(inquiry_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = MedicalInquiry(**data)
            self._inquiries[inquiry_id] = updated
        return updated

    def delete_inquiry(self, inquiry_id: str) -> bool:
        """Delete an inquiry. Returns True if deleted."""
        with self._lock:
            if inquiry_id in self._inquiries:
                del self._inquiries[inquiry_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Standard Response Document CRUD
    # ------------------------------------------------------------------

    def list_standard_responses(
        self,
        *,
        trial_id: str | None = None,
        product_name: str | None = None,
    ) -> list[StandardResponseDoc]:
        """List standard response documents with optional filters."""
        with self._lock:
            result = list(self._standard_responses.values())

        if product_name is not None:
            result = [r for r in result if r.product_name == product_name]

        return sorted(result, key=lambda r: r.id)

    def get_standard_response(self, doc_id: str) -> StandardResponseDoc | None:
        """Get a single standard response document by ID."""
        with self._lock:
            return self._standard_responses.get(doc_id)

    def create_standard_response(self, payload: StandardResponseDocCreate) -> StandardResponseDoc:
        """Create a new standard response document."""
        now = datetime.now(timezone.utc)
        doc_id = f"SRD-{uuid4().hex[:8].upper()}"
        doc = StandardResponseDoc(
            id=doc_id,
            product_name=payload.product_name,
            document_type=payload.document_type,
            title=payload.title,
            version=payload.version,
            content_summary=payload.content_summary,
            category=payload.category,
            effective_date=payload.effective_date,
            author=payload.author,
            created_at=now,
        )
        with self._lock:
            self._standard_responses[doc_id] = doc
        logger.info("Created standard response %s: %s", doc_id, payload.title)
        return doc

    def update_standard_response(
        self, doc_id: str, payload: StandardResponseDocUpdate
    ) -> StandardResponseDoc | None:
        """Update a standard response document."""
        with self._lock:
            existing = self._standard_responses.get(doc_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = StandardResponseDoc(**data)
            self._standard_responses[doc_id] = updated
        return updated

    def delete_standard_response(self, doc_id: str) -> bool:
        """Delete a standard response document. Returns True if deleted."""
        with self._lock:
            if doc_id in self._standard_responses:
                del self._standard_responses[doc_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Product FAQ CRUD
    # ------------------------------------------------------------------

    def list_faqs(
        self,
        *,
        trial_id: str | None = None,
        product_name: str | None = None,
    ) -> list[ProductFAQ]:
        """List product FAQs with optional filters."""
        with self._lock:
            result = list(self._faqs.values())

        if product_name is not None:
            result = [f for f in result if f.product_name == product_name]

        return sorted(result, key=lambda f: f.id)

    def get_faq(self, faq_id: str) -> ProductFAQ | None:
        """Get a single FAQ by ID."""
        with self._lock:
            return self._faqs.get(faq_id)

    def create_faq(self, payload: ProductFAQCreate) -> ProductFAQ:
        """Create a new product FAQ."""
        now = datetime.now(timezone.utc)
        faq_id = f"FAQ-{uuid4().hex[:8].upper()}"
        faq = ProductFAQ(
            id=faq_id,
            product_name=payload.product_name,
            category=payload.category,
            question=payload.question,
            answer=payload.answer,
            author=payload.author,
            last_updated=now,
        )
        with self._lock:
            self._faqs[faq_id] = faq
        logger.info("Created FAQ %s for %s", faq_id, payload.product_name)
        return faq

    def update_faq(
        self, faq_id: str, payload: ProductFAQUpdate
    ) -> ProductFAQ | None:
        """Update a product FAQ."""
        with self._lock:
            existing = self._faqs.get(faq_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            data["last_updated"] = datetime.now(timezone.utc)
            updated = ProductFAQ(**data)
            self._faqs[faq_id] = updated
        return updated

    def delete_faq(self, faq_id: str) -> bool:
        """Delete a FAQ. Returns True if deleted."""
        with self._lock:
            if faq_id in self._faqs:
                del self._faqs[faq_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Field Medical Insight CRUD
    # ------------------------------------------------------------------

    def list_insights(
        self,
        *,
        trial_id: str | None = None,
        product_name: str | None = None,
    ) -> list[FieldMedicalInsight]:
        """List field medical insights with optional filters."""
        with self._lock:
            result = list(self._insights.values())

        if trial_id is not None:
            result = [i for i in result if i.trial_id == trial_id]
        if product_name is not None:
            result = [i for i in result if i.product_name == product_name]

        return sorted(result, key=lambda i: i.reported_date, reverse=True)

    def get_insight(self, insight_id: str) -> FieldMedicalInsight | None:
        """Get a single field medical insight by ID."""
        with self._lock:
            return self._insights.get(insight_id)

    def create_insight(self, payload: FieldMedicalInsightCreate) -> FieldMedicalInsight:
        """Create a new field medical insight."""
        now = datetime.now(timezone.utc)
        insight_id = f"FMI-{uuid4().hex[:8].upper()}"
        insight = FieldMedicalInsight(
            id=insight_id,
            product_name=payload.product_name,
            trial_id=payload.trial_id,
            insight_type=payload.insight_type,
            description=payload.description,
            therapeutic_area=payload.therapeutic_area,
            region=payload.region,
            source=payload.source,
            reported_by=payload.reported_by,
            reported_date=now,
            created_at=now,
        )
        with self._lock:
            self._insights[insight_id] = insight
        logger.info("Created field medical insight %s for %s", insight_id, payload.product_name)
        return insight

    def update_insight(
        self, insight_id: str, payload: FieldMedicalInsightUpdate
    ) -> FieldMedicalInsight | None:
        """Update a field medical insight."""
        with self._lock:
            existing = self._insights.get(insight_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = FieldMedicalInsight(**data)
            self._insights[insight_id] = updated
        return updated

    def delete_insight(self, insight_id: str) -> bool:
        """Delete a field medical insight. Returns True if deleted."""
        with self._lock:
            if insight_id in self._insights:
                del self._insights[insight_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Scientific Communication CRUD
    # ------------------------------------------------------------------

    def list_communications(
        self,
        *,
        trial_id: str | None = None,
        product_name: str | None = None,
    ) -> list[ScientificCommunication]:
        """List scientific communications with optional filters."""
        with self._lock:
            result = list(self._communications.values())

        if product_name is not None:
            result = [c for c in result if c.product_name == product_name]

        return sorted(result, key=lambda c: c.id)

    def get_communication(self, comm_id: str) -> ScientificCommunication | None:
        """Get a single scientific communication by ID."""
        with self._lock:
            return self._communications.get(comm_id)

    def create_communication(self, payload: ScientificCommunicationCreate) -> ScientificCommunication:
        """Create a new scientific communication."""
        now = datetime.now(timezone.utc)
        comm_id = f"SCI-{uuid4().hex[:8].upper()}"
        comm = ScientificCommunication(
            id=comm_id,
            product_name=payload.product_name,
            communication_type=payload.communication_type,
            title=payload.title,
            audience=payload.audience,
            channel=payload.channel,
            content_summary=payload.content_summary,
            author=payload.author,
            created_at=now,
        )
        with self._lock:
            self._communications[comm_id] = comm
        logger.info("Created scientific communication %s: %s", comm_id, payload.title)
        return comm

    def update_communication(
        self, comm_id: str, payload: ScientificCommunicationUpdate
    ) -> ScientificCommunication | None:
        """Update a scientific communication."""
        with self._lock:
            existing = self._communications.get(comm_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ScientificCommunication(**data)
            self._communications[comm_id] = updated
        return updated

    def delete_communication(self, comm_id: str) -> bool:
        """Delete a scientific communication. Returns True if deleted."""
        with self._lock:
            if comm_id in self._communications:
                del self._communications[comm_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> MedicalInformationMetrics:
        """Compute aggregated medical information metrics."""
        with self._lock:
            inquiries = list(self._inquiries.values())
            responses = list(self._standard_responses.values())
            faqs = list(self._faqs.values())
            insights = list(self._insights.values())
            communications = list(self._communications.values())

        # Inquiries by source
        inquiries_by_source: dict[str, int] = {}
        for inq in inquiries:
            key = inq.inquiry_source.value
            inquiries_by_source[key] = inquiries_by_source.get(key, 0) + 1

        # Inquiries by category
        inquiries_by_category: dict[str, int] = {}
        for inq in inquiries:
            key = inq.category.value
            inquiries_by_category[key] = inquiries_by_category.get(key, 0) + 1

        # Inquiries by status
        inquiries_by_status: dict[str, int] = {}
        for inq in inquiries:
            key = inq.status.value
            inquiries_by_status[key] = inquiries_by_status.get(key, 0) + 1

        # Average turnaround
        turnaround_values = [inq.turnaround_days for inq in inquiries if inq.turnaround_days is not None]
        avg_turnaround = (
            round(sum(turnaround_values) / len(turnaround_values), 1)
            if turnaround_values
            else 0.0
        )

        return MedicalInformationMetrics(
            total_inquiries=len(inquiries),
            inquiries_by_source=inquiries_by_source,
            inquiries_by_category=inquiries_by_category,
            inquiries_by_status=inquiries_by_status,
            avg_turnaround_days=avg_turnaround,
            total_standard_responses=len(responses),
            active_standard_responses=sum(1 for r in responses if r.active),
            total_faqs=len(faqs),
            active_faqs=sum(1 for f in faqs if f.active),
            total_insights=len(insights),
            actionable_insights=sum(1 for i in insights if i.action_required),
            total_communications=len(communications),
            communications_sent=sum(1 for c in communications if c.status == "sent"),
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: MedicalInformationService | None = None
_instance_lock = threading.Lock()


def get_medical_information_service() -> MedicalInformationService:
    """Return the singleton MedicalInformationService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = MedicalInformationService()
    return _instance


def reset_medical_information_service() -> MedicalInformationService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = MedicalInformationService()
    return _instance
