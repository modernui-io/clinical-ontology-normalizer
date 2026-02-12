"""Tests for Clinical Pharmacology Operations (CLIN-PHARM).

Covers:
- Seed data verification (studies, samples, escalations, exposure analyses, DDI assessments)
- PK Study CRUD (create, read, update, delete, list, filter by trial/type/status)
- PK Sample CRUD (create, read, update, delete, list, filter by study/matrix/status)
- Sample creation validates study_id exists
- Dose Escalation CRUD (create, read, update, delete, list, filter by study/decision)
- Escalation creation validates study_id exists
- Exposure-Response CRUD (create, read, update, delete, list, filter by study/status)
- DDI Assessment CRUD (create, read, update, delete, list, filter by trial/risk)
- Metrics computation (studies_by_type, samples_by_status, avg_sample_analysis_rate, etc.)
- Error handling (404s, 400s, invalid operations)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.clinical_pharmacology import (
    AnalysisStatus,
    DDIRisk,
    EscalationDecision,
    SampleMatrix,
    SampleStatus,
    StudyType,
)
from app.services.clinical_pharmacology_service import (
    ClinicalPharmacologyService,
    get_clinical_pharmacology_service,
    reset_clinical_pharmacology_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/clinical-pharmacology"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_clinical_pharmacology_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ClinicalPharmacologyService:
    """Shorthand for the fresh service."""
    return fresh_service


@pytest.fixture
async def client():
    """Async HTTP client for API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_study_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "study_type": "pk_single_dose",
        "title": "Test PK Study",
        "description": "A test PK study description",
        "target_analyte": "test_analyte",
        "matrix": "plasma",
        "dose_levels": ["10mg", "20mg"],
        "total_subjects": 12,
        "sampling_timepoints": ["0h", "1h", "4h"],
        "bioanalytical_method": "LC-MS/MS",
        "lloq": 0.01,
        "uloq": 100.0,
        "principal_investigator": "Dr. Test",
    }
    defaults.update(overrides)
    return defaults


def _make_sample_create(**overrides) -> dict:
    defaults = {
        "study_id": "PKS-001",
        "subject_id": "SUBJ-TEST-001",
        "timepoint": "0h",
        "nominal_time_hours": 0.0,
        "matrix": "plasma",
    }
    defaults.update(overrides)
    return defaults


def _make_escalation_create(**overrides) -> dict:
    defaults = {
        "study_id": "PKS-004",
        "cohort_number": 5,
        "dose_level": "500mg SC",
        "subjects_enrolled": 3,
    }
    defaults.update(overrides)
    return defaults


def _make_exposure_create(**overrides) -> dict:
    defaults = {
        "study_id": "PKS-001",
        "analysis_type": "exposure-efficacy",
        "endpoint": "Test endpoint",
        "model_type": "linear_regression",
        "pk_parameter": "AUC",
        "analyst": "Dr. Test Analyst",
    }
    defaults.update(overrides)
    return defaults


def _make_ddi_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "perpetrator_drug": "Drug A",
        "victim_drug": "Drug B",
        "interaction_mechanism": "CYP3A4 inhibition",
        "risk_classification": "low",
        "recommendation": "Monitor closely",
        "assessed_by": "Dr. Test Assessor",
        "references": ["Ref 1", "Ref 2"],
    }
    defaults.update(overrides)
    return defaults


# ===========================================================================
# SECTION 1 – Seed Data Verification (Service-level)
# ===========================================================================


class TestSeedData:
    """Verify seed data is populated correctly."""

    def test_seed_studies_count(self, svc: ClinicalPharmacologyService):
        """Should seed 12 PK studies."""
        assert len(svc.list_studies()) == 12

    def test_seed_samples_count(self, svc: ClinicalPharmacologyService):
        """Should seed 15 PK samples."""
        assert len(svc.list_samples()) == 15

    def test_seed_escalations_count(self, svc: ClinicalPharmacologyService):
        """Should seed 12 dose escalations."""
        assert len(svc.list_escalations()) == 12

    def test_seed_exposure_analyses_count(self, svc: ClinicalPharmacologyService):
        """Should seed 10 exposure-response analyses."""
        assert len(svc.list_exposure_analyses()) == 10

    def test_seed_ddi_assessments_count(self, svc: ClinicalPharmacologyService):
        """Should seed 12 DDI assessments."""
        assert len(svc.list_ddi_assessments()) == 12

    def test_seed_study_by_id(self, svc: ClinicalPharmacologyService):
        """Should retrieve a specific seeded study."""
        study = svc.get_study("PKS-001")
        assert study is not None
        assert study.trial_id == EYLEA_TRIAL
        assert study.study_type == StudyType.PK_SINGLE_DOSE
        assert study.target_analyte == "aflibercept"

    def test_seed_sample_by_id(self, svc: ClinicalPharmacologyService):
        """Should retrieve a specific seeded sample."""
        sample = svc.get_sample("PKSMP-001")
        assert sample is not None
        assert sample.study_id == "PKS-001"
        assert sample.status == SampleStatus.REPORTED

    def test_seed_escalation_by_id(self, svc: ClinicalPharmacologyService):
        """Should retrieve a specific seeded escalation."""
        esc = svc.get_escalation("ESC-001")
        assert esc is not None
        assert esc.decision == EscalationDecision.ESCALATE
        assert esc.dlts_observed == 0

    def test_seed_exposure_analysis_by_id(self, svc: ClinicalPharmacologyService):
        """Should retrieve a specific seeded exposure-response analysis."""
        er = svc.get_exposure_analysis("ER-001")
        assert er is not None
        assert er.status == AnalysisStatus.FINALIZED
        assert er.ec50 == 45.0

    def test_seed_ddi_by_id(self, svc: ClinicalPharmacologyService):
        """Should retrieve a specific seeded DDI assessment."""
        ddi = svc.get_ddi_assessment("DDI-001")
        assert ddi is not None
        assert ddi.risk_classification == DDIRisk.NONE
        assert ddi.perpetrator_drug == "Cemiplimab"

    def test_seed_studies_span_all_trials(self, svc: ClinicalPharmacologyService):
        """Studies should span EYLEA, DUPIXENT, and LIBTAYO."""
        trial_ids = {s.trial_id for s in svc.list_studies()}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_studies_have_multiple_types(self, svc: ClinicalPharmacologyService):
        """Studies should cover multiple study types."""
        types = {s.study_type for s in svc.list_studies()}
        assert len(types) >= 5

    def test_seed_samples_have_multiple_statuses(self, svc: ClinicalPharmacologyService):
        """Samples should cover multiple statuses."""
        statuses = {s.status for s in svc.list_samples()}
        assert len(statuses) >= 5

    def test_seed_ddi_have_multiple_risk_levels(self, svc: ClinicalPharmacologyService):
        """DDI assessments should cover multiple risk levels."""
        risks = {d.risk_classification for d in svc.list_ddi_assessments()}
        assert len(risks) >= 4

    def test_seed_escalation_with_dlts(self, svc: ClinicalPharmacologyService):
        """At least one escalation should have DLTs."""
        esc = svc.get_escalation("ESC-003")
        assert esc is not None
        assert esc.dlts_observed > 0
        assert len(esc.dlt_descriptions) > 0

    def test_seed_failed_qc_sample(self, svc: ClinicalPharmacologyService):
        """At least one sample should have failed QC."""
        sample = svc.get_sample("PKSMP-010")
        assert sample is not None
        assert sample.status == SampleStatus.FAILED_QC
        assert sample.qc_passed is False


# ===========================================================================
# SECTION 2 – PK Studies CRUD (Service-level)
# ===========================================================================


class TestStudyService:
    """Test PK study CRUD at the service level."""

    def test_create_study(self, svc: ClinicalPharmacologyService):
        study = svc.create_study(
            _make_study_payload()
        )
        assert study.id.startswith("PKS-")
        assert study.status == AnalysisStatus.PLANNED
        assert study.title == "Test PK Study"

    def test_get_study_not_found(self, svc: ClinicalPharmacologyService):
        assert svc.get_study("PKS-NONEXISTENT") is None

    def test_update_study(self, svc: ClinicalPharmacologyService):
        updated = svc.update_study("PKS-001", _make_study_update_payload(title="Updated Title"))
        assert updated is not None
        assert updated.title == "Updated Title"

    def test_update_study_not_found(self, svc: ClinicalPharmacologyService):
        assert svc.update_study("PKS-MISSING", _make_study_update_payload()) is None

    def test_delete_study(self, svc: ClinicalPharmacologyService):
        assert svc.delete_study("PKS-001") is True
        assert svc.get_study("PKS-001") is None

    def test_delete_study_not_found(self, svc: ClinicalPharmacologyService):
        assert svc.delete_study("PKS-NONEXISTENT") is False

    def test_filter_studies_by_trial(self, svc: ClinicalPharmacologyService):
        eylea = svc.list_studies(trial_id=EYLEA_TRIAL)
        for s in eylea:
            assert s.trial_id == EYLEA_TRIAL
        assert len(eylea) >= 3

    def test_filter_studies_by_type(self, svc: ClinicalPharmacologyService):
        pk_sd = svc.list_studies(study_type=StudyType.PK_SINGLE_DOSE)
        for s in pk_sd:
            assert s.study_type == StudyType.PK_SINGLE_DOSE
        assert len(pk_sd) >= 2

    def test_filter_studies_by_status(self, svc: ClinicalPharmacologyService):
        completed = svc.list_studies(status=AnalysisStatus.COMPLETED)
        for s in completed:
            assert s.status == AnalysisStatus.COMPLETED
        assert len(completed) >= 2

    def test_filter_studies_combined(self, svc: ClinicalPharmacologyService):
        result = svc.list_studies(trial_id=LIBTAYO_TRIAL, status=AnalysisStatus.IN_PROGRESS)
        for s in result:
            assert s.trial_id == LIBTAYO_TRIAL
            assert s.status == AnalysisStatus.IN_PROGRESS

    def test_list_studies_empty_filter(self, svc: ClinicalPharmacologyService):
        result = svc.list_studies(trial_id="nonexistent-trial")
        assert result == []

    def test_update_study_status(self, svc: ClinicalPharmacologyService):
        updated = svc.update_study("PKS-008", _make_study_update_payload(status="in_progress"))
        assert updated is not None
        assert updated.status == AnalysisStatus.IN_PROGRESS


# ===========================================================================
# SECTION 3 – PK Samples CRUD (Service-level)
# ===========================================================================


class TestSampleService:
    """Test PK sample CRUD at the service level."""

    def test_create_sample(self, svc: ClinicalPharmacologyService):
        from app.schemas.clinical_pharmacology import PKSampleCreate
        payload = PKSampleCreate(**_make_sample_create())
        sample = svc.create_sample(payload)
        assert sample.id.startswith("PKSMP-")
        assert sample.status == SampleStatus.SCHEDULED

    def test_create_sample_invalid_study(self, svc: ClinicalPharmacologyService):
        from app.schemas.clinical_pharmacology import PKSampleCreate
        payload = PKSampleCreate(**_make_sample_create(study_id="PKS-NONEXISTENT"))
        with pytest.raises(ValueError, match="Study 'PKS-NONEXISTENT' not found"):
            svc.create_sample(payload)

    def test_get_sample_not_found(self, svc: ClinicalPharmacologyService):
        assert svc.get_sample("PKSMP-NONEXISTENT") is None

    def test_update_sample(self, svc: ClinicalPharmacologyService):
        from app.schemas.clinical_pharmacology import PKSampleUpdate
        updated = svc.update_sample("PKSMP-005", PKSampleUpdate(status=SampleStatus.RECEIVED_AT_LAB))
        assert updated is not None
        assert updated.status == SampleStatus.RECEIVED_AT_LAB

    def test_update_sample_not_found(self, svc: ClinicalPharmacologyService):
        from app.schemas.clinical_pharmacology import PKSampleUpdate
        assert svc.update_sample("PKSMP-MISSING", PKSampleUpdate(notes="x")) is None

    def test_delete_sample(self, svc: ClinicalPharmacologyService):
        assert svc.delete_sample("PKSMP-001") is True
        assert svc.get_sample("PKSMP-001") is None

    def test_delete_sample_not_found(self, svc: ClinicalPharmacologyService):
        assert svc.delete_sample("PKSMP-NONEXISTENT") is False

    def test_filter_samples_by_study(self, svc: ClinicalPharmacologyService):
        result = svc.list_samples(study_id="PKS-001")
        for s in result:
            assert s.study_id == "PKS-001"
        assert len(result) >= 3

    def test_filter_samples_by_matrix(self, svc: ClinicalPharmacologyService):
        result = svc.list_samples(matrix=SampleMatrix.SERUM)
        for s in result:
            assert s.matrix == SampleMatrix.SERUM
        assert len(result) >= 4

    def test_filter_samples_by_status(self, svc: ClinicalPharmacologyService):
        result = svc.list_samples(sample_status=SampleStatus.REPORTED)
        for s in result:
            assert s.status == SampleStatus.REPORTED
        assert len(result) >= 5

    def test_filter_samples_combined(self, svc: ClinicalPharmacologyService):
        result = svc.list_samples(study_id="PKS-001", sample_status=SampleStatus.REPORTED)
        for s in result:
            assert s.study_id == "PKS-001"
            assert s.status == SampleStatus.REPORTED

    def test_list_samples_empty_filter(self, svc: ClinicalPharmacologyService):
        result = svc.list_samples(study_id="PKS-NONEXISTENT")
        assert result == []

    def test_update_sample_concentration(self, svc: ClinicalPharmacologyService):
        from app.schemas.clinical_pharmacology import PKSampleUpdate
        updated = svc.update_sample("PKSMP-005", PKSampleUpdate(concentration=42.5, qc_passed=True))
        assert updated is not None
        assert updated.concentration == 42.5
        assert updated.qc_passed is True


# ===========================================================================
# SECTION 4 – Dose Escalations CRUD (Service-level)
# ===========================================================================


class TestEscalationService:
    """Test dose escalation CRUD at the service level."""

    def test_create_escalation(self, svc: ClinicalPharmacologyService):
        from app.schemas.clinical_pharmacology import DoseEscalationCreate
        payload = DoseEscalationCreate(**_make_escalation_create())
        esc = svc.create_escalation(payload)
        assert esc.id.startswith("ESC-")
        assert esc.decision is None

    def test_create_escalation_invalid_study(self, svc: ClinicalPharmacologyService):
        from app.schemas.clinical_pharmacology import DoseEscalationCreate
        payload = DoseEscalationCreate(**_make_escalation_create(study_id="PKS-NONEXISTENT"))
        with pytest.raises(ValueError, match="Study 'PKS-NONEXISTENT' not found"):
            svc.create_escalation(payload)

    def test_get_escalation_not_found(self, svc: ClinicalPharmacologyService):
        assert svc.get_escalation("ESC-NONEXISTENT") is None

    def test_update_escalation(self, svc: ClinicalPharmacologyService):
        from app.schemas.clinical_pharmacology import DoseEscalationUpdate
        updated = svc.update_escalation(
            "ESC-004",
            DoseEscalationUpdate(
                decision=EscalationDecision.ESCALATE,
                decision_rationale="Expansion cohort clear",
                decided_by="Dr. Test",
            ),
        )
        assert updated is not None
        assert updated.decision == EscalationDecision.ESCALATE
        assert updated.decision_date is not None

    def test_update_escalation_not_found(self, svc: ClinicalPharmacologyService):
        from app.schemas.clinical_pharmacology import DoseEscalationUpdate
        assert svc.update_escalation("ESC-MISSING", DoseEscalationUpdate(decided_by="x")) is None

    def test_delete_escalation(self, svc: ClinicalPharmacologyService):
        assert svc.delete_escalation("ESC-001") is True
        assert svc.get_escalation("ESC-001") is None

    def test_delete_escalation_not_found(self, svc: ClinicalPharmacologyService):
        assert svc.delete_escalation("ESC-NONEXISTENT") is False

    def test_filter_escalations_by_study(self, svc: ClinicalPharmacologyService):
        result = svc.list_escalations(study_id="PKS-004")
        for e in result:
            assert e.study_id == "PKS-004"
        assert len(result) >= 3

    def test_filter_escalations_by_decision(self, svc: ClinicalPharmacologyService):
        result = svc.list_escalations(decision=EscalationDecision.ESCALATE)
        for e in result:
            assert e.decision == EscalationDecision.ESCALATE
        assert len(result) >= 4

    def test_filter_escalations_combined(self, svc: ClinicalPharmacologyService):
        result = svc.list_escalations(study_id="PKS-005", decision=EscalationDecision.ESCALATE)
        for e in result:
            assert e.study_id == "PKS-005"
            assert e.decision == EscalationDecision.ESCALATE

    def test_list_escalations_empty_filter(self, svc: ClinicalPharmacologyService):
        result = svc.list_escalations(study_id="PKS-NONEXISTENT")
        assert result == []

    def test_update_escalation_dlt_info(self, svc: ClinicalPharmacologyService):
        from app.schemas.clinical_pharmacology import DoseEscalationUpdate
        updated = svc.update_escalation(
            "ESC-004",
            DoseEscalationUpdate(
                subjects_evaluable=6,
                dlts_observed=1,
                dlt_descriptions=["Grade 3 rash"],
            ),
        )
        assert updated is not None
        assert updated.dlts_observed == 1
        assert "Grade 3 rash" in updated.dlt_descriptions


# ===========================================================================
# SECTION 5 – Exposure-Response CRUD (Service-level)
# ===========================================================================


class TestExposureResponseService:
    """Test exposure-response analysis CRUD at the service level."""

    def test_create_exposure_analysis(self, svc: ClinicalPharmacologyService):
        from app.schemas.clinical_pharmacology import ExposureResponseCreate
        payload = ExposureResponseCreate(**_make_exposure_create())
        er = svc.create_exposure_analysis(payload)
        assert er.id.startswith("ER-")
        assert er.status == AnalysisStatus.PLANNED

    def test_get_exposure_analysis_not_found(self, svc: ClinicalPharmacologyService):
        assert svc.get_exposure_analysis("ER-NONEXISTENT") is None

    def test_update_exposure_analysis(self, svc: ClinicalPharmacologyService):
        from app.schemas.clinical_pharmacology import ExposureResponseUpdate
        updated = svc.update_exposure_analysis(
            "ER-008",
            ExposureResponseUpdate(
                status=AnalysisStatus.IN_PROGRESS,
                correlation_coefficient=0.55,
            ),
        )
        assert updated is not None
        assert updated.status == AnalysisStatus.IN_PROGRESS
        assert updated.correlation_coefficient == 0.55

    def test_update_exposure_analysis_not_found(self, svc: ClinicalPharmacologyService):
        from app.schemas.clinical_pharmacology import ExposureResponseUpdate
        assert svc.update_exposure_analysis("ER-MISSING", ExposureResponseUpdate(p_value=0.05)) is None

    def test_delete_exposure_analysis(self, svc: ClinicalPharmacologyService):
        assert svc.delete_exposure_analysis("ER-001") is True
        assert svc.get_exposure_analysis("ER-001") is None

    def test_delete_exposure_analysis_not_found(self, svc: ClinicalPharmacologyService):
        assert svc.delete_exposure_analysis("ER-NONEXISTENT") is False

    def test_filter_exposure_by_study(self, svc: ClinicalPharmacologyService):
        result = svc.list_exposure_analyses(study_id="PKS-003")
        for e in result:
            assert e.study_id == "PKS-003"
        assert len(result) >= 2

    def test_filter_exposure_by_status(self, svc: ClinicalPharmacologyService):
        result = svc.list_exposure_analyses(status=AnalysisStatus.FINALIZED)
        for e in result:
            assert e.status == AnalysisStatus.FINALIZED
        assert len(result) >= 3

    def test_filter_exposure_combined(self, svc: ClinicalPharmacologyService):
        result = svc.list_exposure_analyses(study_id="PKS-005", status=AnalysisStatus.FINALIZED)
        for e in result:
            assert e.study_id == "PKS-005"
            assert e.status == AnalysisStatus.FINALIZED

    def test_list_exposure_empty_filter(self, svc: ClinicalPharmacologyService):
        result = svc.list_exposure_analyses(study_id="PKS-NONEXISTENT")
        assert result == []


# ===========================================================================
# SECTION 6 – DDI Assessments CRUD (Service-level)
# ===========================================================================


class TestDDIService:
    """Test DDI assessment CRUD at the service level."""

    def test_create_ddi_assessment(self, svc: ClinicalPharmacologyService):
        from app.schemas.clinical_pharmacology import DDIAssessmentCreate
        payload = DDIAssessmentCreate(**_make_ddi_create())
        ddi = svc.create_ddi_assessment(payload)
        assert ddi.id.startswith("DDI-")
        assert ddi.assessment_date is not None

    def test_get_ddi_assessment_not_found(self, svc: ClinicalPharmacologyService):
        assert svc.get_ddi_assessment("DDI-NONEXISTENT") is None

    def test_update_ddi_assessment(self, svc: ClinicalPharmacologyService):
        from app.schemas.clinical_pharmacology import DDIAssessmentUpdate
        updated = svc.update_ddi_assessment(
            "DDI-002",
            DDIAssessmentUpdate(
                risk_classification=DDIRisk.MODERATE,
                clinical_result="Updated clinical result",
            ),
        )
        assert updated is not None
        assert updated.risk_classification == DDIRisk.MODERATE
        assert updated.clinical_result == "Updated clinical result"

    def test_update_ddi_assessment_not_found(self, svc: ClinicalPharmacologyService):
        from app.schemas.clinical_pharmacology import DDIAssessmentUpdate
        assert svc.update_ddi_assessment("DDI-MISSING", DDIAssessmentUpdate(recommendation="x")) is None

    def test_delete_ddi_assessment(self, svc: ClinicalPharmacologyService):
        assert svc.delete_ddi_assessment("DDI-001") is True
        assert svc.get_ddi_assessment("DDI-001") is None

    def test_delete_ddi_assessment_not_found(self, svc: ClinicalPharmacologyService):
        assert svc.delete_ddi_assessment("DDI-NONEXISTENT") is False

    def test_filter_ddi_by_trial(self, svc: ClinicalPharmacologyService):
        result = svc.list_ddi_assessments(trial_id=LIBTAYO_TRIAL)
        for d in result:
            assert d.trial_id == LIBTAYO_TRIAL
        assert len(result) >= 4

    def test_filter_ddi_by_risk(self, svc: ClinicalPharmacologyService):
        result = svc.list_ddi_assessments(risk_classification=DDIRisk.NONE)
        for d in result:
            assert d.risk_classification == DDIRisk.NONE
        assert len(result) >= 3

    def test_filter_ddi_combined(self, svc: ClinicalPharmacologyService):
        result = svc.list_ddi_assessments(trial_id=LIBTAYO_TRIAL, risk_classification=DDIRisk.CONTRAINDICATED)
        for d in result:
            assert d.trial_id == LIBTAYO_TRIAL
            assert d.risk_classification == DDIRisk.CONTRAINDICATED
        assert len(result) >= 1

    def test_list_ddi_empty_filter(self, svc: ClinicalPharmacologyService):
        result = svc.list_ddi_assessments(trial_id="nonexistent")
        assert result == []

    def test_update_ddi_auc_ratio(self, svc: ClinicalPharmacologyService):
        from app.schemas.clinical_pharmacology import DDIAssessmentUpdate
        updated = svc.update_ddi_assessment(
            "DDI-002",
            DDIAssessmentUpdate(auc_ratio=1.15, cmax_ratio=1.10),
        )
        assert updated is not None
        assert updated.auc_ratio == 1.15
        assert updated.cmax_ratio == 1.10


# ===========================================================================
# SECTION 7 – Metrics (Service-level)
# ===========================================================================


class TestMetricsService:
    """Test metrics computation at the service level."""

    def test_metrics_total_studies(self, svc: ClinicalPharmacologyService):
        metrics = svc.get_metrics()
        assert metrics.total_studies == 12

    def test_metrics_total_samples(self, svc: ClinicalPharmacologyService):
        metrics = svc.get_metrics()
        assert metrics.total_samples == 15

    def test_metrics_total_escalations(self, svc: ClinicalPharmacologyService):
        metrics = svc.get_metrics()
        assert metrics.total_escalations == 12

    def test_metrics_total_exposure_analyses(self, svc: ClinicalPharmacologyService):
        metrics = svc.get_metrics()
        assert metrics.total_exposure_analyses == 10

    def test_metrics_total_ddi_assessments(self, svc: ClinicalPharmacologyService):
        metrics = svc.get_metrics()
        assert metrics.total_ddi_assessments == 12

    def test_metrics_studies_by_type(self, svc: ClinicalPharmacologyService):
        metrics = svc.get_metrics()
        assert len(metrics.studies_by_type) >= 5
        assert sum(metrics.studies_by_type.values()) == 12

    def test_metrics_studies_by_status(self, svc: ClinicalPharmacologyService):
        metrics = svc.get_metrics()
        assert sum(metrics.studies_by_status.values()) == 12

    def test_metrics_samples_by_status(self, svc: ClinicalPharmacologyService):
        metrics = svc.get_metrics()
        assert sum(metrics.samples_by_status.values()) == 15

    def test_metrics_samples_analyzed(self, svc: ClinicalPharmacologyService):
        metrics = svc.get_metrics()
        assert metrics.samples_analyzed >= 8

    def test_metrics_samples_failed_qc(self, svc: ClinicalPharmacologyService):
        metrics = svc.get_metrics()
        assert metrics.samples_failed_qc >= 1

    def test_metrics_avg_sample_analysis_rate(self, svc: ClinicalPharmacologyService):
        metrics = svc.get_metrics()
        assert 0 < metrics.avg_sample_analysis_rate <= 100
        # Verify formula: (analyzed / total) * 100
        expected = round((metrics.samples_analyzed / metrics.total_samples) * 100, 1)
        assert metrics.avg_sample_analysis_rate == expected

    def test_metrics_ddi_by_risk(self, svc: ClinicalPharmacologyService):
        metrics = svc.get_metrics()
        assert len(metrics.ddi_by_risk) >= 4
        assert sum(metrics.ddi_by_risk.values()) == 12

    def test_metrics_escalations_by_decision(self, svc: ClinicalPharmacologyService):
        metrics = svc.get_metrics()
        # Only escalations with decisions are counted
        total_decided = sum(metrics.escalations_by_decision.values())
        assert total_decided >= 8

    def test_metrics_after_create(self, svc: ClinicalPharmacologyService):
        """Metrics should reflect new records."""
        from app.schemas.clinical_pharmacology import DDIAssessmentCreate
        svc.create_ddi_assessment(DDIAssessmentCreate(**_make_ddi_create()))
        metrics = svc.get_metrics()
        assert metrics.total_ddi_assessments == 13


# ===========================================================================
# SECTION 8 – API Endpoint Tests (Studies)
# ===========================================================================


class TestStudyAPI:
    """Test PK study API endpoints."""

    @pytest.mark.anyio
    async def test_list_studies(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_studies_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_studies_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies", params={"study_type": "pk_single_dose"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["study_type"] == "pk_single_dose"

    @pytest.mark.anyio
    async def test_list_studies_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies", params={"status": "completed"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_get_study(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/PKS-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PKS-001"
        assert data["target_analyte"] == "aflibercept"

    @pytest.mark.anyio
    async def test_get_study_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/PKS-MISSING")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_study(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/studies", json=_make_study_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("PKS-")
        assert data["status"] == "planned"

    @pytest.mark.anyio
    async def test_update_study(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/studies/PKS-001",
            json={"title": "Updated via API"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated via API"

    @pytest.mark.anyio
    async def test_update_study_not_found(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/studies/PKS-MISSING", json={"title": "x"})
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_study(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/studies/PKS-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_study_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/studies/PKS-MISSING")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_then_get(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/studies/PKS-001")
        resp = await client.get(f"{API_PREFIX}/studies/PKS-001")
        assert resp.status_code == 404


# ===========================================================================
# SECTION 9 – API Endpoint Tests (Samples)
# ===========================================================================


class TestSampleAPI:
    """Test PK sample API endpoints."""

    @pytest.mark.anyio
    async def test_list_samples(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/samples")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15

    @pytest.mark.anyio
    async def test_list_samples_filter_study(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/samples", params={"study_id": "PKS-001"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["study_id"] == "PKS-001"

    @pytest.mark.anyio
    async def test_list_samples_filter_matrix(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/samples", params={"matrix": "serum"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["matrix"] == "serum"

    @pytest.mark.anyio
    async def test_list_samples_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/samples", params={"sample_status": "reported"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["status"] == "reported"

    @pytest.mark.anyio
    async def test_get_sample(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/samples/PKSMP-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "PKSMP-001"

    @pytest.mark.anyio
    async def test_get_sample_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/samples/PKSMP-MISSING")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_sample(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/samples", json=_make_sample_create())
        assert resp.status_code == 201
        assert resp.json()["status"] == "scheduled"

    @pytest.mark.anyio
    async def test_create_sample_invalid_study(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/samples",
            json=_make_sample_create(study_id="PKS-NONEXISTENT"),
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_sample(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/samples/PKSMP-005",
            json={"status": "received_at_lab"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "received_at_lab"

    @pytest.mark.anyio
    async def test_update_sample_not_found(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/samples/PKSMP-MISSING", json={"notes": "x"})
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_sample(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/samples/PKSMP-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_sample_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/samples/PKSMP-MISSING")
        assert resp.status_code == 404


# ===========================================================================
# SECTION 10 – API Endpoint Tests (Escalations)
# ===========================================================================


class TestEscalationAPI:
    """Test dose escalation API endpoints."""

    @pytest.mark.anyio
    async def test_list_escalations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/escalations")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_list_escalations_filter_study(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/escalations", params={"study_id": "PKS-004"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["study_id"] == "PKS-004"

    @pytest.mark.anyio
    async def test_list_escalations_filter_decision(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/escalations", params={"decision": "escalate"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["decision"] == "escalate"

    @pytest.mark.anyio
    async def test_get_escalation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/escalations/ESC-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "ESC-001"

    @pytest.mark.anyio
    async def test_get_escalation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/escalations/ESC-MISSING")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_escalation(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/escalations", json=_make_escalation_create())
        assert resp.status_code == 201
        assert resp.json()["decision"] is None

    @pytest.mark.anyio
    async def test_create_escalation_invalid_study(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/escalations",
            json=_make_escalation_create(study_id="PKS-NONEXISTENT"),
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_escalation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/escalations/ESC-004",
            json={"decision": "escalate", "decided_by": "Dr. API Test"},
        )
        assert resp.status_code == 200
        assert resp.json()["decision"] == "escalate"

    @pytest.mark.anyio
    async def test_update_escalation_not_found(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/escalations/ESC-MISSING", json={"decided_by": "x"})
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_escalation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/escalations/ESC-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_escalation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/escalations/ESC-MISSING")
        assert resp.status_code == 404


# ===========================================================================
# SECTION 11 – API Endpoint Tests (Exposure-Response)
# ===========================================================================


class TestExposureResponseAPI:
    """Test exposure-response analysis API endpoints."""

    @pytest.mark.anyio
    async def test_list_exposure_analyses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/exposure-analyses")
        assert resp.status_code == 200
        assert resp.json()["total"] == 10

    @pytest.mark.anyio
    async def test_list_exposure_filter_study(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/exposure-analyses", params={"study_id": "PKS-003"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["study_id"] == "PKS-003"

    @pytest.mark.anyio
    async def test_list_exposure_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/exposure-analyses", params={"status": "finalized"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["status"] == "finalized"

    @pytest.mark.anyio
    async def test_get_exposure_analysis(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/exposure-analyses/ER-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "ER-001"

    @pytest.mark.anyio
    async def test_get_exposure_analysis_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/exposure-analyses/ER-MISSING")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_exposure_analysis(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/exposure-analyses", json=_make_exposure_create())
        assert resp.status_code == 201
        assert resp.json()["status"] == "planned"

    @pytest.mark.anyio
    async def test_update_exposure_analysis(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/exposure-analyses/ER-008",
            json={"status": "in_progress", "correlation_coefficient": 0.65},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["correlation_coefficient"] == 0.65

    @pytest.mark.anyio
    async def test_update_exposure_analysis_not_found(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/exposure-analyses/ER-MISSING", json={"p_value": 0.01})
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_exposure_analysis(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/exposure-analyses/ER-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_exposure_analysis_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/exposure-analyses/ER-MISSING")
        assert resp.status_code == 404


# ===========================================================================
# SECTION 12 – API Endpoint Tests (DDI Assessments)
# ===========================================================================


class TestDDIAPI:
    """Test DDI assessment API endpoints."""

    @pytest.mark.anyio
    async def test_list_ddi_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ddi-assessments")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_list_ddi_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ddi-assessments", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_ddi_filter_risk(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ddi-assessments", params={"risk_classification": "none"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["risk_classification"] == "none"

    @pytest.mark.anyio
    async def test_get_ddi_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ddi-assessments/DDI-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "DDI-001"

    @pytest.mark.anyio
    async def test_get_ddi_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ddi-assessments/DDI-MISSING")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_ddi_assessment(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/ddi-assessments", json=_make_ddi_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("DDI-")
        assert data["assessment_date"] is not None

    @pytest.mark.anyio
    async def test_update_ddi_assessment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/ddi-assessments/DDI-002",
            json={"risk_classification": "moderate", "auc_ratio": 1.25},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_classification"] == "moderate"
        assert data["auc_ratio"] == 1.25

    @pytest.mark.anyio
    async def test_update_ddi_not_found(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/ddi-assessments/DDI-MISSING", json={"recommendation": "x"})
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_ddi_assessment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/ddi-assessments/DDI-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_ddi_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/ddi-assessments/DDI-MISSING")
        assert resp.status_code == 404


# ===========================================================================
# SECTION 13 – API Metrics Endpoint
# ===========================================================================


class TestMetricsAPI:
    """Test metrics API endpoint."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_studies"] == 12
        assert data["total_samples"] == 15
        assert data["total_escalations"] == 12
        assert data["total_exposure_analyses"] == 10
        assert data["total_ddi_assessments"] == 12
        assert 0 < data["avg_sample_analysis_rate"] <= 100

    @pytest.mark.anyio
    async def test_metrics_studies_by_type_keys(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "pk_single_dose" in data["studies_by_type"]

    @pytest.mark.anyio
    async def test_metrics_ddi_by_risk_keys(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "none" in data["ddi_by_risk"]
        assert "contraindicated" in data["ddi_by_risk"]

    @pytest.mark.anyio
    async def test_metrics_after_delete(self, client: AsyncClient):
        """Metrics should reflect deleted records."""
        await client.delete(f"{API_PREFIX}/studies/PKS-001")
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.json()["total_studies"] == 11


# ===========================================================================
# SECTION 14 – Edge Cases & Additional Tests
# ===========================================================================


class TestEdgeCases:
    """Test edge cases and additional scenarios."""

    @pytest.mark.anyio
    async def test_create_study_minimal_fields(self, client: AsyncClient):
        """Create study with minimal required fields."""
        payload = {
            "trial_id": EYLEA_TRIAL,
            "study_type": "bioequivalence",
            "title": "Minimal Study",
            "description": "Minimal desc",
            "target_analyte": "drug_x",
            "matrix": "urine",
            "bioanalytical_method": "ELISA",
            "principal_investigator": "Dr. Min",
        }
        resp = await client.post(f"{API_PREFIX}/studies", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["dose_levels"] == []
        assert data["total_subjects"] == 0

    @pytest.mark.anyio
    async def test_create_ddi_minimal(self, client: AsyncClient):
        """Create DDI with minimal required fields."""
        payload = {
            "trial_id": DUPIXENT_TRIAL,
            "perpetrator_drug": "X",
            "victim_drug": "Y",
            "interaction_mechanism": "Unknown",
            "recommendation": "TBD",
            "assessed_by": "Dr. Minimal",
        }
        resp = await client.post(f"{API_PREFIX}/ddi-assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["risk_classification"] == "low"
        assert data["references"] == []

    @pytest.mark.anyio
    async def test_list_studies_no_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies", params={"trial_id": "no-such-trial"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["items"] == []

    @pytest.mark.anyio
    async def test_list_samples_no_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/samples", params={"study_id": "PKS-NONE"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_list_escalations_no_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/escalations", params={"study_id": "PKS-NONE"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_list_exposure_no_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/exposure-analyses", params={"study_id": "PKS-NONE"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_list_ddi_no_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ddi-assessments", params={"trial_id": "NONE"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_update_study_partial(self, client: AsyncClient):
        """Partial update should not wipe other fields."""
        resp = await client.put(
            f"{API_PREFIX}/studies/PKS-001",
            json={"total_subjects": 30},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_subjects"] == 30
        assert data["title"] == "Aflibercept Single-Dose PK in Healthy Volunteers"

    @pytest.mark.anyio
    async def test_update_sample_qc(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/samples/PKSMP-012",
            json={"qc_passed": False, "notes": "Hemolyzed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["qc_passed"] is False
        assert data["notes"] == "Hemolyzed"

    @pytest.mark.anyio
    async def test_create_then_get_study(self, client: AsyncClient):
        """Create, then retrieve by ID."""
        create_resp = await client.post(f"{API_PREFIX}/studies", json=_make_study_create())
        assert create_resp.status_code == 201
        study_id = create_resp.json()["id"]
        get_resp = await client.get(f"{API_PREFIX}/studies/{study_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["title"] == "Test PK Study"

    @pytest.mark.anyio
    async def test_create_then_get_sample(self, client: AsyncClient):
        create_resp = await client.post(f"{API_PREFIX}/samples", json=_make_sample_create())
        assert create_resp.status_code == 201
        sample_id = create_resp.json()["id"]
        get_resp = await client.get(f"{API_PREFIX}/samples/{sample_id}")
        assert get_resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_then_get_escalation(self, client: AsyncClient):
        create_resp = await client.post(f"{API_PREFIX}/escalations", json=_make_escalation_create())
        assert create_resp.status_code == 201
        esc_id = create_resp.json()["id"]
        get_resp = await client.get(f"{API_PREFIX}/escalations/{esc_id}")
        assert get_resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_then_get_exposure(self, client: AsyncClient):
        create_resp = await client.post(f"{API_PREFIX}/exposure-analyses", json=_make_exposure_create())
        assert create_resp.status_code == 201
        er_id = create_resp.json()["id"]
        get_resp = await client.get(f"{API_PREFIX}/exposure-analyses/{er_id}")
        assert get_resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_then_get_ddi(self, client: AsyncClient):
        create_resp = await client.post(f"{API_PREFIX}/ddi-assessments", json=_make_ddi_create())
        assert create_resp.status_code == 201
        ddi_id = create_resp.json()["id"]
        get_resp = await client.get(f"{API_PREFIX}/ddi-assessments/{ddi_id}")
        assert get_resp.status_code == 200

    @pytest.mark.anyio
    async def test_delete_then_list_studies(self, client: AsyncClient):
        """Deleting should reduce the count."""
        await client.delete(f"{API_PREFIX}/studies/PKS-001")
        resp = await client.get(f"{API_PREFIX}/studies")
        assert resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_then_list_samples(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/samples/PKSMP-001")
        resp = await client.get(f"{API_PREFIX}/samples")
        assert resp.json()["total"] == 14

    def test_singleton_returns_same_instance(self):
        """get_clinical_pharmacology_service should return the same instance."""
        svc1 = get_clinical_pharmacology_service()
        svc2 = get_clinical_pharmacology_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        """reset should create a new instance."""
        svc1 = get_clinical_pharmacology_service()
        svc2 = reset_clinical_pharmacology_service()
        assert svc1 is not svc2

    def test_study_sorted_by_id(self, svc: ClinicalPharmacologyService):
        studies = svc.list_studies()
        ids = [s.id for s in studies]
        assert ids == sorted(ids)

    def test_sample_sorted_by_id(self, svc: ClinicalPharmacologyService):
        samples = svc.list_samples()
        ids = [s.id for s in samples]
        assert ids == sorted(ids)

    def test_escalation_sorted_by_id(self, svc: ClinicalPharmacologyService):
        escalations = svc.list_escalations()
        ids = [e.id for e in escalations]
        assert ids == sorted(ids)

    def test_exposure_sorted_by_id(self, svc: ClinicalPharmacologyService):
        analyses = svc.list_exposure_analyses()
        ids = [e.id for e in analyses]
        assert ids == sorted(ids)

    def test_ddi_sorted_by_id(self, svc: ClinicalPharmacologyService):
        ddis = svc.list_ddi_assessments()
        ids = [d.id for d in ddis]
        assert ids == sorted(ids)

    @pytest.mark.anyio
    async def test_study_response_fields(self, client: AsyncClient):
        """Verify all expected fields are in the response."""
        resp = await client.get(f"{API_PREFIX}/studies/PKS-001")
        data = resp.json()
        expected_keys = {
            "id", "trial_id", "study_type", "title", "description",
            "target_analyte", "matrix", "dose_levels", "total_subjects",
            "sampling_timepoints", "bioanalytical_method", "lloq", "uloq",
            "status", "principal_investigator", "start_date", "completion_date",
            "created_at",
        }
        assert expected_keys.issubset(set(data.keys()))

    @pytest.mark.anyio
    async def test_sample_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/samples/PKSMP-001")
        data = resp.json()
        expected_keys = {
            "id", "study_id", "subject_id", "timepoint",
            "nominal_time_hours", "matrix", "status",
        }
        assert expected_keys.issubset(set(data.keys()))

    @pytest.mark.anyio
    async def test_ddi_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ddi-assessments/DDI-001")
        data = resp.json()
        expected_keys = {
            "id", "trial_id", "perpetrator_drug", "victim_drug",
            "interaction_mechanism", "risk_classification",
            "recommendation", "assessed_by", "assessment_date",
        }
        assert expected_keys.issubset(set(data.keys()))

    @pytest.mark.anyio
    async def test_metrics_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        expected_keys = {
            "total_studies", "studies_by_type", "studies_by_status",
            "total_samples", "samples_by_status", "samples_analyzed",
            "samples_failed_qc", "total_escalations", "escalations_by_decision",
            "total_exposure_analyses", "total_ddi_assessments", "ddi_by_risk",
            "avg_sample_analysis_rate",
        }
        assert expected_keys == set(data.keys())


# ===========================================================================
# Payload helpers (using Pydantic models for service-level tests)
# ===========================================================================


def _make_study_payload(**overrides):
    from app.schemas.clinical_pharmacology import PKStudyCreate
    return PKStudyCreate(**_make_study_create(**overrides))


def _make_study_update_payload(**overrides):
    from app.schemas.clinical_pharmacology import PKStudyUpdate
    return PKStudyUpdate(**overrides)
