"""Biomarker Analysis & Real-World Evidence Service (VP-DS-9).

Pharma-grade biomarker management and RWE platform for clinical trial
patient recruitment.  Covers biomarker discovery/validation lifecycle,
association analysis, patient biomarker recording, panel management,
RWE study design, propensity score matching, RWE-RCT comparability,
patient stratification, and enrichment analysis.

Usage:
    from app.services.biomarker_analysis_service import (
        get_biomarker_analysis_service,
    )

    svc = get_biomarker_analysis_service()
    biomarkers = svc.list_biomarkers()
"""

from __future__ import annotations

import logging
import math
import random
import statistics
import threading
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from app.schemas.biomarker_analysis import (
    AssociationCreateRequest,
    Biomarker,
    BiomarkerAssociation,
    BiomarkerCreateRequest,
    BiomarkerMetrics,
    BiomarkerPanel,
    BiomarkerRole,
    BiomarkerStatus,
    BiomarkerStratificationResult,
    BiomarkerType,
    ComparabilityCreateRequest,
    EnrichmentResult,
    EvidenceLevel,
    MatchingMethod,
    PanelCreateRequest,
    PatientBiomarkerRequest,
    PatientBiomarkerValue,
    PropensityScoreResult,
    RWEComparability,
    RWEMetrics,
    RWEStudy,
    RWEStudyCreateRequest,
    RWEStudyType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Trial / Patient ID constants (matching adverse_event_service)
# ---------------------------------------------------------------------------

EYLEA_TRIAL_ID = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL_ID = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL_ID = "00000000-de00-0003-0000-000000000003"

PATIENT_IDS = [f"PAT-{i:04d}" for i in range(1, 11)]


class BiomarkerAnalysisService:
    """In-memory biomarker analysis and RWE engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._biomarkers: dict[str, Biomarker] = {}
        self._associations: dict[str, BiomarkerAssociation] = {}
        self._patient_values: dict[str, PatientBiomarkerValue] = {}
        self._panels: dict[str, BiomarkerPanel] = {}
        self._rwe_studies: dict[str, RWEStudy] = {}
        self._comparabilities: dict[str, RWEComparability] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data seeding
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate Regeneron-specific biomarker and RWE data."""
        now = datetime.now(timezone.utc)
        today = now.date()

        # ----- 12 Biomarkers -----
        biomarkers_data = [
            # DME / EYLEA biomarkers
            {
                "id": "BM-0001", "name": "VEGF-A",
                "biomarker_type": BiomarkerType.PROTEOMIC,
                "role": BiomarkerRole.PREDICTIVE,
                "description": "Vascular endothelial growth factor A - primary target of aflibercept (EYLEA)",
                "protein_target": "VEGF-A",
                "measurement_unit": "pg/mL",
                "normal_range_low": 10.0, "normal_range_high": 50.0,
                "clinical_significance": "Elevated levels predict anti-VEGF treatment response in DME",
                "evidence_level": EvidenceLevel.LEVEL_1A,
                "status": BiomarkerStatus.APPROVED,
                "associated_conditions": ["Diabetic Macular Edema", "Wet AMD", "DME"],
                "associated_trials": [EYLEA_TRIAL_ID],
                "sensitivity": 0.89, "specificity": 0.82, "auc_roc": 0.91,
            },
            {
                "id": "BM-0002", "name": "HbA1c",
                "biomarker_type": BiomarkerType.CLINICAL_MEASUREMENT,
                "role": BiomarkerRole.PROGNOSTIC,
                "description": "Glycated hemoglobin - measures average blood sugar over 2-3 months",
                "measurement_unit": "%",
                "normal_range_low": 4.0, "normal_range_high": 5.6,
                "clinical_significance": "Higher HbA1c correlates with DME severity and treatment resistance",
                "evidence_level": EvidenceLevel.LEVEL_1B,
                "status": BiomarkerStatus.APPROVED,
                "associated_conditions": ["Diabetic Macular Edema", "Type 2 Diabetes"],
                "associated_trials": [EYLEA_TRIAL_ID],
                "sensitivity": 0.78, "specificity": 0.85, "auc_roc": 0.84,
            },
            {
                "id": "BM-0003", "name": "Central Retinal Thickness",
                "biomarker_type": BiomarkerType.IMAGING,
                "role": BiomarkerRole.SURROGATE_ENDPOINT,
                "description": "OCT-measured central subfield thickness of the retina",
                "measurement_unit": "um",
                "normal_range_low": 200.0, "normal_range_high": 300.0,
                "clinical_significance": "Primary anatomic endpoint in DME trials; reduction indicates treatment response",
                "evidence_level": EvidenceLevel.LEVEL_1A,
                "status": BiomarkerStatus.QUALIFIED,
                "associated_conditions": ["Diabetic Macular Edema"],
                "associated_trials": [EYLEA_TRIAL_ID],
                "sensitivity": 0.92, "specificity": 0.88, "auc_roc": 0.94,
            },
            {
                "id": "BM-0004", "name": "Visual Acuity BCVA",
                "biomarker_type": BiomarkerType.CLINICAL_MEASUREMENT,
                "role": BiomarkerRole.SURROGATE_ENDPOINT,
                "description": "Best-corrected visual acuity measured in ETDRS letters",
                "measurement_unit": "ETDRS letters",
                "normal_range_low": 70.0, "normal_range_high": 85.0,
                "clinical_significance": "Primary functional endpoint in retinal disease trials",
                "evidence_level": EvidenceLevel.LEVEL_1A,
                "status": BiomarkerStatus.APPROVED,
                "associated_conditions": ["Diabetic Macular Edema", "Wet AMD"],
                "associated_trials": [EYLEA_TRIAL_ID],
                "sensitivity": 0.85, "specificity": 0.80, "auc_roc": 0.87,
            },
            # Atopic Dermatitis / Dupixent biomarkers
            {
                "id": "BM-0005", "name": "IgE Total",
                "biomarker_type": BiomarkerType.PROTEOMIC,
                "role": BiomarkerRole.DIAGNOSTIC,
                "description": "Total immunoglobulin E - marker of atopic disease burden",
                "protein_target": "IgE",
                "measurement_unit": "IU/mL",
                "normal_range_low": 0.0, "normal_range_high": 100.0,
                "clinical_significance": "Elevated IgE supports atopic dermatitis diagnosis and severity assessment",
                "evidence_level": EvidenceLevel.LEVEL_2A,
                "status": BiomarkerStatus.VALIDATED,
                "associated_conditions": ["Atopic Dermatitis", "Asthma", "Allergic Rhinitis"],
                "associated_trials": [DUPIXENT_TRIAL_ID],
                "sensitivity": 0.75, "specificity": 0.70, "auc_roc": 0.78,
            },
            {
                "id": "BM-0006", "name": "EASI Score",
                "biomarker_type": BiomarkerType.COMPOSITE,
                "role": BiomarkerRole.PHARMACODYNAMIC,
                "description": "Eczema Area and Severity Index - composite clinical severity score",
                "measurement_unit": "score",
                "normal_range_low": 0.0, "normal_range_high": 7.0,
                "clinical_significance": "Standard endpoint for AD treatment trials; EASI-75 is a key response metric",
                "evidence_level": EvidenceLevel.LEVEL_1A,
                "status": BiomarkerStatus.APPROVED,
                "associated_conditions": ["Atopic Dermatitis"],
                "associated_trials": [DUPIXENT_TRIAL_ID],
                "sensitivity": 0.88, "specificity": 0.84, "auc_roc": 0.90,
            },
            {
                "id": "BM-0007", "name": "Thymus and Activation-Regulated Chemokine (TARC)",
                "biomarker_type": BiomarkerType.PROTEOMIC,
                "role": BiomarkerRole.PHARMACODYNAMIC,
                "description": "CCL17/TARC - Type 2 inflammation biomarker, rapidly responsive to dupilumab",
                "protein_target": "CCL17",
                "measurement_unit": "pg/mL",
                "normal_range_low": 0.0, "normal_range_high": 450.0,
                "clinical_significance": "Rapid decline post-dupilumab initiation predicts clinical response",
                "evidence_level": EvidenceLevel.LEVEL_1B,
                "status": BiomarkerStatus.VALIDATED,
                "associated_conditions": ["Atopic Dermatitis"],
                "associated_trials": [DUPIXENT_TRIAL_ID],
                "sensitivity": 0.82, "specificity": 0.79, "auc_roc": 0.85,
            },
            # CSCC / Libtayo biomarkers
            {
                "id": "BM-0008", "name": "PD-L1 Expression",
                "biomarker_type": BiomarkerType.PROTEOMIC,
                "role": BiomarkerRole.PREDICTIVE,
                "description": "Programmed death-ligand 1 expression by IHC (CPS or TPS)",
                "protein_target": "PD-L1",
                "measurement_unit": "CPS",
                "normal_range_low": 0.0, "normal_range_high": 1.0,
                "clinical_significance": "Higher PD-L1 expression associated with improved cemiplimab response in CSCC",
                "evidence_level": EvidenceLevel.LEVEL_2A,
                "status": BiomarkerStatus.QUALIFIED,
                "associated_conditions": ["Cutaneous Squamous Cell Carcinoma", "NSCLC", "CSCC"],
                "associated_trials": [LIBTAYO_TRIAL_ID],
                "sensitivity": 0.72, "specificity": 0.68, "auc_roc": 0.75,
            },
            {
                "id": "BM-0009", "name": "Tumor Mutation Burden",
                "biomarker_type": BiomarkerType.GENOMIC,
                "role": BiomarkerRole.PREDICTIVE,
                "description": "Total number of somatic mutations per megabase of genome",
                "gene_symbol": "TMB",
                "measurement_unit": "mut/Mb",
                "normal_range_low": 0.0, "normal_range_high": 10.0,
                "clinical_significance": "High TMB (>10 mut/Mb) predicts immunotherapy response",
                "evidence_level": EvidenceLevel.LEVEL_2B,
                "status": BiomarkerStatus.VALIDATED,
                "associated_conditions": ["Cutaneous Squamous Cell Carcinoma", "NSCLC", "Melanoma"],
                "associated_trials": [LIBTAYO_TRIAL_ID],
                "sensitivity": 0.65, "specificity": 0.73, "auc_roc": 0.72,
            },
            {
                "id": "BM-0010", "name": "CD8+ TIL Density",
                "biomarker_type": BiomarkerType.PROTEOMIC,
                "role": BiomarkerRole.PROGNOSTIC,
                "description": "Density of CD8+ tumor-infiltrating lymphocytes",
                "protein_target": "CD8",
                "measurement_unit": "cells/mm2",
                "normal_range_low": 50.0, "normal_range_high": 500.0,
                "clinical_significance": "High CD8+ TIL density associated with better prognosis and immunotherapy response",
                "evidence_level": EvidenceLevel.LEVEL_2A,
                "status": BiomarkerStatus.VALIDATED,
                "associated_conditions": ["Cutaneous Squamous Cell Carcinoma", "Melanoma"],
                "associated_trials": [LIBTAYO_TRIAL_ID],
                "sensitivity": 0.70, "specificity": 0.75, "auc_roc": 0.77,
            },
            # Cross-cutting biomarkers
            {
                "id": "BM-0011", "name": "IL-4/IL-13 Signaling Biomarker",
                "biomarker_type": BiomarkerType.PROTEOMIC,
                "role": BiomarkerRole.PREDICTIVE,
                "description": "Composite type 2 cytokine signaling marker",
                "protein_target": "IL-4R/IL-13",
                "measurement_unit": "pg/mL",
                "normal_range_low": 0.0, "normal_range_high": 30.0,
                "clinical_significance": "Elevated IL-4/IL-13 signaling predicts dupilumab response",
                "evidence_level": EvidenceLevel.LEVEL_2A,
                "status": BiomarkerStatus.DISCOVERED,
                "associated_conditions": ["Atopic Dermatitis", "Asthma", "Eosinophilic Esophagitis"],
                "associated_trials": [DUPIXENT_TRIAL_ID],
                "sensitivity": 0.68, "specificity": 0.72, "auc_roc": 0.74,
            },
            {
                "id": "BM-0012", "name": "Anti-Drug Antibodies",
                "biomarker_type": BiomarkerType.PROTEOMIC,
                "role": BiomarkerRole.SAFETY,
                "description": "Antibodies developed against biologic therapeutic agents",
                "protein_target": "ADA",
                "measurement_unit": "titer",
                "normal_range_low": 0.0, "normal_range_high": 1.0,
                "clinical_significance": "ADA development may reduce drug efficacy and increase adverse events",
                "evidence_level": EvidenceLevel.LEVEL_1B,
                "status": BiomarkerStatus.APPROVED,
                "associated_conditions": ["Immunogenicity", "Treatment Failure"],
                "associated_trials": [EYLEA_TRIAL_ID, DUPIXENT_TRIAL_ID, LIBTAYO_TRIAL_ID],
                "sensitivity": 0.90, "specificity": 0.95, "auc_roc": 0.96,
            },
        ]

        for bd in biomarkers_data:
            self._biomarkers[bd["id"]] = Biomarker(
                created_at=now,
                updated_at=now,
                **bd,
            )

        # ----- 15 Biomarker Associations -----
        associations_data = [
            ("BA-0001", "BM-0001", "Diabetic Macular Edema", 0.72, 0.001, (0.55, 0.89), 450, "VIVID/VISTA Phase 3", "DME patients"),
            ("BA-0002", "BM-0001", "Wet AMD", 0.68, 0.003, (0.48, 0.88), 380, "VIEW 1/2", "nAMD patients"),
            ("BA-0003", "BM-0002", "Diabetic Macular Edema", -0.45, 0.01, (-0.62, -0.28), 320, "PHOTON", "Type 2 DM with DME"),
            ("BA-0004", "BM-0003", "Diabetic Macular Edema", 0.85, 0.0001, (0.78, 0.92), 500, "YOSEMITE/RHINE", "All DME"),
            ("BA-0005", "BM-0004", "Diabetic Macular Edema", 0.78, 0.0005, (0.65, 0.91), 480, "PHOTON Extension", "DME on aflibercept"),
            ("BA-0006", "BM-0005", "Atopic Dermatitis", 0.52, 0.02, (0.35, 0.69), 290, "LIBERTY AD SOLO", "Moderate-to-severe AD"),
            ("BA-0007", "BM-0006", "Atopic Dermatitis", 0.91, 0.0001, (0.86, 0.96), 600, "LIBERTY AD CHRONOS", "AD EASI >= 16"),
            ("BA-0008", "BM-0007", "Atopic Dermatitis", 0.65, 0.005, (0.48, 0.82), 350, "LIBERTY AD SOLO 2", "Adult AD patients"),
            ("BA-0009", "BM-0008", "Cutaneous Squamous Cell Carcinoma", 0.48, 0.03, (0.28, 0.68), 200, "EMPOWER-CSCC-1", "Advanced CSCC"),
            ("BA-0010", "BM-0009", "Cutaneous Squamous Cell Carcinoma", 0.55, 0.01, (0.38, 0.72), 180, "EMPOWER-CSCC-1", "Metastatic CSCC"),
            ("BA-0011", "BM-0010", "Cutaneous Squamous Cell Carcinoma", 0.62, 0.008, (0.45, 0.79), 220, "EMPOWER-CSCC-2", "Locally advanced CSCC"),
            ("BA-0012", "BM-0011", "Atopic Dermatitis", 0.58, 0.015, (0.40, 0.76), 270, "Phase 2 Biomarker Study", "Type 2 high AD"),
            ("BA-0013", "BM-0012", "Immunogenicity", -0.35, 0.04, (-0.55, -0.15), 150, "Long-term safety pool", "All biologic recipients"),
            ("BA-0014", "BM-0003", "Wet AMD", 0.80, 0.0002, (0.72, 0.88), 420, "VIEW Extension", "nAMD on anti-VEGF"),
            ("BA-0015", "BM-0006", "Asthma", 0.42, 0.05, (0.22, 0.62), 180, "DRI12544", "Uncontrolled asthma"),
        ]

        for ad in associations_data:
            self._associations[ad[0]] = BiomarkerAssociation(
                id=ad[0], biomarker_id=ad[1], condition=ad[2],
                effect_size=ad[3], p_value=ad[4],
                confidence_interval=ad[5], sample_size=ad[6],
                study_reference=ad[7], population=ad[8],
            )

        # ----- 30 Patient Biomarker Values across 10 patients -----
        random.seed(42)
        pv_counter = 0
        for i, pid in enumerate(PATIENT_IDS):
            # Each patient gets 3 biomarker measurements
            bm_subset = [
                ("BM-0001", 15.0, 120.0),   # VEGF-A
                ("BM-0002", 4.5, 12.0),      # HbA1c
                ("BM-0003", 180.0, 550.0),   # CRT
                ("BM-0005", 20.0, 2500.0),   # IgE
                ("BM-0006", 0.0, 72.0),      # EASI
                ("BM-0008", 0.0, 100.0),     # PD-L1
            ]
            # Pick 3 biomarkers for this patient
            chosen = bm_subset[i % len(bm_subset): i % len(bm_subset) + 3]
            if len(chosen) < 3:
                chosen = chosen + bm_subset[:3 - len(chosen)]

            for bm_id, low, high in chosen:
                pv_counter += 1
                val = round(random.uniform(low, high), 2)
                bm = self._biomarkers.get(bm_id)
                is_abn = False
                if bm and bm.normal_range_high is not None:
                    is_abn = val > bm.normal_range_high
                if bm and bm.normal_range_low is not None:
                    is_abn = is_abn or val < bm.normal_range_low

                pv_id = f"PBV-{pv_counter:04d}"
                self._patient_values[pv_id] = PatientBiomarkerValue(
                    id=pv_id,
                    patient_id=pid,
                    biomarker_id=bm_id,
                    value=val,
                    measurement_date=today - timedelta(days=random.randint(1, 90)),
                    source="EHR Import",
                    is_abnormal=is_abn,
                )

        # ----- 3 Biomarker Panels -----
        self._panels["PNL-0001"] = BiomarkerPanel(
            id="PNL-0001",
            name="DME Progression Panel",
            description="Biomarker panel for predicting DME progression and anti-VEGF response",
            biomarkers=["BM-0001", "BM-0002", "BM-0003", "BM-0004"],
            target_condition="Diabetic Macular Edema",
            panel_sensitivity=0.93,
            panel_specificity=0.87,
            created_at=now,
        )
        self._panels["PNL-0002"] = BiomarkerPanel(
            id="PNL-0002",
            name="AD Severity Panel",
            description="Composite assessment panel for atopic dermatitis severity and Dupixent eligibility",
            biomarkers=["BM-0005", "BM-0006", "BM-0007", "BM-0011"],
            target_condition="Atopic Dermatitis",
            panel_sensitivity=0.90,
            panel_specificity=0.85,
            created_at=now,
        )
        self._panels["PNL-0003"] = BiomarkerPanel(
            id="PNL-0003",
            name="CSCC Immunotherapy Response Panel",
            description="Biomarker panel for predicting cemiplimab (Libtayo) response in CSCC",
            biomarkers=["BM-0008", "BM-0009", "BM-0010"],
            target_condition="Cutaneous Squamous Cell Carcinoma",
            panel_sensitivity=0.80,
            panel_specificity=0.78,
            created_at=now,
        )

        # ----- 4 RWE Studies -----
        self._rwe_studies["RWE-0001"] = RWEStudy(
            id="RWE-0001",
            title="DME Treatment Outcomes in Real-World Clinical Practice",
            study_type=RWEStudyType.RETROSPECTIVE_COHORT,
            description="Retrospective analysis of aflibercept treatment outcomes in DME patients from US claims data",
            data_source="Optum Claims Database",
            sample_size=12500,
            study_period_start=today - timedelta(days=1095),
            study_period_end=today - timedelta(days=30),
            primary_endpoint="Change in BCVA at 12 months",
            matching_method=MatchingMethod.PROPENSITY_SCORE,
            covariates=["age", "sex", "baseline_bcva", "hba1c", "diabetes_duration", "prior_treatment"],
            results_summary="Aflibercept 8mg demonstrated non-inferior visual acuity gains vs 2mg in real-world DME patients",
            treatment_effect=0.85,
            confidence_interval=(0.72, 0.98),
            p_value=0.001,
            bias_assessment="Moderate risk - residual confounding from unmeasured variables",
            limitations=["Claims data lacks clinical detail", "No randomization", "Selection bias possible"],
            created_at=now,
            status="COMPLETED",
        )
        self._rwe_studies["RWE-0002"] = RWEStudy(
            id="RWE-0002",
            title="Dupixent Real-World Effectiveness in Atopic Dermatitis",
            study_type=RWEStudyType.PROSPECTIVE_COHORT,
            description="Prospective registry study of dupilumab effectiveness in moderate-to-severe AD",
            data_source="PROSE Registry",
            sample_size=3200,
            study_period_start=today - timedelta(days=730),
            study_period_end=today,
            primary_endpoint="EASI-75 response at 16 weeks",
            matching_method=MatchingMethod.INVERSE_PROBABILITY_WEIGHTING,
            covariates=["age", "sex", "baseline_easi", "prior_systemic", "ige_level", "disease_duration"],
            results_summary="65.2% of patients achieved EASI-75 at 16 weeks, consistent with RCT findings",
            treatment_effect=0.78,
            confidence_interval=(0.70, 0.86),
            p_value=0.0001,
            bias_assessment="Low risk - prospective design with standardized data collection",
            limitations=["Single-arm design", "No concurrent control", "Adherent population bias"],
            created_at=now,
            status="COMPLETED",
        )
        self._rwe_studies["RWE-0003"] = RWEStudy(
            id="RWE-0003",
            title="Cemiplimab 2nd-Line CSCC Real-World Response",
            study_type=RWEStudyType.RETROSPECTIVE_COHORT,
            description="Retrospective analysis of cemiplimab outcomes in 2nd-line advanced CSCC",
            data_source="Flatiron Health EHR Database",
            sample_size=850,
            study_period_start=today - timedelta(days=900),
            study_period_end=today - timedelta(days=60),
            primary_endpoint="Overall response rate",
            matching_method=MatchingMethod.COARSENED_EXACT,
            covariates=["age", "ecog_status", "prior_therapy", "tumor_stage", "pd_l1_status"],
            results_summary="ORR of 42.3% in 2nd-line CSCC, with durable responses in PD-L1 high patients",
            treatment_effect=0.65,
            confidence_interval=(0.52, 0.78),
            p_value=0.005,
            bias_assessment="Moderate risk - selection bias in EHR data",
            limitations=["Retrospective design", "Missing PD-L1 data in 30% of patients", "Short follow-up"],
            created_at=now,
            status="COMPLETED",
        )
        self._rwe_studies["RWE-0004"] = RWEStudy(
            id="RWE-0004",
            title="Comparative Effectiveness: Anti-VEGF Agents in DME",
            study_type=RWEStudyType.TARGET_TRIAL_EMULATION,
            description="Target trial emulation comparing aflibercept vs ranibizumab in treatment-naive DME",
            data_source="IRIS Registry (AAO)",
            sample_size=28000,
            study_period_start=today - timedelta(days=1460),
            study_period_end=today - timedelta(days=90),
            primary_endpoint="Change in visual acuity at 24 months",
            matching_method=MatchingMethod.PROPENSITY_SCORE,
            covariates=["age", "sex", "race", "baseline_va", "crt", "lens_status", "prior_laser"],
            results_summary="Aflibercept associated with slightly greater VA gains at 24 months (1.2 letters, 95% CI: 0.3-2.1)",
            treatment_effect=0.92,
            confidence_interval=(0.85, 0.99),
            p_value=0.02,
            bias_assessment="Low-moderate risk - large sample with robust matching",
            limitations=["Observational design", "Potential channeling bias", "Missing OCT data"],
            created_at=now,
            status="ACTIVE",
        )

        # ----- 2 RWE-RCT Comparability Assessments -----
        self._comparabilities["CMP-0001"] = RWEComparability(
            id="CMP-0001",
            rwe_study_id="RWE-0001",
            rct_reference="PHOTON Phase 3 (NCT04429503)",
            endpoint_comparison="BCVA change from baseline at 48 weeks",
            rwe_effect_size=0.85,
            rct_effect_size=0.92,
            agreement_score=0.88,
            assessment_notes="RWE effect size within 10% of RCT estimate; population differences in baseline HbA1c noted",
        )
        self._comparabilities["CMP-0002"] = RWEComparability(
            id="CMP-0002",
            rwe_study_id="RWE-0002",
            rct_reference="LIBERTY AD CHRONOS (NCT02260986)",
            endpoint_comparison="EASI-75 response rate at 16 weeks",
            rwe_effect_size=0.78,
            rct_effect_size=0.82,
            agreement_score=0.92,
            assessment_notes="Excellent agreement; RWE population older on average but similar disease severity at baseline",
        )

        logger.info(
            "Biomarker analysis service seeded: %d biomarkers, %d associations, "
            "%d patient values, %d panels, %d RWE studies, %d comparabilities",
            len(self._biomarkers),
            len(self._associations),
            len(self._patient_values),
            len(self._panels),
            len(self._rwe_studies),
            len(self._comparabilities),
        )

    # ------------------------------------------------------------------
    # Biomarker CRUD
    # ------------------------------------------------------------------

    def list_biomarkers(
        self,
        biomarker_type: Optional[BiomarkerType] = None,
        role: Optional[BiomarkerRole] = None,
        status: Optional[BiomarkerStatus] = None,
    ) -> list[Biomarker]:
        """List all biomarkers with optional filters."""
        results = list(self._biomarkers.values())
        if biomarker_type:
            results = [b for b in results if b.biomarker_type == biomarker_type]
        if role:
            results = [b for b in results if b.role == role]
        if status:
            results = [b for b in results if b.status == status]
        return results

    def get_biomarker(self, biomarker_id: str) -> Optional[Biomarker]:
        """Get a single biomarker by ID."""
        return self._biomarkers.get(biomarker_id)

    def create_biomarker(self, req: BiomarkerCreateRequest) -> Biomarker:
        """Create a new biomarker."""
        now = datetime.now(timezone.utc)
        with self._lock:
            bm_id = f"BM-{len(self._biomarkers) + 1:04d}"
            while bm_id in self._biomarkers:
                bm_id = f"BM-{int(bm_id.split('-')[1]) + 1:04d}"
            bm = Biomarker(
                id=bm_id,
                name=req.name,
                biomarker_type=req.biomarker_type,
                role=req.role,
                description=req.description,
                gene_symbol=req.gene_symbol,
                protein_target=req.protein_target,
                measurement_unit=req.measurement_unit,
                normal_range_low=req.normal_range_low,
                normal_range_high=req.normal_range_high,
                clinical_significance=req.clinical_significance,
                evidence_level=req.evidence_level,
                status=BiomarkerStatus.DISCOVERED,
                associated_conditions=req.associated_conditions,
                associated_trials=req.associated_trials,
                sensitivity=req.sensitivity,
                specificity=req.specificity,
                auc_roc=req.auc_roc,
                created_at=now,
                updated_at=now,
            )
            self._biomarkers[bm_id] = bm
        return bm

    def update_biomarker_status(
        self, biomarker_id: str, new_status: BiomarkerStatus
    ) -> Optional[Biomarker]:
        """Advance biomarker through its lifecycle."""
        with self._lock:
            bm = self._biomarkers.get(biomarker_id)
            if bm is None:
                return None
            # Validate lifecycle transitions
            valid_transitions: dict[BiomarkerStatus, list[BiomarkerStatus]] = {
                BiomarkerStatus.DISCOVERED: [BiomarkerStatus.VALIDATED, BiomarkerStatus.REJECTED],
                BiomarkerStatus.VALIDATED: [BiomarkerStatus.QUALIFIED, BiomarkerStatus.REJECTED],
                BiomarkerStatus.QUALIFIED: [BiomarkerStatus.APPROVED, BiomarkerStatus.REJECTED],
                BiomarkerStatus.APPROVED: [BiomarkerStatus.REJECTED],
                BiomarkerStatus.REJECTED: [],
            }
            if new_status not in valid_transitions.get(bm.status, []):
                return None
            updated = bm.model_copy(
                update={"status": new_status, "updated_at": datetime.now(timezone.utc)}
            )
            self._biomarkers[biomarker_id] = updated
        return updated

    def delete_biomarker(self, biomarker_id: str) -> bool:
        """Delete a biomarker."""
        with self._lock:
            if biomarker_id in self._biomarkers:
                del self._biomarkers[biomarker_id]
                return True
        return False

    # ------------------------------------------------------------------
    # Association analysis
    # ------------------------------------------------------------------

    def create_association(self, req: AssociationCreateRequest) -> Optional[BiomarkerAssociation]:
        """Create a biomarker-condition association."""
        if req.biomarker_id not in self._biomarkers:
            return None
        with self._lock:
            assoc_id = f"BA-{len(self._associations) + 1:04d}"
            while assoc_id in self._associations:
                assoc_id = f"BA-{int(assoc_id.split('-')[1]) + 1:04d}"
            assoc = BiomarkerAssociation(
                id=assoc_id,
                biomarker_id=req.biomarker_id,
                condition=req.condition,
                effect_size=req.effect_size,
                p_value=req.p_value,
                confidence_interval=req.confidence_interval,
                sample_size=req.sample_size,
                study_reference=req.study_reference,
                population=req.population,
            )
            self._associations[assoc_id] = assoc
        return assoc

    def get_associations_by_biomarker(self, biomarker_id: str) -> list[BiomarkerAssociation]:
        """Get all associations for a specific biomarker."""
        return [a for a in self._associations.values() if a.biomarker_id == biomarker_id]

    def get_associations_by_condition(self, condition: str) -> list[BiomarkerAssociation]:
        """Get all associations for a specific condition."""
        condition_lower = condition.lower()
        return [a for a in self._associations.values() if condition_lower in a.condition.lower()]

    def list_associations(self) -> list[BiomarkerAssociation]:
        """List all associations."""
        return list(self._associations.values())

    # ------------------------------------------------------------------
    # Patient biomarker values
    # ------------------------------------------------------------------

    def record_patient_biomarker(self, req: PatientBiomarkerRequest) -> Optional[PatientBiomarkerValue]:
        """Record a biomarker measurement for a patient."""
        bm = self._biomarkers.get(req.biomarker_id)
        if bm is None:
            return None

        is_abn = False
        if bm.normal_range_high is not None:
            is_abn = req.value > bm.normal_range_high
        if bm.normal_range_low is not None:
            is_abn = is_abn or req.value < bm.normal_range_low

        mdate = req.measurement_date or date.today()

        with self._lock:
            pv_id = f"PBV-{len(self._patient_values) + 1:04d}"
            while pv_id in self._patient_values:
                pv_id = f"PBV-{int(pv_id.split('-')[1]) + 1:04d}"
            pv = PatientBiomarkerValue(
                id=pv_id,
                patient_id=req.patient_id,
                biomarker_id=req.biomarker_id,
                value=req.value,
                measurement_date=mdate,
                source=req.source,
                is_abnormal=is_abn,
            )
            self._patient_values[pv_id] = pv
        return pv

    def get_patient_biomarkers(self, patient_id: str) -> list[PatientBiomarkerValue]:
        """Get all biomarker values for a patient."""
        return [v for v in self._patient_values.values() if v.patient_id == patient_id]

    def get_biomarker_patient_values(self, biomarker_id: str) -> list[PatientBiomarkerValue]:
        """Get all patient values for a specific biomarker."""
        return [v for v in self._patient_values.values() if v.biomarker_id == biomarker_id]

    def list_patient_values(self) -> list[PatientBiomarkerValue]:
        """List all patient biomarker values."""
        return list(self._patient_values.values())

    # ------------------------------------------------------------------
    # Panel management
    # ------------------------------------------------------------------

    def create_panel(self, req: PanelCreateRequest) -> BiomarkerPanel:
        """Create a new biomarker panel."""
        now = datetime.now(timezone.utc)
        with self._lock:
            pnl_id = f"PNL-{len(self._panels) + 1:04d}"
            while pnl_id in self._panels:
                pnl_id = f"PNL-{int(pnl_id.split('-')[1]) + 1:04d}"

            # Calculate composite sensitivity/specificity
            sensitivities = []
            specificities = []
            for bm_id in req.biomarkers:
                bm = self._biomarkers.get(bm_id)
                if bm:
                    if bm.sensitivity is not None:
                        sensitivities.append(bm.sensitivity)
                    if bm.specificity is not None:
                        specificities.append(bm.specificity)

            panel_sens = None
            panel_spec = None
            if sensitivities:
                # Parallel testing: combined sensitivity = 1 - prod(1 - si)
                panel_sens = round(1.0 - math.prod(1.0 - s for s in sensitivities), 4)
            if specificities:
                # Parallel testing: combined specificity = prod(sp_i)
                panel_spec = round(math.prod(specificities), 4)

            panel = BiomarkerPanel(
                id=pnl_id,
                name=req.name,
                description=req.description,
                biomarkers=req.biomarkers,
                target_condition=req.target_condition,
                panel_sensitivity=panel_sens,
                panel_specificity=panel_spec,
                created_at=now,
            )
            self._panels[pnl_id] = panel
        return panel

    def get_panel(self, panel_id: str) -> Optional[BiomarkerPanel]:
        """Get a panel by ID."""
        return self._panels.get(panel_id)

    def list_panels(self) -> list[BiomarkerPanel]:
        """List all panels."""
        return list(self._panels.values())

    def score_patient_panel(self, panel_id: str, patient_id: str) -> Optional[dict]:
        """Score a patient against a biomarker panel.

        Returns a dict with individual biomarker results and a composite score.
        """
        panel = self._panels.get(panel_id)
        if panel is None:
            return None

        patient_vals = self.get_patient_biomarkers(patient_id)
        val_by_bm = {v.biomarker_id: v for v in patient_vals}

        results = []
        abnormal_count = 0
        measured_count = 0
        for bm_id in panel.biomarkers:
            bm = self._biomarkers.get(bm_id)
            pv = val_by_bm.get(bm_id)
            entry: dict = {
                "biomarker_id": bm_id,
                "biomarker_name": bm.name if bm else bm_id,
                "measured": pv is not None,
                "value": pv.value if pv else None,
                "is_abnormal": pv.is_abnormal if pv else None,
            }
            results.append(entry)
            if pv is not None:
                measured_count += 1
                if pv.is_abnormal:
                    abnormal_count += 1

        completeness = measured_count / len(panel.biomarkers) if panel.biomarkers else 0.0
        composite = abnormal_count / measured_count if measured_count > 0 else 0.0

        return {
            "panel_id": panel_id,
            "panel_name": panel.name,
            "patient_id": patient_id,
            "results": results,
            "completeness": round(completeness, 4),
            "abnormal_ratio": round(composite, 4),
            "measured_count": measured_count,
            "total_biomarkers": len(panel.biomarkers),
        }

    # ------------------------------------------------------------------
    # RWE Study CRUD
    # ------------------------------------------------------------------

    def create_rwe_study(self, req: RWEStudyCreateRequest) -> RWEStudy:
        """Create a new RWE study."""
        now = datetime.now(timezone.utc)
        with self._lock:
            study_id = f"RWE-{len(self._rwe_studies) + 1:04d}"
            while study_id in self._rwe_studies:
                study_id = f"RWE-{int(study_id.split('-')[1]) + 1:04d}"
            study = RWEStudy(
                id=study_id,
                title=req.title,
                study_type=req.study_type,
                description=req.description,
                data_source=req.data_source,
                sample_size=req.sample_size,
                study_period_start=req.study_period_start,
                study_period_end=req.study_period_end,
                primary_endpoint=req.primary_endpoint,
                matching_method=req.matching_method,
                covariates=req.covariates,
                created_at=now,
                status="ACTIVE",
            )
            self._rwe_studies[study_id] = study
        return study

    def get_rwe_study(self, study_id: str) -> Optional[RWEStudy]:
        """Get an RWE study by ID."""
        return self._rwe_studies.get(study_id)

    def list_rwe_studies(
        self,
        study_type: Optional[RWEStudyType] = None,
        status: Optional[str] = None,
    ) -> list[RWEStudy]:
        """List all RWE studies with optional filters."""
        results = list(self._rwe_studies.values())
        if study_type:
            results = [s for s in results if s.study_type == study_type]
        if status:
            results = [s for s in results if s.status == status]
        return results

    def complete_rwe_study(
        self,
        study_id: str,
        results_summary: str,
        treatment_effect: float,
        confidence_interval: tuple[float, float],
        p_value: float,
        bias_assessment: str = "",
        limitations: Optional[list[str]] = None,
    ) -> Optional[RWEStudy]:
        """Complete an RWE study with results."""
        with self._lock:
            study = self._rwe_studies.get(study_id)
            if study is None:
                return None
            updated = study.model_copy(update={
                "results_summary": results_summary,
                "treatment_effect": treatment_effect,
                "confidence_interval": confidence_interval,
                "p_value": p_value,
                "bias_assessment": bias_assessment,
                "limitations": limitations or [],
                "status": "COMPLETED",
            })
            self._rwe_studies[study_id] = updated
        return updated

    def delete_rwe_study(self, study_id: str) -> bool:
        """Delete an RWE study."""
        with self._lock:
            if study_id in self._rwe_studies:
                del self._rwe_studies[study_id]
                return True
        return False

    # ------------------------------------------------------------------
    # Propensity score matching
    # ------------------------------------------------------------------

    def run_propensity_score_matching(
        self,
        study_id: str,
        treatment_biomarker_id: Optional[str] = None,
    ) -> Optional[PropensityScoreResult]:
        """Simulate propensity score matching for an RWE study.

        In a production system this would run actual PS matching.
        Here we simulate realistic results.
        """
        study = self._rwe_studies.get(study_id)
        if study is None:
            return None

        random.seed(hash(study_id) % 2**32)

        treatment_n = study.sample_size // 2
        control_n = study.sample_size - treatment_n
        matched = int(min(treatment_n, control_n) * random.uniform(0.75, 0.95))

        # Generate balance metrics for covariates
        balance = {}
        smds = {}
        for cov in study.covariates:
            smd = round(random.uniform(-0.08, 0.08), 4)
            smds[cov] = smd
            balance[cov] = round(1.0 - abs(smd), 4)

        ate = round(random.uniform(0.05, 0.25), 4)
        att = round(ate * random.uniform(0.9, 1.1), 4)

        return PropensityScoreResult(
            treatment_group_size=treatment_n,
            control_group_size=control_n,
            matched_pairs=matched,
            balance_metrics=balance,
            ate=ate,
            att=att,
            standardized_mean_differences=smds,
        )

    # ------------------------------------------------------------------
    # RWE-RCT comparability
    # ------------------------------------------------------------------

    def create_comparability(self, req: ComparabilityCreateRequest) -> Optional[RWEComparability]:
        """Create an RWE-RCT comparability assessment."""
        if req.rwe_study_id not in self._rwe_studies:
            return None

        # Calculate agreement score
        if req.rct_effect_size != 0:
            ratio = req.rwe_effect_size / req.rct_effect_size
            agreement = max(0.0, min(1.0, 1.0 - abs(1.0 - ratio)))
        else:
            agreement = 0.0

        with self._lock:
            cmp_id = f"CMP-{len(self._comparabilities) + 1:04d}"
            while cmp_id in self._comparabilities:
                cmp_id = f"CMP-{int(cmp_id.split('-')[1]) + 1:04d}"
            cmp = RWEComparability(
                id=cmp_id,
                rwe_study_id=req.rwe_study_id,
                rct_reference=req.rct_reference,
                endpoint_comparison=req.endpoint_comparison,
                rwe_effect_size=req.rwe_effect_size,
                rct_effect_size=req.rct_effect_size,
                agreement_score=round(agreement, 4),
                assessment_notes=req.assessment_notes,
            )
            self._comparabilities[cmp_id] = cmp
        return cmp

    def get_comparability(self, cmp_id: str) -> Optional[RWEComparability]:
        """Get a comparability assessment by ID."""
        return self._comparabilities.get(cmp_id)

    def list_comparabilities(self) -> list[RWEComparability]:
        """List all comparability assessments."""
        return list(self._comparabilities.values())

    def get_comparabilities_by_study(self, rwe_study_id: str) -> list[RWEComparability]:
        """Get all comparability assessments for a given RWE study."""
        return [c for c in self._comparabilities.values() if c.rwe_study_id == rwe_study_id]

    # ------------------------------------------------------------------
    # Biomarker stratification
    # ------------------------------------------------------------------

    def stratify_patients(
        self,
        biomarker_id: str,
        threshold: Optional[float] = None,
    ) -> Optional[BiomarkerStratificationResult]:
        """Stratify patients by a biomarker value above/below a threshold.

        If no threshold is provided, uses the biomarker's normal_range_high.
        """
        bm = self._biomarkers.get(biomarker_id)
        if bm is None:
            return None

        if threshold is None:
            threshold = bm.normal_range_high if bm.normal_range_high is not None else 0.0

        values = self.get_biomarker_patient_values(biomarker_id)
        above = [v for v in values if v.value >= threshold]
        below = [v for v in values if v.value < threshold]

        above_vals = [v.value for v in above]
        below_vals = [v.value for v in below]

        return BiomarkerStratificationResult(
            biomarker_id=biomarker_id,
            biomarker_name=bm.name,
            threshold=threshold,
            above_threshold=[v.patient_id for v in above],
            below_threshold=[v.patient_id for v in below],
            above_count=len(above),
            below_count=len(below),
            above_mean=round(statistics.mean(above_vals), 4) if above_vals else None,
            below_mean=round(statistics.mean(below_vals), 4) if below_vals else None,
        )

    # ------------------------------------------------------------------
    # Enrichment analysis
    # ------------------------------------------------------------------

    def enrichment_analysis(self, biomarker_id: str) -> Optional[EnrichmentResult]:
        """Identify whether a biomarker predicts trial success.

        Simulates enrichment analysis using available association and
        patient data.
        """
        bm = self._biomarkers.get(biomarker_id)
        if bm is None:
            return None

        assocs = self.get_associations_by_biomarker(biomarker_id)
        patient_vals = self.get_biomarker_patient_values(biomarker_id)

        # Calculate enrichment score from effect sizes
        if assocs:
            avg_effect = statistics.mean(abs(a.effect_size) for a in assocs)
            avg_p = statistics.mean(a.p_value for a in assocs)
            total_sample = sum(a.sample_size for a in assocs)
        else:
            avg_effect = 0.0
            avg_p = 1.0
            total_sample = 0

        enrichment_score = round(avg_effect * (1.0 - avg_p), 4) if avg_p < 1.0 else 0.0
        predictive_value = round(avg_effect, 4)

        recommended_threshold = None
        if bm.normal_range_high is not None:
            recommended_threshold = bm.normal_range_high

        return EnrichmentResult(
            biomarker_id=biomarker_id,
            biomarker_name=bm.name,
            enrichment_score=enrichment_score,
            predictive_value=predictive_value,
            recommended_threshold=recommended_threshold,
            sample_size=total_sample,
            p_value=round(avg_p, 6) if assocs else None,
        )

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_biomarker_metrics(self) -> BiomarkerMetrics:
        """Compute aggregate biomarker metrics."""
        bms = list(self._biomarkers.values())

        by_status: dict[str, int] = defaultdict(int)
        by_type: dict[str, int] = defaultdict(int)
        by_role: dict[str, int] = defaultdict(int)
        sensitivities = []
        specificities = []
        aucs = []

        for bm in bms:
            by_status[bm.status.value] += 1
            by_type[bm.biomarker_type.value] += 1
            by_role[bm.role.value] += 1
            if bm.sensitivity is not None:
                sensitivities.append(bm.sensitivity)
            if bm.specificity is not None:
                specificities.append(bm.specificity)
            if bm.auc_roc is not None:
                aucs.append(bm.auc_roc)

        return BiomarkerMetrics(
            total_biomarkers=len(bms),
            by_status=dict(by_status),
            by_type=dict(by_type),
            by_role=dict(by_role),
            avg_sensitivity=round(statistics.mean(sensitivities), 4) if sensitivities else None,
            avg_specificity=round(statistics.mean(specificities), 4) if specificities else None,
            avg_auc_roc=round(statistics.mean(aucs), 4) if aucs else None,
            total_associations=len(self._associations),
            total_panels=len(self._panels),
            total_patient_values=len(self._patient_values),
        )

    def get_rwe_metrics(self) -> RWEMetrics:
        """Compute aggregate RWE study metrics."""
        studies = list(self._rwe_studies.values())

        by_type: dict[str, int] = defaultdict(int)
        by_method: dict[str, int] = defaultdict(int)
        effect_sizes = []
        completed = 0

        for s in studies:
            by_type[s.study_type.value] += 1
            if s.matching_method:
                by_method[s.matching_method.value] += 1
            if s.treatment_effect is not None:
                effect_sizes.append(s.treatment_effect)
            if s.status == "COMPLETED":
                completed += 1

        sample_sizes = [s.sample_size for s in studies if s.sample_size > 0]
        comps = list(self._comparabilities.values())
        agreement_scores = [c.agreement_score for c in comps]

        return RWEMetrics(
            total_studies=len(studies),
            by_study_type=dict(by_type),
            by_matching_method=dict(by_method),
            avg_sample_size=round(statistics.mean(sample_sizes), 2) if sample_sizes else 0.0,
            avg_effect_size=round(statistics.mean(effect_sizes), 4) if effect_sizes else None,
            total_comparability_assessments=len(comps),
            avg_agreement_score=round(statistics.mean(agreement_scores), 4) if agreement_scores else None,
            completed_studies=completed,
        )

    # ------------------------------------------------------------------
    # Stats helper
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return summary statistics for health check."""
        return {
            "biomarkers": len(self._biomarkers),
            "associations": len(self._associations),
            "patient_values": len(self._patient_values),
            "panels": len(self._panels),
            "rwe_studies": len(self._rwe_studies),
            "comparabilities": len(self._comparabilities),
        }


# ---------------------------------------------------------------------------
# Singleton management
# ---------------------------------------------------------------------------

_instance: BiomarkerAnalysisService | None = None
_instance_lock = threading.Lock()


def get_biomarker_analysis_service() -> BiomarkerAnalysisService:
    """Return the singleton BiomarkerAnalysisService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = BiomarkerAnalysisService()
    return _instance


def reset_biomarker_analysis_service() -> BiomarkerAnalysisService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = BiomarkerAnalysisService()
    return _instance
