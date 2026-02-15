"""Tests for P1-012 (guideline versioning) and P1-013 (drug safety coverage).

Covers:
- Guideline freshness checking (current, stale, expired)
- Custom staleness threshold via env var
- Guideline version info / corpus summary
- Drug pair coverage labeling (covered, partially_covered, uncovered)
- Coverage report generation
- Strict mode behavior
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import pytest

from app.services.guideline_version_service import (
    DEFAULT_STALENESS_DAYS,
    EXPIRY_DAYS,
    GuidelineMetadata,
    GuidelineStatus,
    GuidelineVersionService,
    reset_guideline_version_service,
)
from app.services.drug_safety import (
    DrugCoverageReport,
    DrugSafetyService,
    InteractionCheckResult,
    reset_drug_safety_service,
)


# ============================================================================
# Helpers
# ============================================================================

TODAY = date(2026, 2, 15)


def _make_guideline(
    guideline_id: str = "TEST-001",
    title: str = "Test Guideline",
    version: str = "1.0",
    source_org: str = "Test Org",
    published_date: date | None = None,
    superseded_by: str | None = None,
) -> GuidelineMetadata:
    return GuidelineMetadata(
        guideline_id=guideline_id,
        title=title,
        version=version,
        source_org=source_org,
        published_date=published_date or TODAY,
        superseded_by=superseded_by,
    )


# ============================================================================
# P1-012  Guideline Versioning
# ============================================================================


class TestGuidelineFreshnessChecking:
    """Guideline freshness: current, stale, expired statuses."""

    def test_current_guideline(self) -> None:
        """A recently published guideline should be CURRENT."""
        g = _make_guideline(published_date=TODAY - timedelta(days=100))
        svc = GuidelineVersionService(guidelines=[g], today=TODAY)

        result = svc.check_guideline_freshness("TEST-001")
        assert result is not None
        assert result.status == GuidelineStatus.CURRENT
        assert result.days_since_published == 100
        assert "current" in result.message.lower()

    def test_stale_guideline(self) -> None:
        """A guideline older than staleness threshold should be STALE."""
        pub = TODAY - timedelta(days=DEFAULT_STALENESS_DAYS + 10)
        g = _make_guideline(published_date=pub)
        svc = GuidelineVersionService(guidelines=[g], today=TODAY)

        result = svc.check_guideline_freshness("TEST-001")
        assert result is not None
        assert result.status == GuidelineStatus.STALE
        assert "outdated" in result.message.lower() or "stale" in result.message.lower()

    def test_expired_guideline(self) -> None:
        """A guideline older than EXPIRY_DAYS (5 years) should be EXPIRED."""
        pub = TODAY - timedelta(days=EXPIRY_DAYS + 30)
        g = _make_guideline(published_date=pub)
        svc = GuidelineVersionService(guidelines=[g], today=TODAY)

        result = svc.check_guideline_freshness("TEST-001")
        assert result is not None
        assert result.status == GuidelineStatus.EXPIRED
        assert "expired" in result.message.lower()

    def test_superseded_guideline(self) -> None:
        """A guideline that has been superseded should be SUPERSEDED."""
        g = _make_guideline(
            published_date=TODAY - timedelta(days=30),
            superseded_by="TEST-002",
        )
        svc = GuidelineVersionService(guidelines=[g], today=TODAY)

        result = svc.check_guideline_freshness("TEST-001")
        assert result is not None
        assert result.status == GuidelineStatus.SUPERSEDED
        assert "superseded" in result.message.lower()
        assert "TEST-002" in result.message

    def test_unknown_guideline_returns_none(self) -> None:
        """Checking an unknown guideline ID returns None."""
        svc = GuidelineVersionService(guidelines=[], today=TODAY)
        assert svc.check_guideline_freshness("DOES-NOT-EXIST") is None

    def test_boundary_exactly_at_staleness_threshold(self) -> None:
        """A guideline exactly at the staleness boundary is STALE."""
        pub = TODAY - timedelta(days=DEFAULT_STALENESS_DAYS)
        g = _make_guideline(published_date=pub)
        svc = GuidelineVersionService(guidelines=[g], today=TODAY)

        result = svc.check_guideline_freshness("TEST-001")
        assert result is not None
        assert result.status == GuidelineStatus.STALE

    def test_boundary_one_day_before_staleness(self) -> None:
        """A guideline one day before staleness threshold is CURRENT."""
        pub = TODAY - timedelta(days=DEFAULT_STALENESS_DAYS - 1)
        g = _make_guideline(published_date=pub)
        svc = GuidelineVersionService(guidelines=[g], today=TODAY)

        result = svc.check_guideline_freshness("TEST-001")
        assert result is not None
        assert result.status == GuidelineStatus.CURRENT


class TestCustomStalenessThreshold:
    """GUIDELINE_STALENESS_DAYS env var for custom threshold."""

    def test_custom_threshold_via_constructor(self) -> None:
        """Explicit staleness_days parameter overrides default."""
        pub = TODAY - timedelta(days=200)
        g = _make_guideline(published_date=pub)
        svc = GuidelineVersionService(
            guidelines=[g], staleness_days=180, today=TODAY,
        )

        result = svc.check_guideline_freshness("TEST-001")
        assert result is not None
        assert result.status == GuidelineStatus.STALE
        assert result.staleness_threshold_days == 180

    def test_custom_threshold_via_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GUIDELINE_STALENESS_DAYS env var sets threshold."""
        monkeypatch.setenv("GUIDELINE_STALENESS_DAYS", "365")

        pub = TODAY - timedelta(days=400)
        g = _make_guideline(published_date=pub)
        svc = GuidelineVersionService(guidelines=[g], today=TODAY)

        assert svc.staleness_threshold_days == 365
        result = svc.check_guideline_freshness("TEST-001")
        assert result is not None
        assert result.status == GuidelineStatus.STALE

    def test_invalid_env_var_falls_back_to_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Invalid env var value falls back to DEFAULT_STALENESS_DAYS."""
        monkeypatch.setenv("GUIDELINE_STALENESS_DAYS", "not-a-number")

        svc = GuidelineVersionService(guidelines=[], today=TODAY)
        assert svc.staleness_threshold_days == DEFAULT_STALENESS_DAYS

    def test_short_threshold_makes_recent_stale(self) -> None:
        """A very short threshold can make a 60-day-old guideline stale."""
        pub = TODAY - timedelta(days=60)
        g = _make_guideline(published_date=pub)
        svc = GuidelineVersionService(
            guidelines=[g], staleness_days=30, today=TODAY,
        )

        result = svc.check_guideline_freshness("TEST-001")
        assert result is not None
        assert result.status == GuidelineStatus.STALE


class TestGuidelineVersionInfo:
    """get_guideline_version_info() returns corpus summary."""

    def test_corpus_summary_counts(self) -> None:
        """Corpus info correctly counts guidelines by status."""
        guidelines = [
            _make_guideline(
                guideline_id="CURRENT",
                published_date=TODAY - timedelta(days=100),
            ),
            _make_guideline(
                guideline_id="STALE",
                published_date=TODAY - timedelta(days=DEFAULT_STALENESS_DAYS + 10),
            ),
            _make_guideline(
                guideline_id="EXPIRED",
                published_date=TODAY - timedelta(days=EXPIRY_DAYS + 100),
            ),
            _make_guideline(
                guideline_id="SUPERSEDED",
                published_date=TODAY - timedelta(days=30),
                superseded_by="CURRENT",
            ),
        ]
        svc = GuidelineVersionService(guidelines=guidelines, today=TODAY)
        info = svc.get_guideline_version_info()

        assert info.total_guidelines == 4
        assert info.current_count == 1
        assert info.stale_count == 1
        assert info.expired_count == 1
        assert info.superseded_count == 1
        assert info.staleness_threshold_days == DEFAULT_STALENESS_DAYS
        assert len(info.guidelines) == 4

    def test_empty_corpus(self) -> None:
        """Empty corpus returns zero counts."""
        svc = GuidelineVersionService(guidelines=[], today=TODAY)
        info = svc.get_guideline_version_info()
        assert info.total_guidelines == 0
        assert info.current_count == 0

    def test_builtin_guidelines_load(self) -> None:
        """Default constructor loads the built-in guideline corpus."""
        svc = GuidelineVersionService(today=TODAY)
        info = svc.get_guideline_version_info()
        assert info.total_guidelines > 0


# ============================================================================
# P1-013  Drug Safety Coverage Expansion
# ============================================================================


class TestDrugPairCoverageLabeling:
    """coverage_status field on InteractionCheckResult."""

    def setup_method(self) -> None:
        reset_drug_safety_service()
        self.svc = DrugSafetyService(use_rxnorm=False)

    def test_covered_pair_with_interaction(self) -> None:
        """Two known drugs with a known interaction are 'covered'."""
        result = self.svc.check_interactions(["warfarin", "aspirin"])
        assert result.coverage_status == "covered"
        assert result.total_interactions >= 1
        assert result.drug_coverage_warning is None

    def test_covered_pair_without_interaction(self) -> None:
        """Two known drugs without a known interaction are still 'covered'."""
        result = self.svc.check_interactions(["metformin", "sertraline"])
        assert result.coverage_status == "covered"
        assert result.drug_coverage_warning is None

    def test_uncovered_drugs(self) -> None:
        """Completely unknown drugs produce 'uncovered' with warning."""
        result = self.svc.check_interactions(["unknowndrug_x", "unknowndrug_y"])
        assert result.coverage_status == "uncovered"
        assert result.drug_coverage_warning is not None
        assert "unknowndrug_x" in result.drug_coverage_warning
        assert "unknowndrug_y" in result.drug_coverage_warning

    def test_partially_covered_drugs(self) -> None:
        """Mix of known and unknown drugs produces 'partially_covered'."""
        result = self.svc.check_interactions(["warfarin", "unknowndrug_z"])
        assert result.coverage_status == "partially_covered"
        assert result.drug_coverage_warning is not None
        assert "unknowndrug_z" in result.drug_coverage_warning

    def test_empty_drug_list(self) -> None:
        """Empty drug list returns 'covered' with no warning."""
        result = self.svc.check_interactions([])
        assert result.coverage_status == "covered"
        assert result.drug_coverage_warning is None


class TestCoverageReport:
    """get_coverage_report() method."""

    def setup_method(self) -> None:
        reset_drug_safety_service()
        self.svc = DrugSafetyService(use_rxnorm=False)

    def test_report_returns_valid_data(self) -> None:
        """Coverage report has expected fields and positive counts."""
        report = self.svc.get_coverage_report()
        assert isinstance(report, DrugCoverageReport)
        assert report.total_drugs_known > 0
        assert report.total_interactions > 0
        assert 0.0 <= report.coverage_percent <= 100.0
        assert len(report.known_drug_names) == report.total_drugs_known

    def test_report_drug_names_sorted(self) -> None:
        """Known drug names in report are sorted alphabetically."""
        report = self.svc.get_coverage_report()
        assert report.known_drug_names == sorted(report.known_drug_names)


class TestStrictMode:
    """DRUG_SAFETY_STRICT_MODE env var behavior."""

    def setup_method(self) -> None:
        reset_drug_safety_service()
        self.svc = DrugSafetyService(use_rxnorm=False)

    def test_strict_mode_off_by_default(self) -> None:
        """Without env var, warning does not contain STRICT MODE prefix."""
        result = self.svc.check_interactions(["warfarin", "unknowndrug_z"])
        assert result.drug_coverage_warning is not None
        assert "[STRICT MODE]" not in result.drug_coverage_warning

    def test_strict_mode_on(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With DRUG_SAFETY_STRICT_MODE=true, warning has STRICT MODE prefix."""
        monkeypatch.setenv("DRUG_SAFETY_STRICT_MODE", "true")

        result = self.svc.check_interactions(["warfarin", "unknowndrug_z"])
        assert result.drug_coverage_warning is not None
        assert result.drug_coverage_warning.startswith("[STRICT MODE]")

    def test_strict_mode_with_value_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DRUG_SAFETY_STRICT_MODE=1 also activates strict mode."""
        monkeypatch.setenv("DRUG_SAFETY_STRICT_MODE", "1")

        result = self.svc.check_interactions(["warfarin", "unknowndrug_z"])
        assert result.drug_coverage_warning is not None
        assert "[STRICT MODE]" in result.drug_coverage_warning

    def test_strict_mode_no_warning_when_covered(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Strict mode does not produce warning when all drugs are covered."""
        monkeypatch.setenv("DRUG_SAFETY_STRICT_MODE", "true")

        result = self.svc.check_interactions(["warfarin", "aspirin"])
        assert result.drug_coverage_warning is None
        assert result.coverage_status == "covered"


class TestBrandNameResolution:
    """Coverage works with brand-name drugs resolved via aliases."""

    def setup_method(self) -> None:
        reset_drug_safety_service()
        self.svc = DrugSafetyService(use_rxnorm=False)

    def test_brand_name_resolves_to_covered(self) -> None:
        """Brand names that resolve to known generics are 'covered'."""
        result = self.svc.check_interactions(["Coumadin", "Advil"])
        assert result.coverage_status == "covered"
        # warfarin + ibuprofen should have a known interaction
        assert result.total_interactions >= 1
