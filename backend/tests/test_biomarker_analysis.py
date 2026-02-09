"""Tests for Biomarker Analysis & Real-World Evidence (VP-DS-9).

Covers:
- Seed data verification (12 biomarkers, 15 associations, 30 patient values,
  3 panels, 4 RWE studies, 2 comparabilities)
- Biomarker CRUD + lifecycle transitions
- Association analysis (create, query by biomarker/condition)
- Patient biomarker recording + abnormality detection
- Panel management + composite scoring
- RWE study CRUD + completion
- Propensity score matching simulation
- RWE-RCT comparability assessment
- Patient stratification
- Enrichment analysis
- Biomarker metrics
- RWE metrics
- API integration (all 32 endpoints)
- Error handling (404s, invalid status transitions)
"""

from __future__ import annotations

from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.biomarker_analysis import (
    AssociationCreateRequest,
    BiomarkerCreateRequest,
    BiomarkerRole,
    BiomarkerStatus,
    BiomarkerType,
    ComparabilityCreateRequest,
    EvidenceLevel,
    MatchingMethod,
    PanelCreateRequest,
    PatientBiomarkerRequest,
    RWEStudyCreateRequest,
    RWEStudyType,
)
from app.services.biomarker_analysis_service import (
    DUPIXENT_TRIAL_ID,
    EYLEA_TRIAL_ID,
    LIBTAYO_TRIAL_ID,
    PATIENT_IDS,
    BiomarkerAnalysisService,
    get_biomarker_analysis_service,
    reset_biomarker_analysis_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_PREFIX = "/api/v1/biomarker-analysis"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_biomarker_analysis_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> BiomarkerAnalysisService:
    """Shorthand for the fresh service."""
    return fresh_service


# ===========================================================================
# Section 1: Seed data verification
# ===========================================================================


class TestSeedData:
    """Verify the seed data is loaded correctly on service init."""

    def test_seed_twelve_biomarkers(self, svc: BiomarkerAnalysisService):
        """Seed should contain exactly 12 biomarkers."""
        bms = svc.list_biomarkers()
        assert len(bms) == 12

    def test_seed_vegfa_biomarker(self, svc: BiomarkerAnalysisService):
        """VEGF-A biomarker should have correct properties."""
        bm = svc.get_biomarker("BM-0001")
        assert bm is not None
        assert bm.name == "VEGF-A"
        assert bm.biomarker_type == BiomarkerType.PROTEOMIC
        assert bm.role == BiomarkerRole.PREDICTIVE
        assert bm.status == BiomarkerStatus.APPROVED
        assert bm.sensitivity == 0.89
        assert bm.specificity == 0.82
        assert bm.auc_roc == 0.91

    def test_seed_hba1c_biomarker(self, svc: BiomarkerAnalysisService):
        """HbA1c biomarker should have correct properties."""
        bm = svc.get_biomarker("BM-0002")
        assert bm is not None
        assert bm.name == "HbA1c"
        assert bm.biomarker_type == BiomarkerType.CLINICAL_MEASUREMENT
        assert bm.role == BiomarkerRole.PROGNOSTIC

    def test_seed_crt_biomarker(self, svc: BiomarkerAnalysisService):
        """Central Retinal Thickness biomarker should exist."""
        bm = svc.get_biomarker("BM-0003")
        assert bm is not None
        assert bm.name == "Central Retinal Thickness"
        assert bm.biomarker_type == BiomarkerType.IMAGING

    def test_seed_bcva_biomarker(self, svc: BiomarkerAnalysisService):
        """Visual Acuity BCVA biomarker should exist."""
        bm = svc.get_biomarker("BM-0004")
        assert bm is not None
        assert bm.role == BiomarkerRole.SURROGATE_ENDPOINT

    def test_seed_ige_biomarker(self, svc: BiomarkerAnalysisService):
        """IgE Total biomarker for Dupixent should exist."""
        bm = svc.get_biomarker("BM-0005")
        assert bm is not None
        assert bm.name == "IgE Total"
        assert DUPIXENT_TRIAL_ID in bm.associated_trials

    def test_seed_easi_biomarker(self, svc: BiomarkerAnalysisService):
        """EASI Score biomarker should be COMPOSITE type."""
        bm = svc.get_biomarker("BM-0006")
        assert bm is not None
        assert bm.biomarker_type == BiomarkerType.COMPOSITE

    def test_seed_tarc_biomarker(self, svc: BiomarkerAnalysisService):
        """TARC biomarker should exist with correct protein target."""
        bm = svc.get_biomarker("BM-0007")
        assert bm is not None
        assert bm.protein_target == "CCL17"

    def test_seed_pdl1_biomarker(self, svc: BiomarkerAnalysisService):
        """PD-L1 Expression biomarker for Libtayo should exist."""
        bm = svc.get_biomarker("BM-0008")
        assert bm is not None
        assert LIBTAYO_TRIAL_ID in bm.associated_trials

    def test_seed_tmb_biomarker(self, svc: BiomarkerAnalysisService):
        """Tumor Mutation Burden biomarker should be GENOMIC type."""
        bm = svc.get_biomarker("BM-0009")
        assert bm is not None
        assert bm.biomarker_type == BiomarkerType.GENOMIC

    def test_seed_cd8_biomarker(self, svc: BiomarkerAnalysisService):
        """CD8+ TIL Density biomarker should exist."""
        bm = svc.get_biomarker("BM-0010")
        assert bm is not None
        assert bm.protein_target == "CD8"

    def test_seed_il4_biomarker(self, svc: BiomarkerAnalysisService):
        """IL-4/IL-13 signaling biomarker should be DISCOVERED status."""
        bm = svc.get_biomarker("BM-0011")
        assert bm is not None
        assert bm.status == BiomarkerStatus.DISCOVERED

    def test_seed_ada_biomarker(self, svc: BiomarkerAnalysisService):
        """Anti-drug antibodies biomarker should span all 3 trials."""
        bm = svc.get_biomarker("BM-0012")
        assert bm is not None
        assert bm.role == BiomarkerRole.SAFETY
        assert len(bm.associated_trials) == 3

    def test_seed_fifteen_associations(self, svc: BiomarkerAnalysisService):
        """Seed should contain exactly 15 associations."""
        assocs = svc.list_associations()
        assert len(assocs) == 15

    def test_seed_thirty_patient_values(self, svc: BiomarkerAnalysisService):
        """Seed should contain exactly 30 patient biomarker values."""
        vals = svc.list_patient_values()
        assert len(vals) == 30

    def test_seed_three_panels(self, svc: BiomarkerAnalysisService):
        """Seed should contain exactly 3 panels."""
        panels = svc.list_panels()
        assert len(panels) == 3

    def test_seed_dme_panel(self, svc: BiomarkerAnalysisService):
        """DME Progression Panel should contain 4 biomarkers."""
        panel = svc.get_panel("PNL-0001")
        assert panel is not None
        assert panel.name == "DME Progression Panel"
        assert len(panel.biomarkers) == 4
        assert panel.panel_sensitivity == 0.93

    def test_seed_ad_panel(self, svc: BiomarkerAnalysisService):
        """AD Severity Panel should contain 4 biomarkers."""
        panel = svc.get_panel("PNL-0002")
        assert panel is not None
        assert panel.target_condition == "Atopic Dermatitis"
        assert len(panel.biomarkers) == 4

    def test_seed_cscc_panel(self, svc: BiomarkerAnalysisService):
        """CSCC Response Panel should contain 3 biomarkers."""
        panel = svc.get_panel("PNL-0003")
        assert panel is not None
        assert len(panel.biomarkers) == 3

    def test_seed_four_rwe_studies(self, svc: BiomarkerAnalysisService):
        """Seed should contain exactly 4 RWE studies."""
        studies = svc.list_rwe_studies()
        assert len(studies) == 4

    def test_seed_dme_rwe_study(self, svc: BiomarkerAnalysisService):
        """DME Treatment Outcomes study should be completed."""
        study = svc.get_rwe_study("RWE-0001")
        assert study is not None
        assert study.study_type == RWEStudyType.RETROSPECTIVE_COHORT
        assert study.status == "COMPLETED"
        assert study.sample_size == 12500

    def test_seed_dupixent_rwe_study(self, svc: BiomarkerAnalysisService):
        """Dupixent RWE study should use IPW matching."""
        study = svc.get_rwe_study("RWE-0002")
        assert study is not None
        assert study.matching_method == MatchingMethod.INVERSE_PROBABILITY_WEIGHTING

    def test_seed_cscc_rwe_study(self, svc: BiomarkerAnalysisService):
        """CSCC RWE study should use coarsened exact matching."""
        study = svc.get_rwe_study("RWE-0003")
        assert study is not None
        assert study.matching_method == MatchingMethod.COARSENED_EXACT

    def test_seed_target_trial_emulation(self, svc: BiomarkerAnalysisService):
        """Comparative effectiveness study should be target trial emulation."""
        study = svc.get_rwe_study("RWE-0004")
        assert study is not None
        assert study.study_type == RWEStudyType.TARGET_TRIAL_EMULATION

    def test_seed_two_comparabilities(self, svc: BiomarkerAnalysisService):
        """Seed should contain exactly 2 comparability assessments."""
        comps = svc.list_comparabilities()
        assert len(comps) == 2

    def test_seed_comparability_agreement_scores(self, svc: BiomarkerAnalysisService):
        """Comparability agreement scores should be between 0 and 1."""
        comps = svc.list_comparabilities()
        for c in comps:
            assert 0.0 <= c.agreement_score <= 1.0


# ===========================================================================
# Section 2: Biomarker CRUD
# ===========================================================================


class TestBiomarkerCRUD:
    """Test biomarker create, read, update status, and delete."""

    def test_create_biomarker(self, svc: BiomarkerAnalysisService):
        """Creating a biomarker should return a valid object with DISCOVERED status."""
        req = BiomarkerCreateRequest(
            name="Novel Biomarker X",
            biomarker_type=BiomarkerType.GENOMIC,
            role=BiomarkerRole.PREDICTIVE,
            description="Test biomarker",
            gene_symbol="NOVX",
            measurement_unit="copies/mL",
        )
        bm = svc.create_biomarker(req)
        assert bm.id.startswith("BM-")
        assert bm.name == "Novel Biomarker X"
        assert bm.status == BiomarkerStatus.DISCOVERED

    def test_create_biomarker_persists(self, svc: BiomarkerAnalysisService):
        """Created biomarker should be retrievable."""
        req = BiomarkerCreateRequest(
            name="Test Persist",
            biomarker_type=BiomarkerType.METABOLOMIC,
            role=BiomarkerRole.DIAGNOSTIC,
        )
        bm = svc.create_biomarker(req)
        retrieved = svc.get_biomarker(bm.id)
        assert retrieved is not None
        assert retrieved.name == "Test Persist"

    def test_list_biomarkers_filter_by_type(self, svc: BiomarkerAnalysisService):
        """Filtering by type should return correct subset."""
        genomic = svc.list_biomarkers(biomarker_type=BiomarkerType.GENOMIC)
        assert len(genomic) >= 1
        for bm in genomic:
            assert bm.biomarker_type == BiomarkerType.GENOMIC

    def test_list_biomarkers_filter_by_role(self, svc: BiomarkerAnalysisService):
        """Filtering by role should return correct subset."""
        predictive = svc.list_biomarkers(role=BiomarkerRole.PREDICTIVE)
        assert len(predictive) >= 1
        for bm in predictive:
            assert bm.role == BiomarkerRole.PREDICTIVE

    def test_list_biomarkers_filter_by_status(self, svc: BiomarkerAnalysisService):
        """Filtering by status should return correct subset."""
        approved = svc.list_biomarkers(status=BiomarkerStatus.APPROVED)
        assert len(approved) >= 1
        for bm in approved:
            assert bm.status == BiomarkerStatus.APPROVED

    def test_delete_biomarker(self, svc: BiomarkerAnalysisService):
        """Deleting a biomarker should remove it."""
        assert svc.delete_biomarker("BM-0001") is True
        assert svc.get_biomarker("BM-0001") is None

    def test_delete_nonexistent_biomarker(self, svc: BiomarkerAnalysisService):
        """Deleting a nonexistent biomarker should return False."""
        assert svc.delete_biomarker("BM-9999") is False

    def test_get_nonexistent_biomarker(self, svc: BiomarkerAnalysisService):
        """Getting a nonexistent biomarker should return None."""
        assert svc.get_biomarker("BM-9999") is None


# ===========================================================================
# Section 3: Biomarker lifecycle status transitions
# ===========================================================================


class TestBiomarkerLifecycle:
    """Test biomarker status lifecycle transitions."""

    def test_discovered_to_validated(self, svc: BiomarkerAnalysisService):
        """DISCOVERED -> VALIDATED should succeed."""
        result = svc.update_biomarker_status("BM-0011", BiomarkerStatus.VALIDATED)
        assert result is not None
        assert result.status == BiomarkerStatus.VALIDATED

    def test_validated_to_qualified(self, svc: BiomarkerAnalysisService):
        """VALIDATED -> QUALIFIED should succeed."""
        # BM-0005 is VALIDATED
        result = svc.update_biomarker_status("BM-0005", BiomarkerStatus.QUALIFIED)
        assert result is not None
        assert result.status == BiomarkerStatus.QUALIFIED

    def test_qualified_to_approved(self, svc: BiomarkerAnalysisService):
        """QUALIFIED -> APPROVED should succeed."""
        # BM-0003 is QUALIFIED
        result = svc.update_biomarker_status("BM-0003", BiomarkerStatus.APPROVED)
        assert result is not None
        assert result.status == BiomarkerStatus.APPROVED

    def test_discovered_to_rejected(self, svc: BiomarkerAnalysisService):
        """DISCOVERED -> REJECTED should succeed."""
        result = svc.update_biomarker_status("BM-0011", BiomarkerStatus.REJECTED)
        assert result is not None
        assert result.status == BiomarkerStatus.REJECTED

    def test_invalid_transition_discovered_to_approved(self, svc: BiomarkerAnalysisService):
        """DISCOVERED -> APPROVED should fail (skip steps)."""
        result = svc.update_biomarker_status("BM-0011", BiomarkerStatus.APPROVED)
        assert result is None

    def test_invalid_transition_rejected_to_validated(self, svc: BiomarkerAnalysisService):
        """REJECTED -> anything should fail."""
        svc.update_biomarker_status("BM-0011", BiomarkerStatus.REJECTED)
        result = svc.update_biomarker_status("BM-0011", BiomarkerStatus.VALIDATED)
        assert result is None

    def test_status_update_nonexistent(self, svc: BiomarkerAnalysisService):
        """Updating status of nonexistent biomarker should return None."""
        result = svc.update_biomarker_status("BM-9999", BiomarkerStatus.VALIDATED)
        assert result is None


# ===========================================================================
# Section 4: Association analysis
# ===========================================================================


class TestAssociations:
    """Test biomarker-condition association management."""

    def test_create_association(self, svc: BiomarkerAnalysisService):
        """Creating an association should return a valid object."""
        req = AssociationCreateRequest(
            biomarker_id="BM-0001",
            condition="Retinal Vein Occlusion",
            effect_size=0.55,
            p_value=0.01,
            confidence_interval=(0.35, 0.75),
            sample_size=200,
            study_reference="RVO Study 2024",
            population="RVO patients",
        )
        assoc = svc.create_association(req)
        assert assoc is not None
        assert assoc.id.startswith("BA-")
        assert assoc.effect_size == 0.55

    def test_create_association_invalid_biomarker(self, svc: BiomarkerAnalysisService):
        """Creating an association with nonexistent biomarker should return None."""
        req = AssociationCreateRequest(
            biomarker_id="BM-9999",
            condition="Test",
            effect_size=0.5,
            p_value=0.05,
        )
        assert svc.create_association(req) is None

    def test_get_associations_by_biomarker(self, svc: BiomarkerAnalysisService):
        """Getting associations by biomarker should return correct results."""
        assocs = svc.get_associations_by_biomarker("BM-0001")
        assert len(assocs) >= 2  # VEGF-A has DME and Wet AMD
        for a in assocs:
            assert a.biomarker_id == "BM-0001"

    def test_get_associations_by_condition(self, svc: BiomarkerAnalysisService):
        """Getting associations by condition should do case-insensitive search."""
        assocs = svc.get_associations_by_condition("diabetic macular edema")
        assert len(assocs) >= 3

    def test_get_associations_by_condition_partial(self, svc: BiomarkerAnalysisService):
        """Partial condition match should work."""
        assocs = svc.get_associations_by_condition("Atopic")
        assert len(assocs) >= 3

    def test_association_has_p_value(self, svc: BiomarkerAnalysisService):
        """All associations should have p-values <= 0.05."""
        assocs = svc.list_associations()
        for a in assocs:
            assert a.p_value <= 0.05

    def test_association_has_effect_size(self, svc: BiomarkerAnalysisService):
        """All associations should have non-zero effect sizes."""
        assocs = svc.list_associations()
        for a in assocs:
            assert a.effect_size != 0.0


# ===========================================================================
# Section 5: Patient biomarker values
# ===========================================================================


class TestPatientBiomarkers:
    """Test patient biomarker value recording and retrieval."""

    def test_record_patient_biomarker(self, svc: BiomarkerAnalysisService):
        """Recording a biomarker value should return valid result."""
        req = PatientBiomarkerRequest(
            patient_id="PAT-NEW",
            biomarker_id="BM-0001",
            value=75.0,
            source="Lab Report",
        )
        pv = svc.record_patient_biomarker(req)
        assert pv is not None
        assert pv.patient_id == "PAT-NEW"
        assert pv.value == 75.0
        assert pv.is_abnormal is True  # 75 > normal_range_high (50)

    def test_record_normal_value(self, svc: BiomarkerAnalysisService):
        """Recording a normal value should not be flagged abnormal."""
        req = PatientBiomarkerRequest(
            patient_id="PAT-NEW",
            biomarker_id="BM-0001",
            value=30.0,
            source="Lab Report",
        )
        pv = svc.record_patient_biomarker(req)
        assert pv is not None
        assert pv.is_abnormal is False  # 30 is within 10-50

    def test_record_below_normal(self, svc: BiomarkerAnalysisService):
        """Value below normal range should be flagged abnormal."""
        req = PatientBiomarkerRequest(
            patient_id="PAT-NEW",
            biomarker_id="BM-0002",  # HbA1c: 4.0-5.6
            value=3.5,
            source="Lab Report",
        )
        pv = svc.record_patient_biomarker(req)
        assert pv is not None
        assert pv.is_abnormal is True

    def test_record_invalid_biomarker(self, svc: BiomarkerAnalysisService):
        """Recording value for nonexistent biomarker should return None."""
        req = PatientBiomarkerRequest(
            patient_id="PAT-NEW",
            biomarker_id="BM-9999",
            value=50.0,
        )
        assert svc.record_patient_biomarker(req) is None

    def test_get_patient_biomarkers(self, svc: BiomarkerAnalysisService):
        """Getting patient biomarkers should return correct results."""
        vals = svc.get_patient_biomarkers("PAT-0001")
        assert len(vals) == 3  # Each patient gets 3 measurements

    def test_get_biomarker_patient_values(self, svc: BiomarkerAnalysisService):
        """Getting values by biomarker should return measurements."""
        vals = svc.get_biomarker_patient_values("BM-0001")
        assert len(vals) >= 1

    def test_patient_values_have_dates(self, svc: BiomarkerAnalysisService):
        """All patient values should have measurement dates."""
        vals = svc.list_patient_values()
        for v in vals:
            assert v.measurement_date is not None

    def test_patient_values_have_sources(self, svc: BiomarkerAnalysisService):
        """All seed patient values should have EHR Import source."""
        vals = svc.list_patient_values()
        for v in vals:
            assert v.source == "EHR Import"


# ===========================================================================
# Section 6: Panel management
# ===========================================================================


class TestPanels:
    """Test biomarker panel management and composite scoring."""

    def test_create_panel(self, svc: BiomarkerAnalysisService):
        """Creating a panel should calculate composite sensitivity/specificity."""
        req = PanelCreateRequest(
            name="Test Panel",
            description="A test panel",
            biomarkers=["BM-0001", "BM-0002"],
            target_condition="Test Condition",
        )
        panel = svc.create_panel(req)
        assert panel.id.startswith("PNL-")
        assert panel.name == "Test Panel"
        assert panel.panel_sensitivity is not None
        assert panel.panel_specificity is not None

    def test_create_panel_composite_sensitivity(self, svc: BiomarkerAnalysisService):
        """Panel sensitivity should be >= individual biomarker sensitivities (parallel test)."""
        req = PanelCreateRequest(
            name="High Sens Panel",
            biomarkers=["BM-0001", "BM-0002"],
            target_condition="DME",
        )
        panel = svc.create_panel(req)
        bm1 = svc.get_biomarker("BM-0001")
        bm2 = svc.get_biomarker("BM-0002")
        # Parallel testing: combined sensitivity >= max individual
        assert panel.panel_sensitivity >= max(bm1.sensitivity, bm2.sensitivity)

    def test_get_panel(self, svc: BiomarkerAnalysisService):
        """Getting a panel by ID should work."""
        panel = svc.get_panel("PNL-0001")
        assert panel is not None
        assert panel.name == "DME Progression Panel"

    def test_get_nonexistent_panel(self, svc: BiomarkerAnalysisService):
        """Getting a nonexistent panel should return None."""
        assert svc.get_panel("PNL-9999") is None

    def test_score_patient_panel(self, svc: BiomarkerAnalysisService):
        """Scoring a patient against a panel should return results."""
        result = svc.score_patient_panel("PNL-0001", "PAT-0001")
        assert result is not None
        assert result["panel_id"] == "PNL-0001"
        assert result["patient_id"] == "PAT-0001"
        assert "results" in result
        assert "completeness" in result
        assert "abnormal_ratio" in result

    def test_score_patient_panel_nonexistent(self, svc: BiomarkerAnalysisService):
        """Scoring against nonexistent panel should return None."""
        assert svc.score_patient_panel("PNL-9999", "PAT-0001") is None

    def test_score_patient_completeness(self, svc: BiomarkerAnalysisService):
        """Completeness should be between 0 and 1."""
        result = svc.score_patient_panel("PNL-0001", "PAT-0001")
        assert result is not None
        assert 0.0 <= result["completeness"] <= 1.0

    def test_score_patient_total_biomarkers(self, svc: BiomarkerAnalysisService):
        """Total biomarkers in score should match panel."""
        result = svc.score_patient_panel("PNL-0001", "PAT-0001")
        assert result is not None
        assert result["total_biomarkers"] == 4


# ===========================================================================
# Section 7: RWE Study CRUD
# ===========================================================================


class TestRWEStudies:
    """Test RWE study create, read, complete, and delete."""

    def test_create_rwe_study(self, svc: BiomarkerAnalysisService):
        """Creating an RWE study should return a valid object."""
        req = RWEStudyCreateRequest(
            title="New RWE Study",
            study_type=RWEStudyType.CASE_CONTROL,
            description="Test study",
            data_source="Test Database",
            sample_size=500,
            primary_endpoint="Overall survival",
            matching_method=MatchingMethod.EXACT,
            covariates=["age", "sex"],
        )
        study = svc.create_rwe_study(req)
        assert study.id.startswith("RWE-")
        assert study.status == "ACTIVE"

    def test_list_rwe_studies_filter_by_type(self, svc: BiomarkerAnalysisService):
        """Filtering by study type should return correct subset."""
        retro = svc.list_rwe_studies(study_type=RWEStudyType.RETROSPECTIVE_COHORT)
        assert len(retro) >= 2
        for s in retro:
            assert s.study_type == RWEStudyType.RETROSPECTIVE_COHORT

    def test_list_rwe_studies_filter_by_status(self, svc: BiomarkerAnalysisService):
        """Filtering by status should return correct subset."""
        completed = svc.list_rwe_studies(status="COMPLETED")
        assert len(completed) >= 3

    def test_complete_rwe_study(self, svc: BiomarkerAnalysisService):
        """Completing a study should update results and status."""
        # Create new study first
        req = RWEStudyCreateRequest(
            title="Study to Complete",
            study_type=RWEStudyType.CROSS_SECTIONAL,
            sample_size=1000,
        )
        study = svc.create_rwe_study(req)
        result = svc.complete_rwe_study(
            study_id=study.id,
            results_summary="Positive results",
            treatment_effect=0.75,
            confidence_interval=(0.60, 0.90),
            p_value=0.01,
            bias_assessment="Low risk",
        )
        assert result is not None
        assert result.status == "COMPLETED"
        assert result.treatment_effect == 0.75

    def test_complete_nonexistent_study(self, svc: BiomarkerAnalysisService):
        """Completing a nonexistent study should return None."""
        result = svc.complete_rwe_study(
            "RWE-9999", "test", 0.5, (0.3, 0.7), 0.05,
        )
        assert result is None

    def test_delete_rwe_study(self, svc: BiomarkerAnalysisService):
        """Deleting an RWE study should remove it."""
        assert svc.delete_rwe_study("RWE-0001") is True
        assert svc.get_rwe_study("RWE-0001") is None

    def test_delete_nonexistent_study(self, svc: BiomarkerAnalysisService):
        """Deleting a nonexistent study should return False."""
        assert svc.delete_rwe_study("RWE-9999") is False

    def test_get_nonexistent_study(self, svc: BiomarkerAnalysisService):
        """Getting a nonexistent study should return None."""
        assert svc.get_rwe_study("RWE-9999") is None

    def test_rwe_study_has_covariates(self, svc: BiomarkerAnalysisService):
        """RWE studies should have covariates."""
        study = svc.get_rwe_study("RWE-0001")
        assert len(study.covariates) >= 5


# ===========================================================================
# Section 8: Propensity score matching
# ===========================================================================


class TestPropensityScoreMatching:
    """Test propensity score matching simulation."""

    def test_run_propensity_score(self, svc: BiomarkerAnalysisService):
        """Running PS matching should return valid results."""
        result = svc.run_propensity_score_matching("RWE-0001")
        assert result is not None
        assert result.treatment_group_size > 0
        assert result.control_group_size > 0
        assert result.matched_pairs > 0
        assert result.ate is not None
        assert result.att is not None

    def test_ps_balance_metrics(self, svc: BiomarkerAnalysisService):
        """PS matching should generate balance metrics for each covariate."""
        result = svc.run_propensity_score_matching("RWE-0001")
        study = svc.get_rwe_study("RWE-0001")
        assert len(result.balance_metrics) == len(study.covariates)

    def test_ps_standardized_mean_differences(self, svc: BiomarkerAnalysisService):
        """PS matching should generate SMDs for each covariate."""
        result = svc.run_propensity_score_matching("RWE-0001")
        study = svc.get_rwe_study("RWE-0001")
        assert len(result.standardized_mean_differences) == len(study.covariates)

    def test_ps_smd_bounds(self, svc: BiomarkerAnalysisService):
        """SMDs should be small (well-balanced) after matching."""
        result = svc.run_propensity_score_matching("RWE-0001")
        for smd in result.standardized_mean_differences.values():
            assert abs(smd) < 0.1

    def test_ps_matched_pairs_reasonable(self, svc: BiomarkerAnalysisService):
        """Matched pairs should be <= min(treatment, control)."""
        result = svc.run_propensity_score_matching("RWE-0001")
        assert result.matched_pairs <= min(result.treatment_group_size, result.control_group_size)

    def test_ps_nonexistent_study(self, svc: BiomarkerAnalysisService):
        """PS matching on nonexistent study should return None."""
        assert svc.run_propensity_score_matching("RWE-9999") is None


# ===========================================================================
# Section 9: RWE-RCT Comparability
# ===========================================================================


class TestComparability:
    """Test RWE-RCT comparability assessment."""

    def test_create_comparability(self, svc: BiomarkerAnalysisService):
        """Creating a comparability should auto-calculate agreement score."""
        req = ComparabilityCreateRequest(
            rwe_study_id="RWE-0003",
            rct_reference="EMPOWER-CSCC-1",
            endpoint_comparison="ORR",
            rwe_effect_size=0.65,
            rct_effect_size=0.70,
            assessment_notes="Close agreement",
        )
        cmp = svc.create_comparability(req)
        assert cmp is not None
        assert cmp.id.startswith("CMP-")
        assert 0.0 <= cmp.agreement_score <= 1.0

    def test_create_comparability_invalid_study(self, svc: BiomarkerAnalysisService):
        """Creating comparability with nonexistent study should return None."""
        req = ComparabilityCreateRequest(
            rwe_study_id="RWE-9999",
            rct_reference="Test",
        )
        assert svc.create_comparability(req) is None

    def test_get_comparability(self, svc: BiomarkerAnalysisService):
        """Getting a comparability by ID should work."""
        cmp = svc.get_comparability("CMP-0001")
        assert cmp is not None
        assert cmp.rwe_study_id == "RWE-0001"

    def test_get_comparabilities_by_study(self, svc: BiomarkerAnalysisService):
        """Getting comparabilities by study should return correct results."""
        comps = svc.get_comparabilities_by_study("RWE-0001")
        assert len(comps) == 1
        assert comps[0].rct_reference == "PHOTON Phase 3 (NCT04429503)"

    def test_agreement_score_calculation(self, svc: BiomarkerAnalysisService):
        """Agreement score should be high when effect sizes are similar."""
        req = ComparabilityCreateRequest(
            rwe_study_id="RWE-0001",
            rct_reference="Test RCT",
            rwe_effect_size=0.90,
            rct_effect_size=0.90,
        )
        cmp = svc.create_comparability(req)
        assert cmp.agreement_score == 1.0

    def test_agreement_score_low(self, svc: BiomarkerAnalysisService):
        """Agreement score should be low when effect sizes diverge."""
        req = ComparabilityCreateRequest(
            rwe_study_id="RWE-0001",
            rct_reference="Test RCT",
            rwe_effect_size=0.30,
            rct_effect_size=0.90,
        )
        cmp = svc.create_comparability(req)
        assert cmp.agreement_score < 0.7


# ===========================================================================
# Section 10: Stratification
# ===========================================================================


class TestStratification:
    """Test patient stratification by biomarker values."""

    def test_stratify_with_default_threshold(self, svc: BiomarkerAnalysisService):
        """Stratifying should use normal_range_high as default threshold."""
        result = svc.stratify_patients("BM-0001")
        assert result is not None
        assert result.biomarker_name == "VEGF-A"
        assert result.threshold == 50.0  # normal_range_high
        assert result.above_count + result.below_count >= 1

    def test_stratify_with_custom_threshold(self, svc: BiomarkerAnalysisService):
        """Stratifying with custom threshold should work."""
        result = svc.stratify_patients("BM-0001", threshold=30.0)
        assert result is not None
        assert result.threshold == 30.0

    def test_stratify_nonexistent_biomarker(self, svc: BiomarkerAnalysisService):
        """Stratifying with nonexistent biomarker should return None."""
        assert svc.stratify_patients("BM-9999") is None

    def test_stratify_groups_are_disjoint(self, svc: BiomarkerAnalysisService):
        """Above and below groups should have no overlap."""
        result = svc.stratify_patients("BM-0001")
        if result and result.above_threshold and result.below_threshold:
            assert set(result.above_threshold).isdisjoint(set(result.below_threshold))

    def test_stratify_mean_above_threshold(self, svc: BiomarkerAnalysisService):
        """Mean of above group should be >= threshold."""
        result = svc.stratify_patients("BM-0001")
        if result and result.above_mean is not None:
            assert result.above_mean >= result.threshold


# ===========================================================================
# Section 11: Enrichment analysis
# ===========================================================================


class TestEnrichment:
    """Test biomarker enrichment analysis."""

    def test_enrichment_vegfa(self, svc: BiomarkerAnalysisService):
        """VEGF-A enrichment should have positive enrichment score."""
        result = svc.enrichment_analysis("BM-0001")
        assert result is not None
        assert result.biomarker_name == "VEGF-A"
        assert result.enrichment_score > 0

    def test_enrichment_predictive_value(self, svc: BiomarkerAnalysisService):
        """Enrichment should report a predictive value."""
        result = svc.enrichment_analysis("BM-0001")
        assert result is not None
        assert result.predictive_value > 0

    def test_enrichment_recommended_threshold(self, svc: BiomarkerAnalysisService):
        """Enrichment should recommend a threshold for biomarkers with normal ranges."""
        result = svc.enrichment_analysis("BM-0001")
        assert result is not None
        assert result.recommended_threshold == 50.0

    def test_enrichment_sample_size(self, svc: BiomarkerAnalysisService):
        """Enrichment sample size should aggregate across associations."""
        result = svc.enrichment_analysis("BM-0001")
        assert result is not None
        assert result.sample_size > 0

    def test_enrichment_nonexistent_biomarker(self, svc: BiomarkerAnalysisService):
        """Enrichment of nonexistent biomarker should return None."""
        assert svc.enrichment_analysis("BM-9999") is None


# ===========================================================================
# Section 12: Biomarker metrics
# ===========================================================================


class TestBiomarkerMetrics:
    """Test biomarker aggregate metrics."""

    def test_biomarker_metrics_total(self, svc: BiomarkerAnalysisService):
        """Total biomarkers should be 12."""
        metrics = svc.get_biomarker_metrics()
        assert metrics.total_biomarkers == 12

    def test_biomarker_metrics_by_status(self, svc: BiomarkerAnalysisService):
        """Metrics should break down by status."""
        metrics = svc.get_biomarker_metrics()
        assert len(metrics.by_status) >= 3  # DISCOVERED, VALIDATED, QUALIFIED, APPROVED

    def test_biomarker_metrics_by_type(self, svc: BiomarkerAnalysisService):
        """Metrics should break down by biomarker type."""
        metrics = svc.get_biomarker_metrics()
        assert "PROTEOMIC" in metrics.by_type
        assert "GENOMIC" in metrics.by_type

    def test_biomarker_metrics_by_role(self, svc: BiomarkerAnalysisService):
        """Metrics should break down by biomarker role."""
        metrics = svc.get_biomarker_metrics()
        assert "PREDICTIVE" in metrics.by_role
        assert "PROGNOSTIC" in metrics.by_role

    def test_biomarker_metrics_avg_sensitivity(self, svc: BiomarkerAnalysisService):
        """Average sensitivity should be reasonable."""
        metrics = svc.get_biomarker_metrics()
        assert metrics.avg_sensitivity is not None
        assert 0.5 < metrics.avg_sensitivity < 1.0

    def test_biomarker_metrics_avg_specificity(self, svc: BiomarkerAnalysisService):
        """Average specificity should be reasonable."""
        metrics = svc.get_biomarker_metrics()
        assert metrics.avg_specificity is not None
        assert 0.5 < metrics.avg_specificity < 1.0

    def test_biomarker_metrics_avg_auc(self, svc: BiomarkerAnalysisService):
        """Average AUC-ROC should be reasonable."""
        metrics = svc.get_biomarker_metrics()
        assert metrics.avg_auc_roc is not None
        assert 0.5 < metrics.avg_auc_roc < 1.0

    def test_biomarker_metrics_associations_count(self, svc: BiomarkerAnalysisService):
        """Total associations count should be 15."""
        metrics = svc.get_biomarker_metrics()
        assert metrics.total_associations == 15

    def test_biomarker_metrics_panels_count(self, svc: BiomarkerAnalysisService):
        """Total panels count should be 3."""
        metrics = svc.get_biomarker_metrics()
        assert metrics.total_panels == 3

    def test_biomarker_metrics_patient_values_count(self, svc: BiomarkerAnalysisService):
        """Total patient values count should be 30."""
        metrics = svc.get_biomarker_metrics()
        assert metrics.total_patient_values == 30


# ===========================================================================
# Section 13: RWE metrics
# ===========================================================================


class TestRWEMetrics:
    """Test RWE aggregate metrics."""

    def test_rwe_metrics_total_studies(self, svc: BiomarkerAnalysisService):
        """Total RWE studies should be 4."""
        metrics = svc.get_rwe_metrics()
        assert metrics.total_studies == 4

    def test_rwe_metrics_by_study_type(self, svc: BiomarkerAnalysisService):
        """Metrics should break down by study type."""
        metrics = svc.get_rwe_metrics()
        assert "RETROSPECTIVE_COHORT" in metrics.by_study_type

    def test_rwe_metrics_by_matching_method(self, svc: BiomarkerAnalysisService):
        """Metrics should break down by matching method."""
        metrics = svc.get_rwe_metrics()
        assert "PROPENSITY_SCORE" in metrics.by_matching_method

    def test_rwe_metrics_avg_sample_size(self, svc: BiomarkerAnalysisService):
        """Average sample size should be positive."""
        metrics = svc.get_rwe_metrics()
        assert metrics.avg_sample_size > 0

    def test_rwe_metrics_avg_effect_size(self, svc: BiomarkerAnalysisService):
        """Average effect size should be positive."""
        metrics = svc.get_rwe_metrics()
        assert metrics.avg_effect_size is not None
        assert metrics.avg_effect_size > 0

    def test_rwe_metrics_comparability_count(self, svc: BiomarkerAnalysisService):
        """Total comparability assessments should be 2."""
        metrics = svc.get_rwe_metrics()
        assert metrics.total_comparability_assessments == 2

    def test_rwe_metrics_avg_agreement(self, svc: BiomarkerAnalysisService):
        """Average agreement score should be between 0 and 1."""
        metrics = svc.get_rwe_metrics()
        assert metrics.avg_agreement_score is not None
        assert 0.0 <= metrics.avg_agreement_score <= 1.0

    def test_rwe_metrics_completed_studies(self, svc: BiomarkerAnalysisService):
        """Completed studies count should be >= 3."""
        metrics = svc.get_rwe_metrics()
        assert metrics.completed_studies >= 3


# ===========================================================================
# Section 14: Service stats
# ===========================================================================


class TestServiceStats:
    """Test service health stats."""

    def test_stats_keys(self, svc: BiomarkerAnalysisService):
        """Stats should include all expected keys."""
        stats = svc.get_stats()
        assert "biomarkers" in stats
        assert "associations" in stats
        assert "patient_values" in stats
        assert "panels" in stats
        assert "rwe_studies" in stats
        assert "comparabilities" in stats

    def test_stats_values(self, svc: BiomarkerAnalysisService):
        """Stats values should match seed data counts."""
        stats = svc.get_stats()
        assert stats["biomarkers"] == 12
        assert stats["associations"] == 15
        assert stats["patient_values"] == 30
        assert stats["panels"] == 3
        assert stats["rwe_studies"] == 4
        assert stats["comparabilities"] == 2


# ===========================================================================
# Section 15: Singleton management
# ===========================================================================


class TestSingleton:
    """Test singleton pattern."""

    def test_get_service_returns_same_instance(self):
        """get_biomarker_analysis_service should return the same instance."""
        svc1 = get_biomarker_analysis_service()
        svc2 = get_biomarker_analysis_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        """reset should create a fresh instance."""
        svc1 = get_biomarker_analysis_service()
        svc2 = reset_biomarker_analysis_service()
        # After reset, getting service should return the new one
        svc3 = get_biomarker_analysis_service()
        assert svc3 is svc2


# ===========================================================================
# Section 16: API integration tests
# ===========================================================================


@pytest.mark.anyio
class TestBiomarkerAPI:
    """Test all API endpoints via HTTP."""

    async def _client(self):
        """Create async test client."""
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    async def test_api_list_biomarkers(self):
        """GET /biomarkers should return 200 with items."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/biomarkers")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    async def test_api_list_biomarkers_filter_type(self):
        """GET /biomarkers?biomarker_type=GENOMIC should filter."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/biomarkers", params={"biomarker_type": "GENOMIC"})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1

    async def test_api_create_biomarker(self):
        """POST /biomarkers should create and return 201."""
        payload = {
            "name": "API Test Biomarker",
            "biomarker_type": "GENOMIC",
            "role": "PREDICTIVE",
            "description": "Created via API",
        }
        async with await self._client() as c:
            r = await c.post(f"{API_PREFIX}/biomarkers", json=payload)
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "API Test Biomarker"
        assert data["status"] == "DISCOVERED"

    async def test_api_get_biomarker(self):
        """GET /biomarkers/{id} should return 200."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/biomarkers/BM-0001")
        assert r.status_code == 200
        assert r.json()["name"] == "VEGF-A"

    async def test_api_get_biomarker_404(self):
        """GET /biomarkers/{id} with invalid ID should return 404."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/biomarkers/BM-9999")
        assert r.status_code == 404

    async def test_api_delete_biomarker(self):
        """DELETE /biomarkers/{id} should return 204."""
        async with await self._client() as c:
            r = await c.delete(f"{API_PREFIX}/biomarkers/BM-0001")
        assert r.status_code == 204

    async def test_api_delete_biomarker_404(self):
        """DELETE /biomarkers/{id} with invalid ID should return 404."""
        async with await self._client() as c:
            r = await c.delete(f"{API_PREFIX}/biomarkers/BM-9999")
        assert r.status_code == 404

    async def test_api_update_status(self):
        """PUT /biomarkers/{id}/status should update status."""
        async with await self._client() as c:
            r = await c.put(
                f"{API_PREFIX}/biomarkers/BM-0011/status",
                params={"new_status": "VALIDATED"},
            )
        assert r.status_code == 200
        assert r.json()["status"] == "VALIDATED"

    async def test_api_update_status_invalid(self):
        """PUT /biomarkers/{id}/status with invalid transition should return 400."""
        async with await self._client() as c:
            r = await c.put(
                f"{API_PREFIX}/biomarkers/BM-0011/status",
                params={"new_status": "APPROVED"},
            )
        assert r.status_code == 400

    async def test_api_list_associations(self):
        """GET /associations should return 200."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/associations")
        assert r.status_code == 200
        assert len(r.json()) == 15

    async def test_api_create_association(self):
        """POST /associations should create and return 201."""
        payload = {
            "biomarker_id": "BM-0001",
            "condition": "API Test Condition",
            "effect_size": 0.5,
            "p_value": 0.02,
        }
        async with await self._client() as c:
            r = await c.post(f"{API_PREFIX}/associations", json=payload)
        assert r.status_code == 201

    async def test_api_create_association_invalid_biomarker(self):
        """POST /associations with invalid biomarker should return 404."""
        payload = {
            "biomarker_id": "BM-9999",
            "condition": "Test",
            "effect_size": 0.5,
            "p_value": 0.05,
        }
        async with await self._client() as c:
            r = await c.post(f"{API_PREFIX}/associations", json=payload)
        assert r.status_code == 404

    async def test_api_associations_by_biomarker(self):
        """GET /associations/by-biomarker/{id} should return results."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/associations/by-biomarker/BM-0001")
        assert r.status_code == 200
        assert len(r.json()) >= 2

    async def test_api_associations_by_condition(self):
        """GET /associations/by-condition should return results."""
        async with await self._client() as c:
            r = await c.get(
                f"{API_PREFIX}/associations/by-condition",
                params={"condition": "Diabetic"},
            )
        assert r.status_code == 200
        assert len(r.json()) >= 3

    async def test_api_list_patient_values(self):
        """GET /patient-values should return 200."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/patient-values")
        assert r.status_code == 200
        assert len(r.json()) == 30

    async def test_api_record_patient_value(self):
        """POST /patient-values should record and return 201."""
        payload = {
            "patient_id": "PAT-NEW",
            "biomarker_id": "BM-0001",
            "value": 75.0,
            "source": "API Test",
        }
        async with await self._client() as c:
            r = await c.post(f"{API_PREFIX}/patient-values", json=payload)
        assert r.status_code == 201
        assert r.json()["is_abnormal"] is True

    async def test_api_record_patient_value_invalid(self):
        """POST /patient-values with invalid biomarker should return 404."""
        payload = {
            "patient_id": "PAT-NEW",
            "biomarker_id": "BM-9999",
            "value": 50.0,
        }
        async with await self._client() as c:
            r = await c.post(f"{API_PREFIX}/patient-values", json=payload)
        assert r.status_code == 404

    async def test_api_patient_biomarkers(self):
        """GET /patient-values/{patient_id} should return results."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/patient-values/PAT-0001")
        assert r.status_code == 200
        assert len(r.json()) == 3

    async def test_api_biomarker_values(self):
        """GET /patient-values/biomarker/{id} should return results."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/patient-values/biomarker/BM-0001")
        assert r.status_code == 200
        assert len(r.json()) >= 1

    async def test_api_list_panels(self):
        """GET /panels should return 200."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/panels")
        assert r.status_code == 200
        assert len(r.json()) == 3

    async def test_api_create_panel(self):
        """POST /panels should create and return 201."""
        payload = {
            "name": "API Test Panel",
            "biomarkers": ["BM-0001", "BM-0002"],
            "target_condition": "Test",
        }
        async with await self._client() as c:
            r = await c.post(f"{API_PREFIX}/panels", json=payload)
        assert r.status_code == 201

    async def test_api_get_panel(self):
        """GET /panels/{id} should return 200."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/panels/PNL-0001")
        assert r.status_code == 200
        assert r.json()["name"] == "DME Progression Panel"

    async def test_api_get_panel_404(self):
        """GET /panels/{id} with invalid ID should return 404."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/panels/PNL-9999")
        assert r.status_code == 404

    async def test_api_score_panel(self):
        """GET /panels/{id}/score/{patient_id} should return results."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/panels/PNL-0001/score/PAT-0001")
        assert r.status_code == 200
        data = r.json()
        assert "completeness" in data

    async def test_api_score_panel_404(self):
        """GET /panels/{id}/score/{patient_id} with invalid panel should return 404."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/panels/PNL-9999/score/PAT-0001")
        assert r.status_code == 404

    async def test_api_list_rwe_studies(self):
        """GET /rwe-studies should return 200."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/rwe-studies")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 4

    async def test_api_create_rwe_study(self):
        """POST /rwe-studies should create and return 201."""
        payload = {
            "title": "API Test Study",
            "study_type": "CASE_CONTROL",
            "sample_size": 500,
        }
        async with await self._client() as c:
            r = await c.post(f"{API_PREFIX}/rwe-studies", json=payload)
        assert r.status_code == 201
        assert r.json()["status"] == "ACTIVE"

    async def test_api_get_rwe_study(self):
        """GET /rwe-studies/{id} should return 200."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/rwe-studies/RWE-0001")
        assert r.status_code == 200

    async def test_api_get_rwe_study_404(self):
        """GET /rwe-studies/{id} with invalid ID should return 404."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/rwe-studies/RWE-9999")
        assert r.status_code == 404

    async def test_api_delete_rwe_study(self):
        """DELETE /rwe-studies/{id} should return 204."""
        async with await self._client() as c:
            r = await c.delete(f"{API_PREFIX}/rwe-studies/RWE-0001")
        assert r.status_code == 204

    async def test_api_delete_rwe_study_404(self):
        """DELETE /rwe-studies/{id} with invalid ID should return 404."""
        async with await self._client() as c:
            r = await c.delete(f"{API_PREFIX}/rwe-studies/RWE-9999")
        assert r.status_code == 404

    async def test_api_propensity_score(self):
        """POST /rwe-studies/{id}/propensity-score should return results."""
        async with await self._client() as c:
            r = await c.post(f"{API_PREFIX}/rwe-studies/RWE-0001/propensity-score")
        assert r.status_code == 200
        data = r.json()
        assert data["matched_pairs"] > 0

    async def test_api_propensity_score_404(self):
        """POST /rwe-studies/{id}/propensity-score with invalid ID should return 404."""
        async with await self._client() as c:
            r = await c.post(f"{API_PREFIX}/rwe-studies/RWE-9999/propensity-score")
        assert r.status_code == 404

    async def test_api_list_comparabilities(self):
        """GET /comparabilities should return 200."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/comparabilities")
        assert r.status_code == 200
        assert len(r.json()) == 2

    async def test_api_create_comparability(self):
        """POST /comparabilities should create and return 201."""
        payload = {
            "rwe_study_id": "RWE-0003",
            "rct_reference": "Test RCT",
            "rwe_effect_size": 0.65,
            "rct_effect_size": 0.70,
        }
        async with await self._client() as c:
            r = await c.post(f"{API_PREFIX}/comparabilities", json=payload)
        assert r.status_code == 201

    async def test_api_create_comparability_invalid_study(self):
        """POST /comparabilities with invalid study should return 404."""
        payload = {
            "rwe_study_id": "RWE-9999",
            "rct_reference": "Test",
        }
        async with await self._client() as c:
            r = await c.post(f"{API_PREFIX}/comparabilities", json=payload)
        assert r.status_code == 404

    async def test_api_get_comparability(self):
        """GET /comparabilities/{id} should return 200."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/comparabilities/CMP-0001")
        assert r.status_code == 200

    async def test_api_get_comparability_404(self):
        """GET /comparabilities/{id} with invalid ID should return 404."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/comparabilities/CMP-9999")
        assert r.status_code == 404

    async def test_api_comparabilities_by_study(self):
        """GET /comparabilities/by-study/{id} should return results."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/comparabilities/by-study/RWE-0001")
        assert r.status_code == 200
        assert len(r.json()) >= 1

    async def test_api_stratification(self):
        """GET /stratification/{biomarker_id} should return results."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/stratification/BM-0001")
        assert r.status_code == 200
        data = r.json()
        assert "above_count" in data
        assert "below_count" in data

    async def test_api_stratification_custom_threshold(self):
        """GET /stratification/{id}?threshold=30 should use custom threshold."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/stratification/BM-0001", params={"threshold": 30.0})
        assert r.status_code == 200
        assert r.json()["threshold"] == 30.0

    async def test_api_stratification_404(self):
        """GET /stratification/{id} with invalid ID should return 404."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/stratification/BM-9999")
        assert r.status_code == 404

    async def test_api_enrichment(self):
        """GET /enrichment/{biomarker_id} should return results."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/enrichment/BM-0001")
        assert r.status_code == 200
        data = r.json()
        assert data["enrichment_score"] > 0

    async def test_api_enrichment_404(self):
        """GET /enrichment/{id} with invalid ID should return 404."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/enrichment/BM-9999")
        assert r.status_code == 404

    async def test_api_biomarker_metrics(self):
        """GET /metrics/biomarkers should return 200."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/metrics/biomarkers")
        assert r.status_code == 200
        data = r.json()
        assert data["total_biomarkers"] == 12

    async def test_api_rwe_metrics(self):
        """GET /metrics/rwe should return 200."""
        async with await self._client() as c:
            r = await c.get(f"{API_PREFIX}/metrics/rwe")
        assert r.status_code == 200
        data = r.json()
        assert data["total_studies"] == 4
