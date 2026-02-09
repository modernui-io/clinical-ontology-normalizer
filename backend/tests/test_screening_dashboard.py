"""Tests for Patient Screening Dashboard (VP-Product-8).

Covers:
- Seed data verification
- Saved search CRUD (create, read, update, delete)
- Screening session execution
- Dashboard summary
- Screening metrics
- Screening history
- Session details and export
- Saved search execution
- Filtering and pagination
- Error handling (404, 400)
- API endpoint integration
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.screening_dashboard import (
    FilterOperator,
    SavedSearchCreate,
    SavedSearchFilters,
    SavedSearchUpdate,
    ScreeningFilter,
    ScreeningStatus,
)
from app.services.screening_dashboard_service import (
    ScreeningDashboardService,
    get_screening_dashboard_service,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

API_PREFIX = "/screening-dashboard"


@pytest.fixture(autouse=True)
def clean_service():
    """Ensure a fresh service for every test (with seed data)."""
    svc = get_screening_dashboard_service()
    svc.clear()
    yield svc
    svc.clear()


@pytest.fixture
def svc(clean_service) -> ScreeningDashboardService:
    """Shorthand for the clean service."""
    return clean_service


@pytest.fixture
async def api_client():
    """Async client for API tests (no DB needed -- service is in-memory)."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test/api/v1",
    ) as ac:
        yield ac


# ===========================================================================
# 1. Seed Data Verification
# ===========================================================================


class TestSeedData:
    """Verify pre-populated data is present after clear() (re-populate)."""

    def test_seed_saved_searches_count(self, svc: ScreeningDashboardService):
        searches = svc.list_saved_searches()
        assert len(searches) == 5

    def test_seed_saved_search_names(self, svc: ScreeningDashboardService):
        names = {s.name for s in svc.list_saved_searches()}
        assert "EYLEA DME Candidates" in names
        assert "Dupixent AD Candidates" in names
        assert "Libtayo CSCC Candidates" in names
        assert "High-Risk Diabetics" in names
        assert "Young Adults with Skin Conditions" in names

    def test_seed_sessions_count(self, svc: ScreeningDashboardService):
        history = svc.get_screening_history(limit=100)
        assert len(history) == 3

    def test_seed_sessions_have_results(self, svc: ScreeningDashboardService):
        history = svc.get_screening_history(limit=100)
        for h in history:
            session = svc.get_session(h.id)
            assert session is not None
            assert session.total_screened > 0

    def test_seed_stats(self, svc: ScreeningDashboardService):
        stats = svc.get_stats()
        assert stats["saved_searches"] == 5
        assert stats["sessions"] == 3
        assert stats["demo_patients"] == 12
        assert stats["trial_criteria"] == 3

    def test_seed_search_has_filters(self, svc: ScreeningDashboardService):
        searches = svc.list_saved_searches()
        eylea = next(s for s in searches if s.name == "EYLEA DME Candidates")
        assert eylea.filters.trial_id == "TRIAL-EYLEA-DME"
        assert "Diabetic Macular Edema" in eylea.filters.conditions

    def test_seed_search_created_by(self, svc: ScreeningDashboardService):
        searches = svc.list_saved_searches()
        diabetics = next(s for s in searches if s.name == "High-Risk Diabetics")
        assert diabetics.created_by == "dr.smith"

    def test_seed_session_trial_ids(self, svc: ScreeningDashboardService):
        history = svc.get_screening_history(limit=100)
        trial_ids = {h.trial_id for h in history}
        assert "TRIAL-EYLEA-DME" in trial_ids
        assert "TRIAL-DUPIXENT-AD" in trial_ids
        assert "TRIAL-LIBTAYO-CSCC" in trial_ids


# ===========================================================================
# 2. Saved Search CRUD
# ===========================================================================


class TestSavedSearchCRUD:
    """Tests for saved search create, read, update, delete."""

    def test_create_saved_search(self, svc: ScreeningDashboardService):
        create = SavedSearchCreate(
            name="Test Search",
            description="A test search",
            created_by="tester",
            filters=SavedSearchFilters(
                conditions=["Diabetes"],
                age_range={"min": 30, "max": 70},
            ),
        )
        result = svc.create_saved_search(create)
        assert result.name == "Test Search"
        assert result.description == "A test search"
        assert result.created_by == "tester"
        assert result.id

    def test_create_increments_count(self, svc: ScreeningDashboardService):
        initial = len(svc.list_saved_searches())
        svc.create_saved_search(SavedSearchCreate(
            name="New",
            filters=SavedSearchFilters(conditions=["X"]),
        ))
        assert len(svc.list_saved_searches()) == initial + 1

    def test_get_saved_search_by_id(self, svc: ScreeningDashboardService):
        searches = svc.list_saved_searches()
        search = svc.get_saved_search(searches[0].id)
        assert search is not None
        assert search.id == searches[0].id

    def test_get_nonexistent_search(self, svc: ScreeningDashboardService):
        result = svc.get_saved_search("nonexistent-id")
        assert result is None

    def test_update_saved_search_name(self, svc: ScreeningDashboardService):
        searches = svc.list_saved_searches()
        updated = svc.update_saved_search(
            searches[0].id,
            SavedSearchUpdate(name="Updated Name"),
        )
        assert updated is not None
        assert updated.name == "Updated Name"

    def test_update_saved_search_description(self, svc: ScreeningDashboardService):
        searches = svc.list_saved_searches()
        updated = svc.update_saved_search(
            searches[0].id,
            SavedSearchUpdate(description="New description"),
        )
        assert updated is not None
        assert updated.description == "New description"

    def test_update_saved_search_filters(self, svc: ScreeningDashboardService):
        searches = svc.list_saved_searches()
        new_filters = SavedSearchFilters(
            conditions=["Hypertension"],
            age_range={"min": 40, "max": 80},
        )
        updated = svc.update_saved_search(
            searches[0].id,
            SavedSearchUpdate(filters=new_filters),
        )
        assert updated is not None
        assert "Hypertension" in updated.filters.conditions

    def test_update_nonexistent_search(self, svc: ScreeningDashboardService):
        result = svc.update_saved_search(
            "bad-id",
            SavedSearchUpdate(name="Nope"),
        )
        assert result is None

    def test_update_preserves_unchanged_fields(self, svc: ScreeningDashboardService):
        searches = svc.list_saved_searches()
        original = searches[0]
        updated = svc.update_saved_search(
            original.id,
            SavedSearchUpdate(name="Changed Name Only"),
        )
        assert updated is not None
        assert updated.description == original.description
        assert updated.filters == original.filters

    def test_update_changes_updated_at(self, svc: ScreeningDashboardService):
        searches = svc.list_saved_searches()
        original = searches[0]
        updated = svc.update_saved_search(
            original.id,
            SavedSearchUpdate(name="Triggers Timestamp"),
        )
        assert updated is not None
        assert updated.updated_at >= original.updated_at

    def test_delete_saved_search(self, svc: ScreeningDashboardService):
        searches = svc.list_saved_searches()
        count_before = len(searches)
        deleted = svc.delete_saved_search(searches[0].id)
        assert deleted is True
        assert len(svc.list_saved_searches()) == count_before - 1

    def test_delete_nonexistent_search(self, svc: ScreeningDashboardService):
        result = svc.delete_saved_search("bad-id")
        assert result is False

    def test_delete_same_search_twice(self, svc: ScreeningDashboardService):
        searches = svc.list_saved_searches()
        sid = searches[0].id
        assert svc.delete_saved_search(sid) is True
        assert svc.delete_saved_search(sid) is False

    def test_create_search_minimal_fields(self, svc: ScreeningDashboardService):
        create = SavedSearchCreate(
            name="Minimal",
            filters=SavedSearchFilters(),
        )
        result = svc.create_saved_search(create)
        assert result.name == "Minimal"
        assert result.created_by == "system"
        assert result.filters.conditions == []


# ===========================================================================
# 3. Run Screening
# ===========================================================================


class TestRunScreening:
    """Tests for run_screening."""

    def test_run_screening_eylea(self, svc: ScreeningDashboardService):
        from app.schemas.screening_dashboard import RunScreeningRequest
        request = RunScreeningRequest(trial_id="TRIAL-EYLEA-DME")
        session = svc.run_screening(request)
        assert session.trial_id == "TRIAL-EYLEA-DME"
        assert session.total_screened == 12
        assert session.total_eligible >= 0
        assert session.total_ineligible >= 0

    def test_run_screening_dupixent(self, svc: ScreeningDashboardService):
        from app.schemas.screening_dashboard import RunScreeningRequest
        request = RunScreeningRequest(trial_id="TRIAL-DUPIXENT-AD")
        session = svc.run_screening(request)
        assert session.trial_id == "TRIAL-DUPIXENT-AD"
        assert session.total_screened == 12

    def test_run_screening_libtayo(self, svc: ScreeningDashboardService):
        from app.schemas.screening_dashboard import RunScreeningRequest
        request = RunScreeningRequest(trial_id="TRIAL-LIBTAYO-CSCC")
        session = svc.run_screening(request)
        assert session.trial_id == "TRIAL-LIBTAYO-CSCC"
        assert session.total_screened == 12

    def test_run_screening_unknown_trial(self, svc: ScreeningDashboardService):
        from app.schemas.screening_dashboard import RunScreeningRequest
        request = RunScreeningRequest(trial_id="UNKNOWN-TRIAL")
        session = svc.run_screening(request)
        assert session.total_screened == 0

    def test_run_screening_adds_session(self, svc: ScreeningDashboardService):
        from app.schemas.screening_dashboard import RunScreeningRequest
        initial_count = len(svc.get_screening_history(limit=100))
        svc.run_screening(RunScreeningRequest(trial_id="TRIAL-EYLEA-DME"))
        assert len(svc.get_screening_history(limit=100)) == initial_count + 1

    def test_run_screening_with_filters(self, svc: ScreeningDashboardService):
        from app.schemas.screening_dashboard import RunScreeningRequest
        request = RunScreeningRequest(
            trial_id="TRIAL-EYLEA-DME",
            filters=[
                ScreeningFilter(field="age", operator=FilterOperator.GTE, value=60),
            ],
        )
        session = svc.run_screening(request)
        # Only patients age >= 60 should be screened
        assert session.total_screened < 12

    def test_run_screening_result_statuses(self, svc: ScreeningDashboardService):
        from app.schemas.screening_dashboard import RunScreeningRequest
        session = svc.run_screening(RunScreeningRequest(trial_id="TRIAL-EYLEA-DME"))
        statuses = {r.status for r in session.results}
        # Should have at least some eligible and some ineligible
        assert len(statuses) > 0

    def test_run_screening_results_have_patient_info(self, svc: ScreeningDashboardService):
        from app.schemas.screening_dashboard import RunScreeningRequest
        session = svc.run_screening(RunScreeningRequest(trial_id="TRIAL-EYLEA-DME"))
        for r in session.results:
            assert r.patient_id
            assert r.patient_name
            assert r.age > 0
            assert r.gender in ("Male", "Female")

    def test_run_screening_match_score_range(self, svc: ScreeningDashboardService):
        from app.schemas.screening_dashboard import RunScreeningRequest
        session = svc.run_screening(RunScreeningRequest(trial_id="TRIAL-EYLEA-DME"))
        for r in session.results:
            assert 0.0 <= r.match_score <= 1.0

    def test_run_screening_session_timestamps(self, svc: ScreeningDashboardService):
        from app.schemas.screening_dashboard import RunScreeningRequest
        session = svc.run_screening(RunScreeningRequest(trial_id="TRIAL-EYLEA-DME"))
        assert session.started_at is not None
        assert session.completed_at is not None
        assert session.completed_at >= session.started_at


# ===========================================================================
# 4. Dashboard Summary
# ===========================================================================


class TestDashboardSummary:
    """Tests for get_dashboard_summary."""

    def test_summary_active_trials(self, svc: ScreeningDashboardService):
        summary = svc.get_dashboard_summary()
        assert summary.active_trials == 3

    def test_summary_total_patients(self, svc: ScreeningDashboardService):
        summary = svc.get_dashboard_summary()
        assert summary.total_patients == 12

    def test_summary_screening_rate_trend(self, svc: ScreeningDashboardService):
        summary = svc.get_dashboard_summary()
        assert len(summary.screening_rate_trend) == 7

    def test_summary_trend_has_dates(self, svc: ScreeningDashboardService):
        summary = svc.get_dashboard_summary()
        for item in summary.screening_rate_trend:
            assert "date" in item
            assert "count" in item

    def test_summary_top_matching_trials(self, svc: ScreeningDashboardService):
        summary = svc.get_dashboard_summary()
        assert len(summary.top_matching_trials) > 0

    def test_summary_top_trial_fields(self, svc: ScreeningDashboardService):
        summary = svc.get_dashboard_summary()
        for trial in summary.top_matching_trials:
            assert trial.trial_id
            assert trial.trial_name
            assert trial.eligible_count >= 0


# ===========================================================================
# 5. Screening Metrics
# ===========================================================================


class TestScreeningMetrics:
    """Tests for get_screening_metrics."""

    def test_metrics_total_sessions(self, svc: ScreeningDashboardService):
        metrics = svc.get_screening_metrics()
        assert metrics.total_sessions == 3

    def test_metrics_avg_patients(self, svc: ScreeningDashboardService):
        metrics = svc.get_screening_metrics()
        assert metrics.avg_patients_per_session > 0

    def test_metrics_avg_match_score(self, svc: ScreeningDashboardService):
        metrics = svc.get_screening_metrics()
        assert 0.0 <= metrics.avg_match_score <= 1.0

    def test_metrics_exclusion_reasons(self, svc: ScreeningDashboardService):
        metrics = svc.get_screening_metrics()
        assert len(metrics.most_common_exclusion_reasons) > 0

    def test_metrics_exclusion_reasons_have_counts(self, svc: ScreeningDashboardService):
        metrics = svc.get_screening_metrics()
        for reason in metrics.most_common_exclusion_reasons:
            assert reason.reason
            assert reason.count > 0

    def test_metrics_volume_by_day(self, svc: ScreeningDashboardService):
        metrics = svc.get_screening_metrics()
        assert len(metrics.screening_volume_by_day) >= 1

    def test_metrics_volume_day_fields(self, svc: ScreeningDashboardService):
        metrics = svc.get_screening_metrics()
        for vol in metrics.screening_volume_by_day:
            assert vol.date
            assert vol.sessions >= 0
            assert vol.patients_screened >= 0

    def test_metrics_empty_service(self, svc: ScreeningDashboardService):
        svc.clear_all()
        metrics = svc.get_screening_metrics()
        assert metrics.total_sessions == 0
        assert metrics.avg_patients_per_session == 0.0
        assert metrics.avg_match_score == 0.0


# ===========================================================================
# 6. Screening History
# ===========================================================================


class TestScreeningHistory:
    """Tests for get_screening_history."""

    def test_history_returns_sessions(self, svc: ScreeningDashboardService):
        history = svc.get_screening_history()
        assert len(history) == 3

    def test_history_sorted_by_recency(self, svc: ScreeningDashboardService):
        history = svc.get_screening_history()
        for i in range(len(history) - 1):
            assert history[i].started_at >= history[i + 1].started_at

    def test_history_limit(self, svc: ScreeningDashboardService):
        history = svc.get_screening_history(limit=1)
        assert len(history) == 1

    def test_history_limit_larger_than_count(self, svc: ScreeningDashboardService):
        history = svc.get_screening_history(limit=100)
        assert len(history) == 3

    def test_history_item_fields(self, svc: ScreeningDashboardService):
        history = svc.get_screening_history()
        for h in history:
            assert h.id
            assert h.trial_id
            assert h.total_screened >= 0
            assert h.started_at is not None


# ===========================================================================
# 7. Session Details & Export
# ===========================================================================


class TestSessionDetailsAndExport:
    """Tests for get_session and export_results."""

    def test_get_session_by_id(self, svc: ScreeningDashboardService):
        history = svc.get_screening_history()
        session = svc.get_session(history[0].id)
        assert session is not None
        assert session.id == history[0].id

    def test_get_nonexistent_session(self, svc: ScreeningDashboardService):
        assert svc.get_session("bad-id") is None

    def test_session_has_results(self, svc: ScreeningDashboardService):
        history = svc.get_screening_history()
        session = svc.get_session(history[0].id)
        assert session is not None
        assert len(session.results) > 0

    def test_export_json(self, svc: ScreeningDashboardService):
        history = svc.get_screening_history()
        export = svc.export_results(history[0].id, fmt="json")
        assert export is not None
        assert export.format == "json"
        assert export.row_count > 0
        assert len(export.columns) > 0
        assert len(export.data) == export.row_count

    def test_export_csv(self, svc: ScreeningDashboardService):
        history = svc.get_screening_history()
        export = svc.export_results(history[0].id, fmt="csv")
        assert export is not None
        assert export.format == "csv"
        # CSV format joins lists with "; "
        for row in export.data:
            if row.get("matched_criteria"):
                assert isinstance(row["matched_criteria"], str)

    def test_export_json_lists(self, svc: ScreeningDashboardService):
        history = svc.get_screening_history()
        export = svc.export_results(history[0].id, fmt="json")
        assert export is not None
        for row in export.data:
            if row.get("matched_criteria"):
                assert isinstance(row["matched_criteria"], list)

    def test_export_nonexistent_session(self, svc: ScreeningDashboardService):
        assert svc.export_results("bad-id") is None

    def test_export_columns(self, svc: ScreeningDashboardService):
        history = svc.get_screening_history()
        export = svc.export_results(history[0].id)
        assert export is not None
        expected_cols = [
            "patient_id", "patient_name", "age", "gender",
            "match_score", "status", "matched_criteria",
        ]
        for col in expected_cols:
            assert col in export.columns

    def test_export_session_id_matches(self, svc: ScreeningDashboardService):
        history = svc.get_screening_history()
        export = svc.export_results(history[0].id)
        assert export is not None
        assert export.session_id == history[0].id


# ===========================================================================
# 8. Execute Saved Search
# ===========================================================================


class TestExecuteSavedSearch:
    """Tests for execute_saved_search."""

    def test_execute_trial_based_search(self, svc: ScreeningDashboardService):
        searches = svc.list_saved_searches()
        eylea = next(s for s in searches if s.name == "EYLEA DME Candidates")
        session = svc.execute_saved_search(eylea.id)
        assert session is not None
        assert session.trial_id == "TRIAL-EYLEA-DME"
        assert session.total_screened > 0

    def test_execute_updates_last_run(self, svc: ScreeningDashboardService):
        searches = svc.list_saved_searches()
        eylea = next(s for s in searches if s.name == "EYLEA DME Candidates")
        assert eylea.last_run is None
        svc.execute_saved_search(eylea.id)
        updated = svc.get_saved_search(eylea.id)
        assert updated is not None
        assert updated.last_run is not None

    def test_execute_updates_patient_count(self, svc: ScreeningDashboardService):
        searches = svc.list_saved_searches()
        eylea = next(s for s in searches if s.name == "EYLEA DME Candidates")
        svc.execute_saved_search(eylea.id)
        updated = svc.get_saved_search(eylea.id)
        assert updated is not None
        assert updated.patient_count >= 0

    def test_execute_adds_session(self, svc: ScreeningDashboardService):
        initial = len(svc.get_screening_history(limit=100))
        searches = svc.list_saved_searches()
        svc.execute_saved_search(searches[0].id)
        assert len(svc.get_screening_history(limit=100)) == initial + 1

    def test_execute_nonexistent_search(self, svc: ScreeningDashboardService):
        result = svc.execute_saved_search("bad-id")
        assert result is None

    def test_execute_custom_search_no_trial(self, svc: ScreeningDashboardService):
        searches = svc.list_saved_searches()
        diabetics = next(s for s in searches if s.name == "High-Risk Diabetics")
        session = svc.execute_saved_search(diabetics.id)
        assert session is not None
        assert session.trial_id == "CUSTOM"
        assert session.total_screened > 0

    def test_execute_dupixent_search(self, svc: ScreeningDashboardService):
        searches = svc.list_saved_searches()
        dupixent = next(s for s in searches if s.name == "Dupixent AD Candidates")
        session = svc.execute_saved_search(dupixent.id)
        assert session is not None
        assert session.trial_id == "TRIAL-DUPIXENT-AD"

    def test_execute_young_adults_search(self, svc: ScreeningDashboardService):
        searches = svc.list_saved_searches()
        young = next(s for s in searches if s.name == "Young Adults with Skin Conditions")
        session = svc.execute_saved_search(young.id)
        assert session is not None
        # This is a custom search (no trial_id), results should only include young patients
        for r in session.results:
            assert r.age <= 35


# ===========================================================================
# 9. Filter Logic
# ===========================================================================


class TestFilterLogic:
    """Tests for patient filtering with ScreeningFilter."""

    def test_filter_age_gte(self, svc: ScreeningDashboardService):
        from app.schemas.screening_dashboard import RunScreeningRequest
        session = svc.run_screening(RunScreeningRequest(
            trial_id="TRIAL-EYLEA-DME",
            filters=[ScreeningFilter(field="age", operator=FilterOperator.GTE, value=60)],
        ))
        for r in session.results:
            assert r.age >= 60

    def test_filter_age_lte(self, svc: ScreeningDashboardService):
        from app.schemas.screening_dashboard import RunScreeningRequest
        session = svc.run_screening(RunScreeningRequest(
            trial_id="TRIAL-EYLEA-DME",
            filters=[ScreeningFilter(field="age", operator=FilterOperator.LTE, value=50)],
        ))
        for r in session.results:
            assert r.age <= 50

    def test_filter_gender_eq(self, svc: ScreeningDashboardService):
        from app.schemas.screening_dashboard import RunScreeningRequest
        session = svc.run_screening(RunScreeningRequest(
            trial_id="TRIAL-EYLEA-DME",
            filters=[ScreeningFilter(field="gender", operator=FilterOperator.EQ, value="Female")],
        ))
        for r in session.results:
            assert r.gender == "Female"

    def test_filter_condition_contains(self, svc: ScreeningDashboardService):
        from app.schemas.screening_dashboard import RunScreeningRequest
        session = svc.run_screening(RunScreeningRequest(
            trial_id="TRIAL-EYLEA-DME",
            filters=[ScreeningFilter(field="condition", operator=FilterOperator.CONTAINS, value="Diabetes")],
        ))
        for r in session.results:
            assert any("diabetes" in c.lower() for c in r.primary_conditions)

    def test_filter_age_between(self, svc: ScreeningDashboardService):
        from app.schemas.screening_dashboard import RunScreeningRequest
        session = svc.run_screening(RunScreeningRequest(
            trial_id="TRIAL-EYLEA-DME",
            filters=[ScreeningFilter(field="age", operator=FilterOperator.BETWEEN, values=[50, 65])],
        ))
        for r in session.results:
            assert 50 <= r.age <= 65

    def test_filter_multiple_combined(self, svc: ScreeningDashboardService):
        from app.schemas.screening_dashboard import RunScreeningRequest
        session = svc.run_screening(RunScreeningRequest(
            trial_id="TRIAL-EYLEA-DME",
            filters=[
                ScreeningFilter(field="age", operator=FilterOperator.GTE, value=55),
                ScreeningFilter(field="gender", operator=FilterOperator.EQ, value="Male"),
            ],
        ))
        for r in session.results:
            assert r.age >= 55
            assert r.gender == "Male"


# ===========================================================================
# 10. Service Utility Methods
# ===========================================================================


class TestUtilityMethods:
    """Tests for get_stats, clear, clear_all."""

    def test_stats_keys(self, svc: ScreeningDashboardService):
        stats = svc.get_stats()
        assert "saved_searches" in stats
        assert "sessions" in stats
        assert "demo_patients" in stats
        assert "trial_criteria" in stats

    def test_clear_repopulates(self, svc: ScreeningDashboardService):
        svc.clear()
        assert len(svc.list_saved_searches()) == 5
        assert len(svc.get_screening_history(limit=100)) == 3

    def test_clear_all_empties(self, svc: ScreeningDashboardService):
        svc.clear_all()
        assert len(svc.list_saved_searches()) == 0
        assert len(svc.get_screening_history(limit=100)) == 0
        stats = svc.get_stats()
        assert stats["saved_searches"] == 0
        assert stats["sessions"] == 0


# ===========================================================================
# 11. API Endpoint Integration - Summary, Metrics, History, Stats
# ===========================================================================


@pytest.mark.anyio
async def test_api_get_summary(api_client: AsyncClient):
    resp = await api_client.get(f"{API_PREFIX}/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["active_trials"] == 3
    assert body["total_patients"] == 12
    assert "screening_rate_trend" in body
    assert "top_matching_trials" in body


@pytest.mark.anyio
async def test_api_get_metrics(api_client: AsyncClient):
    resp = await api_client.get(f"{API_PREFIX}/metrics")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_sessions"] == 3
    assert body["avg_patients_per_session"] > 0
    assert "most_common_exclusion_reasons" in body
    assert "screening_volume_by_day" in body


@pytest.mark.anyio
async def test_api_get_history(api_client: AsyncClient):
    resp = await api_client.get(f"{API_PREFIX}/history")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 3


@pytest.mark.anyio
async def test_api_get_history_with_limit(api_client: AsyncClient):
    resp = await api_client.get(f"{API_PREFIX}/history", params={"limit": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1


@pytest.mark.anyio
async def test_api_get_stats(api_client: AsyncClient):
    resp = await api_client.get(f"{API_PREFIX}/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["saved_searches"] == 5
    assert body["sessions"] == 3


# ===========================================================================
# 12. API Endpoint Integration - Run Screening
# ===========================================================================


@pytest.mark.anyio
async def test_api_run_screening(api_client: AsyncClient):
    resp = await api_client.post(
        f"{API_PREFIX}/run",
        json={"trial_id": "TRIAL-EYLEA-DME"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["trial_id"] == "TRIAL-EYLEA-DME"
    assert body["total_screened"] == 12
    assert len(body["results"]) > 0


@pytest.mark.anyio
async def test_api_run_screening_with_filters(api_client: AsyncClient):
    resp = await api_client.post(
        f"{API_PREFIX}/run",
        json={
            "trial_id": "TRIAL-DUPIXENT-AD",
            "filters": [
                {"field": "age", "operator": "gte", "value": 30},
            ],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    for r in body["results"]:
        assert r["age"] >= 30


@pytest.mark.anyio
async def test_api_run_screening_unknown_trial(api_client: AsyncClient):
    resp = await api_client.post(
        f"{API_PREFIX}/run",
        json={"trial_id": "UNKNOWN-TRIAL-XYZ"},
    )
    assert resp.status_code == 400
    body = resp.json()
    # Error middleware wraps in "message" field
    assert "Unknown trial_id" in body.get("message", body.get("detail", ""))


@pytest.mark.anyio
async def test_api_run_screening_with_created_by(api_client: AsyncClient):
    resp = await api_client.post(
        f"{API_PREFIX}/run",
        json={"trial_id": "TRIAL-EYLEA-DME", "created_by": "dr.test"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["created_by"] == "dr.test"


# ===========================================================================
# 13. API Endpoint Integration - Sessions
# ===========================================================================


@pytest.mark.anyio
async def test_api_get_session(api_client: AsyncClient):
    # Get a session ID from history
    history_resp = await api_client.get(f"{API_PREFIX}/history")
    sessions = history_resp.json()
    session_id = sessions[0]["id"]

    resp = await api_client.get(f"{API_PREFIX}/sessions/{session_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == session_id
    assert "results" in body


@pytest.mark.anyio
async def test_api_get_session_not_found(api_client: AsyncClient):
    resp = await api_client.get(f"{API_PREFIX}/sessions/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_api_export_json(api_client: AsyncClient):
    history_resp = await api_client.get(f"{API_PREFIX}/history")
    session_id = history_resp.json()[0]["id"]

    resp = await api_client.get(
        f"{API_PREFIX}/sessions/{session_id}/export",
        params={"format": "json"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["format"] == "json"
    assert body["row_count"] > 0
    assert body["session_id"] == session_id


@pytest.mark.anyio
async def test_api_export_csv(api_client: AsyncClient):
    history_resp = await api_client.get(f"{API_PREFIX}/history")
    session_id = history_resp.json()[0]["id"]

    resp = await api_client.get(
        f"{API_PREFIX}/sessions/{session_id}/export",
        params={"format": "csv"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["format"] == "csv"


@pytest.mark.anyio
async def test_api_export_not_found(api_client: AsyncClient):
    resp = await api_client.get(
        f"{API_PREFIX}/sessions/nonexistent-id/export",
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_api_export_invalid_format(api_client: AsyncClient):
    history_resp = await api_client.get(f"{API_PREFIX}/history")
    session_id = history_resp.json()[0]["id"]

    resp = await api_client.get(
        f"{API_PREFIX}/sessions/{session_id}/export",
        params={"format": "xml"},
    )
    assert resp.status_code == 422


# ===========================================================================
# 14. API Endpoint Integration - Saved Searches CRUD
# ===========================================================================


@pytest.mark.anyio
async def test_api_list_saved_searches(api_client: AsyncClient):
    resp = await api_client.get(f"{API_PREFIX}/saved-searches")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 5


@pytest.mark.anyio
async def test_api_create_saved_search(api_client: AsyncClient):
    resp = await api_client.post(
        f"{API_PREFIX}/saved-searches",
        json={
            "name": "API Test Search",
            "description": "Created via API",
            "filters": {
                "conditions": ["Test Condition"],
                "age_range": {"min": 20, "max": 60},
            },
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "API Test Search"
    assert body["id"]


@pytest.mark.anyio
async def test_api_create_saved_search_minimal(api_client: AsyncClient):
    resp = await api_client.post(
        f"{API_PREFIX}/saved-searches",
        json={
            "name": "Minimal Search",
            "filters": {},
        },
    )
    assert resp.status_code == 201


@pytest.mark.anyio
async def test_api_get_saved_search(api_client: AsyncClient):
    list_resp = await api_client.get(f"{API_PREFIX}/saved-searches")
    search_id = list_resp.json()[0]["id"]

    resp = await api_client.get(f"{API_PREFIX}/saved-searches/{search_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == search_id


@pytest.mark.anyio
async def test_api_get_saved_search_not_found(api_client: AsyncClient):
    resp = await api_client.get(f"{API_PREFIX}/saved-searches/nonexistent")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_api_update_saved_search(api_client: AsyncClient):
    list_resp = await api_client.get(f"{API_PREFIX}/saved-searches")
    search_id = list_resp.json()[0]["id"]

    resp = await api_client.put(
        f"{API_PREFIX}/saved-searches/{search_id}",
        json={"name": "Updated via API"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated via API"


@pytest.mark.anyio
async def test_api_update_saved_search_not_found(api_client: AsyncClient):
    resp = await api_client.put(
        f"{API_PREFIX}/saved-searches/nonexistent",
        json={"name": "Nope"},
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_api_delete_saved_search(api_client: AsyncClient):
    list_resp = await api_client.get(f"{API_PREFIX}/saved-searches")
    search_id = list_resp.json()[0]["id"]

    resp = await api_client.delete(f"{API_PREFIX}/saved-searches/{search_id}")
    assert resp.status_code == 204

    # Verify deletion
    get_resp = await api_client.get(f"{API_PREFIX}/saved-searches/{search_id}")
    assert get_resp.status_code == 404


@pytest.mark.anyio
async def test_api_delete_saved_search_not_found(api_client: AsyncClient):
    resp = await api_client.delete(f"{API_PREFIX}/saved-searches/nonexistent")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_api_execute_saved_search(api_client: AsyncClient):
    list_resp = await api_client.get(f"{API_PREFIX}/saved-searches")
    search_id = list_resp.json()[0]["id"]

    resp = await api_client.post(f"{API_PREFIX}/saved-searches/{search_id}/execute")
    assert resp.status_code == 201
    body = resp.json()
    assert body["total_screened"] > 0
    assert "results" in body


@pytest.mark.anyio
async def test_api_execute_saved_search_not_found(api_client: AsyncClient):
    resp = await api_client.post(f"{API_PREFIX}/saved-searches/nonexistent/execute")
    assert resp.status_code == 404


# ===========================================================================
# 15. Screening Result Verification
# ===========================================================================


class TestScreeningResultDetails:
    """Tests for detailed screening result correctness."""

    def test_eligible_patient_has_all_criteria_matched(self, svc: ScreeningDashboardService):
        from app.schemas.screening_dashboard import RunScreeningRequest
        session = svc.run_screening(RunScreeningRequest(trial_id="TRIAL-EYLEA-DME"))
        eligible = [r for r in session.results if r.status == ScreeningStatus.ELIGIBLE]
        for r in eligible:
            assert len(r.unmatched_criteria) == 0
            assert len(r.missing_data) == 0

    def test_ineligible_patient_has_unmatched_criteria(self, svc: ScreeningDashboardService):
        from app.schemas.screening_dashboard import RunScreeningRequest
        session = svc.run_screening(RunScreeningRequest(trial_id="TRIAL-EYLEA-DME"))
        ineligible = [r for r in session.results if r.status == ScreeningStatus.INELIGIBLE]
        for r in ineligible:
            assert len(r.unmatched_criteria) > 0

    def test_indeterminate_has_missing_data(self, svc: ScreeningDashboardService):
        from app.schemas.screening_dashboard import RunScreeningRequest
        session = svc.run_screening(RunScreeningRequest(trial_id="TRIAL-EYLEA-DME"))
        indeterminate = [r for r in session.results if r.status == ScreeningStatus.INDETERMINATE]
        for r in indeterminate:
            assert len(r.missing_data) > 0
            assert len(r.unmatched_criteria) == 0

    def test_patient_conditions_populated(self, svc: ScreeningDashboardService):
        from app.schemas.screening_dashboard import RunScreeningRequest
        session = svc.run_screening(RunScreeningRequest(trial_id="TRIAL-EYLEA-DME"))
        for r in session.results:
            assert len(r.primary_conditions) > 0

    def test_eligible_patient_dme(self, svc: ScreeningDashboardService):
        """Patients with DME, correct age, and correct labs should be eligible."""
        from app.schemas.screening_dashboard import RunScreeningRequest
        session = svc.run_screening(RunScreeningRequest(trial_id="TRIAL-EYLEA-DME"))
        # Maria Garcia (PAT-001): DME, age 62, BCVA 58 (24-73), CRT 350 (>=300) -- eligible
        maria = next((r for r in session.results if r.patient_id == "PAT-001"), None)
        assert maria is not None
        assert maria.status == ScreeningStatus.ELIGIBLE

    def test_ineligible_patient_no_dme(self, svc: ScreeningDashboardService):
        """Patients without DME should be ineligible for EYLEA trial."""
        from app.schemas.screening_dashboard import RunScreeningRequest
        session = svc.run_screening(RunScreeningRequest(trial_id="TRIAL-EYLEA-DME"))
        # Sarah Chen (PAT-003): No DME -- ineligible
        sarah = next((r for r in session.results if r.patient_id == "PAT-003"), None)
        assert sarah is not None
        assert sarah.status == ScreeningStatus.INELIGIBLE


# ===========================================================================
# 16. Edge Cases and Error Handling
# ===========================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_create_search_empty_conditions(self, svc: ScreeningDashboardService):
        create = SavedSearchCreate(
            name="Empty Conditions",
            filters=SavedSearchFilters(conditions=[]),
        )
        result = svc.create_saved_search(create)
        assert result.filters.conditions == []

    def test_run_screening_totals_add_up(self, svc: ScreeningDashboardService):
        from app.schemas.screening_dashboard import RunScreeningRequest
        session = svc.run_screening(RunScreeningRequest(trial_id="TRIAL-EYLEA-DME"))
        total = session.total_eligible + session.total_ineligible + session.total_indeterminate
        assert total == session.total_screened

    def test_multiple_runs_create_separate_sessions(self, svc: ScreeningDashboardService):
        from app.schemas.screening_dashboard import RunScreeningRequest
        initial_count = len(svc.get_screening_history(limit=100))
        svc.run_screening(RunScreeningRequest(trial_id="TRIAL-EYLEA-DME"))
        svc.run_screening(RunScreeningRequest(trial_id="TRIAL-DUPIXENT-AD"))
        assert len(svc.get_screening_history(limit=100)) == initial_count + 2

    def test_export_data_has_correct_row_count(self, svc: ScreeningDashboardService):
        from app.schemas.screening_dashboard import RunScreeningRequest
        session = svc.run_screening(RunScreeningRequest(trial_id="TRIAL-EYLEA-DME"))
        export = svc.export_results(session.id)
        assert export is not None
        assert export.row_count == session.total_screened
        assert len(export.data) == session.total_screened

    def test_filter_between_missing_values(self, svc: ScreeningDashboardService):
        from app.schemas.screening_dashboard import RunScreeningRequest
        session = svc.run_screening(RunScreeningRequest(
            trial_id="TRIAL-EYLEA-DME",
            filters=[ScreeningFilter(field="age", operator=FilterOperator.BETWEEN, values=[200, 300])],
        ))
        assert session.total_screened == 0


# ===========================================================================
# 17. Additional API Validation Tests
# ===========================================================================


@pytest.mark.anyio
async def test_api_create_search_missing_name(api_client: AsyncClient):
    resp = await api_client.post(
        f"{API_PREFIX}/saved-searches",
        json={"filters": {}},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_api_create_search_missing_filters(api_client: AsyncClient):
    resp = await api_client.post(
        f"{API_PREFIX}/saved-searches",
        json={"name": "No Filters"},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_api_run_missing_trial_id(api_client: AsyncClient):
    resp = await api_client.post(
        f"{API_PREFIX}/run",
        json={},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_api_history_invalid_limit(api_client: AsyncClient):
    resp = await api_client.get(f"{API_PREFIX}/history", params={"limit": 0})
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_api_history_limit_too_large(api_client: AsyncClient):
    resp = await api_client.get(f"{API_PREFIX}/history", params={"limit": 200})
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_api_run_screening_returns_session_fields(api_client: AsyncClient):
    resp = await api_client.post(
        f"{API_PREFIX}/run",
        json={"trial_id": "TRIAL-LIBTAYO-CSCC"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body
    assert "trial_id" in body
    assert "total_screened" in body
    assert "total_eligible" in body
    assert "total_ineligible" in body
    assert "total_indeterminate" in body
    assert "results" in body
    assert "started_at" in body
    assert "completed_at" in body


@pytest.mark.anyio
async def test_api_summary_trend_length(api_client: AsyncClient):
    resp = await api_client.get(f"{API_PREFIX}/summary")
    body = resp.json()
    assert len(body["screening_rate_trend"]) == 7


@pytest.mark.anyio
async def test_api_metrics_exclusion_counts(api_client: AsyncClient):
    resp = await api_client.get(f"{API_PREFIX}/metrics")
    body = resp.json()
    for reason in body["most_common_exclusion_reasons"]:
        assert reason["count"] > 0
        assert reason["reason"]


@pytest.mark.anyio
async def test_api_full_workflow(api_client: AsyncClient):
    """Test a full workflow: create search, execute, get session, export."""
    # Create
    create_resp = await api_client.post(
        f"{API_PREFIX}/saved-searches",
        json={
            "name": "Workflow Test",
            "filters": {
                "trial_id": "TRIAL-DUPIXENT-AD",
                "conditions": ["Atopic Dermatitis"],
            },
        },
    )
    assert create_resp.status_code == 201
    search_id = create_resp.json()["id"]

    # Execute
    exec_resp = await api_client.post(f"{API_PREFIX}/saved-searches/{search_id}/execute")
    assert exec_resp.status_code == 201
    session_id = exec_resp.json()["id"]

    # Get session
    session_resp = await api_client.get(f"{API_PREFIX}/sessions/{session_id}")
    assert session_resp.status_code == 200
    assert session_resp.json()["total_screened"] > 0

    # Export
    export_resp = await api_client.get(f"{API_PREFIX}/sessions/{session_id}/export")
    assert export_resp.status_code == 200
    assert export_resp.json()["row_count"] > 0

    # Delete search
    del_resp = await api_client.delete(f"{API_PREFIX}/saved-searches/{search_id}")
    assert del_resp.status_code == 204


@pytest.mark.anyio
async def test_api_update_search_with_new_filters(api_client: AsyncClient):
    list_resp = await api_client.get(f"{API_PREFIX}/saved-searches")
    search_id = list_resp.json()[0]["id"]

    resp = await api_client.put(
        f"{API_PREFIX}/saved-searches/{search_id}",
        json={
            "name": "Updated Filters",
            "filters": {
                "conditions": ["Hypertension"],
                "age_range": {"min": 50, "max": 80},
            },
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Updated Filters"
    assert "Hypertension" in body["filters"]["conditions"]
