"""Labeling Management Service (LABEL-MGMT).

Manages drug labeling lifecycle: label content sections, labeling negotiations
with health authorities, label artwork management, labeling change control,
country-specific labeling requirements, and labeling operational metrics.

Usage:
    from app.services.labeling_management_service import get_labeling_management_service

    svc = get_labeling_management_service()
    labels = svc.list_labels()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.labeling_management import (
    ArtworkStatus,
    ChangeCategory,
    CountryLabel,
    CountryLabelCreate,
    CountryLabelUpdate,
    LabelArtwork,
    LabelArtworkCreate,
    LabelArtworkUpdate,
    LabelChange,
    LabelChangeCreate,
    LabelChangeUpdate,
    LabelContent,
    LabelContentCreate,
    LabelContentUpdate,
    LabelingMetrics,
    LabelNegotiation,
    LabelNegotiationCreate,
    LabelNegotiationUpdate,
    LabelSection,
    LabelStatus,
    NegotiationStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class LabelingManagementService:
    """In-memory Labeling Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._labels: dict[str, LabelContent] = {}
        self._negotiations: dict[str, LabelNegotiation] = {}
        self._artworks: dict[str, LabelArtwork] = {}
        self._changes: dict[str, LabelChange] = {}
        self._country_labels: dict[str, CountryLabel] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic labeling data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Label Content records ---
        labels_data = [
            {"id": "LC-001", "trial_id": EYLEA_TRIAL, "product_name": "EYLEA (aflibercept)", "version": "14.0", "section": LabelSection.INDICATIONS, "content_text": "EYLEA is indicated for the treatment of Neovascular (Wet) Age-Related Macular Degeneration (AMD), Macular Edema following Retinal Vein Occlusion (RVO), Diabetic Macular Edema (DME), and Diabetic Retinopathy (DR).", "status": LabelStatus.EFFECTIVE, "language": "en", "country": "US", "effective_date": now - timedelta(days=180), "author": "dr.smith", "reviewer": "dr.chen", "approved_by": "vp_regulatory", "approved_date": now - timedelta(days=200), "created_at": now - timedelta(days=365)},
            {"id": "LC-002", "trial_id": EYLEA_TRIAL, "product_name": "EYLEA (aflibercept)", "version": "14.0", "section": LabelSection.DOSAGE, "content_text": "The recommended dose for EYLEA is 2 mg (0.05 mL) administered by intravitreal injection every 4 weeks (monthly) for the first 3 months, followed by 2 mg once every 8 weeks (2 months).", "status": LabelStatus.EFFECTIVE, "language": "en", "country": "US", "effective_date": now - timedelta(days=180), "author": "dr.smith", "reviewer": "dr.chen", "approved_by": "vp_regulatory", "approved_date": now - timedelta(days=200), "created_at": now - timedelta(days=365)},
            {"id": "LC-003", "trial_id": EYLEA_TRIAL, "product_name": "EYLEA (aflibercept)", "version": "15.0", "section": LabelSection.WARNINGS, "content_text": "Endophthalmitis and retinal detachments have been reported following intravitreal injections. Proper aseptic injection technique must always be used.", "status": LabelStatus.HA_NEGOTIATION, "language": "en", "country": "US", "author": "dr.smith", "reviewer": "dr.chen", "created_at": now - timedelta(days=60)},
            {"id": "LC-004", "trial_id": EYLEA_TRIAL, "product_name": "EYLEA (aflibercept)", "version": "15.0", "section": LabelSection.ADVERSE_REACTIONS, "content_text": "Most common adverse reactions (>=5%) are conjunctival hemorrhage, eye pain, cataract, vitreous detachment, vitreous floaters, and intraocular pressure increased.", "status": LabelStatus.INTERNAL_REVIEW, "language": "en", "author": "dr.smith", "created_at": now - timedelta(days=45)},
            {"id": "LC-005", "trial_id": DUPIXENT_TRIAL, "product_name": "DUPIXENT (dupilumab)", "version": "21.0", "section": LabelSection.INDICATIONS, "content_text": "DUPIXENT is indicated for the treatment of moderate-to-severe atopic dermatitis in adults and pediatric patients aged 6 months and older whose disease is not adequately controlled with topical prescription therapies or when those therapies are not advisable.", "status": LabelStatus.EFFECTIVE, "language": "en", "country": "US", "effective_date": now - timedelta(days=120), "author": "dr.martinez", "reviewer": "dr.patel", "approved_by": "vp_regulatory", "approved_date": now - timedelta(days=140), "created_at": now - timedelta(days=300)},
            {"id": "LC-006", "trial_id": DUPIXENT_TRIAL, "product_name": "DUPIXENT (dupilumab)", "version": "21.0", "section": LabelSection.DOSAGE, "content_text": "The recommended dose is an initial dose of 600 mg (two 300 mg injections), followed by 300 mg given every other week administered as subcutaneous injection.", "status": LabelStatus.EFFECTIVE, "language": "en", "country": "US", "effective_date": now - timedelta(days=120), "author": "dr.martinez", "reviewer": "dr.patel", "approved_by": "vp_regulatory", "approved_date": now - timedelta(days=140), "created_at": now - timedelta(days=300)},
            {"id": "LC-007", "trial_id": DUPIXENT_TRIAL, "product_name": "DUPIXENT (dupilumab)", "version": "22.0", "section": LabelSection.CLINICAL_STUDIES, "content_text": "The efficacy and safety of DUPIXENT were assessed in three randomized, double-blind, placebo-controlled, multicenter trials in adults with moderate-to-severe atopic dermatitis.", "status": LabelStatus.DRAFT, "language": "en", "author": "dr.martinez", "created_at": now - timedelta(days=30)},
            {"id": "LC-008", "trial_id": DUPIXENT_TRIAL, "product_name": "DUPIXENT (dupilumab)", "version": "21.0", "section": LabelSection.CONTRAINDICATIONS, "content_text": "DUPIXENT is contraindicated in patients with known hypersensitivity to dupilumab or any of its excipients.", "status": LabelStatus.APPROVED, "language": "en", "country": "US", "approved_by": "vp_regulatory", "approved_date": now - timedelta(days=90), "author": "dr.martinez", "reviewer": "dr.patel", "created_at": now - timedelta(days=200)},
            {"id": "LC-009", "trial_id": LIBTAYO_TRIAL, "product_name": "LIBTAYO (cemiplimab-rwlc)", "version": "8.0", "section": LabelSection.INDICATIONS, "content_text": "LIBTAYO is indicated for the treatment of patients with metastatic or locally advanced cutaneous squamous cell carcinoma (CSCC) who are not candidates for curative surgery or curative radiation.", "status": LabelStatus.EFFECTIVE, "language": "en", "country": "US", "effective_date": now - timedelta(days=90), "author": "dr.liu", "reviewer": "dr.foster", "approved_by": "vp_regulatory", "approved_date": now - timedelta(days=110), "created_at": now - timedelta(days=250)},
            {"id": "LC-010", "trial_id": LIBTAYO_TRIAL, "product_name": "LIBTAYO (cemiplimab-rwlc)", "version": "8.0", "section": LabelSection.BOXED_WARNING, "content_text": "Immune-mediated adverse reactions: LIBTAYO can cause immune-mediated adverse reactions in any organ system including pneumonitis, colitis, hepatitis, endocrinopathies, nephritis, and dermatologic reactions.", "status": LabelStatus.EFFECTIVE, "language": "en", "country": "US", "effective_date": now - timedelta(days=90), "author": "dr.liu", "reviewer": "dr.foster", "approved_by": "vp_regulatory", "approved_date": now - timedelta(days=110), "created_at": now - timedelta(days=250)},
            {"id": "LC-011", "trial_id": LIBTAYO_TRIAL, "product_name": "LIBTAYO (cemiplimab-rwlc)", "version": "9.0", "section": LabelSection.CLINICAL_PHARMACOLOGY, "content_text": "Cemiplimab is a recombinant human IgG4 monoclonal antibody that binds to PD-1 and blocks its interaction with PD-L1 and PD-L2, releasing PD-1 pathway-mediated inhibition of the immune response.", "status": LabelStatus.HA_NEGOTIATION, "language": "en", "author": "dr.liu", "created_at": now - timedelta(days=40)},
            {"id": "LC-012", "trial_id": LIBTAYO_TRIAL, "product_name": "LIBTAYO (cemiplimab-rwlc)", "version": "9.0", "section": LabelSection.DRUG_INTERACTIONS, "content_text": "No formal pharmacokinetic drug interaction studies have been conducted with LIBTAYO. Use of systemic corticosteroids or immunosuppressants before starting cemiplimab should be avoided.", "status": LabelStatus.SUPERSEDED, "language": "en", "country": "US", "author": "dr.liu", "expiry_date": now - timedelta(days=30), "created_at": now - timedelta(days=400)},
        ]

        for lbl in labels_data:
            self._labels[lbl["id"]] = LabelContent(**lbl)

        # --- 10 Label Negotiations ---
        negotiations_data = [
            {"id": "LN-001", "label_id": "LC-003", "trial_id": EYLEA_TRIAL, "health_authority": "FDA", "section": LabelSection.WARNINGS, "proposed_text": "Updated warnings language to include arterial thromboembolic events and endophthalmitis risk with revised incidence data.", "ha_position": "FDA requests inclusion of additional post-marketing safety data on retinal detachment.", "status": NegotiationStatus.UNDER_DISCUSSION, "negotiation_rounds": 2, "meeting_date": now + timedelta(days=14), "regulatory_contact": "dr.fda_reviewer_1", "internal_lead": "dr.smith", "notes": "Scheduled Type A meeting for label discussion.", "created_at": now - timedelta(days=55)},
            {"id": "LN-002", "label_id": "LC-003", "trial_id": EYLEA_TRIAL, "health_authority": "EMA", "section": LabelSection.WARNINGS, "proposed_text": "Harmonized warnings section aligning with FDA-approved language for EU SmPC.", "status": NegotiationStatus.PROPOSED, "negotiation_rounds": 0, "regulatory_contact": "ema_rapporteur_1", "internal_lead": "dr.smith", "created_at": now - timedelta(days=40)},
            {"id": "LN-003", "label_id": "LC-005", "trial_id": DUPIXENT_TRIAL, "health_authority": "FDA", "section": LabelSection.INDICATIONS, "proposed_text": "Expand indications to include prurigo nodularis in adults.", "ha_position": "FDA agrees with proposed indication expansion pending final data review.", "agreed_text": "DUPIXENT is indicated for the treatment of prurigo nodularis in adults whose disease is not adequately controlled with topical therapies.", "status": NegotiationStatus.AGREED, "negotiation_rounds": 3, "regulatory_contact": "dr.fda_reviewer_2", "internal_lead": "dr.martinez", "notes": "Agreement reached after 3 rounds of negotiation.", "created_at": now - timedelta(days=150)},
            {"id": "LN-004", "label_id": "LC-007", "trial_id": DUPIXENT_TRIAL, "health_authority": "FDA", "section": LabelSection.CLINICAL_STUDIES, "proposed_text": "Include Phase 3 data from LIBERTY AD HIVE study supporting efficacy in pediatric patients 6 months to 5 years.", "status": NegotiationStatus.PROPOSED, "negotiation_rounds": 0, "regulatory_contact": "dr.fda_reviewer_2", "internal_lead": "dr.martinez", "created_at": now - timedelta(days=25)},
            {"id": "LN-005", "label_id": "LC-009", "trial_id": LIBTAYO_TRIAL, "health_authority": "FDA", "section": LabelSection.INDICATIONS, "proposed_text": "Expand indication to include first-line treatment for advanced non-small cell lung cancer (NSCLC).", "ha_position": "FDA requests additional overall survival data from confirmatory trial.", "status": NegotiationStatus.DISPUTED, "negotiation_rounds": 4, "meeting_date": now + timedelta(days=30), "regulatory_contact": "dr.fda_reviewer_3", "internal_lead": "dr.liu", "notes": "Dispute over adequacy of OS data from single-arm trial.", "created_at": now - timedelta(days=100)},
            {"id": "LN-006", "label_id": "LC-011", "trial_id": LIBTAYO_TRIAL, "health_authority": "FDA", "section": LabelSection.CLINICAL_PHARMACOLOGY, "proposed_text": "Updated PK parameters based on population PK analysis from Phase 3 studies.", "status": NegotiationStatus.UNDER_DISCUSSION, "negotiation_rounds": 1, "regulatory_contact": "dr.fda_reviewer_3", "internal_lead": "dr.liu", "created_at": now - timedelta(days=35)},
            {"id": "LN-007", "label_id": "LC-001", "trial_id": EYLEA_TRIAL, "health_authority": "PMDA", "section": LabelSection.INDICATIONS, "proposed_text": "Japanese-specific indication language for treatment of myopic choroidal neovascularization.", "ha_position": "PMDA agrees with proposed language.", "agreed_text": "EYLEA is indicated for treatment of subfoveal choroidal neovascularization due to pathologic myopia.", "status": NegotiationStatus.AGREED, "negotiation_rounds": 1, "regulatory_contact": "pmda_reviewer_1", "internal_lead": "dr.tanaka", "created_at": now - timedelta(days=200)},
            {"id": "LN-008", "label_id": "LC-010", "trial_id": LIBTAYO_TRIAL, "health_authority": "EMA", "section": LabelSection.BOXED_WARNING, "proposed_text": "EU SmPC special warnings section for immune-mediated adverse reactions aligned with FDA boxed warning.", "status": NegotiationStatus.PROPOSED, "negotiation_rounds": 0, "regulatory_contact": "ema_rapporteur_2", "internal_lead": "dr.liu", "created_at": now - timedelta(days=30)},
            {"id": "LN-009", "label_id": "LC-006", "trial_id": DUPIXENT_TRIAL, "health_authority": "Health Canada", "section": LabelSection.DOSAGE, "proposed_text": "Canadian product monograph dosing section aligned with US PI for atopic dermatitis.", "ha_position": "Health Canada requests additional pharmacovigilance plan details.", "status": NegotiationStatus.UNDER_DISCUSSION, "negotiation_rounds": 2, "regulatory_contact": "hc_reviewer_1", "internal_lead": "dr.martinez", "created_at": now - timedelta(days=80)},
            {"id": "LN-010", "label_id": "LC-005", "trial_id": DUPIXENT_TRIAL, "health_authority": "TGA", "section": LabelSection.INDICATIONS, "proposed_text": "Australian PI indication for moderate-to-severe atopic dermatitis aligned with US approval.", "agreed_text": "DUPIXENT is indicated for the treatment of moderate-to-severe atopic dermatitis in adults and adolescents 12 years and older.", "status": NegotiationStatus.AGREED, "negotiation_rounds": 2, "regulatory_contact": "tga_evaluator_1", "internal_lead": "dr.wilson", "created_at": now - timedelta(days=160)},
        ]

        for neg in negotiations_data:
            self._negotiations[neg["id"]] = LabelNegotiation(**neg)

        # --- 12 Label Artworks ---
        artworks_data = [
            {"id": "LA-001", "label_id": "LC-001", "artwork_type": "carton_label", "file_name": "EYLEA_carton_v14_US.ai", "version": "14.0", "status": ArtworkStatus.APPROVED, "dimensions": "120mm x 80mm", "color_model": "CMYK+PMS", "language": "en", "country": "US", "designer": "design_team_lead", "reviewer": "qa_artwork_reviewer", "approved_date": now - timedelta(days=170), "print_specification": "300dpi offset lithography on 18pt C1S", "created_at": now - timedelta(days=210)},
            {"id": "LA-002", "label_id": "LC-001", "artwork_type": "vial_label", "file_name": "EYLEA_vial_v14_US.ai", "version": "14.0", "status": ArtworkStatus.IN_PRODUCTION, "dimensions": "45mm x 30mm", "color_model": "CMYK", "language": "en", "country": "US", "designer": "design_team_lead", "reviewer": "qa_artwork_reviewer", "approved_date": now - timedelta(days=160), "print_specification": "600dpi flexographic on pressure-sensitive label stock", "created_at": now - timedelta(days=200)},
            {"id": "LA-003", "label_id": "LC-001", "artwork_type": "patient_leaflet", "file_name": "EYLEA_PIL_v14_US.pdf", "version": "14.0", "status": ArtworkStatus.PRINT_READY, "dimensions": "A5 folded", "color_model": "CMYK", "language": "en", "country": "US", "designer": "design_team_2", "reviewer": "qa_artwork_reviewer", "approved_date": now - timedelta(days=165), "created_at": now - timedelta(days=205)},
            {"id": "LA-004", "label_id": "LC-005", "artwork_type": "carton_label", "file_name": "DUPIXENT_carton_v21_US.ai", "version": "21.0", "status": ArtworkStatus.APPROVED, "dimensions": "150mm x 100mm", "color_model": "CMYK+PMS", "language": "en", "country": "US", "designer": "design_team_lead", "reviewer": "qa_artwork_reviewer", "approved_date": now - timedelta(days=110), "print_specification": "300dpi offset lithography on 18pt C1S", "created_at": now - timedelta(days=160)},
            {"id": "LA-005", "label_id": "LC-005", "artwork_type": "prefilled_syringe_label", "file_name": "DUPIXENT_syringe_v21_US.ai", "version": "21.0", "status": ArtworkStatus.IN_PRODUCTION, "dimensions": "60mm x 15mm", "color_model": "CMYK", "language": "en", "country": "US", "designer": "design_team_3", "reviewer": "qa_artwork_reviewer", "approved_date": now - timedelta(days=105), "print_specification": "Screen print on polypropylene barrel", "created_at": now - timedelta(days=155)},
            {"id": "LA-006", "label_id": "LC-005", "artwork_type": "patient_leaflet", "file_name": "DUPIXENT_PIL_v21_US.pdf", "version": "21.0", "status": ArtworkStatus.REVIEW, "dimensions": "A4 tri-fold", "color_model": "CMYK", "language": "en", "country": "US", "designer": "design_team_2", "created_at": now - timedelta(days=50)},
            {"id": "LA-007", "label_id": "LC-009", "artwork_type": "carton_label", "file_name": "LIBTAYO_carton_v8_US.ai", "version": "8.0", "status": ArtworkStatus.APPROVED, "dimensions": "130mm x 90mm", "color_model": "CMYK+PMS", "language": "en", "country": "US", "designer": "design_team_lead", "reviewer": "qa_artwork_reviewer", "approved_date": now - timedelta(days=80), "print_specification": "300dpi offset lithography on 18pt C1S", "created_at": now - timedelta(days=140)},
            {"id": "LA-008", "label_id": "LC-009", "artwork_type": "vial_label", "file_name": "LIBTAYO_vial_v8_US.ai", "version": "8.0", "status": ArtworkStatus.PRINT_READY, "dimensions": "50mm x 35mm", "color_model": "CMYK", "language": "en", "country": "US", "designer": "design_team_3", "reviewer": "qa_artwork_reviewer", "approved_date": now - timedelta(days=75), "print_specification": "600dpi flexographic on pressure-sensitive label stock", "created_at": now - timedelta(days=135)},
            {"id": "LA-009", "label_id": "LC-003", "artwork_type": "carton_label", "file_name": "EYLEA_carton_v15_draft.ai", "version": "15.0", "status": ArtworkStatus.DESIGN, "dimensions": "120mm x 80mm", "color_model": "CMYK+PMS", "language": "en", "designer": "design_team_lead", "created_at": now - timedelta(days=30)},
            {"id": "LA-010", "label_id": "LC-007", "artwork_type": "patient_leaflet", "file_name": "DUPIXENT_PIL_v22_draft.pdf", "version": "22.0", "status": ArtworkStatus.DESIGN, "dimensions": "A4 tri-fold", "color_model": "CMYK", "language": "en", "designer": "design_team_2", "created_at": now - timedelta(days=20)},
            {"id": "LA-011", "label_id": "LC-005", "artwork_type": "carton_label", "file_name": "DUPIXENT_carton_v21_JP.ai", "version": "21.0", "status": ArtworkStatus.PROOF, "dimensions": "150mm x 100mm", "color_model": "CMYK+PMS", "language": "ja", "country": "JP", "designer": "design_team_lead", "reviewer": "qa_artwork_reviewer_jp", "created_at": now - timedelta(days=70)},
            {"id": "LA-012", "label_id": "LC-009", "artwork_type": "patient_leaflet", "file_name": "LIBTAYO_PIL_v8_EU.pdf", "version": "8.0", "status": ArtworkStatus.REVIEW, "dimensions": "A5 booklet", "color_model": "CMYK", "language": "en", "country": "EU", "designer": "design_team_2", "created_at": now - timedelta(days=45)},
        ]

        for aw in artworks_data:
            self._artworks[aw["id"]] = LabelArtwork(**aw)

        # --- 12 Label Changes ---
        changes_data = [
            {"id": "LCH-001", "label_id": "LC-001", "trial_id": EYLEA_TRIAL, "change_category": ChangeCategory.SAFETY_UPDATE, "description": "Update warnings section to include post-marketing reports of arterial thromboembolic events.", "affected_sections": [LabelSection.WARNINGS, LabelSection.ADVERSE_REACTIONS], "rationale": "PSUR #14 identified new safety signal requiring label update per FDA guidance.", "safety_impact": True, "regulatory_notification_required": True, "implementation_date": now + timedelta(days=60), "status": "in_progress", "requested_by": "safety_officer", "created_at": now - timedelta(days=90)},
            {"id": "LCH-002", "label_id": "LC-001", "trial_id": EYLEA_TRIAL, "change_category": ChangeCategory.EFFICACY_UPDATE, "description": "Add 96-week efficacy data from PULSAR trial to Clinical Studies section.", "affected_sections": [LabelSection.CLINICAL_STUDIES], "rationale": "Phase 3 PULSAR study 96-week results now available for label update.", "safety_impact": False, "regulatory_notification_required": True, "status": "pending", "requested_by": "clinical_ops", "created_at": now - timedelta(days=60)},
            {"id": "LCH-003", "label_id": "LC-005", "trial_id": DUPIXENT_TRIAL, "change_category": ChangeCategory.NEW_INDICATION, "description": "Add prurigo nodularis indication to prescribing information.", "affected_sections": [LabelSection.INDICATIONS, LabelSection.DOSAGE, LabelSection.CLINICAL_STUDIES], "rationale": "FDA approval of sNDA for prurigo nodularis in adults.", "safety_impact": False, "regulatory_notification_required": True, "implementation_date": now - timedelta(days=30), "status": "completed", "requested_by": "regulatory_affairs", "approved_by": "vp_regulatory", "created_at": now - timedelta(days=180)},
            {"id": "LCH-004", "label_id": "LC-005", "trial_id": DUPIXENT_TRIAL, "change_category": ChangeCategory.SAFETY_UPDATE, "description": "Update conjunctivitis warning language based on new clinical data.", "affected_sections": [LabelSection.WARNINGS, LabelSection.ADVERSE_REACTIONS], "rationale": "Increased conjunctivitis incidence observed in LIBERTY AD trials.", "safety_impact": True, "regulatory_notification_required": True, "status": "in_progress", "requested_by": "safety_officer", "created_at": now - timedelta(days=45)},
            {"id": "LCH-005", "label_id": "LC-009", "trial_id": LIBTAYO_TRIAL, "change_category": ChangeCategory.SAFETY_UPDATE, "description": "Add immune-mediated myocarditis to warnings and adverse reactions.", "affected_sections": [LabelSection.BOXED_WARNING, LabelSection.WARNINGS, LabelSection.ADVERSE_REACTIONS], "rationale": "Post-marketing reports of fatal myocarditis requiring urgent label update.", "safety_impact": True, "regulatory_notification_required": True, "implementation_date": now + timedelta(days=30), "status": "in_progress", "requested_by": "safety_officer", "created_at": now - timedelta(days=50)},
            {"id": "LCH-006", "label_id": "LC-009", "trial_id": LIBTAYO_TRIAL, "change_category": ChangeCategory.NEW_INDICATION, "description": "Add first-line NSCLC indication pending confirmatory trial data.", "affected_sections": [LabelSection.INDICATIONS, LabelSection.DOSAGE, LabelSection.CLINICAL_STUDIES, LabelSection.CLINICAL_PHARMACOLOGY], "rationale": "Accelerated approval pathway for first-line advanced NSCLC.", "safety_impact": False, "regulatory_notification_required": True, "status": "pending", "requested_by": "regulatory_affairs", "created_at": now - timedelta(days=100)},
            {"id": "LCH-007", "label_id": "LC-006", "trial_id": DUPIXENT_TRIAL, "change_category": ChangeCategory.FORMULATION_CHANGE, "description": "Update dosage section for new 200 mg/1.14 mL prefilled pen presentation.", "affected_sections": [LabelSection.DOSAGE, LabelSection.DOSAGE_FORMS], "rationale": "New pen device approved for self-administration convenience.", "safety_impact": False, "regulatory_notification_required": True, "implementation_date": now - timedelta(days=10), "status": "completed", "requested_by": "cmc_team", "approved_by": "vp_regulatory", "created_at": now - timedelta(days=120)},
            {"id": "LCH-008", "label_id": "LC-002", "trial_id": EYLEA_TRIAL, "change_category": ChangeCategory.MANUFACTURING_CHANGE, "description": "Update manufacturing site information in product description.", "affected_sections": [LabelSection.DOSAGE_FORMS], "rationale": "Addition of new manufacturing facility in Limerick, Ireland.", "safety_impact": False, "regulatory_notification_required": True, "status": "completed", "requested_by": "cmc_team", "approved_by": "regulatory_lead", "created_at": now - timedelta(days=200)},
            {"id": "LCH-009", "label_id": "LC-010", "trial_id": LIBTAYO_TRIAL, "change_category": ChangeCategory.ADMINISTRATIVE, "description": "Update NDC codes and packaging configuration for 350 mg/7 mL vial.", "affected_sections": [LabelSection.DOSAGE_FORMS], "rationale": "New packaging configuration for 350 mg single-dose vial.", "safety_impact": False, "regulatory_notification_required": False, "status": "completed", "requested_by": "supply_chain", "approved_by": "regulatory_lead", "created_at": now - timedelta(days=150)},
            {"id": "LCH-010", "label_id": "LC-005", "trial_id": DUPIXENT_TRIAL, "change_category": ChangeCategory.POST_MARKETING, "description": "Add arthralgia as an identified risk in post-marketing experience section.", "affected_sections": [LabelSection.ADVERSE_REACTIONS], "rationale": "Post-marketing surveillance identified arthralgia as associated adverse reaction.", "safety_impact": True, "regulatory_notification_required": True, "status": "pending", "requested_by": "pharmacovigilance_lead", "created_at": now - timedelta(days=35)},
            {"id": "LCH-011", "label_id": "LC-001", "trial_id": EYLEA_TRIAL, "change_category": ChangeCategory.EFFICACY_UPDATE, "description": "Update clinical studies section with PHOTON trial results for extended dosing interval.", "affected_sections": [LabelSection.CLINICAL_STUDIES, LabelSection.DOSAGE], "rationale": "PHOTON trial supports extended dosing of every 12 or 16 weeks.", "safety_impact": False, "regulatory_notification_required": True, "status": "in_progress", "requested_by": "medical_affairs", "created_at": now - timedelta(days=70)},
            {"id": "LCH-012", "label_id": "LC-009", "trial_id": LIBTAYO_TRIAL, "change_category": ChangeCategory.SAFETY_UPDATE, "description": "Update hepatotoxicity warnings with revised monitoring recommendations.", "affected_sections": [LabelSection.WARNINGS], "rationale": "FDA safety communication on immune checkpoint inhibitor hepatotoxicity.", "safety_impact": True, "regulatory_notification_required": True, "status": "pending", "requested_by": "safety_officer", "created_at": now - timedelta(days=25)},
        ]

        for ch in changes_data:
            self._changes[ch["id"]] = LabelChange(**ch)

        # --- 12 Country Labels ---
        country_labels_data = [
            {"id": "CL-001", "label_id": "LC-001", "country": "US", "language": "en", "local_product_name": "EYLEA", "translation_status": "approved", "local_requirements": ["FDA-approved USPI format", "Medication Guide required"], "regulatory_authority": "FDA", "approval_date": now - timedelta(days=180), "implementation_date": now - timedelta(days=170), "responsible_person": "us_regulatory_lead", "created_at": now - timedelta(days=365)},
            {"id": "CL-002", "label_id": "LC-001", "country": "EU", "language": "en", "local_product_name": "Eylea", "translation_status": "approved", "local_requirements": ["EMA SmPC format", "Package leaflet per QRD template"], "regulatory_authority": "EMA", "approval_date": now - timedelta(days=160), "implementation_date": now - timedelta(days=150), "responsible_person": "eu_regulatory_lead", "created_at": now - timedelta(days=350)},
            {"id": "CL-003", "label_id": "LC-001", "country": "JP", "language": "ja", "local_product_name": "Eylea (in Japanese)", "translation_status": "approved", "local_requirements": ["PMDA Japanese PI format", "Patient medication guide in Japanese"], "deviation_from_core": "Additional indication for myopic CNV approved in Japan only.", "regulatory_authority": "PMDA", "approval_date": now - timedelta(days=140), "implementation_date": now - timedelta(days=130), "responsible_person": "jp_regulatory_lead", "created_at": now - timedelta(days=340)},
            {"id": "CL-004", "label_id": "LC-005", "country": "US", "language": "en", "local_product_name": "DUPIXENT", "translation_status": "approved", "local_requirements": ["FDA-approved USPI format", "Medication Guide required", "Instructions for Use (IFU)"], "regulatory_authority": "FDA", "approval_date": now - timedelta(days=120), "implementation_date": now - timedelta(days=110), "responsible_person": "us_regulatory_lead", "created_at": now - timedelta(days=300)},
            {"id": "CL-005", "label_id": "LC-005", "country": "EU", "language": "en", "local_product_name": "Dupixent", "translation_status": "in_progress", "local_requirements": ["EMA SmPC format", "PIL per QRD template", "Blue Box labeling"], "regulatory_authority": "EMA", "responsible_person": "eu_regulatory_lead", "created_at": now - timedelta(days=280)},
            {"id": "CL-006", "label_id": "LC-005", "country": "CN", "language": "zh", "local_product_name": "Dupixent (in Chinese)", "translation_status": "pending", "local_requirements": ["NMPA format", "Chinese language requirements", "Local importer information"], "regulatory_authority": "NMPA", "responsible_person": "cn_regulatory_lead", "created_at": now - timedelta(days=200)},
            {"id": "CL-007", "label_id": "LC-009", "country": "US", "language": "en", "local_product_name": "LIBTAYO", "translation_status": "approved", "local_requirements": ["FDA-approved USPI format", "Medication Guide required"], "regulatory_authority": "FDA", "approval_date": now - timedelta(days=90), "implementation_date": now - timedelta(days=80), "responsible_person": "us_regulatory_lead", "created_at": now - timedelta(days=250)},
            {"id": "CL-008", "label_id": "LC-009", "country": "EU", "language": "en", "local_product_name": "Libtayo", "translation_status": "approved", "local_requirements": ["EMA SmPC format", "PIL per QRD template"], "regulatory_authority": "EMA", "approval_date": now - timedelta(days=70), "implementation_date": now - timedelta(days=60), "responsible_person": "eu_regulatory_lead", "created_at": now - timedelta(days=230)},
            {"id": "CL-009", "label_id": "LC-005", "country": "AU", "language": "en", "local_product_name": "DUPIXENT", "translation_status": "approved", "local_requirements": ["TGA PI format", "Consumer Medicine Information (CMI)"], "regulatory_authority": "TGA", "approval_date": now - timedelta(days=100), "implementation_date": now - timedelta(days=90), "responsible_person": "au_regulatory_lead", "created_at": now - timedelta(days=260)},
            {"id": "CL-010", "label_id": "LC-001", "country": "CA", "language": "en", "local_product_name": "EYLEA", "translation_status": "approved", "local_requirements": ["Health Canada Product Monograph format", "Bilingual labeling (EN/FR)"], "regulatory_authority": "Health Canada", "approval_date": now - timedelta(days=150), "implementation_date": now - timedelta(days=140), "responsible_person": "ca_regulatory_lead", "created_at": now - timedelta(days=330)},
            {"id": "CL-011", "label_id": "LC-001", "country": "BR", "language": "pt", "local_product_name": "Eylea", "translation_status": "in_progress", "local_requirements": ["ANVISA format", "Portuguese language", "Local distributor information"], "regulatory_authority": "ANVISA", "responsible_person": "br_regulatory_lead", "created_at": now - timedelta(days=180)},
            {"id": "CL-012", "label_id": "LC-009", "country": "KR", "language": "ko", "local_product_name": "Libtayo (in Korean)", "translation_status": "pending", "local_requirements": ["MFDS format", "Korean language labeling"], "regulatory_authority": "MFDS", "responsible_person": "kr_regulatory_lead", "created_at": now - timedelta(days=120)},
        ]

        for cl in country_labels_data:
            self._country_labels[cl["id"]] = CountryLabel(**cl)

    # ------------------------------------------------------------------
    # Label Content Management
    # ------------------------------------------------------------------

    def list_labels(
        self,
        *,
        trial_id: str | None = None,
        status: LabelStatus | None = None,
        section: LabelSection | None = None,
    ) -> list[LabelContent]:
        """List label content records with optional filters."""
        with self._lock:
            result = list(self._labels.values())

        if trial_id is not None:
            result = [lbl for lbl in result if lbl.trial_id == trial_id]
        if status is not None:
            result = [lbl for lbl in result if lbl.status == status]
        if section is not None:
            result = [lbl for lbl in result if lbl.section == section]

        return sorted(result, key=lambda lbl: lbl.id)

    def get_label(self, label_id: str) -> LabelContent | None:
        """Get a single label content record by ID."""
        with self._lock:
            return self._labels.get(label_id)

    def create_label(self, payload: LabelContentCreate) -> LabelContent:
        """Create a new label content record."""
        label_id = f"LC-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        label = LabelContent(
            id=label_id,
            trial_id=payload.trial_id,
            product_name=payload.product_name,
            version=payload.version,
            section=payload.section,
            content_text=payload.content_text,
            status=LabelStatus.DRAFT,
            language=payload.language,
            country=payload.country,
            author=payload.author,
            created_at=now,
        )
        with self._lock:
            self._labels[label_id] = label
        logger.info("Created label %s: %s v%s %s", label_id, payload.product_name, payload.version, payload.section.value)
        return label

    def update_label(
        self, label_id: str, payload: LabelContentUpdate
    ) -> LabelContent | None:
        """Update an existing label content record."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._labels.get(label_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set approved_date when approved_by is provided
            if "approved_by" in updates and updates["approved_by"] is not None and existing.approved_date is None:
                updates["approved_date"] = now

            data.update(updates)
            updated = LabelContent(**data)
            self._labels[label_id] = updated
        return updated

    def delete_label(self, label_id: str) -> bool:
        """Delete a label content record. Returns True if deleted."""
        with self._lock:
            if label_id in self._labels:
                del self._labels[label_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Label Negotiation Management
    # ------------------------------------------------------------------

    def list_negotiations(
        self,
        *,
        trial_id: str | None = None,
        label_id: str | None = None,
        status: NegotiationStatus | None = None,
    ) -> list[LabelNegotiation]:
        """List label negotiations with optional filters."""
        with self._lock:
            result = list(self._negotiations.values())

        if trial_id is not None:
            result = [n for n in result if n.trial_id == trial_id]
        if label_id is not None:
            result = [n for n in result if n.label_id == label_id]
        if status is not None:
            result = [n for n in result if n.status == status]

        return sorted(result, key=lambda n: n.id)

    def get_negotiation(self, negotiation_id: str) -> LabelNegotiation | None:
        """Get a single label negotiation by ID."""
        with self._lock:
            return self._negotiations.get(negotiation_id)

    def create_negotiation(self, payload: LabelNegotiationCreate) -> LabelNegotiation:
        """Create a new label negotiation."""
        negotiation_id = f"LN-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        negotiation = LabelNegotiation(
            id=negotiation_id,
            label_id=payload.label_id,
            trial_id=payload.trial_id,
            health_authority=payload.health_authority,
            section=payload.section,
            proposed_text=payload.proposed_text,
            status=NegotiationStatus.PROPOSED,
            negotiation_rounds=0,
            regulatory_contact=payload.regulatory_contact,
            internal_lead=payload.internal_lead,
            created_at=now,
        )
        with self._lock:
            self._negotiations[negotiation_id] = negotiation
        logger.info("Created negotiation %s: label=%s HA=%s", negotiation_id, payload.label_id, payload.health_authority)
        return negotiation

    def update_negotiation(
        self, negotiation_id: str, payload: LabelNegotiationUpdate
    ) -> LabelNegotiation | None:
        """Update an existing label negotiation."""
        with self._lock:
            existing = self._negotiations.get(negotiation_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = LabelNegotiation(**data)
            self._negotiations[negotiation_id] = updated
        return updated

    def delete_negotiation(self, negotiation_id: str) -> bool:
        """Delete a label negotiation. Returns True if deleted."""
        with self._lock:
            if negotiation_id in self._negotiations:
                del self._negotiations[negotiation_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Label Artwork Management
    # ------------------------------------------------------------------

    def list_artworks(
        self,
        *,
        label_id: str | None = None,
        status: ArtworkStatus | None = None,
    ) -> list[LabelArtwork]:
        """List label artworks with optional filters."""
        with self._lock:
            result = list(self._artworks.values())

        if label_id is not None:
            result = [a for a in result if a.label_id == label_id]
        if status is not None:
            result = [a for a in result if a.status == status]

        return sorted(result, key=lambda a: a.id)

    def get_artwork(self, artwork_id: str) -> LabelArtwork | None:
        """Get a single label artwork by ID."""
        with self._lock:
            return self._artworks.get(artwork_id)

    def create_artwork(self, payload: LabelArtworkCreate) -> LabelArtwork:
        """Create a new label artwork."""
        artwork_id = f"LA-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        artwork = LabelArtwork(
            id=artwork_id,
            label_id=payload.label_id,
            artwork_type=payload.artwork_type,
            file_name=payload.file_name,
            version=payload.version,
            status=ArtworkStatus.DESIGN,
            language=payload.language,
            country=payload.country,
            designer=payload.designer,
            created_at=now,
        )
        with self._lock:
            self._artworks[artwork_id] = artwork
        logger.info("Created artwork %s: label=%s file=%s", artwork_id, payload.label_id, payload.file_name)
        return artwork

    def update_artwork(
        self, artwork_id: str, payload: LabelArtworkUpdate
    ) -> LabelArtwork | None:
        """Update an existing label artwork."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._artworks.get(artwork_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set approved_date when status transitions to approved
            if "status" in updates and updates["status"] == ArtworkStatus.APPROVED and existing.approved_date is None:
                updates["approved_date"] = now

            data.update(updates)
            updated = LabelArtwork(**data)
            self._artworks[artwork_id] = updated
        return updated

    def delete_artwork(self, artwork_id: str) -> bool:
        """Delete a label artwork. Returns True if deleted."""
        with self._lock:
            if artwork_id in self._artworks:
                del self._artworks[artwork_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Label Change Management
    # ------------------------------------------------------------------

    def list_changes(
        self,
        *,
        trial_id: str | None = None,
        label_id: str | None = None,
        change_category: ChangeCategory | None = None,
    ) -> list[LabelChange]:
        """List label changes with optional filters."""
        with self._lock:
            result = list(self._changes.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]
        if label_id is not None:
            result = [c for c in result if c.label_id == label_id]
        if change_category is not None:
            result = [c for c in result if c.change_category == change_category]

        return sorted(result, key=lambda c: c.id)

    def get_change(self, change_id: str) -> LabelChange | None:
        """Get a single label change by ID."""
        with self._lock:
            return self._changes.get(change_id)

    def create_change(self, payload: LabelChangeCreate) -> LabelChange:
        """Create a new label change."""
        change_id = f"LCH-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        change = LabelChange(
            id=change_id,
            label_id=payload.label_id,
            trial_id=payload.trial_id,
            change_category=payload.change_category,
            description=payload.description,
            affected_sections=payload.affected_sections,
            rationale=payload.rationale,
            safety_impact=payload.safety_impact,
            status="pending",
            requested_by=payload.requested_by,
            created_at=now,
        )
        with self._lock:
            self._changes[change_id] = change
        logger.info("Created label change %s: %s for label=%s", change_id, payload.change_category.value, payload.label_id)
        return change

    def update_change(
        self, change_id: str, payload: LabelChangeUpdate
    ) -> LabelChange | None:
        """Update an existing label change."""
        with self._lock:
            existing = self._changes.get(change_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = LabelChange(**data)
            self._changes[change_id] = updated
        return updated

    def delete_change(self, change_id: str) -> bool:
        """Delete a label change. Returns True if deleted."""
        with self._lock:
            if change_id in self._changes:
                del self._changes[change_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Country Label Management
    # ------------------------------------------------------------------

    def list_country_labels(
        self,
        *,
        label_id: str | None = None,
        country: str | None = None,
    ) -> list[CountryLabel]:
        """List country labels with optional filters."""
        with self._lock:
            result = list(self._country_labels.values())

        if label_id is not None:
            result = [cl for cl in result if cl.label_id == label_id]
        if country is not None:
            result = [cl for cl in result if cl.country == country]

        return sorted(result, key=lambda cl: cl.id)

    def get_country_label(self, country_label_id: str) -> CountryLabel | None:
        """Get a single country label by ID."""
        with self._lock:
            return self._country_labels.get(country_label_id)

    def create_country_label(self, payload: CountryLabelCreate) -> CountryLabel:
        """Create a new country label."""
        country_label_id = f"CL-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        country_label = CountryLabel(
            id=country_label_id,
            label_id=payload.label_id,
            country=payload.country,
            language=payload.language,
            local_product_name=payload.local_product_name,
            translation_status="pending",
            local_requirements=payload.local_requirements,
            regulatory_authority=payload.regulatory_authority,
            responsible_person=payload.responsible_person,
            created_at=now,
        )
        with self._lock:
            self._country_labels[country_label_id] = country_label
        logger.info("Created country label %s: label=%s country=%s", country_label_id, payload.label_id, payload.country)
        return country_label

    def update_country_label(
        self, country_label_id: str, payload: CountryLabelUpdate
    ) -> CountryLabel | None:
        """Update an existing country label."""
        with self._lock:
            existing = self._country_labels.get(country_label_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CountryLabel(**data)
            self._country_labels[country_label_id] = updated
        return updated

    def delete_country_label(self, country_label_id: str) -> bool:
        """Delete a country label. Returns True if deleted."""
        with self._lock:
            if country_label_id in self._country_labels:
                del self._country_labels[country_label_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> LabelingMetrics:
        """Compute aggregated labeling management metrics."""
        with self._lock:
            labels = list(self._labels.values())
            negotiations = list(self._negotiations.values())
            artworks = list(self._artworks.values())
            changes = list(self._changes.values())
            country_labels = list(self._country_labels.values())

        if trial_id is not None:
            labels = [lbl for lbl in labels if lbl.trial_id == trial_id]
            negotiations = [n for n in negotiations if n.trial_id == trial_id]
            changes = [c for c in changes if c.trial_id == trial_id]
            # Artworks and country labels are filtered by label_id belonging to trial
            trial_label_ids = {lbl.id for lbl in labels}
            artworks = [a for a in artworks if a.label_id in trial_label_ids]
            country_labels = [cl for cl in country_labels if cl.label_id in trial_label_ids]

        # Labels by status
        labels_by_status: dict[str, int] = {}
        for lbl in labels:
            key = lbl.status.value
            labels_by_status[key] = labels_by_status.get(key, 0) + 1

        # Labels by section
        labels_by_section: dict[str, int] = {}
        for lbl in labels:
            key = lbl.section.value
            labels_by_section[key] = labels_by_section.get(key, 0) + 1

        # Negotiations by status
        negotiations_by_status: dict[str, int] = {}
        for n in negotiations:
            key = n.status.value
            negotiations_by_status[key] = negotiations_by_status.get(key, 0) + 1

        # Average negotiation rounds
        if negotiations:
            avg_rounds = sum(n.negotiation_rounds for n in negotiations) / len(negotiations)
        else:
            avg_rounds = 0.0

        # Artworks by status
        artworks_by_status: dict[str, int] = {}
        for a in artworks:
            key = a.status.value
            artworks_by_status[key] = artworks_by_status.get(key, 0) + 1

        # Changes by category
        changes_by_category: dict[str, int] = {}
        for c in changes:
            key = c.change_category.value
            changes_by_category[key] = changes_by_category.get(key, 0) + 1

        safety_changes = sum(1 for c in changes if c.safety_impact)

        # Countries covered
        countries = {cl.country for cl in country_labels}

        return LabelingMetrics(
            total_labels=len(labels),
            labels_by_status=labels_by_status,
            labels_by_section=labels_by_section,
            total_negotiations=len(negotiations),
            negotiations_by_status=negotiations_by_status,
            avg_negotiation_rounds=round(avg_rounds, 1),
            total_artworks=len(artworks),
            artworks_by_status=artworks_by_status,
            total_changes=len(changes),
            changes_by_category=changes_by_category,
            safety_changes=safety_changes,
            total_country_labels=len(country_labels),
            countries_covered=len(countries),
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: LabelingManagementService | None = None
_instance_lock = threading.Lock()


def get_labeling_management_service() -> LabelingManagementService:
    """Return the singleton LabelingManagementService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = LabelingManagementService()
    return _instance


def reset_labeling_management_service() -> LabelingManagementService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = LabelingManagementService()
    return _instance
