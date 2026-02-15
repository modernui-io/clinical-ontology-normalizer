"""Tests for P2-006, P2-008, P2-009 clinical features.

Covers:
- KG completeness scorer service (P2-006)
- KG completeness API endpoint (P2-006)
- Clinician feedback API endpoint (P2-009)
- Clinician feedback summary endpoint (P2-009)
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.kg_completeness_scorer import (
    KGCompletenessScore,
    score_patient_graph,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture(autouse=True)
def _clear_feedback_store():
    """Clear the in-memory feedback store between tests."""
    from app.api.clinician_feedback import _feedback_store
    _feedback_store.clear()
    yield
    _feedback_store.clear()


# ===========================================================================
# P2-006: KG Completeness Scorer - Unit Tests
# ===========================================================================


class TestKGCompletenessScorer:
    """Unit tests for score_patient_graph."""

    def test_empty_graph_scores_zero(self) -> None:
        """An empty graph should return 0.0 overall."""
        result = score_patient_graph("pt-001", [], [])
        assert result.overall_score == 0.0
        assert all(v == 0.0 for v in result.dimensions.values())
        assert len(result.missing_categories) == 5
        assert any("Empty knowledge graph" in f for f in result.data_quality_flags)

    def test_full_graph_scores_high(self) -> None:
        """A graph with all dimensions well-covered should score near 1.0."""
        nodes = [
            {"type": "condition", "label": "T2DM"},
            {"type": "condition", "label": "HTN"},
            {"type": "condition", "label": "CKD"},
            {"type": "drug", "label": "Metformin"},
            {"type": "drug", "label": "Lisinopril"},
            {"type": "measurement", "label": "HbA1c"},
            {"type": "measurement", "label": "Creatinine"},
            {"type": "measurement", "label": "BP"},
            {"type": "procedure", "label": "Dialysis access"},
            {"type": "demographic", "label": "Age 65"},
            {"type": "demographic", "label": "Male"},
        ]
        edges = [
            {"source": "pt-001", "target": "n1", "relation": "has_condition"},
        ]
        result = score_patient_graph("pt-001", nodes, edges)
        assert result.overall_score == 1.0
        assert result.missing_categories == []
        assert all(v == 1.0 for v in result.dimensions.values())

    def test_partial_graph(self) -> None:
        """A graph with some dimensions should have a partial score."""
        nodes = [
            {"type": "condition", "label": "T2DM"},
            {"type": "drug", "label": "Metformin"},
        ]
        result = score_patient_graph("pt-002", nodes, [])
        assert 0.0 < result.overall_score < 1.0
        assert result.dimensions["conditions"] > 0
        assert result.dimensions["medications"] > 0
        assert result.dimensions["labs"] == 0.0
        assert "No lab results found" in result.missing_categories

    def test_patient_node_counts_as_demographics(self) -> None:
        """A 'patient' node type should count toward demographics."""
        nodes = [{"type": "patient", "label": "John Doe"}]
        result = score_patient_graph("pt-003", nodes, [])
        assert result.dimensions["demographics"] > 0

    def test_observation_counts_as_labs(self) -> None:
        """An 'observation' node type should count toward labs."""
        nodes = [{"type": "observation", "label": "Blood Pressure"}]
        result = score_patient_graph("pt-004", nodes, [])
        assert result.dimensions["labs"] > 0

    def test_unknown_node_type_ignored(self) -> None:
        """Unknown node types should not affect any dimension."""
        nodes = [{"type": "foobar", "label": "Mystery"}]
        result = score_patient_graph("pt-005", nodes, [])
        assert result.overall_score == 0.0

    def test_disconnected_graph_flag(self) -> None:
        """Multiple nodes with no edges should produce a disconnected flag."""
        nodes = [
            {"type": "condition", "label": "A"},
            {"type": "drug", "label": "B"},
        ]
        result = score_patient_graph("pt-006", nodes, [])
        assert any("disconnected" in f for f in result.data_quality_flags)

    def test_category_counts_populated(self) -> None:
        """category_counts should accurately reflect node counts per dimension."""
        nodes = [
            {"type": "condition", "label": "A"},
            {"type": "condition", "label": "B"},
            {"type": "drug", "label": "C"},
        ]
        result = score_patient_graph("pt-007", nodes, [])
        assert result.category_counts["conditions"] == 2
        assert result.category_counts["medications"] == 1
        assert result.category_counts["labs"] == 0


# ===========================================================================
# P2-006: KG Completeness API Tests
# ===========================================================================


class TestKGCompletenessAPI:
    """API tests for /api/v1/kg/completeness/score."""

    @pytest.mark.asyncio
    async def test_score_endpoint_returns_200(self, client: AsyncClient) -> None:
        """POST /api/v1/kg/completeness/score should return 200."""
        response = await client.post(
            "/api/v1/kg/completeness/score",
            json={
                "patient_id": "pt-001",
                "nodes": [{"type": "condition", "label": "T2DM"}],
                "edges": [],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "overall_score" in data
        assert "dimensions" in data
        assert "missing_categories" in data
        assert data["patient_id"] == "pt-001"

    @pytest.mark.asyncio
    async def test_score_endpoint_empty_graph(self, client: AsyncClient) -> None:
        """Empty graph should return 0.0 overall score."""
        response = await client.post(
            "/api/v1/kg/completeness/score",
            json={"patient_id": "pt-002", "nodes": [], "edges": []},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["overall_score"] == 0.0

    @pytest.mark.asyncio
    async def test_score_endpoint_validation(self, client: AsyncClient) -> None:
        """Missing patient_id should return 422."""
        response = await client.post(
            "/api/v1/kg/completeness/score",
            json={"nodes": [], "edges": []},
        )
        assert response.status_code == 422


# ===========================================================================
# P2-009: Clinician Feedback API Tests
# ===========================================================================


class TestClinicianFeedbackAPI:
    """API tests for /api/v1/clinician-feedback."""

    @pytest.mark.asyncio
    async def test_submit_feedback_returns_201(self, client: AsyncClient) -> None:
        """POST /api/v1/clinician-feedback should return 201."""
        response = await client.post(
            "/api/v1/clinician-feedback",
            json={
                "query_id": "q-123",
                "response_id": "r-456",
                "rating": 4,
                "feedback_text": "Good response",
                "correction_type": "agree",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["query_id"] == "q-123"
        assert data["response_id"] == "r-456"
        assert data["rating"] == 4
        assert data["correction_type"] == "agree"
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_submit_feedback_invalid_rating(self, client: AsyncClient) -> None:
        """Rating outside 1-5 should return 422."""
        response = await client.post(
            "/api/v1/clinician-feedback",
            json={
                "query_id": "q-123",
                "response_id": "r-456",
                "rating": 6,
                "correction_type": "agree",
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_submit_feedback_invalid_correction_type(
        self, client: AsyncClient
    ) -> None:
        """Invalid correction type should return 422."""
        response = await client.post(
            "/api/v1/clinician-feedback",
            json={
                "query_id": "q-123",
                "response_id": "r-456",
                "rating": 3,
                "correction_type": "invalid_type",
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_submit_feedback_without_text(self, client: AsyncClient) -> None:
        """Feedback text is optional."""
        response = await client.post(
            "/api/v1/clinician-feedback",
            json={
                "query_id": "q-123",
                "response_id": "r-456",
                "rating": 5,
                "correction_type": "agree",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["feedback_text"] is None

    @pytest.mark.asyncio
    async def test_feedback_summary_empty(self, client: AsyncClient) -> None:
        """Summary with no data should return zeroed stats."""
        response = await client.get("/api/v1/clinician-feedback/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["total_feedbacks"] == 0
        assert data["average_rating"] == 0.0

    @pytest.mark.asyncio
    async def test_feedback_summary_with_data(self, client: AsyncClient) -> None:
        """Summary after submitting feedback should reflect counts."""
        # Submit two feedbacks
        await client.post(
            "/api/v1/clinician-feedback",
            json={
                "query_id": "q-1",
                "response_id": "r-1",
                "rating": 5,
                "correction_type": "agree",
            },
        )
        await client.post(
            "/api/v1/clinician-feedback",
            json={
                "query_id": "q-2",
                "response_id": "r-2",
                "rating": 3,
                "correction_type": "partial",
            },
        )

        response = await client.get("/api/v1/clinician-feedback/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["total_feedbacks"] == 2
        assert data["average_rating"] == 4.0
        assert data["rating_distribution"]["5"] == 1 or data["rating_distribution"][5] == 1
        assert data["recent_feedback_count"] == 2
        # Check correction type counts
        ct = data["correction_type_counts"]
        assert ct["agree"] == 1
        assert ct["partial"] == 1

    @pytest.mark.asyncio
    async def test_all_correction_types_accepted(self, client: AsyncClient) -> None:
        """All four correction types should be accepted."""
        for ct in ["agree", "disagree", "partial", "irrelevant"]:
            response = await client.post(
                "/api/v1/clinician-feedback",
                json={
                    "query_id": f"q-{ct}",
                    "response_id": f"r-{ct}",
                    "rating": 3,
                    "correction_type": ct,
                },
            )
            assert response.status_code == 201, f"Failed for correction_type={ct}"
