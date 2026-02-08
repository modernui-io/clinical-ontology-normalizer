"""Tests for Terminology Governance workflow service and API endpoints.

Dir-CI-3.1: Terminology Governance Workflow - verifies submission to review
queue, approve/reject/escalate workflows, queue filtering, review statistics,
auto-submission for low-confidence mappings, and API endpoint responses.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.terminology_governance import (
    ReviewDecision,
    ReviewItemResponse,
    ReviewStats,
    ReviewStatus,
    ReviewSubmission,
)
from app.services.terminology_governance_service import (
    TerminologyGovernanceService,
    get_terminology_governance_service,
    reset_terminology_governance_service,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def _reset_service():
    """Reset the governance service singleton before each test."""
    reset_terminology_governance_service()
    yield
    reset_terminology_governance_service()


@pytest.fixture()
def service() -> TerminologyGovernanceService:
    """Get a fresh governance service instance."""
    return get_terminology_governance_service()


def _submit_sample(
    service: TerminologyGovernanceService,
    *,
    confidence: float = 0.5,
    domain: str = "condition",
    concept_name: str = "Hypertension",
    concept_id: int = 316866,
) -> ReviewItemResponse:
    """Helper to submit a sample mapping for review."""
    return service.submit_for_review(
        mention_id="mention-001",
        candidate_id="candidate-001",
        concept_name=concept_name,
        concept_id=concept_id,
        confidence=confidence,
        domain=domain,
        reason="Low confidence mapping",
        submitted_by="dr.smith",
    )


# ============================================================================
# Schema tests
# ============================================================================


class TestTerminologyGovernanceSchemas:
    """Test Pydantic schema construction and validation."""

    def test_review_item_response_creation(self):
        now = datetime.now(timezone.utc)
        item = ReviewItemResponse(
            id="r-001",
            mention_id="m-001",
            candidate_id="c-001",
            concept_name="Diabetes mellitus",
            concept_id=201826,
            confidence=0.45,
            domain="condition",
            status=ReviewStatus.PENDING,
            reason="Low confidence",
            submitted_at=now,
            submitted_by="system",
        )
        assert item.id == "r-001"
        assert item.status == ReviewStatus.PENDING
        assert item.confidence == 0.45
        assert item.reviewed_at is None

    def test_review_submission_creation(self):
        submission = ReviewSubmission(
            mention_id="m-001",
            candidate_id="c-001",
            reason="Manual review requested",
            submitted_by="dr.jones",
        )
        assert submission.mention_id == "m-001"
        assert submission.submitted_by == "dr.jones"

    def test_review_decision_creation(self):
        decision = ReviewDecision(
            reviewer_id="expert-1",
            notes="Correct mapping confirmed",
        )
        assert decision.reviewer_id == "expert-1"
        assert decision.suggested_concept_id is None

    def test_review_decision_with_suggested_concept(self):
        decision = ReviewDecision(
            reviewer_id="expert-1",
            notes="Better concept available",
            suggested_concept_id=442793,
        )
        assert decision.suggested_concept_id == 442793

    def test_review_stats_creation(self):
        stats = ReviewStats(
            total=100,
            pending=40,
            approved=35,
            rejected=20,
            escalated=5,
            avg_review_hours=2.5,
        )
        assert stats.total == 100
        assert stats.pending == 40
        assert stats.avg_review_hours == 2.5

    def test_review_status_enum_values(self):
        assert ReviewStatus.PENDING == "pending"
        assert ReviewStatus.APPROVED == "approved"
        assert ReviewStatus.REJECTED == "rejected"
        assert ReviewStatus.ESCALATED == "escalated"


# ============================================================================
# Service tests
# ============================================================================


class TestTerminologyGovernanceService:
    """Test the governance service business logic."""

    def test_submit_for_review(self, service: TerminologyGovernanceService):
        item = _submit_sample(service)

        assert item.id is not None
        assert item.status == ReviewStatus.PENDING
        assert item.mention_id == "mention-001"
        assert item.concept_name == "Hypertension"
        assert item.confidence == 0.5
        assert item.domain == "condition"
        assert item.submitted_by == "dr.smith"
        assert item.reviewed_at is None
        assert item.reviewer_id is None

    def test_get_review_queue_empty(self, service: TerminologyGovernanceService):
        items = service.get_review_queue()
        assert items == []

    def test_get_review_queue_returns_items(self, service: TerminologyGovernanceService):
        _submit_sample(service)
        _submit_sample(service, concept_name="Diabetes", concept_id=201826)

        items = service.get_review_queue()
        assert len(items) == 2

    def test_get_review_queue_filter_by_status(self, service: TerminologyGovernanceService):
        item1 = _submit_sample(service)
        _submit_sample(service, concept_name="Diabetes", concept_id=201826)

        # Approve one
        service.approve_mapping(item1.id, "expert-1", "Looks good")

        pending = service.get_review_queue(status=ReviewStatus.PENDING)
        assert len(pending) == 1
        assert pending[0].concept_name == "Diabetes"

        approved = service.get_review_queue(status=ReviewStatus.APPROVED)
        assert len(approved) == 1
        assert approved[0].id == item1.id

    def test_get_review_queue_filter_by_domain(self, service: TerminologyGovernanceService):
        _submit_sample(service, domain="condition")
        _submit_sample(service, domain="drug", concept_name="Metformin", concept_id=1503297)

        conditions = service.get_review_queue(domain="condition")
        assert len(conditions) == 1
        assert conditions[0].domain == "condition"

        drugs = service.get_review_queue(domain="drug")
        assert len(drugs) == 1
        assert drugs[0].domain == "drug"

    def test_get_review_queue_pagination(self, service: TerminologyGovernanceService):
        for i in range(5):
            _submit_sample(service, concept_name=f"Concept-{i}", concept_id=1000 + i)

        page1 = service.get_review_queue(limit=2, offset=0)
        assert len(page1) == 2

        page2 = service.get_review_queue(limit=2, offset=2)
        assert len(page2) == 2

        page3 = service.get_review_queue(limit=2, offset=4)
        assert len(page3) == 1

    def test_approve_mapping(self, service: TerminologyGovernanceService):
        item = _submit_sample(service)

        result = service.approve_mapping(item.id, "expert-1", "Confirmed correct")
        assert result is not None
        assert result.status == ReviewStatus.APPROVED
        assert result.reviewer_id == "expert-1"
        assert result.notes == "Confirmed correct"
        assert result.reviewed_at is not None

    def test_approve_nonexistent_returns_none(self, service: TerminologyGovernanceService):
        result = service.approve_mapping("nonexistent-id", "expert-1")
        assert result is None

    def test_reject_mapping(self, service: TerminologyGovernanceService):
        item = _submit_sample(service)

        result = service.reject_mapping(
            item.id,
            "expert-1",
            reason="Wrong concept",
            suggested_concept_id=442793,
        )
        assert result is not None
        assert result.status == ReviewStatus.REJECTED
        assert result.reviewer_id == "expert-1"
        assert result.notes == "Wrong concept"
        assert result.suggested_concept_id == 442793
        assert result.reviewed_at is not None

    def test_reject_nonexistent_returns_none(self, service: TerminologyGovernanceService):
        result = service.reject_mapping("nonexistent-id", "expert-1")
        assert result is None

    def test_escalate_mapping(self, service: TerminologyGovernanceService):
        item = _submit_sample(service)

        result = service.escalate_mapping(
            item.id,
            "junior-expert",
            reason="Need senior review for ambiguous mapping",
        )
        assert result is not None
        assert result.status == ReviewStatus.ESCALATED
        assert result.reviewer_id == "junior-expert"
        assert result.notes == "Need senior review for ambiguous mapping"

    def test_escalate_nonexistent_returns_none(self, service: TerminologyGovernanceService):
        result = service.escalate_mapping("nonexistent-id", "expert-1")
        assert result is None

    def test_auto_submit_low_confidence(self, service: TerminologyGovernanceService):
        result = service.auto_submit_if_low_confidence(
            mention_id="m-001",
            candidate_id="c-001",
            concept_name="Asthma",
            concept_id=317009,
            confidence=0.4,
            domain="condition",
        )
        assert result is not None
        assert result.status == ReviewStatus.PENDING
        assert "Auto-submitted" in result.reason
        assert "0.40" in result.reason

    def test_auto_submit_high_confidence_not_submitted(
        self, service: TerminologyGovernanceService
    ):
        result = service.auto_submit_if_low_confidence(
            mention_id="m-001",
            candidate_id="c-001",
            concept_name="Asthma",
            concept_id=317009,
            confidence=0.85,
            domain="condition",
        )
        assert result is None

        # Nothing in the queue
        items = service.get_review_queue()
        assert len(items) == 0

    def test_auto_submit_at_threshold_not_submitted(
        self, service: TerminologyGovernanceService
    ):
        """Confidence exactly at threshold should NOT trigger auto-submit."""
        result = service.auto_submit_if_low_confidence(
            mention_id="m-001",
            candidate_id="c-001",
            concept_name="Asthma",
            concept_id=317009,
            confidence=0.7,
            domain="condition",
        )
        assert result is None

    def test_auto_submit_just_below_threshold(
        self, service: TerminologyGovernanceService
    ):
        """Confidence just below threshold should trigger auto-submit."""
        result = service.auto_submit_if_low_confidence(
            mention_id="m-001",
            candidate_id="c-001",
            concept_name="Asthma",
            concept_id=317009,
            confidence=0.69,
            domain="condition",
        )
        assert result is not None
        assert result.status == ReviewStatus.PENDING

    def test_get_review_stats_empty(self, service: TerminologyGovernanceService):
        stats = service.get_review_stats()
        assert stats.total == 0
        assert stats.pending == 0
        assert stats.approved == 0
        assert stats.rejected == 0
        assert stats.escalated == 0
        assert stats.avg_review_hours == 0.0

    def test_get_review_stats_with_data(self, service: TerminologyGovernanceService):
        item1 = _submit_sample(service, concept_name="Hypertension")
        item2 = _submit_sample(service, concept_name="Diabetes", concept_id=201826)
        item3 = _submit_sample(service, concept_name="Asthma", concept_id=317009)
        _submit_sample(service, concept_name="COPD", concept_id=255573)

        service.approve_mapping(item1.id, "expert-1")
        service.reject_mapping(item2.id, "expert-1", reason="Wrong")
        service.escalate_mapping(item3.id, "expert-2", reason="Ambiguous")

        stats = service.get_review_stats()
        assert stats.total == 4
        assert stats.pending == 1
        assert stats.approved == 1
        assert stats.rejected == 1
        assert stats.escalated == 1

    def test_get_review_by_id(self, service: TerminologyGovernanceService):
        item = _submit_sample(service)

        found = service.get_review_by_id(item.id)
        assert found is not None
        assert found.id == item.id

    def test_get_review_by_id_nonexistent(self, service: TerminologyGovernanceService):
        found = service.get_review_by_id("nonexistent")
        assert found is None

    def test_clear(self, service: TerminologyGovernanceService):
        _submit_sample(service)
        _submit_sample(service)
        assert len(service.get_review_queue()) == 2

        service.clear()
        assert len(service.get_review_queue()) == 0

    def test_singleton_pattern(self):
        svc1 = get_terminology_governance_service()
        svc2 = get_terminology_governance_service()
        assert svc1 is svc2

    def test_reset_singleton(self):
        svc1 = get_terminology_governance_service()
        reset_terminology_governance_service()
        svc2 = get_terminology_governance_service()
        assert svc1 is not svc2


# ============================================================================
# API endpoint tests
# ============================================================================


@pytest.mark.anyio
class TestTerminologyGovernanceAPI:
    """Test the API endpoints via httpx AsyncClient."""

    @pytest.fixture(autouse=True)
    def _setup_service(self):
        """Get a fresh service for API tests."""
        reset_terminology_governance_service()
        self.service = get_terminology_governance_service()
        yield
        reset_terminology_governance_service()

    async def _client(self):
        """Create an async test client."""
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    async def test_get_empty_queue(self):
        async with await self._client() as client:
            resp = await client.get("/api/v1/terminology/review-queue")
            assert resp.status_code == 200
            assert resp.json() == []

    async def test_submit_for_review_endpoint(self):
        async with await self._client() as client:
            resp = await client.post(
                "/api/v1/terminology/review-queue",
                json={
                    "mention_id": "m-001",
                    "candidate_id": "c-001",
                    "reason": "Low confidence",
                    "submitted_by": "dr.smith",
                },
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["status"] == "pending"
            assert data["submitted_by"] == "dr.smith"

    async def test_approve_mapping_endpoint(self):
        # Submit via service
        item = _submit_sample(self.service)

        async with await self._client() as client:
            resp = await client.put(
                f"/api/v1/terminology/review-queue/{item.id}/approve",
                json={
                    "reviewer_id": "expert-1",
                    "notes": "Confirmed correct",
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "approved"
            assert data["reviewer_id"] == "expert-1"

    async def test_reject_mapping_endpoint(self):
        item = _submit_sample(self.service)

        async with await self._client() as client:
            resp = await client.put(
                f"/api/v1/terminology/review-queue/{item.id}/reject",
                json={
                    "reviewer_id": "expert-1",
                    "notes": "Wrong concept",
                    "suggested_concept_id": 442793,
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "rejected"
            assert data["suggested_concept_id"] == 442793

    async def test_escalate_mapping_endpoint(self):
        item = _submit_sample(self.service)

        async with await self._client() as client:
            resp = await client.put(
                f"/api/v1/terminology/review-queue/{item.id}/escalate",
                json={
                    "reviewer_id": "junior-expert",
                    "notes": "Needs senior review",
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "escalated"

    async def test_approve_nonexistent_returns_404(self):
        async with await self._client() as client:
            resp = await client.put(
                "/api/v1/terminology/review-queue/nonexistent/approve",
                json={"reviewer_id": "expert-1", "notes": ""},
            )
            assert resp.status_code == 404

    async def test_reject_nonexistent_returns_404(self):
        async with await self._client() as client:
            resp = await client.put(
                "/api/v1/terminology/review-queue/nonexistent/reject",
                json={"reviewer_id": "expert-1", "notes": ""},
            )
            assert resp.status_code == 404

    async def test_get_review_stats_endpoint(self):
        _submit_sample(self.service, concept_name="Hypertension")
        item2 = _submit_sample(self.service, concept_name="Diabetes", concept_id=201826)
        self.service.approve_mapping(item2.id, "expert-1")

        async with await self._client() as client:
            resp = await client.get("/api/v1/terminology/review-queue/stats")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 2
            assert data["pending"] == 1
            assert data["approved"] == 1

    async def test_get_queue_filter_by_status(self):
        item1 = _submit_sample(self.service, concept_name="Hypertension")
        _submit_sample(self.service, concept_name="Diabetes", concept_id=201826)
        self.service.approve_mapping(item1.id, "expert-1")

        async with await self._client() as client:
            resp = await client.get(
                "/api/v1/terminology/review-queue",
                params={"status": "pending"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["status"] == "pending"

    async def test_get_queue_filter_by_domain(self):
        _submit_sample(self.service, domain="condition")
        _submit_sample(
            self.service, domain="drug", concept_name="Metformin", concept_id=1503297
        )

        async with await self._client() as client:
            resp = await client.get(
                "/api/v1/terminology/review-queue",
                params={"domain": "drug"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["domain"] == "drug"
