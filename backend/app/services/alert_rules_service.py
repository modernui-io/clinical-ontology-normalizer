"""Alert Rules Service for clinical risk-based alerting.

Provides functionality to create, manage, and evaluate clinical alert rules
based on risk thresholds, lab values, and clinical conditions.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Severity levels for alerts."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertCategory(str, Enum):
    """Categories of clinical alerts."""

    RISK_SCORE = "risk_score"
    LAB_VALUE = "lab_value"
    VITAL_SIGN = "vital_sign"
    MEDICATION = "medication"
    CONDITION = "condition"
    QUALITY_GAP = "quality_gap"
    CARE_COORDINATION = "care_coordination"


class RuleOperator(str, Enum):
    """Comparison operators for rule conditions."""

    EQUALS = "eq"
    NOT_EQUALS = "neq"
    GREATER_THAN = "gt"
    GREATER_THAN_OR_EQUALS = "gte"
    LESS_THAN = "lt"
    LESS_THAN_OR_EQUALS = "lte"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    EXISTS = "exists"


class RuleStatus(str, Enum):
    """Status of an alert rule."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAFT = "draft"
    ARCHIVED = "archived"


@dataclass
class RuleCondition:
    """A single condition within an alert rule."""

    field: str
    operator: RuleOperator
    value: Any
    label: str = ""


@dataclass
class AlertAction:
    """Action to take when an alert is triggered."""

    type: str  # notify, escalate, create_task, send_message
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertRule:
    """Definition of a clinical alert rule."""

    id: str
    name: str
    description: str
    category: AlertCategory
    severity: AlertSeverity
    status: RuleStatus
    conditions: list[RuleCondition]
    actions: list[AlertAction]
    created_at: datetime
    updated_at: datetime
    created_by: str
    patient_filter: dict[str, Any] | None = None
    cooldown_minutes: int = 60  # Don't re-alert within this window
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertEvaluation:
    """Result of evaluating a rule against patient data."""

    rule_id: str
    rule_name: str
    triggered: bool
    severity: AlertSeverity
    message: str
    matched_conditions: list[str]
    patient_id: str | None = None
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    context: dict[str, Any] = field(default_factory=dict)


class AlertRulesService:
    """Service for managing and evaluating clinical alert rules."""

    def __init__(self) -> None:
        """Initialize the alert rules service."""
        self._rules: dict[str, AlertRule] = {}
        self._lock = threading.Lock()
        self._init_default_rules()

    def _init_default_rules(self) -> None:
        """Initialize default clinical alert rules."""
        default_rules = [
            AlertRule(
                id=str(uuid4()),
                name="High Readmission Risk",
                description="Alert when 30-day readmission risk exceeds threshold",
                category=AlertCategory.RISK_SCORE,
                severity=AlertSeverity.HIGH,
                status=RuleStatus.ACTIVE,
                conditions=[
                    RuleCondition(
                        field="readmission_risk_score",
                        operator=RuleOperator.GREATER_THAN_OR_EQUALS,
                        value=0.7,
                        label="Readmission risk >= 70%",
                    )
                ],
                actions=[
                    AlertAction(type="notify", config={"channel": "care_team"}),
                ],
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                created_by="system",
            ),
            AlertRule(
                id=str(uuid4()),
                name="Critical Lab Value",
                description="Alert on critical laboratory values",
                category=AlertCategory.LAB_VALUE,
                severity=AlertSeverity.CRITICAL,
                status=RuleStatus.ACTIVE,
                conditions=[
                    RuleCondition(
                        field="potassium",
                        operator=RuleOperator.GREATER_THAN,
                        value=6.5,
                        label="Potassium > 6.5 mEq/L",
                    )
                ],
                actions=[
                    AlertAction(type="notify", config={"channel": "physician", "urgent": True}),
                ],
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                created_by="system",
            ),
            AlertRule(
                id=str(uuid4()),
                name="Mortality Risk Escalation",
                description="Alert when mortality risk tier changes to high",
                category=AlertCategory.RISK_SCORE,
                severity=AlertSeverity.HIGH,
                status=RuleStatus.ACTIVE,
                conditions=[
                    RuleCondition(
                        field="mortality_risk_tier",
                        operator=RuleOperator.EQUALS,
                        value="high",
                        label="Mortality risk tier is high",
                    )
                ],
                actions=[
                    AlertAction(type="escalate", config={"to": "attending_physician"}),
                ],
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                created_by="system",
            ),
            AlertRule(
                id=str(uuid4()),
                name="Quality Gap Identified",
                description="Alert when patient has open quality care gap",
                category=AlertCategory.QUALITY_GAP,
                severity=AlertSeverity.MEDIUM,
                status=RuleStatus.ACTIVE,
                conditions=[
                    RuleCondition(
                        field="open_quality_gaps",
                        operator=RuleOperator.GREATER_THAN,
                        value=0,
                        label="Has open quality gaps",
                    )
                ],
                actions=[
                    AlertAction(type="create_task", config={"type": "quality_outreach"}),
                ],
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                created_by="system",
            ),
        ]

        for rule in default_rules:
            self._rules[rule.id] = rule

    def create_rule(
        self,
        name: str,
        description: str,
        category: AlertCategory,
        severity: AlertSeverity,
        conditions: list[dict[str, Any]],
        actions: list[dict[str, Any]],
        created_by: str,
        patient_filter: dict[str, Any] | None = None,
        cooldown_minutes: int = 60,
        metadata: dict[str, Any] | None = None,
    ) -> AlertRule:
        """Create a new alert rule.

        Args:
            name: Rule name.
            description: Rule description.
            category: Alert category.
            severity: Alert severity.
            conditions: List of condition dicts.
            actions: List of action dicts.
            created_by: User ID who created the rule.
            patient_filter: Optional patient filter criteria.
            cooldown_minutes: Cooldown between repeated alerts.
            metadata: Optional metadata.

        Returns:
            Created AlertRule.
        """
        rule_id = str(uuid4())
        now = datetime.now(timezone.utc)

        parsed_conditions = [
            RuleCondition(
                field=c["field"],
                operator=RuleOperator(c["operator"]),
                value=c["value"],
                label=c.get("label", ""),
            )
            for c in conditions
        ]

        parsed_actions = [
            AlertAction(type=a["type"], config=a.get("config", {}))
            for a in actions
        ]

        rule = AlertRule(
            id=rule_id,
            name=name,
            description=description,
            category=category,
            severity=severity,
            status=RuleStatus.ACTIVE,
            conditions=parsed_conditions,
            actions=parsed_actions,
            created_at=now,
            updated_at=now,
            created_by=created_by,
            patient_filter=patient_filter,
            cooldown_minutes=cooldown_minutes,
            metadata=metadata or {},
        )

        with self._lock:
            self._rules[rule_id] = rule

        logger.info(f"Created alert rule: {rule_id} - {name}")
        return rule

    def get_rule(self, rule_id: str) -> AlertRule | None:
        """Get a rule by ID."""
        return self._rules.get(rule_id)

    def list_rules(
        self,
        category: AlertCategory | None = None,
        status: RuleStatus | None = None,
        severity: AlertSeverity | None = None,
        limit: int = 100,
    ) -> list[AlertRule]:
        """List alert rules with optional filtering.

        Args:
            category: Filter by category.
            status: Filter by status.
            severity: Filter by severity.
            limit: Maximum results.

        Returns:
            List of matching rules.
        """
        rules = list(self._rules.values())

        if category:
            rules = [r for r in rules if r.category == category]

        if status:
            rules = [r for r in rules if r.status == status]

        if severity:
            rules = [r for r in rules if r.severity == severity]

        # Sort by updated_at descending
        rules.sort(key=lambda r: r.updated_at, reverse=True)

        return rules[:limit]

    def update_rule(
        self,
        rule_id: str,
        **updates: Any,
    ) -> AlertRule | None:
        """Update an existing rule.

        Args:
            rule_id: Rule ID to update.
            **updates: Fields to update.

        Returns:
            Updated rule or None if not found.
        """
        with self._lock:
            rule = self._rules.get(rule_id)
            if not rule:
                return None

            # Update allowed fields
            if "name" in updates:
                rule.name = updates["name"]
            if "description" in updates:
                rule.description = updates["description"]
            if "severity" in updates:
                rule.severity = AlertSeverity(updates["severity"])
            if "status" in updates:
                rule.status = RuleStatus(updates["status"])
            if "conditions" in updates:
                rule.conditions = [
                    RuleCondition(
                        field=c["field"],
                        operator=RuleOperator(c["operator"]),
                        value=c["value"],
                        label=c.get("label", ""),
                    )
                    for c in updates["conditions"]
                ]
            if "actions" in updates:
                rule.actions = [
                    AlertAction(type=a["type"], config=a.get("config", {}))
                    for a in updates["actions"]
                ]
            if "cooldown_minutes" in updates:
                rule.cooldown_minutes = updates["cooldown_minutes"]
            if "metadata" in updates:
                rule.metadata = updates["metadata"]

            rule.updated_at = datetime.now(timezone.utc)

        logger.info(f"Updated alert rule: {rule_id}")
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule.

        Args:
            rule_id: Rule ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        with self._lock:
            if rule_id in self._rules:
                del self._rules[rule_id]
                logger.info(f"Deleted alert rule: {rule_id}")
                return True
        return False

    def evaluate_rule(
        self,
        rule_id: str,
        patient_data: dict[str, Any],
        patient_id: str | None = None,
    ) -> AlertEvaluation:
        """Evaluate a rule against patient data.

        Args:
            rule_id: Rule to evaluate.
            patient_data: Patient data to evaluate against.
            patient_id: Optional patient identifier.

        Returns:
            AlertEvaluation result.
        """
        rule = self.get_rule(rule_id)
        if not rule:
            return AlertEvaluation(
                rule_id=rule_id,
                rule_name="Unknown",
                triggered=False,
                severity=AlertSeverity.INFO,
                message="Rule not found",
                matched_conditions=[],
                patient_id=patient_id,
            )

        matched = []
        all_matched = True

        for condition in rule.conditions:
            if self._evaluate_condition(condition, patient_data):
                matched.append(condition.label or f"{condition.field} {condition.operator.value} {condition.value}")
            else:
                all_matched = False

        triggered = all_matched and len(matched) > 0

        message = ""
        if triggered:
            message = f"Alert triggered: {rule.name} - {', '.join(matched)}"
        else:
            message = f"Rule not triggered: {rule.name}"

        return AlertEvaluation(
            rule_id=rule_id,
            rule_name=rule.name,
            triggered=triggered,
            severity=rule.severity,
            message=message,
            matched_conditions=matched,
            patient_id=patient_id,
            context={"rule_category": rule.category.value},
        )

    def _evaluate_condition(
        self,
        condition: RuleCondition,
        data: dict[str, Any],
    ) -> bool:
        """Evaluate a single condition against data.

        Args:
            condition: Condition to evaluate.
            data: Data to evaluate against.

        Returns:
            True if condition is met.
        """
        field_value = data.get(condition.field)

        if condition.operator == RuleOperator.EXISTS:
            return field_value is not None

        if field_value is None:
            return False

        op = condition.operator
        target = condition.value

        try:
            if op == RuleOperator.EQUALS:
                return field_value == target
            elif op == RuleOperator.NOT_EQUALS:
                return field_value != target
            elif op == RuleOperator.GREATER_THAN:
                return float(field_value) > float(target)
            elif op == RuleOperator.GREATER_THAN_OR_EQUALS:
                return float(field_value) >= float(target)
            elif op == RuleOperator.LESS_THAN:
                return float(field_value) < float(target)
            elif op == RuleOperator.LESS_THAN_OR_EQUALS:
                return float(field_value) <= float(target)
            elif op == RuleOperator.IN:
                return field_value in target
            elif op == RuleOperator.NOT_IN:
                return field_value not in target
            elif op == RuleOperator.CONTAINS:
                return str(target) in str(field_value)
        except (ValueError, TypeError):
            return False

        return False

    def evaluate_patient(
        self,
        patient_data: dict[str, Any],
        patient_id: str | None = None,
        category: AlertCategory | None = None,
    ) -> list[AlertEvaluation]:
        """Evaluate all active rules against a patient.

        Args:
            patient_data: Patient data to evaluate.
            patient_id: Optional patient identifier.
            category: Optional category filter.

        Returns:
            List of evaluations (triggered and not triggered).
        """
        rules = self.list_rules(category=category, status=RuleStatus.ACTIVE)
        evaluations = []

        for rule in rules:
            eval_result = self.evaluate_rule(rule.id, patient_data, patient_id)
            evaluations.append(eval_result)

        return evaluations

    def get_stats(self) -> dict[str, Any]:
        """Get alert rules statistics."""
        rules = list(self._rules.values())

        by_category: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_status: dict[str, int] = {}

        for rule in rules:
            by_category[rule.category.value] = by_category.get(rule.category.value, 0) + 1
            by_severity[rule.severity.value] = by_severity.get(rule.severity.value, 0) + 1
            by_status[rule.status.value] = by_status.get(rule.status.value, 0) + 1

        return {
            "total_rules": len(rules),
            "by_category": by_category,
            "by_severity": by_severity,
            "by_status": by_status,
            "active_rules": by_status.get("active", 0),
        }


# Singleton instance
_alert_rules_service: AlertRulesService | None = None
_alert_rules_lock = threading.Lock()


def get_alert_rules_service() -> AlertRulesService:
    """Get the singleton AlertRulesService instance."""
    global _alert_rules_service

    if _alert_rules_service is None:
        with _alert_rules_lock:
            if _alert_rules_service is None:
                logger.info("Creating singleton AlertRulesService instance")
                _alert_rules_service = AlertRulesService()

    return _alert_rules_service


def reset_alert_rules_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _alert_rules_service
    with _alert_rules_lock:
        _alert_rules_service = None
