"""Benefit-Risk Assessment Service (CLINICAL-8).

Manages structured benefit-risk assessments including assessment lifecycle
(draft -> in_review -> finalized -> superseded), benefit and risk outcome
quantification, multi-criteria frameworks, and aggregate metrics.

Usage:
    from app.services.benefit_risk_assessment_service import (
        get_benefit_risk_assessment_service,
    )

    svc = get_benefit_risk_assessment_service()
    assessments = svc.list_assessments()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.benefit_risk_assessment import (
    AssessmentCreate,
    AssessmentFramework,
    AssessmentStatus,
    AssessmentUpdate,
    BenefitOutcome,
    BenefitOutcomeCreate,
    BenefitOutcomeUpdate,
    BenefitRiskAssessment,
    BenefitRiskMetrics,
    LikelihoodLevel,
    OutcomeCategory,
    RiskOutcome,
    RiskOutcomeCreate,
    RiskOutcomeUpdate,
    SeverityLevel,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class BenefitRiskAssessmentService:
    """In-memory Benefit-Risk Assessment engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._assessments: dict[str, BenefitRiskAssessment] = {}
        self._benefits: dict[str, BenefitOutcome] = {}
        self._risks: dict[str, RiskOutcome] = {}
        self._lock = threading.Lock()
        self._next_assessment_number: dict[str, int] = {}
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic benefit-risk assessment data."""
        now = datetime.now(timezone.utc)

        # --- Assessment 1: Oncology (Libtayo - cemiplimab) ---
        self._assessments["BRA-001"] = BenefitRiskAssessment(
            id="BRA-001",
            trial_id=LIBTAYO_TRIAL,
            drug_name="Cemiplimab (Libtayo)",
            indication="Advanced cutaneous squamous cell carcinoma (CSCC)",
            comparator="Investigator's choice chemotherapy",
            assessment_number=1,
            version=1,
            status=AssessmentStatus.FINALIZED,
            framework=AssessmentFramework.FDA_BRF,
            assessor="Dr. Elena Rodriguez",
            assessment_date=now - timedelta(days=120),
            finalized_date=now - timedelta(days=90),
            overall_conclusion=(
                "The benefit-risk balance for cemiplimab in advanced CSCC is favorable. "
                "Durable tumor responses (ORR 47%) with manageable immune-related adverse "
                "events outweigh the risks. The unmet medical need in this population "
                "further supports a positive assessment."
            ),
            regulatory_context="Pre-NDA submission for advanced CSCC indication",
            target_population="Adults with metastatic or locally advanced CSCC not candidates for curative surgery or radiation",
        )
        self._next_assessment_number[LIBTAYO_TRIAL] = 2

        # Benefits for BRA-001 (Oncology)
        oncology_benefits = [
            {
                "id": "BEN-001",
                "assessment_id": "BRA-001",
                "outcome_name": "Overall Response Rate (ORR)",
                "category": OutcomeCategory.EFFICACY,
                "description": "Confirmed complete or partial tumor response per RECIST v1.1 criteria",
                "effect_size": 0.47,
                "confidence_interval": "0.38-0.56",
                "p_value": 0.0001,
                "clinical_significance": "Clinically meaningful response rate in a population with limited treatment options and historically poor outcomes",
                "severity": SeverityLevel.LIFE_THREATENING,
                "likelihood": LikelihoodLevel.COMMON,
                "weight": 4.0,
                "data_source": "Phase II pivotal trial (EMPOWER-CSCC-1)",
                "evidence_quality": "high",
            },
            {
                "id": "BEN-002",
                "assessment_id": "BRA-001",
                "outcome_name": "Duration of Response (DOR)",
                "category": OutcomeCategory.EFFICACY,
                "description": "Median duration of confirmed response; majority of responses ongoing at data cutoff",
                "effect_size": None,
                "confidence_interval": None,
                "p_value": None,
                "clinical_significance": "Durable responses with median DOR not reached; 68% of responders maintained response at 12 months",
                "severity": SeverityLevel.LIFE_THREATENING,
                "likelihood": LikelihoodLevel.COMMON,
                "weight": 3.5,
                "data_source": "Phase II pivotal trial (EMPOWER-CSCC-1)",
                "evidence_quality": "high",
            },
            {
                "id": "BEN-003",
                "assessment_id": "BRA-001",
                "outcome_name": "Overall Survival Improvement",
                "category": OutcomeCategory.EFFICACY,
                "description": "Improvement in overall survival compared to historical controls",
                "effect_size": 0.58,
                "confidence_interval": "0.42-0.79",
                "p_value": 0.0008,
                "clinical_significance": "Significant survival benefit with HR 0.58 compared to historical chemotherapy outcomes",
                "severity": SeverityLevel.FATAL,
                "likelihood": LikelihoodLevel.COMMON,
                "weight": 5.0,
                "data_source": "Phase II pivotal trial with historical comparator analysis",
                "evidence_quality": "moderate",
            },
            {
                "id": "BEN-004",
                "assessment_id": "BRA-001",
                "outcome_name": "Quality of Life Maintenance",
                "category": OutcomeCategory.QUALITY_OF_LIFE,
                "description": "Maintenance of health-related quality of life during treatment per EORTC QLQ-C30",
                "effect_size": None,
                "confidence_interval": None,
                "p_value": 0.032,
                "clinical_significance": "Patients maintained baseline QoL scores throughout treatment; no clinically meaningful deterioration",
                "severity": None,
                "likelihood": LikelihoodLevel.COMMON,
                "weight": 2.0,
                "data_source": "Phase II pivotal trial PRO substudy",
                "evidence_quality": "moderate",
            },
        ]
        for b in oncology_benefits:
            self._benefits[b["id"]] = BenefitOutcome(**b)

        # Risks for BRA-001 (Oncology)
        oncology_risks = [
            {
                "id": "RSK-001",
                "assessment_id": "BRA-001",
                "outcome_name": "Hepatotoxicity (Grade 3+)",
                "category": OutcomeCategory.SAFETY,
                "description": "Immune-mediated hepatitis with ALT/AST elevation >= 5x ULN requiring corticosteroid intervention",
                "incidence_rate": 2.8,
                "relative_risk": 3.2,
                "severity": SeverityLevel.SEVERE,
                "likelihood": LikelihoodLevel.UNCOMMON,
                "reversibility": "Reversible with corticosteroid therapy in 85% of cases; median time to resolution 6 weeks",
                "management_strategy": "Hepatic monitoring at baseline and every 2 weeks for 12 weeks, then monthly. Hold for Grade 2, discontinue for Grade 3+. High-dose corticosteroids per protocol.",
                "weight": 3.5,
                "data_source": "Phase II pivotal trial (EMPOWER-CSCC-1)",
            },
            {
                "id": "RSK-002",
                "assessment_id": "BRA-001",
                "outcome_name": "Immune-mediated Pneumonitis",
                "category": OutcomeCategory.SAFETY,
                "description": "Immune-mediated inflammation of lung parenchyma presenting as dyspnea, cough, and radiographic infiltrates",
                "incidence_rate": 3.5,
                "relative_risk": 4.1,
                "severity": SeverityLevel.LIFE_THREATENING,
                "likelihood": LikelihoodLevel.UNCOMMON,
                "reversibility": "Partially reversible; Grade 1-2 generally resolves; Grade 3+ may result in residual fibrosis",
                "management_strategy": "Chest CT at baseline. Hold for Grade 2, discontinue for Grade 3+. Systemic corticosteroids; consider infliximab for steroid-refractory cases.",
                "weight": 4.5,
                "data_source": "Phase II pivotal trial (EMPOWER-CSCC-1)",
            },
            {
                "id": "RSK-003",
                "assessment_id": "BRA-001",
                "outcome_name": "Hypothyroidism",
                "category": OutcomeCategory.TOLERABILITY,
                "description": "Immune-mediated thyroid dysfunction with elevated TSH requiring hormone replacement",
                "incidence_rate": 7.2,
                "relative_risk": 5.8,
                "severity": SeverityLevel.MILD,
                "likelihood": LikelihoodLevel.COMMON,
                "reversibility": "Irreversible in most cases; requires lifelong thyroid hormone replacement",
                "management_strategy": "TSH monitoring at baseline and every 6 weeks. Levothyroxine replacement for clinical hypothyroidism. Treatment continuation permitted.",
                "weight": 1.5,
                "data_source": "Phase II pivotal trial (EMPOWER-CSCC-1)",
            },
            {
                "id": "RSK-004",
                "assessment_id": "BRA-001",
                "outcome_name": "Infusion-related Reactions",
                "category": OutcomeCategory.TOLERABILITY,
                "description": "Systemic reactions during or within 24 hours of infusion including fever, chills, rigors, flushing",
                "incidence_rate": 9.1,
                "relative_risk": 2.5,
                "severity": SeverityLevel.MODERATE,
                "likelihood": LikelihoodLevel.COMMON,
                "reversibility": "Reversible with infusion interruption and supportive care",
                "management_strategy": "Pre-medication with acetaminophen and diphenhydramine. Reduce infusion rate for Grade 1-2. Discontinue for Grade 3+.",
                "weight": 1.0,
                "data_source": "Phase II pivotal trial (EMPOWER-CSCC-1)",
            },
        ]
        for r in oncology_risks:
            self._risks[r["id"]] = RiskOutcome(**r)

        # --- Assessment 2: Autoimmune (Dupixent - dupilumab) ---
        self._assessments["BRA-002"] = BenefitRiskAssessment(
            id="BRA-002",
            trial_id=DUPIXENT_TRIAL,
            drug_name="Dupilumab (Dupixent)",
            indication="Moderate-to-severe atopic dermatitis",
            comparator="Placebo",
            assessment_number=1,
            version=1,
            status=AssessmentStatus.FINALIZED,
            framework=AssessmentFramework.EMA_EFFECTS_TABLE,
            assessor="Dr. Michael Chen",
            assessment_date=now - timedelta(days=180),
            finalized_date=now - timedelta(days=150),
            overall_conclusion=(
                "Dupilumab demonstrates a strongly favorable benefit-risk profile in "
                "moderate-to-severe atopic dermatitis. EASI-75 response rates of 51% vs 15% "
                "placebo, combined with significant itch reduction, outweigh the manageable "
                "adverse event profile dominated by injection site reactions and conjunctivitis."
            ),
            regulatory_context="Post-marketing Type II variation for adolescent extension",
            target_population="Adults and adolescents (12+) with moderate-to-severe atopic dermatitis inadequately controlled by topical therapies",
        )
        self._next_assessment_number[DUPIXENT_TRIAL] = 2

        # Benefits for BRA-002 (Autoimmune)
        autoimmune_benefits = [
            {
                "id": "BEN-005",
                "assessment_id": "BRA-002",
                "outcome_name": "EASI-75 Response at Week 16",
                "category": OutcomeCategory.EFFICACY,
                "description": "Proportion of patients achieving >= 75% improvement in Eczema Area and Severity Index from baseline",
                "effect_size": 3.4,
                "confidence_interval": "2.6-4.5",
                "p_value": 0.00001,
                "clinical_significance": "Substantial and clinically meaningful skin clearance; 51% responders vs 15% placebo (OR 3.4)",
                "severity": SeverityLevel.MODERATE,
                "likelihood": LikelihoodLevel.COMMON,
                "weight": 4.0,
                "data_source": "Phase III LIBERTY AD SOLO 1 & SOLO 2 (pooled analysis)",
                "evidence_quality": "high",
            },
            {
                "id": "BEN-006",
                "assessment_id": "BRA-002",
                "outcome_name": "Pruritus NRS Improvement >= 4 Points",
                "category": OutcomeCategory.QUALITY_OF_LIFE,
                "description": "Clinically meaningful reduction in itch severity measured by peak pruritus Numerical Rating Scale",
                "effect_size": 2.8,
                "confidence_interval": "2.1-3.7",
                "p_value": 0.00003,
                "clinical_significance": "Rapid and sustained itch reduction; meaningful impact on sleep, daily function, and patient wellbeing",
                "severity": SeverityLevel.MODERATE,
                "likelihood": LikelihoodLevel.COMMON,
                "weight": 3.5,
                "data_source": "Phase III LIBERTY AD SOLO 1 & SOLO 2 (pooled analysis)",
                "evidence_quality": "high",
            },
            {
                "id": "BEN-007",
                "assessment_id": "BRA-002",
                "outcome_name": "DLQI Improvement >= 4 Points",
                "category": OutcomeCategory.QUALITY_OF_LIFE,
                "description": "Clinically meaningful improvement in Dermatology Life Quality Index at Week 16",
                "effect_size": 2.5,
                "confidence_interval": "1.9-3.3",
                "p_value": 0.0001,
                "clinical_significance": "Meaningful quality of life improvement across multiple domains including symptoms, daily activities, and emotional wellbeing",
                "severity": None,
                "likelihood": LikelihoodLevel.COMMON,
                "weight": 2.5,
                "data_source": "Phase III LIBERTY AD SOLO 1 & SOLO 2 (pooled analysis)",
                "evidence_quality": "high",
            },
            {
                "id": "BEN-008",
                "assessment_id": "BRA-002",
                "outcome_name": "Reduction in Topical Corticosteroid Use",
                "category": OutcomeCategory.CONVENIENCE,
                "description": "Decrease in concomitant topical corticosteroid requirement over 52 weeks",
                "effect_size": None,
                "confidence_interval": None,
                "p_value": 0.002,
                "clinical_significance": "50% reduction in TCS use vs 18% for placebo; reduces long-term steroid side effect burden",
                "severity": None,
                "likelihood": LikelihoodLevel.COMMON,
                "weight": 2.0,
                "data_source": "Phase III LIBERTY AD CHRONOS (52-week data)",
                "evidence_quality": "high",
            },
        ]
        for b in autoimmune_benefits:
            self._benefits[b["id"]] = BenefitOutcome(**b)

        # Risks for BRA-002 (Autoimmune)
        autoimmune_risks = [
            {
                "id": "RSK-005",
                "assessment_id": "BRA-002",
                "outcome_name": "Injection Site Reactions",
                "category": OutcomeCategory.TOLERABILITY,
                "description": "Local reactions at subcutaneous injection site including erythema, edema, pruritus, and pain",
                "incidence_rate": 15.3,
                "relative_risk": 2.1,
                "severity": SeverityLevel.MILD,
                "likelihood": LikelihoodLevel.VERY_COMMON,
                "reversibility": "Reversible; typically resolves within 3-5 days without intervention",
                "management_strategy": "Rotate injection sites. Apply cold pack before injection. Topical corticosteroid for persistent reactions. Generally self-limiting.",
                "weight": 1.0,
                "data_source": "Phase III LIBERTY AD SOLO 1 & SOLO 2 (pooled analysis)",
            },
            {
                "id": "RSK-006",
                "assessment_id": "BRA-002",
                "outcome_name": "Conjunctivitis",
                "category": OutcomeCategory.SAFETY,
                "description": "New onset or exacerbation of conjunctivitis, including allergic, bacterial, and non-specific forms",
                "incidence_rate": 9.8,
                "relative_risk": 3.4,
                "severity": SeverityLevel.MODERATE,
                "likelihood": LikelihoodLevel.COMMON,
                "reversibility": "Reversible with appropriate ophthalmologic treatment in most cases",
                "management_strategy": "Ophthalmology referral for Grade 2+. Artificial tears for mild cases. Topical anti-inflammatory for moderate cases. Treatment continuation with monitoring.",
                "weight": 2.5,
                "data_source": "Phase III LIBERTY AD SOLO 1 & SOLO 2 (pooled analysis)",
            },
            {
                "id": "RSK-007",
                "assessment_id": "BRA-002",
                "outcome_name": "Herpes Viral Infections",
                "category": OutcomeCategory.SAFETY,
                "description": "Oral herpes, herpes simplex, and eczema herpeticum events",
                "incidence_rate": 3.8,
                "relative_risk": 1.8,
                "severity": SeverityLevel.MODERATE,
                "likelihood": LikelihoodLevel.UNCOMMON,
                "reversibility": "Reversible with antiviral therapy",
                "management_strategy": "Monitor for herpetic lesions. Prompt antiviral therapy (acyclovir/valacyclovir). Consider prophylaxis in patients with recurrent history.",
                "weight": 2.0,
                "data_source": "Phase III LIBERTY AD SOLO 1 & SOLO 2 (pooled analysis)",
            },
            {
                "id": "RSK-008",
                "assessment_id": "BRA-002",
                "outcome_name": "Eosinophilia",
                "category": OutcomeCategory.SAFETY,
                "description": "Treatment-emergent eosinophilia (blood eosinophil count >= 5000 cells/mcL)",
                "incidence_rate": 1.2,
                "relative_risk": 2.9,
                "severity": SeverityLevel.MILD,
                "likelihood": LikelihoodLevel.UNCOMMON,
                "reversibility": "Reversible; eosinophil counts typically normalize after treatment discontinuation",
                "management_strategy": "CBC monitoring at baseline and periodically. Evaluate for eosinophilic conditions if counts > 10,000. Generally transient and not associated with clinical symptoms.",
                "weight": 1.5,
                "data_source": "Phase III LIBERTY AD SOLO 1 & SOLO 2 (pooled analysis)",
            },
        ]
        for r in autoimmune_risks:
            self._risks[r["id"]] = RiskOutcome(**r)

        # --- Assessment 3: Ophthalmology (Eylea - aflibercept) - Draft ---
        self._assessments["BRA-003"] = BenefitRiskAssessment(
            id="BRA-003",
            trial_id=EYLEA_TRIAL,
            drug_name="Aflibercept (Eylea)",
            indication="Neovascular (wet) age-related macular degeneration",
            comparator="Ranibizumab (Lucentis)",
            assessment_number=1,
            version=1,
            status=AssessmentStatus.DRAFT,
            framework=AssessmentFramework.MCDA,
            assessor="Dr. Sarah Kim",
            assessment_date=now - timedelta(days=14),
            finalized_date=None,
            overall_conclusion=None,
            regulatory_context="Supplemental BLA for extended dosing interval (q12w)",
            target_population="Adults with neovascular AMD requiring anti-VEGF therapy",
        )
        self._next_assessment_number[EYLEA_TRIAL] = 2

        # Benefits for BRA-003 (Ophthalmology)
        ophtho_benefits = [
            {
                "id": "BEN-009",
                "assessment_id": "BRA-003",
                "outcome_name": "Best-Corrected Visual Acuity (BCVA) Gain",
                "category": OutcomeCategory.EFFICACY,
                "description": "Mean change from baseline in BCVA (ETDRS letters) at Week 52",
                "effect_size": -0.32,
                "confidence_interval": "-1.87 to 1.23",
                "p_value": None,
                "clinical_significance": "Non-inferior to ranibizumab with mean gain of 8.4 letters vs 8.7 letters; difference within pre-specified non-inferiority margin",
                "severity": SeverityLevel.SEVERE,
                "likelihood": LikelihoodLevel.VERY_COMMON,
                "weight": 5.0,
                "data_source": "Phase III VIEW 1 & VIEW 2 (pooled analysis)",
                "evidence_quality": "high",
            },
            {
                "id": "BEN-010",
                "assessment_id": "BRA-003",
                "outcome_name": "Extended Dosing Interval",
                "category": OutcomeCategory.CONVENIENCE,
                "description": "Ability to maintain visual gains with every-8-week dosing after initial monthly loading phase",
                "effect_size": None,
                "confidence_interval": None,
                "p_value": None,
                "clinical_significance": "Reduced treatment burden: 7 injections in year 1 vs 13 for monthly ranibizumab; significant reduction in clinic visits and caregiver burden",
                "severity": None,
                "likelihood": LikelihoodLevel.VERY_COMMON,
                "weight": 3.0,
                "data_source": "Phase III VIEW 1 & VIEW 2 (pooled analysis)",
                "evidence_quality": "high",
            },
        ]
        for b in ophtho_benefits:
            self._benefits[b["id"]] = BenefitOutcome(**b)

        # Risks for BRA-003 (Ophthalmology)
        ophtho_risks = [
            {
                "id": "RSK-009",
                "assessment_id": "BRA-003",
                "outcome_name": "Endophthalmitis",
                "category": OutcomeCategory.SAFETY,
                "description": "Intraocular infection following intravitreal injection",
                "incidence_rate": 0.05,
                "relative_risk": 1.1,
                "severity": SeverityLevel.LIFE_THREATENING,
                "likelihood": LikelihoodLevel.VERY_RARE,
                "reversibility": "Partially reversible; may result in permanent vision loss if not promptly treated",
                "management_strategy": "Strict aseptic technique. Post-injection monitoring for 2-7 days. Emergent intravitreal antibiotics if suspected. Vitrectomy in severe cases.",
                "weight": 5.0,
                "data_source": "Phase III VIEW 1 & VIEW 2 (pooled analysis)",
            },
            {
                "id": "RSK-010",
                "assessment_id": "BRA-003",
                "outcome_name": "Increased Intraocular Pressure",
                "category": OutcomeCategory.SAFETY,
                "description": "Transient or sustained elevation in intraocular pressure following injection",
                "incidence_rate": 3.9,
                "relative_risk": 1.3,
                "severity": SeverityLevel.MODERATE,
                "likelihood": LikelihoodLevel.UNCOMMON,
                "reversibility": "Reversible; transient elevations resolve within 30-60 minutes; sustained elevations manageable with topical IOP-lowering agents",
                "management_strategy": "IOP check at each visit. Topical timolol for sustained elevation. Anterior chamber paracentesis for acute IOP spikes > 40 mmHg.",
                "weight": 2.0,
                "data_source": "Phase III VIEW 1 & VIEW 2 (pooled analysis)",
            },
        ]
        for r in ophtho_risks:
            self._risks[r["id"]] = RiskOutcome(**r)

        # --- Assessment 4: Superseded (older Dupixent assessment) ---
        self._assessments["BRA-004"] = BenefitRiskAssessment(
            id="BRA-004",
            trial_id=DUPIXENT_TRIAL,
            drug_name="Dupilumab (Dupixent)",
            indication="Moderate-to-severe atopic dermatitis",
            comparator="Placebo",
            assessment_number=2,
            version=1,
            status=AssessmentStatus.SUPERSEDED,
            framework=AssessmentFramework.EMA_EFFECTS_TABLE,
            assessor="Dr. Michael Chen",
            assessment_date=now - timedelta(days=365),
            finalized_date=now - timedelta(days=330),
            overall_conclusion=(
                "Initial assessment based on interim data. Favorable benefit-risk profile "
                "observed; updated assessment planned with final study data."
            ),
            regulatory_context="Initial MAA assessment",
            target_population="Adults with moderate-to-severe atopic dermatitis",
        )
        self._next_assessment_number[DUPIXENT_TRIAL] = 3

        # --- Assessment 5: In-review (Libtayo lung cancer) ---
        self._assessments["BRA-005"] = BenefitRiskAssessment(
            id="BRA-005",
            trial_id=LIBTAYO_TRIAL,
            drug_name="Cemiplimab (Libtayo)",
            indication="Advanced non-small cell lung cancer (NSCLC) with PD-L1 >= 50%",
            comparator="Platinum-doublet chemotherapy",
            assessment_number=2,
            version=1,
            status=AssessmentStatus.IN_REVIEW,
            framework=AssessmentFramework.PROACT_URL,
            assessor="Dr. James Williams",
            assessment_date=now - timedelta(days=30),
            finalized_date=None,
            overall_conclusion=None,
            regulatory_context="Supplemental BLA for first-line NSCLC monotherapy",
            target_population="Adults with advanced NSCLC, PD-L1 TPS >= 50%, no EGFR/ALK/ROS1 alterations",
        )
        self._next_assessment_number[LIBTAYO_TRIAL] = 3

        # Benefits for BRA-005 (NSCLC)
        nsclc_benefits = [
            {
                "id": "BEN-011",
                "assessment_id": "BRA-005",
                "outcome_name": "Overall Survival (OS)",
                "category": OutcomeCategory.EFFICACY,
                "description": "Improvement in overall survival compared to platinum-doublet chemotherapy",
                "effect_size": 0.57,
                "confidence_interval": "0.42-0.77",
                "p_value": 0.0002,
                "clinical_significance": "Significant 43% reduction in risk of death; median OS 22.1 vs 14.3 months",
                "severity": SeverityLevel.FATAL,
                "likelihood": LikelihoodLevel.COMMON,
                "weight": 5.0,
                "data_source": "Phase III EMPOWER-Lung 1",
                "evidence_quality": "high",
            },
            {
                "id": "BEN-012",
                "assessment_id": "BRA-005",
                "outcome_name": "Progression-Free Survival (PFS)",
                "category": OutcomeCategory.EFFICACY,
                "description": "Improvement in progression-free survival per BICR assessment",
                "effect_size": 0.54,
                "confidence_interval": "0.43-0.68",
                "p_value": 0.00001,
                "clinical_significance": "Significant 46% reduction in risk of progression or death; median PFS 8.2 vs 5.7 months",
                "severity": SeverityLevel.LIFE_THREATENING,
                "likelihood": LikelihoodLevel.COMMON,
                "weight": 4.0,
                "data_source": "Phase III EMPOWER-Lung 1",
                "evidence_quality": "high",
            },
        ]
        for b in nsclc_benefits:
            self._benefits[b["id"]] = BenefitOutcome(**b)

        # Risks for BRA-005 (NSCLC)
        nsclc_risks = [
            {
                "id": "RSK-011",
                "assessment_id": "BRA-005",
                "outcome_name": "Immune-mediated Colitis",
                "category": OutcomeCategory.SAFETY,
                "description": "Immune-mediated colitis/diarrhea with risk of bowel perforation",
                "incidence_rate": 4.2,
                "relative_risk": 3.8,
                "severity": SeverityLevel.SEVERE,
                "likelihood": LikelihoodLevel.UNCOMMON,
                "reversibility": "Reversible in most cases with immunosuppressive therapy",
                "management_strategy": "Monitor for diarrhea, abdominal pain. Hold for Grade 2-3, discontinue for Grade 4. High-dose corticosteroids; infliximab for steroid-refractory cases.",
                "weight": 3.0,
                "data_source": "Phase III EMPOWER-Lung 1",
            },
            {
                "id": "RSK-012",
                "assessment_id": "BRA-005",
                "outcome_name": "Immune-mediated Nephritis",
                "category": OutcomeCategory.SAFETY,
                "description": "Immune-mediated renal injury with elevated creatinine",
                "incidence_rate": 1.5,
                "relative_risk": 2.8,
                "severity": SeverityLevel.SEVERE,
                "likelihood": LikelihoodLevel.RARE,
                "reversibility": "Partially reversible; some patients may not recover full renal function",
                "management_strategy": "Serum creatinine monitoring at baseline and periodically. Hold for Grade 2, discontinue for Grade 3+. Corticosteroids per protocol.",
                "weight": 3.5,
                "data_source": "Phase III EMPOWER-Lung 1",
            },
        ]
        for r in nsclc_risks:
            self._risks[r["id"]] = RiskOutcome(**r)

    # ------------------------------------------------------------------
    # Assessment CRUD
    # ------------------------------------------------------------------

    def list_assessments(
        self,
        *,
        trial_id: str | None = None,
        status: AssessmentStatus | None = None,
        framework: AssessmentFramework | None = None,
        drug_name: str | None = None,
    ) -> list[BenefitRiskAssessment]:
        """List assessments with optional filters."""
        with self._lock:
            result = list(self._assessments.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if status is not None:
            result = [a for a in result if a.status == status]
        if framework is not None:
            result = [a for a in result if a.framework == framework]
        if drug_name is not None:
            result = [a for a in result if drug_name.lower() in a.drug_name.lower()]

        return sorted(result, key=lambda a: a.assessment_date, reverse=True)

    def get_assessment(self, assessment_id: str) -> BenefitRiskAssessment | None:
        """Get a single assessment by ID."""
        with self._lock:
            return self._assessments.get(assessment_id)

    def create_assessment(self, payload: AssessmentCreate) -> BenefitRiskAssessment:
        """Create a new assessment in draft status."""
        now = datetime.now(timezone.utc)
        assessment_id = f"BRA-{uuid4().hex[:8].upper()}"

        with self._lock:
            # Determine assessment number for this trial
            num = self._next_assessment_number.get(payload.trial_id, 1)
            self._next_assessment_number[payload.trial_id] = num + 1

            assessment = BenefitRiskAssessment(
                id=assessment_id,
                trial_id=payload.trial_id,
                drug_name=payload.drug_name,
                indication=payload.indication,
                comparator=payload.comparator,
                assessment_number=num,
                version=1,
                status=AssessmentStatus.DRAFT,
                framework=payload.framework,
                assessor=payload.assessor,
                assessment_date=now,
                finalized_date=None,
                overall_conclusion=payload.overall_conclusion,
                regulatory_context=payload.regulatory_context,
                target_population=payload.target_population,
            )
            self._assessments[assessment_id] = assessment

        logger.info("Created assessment %s: %s for %s", assessment_id, payload.drug_name, payload.indication)
        return assessment

    def update_assessment(
        self, assessment_id: str, payload: AssessmentUpdate
    ) -> BenefitRiskAssessment | None:
        """Update an existing assessment. Only draft/in_review assessments can be updated."""
        with self._lock:
            existing = self._assessments.get(assessment_id)
            if existing is None:
                return None

            if existing.status in (AssessmentStatus.FINALIZED, AssessmentStatus.SUPERSEDED):
                raise ValueError(
                    f"Cannot update assessment '{assessment_id}' with status '{existing.status.value}'"
                )

            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = BenefitRiskAssessment(**data)
            self._assessments[assessment_id] = updated

        return updated

    def delete_assessment(self, assessment_id: str) -> bool:
        """Delete an assessment and its associated outcomes. Only draft assessments can be deleted."""
        with self._lock:
            existing = self._assessments.get(assessment_id)
            if existing is None:
                return False

            if existing.status != AssessmentStatus.DRAFT:
                raise ValueError(
                    f"Cannot delete assessment '{assessment_id}' with status '{existing.status.value}'. "
                    "Only draft assessments can be deleted."
                )

            del self._assessments[assessment_id]
            # Remove associated benefits and risks
            self._benefits = {
                k: v for k, v in self._benefits.items() if v.assessment_id != assessment_id
            }
            self._risks = {
                k: v for k, v in self._risks.items() if v.assessment_id != assessment_id
            }

        logger.info("Deleted assessment %s", assessment_id)
        return True

    def finalize_assessment(self, assessment_id: str) -> BenefitRiskAssessment | None:
        """Finalize a draft or in-review assessment."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._assessments.get(assessment_id)
            if existing is None:
                return None

            if existing.status not in (AssessmentStatus.DRAFT, AssessmentStatus.IN_REVIEW):
                raise ValueError(
                    f"Cannot finalize assessment '{assessment_id}' with status '{existing.status.value}'. "
                    "Only draft or in_review assessments can be finalized."
                )

            data = existing.model_dump()
            data["status"] = AssessmentStatus.FINALIZED
            data["finalized_date"] = now
            updated = BenefitRiskAssessment(**data)
            self._assessments[assessment_id] = updated

        logger.info("Finalized assessment %s", assessment_id)
        return updated

    def supersede_assessment(self, assessment_id: str) -> BenefitRiskAssessment | None:
        """Mark a finalized assessment as superseded."""
        with self._lock:
            existing = self._assessments.get(assessment_id)
            if existing is None:
                return None

            if existing.status != AssessmentStatus.FINALIZED:
                raise ValueError(
                    f"Cannot supersede assessment '{assessment_id}' with status '{existing.status.value}'. "
                    "Only finalized assessments can be superseded."
                )

            data = existing.model_dump()
            data["status"] = AssessmentStatus.SUPERSEDED
            updated = BenefitRiskAssessment(**data)
            self._assessments[assessment_id] = updated

        logger.info("Superseded assessment %s", assessment_id)
        return updated

    # ------------------------------------------------------------------
    # Benefit Outcomes
    # ------------------------------------------------------------------

    def list_benefits(self, assessment_id: str) -> list[BenefitOutcome]:
        """List benefit outcomes for an assessment."""
        with self._lock:
            result = [
                b for b in self._benefits.values()
                if b.assessment_id == assessment_id
            ]
        return sorted(result, key=lambda b: b.weight, reverse=True)

    def get_benefit(self, benefit_id: str) -> BenefitOutcome | None:
        """Get a single benefit outcome by ID."""
        with self._lock:
            return self._benefits.get(benefit_id)

    def create_benefit(
        self, assessment_id: str, payload: BenefitOutcomeCreate
    ) -> BenefitOutcome:
        """Create a benefit outcome for an assessment."""
        benefit_id = f"BEN-{uuid4().hex[:8].upper()}"
        benefit = BenefitOutcome(
            id=benefit_id,
            assessment_id=assessment_id,
            **payload.model_dump(),
        )
        with self._lock:
            self._benefits[benefit_id] = benefit
        logger.info("Created benefit %s for assessment %s", benefit_id, assessment_id)
        return benefit

    def update_benefit(
        self, benefit_id: str, payload: BenefitOutcomeUpdate
    ) -> BenefitOutcome | None:
        """Update a benefit outcome."""
        with self._lock:
            existing = self._benefits.get(benefit_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = BenefitOutcome(**data)
            self._benefits[benefit_id] = updated
        return updated

    def delete_benefit(self, benefit_id: str) -> bool:
        """Delete a benefit outcome."""
        with self._lock:
            if benefit_id in self._benefits:
                del self._benefits[benefit_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Risk Outcomes
    # ------------------------------------------------------------------

    def list_risks(self, assessment_id: str) -> list[RiskOutcome]:
        """List risk outcomes for an assessment."""
        with self._lock:
            result = [
                r for r in self._risks.values()
                if r.assessment_id == assessment_id
            ]
        return sorted(result, key=lambda r: r.weight, reverse=True)

    def get_risk(self, risk_id: str) -> RiskOutcome | None:
        """Get a single risk outcome by ID."""
        with self._lock:
            return self._risks.get(risk_id)

    def create_risk(
        self, assessment_id: str, payload: RiskOutcomeCreate
    ) -> RiskOutcome:
        """Create a risk outcome for an assessment."""
        risk_id = f"RSK-{uuid4().hex[:8].upper()}"
        risk = RiskOutcome(
            id=risk_id,
            assessment_id=assessment_id,
            **payload.model_dump(),
        )
        with self._lock:
            self._risks[risk_id] = risk
        logger.info("Created risk %s for assessment %s", risk_id, assessment_id)
        return risk

    def update_risk(
        self, risk_id: str, payload: RiskOutcomeUpdate
    ) -> RiskOutcome | None:
        """Update a risk outcome."""
        with self._lock:
            existing = self._risks.get(risk_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = RiskOutcome(**data)
            self._risks[risk_id] = updated
        return updated

    def delete_risk(self, risk_id: str) -> bool:
        """Delete a risk outcome."""
        with self._lock:
            if risk_id in self._risks:
                del self._risks[risk_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> BenefitRiskMetrics:
        """Compute aggregated benefit-risk assessment metrics."""
        with self._lock:
            assessments = list(self._assessments.values())
            benefits = list(self._benefits.values())
            risks = list(self._risks.values())

        # Counts by status
        by_status: dict[str, int] = {}
        for a in assessments:
            key = a.status.value
            by_status[key] = by_status.get(key, 0) + 1

        # Counts by framework
        by_framework: dict[str, int] = {}
        for a in assessments:
            key = a.framework.value
            by_framework[key] = by_framework.get(key, 0) + 1

        total = len(assessments)
        total_benefits = len(benefits)
        total_risks = len(risks)
        avg_benefits = round(total_benefits / max(1, total), 1)
        avg_risks = round(total_risks / max(1, total), 1)
        finalized = sum(1 for a in assessments if a.status == AssessmentStatus.FINALIZED)
        superseded = sum(1 for a in assessments if a.status == AssessmentStatus.SUPERSEDED)

        return BenefitRiskMetrics(
            total_assessments=total,
            assessments_by_status=by_status,
            assessments_by_framework=by_framework,
            total_benefit_outcomes=total_benefits,
            total_risk_outcomes=total_risks,
            avg_benefits_per_assessment=avg_benefits,
            avg_risks_per_assessment=avg_risks,
            finalized_assessments=finalized,
            superseded_assessments=superseded,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: BenefitRiskAssessmentService | None = None
_lock = threading.Lock()


def get_benefit_risk_assessment_service() -> BenefitRiskAssessmentService:
    """Return the singleton BenefitRiskAssessmentService instance."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = BenefitRiskAssessmentService()
    return _instance


def reset_benefit_risk_assessment_service() -> BenefitRiskAssessmentService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _lock:
        _instance = BenefitRiskAssessmentService()
    return _instance
