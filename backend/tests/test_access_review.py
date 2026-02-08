"""Tests for Access Review & Certification Management (CISO-11).

Covers:
- Seed data verification (25 entitlements, 3 cycles, 14 decisions, 8 users)
- Review cycle CRUD (create, read, update, delete, list with filters)
- Cycle lifecycle transitions (start, complete, invalid transitions)
- Entitlement CRUD (create, read, delete, list with filters)
- Review decision submission with side-effects (certify, revoke, modify, escalate)
- Pending review tracking per cycle
- Excessive access detection (ADMIN threshold, unused access threshold)
- Access review metrics calculation
- Overdue cycle detection
- API endpoint integration tests (17 endpoints)
- Error handling (404 for unknown IDs, 400 for invalid transitions)
- Edge cases (empty filters, combined filters, decision after revoke)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.access_review import (
    AccessEntitlement,
    AccessLevel,
    AccessReviewMetrics,
    CycleStatus,
    CycleType,
    DecisionListResponse,
    DecisionSubmitRequest,
    EntitlementCreateRequest,
    EntitlementListResponse,
    ExcessiveAccessResponse,
    ReviewCycle,
    ReviewCycleCreateRequest,
    ReviewCycleListResponse,
    ReviewCycleUpdateRequest,
    ReviewDecision,
    ReviewDecisionType,
)
from app.services.access_review_service import (
    ADMIN_RESOURCE_THRESHOLD,
    UNUSED_DAYS_THRESHOLD,
    AccessReviewService,
    get_access_review_service,
    reset_access_review_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_PREFIX = "/api/v1/access-review"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton between tests."""
    reset_access_review_service()
    yield
    reset_access_review_service()


@pytest.fixture
def svc() -> AccessReviewService:
    """Fresh service instance via singleton."""
    return get_access_review_service()


def _make_cycle_create(**overrides) -> ReviewCycleCreateRequest:
    """Helper to build a ReviewCycleCreateRequest with defaults."""
    now = datetime.now(timezone.utc)
    defaults = dict(
        name="Test Quarterly Review",
        cycle_type=CycleType.QUARTERLY,
        start_date=now + timedelta(days=1),
        end_date=now + timedelta(days=31),
        reviewer="Test Reviewer",
    )
    defaults.update(overrides)
    return ReviewCycleCreateRequest(**defaults)


def _make_entitlement_create(**overrides) -> EntitlementCreateRequest:
    """Helper to build an EntitlementCreateRequest with defaults."""
    defaults = dict(
        user_id="USR-TEST",
        user_name="Test User",
        user_role="tester",
        resource="test_resource",
        access_level=AccessLevel.READ,
        granted_by="Admin",
        justification="Testing purposes",
    )
    defaults.update(overrides)
    return EntitlementCreateRequest(**defaults)


def _make_decision_submit(**overrides) -> DecisionSubmitRequest:
    """Helper to build a DecisionSubmitRequest with defaults."""
    defaults = dict(
        entitlement_id="ENT-001",
        decision=ReviewDecisionType.CERTIFY,
        reviewer="Test Reviewer",
        comments="Looks good",
    )
    defaults.update(overrides)
    return DecisionSubmitRequest(**defaults)


# ===========================================================================
# 1. Seed Data Verification
# ===========================================================================


class TestSeedData:
    """Verify pre-populated seed data."""

    def test_seed_entitlement_count(self, svc: AccessReviewService):
        ents = svc.list_entitlements()
        assert len(ents) == 25

    def test_seed_cycle_count(self, svc: AccessReviewService):
        cycles = svc.list_cycles()
        assert len(cycles) == 3

    def test_seed_decision_count(self, svc: AccessReviewService):
        decisions = svc.list_decisions()
        assert len(decisions) == 14

    def test_seed_cycle_ids(self, svc: AccessReviewService):
        cycles = svc.list_cycles()
        ids = {c.id for c in cycles}
        assert ids == {"CYC-001", "CYC-002", "CYC-003"}

    def test_seed_completed_cycles(self, svc: AccessReviewService):
        completed = svc.list_cycles(status=CycleStatus.COMPLETED)
        assert len(completed) == 2

    def test_seed_in_progress_cycle(self, svc: AccessReviewService):
        in_progress = svc.list_cycles(status=CycleStatus.IN_PROGRESS)
        assert len(in_progress) == 1
        assert in_progress[0].id == "CYC-003"

    def test_seed_cycle_types(self, svc: AccessReviewService):
        for c in svc.list_cycles():
            assert c.cycle_type == CycleType.QUARTERLY

    def test_seed_user_count(self, svc: AccessReviewService):
        ents = svc.list_entitlements()
        user_ids = {e.user_id for e in ents}
        assert len(user_ids) == 8

    def test_seed_entitlement_roles(self, svc: AccessReviewService):
        ents = svc.list_entitlements()
        roles = {e.user_role for e in ents}
        expected_roles = {"clinician", "admin", "data_analyst", "developer", "auditor", "operations"}
        assert roles == expected_roles

    def test_seed_first_entitlement(self, svc: AccessReviewService):
        ent = svc.get_entitlement("ENT-001")
        assert ent is not None
        assert ent.user_id == "USR-001"
        assert ent.user_name == "Dr. Sarah Chen"
        assert ent.user_role == "clinician"
        assert ent.resource == "patient_records"
        assert ent.access_level == AccessLevel.WRITE

    def test_seed_admin_entitlements(self, svc: AccessReviewService):
        admin_ents = svc.list_entitlements(access_level=AccessLevel.ADMIN)
        assert len(admin_ents) >= 6  # Multiple admins

    def test_seed_decisions_by_cycle(self, svc: AccessReviewService):
        cyc1_decs = svc.list_decisions(cycle_id="CYC-001")
        cyc2_decs = svc.list_decisions(cycle_id="CYC-002")
        assert len(cyc1_decs) == 7
        assert len(cyc2_decs) == 7


# ===========================================================================
# 2. Review Cycle CRUD
# ===========================================================================


class TestCycleCRUD:
    """Test review cycle create, read, update, delete."""

    def test_create_cycle(self, svc: AccessReviewService):
        req = _make_cycle_create()
        cycle = svc.create_cycle(req)
        assert cycle.name == "Test Quarterly Review"
        assert cycle.cycle_type == CycleType.QUARTERLY
        assert cycle.status == CycleStatus.PLANNED
        assert cycle.reviewer == "Test Reviewer"

    def test_create_cycle_generates_id(self, svc: AccessReviewService):
        req = _make_cycle_create()
        cycle = svc.create_cycle(req)
        assert cycle.id.startswith("CYC-")
        assert len(cycle.id) > 4

    def test_get_cycle(self, svc: AccessReviewService):
        cycle = svc.get_cycle("CYC-001")
        assert cycle is not None
        assert cycle.name == "Q3 2025 Quarterly Access Review"

    def test_get_cycle_not_found(self, svc: AccessReviewService):
        result = svc.get_cycle("CYC-NONEXISTENT")
        assert result is None

    def test_update_cycle_name(self, svc: AccessReviewService):
        req = ReviewCycleUpdateRequest(name="Updated Name")
        updated = svc.update_cycle("CYC-001", req)
        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.status == CycleStatus.COMPLETED  # unchanged

    def test_update_cycle_status(self, svc: AccessReviewService):
        req = ReviewCycleUpdateRequest(status=CycleStatus.OVERDUE)
        updated = svc.update_cycle("CYC-003", req)
        assert updated is not None
        assert updated.status == CycleStatus.OVERDUE

    def test_update_cycle_not_found(self, svc: AccessReviewService):
        req = ReviewCycleUpdateRequest(name="Nothing")
        assert svc.update_cycle("CYC-FAKE", req) is None

    def test_delete_cycle(self, svc: AccessReviewService):
        # CYC-001 has 7 decisions
        initial_decisions = len(svc.list_decisions())
        assert svc.delete_cycle("CYC-001") is True
        assert svc.get_cycle("CYC-001") is None
        # Decisions for CYC-001 should be removed
        assert len(svc.list_decisions()) == initial_decisions - 7

    def test_delete_cycle_not_found(self, svc: AccessReviewService):
        assert svc.delete_cycle("CYC-FAKE") is False

    def test_list_cycles_no_filter(self, svc: AccessReviewService):
        cycles = svc.list_cycles()
        assert len(cycles) == 3

    def test_list_cycles_by_type(self, svc: AccessReviewService):
        cycles = svc.list_cycles(cycle_type=CycleType.QUARTERLY)
        assert len(cycles) == 3
        cycles = svc.list_cycles(cycle_type=CycleType.ANNUAL)
        assert len(cycles) == 0

    def test_list_cycles_by_status(self, svc: AccessReviewService):
        cycles = svc.list_cycles(status=CycleStatus.COMPLETED)
        assert len(cycles) == 2

    def test_list_cycles_sorted_by_start_date_desc(self, svc: AccessReviewService):
        cycles = svc.list_cycles()
        for i in range(len(cycles) - 1):
            assert cycles[i].start_date >= cycles[i + 1].start_date


# ===========================================================================
# 3. Cycle Lifecycle Transitions
# ===========================================================================


class TestCycleLifecycle:
    """Test cycle start/complete transitions."""

    def test_start_planned_cycle(self, svc: AccessReviewService):
        req = _make_cycle_create()
        cycle = svc.create_cycle(req)
        started = svc.start_cycle(cycle.id)
        assert started is not None
        assert started.status == CycleStatus.IN_PROGRESS

    def test_start_non_planned_cycle_fails(self, svc: AccessReviewService):
        # CYC-003 is IN_PROGRESS
        result = svc.start_cycle("CYC-003")
        assert result is None

    def test_start_completed_cycle_fails(self, svc: AccessReviewService):
        result = svc.start_cycle("CYC-001")
        assert result is None

    def test_start_nonexistent_cycle_fails(self, svc: AccessReviewService):
        result = svc.start_cycle("CYC-FAKE")
        assert result is None

    def test_complete_in_progress_cycle(self, svc: AccessReviewService):
        completed = svc.complete_cycle("CYC-003")
        assert completed is not None
        assert completed.status == CycleStatus.COMPLETED

    def test_complete_planned_cycle_fails(self, svc: AccessReviewService):
        req = _make_cycle_create()
        cycle = svc.create_cycle(req)
        result = svc.complete_cycle(cycle.id)
        assert result is None

    def test_complete_already_completed_fails(self, svc: AccessReviewService):
        result = svc.complete_cycle("CYC-001")
        assert result is None

    def test_complete_nonexistent_cycle_fails(self, svc: AccessReviewService):
        result = svc.complete_cycle("CYC-FAKE")
        assert result is None

    def test_full_lifecycle(self, svc: AccessReviewService):
        req = _make_cycle_create()
        cycle = svc.create_cycle(req)
        assert cycle.status == CycleStatus.PLANNED

        started = svc.start_cycle(cycle.id)
        assert started is not None
        assert started.status == CycleStatus.IN_PROGRESS

        completed = svc.complete_cycle(cycle.id)
        assert completed is not None
        assert completed.status == CycleStatus.COMPLETED


# ===========================================================================
# 4. Entitlement CRUD
# ===========================================================================


class TestEntitlementCRUD:
    """Test entitlement create, read, delete, list with filters."""

    def test_create_entitlement(self, svc: AccessReviewService):
        req = _make_entitlement_create()
        ent = svc.create_entitlement(req)
        assert ent.user_id == "USR-TEST"
        assert ent.resource == "test_resource"
        assert ent.access_level == AccessLevel.READ
        assert ent.last_used is None

    def test_create_entitlement_generates_id(self, svc: AccessReviewService):
        req = _make_entitlement_create()
        ent = svc.create_entitlement(req)
        assert ent.id.startswith("ENT-")

    def test_get_entitlement(self, svc: AccessReviewService):
        ent = svc.get_entitlement("ENT-001")
        assert ent is not None
        assert ent.user_name == "Dr. Sarah Chen"

    def test_get_entitlement_not_found(self, svc: AccessReviewService):
        assert svc.get_entitlement("ENT-FAKE") is None

    def test_delete_entitlement(self, svc: AccessReviewService):
        initial = len(svc.list_entitlements())
        assert svc.delete_entitlement("ENT-001") is True
        assert len(svc.list_entitlements()) == initial - 1
        assert svc.get_entitlement("ENT-001") is None

    def test_delete_entitlement_not_found(self, svc: AccessReviewService):
        assert svc.delete_entitlement("ENT-FAKE") is False

    def test_list_entitlements_no_filter(self, svc: AccessReviewService):
        ents = svc.list_entitlements()
        assert len(ents) == 25

    def test_list_entitlements_by_user(self, svc: AccessReviewService):
        ents = svc.list_entitlements(user_id="USR-001")
        assert len(ents) == 3
        for e in ents:
            assert e.user_id == "USR-001"

    def test_list_entitlements_by_resource(self, svc: AccessReviewService):
        ents = svc.list_entitlements(resource="patient_records")
        assert len(ents) >= 3

    def test_list_entitlements_by_access_level(self, svc: AccessReviewService):
        ents = svc.list_entitlements(access_level=AccessLevel.OWNER)
        assert len(ents) == 0  # No OWNER in seed data

    def test_list_entitlements_combined_filters(self, svc: AccessReviewService):
        ents = svc.list_entitlements(user_id="USR-002", access_level=AccessLevel.ADMIN)
        assert len(ents) >= 3
        for e in ents:
            assert e.user_id == "USR-002"
            assert e.access_level == AccessLevel.ADMIN


# ===========================================================================
# 5. Review Decision Submission
# ===========================================================================


class TestDecisionSubmission:
    """Test decision submission and side-effects."""

    def test_submit_certify_decision(self, svc: AccessReviewService):
        req = _make_decision_submit(
            entitlement_id="ENT-001",
            decision=ReviewDecisionType.CERTIFY,
        )
        dec = svc.submit_decision("CYC-003", req)
        assert dec is not None
        assert dec.decision == ReviewDecisionType.CERTIFY
        assert dec.cycle_id == "CYC-003"
        # Entitlement should still exist
        assert svc.get_entitlement("ENT-001") is not None

    def test_submit_revoke_deletes_entitlement(self, svc: AccessReviewService):
        req = _make_decision_submit(
            entitlement_id="ENT-003",
            decision=ReviewDecisionType.REVOKE,
            comments="No longer needed",
        )
        dec = svc.submit_decision("CYC-003", req)
        assert dec is not None
        assert dec.decision == ReviewDecisionType.REVOKE
        # Entitlement should be deleted
        assert svc.get_entitlement("ENT-003") is None

    def test_submit_modify_changes_access_level(self, svc: AccessReviewService):
        # ENT-004 is ADMIN, modify to READ
        req = _make_decision_submit(
            entitlement_id="ENT-004",
            decision=ReviewDecisionType.MODIFY,
            new_access_level=AccessLevel.READ,
            comments="Reduced access",
        )
        dec = svc.submit_decision("CYC-003", req)
        assert dec is not None
        assert dec.decision == ReviewDecisionType.MODIFY
        assert dec.new_access_level == AccessLevel.READ
        ent = svc.get_entitlement("ENT-004")
        assert ent is not None
        assert ent.access_level == AccessLevel.READ

    def test_submit_escalate_decision(self, svc: AccessReviewService):
        req = _make_decision_submit(
            entitlement_id="ENT-005",
            decision=ReviewDecisionType.ESCALATE,
            comments="Needs VP approval",
        )
        dec = svc.submit_decision("CYC-003", req)
        assert dec is not None
        assert dec.decision == ReviewDecisionType.ESCALATE

    def test_submit_decision_invalid_cycle(self, svc: AccessReviewService):
        req = _make_decision_submit()
        assert svc.submit_decision("CYC-FAKE", req) is None

    def test_submit_decision_invalid_entitlement(self, svc: AccessReviewService):
        req = _make_decision_submit(entitlement_id="ENT-FAKE")
        assert svc.submit_decision("CYC-003", req) is None

    def test_list_decisions_no_filter(self, svc: AccessReviewService):
        decs = svc.list_decisions()
        assert len(decs) == 14

    def test_list_decisions_by_cycle(self, svc: AccessReviewService):
        decs = svc.list_decisions(cycle_id="CYC-001")
        assert len(decs) == 7
        for d in decs:
            assert d.cycle_id == "CYC-001"

    def test_list_decisions_by_type(self, svc: AccessReviewService):
        decs = svc.list_decisions(decision_type=ReviewDecisionType.CERTIFY)
        certify_count = len(decs)
        assert certify_count >= 5
        for d in decs:
            assert d.decision == ReviewDecisionType.CERTIFY

    def test_list_decisions_sorted_desc(self, svc: AccessReviewService):
        decs = svc.list_decisions()
        for i in range(len(decs) - 1):
            assert decs[i].decided_at >= decs[i + 1].decided_at


# ===========================================================================
# 6. Pending Reviews
# ===========================================================================


class TestPendingReviews:
    """Test pending review tracking per cycle."""

    def test_pending_reviews_for_new_cycle(self, svc: AccessReviewService):
        req = _make_cycle_create()
        cycle = svc.create_cycle(req)
        pending = svc.get_pending_reviews(cycle.id)
        assert pending is not None
        # All entitlements should be pending for a brand new cycle
        assert len(pending) == 25

    def test_pending_reviews_for_completed_cycle(self, svc: AccessReviewService):
        pending = svc.get_pending_reviews("CYC-001")
        assert pending is not None
        # 7 decisions were made, so 25 - 7 = 18 pending (some may be revoked)
        total_ents = len(svc.list_entitlements())
        reviewed = len(svc.list_decisions(cycle_id="CYC-001"))
        assert len(pending) == total_ents - reviewed

    def test_pending_reviews_invalid_cycle(self, svc: AccessReviewService):
        assert svc.get_pending_reviews("CYC-FAKE") is None

    def test_pending_decreases_after_decision(self, svc: AccessReviewService):
        pending_before = svc.get_pending_reviews("CYC-003")
        assert pending_before is not None
        count_before = len(pending_before)

        req = _make_decision_submit(entitlement_id="ENT-001")
        svc.submit_decision("CYC-003", req)

        pending_after = svc.get_pending_reviews("CYC-003")
        assert pending_after is not None
        assert len(pending_after) == count_before - 1


# ===========================================================================
# 7. Excessive Access Detection
# ===========================================================================


class TestExcessiveAccess:
    """Test excessive access detection logic."""

    def test_detect_excessive_access_returns_results(self, svc: AccessReviewService):
        result = svc.detect_excessive_access()
        assert result.total > 0

    def test_admin_threshold_flagged(self, svc: AccessReviewService):
        result = svc.detect_excessive_access()
        # USR-002 (James Rodriguez) has 4 ADMIN entitlements, USR-008 (Alex Turner) has 4
        flagged_ids = {e.user_id for e in result.items}
        assert "USR-002" in flagged_ids
        assert "USR-008" in flagged_ids

    def test_unused_access_flagged(self, svc: AccessReviewService):
        result = svc.detect_excessive_access()
        flagged_ids = {e.user_id for e in result.items}
        # USR-005 (Lisa Thompson) has ENT-016 unused 120 days
        # USR-006 (David Kim) has access unused 200 and 150 days
        assert "USR-006" in flagged_ids

    def test_excessive_access_reasons_populated(self, svc: AccessReviewService):
        result = svc.detect_excessive_access()
        for entry in result.items:
            assert len(entry.reasons) > 0
            assert len(entry.entitlements) > 0

    def test_clean_user_not_flagged(self, svc: AccessReviewService):
        result = svc.detect_excessive_access()
        flagged_ids = {e.user_id for e in result.items}
        # USR-007 (Rachel Green) has only READ/WRITE, recent usage
        assert "USR-007" not in flagged_ids

    def test_admin_threshold_constant(self):
        assert ADMIN_RESOURCE_THRESHOLD == 3

    def test_unused_threshold_constant(self):
        assert UNUSED_DAYS_THRESHOLD == 90


# ===========================================================================
# 8. Metrics
# ===========================================================================


class TestMetrics:
    """Test access review metrics calculation."""

    def test_metrics_total_cycles(self, svc: AccessReviewService):
        metrics = svc.get_metrics()
        assert metrics.total_cycles == 3

    def test_metrics_total_entitlements(self, svc: AccessReviewService):
        metrics = svc.get_metrics()
        assert metrics.total_entitlements == 25

    def test_metrics_certification_rate(self, svc: AccessReviewService):
        metrics = svc.get_metrics()
        assert 0 <= metrics.certification_rate <= 100
        # Most seed decisions are CERTIFY
        assert metrics.certification_rate > 40

    def test_metrics_revocation_rate(self, svc: AccessReviewService):
        metrics = svc.get_metrics()
        assert 0 <= metrics.revocation_rate <= 100
        assert metrics.revocation_rate > 0  # Some revocations exist

    def test_metrics_avg_review_time(self, svc: AccessReviewService):
        metrics = svc.get_metrics()
        assert metrics.avg_review_time_days > 0

    def test_metrics_by_decision(self, svc: AccessReviewService):
        metrics = svc.get_metrics()
        assert len(metrics.by_decision) > 0
        assert "CERTIFY" in metrics.by_decision
        total = sum(metrics.by_decision.values())
        assert total == 14  # Total seed decisions

    def test_metrics_excessive_access_count(self, svc: AccessReviewService):
        metrics = svc.get_metrics()
        assert metrics.excessive_access_count > 0


# ===========================================================================
# 9. Overdue Cycles
# ===========================================================================


class TestOverdueCycles:
    """Test overdue cycle detection."""

    def test_no_overdue_in_seed_data(self, svc: AccessReviewService):
        # CYC-003 is IN_PROGRESS and end_date is in the future
        overdue = svc.get_overdue_cycles()
        assert len(overdue) == 0

    def test_overdue_status_detected(self, svc: AccessReviewService):
        req = ReviewCycleUpdateRequest(status=CycleStatus.OVERDUE)
        svc.update_cycle("CYC-003", req)
        overdue = svc.get_overdue_cycles()
        assert len(overdue) == 1
        assert overdue[0].id == "CYC-003"

    def test_in_progress_past_end_date_detected(self, svc: AccessReviewService):
        # Create a cycle with past end date
        now = datetime.now(timezone.utc)
        req = _make_cycle_create(
            start_date=now - timedelta(days=60),
            end_date=now - timedelta(days=10),
        )
        cycle = svc.create_cycle(req)
        # Start it (moves to IN_PROGRESS)
        svc.start_cycle(cycle.id)
        overdue = svc.get_overdue_cycles()
        assert len(overdue) == 1


# ===========================================================================
# 10. Service Stats
# ===========================================================================


class TestServiceStats:
    """Test service health/stats method."""

    def test_get_stats(self, svc: AccessReviewService):
        stats = svc.get_stats()
        assert stats["cycles"] == 3
        assert stats["entitlements"] == 25
        assert stats["decisions"] == 14


# ===========================================================================
# 11. API Endpoint Integration Tests
# ===========================================================================


@pytest.mark.anyio
class TestAPIEndpoints:
    """Integration tests for all access review API endpoints."""

    async def test_list_cycles(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/cycles")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == 3

    async def test_list_cycles_filter_by_status(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/cycles", params={"status": "COMPLETED"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    async def test_create_cycle(self):
        now = datetime.now(timezone.utc)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/cycles",
                json={
                    "name": "API Test Cycle",
                    "cycle_type": "QUARTERLY",
                    "start_date": now.isoformat(),
                    "end_date": (now + timedelta(days=30)).isoformat(),
                    "reviewer": "API Tester",
                },
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "API Test Cycle"
        assert data["status"] == "PLANNED"

    async def test_get_cycle(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/cycles/CYC-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "CYC-001"

    async def test_get_cycle_not_found(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/cycles/CYC-NONEXISTENT")
        assert resp.status_code == 404

    async def test_update_cycle(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                f"{API_PREFIX}/cycles/CYC-003",
                json={"name": "Updated Cycle Name"},
            )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Cycle Name"

    async def test_delete_cycle(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(f"{API_PREFIX}/cycles/CYC-001")
        assert resp.status_code == 204

    async def test_delete_cycle_not_found(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(f"{API_PREFIX}/cycles/CYC-FAKE")
        assert resp.status_code == 404

    async def test_start_cycle(self):
        # First create a PLANNED cycle, then start it
        now = datetime.now(timezone.utc)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            create_resp = await client.post(
                f"{API_PREFIX}/cycles",
                json={
                    "name": "Startable Cycle",
                    "cycle_type": "ANNUAL",
                    "start_date": now.isoformat(),
                    "end_date": (now + timedelta(days=90)).isoformat(),
                    "reviewer": "Tester",
                },
            )
            cycle_id = create_resp.json()["id"]
            resp = await client.post(f"{API_PREFIX}/cycles/{cycle_id}/start")
        assert resp.status_code == 200
        assert resp.json()["status"] == "IN_PROGRESS"

    async def test_start_cycle_invalid(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(f"{API_PREFIX}/cycles/CYC-003/start")
        assert resp.status_code == 400

    async def test_complete_cycle(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(f"{API_PREFIX}/cycles/CYC-003/complete")
        assert resp.status_code == 200
        assert resp.json()["status"] == "COMPLETED"

    async def test_complete_cycle_invalid(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(f"{API_PREFIX}/cycles/CYC-001/complete")
        assert resp.status_code == 400

    async def test_get_pending_reviews(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/cycles/CYC-003/pending")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] == 25  # No decisions yet in CYC-003

    async def test_get_pending_reviews_not_found(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/cycles/CYC-FAKE/pending")
        assert resp.status_code == 404

    async def test_submit_decision(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/cycles/CYC-003/decisions",
                json={
                    "entitlement_id": "ENT-001",
                    "decision": "CERTIFY",
                    "reviewer": "API Tester",
                    "comments": "Looks good",
                },
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["decision"] == "CERTIFY"
        assert data["cycle_id"] == "CYC-003"

    async def test_submit_decision_not_found(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/cycles/CYC-FAKE/decisions",
                json={
                    "entitlement_id": "ENT-001",
                    "decision": "CERTIFY",
                    "reviewer": "Tester",
                },
            )
        assert resp.status_code == 404

    async def test_list_entitlements(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/entitlements")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 25

    async def test_list_entitlements_filter_by_user(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"{API_PREFIX}/entitlements", params={"user_id": "USR-001"}
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    async def test_create_entitlement(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/entitlements",
                json={
                    "user_id": "USR-NEW",
                    "user_name": "New User",
                    "user_role": "viewer",
                    "resource": "reports",
                    "access_level": "READ",
                    "granted_by": "Admin",
                    "justification": "Needs reports access",
                },
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["user_id"] == "USR-NEW"
        assert data["access_level"] == "READ"

    async def test_get_entitlement(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/entitlements/ENT-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "ENT-001"

    async def test_get_entitlement_not_found(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/entitlements/ENT-FAKE")
        assert resp.status_code == 404

    async def test_delete_entitlement(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(f"{API_PREFIX}/entitlements/ENT-001")
        assert resp.status_code == 204

    async def test_delete_entitlement_not_found(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(f"{API_PREFIX}/entitlements/ENT-FAKE")
        assert resp.status_code == 404

    async def test_list_decisions(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/decisions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 14

    async def test_list_decisions_filter_by_cycle(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"{API_PREFIX}/decisions", params={"cycle_id": "CYC-001"}
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 7

    async def test_detect_excessive_access(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/excessive-access")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        assert len(data["items"]) > 0

    async def test_get_metrics(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cycles"] == 3
        assert data["total_entitlements"] == 25
        assert "certification_rate" in data
        assert "by_decision" in data

    async def test_get_overdue_cycles(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/overdue")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
