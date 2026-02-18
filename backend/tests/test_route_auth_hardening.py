"""Route authentication hardening tests.

Verifies that clinical/PHI endpoints enforce JWT authentication (401)
and permission checks (403) after the auth hardening changes.

Authentication (401) is enforced by the ``get_current_user`` dependency,
which is overridable in tests.  Authorization (403) via
``app.core.permissions.PermissionChecker`` reads from ``request.state.user``
and is a no-op when ``auth_enabled=False`` (dev mode).  For those routes we
only test the 401 gate here.  Routes using ``require_admin`` (which chains
through ``get_current_user``) also get 403 tests.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.middleware.auth_middleware import CurrentUser, get_current_user
from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(permissions: list[str] | None = None, roles: list[str] | None = None) -> CurrentUser:
    return CurrentUser(
        id="u1",
        email="t@test.com",
        name="Test User",
        roles=roles or ["provider"],
        permissions=permissions or [],
    )


def make_admin() -> CurrentUser:
    return CurrentUser(
        id="admin1",
        email="admin@test.com",
        name="Admin",
        roles=["admin"],
        permissions=["admin"],
    )


def _raise_401():
    """Simulates missing/invalid JWT by raising 401 immediately."""
    from fastapi import HTTPException, status
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_overrides():
    """Reset dependency overrides after each test."""
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def unauthed() -> TestClient:
    """Client with no auth (simulates missing/invalid JWT)."""
    app.dependency_overrides[get_current_user] = _raise_401
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def no_perm() -> TestClient:
    """Client with valid auth but no permissions (for require_admin 403 tests)."""
    app.dependency_overrides[get_current_user] = lambda: make_user(permissions=[])
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def admin() -> TestClient:
    """Client with admin role."""
    app.dependency_overrides[get_current_user] = lambda: make_admin()
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def provider() -> TestClient:
    """Client with provider role and read_documents permission."""
    app.dependency_overrides[get_current_user] = lambda: make_user(
        permissions=["read_documents", "read_clinical_facts", "read_patients"],
        roles=["provider"],
    )
    return TestClient(app, raise_server_exceptions=False)


# ===========================================================================
# export.py — GET /api/v1/export/omop/{patient_id}
# Requires: EXPORT_DATA permission
# ===========================================================================

class TestExportOmop:
    ENDPOINT = "/api/v1/export/omop/patient-xyz"

    def test_no_auth_returns_401(self, unauthed):
        assert unauthed.get(self.ENDPOINT).status_code == 401


# ===========================================================================
# graph_rag.py
# ===========================================================================

class TestGraphRagPatientSummary:
    """GET /api/v1/graph-rag/patient-summary/{patient_id}"""

    ENDPOINT = "/api/v1/graph-rag/patient-summary/patient-xyz"

    def test_no_auth_returns_401(self, unauthed):
        assert unauthed.get(self.ENDPOINT).status_code == 401


class TestGraphRagSearch:
    """GET /api/v1/graph-rag/search/{patient_id}"""

    def test_no_auth_returns_401(self, unauthed):
        resp = unauthed.get(
            "/api/v1/graph-rag/search/patient-xyz",
            params={"query": "diabetes"},
        )
        assert resp.status_code == 401


class TestGraphRagAnswer:
    """POST /api/v1/graph-rag/answer"""

    def test_no_auth_returns_401(self, unauthed):
        resp = unauthed.post(
            "/api/v1/graph-rag/answer",
            params={"patient_id": "p1", "question": "medications?"},
        )
        assert resp.status_code == 401


class TestGraphRagOntologySearch:
    """GET /api/v1/graph-rag/ontology/search"""

    def test_no_auth_returns_401(self, unauthed):
        resp = unauthed.get(
            "/api/v1/graph-rag/ontology/search",
            params={"query": "diabetes"},
        )
        assert resp.status_code == 401


class TestGraphRagConceptPatients:
    """GET /api/v1/graph-rag/concepts/{omop_concept_id}/patients"""

    def test_no_auth_returns_401(self, unauthed):
        assert unauthed.get("/api/v1/graph-rag/concepts/201826/patients").status_code == 401


class TestGraphRagGlobalConcepts:
    """GET /api/v1/graph-rag/global-concepts"""

    def test_no_auth_returns_401(self, unauthed):
        assert unauthed.get("/api/v1/graph-rag/global-concepts").status_code == 401


# ===========================================================================
# clinical_agent.py
# ===========================================================================

class TestClinicalAgentPatientGraph:
    """GET /api/v1/clinical-agent/graph/{patient_id}"""

    ENDPOINT = "/api/v1/clinical-agent/graph/patient-xyz"

    def test_no_auth_returns_401(self, unauthed):
        assert unauthed.get(self.ENDPOINT).status_code == 401

    def test_with_auth_passes_gate(self, provider):
        resp = provider.get(self.ENDPOINT)
        assert resp.status_code not in (401, 403)


class TestClinicalAgentListPatients:
    """GET /api/v1/clinical-agent/patients"""

    def test_no_auth_returns_401(self, unauthed):
        assert unauthed.get("/api/v1/clinical-agent/patients").status_code == 401


class TestClinicalAgentDeleteGraph:
    """DELETE /api/v1/clinical-agent/graph/{patient_id}"""

    def test_no_auth_returns_401(self, unauthed):
        resp = unauthed.delete("/api/v1/clinical-agent/graph/patient-xyz")
        assert resp.status_code == 401


class TestClinicalAgentProvenance:
    """GET /api/v1/clinical-agent/provenance/{query_id}"""

    def test_no_auth_returns_401(self, unauthed):
        resp = unauthed.get("/api/v1/clinical-agent/provenance/q-123")
        assert resp.status_code == 401


# ===========================================================================
# graph.py: Admin Cypher
# Uses require_admin (chains get_current_user) → 403 testable
# ===========================================================================

class TestGraphCypherQuery:
    """POST /api/v1/graph/query — admin only via require_admin."""

    ENDPOINT = "/api/v1/graph/query"
    BODY = {"query": "MATCH (n) RETURN n LIMIT 1"}

    def test_no_auth_returns_401(self, unauthed):
        assert unauthed.post(self.ENDPOINT, json=self.BODY).status_code == 401

    def test_non_admin_returns_403(self, no_perm):
        # require_admin uses get_current_user, so override is respected
        assert no_perm.post(self.ENDPOINT, json=self.BODY).status_code == 403

    def test_admin_passes_gate(self, admin):
        resp = admin.post(self.ENDPOINT, json=self.BODY)
        assert resp.status_code not in (401, 403)


class TestGraphHealth:
    """GET /api/v1/graph/health — must stay public."""

    def test_health_public_no_auth(self, unauthed):
        resp = unauthed.get("/api/v1/graph/health")
        assert resp.status_code not in (401, 403)


class TestGraphSimilarPatients:
    """GET /api/v1/graph/patients/{patient_id}/similar"""

    def test_no_auth_returns_401(self, unauthed):
        assert unauthed.get("/api/v1/graph/patients/p1/similar").status_code == 401


class TestGraphPatientSubgraph:
    """GET /api/v1/graph/patients/{patient_id}/subgraph"""

    def test_no_auth_returns_401(self, unauthed):
        assert unauthed.get("/api/v1/graph/patients/p1/subgraph").status_code == 401


class TestGraphConceptNeighbors:
    """GET /api/v1/graph/concepts/{concept_id}/neighbors"""

    def test_no_auth_returns_401(self, unauthed):
        assert unauthed.get("/api/v1/graph/concepts/201826/neighbors").status_code == 401


class TestGraphCacheStats:
    """GET /api/v1/graph/cache/stats"""

    def test_no_auth_returns_401(self, unauthed):
        assert unauthed.get("/api/v1/graph/cache/stats").status_code == 401


class TestGraphStats:
    """GET /api/v1/graph/stats"""

    def test_no_auth_returns_401(self, unauthed):
        assert unauthed.get("/api/v1/graph/stats").status_code == 401


class TestGraphMultiHopReasoning:
    """POST /api/v1/graph/reasoning/multi-hop"""

    def test_no_auth_returns_401(self, unauthed):
        resp = unauthed.post(
            "/api/v1/graph/reasoning/multi-hop",
            json={"seed_concept_ids": [201826], "max_hops": 2},
        )
        assert resp.status_code == 401


# ===========================================================================
# nlp.py
# ===========================================================================

class TestNLPExtract:
    """POST /api/v1/nlp/extract"""

    ENDPOINT = "/api/v1/nlp/extract"

    def test_no_auth_returns_401(self, unauthed):
        assert unauthed.post(
            self.ENDPOINT,
            json={"text": "Patient has diabetes mellitus."},
        ).status_code == 401

    def test_with_auth_passes_gate(self, provider):
        resp = provider.post(
            self.ENDPOINT,
            json={"text": "Patient has diabetes mellitus."},
        )
        assert resp.status_code not in (401, 403)


class TestNLPModels:
    """GET /api/v1/nlp/models"""

    def test_no_auth_returns_401(self, unauthed):
        assert unauthed.get("/api/v1/nlp/models").status_code == 401


class TestNLPSamples:
    """GET /api/v1/nlp/samples"""

    def test_no_auth_returns_401(self, unauthed):
        assert unauthed.get("/api/v1/nlp/samples").status_code == 401


class TestNLPStats:
    """GET /api/v1/nlp/stats"""

    def test_no_auth_returns_401(self, unauthed):
        assert unauthed.get("/api/v1/nlp/stats").status_code == 401


class TestNLPPreload:
    """POST /api/v1/nlp/preload — requires admin via require_admin."""

    ENDPOINT = "/api/v1/nlp/preload"

    def test_no_auth_returns_401(self, unauthed):
        assert unauthed.post(self.ENDPOINT).status_code == 401

    def test_non_admin_returns_403(self, no_perm):
        # require_admin chains get_current_user, so override is respected
        assert no_perm.post(self.ENDPOINT).status_code == 403

    def test_admin_passes_gate(self, admin):
        resp = admin.post(self.ENDPOINT)
        assert resp.status_code not in (401, 403)
