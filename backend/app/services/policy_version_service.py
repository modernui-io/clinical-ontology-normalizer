"""Clinical Policy Versioning Service (P3-014).

Provides semantic versioning for clinical policy and confidence rule packs.
Every clinical response should embed the active policy version for auditability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
import hashlib
import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Semantic version pattern: MAJOR.MINOR.PATCH with optional pre-release
_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z\-.]+))?$"
)


@dataclass
class PolicyRule:
    """A single rule within a policy pack."""

    rule_id: str
    description: str
    severity: str  # "critical" | "warning" | "info"
    expression: str  # human-readable rule expression
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "description": self.description,
            "severity": self.severity,
            "expression": self.expression,
            "enabled": self.enabled,
        }


@dataclass
class PolicyPack:
    """A versioned collection of clinical policy rules."""

    name: str
    version: str  # semver string, e.g. "1.2.0"
    effective_date: date
    rules: list[PolicyRule] = field(default_factory=list)
    checksum: str = ""  # SHA-256 of canonical rule content

    def __post_init__(self) -> None:
        if not self.checksum:
            self.checksum = self._compute_checksum()

    def _compute_checksum(self) -> str:
        """Compute SHA-256 checksum over canonical rule content."""
        canonical = json.dumps(
            [r.to_dict() for r in self.rules],
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "effective_date": self.effective_date.isoformat(),
            "rules": [r.to_dict() for r in self.rules],
            "checksum": self.checksum,
        }

    def audit_stamp(self) -> dict[str, str]:
        """Return minimal audit info to embed in clinical responses."""
        return {
            "policy_name": self.name,
            "policy_version": self.version,
            "policy_checksum": self.checksum[:16],
            "effective_date": self.effective_date.isoformat(),
        }


@dataclass
class PolicyDiff:
    """Summary of differences between two policy pack versions."""

    old_version: str
    new_version: str
    added_rules: list[str]
    removed_rules: list[str]
    modified_rules: list[str]
    severity_changes: list[str]
    is_breaking: bool  # True if major version bump is warranted

    def to_dict(self) -> dict[str, Any]:
        return {
            "old_version": self.old_version,
            "new_version": self.new_version,
            "added_rules": self.added_rules,
            "removed_rules": self.removed_rules,
            "modified_rules": self.modified_rules,
            "severity_changes": self.severity_changes,
            "is_breaking": self.is_breaking,
        }


# ---------------------------------------------------------------------------
# Default policy pack
# ---------------------------------------------------------------------------

_DEFAULT_RULES: list[PolicyRule] = [
    PolicyRule(
        rule_id="CONF-001",
        description="Flag low-confidence predictions for human review",
        severity="warning",
        expression="confidence < 0.5",
    ),
    PolicyRule(
        rule_id="CONF-002",
        description="Reject predictions with extremely low confidence",
        severity="critical",
        expression="confidence < 0.2",
    ),
    PolicyRule(
        rule_id="SAFETY-001",
        description="Require contraindication check for medication queries",
        severity="critical",
        expression="question_class == 'medication_query' and not contraindication_checked",
    ),
    PolicyRule(
        rule_id="SAFETY-002",
        description="Flag pregnancy category D/X drugs in reproductive age patients",
        severity="critical",
        expression="pregnancy_category in ('D', 'X') and patient_age >= 12 and patient_age <= 50",
    ),
    PolicyRule(
        rule_id="AUDIT-001",
        description="Attach policy version to every clinical response",
        severity="info",
        expression="always",
    ),
    PolicyRule(
        rule_id="SCOPE-001",
        description="Warn when query falls outside trained domain",
        severity="warning",
        expression="domain_coverage < 0.3",
    ),
]

_DEFAULT_PACK = PolicyPack(
    name="clinical-confidence-policy",
    version="1.0.0",
    effective_date=date(2026, 1, 1),
    rules=_DEFAULT_RULES,
)


# ---------------------------------------------------------------------------
# Singleton state
# ---------------------------------------------------------------------------

_active_pack: PolicyPack = _DEFAULT_PACK


def get_active_policy_pack() -> PolicyPack:
    """Return the currently active policy pack."""
    return _active_pack


def set_active_policy_pack(pack: PolicyPack) -> None:
    """Replace the active policy pack (for testing or hot-reload)."""
    global _active_pack
    validate_policy_version(pack)
    _active_pack = pack
    logger.info("Active policy pack set to %s v%s", pack.name, pack.version)


def reset_active_policy_pack() -> None:
    """Reset to the default policy pack (for testing)."""
    global _active_pack
    _active_pack = _DEFAULT_PACK


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class PolicyValidationError(Exception):
    """Raised when a policy pack fails validation."""


def validate_policy_version(pack: PolicyPack) -> None:
    """Validate a policy pack's version format and checksum integrity.

    Raises:
        PolicyValidationError: If validation fails.
    """
    # Validate semver format
    if not _SEMVER_RE.match(pack.version):
        raise PolicyValidationError(
            f"Invalid semantic version: '{pack.version}'. "
            "Expected format: MAJOR.MINOR.PATCH (e.g., 1.2.3)"
        )

    # Validate checksum integrity
    expected = pack._compute_checksum()
    if pack.checksum != expected:
        raise PolicyValidationError(
            f"Checksum mismatch for policy '{pack.name}' v{pack.version}. "
            f"Expected {expected[:16]}..., got {pack.checksum[:16]}..."
        )

    # Validate rules have unique IDs
    rule_ids = [r.rule_id for r in pack.rules]
    if len(rule_ids) != len(set(rule_ids)):
        duplicates = [rid for rid in rule_ids if rule_ids.count(rid) > 1]
        raise PolicyValidationError(
            f"Duplicate rule IDs found: {set(duplicates)}"
        )

    logger.debug("Policy pack %s v%s passed validation", pack.name, pack.version)


# ---------------------------------------------------------------------------
# Version comparison / diff
# ---------------------------------------------------------------------------


def parse_semver(version: str) -> tuple[int, int, int]:
    """Parse a semver string into (major, minor, patch)."""
    m = _SEMVER_RE.match(version)
    if not m:
        raise ValueError(f"Invalid semver: {version}")
    return int(m.group("major")), int(m.group("minor")), int(m.group("patch"))


def compare_policy_versions(old: PolicyPack, new: PolicyPack) -> PolicyDiff:
    """Compare two policy packs and produce a diff summary.

    Args:
        old: The previous policy pack.
        new: The proposed/new policy pack.

    Returns:
        PolicyDiff with lists of added, removed, and modified rules.
    """
    old_map = {r.rule_id: r for r in old.rules}
    new_map = {r.rule_id: r for r in new.rules}

    old_ids = set(old_map)
    new_ids = set(new_map)

    added = sorted(new_ids - old_ids)
    removed = sorted(old_ids - new_ids)

    modified: list[str] = []
    severity_changes: list[str] = []

    for rid in sorted(old_ids & new_ids):
        old_rule = old_map[rid]
        new_rule = new_map[rid]
        if old_rule.to_dict() != new_rule.to_dict():
            modified.append(rid)
        if old_rule.severity != new_rule.severity:
            severity_changes.append(
                f"{rid}: {old_rule.severity} -> {new_rule.severity}"
            )

    # A breaking change is indicated if critical rules were removed or severity downgraded
    is_breaking = bool(removed) or any(
        old_map.get(rid) and old_map[rid].severity == "critical"
        for rid in removed
    )

    return PolicyDiff(
        old_version=old.version,
        new_version=new.version,
        added_rules=added,
        removed_rules=removed,
        modified_rules=modified,
        severity_changes=severity_changes,
        is_breaking=is_breaking,
    )
