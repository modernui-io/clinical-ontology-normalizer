"""Tests for CMO-1.4: Clinical Validation Study Design.

Tests cover:
- Study creation and lifecycle
- Case recording and study status transitions
- Sensitivity, specificity, PPV, NPV calculation
- Cohen's Kappa inter-rater agreement
- Confusion matrix construction
- Edge cases (perfect agreement, no agreement, empty study)
- API endpoints via TestClient
"""

from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from app.schemas.validation_study import (
    ConfusionMatrix,
    ScreeningResult,
    StudyCaseCreate,
    StudyMethodology,
    StudyStatus,
    ValidationStudyCreate,
)
from app.services.validation_study_service import ValidationStudyService


# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture()
def service() -> ValidationStudyService:
    """Fresh ValidationStudyService for each test."""
    return ValidationStudyService()


@pytest.fixture()
def study_create() -> ValidationStudyCreate:
    """Default study creation payload."""
    return ValidationStudyCreate(
        name="AD Screening Validation",
        description="Validate screening accuracy for Dupixent AD trial",
        trial_id="trial-001",
        sample_size=100,
        methodology=StudyMethodology.RETROSPECTIVE_CHART_REVIEW,
    )


def _make_case(
    patient_id: str = "patient-1",
    system: ScreeningResult = ScreeningResult.ELIGIBLE,
    gold: ScreeningResult = ScreeningResult.ELIGIBLE,
    reviewer: str = "dr-smith",
) -> StudyCaseCreate:
    return StudyCaseCreate(
        patient_id=patient_id,
        system_result=system,
        gold_standard_result=gold,
        reviewer_id=reviewer,
    )


# ==============================================================================
# Study Creation Tests
# ==============================================================================


class TestStudyCreation:
    def test_create_study(self, service: ValidationStudyService, study_create: ValidationStudyCreate):
        study = service.create_study(study_create)
        assert study.id is not None
        assert study.name == "AD Screening Validation"
        assert study.trial_id == "trial-001"
        assert study.sample_size == 100
        assert study.methodology == StudyMethodology.RETROSPECTIVE_CHART_REVIEW
        assert study.status == StudyStatus.DESIGN
        assert study.case_count == 0

    def test_create_study_defaults(self, service: ValidationStudyService):
        create = ValidationStudyCreate(
            name="Minimal Study",
            trial_id="trial-002",
            sample_size=50,
        )
        study = service.create_study(create)
        assert study.description == ""
        assert study.methodology == StudyMethodology.RETROSPECTIVE_CHART_REVIEW

    def test_list_studies(self, service: ValidationStudyService, study_create: ValidationStudyCreate):
        service.create_study(study_create)
        study_create2 = ValidationStudyCreate(
            name="Study 2", trial_id="trial-002", sample_size=50,
        )
        service.create_study(study_create2)
        studies = service.list_studies()
        assert len(studies) == 2

    def test_get_study(self, service: ValidationStudyService, study_create: ValidationStudyCreate):
        study = service.create_study(study_create)
        retrieved = service.get_study(study.id)
        assert retrieved is not None
        assert retrieved.id == study.id

    def test_get_study_not_found(self, service: ValidationStudyService):
        assert service.get_study("nonexistent") is None


# ==============================================================================
# Case Recording Tests
# ==============================================================================


class TestCaseRecording:
    def test_add_case(self, service: ValidationStudyService, study_create: ValidationStudyCreate):
        study = service.create_study(study_create)
        case = service.add_case(study.id, _make_case())
        assert case is not None
        assert case.study_id == study.id
        assert case.patient_id == "patient-1"
        assert case.system_result == ScreeningResult.ELIGIBLE
        assert case.gold_standard_result == ScreeningResult.ELIGIBLE

    def test_add_case_not_found(self, service: ValidationStudyService):
        assert service.add_case("nonexistent", _make_case()) is None

    def test_add_case_with_notes(self, service: ValidationStudyService, study_create: ValidationStudyCreate):
        study = service.create_study(study_create)
        case = service.add_case(
            study.id,
            StudyCaseCreate(
                patient_id="p1",
                system_result=ScreeningResult.ELIGIBLE,
                gold_standard_result=ScreeningResult.INELIGIBLE,
                reviewer_id="dr-jones",
                notes="Borderline case, patient has partial AD remission",
            ),
        )
        assert case is not None
        assert case.notes == "Borderline case, patient has partial AD remission"

    def test_get_cases(self, service: ValidationStudyService, study_create: ValidationStudyCreate):
        study = service.create_study(study_create)
        service.add_case(study.id, _make_case(patient_id="p1"))
        service.add_case(study.id, _make_case(patient_id="p2"))
        cases = service.get_cases(study.id)
        assert len(cases) == 2


# ==============================================================================
# Study Lifecycle Tests
# ==============================================================================


class TestStudyLifecycle:
    def test_design_to_in_progress(self, service: ValidationStudyService, study_create: ValidationStudyCreate):
        study = service.create_study(study_create)
        assert study.status == StudyStatus.DESIGN
        service.add_case(study.id, _make_case())
        updated = service.get_study(study.id)
        assert updated is not None
        assert updated.status == StudyStatus.IN_PROGRESS

    def test_in_progress_to_complete(self, service: ValidationStudyService):
        create = ValidationStudyCreate(
            name="Small Study",
            trial_id="trial-003",
            sample_size=3,
        )
        study = service.create_study(create)
        service.add_case(study.id, _make_case(patient_id="p1"))
        assert service.get_study(study.id).status == StudyStatus.IN_PROGRESS
        service.add_case(study.id, _make_case(patient_id="p2"))
        assert service.get_study(study.id).status == StudyStatus.IN_PROGRESS
        service.add_case(study.id, _make_case(patient_id="p3"))
        assert service.get_study(study.id).status == StudyStatus.COMPLETE

    def test_case_count_updates(self, service: ValidationStudyService, study_create: ValidationStudyCreate):
        study = service.create_study(study_create)
        assert study.case_count == 0
        service.add_case(study.id, _make_case(patient_id="p1"))
        assert service.get_study(study.id).case_count == 1
        service.add_case(study.id, _make_case(patient_id="p2"))
        assert service.get_study(study.id).case_count == 2


# ==============================================================================
# Metrics Computation Tests
# ==============================================================================


class TestMetricsComputation:
    def _create_study_with_cases(
        self,
        service: ValidationStudyService,
        cases: list[tuple[ScreeningResult, ScreeningResult]],
    ) -> str:
        """Helper: create a study and add cases from (system, gold) tuples."""
        create = ValidationStudyCreate(
            name="Test Study",
            trial_id="trial-test",
            sample_size=len(cases),
        )
        study = service.create_study(create)
        for i, (sys, gold) in enumerate(cases):
            service.add_case(
                study.id,
                _make_case(patient_id=f"p{i}", system=sys, gold=gold),
            )
        return study.id

    def test_sensitivity_calculation(self, service: ValidationStudyService):
        """Sensitivity = TP / (TP + FN)."""
        E = ScreeningResult.ELIGIBLE
        I = ScreeningResult.INELIGIBLE
        # 8 TP, 2 FN -> sensitivity = 8/10 = 0.8
        cases = [(E, E)] * 8 + [(I, E)] * 2 + [(I, I)] * 5 + [(E, I)] * 1
        study_id = self._create_study_with_cases(service, cases)
        metrics = service.compute_metrics(study_id)
        assert metrics is not None
        assert metrics.sensitivity == 0.8

    def test_specificity_calculation(self, service: ValidationStudyService):
        """Specificity = TN / (TN + FP)."""
        E = ScreeningResult.ELIGIBLE
        I = ScreeningResult.INELIGIBLE
        # 9 TN, 1 FP -> specificity = 9/10 = 0.9
        cases = [(E, E)] * 5 + [(I, I)] * 9 + [(E, I)] * 1
        study_id = self._create_study_with_cases(service, cases)
        metrics = service.compute_metrics(study_id)
        assert metrics is not None
        assert metrics.specificity == 0.9

    def test_ppv_calculation(self, service: ValidationStudyService):
        """PPV = TP / (TP + FP)."""
        E = ScreeningResult.ELIGIBLE
        I = ScreeningResult.INELIGIBLE
        # 7 TP, 3 FP -> PPV = 7/10 = 0.7
        cases = [(E, E)] * 7 + [(E, I)] * 3 + [(I, I)] * 5
        study_id = self._create_study_with_cases(service, cases)
        metrics = service.compute_metrics(study_id)
        assert metrics is not None
        assert metrics.ppv == 0.7

    def test_npv_calculation(self, service: ValidationStudyService):
        """NPV = TN / (TN + FN)."""
        E = ScreeningResult.ELIGIBLE
        I = ScreeningResult.INELIGIBLE
        # 8 TN, 2 FN -> NPV = 8/10 = 0.8
        cases = [(E, E)] * 5 + [(I, I)] * 8 + [(I, E)] * 2
        study_id = self._create_study_with_cases(service, cases)
        metrics = service.compute_metrics(study_id)
        assert metrics is not None
        assert metrics.npv == 0.8

    def test_accuracy_and_f1(self, service: ValidationStudyService):
        """Accuracy = (TP + TN) / total; F1 = 2*(PPV*Sens)/(PPV+Sens)."""
        E = ScreeningResult.ELIGIBLE
        I = ScreeningResult.INELIGIBLE
        # 8 TP, 7 TN, 2 FP, 3 FN -> total=20
        cases = [(E, E)] * 8 + [(I, I)] * 7 + [(E, I)] * 2 + [(I, E)] * 3
        study_id = self._create_study_with_cases(service, cases)
        metrics = service.compute_metrics(study_id)
        assert metrics is not None
        # Accuracy = (8+7)/20 = 0.75
        assert metrics.accuracy == 0.75
        # Sensitivity = 8/(8+3) = 0.7273
        assert metrics.sensitivity == pytest.approx(8 / 11, abs=0.001)
        # PPV = 8/(8+2) = 0.8
        assert metrics.ppv == 0.8
        # F1 = 2*0.8*0.7273 / (0.8 + 0.7273) = 0.7619
        expected_f1 = 2 * 0.8 * (8 / 11) / (0.8 + 8 / 11)
        assert metrics.f1_score == pytest.approx(expected_f1, abs=0.01)

    def test_confusion_matrix(self, service: ValidationStudyService):
        E = ScreeningResult.ELIGIBLE
        I = ScreeningResult.INELIGIBLE
        cases = [(E, E)] * 10 + [(I, I)] * 20 + [(E, I)] * 3 + [(I, E)] * 2
        study_id = self._create_study_with_cases(service, cases)
        metrics = service.compute_metrics(study_id)
        assert metrics is not None
        cm = metrics.confusion_matrix
        assert cm.true_positive == 10
        assert cm.true_negative == 20
        assert cm.false_positive == 3
        assert cm.false_negative == 2

    def test_cohens_kappa(self, service: ValidationStudyService):
        """Test Cohen's Kappa computation with known values."""
        E = ScreeningResult.ELIGIBLE
        I = ScreeningResult.INELIGIBLE
        # Using a well-known example:
        # TP=20, TN=15, FP=10, FN=5 -> total=50
        cases = [(E, E)] * 20 + [(I, I)] * 15 + [(E, I)] * 10 + [(I, E)] * 5
        study_id = self._create_study_with_cases(service, cases)
        metrics = service.compute_metrics(study_id)
        assert metrics is not None

        # Manual calculation:
        # p_o = (20+15)/50 = 0.7
        # sys_pos = 30, sys_neg = 20, gold_pos = 25, gold_neg = 25
        # p_e = (30*25 + 20*25) / (50*50) = (750 + 500) / 2500 = 0.5
        # kappa = (0.7 - 0.5) / (1 - 0.5) = 0.4
        assert metrics.cohens_kappa == pytest.approx(0.4, abs=0.001)

    def test_perfect_agreement(self, service: ValidationStudyService):
        """Perfect agreement: all cases agree -> kappa=1.0, accuracy=1.0."""
        E = ScreeningResult.ELIGIBLE
        I = ScreeningResult.INELIGIBLE
        cases = [(E, E)] * 10 + [(I, I)] * 10
        study_id = self._create_study_with_cases(service, cases)
        metrics = service.compute_metrics(study_id)
        assert metrics is not None
        assert metrics.sensitivity == 1.0
        assert metrics.specificity == 1.0
        assert metrics.ppv == 1.0
        assert metrics.npv == 1.0
        assert metrics.accuracy == 1.0
        assert metrics.f1_score == 1.0
        assert metrics.cohens_kappa == 1.0

    def test_no_agreement(self, service: ValidationStudyService):
        """Complete disagreement: system always wrong."""
        E = ScreeningResult.ELIGIBLE
        I = ScreeningResult.INELIGIBLE
        # All FP and FN -- no agreement
        cases = [(E, I)] * 10 + [(I, E)] * 10
        study_id = self._create_study_with_cases(service, cases)
        metrics = service.compute_metrics(study_id)
        assert metrics is not None
        assert metrics.sensitivity == 0.0
        assert metrics.specificity == 0.0
        assert metrics.accuracy == 0.0
        assert metrics.cohens_kappa is not None
        assert metrics.cohens_kappa < 0

    def test_empty_study_metrics(self, service: ValidationStudyService):
        """Metrics for a study with no cases."""
        create = ValidationStudyCreate(
            name="Empty",
            trial_id="trial-empty",
            sample_size=10,
        )
        study = service.create_study(create)
        metrics = service.compute_metrics(study.id)
        assert metrics is not None
        assert metrics.total_cases == 0
        assert metrics.sensitivity is None
        assert metrics.specificity is None
        assert metrics.cohens_kappa is None

    def test_metrics_not_found(self, service: ValidationStudyService):
        assert service.compute_metrics("nonexistent") is None

    def test_confidence_intervals(self, service: ValidationStudyService):
        """Verify Wilson CI is computed for sensitivity and specificity."""
        E = ScreeningResult.ELIGIBLE
        I = ScreeningResult.INELIGIBLE
        cases = [(E, E)] * 90 + [(I, E)] * 10 + [(I, I)] * 80 + [(E, I)] * 20
        study_id = self._create_study_with_cases(service, cases)
        metrics = service.compute_metrics(study_id)
        assert metrics is not None
        assert metrics.sensitivity_ci is not None
        assert metrics.sensitivity_ci.lower < metrics.sensitivity
        assert metrics.sensitivity_ci.upper > metrics.sensitivity
        assert metrics.specificity_ci is not None
        assert metrics.specificity_ci.lower < metrics.specificity
        assert metrics.specificity_ci.upper > metrics.specificity


# ==============================================================================
# Report Tests
# ==============================================================================


class TestStudyReport:
    def test_report_with_metrics(self, service: ValidationStudyService):
        E = ScreeningResult.ELIGIBLE
        I = ScreeningResult.INELIGIBLE
        create = ValidationStudyCreate(
            name="Report Test",
            trial_id="trial-report",
            sample_size=10,
        )
        study = service.create_study(create)
        for i in range(10):
            sys = E if i < 8 else I
            gold = E if i < 7 else I
            service.add_case(study.id, _make_case(patient_id=f"p{i}", system=sys, gold=gold))

        report = service.get_study_report(study.id)
        assert report is not None
        assert report.sample_size_achieved == 10
        assert report.completion_rate == 1.0
        assert report.metrics is not None
        assert report.study.status == StudyStatus.COMPLETE
        # Check target assessment
        assert report.meets_sensitivity_target is not None
        assert report.meets_specificity_target is not None

    def test_report_not_found(self, service: ValidationStudyService):
        assert service.get_study_report("nonexistent") is None

    def test_report_empty_study(self, service: ValidationStudyService):
        create = ValidationStudyCreate(
            name="Empty Report",
            trial_id="trial-empty",
            sample_size=50,
        )
        study = service.create_study(create)
        report = service.get_study_report(study.id)
        assert report is not None
        assert report.sample_size_achieved == 0
        assert report.completion_rate == 0.0


# ==============================================================================
# API Endpoint Tests
# ==============================================================================


class TestAPIEndpoints:
    @pytest.fixture()
    def client(self) -> TestClient:
        """Create a TestClient that hits the validation study endpoints."""
        from app.main import app
        return TestClient(app)

    def test_create_study_endpoint(self, client: TestClient):
        resp = client.post(
            "/api/v1/validation/studies",
            json={
                "name": "API Test Study",
                "trial_id": "trial-api",
                "sample_size": 50,
                "methodology": "RETROSPECTIVE_CHART_REVIEW",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "API Test Study"
        assert data["status"] == "DESIGN"

    def test_list_studies_endpoint(self, client: TestClient):
        client.post(
            "/api/v1/validation/studies",
            json={"name": "S1", "trial_id": "t1", "sample_size": 10},
        )
        resp = client.get("/api/v1/validation/studies")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1

    def test_get_study_endpoint(self, client: TestClient):
        create_resp = client.post(
            "/api/v1/validation/studies",
            json={"name": "S2", "trial_id": "t2", "sample_size": 10},
        )
        study_id = create_resp.json()["id"]
        resp = client.get(f"/api/v1/validation/studies/{study_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == study_id

    def test_get_study_not_found_endpoint(self, client: TestClient):
        resp = client.get("/api/v1/validation/studies/nonexistent")
        assert resp.status_code == 404

    def test_add_case_endpoint(self, client: TestClient):
        create_resp = client.post(
            "/api/v1/validation/studies",
            json={"name": "S3", "trial_id": "t3", "sample_size": 10},
        )
        study_id = create_resp.json()["id"]
        resp = client.post(
            f"/api/v1/validation/studies/{study_id}/cases",
            json={
                "patient_id": "p1",
                "system_result": "ELIGIBLE",
                "gold_standard_result": "ELIGIBLE",
                "reviewer_id": "dr-test",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_id"] == "p1"
        assert data["system_result"] == "ELIGIBLE"

    def test_metrics_endpoint(self, client: TestClient):
        create_resp = client.post(
            "/api/v1/validation/studies",
            json={"name": "S4", "trial_id": "t4", "sample_size": 2},
        )
        study_id = create_resp.json()["id"]
        client.post(
            f"/api/v1/validation/studies/{study_id}/cases",
            json={
                "patient_id": "p1",
                "system_result": "ELIGIBLE",
                "gold_standard_result": "ELIGIBLE",
                "reviewer_id": "dr-test",
            },
        )
        client.post(
            f"/api/v1/validation/studies/{study_id}/cases",
            json={
                "patient_id": "p2",
                "system_result": "INELIGIBLE",
                "gold_standard_result": "INELIGIBLE",
                "reviewer_id": "dr-test",
            },
        )
        resp = client.get(f"/api/v1/validation/studies/{study_id}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sensitivity"] == 1.0
        assert data["specificity"] == 1.0
        assert "confusion_matrix" in data

    def test_report_endpoint(self, client: TestClient):
        create_resp = client.post(
            "/api/v1/validation/studies",
            json={"name": "S5", "trial_id": "t5", "sample_size": 2},
        )
        study_id = create_resp.json()["id"]
        client.post(
            f"/api/v1/validation/studies/{study_id}/cases",
            json={
                "patient_id": "p1",
                "system_result": "ELIGIBLE",
                "gold_standard_result": "ELIGIBLE",
                "reviewer_id": "dr-test",
            },
        )
        resp = client.get(f"/api/v1/validation/studies/{study_id}/report")
        assert resp.status_code == 200
        data = resp.json()
        assert "study" in data
        assert "metrics" in data
        assert data["sample_size_achieved"] == 1
        assert data["completion_rate"] == 0.5
