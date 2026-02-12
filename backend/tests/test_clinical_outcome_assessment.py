"""Tests for Clinical Outcome Assessment Management (COA-MGT).

Covers:
- Seed data verification (instruments, assessments, validations, translations, compliance reports)
- Instrument CRUD (create, read, update, delete, list, filter by trial)
- Assessment CRUD (create, read, update, delete, list, filter by trial/instrument)
- Validation CRUD (create, read, update, delete, list, filter by instrument)
- Translation CRUD (create, read, update, delete, list, filter by instrument)
- Compliance Report CRUD (create, read, update, delete, list, filter by trial/instrument)
- Metrics computation
- Error handling (404s)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.clinical_outcome_assessment_service import (
    ClinicalOutcomeAssessmentService,
    get_clinical_outcome_assessment_service,
    reset_clinical_outcome_assessment_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/clinical-outcome-assessment"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_clinical_outcome_assessment_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ClinicalOutcomeAssessmentService:
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


def _make_instrument_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "instrument_name": "Test PRO Instrument",
        "coa_type": "patient_reported_outcome",
        "description": "A test patient-reported outcome instrument",
        "version": "1.0",
        "created_by": "Dr. Test",
        "domains": ["domain_a", "domain_b"],
        "total_items": 10,
    }
    defaults.update(overrides)
    return defaults


def _make_assessment_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "instrument_id": "COA-INST-001",
        "trial_id": EYLEA_TRIAL,
        "subject_id": "PT-9999",
        "site_id": "SITE-101",
        "visit": "Week 48",
        "frequency": "monthly",
        "scheduled_date": now.isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_validation_create(**overrides) -> dict:
    defaults = {
        "instrument_id": "COA-INST-001",
        "validation_level": "reliability",
        "study_name": "Test Validation Study",
        "population": "Test population",
        "validated_by": "Dr. Validator",
        "sample_size": 100,
    }
    defaults.update(overrides)
    return defaults


def _make_translation_create(**overrides) -> dict:
    defaults = {
        "instrument_id": "COA-INST-001",
        "target_language": "ru",
        "target_country": "Russia",
        "translation_method": "forward_backward",
    }
    defaults.update(overrides)
    return defaults


def _make_compliance_report_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "instrument_id": "COA-INST-001",
        "reporting_period_start": (now - timedelta(days=30)).isoformat(),
        "reporting_period_end": now.isoformat(),
        "generated_by": "Test Operator",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_instruments_count(self, svc: ClinicalOutcomeAssessmentService):
        instruments = svc.list_instruments()
        assert len(instruments) == 12

    def test_seed_instruments_across_trials(self, svc: ClinicalOutcomeAssessmentService):
        eylea = svc.list_instruments(trial_id=EYLEA_TRIAL)
        dupixent = svc.list_instruments(trial_id=DUPIXENT_TRIAL)
        libtayo = svc.list_instruments(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) == 4
        assert len(dupixent) == 4
        assert len(libtayo) == 4

    def test_seed_assessments_count(self, svc: ClinicalOutcomeAssessmentService):
        assessments = svc.list_assessments()
        assert len(assessments) == 15

    def test_seed_validations_count(self, svc: ClinicalOutcomeAssessmentService):
        validations = svc.list_validations()
        assert len(validations) == 10

    def test_seed_translations_count(self, svc: ClinicalOutcomeAssessmentService):
        translations = svc.list_translations()
        assert len(translations) == 10

    def test_seed_compliance_reports_count(self, svc: ClinicalOutcomeAssessmentService):
        reports = svc.list_compliance_reports()
        assert len(reports) == 10

    def test_seed_coa_types_present(self, svc: ClinicalOutcomeAssessmentService):
        instruments = svc.list_instruments()
        types = {i.coa_type.value for i in instruments}
        assert "patient_reported_outcome" in types
        assert "clinician_reported_outcome" in types
        assert "observer_reported_outcome" in types
        assert "performance_outcome" in types

    def test_seed_instrument_statuses_present(self, svc: ClinicalOutcomeAssessmentService):
        instruments = svc.list_instruments()
        statuses = {i.status.value for i in instruments}
        assert "validated" in statuses
        assert "regulatory_qualified" in statuses

    def test_seed_assessment_statuses_present(self, svc: ClinicalOutcomeAssessmentService):
        assessments = svc.list_assessments()
        statuses = {a.completion_status.value for a in assessments}
        assert "completed" in statuses
        assert "missed" in statuses
        assert "partially_completed" in statuses


# =====================================================================
# INSTRUMENT CRUD
# =====================================================================


class TestInstrumentCrud:
    """Test instrument create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_instruments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/instruments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_instruments_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/instruments", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_instrument(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/instruments/COA-INST-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "COA-INST-001"
        assert data["instrument_name"] == "NEI VFQ-25"

    @pytest.mark.anyio
    async def test_get_instrument_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/instruments/COA-INST-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_instrument(self, client: AsyncClient):
        payload = _make_instrument_create()
        resp = await client.post(f"{API_PREFIX}/instruments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["instrument_name"] == "Test PRO Instrument"
        assert data["id"].startswith("COA-INST-")

    @pytest.mark.anyio
    async def test_update_instrument(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/instruments/COA-INST-001",
            json={"status": "regulatory_qualified", "scoring_algorithm": "Updated algorithm"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "regulatory_qualified"
        assert data["scoring_algorithm"] == "Updated algorithm"

    @pytest.mark.anyio
    async def test_update_instrument_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/instruments/COA-INST-NONEXISTENT",
            json={"status": "validated"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_instrument(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/instruments/COA-INST-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/instruments/COA-INST-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_instrument_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/instruments/COA-INST-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# ASSESSMENT CRUD
# =====================================================================


class TestAssessmentCrud:
    """Test assessment create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15

    @pytest.mark.anyio
    async def test_list_assessments_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_assessments_filter_instrument(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/assessments", params={"instrument_id": "COA-INST-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["instrument_id"] == "COA-INST-001"

    @pytest.mark.anyio
    async def test_get_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/COA-ASM-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "COA-ASM-001"
        assert data["subject_id"] == "PT-1001"

    @pytest.mark.anyio
    async def test_get_assessment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/COA-ASM-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_assessment(self, client: AsyncClient):
        payload = _make_assessment_create()
        resp = await client.post(f"{API_PREFIX}/assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["subject_id"] == "PT-9999"
        assert data["id"].startswith("COA-ASM-")

    @pytest.mark.anyio
    async def test_update_assessment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/assessments/COA-ASM-001",
            json={"completion_status": "completed", "total_score": 85.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["completion_status"] == "completed"
        assert data["total_score"] == 85.0

    @pytest.mark.anyio
    async def test_update_assessment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/assessments/COA-ASM-NONEXISTENT",
            json={"total_score": 50.0},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_assessment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/assessments/COA-ASM-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/assessments/COA-ASM-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_assessment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/assessments/COA-ASM-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# VALIDATION CRUD
# =====================================================================


class TestValidationCrud:
    """Test instrument validation CRUD operations."""

    @pytest.mark.anyio
    async def test_list_validations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_validations_filter_instrument(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/validations", params={"instrument_id": "COA-INST-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["instrument_id"] == "COA-INST-001"

    @pytest.mark.anyio
    async def test_get_validation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations/COA-VAL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "COA-VAL-001"
        assert data["validation_level"] == "full_psychometric"

    @pytest.mark.anyio
    async def test_get_validation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations/COA-VAL-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_validation(self, client: AsyncClient):
        payload = _make_validation_create()
        resp = await client.post(f"{API_PREFIX}/validations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["study_name"] == "Test Validation Study"
        assert data["id"].startswith("COA-VAL-")

    @pytest.mark.anyio
    async def test_update_validation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/validations/COA-VAL-001",
            json={"cronbach_alpha": 0.95, "conclusion": "Updated conclusion"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["cronbach_alpha"] == 0.95
        assert data["conclusion"] == "Updated conclusion"

    @pytest.mark.anyio
    async def test_update_validation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/validations/COA-VAL-NONEXISTENT",
            json={"cronbach_alpha": 0.9},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_validation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/validations/COA-VAL-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/validations/COA-VAL-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_validation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/validations/COA-VAL-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# TRANSLATION CRUD
# =====================================================================


class TestTranslationCrud:
    """Test translation adaptation CRUD operations."""

    @pytest.mark.anyio
    async def test_list_translations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/translations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_translations_filter_instrument(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/translations", params={"instrument_id": "COA-INST-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["instrument_id"] == "COA-INST-001"

    @pytest.mark.anyio
    async def test_get_translation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/translations/COA-TRN-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "COA-TRN-001"
        assert data["target_language"] == "es"

    @pytest.mark.anyio
    async def test_get_translation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/translations/COA-TRN-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_translation(self, client: AsyncClient):
        payload = _make_translation_create()
        resp = await client.post(f"{API_PREFIX}/translations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["target_language"] == "ru"
        assert data["id"].startswith("COA-TRN-")

    @pytest.mark.anyio
    async def test_update_translation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/translations/COA-TRN-005",
            json={"status": "completed", "harmonized": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["harmonized"] is True

    @pytest.mark.anyio
    async def test_update_translation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/translations/COA-TRN-NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_translation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/translations/COA-TRN-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/translations/COA-TRN-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_translation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/translations/COA-TRN-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# COMPLIANCE REPORT CRUD
# =====================================================================


class TestComplianceReportCrud:
    """Test compliance report CRUD operations."""

    @pytest.mark.anyio
    async def test_list_compliance_reports(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance-reports")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_compliance_reports_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/compliance-reports", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_compliance_reports_filter_instrument(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/compliance-reports", params={"instrument_id": "COA-INST-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["instrument_id"] == "COA-INST-001"

    @pytest.mark.anyio
    async def test_get_compliance_report(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance-reports/COA-CMP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "COA-CMP-001"
        assert data["compliance_pct"] == 92.0

    @pytest.mark.anyio
    async def test_get_compliance_report_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance-reports/COA-CMP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_compliance_report(self, client: AsyncClient):
        payload = _make_compliance_report_create()
        resp = await client.post(f"{API_PREFIX}/compliance-reports", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["generated_by"] == "Test Operator"
        assert data["id"].startswith("COA-CMP-")

    @pytest.mark.anyio
    async def test_update_compliance_report(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/compliance-reports/COA-CMP-001",
            json={"total_expected": 200, "total_completed": 190, "compliance_pct": 95.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_expected"] == 200
        assert data["total_completed"] == 190
        assert data["compliance_pct"] == 95.0

    @pytest.mark.anyio
    async def test_update_compliance_report_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/compliance-reports/COA-CMP-NONEXISTENT",
            json={"compliance_pct": 99.0},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_compliance_report(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/compliance-reports/COA-CMP-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/compliance-reports/COA-CMP-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_compliance_report_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/compliance-reports/COA-CMP-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestCOAMetrics:
    """Test COA metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_instruments"] == 12
        assert data["total_assessments"] == 15
        assert data["total_validations"] == 10
        assert data["total_translations"] == 10
        assert data["total_compliance_reports"] == 10
        assert 0.0 <= data["overall_compliance_pct"] <= 100.0
        assert data["avg_data_quality_issues"] >= 0.0

    @pytest.mark.anyio
    async def test_get_metrics_by_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_instruments"] == 4
        assert data["total_assessments"] == 5

    @pytest.mark.anyio
    async def test_metrics_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_instruments"] == 0
        assert data["total_assessments"] == 0

    def test_metrics_instruments_by_type(self, svc: ClinicalOutcomeAssessmentService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.instruments_by_type.values())
        assert total_by_type == metrics.total_instruments

    def test_metrics_instruments_by_status(self, svc: ClinicalOutcomeAssessmentService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.instruments_by_status.values())
        assert total_by_status == metrics.total_instruments

    def test_metrics_assessments_by_status(self, svc: ClinicalOutcomeAssessmentService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.assessments_by_status.values())
        assert total_by_status == metrics.total_assessments

    def test_metrics_validations_by_level(self, svc: ClinicalOutcomeAssessmentService):
        metrics = svc.get_metrics()
        total_by_level = sum(metrics.validations_by_level.values())
        assert total_by_level == metrics.total_validations

    def test_metrics_translations_completed(self, svc: ClinicalOutcomeAssessmentService):
        metrics = svc.get_metrics()
        assert metrics.translations_completed <= metrics.total_translations
        assert metrics.translations_completed > 0


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_clinical_outcome_assessment_service()
        svc2 = get_clinical_outcome_assessment_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_clinical_outcome_assessment_service()
        svc2 = reset_clinical_outcome_assessment_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_clinical_outcome_assessment_service()
        svc.delete_instrument("COA-INST-001")
        assert svc.get_instrument("COA-INST-001") is None
        svc2 = reset_clinical_outcome_assessment_service()
        assert svc2.get_instrument("COA-INST-001") is not None


# =====================================================================
# EDGE CASES AND DATA VALIDATION
# =====================================================================


class TestEdgeCases:
    """Test edge cases and data validation."""

    @pytest.mark.anyio
    async def test_instrument_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/instruments/COA-INST-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "instrument_name" in data
        assert "coa_type" in data
        assert "domains" in data
        assert "status" in data
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_assessment_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/COA-ASM-001")
        data = resp.json()
        assert "id" in data
        assert "instrument_id" in data
        assert "trial_id" in data
        assert "subject_id" in data
        assert "completion_status" in data
        assert "domain_scores" in data

    @pytest.mark.anyio
    async def test_validation_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations/COA-VAL-001")
        data = resp.json()
        assert "id" in data
        assert "instrument_id" in data
        assert "validation_level" in data
        assert "sample_size" in data
        assert "cronbach_alpha" in data

    @pytest.mark.anyio
    async def test_translation_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/translations/COA-TRN-001")
        data = resp.json()
        assert "id" in data
        assert "instrument_id" in data
        assert "target_language" in data
        assert "target_country" in data
        assert "harmonized" in data

    @pytest.mark.anyio
    async def test_compliance_report_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance-reports/COA-CMP-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "instrument_id" in data
        assert "compliance_pct" in data
        assert "by_site" in data
        assert "by_visit" in data

    @pytest.mark.anyio
    async def test_metrics_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "total_instruments" in data
        assert "instruments_by_type" in data
        assert "instruments_by_status" in data
        assert "total_assessments" in data
        assert "assessments_by_status" in data
        assert "overall_compliance_pct" in data
        assert "total_validations" in data
        assert "validations_by_level" in data
        assert "total_translations" in data
        assert "translations_completed" in data
        assert "total_compliance_reports" in data
        assert "avg_data_quality_issues" in data

    def test_completed_assessments_have_scores(self, svc: ClinicalOutcomeAssessmentService):
        assessments = svc.list_assessments()
        completed = [a for a in assessments if a.completion_status.value == "completed"]
        for a in completed:
            assert a.total_score is not None

    def test_missed_assessments_have_no_scores(self, svc: ClinicalOutcomeAssessmentService):
        assessments = svc.list_assessments()
        missed = [a for a in assessments if a.completion_status.value == "missed"]
        for a in missed:
            assert a.total_score is None

    @pytest.mark.anyio
    async def test_list_instruments_empty_trial_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/instruments", params={"trial_id": "NONEXISTENT"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_validations_empty_instrument_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/validations", params={"instrument_id": "NONEXISTENT"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_translations_empty_instrument_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/translations", params={"instrument_id": "NONEXISTENT"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_compliance_reports_empty_trial_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/compliance-reports", params={"trial_id": "NONEXISTENT"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    def test_eylea_compliance_reports_count(self, svc: ClinicalOutcomeAssessmentService):
        reports = svc.list_compliance_reports(trial_id=EYLEA_TRIAL)
        assert len(reports) == 3

    def test_dupixent_compliance_reports_count(self, svc: ClinicalOutcomeAssessmentService):
        reports = svc.list_compliance_reports(trial_id=DUPIXENT_TRIAL)
        assert len(reports) == 4

    def test_libtayo_compliance_reports_count(self, svc: ClinicalOutcomeAssessmentService):
        reports = svc.list_compliance_reports(trial_id=LIBTAYO_TRIAL)
        assert len(reports) == 3
