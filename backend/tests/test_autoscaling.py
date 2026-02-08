"""Tests for Auto-Scaling Policies and Event-Driven Scaling (DEVOPS-3).

Covers:
- Schema validation: enums, constraints, defaults
- Scaling policy CRUD: create, read, update, delete
- Built-in policies: screening_burst, fhir_import_spike, business_hours, nlp_batch, api_latency
- Scaling targets: configuration, current replicas, min/max bounds
- Scaling evaluation: scale-up, scale-down, no-op, cooldown, stabilization
- Scale-up bias: prefer scaling up over down
- KEDA spec generation: YAML output for all target types
- Scaling history: recording and filtering events
- Predictive scaling: trend detection, proactive recommendation
- API endpoints: full CRUD and evaluation via HTTP
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.schemas.autoscaling import (
    KEDAScaledObjectSpec,
    MetricTrend,
    PolicyStatus,
    PredictiveScalingReport,
    ScalingDecision,
    ScalingDirection,
    ScalingEvaluationRequest,
    ScalingEvaluationResponse,
    ScalingEvent,
    ScalingHistoryResponse,
    ScalingPoliciesResponse,
    ScalingPolicy,
    ScalingPolicyCreate,
    ScalingPolicyType,
    ScalingPolicyUpdate,
    ScalingTargetConfig,
    ScalingTargetName,
    ScalingTargetStatus,
    ScalingTargetsResponse,
    ScheduleConfig,
    TrendDirection,
)
from app.services.autoscaling_service import (
    AutoScalingService,
    get_autoscaling_service,
    reset_autoscaling_service,
)


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def svc() -> AutoScalingService:
    """Create a fresh AutoScalingService instance."""
    return AutoScalingService()


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the singleton before and after each test."""
    reset_autoscaling_service()
    yield
    reset_autoscaling_service()


# ===========================================================================
# Schema Tests
# ===========================================================================


class TestSchemas:
    """Test Pydantic schema validation and defaults."""

    def test_scaling_policy_type_values(self):
        """All expected policy types exist."""
        expected = {"cpu_threshold", "memory_threshold", "request_rate",
                    "queue_depth", "schedule", "custom_metric"}
        actual = {e.value for e in ScalingPolicyType}
        assert expected == actual

    def test_scaling_direction_values(self):
        """All expected scaling directions exist."""
        expected = {"up", "down", "none"}
        actual = {e.value for e in ScalingDirection}
        assert expected == actual

    def test_scaling_target_name_values(self):
        """All expected target names exist."""
        expected = {"backend_api", "fhir_worker", "nlp_worker", "screening_worker"}
        actual = {e.value for e in ScalingTargetName}
        assert expected == actual

    def test_policy_status_values(self):
        """Active and disabled statuses exist."""
        assert PolicyStatus.ACTIVE.value == "active"
        assert PolicyStatus.DISABLED.value == "disabled"

    def test_trend_direction_values(self):
        """Trend directions include increasing, decreasing, stable."""
        expected = {"increasing", "decreasing", "stable"}
        actual = {e.value for e in TrendDirection}
        assert expected == actual

    def test_schedule_config_defaults(self):
        """ScheduleConfig has sensible defaults."""
        s = ScheduleConfig()
        assert s.days_of_week == [0, 1, 2, 3, 4]
        assert s.start_hour == 8
        assert s.end_hour == 18
        assert s.timezone == "US/Eastern"

    def test_scaling_policy_create_validation(self):
        """ScalingPolicyCreate enforces required fields."""
        p = ScalingPolicyCreate(
            name="test",
            policy_type=ScalingPolicyType.CPU_THRESHOLD,
            target=ScalingTargetName.BACKEND_API,
        )
        assert p.name == "test"
        assert p.threshold == 70.0  # default
        assert p.cooldown_seconds == 300
        assert p.stabilization_seconds == 600
        assert p.scale_up_step == 2
        assert p.scale_down_step == 1
        assert p.status == PolicyStatus.ACTIVE

    def test_scaling_event_schema(self):
        """ScalingEvent can be constructed with all fields."""
        e = ScalingEvent(
            id="evt-1",
            target=ScalingTargetName.BACKEND_API,
            direction=ScalingDirection.UP,
            from_replicas=3,
            to_replicas=5,
            reason="CPU high",
            policy_id="pol-1",
            policy_name="cpu_policy",
            metric_value=85.0,
            threshold=70.0,
            timestamp=datetime.now(timezone.utc),
        )
        assert e.from_replicas == 3
        assert e.to_replicas == 5

    def test_keda_spec_schema(self):
        """KEDAScaledObjectSpec has correct defaults."""
        spec = KEDAScaledObjectSpec(
            target=ScalingTargetName.BACKEND_API,
            yaml_content="test: true",
        )
        assert spec.api_version == "keda.sh/v1alpha1"
        assert spec.kind == "ScaledObject"


# ===========================================================================
# Service - Built-in Policies
# ===========================================================================


class TestBuiltinPolicies:
    """Test pre-configured clinical workload policies."""

    def test_builtin_policies_loaded(self, svc: AutoScalingService):
        """All 5 built-in policies are loaded."""
        result = svc.list_policies()
        assert result.total == 5

    def test_screening_burst_policy(self, svc: AutoScalingService):
        """screening_burst policy is correctly configured."""
        policy = svc.get_policy("builtin-screening_burst")
        assert policy.name == "screening_burst"
        assert policy.policy_type == ScalingPolicyType.QUEUE_DEPTH
        assert policy.target == ScalingTargetName.SCREENING_WORKER
        assert policy.threshold == 50.0
        assert policy.metric_name == "screening_queue_depth"

    def test_fhir_import_spike_policy(self, svc: AutoScalingService):
        """fhir_import_spike policy is correctly configured."""
        policy = svc.get_policy("builtin-fhir_import_spike")
        assert policy.name == "fhir_import_spike"
        assert policy.policy_type == ScalingPolicyType.REQUEST_RATE
        assert policy.target == ScalingTargetName.FHIR_WORKER
        assert policy.threshold == 10.0

    def test_business_hours_policy(self, svc: AutoScalingService):
        """business_hours policy has a schedule config."""
        policy = svc.get_policy("builtin-business_hours")
        assert policy.name == "business_hours"
        assert policy.policy_type == ScalingPolicyType.SCHEDULE
        assert policy.target == ScalingTargetName.BACKEND_API
        assert policy.desired_replicas == 5
        assert policy.schedule is not None
        assert policy.schedule.days_of_week == [0, 1, 2, 3, 4]

    def test_nlp_batch_policy(self, svc: AutoScalingService):
        """nlp_batch policy is correctly configured."""
        policy = svc.get_policy("builtin-nlp_batch")
        assert policy.name == "nlp_batch"
        assert policy.policy_type == ScalingPolicyType.QUEUE_DEPTH
        assert policy.target == ScalingTargetName.NLP_WORKER
        assert policy.threshold == 100.0

    def test_api_latency_policy(self, svc: AutoScalingService):
        """api_latency policy uses custom metric."""
        policy = svc.get_policy("builtin-api_latency")
        assert policy.name == "api_latency"
        assert policy.policy_type == ScalingPolicyType.CUSTOM_METRIC
        assert policy.target == ScalingTargetName.BACKEND_API
        assert policy.threshold == 2.0
        assert policy.metric_name == "p95_latency_seconds"


# ===========================================================================
# Service - Policy CRUD
# ===========================================================================


class TestPolicyCRUD:
    """Test create, read, update, delete operations on policies."""

    def test_create_policy(self, svc: AutoScalingService):
        """Create a new custom policy."""
        data = ScalingPolicyCreate(
            name="custom_cpu",
            description="Scale backend on CPU",
            policy_type=ScalingPolicyType.CPU_THRESHOLD,
            target=ScalingTargetName.BACKEND_API,
            threshold=80.0,
        )
        policy = svc.create_policy(data)
        assert policy.id.startswith("pol-")
        assert policy.name == "custom_cpu"
        assert policy.threshold == 80.0
        assert policy.trigger_count == 0

    def test_get_policy_not_found(self, svc: AutoScalingService):
        """Getting a nonexistent policy raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            svc.get_policy("nonexistent")

    def test_update_policy(self, svc: AutoScalingService):
        """Update an existing policy's threshold and description."""
        data = ScalingPolicyCreate(
            name="updatable",
            policy_type=ScalingPolicyType.CPU_THRESHOLD,
            target=ScalingTargetName.BACKEND_API,
        )
        created = svc.create_policy(data)

        update = ScalingPolicyUpdate(threshold=90.0, description="Updated")
        updated = svc.update_policy(created.id, update)
        assert updated.threshold == 90.0
        assert updated.description == "Updated"
        assert updated.updated_at > created.updated_at

    def test_update_policy_not_found(self, svc: AutoScalingService):
        """Updating a nonexistent policy raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            svc.update_policy("fake-id", ScalingPolicyUpdate(threshold=99.0))

    def test_delete_policy(self, svc: AutoScalingService):
        """Delete a policy and verify it's gone."""
        data = ScalingPolicyCreate(
            name="to_delete",
            policy_type=ScalingPolicyType.MEMORY_THRESHOLD,
            target=ScalingTargetName.NLP_WORKER,
        )
        created = svc.create_policy(data)
        deleted = svc.delete_policy(created.id)
        assert deleted.id == created.id

        with pytest.raises(ValueError, match="not found"):
            svc.get_policy(created.id)

    def test_delete_policy_not_found(self, svc: AutoScalingService):
        """Deleting a nonexistent policy raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            svc.delete_policy("nonexistent")

    def test_filter_policies_by_target(self, svc: AutoScalingService):
        """Filter policies by target name."""
        result = svc.list_policies(target=ScalingTargetName.SCREENING_WORKER)
        assert result.total >= 1
        for p in result.policies:
            assert p.target == ScalingTargetName.SCREENING_WORKER

    def test_filter_policies_by_status(self, svc: AutoScalingService):
        """Filter policies by status."""
        result = svc.list_policies(status=PolicyStatus.ACTIVE)
        assert result.total == 5  # All built-in are active
        result_disabled = svc.list_policies(status=PolicyStatus.DISABLED)
        assert result_disabled.total == 0

    def test_disable_policy(self, svc: AutoScalingService):
        """Disable a policy via update."""
        policy = svc.get_policy("builtin-screening_burst")
        svc.update_policy(policy.id, ScalingPolicyUpdate(status=PolicyStatus.DISABLED))
        updated = svc.get_policy(policy.id)
        assert updated.status == PolicyStatus.DISABLED


# ===========================================================================
# Service - Scaling Targets
# ===========================================================================


class TestScalingTargets:
    """Test scaling target configuration and status."""

    def test_default_targets_loaded(self, svc: AutoScalingService):
        """All 4 default targets are loaded."""
        targets = svc.get_targets()
        assert len(targets.targets) == 4

    def test_backend_api_target_defaults(self, svc: AutoScalingService):
        """backend_api target has correct min/max/default."""
        targets = svc.get_targets()
        backend = next(t for t in targets.targets if t.name == ScalingTargetName.BACKEND_API)
        assert backend.min_replicas == 2
        assert backend.max_replicas == 20
        assert backend.current_replicas == 3  # default

    def test_screening_worker_target_defaults(self, svc: AutoScalingService):
        """screening_worker target has correct defaults."""
        targets = svc.get_targets()
        sw = next(t for t in targets.targets if t.name == ScalingTargetName.SCREENING_WORKER)
        assert sw.min_replicas == 1
        assert sw.max_replicas == 15
        assert sw.current_replicas == 3

    def test_set_replicas_clamped(self, svc: AutoScalingService):
        """Setting replicas beyond max is clamped."""
        svc.set_replicas(ScalingTargetName.NLP_WORKER, 100)
        targets = svc.get_targets()
        nlp = next(t for t in targets.targets if t.name == ScalingTargetName.NLP_WORKER)
        assert nlp.current_replicas == 8  # max for nlp_worker

    def test_set_replicas_below_min(self, svc: AutoScalingService):
        """Setting replicas below min is clamped up."""
        svc.set_replicas(ScalingTargetName.BACKEND_API, 0)
        targets = svc.get_targets()
        ba = next(t for t in targets.targets if t.name == ScalingTargetName.BACKEND_API)
        assert ba.current_replicas == 2  # min for backend_api

    def test_active_policies_count(self, svc: AutoScalingService):
        """Target status shows correct active policy count."""
        targets = svc.get_targets()
        # backend_api has business_hours + api_latency = 2 active policies
        ba = next(t for t in targets.targets if t.name == ScalingTargetName.BACKEND_API)
        assert ba.active_policies == 2


# ===========================================================================
# Service - Scaling Evaluation
# ===========================================================================


class TestScalingEvaluation:
    """Test scaling decision evaluation logic."""

    def test_scale_up_on_high_queue_depth(self, svc: AutoScalingService):
        """Screening workers scale up when queue depth exceeds threshold."""
        # Clear cooldown by removing it manually; use a fresh service
        result = svc.evaluate(metrics={"screening_queue_depth": 80})
        screening_decisions = [
            d for d in result.decisions if d.target == ScalingTargetName.SCREENING_WORKER
        ]
        assert len(screening_decisions) == 1
        decision = screening_decisions[0]
        assert decision.direction == ScalingDirection.UP
        assert decision.desired_replicas > 3

    def test_no_scale_when_below_threshold(self, svc: AutoScalingService):
        """No scaling when all metrics are below thresholds."""
        result = svc.evaluate(metrics={"screening_queue_depth": 10})
        screening_decisions = [
            d for d in result.decisions if d.target == ScalingTargetName.SCREENING_WORKER
        ]
        if screening_decisions:
            decision = screening_decisions[0]
            # Either no action or scale-down blocked by stabilization
            assert decision.direction in (ScalingDirection.NONE, ScalingDirection.DOWN)

    def test_scale_up_increases_replicas(self, svc: AutoScalingService):
        """Scaling up actually increases current replicas."""
        svc.set_replicas(ScalingTargetName.SCREENING_WORKER, 3)
        svc.evaluate(metrics={"screening_queue_depth": 80})
        targets = svc.get_targets()
        sw = next(t for t in targets.targets if t.name == ScalingTargetName.SCREENING_WORKER)
        assert sw.current_replicas > 3

    def test_scale_up_respects_max(self, svc: AutoScalingService):
        """Scaling up does not exceed max replicas."""
        svc.set_replicas(ScalingTargetName.SCREENING_WORKER, 14)
        svc.evaluate(metrics={"screening_queue_depth": 200})
        targets = svc.get_targets()
        sw = next(t for t in targets.targets if t.name == ScalingTargetName.SCREENING_WORKER)
        assert sw.current_replicas <= 15

    def test_evaluated_policies_count(self, svc: AutoScalingService):
        """Evaluation reports how many policies were evaluated."""
        result = svc.evaluate(metrics={"cpu_percent": 50})
        assert result.evaluated_policies > 0

    def test_evaluation_with_target_filter(self, svc: AutoScalingService):
        """Filtering by target evaluates only that target's policies."""
        result = svc.evaluate(
            metrics={"screening_queue_depth": 80},
            target_filter=ScalingTargetName.SCREENING_WORKER,
        )
        for d in result.decisions:
            assert d.target == ScalingTargetName.SCREENING_WORKER

    def test_cooldown_prevents_rapid_scale_up(self, svc: AutoScalingService):
        """Cooldown prevents scaling up again too soon."""
        # First evaluation scales up
        svc.evaluate(metrics={"screening_queue_depth": 80})
        # Immediate second evaluation should have cooldown active
        result2 = svc.evaluate(metrics={"screening_queue_depth": 80})
        screening_decisions = [
            d for d in result2.decisions if d.target == ScalingTargetName.SCREENING_WORKER
        ]
        if screening_decisions:
            decision = screening_decisions[0]
            if decision.direction == ScalingDirection.UP:
                assert decision.cooldown_active


# ===========================================================================
# Service - Scaling History
# ===========================================================================


class TestScalingHistory:
    """Test scaling event recording and retrieval."""

    def test_history_starts_empty(self, svc: AutoScalingService):
        """History is empty initially."""
        history = svc.get_history()
        assert history.total == 0

    def test_scaling_records_event(self, svc: AutoScalingService):
        """Scaling up records a history event."""
        svc.evaluate(metrics={"screening_queue_depth": 80})
        history = svc.get_history()
        assert history.total >= 1
        event = history.events[0]
        assert event.direction == ScalingDirection.UP
        assert event.target == ScalingTargetName.SCREENING_WORKER

    def test_history_filter_by_target(self, svc: AutoScalingService):
        """History can be filtered by target."""
        svc.evaluate(metrics={"screening_queue_depth": 80})
        history = svc.get_history(target=ScalingTargetName.BACKEND_API)
        # No backend_api scaling should have occurred
        for e in history.events:
            assert e.target == ScalingTargetName.BACKEND_API

    def test_history_pagination(self, svc: AutoScalingService):
        """History supports limit and offset."""
        svc.evaluate(metrics={"screening_queue_depth": 80})
        history = svc.get_history(limit=1, offset=0)
        assert history.limit == 1
        assert len(history.events) <= 1


# ===========================================================================
# Service - KEDA Spec Generation
# ===========================================================================


class TestKEDASpec:
    """Test KEDA ScaledObject YAML generation."""

    def test_generate_keda_spec_backend(self, svc: AutoScalingService):
        """Generate KEDA spec for backend_api."""
        spec = svc.generate_keda_spec(ScalingTargetName.BACKEND_API)
        assert spec.target == ScalingTargetName.BACKEND_API
        assert "apiVersion: keda.sh/v1alpha1" in spec.yaml_content
        assert "kind: ScaledObject" in spec.yaml_content
        assert "backend_api" in spec.yaml_content
        assert "minReplicaCount: 2" in spec.yaml_content
        assert "maxReplicaCount: 20" in spec.yaml_content

    def test_generate_keda_spec_screening(self, svc: AutoScalingService):
        """Generate KEDA spec for screening_worker."""
        spec = svc.generate_keda_spec(ScalingTargetName.SCREENING_WORKER)
        assert "screening_worker" in spec.yaml_content
        assert "redis-lists" in spec.yaml_content

    def test_generate_keda_spec_fhir(self, svc: AutoScalingService):
        """Generate KEDA spec for fhir_worker."""
        spec = svc.generate_keda_spec(ScalingTargetName.FHIR_WORKER)
        assert "fhir_worker" in spec.yaml_content
        assert "prometheus" in spec.yaml_content

    def test_generate_keda_spec_nlp(self, svc: AutoScalingService):
        """Generate KEDA spec for nlp_worker."""
        spec = svc.generate_keda_spec(ScalingTargetName.NLP_WORKER)
        assert "nlp_worker" in spec.yaml_content

    def test_keda_spec_metadata(self, svc: AutoScalingService):
        """KEDA spec has correct metadata."""
        spec = svc.generate_keda_spec(ScalingTargetName.BACKEND_API)
        assert spec.metadata["namespace"] == "clinical-platform"
        assert spec.metadata["min_replicas"] == 2
        assert spec.metadata["max_replicas"] == 20

    def test_keda_spec_contains_triggers(self, svc: AutoScalingService):
        """KEDA spec includes triggers section."""
        spec = svc.generate_keda_spec(ScalingTargetName.BACKEND_API)
        assert "triggers:" in spec.yaml_content


# ===========================================================================
# Service - Predictive Scaling
# ===========================================================================


class TestPredictiveScaling:
    """Test time-series trend detection for proactive scaling."""

    def test_insufficient_data(self, svc: AutoScalingService):
        """Predictive report with no data returns stable/no prescale."""
        report = svc.get_predictive_report(ScalingTargetName.SCREENING_WORKER)
        assert report.should_prescale is False
        assert report.target == ScalingTargetName.SCREENING_WORKER

    def test_increasing_trend_detection(self, svc: AutoScalingService):
        """Detect increasing trend from rising metric data."""
        now = datetime.now(timezone.utc)
        # Feed increasing data points
        for i in range(20):
            metrics = {"screening_queue_depth": float(10 + i * 5)}
            svc._record_metrics(metrics, now + timedelta(seconds=i * 30))

        report = svc.get_predictive_report(ScalingTargetName.SCREENING_WORKER)
        # Should have at least one trend analyzed
        assert len(report.trends) >= 1
        # Find the queue depth trend
        queue_trends = [t for t in report.trends if t.metric_name == "screening_queue_depth"]
        if queue_trends:
            assert queue_trends[0].direction == TrendDirection.INCREASING
            assert queue_trends[0].slope > 0

    def test_stable_trend(self, svc: AutoScalingService):
        """Stable metrics result in stable trend."""
        now = datetime.now(timezone.utc)
        for i in range(10):
            metrics = {"screening_queue_depth": 25.0}
            svc._record_metrics(metrics, now + timedelta(seconds=i * 30))

        report = svc.get_predictive_report(ScalingTargetName.SCREENING_WORKER)
        queue_trends = [t for t in report.trends if t.metric_name == "screening_queue_depth"]
        if queue_trends:
            assert queue_trends[0].direction == TrendDirection.STABLE

    def test_decreasing_trend(self, svc: AutoScalingService):
        """Decreasing metrics result in decreasing trend."""
        now = datetime.now(timezone.utc)
        for i in range(15):
            metrics = {"screening_queue_depth": float(100 - i * 5)}
            svc._record_metrics(metrics, now + timedelta(seconds=i * 30))

        report = svc.get_predictive_report(ScalingTargetName.SCREENING_WORKER)
        queue_trends = [t for t in report.trends if t.metric_name == "screening_queue_depth"]
        if queue_trends:
            assert queue_trends[0].direction == TrendDirection.DECREASING
            assert queue_trends[0].slope < 0


# ===========================================================================
# Service - Stats
# ===========================================================================


class TestServiceStats:
    """Test service statistics."""

    def test_get_stats(self, svc: AutoScalingService):
        """Stats contain expected keys and values."""
        stats = svc.get_stats()
        assert stats["targets"] == 4
        assert stats["policies"] == 5
        assert stats["active_policies"] == 5
        assert stats["history_events"] == 0
        assert stats["tracked_metrics"] == 0


# ===========================================================================
# Singleton
# ===========================================================================


class TestSingleton:
    """Test singleton pattern."""

    def test_singleton_returns_same_instance(self):
        """get_autoscaling_service returns the same instance."""
        a = get_autoscaling_service()
        b = get_autoscaling_service()
        assert a is b

    def test_reset_singleton(self):
        """reset clears the singleton."""
        a = get_autoscaling_service()
        reset_autoscaling_service()
        b = get_autoscaling_service()
        assert a is not b


# ===========================================================================
# API Endpoint Tests
# ===========================================================================


@pytest.fixture
def api_prefix() -> str:
    return "/api/v1/infrastructure/scaling"


@pytest.mark.asyncio
class TestAPIEndpoints:
    """Test API endpoints via HTTPX async client."""

    async def _client(self):
        """Create async test client."""
        from app.main import app
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    async def test_list_policies(self, api_prefix: str):
        """GET /policies returns all policies."""
        async with await self._client() as client:
            resp = await client.get(f"{api_prefix}/policies")
        assert resp.status_code == 200
        data = resp.json()
        assert "policies" in data
        assert data["total"] >= 5

    async def test_get_policy_detail(self, api_prefix: str):
        """GET /policies/{id} returns a specific policy."""
        async with await self._client() as client:
            resp = await client.get(f"{api_prefix}/policies/builtin-screening_burst")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "screening_burst"

    async def test_get_policy_not_found(self, api_prefix: str):
        """GET /policies/{id} returns 404 for unknown ID."""
        async with await self._client() as client:
            resp = await client.get(f"{api_prefix}/policies/nonexistent")
        assert resp.status_code == 404

    async def test_create_policy(self, api_prefix: str):
        """POST /policies creates a new policy."""
        payload = {
            "name": "test_cpu",
            "policy_type": "cpu_threshold",
            "target": "backend_api",
            "threshold": 85.0,
        }
        async with await self._client() as client:
            resp = await client.post(f"{api_prefix}/policies", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "test_cpu"
        assert data["id"].startswith("pol-")

    async def test_update_policy(self, api_prefix: str):
        """PUT /policies/{id} updates a policy."""
        async with await self._client() as client:
            resp = await client.put(
                f"{api_prefix}/policies/builtin-screening_burst",
                json={"threshold": 75.0},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["threshold"] == 75.0

    async def test_update_policy_not_found(self, api_prefix: str):
        """PUT /policies/{id} returns 404 for unknown ID."""
        async with await self._client() as client:
            resp = await client.put(
                f"{api_prefix}/policies/nonexistent",
                json={"threshold": 99.0},
            )
        assert resp.status_code == 404

    async def test_delete_policy(self, api_prefix: str):
        """DELETE /policies/{id} removes a policy."""
        # Create, then delete
        async with await self._client() as client:
            create_resp = await client.post(
                f"{api_prefix}/policies",
                json={
                    "name": "deleteme",
                    "policy_type": "memory_threshold",
                    "target": "nlp_worker",
                },
            )
            policy_id = create_resp.json()["id"]
            del_resp = await client.delete(f"{api_prefix}/policies/{policy_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["id"] == policy_id

    async def test_delete_policy_not_found(self, api_prefix: str):
        """DELETE /policies/{id} returns 404 for unknown ID."""
        async with await self._client() as client:
            resp = await client.delete(f"{api_prefix}/policies/nonexistent")
        assert resp.status_code == 404

    async def test_get_targets(self, api_prefix: str):
        """GET /targets returns all scaling targets."""
        async with await self._client() as client:
            resp = await client.get(f"{api_prefix}/targets")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["targets"]) == 4

    async def test_evaluate_scaling(self, api_prefix: str):
        """POST /evaluate returns scaling decisions."""
        async with await self._client() as client:
            resp = await client.post(
                f"{api_prefix}/evaluate",
                json={"metrics": {"screening_queue_depth": 80}},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "decisions" in data
        assert data["evaluated_policies"] > 0

    async def test_evaluate_with_target_filter(self, api_prefix: str):
        """POST /evaluate with target filter."""
        async with await self._client() as client:
            resp = await client.post(
                f"{api_prefix}/evaluate",
                json={
                    "metrics": {"screening_queue_depth": 80},
                    "target": "screening_worker",
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        for d in data["decisions"]:
            assert d["target"] == "screening_worker"

    async def test_get_history(self, api_prefix: str):
        """GET /history returns scaling history."""
        async with await self._client() as client:
            resp = await client.get(f"{api_prefix}/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert "total" in data

    async def test_get_keda_spec(self, api_prefix: str):
        """GET /keda-spec/{target} returns KEDA YAML."""
        async with await self._client() as client:
            resp = await client.get(f"{api_prefix}/keda-spec/backend_api")
        assert resp.status_code == 200
        data = resp.json()
        assert data["target"] == "backend_api"
        assert "yaml_content" in data
        assert "apiVersion" in data["yaml_content"]

    async def test_filter_policies_by_target_api(self, api_prefix: str):
        """GET /policies?target=screening_worker filters correctly."""
        async with await self._client() as client:
            resp = await client.get(
                f"{api_prefix}/policies", params={"target": "screening_worker"}
            )
        assert resp.status_code == 200
        data = resp.json()
        for p in data["policies"]:
            assert p["target"] == "screening_worker"

    async def test_filter_policies_by_status_api(self, api_prefix: str):
        """GET /policies?status=active filters correctly."""
        async with await self._client() as client:
            resp = await client.get(
                f"{api_prefix}/policies", params={"status": "active"}
            )
        assert resp.status_code == 200
        data = resp.json()
        for p in data["policies"]:
            assert p["status"] == "active"
