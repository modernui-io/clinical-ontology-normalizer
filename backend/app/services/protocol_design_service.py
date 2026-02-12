"""Protocol Design & Optimization (PROTO-DESIGN) Service.

Manages protocol development lifecycle: protocol elements, endpoint definitions,
sample size calculations, schedule of assessments, protocol simulations, and
protocol design metrics.

Usage:
    from app.services.protocol_design_service import (
        get_protocol_design_service,
    )

    svc = get_protocol_design_service()
    protocols = svc.list_protocols()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.protocol_design import (
    AssessmentType,
    DesignStatus,
    DesignType,
    EndpointCategory,
    EndpointDefinition,
    EndpointDefinitionCreate,
    ProtocolDesignMetrics,
    ProtocolElement,
    ProtocolElementCreate,
    ProtocolElementUpdate,
    ProtocolPhase,
    ProtocolSimulation,
    ProtocolSimulationCreate,
    ProtocolSimulationUpdate,
    SampleSizeCalc,
    SampleSizeCalcCreate,
    ScheduleOfAssessments,
    ScheduleOfAssessmentsCreate,
    SimulationStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class ProtocolDesignService:
    """In-memory Protocol Design & Optimization engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._protocols: dict[str, ProtocolElement] = {}
        self._endpoints: dict[str, EndpointDefinition] = {}
        self._sample_calcs: dict[str, SampleSizeCalc] = {}
        self._schedules: dict[str, ScheduleOfAssessments] = {}
        self._simulations: dict[str, ProtocolSimulation] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic protocol design data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Protocol Elements ---
        protocols_data = [
            # EYLEA protocols
            {
                "id": "PROTO-001",
                "trial_id": EYLEA_TRIAL,
                "protocol_version": "4.0",
                "phase": ProtocolPhase.PHASE_3,
                "design_type": DesignType.PARALLEL,
                "status": DesignStatus.FINALIZED,
                "title": "EYLEA HD Phase 3 - Wet AMD Superiority Study",
                "indication": "Neovascular (wet) age-related macular degeneration",
                "target_population": "Adults >=50 with active CNV secondary to AMD",
                "treatment_arms": ["Aflibercept 8mg Q12W", "Aflibercept 8mg Q16W", "Aflibercept 2mg Q8W"],
                "randomization_ratio": "1:1:1",
                "blinding": "double_blind",
                "planned_enrollment": 1050,
                "treatment_duration_weeks": 48,
                "follow_up_duration_weeks": 96,
                "countries": ["US", "UK", "DE", "JP", "AU"],
                "sites_planned": 180,
                "author": "Dr. Elizabeth Chen",
                "created_at": now - timedelta(days=365),
            },
            {
                "id": "PROTO-002",
                "trial_id": EYLEA_TRIAL,
                "protocol_version": "2.1",
                "phase": ProtocolPhase.PHASE_3B,
                "design_type": DesignType.PARALLEL,
                "status": DesignStatus.APPROVED,
                "title": "EYLEA HD Extension Study - Long-term Safety",
                "indication": "Diabetic macular edema",
                "target_population": "Adults with center-involving DME and BCVA 24-73 letters",
                "treatment_arms": ["Aflibercept 8mg Q12W", "Aflibercept 8mg PRN"],
                "randomization_ratio": "1:1",
                "blinding": "open_label",
                "planned_enrollment": 400,
                "treatment_duration_weeks": 52,
                "follow_up_duration_weeks": 104,
                "countries": ["US", "CA", "FR", "IT"],
                "sites_planned": 95,
                "author": "Dr. James Rodriguez",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "PROTO-003",
                "trial_id": EYLEA_TRIAL,
                "protocol_version": "1.0",
                "phase": ProtocolPhase.PHASE_2,
                "design_type": DesignType.ADAPTIVE,
                "status": DesignStatus.DRAFT,
                "title": "EYLEA HD Dose-Finding in Retinal Vein Occlusion",
                "indication": "Macular edema following retinal vein occlusion",
                "target_population": "Adults with ME secondary to BRVO or CRVO",
                "treatment_arms": ["Aflibercept 4mg Q4W", "Aflibercept 8mg Q4W", "Aflibercept 8mg Q8W"],
                "randomization_ratio": "1:1:1",
                "blinding": "double_blind",
                "planned_enrollment": 240,
                "treatment_duration_weeks": 24,
                "follow_up_duration_weeks": 52,
                "countries": ["US", "UK"],
                "sites_planned": 45,
                "author": "Dr. Sarah Thompson",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "PROTO-004",
                "trial_id": EYLEA_TRIAL,
                "protocol_version": "1.0",
                "phase": ProtocolPhase.PHASE_1,
                "design_type": DesignType.SINGLE_ARM,
                "status": DesignStatus.CONCEPT,
                "title": "EYLEA Next-Gen Formulation PK Study",
                "indication": "Healthy volunteers / wet AMD",
                "target_population": "Adults 18-75 with stable wet AMD",
                "treatment_arms": ["Aflibercept next-gen 8mg"],
                "randomization_ratio": None,
                "blinding": "open_label",
                "planned_enrollment": 30,
                "treatment_duration_weeks": 12,
                "follow_up_duration_weeks": 24,
                "countries": ["US"],
                "sites_planned": 5,
                "author": "Dr. Michael Patel",
                "created_at": now - timedelta(days=10),
            },
            # Dupixent protocols
            {
                "id": "PROTO-005",
                "trial_id": DUPIXENT_TRIAL,
                "protocol_version": "3.2",
                "phase": ProtocolPhase.PHASE_3,
                "design_type": DesignType.PARALLEL,
                "status": DesignStatus.FINALIZED,
                "title": "LIBERTY AD PEAK - Dupixent Monotherapy in Moderate-to-Severe AD",
                "indication": "Atopic dermatitis, moderate to severe",
                "target_population": "Adults >=18 with EASI >=16 and IGA >=3",
                "treatment_arms": ["Dupilumab 300mg Q2W", "Placebo Q2W"],
                "randomization_ratio": "2:1",
                "blinding": "double_blind",
                "planned_enrollment": 750,
                "treatment_duration_weeks": 16,
                "follow_up_duration_weeks": 52,
                "countries": ["US", "DE", "JP", "KR", "BR"],
                "sites_planned": 150,
                "author": "Dr. Angela Martinez",
                "created_at": now - timedelta(days=300),
            },
            {
                "id": "PROTO-006",
                "trial_id": DUPIXENT_TRIAL,
                "protocol_version": "2.0",
                "phase": ProtocolPhase.PHASE_3,
                "design_type": DesignType.PARALLEL,
                "status": DesignStatus.APPROVED,
                "title": "LIBERTY ASTHMA VOYAGE - Dupixent in Severe Asthma",
                "indication": "Severe uncontrolled asthma with type 2 inflammation",
                "target_population": "Adults and adolescents >=12 with eosinophils >=300 or FeNO >=25",
                "treatment_arms": ["Dupilumab 200mg Q2W", "Dupilumab 300mg Q2W", "Placebo Q2W"],
                "randomization_ratio": "1:1:1",
                "blinding": "double_blind",
                "planned_enrollment": 900,
                "treatment_duration_weeks": 52,
                "follow_up_duration_weeks": 64,
                "countries": ["US", "UK", "FR", "DE", "AU", "JP"],
                "sites_planned": 200,
                "author": "Dr. David Nakamura",
                "created_at": now - timedelta(days=250),
            },
            {
                "id": "PROTO-007",
                "trial_id": DUPIXENT_TRIAL,
                "protocol_version": "1.1",
                "phase": ProtocolPhase.PHASE_2B,
                "design_type": DesignType.ADAPTIVE,
                "status": DesignStatus.UNDER_REVIEW,
                "title": "Dupixent Dose Optimization in COPD with T2 High",
                "indication": "Chronic obstructive pulmonary disease with eosinophilic phenotype",
                "target_population": "Adults >=40 with COPD and blood eosinophils >=300",
                "treatment_arms": ["Dupilumab 300mg Q2W", "Dupilumab 300mg Q4W", "Placebo"],
                "randomization_ratio": "1:1:1",
                "blinding": "double_blind",
                "planned_enrollment": 480,
                "treatment_duration_weeks": 24,
                "follow_up_duration_weeks": 36,
                "countries": ["US", "UK", "NL"],
                "sites_planned": 70,
                "author": "Dr. Patricia Sullivan",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "PROTO-008",
                "trial_id": DUPIXENT_TRIAL,
                "protocol_version": "1.0",
                "phase": ProtocolPhase.PHASE_2,
                "design_type": DesignType.CROSSOVER,
                "status": DesignStatus.DRAFT,
                "title": "Dupixent in Chronic Rhinosinusitis with Nasal Polyps - Biomarker Study",
                "indication": "Chronic rhinosinusitis with nasal polyps",
                "target_population": "Adults >=18 with bilateral nasal polyps and NPS >=5",
                "treatment_arms": ["Dupilumab 300mg Q2W -> Placebo", "Placebo -> Dupilumab 300mg Q2W"],
                "randomization_ratio": "1:1",
                "blinding": "double_blind",
                "planned_enrollment": 120,
                "treatment_duration_weeks": 24,
                "follow_up_duration_weeks": 48,
                "countries": ["US", "BE"],
                "sites_planned": 25,
                "author": "Dr. Thomas Berg",
                "created_at": now - timedelta(days=30),
            },
            # Libtayo protocols
            {
                "id": "PROTO-009",
                "trial_id": LIBTAYO_TRIAL,
                "protocol_version": "5.0",
                "phase": ProtocolPhase.PHASE_3,
                "design_type": DesignType.PARALLEL,
                "status": DesignStatus.FINALIZED,
                "title": "EMPOWER-CSCC 1 - Libtayo in Advanced Cutaneous SCC",
                "indication": "Advanced cutaneous squamous cell carcinoma",
                "target_population": "Adults with metastatic or locally advanced CSCC not amenable to surgery/radiation",
                "treatment_arms": ["Cemiplimab 350mg Q3W", "Investigator choice chemotherapy"],
                "randomization_ratio": "1:1",
                "blinding": "open_label",
                "planned_enrollment": 480,
                "treatment_duration_weeks": 96,
                "follow_up_duration_weeks": 144,
                "countries": ["US", "UK", "DE", "FR", "AU", "BR"],
                "sites_planned": 130,
                "author": "Dr. Catherine Liu",
                "created_at": now - timedelta(days=400),
            },
            {
                "id": "PROTO-010",
                "trial_id": LIBTAYO_TRIAL,
                "protocol_version": "3.1",
                "phase": ProtocolPhase.PHASE_3,
                "design_type": DesignType.PARALLEL,
                "status": DesignStatus.APPROVED,
                "title": "EMPOWER-LUNG 3 - Libtayo + Chemo in First-line NSCLC",
                "indication": "Non-small cell lung cancer, first-line",
                "target_population": "Adults with stage IV NSCLC, PD-L1 >=50%, no EGFR/ALK alterations",
                "treatment_arms": ["Cemiplimab 350mg Q3W + Platinum-doublet", "Platinum-doublet + Placebo"],
                "randomization_ratio": "2:1",
                "blinding": "double_blind",
                "planned_enrollment": 720,
                "treatment_duration_weeks": 108,
                "follow_up_duration_weeks": 156,
                "countries": ["US", "UK", "DE", "JP", "KR", "AU"],
                "sites_planned": 175,
                "author": "Dr. Andrew Foster",
                "created_at": now - timedelta(days=350),
            },
            {
                "id": "PROTO-011",
                "trial_id": LIBTAYO_TRIAL,
                "protocol_version": "1.0",
                "phase": ProtocolPhase.PHASE_2,
                "design_type": DesignType.BASKET,
                "status": DesignStatus.UNDER_REVIEW,
                "title": "Libtayo Basket Trial - TMB-High Solid Tumors",
                "indication": "Advanced solid tumors with high tumor mutational burden",
                "target_population": "Adults with TMB >=10 mut/Mb across solid tumor types",
                "treatment_arms": ["Cemiplimab 350mg Q3W"],
                "randomization_ratio": None,
                "blinding": "open_label",
                "planned_enrollment": 300,
                "treatment_duration_weeks": 52,
                "follow_up_duration_weeks": 104,
                "countries": ["US", "UK", "FR"],
                "sites_planned": 60,
                "author": "Dr. Natalie Wong",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "PROTO-012",
                "trial_id": LIBTAYO_TRIAL,
                "protocol_version": "1.0",
                "phase": ProtocolPhase.PHASE_1B,
                "design_type": DesignType.SINGLE_ARM,
                "status": DesignStatus.CONCEPT,
                "title": "Libtayo + Novel Anti-LAG3 Combination Dose Escalation",
                "indication": "Advanced solid tumors refractory to prior anti-PD-1/PD-L1",
                "target_population": "Adults with progressive disease on prior checkpoint inhibitor",
                "treatment_arms": ["Cemiplimab 350mg Q3W + Anti-LAG3 dose escalation"],
                "randomization_ratio": None,
                "blinding": "open_label",
                "planned_enrollment": 60,
                "treatment_duration_weeks": 24,
                "follow_up_duration_weeks": 52,
                "countries": ["US"],
                "sites_planned": 10,
                "author": "Dr. Gregory Harris",
                "created_at": now - timedelta(days=15),
            },
        ]

        for p in protocols_data:
            self._protocols[p["id"]] = ProtocolElement(**p)

        # --- 18 Endpoint Definitions ---
        endpoints_data = [
            # EYLEA PROTO-001 endpoints
            {"id": "EP-001", "protocol_id": "PROTO-001", "category": EndpointCategory.PRIMARY, "name": "BCVA Change from Baseline at Week 48", "description": "Change in best-corrected visual acuity (ETDRS letters) from baseline at Week 48", "measurement_tool": "ETDRS Chart", "timepoint": "Week 48", "statistical_method": "Mixed-effects model for repeated measures (MMRM)", "clinically_meaningful_difference": ">=4 letters non-inferiority margin", "regulatory_accepted": True, "validated_instrument": True},
            {"id": "EP-002", "protocol_id": "PROTO-001", "category": EndpointCategory.SECONDARY, "name": "Central Retinal Thickness Change at Week 48", "description": "Change in CRT measured by SD-OCT from baseline at Week 48", "measurement_tool": "SD-OCT", "timepoint": "Week 48", "statistical_method": "ANCOVA with baseline adjustment", "clinically_meaningful_difference": None, "regulatory_accepted": True, "validated_instrument": True},
            {"id": "EP-003", "protocol_id": "PROTO-001", "category": EndpointCategory.SAFETY, "name": "Incidence of Ocular AEs", "description": "Incidence and severity of treatment-emergent ocular adverse events", "measurement_tool": "MedDRA Coding", "timepoint": "Through Week 96", "statistical_method": "Descriptive statistics", "clinically_meaningful_difference": None, "regulatory_accepted": True, "validated_instrument": True},
            {"id": "EP-004", "protocol_id": "PROTO-001", "category": EndpointCategory.BIOMARKER, "name": "Anti-drug Antibody Development", "description": "Incidence and titer of anti-aflibercept antibodies", "measurement_tool": "ELISA", "timepoint": "Baseline, Week 12, 24, 48, 96", "statistical_method": "Descriptive statistics", "clinically_meaningful_difference": None, "regulatory_accepted": False, "validated_instrument": True},
            # Dupixent PROTO-005 endpoints
            {"id": "EP-005", "protocol_id": "PROTO-005", "category": EndpointCategory.PRIMARY, "name": "EASI-75 Response at Week 16", "description": "Proportion achieving >=75% improvement in EASI score at Week 16", "measurement_tool": "EASI Scale", "timepoint": "Week 16", "statistical_method": "Cochran-Mantel-Haenszel test", "clinically_meaningful_difference": ">=15% difference vs placebo", "regulatory_accepted": True, "validated_instrument": True},
            {"id": "EP-006", "protocol_id": "PROTO-005", "category": EndpointCategory.PRIMARY, "name": "IGA 0/1 Response at Week 16", "description": "Proportion achieving IGA score 0 or 1 with >=2 point reduction at Week 16", "measurement_tool": "IGA Scale", "timepoint": "Week 16", "statistical_method": "Cochran-Mantel-Haenszel test", "clinically_meaningful_difference": ">=10% difference vs placebo", "regulatory_accepted": True, "validated_instrument": True},
            {"id": "EP-007", "protocol_id": "PROTO-005", "category": EndpointCategory.SECONDARY, "name": "Pruritus NRS Change at Week 4", "description": "Change from baseline in weekly average peak Pruritus NRS score at Week 4", "measurement_tool": "Pruritus NRS (0-10)", "timepoint": "Week 4", "statistical_method": "MMRM", "clinically_meaningful_difference": ">=3 point reduction", "regulatory_accepted": True, "validated_instrument": True},
            {"id": "EP-008", "protocol_id": "PROTO-005", "category": EndpointCategory.PATIENT_REPORTED, "name": "DLQI Change at Week 16", "description": "Change from baseline in Dermatology Life Quality Index at Week 16", "measurement_tool": "DLQI", "timepoint": "Week 16", "statistical_method": "ANCOVA", "clinically_meaningful_difference": ">=4 points", "regulatory_accepted": True, "validated_instrument": True},
            {"id": "EP-009", "protocol_id": "PROTO-005", "category": EndpointCategory.EXPLORATORY, "name": "Serum Biomarker Panel", "description": "Change in TARC, total IgE, eotaxin-3 from baseline", "measurement_tool": "Immunoassay Panel", "timepoint": "Baseline, Week 4, 16, 52", "statistical_method": "Descriptive with correlation analysis", "clinically_meaningful_difference": None, "regulatory_accepted": False, "validated_instrument": True},
            # Dupixent PROTO-006 endpoints
            {"id": "EP-010", "protocol_id": "PROTO-006", "category": EndpointCategory.PRIMARY, "name": "Annualized Severe Exacerbation Rate", "description": "Rate of severe asthma exacerbations over 52 weeks", "measurement_tool": "Clinical assessment", "timepoint": "Over 52 weeks", "statistical_method": "Negative binomial regression", "clinically_meaningful_difference": ">=50% reduction vs placebo", "regulatory_accepted": True, "validated_instrument": True},
            {"id": "EP-011", "protocol_id": "PROTO-006", "category": EndpointCategory.SECONDARY, "name": "FEV1 Change at Week 12", "description": "Change from baseline in pre-bronchodilator FEV1 at Week 12", "measurement_tool": "Spirometry", "timepoint": "Week 12", "statistical_method": "MMRM", "clinically_meaningful_difference": ">=200mL", "regulatory_accepted": True, "validated_instrument": True},
            # Libtayo PROTO-009 endpoints
            {"id": "EP-012", "protocol_id": "PROTO-009", "category": EndpointCategory.PRIMARY, "name": "Overall Response Rate (ORR)", "description": "Proportion with confirmed CR or PR per RECIST 1.1 by independent central review", "measurement_tool": "RECIST 1.1 / CT-MRI", "timepoint": "Best overall response", "statistical_method": "Exact binomial confidence interval", "clinically_meaningful_difference": None, "regulatory_accepted": True, "validated_instrument": True},
            {"id": "EP-013", "protocol_id": "PROTO-009", "category": EndpointCategory.SECONDARY, "name": "Duration of Response (DOR)", "description": "Time from first response to progression or death", "measurement_tool": "RECIST 1.1", "timepoint": "Continuous", "statistical_method": "Kaplan-Meier", "clinically_meaningful_difference": None, "regulatory_accepted": True, "validated_instrument": True},
            {"id": "EP-014", "protocol_id": "PROTO-009", "category": EndpointCategory.SECONDARY, "name": "Progression-Free Survival (PFS)", "description": "Time from randomization to first progression or death", "measurement_tool": "RECIST 1.1", "timepoint": "Continuous", "statistical_method": "Log-rank test / Cox regression", "clinically_meaningful_difference": "HR <=0.70", "regulatory_accepted": True, "validated_instrument": True},
            # Libtayo PROTO-010 endpoints
            {"id": "EP-015", "protocol_id": "PROTO-010", "category": EndpointCategory.PRIMARY, "name": "Overall Survival (OS)", "description": "Time from randomization to death from any cause", "measurement_tool": "Clinical assessment", "timepoint": "Continuous", "statistical_method": "Log-rank test / Cox regression", "clinically_meaningful_difference": "HR <=0.75", "regulatory_accepted": True, "validated_instrument": True},
            {"id": "EP-016", "protocol_id": "PROTO-010", "category": EndpointCategory.SECONDARY, "name": "ORR by BICR", "description": "Overall response rate by blinded independent central review", "measurement_tool": "RECIST 1.1", "timepoint": "Best overall response", "statistical_method": "CMH test stratified by PD-L1", "clinically_meaningful_difference": None, "regulatory_accepted": True, "validated_instrument": True},
            {"id": "EP-017", "protocol_id": "PROTO-010", "category": EndpointCategory.PHARMACOKINETIC, "name": "Cemiplimab Trough Concentrations", "description": "Trough serum concentrations of cemiplimab at steady state", "measurement_tool": "Validated LC-MS/MS", "timepoint": "Pre-dose Cycles 1-8", "statistical_method": "Population PK modeling", "clinically_meaningful_difference": None, "regulatory_accepted": False, "validated_instrument": True},
            {"id": "EP-018", "protocol_id": "PROTO-010", "category": EndpointCategory.SAFETY, "name": "Immune-Related AE Incidence", "description": "Incidence and severity of immune-related adverse events", "measurement_tool": "MedDRA / CTCAE v5.0", "timepoint": "Through 90 days post-treatment", "statistical_method": "Descriptive statistics", "clinically_meaningful_difference": None, "regulatory_accepted": True, "validated_instrument": True},
        ]

        for e in endpoints_data:
            self._endpoints[e["id"]] = EndpointDefinition(**e)

        # --- 12 Sample Size Calculations ---
        calcs_data = [
            {"id": "SSC-001", "protocol_id": "PROTO-001", "endpoint_id": "EP-001", "alpha": 0.025, "power": 0.90, "effect_size": 0.35, "dropout_rate_pct": 15.0, "sample_per_arm": 350, "total_sample": 1050, "method": "MMRM with non-inferiority margin", "assumptions": ["Non-inferiority margin: 4 letters", "SD of BCVA change: 12 letters", "Correlation between visits: 0.6", "15% dropout rate"], "calculated_by": "Dr. Robert Statman", "calculation_date": now - timedelta(days=360)},
            {"id": "SSC-002", "protocol_id": "PROTO-002", "endpoint_id": None, "alpha": 0.05, "power": 0.80, "effect_size": None, "dropout_rate_pct": 20.0, "sample_per_arm": 200, "total_sample": 400, "method": "Descriptive safety study (event-driven)", "assumptions": ["Safety study - not powered for efficacy", "200 per arm for rare event detection", "20% dropout rate expected"], "calculated_by": "Dr. Lisa Quantova", "calculation_date": now - timedelta(days=195)},
            {"id": "SSC-003", "protocol_id": "PROTO-003", "endpoint_id": None, "alpha": 0.05, "power": 0.80, "effect_size": 0.40, "dropout_rate_pct": 12.0, "sample_per_arm": 80, "total_sample": 240, "method": "Adaptive design with interim futility analysis", "assumptions": ["Effect size 0.4 based on Phase 1 data", "Interim at 50% enrollment", "Futility boundary: conditional power <20%"], "calculated_by": "Dr. Robert Statman", "calculation_date": now - timedelta(days=40)},
            {"id": "SSC-004", "protocol_id": "PROTO-005", "endpoint_id": "EP-005", "alpha": 0.025, "power": 0.90, "effect_size": None, "dropout_rate_pct": 10.0, "sample_per_arm": 375, "total_sample": 750, "method": "CMH test for binary endpoint (2:1 randomization)", "assumptions": ["Placebo EASI-75 rate: 15%", "Dupilumab EASI-75 rate: 45%", "10% dropout", "One-sided alpha 0.025"], "calculated_by": "Dr. Maria Poweris", "calculation_date": now - timedelta(days=295)},
            {"id": "SSC-005", "protocol_id": "PROTO-005", "endpoint_id": "EP-006", "alpha": 0.025, "power": 0.85, "effect_size": None, "dropout_rate_pct": 10.0, "sample_per_arm": 375, "total_sample": 750, "method": "CMH test for binary endpoint (co-primary)", "assumptions": ["Placebo IGA 0/1 rate: 10%", "Dupilumab IGA 0/1 rate: 35%", "Multiplicity adjustment via hierarchical testing"], "calculated_by": "Dr. Maria Poweris", "calculation_date": now - timedelta(days=295)},
            {"id": "SSC-006", "protocol_id": "PROTO-006", "endpoint_id": "EP-010", "alpha": 0.05, "power": 0.90, "effect_size": 0.50, "dropout_rate_pct": 15.0, "sample_per_arm": 300, "total_sample": 900, "method": "Negative binomial regression model", "assumptions": ["Placebo exacerbation rate: 1.2/year", "50% rate reduction expected", "Overdispersion parameter: 0.8", "15% dropout"], "calculated_by": "Dr. Robert Statman", "calculation_date": now - timedelta(days=245)},
            {"id": "SSC-007", "protocol_id": "PROTO-007", "endpoint_id": None, "alpha": 0.05, "power": 0.80, "effect_size": 0.30, "dropout_rate_pct": 15.0, "sample_per_arm": 160, "total_sample": 480, "method": "Adaptive seamless Phase 2b/3 design", "assumptions": ["Interim analysis at 50% information", "Promising zone: 0.0025 < p < 0.5", "Adaptive sample re-estimation allowed"], "calculated_by": "Dr. Lisa Quantova", "calculation_date": now - timedelta(days=55)},
            {"id": "SSC-008", "protocol_id": "PROTO-009", "endpoint_id": "EP-012", "alpha": 0.025, "power": 0.90, "effect_size": None, "dropout_rate_pct": 10.0, "sample_per_arm": 240, "total_sample": 480, "method": "Exact binomial test for ORR", "assumptions": ["Expected ORR cemiplimab: 45%", "Expected ORR chemotherapy: 25%", "Stratified by metastatic vs locally advanced"], "calculated_by": "Dr. Maria Poweris", "calculation_date": now - timedelta(days=395)},
            {"id": "SSC-009", "protocol_id": "PROTO-010", "endpoint_id": "EP-015", "alpha": 0.025, "power": 0.90, "effect_size": None, "dropout_rate_pct": 5.0, "sample_per_arm": 360, "total_sample": 720, "method": "Log-rank test for OS with 2:1 randomization", "assumptions": ["Median OS control: 14 months", "Target HR: 0.75", "Two interim analyses (O'Brien-Fleming)", "5% loss to follow-up"], "calculated_by": "Dr. Robert Statman", "calculation_date": now - timedelta(days=345)},
            {"id": "SSC-010", "protocol_id": "PROTO-011", "endpoint_id": None, "alpha": 0.05, "power": 0.80, "effect_size": None, "dropout_rate_pct": 10.0, "sample_per_arm": 300, "total_sample": 300, "method": "Simon two-stage optimal design (basket)", "assumptions": ["Null ORR: 15%", "Alternative ORR: 30%", "Stage 1: 15 patients per basket", "5 tumor-type baskets"], "calculated_by": "Dr. Lisa Quantova", "calculation_date": now - timedelta(days=85)},
            {"id": "SSC-011", "protocol_id": "PROTO-008", "endpoint_id": None, "alpha": 0.05, "power": 0.80, "effect_size": 0.45, "dropout_rate_pct": 10.0, "sample_per_arm": 60, "total_sample": 120, "method": "Crossover design with washout adjustment", "assumptions": ["Carryover effect minimal with 4-week washout", "Within-patient correlation: 0.7", "Effect size 0.45 for NPS reduction"], "calculated_by": "Dr. Maria Poweris", "calculation_date": now - timedelta(days=25)},
            {"id": "SSC-012", "protocol_id": "PROTO-012", "endpoint_id": None, "alpha": 0.10, "power": 0.80, "effect_size": None, "dropout_rate_pct": 15.0, "sample_per_arm": 60, "total_sample": 60, "method": "3+3 dose escalation followed by expansion", "assumptions": ["DLT observation window: 21 days", "6 dose levels planned", "Expansion cohort: 20 patients at RP2D"], "calculated_by": "Dr. Robert Statman", "calculation_date": now - timedelta(days=10)},
        ]

        for c in calcs_data:
            self._sample_calcs[c["id"]] = SampleSizeCalc(**c)

        # --- 15 Schedule of Assessments ---
        schedules_data = [
            # PROTO-001 schedule (EYLEA)
            {"id": "SOA-001", "protocol_id": "PROTO-001", "visit_name": "Screening", "visit_number": 0, "day": -28, "window_minus_days": 0, "window_plus_days": 14, "assessments": [AssessmentType.PHYSICAL_EXAM, AssessmentType.VITAL_SIGNS, AssessmentType.LAB_WORK, AssessmentType.ECG, AssessmentType.IMAGING], "mandatory": True, "estimated_duration_minutes": 180, "notes": "Full screening including OCT and fluorescein angiography"},
            {"id": "SOA-002", "protocol_id": "PROTO-001", "visit_name": "Baseline / Day 1", "visit_number": 1, "day": 1, "window_minus_days": 0, "window_plus_days": 0, "assessments": [AssessmentType.VITAL_SIGNS, AssessmentType.IMAGING, AssessmentType.BIOMARKER, AssessmentType.PK_SAMPLE, AssessmentType.ADVERSE_EVENT, AssessmentType.CONCOMITANT_MED], "mandatory": True, "estimated_duration_minutes": 120, "notes": "First injection visit with baseline OCT and BCVA"},
            {"id": "SOA-003", "protocol_id": "PROTO-001", "visit_name": "Week 4", "visit_number": 2, "day": 29, "window_minus_days": 3, "window_plus_days": 3, "assessments": [AssessmentType.VITAL_SIGNS, AssessmentType.IMAGING, AssessmentType.ADVERSE_EVENT, AssessmentType.CONCOMITANT_MED], "mandatory": True, "estimated_duration_minutes": 90, "notes": "Monthly injection visit"},
            {"id": "SOA-004", "protocol_id": "PROTO-001", "visit_name": "Week 48 (Primary)", "visit_number": 12, "day": 337, "window_minus_days": 7, "window_plus_days": 7, "assessments": [AssessmentType.PHYSICAL_EXAM, AssessmentType.VITAL_SIGNS, AssessmentType.LAB_WORK, AssessmentType.IMAGING, AssessmentType.BIOMARKER, AssessmentType.PK_SAMPLE, AssessmentType.ADVERSE_EVENT, AssessmentType.CONCOMITANT_MED], "mandatory": True, "estimated_duration_minutes": 150, "notes": "Primary endpoint assessment visit"},
            {"id": "SOA-005", "protocol_id": "PROTO-001", "visit_name": "Week 96 (End of Study)", "visit_number": 24, "day": 673, "window_minus_days": 7, "window_plus_days": 7, "assessments": [AssessmentType.PHYSICAL_EXAM, AssessmentType.VITAL_SIGNS, AssessmentType.LAB_WORK, AssessmentType.ECG, AssessmentType.IMAGING, AssessmentType.BIOMARKER, AssessmentType.ADVERSE_EVENT, AssessmentType.CONCOMITANT_MED, AssessmentType.QUESTIONNAIRE], "mandatory": True, "estimated_duration_minutes": 180, "notes": "Final study visit with comprehensive assessment"},
            # PROTO-005 schedule (Dupixent AD)
            {"id": "SOA-006", "protocol_id": "PROTO-005", "visit_name": "Screening", "visit_number": 0, "day": -35, "window_minus_days": 0, "window_plus_days": 21, "assessments": [AssessmentType.PHYSICAL_EXAM, AssessmentType.VITAL_SIGNS, AssessmentType.LAB_WORK, AssessmentType.QUESTIONNAIRE], "mandatory": True, "estimated_duration_minutes": 120, "notes": "EASI, IGA, BSA assessment and washout verification"},
            {"id": "SOA-007", "protocol_id": "PROTO-005", "visit_name": "Baseline / Day 1", "visit_number": 1, "day": 1, "window_minus_days": 0, "window_plus_days": 0, "assessments": [AssessmentType.VITAL_SIGNS, AssessmentType.BIOMARKER, AssessmentType.QUESTIONNAIRE, AssessmentType.ADVERSE_EVENT, AssessmentType.CONCOMITANT_MED], "mandatory": True, "estimated_duration_minutes": 90, "notes": "Loading dose administration. EASI/IGA/NRS baseline"},
            {"id": "SOA-008", "protocol_id": "PROTO-005", "visit_name": "Week 16 (Primary)", "visit_number": 9, "day": 113, "window_minus_days": 3, "window_plus_days": 3, "assessments": [AssessmentType.PHYSICAL_EXAM, AssessmentType.VITAL_SIGNS, AssessmentType.LAB_WORK, AssessmentType.BIOMARKER, AssessmentType.QUESTIONNAIRE, AssessmentType.ADVERSE_EVENT, AssessmentType.CONCOMITANT_MED], "mandatory": True, "estimated_duration_minutes": 120, "notes": "Primary endpoint assessment - EASI-75 and IGA 0/1"},
            {"id": "SOA-009", "protocol_id": "PROTO-005", "visit_name": "Week 52 (End of Treatment)", "visit_number": 27, "day": 365, "window_minus_days": 7, "window_plus_days": 7, "assessments": [AssessmentType.PHYSICAL_EXAM, AssessmentType.VITAL_SIGNS, AssessmentType.LAB_WORK, AssessmentType.BIOMARKER, AssessmentType.QUESTIONNAIRE, AssessmentType.ADVERSE_EVENT, AssessmentType.CONCOMITANT_MED], "mandatory": True, "estimated_duration_minutes": 150, "notes": "Final treatment visit with durability assessment"},
            # PROTO-009 schedule (Libtayo CSCC)
            {"id": "SOA-010", "protocol_id": "PROTO-009", "visit_name": "Screening", "visit_number": 0, "day": -28, "window_minus_days": 0, "window_plus_days": 14, "assessments": [AssessmentType.PHYSICAL_EXAM, AssessmentType.VITAL_SIGNS, AssessmentType.LAB_WORK, AssessmentType.ECG, AssessmentType.IMAGING, AssessmentType.BIOMARKER], "mandatory": True, "estimated_duration_minutes": 180, "notes": "Tumor biopsy for PD-L1, baseline CT scan, ECG"},
            {"id": "SOA-011", "protocol_id": "PROTO-009", "visit_name": "Cycle 1 Day 1", "visit_number": 1, "day": 1, "window_minus_days": 0, "window_plus_days": 0, "assessments": [AssessmentType.VITAL_SIGNS, AssessmentType.LAB_WORK, AssessmentType.PK_SAMPLE, AssessmentType.ADVERSE_EVENT, AssessmentType.CONCOMITANT_MED], "mandatory": True, "estimated_duration_minutes": 120, "notes": "First infusion with PK sampling pre/post"},
            {"id": "SOA-012", "protocol_id": "PROTO-009", "visit_name": "Cycle 3 Day 1 (Week 9)", "visit_number": 3, "day": 64, "window_minus_days": 3, "window_plus_days": 3, "assessments": [AssessmentType.VITAL_SIGNS, AssessmentType.LAB_WORK, AssessmentType.IMAGING, AssessmentType.ADVERSE_EVENT, AssessmentType.CONCOMITANT_MED], "mandatory": True, "estimated_duration_minutes": 150, "notes": "First tumor assessment by RECIST 1.1"},
            # PROTO-010 schedule (Libtayo NSCLC)
            {"id": "SOA-013", "protocol_id": "PROTO-010", "visit_name": "Screening", "visit_number": 0, "day": -28, "window_minus_days": 0, "window_plus_days": 14, "assessments": [AssessmentType.PHYSICAL_EXAM, AssessmentType.VITAL_SIGNS, AssessmentType.LAB_WORK, AssessmentType.ECG, AssessmentType.IMAGING, AssessmentType.BIOMARKER], "mandatory": True, "estimated_duration_minutes": 210, "notes": "PD-L1 testing, brain MRI, baseline CT chest/abdomen/pelvis"},
            {"id": "SOA-014", "protocol_id": "PROTO-010", "visit_name": "Cycle 1 Day 1", "visit_number": 1, "day": 1, "window_minus_days": 0, "window_plus_days": 0, "assessments": [AssessmentType.VITAL_SIGNS, AssessmentType.LAB_WORK, AssessmentType.PK_SAMPLE, AssessmentType.ADVERSE_EVENT, AssessmentType.CONCOMITANT_MED], "mandatory": True, "estimated_duration_minutes": 180, "notes": "First infusion day - cemiplimab + chemo"},
            {"id": "SOA-015", "protocol_id": "PROTO-010", "visit_name": "Cycle 3 Day 1 (Week 9)", "visit_number": 3, "day": 64, "window_minus_days": 3, "window_plus_days": 3, "assessments": [AssessmentType.VITAL_SIGNS, AssessmentType.LAB_WORK, AssessmentType.IMAGING, AssessmentType.PK_SAMPLE, AssessmentType.ADVERSE_EVENT, AssessmentType.CONCOMITANT_MED], "mandatory": True, "estimated_duration_minutes": 180, "notes": "First RECIST assessment, PK trough sample"},
        ]

        for s in schedules_data:
            self._schedules[s["id"]] = ScheduleOfAssessments(**s)

        # --- 12 Protocol Simulations ---
        sims_data = [
            {"id": "SIM-001", "protocol_id": "PROTO-001", "simulation_name": "EYLEA HD Enrollment Feasibility - Base Case", "status": SimulationStatus.COMPLETED, "iterations": 10000, "enrollment_rate_per_month": 35.0, "dropout_rate_pct": 15.0, "effect_size": 0.35, "predicted_power": 0.92, "predicted_duration_months": 30.0, "predicted_cost": 185000000.0, "success_probability_pct": 88.5, "run_date": now - timedelta(days=355), "run_by": "Dr. Robert Statman"},
            {"id": "SIM-002", "protocol_id": "PROTO-001", "simulation_name": "EYLEA HD Enrollment Feasibility - Conservative", "status": SimulationStatus.COMPLETED, "iterations": 10000, "enrollment_rate_per_month": 25.0, "dropout_rate_pct": 20.0, "effect_size": 0.30, "predicted_power": 0.85, "predicted_duration_months": 42.0, "predicted_cost": 210000000.0, "success_probability_pct": 76.2, "run_date": now - timedelta(days=355), "run_by": "Dr. Robert Statman"},
            {"id": "SIM-003", "protocol_id": "PROTO-003", "simulation_name": "RVO Adaptive Design Operating Characteristics", "status": SimulationStatus.COMPLETED, "iterations": 50000, "enrollment_rate_per_month": 15.0, "dropout_rate_pct": 12.0, "effect_size": 0.40, "predicted_power": 0.83, "predicted_duration_months": 16.0, "predicted_cost": 42000000.0, "success_probability_pct": 72.8, "run_date": now - timedelta(days=40), "run_by": "Dr. Lisa Quantova"},
            {"id": "SIM-004", "protocol_id": "PROTO-005", "simulation_name": "LIBERTY AD PEAK Power Simulation", "status": SimulationStatus.COMPLETED, "iterations": 10000, "enrollment_rate_per_month": 50.0, "dropout_rate_pct": 10.0, "effect_size": 0.50, "predicted_power": 0.94, "predicted_duration_months": 15.0, "predicted_cost": 120000000.0, "success_probability_pct": 91.3, "run_date": now - timedelta(days=290), "run_by": "Dr. Maria Poweris"},
            {"id": "SIM-005", "protocol_id": "PROTO-006", "simulation_name": "LIBERTY ASTHMA VOYAGE Enrollment Model", "status": SimulationStatus.COMPLETED, "iterations": 10000, "enrollment_rate_per_month": 40.0, "dropout_rate_pct": 15.0, "effect_size": 0.50, "predicted_power": 0.91, "predicted_duration_months": 22.5, "predicted_cost": 165000000.0, "success_probability_pct": 85.7, "run_date": now - timedelta(days=240), "run_by": "Dr. Robert Statman"},
            {"id": "SIM-006", "protocol_id": "PROTO-007", "simulation_name": "COPD Adaptive Design Simulation", "status": SimulationStatus.RUNNING, "iterations": 25000, "enrollment_rate_per_month": 20.0, "dropout_rate_pct": 15.0, "effect_size": 0.30, "predicted_power": None, "predicted_duration_months": None, "predicted_cost": None, "success_probability_pct": None, "run_date": None, "run_by": "Dr. Lisa Quantova"},
            {"id": "SIM-007", "protocol_id": "PROTO-009", "simulation_name": "EMPOWER-CSCC 1 ORR Simulation", "status": SimulationStatus.COMPLETED, "iterations": 10000, "enrollment_rate_per_month": 20.0, "dropout_rate_pct": 10.0, "effect_size": None, "predicted_power": 0.93, "predicted_duration_months": 24.0, "predicted_cost": 95000000.0, "success_probability_pct": 89.1, "run_date": now - timedelta(days=390), "run_by": "Dr. Maria Poweris"},
            {"id": "SIM-008", "protocol_id": "PROTO-010", "simulation_name": "EMPOWER-LUNG 3 OS Event-Driven Simulation", "status": SimulationStatus.COMPLETED, "iterations": 10000, "enrollment_rate_per_month": 30.0, "dropout_rate_pct": 5.0, "effect_size": None, "predicted_power": 0.90, "predicted_duration_months": 36.0, "predicted_cost": 225000000.0, "success_probability_pct": 82.4, "run_date": now - timedelta(days=340), "run_by": "Dr. Robert Statman"},
            {"id": "SIM-009", "protocol_id": "PROTO-011", "simulation_name": "TMB-High Basket Trial Futility Simulation", "status": SimulationStatus.COMPLETED, "iterations": 50000, "enrollment_rate_per_month": 12.0, "dropout_rate_pct": 10.0, "effect_size": None, "predicted_power": 0.82, "predicted_duration_months": 25.0, "predicted_cost": 55000000.0, "success_probability_pct": 68.3, "run_date": now - timedelta(days=80), "run_by": "Dr. Lisa Quantova"},
            {"id": "SIM-010", "protocol_id": "PROTO-012", "simulation_name": "LAG3 Combo Dose Escalation DLT Sim", "status": SimulationStatus.CONFIGURED, "iterations": 5000, "enrollment_rate_per_month": 5.0, "dropout_rate_pct": 15.0, "effect_size": None, "predicted_power": None, "predicted_duration_months": None, "predicted_cost": None, "success_probability_pct": None, "run_date": None, "run_by": "Dr. Robert Statman"},
            {"id": "SIM-011", "protocol_id": "PROTO-001", "simulation_name": "EYLEA HD Sensitivity - High Dropout", "status": SimulationStatus.COMPLETED, "iterations": 10000, "enrollment_rate_per_month": 35.0, "dropout_rate_pct": 25.0, "effect_size": 0.35, "predicted_power": 0.87, "predicted_duration_months": 32.0, "predicted_cost": 195000000.0, "success_probability_pct": 79.6, "run_date": now - timedelta(days=350), "run_by": "Dr. Lisa Quantova"},
            {"id": "SIM-012", "protocol_id": "PROTO-005", "simulation_name": "LIBERTY AD Subgroup Power Analysis", "status": SimulationStatus.FAILED, "iterations": 10000, "enrollment_rate_per_month": 50.0, "dropout_rate_pct": 10.0, "effect_size": 0.30, "predicted_power": None, "predicted_duration_months": None, "predicted_cost": None, "success_probability_pct": None, "run_date": now - timedelta(days=280), "run_by": "Dr. Maria Poweris"},
        ]

        for s in sims_data:
            self._simulations[s["id"]] = ProtocolSimulation(**s)

    # ------------------------------------------------------------------
    # Protocol Element CRUD
    # ------------------------------------------------------------------

    def list_protocols(
        self,
        *,
        trial_id: str | None = None,
        phase: ProtocolPhase | None = None,
        status: DesignStatus | None = None,
    ) -> list[ProtocolElement]:
        """List protocol elements with optional filters."""
        with self._lock:
            result = list(self._protocols.values())

        if trial_id is not None:
            result = [p for p in result if p.trial_id == trial_id]
        if phase is not None:
            result = [p for p in result if p.phase == phase]
        if status is not None:
            result = [p for p in result if p.status == status]

        return sorted(result, key=lambda p: p.created_at, reverse=True)

    def get_protocol(self, protocol_id: str) -> ProtocolElement | None:
        """Get a single protocol element by ID."""
        with self._lock:
            return self._protocols.get(protocol_id)

    def create_protocol(self, payload: ProtocolElementCreate) -> ProtocolElement:
        """Create a new protocol element."""
        now = datetime.now(timezone.utc)
        protocol_id = f"PROTO-{uuid4().hex[:8].upper()}"
        protocol = ProtocolElement(
            id=protocol_id,
            trial_id=payload.trial_id,
            protocol_version=payload.protocol_version,
            phase=payload.phase,
            design_type=payload.design_type,
            status=DesignStatus.CONCEPT,
            title=payload.title,
            indication=payload.indication,
            target_population=payload.target_population,
            treatment_arms=payload.treatment_arms,
            blinding=payload.blinding,
            planned_enrollment=payload.planned_enrollment,
            author=payload.author,
            created_at=now,
        )
        with self._lock:
            self._protocols[protocol_id] = protocol
        logger.info("Created protocol %s: %s", protocol_id, payload.title)
        return protocol

    def update_protocol(
        self, protocol_id: str, payload: ProtocolElementUpdate
    ) -> ProtocolElement | None:
        """Update an existing protocol element."""
        with self._lock:
            existing = self._protocols.get(protocol_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ProtocolElement(**data)
            self._protocols[protocol_id] = updated
        return updated

    def delete_protocol(self, protocol_id: str) -> bool:
        """Delete a protocol element. Returns True if deleted."""
        with self._lock:
            if protocol_id in self._protocols:
                del self._protocols[protocol_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Endpoint Definition CRUD
    # ------------------------------------------------------------------

    def list_endpoints(
        self,
        *,
        protocol_id: str | None = None,
        category: EndpointCategory | None = None,
    ) -> list[EndpointDefinition]:
        """List endpoint definitions with optional filters."""
        with self._lock:
            result = list(self._endpoints.values())

        if protocol_id is not None:
            result = [e for e in result if e.protocol_id == protocol_id]
        if category is not None:
            result = [e for e in result if e.category == category]

        return sorted(result, key=lambda e: e.id)

    def get_endpoint(self, endpoint_id: str) -> EndpointDefinition | None:
        """Get a single endpoint definition by ID."""
        with self._lock:
            return self._endpoints.get(endpoint_id)

    def create_endpoint(self, payload: EndpointDefinitionCreate) -> EndpointDefinition:
        """Create a new endpoint definition."""
        endpoint_id = f"EP-{uuid4().hex[:8].upper()}"
        endpoint = EndpointDefinition(
            id=endpoint_id,
            protocol_id=payload.protocol_id,
            category=payload.category,
            name=payload.name,
            description=payload.description,
            measurement_tool=payload.measurement_tool,
            timepoint=payload.timepoint,
            statistical_method=payload.statistical_method,
            clinically_meaningful_difference=payload.clinically_meaningful_difference,
        )
        with self._lock:
            self._endpoints[endpoint_id] = endpoint
        logger.info("Created endpoint %s: %s", endpoint_id, payload.name)
        return endpoint

    def update_endpoint(
        self, endpoint_id: str, payload: dict
    ) -> EndpointDefinition | None:
        """Update an endpoint definition from a dict of changes."""
        with self._lock:
            existing = self._endpoints.get(endpoint_id)
            if existing is None:
                return None
            data = existing.model_dump()
            data.update(payload)
            updated = EndpointDefinition(**data)
            self._endpoints[endpoint_id] = updated
        return updated

    def delete_endpoint(self, endpoint_id: str) -> bool:
        """Delete an endpoint definition. Returns True if deleted."""
        with self._lock:
            if endpoint_id in self._endpoints:
                del self._endpoints[endpoint_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Sample Size Calculation CRUD
    # ------------------------------------------------------------------

    def list_sample_calcs(
        self,
        *,
        protocol_id: str | None = None,
    ) -> list[SampleSizeCalc]:
        """List sample size calculations with optional protocol filter."""
        with self._lock:
            result = list(self._sample_calcs.values())

        if protocol_id is not None:
            result = [c for c in result if c.protocol_id == protocol_id]

        return sorted(result, key=lambda c: c.calculation_date, reverse=True)

    def get_sample_calc(self, calc_id: str) -> SampleSizeCalc | None:
        """Get a single sample size calculation by ID."""
        with self._lock:
            return self._sample_calcs.get(calc_id)

    def create_sample_calc(self, payload: SampleSizeCalcCreate) -> SampleSizeCalc:
        """Create a new sample size calculation."""
        now = datetime.now(timezone.utc)
        calc_id = f"SSC-{uuid4().hex[:8].upper()}"
        calc = SampleSizeCalc(
            id=calc_id,
            protocol_id=payload.protocol_id,
            endpoint_id=payload.endpoint_id,
            alpha=payload.alpha,
            power=payload.power,
            effect_size=payload.effect_size,
            dropout_rate_pct=payload.dropout_rate_pct,
            sample_per_arm=payload.sample_per_arm,
            total_sample=payload.total_sample,
            method=payload.method,
            assumptions=payload.assumptions,
            calculated_by=payload.calculated_by,
            calculation_date=now,
        )
        with self._lock:
            self._sample_calcs[calc_id] = calc
        logger.info("Created sample size calc %s for protocol %s", calc_id, payload.protocol_id)
        return calc

    def update_sample_calc(
        self, calc_id: str, payload: dict
    ) -> SampleSizeCalc | None:
        """Update a sample size calculation from a dict of changes."""
        with self._lock:
            existing = self._sample_calcs.get(calc_id)
            if existing is None:
                return None
            data = existing.model_dump()
            data.update(payload)
            updated = SampleSizeCalc(**data)
            self._sample_calcs[calc_id] = updated
        return updated

    def delete_sample_calc(self, calc_id: str) -> bool:
        """Delete a sample size calculation. Returns True if deleted."""
        with self._lock:
            if calc_id in self._sample_calcs:
                del self._sample_calcs[calc_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Schedule of Assessments CRUD
    # ------------------------------------------------------------------

    def list_schedules(
        self,
        *,
        protocol_id: str | None = None,
    ) -> list[ScheduleOfAssessments]:
        """List schedule of assessments with optional protocol filter."""
        with self._lock:
            result = list(self._schedules.values())

        if protocol_id is not None:
            result = [s for s in result if s.protocol_id == protocol_id]

        return sorted(result, key=lambda s: (s.protocol_id, s.visit_number))

    def get_schedule(self, schedule_id: str) -> ScheduleOfAssessments | None:
        """Get a single schedule of assessments entry by ID."""
        with self._lock:
            return self._schedules.get(schedule_id)

    def create_schedule(self, payload: ScheduleOfAssessmentsCreate) -> ScheduleOfAssessments:
        """Create a new schedule of assessments entry."""
        schedule_id = f"SOA-{uuid4().hex[:8].upper()}"
        schedule = ScheduleOfAssessments(
            id=schedule_id,
            protocol_id=payload.protocol_id,
            visit_name=payload.visit_name,
            visit_number=payload.visit_number,
            day=payload.day,
            window_minus_days=payload.window_minus_days,
            window_plus_days=payload.window_plus_days,
            assessments=payload.assessments,
            mandatory=payload.mandatory,
            estimated_duration_minutes=payload.estimated_duration_minutes,
        )
        with self._lock:
            self._schedules[schedule_id] = schedule
        logger.info("Created schedule %s: %s", schedule_id, payload.visit_name)
        return schedule

    def update_schedule(
        self, schedule_id: str, payload: dict
    ) -> ScheduleOfAssessments | None:
        """Update a schedule of assessments entry from a dict of changes."""
        with self._lock:
            existing = self._schedules.get(schedule_id)
            if existing is None:
                return None
            data = existing.model_dump()
            data.update(payload)
            updated = ScheduleOfAssessments(**data)
            self._schedules[schedule_id] = updated
        return updated

    def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule of assessments entry. Returns True if deleted."""
        with self._lock:
            if schedule_id in self._schedules:
                del self._schedules[schedule_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Protocol Simulation CRUD
    # ------------------------------------------------------------------

    def list_simulations(
        self,
        *,
        protocol_id: str | None = None,
        status: SimulationStatus | None = None,
    ) -> list[ProtocolSimulation]:
        """List protocol simulations with optional filters."""
        with self._lock:
            result = list(self._simulations.values())

        if protocol_id is not None:
            result = [s for s in result if s.protocol_id == protocol_id]
        if status is not None:
            result = [s for s in result if s.status == status]

        return sorted(result, key=lambda s: s.id)

    def get_simulation(self, simulation_id: str) -> ProtocolSimulation | None:
        """Get a single protocol simulation by ID."""
        with self._lock:
            return self._simulations.get(simulation_id)

    def create_simulation(self, payload: ProtocolSimulationCreate) -> ProtocolSimulation:
        """Create a new protocol simulation."""
        simulation_id = f"SIM-{uuid4().hex[:8].upper()}"
        simulation = ProtocolSimulation(
            id=simulation_id,
            protocol_id=payload.protocol_id,
            simulation_name=payload.simulation_name,
            status=SimulationStatus.CONFIGURED,
            iterations=payload.iterations,
            enrollment_rate_per_month=payload.enrollment_rate_per_month,
            dropout_rate_pct=payload.dropout_rate_pct,
            effect_size=payload.effect_size,
            run_by=payload.run_by,
        )
        with self._lock:
            self._simulations[simulation_id] = simulation
        logger.info("Created simulation %s: %s", simulation_id, payload.simulation_name)
        return simulation

    def update_simulation(
        self, simulation_id: str, payload: ProtocolSimulationUpdate
    ) -> ProtocolSimulation | None:
        """Update a protocol simulation."""
        with self._lock:
            existing = self._simulations.get(simulation_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ProtocolSimulation(**data)
            self._simulations[simulation_id] = updated
        return updated

    def delete_simulation(self, simulation_id: str) -> bool:
        """Delete a protocol simulation. Returns True if deleted."""
        with self._lock:
            if simulation_id in self._simulations:
                del self._simulations[simulation_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self) -> ProtocolDesignMetrics:
        """Compute aggregated protocol design metrics."""
        with self._lock:
            protocols = list(self._protocols.values())
            endpoints = list(self._endpoints.values())
            sample_calcs = list(self._sample_calcs.values())
            schedules = list(self._schedules.values())
            simulations = list(self._simulations.values())

        # Protocols by phase
        protocols_by_phase: dict[str, int] = {}
        for p in protocols:
            key = p.phase.value
            protocols_by_phase[key] = protocols_by_phase.get(key, 0) + 1

        # Protocols by design
        protocols_by_design: dict[str, int] = {}
        for p in protocols:
            key = p.design_type.value
            protocols_by_design[key] = protocols_by_design.get(key, 0) + 1

        # Protocols by status
        protocols_by_status: dict[str, int] = {}
        for p in protocols:
            key = p.status.value
            protocols_by_status[key] = protocols_by_status.get(key, 0) + 1

        # Endpoints by category
        endpoints_by_category: dict[str, int] = {}
        for e in endpoints:
            key = e.category.value
            endpoints_by_category[key] = endpoints_by_category.get(key, 0) + 1

        # Average visit duration
        durations = [s.estimated_duration_minutes for s in schedules if s.estimated_duration_minutes > 0]
        avg_duration = round(sum(durations) / len(durations), 1) if durations else 0.0

        # Simulations by status
        sims_by_status: dict[str, int] = {}
        for s in simulations:
            key = s.status.value
            sims_by_status[key] = sims_by_status.get(key, 0) + 1

        # Average predicted power (completed simulations only)
        powers = [s.predicted_power for s in simulations if s.predicted_power is not None]
        avg_power = round(sum(powers) / len(powers), 4) if powers else None

        return ProtocolDesignMetrics(
            total_protocols=len(protocols),
            protocols_by_phase=protocols_by_phase,
            protocols_by_design=protocols_by_design,
            protocols_by_status=protocols_by_status,
            total_endpoints=len(endpoints),
            endpoints_by_category=endpoints_by_category,
            total_sample_calcs=len(sample_calcs),
            total_schedule_visits=len(schedules),
            avg_visit_duration_minutes=avg_duration,
            total_simulations=len(simulations),
            simulations_by_status=sims_by_status,
            avg_predicted_power=avg_power,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ProtocolDesignService | None = None
_instance_lock = threading.Lock()


def get_protocol_design_service() -> ProtocolDesignService:
    """Return the singleton ProtocolDesignService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ProtocolDesignService()
    return _instance


def reset_protocol_design_service() -> ProtocolDesignService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = ProtocolDesignService()
    return _instance
