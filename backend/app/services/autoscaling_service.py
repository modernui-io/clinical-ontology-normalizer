"""Auto-Scaling Service (DEVOPS-3).

Manages scaling policies, evaluates scaling decisions based on current metrics,
generates KEDA-compatible ScaledObject specs, records scaling history, and
performs basic predictive scaling via time-series trend detection.

Usage:
    from app.services.autoscaling_service import get_autoscaling_service

    svc = get_autoscaling_service()
    policies = svc.list_policies()
    decision = svc.evaluate(metrics={"cpu_percent": 85})
"""

from __future__ import annotations

import logging
import statistics
import threading
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any

from app.schemas.autoscaling import (
    KEDAScaledObjectSpec,
    MetricTrend,
    PolicyStatus,
    PredictiveScalingReport,
    ScalingDecision,
    ScalingDirection,
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

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default scaling target configurations
# ---------------------------------------------------------------------------

DEFAULT_TARGETS: dict[str, dict[str, Any]] = {
    ScalingTargetName.BACKEND_API.value: {
        "min_replicas": 2,
        "max_replicas": 20,
        "default_replicas": 3,
        "description": "FastAPI backend workers",
    },
    ScalingTargetName.FHIR_WORKER.value: {
        "min_replicas": 1,
        "max_replicas": 10,
        "default_replicas": 2,
        "description": "FHIR import/export workers",
    },
    ScalingTargetName.NLP_WORKER.value: {
        "min_replicas": 1,
        "max_replicas": 8,
        "default_replicas": 2,
        "description": "NLP pipeline workers",
    },
    ScalingTargetName.SCREENING_WORKER.value: {
        "min_replicas": 1,
        "max_replicas": 15,
        "default_replicas": 3,
        "description": "Trial screening workers",
    },
}

# ---------------------------------------------------------------------------
# Pre-configured clinical workload policies
# ---------------------------------------------------------------------------

_BUILTIN_POLICIES: list[dict[str, Any]] = [
    {
        "name": "screening_burst",
        "description": "Scale screening workers when queue exceeds 50 pending screenings",
        "policy_type": ScalingPolicyType.QUEUE_DEPTH,
        "target": ScalingTargetName.SCREENING_WORKER,
        "threshold": 50.0,
        "cooldown_seconds": 120,
        "stabilization_seconds": 600,
        "scale_up_step": 3,
        "scale_down_step": 1,
        "metric_name": "screening_queue_depth",
    },
    {
        "name": "fhir_import_spike",
        "description": "Scale FHIR workers when webhook rate exceeds 10/min",
        "policy_type": ScalingPolicyType.REQUEST_RATE,
        "target": ScalingTargetName.FHIR_WORKER,
        "threshold": 10.0,
        "cooldown_seconds": 180,
        "stabilization_seconds": 600,
        "scale_up_step": 2,
        "scale_down_step": 1,
        "metric_name": "fhir_webhook_rate",
    },
    {
        "name": "business_hours",
        "description": "Scale backend to 5 replicas Mon-Fri 8am-6pm EST",
        "policy_type": ScalingPolicyType.SCHEDULE,
        "target": ScalingTargetName.BACKEND_API,
        "threshold": 0.0,
        "desired_replicas": 5,
        "cooldown_seconds": 0,
        "stabilization_seconds": 0,
        "schedule": {
            "days_of_week": [0, 1, 2, 3, 4],
            "start_hour": 8,
            "end_hour": 18,
            "timezone": "US/Eastern",
        },
    },
    {
        "name": "nlp_batch",
        "description": "Scale NLP workers when document queue exceeds 100",
        "policy_type": ScalingPolicyType.QUEUE_DEPTH,
        "target": ScalingTargetName.NLP_WORKER,
        "threshold": 100.0,
        "cooldown_seconds": 180,
        "stabilization_seconds": 600,
        "scale_up_step": 2,
        "scale_down_step": 1,
        "metric_name": "nlp_document_queue_depth",
    },
    {
        "name": "api_latency",
        "description": "Scale backend when p95 latency exceeds 2 seconds",
        "policy_type": ScalingPolicyType.CUSTOM_METRIC,
        "target": ScalingTargetName.BACKEND_API,
        "threshold": 2.0,
        "cooldown_seconds": 300,
        "stabilization_seconds": 900,
        "scale_up_step": 2,
        "scale_down_step": 1,
        "metric_name": "p95_latency_seconds",
    },
]


# ---------------------------------------------------------------------------
# Metric name mapping for policy types
# ---------------------------------------------------------------------------

_POLICY_TYPE_METRIC_MAP: dict[ScalingPolicyType, str] = {
    ScalingPolicyType.CPU_THRESHOLD: "cpu_percent",
    ScalingPolicyType.MEMORY_THRESHOLD: "memory_percent",
    ScalingPolicyType.REQUEST_RATE: "request_rate",
    ScalingPolicyType.QUEUE_DEPTH: "queue_depth",
}


class AutoScalingService:
    """Service for managing auto-scaling policies, decisions, and history.

    Thread-safe singleton that maintains:
    - Scaling policies (built-in + user-created)
    - Scaling target configurations and current replica counts
    - Scaling event history
    - Metric history for predictive scaling
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

        # Scaling targets: name -> config
        self._targets: dict[str, ScalingTargetConfig] = {}
        for name, cfg in DEFAULT_TARGETS.items():
            self._targets[name] = ScalingTargetConfig(
                name=ScalingTargetName(name),
                min_replicas=cfg["min_replicas"],
                max_replicas=cfg["max_replicas"],
                default_replicas=cfg["default_replicas"],
                current_replicas=cfg["default_replicas"],
                description=cfg.get("description", ""),
            )

        # Policies: id -> ScalingPolicy
        self._policies: dict[str, ScalingPolicy] = {}
        self._load_builtin_policies()

        # Scaling history
        self._history: list[ScalingEvent] = []
        self._max_history: int = 1000

        # Last scale times per target (for cooldown tracking)
        self._last_scale_up: dict[str, datetime] = {}
        self._last_scale_down: dict[str, datetime] = {}

        # Metric history for predictive scaling: metric_name -> deque of (timestamp, value)
        self._metric_history: dict[str, deque[tuple[datetime, float]]] = {}
        self._metric_history_max: int = 120  # Keep last 120 data points

        logger.info(
            "AutoScalingService initialized with %d targets, %d builtin policies",
            len(self._targets),
            len(self._policies),
        )

    # -----------------------------------------------------------------------
    # Built-in policies
    # -----------------------------------------------------------------------

    def _load_builtin_policies(self) -> None:
        """Load pre-configured clinical workload policies."""
        now = datetime.now(timezone.utc)
        for spec in _BUILTIN_POLICIES:
            policy_id = f"builtin-{spec['name']}"
            schedule = None
            if spec.get("schedule"):
                schedule = ScheduleConfig(**spec["schedule"])

            self._policies[policy_id] = ScalingPolicy(
                id=policy_id,
                name=spec["name"],
                description=spec.get("description", ""),
                policy_type=spec["policy_type"],
                target=spec["target"],
                threshold=spec.get("threshold", 0.0),
                min_replicas=spec.get("min_replicas"),
                max_replicas=spec.get("max_replicas"),
                desired_replicas=spec.get("desired_replicas"),
                cooldown_seconds=spec.get("cooldown_seconds", 300),
                stabilization_seconds=spec.get("stabilization_seconds", 600),
                scale_up_step=spec.get("scale_up_step", 2),
                scale_down_step=spec.get("scale_down_step", 1),
                schedule=schedule,
                metric_name=spec.get("metric_name"),
                status=PolicyStatus.ACTIVE,
                created_at=now,
                updated_at=now,
                last_triggered=None,
                trigger_count=0,
            )

    # -----------------------------------------------------------------------
    # Policy CRUD
    # -----------------------------------------------------------------------

    def list_policies(
        self,
        target: ScalingTargetName | None = None,
        status: PolicyStatus | None = None,
    ) -> ScalingPoliciesResponse:
        """List all scaling policies, optionally filtered."""
        with self._lock:
            policies = list(self._policies.values())

        if target is not None:
            policies = [p for p in policies if p.target == target]
        if status is not None:
            policies = [p for p in policies if p.status == status]

        return ScalingPoliciesResponse(policies=policies, total=len(policies))

    def get_policy(self, policy_id: str) -> ScalingPolicy:
        """Get a single policy by ID.

        Raises:
            ValueError: If policy not found.
        """
        with self._lock:
            policy = self._policies.get(policy_id)
        if policy is None:
            raise ValueError(f"Policy '{policy_id}' not found")
        return policy

    def create_policy(self, data: ScalingPolicyCreate) -> ScalingPolicy:
        """Create a new scaling policy.

        Returns:
            The created ScalingPolicy with a generated ID.
        """
        now = datetime.now(timezone.utc)
        policy_id = f"pol-{uuid.uuid4().hex[:12]}"

        policy = ScalingPolicy(
            id=policy_id,
            name=data.name,
            description=data.description,
            policy_type=data.policy_type,
            target=data.target,
            threshold=data.threshold,
            min_replicas=data.min_replicas,
            max_replicas=data.max_replicas,
            desired_replicas=data.desired_replicas,
            cooldown_seconds=data.cooldown_seconds,
            stabilization_seconds=data.stabilization_seconds,
            scale_up_step=data.scale_up_step,
            scale_down_step=data.scale_down_step,
            schedule=data.schedule,
            metric_name=data.metric_name,
            status=data.status,
            created_at=now,
            updated_at=now,
            last_triggered=None,
            trigger_count=0,
        )

        with self._lock:
            self._policies[policy_id] = policy

        logger.info("Created scaling policy %s (%s) for %s", policy_id, data.name, data.target)
        return policy

    def update_policy(self, policy_id: str, data: ScalingPolicyUpdate) -> ScalingPolicy:
        """Update an existing scaling policy.

        Raises:
            ValueError: If policy not found.
        """
        with self._lock:
            policy = self._policies.get(policy_id)
            if policy is None:
                raise ValueError(f"Policy '{policy_id}' not found")

            update_fields = data.model_dump(exclude_unset=True)
            current = policy.model_dump()
            current.update(update_fields)
            current["updated_at"] = datetime.now(timezone.utc)

            updated = ScalingPolicy(**current)
            self._policies[policy_id] = updated

        logger.info("Updated scaling policy %s", policy_id)
        return updated

    def delete_policy(self, policy_id: str) -> ScalingPolicy:
        """Delete a scaling policy.

        Raises:
            ValueError: If policy not found.
        """
        with self._lock:
            policy = self._policies.pop(policy_id, None)
        if policy is None:
            raise ValueError(f"Policy '{policy_id}' not found")

        logger.info("Deleted scaling policy %s (%s)", policy_id, policy.name)
        return policy

    # -----------------------------------------------------------------------
    # Scaling Targets
    # -----------------------------------------------------------------------

    def get_targets(self) -> ScalingTargetsResponse:
        """Get all scaling targets with their current status."""
        with self._lock:
            targets = []
            for name, config in self._targets.items():
                active_count = sum(
                    1
                    for p in self._policies.values()
                    if p.target.value == name and p.status == PolicyStatus.ACTIVE
                )
                targets.append(
                    ScalingTargetStatus(
                        name=config.name,
                        current_replicas=config.current_replicas,
                        min_replicas=config.min_replicas,
                        max_replicas=config.max_replicas,
                        desired_replicas=config.current_replicas,
                        last_scale_time=self._last_scale_up.get(name)
                        or self._last_scale_down.get(name),
                        active_policies=active_count,
                    )
                )

        return ScalingTargetsResponse(
            targets=targets,
            timestamp=datetime.now(timezone.utc),
        )

    def set_replicas(self, target: ScalingTargetName, replicas: int) -> None:
        """Set the current replica count for a target (for testing/simulation)."""
        with self._lock:
            config = self._targets.get(target.value)
            if config is None:
                raise ValueError(f"Unknown target '{target.value}'")
            clamped = max(config.min_replicas, min(config.max_replicas, replicas))
            self._targets[target.value] = config.model_copy(
                update={"current_replicas": clamped}
            )

    # -----------------------------------------------------------------------
    # Scaling Evaluation
    # -----------------------------------------------------------------------

    def evaluate(
        self,
        metrics: dict[str, float],
        target_filter: ScalingTargetName | None = None,
    ) -> ScalingEvaluationResponse:
        """Evaluate all active policies against provided metrics.

        For each target, determines whether to scale up, scale down, or do nothing.
        Scale-up is preferred (bias towards availability).

        Args:
            metrics: Current metric values, e.g. {"cpu_percent": 85, "queue_depth": 120}.
            target_filter: Optionally evaluate only for a specific target.

        Returns:
            ScalingEvaluationResponse with decisions for each target.
        """
        now = datetime.now(timezone.utc)

        # Record metrics in history for predictive scaling
        self._record_metrics(metrics, now)

        with self._lock:
            active_policies = [
                p for p in self._policies.values() if p.status == PolicyStatus.ACTIVE
            ]

        if target_filter is not None:
            active_policies = [p for p in active_policies if p.target == target_filter]

        # Group policies by target
        target_policies: dict[str, list[ScalingPolicy]] = {}
        for p in active_policies:
            target_policies.setdefault(p.target.value, []).append(p)

        decisions: list[ScalingDecision] = []
        for target_name, policies in target_policies.items():
            decision = self._evaluate_target(target_name, policies, metrics, now)
            decisions.append(decision)

            # Apply scaling if a real direction is chosen
            if decision.direction != ScalingDirection.NONE and not decision.cooldown_active:
                self._apply_scaling(decision, now)

        return ScalingEvaluationResponse(
            decisions=decisions,
            evaluated_policies=len(active_policies),
            timestamp=now,
        )

    def _evaluate_target(
        self,
        target_name: str,
        policies: list[ScalingPolicy],
        metrics: dict[str, float],
        now: datetime,
    ) -> ScalingDecision:
        """Evaluate scaling for a single target across all its policies."""
        with self._lock:
            config = self._targets[target_name]
            current = config.current_replicas

        scale_up_needed = False
        scale_down_possible = True
        triggered_ids: list[str] = []
        reasons: list[str] = []
        metric_values: dict[str, float] = {}
        desired = current

        for policy in policies:
            metric_key = self._get_metric_key(policy)
            if metric_key is None:
                # Schedule-based
                if policy.policy_type == ScalingPolicyType.SCHEDULE:
                    in_schedule = self._is_in_schedule(policy.schedule, now)
                    schedule_desired = policy.desired_replicas or config.default_replicas
                    if in_schedule and current < schedule_desired:
                        scale_up_needed = True
                        desired = max(desired, schedule_desired)
                        triggered_ids.append(policy.id)
                        reasons.append(
                            f"Schedule '{policy.name}': in active window, want {schedule_desired}"
                        )
                    elif not in_schedule and current > config.default_replicas:
                        # Outside schedule, scale down to default
                        desired = min(desired, config.default_replicas)
                        reasons.append(
                            f"Schedule '{policy.name}': outside window, returning to default {config.default_replicas}"
                        )
                    else:
                        scale_down_possible = False
                continue

            metric_val = metrics.get(metric_key)
            if metric_val is None:
                # No data for this metric; skip
                scale_down_possible = False
                continue

            metric_values[metric_key] = metric_val

            if metric_val > policy.threshold:
                scale_up_needed = True
                step = policy.scale_up_step
                new_desired = current + step
                # Apply policy-level max override
                policy_max = policy.max_replicas or config.max_replicas
                new_desired = min(new_desired, policy_max)
                desired = max(desired, new_desired)
                triggered_ids.append(policy.id)
                reasons.append(
                    f"Policy '{policy.name}': {metric_key}={metric_val:.1f} > threshold {policy.threshold}"
                )
            else:
                # Metric is below threshold -- scale down could apply
                pass

        # Determine direction
        if scale_up_needed and desired > current:
            direction = ScalingDirection.UP
            # Clamp to target max
            desired = min(desired, config.max_replicas)
        elif not scale_up_needed and scale_down_possible and current > config.min_replicas:
            # Scale down: only if all metrics are below threshold
            direction = ScalingDirection.DOWN
            step = min(p.scale_down_step for p in policies) if policies else 1
            desired = max(current - step, config.min_replicas)
            reasons.append(f"All metrics below thresholds, scaling down by {step}")
        else:
            direction = ScalingDirection.NONE
            desired = current
            if not reasons:
                reasons.append("No scaling action needed")

        # Check cooldown
        cooldown_active = False
        if direction == ScalingDirection.UP:
            cooldown = max((p.cooldown_seconds for p in policies if p.id in triggered_ids), default=300)
            last_up = self._last_scale_up.get(target_name)
            if last_up and (now - last_up).total_seconds() < cooldown:
                cooldown_active = True
                reasons.append(
                    f"Cooldown active: last scale-up was {(now - last_up).total_seconds():.0f}s ago, "
                    f"cooldown is {cooldown}s"
                )
        elif direction == ScalingDirection.DOWN:
            stabilization = max((p.stabilization_seconds for p in policies), default=600)
            last_down = self._last_scale_down.get(target_name)
            last_up = self._last_scale_up.get(target_name)
            last_event = max(filter(None, [last_down, last_up]), default=None)
            if last_event and (now - last_event).total_seconds() < stabilization:
                cooldown_active = True
                reasons.append(
                    f"Stabilization active: last scale event was {(now - last_event).total_seconds():.0f}s ago, "
                    f"stabilization is {stabilization}s"
                )

        return ScalingDecision(
            target=ScalingTargetName(target_name),
            direction=direction,
            current_replicas=current,
            desired_replicas=desired,
            reason="; ".join(reasons),
            triggered_policies=triggered_ids,
            metric_values=metric_values,
            cooldown_active=cooldown_active,
            timestamp=now,
        )

    def _apply_scaling(self, decision: ScalingDecision, now: datetime) -> None:
        """Apply a scaling decision: update replicas and record history."""
        target_name = decision.target.value

        with self._lock:
            config = self._targets[target_name]
            from_replicas = config.current_replicas
            to_replicas = decision.desired_replicas

            # Clamp
            to_replicas = max(config.min_replicas, min(config.max_replicas, to_replicas))

            if to_replicas == from_replicas:
                return

            self._targets[target_name] = config.model_copy(
                update={"current_replicas": to_replicas}
            )

            if decision.direction == ScalingDirection.UP:
                self._last_scale_up[target_name] = now
            elif decision.direction == ScalingDirection.DOWN:
                self._last_scale_down[target_name] = now

            # Update triggered policies
            for pid in decision.triggered_policies:
                policy = self._policies.get(pid)
                if policy:
                    self._policies[pid] = policy.model_copy(
                        update={
                            "last_triggered": now,
                            "trigger_count": policy.trigger_count + 1,
                        }
                    )

            # Record event
            first_policy_id = decision.triggered_policies[0] if decision.triggered_policies else None
            first_policy_name = None
            if first_policy_id:
                p = self._policies.get(first_policy_id)
                first_policy_name = p.name if p else None

            metric_val = None
            threshold = None
            if decision.metric_values:
                metric_val = next(iter(decision.metric_values.values()))
            if first_policy_id:
                p = self._policies.get(first_policy_id)
                if p:
                    threshold = p.threshold

            event = ScalingEvent(
                id=f"evt-{uuid.uuid4().hex[:12]}",
                target=decision.target,
                direction=decision.direction,
                from_replicas=from_replicas,
                to_replicas=to_replicas,
                reason=decision.reason,
                policy_id=first_policy_id,
                policy_name=first_policy_name,
                metric_value=metric_val,
                threshold=threshold,
                timestamp=now,
            )
            self._history.append(event)

            # Trim history
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        logger.info(
            "Scaled %s %s: %d -> %d (%s)",
            target_name,
            decision.direction.value,
            from_replicas,
            to_replicas,
            decision.reason[:100],
        )

    def _get_metric_key(self, policy: ScalingPolicy) -> str | None:
        """Determine the metric key for a given policy."""
        if policy.policy_type == ScalingPolicyType.SCHEDULE:
            return None
        if policy.metric_name:
            return policy.metric_name
        return _POLICY_TYPE_METRIC_MAP.get(policy.policy_type)

    def _is_in_schedule(self, schedule: ScheduleConfig | None, now: datetime) -> bool:
        """Check whether the current time is within the schedule window."""
        if schedule is None:
            return False

        # Use provided timezone or default to UTC
        try:
            import zoneinfo
            tz = zoneinfo.ZoneInfo(schedule.timezone)
            local_now = now.astimezone(tz)
        except Exception:
            local_now = now

        day_of_week = local_now.weekday()  # 0=Monday
        hour = local_now.hour

        if day_of_week not in schedule.days_of_week:
            return False

        return schedule.start_hour <= hour < schedule.end_hour

    # -----------------------------------------------------------------------
    # Scaling History
    # -----------------------------------------------------------------------

    def get_history(
        self,
        target: ScalingTargetName | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> ScalingHistoryResponse:
        """Get scaling event history, optionally filtered by target."""
        with self._lock:
            events = list(self._history)

        if target is not None:
            events = [e for e in events if e.target == target]

        # Sort by timestamp descending (most recent first)
        events.sort(key=lambda e: e.timestamp, reverse=True)
        total = len(events)
        page = events[offset: offset + limit]

        return ScalingHistoryResponse(
            events=page,
            total=total,
            limit=limit,
            offset=offset,
        )

    # -----------------------------------------------------------------------
    # KEDA Spec Generation
    # -----------------------------------------------------------------------

    def generate_keda_spec(self, target: ScalingTargetName) -> KEDAScaledObjectSpec:
        """Generate a KEDA ScaledObject YAML for the given target.

        Raises:
            ValueError: If target is unknown.
        """
        with self._lock:
            config = self._targets.get(target.value)
            if config is None:
                raise ValueError(f"Unknown target '{target.value}'")

            # Gather active policies for this target
            policies = [
                p
                for p in self._policies.values()
                if p.target == target and p.status == PolicyStatus.ACTIVE
            ]

        # Build triggers from policies
        triggers: list[dict[str, Any]] = []
        for policy in policies:
            if policy.policy_type == ScalingPolicyType.CPU_THRESHOLD:
                triggers.append({
                    "type": "cpu",
                    "metadata": {
                        "type": "Utilization",
                        "value": str(int(policy.threshold)),
                    },
                })
            elif policy.policy_type == ScalingPolicyType.MEMORY_THRESHOLD:
                triggers.append({
                    "type": "memory",
                    "metadata": {
                        "type": "Utilization",
                        "value": str(int(policy.threshold)),
                    },
                })
            elif policy.policy_type == ScalingPolicyType.QUEUE_DEPTH:
                triggers.append({
                    "type": "redis-lists",
                    "metadata": {
                        "address": "redis:6379",
                        "listName": policy.metric_name or "job_queue",
                        "listLength": str(int(policy.threshold)),
                    },
                })
            elif policy.policy_type == ScalingPolicyType.REQUEST_RATE:
                triggers.append({
                    "type": "prometheus",
                    "metadata": {
                        "serverAddress": "http://prometheus:9090",
                        "metricName": policy.metric_name or "http_requests_total",
                        "threshold": str(int(policy.threshold)),
                        "query": f'sum(rate({policy.metric_name or "http_requests_total"}[1m]))',
                    },
                })
            elif policy.policy_type == ScalingPolicyType.CUSTOM_METRIC:
                triggers.append({
                    "type": "prometheus",
                    "metadata": {
                        "serverAddress": "http://prometheus:9090",
                        "metricName": policy.metric_name or "custom_metric",
                        "threshold": str(policy.threshold),
                        "query": policy.metric_name or "custom_metric",
                    },
                })
            elif policy.policy_type == ScalingPolicyType.SCHEDULE:
                if policy.schedule:
                    triggers.append({
                        "type": "cron",
                        "metadata": {
                            "timezone": policy.schedule.timezone,
                            "start": f"{policy.schedule.start_hour} * * * *",
                            "end": f"{policy.schedule.end_hour} * * * *",
                            "desiredReplicas": str(
                                policy.desired_replicas or config.default_replicas
                            ),
                        },
                    })

        # Determine the most restrictive cooldown
        cooldowns = [p.cooldown_seconds for p in policies if p.cooldown_seconds > 0]
        cooldown = min(cooldowns) if cooldowns else 300

        # Build YAML
        yaml_lines = [
            "apiVersion: keda.sh/v1alpha1",
            "kind: ScaledObject",
            "metadata:",
            f"  name: {target.value}-scaledobject",
            "  namespace: clinical-platform",
            "  labels:",
            "    app: clinical-platform",
            f"    component: {target.value}",
            "spec:",
            "  scaleTargetRef:",
            f"    name: {target.value}",
            f"  minReplicaCount: {config.min_replicas}",
            f"  maxReplicaCount: {config.max_replicas}",
            f"  cooldownPeriod: {cooldown}",
            "  advanced:",
            "    horizontalPodAutoscalerConfig:",
            "      behavior:",
            "        scaleUp:",
            "          stabilizationWindowSeconds: 60",
            "          policies:",
            "            - type: Pods",
            "              value: 3",
            "              periodSeconds: 60",
            "        scaleDown:",
            "          stabilizationWindowSeconds: 300",
            "          policies:",
            "            - type: Pods",
            "              value: 1",
            "              periodSeconds: 120",
            "  triggers:",
        ]

        for trigger in triggers:
            yaml_lines.append(f"    - type: {trigger['type']}")
            yaml_lines.append("      metadata:")
            for k, v in trigger["metadata"].items():
                yaml_lines.append(f"        {k}: \"{v}\"")

        # If no triggers, add a default CPU trigger
        if not triggers:
            yaml_lines.extend([
                "    - type: cpu",
                "      metadata:",
                '        type: "Utilization"',
                '        value: "70"',
            ])

        yaml_content = "\n".join(yaml_lines) + "\n"

        return KEDAScaledObjectSpec(
            target=target,
            yaml_content=yaml_content,
            api_version="keda.sh/v1alpha1",
            kind="ScaledObject",
            metadata={
                "name": f"{target.value}-scaledobject",
                "namespace": "clinical-platform",
                "triggers_count": len(triggers) or 1,
                "min_replicas": config.min_replicas,
                "max_replicas": config.max_replicas,
            },
        )

    # -----------------------------------------------------------------------
    # Predictive Scaling
    # -----------------------------------------------------------------------

    def _record_metrics(self, metrics: dict[str, float], now: datetime) -> None:
        """Record metric values for trend analysis."""
        with self._lock:
            for name, value in metrics.items():
                if name not in self._metric_history:
                    self._metric_history[name] = deque(maxlen=self._metric_history_max)
                self._metric_history[name].append((now, value))

    def get_predictive_report(
        self,
        target: ScalingTargetName,
        window_minutes: int = 30,
    ) -> PredictiveScalingReport:
        """Generate a predictive scaling report for a target.

        Analyzes metric trends and recommends proactive scaling if a consistent
        increase is detected.
        """
        with self._lock:
            config = self._targets.get(target.value)
            if config is None:
                raise ValueError(f"Unknown target '{target.value}'")

            # Get policies for this target to know which metrics to analyze
            policies = [
                p
                for p in self._policies.values()
                if p.target == target and p.status == PolicyStatus.ACTIVE
            ]

        now = datetime.now(timezone.utc)
        trends: list[MetricTrend] = []
        should_prescale = False
        recommended = config.current_replicas

        for policy in policies:
            metric_key = self._get_metric_key(policy)
            if metric_key is None:
                continue

            trend = self._analyze_trend(metric_key, window_minutes, now, policy.threshold)
            trends.append(trend)

            if trend.direction == TrendDirection.INCREASING and trend.confidence >= 0.6:
                should_prescale = True
                recommended = max(
                    recommended,
                    config.current_replicas + policy.scale_up_step,
                )

        # Clamp recommendation
        recommended = min(recommended, config.max_replicas)
        recommended = max(recommended, config.min_replicas)

        return PredictiveScalingReport(
            target=target,
            trends=trends,
            should_prescale=should_prescale,
            recommended_replicas=recommended if should_prescale else None,
            analysis_window_minutes=window_minutes,
            timestamp=now,
        )

    def _analyze_trend(
        self,
        metric_name: str,
        window_minutes: int,
        now: datetime,
        threshold: float,
    ) -> MetricTrend:
        """Analyze the trend of a single metric over the given window."""
        with self._lock:
            history = self._metric_history.get(metric_name, deque())
            # Filter to window
            cutoff = now.timestamp() - (window_minutes * 60)
            data_points = [
                (ts, val)
                for ts, val in history
                if ts.timestamp() >= cutoff
            ]

        if len(data_points) < 3:
            return MetricTrend(
                metric_name=metric_name,
                direction=TrendDirection.STABLE,
                slope=0.0,
                confidence=0.0,
                data_points=len(data_points),
                predicted_value=None,
                recommendation="Insufficient data for trend analysis",
            )

        # Simple linear regression
        values = [v for _, v in data_points]
        n = len(values)
        xs = list(range(n))
        mean_x = statistics.mean(xs)
        mean_y = statistics.mean(values)

        numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values))
        denominator = sum((x - mean_x) ** 2 for x in xs)

        if denominator == 0:
            slope = 0.0
        else:
            slope = numerator / denominator

        # Predicted next value
        predicted = mean_y + slope * n

        # Calculate R-squared as confidence
        ss_res = sum((y - (mean_y + slope * (x - mean_x))) ** 2 for x, y in zip(xs, values))
        ss_tot = sum((y - mean_y) ** 2 for y in values)
        if ss_tot == 0:
            r_squared = 0.0
        else:
            r_squared = max(0.0, 1.0 - ss_res / ss_tot)

        # Determine direction
        if slope > 0.1:
            direction = TrendDirection.INCREASING
        elif slope < -0.1:
            direction = TrendDirection.DECREASING
        else:
            direction = TrendDirection.STABLE

        # Build recommendation
        if direction == TrendDirection.INCREASING and r_squared >= 0.6:
            if predicted > threshold:
                recommendation = (
                    f"Metric is trending up (slope={slope:.2f}) and predicted to exceed "
                    f"threshold ({threshold}) soon. Pre-scaling recommended."
                )
            else:
                recommendation = (
                    f"Metric is trending up (slope={slope:.2f}) but predicted value "
                    f"({predicted:.1f}) is still below threshold ({threshold})."
                )
        elif direction == TrendDirection.DECREASING:
            recommendation = f"Metric is trending down (slope={slope:.2f}). Scale-down may be possible."
        else:
            recommendation = "Metric is stable. No proactive scaling needed."

        return MetricTrend(
            metric_name=metric_name,
            direction=direction,
            slope=round(slope, 4),
            confidence=round(r_squared, 4),
            data_points=n,
            predicted_value=round(predicted, 2),
            recommendation=recommendation,
        )

    # -----------------------------------------------------------------------
    # Stats
    # -----------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return service statistics."""
        with self._lock:
            return {
                "targets": len(self._targets),
                "policies": len(self._policies),
                "active_policies": sum(
                    1 for p in self._policies.values() if p.status == PolicyStatus.ACTIVE
                ),
                "history_events": len(self._history),
                "tracked_metrics": len(self._metric_history),
            }


# ---------------------------------------------------------------------------
# Singleton management
# ---------------------------------------------------------------------------

_instance: AutoScalingService | None = None
_lock = threading.Lock()


def get_autoscaling_service() -> AutoScalingService:
    """Get or create the singleton AutoScalingService."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = AutoScalingService()
    return _instance


def reset_autoscaling_service() -> None:
    """Reset the singleton (for testing)."""
    global _instance
    with _lock:
        _instance = None
