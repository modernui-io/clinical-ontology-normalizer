"""Tests for Electronic Data Capture (EDC) Form Management (CLINICAL-24).

Covers:
- Seed data verification (templates, instances, queries, edit checks)
- CRF template CRUD (create, read, update, delete, list, filter by trial/name/status)
- CRF instance CRUD (create, read, update, delete, list, filter)
- CRF instance lifecycle (blank -> in_progress -> completed -> signed -> locked -> frozen)
- Data entry and auto-status transitions
- Data query CRUD (create, read, list, filter by instance/status/auto-generated)
- Data query lifecycle (open -> answered -> closed, open -> cancelled)
- Edit check CRUD (create, read, update, delete, list, filter by template/type/active)
- Edit check execution against CRF instances
- EDC metrics computation
- Error handling (404s, 400s, invalid operations)
- Edge cases (locked/frozen forms, duplicate operations, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.edc_forms import (
    CRFFieldCreate,
    CRFInstanceCreate,
    CRFInstanceSign,
    CRFInstanceUpdate,
    CRFTemplateCreate,
    CRFTemplateUpdate,
    DataQueryClose,
    DataQueryCreate,
    DataQueryRespond,
    EditCheckCreate,
    EditCheckSeverity,
    EditCheckType,
    EditCheckUpdate,
    FieldType,
    FormStatus,
    QueryStatus,
)
from app.services.edc_forms_service import (
    EDCService,
    get_edc_service,
    reset_edc_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/edc"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_edc_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> EDCService:
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


def _make_template_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "form_name": "Test Form",
        "version": "1.0",
        "visit_applicability": ["Screening", "Baseline"],
    }
    defaults.update(overrides)
    return defaults


def _make_instance_create(**overrides) -> dict:
    defaults = {
        "template_id": "CRF-TPL-001",
        "patient_id": "PAT-0001",
        "visit_number": 1,
        "site_id": "SITE-101",
    }
    defaults.update(overrides)
    return defaults


def _make_query_create(**overrides) -> dict:
    defaults = {
        "instance_id": "CRF-0001",
        "field_name": "systolic_bp",
        "query_text": "Value seems high. Please verify.",
        "raised_by": "DM-TestUser",
        "auto_generated": False,
    }
    defaults.update(overrides)
    return defaults


def _make_edit_check_create(**overrides) -> dict:
    defaults = {
        "template_id": "CRF-TPL-002",
        "check_type": "range_check",
        "description": "Test range check",
        "expression": "test_field >= 0 AND test_field <= 100",
        "error_message": "Test field out of range",
        "severity": "error",
    }
    defaults.update(overrides)
    return defaults


def _find_instance_by_status(svc: EDCService, status: FormStatus) -> str | None:
    """Find an instance with the given status."""
    instances = svc.list_instances(status=status)
    return instances[0].id if instances else None


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_templates_count(self, svc: EDCService):
        templates = svc.list_templates()
        assert len(templates) == 8

    def test_seed_templates_form_names(self, svc: EDCService):
        templates = svc.list_templates()
        names = {t.form_name for t in templates}
        assert "Demographics" in names
        assert "Vital Signs" in names
        assert "Adverse Events" in names
        assert "Concomitant Medications" in names
        assert "Medical History" in names
        assert "Lab Results" in names
        assert "Efficacy Assessment" in names
        assert "Study Drug Administration" in names

    def test_seed_templates_have_fields(self, svc: EDCService):
        for tpl in svc.list_templates():
            assert len(tpl.fields) > 0, f"Template {tpl.id} has no fields"

    def test_seed_templates_trials(self, svc: EDCService):
        templates = svc.list_templates()
        trials = {t.trial_id for t in templates}
        assert EYLEA_TRIAL in trials
        assert DUPIXENT_TRIAL in trials
        assert LIBTAYO_TRIAL in trials

    def test_seed_instances_count(self, svc: EDCService):
        instances = svc.list_instances()
        assert len(instances) == 100

    def test_seed_instances_statuses(self, svc: EDCService):
        instances = svc.list_instances()
        statuses = {i.status for i in instances}
        # Should have multiple statuses represented
        assert len(statuses) >= 3

    def test_seed_queries_count(self, svc: EDCService):
        queries = svc.list_queries()
        assert len(queries) == 30

    def test_seed_queries_statuses(self, svc: EDCService):
        queries = svc.list_queries()
        statuses = {q.status for q in queries}
        assert len(statuses) >= 2

    def test_seed_edit_checks_count(self, svc: EDCService):
        checks = svc.list_edit_checks()
        assert len(checks) == 25

    def test_seed_edit_checks_types(self, svc: EDCService):
        checks = svc.list_edit_checks()
        types = {ec.check_type for ec in checks}
        assert EditCheckType.RANGE_CHECK in types
        assert EditCheckType.CONSISTENCY_CHECK in types
        assert EditCheckType.REQUIRED_FIELD in types

    def test_seed_demographics_template_fields(self, svc: EDCService):
        tpl = svc.get_template("CRF-TPL-001")
        assert tpl is not None
        assert tpl.form_name == "Demographics"
        field_names = {f.field_name for f in tpl.fields}
        assert "subject_initials" in field_names
        assert "birth_date" in field_names
        assert "sex" in field_names

    def test_seed_vitals_template_sdtm(self, svc: EDCService):
        tpl = svc.get_template("CRF-TPL-002")
        assert tpl is not None
        for field in tpl.fields:
            assert field.sdtm_domain is not None


# =====================================================================
# TEMPLATE CRUD
# =====================================================================


class TestTemplateCRUD:
    """Test CRF template create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_templates(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8
        assert len(data["items"]) == 8

    @pytest.mark.anyio
    async def test_list_templates_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/templates", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_templates_filter_form_name(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/templates", params={"form_name": "vital"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert "vital" in item["form_name"].lower()

    @pytest.mark.anyio
    async def test_list_templates_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/templates", params={"status": "active"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8

    @pytest.mark.anyio
    async def test_get_template(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/templates/CRF-TPL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CRF-TPL-001"
        assert data["form_name"] == "Demographics"
        assert len(data["fields"]) > 0

    @pytest.mark.anyio
    async def test_get_template_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/templates/CRF-TPL-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_template(self, client: AsyncClient):
        payload = _make_template_create()
        resp = await client.post(f"{API_PREFIX}/templates", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["form_name"] == "Test Form"
        assert data["id"].startswith("CRF-TPL-")
        assert data["status"] == "active"

    @pytest.mark.anyio
    async def test_create_template_with_fields(self, client: AsyncClient):
        payload = _make_template_create(
            form_name="Custom Form",
            fields=[
                {
                    "field_name": "test_field",
                    "label": "Test Field",
                    "field_type": "text",
                    "required": True,
                },
            ],
        )
        resp = await client.post(f"{API_PREFIX}/templates", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["fields"]) == 1
        assert data["fields"][0]["field_name"] == "test_field"

    @pytest.mark.anyio
    async def test_update_template(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/templates/CRF-TPL-001",
            json={"form_name": "Updated Demographics", "version": "3.0"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["form_name"] == "Updated Demographics"
        assert data["version"] == "3.0"

    @pytest.mark.anyio
    async def test_update_template_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/templates/CRF-TPL-NONEXISTENT",
            json={"form_name": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_template(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/templates/CRF-TPL-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/templates/CRF-TPL-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_template_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/templates/CRF-TPL-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# INSTANCE CRUD
# =====================================================================


class TestInstanceCRUD:
    """Test CRF instance create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_instances(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/instances")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 100

    @pytest.mark.anyio
    async def test_list_instances_filter_template(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/instances", params={"template_id": "CRF-TPL-001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["template_id"] == "CRF-TPL-001"

    @pytest.mark.anyio
    async def test_list_instances_filter_patient(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/instances", params={"patient_id": "PAT-0001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["patient_id"] == "PAT-0001"

    @pytest.mark.anyio
    async def test_list_instances_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/instances", params={"site_id": "SITE-101"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_instances_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/instances", params={"status": "completed"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_list_instances_filter_visit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/instances", params={"visit_number": 1})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["visit_number"] == 1

    @pytest.mark.anyio
    async def test_get_instance(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/instances/CRF-0001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CRF-0001"

    @pytest.mark.anyio
    async def test_get_instance_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/instances/CRF-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_instance(self, client: AsyncClient):
        payload = _make_instance_create()
        resp = await client.post(f"{API_PREFIX}/instances", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["template_id"] == "CRF-TPL-001"
        assert data["patient_id"] == "PAT-0001"
        assert data["status"] == "blank"
        assert data["data"] == {}

    @pytest.mark.anyio
    async def test_create_instance_invalid_template(self, client: AsyncClient):
        payload = _make_instance_create(template_id="CRF-TPL-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/instances", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_delete_instance(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/instances/CRF-0001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/instances/CRF-0001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_instance_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/instances/CRF-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# INSTANCE LIFECYCLE
# =====================================================================


class TestInstanceLifecycle:
    """Test CRF instance lifecycle: blank -> in_progress -> completed -> signed -> locked -> frozen."""

    @pytest.mark.anyio
    async def test_blank_to_in_progress_on_data_entry(self, client: AsyncClient):
        """Entering data on a blank form should auto-transition to in_progress."""
        # Create a blank instance
        payload = _make_instance_create()
        resp = await client.post(f"{API_PREFIX}/instances", json=payload)
        assert resp.status_code == 201
        inst_id = resp.json()["id"]
        assert resp.json()["status"] == "blank"

        # Enter data
        resp2 = await client.put(
            f"{API_PREFIX}/instances/{inst_id}",
            json={"data": {"subject_initials": "JD"}},
        )
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "in_progress"
        assert resp2.json()["started_date"] is not None

    @pytest.mark.anyio
    async def test_complete_instance(self, client: AsyncClient):
        """Manually set status to completed."""
        payload = _make_instance_create()
        resp = await client.post(f"{API_PREFIX}/instances", json=payload)
        inst_id = resp.json()["id"]

        # Add data and mark completed
        resp2 = await client.put(
            f"{API_PREFIX}/instances/{inst_id}",
            json={"data": {"subject_initials": "JD"}, "status": "completed"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "completed"
        assert resp2.json()["completed_date"] is not None

    @pytest.mark.anyio
    async def test_sign_completed_instance(self, client: AsyncClient):
        """Sign a completed instance."""
        payload = _make_instance_create()
        resp = await client.post(f"{API_PREFIX}/instances", json=payload)
        inst_id = resp.json()["id"]

        # Complete the form
        await client.put(
            f"{API_PREFIX}/instances/{inst_id}",
            json={"data": {"subject_initials": "JD"}, "status": "completed"},
        )

        # Sign
        resp3 = await client.post(
            f"{API_PREFIX}/instances/{inst_id}/sign",
            json={"signed_by": "Dr. Test"},
        )
        assert resp3.status_code == 200
        data = resp3.json()
        assert data["status"] == "signed"
        assert data["signed_by"] == "Dr. Test"
        assert data["signed_date"] is not None

    @pytest.mark.anyio
    async def test_lock_signed_instance(self, client: AsyncClient):
        """Lock a signed instance."""
        payload = _make_instance_create()
        resp = await client.post(f"{API_PREFIX}/instances", json=payload)
        inst_id = resp.json()["id"]

        await client.put(
            f"{API_PREFIX}/instances/{inst_id}",
            json={"data": {"subject_initials": "JD"}, "status": "completed"},
        )
        await client.post(
            f"{API_PREFIX}/instances/{inst_id}/sign",
            json={"signed_by": "Dr. Test"},
        )

        resp4 = await client.post(f"{API_PREFIX}/instances/{inst_id}/lock")
        assert resp4.status_code == 200
        data = resp4.json()
        assert data["status"] == "locked"
        assert data["locked_date"] is not None

    @pytest.mark.anyio
    async def test_freeze_locked_instance(self, client: AsyncClient):
        """Freeze a locked instance."""
        payload = _make_instance_create()
        resp = await client.post(f"{API_PREFIX}/instances", json=payload)
        inst_id = resp.json()["id"]

        await client.put(
            f"{API_PREFIX}/instances/{inst_id}",
            json={"data": {"subject_initials": "JD"}, "status": "completed"},
        )
        await client.post(
            f"{API_PREFIX}/instances/{inst_id}/sign",
            json={"signed_by": "Dr. Test"},
        )
        await client.post(f"{API_PREFIX}/instances/{inst_id}/lock")

        resp5 = await client.post(f"{API_PREFIX}/instances/{inst_id}/freeze")
        assert resp5.status_code == 200
        assert resp5.json()["status"] == "frozen"

    @pytest.mark.anyio
    async def test_cannot_update_locked_instance(self, client: AsyncClient):
        """Cannot update data on a locked form."""
        # Find a locked instance
        svc = get_edc_service()
        locked_id = _find_instance_by_status(svc, FormStatus.LOCKED)
        if locked_id is None:
            pytest.skip("No locked instances in seed data")

        resp = await client.put(
            f"{API_PREFIX}/instances/{locked_id}",
            json={"data": {"test": "value"}},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_cannot_update_frozen_instance(self, client: AsyncClient):
        """Cannot update data on a frozen form."""
        svc = get_edc_service()
        frozen_id = _find_instance_by_status(svc, FormStatus.FROZEN)
        if frozen_id is None:
            pytest.skip("No frozen instances in seed data")

        resp = await client.put(
            f"{API_PREFIX}/instances/{frozen_id}",
            json={"data": {"test": "value"}},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_cannot_sign_blank_instance(self, client: AsyncClient):
        """Cannot sign a blank form."""
        payload = _make_instance_create()
        resp = await client.post(f"{API_PREFIX}/instances", json=payload)
        inst_id = resp.json()["id"]

        resp2 = await client.post(
            f"{API_PREFIX}/instances/{inst_id}/sign",
            json={"signed_by": "Dr. Test"},
        )
        assert resp2.status_code == 400

    @pytest.mark.anyio
    async def test_cannot_lock_unsigned_instance(self, client: AsyncClient):
        """Cannot lock a form that hasn't been signed."""
        payload = _make_instance_create()
        resp = await client.post(f"{API_PREFIX}/instances", json=payload)
        inst_id = resp.json()["id"]

        await client.put(
            f"{API_PREFIX}/instances/{inst_id}",
            json={"data": {"subject_initials": "JD"}, "status": "completed"},
        )

        resp3 = await client.post(f"{API_PREFIX}/instances/{inst_id}/lock")
        assert resp3.status_code == 400

    @pytest.mark.anyio
    async def test_cannot_freeze_unlocked_instance(self, client: AsyncClient):
        """Cannot freeze a form that hasn't been locked."""
        payload = _make_instance_create()
        resp = await client.post(f"{API_PREFIX}/instances", json=payload)
        inst_id = resp.json()["id"]

        await client.put(
            f"{API_PREFIX}/instances/{inst_id}",
            json={"data": {"subject_initials": "JD"}, "status": "completed"},
        )
        await client.post(
            f"{API_PREFIX}/instances/{inst_id}/sign",
            json={"signed_by": "Dr. Test"},
        )

        resp4 = await client.post(f"{API_PREFIX}/instances/{inst_id}/freeze")
        assert resp4.status_code == 400

    def test_sign_instance_service_level(self, svc: EDCService):
        """Test signing at service level."""
        inst = svc.create_instance(CRFInstanceCreate(
            template_id="CRF-TPL-001",
            patient_id="PAT-TEST",
            visit_number=1,
            site_id="SITE-101",
        ))
        svc.update_instance(inst.id, CRFInstanceUpdate(
            data={"subject_initials": "TT"},
            status=FormStatus.COMPLETED,
        ))
        signed = svc.sign_instance(inst.id, CRFInstanceSign(signed_by="Dr. Service"))
        assert signed is not None
        assert signed.status == FormStatus.SIGNED

    @pytest.mark.anyio
    async def test_sign_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/instances/CRF-NONEXISTENT/sign",
            json={"signed_by": "Dr. Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_lock_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/instances/CRF-NONEXISTENT/lock")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_freeze_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/instances/CRF-NONEXISTENT/freeze")
        assert resp.status_code == 404


# =====================================================================
# DATA QUERIES
# =====================================================================


class TestDataQueries:
    """Test data query operations."""

    @pytest.mark.anyio
    async def test_list_queries(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 30

    @pytest.mark.anyio
    async def test_list_queries_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries", params={"status": "open"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "open"

    @pytest.mark.anyio
    async def test_list_queries_filter_auto_generated(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries", params={"auto_generated": True})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["auto_generated"] is True

    @pytest.mark.anyio
    async def test_list_queries_filter_instance(self, client: AsyncClient):
        # Get first query to know its instance_id
        svc = get_edc_service()
        queries = svc.list_queries()
        if not queries:
            pytest.skip("No queries in seed data")
        target_instance = queries[0].instance_id

        resp = await client.get(
            f"{API_PREFIX}/queries", params={"instance_id": target_instance}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["instance_id"] == target_instance

    @pytest.mark.anyio
    async def test_get_query(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries/QRY-0001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "QRY-0001"

    @pytest.mark.anyio
    async def test_get_query_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries/QRY-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_query(self, client: AsyncClient):
        # Find a valid instance
        svc = get_edc_service()
        instances = svc.list_instances()
        inst_id = instances[0].id

        payload = _make_query_create(instance_id=inst_id)
        resp = await client.post(f"{API_PREFIX}/queries", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "open"
        assert data["id"].startswith("QRY-")

    @pytest.mark.anyio
    async def test_create_query_invalid_instance(self, client: AsyncClient):
        payload = _make_query_create(instance_id="CRF-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/queries", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_respond_to_query(self, client: AsyncClient):
        # Find an open query
        svc = get_edc_service()
        open_queries = svc.list_queries(status=QueryStatus.OPEN)
        if not open_queries:
            pytest.skip("No open queries in seed data")
        q_id = open_queries[0].id

        resp = await client.post(
            f"{API_PREFIX}/queries/{q_id}/respond",
            json={"response": "Verified. Value correct.", "responded_by": "Site-Coord"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "answered"
        assert data["response"] == "Verified. Value correct."
        assert data["responded_by"] == "Site-Coord"
        assert data["responded_date"] is not None

    @pytest.mark.anyio
    async def test_respond_to_non_open_query(self, client: AsyncClient):
        svc = get_edc_service()
        closed_queries = svc.list_queries(status=QueryStatus.CLOSED)
        if not closed_queries:
            pytest.skip("No closed queries in seed data")
        q_id = closed_queries[0].id

        resp = await client.post(
            f"{API_PREFIX}/queries/{q_id}/respond",
            json={"response": "Test", "responded_by": "Test"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_respond_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/queries/QRY-NONEXISTENT/respond",
            json={"response": "Test", "responded_by": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_close_query(self, client: AsyncClient):
        svc = get_edc_service()
        answered_queries = svc.list_queries(status=QueryStatus.ANSWERED)
        if not answered_queries:
            pytest.skip("No answered queries in seed data")
        q_id = answered_queries[0].id

        resp = await client.post(
            f"{API_PREFIX}/queries/{q_id}/close",
            json={"closed_by": "DM-Closer"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "closed"

    @pytest.mark.anyio
    async def test_close_query_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/queries/QRY-NONEXISTENT/close",
            json={"closed_by": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_cancel_query(self, client: AsyncClient):
        svc = get_edc_service()
        open_queries = svc.list_queries(status=QueryStatus.OPEN)
        if not open_queries:
            pytest.skip("No open queries in seed data")
        q_id = open_queries[0].id

        resp = await client.post(f"{API_PREFIX}/queries/{q_id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    @pytest.mark.anyio
    async def test_cancel_closed_query(self, client: AsyncClient):
        svc = get_edc_service()
        closed_queries = svc.list_queries(status=QueryStatus.CLOSED)
        if not closed_queries:
            pytest.skip("No closed queries in seed data")
        q_id = closed_queries[0].id

        resp = await client.post(f"{API_PREFIX}/queries/{q_id}/cancel")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_cancel_query_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/queries/QRY-NONEXISTENT/cancel")
        assert resp.status_code == 404


# =====================================================================
# DATA QUERY LIFECYCLE
# =====================================================================


class TestDataQueryLifecycle:
    """Test data query lifecycle transitions."""

    def test_query_lifecycle_open_to_answered_to_closed(self, svc: EDCService):
        # Create a query
        instances = svc.list_instances()
        inst_id = instances[0].id
        query = svc.create_query(DataQueryCreate(
            instance_id=inst_id,
            field_name="test_field",
            query_text="Test query",
            raised_by="Tester",
        ))
        assert query.status == QueryStatus.OPEN

        # Respond
        responded = svc.respond_to_query(query.id, DataQueryRespond(
            response="Value verified",
            responded_by="Site",
        ))
        assert responded is not None
        assert responded.status == QueryStatus.ANSWERED

        # Close
        closed = svc.close_query(query.id, DataQueryClose(closed_by="DM"))
        assert closed is not None
        assert closed.status == QueryStatus.CLOSED

    def test_query_lifecycle_open_to_cancelled(self, svc: EDCService):
        instances = svc.list_instances()
        inst_id = instances[0].id
        query = svc.create_query(DataQueryCreate(
            instance_id=inst_id,
            field_name="test_field",
            query_text="Test cancel",
            raised_by="Tester",
        ))
        cancelled = svc.cancel_query(query.id)
        assert cancelled is not None
        assert cancelled.status == QueryStatus.CANCELLED

    def test_query_close_open_directly(self, svc: EDCService):
        """Can close an open query directly (without answering)."""
        instances = svc.list_instances()
        inst_id = instances[0].id
        query = svc.create_query(DataQueryCreate(
            instance_id=inst_id,
            field_name="test_field",
            query_text="Direct close",
            raised_by="Tester",
        ))
        closed = svc.close_query(query.id, DataQueryClose(closed_by="DM"))
        assert closed is not None
        assert closed.status == QueryStatus.CLOSED


# =====================================================================
# EDIT CHECKS
# =====================================================================


class TestEditChecks:
    """Test edit check CRUD operations."""

    @pytest.mark.anyio
    async def test_list_edit_checks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/edit-checks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 25

    @pytest.mark.anyio
    async def test_list_edit_checks_filter_template(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/edit-checks", params={"template_id": "CRF-TPL-002"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["template_id"] == "CRF-TPL-002"

    @pytest.mark.anyio
    async def test_list_edit_checks_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/edit-checks", params={"check_type": "range_check"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["check_type"] == "range_check"

    @pytest.mark.anyio
    async def test_list_edit_checks_filter_active(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/edit-checks", params={"active": True}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 25  # All seeded checks are active

    @pytest.mark.anyio
    async def test_get_edit_check(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/edit-checks/EC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "EC-001"
        assert data["check_type"] == "range_check"

    @pytest.mark.anyio
    async def test_get_edit_check_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/edit-checks/EC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_edit_check(self, client: AsyncClient):
        payload = _make_edit_check_create()
        resp = await client.post(f"{API_PREFIX}/edit-checks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["check_type"] == "range_check"
        assert data["id"].startswith("EC-")
        assert data["active"] is True

    @pytest.mark.anyio
    async def test_create_edit_check_invalid_template(self, client: AsyncClient):
        payload = _make_edit_check_create(template_id="CRF-TPL-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/edit-checks", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_edit_check(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/edit-checks/EC-001",
            json={"description": "Updated check", "severity": "warning"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == "Updated check"
        assert data["severity"] == "warning"

    @pytest.mark.anyio
    async def test_update_edit_check_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/edit-checks/EC-NONEXISTENT",
            json={"description": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_edit_check(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/edit-checks/EC-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/edit-checks/EC-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_edit_check_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/edit-checks/EC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_deactivate_edit_check(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/edit-checks/EC-001",
            json={"active": False},
        )
        assert resp.status_code == 200
        assert resp.json()["active"] is False

    @pytest.mark.anyio
    async def test_create_edit_check_all_types(self, client: AsyncClient):
        """Create edit checks of each type."""
        for check_type in ["range_check", "consistency_check", "required_field", "cross_form_check", "dynamic_edit"]:
            payload = _make_edit_check_create(
                check_type=check_type,
                description=f"Test {check_type}",
            )
            resp = await client.post(f"{API_PREFIX}/edit-checks", json=payload)
            assert resp.status_code == 201
            assert resp.json()["check_type"] == check_type


# =====================================================================
# EDIT CHECK EXECUTION
# =====================================================================


class TestEditCheckExecution:
    """Test running edit checks against CRF instances."""

    @pytest.mark.anyio
    async def test_run_edit_checks(self, client: AsyncClient):
        # Find an instance with data
        svc = get_edc_service()
        ip_instances = svc.list_instances(status=FormStatus.IN_PROGRESS)
        if not ip_instances:
            ip_instances = svc.list_instances(status=FormStatus.COMPLETED)
        if not ip_instances:
            pytest.skip("No instances with data")

        inst_id = ip_instances[0].id
        resp = await client.post(f"{API_PREFIX}/instances/{inst_id}/run-edit-checks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["instance_id"] == inst_id
        assert data["total_checks"] >= 0
        assert data["passed"] >= 0
        assert data["failed"] >= 0
        assert data["passed"] + data["failed"] == data["total_checks"]

    @pytest.mark.anyio
    async def test_run_edit_checks_invalid_instance(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/instances/CRF-NONEXISTENT/run-edit-checks")
        assert resp.status_code == 400

    def test_run_edit_checks_service_level(self, svc: EDCService):
        """Run edit checks at service level."""
        instances = svc.list_instances(status=FormStatus.COMPLETED)
        if not instances:
            pytest.skip("No completed instances")
        result = svc.run_edit_checks(instances[0].id)
        assert result.instance_id == instances[0].id
        assert result.total_checks >= 0

    def test_run_edit_checks_blank_instance(self, svc: EDCService):
        """Edit checks on blank instance should run but may flag required fields."""
        inst = svc.create_instance(CRFInstanceCreate(
            template_id="CRF-TPL-002",
            patient_id="PAT-TEST",
            visit_number=1,
            site_id="SITE-101",
        ))
        result = svc.run_edit_checks(inst.id)
        assert result.instance_id == inst.id
        # Should have checks for the vitals template
        assert result.total_checks >= 0


# =====================================================================
# METRICS
# =====================================================================


class TestEDCMetrics:
    """Test EDC metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_forms"] == 100
        assert data["total_queries"] == 30
        assert data["open_queries"] >= 0
        assert data["avg_query_resolution_days"] >= 0
        assert 0 <= data["completion_rate"] <= 100

    def test_metrics_forms_by_status(self, svc: EDCService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.forms_by_status.values())
        assert total_by_status == metrics.total_forms

    def test_metrics_open_queries_consistent(self, svc: EDCService):
        metrics = svc.get_metrics()
        open_queries = svc.list_queries(status=QueryStatus.OPEN)
        assert metrics.open_queries == len(open_queries)

    def test_metrics_completion_rate_range(self, svc: EDCService):
        metrics = svc.get_metrics()
        assert 0.0 <= metrics.completion_rate <= 100.0

    def test_metrics_avg_resolution_positive(self, svc: EDCService):
        metrics = svc.get_metrics()
        assert metrics.avg_query_resolution_days >= 0.0


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_edc_service()
        svc2 = get_edc_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_edc_service()
        svc2 = reset_edc_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_edc_service()
        svc.delete_template("CRF-TPL-001")
        assert svc.get_template("CRF-TPL-001") is None
        svc2 = reset_edc_service()
        assert svc2.get_template("CRF-TPL-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_templates_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/templates")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_instances_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/instances")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_queries_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_edit_checks_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/edit-checks")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_template_create_with_visit_applicability(self, client: AsyncClient):
        payload = _make_template_create(
            visit_applicability=["Screening", "Baseline", "Week 4", "Week 12"],
        )
        resp = await client.post(f"{API_PREFIX}/templates", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["visit_applicability"]) == 4

    @pytest.mark.anyio
    async def test_instance_data_update_merges(self, client: AsyncClient):
        """Updating data should merge with existing data."""
        payload = _make_instance_create()
        resp = await client.post(f"{API_PREFIX}/instances", json=payload)
        inst_id = resp.json()["id"]

        # First update
        await client.put(
            f"{API_PREFIX}/instances/{inst_id}",
            json={"data": {"field_a": "value_a"}},
        )

        # Second update
        resp3 = await client.put(
            f"{API_PREFIX}/instances/{inst_id}",
            json={"data": {"field_b": "value_b"}},
        )
        assert resp3.status_code == 200
        data = resp3.json()["data"]
        assert data["field_a"] == "value_a"
        assert data["field_b"] == "value_b"

    @pytest.mark.anyio
    async def test_update_instance_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/instances/CRF-NONEXISTENT",
            json={"data": {"test": "value"}},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_template_has_version(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/templates/CRF-TPL-001")
        data = resp.json()
        assert "version" in data
        assert data["version"] is not None

    @pytest.mark.anyio
    async def test_template_fields_have_sdtm_mapping(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/templates/CRF-TPL-002")
        data = resp.json()
        for field in data["fields"]:
            assert "sdtm_domain" in field
            assert "sdtm_variable" in field

    @pytest.mark.anyio
    async def test_template_fields_have_sas_variable(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/templates/CRF-TPL-001")
        data = resp.json()
        for field in data["fields"]:
            assert "sas_variable_name" in field

    @pytest.mark.anyio
    async def test_query_has_auto_generated_flag(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries/QRY-0001")
        data = resp.json()
        assert "auto_generated" in data
        assert isinstance(data["auto_generated"], bool)

    @pytest.mark.anyio
    async def test_edit_check_has_severity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/edit-checks/EC-001")
        data = resp.json()
        assert data["severity"] in ["warning", "error"]


# =====================================================================
# TEMPLATE FIELD DETAILS
# =====================================================================


class TestTemplateFieldDetails:
    """Test detailed field configuration in templates."""

    @pytest.mark.anyio
    async def test_demographics_field_types(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/templates/CRF-TPL-001")
        data = resp.json()
        field_types = {f["field_name"]: f["field_type"] for f in data["fields"]}
        assert field_types["subject_initials"] == "text"
        assert field_types["birth_date"] == "date"
        assert field_types["sex"] == "dropdown"
        assert field_types["race"] == "checkbox"
        assert field_types["ethnicity"] == "radio"

    @pytest.mark.anyio
    async def test_vitals_fields_have_validation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/templates/CRF-TPL-002")
        data = resp.json()
        bp_field = next(f for f in data["fields"] if f["field_name"] == "systolic_bp")
        assert bp_field["validation_rules"] is not None
        assert "min" in bp_field["validation_rules"]
        assert "max" in bp_field["validation_rules"]

    @pytest.mark.anyio
    async def test_dropdown_fields_have_options(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/templates/CRF-TPL-001")
        data = resp.json()
        sex_field = next(f for f in data["fields"] if f["field_name"] == "sex")
        assert sex_field["options"] is not None
        assert len(sex_field["options"]) > 0
        assert "Male" in sex_field["options"]

    @pytest.mark.anyio
    async def test_ae_template_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/templates/CRF-TPL-003")
        data = resp.json()
        field_names = {f["field_name"] for f in data["fields"]}
        assert "ae_term" in field_names
        assert "ae_severity" in field_names
        assert "ae_serious" in field_names
        assert "ae_relationship" in field_names

    @pytest.mark.anyio
    async def test_lab_results_have_lab_value_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/templates/CRF-TPL-006")
        data = resp.json()
        lab_fields = [f for f in data["fields"] if f["field_type"] == "lab_value"]
        assert len(lab_fields) >= 5


# =====================================================================
# FORM STATUS DISTRIBUTION
# =====================================================================


class TestFormStatusDistribution:
    """Test form status distribution in seed data."""

    def test_all_statuses_represented(self, svc: EDCService):
        instances = svc.list_instances()
        statuses = {i.status for i in instances}
        # At minimum, several statuses should be present
        assert len(statuses) >= 3

    def test_signed_instances_have_signer(self, svc: EDCService):
        signed = svc.list_instances(status=FormStatus.SIGNED)
        for inst in signed:
            assert inst.signed_by is not None
            assert inst.signed_date is not None

    def test_locked_instances_have_lock_date(self, svc: EDCService):
        locked = svc.list_instances(status=FormStatus.LOCKED)
        for inst in locked:
            assert inst.locked_date is not None

    def test_completed_instances_have_completion_date(self, svc: EDCService):
        completed = svc.list_instances(status=FormStatus.COMPLETED)
        for inst in completed:
            assert inst.completed_date is not None

    def test_blank_instances_have_no_data_dates(self, svc: EDCService):
        blank = svc.list_instances(status=FormStatus.BLANK)
        for inst in blank:
            assert inst.started_date is None


# =====================================================================
# EDIT CHECK TYPES
# =====================================================================


class TestEditCheckTypes:
    """Test edit check type distribution and properties."""

    def test_range_checks_count(self, svc: EDCService):
        checks = svc.list_edit_checks(check_type=EditCheckType.RANGE_CHECK)
        assert len(checks) >= 8

    def test_consistency_checks_count(self, svc: EDCService):
        checks = svc.list_edit_checks(check_type=EditCheckType.CONSISTENCY_CHECK)
        assert len(checks) >= 4

    def test_required_field_checks_count(self, svc: EDCService):
        checks = svc.list_edit_checks(check_type=EditCheckType.REQUIRED_FIELD)
        assert len(checks) >= 3

    def test_dynamic_edit_checks_exist(self, svc: EDCService):
        checks = svc.list_edit_checks(check_type=EditCheckType.DYNAMIC_EDIT)
        assert len(checks) >= 2

    def test_cross_form_checks_exist(self, svc: EDCService):
        checks = svc.list_edit_checks(check_type=EditCheckType.CROSS_FORM_CHECK)
        assert len(checks) >= 1

    def test_all_checks_have_expression(self, svc: EDCService):
        for ec in svc.list_edit_checks():
            assert ec.expression
            assert len(ec.expression) > 5

    def test_all_checks_have_error_message(self, svc: EDCService):
        for ec in svc.list_edit_checks():
            assert ec.error_message
            assert len(ec.error_message) > 5

    @pytest.mark.anyio
    async def test_all_edit_check_types_in_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/edit-checks")
        data = resp.json()
        types = {item["check_type"] for item in data["items"]}
        assert "range_check" in types
        assert "consistency_check" in types
        assert "required_field" in types


# =====================================================================
# MULTIPLE OPERATIONS
# =====================================================================


class TestMultipleOperations:
    """Test sequences of operations."""

    @pytest.mark.anyio
    async def test_create_template_then_instance(self, client: AsyncClient):
        """Create a template and then an instance for it."""
        tpl_resp = await client.post(
            f"{API_PREFIX}/templates",
            json=_make_template_create(form_name="New Custom Form"),
        )
        assert tpl_resp.status_code == 201
        tpl_id = tpl_resp.json()["id"]

        inst_resp = await client.post(
            f"{API_PREFIX}/instances",
            json=_make_instance_create(template_id=tpl_id),
        )
        assert inst_resp.status_code == 201
        assert inst_resp.json()["template_id"] == tpl_id

    @pytest.mark.anyio
    async def test_create_instance_enter_data_create_query(self, client: AsyncClient):
        """Full workflow: create instance, enter data, raise query."""
        # Create instance
        inst_resp = await client.post(
            f"{API_PREFIX}/instances",
            json=_make_instance_create(),
        )
        inst_id = inst_resp.json()["id"]

        # Enter data
        await client.put(
            f"{API_PREFIX}/instances/{inst_id}",
            json={"data": {"systolic_bp": 300}},
        )

        # Raise query
        q_resp = await client.post(
            f"{API_PREFIX}/queries",
            json=_make_query_create(
                instance_id=inst_id,
                field_name="systolic_bp",
                query_text="BP value of 300 seems extremely high",
            ),
        )
        assert q_resp.status_code == 201
        assert q_resp.json()["instance_id"] == inst_id

    @pytest.mark.anyio
    async def test_full_form_lifecycle(self, client: AsyncClient):
        """Full lifecycle: create -> data entry -> complete -> sign -> lock -> freeze."""
        # Create
        resp = await client.post(
            f"{API_PREFIX}/instances",
            json=_make_instance_create(),
        )
        inst_id = resp.json()["id"]
        assert resp.json()["status"] == "blank"

        # Data entry
        resp = await client.put(
            f"{API_PREFIX}/instances/{inst_id}",
            json={"data": {"subject_initials": "JD", "birth_date": "1980-01-01"}},
        )
        assert resp.json()["status"] == "in_progress"

        # Complete
        resp = await client.put(
            f"{API_PREFIX}/instances/{inst_id}",
            json={"status": "completed"},
        )
        assert resp.json()["status"] == "completed"

        # Sign
        resp = await client.post(
            f"{API_PREFIX}/instances/{inst_id}/sign",
            json={"signed_by": "Dr. Full Lifecycle"},
        )
        assert resp.json()["status"] == "signed"

        # Lock
        resp = await client.post(f"{API_PREFIX}/instances/{inst_id}/lock")
        assert resp.json()["status"] == "locked"

        # Freeze
        resp = await client.post(f"{API_PREFIX}/instances/{inst_id}/freeze")
        assert resp.json()["status"] == "frozen"

        # Verify cannot update frozen
        resp = await client.put(
            f"{API_PREFIX}/instances/{inst_id}",
            json={"data": {"test": "should fail"}},
        )
        assert resp.status_code == 400
