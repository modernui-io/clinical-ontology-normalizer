"""Dependency classification for health/readiness policies.

P1-021: Splits infrastructure dependencies into CRITICAL vs NON_CRITICAL classes.
Critical dependencies block readiness; non-critical dependencies allow degraded mode.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DependencyClass(str, Enum):
    """Classification tier for infrastructure dependencies."""

    CRITICAL = "critical"
    NON_CRITICAL = "non_critical"


@dataclass(frozen=True)
class DependencyInfo:
    """Metadata for a single dependency."""

    name: str
    dep_class: DependencyClass
    description: str
    feature_gate: str | None = None  # Config key that enables this dependency


# Default dependency registry.
# feature_gate=None means the dependency is always checked.
DEPENDENCY_REGISTRY: dict[str, DependencyInfo] = {
    "database": DependencyInfo(
        name="database",
        dep_class=DependencyClass.CRITICAL,
        description="PostgreSQL primary data store",
    ),
    "redis": DependencyInfo(
        name="redis",
        dep_class=DependencyClass.CRITICAL,
        description="Redis job queue and cache",
        feature_gate="redis",  # critical when queue features enabled
    ),
    "neo4j": DependencyInfo(
        name="neo4j",
        dep_class=DependencyClass.NON_CRITICAL,
        description="Neo4j graph database for knowledge graph features",
        feature_gate="neo4j",
    ),
    "kafka": DependencyInfo(
        name="kafka",
        dep_class=DependencyClass.NON_CRITICAL,
        description="Kafka event streaming",
        feature_gate="kafka",
    ),
}


@dataclass
class ClassifiedHealthResult:
    """Result of evaluating dependency health with classification awareness.

    Attributes:
        ready: Whether the system should accept traffic.
        degraded: True when all critical deps are up but some non-critical are down.
        critical_down: Names of critical dependencies that are down.
        non_critical_down: Names of non-critical dependencies that are down.
        dependency_classes: Mapping of dep name -> class for the response payload.
    """

    ready: bool = True
    degraded: bool = False
    critical_down: list[str] = field(default_factory=list)
    non_critical_down: list[str] = field(default_factory=list)
    dependency_classes: dict[str, str] = field(default_factory=dict)


def get_dependency_class(name: str) -> DependencyClass:
    """Look up the class for a named dependency.

    Falls back to NON_CRITICAL for unknown dependencies (safe default).
    """
    info = DEPENDENCY_REGISTRY.get(name)
    if info is None:
        return DependencyClass.NON_CRITICAL
    return info.dep_class


def classify_health_results(
    check_results: dict[str, bool],
    required_services: set[str] | None = None,
) -> ClassifiedHealthResult:
    """Evaluate a set of dependency health checks against the classification policy.

    Args:
        check_results: Mapping of dependency name -> is_up (True/False).
        required_services: Optional override set. Dependencies in this set that
            are normally NON_CRITICAL are promoted to CRITICAL for this evaluation.

    Returns:
        ClassifiedHealthResult with readiness and degradation info.
    """
    required = required_services or set()
    result = ClassifiedHealthResult()

    for dep_name, is_up in check_results.items():
        dep_class = get_dependency_class(dep_name)

        # Promote to CRITICAL if listed in required_services
        effective_class = dep_class
        if dep_name in required and dep_class == DependencyClass.NON_CRITICAL:
            effective_class = DependencyClass.CRITICAL

        result.dependency_classes[dep_name] = effective_class.value

        if not is_up:
            if effective_class == DependencyClass.CRITICAL:
                result.critical_down.append(dep_name)
            else:
                result.non_critical_down.append(dep_name)

    # Ready only if no critical deps are down
    result.ready = len(result.critical_down) == 0
    # Degraded when ready but some non-critical deps are down
    result.degraded = result.ready and len(result.non_critical_down) > 0

    return result


def get_all_dependency_classes() -> dict[str, str]:
    """Return all registered dependency names and their classes.

    Useful for including in health response payloads.
    """
    return {
        name: info.dep_class.value for name, info in DEPENDENCY_REGISTRY.items()
    }
