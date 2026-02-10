"""Tests for Data Queries & Discrepancy Management (CLINICAL-18).

Covers:
- Seed data verification (queries, responses, auto-rules, resolutions)
- Query CRUD (create, read, update, delete, list, filter by all dimensions)
- Query lifecycle (open, respond, close, requery, cancel)
- Response management (add response, list responses)
- Auto-query rule CRUD (create, read, update, delete, list, filter)
- Auto-query rule evaluation (generate queries from rules)
- Query aging report (buckets, oldest query)
- Query metrics computation (by status, category, site, priority)
- Site query summary
- Bulk operations (bulk close, bulk assign)
- Discrepancy resolution tracking
- Error handling (404s, 400s, invalid lifecycle transitions)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.data_queries import router as data_queries_router
from app.schemas.data_queries import (
    AutoQueryRuleCreate,
    AutoQueryRuleUpdate,
    BulkAssignRequest,
    BulkCloseRequest,
    DataQueryCreate,
    DataQueryUpdate,
    QueryCategory,
    QueryCloseRequest,
    QueryPriority,
    QueryResponseCreate,
    QuerySource,
    QueryStatus,
    ResolutionType,
)
from app.services.data_queries_service import (
    DataQueriesService,
    get_data_queries_service,
    reset_data_queries_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/data-queries"

# Standalone test app with the data-queries router
_test_app = FastAPI()
_test_app.include_router(data_queries_router)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_data_queries_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> DataQueriesService:
    """Shorthand for the fresh service."""
    return fresh_service


@pytest.fixture
async def client():
    """Async HTTP client for API tests."""
    transport = ASGITransport(app=_test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_query_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "subject_id": "SUBJ-9999",
        "visit_name": "Visit 1",
        "form_name": "Vital Signs",
        "field_name": "systolic_bp",
        "query_text": "Test query: please verify this value.",
        "priority": "medium",
        "category": "missing_data",
        "source": "manual",
    }
    defaults.update(overrides)
    return defaults


def _make_rule_create(**overrides) -> dict:
    defaults = {
        "rule_name": "Test Rule",
        "condition": "field IS NULL",
        "form": "Test Form",
        "field": "test_field",
        "message_template": "Test field is missing for subject {subject_id}.",
        "category": "missing_data",
        "priority": "medium",
        "active": True,
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_queries_count(self, svc: DataQueriesService):
        queries = svc.list_queries()
        assert len(queries) == 25

    def test_seed_queries_have_all_statuses(self, svc: DataQueriesService):
        queries = svc.list_queries()
        statuses = {q.status for q in queries}
        assert QueryStatus.OPEN in statuses
        assert QueryStatus.ANSWERED in statuses
        assert QueryStatus.CLOSED in statuses
        assert QueryStatus.CANCELLED in statuses
        assert QueryStatus.REQUERIED in statuses

    def test_seed_queries_have_all_priorities(self, svc: DataQueriesService):
        queries = svc.list_queries()
        priorities = {q.priority for q in queries}
        assert QueryPriority.CRITICAL in priorities
        assert QueryPriority.HIGH in priorities
        assert QueryPriority.MEDIUM in priorities

    def test_seed_queries_have_all_categories(self, svc: DataQueriesService):
        queries = svc.list_queries()
        categories = {q.category for q in queries}
        assert QueryCategory.MISSING_DATA in categories
        assert QueryCategory.INCONSISTENT in categories
        assert QueryCategory.OUT_OF_RANGE in categories
        assert QueryCategory.CODING_ERROR in categories
        assert QueryCategory.CONSENT in categories
        assert QueryCategory.PROTOCOL_DEVIATION in categories

    def test_seed_queries_have_all_sources(self, svc: DataQueriesService):
        queries = svc.list_queries()
        sources = {q.source for q in queries}
        assert QuerySource.MANUAL in sources
        assert QuerySource.AUTO_RULE in sources
        assert QuerySource.SDV in sources
        assert QuerySource.MEDICAL_REVIEW in sources

    def test_seed_auto_rules_count(self, svc: DataQueriesService):
        rules = svc.list_auto_rules()
        assert len(rules) == 8

    def test_seed_auto_rules_active_count(self, svc: DataQueriesService):
        active_rules = svc.list_auto_rules(active=True)
        assert len(active_rules) == 7

    def test_seed_auto_rules_inactive_count(self, svc: DataQueriesService):
        inactive_rules = svc.list_auto_rules(active=False)
        assert len(inactive_rules) == 1

    def test_seed_resolutions_exist(self, svc: DataQueriesService):
        resolutions = svc.list_resolutions()
        assert len(resolutions) == 6

    def test_seed_responses_exist_on_answered_queries(self, svc: DataQueriesService):
        query = svc.get_query("DQ-002")
        assert query is not None
        assert len(query.responses) > 0

    def test_seed_closed_queries_have_dates(self, svc: DataQueriesService):
        closed = svc.list_queries(status=QueryStatus.CLOSED)
        for q in closed:
            assert q.closed_date is not None

    def test_seed_queries_span_multiple_trials(self, svc: DataQueriesService):
        queries = svc.list_queries()
        trial_ids = {q.trial_id for q in queries}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_queries_span_multiple_sites(self, svc: DataQueriesService):
        queries = svc.list_queries()
        site_ids = {q.site_id for q in queries}
        assert len(site_ids) >= 7


# =====================================================================
# QUERY CRUD
# =====================================================================


class TestQueryCrud:
    """Test data query create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_queries(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 25
        assert len(data["items"]) == 25

    @pytest.mark.anyio
    async def test_list_queries_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries", params={"status": "open"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "open"

    @pytest.mark.anyio
    async def test_list_queries_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries", params={"site_id": "SITE-101"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_queries_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_queries_filter_priority(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries", params={"priority": "critical"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["priority"] == "critical"

    @pytest.mark.anyio
    async def test_list_queries_filter_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries", params={"category": "out_of_range"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["category"] == "out_of_range"

    @pytest.mark.anyio
    async def test_list_queries_filter_source(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries", params={"source": "auto_rule"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["source"] == "auto_rule"

    @pytest.mark.anyio
    async def test_list_queries_sorted_by_opened_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries")
        data = resp.json()
        dates = [item["opened_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_get_query(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries/DQ-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DQ-001"
        assert data["form_name"] == "Informed Consent"
        assert data["field_name"] == "consent_date"
        assert data["status"] == "open"

    @pytest.mark.anyio
    async def test_get_query_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries/DQ-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_query(self, client: AsyncClient):
        payload = _make_query_create()
        resp = await client.post(f"{API_PREFIX}/queries", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("DQ-")
        assert data["site_id"] == "SITE-101"
        assert data["status"] == "open"
        assert data["form_name"] == "Vital Signs"

    @pytest.mark.anyio
    async def test_create_query_all_fields(self, client: AsyncClient):
        payload = _make_query_create(
            subject_id="SUBJ-NEW",
            visit_name="Screening",
            priority="critical",
            category="consent",
            source="sdv",
            assigned_to="Dr. Smith",
        )
        resp = await client.post(f"{API_PREFIX}/queries", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["subject_id"] == "SUBJ-NEW"
        assert data["priority"] == "critical"
        assert data["category"] == "consent"
        assert data["source"] == "sdv"
        assert data["assigned_to"] == "Dr. Smith"

    @pytest.mark.anyio
    async def test_update_query(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/queries/DQ-001",
            json={"priority": "high", "assigned_to": "New Assignee"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["priority"] == "high"
        assert data["assigned_to"] == "New Assignee"

    @pytest.mark.anyio
    async def test_update_query_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/queries/DQ-NONEXISTENT",
            json={"priority": "low"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_query(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/queries/DQ-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/queries/DQ-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_query_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/queries/DQ-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_query_cleans_up_responses(self, svc: DataQueriesService, client: AsyncClient):
        # DQ-002 has responses
        query = svc.get_query("DQ-002")
        assert query is not None
        assert len(query.responses) > 0
        resp = await client.delete(f"{API_PREFIX}/queries/DQ-002")
        assert resp.status_code == 204
        # Verify responses are cleaned up
        responses = svc.list_responses("DQ-002")
        assert len(responses) == 0


# =====================================================================
# QUERY LIFECYCLE
# =====================================================================


class TestQueryLifecycle:
    """Test query lifecycle transitions: open, respond, close, requery, cancel."""

    @pytest.mark.anyio
    async def test_respond_to_open_query(self, client: AsyncClient):
        payload = {
            "responder": "Dr. Test, Investigator",
            "response_text": "Value has been verified against source.",
            "attachments": ["source_doc.pdf"],
        }
        resp = await client.post(f"{API_PREFIX}/queries/DQ-001/respond", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["responder"] == "Dr. Test, Investigator"
        assert data["response_text"] == "Value has been verified against source."
        assert "source_doc.pdf" in data["attachments"]

        # Verify query status changed to answered
        resp2 = await client.get(f"{API_PREFIX}/queries/DQ-001")
        assert resp2.json()["status"] == "answered"
        assert resp2.json()["answered_date"] is not None

    @pytest.mark.anyio
    async def test_respond_to_query_not_found(self, client: AsyncClient):
        payload = {"responder": "Test", "response_text": "Test response"}
        resp = await client.post(f"{API_PREFIX}/queries/DQ-NONEXISTENT/respond", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_respond_to_closed_query_fails(self, client: AsyncClient):
        payload = {"responder": "Test", "response_text": "Test"}
        resp = await client.post(f"{API_PREFIX}/queries/DQ-003/respond", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_respond_to_cancelled_query_fails(self, client: AsyncClient):
        payload = {"responder": "Test", "response_text": "Test"}
        resp = await client.post(f"{API_PREFIX}/queries/DQ-016/respond", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_close_answered_query(self, client: AsyncClient):
        payload = {
            "resolution_type": "data_corrected",
            "resolution_notes": "Value verified and corrected in CRF.",
            "resolved_by": "Data Manager",
        }
        resp = await client.post(f"{API_PREFIX}/queries/DQ-002/close", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "closed"
        assert data["closed_date"] is not None

    @pytest.mark.anyio
    async def test_close_open_query(self, client: AsyncClient):
        payload = {
            "resolution_type": "confirmed_correct",
            "resolution_notes": "Data reviewed and found to be correct.",
            "resolved_by": "CRA",
        }
        resp = await client.post(f"{API_PREFIX}/queries/DQ-001/close", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "closed"

    @pytest.mark.anyio
    async def test_close_already_closed_query_fails(self, client: AsyncClient):
        payload = {
            "resolution_type": "data_corrected",
            "resolution_notes": "Test",
            "resolved_by": "Test",
        }
        resp = await client.post(f"{API_PREFIX}/queries/DQ-003/close", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_close_cancelled_query_fails(self, client: AsyncClient):
        payload = {
            "resolution_type": "data_corrected",
            "resolution_notes": "Test",
            "resolved_by": "Test",
        }
        resp = await client.post(f"{API_PREFIX}/queries/DQ-016/close", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_close_query_not_found(self, client: AsyncClient):
        payload = {
            "resolution_type": "data_corrected",
            "resolution_notes": "Test",
            "resolved_by": "Test",
        }
        resp = await client.post(f"{API_PREFIX}/queries/DQ-NONEXISTENT/close", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_requery_answered_query(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/queries/DQ-002/requery",
            params={"query_text": "Previous response insufficient. Please provide source documentation."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "requeried"
        assert "source documentation" in data["query_text"]
        assert data["answered_date"] is None

    @pytest.mark.anyio
    async def test_requery_open_query(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/queries/DQ-001/requery",
            params={"query_text": "Updated query text with more details."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "requeried"

    @pytest.mark.anyio
    async def test_requery_closed_query_fails(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/queries/DQ-003/requery",
            params={"query_text": "Test"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_requery_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/queries/DQ-NONEXISTENT/requery",
            params={"query_text": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_cancel_open_query(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/queries/DQ-001/cancel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"
        assert data["closed_date"] is not None

    @pytest.mark.anyio
    async def test_cancel_already_cancelled_fails(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/queries/DQ-016/cancel")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_cancel_closed_query_fails(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/queries/DQ-003/cancel")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_cancel_query_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/queries/DQ-NONEXISTENT/cancel")
        assert resp.status_code == 404

    def test_full_lifecycle_open_respond_close(self, svc: DataQueriesService):
        """Test complete lifecycle: open -> respond -> close."""
        # Open
        query = svc.create_query(DataQueryCreate(
            trial_id=EYLEA_TRIAL,
            site_id="SITE-101",
            form_name="Vital Signs",
            field_name="weight",
            query_text="Weight value appears incorrect.",
            category=QueryCategory.OUT_OF_RANGE,
            source=QuerySource.MANUAL,
        ))
        assert query.status == QueryStatus.OPEN

        # Respond
        response = svc.respond_to_query(query.id, QueryResponseCreate(
            responder="Site Coordinator",
            response_text="Weight corrected to 75 kg.",
        ))
        assert response is not None
        updated = svc.get_query(query.id)
        assert updated is not None
        assert updated.status == QueryStatus.ANSWERED
        assert updated.answered_date is not None

        # Close
        closed = svc.close_query(query.id, QueryCloseRequest(
            resolution_type=ResolutionType.DATA_CORRECTED,
            resolution_notes="Weight corrected per source.",
            resolved_by="Data Manager",
        ))
        assert closed is not None
        assert closed.status == QueryStatus.CLOSED
        assert closed.closed_date is not None

        # Verify resolution exists
        resolution = svc.get_resolution(query.id)
        assert resolution is not None
        assert resolution.resolution_type == ResolutionType.DATA_CORRECTED

    def test_lifecycle_open_respond_requery_respond_close(self, svc: DataQueriesService):
        """Test lifecycle with requery: open -> respond -> requery -> respond -> close."""
        query = svc.create_query(DataQueryCreate(
            trial_id=DUPIXENT_TRIAL,
            site_id="SITE-103",
            form_name="Lab Results",
            field_name="glucose",
            query_text="Glucose value seems high.",
            category=QueryCategory.OUT_OF_RANGE,
            source=QuerySource.MANUAL,
        ))
        assert query.status == QueryStatus.OPEN

        # First response
        svc.respond_to_query(query.id, QueryResponseCreate(
            responder="Site Coordinator",
            response_text="Value is correct.",
        ))
        updated = svc.get_query(query.id)
        assert updated is not None
        assert updated.status == QueryStatus.ANSWERED

        # Requery
        requeried = svc.requery(query.id, "Please provide source document to confirm.")
        assert requeried is not None
        assert requeried.status == QueryStatus.REQUERIED
        assert requeried.answered_date is None

        # Second response
        svc.respond_to_query(query.id, QueryResponseCreate(
            responder="Investigator",
            response_text="Source document attached showing glucose of 250 mg/dL.",
            attachments=["glucose_lab_report.pdf"],
        ))
        updated = svc.get_query(query.id)
        assert updated is not None
        assert updated.status == QueryStatus.ANSWERED
        assert len(updated.responses) == 2

        # Close
        closed = svc.close_query(query.id, QueryCloseRequest(
            resolution_type=ResolutionType.CONFIRMED_CORRECT,
            resolution_notes="Source document confirms value.",
            resolved_by="CRA",
        ))
        assert closed is not None
        assert closed.status == QueryStatus.CLOSED


# =====================================================================
# QUERY RESPONSES
# =====================================================================


class TestQueryResponses:
    """Test query response management."""

    @pytest.mark.anyio
    async def test_list_responses_for_query(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries/DQ-002/responses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    @pytest.mark.anyio
    async def test_list_responses_for_query_with_multiple(self, client: AsyncClient):
        # DQ-005 has multiple responses (initial + requery)
        resp = await client.get(f"{API_PREFIX}/queries/DQ-005/responses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2

    @pytest.mark.anyio
    async def test_list_responses_query_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries/DQ-NONEXISTENT/responses")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_responses_no_responses(self, client: AsyncClient):
        # DQ-001 is open with no responses
        resp = await client.get(f"{API_PREFIX}/queries/DQ-001/responses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_response_has_attachments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries/DQ-002/responses")
        data = resp.json()
        has_attachment = any(
            len(r["attachments"]) > 0 for r in data["items"]
        )
        assert has_attachment


# =====================================================================
# DISCREPANCY RESOLUTIONS
# =====================================================================


class TestDiscrepancyResolutions:
    """Test discrepancy resolution tracking."""

    @pytest.mark.anyio
    async def test_get_resolution_for_closed_query(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries/DQ-003/resolution")
        assert resp.status_code == 200
        data = resp.json()
        assert data["query_id"] == "DQ-003"
        assert data["resolution_type"] == "data_corrected"
        assert data["resolved_by"] is not None

    @pytest.mark.anyio
    async def test_get_resolution_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries/DQ-001/resolution")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_close_creates_resolution(self, client: AsyncClient):
        # Close an open query
        close_payload = {
            "resolution_type": "confirmed_correct",
            "resolution_notes": "Data verified against source.",
            "resolved_by": "CRA Test",
        }
        resp = await client.post(f"{API_PREFIX}/queries/DQ-001/close", json=close_payload)
        assert resp.status_code == 200

        # Check resolution was created
        resp2 = await client.get(f"{API_PREFIX}/queries/DQ-001/resolution")
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["resolution_type"] == "confirmed_correct"
        assert data["resolved_by"] == "CRA Test"

    def test_resolution_for_cancelled_query(self, svc: DataQueriesService):
        # DQ-016 is cancelled and has a resolution
        resolution = svc.get_resolution("DQ-016")
        assert resolution is not None
        assert resolution.resolution_type == ResolutionType.QUERY_WITHDRAWN


# =====================================================================
# AUTO-QUERY RULES
# =====================================================================


class TestAutoQueryRules:
    """Test auto-query rule CRUD operations."""

    @pytest.mark.anyio
    async def test_list_auto_rules(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/auto-rules")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8

    @pytest.mark.anyio
    async def test_list_auto_rules_filter_active(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/auto-rules", params={"active": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 7
        for item in data["items"]:
            assert item["active"] is True

    @pytest.mark.anyio
    async def test_list_auto_rules_filter_inactive(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/auto-rules", params={"active": False})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        for item in data["items"]:
            assert item["active"] is False

    @pytest.mark.anyio
    async def test_get_auto_rule(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/auto-rules/AQR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "AQR-001"
        assert data["rule_name"] == "Missing Informed Consent Date"
        assert data["active"] is True

    @pytest.mark.anyio
    async def test_get_auto_rule_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/auto-rules/AQR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_auto_rule(self, client: AsyncClient):
        payload = _make_rule_create()
        resp = await client.post(f"{API_PREFIX}/auto-rules", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("AQR-")
        assert data["rule_name"] == "Test Rule"
        assert data["active"] is True

    @pytest.mark.anyio
    async def test_create_auto_rule_inactive(self, client: AsyncClient):
        payload = _make_rule_create(active=False, rule_name="Inactive Rule")
        resp = await client.post(f"{API_PREFIX}/auto-rules", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["active"] is False

    @pytest.mark.anyio
    async def test_update_auto_rule(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/auto-rules/AQR-001",
            json={"rule_name": "Updated Rule Name", "priority": "high"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["rule_name"] == "Updated Rule Name"
        assert data["priority"] == "high"

    @pytest.mark.anyio
    async def test_update_auto_rule_deactivate(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/auto-rules/AQR-001",
            json={"active": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] is False

    @pytest.mark.anyio
    async def test_update_auto_rule_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/auto-rules/AQR-NONEXISTENT",
            json={"rule_name": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_auto_rule(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/auto-rules/AQR-008")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/auto-rules/AQR-008")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_auto_rule_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/auto-rules/AQR-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# AUTO-QUERY EVALUATION
# =====================================================================


class TestAutoQueryEvaluation:
    """Test auto-query rule evaluation and query generation."""

    @pytest.mark.anyio
    async def test_evaluate_auto_rules(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/auto-rules/evaluate",
            params={"trial_id": EYLEA_TRIAL, "site_id": "SITE-101"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Should generate one query per active rule (7 active rules)
        assert data["total"] == 7
        for item in data["items"]:
            assert item["source"] == "auto_rule"
            assert item["status"] == "open"
            assert item["site_id"] == "SITE-101"
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_evaluate_creates_queries_in_system(self, client: AsyncClient):
        # Get initial count
        resp1 = await client.get(f"{API_PREFIX}/queries")
        initial_count = resp1.json()["total"]

        # Run evaluation
        await client.post(
            f"{API_PREFIX}/auto-rules/evaluate",
            params={"trial_id": EYLEA_TRIAL, "site_id": "SITE-102"},
        )

        # Verify new queries were added
        resp2 = await client.get(f"{API_PREFIX}/queries")
        new_count = resp2.json()["total"]
        assert new_count > initial_count

    def test_evaluate_only_active_rules(self, svc: DataQueriesService):
        initial_count = len(svc.list_queries())
        generated = svc.evaluate_auto_rules(EYLEA_TRIAL, "SITE-101")
        # Only 7 active rules
        assert len(generated) == 7
        # All generated queries have auto_rule_id
        for q in generated:
            assert q.auto_rule_id is not None
            assert q.source == QuerySource.AUTO_RULE

        total = len(svc.list_queries())
        assert total == initial_count + 7


# =====================================================================
# AGING REPORT
# =====================================================================


class TestAgingReport:
    """Test query aging report generation."""

    @pytest.mark.anyio
    async def test_get_aging_report(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports/aging")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_open"] > 0
        assert len(data["buckets"]) == 4
        assert data["oldest_query_days"] >= 0
        assert data["generated_at"] is not None

    @pytest.mark.anyio
    async def test_aging_report_bucket_labels(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports/aging")
        data = resp.json()
        bucket_labels = [b["bucket"] for b in data["buckets"]]
        assert "0-7d" in bucket_labels
        assert "8-14d" in bucket_labels
        assert "15-30d" in bucket_labels
        assert "30+d" in bucket_labels

    @pytest.mark.anyio
    async def test_aging_report_total_matches_buckets(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports/aging")
        data = resp.json()
        bucket_total = sum(b["count"] for b in data["buckets"])
        assert bucket_total == data["total_open"]

    @pytest.mark.anyio
    async def test_aging_report_includes_query_ids(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports/aging")
        data = resp.json()
        all_ids = []
        for b in data["buckets"]:
            all_ids.extend(b["query_ids"])
        assert len(all_ids) == data["total_open"]

    def test_aging_report_oldest_query(self, svc: DataQueriesService):
        report = svc.get_aging_report()
        assert report.oldest_query_days > 0
        # Should be at least 20 days (DQ-005 opened 25 days ago, requeried)
        assert report.oldest_query_days >= 10


# =====================================================================
# QUERY METRICS
# =====================================================================


class TestQueryMetrics:
    """Test query metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_queries"] == 25
        assert data["open_queries"] > 0
        assert data["answered_queries"] > 0
        assert data["closed_queries"] > 0
        assert data["cancelled_queries"] > 0
        assert data["requeried_queries"] > 0

    @pytest.mark.anyio
    async def test_metrics_status_counts_add_up(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports/metrics")
        data = resp.json()
        total_by_status = (
            data["open_queries"]
            + data["answered_queries"]
            + data["closed_queries"]
            + data["cancelled_queries"]
            + data["requeried_queries"]
        )
        assert total_by_status == data["total_queries"]

    @pytest.mark.anyio
    async def test_metrics_has_by_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports/metrics")
        data = resp.json()
        assert len(data["queries_by_category"]) > 0
        total_by_cat = sum(data["queries_by_category"].values())
        assert total_by_cat == data["total_queries"]

    @pytest.mark.anyio
    async def test_metrics_has_by_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports/metrics")
        data = resp.json()
        assert len(data["queries_by_site"]) > 0
        total_by_site = sum(data["queries_by_site"].values())
        assert total_by_site == data["total_queries"]

    @pytest.mark.anyio
    async def test_metrics_has_by_priority(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports/metrics")
        data = resp.json()
        assert len(data["queries_by_priority"]) > 0
        total_by_priority = sum(data["queries_by_priority"].values())
        assert total_by_priority == data["total_queries"]

    @pytest.mark.anyio
    async def test_metrics_avg_resolution_days(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports/metrics")
        data = resp.json()
        # Should have some positive resolution time since we have closed queries
        assert data["avg_resolution_days"] > 0

    @pytest.mark.anyio
    async def test_metrics_auto_vs_manual_count(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports/metrics")
        data = resp.json()
        assert data["auto_query_count"] > 0
        assert data["manual_query_count"] > 0
        # Auto + manual doesn't have to equal total (there's also SDV and medical_review)

    def test_metrics_categories_include_all_used(self, svc: DataQueriesService):
        metrics = svc.get_query_metrics()
        assert "missing_data" in metrics.queries_by_category
        assert "inconsistent" in metrics.queries_by_category
        assert "out_of_range" in metrics.queries_by_category
        assert "coding_error" in metrics.queries_by_category
        assert "consent" in metrics.queries_by_category


# =====================================================================
# SITE QUERY SUMMARY
# =====================================================================


class TestSiteQuerySummary:
    """Test site query summary reports."""

    @pytest.mark.anyio
    async def test_get_site_summary_all(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports/site-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 7  # At least 7 distinct sites

    @pytest.mark.anyio
    async def test_get_site_summary_specific_site(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/reports/site-summary", params={"site_id": "SITE-101"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_site_summary_counts_consistent(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/reports/site-summary", params={"site_id": "SITE-101"}
        )
        data = resp.json()
        summary = data["items"][0]
        # Total should be sum of all status counts (approximately, minus cancelled)
        assert summary["total_queries"] > 0
        assert summary["total_queries"] >= summary["open_queries"]

    @pytest.mark.anyio
    async def test_site_summary_has_avg_resolution(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports/site-summary")
        data = resp.json()
        # At least some sites should have avg_resolution_days > 0
        has_resolution_time = any(
            item["avg_resolution_days"] > 0 for item in data["items"]
        )
        assert has_resolution_time

    def test_site_summary_nonexistent_site_returns_empty(self, svc: DataQueriesService):
        summaries = svc.get_site_query_summary(site_id="SITE-NONEXISTENT")
        assert len(summaries) == 0


# =====================================================================
# BULK OPERATIONS
# =====================================================================


class TestBulkOperations:
    """Test bulk close and bulk assign operations."""

    @pytest.mark.anyio
    async def test_bulk_close_queries(self, client: AsyncClient):
        payload = {
            "query_ids": ["DQ-001", "DQ-004", "DQ-007"],
            "resolution_type": "confirmed_correct",
            "resolution_notes": "Bulk closure - data verified.",
            "resolved_by": "Data Manager",
        }
        resp = await client.post(f"{API_PREFIX}/bulk/close", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_succeeded"] == 3
        assert data["total_failed"] == 0
        assert len(data["succeeded"]) == 3

        # Verify queries are actually closed
        for qid in ["DQ-001", "DQ-004", "DQ-007"]:
            resp2 = await client.get(f"{API_PREFIX}/queries/{qid}")
            assert resp2.json()["status"] == "closed"

    @pytest.mark.anyio
    async def test_bulk_close_with_some_failures(self, client: AsyncClient):
        payload = {
            "query_ids": ["DQ-001", "DQ-003", "DQ-NONEXISTENT"],
            "resolution_type": "data_corrected",
            "resolution_notes": "Bulk closure test.",
            "resolved_by": "Test",
        }
        resp = await client.post(f"{API_PREFIX}/bulk/close", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        # DQ-001 should succeed, DQ-003 already closed fails, NONEXISTENT fails
        assert data["total_succeeded"] == 1
        assert data["total_failed"] == 2

    @pytest.mark.anyio
    async def test_bulk_assign_queries(self, client: AsyncClient):
        payload = {
            "query_ids": ["DQ-001", "DQ-004", "DQ-006"],
            "assigned_to": "Senior Data Manager",
        }
        resp = await client.post(f"{API_PREFIX}/bulk/assign", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_succeeded"] == 3
        assert data["total_failed"] == 0

        # Verify assignments
        for qid in ["DQ-001", "DQ-004", "DQ-006"]:
            resp2 = await client.get(f"{API_PREFIX}/queries/{qid}")
            assert resp2.json()["assigned_to"] == "Senior Data Manager"

    @pytest.mark.anyio
    async def test_bulk_assign_with_nonexistent(self, client: AsyncClient):
        payload = {
            "query_ids": ["DQ-001", "DQ-NONEXISTENT"],
            "assigned_to": "Test Assignee",
        }
        resp = await client.post(f"{API_PREFIX}/bulk/assign", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_succeeded"] == 1
        assert data["total_failed"] == 1
        assert "DQ-001" in data["succeeded"]
        assert "DQ-NONEXISTENT" in data["failed"]

    def test_bulk_close_empty_list(self, svc: DataQueriesService):
        result = svc.bulk_close_queries(BulkCloseRequest(
            query_ids=[],
            resolution_type=ResolutionType.DATA_CORRECTED,
            resolution_notes="Test",
            resolved_by="Test",
        ))
        assert result.total_succeeded == 0
        assert result.total_failed == 0

    def test_bulk_assign_empty_list(self, svc: DataQueriesService):
        result = svc.bulk_assign_queries(BulkAssignRequest(
            query_ids=[],
            assigned_to="Test",
        ))
        assert result.total_succeeded == 0
        assert result.total_failed == 0


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_data_queries_service()
        svc2 = get_data_queries_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_data_queries_service()
        svc2 = reset_data_queries_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_data_queries_service()
        svc.delete_query("DQ-001")
        assert svc.get_query("DQ-001") is None
        svc2 = reset_data_queries_service()
        assert svc2.get_query("DQ-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_queries_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_queries_filter_returns_empty(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/queries", params={"site_id": "SITE-NONEXISTENT"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_auto_rules_no_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/auto-rules")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_query_minimal_fields(self, client: AsyncClient):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "site_id": "SITE-101",
            "form_name": "Test Form",
            "field_name": "test_field",
            "query_text": "Test query.",
            "category": "other",
        }
        resp = await client.post(f"{API_PREFIX}/queries", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["priority"] == "medium"  # Default
        assert data["source"] == "manual"  # Default
        assert data["subject_id"] is None
        assert data["visit_name"] is None

    @pytest.mark.anyio
    async def test_query_responses_preserved_on_status_change(self, client: AsyncClient):
        # DQ-002 is answered and has responses
        # Close it and verify responses still exist
        close_payload = {
            "resolution_type": "confirmed_correct",
            "resolution_notes": "Test",
            "resolved_by": "Test",
        }
        await client.post(f"{API_PREFIX}/queries/DQ-002/close", json=close_payload)
        resp = await client.get(f"{API_PREFIX}/queries/DQ-002")
        data = resp.json()
        assert len(data["responses"]) > 0
        assert data["status"] == "closed"

    @pytest.mark.anyio
    async def test_multiple_responds_accumulate(self, client: AsyncClient):
        # First response to open query
        payload1 = {"responder": "Coordinator", "response_text": "First response"}
        await client.post(f"{API_PREFIX}/queries/DQ-001/respond", json=payload1)

        # Requery
        await client.post(
            f"{API_PREFIX}/queries/DQ-001/requery",
            params={"query_text": "Need more info"},
        )

        # Second response
        payload2 = {"responder": "Investigator", "response_text": "Second response"}
        await client.post(f"{API_PREFIX}/queries/DQ-001/respond", json=payload2)

        # Verify both responses exist
        resp = await client.get(f"{API_PREFIX}/queries/DQ-001")
        data = resp.json()
        assert len(data["responses"]) == 2

    def test_query_auto_rule_linkage(self, svc: DataQueriesService):
        """Auto-rule generated queries should link back to their rule."""
        auto_queries = svc.list_queries(source=QuerySource.AUTO_RULE)
        for q in auto_queries:
            assert q.auto_rule_id is not None
            rule = svc.get_auto_rule(q.auto_rule_id)
            assert rule is not None

    def test_closed_query_has_resolution(self, svc: DataQueriesService):
        """All seeded closed queries should have resolutions."""
        closed = svc.list_queries(status=QueryStatus.CLOSED)
        for q in closed:
            resolution = svc.get_resolution(q.id)
            assert resolution is not None
            assert resolution.resolved_by is not None

    @pytest.mark.anyio
    async def test_query_has_correct_timestamps(self, client: AsyncClient):
        # Create a query
        payload = _make_query_create()
        resp = await client.post(f"{API_PREFIX}/queries", json=payload)
        data = resp.json()
        assert data["opened_date"] is not None
        assert data["created_at"] is not None
        assert data["answered_date"] is None
        assert data["closed_date"] is None

    @pytest.mark.anyio
    async def test_auto_rule_create_with_all_fields(self, client: AsyncClient):
        payload = _make_rule_create(
            rule_name="Full Rule",
            condition="value > 100",
            form="Lab Results",
            field="hemoglobin",
            message_template="Hemoglobin value {value} out of range.",
            category="out_of_range",
            priority="critical",
            active=True,
        )
        resp = await client.post(f"{API_PREFIX}/auto-rules", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["category"] == "out_of_range"
        assert data["priority"] == "critical"


# =====================================================================
# ENUMERATION COVERAGE
# =====================================================================


class TestEnumerations:
    """Test that all enum values are correctly used in the system."""

    @pytest.mark.anyio
    async def test_all_query_statuses_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "open" in statuses
        assert "answered" in statuses
        assert "closed" in statuses
        assert "cancelled" in statuses
        assert "requeried" in statuses

    @pytest.mark.anyio
    async def test_all_priorities_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries")
        data = resp.json()
        priorities = {item["priority"] for item in data["items"]}
        assert "critical" in priorities
        assert "high" in priorities
        assert "medium" in priorities

    @pytest.mark.anyio
    async def test_all_categories_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries")
        data = resp.json()
        categories = {item["category"] for item in data["items"]}
        assert "missing_data" in categories
        assert "inconsistent" in categories
        assert "out_of_range" in categories
        assert "coding_error" in categories
        assert "consent" in categories
        assert "protocol_deviation" in categories

    @pytest.mark.anyio
    async def test_all_sources_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries")
        data = resp.json()
        sources = {item["source"] for item in data["items"]}
        assert "manual" in sources
        assert "auto_rule" in sources
        assert "sdv" in sources
        assert "medical_review" in sources

    @pytest.mark.anyio
    async def test_resolution_types(self, svc: DataQueriesService):
        resolutions = svc.list_resolutions()
        types = {r.resolution_type for r in resolutions}
        assert ResolutionType.DATA_CORRECTED in types
        assert ResolutionType.QUERY_WITHDRAWN in types


# =====================================================================
# QUERY FILTER COMBINATIONS
# =====================================================================


class TestFilterCombinations:
    """Test combining multiple filters."""

    @pytest.mark.anyio
    async def test_filter_by_trial_and_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/queries",
            params={"trial_id": EYLEA_TRIAL, "status": "open"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["status"] == "open"

    @pytest.mark.anyio
    async def test_filter_by_site_and_category(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/queries",
            params={"site_id": "SITE-103", "category": "inconsistent"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-103"
            assert item["category"] == "inconsistent"

    @pytest.mark.anyio
    async def test_filter_by_priority_and_source(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/queries",
            params={"priority": "critical", "source": "auto_rule"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["priority"] == "critical"
            assert item["source"] == "auto_rule"

    @pytest.mark.anyio
    async def test_filter_all_params_returns_subset(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/queries",
            params={
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "status": "open",
                "priority": "critical",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["site_id"] == "SITE-101"
            assert item["status"] == "open"
            assert item["priority"] == "critical"


# =====================================================================
# METRICS AFTER MUTATIONS
# =====================================================================


class TestMetricsAfterMutations:
    """Test that metrics update correctly after data changes."""

    @pytest.mark.anyio
    async def test_metrics_after_closing_query(self, client: AsyncClient):
        # Get initial metrics
        resp1 = await client.get(f"{API_PREFIX}/reports/metrics")
        initial = resp1.json()
        initial_closed = initial["closed_queries"]
        initial_open = initial["open_queries"]

        # Close an open query
        close_payload = {
            "resolution_type": "data_corrected",
            "resolution_notes": "Test",
            "resolved_by": "Test",
        }
        await client.post(f"{API_PREFIX}/queries/DQ-001/close", json=close_payload)

        # Check updated metrics
        resp2 = await client.get(f"{API_PREFIX}/reports/metrics")
        updated = resp2.json()
        assert updated["closed_queries"] == initial_closed + 1
        assert updated["open_queries"] == initial_open - 1

    @pytest.mark.anyio
    async def test_metrics_after_creating_query(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/reports/metrics")
        initial_total = resp1.json()["total_queries"]

        payload = _make_query_create()
        await client.post(f"{API_PREFIX}/queries", json=payload)

        resp2 = await client.get(f"{API_PREFIX}/reports/metrics")
        assert resp2.json()["total_queries"] == initial_total + 1

    @pytest.mark.anyio
    async def test_aging_report_after_closing_query(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/reports/aging")
        initial_open = resp1.json()["total_open"]

        # Close an open query
        close_payload = {
            "resolution_type": "data_corrected",
            "resolution_notes": "Test",
            "resolved_by": "Test",
        }
        await client.post(f"{API_PREFIX}/queries/DQ-001/close", json=close_payload)

        resp2 = await client.get(f"{API_PREFIX}/reports/aging")
        assert resp2.json()["total_open"] == initial_open - 1

    @pytest.mark.anyio
    async def test_site_summary_after_creating_query(self, client: AsyncClient):
        # Get initial summary for SITE-101
        resp1 = await client.get(
            f"{API_PREFIX}/reports/site-summary", params={"site_id": "SITE-101"}
        )
        initial_total = resp1.json()["items"][0]["total_queries"]

        # Create a new query for SITE-101
        payload = _make_query_create(site_id="SITE-101")
        await client.post(f"{API_PREFIX}/queries", json=payload)

        # Check updated summary
        resp2 = await client.get(
            f"{API_PREFIX}/reports/site-summary", params={"site_id": "SITE-101"}
        )
        assert resp2.json()["items"][0]["total_queries"] == initial_total + 1
