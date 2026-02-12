"""Health Economics & Outcomes Research (HEOR) Service.

Manages HEOR studies, cost-effectiveness analyses, budget impact models,
value dossiers, and payer evidence packages for Regeneron pipeline products.

Usage:
    from app.services.heor_service import get_heor_service, reset_heor_service

    svc = get_heor_service()
    studies = svc.list_studies()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.heor import (
    AnalysisType,
    BudgetImpactModel,
    BudgetImpactModelCreate,
    BudgetImpactModelUpdate,
    CostEffectivenessResult,
    CostEffectivenessResultCreate,
    CostEffectivenessResultUpdate,
    DossierStatus,
    EvidenceGrade,
    HEORMetrics,
    HEORStudy,
    HEORStudyCreate,
    HEORStudyUpdate,
    ModelType,
    PayerEvidence,
    PayerEvidenceCreate,
    PayerEvidenceUpdate,
    PayerType,
    StudyStatus,
    ValueDossier,
    ValueDossierCreate,
    ValueDossierUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class HEORService:
    """In-memory Health Economics & Outcomes Research engine."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._studies: dict[str, HEORStudy] = {}
        self._ce_results: dict[str, CostEffectivenessResult] = {}
        self._budget_models: dict[str, BudgetImpactModel] = {}
        self._dossiers: dict[str, ValueDossier] = {}
        self._payer_evidence: dict[str, PayerEvidence] = {}
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Seed data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Populate realistic HEOR demo data across Regeneron pipeline trials."""
        now = datetime.now(timezone.utc)

        # ---- HEOR Studies ----
        studies_data = [
            # EYLEA studies
            {
                "id": "heor-study-001",
                "trial_id": EYLEA_TRIAL,
                "title": "Cost-Effectiveness of EYLEA vs Ranibizumab in Wet AMD",
                "analysis_type": AnalysisType.COST_EFFECTIVENESS,
                "comparator": "Ranibizumab (Lucentis)",
                "perspective": "US Healthcare Payer",
                "time_horizon": "Lifetime",
                "discount_rate_pct": 3.0,
                "status": StudyStatus.COMPLETED,
                "principal_analyst": "Dr. Sarah Chen",
                "target_publication": "PharmacoEconomics",
                "start_date": now - timedelta(days=365),
                "completion_date": now - timedelta(days=30),
                "country": "US",
                "data_sources": ["MARINA trial", "ANCHOR trial", "VIEW 1&2"],
                "created_at": now - timedelta(days=400),
            },
            {
                "id": "heor-study-002",
                "trial_id": EYLEA_TRIAL,
                "title": "Cost-Utility of EYLEA vs Bevacizumab in DME",
                "analysis_type": AnalysisType.COST_UTILITY,
                "comparator": "Bevacizumab (Avastin)",
                "perspective": "UK NHS",
                "time_horizon": "10 years",
                "discount_rate_pct": 3.5,
                "status": StudyStatus.PUBLISHED,
                "principal_analyst": "Dr. James Wright",
                "target_publication": "Value in Health",
                "start_date": now - timedelta(days=500),
                "completion_date": now - timedelta(days=90),
                "country": "UK",
                "data_sources": ["DA VINCI trial", "VIVID/VISTA trials", "NHS HES data"],
                "created_at": now - timedelta(days=520),
            },
            {
                "id": "heor-study-003",
                "trial_id": EYLEA_TRIAL,
                "title": "Budget Impact of EYLEA HD for Retinal Conditions",
                "analysis_type": AnalysisType.BUDGET_IMPACT,
                "comparator": "EYLEA 2mg (standard dose)",
                "perspective": "US Commercial Payer",
                "time_horizon": "3 years",
                "discount_rate_pct": 0.0,
                "status": StudyStatus.ANALYSIS,
                "principal_analyst": "Dr. Lisa Park",
                "country": "US",
                "data_sources": ["PULSAR trial", "PHOTON trial", "Claims data 2023"],
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "heor-study-004",
                "trial_id": EYLEA_TRIAL,
                "title": "Systematic Review of Anti-VEGF Cost-Effectiveness in RVO",
                "analysis_type": AnalysisType.SYSTEMATIC_REVIEW,
                "comparator": "All anti-VEGF agents",
                "perspective": "Societal",
                "time_horizon": "5 years",
                "discount_rate_pct": 3.0,
                "status": StudyStatus.DATA_COLLECTION,
                "principal_analyst": "Dr. Emily Zhao",
                "country": "Global",
                "data_sources": ["PubMed", "Cochrane Library", "NICE evidence reviews"],
                "created_at": now - timedelta(days=120),
            },
            # DUPIXENT studies
            {
                "id": "heor-study-005",
                "trial_id": DUPIXENT_TRIAL,
                "title": "Cost-Utility of DUPIXENT vs JAK Inhibitors in Atopic Dermatitis",
                "analysis_type": AnalysisType.COST_UTILITY,
                "comparator": "Upadacitinib (Rinvoq)",
                "perspective": "US Healthcare Payer",
                "time_horizon": "Lifetime",
                "discount_rate_pct": 3.0,
                "status": StudyStatus.COMPLETED,
                "principal_analyst": "Dr. Michael Torres",
                "target_publication": "JACI: In Practice",
                "start_date": now - timedelta(days=300),
                "completion_date": now - timedelta(days=15),
                "country": "US",
                "data_sources": ["LIBERTY AD SOLO 1&2", "Heads Up trial", "MarketScan claims"],
                "created_at": now - timedelta(days=350),
            },
            {
                "id": "heor-study-006",
                "trial_id": DUPIXENT_TRIAL,
                "title": "Cost-Effectiveness of DUPIXENT vs Abrocitinib in Moderate-to-Severe AD",
                "analysis_type": AnalysisType.COST_EFFECTIVENESS,
                "comparator": "Abrocitinib (Cibinqo)",
                "perspective": "German Statutory Health Insurance",
                "time_horizon": "10 years",
                "discount_rate_pct": 3.0,
                "status": StudyStatus.REPORTING,
                "principal_analyst": "Dr. Anna Schmidt",
                "target_publication": "Journal of Dermatological Treatment",
                "start_date": now - timedelta(days=240),
                "country": "Germany",
                "data_sources": ["LIBERTY AD CHRONOS", "JADE COMPARE", "German SHI claims"],
                "created_at": now - timedelta(days=260),
            },
            {
                "id": "heor-study-007",
                "trial_id": DUPIXENT_TRIAL,
                "title": "Meta-Analysis of DUPIXENT Efficacy Across Type 2 Inflammatory Conditions",
                "analysis_type": AnalysisType.META_ANALYSIS,
                "comparator": "Placebo / Standard of Care",
                "perspective": "Clinical",
                "time_horizon": "52 weeks",
                "discount_rate_pct": 0.0,
                "status": StudyStatus.ANALYSIS,
                "principal_analyst": "Dr. Robert Kim",
                "country": "Global",
                "data_sources": ["LIBERTY Asthma trials", "SINUS trials", "EoE trials"],
                "created_at": now - timedelta(days=200),
            },
            # LIBTAYO studies
            {
                "id": "heor-study-008",
                "trial_id": LIBTAYO_TRIAL,
                "title": "Budget Impact of LIBTAYO for Advanced CSCC",
                "analysis_type": AnalysisType.BUDGET_IMPACT,
                "comparator": "Chemotherapy (cisplatin-based)",
                "perspective": "US Medicare",
                "time_horizon": "3 years",
                "discount_rate_pct": 0.0,
                "status": StudyStatus.COMPLETED,
                "principal_analyst": "Dr. Karen Patel",
                "target_publication": "Journal of Medical Economics",
                "start_date": now - timedelta(days=400),
                "completion_date": now - timedelta(days=60),
                "country": "US",
                "data_sources": ["EMPOWER-CSCC-1", "SEER-Medicare", "Flatiron data"],
                "created_at": now - timedelta(days=430),
            },
            {
                "id": "heor-study-009",
                "trial_id": LIBTAYO_TRIAL,
                "title": "Cost-Effectiveness of LIBTAYO vs Pembrolizumab in 1L NSCLC",
                "analysis_type": AnalysisType.COST_EFFECTIVENESS,
                "comparator": "Pembrolizumab (Keytruda)",
                "perspective": "US Healthcare Payer",
                "time_horizon": "Lifetime",
                "discount_rate_pct": 3.0,
                "status": StudyStatus.PROTOCOL_DEVELOPMENT,
                "principal_analyst": "Dr. David Nguyen",
                "country": "US",
                "data_sources": ["EMPOWER-Lung 1", "KEYNOTE-024", "KEYNOTE-042"],
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "heor-study-010",
                "trial_id": LIBTAYO_TRIAL,
                "title": "Comparative Effectiveness of LIBTAYO in Advanced BCC",
                "analysis_type": AnalysisType.COMPARATIVE_EFFECTIVENESS,
                "comparator": "Vismodegib (Erivedge)",
                "perspective": "US Healthcare Payer",
                "time_horizon": "5 years",
                "discount_rate_pct": 3.0,
                "status": StudyStatus.PLANNED,
                "principal_analyst": "Dr. Rachel Green",
                "country": "US",
                "data_sources": ["EMPOWER-BCC", "STEVIE trial"],
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "heor-study-011",
                "trial_id": DUPIXENT_TRIAL,
                "title": "Cost-Minimization of DUPIXENT vs Tralokinumab in AD",
                "analysis_type": AnalysisType.COST_MINIMIZATION,
                "comparator": "Tralokinumab (Adbry)",
                "perspective": "Canadian Public Payer",
                "time_horizon": "1 year",
                "discount_rate_pct": 1.5,
                "status": StudyStatus.DATA_COLLECTION,
                "principal_analyst": "Dr. Marc Beauchamp",
                "country": "Canada",
                "data_sources": ["LIBERTY AD SOLO", "ECZTRA trials", "IQVIA claims"],
                "created_at": now - timedelta(days=140),
            },
        ]

        for s in studies_data:
            self._studies[s["id"]] = HEORStudy(**s)

        # ---- Cost-Effectiveness Results ----
        ce_data = [
            {
                "id": "ce-result-001",
                "study_id": "heor-study-001",
                "model_type": ModelType.MARKOV,
                "icer": 42500.0,
                "icer_currency": "USD",
                "incremental_cost": 12750.0,
                "incremental_qaly": 0.30,
                "incremental_ly": 0.15,
                "wtp_threshold": 50000.0,
                "cost_effective": True,
                "nmb": 2250.0,
                "sensitivity_analysis_type": "Probabilistic (10,000 iterations)",
                "confidence_interval_low": 35000.0,
                "confidence_interval_high": 52000.0,
                "probability_cost_effective_pct": 68.5,
                "analysis_date": now - timedelta(days=45),
                "analyst": "Dr. Sarah Chen",
            },
            {
                "id": "ce-result-002",
                "study_id": "heor-study-001",
                "model_type": ModelType.DISCRETE_EVENT,
                "icer": 38900.0,
                "icer_currency": "USD",
                "incremental_cost": 11670.0,
                "incremental_qaly": 0.30,
                "wtp_threshold": 50000.0,
                "cost_effective": True,
                "nmb": 3330.0,
                "sensitivity_analysis_type": "One-way sensitivity analysis",
                "confidence_interval_low": 31000.0,
                "confidence_interval_high": 48000.0,
                "probability_cost_effective_pct": 74.2,
                "analysis_date": now - timedelta(days=40),
                "analyst": "Dr. Sarah Chen",
            },
            {
                "id": "ce-result-003",
                "study_id": "heor-study-002",
                "model_type": ModelType.MARKOV,
                "icer": 18500.0,
                "icer_currency": "GBP",
                "incremental_cost": 5550.0,
                "incremental_qaly": 0.30,
                "incremental_ly": 0.10,
                "wtp_threshold": 30000.0,
                "cost_effective": True,
                "nmb": 3450.0,
                "sensitivity_analysis_type": "Probabilistic (5,000 iterations)",
                "confidence_interval_low": 12000.0,
                "confidence_interval_high": 26000.0,
                "probability_cost_effective_pct": 82.1,
                "analysis_date": now - timedelta(days=100),
                "analyst": "Dr. James Wright",
            },
            {
                "id": "ce-result-004",
                "study_id": "heor-study-005",
                "model_type": ModelType.PARTITIONED_SURVIVAL,
                "icer": 67800.0,
                "icer_currency": "USD",
                "incremental_cost": 33900.0,
                "incremental_qaly": 0.50,
                "wtp_threshold": 100000.0,
                "cost_effective": True,
                "nmb": 16100.0,
                "sensitivity_analysis_type": "Probabilistic (10,000 iterations)",
                "confidence_interval_low": 52000.0,
                "confidence_interval_high": 85000.0,
                "probability_cost_effective_pct": 78.9,
                "analysis_date": now - timedelta(days=20),
                "analyst": "Dr. Michael Torres",
            },
            {
                "id": "ce-result-005",
                "study_id": "heor-study-005",
                "model_type": ModelType.DECISION_TREE,
                "icer": 71200.0,
                "icer_currency": "USD",
                "incremental_cost": 35600.0,
                "incremental_qaly": 0.50,
                "wtp_threshold": 100000.0,
                "cost_effective": True,
                "nmb": 14400.0,
                "sensitivity_analysis_type": "Tornado diagram",
                "confidence_interval_low": 58000.0,
                "confidence_interval_high": 89000.0,
                "probability_cost_effective_pct": 71.3,
                "analysis_date": now - timedelta(days=18),
                "analyst": "Dr. Michael Torres",
            },
            {
                "id": "ce-result-006",
                "study_id": "heor-study-006",
                "model_type": ModelType.MICROSIMULATION,
                "icer": 45600.0,
                "icer_currency": "EUR",
                "incremental_cost": 22800.0,
                "incremental_qaly": 0.50,
                "wtp_threshold": 50000.0,
                "cost_effective": True,
                "nmb": 2200.0,
                "sensitivity_analysis_type": "Scenario analysis",
                "confidence_interval_low": 38000.0,
                "confidence_interval_high": 55000.0,
                "probability_cost_effective_pct": 58.4,
                "analysis_date": now - timedelta(days=10),
                "analyst": "Dr. Anna Schmidt",
            },
            {
                "id": "ce-result-007",
                "study_id": "heor-study-009",
                "model_type": ModelType.PARTITIONED_SURVIVAL,
                "icer": None,
                "icer_currency": "USD",
                "incremental_cost": None,
                "incremental_qaly": None,
                "wtp_threshold": 150000.0,
                "cost_effective": None,
                "analysis_date": now - timedelta(days=5),
                "analyst": "Dr. David Nguyen",
            },
            {
                "id": "ce-result-008",
                "study_id": "heor-study-001",
                "model_type": ModelType.HYBRID,
                "icer": 40100.0,
                "icer_currency": "USD",
                "incremental_cost": 12030.0,
                "incremental_qaly": 0.30,
                "wtp_threshold": 50000.0,
                "cost_effective": True,
                "nmb": 2970.0,
                "sensitivity_analysis_type": "Structural uncertainty",
                "confidence_interval_low": 33000.0,
                "confidence_interval_high": 49000.0,
                "probability_cost_effective_pct": 72.0,
                "analysis_date": now - timedelta(days=35),
                "analyst": "Dr. Sarah Chen",
            },
            {
                "id": "ce-result-009",
                "study_id": "heor-study-006",
                "model_type": ModelType.MARKOV,
                "icer": 48200.0,
                "icer_currency": "EUR",
                "incremental_cost": 24100.0,
                "incremental_qaly": 0.50,
                "wtp_threshold": 50000.0,
                "cost_effective": True,
                "nmb": 900.0,
                "sensitivity_analysis_type": "Probabilistic (5,000 iterations)",
                "confidence_interval_low": 40000.0,
                "confidence_interval_high": 58000.0,
                "probability_cost_effective_pct": 53.7,
                "analysis_date": now - timedelta(days=8),
                "analyst": "Dr. Anna Schmidt",
            },
            {
                "id": "ce-result-010",
                "study_id": "heor-study-010",
                "model_type": ModelType.DECISION_TREE,
                "icer": 125000.0,
                "icer_currency": "USD",
                "incremental_cost": 62500.0,
                "incremental_qaly": 0.50,
                "wtp_threshold": 100000.0,
                "cost_effective": False,
                "nmb": -12500.0,
                "analysis_date": now - timedelta(days=2),
                "analyst": "Dr. Rachel Green",
            },
        ]

        for r in ce_data:
            self._ce_results[r["id"]] = CostEffectivenessResult(**r)

        # ---- Budget Impact Models ----
        budget_data = [
            {
                "id": "bim-001",
                "study_id": "heor-study-003",
                "target_population_size": 250000,
                "market_share_year1_pct": 15.0,
                "market_share_year2_pct": 25.0,
                "market_share_year3_pct": 35.0,
                "drug_cost_per_patient": 14200.0,
                "comparator_cost_per_patient": 11800.0,
                "total_budget_impact_year1": 90000000.0,
                "total_budget_impact_year2": 150000000.0,
                "total_budget_impact_year3": 210000000.0,
                "cumulative_budget_impact": 450000000.0,
                "pmpm_impact": 0.75,
                "assumptions": [
                    "10% annual market growth",
                    "Equal efficacy assumed",
                    "No rebates or discounts included",
                    "US commercial population base",
                ],
                "model_date": now - timedelta(days=60),
                "modeler": "Dr. Lisa Park",
            },
            {
                "id": "bim-002",
                "study_id": "heor-study-008",
                "target_population_size": 45000,
                "market_share_year1_pct": 30.0,
                "market_share_year2_pct": 45.0,
                "market_share_year3_pct": 55.0,
                "drug_cost_per_patient": 165000.0,
                "comparator_cost_per_patient": 28000.0,
                "total_budget_impact_year1": 1849500000.0,
                "total_budget_impact_year2": 2774250000.0,
                "total_budget_impact_year3": 3391750000.0,
                "cumulative_budget_impact": 8015500000.0,
                "pmpm_impact": 2.85,
                "assumptions": [
                    "Medicare fee-for-service population",
                    "CSCC incidence per SEER registry",
                    "Treatment until progression or unacceptable toxicity",
                    "Includes administration and monitoring costs",
                ],
                "model_date": now - timedelta(days=70),
                "modeler": "Dr. Karen Patel",
            },
            {
                "id": "bim-003",
                "study_id": "heor-study-003",
                "target_population_size": 180000,
                "market_share_year1_pct": 10.0,
                "market_share_year2_pct": 18.0,
                "market_share_year3_pct": 28.0,
                "drug_cost_per_patient": 16800.0,
                "comparator_cost_per_patient": 14200.0,
                "total_budget_impact_year1": 46800000.0,
                "total_budget_impact_year2": 84240000.0,
                "total_budget_impact_year3": 131040000.0,
                "cumulative_budget_impact": 262080000.0,
                "pmpm_impact": 0.55,
                "assumptions": [
                    "Managed care population subset",
                    "Includes DME and RVO indications",
                    "WAC pricing without rebates",
                ],
                "model_date": now - timedelta(days=50),
                "modeler": "Dr. Lisa Park",
            },
            {
                "id": "bim-004",
                "study_id": "heor-study-005",
                "target_population_size": 500000,
                "market_share_year1_pct": 20.0,
                "market_share_year2_pct": 30.0,
                "market_share_year3_pct": 38.0,
                "drug_cost_per_patient": 36000.0,
                "comparator_cost_per_patient": 32000.0,
                "total_budget_impact_year1": 400000000.0,
                "total_budget_impact_year2": 600000000.0,
                "total_budget_impact_year3": 760000000.0,
                "cumulative_budget_impact": 1760000000.0,
                "pmpm_impact": 1.20,
                "assumptions": [
                    "Moderate-to-severe AD population",
                    "Biologic-eligible patients only",
                    "Includes drug + admin costs",
                    "No step-therapy assumptions",
                ],
                "model_date": now - timedelta(days=25),
                "modeler": "Dr. Michael Torres",
            },
            {
                "id": "bim-005",
                "study_id": "heor-study-008",
                "target_population_size": 15000,
                "market_share_year1_pct": 25.0,
                "market_share_year2_pct": 40.0,
                "market_share_year3_pct": 50.0,
                "drug_cost_per_patient": 165000.0,
                "comparator_cost_per_patient": 45000.0,
                "total_budget_impact_year1": 450000000.0,
                "total_budget_impact_year2": 720000000.0,
                "total_budget_impact_year3": 900000000.0,
                "cumulative_budget_impact": 2070000000.0,
                "pmpm_impact": 1.95,
                "assumptions": [
                    "Commercial payer perspective",
                    "Locally advanced or metastatic CSCC",
                    "Weighted average comparator costs",
                ],
                "model_date": now - timedelta(days=65),
                "modeler": "Dr. Karen Patel",
            },
            {
                "id": "bim-006",
                "study_id": "heor-study-009",
                "target_population_size": 120000,
                "market_share_year1_pct": 5.0,
                "market_share_year2_pct": 12.0,
                "market_share_year3_pct": 20.0,
                "drug_cost_per_patient": 150000.0,
                "comparator_cost_per_patient": 155000.0,
                "total_budget_impact_year1": -30000000.0,
                "total_budget_impact_year2": -72000000.0,
                "total_budget_impact_year3": -120000000.0,
                "cumulative_budget_impact": -222000000.0,
                "pmpm_impact": -0.35,
                "assumptions": [
                    "1L NSCLC PD-L1 >= 50%",
                    "LIBTAYO priced below pembrolizumab",
                    "Includes supportive care costs",
                ],
                "model_date": now - timedelta(days=85),
                "modeler": "Dr. David Nguyen",
            },
            {
                "id": "bim-007",
                "study_id": "heor-study-011",
                "target_population_size": 320000,
                "market_share_year1_pct": 12.0,
                "market_share_year2_pct": 20.0,
                "market_share_year3_pct": 26.0,
                "drug_cost_per_patient": 36000.0,
                "comparator_cost_per_patient": 34500.0,
                "total_budget_impact_year1": 57600000.0,
                "total_budget_impact_year2": 96000000.0,
                "total_budget_impact_year3": 124800000.0,
                "cumulative_budget_impact": 278400000.0,
                "pmpm_impact": 0.42,
                "assumptions": [
                    "Canadian public formulary listing",
                    "AD patient population from CIHI data",
                    "CAD to USD converted at 0.75",
                ],
                "model_date": now - timedelta(days=130),
                "modeler": "Dr. Marc Beauchamp",
            },
            {
                "id": "bim-008",
                "study_id": "heor-study-010",
                "target_population_size": 8000,
                "market_share_year1_pct": 8.0,
                "market_share_year2_pct": 15.0,
                "market_share_year3_pct": 22.0,
                "drug_cost_per_patient": 165000.0,
                "comparator_cost_per_patient": 90000.0,
                "total_budget_impact_year1": 48000000.0,
                "total_budget_impact_year2": 90000000.0,
                "total_budget_impact_year3": 132000000.0,
                "cumulative_budget_impact": 270000000.0,
                "pmpm_impact": 0.30,
                "assumptions": [
                    "Advanced BCC post-hedgehog inhibitor",
                    "Small eligible population",
                    "Includes BCC-specific monitoring costs",
                ],
                "model_date": now - timedelta(days=20),
                "modeler": "Dr. Rachel Green",
            },
            {
                "id": "bim-009",
                "study_id": "heor-study-001",
                "target_population_size": 400000,
                "market_share_year1_pct": 40.0,
                "market_share_year2_pct": 42.0,
                "market_share_year3_pct": 44.0,
                "drug_cost_per_patient": 11800.0,
                "comparator_cost_per_patient": 10500.0,
                "total_budget_impact_year1": 208000000.0,
                "total_budget_impact_year2": 218400000.0,
                "total_budget_impact_year3": 228800000.0,
                "cumulative_budget_impact": 655200000.0,
                "pmpm_impact": 0.68,
                "assumptions": [
                    "Established market leader position",
                    "Wet AMD + DME combined",
                    "Net price after all rebates",
                ],
                "model_date": now - timedelta(days=42),
                "modeler": "Dr. Sarah Chen",
            },
            {
                "id": "bim-010",
                "study_id": "heor-study-006",
                "target_population_size": 220000,
                "market_share_year1_pct": 18.0,
                "market_share_year2_pct": 24.0,
                "market_share_year3_pct": 30.0,
                "drug_cost_per_patient": 28000.0,
                "comparator_cost_per_patient": 26000.0,
                "total_budget_impact_year1": 79200000.0,
                "total_budget_impact_year2": 105600000.0,
                "total_budget_impact_year3": 132000000.0,
                "cumulative_budget_impact": 316800000.0,
                "pmpm_impact": 0.48,
                "assumptions": [
                    "German SHI perspective",
                    "IQWiG added benefit assessment assumed",
                    "Includes monitoring and AE management",
                ],
                "model_date": now - timedelta(days=6),
                "modeler": "Dr. Anna Schmidt",
            },
        ]

        for b in budget_data:
            self._budget_models[b["id"]] = BudgetImpactModel(**b)

        # ---- Value Dossiers ----
        dossier_data = [
            {
                "id": "dossier-001",
                "trial_id": EYLEA_TRIAL,
                "product_name": "EYLEA (aflibercept)",
                "indication": "Wet Age-Related Macular Degeneration",
                "target_payer_type": PayerType.COMMERCIAL,
                "target_market": "US",
                "status": DossierStatus.APPROVED,
                "evidence_grade": EvidenceGrade.HIGH,
                "clinical_value_summary": "EYLEA demonstrates superior visual acuity gains vs ranibizumab in pivotal VIEW trials with extended dosing flexibility, reducing treatment burden while maintaining efficacy outcomes.",
                "economic_value_summary": "At an ICER of $42,500/QALY (well below $50K WTP threshold), EYLEA represents a cost-effective treatment option with favorable budget predictability due to fixed dosing intervals.",
                "unmet_need_description": "Patients with wet AMD face progressive irreversible vision loss. EYLEA addresses the need for effective anti-VEGF therapy with less frequent dosing compared to monthly ranibizumab.",
                "key_messages": [
                    "Cost-effective vs ranibizumab (ICER $42,500/QALY)",
                    "Extended dosing reduces treatment burden",
                    "Strong real-world evidence base",
                    "Favorable safety profile over 10+ years",
                ],
                "supporting_studies": ["heor-study-001", "heor-study-002"],
                "author": "Dr. Sarah Chen",
                "reviewer": "Dr. James Wright",
                "submission_date": now - timedelta(days=20),
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "dossier-002",
                "trial_id": DUPIXENT_TRIAL,
                "product_name": "DUPIXENT (dupilumab)",
                "indication": "Moderate-to-Severe Atopic Dermatitis",
                "target_payer_type": PayerType.COMMERCIAL,
                "target_market": "US",
                "status": DossierStatus.SUBMITTED,
                "evidence_grade": EvidenceGrade.HIGH,
                "clinical_value_summary": "DUPIXENT is the first-in-class IL-4/IL-13 inhibitor with proven efficacy in moderate-to-severe AD, demonstrated in LIBERTY AD program across diverse patient populations with consistent safety profile.",
                "economic_value_summary": "At $67,800/QALY against JAK inhibitors, DUPIXENT provides good value when considering its superior long-term safety profile compared to JAK inhibitor class-wide black box warnings.",
                "unmet_need_description": "Patients with moderate-to-severe AD inadequately controlled on topical therapies need targeted systemic options with favorable safety allowing long-term use.",
                "key_messages": [
                    "First targeted biologic for AD with proven efficacy",
                    "No black-box warnings unlike JAK inhibitors",
                    "Favorable cost-utility vs JAK class ($67,800/QALY)",
                    "Broad indication coverage across Type 2 conditions",
                ],
                "supporting_studies": ["heor-study-005", "heor-study-006", "heor-study-007"],
                "author": "Dr. Michael Torres",
                "reviewer": "Dr. Anna Schmidt",
                "submission_date": now - timedelta(days=5),
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "dossier-003",
                "trial_id": LIBTAYO_TRIAL,
                "product_name": "LIBTAYO (cemiplimab)",
                "indication": "Advanced Cutaneous Squamous Cell Carcinoma",
                "target_payer_type": PayerType.MEDICARE,
                "target_market": "US",
                "status": DossierStatus.APPROVED,
                "evidence_grade": EvidenceGrade.HIGH,
                "clinical_value_summary": "LIBTAYO is the first FDA-approved treatment for advanced CSCC with durable response rates exceeding 40% in the EMPOWER-CSCC program, filling a critical treatment gap.",
                "economic_value_summary": "Budget impact analysis shows manageable PMPM impact of $2.85 for Medicare, offset by reduced need for costly surgical interventions and hospitalizations.",
                "unmet_need_description": "Advanced CSCC had no approved systemic therapy prior to LIBTAYO. Patients failing surgery/radiation had limited options with poor outcomes on chemotherapy.",
                "key_messages": [
                    "First-and-only approved immunotherapy for CSCC",
                    "Durable responses >40% in heavily pretreated patients",
                    "Manageable budget impact ($2.85 PMPM Medicare)",
                    "Reduces downstream surgical and hospitalization costs",
                ],
                "supporting_studies": ["heor-study-008"],
                "author": "Dr. Karen Patel",
                "reviewer": "Dr. David Nguyen",
                "submission_date": now - timedelta(days=55),
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "dossier-004",
                "trial_id": EYLEA_TRIAL,
                "product_name": "EYLEA HD (aflibercept 8mg)",
                "indication": "Diabetic Macular Edema",
                "target_payer_type": PayerType.NATIONAL_HTA,
                "target_market": "UK",
                "status": DossierStatus.INTERNAL_REVIEW,
                "evidence_grade": EvidenceGrade.MODERATE,
                "clinical_value_summary": "EYLEA HD 8mg demonstrates non-inferior visual acuity gains with significantly extended dosing intervals (up to 16 weeks) compared to EYLEA 2mg every 8 weeks in PHOTON trial.",
                "economic_value_summary": "Extended dosing intervals projected to reduce per-patient treatment costs by 30-40% through fewer injections and clinic visits over a 2-year treatment horizon.",
                "unmet_need_description": "DME patients require frequent intravitreal injections creating significant treatment burden. EYLEA HD addresses this with longer dosing intervals maintaining efficacy.",
                "key_messages": [
                    "Up to 16-week dosing intervals",
                    "30-40% fewer injections vs standard EYLEA",
                    "Non-inferior efficacy in PHOTON trial",
                    "Reduced patient and healthcare system burden",
                ],
                "supporting_studies": ["heor-study-003"],
                "author": "Dr. James Wright",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "dossier-005",
                "trial_id": DUPIXENT_TRIAL,
                "product_name": "DUPIXENT (dupilumab)",
                "indication": "Eosinophilic Esophagitis",
                "target_payer_type": PayerType.REGIONAL_HTA,
                "target_market": "France",
                "status": DossierStatus.DRAFT,
                "evidence_grade": EvidenceGrade.MODERATE,
                "clinical_value_summary": "DUPIXENT demonstrated significant histologic improvement in EoE patients in Phase 3 trials, offering the first approved targeted therapy for this chronic condition.",
                "economic_value_summary": "Cost-effectiveness analysis pending. Preliminary modeling suggests favorable ICER vs chronic PPI therapy when accounting for reduced endoscopic procedures.",
                "unmet_need_description": "EoE patients have limited treatment options beyond empiric dietary elimination and off-label PPI use. DUPIXENT provides a targeted mechanism-based approach.",
                "key_messages": [
                    "First targeted biologic approved for EoE",
                    "Significant histologic remission rates",
                    "Reduces need for repeat endoscopies",
                    "Addresses growing EoE prevalence",
                ],
                "supporting_studies": ["heor-study-007"],
                "author": "Dr. Robert Kim",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "dossier-006",
                "trial_id": LIBTAYO_TRIAL,
                "product_name": "LIBTAYO (cemiplimab)",
                "indication": "First-Line Non-Small Cell Lung Cancer (PD-L1 >=50%)",
                "target_payer_type": PayerType.GOVERNMENT,
                "target_market": "Australia",
                "status": DossierStatus.DRAFT,
                "evidence_grade": EvidenceGrade.MODERATE,
                "clinical_value_summary": "EMPOWER-Lung 1 demonstrated significant OS improvement with LIBTAYO monotherapy vs chemotherapy in PD-L1-high NSCLC, with median OS not reached vs 14.2 months.",
                "economic_value_summary": "Budget impact modeling indicates potential cost savings vs pembrolizumab due to competitive pricing, with estimated $0.35 PMPM savings.",
                "unmet_need_description": "While PD-1 inhibitors exist for this setting, additional competitive options drive price competition and access, benefiting payers and patients.",
                "key_messages": [
                    "Significant OS benefit vs chemotherapy",
                    "Competitive pricing vs pembrolizumab",
                    "Budget-neutral or cost-saving for payers",
                    "Expands immunotherapy access in NSCLC",
                ],
                "supporting_studies": ["heor-study-009", "heor-study-010"],
                "author": "Dr. David Nguyen",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "dossier-007",
                "trial_id": DUPIXENT_TRIAL,
                "product_name": "DUPIXENT (dupilumab)",
                "indication": "Chronic Rhinosinusitis with Nasal Polyps",
                "target_payer_type": PayerType.PRIVATE_PAYER,
                "target_market": "US",
                "status": DossierStatus.REVISION_REQUESTED,
                "evidence_grade": EvidenceGrade.HIGH,
                "clinical_value_summary": "SINUS-24 and SINUS-52 trials demonstrated significant improvement in nasal polyp score, nasal congestion, and CT opacification with DUPIXENT vs placebo in CRSwNP.",
                "economic_value_summary": "Reduces need for repeat sinus surgeries (avg $15K-25K per surgery), positioning DUPIXENT as cost-effective when surgical avoidance is factored into long-term economic models.",
                "unmet_need_description": "CRSwNP patients often undergo multiple sinus surgeries with recurrence. DUPIXENT provides a non-surgical option targeting the underlying Type 2 inflammation.",
                "key_messages": [
                    "Significant reduction in nasal polyp burden",
                    "Reduces need for repeat sinus surgery",
                    "Cost-effective when accounting for surgical avoidance",
                    "Improved quality of life across SINUS program",
                ],
                "supporting_studies": ["heor-study-007"],
                "author": "Dr. Robert Kim",
                "reviewer": "Payer medical director",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "dossier-008",
                "trial_id": EYLEA_TRIAL,
                "product_name": "EYLEA (aflibercept)",
                "indication": "Retinal Vein Occlusion",
                "target_payer_type": PayerType.NATIONAL_HTA,
                "target_market": "Canada",
                "status": DossierStatus.ACCEPTED,
                "evidence_grade": EvidenceGrade.HIGH,
                "clinical_value_summary": "EYLEA showed rapid visual acuity gains in RVO patients in COPERNICUS and GALILEO trials with consistent outcomes across BRVO and CRVO subtypes.",
                "economic_value_summary": "Favorable cost per QALY gained ($25,400 CAD) well below CADTH $50K WTP threshold. Real-world evidence confirms trial-consistent outcomes.",
                "unmet_need_description": "RVO causes sudden vision loss with limited treatment options prior to anti-VEGF era. EYLEA provides effective treatment with predictable dosing schedule.",
                "key_messages": [
                    "Rapid visual acuity improvement in RVO",
                    "Consistent outcomes across BRVO and CRVO",
                    "Below CADTH WTP threshold ($25,400/QALY CAD)",
                    "Strong real-world effectiveness data",
                ],
                "supporting_studies": ["heor-study-004"],
                "author": "Dr. Emily Zhao",
                "reviewer": "CADTH reviewer panel",
                "submission_date": now - timedelta(days=180),
                "created_at": now - timedelta(days=250),
            },
            {
                "id": "dossier-009",
                "trial_id": LIBTAYO_TRIAL,
                "product_name": "LIBTAYO (cemiplimab)",
                "indication": "Advanced Basal Cell Carcinoma",
                "target_payer_type": PayerType.COMMERCIAL,
                "target_market": "US",
                "status": DossierStatus.INTERNAL_REVIEW,
                "evidence_grade": EvidenceGrade.MODERATE,
                "clinical_value_summary": "LIBTAYO demonstrated meaningful response rates in locally advanced and metastatic BCC patients who progressed on or were intolerant to hedgehog pathway inhibitors.",
                "economic_value_summary": "Preliminary cost-effectiveness modeling suggests ICER above $100K/QALY threshold but may be acceptable given rare disease context and lack of alternatives.",
                "unmet_need_description": "Post-hedgehog inhibitor BCC patients have no approved systemic options. LIBTAYO fills a critical gap in the treatment algorithm.",
                "key_messages": [
                    "Addresses critical post-HHI treatment gap",
                    "Meaningful response in refractory BCC",
                    "Orphan-like disease economics apply",
                    "Reduces palliative care burden",
                ],
                "supporting_studies": ["heor-study-010"],
                "author": "Dr. Rachel Green",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "dossier-010",
                "trial_id": DUPIXENT_TRIAL,
                "product_name": "DUPIXENT (dupilumab)",
                "indication": "Moderate-to-Severe Atopic Dermatitis",
                "target_payer_type": PayerType.NATIONAL_HTA,
                "target_market": "Germany",
                "status": DossierStatus.SUBMITTED,
                "evidence_grade": EvidenceGrade.HIGH,
                "clinical_value_summary": "LIBERTY AD program demonstrates consistent efficacy of DUPIXENT across global populations. IQWiG assessment supports considerable added benefit over standard of care.",
                "economic_value_summary": "Cost-utility analysis by IQVIA shows DUPIXENT ICER of EUR 45,600/QALY, within G-BA accepted range for added-benefit biologics.",
                "unmet_need_description": "German AD patients with moderate-to-severe disease need effective systemic options with favorable long-term safety for chronic use.",
                "key_messages": [
                    "IQWiG: considerable added benefit designation",
                    "Within G-BA accepted ICER range (EUR 45,600/QALY)",
                    "First-line biologic positioning recommended",
                    "Favorable safety vs JAK inhibitors for long-term use",
                ],
                "supporting_studies": ["heor-study-006"],
                "author": "Dr. Anna Schmidt",
                "reviewer": "G-BA reviewers",
                "submission_date": now - timedelta(days=3),
                "created_at": now - timedelta(days=40),
            },
        ]

        for d in dossier_data:
            self._dossiers[d["id"]] = ValueDossier(**d)

        # ---- Payer Evidence ----
        payer_data = [
            {
                "id": "pe-001",
                "dossier_id": "dossier-001",
                "payer_name": "Aetna",
                "payer_type": PayerType.COMMERCIAL,
                "country": "US",
                "submission_date": now - timedelta(days=18),
                "response_date": now - timedelta(days=5),
                "outcome": "Favorable",
                "coverage_decision": "Preferred Tier 2 specialty",
                "restrictions": ["Prior authorization required", "Step therapy: trial of bevacizumab first"],
                "feedback_summary": "Strong clinical evidence package. Payer requests real-world utilization data at 6-month review.",
                "next_review_date": now + timedelta(days=165),
                "contact_person": "Dr. Jennifer Walsh",
            },
            {
                "id": "pe-002",
                "dossier_id": "dossier-001",
                "payer_name": "UnitedHealthcare",
                "payer_type": PayerType.COMMERCIAL,
                "country": "US",
                "submission_date": now - timedelta(days=15),
                "outcome": "Under Review",
                "contact_person": "Dr. Michael Stevens",
            },
            {
                "id": "pe-003",
                "dossier_id": "dossier-002",
                "payer_name": "Express Scripts",
                "payer_type": PayerType.COMMERCIAL,
                "country": "US",
                "submission_date": now - timedelta(days=4),
                "outcome": "Under Review",
                "contact_person": "Dr. Amanda Brown",
            },
            {
                "id": "pe-004",
                "dossier_id": "dossier-003",
                "payer_name": "CMS Medicare Part B",
                "payer_type": PayerType.MEDICARE,
                "country": "US",
                "submission_date": now - timedelta(days=50),
                "response_date": now - timedelta(days=20),
                "outcome": "Approved",
                "coverage_decision": "Medicare Part B J-code coverage",
                "restrictions": ["Diagnosis of advanced/metastatic CSCC", "Not a candidate for surgery/radiation"],
                "feedback_summary": "Meets unmet medical need criteria. National coverage decision issued.",
                "next_review_date": now + timedelta(days=330),
                "contact_person": "CMS Coverage Analysis Group",
            },
            {
                "id": "pe-005",
                "dossier_id": "dossier-003",
                "payer_name": "Medicaid (California)",
                "payer_type": PayerType.MEDICAID,
                "country": "US",
                "submission_date": now - timedelta(days=45),
                "response_date": now - timedelta(days=12),
                "outcome": "Conditional Approval",
                "coverage_decision": "Formulary coverage with prior authorization",
                "restrictions": ["Oncologist prescription required", "Prior auth for first 6 months"],
                "feedback_summary": "Approved following CMS national coverage. State supplemental rebate negotiated.",
                "contact_person": "CA Dept of Health Care Services",
            },
            {
                "id": "pe-006",
                "dossier_id": "dossier-004",
                "payer_name": "NICE",
                "payer_type": PayerType.NATIONAL_HTA,
                "country": "UK",
                "submission_date": None,
                "outcome": "Pre-Submission",
                "contact_person": "NICE Appraisal Committee",
            },
            {
                "id": "pe-007",
                "dossier_id": "dossier-008",
                "payer_name": "CADTH",
                "payer_type": PayerType.NATIONAL_HTA,
                "country": "Canada",
                "submission_date": now - timedelta(days=175),
                "response_date": now - timedelta(days=90),
                "outcome": "Recommended with Conditions",
                "coverage_decision": "Listed on provincial formularies pending price negotiation",
                "restrictions": ["Price reduction required per pCPA negotiation", "Specialists only"],
                "feedback_summary": "CADTH CDR recommended listing with clinical criteria aligned to trial population. pCPA negotiation ongoing.",
                "next_review_date": now + timedelta(days=90),
                "contact_person": "CADTH Review Committee",
            },
            {
                "id": "pe-008",
                "dossier_id": "dossier-010",
                "payer_name": "G-BA (Federal Joint Committee)",
                "payer_type": PayerType.NATIONAL_HTA,
                "country": "Germany",
                "submission_date": now - timedelta(days=2),
                "outcome": "Submitted",
                "contact_person": "G-BA Assessment Division",
            },
            {
                "id": "pe-009",
                "dossier_id": "dossier-007",
                "payer_name": "Cigna",
                "payer_type": PayerType.PRIVATE_PAYER,
                "country": "US",
                "submission_date": now - timedelta(days=70),
                "response_date": now - timedelta(days=30),
                "outcome": "Revision Requested",
                "coverage_decision": None,
                "restrictions": [],
                "feedback_summary": "Payer requests additional data on surgical cost offset and head-to-head data vs endoscopic sinus surgery. Resubmit within 60 days.",
                "next_review_date": now + timedelta(days=30),
                "contact_person": "Dr. Thomas Lee",
            },
            {
                "id": "pe-010",
                "dossier_id": "dossier-006",
                "payer_name": "PBAC (Australia)",
                "payer_type": PayerType.GOVERNMENT,
                "country": "Australia",
                "submission_date": None,
                "outcome": "Pre-Submission",
                "contact_person": "PBAC Secretariat",
            },
            {
                "id": "pe-011",
                "dossier_id": "dossier-002",
                "payer_name": "CVS Caremark",
                "payer_type": PayerType.COMMERCIAL,
                "country": "US",
                "submission_date": now - timedelta(days=3),
                "outcome": "Under Review",
                "contact_person": "CVS Specialty P&T Committee",
            },
            {
                "id": "pe-012",
                "dossier_id": "dossier-005",
                "payer_name": "HAS (Haute Autorite de Sante)",
                "payer_type": PayerType.REGIONAL_HTA,
                "country": "France",
                "submission_date": None,
                "outcome": "Pre-Submission",
                "contact_person": "HAS Transparency Committee",
            },
        ]

        for p in payer_data:
            self._payer_evidence[p["id"]] = PayerEvidence(**p)

        logger.info(
            "HEOR service seeded: %d studies, %d CE results, %d budget models, "
            "%d dossiers, %d payer evidence records",
            len(self._studies),
            len(self._ce_results),
            len(self._budget_models),
            len(self._dossiers),
            len(self._payer_evidence),
        )

    # ------------------------------------------------------------------
    # Studies CRUD
    # ------------------------------------------------------------------

    def list_studies(
        self,
        *,
        trial_id: str | None = None,
        analysis_type: AnalysisType | None = None,
        status: StudyStatus | None = None,
        country: str | None = None,
    ) -> list[HEORStudy]:
        with self._lock:
            items = list(self._studies.values())
        if trial_id:
            items = [s for s in items if s.trial_id == trial_id]
        if analysis_type:
            items = [s for s in items if s.analysis_type == analysis_type]
        if status:
            items = [s for s in items if s.status == status]
        if country:
            items = [s for s in items if s.country.lower() == country.lower()]
        return items

    def get_study(self, study_id: str) -> HEORStudy | None:
        with self._lock:
            return self._studies.get(study_id)

    def create_study(self, data: HEORStudyCreate) -> HEORStudy:
        now = datetime.now(timezone.utc)
        study = HEORStudy(
            id=str(uuid4()),
            trial_id=data.trial_id,
            title=data.title,
            analysis_type=data.analysis_type,
            comparator=data.comparator,
            perspective=data.perspective,
            time_horizon=data.time_horizon,
            discount_rate_pct=data.discount_rate_pct,
            status=StudyStatus.PLANNED,
            principal_analyst=data.principal_analyst,
            country=data.country,
            data_sources=data.data_sources,
            created_at=now,
        )
        with self._lock:
            self._studies[study.id] = study
        return study

    def update_study(self, study_id: str, data: HEORStudyUpdate) -> HEORStudy | None:
        with self._lock:
            study = self._studies.get(study_id)
            if not study:
                return None
            updates = data.model_dump(exclude_unset=True)
            updated = study.model_copy(update=updates)
            self._studies[study_id] = updated
            return updated

    def delete_study(self, study_id: str) -> bool:
        with self._lock:
            return self._studies.pop(study_id, None) is not None

    # ------------------------------------------------------------------
    # Cost-Effectiveness Results CRUD
    # ------------------------------------------------------------------

    def list_ce_results(
        self,
        *,
        study_id: str | None = None,
        model_type: ModelType | None = None,
    ) -> list[CostEffectivenessResult]:
        with self._lock:
            items = list(self._ce_results.values())
        if study_id:
            items = [r for r in items if r.study_id == study_id]
        if model_type:
            items = [r for r in items if r.model_type == model_type]
        return items

    def get_ce_result(self, result_id: str) -> CostEffectivenessResult | None:
        with self._lock:
            return self._ce_results.get(result_id)

    def create_ce_result(self, data: CostEffectivenessResultCreate) -> CostEffectivenessResult:
        now = datetime.now(timezone.utc)
        # Auto-compute cost_effective when icer and wtp_threshold both set
        cost_effective: bool | None = None
        if data.icer is not None and data.wtp_threshold is not None:
            cost_effective = data.icer <= data.wtp_threshold
        result = CostEffectivenessResult(
            id=str(uuid4()),
            study_id=data.study_id,
            model_type=data.model_type,
            icer=data.icer,
            incremental_cost=data.incremental_cost,
            incremental_qaly=data.incremental_qaly,
            incremental_ly=data.incremental_ly,
            wtp_threshold=data.wtp_threshold,
            cost_effective=cost_effective,
            analysis_date=now,
            analyst=data.analyst,
        )
        with self._lock:
            self._ce_results[result.id] = result
        return result

    def update_ce_result(self, result_id: str, data: CostEffectivenessResultUpdate) -> CostEffectivenessResult | None:
        with self._lock:
            result = self._ce_results.get(result_id)
            if not result:
                return None
            updates = data.model_dump(exclude_unset=True)
            updated = result.model_copy(update=updates)
            # Re-compute cost_effective if icer or wtp_threshold changed
            icer = updated.icer
            wtp = updated.wtp_threshold
            if icer is not None and wtp is not None:
                updated = updated.model_copy(update={"cost_effective": icer <= wtp})
            self._ce_results[result_id] = updated
            return updated

    def delete_ce_result(self, result_id: str) -> bool:
        with self._lock:
            return self._ce_results.pop(result_id, None) is not None

    # ------------------------------------------------------------------
    # Budget Impact Models CRUD
    # ------------------------------------------------------------------

    def list_budget_models(
        self,
        *,
        study_id: str | None = None,
    ) -> list[BudgetImpactModel]:
        with self._lock:
            items = list(self._budget_models.values())
        if study_id:
            items = [b for b in items if b.study_id == study_id]
        return items

    def get_budget_model(self, model_id: str) -> BudgetImpactModel | None:
        with self._lock:
            return self._budget_models.get(model_id)

    def create_budget_model(self, data: BudgetImpactModelCreate) -> BudgetImpactModel:
        now = datetime.now(timezone.utc)
        model = BudgetImpactModel(
            id=str(uuid4()),
            study_id=data.study_id,
            target_population_size=data.target_population_size,
            market_share_year1_pct=data.market_share_year1_pct,
            market_share_year2_pct=data.market_share_year2_pct,
            market_share_year3_pct=data.market_share_year3_pct,
            drug_cost_per_patient=data.drug_cost_per_patient,
            comparator_cost_per_patient=data.comparator_cost_per_patient,
            assumptions=data.assumptions,
            model_date=now,
            modeler=data.modeler,
        )
        with self._lock:
            self._budget_models[model.id] = model
        return model

    def update_budget_model(self, model_id: str, data: BudgetImpactModelUpdate) -> BudgetImpactModel | None:
        with self._lock:
            model = self._budget_models.get(model_id)
            if not model:
                return None
            updates = data.model_dump(exclude_unset=True)
            updated = model.model_copy(update=updates)
            self._budget_models[model_id] = updated
            return updated

    def delete_budget_model(self, model_id: str) -> bool:
        with self._lock:
            return self._budget_models.pop(model_id, None) is not None

    # ------------------------------------------------------------------
    # Value Dossiers CRUD
    # ------------------------------------------------------------------

    def list_dossiers(
        self,
        *,
        trial_id: str | None = None,
        status: DossierStatus | None = None,
        target_market: str | None = None,
        target_payer_type: PayerType | None = None,
        evidence_grade: EvidenceGrade | None = None,
    ) -> list[ValueDossier]:
        with self._lock:
            items = list(self._dossiers.values())
        if trial_id:
            items = [d for d in items if d.trial_id == trial_id]
        if status:
            items = [d for d in items if d.status == status]
        if target_market:
            items = [d for d in items if d.target_market.lower() == target_market.lower()]
        if target_payer_type:
            items = [d for d in items if d.target_payer_type == target_payer_type]
        if evidence_grade:
            items = [d for d in items if d.evidence_grade == evidence_grade]
        return items

    def get_dossier(self, dossier_id: str) -> ValueDossier | None:
        with self._lock:
            return self._dossiers.get(dossier_id)

    def create_dossier(self, data: ValueDossierCreate) -> ValueDossier:
        now = datetime.now(timezone.utc)
        dossier = ValueDossier(
            id=str(uuid4()),
            trial_id=data.trial_id,
            product_name=data.product_name,
            indication=data.indication,
            target_payer_type=data.target_payer_type,
            target_market=data.target_market,
            status=DossierStatus.DRAFT,
            evidence_grade=EvidenceGrade.MODERATE,
            clinical_value_summary=data.clinical_value_summary,
            economic_value_summary=data.economic_value_summary,
            unmet_need_description=data.unmet_need_description,
            key_messages=data.key_messages,
            author=data.author,
            created_at=now,
        )
        with self._lock:
            self._dossiers[dossier.id] = dossier
        return dossier

    def update_dossier(self, dossier_id: str, data: ValueDossierUpdate) -> ValueDossier | None:
        with self._lock:
            dossier = self._dossiers.get(dossier_id)
            if not dossier:
                return None
            updates = data.model_dump(exclude_unset=True)
            updated = dossier.model_copy(update=updates)
            self._dossiers[dossier_id] = updated
            return updated

    def delete_dossier(self, dossier_id: str) -> bool:
        with self._lock:
            return self._dossiers.pop(dossier_id, None) is not None

    # ------------------------------------------------------------------
    # Payer Evidence CRUD
    # ------------------------------------------------------------------

    def list_payer_evidence(
        self,
        *,
        dossier_id: str | None = None,
        payer_type: PayerType | None = None,
        country: str | None = None,
    ) -> list[PayerEvidence]:
        with self._lock:
            items = list(self._payer_evidence.values())
        if dossier_id:
            items = [p for p in items if p.dossier_id == dossier_id]
        if payer_type:
            items = [p for p in items if p.payer_type == payer_type]
        if country:
            items = [p for p in items if p.country.lower() == country.lower()]
        return items

    def get_payer_evidence(self, evidence_id: str) -> PayerEvidence | None:
        with self._lock:
            return self._payer_evidence.get(evidence_id)

    def create_payer_evidence(self, data: PayerEvidenceCreate) -> PayerEvidence:
        evidence = PayerEvidence(
            id=str(uuid4()),
            dossier_id=data.dossier_id,
            payer_name=data.payer_name,
            payer_type=data.payer_type,
            country=data.country,
            contact_person=data.contact_person,
        )
        with self._lock:
            self._payer_evidence[evidence.id] = evidence
        return evidence

    def update_payer_evidence(self, evidence_id: str, data: PayerEvidenceUpdate) -> PayerEvidence | None:
        with self._lock:
            evidence = self._payer_evidence.get(evidence_id)
            if not evidence:
                return None
            updates = data.model_dump(exclude_unset=True)
            updated = evidence.model_copy(update=updates)
            self._payer_evidence[evidence_id] = updated
            return updated

    def delete_payer_evidence(self, evidence_id: str) -> bool:
        with self._lock:
            return self._payer_evidence.pop(evidence_id, None) is not None

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> HEORMetrics:
        with self._lock:
            studies = list(self._studies.values())
            ce_results = list(self._ce_results.values())
            budget_models = list(self._budget_models.values())
            dossiers = list(self._dossiers.values())
            payer_evidence = list(self._payer_evidence.values())

        studies_by_type: dict[str, int] = {}
        for s in studies:
            key = s.analysis_type.value
            studies_by_type[key] = studies_by_type.get(key, 0) + 1

        studies_by_status: dict[str, int] = {}
        for s in studies:
            key = s.status.value
            studies_by_status[key] = studies_by_status.get(key, 0) + 1

        results_by_model: dict[str, int] = {}
        for r in ce_results:
            key = r.model_type.value
            results_by_model[key] = results_by_model.get(key, 0) + 1

        cost_effective_count = sum(1 for r in ce_results if r.cost_effective is True)

        dossiers_by_status: dict[str, int] = {}
        for d in dossiers:
            key = d.status.value
            dossiers_by_status[key] = dossiers_by_status.get(key, 0) + 1

        payer_by_type: dict[str, int] = {}
        for p in payer_evidence:
            key = p.payer_type.value
            payer_by_type[key] = payer_by_type.get(key, 0) + 1

        # avg_icer from results that have icer values
        icer_values = [r.icer for r in ce_results if r.icer is not None]
        avg_icer = sum(icer_values) / len(icer_values) if icer_values else None

        return HEORMetrics(
            total_studies=len(studies),
            studies_by_type=studies_by_type,
            studies_by_status=studies_by_status,
            total_ce_results=len(ce_results),
            results_by_model=results_by_model,
            cost_effective_count=cost_effective_count,
            total_budget_models=len(budget_models),
            total_dossiers=len(dossiers),
            dossiers_by_status=dossiers_by_status,
            total_payer_submissions=len(payer_evidence),
            payer_by_type=payer_by_type,
            avg_icer=avg_icer,
        )


# ---------------------------------------------------------------------------
# Singleton management
# ---------------------------------------------------------------------------

_service: HEORService | None = None
_service_lock = threading.Lock()


def get_heor_service() -> HEORService:
    """Return singleton HEORService instance (lazy init)."""
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = HEORService()
    return _service


def reset_heor_service() -> HEORService:
    """Reset singleton with fresh seed data (for testing)."""
    global _service
    with _service_lock:
        _service = HEORService()
    return _service
