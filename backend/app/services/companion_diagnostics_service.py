"""Companion Diagnostics (CDx) Management Service (CDx-MGMT).

Manages companion diagnostic lifecycle operations: CDx registration and tracking,
biomarker-drug pairing, analytical/clinical validation studies, regulatory pathway
management, assay performance metrics (sensitivity, specificity, PPV, NPV),
concordance analysis, and CDx portfolio metrics.

Usage:
    from app.services.companion_diagnostics_service import (
        get_companion_diagnostics_service,
    )

    svc = get_companion_diagnostics_service()
    cdx_list = svc.list_cdx()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.companion_diagnostics import (
    CdxCreate,
    CdxListResponse,
    CdxMetrics,
    CdxStatus,
    CdxType,
    CdxUpdate,
    CdxValidationStudy,
    CdxValidationStudyCreate,
    CdxValidationStudyListResponse,
    CdxValidationStudyUpdate,
    BiomarkerType,
    CompanionDiagnostic,
    RegulatoryPathway,
    ValidationStudyStatus,
    ValidationStudyType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class CompanionDiagnosticsService:
    """In-memory Companion Diagnostics Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._cdx: dict[str, CompanionDiagnostic] = {}
        self._studies: dict[str, CdxValidationStudy] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic CDx data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Companion Diagnostics ---
        cdx_data = [
            # EYLEA-linked CDx (ophthalmology biomarkers)
            {
                "id": "CDX-001",
                "cdx_name": "VEGF-A Ocular Level Assay",
                "cdx_type": CdxType.IVD,
                "status": CdxStatus.APPROVED,
                "biomarker_name": "VEGF-A",
                "biomarker_type": BiomarkerType.PROTEOMIC,
                "gene_target": "VEGFA",
                "variant": None,
                "assay_manufacturer": "Roche Diagnostics",
                "assay_platform": "Elecsys VEGF",
                "sensitivity": 95.2,
                "specificity": 92.8,
                "ppv": 89.5,
                "npv": 96.1,
                "concordance_rate": 94.0,
                "trial_ids": [EYLEA_TRIAL],
                "drug_name": "Eylea (aflibercept)",
                "therapeutic_area": "Ophthalmology",
                "regulatory_pathway": RegulatoryPathway.PMA,
                "submission_date": now - timedelta(days=365),
                "approval_date": now - timedelta(days=180),
                "labeling_text": "For identification of patients with elevated VEGF-A suitable for anti-VEGF therapy",
                "cutoff_value": 200.0,
                "cutoff_unit": "pg/mL",
                "sample_type": "Aqueous humor",
                "turnaround_days": 3,
                "created_at": now - timedelta(days=400),
                "updated_at": now - timedelta(days=10),
            },
            {
                "id": "CDX-002",
                "cdx_name": "Complement Factor H IHC Panel",
                "cdx_type": CdxType.IHC,
                "status": CdxStatus.CLINICAL_VALIDATION,
                "biomarker_name": "Complement Factor H",
                "biomarker_type": BiomarkerType.PROTEOMIC,
                "gene_target": "CFH",
                "variant": "Y402H",
                "assay_manufacturer": "Agilent/Dako",
                "assay_platform": "Dako Autostainer Link 48",
                "sensitivity": 88.7,
                "specificity": 91.2,
                "ppv": 85.3,
                "npv": 93.0,
                "concordance_rate": 90.1,
                "trial_ids": [EYLEA_TRIAL],
                "drug_name": "Eylea (aflibercept)",
                "therapeutic_area": "Ophthalmology",
                "regulatory_pathway": RegulatoryPathway.PMA,
                "submission_date": None,
                "approval_date": None,
                "labeling_text": None,
                "cutoff_value": 50.0,
                "cutoff_unit": "TPS",
                "sample_type": "Retinal biopsy FFPE",
                "turnaround_days": 5,
                "created_at": now - timedelta(days=300),
                "updated_at": now - timedelta(days=20),
            },
            {
                "id": "CDX-003",
                "cdx_name": "Retinal ANGPT2 Liquid Biopsy",
                "cdx_type": CdxType.LIQUID_BIOPSY,
                "status": CdxStatus.ANALYTICAL_VALIDATION,
                "biomarker_name": "Angiopoietin-2",
                "biomarker_type": BiomarkerType.PROTEOMIC,
                "gene_target": "ANGPT2",
                "variant": None,
                "assay_manufacturer": "Guardant Health",
                "assay_platform": "Guardant360 CDx",
                "sensitivity": 82.5,
                "specificity": 87.3,
                "ppv": None,
                "npv": None,
                "concordance_rate": None,
                "trial_ids": [EYLEA_TRIAL],
                "drug_name": "Eylea (aflibercept)",
                "therapeutic_area": "Ophthalmology",
                "regulatory_pathway": None,
                "submission_date": None,
                "approval_date": None,
                "labeling_text": None,
                "cutoff_value": 3.5,
                "cutoff_unit": "ng/mL",
                "sample_type": "Blood plasma",
                "turnaround_days": 7,
                "created_at": now - timedelta(days=200),
                "updated_at": now - timedelta(days=15),
            },
            # DUPIXENT-linked CDx (immunology biomarkers)
            {
                "id": "CDX-004",
                "cdx_name": "Total Serum IgE Quantification Assay",
                "cdx_type": CdxType.IVD,
                "status": CdxStatus.APPROVED,
                "biomarker_name": "Total IgE",
                "biomarker_type": BiomarkerType.PROTEOMIC,
                "gene_target": None,
                "variant": None,
                "assay_manufacturer": "Siemens Healthineers",
                "assay_platform": "IMMULITE 2000 XPi",
                "sensitivity": 97.1,
                "specificity": 94.5,
                "ppv": 91.8,
                "npv": 98.0,
                "concordance_rate": 96.2,
                "trial_ids": [DUPIXENT_TRIAL],
                "drug_name": "Dupixent (dupilumab)",
                "therapeutic_area": "Immunology",
                "regulatory_pathway": RegulatoryPathway.DE_NOVO_510K,
                "submission_date": now - timedelta(days=500),
                "approval_date": now - timedelta(days=300),
                "labeling_text": "For quantification of total serum IgE in patients being evaluated for anti-IL4R therapy",
                "cutoff_value": 150.0,
                "cutoff_unit": "IU/mL",
                "sample_type": "Serum",
                "turnaround_days": 2,
                "created_at": now - timedelta(days=550),
                "updated_at": now - timedelta(days=5),
            },
            {
                "id": "CDX-005",
                "cdx_name": "IL-4/IL-13 Pathway Activation NGS Panel",
                "cdx_type": CdxType.NGS_PANEL,
                "status": CdxStatus.CLINICAL_VALIDATION,
                "biomarker_name": "IL-4/IL-13 signature",
                "biomarker_type": BiomarkerType.GENOMIC,
                "gene_target": "IL4R",
                "variant": "Q576R",
                "assay_manufacturer": "Foundation Medicine",
                "assay_platform": "FoundationOne CDx",
                "sensitivity": 91.0,
                "specificity": 88.5,
                "ppv": 86.2,
                "npv": 92.7,
                "concordance_rate": 89.8,
                "trial_ids": [DUPIXENT_TRIAL],
                "drug_name": "Dupixent (dupilumab)",
                "therapeutic_area": "Immunology",
                "regulatory_pathway": RegulatoryPathway.PMA,
                "submission_date": None,
                "approval_date": None,
                "labeling_text": None,
                "cutoff_value": None,
                "cutoff_unit": None,
                "sample_type": "FFPE tissue",
                "turnaround_days": 14,
                "created_at": now - timedelta(days=250),
                "updated_at": now - timedelta(days=30),
            },
            {
                "id": "CDX-006",
                "cdx_name": "Eosinophil Blood Count PCR Assay",
                "cdx_type": CdxType.PCR,
                "status": CdxStatus.APPROVED,
                "biomarker_name": "Blood eosinophils",
                "biomarker_type": BiomarkerType.GENOMIC,
                "gene_target": "TSLP",
                "variant": None,
                "assay_manufacturer": "Abbott Diagnostics",
                "assay_platform": "Alinity m System",
                "sensitivity": 93.8,
                "specificity": 90.4,
                "ppv": 88.9,
                "npv": 94.7,
                "concordance_rate": 92.5,
                "trial_ids": [DUPIXENT_TRIAL],
                "drug_name": "Dupixent (dupilumab)",
                "therapeutic_area": "Immunology",
                "regulatory_pathway": RegulatoryPathway.DE_NOVO_510K,
                "submission_date": now - timedelta(days=400),
                "approval_date": now - timedelta(days=220),
                "labeling_text": "For quantification of eosinophil-associated gene expression in Type 2 inflammatory conditions",
                "cutoff_value": 300.0,
                "cutoff_unit": "cells/uL",
                "sample_type": "Whole blood",
                "turnaround_days": 1,
                "created_at": now - timedelta(days=450),
                "updated_at": now - timedelta(days=8),
            },
            {
                "id": "CDX-007",
                "cdx_name": "Periostin Serum ELISA",
                "cdx_type": CdxType.IVD,
                "status": CdxStatus.IN_DEVELOPMENT,
                "biomarker_name": "Periostin",
                "biomarker_type": BiomarkerType.PROTEOMIC,
                "gene_target": "POSTN",
                "variant": None,
                "assay_manufacturer": "Regeneron Diagnostics",
                "assay_platform": "Custom ELISA Platform",
                "sensitivity": None,
                "specificity": None,
                "ppv": None,
                "npv": None,
                "concordance_rate": None,
                "trial_ids": [DUPIXENT_TRIAL],
                "drug_name": "Dupixent (dupilumab)",
                "therapeutic_area": "Immunology",
                "regulatory_pathway": None,
                "submission_date": None,
                "approval_date": None,
                "labeling_text": None,
                "cutoff_value": None,
                "cutoff_unit": None,
                "sample_type": "Serum",
                "turnaround_days": 4,
                "created_at": now - timedelta(days=60),
                "updated_at": now - timedelta(days=3),
            },
            # LIBTAYO-linked CDx (oncology biomarkers)
            {
                "id": "CDX-008",
                "cdx_name": "PD-L1 IHC 22C3 pharmDx",
                "cdx_type": CdxType.IHC,
                "status": CdxStatus.APPROVED,
                "biomarker_name": "PD-L1 (22C3)",
                "biomarker_type": BiomarkerType.PROTEOMIC,
                "gene_target": "CD274",
                "variant": None,
                "assay_manufacturer": "Agilent/Dako",
                "assay_platform": "Dako Autostainer Link 48",
                "sensitivity": 96.5,
                "specificity": 93.2,
                "ppv": 90.8,
                "npv": 97.3,
                "concordance_rate": 95.1,
                "trial_ids": [LIBTAYO_TRIAL],
                "drug_name": "Libtayo (cemiplimab)",
                "therapeutic_area": "Oncology",
                "regulatory_pathway": RegulatoryPathway.PMA,
                "submission_date": now - timedelta(days=600),
                "approval_date": now - timedelta(days=400),
                "labeling_text": "For selection of NSCLC patients with TPS >= 50% for cemiplimab monotherapy",
                "cutoff_value": 50.0,
                "cutoff_unit": "TPS",
                "sample_type": "FFPE tissue",
                "turnaround_days": 5,
                "created_at": now - timedelta(days=650),
                "updated_at": now - timedelta(days=12),
            },
            {
                "id": "CDX-009",
                "cdx_name": "TMB NGS Comprehensive Panel",
                "cdx_type": CdxType.NGS_PANEL,
                "status": CdxStatus.CLINICAL_VALIDATION,
                "biomarker_name": "Tumor Mutational Burden",
                "biomarker_type": BiomarkerType.GENOMIC,
                "gene_target": None,
                "variant": None,
                "assay_manufacturer": "Foundation Medicine",
                "assay_platform": "FoundationOne CDx",
                "sensitivity": 90.3,
                "specificity": 87.6,
                "ppv": 84.1,
                "npv": 92.5,
                "concordance_rate": 88.9,
                "trial_ids": [LIBTAYO_TRIAL],
                "drug_name": "Libtayo (cemiplimab)",
                "therapeutic_area": "Oncology",
                "regulatory_pathway": RegulatoryPathway.PMA,
                "submission_date": None,
                "approval_date": None,
                "labeling_text": None,
                "cutoff_value": 10.0,
                "cutoff_unit": "mut/Mb",
                "sample_type": "FFPE tissue",
                "turnaround_days": 14,
                "created_at": now - timedelta(days=280),
                "updated_at": now - timedelta(days=25),
            },
            {
                "id": "CDX-010",
                "cdx_name": "MSI/dMMR FISH Panel",
                "cdx_type": CdxType.FISH,
                "status": CdxStatus.REGULATORY_SUBMISSION,
                "biomarker_name": "MSI/dMMR status",
                "biomarker_type": BiomarkerType.GENOMIC,
                "gene_target": "MLH1",
                "variant": None,
                "assay_manufacturer": "Abbott Molecular",
                "assay_platform": "Vysis ALK Break Apart FISH",
                "sensitivity": 94.1,
                "specificity": 96.0,
                "ppv": 93.5,
                "npv": 96.3,
                "concordance_rate": 95.5,
                "trial_ids": [LIBTAYO_TRIAL],
                "drug_name": "Libtayo (cemiplimab)",
                "therapeutic_area": "Oncology",
                "regulatory_pathway": RegulatoryPathway.PMA,
                "submission_date": now - timedelta(days=45),
                "approval_date": None,
                "labeling_text": None,
                "cutoff_value": None,
                "cutoff_unit": None,
                "sample_type": "FFPE tissue",
                "turnaround_days": 7,
                "created_at": now - timedelta(days=350),
                "updated_at": now - timedelta(days=7),
            },
            {
                "id": "CDX-011",
                "cdx_name": "ctDNA Liquid Biopsy Panel",
                "cdx_type": CdxType.LIQUID_BIOPSY,
                "status": CdxStatus.ANALYTICAL_VALIDATION,
                "biomarker_name": "ctDNA mutations",
                "biomarker_type": BiomarkerType.GENOMIC,
                "gene_target": "EGFR",
                "variant": "L858R",
                "assay_manufacturer": "Guardant Health",
                "assay_platform": "Guardant360 CDx",
                "sensitivity": 85.2,
                "specificity": 99.1,
                "ppv": 97.8,
                "npv": 91.0,
                "concordance_rate": 92.3,
                "trial_ids": [LIBTAYO_TRIAL],
                "drug_name": "Libtayo (cemiplimab)",
                "therapeutic_area": "Oncology",
                "regulatory_pathway": RegulatoryPathway.PMA,
                "submission_date": None,
                "approval_date": None,
                "labeling_text": None,
                "cutoff_value": 0.5,
                "cutoff_unit": "% VAF",
                "sample_type": "Blood plasma",
                "turnaround_days": 10,
                "created_at": now - timedelta(days=180),
                "updated_at": now - timedelta(days=18),
            },
            {
                "id": "CDX-012",
                "cdx_name": "KRAS G12C Mutation PCR",
                "cdx_type": CdxType.PCR,
                "status": CdxStatus.WITHDRAWN,
                "biomarker_name": "KRAS G12C",
                "biomarker_type": BiomarkerType.GENOMIC,
                "gene_target": "KRAS",
                "variant": "G12C",
                "assay_manufacturer": "Qiagen",
                "assay_platform": "therascreen KRAS RGQ PCR",
                "sensitivity": 97.0,
                "specificity": 99.5,
                "ppv": 99.0,
                "npv": 97.8,
                "concordance_rate": 98.2,
                "trial_ids": [LIBTAYO_TRIAL],
                "drug_name": "Libtayo (cemiplimab)",
                "therapeutic_area": "Oncology",
                "regulatory_pathway": RegulatoryPathway.PMA,
                "submission_date": now - timedelta(days=700),
                "approval_date": now - timedelta(days=500),
                "labeling_text": "Withdrawn: replaced by NGS-based comprehensive panel",
                "cutoff_value": None,
                "cutoff_unit": None,
                "sample_type": "FFPE tissue",
                "turnaround_days": 3,
                "created_at": now - timedelta(days=750),
                "updated_at": now - timedelta(days=60),
            },
        ]

        for c in cdx_data:
            self._cdx[c["id"]] = CompanionDiagnostic(**c)

        # --- 15 Validation Studies ---
        studies_data = [
            # CDX-001 studies
            {
                "id": "VS-001",
                "cdx_id": "CDX-001",
                "study_type": ValidationStudyType.ANALYTICAL_VALIDATION,
                "study_name": "VEGF-A Analytical Sensitivity & Linearity Study",
                "sample_size": 240,
                "concordance_rate": 94.5,
                "sensitivity": 95.2,
                "specificity": 92.8,
                "status": ValidationStudyStatus.COMPLETED,
                "start_date": now - timedelta(days=500),
                "completion_date": now - timedelta(days=380),
                "findings": "Assay demonstrated excellent analytical sensitivity (LOD: 5 pg/mL) with linear range 5-2000 pg/mL.",
                "created_at": now - timedelta(days=500),
            },
            {
                "id": "VS-002",
                "cdx_id": "CDX-001",
                "study_type": ValidationStudyType.CLINICAL_VALIDATION,
                "study_name": "VEGF-A Clinical Utility in nAMD Patient Selection",
                "sample_size": 520,
                "concordance_rate": 93.2,
                "sensitivity": 94.8,
                "specificity": 91.5,
                "status": ValidationStudyStatus.COMPLETED,
                "start_date": now - timedelta(days=450),
                "completion_date": now - timedelta(days=280),
                "findings": "VEGF-A levels >200 pg/mL strongly predict response to anti-VEGF therapy (OR 4.7, p<0.001).",
                "created_at": now - timedelta(days=450),
            },
            {
                "id": "VS-003",
                "cdx_id": "CDX-001",
                "study_type": ValidationStudyType.REPRODUCIBILITY,
                "study_name": "VEGF-A Inter-Laboratory Reproducibility Assessment",
                "sample_size": 180,
                "concordance_rate": 96.1,
                "sensitivity": None,
                "specificity": None,
                "status": ValidationStudyStatus.COMPLETED,
                "start_date": now - timedelta(days=350),
                "completion_date": now - timedelta(days=280),
                "findings": "CV% <8% across 5 reference laboratories. Excellent inter-laboratory reproducibility.",
                "created_at": now - timedelta(days=350),
            },
            # CDX-004 studies
            {
                "id": "VS-004",
                "cdx_id": "CDX-004",
                "study_type": ValidationStudyType.ANALYTICAL_VALIDATION,
                "study_name": "Total IgE IMMULITE Platform Analytical Validation",
                "sample_size": 300,
                "concordance_rate": 97.0,
                "sensitivity": 97.1,
                "specificity": 94.5,
                "status": ValidationStudyStatus.COMPLETED,
                "start_date": now - timedelta(days=600),
                "completion_date": now - timedelta(days=520),
                "findings": "Analytical range 2-5000 IU/mL with excellent precision (CV% <5%).",
                "created_at": now - timedelta(days=600),
            },
            {
                "id": "VS-005",
                "cdx_id": "CDX-004",
                "study_type": ValidationStudyType.CLINICAL_VALIDATION,
                "study_name": "IgE-Guided Dupixent Patient Selection Study",
                "sample_size": 680,
                "concordance_rate": 95.5,
                "sensitivity": 96.3,
                "specificity": 93.8,
                "status": ValidationStudyStatus.COMPLETED,
                "start_date": now - timedelta(days=550),
                "completion_date": now - timedelta(days=340),
                "findings": "Patients with IgE >150 IU/mL showed significantly better EASI-75 response (67% vs 31%, p<0.001).",
                "created_at": now - timedelta(days=550),
            },
            # CDX-005 studies
            {
                "id": "VS-006",
                "cdx_id": "CDX-005",
                "study_type": ValidationStudyType.ANALYTICAL_VALIDATION,
                "study_name": "IL-4R NGS Panel Analytical Performance",
                "sample_size": 200,
                "concordance_rate": 91.2,
                "sensitivity": 91.0,
                "specificity": 88.5,
                "status": ValidationStudyStatus.COMPLETED,
                "start_date": now - timedelta(days=280),
                "completion_date": now - timedelta(days=200),
                "findings": "Panel detects IL4R Q576R with 91% sensitivity. LOD at 5% allele frequency.",
                "created_at": now - timedelta(days=280),
            },
            {
                "id": "VS-007",
                "cdx_id": "CDX-005",
                "study_type": ValidationStudyType.CLINICAL_VALIDATION,
                "study_name": "IL-4/IL-13 Signature Clinical Concordance",
                "sample_size": 420,
                "concordance_rate": 88.3,
                "sensitivity": 90.5,
                "specificity": 87.1,
                "status": ValidationStudyStatus.IN_PROGRESS,
                "start_date": now - timedelta(days=120),
                "completion_date": None,
                "findings": None,
                "created_at": now - timedelta(days=120),
            },
            # CDX-008 studies
            {
                "id": "VS-008",
                "cdx_id": "CDX-008",
                "study_type": ValidationStudyType.ANALYTICAL_VALIDATION,
                "study_name": "PD-L1 22C3 IHC Analytical Validation",
                "sample_size": 350,
                "concordance_rate": 95.8,
                "sensitivity": 96.5,
                "specificity": 93.2,
                "status": ValidationStudyStatus.COMPLETED,
                "start_date": now - timedelta(days=700),
                "completion_date": now - timedelta(days=600),
                "findings": "22C3 antibody demonstrates robust staining with TPS scoring. Excellent inter-pathologist agreement (kappa=0.85).",
                "created_at": now - timedelta(days=700),
            },
            {
                "id": "VS-009",
                "cdx_id": "CDX-008",
                "study_type": ValidationStudyType.CLINICAL_VALIDATION,
                "study_name": "PD-L1 TPS Predictive Value for Cemiplimab Response",
                "sample_size": 780,
                "concordance_rate": 94.2,
                "sensitivity": 95.8,
                "specificity": 92.0,
                "status": ValidationStudyStatus.COMPLETED,
                "start_date": now - timedelta(days=650),
                "completion_date": now - timedelta(days=430),
                "findings": "TPS >=50% predicts ORR of 39% vs 7% for TPS <1%. Strong predictive value for cemiplimab monotherapy.",
                "created_at": now - timedelta(days=650),
            },
            {
                "id": "VS-010",
                "cdx_id": "CDX-008",
                "study_type": ValidationStudyType.CONCORDANCE,
                "study_name": "22C3 vs SP142 vs SP263 PD-L1 Antibody Concordance",
                "sample_size": 500,
                "concordance_rate": 82.5,
                "sensitivity": None,
                "specificity": None,
                "status": ValidationStudyStatus.COMPLETED,
                "start_date": now - timedelta(days=550),
                "completion_date": now - timedelta(days=420),
                "findings": "22C3 and SP263 show high concordance (OPA 89%). SP142 demonstrates lower concordance with both.",
                "created_at": now - timedelta(days=550),
            },
            # CDX-009 studies
            {
                "id": "VS-011",
                "cdx_id": "CDX-009",
                "study_type": ValidationStudyType.ANALYTICAL_VALIDATION,
                "study_name": "TMB Panel Analytical Sensitivity Study",
                "sample_size": 280,
                "concordance_rate": 90.1,
                "sensitivity": 90.3,
                "specificity": 87.6,
                "status": ValidationStudyStatus.COMPLETED,
                "start_date": now - timedelta(days=320),
                "completion_date": now - timedelta(days=230),
                "findings": "TMB quantification accurate across range 0-100 mut/Mb. Minimum input 50ng DNA required.",
                "created_at": now - timedelta(days=320),
            },
            {
                "id": "VS-012",
                "cdx_id": "CDX-009",
                "study_type": ValidationStudyType.BRIDGING_STUDY,
                "study_name": "WES vs Panel-Based TMB Concordance Bridging",
                "sample_size": 350,
                "concordance_rate": 87.5,
                "sensitivity": None,
                "specificity": None,
                "status": ValidationStudyStatus.IN_PROGRESS,
                "start_date": now - timedelta(days=90),
                "completion_date": None,
                "findings": None,
                "created_at": now - timedelta(days=90),
            },
            # CDX-010 studies
            {
                "id": "VS-013",
                "cdx_id": "CDX-010",
                "study_type": ValidationStudyType.ANALYTICAL_VALIDATION,
                "study_name": "MSI/dMMR FISH Panel Validation",
                "sample_size": 250,
                "concordance_rate": 95.8,
                "sensitivity": 94.1,
                "specificity": 96.0,
                "status": ValidationStudyStatus.COMPLETED,
                "start_date": now - timedelta(days=400),
                "completion_date": now - timedelta(days=300),
                "findings": "FISH panel detects MLH1/MSH2/MSH6/PMS2 loss with high accuracy. Concordant with IHC in 95.8% of cases.",
                "created_at": now - timedelta(days=400),
            },
            {
                "id": "VS-014",
                "cdx_id": "CDX-010",
                "study_type": ValidationStudyType.PROFICIENCY_TESTING,
                "study_name": "MSI FISH Inter-Lab Proficiency Panel",
                "sample_size": 100,
                "concordance_rate": 94.0,
                "sensitivity": None,
                "specificity": None,
                "status": ValidationStudyStatus.COMPLETED,
                "start_date": now - timedelta(days=200),
                "completion_date": now - timedelta(days=150),
                "findings": "All 8 participating labs achieved >90% concordance on proficiency panel.",
                "created_at": now - timedelta(days=200),
            },
            # CDX-002 study (planned)
            {
                "id": "VS-015",
                "cdx_id": "CDX-002",
                "study_type": ValidationStudyType.CLINICAL_VALIDATION,
                "study_name": "CFH Y402H Clinical Utility in AMD Treatment Selection",
                "sample_size": 400,
                "concordance_rate": None,
                "sensitivity": None,
                "specificity": None,
                "status": ValidationStudyStatus.PLANNED,
                "start_date": now + timedelta(days=30),
                "completion_date": None,
                "findings": None,
                "created_at": now - timedelta(days=30),
            },
        ]

        for s in studies_data:
            self._studies[s["id"]] = CdxValidationStudy(**s)

    # ------------------------------------------------------------------
    # CDx Management
    # ------------------------------------------------------------------

    def list_cdx(
        self,
        *,
        trial_id: str | None = None,
        status: CdxStatus | None = None,
        cdx_type: CdxType | None = None,
        biomarker_type: BiomarkerType | None = None,
        therapeutic_area: str | None = None,
    ) -> list[CompanionDiagnostic]:
        """List companion diagnostics with optional filters."""
        with self._lock:
            result = list(self._cdx.values())

        if trial_id is not None:
            result = [c for c in result if trial_id in c.trial_ids]
        if status is not None:
            result = [c for c in result if c.status == status]
        if cdx_type is not None:
            result = [c for c in result if c.cdx_type == cdx_type]
        if biomarker_type is not None:
            result = [c for c in result if c.biomarker_type == biomarker_type]
        if therapeutic_area is not None:
            result = [c for c in result if c.therapeutic_area.lower() == therapeutic_area.lower()]

        return sorted(result, key=lambda c: c.id)

    def get_cdx(self, cdx_id: str) -> CompanionDiagnostic | None:
        """Get a single CDx by ID."""
        with self._lock:
            return self._cdx.get(cdx_id)

    def create_cdx(self, payload: CdxCreate) -> CompanionDiagnostic:
        """Create a new companion diagnostic."""
        now = datetime.now(timezone.utc)
        cdx_id = f"CDX-{uuid4().hex[:8].upper()}"
        cdx = CompanionDiagnostic(
            id=cdx_id,
            cdx_name=payload.cdx_name,
            cdx_type=payload.cdx_type,
            status=CdxStatus.IN_DEVELOPMENT,
            biomarker_name=payload.biomarker_name,
            biomarker_type=payload.biomarker_type,
            gene_target=payload.gene_target,
            variant=payload.variant,
            assay_manufacturer=payload.assay_manufacturer,
            assay_platform=payload.assay_platform,
            sensitivity=payload.sensitivity,
            specificity=payload.specificity,
            ppv=payload.ppv,
            npv=payload.npv,
            concordance_rate=payload.concordance_rate,
            trial_ids=payload.trial_ids,
            drug_name=payload.drug_name,
            therapeutic_area=payload.therapeutic_area,
            regulatory_pathway=payload.regulatory_pathway,
            submission_date=None,
            approval_date=None,
            labeling_text=payload.labeling_text,
            cutoff_value=payload.cutoff_value,
            cutoff_unit=payload.cutoff_unit,
            sample_type=payload.sample_type,
            turnaround_days=payload.turnaround_days,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._cdx[cdx_id] = cdx
        logger.info("Created companion diagnostic %s: %s", cdx_id, payload.cdx_name)
        return cdx

    def update_cdx(
        self, cdx_id: str, payload: CdxUpdate
    ) -> CompanionDiagnostic | None:
        """Update an existing companion diagnostic."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._cdx.get(cdx_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            data["updated_at"] = now
            updated = CompanionDiagnostic(**data)
            self._cdx[cdx_id] = updated
        return updated

    def delete_cdx(self, cdx_id: str) -> bool:
        """Delete a CDx. Returns True if deleted."""
        with self._lock:
            if cdx_id in self._cdx:
                del self._cdx[cdx_id]
                # Also delete associated studies
                study_ids_to_remove = [
                    sid for sid, s in self._studies.items()
                    if s.cdx_id == cdx_id
                ]
                for sid in study_ids_to_remove:
                    del self._studies[sid]
                return True
            return False

    # ------------------------------------------------------------------
    # Validation Study Management
    # ------------------------------------------------------------------

    def list_studies(
        self,
        *,
        cdx_id: str | None = None,
        study_type: ValidationStudyType | None = None,
        status: ValidationStudyStatus | None = None,
    ) -> list[CdxValidationStudy]:
        """List validation studies with optional filters."""
        with self._lock:
            result = list(self._studies.values())

        if cdx_id is not None:
            result = [s for s in result if s.cdx_id == cdx_id]
        if study_type is not None:
            result = [s for s in result if s.study_type == study_type]
        if status is not None:
            result = [s for s in result if s.status == status]

        return sorted(result, key=lambda s: s.id)

    def get_study(self, study_id: str) -> CdxValidationStudy | None:
        """Get a single validation study by ID."""
        with self._lock:
            return self._studies.get(study_id)

    def create_study(
        self, cdx_id: str, payload: CdxValidationStudyCreate
    ) -> CdxValidationStudy | None:
        """Create a new validation study for a CDx. Returns None if CDx not found."""
        now = datetime.now(timezone.utc)
        with self._lock:
            if cdx_id not in self._cdx:
                return None
        study_id = f"VS-{uuid4().hex[:8].upper()}"
        study = CdxValidationStudy(
            id=study_id,
            cdx_id=cdx_id,
            study_type=payload.study_type,
            study_name=payload.study_name,
            sample_size=payload.sample_size,
            concordance_rate=payload.concordance_rate,
            sensitivity=payload.sensitivity,
            specificity=payload.specificity,
            status=ValidationStudyStatus.PLANNED,
            start_date=payload.start_date,
            completion_date=payload.completion_date,
            findings=payload.findings,
            created_at=now,
        )
        with self._lock:
            self._studies[study_id] = study
        logger.info("Created validation study %s for CDx %s", study_id, cdx_id)
        return study

    def update_study(
        self, study_id: str, payload: CdxValidationStudyUpdate
    ) -> CdxValidationStudy | None:
        """Update an existing validation study."""
        with self._lock:
            existing = self._studies.get(study_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CdxValidationStudy(**data)
            self._studies[study_id] = updated
        return updated

    def delete_study(self, study_id: str) -> bool:
        """Delete a validation study. Returns True if deleted."""
        with self._lock:
            if study_id in self._studies:
                del self._studies[study_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> CdxMetrics:
        """Compute aggregated CDx portfolio metrics."""
        with self._lock:
            all_cdx = list(self._cdx.values())
            all_studies = list(self._studies.values())

        if trial_id is not None:
            all_cdx = [c for c in all_cdx if trial_id in c.trial_ids]
            cdx_ids = {c.id for c in all_cdx}
            all_studies = [s for s in all_studies if s.cdx_id in cdx_ids]

        # CDx by status
        cdx_by_status: dict[str, int] = {}
        for c in all_cdx:
            key = c.status.value
            cdx_by_status[key] = cdx_by_status.get(key, 0) + 1

        # CDx by type
        cdx_by_type: dict[str, int] = {}
        for c in all_cdx:
            key = c.cdx_type.value
            cdx_by_type[key] = cdx_by_type.get(key, 0) + 1

        # CDx by biomarker type
        cdx_by_biomarker_type: dict[str, int] = {}
        for c in all_cdx:
            key = c.biomarker_type.value
            cdx_by_biomarker_type[key] = cdx_by_biomarker_type.get(key, 0) + 1

        # Studies metrics
        studies_in_progress = sum(
            1 for s in all_studies if s.status == ValidationStudyStatus.IN_PROGRESS
        )
        studies_completed = sum(
            1 for s in all_studies if s.status == ValidationStudyStatus.COMPLETED
        )

        # Averages across CDx with data
        sensitivities = [c.sensitivity for c in all_cdx if c.sensitivity is not None]
        specificities = [c.specificity for c in all_cdx if c.specificity is not None]
        concordances = [c.concordance_rate for c in all_cdx if c.concordance_rate is not None]

        avg_sensitivity = round(sum(sensitivities) / len(sensitivities), 1) if sensitivities else None
        avg_specificity = round(sum(specificities) / len(specificities), 1) if specificities else None
        avg_concordance = round(sum(concordances) / len(concordances), 1) if concordances else None

        # Approved count
        approved_count = sum(1 for c in all_cdx if c.status == CdxStatus.APPROVED)

        # Pending submission count
        pending_submission_count = sum(
            1 for c in all_cdx if c.status == CdxStatus.REGULATORY_SUBMISSION
        )

        return CdxMetrics(
            total_cdx=len(all_cdx),
            cdx_by_status=cdx_by_status,
            cdx_by_type=cdx_by_type,
            cdx_by_biomarker_type=cdx_by_biomarker_type,
            total_validation_studies=len(all_studies),
            studies_in_progress=studies_in_progress,
            studies_completed=studies_completed,
            avg_sensitivity=avg_sensitivity,
            avg_specificity=avg_specificity,
            avg_concordance=avg_concordance,
            approved_count=approved_count,
            pending_submission_count=pending_submission_count,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: CompanionDiagnosticsService | None = None
_instance_lock = threading.Lock()


def get_companion_diagnostics_service() -> CompanionDiagnosticsService:
    """Return the singleton CompanionDiagnosticsService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = CompanionDiagnosticsService()
    return _instance


def reset_companion_diagnostics_service() -> CompanionDiagnosticsService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = CompanionDiagnosticsService()
    return _instance
