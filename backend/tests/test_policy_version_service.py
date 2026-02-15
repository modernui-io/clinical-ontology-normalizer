"""Tests for Policy Version Service (P3-014)."""

import pytest
from datetime import date

from app.services.policy_version_service import (
    PolicyRule,
    PolicyPack,
    PolicyDiff,
    PolicyValidationError,
    get_active_policy_pack,
    set_active_policy_pack,
    reset_active_policy_pack,
    validate_policy_version,
    compare_policy_versions,
    parse_semver,
)


@pytest.fixture(autouse=True)
def _reset_policy():
    """Reset policy singleton before each test."""
    reset_active_policy_pack()


def _make_rule(rule_id: str = "R-001", severity: str = "warning") -> PolicyRule:
    return PolicyRule(
        rule_id=rule_id,
        description=f"Test rule {rule_id}",
        severity=severity,
        expression="test_expression",
        enabled=True,
    )


def _make_pack(
    version: str = "1.0.0",
    rules: list[PolicyRule] | None = None,
) -> PolicyPack:
    if rules is None:
        rules = [_make_rule()]
    return PolicyPack(
        name="test-policy",
        version=version,
        effective_date=date(2026, 1, 1),
        rules=rules,
    )


# ---------------------------------------------------------------------------
# PolicyRule
# ---------------------------------------------------------------------------


class TestPolicyRule:
    def test_to_dict(self):
        r = _make_rule()
        d = r.to_dict()
        assert d["rule_id"] == "R-001"
        assert d["enabled"] is True


# ---------------------------------------------------------------------------
# PolicyPack
# ---------------------------------------------------------------------------


class TestPolicyPack:
    def test_checksum_auto_computed(self):
        pack = _make_pack()
        assert pack.checksum
        assert len(pack.checksum) == 64  # SHA-256 hex digest

    def test_checksum_changes_with_rules(self):
        pack1 = _make_pack(rules=[_make_rule("A")])
        pack2 = _make_pack(rules=[_make_rule("B")])
        assert pack1.checksum != pack2.checksum

    def test_to_dict(self):
        pack = _make_pack()
        d = pack.to_dict()
        assert d["name"] == "test-policy"
        assert d["version"] == "1.0.0"
        assert len(d["rules"]) == 1

    def test_audit_stamp(self):
        pack = _make_pack()
        stamp = pack.audit_stamp()
        assert stamp["policy_name"] == "test-policy"
        assert stamp["policy_version"] == "1.0.0"
        assert len(stamp["policy_checksum"]) == 16


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_valid_pack(self):
        pack = _make_pack("2.1.3")
        validate_policy_version(pack)  # should not raise

    def test_invalid_semver(self):
        pack = _make_pack("not-a-version")
        with pytest.raises(PolicyValidationError, match="Invalid semantic version"):
            validate_policy_version(pack)

    def test_invalid_semver_two_part(self):
        pack = _make_pack("1.0")
        with pytest.raises(PolicyValidationError):
            validate_policy_version(pack)

    def test_checksum_mismatch(self):
        pack = _make_pack()
        pack.checksum = "0" * 64  # wrong checksum
        with pytest.raises(PolicyValidationError, match="Checksum mismatch"):
            validate_policy_version(pack)

    def test_duplicate_rule_ids(self):
        rules = [_make_rule("DUP"), _make_rule("DUP")]
        pack = _make_pack(rules=rules)
        with pytest.raises(PolicyValidationError, match="Duplicate rule IDs"):
            validate_policy_version(pack)

    def test_prerelease_version_accepted(self):
        pack = _make_pack("1.0.0-beta.1")
        validate_policy_version(pack)  # should not raise


# ---------------------------------------------------------------------------
# Active pack management
# ---------------------------------------------------------------------------


class TestActivePack:
    def test_default_pack_exists(self):
        pack = get_active_policy_pack()
        assert pack is not None
        assert pack.name == "clinical-confidence-policy"
        assert pack.version == "1.0.0"

    def test_set_active_pack(self):
        new_pack = _make_pack("2.0.0")
        set_active_policy_pack(new_pack)
        assert get_active_policy_pack().version == "2.0.0"

    def test_set_invalid_pack_rejected(self):
        bad_pack = _make_pack("bad")
        with pytest.raises(PolicyValidationError):
            set_active_policy_pack(bad_pack)

    def test_reset_restores_default(self):
        new_pack = _make_pack("3.0.0")
        set_active_policy_pack(new_pack)
        reset_active_policy_pack()
        assert get_active_policy_pack().version == "1.0.0"


# ---------------------------------------------------------------------------
# Version parsing
# ---------------------------------------------------------------------------


class TestParseSemver:
    def test_basic(self):
        assert parse_semver("1.2.3") == (1, 2, 3)

    def test_zero(self):
        assert parse_semver("0.0.0") == (0, 0, 0)

    def test_invalid(self):
        with pytest.raises(ValueError):
            parse_semver("abc")


# ---------------------------------------------------------------------------
# Version comparison / diff
# ---------------------------------------------------------------------------


class TestCompareVersions:
    def test_no_changes(self):
        pack = _make_pack("1.0.0")
        diff = compare_policy_versions(pack, pack)
        assert diff.added_rules == []
        assert diff.removed_rules == []
        assert diff.modified_rules == []

    def test_added_rule(self):
        old = _make_pack("1.0.0", rules=[_make_rule("A")])
        new = _make_pack("1.1.0", rules=[_make_rule("A"), _make_rule("B")])
        diff = compare_policy_versions(old, new)
        assert "B" in diff.added_rules
        assert diff.removed_rules == []

    def test_removed_rule(self):
        old = _make_pack("1.0.0", rules=[_make_rule("A"), _make_rule("B")])
        new = _make_pack("2.0.0", rules=[_make_rule("A")])
        diff = compare_policy_versions(old, new)
        assert "B" in diff.removed_rules
        assert diff.is_breaking

    def test_modified_rule(self):
        r1 = _make_rule("A")
        r2 = PolicyRule(
            rule_id="A",
            description="Changed description",
            severity="warning",
            expression="test_expression",
            enabled=True,
        )
        old = _make_pack("1.0.0", rules=[r1])
        new = _make_pack("1.0.1", rules=[r2])
        diff = compare_policy_versions(old, new)
        assert "A" in diff.modified_rules

    def test_severity_change_tracked(self):
        r1 = _make_rule("A", severity="warning")
        r2 = PolicyRule(
            rule_id="A",
            description="Test rule A",
            severity="critical",
            expression="test_expression",
            enabled=True,
        )
        old = _make_pack("1.0.0", rules=[r1])
        new = _make_pack("1.1.0", rules=[r2])
        diff = compare_policy_versions(old, new)
        assert len(diff.severity_changes) == 1
        assert "warning -> critical" in diff.severity_changes[0]

    def test_diff_to_dict(self):
        old = _make_pack("1.0.0", rules=[_make_rule("A")])
        new = _make_pack("1.1.0", rules=[_make_rule("A"), _make_rule("B")])
        diff = compare_policy_versions(old, new)
        d = diff.to_dict()
        assert d["old_version"] == "1.0.0"
        assert d["new_version"] == "1.1.0"
        assert "B" in d["added_rules"]
