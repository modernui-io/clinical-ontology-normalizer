"""Pharmacogenomics Management (PGx-MGT) Service.

Manages pharmacogenomics operations: drug-gene interaction tracking,
genotype-phenotype mapping, PGx test orders, variant results interpretation,
dosing recommendation generation, and pharmacogenomics operational metrics.

Usage:
    from app.services.pharmacogenomics_service import (
        get_pharmacogenomics_service,
    )

    svc = get_pharmacogenomics_service()
    interactions = svc.list_drug_gene_interactions()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.pharmacogenomics import (
    DosingRecommendation,
    DosingRecommendationCreate,
    DosingRecommendationUpdate,
    DrugGeneInteraction,
    DrugGeneInteractionCreate,
    DrugGeneInteractionUpdate,
    EvidenceLevel,
    GenotypePhenotype,
    GenotypePhenotypeCreate,
    GenotypePhenotypeUpdate,
    MetabolizerStatus,
    PGxTestOrder,
    PGxTestOrderCreate,
    PGxTestOrderUpdate,
    PharmacogenomicsMetrics,
    RecommendationAction,
    TestStatus,
    VariantResult,
    VariantResultCreate,
    VariantResultUpdate,
    VariantSignificance,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class PharmacogenomicsService:
    """In-memory Pharmacogenomics Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._interactions: dict[str, DrugGeneInteraction] = {}
        self._genotype_phenotypes: dict[str, GenotypePhenotype] = {}
        self._test_orders: dict[str, PGxTestOrder] = {}
        self._variant_results: dict[str, VariantResult] = {}
        self._dosing_recommendations: dict[str, DosingRecommendation] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic pharmacogenomics data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Drug-Gene Interactions ---
        interactions_data = [
            {"id": "DGI-001", "drug_name": "Aflibercept", "gene_symbol": "VEGFA", "gene_id": "HGNC:12680", "interaction_type": "pharmacodynamic", "evidence_level": EvidenceLevel.LEVEL_1A, "clinical_significance": "VEGF-A polymorphisms may alter binding affinity and treatment response", "affected_metabolizer_statuses": ["normal", "intermediate"], "guideline_source": "CPIC", "guideline_id": "CPIC-2024-VEGFA", "population_frequency_pct": 22.5, "description": "VEGFA gene variants influence anti-VEGF therapy response in retinal diseases", "actionable": True, "last_reviewed": now - timedelta(days=30), "created_at": now - timedelta(days=180)},
            {"id": "DGI-002", "drug_name": "Aflibercept", "gene_symbol": "FLT1", "gene_id": "HGNC:3763", "interaction_type": "pharmacodynamic", "evidence_level": EvidenceLevel.LEVEL_2A, "clinical_significance": "FLT1 variants may influence VEGF receptor signaling and drug efficacy", "affected_metabolizer_statuses": ["normal"], "guideline_source": "PharmGKB", "guideline_id": "PA-FLT1-001", "population_frequency_pct": 8.3, "description": "FLT1 polymorphisms associated with differential anti-VEGF response", "actionable": True, "last_reviewed": now - timedelta(days=45), "created_at": now - timedelta(days=200)},
            {"id": "DGI-003", "drug_name": "Dupilumab", "gene_symbol": "IL4R", "gene_id": "HGNC:6015", "interaction_type": "pharmacodynamic", "evidence_level": EvidenceLevel.LEVEL_1A, "clinical_significance": "IL4R alpha variants affect dupilumab binding and efficacy in atopic dermatitis", "affected_metabolizer_statuses": ["normal", "poor"], "guideline_source": "CPIC", "guideline_id": "CPIC-2024-IL4R", "population_frequency_pct": 15.7, "description": "IL4R gene variants modulate IL-4/IL-13 pathway response to dupilumab", "actionable": True, "last_reviewed": now - timedelta(days=20), "created_at": now - timedelta(days=150)},
            {"id": "DGI-004", "drug_name": "Dupilumab", "gene_symbol": "IL13", "gene_id": "HGNC:5973", "interaction_type": "pharmacodynamic", "evidence_level": EvidenceLevel.LEVEL_1B, "clinical_significance": "IL13 polymorphisms associated with variable dupilumab response", "affected_metabolizer_statuses": ["normal", "intermediate"], "guideline_source": "DPWG", "guideline_id": "DPWG-IL13-2024", "population_frequency_pct": 12.1, "description": "IL13 variants influence type 2 inflammatory pathway modulation", "actionable": True, "last_reviewed": now - timedelta(days=35), "created_at": now - timedelta(days=160)},
            {"id": "DGI-005", "drug_name": "Cemiplimab", "gene_symbol": "PD-L1", "gene_id": "HGNC:17635", "interaction_type": "pharmacodynamic", "evidence_level": EvidenceLevel.LEVEL_1A, "clinical_significance": "PD-L1 expression level directly affects checkpoint inhibitor efficacy", "affected_metabolizer_statuses": ["normal"], "guideline_source": "NCCN", "guideline_id": "NCCN-PDL1-2024", "population_frequency_pct": 35.0, "description": "PD-L1 gene expression is a key biomarker for cemiplimab response prediction", "actionable": True, "last_reviewed": now - timedelta(days=15), "created_at": now - timedelta(days=120)},
            {"id": "DGI-006", "drug_name": "Cemiplimab", "gene_symbol": "HLA-A", "gene_id": "HGNC:4931", "interaction_type": "pharmacodynamic", "evidence_level": EvidenceLevel.LEVEL_2A, "clinical_significance": "HLA-A alleles influence neoantigen presentation and checkpoint inhibitor response", "affected_metabolizer_statuses": ["normal", "intermediate"], "guideline_source": "PharmGKB", "guideline_id": "PA-HLA-A-001", "population_frequency_pct": 18.9, "description": "HLA class I diversity affects immune response to PD-1 blockade", "actionable": True, "last_reviewed": now - timedelta(days=25), "created_at": now - timedelta(days=140)},
            {"id": "DGI-007", "drug_name": "Aflibercept", "gene_symbol": "CYP1A2", "gene_id": "HGNC:2596", "interaction_type": "pharmacokinetic", "evidence_level": EvidenceLevel.LEVEL_2B, "clinical_significance": "CYP1A2 variants may affect aflibercept clearance rates", "affected_metabolizer_statuses": ["ultra_rapid", "poor"], "guideline_source": "CPIC", "guideline_id": "CPIC-CYP1A2-2024", "population_frequency_pct": 5.2, "description": "CYP1A2 metabolizer status influences systemic drug clearance", "actionable": False, "last_reviewed": now - timedelta(days=60), "created_at": now - timedelta(days=220)},
            {"id": "DGI-008", "drug_name": "Dupilumab", "gene_symbol": "FLG", "gene_id": "HGNC:3748", "interaction_type": "pharmacodynamic", "evidence_level": EvidenceLevel.LEVEL_1B, "clinical_significance": "Filaggrin loss-of-function variants predict enhanced dupilumab response", "affected_metabolizer_statuses": ["normal"], "guideline_source": "CPIC", "guideline_id": "CPIC-FLG-2024", "population_frequency_pct": 10.4, "description": "FLG null alleles associated with improved response to IL-4/IL-13 blockade", "actionable": True, "last_reviewed": now - timedelta(days=40), "created_at": now - timedelta(days=170)},
            {"id": "DGI-009", "drug_name": "Cemiplimab", "gene_symbol": "TMB", "gene_id": None, "interaction_type": "pharmacodynamic", "evidence_level": EvidenceLevel.LEVEL_1A, "clinical_significance": "High tumor mutational burden predicts checkpoint inhibitor response", "affected_metabolizer_statuses": [], "guideline_source": "NCCN", "guideline_id": "NCCN-TMB-2024", "population_frequency_pct": 28.0, "description": "TMB-high tumors show enhanced neoantigen load and immunogenicity", "actionable": True, "last_reviewed": now - timedelta(days=10), "created_at": now - timedelta(days=100)},
            {"id": "DGI-010", "drug_name": "Dupilumab", "gene_symbol": "TSLP", "gene_id": "HGNC:30743", "interaction_type": "pharmacodynamic", "evidence_level": EvidenceLevel.LEVEL_2A, "clinical_significance": "TSLP variants influence type 2 immune response and dupilumab efficacy", "affected_metabolizer_statuses": ["normal", "intermediate"], "guideline_source": "PharmGKB", "guideline_id": "PA-TSLP-001", "population_frequency_pct": 7.8, "description": "TSLP gene polymorphisms modulate epithelial cytokine signaling", "actionable": True, "last_reviewed": now - timedelta(days=50), "created_at": now - timedelta(days=190)},
            {"id": "DGI-011", "drug_name": "Cemiplimab", "gene_symbol": "CTLA4", "gene_id": "HGNC:2505", "interaction_type": "pharmacodynamic", "evidence_level": EvidenceLevel.LEVEL_2B, "clinical_significance": "CTLA-4 polymorphisms may modulate immune checkpoint response", "affected_metabolizer_statuses": ["normal"], "guideline_source": "PharmGKB", "guideline_id": "PA-CTLA4-001", "population_frequency_pct": 14.2, "description": "CTLA4 variants influence T-cell co-inhibitory signaling pathway", "actionable": False, "last_reviewed": now - timedelta(days=55), "created_at": now - timedelta(days=210)},
            {"id": "DGI-012", "drug_name": "Aflibercept", "gene_symbol": "KDR", "gene_id": "HGNC:6307", "interaction_type": "pharmacodynamic", "evidence_level": EvidenceLevel.LEVEL_1B, "clinical_significance": "VEGFR2/KDR variants influence anti-VEGF therapy efficacy", "affected_metabolizer_statuses": ["normal", "intermediate"], "guideline_source": "CPIC", "guideline_id": "CPIC-KDR-2024", "population_frequency_pct": 11.6, "description": "KDR gene polymorphisms affect VEGF receptor binding and signaling", "actionable": True, "last_reviewed": now - timedelta(days=28), "created_at": now - timedelta(days=165)},
        ]

        for item in interactions_data:
            self._interactions[item["id"]] = DrugGeneInteraction(**item)

        # --- 12 Genotype-Phenotype Mappings ---
        gp_data = [
            {"id": "GP-001", "gene_symbol": "CYP2D6", "diplotype": "*1/*1", "phenotype": "Normal Metabolizer", "metabolizer_status": MetabolizerStatus.NORMAL, "activity_score": 2.0, "allele_1": "*1", "allele_2": "*1", "functional_status_1": "normal function", "functional_status_2": "normal function", "frequency_european_pct": 40.0, "frequency_african_pct": 35.0, "frequency_asian_pct": 45.0, "reference_source": "CPIC", "created_at": now - timedelta(days=200)},
            {"id": "GP-002", "gene_symbol": "CYP2D6", "diplotype": "*1/*4", "phenotype": "Intermediate Metabolizer", "metabolizer_status": MetabolizerStatus.INTERMEDIATE, "activity_score": 1.0, "allele_1": "*1", "allele_2": "*4", "functional_status_1": "normal function", "functional_status_2": "no function", "frequency_european_pct": 18.0, "frequency_african_pct": 5.0, "frequency_asian_pct": 1.5, "reference_source": "CPIC", "created_at": now - timedelta(days=195)},
            {"id": "GP-003", "gene_symbol": "CYP2D6", "diplotype": "*4/*4", "phenotype": "Poor Metabolizer", "metabolizer_status": MetabolizerStatus.POOR, "activity_score": 0.0, "allele_1": "*4", "allele_2": "*4", "functional_status_1": "no function", "functional_status_2": "no function", "frequency_european_pct": 5.5, "frequency_african_pct": 1.5, "frequency_asian_pct": 0.5, "reference_source": "CPIC", "created_at": now - timedelta(days=190)},
            {"id": "GP-004", "gene_symbol": "CYP2D6", "diplotype": "*1/*1xN", "phenotype": "Ultra-rapid Metabolizer", "metabolizer_status": MetabolizerStatus.ULTRA_RAPID, "activity_score": 3.0, "allele_1": "*1", "allele_2": "*1xN", "functional_status_1": "normal function", "functional_status_2": "increased function", "frequency_european_pct": 3.0, "frequency_african_pct": 20.0, "frequency_asian_pct": 1.0, "reference_source": "CPIC", "created_at": now - timedelta(days=185)},
            {"id": "GP-005", "gene_symbol": "CYP2C19", "diplotype": "*1/*1", "phenotype": "Normal Metabolizer", "metabolizer_status": MetabolizerStatus.NORMAL, "activity_score": 2.0, "allele_1": "*1", "allele_2": "*1", "functional_status_1": "normal function", "functional_status_2": "normal function", "frequency_european_pct": 40.0, "frequency_african_pct": 33.0, "frequency_asian_pct": 35.0, "reference_source": "CPIC", "created_at": now - timedelta(days=180)},
            {"id": "GP-006", "gene_symbol": "CYP2C19", "diplotype": "*1/*2", "phenotype": "Intermediate Metabolizer", "metabolizer_status": MetabolizerStatus.INTERMEDIATE, "activity_score": 1.0, "allele_1": "*1", "allele_2": "*2", "functional_status_1": "normal function", "functional_status_2": "no function", "frequency_european_pct": 25.0, "frequency_african_pct": 28.0, "frequency_asian_pct": 40.0, "reference_source": "CPIC", "created_at": now - timedelta(days=175)},
            {"id": "GP-007", "gene_symbol": "CYP2C19", "diplotype": "*2/*2", "phenotype": "Poor Metabolizer", "metabolizer_status": MetabolizerStatus.POOR, "activity_score": 0.0, "allele_1": "*2", "allele_2": "*2", "functional_status_1": "no function", "functional_status_2": "no function", "frequency_european_pct": 2.5, "frequency_african_pct": 4.0, "frequency_asian_pct": 14.0, "reference_source": "CPIC", "created_at": now - timedelta(days=170)},
            {"id": "GP-008", "gene_symbol": "CYP2C19", "diplotype": "*17/*17", "phenotype": "Ultra-rapid Metabolizer", "metabolizer_status": MetabolizerStatus.ULTRA_RAPID, "activity_score": 3.0, "allele_1": "*17", "allele_2": "*17", "functional_status_1": "increased function", "functional_status_2": "increased function", "frequency_european_pct": 4.5, "frequency_african_pct": 5.5, "frequency_asian_pct": 0.5, "reference_source": "CPIC", "created_at": now - timedelta(days=165)},
            {"id": "GP-009", "gene_symbol": "CYP3A5", "diplotype": "*1/*3", "phenotype": "Intermediate Metabolizer", "metabolizer_status": MetabolizerStatus.INTERMEDIATE, "activity_score": 1.0, "allele_1": "*1", "allele_2": "*3", "functional_status_1": "normal function", "functional_status_2": "no function", "frequency_european_pct": 15.0, "frequency_african_pct": 50.0, "frequency_asian_pct": 25.0, "reference_source": "CPIC", "created_at": now - timedelta(days=160)},
            {"id": "GP-010", "gene_symbol": "DPYD", "diplotype": "*1/*1", "phenotype": "Normal Metabolizer", "metabolizer_status": MetabolizerStatus.NORMAL, "activity_score": 2.0, "allele_1": "*1", "allele_2": "*1", "functional_status_1": "normal function", "functional_status_2": "normal function", "frequency_european_pct": 95.0, "frequency_african_pct": 96.0, "frequency_asian_pct": 97.0, "reference_source": "CPIC", "created_at": now - timedelta(days=155)},
            {"id": "GP-011", "gene_symbol": "SLCO1B1", "diplotype": "*1a/*1a", "phenotype": "Normal Function", "metabolizer_status": MetabolizerStatus.NORMAL, "activity_score": 2.0, "allele_1": "*1a", "allele_2": "*1a", "functional_status_1": "normal function", "functional_status_2": "normal function", "frequency_european_pct": 60.0, "frequency_african_pct": 70.0, "frequency_asian_pct": 55.0, "reference_source": "CPIC", "created_at": now - timedelta(days=150)},
            {"id": "GP-012", "gene_symbol": "TPMT", "diplotype": "*1/*3A", "phenotype": "Intermediate Metabolizer", "metabolizer_status": MetabolizerStatus.INTERMEDIATE, "activity_score": 1.0, "allele_1": "*1", "allele_2": "*3A", "functional_status_1": "normal function", "functional_status_2": "no function", "frequency_european_pct": 8.0, "frequency_african_pct": 3.0, "frequency_asian_pct": 2.0, "reference_source": "CPIC", "created_at": now - timedelta(days=145)},
        ]

        for item in gp_data:
            self._genotype_phenotypes[item["id"]] = GenotypePhenotype(**item)

        # --- 12 PGx Test Orders ---
        orders_data = [
            {"id": "PTO-001", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1001", "site_id": "SITE-101", "panel_name": "Ophthalmic PGx Panel", "genes_tested": ["VEGFA", "FLT1", "KDR", "CYP1A2"], "status": TestStatus.REPORTED, "ordered_by": "Dr. Chen", "ordered_date": now - timedelta(days=90), "sample_type": "blood", "sample_collected_date": now - timedelta(days=88), "lab_name": "GeneSight Clinical Lab", "lab_accession": "GS-2024-0001", "resulted_date": now - timedelta(days=78), "reported_date": now - timedelta(days=75), "turnaround_days": 12, "created_at": now - timedelta(days=90)},
            {"id": "PTO-002", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1002", "site_id": "SITE-101", "panel_name": "Ophthalmic PGx Panel", "genes_tested": ["VEGFA", "FLT1", "KDR"], "status": TestStatus.REPORTED, "ordered_by": "Dr. Rodriguez", "ordered_date": now - timedelta(days=85), "sample_type": "blood", "sample_collected_date": now - timedelta(days=83), "lab_name": "GeneSight Clinical Lab", "lab_accession": "GS-2024-0002", "resulted_date": now - timedelta(days=73), "reported_date": now - timedelta(days=70), "turnaround_days": 15, "created_at": now - timedelta(days=85)},
            {"id": "PTO-003", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1003", "site_id": "SITE-102", "panel_name": "Ophthalmic PGx Panel", "genes_tested": ["VEGFA", "FLT1"], "status": TestStatus.RESULTED, "ordered_by": "Dr. Thompson", "ordered_date": now - timedelta(days=60), "sample_type": "blood", "sample_collected_date": now - timedelta(days=58), "lab_name": "Invitae Pharmacogenomics", "lab_accession": "INV-2024-0003", "resulted_date": now - timedelta(days=48), "reported_date": None, "turnaround_days": 12, "created_at": now - timedelta(days=60)},
            {"id": "PTO-004", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1004", "site_id": "SITE-102", "panel_name": "Comprehensive PGx Panel", "genes_tested": ["VEGFA", "FLT1", "KDR", "CYP1A2", "CYP2D6"], "status": TestStatus.IN_PROCESS, "ordered_by": "Dr. Kim", "ordered_date": now - timedelta(days=30), "sample_type": "blood", "sample_collected_date": now - timedelta(days=28), "lab_name": "GeneSight Clinical Lab", "lab_accession": "GS-2024-0004", "resulted_date": None, "reported_date": None, "turnaround_days": None, "created_at": now - timedelta(days=30)},
            {"id": "PTO-005", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2001", "site_id": "SITE-104", "panel_name": "Immunology PGx Panel", "genes_tested": ["IL4R", "IL13", "FLG", "TSLP"], "status": TestStatus.REPORTED, "ordered_by": "Dr. Williams", "ordered_date": now - timedelta(days=100), "sample_type": "blood", "sample_collected_date": now - timedelta(days=98), "lab_name": "OneOme RightMed", "lab_accession": "OM-2024-0005", "resulted_date": now - timedelta(days=86), "reported_date": now - timedelta(days=83), "turnaround_days": 14, "created_at": now - timedelta(days=100)},
            {"id": "PTO-006", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2002", "site_id": "SITE-104", "panel_name": "Immunology PGx Panel", "genes_tested": ["IL4R", "IL13", "FLG"], "status": TestStatus.REPORTED, "ordered_by": "Dr. Martinez", "ordered_date": now - timedelta(days=95), "sample_type": "blood", "sample_collected_date": now - timedelta(days=93), "lab_name": "OneOme RightMed", "lab_accession": "OM-2024-0006", "resulted_date": now - timedelta(days=82), "reported_date": now - timedelta(days=80), "turnaround_days": 13, "created_at": now - timedelta(days=95)},
            {"id": "PTO-007", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2003", "site_id": "SITE-105", "panel_name": "Immunology PGx Panel", "genes_tested": ["IL4R", "IL13", "TSLP"], "status": TestStatus.SAMPLE_COLLECTED, "ordered_by": "Dr. Nakamura", "ordered_date": now - timedelta(days=20), "sample_type": "blood", "sample_collected_date": now - timedelta(days=18), "lab_name": "Invitae Pharmacogenomics", "lab_accession": None, "resulted_date": None, "reported_date": None, "turnaround_days": None, "created_at": now - timedelta(days=20)},
            {"id": "PTO-008", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2004", "site_id": "SITE-105", "panel_name": "Comprehensive Immunology Panel", "genes_tested": ["IL4R", "IL13", "FLG", "TSLP", "CYP2D6"], "status": TestStatus.ORDERED, "ordered_by": "Dr. Sullivan", "ordered_date": now - timedelta(days=5), "sample_type": "blood", "sample_collected_date": None, "lab_name": None, "lab_accession": None, "resulted_date": None, "reported_date": None, "turnaround_days": None, "created_at": now - timedelta(days=5)},
            {"id": "PTO-009", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3001", "site_id": "SITE-107", "panel_name": "Oncology PGx Panel", "genes_tested": ["PD-L1", "HLA-A", "CTLA4", "TMB"], "status": TestStatus.REPORTED, "ordered_by": "Dr. Liu", "ordered_date": now - timedelta(days=110), "sample_type": "blood", "sample_collected_date": now - timedelta(days=108), "lab_name": "Foundation Medicine", "lab_accession": "FM-2024-0009", "resulted_date": now - timedelta(days=95), "reported_date": now - timedelta(days=92), "turnaround_days": 15, "created_at": now - timedelta(days=110)},
            {"id": "PTO-010", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3002", "site_id": "SITE-107", "panel_name": "Oncology PGx Panel", "genes_tested": ["PD-L1", "HLA-A", "TMB"], "status": TestStatus.REPORTED, "ordered_by": "Dr. Foster", "ordered_date": now - timedelta(days=105), "sample_type": "blood", "sample_collected_date": now - timedelta(days=103), "lab_name": "Foundation Medicine", "lab_accession": "FM-2024-0010", "resulted_date": now - timedelta(days=92), "reported_date": now - timedelta(days=89), "turnaround_days": 13, "created_at": now - timedelta(days=105)},
            {"id": "PTO-011", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3003", "site_id": "SITE-108", "panel_name": "Oncology PGx Panel", "genes_tested": ["PD-L1", "HLA-A", "CTLA4"], "status": TestStatus.IN_PROCESS, "ordered_by": "Dr. Wong", "ordered_date": now - timedelta(days=25), "sample_type": "blood", "sample_collected_date": now - timedelta(days=23), "lab_name": "Foundation Medicine", "lab_accession": "FM-2024-0011", "resulted_date": None, "reported_date": None, "turnaround_days": None, "created_at": now - timedelta(days=25)},
            {"id": "PTO-012", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3004", "site_id": "SITE-108", "panel_name": "Comprehensive Oncology Panel", "genes_tested": ["PD-L1", "HLA-A", "CTLA4", "TMB", "CYP2D6"], "status": TestStatus.CANCELLED, "ordered_by": "Dr. Harris", "ordered_date": now - timedelta(days=40), "sample_type": "blood", "sample_collected_date": None, "lab_name": None, "lab_accession": None, "resulted_date": None, "reported_date": None, "turnaround_days": None, "created_at": now - timedelta(days=40)},
        ]

        for item in orders_data:
            self._test_orders[item["id"]] = PGxTestOrder(**item)

        # --- 12 Variant Results ---
        variants_data = [
            {"id": "VR-001", "test_order_id": "PTO-001", "subject_id": "PT-1001", "gene_symbol": "VEGFA", "variant_name": "rs2010963", "rs_id": "rs2010963", "hgvs_coding": "c.-634G>C", "hgvs_protein": None, "zygosity": "heterozygous", "allele_frequency": 0.34, "significance": VariantSignificance.PATHOGENIC, "diplotype": None, "phenotype": "Reduced VEGF expression", "metabolizer_status": MetabolizerStatus.INTERMEDIATE, "activity_score": 1.0, "interpretation": "Associated with reduced anti-VEGF response", "reviewed_by": "Dr. Chen", "created_at": now - timedelta(days=78)},
            {"id": "VR-002", "test_order_id": "PTO-001", "subject_id": "PT-1001", "gene_symbol": "FLT1", "variant_name": "rs722503", "rs_id": "rs722503", "hgvs_coding": "c.3025A>G", "hgvs_protein": "p.Thr1009Ala", "zygosity": "homozygous", "allele_frequency": 0.12, "significance": VariantSignificance.LIKELY_BENIGN, "diplotype": None, "phenotype": "Normal receptor function", "metabolizer_status": MetabolizerStatus.NORMAL, "activity_score": 2.0, "interpretation": "Normal VEGFR1 function expected", "reviewed_by": "Dr. Rodriguez", "created_at": now - timedelta(days=78)},
            {"id": "VR-003", "test_order_id": "PTO-002", "subject_id": "PT-1002", "gene_symbol": "VEGFA", "variant_name": "rs3025039", "rs_id": "rs3025039", "hgvs_coding": "c.936C>T", "hgvs_protein": None, "zygosity": "heterozygous", "allele_frequency": 0.18, "significance": VariantSignificance.UNCERTAIN, "diplotype": None, "phenotype": "Uncertain VEGF expression impact", "metabolizer_status": None, "activity_score": None, "interpretation": "Variant of uncertain significance; clinical correlation recommended", "reviewed_by": None, "created_at": now - timedelta(days=73)},
            {"id": "VR-004", "test_order_id": "PTO-005", "subject_id": "PT-2001", "gene_symbol": "IL4R", "variant_name": "rs1805010", "rs_id": "rs1805010", "hgvs_coding": "c.223A>G", "hgvs_protein": "p.Ile75Val", "zygosity": "heterozygous", "allele_frequency": 0.42, "significance": VariantSignificance.LIKELY_PATHOGENIC, "diplotype": None, "phenotype": "Altered IL-4 receptor signaling", "metabolizer_status": MetabolizerStatus.INTERMEDIATE, "activity_score": 1.5, "interpretation": "May reduce dupilumab binding affinity; monitor response closely", "reviewed_by": "Dr. Williams", "created_at": now - timedelta(days=86)},
            {"id": "VR-005", "test_order_id": "PTO-005", "subject_id": "PT-2001", "gene_symbol": "FLG", "variant_name": "R501X", "rs_id": "rs61816761", "hgvs_coding": "c.1501C>T", "hgvs_protein": "p.Arg501Ter", "zygosity": "heterozygous", "allele_frequency": 0.04, "significance": VariantSignificance.PATHOGENIC, "diplotype": None, "phenotype": "Loss of filaggrin function", "metabolizer_status": None, "activity_score": None, "interpretation": "FLG loss-of-function predicts enhanced dupilumab response", "reviewed_by": "Dr. Martinez", "created_at": now - timedelta(days=86)},
            {"id": "VR-006", "test_order_id": "PTO-006", "subject_id": "PT-2002", "gene_symbol": "IL13", "variant_name": "rs20541", "rs_id": "rs20541", "hgvs_coding": "c.431G>A", "hgvs_protein": "p.Arg144Gln", "zygosity": "homozygous", "allele_frequency": 0.25, "significance": VariantSignificance.PATHOGENIC, "diplotype": None, "phenotype": "Enhanced IL-13 activity", "metabolizer_status": MetabolizerStatus.NORMAL, "activity_score": 2.0, "interpretation": "Homozygous variant associated with enhanced type 2 inflammation", "reviewed_by": "Dr. Nakamura", "created_at": now - timedelta(days=82)},
            {"id": "VR-007", "test_order_id": "PTO-009", "subject_id": "PT-3001", "gene_symbol": "PD-L1", "variant_name": "High Expression", "rs_id": None, "hgvs_coding": None, "hgvs_protein": None, "zygosity": "N/A", "allele_frequency": None, "significance": VariantSignificance.PATHOGENIC, "diplotype": None, "phenotype": "PD-L1 TPS >= 50%", "metabolizer_status": None, "activity_score": None, "interpretation": "High PD-L1 expression predicts favorable checkpoint inhibitor response", "reviewed_by": "Dr. Liu", "created_at": now - timedelta(days=95)},
            {"id": "VR-008", "test_order_id": "PTO-009", "subject_id": "PT-3001", "gene_symbol": "HLA-A", "variant_name": "HLA-A*02:01", "rs_id": None, "hgvs_coding": None, "hgvs_protein": None, "zygosity": "heterozygous", "allele_frequency": 0.29, "significance": VariantSignificance.BENIGN, "diplotype": "HLA-A*02:01/HLA-A*03:01", "phenotype": "Normal MHC class I presentation", "metabolizer_status": None, "activity_score": None, "interpretation": "Common HLA-A allele; broad neoantigen presentation capability", "reviewed_by": "Dr. Foster", "created_at": now - timedelta(days=95)},
            {"id": "VR-009", "test_order_id": "PTO-010", "subject_id": "PT-3002", "gene_symbol": "PD-L1", "variant_name": "Low Expression", "rs_id": None, "hgvs_coding": None, "hgvs_protein": None, "zygosity": "N/A", "allele_frequency": None, "significance": VariantSignificance.LIKELY_PATHOGENIC, "diplotype": None, "phenotype": "PD-L1 TPS 1-49%", "metabolizer_status": None, "activity_score": None, "interpretation": "Low PD-L1 expression; response to cemiplimab may be reduced", "reviewed_by": "Dr. Wong", "created_at": now - timedelta(days=92)},
            {"id": "VR-010", "test_order_id": "PTO-010", "subject_id": "PT-3002", "gene_symbol": "TMB", "variant_name": "TMB-High", "rs_id": None, "hgvs_coding": None, "hgvs_protein": None, "zygosity": "N/A", "allele_frequency": None, "significance": VariantSignificance.PATHOGENIC, "diplotype": None, "phenotype": "TMB >= 10 mut/Mb", "metabolizer_status": None, "activity_score": None, "interpretation": "High TMB compensates for low PD-L1; immunotherapy benefit expected", "reviewed_by": "Dr. Harris", "created_at": now - timedelta(days=92)},
            {"id": "VR-011", "test_order_id": "PTO-003", "subject_id": "PT-1003", "gene_symbol": "VEGFA", "variant_name": "rs833061", "rs_id": "rs833061", "hgvs_coding": "c.-460T>C", "hgvs_protein": None, "zygosity": "homozygous", "allele_frequency": 0.45, "significance": VariantSignificance.LIKELY_BENIGN, "diplotype": None, "phenotype": "Normal VEGF expression", "metabolizer_status": MetabolizerStatus.NORMAL, "activity_score": 2.0, "interpretation": "Common variant; normal anti-VEGF response expected", "reviewed_by": "Dr. Thompson", "created_at": now - timedelta(days=48)},
            {"id": "VR-012", "test_order_id": "PTO-006", "subject_id": "PT-2002", "gene_symbol": "IL4R", "variant_name": "rs1801275", "rs_id": "rs1801275", "hgvs_coding": "c.1727A>G", "hgvs_protein": "p.Gln576Arg", "zygosity": "heterozygous", "allele_frequency": 0.15, "significance": VariantSignificance.UNCERTAIN, "diplotype": None, "phenotype": "Uncertain IL-4R impact", "metabolizer_status": None, "activity_score": None, "interpretation": "VUS; insufficient evidence for clinical actionability", "reviewed_by": None, "created_at": now - timedelta(days=82)},
        ]

        for item in variants_data:
            self._variant_results[item["id"]] = VariantResult(**item)

        # --- 12 Dosing Recommendations ---
        recs_data = [
            {"id": "DR-001", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1001", "drug_name": "Aflibercept", "gene_symbol": "VEGFA", "metabolizer_status": MetabolizerStatus.INTERMEDIATE, "action": RecommendationAction.MONITORING_REQUIRED, "standard_dose": "2 mg intravitreal q8w", "recommended_dose": "2 mg intravitreal q8w with enhanced OCT monitoring", "alternative_drug": None, "recommendation_text": "VEGFA rs2010963 heterozygous variant detected. Standard dose recommended with enhanced monitoring for treatment response at weeks 4, 8, and 12.", "evidence_level": EvidenceLevel.LEVEL_1A, "guideline_source": "CPIC", "variant_result_id": "VR-001", "accepted": True, "accepted_by": "Dr. Chen", "accepted_date": now - timedelta(days=70), "override_reason": None, "created_at": now - timedelta(days=75)},
            {"id": "DR-002", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1002", "drug_name": "Aflibercept", "gene_symbol": "VEGFA", "metabolizer_status": MetabolizerStatus.NORMAL, "action": RecommendationAction.STANDARD_DOSE, "standard_dose": "2 mg intravitreal q8w", "recommended_dose": None, "alternative_drug": None, "recommendation_text": "No actionable VEGFA variants detected. Proceed with standard dosing protocol.", "evidence_level": EvidenceLevel.LEVEL_1A, "guideline_source": "CPIC", "variant_result_id": "VR-003", "accepted": True, "accepted_by": "Dr. Rodriguez", "accepted_date": now - timedelta(days=68), "override_reason": None, "created_at": now - timedelta(days=70)},
            {"id": "DR-003", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1003", "drug_name": "Aflibercept", "gene_symbol": "VEGFA", "metabolizer_status": MetabolizerStatus.NORMAL, "action": RecommendationAction.STANDARD_DOSE, "standard_dose": "2 mg intravitreal q8w", "recommended_dose": None, "alternative_drug": None, "recommendation_text": "Common VEGFA variant detected (rs833061). Standard dose appropriate.", "evidence_level": EvidenceLevel.LEVEL_2A, "guideline_source": "PharmGKB", "variant_result_id": "VR-011", "accepted": True, "accepted_by": "Dr. Thompson", "accepted_date": now - timedelta(days=45), "override_reason": None, "created_at": now - timedelta(days=48)},
            {"id": "DR-004", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2001", "drug_name": "Dupilumab", "gene_symbol": "IL4R", "metabolizer_status": MetabolizerStatus.INTERMEDIATE, "action": RecommendationAction.DOSE_INCREASE, "standard_dose": "300 mg SC q2w", "recommended_dose": "300 mg SC qw (weekly dosing)", "alternative_drug": None, "recommendation_text": "IL4R rs1805010 variant may reduce binding. Consider more frequent dosing or enhanced monitoring of EASI scores.", "evidence_level": EvidenceLevel.LEVEL_1A, "guideline_source": "CPIC", "variant_result_id": "VR-004", "accepted": False, "accepted_by": None, "accepted_date": None, "override_reason": "Investigator prefers standard dose with enhanced EASI monitoring per protocol", "created_at": now - timedelta(days=83)},
            {"id": "DR-005", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2001", "drug_name": "Dupilumab", "gene_symbol": "FLG", "metabolizer_status": MetabolizerStatus.NORMAL, "action": RecommendationAction.STANDARD_DOSE, "standard_dose": "300 mg SC q2w", "recommended_dose": None, "alternative_drug": None, "recommendation_text": "FLG R501X loss-of-function variant detected. Predicts enhanced dupilumab response. Standard dose recommended.", "evidence_level": EvidenceLevel.LEVEL_1B, "guideline_source": "CPIC", "variant_result_id": "VR-005", "accepted": True, "accepted_by": "Dr. Williams", "accepted_date": now - timedelta(days=80), "override_reason": None, "created_at": now - timedelta(days=83)},
            {"id": "DR-006", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2002", "drug_name": "Dupilumab", "gene_symbol": "IL13", "metabolizer_status": MetabolizerStatus.NORMAL, "action": RecommendationAction.MONITORING_REQUIRED, "standard_dose": "300 mg SC q2w", "recommended_dose": "300 mg SC q2w with biomarker monitoring", "alternative_drug": None, "recommendation_text": "Homozygous IL13 rs20541 variant associated with enhanced type 2 inflammation. Standard dose with IgE and eosinophil monitoring recommended.", "evidence_level": EvidenceLevel.LEVEL_1B, "guideline_source": "DPWG", "variant_result_id": "VR-006", "accepted": True, "accepted_by": "Dr. Nakamura", "accepted_date": now - timedelta(days=78), "override_reason": None, "created_at": now - timedelta(days=80)},
            {"id": "DR-007", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3001", "drug_name": "Cemiplimab", "gene_symbol": "PD-L1", "metabolizer_status": MetabolizerStatus.NORMAL, "action": RecommendationAction.STANDARD_DOSE, "standard_dose": "350 mg IV q3w", "recommended_dose": None, "alternative_drug": None, "recommendation_text": "High PD-L1 expression (TPS >= 50%). Favorable biomarker profile for cemiplimab. Standard dose recommended.", "evidence_level": EvidenceLevel.LEVEL_1A, "guideline_source": "NCCN", "variant_result_id": "VR-007", "accepted": True, "accepted_by": "Dr. Liu", "accepted_date": now - timedelta(days=88), "override_reason": None, "created_at": now - timedelta(days=92)},
            {"id": "DR-008", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3002", "drug_name": "Cemiplimab", "gene_symbol": "PD-L1", "metabolizer_status": MetabolizerStatus.NORMAL, "action": RecommendationAction.MONITORING_REQUIRED, "standard_dose": "350 mg IV q3w", "recommended_dose": "350 mg IV q3w with enhanced imaging", "alternative_drug": None, "recommendation_text": "Low PD-L1 expression but TMB-high. Continue cemiplimab with enhanced imaging surveillance at q6w intervals.", "evidence_level": EvidenceLevel.LEVEL_1A, "guideline_source": "NCCN", "variant_result_id": "VR-009", "accepted": True, "accepted_by": "Dr. Foster", "accepted_date": now - timedelta(days=85), "override_reason": None, "created_at": now - timedelta(days=89)},
            {"id": "DR-009", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3002", "drug_name": "Cemiplimab", "gene_symbol": "TMB", "metabolizer_status": MetabolizerStatus.NORMAL, "action": RecommendationAction.STANDARD_DOSE, "standard_dose": "350 mg IV q3w", "recommended_dose": None, "alternative_drug": None, "recommendation_text": "TMB-high (>= 10 mut/Mb) detected. Strong predictor of checkpoint inhibitor benefit. Standard dose appropriate.", "evidence_level": EvidenceLevel.LEVEL_1A, "guideline_source": "NCCN", "variant_result_id": "VR-010", "accepted": True, "accepted_by": "Dr. Foster", "accepted_date": now - timedelta(days=85), "override_reason": None, "created_at": now - timedelta(days=89)},
            {"id": "DR-010", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2002", "drug_name": "Dupilumab", "gene_symbol": "IL4R", "metabolizer_status": MetabolizerStatus.NORMAL, "action": RecommendationAction.NO_ACTION, "standard_dose": "300 mg SC q2w", "recommended_dose": None, "alternative_drug": None, "recommendation_text": "IL4R rs1801275 is a VUS with insufficient evidence for clinical action. No dosing change recommended.", "evidence_level": EvidenceLevel.LEVEL_3, "guideline_source": "PharmGKB", "variant_result_id": "VR-012", "accepted": True, "accepted_by": "Dr. Martinez", "accepted_date": now - timedelta(days=78), "override_reason": None, "created_at": now - timedelta(days=80)},
            {"id": "DR-011", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1001", "drug_name": "Aflibercept", "gene_symbol": "FLT1", "metabolizer_status": MetabolizerStatus.NORMAL, "action": RecommendationAction.STANDARD_DOSE, "standard_dose": "2 mg intravitreal q8w", "recommended_dose": None, "alternative_drug": None, "recommendation_text": "FLT1 rs722503 homozygous variant is likely benign. Standard aflibercept dosing maintained.", "evidence_level": EvidenceLevel.LEVEL_2A, "guideline_source": "PharmGKB", "variant_result_id": "VR-002", "accepted": True, "accepted_by": "Dr. Rodriguez", "accepted_date": now - timedelta(days=72), "override_reason": None, "created_at": now - timedelta(days=75)},
            {"id": "DR-012", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3001", "drug_name": "Cemiplimab", "gene_symbol": "HLA-A", "metabolizer_status": MetabolizerStatus.NORMAL, "action": RecommendationAction.NO_ACTION, "standard_dose": "350 mg IV q3w", "recommended_dose": None, "alternative_drug": None, "recommendation_text": "Common HLA-A*02:01 allele detected. Broad neoantigen presentation expected. No dosing change required.", "evidence_level": EvidenceLevel.LEVEL_2A, "guideline_source": "PharmGKB", "variant_result_id": "VR-008", "accepted": True, "accepted_by": "Dr. Liu", "accepted_date": now - timedelta(days=88), "override_reason": None, "created_at": now - timedelta(days=92)},
        ]

        for item in recs_data:
            self._dosing_recommendations[item["id"]] = DosingRecommendation(**item)

    # ------------------------------------------------------------------
    # Drug-Gene Interactions
    # ------------------------------------------------------------------

    def list_drug_gene_interactions(
        self, *, trial_id: str | None = None,
    ) -> list[DrugGeneInteraction]:
        """List drug-gene interactions."""
        with self._lock:
            result = list(self._interactions.values())
        # Drug-gene interactions are not tied to trials directly,
        # but we keep the signature consistent for API uniformity.
        return sorted(result, key=lambda x: x.id)

    def get_drug_gene_interaction(self, interaction_id: str) -> DrugGeneInteraction | None:
        with self._lock:
            return self._interactions.get(interaction_id)

    def create_drug_gene_interaction(self, payload: DrugGeneInteractionCreate) -> DrugGeneInteraction:
        now = datetime.now(timezone.utc)
        iid = f"DGI-{uuid4().hex[:8].upper()}"
        interaction = DrugGeneInteraction(
            id=iid,
            drug_name=payload.drug_name,
            gene_symbol=payload.gene_symbol,
            gene_id=payload.gene_id,
            interaction_type=payload.interaction_type,
            evidence_level=payload.evidence_level,
            clinical_significance=payload.clinical_significance,
            guideline_source=payload.guideline_source,
            description=payload.description,
            actionable=payload.actionable,
            last_reviewed=now,
            created_at=now,
        )
        with self._lock:
            self._interactions[iid] = interaction
        logger.info("Created drug-gene interaction %s: %s/%s", iid, payload.drug_name, payload.gene_symbol)
        return interaction

    def update_drug_gene_interaction(
        self, interaction_id: str, payload: DrugGeneInteractionUpdate,
    ) -> DrugGeneInteraction | None:
        with self._lock:
            existing = self._interactions.get(interaction_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DrugGeneInteraction(**data)
            self._interactions[interaction_id] = updated
        return updated

    def delete_drug_gene_interaction(self, interaction_id: str) -> bool:
        with self._lock:
            if interaction_id in self._interactions:
                del self._interactions[interaction_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Genotype-Phenotype Mappings
    # ------------------------------------------------------------------

    def list_genotype_phenotypes(
        self, *, trial_id: str | None = None,
    ) -> list[GenotypePhenotype]:
        with self._lock:
            result = list(self._genotype_phenotypes.values())
        return sorted(result, key=lambda x: x.id)

    def get_genotype_phenotype(self, gp_id: str) -> GenotypePhenotype | None:
        with self._lock:
            return self._genotype_phenotypes.get(gp_id)

    def create_genotype_phenotype(self, payload: GenotypePhenotypeCreate) -> GenotypePhenotype:
        now = datetime.now(timezone.utc)
        gp_id = f"GP-{uuid4().hex[:8].upper()}"
        gp = GenotypePhenotype(
            id=gp_id,
            gene_symbol=payload.gene_symbol,
            diplotype=payload.diplotype,
            phenotype=payload.phenotype,
            metabolizer_status=payload.metabolizer_status,
            activity_score=payload.activity_score,
            allele_1=payload.allele_1,
            allele_2=payload.allele_2,
            reference_source=payload.reference_source,
            created_at=now,
        )
        with self._lock:
            self._genotype_phenotypes[gp_id] = gp
        logger.info("Created genotype-phenotype %s: %s %s", gp_id, payload.gene_symbol, payload.diplotype)
        return gp

    def update_genotype_phenotype(
        self, gp_id: str, payload: GenotypePhenotypeUpdate,
    ) -> GenotypePhenotype | None:
        with self._lock:
            existing = self._genotype_phenotypes.get(gp_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = GenotypePhenotype(**data)
            self._genotype_phenotypes[gp_id] = updated
        return updated

    def delete_genotype_phenotype(self, gp_id: str) -> bool:
        with self._lock:
            if gp_id in self._genotype_phenotypes:
                del self._genotype_phenotypes[gp_id]
                return True
            return False

    # ------------------------------------------------------------------
    # PGx Test Orders
    # ------------------------------------------------------------------

    def list_test_orders(
        self, *, trial_id: str | None = None,
    ) -> list[PGxTestOrder]:
        with self._lock:
            result = list(self._test_orders.values())
        if trial_id is not None:
            result = [o for o in result if o.trial_id == trial_id]
        return sorted(result, key=lambda x: x.id)

    def get_test_order(self, order_id: str) -> PGxTestOrder | None:
        with self._lock:
            return self._test_orders.get(order_id)

    def create_test_order(self, payload: PGxTestOrderCreate) -> PGxTestOrder:
        now = datetime.now(timezone.utc)
        oid = f"PTO-{uuid4().hex[:8].upper()}"
        order = PGxTestOrder(
            id=oid,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            site_id=payload.site_id,
            panel_name=payload.panel_name,
            genes_tested=payload.genes_tested,
            status=TestStatus.ORDERED,
            ordered_by=payload.ordered_by,
            ordered_date=now,
            sample_type=payload.sample_type,
            lab_name=payload.lab_name,
            created_at=now,
        )
        with self._lock:
            self._test_orders[oid] = order
        logger.info("Created PGx test order %s: trial=%s subject=%s", oid, payload.trial_id, payload.subject_id)
        return order

    def update_test_order(
        self, order_id: str, payload: PGxTestOrderUpdate,
    ) -> PGxTestOrder | None:
        with self._lock:
            existing = self._test_orders.get(order_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = PGxTestOrder(**data)
            self._test_orders[order_id] = updated
        return updated

    def delete_test_order(self, order_id: str) -> bool:
        with self._lock:
            if order_id in self._test_orders:
                del self._test_orders[order_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Variant Results
    # ------------------------------------------------------------------

    def list_variant_results(
        self, *, trial_id: str | None = None,
    ) -> list[VariantResult]:
        with self._lock:
            result = list(self._variant_results.values())
        if trial_id is not None:
            # Filter by trial through test orders
            trial_order_ids = {
                o.id for o in self._test_orders.values() if o.trial_id == trial_id
            }
            result = [v for v in result if v.test_order_id in trial_order_ids]
        return sorted(result, key=lambda x: x.id)

    def get_variant_result(self, result_id: str) -> VariantResult | None:
        with self._lock:
            return self._variant_results.get(result_id)

    def create_variant_result(self, payload: VariantResultCreate) -> VariantResult:
        now = datetime.now(timezone.utc)
        vid = f"VR-{uuid4().hex[:8].upper()}"
        vr = VariantResult(
            id=vid,
            test_order_id=payload.test_order_id,
            subject_id=payload.subject_id,
            gene_symbol=payload.gene_symbol,
            variant_name=payload.variant_name,
            zygosity=payload.zygosity,
            rs_id=payload.rs_id,
            significance=payload.significance,
            diplotype=payload.diplotype,
            phenotype=payload.phenotype,
            metabolizer_status=payload.metabolizer_status,
            created_at=now,
        )
        with self._lock:
            self._variant_results[vid] = vr
        logger.info("Created variant result %s: %s %s", vid, payload.gene_symbol, payload.variant_name)
        return vr

    def update_variant_result(
        self, result_id: str, payload: VariantResultUpdate,
    ) -> VariantResult | None:
        with self._lock:
            existing = self._variant_results.get(result_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = VariantResult(**data)
            self._variant_results[result_id] = updated
        return updated

    def delete_variant_result(self, result_id: str) -> bool:
        with self._lock:
            if result_id in self._variant_results:
                del self._variant_results[result_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Dosing Recommendations
    # ------------------------------------------------------------------

    def list_dosing_recommendations(
        self, *, trial_id: str | None = None,
    ) -> list[DosingRecommendation]:
        with self._lock:
            result = list(self._dosing_recommendations.values())
        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        return sorted(result, key=lambda x: x.id)

    def get_dosing_recommendation(self, rec_id: str) -> DosingRecommendation | None:
        with self._lock:
            return self._dosing_recommendations.get(rec_id)

    def create_dosing_recommendation(self, payload: DosingRecommendationCreate) -> DosingRecommendation:
        now = datetime.now(timezone.utc)
        rid = f"DR-{uuid4().hex[:8].upper()}"
        rec = DosingRecommendation(
            id=rid,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            drug_name=payload.drug_name,
            gene_symbol=payload.gene_symbol,
            metabolizer_status=payload.metabolizer_status,
            action=payload.action,
            standard_dose=payload.standard_dose,
            recommended_dose=payload.recommended_dose,
            alternative_drug=payload.alternative_drug,
            recommendation_text=payload.recommendation_text,
            evidence_level=payload.evidence_level,
            guideline_source=payload.guideline_source,
            variant_result_id=payload.variant_result_id,
            created_at=now,
        )
        with self._lock:
            self._dosing_recommendations[rid] = rec
        logger.info("Created dosing recommendation %s: %s/%s for %s", rid, payload.drug_name, payload.gene_symbol, payload.subject_id)
        return rec

    def update_dosing_recommendation(
        self, rec_id: str, payload: DosingRecommendationUpdate,
    ) -> DosingRecommendation | None:
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._dosing_recommendations.get(rec_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            # Auto-set accepted_date when accepted is set
            if "accepted" in updates and updates["accepted"] is True and existing.accepted is not True:
                updates["accepted_date"] = now
            data.update(updates)
            updated = DosingRecommendation(**data)
            self._dosing_recommendations[rec_id] = updated
        return updated

    def delete_dosing_recommendation(self, rec_id: str) -> bool:
        with self._lock:
            if rec_id in self._dosing_recommendations:
                del self._dosing_recommendations[rec_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> PharmacogenomicsMetrics:
        """Compute aggregated pharmacogenomics metrics."""
        with self._lock:
            interactions = list(self._interactions.values())
            gps = list(self._genotype_phenotypes.values())
            orders = list(self._test_orders.values())
            variants = list(self._variant_results.values())
            recs = list(self._dosing_recommendations.values())

        if trial_id is not None:
            orders = [o for o in orders if o.trial_id == trial_id]
            trial_order_ids = {o.id for o in orders}
            variants = [v for v in variants if v.test_order_id in trial_order_ids]
            recs = [r for r in recs if r.trial_id == trial_id]

        # Interactions by evidence level
        interactions_by_evidence: dict[str, int] = {}
        for i in interactions:
            key = i.evidence_level.value
            interactions_by_evidence[key] = interactions_by_evidence.get(key, 0) + 1

        actionable_count = sum(1 for i in interactions if i.actionable)

        # Genotypes by metabolizer status
        genotypes_by_metabolizer: dict[str, int] = {}
        for gp in gps:
            key = gp.metabolizer_status.value
            genotypes_by_metabolizer[key] = genotypes_by_metabolizer.get(key, 0) + 1

        # Orders by status
        orders_by_status: dict[str, int] = {}
        for o in orders:
            key = o.status.value
            orders_by_status[key] = orders_by_status.get(key, 0) + 1

        # Average turnaround
        turnaround_orders = [o for o in orders if o.turnaround_days is not None]
        avg_turnaround = (
            round(sum(o.turnaround_days for o in turnaround_orders) / len(turnaround_orders), 1)
            if turnaround_orders
            else 0.0
        )

        # Variants by significance
        variants_by_significance: dict[str, int] = {}
        for v in variants:
            key = v.significance.value
            variants_by_significance[key] = variants_by_significance.get(key, 0) + 1

        # Recommendations by action
        recommendations_by_action: dict[str, int] = {}
        for r in recs:
            key = r.action.value
            recommendations_by_action[key] = recommendations_by_action.get(key, 0) + 1

        # Acceptance rate
        recs_with_decision = [r for r in recs if r.accepted is not None]
        accepted_count = sum(1 for r in recs_with_decision if r.accepted is True)
        acceptance_pct = (
            round(accepted_count / len(recs_with_decision) * 100.0, 1)
            if recs_with_decision
            else 0.0
        )

        return PharmacogenomicsMetrics(
            total_interactions=len(interactions),
            actionable_interactions=actionable_count,
            interactions_by_evidence=interactions_by_evidence,
            total_genotype_phenotypes=len(gps),
            genotypes_by_metabolizer=genotypes_by_metabolizer,
            total_test_orders=len(orders),
            orders_by_status=orders_by_status,
            avg_turnaround_days=avg_turnaround,
            total_variant_results=len(variants),
            variants_by_significance=variants_by_significance,
            total_recommendations=len(recs),
            recommendations_by_action=recommendations_by_action,
            recommendation_acceptance_pct=acceptance_pct,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: PharmacogenomicsService | None = None
_instance_lock = threading.Lock()


def get_pharmacogenomics_service() -> PharmacogenomicsService:
    """Return the singleton PharmacogenomicsService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = PharmacogenomicsService()
    return _instance


def reset_pharmacogenomics_service() -> PharmacogenomicsService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = PharmacogenomicsService()
    return _instance
