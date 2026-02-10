"""Ancillary Study Management Service.

Manages sub-studies, companion diagnostics, biomarker studies, pharmacokinetic
studies, and their integration with parent trials.  Includes full CRUD for
studies, samples, endpoints, sub-study sites, and data sharing agreements,
plus sample collection, analysis tracking, site activation, study progress,
and operational metrics.

Usage:
    from app.services.ancillary_study_service import (
        get_ancillary_study_service,
    )

    svc = get_ancillary_study_service()
    studies = svc.list_studies()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.ancillary_study import (
    AgreementStatus,
    AgreementType,
    AnalysisStatus,
    AncillaryMetrics,
    AncillaryStatus,
    AncillaryStudy,
    AncillaryStudyCreate,
    AncillaryStudyType,
    AncillaryStudyUpdate,
    DataSharingAgreement,
    DataSharingAgreementCreate,
    DataSharingAgreementUpdate,
    EndpointType,
    SampleType,
    StudyEndpoint,
    StudyEndpointCreate,
    StudyEndpointUpdate,
    StudyProgress,
    StudyRelationship,
    StudySample,
    StudySampleCreate,
    StudySampleUpdate,
    SubStudySite,
    SubStudySiteCreate,
    SubStudySiteStatus,
    SubStudySiteUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Parent trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class AncillaryStudyService:
    """In-memory Ancillary Study Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._studies: dict[str, AncillaryStudy] = {}
        self._samples: dict[str, StudySample] = {}
        self._endpoints: dict[str, StudyEndpoint] = {}
        self._sites: dict[str, SubStudySite] = {}
        self._agreements: dict[str, DataSharingAgreement] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901 — seed method is intentionally long
        """Pre-populate realistic ancillary study data."""
        now = datetime.now(timezone.utc)

        # --- 4 Ancillary Studies ---
        studies_data = [
            {
                "id": "ANC-001",
                "parent_trial_id": EYLEA_TRIAL,
                "study_name": "VEGF Biomarker Substudy",
                "study_type": AncillaryStudyType.BIOMARKER,
                "relationship": StudyRelationship.EMBEDDED,
                "status": AncillaryStatus.ENROLLING,
                "protocol_number": "EYL-BIO-2025-01",
                "pi_name": "Dr. Sarah Chen",
                "pi_institution": "Massachusetts Eye and Ear",
                "start_date": now - timedelta(days=180),
                "end_date": now + timedelta(days=365),
                "target_enrollment": 120,
                "current_enrollment": 78,
                "budget": 2500000.0,
                "funding_source": "Regeneron Pharmaceuticals",
                "description": "Exploratory biomarker sub-study evaluating VEGF-A, VEGF-C, and PlGF levels as predictive markers for treatment response in wet AMD patients receiving aflibercept.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "ANC-002",
                "parent_trial_id": DUPIXENT_TRIAL,
                "study_name": "Dupilumab PK/PD Characterization",
                "study_type": AncillaryStudyType.PK_STUDY,
                "relationship": StudyRelationship.MANDATORY,
                "status": AncillaryStatus.ACTIVE,
                "protocol_number": "DUP-PK-2025-03",
                "pi_name": "Dr. James Rodriguez",
                "pi_institution": "Johns Hopkins Clinical Pharmacology",
                "start_date": now - timedelta(days=120),
                "end_date": now + timedelta(days=240),
                "target_enrollment": 60,
                "current_enrollment": 45,
                "budget": 1800000.0,
                "funding_source": "Sanofi/Regeneron",
                "description": "Population PK/PD study characterizing dupilumab exposure-response relationships in moderate-to-severe atopic dermatitis, with intensive sampling in a subset of patients.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "ANC-003",
                "parent_trial_id": LIBTAYO_TRIAL,
                "study_name": "PD-L1 Companion Diagnostic Validation",
                "study_type": AncillaryStudyType.COMPANION_DIAGNOSTIC,
                "relationship": StudyRelationship.MANDATORY,
                "status": AncillaryStatus.ACTIVE,
                "protocol_number": "LIB-CDx-2025-01",
                "pi_name": "Dr. Maria Gonzalez",
                "pi_institution": "MD Anderson Cancer Center",
                "start_date": now - timedelta(days=240),
                "end_date": now + timedelta(days=180),
                "target_enrollment": 200,
                "current_enrollment": 162,
                "budget": 3200000.0,
                "funding_source": "Regeneron/Sanofi",
                "description": "Prospective validation of PD-L1 tumor proportion score (TPS) as a companion diagnostic for cemiplimab patient selection in advanced CSCC, comparing SP263 and 22C3 assays.",
                "created_at": now - timedelta(days=260),
            },
            {
                "id": "ANC-004",
                "parent_trial_id": EYLEA_TRIAL,
                "study_name": "Retinal Imaging Ancillary Study",
                "study_type": AncillaryStudyType.IMAGING,
                "relationship": StudyRelationship.OPTIONAL,
                "status": AncillaryStatus.PLANNED,
                "protocol_number": "EYL-IMG-2026-01",
                "pi_name": "Dr. Robert Kim",
                "pi_institution": "Bascom Palmer Eye Institute",
                "start_date": now + timedelta(days=30),
                "end_date": now + timedelta(days=730),
                "target_enrollment": 80,
                "current_enrollment": 0,
                "budget": 1500000.0,
                "funding_source": "NIH R01 Grant",
                "description": "Advanced OCT and OCTA imaging sub-study to characterize retinal vascular changes and fluid dynamics in response to aflibercept treatment over 24 months.",
                "created_at": now - timedelta(days=30),
            },
        ]

        for s in studies_data:
            self._studies[s["id"]] = AncillaryStudy(**s)

        # --- 10 Study Samples ---
        samples_data = [
            {
                "id": "SMP-001",
                "ancillary_study_id": "ANC-001",
                "patient_id": "PAT-1001",
                "site_id": "SITE-101",
                "sample_type": SampleType.PLASMA,
                "collection_date": now - timedelta(days=90),
                "visit_number": 1,
                "processing_instructions": "Centrifuge at 2000g for 15 min within 30 min of collection. Aliquot into 0.5mL cryovials.",
                "storage_condition": "-80C",
                "aliquot_count": 4,
                "shipped_to_lab": True,
                "lab_received_date": now - timedelta(days=85),
                "analysis_status": AnalysisStatus.COMPLETED,
                "results_available": True,
            },
            {
                "id": "SMP-002",
                "ancillary_study_id": "ANC-001",
                "patient_id": "PAT-1001",
                "site_id": "SITE-101",
                "sample_type": SampleType.SERUM,
                "collection_date": now - timedelta(days=90),
                "visit_number": 1,
                "processing_instructions": "Allow to clot 30 min at RT. Centrifuge 1500g for 10 min.",
                "storage_condition": "-80C",
                "aliquot_count": 3,
                "shipped_to_lab": True,
                "lab_received_date": now - timedelta(days=85),
                "analysis_status": AnalysisStatus.COMPLETED,
                "results_available": True,
            },
            {
                "id": "SMP-003",
                "ancillary_study_id": "ANC-001",
                "patient_id": "PAT-1002",
                "site_id": "SITE-102",
                "sample_type": SampleType.PLASMA,
                "collection_date": now - timedelta(days=60),
                "visit_number": 1,
                "processing_instructions": "Centrifuge at 2000g for 15 min within 30 min of collection.",
                "storage_condition": "-80C",
                "aliquot_count": 4,
                "shipped_to_lab": True,
                "lab_received_date": now - timedelta(days=55),
                "analysis_status": AnalysisStatus.IN_PROGRESS,
                "results_available": False,
            },
            {
                "id": "SMP-004",
                "ancillary_study_id": "ANC-001",
                "patient_id": "PAT-1003",
                "site_id": "SITE-103",
                "sample_type": SampleType.BLOOD,
                "collection_date": now - timedelta(days=30),
                "visit_number": 2,
                "processing_instructions": "Collect in EDTA tube. Process within 2 hours.",
                "storage_condition": "-20C",
                "aliquot_count": 2,
                "shipped_to_lab": False,
                "lab_received_date": None,
                "analysis_status": AnalysisStatus.PENDING,
                "results_available": False,
            },
            {
                "id": "SMP-005",
                "ancillary_study_id": "ANC-002",
                "patient_id": "PAT-2001",
                "site_id": "SITE-103",
                "sample_type": SampleType.SERUM,
                "collection_date": now - timedelta(days=100),
                "visit_number": 1,
                "processing_instructions": "Pre-dose trough sample. Clot 30 min. Centrifuge 2000g.",
                "storage_condition": "-80C",
                "aliquot_count": 3,
                "shipped_to_lab": True,
                "lab_received_date": now - timedelta(days=95),
                "analysis_status": AnalysisStatus.COMPLETED,
                "results_available": True,
            },
            {
                "id": "SMP-006",
                "ancillary_study_id": "ANC-002",
                "patient_id": "PAT-2001",
                "site_id": "SITE-103",
                "sample_type": SampleType.SERUM,
                "collection_date": now - timedelta(days=86),
                "visit_number": 2,
                "processing_instructions": "2-hour post-dose sample. Clot 30 min. Centrifuge 2000g.",
                "storage_condition": "-80C",
                "aliquot_count": 3,
                "shipped_to_lab": True,
                "lab_received_date": now - timedelta(days=80),
                "analysis_status": AnalysisStatus.COMPLETED,
                "results_available": True,
            },
            {
                "id": "SMP-007",
                "ancillary_study_id": "ANC-002",
                "patient_id": "PAT-2002",
                "site_id": "SITE-104",
                "sample_type": SampleType.BLOOD,
                "collection_date": now - timedelta(days=45),
                "visit_number": 1,
                "processing_instructions": "Collect in EDTA tube. Process within 1 hour for PK analysis.",
                "storage_condition": "-80C",
                "aliquot_count": 5,
                "shipped_to_lab": True,
                "lab_received_date": now - timedelta(days=40),
                "analysis_status": AnalysisStatus.IN_PROGRESS,
                "results_available": False,
            },
            {
                "id": "SMP-008",
                "ancillary_study_id": "ANC-003",
                "patient_id": "PAT-3001",
                "site_id": "SITE-105",
                "sample_type": SampleType.TISSUE,
                "collection_date": now - timedelta(days=200),
                "visit_number": 1,
                "processing_instructions": "FFPE block. Ship at ambient temperature. Minimum 10 unstained slides.",
                "storage_condition": "Ambient",
                "aliquot_count": 1,
                "shipped_to_lab": True,
                "lab_received_date": now - timedelta(days=195),
                "analysis_status": AnalysisStatus.COMPLETED,
                "results_available": True,
            },
            {
                "id": "SMP-009",
                "ancillary_study_id": "ANC-003",
                "patient_id": "PAT-3002",
                "site_id": "SITE-106",
                "sample_type": SampleType.TISSUE,
                "collection_date": now - timedelta(days=150),
                "visit_number": 1,
                "processing_instructions": "FFPE block. Ship at ambient temperature.",
                "storage_condition": "Ambient",
                "aliquot_count": 1,
                "shipped_to_lab": True,
                "lab_received_date": now - timedelta(days=145),
                "analysis_status": AnalysisStatus.FAILED,
                "results_available": False,
            },
            {
                "id": "SMP-010",
                "ancillary_study_id": "ANC-003",
                "patient_id": "PAT-3003",
                "site_id": "SITE-107",
                "sample_type": SampleType.TISSUE,
                "collection_date": now - timedelta(days=20),
                "visit_number": 1,
                "processing_instructions": "FFPE block. Minimum tumor content 50%.",
                "storage_condition": "Ambient",
                "aliquot_count": 1,
                "shipped_to_lab": False,
                "lab_received_date": None,
                "analysis_status": AnalysisStatus.PENDING,
                "results_available": False,
            },
        ]

        for s in samples_data:
            self._samples[s["id"]] = StudySample(**s)

        # --- 7 Study Endpoints ---
        endpoints_data = [
            {
                "id": "EP-001",
                "ancillary_study_id": "ANC-001",
                "endpoint_name": "Change in VEGF-A from Baseline",
                "endpoint_type": EndpointType.PRIMARY,
                "description": "Absolute change in plasma VEGF-A levels from baseline to Week 12",
                "measurement_method": "Quantitative ELISA (R&D Systems)",
                "measurement_timepoints": ["Baseline", "Week 4", "Week 8", "Week 12"],
                "target_value": ">=30% reduction",
                "statistical_method": "Mixed-effects model for repeated measures (MMRM)",
                "analysis_population": "Modified ITT",
            },
            {
                "id": "EP-002",
                "ancillary_study_id": "ANC-001",
                "endpoint_name": "VEGF-C / PlGF Ratio",
                "endpoint_type": EndpointType.SECONDARY,
                "description": "Correlation of VEGF-C/PlGF ratio with visual acuity outcomes",
                "measurement_method": "Multiplex immunoassay (Meso Scale Discovery)",
                "measurement_timepoints": ["Baseline", "Week 12", "Week 24"],
                "target_value": None,
                "statistical_method": "Pearson correlation with Bonferroni correction",
                "analysis_population": "Per-Protocol",
            },
            {
                "id": "EP-003",
                "ancillary_study_id": "ANC-002",
                "endpoint_name": "Dupilumab Trough Concentration",
                "endpoint_type": EndpointType.PRIMARY,
                "description": "Steady-state trough concentration (Cmin,ss) of dupilumab",
                "measurement_method": "Validated ELISA (LLOQ 0.078 mg/L)",
                "measurement_timepoints": ["Week 2", "Week 4", "Week 8", "Week 16"],
                "target_value": ">=10 mg/L",
                "statistical_method": "Population PK modeling (NONMEM)",
                "analysis_population": "PK Population",
            },
            {
                "id": "EP-004",
                "ancillary_study_id": "ANC-002",
                "endpoint_name": "Exposure-EASI Response",
                "endpoint_type": EndpointType.SECONDARY,
                "description": "Relationship between dupilumab AUC and EASI-75 response rate",
                "measurement_method": "Model-predicted AUC from PopPK + clinical EASI assessment",
                "measurement_timepoints": ["Week 16"],
                "target_value": None,
                "statistical_method": "Logistic regression of exposure quartiles",
                "analysis_population": "Modified ITT",
            },
            {
                "id": "EP-005",
                "ancillary_study_id": "ANC-003",
                "endpoint_name": "PD-L1 TPS Concordance",
                "endpoint_type": EndpointType.PRIMARY,
                "description": "Inter-assay concordance rate between SP263 and 22C3 PD-L1 IHC assays",
                "measurement_method": "PD-L1 IHC scoring by two independent pathologists",
                "measurement_timepoints": ["Screening"],
                "target_value": ">=90% concordance",
                "statistical_method": "Cohen kappa with 95% CI, Bland-Altman analysis",
                "analysis_population": "Evaluable Tissue Population",
            },
            {
                "id": "EP-006",
                "ancillary_study_id": "ANC-003",
                "endpoint_name": "PD-L1 Predictive Value for ORR",
                "endpoint_type": EndpointType.EXPLORATORY,
                "description": "Predictive value of PD-L1 TPS >=50% for overall response rate",
                "measurement_method": "RECIST v1.1 assessment + PD-L1 TPS",
                "measurement_timepoints": ["Screening", "Week 9", "Week 18"],
                "target_value": None,
                "statistical_method": "Subgroup analysis: PD-L1 high vs low, Fisher exact test",
                "analysis_population": "ITT",
            },
            {
                "id": "EP-007",
                "ancillary_study_id": "ANC-002",
                "endpoint_name": "Anti-Drug Antibody Incidence",
                "endpoint_type": EndpointType.SAFETY,
                "description": "Incidence and titer of anti-dupilumab antibodies and impact on PK",
                "measurement_method": "Validated bridging ECL immunoassay",
                "measurement_timepoints": ["Baseline", "Week 4", "Week 16", "Week 24"],
                "target_value": None,
                "statistical_method": "Descriptive statistics, PK impact analysis",
                "analysis_population": "Safety Population",
            },
        ]

        for e in endpoints_data:
            self._endpoints[e["id"]] = StudyEndpoint(**e)

        # --- 6 Sub-Study Sites ---
        sites_data = [
            {
                "id": "SSS-001",
                "ancillary_study_id": "ANC-001",
                "site_id": "SITE-101",
                "site_name": "Memorial Hermann Hospital",
                "activation_date": now - timedelta(days=170),
                "status": SubStudySiteStatus.ENROLLING,
                "patients_enrolled": 25,
                "samples_collected": 48,
                "irb_approval_date": now - timedelta(days=190),
                "irb_expiry_date": now + timedelta(days=175),
            },
            {
                "id": "SSS-002",
                "ancillary_study_id": "ANC-001",
                "site_id": "SITE-102",
                "site_name": "Cleveland Clinic Foundation",
                "activation_date": now - timedelta(days=160),
                "status": SubStudySiteStatus.ENROLLING,
                "patients_enrolled": 30,
                "samples_collected": 55,
                "irb_approval_date": now - timedelta(days=180),
                "irb_expiry_date": now + timedelta(days=185),
            },
            {
                "id": "SSS-003",
                "ancillary_study_id": "ANC-002",
                "site_id": "SITE-103",
                "site_name": "Johns Hopkins Research Center",
                "activation_date": now - timedelta(days=110),
                "status": SubStudySiteStatus.ENROLLING,
                "patients_enrolled": 20,
                "samples_collected": 38,
                "irb_approval_date": now - timedelta(days=130),
                "irb_expiry_date": now + timedelta(days=235),
            },
            {
                "id": "SSS-004",
                "ancillary_study_id": "ANC-002",
                "site_id": "SITE-104",
                "site_name": "Mayo Clinic Jacksonville",
                "activation_date": now - timedelta(days=90),
                "status": SubStudySiteStatus.ACTIVATED,
                "patients_enrolled": 12,
                "samples_collected": 20,
                "irb_approval_date": now - timedelta(days=100),
                "irb_expiry_date": now + timedelta(days=265),
            },
            {
                "id": "SSS-005",
                "ancillary_study_id": "ANC-003",
                "site_id": "SITE-105",
                "site_name": "Duke Clinical Research Institute",
                "activation_date": now - timedelta(days=230),
                "status": SubStudySiteStatus.ENROLLING,
                "patients_enrolled": 85,
                "samples_collected": 90,
                "irb_approval_date": now - timedelta(days=250),
                "irb_expiry_date": now + timedelta(days=115),
            },
            {
                "id": "SSS-006",
                "ancillary_study_id": "ANC-003",
                "site_id": "SITE-106",
                "site_name": "Cedars-Sinai Medical Center",
                "activation_date": now - timedelta(days=200),
                "status": SubStudySiteStatus.ENROLLING,
                "patients_enrolled": 55,
                "samples_collected": 60,
                "irb_approval_date": now - timedelta(days=220),
                "irb_expiry_date": now + timedelta(days=145),
            },
        ]

        for s in sites_data:
            self._sites[s["id"]] = SubStudySite(**s)

        # --- 3 Data Sharing Agreements ---
        agreements_data = [
            {
                "id": "DSA-001",
                "ancillary_study_id": "ANC-001",
                "partner_organization": "Genentech Biomarker Lab",
                "agreement_type": AgreementType.DATA_USE_AGREEMENT,
                "effective_date": now - timedelta(days=200),
                "expiry_date": now + timedelta(days=530),
                "data_types_shared": ["biomarker_levels", "clinical_outcomes", "demographics"],
                "restrictions": "Data may not be used for commercial product development without separate license agreement",
                "status": AgreementStatus.ACTIVE,
            },
            {
                "id": "DSA-002",
                "ancillary_study_id": "ANC-003",
                "partner_organization": "Agilent/Dako Pathology",
                "agreement_type": AgreementType.MATERIAL_TRANSFER,
                "effective_date": now - timedelta(days=250),
                "expiry_date": now + timedelta(days=115),
                "data_types_shared": ["tissue_samples", "ihc_staining_data", "pathology_reports"],
                "restrictions": "Tissue blocks must be returned after analysis. No genetic sequencing without amendment.",
                "status": AgreementStatus.ACTIVE,
            },
            {
                "id": "DSA-003",
                "ancillary_study_id": "ANC-002",
                "partner_organization": "University of Michigan PK Core",
                "agreement_type": AgreementType.COLLABORATION,
                "effective_date": now - timedelta(days=120),
                "expiry_date": now + timedelta(days=245),
                "data_types_shared": ["pk_concentrations", "dosing_history", "covariates"],
                "restrictions": "All publications require sponsor review 30 days prior to submission",
                "status": AgreementStatus.ACTIVE,
            },
        ]

        for a in agreements_data:
            self._agreements[a["id"]] = DataSharingAgreement(**a)

    # ------------------------------------------------------------------
    # Study CRUD
    # ------------------------------------------------------------------

    def list_studies(
        self,
        *,
        study_type: AncillaryStudyType | None = None,
        status: AncillaryStatus | None = None,
        parent_trial_id: str | None = None,
    ) -> list[AncillaryStudy]:
        """List ancillary studies with optional filters."""
        with self._lock:
            result = list(self._studies.values())

        if study_type is not None:
            result = [s for s in result if s.study_type == study_type]
        if status is not None:
            result = [s for s in result if s.status == status]
        if parent_trial_id is not None:
            result = [s for s in result if s.parent_trial_id == parent_trial_id]

        return sorted(result, key=lambda s: s.id)

    def get_study(self, study_id: str) -> AncillaryStudy | None:
        """Get a single ancillary study by ID."""
        with self._lock:
            return self._studies.get(study_id)

    def create_study(self, payload: AncillaryStudyCreate) -> AncillaryStudy:
        """Create a new ancillary study."""
        now = datetime.now(timezone.utc)
        study_id = f"ANC-{uuid4().hex[:8].upper()}"
        study = AncillaryStudy(
            id=study_id,
            status=AncillaryStatus.PLANNED,
            current_enrollment=0,
            created_at=now,
            **payload.model_dump(),
        )
        with self._lock:
            self._studies[study_id] = study
        logger.info("Created ancillary study %s: %s", study_id, payload.study_name)
        return study

    def update_study(
        self, study_id: str, payload: AncillaryStudyUpdate
    ) -> AncillaryStudy | None:
        """Update an existing ancillary study."""
        with self._lock:
            existing = self._studies.get(study_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = AncillaryStudy(**data)
            self._studies[study_id] = updated
        return updated

    def delete_study(self, study_id: str) -> bool:
        """Delete an ancillary study. Returns True if deleted."""
        with self._lock:
            if study_id in self._studies:
                del self._studies[study_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Sample Management
    # ------------------------------------------------------------------

    def list_samples(
        self,
        *,
        ancillary_study_id: str | None = None,
        patient_id: str | None = None,
        site_id: str | None = None,
        sample_type: SampleType | None = None,
        analysis_status: AnalysisStatus | None = None,
    ) -> list[StudySample]:
        """List samples with optional filters."""
        with self._lock:
            result = list(self._samples.values())

        if ancillary_study_id is not None:
            result = [s for s in result if s.ancillary_study_id == ancillary_study_id]
        if patient_id is not None:
            result = [s for s in result if s.patient_id == patient_id]
        if site_id is not None:
            result = [s for s in result if s.site_id == site_id]
        if sample_type is not None:
            result = [s for s in result if s.sample_type == sample_type]
        if analysis_status is not None:
            result = [s for s in result if s.analysis_status == analysis_status]

        return sorted(result, key=lambda s: s.collection_date, reverse=True)

    def get_sample(self, sample_id: str) -> StudySample | None:
        """Get a single sample by ID."""
        with self._lock:
            return self._samples.get(sample_id)

    def collect_sample(self, payload: StudySampleCreate) -> StudySample:
        """Register a new sample collection."""
        # Verify study exists
        with self._lock:
            if payload.ancillary_study_id not in self._studies:
                raise ValueError(
                    f"Ancillary study '{payload.ancillary_study_id}' not found"
                )

        sample_id = f"SMP-{uuid4().hex[:8].upper()}"
        sample = StudySample(
            id=sample_id,
            shipped_to_lab=False,
            lab_received_date=None,
            analysis_status=AnalysisStatus.PENDING,
            results_available=False,
            **payload.model_dump(),
        )
        with self._lock:
            self._samples[sample_id] = sample

            # Update site sample count if applicable
            for site in self._sites.values():
                if (
                    site.ancillary_study_id == payload.ancillary_study_id
                    and site.site_id == payload.site_id
                ):
                    site_data = site.model_dump()
                    site_data["samples_collected"] = site.samples_collected + 1
                    self._sites[site.id] = SubStudySite(**site_data)
                    break

        logger.info(
            "Collected sample %s for study %s patient %s",
            sample_id,
            payload.ancillary_study_id,
            payload.patient_id,
        )
        return sample

    def update_sample(
        self, sample_id: str, payload: StudySampleUpdate
    ) -> StudySample | None:
        """Update a sample record (e.g., ship, receive, update analysis)."""
        with self._lock:
            existing = self._samples.get(sample_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = StudySample(**data)
            self._samples[sample_id] = updated
        return updated

    def track_analysis(
        self,
        sample_id: str,
        analysis_status: AnalysisStatus,
        results_available: bool = False,
    ) -> StudySample | None:
        """Update the analysis status and results availability for a sample."""
        with self._lock:
            existing = self._samples.get(sample_id)
            if existing is None:
                return None
            data = existing.model_dump()
            data["analysis_status"] = analysis_status
            data["results_available"] = results_available
            updated = StudySample(**data)
            self._samples[sample_id] = updated
        logger.info(
            "Updated analysis for sample %s: status=%s results=%s",
            sample_id,
            analysis_status.value,
            results_available,
        )
        return updated

    def delete_sample(self, sample_id: str) -> bool:
        """Delete a sample record. Returns True if deleted."""
        with self._lock:
            if sample_id in self._samples:
                del self._samples[sample_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Endpoint Management
    # ------------------------------------------------------------------

    def list_endpoints(
        self,
        *,
        ancillary_study_id: str | None = None,
        endpoint_type: EndpointType | None = None,
    ) -> list[StudyEndpoint]:
        """List endpoints with optional filters."""
        with self._lock:
            result = list(self._endpoints.values())

        if ancillary_study_id is not None:
            result = [e for e in result if e.ancillary_study_id == ancillary_study_id]
        if endpoint_type is not None:
            result = [e for e in result if e.endpoint_type == endpoint_type]

        return sorted(result, key=lambda e: e.id)

    def get_endpoint(self, endpoint_id: str) -> StudyEndpoint | None:
        """Get a single endpoint by ID."""
        with self._lock:
            return self._endpoints.get(endpoint_id)

    def create_endpoint(self, payload: StudyEndpointCreate) -> StudyEndpoint:
        """Create a new study endpoint."""
        with self._lock:
            if payload.ancillary_study_id not in self._studies:
                raise ValueError(
                    f"Ancillary study '{payload.ancillary_study_id}' not found"
                )

        ep_id = f"EP-{uuid4().hex[:8].upper()}"
        endpoint = StudyEndpoint(
            id=ep_id,
            **payload.model_dump(),
        )
        with self._lock:
            self._endpoints[ep_id] = endpoint
        logger.info(
            "Created endpoint %s for study %s",
            ep_id,
            payload.ancillary_study_id,
        )
        return endpoint

    def update_endpoint(
        self, endpoint_id: str, payload: StudyEndpointUpdate
    ) -> StudyEndpoint | None:
        """Update a study endpoint."""
        with self._lock:
            existing = self._endpoints.get(endpoint_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = StudyEndpoint(**data)
            self._endpoints[endpoint_id] = updated
        return updated

    def delete_endpoint(self, endpoint_id: str) -> bool:
        """Delete a study endpoint. Returns True if deleted."""
        with self._lock:
            if endpoint_id in self._endpoints:
                del self._endpoints[endpoint_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Sub-Study Site Management
    # ------------------------------------------------------------------

    def list_sites(
        self,
        *,
        ancillary_study_id: str | None = None,
        status: SubStudySiteStatus | None = None,
    ) -> list[SubStudySite]:
        """List sub-study sites with optional filters."""
        with self._lock:
            result = list(self._sites.values())

        if ancillary_study_id is not None:
            result = [s for s in result if s.ancillary_study_id == ancillary_study_id]
        if status is not None:
            result = [s for s in result if s.status == status]

        return sorted(result, key=lambda s: s.id)

    def get_site(self, site_record_id: str) -> SubStudySite | None:
        """Get a single sub-study site by record ID."""
        with self._lock:
            return self._sites.get(site_record_id)

    def create_site(self, payload: SubStudySiteCreate) -> SubStudySite:
        """Add a site to an ancillary study."""
        with self._lock:
            if payload.ancillary_study_id not in self._studies:
                raise ValueError(
                    f"Ancillary study '{payload.ancillary_study_id}' not found"
                )

        record_id = f"SSS-{uuid4().hex[:8].upper()}"
        site = SubStudySite(
            id=record_id,
            activation_date=None,
            status=SubStudySiteStatus.PENDING,
            patients_enrolled=0,
            samples_collected=0,
            **payload.model_dump(),
        )
        with self._lock:
            self._sites[record_id] = site
        logger.info(
            "Added site %s to study %s",
            payload.site_id,
            payload.ancillary_study_id,
        )
        return site

    def update_site(
        self, site_record_id: str, payload: SubStudySiteUpdate
    ) -> SubStudySite | None:
        """Update a sub-study site record."""
        with self._lock:
            existing = self._sites.get(site_record_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SubStudySite(**data)
            self._sites[site_record_id] = updated
        return updated

    def activate_site(self, site_record_id: str) -> SubStudySite | None:
        """Activate a sub-study site, setting activation date and status."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._sites.get(site_record_id)
            if existing is None:
                return None

            if existing.status not in (
                SubStudySiteStatus.PENDING,
                SubStudySiteStatus.SUSPENDED,
            ):
                raise ValueError(
                    f"Site '{site_record_id}' cannot be activated from "
                    f"status '{existing.status.value}'"
                )

            data = existing.model_dump()
            data["status"] = SubStudySiteStatus.ACTIVATED
            data["activation_date"] = now
            updated = SubStudySite(**data)
            self._sites[site_record_id] = updated
        logger.info("Activated sub-study site %s", site_record_id)
        return updated

    def delete_site(self, site_record_id: str) -> bool:
        """Delete a sub-study site record. Returns True if deleted."""
        with self._lock:
            if site_record_id in self._sites:
                del self._sites[site_record_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Data Sharing Agreements
    # ------------------------------------------------------------------

    def list_agreements(
        self,
        *,
        ancillary_study_id: str | None = None,
        status: AgreementStatus | None = None,
    ) -> list[DataSharingAgreement]:
        """List data sharing agreements with optional filters."""
        with self._lock:
            result = list(self._agreements.values())

        if ancillary_study_id is not None:
            result = [a for a in result if a.ancillary_study_id == ancillary_study_id]
        if status is not None:
            result = [a for a in result if a.status == status]

        return sorted(result, key=lambda a: a.id)

    def get_agreement(self, agreement_id: str) -> DataSharingAgreement | None:
        """Get a single data sharing agreement by ID."""
        with self._lock:
            return self._agreements.get(agreement_id)

    def create_agreement(
        self, payload: DataSharingAgreementCreate
    ) -> DataSharingAgreement:
        """Create a new data sharing agreement."""
        with self._lock:
            if payload.ancillary_study_id not in self._studies:
                raise ValueError(
                    f"Ancillary study '{payload.ancillary_study_id}' not found"
                )

        agreement_id = f"DSA-{uuid4().hex[:8].upper()}"
        agreement = DataSharingAgreement(
            id=agreement_id,
            status=AgreementStatus.DRAFT,
            **payload.model_dump(),
        )
        with self._lock:
            self._agreements[agreement_id] = agreement
        logger.info(
            "Created agreement %s for study %s with %s",
            agreement_id,
            payload.ancillary_study_id,
            payload.partner_organization,
        )
        return agreement

    def update_agreement(
        self, agreement_id: str, payload: DataSharingAgreementUpdate
    ) -> DataSharingAgreement | None:
        """Update a data sharing agreement."""
        with self._lock:
            existing = self._agreements.get(agreement_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DataSharingAgreement(**data)
            self._agreements[agreement_id] = updated
        return updated

    def delete_agreement(self, agreement_id: str) -> bool:
        """Delete a data sharing agreement. Returns True if deleted."""
        with self._lock:
            if agreement_id in self._agreements:
                del self._agreements[agreement_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Study Progress
    # ------------------------------------------------------------------

    def get_study_progress(self, study_id: str) -> StudyProgress | None:
        """Get progress summary for a specific ancillary study."""
        with self._lock:
            study = self._studies.get(study_id)
            if study is None:
                return None

            samples = [
                s for s in self._samples.values()
                if s.ancillary_study_id == study_id
            ]
            endpoints = [
                e for e in self._endpoints.values()
                if e.ancillary_study_id == study_id
            ]
            sites = [
                s for s in self._sites.values()
                if s.ancillary_study_id == study_id
            ]
            agreements = [
                a for a in self._agreements.values()
                if a.ancillary_study_id == study_id
            ]

        enrollment_pct = (
            round(study.current_enrollment / study.target_enrollment * 100, 1)
            if study.target_enrollment > 0
            else 0.0
        )

        analyzed = sum(
            1 for s in samples if s.analysis_status == AnalysisStatus.COMPLETED
        )
        active_sites = sum(
            1 for s in sites
            if s.status in (SubStudySiteStatus.ACTIVATED, SubStudySiteStatus.ENROLLING)
        )
        active_agreements = sum(
            1 for a in agreements if a.status == AgreementStatus.ACTIVE
        )

        return StudyProgress(
            study_id=study_id,
            study_name=study.study_name,
            status=study.status,
            enrollment_percentage=min(enrollment_pct, 100.0),
            samples_collected=len(samples),
            samples_analyzed=analyzed,
            active_sites=active_sites,
            endpoints_defined=len(endpoints),
            agreements_active=active_agreements,
        )

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> AncillaryMetrics:
        """Compute aggregated ancillary study operational metrics."""
        with self._lock:
            studies = list(self._studies.values())
            samples = list(self._samples.values())
            endpoints = list(self._endpoints.values())
            sites = list(self._sites.values())
            agreements = list(self._agreements.values())

        # Studies by type
        by_type: dict[str, int] = {}
        for s in studies:
            key = s.study_type.value
            by_type[key] = by_type.get(key, 0) + 1

        # Studies by status
        by_status: dict[str, int] = {}
        for s in studies:
            key = s.status.value
            by_status[key] = by_status.get(key, 0) + 1

        # Samples
        pending = sum(
            1 for s in samples
            if s.analysis_status in (AnalysisStatus.PENDING, AnalysisStatus.IN_PROGRESS)
        )
        analyzed = sum(
            1 for s in samples if s.analysis_status == AnalysisStatus.COMPLETED
        )

        # Sites
        active_sites = sum(
            1 for s in sites
            if s.status in (SubStudySiteStatus.ACTIVATED, SubStudySiteStatus.ENROLLING)
        )

        # Agreements
        active_agreements = sum(
            1 for a in agreements if a.status == AgreementStatus.ACTIVE
        )

        # Budget and enrollment
        total_budget = sum(s.budget for s in studies)
        total_enrollment = sum(s.current_enrollment for s in studies)

        enrollment_pcts: list[float] = []
        for s in studies:
            if s.target_enrollment > 0:
                pct = min(s.current_enrollment / s.target_enrollment * 100, 100.0)
                enrollment_pcts.append(pct)
        avg_enrollment = (
            round(sum(enrollment_pcts) / len(enrollment_pcts), 1)
            if enrollment_pcts
            else 0.0
        )

        return AncillaryMetrics(
            total_studies=len(studies),
            studies_by_type=by_type,
            studies_by_status=by_status,
            total_samples=len(samples),
            samples_pending_analysis=pending,
            samples_analyzed=analyzed,
            total_endpoints=len(endpoints),
            total_sites=len(sites),
            active_sites=active_sites,
            total_agreements=len(agreements),
            active_agreements=active_agreements,
            total_budget=total_budget,
            total_enrollment=total_enrollment,
            avg_enrollment_percentage=avg_enrollment,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: AncillaryStudyService | None = None
_instance_lock = threading.Lock()


def get_ancillary_study_service() -> AncillaryStudyService:
    """Return the singleton AncillaryStudyService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = AncillaryStudyService()
    return _instance


def reset_ancillary_study_service() -> AncillaryStudyService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = AncillaryStudyService()
    return _instance
