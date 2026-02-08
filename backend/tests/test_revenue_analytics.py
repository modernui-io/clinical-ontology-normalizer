"""Tests for CFO-2: Revenue Analytics & Financial Reporting Service.

Tests cover:
- Seed data: contracts, monthly revenue, cohorts
- Contract CRUD: create, read, update, list, filter by status/sponsor
- Monthly revenue: full range, filtered range, empty range
- Revenue metrics: MRR, ARR, growth, NRR, margins, LTV/CAC, payback
- Cohort analysis: count, retention rates, churn
- Revenue forecasting: projection, confidence intervals, assumptions
- Financial reports: monthly, quarterly, annual P&L
- Revenue breakdowns: by stream, by sponsor
- Revenue recognition: recognize, update contract, update monthly
- API endpoint integration tests (all 12 routes)
- Edge cases: not-found, empty data, zero division protection
- Singleton pattern (get/reset)
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.revenue_analytics import (
    ContractStatus,
    ReportType,
    RevenueStream,
)
from app.services.revenue_analytics_service import (
    RevenueAnalyticsService,
    get_revenue_analytics_service,
    reset_revenue_analytics_service,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_service():
    """Reset the singleton service before and after each test."""
    reset_revenue_analytics_service()
    yield
    reset_revenue_analytics_service()


@pytest.fixture
def service() -> RevenueAnalyticsService:
    return get_revenue_analytics_service()


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ============================================================================
# Seed Data Tests
# ============================================================================


class TestSeedData:
    """Tests for pre-populated contracts, monthly revenue, and cohorts."""

    def test_seed_contracts_count(self, service: RevenueAnalyticsService):
        """Service should have 6 pre-populated contracts."""
        result = service.list_contracts()
        assert result.total == 6

    def test_seed_contracts_have_ids(self, service: RevenueAnalyticsService):
        """All contracts should have CTR- prefixed IDs."""
        result = service.list_contracts()
        for c in result.contracts:
            assert c.id.startswith("CTR-")

    def test_seed_contracts_sponsors(self, service: RevenueAnalyticsService):
        """Seed data should include expected sponsors."""
        result = service.list_contracts()
        sponsors = {c.sponsor_name for c in result.contracts}
        assert "Regeneron" in sponsors
        assert "Pfizer" in sponsors
        assert "Novartis" in sponsors
        assert "AstraZeneca" in sponsors

    def test_seed_contracts_trial_ids(self, service: RevenueAnalyticsService):
        """Seed data should include expected trial IDs."""
        result = service.list_contracts()
        trial_ids = {c.trial_id for c in result.contracts}
        assert "EYLEA-HD-2024" in trial_ids
        assert "DUPIXENT-AD-2024" in trial_ids
        assert "LIBTAYO-NSCLC-2024" in trial_ids

    def test_seed_contracts_have_positive_values(self, service: RevenueAnalyticsService):
        """All contracts should have positive contract values."""
        result = service.list_contracts()
        for c in result.contracts:
            assert c.total_contract_value > 0

    def test_seed_contracts_remaining_value(self, service: RevenueAnalyticsService):
        """Remaining value = total - recognized."""
        result = service.list_contracts()
        for c in result.contracts:
            expected = c.total_contract_value - c.recognized_revenue
            assert abs(c.remaining_value - expected) < 0.01

    def test_seed_active_contracts(self, service: RevenueAnalyticsService):
        """Most contracts should be active."""
        result = service.list_contracts(status=ContractStatus.ACTIVE)
        assert result.total >= 4

    def test_seed_monthly_revenue_count(self, service: RevenueAnalyticsService):
        """Service should have 12 months of revenue data."""
        result = service.get_monthly_revenue()
        assert result.total == 12

    def test_seed_monthly_revenue_growth(self, service: RevenueAnalyticsService):
        """Revenue should generally grow month-over-month."""
        result = service.get_monthly_revenue()
        totals = [m.total for m in result.months]
        assert totals[-1] > totals[0]

    def test_seed_monthly_revenue_has_streams(self, service: RevenueAnalyticsService):
        """Each month should have stream breakdown."""
        result = service.get_monthly_revenue()
        for m in result.months:
            assert len(m.by_stream) > 0

    def test_seed_monthly_revenue_has_sponsors(self, service: RevenueAnalyticsService):
        """Each month should have sponsor breakdown."""
        result = service.get_monthly_revenue()
        for m in result.months:
            assert len(m.by_sponsor) > 0

    def test_seed_monthly_revenue_patient_volume(self, service: RevenueAnalyticsService):
        """Each month should have positive patient volume."""
        result = service.get_monthly_revenue()
        for m in result.months:
            assert m.patient_volume > 0

    def test_seed_cohorts_count(self, service: RevenueAnalyticsService):
        """Service should have 4 cohort records."""
        result = service.get_cohort_analysis()
        assert result.total == 4

    def test_seed_cohorts_have_sponsors(self, service: RevenueAnalyticsService):
        """Each cohort should have at least 1 sponsor acquired."""
        result = service.get_cohort_analysis()
        for c in result.cohorts:
            assert c.sponsors_acquired >= 1

    def test_seed_cohorts_retention_decreases(self, service: RevenueAnalyticsService):
        """Month 1 retention should be >= month 12 retention."""
        result = service.get_cohort_analysis()
        for c in result.cohorts:
            assert c.month_1_retention >= c.month_12_retention


# ============================================================================
# Contract CRUD
# ============================================================================


class TestContractCRUD:
    """Tests for contract create, read, update, list."""

    def test_create_contract(self, service: RevenueAnalyticsService):
        """Creating a contract should return it with an ID."""
        from app.schemas.revenue_analytics import RevenueContractCreate
        data = RevenueContractCreate(
            sponsor_name="Merck",
            trial_id="MRK-IMM-2025",
            stream=RevenueStream.PLATFORM_LICENSE,
            status=ContractStatus.DRAFT,
            monthly_base_fee=20_000.0,
            per_patient_fee=600.0,
            per_enrollment_fee=4_000.0,
            start_date=date(2025, 6, 1),
            end_date=date(2027, 5, 31),
            total_contract_value=800_000.0,
        )
        contract = service.create_contract(data)
        assert contract.id.startswith("CTR-")
        assert contract.sponsor_name == "Merck"
        assert contract.recognized_revenue == 0.0
        assert contract.remaining_value == 800_000.0

    def test_create_contract_increments_count(self, service: RevenueAnalyticsService):
        """Creating a contract should increment the total count."""
        before = service.list_contracts().total
        from app.schemas.revenue_analytics import RevenueContractCreate
        data = RevenueContractCreate(
            sponsor_name="Sanofi",
            trial_id="SNF-DRM-2025",
            stream=RevenueStream.DATA_ANALYTICS,
            start_date=date(2025, 7, 1),
            end_date=date(2026, 6, 30),
            total_contract_value=500_000.0,
        )
        service.create_contract(data)
        after = service.list_contracts().total
        assert after == before + 1

    def test_get_contract_by_id(self, service: RevenueAnalyticsService):
        """Should retrieve a contract by its ID."""
        contracts = service.list_contracts().contracts
        target = contracts[0]
        result = service.get_contract(target.id)
        assert result is not None
        assert result.id == target.id

    def test_get_contract_not_found(self, service: RevenueAnalyticsService):
        """Non-existent contract should return None."""
        result = service.get_contract("CTR-NONEXISTENT")
        assert result is None

    def test_update_contract_status(self, service: RevenueAnalyticsService):
        """Updating status should persist."""
        from app.schemas.revenue_analytics import RevenueContractUpdate
        contracts = service.list_contracts().contracts
        target = contracts[0]
        updated = service.update_contract(
            target.id,
            RevenueContractUpdate(status=ContractStatus.PAUSED),
        )
        assert updated is not None
        assert updated.status == ContractStatus.PAUSED

    def test_update_contract_fee(self, service: RevenueAnalyticsService):
        """Updating fees should persist."""
        from app.schemas.revenue_analytics import RevenueContractUpdate
        contracts = service.list_contracts().contracts
        target = contracts[0]
        updated = service.update_contract(
            target.id,
            RevenueContractUpdate(monthly_base_fee=99_999.0),
        )
        assert updated is not None
        assert updated.monthly_base_fee == 99_999.0

    def test_update_contract_not_found(self, service: RevenueAnalyticsService):
        """Updating non-existent contract should return None."""
        from app.schemas.revenue_analytics import RevenueContractUpdate
        result = service.update_contract(
            "CTR-NONEXISTENT",
            RevenueContractUpdate(status=ContractStatus.TERMINATED),
        )
        assert result is None

    def test_list_contracts_filter_by_status(self, service: RevenueAnalyticsService):
        """Filtering by DRAFT should return only DRAFT contracts."""
        result = service.list_contracts(status=ContractStatus.DRAFT)
        for c in result.contracts:
            assert c.status == ContractStatus.DRAFT

    def test_list_contracts_filter_by_sponsor(self, service: RevenueAnalyticsService):
        """Filtering by sponsor should return only that sponsor."""
        result = service.list_contracts(sponsor="Regeneron")
        assert result.total >= 3
        for c in result.contracts:
            assert c.sponsor_name == "Regeneron"

    def test_list_contracts_filter_case_insensitive(self, service: RevenueAnalyticsService):
        """Sponsor filter should be case-insensitive."""
        result = service.list_contracts(sponsor="regeneron")
        assert result.total >= 3

    def test_list_contracts_combined_filters(self, service: RevenueAnalyticsService):
        """Status + sponsor filters should both apply."""
        result = service.list_contracts(
            status=ContractStatus.ACTIVE,
            sponsor="Regeneron",
        )
        for c in result.contracts:
            assert c.status == ContractStatus.ACTIVE
            assert c.sponsor_name == "Regeneron"


# ============================================================================
# Monthly Revenue
# ============================================================================


class TestMonthlyRevenue:
    """Tests for monthly revenue retrieval and filtering."""

    def test_full_range(self, service: RevenueAnalyticsService):
        """Full range should return all 12 months."""
        result = service.get_monthly_revenue()
        assert result.total == 12

    def test_filtered_start(self, service: RevenueAnalyticsService):
        """Filtering with start_month should exclude earlier months."""
        result = service.get_monthly_revenue(start_month="2025-06")
        assert result.total == 7  # June through December
        for m in result.months:
            assert m.month >= "2025-06"

    def test_filtered_end(self, service: RevenueAnalyticsService):
        """Filtering with end_month should exclude later months."""
        result = service.get_monthly_revenue(end_month="2025-03")
        assert result.total == 3
        for m in result.months:
            assert m.month <= "2025-03"

    def test_filtered_range(self, service: RevenueAnalyticsService):
        """Filtering with start and end should return months in range."""
        result = service.get_monthly_revenue(
            start_month="2025-04",
            end_month="2025-06",
        )
        assert result.total == 3

    def test_empty_range(self, service: RevenueAnalyticsService):
        """A range with no data should return empty list."""
        result = service.get_monthly_revenue(
            start_month="2030-01",
            end_month="2030-12",
        )
        assert result.total == 0

    def test_months_sorted(self, service: RevenueAnalyticsService):
        """Months should be in chronological order."""
        result = service.get_monthly_revenue()
        months = [m.month for m in result.months]
        assert months == sorted(months)

    def test_stream_breakdown_sums(self, service: RevenueAnalyticsService):
        """Stream breakdown should approximately sum to total."""
        result = service.get_monthly_revenue()
        for m in result.months:
            stream_sum = sum(m.by_stream.values())
            assert abs(stream_sum - m.total) < 1.0  # rounding tolerance

    def test_sponsor_breakdown_sums(self, service: RevenueAnalyticsService):
        """Sponsor breakdown should approximately sum to total."""
        result = service.get_monthly_revenue()
        for m in result.months:
            sponsor_sum = sum(m.by_sponsor.values())
            assert abs(sponsor_sum - m.total) < 1.0


# ============================================================================
# Revenue Metrics
# ============================================================================


class TestRevenueMetrics:
    """Tests for SaaS metric calculations."""

    def test_mrr_positive(self, service: RevenueAnalyticsService):
        """MRR should be positive."""
        metrics = service.get_revenue_metrics()
        assert metrics.mrr > 0

    def test_arr_is_12x_mrr(self, service: RevenueAnalyticsService):
        """ARR should be 12x MRR."""
        metrics = service.get_revenue_metrics()
        assert abs(metrics.arr - metrics.mrr * 12) < 0.01

    def test_mrr_growth_positive(self, service: RevenueAnalyticsService):
        """MRR growth should be positive with growing revenue."""
        metrics = service.get_revenue_metrics()
        assert metrics.mrr_growth_rate_pct > 0

    def test_nrr_above_100(self, service: RevenueAnalyticsService):
        """NRR should be above 100% with growing revenue."""
        metrics = service.get_revenue_metrics()
        assert metrics.net_revenue_retention_pct > 100

    def test_gross_margin_positive(self, service: RevenueAnalyticsService):
        """Gross margin should be positive."""
        metrics = service.get_revenue_metrics()
        assert metrics.gross_margin_pct > 0
        assert metrics.gross_margin_pct < 100

    def test_arpu_positive(self, service: RevenueAnalyticsService):
        """ARPU should be positive."""
        metrics = service.get_revenue_metrics()
        assert metrics.arpu > 0

    def test_ltv_positive(self, service: RevenueAnalyticsService):
        """LTV should be positive."""
        metrics = service.get_revenue_metrics()
        assert metrics.ltv > 0

    def test_cac_matches_constant(self, service: RevenueAnalyticsService):
        """CAC should match the service constant."""
        metrics = service.get_revenue_metrics()
        assert metrics.cac == service.CAC

    def test_ltv_cac_ratio(self, service: RevenueAnalyticsService):
        """LTV/CAC ratio should be consistent with components."""
        metrics = service.get_revenue_metrics()
        if metrics.cac > 0:
            expected = metrics.ltv / metrics.cac
            assert abs(metrics.ltv_cac_ratio - round(expected, 2)) < 0.01

    def test_payback_period(self, service: RevenueAnalyticsService):
        """Payback period should be consistent with CAC/ARPU."""
        metrics = service.get_revenue_metrics()
        if metrics.arpu > 0:
            expected = metrics.cac / metrics.arpu
            assert abs(metrics.payback_period_months - round(expected, 2)) < 0.01

    def test_revenue_per_employee(self, service: RevenueAnalyticsService):
        """Revenue per employee should be ARR / employee count."""
        metrics = service.get_revenue_metrics()
        expected = metrics.arr / service.EMPLOYEE_COUNT
        assert abs(metrics.revenue_per_employee - round(expected, 2)) < 0.01


# ============================================================================
# Cohort Analysis
# ============================================================================


class TestCohortAnalysis:
    """Tests for sponsor cohort retention analysis."""

    def test_cohort_count(self, service: RevenueAnalyticsService):
        """Should return 4 cohort records."""
        result = service.get_cohort_analysis()
        assert result.total == 4

    def test_cohort_months(self, service: RevenueAnalyticsService):
        """Cohort months should be quarterly."""
        result = service.get_cohort_analysis()
        months = {c.cohort_month for c in result.cohorts}
        assert "2024-Q1" in months
        assert "2025-Q1" in months

    def test_cohort_retention_bounds(self, service: RevenueAnalyticsService):
        """Retention rates should be between 0 and 1."""
        result = service.get_cohort_analysis()
        for c in result.cohorts:
            assert 0.0 <= c.month_1_retention <= 1.0
            assert 0.0 <= c.month_3_retention <= 1.0
            assert 0.0 <= c.month_6_retention <= 1.0
            assert 0.0 <= c.month_12_retention <= 1.0

    def test_cohort_churn_rate_bounds(self, service: RevenueAnalyticsService):
        """Churn rate should be between 0 and 1."""
        result = service.get_cohort_analysis()
        for c in result.cohorts:
            assert 0.0 <= c.churn_rate <= 1.0

    def test_cohort_avg_revenue(self, service: RevenueAnalyticsService):
        """Average revenue per sponsor should be positive."""
        result = service.get_cohort_analysis()
        for c in result.cohorts:
            assert c.avg_revenue_per_sponsor > 0


# ============================================================================
# Revenue Forecasting
# ============================================================================


class TestRevenueForecast:
    """Tests for revenue forecasting with linear regression."""

    def test_forecast_default_months(self, service: RevenueAnalyticsService):
        """Default forecast should return 6 months."""
        result = service.forecast_revenue()
        assert result.total == 6

    def test_forecast_custom_months(self, service: RevenueAnalyticsService):
        """Custom forecast should return requested months."""
        result = service.forecast_revenue(months_ahead=12)
        assert result.total == 12

    def test_forecast_months_are_future(self, service: RevenueAnalyticsService):
        """Forecast months should be after historical data."""
        result = service.forecast_revenue()
        for f in result.forecasts:
            assert f.month > "2025-12"

    def test_forecast_projected_positive(self, service: RevenueAnalyticsService):
        """Projected revenue should be positive."""
        result = service.forecast_revenue()
        for f in result.forecasts:
            assert f.projected_revenue > 0

    def test_forecast_confidence_bounds(self, service: RevenueAnalyticsService):
        """Confidence low <= projected <= confidence high."""
        result = service.forecast_revenue()
        for f in result.forecasts:
            assert f.confidence_low <= f.projected_revenue
            assert f.projected_revenue <= f.confidence_high

    def test_forecast_confidence_widens(self, service: RevenueAnalyticsService):
        """Confidence interval should widen for farther-out months."""
        result = service.forecast_revenue(months_ahead=6)
        widths = [
            f.confidence_high - f.confidence_low
            for f in result.forecasts
        ]
        # Generally increasing (allow small tolerance)
        assert widths[-1] > widths[0]

    def test_forecast_has_assumptions(self, service: RevenueAnalyticsService):
        """Each forecast should have assumptions."""
        result = service.forecast_revenue()
        for f in result.forecasts:
            assert len(f.assumptions) > 0

    def test_forecast_month_format(self, service: RevenueAnalyticsService):
        """Forecast months should be YYYY-MM format."""
        result = service.forecast_revenue()
        for f in result.forecasts:
            assert len(f.month) == 7
            assert f.month[4] == "-"

    def test_forecast_sequential_months(self, service: RevenueAnalyticsService):
        """Forecast months should be sequential."""
        result = service.forecast_revenue(months_ahead=6)
        months = [f.month for f in result.forecasts]
        assert months == sorted(months)


# ============================================================================
# Financial Reports
# ============================================================================


class TestFinancialReport:
    """Tests for P&L-style financial reports."""

    def test_monthly_report(self, service: RevenueAnalyticsService):
        """Monthly report should return valid P&L."""
        report = service.generate_financial_report(
            report_type=ReportType.MONTHLY,
            period="2025-12",
        )
        assert report.report_type == ReportType.MONTHLY
        assert report.period == "2025-12"
        assert report.total_revenue > 0

    def test_quarterly_report(self, service: RevenueAnalyticsService):
        """Quarterly report should aggregate 3 months."""
        report = service.generate_financial_report(
            report_type=ReportType.QUARTERLY,
            period="2025-Q4",
        )
        assert report.report_type == ReportType.QUARTERLY
        assert report.period == "2025-Q4"
        # Q4 = Oct + Nov + Dec should be > any single month
        monthly = service.generate_financial_report(
            report_type=ReportType.MONTHLY,
            period="2025-12",
        )
        assert report.total_revenue > monthly.total_revenue

    def test_annual_report(self, service: RevenueAnalyticsService):
        """Annual report should aggregate all 12 months."""
        report = service.generate_financial_report(
            report_type=ReportType.ANNUAL,
            period="2025",
        )
        assert report.report_type == ReportType.ANNUAL
        assert report.period == "2025"
        assert report.total_revenue > 0

    def test_report_gross_profit(self, service: RevenueAnalyticsService):
        """Gross profit = revenue - costs."""
        report = service.generate_financial_report(
            report_type=ReportType.MONTHLY,
            period="2025-12",
        )
        expected = report.total_revenue - report.total_costs
        assert abs(report.gross_profit - expected) < 0.01

    def test_report_gross_margin(self, service: RevenueAnalyticsService):
        """Gross margin should be positive and < 100%."""
        report = service.generate_financial_report(
            report_type=ReportType.MONTHLY,
            period="2025-12",
        )
        assert report.gross_margin_pct > 0
        assert report.gross_margin_pct < 100

    def test_report_ebitda(self, service: RevenueAnalyticsService):
        """EBITDA = gross profit - operating expenses."""
        report = service.generate_financial_report(
            report_type=ReportType.MONTHLY,
            period="2025-12",
        )
        expected = report.gross_profit - report.operating_expenses
        assert abs(report.ebitda - expected) < 0.01

    def test_report_mrr_positive(self, service: RevenueAnalyticsService):
        """MRR in report should be positive."""
        report = service.generate_financial_report(
            report_type=ReportType.MONTHLY,
            period="2025-12",
        )
        assert report.mrr > 0

    def test_report_arr_is_12x_mrr(self, service: RevenueAnalyticsService):
        """ARR should be 12x MRR."""
        report = service.generate_financial_report(
            report_type=ReportType.MONTHLY,
            period="2025-12",
        )
        assert abs(report.arr - report.mrr * 12) < 0.01

    def test_report_customer_count(self, service: RevenueAnalyticsService):
        """Customer count should match active sponsors."""
        report = service.generate_financial_report(
            report_type=ReportType.MONTHLY,
            period="2025-12",
        )
        assert report.customer_count >= 1

    def test_report_default_period(self, service: RevenueAnalyticsService):
        """Default monthly report should use last available month."""
        report = service.generate_financial_report(report_type=ReportType.MONTHLY)
        assert report.period == "2025-12"


# ============================================================================
# Revenue Breakdowns
# ============================================================================


class TestRevenueBreakdown:
    """Tests for revenue breakdown by stream and sponsor."""

    def test_by_stream_all_streams(self, service: RevenueAnalyticsService):
        """By-stream breakdown should include all 6 streams."""
        result = service.get_revenue_by_stream()
        assert len(result.streams) == 6

    def test_by_stream_totals_match(self, service: RevenueAnalyticsService):
        """Stream totals should sum to total_revenue."""
        result = service.get_revenue_by_stream()
        stream_sum = sum(s.total for s in result.streams)
        assert abs(stream_sum - result.total_revenue) < 1.0

    def test_by_stream_percentages_sum_to_100(self, service: RevenueAnalyticsService):
        """Stream percentages should sum to ~100%."""
        result = service.get_revenue_by_stream()
        pct_sum = sum(s.percentage for s in result.streams)
        assert abs(pct_sum - 100.0) < 1.0

    def test_by_sponsor_all_sponsors(self, service: RevenueAnalyticsService):
        """By-sponsor breakdown should include all 4 sponsors."""
        result = service.get_revenue_by_sponsor()
        assert len(result.sponsors) >= 4

    def test_by_sponsor_totals_match(self, service: RevenueAnalyticsService):
        """Sponsor totals should sum to total_revenue."""
        result = service.get_revenue_by_sponsor()
        sponsor_sum = sum(s.total for s in result.sponsors)
        assert abs(sponsor_sum - result.total_revenue) < 1.0

    def test_by_sponsor_percentages_sum_to_100(self, service: RevenueAnalyticsService):
        """Sponsor percentages should sum to ~100%."""
        result = service.get_revenue_by_sponsor()
        pct_sum = sum(s.percentage for s in result.sponsors)
        assert abs(pct_sum - 100.0) < 1.0

    def test_by_sponsor_sorted_descending(self, service: RevenueAnalyticsService):
        """Sponsors should be sorted by revenue descending."""
        result = service.get_revenue_by_sponsor()
        totals = [s.total for s in result.sponsors]
        assert totals == sorted(totals, reverse=True)


# ============================================================================
# Revenue Recognition
# ============================================================================


class TestRevenueRecognition:
    """Tests for revenue recognition events."""

    def test_recognize_updates_contract(self, service: RevenueAnalyticsService):
        """Recognizing revenue should update the contract."""
        contracts = service.list_contracts().contracts
        target = contracts[0]
        original_recognized = target.recognized_revenue

        result = service.recognize_revenue(target.id, 10_000.0, "2025-12")
        assert result is not None
        assert result.amount_recognized == 10_000.0
        assert result.total_recognized == original_recognized + 10_000.0

    def test_recognize_updates_remaining(self, service: RevenueAnalyticsService):
        """Recognizing revenue should decrease remaining value."""
        contracts = service.list_contracts().contracts
        target = contracts[0]
        original_remaining = target.remaining_value

        service.recognize_revenue(target.id, 5_000.0, "2025-12")
        updated = service.get_contract(target.id)
        assert updated is not None
        assert abs(updated.remaining_value - (original_remaining - 5_000.0)) < 0.01

    def test_recognize_not_found(self, service: RevenueAnalyticsService):
        """Recognizing on non-existent contract should return None."""
        result = service.recognize_revenue("CTR-NONEXISTENT", 1_000.0, "2025-12")
        assert result is None

    def test_recognize_updates_monthly(self, service: RevenueAnalyticsService):
        """Recognizing revenue should update monthly total if month exists."""
        contracts = service.list_contracts().contracts
        target = contracts[0]

        before = service.get_monthly_revenue(start_month="2025-12", end_month="2025-12")
        original_total = before.months[0].total

        service.recognize_revenue(target.id, 7_500.0, "2025-12")
        after = service.get_monthly_revenue(start_month="2025-12", end_month="2025-12")
        assert abs(after.months[0].total - (original_total + 7_500.0)) < 0.01


# ============================================================================
# Stats / Singleton
# ============================================================================


class TestServiceStats:
    """Tests for service stats and singleton pattern."""

    def test_stats(self, service: RevenueAnalyticsService):
        """Stats should report expected counts."""
        stats = service.get_stats()
        assert stats["contract_count"] == 6
        assert stats["monthly_revenue_months"] == 12
        assert stats["cohort_count"] == 4
        assert stats["active_contracts"] >= 4

    def test_singleton_returns_same_instance(self):
        """get_revenue_analytics_service should return the same instance."""
        s1 = get_revenue_analytics_service()
        s2 = get_revenue_analytics_service()
        assert s1 is s2

    def test_reset_creates_new_instance(self):
        """reset then get should return a fresh instance."""
        s1 = get_revenue_analytics_service()
        reset_revenue_analytics_service()
        s2 = get_revenue_analytics_service()
        assert s1 is not s2


# ============================================================================
# API Endpoint Tests
# ============================================================================


class TestAPIEndpoints:
    """Integration tests for all revenue analytics API endpoints."""

    @pytest.mark.anyio
    async def test_list_contracts(self, client: AsyncClient):
        """GET /revenue-analytics/contracts should return 200."""
        resp = await client.get("/api/v1/revenue-analytics/contracts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6
        assert len(data["contracts"]) == 6

    @pytest.mark.anyio
    async def test_list_contracts_filter_status(self, client: AsyncClient):
        """GET /revenue-analytics/contracts?status=active should filter."""
        resp = await client.get("/api/v1/revenue-analytics/contracts?status=active")
        assert resp.status_code == 200
        data = resp.json()
        for c in data["contracts"]:
            assert c["status"] == "active"

    @pytest.mark.anyio
    async def test_list_contracts_filter_sponsor(self, client: AsyncClient):
        """GET /revenue-analytics/contracts?sponsor=Regeneron should filter."""
        resp = await client.get("/api/v1/revenue-analytics/contracts?sponsor=Regeneron")
        assert resp.status_code == 200
        data = resp.json()
        for c in data["contracts"]:
            assert c["sponsor_name"] == "Regeneron"

    @pytest.mark.anyio
    async def test_get_contract_by_id(self, client: AsyncClient):
        """GET /revenue-analytics/contracts/{id} should return the contract."""
        list_resp = await client.get("/api/v1/revenue-analytics/contracts")
        contract_id = list_resp.json()["contracts"][0]["id"]

        resp = await client.get(f"/api/v1/revenue-analytics/contracts/{contract_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == contract_id

    @pytest.mark.anyio
    async def test_get_contract_not_found(self, client: AsyncClient):
        """GET /revenue-analytics/contracts/CTR-MISSING should return 404."""
        resp = await client.get("/api/v1/revenue-analytics/contracts/CTR-MISSING")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_contract(self, client: AsyncClient):
        """POST /revenue-analytics/contracts should create and return 201."""
        body = {
            "sponsor_name": "Merck",
            "trial_id": "MRK-TEST",
            "stream": "platform_license",
            "start_date": "2025-06-01",
            "end_date": "2026-05-31",
            "total_contract_value": 600000,
        }
        resp = await client.post("/api/v1/revenue-analytics/contracts", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["sponsor_name"] == "Merck"
        assert data["id"].startswith("CTR-")

    @pytest.mark.anyio
    async def test_update_contract(self, client: AsyncClient):
        """PUT /revenue-analytics/contracts/{id} should update."""
        list_resp = await client.get("/api/v1/revenue-analytics/contracts")
        contract_id = list_resp.json()["contracts"][0]["id"]

        resp = await client.put(
            f"/api/v1/revenue-analytics/contracts/{contract_id}",
            json={"status": "paused"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "paused"

    @pytest.mark.anyio
    async def test_update_contract_not_found(self, client: AsyncClient):
        """PUT /revenue-analytics/contracts/CTR-MISSING should return 404."""
        resp = await client.put(
            "/api/v1/revenue-analytics/contracts/CTR-MISSING",
            json={"status": "paused"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_monthly_revenue(self, client: AsyncClient):
        """GET /revenue-analytics/monthly should return 200 with 12 months."""
        resp = await client.get("/api/v1/revenue-analytics/monthly")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_monthly_revenue_filtered(self, client: AsyncClient):
        """GET /revenue-analytics/monthly with range should filter."""
        resp = await client.get(
            "/api/v1/revenue-analytics/monthly?start_month=2025-06&end_month=2025-08"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_revenue_metrics(self, client: AsyncClient):
        """GET /revenue-analytics/metrics should return 200 with metrics."""
        resp = await client.get("/api/v1/revenue-analytics/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mrr"] > 0
        assert data["arr"] > 0

    @pytest.mark.anyio
    async def test_cohort_analysis(self, client: AsyncClient):
        """GET /revenue-analytics/cohorts should return 200 with 4 cohorts."""
        resp = await client.get("/api/v1/revenue-analytics/cohorts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4

    @pytest.mark.anyio
    async def test_forecast(self, client: AsyncClient):
        """GET /revenue-analytics/forecast should return 200 with forecasts."""
        resp = await client.get("/api/v1/revenue-analytics/forecast")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6

    @pytest.mark.anyio
    async def test_forecast_custom_months(self, client: AsyncClient):
        """GET /revenue-analytics/forecast?months_ahead=3 should return 3."""
        resp = await client.get("/api/v1/revenue-analytics/forecast?months_ahead=3")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_financial_report_monthly(self, client: AsyncClient):
        """GET /revenue-analytics/report?report_type=monthly should return P&L."""
        resp = await client.get(
            "/api/v1/revenue-analytics/report?report_type=monthly&period=2025-12"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["report_type"] == "monthly"
        assert data["total_revenue"] > 0

    @pytest.mark.anyio
    async def test_financial_report_quarterly(self, client: AsyncClient):
        """GET /revenue-analytics/report?report_type=quarterly should work."""
        resp = await client.get(
            "/api/v1/revenue-analytics/report?report_type=quarterly&period=2025-Q4"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["report_type"] == "quarterly"

    @pytest.mark.anyio
    async def test_financial_report_annual(self, client: AsyncClient):
        """GET /revenue-analytics/report?report_type=annual should work."""
        resp = await client.get(
            "/api/v1/revenue-analytics/report?report_type=annual&period=2025"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["report_type"] == "annual"

    @pytest.mark.anyio
    async def test_revenue_by_stream(self, client: AsyncClient):
        """GET /revenue-analytics/by-stream should return 200."""
        resp = await client.get("/api/v1/revenue-analytics/by-stream")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["streams"]) == 6
        assert data["total_revenue"] > 0

    @pytest.mark.anyio
    async def test_revenue_by_sponsor(self, client: AsyncClient):
        """GET /revenue-analytics/by-sponsor should return 200."""
        resp = await client.get("/api/v1/revenue-analytics/by-sponsor")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["sponsors"]) >= 4
        assert data["total_revenue"] > 0

    @pytest.mark.anyio
    async def test_recognize_revenue(self, client: AsyncClient):
        """POST /revenue-analytics/recognize should return 200."""
        list_resp = await client.get("/api/v1/revenue-analytics/contracts")
        contract_id = list_resp.json()["contracts"][0]["id"]

        body = {
            "contract_id": contract_id,
            "amount": 5000,
            "month": "2025-12",
        }
        resp = await client.post("/api/v1/revenue-analytics/recognize", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["amount_recognized"] == 5000

    @pytest.mark.anyio
    async def test_recognize_revenue_not_found(self, client: AsyncClient):
        """POST /revenue-analytics/recognize with bad ID should return 404."""
        body = {
            "contract_id": "CTR-NONEXISTENT",
            "amount": 1000,
            "month": "2025-12",
        }
        resp = await client.post("/api/v1/revenue-analytics/recognize", json=body)
        assert resp.status_code == 404
