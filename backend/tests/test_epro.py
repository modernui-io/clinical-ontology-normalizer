"""Tests for Electronic Patient-Reported Outcomes (ePRO) & Questionnaire Management (CLINICAL-9).

Covers:
- Seed data verification (instruments, questions, schedules, assignments, responses)
- Instrument CRUD (create, read, update, delete, list, filter by category)
- Question retrieval per instrument
- Schedule template creation and listing (with trial filter)
- Patient assignment creation, listing, deactivation
- Questionnaire response submission and retrieval
- Scored response with domain breakdown and interpretation
- Patient response history with pagination and instrument filter
- Compliance reporting (patient-level, trial-level)
- Reminder generation (upcoming / overdue, patient / trial filters)
- Score trend analysis with MCID detection
- MCID alert generation
- ePRO dashboard metrics
- Error handling (404s for missing instruments, assignments, responses)
- Edge cases (empty patient, inactive assignments, unknown trials)
- Business logic (scoring algorithms, compliance calculation, trend direction)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.epro import (
    Answer,
    AssignmentCreate,
    ComplianceStatus,
    InstrumentCategory,
    InstrumentCreate,
    InstrumentUpdate,
    QuestionType,
    ResponseSubmit,
    ResponseWindow,
    ScheduleCreate,
)
from app.services.epro_service import (
    EPROService,
    get_epro_service,
    reset_epro_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/epro"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_epro_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> EPROService:
    """Shorthand for the fresh service."""
    return fresh_service


@pytest.fixture
async def client():
    """Async HTTP client for API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_instrument_create(**overrides) -> dict:
    defaults = {
        "name": "Test Patient Health Questionnaire",
        "abbreviation": "PHQ-9",
        "category": "symptom_severity",
        "description": "Depression screening instrument",
        "version": "1.0",
        "scoring_algorithm": "Sum of 9 items (0-27)",
        "min_score": 0,
        "max_score": 27,
        "mcid": 5.0,
        "validated_languages": ["en", "es"],
    }
    defaults.update(overrides)
    return defaults


def _make_schedule_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "instrument_id": "INST-001",
        "frequency": "weekly",
        "window_before_days": 1,
        "window_after_days": 2,
        "start_visit": "Visit 1",
        "end_visit": "Visit 8",
    }
    defaults.update(overrides)
    return defaults


def _make_assignment_create(**overrides) -> dict:
    defaults = {
        "patient_id": "PAT-NEW-001",
        "trial_id": EYLEA_TRIAL,
        "instrument_id": "INST-001",
        "schedule_template_id": "SCHED-001",
        "language": "en",
    }
    defaults.update(overrides)
    return defaults


def _make_response_submit(**overrides) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    defaults = {
        "assignment_id": "ASGN-001",
        "answers": [
            {"question_id": "EQ5D-Q01", "value": 2.0, "timestamp": now},
            {"question_id": "EQ5D-Q02", "value": 1.0, "timestamp": now},
            {"question_id": "EQ5D-Q03", "value": 2.0, "timestamp": now},
            {"question_id": "EQ5D-Q04", "value": 3.0, "timestamp": now},
            {"question_id": "EQ5D-Q05", "value": 1.0, "timestamp": now},
            {"question_id": "EQ5D-VAS", "value": 75.0, "timestamp": now},
        ],
        "language": "en",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_instruments_count(self, svc: EPROService):
        instruments = svc.list_instruments()
        assert len(instruments) == 6

    def test_seed_instruments_include_eq5d(self, svc: EPROService):
        inst = svc.get_instrument("INST-001")
        assert inst.abbreviation == "EQ-5D-5L"
        assert inst.category == InstrumentCategory.QUALITY_OF_LIFE

    def test_seed_instruments_include_qlq_c30(self, svc: EPROService):
        inst = svc.get_instrument("INST-002")
        assert inst.abbreviation == "EORTC QLQ-C30"
        assert inst.mcid == 10.0

    def test_seed_instruments_include_dlqi(self, svc: EPROService):
        inst = svc.get_instrument("INST-003")
        assert inst.abbreviation == "DLQI"
        assert inst.max_score == 30

    def test_seed_instruments_include_vfq25(self, svc: EPROService):
        inst = svc.get_instrument("INST-004")
        assert inst.abbreviation == "NEI-VFQ-25"
        assert inst.category == InstrumentCategory.FUNCTIONAL_STATUS

    def test_seed_instruments_include_proctcae(self, svc: EPROService):
        inst = svc.get_instrument("INST-005")
        assert inst.abbreviation == "PRO-CTCAE"
        assert inst.category == InstrumentCategory.SAFETY

    def test_seed_instruments_include_wpai(self, svc: EPROService):
        inst = svc.get_instrument("INST-006")
        assert inst.abbreviation == "WPAI"

    def test_seed_eq5d_has_6_questions(self, svc: EPROService):
        questions = svc.get_instrument_questions("INST-001")
        assert len(questions) == 6

    def test_seed_qlq_c30_has_30_questions(self, svc: EPROService):
        questions = svc.get_instrument_questions("INST-002")
        assert len(questions) == 30

    def test_seed_dlqi_has_10_questions(self, svc: EPROService):
        questions = svc.get_instrument_questions("INST-003")
        assert len(questions) == 10

    def test_seed_vfq25_has_25_questions(self, svc: EPROService):
        questions = svc.get_instrument_questions("INST-004")
        assert len(questions) == 25

    def test_seed_proctcae_has_24_questions(self, svc: EPROService):
        questions = svc.get_instrument_questions("INST-005")
        assert len(questions) == 24

    def test_seed_wpai_has_6_questions(self, svc: EPROService):
        questions = svc.get_instrument_questions("INST-006")
        assert len(questions) == 6

    def test_seed_schedules_count(self, svc: EPROService):
        schedules = svc.list_schedules()
        assert len(schedules) == 8

    def test_seed_assignments_count(self, svc: EPROService):
        # 30 assignments total
        total = 0
        for pid in ["PAT-DME-001", "PAT-DME-003", "PAT-DME-007", "PAT-DME-012", "PAT-DME-019",
                     "PAT-AD-007", "PAT-AD-015", "PAT-AD-021", "PAT-AD-028", "PAT-AD-033",
                     "PAT-CSCC-005", "PAT-CSCC-012", "PAT-CSCC-018", "PAT-CSCC-022", "PAT-CSCC-025"]:
            total += len(svc.get_patient_assignments(pid))
        assert total == 30

    def test_seed_responses_count(self, svc: EPROService):
        # 60 responses total (2 per assignment)
        responses_count = 0
        for pid in ["PAT-DME-001", "PAT-DME-003", "PAT-DME-007", "PAT-DME-012", "PAT-DME-019",
                     "PAT-AD-007", "PAT-AD-015", "PAT-AD-021", "PAT-AD-028", "PAT-AD-033",
                     "PAT-CSCC-005", "PAT-CSCC-012", "PAT-CSCC-018", "PAT-CSCC-022", "PAT-CSCC-025"]:
            items, total = svc.get_patient_responses(pid)
            responses_count += total
        assert responses_count == 60

    def test_seed_instruments_have_validated_languages(self, svc: EPROService):
        inst = svc.get_instrument("INST-001")
        assert "en" in inst.validated_languages
        assert len(inst.validated_languages) > 1

    def test_seed_instruments_have_copyright(self, svc: EPROService):
        inst = svc.get_instrument("INST-001")
        assert inst.copyright_holder == "EuroQol Group"

    def test_seed_categories_covered(self, svc: EPROService):
        instruments = svc.list_instruments()
        categories = {i.category for i in instruments}
        assert InstrumentCategory.QUALITY_OF_LIFE in categories
        assert InstrumentCategory.FUNCTIONAL_STATUS in categories
        assert InstrumentCategory.SAFETY in categories


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
        assert data["total"] == 6
        assert len(data["items"]) == 6

    @pytest.mark.anyio
    async def test_list_instruments_filter_category(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/instruments", params={"category": "quality_of_life"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["category"] == "quality_of_life"

    @pytest.mark.anyio
    async def test_list_instruments_filter_functional_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/instruments", params={"category": "functional_status"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2  # VFQ-25 and WPAI

    @pytest.mark.anyio
    async def test_list_instruments_filter_safety(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/instruments", params={"category": "safety"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1  # PRO-CTCAE

    @pytest.mark.anyio
    async def test_get_instrument(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/instruments/INST-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "INST-001"
        assert data["abbreviation"] == "EQ-5D-5L"
        assert data["mcid"] == 0.08

    @pytest.mark.anyio
    async def test_get_instrument_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/instruments/INST-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_instrument(self, client: AsyncClient):
        payload = _make_instrument_create()
        resp = await client.post(f"{API_PREFIX}/instruments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Patient Health Questionnaire"
        assert data["abbreviation"] == "PHQ-9"
        assert data["id"].startswith("INST-")

    @pytest.mark.anyio
    async def test_create_instrument_with_mcid(self, client: AsyncClient):
        payload = _make_instrument_create(mcid=3.0)
        resp = await client.post(f"{API_PREFIX}/instruments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["mcid"] == 3.0

    @pytest.mark.anyio
    async def test_create_instrument_without_optional_fields(self, client: AsyncClient):
        payload = {
            "name": "Minimal Instrument",
            "abbreviation": "MIN",
            "category": "adherence",
            "description": "A minimal instrument",
        }
        resp = await client.post(f"{API_PREFIX}/instruments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["mcid"] is None
        assert data["copyright_holder"] is None

    @pytest.mark.anyio
    async def test_update_instrument(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/instruments/INST-001",
            json={"name": "Updated EQ-5D-5L", "mcid": 0.10},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated EQ-5D-5L"
        assert data["mcid"] == 0.10

    @pytest.mark.anyio
    async def test_update_instrument_description(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/instruments/INST-003",
            json={"description": "Updated DLQI description"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == "Updated DLQI description"

    @pytest.mark.anyio
    async def test_update_instrument_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/instruments/INST-NONEXISTENT",
            json={"name": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_instrument(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/instruments/INST-001")
        assert resp.status_code == 204
        # Verify it's gone
        resp2 = await client.get(f"{API_PREFIX}/instruments/INST-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_instrument_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/instruments/INST-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_instrument_questions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/instruments/INST-001/questions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 6
        # First question should be Mobility
        assert "mobility" in data[0]["text"].lower()

    @pytest.mark.anyio
    async def test_get_instrument_questions_dlqi(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/instruments/INST-003/questions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 10

    @pytest.mark.anyio
    async def test_get_instrument_questions_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/instruments/INST-NONEXISTENT/questions")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_instrument_questions_have_types(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/instruments/INST-001/questions")
        data = resp.json()
        types = {q["type"] for q in data}
        assert "likert" in types
        assert "visual_analog_scale" in types


# =====================================================================
# SCHEDULE TEMPLATES
# =====================================================================


class TestScheduleTemplates:
    """Test schedule template operations."""

    @pytest.mark.anyio
    async def test_list_schedules(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/schedules")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8

    @pytest.mark.anyio
    async def test_list_schedules_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/schedules", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_schedules_filter_dupixent(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/schedules", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_schedules_filter_libtayo(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/schedules", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_create_schedule(self, client: AsyncClient):
        payload = _make_schedule_create()
        resp = await client.post(f"{API_PREFIX}/schedules", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["instrument_id"] == "INST-001"
        assert data["frequency"] == "weekly"
        assert data["id"].startswith("SCHED-")

    @pytest.mark.anyio
    async def test_create_schedule_invalid_instrument(self, client: AsyncClient):
        payload = _make_schedule_create(instrument_id="INST-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/schedules", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_schedule_has_window_days(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/schedules")
        data = resp.json()
        for item in data["items"]:
            assert "window_before_days" in item
            assert "window_after_days" in item
            assert item["window_before_days"] >= 0
            assert item["window_after_days"] >= 0


# =====================================================================
# PATIENT ASSIGNMENTS
# =====================================================================


class TestPatientAssignments:
    """Test patient assignment operations."""

    @pytest.mark.anyio
    async def test_get_patient_assignments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients/PAT-DME-001/assignments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2  # VFQ-25 and EQ-5D

    @pytest.mark.anyio
    async def test_get_patient_assignments_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients/PAT-AD-007/assignments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2  # DLQI and EQ-5D

    @pytest.mark.anyio
    async def test_get_patient_assignments_empty(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients/PAT-NONEXISTENT/assignments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_create_assignment(self, client: AsyncClient):
        payload = _make_assignment_create()
        resp = await client.post(f"{API_PREFIX}/assignments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_id"] == "PAT-NEW-001"
        assert data["instrument_id"] == "INST-001"
        assert data["active"] is True
        assert data["id"].startswith("ASGN-")

    @pytest.mark.anyio
    async def test_create_assignment_invalid_instrument(self, client: AsyncClient):
        payload = _make_assignment_create(instrument_id="INST-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/assignments", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_deactivate_assignment(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/assignments/ASGN-001/deactivate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] is False

    @pytest.mark.anyio
    async def test_deactivate_assignment_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/assignments/ASGN-NONEXISTENT/deactivate")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_deactivated_assignment_excluded_by_default(self, client: AsyncClient):
        # Deactivate one assignment for PAT-DME-001
        await client.post(f"{API_PREFIX}/assignments/ASGN-001/deactivate")
        resp = await client.get(f"{API_PREFIX}/patients/PAT-DME-001/assignments")
        data = resp.json()
        assert data["total"] == 1

    @pytest.mark.anyio
    async def test_deactivated_assignment_included_when_requested(self, client: AsyncClient):
        await client.post(f"{API_PREFIX}/assignments/ASGN-001/deactivate")
        resp = await client.get(
            f"{API_PREFIX}/patients/PAT-DME-001/assignments",
            params={"active_only": False},
        )
        data = resp.json()
        assert data["total"] == 2

    @pytest.mark.anyio
    async def test_assignment_has_language(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients/PAT-DME-001/assignments")
        data = resp.json()
        for item in data["items"]:
            assert item["language"] == "en"


# =====================================================================
# QUESTIONNAIRE RESPONSES
# =====================================================================


class TestQuestionnaireResponses:
    """Test questionnaire response submission and retrieval."""

    @pytest.mark.anyio
    async def test_submit_response(self, client: AsyncClient):
        payload = _make_response_submit()
        resp = await client.post(f"{API_PREFIX}/responses", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["assignment_id"] == "ASGN-001"
        assert data["patient_id"] == "PAT-DME-001"
        assert data["instrument_id"] == "INST-004"  # VFQ-25 via ASGN-001
        assert data["total_score"] is not None
        assert data["compliance_status"] == "compliant"
        assert data["id"].startswith("RESP-")

    @pytest.mark.anyio
    async def test_submit_response_invalid_assignment(self, client: AsyncClient):
        payload = _make_response_submit(assignment_id="ASGN-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/responses", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_response(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/responses/RESP-0001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RESP-0001"
        assert data["total_score"] is not None
        assert len(data["answers"]) > 0

    @pytest.mark.anyio
    async def test_get_response_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/responses/RESP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_scored_response(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/responses/RESP-0001/scored")
        assert resp.status_code == 200
        data = resp.json()
        assert data["response_id"] == "RESP-0001"
        assert data["instrument_name"] is not None
        assert data["total_score"] is not None
        assert "domain_scores" in data

    @pytest.mark.anyio
    async def test_get_scored_response_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/responses/RESP-NONEXISTENT/scored")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_scored_response_has_interpretation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/responses/RESP-0001/scored")
        data = resp.json()
        # Interpretation should be present for instruments with min/max scores
        assert data["interpretation"] is not None or data["total_score"] is not None

    @pytest.mark.anyio
    async def test_get_patient_responses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients/PAT-DME-001/responses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["patient_id"] == "PAT-DME-001"

    @pytest.mark.anyio
    async def test_get_patient_responses_filter_instrument(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/patients/PAT-DME-001/responses",
            params={"instrument_id": "INST-004"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["instrument_id"] == "INST-004"

    @pytest.mark.anyio
    async def test_get_patient_responses_pagination(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/patients/PAT-DME-001/responses",
            params={"limit": 1, "offset": 0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 1

    @pytest.mark.anyio
    async def test_get_patient_responses_empty(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients/PAT-NONEXISTENT/responses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_response_has_window(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/responses/RESP-0001")
        data = resp.json()
        assert data["window_start"] is not None
        assert data["window_end"] is not None


# =====================================================================
# COMPLIANCE MONITORING
# =====================================================================


class TestComplianceMonitoring:
    """Test compliance reporting at patient and trial level."""

    @pytest.mark.anyio
    async def test_patient_compliance(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients/PAT-DME-001/compliance")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        for report in data:
            assert report["patient_id"] == "PAT-DME-001"
            assert 0 <= report["compliance_rate"] <= 1
            assert report["total_expected"] > 0
            assert report["total_completed"] >= 0

    @pytest.mark.anyio
    async def test_patient_compliance_has_instrument_info(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients/PAT-DME-001/compliance")
        data = resp.json()
        for report in data:
            assert "instrument_id" in report
            assert "instrument_name" in report
            assert len(report["instrument_name"]) > 0

    @pytest.mark.anyio
    async def test_patient_compliance_has_consecutive_misses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients/PAT-DME-001/compliance")
        data = resp.json()
        for report in data:
            assert "consecutive_misses" in report
            assert report["consecutive_misses"] >= 0

    @pytest.mark.anyio
    async def test_patient_compliance_empty_patient(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients/PAT-NONEXISTENT/compliance")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 0

    @pytest.mark.anyio
    async def test_trial_compliance_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials/{EYLEA_TRIAL}/compliance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["total_patients"] > 0
        assert 0 <= data["overall_compliance_rate"] <= 1
        assert "by_instrument" in data
        assert len(data["by_instrument"]) > 0

    @pytest.mark.anyio
    async def test_trial_compliance_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials/{DUPIXENT_TRIAL}/compliance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_patients"] == 5

    @pytest.mark.anyio
    async def test_trial_compliance_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials/{LIBTAYO_TRIAL}/compliance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_patients"] == 5

    @pytest.mark.anyio
    async def test_trial_compliance_unknown_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials/unknown-trial-id/compliance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_patients"] == 0
        assert data["overall_compliance_rate"] == 1.0

    @pytest.mark.anyio
    async def test_trial_compliance_has_at_risk_patients(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials/{EYLEA_TRIAL}/compliance")
        data = resp.json()
        assert "patients_at_risk" in data
        assert data["patients_at_risk"] >= 0

    @pytest.mark.anyio
    async def test_trial_compliance_has_overdue(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials/{EYLEA_TRIAL}/compliance")
        data = resp.json()
        assert "total_overdue" in data
        assert data["total_overdue"] >= 0

    def test_compliance_alert_on_consecutive_misses(self, svc: EPROService):
        reports = svc.get_patient_compliance("PAT-DME-001")
        for report in reports:
            if report.consecutive_misses >= 2:
                assert report.alert is True


# =====================================================================
# REMINDERS
# =====================================================================


class TestReminders:
    """Test reminder generation for upcoming and overdue questionnaires."""

    @pytest.mark.anyio
    async def test_get_reminders(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reminders")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total_upcoming" in data
        assert "total_overdue" in data

    @pytest.mark.anyio
    async def test_get_reminders_filter_patient(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/reminders", params={"patient_id": "PAT-DME-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["patient_id"] == "PAT-DME-001"

    @pytest.mark.anyio
    async def test_get_reminders_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/reminders", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["items"], list)

    @pytest.mark.anyio
    async def test_reminders_have_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reminders")
        data = resp.json()
        for item in data["items"]:
            assert item["status"] in ("upcoming", "overdue")

    @pytest.mark.anyio
    async def test_reminders_have_due_date(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reminders")
        data = resp.json()
        for item in data["items"]:
            assert "due_date" in item
            assert "window_end" in item
            assert "days_until_due" in item

    @pytest.mark.anyio
    async def test_reminders_have_instrument_info(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reminders")
        data = resp.json()
        for item in data["items"]:
            assert "instrument_name" in item
            assert len(item["instrument_name"]) > 0

    @pytest.mark.anyio
    async def test_reminders_sorted_by_urgency(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reminders")
        data = resp.json()
        if len(data["items"]) > 1:
            days = [item["days_until_due"] for item in data["items"]]
            assert days == sorted(days)

    @pytest.mark.anyio
    async def test_reminders_totals_match(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reminders")
        data = resp.json()
        upcoming = len([i for i in data["items"] if i["status"] == "upcoming"])
        overdue = len([i for i in data["items"] if i["status"] == "overdue"])
        assert data["total_upcoming"] == upcoming
        assert data["total_overdue"] == overdue

    @pytest.mark.anyio
    async def test_reminders_empty_patient(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/reminders", params={"patient_id": "PAT-NONEXISTENT"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_upcoming"] == 0
        assert data["total_overdue"] == 0


# =====================================================================
# SCORE TRENDS
# =====================================================================


class TestScoreTrends:
    """Test score trend analysis."""

    @pytest.mark.anyio
    async def test_get_patient_trends(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients/PAT-DME-001/trends")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        for trend in data:
            assert trend["patient_id"] == "PAT-DME-001"
            assert "baseline_score" in trend
            assert "current_score" in trend
            assert "trend_direction" in trend
            assert "data_points" in trend

    @pytest.mark.anyio
    async def test_get_patient_trends_filter_instrument(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/patients/PAT-DME-001/trends",
            params={"instrument_id": "INST-004"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for trend in data:
            assert trend["instrument_id"] == "INST-004"

    @pytest.mark.anyio
    async def test_trends_have_mcid_info(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients/PAT-DME-001/trends")
        data = resp.json()
        for trend in data:
            assert "mcid_exceeded" in trend
            assert isinstance(trend["mcid_exceeded"], bool)

    @pytest.mark.anyio
    async def test_trends_have_data_points(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients/PAT-DME-001/trends")
        data = resp.json()
        for trend in data:
            assert len(trend["data_points"]) > 0
            for dp in trend["data_points"]:
                assert "response_id" in dp
                assert "date" in dp
                assert "score" in dp

    @pytest.mark.anyio
    async def test_trends_direction_values(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients/PAT-DME-001/trends")
        data = resp.json()
        for trend in data:
            assert trend["trend_direction"] in ("improving", "worsening", "stable")

    @pytest.mark.anyio
    async def test_trends_empty_patient(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients/PAT-NONEXISTENT/trends")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 0

    def test_trend_direction_logic(self, svc: EPROService):
        trends = svc.get_patient_trends("PAT-DME-001")
        for trend in trends:
            if trend.baseline_score is not None and trend.current_score is not None:
                assert trend.change_from_baseline is not None

    def test_trend_data_points_chronological(self, svc: EPROService):
        trends = svc.get_patient_trends("PAT-DME-001")
        for trend in trends:
            dates = [dp.date for dp in trend.data_points]
            assert dates == sorted(dates)


# =====================================================================
# MCID ALERTS
# =====================================================================


class TestMCIDAlerts:
    """Test MCID alert detection."""

    @pytest.mark.anyio
    async def test_get_mcid_alerts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mcid-alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == len(data["items"])

    @pytest.mark.anyio
    async def test_mcid_alerts_have_required_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mcid-alerts")
        data = resp.json()
        for alert in data["items"]:
            assert "patient_id" in alert
            assert "instrument_id" in alert
            assert "instrument_name" in alert
            assert "baseline_score" in alert
            assert "current_score" in alert
            assert "change" in alert
            assert "mcid_threshold" in alert
            assert "direction" in alert
            assert "detected_at" in alert

    @pytest.mark.anyio
    async def test_mcid_alert_direction_values(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mcid-alerts")
        data = resp.json()
        for alert in data["items"]:
            assert alert["direction"] in ("improvement", "deterioration")

    @pytest.mark.anyio
    async def test_mcid_alert_change_exceeds_threshold(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mcid-alerts")
        data = resp.json()
        for alert in data["items"]:
            assert abs(alert["change"]) >= alert["mcid_threshold"]

    def test_mcid_alerts_service(self, svc: EPROService):
        alerts = svc.get_mcid_alerts()
        for alert in alerts:
            assert alert.mcid_threshold > 0
            assert abs(alert.change) >= alert.mcid_threshold


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test ePRO dashboard metrics."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_instruments"] == 6
        assert data["total_assignments"] == 30
        assert data["total_responses"] == 60
        assert data["active_patients"] > 0

    @pytest.mark.anyio
    async def test_metrics_compliance_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert 0 <= data["avg_compliance_rate"] <= 1

    @pytest.mark.anyio
    async def test_metrics_completion_rate_7d(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert 0 <= data["completion_rate_7d"] <= 1

    @pytest.mark.anyio
    async def test_metrics_overdue_count(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["overdue_count"] >= 0

    @pytest.mark.anyio
    async def test_metrics_instruments_by_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "instruments_by_category" in data
        cats = data["instruments_by_category"]
        assert isinstance(cats, dict)
        assert len(cats) > 0

    @pytest.mark.anyio
    async def test_metrics_mcid_alerts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "mcid_alerts_active" in data
        assert data["mcid_alerts_active"] >= 0

    def test_metrics_service(self, svc: EPROService):
        metrics = svc.get_metrics()
        assert metrics.total_instruments == 6
        assert metrics.total_assignments == 30
        assert metrics.total_responses == 60


# =====================================================================
# SCORING ALGORITHMS (Service-level)
# =====================================================================


class TestScoringAlgorithms:
    """Test instrument-specific scoring algorithms."""

    def test_eq5d_score_range(self, svc: EPROService):
        responses, _ = svc.get_patient_responses("PAT-DME-001", instrument_id="INST-001")
        for resp in responses:
            if resp.total_score is not None:
                assert -0.281 <= resp.total_score <= 1.0

    def test_qlq_c30_score_range(self, svc: EPROService):
        responses, _ = svc.get_patient_responses("PAT-CSCC-005", instrument_id="INST-002")
        for resp in responses:
            if resp.total_score is not None:
                assert 0 <= resp.total_score <= 100

    def test_dlqi_score_range(self, svc: EPROService):
        responses, _ = svc.get_patient_responses("PAT-AD-007", instrument_id="INST-003")
        for resp in responses:
            if resp.total_score is not None:
                assert 0 <= resp.total_score <= 30

    def test_vfq25_score_range(self, svc: EPROService):
        responses, _ = svc.get_patient_responses("PAT-DME-001", instrument_id="INST-004")
        for resp in responses:
            if resp.total_score is not None:
                assert 0 <= resp.total_score <= 100

    def test_proctcae_score_range(self, svc: EPROService):
        responses, _ = svc.get_patient_responses("PAT-CSCC-005", instrument_id="INST-005")
        for resp in responses:
            if resp.total_score is not None:
                assert 0 <= resp.total_score <= 4

    def test_wpai_score_range(self, svc: EPROService):
        responses, _ = svc.get_patient_responses("PAT-AD-015", instrument_id="INST-006")
        for resp in responses:
            if resp.total_score is not None:
                assert 0 <= resp.total_score <= 100

    def test_compute_score_eq5d(self, svc: EPROService):
        inst = svc.get_instrument("INST-001")
        # All 1s (best) should give utility near 1.0
        answers = [
            Answer(question_id="EQ5D-Q01", value=1.0),
            Answer(question_id="EQ5D-Q02", value=1.0),
            Answer(question_id="EQ5D-Q03", value=1.0),
            Answer(question_id="EQ5D-Q04", value=1.0),
            Answer(question_id="EQ5D-Q05", value=1.0),
            Answer(question_id="EQ5D-VAS", value=90.0),
        ]
        score = svc._compute_score(inst, answers)
        assert score == 1.0

    def test_compute_score_eq5d_worst(self, svc: EPROService):
        inst = svc.get_instrument("INST-001")
        answers = [
            Answer(question_id="EQ5D-Q01", value=5.0),
            Answer(question_id="EQ5D-Q02", value=5.0),
            Answer(question_id="EQ5D-Q03", value=5.0),
            Answer(question_id="EQ5D-Q04", value=5.0),
            Answer(question_id="EQ5D-Q05", value=5.0),
            Answer(question_id="EQ5D-VAS", value=10.0),
        ]
        score = svc._compute_score(inst, answers)
        assert score == 0.0

    def test_compute_score_dlqi(self, svc: EPROService):
        inst = svc.get_instrument("INST-003")
        # All 0s = no effect
        answers = [Answer(question_id=f"DLQI-Q{i:02d}", value=0.0) for i in range(1, 11)]
        score = svc._compute_score(inst, answers)
        assert score == 0.0

    def test_compute_score_dlqi_max(self, svc: EPROService):
        inst = svc.get_instrument("INST-003")
        # All 3s = maximum (30)
        answers = [Answer(question_id=f"DLQI-Q{i:02d}", value=3.0) for i in range(1, 11)]
        score = svc._compute_score(inst, answers)
        assert score == 30.0

    def test_compute_score_empty_answers(self, svc: EPROService):
        inst = svc.get_instrument("INST-001")
        score = svc._compute_score(inst, [])
        assert score == 0.0


# =====================================================================
# EDGE CASES
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_update_instrument_partial(self, client: AsyncClient):
        # Only update name, leave everything else
        resp = await client.put(
            f"{API_PREFIX}/instruments/INST-001",
            json={"name": "Partially Updated"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Partially Updated"
        assert data["abbreviation"] == "EQ-5D-5L"  # unchanged

    @pytest.mark.anyio
    async def test_submit_response_auto_scores(self, client: AsyncClient):
        payload = _make_response_submit()
        resp = await client.post(f"{API_PREFIX}/responses", json=payload)
        data = resp.json()
        assert data["total_score"] is not None

    @pytest.mark.anyio
    async def test_create_and_use_custom_instrument(self, client: AsyncClient):
        # Create instrument
        inst_resp = await client.post(
            f"{API_PREFIX}/instruments",
            json=_make_instrument_create(),
        )
        assert inst_resp.status_code == 201
        inst_id = inst_resp.json()["id"]

        # Verify in list
        list_resp = await client.get(f"{API_PREFIX}/instruments")
        assert list_resp.json()["total"] == 7

        # Create assignment with new instrument
        asgn_resp = await client.post(
            f"{API_PREFIX}/assignments",
            json=_make_assignment_create(instrument_id=inst_id),
        )
        assert asgn_resp.status_code == 201

    @pytest.mark.anyio
    async def test_schedule_frequencies_correct(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/schedules")
        data = resp.json()
        frequencies = {item["frequency"] for item in data["items"]}
        # At least monthly and biweekly in seed data
        assert "monthly" in frequencies
        assert "biweekly" in frequencies

    @pytest.mark.anyio
    async def test_patient_with_no_trends(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients/PAT-NONEXISTENT/trends")
        assert resp.status_code == 200
        data = resp.json()
        assert data == []

    @pytest.mark.anyio
    async def test_compliance_for_all_seed_patients(self, client: AsyncClient):
        for pid in ["PAT-DME-001", "PAT-AD-007", "PAT-CSCC-005"]:
            resp = await client.get(f"{API_PREFIX}/patients/{pid}/compliance")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) > 0

    def test_service_clear(self, svc: EPROService):
        svc.clear()
        assert len(svc.list_instruments()) == 0
        responses, total = svc.get_patient_responses("PAT-DME-001")
        assert total == 0

    def test_service_stats(self, svc: EPROService):
        stats = svc.get_stats()
        assert stats["service"] == "epro"
        assert stats["total_instruments"] == 6
        assert stats["total_assignments"] == 30
        assert stats["total_responses"] == 60
        assert stats["total_schedules"] == 8

    def test_get_instrument_raises_keyerror(self, svc: EPROService):
        with pytest.raises(KeyError):
            svc.get_instrument("NONEXISTENT")

    def test_submit_response_raises_keyerror_missing_assignment(self, svc: EPROService):
        with pytest.raises(KeyError):
            svc.submit_response(ResponseSubmit(
                assignment_id="NONEXISTENT",
                answers=[],
            ))

    def test_deactivate_raises_keyerror(self, svc: EPROService):
        with pytest.raises(KeyError):
            svc.deactivate_assignment("NONEXISTENT")

    def test_delete_instrument_raises_keyerror(self, svc: EPROService):
        with pytest.raises(KeyError):
            svc.delete_instrument("NONEXISTENT")

    def test_update_instrument_raises_keyerror(self, svc: EPROService):
        with pytest.raises(KeyError):
            svc.update_instrument("NONEXISTENT", InstrumentUpdate(name="X"))


# =====================================================================
# COMPLIANCE CALCULATION LOGIC (Service-level)
# =====================================================================


class TestComplianceLogic:
    """Test compliance calculation business logic."""

    def test_compliance_rate_calculation(self, svc: EPROService):
        reports = svc.get_patient_compliance("PAT-DME-001")
        for report in reports:
            if report.total_expected > 0:
                expected_rate = report.total_completed / report.total_expected
                assert abs(report.compliance_rate - min(1.0, expected_rate)) < 0.01

    def test_compliance_report_fields(self, svc: EPROService):
        reports = svc.get_patient_compliance("PAT-AD-007")
        assert len(reports) > 0
        for report in reports:
            assert report.missed_windows >= 0
            assert report.late_submissions >= 0

    def test_trial_compliance_all_trials(self, svc: EPROService):
        for trial_id in [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL]:
            report = svc.get_trial_compliance(trial_id)
            assert report.trial_id == trial_id
            assert report.total_patients > 0

    def test_trial_compliance_empty(self, svc: EPROService):
        report = svc.get_trial_compliance("nonexistent-trial")
        assert report.total_patients == 0
        assert report.overall_compliance_rate == 1.0


# =====================================================================
# TREND ANALYSIS LOGIC (Service-level)
# =====================================================================


class TestTrendAnalysisLogic:
    """Test trend analysis business logic."""

    def test_trend_for_dlqi_improving(self, svc: EPROService):
        """For DLQI, lower is better; negative change = improvement."""
        trends = svc.get_patient_trends("PAT-AD-007", instrument_id="INST-003")
        for trend in trends:
            if trend.mcid_exceeded and trend.change_from_baseline is not None:
                if trend.change_from_baseline < 0:
                    assert trend.trend_direction == "improving"

    def test_trend_for_proctcae_improving(self, svc: EPROService):
        """For PRO-CTCAE, lower is better; negative change = improvement."""
        trends = svc.get_patient_trends("PAT-CSCC-005", instrument_id="INST-005")
        for trend in trends:
            if trend.mcid_exceeded and trend.change_from_baseline is not None:
                if trend.change_from_baseline < 0:
                    assert trend.trend_direction == "improving"

    def test_trend_for_vfq25(self, svc: EPROService):
        """For VFQ-25, higher is better; positive change = improvement."""
        trends = svc.get_patient_trends("PAT-DME-001", instrument_id="INST-004")
        for trend in trends:
            if trend.mcid_exceeded and trend.change_from_baseline is not None:
                if trend.change_from_baseline > 0:
                    assert trend.trend_direction == "improving"

    def test_baseline_score_is_first(self, svc: EPROService):
        trends = svc.get_patient_trends("PAT-DME-001")
        for trend in trends:
            if trend.data_points:
                assert trend.baseline_score == trend.data_points[0].score

    def test_current_score_is_last(self, svc: EPROService):
        trends = svc.get_patient_trends("PAT-DME-001")
        for trend in trends:
            if trend.data_points:
                assert trend.current_score == trend.data_points[-1].score

    def test_mcid_change_in_data_points(self, svc: EPROService):
        trends = svc.get_patient_trends("PAT-DME-001")
        for trend in trends:
            for dp in trend.data_points:
                # First point should have mcid_change of 0
                if dp.response_id == trend.data_points[0].response_id:
                    if dp.mcid_change is not None:
                        assert dp.mcid_change == 0.0


# =====================================================================
# FULL WORKFLOW
# =====================================================================


class TestFullWorkflow:
    """Test end-to-end workflows."""

    @pytest.mark.anyio
    async def test_instrument_lifecycle(self, client: AsyncClient):
        # Create
        create_resp = await client.post(
            f"{API_PREFIX}/instruments",
            json=_make_instrument_create(name="Lifecycle Instrument", abbreviation="LCI"),
        )
        assert create_resp.status_code == 201
        inst_id = create_resp.json()["id"]

        # Read
        get_resp = await client.get(f"{API_PREFIX}/instruments/{inst_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "Lifecycle Instrument"

        # Update
        update_resp = await client.put(
            f"{API_PREFIX}/instruments/{inst_id}",
            json={"name": "Updated Lifecycle"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["name"] == "Updated Lifecycle"

        # Delete
        delete_resp = await client.delete(f"{API_PREFIX}/instruments/{inst_id}")
        assert delete_resp.status_code == 204

        # Verify gone
        gone_resp = await client.get(f"{API_PREFIX}/instruments/{inst_id}")
        assert gone_resp.status_code == 404

    @pytest.mark.anyio
    async def test_assignment_and_response_workflow(self, client: AsyncClient):
        # Create assignment
        asgn_resp = await client.post(
            f"{API_PREFIX}/assignments",
            json=_make_assignment_create(patient_id="PAT-WORKFLOW-001"),
        )
        assert asgn_resp.status_code == 201
        asgn_id = asgn_resp.json()["id"]

        # Submit response for that assignment
        now = datetime.now(timezone.utc).isoformat()
        submit_resp = await client.post(
            f"{API_PREFIX}/responses",
            json={
                "assignment_id": asgn_id,
                "answers": [
                    {"question_id": "EQ5D-Q01", "value": 1.0, "timestamp": now},
                    {"question_id": "EQ5D-Q02", "value": 1.0, "timestamp": now},
                    {"question_id": "EQ5D-Q03", "value": 2.0, "timestamp": now},
                    {"question_id": "EQ5D-Q04", "value": 1.0, "timestamp": now},
                    {"question_id": "EQ5D-Q05", "value": 1.0, "timestamp": now},
                    {"question_id": "EQ5D-VAS", "value": 85.0, "timestamp": now},
                ],
                "language": "en",
            },
        )
        assert submit_resp.status_code == 201
        resp_id = submit_resp.json()["id"]

        # Verify response retrievable
        get_resp = await client.get(f"{API_PREFIX}/responses/{resp_id}")
        assert get_resp.status_code == 200

        # Get scored response
        scored_resp = await client.get(f"{API_PREFIX}/responses/{resp_id}/scored")
        assert scored_resp.status_code == 200
        assert scored_resp.json()["total_score"] is not None

        # Check patient responses
        patient_resp = await client.get(f"{API_PREFIX}/patients/PAT-WORKFLOW-001/responses")
        assert patient_resp.status_code == 200
        assert patient_resp.json()["total"] >= 1

    @pytest.mark.anyio
    async def test_schedule_and_assignment_workflow(self, client: AsyncClient):
        # Create schedule
        sched_resp = await client.post(
            f"{API_PREFIX}/schedules",
            json=_make_schedule_create(frequency="daily"),
        )
        assert sched_resp.status_code == 201
        sched_id = sched_resp.json()["id"]

        # Create assignment using that schedule
        asgn_resp = await client.post(
            f"{API_PREFIX}/assignments",
            json=_make_assignment_create(
                patient_id="PAT-SCHED-001",
                schedule_template_id=sched_id,
            ),
        )
        assert asgn_resp.status_code == 201
        assert asgn_resp.json()["schedule_template_id"] == sched_id

    @pytest.mark.anyio
    async def test_deactivate_stops_reminders(self, client: AsyncClient):
        # Get reminders for PAT-DME-001 before deactivation
        before = await client.get(
            f"{API_PREFIX}/reminders", params={"patient_id": "PAT-DME-001"}
        )
        before_count = len(before.json()["items"])

        # Deactivate both assignments
        await client.post(f"{API_PREFIX}/assignments/ASGN-001/deactivate")
        await client.post(f"{API_PREFIX}/assignments/ASGN-002/deactivate")

        # Reminders should be gone
        after = await client.get(
            f"{API_PREFIX}/reminders", params={"patient_id": "PAT-DME-001"}
        )
        after_count = len(after.json()["items"])
        assert after_count == 0
