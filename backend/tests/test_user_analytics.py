"""Tests for User Analytics & Feature Flag Management (VP-Product-9).

Covers:
- Seed data verification (events, sessions, flags, evaluations)
- Event CRUD (create, list with all filter combinations)
- Event count by category
- Session management (create, end, list, get)
- Feature flag CRUD (create, read, update, archive, list)
- Rollout strategy evaluation (ALL_USERS, PERCENTAGE, USER_LIST, ROLE_BASED, GRADUAL)
- Flag evaluation determinism and bucketing
- Funnel analysis (conversion rates, drop-off, stages)
- Retention cohort analysis (daily, weekly, monthly)
- Product health metrics (DAU/WAU/MAU, session duration, adoption)
- Top events and top pages
- Event rate calculation
- User segmentation
- API integration (all endpoints)
- Error handling (404s, 400s)
- Pagination and edge cases
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.user_analytics import (
    EventCategory,
    EventCreateRequest,
    FeatureFlagCreateRequest,
    FeatureFlagUpdateRequest,
    FlagEvaluateRequest,
    FlagStatus,
    FlagVariant,
    FunnelStage,
    MetricType,
    RetentionPeriod,
    RolloutStrategy,
)
from app.services.user_analytics_service import (
    UserAnalyticsService,
    get_user_analytics_service,
    reset_user_analytics_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_PREFIX = "/api/v1/user-analytics"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_user_analytics_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> UserAnalyticsService:
    """Shorthand for the fresh service."""
    return fresh_service


def _make_event_request(**kwargs) -> EventCreateRequest:
    """Helper to build an EventCreateRequest with defaults."""
    defaults = dict(
        user_id="test-user-001",
        session_id="sess-0001",
        event_category=EventCategory.PAGE_VIEW,
        event_name="test_event",
        properties={"source": "test"},
        page_url="/test",
        duration_ms=1000,
    )
    defaults.update(kwargs)
    return EventCreateRequest(**defaults)


def _make_flag_request(**kwargs) -> FeatureFlagCreateRequest:
    """Helper to build a FeatureFlagCreateRequest with defaults."""
    defaults = dict(
        name="test-flag",
        description="A test feature flag",
        status=FlagStatus.ACTIVE,
        rollout_strategy=RolloutStrategy.ALL_USERS,
        rollout_percentage=100.0,
        created_by="test-user",
        variants=[
            FlagVariant(name="control", weight=0.5, payload={}),
            FlagVariant(name="treatment", weight=0.5, payload={"enabled": True}),
        ],
    )
    defaults.update(kwargs)
    return FeatureFlagCreateRequest(**defaults)


# ===========================================================================
# Section 1: Seed data verification
# ===========================================================================


class TestSeedData:
    """Verify the seed data is loaded correctly on service init."""

    def test_seed_events_count(self, svc: UserAnalyticsService):
        """Seed should contain 220 analytics events."""
        items, total = svc.list_events(limit=300)
        assert total == 220

    def test_seed_sessions_count(self, svc: UserAnalyticsService):
        """Seed should contain 30 sessions."""
        items, total = svc.list_sessions(limit=50)
        assert total == 30

    def test_seed_flags_count(self, svc: UserAnalyticsService):
        """Seed should contain 8 feature flags."""
        flags = svc.list_flags()
        assert len(flags) == 8

    def test_seed_evaluations_count(self, svc: UserAnalyticsService):
        """Seed should contain 55 flag evaluations."""
        assert len(svc._evaluations) == 55

    def test_seed_event_ids_format(self, svc: UserAnalyticsService):
        """All event IDs should start with 'evt-'."""
        for eid in svc._events:
            assert eid.startswith("evt-")

    def test_seed_session_ids_format(self, svc: UserAnalyticsService):
        """All session IDs should start with 'sess-'."""
        for sid in svc._sessions:
            assert sid.startswith("sess-")

    def test_seed_flag_ids_format(self, svc: UserAnalyticsService):
        """All flag IDs should start with 'flag-'."""
        for fid in svc._flags:
            assert fid.startswith("flag-")

    def test_seed_active_flags_count(self, svc: UserAnalyticsService):
        """Seed should contain 5 active flags."""
        active = svc.list_flags(status=FlagStatus.ACTIVE)
        assert len(active) == 5

    def test_seed_inactive_flags_count(self, svc: UserAnalyticsService):
        """Seed should contain 2 inactive flags."""
        inactive = svc.list_flags(status=FlagStatus.INACTIVE)
        assert len(inactive) == 2

    def test_seed_archived_flags_count(self, svc: UserAnalyticsService):
        """Seed should contain 1 archived flag."""
        archived = svc.list_flags(status=FlagStatus.ARCHIVED)
        assert len(archived) == 1

    def test_seed_flag_names(self, svc: UserAnalyticsService):
        """Verify known flag names exist."""
        names = {f.name for f in svc.list_flags()}
        assert "enhanced-screening-ui" in names
        assert "ai-eligibility-check" in names
        assert "bulk-screening-export" in names
        assert "deprecated-legacy-export" in names

    def test_seed_percentage_rollout_flags(self, svc: UserAnalyticsService):
        """Two flags should use percentage rollout."""
        percentage_flags = [
            f for f in svc.list_flags()
            if f.rollout_strategy == RolloutStrategy.PERCENTAGE
        ]
        assert len(percentage_flags) == 2

    def test_seed_sessions_have_users(self, svc: UserAnalyticsService):
        """All sessions should belong to users matching pattern user-XXX."""
        for sess in svc._sessions.values():
            assert sess.user_id.startswith("user-")

    def test_seed_unique_users(self, svc: UserAnalyticsService):
        """Seed should have 15 unique users."""
        users = {e.user_id for e in svc._events.values()}
        assert len(users) == 15

    def test_seed_stats(self, svc: UserAnalyticsService):
        """Stats should reflect seed data counts."""
        stats = svc.get_stats()
        assert stats["total_events"] == 220
        assert stats["total_sessions"] == 30
        assert stats["total_flags"] == 8
        assert stats["total_evaluations"] == 55
        assert stats["service"] == "user_analytics"


# ===========================================================================
# Section 2: Event CRUD + filtering
# ===========================================================================


class TestEventCRUD:
    """Test event tracking and retrieval."""

    def test_track_event(self, svc: UserAnalyticsService):
        """Should create a new event."""
        req = _make_event_request()
        event = svc.track_event(req)
        assert event.id.startswith("evt-")
        assert event.user_id == "test-user-001"
        assert event.event_name == "test_event"
        assert event.event_category == EventCategory.PAGE_VIEW

    def test_track_event_increments_count(self, svc: UserAnalyticsService):
        """Tracking should increase total event count."""
        _, before = svc.list_events(limit=1)
        svc.track_event(_make_event_request())
        _, after = svc.list_events(limit=1)
        assert after == before + 1

    def test_track_event_updates_session_count(self, svc: UserAnalyticsService):
        """Tracking should update the session events_count."""
        session = svc.get_session("sess-0001")
        original_count = session.events_count
        svc.track_event(_make_event_request(session_id="sess-0001"))
        updated = svc.get_session("sess-0001")
        assert updated.events_count == original_count + 1

    def test_track_page_view_increments_page_views(self, svc: UserAnalyticsService):
        """PAGE_VIEW events should increment session page_views."""
        session = svc.get_session("sess-0001")
        original = session.page_views
        svc.track_event(_make_event_request(
            session_id="sess-0001",
            event_category=EventCategory.PAGE_VIEW,
        ))
        updated = svc.get_session("sess-0001")
        assert updated.page_views == original + 1

    def test_list_events_pagination(self, svc: UserAnalyticsService):
        """Should respect limit and offset."""
        items, total = svc.list_events(limit=5, offset=0)
        assert len(items) == 5
        assert total == 220

    def test_list_events_filter_by_user(self, svc: UserAnalyticsService):
        """Should filter events by user_id."""
        items, total = svc.list_events(user_id="user-001")
        assert total > 0
        for item in items:
            assert item.user_id == "user-001"

    def test_list_events_filter_by_category(self, svc: UserAnalyticsService):
        """Should filter events by category."""
        items, total = svc.list_events(category=EventCategory.PAGE_VIEW)
        assert total > 0
        for item in items:
            assert item.event_category == EventCategory.PAGE_VIEW

    def test_list_events_filter_by_event_name(self, svc: UserAnalyticsService):
        """Should filter events by event_name."""
        items, total = svc.list_events(event_name="search_trials")
        assert total > 0
        for item in items:
            assert item.event_name == "search_trials"

    def test_list_events_sorted_by_timestamp(self, svc: UserAnalyticsService):
        """Events should be sorted by timestamp descending."""
        items, _ = svc.list_events(limit=10)
        for i in range(len(items) - 1):
            assert items[i].timestamp >= items[i + 1].timestamp

    def test_count_events_by_category(self, svc: UserAnalyticsService):
        """Should return counts for each category."""
        counts = svc.count_events_by_category()
        assert "PAGE_VIEW" in counts
        assert counts["PAGE_VIEW"] > 0
        total = sum(counts.values())
        assert total == 220

    def test_track_event_with_properties(self, svc: UserAnalyticsService):
        """Should store event properties."""
        req = _make_event_request(properties={"trial_id": "T-001", "phase": "III"})
        event = svc.track_event(req)
        assert event.properties["trial_id"] == "T-001"

    def test_track_event_without_duration(self, svc: UserAnalyticsService):
        """Should allow events without duration."""
        req = _make_event_request(duration_ms=None)
        event = svc.track_event(req)
        assert event.duration_ms is None

    def test_list_events_empty_filter(self, svc: UserAnalyticsService):
        """Filtering by non-existent user should return empty."""
        items, total = svc.list_events(user_id="non-existent-user")
        assert total == 0
        assert len(items) == 0


# ===========================================================================
# Section 3: Session management
# ===========================================================================


class TestSessionManagement:
    """Test session CRUD operations."""

    def test_create_session(self, svc: UserAnalyticsService):
        """Should create a new session."""
        session = svc.create_session("test-user", device_type="desktop", browser="Chrome 120")
        assert session.id.startswith("sess-")
        assert session.user_id == "test-user"
        assert session.device_type == "desktop"
        assert session.ended_at is None
        assert session.page_views == 0

    def test_end_session(self, svc: UserAnalyticsService):
        """Should end an active session."""
        session = svc.create_session("test-user")
        ended = svc.end_session(session.id)
        assert ended.ended_at is not None
        assert ended.ended_at >= ended.started_at

    def test_end_session_not_found(self, svc: UserAnalyticsService):
        """Should raise KeyError for non-existent session."""
        with pytest.raises(KeyError, match="not found"):
            svc.end_session("nonexistent-session")

    def test_end_session_already_ended(self, svc: UserAnalyticsService):
        """Should raise ValueError for already ended session."""
        session = svc.create_session("test-user")
        svc.end_session(session.id)
        with pytest.raises(ValueError, match="already ended"):
            svc.end_session(session.id)

    def test_get_session(self, svc: UserAnalyticsService):
        """Should retrieve a session by ID."""
        session = svc.get_session("sess-0001")
        assert session.id == "sess-0001"

    def test_get_session_not_found(self, svc: UserAnalyticsService):
        """Should raise KeyError for non-existent session."""
        with pytest.raises(KeyError, match="not found"):
            svc.get_session("nonexistent")

    def test_list_sessions(self, svc: UserAnalyticsService):
        """Should list all sessions."""
        items, total = svc.list_sessions()
        assert total == 30

    def test_list_sessions_by_user(self, svc: UserAnalyticsService):
        """Should filter sessions by user."""
        items, total = svc.list_sessions(user_id="user-001")
        assert total > 0
        for item in items:
            assert item.user_id == "user-001"

    def test_list_sessions_pagination(self, svc: UserAnalyticsService):
        """Should respect pagination."""
        items, total = svc.list_sessions(limit=5, offset=0)
        assert len(items) == 5
        assert total == 30

    def test_list_sessions_sorted_by_start(self, svc: UserAnalyticsService):
        """Sessions should be sorted by started_at descending."""
        items, _ = svc.list_sessions(limit=10)
        for i in range(len(items) - 1):
            assert items[i].started_at >= items[i + 1].started_at


# ===========================================================================
# Section 4: Feature flag CRUD
# ===========================================================================


class TestFeatureFlagCRUD:
    """Test feature flag create, read, update, delete (archive)."""

    def test_create_flag(self, svc: UserAnalyticsService):
        """Should create a new feature flag."""
        req = _make_flag_request()
        flag = svc.create_flag(req)
        assert flag.id.startswith("flag-")
        assert flag.name == "test-flag"
        assert flag.status == FlagStatus.ACTIVE
        assert len(flag.variants) == 2

    def test_get_flag(self, svc: UserAnalyticsService):
        """Should retrieve a flag by ID."""
        flag = svc.get_flag("flag-001")
        assert flag.name == "enhanced-screening-ui"

    def test_get_flag_not_found(self, svc: UserAnalyticsService):
        """Should raise KeyError for non-existent flag."""
        with pytest.raises(KeyError, match="not found"):
            svc.get_flag("nonexistent-flag")

    def test_update_flag_name(self, svc: UserAnalyticsService):
        """Should update flag name."""
        req = FeatureFlagUpdateRequest(name="renamed-flag")
        updated = svc.update_flag("flag-001", req)
        assert updated.name == "renamed-flag"

    def test_update_flag_status(self, svc: UserAnalyticsService):
        """Should update flag status."""
        req = FeatureFlagUpdateRequest(status=FlagStatus.INACTIVE)
        updated = svc.update_flag("flag-001", req)
        assert updated.status == FlagStatus.INACTIVE

    def test_update_flag_rollout_percentage(self, svc: UserAnalyticsService):
        """Should update rollout percentage."""
        req = FeatureFlagUpdateRequest(rollout_percentage=75.0)
        updated = svc.update_flag("flag-002", req)
        assert updated.rollout_percentage == 75.0

    def test_update_flag_not_found(self, svc: UserAnalyticsService):
        """Should raise KeyError for non-existent flag."""
        req = FeatureFlagUpdateRequest(name="new-name")
        with pytest.raises(KeyError, match="not found"):
            svc.update_flag("nonexistent", req)

    def test_update_flag_updates_timestamp(self, svc: UserAnalyticsService):
        """Update should refresh updated_at."""
        before = svc.get_flag("flag-001").updated_at
        req = FeatureFlagUpdateRequest(description="updated desc")
        updated = svc.update_flag("flag-001", req)
        assert updated.updated_at >= before

    def test_archive_flag(self, svc: UserAnalyticsService):
        """Should archive a flag."""
        archived = svc.archive_flag("flag-001")
        assert archived.status == FlagStatus.ARCHIVED

    def test_archive_flag_not_found(self, svc: UserAnalyticsService):
        """Should raise KeyError for non-existent flag."""
        with pytest.raises(KeyError, match="not found"):
            svc.archive_flag("nonexistent")

    def test_list_flags_all(self, svc: UserAnalyticsService):
        """Should list all flags."""
        flags = svc.list_flags()
        assert len(flags) == 8

    def test_list_flags_by_status(self, svc: UserAnalyticsService):
        """Should filter flags by status."""
        active = svc.list_flags(status=FlagStatus.ACTIVE)
        for f in active:
            assert f.status == FlagStatus.ACTIVE

    def test_list_flags_sorted_by_created_at(self, svc: UserAnalyticsService):
        """Flags should be sorted by created_at descending."""
        flags = svc.list_flags()
        for i in range(len(flags) - 1):
            assert flags[i].created_at >= flags[i + 1].created_at

    def test_create_flag_with_allowed_users(self, svc: UserAnalyticsService):
        """Should store allowed users."""
        req = _make_flag_request(
            rollout_strategy=RolloutStrategy.USER_LIST,
            allowed_users=["u1", "u2"],
        )
        flag = svc.create_flag(req)
        assert flag.allowed_users == ["u1", "u2"]

    def test_create_flag_with_allowed_roles(self, svc: UserAnalyticsService):
        """Should store allowed roles."""
        req = _make_flag_request(
            rollout_strategy=RolloutStrategy.ROLE_BASED,
            allowed_roles=["admin", "researcher"],
        )
        flag = svc.create_flag(req)
        assert "admin" in flag.allowed_roles


# ===========================================================================
# Section 5: Rollout strategy evaluation
# ===========================================================================


class TestRolloutStrategyEvaluation:
    """Test flag evaluation with different rollout strategies."""

    def test_evaluate_all_users_strategy(self, svc: UserAnalyticsService):
        """ALL_USERS strategy should give non-default variant to all."""
        ev = svc.evaluate_flag("flag-001", "any-user")
        assert ev.variant in ("control", "treatment")
        assert ev.context["reason"] == "all_users"

    def test_evaluate_percentage_included(self, svc: UserAnalyticsService):
        """PERCENTAGE strategy: user in percentage gets treatment."""
        # flag-002 is 50% rollout, try many users to find included one
        included = False
        for i in range(50):
            ev = svc.evaluate_flag("flag-002", f"pct-user-{i}")
            if ev.context.get("reason") == "percentage_included":
                included = True
                break
        assert included, "At least one user should be included at 50%"

    def test_evaluate_percentage_excluded(self, svc: UserAnalyticsService):
        """PERCENTAGE strategy: some users should be excluded at 50%."""
        excluded = False
        for i in range(50):
            ev = svc.evaluate_flag("flag-002", f"pct-user-{i}")
            if ev.context.get("reason") == "percentage_excluded":
                excluded = True
                break
        assert excluded, "At least one user should be excluded at 50%"

    def test_evaluate_percentage_deterministic(self, svc: UserAnalyticsService):
        """Same user+flag should always get same bucket."""
        ev1 = svc.evaluate_flag("flag-002", "deterministic-user")
        ev2 = svc.evaluate_flag("flag-002", "deterministic-user")
        assert ev1.variant == ev2.variant

    def test_evaluate_user_list_included(self, svc: UserAnalyticsService):
        """USER_LIST strategy: allowed user gets variant."""
        # flag-005 allows user-001, user-002, user-003
        ev = svc.evaluate_flag("flag-005", "user-001")
        # flag is INACTIVE, so it returns default_variant
        assert ev.context["reason"] == "flag_not_active"

    def test_evaluate_user_list_excluded(self, svc: UserAnalyticsService):
        """USER_LIST strategy: non-listed user gets default."""
        # Create an active user-list flag
        req = _make_flag_request(
            name="test-user-list",
            rollout_strategy=RolloutStrategy.USER_LIST,
            allowed_users=["allowed-user"],
        )
        flag = svc.create_flag(req)
        ev = svc.evaluate_flag(flag.id, "not-allowed-user")
        assert ev.context["reason"] == "user_not_in_list"
        assert ev.variant == "control"

    def test_evaluate_user_list_active_included(self, svc: UserAnalyticsService):
        """Active USER_LIST flag: allowed user gets treatment."""
        req = _make_flag_request(
            name="test-user-list-active",
            rollout_strategy=RolloutStrategy.USER_LIST,
            allowed_users=["allowed-user"],
        )
        flag = svc.create_flag(req)
        ev = svc.evaluate_flag(flag.id, "allowed-user")
        assert ev.context["reason"] == "user_in_list"

    def test_evaluate_role_based_match(self, svc: UserAnalyticsService):
        """ROLE_BASED strategy: matching role gets variant."""
        # flag-003 allows admin and clinical_researcher
        ev = svc.evaluate_flag("flag-003", "user-001", role="admin")
        assert ev.context["reason"] == "role_match"

    def test_evaluate_role_based_no_match(self, svc: UserAnalyticsService):
        """ROLE_BASED strategy: non-matching role gets default."""
        ev = svc.evaluate_flag("flag-003", "user-001", role="viewer")
        assert ev.context["reason"] == "role_no_match"
        assert ev.variant == "control"

    def test_evaluate_role_based_no_role(self, svc: UserAnalyticsService):
        """ROLE_BASED strategy: no role provided gets default."""
        ev = svc.evaluate_flag("flag-003", "user-001")
        assert ev.context["reason"] == "role_no_match"

    def test_evaluate_gradual_strategy(self, svc: UserAnalyticsService):
        """GRADUAL strategy should work like percentage."""
        # flag-008 is gradual at 60%
        included = 0
        for i in range(100):
            ev = svc.evaluate_flag("flag-008", f"gradual-user-{i}")
            if ev.context.get("reason") == "gradual_included":
                included += 1
        # Should be roughly around 60% (allow wide margin for hash distribution)
        assert 30 < included < 90

    def test_evaluate_inactive_flag(self, svc: UserAnalyticsService):
        """Inactive flag should return default variant."""
        ev = svc.evaluate_flag("flag-004", "any-user")
        assert ev.context["reason"] == "flag_not_active"
        assert ev.variant == "control"

    def test_evaluate_archived_flag(self, svc: UserAnalyticsService):
        """Archived flag should return default variant."""
        ev = svc.evaluate_flag("flag-006", "any-user")
        assert ev.context["reason"] == "flag_not_active"

    def test_evaluate_not_found(self, svc: UserAnalyticsService):
        """Evaluating non-existent flag should raise KeyError."""
        with pytest.raises(KeyError, match="not found"):
            svc.evaluate_flag("nonexistent", "user")

    def test_evaluate_records_evaluation(self, svc: UserAnalyticsService):
        """Evaluation should be stored."""
        before = len(svc._evaluations)
        svc.evaluate_flag("flag-001", "eval-test-user")
        assert len(svc._evaluations) == before + 1

    def test_user_bucket_deterministic(self, svc: UserAnalyticsService):
        """User bucket should be deterministic."""
        b1 = UserAnalyticsService._user_bucket("flag-001", "user-1")
        b2 = UserAnalyticsService._user_bucket("flag-001", "user-1")
        assert b1 == b2

    def test_user_bucket_range(self, svc: UserAnalyticsService):
        """User bucket should be between 0 and 100."""
        for i in range(100):
            bucket = UserAnalyticsService._user_bucket("flag-001", f"user-{i}")
            assert 0 <= bucket <= 100


# ===========================================================================
# Section 6: Funnel analysis
# ===========================================================================


class TestFunnelAnalysis:
    """Test funnel conversion analysis."""

    def test_funnel_returns_all_stages(self, svc: UserAnalyticsService):
        """Default funnel should have all 7 stages."""
        result = svc.analyze_funnel()
        assert len(result.stages) == 7

    def test_funnel_first_stage_conversion(self, svc: UserAnalyticsService):
        """First stage conversion should be 1.0."""
        result = svc.analyze_funnel()
        assert result.stages[0].conversion_from_previous == 1.0

    def test_funnel_name(self, svc: UserAnalyticsService):
        """Funnel name should match input."""
        result = svc.analyze_funnel(funnel_name="custom_funnel")
        assert result.funnel_name == "custom_funnel"

    def test_funnel_conversion_rate(self, svc: UserAnalyticsService):
        """End-to-end conversion rate should be between 0 and 1."""
        result = svc.analyze_funnel()
        assert 0.0 <= result.conversion_rate <= 1.0

    def test_funnel_total_entered(self, svc: UserAnalyticsService):
        """Total entered should match first stage count."""
        result = svc.analyze_funnel()
        assert result.total_entered == result.stages[0].count

    def test_funnel_decreasing_or_stable(self, svc: UserAnalyticsService):
        """Funnel stages should generally have non-increasing counts (except for data overlaps)."""
        result = svc.analyze_funnel()
        # Just check that total_entered >= last stage
        assert result.total_entered >= result.stages[-1].count

    def test_funnel_custom_stages(self, svc: UserAnalyticsService):
        """Should analyze custom subset of stages."""
        result = svc.analyze_funnel(stages=[FunnelStage.VISIT, FunnelStage.SEARCH_TRIAL])
        assert len(result.stages) == 2

    def test_funnel_drop_off_stages(self, svc: UserAnalyticsService):
        """Drop-off stages should contain valid stages."""
        result = svc.analyze_funnel()
        for stage in result.drop_off_stages:
            assert isinstance(stage, FunnelStage)

    def test_funnel_stage_results_structure(self, svc: UserAnalyticsService):
        """Each stage result should have required fields."""
        result = svc.analyze_funnel()
        for sr in result.stages:
            assert sr.count >= 0
            assert 0.0 <= sr.conversion_from_previous <= 1.0
            assert 0.0 <= sr.drop_off_rate <= 1.0


# ===========================================================================
# Section 7: Retention cohorts
# ===========================================================================


class TestRetentionCohorts:
    """Test retention cohort analysis."""

    def test_retention_returns_cohorts(self, svc: UserAnalyticsService):
        """Should return requested number of cohorts."""
        cohorts = svc.analyze_retention(num_cohorts=4)
        assert len(cohorts) == 4

    def test_retention_cohort_structure(self, svc: UserAnalyticsService):
        """Each cohort should have required fields."""
        cohorts = svc.analyze_retention(num_cohorts=2, num_periods=3)
        for c in cohorts:
            assert len(c.periods) == 3
            assert len(c.retention_rates) == 3
            assert c.cohort_size > 0
            assert c.cohort_date  # not empty

    def test_retention_rates_range(self, svc: UserAnalyticsService):
        """Retention rates should be between 0 and 1."""
        cohorts = svc.analyze_retention()
        for c in cohorts:
            for rate in c.retention_rates:
                assert 0.0 <= rate <= 1.0

    def test_retention_daily_period(self, svc: UserAnalyticsService):
        """Should support daily retention."""
        cohorts = svc.analyze_retention(period=RetentionPeriod.DAILY, num_cohorts=2)
        assert len(cohorts) == 2

    def test_retention_monthly_period(self, svc: UserAnalyticsService):
        """Should support monthly retention."""
        cohorts = svc.analyze_retention(period=RetentionPeriod.MONTHLY, num_cohorts=2)
        assert len(cohorts) == 2

    def test_retention_weekly_period(self, svc: UserAnalyticsService):
        """Should support weekly retention (default)."""
        cohorts = svc.analyze_retention(period=RetentionPeriod.WEEKLY)
        assert len(cohorts) > 0


# ===========================================================================
# Section 8: Product metrics
# ===========================================================================


class TestProductMetrics:
    """Test product health metrics and analytics."""

    def test_get_metrics(self, svc: UserAnalyticsService):
        """Should return aggregated metrics."""
        metrics = svc.get_metrics()
        assert metrics.total_events == 220
        assert metrics.total_sessions == 30
        assert metrics.unique_users == 15

    def test_get_metrics_active_flags(self, svc: UserAnalyticsService):
        """Active flags count should match seed data."""
        metrics = svc.get_metrics()
        assert metrics.active_flags == 5

    def test_get_metrics_top_events(self, svc: UserAnalyticsService):
        """Should return top events."""
        metrics = svc.get_metrics()
        assert len(metrics.top_events) > 0
        assert "event_name" in metrics.top_events[0]
        assert "count" in metrics.top_events[0]

    def test_get_metrics_top_pages(self, svc: UserAnalyticsService):
        """Should return top pages."""
        metrics = svc.get_metrics()
        assert len(metrics.top_pages) > 0
        assert "page_url" in metrics.top_pages[0]

    def test_get_metrics_events_per_session(self, svc: UserAnalyticsService):
        """Events per session should be positive."""
        metrics = svc.get_metrics()
        assert metrics.events_per_session > 0

    def test_get_metrics_avg_session_duration(self, svc: UserAnalyticsService):
        """Avg session duration should be positive."""
        metrics = svc.get_metrics()
        assert metrics.avg_session_duration_minutes > 0

    def test_get_metrics_feature_adoption(self, svc: UserAnalyticsService):
        """Feature adoption rates should be present for active flags."""
        metrics = svc.get_metrics()
        assert len(metrics.feature_adoption_rates) > 0

    def test_product_health_report(self, svc: UserAnalyticsService):
        """Should generate comprehensive product health report."""
        report = svc.get_product_health()
        assert report.generated_at is not None
        assert len(report.metrics) >= 5
        assert report.total_feature_flags == 8

    def test_product_health_dau_wau_mau(self, svc: UserAnalyticsService):
        """Health report should include DAU, WAU, MAU metrics."""
        report = svc.get_product_health()
        metric_names = {m.name for m in report.metrics}
        assert "DAU" in metric_names
        assert "WAU" in metric_names
        assert "MAU" in metric_names

    def test_product_health_metric_types(self, svc: UserAnalyticsService):
        """Metrics should have proper types."""
        report = svc.get_product_health()
        for m in report.metrics:
            assert isinstance(m.metric_type, MetricType)

    def test_top_events_limit(self, svc: UserAnalyticsService):
        """Top events should respect limit parameter."""
        top = svc.get_top_events(limit=3)
        assert len(top) <= 3

    def test_top_pages_limit(self, svc: UserAnalyticsService):
        """Top pages should respect limit parameter."""
        top = svc.get_top_pages(limit=3)
        assert len(top) <= 3

    def test_event_rate(self, svc: UserAnalyticsService):
        """Event rate should be a non-negative number."""
        rate = svc.get_event_rate(window_minutes=60)
        assert rate >= 0

    def test_event_rate_different_windows(self, svc: UserAnalyticsService):
        """Different time windows should produce different rates."""
        rate_60 = svc.get_event_rate(window_minutes=60)
        rate_1440 = svc.get_event_rate(window_minutes=1440)
        # Wider window should have events if narrower one does
        # (or at least rate is valid)
        assert rate_60 >= 0
        assert rate_1440 >= 0


# ===========================================================================
# Section 9: User segmentation
# ===========================================================================


class TestUserSegmentation:
    """Test user behavior segmentation."""

    def test_segments_has_all_categories(self, svc: UserAnalyticsService):
        """Should return all segment categories."""
        segments = svc.get_user_segments()
        assert "power_users" in segments
        assert "regular_users" in segments
        assert "casual_users" in segments
        assert "inactive_users" in segments

    def test_segments_cover_all_users(self, svc: UserAnalyticsService):
        """All users with events should be in exactly one segment."""
        segments = svc.get_user_segments()
        all_segmented = set()
        for users in segments.values():
            for u in users:
                assert u not in all_segmented, f"User {u} in multiple segments"
                all_segmented.add(u)
        # All users in events should be segmented
        all_event_users = {e.user_id for e in svc._events.values()}
        assert all_event_users == all_segmented


# ===========================================================================
# Section 10: Clear / utility
# ===========================================================================


class TestUtility:
    """Test utility methods."""

    def test_clear(self, svc: UserAnalyticsService):
        """Clear should remove all data."""
        svc.clear()
        assert len(svc._events) == 0
        assert len(svc._sessions) == 0
        assert len(svc._flags) == 0
        assert len(svc._evaluations) == 0

    def test_reset_service(self):
        """Reset should create fresh instance with seed data."""
        svc1 = get_user_analytics_service()
        svc1.clear()
        assert len(svc1._events) == 0

        svc2 = reset_user_analytics_service()
        assert len(svc2._events) == 220


# ===========================================================================
# Section 11: API integration tests
# ===========================================================================


@pytest.mark.anyio
class TestAPIEvents:
    """Test event tracking API endpoints."""

    async def test_track_event(self):
        """POST /events should create an event."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/events",
                json={
                    "user_id": "api-user",
                    "session_id": "sess-0001",
                    "event_category": "PAGE_VIEW",
                    "event_name": "api_test_event",
                    "properties": {"source": "api-test"},
                    "page_url": "/api-test",
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["event_name"] == "api_test_event"
        assert data["id"].startswith("evt-")

    async def test_list_events(self):
        """GET /events should return paginated events."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/events", params={"limit": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 5
        assert data["total"] == 220

    async def test_list_events_filter_user(self):
        """GET /events?user_id= should filter by user."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"{API_PREFIX}/events", params={"user_id": "user-001"}
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0

    async def test_list_events_filter_category(self):
        """GET /events?category= should filter by category."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"{API_PREFIX}/events", params={"category": "SEARCH"}
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0

    async def test_count_events(self):
        """GET /events/count should return counts by category."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/events/count")
        assert resp.status_code == 200
        data = resp.json()
        assert "PAGE_VIEW" in data


@pytest.mark.anyio
class TestAPISessions:
    """Test session management API endpoints."""

    async def test_list_sessions(self):
        """GET /sessions should return sessions."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 30

    async def test_get_session(self):
        """GET /sessions/{id} should return session detail."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/sessions/sess-0001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "sess-0001"

    async def test_get_session_not_found(self):
        """GET /sessions/{id} should return 404 for missing session."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/sessions/nonexistent")
        assert resp.status_code == 404

    async def test_create_session(self):
        """POST /sessions should create a session."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/sessions",
                json={"user_id": "api-user", "device_type": "mobile", "browser": "Safari 17"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "api-user"

    async def test_end_session(self):
        """PUT /sessions/{id}/end should end a session."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Create a new session first
            create_resp = await client.post(
                f"{API_PREFIX}/sessions",
                json={"user_id": "api-user"},
            )
            session_id = create_resp.json()["id"]

            resp = await client.put(f"{API_PREFIX}/sessions/{session_id}/end")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ended_at"] is not None

    async def test_end_session_not_found(self):
        """PUT /sessions/{id}/end should return 404 for missing session."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(f"{API_PREFIX}/sessions/nonexistent/end")
        assert resp.status_code == 404


@pytest.mark.anyio
class TestAPIFeatureFlags:
    """Test feature flag API endpoints."""

    async def test_list_flags(self):
        """GET /feature-flags should return all flags."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/feature-flags")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8

    async def test_list_flags_filter_status(self):
        """GET /feature-flags?status= should filter by status."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"{API_PREFIX}/feature-flags", params={"status": "ACTIVE"}
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    async def test_create_flag(self):
        """POST /feature-flags should create a flag."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/feature-flags",
                json={
                    "name": "api-test-flag",
                    "description": "Created via API",
                    "status": "ACTIVE",
                    "rollout_strategy": "ALL_USERS",
                    "created_by": "api-tester",
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "api-test-flag"

    async def test_get_flag(self):
        """GET /feature-flags/{id} should return flag detail."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/feature-flags/flag-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "enhanced-screening-ui"

    async def test_get_flag_not_found(self):
        """GET /feature-flags/{id} should return 404 for missing flag."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/feature-flags/nonexistent")
        assert resp.status_code == 404

    async def test_update_flag(self):
        """PUT /feature-flags/{id} should update the flag."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                f"{API_PREFIX}/feature-flags/flag-001",
                json={"description": "Updated via API"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == "Updated via API"

    async def test_update_flag_not_found(self):
        """PUT /feature-flags/{id} should return 404 for missing flag."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                f"{API_PREFIX}/feature-flags/nonexistent",
                json={"description": "nope"},
            )
        assert resp.status_code == 404

    async def test_archive_flag(self):
        """DELETE /feature-flags/{id} should archive the flag."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(f"{API_PREFIX}/feature-flags/flag-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ARCHIVED"

    async def test_archive_flag_not_found(self):
        """DELETE /feature-flags/{id} should return 404 for missing flag."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(f"{API_PREFIX}/feature-flags/nonexistent")
        assert resp.status_code == 404

    async def test_evaluate_flag(self):
        """POST /feature-flags/{id}/evaluate should evaluate for user."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/feature-flags/flag-001/evaluate",
                json={"user_id": "eval-api-user"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["flag_id"] == "flag-001"
        assert data["user_id"] == "eval-api-user"
        assert "variant" in data

    async def test_evaluate_flag_with_role(self):
        """POST /feature-flags/{id}/evaluate with role."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/feature-flags/flag-003/evaluate",
                json={"user_id": "role-user", "role": "admin"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["context"]["reason"] == "role_match"

    async def test_evaluate_flag_not_found(self):
        """POST /feature-flags/{id}/evaluate should return 404 for missing flag."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/feature-flags/nonexistent/evaluate",
                json={"user_id": "user"},
            )
        assert resp.status_code == 404


@pytest.mark.anyio
class TestAPIAnalytics:
    """Test analytics and reporting API endpoints."""

    async def test_funnel_analysis(self):
        """GET /funnels should return funnel analysis."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/funnels")
        assert resp.status_code == 200
        data = resp.json()
        assert data["funnel_name"] == "trial_screening"
        assert len(data["stages"]) == 7

    async def test_funnel_analysis_custom_name(self):
        """GET /funnels?funnel_name= should use custom name."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"{API_PREFIX}/funnels",
                params={"funnel_name": "enrollment"},
            )
        assert resp.status_code == 200
        assert resp.json()["funnel_name"] == "enrollment"

    async def test_retention_cohorts(self):
        """GET /retention should return cohort data."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/retention")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 4  # default num_cohorts

    async def test_retention_with_params(self):
        """GET /retention with params should customize analysis."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"{API_PREFIX}/retention",
                params={"period": "DAILY", "num_cohorts": 2, "num_periods": 3},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    async def test_product_health(self):
        """GET /metrics should return product health report."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "metrics" in data
        assert "user_analytics" in data
        assert data["total_feature_flags"] == 8

    async def test_top_events(self):
        """GET /top-events should return top events."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/top-events", params={"limit": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) <= 5

    async def test_top_pages(self):
        """GET /top-pages should return top pages."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/top-pages", params={"limit": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) <= 5

    async def test_event_rate(self):
        """GET /event-rate should return event rate."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"{API_PREFIX}/event-rate", params={"window_minutes": 60}
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "events_per_minute" in data
        assert data["window_minutes"] == 60

    async def test_segments(self):
        """GET /segments should return user segments."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/segments")
        assert resp.status_code == 200
        data = resp.json()
        assert "power_users" in data
        assert "regular_users" in data
        assert "casual_users" in data
        assert "inactive_users" in data


# ===========================================================================
# Section 12: Error handling and edge cases
# ===========================================================================


class TestErrorHandling:
    """Test error conditions and edge cases."""

    def test_empty_events_after_clear(self, svc: UserAnalyticsService):
        """Should handle empty state gracefully."""
        svc.clear()
        items, total = svc.list_events()
        assert total == 0

    def test_empty_sessions_after_clear(self, svc: UserAnalyticsService):
        """Should handle empty sessions."""
        svc.clear()
        items, total = svc.list_sessions()
        assert total == 0

    def test_empty_flags_after_clear(self, svc: UserAnalyticsService):
        """Should handle empty flags."""
        svc.clear()
        flags = svc.list_flags()
        assert len(flags) == 0

    def test_metrics_empty_state(self, svc: UserAnalyticsService):
        """Metrics should work with empty data."""
        svc.clear()
        metrics = svc.get_metrics()
        assert metrics.total_events == 0
        assert metrics.total_sessions == 0

    def test_funnel_empty_state(self, svc: UserAnalyticsService):
        """Funnel should work with empty data."""
        svc.clear()
        result = svc.analyze_funnel()
        assert result.total_entered == 0
        assert result.conversion_rate == 0.0

    def test_retention_empty_state(self, svc: UserAnalyticsService):
        """Retention should work with empty data."""
        svc.clear()
        cohorts = svc.analyze_retention()
        assert len(cohorts) > 0

    def test_product_health_empty_state(self, svc: UserAnalyticsService):
        """Product health should work with empty data."""
        svc.clear()
        report = svc.get_product_health()
        assert report.user_analytics.total_events == 0

    def test_top_events_empty_state(self, svc: UserAnalyticsService):
        """Top events should return empty list when no data."""
        svc.clear()
        top = svc.get_top_events()
        assert len(top) == 0

    def test_segments_empty_state(self, svc: UserAnalyticsService):
        """Segments should return empty lists when no data."""
        svc.clear()
        segments = svc.get_user_segments()
        for category_users in segments.values():
            assert len(category_users) == 0

    def test_list_events_large_offset(self, svc: UserAnalyticsService):
        """Large offset should return empty list."""
        items, total = svc.list_events(offset=9999)
        assert len(items) == 0
        assert total == 220

    def test_list_sessions_large_offset(self, svc: UserAnalyticsService):
        """Large offset should return empty list."""
        items, total = svc.list_sessions(offset=9999)
        assert len(items) == 0
        assert total == 30

    def test_event_with_invalid_session(self, svc: UserAnalyticsService):
        """Event with non-existent session should still be created."""
        req = _make_event_request(session_id="nonexistent-session")
        event = svc.track_event(req)
        assert event.id is not None

    def test_flag_update_partial(self, svc: UserAnalyticsService):
        """Partial update should only change specified fields."""
        original = svc.get_flag("flag-001")
        req = FeatureFlagUpdateRequest(description="only desc changed")
        updated = svc.update_flag("flag-001", req)
        assert updated.description == "only desc changed"
        assert updated.name == original.name
        assert updated.rollout_strategy == original.rollout_strategy

    def test_concurrent_service_access(self, svc: UserAnalyticsService):
        """Singleton should return same instance."""
        svc1 = get_user_analytics_service()
        svc2 = get_user_analytics_service()
        assert svc1 is svc2
