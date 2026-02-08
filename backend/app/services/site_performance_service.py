"""Clinical Site Performance Analytics Service (CMO-8).

Provides site performance monitoring, benchmarking, scoring, and
recommendations for multi-site clinical trial operations.

Usage:
    from app.services.site_performance_service import (
        get_site_performance_service,
    )

    svc = get_site_performance_service()
    site = svc.get_site("site-001")
    scores = svc.calculate_performance_scores()
"""

from __future__ import annotations

import logging
import math
import random
import threading
from datetime import datetime, timezone
from typing import Any

from app.schemas.site_performance import (
    ClinicalSite,
    EnrollmentTrendResponse,
    MetricComparison,
    MonthlyEnrollment,
    Quartile,
    RecommendationType,
    SiteBenchmark,
    SiteBenchmarksResponse,
    SiteComparison,
    SiteListResponse,
    SiteMetrics,
    SitePerformanceScore,
    SiteRecommendation,
    SiteRecommendationsResponse,
    SiteScoresResponse,
    SiteStatus,
    UnderperformersResponse,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Regeneron trial IDs (matching trial_eligibility_service.py seed data)
# ---------------------------------------------------------------------------
_TRIAL_EYLEA_HD = "00000000-de00-0001-0000-000000000001"
_TRIAL_DUPIXENT = "00000000-de00-0002-0000-000000000002"
_TRIAL_LIBTAYO = "00000000-de00-0003-0000-000000000003"


class SitePerformanceService:
    """In-memory clinical site performance analytics engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._sites: dict[str, ClinicalSite] = {}
        self._lock = threading.Lock()
        self._seed_sites()

    # ------------------------------------------------------------------
    # Seed data
    # ------------------------------------------------------------------

    def _seed_sites(self) -> None:
        """Pre-populate 15 clinical sites across US, EU, and Asia."""
        now = datetime.now(timezone.utc).isoformat()
        seed_data: list[dict[str, Any]] = [
            # --- Top performers ---
            {
                "id": "site-001",
                "name": "Johns Hopkins Oncology Center",
                "institution": "Johns Hopkins Medicine",
                "location": {"city": "Baltimore", "state": "MD", "country": "US"},
                "pi_name": "Dr. Sarah Chen",
                "status": SiteStatus.ENROLLING,
                "activated_date": "2024-01-15",
                "trials": [_TRIAL_EYLEA_HD, _TRIAL_LIBTAYO],
                "total_screened": 245,
                "total_enrolled": 178,
                "screen_failure_rate": 0.27,
                "enrollment_rate_per_month": 14.8,
                "avg_time_to_first_patient_days": 18.0,
                "avg_query_resolution_days": 1.2,
                "protocol_deviation_count": 2,
            },
            {
                "id": "site-002",
                "name": "Mayo Clinic Rochester",
                "institution": "Mayo Clinic",
                "location": {"city": "Rochester", "state": "MN", "country": "US"},
                "pi_name": "Dr. James Wilson",
                "status": SiteStatus.ENROLLING,
                "activated_date": "2024-02-01",
                "trials": [_TRIAL_DUPIXENT, _TRIAL_LIBTAYO],
                "total_screened": 198,
                "total_enrolled": 152,
                "screen_failure_rate": 0.23,
                "enrollment_rate_per_month": 12.7,
                "avg_time_to_first_patient_days": 21.0,
                "avg_query_resolution_days": 1.5,
                "protocol_deviation_count": 1,
            },
            {
                "id": "site-003",
                "name": "Charite Universitaetsmedizin Berlin",
                "institution": "Charite Berlin",
                "location": {"city": "Berlin", "state": "Berlin", "country": "DE"},
                "pi_name": "Prof. Klaus Mueller",
                "status": SiteStatus.ENROLLING,
                "activated_date": "2024-01-20",
                "trials": [_TRIAL_EYLEA_HD, _TRIAL_DUPIXENT],
                "total_screened": 210,
                "total_enrolled": 155,
                "screen_failure_rate": 0.26,
                "enrollment_rate_per_month": 12.9,
                "avg_time_to_first_patient_days": 22.0,
                "avg_query_resolution_days": 1.8,
                "protocol_deviation_count": 3,
            },
            # --- Average performers ---
            {
                "id": "site-004",
                "name": "Cleveland Clinic Foundation",
                "institution": "Cleveland Clinic",
                "location": {"city": "Cleveland", "state": "OH", "country": "US"},
                "pi_name": "Dr. Michael Park",
                "status": SiteStatus.ACTIVE,
                "activated_date": "2024-03-10",
                "trials": [_TRIAL_EYLEA_HD],
                "total_screened": 130,
                "total_enrolled": 78,
                "screen_failure_rate": 0.40,
                "enrollment_rate_per_month": 7.8,
                "avg_time_to_first_patient_days": 35.0,
                "avg_query_resolution_days": 3.2,
                "protocol_deviation_count": 5,
            },
            {
                "id": "site-005",
                "name": "University College London Hospital",
                "institution": "UCL Hospitals NHS Trust",
                "location": {"city": "London", "state": "England", "country": "GB"},
                "pi_name": "Prof. Emma Thompson",
                "status": SiteStatus.ENROLLING,
                "activated_date": "2024-02-15",
                "trials": [_TRIAL_DUPIXENT, _TRIAL_LIBTAYO],
                "total_screened": 155,
                "total_enrolled": 89,
                "screen_failure_rate": 0.43,
                "enrollment_rate_per_month": 7.4,
                "avg_time_to_first_patient_days": 30.0,
                "avg_query_resolution_days": 2.8,
                "protocol_deviation_count": 4,
            },
            {
                "id": "site-006",
                "name": "Tokyo University Hospital",
                "institution": "University of Tokyo",
                "location": {"city": "Tokyo", "state": "Tokyo", "country": "JP"},
                "pi_name": "Dr. Yuki Tanaka",
                "status": SiteStatus.ENROLLING,
                "activated_date": "2024-03-01",
                "trials": [_TRIAL_EYLEA_HD],
                "total_screened": 142,
                "total_enrolled": 82,
                "screen_failure_rate": 0.42,
                "enrollment_rate_per_month": 6.8,
                "avg_time_to_first_patient_days": 28.0,
                "avg_query_resolution_days": 2.5,
                "protocol_deviation_count": 3,
            },
            {
                "id": "site-007",
                "name": "Hospital Universitario La Paz",
                "institution": "La Paz University Hospital",
                "location": {"city": "Madrid", "state": "Madrid", "country": "ES"},
                "pi_name": "Dr. Carlos Garcia",
                "status": SiteStatus.ACTIVE,
                "activated_date": "2024-04-01",
                "trials": [_TRIAL_DUPIXENT],
                "total_screened": 110,
                "total_enrolled": 62,
                "screen_failure_rate": 0.44,
                "enrollment_rate_per_month": 6.2,
                "avg_time_to_first_patient_days": 33.0,
                "avg_query_resolution_days": 3.0,
                "protocol_deviation_count": 6,
            },
            {
                "id": "site-008",
                "name": "Samsung Medical Center",
                "institution": "Samsung Medical Center",
                "location": {"city": "Seoul", "state": "Seoul", "country": "KR"},
                "pi_name": "Dr. Min-Jun Kim",
                "status": SiteStatus.ENROLLING,
                "activated_date": "2024-02-20",
                "trials": [_TRIAL_EYLEA_HD, _TRIAL_LIBTAYO],
                "total_screened": 160,
                "total_enrolled": 95,
                "screen_failure_rate": 0.41,
                "enrollment_rate_per_month": 7.9,
                "avg_time_to_first_patient_days": 25.0,
                "avg_query_resolution_days": 2.2,
                "protocol_deviation_count": 4,
            },
            # --- Underperformers ---
            {
                "id": "site-009",
                "name": "Regional Medical Center Dallas",
                "institution": "Dallas Regional Health",
                "location": {"city": "Dallas", "state": "TX", "country": "US"},
                "pi_name": "Dr. Robert Lee",
                "status": SiteStatus.ACTIVE,
                "activated_date": "2024-05-01",
                "trials": [_TRIAL_DUPIXENT],
                "total_screened": 85,
                "total_enrolled": 28,
                "screen_failure_rate": 0.67,
                "enrollment_rate_per_month": 3.5,
                "avg_time_to_first_patient_days": 55.0,
                "avg_query_resolution_days": 6.5,
                "protocol_deviation_count": 12,
            },
            {
                "id": "site-010",
                "name": "Community Hospital of the Monterey Peninsula",
                "institution": "Montage Health",
                "location": {"city": "Monterey", "state": "CA", "country": "US"},
                "pi_name": "Dr. Lisa Wang",
                "status": SiteStatus.PAUSED,
                "activated_date": "2024-04-15",
                "trials": [_TRIAL_LIBTAYO],
                "total_screened": 45,
                "total_enrolled": 12,
                "screen_failure_rate": 0.73,
                "enrollment_rate_per_month": 1.5,
                "avg_time_to_first_patient_days": 72.0,
                "avg_query_resolution_days": 8.0,
                "protocol_deviation_count": 15,
            },
            {
                "id": "site-011",
                "name": "Hopital Pitie-Salpetriere",
                "institution": "AP-HP",
                "location": {"city": "Paris", "state": "Ile-de-France", "country": "FR"},
                "pi_name": "Dr. Pierre Dupont",
                "status": SiteStatus.ACTIVE,
                "activated_date": "2024-06-01",
                "trials": [_TRIAL_EYLEA_HD],
                "total_screened": 60,
                "total_enrolled": 22,
                "screen_failure_rate": 0.63,
                "enrollment_rate_per_month": 2.8,
                "avg_time_to_first_patient_days": 48.0,
                "avg_query_resolution_days": 5.5,
                "protocol_deviation_count": 9,
            },
            {
                "id": "site-012",
                "name": "Apollo Hospitals Chennai",
                "institution": "Apollo Hospitals Group",
                "location": {"city": "Chennai", "state": "Tamil Nadu", "country": "IN"},
                "pi_name": "Dr. Priya Sharma",
                "status": SiteStatus.ENROLLING,
                "activated_date": "2024-03-15",
                "trials": [_TRIAL_DUPIXENT, _TRIAL_EYLEA_HD],
                "total_screened": 175,
                "total_enrolled": 105,
                "screen_failure_rate": 0.40,
                "enrollment_rate_per_month": 8.8,
                "avg_time_to_first_patient_days": 26.0,
                "avg_query_resolution_days": 2.0,
                "protocol_deviation_count": 5,
            },
            # --- Edge status sites ---
            {
                "id": "site-013",
                "name": "Peking University First Hospital",
                "institution": "Peking University",
                "location": {"city": "Beijing", "state": "Beijing", "country": "CN"},
                "pi_name": "Dr. Wei Zhang",
                "status": SiteStatus.PENDING_ACTIVATION,
                "activated_date": None,
                "trials": [_TRIAL_LIBTAYO],
                "total_screened": 0,
                "total_enrolled": 0,
                "screen_failure_rate": 0.0,
                "enrollment_rate_per_month": 0.0,
                "avg_time_to_first_patient_days": None,
                "avg_query_resolution_days": None,
                "protocol_deviation_count": 0,
            },
            {
                "id": "site-014",
                "name": "Massachusetts General Hospital",
                "institution": "Mass General Brigham",
                "location": {"city": "Boston", "state": "MA", "country": "US"},
                "pi_name": "Dr. David Martinez",
                "status": SiteStatus.CLOSED,
                "activated_date": "2023-09-01",
                "trials": [_TRIAL_DUPIXENT],
                "total_screened": 220,
                "total_enrolled": 165,
                "screen_failure_rate": 0.25,
                "enrollment_rate_per_month": 10.3,
                "avg_time_to_first_patient_days": 20.0,
                "avg_query_resolution_days": 1.6,
                "protocol_deviation_count": 2,
            },
            {
                "id": "site-015",
                "name": "Sydney Royal Prince Alfred Hospital",
                "institution": "Sydney Local Health District",
                "location": {"city": "Sydney", "state": "NSW", "country": "AU"},
                "pi_name": "Dr. Olivia Brown",
                "status": SiteStatus.ENROLLING,
                "activated_date": "2024-04-01",
                "trials": [_TRIAL_EYLEA_HD, _TRIAL_LIBTAYO],
                "total_screened": 120,
                "total_enrolled": 72,
                "screen_failure_rate": 0.40,
                "enrollment_rate_per_month": 7.2,
                "avg_time_to_first_patient_days": 32.0,
                "avg_query_resolution_days": 2.8,
                "protocol_deviation_count": 4,
            },
        ]

        with self._lock:
            for sd in seed_data:
                site = ClinicalSite(created_at=now, **sd)
                self._sites[site.id] = site

        logger.info("Seeded %d clinical sites for site performance analytics", len(seed_data))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def get_site(self, site_id: str) -> ClinicalSite | None:
        """Return a single site by ID, or ``None`` if not found."""
        return self._sites.get(site_id)

    def list_sites(
        self,
        *,
        status: SiteStatus | str | None = None,
        country: str | None = None,
        trial_id: str | None = None,
    ) -> SiteListResponse:
        """List sites with optional filters."""
        results = list(self._sites.values())

        if status is not None:
            if isinstance(status, str):
                status = SiteStatus(status)
            results = [s for s in results if s.status == status]

        if country is not None:
            country_upper = country.upper()
            results = [s for s in results if s.location.get("country", "").upper() == country_upper]

        if trial_id is not None:
            results = [s for s in results if trial_id in s.trials]

        return SiteListResponse(sites=results, total=len(results))

    # ------------------------------------------------------------------
    # Performance scoring
    # ------------------------------------------------------------------

    def calculate_performance_scores(self) -> SiteScoresResponse:
        """Score all sites on enrollment, quality, timeliness, compliance.

        Scoring weights:
            - Enrollment  40%
            - Quality     25%
            - Timeliness  20%
            - Compliance  15%
        """
        now = datetime.now(timezone.utc).isoformat()
        scorable = [s for s in self._sites.values() if s.total_screened > 0]

        if not scorable:
            return SiteScoresResponse(scores=[], calculated_at=now)

        raw_scores: list[dict[str, Any]] = []
        for site in scorable:
            enrollment = self._enrollment_score(site)
            quality = self._quality_score(site)
            timeliness = self._timeliness_score(site)
            compliance = self._compliance_score(site)
            overall = (
                enrollment * 0.40
                + quality * 0.25
                + timeliness * 0.20
                + compliance * 0.15
            )
            raw_scores.append({
                "site_id": site.id,
                "enrollment_score": round(enrollment, 1),
                "quality_score": round(quality, 1),
                "timeliness_score": round(timeliness, 1),
                "compliance_score": round(compliance, 1),
                "overall_score": round(overall, 1),
            })

        # Sort by overall descending to assign rank
        raw_scores.sort(key=lambda x: x["overall_score"], reverse=True)
        n = len(raw_scores)

        scores: list[SitePerformanceScore] = []
        for rank_idx, rs in enumerate(raw_scores, start=1):
            quartile = self._rank_to_quartile(rank_idx, n)
            scores.append(SitePerformanceScore(
                rank=rank_idx,
                quartile=quartile,
                calculated_at=now,
                **rs,
            ))

        return SiteScoresResponse(scores=scores, calculated_at=now)

    # ------------------------------------------------------------------
    # Benchmarks
    # ------------------------------------------------------------------

    def get_site_benchmarks(self, site_id: str) -> SiteBenchmarksResponse | None:
        """Compare a site against cohort benchmarks (p25/p50/p75/p90)."""
        site = self._sites.get(site_id)
        if site is None:
            return None

        metrics_to_benchmark = [
            ("enrollment_rate_per_month", [s.enrollment_rate_per_month for s in self._sites.values() if s.total_screened > 0]),
            ("screen_failure_rate", [s.screen_failure_rate for s in self._sites.values() if s.total_screened > 0]),
            ("total_enrolled", [float(s.total_enrolled) for s in self._sites.values() if s.total_screened > 0]),
            ("avg_query_resolution_days", [s.avg_query_resolution_days for s in self._sites.values() if s.avg_query_resolution_days is not None]),
            ("protocol_deviation_count", [float(s.protocol_deviation_count) for s in self._sites.values() if s.total_screened > 0]),
        ]

        benchmarks: list[SiteBenchmark] = []
        for metric_name, values in metrics_to_benchmark:
            if not values:
                continue
            site_value = self._get_metric_value(site, metric_name)
            if site_value is None:
                continue

            sorted_vals = sorted(values)
            bm = SiteBenchmark(
                metric_name=metric_name,
                p25=self._percentile(sorted_vals, 25),
                p50=self._percentile(sorted_vals, 50),
                p75=self._percentile(sorted_vals, 75),
                p90=self._percentile(sorted_vals, 90),
                site_value=site_value,
                percentile_rank=self._compute_percentile_rank(sorted_vals, site_value),
            )
            benchmarks.append(bm)

        return SiteBenchmarksResponse(site_id=site_id, benchmarks=benchmarks)

    # ------------------------------------------------------------------
    # Head-to-head comparison
    # ------------------------------------------------------------------

    def compare_sites(self, site_a_id: str, site_b_id: str) -> SiteComparison | None:
        """Compare two sites across key metrics."""
        site_a = self._sites.get(site_a_id)
        site_b = self._sites.get(site_b_id)
        if site_a is None or site_b is None:
            return None

        metric_names = [
            "enrollment_rate_per_month",
            "screen_failure_rate",
            "total_enrolled",
            "avg_query_resolution_days",
            "protocol_deviation_count",
        ]
        # For these metrics, lower is better
        lower_is_better = {"screen_failure_rate", "avg_query_resolution_days", "protocol_deviation_count"}

        comparisons: list[MetricComparison] = []
        for metric in metric_names:
            val_a = self._get_metric_value(site_a, metric) or 0.0
            val_b = self._get_metric_value(site_b, metric) or 0.0
            diff = round(val_a - val_b, 4)

            if abs(diff) < 1e-9:
                better = "tie"
            elif metric in lower_is_better:
                better = "a" if val_a < val_b else "b"
            else:
                better = "a" if val_a > val_b else "b"

            comparisons.append(MetricComparison(
                metric=metric,
                site_a_value=val_a,
                site_b_value=val_b,
                difference=diff,
                better=better,
            ))

        return SiteComparison(
            site_a_id=site_a_id,
            site_b_id=site_b_id,
            metrics_comparison=comparisons,
        )

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    def get_recommendations(self, site_id: str) -> SiteRecommendationsResponse | None:
        """Auto-generate recommendations based on performance."""
        site = self._sites.get(site_id)
        if site is None:
            return None

        recs: list[SiteRecommendation] = []

        # High screen failure rate
        if site.screen_failure_rate > 0.60:
            recs.append(SiteRecommendation(
                site_id=site_id,
                recommendation_type=RecommendationType.TRAINING_NEEDED,
                rationale=(
                    f"Screen failure rate of {site.screen_failure_rate:.0%} is above 60% threshold. "
                    "Recommend training site coordinators on patient pre-screening criteria."
                ),
                priority="high",
            ))

        # Low enrollment rate
        if site.enrollment_rate_per_month < 4.0 and site.total_screened > 0:
            recs.append(SiteRecommendation(
                site_id=site_id,
                recommendation_type=RecommendationType.INCREASE_CAPACITY,
                rationale=(
                    f"Enrollment rate of {site.enrollment_rate_per_month:.1f}/month is below 4.0 target. "
                    "Consider increasing recruitment resources or adding referral channels."
                ),
                priority="high",
            ))

        # Many protocol deviations
        if site.protocol_deviation_count > 10:
            recs.append(SiteRecommendation(
                site_id=site_id,
                recommendation_type=RecommendationType.PAUSE_ENROLLMENT,
                rationale=(
                    f"Site has {site.protocol_deviation_count} protocol deviations. "
                    "Consider pausing enrollment for corrective action."
                ),
                priority="high",
            ))

        # Strong performer with few trials
        if (
            site.enrollment_rate_per_month > 10.0
            and site.screen_failure_rate < 0.35
            and len(site.trials) < 3
        ):
            recs.append(SiteRecommendation(
                site_id=site_id,
                recommendation_type=RecommendationType.EXPAND_TRIALS,
                rationale=(
                    "Site is a top performer with capacity for additional trials. "
                    "Consider adding more study protocols."
                ),
                priority="medium",
            ))

        # Very poor overall
        if (
            site.screen_failure_rate > 0.70
            and site.enrollment_rate_per_month < 2.0
            and site.protocol_deviation_count > 10
        ):
            recs.append(SiteRecommendation(
                site_id=site_id,
                recommendation_type=RecommendationType.CLOSE,
                rationale=(
                    "Site has critically poor performance across all metrics. "
                    "Consider closing and redistributing patients."
                ),
                priority="high",
            ))

        # If no issues found, give a positive note
        if not recs:
            recs.append(SiteRecommendation(
                site_id=site_id,
                recommendation_type=RecommendationType.EXPAND_TRIALS,
                rationale="Site is performing within acceptable parameters. No corrective actions needed.",
                priority="low",
            ))

        return SiteRecommendationsResponse(site_id=site_id, recommendations=recs)

    # ------------------------------------------------------------------
    # Underperformers
    # ------------------------------------------------------------------

    def get_underperformers(self, threshold: float = 50.0) -> UnderperformersResponse:
        """Return sites with overall score below *threshold*."""
        scores_resp = self.calculate_performance_scores()
        under_ids = {s.site_id for s in scores_resp.scores if s.overall_score < threshold}
        under_sites = [s for s in self._sites.values() if s.id in under_ids]
        return UnderperformersResponse(
            threshold=threshold,
            sites=under_sites,
            total=len(under_sites),
        )

    # ------------------------------------------------------------------
    # Aggregate metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> SiteMetrics:
        """Return program-wide aggregate site metrics."""
        all_sites = list(self._sites.values())
        active_statuses = {SiteStatus.ACTIVE, SiteStatus.ENROLLING}
        active = [s for s in all_sites if s.status in active_statuses]

        by_country: dict[str, int] = {}
        for s in all_sites:
            country = s.location.get("country", "Unknown")
            by_country[country] = by_country.get(country, 0) + 1

        enrollment_rates = [s.enrollment_rate_per_month for s in all_sites if s.total_screened > 0]
        sfr_values = [s.screen_failure_rate for s in all_sites if s.total_screened > 0]

        # Top / under performers based on scores
        scores_resp = self.calculate_performance_scores()
        top_ids = [s.site_id for s in scores_resp.scores if s.quartile == Quartile.Q1]
        under_ids = [s.site_id for s in scores_resp.scores if s.quartile == Quartile.Q4]

        return SiteMetrics(
            total_sites=len(all_sites),
            active_sites=len(active),
            avg_enrollment_rate=round(sum(enrollment_rates) / len(enrollment_rates), 2) if enrollment_rates else 0.0,
            avg_screen_failure_rate=round(sum(sfr_values) / len(sfr_values), 2) if sfr_values else 0.0,
            top_performers=top_ids,
            underperformers=under_ids,
            by_country=by_country,
            total_enrolled_all_sites=sum(s.total_enrolled for s in all_sites),
        )

    # ------------------------------------------------------------------
    # Enrollment trends
    # ------------------------------------------------------------------

    def get_enrollment_trends(self, site_id: str, months: int = 6) -> EnrollmentTrendResponse | None:
        """Return monthly enrollment trend for a site (synthetic)."""
        site = self._sites.get(site_id)
        if site is None:
            return None

        # Generate plausible synthetic monthly data based on the site's rate
        rng = random.Random(hash(site_id))
        rate = site.enrollment_rate_per_month
        trend: list[MonthlyEnrollment] = []
        now = datetime.now(timezone.utc)

        for i in range(months, 0, -1):
            month_num = ((now.month - i - 1) % 12) + 1
            year = now.year if now.month - i > 0 else now.year - 1
            label = f"{year}-{month_num:02d}"
            enrolled = max(0, int(rate + rng.gauss(0, rate * 0.25)))
            screened = max(enrolled, int(enrolled / max(1.0 - site.screen_failure_rate, 0.1)))
            trend.append(MonthlyEnrollment(month=label, enrolled=enrolled, screened=screened))

        return EnrollmentTrendResponse(site_id=site_id, months=trend)

    # ------------------------------------------------------------------
    # Housekeeping
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all sites and re-seed."""
        with self._lock:
            self._sites.clear()
        self._seed_sites()

    def get_stats(self) -> dict[str, Any]:
        """Return service stats for health check."""
        return {
            "total_sites": len(self._sites),
            "active_sites": sum(
                1 for s in self._sites.values()
                if s.status in {SiteStatus.ACTIVE, SiteStatus.ENROLLING}
            ),
        }

    # ------------------------------------------------------------------
    # Private scoring helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _enrollment_score(site: ClinicalSite) -> float:
        """Score enrollment (0-100). Higher enrollment rate = higher score."""
        # Baseline: 15 patients/month is perfect
        return min(100.0, (site.enrollment_rate_per_month / 15.0) * 100.0)

    @staticmethod
    def _quality_score(site: ClinicalSite) -> float:
        """Score quality (0-100). Lower screen failure = higher quality."""
        return max(0.0, (1.0 - site.screen_failure_rate) * 100.0)

    @staticmethod
    def _timeliness_score(site: ClinicalSite) -> float:
        """Score timeliness (0-100). Lower time to first patient = higher."""
        if site.avg_time_to_first_patient_days is None:
            return 50.0  # neutral for pending sites
        # 14 days = perfect, 90+ days = 0
        days = site.avg_time_to_first_patient_days
        return max(0.0, min(100.0, (1.0 - (days - 14.0) / 76.0) * 100.0))

    @staticmethod
    def _compliance_score(site: ClinicalSite) -> float:
        """Score compliance (0-100). Fewer deviations = higher score."""
        # 0 deviations = 100, 20+ = 0
        return max(0.0, min(100.0, (1.0 - site.protocol_deviation_count / 20.0) * 100.0))

    @staticmethod
    def _rank_to_quartile(rank: int, total: int) -> Quartile:
        """Convert a 1-based rank to a quartile."""
        if total == 0:
            return Quartile.Q4
        pct = rank / total
        if pct <= 0.25:
            return Quartile.Q1
        if pct <= 0.50:
            return Quartile.Q2
        if pct <= 0.75:
            return Quartile.Q3
        return Quartile.Q4

    @staticmethod
    def _percentile(sorted_vals: list[float], pct: int) -> float:
        """Calculate a percentile from a sorted list."""
        n = len(sorted_vals)
        if n == 0:
            return 0.0
        k = (pct / 100.0) * (n - 1)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return round(sorted_vals[int(k)], 4)
        return round(sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f), 4)

    @staticmethod
    def _compute_percentile_rank(sorted_vals: list[float], value: float) -> float:
        """Compute the percentile rank of *value* in *sorted_vals*."""
        n = len(sorted_vals)
        if n == 0:
            return 50.0
        below = sum(1 for v in sorted_vals if v < value)
        equal = sum(1 for v in sorted_vals if v == value)
        return round(((below + 0.5 * equal) / n) * 100.0, 1)

    @staticmethod
    def _get_metric_value(site: ClinicalSite, metric_name: str) -> float | None:
        """Extract a numeric metric value from a ClinicalSite."""
        mapping: dict[str, Any] = {
            "enrollment_rate_per_month": site.enrollment_rate_per_month,
            "screen_failure_rate": site.screen_failure_rate,
            "total_enrolled": float(site.total_enrolled),
            "avg_query_resolution_days": site.avg_query_resolution_days,
            "protocol_deviation_count": float(site.protocol_deviation_count),
            "avg_time_to_first_patient_days": site.avg_time_to_first_patient_days,
        }
        val = mapping.get(metric_name)
        return float(val) if val is not None else None


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: SitePerformanceService | None = None
_instance_lock = threading.Lock()


def get_site_performance_service() -> SitePerformanceService:
    """Return the singleton ``SitePerformanceService``."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = SitePerformanceService()
    return _instance
