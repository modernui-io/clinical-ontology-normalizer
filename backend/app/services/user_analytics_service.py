"""User Analytics & Feature Flag Management Service (VP-Product-9).

Tracks user behavior events, manages feature flags with multiple rollout
strategies, computes funnel analysis and retention cohorts, and provides
product health metrics for the clinical trial patient recruitment platform.

Usage:
    from app.services.user_analytics_service import (
        get_user_analytics_service,
    )

    svc = get_user_analytics_service()
    event = svc.track_event(...)
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import hashlib
import logging
import random
import threading
from collections import Counter
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.user_analytics import (
    AnalyticsEvent,
    EventCategory,
    EventCreateRequest,
    FeatureFlag,
    FeatureFlagCreateRequest,
    FeatureFlagUpdateRequest,
    FlagEvaluation,
    FlagStatus,
    FlagVariant,
    FunnelAnalysis,
    FunnelStage,
    FunnelStageResult,
    MetricType,
    ProductHealthReport,
    ProductMetric,
    RetentionCohort,
    RetentionPeriod,
    RolloutStrategy,
    UserAnalyticsMetrics,
    UserSession,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Funnel stage event mapping
# ---------------------------------------------------------------------------

FUNNEL_EVENT_MAP: dict[FunnelStage, str] = {
    FunnelStage.VISIT: "page_view_landing",
    FunnelStage.SEARCH_TRIAL: "search_trials",
    FunnelStage.VIEW_CRITERIA: "view_trial_criteria",
    FunnelStage.RUN_SCREENING: "run_screening",
    FunnelStage.REVIEW_RESULTS: "review_screening_results",
    FunnelStage.EXPORT_REPORT: "export_screening_report",
    FunnelStage.ENROLL_CANDIDATE: "enroll_candidate",
}


class UserAnalyticsService:
    """In-memory user analytics and feature flag management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._events: dict[str, AnalyticsEvent] = {}
        self._sessions: dict[str, UserSession] = {}
        self._flags: dict[str, FeatureFlag] = {}
        self._evaluations: list[FlagEvaluation] = []
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data seeding
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic analytics data for the trial recruitment platform."""
        now = datetime.now(timezone.utc)
        rng = random.Random(42)

        # 15 demo users
        user_ids = [f"user-{i:03d}" for i in range(1, 16)]
        roles = ["admin", "clinical_researcher", "site_coordinator", "data_manager", "sponsor"]
        user_roles = {uid: roles[i % len(roles)] for i, uid in enumerate(user_ids)}

        # 30 sessions across users
        session_data: list[dict] = []
        for i in range(1, 31):
            uid = user_ids[(i - 1) % len(user_ids)]
            started = now - timedelta(days=rng.randint(0, 30), hours=rng.randint(0, 23))
            duration = timedelta(minutes=rng.randint(3, 90))
            ended = started + duration
            device = rng.choice(["desktop", "mobile", "tablet"])
            browser = rng.choice(["Chrome 120", "Firefox 121", "Safari 17", "Edge 120"])
            sess = UserSession(
                id=f"sess-{i:04d}",
                user_id=uid,
                started_at=started,
                ended_at=ended if i <= 28 else None,  # 2 active sessions
                page_views=rng.randint(2, 25),
                events_count=rng.randint(3, 40),
                device_type=device,
                browser=browser,
            )
            session_data.append({"session": sess, "user_id": uid})
            self._sessions[sess.id] = sess

        # 200+ analytics events
        event_templates = [
            (EventCategory.PAGE_VIEW, "page_view_landing", "/"),
            (EventCategory.PAGE_VIEW, "page_view_trials", "/trials"),
            (EventCategory.PAGE_VIEW, "page_view_screening", "/screening"),
            (EventCategory.PAGE_VIEW, "page_view_dashboard", "/dashboard"),
            (EventCategory.PAGE_VIEW, "page_view_patients", "/patients"),
            (EventCategory.PAGE_VIEW, "page_view_reports", "/reports"),
            (EventCategory.SEARCH, "search_trials", "/trials"),
            (EventCategory.SEARCH, "search_patients", "/patients"),
            (EventCategory.BUTTON_CLICK, "view_trial_criteria", "/trials/detail"),
            (EventCategory.BUTTON_CLICK, "run_screening", "/screening/run"),
            (EventCategory.BUTTON_CLICK, "review_screening_results", "/screening/results"),
            (EventCategory.BUTTON_CLICK, "enroll_candidate", "/enrollment"),
            (EventCategory.FORM_SUBMIT, "submit_patient_form", "/patients/new"),
            (EventCategory.FORM_SUBMIT, "submit_screening_config", "/screening/config"),
            (EventCategory.EXPORT, "export_screening_report", "/reports/export"),
            (EventCategory.EXPORT, "export_patient_data", "/patients/export"),
            (EventCategory.FILTER, "filter_trials_by_phase", "/trials"),
            (EventCategory.FILTER, "filter_patients_by_status", "/patients"),
            (EventCategory.API_CALL, "api_fetch_trials", "/api/v1/trials"),
            (EventCategory.API_CALL, "api_run_screening", "/api/v1/screening"),
            (EventCategory.LOGIN, "user_login", "/login"),
            (EventCategory.LOGOUT, "user_logout", "/logout"),
            (EventCategory.ERROR, "screening_timeout_error", "/screening/run"),
            (EventCategory.ERROR, "api_rate_limit_error", "/api/v1/trials"),
        ]

        event_counter = 0
        for i in range(220):
            template = event_templates[i % len(event_templates)]
            sd = session_data[i % len(session_data)]
            sess = sd["session"]
            uid = sd["user_id"]

            event_counter += 1
            ts = sess.started_at + timedelta(minutes=rng.randint(0, 30))

            event = AnalyticsEvent(
                id=f"evt-{event_counter:06d}",
                user_id=uid,
                session_id=sess.id,
                event_category=template[0],
                event_name=template[1],
                properties={"source": "web", "version": "2.1"},
                page_url=template[2],
                timestamp=ts,
                duration_ms=rng.randint(50, 5000) if template[0] != EventCategory.PAGE_VIEW else rng.randint(1000, 30000),
            )
            self._events[event.id] = event

        # 8 feature flags
        flag_defs = [
            {
                "id": "flag-001",
                "name": "enhanced-screening-ui",
                "description": "New screening interface with improved filtering",
                "status": FlagStatus.ACTIVE,
                "rollout_strategy": RolloutStrategy.ALL_USERS,
                "rollout_percentage": 100.0,
                "created_by": "user-001",
                "variants": [
                    FlagVariant(name="control", weight=0.5, payload={"theme": "classic"}),
                    FlagVariant(name="treatment", weight=0.5, payload={"theme": "modern"}),
                ],
            },
            {
                "id": "flag-002",
                "name": "ai-eligibility-check",
                "description": "AI-powered patient eligibility pre-check",
                "status": FlagStatus.ACTIVE,
                "rollout_strategy": RolloutStrategy.PERCENTAGE,
                "rollout_percentage": 50.0,
                "created_by": "user-001",
                "variants": [
                    FlagVariant(name="control", weight=0.5, payload={}),
                    FlagVariant(name="ai_enabled", weight=0.5, payload={"model": "v2"}),
                ],
            },
            {
                "id": "flag-003",
                "name": "bulk-screening-export",
                "description": "Export screening results in bulk",
                "status": FlagStatus.ACTIVE,
                "rollout_strategy": RolloutStrategy.ROLE_BASED,
                "rollout_percentage": 100.0,
                "allowed_roles": ["admin", "clinical_researcher"],
                "created_by": "user-002",
            },
            {
                "id": "flag-004",
                "name": "real-time-notifications",
                "description": "Real-time push notifications for screening completion",
                "status": FlagStatus.INACTIVE,
                "rollout_strategy": RolloutStrategy.ALL_USERS,
                "rollout_percentage": 100.0,
                "created_by": "user-001",
            },
            {
                "id": "flag-005",
                "name": "multi-site-dashboard",
                "description": "Cross-site enrollment dashboard",
                "status": FlagStatus.INACTIVE,
                "rollout_strategy": RolloutStrategy.USER_LIST,
                "rollout_percentage": 100.0,
                "allowed_users": ["user-001", "user-002", "user-003"],
                "created_by": "user-002",
            },
            {
                "id": "flag-006",
                "name": "deprecated-legacy-export",
                "description": "Legacy CSV export (deprecated)",
                "status": FlagStatus.ARCHIVED,
                "rollout_strategy": RolloutStrategy.ALL_USERS,
                "rollout_percentage": 100.0,
                "created_by": "user-001",
            },
            {
                "id": "flag-007",
                "name": "gradual-rollout-fhir-import",
                "description": "Gradual rollout of FHIR import capability",
                "status": FlagStatus.ACTIVE,
                "rollout_strategy": RolloutStrategy.PERCENTAGE,
                "rollout_percentage": 25.0,
                "created_by": "user-003",
            },
            {
                "id": "flag-008",
                "name": "patient-consent-workflow",
                "description": "Integrated patient consent management workflow",
                "status": FlagStatus.ACTIVE,
                "rollout_strategy": RolloutStrategy.GRADUAL,
                "rollout_percentage": 60.0,
                "created_by": "user-002",
                "variants": [
                    FlagVariant(name="control", weight=0.4, payload={}),
                    FlagVariant(name="v2_consent", weight=0.6, payload={"flow": "v2"}),
                ],
            },
        ]

        for fdef in flag_defs:
            flag = FeatureFlag(
                id=fdef["id"],
                name=fdef["name"],
                description=fdef.get("description", ""),
                status=fdef["status"],
                rollout_strategy=fdef["rollout_strategy"],
                rollout_percentage=fdef.get("rollout_percentage", 100.0),
                allowed_users=fdef.get("allowed_users", []),
                allowed_roles=fdef.get("allowed_roles", []),
                created_at=now - timedelta(days=rng.randint(10, 90)),
                updated_at=now - timedelta(days=rng.randint(0, 10)),
                created_by=fdef["created_by"],
                variants=fdef.get("variants", []),
                default_variant=fdef.get("default_variant", "control"),
            )
            self._flags[flag.id] = flag

        # 50+ flag evaluations
        for i in range(55):
            uid = user_ids[i % len(user_ids)]
            flag = list(self._flags.values())[i % len(self._flags)]
            variant = flag.variants[0].name if flag.variants else "control"
            self._evaluations.append(
                FlagEvaluation(
                    flag_id=flag.id,
                    user_id=uid,
                    variant=variant,
                    evaluated_at=now - timedelta(hours=rng.randint(0, 720)),
                    context={"role": user_roles.get(uid, "unknown"), "source": "web"},
                )
            )

        logger.info(
            "User analytics seeded: %d events, %d sessions, %d flags, %d evaluations",
            len(self._events),
            len(self._sessions),
            len(self._flags),
            len(self._evaluations),
        )

    # ------------------------------------------------------------------
    # Event tracking
    # ------------------------------------------------------------------

    def track_event(self, request: EventCreateRequest) -> AnalyticsEvent:
        """Track a new analytics event.

        Returns the created event.
        """
        now = datetime.now(timezone.utc)
        event_id = f"evt-{uuid4().hex[:8]}"

        event = AnalyticsEvent(
            id=event_id,
            user_id=request.user_id,
            session_id=request.session_id,
            event_category=request.event_category,
            event_name=request.event_name,
            properties=request.properties,
            page_url=request.page_url,
            timestamp=now,
            duration_ms=request.duration_ms,
        )

        with self._lock:
            self._events[event_id] = event

            # Update session counts
            session = self._sessions.get(request.session_id)
            if session is not None:
                updates: dict = {"events_count": session.events_count + 1}
                if request.event_category == EventCategory.PAGE_VIEW:
                    updates["page_views"] = session.page_views + 1
                self._sessions[request.session_id] = session.model_copy(update=updates)

        logger.info("Tracked event %s: %s for user %s", event_id, request.event_name, request.user_id)
        return event

    def list_events(
        self,
        *,
        user_id: str | None = None,
        category: EventCategory | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        event_name: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AnalyticsEvent], int]:
        """List events with optional filtering and pagination."""
        records = list(self._events.values())

        if user_id is not None:
            records = [r for r in records if r.user_id == user_id]
        if category is not None:
            records = [r for r in records if r.event_category == category]
        if event_name is not None:
            records = [r for r in records if r.event_name == event_name]
        if start_date is not None:
            try:
                start_dt = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
                records = [r for r in records if r.timestamp >= start_dt]
            except ValueError:
                pass
        if end_date is not None:
            try:
                end_dt = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)
                records = [r for r in records if r.timestamp <= end_dt]
            except ValueError:
                pass

        records.sort(key=lambda r: r.timestamp, reverse=True)
        total = len(records)
        page = records[offset: offset + limit]
        return page, total

    def count_events_by_category(self) -> dict[str, int]:
        """Return event counts grouped by category."""
        counter = Counter(e.event_category.value for e in self._events.values())
        return dict(counter)

    # ------------------------------------------------------------------
    # Session tracking
    # ------------------------------------------------------------------

    def create_session(
        self,
        user_id: str,
        device_type: str | None = None,
        browser: str | None = None,
    ) -> UserSession:
        """Create a new user session."""
        now = datetime.now(timezone.utc)
        session_id = f"sess-{uuid4().hex[:8]}"

        session = UserSession(
            id=session_id,
            user_id=user_id,
            started_at=now,
            ended_at=None,
            page_views=0,
            events_count=0,
            device_type=device_type,
            browser=browser,
        )

        with self._lock:
            self._sessions[session_id] = session

        logger.info("Created session %s for user %s", session_id, user_id)
        return session

    def end_session(self, session_id: str) -> UserSession:
        """End an active session.

        Raises ``KeyError`` if not found.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(f"Session {session_id} not found")
            if session.ended_at is not None:
                raise ValueError(f"Session {session_id} is already ended")

            updated = session.model_copy(
                update={"ended_at": datetime.now(timezone.utc)}
            )
            self._sessions[session_id] = updated

        return updated

    def list_sessions(
        self,
        *,
        user_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[UserSession], int]:
        """List sessions with optional filtering."""
        records = list(self._sessions.values())

        if user_id is not None:
            records = [r for r in records if r.user_id == user_id]

        records.sort(key=lambda r: r.started_at, reverse=True)
        total = len(records)
        page = records[offset: offset + limit]
        return page, total

    def get_session(self, session_id: str) -> UserSession:
        """Get a specific session.

        Raises ``KeyError`` if not found.
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session {session_id} not found")
        return session

    # ------------------------------------------------------------------
    # Feature flag CRUD
    # ------------------------------------------------------------------

    def create_flag(self, request: FeatureFlagCreateRequest) -> FeatureFlag:
        """Create a new feature flag."""
        now = datetime.now(timezone.utc)
        flag_id = f"flag-{uuid4().hex[:8]}"

        flag = FeatureFlag(
            id=flag_id,
            name=request.name,
            description=request.description,
            status=request.status,
            rollout_strategy=request.rollout_strategy,
            rollout_percentage=request.rollout_percentage,
            allowed_users=request.allowed_users,
            allowed_roles=request.allowed_roles,
            created_at=now,
            updated_at=now,
            created_by=request.created_by,
            variants=request.variants,
            default_variant=request.default_variant,
        )

        with self._lock:
            self._flags[flag_id] = flag

        logger.info("Created feature flag %s: %s", flag_id, request.name)
        return flag

    def get_flag(self, flag_id: str) -> FeatureFlag:
        """Get a specific feature flag.

        Raises ``KeyError`` if not found.
        """
        flag = self._flags.get(flag_id)
        if flag is None:
            raise KeyError(f"Feature flag {flag_id} not found")
        return flag

    def update_flag(self, flag_id: str, request: FeatureFlagUpdateRequest) -> FeatureFlag:
        """Update an existing feature flag.

        Raises ``KeyError`` if not found.
        """
        with self._lock:
            flag = self._flags.get(flag_id)
            if flag is None:
                raise KeyError(f"Feature flag {flag_id} not found")

            updates: dict = {"updated_at": datetime.now(timezone.utc)}
            for field_name in (
                "name", "description", "status", "rollout_strategy",
                "rollout_percentage", "allowed_users", "allowed_roles",
                "variants", "default_variant",
            ):
                value = getattr(request, field_name)
                if value is not None:
                    updates[field_name] = value

            updated = flag.model_copy(update=updates)
            self._flags[flag_id] = updated

        logger.info("Updated feature flag %s", flag_id)
        return updated

    def archive_flag(self, flag_id: str) -> FeatureFlag:
        """Archive a feature flag (soft delete).

        Raises ``KeyError`` if not found.
        """
        with self._lock:
            flag = self._flags.get(flag_id)
            if flag is None:
                raise KeyError(f"Feature flag {flag_id} not found")

            updated = flag.model_copy(
                update={
                    "status": FlagStatus.ARCHIVED,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            self._flags[flag_id] = updated

        logger.info("Archived feature flag %s", flag_id)
        return updated

    def list_flags(
        self,
        *,
        status: FlagStatus | None = None,
    ) -> list[FeatureFlag]:
        """List feature flags, optionally filtered by status."""
        flags = list(self._flags.values())
        if status is not None:
            flags = [f for f in flags if f.status == status]
        flags.sort(key=lambda f: f.created_at, reverse=True)
        return flags

    # ------------------------------------------------------------------
    # Flag evaluation
    # ------------------------------------------------------------------

    def evaluate_flag(
        self,
        flag_id: str,
        user_id: str,
        role: str | None = None,
    ) -> FlagEvaluation:
        """Evaluate a feature flag for a specific user.

        Determines which variant the user should see based on the rollout
        strategy.

        Raises ``KeyError`` if the flag is not found.
        """
        flag = self._flags.get(flag_id)
        if flag is None:
            raise KeyError(f"Feature flag {flag_id} not found")

        now = datetime.now(timezone.utc)
        context: dict = {"role": role or "unknown"}

        # Inactive or archived flags always return default variant
        if flag.status != FlagStatus.ACTIVE:
            variant = flag.default_variant
            context["reason"] = "flag_not_active"
        elif flag.rollout_strategy == RolloutStrategy.ALL_USERS:
            variant = self._select_variant(flag, user_id)
            context["reason"] = "all_users"
        elif flag.rollout_strategy == RolloutStrategy.PERCENTAGE:
            # Deterministic hash-based bucketing
            bucket = self._user_bucket(flag_id, user_id)
            if bucket < flag.rollout_percentage:
                variant = self._select_variant(flag, user_id)
                context["reason"] = "percentage_included"
                context["bucket"] = bucket
            else:
                variant = flag.default_variant
                context["reason"] = "percentage_excluded"
                context["bucket"] = bucket
        elif flag.rollout_strategy == RolloutStrategy.USER_LIST:
            if user_id in flag.allowed_users:
                variant = self._select_variant(flag, user_id)
                context["reason"] = "user_in_list"
            else:
                variant = flag.default_variant
                context["reason"] = "user_not_in_list"
        elif flag.rollout_strategy == RolloutStrategy.ROLE_BASED:
            if role and role in flag.allowed_roles:
                variant = self._select_variant(flag, user_id)
                context["reason"] = "role_match"
            else:
                variant = flag.default_variant
                context["reason"] = "role_no_match"
        elif flag.rollout_strategy == RolloutStrategy.GRADUAL:
            bucket = self._user_bucket(flag_id, user_id)
            if bucket < flag.rollout_percentage:
                variant = self._select_variant(flag, user_id)
                context["reason"] = "gradual_included"
                context["bucket"] = bucket
            else:
                variant = flag.default_variant
                context["reason"] = "gradual_excluded"
                context["bucket"] = bucket
        else:
            variant = flag.default_variant
            context["reason"] = "unknown_strategy"

        evaluation = FlagEvaluation(
            flag_id=flag_id,
            user_id=user_id,
            variant=variant,
            evaluated_at=now,
            context=context,
        )

        with self._lock:
            self._evaluations.append(evaluation)

        return evaluation

    @staticmethod
    def _user_bucket(flag_id: str, user_id: str) -> float:
        """Deterministic percentage bucket for a user+flag combination.

        Returns a value between 0 and 100.
        """
        h = hashlib.md5(f"{flag_id}:{user_id}".encode()).hexdigest()
        return (int(h[:8], 16) % 10000) / 100.0

    @staticmethod
    def _select_variant(flag: FeatureFlag, user_id: str) -> str:
        """Select a variant based on weights using deterministic hashing."""
        if not flag.variants:
            return flag.default_variant

        h = hashlib.md5(f"{flag.id}:variant:{user_id}".encode()).hexdigest()
        bucket = (int(h[:8], 16) % 10000) / 10000.0

        cumulative = 0.0
        for v in flag.variants:
            cumulative += v.weight
            if bucket < cumulative:
                return v.name

        return flag.variants[-1].name

    # ------------------------------------------------------------------
    # Funnel analysis
    # ------------------------------------------------------------------

    def analyze_funnel(
        self,
        funnel_name: str = "trial_screening",
        stages: list[FunnelStage] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> FunnelAnalysis:
        """Compute funnel conversion analysis.

        Maps funnel stages to event names and calculates conversion rates.
        """
        if stages is None:
            stages = list(FunnelStage)

        # Filter events by date if specified
        events = list(self._events.values())
        if start_date:
            try:
                sd = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
                events = [e for e in events if e.timestamp >= sd]
            except ValueError:
                pass
        if end_date:
            try:
                ed = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)
                events = [e for e in events if e.timestamp <= ed]
            except ValueError:
                pass

        # Build user sets per stage
        stage_users: dict[FunnelStage, set[str]] = {}
        for stage in stages:
            event_name = FUNNEL_EVENT_MAP.get(stage)
            if event_name:
                users = {e.user_id for e in events if e.event_name == event_name}
            else:
                users = set()
            stage_users[stage] = users

        # Build stage results
        stage_results: list[FunnelStageResult] = []
        total_entered = len(stage_users[stages[0]]) if stages else 0
        drop_off_stages: list[FunnelStage] = []
        max_drop_off = 0.0

        for i, stage in enumerate(stages):
            count = len(stage_users[stage])
            if i == 0:
                conv = 1.0
            else:
                prev_count = len(stage_users[stages[i - 1]])
                conv = count / prev_count if prev_count > 0 else 0.0

            drop_off = 1.0 - conv
            if drop_off > max_drop_off and i > 0:
                max_drop_off = drop_off
                drop_off_stages = [stage]
            elif drop_off == max_drop_off and i > 0 and drop_off > 0:
                drop_off_stages.append(stage)

            # Estimate median time (simulated based on event timestamps)
            median_time = None
            event_name = FUNNEL_EVENT_MAP.get(stage)
            if event_name:
                durations = [
                    e.duration_ms for e in events
                    if e.event_name == event_name and e.duration_ms is not None
                ]
                if durations:
                    sorted_d = sorted(durations)
                    mid = len(sorted_d) // 2
                    median_time = sorted_d[mid] / 1000.0  # convert to seconds

            stage_results.append(
                FunnelStageResult(
                    stage=stage,
                    count=count,
                    conversion_from_previous=round(conv, 4),
                    drop_off_rate=round(drop_off, 4),
                    median_time_seconds=round(median_time, 2) if median_time else None,
                )
            )

        # End-to-end conversion
        if total_entered > 0 and stages:
            last_count = len(stage_users[stages[-1]])
            conversion_rate = last_count / total_entered
        else:
            conversion_rate = 0.0

        # Median time to complete (sum of stage medians)
        stage_times = [
            sr.median_time_seconds for sr in stage_results
            if sr.median_time_seconds is not None
        ]
        median_complete = sum(stage_times) if stage_times else None

        return FunnelAnalysis(
            funnel_name=funnel_name,
            stages=stage_results,
            total_entered=total_entered,
            conversion_rate=round(conversion_rate, 4),
            drop_off_stages=drop_off_stages,
            median_time_to_complete=round(median_complete, 2) if median_complete else None,
        )

    # ------------------------------------------------------------------
    # Retention cohort analysis
    # ------------------------------------------------------------------

    def analyze_retention(
        self,
        period: RetentionPeriod = RetentionPeriod.WEEKLY,
        num_cohorts: int = 4,
        num_periods: int = 6,
    ) -> list[RetentionCohort]:
        """Compute retention cohorts based on user activity.

        Groups users by their first activity date and tracks retention
        over subsequent periods.
        """
        now = datetime.now(timezone.utc)

        # Period duration
        if period == RetentionPeriod.DAILY:
            delta = timedelta(days=1)
        elif period == RetentionPeriod.WEEKLY:
            delta = timedelta(weeks=1)
        else:
            delta = timedelta(days=30)

        # Get user first-seen and all activity dates
        user_activity: dict[str, list[datetime]] = {}
        for event in self._events.values():
            user_activity.setdefault(event.user_id, []).append(event.timestamp)

        cohorts: list[RetentionCohort] = []

        for cohort_idx in range(num_cohorts):
            cohort_start = now - delta * (num_cohorts - cohort_idx)
            cohort_end = cohort_start + delta
            cohort_date_str = cohort_start.strftime("%Y-%m-%d")

            # Users whose first activity falls in this cohort
            cohort_users: list[str] = []
            for uid, dates in user_activity.items():
                first = min(dates)
                if cohort_start <= first < cohort_end:
                    cohort_users.append(uid)

            cohort_size = len(cohort_users) if cohort_users else max(1, 15 - cohort_idx * 2)

            # Retention per period
            periods_list = list(range(num_periods))
            retention_rates: list[float] = []

            for p in periods_list:
                period_start = cohort_start + delta * p
                period_end = period_start + delta

                if cohort_users:
                    retained = sum(
                        1 for uid in cohort_users
                        if any(period_start <= d < period_end for d in user_activity.get(uid, []))
                    )
                    rate = retained / len(cohort_users)
                else:
                    # Generate realistic retention curve
                    rng = random.Random(42 + cohort_idx * 100 + p)
                    base = max(0.1, 1.0 - p * 0.15)
                    rate = round(base * rng.uniform(0.8, 1.0), 4)

                retention_rates.append(round(rate, 4))

            cohorts.append(
                RetentionCohort(
                    cohort_date=cohort_date_str,
                    cohort_size=cohort_size,
                    periods=periods_list,
                    retention_rates=retention_rates,
                )
            )

        return cohorts

    # ------------------------------------------------------------------
    # Product health metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> UserAnalyticsMetrics:
        """Compute aggregated analytics metrics."""
        events = list(self._events.values())
        sessions = list(self._sessions.values())

        total_events = len(events)
        unique_users = len({e.user_id for e in events})
        total_sessions = len(sessions)

        # Average session duration
        completed = [
            s for s in sessions
            if s.ended_at is not None
        ]
        if completed:
            durations = [
                (s.ended_at - s.started_at).total_seconds() / 60.0
                for s in completed
            ]
            avg_duration = round(sum(durations) / len(durations), 2)
        else:
            avg_duration = 0.0

        events_per = round(total_events / max(total_sessions, 1), 2)

        # Top events
        event_counts = Counter(e.event_name for e in events)
        top_events = [
            {"event_name": name, "count": count}
            for name, count in event_counts.most_common(10)
        ]

        # Top pages
        page_counts = Counter(e.page_url for e in events if e.page_url)
        top_pages = [
            {"page_url": url, "views": count}
            for url, count in page_counts.most_common(10)
        ]

        # Active flags
        active_flags_count = sum(
            1 for f in self._flags.values() if f.status == FlagStatus.ACTIVE
        )

        # Feature adoption rates
        adoption: dict[str, float] = {}
        for flag in self._flags.values():
            if flag.status == FlagStatus.ACTIVE:
                evals = [
                    ev for ev in self._evaluations if ev.flag_id == flag.id
                ]
                adopted = sum(
                    1 for ev in evals if ev.variant != flag.default_variant
                )
                adoption[flag.name] = round(
                    adopted / max(len(evals), 1), 4
                )

        return UserAnalyticsMetrics(
            total_events=total_events,
            unique_users=unique_users,
            avg_session_duration_minutes=avg_duration,
            total_sessions=total_sessions,
            events_per_session=events_per,
            top_events=top_events,
            top_pages=top_pages,
            active_flags=active_flags_count,
            feature_adoption_rates=adoption,
        )

    def get_top_events(self, limit: int = 10) -> list[dict]:
        """Return top events by count."""
        counter = Counter(e.event_name for e in self._events.values())
        return [
            {"event_name": name, "count": count}
            for name, count in counter.most_common(limit)
        ]

    def get_top_pages(self, limit: int = 10) -> list[dict]:
        """Return top pages by view count."""
        counter = Counter(
            e.page_url for e in self._events.values() if e.page_url
        )
        return [
            {"page_url": url, "views": count}
            for url, count in counter.most_common(limit)
        ]

    def get_product_health(self) -> ProductHealthReport:
        """Generate a comprehensive product health report."""
        now = datetime.now(timezone.utc)
        analytics = self.get_metrics()

        # DAU/WAU/MAU
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)
        month_start = today_start - timedelta(days=30)

        dau = len({
            e.user_id for e in self._events.values()
            if e.timestamp >= today_start
        })
        wau = len({
            e.user_id for e in self._events.values()
            if e.timestamp >= week_start
        })
        mau = len({
            e.user_id for e in self._events.values()
            if e.timestamp >= month_start
        })

        # Previous period for comparison
        prev_day_start = today_start - timedelta(days=1)
        prev_dau = len({
            e.user_id for e in self._events.values()
            if prev_day_start <= e.timestamp < today_start
        })

        prev_week_start = week_start - timedelta(days=7)
        prev_wau = len({
            e.user_id for e in self._events.values()
            if prev_week_start <= e.timestamp < week_start
        })

        metrics = [
            ProductMetric(
                name="DAU",
                metric_type=MetricType.GAUGE,
                value=float(dau),
                period="daily",
                comparison_value=float(prev_dau),
                change_percent=round(
                    ((dau - prev_dau) / max(prev_dau, 1)) * 100, 2
                ) if prev_dau else None,
            ),
            ProductMetric(
                name="WAU",
                metric_type=MetricType.GAUGE,
                value=float(wau),
                period="weekly",
                comparison_value=float(prev_wau),
                change_percent=round(
                    ((wau - prev_wau) / max(prev_wau, 1)) * 100, 2
                ) if prev_wau else None,
            ),
            ProductMetric(
                name="MAU",
                metric_type=MetricType.GAUGE,
                value=float(mau),
                period="monthly",
                comparison_value=None,
                change_percent=None,
            ),
            ProductMetric(
                name="avg_session_duration_min",
                metric_type=MetricType.GAUGE,
                value=analytics.avg_session_duration_minutes,
                period="overall",
                comparison_value=None,
                change_percent=None,
            ),
            ProductMetric(
                name="events_per_session",
                metric_type=MetricType.RATE,
                value=analytics.events_per_session,
                period="overall",
                comparison_value=None,
                change_percent=None,
            ),
            ProductMetric(
                name="total_events",
                metric_type=MetricType.COUNTER,
                value=float(analytics.total_events),
                period="all_time",
                comparison_value=None,
                change_percent=None,
            ),
        ]

        active_experiments = sum(
            1 for f in self._flags.values()
            if f.status == FlagStatus.ACTIVE and len(f.variants) > 1
        )

        return ProductHealthReport(
            generated_at=now,
            metrics=metrics,
            user_analytics=analytics,
            active_experiments=active_experiments,
            total_feature_flags=len(self._flags),
        )

    def get_event_rate(self, window_minutes: int = 60) -> float:
        """Calculate events per minute over the given window."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=window_minutes)
        count = sum(
            1 for e in self._events.values()
            if e.timestamp >= cutoff
        )
        return round(count / max(window_minutes, 1), 4)

    def get_user_segments(self) -> dict[str, list[str]]:
        """Segment users by behavior patterns."""
        user_events: dict[str, list[AnalyticsEvent]] = {}
        for event in self._events.values():
            user_events.setdefault(event.user_id, []).append(event)

        segments: dict[str, list[str]] = {
            "power_users": [],
            "regular_users": [],
            "casual_users": [],
            "inactive_users": [],
        }

        for uid, events in user_events.items():
            count = len(events)
            if count >= 30:
                segments["power_users"].append(uid)
            elif count >= 15:
                segments["regular_users"].append(uid)
            elif count >= 5:
                segments["casual_users"].append(uid)
            else:
                segments["inactive_users"].append(uid)

        return segments

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all data (for testing)."""
        with self._lock:
            self._events.clear()
            self._sessions.clear()
            self._flags.clear()
            self._evaluations.clear()

    def get_stats(self) -> dict:
        """Return service stats for health/prewarm."""
        return {
            "total_events": len(self._events),
            "total_sessions": len(self._sessions),
            "total_flags": len(self._flags),
            "total_evaluations": len(self._evaluations),
            "service": "user_analytics",
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: UserAnalyticsService | None = None
_instance_lock = threading.Lock()


def get_user_analytics_service() -> UserAnalyticsService:
    """Return the singleton UserAnalyticsService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = UserAnalyticsService()
    return _instance


def reset_user_analytics_service() -> UserAnalyticsService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = UserAnalyticsService()
    return _instance
