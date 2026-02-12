"""Real-World Evidence (RWE) Integration & Analysis Service.

Manages real-world data sources, RWE studies, outcome tracking, comparative
effectiveness analyses, health economic evaluations, and regulatory submission
packages for RWE data.

Usage:
    from app.services.real_world_evidence_service import (
        get_rwe_service,
    )

    svc = get_rwe_service()
    studies = svc.list_studies()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from collections import Counter
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.real_world_evidence import (
    AnalysisStatus,
    ComparativeEffectiveness,
    ComparativeEffectivenessCreate,
    ComparativeEffectivenessUpdate,
    DataSourceType,
    EvidenceGrade,
    HealthEconomicAnalysis,
    HealthEconomicAnalysisCreate,
    HealthEconomicAnalysisUpdate,
    OutcomeType,
    RWEDataSource,
    RWEDataSourceCreate,
    RWEDataSourceUpdate,
    RWEMetrics,
    RWEStudy,
    RWEStudyCreate,
    RWEStudyUpdate,
    RWESubmissionPackage,
    RWESubmissionPackageCreate,
    RWESubmissionPackageUpdate,
    RealWorldOutcome,
    RealWorldOutcomeCreate,
    RealWorldOutcomeUpdate,
    StudyDesign,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class RWEService:
    """In-memory Real-World Evidence engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._data_sources: dict[str, RWEDataSource] = {}
        self._studies: dict[str, RWEStudy] = {}
        self._outcomes: dict[str, RealWorldOutcome] = {}
        self._comparative: dict[str, ComparativeEffectiveness] = {}
        self._health_econ: dict[str, HealthEconomicAnalysis] = {}
        self._submissions: dict[str, RWESubmissionPackage] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic RWE data."""
        now = datetime.now(timezone.utc)

        # --- 4 Data Sources ---
        ds_data = [
            {
                "id": "DS-001",
                "name": "Optum Clinformatics Extended DOD",
                "data_source_type": DataSourceType.CLAIMS,
                "description": "De-identified administrative health claims for members of large commercial and Medicare Advantage health plans",
                "patient_count": 84_000_000,
                "date_range_start": now - timedelta(days=3650),
                "date_range_end": now - timedelta(days=90),
                "geographic_coverage": ["United States"],
                "data_elements": ["diagnoses", "procedures", "pharmacy_claims", "lab_results", "enrollment"],
                "refresh_frequency": "quarterly",
                "data_lag_days": 90,
                "quality_score": 88.5,
                "vendor": "Optum",
                "contract_id": "OPT-2025-RWE-001",
            },
            {
                "id": "DS-002",
                "name": "Flatiron Health Oncology EHR",
                "data_source_type": DataSourceType.EHR,
                "description": "Curated electronic health record data from 280+ oncology clinics across the US",
                "patient_count": 3_200_000,
                "date_range_start": now - timedelta(days=2555),
                "date_range_end": now - timedelta(days=30),
                "geographic_coverage": ["United States"],
                "data_elements": ["diagnoses", "treatments", "biomarkers", "progression", "mortality", "genomics"],
                "refresh_frequency": "monthly",
                "data_lag_days": 30,
                "quality_score": 92.0,
                "vendor": "Flatiron Health",
                "contract_id": "FH-2025-ONC-002",
            },
            {
                "id": "DS-003",
                "name": "IQVIA PharMetrics Plus",
                "data_source_type": DataSourceType.CLAIMS,
                "description": "Adjudicated health plan claims data from managed care plans covering all US census regions",
                "patient_count": 150_000_000,
                "date_range_start": now - timedelta(days=5475),
                "date_range_end": now - timedelta(days=120),
                "geographic_coverage": ["United States"],
                "data_elements": ["diagnoses", "procedures", "pharmacy_claims", "enrollment", "provider_specialty"],
                "refresh_frequency": "quarterly",
                "data_lag_days": 120,
                "quality_score": 85.0,
                "vendor": "IQVIA",
                "contract_id": "IQV-2025-PM-003",
            },
            {
                "id": "DS-004",
                "name": "UK Biobank Registry",
                "data_source_type": DataSourceType.REGISTRY,
                "description": "Prospective cohort study with deep phenotyping and genotyping of 500,000 UK participants",
                "patient_count": 500_000,
                "date_range_start": now - timedelta(days=6570),
                "date_range_end": now - timedelta(days=60),
                "geographic_coverage": ["United Kingdom"],
                "data_elements": ["demographics", "biomarkers", "imaging", "genomics", "linked_EHR", "mortality"],
                "refresh_frequency": "annually",
                "data_lag_days": 180,
                "quality_score": 95.0,
                "vendor": "UK Biobank",
                "contract_id": "UKB-2024-REG-001",
            },
        ]

        for ds in ds_data:
            self._data_sources[ds["id"]] = RWEDataSource(**ds)

        # --- 4 Studies ---
        studies_data = [
            {
                "id": "RWE-STUDY-001",
                "trial_id": EYLEA_TRIAL,
                "study_name": "EYLEA Real-World Effectiveness in nAMD: 24-Month Outcomes",
                "study_design": StudyDesign.RETROSPECTIVE_COHORT,
                "indication": "Neovascular age-related macular degeneration (nAMD)",
                "comparator": "Ranibizumab (Lucentis)",
                "primary_endpoint": "Mean change in visual acuity at 24 months",
                "secondary_endpoints": [
                    "Treatment persistence at 12 months",
                    "Mean number of injections at 24 months",
                    "Proportion achieving 20/40 or better",
                ],
                "target_population": "Treatment-naive nAMD patients aged 50+ initiating anti-VEGF therapy",
                "sample_size": 45_200,
                "status": AnalysisStatus.PUBLISHED,
                "start_date": now - timedelta(days=730),
                "completion_date": now - timedelta(days=90),
                "lead_analyst": "Dr. Sarah Chen",
                "protocol_document": "PROT-RWE-001-v2.0",
            },
            {
                "id": "RWE-STUDY-002",
                "trial_id": DUPIXENT_TRIAL,
                "study_name": "DUPIXENT Comparative Effectiveness in Moderate-to-Severe Atopic Dermatitis",
                "study_design": StudyDesign.PROSPECTIVE_COHORT,
                "indication": "Moderate-to-severe atopic dermatitis",
                "comparator": "Systemic immunosuppressants (methotrexate, cyclosporine)",
                "primary_endpoint": "EASI-75 response at 16 weeks",
                "secondary_endpoints": [
                    "DLQI improvement from baseline",
                    "Corticosteroid-free days",
                    "Infection rate requiring antibiotics",
                ],
                "target_population": "Adults with moderate-to-severe AD inadequately controlled by topical therapies",
                "sample_size": 12_800,
                "status": AnalysisStatus.ANALYSIS,
                "start_date": now - timedelta(days=365),
                "completion_date": None,
                "lead_analyst": "Dr. Michael Torres",
                "protocol_document": "PROT-RWE-002-v1.3",
            },
            {
                "id": "RWE-STUDY-003",
                "trial_id": LIBTAYO_TRIAL,
                "study_name": "LIBTAYO Health Economic Impact in Advanced CSCC",
                "study_design": StudyDesign.RETROSPECTIVE_COHORT,
                "indication": "Advanced cutaneous squamous cell carcinoma (CSCC)",
                "comparator": "Platinum-based chemotherapy",
                "primary_endpoint": "Overall survival at 24 months",
                "secondary_endpoints": [
                    "Progression-free survival",
                    "Healthcare resource utilization",
                    "Total cost of care",
                ],
                "target_population": "Adults with locally advanced or metastatic CSCC not candidates for surgery or radiation",
                "sample_size": 3_400,
                "status": AnalysisStatus.PEER_REVIEW,
                "start_date": now - timedelta(days=545),
                "completion_date": now - timedelta(days=30),
                "lead_analyst": "Dr. Emily Rodriguez",
                "protocol_document": "PROT-RWE-003-v1.1",
            },
            {
                "id": "RWE-STUDY-004",
                "trial_id": EYLEA_TRIAL,
                "study_name": "EYLEA Diabetic Macular Edema Registry Study",
                "study_design": StudyDesign.PROSPECTIVE_COHORT,
                "indication": "Diabetic macular edema (DME)",
                "comparator": "Bevacizumab (Avastin)",
                "primary_endpoint": "Central retinal thickness change at 12 months",
                "secondary_endpoints": [
                    "Visual acuity change at 12 months",
                    "Treatment burden (injection frequency)",
                    "Patient-reported visual function",
                ],
                "target_population": "Adults with center-involving DME and BCVA 20/32 to 20/320",
                "sample_size": 8_500,
                "status": AnalysisStatus.DATA_COLLECTION,
                "start_date": now - timedelta(days=180),
                "completion_date": None,
                "lead_analyst": "Dr. James Park",
                "protocol_document": "PROT-RWE-004-v1.0",
            },
        ]

        for s in studies_data:
            self._studies[s["id"]] = RWEStudy(**s)

        # --- 8 Outcomes ---
        outcomes_data = [
            {
                "id": "OUT-001",
                "study_id": "RWE-STUDY-001",
                "outcome_type": OutcomeType.EFFECTIVENESS,
                "outcome_name": "Mean visual acuity change at 24 months",
                "measurement_method": "ETDRS letter score change from baseline",
                "timepoint": "24 months",
                "result_value": 8.2,
                "confidence_interval_lower": 7.5,
                "confidence_interval_upper": 8.9,
                "p_value": 0.001,
                "clinical_significance": "Clinically meaningful improvement exceeding 5-letter MCID",
                "evidence_grade": EvidenceGrade.MODERATE,
                "population_size": 42_100,
            },
            {
                "id": "OUT-002",
                "study_id": "RWE-STUDY-001",
                "outcome_type": OutcomeType.EFFECTIVENESS,
                "outcome_name": "Treatment persistence at 12 months",
                "measurement_method": "Proportion of patients continuing treatment at 12 months",
                "timepoint": "12 months",
                "result_value": 72.3,
                "confidence_interval_lower": 70.8,
                "confidence_interval_upper": 73.8,
                "p_value": 0.003,
                "clinical_significance": "Higher persistence vs comparator indicating better tolerability",
                "evidence_grade": EvidenceGrade.MODERATE,
                "population_size": 45_200,
            },
            {
                "id": "OUT-003",
                "study_id": "RWE-STUDY-001",
                "outcome_type": OutcomeType.SAFETY,
                "outcome_name": "Endophthalmitis incidence per injection",
                "measurement_method": "Rate of endophthalmitis events per 10,000 intravitreal injections",
                "timepoint": "24 months",
                "result_value": 2.1,
                "confidence_interval_lower": 1.4,
                "confidence_interval_upper": 2.8,
                "p_value": 0.45,
                "clinical_significance": "Comparable safety profile to controlled trial data",
                "evidence_grade": EvidenceGrade.HIGH,
                "population_size": 42_100,
            },
            {
                "id": "OUT-004",
                "study_id": "RWE-STUDY-002",
                "outcome_type": OutcomeType.EFFECTIVENESS,
                "outcome_name": "EASI-75 response at 16 weeks",
                "measurement_method": "Proportion achieving 75% reduction in EASI score",
                "timepoint": "16 weeks",
                "result_value": 62.8,
                "confidence_interval_lower": 59.4,
                "confidence_interval_upper": 66.2,
                "p_value": 0.0001,
                "clinical_significance": "Significantly higher response rate vs systemic immunosuppressants",
                "evidence_grade": EvidenceGrade.MODERATE,
                "population_size": 11_200,
            },
            {
                "id": "OUT-005",
                "study_id": "RWE-STUDY-002",
                "outcome_type": OutcomeType.PATIENT_REPORTED,
                "outcome_name": "DLQI improvement from baseline",
                "measurement_method": "Mean change in Dermatology Life Quality Index score",
                "timepoint": "16 weeks",
                "result_value": -9.5,
                "confidence_interval_lower": -10.2,
                "confidence_interval_upper": -8.8,
                "p_value": 0.0001,
                "clinical_significance": "Exceeds MCID of 4 points, indicating very large improvement",
                "evidence_grade": EvidenceGrade.MODERATE,
                "population_size": 10_800,
            },
            {
                "id": "OUT-006",
                "study_id": "RWE-STUDY-003",
                "outcome_type": OutcomeType.EFFECTIVENESS,
                "outcome_name": "Overall survival at 24 months",
                "measurement_method": "Kaplan-Meier estimated survival probability",
                "timepoint": "24 months",
                "result_value": 73.2,
                "confidence_interval_lower": 68.1,
                "confidence_interval_upper": 78.3,
                "p_value": 0.002,
                "clinical_significance": "Significant OS benefit consistent with Phase III data",
                "evidence_grade": EvidenceGrade.MODERATE,
                "population_size": 3_200,
            },
            {
                "id": "OUT-007",
                "study_id": "RWE-STUDY-003",
                "outcome_type": OutcomeType.ECONOMIC,
                "outcome_name": "Total cost of care at 24 months",
                "measurement_method": "Mean total healthcare costs (medical + pharmacy) in USD",
                "timepoint": "24 months",
                "result_value": 145_200.0,
                "confidence_interval_lower": 132_400.0,
                "confidence_interval_upper": 158_000.0,
                "p_value": 0.12,
                "clinical_significance": "Higher acquisition cost offset by reduced hospitalizations",
                "evidence_grade": EvidenceGrade.LOW,
                "population_size": 3_200,
            },
            {
                "id": "OUT-008",
                "study_id": "RWE-STUDY-003",
                "outcome_type": OutcomeType.SAFETY,
                "outcome_name": "Immune-related adverse event rate",
                "measurement_method": "Incidence of grade 3+ immune-related AEs per 100 patient-years",
                "timepoint": "24 months",
                "result_value": 12.8,
                "confidence_interval_lower": 9.5,
                "confidence_interval_upper": 16.1,
                "p_value": 0.08,
                "clinical_significance": "Consistent with known checkpoint inhibitor safety profile",
                "evidence_grade": EvidenceGrade.MODERATE,
                "population_size": 3_200,
            },
        ]

        for o in outcomes_data:
            self._outcomes[o["id"]] = RealWorldOutcome(**o)

        # --- 4 Comparative Effectiveness ---
        ce_data = [
            {
                "id": "CE-001",
                "study_id": "RWE-STUDY-001",
                "treatment_arm": "Aflibercept (EYLEA)",
                "comparator_arm": "Ranibizumab (Lucentis)",
                "endpoint": "Visual acuity gain at 24 months",
                "hazard_ratio": None,
                "odds_ratio": 1.28,
                "relative_risk": 1.15,
                "absolute_risk_reduction": 0.08,
                "nnt": 13,
                "nnh": None,
                "favors": "Aflibercept (EYLEA)",
                "statistical_method": "Propensity score-matched cohort analysis with inverse probability weighting",
            },
            {
                "id": "CE-002",
                "study_id": "RWE-STUDY-001",
                "treatment_arm": "Aflibercept (EYLEA)",
                "comparator_arm": "Ranibizumab (Lucentis)",
                "endpoint": "Treatment persistence at 12 months",
                "hazard_ratio": 0.82,
                "odds_ratio": None,
                "relative_risk": None,
                "absolute_risk_reduction": 0.05,
                "nnt": 20,
                "nnh": None,
                "favors": "Aflibercept (EYLEA)",
                "statistical_method": "Cox proportional hazards with time-varying covariates",
            },
            {
                "id": "CE-003",
                "study_id": "RWE-STUDY-002",
                "treatment_arm": "Dupilumab (DUPIXENT)",
                "comparator_arm": "Systemic immunosuppressants",
                "endpoint": "EASI-75 response at 16 weeks",
                "hazard_ratio": None,
                "odds_ratio": 2.45,
                "relative_risk": 1.68,
                "absolute_risk_reduction": 0.25,
                "nnt": 4,
                "nnh": None,
                "favors": "Dupilumab (DUPIXENT)",
                "statistical_method": "Inverse probability of treatment weighting with doubly robust estimation",
            },
            {
                "id": "CE-004",
                "study_id": "RWE-STUDY-003",
                "treatment_arm": "Cemiplimab (LIBTAYO)",
                "comparator_arm": "Platinum-based chemotherapy",
                "endpoint": "Overall survival at 24 months",
                "hazard_ratio": 0.58,
                "odds_ratio": None,
                "relative_risk": None,
                "absolute_risk_reduction": 0.22,
                "nnt": 5,
                "nnh": 8,
                "favors": "Cemiplimab (LIBTAYO)",
                "statistical_method": "Adjusted Kaplan-Meier with IPTW and sensitivity analyses",
            },
        ]

        for ce in ce_data:
            self._comparative[ce["id"]] = ComparativeEffectiveness(**ce)

        # --- 3 Health Economic Analyses ---
        he_data = [
            {
                "id": "HE-001",
                "study_id": "RWE-STUDY-001",
                "analysis_type": "CUA",
                "perspective": "US payer",
                "time_horizon": "lifetime",
                "discount_rate": 0.03,
                "cost_per_qaly": 38_500.0,
                "incremental_cost": 12_450.0,
                "incremental_effectiveness": 0.32,
                "icer": 38_906.25,
                "willingness_to_pay_threshold": 100_000.0,
                "cost_effective": True,
                "sensitivity_analysis_results": {
                    "discount_rate_0%": 32_100.0,
                    "discount_rate_5%": 45_200.0,
                    "drug_cost_+20%": 52_800.0,
                    "drug_cost_-20%": 25_100.0,
                    "time_horizon_10yr": 42_300.0,
                },
            },
            {
                "id": "HE-002",
                "study_id": "RWE-STUDY-003",
                "analysis_type": "CEA",
                "perspective": "healthcare system",
                "time_horizon": "5 years",
                "discount_rate": 0.03,
                "cost_per_qaly": 67_800.0,
                "incremental_cost": 45_300.0,
                "incremental_effectiveness": 0.67,
                "icer": 67_611.94,
                "willingness_to_pay_threshold": 150_000.0,
                "cost_effective": True,
                "sensitivity_analysis_results": {
                    "OS_benefit_reduced_25%": 95_400.0,
                    "OS_benefit_increased_25%": 48_200.0,
                    "drug_cost_+30%": 88_700.0,
                    "hospitalization_cost_+20%": 58_900.0,
                },
            },
            {
                "id": "HE-003",
                "study_id": "RWE-STUDY-002",
                "analysis_type": "CBA",
                "perspective": "societal",
                "time_horizon": "3 years",
                "discount_rate": 0.03,
                "cost_per_qaly": None,
                "incremental_cost": 28_700.0,
                "incremental_effectiveness": 0.45,
                "icer": 63_777.78,
                "willingness_to_pay_threshold": 100_000.0,
                "cost_effective": True,
                "sensitivity_analysis_results": {
                    "productivity_gains_included": 41_200.0,
                    "productivity_gains_excluded": 72_300.0,
                    "indirect_costs_+50%": 35_600.0,
                },
            },
        ]

        for h in he_data:
            self._health_econ[h["id"]] = HealthEconomicAnalysis(**h)

        # --- 3 Submission Packages ---
        sub_data = [
            {
                "id": "SUB-001",
                "study_id": "RWE-STUDY-001",
                "regulatory_authority": "FDA",
                "submission_date": now - timedelta(days=60),
                "package_type": "supplemental NDA",
                "data_sources_included": ["DS-001", "DS-003"],
                "methodology_summary": "Retrospective cohort study using propensity score matching across two large US claims databases with 24-month follow-up",
                "key_findings": [
                    "EYLEA demonstrates superior visual acuity outcomes vs ranibizumab in real-world nAMD",
                    "Higher treatment persistence at 12 months (72.3% vs 67.1%)",
                    "Comparable safety profile to controlled trial data",
                    "Cost-effective at $38,500/QALY under US payer perspective",
                ],
                "status": AnalysisStatus.SUBMITTED_TO_FDA,
                "reviewer_feedback": None,
            },
            {
                "id": "SUB-002",
                "study_id": "RWE-STUDY-003",
                "regulatory_authority": "FDA",
                "submission_date": None,
                "package_type": "post-market commitment",
                "data_sources_included": ["DS-002"],
                "methodology_summary": "Retrospective cohort study using oncology EHR data with adjusted survival analysis and health economic evaluation",
                "key_findings": [
                    "LIBTAYO shows 73.2% OS at 24 months in advanced CSCC",
                    "Significant OS benefit vs platinum chemotherapy (HR 0.58)",
                    "Cost-effective at $67,800/QALY under healthcare system perspective",
                ],
                "status": AnalysisStatus.PEER_REVIEW,
                "reviewer_feedback": None,
            },
            {
                "id": "SUB-003",
                "study_id": "RWE-STUDY-001",
                "regulatory_authority": "EMA",
                "submission_date": now - timedelta(days=30),
                "package_type": "label expansion",
                "data_sources_included": ["DS-001", "DS-004"],
                "methodology_summary": "Multi-database retrospective cohort study spanning US claims and UK registry data with propensity-matched comparative effectiveness analysis",
                "key_findings": [
                    "Consistent effectiveness across US and UK populations",
                    "Real-world outcomes support extension to broader nAMD population",
                    "Favorable benefit-risk profile maintained in elderly subgroups",
                ],
                "status": AnalysisStatus.SUBMITTED_TO_FDA,
                "reviewer_feedback": "Reviewer requested additional subgroup analysis for patients >85 years",
            },
        ]

        for s in sub_data:
            self._submissions[s["id"]] = RWESubmissionPackage(**s)

    # ------------------------------------------------------------------
    # Data Source Management
    # ------------------------------------------------------------------

    def list_data_sources(
        self,
        *,
        data_source_type: DataSourceType | None = None,
    ) -> list[RWEDataSource]:
        """List RWE data sources with optional type filter."""
        with self._lock:
            result = list(self._data_sources.values())

        if data_source_type is not None:
            result = [ds for ds in result if ds.data_source_type == data_source_type]

        return sorted(result, key=lambda ds: ds.id)

    def get_data_source(self, ds_id: str) -> RWEDataSource | None:
        """Get a single data source by ID."""
        with self._lock:
            return self._data_sources.get(ds_id)

    def create_data_source(self, payload: RWEDataSourceCreate) -> RWEDataSource:
        """Create a new RWE data source."""
        ds_id = f"DS-{uuid4().hex[:8].upper()}"
        ds = RWEDataSource(id=ds_id, **payload.model_dump())
        with self._lock:
            self._data_sources[ds_id] = ds
        logger.info("Created RWE data source %s: %s", ds_id, payload.name)
        return ds

    def update_data_source(self, ds_id: str, payload: RWEDataSourceUpdate) -> RWEDataSource | None:
        """Update an existing data source."""
        with self._lock:
            existing = self._data_sources.get(ds_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = RWEDataSource(**data)
            self._data_sources[ds_id] = updated
        return updated

    def delete_data_source(self, ds_id: str) -> bool:
        """Delete a data source. Returns True if deleted."""
        with self._lock:
            if ds_id in self._data_sources:
                del self._data_sources[ds_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Study Management
    # ------------------------------------------------------------------

    def list_studies(
        self,
        *,
        trial_id: str | None = None,
        status: AnalysisStatus | None = None,
        study_design: StudyDesign | None = None,
    ) -> list[RWEStudy]:
        """List RWE studies with optional filters."""
        with self._lock:
            result = list(self._studies.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if status is not None:
            result = [s for s in result if s.status == status]
        if study_design is not None:
            result = [s for s in result if s.study_design == study_design]

        return sorted(result, key=lambda s: s.start_date, reverse=True)

    def get_study(self, study_id: str) -> RWEStudy | None:
        """Get a single study by ID."""
        with self._lock:
            return self._studies.get(study_id)

    def initiate_study(self, payload: RWEStudyCreate) -> RWEStudy:
        """Initiate a new RWE study."""
        now = datetime.now(timezone.utc)
        study_id = f"RWE-STUDY-{uuid4().hex[:8].upper()}"
        study = RWEStudy(
            id=study_id,
            status=AnalysisStatus.PLANNED,
            start_date=now,
            completion_date=None,
            **payload.model_dump(),
        )
        with self._lock:
            self._studies[study_id] = study
        logger.info("Initiated RWE study %s: %s", study_id, payload.study_name)
        return study

    def update_study(self, study_id: str, payload: RWEStudyUpdate) -> RWEStudy | None:
        """Update an existing study."""
        with self._lock:
            existing = self._studies.get(study_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = RWEStudy(**data)
            self._studies[study_id] = updated
        return updated

    def delete_study(self, study_id: str) -> bool:
        """Delete a study. Returns True if deleted."""
        with self._lock:
            if study_id in self._studies:
                del self._studies[study_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Outcome Recording
    # ------------------------------------------------------------------

    def list_outcomes(
        self,
        *,
        study_id: str | None = None,
        outcome_type: OutcomeType | None = None,
        evidence_grade: EvidenceGrade | None = None,
    ) -> list[RealWorldOutcome]:
        """List outcomes with optional filters."""
        with self._lock:
            result = list(self._outcomes.values())

        if study_id is not None:
            result = [o for o in result if o.study_id == study_id]
        if outcome_type is not None:
            result = [o for o in result if o.outcome_type == outcome_type]
        if evidence_grade is not None:
            result = [o for o in result if o.evidence_grade == evidence_grade]

        return sorted(result, key=lambda o: o.id)

    def get_outcome(self, outcome_id: str) -> RealWorldOutcome | None:
        """Get a single outcome by ID."""
        with self._lock:
            return self._outcomes.get(outcome_id)

    def record_outcome(self, payload: RealWorldOutcomeCreate) -> RealWorldOutcome:
        """Record a new real-world outcome."""
        # Validate study exists
        with self._lock:
            study = self._studies.get(payload.study_id)
        if study is None:
            raise ValueError(f"Study '{payload.study_id}' not found")

        outcome_id = f"OUT-{uuid4().hex[:8].upper()}"
        outcome = RealWorldOutcome(id=outcome_id, **payload.model_dump())
        with self._lock:
            self._outcomes[outcome_id] = outcome
        logger.info(
            "Recorded outcome %s for study %s: %s",
            outcome_id, payload.study_id, payload.outcome_name,
        )
        return outcome

    def update_outcome(self, outcome_id: str, payload: RealWorldOutcomeUpdate) -> RealWorldOutcome | None:
        """Update an existing outcome."""
        with self._lock:
            existing = self._outcomes.get(outcome_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = RealWorldOutcome(**data)
            self._outcomes[outcome_id] = updated
        return updated

    def delete_outcome(self, outcome_id: str) -> bool:
        """Delete an outcome. Returns True if deleted."""
        with self._lock:
            if outcome_id in self._outcomes:
                del self._outcomes[outcome_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Comparative Effectiveness
    # ------------------------------------------------------------------

    def list_comparative_analyses(
        self,
        *,
        study_id: str | None = None,
    ) -> list[ComparativeEffectiveness]:
        """List comparative effectiveness analyses."""
        with self._lock:
            result = list(self._comparative.values())

        if study_id is not None:
            result = [c for c in result if c.study_id == study_id]

        return sorted(result, key=lambda c: c.id)

    def get_comparative_analysis(self, ce_id: str) -> ComparativeEffectiveness | None:
        """Get a single comparative effectiveness analysis."""
        with self._lock:
            return self._comparative.get(ce_id)

    def run_comparative_analysis(self, payload: ComparativeEffectivenessCreate) -> ComparativeEffectiveness:
        """Run/record a comparative effectiveness analysis."""
        with self._lock:
            study = self._studies.get(payload.study_id)
        if study is None:
            raise ValueError(f"Study '{payload.study_id}' not found")

        ce_id = f"CE-{uuid4().hex[:8].upper()}"
        ce = ComparativeEffectiveness(id=ce_id, **payload.model_dump())
        with self._lock:
            self._comparative[ce_id] = ce
        logger.info(
            "Ran comparative analysis %s for study %s: %s vs %s",
            ce_id, payload.study_id, payload.treatment_arm, payload.comparator_arm,
        )
        return ce

    def update_comparative_analysis(self, ce_id: str, payload: ComparativeEffectivenessUpdate) -> ComparativeEffectiveness | None:
        """Update a comparative effectiveness record."""
        with self._lock:
            existing = self._comparative.get(ce_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ComparativeEffectiveness(**data)
            self._comparative[ce_id] = updated
        return updated

    def delete_comparative_analysis(self, ce_id: str) -> bool:
        """Delete a comparative effectiveness record."""
        with self._lock:
            if ce_id in self._comparative:
                del self._comparative[ce_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Health Economics
    # ------------------------------------------------------------------

    def list_health_economics(
        self,
        *,
        study_id: str | None = None,
    ) -> list[HealthEconomicAnalysis]:
        """List health economic analyses."""
        with self._lock:
            result = list(self._health_econ.values())

        if study_id is not None:
            result = [h for h in result if h.study_id == study_id]

        return sorted(result, key=lambda h: h.id)

    def get_health_economic(self, he_id: str) -> HealthEconomicAnalysis | None:
        """Get a single health economic analysis."""
        with self._lock:
            return self._health_econ.get(he_id)

    def calculate_health_economics(self, payload: HealthEconomicAnalysisCreate) -> HealthEconomicAnalysis:
        """Calculate/record a health economic analysis."""
        with self._lock:
            study = self._studies.get(payload.study_id)
        if study is None:
            raise ValueError(f"Study '{payload.study_id}' not found")

        he_id = f"HE-{uuid4().hex[:8].upper()}"
        he = HealthEconomicAnalysis(id=he_id, **payload.model_dump())
        with self._lock:
            self._health_econ[he_id] = he
        logger.info(
            "Calculated health economics %s for study %s: %s (%s perspective)",
            he_id, payload.study_id, payload.analysis_type, payload.perspective,
        )
        return he

    def update_health_economic(self, he_id: str, payload: HealthEconomicAnalysisUpdate) -> HealthEconomicAnalysis | None:
        """Update a health economic analysis."""
        with self._lock:
            existing = self._health_econ.get(he_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = HealthEconomicAnalysis(**data)
            self._health_econ[he_id] = updated
        return updated

    def delete_health_economic(self, he_id: str) -> bool:
        """Delete a health economic analysis."""
        with self._lock:
            if he_id in self._health_econ:
                del self._health_econ[he_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Submission Packages
    # ------------------------------------------------------------------

    def list_submission_packages(
        self,
        *,
        study_id: str | None = None,
        regulatory_authority: str | None = None,
        status: AnalysisStatus | None = None,
    ) -> list[RWESubmissionPackage]:
        """List submission packages with optional filters."""
        with self._lock:
            result = list(self._submissions.values())

        if study_id is not None:
            result = [s for s in result if s.study_id == study_id]
        if regulatory_authority is not None:
            result = [s for s in result if s.regulatory_authority == regulatory_authority]
        if status is not None:
            result = [s for s in result if s.status == status]

        return sorted(result, key=lambda s: s.id)

    def get_submission_package(self, sub_id: str) -> RWESubmissionPackage | None:
        """Get a single submission package."""
        with self._lock:
            return self._submissions.get(sub_id)

    def prepare_submission_package(self, payload: RWESubmissionPackageCreate) -> RWESubmissionPackage:
        """Prepare a new RWE submission package."""
        with self._lock:
            study = self._studies.get(payload.study_id)
        if study is None:
            raise ValueError(f"Study '{payload.study_id}' not found")

        sub_id = f"SUB-{uuid4().hex[:8].upper()}"
        sub = RWESubmissionPackage(
            id=sub_id,
            submission_date=None,
            status=AnalysisStatus.PLANNED,
            reviewer_feedback=None,
            **payload.model_dump(),
        )
        with self._lock:
            self._submissions[sub_id] = sub
        logger.info(
            "Prepared submission package %s for study %s -> %s",
            sub_id, payload.study_id, payload.regulatory_authority,
        )
        return sub

    def update_submission_package(self, sub_id: str, payload: RWESubmissionPackageUpdate) -> RWESubmissionPackage | None:
        """Update a submission package."""
        with self._lock:
            existing = self._submissions.get(sub_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = RWESubmissionPackage(**data)
            self._submissions[sub_id] = updated
        return updated

    def delete_submission_package(self, sub_id: str) -> bool:
        """Delete a submission package."""
        with self._lock:
            if sub_id in self._submissions:
                del self._submissions[sub_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self) -> RWEMetrics:
        """Compute aggregated RWE operational metrics."""
        with self._lock:
            data_sources = list(self._data_sources.values())
            studies = list(self._studies.values())
            outcomes = list(self._outcomes.values())
            comparative = list(self._comparative.values())
            health_econ = list(self._health_econ.values())
            submissions = list(self._submissions.values())

        # Data sources
        total_patients = sum(ds.patient_count for ds in data_sources)
        avg_quality = (
            round(sum(ds.quality_score for ds in data_sources) / max(1, len(data_sources)), 1)
            if data_sources
            else 0.0
        )

        # Studies by status
        studies_by_status: dict[str, int] = {}
        for s in studies:
            key = s.status.value
            studies_by_status[key] = studies_by_status.get(key, 0) + 1

        # Studies by design
        studies_by_design: dict[str, int] = {}
        for s in studies:
            key = s.study_design.value
            studies_by_design[key] = studies_by_design.get(key, 0) + 1

        # Outcomes by type
        outcomes_by_type: dict[str, int] = {}
        for o in outcomes:
            key = o.outcome_type.value
            outcomes_by_type[key] = outcomes_by_type.get(key, 0) + 1

        # Cost-effective treatments
        cost_effective_count = sum(1 for h in health_econ if h.cost_effective)

        # Submissions by authority
        submissions_by_authority: dict[str, int] = {}
        for s in submissions:
            key = s.regulatory_authority
            submissions_by_authority[key] = submissions_by_authority.get(key, 0) + 1

        # Average evidence grade (most common)
        if outcomes:
            grade_counter: Counter[str] = Counter(o.evidence_grade.value for o in outcomes)
            avg_grade = grade_counter.most_common(1)[0][0]
        else:
            avg_grade = ""

        return RWEMetrics(
            total_data_sources=len(data_sources),
            total_patients_across_sources=total_patients,
            average_data_quality_score=avg_quality,
            total_studies=len(studies),
            studies_by_status=studies_by_status,
            studies_by_design=studies_by_design,
            total_outcomes=len(outcomes),
            outcomes_by_type=outcomes_by_type,
            total_comparative_analyses=len(comparative),
            total_health_economic_analyses=len(health_econ),
            cost_effective_treatments=cost_effective_count,
            total_submission_packages=len(submissions),
            submissions_by_authority=submissions_by_authority,
            average_evidence_grade=avg_grade,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: RWEService | None = None
_instance_lock = threading.Lock()


def get_rwe_service() -> RWEService:
    """Return the singleton RWEService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = RWEService()
    return _instance


def reset_real_world_evidence_service() -> RWEService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = RWEService()
    return _instance
