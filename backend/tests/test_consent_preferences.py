"""Tests for Patient Consent Preference Center (VP-Product-7).

Covers:
- Seed data verification (profiles, templates, audit trail)
- Profile queries (get, list, filter by status, pagination)
- Single preference updates (opt-in, opt-out, channel prefs, sources)
- Bulk preference updates
- Consent withdrawal (single category, all categories, reason required)
- Audit trail (per-patient, per-category, ordering, limits)
- Consent checks (category, category+channel, expired, unknown patient)
- Expiring consent detection
- Template management (list, get, apply)
- Consent export for data portability
- Program-wide metrics calculation
- API endpoint integration tests (all 16+ endpoints)
- Edge cases (unknown patients, empty reasons, duplicate updates)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.consent_preferences import (
    ConsentAction,
    ConsentCategory,
    ConsentSource,
    OverallConsentStatus,
    PreferenceStatus,
)
from app.services.consent_preferences_service import (
    ConsentPreferencesService,
    get_consent_preferences_service,
    reset_consent_preferences_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_PREFIX = "/api/v1/consent-preferences"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_service():
    """Ensure a fresh service for every test."""
    reset_consent_preferences_service()
    svc = get_consent_preferences_service()
    yield svc
    reset_consent_preferences_service()


@pytest.fixture
def svc(clean_service) -> ConsentPreferencesService:
    """Shorthand for the clean service."""
    return clean_service


# ===========================================================================
# 1. Seed Data Verification
# ===========================================================================


class TestSeedData:
    """Verify the service seeds correctly."""

    def test_seed_creates_profiles(self, svc: ConsentPreferencesService):
        profiles, total = svc.list_profiles()
        assert total == 12
        assert len(profiles) == 12

    def test_seed_creates_templates(self, svc: ConsentPreferencesService):
        templates = svc.get_templates()
        assert len(templates) == 2

    def test_seed_standard_template(self, svc: ConsentPreferencesService):
        tmpl = svc.get_template("tmpl-standard")
        assert tmpl.name == "Standard Clinical Trial"
        assert len(tmpl.categories) == 4
        assert len(tmpl.required_categories) == 2

    def test_seed_enhanced_template(self, svc: ConsentPreferencesService):
        tmpl = svc.get_template("tmpl-enhanced")
        assert tmpl.name == "Enhanced Research"
        assert len(tmpl.categories) == 8
        assert len(tmpl.required_categories) == 3

    def test_seed_fully_consented_patients(self, svc: ConsentPreferencesService):
        p1 = svc.get_profile("PAT-001")
        assert p1.overall_consent_status == OverallConsentStatus.FULL

    def test_seed_partially_consented_patients(self, svc: ConsentPreferencesService):
        p3 = svc.get_profile("PAT-003")
        assert p3.overall_consent_status == OverallConsentStatus.PARTIAL

    def test_seed_withdrawn_patients(self, svc: ConsentPreferencesService):
        p6 = svc.get_profile("PAT-006")
        assert p6.overall_consent_status == OverallConsentStatus.WITHDRAWN

    def test_seed_pending_patients(self, svc: ConsentPreferencesService):
        p8 = svc.get_profile("PAT-008")
        assert p8.overall_consent_status == OverallConsentStatus.PENDING

    def test_seed_audit_entries_exist(self, svc: ConsentPreferencesService):
        trail = svc.get_audit_trail("PAT-001")
        assert len(trail) > 0

    def test_seed_profile_completeness(self, svc: ConsentPreferencesService):
        p1 = svc.get_profile("PAT-001")
        assert p1.profile_completeness_pct == 100.0

    def test_seed_pending_completeness_zero(self, svc: ConsentPreferencesService):
        p8 = svc.get_profile("PAT-008")
        assert p8.profile_completeness_pct == 0.0


# ===========================================================================
# 2. Profile Queries
# ===========================================================================


class TestProfileQueries:
    """Tests for get_profile and list_profiles."""

    def test_get_profile_existing(self, svc: ConsentPreferencesService):
        profile = svc.get_profile("PAT-001")
        assert profile.patient_id == "PAT-001"
        assert len(profile.preferences) == 8  # all categories

    def test_get_profile_not_found(self, svc: ConsentPreferencesService):
        with pytest.raises(KeyError, match="not found"):
            svc.get_profile("PAT-NONEXISTENT")

    def test_list_profiles_all(self, svc: ConsentPreferencesService):
        profiles, total = svc.list_profiles()
        assert total == 12

    def test_list_profiles_filter_full(self, svc: ConsentPreferencesService):
        profiles, total = svc.list_profiles(status=OverallConsentStatus.FULL)
        assert total == 2
        for p in profiles:
            assert p.overall_consent_status == OverallConsentStatus.FULL

    def test_list_profiles_filter_withdrawn(self, svc: ConsentPreferencesService):
        profiles, total = svc.list_profiles(status=OverallConsentStatus.WITHDRAWN)
        assert total == 2

    def test_list_profiles_filter_pending(self, svc: ConsentPreferencesService):
        profiles, total = svc.list_profiles(status=OverallConsentStatus.PENDING)
        assert total == 2

    def test_list_profiles_filter_partial(self, svc: ConsentPreferencesService):
        profiles, total = svc.list_profiles(status=OverallConsentStatus.PARTIAL)
        assert total == 6  # PAT-003, PAT-004, PAT-005, PAT-010, PAT-011, PAT-012

    def test_list_profiles_pagination_limit(self, svc: ConsentPreferencesService):
        profiles, total = svc.list_profiles(limit=3)
        assert len(profiles) == 3
        assert total == 12

    def test_list_profiles_pagination_offset(self, svc: ConsentPreferencesService):
        profiles, total = svc.list_profiles(limit=5, offset=10)
        assert len(profiles) == 2  # only 2 left at offset 10
        assert total == 12


# ===========================================================================
# 3. Single Preference Updates
# ===========================================================================


class TestPreferenceUpdate:
    """Tests for update_preference."""

    def test_update_opt_in(self, svc: ConsentPreferencesService):
        pref = svc.update_preference(
            patient_id="PAT-008",
            category=ConsentCategory.TRIAL_SCREENING,
            status=PreferenceStatus.OPTED_IN,
            grantor="coordinator-1",
        )
        assert pref.status == PreferenceStatus.OPTED_IN
        assert pref.patient_id == "PAT-008"
        assert pref.category == ConsentCategory.TRIAL_SCREENING

    def test_update_opt_out(self, svc: ConsentPreferencesService):
        pref = svc.update_preference(
            patient_id="PAT-001",
            category=ConsentCategory.ANALYTICS,
            status=PreferenceStatus.OPTED_OUT,
            grantor="patient",
        )
        assert pref.status == PreferenceStatus.OPTED_OUT

    def test_update_channel_preferences(self, svc: ConsentPreferencesService):
        channels = {"EMAIL": True, "SMS": True, "PHONE": False, "PORTAL": True, "MAIL": False}
        pref = svc.update_preference(
            patient_id="PAT-001",
            category=ConsentCategory.COMMUNICATION,
            status=PreferenceStatus.OPTED_IN,
            channel_prefs=channels,
            grantor="patient",
        )
        assert pref.channel_preferences["SMS"] is True
        assert pref.channel_preferences["PHONE"] is False

    def test_update_with_source(self, svc: ConsentPreferencesService):
        pref = svc.update_preference(
            patient_id="PAT-001",
            category=ConsentCategory.DATA_SHARING,
            status=PreferenceStatus.OPTED_IN,
            source=ConsentSource.PAPER_FORM,
            grantor="coordinator",
        )
        assert pref.source == ConsentSource.PAPER_FORM

    def test_update_with_ip_address(self, svc: ConsentPreferencesService):
        pref = svc.update_preference(
            patient_id="PAT-001",
            category=ConsentCategory.DATA_SHARING,
            status=PreferenceStatus.OPTED_IN,
            grantor="patient",
            ip_address="192.168.1.100",
        )
        assert pref.ip_address == "192.168.1.100"

    def test_update_increments_version(self, svc: ConsentPreferencesService):
        # First get current version
        profile = svc.get_profile("PAT-001")
        old_pref = None
        for p in profile.preferences:
            if p.category == ConsentCategory.ANALYTICS:
                old_pref = p
                break
        assert old_pref is not None
        old_version = old_pref.version

        pref = svc.update_preference(
            patient_id="PAT-001",
            category=ConsentCategory.ANALYTICS,
            status=PreferenceStatus.OPTED_OUT,
            grantor="patient",
        )
        assert pref.version == old_version + 1

    def test_update_creates_audit_entry(self, svc: ConsentPreferencesService):
        trail_before = svc.get_audit_trail("PAT-001", category=ConsentCategory.ANALYTICS)
        count_before = len(trail_before)

        svc.update_preference(
            patient_id="PAT-001",
            category=ConsentCategory.ANALYTICS,
            status=PreferenceStatus.OPTED_OUT,
            grantor="patient",
        )

        trail_after = svc.get_audit_trail("PAT-001", category=ConsentCategory.ANALYTICS)
        assert len(trail_after) == count_before + 1

    def test_update_recalculates_overall_status(self, svc: ConsentPreferencesService):
        # PAT-001 is FULL; opt out of one category should make it PARTIAL
        assert svc.get_profile("PAT-001").overall_consent_status == OverallConsentStatus.FULL
        svc.update_preference(
            patient_id="PAT-001",
            category=ConsentCategory.ANALYTICS,
            status=PreferenceStatus.OPTED_OUT,
            grantor="patient",
        )
        assert svc.get_profile("PAT-001").overall_consent_status == OverallConsentStatus.PARTIAL

    def test_update_creates_new_patient_profile(self, svc: ConsentPreferencesService):
        pref = svc.update_preference(
            patient_id="PAT-NEW",
            category=ConsentCategory.TRIAL_SCREENING,
            status=PreferenceStatus.OPTED_IN,
            grantor="coordinator",
        )
        assert pref.patient_id == "PAT-NEW"
        profile = svc.get_profile("PAT-NEW")
        assert profile.patient_id == "PAT-NEW"


# ===========================================================================
# 4. Bulk Preference Updates
# ===========================================================================


class TestBulkUpdate:
    """Tests for bulk_update_preferences."""

    def test_bulk_update_multiple_categories(self, svc: ConsentPreferencesService):
        profile = svc.bulk_update_preferences(
            patient_id="PAT-008",
            preferences=[
                {
                    "category": ConsentCategory.TRIAL_SCREENING,
                    "status": PreferenceStatus.OPTED_IN,
                    "grantor": "coordinator",
                },
                {
                    "category": ConsentCategory.DATA_SHARING,
                    "status": PreferenceStatus.OPTED_IN,
                    "grantor": "coordinator",
                },
                {
                    "category": ConsentCategory.COMMUNICATION,
                    "status": PreferenceStatus.OPTED_OUT,
                    "grantor": "coordinator",
                },
            ],
        )
        assert profile.patient_id == "PAT-008"
        statuses = {p.category: p.status for p in profile.preferences}
        assert statuses[ConsentCategory.TRIAL_SCREENING] == PreferenceStatus.OPTED_IN
        assert statuses[ConsentCategory.DATA_SHARING] == PreferenceStatus.OPTED_IN
        assert statuses[ConsentCategory.COMMUNICATION] == PreferenceStatus.OPTED_OUT

    def test_bulk_update_creates_audit_for_each(self, svc: ConsentPreferencesService):
        svc.bulk_update_preferences(
            patient_id="PAT-NEW-BULK",
            preferences=[
                {"category": ConsentCategory.TRIAL_SCREENING, "status": PreferenceStatus.OPTED_IN, "grantor": "sys"},
                {"category": ConsentCategory.DATA_SHARING, "status": PreferenceStatus.OPTED_IN, "grantor": "sys"},
            ],
        )
        trail = svc.get_audit_trail("PAT-NEW-BULK")
        assert len(trail) == 2


# ===========================================================================
# 5. Consent Withdrawal
# ===========================================================================


class TestWithdrawal:
    """Tests for withdraw_consent and withdraw_all_consent."""

    def test_withdraw_single_category(self, svc: ConsentPreferencesService):
        pref = svc.withdraw_consent(
            patient_id="PAT-001",
            category=ConsentCategory.BIOBANK,
            reason="No longer interested in biobanking",
        )
        assert pref.status == PreferenceStatus.OPTED_OUT
        assert pref.withdrawal_reason == "No longer interested in biobanking"

    def test_withdraw_requires_reason(self, svc: ConsentPreferencesService):
        with pytest.raises(ValueError, match="required"):
            svc.withdraw_consent(
                patient_id="PAT-001",
                category=ConsentCategory.BIOBANK,
                reason="",
            )

    def test_withdraw_empty_whitespace_reason(self, svc: ConsentPreferencesService):
        with pytest.raises(ValueError, match="required"):
            svc.withdraw_consent(
                patient_id="PAT-001",
                category=ConsentCategory.BIOBANK,
                reason="   ",
            )

    def test_withdraw_unknown_patient(self, svc: ConsentPreferencesService):
        with pytest.raises(KeyError, match="not found"):
            svc.withdraw_consent(
                patient_id="PAT-GHOST",
                category=ConsentCategory.BIOBANK,
                reason="test",
            )

    def test_withdraw_creates_audit_entry(self, svc: ConsentPreferencesService):
        svc.withdraw_consent(
            patient_id="PAT-001",
            category=ConsentCategory.BIOBANK,
            reason="Personal preference",
        )
        trail = svc.get_audit_trail("PAT-001", category=ConsentCategory.BIOBANK)
        latest = trail[0]
        assert latest.action == ConsentAction.WITHDRAWN
        assert latest.new_status == PreferenceStatus.OPTED_OUT
        assert "Personal preference" in (latest.notes or "")

    def test_withdraw_all_consent(self, svc: ConsentPreferencesService):
        profile = svc.withdraw_all_consent(
            patient_id="PAT-001",
            reason="Leaving the trial program",
        )
        assert profile.overall_consent_status == OverallConsentStatus.WITHDRAWN
        for pref in profile.preferences:
            assert pref.status == PreferenceStatus.OPTED_OUT

    def test_withdraw_all_requires_reason(self, svc: ConsentPreferencesService):
        with pytest.raises(ValueError, match="required"):
            svc.withdraw_all_consent(patient_id="PAT-001", reason="")

    def test_withdraw_all_unknown_patient(self, svc: ConsentPreferencesService):
        with pytest.raises(KeyError, match="not found"):
            svc.withdraw_all_consent(patient_id="PAT-GHOST", reason="test")

    def test_withdraw_updates_profile_status(self, svc: ConsentPreferencesService):
        assert svc.get_profile("PAT-001").overall_consent_status == OverallConsentStatus.FULL
        svc.withdraw_consent(
            patient_id="PAT-001",
            category=ConsentCategory.ANALYTICS,
            reason="privacy concern",
        )
        assert svc.get_profile("PAT-001").overall_consent_status == OverallConsentStatus.PARTIAL


# ===========================================================================
# 6. Audit Trail
# ===========================================================================


class TestAuditTrail:
    """Tests for get_audit_trail."""

    def test_audit_trail_exists_for_seed(self, svc: ConsentPreferencesService):
        trail = svc.get_audit_trail("PAT-001")
        assert len(trail) > 0

    def test_audit_trail_ordered_most_recent_first(self, svc: ConsentPreferencesService):
        # Make an update so we have a fresh entry
        svc.update_preference(
            patient_id="PAT-001",
            category=ConsentCategory.ANALYTICS,
            status=PreferenceStatus.OPTED_OUT,
            grantor="patient",
        )
        trail = svc.get_audit_trail("PAT-001")
        for i in range(len(trail) - 1):
            assert trail[i].timestamp >= trail[i + 1].timestamp

    def test_audit_trail_filter_by_category(self, svc: ConsentPreferencesService):
        trail = svc.get_audit_trail("PAT-001", category=ConsentCategory.TRIAL_SCREENING)
        for entry in trail:
            assert entry.category == ConsentCategory.TRIAL_SCREENING

    def test_audit_trail_limit(self, svc: ConsentPreferencesService):
        trail = svc.get_audit_trail("PAT-001", limit=2)
        assert len(trail) <= 2

    def test_audit_trail_empty_for_unknown_patient(self, svc: ConsentPreferencesService):
        trail = svc.get_audit_trail("PAT-UNKNOWN")
        assert trail == []

    def test_audit_entry_has_required_fields(self, svc: ConsentPreferencesService):
        trail = svc.get_audit_trail("PAT-001")
        entry = trail[0]
        assert entry.id is not None
        assert entry.patient_id == "PAT-001"
        assert entry.category is not None
        assert entry.action is not None
        assert entry.new_status is not None
        assert entry.performed_by is not None
        assert entry.timestamp is not None


# ===========================================================================
# 7. Consent Checks
# ===========================================================================


class TestConsentCheck:
    """Tests for check_consent."""

    def test_check_opted_in(self, svc: ConsentPreferencesService):
        result = svc.check_consent("PAT-001", ConsentCategory.TRIAL_SCREENING)
        assert result.is_consented is True
        assert result.status == PreferenceStatus.OPTED_IN

    def test_check_opted_out(self, svc: ConsentPreferencesService):
        result = svc.check_consent("PAT-006", ConsentCategory.TRIAL_SCREENING)
        assert result.is_consented is False
        assert result.status == PreferenceStatus.OPTED_OUT

    def test_check_not_set(self, svc: ConsentPreferencesService):
        result = svc.check_consent("PAT-008", ConsentCategory.TRIAL_SCREENING)
        assert result.is_consented is False
        assert result.status == PreferenceStatus.NOT_SET

    def test_check_unknown_patient(self, svc: ConsentPreferencesService):
        result = svc.check_consent("PAT-UNKNOWN", ConsentCategory.TRIAL_SCREENING)
        assert result.is_consented is False
        assert result.status == PreferenceStatus.NOT_SET

    def test_check_with_channel_enabled(self, svc: ConsentPreferencesService):
        result = svc.check_consent("PAT-001", ConsentCategory.TRIAL_SCREENING, channel="EMAIL")
        assert result.is_consented is True
        assert result.channel == "EMAIL"

    def test_check_with_channel_disabled(self, svc: ConsentPreferencesService):
        result = svc.check_consent("PAT-001", ConsentCategory.TRIAL_SCREENING, channel="SMS")
        assert result.is_consented is False
        assert result.channel == "SMS"

    def test_check_with_channel_not_set(self, svc: ConsentPreferencesService):
        result = svc.check_consent("PAT-001", ConsentCategory.TRIAL_SCREENING, channel="FAX")
        assert result.is_consented is False


# ===========================================================================
# 8. Expiring Consents
# ===========================================================================


class TestExpiringConsents:
    """Tests for get_expiring_consents."""

    def test_expiring_within_30_days(self, svc: ConsentPreferencesService):
        items = svc.get_expiring_consents(days_ahead=30)
        assert len(items) > 0

    def test_expiring_sorted_by_days(self, svc: ConsentPreferencesService):
        items = svc.get_expiring_consents(days_ahead=30)
        for i in range(len(items) - 1):
            assert items[i].days_until_expiry <= items[i + 1].days_until_expiry

    def test_expiring_within_3_days(self, svc: ConsentPreferencesService):
        items = svc.get_expiring_consents(days_ahead=3)
        for item in items:
            assert item.days_until_expiry <= 3

    def test_expiring_has_patient_id(self, svc: ConsentPreferencesService):
        items = svc.get_expiring_consents(days_ahead=30)
        for item in items:
            assert item.patient_id is not None
            assert item.category is not None
            assert item.expires_at is not None


# ===========================================================================
# 9. Template Management
# ===========================================================================


class TestTemplateManagement:
    """Tests for template CRUD and application."""

    def test_list_templates(self, svc: ConsentPreferencesService):
        templates = svc.get_templates()
        assert len(templates) == 2

    def test_get_template_standard(self, svc: ConsentPreferencesService):
        tmpl = svc.get_template("tmpl-standard")
        assert tmpl.id == "tmpl-standard"
        assert ConsentCategory.TRIAL_SCREENING in tmpl.categories

    def test_get_template_not_found(self, svc: ConsentPreferencesService):
        with pytest.raises(KeyError, match="not found"):
            svc.get_template("tmpl-nonexistent")

    def test_apply_template_to_new_patient(self, svc: ConsentPreferencesService):
        profile = svc.apply_template(
            patient_id="PAT-TEMPLATE-NEW",
            template_id="tmpl-standard",
            grantor="coordinator",
        )
        assert profile.patient_id == "PAT-TEMPLATE-NEW"
        statuses = {p.category: p.status for p in profile.preferences}
        for cat in svc.get_template("tmpl-standard").categories:
            assert statuses[cat] == PreferenceStatus.OPTED_IN

    def test_apply_template_creates_audit_trail(self, svc: ConsentPreferencesService):
        svc.apply_template(
            patient_id="PAT-TEMPLATE-AUDIT",
            template_id="tmpl-standard",
            grantor="coordinator",
        )
        trail = svc.get_audit_trail("PAT-TEMPLATE-AUDIT")
        assert len(trail) == 4  # 4 categories in standard template

    def test_apply_template_not_found(self, svc: ConsentPreferencesService):
        with pytest.raises(KeyError, match="not found"):
            svc.apply_template(
                patient_id="PAT-001",
                template_id="tmpl-nonexistent",
                grantor="coordinator",
            )

    def test_apply_enhanced_template(self, svc: ConsentPreferencesService):
        profile = svc.apply_template(
            patient_id="PAT-ENHANCED",
            template_id="tmpl-enhanced",
            grantor="coordinator",
        )
        statuses = {p.category: p.status for p in profile.preferences}
        assert statuses[ConsentCategory.BIOBANK] == PreferenceStatus.OPTED_IN
        assert statuses[ConsentCategory.GENETIC_ANALYSIS] == PreferenceStatus.OPTED_IN


# ===========================================================================
# 10. Consent Export
# ===========================================================================


class TestConsentExport:
    """Tests for export_consent_record."""

    def test_export_existing_patient(self, svc: ConsentPreferencesService):
        export = svc.export_consent_record("PAT-001")
        assert export.patient_id == "PAT-001"
        assert export.profile is not None
        assert export.audit_trail is not None
        assert export.exported_at is not None
        assert export.export_format == "JSON"

    def test_export_includes_full_profile(self, svc: ConsentPreferencesService):
        export = svc.export_consent_record("PAT-001")
        assert len(export.profile.preferences) == 8

    def test_export_includes_audit_trail(self, svc: ConsentPreferencesService):
        export = svc.export_consent_record("PAT-001")
        assert len(export.audit_trail) > 0

    def test_export_unknown_patient(self, svc: ConsentPreferencesService):
        with pytest.raises(KeyError, match="not found"):
            svc.export_consent_record("PAT-GHOST")


# ===========================================================================
# 11. Program Metrics
# ===========================================================================


class TestMetrics:
    """Tests for get_metrics."""

    def test_metrics_total_patients(self, svc: ConsentPreferencesService):
        metrics = svc.get_metrics()
        assert metrics.total_patients == 12

    def test_metrics_percentages_sum(self, svc: ConsentPreferencesService):
        metrics = svc.get_metrics()
        total_pct = (
            metrics.fully_consented_pct
            + metrics.partially_consented_pct
            + metrics.withdrawn_pct
            + metrics.pending_pct
        )
        assert abs(total_pct - 100.0) < 0.5  # allow rounding tolerance

    def test_metrics_by_category_has_all_categories(self, svc: ConsentPreferencesService):
        metrics = svc.get_metrics()
        for cat in ConsentCategory:
            assert cat.value in metrics.by_category

    def test_metrics_category_counts_sum(self, svc: ConsentPreferencesService):
        metrics = svc.get_metrics()
        for cat_name, cat_metrics in metrics.by_category.items():
            total = cat_metrics.opted_in + cat_metrics.opted_out + cat_metrics.not_set
            assert total == 12  # all 12 patients

    def test_metrics_avg_categories_consented(self, svc: ConsentPreferencesService):
        metrics = svc.get_metrics()
        assert metrics.avg_categories_consented >= 0
        assert metrics.avg_categories_consented <= len(ConsentCategory)

    def test_metrics_consent_rate_trend(self, svc: ConsentPreferencesService):
        metrics = svc.get_metrics()
        assert len(metrics.consent_rate_trend) == 6

    def test_metrics_withdrawal_rate(self, svc: ConsentPreferencesService):
        metrics = svc.get_metrics()
        assert metrics.withdrawal_rate_30d >= 0


# ===========================================================================
# 12. Edge Cases
# ===========================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_update_same_preference_twice(self, svc: ConsentPreferencesService):
        svc.update_preference(
            patient_id="PAT-001",
            category=ConsentCategory.ANALYTICS,
            status=PreferenceStatus.OPTED_OUT,
            grantor="patient",
        )
        pref = svc.update_preference(
            patient_id="PAT-001",
            category=ConsentCategory.ANALYTICS,
            status=PreferenceStatus.OPTED_IN,
            grantor="patient",
        )
        assert pref.status == PreferenceStatus.OPTED_IN

    def test_withdraw_already_opted_out(self, svc: ConsentPreferencesService):
        svc.withdraw_consent(
            patient_id="PAT-001",
            category=ConsentCategory.ANALYTICS,
            reason="first withdrawal",
        )
        pref = svc.withdraw_consent(
            patient_id="PAT-001",
            category=ConsentCategory.ANALYTICS,
            reason="second withdrawal",
        )
        assert pref.status == PreferenceStatus.OPTED_OUT

    def test_profile_completeness_after_updates(self, svc: ConsentPreferencesService):
        # PAT-008 starts with all NOT_SET (0% completeness)
        p = svc.get_profile("PAT-008")
        assert p.profile_completeness_pct == 0.0

        # Opt in to one category
        svc.update_preference(
            patient_id="PAT-008",
            category=ConsentCategory.TRIAL_SCREENING,
            status=PreferenceStatus.OPTED_IN,
            grantor="coordinator",
        )
        p = svc.get_profile("PAT-008")
        assert p.profile_completeness_pct > 0.0

    def test_clear_and_reseed(self, svc: ConsentPreferencesService):
        svc.clear()
        profiles, total = svc.list_profiles()
        assert total == 12  # re-seeded


# ===========================================================================
# 13. API Endpoint Integration Tests
# ===========================================================================


@pytest.mark.anyio
class TestAPIEndpoints:
    """Integration tests for the consent preferences API."""

    async def test_list_profiles(self, svc: ConsentPreferencesService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/profiles")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 12
            assert len(data["profiles"]) == 12

    async def test_list_profiles_with_status_filter(self, svc: ConsentPreferencesService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/profiles", params={"status": "FULL"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 2

    async def test_list_profiles_pagination(self, svc: ConsentPreferencesService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/profiles", params={"limit": 3, "offset": 0})
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["profiles"]) == 3
            assert data["total"] == 12

    async def test_get_profile(self, svc: ConsentPreferencesService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/profiles/PAT-001")
            assert resp.status_code == 200
            data = resp.json()
            assert data["patient_id"] == "PAT-001"

    async def test_get_profile_not_found(self, svc: ConsentPreferencesService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/profiles/PAT-NONEXISTENT")
            assert resp.status_code == 404

    async def test_update_preference(self, svc: ConsentPreferencesService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.put(
                f"{API_PREFIX}/profiles/PAT-001/preferences",
                json={
                    "category": "ANALYTICS",
                    "status": "OPTED_OUT",
                    "grantor": "patient",
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "OPTED_OUT"

    async def test_bulk_update_preferences(self, svc: ConsentPreferencesService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.put(
                f"{API_PREFIX}/profiles/PAT-008/preferences/bulk",
                json={
                    "preferences": [
                        {"category": "TRIAL_SCREENING", "status": "OPTED_IN", "grantor": "coordinator"},
                        {"category": "DATA_SHARING", "status": "OPTED_IN", "grantor": "coordinator"},
                    ]
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["patient_id"] == "PAT-008"

    async def test_withdraw_consent(self, svc: ConsentPreferencesService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/profiles/PAT-001/withdraw/BIOBANK",
                json={"reason": "No longer interested"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "OPTED_OUT"

    async def test_withdraw_consent_not_found(self, svc: ConsentPreferencesService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/profiles/PAT-GHOST/withdraw/BIOBANK",
                json={"reason": "test"},
            )
            assert resp.status_code == 404

    async def test_withdraw_all_consent(self, svc: ConsentPreferencesService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/profiles/PAT-001/withdraw-all",
                json={"reason": "Leaving program"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["overall_consent_status"] == "WITHDRAWN"

    async def test_audit_trail(self, svc: ConsentPreferencesService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/profiles/PAT-001/audit")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) > 0

    async def test_audit_trail_by_category(self, svc: ConsentPreferencesService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/profiles/PAT-001/audit/TRIAL_SCREENING")
            assert resp.status_code == 200
            data = resp.json()
            for entry in data:
                assert entry["category"] == "TRIAL_SCREENING"

    async def test_check_consent(self, svc: ConsentPreferencesService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/check/PAT-001/TRIAL_SCREENING")
            assert resp.status_code == 200
            data = resp.json()
            assert data["is_consented"] is True

    async def test_check_consent_with_channel(self, svc: ConsentPreferencesService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/check/PAT-001/TRIAL_SCREENING/EMAIL")
            assert resp.status_code == 200
            data = resp.json()
            assert data["is_consented"] is True
            assert data["channel"] == "EMAIL"

    async def test_expiring_consents(self, svc: ConsentPreferencesService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/expiring", params={"days_ahead": 30})
            assert resp.status_code == 200
            data = resp.json()
            assert "items" in data
            assert "total" in data
            assert data["days_ahead"] == 30

    async def test_metrics(self, svc: ConsentPreferencesService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/metrics")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_patients"] == 12

    async def test_list_templates(self, svc: ConsentPreferencesService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/templates")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 2

    async def test_get_template(self, svc: ConsentPreferencesService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/templates/tmpl-standard")
            assert resp.status_code == 200
            data = resp.json()
            assert data["name"] == "Standard Clinical Trial"

    async def test_get_template_not_found(self, svc: ConsentPreferencesService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/templates/tmpl-fake")
            assert resp.status_code == 404

    async def test_apply_template(self, svc: ConsentPreferencesService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/profiles/PAT-API-TMPL/apply-template",
                json={
                    "template_id": "tmpl-standard",
                    "grantor": "coordinator",
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["patient_id"] == "PAT-API-TMPL"

    async def test_apply_template_not_found(self, svc: ConsentPreferencesService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/profiles/PAT-001/apply-template",
                json={
                    "template_id": "tmpl-nonexistent",
                    "grantor": "coordinator",
                },
            )
            assert resp.status_code == 404

    async def test_export_consent_record(self, svc: ConsentPreferencesService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/profiles/PAT-001/export")
            assert resp.status_code == 200
            data = resp.json()
            assert data["patient_id"] == "PAT-001"
            assert data["profile"] is not None
            assert data["audit_trail"] is not None
            assert data["exported_at"] is not None

    async def test_export_not_found(self, svc: ConsentPreferencesService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/profiles/PAT-GHOST/export")
            assert resp.status_code == 404
