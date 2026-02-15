"""Tests for P3-024: Compliance Evidence Binder Automation.

Tests cover:
- Binder generation with all 6 evidence categories
- Evidence item structure (category, title, description, artifact_path, status)
- Completeness percentage calculation
- Binder summary generation
- Category breakdown in summary
- Evidence status (collected, pending, missing) logic
- Singleton pattern (get/reset)
- Idempotent re-generation
"""

from __future__ import annotations

import pytest

from app.services.compliance_binder_service import (
    BinderSummary,
    ComplianceBinder,
    ComplianceBinderService,
    EvidenceCategory,
    EvidenceItem,
    EvidenceStatus,
    get_compliance_binder_service,
    reset_compliance_binder_service,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton before and after each test."""
    reset_compliance_binder_service()
    yield
    reset_compliance_binder_service()


@pytest.fixture
def service() -> ComplianceBinderService:
    return ComplianceBinderService()


# ============================================================================
# Binder Generation
# ============================================================================


class TestGenerateBinder:
    """Tests for generate_binder."""

    def test_returns_compliance_binder(self, service: ComplianceBinderService):
        binder = service.generate_binder()
        assert isinstance(binder, ComplianceBinder)

    def test_binder_has_id(self, service: ComplianceBinderService):
        binder = service.generate_binder()
        assert binder.binder_id.startswith("BINDER-")

    def test_binder_has_created_at(self, service: ComplianceBinderService):
        binder = service.generate_binder()
        from datetime import datetime
        datetime.fromisoformat(binder.created_at)

    def test_binder_has_items(self, service: ComplianceBinderService):
        binder = service.generate_binder()
        assert len(binder.items) > 0

    def test_all_categories_represented(self, service: ComplianceBinderService):
        binder = service.generate_binder()
        categories_found = {i.category for i in binder.items}
        for cat in EvidenceCategory:
            assert cat in categories_found, f"Missing category: {cat.value}"

    def test_items_have_required_fields(self, service: ComplianceBinderService):
        binder = service.generate_binder()
        for item in binder.items:
            assert isinstance(item, EvidenceItem)
            assert item.category in EvidenceCategory
            assert item.title
            assert item.description
            assert item.artifact_path
            assert item.status in EvidenceStatus

    def test_completeness_percent_in_range(self, service: ComplianceBinderService):
        binder = service.generate_binder()
        assert 0.0 <= binder.completeness_percent <= 100.0

    def test_completeness_matches_collected_ratio(self, service: ComplianceBinderService):
        binder = service.generate_binder()
        total = len(binder.items)
        collected = sum(1 for i in binder.items if i.status == EvidenceStatus.COLLECTED)
        expected = round(collected / total * 100.0, 1) if total > 0 else 0.0
        assert binder.completeness_percent == expected

    def test_collected_items_have_timestamp(self, service: ComplianceBinderService):
        binder = service.generate_binder()
        for item in binder.items:
            if item.status == EvidenceStatus.COLLECTED:
                assert item.collected_at, f"Collected item '{item.title}' missing timestamp"

    def test_regeneration_produces_new_binder_id(self, service: ComplianceBinderService):
        b1 = service.generate_binder()
        b2 = service.generate_binder()
        assert b1.binder_id != b2.binder_id


# ============================================================================
# Binder Summary
# ============================================================================


class TestGetBinderSummary:
    """Tests for get_binder_summary."""

    def test_returns_none_before_generation(self, service: ComplianceBinderService):
        result = service.get_binder_summary()
        assert result is None

    def test_returns_summary_after_generation(self, service: ComplianceBinderService):
        service.generate_binder()
        summary = service.get_binder_summary()
        assert isinstance(summary, BinderSummary)

    def test_summary_totals_match_binder(self, service: ComplianceBinderService):
        binder = service.generate_binder()
        summary = service.get_binder_summary()
        assert summary is not None
        assert summary.total_items == len(binder.items)
        assert summary.collected + summary.pending + summary.missing == summary.total_items

    def test_summary_has_category_breakdown(self, service: ComplianceBinderService):
        service.generate_binder()
        summary = service.get_binder_summary()
        assert summary is not None
        for cat in EvidenceCategory:
            assert cat.value in summary.by_category
            cat_data = summary.by_category[cat.value]
            assert "total" in cat_data
            assert "collected" in cat_data
            assert "pending" in cat_data
            assert "missing" in cat_data
            assert cat_data["collected"] + cat_data["pending"] + cat_data["missing"] == cat_data["total"]

    def test_summary_completeness_matches_binder(self, service: ComplianceBinderService):
        binder = service.generate_binder()
        summary = service.get_binder_summary()
        assert summary is not None
        assert summary.completeness_percent == binder.completeness_percent

    def test_summary_binder_id_matches(self, service: ComplianceBinderService):
        binder = service.generate_binder()
        summary = service.get_binder_summary()
        assert summary is not None
        assert summary.binder_id == binder.binder_id


# ============================================================================
# Evidence Categories
# ============================================================================


class TestEvidenceCategories:
    """Tests verifying all evidence categories have items."""

    def test_security_controls_items(self, service: ComplianceBinderService):
        binder = service.generate_binder()
        items = [i for i in binder.items if i.category == EvidenceCategory.SECURITY_CONTROLS]
        assert len(items) >= 2

    def test_access_management_items(self, service: ComplianceBinderService):
        binder = service.generate_binder()
        items = [i for i in binder.items if i.category == EvidenceCategory.ACCESS_MANAGEMENT]
        assert len(items) >= 2

    def test_audit_logs_items(self, service: ComplianceBinderService):
        binder = service.generate_binder()
        items = [i for i in binder.items if i.category == EvidenceCategory.AUDIT_LOGS]
        assert len(items) >= 2

    def test_data_protection_items(self, service: ComplianceBinderService):
        binder = service.generate_binder()
        items = [i for i in binder.items if i.category == EvidenceCategory.DATA_PROTECTION]
        assert len(items) >= 2

    def test_incident_response_items(self, service: ComplianceBinderService):
        binder = service.generate_binder()
        items = [i for i in binder.items if i.category == EvidenceCategory.INCIDENT_RESPONSE]
        assert len(items) >= 2

    def test_change_management_items(self, service: ComplianceBinderService):
        binder = service.generate_binder()
        items = [i for i in binder.items if i.category == EvidenceCategory.CHANGE_MANAGEMENT]
        assert len(items) >= 2


# ============================================================================
# Singleton
# ============================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_returns_same_instance(self):
        s1 = get_compliance_binder_service()
        s2 = get_compliance_binder_service()
        assert s1 is s2

    def test_reset_creates_new_instance(self):
        s1 = get_compliance_binder_service()
        reset_compliance_binder_service()
        s2 = get_compliance_binder_service()
        assert s1 is not s2
