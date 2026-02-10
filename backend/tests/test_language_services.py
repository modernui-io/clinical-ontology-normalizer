"""Tests for Language & Translation Services.

Covers:
- Seed data verification (projects, tasks, validations, translators, glossary)
- Translation project CRUD (create, read, update, delete, list, filters)
- Translation task CRUD (create, read, update, delete, list, filters)
- Linguistic validation CRUD (create, read, update, delete, list, filters)
- Certified translator CRUD (create, read, update, delete, list, filters)
- Translation glossary CRUD (create, read, update, delete, list, filters)
- Workflow operations (assign translator, submit translation, certify translation)
- Project progress tracking
- Language metrics computation
- Error handling (404s, 400s)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.language_services import (
    CertificationLevel,
    DocumentCategory,
    TranslationStatus,
    TranslatorStatus,
    ValidationMethod,
)
from app.services.language_services_service import (
    LanguageServicesService,
    get_language_services_service,
    reset_language_services_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/language-services"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_language_services_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> LanguageServicesService:
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


def _make_project_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "project_name": "Test Translation Project",
        "source_language": "en",
        "target_languages": ["fr", "de"],
        "document_category": "protocol",
        "due_date": (now + timedelta(days=60)).isoformat(),
        "requestor": "Test Requestor",
        "priority": "normal",
    }
    defaults.update(overrides)
    return defaults


def _make_task_create(**overrides) -> dict:
    defaults = {
        "project_id": "TPRJ-001",
        "source_document": "test_document.docx",
        "source_language": "en",
        "target_language": "fr",
        "word_count": 10000,
    }
    defaults.update(overrides)
    return defaults


def _make_validation_create(**overrides) -> dict:
    defaults = {
        "task_id": "TTSK-001",
        "method": "forward_backward",
        "validator": "Dr. Test Validator",
        "cognitive_debriefing_participants": None,
        "issues_found": 2,
        "issues_resolved": 2,
        "conceptual_equivalence_score": 92.0,
        "cultural_appropriateness_score": 90.0,
        "readability_score": 88.0,
        "overall_pass": True,
        "notes": "Test validation notes.",
    }
    defaults.update(overrides)
    return defaults


def _make_translator_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "name": "Dr. Test Translator",
        "email": "test@translator.com",
        "languages": ["en", "fr"],
        "specializations": ["oncology"],
        "certification_level": "certified",
        "certifying_body": "Test Certifying Body",
        "certification_expiry": (now + timedelta(days=365)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_glossary_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "source_term": "Test Clinical Term",
        "source_language": "en",
        "translations": {"fr": "Terme clinique test", "de": "Klinischer Testbegriff"},
        "context": "Test context for glossary term.",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_projects_count(self, svc: LanguageServicesService):
        projects = svc.list_projects()
        assert len(projects) == 4

    def test_seed_tasks_count(self, svc: LanguageServicesService):
        tasks = svc.list_tasks()
        assert len(tasks) == 12

    def test_seed_validations_count(self, svc: LanguageServicesService):
        validations = svc.list_validations()
        assert len(validations) == 5

    def test_seed_translators_count(self, svc: LanguageServicesService):
        translators = svc.list_translators()
        assert len(translators) == 6

    def test_seed_glossary_count(self, svc: LanguageServicesService):
        glossary = svc.list_glossary()
        assert len(glossary) == 10

    def test_seed_projects_span_all_trials(self, svc: LanguageServicesService):
        projects = svc.list_projects()
        trial_ids = {p.trial_id for p in projects}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_multiple_statuses_present(self, svc: LanguageServicesService):
        projects = svc.list_projects()
        statuses = {p.status for p in projects}
        assert TranslationStatus.DELIVERED in statuses
        assert TranslationStatus.IN_PROGRESS in statuses
        assert TranslationStatus.REQUESTED in statuses

    def test_seed_translators_have_active_and_inactive(self, svc: LanguageServicesService):
        translators = svc.list_translators()
        statuses = {t.status for t in translators}
        assert TranslatorStatus.ACTIVE in statuses
        assert TranslatorStatus.INACTIVE in statuses

    def test_seed_validations_have_pass_and_fail(self, svc: LanguageServicesService):
        validations = svc.list_validations()
        passes = {v.overall_pass for v in validations}
        assert True in passes
        assert False in passes

    def test_seed_glossary_has_approved_and_unapproved(self, svc: LanguageServicesService):
        glossary = svc.list_glossary()
        approvals = {g.approved for g in glossary}
        assert True in approvals
        assert False in approvals


# =====================================================================
# TRANSLATION PROJECT CRUD
# =====================================================================


class TestProjectCrud:
    """Test translation project CRUD operations."""

    @pytest.mark.anyio
    async def test_list_projects(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        assert len(data["items"]) == 4

    @pytest.mark.anyio
    async def test_list_projects_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/projects", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_projects_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/projects", params={"status": "delivered"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "delivered"

    @pytest.mark.anyio
    async def test_list_projects_filter_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/projects", params={"document_category": "protocol"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["document_category"] == "protocol"

    @pytest.mark.anyio
    async def test_get_project(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/projects/TPRJ-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "TPRJ-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_project_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/projects/TPRJ-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_project(self, client: AsyncClient):
        payload = _make_project_create()
        resp = await client.post(f"{API_PREFIX}/projects", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["project_name"] == "Test Translation Project"
        assert data["id"].startswith("TPRJ-")
        assert data["status"] == "requested"

    @pytest.mark.anyio
    async def test_update_project(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/projects/TPRJ-001",
            json={"priority": "urgent", "project_name": "Updated Name"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["priority"] == "urgent"
        assert data["project_name"] == "Updated Name"

    @pytest.mark.anyio
    async def test_update_project_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/projects/TPRJ-NONEXISTENT",
            json={"priority": "low"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_project(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/projects/TPRJ-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/projects/TPRJ-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_project_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/projects/TPRJ-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# TRANSLATION TASK CRUD
# =====================================================================


class TestTaskCrud:
    """Test translation task CRUD operations."""

    @pytest.mark.anyio
    async def test_list_tasks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_tasks_filter_project(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks", params={"project_id": "TPRJ-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["project_id"] == "TPRJ-001"

    @pytest.mark.anyio
    async def test_list_tasks_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks", params={"status": "delivered"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "delivered"

    @pytest.mark.anyio
    async def test_list_tasks_filter_language(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks", params={"target_language": "ja"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["target_language"] == "ja"

    @pytest.mark.anyio
    async def test_list_tasks_filter_translator(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks", params={"translator_id": "TRN-001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["translator_id"] == "TRN-001"

    @pytest.mark.anyio
    async def test_get_task(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks/TTSK-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "TTSK-001"
        assert data["word_count"] == 45000

    @pytest.mark.anyio
    async def test_get_task_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks/TTSK-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_task(self, client: AsyncClient):
        payload = _make_task_create()
        resp = await client.post(f"{API_PREFIX}/tasks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("TTSK-")
        assert data["status"] == "requested"
        assert data["word_count"] == 10000

    @pytest.mark.anyio
    async def test_update_task(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/tasks/TTSK-010",
            json={"status": "in_progress", "translator_id": "TRN-004"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["translator_id"] == "TRN-004"

    @pytest.mark.anyio
    async def test_update_task_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/tasks/TTSK-NONEXISTENT",
            json={"status": "in_progress"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_task(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/tasks/TTSK-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/tasks/TTSK-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_task_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/tasks/TTSK-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# LINGUISTIC VALIDATION CRUD
# =====================================================================


class TestValidationCrud:
    """Test linguistic validation CRUD operations."""

    @pytest.mark.anyio
    async def test_list_validations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_list_validations_filter_task(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations", params={"task_id": "TTSK-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["task_id"] == "TTSK-001"

    @pytest.mark.anyio
    async def test_list_validations_filter_method(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations", params={"method": "forward_backward"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["method"] == "forward_backward"

    @pytest.mark.anyio
    async def test_get_validation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations/LVAL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "LVAL-001"
        assert data["overall_pass"] is True

    @pytest.mark.anyio
    async def test_get_validation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations/LVAL-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_validation(self, client: AsyncClient):
        payload = _make_validation_create()
        resp = await client.post(f"{API_PREFIX}/validations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("LVAL-")
        assert data["overall_pass"] is True
        assert data["conceptual_equivalence_score"] == 92.0

    @pytest.mark.anyio
    async def test_create_validation_invalid_task(self, client: AsyncClient):
        payload = _make_validation_create(task_id="TTSK-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/validations", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_validation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/validations/LVAL-005",
            json={"issues_resolved": 4, "overall_pass": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["issues_resolved"] == 4
        assert data["overall_pass"] is True

    @pytest.mark.anyio
    async def test_update_validation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/validations/LVAL-NONEXISTENT",
            json={"overall_pass": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_validation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/validations/LVAL-005")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/validations/LVAL-005")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_validation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/validations/LVAL-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# CERTIFIED TRANSLATOR CRUD
# =====================================================================


class TestTranslatorCrud:
    """Test certified translator CRUD operations."""

    @pytest.mark.anyio
    async def test_list_translators(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/translators")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6

    @pytest.mark.anyio
    async def test_list_translators_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/translators", params={"status": "active"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        for item in data["items"]:
            assert item["status"] == "active"

    @pytest.mark.anyio
    async def test_list_translators_filter_language(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/translators", params={"language": "ja"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert "ja" in item["languages"]

    @pytest.mark.anyio
    async def test_list_translators_filter_certification(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/translators", params={"certification_level": "certified"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["certification_level"] == "certified"

    @pytest.mark.anyio
    async def test_get_translator(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/translators/TRN-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "TRN-001"
        assert data["name"] == "Marie Dupont"

    @pytest.mark.anyio
    async def test_get_translator_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/translators/TRN-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_translator(self, client: AsyncClient):
        payload = _make_translator_create()
        resp = await client.post(f"{API_PREFIX}/translators", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("TRN-")
        assert data["name"] == "Dr. Test Translator"
        assert data["status"] == "pending_qualification"

    @pytest.mark.anyio
    async def test_update_translator(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/translators/TRN-006",
            json={"status": "active", "quality_rating": 4.5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"
        assert data["quality_rating"] == 4.5

    @pytest.mark.anyio
    async def test_update_translator_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/translators/TRN-NONEXISTENT",
            json={"status": "active"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_translator(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/translators/TRN-006")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/translators/TRN-006")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_translator_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/translators/TRN-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# TRANSLATION GLOSSARY CRUD
# =====================================================================


class TestGlossaryCrud:
    """Test translation glossary CRUD operations."""

    @pytest.mark.anyio
    async def test_list_glossary(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/glossary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_glossary_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/glossary", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_glossary_filter_approved(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/glossary", params={"approved": True})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["approved"] is True

    @pytest.mark.anyio
    async def test_list_glossary_filter_language(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/glossary", params={"source_language": "en"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["source_language"] == "en"

    @pytest.mark.anyio
    async def test_get_glossary_entry(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/glossary/GLOSS-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "GLOSS-001"
        assert data["source_term"] == "Best-Corrected Visual Acuity"

    @pytest.mark.anyio
    async def test_get_glossary_entry_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/glossary/GLOSS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_glossary_entry(self, client: AsyncClient):
        payload = _make_glossary_create()
        resp = await client.post(f"{API_PREFIX}/glossary", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("GLOSS-")
        assert data["source_term"] == "Test Clinical Term"
        assert data["approved"] is False

    @pytest.mark.anyio
    async def test_update_glossary_entry(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/glossary/GLOSS-006",
            json={"approved": True, "approved_by": "Dr. Reviewer"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["approved"] is True
        assert data["approved_by"] == "Dr. Reviewer"

    @pytest.mark.anyio
    async def test_update_glossary_entry_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/glossary/GLOSS-NONEXISTENT",
            json={"approved": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_glossary_entry(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/glossary/GLOSS-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/glossary/GLOSS-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_glossary_entry_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/glossary/GLOSS-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# WORKFLOW OPERATIONS
# =====================================================================


class TestWorkflowOperations:
    """Test translation workflow operations."""

    @pytest.mark.anyio
    async def test_assign_translator(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/tasks/TTSK-010/assign-translator",
            json={"translator_id": "TRN-004", "reviewer_id": "TRN-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["translator_id"] == "TRN-004"
        assert data["reviewer_id"] == "TRN-001"
        assert data["started_date"] is not None

    @pytest.mark.anyio
    async def test_assign_translator_task_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/tasks/TTSK-NONEXISTENT/assign-translator",
            json={"translator_id": "TRN-001"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_assign_translator_invalid_translator(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/tasks/TTSK-010/assign-translator",
            json={"translator_id": "TRN-INVALID"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_submit_translation(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/tasks/TTSK-008/submit-translation",
            json={
                "translated_text_reference": "Dupixent_PatientDiary_v1.0_ES.docx",
                "back_translation_reference": "Dupixent_PatientDiary_v1.0_ES_BT.docx",
                "reconciliation_notes": "All terms verified.",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "back_translated"
        assert data["translated_text_reference"] == "Dupixent_PatientDiary_v1.0_ES.docx"

    @pytest.mark.anyio
    async def test_submit_translation_without_back_translation(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/tasks/TTSK-009/submit-translation",
            json={"translated_text_reference": "Dupixent_PatientDiary_v1.0_PT.docx"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "translated"

    @pytest.mark.anyio
    async def test_submit_translation_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/tasks/TTSK-NONEXISTENT/submit-translation",
            json={"translated_text_reference": "test.docx"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_certify_translation(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/tasks/TTSK-005/certify",
            json={"certified_by": "Dr. Chief Reviewer", "certification_notes": "Approved for use."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "certified"
        assert data["completed_date"] is not None

    @pytest.mark.anyio
    async def test_certify_translation_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/tasks/TTSK-NONEXISTENT/certify",
            json={"certified_by": "Dr. Test"},
        )
        assert resp.status_code == 404


# =====================================================================
# PROJECT PROGRESS
# =====================================================================


class TestProjectProgress:
    """Test project progress tracking."""

    @pytest.mark.anyio
    async def test_get_project_progress(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/projects/TPRJ-001/progress")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == "TPRJ-001"
        assert data["total_tasks"] == 3
        assert data["tasks_completed"] == 3  # All delivered
        assert data["completion_percentage"] == 100.0
        assert data["total_word_count"] == 135000

    @pytest.mark.anyio
    async def test_get_project_progress_partial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/projects/TPRJ-003/progress")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == "TPRJ-003"
        assert data["total_tasks"] == 3
        assert data["tasks_completed"] == 0
        assert data["tasks_in_progress"] == 2
        assert data["tasks_pending"] == 1
        assert 0.0 <= data["completion_percentage"] <= 100.0

    @pytest.mark.anyio
    async def test_get_project_progress_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/projects/TPRJ-NONEXISTENT/progress")
        assert resp.status_code == 404

    def test_project_progress_validations(self, svc: LanguageServicesService):
        progress = svc.get_project_progress("TPRJ-001")
        assert progress is not None
        assert progress.validations_passed == 3  # LVAL-001, LVAL-002, LVAL-003
        assert progress.validations_failed == 0

    def test_project_progress_with_failed_validation(self, svc: LanguageServicesService):
        progress = svc.get_project_progress("TPRJ-002")
        assert progress is not None
        assert progress.validations_passed == 1  # LVAL-004
        assert progress.validations_failed == 1  # LVAL-005


# =====================================================================
# LANGUAGE METRICS
# =====================================================================


class TestLanguageMetrics:
    """Test language metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_projects"] == 4
        assert data["total_tasks"] == 12
        assert data["total_translators"] == 6
        assert data["active_translators"] == 5
        assert data["total_validations"] == 5
        assert data["validations_passed"] == 4
        assert data["validations_failed"] == 1
        assert data["total_glossary_entries"] == 10
        assert data["approved_glossary_entries"] == 8
        assert data["total_word_count"] > 0
        assert len(data["languages_supported"]) > 0
        assert 0.0 <= data["avg_translator_rating"] <= 5.0
        assert data["avg_conceptual_equivalence"] > 0
        assert data["avg_cultural_appropriateness"] > 0
        assert data["avg_readability"] > 0

    @pytest.mark.anyio
    async def test_get_metrics_by_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_projects"] == 2

    @pytest.mark.anyio
    async def test_get_metrics_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_projects"] == 0
        assert data["total_tasks"] == 0

    def test_metrics_projects_by_status(self, svc: LanguageServicesService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.projects_by_status.values())
        assert total_by_status == metrics.total_projects

    def test_metrics_tasks_by_status(self, svc: LanguageServicesService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.tasks_by_status.values())
        assert total_by_status == metrics.total_tasks


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_language_services_service()
        svc2 = get_language_services_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_language_services_service()
        svc2 = reset_language_services_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_language_services_service()
        svc.delete_project("TPRJ-001")
        assert svc.get_project("TPRJ-001") is None
        svc2 = reset_language_services_service()
        assert svc2.get_project("TPRJ-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_projects_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/projects")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_tasks_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_validations_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_translators_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/translators")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_glossary_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/glossary")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_project_all_categories(self, client: AsyncClient):
        for cat in ["protocol", "icf", "patient_diary", "questionnaire", "label", "packaging", "regulatory_submission", "training_material"]:
            payload = _make_project_create(document_category=cat, project_name=f"Test {cat}")
            resp = await client.post(f"{API_PREFIX}/projects", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["document_category"] == cat

    @pytest.mark.anyio
    async def test_create_validation_all_methods(self, client: AsyncClient):
        for method in ["forward_backward", "dual_forward", "cognitive_debriefing", "clinician_review", "harmonization"]:
            payload = _make_validation_create(method=method)
            resp = await client.post(f"{API_PREFIX}/validations", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["method"] == method

    @pytest.mark.anyio
    async def test_create_translator_all_certification_levels(self, client: AsyncClient):
        for level in ["standard", "certified", "sworn", "notarized"]:
            payload = _make_translator_create(certification_level=level, name=f"Translator {level}")
            resp = await client.post(f"{API_PREFIX}/translators", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["certification_level"] == level

    @pytest.mark.anyio
    async def test_project_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/projects/TPRJ-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "project_name" in data
        assert "source_language" in data
        assert "target_languages" in data
        assert "document_category" in data
        assert "status" in data
        assert "requested_date" in data
        assert "due_date" in data
        assert "requestor" in data
        assert "priority" in data

    @pytest.mark.anyio
    async def test_task_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tasks/TTSK-001")
        data = resp.json()
        assert "id" in data
        assert "project_id" in data
        assert "source_document" in data
        assert "source_language" in data
        assert "target_language" in data
        assert "status" in data
        assert "translator_id" in data
        assert "word_count" in data

    @pytest.mark.anyio
    async def test_validation_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations/LVAL-001")
        data = resp.json()
        assert "id" in data
        assert "task_id" in data
        assert "method" in data
        assert "validator" in data
        assert "conceptual_equivalence_score" in data
        assert "cultural_appropriateness_score" in data
        assert "readability_score" in data
        assert "overall_pass" in data

    @pytest.mark.anyio
    async def test_translator_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/translators/TRN-001")
        data = resp.json()
        assert "id" in data
        assert "name" in data
        assert "email" in data
        assert "languages" in data
        assert "specializations" in data
        assert "certification_level" in data
        assert "certifying_body" in data
        assert "status" in data
        assert "quality_rating" in data

    @pytest.mark.anyio
    async def test_glossary_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/glossary/GLOSS-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "source_term" in data
        assert "source_language" in data
        assert "translations" in data
        assert "context" in data
        assert "approved" in data

    @pytest.mark.anyio
    async def test_metrics_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "total_projects" in data
        assert "projects_by_status" in data
        assert "total_tasks" in data
        assert "tasks_by_status" in data
        assert "total_translators" in data
        assert "active_translators" in data
        assert "total_validations" in data
        assert "validations_passed" in data
        assert "validations_failed" in data
        assert "avg_conceptual_equivalence" in data
        assert "avg_cultural_appropriateness" in data
        assert "avg_readability" in data
        assert "total_glossary_entries" in data
        assert "approved_glossary_entries" in data
        assert "total_word_count" in data
        assert "languages_supported" in data
        assert "avg_translator_rating" in data

    def test_delivered_tasks_have_completed_date(self, svc: LanguageServicesService):
        tasks = svc.list_tasks(status=TranslationStatus.DELIVERED)
        for t in tasks:
            assert t.completed_date is not None

    def test_requested_tasks_have_no_translator(self, svc: LanguageServicesService):
        tasks = svc.list_tasks(status=TranslationStatus.REQUESTED)
        for t in tasks:
            assert t.translator_id is None
