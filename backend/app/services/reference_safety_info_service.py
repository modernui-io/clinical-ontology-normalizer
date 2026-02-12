"""Reference Safety Information Management Service (RSI-MGT).

Manages reference safety information operations including safety document
lifecycle, Investigator's Brochure section management, safety updates and
labeling changes, safety narrative authoring, RSI line item tracking,
and operational metrics.

Usage:
    from app.services.reference_safety_info_service import (
        get_reference_safety_info_service,
    )

    svc = get_reference_safety_info_service()
    documents = svc.list_safety_documents()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.reference_safety_info import (
    DocumentCategory,
    IBSection,
    IBSectionCreate,
    IBSectionUpdate,
    NarrativeType,
    RSILineItem,
    RSILineItemCreate,
    RSILineItemUpdate,
    RSIMetrics,
    ReviewStatus,
    SafetyDocument,
    SafetyDocumentCreate,
    SafetyDocumentUpdate,
    SafetyNarrative,
    SafetyNarrativeCreate,
    SafetyNarrativeUpdate,
    SafetyUpdate,
    SafetyUpdateCreate,
    SafetyUpdateModify,
    SectionType,
    UpdateType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class ReferenceSafetyInfoService:
    """In-memory Reference Safety Information Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._safety_documents: dict[str, SafetyDocument] = {}
        self._ib_sections: dict[str, IBSection] = {}
        self._safety_updates: dict[str, SafetyUpdate] = {}
        self._safety_narratives: dict[str, SafetyNarrative] = {}
        self._rsi_line_items: dict[str, RSILineItem] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic RSI data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Safety Documents ---
        documents_data = [
            {"id": "SDOC-001", "trial_id": EYLEA_TRIAL, "product_name": "EYLEA HD", "category": DocumentCategory.INVESTIGATORS_BROCHURE, "title": "EYLEA HD Investigator's Brochure v14", "version": "14.0", "status": ReviewStatus.PUBLISHED, "effective_date": now - timedelta(days=180), "expiry_date": now + timedelta(days=185), "total_pages": 342, "data_lock_date": now - timedelta(days=200), "reporting_period_start": now - timedelta(days=545), "reporting_period_end": now - timedelta(days=180), "author": "Dr. Sarah Mitchell", "medical_reviewer": "Dr. James Chen", "approved_by": "Dr. Robert Torres", "approved_date": now - timedelta(days=185), "created_at": now - timedelta(days=220)},
            {"id": "SDOC-002", "trial_id": EYLEA_TRIAL, "product_name": "EYLEA HD", "category": DocumentCategory.DSUR, "title": "EYLEA HD DSUR 2025 Annual Report", "version": "1.0", "status": ReviewStatus.APPROVED, "effective_date": now - timedelta(days=60), "expiry_date": None, "total_pages": 186, "data_lock_date": now - timedelta(days=90), "reporting_period_start": now - timedelta(days=425), "reporting_period_end": now - timedelta(days=60), "author": "Dr. Emily Park", "medical_reviewer": "Dr. James Chen", "approved_by": "Dr. Robert Torres", "approved_date": now - timedelta(days=30), "created_at": now - timedelta(days=120)},
            {"id": "SDOC-003", "trial_id": EYLEA_TRIAL, "product_name": "EYLEA HD", "category": DocumentCategory.RSI_TABLE, "title": "EYLEA HD Reference Safety Information Table v8", "version": "8.0", "status": ReviewStatus.PUBLISHED, "effective_date": now - timedelta(days=90), "expiry_date": now + timedelta(days=275), "total_pages": 28, "data_lock_date": now - timedelta(days=100), "reporting_period_start": None, "reporting_period_end": None, "author": "Dr. Lisa Nakamura", "medical_reviewer": "Dr. James Chen", "approved_by": "Dr. Robert Torres", "approved_date": now - timedelta(days=95), "created_at": now - timedelta(days=130)},
            {"id": "SDOC-004", "trial_id": DUPIXENT_TRIAL, "product_name": "Dupixent", "category": DocumentCategory.INVESTIGATORS_BROCHURE, "title": "Dupixent Investigator's Brochure v22", "version": "22.0", "status": ReviewStatus.PUBLISHED, "effective_date": now - timedelta(days=120), "expiry_date": now + timedelta(days=245), "total_pages": 528, "data_lock_date": now - timedelta(days=150), "reporting_period_start": now - timedelta(days=485), "reporting_period_end": now - timedelta(days=120), "author": "Dr. Angela Martinez", "medical_reviewer": "Dr. David Wilson", "approved_by": "Dr. Patricia Sullivan", "approved_date": now - timedelta(days=125), "created_at": now - timedelta(days=180)},
            {"id": "SDOC-005", "trial_id": DUPIXENT_TRIAL, "product_name": "Dupixent", "category": DocumentCategory.DSUR, "title": "Dupixent DSUR 2025 Annual Report", "version": "1.0", "status": ReviewStatus.MEDICAL_REVIEW, "effective_date": None, "expiry_date": None, "total_pages": 245, "data_lock_date": now - timedelta(days=45), "reporting_period_start": now - timedelta(days=410), "reporting_period_end": now - timedelta(days=45), "author": "Dr. Michael Patel", "medical_reviewer": "Dr. David Wilson", "approved_by": None, "approved_date": None, "created_at": now - timedelta(days=60)},
            {"id": "SDOC-006", "trial_id": DUPIXENT_TRIAL, "product_name": "Dupixent", "category": DocumentCategory.CORE_DATA_SHEET, "title": "Dupixent Company Core Data Sheet v12", "version": "12.0", "status": ReviewStatus.PUBLISHED, "effective_date": now - timedelta(days=200), "expiry_date": now + timedelta(days=165), "total_pages": 42, "data_lock_date": None, "reporting_period_start": None, "reporting_period_end": None, "author": "Dr. Laura Kim", "medical_reviewer": "Dr. David Wilson", "approved_by": "Dr. Patricia Sullivan", "approved_date": now - timedelta(days=205), "created_at": now - timedelta(days=240)},
            {"id": "SDOC-007", "trial_id": DUPIXENT_TRIAL, "product_name": "Dupixent", "category": DocumentCategory.RSI_TABLE, "title": "Dupixent Reference Safety Information Table v15", "version": "15.0", "status": ReviewStatus.PUBLISHED, "effective_date": now - timedelta(days=100), "expiry_date": now + timedelta(days=265), "total_pages": 35, "data_lock_date": now - timedelta(days=110), "reporting_period_start": None, "reporting_period_end": None, "author": "Dr. Angela Martinez", "medical_reviewer": "Dr. David Wilson", "approved_by": "Dr. Patricia Sullivan", "approved_date": now - timedelta(days=105), "created_at": now - timedelta(days=140)},
            {"id": "SDOC-008", "trial_id": LIBTAYO_TRIAL, "product_name": "Libtayo", "category": DocumentCategory.INVESTIGATORS_BROCHURE, "title": "Libtayo Investigator's Brochure v18", "version": "18.0", "status": ReviewStatus.PUBLISHED, "effective_date": now - timedelta(days=150), "expiry_date": now + timedelta(days=215), "total_pages": 456, "data_lock_date": now - timedelta(days=170), "reporting_period_start": now - timedelta(days=535), "reporting_period_end": now - timedelta(days=150), "author": "Dr. Catherine Liu", "medical_reviewer": "Dr. Andrew Foster", "approved_by": "Dr. Gregory Harris", "approved_date": now - timedelta(days=155), "created_at": now - timedelta(days=200)},
            {"id": "SDOC-009", "trial_id": LIBTAYO_TRIAL, "product_name": "Libtayo", "category": DocumentCategory.DSUR, "title": "Libtayo DSUR 2025 Annual Report", "version": "1.0", "status": ReviewStatus.SAFETY_REVIEW, "effective_date": None, "expiry_date": None, "total_pages": 312, "data_lock_date": now - timedelta(days=30), "reporting_period_start": now - timedelta(days=395), "reporting_period_end": now - timedelta(days=30), "author": "Dr. Natalie Wong", "medical_reviewer": "Dr. Andrew Foster", "approved_by": None, "approved_date": None, "created_at": now - timedelta(days=50)},
            {"id": "SDOC-010", "trial_id": LIBTAYO_TRIAL, "product_name": "Libtayo", "category": DocumentCategory.PSUR, "title": "Libtayo PSUR #6", "version": "6.0", "status": ReviewStatus.APPROVED, "effective_date": now - timedelta(days=75), "expiry_date": None, "total_pages": 198, "data_lock_date": now - timedelta(days=100), "reporting_period_start": now - timedelta(days=260), "reporting_period_end": now - timedelta(days=75), "author": "Dr. Catherine Liu", "medical_reviewer": "Dr. Andrew Foster", "approved_by": "Dr. Gregory Harris", "approved_date": now - timedelta(days=40), "created_at": now - timedelta(days=120)},
            {"id": "SDOC-011", "trial_id": LIBTAYO_TRIAL, "product_name": "Libtayo", "category": DocumentCategory.SAFETY_LABEL, "title": "Libtayo US Prescribing Information Safety Section", "version": "5.0", "status": ReviewStatus.PUBLISHED, "effective_date": now - timedelta(days=250), "expiry_date": None, "total_pages": 18, "data_lock_date": None, "reporting_period_start": None, "reporting_period_end": None, "author": "Dr. Andrew Foster", "medical_reviewer": "Dr. Gregory Harris", "approved_by": "Dr. Gregory Harris", "approved_date": now - timedelta(days=255), "created_at": now - timedelta(days=280)},
            {"id": "SDOC-012", "trial_id": LIBTAYO_TRIAL, "product_name": "Libtayo", "category": DocumentCategory.RSI_TABLE, "title": "Libtayo Reference Safety Information Table v10", "version": "10.0", "status": ReviewStatus.DRAFT, "effective_date": None, "expiry_date": None, "total_pages": 0, "data_lock_date": None, "reporting_period_start": None, "reporting_period_end": None, "author": "Dr. Natalie Wong", "medical_reviewer": None, "approved_by": None, "approved_date": None, "created_at": now - timedelta(days=10)},
        ]

        for d in documents_data:
            self._safety_documents[d["id"]] = SafetyDocument(**d)

        # --- 15 IB Sections ---
        sections_data = [
            {"id": "SEC-001", "document_id": "SDOC-001", "section_number": "5.1", "section_type": SectionType.CLINICAL_SAFETY, "title": "Clinical Safety Summary - EYLEA HD", "content_summary": "Overview of clinical safety profile from pivotal trials. Includes injection-related adverse events, ocular safety outcomes, and systemic safety data from 2,400+ treated patients.", "word_count": 8500, "tables_count": 12, "figures_count": 4, "references_count": 28, "last_updated": now - timedelta(days=185), "updated_by": "Dr. Sarah Mitchell", "change_description": "Updated with 48-week safety data from PULSAR trial", "created_at": now - timedelta(days=220)},
            {"id": "SEC-002", "document_id": "SDOC-001", "section_number": "4.1", "section_type": SectionType.PHARMACOLOGY, "title": "Clinical Pharmacology - EYLEA HD", "content_summary": "Pharmacological properties of aflibercept 8mg including VEGF binding kinetics, receptor specificity, and pharmacodynamic effects on retinal vasculature.", "word_count": 4200, "tables_count": 6, "figures_count": 3, "references_count": 15, "last_updated": now - timedelta(days=200), "updated_by": "Dr. James Chen", "change_description": None, "created_at": now - timedelta(days=220)},
            {"id": "SEC-003", "document_id": "SDOC-001", "section_number": "4.3", "section_type": SectionType.PHARMACOKINETICS, "title": "Pharmacokinetics - EYLEA HD", "content_summary": "Systemic PK parameters following intravitreal injection. Free aflibercept plasma concentrations, half-life, and accumulation data.", "word_count": 3100, "tables_count": 4, "figures_count": 5, "references_count": 12, "last_updated": now - timedelta(days=190), "updated_by": "Dr. Sarah Mitchell", "change_description": "Added population PK analysis results", "created_at": now - timedelta(days=220)},
            {"id": "SEC-004", "document_id": "SDOC-001", "section_number": "3.2", "section_type": SectionType.TOXICOLOGY, "title": "Toxicology Summary - EYLEA HD", "content_summary": "Nonclinical toxicology findings from repeat-dose IVT studies in rabbits and cynomolgus monkeys. NOAEL determinations and safety margins.", "word_count": 5600, "tables_count": 8, "figures_count": 2, "references_count": 18, "last_updated": now - timedelta(days=210), "updated_by": "Dr. James Chen", "change_description": None, "created_at": now - timedelta(days=220)},
            {"id": "SEC-005", "document_id": "SDOC-001", "section_number": "5.5", "section_type": SectionType.SPECIAL_POPULATIONS, "title": "Special Populations - EYLEA HD", "content_summary": "Safety data in elderly patients (>=75 years), patients with renal/hepatic impairment, and diabetic subpopulations.", "word_count": 3800, "tables_count": 6, "figures_count": 1, "references_count": 10, "last_updated": now - timedelta(days=188), "updated_by": "Dr. Sarah Mitchell", "change_description": "Updated elderly subgroup analysis", "created_at": now - timedelta(days=220)},
            {"id": "SEC-006", "document_id": "SDOC-004", "section_number": "5.1", "section_type": SectionType.CLINICAL_SAFETY, "title": "Clinical Safety Summary - Dupixent", "content_summary": "Comprehensive safety profile across atopic dermatitis, asthma, CRSwNP, EoE, prurigo nodularis, and COPD indications. Pooled safety from 12,000+ patients.", "word_count": 14200, "tables_count": 22, "figures_count": 8, "references_count": 45, "last_updated": now - timedelta(days=125), "updated_by": "Dr. Angela Martinez", "change_description": "Added COPD phase 3 safety data", "created_at": now - timedelta(days=180)},
            {"id": "SEC-007", "document_id": "SDOC-004", "section_number": "5.3", "section_type": SectionType.DRUG_INTERACTIONS, "title": "Drug Interactions - Dupixent", "content_summary": "Assessment of drug-drug interactions with CYP450 substrates. Impact on vaccine immunogenicity. Concomitant medication analysis.", "word_count": 2800, "tables_count": 4, "figures_count": 1, "references_count": 14, "last_updated": now - timedelta(days=130), "updated_by": "Dr. Michael Patel", "change_description": None, "created_at": now - timedelta(days=180)},
            {"id": "SEC-008", "document_id": "SDOC-004", "section_number": "3.1", "section_type": SectionType.NONCLINICAL_SAFETY, "title": "Nonclinical Safety - Dupixent", "content_summary": "Nonclinical safety pharmacology, general toxicity, reproductive toxicity, and immunotoxicity studies in mice and monkeys.", "word_count": 6900, "tables_count": 10, "figures_count": 3, "references_count": 22, "last_updated": now - timedelta(days=140), "updated_by": "Dr. David Wilson", "change_description": None, "created_at": now - timedelta(days=180)},
            {"id": "SEC-009", "document_id": "SDOC-004", "section_number": "5.6", "section_type": SectionType.OVERDOSE, "title": "Overdose Information - Dupixent", "content_summary": "Overdose experience from clinical trials and postmarketing. Maximum administered doses and management guidelines.", "word_count": 1200, "tables_count": 1, "figures_count": 0, "references_count": 5, "last_updated": now - timedelta(days=135), "updated_by": "Dr. Angela Martinez", "change_description": None, "created_at": now - timedelta(days=180)},
            {"id": "SEC-010", "document_id": "SDOC-004", "section_number": "5.4", "section_type": SectionType.SPECIAL_POPULATIONS, "title": "Special Populations - Dupixent", "content_summary": "Safety in pediatric patients (6 months to 17 years), elderly, pregnant/lactating women, and immunocompromised patients.", "word_count": 5100, "tables_count": 8, "figures_count": 2, "references_count": 16, "last_updated": now - timedelta(days=128), "updated_by": "Dr. Angela Martinez", "change_description": "Added pediatric 6-11 months safety data", "created_at": now - timedelta(days=180)},
            {"id": "SEC-011", "document_id": "SDOC-008", "section_number": "5.1", "section_type": SectionType.CLINICAL_SAFETY, "title": "Clinical Safety Summary - Libtayo", "content_summary": "Clinical safety across CSCC, BCC, NSCLC, and cervical cancer indications. Immune-mediated adverse reactions, infusion reactions, and long-term safety.", "word_count": 11800, "tables_count": 18, "figures_count": 6, "references_count": 38, "last_updated": now - timedelta(days=155), "updated_by": "Dr. Catherine Liu", "change_description": "Updated with cervical cancer safety data", "created_at": now - timedelta(days=200)},
            {"id": "SEC-012", "document_id": "SDOC-008", "section_number": "5.2", "section_type": SectionType.DRUG_INTERACTIONS, "title": "Drug Interactions - Libtayo", "content_summary": "PD-1 blockade effects on concomitant medications. Corticosteroid interaction analysis. Immunosuppressant considerations.", "word_count": 2400, "tables_count": 3, "figures_count": 1, "references_count": 11, "last_updated": now - timedelta(days=160), "updated_by": "Dr. Andrew Foster", "change_description": None, "created_at": now - timedelta(days=200)},
            {"id": "SEC-013", "document_id": "SDOC-008", "section_number": "3.2", "section_type": SectionType.TOXICOLOGY, "title": "Toxicology Summary - Libtayo", "content_summary": "Nonclinical toxicology from repeat-dose studies in cynomolgus monkeys. Immune-related findings, reproductive toxicity, and carcinogenicity assessment.", "word_count": 7200, "tables_count": 9, "figures_count": 2, "references_count": 20, "last_updated": now - timedelta(days=165), "updated_by": "Dr. Andrew Foster", "change_description": None, "created_at": now - timedelta(days=200)},
            {"id": "SEC-014", "document_id": "SDOC-008", "section_number": "4.2", "section_type": SectionType.PHARMACOKINETICS, "title": "Pharmacokinetics - Libtayo", "content_summary": "Population PK model, dose-exposure relationships, immunogenicity impact on PK, and special population PK analyses.", "word_count": 4500, "tables_count": 7, "figures_count": 4, "references_count": 14, "last_updated": now - timedelta(days=158), "updated_by": "Dr. Catherine Liu", "change_description": "Added flat-dose PK bridging data", "created_at": now - timedelta(days=200)},
            {"id": "SEC-015", "document_id": "SDOC-008", "section_number": "5.5", "section_type": SectionType.SPECIAL_POPULATIONS, "title": "Special Populations - Libtayo", "content_summary": "Safety in elderly (>=65 years), patients with autoimmune conditions, organ transplant recipients, and hepatic/renal impairment.", "word_count": 4100, "tables_count": 5, "figures_count": 2, "references_count": 13, "last_updated": now - timedelta(days=157), "updated_by": "Dr. Natalie Wong", "change_description": None, "created_at": now - timedelta(days=200)},
        ]

        for s in sections_data:
            self._ib_sections[s["id"]] = IBSection(**s)

        # --- 12 Safety Updates ---
        updates_data = [
            {"id": "UPD-001", "document_id": "SDOC-001", "trial_id": EYLEA_TRIAL, "product_name": "EYLEA HD", "update_type": UpdateType.FREQUENCY_CHANGE, "safety_topic": "Endophthalmitis incidence rate update", "previous_information": "Endophthalmitis reported in 0.03% of injections", "updated_information": "Endophthalmitis reported in 0.02% of injections based on cumulative 48-week data from PULSAR and PHOTON trials", "rationale": "Updated pooled incidence from expanded dataset (n=2,847 patients)", "affected_sections": ["5.1", "5.2"], "regulatory_notification_required": True, "investigator_notification_required": True, "irb_notification_required": False, "proposed_by": "Dr. Sarah Mitchell", "approved_by": "Dr. Robert Torres", "implementation_date": now - timedelta(days=180), "created_at": now - timedelta(days=200)},
            {"id": "UPD-002", "document_id": "SDOC-001", "trial_id": EYLEA_TRIAL, "product_name": "EYLEA HD", "update_type": UpdateType.NEW_SIGNAL, "safety_topic": "Retinal pigment epithelial tear risk characterization", "previous_information": None, "updated_information": "RPE tears observed in 1.2% of patients in PULSAR trial, predominantly in eyes with pre-existing PED >400 micrometers", "rationale": "New safety signal identified during routine signal detection. Risk factor analysis completed.", "affected_sections": ["5.1", "5.5"], "regulatory_notification_required": True, "investigator_notification_required": True, "irb_notification_required": True, "proposed_by": "Dr. James Chen", "approved_by": "Dr. Robert Torres", "implementation_date": now - timedelta(days=175), "created_at": now - timedelta(days=195)},
            {"id": "UPD-003", "document_id": "SDOC-003", "trial_id": EYLEA_TRIAL, "product_name": "EYLEA HD", "update_type": UpdateType.LABELING_CHANGE, "safety_topic": "RSI table update for intraocular pressure elevation", "previous_information": "IOP elevation listed as uncommon (>=1/1000 to <1/100)", "updated_information": "IOP elevation reclassified as common (>=1/100 to <1/10) based on pooled analysis", "rationale": "Frequency category change based on cumulative data exceeding threshold", "affected_sections": ["Table 1"], "regulatory_notification_required": True, "investigator_notification_required": True, "irb_notification_required": True, "proposed_by": "Dr. Lisa Nakamura", "approved_by": "Dr. Robert Torres", "implementation_date": now - timedelta(days=85), "created_at": now - timedelta(days=110)},
            {"id": "UPD-004", "document_id": "SDOC-004", "trial_id": DUPIXENT_TRIAL, "product_name": "Dupixent", "update_type": UpdateType.NEW_RISK, "safety_topic": "Facial erythema (Dupixent face) characterization", "previous_information": None, "updated_information": "Facial erythema reported in 2.8% of atopic dermatitis patients. Predominantly mild-moderate, self-limiting. Management recommendations added.", "rationale": "Accumulating postmarketing reports and clinical trial data warrant inclusion as identified risk", "affected_sections": ["5.1", "5.4"], "regulatory_notification_required": True, "investigator_notification_required": True, "irb_notification_required": True, "proposed_by": "Dr. Angela Martinez", "approved_by": "Dr. Patricia Sullivan", "implementation_date": now - timedelta(days=115), "created_at": now - timedelta(days=145)},
            {"id": "UPD-005", "document_id": "SDOC-004", "trial_id": DUPIXENT_TRIAL, "product_name": "Dupixent", "update_type": UpdateType.FREQUENCY_CHANGE, "safety_topic": "Conjunctivitis frequency update across indications", "previous_information": "Conjunctivitis reported as common in AD patients", "updated_information": "Conjunctivitis frequency varies by indication: AD 8.6%, asthma 1.2%, CRSwNP 0.8%. Risk-benefit discussion updated.", "rationale": "Indication-specific frequency analysis from pooled data across all approved indications", "affected_sections": ["5.1"], "regulatory_notification_required": False, "investigator_notification_required": True, "irb_notification_required": False, "proposed_by": "Dr. Michael Patel", "approved_by": "Dr. Patricia Sullivan", "implementation_date": now - timedelta(days=100), "created_at": now - timedelta(days=130)},
            {"id": "UPD-006", "document_id": "SDOC-007", "trial_id": DUPIXENT_TRIAL, "product_name": "Dupixent", "update_type": UpdateType.REMOVED_RISK, "safety_topic": "Helminth infection risk reclassification", "previous_information": "Helminth infection listed as important potential risk", "updated_information": "Helminth infection reclassified from important potential risk to potential risk based on absence of signal in 6-year cumulative data", "rationale": "No clinically meaningful imbalance in helminth infections across 12,000+ patient-years of exposure", "affected_sections": ["Table 2"], "regulatory_notification_required": False, "investigator_notification_required": False, "irb_notification_required": False, "proposed_by": "Dr. Laura Kim", "approved_by": "Dr. Patricia Sullivan", "implementation_date": now - timedelta(days=95), "created_at": now - timedelta(days=120)},
            {"id": "UPD-007", "document_id": "SDOC-005", "trial_id": DUPIXENT_TRIAL, "product_name": "Dupixent", "update_type": UpdateType.REGULATORY_REQUEST, "safety_topic": "EMA requested DSUR safety update for eosinophilic conditions", "previous_information": None, "updated_information": "Enhanced monitoring data for eosinophilic GI events across all indications per EMA Day 120 list of questions", "rationale": "Regulatory authority request during Type II variation assessment", "affected_sections": ["3.1", "3.2"], "regulatory_notification_required": True, "investigator_notification_required": False, "irb_notification_required": False, "proposed_by": "Dr. David Wilson", "approved_by": None, "implementation_date": None, "created_at": now - timedelta(days=40)},
            {"id": "UPD-008", "document_id": "SDOC-008", "trial_id": LIBTAYO_TRIAL, "product_name": "Libtayo", "update_type": UpdateType.SEVERITY_UPGRADE, "safety_topic": "Immune-mediated myocarditis severity reclassification", "previous_information": "Myocarditis listed as rare immune-mediated adverse reaction", "updated_information": "Myocarditis severity upgraded to important identified risk with fatal outcomes reported. Enhanced monitoring and management algorithm added.", "rationale": "Post-marketing fatal cases and updated literature review support severity upgrade", "affected_sections": ["5.1", "5.3", "5.5"], "regulatory_notification_required": True, "investigator_notification_required": True, "irb_notification_required": True, "proposed_by": "Dr. Catherine Liu", "approved_by": "Dr. Gregory Harris", "implementation_date": now - timedelta(days=145), "created_at": now - timedelta(days=170)},
            {"id": "UPD-009", "document_id": "SDOC-008", "trial_id": LIBTAYO_TRIAL, "product_name": "Libtayo", "update_type": UpdateType.NEW_SIGNAL, "safety_topic": "Hemophagocytic lymphohistiocytosis (HLH) signal", "previous_information": None, "updated_information": "HLH reported in 3 patients (0.05%) across clinical program. Potential class effect of anti-PD-1 therapy. Added as important potential risk.", "rationale": "Signal detected during routine pharmacovigilance. Cross-class review of anti-PD-1/PD-L1 literature supports plausibility.", "affected_sections": ["5.1"], "regulatory_notification_required": True, "investigator_notification_required": True, "irb_notification_required": True, "proposed_by": "Dr. Andrew Foster", "approved_by": "Dr. Gregory Harris", "implementation_date": now - timedelta(days=140), "created_at": now - timedelta(days=165)},
            {"id": "UPD-010", "document_id": "SDOC-008", "trial_id": LIBTAYO_TRIAL, "product_name": "Libtayo", "update_type": UpdateType.FREQUENCY_CHANGE, "safety_topic": "Immune-mediated hepatitis frequency update", "previous_information": "Hepatitis reported in 1.1% of patients", "updated_information": "Hepatitis reported in 2.3% of patients in pooled analysis including cervical cancer indication data", "rationale": "Higher incidence observed in cervical cancer patient population. Pooled frequency updated.", "affected_sections": ["5.1", "5.2"], "regulatory_notification_required": True, "investigator_notification_required": True, "irb_notification_required": False, "proposed_by": "Dr. Natalie Wong", "approved_by": "Dr. Gregory Harris", "implementation_date": now - timedelta(days=130), "created_at": now - timedelta(days=155)},
            {"id": "UPD-011", "document_id": "SDOC-010", "trial_id": LIBTAYO_TRIAL, "product_name": "Libtayo", "update_type": UpdateType.LABELING_CHANGE, "safety_topic": "PSUR labeling recommendation for Steven-Johnson Syndrome", "previous_information": "SJS/TEN not listed in labeling", "updated_information": "SJS/TEN added as rare adverse reaction based on post-marketing reports. Proposed labeling update to include in Warnings section.", "rationale": "Causality assessment supports listing. Multiple well-documented cases with positive dechallenge.", "affected_sections": ["Section 4.4", "Section 4.8"], "regulatory_notification_required": True, "investigator_notification_required": True, "irb_notification_required": True, "proposed_by": "Dr. Catherine Liu", "approved_by": "Dr. Gregory Harris", "implementation_date": now - timedelta(days=70), "created_at": now - timedelta(days=100)},
            {"id": "UPD-012", "document_id": "SDOC-012", "trial_id": LIBTAYO_TRIAL, "product_name": "Libtayo", "update_type": UpdateType.NEW_RISK, "safety_topic": "Immune-mediated encephalitis characterization", "previous_information": None, "updated_information": "Encephalitis reported in 0.1% of patients. Median time to onset 21 days. Management with high-dose corticosteroids recommended.", "rationale": "Sufficient clinical data to characterize as identified risk with clinical guidance", "affected_sections": ["5.1", "5.5"], "regulatory_notification_required": True, "investigator_notification_required": True, "irb_notification_required": True, "proposed_by": "Dr. Natalie Wong", "approved_by": None, "implementation_date": None, "created_at": now - timedelta(days=8)},
        ]

        for u in updates_data:
            self._safety_updates[u["id"]] = SafetyUpdate(**u)

        # --- 12 Safety Narratives ---
        narratives_data = [
            {"id": "NAR-001", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1001", "narrative_type": NarrativeType.SAE_NARRATIVE, "case_number": "EYLEA-SAE-2025-001", "event_term": "Endophthalmitis", "narrative_text": "A 72-year-old male with neovascular AMD developed endophthalmitis 3 days after the 4th intravitreal injection of EYLEA HD 8mg. Treated with intravitreal antibiotics and resolved within 14 days.", "word_count": 450, "status": ReviewStatus.APPROVED, "author": "Dr. Sarah Mitchell", "medical_reviewer": "Dr. James Chen", "review_date": now - timedelta(days=80), "regulatory_submission_required": True, "submitted_date": now - timedelta(days=75), "created_at": now - timedelta(days=90)},
            {"id": "NAR-002", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1003", "narrative_type": NarrativeType.SAE_NARRATIVE, "case_number": "EYLEA-SAE-2025-002", "event_term": "Retinal detachment", "narrative_text": "An 81-year-old female experienced rhegmatogenous retinal detachment 6 weeks after study drug administration. Required surgical repair. Assessed as unlikely related to treatment.", "word_count": 380, "status": ReviewStatus.APPROVED, "author": "Dr. Lisa Nakamura", "medical_reviewer": "Dr. James Chen", "review_date": now - timedelta(days=65), "regulatory_submission_required": True, "submitted_date": now - timedelta(days=60), "created_at": now - timedelta(days=75)},
            {"id": "NAR-003", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1005", "narrative_type": NarrativeType.SUSAR_NARRATIVE, "case_number": "EYLEA-SUSAR-2025-001", "event_term": "Retinal vasculitis", "narrative_text": "A 68-year-old female developed retinal vasculitis 10 days post-injection. This is an unexpected serious adverse reaction not listed in the current IB. Resolved with systemic corticosteroids.", "word_count": 620, "status": ReviewStatus.PUBLISHED, "author": "Dr. James Chen", "medical_reviewer": "Dr. Robert Torres", "review_date": now - timedelta(days=55), "regulatory_submission_required": True, "submitted_date": now - timedelta(days=50), "created_at": now - timedelta(days=60)},
            {"id": "NAR-004", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2001", "narrative_type": NarrativeType.SAE_NARRATIVE, "case_number": "DPX-SAE-2025-001", "event_term": "Anaphylaxis", "narrative_text": "A 34-year-old female with severe atopic dermatitis experienced anaphylaxis within 30 minutes of the 6th dose of dupilumab. Treated with epinephrine and recovered. Drug permanently discontinued.", "word_count": 520, "status": ReviewStatus.APPROVED, "author": "Dr. Angela Martinez", "medical_reviewer": "Dr. David Wilson", "review_date": now - timedelta(days=95), "regulatory_submission_required": True, "submitted_date": now - timedelta(days=90), "created_at": now - timedelta(days=100)},
            {"id": "NAR-005", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2004", "narrative_type": NarrativeType.SAE_NARRATIVE, "case_number": "DPX-SAE-2025-002", "event_term": "Severe eczema herpeticum", "narrative_text": "A 28-year-old male with AD developed severe eczema herpeticum requiring hospitalization. Occurred 8 weeks into treatment. Treated with IV acyclovir. Drug temporarily interrupted.", "word_count": 480, "status": ReviewStatus.MEDICAL_REVIEW, "author": "Dr. Michael Patel", "medical_reviewer": "Dr. David Wilson", "review_date": None, "regulatory_submission_required": True, "submitted_date": None, "created_at": now - timedelta(days=35)},
            {"id": "NAR-006", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2006", "narrative_type": NarrativeType.PREGNANCY_NARRATIVE, "case_number": "DPX-PREG-2025-001", "event_term": "Pregnancy exposure", "narrative_text": "A 31-year-old female participant became pregnant during the study. Drug was discontinued immediately upon confirmation. Patient enrolled in pregnancy registry for follow-up.", "word_count": 350, "status": ReviewStatus.APPROVED, "author": "Dr. Laura Kim", "medical_reviewer": "Dr. Patricia Sullivan", "review_date": now - timedelta(days=40), "regulatory_submission_required": True, "submitted_date": now - timedelta(days=35), "created_at": now - timedelta(days=50)},
            {"id": "NAR-007", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2008", "narrative_type": NarrativeType.SPECIAL_INTEREST, "case_number": "DPX-AESI-2025-001", "event_term": "Eosinophilic pneumonia", "narrative_text": "A 45-year-old female with asthma developed eosinophilic pneumonia 12 weeks into treatment. Event of special interest per protocol. Resolved after drug discontinuation and corticosteroid treatment.", "word_count": 550, "status": ReviewStatus.SAFETY_REVIEW, "author": "Dr. Angela Martinez", "medical_reviewer": "Dr. David Wilson", "review_date": None, "regulatory_submission_required": True, "submitted_date": None, "created_at": now - timedelta(days=25)},
            {"id": "NAR-008", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3001", "narrative_type": NarrativeType.SAE_NARRATIVE, "case_number": "LBT-SAE-2025-001", "event_term": "Immune-mediated pneumonitis", "narrative_text": "A 65-year-old male with NSCLC developed Grade 3 immune-mediated pneumonitis after cycle 4 of cemiplimab. Treated with high-dose methylprednisolone with partial improvement.", "word_count": 680, "status": ReviewStatus.APPROVED, "author": "Dr. Catherine Liu", "medical_reviewer": "Dr. Andrew Foster", "review_date": now - timedelta(days=100), "regulatory_submission_required": True, "submitted_date": now - timedelta(days=95), "created_at": now - timedelta(days=110)},
            {"id": "NAR-009", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3004", "narrative_type": NarrativeType.SUSAR_NARRATIVE, "case_number": "LBT-SUSAR-2025-001", "event_term": "Myocarditis", "narrative_text": "A 58-year-old male developed fulminant myocarditis after cycle 2 of cemiplimab. Required ICU admission with inotropic support. Fatal outcome despite aggressive immunosuppressive therapy.", "word_count": 850, "status": ReviewStatus.PUBLISHED, "author": "Dr. Andrew Foster", "medical_reviewer": "Dr. Gregory Harris", "review_date": now - timedelta(days=70), "regulatory_submission_required": True, "submitted_date": now - timedelta(days=65), "created_at": now - timedelta(days=80)},
            {"id": "NAR-010", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3004", "narrative_type": NarrativeType.DEATH_NARRATIVE, "case_number": "LBT-DEATH-2025-001", "event_term": "Death due to myocarditis", "narrative_text": "Death narrative for PT-3004 who died from fulminant myocarditis on study Day 48. Autopsy confirmed immune-mediated myocarditis. Assessed as related to cemiplimab.", "word_count": 1200, "status": ReviewStatus.PUBLISHED, "author": "Dr. Catherine Liu", "medical_reviewer": "Dr. Gregory Harris", "review_date": now - timedelta(days=68), "regulatory_submission_required": True, "submitted_date": now - timedelta(days=63), "created_at": now - timedelta(days=78)},
            {"id": "NAR-011", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3007", "narrative_type": NarrativeType.SAE_NARRATIVE, "case_number": "LBT-SAE-2025-002", "event_term": "Immune-mediated colitis", "narrative_text": "A 71-year-old female with cervical cancer developed Grade 3 colitis after cycle 6. Colonoscopy confirmed immune-mediated etiology. Managed with infliximab after steroid-refractory course.", "word_count": 590, "status": ReviewStatus.DRAFT, "author": "Dr. Natalie Wong", "medical_reviewer": None, "review_date": None, "regulatory_submission_required": True, "submitted_date": None, "created_at": now - timedelta(days=15)},
            {"id": "NAR-012", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3009", "narrative_type": NarrativeType.SPECIAL_INTEREST, "case_number": "LBT-AESI-2025-001", "event_term": "Hemophagocytic lymphohistiocytosis", "narrative_text": "A 62-year-old male developed HLH with pancytopenia, hyperferritinemia, and hepatosplenomegaly after cycle 3. Event of special interest per protocol amendment. Ongoing at time of report.", "word_count": 720, "status": ReviewStatus.DRAFT, "author": "Dr. Natalie Wong", "medical_reviewer": None, "review_date": None, "regulatory_submission_required": True, "submitted_date": None, "created_at": now - timedelta(days=5)},
        ]

        for n in narratives_data:
            self._safety_narratives[n["id"]] = SafetyNarrative(**n)

        # --- 15 RSI Line Items ---
        line_items_data = [
            {"id": "RSI-001", "document_id": "SDOC-003", "product_name": "EYLEA HD", "adverse_event_term": "Conjunctival hemorrhage", "system_organ_class": "Eye disorders", "frequency_category": "Very common (>=1/10)", "incidence_pct": 24.5, "seriousness": "Non-serious", "expectedness": "expected", "source": "Pooled Phase 3 (PULSAR + PHOTON)", "first_reported_date": now - timedelta(days=400), "last_updated": now - timedelta(days=90), "notes": None, "created_at": now - timedelta(days=130)},
            {"id": "RSI-002", "document_id": "SDOC-003", "product_name": "EYLEA HD", "adverse_event_term": "Eye pain", "system_organ_class": "Eye disorders", "frequency_category": "Common (>=1/100 to <1/10)", "incidence_pct": 5.8, "seriousness": "Non-serious", "expectedness": "expected", "source": "Pooled Phase 3", "first_reported_date": now - timedelta(days=400), "last_updated": now - timedelta(days=90), "notes": None, "created_at": now - timedelta(days=130)},
            {"id": "RSI-003", "document_id": "SDOC-003", "product_name": "EYLEA HD", "adverse_event_term": "Intraocular pressure increased", "system_organ_class": "Eye disorders", "frequency_category": "Common (>=1/100 to <1/10)", "incidence_pct": 3.2, "seriousness": "Non-serious", "expectedness": "expected", "source": "Pooled Phase 3", "first_reported_date": now - timedelta(days=400), "last_updated": now - timedelta(days=85), "notes": "Frequency upgraded from uncommon per UPD-003", "created_at": now - timedelta(days=130)},
            {"id": "RSI-004", "document_id": "SDOC-003", "product_name": "EYLEA HD", "adverse_event_term": "Endophthalmitis", "system_organ_class": "Eye disorders", "frequency_category": "Rare (>=1/10000 to <1/1000)", "incidence_pct": 0.02, "seriousness": "Serious", "expectedness": "expected", "source": "Pooled clinical trials", "first_reported_date": now - timedelta(days=500), "last_updated": now - timedelta(days=90), "notes": "Injection-related risk; sterile technique critical", "created_at": now - timedelta(days=130)},
            {"id": "RSI-005", "document_id": "SDOC-003", "product_name": "EYLEA HD", "adverse_event_term": "Retinal pigment epithelial tear", "system_organ_class": "Eye disorders", "frequency_category": "Uncommon (>=1/1000 to <1/100)", "incidence_pct": 1.2, "seriousness": "Serious", "expectedness": "expected", "source": "PULSAR trial", "first_reported_date": now - timedelta(days=195), "last_updated": now - timedelta(days=90), "notes": "New signal identified per UPD-002. Risk factor: PED >400um", "created_at": now - timedelta(days=130)},
            {"id": "RSI-006", "document_id": "SDOC-007", "product_name": "Dupixent", "adverse_event_term": "Injection site reaction", "system_organ_class": "General disorders", "frequency_category": "Very common (>=1/10)", "incidence_pct": 15.2, "seriousness": "Non-serious", "expectedness": "expected", "source": "Pooled across indications", "first_reported_date": now - timedelta(days=600), "last_updated": now - timedelta(days=100), "notes": None, "created_at": now - timedelta(days=140)},
            {"id": "RSI-007", "document_id": "SDOC-007", "product_name": "Dupixent", "adverse_event_term": "Conjunctivitis", "system_organ_class": "Eye disorders", "frequency_category": "Common (>=1/100 to <1/10)", "incidence_pct": 8.6, "seriousness": "Non-serious", "expectedness": "expected", "source": "Pooled AD trials", "first_reported_date": now - timedelta(days=550), "last_updated": now - timedelta(days=100), "notes": "Indication-specific frequency: AD 8.6%, asthma 1.2%, CRSwNP 0.8%", "created_at": now - timedelta(days=140)},
            {"id": "RSI-008", "document_id": "SDOC-007", "product_name": "Dupixent", "adverse_event_term": "Facial erythema", "system_organ_class": "Skin disorders", "frequency_category": "Common (>=1/100 to <1/10)", "incidence_pct": 2.8, "seriousness": "Non-serious", "expectedness": "expected", "source": "Pooled AD trials + post-marketing", "first_reported_date": now - timedelta(days=145), "last_updated": now - timedelta(days=100), "notes": "Newly identified risk per UPD-004. Also known as Dupixent face.", "created_at": now - timedelta(days=140)},
            {"id": "RSI-009", "document_id": "SDOC-007", "product_name": "Dupixent", "adverse_event_term": "Anaphylaxis", "system_organ_class": "Immune system disorders", "frequency_category": "Rare (>=1/10000 to <1/1000)", "incidence_pct": 0.08, "seriousness": "Serious", "expectedness": "expected", "source": "Pooled across indications", "first_reported_date": now - timedelta(days=500), "last_updated": now - timedelta(days=100), "notes": None, "created_at": now - timedelta(days=140)},
            {"id": "RSI-010", "document_id": "SDOC-007", "product_name": "Dupixent", "adverse_event_term": "Eosinophilia", "system_organ_class": "Blood disorders", "frequency_category": "Common (>=1/100 to <1/10)", "incidence_pct": 4.1, "seriousness": "Non-serious", "expectedness": "expected", "source": "Pooled across indications", "first_reported_date": now - timedelta(days=500), "last_updated": now - timedelta(days=100), "notes": "Transient eosinophilia; usually resolves without intervention", "created_at": now - timedelta(days=140)},
            {"id": "RSI-011", "document_id": "SDOC-008", "product_name": "Libtayo", "adverse_event_term": "Immune-mediated pneumonitis", "system_organ_class": "Respiratory disorders", "frequency_category": "Common (>=1/100 to <1/10)", "incidence_pct": 4.8, "seriousness": "Serious", "expectedness": "expected", "source": "Pooled clinical program", "first_reported_date": now - timedelta(days=500), "last_updated": now - timedelta(days=150), "notes": "Grade >=3 in 1.8% of patients", "created_at": now - timedelta(days=200)},
            {"id": "RSI-012", "document_id": "SDOC-008", "product_name": "Libtayo", "adverse_event_term": "Immune-mediated hepatitis", "system_organ_class": "Hepatobiliary disorders", "frequency_category": "Common (>=1/100 to <1/10)", "incidence_pct": 2.3, "seriousness": "Serious", "expectedness": "expected", "source": "Pooled clinical program", "first_reported_date": now - timedelta(days=500), "last_updated": now - timedelta(days=130), "notes": "Frequency updated per UPD-010 (previously 1.1%)", "created_at": now - timedelta(days=200)},
            {"id": "RSI-013", "document_id": "SDOC-008", "product_name": "Libtayo", "adverse_event_term": "Immune-mediated colitis", "system_organ_class": "Gastrointestinal disorders", "frequency_category": "Common (>=1/100 to <1/10)", "incidence_pct": 2.0, "seriousness": "Serious", "expectedness": "expected", "source": "Pooled clinical program", "first_reported_date": now - timedelta(days=500), "last_updated": now - timedelta(days=150), "notes": None, "created_at": now - timedelta(days=200)},
            {"id": "RSI-014", "document_id": "SDOC-008", "product_name": "Libtayo", "adverse_event_term": "Myocarditis", "system_organ_class": "Cardiac disorders", "frequency_category": "Rare (>=1/10000 to <1/1000)", "incidence_pct": 0.15, "seriousness": "Serious", "expectedness": "expected", "source": "Pooled clinical program + post-marketing", "first_reported_date": now - timedelta(days=300), "last_updated": now - timedelta(days=145), "notes": "Severity upgraded to important identified risk per UPD-008. Fatal cases reported.", "created_at": now - timedelta(days=200)},
            {"id": "RSI-015", "document_id": "SDOC-008", "product_name": "Libtayo", "adverse_event_term": "Steven-Johnson Syndrome/TEN", "system_organ_class": "Skin disorders", "frequency_category": "Rare (>=1/10000 to <1/1000)", "incidence_pct": None, "seriousness": "Serious", "expectedness": "unexpected", "source": "Post-marketing reports", "first_reported_date": now - timedelta(days=100), "last_updated": now - timedelta(days=70), "notes": "Newly added per PSUR recommendation UPD-011", "created_at": now - timedelta(days=100)},
        ]

        for li in line_items_data:
            self._rsi_line_items[li["id"]] = RSILineItem(**li)

    # ------------------------------------------------------------------
    # Safety Document Management
    # ------------------------------------------------------------------

    def list_safety_documents(
        self,
        *,
        trial_id: str | None = None,
        product_name: str | None = None,
        category: DocumentCategory | None = None,
        status: ReviewStatus | None = None,
    ) -> list[SafetyDocument]:
        """List safety documents with optional filters."""
        with self._lock:
            result = list(self._safety_documents.values())

        if trial_id is not None:
            result = [d for d in result if d.trial_id == trial_id]
        if product_name is not None:
            result = [d for d in result if d.product_name == product_name]
        if category is not None:
            result = [d for d in result if d.category == category]
        if status is not None:
            result = [d for d in result if d.status == status]

        return sorted(result, key=lambda d: d.created_at, reverse=True)

    def get_safety_document(self, document_id: str) -> SafetyDocument | None:
        """Get a single safety document by ID."""
        with self._lock:
            return self._safety_documents.get(document_id)

    def create_safety_document(self, payload: SafetyDocumentCreate) -> SafetyDocument:
        """Create a new safety document."""
        now = datetime.now(timezone.utc)
        document_id = f"SDOC-{uuid4().hex[:8].upper()}"
        document = SafetyDocument(
            id=document_id,
            trial_id=payload.trial_id,
            product_name=payload.product_name,
            category=payload.category,
            title=payload.title,
            version=payload.version,
            status=ReviewStatus.DRAFT,
            author=payload.author,
            created_at=now,
        )
        with self._lock:
            self._safety_documents[document_id] = document
        logger.info("Created safety document %s: %s", document_id, payload.title)
        return document

    def update_safety_document(
        self, document_id: str, payload: SafetyDocumentUpdate
    ) -> SafetyDocument | None:
        """Update an existing safety document."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._safety_documents.get(document_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set approved_date when approved_by is set
            if "approved_by" in updates and updates["approved_by"] is not None:
                if existing.approved_by is None:
                    updates["approved_date"] = now

            data.update(updates)
            updated = SafetyDocument(**data)
            self._safety_documents[document_id] = updated
        return updated

    def delete_safety_document(self, document_id: str) -> bool:
        """Delete a safety document. Returns True if deleted."""
        with self._lock:
            if document_id in self._safety_documents:
                del self._safety_documents[document_id]
                return True
            return False

    # ------------------------------------------------------------------
    # IB Section Management
    # ------------------------------------------------------------------

    def list_ib_sections(
        self,
        *,
        document_id: str | None = None,
        section_type: SectionType | None = None,
    ) -> list[IBSection]:
        """List IB sections with optional filters."""
        with self._lock:
            result = list(self._ib_sections.values())

        if document_id is not None:
            result = [s for s in result if s.document_id == document_id]
        if section_type is not None:
            result = [s for s in result if s.section_type == section_type]

        return sorted(result, key=lambda s: s.section_number)

    def get_ib_section(self, section_id: str) -> IBSection | None:
        """Get a single IB section by ID."""
        with self._lock:
            return self._ib_sections.get(section_id)

    def create_ib_section(self, payload: IBSectionCreate) -> IBSection:
        """Create a new IB section."""
        now = datetime.now(timezone.utc)
        section_id = f"SEC-{uuid4().hex[:8].upper()}"
        section = IBSection(
            id=section_id,
            document_id=payload.document_id,
            section_number=payload.section_number,
            section_type=payload.section_type,
            title=payload.title,
            content_summary=payload.content_summary,
            updated_by=payload.updated_by,
            last_updated=now,
            created_at=now,
        )
        with self._lock:
            self._ib_sections[section_id] = section
        logger.info("Created IB section %s: %s", section_id, payload.title)
        return section

    def update_ib_section(
        self, section_id: str, payload: IBSectionUpdate
    ) -> IBSection | None:
        """Update an IB section."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._ib_sections.get(section_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            data["last_updated"] = now
            updated = IBSection(**data)
            self._ib_sections[section_id] = updated
        return updated

    def delete_ib_section(self, section_id: str) -> bool:
        """Delete an IB section. Returns True if deleted."""
        with self._lock:
            if section_id in self._ib_sections:
                del self._ib_sections[section_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Safety Update Management
    # ------------------------------------------------------------------

    def list_safety_updates(
        self,
        *,
        document_id: str | None = None,
        trial_id: str | None = None,
        product_name: str | None = None,
        update_type: UpdateType | None = None,
    ) -> list[SafetyUpdate]:
        """List safety updates with optional filters."""
        with self._lock:
            result = list(self._safety_updates.values())

        if document_id is not None:
            result = [u for u in result if u.document_id == document_id]
        if trial_id is not None:
            result = [u for u in result if u.trial_id == trial_id]
        if product_name is not None:
            result = [u for u in result if u.product_name == product_name]
        if update_type is not None:
            result = [u for u in result if u.update_type == update_type]

        return sorted(result, key=lambda u: u.created_at, reverse=True)

    def get_safety_update(self, update_id: str) -> SafetyUpdate | None:
        """Get a single safety update by ID."""
        with self._lock:
            return self._safety_updates.get(update_id)

    def create_safety_update(self, payload: SafetyUpdateCreate) -> SafetyUpdate:
        """Create a new safety update."""
        now = datetime.now(timezone.utc)
        update_id = f"UPD-{uuid4().hex[:8].upper()}"
        update = SafetyUpdate(
            id=update_id,
            document_id=payload.document_id,
            trial_id=payload.trial_id,
            product_name=payload.product_name,
            update_type=payload.update_type,
            safety_topic=payload.safety_topic,
            updated_information=payload.updated_information,
            rationale=payload.rationale,
            proposed_by=payload.proposed_by,
            created_at=now,
        )
        with self._lock:
            self._safety_updates[update_id] = update
        logger.info("Created safety update %s: %s", update_id, payload.safety_topic)
        return update

    def update_safety_update(
        self, update_id: str, payload: SafetyUpdateModify
    ) -> SafetyUpdate | None:
        """Update an existing safety update."""
        with self._lock:
            existing = self._safety_updates.get(update_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SafetyUpdate(**data)
            self._safety_updates[update_id] = updated
        return updated

    def delete_safety_update(self, update_id: str) -> bool:
        """Delete a safety update. Returns True if deleted."""
        with self._lock:
            if update_id in self._safety_updates:
                del self._safety_updates[update_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Safety Narrative Management
    # ------------------------------------------------------------------

    def list_safety_narratives(
        self,
        *,
        trial_id: str | None = None,
        narrative_type: NarrativeType | None = None,
        status: ReviewStatus | None = None,
    ) -> list[SafetyNarrative]:
        """List safety narratives with optional filters."""
        with self._lock:
            result = list(self._safety_narratives.values())

        if trial_id is not None:
            result = [n for n in result if n.trial_id == trial_id]
        if narrative_type is not None:
            result = [n for n in result if n.narrative_type == narrative_type]
        if status is not None:
            result = [n for n in result if n.status == status]

        return sorted(result, key=lambda n: n.created_at, reverse=True)

    def get_safety_narrative(self, narrative_id: str) -> SafetyNarrative | None:
        """Get a single safety narrative by ID."""
        with self._lock:
            return self._safety_narratives.get(narrative_id)

    def create_safety_narrative(self, payload: SafetyNarrativeCreate) -> SafetyNarrative:
        """Create a new safety narrative."""
        now = datetime.now(timezone.utc)
        narrative_id = f"NAR-{uuid4().hex[:8].upper()}"
        narrative = SafetyNarrative(
            id=narrative_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            narrative_type=payload.narrative_type,
            case_number=payload.case_number,
            event_term=payload.event_term,
            narrative_text=payload.narrative_text,
            word_count=len(payload.narrative_text.split()),
            status=ReviewStatus.DRAFT,
            author=payload.author,
            created_at=now,
        )
        with self._lock:
            self._safety_narratives[narrative_id] = narrative
        logger.info("Created safety narrative %s: %s", narrative_id, payload.case_number)
        return narrative

    def update_safety_narrative(
        self, narrative_id: str, payload: SafetyNarrativeUpdate
    ) -> SafetyNarrative | None:
        """Update a safety narrative."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._safety_narratives.get(narrative_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set review_date when medical_reviewer is set
            if "medical_reviewer" in updates and updates["medical_reviewer"] is not None:
                if existing.medical_reviewer is None:
                    updates["review_date"] = now

            # Update word count if narrative text changed
            if "narrative_text" in updates and updates["narrative_text"] is not None:
                updates["word_count"] = len(updates["narrative_text"].split())

            data.update(updates)
            updated = SafetyNarrative(**data)
            self._safety_narratives[narrative_id] = updated
        return updated

    def delete_safety_narrative(self, narrative_id: str) -> bool:
        """Delete a safety narrative. Returns True if deleted."""
        with self._lock:
            if narrative_id in self._safety_narratives:
                del self._safety_narratives[narrative_id]
                return True
            return False

    # ------------------------------------------------------------------
    # RSI Line Item Management
    # ------------------------------------------------------------------

    def list_rsi_line_items(
        self,
        *,
        document_id: str | None = None,
        product_name: str | None = None,
    ) -> list[RSILineItem]:
        """List RSI line items with optional filters."""
        with self._lock:
            result = list(self._rsi_line_items.values())

        if document_id is not None:
            result = [li for li in result if li.document_id == document_id]
        if product_name is not None:
            result = [li for li in result if li.product_name == product_name]

        return sorted(result, key=lambda li: li.adverse_event_term)

    def get_rsi_line_item(self, line_item_id: str) -> RSILineItem | None:
        """Get a single RSI line item by ID."""
        with self._lock:
            return self._rsi_line_items.get(line_item_id)

    def create_rsi_line_item(self, payload: RSILineItemCreate) -> RSILineItem:
        """Create a new RSI line item."""
        now = datetime.now(timezone.utc)
        line_item_id = f"RSI-{uuid4().hex[:8].upper()}"
        line_item = RSILineItem(
            id=line_item_id,
            document_id=payload.document_id,
            product_name=payload.product_name,
            adverse_event_term=payload.adverse_event_term,
            system_organ_class=payload.system_organ_class,
            frequency_category=payload.frequency_category,
            incidence_pct=payload.incidence_pct,
            source=payload.source,
            last_updated=now,
            created_at=now,
        )
        with self._lock:
            self._rsi_line_items[line_item_id] = line_item
        logger.info("Created RSI line item %s: %s", line_item_id, payload.adverse_event_term)
        return line_item

    def update_rsi_line_item(
        self, line_item_id: str, payload: RSILineItemUpdate
    ) -> RSILineItem | None:
        """Update an RSI line item."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._rsi_line_items.get(line_item_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            data["last_updated"] = now
            updated = RSILineItem(**data)
            self._rsi_line_items[line_item_id] = updated
        return updated

    def delete_rsi_line_item(self, line_item_id: str) -> bool:
        """Delete an RSI line item. Returns True if deleted."""
        with self._lock:
            if line_item_id in self._rsi_line_items:
                del self._rsi_line_items[line_item_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> RSIMetrics:
        """Compute aggregated RSI metrics."""
        with self._lock:
            documents = list(self._safety_documents.values())
            sections = list(self._ib_sections.values())
            updates = list(self._safety_updates.values())
            narratives = list(self._safety_narratives.values())
            line_items = list(self._rsi_line_items.values())

        if trial_id is not None:
            documents = [d for d in documents if d.trial_id == trial_id]
            # Filter sections by documents belonging to trial
            doc_ids = {d.id for d in documents}
            sections = [s for s in sections if s.document_id in doc_ids]
            updates = [u for u in updates if u.trial_id == trial_id]
            narratives = [n for n in narratives if n.trial_id == trial_id]
            line_items = [li for li in line_items if li.document_id in doc_ids]

        # Documents by category
        documents_by_category: dict[str, int] = {}
        for d in documents:
            key = d.category.value
            documents_by_category[key] = documents_by_category.get(key, 0) + 1

        # Documents by status
        documents_by_status: dict[str, int] = {}
        for d in documents:
            key = d.status.value
            documents_by_status[key] = documents_by_status.get(key, 0) + 1

        # Active documents (published or approved)
        active_documents = sum(
            1 for d in documents
            if d.status in (ReviewStatus.PUBLISHED, ReviewStatus.APPROVED)
        )

        # Updates by type
        updates_by_type: dict[str, int] = {}
        for u in updates:
            key = u.update_type.value
            updates_by_type[key] = updates_by_type.get(key, 0) + 1

        # Pending notifications
        pending_notifications = sum(
            1 for u in updates
            if (u.regulatory_notification_required or u.investigator_notification_required or u.irb_notification_required)
            and u.implementation_date is None
        )

        # Narratives by type
        narratives_by_type: dict[str, int] = {}
        for n in narratives:
            key = n.narrative_type.value
            narratives_by_type[key] = narratives_by_type.get(key, 0) + 1

        # Narratives pending review
        narratives_pending_review = sum(
            1 for n in narratives
            if n.status in (ReviewStatus.DRAFT, ReviewStatus.MEDICAL_REVIEW, ReviewStatus.SAFETY_REVIEW)
        )

        # Expected events
        expected_events = sum(
            1 for li in line_items
            if li.expectedness == "expected"
        )

        return RSIMetrics(
            total_documents=len(documents),
            documents_by_category=documents_by_category,
            documents_by_status=documents_by_status,
            active_documents=active_documents,
            total_ib_sections=len(sections),
            total_safety_updates=len(updates),
            updates_by_type=updates_by_type,
            pending_notifications=pending_notifications,
            total_narratives=len(narratives),
            narratives_by_type=narratives_by_type,
            narratives_pending_review=narratives_pending_review,
            total_rsi_line_items=len(line_items),
            expected_events=expected_events,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ReferenceSafetyInfoService | None = None
_instance_lock = threading.Lock()


def get_reference_safety_info_service() -> ReferenceSafetyInfoService:
    """Return the singleton ReferenceSafetyInfoService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ReferenceSafetyInfoService()
    return _instance


def reset_reference_safety_info_service() -> ReferenceSafetyInfoService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = ReferenceSafetyInfoService()
    return _instance
