"""P3-013: Tests for stale-guideline detection and alert generation."""

from __future__ import annotations

from datetime import date

import pytest

from app.services.guideline_version_service import (
    APPROACHING_STALE_DAYS,
    DEFAULT_STALENESS_DAYS,
    EXPIRY_DAYS,
    GuidelineAlert,
    GuidelineAlertType,
    GuidelineMetadata,
    GuidelineStatus,
    GuidelineVersionService,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_guideline(
    gid: str,
    title: str,
    published: date,
    source_org: str = "TestOrg",
    superseded_by: str | None = None,
) -> GuidelineMetadata:
    return GuidelineMetadata(
        guideline_id=gid,
        title=title,
        version="1.0",
        source_org=source_org,
        published_date=published,
        superseded_by=superseded_by,
    )


FIXED_TODAY = date(2026, 2, 15)


def _service(guidelines: list[GuidelineMetadata], staleness_days: int | None = None) -> GuidelineVersionService:
    return GuidelineVersionService(
        guidelines=guidelines,
        staleness_days=staleness_days,
        today=FIXED_TODAY,
    )


# ===========================================================================
# check_all_guidelines_freshness
# ===========================================================================


class TestCheckAllGuidelinesFreshness:
    def test_returns_empty_when_all_current(self):
        svc = _service([
            _make_guideline("G1", "Current Guide", date(2025, 6, 1)),
        ])
        results = svc.check_all_guidelines_freshness()
        assert results == []

    def test_returns_stale_guidelines(self):
        svc = _service([
            _make_guideline("G1", "Stale Guide", date(2023, 1, 1)),
        ])
        results = svc.check_all_guidelines_freshness()
        assert len(results) == 1
        assert results[0].guideline_id == "G1"
        assert results[0].status == GuidelineStatus.STALE

    def test_returns_expired_guidelines(self):
        svc = _service([
            _make_guideline("G1", "Expired Guide", date(2019, 1, 1)),
        ])
        results = svc.check_all_guidelines_freshness()
        assert len(results) == 1
        assert results[0].status == GuidelineStatus.EXPIRED

    def test_excludes_superseded(self):
        svc = _service([
            _make_guideline("G1", "Superseded", date(2020, 1, 1), superseded_by="G2"),
            _make_guideline("G2", "Replacement", date(2025, 6, 1)),
        ])
        results = svc.check_all_guidelines_freshness()
        # Superseded should not appear; G2 is current so also excluded
        assert len(results) == 0

    def test_mixed_corpus(self):
        svc = _service([
            _make_guideline("CURR", "Current", date(2025, 6, 1)),
            _make_guideline("STALE", "Stale", date(2023, 6, 1)),
            _make_guideline("EXP", "Expired", date(2018, 1, 1)),
        ])
        results = svc.check_all_guidelines_freshness()
        ids = {r.guideline_id for r in results}
        assert ids == {"STALE", "EXP"}


# ===========================================================================
# get_guidelines_needing_review
# ===========================================================================


class TestGetGuidelinesNeedingReview:
    def test_returns_approaching_stale(self):
        # Published 660 days before FIXED_TODAY => 70 days until stale (within 90-day window)
        pub_date = date(2024, 4, 22)  # ~665 days before 2026-02-15
        svc = _service([
            _make_guideline("G1", "Almost Stale", pub_date),
        ])
        results = svc.get_guidelines_needing_review()
        assert len(results) == 1
        assert results[0].guideline_id == "G1"

    def test_excludes_far_from_stale(self):
        svc = _service([
            _make_guideline("G1", "Very Fresh", date(2025, 12, 1)),
        ])
        results = svc.get_guidelines_needing_review()
        assert results == []

    def test_excludes_already_stale(self):
        svc = _service([
            _make_guideline("G1", "Already Stale", date(2023, 1, 1)),
        ])
        results = svc.get_guidelines_needing_review()
        assert results == []

    def test_custom_staleness_threshold(self):
        # 100-day staleness, published 50 days ago => 50 days until stale (within 90)
        svc = _service(
            [_make_guideline("G1", "Short Window", date(2025, 12, 27))],
            staleness_days=100,
        )
        results = svc.get_guidelines_needing_review()
        assert len(results) == 1


# ===========================================================================
# GuidelineAlert model
# ===========================================================================


class TestGuidelineAlertModel:
    def test_alert_fields(self):
        alert = GuidelineAlert(
            guideline_id="G1",
            title="Test",
            alert_type=GuidelineAlertType.STALE,
            days_until_stale=-10,
            owner_email="team@example.com",
        )
        assert alert.alert_type == GuidelineAlertType.STALE
        assert alert.owner_email == "team@example.com"

    def test_alert_type_values(self):
        assert GuidelineAlertType.APPROACHING_STALE.value == "approaching_stale"
        assert GuidelineAlertType.STALE.value == "stale"
        assert GuidelineAlertType.EXPIRED.value == "expired"


# ===========================================================================
# generate_alerts
# ===========================================================================


class TestGenerateAlerts:
    def test_expired_generates_alert(self):
        svc = _service([
            _make_guideline("G1", "Old Guide", date(2018, 1, 1), source_org="OldOrg"),
        ])
        alerts = svc.generate_alerts()
        assert len(alerts) == 1
        assert alerts[0].alert_type == GuidelineAlertType.EXPIRED
        assert alerts[0].days_until_stale is None
        assert alerts[0].owner_email is not None

    def test_stale_generates_alert(self):
        svc = _service([
            _make_guideline("G1", "Stale Guide", date(2023, 6, 1), source_org="StaleOrg"),
        ])
        alerts = svc.generate_alerts()
        assert len(alerts) == 1
        assert alerts[0].alert_type == GuidelineAlertType.STALE
        assert alerts[0].days_until_stale is not None

    def test_approaching_stale_generates_alert(self):
        pub_date = date(2024, 4, 22)  # ~665 days before 2026-02-15, within 90-day window
        svc = _service([
            _make_guideline("G1", "Almost Stale", pub_date, source_org="SomeOrg"),
        ])
        alerts = svc.generate_alerts()
        assert len(alerts) == 1
        assert alerts[0].alert_type == GuidelineAlertType.APPROACHING_STALE
        assert alerts[0].days_until_stale is not None
        assert 0 < alerts[0].days_until_stale <= APPROACHING_STALE_DAYS

    def test_current_no_alert(self):
        svc = _service([
            _make_guideline("G1", "Fresh", date(2025, 12, 1)),
        ])
        alerts = svc.generate_alerts()
        assert alerts == []

    def test_superseded_no_alert(self):
        svc = _service([
            _make_guideline("G1", "Superseded", date(2020, 1, 1), superseded_by="G2"),
        ])
        alerts = svc.generate_alerts()
        assert alerts == []

    def test_owner_email_derived_from_source_org(self):
        svc = _service([
            _make_guideline("G1", "Stale", date(2023, 1, 1), source_org="ACC/AHA"),
        ])
        alerts = svc.generate_alerts()
        assert len(alerts) == 1
        assert "acc-aha" in alerts[0].owner_email

    def test_mixed_corpus_alert_counts(self):
        svc = _service([
            _make_guideline("CURR", "Current", date(2025, 12, 1)),
            _make_guideline("APPROACH", "Approaching", date(2024, 4, 22)),
            _make_guideline("STALE", "Stale", date(2023, 6, 1)),
            _make_guideline("EXP", "Expired", date(2018, 1, 1)),
            _make_guideline("SUP", "Superseded", date(2020, 1, 1), superseded_by="CURR"),
        ])
        alerts = svc.generate_alerts()
        types = {a.alert_type for a in alerts}
        assert GuidelineAlertType.APPROACHING_STALE in types
        assert GuidelineAlertType.STALE in types
        assert GuidelineAlertType.EXPIRED in types
        assert len(alerts) == 3  # approach + stale + expired

    def test_generate_alerts_with_builtin_corpus(self):
        """Smoke test: generate_alerts works against the built-in corpus."""
        svc = GuidelineVersionService(today=FIXED_TODAY)
        alerts = svc.generate_alerts()
        # Should have at least one alert (APA-MDD-2010 is expired)
        assert len(alerts) >= 1
        alert_ids = {a.guideline_id for a in alerts}
        assert "APA-MDD-2010" in alert_ids
