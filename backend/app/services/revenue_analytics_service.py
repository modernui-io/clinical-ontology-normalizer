"""Revenue Analytics & Financial Reporting Service (CFO-2).

Provides revenue analytics for a pharma-regulated clinical trial
patient recruitment platform:
- Revenue contract CRUD (multi-sponsor, multi-trial)
- Historical monthly revenue tracking with stream/sponsor breakdown
- SaaS metrics: MRR, ARR, NRR, LTV/CAC, payback period
- Sponsor cohort retention analysis (quarterly cohorts)
- Simple linear regression revenue forecasting with confidence intervals
- P&L-style financial reporting (monthly/quarterly/annual)
- Revenue breakdown by stream and sponsor

All data lives in-memory; in production this would be backed by a
financial data warehouse or billing service.
"""

from __future__ import annotations

import logging
import math
import statistics
import threading
from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from app.schemas.revenue_analytics import (
    CohortAnalysis,
    CohortAnalysisListResponse,
    ContractStatus,
    FinancialReport,
    MonthlyRevenue,
    MonthlyRevenueListResponse,
    ReportType,
    RevenueBySponsorItem,
    RevenueBySponsorResponse,
    RevenueByStreamItem,
    RevenueByStreamResponse,
    RevenueContract,
    RevenueContractCreate,
    RevenueContractListResponse,
    RevenueContractUpdate,
    RevenueForecast,
    RevenueForecastListResponse,
    RevenueMetrics,
    RevenueRecognitionResponse,
    RevenueStream,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton plumbing
# ---------------------------------------------------------------------------

_service: RevenueAnalyticsService | None = None
_service_lock = threading.Lock()


def get_revenue_analytics_service() -> RevenueAnalyticsService:
    """Return the singleton RevenueAnalyticsService instance."""
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = RevenueAnalyticsService()
    return _service


def reset_revenue_analytics_service() -> None:
    """Reset the singleton (for testing)."""
    global _service
    with _service_lock:
        _service = None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class RevenueAnalyticsService:
    """In-memory revenue analytics and financial reporting engine."""

    # Platform-level assumptions
    EMPLOYEE_COUNT: int = 45
    MONTHLY_OPERATING_EXPENSES: float = 285_000.0
    COGS_RATE: float = 0.35  # 35% of revenue goes to COGS
    CAC: float = 42_000.0  # Customer acquisition cost per sponsor
    AVG_SPONSOR_LIFETIME_MONTHS: int = 24

    def __init__(self) -> None:
        self._contracts: dict[str, RevenueContract] = {}
        self._monthly_revenue: dict[str, MonthlyRevenue] = {}
        self._cohorts: list[CohortAnalysis] = []
        self._populate_contracts()
        self._populate_monthly_revenue()
        self._populate_cohorts()

    # ------------------------------------------------------------------
    # Seed data
    # ------------------------------------------------------------------

    def _populate_contracts(self) -> None:
        """Pre-populate 6 realistic revenue contracts."""
        now = datetime.now(timezone.utc)
        seed_contracts: list[dict[str, Any]] = [
            {
                "sponsor_name": "Regeneron",
                "trial_id": "EYLEA-HD-2024",
                "stream": RevenueStream.PER_PATIENT_SCREENING,
                "status": ContractStatus.ACTIVE,
                "monthly_base_fee": 35_000.0,
                "per_patient_fee": 1_200.0,
                "per_enrollment_fee": 6_500.0,
                "start_date": date(2024, 3, 1),
                "end_date": date(2026, 2, 28),
                "total_contract_value": 2_400_000.0,
                "recognized_revenue": 1_680_000.0,
            },
            {
                "sponsor_name": "Regeneron",
                "trial_id": "DUPIXENT-AD-2024",
                "stream": RevenueStream.PLATFORM_LICENSE,
                "status": ContractStatus.ACTIVE,
                "monthly_base_fee": 50_000.0,
                "per_patient_fee": 800.0,
                "per_enrollment_fee": 5_000.0,
                "start_date": date(2024, 6, 1),
                "end_date": date(2026, 5, 31),
                "total_contract_value": 1_800_000.0,
                "recognized_revenue": 1_050_000.0,
            },
            {
                "sponsor_name": "Regeneron",
                "trial_id": "LIBTAYO-NSCLC-2024",
                "stream": RevenueStream.PER_ENROLLMENT,
                "status": ContractStatus.ACTIVE,
                "monthly_base_fee": 25_000.0,
                "per_patient_fee": 1_500.0,
                "per_enrollment_fee": 8_000.0,
                "start_date": date(2024, 9, 1),
                "end_date": date(2026, 8, 31),
                "total_contract_value": 1_500_000.0,
                "recognized_revenue": 625_000.0,
            },
            {
                "sponsor_name": "Pfizer",
                "trial_id": "PFZ-ONC-2024",
                "stream": RevenueStream.DATA_ANALYTICS,
                "status": ContractStatus.ACTIVE,
                "monthly_base_fee": 40_000.0,
                "per_patient_fee": 1_000.0,
                "per_enrollment_fee": 5_500.0,
                "start_date": date(2024, 1, 1),
                "end_date": date(2025, 12, 31),
                "total_contract_value": 1_200_000.0,
                "recognized_revenue": 960_000.0,
            },
            {
                "sponsor_name": "Novartis",
                "trial_id": "NVS-CNS-2025",
                "stream": RevenueStream.INTEGRATION_FEES,
                "status": ContractStatus.ACTIVE,
                "monthly_base_fee": 30_000.0,
                "per_patient_fee": 900.0,
                "per_enrollment_fee": 4_500.0,
                "start_date": date(2025, 1, 1),
                "end_date": date(2026, 12, 31),
                "total_contract_value": 950_000.0,
                "recognized_revenue": 190_000.0,
            },
            {
                "sponsor_name": "AstraZeneca",
                "trial_id": "AZ-RESP-2025",
                "stream": RevenueStream.PROFESSIONAL_SERVICES,
                "status": ContractStatus.DRAFT,
                "monthly_base_fee": 15_000.0,
                "per_patient_fee": 500.0,
                "per_enrollment_fee": 3_000.0,
                "start_date": date(2025, 4, 1),
                "end_date": date(2027, 3, 31),
                "total_contract_value": 720_000.0,
                "recognized_revenue": 0.0,
            },
        ]

        for item in seed_contracts:
            contract_id = f"CTR-{uuid4().hex[:8].upper()}"
            remaining = item["total_contract_value"] - item["recognized_revenue"]
            self._contracts[contract_id] = RevenueContract(
                id=contract_id,
                sponsor_name=item["sponsor_name"],
                trial_id=item["trial_id"],
                stream=item["stream"],
                status=item["status"],
                monthly_base_fee=item["monthly_base_fee"],
                per_patient_fee=item["per_patient_fee"],
                per_enrollment_fee=item["per_enrollment_fee"],
                start_date=item["start_date"],
                end_date=item["end_date"],
                total_contract_value=item["total_contract_value"],
                recognized_revenue=item["recognized_revenue"],
                remaining_value=remaining,
                created_at=now,
            )

    def _populate_monthly_revenue(self) -> None:
        """Pre-populate 12 months of historical monthly revenue."""
        # Base revenue grows ~8% month-over-month
        base = 320_000.0
        growth = 1.08
        months = [
            "2025-01", "2025-02", "2025-03", "2025-04",
            "2025-05", "2025-06", "2025-07", "2025-08",
            "2025-09", "2025-10", "2025-11", "2025-12",
        ]

        stream_splits = {
            RevenueStream.PLATFORM_LICENSE.value: 0.30,
            RevenueStream.PER_PATIENT_SCREENING.value: 0.25,
            RevenueStream.PER_ENROLLMENT.value: 0.20,
            RevenueStream.DATA_ANALYTICS.value: 0.12,
            RevenueStream.INTEGRATION_FEES.value: 0.08,
            RevenueStream.PROFESSIONAL_SERVICES.value: 0.05,
        }

        sponsor_splits = {
            "Regeneron": 0.45,
            "Pfizer": 0.22,
            "Novartis": 0.18,
            "AstraZeneca": 0.15,
        }

        for i, month in enumerate(months):
            total = round(base * (growth ** i), 2)
            by_stream = {k: round(total * v, 2) for k, v in stream_splits.items()}
            by_sponsor = {k: round(total * v, 2) for k, v in sponsor_splits.items()}
            patient_vol = 180 + i * 25
            enrollment_vol = int(patient_vol * 0.12)

            self._monthly_revenue[month] = MonthlyRevenue(
                month=month,
                total=total,
                by_stream=by_stream,
                by_sponsor=by_sponsor,
                patient_volume=patient_vol,
                enrollment_volume=enrollment_vol,
            )

    def _populate_cohorts(self) -> None:
        """Pre-populate 4 quarterly cohort analysis records."""
        self._cohorts = [
            CohortAnalysis(
                cohort_month="2024-Q1",
                sponsors_acquired=2,
                total_contract_value=3_600_000.0,
                month_1_retention=1.0,
                month_3_retention=1.0,
                month_6_retention=1.0,
                month_12_retention=1.0,
                avg_revenue_per_sponsor=1_800_000.0,
                churn_rate=0.0,
            ),
            CohortAnalysis(
                cohort_month="2024-Q2",
                sponsors_acquired=1,
                total_contract_value=1_800_000.0,
                month_1_retention=1.0,
                month_3_retention=1.0,
                month_6_retention=1.0,
                month_12_retention=0.90,
                avg_revenue_per_sponsor=1_800_000.0,
                churn_rate=0.10,
            ),
            CohortAnalysis(
                cohort_month="2024-Q3",
                sponsors_acquired=1,
                total_contract_value=1_500_000.0,
                month_1_retention=1.0,
                month_3_retention=1.0,
                month_6_retention=0.95,
                month_12_retention=0.0,
                avg_revenue_per_sponsor=1_500_000.0,
                churn_rate=0.05,
            ),
            CohortAnalysis(
                cohort_month="2025-Q1",
                sponsors_acquired=2,
                total_contract_value=1_670_000.0,
                month_1_retention=1.0,
                month_3_retention=0.95,
                month_6_retention=0.0,
                month_12_retention=0.0,
                avg_revenue_per_sponsor=835_000.0,
                churn_rate=0.05,
            ),
        ]

    # ------------------------------------------------------------------
    # Contract CRUD
    # ------------------------------------------------------------------

    def create_contract(self, data: RevenueContractCreate) -> RevenueContract:
        """Create a new revenue contract."""
        contract_id = f"CTR-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        remaining = data.total_contract_value
        contract = RevenueContract(
            id=contract_id,
            sponsor_name=data.sponsor_name,
            trial_id=data.trial_id,
            stream=data.stream,
            status=data.status,
            monthly_base_fee=data.monthly_base_fee,
            per_patient_fee=data.per_patient_fee,
            per_enrollment_fee=data.per_enrollment_fee,
            start_date=data.start_date,
            end_date=data.end_date,
            total_contract_value=data.total_contract_value,
            recognized_revenue=0.0,
            remaining_value=remaining,
            created_at=now,
        )
        self._contracts[contract_id] = contract
        return contract

    def update_contract(self, contract_id: str, data: RevenueContractUpdate) -> RevenueContract | None:
        """Update an existing revenue contract. Returns None if not found."""
        contract = self._contracts.get(contract_id)
        if contract is None:
            return None

        updates: dict[str, Any] = {}
        for field_name in data.model_fields:
            value = getattr(data, field_name)
            if value is not None:
                updates[field_name] = value

        updated = contract.model_copy(update=updates)
        # Recalculate remaining value
        updated = updated.model_copy(update={
            "remaining_value": updated.total_contract_value - updated.recognized_revenue,
        })
        self._contracts[contract_id] = updated
        return updated

    def get_contract(self, contract_id: str) -> RevenueContract | None:
        """Return a single contract by ID."""
        return self._contracts.get(contract_id)

    def list_contracts(
        self,
        status: ContractStatus | None = None,
        sponsor: str | None = None,
    ) -> RevenueContractListResponse:
        """List contracts with optional status/sponsor filters."""
        result = list(self._contracts.values())
        if status is not None:
            result = [c for c in result if c.status == status]
        if sponsor is not None:
            result = [c for c in result if c.sponsor_name.lower() == sponsor.lower()]
        return RevenueContractListResponse(total=len(result), contracts=result)

    # ------------------------------------------------------------------
    # Monthly Revenue
    # ------------------------------------------------------------------

    def get_monthly_revenue(
        self,
        start_month: str | None = None,
        end_month: str | None = None,
    ) -> MonthlyRevenueListResponse:
        """Return historical monthly revenue, optionally filtered by range."""
        months = sorted(self._monthly_revenue.keys())
        if start_month:
            months = [m for m in months if m >= start_month]
        if end_month:
            months = [m for m in months if m <= end_month]
        records = [self._monthly_revenue[m] for m in months]
        return MonthlyRevenueListResponse(total=len(records), months=records)

    # ------------------------------------------------------------------
    # Revenue Metrics (SaaS KPIs)
    # ------------------------------------------------------------------

    def get_revenue_metrics(self) -> RevenueMetrics:
        """Calculate SaaS revenue metrics from current data."""
        sorted_months = sorted(self._monthly_revenue.keys())
        if len(sorted_months) < 2:
            return RevenueMetrics()

        latest = self._monthly_revenue[sorted_months[-1]]
        previous = self._monthly_revenue[sorted_months[-2]]

        mrr = latest.total
        arr = mrr * 12.0

        # MRR growth rate
        if previous.total > 0:
            mrr_growth = ((mrr - previous.total) / previous.total) * 100.0
        else:
            mrr_growth = 0.0

        # Active sponsor count
        active_sponsors = len({
            c.sponsor_name for c in self._contracts.values()
            if c.status == ContractStatus.ACTIVE
        })

        # ARPU
        arpu = mrr / active_sponsors if active_sponsors > 0 else 0.0

        # NRR (simplified: compare same-sponsor revenue month-over-month)
        if previous.total > 0:
            nrr = (mrr / previous.total) * 100.0
        else:
            nrr = 100.0

        # Gross margin
        cogs = mrr * self.COGS_RATE
        gross_margin = ((mrr - cogs) / mrr) * 100.0 if mrr > 0 else 0.0

        # LTV & CAC
        monthly_churn = 1.0 / self.AVG_SPONSOR_LIFETIME_MONTHS
        ltv = arpu * (1.0 / monthly_churn) if monthly_churn > 0 else 0.0
        ltv_cac = ltv / self.CAC if self.CAC > 0 else 0.0
        payback = self.CAC / arpu if arpu > 0 else 0.0

        # Revenue per employee
        rpe = (arr / self.EMPLOYEE_COUNT) if self.EMPLOYEE_COUNT > 0 else 0.0

        return RevenueMetrics(
            mrr=round(mrr, 2),
            arr=round(arr, 2),
            mrr_growth_rate_pct=round(mrr_growth, 2),
            net_revenue_retention_pct=round(nrr, 2),
            gross_margin_pct=round(gross_margin, 2),
            arpu=round(arpu, 2),
            ltv=round(ltv, 2),
            cac=self.CAC,
            ltv_cac_ratio=round(ltv_cac, 2),
            payback_period_months=round(payback, 2),
            revenue_per_employee=round(rpe, 2),
        )

    # ------------------------------------------------------------------
    # Cohort Analysis
    # ------------------------------------------------------------------

    def get_cohort_analysis(self) -> CohortAnalysisListResponse:
        """Return sponsor cohort retention analysis."""
        return CohortAnalysisListResponse(
            total=len(self._cohorts),
            cohorts=list(self._cohorts),
        )

    # ------------------------------------------------------------------
    # Revenue Forecasting
    # ------------------------------------------------------------------

    def forecast_revenue(self, months_ahead: int = 6) -> RevenueForecastListResponse:
        """Forecast revenue using simple linear regression.

        Uses the historical monthly revenue data to fit a trend line
        and project forward with confidence intervals.
        """
        sorted_months = sorted(self._monthly_revenue.keys())
        if len(sorted_months) < 2:
            return RevenueForecastListResponse()

        # Build x (index), y (total) arrays
        y_values = [self._monthly_revenue[m].total for m in sorted_months]
        n = len(y_values)
        x_values = list(range(n))

        # Simple linear regression: y = a + bx
        x_mean = statistics.mean(x_values)
        y_mean = statistics.mean(y_values)

        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values))
        denominator = sum((x - x_mean) ** 2 for x in x_values)

        if denominator == 0:
            slope = 0.0
        else:
            slope = numerator / denominator
        intercept = y_mean - slope * x_mean

        # Residual standard error
        residuals = [y - (intercept + slope * x) for x, y in zip(x_values, y_values)]
        if n > 2:
            rse = math.sqrt(sum(r ** 2 for r in residuals) / (n - 2))
        else:
            rse = 0.0

        # Generate forecast months
        last_month = sorted_months[-1]
        year, month_num = int(last_month[:4]), int(last_month[5:7])

        forecasts: list[RevenueForecast] = []
        for i in range(1, months_ahead + 1):
            future_x = n + i - 1
            projected = intercept + slope * future_x
            # Wider confidence interval for farther-out months
            margin = 1.96 * rse * math.sqrt(1 + 1 / n + (future_x - x_mean) ** 2 / denominator) if denominator > 0 else 0.0

            # Compute future month string
            fm = month_num + i
            fy = year + (fm - 1) // 12
            fm = ((fm - 1) % 12) + 1
            month_str = f"{fy:04d}-{fm:02d}"

            forecasts.append(RevenueForecast(
                month=month_str,
                projected_revenue=round(max(projected, 0.0), 2),
                confidence_low=round(max(projected - margin, 0.0), 2),
                confidence_high=round(projected + margin, 2),
                assumptions=[
                    "Linear trend extrapolation from 12-month history",
                    f"Slope: ${slope:,.0f}/month",
                    f"Current MRR growth trajectory maintained",
                    f"Active sponsor count remains stable",
                ],
            ))

        return RevenueForecastListResponse(total=len(forecasts), forecasts=forecasts)

    # ------------------------------------------------------------------
    # Financial Report
    # ------------------------------------------------------------------

    def generate_financial_report(
        self,
        report_type: ReportType = ReportType.MONTHLY,
        period: str | None = None,
    ) -> FinancialReport:
        """Generate a P&L-style financial report.

        For MONTHLY, period should be YYYY-MM.
        For QUARTERLY, period should be YYYY-QN.
        For ANNUAL, period should be YYYY.
        """
        sorted_months = sorted(self._monthly_revenue.keys())

        if report_type == ReportType.MONTHLY:
            target_month = period or (sorted_months[-1] if sorted_months else "2025-12")
            rev_data = self._monthly_revenue.get(target_month)
            total_revenue = rev_data.total if rev_data else 0.0
            period_label = target_month

        elif report_type == ReportType.QUARTERLY:
            # Parse YYYY-QN
            if period and "-Q" in period:
                year_str, q_str = period.split("-Q")
                target_year = int(year_str)
                quarter = int(q_str)
            else:
                target_year = 2025
                quarter = 4
            q_months = [
                f"{target_year:04d}-{m:02d}"
                for m in range((quarter - 1) * 3 + 1, quarter * 3 + 1)
            ]
            total_revenue = sum(
                self._monthly_revenue[m].total
                for m in q_months
                if m in self._monthly_revenue
            )
            period_label = period or f"{target_year}-Q{quarter}"

        else:  # ANNUAL
            target_year = int(period) if period else 2025
            year_months = [m for m in sorted_months if m.startswith(str(target_year))]
            total_revenue = sum(self._monthly_revenue[m].total for m in year_months)
            period_label = str(target_year)

        # Cost calculations
        if report_type == ReportType.MONTHLY:
            months_in_period = 1
        elif report_type == ReportType.QUARTERLY:
            months_in_period = 3
        else:
            months_in_period = 12

        total_costs = round(total_revenue * self.COGS_RATE, 2)
        gross_profit = round(total_revenue - total_costs, 2)
        gross_margin = round((gross_profit / total_revenue) * 100, 2) if total_revenue > 0 else 0.0
        opex = round(self.MONTHLY_OPERATING_EXPENSES * months_in_period, 2)
        ebitda = round(gross_profit - opex, 2)
        ebitda_margin = round((ebitda / total_revenue) * 100, 2) if total_revenue > 0 else 0.0

        # MRR from latest month in period
        latest_month = sorted_months[-1] if sorted_months else None
        mrr = self._monthly_revenue[latest_month].total if latest_month else 0.0

        # Previous month for growth
        if len(sorted_months) >= 2:
            prev_month = self._monthly_revenue[sorted_months[-2]].total
            mrr_growth = round(((mrr - prev_month) / prev_month) * 100, 2) if prev_month > 0 else 0.0
        else:
            mrr_growth = 0.0

        active_sponsors = len({
            c.sponsor_name for c in self._contracts.values()
            if c.status == ContractStatus.ACTIVE
        })
        arpu = round(mrr / active_sponsors, 2) if active_sponsors > 0 else 0.0

        return FinancialReport(
            report_type=report_type,
            period=period_label,
            total_revenue=round(total_revenue, 2),
            total_costs=total_costs,
            gross_profit=gross_profit,
            gross_margin_pct=gross_margin,
            operating_expenses=opex,
            ebitda=ebitda,
            ebitda_margin_pct=ebitda_margin,
            mrr=round(mrr, 2),
            arr=round(mrr * 12, 2),
            mrr_growth_rate=mrr_growth,
            net_revenue_retention=round(mrr / self._monthly_revenue[sorted_months[-2]].total * 100, 2) if len(sorted_months) >= 2 and self._monthly_revenue[sorted_months[-2]].total > 0 else 100.0,
            customer_count=active_sponsors,
            arpu=arpu,
        )

    # ------------------------------------------------------------------
    # Revenue Breakdowns
    # ------------------------------------------------------------------

    def get_revenue_by_stream(self) -> RevenueByStreamResponse:
        """Aggregate revenue by stream across all months."""
        stream_totals: dict[str, float] = {}
        grand_total = 0.0

        for rev in self._monthly_revenue.values():
            grand_total += rev.total
            for stream_key, amount in rev.by_stream.items():
                stream_totals[stream_key] = stream_totals.get(stream_key, 0.0) + amount

        items = []
        for stream in RevenueStream:
            total = stream_totals.get(stream.value, 0.0)
            pct = round((total / grand_total) * 100, 2) if grand_total > 0 else 0.0
            items.append(RevenueByStreamItem(
                stream=stream,
                total=round(total, 2),
                percentage=pct,
            ))

        return RevenueByStreamResponse(
            total_revenue=round(grand_total, 2),
            streams=items,
        )

    def get_revenue_by_sponsor(self) -> RevenueBySponsorResponse:
        """Aggregate revenue by sponsor across all months."""
        sponsor_totals: dict[str, float] = {}
        grand_total = 0.0

        for rev in self._monthly_revenue.values():
            grand_total += rev.total
            for sponsor, amount in rev.by_sponsor.items():
                sponsor_totals[sponsor] = sponsor_totals.get(sponsor, 0.0) + amount

        items = []
        for sponsor, total in sorted(sponsor_totals.items(), key=lambda x: -x[1]):
            pct = round((total / grand_total) * 100, 2) if grand_total > 0 else 0.0
            items.append(RevenueBySponsorItem(
                sponsor_name=sponsor,
                total=round(total, 2),
                percentage=pct,
            ))

        return RevenueBySponsorResponse(
            total_revenue=round(grand_total, 2),
            sponsors=items,
        )

    # ------------------------------------------------------------------
    # Revenue Recognition
    # ------------------------------------------------------------------

    def recognize_revenue(
        self,
        contract_id: str,
        amount: float,
        month: str,
    ) -> RevenueRecognitionResponse | None:
        """Recognize revenue for a contract in a given month.

        Returns None if contract not found.
        """
        contract = self._contracts.get(contract_id)
        if contract is None:
            return None

        new_recognized = contract.recognized_revenue + amount
        new_remaining = contract.total_contract_value - new_recognized
        updated = contract.model_copy(update={
            "recognized_revenue": round(new_recognized, 2),
            "remaining_value": round(max(new_remaining, 0.0), 2),
        })
        self._contracts[contract_id] = updated

        # Also update monthly revenue if month exists
        if month in self._monthly_revenue:
            mr = self._monthly_revenue[month]
            updated_mr = mr.model_copy(update={
                "total": round(mr.total + amount, 2),
            })
            self._monthly_revenue[month] = updated_mr

        return RevenueRecognitionResponse(
            contract_id=contract_id,
            amount_recognized=amount,
            month=month,
            total_recognized=round(new_recognized, 2),
            remaining_value=round(max(new_remaining, 0.0), 2),
        )

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return service stats for health checks."""
        return {
            "contract_count": len(self._contracts),
            "monthly_revenue_months": len(self._monthly_revenue),
            "cohort_count": len(self._cohorts),
            "active_contracts": len([
                c for c in self._contracts.values()
                if c.status == ContractStatus.ACTIVE
            ]),
        }
