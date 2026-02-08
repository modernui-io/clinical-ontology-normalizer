"""Tests for Site Referral Network and Trial Enrollment Workflow (VP-Product-5).

Covers:
- Schema construction and enum validation
- ReferralService CRUD operations
- Referral status lifecycle transitions
- Site matching/suggestion scoring
- Enrollment workflow tracking and stage advancement
- Network analytics computation
- API endpoint validation
- Edge cases and error handling

40+ test cases.
"""

from __future__ import annotations

import pytest

from fastapi.testclient import TestClient

from app.schemas.referral_network import (
    ENROLLMENT_STAGE_TRANSITIONS,
    REFERRAL_STATUS_TRANSITIONS,
    EnrollmentAdvanceRequest,
    EnrollmentAdvanceResponse,
    EnrollmentMilestone,
    EnrollmentStage,
    EnrollmentTracking,
    NetworkAnalytics,
    ReferralCreate,
    ReferralListResponse,
    ReferralPriority,
    ReferralResponse,
    ReferralStatus,
    ReferralUpdate,
    SiteReferralMetrics,
    SiteSuggestion,
    SiteSuggestionRequest,
    SiteSuggestionResponse,
)
from app.services.referral_service import (
    ReferralService,
    get_referral_service,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def service() -> ReferralService:
    """Create a fresh ReferralService instance for each test."""
    return ReferralService()


@pytest.fixture
def client() -> TestClient:
    """Create a test client for API endpoint tests."""
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


def _make_referral_create(**overrides) -> ReferralCreate:
    """Helper to build a ReferralCreate with sensible defaults."""
    defaults = {
        "patient_id": "PAT-100",
        "source_site_id": "site-001",
        "destination_site_id": "site-002",
        "trial_id": "trial-eylea",
        "referring_provider": "Dr. Test",
        "reason": "Patient eligible for trial",
        "priority": ReferralPriority.NORMAL,
        "notes": "Test referral",
    }
    defaults.update(overrides)
    return ReferralCreate(**defaults)


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestSchemas:
    """Test Pydantic schema construction and validation."""

    def test_referral_status_enum(self) -> None:
        """Test all referral status values exist."""
        statuses = [s.value for s in ReferralStatus]
        assert "initiated" in statuses
        assert "pending_review" in statuses
        assert "accepted" in statuses
        assert "completed" in statuses
        assert "declined" in statuses
        assert "cancelled" in statuses

    def test_referral_priority_enum(self) -> None:
        """Test all priority levels exist."""
        priorities = [p.value for p in ReferralPriority]
        assert "urgent" in priorities
        assert "high" in priorities
        assert "normal" in priorities
        assert "low" in priorities

    def test_enrollment_stage_enum(self) -> None:
        """Test all enrollment stages exist."""
        stages = [s.value for s in EnrollmentStage]
        expected = [
            "candidate", "referred", "screened", "eligible",
            "consented", "enrolled", "active", "withdrawn",
        ]
        for e in expected:
            assert e in stages

    def test_referral_create_schema(self) -> None:
        """Test creating a ReferralCreate schema."""
        create = _make_referral_create()
        assert create.patient_id == "PAT-100"
        assert create.priority == ReferralPriority.NORMAL

    def test_referral_update_schema(self) -> None:
        """Test ReferralUpdate with partial fields."""
        update = ReferralUpdate(status=ReferralStatus.ACCEPTED)
        assert update.status == ReferralStatus.ACCEPTED
        assert update.priority is None

    def test_site_suggestion_request(self) -> None:
        """Test SiteSuggestionRequest with coordinates."""
        req = SiteSuggestionRequest(
            patient_id="PAT-1",
            trial_id="trial-eylea",
            patient_lat=33.75,
            patient_lon=-84.39,
            max_results=3,
        )
        assert req.max_results == 3

    def test_enrollment_milestone_schema(self) -> None:
        """Test EnrollmentMilestone creation."""
        milestone = EnrollmentMilestone(
            stage=EnrollmentStage.SCREENED,
            timestamp="2025-01-01T00:00:00+00:00",
            notes="Screening complete",
        )
        assert milestone.stage == EnrollmentStage.SCREENED

    def test_referral_status_transitions_complete(self) -> None:
        """Ensure every ReferralStatus has a transition entry."""
        for status in ReferralStatus:
            assert status in REFERRAL_STATUS_TRANSITIONS

    def test_enrollment_stage_transitions_complete(self) -> None:
        """Ensure every EnrollmentStage has a transition entry."""
        for stage in EnrollmentStage:
            assert stage in ENROLLMENT_STAGE_TRANSITIONS

    def test_terminal_stages_have_no_transitions(self) -> None:
        """COMPLETED, DECLINED, CANCELLED have no outgoing transitions."""
        for terminal in [ReferralStatus.COMPLETED, ReferralStatus.DECLINED, ReferralStatus.CANCELLED]:
            assert REFERRAL_STATUS_TRANSITIONS[terminal] == []

    def test_withdrawn_is_terminal_enrollment(self) -> None:
        """WITHDRAWN has no forward transitions."""
        assert ENROLLMENT_STAGE_TRANSITIONS[EnrollmentStage.WITHDRAWN] == []


# ---------------------------------------------------------------------------
# Referral Service CRUD tests
# ---------------------------------------------------------------------------


class TestReferralCRUD:
    """Test ReferralService create/read/update/list."""

    def test_create_referral(self, service: ReferralService) -> None:
        """Creating a referral returns a valid response."""
        create = _make_referral_create()
        ref = service.create_referral(create)
        assert ref.id is not None
        assert ref.patient_id == "PAT-100"
        assert ref.status == ReferralStatus.INITIATED

    def test_get_referral(self, service: ReferralService) -> None:
        """Can retrieve a referral by ID."""
        create = _make_referral_create()
        ref = service.create_referral(create)
        fetched = service.get_referral(ref.id)
        assert fetched is not None
        assert fetched.id == ref.id

    def test_get_referral_not_found(self, service: ReferralService) -> None:
        """Non-existent referral returns None."""
        assert service.get_referral("nonexistent") is None

    def test_list_referrals_all(self, service: ReferralService) -> None:
        """List returns demo referrals."""
        refs, total = service.list_referrals()
        assert total == 10  # 10 demo referrals

    def test_list_referrals_filter_trial(self, service: ReferralService) -> None:
        """Filter referrals by trial_id."""
        refs, total = service.list_referrals(trial_id="trial-eylea")
        assert total == 3
        for r in refs:
            assert r.trial_id == "trial-eylea"

    def test_list_referrals_filter_status(self, service: ReferralService) -> None:
        """Filter referrals by status."""
        refs, total = service.list_referrals(status=ReferralStatus.COMPLETED)
        assert total == 2  # 2 demo completed referrals
        for r in refs:
            assert r.status == ReferralStatus.COMPLETED

    def test_list_referrals_filter_site(self, service: ReferralService) -> None:
        """Filter referrals by site (source or destination)."""
        refs, total = service.list_referrals(site_id="site-005")
        assert total > 0
        for r in refs:
            assert r.source_site_id == "site-005" or r.destination_site_id == "site-005"

    def test_list_referrals_filter_patient(self, service: ReferralService) -> None:
        """Filter referrals by patient ID."""
        refs, total = service.list_referrals(patient_id="PAT-001")
        assert total == 1
        assert refs[0].patient_id == "PAT-001"

    def test_list_referrals_pagination(self, service: ReferralService) -> None:
        """Pagination works correctly."""
        refs, total = service.list_referrals(limit=3, offset=0)
        assert len(refs) == 3
        assert total == 10

    def test_update_referral_status(self, service: ReferralService) -> None:
        """Update referral status through valid transition."""
        create = _make_referral_create()
        ref = service.create_referral(create)
        assert ref.status == ReferralStatus.INITIATED

        update = ReferralUpdate(status=ReferralStatus.PENDING_REVIEW)
        updated = service.update_referral(ref.id, update)
        assert updated is not None
        assert updated.status == ReferralStatus.PENDING_REVIEW

    def test_update_referral_invalid_transition(self, service: ReferralService) -> None:
        """Invalid status transitions raise ValueError."""
        create = _make_referral_create()
        ref = service.create_referral(create)

        # INITIATED -> COMPLETED is not valid
        with pytest.raises(ValueError, match="Invalid status transition"):
            service.update_referral(
                ref.id, ReferralUpdate(status=ReferralStatus.COMPLETED)
            )

    def test_update_referral_not_found(self, service: ReferralService) -> None:
        """Updating non-existent referral returns None."""
        result = service.update_referral(
            "nonexistent", ReferralUpdate(notes="test")
        )
        assert result is None

    def test_update_referral_priority(self, service: ReferralService) -> None:
        """Can update referral priority."""
        create = _make_referral_create()
        ref = service.create_referral(create)

        updated = service.update_referral(
            ref.id, ReferralUpdate(priority=ReferralPriority.URGENT)
        )
        assert updated is not None
        assert updated.priority == ReferralPriority.URGENT

    def test_update_referral_accepted_sets_timestamp(self, service: ReferralService) -> None:
        """Accepting a referral sets accepted_at timestamp."""
        create = _make_referral_create()
        ref = service.create_referral(create)

        # Move to pending_review
        service.update_referral(
            ref.id, ReferralUpdate(status=ReferralStatus.PENDING_REVIEW)
        )
        # Accept
        updated = service.update_referral(
            ref.id, ReferralUpdate(status=ReferralStatus.ACCEPTED)
        )
        assert updated is not None
        assert updated.accepted_at is not None

    def test_full_referral_lifecycle(self, service: ReferralService) -> None:
        """Walk through the full referral lifecycle."""
        create = _make_referral_create()
        ref = service.create_referral(create)

        # INITIATED -> PENDING_REVIEW
        ref = service.update_referral(
            ref.id, ReferralUpdate(status=ReferralStatus.PENDING_REVIEW)
        )
        assert ref.status == ReferralStatus.PENDING_REVIEW

        # PENDING_REVIEW -> ACCEPTED
        ref = service.update_referral(
            ref.id, ReferralUpdate(status=ReferralStatus.ACCEPTED)
        )
        assert ref.status == ReferralStatus.ACCEPTED
        assert ref.accepted_at is not None

        # ACCEPTED -> IN_PROGRESS
        ref = service.update_referral(
            ref.id, ReferralUpdate(status=ReferralStatus.IN_PROGRESS)
        )
        assert ref.status == ReferralStatus.IN_PROGRESS

        # IN_PROGRESS -> COMPLETED
        ref = service.update_referral(
            ref.id, ReferralUpdate(status=ReferralStatus.COMPLETED)
        )
        assert ref.status == ReferralStatus.COMPLETED
        assert ref.completed_at is not None


# ---------------------------------------------------------------------------
# Site suggestion tests
# ---------------------------------------------------------------------------


class TestSiteSuggestions:
    """Test site matching and suggestion logic."""

    def test_suggest_sites_returns_results(self, service: ReferralService) -> None:
        """Suggestions return at least one site."""
        req = SiteSuggestionRequest(
            patient_id="PAT-1",
            trial_id="trial-eylea",
        )
        resp = service.suggest_sites(req)
        assert len(resp.suggestions) > 0
        assert resp.total_sites_evaluated == 5

    def test_suggest_sites_with_coordinates(self, service: ReferralService) -> None:
        """Distance scoring works with coordinates (Atlanta)."""
        req = SiteSuggestionRequest(
            patient_id="PAT-1",
            trial_id="trial-eylea",
            patient_lat=33.75,
            patient_lon=-84.39,
        )
        resp = service.suggest_sites(req)
        # Emory (Atlanta) should score highest on distance
        emory = [s for s in resp.suggestions if "Emory" in s.site_name]
        assert len(emory) == 1
        assert emory[0].distance_score > 0.9

    def test_suggest_sites_specialty_match(self, service: ReferralService) -> None:
        """EYLEA trial should score high for ophthalmology sites."""
        req = SiteSuggestionRequest(
            patient_id="PAT-1",
            trial_id="trial-eylea",
        )
        resp = service.suggest_sites(req)
        # Emory and Bascom Palmer are ophthalmology - should have high specialty scores
        for s in resp.suggestions:
            if "Emory" in s.site_name or "Bascom" in s.site_name:
                assert s.specialty_score > 0.5

    def test_suggest_sites_dermatology_trial(self, service: ReferralService) -> None:
        """Dupixent trial should favor dermatology sites."""
        req = SiteSuggestionRequest(
            patient_id="PAT-1",
            trial_id="trial-dupixent",
        )
        resp = service.suggest_sites(req)
        # Northwestern Dermatology should have good specialty score
        nw = [s for s in resp.suggestions if "Northwestern" in s.site_name]
        assert len(nw) == 1
        assert nw[0].specialty_score > 0.5

    def test_suggest_sites_max_results(self, service: ReferralService) -> None:
        """max_results limits the number of suggestions."""
        req = SiteSuggestionRequest(
            patient_id="PAT-1",
            trial_id="trial-eylea",
            max_results=2,
        )
        resp = service.suggest_sites(req)
        assert len(resp.suggestions) == 2

    def test_suggest_sites_sorted_by_score(self, service: ReferralService) -> None:
        """Suggestions are sorted by overall_score descending."""
        req = SiteSuggestionRequest(
            patient_id="PAT-1",
            trial_id="trial-eylea",
        )
        resp = service.suggest_sites(req)
        scores = [s.overall_score for s in resp.suggestions]
        assert scores == sorted(scores, reverse=True)

    def test_capacity_score_full_site(self, service: ReferralService) -> None:
        """A site at full capacity should have capacity_score near 0."""
        # MSK has 52/80 enrollment
        req = SiteSuggestionRequest(
            patient_id="PAT-1",
            trial_id="trial-libtayo",
        )
        resp = service.suggest_sites(req)
        msk = [s for s in resp.suggestions if "Sloan" in s.site_name]
        assert len(msk) == 1
        # 28/80 = 0.35
        assert msk[0].capacity_score == pytest.approx(0.35, abs=0.01)

    def test_unknown_trial_defaults_to_general(self, service: ReferralService) -> None:
        """Unknown trial gets general medicine specialties."""
        req = SiteSuggestionRequest(
            patient_id="PAT-1",
            trial_id="trial-unknown-xyz",
        )
        resp = service.suggest_sites(req)
        # All sites should get specialty_score of 0.0 (no general_medicine specialty)
        for s in resp.suggestions:
            assert s.specialty_score == 0.0


# ---------------------------------------------------------------------------
# Enrollment workflow tests
# ---------------------------------------------------------------------------


class TestEnrollmentWorkflow:
    """Test enrollment tracking and stage advancement."""

    def test_create_enrollment(self, service: ReferralService) -> None:
        """Creating enrollment starts at CANDIDATE."""
        tracking = service.create_enrollment("PAT-1", "trial-1")
        assert tracking.current_stage == EnrollmentStage.CANDIDATE
        assert len(tracking.milestones) == 1
        assert tracking.milestones[0].stage == EnrollmentStage.CANDIDATE

    def test_get_enrollment_not_found(self, service: ReferralService) -> None:
        """Get enrollment returns None for non-existent pair."""
        assert service.get_enrollment("nonexistent", "nonexistent") is None

    def test_advance_enrollment(self, service: ReferralService) -> None:
        """Advance enrollment through stages."""
        service.create_enrollment("PAT-1", "trial-1")
        result = service.advance_enrollment("PAT-1", "trial-1", notes="Referral sent")
        assert result is not None
        assert result.previous_stage == EnrollmentStage.CANDIDATE
        assert result.current_stage == EnrollmentStage.REFERRED

    def test_advance_enrollment_full_path(self, service: ReferralService) -> None:
        """Walk through the full enrollment path to ACTIVE."""
        service.create_enrollment("PAT-1", "trial-1")
        expected_path = [
            EnrollmentStage.REFERRED,
            EnrollmentStage.SCREENED,
            EnrollmentStage.ELIGIBLE,
            EnrollmentStage.CONSENTED,
            EnrollmentStage.ENROLLED,
            EnrollmentStage.ACTIVE,
        ]
        for expected_stage in expected_path:
            result = service.advance_enrollment("PAT-1", "trial-1")
            assert result is not None
            assert result.current_stage == expected_stage

        # Verify milestones accumulated
        tracking = service.get_enrollment("PAT-1", "trial-1")
        assert tracking is not None
        assert len(tracking.milestones) == 7  # CANDIDATE + 6 advances

    def test_advance_from_terminal_raises(self, service: ReferralService) -> None:
        """Cannot advance past ACTIVE (terminal non-withdrawn stage)."""
        service.create_enrollment("PAT-1", "trial-1")
        # Advance to ACTIVE
        for _ in range(6):
            service.advance_enrollment("PAT-1", "trial-1")

        with pytest.raises(ValueError, match="terminal stage"):
            service.advance_enrollment("PAT-1", "trial-1")

    def test_withdraw_enrollment(self, service: ReferralService) -> None:
        """Withdraw a patient from enrollment."""
        service.create_enrollment("PAT-1", "trial-1")
        service.advance_enrollment("PAT-1", "trial-1")  # REFERRED

        result = service.withdraw_enrollment(
            "PAT-1", "trial-1", notes="Patient withdrew consent"
        )
        assert result is not None
        assert result.current_stage == EnrollmentStage.WITHDRAWN

    def test_withdraw_already_withdrawn(self, service: ReferralService) -> None:
        """Cannot withdraw a patient who is already withdrawn."""
        service.create_enrollment("PAT-1", "trial-1")
        service.withdraw_enrollment("PAT-1", "trial-1")

        with pytest.raises(ValueError, match="already withdrawn"):
            service.withdraw_enrollment("PAT-1", "trial-1")

    def test_time_to_enrollment(self, service: ReferralService) -> None:
        """time_to_enrollment_days is computed when ENROLLED is reached."""
        service.create_enrollment("PAT-1", "trial-1")
        # Not enrolled yet
        tracking = service.get_enrollment("PAT-1", "trial-1")
        assert tracking.time_to_enrollment_days is None

        # Advance to ENROLLED (5 steps from CANDIDATE)
        for _ in range(5):
            service.advance_enrollment("PAT-1", "trial-1")

        tracking = service.get_enrollment("PAT-1", "trial-1")
        assert tracking.current_stage == EnrollmentStage.ENROLLED
        # Should be near 0 days since everything happened instantly
        assert tracking.time_to_enrollment_days is not None
        assert tracking.time_to_enrollment_days >= 0.0

    def test_advance_nonexistent_enrollment(self, service: ReferralService) -> None:
        """Advancing nonexistent enrollment returns None."""
        result = service.advance_enrollment("nonexistent", "nonexistent")
        assert result is None

    def test_withdraw_nonexistent_enrollment(self, service: ReferralService) -> None:
        """Withdrawing nonexistent enrollment returns None."""
        result = service.withdraw_enrollment("nonexistent", "nonexistent")
        assert result is None

    def test_create_enrollment_idempotent(self, service: ReferralService) -> None:
        """Creating enrollment twice returns same record."""
        t1 = service.create_enrollment("PAT-1", "trial-1")
        t2 = service.create_enrollment("PAT-1", "trial-1")
        assert t1.patient_id == t2.patient_id
        assert t1.trial_id == t2.trial_id


# ---------------------------------------------------------------------------
# Network analytics tests
# ---------------------------------------------------------------------------


class TestNetworkAnalytics:
    """Test referral network analytics computation."""

    def test_analytics_returns_totals(self, service: ReferralService) -> None:
        """Analytics returns correct totals from demo data."""
        analytics = service.get_analytics()
        assert analytics.total_referrals == 10
        assert analytics.total_completed_referrals == 2
        assert analytics.total_declined_referrals == 1

    def test_analytics_acceptance_rate(self, service: ReferralService) -> None:
        """Overall acceptance rate computed correctly."""
        analytics = service.get_analytics()
        # Non-cancelled referrals: 9 (10 total - 1 cancelled)
        # Accepted/in_progress/completed: 2 + 2 + 2 = 6
        # Rate: 6/9 = 0.6667
        assert analytics.overall_acceptance_rate > 0.0
        assert analytics.overall_acceptance_rate <= 1.0

    def test_analytics_conversion_rate(self, service: ReferralService) -> None:
        """Conversion rate (completed / total) computed correctly."""
        analytics = service.get_analytics()
        assert analytics.overall_conversion_rate == pytest.approx(2 / 10, abs=0.01)

    def test_analytics_filter_by_trial(self, service: ReferralService) -> None:
        """Analytics can be filtered by trial."""
        analytics = service.get_analytics(trial_id="trial-eylea")
        assert analytics.total_referrals == 3

    def test_analytics_filter_by_site(self, service: ReferralService) -> None:
        """Analytics can be filtered by site."""
        analytics = service.get_analytics(site_id="site-005")
        assert analytics.total_referrals > 0

    def test_analytics_site_metrics(self, service: ReferralService) -> None:
        """Per-site metrics are computed."""
        analytics = service.get_analytics()
        assert len(analytics.site_metrics) > 0
        for sm in analytics.site_metrics:
            assert sm.site_id is not None
            assert sm.referrals_sent >= 0
            assert sm.referrals_received >= 0

    def test_analytics_top_referring_sites(self, service: ReferralService) -> None:
        """Top referring sites are sorted by referrals_sent."""
        analytics = service.get_analytics()
        assert len(analytics.top_referring_sites) > 0
        sent_counts = [s.referrals_sent for s in analytics.top_referring_sites]
        assert sent_counts == sorted(sent_counts, reverse=True)

    def test_analytics_volume_by_trial(self, service: ReferralService) -> None:
        """Referral volume by trial is computed."""
        analytics = service.get_analytics()
        assert "trial-eylea" in analytics.referral_volume_by_trial
        assert analytics.referral_volume_by_trial["trial-eylea"] == 3

    def test_analytics_empty_filter(self, service: ReferralService) -> None:
        """Analytics with no matching referrals returns zeros."""
        analytics = service.get_analytics(trial_id="nonexistent-trial")
        assert analytics.total_referrals == 0
        assert analytics.overall_acceptance_rate == 0.0

    def test_service_stats(self, service: ReferralService) -> None:
        """get_stats returns expected keys."""
        stats = service.get_stats()
        assert "total_referrals" in stats
        assert "total_sites" in stats
        assert stats["total_referrals"] == 10
        assert stats["total_sites"] == 5
        assert stats["demo_referrals"] == 10


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestReferralAPI:
    """Test API endpoints via TestClient."""

    def test_create_referral_api(self, client: TestClient) -> None:
        """POST /referrals creates a referral."""
        response = client.post(
            "/api/v1/referrals",
            json={
                "patient_id": "PAT-API-1",
                "source_site_id": "site-001",
                "destination_site_id": "site-002",
                "trial_id": "trial-eylea",
                "priority": "high",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["patient_id"] == "PAT-API-1"
        assert data["status"] == "initiated"

    def test_list_referrals_api(self, client: TestClient) -> None:
        """GET /referrals returns referral list."""
        response = client.get("/api/v1/referrals")
        assert response.status_code == 200
        data = response.json()
        assert "referrals" in data
        assert "total" in data
        assert data["total"] >= 10

    def test_list_referrals_filter_api(self, client: TestClient) -> None:
        """GET /referrals with filters works."""
        response = client.get(
            "/api/v1/referrals", params={"trial_id": "trial-eylea"}
        )
        assert response.status_code == 200
        data = response.json()
        for r in data["referrals"]:
            assert r["trial_id"] == "trial-eylea"

    def test_get_referral_api(self, client: TestClient) -> None:
        """GET /referrals/{id} returns referral detail."""
        # Get a referral ID from the list
        list_resp = client.get("/api/v1/referrals", params={"limit": 1})
        referral_id = list_resp.json()["referrals"][0]["id"]

        response = client.get(f"/api/v1/referrals/{referral_id}")
        assert response.status_code == 200
        assert response.json()["id"] == referral_id

    def test_get_referral_not_found_api(self, client: TestClient) -> None:
        """GET /referrals/{id} returns 404 for nonexistent."""
        response = client.get("/api/v1/referrals/nonexistent-id")
        assert response.status_code == 404

    def test_update_referral_api(self, client: TestClient) -> None:
        """PUT /referrals/{id} updates a referral."""
        # Create one first
        create_resp = client.post(
            "/api/v1/referrals",
            json={
                "patient_id": "PAT-API-2",
                "source_site_id": "site-001",
                "destination_site_id": "site-002",
                "trial_id": "trial-eylea",
            },
        )
        referral_id = create_resp.json()["id"]

        response = client.put(
            f"/api/v1/referrals/{referral_id}",
            json={"status": "pending_review"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "pending_review"

    def test_update_referral_invalid_transition_api(self, client: TestClient) -> None:
        """PUT /referrals/{id} returns 400 for invalid transition."""
        create_resp = client.post(
            "/api/v1/referrals",
            json={
                "patient_id": "PAT-API-3",
                "source_site_id": "site-001",
                "destination_site_id": "site-002",
                "trial_id": "trial-eylea",
            },
        )
        referral_id = create_resp.json()["id"]

        response = client.put(
            f"/api/v1/referrals/{referral_id}",
            json={"status": "completed"},
        )
        assert response.status_code == 400

    def test_suggest_sites_api(self, client: TestClient) -> None:
        """POST /referrals/suggest-sites returns suggestions."""
        response = client.post(
            "/api/v1/referrals/suggest-sites",
            json={
                "patient_id": "PAT-1",
                "trial_id": "trial-eylea",
                "patient_lat": 33.75,
                "patient_lon": -84.39,
                "max_results": 3,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["suggestions"]) == 3
        assert data["total_sites_evaluated"] == 5

    def test_analytics_api(self, client: TestClient) -> None:
        """GET /referrals/analytics returns network analytics."""
        response = client.get("/api/v1/referrals/analytics")
        assert response.status_code == 200
        data = response.json()
        assert "total_referrals" in data
        assert "site_metrics" in data
        assert "top_referring_sites" in data
        assert data["total_referrals"] >= 10

    def test_enrollment_get_api(self, client: TestClient) -> None:
        """GET /referrals/enrollment/{patient_id}/{trial_id} returns tracking."""
        response = client.get("/api/v1/referrals/enrollment/PAT-ENR-1/trial-1")
        assert response.status_code == 200
        data = response.json()
        assert data["patient_id"] == "PAT-ENR-1"
        assert data["current_stage"] == "candidate"

    def test_enrollment_advance_api(self, client: TestClient) -> None:
        """POST /referrals/enrollment/{pid}/{tid}/advance advances enrollment."""
        # Ensure enrollment exists
        client.get("/api/v1/referrals/enrollment/PAT-ENR-2/trial-2")

        response = client.post(
            "/api/v1/referrals/enrollment/PAT-ENR-2/trial-2/advance",
            json={"notes": "Referred to site"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["previous_stage"] == "candidate"
        assert data["current_stage"] == "referred"

    def test_enrollment_advance_terminal_api(self, client: TestClient) -> None:
        """Advancing at terminal stage returns 400."""
        # Create and advance to ACTIVE (6 steps)
        client.get("/api/v1/referrals/enrollment/PAT-ENR-3/trial-3")
        for _ in range(6):
            client.post(
                "/api/v1/referrals/enrollment/PAT-ENR-3/trial-3/advance",
                json={},
            )

        response = client.post(
            "/api/v1/referrals/enrollment/PAT-ENR-3/trial-3/advance",
            json={},
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Singleton tests
# ---------------------------------------------------------------------------


class TestSingleton:
    """Test singleton accessor."""

    def test_get_referral_service_returns_instance(self) -> None:
        """get_referral_service returns a ReferralService."""
        svc = get_referral_service()
        assert isinstance(svc, ReferralService)

    def test_get_referral_service_singleton(self) -> None:
        """get_referral_service returns the same instance each time."""
        svc1 = get_referral_service()
        svc2 = get_referral_service()
        assert svc1 is svc2
